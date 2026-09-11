"""Classement des itinéraires et plafonnement des candidats présentés au décideur.

Deux lectures d'un plan, volontairement distinctes (ticket 022) : `_primary_mode` rend la
catégorie agrégée de l'enquête (marche / vélo / voiture / transports collectifs) pour les
métriques ; `_selection_group` en dérive la clé de regroupement des options offertes à
l'agent (le ferroviaire à part), et `_select_candidates` plafonne la liste en gardant le plus
rapide de chaque groupe. Extrait de `simulation_controller.py` (ticket 035, spec 02) pour que
la simulation GAMA et l'exécution sans simulateur plafonnent **à l'identique** ; le contrôleur
ré-exporte ces noms.
"""

from loguru import logger

from mobility_core.mode_hierarchy import hierarchy as _mode_hierarchy
from llm_gateway.telemetry.alarms import fire_alarme
from models import TravelPlan

# Famille de la hiérarchie de l'enquête → catégorie de la métrique. Ce sont les QUATRE
# catégories agrégées de l'enquête (marche / vélo / véhicule particulier / transports en
# commun, cf. rapport p. 53 : les rangs 1 à 13 forment « transports en commun » et le train
# en fait partie). Fondre `rail` dans `transit` est donc CORRECT ici, et Grafana 07 mappe
# des deux côtés vers les mêmes quatre catégories.
MODE_HIERARCHY = _mode_hierarchy()

_METRIC_MODE = {
    "metro": "transit", "tram": "transit", "cableway": "transit", "bus": "transit",
    "rail": "transit", "car": "car", "motorbike": "other", "bicycle": "bike",
    "foot": "walk",
}
_unknown_metric_modes: set = set()


def _primary_mode(plan: TravelPlan) -> str:
    """Mode principal d'un plan, dans les quatre catégories agrégées de l'enquête.

    L'ordre vient de `mobility_core.mode_hierarchy` (annexe p. 53 du rapport, contrôlée
    sur les microdonnées) et non plus d'une cascade écrite ici, qui testait la **voiture en
    premier** alors qu'elle est au rang 19, sous tout le collectif (ticket 022).

    ⚠ Ne sert PAS à répondre « ce plan utilise-t-il la voiture ? » — c'est
    `_vehicle_mode`. Un mode principal et un mode de véhicule sont deux grandeurs
    différentes ; les confondre est le défaut que ce ticket sépare.
    """
    modes = {(leg.mode or "").lower() for leg in plan.legs if not leg.is_transfer}
    if not modes - {""}:
        # Aucune jambe mécanisée = un déplacement à pied. Ce n'est pas un repli : c'est le
        # rang 36 de l'enquête, « Marche à pied UNIQUEMENT », et il est mesuré — les
        # 14 842 déplacements sans trajet détaillé des microdonnées sont TOUS codés 01.
        return "walk"
    family = MODE_HIERARCHY.primary_family(modes)
    if family is None:
        # `transit` était le DÉFAUT de la cascade : tout mode inconnu y atterrissait sans
        # une ligne de journal, donc gonflait la part TC sans laisser de trace.
        cle = ",".join(sorted(modes))
        if cle not in _unknown_metric_modes:
            _unknown_metric_modes.add(cle)
            logger.error(
                f"[ALARME] Modes hors hiérarchie dans un plan : {{{cle}}} — comptés "
                "« other » dans trip_mode_by_purpose, et non plus « transit ». "
                "Complétez mobility_core/data/mode_hierarchy_emc2.json.")
            fire_alarme("mode_hierarchie")
        return "other"
    return _METRIC_MODE[family]


# ── Anticipation de la chaîne de la journée (ticket 014) ─────────────────────
# Le choix reste trajet par trajet, mais le bloc persona du prompt est enrichi :
# météo des tranches restantes (tous les agents), agenda glissant des trajets
# restants et position des véhicules (agents qui ont quelque chose à chaîner).
# Les verrous de chaîne restent le filet de sécurité — ce bloc informe, il ne
# contraint pas. La signature déterministe de ces textes entre dans la clé du
# cache de décisions (extra_key) : deux anticipations différentes ne peuvent
# pas se servir mutuellement une décision.


# Le train forme son propre groupe d'options, distinct du bus et de l'autocar. Décision de
# l'auteur du dépôt (2026-09-04), sur mesure : sur les 440 points où un itinéraire
# **ferroviaire direct** existe, 122 (27,7 %) le perdaient au profit d'un bus + train plus
# rapide, parce que les deux partageaient le groupe « transit ». L'agent ne voyait alors jamais
# le train comme un choix. La hiérarchie de l'enquête les distingue d'ailleurs : le bus et
# l'autocar sont au rang 4, le train régional au rang 8 (annexe p. 53).
GROUPE_RAIL = "transit:rail"


def _selection_group(plan: TravelPlan) -> str:
    """Clé de regroupement des options offertes à l'agent.

    C'est la catégorie de `_primary_mode`, **sauf** le collectif, qui se scinde en deux : le
    ferroviaire d'un côté, le reste du collectif de l'autre.

    Pourquoi seulement le train, et pas une clé par famille (métro, tram, téléphérique, bus,
    train). Parce que le plafond d'options est de 6, tenu à 6 par décision du 2026-09-04 : avec
    huit groupes possibles, la passe de priorité — qui prend le plus rapide de chaque groupe
    inédit, par durée croissante — pourrait remplir les six créneaux de variantes collectives et
    **écarter la voiture**, le vélo ou la marche. Avec cinq groupes (marche, vélo, voiture,
    collectif, ferroviaire), les cinq tiennent et il reste un créneau de remplissage.

    ⚠ Ne sert PAS aux métriques : `trip_mode_by_purpose` et les parts modales restent sur les
    quatre catégories de l'enquête, où le train est un transport collectif. Cette clé ne décide
    que de ce que l'agent a sous les yeux.
    """
    categorie = _primary_mode(plan)
    if categorie != "transit":
        return categorie
    modes = {(leg.mode or "").lower() for leg in plan.legs if not leg.is_transfer}
    return GROUPE_RAIL if MODE_HIERARCHY.primary_family(modes) == "rail" else categorie


def _select_candidates(itineraries: list[TravelPlan], max_n: int) -> list[TravelPlan]:
    """Cap to max_n itineraries, keeping the fastest plan per mode group first."""
    by_duration = sorted(itineraries, key=lambda p: p.duration or float("inf"))
    seen, priority, rest = set(), [], []
    for plan in by_duration:
        mode = _selection_group(plan)
        if mode not in seen:
            seen.add(mode)
            priority.append(plan)
        else:
            rest.append(plan)
    selected = priority[:max_n]
    for plan in rest:
        if len(selected) >= max_n:
            break
        selected.append(plan)
    return selected
