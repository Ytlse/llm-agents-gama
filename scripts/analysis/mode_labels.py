"""Libellés de mode de `moves.csv` : la table de détail, la table d'agrégation, et
l'alarme quand un libellé sort des deux.

POURQUOI CE MODULE EXISTE. La colonne « Mode de transport Choisi » porte des libellés
FINS (`Marche`, `Vélo`, `Voiture Privée`, `Transports_collectifs`, `Train`,
`Deux-roues motorisé`, `Autres modes`, `Aucun`), et les cibles de
`cerema_values.yaml` sont publiées par CATÉGORIE d'enquête (`marche`, `velo`,
`voiture`, `transports_collectifs`, `autres_modes`). Les deux niveaux sont utiles :
le détail dit ce que la simulation a produit, la catégorie dit à quoi le comparer.
Écraser le premier dans le second dès la lecture perd de l'information sans le dire.

Jusqu'au 2026-09-04, deux consommateurs ramenaient les libellés à quatre catégories
par une table INCOMPLÈTE, et jetaient en silence ce qu'elle ne connaissait pas :

* `audit_perimetre.MOVE_MODE_MAP` — pas d'entrée « Train » : un déplacement en train
  sortait de l'audit des parts modales par un `continue`, sans être compté ni signalé.
  Le dénominateur baissait, les parts des autres modes montaient, et rien ne le disait ;
* `scripts/analysis/selected_mode_stats.ipynb` — un `replace()` sans `Train`, sans
  `Deux-roues motorisé`, sans `Autres modes`, suivi d'un `reindex(mode_order)` qui les
  éliminait sans avertissement.

C'est le motif que ce dépôt traque : **l'absence de mesure produit le score parfait**.
Un mode qui disparaît du dénominateur ne fait pas apparaître d'erreur — il fait monter
les parts des modes restants, donc il déplace la note sans laisser de trace.

CE QUE LE MODULE GARANTIT.

1. **Rien ne se jette.** Chaque libellé lu tombe dans une catégorie ; un libellé hors
   table tombe dans `libelle_inconnu` — il est compté, nommé, et il alarme.
2. **L'invariant est vérifié, pas espéré** : la somme des effectifs détaillés et la
   somme des effectifs par catégorie valent toutes deux le nombre de lignes lues.
   `ModeTally.check()` alarme puis lève si l'égalité tombe.
3. **L'alarme est repérable par `make error`** : elle s'écrit en ERROR, préfixée
   `[ALARME]`, dans l'`app.log` du run analysé, au format que `scripts/errors.py`
   sait relire (`AAAA-MM-JJ HH:MM:SS | ERROR    | <logger> - <message>`). Un carnet
   Jupyter n'a pas de journal ; c'est la raison pour laquelle la logique de
   normalisation vit ici et non dans le carnet.

CE QUE LE MODULE NE FAIT PAS. Il ne décide pas de la HIÉRARCHIE des modes — quel mode
est principal quand un déplacement en mêle deux. C'est le ticket 022, et cela se joue
dans `move_logger._plan_transport_mode`, en amont du libellé que ce module lit.

Usage depuis un carnet de `scripts/analysis/` :

    import os, sys; sys.path.append(os.getcwd())
    from mode_labels import normalize_column, tally_labels

Usage depuis un script du dépôt :

    from scripts.analysis.mode_labels import normalize_labels, tally_labels
"""

from __future__ import annotations

import logging
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]

# Colonnes de `moves.csv` qui portent un libellé de mode.
MODE_COLUMN = "Mode de transport Choisi"
FASTEST_COLUMN = "Plus rapide"
MODE_COLUMNS = (MODE_COLUMN, FASTEST_COLUMN)

# ── Les deux niveaux de lecture ───────────────────────────────────────────────

# Catégories de l'enquête, telles que `cerema_values.yaml` les publie. `autres_modes`
# est le résidu de la référence (2 à 5 points selon la strate) : c'est une catégorie
# de l'enquête, pas un fourre-tout pour les libellés qu'on ne sait pas lire.
SURVEY_CATEGORIES = ("marche", "velo", "voiture", "transports_collectifs",
                     "autres_modes")

