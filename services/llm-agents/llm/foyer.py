"""Ce qu'un membre du foyer raconte aux autres — ticket 100, lot 4 (conception : ticket 078).

L'AGENT CONSOLIDE SEUL, ET MEURT AVEC CE QU'IL A APPRIS
-------------------------------------------------------
Le foyer existe pourtant dans les données depuis le sceau — `household.id` — et il est le
**seul groupe social de la simulation qui porte un identifiant stable**. Sur la cohorte v6,
788 agents sur 1 000 vivent avec quelqu'un d'autre de la simulation, et ces gens-là ne se
ressemblent pas : 223 ménages sur 287 mêlent des motifs de déplacement différents, 133 des
permis différents.

Ce module en fait un canal. À la consolidation du soir, ce que les autres membres ont vécu et
appris entre dans l'appel **comme une entrée de plus**.

« Le soir » est une règle, pas une façon de parler (2026-09-25) : la première consolidation du
receveur à partir de `memoire__recit_soir_heure` (18 h), ou avant 3 h, et une seule fois par
journée simulée. Avant, le bloc partait à chaque consolidation — trois par jour en médiane —,
et un receveur qui consolidait peu trouvait jusqu'à onze bilans chez les autres. Pas de passe séparée, pas de prompt
dédié, **pas un seul appel LLM supplémentaire** : le surcoût est en jetons d'entrée sur un
appel qui a déjà lieu.

DEUX CHOSES CIRCULENT, ET ELLES NE CIRCULENT PAS PAREIL
--------------------------------------------------------
**Le récit du soir** — le bilan de la journée de chaque autre membre (D1, précisée le
2026-09-22). Ce bilan n'est pas rédigé ici : c'est la réflexion que l'agent a lui-même écrite
le soir, `a text summarising what happened today`. Le récit la **cite**. C'est la seule lecture
compatible avec la consigne « aucune nouvelle information » : un bilan que nous composerions
serait une reformulation, donc un texte que son porteur n'a jamais dit.

**Les croyances** — les concepts, sous les six règles du 078, inchangées.

UN SEUL SAUT (D2), ET QUATRE GARDES CONTRE LA BOUCLE
-----------------------------------------------------
L'auteur, le 2026-09-22 : « attention aux boucles infinies au sein de la famille ; l'agent doit
reconnaître une information déjà connue ». Aucune garde ne suffit seule.

- **G1 — un récit n'est jamais servi deux fois au même receveur.** Repère `lu_jusqu_a`, par
  receveur ET par membre, posé sur l'horodatage du dernier bilan CITÉ (pas sur l'heure du
  receveur, qui avalait un bilan daté d'avant mais arrivé après dans la file) : ce que A
  produit après le passage de B n'est pas perdu, il est lu le soir suivant. Le partage est au fil de l'eau, avec un décalage d'au plus une nuit, jamais une
  perte — et l'ordre des consolidations reste indifférent, ce qui évite une barrière dans une
  file EDF dimensionnée pour ne pas en avoir.
- **G2 — le receveur voit ce qu'il croit déjà**, dans le même appel : `known_beliefs` est dans
  le prompt de réflexion depuis le lot 3 du 071, avec ses compteurs. C'est là que l'agent
  reconnaît une information connue, et le vocabulaire pour le dire existe : `confirm` plutôt
  que `create`.
- **G3 — ce qui est entendu ne repart jamais.** `origine: entendu`, y compris après
  confirmation ultérieure par un trajet du receveur. Sa propre journée peut créer une croyance
  `vecu` distincte, qui circule, elle.
- **G4 — le détecteur de reformulation circulaire** : dans un même foyer et un même panier,
  combien de concepts distincts coexistent et combien de mots-clés ils partagent. ⚠ Il ALERTE,
  il ne coupe rien : le 071 et le 077 ont tous deux refusé qu'une mesure de similarité décide à
  la place d'une règle.

G3 ferme le cycle *A dit → B croit → B dit → A croit*. Il n'empêche pas A de répéter la même
chose chaque soir : c'est G2 qui doit l'absorber, et G4 qui doit le rendre visible si G2 échoue.

RIEN N'EST ÉCRIT DANS LE DOS DU RECEVEUR
-----------------------------------------
Le bloc est une **entrée de l'appel**, jamais une écriture dans la mémoire de B. Une phrase
entendue qui ne résonne avec rien disparaît avec l'appel — c'est le bon défaut : la mémoire ne
grossit pas d'avoir écouté.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from llm.concepts import panier_de
from llm.memory import MemoryType
from settings import settings

# Modes qu'aucun verrou de possession n'écarte : ils traversent pour tout le monde, ici comme
# dans `eligibilite()`.
MODES_SANS_VERROU: frozenset[str] = frozenset({"walking", "public_transport", "train"})

# Correspondance entre le vocabulaire des concepts (hiérarchie canonique) et celui du verrou de
# possession (`vehicle_chain._VEHICLE_MODES`). EXPLICITE et testée : trois vocabulaires de modes
# coexistent dans ce dépôt, et un mot inconnu qui passerait « par défaut » rendrait le verrou de
# permis décoratif (ticket 077, lot A).
MODE_VERS_VEHICULE: dict[str, str] = {"car": "car", "cycling": "bike", "motorbike": "bike"}


@dataclass
class Membre:
    """Ce que le foyer a besoin de savoir d'un agent, et rien de plus."""

    person_id: str
    household_id: str
    nom: str
    age: int | None
    immobile: bool = False

    @property
    def libelle(self) -> str:
        """« Matéo (8) », ou « Matéo » quand l'âge manque. Jamais un lien de parenté.

        ⚠ EMC² et eqasim donnent l'appartenance au ménage, l'âge et le genre — **pas la
        filiation**. Dire « votre fils » fabriquerait une donnée, et elle retomberait dans les
        prompts comme un fait.
        """
        return f"{self.nom} ({self.age})" if self.age is not None else self.nom


