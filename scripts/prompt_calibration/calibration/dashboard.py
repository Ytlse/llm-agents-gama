"""Dashboard Streamlit — phase 2 du ticket 004 (D5).

Lecteur du store SQLite, rafraîchissable pendant un run. Toutes les vues sont en
**lecture pure** sauf Maintenance → import, qui peut écrire.

Un **filtre d'expérience** (branche) unique vit dans la barre latérale et
s'applique à toutes les vues. Sa clé de session (`exp_filter`) est stable → la
sélection **persiste au changement de vue** (pas de réinitialisation). « Toutes
les branches » lève le filtre ; les vues mono-branche (Run, Maintenance)
retombent sur la première branche quand aucune expérience n'est isolée. Vues :

- **Timeline** : toutes les mutations depuis l'origine (itération, branche,
  opérateur, bloc, rationale, verdict, score composite ET par dimension), avec
  filtres et courbe du meilleur score.
- **DAG** : graphe de lignée des prompts (un chemin par branche, merges visibles,
  nœud coloré par score) ; sélection d'un nœud → prompt, diff vs parent, scores,
  carte d'ablation (avec contribution de chaque dimension au Δ de chaque bloc).
- **Distribution** : parts modales actuel vs EMC² (global) et pires croisements
  strate × mode pour le nœud sélectionné.
- **Comparaison** : barres comparant les parts modales de plusieurs prompts
  (seed, meilleur, sélection libre) à la vérité terrain EMC², en global et par
  strate (âge, occupation, genre, motif, distance).
- **Run** : branche active, itération, modèles/températures, volumétrie d'éval.
- **Maintenance** : commandes `status` / `export` / `import` depuis l'UI. `status`
  et `export` sont en lecture seule ; `import` **écrit** dans le store (protégé par
  une case de confirmation).

Lancement (ne pas exécuter ce fichier directement) :

    calibrate dashboard --config run.yaml
    # ≡ streamlit run calibration/dashboard.py -- --config run.yaml

La logique de requête est dans ``dashboard_data.py`` (pure, testée). Ce module
ne fait que le rendu.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# ``streamlit run`` exécute ce fichier comme script (__main__), sans contexte de
# package → les imports relatifs échouent. On ajoute le dossier parent du package
# au chemin et on importe ``calibration`` en absolu.
_PKG_PARENT = Path(__file__).resolve().parents[1]
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

from calibration import dashboard_data as dd  # noqa: E402
from calibration.metrics import MODE_COLORS  # noqa: E402
from calibration.models import RunConfig  # noqa: E402
from calibration.store import RunStore  # noqa: E402

VERDICT_COLORS = {
    "accepted": "#22AA44", "rejected_score": "#EE4444", "rejected_stat": "#EE8844",
    "rejected_tabu": "#AA8844", "vetoed": "#BB44BB", "invalid": "#888888",
    "rejected_dup_block": "#777777", "rejected_gate": "#CC6644",
    "rejected_race": "#DDAA44", "proposed": "#4488CC",
}


# ── Chargement config / store ────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    # Streamlit passe les arguments du script après « -- ».
    argv = sys.argv[1:]
    p = argparse.ArgumentParser(prog="calibrate dashboard")
    p.add_argument("--config", type=Path, default=None)
    p.add_argument("--store", type=Path, default=None,
                   help="chemin du store (sinon store_path de la config)")
    args, _ = p.parse_known_args(argv)
    return args


@st.cache_resource
def _load_config(config_path: str | None) -> RunConfig:
    if config_path:
        return RunConfig.from_yaml(config_path)
    return RunConfig()


def _open_store(store_path: Path) -> RunStore:
    # Ouverture neuve à chaque rerun : le dashboard voit toujours l'état courant.
    return RunStore(store_path)


# ── Vues ─────────────────────────────────────────────────────────────────────

def view_timeline(store: RunStore, branch_filter: str | None = None) -> None:
    st.header("Timeline des mutations")
    df = dd.timeline_df(store)
    if branch_filter is not None:
        df = df[df["branch"] == branch_filter]
    if df.empty:
        st.info("Aucune mutation dans le store. Lancez `calibrate run` d'abord.")
        return

    c1, c2, c3 = st.columns(3)
    verdicts = sorted(df["verdict"].dropna().unique().tolist())
    sel_verdicts = c1.multiselect("Verdict", verdicts, default=verdicts)
    operators = sorted(df["operator"].dropna().unique().tolist())
    sel_ops = c2.multiselect("Opérateur", operators, default=operators)
    it_min, it_max = int(df["iteration"].min()), int(df["iteration"].max())
    if it_min < it_max:
        lo, hi = c3.slider("Itérations", it_min, it_max, (it_min, it_max))
    else:
        lo, hi = it_min, it_max

    mask = (df["verdict"].isin(sel_verdicts) & df["operator"].isin(sel_ops)
            & df["iteration"].between(lo, hi))
    fdf = df[mask].copy()

    st.subheader("Score composite & meilleur score")
    _plot_timeline_curve(df, fdf)

    st.subheader("Mutations")
    show_cols = ["iteration", "branch", "operator", "target_block", "verdict",
                 "composite", "best_so_far"] + dd.GUARDED_DIMS + \
                ["reject_cause", "rationale"]
    st.dataframe(fdf[show_cols].style.map(
        lambda v: f"color: {VERDICT_COLORS.get(v, '')}", subset=["verdict"]), hide_index=True, width='stretch')

    st.subheader("Détail d'une mutation")
    options = fdf["id"].tolist()
    if not options:
        st.caption("Aucune mutation à afficher dans la sélection.")
        return

    labels = {
        row["id"]: f"Iter {row['iteration']} ({row['branch']}) - {row['operator']} {row['target_block']}"
        for _, row in fdf.iterrows()
    }

    # Par défaut, la mutation en cours si elle existe, sinon la dernière.
    # « En cours » = la 'proposed' au plus grand id (la plus récente toutes
    # branches confondues) — une vieille 'proposed' orpheline d'une campagne
    # arrêtée ne doit pas masquer celle du run actif.
    current_mutation = fdf[fdf["verdict"] == "proposed"].sort_values("id").tail(1)
    default_id = None
    if not current_mutation.empty:
        default_id = current_mutation.iloc[0]["id"]

    default_index = options.index(default_id) if default_id in options else len(options) - 1

    selected_id = st.selectbox(
        "Choisir une mutation pour voir le prompt de demande :",
        options=options, format_func=lambda x: labels.get(x, x), index=default_index)

    if selected_id:
        selected = fdf[fdf["id"] == selected_id].iloc[0]
        is_current = selected["verdict"] == "proposed"
        expander_title = "▶️ Mutation en cours" if is_current else "Prompt de demande de mutation"
        with st.expander(expander_title, expanded=is_current):
            st.code(selected["mutation_prompt_text"], language="markdown")
        st.caption("Réponse du modèle de mutation :")
        st.json({"action": selected["operator"], "target_block": selected["target_block"],
                 "new_content": selected["new_content"], "rationale": selected["rationale"]})


def _plot_timeline_curve(full: pd.DataFrame, filtered: pd.DataFrame) -> None:
    import plotly.graph_objects as go
    fig = go.Figure()
    for branch, grp in full.groupby("branch", sort=False):
        ev = grp[grp["composite"].notna()]
        fig.add_trace(go.Scatter(
            x=ev["iteration"], y=ev["composite"], mode="markers",
            name=f"{branch} · composite", opacity=0.45,
            marker=dict(size=6,
                        color=[VERDICT_COLORS.get(v, "#888") for v in ev["verdict"]])))
        bs = grp[grp["best_so_far"].notna()]
        fig.add_trace(go.Scatter(
            x=bs["iteration"], y=bs["best_so_far"], mode="lines",
            name=f"{branch} · meilleur", line=dict(width=2)))
    fig.update_layout(height=380, xaxis_title="itération",
                      yaxis_title="composite (↓ = mieux)",
                      legend=dict(orientation="h", y=-0.25), margin=dict(t=10))
    st.plotly_chart(fig, width='stretch')


def view_dag(store: RunStore, branch_filter: str | None = None) -> None:
    st.header("DAG de lignée des prompts")
    nodes = dd.lineage_df(store)
    if branch_filter is not None:
        nodes = nodes[nodes["branch"] == branch_filter]
    if nodes.empty:
        st.info("Aucun nœud sur le chemin d'optimisation. Lancez `calibrate run`.")
        return
    edges = dd.lineage_edges(nodes)
    selected = _plot_dag(nodes, edges)

    st.divider()
    _node_panel(store, selected, all_nodes=nodes)


def _plot_dag(nodes: pd.DataFrame, edges: list) -> str:
    import plotly.graph_objects as go

    branch_order = sorted(nodes["branch"].unique().tolist())
    y_of = {b: i for i, b in enumerate(branch_order)}
    pos = {r["hash"]: (r["iteration"], y_of[r["branch"]])
           for _, r in nodes.iterrows()}

    fig = go.Figure()
    # Arêtes (merges en tireté).
    for parent, child, is_merge in edges:
        if parent not in pos or child not in pos:
            continue
        x0, y0 = pos[parent]
        x1, y1 = pos[child]
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[y0, y1], mode="lines", hoverinfo="skip",
            showlegend=False,
            line=dict(color="#BB44BB" if is_merge else "#BBBBBB",
                      width=1.5, dash="dash" if is_merge else "solid")))
    # Nœuds colorés par composite.
    comp = pd.to_numeric(nodes["composite"], errors="coerce")
    fig.add_trace(go.Scatter(
        x=nodes["iteration"], y=[y_of[b] for b in nodes["branch"]],
        mode="markers+text", showlegend=False,
        text=nodes["iteration"].astype(str), textposition="top center",
        customdata=nodes["hash"],
        hovertemplate="iter %{x} · %{customdata}<br>composite=%{marker.color:.2f}<extra></extra>",
        marker=dict(size=16, color=comp, colorscale="RdYlGn_r",
                    showscale=True, colorbar=dict(title="composite"),
                    line=dict(width=1, color="#333"))))
    fig.update_layout(
        height=340, margin=dict(t=10),
        xaxis_title="itération",
        yaxis=dict(tickmode="array", tickvals=list(y_of.values()),
                   ticktext=branch_order, title="branche"))

    event = st.plotly_chart(fig, on_select="rerun", key="dag", width='stretch')
    picked = _selection_hash(event)

    options = nodes["hash"].tolist()
    labels = {r["hash"]: f"iter {r['iteration']} · {r['branch']} · {r['hash'][:8]}"
              for _, r in nodes.iterrows()}
    default_idx = options.index(picked) if picked in options else len(options) - 1
    return st.selectbox("Nœud", options, index=default_idx,
                        format_func=lambda h: labels.get(h, h))


def _selection_hash(event) -> str | None:
    """Extrait le hash cliqué depuis l'événement de sélection Plotly (best-effort)."""
    try:
        points = event["selection"]["points"]
        for pt in points:
            cd = pt.get("customdata")
            if isinstance(cd, list):
                cd = cd[0] if cd else None
            if cd:
                return cd
    except (KeyError, TypeError, IndexError):
        pass
    return None


