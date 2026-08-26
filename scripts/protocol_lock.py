"""protocol_lock.py — Jeton d'exclusion des procédures du protocole exogène (ticket 023).

Garantit qu'**aucun run de simulation ne tourne** pendant qu'une procédure de
`docs/arch/protocole-parametre-exogene.md` s'exécute, et laisse dans l'archive la preuve
qu'aucune consommation concurrente n'a eu lieu.

## Pourquoi c'est de la méthode et pas de l'hygiène

Le protocole constate lui-même qu'un Δ placebo de même signe que le Δ traité « signale une
dérive systématique ENTRE BRAS et non du bruit pur ». **Un run concurrent en est une cause
directe** : il consomme le même quota LLM, et si la cascade de fournisseurs bascule entre le
premier et le second bras, les deux bras n'ont pas été évalués par le même modèle. Ce n'est
pas du bruit — c'est un facteur confondu avec le traitement, invisible dans les agrégats.

Deux autres ressources partagées cassent de la même façon :

| Ressource | Ce qui casse |
|---|---|
| Store content-addressed | deux procédures écrivant sous la même clé `ds=` |
| Lien `experiments/current` | `make run` le repointe ; une archive en cours archiverait le mauvais run |

## ⚠ Ce que ce jeton NE couvre PAS

**La campagne génétique de la VM Google Cloud.** Elle tourne en autonomie, avec son propre
quota et son propre déclenchement hebdomadaire ; un fichier de verrou sur ce poste ne
l'atteint pas. C'est pourquoi la prise exige `--cloud-paused` : une liste de contrôle
explicite, la réponse la plus honnête et la moins coûteuse (axe D4 du ticket 023). Les
instantanés de quota pris à l'acquisition et au relâchement forment le second filet : ils
**détectent** après coup une consommation concurrente qu'on n'a pas su bloquer, donc
permettent de savoir si une mesure est à jeter. Un filet, pas un verrou — et c'est écrit
dans la sortie de `status`, pas seulement dans le ticket.

## Le PID enregistré est celui de la SESSION, pas du processus

`make protocol-lock` se termine immédiatement : son PID serait mort à la seconde suivante et
tout jeton paraîtrait orphelin. On enregistre donc `os.getsid(0)`, le meneur de session —
c'est-à-dire le shell interactif — qui vit aussi longtemps que le terminal depuis lequel la
procédure est conduite. Fermer ce terminal rend le jeton orphelin, ce qui est exactement le
sens voulu.

Usage :
    make protocol-status
    make protocol-lock SUBJECT="ticket 023 — A/B fenêtre météo" CLOUD_PAUSED=1
    make protocol-unlock
"""

from __future__ import annotations

import sys
from pathlib import Path

# ⚠ À FAIRE AVANT TOUT AUTRE IMPORT. `scripts/warnings.py` porte le nom d'un module
# standard, et Python place le répertoire du script en tête de `sys.path` : le `import
# warnings` que fait `subprocess` tomberait sur lui, et l'échec est indéchiffrable — une
# `FileNotFoundError` portant le nom de la sous-commande passée en ligne de commande. On
# retire donc `scripts/` du path avant d'importer quoi que ce soit d'autre. `sys` et
# `pathlib` sont sûrs : ni l'un ni l'autre n'importe `warnings`.
_HERE = Path(__file__).resolve().parent
if sys.path and Path(sys.path[0] or ".").resolve() == _HERE:
    sys.path.pop(0)

import argparse  # noqa: E402
import getpass  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import socket  # noqa: E402
import subprocess  # noqa: E402
from datetime import datetime, timezone  # noqa: E402


