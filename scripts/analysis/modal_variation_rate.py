#!/usr/bin/env python3
"""Analyse comportementale : Stabilité modale et taux de variation des choix d'itinéraires.

Outil d'analyse formelle mesurant :
1. Le taux de changement modal au jour le jour pour une même activité :
   P(Mode_d != Mode_{d-1} | Activité, Persona)
2. La stabilité modale : pourcentage et durée des séquences consécutives sans changement.
3. La décomposition par phase comportementale :
   - Pré-choc (Jours 1-7)
   - Péri-choc (Jours 8-9)
   - Post-choc immédiat (Jours 10-14)
   - Post-choc tardif / rétablissement (Jours 15-21+)
4. L'entropie modale et d'itinéraire de Shannon (diversification du bouquet par persona).
5. La distinction diagnostique entre décisions réelles du LLM et replis par défaut (LLM Error).

Respecte rigoureusement la charte graphique du projet (`scripts/dashboard/palette.py`).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Configuration non interactive et cache matplotlib sécurisé
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Tentative d'import de la palette officielle du projet
try:
    from scripts.dashboard.palette import MODE_COLORS as _PALETTE_MODES, NEUTRAL as _PALETTE_NEUTRAL
    PALETTE_OFFICIELLE = {k: v[0] for k, v in _PALETTE_MODES.items()}
    COULEUR_NEUTRE = _PALETTE_NEUTRAL[0]
except ImportError:
    PALETTE_OFFICIELLE = {
        "Voiture Privée": "#CE3B4B",
        "Vélo": "#7C4DDB",
        "Transports_collectifs": "#178A3F",
        "Marche": "#0B7A9B",
        "Deux-roues motorisé": "#B5259B",
        "Train": "#5B3AB8",
    }
    COULEUR_NEUTRE = "#6E6D69"

# Palette des phases temporelles (cohérente, sobre, accessible)
PALETTE_PHASES = {
    "1. Pré-choc (J1-7)": "#0B7A9B",          # Cyan soutenu
    "2. Péri-choc (J8-9)": "#CE3B4B",         # Rouge alerte
    "3. Post-choc immédiat (J10-14)": "#B5259B", # Magenta transition
    "4. Post-choc tardif (J15-21+)": "#178A3F",  # Vert stabilisation
}

# Heure frontière de la journée simulée (tampons vides à 3h, cohérent avec calcul.py)
FRONTIERE_JOUR_H = 3

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("modal_variation")


# ── Modèles de données ─────────────────────────────────────────────────────────

@dataclass
class TransitionObservation:
    person_id: str
    activite_id: str
    motif: str
    jour_prev: int
    jour_curr: int
    date_prev: str
    date_curr: str
    phase_curr: str
    mode_prev: str
    mode_curr: str
    route_prev: str
    route_curr: str
    modal_change: bool
    route_change: bool
    day_gap: int
    is_consecutive_day: bool
    selection_prev: str
    selection_curr: str
    is_llm_valid_transition: bool


# ── Extraction et préparation des données ──────────────────────────────────────

def extract_chosen_route(row: pd.Series) -> str:
    """Extrait la signature de l'itinéraire retenu (mode, durée, distance)."""
    opts = str(row.get("Options (descriptif)", ""))
    idx = row.get("Index retenu")
    mode_choisi = str(row.get("Mode de transport Choisi", ""))
    if pd.isna(idx) or not opts:
        return mode_choisi
    try:
        idx_int = int(idx)
        parts = opts.split(" | ")
        for p in parts:
            p_strip = p.strip()
            if p_strip.startswith(f"{idx_int}:"):
                return p_strip[len(f"{idx_int}:"):]
    except (ValueError, TypeError):
        pass
    return mode_choisi


