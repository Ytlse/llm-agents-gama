"""Tableau de bord de pilotage — Streamlit.

Volets :
  🏠 Vue d'ensemble — les feux de l'état courant : services, run, providers,
                 calibration, git, jobs. Répond à « est-ce que ça tourne ? ».
  🎮 Run GAMA   — le run en cours ou le dernier : progression des agents,
                 santé des logs, cache LLM, lancement/arrêt.
  🤖 Providers — quotas et disponibilité des providers LLM, rafraîchissement
                 de providers.yaml (`make providers`).
  ▶ Commandes  — lance les cibles `make` de la racine, de prompt_calibration et
                 d'otp-toulouse, avec suivi de sortie en direct et arrêt propre.
  🎫 Tickets   — état des tickets de docs/tickets/.
  📊 Métriques — services Docker, santé d'un run au choix, scores de synthèse,
                 avancement des campagnes de calibration.

Lancement : `make dashboard` depuis la racine du dépôt.
"""

from __future__ import annotations

import shlex
import subprocess
from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# Exécutable via `streamlit run scripts/dashboard/app.py` : le dossier du script
# est sur sys.path, mais pas la racine du dépôt — d'où les imports relatifs au
# package quand il est disponible, absolus sinon.
try:  # pragma: no cover
    from scripts.dashboard import live, makefiles, metrics, palette, runner, tickets
except ImportError:  # pragma: no cover
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.dashboard import live, makefiles, metrics, palette, runner, tickets

REPO_ROOT = Path(__file__).resolve().parents[2]

st.set_page_config(page_title="Pilotage llm-agents-gama", page_icon="🚦", layout="wide")


# ── Thème ─────────────────────────────────────────────────────────────────────
def is_dark() -> bool:
    """Thème actif de l'application, pour choisir les pas de couleur des graphes.

    `theme.base` (posé par `make dashboard`) fait foi : c'est le thème que le
    frontend applique réellement. `st.context.theme`, lui, rapporte la
    préférence du navigateur, qui diverge dès qu'une option `--theme.*` est
    passée — d'où des libellés blancs sur fond clair si on s'y fie.
    """
    try:
        base = st.get_option("theme.base")
    except Exception:  # pragma: no cover
        base = None
    if base in ("light", "dark"):
        return base == "dark"
    try:
        return (st.context.theme.type or "light") == "dark"
    except Exception:  # pragma: no cover — versions sans st.context.theme
        return False


DARK = is_dark()
INK = "#ffffff" if DARK else "#0b0b0b"
INK_SOFT = "#c3c2b7" if DARK else "#52514e"


@st.cache_resource
def get_registry() -> runner.Registry:
    return runner.Registry()


REGISTRY = get_registry()


@st.cache_data(ttl=30, show_spinner=False)
def cached_targets():
    projects, targets = makefiles.all_targets()
    return projects, targets


@st.cache_data(ttl=15, show_spinner=False)
def cached_docker():
    return metrics.docker_status()


@st.cache_data(ttl=30, show_spinner=False)
def cached_runs():
    return metrics.list_runs()


@st.cache_data(ttl=60, show_spinner="Lecture de moves.csv…")
def cached_moves(run_path: str):
    return metrics.moves_stats(Path(run_path))


@st.cache_data(show_spinner="Dépouillement du log…")
def cached_log_counts(log_path: str, size: int, mtime: float):
    """Clé de cache = (chemin, taille, mtime) : un log qui grossit est relu."""
    return metrics.log_counts(Path(log_path))


@st.cache_data(ttl=30, show_spinner=False)
def cached_synthesis():
    return metrics.synthesis_summary()


@st.cache_data(ttl=30, show_spinner=False)
def cached_calibration():
    return metrics.calibration_stores()


@st.cache_data(ttl=30, show_spinner=False)
def cached_git():
    return metrics.git_state()


# ── Caches « temps réel » (TTL courts, sondes locales) ───────────────────────
@st.cache_data(ttl=5, show_spinner=False)
def cached_run_process():
    return live.run_process()


@st.cache_data(ttl=5, show_spinner=False)
def cached_health():
    return live.api_health()


@st.cache_data(ttl=5, show_spinner=False)
def cached_controller_stats():
    return live.controller_stats()


@st.cache_data(show_spinner=False)
def cached_agent_states(run_path: str, mtime: float):
    """Clé = (run, mtime du CSV) : relu seulement quand le fichier change."""
    return metrics.agent_states(Path(run_path))


@st.cache_data(show_spinner=False)
def cached_top_errors(log_path: str, level: str, mtime: float):
    return metrics.top_log_messages(Path(log_path), level=level)


@st.cache_data(ttl=60, show_spinner=False)
def cached_llm_errors(run_path: str):
    return metrics.llm_errors_stats(Path(run_path))


@st.cache_data(ttl=60, show_spinner=False)
def cached_cache_hit_rate(run_path: str):
    return metrics.llm_cache_hit_rate(Path(run_path))


@st.cache_data(ttl=30, show_spinner=False)
def cached_providers_static():
    return metrics.providers_static()


@st.cache_data(ttl=15, show_spinner=False)
def cached_calib_progress():
    return metrics.calib_progress()


@st.cache_data(show_spinner=False)
def cached_ga_details(store_path: str, mtime: float):
    """Clé = (store, mtime) : relu après chaque `pull-db`."""
    return metrics.ga_details(Path(store_path))


def make_action(
    label: str,
    target_name: str,
    *,
    project: str = "root",
    values: dict[str, str] | None = None,
    key: str | None = None,
    disabled: bool = False,
    help: str | None = None,
) -> None:
    """Bouton contextuel : lance une cible make via le registre de jobs.

    C'est le même chemin que le volet ▶ Commandes (mêmes drapeaux, même log
    dans 📟 Lancements) — seul l'emplacement du bouton change."""
    if st.button(label, key=key or f"act-{project}-{target_name}", width="stretch", disabled=disabled, help=help):
        _, targets = cached_targets()
        target = next((t for t in targets.get(project, []) if t.name == target_name), None)
        if target is None:
            st.error(f"Cible `{target_name}` introuvable dans le Makefile `{project}`.")
            return
        REGISTRY.launch(target.key, target.command(values or {}), target.cwd, target.flags)
        st.toast(f"make {target_name} lancé — suivi dans 📟 Lancements")


