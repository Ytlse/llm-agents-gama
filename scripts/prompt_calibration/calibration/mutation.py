"""Génération et application de mutations — phase 1 du ticket 004.

- ``apply_mutation`` : fonction **pure** (modify / delete / insert), testable.
- ``MutationGenerator`` : appelle le modèle de mutation (distinct du modèle d'éval,
  DG) pour proposer une mutation ciblée, guidée par les écarts EMC², les scores par
  dimension, l'historique et l'attribution Shapley. L'appel est injectable (``mutate_fn``).
- l'attribution Shapley (``calibration.shapley``) mesure la contribution de chaque
  bloc au score (nourrit le mutateur et la carte colorée du dashboard) ; le formatage
  de cette carte pour le mutateur vit ici (``format_ablation_for_mutation``).

Les opérateurs riches (reorder/merge/condense/crossover) et le tabu/entonnoir
arrivent en phase 4 — la phase 1 reproduit le comportement de l'ancienne lib.
"""

from __future__ import annotations

import json
import time
from typing import Callable, Optional

import pandas as pd

from .metrics import (MODES, _STRATA_DIMS, Metric, worst_strata_modes)
from .models import Mutation, RunConfig

# ── Application (pure) ───────────────────────────────────────────────────────

# Opérateurs équivalents en application (le nom distinct sert au bandit / dashboard).
_MODIFY_LIKE = ("modify", "condense")
_DELETE_LIKE = ("delete", "compact_delete")


def apply_mutation(blocks: list[dict], mutation: dict) -> Optional[list[dict]]:
    """Applique la mutation. Renvoie ``None`` si elle est invalide.

    Opérateurs de phase 1 :
    - ``modify`` : remplace le contenu d'un bloc mutable existant ;
    - ``delete`` : retire un bloc (interdit sur ``json_schema``) ;
    - ``insert`` : crée ``inserted_N`` juste APRÈS ``target_block`` (interdit après
      ``json_schema``) ; la cible n'a pas besoin d'être mutable.

    Opérateurs riches de phase 4 (DE) :
    - ``condense`` : réécriture plus courte à sens constant (= ``modify``) ;
    - ``compact_delete`` : suppression pilotée par la passe de compaction (= ``delete``) ;
    - ``reorder`` : déplace ``target_block`` juste après ``anchor``
      (``anchor="__start__"`` → en tête) ;
    - ``merge_blocks`` : fusionne ``target_block`` + ``second_block`` en un seul
      bloc (contenu = ``new_content``), retire ``second_block`` ;
    - ``split`` : scinde ``target_block`` en plusieurs blocs (parties séparées par
      une ligne vide dans ``new_content``).
    """
    target = mutation.get("target_block", "")
    action = mutation.get("action", "modify")
    content = mutation.get("new_content", "")

    target_block = next((b for b in blocks if b["name"] == target), None)
    if target_block is None:
        return None
    # Toute mutation autre qu'un insert/reorder touchant le contenu exige la mutabilité.
    if action not in ("insert", "reorder") and not target_block["mutable"]:
        return None
    if action in _DELETE_LIKE + ("insert", "reorder", "merge_blocks", "split") and target == "json_schema":
        return None

    if action == "insert":
        if not content.strip():
            return None
        return _insert_after(blocks, target, content)

    if action == "reorder":
        return _reorder(blocks, target, mutation.get("anchor", ""))

    if action == "merge_blocks":
        return _merge_blocks(blocks, target, mutation.get("second_block", ""), content)

    if action == "split":
        return _split(blocks, target, content)

    # modify / condense / delete / compact_delete
    out = []
    for b in blocks:
        if b["name"] == target:
            if action not in _DELETE_LIKE:
                if not content.strip():
                    return None
                out.append({**b, "content": content})
        else:
            out.append(b)
    return out


def _insert_after(blocks: list[dict], target: str, content: str) -> list[dict]:
    n_ins = sum(1 for b in blocks if b["name"].startswith("inserted_"))
    new_block = {"name": f"inserted_{n_ins + 1}", "mutable": True, "content": content}
    out = []
    for b in blocks:
        out.append(b)
        if b["name"] == target:
            out.append(new_block)
    return out


def _reorder(blocks: list[dict], target: str, anchor: str) -> Optional[list[dict]]:
    """Déplace ``target`` juste après ``anchor`` (``__start__`` → en tête).

    Refuse un ancrage sur le bloc lui-même, un ancrage introuvable, ou un
    déplacement après ``json_schema`` (le schéma doit rester en dernier).
    """
    if anchor == target:
        return None
    moved = next((b for b in blocks if b["name"] == target), None)
    if moved is None:
        return None
    rest = [b for b in blocks if b["name"] != target]
    if anchor == "__start__":
        return [moved] + rest
    if anchor == "json_schema":
        return None
    names = [b["name"] for b in rest]
    if anchor not in names:
        return None
    pos = names.index(anchor) + 1
    return rest[:pos] + [moved] + rest[pos:]


def _merge_blocks(blocks: list[dict], target: str, second: str,
                  content: str) -> Optional[list[dict]]:
    """Fusionne ``target`` et ``second`` : ``target`` reçoit ``content``, ``second`` disparaît."""
    if not second or second == target or not content.strip():
        return None
    sec_block = next((b for b in blocks if b["name"] == second), None)
    if sec_block is None or not sec_block["mutable"] or second == "json_schema":
        return None
    out = []
    for b in blocks:
        if b["name"] == second:
            continue
        if b["name"] == target:
            out.append({**b, "content": content})
        else:
            out.append(b)
    return out