def _node_panel(store: RunStore, node_hash: str, all_nodes: pd.DataFrame) -> None:
    try:
        node_info = all_nodes[all_nodes["hash"] == node_hash].iloc[0]
    except IndexError:
        st.warning("Nœud introuvable dans la lignée.")
        return

    st.subheader(f"Nœud `{node_hash}` — branche {node_info['branch']}, "
                 f"itération {node_info['iteration']}")

    # --- Sélecteur de comparaison pour le diff ---
    previous_nodes = all_nodes[
        (all_nodes["branch"] == node_info["branch"]) &
        (all_nodes["iteration"] < node_info["iteration"])
    ].sort_values("iteration", ascending=False)

    parent_hash = node_info["parent"]
    # Nœud seed : parent absent (None, ou NaN — truthy ! — via pandas).
    if not isinstance(parent_hash, str) or not parent_hash:
        parent_hash = None
    options = {parent_hash: f"Parent ({parent_hash[:8]})"} if parent_hash else {}
    options.update({
        r["hash"]: f"iter {r['iteration']} · {r['hash'][:8]}"
        for _, r in previous_nodes.iterrows()
        if r["hash"] != parent_hash
    })
    option_keys = list(options.keys())
    option_keys.append("")  # Pour "Aucun"
    options[""] = "Aucun"

    compare_to_hash = st.selectbox(
        "Comparer avec",
        options=option_keys,
        format_func=lambda h: options.get(h, h),
        index=0,
        key=f"compare_{node_hash}"
    )

    detail = dd.node_detail(store, node_hash, compare_to_hash=compare_to_hash)
    if detail is None:
        st.warning("Nœud introuvable.")
        return

    tab_prompt, tab_diff, tab_scores, tab_abl = st.tabs(["Prompt", "Diff", "Scores", "Ablation"])
    with tab_prompt:
        st.code(detail["prompt_text"], language="markdown")
    with tab_diff:
        if detail["diff"]:
            st.code(detail["diff"], language="diff")
        elif compare_to_hash:
            st.caption("Pas de différence.")
        else:
            st.caption("Nœud seed ou aucune comparaison sélectionnée.")
    with tab_scores:
        scores = detail["scores_by_dataset"]
        if scores:
            srows = [{"jeu": ds, **{d: sc.get(d) for d in dd.SCORE_DIMS}}
                     for ds, sc in scores.items()]
            st.dataframe(pd.DataFrame(srows), hide_index=True, width='stretch')
        else:
            st.caption("Aucun score pour ce nœud.")
    with tab_abl:
        if detail["ablations"]:
            adf = dd.ablation_table(detail)
            # Correction pour ArrowTypeError : forcer les colonnes en numérique.
            num_cols = [c for c in adf.columns if c not in ("bloc", "method", "diag")]
            adf[num_cols] = adf[num_cols].apply(pd.to_numeric, errors="coerce").round(1)
            dim_cols = [c for c in num_cols if c != "value"]
            st.dataframe(
                adf.sort_values("value", ascending=False, na_position="last")
                   .style.background_gradient(cmap="RdYlGn", subset=dim_cols,
                                              vmin=-5, vmax=5, axis=None),
                hide_index=True, width='stretch')
            st.caption("value = Δ composite si le bloc est retiré "
                       "(↑ = bloc utile, ≈ 0 = candidat à la compaction). "
                       "Colonnes de dimension : contribution pondérée de chaque "
                       "dimension à ce Δ, en pts de composite (elles somment à value ; "
                       "vert = le bloc aide cette dimension, rouge = il la dégrade).")
        else:
            st.caption("Aucune ablation enregistrée pour ce nœud.")


