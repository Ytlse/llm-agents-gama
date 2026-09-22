import asyncio
import csv
import itertools
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mobility_core.housing_type import TRAIT_KEY as HOUSING_TRAIT_KEY, key_for
from mobility_core.mode_hierarchy import hierarchy as _mode_hierarchy
from mobility_core.population_reference import COURONNES, OUT_OF_PERIMETER
from mobility_core.residence_zone import TRAIT_KEY as RESIDENCE_TRAIT_KEY
from models import Person, TravelPlan
from settings import settings

# Valeurs acceptées dans la colonne « Lieu de résidence ». `hors périmètre` en est
# une : un domicile connu et situé hors des 453 communes de l'enquête n'a aucune
# cible par zone, et sa masse doit être COMPTÉE plutôt que diluée dans la 3ᵉ
# couronne (axe A4 du ticket 020). Une valeur hors de cette liste est ramenée à vide
# plutôt que journalisée : la page de synthèse joint cette colonne sur les libellés
# EMC², une valeur exotique y disparaîtrait sans être comptée.
RESIDENCE_VALUES = frozenset((*COURONNES, OUT_OF_PERIMETER))

logger = logging.getLogger(__name__)

_MODE_HIERARCHY = _mode_hierarchy()

# Jeux de modes inconnus déjà signalés — l'alarme se déclenche sur front montant.
_UNKNOWN_MODES_SEEN: set[str] = set()

# Familles de modes, DÉDUITES de la hiérarchie de l'enquête et non plus écrites ici
# (ticket 022). Cinq listes littérales cohabitaient dans le dépôt et une seule d'entre
# elles suffisait à faire dériver une part modale : une liste incomplète rend un chiffre
# plausible et faux (le Téléo compté en marche, le TER compté en marche). L'ordre des
# tests suit désormais l'annexe « Hiérarchie des modes » du rapport AUAT/CEREMA (p. 53),
# contrôlée sur les microdonnées : métro > tram > téléphérique > bus > train > voiture >
# deux-roues motorisé > vélo > marche.
#
# Les cinq noms survivent parce qu'ils sont cités ailleurs (`llm_agent`, le test de
# parité) ; ils ne sont plus une source, seulement une vue.
_BUS_MODES = frozenset().union(*(_MODE_HIERARCHY.legs_by_family[f]
                                 for f in ("metro", "tram", "cableway", "bus")))
_RAIL_MODES = _MODE_HIERARCHY.legs_by_family["rail"]
_CAR_MODES = _MODE_HIERARCHY.legs_by_family["car"]
_BIKE_MODES = _MODE_HIERARCHY.legs_by_family["bicycle"]
_WALK_MODES = _MODE_HIERARCHY.legs_by_family["foot"]

_PURPOSE_FR = {
    "work": "Travail",
    "education": "Etude",
    "shop": "Achats",
    "shopping": "Achats",
    "escort": "Accompagnement",
    "accompany": "Accompagnement",
}

# Modes canoniques (mobility_llm.mode_choice) → libellés des colonnes, alignés sur
# le vocabulaire de « Mode de transport Choisi ». Les libellés viennent de la hiérarchie
# (ticket 022) : une seule table les décide. L'ORDRE, en revanche, reste celui de
# l'affichage et non celui de la hiérarchie — il fixe les colonnes du CSV, et les changer
# rendrait les `moves.csv` archivés incomparables aux nouveaux. `other` n'est pas une
# famille de l'enquête : c'est le fourre-tout du dépôt, il n'a donc pas de rang.
_COLUMN_ORDER = ("walking", "cycling", "car", "public_transport", "train", "motorbike")
_LABEL_BY_CANONICAL = {_MODE_HIERARCHY.canonical_mode[family]:
                       _MODE_HIERARCHY.journal_label[family]
                       for family in _MODE_HIERARCHY.families}