def _split(blocks: list[dict], target: str, content: str) -> Optional[list[dict]]:
    """Scinde ``target`` : 1re partie → ``target`` ; suivantes → ``inserted_N``."""
    parts = [p.strip() for p in content.split("\n\n") if p.strip()]
    if len(parts) < 2:
        return None
    out: list[dict] = []
    n_ins = sum(1 for b in blocks if b["name"].startswith("inserted_"))
    for b in blocks:
        if b["name"] == target:
            out.append({**b, "content": parts[0]})
            for extra in parts[1:]:
                n_ins += 1
                out.append({"name": f"inserted_{n_ins}", "mutable": True, "content": extra})
        else:
            out.append(b)
    return out


# ── Carte de contribution des blocs (attribution Shapley) ────────────────────

# Abréviations des dimensions du score, partagées par l'historique des mutations
# et la carte de contribution Shapley (légende affichée au mutateur).
DIM_ABBREV = {"global": "g", "absent_penalty": "ab", "age": "ag",
              "occupation": "oc", "genre": "ge", "motif": "mo",
              "distance": "di", "length_penalty": "lg"}
DIM_LEGEND = ("g=global, ab=modes absents, ag=âge, oc=occupation, ge=genre, "
              "mo=motif, di=distance, lg=longueur")

# Noms longs des dimensions affichées en colonnes de la table de contribution
# (en-têtes « nom (abrév) », plus lisibles qu'une abréviation seule).
DIM_LABEL = {"global": "global", "age": "âge", "occupation": "occupation",
             "genre": "genre", "motif": "motif", "distance": "distance"}

# Légende + conventions de signe, injectées UNE fois dans le prompt système du
# mutateur (et non plus au coup par coup dans chaque section) pour lever toute
# ambiguïté d'interprétation des chiffres du rapport (dims, Δ, crochets, strates).
LEGEND_AND_SIGNS = f"""\
LÉGENDE ET CONVENTIONS DE SIGNE (lis-la avant d'interpréter les chiffres du rapport) :
- Dimensions du score : {DIM_LEGEND}.
- Modes de déplacement : marche, vélo, TC (transports collectifs), voiture, deux-roues motorisé.
- Le « composite » est une PERTE (écart agrégé à la cible EMC²) : PLUS IL EST BAS, MIEUX C'EST. L'objectif est de le faire BAISSER.
- Δ d'un bloc (attribution Shapley) = effet de sa PRÉSENCE sur le composite :
  • Δ > 0 → bloc UTILE : le retirer dégraderait le score → à garder / modifier avec précaution ;
  • Δ < 0 → bloc NUISIBLE : à réécrire en priorité, voire supprimer ;
  • Δ ≈ 0 → bloc neutre : candidat à la suppression (compaction).
- Contributions par dimension (crochets « [ag+6 mo+3 | oc-13] » ou colonnes de la table) : en points de composite, le SIGNE indique le SENS DE L'EFFET DU BLOC — « + » = le bloc AIDE cette dimension (il RAPPROCHE de la cible EMC², réduit l'écart) ; « − » = le bloc la DÉGRADE (il creuse l'écart). Même orientation que Δ tot (positif = utile). Dans les crochets, à gauche du « | » les dimensions aidées, à droite celles dégradées.
- Écarts strate × mode : « sous-représenté » = ce mode est trop RARE vs EMC² pour cette strate → à RENFORCER ; « sur-représenté » = trop FRÉQUENT → à ATTÉNUER."""

# Une contribution par dimension sous ce seuil (en pts de composite) est du bruit
# d'échantillonnage plus que du signal : elle n'est pas montrée au mutateur.
DETAIL_MIN_ABS = 1.0

# Abréviations des modes pour la colonne « modes poussés » de la table de contribution.
MODE_ABBREV = {"marche": "mar", "voiture": "voit", "velo": "vélo",
               "transports_collectifs": "TC"}

# Poussée modale sous ce seuil (pts de part) = bruit d'échantillonnage : masquée.
MODE_PUSH_MIN_ABS = 1.0


def modes_from_stored(stored: dict) -> dict:
    """Poussées modales d'une ligne d'ablation Shapley **persistée**.

    ``run_shapley`` range les poussées dans ``scores_json`` sous les clés
    ``mode:{m}`` (déjà en convention « poussée », pas φ). Consommé par le
    backfill de reprise et le dashboard. ``{}`` si la ligne est antérieure
    à la matrice bloc × mode.
    """
    return {k.split(":", 1)[1]: v for k, v in stored.items()
            if k.startswith("mode:")}


def format_mode_push(modes: Optional[dict],
                     min_abs: float = MODE_PUSH_MIN_ABS) -> str:
    """Cellule compacte des poussées modales d'un bloc : ``vélo+4 voit-3``.

    Poussée = effet de la **présence** du bloc sur la part du mode (pts de %) —
    « + » = le bloc augmente cette part, « − » = il la réduit. Sens BRUT, à
    croiser avec les leviers (pousser un mode déjà sur-représenté est nuisible).
    ``·`` si rien ne passe le seuil de bruit.
    """
    if not modes:
        return "·"
    kept = sorted(((MODE_ABBREV.get(m, m), v) for m, v in modes.items()
                   if abs(v) >= min_abs), key=lambda x: abs(x[1]), reverse=True)
    return " ".join(f"{a}{v:+.0f}" for a, v in kept) or "·"