# Les quatre catégories effectivement scorées (celles sur lesquelles le L1 est calculé).
SCORED_CATEGORIES = ("voiture", "marche", "transports_collectifs", "velo")

# Trois catégories qui ne sont PAS des catégories d'enquête, et qui existent pour que
# rien ne se jette. Elles sortent des parts modales — un non-déplacement n'est pas un
# déplacement — mais elles sont comptées et publiées, comme `hors périmètre` l'est pour
# les couronnes depuis le ticket 021.
NON_TRIP = "non_deplacement"        # « Aucun » : même localisation, l'agent n'a pas bougé
NO_LABEL = "sans_libelle"           # cellule vide : aucun plan (colonne « Plus rapide »)
UNKNOWN = "libelle_inconnu"         # hors table : le défaut que ce module rend bruyant

OUT_OF_SURVEY_CATEGORIES = (NON_TRIP, NO_LABEL, UNKNOWN)

# ── La table d'agrégation ─────────────────────────────────────────────────────
# Libellé fin (tel qu'écrit dans `moves.csv`) → catégorie. L'ordre fixe l'ordre
# d'affichage du détail.
#
# D'OÙ VIENNENT LES LIBELLÉS. De `llm_module.core.mode_hierarchy` (ticket 022), qui est
# le seul endroit du dépôt où les libellés de la colonne « Mode de transport Choisi »
# sont décidés — `move_logger._CANONICAL_FR` les lit là aussi. Cette table ne les
# recopie pas pour le plaisir : elle y ajoute la DÉCISION D'AGRÉGATION, que la
# hiérarchie ne porte pas et refuse de porter (« c'est une agrégation, pas une
# hiérarchie »). `check_covers_hierarchy()` confronte les deux à chaque comptage, et
# une famille de la hiérarchie sans entrée ici lève une [ALARME] : c'est ce contrôle,
# et non la vigilance, qui empêche le prochain « Train ».
#
# Les deux dernières entrées sont les valeurs que `move_logger` écrit HORS de la
# hiérarchie : « Aucun » (non-déplacement) et la cellule vide (aucun plan).
AGGREGATION: dict[str, str] = {
    "Marche": "marche",
    "Vélo": "velo",
    "Voiture Privée": "voiture",
    "Transports_collectifs": "transports_collectifs",
    # Le train est un mode collectif : l'enquête le range en transports collectifs
    # (`frames.CHOSEN_MODE_MAP["Train"]`, `calibration.metrics.categorize_mode`). Le
    # détail le garde distinct, l'agrégation le fond — c'est tout l'objet des deux niveaux.
    "Train": "transports_collectifs",
    # Deux-roues motorisés et « autres » forment le résidu `autres_modes` de la
    # référence EMC². Ils sortent des quatre catégories scorées, mais dans la référence,
    # pas par oubli.
    "Deux-roues motorisé": "autres_modes",
    "Autres modes": "autres_modes",
    # Écrit par `move_logger` quand `selection_method` vaut « Pas de déplacement (même
    # localisation) » : l'agent n'a pas bougé. Ce n'est pas un déplacement, donc pas une
    # part modale — mais 9,8 % des lignes du run `2026-09-04_01_09` (521 sur 5 322).
    "Aucun": NON_TRIP,
    # `_plan_transport_mode(None)` : aucun itinéraire. Fréquent dans « Plus rapide »
    # (554 lignes sur 5 322), inexistant dans « Mode de transport Choisi ».
    "": NO_LABEL,
}

# Ordre d'affichage du détail.
DETAIL_ORDER = tuple(AGGREGATION)

# Libellés qui comptent comme un déplacement (ceux qui entrent dans une part modale).
TRIP_LABELS = tuple(label for label, cat in AGGREGATION.items()
                    if cat in SURVEY_CATEGORIES)

_LOGGER_NAME = "scripts.analysis.mode_labels"
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s - %(message)s"
_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG = REPO_ROOT / "experiments" / "current" / "app.log"


