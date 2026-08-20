"""Lancement et suivi des cibles `make` depuis le dashboard.

Chaque lancement est un sous-processus détaché (`start_new_session`) dont la
sortie est écrite dans `experiments/.dashboard/<job>.log`. Le registre survit
aux reruns Streamlit (`st.cache_resource`), ce qui permet de suivre un job
pendant qu'il tourne et de l'arrêter proprement (SIGTERM au groupe de
processus, puis SIGKILL après un délai de grâce).
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = REPO_ROOT / "experiments" / ".dashboard"

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


@dataclass
class Job:
    id: str
    label: str
    argv: list[str]
    cwd: Path
    log_path: Path
    started_at: float
    proc: subprocess.Popen | None = None
    returncode: int | None = None
    finished_at: float | None = None
    stopped_by_user: bool = False
    error: str | None = None
    flags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def running(self) -> bool:
        return self.proc is not None and self.returncode is None

    @property
    def duration(self) -> float:
        return (self.finished_at or time.time()) - self.started_at

    @property
    def state(self) -> str:
        if self.error:
            return "erreur"
        if self.running:
            return "en cours"
        if self.stopped_by_user:
            return "arrêté"
        return "ok" if self.returncode == 0 else "échec"

    @property
    def command_line(self) -> str:
        return " ".join(self.argv)


class Registry:
    """Registre de jobs, partagé par toutes les reruns du serveur Streamlit."""

    def __init__(self) -> None:
        self._jobs: list[Job] = []
        self._lock = threading.Lock()
        self._counter = 0
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ── lecture ───────────────────────────────────────────────────────────────
    def jobs(self) -> list[Job]:
        with self._lock:
            self._reap()
            return list(reversed(self._jobs))

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            self._reap()
            return next((j for j in self._jobs if j.id == job_id), None)

    def running_count(self) -> int:
        return sum(1 for j in self.jobs() if j.running)

    def _reap(self) -> None:
        for job in self._jobs:
            if job.proc is not None and job.returncode is None:
                code = job.proc.poll()
                if code is not None:
                    job.returncode = code
                    job.finished_at = time.time()

    # ── écriture ──────────────────────────────────────────────────────────────
    def launch(self, label: str, argv: list[str], cwd: Path, flags: tuple[str, ...] = ()) -> Job:
        with self._lock:
            self._counter += 1
            slug = re.sub(r"[^A-Za-z0-9]+", "-", label).strip("-").lower()[:48]
            job_id = f"{self._counter:03d}-{slug}"
            log_path = LOG_DIR / f"{job_id}.log"
            job = Job(
                id=job_id,
                label=label,
                argv=argv,
                cwd=cwd,
                log_path=log_path,
                started_at=time.time(),
                flags=flags,
            )
            try:
                handle = log_path.open("w", encoding="utf-8", errors="replace")
                handle.write(f"$ cd {cwd}\n$ {' '.join(argv)}\n\n")
                handle.flush()
                job.proc = subprocess.Popen(  # noqa: S603 — argv construit depuis le Makefile
                    argv,
                    cwd=str(cwd),
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                    env={**os.environ, "TERM": "dumb", "NO_COLOR": "1", "PYTHONUNBUFFERED": "1"},
                )
            except OSError as exc:
                job.error = str(exc)
                job.finished_at = time.time()
                job.returncode = -1
            self._jobs.append(job)
            return job

    def stop(self, job_id: str, grace: float = 5.0) -> bool:
        """SIGTERM au groupe de processus, SIGKILL si toujours vivant après `grace`."""
        job = self.get(job_id)
        if job is None or job.proc is None or not job.running:
            return False
        job.stopped_by_user = True
        try:
            pgid = os.getpgid(job.proc.pid)
        except ProcessLookupError:
            return False
        for sig, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, 1.0)):
            try:
                os.killpg(pgid, sig)
            except ProcessLookupError:
                break
            try:
                job.proc.wait(timeout=wait)
                break
            except subprocess.TimeoutExpired:
                continue
        job.returncode = job.proc.poll()
        job.finished_at = time.time()
        return True

    def stop_all(self) -> int:
        return sum(1 for job in self.jobs() if job.running and self.stop(job.id))

    def clear_finished(self) -> None:
        with self._lock:
            self._reap()
            self._jobs = [j for j in self._jobs if j.running]


def tail(job: Job, max_lines: int = 400) -> str:
    """Dernières lignes du log d'un job, débarrassées des codes ANSI."""
    try:
        raw = job.log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(log indisponible)"
    lines = _ANSI_RE.sub("", raw).replace("\r", "\n").splitlines()
    clipped = lines[-max_lines:]
    prefix = f"… {len(lines) - len(clipped)} lignes antérieures dans {job.log_path.name}\n" if len(lines) > len(clipped) else ""
    return prefix + "\n".join(clipped)


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:02d}s"
    return f"{seconds // 3600}h {(seconds % 3600) // 60:02d}m"