def detail_from_stored(stored: dict, weights: dict) -> dict:
    """Détail par dimension d'une ligne d'ablation Shapley **persistée**.

    Le détail pondéré (``w_d × φ_d``, pts de composite) est stocké tel quel dans
    ``scores_json`` par ``loop.run_shapley`` → il suffit de projeter sur les
    dimensions actives. Consommé par la carte du dashboard
    (``dashboard_data.ablation_table``) et par la reprise de boucle (backfill des
    états snapshotés sans ``detail``).
    """
    dims = [d for d, w in weights.items() if w > 0]
    return {d: stored[d] for d in dims if d in stored}


def format_dim_detail(detail: Optional[dict], min_abs: float = DETAIL_MIN_ABS) -> str:
    """Crochet compact des contributions par dimension : ``[ag+6 mo+3 | oc-13]``.

    Contributions pondérées (pts de composite), filtrées à ``|v| ≥ min_abs``,
    positives puis négatives, par magnitude décroissante. Chaîne vide si rien
    ne passe le filtre.
    """
    if not detail:
        return ""
    kept = sorted(((DIM_ABBREV.get(d, d), v) for d, v in detail.items()
                   if abs(v) >= min_abs), key=lambda x: abs(x[1]), reverse=True)
    pos = " ".join(f"{a}{v:+.0f}" for a, v in kept if v > 0)
    neg = " ".join(f"{a}{v:+.0f}" for a, v in kept if v < 0)
    inner = " | ".join(p for p in (pos, neg) if p)
    return f"[{inner}]" if inner else ""


# ── Formatage du contexte de mutation ────────────────────────────────────────

# Colonnes de la table de contribution, dans l'ordre (dimensions « gardées » +
# global) : ce sont celles qui pilotent les leviers, les pénalités techniques
# (absent/longueur) restent agrégées dans la colonne Δ total.
TABLE_DIMS = ["global", "age", "occupation", "genre", "motif", "distance"]


def format_contrib_table(results: list[dict], min_abs: float = DETAIL_MIN_ABS) -> str:
    """Table markdown bloc × dimension des contributions au score.

    Une ligne par bloc, une colonne par dimension (``TABLE_DIMS``) + « modes
    poussés » + ``Δ tot``. Valeurs = contributions **pondérées** (pts de composite)
    issues du ``detail`` Shapley ; signe = sens de l'effet du bloc (« + » aide,
    « − » dégrade, cf. LÉGENDE). « modes poussés » = effet de la présence du bloc
    sur les parts modales (``format_mode_push``, matrice bloc × mode). ``·`` =
    contribution sous le seuil de bruit. Triée par Δ décroissant (blocs utiles en
    tête). ``Δ tot`` est le composite complet et peut inclure des pénalités
    (modes absents, longueur) non détaillées en colonnes.
    """
    cols = [f"{DIM_LABEL.get(d, d)} ({DIM_ABBREV.get(d, d)})" for d in TABLE_DIMS]
    header = "| bloc | " + " | ".join(cols) + " | modes poussés | Δ tot |"
    sep = "| " + " | ".join(["---"] * (len(TABLE_DIMS) + 3)) + " |"
    rows = []
    for r in sorted(results, key=lambda x: x["delta"], reverse=True):
        detail = r.get("detail") or {}
        cells = []
        for d in TABLE_DIMS:
            v = detail.get(d, 0.0)
            cells.append(f"{v:+.1f}" if abs(v) >= min_abs else "·")
        cells.append(format_mode_push(r.get("modes")))
        rows.append(f"| {r['bloc']} | " + " | ".join(cells) + f" | {r['delta']:+.1f} |")
    return "\n".join([header, sep, *rows])


def format_ablation_for_mutation(results: list[dict]) -> str:
    """Contexte de contribution des blocs pour le mutateur.

    Rendu principal = table bloc × dimension (``format_contrib_table``) — les
    conventions de signe sont dans le prompt système (``LEGEND_AND_SIGNS``), plus
    besoin de les répéter. On y ajoute, pour les seuls blocs nuisibles diagnostiqués,
    la raison textuelle de leur régression (canal mode) que la table ne porte pas.
    """
    if not results:
        return ""
    lines = [
        "\nContribution de chaque bloc au score (une ligne par bloc, en points de composite) :",
        "Lecture : « + » = le bloc RAPPROCHE de la cible EMC² sur cette dimension "
        "(réduit l'écart → bloc UTILE) ; « − » = il EN ÉLOIGNE (creuse l'écart → bloc "
        "NUISIBLE) ; « · » = effet négligeable. Colonnes = dimensions (nom + abrév). "
        "Colonne « modes poussés » (mar=marche, vélo, TC=transports collectifs, "
        "voit=voiture) = effet de la PRÉSENCE du bloc sur les parts modales, en pts "
        "de % : « vélo+4 » = le bloc augmente la part du vélo de 4 pts. Sens BRUT à "
        "croiser avec les leviers : pousser un mode SOUS-représenté = utile, pousser "
        "un mode SUR-représenté = nuisible. "
        "Δ tot = bilan du bloc (>0 utile, <0 nuisible).",
        format_contrib_table(results)]
    harmful = [r for r in results if r["harmful"] and r.get("diag")]
    if harmful:
        lines.append("\n🗑 Blocs nuisibles — pourquoi ils régressent :")
        for r in harmful:
            lines.append(f"    • {r['bloc']} : {r['diag']}")
    return "\n".join(lines) + "\n"


# Cap de sécurité d'un snippet affiché : assez large pour un bloc entier (le snippet
# est un MATÉRIAU de réécriture — tronqué court, il forcerait le mutateur à halluciner
# la fin de l'argument), assez serré pour contenir un bloc anormalement long.
SNIPPET_MAX_CHARS = 300


