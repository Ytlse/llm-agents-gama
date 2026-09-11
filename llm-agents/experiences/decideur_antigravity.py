"""Décideur Antigravity (ticket 035, spec decideur-antigravity v2).

Délègue chaque décision de déplacement à un sous-agent Antigravity via IPC sur fichiers,
sans consommer de quota d'API et sans dégrader les garanties du ticket 035.

Le modèle servi par Antigravity est déclaré mais non vérifié (P1/P2) :
`modele_verifie: false` est inscrit dans l'empreinte décideur et dans chaque trace.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger
from models import Person

from experiences.archive import ETAT_EN_ATTENTE_AGENT, ETAT_EN_COURS
from experiences.decision import ContexteDecision, Proposition, ReponseDecideur
from mobility_llm import CATEGORIES, prompt_manager
from mobility_llm.mode_choice import (
    UniformFallback,
    draw_index,
    mode_distribution,
    normalize_option_probabilities,
)
from urban_mobility_agents.agents.llm_agent import Context, _format_distribution


class DecideurAntigravity:
    """Décideur déléguant le choix modal à un sous-agent Antigravity via IPC sur disque."""

    sans_quota = True  # runner.py:218 et 973 neutralisent le bloc quota
    modele_verifie = False  # P1 : modèle déclaré, invérifiable via le runtime IDE

    def __init__(
        self,
        agent,
        modele: str,
        echanges: Path | str | None = None,
        attente_max_s: int = 120,
        parametres: dict | None = None,
        execution=None,
    ) -> None:
        self.agent = agent
        self.modele = str(modele)
        self.nom = f"antigravity:{self.modele}"
        self.attente_max_s = int(attente_max_s)
        self.parametres = dict(parametres or {})
        self.execution = execution

        if echanges is None:
            if execution is not None:
                echanges = execution.dossier / "echanges"
            else:
                echanges = Path("data/echanges_antigravity")
        self.echanges = Path(echanges)
        self.dossier_demandes = self.echanges / "demandes"
        self.dossier_demandes_traitees = self.dossier_demandes / "traitees"
        self.dossier_reponses = self.echanges / "reponses"

        self.dossier_demandes_traitees.mkdir(parents=True, exist_ok=True)
        self.dossier_reponses.mkdir(parents=True, exist_ok=True)

        self.compteurs: Counter = Counter()
        self._demandes_en_cours: dict[str, float] = {}
        self._dernier_log_status: float = time.time()
        self._alarme_timeout_levee: bool = False
        self._alarme_rejet_levee: bool = False
        self._alarme_litterale_levee: bool = False
        self._debut: float = time.time()

        # Cache du schéma de sortie de la catégorie
        cat = CATEGORIES["itinary_multi_agent"]
        self._schema_sortie: dict[str, Any] = json.loads(
            cat.schema_path.read_text(encoding="utf-8")
        )

        logger.info(
            f"[antigravity] Initialisation — modèle attendu: {self.modele}, "
            f"échanges: {self.echanges}, attente max: {self.attente_max_s}s"
        )

    def _verifier_journal_et_alarmes(self, now: float) -> None:
        """Toutes les 30s : statut et alarmes sur front montant (§4.7)."""
        if now - self._dernier_log_status >= 30.0:
            age_max = (
                max(now - t for t in self._demandes_en_cours.values())
                if self._demandes_en_cours
                else 0.0
            )
            logger.info(
                f"[antigravity] Statut — en attente: {len(self._demandes_en_cours)}, "
                f"âge max: {age_max:.1f}s, servies: {self.compteurs['servies']}, "
                f"replis: {self.compteurs['replis']}, rejets: {self.compteurs['rejets']}, "
                f"sans sortie littérale: {self.compteurs['sans_sortie_litterale']}"
            )
            self._dernier_log_status = now

            if age_max >= self.attente_max_s and not self._alarme_timeout_levee:
                logger.error(
                    f"[ALARME] [antigravity] Aucune réponse reçue pour une demande depuis "
                    f"plus de {self.attente_max_s}s (âge: {age_max:.1f}s)"
                )
                self._alarme_timeout_levee = True

            total_traite = (
                self.compteurs["servies"]
                + self.compteurs["rejets"]
                + self.compteurs["timeouts"]
            )
            if total_traite >= 20 and not self._alarme_rejet_levee:
                taux_rejets = self.compteurs["rejets"] / total_traite
                if taux_rejets > 0.01:
                    logger.error(
                        f"[ALARME] [antigravity] Taux de rejets élevé "
                        f"({self.compteurs['rejets']}/{total_traite} = {taux_rejets:.1%}) — "
                        "vérifier le câblage de l'agent Antigravity"
                    )
                    self._alarme_rejet_levee = True

    async def choisir(
        self, person: Person, ctx: ContexteDecision, presentees: list[Proposition]
    ) -> ReponseDecideur:
        """Contrat D1 : construit le prompt exact, l'écrit pour l'agent, et attend sa réponse."""
        options = [p.plan for p in presentees]
        for o in options:
            o.purpose = ctx.purpose

        context = Context(
            person=person,
            timestamp=int(ctx.timestamp),
            activity_id=ctx.activity_id,
            data={"type": "travel_plan"},
        )

        # 1. Construction du payload en processus (pur constructeur)
        payload = await self.agent.build_travel_plan_payload(
            context,
            options,
            ctx.purpose,
            int(ctx.departure_time),
            ctx.anticipation,
        )

        # 2. Rendu exact PromptEngine en processus (sans réseau, sans passerelle)
        cat = CATEGORIES["itinary_multi_agent"]
        items = [cat.item_model(**a) for a in payload["agents"]]
        messages = prompt_manager().render(
            "itinary_multi_agent", items, payload["parameters"]
        )

        messages_dict = [{"role": m.role, "content": m.content} for m in messages]
        presente = {"payload": payload, "messages": messages_dict}

        # 3. Écriture atomique de la demande IPC
        cle = f"{person.person_id}__{ctx.activity_id}"
        demande_fichier = f"{cle}.json"
        demande_path = self.dossier_demandes / demande_fichier
        demande_tmp = self.dossier_demandes / f"{cle}.json.tmp"
        reponse_path = self.dossier_reponses / demande_fichier

        demande_corps = {
            "version": 1,
            "person_id": str(person.person_id),
            "activity_id": str(ctx.activity_id),
            "modele_attendu": self.modele,
            "n_options": len(presentees),
            "messages": messages_dict,
            "schema_sortie": self._schema_sortie,
        }

        # Nettoyer une éventuelle réponse orpheline antérieure
        reponse_path.unlink(missing_ok=True)

        demande_tmp.write_text(
            json.dumps(demande_corps, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(demande_tmp, demande_path)

        # 4. Attente active de la réponse (polling non-bloquant)
        t_start = time.time()
        self._demandes_en_cours[cle] = t_start
        pas_sondage_s = 0.5
        seuil_attente_agent = self.attente_max_s / 4.0

        try:
            while True:
                now = time.time()
                elapsed = now - t_start

                # Gestion d'état typé ETAT_EN_ATTENTE_AGENT (§4.5)
                if elapsed > seuil_attente_agent and self.execution is not None:
                    etat_courant = self.execution.etat().get("etat")
                    if etat_courant not in (ETAT_EN_ATTENTE_AGENT, "epuisee", "arretee"):
                        self.execution.changer_etat(
                            ETAT_EN_ATTENTE_AGENT,
                            f"antigravity: attente agent > {seuil_attente_agent:.0f}s",
                        )

                self._verifier_journal_et_alarmes(now)

                # Timeout par déplacement (§4.5)
                if elapsed >= self.attente_max_s:
                    self.compteurs["timeouts"] += 1
                    return ReponseDecideur(
                        index=None,
                        fournisseur=self.nom,
                        erreur=f"antigravity: pas de réponse en {self.attente_max_s}s",
                        modele_verifie=False,
                        presente=presente,
                    )

                if reponse_path.is_file():
                    try:
                        contenu = reponse_path.read_text(encoding="utf-8")
                        resp = json.loads(contenu)
                    except (json.JSONDecodeError, OSError):
                        # Fichier en cours d'écriture non atomique : attendre le tour suivant
                        await asyncio.sleep(pas_sondage_s)
                        continue

                    # Contrôle person_id / activity_id (§4.4)
                    if (
                        str(resp.get("person_id")) != str(person.person_id)
                        or str(resp.get("activity_id")) != str(ctx.activity_id)
                    ):
                        self.compteurs["rejets"] += 1
                        logger.warning(
                            f"[antigravity] Réponse hors sujet pour {cle} : "
                            f"reçu {resp.get('person_id')}/{resp.get('activity_id')}"
                        )
                        reponse_path.unlink(missing_ok=True)
                        await asyncio.sleep(pas_sondage_s)
                        continue

                    # Contrôle modèle déclaré vs modèle attendu (§4.4)
                    modele_declare = resp.get("modele_declare")
                    if modele_declare != self.modele:
                        self.compteurs["rejets"] += 1
                        # Déplacer la demande vers traitées pour clore la sollicitation
                        traitee_path = self.dossier_demandes_traitees / demande_fichier
                        try:
                            os.replace(demande_path, traitee_path)
                        except OSError:
                            pass
                        return ReponseDecideur(
                            index=None,
                            fournisseur=self.nom,
                            erreur=(
                                f"antigravity: modèle déclaré inattendu "
                                f"({modele_declare!r} != {self.modele!r})"
                            ),
                            reponse_brute=resp.get("reponse_brute"),
                            modele_verifie=False,
                            presente=presente,
                        )

                    # Réponse valide reçue : déplacer la demande vers traitées
                    traitee_path = self.dossier_demandes_traitees / demande_fichier
                    try:
                        os.replace(demande_path, traitee_path)
                    except OSError:
                        pass

                    # Rétablir l'état en cours si on était en attente agent
                    if self.execution is not None:
                        if self.execution.etat().get("etat") == ETAT_EN_ATTENTE_AGENT:
                            self.execution.changer_etat(
                                ETAT_EN_COURS, "antigravity: réponse reçue"
                            )

                    # 5. Interprétation du verdict (§3.1 étape 4, D10)
                    agents = resp.get("agents") or []
                    agent_entry = agents[0] if agents else {}
                    entries = agent_entry.get("probabilities")
                    sent_modes = [
                        t.get("mode") for t in payload["agents"][0]["trajectories"]
                    ]

                    sorted_options = sorted(options, key=lambda p: p.get_code() or "")
                    position_in_sorted = {
                        id(opt): i for i, opt in enumerate(sorted_options)
                    }

                    shuffled_weights = normalize_option_probabilities(
                        entries,
                        len(options),
                        modes=sent_modes,
                        context=f"agent={person.person_id} activity={ctx.activity_id}",
                    )
                    weights_are_fallback = isinstance(
                        shuffled_weights, UniformFallback
                    )

                    weights = [0.0] * len(sorted_options)
                    for opt, w in zip(options, shuffled_weights):
                        weights[position_in_sorted[id(opt)]] += w

                    seed_parts = (
                        ctx.graine_tirage,
                        person.person_id,
                        ctx.activity_id,
                        datetime.fromtimestamp(
                            ctx.timestamp, tz=timezone.utc
                        ).strftime("%Y-%m-%d"),
                    )
                    idx_sorted = draw_index(weights, *seed_parts)
                    chosen_plan = sorted_options[idx_sorted]
                    idx_presentees = options.index(chosen_plan)

                    # Extraction de la justification
                    reasons = [None] * len(sorted_options)
                    if entries:
                        for entry in entries:
                            entry_reason = (
                                entry.get("reason")
                                if isinstance(entry, dict)
                                else getattr(entry, "reason", None)
                            )
                            if not entry_reason:
                                continue
                            try:
                                entry_idx = int(
                                    entry["index"]
                                    if isinstance(entry, dict)
                                    else entry.index
                                )
                            except (TypeError, ValueError, KeyError):
                                continue
                            if 0 <= entry_idx < len(options):
                                opt = options[entry_idx]
                                reasons[position_in_sorted[id(opt)]] = entry_reason

                    agent_reason = agent_entry.get("reason") or ""
                    reason = (
                        (reasons[idx_sorted] if reasons else None)
                        or agent_reason
                        or "Pas de justification fournie."
                    )
                    if "is chosen because it" in reason:
                        reason = f"This plan {reason.split('is chosen because it', 1)[1].strip()}"

                    modes = [opt.mode_label() for opt in sorted_options]
                    distribution = mode_distribution(weights, modes)
                    reason = (
                        f"{reason} [Répartition estimée : "
                        f"{_format_distribution(distribution)} — mode tiré au sort.]"
                    )

                    self.compteurs["servies"] += 1
                    if weights_are_fallback:
                        self.compteurs["replis"] += 1
                    if not resp.get("sortie_litterale"):
                        self.compteurs["sans_sortie_litterale"] += 1
                        if not self._alarme_litterale_levee:
                            logger.warning(
                                "[antigravity] Réponse sans `sortie_litterale` — la trace ne "
                                "montrera pas ce que le modèle a écrit (P8). Le champ est "
                                "attendu verbatim dans chaque fichier de réponse."
                            )
                            self._alarme_litterale_levee = True

                    return ReponseDecideur(
                        index=idx_presentees,
                        fournisseur=self.nom,
                        distribution=dict(distribution or {}),
                        poids=[float(w) for w in shuffled_weights],
                        reponse_brute=(
                            resp.get("reponse_brute")
                            or json.dumps(resp, ensure_ascii=False)
                        ),
                        # P8 — transmise TELLE QUELLE, jamais normalisée ni repliée sur
                        # `reponse_brute` : un trou déclaré vaut mieux qu'une copie qu'on
                        # prendrait pour la sortie du modèle.
                        sortie_litterale=resp.get("sortie_litterale"),
                        raison=reason,
                        souvenirs=[],
                        presente=presente,
                        repli_uniforme=weights_are_fallback,
                        modele_verifie=False,
                    )

                await asyncio.sleep(pas_sondage_s)
        finally:
            self._demandes_en_cours.pop(cle, None)


__all__ = ["DecideurAntigravity"]
