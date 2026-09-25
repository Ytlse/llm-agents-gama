"""Enquête d'affinité modale déclarée — tickets 077 (sonde) et 095, lot B (instrument).

DEUX EXIGENCES DISTINCTES, ET LE MODULE N'EN PORTAIT QU'UNE.

**En SORTIE, étanchéité absolue.** Les réponses vont dans `affinites_declarees.csv` et nulle
part ailleurs : ni STM, ni LTM, ni ChromaDB, ni passerelle de réflexion nocturne. L'enquête ne
contamine aucune délibération ultérieure. C'est ce que ce module promettait déjà, et cela ne
change pas.

**En ENTRÉE, fidélité complète.** Le prompt sert EXACTEMENT le même bloc mémoire que le prompt
de décision — `memoire_noyau(journal, entrées, maintenant, person_id)`, soit « Mes habitudes »,
« Ce que je sais » et « Ce qui a changé récemment » — plus le récit d'identité complet du
persona. Jusqu'au 2026-09-21, la perception servie tenait en quatre champs : nom, âge, genre,
occupation. **Telle qu'écrite, l'enquête mesurait l'a priori du modèle de base sur une femme de
53 ans à temps partiel** — identique au jour 12 et au jour 29, identique dans le bras à fenêtre
7 et dans celui à fenêtre 14. Elle n'aurait rien détecté, et son silence aurait été pris pour
une absence d'effet.

⚠ **L'enquête LIT la mémoire, elle ne la RAPPELLE pas.** `memoire_noyau` ne touche ni `force` ni
`dernier_rappel`. Le chemin de rappel vectoriel, lui, renforce la force de chaque souvenir servi
(`llm_agent.py`, `force_apres_rappel`) : l'emprunter ferait de la sonde un prolongateur de durée
de vie de ce qu'elle observe. Elle ne l'emprunte pas.

L'INSTRUMENT (ticket 095, lot B)
--------------------------------
Six critères d'Adam & Gaudou (2025) — rapidité, praticité, confort, sécurité, accessibilité
financière, écologie — sur une échelle de Likert 0-10, et **cinq prompts par jalon** :

- quatre prompts de perception, **un par mode**, le mode nommé et les trois autres jamais cités.
  Les 24 scores demandés d'un coup produisaient une grille plate ;
- un prompt de PRIORITÉS, qui ne nomme aucun mode. Avec les précédents, il rend calculable
  `score(mode) = Σ val(mode, critère) × prio(critère)` — le mode que le modèle symbolique
  d'Adam & Gaudou prédirait à partir des déclarations de notre agent, à confronter au mode
  qu'il choisit le lendemain.

L'ÉCOLOGIE EST LA QUESTION TÉMOIN. Aucun des six chocs déclarés du dépôt ne la vise. Si le score
d'écologie du vélo chute après une crevaison, l'agent n'a pas noté un critère : il a exprimé une
humeur globale, et l'instrument entier est invalide. Une question qui doit rester plate est une
garde, pas une dépense.
"""

from __future__ import annotations

import asyncio
import csv
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger
from llm.noyau import TITRE_CHANGEMENTS, memoire_noyau
from sim_clock import wall_clock
from urban_mobility_agents.utils.ancre_run import jours_ecoules
from urban_mobility_agents.utils.modeles import modele_de_instance
from urban_mobility_agents.utils.routage import instances_pour

