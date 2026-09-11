#!/usr/bin/env python3
"""Fusionne un cache SQLite de routes OSMnx dans un autre, sans rien écraser.

Pourquoi ce script existe. Du 2026-06-02 au 2026-09-04, le runtime a écrit son cache de
routes dans ``llm-agents/data/osmnx_cache/<population>/`` — un chemin qui n'était monté
sur aucun volume — tandis que le peupleur en masse écrivait dans
``data/cache/osmnx/<population>/``. Aligner les deux chemins (défaut de
``gtfs.osmnx_persistent_cache_dir``) laisserait les routes déjà calculées par le runtime
dans le fichier orphelin : ce script les rapatrie.

Le transfert est ``INSERT OR IGNORE`` : une clé déjà présente dans la cible est conservée
telle quelle, jamais remplacée. Le script est donc idempotent et rejouable — utile parce
qu'un run en cours peut continuer d'écrire dans la source jusqu'à sa fin.

Les lignes portent la version de routage dans leur clé (``routing_version``,
``config/terminal_time.yaml``). Une ligne d'une version révolue n'est jamais resservie ;
elle est transférée quand même, parce qu'elle reste lisible pour un audit et ne coûte que
de la place.

Usage :
    python3 scripts/data/population/merge_osmnx_route_cache.py \\
        llm-agents/data/osmnx_cache/toulouse_population_1000 \\
        data/cache/osmnx/toulouse_population_1000
    # --dry-run pour compter sans écrire
"""

import argparse
import sqlite3
import sys
import time
from pathlib import Path

DB_NAME = "osmnx_cache.db"
COLUMNS = (
    "key, date, day_of_week, time_bucket, mode, "
    "lat_from, lon_from, lat_to, lon_to, result_json, stored_at"
)


def _resolve(arg: str) -> Path:
    """Accepte le répertoire de population ou le fichier .db directement."""
    p = Path(arg)
    return p if p.suffix == ".db" else p / DB_NAME


def _open_readonly(db: Path) -> tuple:
    """Ouvre la source en lecture seule. Retourne (connexion, mode retenu).

    `mode=ro` est préféré : il lit le journal WAL, donc les lignes qu'un run vient
    d'écrire. Il exige de pouvoir créer le fichier -shm à côté de la base ; à défaut
    (répertoire non inscriptible), on retombe sur `immutable=1`, qui ouvre le fichier
    principal SEUL — les lignes du WAL manquent alors, et l'appelant doit le dire.
    """
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        conn.execute("SELECT count(*) FROM osmnx_cache").fetchone()
        return conn, "ro"
    except sqlite3.Error:
        return sqlite3.connect(f"file:{db}?immutable=1", uri=True), "immutable"


def _counts_by_mode(conn: sqlite3.Connection) -> dict:
    return dict(conn.execute("SELECT mode, count(*) FROM osmnx_cache GROUP BY mode"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", help="répertoire de population OU fichier .db source")
    ap.add_argument("target", help="répertoire de population OU fichier .db cible")
    ap.add_argument("--dry-run", action="store_true", help="compter sans écrire")
    args = ap.parse_args()

    src, dst = _resolve(args.source), _resolve(args.target)
    if not src.exists():
        print(f"[ERREUR] Source absente : {src}", file=sys.stderr)
        return 1
    if src.resolve() == dst.resolve():
        print(f"[ERREUR] Source et cible sont le même fichier : {src}", file=sys.stderr)
        return 1

    t0 = time.monotonic()
    src_conn, src_mode = _open_readonly(src)
    if src_mode == "immutable":
        print("[ATTENTION] Source ouverte en `immutable` : les lignes encore dans le journal "
              "WAL ne sont PAS lues. Rejouer la fusion après l'arrêt du run qui l'écrit.")
    n_src = src_conn.execute("SELECT count(*) FROM osmnx_cache").fetchone()[0]
    print(f"Source : {src}")
    print(f"  {n_src} routes — {_counts_by_mode(src_conn)}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    existed = dst.exists()
    dst_conn = sqlite3.connect(str(dst))
    dst_conn.execute("PRAGMA journal_mode=WAL")
    # Cible neuve : on recopie le schéma de la SOURCE (table + index) plutôt que d'importer
    # `OsmnxPersistentCache`, qui tirerait toute la chaîne pydantic du runtime pour un
    # script d'exploitation. Le DDL recopié est celui qui a produit la source : une seule
    # définition, pas une seconde à maintenir ici.
    for (ddl,) in src_conn.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL"
    ).fetchall():
        dst_conn.execute(ddl.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1)
                            .replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1))
    dst_conn.commit()
    n_dst_before = dst_conn.execute("SELECT count(*) FROM osmnx_cache").fetchone()[0]
    print(f"Cible  : {dst} ({'existante' if existed else 'CRÉÉE'})")
    print(f"  {n_dst_before} routes avant — {_counts_by_mode(dst_conn)}")

    if args.dry_run:
        keys = {r[0] for r in src_conn.execute("SELECT key FROM osmnx_cache")}
        have = {r[0] for r in dst_conn.execute("SELECT key FROM osmnx_cache")}
        print(f"\n[DRY-RUN] {len(keys - have)} routes seraient ajoutées, "
              f"{len(keys & have)} déjà présentes — rien n'a été écrit.")
        return 0

    rows = src_conn.execute(f"SELECT {COLUMNS} FROM osmnx_cache").fetchall()
    placeholders = ",".join("?" * len(COLUMNS.split(",")))
    dst_conn.executemany(
        f"INSERT OR IGNORE INTO osmnx_cache ({COLUMNS}) VALUES ({placeholders})", rows
    )
    dst_conn.commit()

    n_dst_after = dst_conn.execute("SELECT count(*) FROM osmnx_cache").fetchone()[0]
    added = n_dst_after - n_dst_before
    elapsed = time.monotonic() - t0
    print(f"\nFusion terminée en {elapsed:.1f}s")
    print(f"  {added} routes ajoutées, {n_src - added} déjà présentes (ignorées)")
    print(f"  Cible : {n_dst_after} routes — {_counts_by_mode(dst_conn)}")
    if added == 0 and n_src > 0:
        print("  [ATTENTION] Aucune route ajoutée : la cible les contenait déjà toutes.")
    src_conn.close()
    dst_conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
