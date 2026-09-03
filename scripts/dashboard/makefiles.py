"""Lecture des Makefile du dépôt : cibles, documentation, métadonnées d'exécution.

La documentation d'une cible est le bloc de commentaires `##` qui la précède
immédiatement — convention déjà en place dans les Makefile du dépôt. Les
métadonnées d'exécution (cible bloquante, destructive, consommatrice de quota
LLM, interactive) sont déclarées ici : elles ne sont pas déductibles du Makefile.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_TARGET_RE = re.compile(r"^([A-Za-z0-9_.\-]+(?:[ \t]+[A-Za-z0-9_.\-]+)*)[ \t]*:(?!=)")
_DOC_RE = re.compile(r"^##[ \t]?(.*)$")

# ── Drapeaux d'exécution ──────────────────────────────────────────────────────
# long        : ne rend pas la main (suivi de logs, serveur, run GAMA)
# interactive : attend une réponse au clavier → inlançable depuis le dashboard
# danger      : destructif (suppression de données, d'images, de caches)
# llm         : consomme du quota LLM payant ou rationné
# gui         : ouvre une fenêtre externe (navigateur, GAMA)
FLAG_LABELS = {
    "long": ("⏳", "ne rend pas la main — arrêtez-la avec « Stop »"),
    "interactive": ("⌨️", "attend une saisie clavier : à lancer dans un terminal"),
    "danger": ("🔥", "destructif — confirmation requise"),
    "llm": ("💸", "consomme du quota LLM — chiffrez d'abord avec DRY_RUN=1"),
    "gui": ("🪟", "ouvre une fenêtre ou un onglet externe"),
}


@dataclass(frozen=True)
class Variable:
    name: str
    help: str = ""
    kind: str = "text"  # text | bool | choice
    choices: tuple[str, ...] = ()
    placeholder: str = ""


@dataclass
class Target:
    name: str
    project: str
    project_label: str
    cwd: Path
    makefile: Path
    line: int
    doc: str = ""
    group: str = "Autres"
    flags: tuple[str, ...] = ()
    variables: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return f"{self.project}:{self.name}"

    @property
    def launchable(self) -> bool:
        return "interactive" not in self.flags

    def command(self, values: dict[str, str]) -> list[str]:
        argv = ["make", self.name]
        argv += [f"{k}={v}" for k, v in values.items() if v not in ("", None)]
        return argv


# ── Métadonnées par cible ─────────────────────────────────────────────────────
# (projet, cible) → (groupe, drapeaux, variables proposées)
_META: dict[tuple[str, str], tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    # racine — Docker
    ("root", "up"): ("Docker", (), ()),
    ("root", "down"): ("Docker", (), ()),
    ("root", "restart"): ("Docker", (), ()),
    ("root", "ps"): ("Docker", (), ()),
    ("root", "logs"): ("Docker", ("long",), ()),
    ("root", "rebuild"): ("Docker", ("long",), ()),
    ("root", "api"): ("Docker", ("long",), ()),
    ("root", "otp"): ("Docker", ("long",), ()),
    # racine — diagnostic
    ("root", "error"): ("Diagnostic", (), ("LOG",)),
    ("root", "warning"): ("Diagnostic", (), ("LOG",)),
    ("root", "report"): ("Diagnostic", (), ("RUN", "OUT")),
    ("root", "capacity"): ("Diagnostic", (), ("RUN", "OUT")),
    ("root", "init"): ("Diagnostic", (), ("RUN", "OUT")),
    # racine — tests
    ("root", "tests"): ("Tests", (), ()),
    ("root", "burst"): ("Tests", ("long",), ()),
    ("root", "analysis"): ("Tests", ("long",), ("LOG_DIR",)),
    # racine — synthèse
    ("root", "synthesis"): ("Synthèse des scores", (), ("RUN",)),
    ("root", "synthesis-open"): ("Synthèse des scores", ("gui",), ("RUN",)),
    ("root", "common-set-eval"): (
        "Synthèse des scores",
        ("llm", "long"),
        ("DRY_RUN", "PROVIDER", "BATCH"),
    ),
    ("root", "heldout-eval"): (
        "Synthèse des scores",
        ("llm", "long"),
        ("DRY_RUN", "PROVIDER", "BATCH", "NODES", "DATASET"),
    ),
    # racine — modèle de choix modal
    ("root", "zones"): ("Modèle de choix modal", (), ()),
    ("root", "housing-type"): ("Modèle de choix modal", (), ()),
    ("root", "policy"): ("Modèle de choix modal", (), ()),
    ("root", "common-set-predict"): ("Modèle de choix modal", (), ("DRY_RUN",)),
    # racine — GAMA
    # `run` et `run-offline` purgent Grafana/Prometheus et les compteurs Redis
    # avant de démarrer → danger.
    ("root", "wait-ready"): ("GAMA", ("long",), ()),
    ("root", "run"): ("GAMA", ("long", "gui", "danger"), ("EXPERIMENT_NAME",)),
    ("root", "run-offline"): ("GAMA", ("long", "danger"), ("EXPERIMENT_NAME",)),
    ("root", "status"): ("GAMA", (), ()),
    ("root", "stop-run"): ("GAMA", (), ()),
    # racine — pilotage
    ("root", "dashboard"): ("Pilotage", ("long", "gui"), ("DASHBOARD_PORT",)),
    ("root", "providers"): ("Pilotage", (), ("DRY_RUN",)),
    # racine — maintenance
    ("root", "purge_cache"): ("Maintenance", ("danger",), ()),
    ("root", "clean"): ("Maintenance", ("danger", "interactive"), ()),
    ("root", "clean_all"): ("Maintenance", ("danger", "interactive"), ()),
    # prompt_calibration — campagne
    ("calib", "run"): ("Campagne", ("llm", "long"), ("ESSAI", "CONFIG", "ITER", "ISLANDS")),
    ("calib", "resume"): ("Campagne", ("llm", "long"), ("ESSAI", "CONFIG", "ITER", "ISLANDS")),
    ("calib", "status"): ("Campagne", (), ("ESSAI",)),
    ("calib", "progress"): ("Campagne", (), ("ESSAI",)),
    ("calib", "export"): ("Campagne", (), ("ESSAI",)),
    ("calib", "finalize"): ("Campagne", ("llm", "long"), ("ESSAI", "WRITE")),
    ("calib", "backtest"): ("Campagne", (), ("ESSAI",)),
    ("calib", "datasets"): ("Campagne", (), ()),
    ("calib", "test"): ("Campagne", (), ()),
    # prompt_calibration — cloud
    ("calib", "cloud-status"): ("Cloud (calib-vm)", (), ("VM", "ZONE")),
    ("calib", "cloud-progress"): ("Cloud (calib-vm)", (), ("VM", "ZONE")),
    ("calib", "cloud-logs"): ("Cloud (calib-vm)", (), ("VM", "ZONE", "LINES", "GREP", "UNIT")),
    ("calib", "pull-cloud"): ("Cloud (calib-vm)", ("long", "gui"), ("VM", "ZONE", "PORT")),
    ("calib", "pull-db"): ("Cloud (calib-vm)", (), ("VM", "ZONE", "LOCAL_DB")),
    ("calib", "pull-reports"): ("Cloud (calib-vm)", (), ("VM", "ZONE")),
    ("calib", "cloud-deploy"): ("Cloud (calib-vm)", (), ("VM", "ZONE")),
    ("calib", "pause"): ("Cloud (calib-vm)", (), ("VM", "ZONE")),
    ("calib", "start"): ("Cloud (calib-vm)", (), ("VM", "ZONE")),
    # prompt_calibration — divers
    ("calib", "ui"): ("Dashboard calibration", ("long", "gui"), ("CONFIG", "PORT")),
    ("calib", "dashboard"): ("Dashboard calibration", ("long", "gui"), ("CONFIG", "PORT")),
    ("calib", "help"): ("Dashboard calibration", (), ()),
    ("calib", "clean"): ("Maintenance", ("danger",), ()),
    # OTP
    ("otp", "build-graph"): ("Graphe OTP", ("long",), ()),
    ("otp", "serve"): ("Graphe OTP", ("long",), ()),
}

GROUP_ORDER = [
    "Docker",
    "GAMA",
    "Pilotage",
    "Diagnostic",
    "Synthèse des scores",
    "Modèle de choix modal",
    "Tests",
    "Campagne",
    "Cloud (calib-vm)",
    "Dashboard calibration",
    "Graphe OTP",
    "Maintenance",
    "Autres",
]


@dataclass
class Project:
    key: str
    label: str
    makefile: Path
    cwd: Path
    variables: dict[str, Variable] = field(default_factory=dict)


def _run_choices() -> tuple[str, ...]:
    out: list[str] = []
    cur = REPO_ROOT / "experiments" / "current"
    if cur.is_dir():
        out.append("experiments/current")
    arch = REPO_ROOT / "experiments" / "archive"
    if arch.is_dir():
        dirs = sorted((p for p in arch.iterdir() if p.is_dir()), reverse=True)
        out += [f"experiments/archive/{p.name}" for p in dirs]
    return tuple(out)


def _calib_config_choices() -> tuple[str, ...]:
    cfg = REPO_ROOT / "prompt_calibration" / "config"
    return tuple(sorted(p.name for p in cfg.glob("*.yaml"))) if cfg.is_dir() else ()


def _root_variables() -> dict[str, Variable]:
    return {
        "RUN": Variable("RUN", "Run analysé (défaut : le plus récent)", "choice", _run_choices()),
        "LOG": Variable("LOG", "Fichier de log", "text", placeholder="experiments/current/app.log"),
        "OUT": Variable("OUT", "Écrire le rapport dans ce fichier", "text", placeholder="rapport.md"),
        "LOG_DIR": Variable("LOG_DIR", "Dossier de run pour les notebooks", "choice", _run_choices()),
        "DRY_RUN": Variable("DRY_RUN", "Chiffrer sans exécuter (DRY_RUN=1)", "bool"),
        "PROVIDER": Variable("PROVIDER", "Fournisseur LLM d'évaluation", "text", placeholder="google2"),
        "BATCH": Variable("BATCH", "Taille de lot d'évaluation", "text", placeholder="10"),
        "NODES": Variable("NODES", "Nœuds évalués", "text", placeholder="all"),
        "DATASET": Variable("DATASET", "Jeu gelé visé", "text", placeholder="test"),
        "EXPERIMENT_NAME": Variable("EXPERIMENT_NAME", "Expérience GAMA", "text", placeholder="e"),
        "DASHBOARD_PORT": Variable("DASHBOARD_PORT", "Port du présent dashboard", "text", placeholder="8503"),
    }


def _calib_variables() -> dict[str, Variable]:
    return {
        "ESSAI": Variable("ESSAI", "Branche / essai visé", "text", placeholder="essai3"),
        "CONFIG": Variable("CONFIG", "Config de campagne", "choice", _calib_config_choices()),
        "ITER": Variable("ITER", "Nombre d'itérations", "text", placeholder="20"),
        "ISLANDS": Variable("ISLANDS", "Nombre d'îlots parallèles", "text", placeholder="4"),
        "PORT": Variable("PORT", "Port du dashboard Streamlit", "text", placeholder="8502"),
        "WRITE": Variable("WRITE", "Publier réellement (WRITE=1)", "bool"),
        "VM": Variable("VM", "Nom de la VM", "text", placeholder="calib-vm"),
        "ZONE": Variable("ZONE", "Zone GCP", "text", placeholder="us-central1-a"),
        "LINES": Variable("LINES", "Lignes de journal", "text", placeholder="200"),
        "GREP": Variable("GREP", "Filtre sur les logs", "text", placeholder="Shapley"),
        "UNIT": Variable("UNIT", "Unité systemd suivie", "choice", ("calib-ga", "calib")),
        "LOCAL_DB": Variable(
            "LOCAL_DB",
            "Destination du store rapatrié",
            "text",
            placeholder="calibration_results/calibration_cloud.db",
        ),
    }


def projects() -> list[Project]:
    return [
        Project("root", "llm-agents-gama (racine)", REPO_ROOT / "Makefile", REPO_ROOT, _root_variables()),
        Project(
            "calib",
            "prompt_calibration",
            REPO_ROOT / "prompt_calibration" / "Makefile",
            REPO_ROOT / "prompt_calibration",
            _calib_variables(),
        ),
        Project("otp", "otp-toulouse", REPO_ROOT / "otp-toulouse" / "Makefile", REPO_ROOT / "otp-toulouse", {}),
    ]


def parse_makefile(project: Project) -> list[Target]:
    """Extrait les cibles d'un Makefile, avec leur bloc de doc `##`."""
    if not project.makefile.is_file():
        return []

    targets: list[Target] = []
    doc_lines: list[str] = []
    seen: set[str] = set()

    for lineno, raw in enumerate(project.makefile.read_text(encoding="utf-8").splitlines(), 1):
        doc = _DOC_RE.match(raw)
        if doc:
            doc_lines.append(doc.group(1).strip())
            continue

        match = _TARGET_RE.match(raw)
        if not match:
            # Une ligne vide ou une recette rompt le rattachement du bloc de doc.
            if not raw.strip() or raw.startswith("\t"):
                doc_lines = []
            continue

        names = match.group(1).split()
        if names[0].startswith(".") or "=" in raw.split(":", 1)[0]:
            doc_lines = []
            continue

        for name in names:
            if name in seen:
                continue
            seen.add(name)
            group, flags, variables = _META.get((project.key, name), ("Autres", (), ()))
            targets.append(
                Target(
                    name=name,
                    project=project.key,
                    project_label=project.label,
                    cwd=project.cwd,
                    makefile=project.makefile,
                    line=lineno,
                    doc=" ".join(doc_lines).strip(),
                    group=group,
                    flags=flags,
                    variables=variables,
                )
            )
        doc_lines = []

    return targets


def all_targets() -> tuple[list[Project], dict[str, list[Target]]]:
    """Retourne les projets et leurs cibles, indexées par clé de projet."""
    projs = projects()
    return projs, {p.key: parse_makefile(p) for p in projs}


def grouped(targets: list[Target]) -> list[tuple[str, list[Target]]]:
    """Regroupe les cibles par groupe, dans l'ordre déclaré."""
    buckets: dict[str, list[Target]] = {}
    for t in targets:
        buckets.setdefault(t.group, []).append(t)
    order = {g: i for i, g in enumerate(GROUP_ORDER)}
    return sorted(buckets.items(), key=lambda kv: order.get(kv[0], len(order)))
