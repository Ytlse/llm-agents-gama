"""Purge du cache LLM : retire les distributions de repli uniforme persistées.

Contexte (2026-08-03) : avant le correctif `UniformFallback`, un vecteur de
probabilités inexploitable (troncature provider → somme nulle) était remplacé
par une distribution uniforme PUIS écrite dans le cache Qdrant comme une
décision légitime. Tout run ultérieur touchant ces clés tirait son mode au
hasard. Ce script retire ces points.

Ciblage : les couples (agent, activity) sont lus depuis les alarmes
`[ALARME] Vecteur de probabilités inexploitable` d'un app.log (--from-log),
ou depuis un fichier de lignes `agent=<id> activity=<id>` (--pairs-file).
Un point n'est supprimé que si sa distribution est EFFECTIVEMENT uniforme
(tous les p égaux, à 1e-9 près) : les entrées légitimes du même couple
(autre créneau, autre météo) sont épargnées.

ATTENTION : Qdrant embarqué est mono-processus — arrêter le controller
(`make down` ou `docker compose stop controller`) avant de lancer ce script.

Usage :
    llm-agents/.venv/bin/python scripts/cache/purge_uniform_fallback.py \
        --cache-dir data/cache/llm/<hash>/<population> \
        --from-log experiments/archive/<run>/app.log \
        [--apply]          # sans --apply : dry-run (liste sans supprimer)
    # --scan-all : audite TOUTE la collection et liste les points uniformes
    #              (héritage d'anciens runs), sans ciblage par couple.
"""

import argparse
import re
import sys
from pathlib import Path

COLLECTION = "llm_decisions"
ALARM_RE = re.compile(r"Vecteur de probabilités inexploitable.*agent=(\S+) activity=(\S+)")
EPS = 1e-9


def is_uniform(probabilities: list) -> bool:
    ps = [float(entry.get("p", 0.0)) for entry in (probabilities or [])]
    if len(ps) < 2 or any(p <= 0 for p in ps):
        return False
    return max(ps) - min(ps) < EPS


def pairs_from_log(path: Path) -> set[tuple[str, str]]:
    pairs = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = ALARM_RE.search(line)
        if m:
            pairs.add((m.group(1), m.group(2)))
    return pairs


def pairs_from_file(path: Path) -> set[tuple[str, str]]:
    pairs = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.search(r"agent=(\S+) activity=(\S+)", line)
        if m:
            pairs.add((m.group(1), m.group(2)))
    return pairs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cache-dir", required=True, help="Répertoire Qdrant local (contient meta.json)")
    ap.add_argument("--from-log", type=Path, help="app.log à parser pour les alarmes somme nulle")
    ap.add_argument("--pairs-file", type=Path, help="Fichier de lignes 'agent=<id> activity=<id>'")
    ap.add_argument("--scan-all", action="store_true", help="Auditer toute la collection (rapport)")
    ap.add_argument("--apply", action="store_true", help="Supprimer réellement (défaut : dry-run)")
    args = ap.parse_args()

    from qdrant_client import QdrantClient
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    pairs: set[tuple[str, str]] = set()
    if args.from_log:
        pairs |= pairs_from_log(args.from_log)
    if args.pairs_file:
        pairs |= pairs_from_file(args.pairs_file)
    if not pairs and not args.scan_all:
        print("Aucun couple agent/activity fourni (--from-log / --pairs-file) et pas de --scan-all.")
        return 2

    client = QdrantClient(path=args.cache_dir)
    to_delete: list[str] = []

    def scan(flt):
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=COLLECTION, scroll_filter=flt,
                with_payload=True, with_vectors=False, limit=256, offset=offset,
            )
            for pt in points:
                payload = pt.payload or {}
                if is_uniform(payload.get("probabilities")):
                    to_delete.append(pt.id)
                    print(f"  uniforme → id={pt.id} agent={payload.get('agent_id')} "
                          f"activity={payload.get('activity_id')} slice={payload.get('time_slice')} "
                          f"weekday={payload.get('weekday')}")
            if offset is None:
                break

    if args.scan_all:
        print("Audit complet de la collection…")
        scan(None)
    else:
        print(f"{len(pairs)} couple(s) agent/activity ciblé(s)")
        for agent_id, activity_id in sorted(pairs):
            scan(Filter(must=[
                FieldCondition(key="agent_id", match=MatchValue(value=str(agent_id))),
                FieldCondition(key="activity_id", match=MatchValue(value=str(activity_id))),
            ]))

    if not to_delete:
        print("Aucun point uniforme trouvé — rien à purger.")
        return 0

    if args.apply:
        client.delete(collection_name=COLLECTION, points_selector=to_delete)
        print(f"✅ {len(to_delete)} point(s) supprimé(s) de {COLLECTION}.")
    else:
        print(f"DRY-RUN : {len(to_delete)} point(s) seraient supprimés — relancer avec --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