def format_snippets_for_mutation(snippets: Optional[list[dict]],
                                 max_chars: int = SNIPPET_MAX_CHARS) -> str:
    """Bibliothèque d'arguments (DL) : meilleurs blocs capitalisés fournis au mutateur.

    Chaque snippet est un bloc inséré/réécrit accepté avec gain significatif, taggé
    par le mode qu'il a aidé. Le mutateur les reçoit comme **matériau de réécriture**
    (les îlots se fertilisent ainsi même sans merge) → contenu fourni en entier
    (cap de sécurité ``max_chars``). Liste de dicts (pure/testable) :
    ``{block_name, content, tag_mode, gain}``.
    """
    if not snippets:
        return ""
    lines = ["\n📚 Bibliothèque d'arguments qui ont marché ailleurs "
             "(matière à réutiliser/adapter, pas à copier tel quel) :"]
    for s in snippets:
        preview = (s.get("content") or "").replace("\n", " ").strip()
        if len(preview) > max_chars:
            preview = preview[:max_chars].rstrip() + "…"
        mode = s.get("tag_mode") or "?"
        lines.append(f"    • (aide {mode}, gain {s.get('gain', 0):.1f}) : {preview}")
    return "\n".join(lines) + "\n"


def format_lessons(lessons: Optional[str]) -> str:
    """Mémoire de leçons (synthèse des rejets précédents) réinjectée au mutateur.

    Chaîne libre produite au tour précédent dans le champ ``reflection`` — la
    synthèse des raisons RÉCURRENTES de rejet. Vide → rien n'est injecté (premiers
    tours, ou ``reflection_enabled=False``).
    """
    if not lessons or not lessons.strip():
        return ""
    return ("\n🧠 Mémoire des leçons (synthèse de TES analyses précédentes des rejets — "
            "tiens-en compte, puis mets-la à jour dans le champ \"reflection\") :\n"
            f"{lessons.strip()}\n")


def extract_reflection(raw) -> str:
    """Récupère le champ ``reflection`` de la sortie brute du mutateur (ou ``""``)."""
    if isinstance(raw, dict):
        r = raw.get("reflection")
        if isinstance(r, str):
            return r.strip()
    return ""


def format_hard_negatives(df: Optional[pd.DataFrame], cerema: dict,
                          k: int = 4) -> str:
    """Exemples concrets de décisions à corriger (*hard negatives*).

    Pour les pires croisements strate × mode **sur-représentés** (le mode est choisi
    trop souvent pour cette strate), montre jusqu'à ``k`` décisions individuelles
    réelles (persona → mode choisi). Le mutateur voit ainsi à quoi ressemble une
    erreur type — au lieu de ne raisonner que sur des agrégats — et peut corriger
    le schéma comportemental de manière ciblée. Sélection **déterministe** (ordre
    du df) → reprenable sans variance. ``""`` si ``k <= 0`` ou rien à montrer.
    """
    if df is None or df.empty or "mode_cat" not in df.columns or k <= 0:
        return ""
    over = [r for r in worst_strata_modes(df, cerema) if r["diff"] > 0]
    if not over:
        return ""
    lines = ["\n🔍 Exemples réels de décisions type à corriger (mode SUR-représenté "
             "pour la strate — corrige par le raisonnement comportemental, jamais "
             "par seuil chiffré) :"]
    shown = 0
    seen_agents: set = set()
    persona_cols = ("genre", "age", "occupation", "motif", "dist_cat")
    for r in over[:3]:
        col = next((c for d, c, _ in _STRATA_DIMS if d == r["dim"]), r["dim"])
        if col not in df.columns:
            continue
        sub = df[(df[col] == r["cat"]) & (df["mode_cat"] == r["mode"])]
        for _, agent in sub.head(2).iterrows():
            aid = agent.get("agent_id")
            if aid is not None and aid in seen_agents:
                continue
            seen_agents.add(aid)
            parts = []
            for c in persona_cols:
                v = agent.get(c)
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    continue
                parts.append(f"{v} ans" if c == "age" else str(v))
            lines.append(f"  • {', '.join(parts)} → {r['mode']} "
                         f"({r['dim']}[{r['cat']}] : {r['diff']:+.0f} pts vs cible)")
            shown += 1
            if shown >= k:
                break
        if shown >= k:
            break
    if shown == 0:
        return ""
    return "\n".join(lines) + "\n"


def _gap_description(df: Optional[pd.DataFrame], cerema: dict) -> tuple[str, str]:
    cerema_g = cerema["parts_modales_2023"]["global"]
    if df is None or len(df) == 0:
        return "(premier run, pas de données)", ""
    total = len(df)
    dist = df["mode_cat"].value_counts()
    dist_lines = [f"  {m}: {dist.get(m, 0) / total * 100:.1f}%  "
                  f"(cible EMC²: {cerema_g.get(m, '?')}%)" for m in MODES]

    def pct(m):
        return dist.get(m, 0) / total * 100

    under = min(MODES, key=lambda m: pct(m) - cerema_g.get(m, 0))
    over = max(MODES, key=lambda m: pct(m) - cerema_g.get(m, 0))
    under_absent = " (ABSENT)" if dist.get(under, 0) == 0 else ""
    worst = (
        "⚠️ DEUX leviers prioritaires (les deux comptent autant) :\n"
        f"  • RENFORCER : {under}{under_absent} (actuel={pct(under):.1f}%, "
        f"cible={cerema_g.get(under, '?')}%, manque {cerema_g.get(under, 0) - pct(under):+.1f} pts)\n"
        f"  • ATTÉNUER  : {over} (actuel={pct(over):.1f}%, cible={cerema_g.get(over, '?')}%, "
        f"excès {pct(over) - cerema_g.get(over, 0):+.1f} pts)")
    return "\n".join(dist_lines), worst