# Un mode canonique absent de la hiérarchie lève ici, à l'import : une colonne muette
# vaudrait mieux qu'un libellé faux, mais une colonne absente vaut mieux que les deux.
_CANONICAL_FR = {canonical: _LABEL_BY_CANONICAL[canonical] for canonical in _COLUMN_ORDER}
_CANONICAL_FR["other"] = "Autres modes"

# Une colonne par mode : la répartition estimée par le LLM avant tirage (somme = 100).
# Un mode non proposé vaut 0 (et non vide) — c'est ce qui distingue « était possible mais
# jugé nul » de « décision sans répartition » (mono-choix, erreur LLM, cache hérité), où
# toutes ces colonnes sont vides.
MODE_PROBABILITY_HEADERS = [f"P({label}) %" for label in _CANONICAL_FR.values()]

# Valeurs admises de « Contrainte de chaîne » (ticket 008, A4) — une seule par ligne :
#   ""              aucune contrainte, le jeu de choix est celui d'OTP ;
#   retour_force    verrou de retour appliqué, options restreintes au mode du véhicule garé ;
#   passager        trajet en voiture conduite par un tiers du foyer ;
#   sortie_bloquee  un mode véhiculé possédé a été écarté faute de véhicule sur place.
# La colonne **explique**, elle ne filtre pas : ces lignes restent dans le scoring, et
# la page de synthèse en affiche la répartition à côté des méthodes de sélection.
CHAIN_CONSTRAINTS = ("", "retour_force", "passager", "sortie_bloquee")

# Valeurs admises de « Anticipation » (ticket 014) — ce que le prompt de CE trajet
# contenait comme contexte d'anticipation :
#   ""        décision sans prompt (cache, mono-option) ou anticipation désactivée ;
#   agenda    bloc complet — agenda glissant + position des véhicules (+ météo du jour) ;
#   meteo     météo du jour seule (agent sans véhicule à chaîner).
# Indispensable pour segmenter l'A/B avant/après : les non-motorisés n'ont pas le bloc.
ANTICIPATION_VALUES = ("", "agenda", "meteo")

CSV_HEADERS = [
    "Référence",
    "Trajet",
    "ID Trajet",
    "Mode de transport Choisi",
    "Plus rapide",
    "Modes proposés au LLM",
    *MODE_PROBABILITY_HEADERS,
    "Lieu de résidence",
    "Genre",
    "Âge",
    "Occupation principale",
    "Type de logement",
    "Motifs de déplacement",
    "Distance parcourue",
    "Méthode de sélection",
    "Contrainte de chaîne",
    "Anticipation",
    "Fournisseur & Modèle",
    "Température",
    "Mémoire à court terme",
    "Mémoire à long terme",
    "Filtre de perception",
    "Traits de personnalité",
    "Météo Température (°C)",
    "Météo Condition",
    "Météo Précipitations (mm)",
    "Raisonnement",
    "Retard planification (s)",
    "Heure de calcul",
    "Temps simulé",
    "Heure de départ",
    "ID Personne",
    "ID Activité",
    # Ticket 035 (spec 04, G6) : d'où viennent les propositions présentées — « enregistree:5 »,
    # « enregistree:3,recalculee:horaire:2 », « en_vol:6 » (calcul en vol, pas de jeu), « hors_jeu:… ».
    # Ajoutées en DERNIÈRE position : aucun consommateur ne lit moves.csv par index.
    "Source des propositions",
    # Propositions écartées avant présentation, par motif (spec 02, D2/D6) :
    # « vehicule_ailleurs:car;retour_force:foot,bus;plafond:2 » — vide si rien n'a été écarté.
    "Écartées (motifs)",
    # Identifiant du lot de la passerelle qui a porté la décision (spec 03, S5) — vide sinon.
    "Identifiant lot",
    # Ticket 077, lot E2 — l'index RETENU parmi les options présentées, pour TOUTE décision.
    # Il n'existait que dans `pipeline_timing.csv`, et seulement pour 66 des 514 trajets du run
    # du ticket 075 : impossible d'y lire si l'agent changeait d'itinéraire à motif constant.
    "Index retenu",
    # Nombre d'options réellement présentées. Sans lui, un index de 0 ne se distingue pas d'un
    # choix contraint : l'absence d'alternative produirait une « fidélité » parfaite.
    "Options présentées",
    # Ticket 077, lot E5 — la décision vient-elle du cache sémantique ou d'un appel direct.
    # « cache », « direct », ou vide quand aucun modèle n'a été sollicité.
    "Origine de la décision",
    # Ticket 077, lot E3 — descriptif des options présentées, index par index.
    "Options (descriptif)",
    # Ticket 079, élargi au ticket 100 — l'événement en vigueur, et le jour RELATIF à son
    # premier jour (−2, −1, 0, +1…). Renseignés pour TOUTE décision, y compris les jours
    # nominaux : le jour relatif est l'abscisse des courbes de décrochage et de retour, et une
    # abscisse qui n'existerait que les jours d'événement ne tracerait rien. Vides quand aucun
    # événement n'est déclaré.
    #
    # ⚠ Les deux premiers gardent leur NOM du ticket 079. Les renommer casserait la relecture
    # des runs déjà archivés — et ce sont eux qui portent les chiffres publiés du § 7.2. Le
    # vocabulaire neuf vit dans `evenements.jsonl` ; ici, on ajoute sans substituer.
    "Choc",
    "Jour relatif au choc",
    # Ticket 100, lot 5 — le rôle de l'agent dans le dispositif : `expose`, `co_resident`
    # (même toit qu'un exposé, rien reçu — c'est chez lui que se lit la diffusion) ou
    # `temoin`. Vide quand le dispositif ne sait pas encore qui lit : une colonne vide n'est
    # pas un rôle, et écrire `temoin` ferait passer une ignorance pour une mesure.
    "Rôle",
    "Raison d'exposition",
]


