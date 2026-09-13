"""Mémoïsation exacte des réflexions STM/LTM (ticket 012).

Un appel LLM de réflexion est une fonction pure de son prompt effectif : même
agent, même identité, même vécu, mêmes consignes ⇒ même introspection. Sur les
re-runs déterministes (décisions servies par le cache, tirages seedés, météo
rejouée), ces prompts sont byte-identiques d'un run à l'autre — les repayer est
un gaspillage de quota. Ce store les mémoïse par empreinte SHA-256 exacte.

Ce que ce store N'EST PAS : un cache par rapprochement. Aucune branche
sémantique, aucun seuil, aucune réutilisation entre agents ou entre vécus
différents — le moindre octet de différence est un miss. Servir à un agent
l'introspection d'un autre serait une dégradation scientifique (doctrine
« aucun mode dégradé », docs/arch/cache-memory.md).

Emplacement : `reflections.sqlite` dans le MÊME répertoire que le cache de
décisions (`<cache_dir>/<prompt_checksum>/<population>/`) — l'invalidation par
changement de prompt système est héritée du checksum de répertoire, comme pour
les décisions.

Le modèle ne fait PAS partie de la clé (amendement de D2, ticket 012) : la
cascade multi-providers route dynamiquement, le modèle n'est pas connu au
lookup. Le provider ayant réellement produit la réflexion est conservé dans la
VALEUR (audit). Rejouer la réflexion stockée est d'ailleurs plus déterministe
que re-demander au vivant, où la roulette des providers changerait la plume.

Concurrence : SQLite en WAL + verrou processus. Les méthodes sont synchrones —
les appeler via `asyncio.to_thread` depuis l'event loop (même convention que
`LlmSemanticCache`).
"""

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from prometheus_client import Counter

REFLECTION_MEMO = Counter(
    "agent_reflection_memo_total",
    "Mémoïsation des réflexions STM/LTM : hits, misses et stores, par catégorie",
    ["category", "event"],  # event ∈ hit | miss | store | store_refused
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reflections (
    key         TEXT PRIMARY KEY,
    person_id   TEXT NOT NULL,
    category    TEXT NOT NULL,
    reflection  TEXT NOT NULL,
    concepts    TEXT NOT NULL,   -- JSON (liste), '[]' si aucune
    provider    TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_reflections_person ON reflections(person_id);
"""


class ReflectionMemoStore:
    """Store de mémoïsation exacte des réflexions (clé = SHA-256 du prompt effectif)."""

    def __init__(self, cache_dir: str):
        path = Path(cache_dir)
        path.mkdir(parents=True, exist_ok=True)
        self._db_path = str(path / "reflections.sqlite")
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
        logger.info(f"ReflectionMemoStore initialisé — {self._db_path}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # ------------------------------------------------------------------ clé

    @staticmethod
    def make_key(
        person_id: str,
        category: str,
        identity: str,
        context_text: str,
        guidelines: str = "",
        departure_timestamp: float = 0.0,
        llm_params: Optional[dict] = None,
    ) -> str:
        """Empreinte exacte du prompt effectif de réflexion.

        Tout ce qui atteint le LLM entre dans la clé : identité, vécu, consignes,
        horodatage de départ (interpolé dans le rendu — déterministe en re-run) et
        paramètres de génération (la température change la plume). La version du
        prompt système n'y figure pas : elle isole déjà le RÉPERTOIRE du store
        (checksum, cf. llm_agent.py).
        """
        material = json.dumps(
            {
                "person_id": str(person_id),
                "category": category,
                "identity": identity,
                "context": context_text,
                "guidelines": guidelines,
                "departure_timestamp": departure_timestamp,
                "llm_params": llm_params or {},
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    # -------------------------------------------------------------- lecture

    def lookup(self, key: str, category: str) -> Optional[dict]:
        """Retourne {reflection, concepts, provider} si le prompt exact a déjà été payé."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT reflection, concepts, provider FROM reflections WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            REFLECTION_MEMO.labels(category=category, event="miss").inc()
            return None
        REFLECTION_MEMO.labels(category=category, event="hit").inc()
        return {
            "reflection": row[0],
            "concepts": json.loads(row[1]),
            "provider": row[2],
        }

    # -------------------------------------------------------------- écriture

    def store(
        self,
        key: str,
        person_id: str,
        category: str,
        reflection: str,
        concepts: Optional[list] = None,
        provider: str = "",
    ) -> bool:
        """Persiste une réflexion réellement produite. Refuse le vide (D3).

        Une réflexion vide ET sans concept est un échec de génération, pas une
        introspection : la persister servirait du néant aux re-runs (même principe
        que le refus des replis uniformes dans le cache de décisions).
        """
        reflection = (reflection or "").strip()
        concepts = concepts or []
        if not reflection and not concepts:
            REFLECTION_MEMO.labels(category=category, event="store_refused").inc()
            logger.info(
                f"[reflection-memo] store refusé — réflexion vide non persistée | "
                f"person={person_id} category={category}"
            )
            return False
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO reflections "
                "(key, person_id, category, reflection, concepts, provider) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (key, str(person_id), category, reflection,
                 json.dumps(concepts, ensure_ascii=False), provider),
            )
            conn.commit()
        REFLECTION_MEMO.labels(category=category, event="store").inc()
        return True

    # ------------------------------------------------------------ diagnostic

    def stats(self) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM reflections").fetchone()[0]
            by_cat = dict(conn.execute(
                "SELECT category, COUNT(*) FROM reflections GROUP BY category"
            ).fetchall())
        return {"total": total, "by_category": by_cat}