def run_make_inline(target: str, values: dict[str, str], *, project: str = "root", timeout: int = 120) -> str:
    """Exécute une cible make en direct et retourne sa sortie — pour les
    consultations courtes dont on veut le résultat dans la page (SSH vers la
    VM, statut…), pas pour les cibles longues."""
    cwd = REPO_ROOT / "prompt_calibration" if project == "calib" else REPO_ROOT
    argv = ["make", target, *(f"{k}={v}" for k, v in values.items() if v)]
    try:
        proc = subprocess.run(  # noqa: S603 — cible et variables contrôlées
            argv, cwd=str(cwd), capture_output=True, text=True, timeout=timeout
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return f"$ {' '.join(argv)}\n⏱ {exc}"
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return f"$ {' '.join(argv)}\n\n" + (out or f"(aucune sortie — code retour {proc.returncode})")


def current_run() -> metrics.RunInfo | None:
    runs = cached_runs()
    return runs[0] if runs and runs[0].is_current else None


def age_label(moment: datetime) -> str:
    seconds = max(0, int((datetime.now() - moment).total_seconds()))
    if seconds < 90:
        return f"il y a {seconds} s"
    if seconds < 5400:
        return f"il y a {seconds // 60} min"
    return f"il y a {seconds // 3600} h {(seconds % 3600) // 60:02d}"


def status_dot(kind: str) -> str:
    return {"good": "🟢", "warning": "🟠", "critical": "🔴", "muted": "⚪"}.get(kind, "⚪")


# ── Barre latérale ────────────────────────────────────────────────────────────
@st.fragment(run_every="2s")
def render_sidebar_jobs() -> None:
    """Compteur de jobs, rafraîchi sans relancer toute la page."""
    running = REGISTRY.running_count()
    st.metric("Jobs en cours", running)
    if running and st.button("⏹ Tout arrêter", width="stretch"):
        stopped = REGISTRY.stop_all()
        st.warning(f"{stopped} job(s) arrêté(s)")


def render_sidebar() -> None:
    git = cached_git()
    st.sidebar.markdown("### 🚦 Pilotage")
    st.sidebar.caption(f"`{REPO_ROOT}`")
    st.sidebar.markdown(
        f"**Branche** `{git['branch']}`  \n"
        f"**HEAD** {git['head'] or '—'}  \n"
        f"**Fichiers modifiés** {git['dirty']}"
    )
    st.sidebar.divider()

    with st.sidebar:
        render_sidebar_jobs()
    if st.sidebar.button("🔄 Rafraîchir les métriques", width="stretch"):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.divider()
    st.sidebar.caption(
        "Les logs des lancements sont conservés dans "
        "`experiments/.dashboard/`. Documentation : `docs/arch/dashboard.md`."
    )


# ── Volet Commandes ───────────────────────────────────────────────────────────
def variable_inputs(target: makefiles.Target, catalogue: dict[str, makefiles.Variable]) -> dict[str, str]:
    """Champs de saisie des variables `make` proposées pour une cible."""
    values: dict[str, str] = {}
    specs = [catalogue[name] for name in target.variables if name in catalogue]
    if not specs:
        return values

    for chunk_start in range(0, len(specs), 3):
        cols = st.columns(3)
        for col, spec in zip(cols, specs[chunk_start : chunk_start + 3]):
            widget_key = f"var-{target.key}-{spec.name}"
            with col:
                if spec.kind == "bool":
                    if st.checkbox(spec.name, help=spec.help, key=widget_key):
                        values[spec.name] = "1"
                elif spec.kind == "choice" and spec.choices:
                    choice = st.selectbox(
                        spec.name,
                        ("(défaut)", *spec.choices),
                        help=spec.help,
                        key=widget_key,
                    )
                    if choice != "(défaut)":
                        values[spec.name] = choice
                else:
                    text = st.text_input(
                        spec.name, help=spec.help, placeholder=spec.placeholder, key=widget_key
                    )
                    if text.strip():
                        values[spec.name] = text.strip()
    return values


def shell_line(target: makefiles.Target, argv: list[str]) -> str:
    rel = target.cwd.relative_to(REPO_ROOT).as_posix()
    prefix = f"cd {rel} && " if rel != "." else ""
    return prefix + " ".join(argv)


def render_target(target: makefiles.Target, catalogue: dict[str, makefiles.Variable]) -> None:
    badges = " ".join(makefiles.FLAG_LABELS[f][0] for f in target.flags if f in makefiles.FLAG_LABELS)
    notes = " · ".join(
        f"{makefiles.FLAG_LABELS[f][0]} {makefiles.FLAG_LABELS[f][1]}"
        for f in target.flags
        if f in makefiles.FLAG_LABELS
    )

    head, action = st.columns([6, 1], vertical_alignment="center")
    with head:
        st.markdown(f"**`make {target.name}`** {badges}")
        caption = " — ".join(part for part in (target.doc, notes) if part)
        if caption:
            st.caption(caption)

    values: dict[str, str] = {}
    confirmed = True
    with head.expander("Options et commande", expanded=not target.launchable):
        values = variable_inputs(target, catalogue)
        extra = st.text_input(
            "Autres variables `make`",
            placeholder="CLÉ=valeur CLÉ2=valeur2",
            key=f"extra-{target.key}",
        )
        for token in shlex.split(extra) if extra.strip() else []:
            if "=" in token:
                key, _, val = token.partition("=")
                values[key.strip()] = val
        if "danger" in target.flags:
            confirmed = st.checkbox(
                "Je confirme : cette cible supprime des données", key=f"confirm-{target.key}"
            )
        st.code(shell_line(target, target.command(values)), language="bash")
        if not target.launchable:
            st.caption("Cette cible pose une question au clavier : copiez la commande dans un terminal.")

    argv = target.command(values)
    with action:
        if not target.launchable:
            st.button("Terminal requis", key=f"run-{target.key}", disabled=True, width="stretch")
        elif st.button("▶ Lancer", key=f"run-{target.key}", disabled=not confirmed, width="stretch"):
            REGISTRY.launch(f"{target.project}:{target.name}", argv, target.cwd, target.flags)
            st.session_state["last_job_label"] = f"make {target.name}"
            st.rerun()


def render_commands() -> None:
    projects, targets = cached_targets()
    labels = {p.label: p for p in projects}
    chosen = st.radio("Projet", list(labels), horizontal=True, label_visibility="collapsed")
    project = labels[chosen]
    project_targets = targets.get(project.key, [])

    if not project_targets:
        st.warning(f"Aucune cible lue dans `{project.makefile}`.")
        return

    groups = makefiles.grouped(project_targets)
    st.caption(
        f"{len(project_targets)} cibles lues dans "
        f"`{project.makefile.relative_to(REPO_ROOT)}` — {len(groups)} groupes."
    )
    for group, group_targets in groups:
        with st.expander(f"{group} — {len(group_targets)} cibles", expanded=(group == "Docker")):
            for target in group_targets:
                render_target(target, project.variables)


# ── Panneau des jobs ──────────────────────────────────────────────────────────
def render_job(job: runner.Job, expanded: bool) -> None:
    icon = {"en cours": "⏳", "ok": "🟢", "échec": "🔴", "arrêté": "⚫", "erreur": "🔴"}[job.state]
    title = f"{icon} {job.label} — {job.state} · {runner.format_duration(job.duration)}"
    with st.expander(title, expanded=expanded):
        info, action = st.columns([5, 1], vertical_alignment="center")
        info.code(f"{job.command_line}   (cwd: {job.cwd})", language="bash")
        if job.running:
            if action.button("⏹ Stop", key=f"stop-{job.id}", width="stretch"):
                REGISTRY.stop(job.id)
                st.rerun()
        elif job.returncode is not None:
            action.metric("Code retour", job.returncode)
        if job.error:
            st.error(job.error)
        st.code(runner.tail(job), language="log")
        st.caption(f"Log complet : `{job.log_path.relative_to(REPO_ROOT)}`")


@st.fragment(run_every="2s")
def render_jobs_live() -> None:
    jobs = REGISTRY.jobs()
    running = [j for j in jobs if j.running]
    if not jobs:
        st.info("Aucun lancement pour l'instant. Choisissez une cible dans **▶ Commandes**.")
        return

    head, action = st.columns([5, 1], vertical_alignment="center")
    head.markdown(f"**{len(running)} en cours** · {len(jobs) - len(running)} terminé(s)")
    if action.button("🧹 Purger l'historique", disabled=bool(len(jobs) == len(running)), width="stretch"):
        REGISTRY.clear_finished()
        st.rerun()

    for index, job in enumerate(jobs):
        render_job(job, expanded=(index == 0))


# ── Volet Tickets ─────────────────────────────────────────────────────────────
def render_tickets() -> None:
    items = tickets.load_tickets()
    if not items:
        st.warning("Aucun ticket trouvé dans `docs/tickets/`.")
        return

    counts = tickets.summary(items)
    cols = st.columns(len(tickets.STATUS_ORDER) + 1)
    cols[0].metric("Tickets", len(items))
    for col, status in zip(cols[1:], tickets.STATUS_ORDER):
        col.metric(f"{tickets.STATUS_ICON[status]} {status.capitalize()}", counts.get(status, 0))

    st.caption(
        "Le statut est déduit des cases à cocher et de la ligne `**État**` du ticket ; "
        "il est surchargeable dans `scripts/dashboard/tickets_status.yaml` (colonne « Source »)."
    )

    frame = pd.DataFrame(
        [
            {
                "": tickets.STATUS_ICON[t.status],
                "N°": t.number,
                "Titre": t.title,
                "Statut": t.status,
                "Source": t.status_source,
                "Cases": f"{t.done}/{t.total_boxes}" if t.total_boxes else "—",
                "Avancement": t.progress if t.progress is not None else 0.0,
                "Modifié": t.modified,
            }
            for t in items
        ]
    )
    st.dataframe(
        frame,
        hide_index=True,
        width="stretch",
        column_config={
            "": st.column_config.TextColumn(width="small"),
            "Titre": st.column_config.TextColumn(width="large"),
            "Avancement": st.column_config.ProgressColumn(
                "Avancement", min_value=0.0, max_value=1.0, format="percent"
            ),
            "Modifié": st.column_config.DatetimeColumn("Modifié", format="DD/MM/YYYY HH:mm"),
        },
    )

    st.markdown("#### Détail")
    for t in items:
        with st.expander(f"{tickets.STATUS_ICON[t.status]} {t.title}"):
            st.markdown(f"**Statut** {t.status} _(source : {t.status_source})_")
            if t.state_line:
                st.markdown(f"**Ligne d'état du ticket** — {t.state_line}")
            if t.note:
                st.info(t.note)
            if t.total_boxes:
                st.progress(t.progress or 0.0, text=f"{t.done}/{t.total_boxes} cases cochées")
            st.caption(f"`{t.rel_path}` — {t.lines} lignes, modifié le {t.modified:%d/%m/%Y %H:%M}")


# ── Volet Métriques ───────────────────────────────────────────────────────────
def render_services() -> None:
    st.markdown("#### Services Docker")
    docker = cached_docker()
    if not docker.available:
        st.warning(f"État Docker indisponible — {docker.error}")
        return
    if not docker.services:
        st.info("Aucun conteneur : la pile est arrêtée (`make up` pour la démarrer).")
        return

    running = docker.running
    total = len(docker.services)
    head = st.columns([1, 5], vertical_alignment="center")
    head[0].metric("Conteneurs actifs", f"{running}/{total}", border=True)
    head[1].markdown(
        " ".join(f"{status_dot(s.kind)} `{s.name}`" for s in docker.services),
        help="Vert : running · Orange : redémarrage ou health dégradée · Rouge : arrêté",
    )
    if docker.missing:
        head[1].caption(f"Services attendus non démarrés : {', '.join(docker.missing)}")

    with st.expander("Détail des conteneurs"):
        st.dataframe(
            pd.DataFrame(
                [
                    {"": status_dot(s.kind), "Service": s.name, "État": s.state, "Statut": s.status}
                    for s in docker.services
                ]
            ),
            hide_index=True,
            width="stretch",
            column_config={"": st.column_config.TextColumn(width="small")},
        )

    actions = st.columns(3)
    with actions[0]:
        make_action("🐳 make up", "up")
    with actions[1]:
        make_action("♻️ make restart", "restart")
    with actions[2]:
        make_action("🔻 make down", "down", key="services-down",
                     help="Arrête tous les services, y compris un éventuel run GAMA offline.")


def modal_split_chart(stats: metrics.MovesStats) -> alt.LayerChart:
    """Barres horizontales du partage modal.

    La couleur reprend la palette officielle du projet (CLAUDE.md), qui n'est pas
    séparable en vision daltonienne : l'identité est donc portée par le libellé
    d'axe et la valeur écrite en bout de barre, jamais par la couleur seule.
    """
    total = sum(n for _, n in stats.modal_split) or 1
    frame = pd.DataFrame(
        [
            {
                "Mode": palette.mode_label(mode),
                "Trajets": count,
                "Part": count / total,
                "Étiquette": f"{count:,} ({100 * count / total:.1f} %)".replace(",", " "),
                "_couleur": palette.mode_color(mode, DARK),
            }
            for mode, count in stats.modal_split
        ]
    ).sort_values("Trajets", ascending=False)

    order = frame["Mode"].tolist()
    base = alt.Chart(frame).encode(
        y=alt.Y(
            "Mode:N",
            sort=order,
            title=None,
            axis=alt.Axis(labelColor=INK, labelFontSize=13, labelLimit=220),
        ),
        x=alt.X("Trajets:Q", title=None, axis=None, scale=alt.Scale(nice=False, padding=0)),
    )
    bars = base.mark_bar(
        cornerRadiusTopRight=4, cornerRadiusBottomRight=4, height=18, stroke=None
    ).encode(
        color=alt.Color("_couleur:N", scale=None, legend=None),
        tooltip=[
            alt.Tooltip("Mode:N"),
            alt.Tooltip("Trajets:Q", format=","),
            alt.Tooltip("Part:Q", format=".1%"),
        ],
    )
    labels = base.mark_text(align="left", dx=8, fontSize=12, color=INK_SOFT).encode(
        text="Étiquette:N"
    )
    return (bars + labels).properties(height=28 * len(frame) + 12).configure_view(stroke=None)


def single_series_chart(pairs: list[tuple[str, int]], hue: str) -> alt.LayerChart:
    """Barres horizontales d'une série unique (pas de légende : le titre suffit)."""
    total = sum(n for _, n in pairs) or 1
    frame = pd.DataFrame(
        [
            {
                "Clé": key,
                "Nombre": count,
                "Étiquette": f"{count:,} ({100 * count / total:.1f} %)".replace(",", " "),
            }
            for key, count in pairs
        ]
    ).sort_values("Nombre", ascending=False)

    order = frame["Clé"].tolist()
    base = alt.Chart(frame).encode(
        y=alt.Y("Clé:N", sort=order, title=None, axis=alt.Axis(labelColor=INK, labelLimit=280)),
        x=alt.X("Nombre:Q", title=None, axis=None, scale=alt.Scale(nice=False, padding=0)),
    )
    bars = base.mark_bar(
        cornerRadiusTopRight=4, cornerRadiusBottomRight=4, height=18, color=hue
    ).encode(tooltip=[alt.Tooltip("Clé:N"), alt.Tooltip("Nombre:Q", format=",")])
    labels = base.mark_text(align="left", dx=8, fontSize=12, color=INK_SOFT).encode(text="Étiquette:N")
    return (bars + labels).properties(height=28 * len(frame) + 12).configure_view(stroke=None)


def render_run_metrics() -> None:
    runs = cached_runs()
    if not runs:
        st.info("Aucun run dans `experiments/`.")
        return

    labels = {f"{r.label} — {r.modified:%d/%m/%Y %H:%M}": r for r in runs}
    chosen = st.selectbox("Run analysé", list(labels))
    run = labels[chosen]

    log = run.path / "app.log"
    if log.is_file():
        run.errors, run.warnings, run.alarms, run.log_span = cached_log_counts(
            str(log), run.log_size, log.stat().st_mtime
        )

    cols = st.columns(5)
    cols[0].metric("Erreurs", f"{run.errors:,}".replace(",", " "), border=True)
    cols[1].metric("Warnings", f"{run.warnings:,}".replace(",", " "), border=True)
    cols[2].metric("🚨 [ALARME]", run.alarms, border=True)
    cols[3].metric("Taille du log", metrics.human_size(run.log_size), border=True)
    cols[4].metric("Dernière écriture", f"{run.modified:%d/%m %H:%M}", border=True)
    if run.log_span:
        st.caption(f"Log couvrant {run.log_span[0]} → {run.log_span[1]} · `{run.rel_path}`")

    if not run.has_moves:
        st.info("Ce run n'a pas de `moves.csv` : pas de métriques de trajets à afficher.")
        return

    stats = cached_moves(str(run.path))
    if stats is None:
        st.warning("`moves.csv` illisible.")
        return

    cols = st.columns(5)
    cols[0].metric("Trajets", f"{stats.trips:,}".replace(",", " "), border=True)
    cols[1].metric("Agents", f"{stats.persons:,}".replace(",", " "), border=True)
    cols[2].metric(
        "Heures simulées", f"{stats.sim_hours:.1f} h" if stats.sim_hours is not None else "—", border=True
    )
    cols[3].metric(
        "Décidés par le LLM",
        f"{stats.llm_share:.1f} %" if stats.llm_share is not None else "—",
        border=True,
    )
    cols[4].metric(
        "Retard planif. p95",
        f"{stats.delay_p95:.0f} s" if stats.delay_p95 is not None else "—",
        border=True,
    )
    if stats.llm_error_share:
        st.caption(f"Erreurs LLM retombées sur l'index par défaut : {stats.llm_error_share:.1f} % des trajets.")

    left, right = st.columns(2)
    with left:
        st.markdown("**Partage modal des trajets**")
        st.altair_chart(modal_split_chart(stats), width="stretch")
        with st.expander("Vue tableau"):
            total = sum(n for _, n in stats.modal_split) or 1
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Mode": palette.mode_label(m), "Trajets": n, "Part": n / total}
                        for m, n in stats.modal_split
                    ]
                ),
                hide_index=True,
                width="stretch",
                column_config={"Part": st.column_config.NumberColumn(format="percent")},
            )
    with right:
        st.markdown("**Méthode de sélection de l'itinéraire**")
        st.altair_chart(
            single_series_chart(stats.selection, palette.mode_color("Marche", DARK)),
            width="stretch",
        )
        st.caption(
            f"{stats.with_distribution:,}".replace(",", " ")
            + f" trajets sur {stats.trips} portent une distribution de probabilités."
        )

    with st.expander("Historique des runs"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Run": r.label,
                        "Modifié": r.modified,
                        "Log": metrics.human_size(r.log_size),
                        "moves.csv": "✅" if r.has_moves else "—",
                        "Chemin": r.rel_path,
                    }
                    for r in runs
                ]
            ),
            hide_index=True,
            width="stretch",
            column_config={"Modifié": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")},
        )


