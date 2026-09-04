"""
core/mode_hierarchy.py — Le mode principal d'un déplacement, une fois pour tout le dépôt.

Un déplacement qui mêle plusieurs modes reçoit **un** mode principal. Le dépôt en portait
quatre tables et trois réponses pour le même trajet — un car liO + TER était
`Transports_collectifs` dans `moves.csv`, `train` dans la répartition, `train` dans les
compteurs du worker et `transit` dans la métrique Prometheus (ticket 022, M1). Ce module
est **le seul endroit** où l'ordre est écrit, et il ne l'écrit pas : il le lit dans
`llm_module/data/mode_hierarchy_emc2.json`, gelé par
`scripts/progedo_logit/export_mode_hierarchy.py`.

## D'OÙ VIENT L'ORDRE

Du rapport publié de l'enquête : AUAT/CEREMA, « Enquête mobilité 2023 — bassin de vie
toulousain », annexe « Hiérarchie des modes », **p. 53**, qui donne les 36 modes enquêtés
dans l'ordre, « défini au niveau national » (p. 12). Il est **contrôlé sur les
microdonnées** — 53 paires de codes tranchées par 2 607 observations, une seule exception,
et elle est conforme à l'annexe (un Flixbus, rang 12, perd contre un TER, rang 8).

Ramené au vocabulaire des jambes que produisent OTP, OSMnx et le car scolaire :

    1. metro   2. tram   3. cableway   4. bus   5. rail
    6. car     7. motorbike   8. bicycle   9. foot

## LES DEUX CRANS QUI SURPRENNENT, ET CE QU'ILS CHANGENT

**Le bus passe avant le train.** Un itinéraire « autocar liO + TER » est un déplacement en
*bus* pour l'enquête : sur 35 déplacements mixtes bus/car ↔ train tranchés, 34 sont codés
bus. La cascade de `move_logger` avait donc raison sur ce point ; ce sont `mode_choice`
(train en tête) et `task_worker` (train en tête) qui divergeaient.

**La voiture passe après tout le collectif** (rang 19, sous les rangs 1 à 13). Sur 770
déplacements mêlant voiture et transports collectifs, l'enquête en code 760 en collectif et
10 en voiture. `move_logger` testait la voiture **en premier** : c'était l'inversion.

## CE QUE CE MODULE NE FAIT PAS

Il ne répond pas à la question « ce plan utilise-t-il la voiture ? ». Un mode principal et
un mode de véhicule sont deux grandeurs différentes : la chaîne de véhicules du ticket 008
demande « où est la voiture », pas « quel est le mode principal ». Les confondre a produit
la moitié du ticket 022 ; `simulation_controller._vehicle_mode` garde donc sa propre
lecture, et elle ne passe pas par ici.

Il ne connaît pas non plus les catégories de score EMC² (`marche` / `voiture` / `velo` /
`transports_collectifs`) : c'est une agrégation, pas une hiérarchie, et elle vit dans
`scripts/synthesis/frames.py` et `prompt_calibration/calibration/metrics.py`. Ce module
leur fournit seulement de quoi vérifier qu'elles ne contredisent pas l'ordre de l'enquête.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping, Optional

DEFAULT_RESOURCE = Path(__file__).resolve().parents[1] / "data" / "mode_hierarchy_emc2.json"

# Version de ressource exigée. Une ressource plus ancienne (ou faite à la main) ne porte
# pas le contrôle sur microdonnées : on refuse plutôt que de servir un ordre non recoupé.
REQUIRED_VERSION = "mh1"

# Familles attendues dans la ressource. Une famille en moins et le mode qu'elle porte
# tomberait silencieusement dans « inconnu » — le motif de vacuité que le dépôt traque.
REQUIRED_FAMILIES = ("metro", "tram", "cableway", "bus", "rail", "car", "motorbike",
                     "bicycle", "foot")


@dataclass(frozen=True)
class ModeHierarchy:
    """La hiérarchie chargée : rangs, libellés, et les deux vocabulaires qu'elle dessert.

    `families` est l'ordre publié, du plus prioritaire au moins prioritaire.
    `leg_rank` va d'un mode de jambe (`"bus"`, `"rail"`, `"__car__"`…) à son rang.
    `journal_label` et `canonical_mode` traduisent une famille dans les deux vocabulaires
    du dépôt : la colonne « Mode de transport Choisi » de `moves.csv` et
    `mode_choice.CANONICAL_MODES`.
    """

    families: tuple[str, ...]
    family_rank: Mapping[str, int]
    leg_rank: Mapping[str, int]
    journal_label: Mapping[str, str]
    canonical_mode: Mapping[str, str]
    legs_by_family: Mapping[str, frozenset[str]]
    meta: dict = field(default_factory=dict)

    # ── Chargement ───────────────────────────────────────────────────────────────

    @classmethod
    def load(cls, resource: Optional[Path] = None) -> "ModeHierarchy":
        """Charge la ressource gelée (seul point d'I/O du module).

        Absence ou version inattendue = erreur explicite. Un repli sur un ordre écrit en
        dur ici ramènerait le littéral que ce module existe pour supprimer.
        """
        path = Path(resource) if resource else DEFAULT_RESOURCE
        if not path.exists():
            raise FileNotFoundError(
                f"Hiérarchie des modes absente : {path}. Produisez-la avec "
                "`python -m scripts.progedo_logit.export_mode_hierarchy` (microdonnées "
                "ProGEDO lil-1750, accès restreint) — la ressource est normalement "
                "versionnée dans le dépôt.")
        doc = json.loads(path.read_text(encoding="utf-8"))
        version = str(doc.get("version") or "")
        if version != REQUIRED_VERSION:
            raise ValueError(
                f"Hiérarchie {path} en version {version!r}, or le module exige "
                f"{REQUIRED_VERSION!r}. Ré-exportez-la.")
        families = tuple(doc.get("ordre_familles") or ())
        manquantes = [f for f in REQUIRED_FAMILIES if f not in families]
        if manquantes:
            raise ValueError(
                f"Hiérarchie {path} sans les familles {manquantes} : les modes qu'elles "
                "portent seraient classés « inconnu » sans que rien ne le signale.")
        leg_rank = {str(k): int(v) for k, v in (doc.get("rang_jambe") or {}).items()}
        if not leg_rank:
            raise ValueError(f"Hiérarchie {path} sans aucun mode de jambe : elle ne "
                             "classerait rien du tout.")
        return cls(
            families=families,
            family_rank={str(k): int(v) for k, v in (doc.get("rang_famille") or {}).items()},
            leg_rank=leg_rank,
            journal_label=dict(doc.get("libelle_journal") or {}),
            canonical_mode=dict(doc.get("mode_canonique") or {}),
            legs_by_family={k: frozenset(v)
                            for k, v in (doc.get("jambes_par_famille") or {}).items()},
            meta={"version": version, "titre": doc.get("titre"),
                  "source_publiee": {k: v for k, v in
                                     (doc.get("source_publiee") or {}).items()
                                     if k in ("rapport", "url", "page")},
                  "provenance": doc.get("provenance") or {}},
        )

    # ── Lecture ──────────────────────────────────────────────────────────────────

    def family_of(self, leg_mode: object) -> Optional[str]:
        """Famille d'un mode de jambe. `None` pour un mode que la hiérarchie ignore.

        `None` est une réponse, pas un défaut : un mode inconnu doit être **compté** et
        signalé par l'appelant, jamais rangé d'office dans le fourre-tout d'à côté.
        """
        mode = str(leg_mode or "").strip().lower()
        if not mode:
            return None
        rank = self.leg_rank.get(mode)
        if rank is None:
            return None
        return self.families[rank - 1]

    def primary_family(self, leg_modes: Iterable[object]) -> Optional[str]:
        """Famille du **mode principal** d'un jeu de modes de jambes.

        C'est la famille de meilleur rang présente. `None` quand aucun mode n'est reconnu
        (jeu vide, ou modes tous inconnus) — à l'appelant de le compter.
        """
        best: Optional[int] = None
        for leg_mode in leg_modes:
            rank = self.leg_rank.get(str(leg_mode or "").strip().lower())
            if rank is not None and (best is None or rank < best):
                best = rank
        return None if best is None else self.families[best - 1]

    def primary_label(self, leg_modes: Iterable[object]) -> Optional[str]:
        """Libellé « Mode de transport Choisi » du mode principal, ou `None`."""
        family = self.primary_family(leg_modes)
        return None if family is None else self.journal_label.get(family)

    def primary_canonical(self, leg_modes: Iterable[object]) -> Optional[str]:
        """Mode canonique (`mode_choice.CANONICAL_MODES`) du mode principal, ou `None`."""
        family = self.primary_family(leg_modes)
        return None if family is None else self.canonical_mode.get(family)

    def canonical_order(self) -> tuple[str, ...]:
        """Modes canoniques dans l'ordre de la hiérarchie, sans doublon.

        C'est l'ordre que doit suivre la cascade de `mode_choice._MODE_KEYWORDS` :
        `public_transport` (métro, rang 1) avant `train` (rang 5) avant `car` (rang 6)…
        """
        ordre: list[str] = []
        for family in self.families:
            canonical = self.canonical_mode.get(family)
            if canonical and canonical not in ordre:
                ordre.append(canonical)
        return tuple(ordre)

    def label_order(self) -> tuple[str, ...]:
        """Libellés de journal dans l'ordre de la hiérarchie, sans doublon."""
        ordre: list[str] = []
        for family in self.families:
            label = self.journal_label.get(family)
            if label and label not in ordre:
                ordre.append(label)
        return tuple(ordre)


@lru_cache(maxsize=1)
def hierarchy() -> ModeHierarchy:
    """La hiérarchie du dépôt, chargée une fois. Point d'entrée de tous les appelants."""
    return ModeHierarchy.load()


# ── Raccourcis, pour que les appelants n'aient pas à porter l'objet ──────────────

def leg_family(leg_mode: object) -> Optional[str]:
    return hierarchy().family_of(leg_mode)


def primary_family(leg_modes: Iterable[object]) -> Optional[str]:
    return hierarchy().primary_family(leg_modes)


def primary_label(leg_modes: Iterable[object]) -> Optional[str]:
    return hierarchy().primary_label(leg_modes)


def primary_canonical(leg_modes: Iterable[object]) -> Optional[str]:
    return hierarchy().primary_canonical(leg_modes)


def family_rank(family: str) -> Optional[int]:
    return hierarchy().family_rank.get(family)