class ModeTallyError(AssertionError):
    """L'invariant de comptage est rompu — un effectif s'est perdu en route."""


# ── Le contrôle de couverture contre la hiérarchie des modes ──────────────────

def check_covers_hierarchy() -> str:
    """Rend "" si la table couvre tous les libellés de journal de la hiérarchie EMC².

    Sinon rend la RAISON, prête à être alarmée. Ne lève pas : l'appelant décide quoi
    faire d'un écart (l'audit en fait un verdict « à corriger », le carnet le crie).

    Trois cas, et ils ne se confondent pas :
      * hiérarchie lisible et couverte → "" ;
      * hiérarchie lisible et un libellé non couvert → la raison. C'est le défaut qu'on
        corrige : une famille de modes ajoutée en amont sortirait des parts modales ;
      * hiérarchie illisible (ressource absente, version inattendue) → une raison AUSSI.
        Un contrôle qui n'a pas pu tourner n'est pas un contrôle vert — « un axe non
        mesuré est un axe qui passe » vaut aussi pour les contrôles.
    """
    try:
        from llm_module.core.mode_hierarchy import hierarchy
    except ImportError as exc:                            # pragma: no cover
        return (f"hiérarchie des modes non importable ({exc}) : la couverture de la "
                f"table d'agrégation n'a PAS été vérifiée.")
    try:
        labels = dict(hierarchy().journal_label)
    except (OSError, ValueError) as exc:
        return (f"hiérarchie des modes illisible ({exc}) : la couverture de la table "
                f"d'agrégation n'a PAS été vérifiée.")
    manquants = sorted({label for label in labels.values()
                        if label not in AGGREGATION})
    if not manquants:
        return ""
    familles = {label: sorted(f for f, l in labels.items() if l == label)
                for label in manquants}
    return (f"libellé(s) de la hiérarchie des modes absent(s) de la table "
            f"d'agrégation : {familles} — les déplacements qui les portent sortiraient "
            f"des parts modales. Ajouter ces libellés à "
            f"scripts/analysis/mode_labels.AGGREGATION.")


_HIERARCHY_ALARMED = False


def _alarm_hierarchy_once(log_dir: Optional[Path] = None) -> str:
    """Alarme une seule fois par processus sur un écart de couverture (front montant)."""
    global _HIERARCHY_ALARMED
    reason = check_covers_hierarchy()
    if reason and not _HIERARCHY_ALARMED:
        _HIERARCHY_ALARMED = True
        log_alarm(f"[ALARME] {reason}", log_dir=log_dir)
    return reason


def category_of(label: Any) -> Optional[str]:
    """Catégorie d'un libellé fin, ou `None` s'il est hors table.

    `None` est un résultat, pas une absence de résultat : l'appelant doit le compter.
    """
    return AGGREGATION.get(_clean(label))


# Écritures d'une cellule VIDE selon le lecteur : le module csv rend `""`, pandas rend
# `NaN` (`str(nan) == "nan"`), une colonne nullable rend `pd.NA` (`"<NA>"`). Les trois
# désignent la même chose — aucun libellé — et doivent tomber dans `sans_libelle`, pas
# dans `libelle_inconnu` : une alarme qui se déclenche sur 554 cellules vides de « Plus
# rapide » serait une alarme qu'on apprend à ignorer. Aucun mode ne s'appelle « nan ».
_MISSING_REPRS = frozenset({"", "nan", "none", "<na>", "nat", "null", "na"})


def _clean(label: Any) -> str:
    if label is None:
        return ""
    text = str(label).strip()
    return "" if text.lower() in _MISSING_REPRS else text


# ── Comptage ──────────────────────────────────────────────────────────────────