def render_synthesis() -> None:
    st.markdown("#### Synthèse des scores")
    synth = cached_synthesis()
    if not synth.available:
        st.warning(synth.error)
        return

    pin = "épinglé" if synth.run_pinned else "non épinglé"
    st.caption(
        f"Page générée le {synth.generated_at or '—'} · run `{synth.run_id or '—'}` ({pin})"
    )
    cols = st.columns(3)
    cols[0].metric("Trajets du jeu commun", f"{synth.n_trips:,}".replace(",", " "), border=True)
    cols[1].metric("Personnes", f"{synth.n_persons:,}".replace(",", " "), border=True)
    cols[2].metric("Avec distribution", f"{synth.pct_distribution:.1f} %", border=True)

    if synth.arms:
        frame = pd.DataFrame(
            [{"Bras": a["label"], **dict(zip(synth.dims, a["cells"]))} for a in synth.arms]
        )
        st.caption(f"Écart au référentiel Cerema — métrique primaire `{synth.primary}` (plus bas = mieux).")
        st.dataframe(
            frame,
            hide_index=True,
            width="stretch",
            column_config={dim: st.column_config.NumberColumn(format="%.2f") for dim in synth.dims},
        )

    statuses = " · ".join(f"{k} : {v}" for k, v in synth.arm_status.items())
    if statuses:
        st.caption(f"État des bras — {statuses}")
    for warning in synth.warnings:
        st.caption(f"⚠️ {warning}")

    actions = st.columns(3)
    with actions[0]:
        make_action("🔄 make synthesis", "synthesis", help="Régénère data.json et index.html — gratuit, aucun appel LLM.")
    with actions[1]:
        make_action("🌐 make synthesis-open", "synthesis-open", help="Régénère puis ouvre docs/synthesis/index.html dans le navigateur.")
    actions[2].caption(
        "Évals payantes (`common-set-eval`, `heldout-eval`) : ▶ Commandes → "
        "Synthèse des scores, avec DRY_RUN=1 d'abord."
    )


