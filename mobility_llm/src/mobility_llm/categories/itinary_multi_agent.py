"""categories/itinary_multi_agent.py — ce que le worker observe d'une décision d'itinéraire.

Le LLM renvoie une distribution sur les options proposées, pas un choix : le tirage effectif
a lieu côté simulation (``mobility_llm.mode_choice.draw_index`` dans le contrôleur). Le
worker, lui, alimente des compteurs de diagnostic : mode le plus probable, masse de
probabilité par mode, tranche de distance, désaccords entre le mode annoncé par le LLM et
celui de l'option. Ce module est appelé par le gateway via ``CategorySpec.observe`` ; il ne
modifie pas la réponse.

Les noms de compteurs sont ceux que ``llm_gateway.api.metrics.WorkerMetricsCollector``
relit dans Redis (``transport_mode_chosen:*``, ``mode_by_provider:*``…) : les changer casse
les dashboards Grafana 04 et 07.
"""
from __future__ import annotations

from llm_gateway.ports.category import ObserveContext
from loguru import logger
from mobility_core.mode_hierarchy import hierarchy

from mobility_llm.mode_choice import (
    argmax_index,
    canonical_mode,
    mode_distribution,
    normalize_option_probabilities,
)

# Au-delà de ce taux d'options mal étiquetées sur la fenêtre observée, on lève une
# alarme : ce n'est plus du bruit, le modèle ne lit plus la liste qu'on lui envoie.
MODE_MISMATCH_ALARM_RATIO = 0.05
MODE_MISMATCH_MIN_SAMPLE = 200

# Famille de la hiérarchie de l'enquête → étiquette des compteurs du worker. Le
# vocabulaire de ces compteurs est FIN (métro, tram et bus distincts, contrairement aux
# quatre catégories du scoring EMC²) : c'est un compteur de diagnostic, pas une part
# modale. Les noms existants sont conservés pour que les séries Redis restent lisibles
# d'un run à l'autre.
WORKER_MODE_LABEL = {
    "metro": "metro", "tram": "tram", "cableway": "cableway", "bus": "bus",
    "rail": "train", "car": "car", "motorbike": "motorbike",
    "bicycle": "cycling", "foot": "walking",
}
# Synonymes en toutes lettres que la hiérarchie ne connaît pas (elle porte les modes de
# JAMBE d'OTP/OSMnx, pas les libellés que le LLM peut écrire).
WORKER_MODE_ALIASES = {
    "train": "rail", "ter": "rail", "intercités": "rail", "intercites": "rail",
    "tc": "bus", "transports en commun": "bus", "transport en commun": "bus",
    "voiture": "car", "driving": "car", "conducteur": "car",
    "vélo": "bicycle", "velo": "bicycle", "cycling": "bicycle",
    "marche": "foot", "walking": "foot", "à pied": "foot", "a pied": "foot",
    "pied": "foot",
}


def extract_primary_mode(mode: str) -> str:
    """Réduit une chaîne de modes composée (« foot,bus,foot ») au mode principal.

    L'ordre vient de ``mobility_core.mode_hierarchy``, donc de l'annexe « Hiérarchie des
    modes » du rapport de l'enquête : métro > tram > téléphérique > bus > train > voiture >
    deux-roues motorisé > vélo > marche. Une chaîne « bus,train » compte ``bus`` (ticket 022).
    """
    if not mode or mode == "unknown":
        return "unknown"
    parts = {m.strip().lower() for m in mode.split(",")}
    jambes = {WORKER_MODE_ALIASES.get(p, p) for p in parts}
    family = hierarchy().primary_family(jambes)
    if family is None:
        logger.error(f"Mode de transport inconnu ou non standard dans la réponse LLM | mode={mode}")
        return "other"
    return WORKER_MODE_LABEL[family]


def distance_bracket(distance_m: float) -> str:
    """Classe une distance en mètres dans une tranche prédéfinie."""
    if distance_m < 1_000:
        return "0-1km"
    if distance_m < 2_000:
        return "1-2km"
    if distance_m < 5_000:
        return "2-5km"
    if distance_m < 10_000:
        return "5-10km"
    if distance_m < 20_000:
        return "10-20km"
    if distance_m < 50_000:
        return "20-50km"
    return ">50km"


