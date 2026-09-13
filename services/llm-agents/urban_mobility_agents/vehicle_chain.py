"""Cohérence de chaîne des véhicules personnels — les règles, et rien d'autre.

Un vélo et une voiture sont des **lieux** : ils restent où leur propriétaire les a garés.
Ce module porte les trois règles (verrou de sortie, stationnement, verrou de retour), le
mode passager et le décompte des orphelins, telles que documentées dans
`docs/arch/vehicle-chain.md`. Il est extrait de `simulation_controller.py` (ticket 035,
spec 02, D1) pour que la **même** implémentation serve la simulation GAMA et l'exécution
sans simulateur (`experiences/decision.py`) : aucune règle n'est réécrite ailleurs, et le
contrôleur ré-exporte ces noms pour ses appelants historiques (tests compris).

Aucune lecture d'horloge, aucun accès réseau : des fonctions pures sur `Person`,
`Location`, `TravelPlan`, plus une métrique Prometheus et une alarme à front montant.
"""

import math
from typing import Optional, Tuple

from loguru import logger
from prometheus_client import Counter

from llm_gateway.telemetry.alarms import fire_alarme
from models import Location, Person, TravelPlan
from settings import settings

# Cohérence de chaîne des véhicules personnels (vélo, voiture). event ∈
#   unavailable   : mode écarté des options — véhicule garé ailleurs qu'au point de départ
#   no_driver     : voiture écartée faute de conducteur (mineur, ou sans permis) — cause
#                   distincte de `unavailable`, qui reste réservé à la position du véhicule
#   passenger     : trajet en voiture retenu pour un non-conducteur — un adulte du foyer
#                   conduit, la voiture ne se gare pas à destination
#   short_return  : verrou de retour non appliqué, trajet sous le seuil de distance
#   forced_return : trajet de retour au domicile restreint à ce mode (l'agent ramène son véhicule)
#   return_failed : verrou de retour inapplicable (aucun itinéraire dans ce mode) → options rendues
#   orphaned      : agent rentré au domicile, véhicule resté ailleurs (cas résiduel du modèle)
#   reset_home    : véhicule orphelin ramené au domicile par le rattrapage de fin de boucle
VEHICLE_CHAIN = Counter(
    'agent_vehicle_chain_total',
    'Événements de cohérence de chaîne des véhicules personnels, par mode et type',
    ['mode', 'event'],
)


def _road_distance_km(origin, destination) -> Optional[float]:
    """Distance routière estimée (km) : vol d'oiseau × 1,3.

    Seule estimation disponible **avant** l'appel à OTP — `plan.distance` n'existe
    qu'une fois un itinéraire choisi. Le facteur 1,3 est la convention historique de
    `_estimate_fallback_duration` ; la factoriser ici évite que le verrou de retour
    (A3) et l'estimation de durée divergent un jour.
    """
    if origin is None or destination is None:
        return None
    lat1, lon1 = math.radians(origin.lat), math.radians(origin.lon)
    lat2, lon2 = math.radians(destination.lat), math.radians(destination.lon)
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    distance_m = 2 * 6_371_000 * math.asin(math.sqrt(a))
    return distance_m * 1.3 / 1000.0



def _vehicle_mode(plan: TravelPlan) -> str:
    """Le plan mobilise-t-il un véhicule personnel, et lequel ?

    Question de **chaîne** (ticket 008), pas de mode principal : un véhicule est un lieu,
    il reste où son propriétaire l'a garé. Un plan qui comporte une jambe voiture engage la
    voiture, même si l'enquête classerait le déplacement en transports collectifs — c'est
    précisément le cas du rabattement. Cette lecture est donc volontairement distincte de
    `_primary_mode`, et son vocabulaire est celui de `_VEHICLE_MODES`.
    """
    modes = {(leg.mode or "").lower() for leg in plan.legs if not leg.is_transfer}
    if modes & {"car"}:
        return "car"
    if modes & {"bicycle", "bike"}:
        return "bike"
    if not modes - {"foot", "walk", ""}:
        return "walk"
    return "transit"