@dataclass
class ModeTally:
    """Le détail par libellé, sa projection par catégorie, et les inconnus nommés.

    `detail` porte les libellés BRUTS tels que lus (inconnus compris), `categories` la
    projection par la table d'agrégation, `unknown` les seuls libellés hors table.
    Les deux premières sommes valent `total` : c'est l'invariant que `check()` vérifie.
    """

    detail: Counter = field(default_factory=Counter)
    categories: Counter = field(default_factory=Counter)
    unknown: Counter = field(default_factory=Counter)
    total: int = 0
    source: str = ""
    # "" si la table d'agrégation couvre la hiérarchie des modes du dépôt ; sinon la
    # raison, déjà alarmée. Un écart ici est un défaut LATENT : il ne se voit pas dans
    # les données de ce run, il se verra au premier run qui portera le mode manquant.
    hierarchy_gap: str = ""

    @property
    def n_unknown(self) -> int:
        """Effectif concerné par un libellé hors table (pas le nombre de libellés)."""
        return sum(self.unknown.values())

    @property
    def n_trips(self) -> int:
        """Effectif qui compte comme un déplacement (base des parts modales)."""
        return sum(n for cat, n in self.categories.items()
                   if cat in SURVEY_CATEGORIES)

    def shares(self, categories: Iterable[str] = SCORED_CATEGORIES) -> dict[str, float]:
        """Parts modales (%) sur les catégories demandées, dénominateur = ces catégories.

        Le dénominateur est explicite et restreint aux catégories passées : c'est ce qui
        rend la part comparable à une cible publiée sur les mêmes catégories.
        """
        wanted = tuple(categories)
        base = sum(self.categories.get(c, 0) for c in wanted)
        if not base:
            return {c: 0.0 for c in wanted}
        return {c: 100.0 * self.categories.get(c, 0) / base for c in wanted}

    def detail_rows(self) -> list[dict]:
        """Détail par libellé, ordre de `DETAIL_ORDER` puis inconnus, avec sa catégorie."""
        rows = []
        seen = set()
        for label in DETAIL_ORDER:
            if self.detail.get(label):
                rows.append({"libelle": label or "(vide)",
                             "categorie": AGGREGATION[label],
                             "n": self.detail[label],
                             "part_pct": 100.0 * self.detail[label] / self.total
                             if self.total else 0.0})
                seen.add(label)
        for label, n in sorted(self.unknown.items(), key=lambda kv: -kv[1]):
            if label in seen:
                continue
            rows.append({"libelle": label or "(vide)", "categorie": UNKNOWN, "n": n,
                         "part_pct": 100.0 * n / self.total if self.total else 0.0})
        return rows

    def check(self, log_dir: Optional[Path] = None) -> None:
        """Vérifie l'égalité des totaux — alarme PUIS lève. Jamais un simple espoir.

        L'égalité ne peut tomber que sur un bug de ce module (un libellé compté d'un
        côté et pas de l'autre). C'est exactement pour ça qu'elle est vérifiée : un
        effectif perdu ici est un effectif retiré d'un dénominateur, donc une part
        modale fausse et plausible.
        """
        detail_sum = sum(self.detail.values())
        category_sum = sum(self.categories.values())
        if detail_sum == self.total == category_sum:
            return
        message = (
            f"[ALARME] {self.source or 'mode_labels'} : invariant de comptage rompu — "
            f"{self.total} ligne(s) lue(s), {detail_sum} en détail, {category_sum} "
            f"en catégories. Un effectif perdu ici sort d'un dénominateur de part "
            f"modale sans laisser de trace.")
        log_alarm(message, log_dir=log_dir)
        raise ModeTallyError(message)


def tally_labels(labels: Iterable[Any], source: str = "",
                 log_dir: Optional[Path] = None, alarm: bool = True) -> ModeTally:
    """Compte des libellés de mode : détail, catégories, inconnus — sans rien jeter.

    `source` nomme l'origine (fichier + colonne) : il apparaît dans l'alarme, qui doit
    dire OÙ chercher. `alarm=False` sert aux tests qui vérifient le comptage sans
    écrire dans un journal.
    """
    tally = ModeTally(source=source)
    for raw in list(labels):
        label = _clean(raw)
        tally.total += 1
        tally.detail[label] += 1
        category = AGGREGATION.get(label)
        if category is None:
            tally.unknown[label] += 1
            tally.categories[UNKNOWN] += 1
        else:
            tally.categories[category] += 1
    tally.check(log_dir=log_dir)
    if alarm:
        alarm_unknown(tally, log_dir=log_dir)
        tally.hierarchy_gap = _alarm_hierarchy_once(log_dir=log_dir)
    else:
        tally.hierarchy_gap = check_covers_hierarchy()
    return tally