def count_mode_mismatches(metrics, agent_resp, traj_modes: list, provider_name: str) -> None:
    """Compare le mode recopié par le LLM à celui de l'option, index par index.

    Ce champ est redondant côté production (le mode réel vient des trajectoires), mais
    c'est justement ce qui en fait un témoin : un désaccord signale que **le modèle a lu
    une autre option que celle qu'il croit noter**, et ses probabilités sont alors
    attribuées aux mauvais index sans que rien d'autre ne le montre.
    """
    total = mismatched = 0
    for entry in agent_resp.probabilities or ():
        announced = getattr(entry, "mode", None)
        if not announced:
            continue
        try:
            i = int(getattr(entry, "index", None))
        except (TypeError, ValueError):
            continue
        if not 0 <= i < len(traj_modes):
            continue
        total += 1
        if canonical_mode(announced) != canonical_mode(traj_modes[i]):
            mismatched += 1
            logger.warning(
                f"Mode annoncé par le LLM ≠ mode de l'option | index={i} "
                f"annoncé={announced!r} réel={traj_modes[i]!r} "
                f"agent={agent_resp.agent_id} provider={provider_name}"
            )

    if not total:
        return
    metrics.incr("mode_label_checked", amount=total)
    if mismatched:
        metrics.incr("mode_label_mismatch", amount=mismatched)

    checked = metrics.get("mode_label_checked") or 0
    bad = metrics.get("mode_label_mismatch") or 0
    if checked >= MODE_MISMATCH_MIN_SAMPLE and bad / checked > MODE_MISMATCH_ALARM_RATIO:
        # Front montant : l'alarme ne part qu'une fois. Le worker n'expose pas de /metrics :
        # elle transite par Redis et ressort en alarme_total{source} côté API.
        if not metrics.get("alarme:mode_label_mismatch"):
            metrics.incr("alarme:mode_label_mismatch")
            logger.error(
                f"[ALARME] Étiquettes de mode incohérentes : {bad}/{checked} "
                f"({100 * bad // checked} %) des options notées portent un mode qui n'est "
                f"pas celui de l'option. Le modèle confond les options : les probabilités "
                f"sont attribuées aux mauvais index et la répartition modale est fausse."
            )


def observe_itinary(ctx: ObserveContext) -> None:
    """Compteurs de diagnostic d'un lot d'itinéraires réussi (hook ``CategorySpec.observe``)."""
    metrics = ctx.metrics
    provider_name = ctx.provider
    specs_by_id = {str(getattr(a, "agent_id", "")): a for a in ctx.items}
    for agent_resp in ctx.output.agents:
        spec = specs_by_id.get(str(agent_resp.agent_id))
        trajectories = list(getattr(spec, "trajectories", []) or []) if spec else []
        idx = agent_resp.chosen_index  # repli : réponse à l'ancien format

        if agent_resp.probabilities and trajectories:
            # Les modes viennent des trajectoires envoyées (source de vérité), pas de ceux
            # recopiés par le LLM. Ils servent aussi à réaligner les index hors bornes.
            traj_modes = [t.get("mode") for t in trajectories]
            weights = normalize_option_probabilities(
                agent_resp.probabilities, len(trajectories),
                modes=traj_modes,
                context=f"agent={agent_resp.agent_id} provider={provider_name}",
            )
            for mode, mass in mode_distribution(weights, traj_modes).items():
                metrics.incr(f"mode_probability_pct:{mode}", amount=round(mass * 100))
            idx = argmax_index(weights)
            count_mode_mismatches(metrics, agent_resp, traj_modes, provider_name)

        in_range = idx is not None and trajectories and 0 <= idx < len(trajectories)
        raw_mode = trajectories[idx].get("mode") if in_range else agent_resp.mode
        primary_mode = extract_primary_mode(raw_mode or "unknown")
        metrics.incr(f"transport_mode_chosen:{primary_mode}")
        metrics.incr(f"mode_by_provider:{primary_mode}:{provider_name}")

        if in_range:
            dist_m = float(trajectories[idx].get("total_distance_m") or 0)
            bracket = distance_bracket(dist_m)
            metrics.incr(f"trip_distance_bracket:{bracket}")
            metrics.incr(f"mode_by_distance:{primary_mode}:{bracket}")
            metrics.incr(f"chosen_index:{idx}")


__all__ = [
    "MODE_MISMATCH_ALARM_RATIO",
    "MODE_MISMATCH_MIN_SAMPLE",
    "WORKER_MODE_ALIASES",
    "WORKER_MODE_LABEL",
    "count_mode_mismatches",
    "distance_bracket",
    "extract_primary_mode",
    "observe_itinary",
]