@dataclass
class EtatFoyer:
    """Ce qu'un receveur a déjà entendu. Persisté au point de reprise (ticket 075).

    Sans persistance, une reprise à chaud ferait ré-entendre au foyer entier plusieurs nuits
    déjà entendues — le défaut que le 075 a corrigé pour la mémoire, à ne pas réintroduire par
    la porte du foyer.
    """

    # G1 — clé `receveur:membre`, valeur l'horodatage simulé du dernier bilan de ce membre CITÉ
    # à ce receveur. Un point de reprise d'avant le 2026-09-25 porte des clés `receveur` seules
    # (l'heure de sa dernière consolidation) : elles servent encore de repli à la lecture.
    lu_jusqu_a: dict[str, str] = field(default_factory=dict)
    # La journée simulée (frontière à 3 h) où ce receveur a déjà entendu son foyer ce soir.
    soir_servi: dict[str, str] = field(default_factory=dict)
    # R2 — les croyances déjà montrées à ce receveur, et sous quelle forme. La clé est
    # `(receveur, doc_id)`, la valeur l'empreinte du contenu montré : un concept PRÉCISÉ change
    # d'empreinte et peut repartir, un concept simplement CONFIRMÉ ne le peut pas.
    croyances_montrees: dict[str, str] = field(default_factory=dict)


_membres: dict[str, Membre] = {}
_par_foyer: dict[str, list[str]] = {}
_etat = EtatFoyer()
_initialise = False


# ── Registre du processus ───────────────────────────────────────────────────────────────────
def initialiser(population) -> int:
    """Indexe les ménages de la population chargée. Rend le nombre de foyers multi-membres.

    Sans `household_id`, aucun foyer : une [ALARME] le dit plutôt que de laisser un run entier
    se dérouler avec un canal vide et sans le moindre symptôme.
    """
    global _initialise
    _membres.clear()
    _par_foyer.clear()
    for personne in population:
        foyer = getattr(personne, "household_id", None)
        if not foyer:
            continue
        traits = getattr(getattr(personne, "identity", None), "traits_json", None) or {}
        membre = Membre(
            person_id=str(personne.person_id),
            household_id=str(foyer),
            nom=str(traits.get("name") or personne.person_id),
            age=traits.get("age"),
            immobile=bool(getattr(personne, "immobile", False)),
        )
        _membres[membre.person_id] = membre
        _par_foyer.setdefault(membre.household_id, []).append(membre.person_id)
    _initialise = True

    multi = sum(1 for m in _par_foyer.values() if len(m) > 1)
    total = sum(1 for _ in population)
    if not _membres and total:
        logger.error(
            "[ALARME] [foyer] aucun agent de la population chargée ne porte `household_id` : "
            "le partage au sein du foyer ne touchera PERSONNE, et le run se déroulera sans le "
            "moindre symptôme. Vérifiez que la population porte bien `household.id`."
        )
    else:
        logger.info(
            f"[foyer] {len(_par_foyer)} ménage(s) indexé(s) sur {total} agent(s), dont "
            f"{multi} à plusieurs membres — {sum(len(m) for m in _par_foyer.values() if len(m) > 1)} "
            f"agent(s) ont quelqu'un à qui parler le soir"
        )
    return multi