def render_calibration() -> None:
    st.markdown("#### Stores de calibration")
    stores = cached_calibration()
    columns = st.columns(len(stores))
    for col, store in zip(columns, stores):
        with col:
            st.markdown(f"**Store `{store.key}`**")
            if not store.available:
                st.caption(f"— {store.error} (`{store.path.relative_to(REPO_ROOT)}`)")
                continue
            if store.key == "cloud" and store.modified:
                st.caption(
                    f"⚠️ Copie rapatriée {age_label(store.modified)} — l'état réel de la VM "
                    "se lit ci-dessous (Campagne cloud) ou se met à jour avec `pull-db`."
                )
            best = store.best
            inner = st.columns(2)
            inner[0].metric("Meilleur score", f"{best.best_score:.2f}" if best else "—", border=True)
            inner[1].metric("Itération", best.iteration if best else "—", border=True)
            inner = st.columns(3)
            inner[0].metric("Nœuds", store.nodes, border=True)
            inner[1].metric("Évals", store.evals, border=True)
            inner[2].metric("Mutations", store.mutations, border=True)
            st.caption(
                f"{store.accepted} acceptée(s) · {store.rejected} rejetée(s) · "
                f"{store.pending} en attente · dernière éval {store.last_activity or '—'}"
            )
            if store.ga:
                stopped = " · ⏹ arrêtée" if store.ga.get("stopped") else ""
                champion = str(store.ga.get("champion") or "—")[:12]
                st.caption(
                    f"🧬 GA : génération {store.ga.get('generation', '—')} · "
                    f"étape `{store.ga.get('step', '—')}` · champion `{champion}`{stopped}"
                )
            if metrics.cooldown_active(store.cooldown):
                st.caption(
                    f"💤 Veille quota jusqu'à {store.cooldown['resume_after']} — "
                    f"{store.cooldown.get('reason', '')}"
                )
            if store.branches:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Branche": b.branch,
                                "Itération": b.iteration,
                                "Best": b.best_score,
                                "Val": b.val_best,
                                "Sans gain": b.val_no_improve,
                                "MAJ": b.updated_at[:16],
                            }
                            for b in store.branches
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Best": st.column_config.NumberColumn(format="%.2f"),
                        "Val": st.column_config.NumberColumn(format="%.2f"),
                    },
                )


