"""Une seule manière de décider (ticket 035, spec 02).

Le mode sans simulateur et la simulation GAMA appellent **ces** fonctions, et rien d'autre, pour
passer des propositions brutes d'un déplacement à la décision archivée :

    eligibilite()  →  plafonner()  →  ordre_presentation()  →  decider()  →  avancer_chaine()

Aucune règle de la chaîne des véhicules n'est écrite ici : tout est délégué à
`urban_mobility_agents.vehicle_chain` (D3). Ce module ajoute ce que le contrôleur ne produisait
pas : le **motif** de chaque écart, l'**ordre** déterministe de présentation, la **trace**
complète de la décision (D6) et le contrat `Decideur` (D1). Il ne lit ni l'horloge ni le fuseau
du processus (D11) : toute heure vient du contexte fourni.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Protocol

from models import Location, Person, TravelPlan
from settings import settings
from urban_mobility_agents.candidats import _select_candidates, _selection_group
from urban_mobility_agents.vehicle_chain import (
    _VEHICLE_MODES,
    MOTIF_PAS_DE_CONDUCTEUR,
    MOTIF_PLAFOND,
    MOTIF_RETOUR_FORCE,
    RETURN_LOCK_MIN_DISTANCE_KM,
    _can_drive,
    _is_car_passenger,
    _orphaned_vehicles,
    _owns_vehicle,
    _park_vehicles,
    _road_distance_km,
    _vehicle_mode,
    _vehicle_unavailable_reason,
    _vehicles_parked_at,
)

# ── Sources d'une proposition (spec 04, G6) ──────────────────────────────────
SOURCE_ENREGISTREE = "enregistree"  # servie depuis le jeu enregistré
SOURCE_EN_VOL = "en_vol"  # calculée par les moteurs pendant l'exécution (pas de jeu)
SOURCE_HORS_JEU = "hors_jeu"  # déplacement que le jeu ne couvre pas (question 9)
SOURCE_LOCALE = "locale"  # produite sans moteur (car scolaire synthétique)
PREFIXE_RECALCUL_OFFRE = "recalculee:offre"
PREFIXE_RECALCUL_HORAIRE = "recalculee:horaire"
PREFIXE_RECALCUL_OFFRE_JOUR = (
    "recalculee:offre_jour"  # autre jour simulé que celui du jeu (décision 18)
)

# ── Méthodes de décision (vocabulaire de la trace) ───────────────────────────
METHODE_SANS_SOLUTION = (
    "sans_solution"  # aucune proposition praticable, décideur non sollicité
)
METHODE_CHOIX_UNIQUE = "choix_unique"  # une seule proposition, décideur non sollicité
METHODE_DECIDEUR = "decideur"  # réponse exploitable du décideur
METHODE_REPLI_UNIFORME = (
    "repli_uniforme"  # réponse inexploitable → tirage uniforme (D10)
)
METHODE_ERREUR = "erreur"  # le décideur n'a pas répondu : PAS une décision
# R13 : le modèle ne PEUT pas décider (hors domaine) — non-décision TERMINALE, comptée,
# ni réessayée (contrairement à ERREUR) ni fabriquée (contrairement au repli uniforme).
METHODE_MODELE_NON_IMPUTABLE = "modele_non_imputable"

# Contrainte de chaîne telle que journalisée dans moves.csv (vehicle-chain.md) —
# une seule valeur par décision, priorité passager > retour_force > sortie_bloquee.
CONTRAINTE_AUCUNE = ""
CONTRAINTE_RETOUR_FORCE = "retour_force"
CONTRAINTE_SORTIE_BLOQUEE = "sortie_bloquee"
CONTRAINTE_PASSAGER = "passager"


@dataclass
class Proposition:
    """Une manière d'effectuer le déplacement, et d'où elle vient."""

    plan: TravelPlan
    source: str = SOURCE_EN_VOL

    @property
    def code(self) -> str:
        try:
            return self.plan.get_code() or self.plan.id
        except TypeError:
            # Jambe sans `transit_route` (plan de test ou de repli) : l'identifiant fait foi.
            return self.plan.id

    @property
    def mode_vehicule(self) -> str:
        return _vehicle_mode(self.plan)

    @property
    def mode(self) -> str:
        return self.plan.mode_label() or "unknown"


@dataclass(frozen=True)
class Ecart:
    """Une proposition écartée, et pourquoi (D2, D6)."""

    code: str
    mode: str
    motif: str


@dataclass
class ResultatFiltre:
    """Sortie d'`eligibilite` : ce qui reste, ce qui est parti, et ce que le contrôleur compte."""

    eligibles: list[Proposition]
    ecartees: list[Ecart]
    # Événements de la métrique `agent_vehicle_chain_total{mode,event}` — le contrôleur les
    # incrémente, le runner les compte : la sémantique reste celle de vehicle-chain.md.
    evenements: list[tuple[str, str]]
    contrainte: str = CONTRAINTE_AUCUNE


