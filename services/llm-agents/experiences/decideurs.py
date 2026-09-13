"""Les décideurs (ticket 035, spec 02 D1/D8, spec 03 S10, spec 05 Q2/Q3/Q12).

Quatre implémentations du même contrat `Decideur.choisir(person, ctx, presentees)` :

- `DecideurPasserelle` : le modèle de langage, via `LlmAgent` (même texte présenté que la
  simulation), **épinglé** à un modèle : seules les instances qui le servent sont sollicitées, une
  réponse servie par une autre instance est refusée (`substitution_refusee`) ;
- `DecideurDureeMinimale` : heuristique déterministe, locale, sans quota ;
- `DecideurAleatoire` : uniforme graîné (plancher `exp_00a` du plan d'expériences) ;
- `DecideurRejeu` : ressert les réponses archivées d'une exécution antérieure — c'est lui qui rend
  l'égalité des modes **vérifiable** sans le bruit d'un modèle (D8, Q6).
"""

from __future__ import annotations

import json
import random
import re

from experiences.decision import (
    ContexteDecision,
    Proposition,
    ReponseDecideur,
    graine_ordre,
)
from experiences.ressources import MoniteurRessources
from loguru import logger
from models import Person
from urban_mobility_agents.candidats import _primary_mode

# `epuise` (bloquant réel, → arrêt/attente de fenêtre) est réservé au quota (429) et au crédit (402)
# CONFIRMÉS. « saturés / indisponibles / timeout » décrit une passerelle OCCUPÉE — transitoire : on
# réessaie, on ne saute jamais (R1/R2). Le « satur » qui vivait dans _RE_QUOTA classait « Providers
# saturés ou indisponibles » en `epuise` à tort (panne du 2026-09-07, rien n'était épuisé).
_RE_QUOTA = re.compile(r"\b(429|quota|rate.?limit)", re.IGNORECASE)
_RE_CREDIT = re.compile(r"\b(402|credit|crédit|insufficient)", re.IGNORECASE)
_RE_OCCUPEE = re.compile(
    r"(satur|indisponible|timeout|occup|unavailable|\b50[234]\b)", re.IGNORECASE
)


def _distribution(poids: list[float], presentees: list[Proposition]) -> dict:
    from mobility_llm.mode_choice import mode_distribution

    return mode_distribution(poids, [p.mode for p in presentees])


def _presente_local(presentees: list[Proposition]) -> dict:
    return {
        "options": [
            {"index": i, "mode": p.mode, "duree_s": p.plan.duration, "source": p.source}
            for i, p in enumerate(presentees)
        ]
    }


class DecideurDureeMinimale:
    nom = "duree_minimale"
    sans_quota = True

    async def choisir(
        self, person: Person, ctx: ContexteDecision, presentees: list[Proposition]
    ) -> ReponseDecideur:
        idx = min(
            range(len(presentees)),
            key=lambda i: (
                (
                    presentees[i].plan.duration
                    if presentees[i].plan.duration is not None
                    else float("inf")
                ),
                presentees[i].code,
            ),
        )
        poids = [1.0 if i == idx else 0.0 for i in range(len(presentees))]
        return ReponseDecideur(
            index=idx,
            fournisseur=self.nom,
            distribution=_distribution(poids, presentees),
            poids=poids,
            reponse_brute=json.dumps({"regle": self.nom, "index": idx}),
            raison="durée minimale",
            presente=_presente_local(presentees),
        )


class DecideurAleatoire:
    sans_quota = True

    def __init__(self, graine: int):
        self.graine = int(graine)
        self.nom = f"aleatoire:{self.graine}"

    async def choisir(
        self, person: Person, ctx: ContexteDecision, presentees: list[Proposition]
    ) -> ReponseDecideur:
        n = len(presentees)
        idx = random.Random(
            graine_ordre(self.graine, person.person_id, ctx.activity_id)
        ).randrange(n)
        poids = [1.0 / n] * n
        return ReponseDecideur(
            index=idx,
            fournisseur=self.nom,
            distribution=_distribution(poids, presentees),
            poids=poids,
            reponse_brute=json.dumps(
                {"regle": "uniforme", "graine": self.graine, "index": idx}
            ),
            raison="tirage uniforme",
            presente=_presente_local(presentees),
        )