def reinitialiser() -> None:
    """Oublie l'index et l'état. Réservé aux tests et à la fin d'un run."""
    global _initialise, _etat
    _membres.clear()
    _par_foyer.clear()
    _etat = EtatFoyer()
    _compteurs_soir.clear()
    _receveurs_tronques.clear()
    _initialise = False


def etat() -> EtatFoyer:
    return _etat


def charger_etat(brut: dict | None) -> None:
    """Relit l'état depuis un point de reprise. Un état illisible ne fait pas perdre le run."""
    global _etat
    if not brut:
        return
    try:
        _etat = EtatFoyer(
            lu_jusqu_a=dict(brut.get("lu_jusqu_a") or {}),
            croyances_montrees=dict(brut.get("croyances_montrees") or {}),
            soir_servi=dict(brut.get("soir_servi") or {}),
        )
        logger.info(
            f"[foyer] état relu du point de reprise : {len(_etat.lu_jusqu_a)} repère(s) de "
            f"lecture, {len(_etat.croyances_montrees)} croyance(s) déjà montrée(s), "
            f"{len(_etat.soir_servi)} receveur(s) déjà servi(s) un soir"
        )
    except Exception as err:  # noqa: BLE001
        logger.warning(f"[foyer] état de reprise illisible ({err}) — le foyer repart à neuf")


def etat_pour_reprise() -> dict:
    return {
        "lu_jusqu_a": dict(_etat.lu_jusqu_a),
        "croyances_montrees": dict(_etat.croyances_montrees),
        "soir_servi": dict(_etat.soir_servi),
    }


def actif() -> bool:
    return bool(getattr(settings.agent, "memoire__partage_foyer_enabled", False))


def foyer_de(person_id: str) -> str | None:
    """Le ménage de cet agent, ou `None` s'il n'en porte pas."""
    membre = _membres.get(str(person_id))
    return membre.household_id if membre else None


def autres_membres(person_id: str) -> list[Membre]:
    """Les autres membres PRÉSENTS du même ménage. R6.

    Un membre du ménage absent de la cohorte n'existe pas et ne raconte rien ; un membre
    `immobile` ne décide de rien non plus, et n'a rien à raconter.
    """
    moi = _membres.get(str(person_id))
    if moi is None:
        return []
    return [
        _membres[p]
        for p in _par_foyer.get(moi.household_id, [])
        if p != moi.person_id and not _membres[p].immobile
    ]


# ── Le récit du soir ────────────────────────────────────────────────────────────────────────
def _empreinte(texte: str) -> str:
    return hashlib.sha256((texte or "").strip().encode("utf-8")).hexdigest()[:16]


def _reflexions_depuis(long_term_memory, person_id: str, depuis: datetime | None) -> list:
    """Les bilans de journée de cet agent postérieurs au repère, du plus ancien au plus récent."""
    try:
        entrees = long_term_memory.user_metadata[str(person_id)]["entries"]
    except (KeyError, TypeError, AttributeError):
        return []
    retenues = [
        e for e in entrees
        if e.memory_type == MemoryType.REFLECTION
        and (depuis is None or e.timestamp > depuis)
        and (e.content or "").strip()
    ]
    return sorted(retenues, key=lambda e: e.timestamp)


def _lire_repere(brut: str | None) -> datetime | None:
    if not brut:
        return None
    try:
        return datetime.fromisoformat(brut)
    except (TypeError, ValueError):
        return None


