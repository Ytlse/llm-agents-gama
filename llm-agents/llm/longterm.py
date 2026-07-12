# scalable_memory.py - Scalable long-term memory system optimized for 1000+ users
import asyncio
import json
import time
from datetime import datetime, timedelta
import string
from typing import List, Dict, Optional, Any
from pathlib import Path
import hashlib
from dataclasses import dataclass
from settings import settings

from loguru import logger
import numpy as np
from prometheus_client import Histogram

LTM_QUERY_DURATION = Histogram(
    'ltm_query_duration_seconds',
    'Durée des appels aquery_user_memories (ChromaDB)',
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10],
)

@dataclass
class MemorySearchResult:
    content: str
    metadata: dict
    score: float = 0.0

from llama_index.core import (
    VectorStoreIndex, 
    Document, 
    StorageContext,
    load_index_from_storage,
    Settings
)
from llama_index.core.vector_stores.types import BasePydanticVectorStore

from llm.memory import MemoryEntry

class VectorStoreFactory:
    """Factory for creating optimized vector stores"""
    
    @staticmethod
    def create_chroma_store(storage_dir: Path) -> Optional[BasePydanticVectorStore]:
        """Create ChromaDB vector store with optimizations"""
        try:
            import chromadb
            from llama_index.vector_stores.chroma import ChromaVectorStore
            
            chroma_client = chromadb.PersistentClient(
                path=str(storage_dir / "chroma_db"),
            )
            
            chroma_collection = chroma_client.get_or_create_collection(
                "memory_collection",
                metadata={"hnsw:space": "cosine"}
            )
            
            return ChromaVectorStore(chroma_collection=chroma_collection)
            
        except ImportError:
            logger.warning("ChromaDB not available, falling back to simple storage")
            return None
    
    # @staticmethod
    # def create_qdrant_store(storage_dir: Path) -> Optional[BasePydanticVectorStore]:
    #     """Create Qdrant vector store with optimizations"""
    #     try:
    #         import qdrant_client
    #         from llama_index.vector_stores.qdrant import QdrantVectorStore
            
    #         client = qdrant_client.QdrantClient(
    #             path=str(storage_dir / "qdrant_db"),
    #             grpc_port=6334,
    #             prefer_grpc=True
    #         )
            
    #         return QdrantVectorStore(
    #             client=client,
    #             collection_name="memory_collection",
    #             parallel=4
    #         )
            
    #     except ImportError:
    #         print("Qdrant not available, falling back to simple storage")
    #         return None
    
    # @staticmethod
    # def create_pinecone_store(config: Dict[str, Any]) -> Optional[BasePydanticVectorStore]:
    #     """Create Pinecone vector store"""
    #     try:
    #         import pinecone
    #         from llama_index.vector_stores.pinecone import PineconeVectorStore
            
    #         api_key = config.get("api_key")
    #         environment = config.get("environment")
    #         index_name = config.get("index_name", "memory-index")
            
    #         if api_key and environment:
    #             pinecone.init(api_key=api_key, environment=environment)
    #             return PineconeVectorStore(
    #                 pinecone_index=pinecone.Index(index_name)
    #             )
                
    #     except ImportError:
    #         print("Pinecone not available, falling back to simple storage")
    #         return None