# ── Volet Calibration ─────────────────────────────────────────────────────────
GA_STEPS = ("populate", "eval", "cut", "confirm", "ablate", "validate", "report", "breed")
GA_STEP_LABELS = {
    "populate": "constitution de la population",
    "eval": "évaluation (1 éval `rank` par individu)",
    "cut": "coupe (tri sur `rank`, survivants μ)",
    "confirm": "confirmation du champion (2 évals `screen`)",
    "ablate": "ablation des meilleurs (coalitions `rank`)",
    "validate": "validation `val` du champion (early stopping)",
    "report": "rapport + notification (mail/Discord)",
    "breed": "reproduction (enfants λ, croisements/mutations)",
}


def render_ga() -> None:
    st.markdown("#### 🧬 Campagne génétique (ticket 009)")
    cloud_db = metrics.CALIB_STORES.get("cloud")
    if cloud_db is None or not cloud_db.is_file():
        st.caption("— store cloud absent : rapatriez-le avec le bouton `pull-db` ci-dessous.")
        return
    ga = cached_ga_details(str(cloud_db), cloud_db.stat().st_mtime)
    if not ga.available:
        st.caption(f"— {ga.error}")
        return

    pulled = datetime.fromtimestamp(cloud_db.stat().st_mtime)
    st.caption(
        f"État au dernier rapatriement ({age_label(pulled)}). Pour le temps réel : "
        "boutons « Campagne cloud » ci-dessous."
    )

    step_pos = f" ({GA_STEPS.index(ga.step) + 1}/{len(GA_STEPS)})" if ga.step in GA_STEPS else ""
    evaluated = sum(1 for i in ga.population if i.rank is not None)
    cols = st.columns(5)
    cols[0].metric("Génération", ga.generation, border=True)
    cols[1].metric(
        "Étape",
        f"{ga.step}{step_pos}" if ga.step else "—",
        border=True,
        help="Cycle : " + " → ".join(GA_STEPS) + ". En cours : "
        + GA_STEP_LABELS.get(ga.step, ga.step),
    )
    cols[2].metric(
        "Population évaluée",
        f"{evaluated}/{len(ga.population)}" if ga.population else "—",
        border=True,
        help="Individus disposant d'un score `rank` — le score de sélection sur lequel la coupe se décide.",
    )
    champion_label = "—"
    if ga.champion:
        champion_label = f"{ga.champion[:8]}"
        if ga.champion_screen is not None:
            champion_label += f" ({ga.champion_screen:.2f})"
    cols[3].metric("Champion", champion_label, border=True)
    val = "—"
    if ga.val_best is not None and ga.val_best != float("inf"):
        val = f"{ga.val_best:.2f}"
    cols[4].metric("Val best", val, border=True, help=f"{ga.val_no_improve} génération(s) sans gain.")

    if ga.stopped:
        st.warning(f"⏹ Campagne arrêtée : {ga.stopped}")
    activity = f"Dernière éval {ga.last_eval[:16] or '—'} · {ga.evals_24h} éval(s) sur 24 h"
    if ga.survivors or ga.children or ga.eliminated:
        activity += (
            f" · {ga.survivors} survivant(s), {ga.children} enfant(s), {ga.eliminated} éliminé(s)"
        )
    st.caption(activity)

    if ga.population:
        frame = pd.DataFrame(
            [
                {
                    "": "👑" if i.is_champion else "",
                    "Individu": i.short,
                    "Profil": i.label,
                    "Origine": i.operator,
                    "Depuis gén.": i.first_seen,
                    "Créé le": i.created_at.replace("T", " "),
                    "Rank": i.rank,
                    "Screen": i.screen,
                    "Val": i.val,
                    "Évals": i.evals,
                    "Statut": "✅ évalué" if i.rank is not None else "⏳ en attente",
                }
                for i in ga.population
            ]
        )
        st.dataframe(
            frame,
            hide_index=True,
            width="stretch",
            column_config={
                "": st.column_config.TextColumn(width="small"),
                "Rank": st.column_config.NumberColumn(
                    format="%.2f",
                    help="Composite sur le jeu `rank` (212 lignes) — LE score de sélection, plus bas = mieux.",
                ),
                "Screen": st.column_config.NumberColumn(
                    format="%.2f", help="Confirmation du champion (jeu `screen`, 569 lignes)."
                ),
                "Val": st.column_config.NumberColumn(
                    format="%.2f", help="Early stopping (jeu `val`, 634 lignes)."
                ),
            },
        )

    if ga.champion_by_gen:
        with st.expander("Champion par génération", expanded=len(ga.champion_by_gen) > 1):
            hist = pd.DataFrame(ga.champion_by_gen)
            st.dataframe(hist, hide_index=True, width="stretch")

    reports_dir = REPO_ROOT / "prompt_calibration" / "calibration_results" / "ga_reports"
    reports = sorted(reports_dir.glob("gen_*.html")) if reports_dir.is_dir() else []
    rep_col, mail_col = st.columns(2)
    with rep_col:
        st.markdown("**Rapports par génération**")
        if reports:
            st.caption(f"{len(reports)} rapport(s) local(aux) — dernier : `{reports[-1].name}`")
            if st.button("🌐 Ouvrir le dernier rapport", key="ga-open-report"):
                subprocess.Popen(["open", str(reports[-1])])  # noqa: S603 S607 — macOS
        else:
            st.caption(
                "Les `gen_NN.html` (générés à l'étape `report`) restent sur la VM : "
                "rapatriez-les avec le bouton ci-dessous."
            )
        make_action(
            "⬇️ Rapatrier les rapports (pull-reports)",
            "pull-reports",
            project="calib",
            help="gcloud compute scp --recurse des ga_reports/ de la VM.",
        )
    with mail_col:
        with st.expander("📧 Rapports par mail — configuration"):
            st.markdown(
                "Un mail part **à chaque génération** (étape `report`) et un **bilan "
                "hebdo** le lundi 08:30 (Paris). Deux réglages :\n"
                "1. `prompt_calibration/config/ga_cloud.yaml` — `notify_mail_to: "
                "votre@adresse` (et `digest_mail: true` pour le digest quotidien) ;\n"
                "2. sur la VM, `~/calib.env` (chmod 600, gabarit `cloud/env.example`) :\n"
                "   `SMTP_USER=<gmail expéditeur>` et `SMTP_APP_PASSWORD=<mot de passe "
                "d'application 16 caractères>`\n"
                "   (Compte Google → Sécurité → Validation en 2 étapes → Mots de passe "
                "des applications). Port 465 SSL par défaut.\n\n"
                "Puis déployer : `make cloud-deploy` (les services systemd lisent "
                "`~/calib.env` via EnvironmentFile)."
            )