class DecideurMajoritaireVoiture:
    """Plancher empirique `exp_00b` : la voiture si elle est offerte, sinon repli neutre.

    « A priori empirique » du plan (`docs/paper/methode/experience_plan`) : reproduit le prior trivial
    « tout le monde conduit ». On retient l'option dont le **mode principal** est la voiture, au
    sens de l'enquête (`_primary_mode`, hiérarchie EMC²) — et **non** au sens de la chaîne
    (`_vehicle_mode`) : un rabattement voiture + train est un déplacement collectif, ce n'est pas
    « prendre la voiture ». Entre plusieurs options voiture, la plus rapide (départage stable par
    `code`, comme la durée minimale). Sans aucune option voiture, repli déterministe sur la
    première option présentée — l'ordre D7 est déjà graîné, donc ce repli n'introduit aucun
    tirage. Local, déterministe, sans quota (S10/Q12).

    `decision.decider` garantit `len(presentees) >= 2` (0 → sans solution, 1 → choix unique, sans
    solliciter) : l'index 0 de repli existe toujours.
    """

    nom = "majoritaire_voiture"
    sans_quota = True

    async def choisir(
        self, person: Person, ctx: ContexteDecision, presentees: list[Proposition]
    ) -> ReponseDecideur:
        voitures = [
            i for i, p in enumerate(presentees) if _primary_mode(p.plan) == "car"
        ]
        if voitures:
            idx = min(
                voitures,
                key=lambda i: (
                    (
                        presentees[i].plan.duration
                        if presentees[i].plan.duration is not None
                        else float("inf")
                    ),
                    presentees[i].code,
                ),
            )
            raison = "voiture disponible (mode principal)"
        else:
            idx = 0
            raison = "aucune option voiture — repli sur la première présentée"
        poids = [1.0 if i == idx else 0.0 for i in range(len(presentees))]
        return ReponseDecideur(
            index=idx,
            fournisseur=self.nom,
            distribution=_distribution(poids, presentees),
            poids=poids,
            reponse_brute=json.dumps({"regle": self.nom, "index": idx}),
            raison=raison,
            presente=_presente_local(presentees),
        )


class DecideurRejeu:
    sans_quota = True

    def __init__(self, execution, nom_source: str | None = None):
        self.execution = execution
        self.nom = f"rejeu:{nom_source or getattr(execution, 'nom', '?')}"

    async def choisir(
        self, person: Person, ctx: ContexteDecision, presentees: list[Proposition]
    ) -> ReponseDecideur:
        trace = self.execution.decision(person.person_id, ctx.activity_id)
        if trace is None or not trace.get("retenue"):
            return ReponseDecideur(
                index=None,
                fournisseur=self.nom,
                erreur="rejeu : aucune décision archivée pour ce déplacement",
            )
        code = trace["retenue"].get("code")
        idx = next((i for i, p in enumerate(presentees) if p.code == code), None)
        if idx is None:
            return ReponseDecideur(
                index=None,
                fournisseur=self.nom,
                erreur=f"rejeu : la proposition archivée {code!r} n'est pas parmi les présentées",
            )
        poids = list(trace.get("poids_presentes") or [])
        if len(poids) != len(presentees):
            poids = [1.0 if i == idx else 0.0 for i in range(len(presentees))]
        return ReponseDecideur(
            index=idx,
            fournisseur=self.nom,
            distribution=dict(trace.get("distribution") or {}),
            poids=poids,
            reponse_brute=trace.get("reponse_brute"),
            raison=trace.get("raison") or "rejeu",
            souvenirs=list(trace.get("souvenirs") or []),
            presente=trace.get("presente"),
            repli_uniforme=trace.get("methode") == "repli_uniforme",
        )


# Le RANG d'une clé, jamais son nom : le journal est lu, copié et transmis, et le nom d'une
# instance désigne un compte. « Passage sur la seconde clé » dit tout ce qu'il faut pour agir.
_RANGS = (
    "première",
    "seconde",
    "troisième",
    "quatrième",
    "cinquième",
    "sixième",
    "septième",
    "huitième",
    "neuvième",
    "dixième",
)