# ── Cohérence de chaîne des véhicules personnels ──────────────────────────────
# Un véhicule est un LIEU : il reste où son propriétaire l'a garé. Trois règles,
# appliquées à l'identique au vélo et à la voiture (cf. docs/arch/vehicle-chain.md) :
#   1. verrou de sortie  — le mode n'est proposé que si le véhicule est au point de départ ;
#   2. stationnement     — après le choix, le véhicule suit l'agent s'il l'a utilisé, sinon il reste ;
#   3. verrou de retour  — sur un trajet vers le domicile, si un véhicule est garé au point
#                          de départ, l'agent le ramène (candidats restreints à ce mode).
# Clés = sorties de `_vehicle_mode`, pour comparer directement au mode d'un plan.
_VEHICLE_MODES: Tuple[str, ...] = ("bike", "car")

# Seuil sous lequel le verrou de retour ne s'applique pas (A3). Sur le run de
# référence, 59,5 % des retours au domicile de moins d'1 km se faisaient en voiture
# et 7,6 % à pied, contre ~76 % de marche attendus par EMC² : le verrou obligeait
# l'agent à reprendre sa voiture pour deux cents mètres. En dessous du seuil, tous
# les modes restent offerts — au prix de quelques véhicules orphelins de plus,
# rattrapés par `_settle_vehicles_at_home`. Valeur en dur et non exposée dans
# `settings.py` : c'est une convention de modélisation documentée, pas un réglage.
RETURN_LOCK_MIN_DISTANCE_KM = 1.0

# Âge légal du permis. La population corrigée (ticket 008, A1) ne porte plus de
# permis de mineur, mais le contrôleur ne s'en remet pas à elle : c'est ici que le
# verrou est dur.
DRIVING_AGE = 18


def _can_drive(traits: dict) -> bool:
    """L'agent peut-il **conduire** une voiture ?

    Permis ET âge légal. Les deux, parce qu'aucun des deux ne suffit : une
    population générée avant les garde-fous A1 distribue des permis à des enfants
    de neuf ans, et un `has_driving_license` absent n'est pas une autorisation.
    """
    return bool(traits.get("has_driving_license", False)) and (traits.get("age", 0) or 0) >= DRIVING_AGE


def _is_car_passenger(person: Person) -> bool:
    """L'agent peut-il **monter** dans la voiture du foyer sans la conduire ?

    Trois conditions : ne pas pouvoir conduire, que le foyer ait une voiture, et
    qu'il y ait quelqu'un d'autre pour la conduire (`household_size > 1`). Un adulte
    sans permis vivant seul n'est donc pas passager — personne ne l'emmène.

    C'est le mode « enfant conduit à l'école » (v1, décision D5) : sans modélisation
    du ménage, on ne génère pas le trajet d'accompagnement du parent, on se contente
    de rendre la voiture accessible à l'enfant. EMC² compte le passager dans
    « voiture », donc la part modale reste comparable ; ce qui change, c'est que la
    voiture ne se gare plus à l'école et que l'enfant n'a pas à la ramener.
    """
    traits = person.identity.traits_json
    return (
        not _can_drive(traits)
        and _owns_car(traits)
        and (traits.get("household_size", 0) or 0) > 1
    )


# Alarme « champ `personal_bike` absent » : elle ne doit se déclencher qu'une fois
# par processus, sinon elle est émise à chaque décision de chaque agent et noie
# `make error`. Le compteur Prometheus, lui, compte tous les cas.
_bike_trait_alarm_on = False


def _owns_bike(traits: dict) -> bool:
    """L'agent possède-t-il un vélo ? Champ absent ⇒ **non**, et l'alarme sonne.

    Le défaut était l'inverse — champ absent valait « vélo normal » — au nom de la
    rétrocompatibilité avec les populations générées avant que le trait existe. C'est
    le scénario que le ticket 015 ferme : une population sans `personal_bike` mettait
    ainsi **100 % des agents à vélo, en silence**, ce qui est le pire des deux erreurs
    possibles. Le vélo est le mode dont la part modale est la plus scrutée du projet ;
    un plancher de possession à 100 % la déplace de plusieurs points sans laisser une
    seule ligne de log.

    Le repli est donc « pas de vélo », qui prive l'agent d'un mode plutôt que de lui en
    offrir un qu'il n'a pas — et il est **bruyant** : les sept populations concernées
    sont sorties du champ du loader (`data/population/old/`), donc ce chemin ne devrait
    plus jamais être emprunté. S'il l'est, c'est une régression de la chaîne de
    génération, pas un cas normal à absorber.
    """
    global _bike_trait_alarm_on
    label = traits.get("personal_bike")
    if label is None:
        if not _bike_trait_alarm_on:
            _bike_trait_alarm_on = True
            logger.error(
                "[ALARME] Trait `personal_bike` absent de traits_json — les agents "
                "concernés sont traités SANS vélo. Une population sans ce trait n'est "
                "pas exploitable : régénérez-la, ou enrichissez-la avec "
                "`python -m scripts.data.population.enrich_personal_bike <fichier>`. "
                "(Alarme émise une seule fois ; le compteur alarme_total{source="
                '"personal_bike_absent"} compte tous les agents concernés.)'
            )
        fire_alarme("personal_bike_absent")
        return False
    return str(label).lower() != "pas de vélo"