def render_calib_progress() -> None:
    prog = cached_calib_progress()
    st.markdown("#### Daemon local (`progress.json`)")
    if not prog.available:
        st.caption(f"— {prog.error}. L'avancement de la VM se lit dans « Campagne cloud ».")
        return
    data = prog.data
    icon = {"actif": "🟢", "arrêté": "⚪"}.get(prog.liveness, "⚪")
    age = f"{int(prog.age_s // 60)} min" if prog.age_s is not None else "?"
    cols = st.columns(4)
    cols[0].metric("Daemon", f"{icon} {prog.liveness}", border=True, help=f"Dernière écriture il y a {age}.")
    cols[1].metric("Branche", data.get("branch", "—"), border=True)
    cols[2].metric("Étape", data.get("stage_label") or data.get("stage", "—"), border=True)
    cols[3].metric("Best", data.get("best") if data.get("best") is not None else "—", border=True)
    st.caption(
        f"{data.get('describe', '')} · itération {data.get('iteration', '—')} · "
        f"{data.get('paid_evals', 0)} évals payées · {data.get('cache_hits', 0)} hits cache · "
        f"{data.get('llm_calls', 0)} appels LLM. Ce fichier ne reflète que les passes "
        "exécutées sur CETTE machine, pas la VM."
    )


def render_calib_cloud() -> None:
    st.markdown("#### Campagne cloud (VM `calib-vm`)")
    st.caption(
        "Chaque consultation passe par `gcloud compute ssh` (quelques secondes) : "
        "rien n'est interrogé automatiquement, uniquement sur bouton."
    )

    configs = sorted(
        f"config/{p.name}" for p in (REPO_ROOT / "prompt_calibration" / "config").glob("*.yaml")
    )
    default = configs.index("config/ga_cloud.yaml") if "config/ga_cloud.yaml" in configs else 0
    left, right = st.columns(2)
    config = left.selectbox(
        "CLOUD_CONFIG (campagne interrogée)",
        configs,
        index=default,
        help="config/ga_cloud.yaml = campagne génétique courante (ticket 009), "
        "config/cloud.yaml = ancien recuit simulé.",
    )
    unit = right.radio(
        "UNIT (daemon suivi par cloud-logs)", ("calib-ga", "calib"), horizontal=True
    )

    probe = st.columns(3)
    if probe[0].button("⏳ Avancement (cloud-progress)", width="stretch"):
        with st.spinner("SSH vers la VM…"):
            st.session_state["calib_cloud_out"] = run_make_inline(
                "cloud-progress", {"CLOUD_CONFIG": config}, project="calib"
            )
    if probe[1].button("📊 État du store (cloud-status)", width="stretch"):
        with st.spinner("SSH vers la VM…"):
            st.session_state["calib_cloud_out"] = run_make_inline(
                "cloud-status", {"CLOUD_CONFIG": config}, project="calib"
            )
    if probe[2].button("📜 Logs du daemon (cloud-logs)", width="stretch"):
        with st.spinner("SSH vers la VM…"):
            st.session_state["calib_cloud_out"] = run_make_inline(
                "cloud-logs", {"UNIT": unit}, project="calib"
            )
    output = st.session_state.get("calib_cloud_out")
    if output:
        st.code(output, language="log")

    st.markdown("**Actions**")
    actions = st.columns(3)
    with actions[0]:
        make_action(
            "⬇️ Rapatrier le store cloud (pull-db)",
            "pull-db",
            project="calib",
            values={"LOCAL_DB": "calibration_results/calibration_cloud.db"},
            help="gcloud compute scp → calibration_results/calibration_cloud.db, sans ouvrir d'UI.",
        )
        st.caption(
            "Met à jour la colonne « cloud » ci-dessus (`calibration_cloud.db`). "
            "Le store `local` n'est pas touché."
        )
    with actions[1]:
        pause_ok = st.checkbox("Confirmer la pause", key="calib-pause-confirm")
        make_action(
            "⏸ Suspendre la campagne (pause)",
            "pause",
            project="calib",
            disabled=not pause_ok,
            help="Coupe le daemon et le digest sur la VM, arme le rappel Discord quotidien.",
        )
    with actions[2]:
        make_action(
            "▶️ Reprendre la campagne (start)",
            "start",
            project="calib",
            help="Désarme le rappel, réarme daemon + digest, vérifie que le daemon est actif.",
        )
    st.caption(
        "Dashboard de calibration détaillé (DAG, Pareto, distributions) : "
        "`make ui` dans ▶ Commandes → projet prompt_calibration."
    )


def render_calibration_tab() -> None:
    render_ga()
    st.divider()
    render_calib_cloud()
    st.divider()
    render_calibration()
    st.divider()
    render_calib_progress()


def render_metrics() -> None:
    render_services()
    st.divider()
    st.markdown("#### Santé du run")
    st.caption("Lancement, arrêt et suivi du run courant : onglet 🎮 Run GAMA.")
    render_run_metrics()
    st.divider()
    render_synthesis()


# ── Volet Vue d'ensemble ──────────────────────────────────────────────────────
@st.fragment(run_every="10s")
def render_overview() -> None:
    """Les feux de l'état courant, rafraîchis toutes les 10 s."""
    proc = cached_run_process()
    docker = cached_docker()
    run = current_run()
    health = cached_health()
    git = cached_git()
    stores = cached_calibration()

    row1 = st.columns(3)
    with row1[0], st.container(border=True):
        st.markdown("**🐳 Services** — onglet 📊 Métriques")
        if not docker.available:
            st.markdown(f"{status_dot('muted')} Docker indisponible")
        elif not docker.services:
            st.markdown(f"{status_dot('critical')} Pile arrêtée — `make up`")
        else:
            kind = "good" if not docker.missing else "warning"
            st.markdown(f"{status_dot(kind)} **{docker.running}/{len(docker.services)}** conteneurs actifs")
            if docker.missing:
                st.caption(f"Manquants : {', '.join(docker.missing)}")

    with row1[1], st.container(border=True):
        st.markdown("**🎮 Run GAMA** — onglet 🎮 Run GAMA")
        if proc.active:
            st.markdown(f"{status_dot('good')} **Actif** ({proc.mode}, pid {proc.pid})")
        else:
            st.markdown(f"{status_dot('muted')} Aucun run en cours")
        if run:
            alarm = f" · 🚨 {run.alarms}" if run.alarms else ""
            st.caption(f"`{run.label}` — dernière écriture {age_label(run.modified)}{alarm}")

    with row1[2], st.container(border=True):
        st.markdown("**🤖 Providers** — onglet 🤖 Providers")
        if health.available:
            n = len(health.providers)
            ok = sum(1 for p in health.providers if p.available)
            cooldown = sum(1 for p in health.providers if p.cooldown)
            exhausted = sum(1 for p in health.providers if p.quota_exhausted)
            kind = "good" if ok == n else ("warning" if ok else "critical")
            st.markdown(f"{status_dot(kind)} **{ok}/{n}** disponibles")
            if cooldown or exhausted:
                st.caption(f"{cooldown} en cooldown · {exhausted} quota jour épuisé")
        else:
            st.markdown(f"{status_dot('muted')} API arrêtée — quotas statiques seulement")

    row2 = st.columns(3)
    with row2[0], st.container(border=True):
        st.markdown("**🧬 Calibration** — onglet 🧬 Calibration")
        parts = []
        for store in stores:
            if store.available and store.best:
                parts.append(f"`{store.key}` best {store.best.best_score:.2f}")
            if store.available and store.ga:
                parts.append(f"GA gén. {store.ga.get('generation', '?')}")
        st.markdown(" · ".join(parts) if parts else f"{status_dot('muted')} stores absents")
        cloud_db = metrics.CALIB_STORES.get("cloud")
        if cloud_db is not None and cloud_db.is_file():
            pulled = datetime.fromtimestamp(cloud_db.stat().st_mtime)
            st.caption(f"Store cloud rapatrié {age_label(pulled)} (`make pull-cloud` pour actualiser)")

    with row2[1], st.container(border=True):
        st.markdown("**🌿 Git**")
        dirty = int(git["dirty"] or 0)
        kind = "good" if dirty == 0 else "warning"
        st.markdown(f"{status_dot(kind)} `{git['branch']}` — **{dirty}** fichier(s) modifié(s)")
        if git["head"]:
            st.caption(git["head"])

    with row2[2], st.container(border=True):
        st.markdown("**⚙️ Jobs** — onglet 📟 Lancements")
        running = REGISTRY.running_count()
        st.markdown(
            f"{status_dot('good' if running else 'muted')} **{running}** lancement(s) en cours"
        )

    st.caption(f"Données lues à {datetime.now():%H:%M:%S} — rafraîchissement automatique (10 s).")