def _residence_zone(traits: dict) -> str:
    """Couronne de résidence — LUE sur le persona, jamais recalculée (ticket 021).

    Le trait est posé à la génération de population (`scripts/data/population/
    enrich_residence_zone.py`) depuis le découpage **par liste de communes** de
    l'enquête, celui contre lequel les parts modales par zone sont publiées.

    ⚠ **Ce module n'importe plus `geo_reference.residence_zone`, et c'est délibéré.**
    Cette fonction classe par DISTANCE à l'hypercentre (8 / 20 / 40 km), ce qui n'est
    pas la définition de l'enquête : le ticket 020 a mesuré 24,4 % de personas mal
    classés et 66 « faux Toulousains » habitant Blagnac ou Balma. Tant que l'import
    existait, un repli « raisonnable » pouvait être rétabli en une ligne par
    inadvertance ; en le retirant, le repli devient impossible plutôt que déconseillé.

    Vide quand le persona ne porte pas le trait — population générée avant le ticket
    021, ou domicile sans coordonnées. Vide n'est donc pas une modalité, exactement
    comme une cellule de probabilité vide n'est pas un 0. `hors périmètre` en est une,
    en revanche : le domicile est connu et il est dehors, il n'a aucune cible EMC², et
    sa masse se compte au lieu de se diluer dans la 3ᵉ couronne.
    """
    value = str(traits.get(RESIDENCE_TRAIT_KEY) or "").strip()
    return value if value in RESIDENCE_VALUES else ""


def _housing_type(traits: dict) -> str:
    """Type de logement du persona, aux modalités de la référence EMC².

    Le trait est posé à la génération de population (`scripts/data/population/
    enrich_housing_type.py`) : il est **imputé** depuis la loi que l'enquête observe
    dans la zone fine du domicile, jamais tiré ici. Ce module ne fait que le recopier.

    Vide quand le persona n'en porte pas — population générée avant l'action A2, ou
    domicile hors de la couche de zones fines, où l'on ne devine pas. Vide n'est donc
    pas une modalité, exactement comme une cellule de probabilité vide n'est pas un 0.
    Une valeur hors référentiel est ramenée à vide plutôt que journalisée : la page de
    synthèse joint cette colonne sur les libellés EMC², une valeur exotique y
    disparaîtrait sans être comptée.
    """
    label = str(traits.get(HOUSING_TRAIT_KEY) or "").strip()
    return label if key_for(label) else ""