def modes_vehicules_eligibles(
    person: Person, from_location: Location | None
) -> dict[str, bool]:
    """Verrou de sortie par mode véhiculé — ce que le contrôleur passe à OTP (`include_*`)."""
    return {
        mode: _vehicle_unavailable_reason(person, mode, from_location) is None
        for mode in _VEHICLE_MODES
    }


def eligibilite(
    person: Person,
    from_location: Location | None,
    propositions: Sequence[Proposition],
    purpose: str | None,
    destination: Location | None,
) -> ResultatFiltre:
    """D2 — écarte ce que la personne ne peut pas emprunter, dans l'ordre documenté.

    1. verrou de sortie, par mode véhiculé : possession, conducteur/passager, position ;
    2. verrou de retour : retour au domicile de plus de `RETURN_LOCK_MIN_DISTANCE_KM` avec un
       véhicule garé au départ ⇒ seules les propositions de ce mode restent.
    Marche et transports collectifs ne sont jamais écartés ici (D2, dernière phrase).
    """
    traits = person.identity.traits_json
    evenements: list[tuple[str, str]] = []
    contrainte = CONTRAINTE_AUCUNE

    motifs = {
        mode: _vehicle_unavailable_reason(person, mode, from_location)
        for mode in _VEHICLE_MODES
    }
    for mode, motif in motifs.items():
        # Événements de sortie : comptés par mode POSSÉDÉ mais écarté, comme le contrôleur
        # le faisait avant routage (ils ne dépendent pas des propositions présentes).
        if motif is None or not _owns_vehicle(traits, mode):
            continue
        if motif == MOTIF_PAS_DE_CONDUCTEUR:
            evenements.append(("car", "no_driver"))
        else:
            evenements.append((mode, "unavailable"))
            contrainte = CONTRAINTE_SORTIE_BLOQUEE

    eligibles: list[Proposition] = []
    ecartees: list[Ecart] = []
    for prop in propositions:
        vm = prop.mode_vehicule
        motif = motifs.get(vm)
        if motif is not None:
            ecartees.append(Ecart(prop.code, prop.mode, motif))
        else:
            eligibles.append(prop)

    if (
        settings.agent.vehicle_chain_enabled
        and settings.agent.vehicle_return_home_lock
        and eligibles
        and (purpose or "").lower() == "home"
    ):
        a_ramener = _vehicles_parked_at(person, from_location)
        od_km = _road_distance_km(from_location, destination)
        if a_ramener and od_km is not None and od_km < RETURN_LOCK_MIN_DISTANCE_KM:
            evenements.extend((mode, "short_return") for mode in sorted(a_ramener))
            a_ramener = set()
        if a_ramener:
            gardees = [p for p in eligibles if p.mode_vehicule in a_ramener]
            evenements.extend(
                (mode, "forced_return" if gardees else "return_failed")
                for mode in sorted(a_ramener)
            )
            if gardees:
                ecartees.extend(
                    Ecart(p.code, p.mode, MOTIF_RETOUR_FORCE)
                    for p in eligibles
                    if p.mode_vehicule not in a_ramener
                )
                eligibles = gardees
                contrainte = CONTRAINTE_RETOUR_FORCE

    return ResultatFiltre(
        eligibles=eligibles,
        ecartees=ecartees,
        evenements=evenements,
        contrainte=contrainte,
    )


def plafonner(
    eligibles: Sequence[Proposition], max_n: int
) -> tuple[list[Proposition], list[Ecart]]:
    """Plafond d'options (`_select_candidates`), avec les écartées tracées `plafond`.

    L'ordre d'entrée est d'abord rendu canonique (durée, code) pour qu'un ex æquo de durée se
    départage pareil dans les deux modes (RG-5) — `_select_candidates` est stable mais dépend
    sinon de l'ordre rendu par les moteurs.
    """
    canon = sorted(
        eligibles,
        key=lambda p: (
            (p.plan.duration if p.plan.duration is not None else float("inf")),
            p.code,
        ),
    )
    plans = [p.plan for p in canon]
    gardes = _select_candidates(plans, max_n)
    garde_ids = {id(pl) for pl in gardes}
    retenues = [p for p in canon if id(p.plan) in garde_ids]
    ecartees = [
        Ecart(p.code, p.mode, MOTIF_PLAFOND)
        for p in canon
        if id(p.plan) not in garde_ids
    ]
    return retenues, ecartees