# ── Volet Run GAMA ────────────────────────────────────────────────────────────
def agent_states_chart(df: pd.DataFrame) -> alt.Chart:
    """Évolution inactifs/prêts/actifs par cycle. Les couleurs (palette d'état)
    ne portent pas l'identité seule : légende nommée, tooltip et vue tableau."""
    tidy = df.melt(
        id_vars=["step", "sim_time"],
        value_vars=["active", "ready", "inactive"],
        var_name="État",
        value_name="Agents",
    )
    labels = {"active": "Actifs", "ready": "Prêts", "inactive": "Inactifs"}
    hues = {
        "Actifs": palette.status_color("good", DARK),
        "Prêts": palette.status_color("warning", DARK),
        "Inactifs": palette.status_color("muted", DARK),
    }
    tidy["État"] = tidy["État"].map(labels)
    return (
        alt.Chart(tidy)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("step:Q", title="Cycle (/sync)", axis=alt.Axis(labelColor=INK, titleColor=INK_SOFT)),
            y=alt.Y("Agents:Q", title=None, axis=alt.Axis(labelColor=INK)),
            color=alt.Color(
                "État:N",
                scale=alt.Scale(domain=list(hues), range=list(hues.values())),
                legend=alt.Legend(orient="top", labelColor=INK, title=None),
            ),
            tooltip=["step:Q", "sim_time:N", "État:N", "Agents:Q"],
        )
        .properties(height=260)
        .configure_view(stroke=None)
    )


@st.fragment(run_every="5s")
def render_run_status() -> None:
    """Bandeau d'état du run, rafraîchi toutes les 5 s."""
    proc = cached_run_process()
    run = current_run()
    ctrl = cached_controller_stats()

    cols = st.columns(5)
    cols[0].metric(
        "État",
        f"🟢 actif ({proc.mode})" if proc.active else "⚪ inactif",
        border=True,
    )
    cols[1].metric(
        "Dernière écriture",
        age_label(run.modified) if run else "—",
        border=True,
        help="mtime de app.log du run courant : le heartbeat le plus fiable.",
    )
    last = None
    if run:
        csv = run.path / "gama_results" / "agent_states.csv"
        if csv.is_file():
            df = cached_agent_states(str(run.path), csv.stat().st_mtime)
            if df is not None and not df.empty:
                last = df.iloc[-1]
    step = ctrl.get("gama_sim_step_count") or (last["step"] if last is not None else None)
    active = ctrl.get("agents_active") if "agents_active" in ctrl else (
        last["active"] if last is not None else None
    )
    total = ctrl.get("gama_sim_agents_total") or (last["total"] if last is not None else None)
    cols[2].metric("Cycle", int(step) if step is not None else "—", border=True)
    cols[3].metric(
        "Agents actifs",
        f"{int(active)}/{int(total)}" if active is not None and total else "—",
        border=True,
    )
    backlog = ctrl.get("controller_backlog_fill_ratio")
    cols[4].metric(
        "Backlog pipeline",
        f"{100 * backlog:.0f} %" if backlog is not None else "—",
        border=True,
        help="Remplissage de la pile d'activités du controller (100 % = pile pleine). "
        "Nécessite le controller démarré.",
    )
    if last is not None:
        st.caption(f"Dernier /sync : cycle {int(last['step'])} à {last['sim_time']} (heure simulée).")


def render_run_actions() -> None:
    proc = cached_run_process()
    st.markdown("#### Actions")
    launch, stop, down = st.columns(3)

    with launch, st.container(border=True):
        st.markdown("**▶ Lancer un run offline**")
        st.caption("Config unique : llm-agents/config/config.yaml (l'éditer directement pour changer de run).")
        confirmed = st.checkbox(
            "Je confirme : purge Grafana/Prometheus et compteurs Redis avant démarrage",
            key="run-confirm",
        )
        if st.button("🚀 make run-offline", disabled=proc.active or not confirmed, width="stretch"):
            argv = ["make", "run-offline"]
            REGISTRY.launch("root:run-offline", argv, REPO_ROOT, ("long", "danger"))
            st.toast("Run lancé — suivi dans 📟 Lancements")
        if proc.active:
            st.caption("Un run tourne déjà : arrêtez-le d'abord.")

    with stop, st.container(border=True):
        st.markdown("**⏹ Arrêter le run**")
        st.caption(
            "Tue le launcher headless et stoppe le service `gama` ; "
            "les autres services restent en place."
        )
        if st.button("⏹ make stop-run", disabled=not proc.active, width="stretch"):
            REGISTRY.launch("root:stop-run", ["make", "stop-run"], REPO_ROOT)
            st.toast("Arrêt demandé — suivi dans 📟 Lancements")

    with down, st.container(border=True):
        st.markdown("**🔻 Couper toute la pile**")
        st.caption("`make down` — arrête tous les services Docker, y compris `gama`.")
        if st.button("🔻 make down", width="stretch"):
            REGISTRY.launch("root:down", ["make", "down"], REPO_ROOT)
            st.toast("Arrêt de la pile — suivi dans 📟 Lancements")