def _log_unknown_modes(modes: set) -> None:
    """Alarme sur front montant : un mode que la hiérarchie ignore ne doit pas passer muet.

    Un mode absent de la hiérarchie atterrit dans « Autres modes », qui est **exclu** du
    scoring EMC² (`frames.CHOSEN_MODE_MAP` le range dans `autres`). Sa masse disparaît donc
    d'une part modale sans rien casser : c'est le défaut du Téléo (2026-08-26) et celui du
    TER (2026-09-04), deux fois le même mécanisme. Une seule ligne par jeu de modes inconnu,
    pour ne pas noyer le journal d'un run de plusieurs milliers de déplacements.
    """
    cle = ",".join(sorted(str(m) for m in modes))
    if cle in _UNKNOWN_MODES_SEEN:
        return
    _UNKNOWN_MODES_SEEN.add(cle)
    logger.error(
        "[ALARME] Modes hors hiérarchie dans un plan : {%s} → colonne « Autres modes », "
        "donc hors scoring EMC². Ajoutez-les à mobility_core/data/mode_hierarchy_emc2.json "
        "(scripts/progedo_logit/export_mode_hierarchy.py, table FAMILLES).", cle)


def _plan_transport_mode(plan: Optional[TravelPlan]) -> str:
    if plan is None:
        return ""
    non_transfer = [leg for leg in (plan.legs or []) if not leg.is_transfer]
    if not non_transfer:
        return "Marche"
    modes = {(leg.mode or "").lower() for leg in non_transfer}
    # Un seul appel, un seul ordre : celui de l'enquête (cf. `llm_module.core.
    # mode_hierarchy`). « Autres modes » n'est plus la sortie d'une cascade épuisée mais
    # celle d'un mode que la hiérarchie ne connaît pas — un cas à voir, pas à absorber.
    label = _MODE_HIERARCHY.primary_label(modes)
    if label is None:
        _log_unknown_modes(modes)
        return "Autres modes"
    return label


def _available_modes_summary(options: Optional[list]) -> str:
    if not options:
        return ""
    return " | ".join(_plan_transport_mode(opt) for opt in options)