# Jalons d'enquête, en jours de CALENDRIER du run (le jour 1 est le premier jour simulé).
#
# ⚠ Les jalons se DÉCLARENT (`EXPERIMENT_SURVEY_DAYS="12,17,29,40"`). La première version les
# écrivait en dur — 5, 9 et 19 — avec les libellés « pré-choc », « péri-choc », « post-choc ».
# Ces libellés dataient du protocole où le choc tombait au jour 8. Quand le choc est passé aux
# jours 15 et 16, le jour 9 est devenu pré-choc, le 19 s'est retrouvé à quatre jours du choc, et
# plus aucun jalon ne tombait après la sortie de la fenêtre de mémoire. Trois libellés faux, et
# un sondage payé pour rien.
#
# Défaut aligné sur le protocole en vigueur (choc aux jours 15 et 16, ancre lundi 16 mars) :
#   J12 — vendredi 27 mars : dernier jour ouvré de la baseline, l'habitude est formée
#   J17 — mercredi 1er avril : lendemain du second jour de choc
#   J29 — lundi 13 avril : jour où le souvenir de choc sort de la fenêtre du bloc noyau
#   J40 — vendredi 24 avril : tardif, une fois le choc hors de portée
JOURS_JALONS_DEFAUT: tuple[int, ...] = (12, 17, 29, 40)
HEURE_ENQUETE_H = 21  # 21h00

# ── L'instrument : six critères, quatre modes, un vecteur de priorités ───────────
# Les six critères d'Adam & Gaudou (2025). Clés canoniques en FRANÇAIS — c'est la langue dans
# laquelle l'échelle a été définie et discutée, et ce sont elles qui sortent dans le CSV ; le
# gabarit s'adresse au modèle en anglais (ticket 074).
#
# ⚠ Retirer la SÉCURITÉ rendrait l'instrument aveugle à quatre chocs déclarés sur six (C2, C3,
# C5, C6). L'ÉCOLOGIE, elle, est la question TÉMOIN : aucun des six chocs ne la vise, et elle
# doit rester plate. Si elle bouge, l'agent a exprimé une humeur globale au lieu de noter un
# critère, et le reste de la mesure ne s'interprète plus.
CRITERES: tuple[str, ...] = (
    "rapidite", "praticite", "confort", "securite", "cout", "ecologie"
)

# Modes interrogés par défaut : les quatre d'Adam & Gaudou. Le train et le deux-roues motorisé
# s'ajoutent quand le choc du run les vise (C4, C5) — liste DÉCLARÉE, jamais codée en dur.
MODES_DEFAUT: tuple[str, ...] = ("voiture", "transports_collectifs", "velo", "marche")

# Comment le mode est NOMMÉ au modèle. Un prompt par mode, les autres jamais cités.
LIBELLE_MODE_EN = {
    "voiture": "the car",
    "transports_collectifs": "public transport",
    "velo": "the bicycle",
    "marche": "walking",
    "train": "the train",
    "deux_roues": "the motor scooter",
}

# Valeur de la colonne `mode` pour les six lignes du vecteur de priorités. Le même fichier porte
# les deux vecteurs : un second fichier obligerait à les rapprocher, et la formule de score les
# consomme ensemble.
MODE_PRIORITES = "critere_priorite"

SCORE_MIN, SCORE_MAX = 0, 10

COLONNES_CSV = (
    "sim_timestamp", "date_simulee", "jour_simule", "persona_id",
    "mode", "critere", "score", "justification", "provider", "model",
)

_jalons: tuple[int, ...] | None = None
_modes: tuple[str, ...] | None = None
_jalons_verifies = False


def reinitialiser() -> None:
    """Oublie les jalons et les modes lus, et le signalement déjà fait. Réservé aux tests."""
    global _jalons, _jalons_verifies, _modes
    _jalons = None
    _modes = None
    _jalons_verifies = False