def render_run_report(run: metrics.RunInfo) -> None:
    st.markdown("#### Rapport de santé (`make report`)")
    if st.button("📋 Générer le rapport du run courant"):
        with st.spinner("scripts/debug/run_report.py…"):
            try:
                proc = subprocess.run(  # noqa: S603 — commande fixe
                    ["python3", "scripts/debug/run_report.py", str(run.path)],
                    cwd=str(REPO_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                st.session_state["run_report_md"] = (
                    proc.stdout if proc.returncode == 0 else f"```\n{proc.stderr[-3000:]}\n```"
                )
            except (subprocess.TimeoutExpired, OSError) as exc:
                st.session_state["run_report_md"] = f"Rapport indisponible : {exc}"
    report = st.session_state.get("run_report_md")
    if report:
        with st.expander("Rapport", expanded=True):
            st.markdown(report)


def render_run_tab() -> None:
    render_run_status()
    st.divider()

    run = current_run()
    if run is None:
        st.info(
            "`experiments/current` ne pointe sur aucun run : lancez-en un ci-dessous. "
            "L'historique est dans l'onglet 📊 Métriques."
        )
        render_run_actions()
        return

    left, right = st.columns([3, 2])
    with left:
        st.markdown("#### Progression des agents")
        csv = run.path / "gama_results" / "agent_states.csv"
        df = cached_agent_states(str(run.path), csv.stat().st_mtime) if csv.is_file() else None
        if df is None or df.empty:
            st.info("Pas encore de `gama_results/agent_states.csv` pour ce run.")
        else:
            st.altair_chart(agent_states_chart(df), width="stretch")
            with st.expander("Vue tableau (derniers cycles)"):
                st.dataframe(df.tail(12), hide_index=True, width="stretch")

    with right:
        st.markdown("#### Santé des logs")
        log = run.path / "app.log"
        if log.is_file():
            errors, warnings, alarms, span = cached_log_counts(
                str(log), run.log_size, log.stat().st_mtime
            )
            cols = st.columns(3)
            cols[0].metric("Erreurs", f"{errors:,}".replace(",", " "), border=True)
            cols[1].metric("Warnings", f"{warnings:,}".replace(",", " "), border=True)
            cols[2].metric("🚨 [ALARME]", alarms, border=True)
            top = cached_top_errors(str(log), "ERROR", log.stat().st_mtime)
            if top:
                with st.expander(f"Top erreurs ({len(top)} motifs)", expanded=alarms > 0):
                    for count, example in top:
                        st.markdown(f"**× {count}** — `{example}`")
        else:
            st.info("Pas de `app.log` pour ce run.")

        st.markdown("#### Pipeline LLM du run")
        hit = cached_cache_hit_rate(str(run.path))
        llm_err = cached_llm_errors(str(run.path))
        cols = st.columns(3)
        cols[0].metric(
            "Cache LLM",
            f"{hit[0]:.0f} %" if hit else "—",
            border=True,
            help="hits / (hits + appels réels) — llm_cache_hits.jsonl vs llm_exchanges.jsonl.",
        )
        cols[1].metric("Erreurs LLM", llm_err.total, border=True)
        cols[2].metric("HTTP 429", llm_err.n_429, border=True)
        if hit:
            st.caption(f"{hit[1]} hits · {hit[2]} appels réels au LLM.")
        if llm_err.by_provider:
            st.caption(
                "Erreurs par provider : "
                + " · ".join(f"`{p}` {n}" for p, n in llm_err.by_provider[:5])
            )

    st.divider()
    render_run_actions()
    st.divider()
    render_run_report(run)


# ── Volet Providers ───────────────────────────────────────────────────────────
def render_providers_tab() -> None:
    health = cached_health()
    static = cached_providers_static()
    by_name = {p["name"]: p for p in static.providers} if static.available else {}

    if health.available:
        n = len(health.providers)
        ok = sum(1 for p in health.providers if p.available)
        cols = st.columns(4)
        cols[0].metric("Providers", n, border=True)
        cols[1].metric("Disponibles", ok, border=True)
        cols[2].metric("En cooldown", sum(1 for p in health.providers if p.cooldown), border=True)
        cols[3].metric(
            "Quota jour épuisé", sum(1 for p in health.providers if p.quota_exhausted), border=True
        )
        frame = pd.DataFrame(
            [
                {
                    "": "🟢" if p.available else ("🟠" if p.cooldown else "🔴"),
                    "Provider": p.name,
                    "Modèle": by_name.get(p.name, {}).get("model", "?"),
                    "RPM": f"{p.current_rpm}/{p.rpm_limit or '∞'}",
                    "Tâches": p.active_tasks,
                    "Req. jour": p.daily_requests,
                    "RPD": p.rpd_limit,
                    "Usage jour": (p.daily_requests / p.rpd_limit) if p.rpd_limit else None,
                    "Tokens jour": p.daily_tokens,
                    "TPD": p.tpd_limit,
                }
                for p in health.providers
            ]
        )
        st.dataframe(
            frame,
            hide_index=True,
            width="stretch",
            column_config={
                "": st.column_config.TextColumn(width="small"),
                "Usage jour": st.column_config.ProgressColumn(
                    "Usage jour", min_value=0.0, max_value=1.0, format="percent"
                ),
                "Req. jour": st.column_config.NumberColumn(format="localized"),
                "Tokens jour": st.column_config.NumberColumn(format="localized"),
                "TPD": st.column_config.NumberColumn(format="localized"),
            },
        )
        st.caption(
            "État vu par le load balancer (`GET :8000/health`). "
            "🟢 disponible · 🟠 cooldown · 🔴 indisponible ou quota épuisé."
        )
    else:
        st.warning(f"{health.error} Les quotas ci-dessous sont ceux déclarés dans `providers.yaml`.")
        if static.available:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Provider": p["name"],
                            "Adapter": p["adapter"],
                            "Modèle": p["model"],
                            "RPM": p["rpm_limit"],
                            "TPM": p["tpm_limit"],
                            "RPD": p["rpd_limit"],
                            "TPD": p["tpd_limit"],
                            "Poids": p["weight"],
                        }
                        for p in static.providers
                    ]
                ),
                hide_index=True,
                width="stretch",
                column_config={
                    "TPM": st.column_config.NumberColumn(format="localized"),
                    "TPD": st.column_config.NumberColumn(format="localized"),
                },
            )
        else:
            st.error(static.error)

    if static.available and static.refreshed_at:
        st.caption(
            f"`providers.yaml` modifié le {static.refreshed_at:%d/%m/%Y %H:%M} "
            f"({age_label(static.refreshed_at)})."
        )

    st.divider()
    st.markdown("#### Rafraîchir les quotas (`make providers`)")
    st.caption(
        "Interroge les en-têtes `x-ratelimit-*` (mistral/groq/cerebras, une requête "
        "sonde par instance) et l'API Cloud Quotas Google, puis réécrit "
        "`llm_module/config/providers.yaml`. Chiffrez d'abord avec le bilan à blanc."
    )
    dry, real = st.columns(2)
    with dry:
        if st.button("🔍 Bilan à blanc (DRY_RUN=1)", width="stretch"):
            REGISTRY.launch("root:providers-dry", ["make", "providers", "DRY_RUN=1"], REPO_ROOT)
            st.toast("Bilan lancé — suivi dans 📟 Lancements")
    with real:
        confirmed = st.checkbox("Je confirme la réécriture de providers.yaml", key="providers-confirm")
        if st.button("🔄 make providers", disabled=not confirmed, width="stretch"):
            REGISTRY.launch("root:providers", ["make", "providers"], REPO_ROOT)
            st.toast("Rafraîchissement lancé — suivi dans 📟 Lancements")

    run = current_run()
    if run:
        llm_err = cached_llm_errors(str(run.path))
        if llm_err.by_provider_429:
            st.divider()
            st.markdown("#### 429 du run courant")
            st.dataframe(
                pd.DataFrame(llm_err.by_provider_429, columns=["Provider", "HTTP 429"]),
                hide_index=True,
                width="stretch",
            )


# ── Assemblage ────────────────────────────────────────────────────────────────
render_sidebar()
st.title("🚦 Pilotage llm-agents-gama")

# Les libellés d'onglet ne peuvent pas être rafraîchis par un fragment : le
# compteur de jobs vit dans la barre latérale et dans le volet Lancements.
tab_overview, tab_run, tab_providers, tab_calib, tab_commands, tab_jobs, tab_tickets, tab_metrics = st.tabs(
    [
        "🏠 Vue d'ensemble",
        "🎮 Run GAMA",
        "🤖 Providers",
        "🧬 Calibration",
        "▶ Commandes",
        "📟 Lancements",
        "🎫 Tickets",
        "📊 Métriques",
    ]
)

with tab_overview:
    render_overview()
with tab_run:
    render_run_tab()
with tab_providers:
    render_providers_tab()
with tab_calib:
    render_calibration_tab()
with tab_commands:
    render_commands()
with tab_jobs:
    render_jobs_live()
with tab_tickets:
    render_tickets()
with tab_metrics:
    render_metrics()