# Catégorie d'un rejet : sépare un rejet DE FOND (leçon transférable — une dimension
# protégée régresse, mutation inapplicable, cible déjà couverte, strate visée non
# améliorée) d'un rejet de SEUIL/BRUIT (l'idée n'est pas invalidée sur le fond, juste
# non significative ou redondante). Le mutateur ne doit PAS sur-interpréter ces derniers.
_REJECT_KIND = {
    "vetoed": "fond",
    "invalid": "fond",
    "rejected_dup_block": "fond",
    "rejected_gate": "fond",
    "rejected_score": "seuil",
    "rejected_stat": "bruit",
    "rejected_race": "bruit",
    "rejected_tabu": "doublon",
}

_REJECT_KIND_LEGEND = ("[fond]=raison de fond (n'y retourne pas à l'identique) ; "
                       "[bruit]/[seuil]=gain non significatif ou composite non amélioré "
                       "(idée non invalidée : reformule/change d'angle) ; "
                       "[doublon]=trop proche d'un rejet récent")


def reject_kind(verdict: Optional[str], cause: str = "") -> str:
    """Catégorie d'un rejet (``fond`` / ``bruit`` / ``seuil`` / ``doublon``), ou ``""``.

    Utilise le ``verdict`` s'il est disponible (états récents) ; à défaut, retombe sur
    une heuristique de forme de ``cause`` (états snapshotés avant l'ajout du verdict)."""
    if verdict and verdict in _REJECT_KIND:
        return _REJECT_KIND[verdict]
    c = cause or ""
    if c.startswith("cos="):
        return "doublon"
    if "Δ=" in c or "palier" in c or "@n=" in c:
        return "bruit"
    if ("+" in c or "≥" in c) and "@" not in c:
        return "fond"
    return ""


def _history_summary(history: list[dict]) -> str:
    past = [h for h in history if h.get("mutation") and h["iteration"] > 0]
    if not past:
        return ""
    lines = []
    for h in past[-20:]:
        m = h["mutation"]
        icon = "✅" if h["kept"] else "↩"
        s = h["scores"]
        dims = (f"g{s.get('global',0):.0f} ag{s.get('age',0):.0f} oc{s.get('occupation',0):.0f} "
                f"ge{s.get('genre',0):.0f} mo{s.get('motif',0):.0f} di{s.get('distance',0):.0f}")
        # La cause de rejet (ex. « motif +12 », « cos=0.93 ») + sa CATÉGORIE
        # ([fond]/[bruit]/…) aident le mutateur à ne pas re-proposer une variante
        # déjà écartée sans sur-interpréter un simple rejet de non-significativité (D3).
        cause = h.get("reject_cause") or ""
        cause_str = ""
        if not h["kept"]:
            kind = reject_kind(h.get("verdict"), cause)
            tag = f"[{kind}]" if kind else ""
            body = f"{tag} {cause[:40]}".strip()
            cause_str = f" | ✗ {body}" if body else ""
        lines.append(f"  iter {h['iteration']:>2} | {icon} | {m.get('action','modify')[:7]:7s} | "
                     f"bloc={m.get('target_block','?'):18s} | "
                     f"comp={s.get('composite',0):.1f} [{dims}] | {m.get('rationale','')[:70]}{cause_str}")
    return ("\nHistorique des mutations (✅=acceptée ↩=rejetée — ne répète pas une tentative rejetée ;\n"
            "scores par dimension : g=global, ag=âge, oc=occupation, ge=genre, mo=motif, di=distance ;\n"
            f"catégorie de rejet : {_REJECT_KIND_LEGEND}) :\n"
            + "\n".join(lines) + "\n")


def _recent_blocks(history: Optional[list[dict]], window: int = 6) -> list[str]:
    """Blocs ciblés par les dernières mutations (acceptées ou non), du plus récent
    au plus ancien, dédupliqués. Le mutateur a tendance à re-cibler toujours le même
    bloc (souvent le premier bullet) ; cette liste nourrit une consigne de diversité.
    """
    if not history:
        return []
    seen: list[str] = []
    for h in reversed(history):
        name = (h.get("mutation") or {}).get("target_block")
        if name and name not in seen:
            seen.append(name)
        if len(seen) >= window:
            break
    return seen