def _owns_car(traits: dict) -> bool:
    """L'agent dispose-t-il d'une voiture dans son ménage ?"""
    return (traits.get("number_of_cars", 0) or 0) > 0


def _owns_vehicle(traits: dict, mode: str) -> bool:
    return _owns_bike(traits) if mode == "bike" else _owns_car(traits)


def _same_place(a: Optional[Location], b: Optional[Location]) -> bool:
    """Deux points désignent-ils le même stationnement ?

    Tolérance en degrés plutôt qu'en mètres : les lieux d'activité proviennent tous du
    même jeu de données (eqasim) et se comparent à l'identique ; la marge absorbe les
    arrondis de sérialisation, pas une vraie distance de marche.
    """
    if a is None or b is None:
        return False
    return abs(a.lat - b.lat) < 1e-6 and abs(a.lon - b.lon) < 1e-6


def _vehicle_position(person: Person, mode: str) -> Optional[Location]:
    """Où est garé le véhicule `mode` ? Clé absente ⇒ au domicile (état initial)."""
    parked = person.state.planning_vehicle_at.get(mode)
    return parked if parked is not None else person.identity.home


def _vehicle_available(person: Person, mode: str, from_location: Optional[Location]) -> bool:
    """Le mode véhiculé peut-il être proposé pour un trajet partant de `from_location` ?

    Deux conditions, et pas seulement la possession : l'agent doit aussi avoir son
    véhicule **là où il se trouve**. Sans la seconde, un agent parti travailler en bus
    retrouvait son vélo pour repartir — sur un run de référence, 352 des 1086 trajets à
    vélo (5,9 points de part modale) reposaient sur ce vélo fantôme. La voiture, elle,
    n'avait aucune contrainte de position du tout.

    La voiture ajoute une condition de **conducteur** (A2) : un agent qui ne peut pas
    conduire ne se voit proposer la voiture que s'il peut y monter en passager — et
    dans ce cas la position du véhicule ne compte pas, puisque ce n'est pas lui qui
    l'a garé. Sinon le mode est refusé sans appel : c'est le verrou dur qui garantit
    qu'aucun mineur ni sans-permis ne conduit.
    """
    return _vehicle_unavailable_reason(person, mode, from_location) is None


# Motifs d'écart du verrou de sortie (ticket 035, spec 02 D2) — le vocabulaire de la trace
# de décision. `retour_force` et `plafond` sont produits plus loin dans la chaîne
# (experiences/decision.py) ; ils figurent ici pour que la liste soit complète en un endroit.
MOTIF_NON_POSSEDE = "non_possede"
MOTIF_PAS_DE_CONDUCTEUR = "pas_de_conducteur"
MOTIF_VEHICULE_AILLEURS = "vehicule_ailleurs"
MOTIF_RETOUR_FORCE = "retour_force"
MOTIF_PLAFOND = "plafond"
MOTIFS_ECART = (MOTIF_NON_POSSEDE, MOTIF_PAS_DE_CONDUCTEUR, MOTIF_VEHICULE_AILLEURS,
                MOTIF_RETOUR_FORCE, MOTIF_PLAFOND)