def view_distribution(store: RunStore, config: RunConfig,
                      branch_filter: str | None = None) -> None:
    st.header("Distribution modale vs EMC²")
    nodes = dd.lineage_df(store)
    if branch_filter is not None:
        nodes = nodes[nodes["branch"] == branch_filter]
    if nodes.empty:
        st.info("Aucun nœud évalué.")
        return
    labels = {r["hash"]: f"iter {r['iteration']} · {r['branch']} · {r['hash'][:8]}"
              for _, r in nodes.iterrows()}
    node_hash = st.selectbox("Nœud", nodes["hash"].tolist(),
                             index=len(nodes) - 1,
                             format_func=lambda h: labels.get(h, h))
    try:
        cerema, meta = dd.load_context(config)
    except (FileNotFoundError, OSError) as exc:
        st.error(f"Ressources introuvables (cerema/jeux gelés) : {exc}")
        return

    view = dd.distribution_view(store, node_hash, cerema, meta)
    if view is None:
        st.info("Pas de décisions train stockées pour ce nœud.")
        return

    st.caption(f"{view['n_decisions']} décisions")
    _plot_global_bars(view["global_bars"])

    st.subheader("Pires croisements strate × mode")
    if view["worst_strata"]:
        wdf = pd.DataFrame(view["worst_strata"])
        wdf = wdf[["dim", "cat", "mode", "actual", "target", "diff", "n", "impact"]]
        st.dataframe(wdf.round(1), hide_index=True, width='stretch')
    else:
        st.caption("Aucune strate au-dessus du seuil d'effectif.")