_MUTATION_SYSTEM = f"""\
Tu es un expert en calibration de prompts pour des agents LLM simulant des comportements de déplacement urbain à Toulouse.

Ton rôle : proposer des modifications textuelles ciblées au prompt système afin de rapprocher la distribution modale produite par le LLM de la référence EMC² 2023 Toulouse.

{LEGEND_AND_SIGNS}

Contraintes absolues :
- N'introduis JAMAIS de pourcentages, de fréquences ou de parts modales explicites dans le prompt.
- N'introduis JAMAIS de règle à seuil chiffré ni de table de correspondance distance→mode. Le choix doit rester un raisonnement comportemental contextuel, jamais un automatisme déterministe lié à la distance.
- Les modifications doivent reposer uniquement sur des facteurs comportementaux (coût, confort, santé, praticité, sécurité, habitudes, contraintes familiales…).
- Chaque candidat modifie UN SEUL bloc (sauf merge_blocks qui en fusionne deux).
- Ne resoumets pas une mutation déjà rejetée, à l'identique NI en variante triviale (mêmes mots réordonnés) : elle recevrait le même verdict.
- Deux leviers comptent autant : RENFORCER un mode sous-représenté ET ATTÉNUER un mode sur-représenté.
- Deux priorités, dans l'ordre : (1) réduire l'écart à EMC² ; (2) raccourcir le prompt sans jamais dégrader le score.

Opérateurs disponibles (champ "action") :
- "modify"       : réécrire le contenu de "target_block".
- "delete"       : supprimer "target_block" (redondant ou nuisible).
- "insert"       : insérer un nouveau bloc ("new_content") juste après "target_block".
- "condense"     : réécrire "target_block" PLUS COURT à sens constant (économie de mots).
- "reorder"      : déplacer "target_block" juste après "anchor" ("__start__" = en tête).
- "merge_blocks" : fusionner "target_block" et "second_block" en un seul ("new_content").
- "split"        : scinder "target_block" en plusieurs blocs ("new_content" = parties séparées par une LIGNE VIDE).

DÉMARCHE — analyse des rejets AVANT de proposer :
- Relis d'abord l'« Historique des mutations » et la « Mémoire des leçons » : repère les raisons RÉCURRENTES pour lesquelles des tentatives ont été rejetées.
- Renseigne le champ "reflection" (2-3 phrases max) : la synthèse de ces raisons + ce que tu changes en conséquence. Elle te sera reservie au tour suivant : formule-la comme une consigne durable, pas comme un commentaire jetable.
- Tiens compte de la CATÉGORIE de rejet annotée dans l'historique :
  • [fond] (dégrade une dimension protégée, mutation inapplicable, cible déjà couverte, strate visée non améliorée) → il y a une vraie leçon : n'y retourne pas à l'identique.
  • [bruit]/[seuil]/[doublon] (gain non significatif au bootstrap ou au palier, composite non amélioré, trop proche d'un rejet récent) → l'idée n'est PAS invalidée sur le fond : garde le LEVIER (l'objectif visé), mais NE RESOUMETS JAMAIS le même texte ni une variante triviale (mêmes mots réarrangés = même verdict, essai gaspillé). La proposition concrète doit différer MATÉRIELLEMENT : renforce nettement l'argument, change de bloc-cible pour le même levier, ou combine-le à un autre. N'invente JAMAIS une leçon de fond à partir d'un rejet de bruit.
- Sers-toi de cette synthèse pour proposer un changement RÉELLEMENT distinct de ce qui a déjà été écarté.

Tu réponds UNIQUEMENT avec un objet JSON valide, sans markdown ni texte supplémentaire.\
"""


def build_mutation_user_msg(blocks: list[dict], df: Optional[pd.DataFrame],
                            best_score: Optional[float], cerema: dict,
                            history: Optional[list[dict]] = None,
                            ablation_results: Optional[list[dict]] = None,
                            n_candidates: int = 1,
                            suggested_operator: Optional[str] = None,
                            snippets: Optional[list[dict]] = None,
                            lessons: Optional[str] = None,
                            reflect: bool = True,
                            hard_negatives_k: int = 4) -> str:
    dist_str, worst_str = _gap_description(df, cerema)
    mutable_names = [b["name"] for b in blocks if b["mutable"]]
    blocks_display = "\n\n".join(f"=== {b['name']} ===\n{b['content']}"
                                 for b in blocks if b["mutable"])
    score_str = (f"Score composite actuel (meilleur) : {best_score:.2f}"
                 if best_score is not None else "Premier run")
    history_str = _history_summary(history) if history else ""
    ablation_str = format_ablation_for_mutation(ablation_results) if ablation_results else ""
    snippets_str = format_snippets_for_mutation(snippets)
    lessons_str = format_lessons(lessons) if reflect else ""
    hard_neg_str = format_hard_negatives(df, cerema, hard_negatives_k)
    worst_strata_str = ""
    if df is not None and not df.empty:
        rows = worst_strata_modes(df, cerema)
        if rows:
            wl = ["\n⚠️ Pires écarts strate × mode (actuel vs cible, impact décroissant) :"]
            for r in rows:
                d = "sur-représenté" if r["diff"] > 0 else "sous-représenté"
                wl.append(f"  {r['dim']}[{r['cat']}] · {r['mode']:22s} : {r['diff']:+5.1f} pts "
                          f"({d}, n={r['n']})")
            worst_strata_str = "\n".join(wl) + "\n"

    hint = ""
    if suggested_operator:
        hint = (f"\n💡 Opérateur à privilégier ce tour (le plus rentable jusqu'ici) : "
                f"\"{suggested_operator}\" — inclus-en au moins un candidat, mais "
                f"garde de la diversité.\n")

    diversity_str = ""
    recent = _recent_blocks(history)
    if recent:
        diversity_str = (
            f"\n⚖️ Diversité des cibles : les derniers tours ont surtout modifié "
            f"« {recent[0]} » (blocs récents : {', '.join(recent)}). Sauf si un levier "
            f"prioritaire impose de rester sur ce bloc, cible d'AUTRES blocs — ne te "
            f"contente pas de re-toucher le même à chaque itération.\n")

    # Champ "reflection" en tête du JSON : synthèse des rejets, commune aux candidats.
    refl_field = ('"reflection":"<synthèse courte des rejets précédents et de ce que '
                  'tu changes>",' if reflect else "")
    refl_intro = (" Commence par le champ \"reflection\" (analyse des rejets)." if reflect
                  else "")
    if n_candidates > 1:
        ask = (
            f"Propose {n_candidates} candidats DIVERS agissant sur les deux leviers, sans "
            f"seuil chiffré, chacun sur un bloc-cible DIFFÉRENT (varie aussi les opérateurs)."
            f"{refl_intro} JSON attendu :\n"
            f'{{{refl_field}"candidates":[{{"target_block":"<nom>","action":"modify",'
            f'"new_content":"<texte>","rationale":"<1 phrase>",'
            f'"second_block":"<pour merge_blocks>","anchor":"<pour reorder>"}}, …]}}')
    else:
        ask = (
            f"Propose UNE modification sur UN SEUL bloc agissant sur les deux leviers, "
            f"sans seuil chiffré.{refl_intro} JSON attendu :\n"
            f'{{{refl_field}"target_block":"<nom>","action":"modify","new_content":"<texte>",'
            f'"rationale":"<1 phrase>","second_block":"","anchor":""}}')

    return f"""Distribution LLM actuelle ({len(df) if df is not None else 0} décisions) :
{dist_str}

{worst_str}
{worst_strata_str}{hard_neg_str}{score_str}
{lessons_str}{history_str}{ablation_str}{snippets_str}{hint}{diversity_str}
Blocs modifiables (état actuel du meilleur prompt) :
{blocks_display}

Options de bloc : {mutable_names}

{ask}"""