class MultiUserLongTermMemory:
    def __init__(self, 
                 storage_dir: str = "/tmp/memory_storage",
                 vector_store_type: str = "chroma",
                 vector_store_config: Dict = None,
                 max_loaded_metadata: int = 5000,
                 use_async: bool = False,
                 long_term_memory_filter_by_datetime: bool = True):
        
        self.use_async = use_async
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        
        self.vector_store_type = vector_store_type
        self.vector_store_config = vector_store_config or {}
        self.max_loaded_metadata = max_loaded_metadata
        self.long_term_memory_filter_by_datetime = long_term_memory_filter_by_datetime
        
        # Shared vector store - KEY OPTIMIZATION
        self.vector_store = self._create_vector_store()
        self.shared_index = None
        
        # LRU cache for user metadata
        self.user_metadata: Dict[str, Dict[str, Any]] = {}
        self.metadata_access_times: Dict[str, datetime] = {}

        # Écriture différée des métadonnées : les agents modifiés sont marqués dirty
        # et flushés par rafale (debounce) au lieu d'une réécriture disque par entrée.
        self._dirty: set = set()
        self._flush_task: Optional[asyncio.Task] = None
        
        # Performance metrics
        self.metrics = {
            "queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "memory_cleanups": 0
        }

        self._init_shared_index(use_async=self.use_async)
        logger.info(f"Initialized scalable memory with {vector_store_type} vector store")
    
    def _create_vector_store(self) -> Optional[BasePydanticVectorStore]:
        """Create vector store based on type"""
        if self.vector_store_type == "chroma":
            return VectorStoreFactory.create_chroma_store(self.storage_dir)
        # elif self.vector_store_type == "qdrant":
        #     return VectorStoreFactory.create_qdrant_store(self.storage_dir)
        # elif self.vector_store_type == "pinecone":
        #     return VectorStoreFactory.create_pinecone_store(self.vector_store_config)
        else:
            return None  # Simple storage

    def _init_shared_index(self, use_async: bool = False):
        """Initialize single shared vector store index"""
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding
        Settings.embed_model = HuggingFaceEmbedding(model_name="all-MiniLM-L6-v2")
        Settings.llm = None

        if self.vector_store:
            storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
            try:
                self.shared_index = load_index_from_storage(storage_context, use_async=use_async)
                logger.info("Loaded existing shared vector index")
            except:
                self.shared_index = VectorStoreIndex.from_documents([], storage_context=storage_context, use_async=use_async)
                logger.info("Created new shared vector index")
        else:
            # Fallback to simple index
            index_path = self.storage_dir / "shared_index"
            if index_path.exists():
                try:
                    storage_context = StorageContext.from_defaults(persist_dir=str(index_path))
                    self.shared_index = load_index_from_storage(storage_context, use_async=use_async)
                    logger.info("Loaded simple vector index")
                    return
                except Exception as e:
                    logger.warning(f"Simple vector index unreadable ({e}) — recreating")
            # Aucun index existant (ou index illisible) : repartir d'un StorageContext neuf
            storage_context = StorageContext.from_defaults()
            self.shared_index = VectorStoreIndex.from_documents([], storage_context=storage_context, use_async=use_async)
            self._persist_shared_index()
            logger.info("Created new simple vector index")
    
    def _persist_shared_index(self):
        """Persist shared index (only for simple storage)"""
        if not self.vector_store:
            index_path = self.storage_dir / "shared_index"
            self.shared_index.storage_context.persist(persist_dir=str(index_path))
    
    def _get_user_metadata_path(self, person_id: str) -> Path:
        """Get metadata file path with sharding"""
        # Use sharding to avoid too many files in one directory
        # shard = abs(hash(person_id)) % 100
        id_bytes = str(person_id).encode('utf-8')
        hash_obj = hashlib.md5(id_bytes)
        hash_int = int(hash_obj.hexdigest()[:8], 16)
        shard = hash_int % 100
        shard_dir = self.storage_dir / "user_metadata" / f"shard_{shard:02d}"
        shard_dir.mkdir(parents=True, exist_ok=True)
        return shard_dir / f"{person_id}.json"
    
    def _load_user_metadata(self, person_id: str) -> Dict[str, Any]:
        """Load user metadata from disk"""
        metadata_path = self._get_user_metadata_path(person_id)
        
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    # Ignore les entrées non-dict (fichiers écrits par l'ancien format
                    # bogué qui sérialisait les MemoryEntry en chaînes via default=str)
                    metadata['entries'] = [
                        MemoryEntry.from_dict(entry)
                        for entry in metadata.get('entries', [])
                        if isinstance(entry, dict)
                    ]
                    self.metadata_access_times[person_id] = datetime.now()
                    self.metrics["cache_misses"] += 1
                    return metadata
            except Exception as e:
                logger.error(f"Error loading metadata for user {person_id}: {e}")
        
        # Default metadata for new user
        metadata = {
            "entries": [], 
            "last_cleanup": None, 
            "last_reflection": None,
            "person_id": person_id,
            "created_at": datetime.now().isoformat(),
            "memory_usage_mb": 0,
            "total_entries": 0
        }
        self.metadata_access_times[person_id] = datetime.now()
        self.metrics["cache_misses"] += 1
        return metadata
    
    def _save_user_metadata(self, person_id: str):
        """Save user metadata to disk"""
        if person_id not in self.user_metadata:
            return
            
        metadata_path = self._get_user_metadata_path(person_id)

        try:
            metadata = self.user_metadata[person_id]
            metadata["total_entries"] = len(metadata["entries"])
            # Les entrées sont des MemoryEntry : sérialisation explicite via to_dict().
            # (json.dumps(default=str) les écrirait comme des chaînes "[date]: contenu",
            # irrécupérables par from_dict au rechargement → mémoire perdue au restart.)
            serializable = {
                **metadata,
                "entries": [entry.to_dict() for entry in metadata["entries"]],
            }
            # Sérialisation unique : le memory_usage_mb écrit dans le fichier est celui
            # de la sauvegarde précédente (valeur purement indicative, décalée d'un save).
            metadata_json = json.dumps(serializable, indent=2, default=str, ensure_ascii=False)
            metadata["memory_usage_mb"] = len(metadata_json.encode('utf-8')) / (1024 * 1024)

            with open(metadata_path, 'w', encoding='utf-8') as f:
                f.write(metadata_json)
            self.metadata_access_times[person_id] = datetime.now()

        except Exception as e:
            logger.error(f"Error saving metadata for user {person_id}: {e}")

    _FLUSH_DELAY_S = 30.0

    def _schedule_flush(self) -> None:
        """Programme un flush différé des métadonnées dirty (une seule tâche en vol)."""
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._flush_after_delay())

    async def _flush_after_delay(self) -> None:
        await asyncio.sleep(self._FLUSH_DELAY_S)
        await self.aflush_dirty()

    async def aflush_dirty(self) -> None:
        """Écrit sur disque les métadonnées de tous les agents marqués dirty (hors event loop)."""
        dirty = list(self._dirty)
        self._dirty.clear()
        for person_id in dirty:
            if person_id in self.user_metadata:
                await asyncio.to_thread(self._save_user_metadata, person_id)

    def _cleanup_metadata_cache(self):
        """LRU eviction for metadata cache"""
        if len(self.user_metadata) <= self.max_loaded_metadata:
            return

        # Sort by access time and remove oldest
        sorted_users = sorted(
            self.metadata_access_times.items(),
            key=lambda x: x[1]
        )

        users_to_remove = len(self.user_metadata) - self.max_loaded_metadata
        removed_count = 0

        for person_id, _ in sorted_users[:users_to_remove]:
            if person_id in self.user_metadata:
                # Save before removing from cache (flush garanti même si un debounce était en attente)
                self._save_user_metadata(person_id)
                self._dirty.discard(person_id)
                del self.user_metadata[person_id]
                if person_id in self.metadata_access_times:
                    del self.metadata_access_times[person_id]
                removed_count += 1

        # Pas de gc.collect() ici : appelé depuis l'event loop via
        # ensure_user_initialized(), il gelait la boucle ~110 ms par éviction.
        self.metrics["memory_cleanups"] += 1

        if removed_count > 0:
            logger.info(f"Cleaned up metadata cache: removed {removed_count} users from memory")
    
    def ensure_user_initialized(self, person_id: str):
        """Ensure user metadata is loaded with cache management"""
        if person_id not in self.user_metadata:
            self.user_metadata[person_id] = self._load_user_metadata(person_id)
            self._cleanup_metadata_cache()
        else:
            # Update access time for LRU
            self.metadata_access_times[person_id] = datetime.now()
            self.metrics["cache_hits"] += 1

    def has_memories(self, person_id: str) -> bool:
        """L'agent a-t-il au moins un souvenir long terme ?

        Lit le cache LRU des métadonnées (en RAM) — aucune requête au vector store.
        Sert au cache sémantique LLM à choisir entre la branche exacte (mémoire vide)
        et la branche par similarité (mémoire remplie).
        """
        self.ensure_user_initialized(person_id)
        return bool(self.user_metadata[person_id]["entries"])

    def get_last_user_memories(self, person_id: str, from_date: datetime) -> List[MemoryEntry]:
        """Get last user memories from a specific date"""
        self.ensure_user_initialized(person_id)
        # logger.debug(f"Retrieving memories for user {person_id} since {from_date}, data: {self.user_metadata[person_id]['entries'][::-1]}")
        return [entry for entry in self.user_metadata[person_id]['entries'] if entry.timestamp >= from_date]

    async def aadd_memory(self, entry: MemoryEntry):
        """Add memory to shared vector store with user namespace"""
        person_id = entry.person_id
        self.ensure_user_initialized(person_id)
        
        # Create document with namespace for user isolation
        doc_id = f"{person_id}_{len(self.user_metadata[person_id]['entries'])}"
        doc = Document(
            text=str(entry.content),
            metadata={
                "person_id": person_id,
                "timestamp": entry.timestamp.isoformat(),
                "memory_type": entry.memory_type,
                "namespace": f"user_{person_id}",  # Key for isolation
                "doc_id": doc_id,
                "tags": entry.tags,
            }
        )
        
        # Add to shared index
        await self.shared_index.ainsert(doc)
        
        # Update user metadata
        self.user_metadata[person_id]["entries"].append(entry)
        # logger.debug(f"Add memory entry for user {person_id}: {entry.to_dict()}")

        # Memory limits per user
        if len(self.user_metadata[person_id]["entries"]) > 10000:
            logger.warning(f"User {person_id} exceeds memory limit, triggering cleanup")
            self.cleanup_user_memories(person_id, days_threshold=7)

        # Écriture différée : les réflexions arrivent par rafales (plusieurs entrées par
        # agent) — le debounce regroupe chaque rafale en une seule écriture disque,
        # exécutée hors de l'event loop. Flush garanti aussi à l'éviction LRU.
        self._dirty.add(person_id)
        self._schedule_flush()

        # Periodic persistence for simple storage
        if not self.vector_store and len(self.user_metadata[person_id]["entries"]) % 10 == 0:
            self._persist_shared_index()

    def _filter_memory_by_working_day(self, message_datetime: datetime, search_datetime: datetime) -> bool:
        # Filter by working day first
        # Convert search_time (seconds since epoch) to day of week
        search_day_of_week = search_datetime.weekday()  # 0=Monday, 6=Sunday
        entry_day_of_week = message_datetime.weekday()
        if (search_day_of_week < 5 and entry_day_of_week >=5) or \
            (search_day_of_week >=5 and entry_day_of_week < 5):
            return False
        
        return True
    
    def _filter_memory_by_peak_time(self, message_datetime: datetime, search_datetime: datetime) -> bool:
        # TODO: Because we do reflection in batch, so the time could be wrong
        # If we do reflection for every entry (arrival), we can filter by peak time

        # Filter by peak time in day
        # search_time_label = time_to_bucket_text(search_datetime.timestamp())
        # entry_time_label = time_to_bucket_text(message_datetime.timestamp())
        # return search_time_label == entry_time_label
        # TODO: For now, we assume all memories are valid
        # We just need a lot of memories to make the model faster converge
        return True
    
    def _filter_memory_by_past_days(self, message_datetime: datetime, search_datetime: datetime, max_past_days: int) -> bool:
        # Filter by past days
        if max_past_days < 0:
            return True
        
        delta_days = (search_datetime - message_datetime).days
        return delta_days <= max_past_days

    async def aquery_user_memories(self, person_id: str, query: str, top_k: int = 8, max_past_days: int = 30, query_at: Optional[int] = None) -> List[MemorySearchResult]:
        """Query memories with namespace filtering"""
        _t0 = time.monotonic()
        self.ensure_user_initialized(person_id)
        self.metrics["queries"] += 1
        query_at_datetime = datetime.fromtimestamp(query_at) if query_at else None

        logger.debug(f"Querying user long term memories for person {person_id}, at {query_at}")

        def filter_message(metadata: dict) -> bool:
            msg_datetime = datetime.fromisoformat(metadata["timestamp"])
            if self.long_term_memory_filter_by_datetime and query_at_datetime:
                return self._filter_memory_by_working_day(msg_datetime, query_at_datetime) \
                    and self._filter_memory_by_peak_time(msg_datetime, query_at_datetime)
            if max_past_days >= 0:
                return self._filter_memory_by_past_days(msg_datetime, query_at_datetime, max_past_days)
            return True
        
        from llama_index.core.vector_stores.types import MetadataFilter, MetadataFilters

        try:
            # Filtrage par person_id délégué au vector store (traduit en `where` Chroma) :
            # évite de rapatrier jusqu'à 500 nœuds globaux pour n'en garder que quelques-uns.
            # La marge ×5 laisse de quoi re-ranker (décroissance temporelle, mots-clés).
            retriever = self.shared_index.as_retriever(
                similarity_top_k=min(max(top_k * 5, 32), 100),
                filters=MetadataFilters(filters=[MetadataFilter(key="person_id", value=person_id)]),
            )

            nodes = await retriever.aretrieve(query)
            logger.debug(f"Retrieved {len(nodes)} raw nodes for user {person_id}")

            # Défense en profondeur : re-vérifie person_id côté Python
            user_results = []
            for node in nodes:
                if (node.metadata.get("person_id") == person_id and \
                    filter_message(node.metadata)):
                    user_results.append(
                        MemorySearchResult(
                            content=node.text,
                            metadata=node.metadata,
                            score=getattr(node, 'score', 0.0)
                        )
                    )
            # Re-rank the results
            scores = self.rank_nodes(query, query_at, user_results)
            # get topk user_results by scores
            top_k_indices = np.argsort(scores)[-top_k:][::-1]
            result = [user_results[i] for i in top_k_indices]
            LTM_QUERY_DURATION.observe(time.monotonic() - _t0)
            return result

        except Exception as e:
            LTM_QUERY_DURATION.observe(time.monotonic() - _t0)
            logger.exception(f"Error querying memories for user {person_id}: {e}")
            return []

    def rank_nodes(self, query: str, query_at: Optional[int], nodes: List[MemorySearchResult]) -> np.ndarray:
        """Rank nodes based on their relevance to the query."""
        if not nodes:
            return np.array([])

        sim_score_weight = settings.agent.long_term_retrieval__sim_weight
        imp_score_weight = settings.agent.long_term_retrieval__keyword_weight
        time_decay_weight = settings.agent.long_term_retrieval__time_weight
        default_reflection_importance_score = settings.agent.long_term_retrieval__default_reflection_importance_score

        # similarity score
        _sim_score = np.array([n.score for n in nodes])
        # logger.debug(f"Sim score debug: {_sim_score.min()}, {_sim_score.max()}, {_sim_score.mean()}")
        # importance score based on keywords, use bleu score with the query
        keyword_only = [(n.metadata.get("tags", "") or "") for n in nodes]
        _imp_score = np.array([
            self._bleu_score(query, kw) if kw else default_reflection_importance_score for kw in keyword_only
        ])
        # logger.debug(f"Importance score debug: {_imp_score.min()}, {_imp_score.max()}, {_imp_score.mean()}")
        # time decay score
        _time_decay_score = np.array([
            self._time_decay_score(n.metadata.get("timestamp"), query_at) for n in nodes
        ])
        # logger.debug(f"Time decay score debug: {_time_decay_score.min()}, {_time_decay_score.max()}, {_time_decay_score.mean()}")

        # Normalize all the score first
        _sim_score = self._normalize_score(_sim_score)
        _imp_score = self._normalize_score(_imp_score)
        _time_decay_score = self._normalize_score(_time_decay_score)

        combined_score = _sim_score * sim_score_weight + _imp_score * imp_score_weight + _time_decay_score * time_decay_weight

        return combined_score

    def _normalize_score(self, a: np.ndarray):
        if a.size == 0:
            return a
        if a.max() == a.min():
            return np.zeros_like(a)

        return (a - a.min()) / (a.max() - a.min())

    def _time_decay_score(self, timestamp_str: str, query_at: Optional[int]) -> float:
        if not timestamp_str or query_at is None:
            return 0.0

        try:
            timestamp = datetime.fromisoformat(timestamp_str)
        except ValueError:
            return 0.0

        # Calculate time decay based on the difference between query time and message time
        decay = settings.agent.long_term_retrieval__time_decay
        time_diff = max(0, (query_at - int(timestamp.timestamp())) / (24*3600))  # Convert to days
        return decay ** time_diff

    def _bleu_score(self, query: str, keyword: str) -> float:
        if not keyword or not query:
            return 0.0

        # Tokenize keywords and query
        kw_tokens = [token.strip(string.punctuation) for token in keyword.lower().split() if token.strip(string.punctuation)]
        query_tokens = [token.strip(string.punctuation) for token in query.lower().split() if token.strip(string.punctuation)]

        # Calculate unigram (1-gram) overlap
        kw_unigrams = set(kw_tokens)
        query_unigrams = set(query_tokens)
        unigram_overlap = len(kw_unigrams.intersection(query_unigrams))
        unigram_score = unigram_overlap / len(kw_unigrams) if kw_unigrams else 0.0

        # Calculate bigram (2-gram) overlap
        kw_bigrams = set(zip(kw_tokens[:-1], kw_tokens[1:])) if len(kw_tokens) > 1 else set()
        query_bigrams = set(zip(query_tokens[:-1], query_tokens[1:])) if len(query_tokens) > 1 else set()
        bigram_overlap = len(kw_bigrams.intersection(query_bigrams))
        bigram_score = bigram_overlap / len(kw_bigrams) if kw_bigrams else 0.0

        # Combine unigram and bigram scores with weights
        # Weight unigrams more heavily as they're more likely to match
        combined_score = (0.7 * unigram_score + 0.3 * bigram_score)
        
        return combined_score

    def cleanup_user_memories(self, person_id: str, days_threshold: int = 30):
        """Cleanup old memories for specific user"""
        self.ensure_user_initialized(person_id)
        
        if person_id not in self.user_metadata:
            return
        
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        original_count = len(self.user_metadata[person_id]["entries"])

        # Filter entries by date and type (entries are MemoryEntry objects)
        filtered_entries = []
        for entry in self.user_metadata[person_id]["entries"]:
            try:
                # Keep if recent or special type
                if (entry.timestamp > cutoff_date or
                        str(entry.memory_type) in ("reflection", "summary")):
                    filtered_entries.append(entry)

            except (TypeError, AttributeError):
                # Keep malformed entries to be safe
                filtered_entries.append(entry)
        
        # Update metadata
        self.user_metadata[person_id]["entries"] = filtered_entries
        self.user_metadata[person_id]["last_cleanup"] = datetime.now().isoformat()
        self._save_user_metadata(person_id)
        
        removed_count = original_count - len(filtered_entries)
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old memories for user {person_id}")
    
    def batch_cleanup_users(self, user_ids: List[str], days_threshold: int = 30):
        """Batch cleanup for multiple users"""
        cleaned_count = 0
        for person_id in user_ids:
            try:
                self.cleanup_user_memories(person_id, days_threshold)
                cleaned_count += 1
                
                # Periodic cache cleanup during batch
                if cleaned_count % 50 == 0:
                    self._cleanup_metadata_cache()
                    
            except Exception as e:
                logger.error(f"Error cleaning up user {person_id}: {e}")
        
        logger.info(f"Batch cleanup completed for {cleaned_count} users")
    
    def get_all_users(self) -> List[str]:
        """Get all users efficiently by scanning shard directories"""
        users = set(self.user_metadata.keys())
        
        # Scan shard directories
        metadata_dir = self.storage_dir / "user_metadata"
        if metadata_dir.exists():
            for shard_dir in metadata_dir.glob("shard_*"):
                if shard_dir.is_dir():
                    for metadata_file in shard_dir.glob("*.json"):
                        users.add(metadata_file.stem)
        
        return list(users)
    
    def get_user_stats(self, person_id: str) -> Dict[str, Any]:
        """Get statistics for specific user"""
        self.ensure_user_initialized(person_id)
        
        if person_id not in self.user_metadata:
            return {"person_id": person_id, "error": "User not found"}
        
        metadata = self.user_metadata[person_id]
        
        # Calculate recent entries
        recent_24h = 0
        recent_7d = 0
        now = datetime.now()
        
        for entry in metadata["entries"]:
            try:
                if now - entry.timestamp < timedelta(hours=24):
                    recent_24h += 1
                if now - entry.timestamp < timedelta(days=7):
                    recent_7d += 1
            except (TypeError, AttributeError):
                continue
        
        return {
            "person_id": person_id,
            "total_entries": len(metadata["entries"]),
            "recent_24h": recent_24h,
            "recent_7d": recent_7d,
            "last_cleanup": metadata.get("last_cleanup"),
            "last_reflection": metadata.get("last_reflection"),
            "created_at": metadata.get("created_at"),
            "memory_usage_mb": metadata.get("memory_usage_mb", 0),
            "in_memory_cache": True,
        }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system-wide statistics"""
        return {
            "total_users": len(self.get_all_users()),
            "loaded_users_in_cache": len(self.user_metadata),
            "max_loaded_metadata": self.max_loaded_metadata,
            "vector_store_type": self.vector_store_type,
            "storage_dir": str(self.storage_dir),
            "cache_hit_ratio": self.metrics["cache_hits"] / max(self.metrics["cache_hits"] + self.metrics["cache_misses"], 1),
            "total_queries": self.metrics["queries"],
            "memory_cleanups": self.metrics["memory_cleanups"],
            "memory_optimized": True,
            "using_shared_index": True
        }
    
    def force_cleanup_all_users(self, days_threshold: int = 30):
        """Force cleanup for all users (maintenance operation)"""
        all_users = self.get_all_users()
        logger.info(f"Starting cleanup for {len(all_users)} users...")
        
        # Process in batches to manage memory
        batch_size = 50
        for i in range(0, len(all_users), batch_size):
            batch = all_users[i:i + batch_size]
            self.batch_cleanup_users(batch, days_threshold)
            
            # Progress update
            logger.info(f"Cleanup progress: {min(i + batch_size, len(all_users))}/{len(all_users)} users")
        
        # Final cleanup
        self._cleanup_metadata_cache()
        if not self.vector_store:
            self._persist_shared_index()
        
        logger.info("Force cleanup completed for all users")
    
    def get_memory_usage_breakdown(self) -> Dict[str, Any]:
        """Get detailed memory usage breakdown"""
        total_entries = 0
        total_size_mb = 0
        user_count = len(self.user_metadata)
        
        for metadata in self.user_metadata.values():
            total_entries += len(metadata.get("entries", []))
            total_size_mb += metadata.get("memory_usage_mb", 0)
        
        return {
            "loaded_users": user_count,
            "total_entries_in_cache": total_entries,
            "total_cache_size_mb": total_size_mb,
            "avg_entries_per_user": total_entries / max(user_count, 1),
            "avg_size_per_user_mb": total_size_mb / max(user_count, 1),
            "cache_efficiency": f"{user_count}/{self.max_loaded_metadata}"
        }
    
    def get_user_all_memories(self, person_id: str) -> List[MemoryEntry]:
        """Get all memories for a specific user"""
        self.ensure_user_initialized(person_id)
        
        if person_id not in self.user_metadata:
            return []

        # Entries are already MemoryEntry objects (converted at load time)
        return list(self.user_metadata[person_id]["entries"])

    async def aexport_user_data(self, person_id: str) -> Dict[str, Any]:
        """Export all data for a specific user"""
        self.ensure_user_initialized(person_id)
        
        if person_id not in self.user_metadata:
            return {"error": "User not found"}
        
        # Get user metadata
        user_data = {
            "person_id": person_id,
            "metadata": self.user_metadata[person_id].copy(),
            "stats": self.get_user_stats(person_id)
        }
        
        # Query all memories for this user
        try:
            all_memories = await self.aquery_user_memories(person_id, "", top_k=1000)
            user_data["memories"] = all_memories
        except Exception as e:
            user_data["memories"] = []
            user_data["export_error"] = str(e)
        
        return user_data
    
    def __str__(self) -> str:
        return f"ScalableLongTermMemory({self.vector_store_type}, {len(self.user_metadata)} users cached)"