def _plot_global_bars(bars: list[dict]) -> None:
    import plotly.graph_objects as go
    modes = [b["mode"] for b in bars]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=modes, y=[b["actual"] for b in bars], name="actuel",
                         marker_color=[MODE_COLORS.get(m, "#888") for m in modes]))
    fig.add_trace(go.Bar(x=modes, y=[b["target"] for b in bars], name="EMC² cible",
                         marker_color="#CCCCCC"))
    fig.update_layout(barmode="group", height=340, yaxis_title="part modale (%)",
                      margin=dict(t=10), legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig, width='stretch')


def view_comparison(store: RunStore, config: RunConfig,
                    branch_filter: str | None = None) -> None:
    """Barres de comparaison : parts modales de plusieurs prompts vs EMC² (vérité
    terrain), en global et par strate (âge, occupation, genre, motif, distance)."""
    st.header("Comparaison prompts vs vérité terrain (EMC²)")
    nodes = dd.lineage_df(store)
    if branch_filter is not None:
        nodes = nodes[nodes["branch"] == branch_filter]
    if nodes.empty:
        st.info("Aucun nœud évalué.")
        return

    labels = {r["hash"]: f"iter {r['iteration']} · {r['branch']} · {r['hash'][:8]}"
              for _, r in nodes.iterrows()}
    # Défaut : le seed (première itération) et le meilleur composite train.
    defaults = []
    seed_row = nodes.sort_values("iteration").iloc[0]
    defaults.append(seed_row["hash"])
    comp = pd.to_numeric(nodes["composite"], errors="coerce")
    if comp.notna().any():
        best_hash = nodes.loc[comp.idxmin(), "hash"]
        if best_hash not in defaults:
            defaults.append(best_hash)

    c1, c2 = st.columns([3, 1])
    selected = c1.multiselect("Prompts à comparer", nodes["hash"].tolist(),
                              default=defaults, format_func=lambda h: labels.get(h, h))
    dimension = c2.selectbox("Dimension", ["global"] + list(dd.DIM_COLUMNS))
    if not selected:
        st.caption("Sélectionner au moins un prompt.")
        return

    try:
        cerema, meta = dd.load_context(config)
    except (FileNotFoundError, OSError) as exc:
        st.error(f"Ressources introuvables (cerema/jeux gelés) : {exc}")
        return

    view = dd.comparison_view(store, selected, cerema, meta, dimension)
    if view["missing"]:
        st.warning("Sans décisions train stockées (ignorés) : "
                   + ", ".join(labels.get(h, h) for h in view["missing"]))

    shown = [h for h in selected if h not in view["missing"]]
    if not shown:
        return
    scores = {h: nodes.loc[nodes["hash"] == h, "composite"].iloc[0] for h in shown}
    st.caption(" · ".join(
        f"{labels[h]} (composite {float(s):.1f})" if s is not None else labels[h]
        for h, s in scores.items()))

    cats = view["categories"]
    if dimension == "global":
        _plot_comparison_bars(cats[0], shown, labels, height=380)
        return
    # Une strate = un graphique, deux par ligne.
    for i in range(0, len(cats), 2):
        cols = st.columns(2)
        for col, cat in zip(cols, cats[i:i + 2]):
            with col:
                n_str = ", ".join(f"{labels[h].split(' · ')[0]}: n={cat['n'].get(h, 0)}"
                                  for h in shown)
                st.markdown(f"**{cat['cat']}**  \n:gray[{n_str}]")
                _plot_comparison_bars(cat, shown, labels, height=280)