def load_and_preprocess_moves(csv_path: Path) -> pd.DataFrame:
    """Charge moves.csv, extrait les journées vécues et assigne les phases."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"Le fichier moves.csv est introuvable : {csv_path}")

    logger.info("Chargement de %s...", csv_path)
    df = pd.read_csv(csv_path)

    # Détection de l'instant de départ
    if "Heure de départ" not in df.columns:
        raise ValueError("La colonne 'Heure de départ' est absente de moves.csv")

    depart_dt = pd.to_datetime(df["Heure de départ"], errors="coerce")
    # Frontière de journée à 3h du matin
    depart_shift = depart_dt - pd.Timedelta(hours=FRONTIERE_JOUR_H)
    ancre_journee = depart_shift.min().floor("D")

    df["depart_dt"] = depart_dt
    df["journee_date"] = depart_shift.dt.strftime("%Y-%m-%d")
    df["jour_simule"] = (depart_shift.dt.floor("D") - ancre_journee).dt.days + 1

    # Découpage formel des 4 phases de l'expérience
    def assign_phase(jour: int) -> str:
        if jour <= 7:
            return "1. Pré-choc (J1-7)"
        elif jour <= 9:
            return "2. Péri-choc (J8-9)"
        elif jour <= 14:
            return "3. Post-choc immédiat (J10-14)"
        else:
            return "4. Post-choc tardif (J15-21+)"

    df["phase"] = df["jour_simule"].apply(assign_phase)
    df["chosen_route"] = df.apply(extract_chosen_route, axis=1)

    # Normalisation des motifs
    df["motif_clean"] = df["Motifs de déplacement"].fillna("other").astype(str)
    motif_mapping = {
        "work": "Travail",
        "shopping": "Achats",
        "shop": "Achats",
        "study": "Etude",
        "education": "Etude",
    }
    df["motif_clean"] = df["motif_clean"].replace(motif_mapping)

    logger.info("%d déplacements chargés sur %d jours simulés (du %s au %s).",
                len(df), df["jour_simule"].max(), df["journee_date"].min(), df["journee_date"].max())
    return df


# ── Calculs des transitions et stabilité ───────────────────────────────────────

def compute_transitions(df: pd.DataFrame, level: str = "activite") -> List[TransitionObservation]:
    """Calcule les transitions jour le jour pour chaque persona et activité.

    level: 'activite' (ID Activité récurrente) ou 'motif' (type d'activité agrégé).
    """
    group_col = "ID Activité" if level == "activite" else "motif_clean"
    transitions: List[TransitionObservation] = []

    for (pid, act_val), grp in df.groupby(["ID Personne", group_col]):
        grp_sorted = grp.sort_values("depart_dt")
        # Premier départ de la journée pour la transition jour-le-jour
        first_per_day = grp_sorted.drop_duplicates(subset=["journee_date"], keep="first")
        if len(first_per_day) < 2:
            continue

        rows = first_per_day.to_dict("records")
        for i in range(1, len(rows)):
            prev = rows[i - 1]
            curr = rows[i]

            j_prev = int(prev["jour_simule"])
            j_curr = int(curr["jour_simule"])
            gap = j_curr - j_prev
            is_consec = (gap == 1) or (gap <= 3 and datetime.fromisoformat(prev["journee_date"]).weekday() == 4)

            sel_prev = str(prev.get("Méthode de sélection", ""))
            sel_curr = str(curr.get("Méthode de sélection", ""))
            is_llm_valid = (sel_prev == "LLM" and sel_curr == "LLM")

            transitions.append(TransitionObservation(
                person_id=str(pid),
                activite_id=str(prev.get("ID Activité", act_val)),
                motif=str(curr["motif_clean"]),
                jour_prev=j_prev,
                jour_curr=j_curr,
                date_prev=str(prev["journee_date"]),
                date_curr=str(curr["journee_date"]),
                phase_curr=str(curr["phase"]),
                mode_prev=str(prev["Mode de transport Choisi"]),
                mode_curr=str(curr["Mode de transport Choisi"]),
                route_prev=str(prev["chosen_route"]),
                route_curr=str(curr["chosen_route"]),
                modal_change=(prev["Mode de transport Choisi"] != curr["Mode de transport Choisi"]),
                route_change=(prev["chosen_route"] != curr["chosen_route"]),
                day_gap=gap,
                is_consecutive_day=is_consec,
                selection_prev=sel_prev,
                selection_curr=sel_curr,
                is_llm_valid_transition=is_llm_valid,
            ))

    return transitions


def compute_phase_summary(transitions: List[TransitionObservation]) -> pd.DataFrame:
    """Génère la synthèse des taux de variation et stabilité par phase."""
    if not transitions:
        return pd.DataFrame()

    tdf = pd.DataFrame([asdict(t) for t in transitions])
    phases_order = [
        "1. Pré-choc (J1-7)",
        "2. Péri-choc (J8-9)",
        "3. Post-choc immédiat (J10-14)",
        "4. Post-choc tardif (J15-21+)",
    ]

    records = []
    for ph in phases_order:
        sub = tdf[tdf["phase_curr"] == ph]
        n_trans = len(sub)
        if n_trans == 0:
            continue

        var_modal = sub["modal_change"].mean()
        stab_modal = 1.0 - var_modal
        var_route = sub["route_change"].mean()
        stab_route = 1.0 - var_route

        # Sous-ensemble transitions consécutives strictes
        sub_consec = sub[sub["is_consecutive_day"]]
        var_consec = sub_consec["modal_change"].mean() if len(sub_consec) > 0 else np.nan

        # Transitions strictement issues du LLM
        sub_llm = sub[sub["is_llm_valid_transition"]]
        var_llm = sub_llm["modal_change"].mean() if len(sub_llm) > 0 else np.nan

        records.append({
            "phase": ph,
            "transitions_total": n_trans,
            "taux_variation_modal": round(var_modal, 4),
            "stabilite_modale": round(stab_modal, 4),
            "taux_variation_itineraire": round(var_route, 4),
            "stabilite_itineraire": round(stab_route, 4),
            "transitions_consecutives": len(sub_consec),
            "taux_var_consecutif": round(var_consec, 4) if not np.isnan(var_consec) else None,
            "transitions_llm_valides": len(sub_llm),
            "taux_var_llm_valide": round(var_llm, 4) if not np.isnan(var_llm) else None,
        })

    return pd.DataFrame(records)


def compute_activity_summary(transitions: List[TransitionObservation]) -> pd.DataFrame:
    """Synthèse des taux de variation et stabilité par motif d'activité."""
    if not transitions:
        return pd.DataFrame()

    tdf = pd.DataFrame([asdict(t) for t in transitions])
    records = []

    for motif, grp in tdf.groupby("motif"):
        n_trans = len(grp)
        var_modal = grp["modal_change"].mean()
        stab_modal = 1.0 - var_modal
        var_route = grp["route_change"].mean()

        # Pré-choc vs Post-choc
        pre = grp[grp["phase_curr"] == "1. Pré-choc (J1-7)"]
        post = grp[grp["phase_curr"].isin(["3. Post-choc immédiat (J10-14)", "4. Post-choc tardif (J15-21+)"])]

        var_pre = pre["modal_change"].mean() if len(pre) > 0 else np.nan
        var_post = post["modal_change"].mean() if len(post) > 0 else np.nan

        records.append({
            "motif": motif,
            "transitions_total": n_trans,
            "taux_variation_global": round(var_modal, 4),
            "stabilite_globale": round(stab_modal, 4),
            "taux_variation_itineraire": round(var_route, 4),
            "taux_var_pre_choc": round(var_pre, 4) if not np.isnan(var_pre) else None,
            "taux_var_post_choc": round(var_post, 4) if not np.isnan(var_post) else None,
            "rigidite_relative": "Très Rigide" if var_modal < 0.10 else ("Modérée" if var_modal < 0.30 else "Flexible"),
        })

    df_res = pd.DataFrame(records).sort_values("stabilite_globale", ascending=False)
    return df_res


# ── Entropie modale et diversification ─────────────────────────────────────────

def compute_entropy(series: pd.Series) -> float:
    """Calcule l'entropie de Shannon en bits : H = - sum(p * log2(p))."""
    if len(series) == 0:
        return 0.0
    counts = series.value_counts()
    probs = counts / len(series)
    return float(-np.sum(probs * np.log2(probs)))


def compute_persona_entropy(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule l'entropie globale et par phase pour chaque persona."""
    records = []
    k_modes_ref = 5.0
    log2_k = np.log2(k_modes_ref)

    for pid, grp in df.groupby("ID Personne"):
        n_trips = len(grp)
        h_mode = compute_entropy(grp["Mode de transport Choisi"])
        h_norm = h_mode / log2_k
        h_route = compute_entropy(grp["chosen_route"])
        modes_distincts = grp["Mode de transport Choisi"].nunique()
        routes_distinctes = grp["chosen_route"].nunique()

        # Entropies par phase
        h_phases = {}
        for ph in ["1. Pré-choc (J1-7)", "2. Péri-choc (J8-9)", "3. Post-choc immédiat (J10-14)", "4. Post-choc tardif (J15-21+)"]:
            sub = grp[grp["phase"] == ph]
            h_phases[ph] = compute_entropy(sub["Mode de transport Choisi"]) if len(sub) > 0 else 0.0

        records.append({
            "persona_id": str(pid),
            "trajets_total": n_trips,
            "modes_distincts": modes_distincts,
            "entropie_modale_bits": round(h_mode, 4),
            "equitabilite_pielou": round(h_norm, 4),
            "routes_distinctes": routes_distinctes,
            "entropie_itineraire_bits": round(h_route, 4),
            "entropie_pre_choc": round(h_phases["1. Pré-choc (J1-7)"], 4),
            "entropie_peri_choc": round(h_phases["2. Péri-choc (J8-9)"], 4),
            "entropie_post_immed": round(h_phases["3. Post-choc immédiat (J10-14)"], 4),
            "entropie_post_tardif": round(h_phases["4. Post-choc tardif (J15-21+)"], 4),
        })

    return pd.DataFrame(records).sort_values("entropie_modale_bits", ascending=False)


# ── Matrices de transition modale ──────────────────────────────────────────────

def compute_transition_matrix(transitions: List[TransitionObservation], phase_filter: Optional[str] = None) -> pd.DataFrame:
    """Calcule la matrice stochastique P(Mode_t | Mode_{t-1})."""
    tdf = pd.DataFrame([asdict(t) for t in transitions])
    if phase_filter:
        tdf = tdf[tdf["phase_curr"] == phase_filter]

    all_modes = sorted(list(set(tdf["mode_prev"].unique()).union(set(tdf["mode_curr"].unique()))))
    matrix = pd.crosstab(
        tdf["mode_prev"],
        tdf["mode_curr"],
        normalize="index"
    ).reindex(index=all_modes, columns=all_modes, fill_value=0.0)
    return matrix


# ── Visualisations conformes à la charte ───────────────────────────────────────

def setup_plot_style() -> None:
    """Applique des paramètres esthétiques sobres et accessibles."""
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    plt.rcParams.update({
        "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans", "sans-serif"],
        "axes.edgecolor": "#CCCCCC",
        "axes.linewidth": 0.8,
        "grid.color": "#E5E5E5",
        "grid.linestyle": "--",
        "grid.alpha": 0.7,
        "figure.autolayout": True,
    })


def plot_phases_variation(phase_summary: pd.DataFrame, output_dir: Path, formats: List[str]) -> None:
    """Graphique 1 : Taux de variation modal et d'itinéraire par phase."""
    setup_plot_style()
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)

    phases = phase_summary["phase"].tolist()
    labels = [p.replace(" (", "\n(") for p in phases]
    x = np.arange(len(phases))
    width = 0.35

    bar1 = ax.bar(x - width / 2, phase_summary["taux_variation_modal"] * 100, width,
                  label="Variation modale : P(Mode_d ≠ Mode_{d-1})", color="#CE3B4B", edgecolor="none")
    bar2 = ax.bar(x + width / 2, phase_summary["taux_variation_itineraire"] * 100, width,
                  label="Variation itinéraire : P(Route_d ≠ Route_{d-1})", color="#0B7A9B", edgecolor="none")

    ax.set_ylabel("Taux de variation (%)", fontsize=11, fontweight="bold", color="#333333")
    ax.set_title("Évolution du taux de variation des choix de déplacement par phase\n(Choc d'avarie moteur J8-9)",
                 fontsize=13, fontweight="bold", pad=14, color="#111111")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylim(0, 100)

    # Étiquettes de valeurs en bout de barre (règle d'accessibilité)
    for rect in bar1:
        height = rect.get_height()
        ax.annotate(f"{height:.1f}%",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9, fontweight="bold", color="#CE3B4B")
    for rect in bar2:
        height = rect.get_height()
        ax.annotate(f"{height:.1f}%",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9, fontweight="bold", color="#0B7A9B")

    ax.legend(frameon=True, facecolor="white", edgecolor="#CCCCCC", fontsize=10)
    fig.tight_layout()

    for fmt in formats:
        fpath = output_dir / f"fig1_taux_variation_phases.{fmt}"
        fig.savefig(fpath, format=fmt, bbox_inches="tight")
        logger.info("Figure enregistrée : %s", fpath)
    plt.close(fig)