def jours_jalons() -> tuple[int, ...]:
    """Les jalons en vigueur, lus une fois puis mémorisés."""
    global _jalons
    if _jalons is not None:
        return _jalons

    brut = (os.getenv("EXPERIMENT_SURVEY_DAYS") or "").strip()
    if not brut:
        _jalons = JOURS_JALONS_DEFAUT
        logger.info(f"[enquete] jalons non déclarés — valeur par défaut {list(_jalons)}")
        return _jalons

    try:
        lus = tuple(int(p.strip()) for p in brut.split(",") if p.strip())
        if not lus or any(j < 1 for j in lus):
            raise ValueError(f"jalons vides ou hors domaine : {lus}")
    except ValueError as exc:
        # Un sondage éteint en silence ne se distingue pas d'un sondage qui n'a rien trouvé.
        logger.error(
            f"[ALARME] [enquete] EXPERIMENT_SURVEY_DAYS illisible (« {brut} » — {exc}) : "
            f"repli sur {list(JOURS_JALONS_DEFAUT)}. Les réponses attendues aux jours déclarés "
            f"n'existeront pas."
        )
        _jalons = JOURS_JALONS_DEFAUT
        return _jalons

    _jalons = lus
    logger.info(f"[enquete] jalons déclarés : {list(_jalons)}")
    return _jalons


def verifier_jalons_atteignables(jour_courant: int, date_du_jour_courant: str) -> None:
    """Signale UNE fois les jalons qui tombent un week-end, donc ne se déclencheront jamais.

    La simulation saute les départs de samedi et dimanche (`agent.no_weekend_departures`). Un
    jalon posé un de ces jours reste muet, et son absence se lit comme une panne du sondage —
    c'est exactement ce qui est arrivé aux chocs posés aux jours 6 et 7 (ticket 077, § 10.2).
    """
    global _jalons_verifies
    if _jalons_verifies:
        return
    _jalons_verifies = True
    try:
        ancre = datetime.fromisoformat(str(date_du_jour_courant)[:10]).date() - timedelta(
            days=int(jour_courant) - 1
        )
    except (TypeError, ValueError) as exc:
        logger.warning(f"[enquete] jalons non vérifiables ({exc!r})")
        return
    for jalon in jours_jalons():
        jour = ancre + timedelta(days=jalon - 1)
        if jour.weekday() >= 5:
            logger.warning(
                f"[enquete] jalon J{jalon} inatteignable : il tombe un "
                f"{'samedi' if jour.weekday() == 5 else 'dimanche'} ({jour.isoformat()}), "
                f"et la simulation saute les week-ends. Ce sondage ne se déclenchera jamais."
            )


def is_enquete_due(timestamp: int, enquetes_menees: set[int]) -> int | None:
    """Vérifie si une enquête d'affinité déclarée doit être déclenchée.

    Retourne le numéro du jour jalon, ou None.
    """
    # Vérification du drapeau d'activation (défaut False pour le mode principal)
    if os.getenv("EXPERIMENT_SURVEY_ENABLED") != "1":
        return None

    jour = jours_ecoules(timestamp) + 1
    verifier_jalons_atteignables(jour, wall_clock(timestamp).strftime("%Y-%m-%d"))
    if jour in jours_jalons() and jour not in enquetes_menees:
        heure = wall_clock(timestamp).hour
        if heure >= HEURE_ENQUETE_H:
            return jour
    return None


def modes_interroges() -> tuple[str, ...]:
    """Les modes à interroger, DÉCLARÉS par `EXPERIMENT_SURVEY_MODES`, lus une fois.

    Codés en dur, ils rendraient l'instrument aveugle aux chocs qui visent le train (C4) ou le
    deux-roues (C5) : quatre prompts sur quatre modes, dont aucun n'est celui que le choc a
    frappé.
    """
    global _modes
    if _modes is not None:
        return _modes
    brut = (os.getenv("EXPERIMENT_SURVEY_MODES") or "").strip()
    if not brut:
        _modes = MODES_DEFAUT
        logger.info(f"[enquete] modes non déclarés — valeur par défaut {list(_modes)}")
        return _modes
    lus = tuple(m.strip() for m in brut.split(",") if m.strip())
    inconnus = [m for m in lus if m not in LIBELLE_MODE_EN]
    if inconnus:
        # Un mode inconnu n'a pas de libellé : le prompt poserait six questions sur rien.
        logger.error(
            f"[ALARME] [enquete] mode(s) inconnu(s) déclaré(s) : {inconnus} — ils sont écartés. "
            f"Modes connus : {sorted(LIBELLE_MODE_EN)}."
        )
        lus = tuple(m for m in lus if m in LIBELLE_MODE_EN)
    if not lus:
        logger.error(
            f"[ALARME] [enquete] EXPERIMENT_SURVEY_MODES (« {brut} ») ne laisse aucun mode "
            f"connu — repli sur {list(MODES_DEFAUT)}."
        )
        lus = MODES_DEFAUT
    _modes = lus
    logger.info(f"[enquete] modes déclarés : {list(_modes)}")
    return _modes