def _plot_comparison_bars(cat: dict, node_hashes: list[str],
                          labels: dict[str, str], height: int = 340) -> None:
    import plotly.graph_objects as go
    modes = [b["mode"] for b in cat["bars"]]
    fig = go.Figure()
    for h in node_hashes:
        fig.add_trace(go.Bar(x=modes, y=[b["values"].get(h) for b in cat["bars"]],
                             name=labels.get(h, h)))
    fig.add_trace(go.Bar(x=modes, y=[b["target"] for b in cat["bars"]],
                         name="EMC² (vérité terrain)", marker_color="#999999"))
    fig.update_layout(barmode="group", height=height, yaxis_title="part modale (%)",
                      margin=dict(t=10, b=10),
                      legend=dict(orientation="h", y=-0.25))
    st.plotly_chart(fig, width='stretch',
                    key=f"cmp_{cat['cat']}_{len(node_hashes)}")


def view_run(store: RunStore, config: RunConfig, branch: str) -> None:
    st.header("État du run")
    status = dd.run_status(store, branch)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Itération", status["iteration"] if status["iteration"] is not None else "—")
    c2.metric("Acceptées", status["accepted"] if status["accepted"] is not None else "—")
    best = status["best_score"]
    c3.metric("Meilleur composite", f"{best:.2f}" if isinstance(best, (int, float)) else "—")
    vb = status["val_best"]
    c4.metric("Meilleur val", f"{vb:.2f}" if isinstance(vb, (int, float)) else "—")

    st.subheader("Configuration")
    st.table(pd.DataFrame([
        {"paramètre": "modèle d'éval", "valeur": config.eval_model},
        {"paramètre": "température d'éval", "valeur": config.eval_temp},
        {"paramètre": "modèle de mutation", "valeur": config.mutation_model},
        {"paramètre": "température de mutation", "valeur": config.mutation_temp},
        {"paramètre": "early-stop patience", "valeur": config.early_stop_patience},
        {"paramètre": "val_no_improve", "valeur": status["val_no_improve"]},
    ]))

    st.subheader("Volumétrie")
    c1, c2, c3 = st.columns(3)
    c1.metric("Nœuds (branche)", status["n_nodes"])
    c2.metric("Mutations (branche)", status["n_mutations"])
    c3.metric("Évals stockées", sum(status["eval_counts"].values()))
    if status["eval_counts"]:
        st.table(pd.DataFrame(
            [{"jeu": k, "évals": v} for k, v in status["eval_counts"].items()]))