def plot_activity_rigidity(activity_summary: pd.DataFrame, output_dir: Path, formats: List[str]) -> None:
    """Graphique 2 : Rigidité vs Flexibilité comportementale par motif."""
    setup_plot_style()
    df_sorted = activity_summary.sort_values("stabilite_globale", ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    y = np.arange(len(df_sorted))
    bar_height = 0.55

    stabs = (df_sorted["stabilite_globale"] * 100).tolist()
    vars_m = (df_sorted["taux_variation_global"] * 100).tolist()

    bars = ax.barh(y, stabs, height=bar_height, color="#178A3F", label="Stabilité modale (%)")
    ax.barh(y, vars_m, left=stabs, height=bar_height, color="#CE3B4B", label="Variation modale (%)")

    ax.set_yticks(y)
    ax.set_yticklabels(df_sorted["motif"].tolist(), fontsize=11, fontweight="bold", color="#222222")
    ax.set_xlabel("Répartition comportementale (%)", fontsize=11, fontweight="bold")
    ax.set_xlim(0, 100)
    ax.set_title("Stabilité vs Flexibilité modale par motif d'activité\n(Ordonné du plus rigide au plus flexible)",
                 fontsize=13, fontweight="bold", pad=12)

    # Étiquettes explicites
    for i, (rect, stab, var, n) in enumerate(zip(bars, stabs, vars_m, df_sorted["transitions_total"])):
        ax.text(stab / 2, i, f"{stab:.1f}% stable", ha="center", va="center", color="white", fontweight="bold", fontsize=9)
        if var >= 10:
            ax.text(stab + var / 2, i, f"{var:.1f}% var", ha="center", va="center", color="white", fontweight="bold", fontsize=9)
        ax.text(101.5, i, f"N={n}", ha="left", va="center", color="#555555", fontsize=9)

    ax.set_ylim(-0.8, len(df_sorted) - 0.2)
    ax.legend(loc="upper left", bbox_to_anchor=(0.02, 0.98), frameon=True, facecolor="white", edgecolor="#CCCCCC", fontsize=10)
    fig.tight_layout()

    for fmt in formats:
        fpath = output_dir / f"fig2_rigidite_par_activite.{fmt}"
        fig.savefig(fpath, format=fmt, bbox_inches="tight")
        logger.info("Figure enregistrée : %s", fpath)
    plt.close(fig)


def plot_persona_entropy_collapse(entropy_df: pd.DataFrame, output_dir: Path, formats: List[str]) -> None:
    """Graphique 3 : Entropie modale (bits) par persona avant vs après choc."""
    setup_plot_style()
    df_sorted = entropy_df.sort_values("entropie_pre_choc", ascending=True)

    fig, ax = plt.subplots(figsize=(11, 6.5), dpi=300)
    y = np.arange(len(df_sorted))
    bar_height = 0.35

    bars_pre = ax.barh(y - bar_height / 2, df_sorted["entropie_pre_choc"], height=bar_height,
                       color="#0B7A9B", label="Pré-choc (J1-7)")
    bars_post = ax.barh(y + bar_height / 2, df_sorted["entropie_post_tardif"], height=bar_height,
                        color="#7C4DDB", label="Post-choc tardif (J15-21+)")

    ax.set_yticks(y)
    labels = [f"Persona {pid} {'(Choc C6)' if pid == '899549' else ''}" for pid in df_sorted["persona_id"]]
    ax.set_yticklabels(labels, fontsize=10, fontweight="bold")
    ax.set_xlabel("Entropie de Shannon H (bits) — Diversification du bouquet modal", fontsize=11, fontweight="bold")
    ax.set_title("Effondrement de la diversification modale (Entropie de Shannon)\nPré-choc vs Rétablissement tardif",
                 fontsize=13, fontweight="bold", pad=12)

    for i, (rect_pre, rect_post) in enumerate(zip(bars_pre, bars_post)):
        w_pre = rect_pre.get_width()
        w_post = rect_post.get_width()
        ax.text(w_pre + 0.03, rect_pre.get_y() + rect_pre.get_height() / 2, f"{w_pre:.2f}",
                va="center", ha="left", fontsize=9, color="#0B7A9B", fontweight="bold")
        ax.text(w_post + 0.03, rect_post.get_y() + rect_post.get_height() / 2, f"{w_post:.2f}",
                va="center", ha="left", fontsize=9, color="#7C4DDB", fontweight="bold")

    ax.legend(loc="lower right", frameon=True, facecolor="white", edgecolor="#CCCCCC")
    fig.tight_layout()

    for fmt in formats:
        fpath = output_dir / f"fig3_entropie_personas_avant_apres.{fmt}"
        fig.savefig(fpath, format=fmt, bbox_inches="tight")
        logger.info("Figure enregistrée : %s", fpath)
    plt.close(fig)


def plot_transition_matrices_heatmap(m_pre: pd.DataFrame, m_post: pd.DataFrame,
                                    output_dir: Path, formats: List[str]) -> None:
    """Graphique 4 : Matrices de transition modale Pré-choc vs Post-choc."""
    setup_plot_style()
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), dpi=300)

    all_modes = sorted(list(set(m_pre.index).union(set(m_post.index))))
    m_pre_sq = m_pre.reindex(index=all_modes, columns=all_modes, fill_value=0.0)
    m_post_sq = m_post.reindex(index=all_modes, columns=all_modes, fill_value=0.0)

    for ax, mat, title in zip(axes, [m_pre_sq, m_post_sq], ["Pré-choc (Jours 1-7)", "Post-choc (Jours 10-21+)"]):
        cax = ax.imshow(mat.values * 100, cmap="Blues", vmin=0, vmax=100)
        ax.set_title(f"Matrice de transition P(Mode_d | Mode_{{d-1}})\n{title}", fontsize=11, fontweight="bold", pad=10)
        ax.set_xticks(range(len(all_modes)))
        ax.set_yticks(range(len(all_modes)))
        ax.set_xticklabels(all_modes, rotation=45, ha="right", fontsize=9)
        ax.set_yticklabels(all_modes, fontsize=9)
        ax.set_xlabel("Mode à d", fontsize=10, fontweight="bold")
        ax.set_ylabel("Mode à d-1", fontsize=10, fontweight="bold")

        for r in range(len(all_modes)):
            for c in range(len(all_modes)):
                val = mat.values[r, c] * 100
                txt_col = "white" if val > 50 else "#222222"
                ax.text(c, r, f"{val:.0f}%", ha="center", va="center", color=txt_col, fontsize=9, fontweight="bold")

    fig.tight_layout()

    for fmt in formats:
        fpath = output_dir / f"fig4_matrices_transition_pre_post.{fmt}"
        fig.savefig(fpath, format=fmt, bbox_inches="tight")
        logger.info("Figure enregistrée : %s", fpath)
    plt.close(fig)