def _repere(receveur_id: str, membre_id: str) -> datetime | None:
    """Le dernier bilan de ce membre déjà cité à ce receveur — ou le repère de l'ancienne forme."""
    propre = _lire_repere(_etat.lu_jusqu_a.get(f"{receveur_id}:{membre_id}"))
    return propre if propre is not None else _lire_repere(_etat.lu_jusqu_a.get(receveur_id))


def recit_du_soir(long_term_memory, receveur_id: str, maintenant: datetime) -> list[str]:
    """Ce que les autres membres ont raconté de leur journée, depuis la dernière fois.

    Une ligne par membre qui a quelque chose de neuf, citant ses bilans du plus ancien au plus
    récent. Vide quand le foyer est vide, quand le drapeau est éteint, ou quand personne n'a
    rien produit de neuf. ⚠ Aucune règle d'heure ici : c'est `bloc_du_soir` qui décide QUAND le
    foyer parle ; cette fonction dit seulement CE QU'il a à dire.

    G1 est structurel : le repère de chaque membre avance jusqu'au dernier bilan cité, et une
    réflexion déjà servie ne repart pas. Un récit n'est JAMAIS copié dans la mémoire du
    receveur — il n'existe que dans l'appel, donc il n'y a rien à re-raconter.
    """
    if not actif():
        return []
    receveur_id = str(receveur_id)
    autres = autres_membres(receveur_id)
    if not autres:
        return []

    borne_membres = int(getattr(settings.agent, "memoire__recit_soir_max", 8))
    borne_bilans = int(getattr(settings.agent, "memoire__recit_soir_max_par_membre", 8))
    lignes: list[str] = []
    reportes = 0
    membres_reportes = 0
    for membre in sorted(autres, key=lambda m: m.person_id):
        reflexions = _reflexions_depuis(
            long_term_memory, membre.person_id, _repere(receveur_id, membre.person_id)
        )
        if not reflexions:
            continue
        if len(lignes) >= borne_membres:
            # Le repère de ce membre ne bouge pas : tout ce qu'il a dit attend le soir suivant.
            reportes += len(reflexions)
            membres_reportes += 1
            continue
        cites = reflexions[:borne_bilans]
        reportes += len(reflexions) - len(cites)
        # ⚠ Le texte est CITÉ, pas reformulé. « Aucune nouvelle information » (auteur,
        # 2026-09-22) : ce qui circule est ce que son porteur a lui-même écrit, dans ses mots.
        # Le réécrire y ferait entrer une information qu'il n'a pas dite.
        citations = " Later: ".join(f'"{(e.content or "").strip()}"' for e in cites)
        lignes.append(f"- {membre.libelle} told you about their day: {citations}")
        _etat.lu_jusqu_a[f"{receveur_id}:{membre.person_id}"] = cites[-1].timestamp.isoformat()

    if reportes:
        # ⚠ Une troncature se COMPTE, et REPORTE : rien n'est perdu, les plus anciens sont
        # cités d'abord et le reste attend le soir suivant. L'[ALARME] part sur front montant,
        # par receveur — un receveur qui reste tronqué plusieurs soirs ne noie pas le journal.
        _compteurs_soir["troncatures"] += reportes
        if receveur_id not in _receveurs_tronques:
            _receveurs_tronques.add(receveur_id)
            logger.error(
                f"[ALARME] [foyer] récit du soir TRONQUÉ pour {receveur_id} le "
                f"{maintenant.isoformat()} : {reportes} bilan(s) reporté(s) au soir suivant "
                f"({membres_reportes} membre(s) au-delà de `memoire__recit_soir_max` = "
                f"{borne_membres}, bornes de `memoire__recit_soir_max_par_membre` = "
                f"{borne_bilans} bilans par membre). Rien n'est perdu ; si cela dure, le "
                f"receveur consolide trop rarement le soir pour son foyer."
            )
    else:
        _receveurs_tronques.discard(receveur_id)
    return lignes