def normalize_labels(labels: Iterable[Any], source: str = "",
                     log_dir: Optional[Path] = None,
                     alarm: bool = True) -> tuple[list[str], ModeTally]:
    """Libellés fins → catégories, avec le comptage qui va avec.

    Un libellé hors table devient `libelle_inconnu` — il reste dans la série, visible,
    au lieu d'être remplacé par `NaN` puis éliminé par un `reindex`.
    """
    values = list(labels)
    tally = tally_labels(values, source=source, log_dir=log_dir, alarm=alarm)
    return [AGGREGATION.get(_clean(v), UNKNOWN) for v in values], tally


# ── Interface pandas (les carnets) ────────────────────────────────────────────

def normalize_column(frame, column: str = MODE_COLUMN, source: str = "",
                     log_dir: Optional[Path] = None, alarm: bool = True):
    """Normalise UNE colonne de libellés vers les catégories d'enquête, en place.

    Rend le `ModeTally` de la colonne : l'appelant peut alors publier le détail, la
    part par catégorie, et ce qui est sorti des parts modales. `pandas` n'est importé
    que par cette porte — le module reste utilisable sans lui.
    """
    if column not in frame.columns:
        raise KeyError(f"colonne absente de la table : {column!r}")
    values = list(frame[column])
    tally = tally_labels(values, source=source or column, log_dir=log_dir, alarm=alarm)
    frame[column] = [AGGREGATION.get(_clean(v), UNKNOWN) for v in values]
    return tally


def normalize_move_columns(frame, columns: Iterable[str] = MODE_COLUMNS,
                           source: str = "moves.csv",
                           log_dir: Optional[Path] = None,
                           alarm: bool = True) -> dict[str, ModeTally]:
    """Normalise toutes les colonnes de mode présentes ; rend un `ModeTally` par colonne.

    Une colonne absente est ignorée SANS erreur (les runs anciens n'ont pas toutes les
    colonnes), mais elle n'est pas silencieuse : elle est absente du dictionnaire rendu,
    et l'appelant peut le constater.
    """
    out: dict[str, ModeTally] = {}
    for column in columns:
        if column in frame.columns:
            out[column] = normalize_column(
                frame, column, source=f"{source} · {column}", log_dir=log_dir,
                alarm=alarm)
    return out


def missing_from(tally: ModeTally,
                 kept: Iterable[str] = SCORED_CATEGORIES) -> dict[str, int]:
    """Ce qu'un affichage restreint à `kept` laisse dehors — nommé et chiffré.

    À imprimer à côté de tout graphique construit sur `mode_order` : un camembert des
    quatre catégories scorées cache tout le reste, et « caché » doit rester « dit ».
    """
    keep = set(kept)
    return {cat: n for cat, n in sorted(tally.categories.items(), key=lambda kv: -kv[1])
            if cat not in keep and n}


# ── L'alarme ──────────────────────────────────────────────────────────────────

def resolve_log_path(log_dir: Optional[Path] = None) -> Path:
    """`app.log` du run analysé, sinon celui de `experiments/current`.

    L'alarme s'écrit dans le journal du run qu'elle concerne : `make error` le lit sans
    argument pour le run courant (`experiments/current` est un lien vers le dernier
    run), et `make error LOG=experiments/archive/<run>/app.log` pour un run archivé.
    """
    override = os.environ.get("MODE_LABELS_LOG")
    if override:
        return Path(override)
    if log_dir is not None:
        candidate = Path(log_dir)
        if candidate.name == "app.log":
            return candidate
        if candidate.is_dir():
            return candidate / "app.log"
    return DEFAULT_LOG


