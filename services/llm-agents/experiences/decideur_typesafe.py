"""Décideur « Jev » (TypeSafe) — ticket 096, lot 1, contrat `specs/ticket_096/tests.md`.

Un décideur de plus au contrat commun `Decideur.choisir(person, ctx, presentees)`, mais d'une
troisième famille : ni modèle de langage génératif, ni modèle tabulaire entraîné sur l'enquête.
Jev est un **classifieur zéro-shot à sortie typée** — on lui envoie un `state` et une question
`Choice`, il rend la distribution complète sur les options et une confiance, sans produire une
ligne de texte.

**Rien de la présentation n'est réécrit.** Le texte servi sort de
`LlmAgent.build_travel_plan_payload`, celui-là même qui sert les bras LLM : une seconde
implémentation du bloc persona ferait diverger les deux bras en silence, et c'est exactement ce
que « à texte présenté égal » interdit. Ce qui change, c'est la FORME de la demande : les
options quittent le texte pour `criteria`, et la consigne perd son bloc `[Output instructions]`
puisque le type `Choice` le remplace.

Trois choses que ce décideur ne fait PAS, et ce sont des décisions :

- il ne **rédige pas** de `raison`. Jev n'en produit pas ; une justification synthétisée à
  partir des probabilités se lirait comme une sortie de modèle dans les traces et les rapports
  mémoire ;
- il n'**arrondit pas** le problème de l'arrondi. Jev rend ses probabilités à deux décimales, et
  une somme à 0,99 ou 1,01 est donc normale (mesuré au lot 0 : dix cas sur 850, tous à ±0,01
  exactement). La tolérance est déclarée, les poids sont renormalisés, et au-delà c'est une
  non-décision ;
- il ne **replie jamais en silence**. Un échec de transport est une erreur (le runner réessaie) ;
  une réponse rendue mais inexploitable est une non-décision explicite (archivée, comptée,
  exclue des parts). Les deux cas sont distincts et ne doivent pas se confondre : l'un se
  réessaie indéfiniment, l'autre jamais.
"""

from __future__ import annotations

import hashlib
import json
import random
import re

from experiences.decision import (
    ContexteDecision,
    Proposition,
    ReponseDecideur,
    graine_ordre,
)
from loguru import logger
from models import Person

# Version épinglée, jamais un alias : `jev-latest` rendrait l'empreinte mensongère au premier
# changement de version, EN SILENCE. La spec refuse l'alias plutôt que de le résoudre au
# lancement — un alias résolu scelle une version que l'`experience.yaml` ne porte pas.
RE_VERSION_FIGEE = re.compile(r"^jev-\d+\.\d+\.\d+$")

# Le marqueur qui sépare, dans une variante de `prompts.yaml`, l'arbitrage (qu'on envoie) de la
# consigne de sortie (que le type `Choice` remplace : schéma JSON, somme à 100, « no markdown »).
MARQUEUR_SORTIE = "[Output instructions]"

# Jev rend ses probabilités arrondies à 2 décimales : avec 6 options, la somme peut valoir 0,99
# ou 1,01. Mesuré au lot 0 sur 850 appels — dix écarts, tous exactement ±0,01, jamais autre
# chose. La tolérance couvre l'arrondi et rien de plus : une somme à 0,80 est une réponse
# inexploitable, pas un arrondi.
TOLERANCE_SOMME = 0.02


def instructions_servies(texte: str) -> str:
    """Le texte d'une variante amputé de son bloc de sortie — ce qui part réellement en
    `instructions`. Fonction séparée parce que l'empreinte en a besoin sans le décideur."""
    coupe = texte.find(MARQUEUR_SORTIE)
    return (texte[:coupe] if coupe > 0 else texte).strip()


