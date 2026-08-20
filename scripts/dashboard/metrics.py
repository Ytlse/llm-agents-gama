"""Collecte des métriques affichées par le dashboard.

Sources locales, toutes lues en lecture seule et sans appel réseau (les sondes
HTTP vivent dans `live.py`) :
  * `docker compose ps`           → état des services
  * `experiments/**`              → santé des runs (logs, moves.csv, agents,
                                    erreurs LLM, cache sémantique)
  * `llm_module/config/providers.yaml` → quotas déclarés des providers
  * `docs/synthesis/data.json`    → scores de la page de synthèse
  * `prompt_calibration/calibration_results/*.db` → avancement des campagnes
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = REPO_ROOT / "experiments"
SYNTHESIS_DATA = REPO_ROOT / "docs" / "synthesis" / "data.json"
CALIB_STORES = {
    "local": REPO_ROOT / "prompt_calibration" / "calibration_results" / "calibration.db",
    "cloud": REPO_ROOT / "prompt_calibration" / "calibration_results" / "calibration_cloud.db",
}

# Services attendus (docker-compose.yml) — sert à repérer les manquants.
EXPECTED_SERVICES = ("api", "worker", "controller", "redis", "otp", "grafana", "prometheus")


# ── Docker ────────────────────────────────────────────────────────────────────
@dataclass
class Service:
    name: str
    state: str
    status: str
    health: str = ""

    @property
    def kind(self) -> str:
        if self.health in ("unhealthy", "starting") or self.state in ("restarting", "paused"):
            return "warning"
        if self.state == "running":
            return "good"
        if self.state in ("exited", "dead"):
            return "critical"
        return "muted"


@dataclass
class DockerStatus:
    available: bool
    services: list[Service] = field(default_factory=list)
    error: str = ""

    @property
    def running(self) -> int:
        return sum(1 for s in self.services if s.state == "running")

    @property
    def missing(self) -> list[str]:
        present = {s.name for s in self.services}
        return [name for name in EXPECTED_SERVICES if not any(name in p for p in present)]


def docker_status(timeout: float = 8.0) -> DockerStatus:
    if shutil.which("docker") is None:
        return DockerStatus(False, error="binaire `docker` introuvable")
    try:
        proc = subprocess.run(  # noqa: S603 — commande fixe
            ["docker", "compose", "ps", "--format", "json", "--all"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return DockerStatus(False, error=f"docker compose ps a échoué : {exc}")
    if proc.returncode != 0:
        return DockerStatus(False, error=(proc.stderr or "").strip()[:300])

    raw = proc.stdout.strip()
    records: list[dict] = []
    if raw.startswith("["):
        try:
            records = json.loads(raw)
        except json.JSONDecodeError:
            records = []
    else:
        for line in raw.splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    services = [
        Service(
            name=r.get("Service") or r.get("Name", "?"),
            state=(r.get("State") or "").lower(),
            status=r.get("Status", ""),
            health=(r.get("Health") or "").lower(),
        )
        for r in records
    ]
    return DockerStatus(True, sorted(services, key=lambda s: s.name))


# ── Runs ──────────────────────────────────────────────────────────────────────
@dataclass
class RunInfo:
    path: Path
    label: str
    is_current: bool
    modified: datetime
    log_size: int
    errors: int = 0
    warnings: int = 0
    alarms: int = 0
    log_span: tuple[str, str] | None = None
    has_moves: bool = False

    @property
    def rel_path(self) -> str:
        return str(self.path.relative_to(REPO_ROOT))


@dataclass
class MovesStats:
    trips: int
    persons: int
    modal_split: list[tuple[str, int]]
    selection: list[tuple[str, int]]
    with_distribution: int
    sim_start: datetime | None
    sim_end: datetime | None
    delay_mean: float | None
    delay_p95: float | None

    @property
    def sim_hours(self) -> float | None:
        if self.sim_start and self.sim_end:
            return (self.sim_end - self.sim_start).total_seconds() / 3600
        return None

    @property
    def llm_share(self) -> float | None:
        total = sum(n for _, n in self.selection)
        if not total:
            return None
        llm = sum(n for k, n in self.selection if k == "LLM")
        return 100 * llm / total

    @property
    def llm_error_share(self) -> float | None:
        total = sum(n for _, n in self.selection)
        if not total:
            return None
        errs = sum(n for k, n in self.selection if "Error" in k or "error" in k)
        return 100 * errs / total


def log_counts(log_path: Path, max_bytes: int = 64 * 1024 * 1024) -> tuple[int, int, int, tuple[str, str] | None]:
    """Compte ERROR / WARNING / [ALARME] et borne temporelle du log."""
    errors = warnings = alarms = 0
    first = last = ""
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as fh:
            if log_path.stat().st_size > max_bytes:  # garde-fou : on ne lit que la fin
                fh.seek(log_path.stat().st_size - max_bytes)
                fh.readline()
            for line in fh:
                if "| ERROR" in line:
                    errors += 1
                elif "| WARNING" in line:
                    warnings += 1
                if "[ALARME]" in line:
                    alarms += 1
                if len(line) > 19 and line[4] == "-" and line[13] == ":":
                    if not first:
                        first = line[:19]
                    last = line[:19]
    except OSError:
        return 0, 0, 0, None
    return errors, warnings, alarms, ((first, last) if first else None)


def list_runs(limit: int = 12) -> list[RunInfo]:
    """Runs les plus récents, sans dépouillement des logs (voir `log_counts`).

    `experiments/current` est un lien symbolique vers l'archive du run en cours :
    on dédoublonne sur le chemin résolu pour ne pas lister deux fois le même run,
    et on marque l'archive pointée comme « en cours ».
    """
    current = EXPERIMENTS / "current"
    current_target = current.resolve() if current.exists() else None

    candidates: list[Path] = []
    archive = EXPERIMENTS / "archive"
    if archive.is_dir():
        candidates += [p for p in archive.iterdir() if p.is_dir()]
    # `current` n'est ajouté que s'il ne pointe pas déjà dans l'archive listée.
    if current.is_dir() and current_target not in {p.resolve() for p in candidates}:
        candidates.append(current)

    runs: list[RunInfo] = []
    for path in candidates:
        log = path / "app.log"
        stat_target = log if log.is_file() else path
        try:
            mtime = datetime.fromtimestamp(stat_target.stat().st_mtime)
        except OSError:
            continue
        is_current = current_target is not None and path.resolve() == current_target
        name = "current" if path.name == "current" else path.name
        runs.append(
            RunInfo(
                path=path,
                label=f"{name} (en cours)" if is_current and path.name != "current" else name,
                is_current=is_current,
                modified=mtime,
                log_size=log.stat().st_size if log.is_file() else 0,
                has_moves=(path / "moves.csv").is_file(),
            )
        )

    runs.sort(key=lambda r: (r.is_current, r.modified), reverse=True)
    return runs[:limit]


def moves_stats(run_path: Path) -> MovesStats | None:
    """Statistiques du moves.csv d'un run (pandas requis)."""
    csv = run_path / "moves.csv"
    if not csv.is_file():
        return None
    try:
        import pandas as pd
    except ImportError:
        return None

    header = pd.read_csv(csv, nrows=0).columns.tolist()
    wanted = [
        "Mode de transport Choisi",
        "ID Personne",
        "Temps simulé",
        "Méthode de sélection",
        "P(Marche) %",
        "Retard planification (s)",
    ]
    usecols = [c for c in wanted if c in header]
    try:
        df = pd.read_csv(csv, usecols=usecols)
    except (ValueError, OSError):
        return None

    def counts(col: str) -> list[tuple[str, int]]:
        if col not in df:
            return []
        vc = df[col].value_counts()
        return [(str(k), int(v)) for k, v in vc.items()]

    sim_start = sim_end = None
    if "Temps simulé" in df:
        times = pd.to_numeric(df["Temps simulé"], errors="coerce").dropna()
        if not times.empty:
            sim_start = datetime.fromtimestamp(float(times.min()))
            sim_end = datetime.fromtimestamp(float(times.max()))

    delay_mean = delay_p95 = None
    if "Retard planification (s)" in df:
        delays = pd.to_numeric(df["Retard planification (s)"], errors="coerce").dropna()
        if not delays.empty:
            delay_mean = float(delays.mean())
            delay_p95 = float(delays.quantile(0.95))

    with_distribution = 0
    if "P(Marche) %" in df:
        with_distribution = int(df["P(Marche) %"].notna().sum())

    return MovesStats(
        trips=len(df),
        persons=int(df["ID Personne"].nunique()) if "ID Personne" in df else 0,
        modal_split=counts("Mode de transport Choisi"),
        selection=counts("Méthode de sélection"),
        with_distribution=with_distribution,
        sim_start=sim_start,
        sim_end=sim_end,
        delay_mean=delay_mean,
        delay_p95=delay_p95,
    )