def perception_de(
    agent: Any, person: Any, timestamp: int, lignes: tuple[str, ...] | list[str] = ()
) -> str:
    """Ce que l'agent SAIT de lui-même au moment de l'enquête — identité et mémoire noyau.

    C'est ici que se joue la fidélité en entrée. Le bloc mémoire est construit par le MÊME appel
    que le prompt de décision (`memoire_noyau`), et non par une variante « allégée » qui
    divergerait en silence : une sonde qui ne voit pas ce que l'agent voit ne mesure pas l'agent.

    ⚠ Aucun rappel vectoriel : `memoire_noyau` lit, il ne renforce rien. Emprunter le chemin de
    rappel prolongerait la durée de vie des souvenirs qu'on observe.

    Un bloc qui ne se construit pas ne fait pas perdre l'enquête, mais il ne disparaît pas non
    plus en silence : sans lui, la réponse mesure le modèle de base et non l'agent, et c'est
    exactement le défaut que ce lot corrige.

    `lignes` (ticket 111, D6) — ce qui est garanti au prompt de décision ce jour-là. Une enquête
    tenue un jour de service voit la MÊME ligne que la décision : sans cela, elle interrogerait
    un agent qui ne sait pas ce qu'il a lu le matin même.
    """
    pid = str(person.person_id)
    morceaux: list[str] = []
    try:
        recit = agent.get_person_identity_description(person)
        if recit:
            morceaux.append(str(recit).strip())
    except Exception as err:  # noqa: BLE001
        logger.warning(f"[enquete] récit d'identité indisponible pour {pid} ({err})")

    try:
        entrees = (
            agent.long_term_memory.user_metadata.get(pid, {}).get("entries", [])
            if getattr(agent, "long_term_memory", None) is not None
            else []
        )
        journal = (
            agent.long_term_memory.journal_trajets(pid)
            if getattr(agent, "long_term_memory", None) is not None
            else {}
        )
        bloc = memoire_noyau(journal, entrees, wall_clock(timestamp), pid, lignes)
    except Exception as err:  # noqa: BLE001
        logger.error(
            f"[ALARME] [enquete] mémoire noyau non construite pour {pid} ({err}) — la réponse "
            f"mesurerait le modèle de base et non l'agent."
        )
        bloc = [TITRE_CHANGEMENTS, *(f"- {l}" for l in lignes)] if lignes else []
    if bloc:
        morceaux.append("\n".join(bloc))
    return "\n\n".join(morceaux)


def _scores_valides(pid: str, jour: int, mode: str, scores: dict) -> dict[str, Any]:
    """Les six scores, tels que rendus. Une valeur hors domaine est SIGNALÉE, pas rabotée.

    Raboter en silence fabriquerait une mesure : un 14 ramené à 10 se lit comme un avis maximal
    alors qu'il dit que le modèle n'a pas respecté l'échelle.
    """
    rendus: dict[str, Any] = {}
    for critere in CRITERES:
        brut = scores.get(critere)
        if brut is None:
            logger.error(
                f"[ALARME] [enquete] critère « {critere} » absent de la réponse | "
                f"persona={pid} jour=J{jour} mode={mode}"
            )
            continue
        try:
            valeur = int(brut)
        except (TypeError, ValueError):
            logger.error(
                f"[ALARME] [enquete] score illisible ({brut!r}) | persona={pid} jour=J{jour} "
                f"mode={mode} critere={critere}"
            )
            rendus[critere] = brut
            continue
        if not (SCORE_MIN <= valeur <= SCORE_MAX):
            logger.error(
                f"[ALARME] [enquete] score hors du domaine {SCORE_MIN}-{SCORE_MAX} ({valeur}) | "
                f"persona={pid} jour=J{jour} mode={mode} critere={critere} — écrit tel quel, "
                f"jamais raboté."
            )
        rendus[critere] = valeur
    return rendus