def graine_ordre(graine: int, person_id: str, activity_id: str | None) -> int:
    raw = f"{graine}|{person_id}|{activity_id or ''}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def ordre_presentation(
    propositions: Sequence, graine: int, person_id: str, activity_id: str | None
) -> list:
    """D7 — ordre de présentation déterministe : même graine, même déplacement ⇒ même ordre.

    L'entrée est d'abord triée par code pour que le résultat ne dépende pas de l'ordre reçu ;
    accepte des `Proposition` comme des `TravelPlan` nus (le contrôleur passe ses plans).
    """

    def _code(x) -> str:
        plan = x.plan if isinstance(x, Proposition) else x
        return plan.get_code() or plan.id or ""

    items = sorted(propositions, key=_code)
    random.Random(graine_ordre(graine, person_id, activity_id)).shuffle(items)
    return items


@dataclass
class ContexteDecision:
    """Ce que le décideur a le droit de savoir — et rien d'autre (D9, D11)."""

    timestamp: int  # horloge SIMULÉE de la décision
    activity_id: str
    purpose: str
    departure_time: int
    from_location: Location | None
    destination: Location | None
    anticipation: dict | None = None
    evenement: dict | None = None
    periode_evenement: str | None = None  # avant | pendant | apres (spec 04, G9)
    graine_ordre: int = 42
    graine_tirage: int = 42
    max_candidats: int = 6


@dataclass
class ReponseDecideur:
    """Ce qu'un décideur rend pour une liste de propositions PRÉSENTÉES (indexées dans cet ordre)."""

    index: int | None  # None ⇒ réponse inexploitable ou erreur
    fournisseur: str = ""
    distribution: dict = field(default_factory=dict)  # par mode canonique
    poids: list[float] = field(default_factory=list)  # par proposition présentée
    reponse_brute: str | None = None
    raison: str = ""
    souvenirs: list[str] = field(default_factory=list)
    presente: dict | None = None  # ce qui a été montré (payload / textes), pour E11
    repli_uniforme: bool = False  # D10
    erreur: str | None = (
        None  # le décideur n'a PAS répondu (réseau, quota, substitution)
    )
    identifiant_lot: str | None = (
        None  # S5 : identifiant du lot de la passerelle si connu
    )
    non_imputable: bool = (
        False  # R13 : non-décision TERMINALE (pas un repli, pas un retry)
    )
    reprise_a: str | None = (
        None  # quota journalier : instant ISO-UTC de réouverture, annoncé par le fournisseur
    )
    modele_verifie: bool | None = (
        None  # antigravity P1 : False si le modèle est déclaré sans attestation passerelle
    )
    sortie_litterale: str | None = (
        # P8 (spec hygiène §8) — la sortie du modèle TELLE QU'ÉMISE, jamais reformatée ni
        # re-sérialisée. `reponse_brute` a montré sa limite : sur le canal antigravity, ses
        # 2 287 réponses étaient du JSON nu sous deux formes selon le segment, donc une
        # re-sérialisation par l'agent intermédiaire — aucune pièce de l'archive ne montrait
        # ce que le modèle avait réellement écrit. None quand le canal ne peut pas la fournir :
        # mieux vaut un trou déclaré qu'une copie qu'on croirait littérale.
        None
    )


class Decideur(Protocol):
    """Contrat D1 : la même interface pour la passerelle, une heuristique ou un rejeu."""

    nom: str
    sans_quota: bool

    async def choisir(
        self, person: Person, ctx: ContexteDecision, presentees: list[Proposition]
    ) -> ReponseDecideur: ...


@dataclass
class Decision:
    retenue: Proposition | None
    methode: str
    trace: dict
    reponse: ReponseDecideur | None = None
    sollicite: bool = False

    @property
    def est_decision(self) -> bool:
        """Une erreur n'est pas une décision : rien n'est archivé, elle sera redemandée."""
        return self.methode != METHODE_ERREUR


def _prop_dict(p: Proposition) -> dict:
    return {
        "code": p.code,
        "mode": p.mode,
        "source": p.source,
        "duree_s": p.plan.duration,
    }