def sha_instructions(categorie: str, variante: str | None) -> str | None:
    """sha256 du texte RÉELLEMENT envoyé à Jev (R6 du ticket 045, appliqué à ce bras).

    L'empreinte de gabarit hache la variante ENTIÈRE ; ce qu'on envoie en est une dérivée. Si
    la règle d'amputation changeait, l'empreinte de gabarit ne bougerait pas et deux exécutions
    incomparables porteraient la même signature. Ce sha-là bouge.
    """
    try:
        from mobility_llm import prompt_manager as get_prompt_manager

        texte = (
            get_prompt_manager().get_system_prompt(
                categorie, variante, verifier_validite=False
            )
            or ""
        )
    except Exception as e:  # noqa: BLE001 — l'empreinte le DIT plutôt que de disparaître
        logger.warning(
            f"[decideur] prompt système indisponible pour l'empreinte typesafe "
            f"(catégorie {categorie!r}, variante {variante!r}) : {e}"
        )
        return None
    return hashlib.sha256(instructions_servies(texte).encode("utf-8")).hexdigest()


def _etat(agent_bloc: dict) -> str:
    """Le bloc persona du payload, SANS les options (elles vont dans `criteria`).

    Les champs et leur ordre suivent `itinary_multi_agent/template.md.j2`. Les options en sont
    retirées parce qu'un `Choice` les porte déjà : les laisser dans le `state` les présenterait
    deux fois, et la documentation de Jev annonce une chute d'exactitude quand le `state`
    grossit de contenu qui ne sert pas la décision.
    """
    lignes = [str(agent_bloc.get("perception") or "")]
    dest = agent_bloc.get("destination") or ""
    zone = agent_bloc.get("destination_zone")
    lignes.append(f"Destination: {dest}{f' ({zone})' if zone else ''}")
    if agent_bloc.get("departure_time"):
        lignes.append(f"Departure: {agent_bloc['departure_time']}")
    if agent_bloc.get("context") and agent_bloc["context"] != "None":
        lignes.append(f"Context: {agent_bloc['context']}")
    if agent_bloc.get("day_outlook"):
        lignes.append(f"Weather later: {agent_bloc['day_outlook']}")
    if agent_bloc.get("agenda"):
        lignes.append("Further trips planned today:")
        lignes += [f"  - {l}" for l in agent_bloc["agenda"]]
    if agent_bloc.get("history"):
        lignes.append("History:")
        lignes += [f"  - {h}" for h in agent_bloc["history"]]
    return "\n".join(lignes)


def cle_option(index: int) -> str:
    """`option_<rang de présentation>`. Indexée et NON nommée par le mode : deux itinéraires
    partagent souvent le même mode (deux variantes bus, deux variantes à pied), et un
    dictionnaire à clé de mode en écraserait une."""
    return f"option_{index}"