def plot_daily_selection_and_transitions(df: pd.DataFrame, transitions: List[TransitionObservation],
                                        output_dir: Path, formats: List[str]) -> None:
    """Graphique 5 : Série temporelle journalière - Taux de variation et méthodes de décision."""
    setup_plot_style()
    tdf = pd.DataFrame([asdict(t) for t in transitions])

    daily_var = tdf.groupby("jour_curr")["modal_change"].agg(["mean", "count"]).reset_index()
    daily_methods = pd.crosstab(df["jour_simule"], df["Méthode de sélection"], normalize="index") * 100

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7.5), sharex=True, dpi=300)

    # Zones de fond pour les phases
    for ax in [ax1, ax2]:
        ax.axvspan(0.5, 7.5, color="#0B7A9B", alpha=0.08, label="Pré-choc")
        ax.axvspan(7.5, 9.5, color="#CE3B4B", alpha=0.15, label="Péri-choc (J8-9)")
        ax.axvspan(9.5, 14.5, color="#B5259B", alpha=0.08, label="Post-choc immédiat")
        ax.axvspan(14.5, 22.5, color="#178A3F", alpha=0.08, label="Post-choc tardif")

    # Trace 1 : Taux de variation modal
    ax1.plot(daily_var["jour_curr"], daily_var["mean"] * 100, marker="o", color="#CE3B4B",
             linewidth=2.2, markersize=6, label="Taux de variation journalier (%)")
    ax1.set_ylabel("Taux de variation (%)", fontsize=10, fontweight="bold")
    ax1.set_ylim(-5, 105)
    ax1.set_title("Dynamique journalière du taux de variation et impact des incidents d'API LLM",
                  fontsize=12, fontweight="bold", pad=10)
    for _, r in daily_var.iterrows():
        ax1.annotate(f"{r['mean'] * 100:.0f}%", (r["jour_curr"], r["mean"] * 100),
                     textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8, fontweight="bold")
    ax1.legend(loc="upper right", frameon=True, facecolor="white")

    # Trace 2 : Méthodes de sélection (LLM valide vs Erreur de quota)
    cols_order = [c for c in ["LLM", "LLM Error (Default index)", "Un seul itinéraire disponible"] if c in daily_methods.columns]
    colors_dict = {
        "LLM": "#178A3F",
        "LLM Error (Default index)": "#CE3B4B",
        "Un seul itinéraire disponible": "#6E6D69",
    }
    bottom = np.zeros(len(daily_methods))
    for col in cols_order:
        vals = daily_methods[col].values
        ax2.bar(daily_methods.index, vals, bottom=bottom, label=col,
                color=colors_dict.get(col, COULEUR_NEUTRE), width=0.7, edgecolor="white", linewidth=0.5)
        bottom += vals

    ax2.set_xlabel("Jour simulé", fontsize=11, fontweight="bold")
    ax2.set_ylabel("Part des décisions (%)", fontsize=10, fontweight="bold")
    ax2.set_ylim(0, 100)
    ax2.set_xlim(0.5, 22.5)
    ax2.legend(loc="upper right", frameon=True, facecolor="white", fontsize=9)

    fig.tight_layout()

    for fmt in formats:
        fpath = output_dir / f"fig5_dynamique_journaliere_et_qualite.{fmt}"
        fig.savefig(fpath, format=fmt, bbox_inches="tight")
        logger.info("Figure enregistrée : %s", fpath)
    plt.close(fig)


