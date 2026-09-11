"""Registre de réservation des clés API (ticket 035, spec parallelisation_experiences).

Le débit LLM est plafonné par clé API : deux expériences actives ne peuvent tourner en parallèle
que si leurs jeux de clés sont **disjoints** (R1). Ce registre est la source de vérité, partagée
et atomique, de « quelle clé est tenue par quelle exécution ». Il vit sur `data/experiences/`,
un bind-mount visible à la fois dans le conteneur `controller` (où tournent les exécutions) et
sur l'hôte (où tourne l'ordonnanceur).

Atomicité (R6) : toute séquence lire → décider → écrire se fait sous un **verrou global** par
création exclusive de dossier (`mkdir`, atomique sur le même système de fichiers, valable
hôte ↔ conteneur sur le bind-mount). Un verrou plus vieux que `VERROU_TTL_S` est réputé abandonné
et volé (aucun processus ne tient le verrou aussi longtemps : la section critique est un
read-modify-write de quelques millisecondes).

Réservation ↔ processus : une clé est tenue tant que l'exécution n'a pas de **statut terminal**
(R7). Le cas normal (fin, arrêt, exception, SIGTERM) libère dans le `finally` de `cmd_lancer`.
Le cas du processus **tué durement** (SIGKILL, OOM) laisse une réservation orpheline : c'est
`reconcilier()` qui la détecte — en testant la vie du pid, ce qui n'a de sens que **dans le
namespace du conteneur** où le processus vit. `reconcilier()` ne doit donc être appelé que
depuis le conteneur (`python -m experiences reconcilier`), jamais depuis l'hôte.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Self

from loguru import logger

from experiences.archive import ETAT_INTERROMPUE, ETATS_FINAUX, F_ETAT
from experiences.experience import dossier_experiences

VERROU_TTL_S = 30.0
_ATTENTE_VERROU_S = 5.0
_PAS_ATTENTE_S = 0.05


def _base() -> Path:
    return dossier_experiences()


def _chemin_registre() -> Path:
    return _base() / ".reservations.json"


def _chemin_verrou() -> Path:
    return _base() / ".reservations.lock"


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class _Verrou:
    """Verrou global inter-processus par `mkdir` exclusif, avec vol d'un verrou périmé."""

    def __enter__(self) -> Self:
        verrou = _chemin_verrou()
        verrou.parent.mkdir(parents=True, exist_ok=True)
        debut = time.monotonic()
        while True:
            try:
                verrou.mkdir()
                return self
            except FileExistsError:
                try:
                    age = time.time() - verrou.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age > VERROU_TTL_S:
                    logger.warning(
                        f"[reservations] verrou périmé ({age:.0f}s > {VERROU_TTL_S:.0f}s) — volé"
                    )
                    try:
                        verrou.rmdir()
                    except FileNotFoundError:
                        pass
                    continue
                if time.monotonic() - debut > _ATTENTE_VERROU_S:
                    # Fail-safe (R12) : plutôt attendre l'appelant que risquer une écriture concurrente.
                    raise TimeoutError(
                        f"verrou de réservation indisponible après {_ATTENTE_VERROU_S:.0f}s"
                    )
                time.sleep(_PAS_ATTENTE_S)

    def __exit__(self, *exc) -> None:
        try:
            _chemin_verrou().rmdir()
        except FileNotFoundError:
            pass


def _lire() -> dict[str, dict]:
    p = _chemin_registre()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {}
    except (json.JSONDecodeError, OSError) as e:
        logger.error(
            f"[reservations] registre illisible ({p}) : {e} — réinitialisé vide"
        )
        return {}