async def _interroger(
    llm_client: Any, pid: str, perception: str, mode: str | None
) -> tuple[dict, str, str] | None:
    """Un prompt, un mode (ou les priorités si `mode` est None). Rend (scores, provider, model)."""
    payload = {
        "category": "enquete_affinite",
        # Ticket 095, lot C — la sonde n'a pas à disputer sa clé à la variable mesurée.
        "instances_admises": instances_pour("enquete_affinite"),
        "agents": [
            {
                "agent_id": pid,
                "perception": perception,
                "mode_interroge": LIBELLE_MODE_EN[mode] if mode else None,
            }
        ],
        "parameters": {"temperature": 0.2, "max_tokens": 512},
    }
    res = await llm_client.execute(payload)
    if not res or not res.agents:
        return None
    rep = res.agents[0]
    scores = getattr(rep, "scores", {}) or {}
    justification = (getattr(rep, "justification", "") or "").strip()
    provider = res.provider_used or "unknown"
    return (
        {"scores": scores, "justification": justification},
        provider,
        modele_de_instance(provider),
    )


async def executer_enquetes_jalon(
    jour: int,
    timestamp: int,
    people: list[Any],
    agent: Any,
    output_dir: Path,
) -> None:
    """Les cinq prompts du jalon, pour chaque persona cible.

    Sauvegarde dans `affinites_declarees.csv` en format LONG — une ligne par (jour, persona,
    mode, critère, score) — SANS JAMAIS toucher à la mémoire des agents. Le format large à 24
    colonnes obligeait à réécrire l'en-tête dès qu'un mode s'ajoutait ; le format long absorbe
    le train et le deux-roues sans changer de schéma.

    `agent` est l'agent LLM complet, et non son seul client : c'est de lui que viennent le récit
    d'identité et la mémoire noyau, sans lesquels la sonde mesure le modèle de base.
    """
    llm_client = getattr(agent, "llm_client", None) or agent
    csv_file = output_dir / "affinites_declarees.csv"
    file_exists = csv_file.is_file()

    target_env = os.getenv("EXPERIMENT_TARGET_PERSONAS")
    if target_env:
        cibles_ids = {pid.strip() for pid in target_env.split(",") if pid.strip()}
        cibles = [p for p in people if str(p.person_id) in cibles_ids]
    elif len(people) == 1:
        # En mode séquentiel de 1 habitant, l'unique persona est la cible
        cibles = people
    else:
        logger.warning(
            "[enquete] Plusieurs personas présents sans EXPERIMENT_TARGET_PERSONAS défini — "
            "sondage ignoré."
        )
        return

    modes = modes_interroges()
    attendus = len(modes) + 1
    logger.info(
        f"[enquete] jalon J{jour} — {len(cibles)} persona(s), {attendus} prompt(s) chacun "
        f"({len(modes)} mode(s) + priorités)."
    )

    lignes: list[dict[str, Any]] = []
    horodatage = wall_clock(timestamp).strftime("%Y-%m-%d %H:%M")

    # 2026-09-24 — les personas s'interrogent ENSEMBLE, mode par mode. Le micro-batching du
    # gateway fusionne alors une vague en un seul prompt multi-agent ; la boucle personne par
    # personne ne lui présentait jamais qu'un agent à la fois. Les modes, eux, restent
    # SÉQUENTIELS : un lot ne réunit ainsi que des questions sur le même mode, et le prompt
    # fusionné n'en cite jamais qu'un.
    from llm import evenements as _evenements

    perceptions = {
        str(p.person_id): perception_de(
            agent,
            p,
            timestamp,
            await _evenements.lignes_du_jour(str(p.person_id), timestamp, compter=False),
        )
        for p in cibles
    }
    rendus: dict[str, int] = {pid: 0 for pid in perceptions}
    par_persona: dict[str, list[dict[str, Any]]] = {pid: [] for pid in perceptions}

    async def _une_question(pid: str, mode: str | None) -> None:
        etiquette = mode or MODE_PRIORITES
        try:
            res = await _interroger(llm_client, pid, perceptions[pid], mode)
        except Exception as err:  # noqa: BLE001
            # Un prompt en échec n'emporte pas les quatre autres : l'enquête est partielle
            # et le dit, plutôt que muette.
            logger.error(
                f"[ALARME] [enquete] appel en échec | persona={pid} jour=J{jour} "
                f"mode={etiquette} : {err}"
            )
            return
        if res is None:
            logger.error(
                f"[ALARME] [enquete] réponse vide | persona={pid} jour=J{jour} "
                f"mode={etiquette}"
            )
            return
        contenu, provider, modele = res
        scores = _scores_valides(pid, jour, etiquette, contenu["scores"])
        if not scores:
            return
        rendus[pid] += 1
        for critere, score in scores.items():
            par_persona[pid].append(
                {
                    "sim_timestamp": timestamp,
                    "date_simulee": horodatage,
                    "jour_simule": jour,
                    "persona_id": pid,
                    "mode": etiquette,
                    "critere": critere,
                    "score": score,
                    "justification": contenu["justification"],
                    "provider": provider,
                    "model": modele,
                }
            )
        logger.info(
            f"[enquete] J{jour} {pid} · {etiquette} : "
            + ", ".join(f"{c}={scores.get(c)}" for c in CRITERES)
            + f" | {provider}/{modele} | étanchéité mémoire : RESPECTÉE."
        )

    # Les quatre (ou six) modes, puis les priorités. `None` = le prompt de priorités.
    for mode in (*modes, None):
        debut_mode = time.monotonic()
        await asyncio.gather(*(_une_question(pid, mode) for pid in perceptions))
        logger.info(
            f"[enquete] J{jour} · {mode or MODE_PRIORITES} : {len(perceptions)} persona(s) "
            f"interrogé(s) ensemble en {time.monotonic() - debut_mode:.1f}s."
        )

    for pid in perceptions:
        # Même ordre qu'avant le regroupement : persona, puis mode dans l'ordre des questions.
        lignes.extend(par_persona[pid])
        if rendus[pid] == 0:
            # Un jalon muet ne se distingue pas d'un jalon sans effet : c'est exactement le
            # silence qui aurait été lu comme « rien n'a bougé » sur la campagne du 077.
            logger.error(
                f"[ALARME] [enquete] jalon J{jour} passé SANS AUCUNE réponse pour le persona "
                f"{pid} — aucune mesure de croyance n'existera pour ce jalon."
            )
        elif rendus[pid] < attendus:
            logger.error(
                f"[ALARME] [enquete] jalon J{jour} incomplet pour {pid} : {rendus[pid]}/{attendus} "
                f"prompts rendus. La formule de score sera incalculable si les priorités "
                f"manquent."
            )

    if lignes:
        with open(csv_file, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(COLONNES_CSV))
            if not file_exists:
                writer.writeheader()
            for ligne in lignes:
                writer.writerow(ligne)
        logger.info(f"[enquete] {len(lignes)} ligne(s) enregistrée(s) dans {csv_file}")