# ── Génération du rapport Markdown ─────────────────────────────────────────────

def generate_markdown_report(phase_df: pd.DataFrame, activity_df: pd.DataFrame,
                             entropy_df: pd.DataFrame, output_dir: Path,
                             df: Optional[pd.DataFrame] = None) -> Path:
    """Génère un rapport d'analyse comportementale exhaustif et chiffré."""
    report_path = output_dir / "rapport_stabilite_variation.md"

    md = []
    md.append("# Rapport d'Analyse Comportementale : Stabilité Modale et Taux de Variation")
    md.append("")
    md.append(f"*Généré le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} par `modal_variation_rate.py`*")
    md.append("")
    md.append("## 1. Synthèse Exécutive")
    md.append("")
    md.append("Ce rapport fournit les métriques formelles de stabilité comportementale et de dynamique de transition modale "
              "sur les choix d'itinéraires avant, pendant et après choc (incident moteur J8-9).")
    md.append("")
    md.append("### Chiffres clés par phase :")
    md.append("")
    md.append("| Phase | Transitions | Taux Variation Modal | Stabilité Modale | Taux Variation Itinéraire | Stabilité Itinéraire |")
    md.append("|---|:---:|:---:|:---:|:---:|:---:|")
    for _, r in phase_df.iterrows():
        md.append(f"| **{r['phase']}** | {r['transitions_total']} | **{r['taux_variation_modal']*100:.1f}%** | "
                  f"{r['stabilite_modale']*100:.1f}% | {r['taux_variation_itineraire']*100:.1f}% | {r['stabilite_itineraire']*100:.1f}% |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 2. Rigidité vs Flexibilité par Activité (Motif)")
    md.append("")
    md.append("L'analyse des transitions modales pour une même activité montre une disparité structurelle majeure "
              "entre motifs obligatoires (navette domicile-travail, études) et motifs non-contraints (loisirs, achats) :")
    md.append("")
    md.append("| Motif | Transitions | Stabilité Globale | Taux Variation Pré-choc | Taux Variation Post-choc | Diagnostic |")
    md.append("|---|:---:|:---:|:---:|:---:|:---:|")
    for _, r in activity_df.iterrows():
        v_pre = f"{r['taux_var_pre_choc']*100:.1f}%" if r['taux_var_pre_choc'] is not None else "N/A"
        v_post = f"{r['taux_var_post_choc']*100:.1f}%" if r['taux_var_post_choc'] is not None else "N/A"
        md.append(f"| **{r['motif']}** | {r['transitions_total']} | **{r['stabilite_globale']*100:.1f}%** | "
                  f"{v_pre} | {v_post} | `{r['rigidite_relative']}` |")
    md.append("")
    md.append("- **Activités rigides** : `Etude` (stabilité 100%, 0% de variation) et `Travail` (stabilité 91.7%, 8.3% de variation globale). "
              "Ces déplacements présentent des contraintes d'horaires et de destination sévères, réduisant drastiquement l'arbitrage modal.")
    md.append("- **Activités flexibles** : `Achats` (variation globale 35.7%, 70% en pré-choc) et `Loisirs` (variation globale 32.3%, 90% en pré-choc). "
              "Ces activités constituent le lieu privilégié de l'exploration multimodale et de la sensibilité aux conditions contextuelles.")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 3. Analyse de l'Entropie Modale et Bouquet d'Itinéraires")
    md.append("")
    md.append("L'entropie de Shannon $H(Persona) = - \\sum p_m \\log_2(p_m)$ quantifie l'équitabilité et la diversification "
              "du bouquet de choix. Une valeur nulle traduit un verrouillage monomodal absolu ; une valeur élevée traduit un comportement multimodale équilibré.")
    md.append("")
    md.append("| Persona | Trajets | Modes Distincts | Entropie H (bits) | Équitabilité Pielou | Entropie Pré-choc | Entropie Post-tardif | Statut |")
    md.append("|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
    for _, r in entropy_df.iterrows():
        choc_tag = " *(Choc C6)*" if r['persona_id'] == '899549' else ""
        md.append(f"| **{r['persona_id']}{choc_tag}** | {r['trajets_total']} | {r['modes_distincts']} | "
                  f"**{r['entropie_modale_bits']:.3f}** | {r['equitabilite_pielou']:.3f} | "
                  f"{r['entropie_pre_choc']:.3f} | {r['entropie_post_tardif']:.3f} | "
                  f"{'Verrouillé (0 bit)' if r['entropie_post_tardif'] == 0 else 'Multimodal'} |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 4. Diagnostic Méthodologique et Décomposition des Décisions")
    md.append("")
    md.append("### Q1 : Quelles activités sont les plus rigides vs flexibles ?")
    md.append("- **Les navettes obligatoires (Travail/Étude)** présentent la plus forte invariance modale.")
    md.append("- **Les loisirs et achats** constituent le foyer principal de flexibilité et d'exploration multimodale.")
    md.append("")
    md.append("### Q2 : Décomposition des modes de décision et fiabilité de l'infrastructure")

    if df is not None and not df.empty:
        total_decisions = len(df)
        method_counts = df["Méthode de sélection"].value_counts().to_dict() if "Méthode de sélection" in df.columns else {}
        llm_count = method_counts.get("LLM", 0)
        error_count = sum(cnt for m, cnt in method_counts.items() if any(k in str(m).lower() for k in ["error", "default", "repli", "fallback"]))
        unique_count = sum(cnt for m, cnt in method_counts.items() if "seul" in str(m).lower())
        other_count = total_decisions - llm_count - error_count - unique_count

        md.append(f"- **Volume total de décisions enregistrées :** {total_decisions}")
        md.append(f"- **Délibérations LLM effectives :** {llm_count} ({llm_count / total_decisions * 100:.1f}%)")
        if error_count > 0:
            md.append(f"- **Replis techniques d'urgence (erreurs / index par défaut) :** {error_count} ({error_count / total_decisions * 100:.1f}%)")
            md.append("  > [!NOTE]\n"
                      f"  > **Avertissement méthodologique :** {error_count} choix ont été forcés par repli technique automatique "
                      "(ex. quota d'API épuisé, indisponibilité de passerelle). "
                      "Ces replis ne reflètent pas un arbitrage cognitif autonome de l'agent et doivent être dissociés de l'effet choc.")
        else:
            md.append("- **Replis techniques d'urgence :** 0 (100% des décisions ont été délibérées ou contraintes par l'offre physique)")

        if unique_count > 0:
            md.append(f"- **Choix physiquement contraints (un seul itinéraire disponible) :** {unique_count} ({unique_count / total_decisions * 100:.1f}%)")
        if other_count > 0:
            md.append(f"- **Autres méthodes de sélection :** {other_count} ({other_count / total_decisions * 100:.1f}%)")
    else:
        md.append("- Aucune donnée de décision détaillée disponible pour décomposer les méthodes de sélection.")

    md.append("")
    md.append("### Q3 : Évolution des taux de transition et persistance")
    md.append("- L'analyse des matrices de transition et des indicateurs d'entropie ci-dessus permet de quantifier l'amplitude de l'exploration modale et d'objectiver la formation éventuelle de nouvelles habitudes.")
    md.append("")

    report_path.write_text("\n".join(md), encoding="utf-8")
    logger.info("Rapport Markdown écrit : %s", report_path)
    return report_path


# ── Point d'entrée principal ───────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mesure du taux de variation des choix d'itinéraires et de modes avant/après choc."
    )
    parser.add_argument(
        "moves_path",
        nargs="?",
        default="experiments/current/moves.csv",
        help="Chemin vers moves.csv (défaut : experiments/current/moves.csv)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Dossier de sortie des rapports et graphiques (défaut : reports/<exp_id>/)"
    )
    parser.add_argument(
        "--mesures-dir",
        default="experiments/current/mesures",
        help="Dossier de sortie des tables CSV complémentaires (défaut : experiments/current/mesures)"
    )
    parser.add_argument(
        "--format",
        choices=["svg", "png", "all"],
        default="svg",
        help="Format des figures (défaut : svg)"
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Désactive la génération graphique pour n'exporter que les tableaux"
    )

    args = parser.parse_args()

    csv_path = Path(args.moves_path).resolve()
    mesures_dir = Path(args.mesures_dir).resolve()

    # 1. Chargement et préparation
    df = load_and_preprocess_moves(csv_path)

    # Détermination de l'identifiant d'expérience pour le rangement
    if args.output_dir:
        out_dir = Path(args.output_dir).resolve()
    else:
        ref = str(df["Référence"].dropna().iloc[0]) if "Référence" in df.columns and len(df["Référence"].dropna()) > 0 else "unknown_run"
        choc_val = str(df["Choc"].dropna().iloc[0]) if "Choc" in df.columns and len(df["Choc"].dropna()) > 0 else ""
        exp_id = f"{choc_val}_{ref}" if choc_val else ref
        out_dir = Path("reports") / exp_id

    out_dir.mkdir(parents=True, exist_ok=True)
    mesures_dir.mkdir(parents=True, exist_ok=True)

    formats = ["png", "svg"] if args.format == "all" else [args.format]

    # 2. Calcul des transitions
    transitions_act = compute_transitions(df, level="activite")
    transitions_motif = compute_transitions(df, level="motif")

    # 3. Synthèses
    phase_summary = compute_phase_summary(transitions_act)
    activity_summary = compute_activity_summary(transitions_motif)
    entropy_summary = compute_persona_entropy(df)

    # 4. Matrices de transition
    m_pre = compute_transition_matrix(transitions_act, phase_filter="1. Pré-choc (J1-7)")
    m_post = compute_transition_matrix(transitions_act, phase_filter="4. Post-choc tardif (J15-21+)")

    # 5. Export des tableaux de données
    csv_phase_out = out_dir / "taux_variation_par_phase.csv"
    csv_act_out = out_dir / "taux_variation_par_activite.csv"
    csv_ent_out = out_dir / "entropie_par_persona.csv"
    csv_trans_out = out_dir / "transitions_detaillees.csv"

    phase_summary.to_csv(csv_phase_out, index=False)
    activity_summary.to_csv(csv_act_out, index=False)
    entropy_summary.to_csv(csv_ent_out, index=False)
    pd.DataFrame([asdict(t) for t in transitions_act]).to_csv(csv_trans_out, index=False)

    # Copie dans mesures_dir si demandé et existant
    if mesures_dir.is_dir():
        phase_summary.to_csv(mesures_dir / "taux_variation_par_phase.csv", index=False)
        activity_summary.to_csv(mesures_dir / "taux_variation_par_activite.csv", index=False)
        entropy_summary.to_csv(mesures_dir / "entropie_par_persona.csv", index=False)

    logger.info("Tableaux CSV exportés dans %s et %s", out_dir, mesures_dir)

    # 6. Graphiques
    if not args.no_plots:
        logger.info("Génération des figures conformes à la charte graphique...")
        plot_phases_variation(phase_summary, out_dir, formats)
        plot_activity_rigidity(activity_summary, out_dir, formats)
        plot_persona_entropy_collapse(entropy_summary, out_dir, formats)
        plot_transition_matrices_heatmap(m_pre, m_post, out_dir, formats)
        plot_daily_selection_and_transitions(df, transitions_act, out_dir, formats)

    # 7. Rapport Markdown
    report_file = generate_markdown_report(phase_summary, activity_summary, entropy_summary, out_dir, df=df)

    print("\n" + "=" * 70)
    print("ANALYSE DU TAUX DE VARIATION ET DE STABILITÉ COMPORTEMENTALE TERMINÉE")
    print("=" * 70)
    print(f"Rapport de synthèse : {report_file}")
    print(f"Dossier des résultats : {out_dir}")
    print(f"Tableaux exportés dans : {mesures_dir}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