def rang_en_mots(rang: int) -> str:
    """1 → « première », 2 → « seconde »… au-delà de dix, « clé n° 11 »."""
    return _RANGS[rang - 1] if 1 <= rang <= len(_RANGS) else f"n° {rang}"


class DecideurPasserelle:
    """Le modèle de langage distant, épinglé (Q2), sans substitution (Q3)."""

    sans_quota = False

    def __init__(
        self,
        agent,
        modele: str,
        instances: list[str],
        moniteur: MoniteurRessources | None = None,
    ):
        self.agent = agent
        self.modele = modele
        self.instances = list(instances)
        self.moniteur = moniteur
        self.nom = f"passerelle:{modele}"
        self._curseur = (
            0  # conservé : plus utilisé par la sélection, sérielle depuis 2026-09-07
        )
        self._derniere_instance: str | None = None
        self.derniere_erreur_quota: str | None = None

    def _prochaine_instance(self, besoin: int = 1) -> str | None:
        candidates = (
            self.moniteur.instances_disponibles(besoin)
            if self.moniteur is not None
            else list(self.instances)
        )
        if not candidates:
            return None
        # SÉRIE, pas rotation (décision du 2026-09-07). `instances_disponibles` ne garde que
        # celles dont le quota du JOUR n'est pas épuisé : prendre toujours la première les
        # consomme l'une après l'autre, au lieu d'entamer deux seaux de 500 requêtes en
        # parallèle. La saturation par minute, elle, est absorbée en aval (attente).
        inst = candidates[0]
        if inst != self._derniere_instance:
            if self._derniere_instance is not None:
                # Le rang dans l'ordre déclaré du modèle, pas le nom de l'instance.
                rang = (
                    self.instances.index(inst) + 1
                    if inst in self.instances
                    else len(self.instances)
                )
                logger.warning(
                    f"[decideur] Passage sur la {rang_en_mots(rang)} clé "
                    f"({rang}/{len(self.instances)}) — la précédente a épuisé son quota du jour ; "
                    f"{len(candidates)} clé(s) encore disponible(s)"
                )
            self._derniere_instance = inst
        return inst

    async def choisir(
        self, person: Person, ctx: ContexteDecision, presentees: list[Proposition]
    ) -> ReponseDecideur:
        from urban_mobility_agents.agents.llm_agent import Context

        instance = self._prochaine_instance()
        if instance is None:
            raison = (
                self.moniteur.raison_epuisement()
                if self.moniteur
                else "aucune instance"
            )
            return ReponseDecideur(
                index=None, fournisseur="", erreur=f"epuise: {raison}"
            )
        options = [p.plan for p in presentees]
        for o in options:
            o.purpose = ctx.purpose
        context = Context(
            person=person,
            timestamp=int(ctx.timestamp),
            activity_id=ctx.activity_id,
            data={"type": "travel_plan"},
        )
        trace: dict = {}
        (
            idx,
            raison,
            fournisseur,
            distribution,
        ) = await self.agent.evaluate_and_choose_travel_plan(
            context=context,
            options=options,
            destination=ctx.purpose,
            departure_time=int(ctx.departure_time),
            anticipation=ctx.anticipation,
            force_provider=instance,
            allowed_providers=set(self.instances),
            trace=trace,
            presentation_figee=True,
        )
        if "substitution_refusee" in trace:
            if self.moniteur is not None:
                self.moniteur.compteurs["substitution_refusee"] += 1
            return ReponseDecideur(
                index=None,
                fournisseur=fournisseur,
                erreur=f"substitution_refusee:{fournisseur}",
                presente={"payload": trace.get("payload")},
                reponse_brute=trace.get("reponse_brute"),
            )
        if not isinstance(idx, int) or idx < 0:
            erreur = str(trace.get("erreur") or raison or "réponse inexploitable")
            reprise_a = trace.get("reprise_a")
            if trace.get("genre_erreur") == "quota_journalier":
                # Le fournisseur l'a QUALIFIÉ lui-même (429 « per day ») : on ne devine plus
                # d'après le texte. Canal ajouté le 2026-09-08 — le message reformulé par le
                # worker (« Providers saturés ou indisponibles ») tombait dans _RE_OCCUPEE et
                # l'exécution attendait indéfiniment une clé fermée pour 7 h. Les regex
                # restent le repli pour un fournisseur qui ne renseigne pas le champ, et la
                # frontière `satur` → occupée (décision du 2026-09-07) n'est pas touchée.
                if self.moniteur is not None:
                    self.moniteur.compteurs["429"] += 1
                self.derniere_erreur_quota = erreur
                erreur = "epuise: " + erreur
            elif _RE_CREDIT.search(erreur) or _RE_QUOTA.search(erreur):
                # Quota (429) ou crédit (402) CONFIRMÉ : bloquant réel → `epuise` (R2).
                if self.moniteur is not None:
                    self.moniteur.compteurs[
                        "402" if _RE_CREDIT.search(erreur) else "429"
                    ] += 1
                self.derniere_erreur_quota = erreur
                erreur = "epuise: " + erreur
            elif _RE_OCCUPEE.search(erreur):
                # Passerelle occupée / indisponible / timeout : TRANSITOIRE, jamais `epuise` (R2).
                erreur = "passerelle_occupee: " + erreur
            return ReponseDecideur(
                index=None,
                fournisseur=fournisseur,
                erreur=erreur,
                presente={"payload": trace.get("payload")},
                reponse_brute=trace.get("reponse_brute"),
                reprise_a=(
                    reprise_a.isoformat() if hasattr(reprise_a, "isoformat") else reprise_a
                ),
            )
        return ReponseDecideur(
            index=idx,
            fournisseur=fournisseur,
            distribution=dict(distribution or {}),
            poids=list(trace.get("poids_presentes") or []),
            reponse_brute=trace.get("reponse_brute"),
            raison=raison or "",
            souvenirs=list(trace.get("souvenirs") or []),
            presente={"payload": trace.get("payload")},
            repli_uniforme=bool(trace.get("repli_uniforme")),
            identifiant_lot=trace.get("identifiant_lot"),
        )