# ── Les croyances (R1 à R6 du ticket 078) ───────────────────────────────────────────────────
def _mode_praticable(mode: str | None, traits: dict) -> bool:
    """R4 — le cas Constance / Jacques.

    Ce que Jacques apprend de la voiture ne doit **jamais** devenir une croyance de Constance,
    12 ans, sans permis et sans vélo. Aucun repli permissif : un mode inconnu ne traverse pas,
    il se compte et s'alarme.
    """
    if not mode or mode == "any":
        return True
    if mode in MODES_SANS_VERROU:
        return True
    vehicule = MODE_VERS_VEHICULE.get(mode)
    if vehicule is None:
        logger.warning(
            f"[foyer] mode « {mode} » hors de la table de correspondance — la croyance NE "
            f"TRAVERSE PAS. Un mot inconnu qui passerait par défaut rendrait le verrou de "
            f"possession décoratif (ticket 077, lot A)."
        )
        return False
    if vehicule == "car":
        return bool(traits.get("has_driving_license")) and int(
            traits.get("number_of_cars") or 0
        ) > 0
    return str(traits.get("personal_bike") or "").lower() not in ("", "no bike")


def croyances_partagees(
    long_term_memory, receveur, maintenant: datetime
) -> tuple[list[str], dict[str, int]]:
    """Ce que les autres membres ont appris et qui peut traverser. Rend (énoncés, refus par règle).

    Les refus sont comptés SÉPARÉMENT, règle par règle : si le canal est vide, c'est la
    première chose à regarder, et un compteur global ne dirait pas laquelle des six ferme la
    porte.
    """
    # « G3 » n'est pas une règle du ticket 078 : c'est la garde anti-boucle du saut unique
    # (D2). Elle est comptée ICI avec les autres depuis le 2026-09-22, parce qu'elle ne l'était
    # pas : sur le run du canal lu, 130 concepts sur 426 ont été écartés par elle sans qu'une
    # seule ligne le dise — le bilan additionnait 296 sur 426 et personne ne voyait le trou.
    # Une garde dont on ne sait pas si elle a mordu ne se vérifie pas : c'est exactement ce que
    # le dépôt a déjà payé sur les compteurs de refus du foyer.
    refus = {f"R{i}": 0 for i in range(1, 7)} | {"G3": 0}
    if not actif():
        return [], refus
    autres = autres_membres(str(receveur.person_id))
    if not autres:
        refus["R6"] += 1
        return [], refus

    traits = getattr(getattr(receveur, "identity", None), "traits_json", None) or {}
    seuil = int(getattr(settings.agent, "memoire__partage_foyer_observations_min", 1))
    borne = int(getattr(settings.agent, "memoire__partage_foyer_max_bloc", 12))
    lignes: list[str] = []
    candidats = 0

    for membre in sorted(autres, key=lambda m: m.person_id):
        try:
            entrees = long_term_memory.user_metadata[membre.person_id]["entries"]
        except (KeyError, TypeError, AttributeError):
            continue
        for concept in entrees:
            if concept.memory_type != MemoryType.CONCEPT:
                continue
            candidats += 1
            _compteurs_soir["candidats"] += 1
            # G3 / D2 — ce qui a été ENTENDU ne repart jamais, même confirmé ensuite.
            if (concept.origine or "vecu") == "entendu":
                refus["G3"] += 1
                continue
            if int(concept.observations or 0) < seuil:
                refus["R1"] += 1
                continue
            if not concept.axe_objet:
                refus["R3"] += 1
                continue
            if not _mode_praticable(concept.axe_objet, traits):
                refus["R4"] += 1
                continue
            contenu = _contenu_lisible(concept)
            if not contenu:
                refus["R3"] += 1
                continue
            cle = f"{receveur.person_id}:{getattr(concept, 'doc_id', '') or contenu[:40]}"
            empreinte = _empreinte(contenu + ("|hs" if not concept.est_servi else ""))
            if _etat.croyances_montrees.get(cle) == empreinte:
                # R2 — jamais montré deux fois. Une simple CONFIRMATION ne fait pas repartir
                # un concept : sinon une croyance que son auteur confirme chaque jour serait
                # servie chaque soir à toute la famille. Seule une précision — qui change le
                # contenu — ou une mise hors service change l'empreinte.
                refus["R2"] += 1
                continue
            if len(lignes) >= borne:
                continue
            _etat.croyances_montrees[cle] = empreinte
            if not concept.est_servi:
                lignes.append(f'- {membre.libelle} no longer believes: "{contenu}"')
            else:
                lignes.append(
                    f'- {membre.libelle} told you: "{contenu}" — they have seen it '
                    f'{int(concept.observations or 0)} time(s)'
                )

    if candidats and not lignes:
        logger.info(
            f"[foyer] {receveur.person_id} : {candidats} concept(s) examiné(s) chez ses "
            f"co-résidents, aucun ne traverse — refus par règle {refus}"
        )
    return lignes, refus


