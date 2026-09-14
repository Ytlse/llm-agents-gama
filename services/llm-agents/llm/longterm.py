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
from sim_clock import gama_timestamp, wall_clock

from loguru import logger
import numpy as np
from prometheus_client import Histogram

# Modèle de plongement par défaut, hérité de l'implémentation de Vu et al. (2025). C'est un
# modèle Sentence-Transformers (Reimers & Gurevych, 2019) entraîné sur un corpus anglophone
# d'après sa fiche — cohérent avec le corpus depuis la bascule anglaise du ticket 074.
MODELE_PLONGEMENT_DEFAUT = "all-MiniLM-L6-v2"

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

from llm.axes import affinite_axes, affinite_meteo
from llm.gravite import est_purgeable, force_apres_rappel, force_initiale, poids_temporel
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
                 max_loaded_metadata: int = 2000,
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

        # Ticket 071, lot 2 — le modèle de plongement vient du PARAMÈTRE. Il était codé en dur
        # ici alors que `settings.agent.embedding_model` existait : un paramètre qui ne commande
        # rien est un mensonge de configuration, et il interdisait de comparer deux modèles sans
        # toucher au code.
        #
        # ⚠ Le modèle ne CHANGE pas : le défaut reste celui en service. Le passage à un modèle
        # francophone, un temps prévu, est abandonné — le dispositif bascule en anglais
        # (ticket 074), et le modèle hérité de Vu et al. redevient cohérent avec le corpus.
        # Tout changement ultérieur imposerait une RECONSTRUCTION COMPLÈTE de l'index, les
        # vecteurs n'étant pas comparables d'un modèle à l'autre.
        modele = (settings.agent.embedding_model or "").strip() or MODELE_PLONGEMENT_DEFAUT
        if modele != MODELE_PLONGEMENT_DEFAUT:
            logger.warning(
                f"[ltm] modèle de plongement NON STANDARD : « {modele} » au lieu de "
                f"« {MODELE_PLONGEMENT_DEFAUT} ». L'index doit avoir été reconstruit avec ce "
                f"modèle, sans quoi les similarités n'ont aucun sens."
            )
        else:
            logger.info(f"[ltm] modèle de plongement : {modele}")
        Settings.embed_model = HuggingFaceEmbedding(model_name=modele)
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
        # Ticket 071 (défaut B) — l'identifiant dérivait de la LONGUEUR de la liste. Après un
        # nettoyage la liste raccourcit, et les identifiants suivants entraient en collision
        # avec ceux déjà indexés. Le compteur est désormais monotone et persisté.
        doc_index = self.user_metadata[person_id].get("next_doc_index")
        if doc_index is None:  # métadonnées d'avant le ticket 071
            doc_index = len(self.user_metadata[person_id]["entries"])
        self.user_metadata[person_id]["next_doc_index"] = doc_index + 1
        doc_id = f"{person_id}_{doc_index}"

        # Ticket 071, lot 1 — la durée de vie est fixée À L'ÉCRITURE, depuis la gravité.
        # `force = min(S0 × (1 + k × I), FORCE_MAX)`, plafond compris : aucune entrée ne part
        # au-delà, même quand S0 triple. Une entrée déjà qualifiée (réflexion rejouée, reprise
        # de run) garde la sienne.
        if entry.force is None:
            entry.force = force_initiale(entry.importance)

        doc = Document(
            # `id_` rend le document adressable pour la suppression : sans lui, une entrée
            # retirée des métadonnées resterait indéfiniment dans l'index vectoriel.
            id_=doc_id,
            text=str(entry.content),
            metadata={
                "person_id": person_id,
                "timestamp": entry.timestamp.isoformat(),
                "memory_type": entry.memory_type,
                "namespace": f"user_{person_id}",  # Key for isolation
                "doc_id": doc_id,
                "tags": entry.tags,
                # Qualification du souvenir (lot 1). Elle est recopiée ici pour que les viviers
                # B et C du lot 2 puissent filtrer sans embedding. ⚠ C'est un INSTANTANÉ figé à
                # l'écriture : `force` et `rappels` évoluent ensuite, et l'autorité sur ces deux
                # champs reste les métadonnées de l'agent, jamais cette copie. Le classement lit
                # donc l'entrée, pas ce dictionnaire (cf. `rank_nodes`).
                "importance": float(entry.importance or 0.0),
                "axe_objet": entry.axe_objet or "",
                "axe_lieu": entry.axe_lieu or "",
                "axe_creneau": entry.axe_creneau or "",
                "axe_motif": entry.axe_motif or "",
                "valence": entry.valence or "neutre",
            }
        )
        
        # Add to shared index
        await self.shared_index.ainsert(doc)
        
        # Update user metadata
        entry.doc_id = doc_id
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

    async def aquery_user_memories(
        self,
        person_id: str,
        query: str,
        top_k: int = 8,
        max_past_days: int = 30,
        query_at: Optional[int] = None,
        modes_offerts: Optional[List[str]] = None,
        contexte: Optional[Dict[str, Any]] = None,
    ) -> List[MemorySearchResult]:
        """Query memories with namespace filtering"""
        _t0 = time.monotonic()
        self.ensure_user_initialized(person_id)
        self.metrics["queries"] += 1
        # Heure MURALE de GAMA : le côté droit des filtres doit se comparer aux
        # `datetime` des souvenirs, qui portent eux aussi des champs muraux
        # (`llm_agent.add_short_term_memory`). Lu dans le fuseau du processus, il
        # décalait d'une heure le jour de semaine et l'ancienneté d'un souvenir de
        # fin de soirée.
        query_at_datetime = wall_clock(query_at) if query_at else None

        logger.debug(f"Querying user long term memories for person {person_id}, at {query_at}")

        def filter_message(metadata: dict) -> bool:
            # Ticket 071 (défaut C) — les deux filtres se CUMULENT. Avant, le filtre par jour
            # ouvré et créneau sortait immédiatement, si bien que la fenêtre d'âge
            # (`max_past_days`) n'était jamais appliquée quand l'option était active : un
            # souvenir vieux de trois ans en temps simulé passait, pourvu qu'il tombe le même
            # jour de semaine que la requête.
            msg_datetime = datetime.fromisoformat(metadata["timestamp"])
            if max_past_days >= 0 and not self._filter_memory_by_past_days(
                msg_datetime, query_at_datetime, max_past_days
            ):
                return False
            if self.long_term_memory_filter_by_datetime and query_at_datetime:
                return self._filter_memory_by_working_day(msg_datetime, query_at_datetime) \
                    and self._filter_memory_by_peak_time(msg_datetime, query_at_datetime)
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

            # Le classement et les filtres lisent les métadonnées de l'agent, pas la copie
            # figée dans l'index : `force`, `rappels` et les compteurs de concepts évoluent,
            # et l'index n'est pas réécrit pour autant. Les entrées sont déjà en RAM ici —
            # `ensure_user_initialized` les a rechargées du disque si l'agent avait été évincé
            # du cache LRU. Construit AVANT les viviers : le filtre des concepts hors service
            # en a besoin.
            entrees_par_doc = {
                e.doc_id: e
                for e in self.user_metadata.get(person_id, {}).get("entries", [])
                if getattr(e, "doc_id", None)
            }

            # ── Vivier A : sémantique. Défense en profondeur sur person_id côté Python.
            user_results = []
            vus = set()
            for node in nodes:
                if (node.metadata.get("person_id") == person_id and \
                    filter_message(node.metadata)):
                    _meta = dict(node.metadata)
                    _meta.setdefault("vivier", "A")
                    _doc = _meta.get("doc_id")
                    if _doc and _doc in vus:
                        continue
                    if _doc:
                        vus.add(_doc)
                    user_results.append(
                        MemorySearchResult(
                            content=node.text,
                            metadata=_meta,
                            score=getattr(node, 'score', 0.0)
                        )
                    )

            # ── Viviers B et C : structurés, lus en RAM, sans plongement (ticket 071, lot 2).
            # Ils s'AJOUTENT au vivier sémantique et sont dédupliqués par identifiant de
            # document. La fenêtre d'âge leur est appliquée comme aux autres : c'est le seul
            # filtre qui subsiste, avec l'identité de l'agent.
            for res in self.viviers_structures(person_id, modes_offerts):
                _doc = res.metadata.get("doc_id")
                if _doc in vus or not filter_message(res.metadata):
                    continue
                vus.add(_doc)
                user_results.append(res)

            # Ticket 071, lot 3 — les concepts MIS HORS SERVICE sont écartés du rappel. Ils
            # restent dans les métadonnées : ils ne sont pas supprimés, leur mise à l'écart
            # datée est l'observable que l'expérience d'hystérésis cherche.
            #
            # ⚠ C'est la TROISIÈME exception à la règle de non-exclusion du lot 2, avec
            # l'identité de l'agent et la fenêtre d'âge. Elle est écrite comme une exception
            # et non fondue dans la règle : « rien ne filtre » se transporte à l'article, et
            # y deviendrait faux sans mention.
            _avant = len(user_results)
            user_results = [
                r for r in user_results
                if (entrees_par_doc.get((r.metadata or {}).get("doc_id")) is None
                    or entrees_par_doc[(r.metadata or {}).get("doc_id")].est_servi)
            ]
            _ecartes = _avant - len(user_results)
            if _ecartes:
                logger.debug(
                    f"[concepts] {_ecartes} concept(s) hors service écarté(s) du rappel pour "
                    f"{person_id} — contredits plus souvent que confirmés, conservés en mémoire"
                )
            # Re-rank the results
            scores = self.rank_nodes(
                query, query_at, user_results, entrees_par_doc, contexte
            )
            # get topk user_results by scores
            top_k_indices = np.argsort(scores)[-top_k:][::-1]
            result = [user_results[i] for i in top_k_indices]

            self._compter_viviers(person_id, user_results, result)

            # Le rappel RENFORCE, et seulement ce qui a été réellement servi au modèle : les
            # candidats écartés du top-K n'ont pas été rappelés. C'est la mécanique de
            # MemoryBank, et le corollaire de Park et al. dont la fraîcheur décroît depuis le
            # dernier rappel et non depuis la création.
            self._renforcer_les_servis(person_id, result, entrees_par_doc, query_at_datetime)

            LTM_QUERY_DURATION.observe(time.monotonic() - _t0)
            return result

        except Exception as e:
            LTM_QUERY_DURATION.observe(time.monotonic() - _t0)
            logger.exception(f"Error querying memories for user {person_id}: {e}")
            return []

    # Fenêtre d'observation des viviers, en nombre de décisions. Les alarmes se lisent sur
    # une fenêtre et non sur un coup : un vivier B vide sur UNE décision est banal — l'agent
    # n'a pas encore de souvenir du mode offert. Vide sur un tiers d'une fenêtre, c'est une
    # normalisation d'axes défaillante.
    _FENETRE_VIVIERS = 200

    def _compter_viviers(
        self,
        person_id: str,
        candidats: List[MemorySearchResult],
        servis: List[MemorySearchResult],
    ) -> None:
        """Part du top-K issue de chaque vivier, et les deux alarmes du lot 2.

        C'est la mesure DIRECTE de l'utilité des viviers structurés. Sans elle, on ne saurait
        pas distinguer « les viviers B et C remontent des souvenirs que A ratait » de « ils ne
        servent à rien et la conception est à revoir ».
        """
        if not hasattr(self, "_viviers_fenetre"):
            self._viviers_fenetre: list = []
            self._alarme_vivier_b = False
            self._alarme_vivier_a = False

        parts = {"A": 0, "B": 0, "C": 0}
        for r in servis:
            parts[(r.metadata or {}).get("vivier", "A")] = (
                parts.get((r.metadata or {}).get("vivier", "A"), 0) + 1
            )
        b_propose = any((c.metadata or {}).get("vivier") == "B" for c in candidats)
        self._viviers_fenetre.append((parts, b_propose))
        if len(self._viviers_fenetre) > self._FENETRE_VIVIERS:
            self._viviers_fenetre = self._viviers_fenetre[-self._FENETRE_VIVIERS:]

        n = len(self._viviers_fenetre)
        if n < self._FENETRE_VIVIERS:
            return  # une fenêtre incomplète ne déclenche rien : trop peu pour conclure

        sans_b = sum(1 for p, propose in self._viviers_fenetre if not propose)
        total_servis = sum(sum(p.values()) for p, _ in self._viviers_fenetre) or 1
        part_a = sum(p.get("A", 0) for p, _ in self._viviers_fenetre) / total_servis

        logger.info(
            f"[viviers] fenêtre de {n} décisions — part du top-K : "
            f"A {part_a:.0%}, B {sum(p.get('B', 0) for p, _ in self._viviers_fenetre) / total_servis:.0%}, "
            f"C {sum(p.get('C', 0) for p, _ in self._viviers_fenetre) / total_servis:.0%} "
            f"| vivier B vide sur {sans_b / n:.0%} des décisions"
        )

        if sans_b / n > 1 / 3 and not self._alarme_vivier_b:
            self._alarme_vivier_b = True
            logger.error(
                f"[ALARME] vivier B vide sur {sans_b / n:.0%} des {n} dernières décisions "
                f"(seuil : un tiers) — la normalisation des axes est probablement défaillante, "
                f"les souvenirs ne portent pas le mode des options offertes"
            )
        elif sans_b / n <= 1 / 6 and self._alarme_vivier_b:
            self._alarme_vivier_b = False
            logger.info("[viviers] le vivier B est de nouveau alimenté")

        if part_a > 0.95 and not self._alarme_vivier_a:
            self._alarme_vivier_a = True
            logger.error(
                f"[ALARME] {part_a:.0%} du top-K vient du SEUL vivier sémantique sur les {n} "
                f"dernières décisions (seuil : 95 %) — les viviers structurés n'apportent rien "
                f"et la conception du lot 2 est à revoir"
            )
        elif part_a <= 0.90 and self._alarme_vivier_a:
            self._alarme_vivier_a = False
            logger.info("[viviers] les viviers structurés contribuent de nouveau au top-K")

    def journal_trajets(self, person_id: str) -> dict:
        """Journal des trajets de l'agent — le compteur d'où sortent ses habitudes (lot 4)."""
        self.ensure_user_initialized(person_id)
        return self.user_metadata[person_id].setdefault("journal", {})

    def noter_trajet(
        self,
        person_id: str,
        motif: Optional[str],
        creneau: Optional[str],
        mode: Optional[str],
        retard_s: float = 0.0,
    ) -> None:
        """Enregistre un trajet accompli dans le journal de l'agent.

        Le journal est PERSISTÉ avec les métadonnées : il réutilise l'écriture différée déjà en
        place. Sans persistance, un run repris repartirait sans habitudes, et le bloc des
        habitudes mentirait par omission tout le premier jour.
        """
        from llm.noyau import noter_trajet as _noter

        _noter(self.journal_trajets(person_id), motif, creneau, mode, retard_s)
        self._dirty.add(person_id)
        self._schedule_flush()

    def viviers_structures(
        self,
        person_id: str,
        modes_offerts: Optional[List[str]] = None,
    ) -> List[MemorySearchResult]:
        """Viviers B (par objet) et C (chocs), lus dans les métadonnées de l'agent.

        Aucun plongement, aucune requête au magasin vectoriel : les souvenirs de l'agent sont
        déjà en RAM ici — `ensure_user_initialized` les recharge du disque si l'agent avait été
        évincé du cache LRU. Le coût est une lecture de liste de quelques centaines d'éléments.

        **B — par objet.** Pour chaque mode offert dans les options de la décision, les
        souvenirs portant ce mode, les plus graves et les plus récents d'abord. C'est lui qui
        fait remonter une chute à vélo du matin sur une décision du soir : ni le lieu, ni le
        créneau, ni le motif ne coïncident, mais l'objet les relie, et l'objet suffit.

        **C — chocs.** Les souvenirs au-dessus du seuil de gravité, **sans aucune condition**
        de lieu, d'heure ni de motif. Il garantit qu'un souvenir grave n'est jamais perdu par
        accident de classement.
        """
        self.ensure_user_initialized(person_id)
        entrees = self.user_metadata.get(person_id, {}).get("entries", [])
        if not entrees:
            return []

        par_mode = int(settings.agent.memoire__vivier_b_par_mode)
        taille_c = int(settings.agent.memoire__vivier_c_taille)
        seuil_choc = float(settings.agent.memoire__importance_choc)

        def _cle(e: MemoryEntry):
            # Gravité d'abord, récence ensuite : à gravité égale, le plus frais passe devant.
            return (float(e.importance or 0.0), e.horodatage_de_reference)

        retenus: Dict[str, MemoryEntry] = {}
        origines: Dict[str, str] = {}

        for mode in {m for m in (modes_offerts or []) if m}:
            candidats = [e for e in entrees if e.axe_objet == mode and e.doc_id]
            for e in sorted(candidats, key=_cle, reverse=True)[:par_mode]:
                retenus.setdefault(e.doc_id, e)
                origines.setdefault(e.doc_id, "B")

        chocs = [
            e for e in entrees
            if e.doc_id and float(e.importance or 0.0) >= seuil_choc
        ]
        for e in sorted(chocs, key=_cle, reverse=True)[:taille_c]:
            retenus.setdefault(e.doc_id, e)
            origines.setdefault(e.doc_id, "C")

        return [
            MemorySearchResult(
                content=entree.content,
                metadata={
                    "person_id": person_id,
                    "timestamp": entree.timestamp.isoformat(),
                    "memory_type": str(entree.memory_type),
                    "doc_id": doc_id,
                    "tags": entree.tags,
                    "vivier": origines[doc_id],
                },
                # Aucune similarité sémantique n'a été calculée pour ces candidats : ils
                # n'ont pas été trouvés par le texte. Zéro est la valeur EXACTE de leur
                # similarité mesurée, pas un défaut — et les quatre autres composantes les
                # classent.
                score=0.0,
            )
            for doc_id, entree in retenus.items()
        ]

    def rank_nodes(
        self,
        query: str,
        query_at: Optional[int],
        nodes: List[MemorySearchResult],
        entrees_par_doc: Optional[Dict[str, MemoryEntry]] = None,
        contexte: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        """Rank nodes based on their relevance to the query.

        `entrees_par_doc` (ticket 071, lot 1) donne accès à l'entrée AUTORITAIRE derrière
        chaque nœud : sa durée de vie propre et la date de son dernier rappel. Absent, le
        classement retombe sur l'horodatage de l'index et la constante de temps par défaut,
        c'est-à-dire exactement le comportement d'avant le lot 1.
        """
        if not nodes:
            return np.array([])

        sim_w = settings.agent.long_term_retrieval__sim_weight
        cat_w = settings.agent.long_term_retrieval__keyword_weight
        temps_w = settings.agent.long_term_retrieval__time_weight
        grav_w = settings.agent.long_term_retrieval__importance_weight
        axes_w = settings.agent.long_term_retrieval__affinite_weight

        entrees = entrees_par_doc or {}
        ctx = contexte or {}

        def _entree(n):
            return entrees.get((n.metadata or {}).get("doc_id"))

        # 1. Similarité sémantique. Bornée : le magasin vectoriel peut sortir de [0, 1], et les
        # candidats des viviers structurés n'ont pas de similarité mesurée — elle vaut zéro,
        # ce qui est exact, et leurs quatre autres composantes les classent.
        _sim = np.clip(np.array([n.score for n in nodes]), 0.0, 1.0)

        # 2. Affinité catégorielle — la MÉTÉO seule (arbitrage du 2026-09-14, issue A). Elle
        # remplace le score dit « BLEU-2 », qui était un taux de rappel lexical asymétrique sur
        # les étiquettes et non le BLEU de Papineni et al. Réduite à la météo parce que ses
        # trois autres attributs — mode, créneau, motif — SONT déjà les axes de la composante
        # suivante : les compter deux fois rendrait le score ininterprétable.
        _cat = np.array([
            affinite_meteo(getattr(_entree(n), "axe_meteo", None), ctx.get("axe_meteo"))
            for n in nodes
        ])

        # 3. Poids temporel : exp(-Δt / force), Δt depuis le dernier rappel.
        _temps = np.array([
            self._time_decay_score(
                n.metadata.get("timestamp"), query_at, entree=_entree(n)
            )
            for n in nodes
        ])

        # 4. Gravité du souvenir. Composante restaurée de Park et al. (2023), que Vu et al.
        # avaient écartée.
        _grav = np.array([
            float(getattr(_entree(n), "importance", 0.0) or 0.0) for n in nodes
        ])

        # 5. Affinité d'axes, en BONUS et jamais en veto : un axe discordant contribue zéro,
        # il ne retranche rien. Hors identité de l'agent et fenêtre d'âge, RIEN ne filtre.
        _axes = np.array([
            affinite_axes(
                getattr(_entree(n), "axe_objet", None),
                getattr(_entree(n), "axe_lieu", None),
                getattr(_entree(n), "axe_creneau", None),
                getattr(_entree(n), "axe_motif", None),
                objet_courant=ctx.get("axe_objet"),
                lieu_courant=ctx.get("axe_lieu"),
                creneau_courant=ctx.get("axe_creneau"),
                motif_courant=ctx.get("axe_motif"),
            )
            for n in nodes
        ])

        # Ticket 048 — la normalisation min-max PAR COMPOSANTE reste abandonnée. Elle ramenait
        # mécaniquement le meilleur candidat du lot à 1 et le pire à 0, quel que soit l'écart
        # réel : deux décisions n'étaient pas comparables, et l'ordre par ancienneté était
        # INVARIANT à la constante de temps. Les cinq composantes entrent en valeur ABSOLUE.
        combined_score = (
            _sim * sim_w
            + _cat * cat_w
            + _temps * temps_w
            + _grav * grav_w
            + _axes * axes_w
        )

        return combined_score

    def _time_decay_score(
        self,
        timestamp_str: str,
        query_at: Optional[int],
        entree: Optional[MemoryEntry] = None,
    ) -> float:
        """Poids temporel d'un souvenir, sur [0, 1] et en valeur ABSOLUE.

        Ticket 071, lot 1 — deux changements par rapport au ticket 048 :

        - la constante de temps n'est plus commune, c'est celle du souvenir, fonction de sa
          gravité : près de vingt jours pour un souvenir `marquant` contre moins de trois pour
          un trajet banal ;
        - le Δt se compte depuis le **dernier rappel** et non depuis l'écriture, comme chez
          Park et al. (2023, § 4.1) et MemoryBank. Un souvenir souvent rappelé reste frais ;
          un souvenir jamais rappelé vieillit depuis son écriture, comme avant.

        `gama_timestamp` et non `.timestamp()` : `query_at` est un horodatage GAMA (heure
        murale) et les `datetime` des souvenirs portent des champs muraux — les soustraire
        après un passage par le fuseau du processus ajouterait une heure d'ancienneté fictive.

        Sans entrée autoritaire (entrée écrite avant le lot 1, ou test qui ne fournit que des
        nœuds), on retombe sur l'horodatage de l'index et la constante par défaut.
        """
        if query_at is None:
            return 0.0

        if entree is not None:
            # Ticket 071, lot 3 — DEUX RÉGIMES, et c'est le point le plus fort du ticket.
            # Pour un concept ou un résumé, la composante temporelle n'est plus une
            # décroissance d'horloge mais la CONFIANCE. Qu'une ligne sature les jours de pluie
            # entre 8 h et 8 h 30 ne devient pas faux parce que dix jours ont passé — or sous
            # le régime uniforme ce concept tombait à 2,8 % de son poids en dix jours et
            # sortait du top-K sans qu'aucune observation ne l'ait infirmé.
            if not entree.est_episodique:
                return float(entree.confiance)
            reference = entree.horodatage_de_reference
            force = entree.force
        else:
            if not timestamp_str:
                return 0.0
            try:
                reference = datetime.fromisoformat(timestamp_str)
            except ValueError:
                return 0.0
            force = None

        time_diff = max(0, (query_at - gama_timestamp(reference)) / (24 * 3600))
        return poids_temporel(time_diff, force)

    def _renforcer_les_servis(
        self,
        person_id: str,
        servis: List[MemorySearchResult],
        entrees_par_doc: Dict[str, MemoryEntry],
        quand: Optional[datetime],
    ) -> int:
        """`force ← min(force + δ, FORCE_MAX)` et `rappels += 1` sur les entrées SERVIES.

        Trois précautions qui ne sont pas des détails :

        - seules les entrées du top-K sont renforcées, pas les candidats : un souvenir écarté
          du classement n'a pas été rappelé ;
        - `timestamp` n'est JAMAIS touché — il s'affiche dans le prompt et sert de côté gauche
          aux filtres par jour et par ancienneté. Le faire glisser réécrirait l'histoire de
          l'agent, qui croirait que sa chute à vélo a eu lieu hier. Seul `dernier_rappel` bouge ;
        - l'écriture disque passe par le mécanisme `dirty` existant : aucun accès disque
          synchrone sur le chemin d'une décision.

        Sans horloge simulée (`quand is None`), on renforce quand même la durée de vie mais on
        ne date pas le rappel : jamais de repli sur l'horloge de la machine.
        """
        if not servis or not entrees_par_doc:
            return 0
        renforces = 0
        for resultat in servis:
            entree = entrees_par_doc.get((resultat.metadata or {}).get("doc_id"))
            if entree is None:
                continue
            entree.force = force_apres_rappel(entree.force)
            entree.rappels = int(entree.rappels or 0) + 1
            if quand is not None:
                entree.dernier_rappel = quand
            renforces += 1
        if renforces:
            self._dirty.add(person_id)
            self._schedule_flush()
        return renforces

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
        # Ticket 071 (défaut D) — une étiquette d'un seul mot n'a AUCUN bigramme : appliquer
        # le poids 0.3 à un score nul la plafonnait à 0.70 même en correspondance parfaite,
        # contre 1.00 pour une étiquette de deux mots. Sans bigrammes, le poids revient en
        # entier aux unigrammes.
        if kw_bigrams:
            combined_score = (0.7 * unigram_score + 0.3 * bigram_score)
        else:
            combined_score = unigram_score
        
        return combined_score

    def _sim_now(self, person_id: str) -> Optional[datetime]:
        """Heure murale SIMULÉE de référence pour cet agent, ou None si indéterminable.

        Le souvenir le plus récent de l'agent porte l'heure murale de GAMA : c'est le seul
        « maintenant » qui ait un sens ici. L'horloge de la machine hôte n'en est pas un.
        """
        entries = self.user_metadata.get(person_id, {}).get("entries") or []
        stamps = [e.timestamp for e in entries if getattr(e, "timestamp", None) is not None]
        return max(stamps) if stamps else None

    def cleanup_user_memories(self, person_id: str, days_threshold: int = 30,
                              now: Optional[datetime] = None):
        """Cleanup old memories for specific user.

        Ticket 071 (défaut A) — le seuil se calculait sur `datetime.now()`, l'horloge de la
        MACHINE, alors que `entry.timestamp` porte l'heure murale de GAMA. Dès qu'un run
        rejouait une date antérieure de plus que le seuil, la condition de conservation était
        fausse pour TOUTES les entrées et le nettoyage vidait concepts et conversations.

        Règle retenue : un nettoyage qui ne sait pas établir le temps simulé ne nettoie RIEN.
        Jamais de repli sur l'horloge de la machine — une suppression ne doit pas dépendre de
        la date à laquelle le run a été lancé.
        """
        self.ensure_user_initialized(person_id)

        if person_id not in self.user_metadata:
            return

        sim_now = now or self._sim_now(person_id)
        if sim_now is None:
            logger.warning(
                f"[cleanup] Temps simulé indéterminable pour {person_id} — aucun souvenir "
                f"horodaté : nettoyage ABANDONNÉ (jamais de repli sur l'horloge machine)"
            )
            return

        original_count = len(self.user_metadata[person_id]["entries"])

        # Ticket 071, lot 1 — la rétention cesse d'être aveugle au contenu du souvenir.
        #
        # AVANT : un seuil d'âge commun, plus une exemption par TYPE (les réflexions et les
        # résumés ne partaient jamais). Deux conséquences fâcheuses : un souvenir grave de
        # trente et un jours tombait avec les trajets ordinaires, et les réflexions
        # s'accumulaient sans fin.
        #
        # MAINTENANT, deux régimes, comme la taxonomie de Tulving (1972) le demande :
        #   - SÉMANTIQUE (concepts, résumés) : jamais purgé par l'horloge. Un concept ne
        #     devient pas faux parce que dix jours ont passé ; il se perd par CONTRADICTION,
        #     et sa mise à l'écart datée est l'observable que l'expérience cherche (lot 3) ;
        #   - ÉPISODIQUE (entrées brutes, réflexions) : purgé quand son poids temporel passe
        #     sous le seuil, soit ~4,6 constantes de temps. Treize jours pour un trajet banal
        #     jamais rappelé, quatre-vingt-onze pour un souvenir `marquant` — donc jamais dans
        #     un run. La gravité et les rappels décident, plus le seul calendrier.
        #
        # `days_threshold` reste un PLANCHER de sécurité : rien de plus jeune n'est purgé,
        # quelle que soit sa durée de vie. Il ne peut donc que retarder une purge, jamais la
        # provoquer.
        filtered_entries = []
        supprimes = []
        for entry in self.user_metadata[person_id]["entries"]:
            try:
                if not entry.est_episodique:
                    filtered_entries.append(entry)
                    continue
                age_jours = (
                    sim_now - entry.horodatage_de_reference
                ).total_seconds() / 86400.0
                if age_jours <= days_threshold:
                    filtered_entries.append(entry)
                elif est_purgeable(age_jours, entry.force):
                    supprimes.append(entry)
                else:
                    filtered_entries.append(entry)

            except (TypeError, AttributeError):
                # Keep malformed entries to be safe
                filtered_entries.append(entry)

        # Ticket 071 (défaut B) — retirer aussi de l'index vectoriel. Sans cela, une entrée
        # absente des métadonnées continuait d'être renvoyée par ChromaDB et réinjectée dans
        # les prompts de décision. L'échec d'une suppression ne doit pas faire perdre la mise
        # à jour des métadonnées : il est journalisé, pas propagé.
        self._delete_from_index(supprimes, person_id)

        # Update metadata
        self.user_metadata[person_id]["entries"] = filtered_entries
        self.user_metadata[person_id]["last_cleanup"] = sim_now.isoformat()
        self._save_user_metadata(person_id)

        removed_count = original_count - len(filtered_entries)
        if removed_count > 0:
            logger.info(
                f"Cleaned up {removed_count} old memories for user {person_id} "
                f"(seuil {days_threshold} j avant {sim_now.isoformat()}, temps simulé)"
            )

    def _delete_from_index(self, entries: List[MemoryEntry], person_id: str) -> int:
        """Retire du vector store les documents des entrées données. Fail-open et journalisé."""
        if not entries or self.shared_index is None:
            return 0
        supprimes = 0
        sans_id = 0
        for entry in entries:
            doc_id = getattr(entry, "doc_id", None)
            if not doc_id:
                sans_id += 1  # entrée écrite avant le ticket 071 : non adressable
                continue
            try:
                self.shared_index.delete_ref_doc(doc_id, delete_from_docstore=True)
                supprimes += 1
            except Exception as exc:  # noqa: BLE001 — une suppression ratée ne doit rien casser
                logger.warning(f"[cleanup] Suppression index échouée pour {doc_id}: {exc}")
        if sans_id:
            logger.warning(
                f"[cleanup] {sans_id} souvenir(s) de {person_id} sans identifiant de document "
                f"(écrits avant le ticket 071) : retirés des métadonnées, CONSERVÉS dans l'index"
            )
        return supprimes
    
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