def construire_decideur(
    spec,
    *,
    agent=None,
    moniteur: MoniteurRessources | None = None,
    instances: list[str] | None = None,
    execution_rejeu=None,
    dossier_echanges=None,
    attente_max_s: int = 120,
    execution=None,
):
    """Fabrique depuis `DecideurSpec` (experience.py)."""
    if spec.type == "duree_minimale":
        return DecideurDureeMinimale()
    if spec.type == "aleatoire":
        return DecideurAleatoire(spec.graine)
    if spec.type == "majoritaire_voiture":
        return DecideurMajoritaireVoiture()
    if spec.type == "rejeu":
        if execution_rejeu is None:
            from experiences.archive import Execution

            execution_rejeu = Execution.ouvrir(spec.rejeu_de)
        return DecideurRejeu(execution_rejeu, spec.rejeu_de)
    if spec.type == "passerelle":
        if agent is None:
            raise ValueError("un décideur passerelle exige un LlmAgent")
        return DecideurPasserelle(agent, spec.modele, instances or [], moniteur)
    if spec.type == "antigravity":
        from experiences.decideur_antigravity import DecideurAntigravity

        if agent is None:
            raise ValueError(
                "un décideur antigravity exige un LlmAgent (construction du payload)"
            )
        return DecideurAntigravity(
            agent=agent,
            modele=spec.modele,
            echanges=dossier_echanges,
            attente_max_s=attente_max_s,
            parametres=spec.parametres,
            execution=execution,
        )
    if spec.type == "modele":
        # Import tardif : LightGBM / geopandas ne sont chargés que si on décide par modèle.
        from experiences.decideur_modele import DecideurModele

        return DecideurModele(artefact=getattr(spec, "artefact", None))
    raise ValueError(f"type de décideur inconnu : {spec.type!r}")


def __getattr__(name: str):
    if name == "DecideurAntigravity":
        from experiences.decideur_antigravity import DecideurAntigravity

        return DecideurAntigravity
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DecideurAleatoire",
    "DecideurAntigravity",
    "DecideurDureeMinimale",
    "DecideurMajoritaireVoiture",
    "DecideurPasserelle",
    "DecideurRejeu",
    "construire_decideur",
]