def _contenu_lisible(concept) -> str:
    """Le texte d'un concept, que son contenu soit un 5-uplet JSON ou une phrase nue."""
    import json

    brut = (concept.content or "").strip()
    if brut.startswith("["):
        try:
            return str(json.loads(brut)[0]).strip()
        except Exception:  # noqa: BLE001
            return brut
    return brut


# ── G4 — le détecteur de reformulation circulaire ───────────────────────────────────────────
_MOTS = re.compile(r"[a-zà-ÿ]{4,}", re.IGNORECASE)


def detecter_reformulation(long_term_memory, household_id: str) -> list[tuple]:
    """Combien de concepts distincts coexistent dans un même panier, et ce qu'ils partagent.

    ⚠ **Indicateur de lecture, jamais un seuil qui agit.** Le 071 et le 077 ont tous deux
    refusé qu'une mesure de similarité décide à la place d'une règle. Celui-ci alerte un
    humain ; il ne coupe rien, et il ne doit jamais le faire.

    Rend une liste de `(panier, nombre de concepts, mots partagés)` pour les paniers où
    plusieurs concepts coexistent — une famille qui redit la même chose sous quatre formes se
    voit alors d'un coup d'œil.
    """
    paniers: dict[tuple, list[str]] = {}
    for person_id in _par_foyer.get(str(household_id), []):
        try:
            entrees = long_term_memory.user_metadata[person_id]["entries"]
        except (KeyError, TypeError, AttributeError):
            continue
        for concept in entrees:
            if concept.memory_type != MemoryType.CONCEPT:
                continue
            paniers.setdefault(
                panier_de(concept.axe_objet, concept.axe_motif), []
            ).append(_contenu_lisible(concept))

    signales = []
    for panier, contenus in sorted(paniers.items(), key=lambda kv: str(kv[0])):
        if len(contenus) < 2:
            continue
        ensembles = [set(m.lower() for m in _MOTS.findall(c)) for c in contenus]
        partages = set.intersection(*ensembles) if ensembles else set()
        if partages:
            signales.append((panier, len(contenus), sorted(partages)))
    if signales:
        logger.warning(
            f"[foyer] reformulation possible dans le ménage {household_id} : "
            + " ; ".join(
                f"panier {p} — {n} concepts partageant {mots}" for p, n, mots in signales
            )
            + ". Indicateur de LECTURE : rien n'est coupé, un humain décide."
        )
    return signales


# Compteurs du soir, cumulés sur le run. Le ticket 078 § 6 les demande dans cet ordre, et la
# première mesure passe AVANT toutes les autres : si le nombre de concepts qui passent R1 est
# proche de zéro, le canal est vide et rien d'autre n'a de sens à mesurer. Le 077 a compté 225
# concepts sur 231 restés à zéro observation — R1 laisserait alors le canal fermé.
_compteurs_soir: Counter = Counter()
# Les receveurs dont le dernier récit a été tronqué — l'[ALARME] part à l'entrée seulement.
_receveurs_tronques: set[str] = set()
# Même frontière de journée que les mesures (`scripts/analysis/mesures/calcul.py`) : un récit
# entendu à 1 h 30 appartient à la soirée de la veille.
FRONTIERE_JOUR_H = 3


def compteurs() -> dict:
    """Ce que le foyer a fait depuis le début du run. Lu par le journal, jamais remis à zéro."""
    return dict(_compteurs_soir)