def view_pareto(store: RunStore, config: RunConfig,
                branch_filter: str | None = None) -> None:
    """Front de Pareto (compromis non dominés) + bibliothèque de snippets (phase 6)."""
    st.header("Archive de Pareto & bibliothèque")
    dims = list(getattr(config, "pareto_dims", None) or [])
    view = dd.pareto_view(store, dims or None)
    # Dominance calculée toutes branches ; l'affichage se restreint à l'exp filtrée
    # (``on_front`` conserve son sens global : nœud de cette exp sur le front global).
    if branch_filter is not None:
        view = dict(view)
        view["items"] = [it for it in view["items"] if it.get("branch") == branch_filter]
        view["front"] = [it for it in view["front"] if it.get("branch") == branch_filter]
    st.caption(f"{len(view['front'])} nœuds non dominés sur {len(view['items'])} évalués "
               f"— dimensions : {', '.join(view['dims'])}")
    if not view["items"]:
        st.info("Aucun nœud évalué : lancer une campagne d'abord.")
        return

    axes = view["dims"]
    if len(axes) >= 2:
        import plotly.graph_objects as go
        xa = st.selectbox("Axe X", axes, index=0)
        ya = st.selectbox("Axe Y", axes, index=1)
        pts = pd.DataFrame(view["items"])
        fig = go.Figure()
        dom = pts[~pts["on_front"]]
        fro = pts[pts["on_front"]]
        if not dom.empty:
            fig.add_trace(go.Scatter(x=dom[xa], y=dom[ya], mode="markers",
                                     name="dominé", marker=dict(color="lightgray", size=7),
                                     text=dom["hash"]))
        if not fro.empty:
            fig.add_trace(go.Scatter(x=fro[xa], y=fro[ya], mode="markers+text",
                                     name="front de Pareto",
                                     marker=dict(color="crimson", size=11),
                                     text=fro["branch"], textposition="top center"))
        fig.update_layout(xaxis_title=f"{xa} (↓ mieux)", yaxis_title=f"{ya} (↓ mieux)",
                          height=460)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Nœuds du front (compromis complémentaires)")
    front_df = pd.DataFrame(view["front"])
    if not front_df.empty:
        cols = ["hash", "branch", "iteration", "composite"] + [
            d for d in view["dims"] if d in front_df.columns]
        st.dataframe(front_df[[c for c in cols if c in front_df.columns]],
                     use_container_width=True)

    st.subheader("Bibliothèque d'arguments comportementaux (DL)")
    snips = dd.snippets_df(store)
    if snips.empty:
        st.caption("Vide : elle se remplit des blocs acceptés avec gain significatif.")
    else:
        st.caption(f"{len(snips)} snippet(s) capitalisé(s), triés par gain observé.")
        st.dataframe(snips, use_container_width=True)