def construire_trace(
    person: Person,
    ctx: ContexteDecision,
    presentees: Sequence[Proposition],
    ecartees: Sequence[Ecart],
    retenue: Proposition | None,
    methode: str,
    reponse: ReponseDecideur | None,
    contrainte: str,
) -> dict:
    """D6 — les cinq éléments (présentées, écartées, retenue, distribution, réponse brute) + sources."""
    t = {
        "person_id": person.person_id,
        "activity_id": ctx.activity_id,
        "purpose": ctx.purpose,
        "timestamp": ctx.timestamp,
        "departure_time": ctx.departure_time,
        "methode": methode,
        "presentees": [_prop_dict(p) for p in presentees],
        "ecartees": [asdict(e) for e in ecartees],
        "retenue": (
            _prop_dict(retenue)
            | {
                "index_presente": next(
                    (i for i, p in enumerate(presentees) if p.code == retenue.code),
                    None,
                )
            }
        )
        if retenue
        else None,
        "distribution": dict(reponse.distribution) if reponse else {},
        "poids_presentes": list(reponse.poids) if reponse else [],
        "reponse_brute": reponse.reponse_brute if reponse else None,
        "sortie_litterale": reponse.sortie_litterale if reponse else None,
        "sources": {p.code: p.source for p in presentees},
        "fournisseur": reponse.fournisseur if reponse else "",
        "raison": reponse.raison if reponse else "",
        "souvenirs": list(reponse.souvenirs) if reponse else [],
        "presente": reponse.presente if reponse else None,
        "identifiant_lot": reponse.identifiant_lot if reponse else None,
        "graine_ordre": ctx.graine_ordre,
        "graine_tirage": ctx.graine_tirage,
        "contrainte_chaine": contrainte,
        "periode_evenement": ctx.periode_evenement,
        "anticipation": (ctx.anticipation or {}).get("trace", "")
        if ctx.anticipation
        else "",
    }
    if reponse and reponse.modele_verifie is not None:
        t["modele_verifie"] = reponse.modele_verifie
    return t


def resumer_ecartees(ecartees: Sequence) -> str:
    """« vehicule_ailleurs:car;plafond:2 » — pour la colonne « Écartées (motifs) » de moves.csv.

    Accepte des `Ecart` ou des dicts de trace. Les écartées par le plafond sont comptées, les
    autres nommées par mode : c'est ce qui permet de relire pourquoi une option manquait.
    """
    par_motif: dict[str, list[str]] = {}
    for e in ecartees:
        motif = e.motif if isinstance(e, Ecart) else str(e.get("motif"))
        mode = e.mode if isinstance(e, Ecart) else str(e.get("mode"))
        par_motif.setdefault(motif, []).append(mode)
    parts = []
    for motif in sorted(par_motif):
        modes = par_motif[motif]
        parts.append(
            f"{motif}:{len(modes)}"
            if motif == MOTIF_PLAFOND
            else f"{motif}:{','.join(sorted(set(modes)))}"
        )
    return ";".join(parts)


CHAMPS_TRACE_OBLIGATOIRES = (
    "presentees",
    "ecartees",
    "retenue",
    "distribution",
    "reponse_brute",
    "sources",
    "methode",
)


def valider_trace(trace: dict) -> list[str]:
    """Champs D6 absents d'une trace relue — vide si l'archive est valide."""
    return [c for c in CHAMPS_TRACE_OBLIGATOIRES if c not in trace]