def _load_live():
    """Charge `dashboard/live.py` par CHEMIN, sans toucher à `sys.path`.

    ⚠ `scripts/warnings.py` porte le nom d'un module standard. Ajouter `scripts/` au
    `sys.path` le fait masquer le vrai `warnings`, que `subprocess` importe — et l'import
    échoue avec une trace incompréhensible (`FileNotFoundError` sur l'argument de la CLI).
    Le chargement par chemin évite le problème à la racine plutôt que de dépendre de
    l'ordre des imports.
    """
    path = Path(__file__).resolve().parent / "dashboard" / "live.py"
    spec = importlib.util.spec_from_file_location("_protocol_lock_live", path)
    module = importlib.util.module_from_spec(spec)
    # `@dataclass` remonte à `sys.modules[cls.__module__]` pour résoudre ses annotations :
    # un module exécuté sans y être inscrit lève un `AttributeError` sur `None`.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


live = _load_live()

ROOT = Path(__file__).resolve().parents[1]
# `experiments/` est déjà gitignoré : le jeton est un état de poste, pas du dépôt.
# PROTOCOL_LOCK_FILE : jeton NOMMÉ pour une campagne dont le quota ne recouvre pas
# celui du jeton par défaut (ex. deux juges épinglés sur des modèles différents —
# les compteurs free tier sont par modèle ET par projet). Deux campagnes ne partagent
# un jeton que si elles partagent un compteur ; sinon chacune prend le sien.
LOCK_PATH = (Path(os.environ["PROTOCOL_LOCK_FILE"]).resolve()
             if os.environ.get("PROTOCOL_LOCK_FILE")
             else ROOT / "experiments" / "protocol_lock.json")

# Services dont la présence signifie qu'un pipeline de décisions peut consommer du quota.
# `api` n'y figure PAS : c'est lui qui sert `/health`, donc les instantanés de quota.
BLOCKING_SERVICES = ("controller", "worker")