def _criteres(trajectories: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for i, t in enumerate(trajectories):
        desc = str(t.get("description") or "").replace("\n- ", " · ").replace("\n", " ")
        out[cle_option(i)] = f"Mode {t.get('mode') or 'unknown'}. {desc}".strip()
    return out


class DecideurTypesafe:
    """Jev comme décideur. Sans quota, sans clé réservée, sans génération de texte."""

    # Ni clé API à réserver ni fenêtre journalière : 1 200 req/min annoncés pour 2 482
    # sollicitations. L'ordonnanceur n'a donc rien à arbitrer (E5).
    sans_quota = True

    def __init__(
        self,
        agent,
        modele: str,
        variante: str | None = None,
        categorie: str = "itinary_multi_agent",
        client=None,
    ):
        if not RE_VERSION_FIGEE.match(str(modele or "")):
            raise ValueError(
                f"décideur typesafe : {modele!r} n'est pas une version figée. "
                "Attendu `jev-<majeur>.<mineur>.<correctif>` (ex. `jev-1.13.0`) ; les alias "
                "`jev-latest` et `jev-preview` sont refusés, ils rendraient l'empreinte "
                "mensongère au premier changement de version."
            )
        self.agent = agent
        self.modele = str(modele)
        self.variante = variante
        self.categorie = categorie
        self.nom = f"typesafe:{self.modele}"
        self._client = client
        self._instructions: str | None = None

    # ── ressources ──────────────────────────────────────────────────────────
    def client(self):
        """Client TypeSafe **asynchrone**, construit à la première décision.

        Asynchrone et pas synchrone, et c'est tout sauf un détail : le runner avance
        `regroupement.parallelisme` personnes de front derrière un `asyncio.Semaphore`. Un appel
        HTTP BLOQUANT dans un `async def` bloque la boucle entière — les huit places du sémaphore
        ne servent plus à rien et tout se sérialise sur le réseau. Mesuré le 2026-09-21 : 40
        décisions/minute avec le client synchrone, là où Jev répond en 300 ms. Le résultat était
        identique, seul le temps changeait ; c'est exactement le genre de défaut qu'aucun test de
        contrat n'attrape et qu'on paie en heures.

        Import tardif : le SDK n'est chargé que si on décide par Jev. La clé suit la convention
        du dépôt (`PROVIDER_KEYS__<instance>`) et est passée EXPLICITEMENT — laisser le SDK
        résoudre son propre `TYPESAFE_API_KEY` ferait servir une clé traînant dans
        l'environnement à l'insu de l'empreinte.
        """
        if self._client is None:
            import os

            from typesafe_sdk import AsyncTypeSafeClient

            cle = os.environ.get("PROVIDER_KEYS__typesafeAI")
            if not cle:
                raise RuntimeError(
                    "décideur typesafe : PROVIDER_KEYS__typesafeAI absent de l'environnement "
                    "— l'exécution ne démarre pas plutôt que de décider sans modèle."
                )
            self._client = AsyncTypeSafeClient(api_key=cle)
        return self._client

    def instructions(self) -> str:
        if self._instructions is None:
            from mobility_llm import prompt_manager as get_prompt_manager

            texte = (
                get_prompt_manager().get_system_prompt(
                    self.categorie, self.variante, verifier_validite=False
                )
                or ""
            )
            self._instructions = instructions_servies(texte)
            logger.info(
                f"[decideur] Jev {self.modele} — consigne « {self.variante or 'active'} », "
                f"{len(self._instructions)} caractères servis en `instructions` "
                f"(bloc de sortie retiré : le type Choice le remplace)"
            )
        return self._instructions

    def empreinte(self) -> dict:
        return {
            "type": "typesafe",
            "modele": self.modele,
            "variante": self.variante,
            "instructions_sha256": sha_instructions(self.categorie, self.variante),
        }

    # ── décision ────────────────────────────────────────────────────────────
    async def choisir(
        self, person: Person, ctx: ContexteDecision, presentees: list[Proposition]
    ) -> ReponseDecideur:
        from experiences.decideurs import _distribution, _presente_local
        from urban_mobility_agents.agents.llm_agent import Context

        options = [p.plan for p in presentees]
        for o in options:
            o.purpose = ctx.purpose
        contexte = Context(
            person=person,
            timestamp=int(ctx.timestamp),
            activity_id=ctx.activity_id,
            data={"type": "travel_plan"},
        )
        # Le MÊME constructeur de payload que les bras LLM (T1) : la présentation ne se
        # réimplémente pas, sinon les deux bras dérivent sans que rien ne le signale.
        payload = await self.agent.build_travel_plan_payload(
            context=contexte,
            options=options,
            destination=ctx.purpose,
            departure_time=int(ctx.departure_time),
            anticipation=ctx.anticipation,
        )
        bloc = (payload.get("agents") or [{}])[0]
        etat = _etat(bloc)
        criteres = _criteres(bloc.get("trajectories") or [])

        from typesafe_sdk import Choice

        try:
            reponse = await self.client().system_one(
                model=self.modele,
                state=etat,
                questions={"mode": Choice(instructions=self.instructions(), criteria=criteres)},
            )
        except Exception as e:  # noqa: BLE001 — la nature de l'échec décide de la suite
            return self._echec_transport(e, presentees)

        rep = reponse.answers["mode"]
        proba = dict(rep.probabilities or {})
        attendues = list(criteres)

        # R4 — une clé manquante n'est pas rattrapable : on ne sait pas ce que Jev aurait mis.
        manquantes = [c for c in attendues if c not in proba]
        if manquantes:
            return self._non_imputable(
                f"cles_manquantes:{','.join(manquantes[:3])}", presentees
            )

        poids = [float(proba[c]) for c in attendues]
        total = sum(poids)
        # R2/R3 — l'arrondi à deux décimales est admis et renormalisé ; au-delà, ce n'est plus
        # un arrondi et on ne devine pas ce que le modèle voulait dire.
        if abs(total - 1.0) > TOLERANCE_SOMME:
            return self._non_imputable(f"somme_hors_tolerance:{total:.4f}", presentees)
        if total <= 0:
            return self._non_imputable("poids_nuls", presentees)
        poids = [w / total for w in poids]

        idx = _tirer(
            poids, graine_ordre(ctx.graine_tirage, person.person_id, ctx.activity_id)
        )
        return ReponseDecideur(
            index=idx,
            fournisseur=self.nom,
            distribution=_distribution(poids, presentees),
            poids=poids,
            # R8 — la réponse ENTIÈRE est archivée : c'est ce qui permet à `DecideurRejeu` de
            # conserver le bras si le service disparaît (§ 6.2 du ticket).
            reponse_brute=json.dumps(
                {
                    "modele": reponse.model,
                    "choice": rep.choice,
                    "probabilities": proba,
                    "confidence": rep.confidence,
                    "input_tokens": getattr(reponse.usage, "input_tokens", None),
                },
                ensure_ascii=False,
            ),
            # R7 — VIDE. Jev ne rédige pas, et une phrase fabriquée à partir des probabilités
            # se lirait comme une sortie de modèle.
            raison="",
            presente=_presente_local(presentees),
        )

    # ── échecs ──────────────────────────────────────────────────────────────
    def _echec_transport(self, e: Exception, presentees: list[Proposition]) -> ReponseDecideur:
        """E1/E2/E3 — un échec de transport est une ERREUR (réessayée), jamais une non-décision.

        Les deux préfixes existent déjà dans le runner : `passerelle_occupee` attend et
        retente, `configuration` (ticket 085) dit qu'il y a une ligne de configuration à
        corriger et non un quota à attendre. Aucun genre d'erreur n'est ajouté ici.
        """
        nom = type(e).__name__
        if nom in ("TypeSafeAuthenticationError", "TypeSafePermissionDeniedError",
                   "TypeSafeNotFoundError", "TypeSafeUnprocessableEntityError",
                   "TypeSafeBadRequestError"):
            prefixe = "configuration"
        else:
            # Débit, surcharge, timeout, coupure réseau : TRANSITOIRE. Jamais `epuise` —
            # ce bras n'a pas de fenêtre de quota journalier à attendre.
            prefixe = "passerelle_occupee"
        logger.debug(f"[decideur] Jev {prefixe} — {nom}: {e}")
        return ReponseDecideur(
            index=None,
            fournisseur=self.nom,
            erreur=f"{prefixe}: {nom}: {e}",
            presente=self._presente(presentees),
        )

    def _non_imputable(self, raison: str, presentees: list[Proposition]) -> ReponseDecideur:
        """E4 — réponse rendue mais inexploitable : non-décision TERMINALE, jamais réessayée."""
        logger.warning(f"[decideur] Jev non imputable ({raison}) — non-décision")
        return ReponseDecideur(
            index=None,
            fournisseur=self.nom,
            non_imputable=True,
            raison=f"typesafe_non_imputable:{raison}",
            presente=self._presente(presentees),
        )

    @staticmethod
    def _presente(presentees: list[Proposition]) -> dict:
        # Import tardif, comme dans `decideur_modele` : `decideurs` importe ce module.
        from experiences.decideurs import _presente_local

        return _presente_local(presentees)


def _tirer(poids: list[float], graine: int) -> int:
    """Tire un index proportionnellement aux poids. IDENTIQUE à `DecideurModele._tirer` :
    même graine, même tirage — c'est ce qui rend deux décideurs comparables déplacement par
    déplacement (R6)."""
    r = random.Random(graine).random() * sum(poids)
    cumul = 0.0
    for i, w in enumerate(poids):
        cumul += w
        if r <= cumul:
            return i
    return len(poids) - 1


__all__ = [
    "DecideurTypesafe",
    "cle_option",
    "instructions_servies",
    "sha_instructions",
    "RE_VERSION_FIGEE",
    "TOLERANCE_SOMME",
]