async def decider(
    person: Person,
    ctx: ContexteDecision,
    propositions: Sequence[Proposition],
    decideur: Decideur,
) -> Decision:
    """D1/D5/D6/D10 — de la liste brute à la décision tracée. Ne modifie pas la personne (voir `avancer_chaine`)."""
    filtre = eligibilite(
        person, ctx.from_location, propositions, ctx.purpose, ctx.destination
    )
    retenues, ecartees_plafond = plafonner(filtre.eligibles, ctx.max_candidats)
    ecartees = list(filtre.ecartees) + ecartees_plafond
    presentees = ordre_presentation(
        retenues, ctx.graine_ordre, person.person_id, ctx.activity_id
    )

    if not presentees:
        trace = construire_trace(
            person,
            ctx,
            [],
            ecartees,
            None,
            METHODE_SANS_SOLUTION,
            None,
            filtre.contrainte,
        )
        return Decision(retenue=None, methode=METHODE_SANS_SOLUTION, trace=trace)

    if len(presentees) == 1:
        seule = presentees[0]
        trace = construire_trace(
            person,
            ctx,
            presentees,
            ecartees,
            seule,
            METHODE_CHOIX_UNIQUE,
            None,
            filtre.contrainte,
        )
        return Decision(retenue=seule, methode=METHODE_CHOIX_UNIQUE, trace=trace)

    reponse = await decideur.choisir(person, ctx, presentees)
    if reponse.non_imputable:
        # R13 — non-décision TERMINALE : archivée, comptée, exclue des parts (aucune
        # retenue), jamais réessayée (est_decision True) ni fabriquée en repli uniforme.
        trace = construire_trace(
            person,
            ctx,
            presentees,
            ecartees,
            None,
            METHODE_MODELE_NON_IMPUTABLE,
            reponse,
            filtre.contrainte,
        )
        return Decision(
            retenue=None,
            methode=METHODE_MODELE_NON_IMPUTABLE,
            trace=trace,
            reponse=reponse,
            sollicite=True,
        )
    if (
        reponse.erreur is not None
        or reponse.index is None
        or not (0 <= reponse.index < len(presentees))
    ):
        if reponse.erreur is None:
            # Réponse rendue mais inexploitable (index hors bornes non réaligné) : repli D10.
            reponse.repli_uniforme = True
            reponse.index = random.Random(
                graine_ordre(ctx.graine_tirage, person.person_id, ctx.activity_id)
            ).randrange(len(presentees))
        else:
            trace = construire_trace(
                person,
                ctx,
                presentees,
                ecartees,
                None,
                METHODE_ERREUR,
                reponse,
                filtre.contrainte,
            )
            trace["erreur"] = reponse.erreur
            return Decision(
                retenue=None,
                methode=METHODE_ERREUR,
                trace=trace,
                reponse=reponse,
                sollicite=True,
            )

    retenue = presentees[reponse.index]
    methode = METHODE_REPLI_UNIFORME if reponse.repli_uniforme else METHODE_DECIDEUR
    contrainte = filtre.contrainte
    if retenue.mode_vehicule == "car" and _is_car_passenger(person):
        contrainte = CONTRAINTE_PASSAGER
    trace = construire_trace(
        person, ctx, presentees, ecartees, retenue, methode, reponse, contrainte
    )
    return Decision(
        retenue=retenue, methode=methode, trace=trace, reponse=reponse, sollicite=True
    )


def avancer_chaine(
    person: Person,
    plan: TravelPlan | None,
    from_location: Location | None,
    destination: Location | None,
    purpose: str | None,
) -> set[str]:
    """D4 — le véhicule utilisé suit la personne, les autres restent ; orphelins rattrapés au domicile.

    Rend l'ensemble des modes orphelins constatés (vide le plus souvent). Sans effet si la chaîne
    est désactivée. Le contrôleur GAMA garde ses propres métriques autour de ce même appel.
    """
    if not settings.agent.vehicle_chain_enabled or plan is None or destination is None:
        return set()
    _park_vehicles(person, plan, from_location, destination)
    if (purpose or "").lower() != "home":
        return set()
    orphelins = _orphaned_vehicles(person)
    if orphelins and settings.agent.vehicle_orphan_reset_at_home:
        for mode in orphelins:
            person.state.planning_vehicle_at.pop(mode, None)
    return orphelins


__all__ = [
    "CONTRAINTE_AUCUNE",
    "CONTRAINTE_PASSAGER",
    "CONTRAINTE_RETOUR_FORCE",
    "CONTRAINTE_SORTIE_BLOQUEE",
    "METHODE_CHOIX_UNIQUE",
    "METHODE_DECIDEUR",
    "METHODE_ERREUR",
    "METHODE_MODELE_NON_IMPUTABLE",
    "METHODE_REPLI_UNIFORME",
    "METHODE_SANS_SOLUTION",
    "PREFIXE_RECALCUL_HORAIRE",
    "PREFIXE_RECALCUL_OFFRE",
    "PREFIXE_RECALCUL_OFFRE_JOUR",
    "SOURCE_ENREGISTREE",
    "SOURCE_EN_VOL",
    "SOURCE_HORS_JEU",
    "SOURCE_LOCALE",
    "ContexteDecision",
    "Decideur",
    "Decision",
    "Ecart",
    "Proposition",
    "ReponseDecideur",
    "ResultatFiltre",
    "_can_drive",
    "_selection_group",
    "avancer_chaine",
    "construire_trace",
    "decider",
    "eligibilite",
    "graine_ordre",
    "modes_vehicules_eligibles",
    "ordre_presentation",
    "plafonner",
    "resumer_ecartees",
    "valider_trace",
]