def _ecrire(registre: dict[str, dict]) -> None:
    p = _chemin_registre()
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(registre, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def _etat_execution(dossier: str) -> str | None:
    """Statut courant d'une exécution, lu directement dans `etat.json` (léger, sans ouvrir l'archive)."""
    p = Path(dossier) / F_ETAT
    if not p.is_file():
        return None
    try:
        return (json.loads(p.read_text(encoding="utf-8")) or {}).get("etat")
    except (json.JSONDecodeError, OSError):
        return None


def _pid_vivant(pid: int) -> bool:
    """Le processus existe-t-il DANS CE namespace ? (n'a de sens que dans le conteneur, cf. module.)"""
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # vivant mais pas à nous
    return True


def _interrompre(dossier: str, raison: str) -> None:
    """Passe une exécution fantôme en statut terminal `interrompue` pour libérer ses clés (R7)."""
    from experiences.archive import Execution

    try:
        Execution.ouvrir(dossier).changer_etat(ETAT_INTERROMPUE, raison=raison)
    except Exception as e:  # noqa: BLE001 — la réconciliation ne doit jamais planter l'ordonnanceur
        logger.error(f"[reservations] réconciliation impossible pour {dossier} : {e}")


def _reconcilier(registre: dict[str, dict], *, tester_pid: bool) -> dict[str, dict]:
    """Retire les clés dont l'exécution est terminée ; réconcilie les fantômes (pid mort)."""
    garde: dict[str, dict] = {}
    interrompus: set[str] = set()
    for cle, e in registre.items():
        dossier = e.get("execution", "")
        etat = _etat_execution(dossier)
        if etat in ETATS_FINAUX:
            continue  # clé libérée : statut terminal
        if tester_pid and not _pid_vivant(int(e.get("pid") or 0)):
            if dossier not in interrompus:
                _interrompre(dossier, f"processus {e.get('pid')} disparu (clé {cle})")
                interrompus.add(dossier)
            continue
        garde[cle] = e
    return garde


# ── API ───────────────────────────────────────────────────────────────────────


def reconcilier() -> list[str]:
    """Libère les clés des exécutions terminées ET des fantômes (pid mort). À N'appeler que
    dans le conteneur (le test de pid dépend du namespace). Renvoie les clés libérées."""
    with _Verrou():
        avant = _lire()
        apres = _reconcilier(avant, tester_pid=True)
        if apres != avant:
            _ecrire(apres)
        return sorted(set(avant) - set(apres))


def _conflits(registre: dict[str, dict], cles: set[str], dossier: str) -> set[str]:
    """Clés déjà tenues par une AUTRE exécution (une réservation de soi-même n'est pas un conflit)."""
    return {
        c for c in cles if c in registre and registre[c].get("execution") != dossier
    }


def _poser(
    registre: dict[str, dict], cles: set[str], dossier: str, exp_nom: str, pid: int
) -> None:
    for c in cles:
        registre[c] = {
            "execution": dossier,
            "exp": exp_nom,
            "pid": pid,
            "depuis": _iso(),
        }


def reserver(
    cles: set[str], dossier_execution: str | Path, exp_nom: str, pid: int | None = None
) -> bool:
    """Réserve atomiquement TOUT `cles` pour cette exécution, ou rien (R1/R6).

    Renvoie True si réservé (aucune clé tenue par une autre exécution), False sinon. Un jeu de
    clés vide est toujours accordé (R8 : expérience sans appel passerelle)."""
    dossier = str(Path(dossier_execution))
    pid = int(pid if pid is not None else os.getpid())
    with _Verrou():
        registre = _reconcilier(_lire(), tester_pid=True)
        conflits = _conflits(registre, cles, dossier)
        if conflits:
            retenues = sorted(f"{c}←{registre[c].get('exp', '?')}" for c in conflits)
            logger.info(
                f"[reservations] {exp_nom} en conflit sur {len(conflits)} clé(s) : {', '.join(retenues)}"
            )
            return False
        _poser(registre, cles, dossier, exp_nom, pid)
        _ecrire(registre)
        if cles:
            logger.info(f"[reservations] {exp_nom} réserve {sorted(cles)}")
        return True


def liberer(dossier_execution: str | Path) -> list[str]:
    """Libère toutes les clés tenues par cette exécution. Renvoie les clés libérées."""
    dossier = str(Path(dossier_execution))
    with _Verrou():
        registre = _lire()
        liberees = [c for c, e in registre.items() if e.get("execution") == dossier]
        if liberees:
            _ecrire({c: e for c, e in registre.items() if c not in liberees})
            logger.info(f"[reservations] libère {sorted(liberees)} (exécution close)")
        return sorted(liberees)


def cles_reservees(*, reconcilier_pid: bool = False) -> set[str]:
    """Clés actuellement tenues. `reconcilier_pid` (conteneur seulement) purge d'abord les fantômes."""
    with _Verrou():
        registre = _reconcilier(_lire(), tester_pid=reconcilier_pid)
        _ecrire(registre)
        return set(registre)


def actives(*, reconcilier_pid: bool = False) -> list[dict]:
    """Exécutions distinctes qui tiennent au moins une clé (une entrée par exécution, ses clés listées)."""
    with _Verrou():
        registre = _reconcilier(_lire(), tester_pid=reconcilier_pid)
        _ecrire(registre)
        par_exec: dict[str, dict] = {}
        for cle, e in registre.items():
            ref = par_exec.setdefault(
                e.get("execution", ""),
                {"execution": e.get("execution"), "exp": e.get("exp"), "cles": []},
            )
            ref["cles"].append(cle)
        for ref in par_exec.values():
            ref["cles"].sort()
        return sorted(
            par_exec.values(),
            key=lambda r: (r.get("exp") or "", r.get("execution") or ""),
        )


# ── File d'attente : admission et promotion (partagent le verrou du registre) ──


def admettre(
    cles: set[str],
    dossier_execution: str | Path,
    exp_nom: str,
    args: dict | None = None,
    pid: int | None = None,
) -> str:
    """Admission atomique d'un lancement (R2/R3/R6). Sous UN verrou :

    - clés disjointes des réservations en cours → **réserve** et renvoie ``"lance"`` ;
    - au moins une clé tenue par une autre expérience → **met en file** (FIFO, dédoublonnée par
      nom d'expérience) et renvoie ``"file"``.

    Appelée dans le conteneur (réconciliation par pid). Un jeu de clés vide passe toujours (R8)."""
    from experiences import file as F

    dossier = str(Path(dossier_execution))
    pid = int(pid if pid is not None else os.getpid())
    with _Verrou():
        registre = _reconcilier(_lire(), tester_pid=True)
        conflits = _conflits(registre, cles, dossier)
        if not conflits:
            _poser(registre, cles, dossier, exp_nom, pid)
            _ecrire(registre)
            if cles:
                logger.info(f"[reservations] {exp_nom} réserve {sorted(cles)}")
            return "lance"
        attente = [e for e in F.charger() if e.get("exp") != exp_nom]
        attente.append(F.entree(exp_nom, cles, args or {}))
        F.sauver(attente)
        retenues = sorted(f"{c}←{registre[c].get('exp', '?')}" for c in conflits)
        logger.info(
            f"[reservations] {exp_nom} en file — clé(s) tenue(s) : {', '.join(retenues)}"
        )
        return "file"


def lister_file() -> list[dict]:
    """Entrées en attente, ordre FIFO (lecture seule, pour affichage)."""
    from experiences import file as F

    with _Verrou():
        return F.charger()


def retirer_file(exp_nom: str) -> bool:
    """Retire une expérience de la file avant sa promotion (R2e). True si une entrée est retirée."""
    from experiences import file as F

    with _Verrou():
        avant = F.charger()
        apres = [e for e in avant if e.get("exp") != exp_nom]
        if len(apres) != len(avant):
            F.sauver(apres)
            logger.info(f"[reservations] {exp_nom} retirée de la file")
            return True
        return False


def promouvoir_pretes() -> list[dict]:
    """Sort de la file, en respectant le FIFO, les expériences dont TOUTES les clés sont libres
    (R2b) sans jamais choisir deux entrées aux clés qui se recouvrent dans le même tour. Ne réserve
    PAS : la relance de `lancer` réservera à son démarrage. Appelée côté hôte APRÈS une
    réconciliation en conteneur ; ne teste donc pas les pid.

    Renvoie les entrées à relancer, dans l'ordre. Une expérience active n'est jamais préemptée
    (R2c) : on ne fait que consommer des clés déjà libres."""
    from experiences import file as F

    with _Verrou():
        pris = set(_lire())
        choisies, restantes = [], []
        for e in F.charger():
            cles = set(e.get("cles") or [])
            if cles & pris:
                restantes.append(e)
            else:
                choisies.append(e)
                pris |= cles
        if choisies:
            F.sauver(restantes)
            for e in choisies:
                logger.info(
                    f"[reservations] promotion de {e.get('exp')} (clés {e.get('cles')})"
                )
        return choisies


__all__ = [
    "actives",
    "admettre",
    "cles_reservees",
    "liberer",
    "lister_file",
    "promouvoir_pretes",
    "reconcilier",
    "reserver",
    "retirer_file",
]
