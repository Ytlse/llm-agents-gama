import asyncio
import hashlib
import json
import threading
import time
import uuid
from datetime import datetime
from typing import Optional

from loguru import logger
from prometheus_client import Counter, Histogram

COLLECTION_NAME = "llm_decisions"
VECTOR_SIZE = 384

LLM_CACHE_HITS = Counter(
    "llm_cache_hits_total",
    "Nombre de requêtes servies depuis le cache LLM sémantique",
    ["activity_purpose"],
)
LLM_CACHE_MISSES = Counter(
    "llm_cache_misses_total",
    "Nombre de cache miss LLM",
    ["reason"],
)
LLM_CACHE_LOOKUP_SECONDS = Histogram(
    "llm_cache_lookup_seconds",
    "Latence totale de la recherche dans le cache LLM (embed + Qdrant)",
)
LLM_CACHE_EMBED_SECONDS = Histogram(
    "llm_cache_embed_seconds",
    "Latence de l'inférence sentence-transformer pour le cache LLM",
)
LLM_CACHE_INSERT_SECONDS = Histogram(
    "llm_cache_insert_seconds",
    "Latence d'écriture Qdrant locale pour le cache LLM",
)


class LlmSemanticCache:
    def __init__(self, cache_dir: str, semantic_threshold: float, embed_model_name: str):
        """Charge le modèle d'embedding et ouvre la base Qdrant locale dans cache_dir."""
        from qdrant_client import QdrantClient
        from sentence_transformers import SentenceTransformer

        self._threshold = semantic_threshold
        logger.info(f"Chargement du modèle d'embedding LLM cache : {embed_model_name}")
        self._model = SentenceTransformer(embed_model_name)
        self._embed_lock = threading.Lock()
        self._client = QdrantClient(path=cache_dir)
        self._ensure_collection()
        logger.info(f"LlmSemanticCache initialisé — répertoire: {cache_dir}, seuil: {semantic_threshold}")

    def _ensure_collection(self):
        """Crée la collection Qdrant si elle n'existe pas encore."""
        from qdrant_client.models import Distance, VectorParams

        existing = {c.name for c in self._client.get_collections().collections}
        if COLLECTION_NAME not in existing:
            self._client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )

    @staticmethod
    def _make_state_hash(options: list, weather: Optional[dict] = None) -> str:
        """Calcule un hash SHA-256 des codes d'options triés + météo pour identifier un contexte de décision."""
        codes = sorted(opt.get_code() for opt in options)
        weather_key = ""
        if weather:
            weather_key = f"{weather.get('weather_code','')}|{round(weather.get('temperature', 0))}|{round(weather.get('precip_mm', 0), 1)}"
        raw = json.dumps(codes, ensure_ascii=False) + weather_key
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _make_time_slice(timestamp: int) -> str:
        """Convertit un timestamp Unix en tranche de 10 minutes (ex: "08:40") pour regrouper les entrées de cache."""
        dt = datetime.fromtimestamp(timestamp)
        minutes = (dt.minute // 10) * 10
        return f"{dt.hour:02d}:{minutes:02d}"

    def _embed(self, text: str) -> list:
        """Encode le texte en vecteur via le sentence-transformer et enregistre la latence."""
        t0 = time.perf_counter()
        with self._embed_lock:
            vec = self._model.encode(text).tolist()
        LLM_CACHE_EMBED_SECONDS.observe(time.perf_counter() - t0)
        return vec

    def _lookup_sync(
        self,
        agent_id: str,
        activity_id: Optional[str],
        timestamp: int,
        options: list,
        memory_text: str,
        weather: Optional[dict],
    ) -> Optional[dict]:
        """Recherche synchrone dans Qdrant. Retourne (résultat, None) sur hit ou (None, raison) sur miss."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        state_hash = self._make_state_hash(options, weather)
        time_slice = self._make_time_slice(timestamp)

        filt = Filter(
            must=[
                FieldCondition(key="agent_id", match=MatchValue(value=str(agent_id))),
                FieldCondition(key="activity_id", match=MatchValue(value=str(activity_id or ""))),
                FieldCondition(key="time_slice", match=MatchValue(value=time_slice)),
                FieldCondition(key="state_hash", match=MatchValue(value=state_hash)),
            ]
        )

        # Recherche sans score_threshold pour distinguer no_candidates de below_threshold
        candidates = self._client.query_points(
            collection_name=COLLECTION_NAME,
            query=self._embed(memory_text),
            query_filter=filt,
            limit=1,
        ).points

        if not candidates:
            return None, "no_candidates"

        best = candidates[0]
        if best.score < self._threshold:
            return None, "below_threshold"

        payload = best.payload or {}
        return {
            "chosen_plan_code": payload.get("chosen_plan_code"),
            "mode": payload.get("mode", ""),
            "score": best.score,
        }, None

    def _store_sync(
        self,
        agent_id: str,
        activity_id: Optional[str],
        timestamp: int,
        options: list,
        memory_text: str,
        chosen_plan_code: str,
        mode: str,
        weather: Optional[dict],
    ):
        """Insère (upsert) un point Qdrant avec le vecteur du texte mémoire et les métadonnées de la décision."""
        from qdrant_client.models import PointStruct
        from datetime import datetime as _dt

        state_hash = self._make_state_hash(options, weather)
        time_slice = self._make_time_slice(timestamp)
        dt = _dt.fromtimestamp(timestamp)

        trajectories = [
            {"code": opt.get_code(), "mode": ",".join(str(l.mode) for l in opt.legs) if opt.legs else "", "duration_ms": opt.duration or 0}
            for opt in options
        ]

        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=self._embed(memory_text),
            payload={
                "agent_id": str(agent_id),
                "activity_id": str(activity_id or ""),
                "time_slice": time_slice,
                "state_hash": state_hash,
                "day": dt.day,
                "month": dt.month,
                "temperature": weather.get("temperature") if weather else None,
                "weather_code": weather.get("weather_code") if weather else None,
                "weather_label": weather.get("weather_label") if weather else None,
                "precip_mm": weather.get("precip_mm") if weather else None,
                "trajectories": trajectories,
                "chosen_plan_code": chosen_plan_code,
                "mode": mode,
                "stored_at": time.time(),
            },
        )
        self._client.upsert(collection_name=COLLECTION_NAME, points=[point])

    async def lookup(
        self,
        agent_id: str,
        activity_id: Optional[str],
        timestamp: int,
        options: list,
        memory_text: str,
        weather: Optional[dict] = None,
        activity_purpose: str = "",
    ) -> Optional[dict]:
        """
        Recherche dans le cache. Retourne un dict {index, mode, score} sur hit,
        None sur miss. L'index correspond à la position dans `options` tel que fourni.
        """
        t0 = time.perf_counter()
        try:
            result, miss_reason = await asyncio.to_thread(
                self._lookup_sync, agent_id, activity_id, timestamp, options, memory_text, weather
            )
        except Exception as e:
            logger.warning(f"LLM cache lookup error: {e}")
            LLM_CACHE_MISSES.labels(reason="lookup_error").inc()
            return None
        finally:
            LLM_CACHE_LOOKUP_SECONDS.observe(time.perf_counter() - t0)

        if result is None:
            LLM_CACHE_MISSES.labels(reason=miss_reason).inc()
            return None

        chosen_code = result.get("chosen_plan_code")
        if not chosen_code:
            LLM_CACHE_MISSES.labels(reason="no_candidates").inc()
            return None

        # Retrouve l'index du plan dans la liste courante (potentiellement mélangée)
        for i, opt in enumerate(options):
            if opt.get_code() == chosen_code:
                LLM_CACHE_HITS.labels(activity_purpose=activity_purpose).inc()
                return {"index": i, "mode": result["mode"], "score": result["score"]}

        # Le code était en cache mais n'existe plus dans les options courantes (itinéraire modifié)
        LLM_CACHE_MISSES.labels(reason="code_not_in_options").inc()
        return None

    async def store(
        self,
        agent_id: str,
        activity_id: Optional[str],
        timestamp: int,
        options: list,
        memory_text: str,
        chosen_plan_code: str,
        mode: str,
        weather: Optional[dict] = None,
    ):
        """Wrapper async de _store_sync : persiste la décision dans Qdrant et enregistre la latence d'écriture."""
        t0 = time.perf_counter()
        try:
            await asyncio.to_thread(
                self._store_sync,
                agent_id,
                activity_id,
                timestamp,
                options,
                memory_text,
                chosen_plan_code,
                mode,
                weather,
            )
        except Exception as e:
            logger.warning(f"LLM cache store error: {e}")
        finally:
            LLM_CACHE_INSERT_SECONDS.observe(time.perf_counter() - t0)