# ── Merge / crossover (phase 6.3) ────────────────────────────────────────────

_CROSSOVER_SYSTEM = """\
Tu es un expert en calibration de prompts pour des agents LLM simulant des comportements de déplacement urbain à Toulouse.

Ton rôle : FUSIONNER deux prompts « parents » complémentaires en un seul prompt « enfant » qui combine leurs forces. Chaque parent est meilleur sur certaines dimensions (âge, occupation, genre, motif, distance) ; l'enfant doit hériter des blocs les plus utiles de chacun.

Contraintes absolues :
- N'introduis JAMAIS de pourcentages, de fréquences ou de parts modales explicites.
- N'introduis JAMAIS de règle à seuil chiffré ni de table distance→mode. Le choix reste un raisonnement comportemental contextuel.
- Ne réécris PAS le schéma JSON (il sera réattaché automatiquement) : ne produis que le corps du prompt système.
- Combine et déduplique : garde les meilleurs arguments de chaque parent, supprime les redondances, reste concis.

Tu réponds UNIQUEMENT avec un objet JSON valide : {"merged_prompt": "<texte du prompt fusionné, sans le schéma JSON>"}.\
"""


def _ablation_hint(ablation: Optional[list[dict]]) -> str:
    """Résumé court des blocs porteurs (Δ/φ élevé) d'un parent, pour guider le merge."""
    if not ablation:
        return "(pas d'analyse de contribution disponible)"
    useful = sorted((r for r in ablation if r.get("delta", 0) > 1.0),
                    key=lambda r: r["delta"], reverse=True)[:4]
    if not useful:
        return "(aucun bloc à forte contribution)"
    return "; ".join(f"{r['bloc']} (+{r['delta']:.1f})" for r in useful)


def build_crossover_user_msg(blocks_a: list[dict], blocks_b: list[dict],
                             ablation_a: Optional[list[dict]] = None,
                             ablation_b: Optional[list[dict]] = None) -> str:
    """Message de merge : corps des deux parents + leurs blocs porteurs."""
    from .blocks import blocks_to_prompt
    body_a = blocks_to_prompt([b for b in blocks_a if b["mutable"]])
    body_b = blocks_to_prompt([b for b in blocks_b if b["mutable"]])
    return f"""PARENT A (blocs porteurs : {_ablation_hint(ablation_a)}) :
\"\"\"
{body_a}
\"\"\"

PARENT B (blocs porteurs : {_ablation_hint(ablation_b)}) :
\"\"\"
{body_b}
\"\"\"

Fusionne A et B en un prompt système enfant qui combine leurs forces respectives,
sans le schéma JSON. Réponds en JSON : {{"merged_prompt": "<texte>"}}."""


