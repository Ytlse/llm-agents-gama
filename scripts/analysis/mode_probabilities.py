"""Lecture des probabilités de mode de `moves.csv` (choix modal probabiliste).

Depuis la bascule vers les probabilités, le LLM n'élit plus un itinéraire : il note
chaque option, et l'agent tire son mode dans la distribution obtenue. `moves.csv` porte
donc, en plus du mode retenu, **une colonne par mode** (`P(Marche) %`, `P(Vélo) %`, …).

Deux lectures possibles, à ne pas confondre :

- **part attendue** — moyenne des probabilités annoncées : ce que le modèle « voulait » ;
- **part tirée** — comptage des modes effectivement retenus : ce que la simulation a fait.

La seconde reproduit la première en espérance. Un écart franc et durable ne vient donc
pas du modèle mais du tirage, du cache (points hérités resservis sans tirage) ou d'un
biais de normalisation — c'est le seul usage vraiment diagnostique de ces colonnes.

⚠ Les deux parts ne portent pas sur la même population : les décisions sans répartition
(mono-choix, absence d'itinéraire, erreur LLM, point de cache hérité) comptent dans la
part tirée mais sont absentes de la part attendue. `expected_vs_drawn` les exclut des
deux côtés par défaut — c'est ce qui rend la comparaison honnête.

Usage en notebook :

    import sys; sys.path.append("..")          # depuis scripts/analysis/
    from mode_probabilities import load_moves, expected_vs_drawn
    df = load_moves("experiments/current/moves.csv")
    expected_vs_drawn(df)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

# Colonne du mode effectivement retenu (vocabulaire de move_logger).
MODE_COLUMN = "Mode de transport Choisi"
METHOD_COLUMN = "Méthode de sélection"

# Palette officielle du projet (cf. .claude/CLAUDE.md) — à passer aux graphiques pour
# rester cohérent avec GAMA et Grafana.
MODE_COLORS = {
    "Marche": "cyan",
    "Vélo": "purple",
    "Voiture Privée": "red",
    "Transports_collectifs": "green",
    "Train": "purple",
    "Deux-roues motorisé": "magenta",
    "Autres modes": "grey",
}


def probability_columns(df: pd.DataFrame) -> list[str]:
    """Colonnes `P(<mode>) %` présentes dans le CSV (vide sur un run pré-bascule)."""
    return [c for c in df.columns if c.startswith("P(") and c.endswith(") %")]


def mode_of(column: str) -> str:
    """`P(Marche) %` → `Marche`."""
    return column[2:-3]


def load_moves(path: str | Path) -> pd.DataFrame:
    """Charge `moves.csv` en typant les colonnes de probabilité en flottants.

    Les cellules vides restent `NaN` : elles signifient « décision sans répartition »,
    ce qui n'est **pas** la même chose qu'un 0 (« mode explicitement écarté »).
    """
    df = pd.read_csv(path)
    for col in probability_columns(df):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def has_distribution(df: pd.DataFrame) -> pd.Series:
    """Masque des décisions issues d'un tirage (au moins une probabilité renseignée)."""
    cols = probability_columns(df)
    if not cols:
        return pd.Series(False, index=df.index)
    return df[cols].notna().any(axis=1)


def expected_share(df: pd.DataFrame, only_probabilistic: bool = True) -> pd.Series:
    """Part modale **attendue** (%), moyenne des probabilités annoncées."""
    cols = probability_columns(df)
    if not cols:
        return pd.Series(dtype=float)
    sub = df[has_distribution(df)] if only_probabilistic else df
    if sub.empty:
        return pd.Series(dtype=float)
    return sub[cols].mean().rename(index=mode_of).sort_values(ascending=False)


def drawn_share(df: pd.DataFrame, only_probabilistic: bool = True) -> pd.Series:
    """Part modale **tirée** (%), comptage des modes effectivement retenus."""
    sub = df[has_distribution(df)] if only_probabilistic else df
    if sub.empty or MODE_COLUMN not in sub.columns:
        return pd.Series(dtype=float)
    return 100 * sub[MODE_COLUMN].value_counts(normalize=True)


def expected_vs_drawn(df: pd.DataFrame, only_probabilistic: bool = True) -> pd.DataFrame:
    """Table `attendu / tiré / écart` (points de %), triée par écart décroissant.

    `only_probabilistic=False` compare la part attendue aux modes de **tous** les
    trajets, mono-choix compris — utile pour la part modale globale du run, trompeur
    pour diagnostiquer le tirage.
    """
    exp = expected_share(df, only_probabilistic)
    got = drawn_share(df, only_probabilistic)
    if exp.empty:
        return pd.DataFrame(columns=["attendu %", "tiré %", "écart (pts)"])
    out = pd.DataFrame({"attendu %": exp, "tiré %": got}).fillna(0.0)
    out["écart (pts)"] = out["tiré %"] - out["attendu %"]
    return out.reindex(out["écart (pts)"].abs().sort_values(ascending=False).index)


def hesitation(df: pd.DataFrame) -> pd.Series:
    """Indice d'hésitation par décision : `1 − p_max` (0 = certitude, ~0.8 = indécision).

    Information inaccessible avant la bascule : elle distingue un persona pour qui la
    voiture est une évidence d'un persona qui aurait aussi bien pu prendre le bus.
    """
    cols = probability_columns(df)
    if not cols:
        return pd.Series(dtype=float)
    return 1 - df[cols].max(axis=1) / 100.0


def summary(path: str | Path, only_probabilistic: bool = True) -> pd.DataFrame:
    """Raccourci : charge un `moves.csv` et renvoie la table attendu/tiré."""
    return expected_vs_drawn(load_moves(path), only_probabilistic)


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "experiments/current/moves.csv"
    frame = load_moves(target)
    n = int(has_distribution(frame).sum())
    print(f"{len(frame)} trajets, dont {n} issus d'un tirage probabiliste\n")
    print(expected_vs_drawn(frame).round(1).to_string())