def view_maintenance(store: RunStore, config: RunConfig, branch: str) -> None:
    """Exécute les commandes CLI ``status`` / ``export`` / ``import`` depuis l'UI.

    ``status`` et ``export`` sont en lecture seule ; ``import`` **écrit** dans le
    store (seule exception au principe de lecteur pur) → protégé par une case de
    confirmation et un avertissement.
    """
    st.header("Maintenance")

    st.subheader("Statut")
    status = dd.run_status(store, branch)
    st.table(pd.DataFrame([
        {"clé": "branche", "valeur": branch},
        {"clé": "itération", "valeur": status["iteration"]},
        {"clé": "acceptées", "valeur": status["accepted"]},
        {"clé": "nœuds (branche)", "valeur": status["n_nodes"]},
        {"clé": "mutations (branche)", "valeur": status["n_mutations"]},
        {"clé": "évals stockées", "valeur": sum(status["eval_counts"].values())},
    ]))

    st.subheader("Export lisible")
    st.caption("Écrit `nodes.csv`, `mutations.csv`, `history.md` (lecture seule).")
    default_out = str(Path(config.store_path).parent / "export")
    out_dir = st.text_input("Répertoire d'export", value=default_out, key="mnt_export_out")
    if st.button("Exporter"):
        out = dd.export_readable(store, out_dir)
        st.success(f"Export → {out}")
        for name in ("nodes.csv", "mutations.csv", "history.md"):
            f = out / name
            if f.exists():
                st.download_button(f"⬇ {name}", f.read_bytes(), file_name=name,
                                   key=f"dl_{name}")

    st.subheader("Import d'un ancien run")
    st.caption("⚠ **Écrit dans le store.** À éviter pendant qu'une campagne écrit "
               "sur la même branche.")
    legacy_dir = st.text_input("Répertoire du run legacy", key="mnt_import_dir")
    confirm = st.checkbox("Je confirme l'écriture dans le store", key="mnt_import_confirm")
    if st.button("Importer", disabled=not (legacy_dir and confirm)):
        try:
            summary = dd.import_legacy_run(store, config, legacy_dir)
            st.success(f"Import terminé : {summary}")
        except (FileNotFoundError, KeyError) as exc:
            st.error(f"Import impossible : {exc}")


# ── Point d'entrée ───────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(page_title="Calibration — dashboard", layout="wide")
    args = _parse_args()
    config = _load_config(str(args.config) if args.config else None)
    store_path = args.store or config.store_path

    st.sidebar.title("Prompt calibration")
    st.sidebar.caption(f"store : `{store_path}`")
    if not Path(store_path).exists():
        st.error(f"Store introuvable : {store_path}")
        st.stop()

    store = _open_store(store_path)
    all_branches = dd.branches(store) or [config.branch]

    # Filtre d'expérience (branche) — global et persistant entre les vues. La clé
    # stable ``exp_filter`` en session_state fait que la sélection ne se
    # réinitialise pas quand on change de page : le selectbox de la barre latérale
    # est rendu à chaque rerun, donc Streamlit lui réinjecte sa valeur mémorisée.
    ALL_BRANCHES = "Toutes les branches"
    exp = st.sidebar.selectbox("Expérience", [ALL_BRANCHES] + all_branches,
                               key="exp_filter")
    branch_filter = None if exp == ALL_BRANCHES else exp
    # Vues mono-branche (Run / Maintenance) : la branche filtrée, sinon la première.
    active_branch = branch_filter or all_branches[0]
    if st.sidebar.button("↻ Rafraîchir"):
        st.rerun()

    # Vue pilotable par query param (?view=DAG) → liens partageables/bookmarkables,
    # synchronisée dans les deux sens avec le radio de la barre latérale.
    views = ["Timeline", "DAG", "Distribution", "Comparaison", "Pareto", "Run",
             "Maintenance"]
    qp = st.query_params.get("view")
    if qp in views and qp != st.session_state.get("_qp_view"):
        st.session_state["view"] = qp          # l'URL a changé → le radio suit
    st.session_state["_qp_view"] = qp
    st.session_state.setdefault("view", "Timeline")
    view = st.sidebar.radio("Vue", views, key="view")
    if st.query_params.get("view") != view:
        st.query_params["view"] = view          # le radio a changé → l'URL suit

    if view == "Timeline":
        view_timeline(store, branch_filter)
    elif view == "DAG":
        view_dag(store, branch_filter)
    elif view == "Distribution":
        view_distribution(store, config, branch_filter)
    elif view == "Comparaison":
        view_comparison(store, config, branch_filter)
    elif view == "Pareto":
        view_pareto(store, config, branch_filter)
    elif view == "Maintenance":
        view_maintenance(store, config, active_branch)
    else:
        view_run(store, config, active_branch)
    store.close()


if __name__ == "__main__":
    main()