def _logger(path: Path, name: str = _LOGGER_NAME) -> logging.Logger:
    """Logger dédié, un handler par fichier, jamais propagé à la racine.

    Le format reproduit celui de `helper.setup_logging` (loguru) parce que
    `scripts/errors.py` le relit par expression régulière : un format différent
    produirait une alarme invisible de `make error`, donc une alarme inutile.

    `name` est le nom AFFICHÉ dans le journal : il doit désigner l'émetteur réel de
    l'alarme (l'audit, un carnet), sinon `make error` renvoie tout le monde ici.
    """
    logger = logging.getLogger(f"{name}[{path}]")
    logger.name = name
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    target = str(path)
    for handler in logger.handlers:
        if getattr(handler, "_mode_labels_target", None) == target:
            return logger
    handler: logging.Handler
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")
    except OSError:
        # Fail-open : une alarme qui ne peut pas s'écrire dans le journal doit
        # quand même se voir. Elle part sur stderr plutôt que de faire tomber
        # l'analyse qui l'a produite.
        handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATEFMT))
    handler._mode_labels_target = target  # type: ignore[attr-defined]
    logger.addHandler(handler)
    return logger


def log_alarm(message: str, log_dir: Optional[Path] = None,
              logger_name: str = _LOGGER_NAME) -> Path:
    """Écrit une ligne ERROR `[ALARME]` là où `make error` la lira, et sur stderr."""
    path = resolve_log_path(log_dir)
    try:
        _logger(path, logger_name).error(message)
    except Exception:  # pragma: no cover - fail-open, jamais bloquant
        pass
    print(message, file=sys.stderr)
    return path


def alarm_unknown(tally: ModeTally, log_dir: Optional[Path] = None) -> Optional[str]:
    """Alarme si des libellés sortent de la table d'agrégation ; rend la ligne écrite.

    Front montant par nature : une alarme par comptage, pas une par ligne lue.
    """
    if not tally.unknown:
        return None
    named = ", ".join(f"« {label or '(vide)'} » ({n})"
                      for label, n in sorted(tally.unknown.items(),
                                             key=lambda kv: (-kv[1], kv[0])))
    share = 100.0 * tally.n_unknown / tally.total if tally.total else 0.0
    message = (
        f"[ALARME] {len(tally.unknown)} libellé(s) de mode hors table d'agrégation "
        f"dans {tally.source or 'mode_labels'} : {named} — "
        f"{tally.n_unknown}/{tally.total} ligne(s) ({share:.1f} %) comptées en "
        f"« {UNKNOWN} », hors de toute part modale. "
        f"Corriger scripts/analysis/mode_labels.AGGREGATION.")
    log_alarm(message, log_dir=log_dir)
    return message


def aggregation_table() -> list[dict]:
    """La table d'agrégation elle-même, pour la publier à côté du détail.

    Publier la table, et pas seulement son résultat, est ce qui permet de recomposer
    l'agrégat depuis le détail — donc de vérifier l'agrégation au lieu de la croire.
    """
    return [{"libelle": label or "(vide)", "categorie": category,
             "dans_les_parts_modales": category in SURVEY_CATEGORIES,
             "scoree": category in SCORED_CATEGORIES}
            for label, category in AGGREGATION.items()]


if __name__ == "__main__":
    import csv

    target = Path(sys.argv[1] if len(sys.argv) > 1
                  else REPO_ROOT / "experiments" / "current" / "moves.csv")
    with target.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for column in MODE_COLUMNS:
        if not rows or column not in rows[0]:
            continue
        t = tally_labels((r.get(column) for r in rows),
                         source=f"{target.name} · {column}",
                         log_dir=target.parent)
        print(f"\n{column} — {t.total} ligne(s), {t.n_trips} déplacement(s)")
        for row in t.detail_rows():
            print(f"   {row['libelle']:24s} → {row['categorie']:22s} "
                  f"{row['n']:6d}  {row['part_pct']:5.1f} %")
        print("   parts modales scorées : "
              + " · ".join(f"{k} {v:.1f} %" for k, v in t.shares().items()))
        out = missing_from(t)
        if out:
            print("   hors parts modales : "
                  + " · ".join(f"{k} {v}" for k, v in out.items()))