CLOUD_LIMITATION = (
    "⚠ Ce jeton est LOCAL. Il ne bloque pas la campagne génétique de la VM Google Cloud, "
    "qui a son propre quota et son propre déclenchement hebdomadaire. Les instantanés de "
    "quota ci-dessous la DÉTECTENT après coup, ils ne la préviennent pas."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _pid_alive(pid: int) -> bool:
    """Le processus existe-t-il encore ? `signal 0` ne fait que tester."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True          # il existe, il ne nous appartient pas
    return True


def quota_snapshot() -> dict:
    """Instantané des quotas par fournisseur, via `live.api_health()`.

    Une API injoignable n'est PAS une erreur — la pile peut être arrêtée, c'est même
    l'état attendu pendant une procédure. On enregistre l'indisponibilité telle quelle :
    un instantané absent qui se dit absent vaut mieux qu'un zéro qui ressemble à une
    mesure. C'est le motif « vacuité ≠ perfection » du dépôt.
    """
    health = live.api_health()
    if not health.available:
        return {"at": _now(), "available": False, "error": health.error}
    return {
        "at": _now(), "available": True,
        "providers": {
            p.name: {"daily_requests": p.daily_requests, "rpd_limit": p.rpd_limit,
                     "daily_tokens": p.daily_tokens, "tpd_limit": p.tpd_limit,
                     "quota_exhausted": p.quota_exhausted, "available": p.available}
            for p in health.providers},
    }


def all_running_services() -> list[str] | None:
    """Tous les services `docker compose` en marche. `None` si la sonde est muette.

    `None` et liste vide ne veulent pas dire la même chose : l'un est « je ne sais pas »,
    l'autre « rien ne tourne ». Les confondre ferait passer une sonde cassée pour une
    preuve d'exclusion — le motif « vacuité ≠ perfection » du dépôt.
    """
    try:
        proc = subprocess.run(  # noqa: S603 — argv fixe
            ["docker", "compose", "ps", "--services", "--status", "running"],
            capture_output=True, text=True, timeout=20, cwd=ROOT)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return sorted(s.strip() for s in proc.stdout.splitlines() if s.strip())


def running_services() -> list[str]:
    """Services **bloquants** actuellement en marche.

    Complète `live.run_process()` : un run peut être arrêté côté GAMA alors que le
    controller et le worker continuent de drainer une file de décisions.
    """
    up = all_running_services()
    if up is None:
        return []            # docker absent : on ne fabrique pas un refus sur une sonde muette
    return [s for s in BLOCKING_SERVICES if s in up]


def stack_snapshot() -> dict:
    """État de la pile — la **seconde** preuve, et parfois la seule qui vaille.

    Les instantanés de quota détectent une consommation concurrente ; ils exigent que
    l'API tourne. Or le cas où l'exclusion est la MEILLEURE — pile entièrement arrêtée —
    est précisément celui où l'API ne répond pas, donc où les quotas manquent. Sans cette
    seconde sonde, l'archive serait la plus pauvre là où la mesure est la plus propre.

    « Aucun service en marche » est une preuve d'exclusion plus directe que deux compteurs
    de quota inchangés : rien ne pouvait consommer.
    """
    up = all_running_services()
    return {
        "at": _now(),
        "probe_available": up is not None,
        "running": up,
        "blocking_running": [s for s in BLOCKING_SERVICES if s in (up or [])],
        "stack_fully_down": up == [],
    }


def read_lock() -> dict | None:
    """Jeton courant, ou `None`. Un fichier illisible est traité comme un jeton présent
    et cassé — jamais comme une absence, qui autoriserait une seconde prise."""
    if not LOCK_PATH.exists():
        return None
    try:
        return json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"_illisible": str(exc), "pid": -1, "subject": "(fichier de jeton corrompu)"}


def is_orphan(lock: dict) -> bool:
    pid = int(lock.get("pid") or -1)
    return pid <= 0 or not _pid_alive(pid)


def describe(lock: dict) -> str:
    age = ""
    try:
        delta = datetime.now(timezone.utc) - datetime.fromisoformat(lock["acquired_at"])
        age = f", depuis {int(delta.total_seconds() // 60)} min"
    except (KeyError, ValueError):
        pass
    return (f"« {lock.get('subject', '?')} » — {lock.get('user', '?')}@"
            f"{lock.get('host', '?')}, PID de session {lock.get('pid', '?')}{age}")


# ── Commandes ────────────────────────────────────────────────────────────────


def cmd_acquire(args: argparse.Namespace) -> int:
    print(f"[protocol-lock] prise demandée — sujet « {args.subject} »")

    existing = read_lock()
    if existing is not None:
        if not is_orphan(existing):
            print(f"[REFUS] jeton déjà détenu : {describe(existing)}", file=sys.stderr)
            print("        Attendez sa libération, ou `make protocol-unlock` si c'est le "
                  "vôtre.", file=sys.stderr)
            return 2
        print(f"[ALARME] jeton ORPHELIN détecté : {describe(existing)}")
        print("         Son processus de session n'existe plus — terminal fermé, ou "
              "procédure interrompue.")
        if not args.steal_orphan:
            print("[REFUS] un jeton orphelin n'est JAMAIS levé automatiquement : une "
                  "procédure peut encore tourner sous un autre shell.", file=sys.stderr)
            print("        Vérifiez, puis reprenez-le explicitement : "
                  "`make protocol-lock SUBJECT=… STEAL=1`", file=sys.stderr)
            return 3
        print("         Reprise explicite demandée (--steal-orphan) — l'ancien jeton est "
              "remplacé.")

    if not args.cloud_paused:
        print("[REFUS] liste de contrôle incomplète : la campagne génétique de la VM "
              "cloud est-elle en pause ?", file=sys.stderr)
        print("        Ce verrou est LOCAL et ne l'atteint pas. Confirmez avec "
              "`CLOUD_PAUSED=1`, après l'avoir vérifié.", file=sys.stderr)
        return 4

    run = live.run_process()
    if run.active:
        print(f"[REFUS] un run de simulation tourne ({run.mode}, PID {run.pid}) — il "
              f"consomme le même quota LLM.", file=sys.stderr)
        print("        Arrêtez-le (`make stop-run`) avant de prendre le jeton.",
              file=sys.stderr)
        return 5

    services = running_services()
    if services:
        print(f"[REFUS] services de pipeline en marche : {', '.join(services)}. Ils "
              f"peuvent drainer une file de décisions même sans GAMA.", file=sys.stderr)
        print(f"        `docker compose stop {' '.join(services)}` avant la prise.",
              file=sys.stderr)
        return 6

    lock = {
        "subject": args.subject,
        "host": socket.gethostname(),
        "user": getpass.getuser(),
        "pid": os.getsid(0),               # meneur de session, cf. l'en-tête du module
        "created_by_pid": os.getpid(),
        "acquired_at": _now(),
        "expected_duration_minutes": args.expected_minutes,
        "cloud_campaign_paused_confirmed": True,
        "quota_at_acquire": quota_snapshot(),
        "quota_at_release": None,
        "stack_at_acquire": stack_snapshot(),
        "stack_at_release": None,
        "limitation": CLOUD_LIMITATION,
    }
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    snap = lock["quota_at_acquire"]
    print(f"[protocol-lock] PRIS — {describe(lock)}")
    print(f"                durée annoncée : {args.expected_minutes} min")
    print(f"                instantané de quota : "
          + (f"{len(snap.get('providers', {}))} fournisseurs relevés"
             if snap["available"] else f"INDISPONIBLE ({snap.get('error')})"))
    stack = lock["stack_at_acquire"]
    if stack["stack_fully_down"]:
        print("                état de la pile : AUCUN service en marche — rien ne peut "
              "consommer. C'est la preuve d'exclusion la plus forte.")
    elif stack["probe_available"]:
        print(f"                état de la pile : {len(stack['running'])} service(s) en "
              f"marche, aucun bloquant — {', '.join(stack['running'])}")
    else:
        print("                état de la pile : INCONNU (docker muet). Ni les quotas ni "
              "les services ne prouvent l'exclusion pour cette mesure.")
    print(f"                fichier : {LOCK_PATH}")
    print(CLOUD_LIMITATION)
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    lock = read_lock()
    if lock is None:
        print("[protocol-lock] aucun jeton à relâcher — rien à faire.")
        return 0                      # idempotent : relâcher deux fois n'est pas une erreur

    mine = lock.get("pid") == os.getsid(0)
    if not mine and not args.force:
        print(f"[REFUS] ce jeton n'est pas celui de votre session : {describe(lock)}",
              file=sys.stderr)
        print("        `make protocol-unlock FORCE=1` si vous savez ce que vous faites.",
              file=sys.stderr)
        return 2

    lock["quota_at_release"] = quota_snapshot()
    lock["stack_at_release"] = stack_snapshot()
    lock["released_at"] = _now()
    # L'archive suit le NOM du jeton : deux jetons nommés ne s'écrasent pas l'un
    # l'autre au relâchement (protocol_lock.json → protocol_lock_last.json,
    # protocol_lock_35.json → protocol_lock_35_last.json).
    archive = LOCK_PATH.with_name(LOCK_PATH.stem + "_last.json")
    archive.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    LOCK_PATH.unlink()
    print(f"[protocol-lock] RELÂCHÉ — {describe(lock)}")
    _report_consumption(lock)
    print(f"                instantanés conservés → {archive}")
    print("                Ils entrent dans l'archive de la mesure : c'est la preuve "
          "qu'aucun run concurrent n'a tourné.")
    return 0


def _report_consumption(lock: dict) -> None:
    """Compare les deux instantanés. Une consommation entre prise et relâchement que la
    procédure n'explique pas est le signe d'un run concurrent — le filet du § cloud."""
    before, after = lock.get("quota_at_acquire") or {}, lock.get("quota_at_release") or {}
    s_before = lock.get("stack_at_acquire") or {}
    s_after = lock.get("stack_at_release") or {}
    if s_before.get("stack_fully_down") and s_after.get("stack_fully_down"):
        print("                état de la pile : aucun service en marche à la prise NI au "
              "relâchement.")
        print("                C'est la preuve d'exclusion : rien du côté local ne pouvait "
              "consommer. Reste la VM cloud, couverte par la liste de contrôle seule.")
    elif s_after.get("blocking_running"):
        print(f"[ALARME] services bloquants démarrés PENDANT la procédure : "
              f"{', '.join(s_after['blocking_running'])}. La mesure est suspecte.")

    if not (before.get("available") and after.get("available")):
        if not (s_before.get("stack_fully_down") and s_after.get("stack_fully_down")):
            print("[ALARME] instantanés de quota incomplets et pile non arrêtée : la "
                  "consommation concurrente ne peut pas être écartée pour cette mesure.")
        return
    moved = []
    for name, a in (before.get("providers") or {}).items():
        b = (after.get("providers") or {}).get(name)
        if not b:
            continue
        d_req = b["daily_requests"] - a["daily_requests"]
        d_tok = b["daily_tokens"] - a["daily_tokens"]
        if d_req or d_tok:
            moved.append(f"{name} +{d_req} req / +{d_tok} tok")
    if moved:
        print(f"                consommation observée : {' · '.join(moved)}")
        print("                À rapprocher du nombre d'appels de la procédure. Un écart "
              "inexpliqué = mesure suspecte.")
    else:
        print("                consommation observée : aucune (quotas identiques).")


def cmd_status(args: argparse.Namespace) -> int:
    lock = read_lock()
    run = live.run_process()
    services = running_services()

    print("═══ Jeton du protocole ═══")
    if lock is None:
        print("  LIBRE — aucune procédure en cours.")
    elif is_orphan(lock):
        print(f"  [ALARME] ORPHELIN — {describe(lock)}")
        print("           Le processus de session n'existe plus. Il n'est PAS levé "
              "automatiquement : vérifiez qu'aucune procédure ne tourne ailleurs, puis "
              "`make protocol-lock SUBJECT=… STEAL=1`.")
    else:
        print(f"  DÉTENU — {describe(lock)}")
        print(f"           durée annoncée : {lock.get('expected_duration_minutes', '?')} min")

    print("\n═══ Ce qui empêcherait une prise ═══")
    print(f"  run de simulation : "
          + (f"ACTIF ({run.mode}, PID {run.pid})" if run.active else "aucun"))
    print(f"  services pipeline : " + (", ".join(services) if services else "aucun"))
    stack = stack_snapshot()
    if stack["stack_fully_down"]:
        print("  état de la pile   : entièrement arrêtée — exclusion maximale")
    elif stack["probe_available"]:
        print(f"  état de la pile   : {len(stack['running'])} service(s) en marche")
    else:
        print("  état de la pile   : INCONNU (docker muet)")

    print(f"\n{CLOUD_LIMITATION}")
    if args.json:
        print("\n" + json.dumps(
            {"lock": lock, "orphan": bool(lock and is_orphan(lock)),
             "run_active": run.active, "blocking_services": services},
            ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    acq = sub.add_parser("acquire", help="prendre le jeton")
    acq.add_argument("--subject", required=True,
                     help="ce que la procédure fait — un jeton anonyme ne se débloque pas "
                          "sans risque")
    acq.add_argument("--expected-minutes", type=int, default=60)
    acq.add_argument("--cloud-paused", action="store_true",
                     help="confirme que la campagne génétique cloud est en pause "
                          "(liste de contrôle obligatoire : ce verrou ne l'atteint pas)")
    acq.add_argument("--steal-orphan", action="store_true",
                     help="reprendre explicitement un jeton orphelin")
    acq.set_defaults(func=cmd_acquire)

    rel = sub.add_parser("release", help="relâcher le jeton (idempotent)")
    rel.add_argument("--force", action="store_true",
                     help="relâcher un jeton qui n'est pas celui de cette session")
    rel.set_defaults(func=cmd_release)

    sta = sub.add_parser("status", help="état du jeton et des sondes")
    sta.add_argument("--json", action="store_true")
    sta.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