def _contexte_choc(start_time_ms: Optional[int], person_id: str = "") -> tuple:
    """Tickets 079 et 100 — `(événement, jour relatif, rôle, raison)` pour cette décision.

    Renseigné pour TOUTE décision d'un run à événement, y compris les jours nominaux : le jour
    relatif est l'abscisse des courbes de décrochage et de retour, et une abscisse qui
    n'existerait que les jours d'événement ne tracerait rien. Quatre valeurs vides quand aucun
    événement n'est déclaré, ce qui laisse les runs nominaux rigoureusement identiques à ce
    qu'ils étaient.

    Ne lève jamais : une colonne de contexte absente vaut mieux qu'une décision perdue.
    """
    try:
        from llm import evenements as evenements_module

        registre = evenements_module.registre()
        if registre is None or start_time_ms is None:
            # ⚠ Quatre valeurs, comme toutes les sorties de cette fonction : une ligne de
            # `moves.csv` qui n'a pas le nombre de colonnes de son en-tête décale tout ce qui
            # suit, et le décalage ne se voit qu'à la relecture, quand il est trop tard.
            return ("", "", "", "")
        role, raison = registre.role_de(str(person_id))
        return (
            registre.evenement.evenement_id,
            registre.jour_relatif(int(start_time_ms) // 1000),
            role,
            raison,
        )
    except Exception:  # noqa: BLE001
        return ("", "", "", "")


def _options_descriptif(options: Optional[list]) -> str:
    """Descriptif des options PRÉSENTÉES — ticket 077, lot E3.

    « 0:car:487s:6.5km | 1:foot,bus,foot:3480s:7.5km ». Un champ par option, dans l'ordre de
    la liste, donc l'index y est celui que porte la colonne « Index retenu ».

    ⚠ Pourquoi cette colonne existe. Jusqu'ici, le descriptif des options n'était reconstituable
    qu'en relisant le TEXTE des prompts de `llm_exchanges.jsonl`, et l'appariement d'un trajet
    à son bloc de prompt ne retrouvait que 247 des 430 trajets du run du ticket 075. Sans
    descriptif, on ne peut pas dire si un agent a changé d'ITINÉRAIRE à mode constant — ce qui
    est précisément la question que la mémoire pose.

    La durée est en secondes et la distance en kilomètres : deux unités déjà employées par les
    colonnes voisines, et aucun arrondi qui masquerait deux options proches.
    """
    if not options:
        return ""
    parts = []
    for index, option in enumerate(options):
        try:
            duree = int(max(0, (option.end_time - option.start_time) // 1000))
        except (AttributeError, TypeError):
            duree = ""
        parts.append(
            f"{index}:{option.mode_label() or '?'}:{duree}s:{_plan_distance_km(option)}km"
        )
    return " | ".join(parts)


def _mode_probability_cells(distribution: Optional[dict]) -> list:
    """Ventile la répartition par mode sur une colonne par mode (ordre `_CANONICAL_FR`).

    Sans répartition (mono-choix, erreur LLM, point de cache hérité), toutes les cellules
    sont vides — à distinguer d'un 0, qui signifie « le LLM a explicitement écarté ce mode ».
    """
    if not distribution:
        return [""] * len(_CANONICAL_FR)
    return [round(distribution.get(mode, 0.0) * 100, 1) for mode in _CANONICAL_FR]


def _plan_distance_km(plan: Optional[TravelPlan]) -> str:
    if plan is None:
        return ""
    if plan.distance is not None:
        return str(round(plan.distance / 1000, 2))
    total = sum(leg.get_distance() for leg in (plan.legs or []))
    return str(round(total / 1000, 2))


class GamaArrivalsLogger:
    _instance: Optional["GamaArrivalsLogger"] = None

    # Ticket 079 — `retard_injecte_s` est en DERNIÈRE position et distinct de `delay_s` :
    # l'un est ce que la simulation a mesuré, l'autre ce qu'un choc déclaré a fait subir. Les
    # confondre rendrait toute relecture d'une campagne à choc impossible.
    _HEADERS = ["move_id", "person_id", "arrive_at", "expected_arrive_at", "delay_s", "started_at", "schedule_at", "departure_delay_s", "timed_out", "retard_injecte_s"]

    def __init__(self):
        self._path: Optional[Path] = None
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "GamaArrivalsLogger":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_header(self):
        path = Path(settings.app.log_file).parent / "gama_results" / "gama_arrivals.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        needs_header = not path.exists()
        self._path = path
        if needs_header:
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(self._HEADERS)

    def _write_arrival(self, move_id: str, person_id: str, arrive_at: int, expected_arrive_at: int,
                       started_at: Optional[int], schedule_at: Optional[int], timed_out: bool,
                       retard_injecte_s: int = 0):
        self._ensure_header()
        delay_s = arrive_at - expected_arrive_at
        departure_delay_s = (started_at - schedule_at) if started_at is not None and schedule_at is not None else None
        with open(self._path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([move_id, person_id, arrive_at, expected_arrive_at, delay_s,
                                    started_at, schedule_at, departure_delay_s, timed_out,
                                    int(retard_injecte_s)])

    async def log_arrival(self, move_id: str, person_id: str, arrive_at: int, expected_arrive_at: int,
                          started_at: Optional[int] = None, schedule_at: Optional[int] = None,
                          timed_out: bool = False, retard_injecte_s: int = 0):
        # Écriture déportée hors de l'event loop (open/write bloquants) ; le lock asyncio
        # garantit l'ordre des lignes et l'unicité de l'écriture d'en-tête.
        async with self._lock:
            await asyncio.to_thread(self._write_arrival, move_id, person_id, arrive_at,
                                    expected_arrive_at, started_at, schedule_at, timed_out,
                                    retard_injecte_s)


class MoveLogger:
    _instance: Optional["MoveLogger"] = None

    def __init__(self):
        self._path: Optional[Path] = None
        self._lock = asyncio.Lock()
        self._counter = itertools.count(1)

    @classmethod
    def get_instance(cls) -> "MoveLogger":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _resolve_path(self) -> Path:
        return Path(settings.app.log_file).parent / "moves.csv"

    def _ensure_header(self):
        path = self._resolve_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        needs_header = not path.exists()
        self._path = path
        if needs_header:
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(CSV_HEADERS)

    async def log_move(
        self,
        person: Person,
        plan: Optional[TravelPlan],
        purpose: Optional[str],
        selection_method: str,
        provider_model: str,
        faster_itinerary: Optional[TravelPlan],
        reasoning: str,
        chain_constraint: str = "",
        anticipation: str = "",
        weather_temp: Optional[float] = None,
        weather_condition: Optional[str] = None,
        weather_precip_mm: Optional[float] = None,
        late_s: int = 0,
        move_id: str = "",
        simulated_time: Optional[int] = None,
        start_time: Optional[int] = None,
        available_options: Optional[list] = None,
        activity_id: Optional[str] = None,
        mode_probabilities: Optional[dict] = None,
        sources: str = "",
        ecartees: str = "",
        lot: str = "",
        selected_index: Optional[int] = None,
        origine_decision: str = "",
    ):
        async with self._lock:
            computed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            trip_id = next(self._counter)
            traits = person.identity.traits_json
            home = person.identity.home

            gender_raw = traits.get("gender", "")
            gender = "Homme" if gender_raw == "Male" else "Femme" if gender_raw == "Female" else gender_raw

            purpose_fr = _PURPOSE_FR.get((purpose or "").lower(), purpose or "")

            no_move = selection_method == "Pas de déplacement (même localisation)"
            row = [
                settings.workdir.name,
                trip_id,
                move_id,
                "Aucun" if no_move else _plan_transport_mode(plan),
                _plan_transport_mode(faster_itinerary),
                _available_modes_summary(available_options),
                *_mode_probability_cells(mode_probabilities),
                _residence_zone(traits),
                gender,
                traits.get("age", ""),
                traits.get("main_occupation", ""),
                _housing_type(traits),
                purpose_fr,
                _plan_distance_km(plan),
                selection_method,
                chain_constraint if chain_constraint in CHAIN_CONSTRAINTS else "",
                anticipation if anticipation in ANTICIPATION_VALUES else "",
                provider_model,
                settings.agent.llm_params.get("temperature", ""),
                True,
                settings.agent.long_term_memory_enabled,
                settings.agent.long_term_memory_filter_by_datetime,
                "personality" in traits,
                weather_temp if weather_temp is not None else "",
                weather_condition if weather_condition is not None else "",
                weather_precip_mm if weather_precip_mm is not None else "",
                reasoning,
                late_s,
                computed_at,
                simulated_time if simulated_time is not None else "",
                # `tz=timezone.utc` sur un horodatage de l'horloge de GAMA rend l'heure
                # MURALE — c'est la définition de `sim_clock.wall_clock` — et ne dépend
                # pas du `TZ` du processus. Laissé tel quel : la colonne « Heure de
                # départ » de moves.csv est déjà l'heure des agents, et la réécrire à
                # valeur identique casserait la comparaison avec les runs archivés.
                datetime.fromtimestamp(start_time / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if start_time is not None else "",
                person.person_id,
                activity_id if activity_id is not None else "",
                sources or "",
                ecartees or "",
                lot or "",
                "" if selected_index is None else int(selected_index),
                len(available_options) if available_options else 0,
                origine_decision or "",
                _options_descriptif(available_options),
                *_contexte_choc(start_time, person.person_id),
            ]

            # Écriture déportée hors de l'event loop (open/write bloquants)
            await asyncio.to_thread(self._write_row, row)

    def _write_row(self, row: list):
        self._ensure_header()
        with open(self._path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