# ── Synthèse des scores ───────────────────────────────────────────────────────
@dataclass
class SynthesisSummary:
    available: bool
    generated_at: str = ""
    run_id: str = ""
    run_pinned: bool = False
    n_trips: int = 0
    n_persons: int = 0
    pct_distribution: float = 0.0
    primary: str = ""
    dims: list[str] = field(default_factory=list)
    arms: list[dict] = field(default_factory=list)
    arm_status: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str = ""


def synthesis_summary() -> SynthesisSummary:
    if not SYNTHESIS_DATA.is_file():
        return SynthesisSummary(False, error="docs/synthesis/data.json absent — lancez `make synthesis`")
    try:
        data = json.loads(SYNTHESIS_DATA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return SynthesisSummary(False, error=f"data.json illisible : {exc}")

    common = data.get("common_set", {}) or {}
    synth = data.get("synthesis", {}) or {}
    dims = [d.get("label", d.get("key", "?")) for d in synth.get("dims", [])]
    arms = []
    for arm in synth.get("arms", []):
        cells = [c.get("value") for c in arm.get("cells", [])]
        arms.append({"label": arm.get("label", "?"), "cells": cells, "basis": arm.get("basis", "")})

    return SynthesisSummary(
        available=True,
        generated_at=str(data.get("generated_at", "")),
        run_id=str(common.get("run_id", "")),
        run_pinned=bool(common.get("run_pinned")),
        n_trips=int(common.get("n_trips") or 0),
        n_persons=int(common.get("n_persons") or 0),
        pct_distribution=float(common.get("pct_distribution") or 0.0),
        primary=str((data.get("score_def") or {}).get("primary", "")),
        dims=dims,
        arms=arms,
        arm_status={k: str((v or {}).get("status", "?")) for k, v in (data.get("arms") or {}).items()},
        warnings=[str(w) for w in (common.get("warnings") or [])],
    )


# ── Calibration de prompt ─────────────────────────────────────────────────────
@dataclass
class CalibBranch:
    store: str
    branch: str
    iteration: int | None
    best_score: float | None
    val_best: float | None
    accepted: int | None
    val_no_improve: int | None
    updated_at: str


@dataclass
class CalibStore:
    key: str
    path: Path
    available: bool
    nodes: int = 0
    evals: int = 0
    mutations: int = 0
    accepted: int = 0
    rejected: int = 0
    pending: int = 0
    branches: list[CalibBranch] = field(default_factory=list)
    last_activity: str = ""
    error: str = ""
    # Campagne génétique (ticket 009) : run_state de la branche spéciale __ga__.
    ga: dict | None = None
    # Veille quota : dernière ligne de la table cooldown (scope global).
    cooldown: dict | None = None
    modified: datetime | None = None

    @property
    def best(self) -> CalibBranch | None:
        scored = [b for b in self.branches if b.best_score is not None]
        return min(scored, key=lambda b: b.best_score) if scored else None


def _scalar(conn: sqlite3.Connection, sql: str, default=0):
    try:
        row = conn.execute(sql).fetchone()
    except sqlite3.Error:
        return default
    return default if row is None or row[0] is None else row[0]


def calibration_stores() -> list[CalibStore]:
    out: list[CalibStore] = []
    for key, path in CALIB_STORES.items():
        if not path.is_file():
            out.append(CalibStore(key, path, False, error="store absent"))
            continue
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            out.append(CalibStore(key, path, False, error=str(exc)))
            continue

        with conn:
            store = CalibStore(
                key=key,
                path=path,
                available=True,
                nodes=int(_scalar(conn, "SELECT COUNT(*) FROM nodes")),
                evals=int(_scalar(conn, "SELECT COUNT(*) FROM evals")),
                mutations=int(_scalar(conn, "SELECT COUNT(*) FROM mutations")),
                # verdicts observés : accepted / imported / proposed / rejected_{race,score,stat,tabu}
                accepted=int(_scalar(conn, "SELECT COUNT(*) FROM mutations WHERE verdict='accepted'")),
                rejected=int(_scalar(conn, "SELECT COUNT(*) FROM mutations WHERE verdict LIKE 'rejected%'")),
                pending=int(_scalar(conn, "SELECT COUNT(*) FROM mutations WHERE verdict='proposed'")),
                last_activity=str(_scalar(conn, "SELECT MAX(created_at) FROM evals", "") or ""),
            )
            try:
                rows = conn.execute("SELECT branch, state_json, updated_at FROM run_state").fetchall()
            except sqlite3.Error:
                rows = []

        for branch, state_json, updated_at in rows:
            try:
                state = json.loads(state_json or "{}")
            except json.JSONDecodeError:
                state = {}
            # Branches spéciales (__ga__, __islands__…) : hors du tableau des
            # branches ; __ga__ porte l'état de la campagne génétique.
            if str(branch).startswith("__"):
                if str(branch) == "__ga__":
                    store.ga = {**state, "updated_at": str(updated_at or "")}
                continue
            store.branches.append(
                CalibBranch(
                    store=key,
                    branch=str(branch),
                    iteration=state.get("iteration"),
                    best_score=state.get("best_score"),
                    val_best=state.get("val_best"),
                    accepted=state.get("accepted"),
                    val_no_improve=state.get("val_no_improve"),
                    updated_at=str(updated_at or ""),
                )
            )
        store.branches.sort(key=lambda b: (b.best_score is None, b.best_score))

        try:
            row = conn.execute(
                "SELECT scope, resume_after, reason FROM cooldown ORDER BY resume_after DESC LIMIT 1"
            ).fetchone()
        except sqlite3.Error:
            row = None
        finally:
            conn.close()
        if row is not None:
            store.cooldown = {"scope": row[0], "resume_after": str(row[1] or ""), "reason": row[2]}
        try:
            store.modified = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            pass
        out.append(store)
    return out


def cooldown_active(cooldown: dict | None) -> bool:
    """La veille quota est-elle encore en cours ? (resume_after dans le futur)"""
    if not cooldown or not cooldown.get("resume_after"):
        return False
    try:
        resume = datetime.fromisoformat(cooldown["resume_after"])
    except ValueError:
        return False
    from datetime import timezone

    now = datetime.now(timezone.utc) if resume.tzinfo else datetime.now()
    return resume > now


# ── Campagne génétique : détail de la population (ticket 009) ────────────────
@dataclass
class GaIndividual:
    hash: str
    label: str
    operator: str
    branch: str
    first_seen: int | None
    created_at: str
    # rank = LE score de sélection (la coupe se décide dessus) ;
    # screen ne sert qu'à confirmer le champion, val à l'early stopping.
    rank: float | None
    screen: float | None
    train: float | None
    val: float | None
    evals: int
    is_champion: bool

    @property
    def short(self) -> str:
        return self.hash[:8]


@dataclass
class GaDetails:
    available: bool
    generation: int = 0
    step: str = ""
    stopped: str = ""
    updated_at: str = ""
    champion: str | None = None
    champion_screen: float | None = None
    val_best: float | None = None
    val_no_improve: int = 0
    champion_by_gen: list = field(default_factory=list)
    population: list[GaIndividual] = field(default_factory=list)
    eliminated: int = 0
    survivors: int = 0
    children: int = 0
    evals_24h: int = 0
    last_eval: str = ""
    error: str = ""


def ga_details(store_path: Path) -> GaDetails:
    """Détail de la campagne génétique depuis la branche spéciale `__ga__` :
    population courante (origine, âge, scores), champion, activité récente.
    Lecture seule du store — pour la VM, c'est la copie rapatriée qui est lue."""
    if not store_path.is_file():
        return GaDetails(False, error="store absent")
    try:
        conn = sqlite3.connect(f"file:{store_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return GaDetails(False, error=str(exc))

    try:
        row = conn.execute(
            "SELECT state_json, updated_at FROM run_state WHERE branch='__ga__'"
        ).fetchone()
    except sqlite3.Error:
        row = None
    if row is None:
        conn.close()
        return GaDetails(False, error="pas d'état __ga__ dans ce store (campagne non démarrée ou store antérieur)")
    try:
        state = json.loads(row[0] or "{}")
    except json.JSONDecodeError:
        conn.close()
        return GaDetails(False, error="état __ga__ illisible")

    details = GaDetails(
        True,
        generation=int(state.get("generation") or 0),
        step=str(state.get("step") or ""),
        stopped=str(state.get("stopped") or ""),
        updated_at=str(row[1] or ""),
        champion=state.get("champion"),
        champion_screen=state.get("champion_screen"),
        val_best=state.get("val_best") if isinstance(state.get("val_best"), (int, float)) else None,
        val_no_improve=int(state.get("val_no_improve") or 0),
        champion_by_gen=state.get("champion_by_gen") or [],
        eliminated=len(state.get("eliminated") or []),
        survivors=len(state.get("survivors") or []),
        children=len(state.get("children") or []),
    )

    population: list[str] = list(state.get("population") or [])
    first_seen: dict = state.get("first_seen") or {}
    edge_ids: dict = state.get("edge_ids") or {}
    if population:
        marks = ",".join("?" for _ in population)
        node_rows = {
            r[0]: r
            for r in conn.execute(
                f"SELECT hash, branch, created_at FROM nodes WHERE hash IN ({marks})", population
            )
        }
        # Libellé et opérateur : la mutation d'origine (edge_ids → mutations.id).
        origins: dict[str, tuple[str, str]] = {}
        edge_list = [v for v in edge_ids.values() if isinstance(v, int)]
        if edge_list:
            marks = ",".join("?" for _ in edge_list)
            for node_to, operator, rationale in conn.execute(
                f"SELECT node_to, operator, rationale FROM mutations WHERE id IN ({marks})", edge_list
            ):
                origins[node_to] = (str(operator or ""), str(rationale or ""))
        # Scores : dernière éval par (nœud, dataset). `rank` est le score de
        # sélection GA ; screen confirme le champion, val fait l'early stopping.
        marks = ",".join("?" for _ in population)
        scores: dict[tuple[str, str], float] = {}
        counts: dict[str, int] = {}
        for node_hash, dataset, scores_json in conn.execute(
            f"SELECT node_hash, dataset, scores_json FROM evals WHERE node_hash IN ({marks}) "
            "ORDER BY created_at",
            population,
        ):
            counts[node_hash] = counts.get(node_hash, 0) + 1
            if dataset in ("rank", "screen", "train", "val"):
                try:
                    composite = json.loads(scores_json).get("composite")
                except (json.JSONDecodeError, AttributeError):
                    composite = None
                if composite is not None:
                    scores[(node_hash, dataset)] = float(composite)

        for node_hash in population:
            node = node_rows.get(node_hash)
            operator, rationale = origins.get(node_hash, ("", ""))
            label = rationale.split("—")[0].strip() if rationale else (node[1] if node else "?")
            details.population.append(
                GaIndividual(
                    hash=node_hash,
                    label=label[:60],
                    operator=operator,
                    branch=node[1] if node else "?",
                    first_seen=first_seen.get(node_hash),
                    created_at=(node[2] or "")[:16] if node else "",
                    rank=scores.get((node_hash, "rank")),
                    screen=scores.get((node_hash, "screen")),
                    train=scores.get((node_hash, "train")),
                    val=scores.get((node_hash, "val")),
                    evals=counts.get(node_hash, 0),
                    is_champion=(node_hash == details.champion),
                )
            )
        details.population.sort(key=lambda i: (i.rank is None, i.rank))

    from datetime import timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    details.evals_24h = int(
        _scalar(conn, f"SELECT COUNT(*) FROM evals WHERE created_at >= '{cutoff}'")
    )
    details.last_eval = str(_scalar(conn, "SELECT MAX(created_at) FROM evals", "") or "")
    conn.close()
    return details


# ── Avancement local de la calibration (progress.json) ───────────────────────
CALIB_PROGRESS = REPO_ROOT / "prompt_calibration" / "calibration_results" / "progress.json"


@dataclass
class CalibProgress:
    available: bool
    data: dict = field(default_factory=dict)
    age_s: float | None = None
    error: str = ""

    @property
    def liveness(self) -> str:
        """Heuristique de vivacité du daemon — même logique que `calibrate progress`."""
        if not self.available:
            return "inconnu"
        if self.age_s is not None and self.age_s > 900:
            return "arrêté"
        return "actif"


def calib_progress() -> CalibProgress:
    """Instantané `progress.json` écrit par le daemon de calibration **local**.

    L'avancement de la VM cloud ne se lit qu'à la demande (`make cloud-progress`,
    SSH) : ce fichier ne reflète que la dernière passe exécutée sur cette machine."""
    if not CALIB_PROGRESS.is_file():
        return CalibProgress(False, error="pas de progress.json local")
    try:
        data = json.loads(CALIB_PROGRESS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return CalibProgress(False, error=f"progress.json illisible : {exc}")
    age = None
    updated = data.get("updated_at")
    if updated:
        try:
            from datetime import timezone

            stamp = datetime.fromisoformat(str(updated))
            now = datetime.now(timezone.utc) if stamp.tzinfo else datetime.now()
            age = (now - stamp).total_seconds()
        except ValueError:
            pass
    return CalibProgress(True, data, age_s=age)


# ── Run GAMA : progression et santé ──────────────────────────────────────────
def agent_states(run_path: Path):
    """Courbe inactifs/prêts/actifs du run — `gama_results/agent_states.csv`,
    une ligne par `/sync` du controller. None si absent ou illisible."""
    csv = run_path / "gama_results" / "agent_states.csv"
    if not csv.is_file():
        return None
    try:
        import pandas as pd

        df = pd.read_csv(csv)
    except (ImportError, ValueError, OSError):
        return None
    needed = {"step", "sim_time", "inactive", "ready", "active", "total"}
    return df if needed.issubset(df.columns) else None


_LOG_PREFIX_RE = None


def top_log_messages(
    log_path: Path, level: str = "ERROR", limit: int = 8, max_bytes: int = 64 * 1024 * 1024
) -> list[tuple[int, str]]:
    """Messages ERROR/WARNING les plus fréquents, normalisés (nombres → N,
    identifiants hex → #). Retourne [(occurrences, exemple)] trié décroissant."""
    global _LOG_PREFIX_RE
    import re

    if _LOG_PREFIX_RE is None:
        _LOG_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[.,]?\d*\s*\|\s*\w+\s*\|\s*")
    marker = f"| {level}"
    counts: dict[str, int] = {}
    examples: dict[str, str] = {}
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as fh:
            if log_path.stat().st_size > max_bytes:
                fh.seek(log_path.stat().st_size - max_bytes)
                fh.readline()
            for line in fh:
                if marker not in line:
                    continue
                message = _LOG_PREFIX_RE.sub("", line).strip()
                key = re.sub(r"0x[0-9a-fA-F]+|[0-9a-f]{8,}", "#", message)
                key = re.sub(r"\d+(?:\.\d+)?", "N", key)[:200]
                counts[key] = counts.get(key, 0) + 1
                examples.setdefault(key, message[:300])
    except OSError:
        return []
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [(n, examples[key]) for key, n in ranked]


@dataclass
class LlmErrorStats:
    total: int = 0
    by_provider: list[tuple[str, int]] = field(default_factory=list)
    n_429: int = 0
    by_provider_429: list[tuple[str, int]] = field(default_factory=list)
    last_time: str = ""


def llm_errors_stats(run_path: Path) -> LlmErrorStats:
    """Dépouillement de `llm_errors.jsonl` (une ligne JSON par erreur LLM)."""
    path = run_path / "llm_errors.jsonl"
    stats = LlmErrorStats()
    if not path.is_file():
        return stats
    by_provider: dict[str, int] = {}
    by_provider_429: dict[str, int] = {}
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                stats.total += 1
                provider = str(rec.get("provider") or "?")
                by_provider[provider] = by_provider.get(provider, 0) + 1
                if rec.get("http_status") == 429:
                    stats.n_429 += 1
                    by_provider_429[provider] = by_provider_429.get(provider, 0) + 1
                stats.last_time = str(rec.get("time") or stats.last_time)
    except OSError:
        return stats
    stats.by_provider = sorted(by_provider.items(), key=lambda kv: kv[1], reverse=True)
    stats.by_provider_429 = sorted(by_provider_429.items(), key=lambda kv: kv[1], reverse=True)
    return stats


def llm_cache_hit_rate(run_path: Path) -> tuple[float, int, int] | None:
    """Hit rate du cache sémantique LLM = hits / (hits + appels réels).

    `llm_cache_hits.jsonl` est du vrai JSONL (1 ligne = 1 hit) ;
    `llm_exchanges.jsonl` est une concaténation d'objets JSON indentés — on
    compte les lignes réduites à `{`, qui ouvrent chaque objet (même calcul que
    scripts/debug/run_report.py)."""
    hits_path = run_path / "llm_cache_hits.jsonl"
    exch_path = run_path / "llm_exchanges.jsonl"
    if not hits_path.is_file() and not exch_path.is_file():
        return None

    def count_lines(path: Path, predicate) -> int:
        if not path.is_file():
            return 0
        n = 0
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if predicate(line):
                        n += 1
        except OSError:
            return 0
        return n

    hits = count_lines(hits_path, lambda l: l.strip().startswith("{"))
    exchanges = count_lines(exch_path, lambda l: l.rstrip("\n") == "{")
    total = hits + exchanges
    if not total:
        return None
    return 100 * hits / total, hits, exchanges


# ── Providers (lecture statique de providers.yaml) ───────────────────────────
PROVIDERS_YAML = REPO_ROOT / "llm_module" / "config" / "providers.yaml"


@dataclass
class ProvidersStatic:
    available: bool
    providers: list[dict] = field(default_factory=list)
    refreshed_at: datetime | None = None
    error: str = ""


def providers_static() -> ProvidersStatic:
    """Providers déclarés dans `providers.yaml` (les blocs commentés — modèles
    retirés — sont invisibles de yaml.safe_load, c'est voulu). Le mtime du
    fichier date le dernier `make providers`."""
    if not PROVIDERS_YAML.is_file():
        return ProvidersStatic(False, error="llm_module/config/providers.yaml absent")
    try:
        import yaml

        data = yaml.safe_load(PROVIDERS_YAML.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001 — yaml.YAMLError + OSError
        return ProvidersStatic(False, error=f"providers.yaml illisible : {exc}")

    providers = []
    for name, cfg in (data.get("providers") or {}).items():
        cfg = cfg or {}
        providers.append(
            {
                "name": name,
                "adapter": cfg.get("adapter", name),
                "model": cfg.get("default_model", "?"),
                "rpm_limit": cfg.get("rpm_limit"),
                "tpm_limit": cfg.get("tpm_limit"),
                "rpd_limit": cfg.get("rpd_limit"),
                "tpd_limit": cfg.get("tpd_limit"),
                "weight": cfg.get("weight", 1.0),
            }
        )
    providers.sort(key=lambda p: p["name"])
    return ProvidersStatic(
        True, providers, refreshed_at=datetime.fromtimestamp(PROVIDERS_YAML.stat().st_mtime)
    )


# ── Divers ────────────────────────────────────────────────────────────────────
def git_state() -> dict[str, str]:
    def run(*args: str) -> str:
        try:
            proc = subprocess.run(  # noqa: S603 — commandes git fixes
                ["git", *args], cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=5
            )
        except (subprocess.TimeoutExpired, OSError):
            return ""
        return proc.stdout.strip() if proc.returncode == 0 else ""

    dirty = run("status", "--porcelain")
    return {
        "branch": run("rev-parse", "--abbrev-ref", "HEAD") or "?",
        "head": run("log", "-1", "--pretty=%h %s"),
        "head_date": run("log", "-1", "--pretty=%cd", "--date=short"),
        "dirty": str(len([line for line in dirty.splitlines() if line.strip()])),
    }


def human_size(num: float) -> str:
    for unit in ("o", "Ko", "Mo", "Go"):
        if abs(num) < 1024:
            return f"{num:.0f} {unit}" if unit == "o" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} To"