def _vehicle_unavailable_reason(person: Person, mode: str, from_location: Optional[Location]) -> Optional[str]:
    """Pourquoi le mode véhiculé n'est PAS proposable depuis `from_location` — `None` s'il l'est.

    C'est la seule implémentation du verrou de sortie : `_vehicle_available` n'en est que la
    lecture booléenne, et la trace de décision (spec 02, D6) en reprend le motif tel quel.
    Ordre des tests, celui du document d'architecture : possession, conducteur/passager,
    position.
    """
    if not _owns_vehicle(person.identity.traits_json, mode):
        return MOTIF_NON_POSSEDE
    if mode == "car" and not _can_drive(person.identity.traits_json):
        return None if _is_car_passenger(person) else MOTIF_PAS_DE_CONDUCTEUR
    if not settings.agent.vehicle_chain_enabled:
        return None
    parked_at = _vehicle_position(person, mode)
    if parked_at is None:
        # Population sans domicile connu (le loader eqasim les écarte dès qu'une bbox est
        # posée) : on ne sait pas où est le véhicule. Dégrader vers l'ancien comportement
        # vaut mieux que priver l'agent de tout mode véhiculé pour toute la simulation.
        VEHICLE_CHAIN.labels(mode=mode, event="no_home").inc()
        return None
    return None if _same_place(parked_at, from_location) else MOTIF_VEHICULE_AILLEURS


def _vehicles_parked_at(person: Person, location: Optional[Location]) -> set[str]:
    """Véhicules possédés garés en `location`, **hors domicile**.

    Sert au verrou de retour : ce sont les véhicules que l'agent doit ramener quand il
    rentre chez lui. Un véhicule déjà au domicile n'a rien à ramener.
    """
    if _same_place(location, person.identity.home):
        return set()
    return {
        mode for mode in _VEHICLE_MODES
        if _owns_vehicle(person.identity.traits_json, mode)
        and _same_place(_vehicle_position(person, mode), location)
    }


def _park_vehicles(
    person: Person,
    plan: Optional[TravelPlan],
    from_location: Optional[Location],
    destination: Optional[Location],
) -> None:
    """Met à jour la position des véhicules après le choix d'un plan.

    Le véhicule utilisé suit l'agent jusqu'à la destination ; les autres restent garés
    où ils étaient. Aucun retour implicite au domicile : c'était le dernier vestige de
    téléportation de la version booléenne (un vélo laissé au bureau était réputé
    retrouvé à la maison le soir).
    """
    if plan is None or destination is None:
        return
    mode = _vehicle_mode(plan)
    if mode not in _VEHICLE_MODES:
        return
    if mode == "car" and _is_car_passenger(person):
        # Ce n'est pas sa voiture : un adulte du foyer l'a conduit et repart avec.
        # Ne rien garer à destination est ce qui empêche, plus loin, le verrou de
        # retour d'obliger un enfant de douze ans à ramener la voiture de l'école.
        return
    # Défensif : le verrou de sortie a déjà écarté les plans dont le véhicule est
    # ailleurs — on ne déplace un véhicule que depuis sa position réelle.
    if not _same_place(_vehicle_position(person, mode), from_location):
        return
    if _same_place(destination, person.identity.home):
        # Retour au domicile : on retire la clé plutôt que de mémoriser le domicile, pour
        # préserver l'invariant « clé absente ⇒ véhicule au domicile ».
        person.state.planning_vehicle_at.pop(mode, None)
    else:
        person.state.planning_vehicle_at[mode] = destination


def _orphaned_vehicles(person: Person) -> set[str]:
    """Véhicules garés ailleurs qu'au domicile alors que l'agent y est rentré.

    Cas résiduel assumé du modèle simple : domicile → travail en voiture, travail →
    sport à pied, sport → domicile en bus. Le verrou de retour ne s'applique qu'aux
    véhicules garés au point de DÉPART du trajet de retour ; celui-ci est resté au
    travail. Mesuré (agent_vehicle_chain_total{event="orphaned"}) et, par défaut,
    rattrapé au domicile pour ne pas priver l'agent de sa voiture les jours suivants.
    """
    return {
        mode for mode in _VEHICLE_MODES
        if _owns_vehicle(person.identity.traits_json, mode)
        and not _same_place(_vehicle_position(person, mode), person.identity.home)
    }



def _chain_stake_modes(person: Person) -> list[str]:
    """Modes véhiculés dont la position engage la chaîne de CE persona.

    La voiture ne compte que pour un conducteur (un passager n'a pas de voiture
    positionnelle — cf. `_vehicle_available`, ticket 008 A2) ; le vélo, dès
    qu'il est possédé, passager compris (son vélo suit les règles normales).
    """
    traits = person.identity.traits_json
    modes = []
    if _owns_car(traits) and _can_drive(traits):
        modes.append("car")
    if _owns_bike(traits):
        modes.append("bike")
    return modes