def journaliser_compteurs() -> None:
    """Le bilan du foyer, journalisé MÊME À ZÉRO.

    Un compteur muet ne distingue pas « le foyer n'avait rien à dire » de « le mécanisme ne
    tourne pas », et c'est la confusion qui a coûté trente jours au ticket 075.
    """
    if not actif():
        logger.info("[foyer] partage au sein du foyer ÉTEINT — aucun bloc n'a été servi.")
        return
    c = _compteurs_soir
    logger.info(
        f"[foyer] bilan du run — {c['blocs_servis']} bloc(s) servi(s) à "
        f"{c['receveurs']} consolidation(s), {c['recits']} bilan(s) et {c['croyances']} "
        f"croyance(s) transmis, {c['troncatures']} bilan(s) reporté(s) par troncature ; "
        f"{c['hors_soir']} consolidation(s) de jour et {c['deja_servi_ce_soir']} seconde(s) "
        f"consolidation(s) du soir sans bloc. Concepts examinés : "
        f"{c['candidats']}, écartés par règle — "
        + ", ".join(f"R{i}:{c[f'refus_R{i}']}" for i in range(1, 7))
        + f", G3:{c['refus_G3']} (déjà entendus, saut unique)"
    )
    # Le compte doit tomber juste. Un écart signifie qu'une sortie de la boucle ne se compte
    # nulle part, et c'est précisément ce qui rend une garde invérifiable.
    compte = c["croyances"] + sum(c[f"refus_R{i}"] for i in range(1, 7)) + c["refus_G3"]
    if c["candidats"] and compte != c["candidats"]:
        logger.error(
            f"[ALARME] [foyer] le compte ne tombe pas juste : {c['candidats']} concept(s) "
            f"examiné(s) pour {compte} issue(s) comptée(s) — {c['candidats'] - compte} "
            f"concept(s) quittent la boucle sans être comptés. Un refus invisible rend la "
            f"règle qui l'a produit invérifiable."
        )
    if c["blocs_servis"] and not c["croyances"]:
        logger.error(
            f"[ALARME] [foyer] {c['blocs_servis']} bloc(s) servi(s) et AUCUNE croyance "
            f"transmise sur tout le run : le canal des croyances est fermé. Regarder R1 "
            f"d'abord ({c['refus_R1']} concepts écartés faute d'ancrage) — c'est la première "
            f"chose à mesurer, et si elle est proche de tout, rien d'autre n'a de sens."
        )


def bloc_du_soir(long_term_memory, receveur, maintenant: datetime) -> str:
    """Le bloc « Tonight at home », prêt à entrer dans l'appel de réflexion. Vide si rien.

    ⚠ Ce bloc est une ENTRÉE de l'appel, jamais une écriture dans la mémoire du receveur. Une
    phrase entendue qui ne résonne avec rien disparaît avec l'appel : la mémoire ne grossit pas
    d'avoir écouté.
    """
    receveur_id = str(receveur.person_id)
    journee = (maintenant - timedelta(hours=FRONTIERE_JOUR_H)).date().isoformat()
    if actif() and autres_membres(receveur_id):
        # Le soir, une fois. Une consolidation de jour ou une seconde consolidation du même
        # soir n'examine RIEN et ne déplace aucun repère : ce qui aurait été dit attend la
        # bonne heure. (Un agent seul suit le chemin d'avant : son refus R6 se compte.)
        heure_soir = int(getattr(settings.agent, "memoire__recit_soir_heure", 18))
        if FRONTIERE_JOUR_H <= maintenant.hour < heure_soir:
            _compteurs_soir["hors_soir"] += 1
            return ""
        if _etat.soir_servi.get(receveur_id) == journee:
            _compteurs_soir["deja_servi_ce_soir"] += 1
            return ""

    recits = recit_du_soir(long_term_memory, receveur_id, maintenant)
    croyances, refus = croyances_partagees(long_term_memory, receveur, maintenant)
    # ⚠ Les refus étaient CALCULÉS puis jetés — la mesure n° 1 du 078 § 6, « ce qui est
    # éligible, avant tout le reste », n'était donc émise nulle part. Un canal vide se serait
    # lu comme un foyer qui n'a rien à se dire.
    _compteurs_soir["receveurs"] += 1
    _compteurs_soir["recits"] += len(recits)
    _compteurs_soir["croyances"] += len(croyances)
    for regle, combien in refus.items():
        _compteurs_soir[f"refus_{regle}"] += combien
    if not recits and not croyances:
        # Un soir sans rien de neuf ne ferme pas la soirée : ce qu'un autre membre racontera
        # à 21 h sera entendu à la consolidation suivante du receveur.
        return ""
    _etat.soir_servi[receveur_id] = journee
    _compteurs_soir["blocs_servis"] += 1
    lignes = ["Tonight at home"] + recits + croyances
    return "\n".join(lignes)