def _extract_crossover_text(raw) -> str:
    """Normalise la sortie du merge (dict {merged_prompt|prompt|text} OU chaîne)."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        for key in ("merged_prompt", "prompt", "text", "content"):
            if isinstance(raw.get(key), str):
                return raw[key]
    return ""


def assemble_crossover(merged_text: str, locked_blocks: list[dict]) -> list[dict]:
    """Décompose le prompt fusionné et réattache les blocs verrouillés (schéma JSON).

    Le corps produit par le merge est décomposé comme un prompt seed (blocs
    mutables cohérents) ; tout ``json_schema`` qu'il contiendrait par erreur est
    écarté au profit des ``locked_blocks`` d'origine, préservés intacts en fin.
    """
    from .blocks import decompose_prompt
    body = [b for b in decompose_prompt(merged_text) if b["name"] != "json_schema"]
    locked = [b for b in locked_blocks if not b["mutable"]]
    return body + locked


def normalize_candidates(raw, n_candidates: int) -> list[dict]:
    """Normalise la sortie du mutateur (dict unique OU liste OU {"candidates":[…]}).

    Garantit une liste de dicts de mutation ; tolère les deux contrats (single =
    phase 3, multi = phase 4) et tronque à ``n_candidates``.
    """
    if isinstance(raw, dict) and "candidates" in raw:
        raw = raw["candidates"]
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    out = [c for c in raw if isinstance(c, dict) and c.get("target_block")]
    return out[:max(1, n_candidates)]


class MutationGenerator:
    """Propose une (ou k) mutation(s) via le modèle de mutation (Gemini par défaut, DG).

    ``mutate_fn(user_msg) -> dict|list`` est injectable ; par défaut l'appel HTTP
    Gemini est construit par :meth:`default` à partir de la config + clé d'API.
    ``propose`` (single, phase 3) et ``propose_candidates`` (multi, phase 4)
    partagent le même ``mutate_fn`` — seul le message change de forme.
    """

    def __init__(self, config: RunConfig, cerema: dict,
                 mutate_fn: Callable[[str], dict],
                 crossover_fn: Optional[Callable[[str], dict]] = None):
        self.config = config
        self.cerema = cerema
        self.mutate_fn = mutate_fn
        # Le merge (phase 6) partage l'appel par défaut si aucun ``crossover_fn``
        # dédié n'est fourni ; le contrat de sortie diffère (prompt fusionné).
        self.crossover_fn = crossover_fn or mutate_fn

    def propose(self, blocks: list[dict], df: Optional[pd.DataFrame],
                best_score: Optional[float], history: Optional[list[dict]] = None,
                ablation_results: Optional[list[dict]] = None,
                snippets: Optional[list[dict]] = None,
                lessons: Optional[str] = None) -> tuple[dict, str]:
        reflect = self.config.reflection_enabled
        user_msg = build_mutation_user_msg(blocks, df, best_score, self.cerema,
                                           history, ablation_results, snippets=snippets,
                                           lessons=lessons, reflect=reflect,
                                           hard_negatives_k=self.config.hard_negatives_k)
        raw = self.mutate_fn(user_msg)
        cands = normalize_candidates(raw, 1)
        mutation = cands[0] if cands else {}
        # La synthèse (champ ``reflection``) chevauche la mutation : la boucle
        # l'absorbe dans la mémoire de leçons (``run_state``) après proposition.
        reflection = extract_reflection(raw)
        if reflection and mutation:
            mutation["reflection"] = reflection
        return mutation, user_msg

    def propose_candidates(self, blocks: list[dict], df: Optional[pd.DataFrame],
                           best_score: Optional[float],
                           history: Optional[list[dict]] = None,
                           ablation_results: Optional[list[dict]] = None,
                           n_candidates: int = 4,
                           suggested_operator: Optional[str] = None,
                           snippets: Optional[list[dict]] = None,
                           lessons: Optional[str] = None,
                           ) -> tuple[list[dict], str]:
        """k candidats en UN appel (entonnoir DD). Renvoie ``(candidats, user_msg)``."""
        reflect = self.config.reflection_enabled
        user_msg = build_mutation_user_msg(
            blocks, df, best_score, self.cerema, history, ablation_results,
            n_candidates=n_candidates, suggested_operator=suggested_operator,
            snippets=snippets, lessons=lessons, reflect=reflect,
            hard_negatives_k=self.config.hard_negatives_k)
        raw = self.mutate_fn(user_msg)
        cands = normalize_candidates(raw, n_candidates)
        # Réflexion commune aux candidats : reportée sur chacun pour que le candidat
        # finalement retenu la porte jusqu'à la mémoire de leçons de la boucle.
        reflection = extract_reflection(raw)
        if reflection:
            for c in cands:
                c["reflection"] = reflection
        return cands, user_msg

    def propose_crossover(self, blocks_a: list[dict], blocks_b: list[dict],
                          ablation_a: Optional[list[dict]] = None,
                          ablation_b: Optional[list[dict]] = None,
                          ) -> tuple[Optional[list[dict]], str]:
        """Fusionne deux parents complémentaires en un prompt (merge, phase 6.3).

        Le mutateur reçoit les blocs modifiables des deux parents, informés de la
        valeur (ablation/Shapley) de chacun dans son lignage (« garde le bloc vélo
        du parent A, il porte +4 »), et rédige un prompt fusionné. Le résultat est
        décomposé puis les blocs **verrouillés** du parent A (schéma JSON) sont
        réattachés. Renvoie ``(blocs_fusionnés, user_msg)`` ou ``(None, user_msg)``
        si le mutateur ne renvoie rien d'exploitable.
        """
        user_msg = build_crossover_user_msg(blocks_a, blocks_b, ablation_a, ablation_b)
        raw = self.crossover_fn(user_msg)
        merged_text = _extract_crossover_text(raw)
        if not merged_text.strip():
            return None, user_msg
        locked = [b for b in blocks_a if not b["mutable"]]
        return assemble_crossover(merged_text, locked), user_msg

    @classmethod
    def default(cls, config: RunConfig, cerema: dict, api_key: str,
                base_url: str = "https://generativelanguage.googleapis.com/v1beta"
                ) -> "MutationGenerator":
        import httpx

        def _call(system: str, user_msg: str, max_tokens: int) -> dict:
            payload = {
                "contents": [{"role": "user", "parts": [{"text": user_msg}]}],
                "systemInstruction": {"parts": [{"text": system}]},
                "generationConfig": {"temperature": config.mutation_temp,
                                     "maxOutputTokens": max_tokens,
                                     "response_mime_type": "application/json"},
            }
            url = f"{base_url}/models/{config.mutation_model}:generateContent"
            headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
            for attempt in range(config.max_retries + 1):
                with httpx.Client(timeout=60.0) as client:
                    resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 429 and attempt < config.max_retries:
                    time.sleep(min(60, config.max_retry_wait))
                    continue
                resp.raise_for_status()
                candidate = resp.json()["candidates"][0]
                return json.loads(candidate["content"]["parts"][0]["text"])
            resp.raise_for_status()
            return {}

        def mutate_fn(user_msg: str) -> dict:
            return _call(_MUTATION_SYSTEM, user_msg, 1024)

        def crossover_fn(user_msg: str) -> dict:
            # Le prompt fusionné est plus long qu'une mutation ciblée.
            return _call(_CROSSOVER_SYSTEM, user_msg, 2048)

        return cls(config, cerema, mutate_fn, crossover_fn=crossover_fn)
