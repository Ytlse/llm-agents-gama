import asyncio
import hashlib
import json
import threading
import time
import uuid
from datetime import datetime
from typing import Optional

from loguru import logger
from prometheus_client import Counter, Gauge, Histogram

from llm_module.core.mode_choice import draw_index, mode_distribution
from llm_module.telemetry.alarms import fire_alarme

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

# Couverture du cache persistant, relevée au démarrage — permet de répondre en un
# coup d'œil « le cache est-il assez peuplé pour l'init ? » (cf. dashboards 02_init_bootstrap
# et 06_cache_llm / init_report).
LLM_CACHE_POINTS_TOTAL = Gauge(
    "llm_cache_points_total",
    "Nombre total de points dans la collection Qdrant du cache LLM au démarrage",
)
LLM_CACHE_POINTS_EXACT = Gauge(
    "llm_cache_points_exact",
    "Points « mémoire vide » (exact match) — chemin utilisé par le bootstrap au /init",
)
LLM_CACHE_POINTS_STALE = Gauge(
    "llm_cache_points_stale",
    "Points inexploitables par le filtre courant (schéma obsolète : weekday manquant)",
)
LLM_CACHE_AGENTS_COVERED = Gauge(
    "llm_cache_agents_covered",
    "Nombre d'agents distincts ayant au moins une décision « mémoire vide » en cache",
)

# Compteurs process-wide hits/lookups pour reporting du taux de cache LLM dans les logs.
_LLM_CACHE_HITS = 0
_LLM_CACHE_LOOKUPS = 0
# Répartition des miss par raison (no_candidates, code_not_in_options, lookup_error)
# pour diagnostiquer le taux d'échec sans dépendre de Prometheus.
_LLM_MISS_REASONS: dict[str, int] = {}


def _record_llm_miss(reason: str) -> None:
    _LLM_MISS_REASONS[reason] = _LLM_MISS_REASONS.get(reason, 0) + 1


def get_llm_cache_stats() -> tuple[int, int]:
    """Retourne (hits, lookups) cumulés du cache sémantique LLM depuis le démarrage."""
    return _LLM_CACHE_HITS, _LLM_CACHE_LOOKUPS


def get_llm_miss_breakdown() -> dict[str, int]:
    """Retourne la répartition cumulée des miss du cache LLM par raison."""
    return dict(_LLM_MISS_REASONS)


_instances: dict[str, "LlmSemanticCache"] = {}
_instances_lock = threading.Lock()


class LlmSemanticCache:
    def __new__(cls, cache_dir: str, semantic_threshold: float, embed_model_name: str):
        with _instances_lock:
            if cache_dir not in _instances:
                instance = super().__new__(cls)
                instance._initialized = False
                _instances[cache_dir] = instance
            return _instances[cache_dir]

    def __init__(self, cache_dir: str, semantic_threshold: float, embed_model_name: str):
        """Charge le modèle d'embedding et ouvre la base Qdrant locale dans cache_dir."""
        if self._initialized:
            return
        from qdrant_client import QdrantClient
        from sentence_transformers import SentenceTransformer

        self._threshold = semantic_threshold
        logger.info(f"Chargement du modèle d'embedding LLM cache : {embed_model_name}")
        self._model = SentenceTransformer(embed_model_name)
        self._embed_lock = threading.Lock()
        # Le QdrantClient en mode embarqué (path=...) n'est PAS thread-safe :
        # des query_points/upsert concurrents (lancés via asyncio.to_thread)
        # corrompent l'index ("operands could not be broadcast", erreurs SQLite).
        # Ce verrou sérialise toutes les opérations sur la base.
        self._db_lock = threading.Lock()
        self._consecutive_errors = 0
        self._empty_vector: Optional[list] = None
        # Agents ayant au moins une décision « mémoire vide » en cache — renseigné par
        # log_coverage(). Sert à classer un miss no_candidates : agent absent (trou de
        # couverture) vs agent présent mais clé différente (météo/créneau/state_hash).
        self._exact_agents: set[str] = set()
        self._miss_diag_budget = 30  # nb de miss no_candidates détaillés au log (borné)
        self._client = QdrantClient(path=cache_dir)
        self._ensure_collection()
        self._initialized = True
        logger.info(f"LlmSemanticCache initialisé — répertoire: {cache_dir}, seuil: {semantic_threshold}")
        self.log_coverage()

    def log_coverage(self) -> None:
        """Relève la couverture du cache persistant au démarrage et l'expose (log + métriques).

        Répond à « le cache est-il assez peuplé pour servir l'init à 100% ? » sans avoir à
        rejouer un run : combien de points, combien exploitables par le bootstrap (chemin
        « mémoire vide »), combien d'agents couverts, et combien de points hérités d'un
        schéma obsolète (weekday manquant) donc jamais servis par le filtre courant.
        """
        try:
            total = 0
            exact = 0            # memory_empty=True → chemin bootstrap
            stale = 0            # weekday manquant → jamais matché par le filtre courant
            agents: set[str] = set()
            offset = None
            with self._db_lock:
                while True:
                    pts, offset = self._client.scroll(
                        collection_name=COLLECTION_NAME,
                        limit=4000,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False,
                    )
                    for p in pts:
                        pl = p.payload or {}
                        total += 1
                        if pl.get("weekday") is None:
                            stale += 1
                        if pl.get("memory_empty"):
                            exact += 1
                            aid = pl.get("agent_id")
                            if aid:
                                agents.add(str(aid))
                    if offset is None:
                        break
            self._exact_agents = agents
            LLM_CACHE_POINTS_TOTAL.set(total)
            LLM_CACHE_POINTS_EXACT.set(exact)
            LLM_CACHE_POINTS_STALE.set(stale)
            LLM_CACHE_AGENTS_COVERED.set(len(agents))
            logger.info(
                f"[cache] couverture LLM au démarrage : {total} points "
                f"({exact} exact/bootstrap, {len(agents)} agents couverts, {stale} obsolètes weekday=None)"
            )
            if total and stale / total > 0.3:
                fire_alarme("cache_llm_stale")
                logger.warning(
                    f"[ALARME] Cache LLM : {stale}/{total} points ({100*stale//total}%) sont hérités d'un "
                    f"schéma obsolète (weekday=None) et ne seront JAMAIS servis par le filtre courant. "
                    f"Ils gonflent la base sans améliorer le hit rate — envisager de repurger/repeupler le cache."
                )
        except Exception as e:
            logger.warning(f"[cache] log_coverage a échoué (non bloquant) : {e}")

    def _ensure_collection(self):
        """Crée la collection Qdrant si elle n'existe pas encore."""
        from qdrant_client.models import Distance, VectorParams

        existing = {c.name for c in self._client.get_collections().collections}
        if COLLECTION_NAME not in existing:
            self._client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )

    _ERROR_ALARM_THRESHOLD = 5

    def _record_db_error(self, operation: str, error: Exception) -> None:
        """Trace une erreur Qdrant et lève une alarme après N erreurs consécutives (base corrompue ?)."""
        self._consecutive_errors += 1
        if self._consecutive_errors == self._ERROR_ALARM_THRESHOLD:
            fire_alarme("cache_llm_qdrant")
            logger.error(
                f"[ALARME] Cache LLM : {self._consecutive_errors} erreurs consécutives "
                f"(dernière : {operation} → {error}) — base Qdrant probablement corrompue, "
                f"le cache ne sert plus aucune décision. Supprimer le répertoire de cache et relancer."
            )

    def _record_db_ok(self) -> None:
        self._consecutive_errors = 0

    @staticmethod
    def _make_state_hash(options: list, weather: Optional[dict] = None, extra_key: str = "",
                         traits_key: str = "") -> str:
        """Hash SHA-256 des codes d'options triés + météo + version des données.

        ⚠ La version des données d'itinéraire (``terminal_time.data_version()``)
        est INDISPENSABLE ici, et c'est le piège le plus discret du ticket 013 :
        ``get_code()`` est fait de routes et d'arrêts, donc **insensible aux
        durées** par construction. Sans version, un run rejouerait tranquillement
        des décisions prises sur des options où la voiture était plus rapide
        qu'elle ne l'est — sans qu'aucun log ne le signale, puisque de son point
        de vue le contexte de décision est identique.

        ``traits_key`` (2026-08-27) : signature des traits du persona. **Troisième
        occurrence du même piège**, et celle qui a coûté un vidage manuel de cache. Les
        traits qui ne conditionnent pas l'offre — l'abonnement TC au premier chef —
        n'apparaissent NI dans les codes d'options NI dans la météo : ils ne changent que
        le texte du prompt (cf. ``_pt_subscription_note``). Sans cette signature, corriger
        l'abonnement de 352 agents laissait leurs décisions déjà en cache être resservies
        sous l'ancien prompt, sans qu'aucun log ne le signale. Le permis, lui, passe par
        ``_can_drive`` et déplace donc les codes d'options : il s'auto-invalidait déjà.

        ``extra_key`` (ticket 014) : signature du contexte d'anticipation injecté
        dans le prompt (météo du jour, agenda restant, position des véhicules).
        Même piège que ci-dessus : ce contexte n'apparaît ni dans les codes
        d'options ni dans la météo du moment — sans lui, deux agendas différents
        se serviraient mutuellement leurs décisions en silence. Vide quand
        l'anticipation est désactivée : le hash ne porte alors que la version des
        données. (Il n'est pour autant pas « celui d'avant » : l'ajout de
        ``data_version`` a déjà rendu inatteignables les points antérieurs au
        ticket 013 — c'est précisément l'effet voulu.)
        """
        from trip_helper.terminal_time import data_version

        codes = sorted(opt.get_code() for opt in options)
        weather_key = ""
        if weather:
            weather_key = f"{weather.get('weather_code','')}|{round(weather.get('temperature', 0))}|{round(weather.get('precip_mm', 0), 1)}"
        raw = (f"{data_version()}|" + json.dumps(codes, ensure_ascii=False)
               + weather_key)
        if extra_key:
            raw += f"|anticipation:{extra_key}"
        if traits_key:
            raw += f"|traits:{traits_key}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _make_time_slice(timestamp: int) -> str:
        """Convertit un timestamp Unix en tranche de 10 minutes (ex: "08:40") pour regrouper les entrées de cache."""
        dt = datetime.fromtimestamp(timestamp)
        minutes = (dt.minute // 10) * 10
        return f"{dt.hour:02d}:{minutes:02d}"

    @staticmethod
    def _make_weekday(timestamp: int) -> str:
        """Catégorie de jour ("Weekday"/"Weekend") : deux jours de même catégorie partagent un contexte."""
        return "Weekend" if datetime.fromtimestamp(timestamp).weekday() >= 5 else "Weekday"

    def _make_filter(
        self,
        agent_id: str,
        activity_id: Optional[str],
        timestamp: int,
        options: list,
        weather: Optional[dict],
        memory_empty: bool,
        extra_key: str = "",
        traits_key: str = "",
    ):
        """Filtre déterministe des conditions factuelles, partagé par les deux branches du cache."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        return Filter(
            must=[
                FieldCondition(key="agent_id", match=MatchValue(value=str(agent_id))),
                FieldCondition(key="activity_id", match=MatchValue(value=str(activity_id or ""))),
                FieldCondition(key="weekday", match=MatchValue(value=self._make_weekday(timestamp))),
                FieldCondition(key="time_slice", match=MatchValue(value=self._make_time_slice(timestamp))),
                FieldCondition(key="state_hash", match=MatchValue(value=self._make_state_hash(options, weather, extra_key, traits_key))),
                FieldCondition(key="memory_empty", match=MatchValue(value=memory_empty)),
            ]
        )

    def _embed(self, text: str) -> list:
        """Encode le texte en vecteur via le sentence-transformer et enregistre la latence."""
        t0 = time.perf_counter()
        with self._embed_lock:
            vec = self._model.encode(text).tolist()
        LLM_CACHE_EMBED_SECONDS.observe(time.perf_counter() - t0)
        return vec

    # Nombre de doublons rapatriés pour départager par `stored_at` : un même contexte
    # peut avoir été écrit plusieurs fois (upsert par UUID) au fil des runs.
    _LOOKUP_SCROLL_LIMIT = 8

    def _lookup_exact_sync(
        self,
        agent_id: str,
        activity_id: Optional[str],
        timestamp: int,
        options: list,
        weather: Optional[dict],
        extra_key: str = "",
        traits_key: str = "",
    ) -> tuple[Optional[dict], Optional[str]]:
        """Branche « mémoire vide » : correspondance exacte sur les conditions factuelles.

        Sans souvenir, deux décisions prises dans les mêmes conditions sont identiques :
        le filtre déterministe suffit. Simple `scroll` clé-valeur — aucun embedding.
        """
        filt = self._make_filter(agent_id, activity_id, timestamp, options, weather, memory_empty=True, extra_key=extra_key, traits_key=traits_key)
        with self._db_lock:
            candidates, _ = self._client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=filt,
                limit=self._LOOKUP_SCROLL_LIMIT,
                with_payload=True,
                with_vectors=False,
            )

        if not candidates:
            return None, "no_candidates"

        # `scroll` ne garantit pas l'ordre : on retient la décision la plus récente.
        best = max(candidates, key=lambda p: (p.payload or {}).get("stored_at") or 0)
        payload = best.payload or {}
        return {
            "chosen_plan_code": payload.get("chosen_plan_code"),
            "probabilities": payload.get("probabilities"),
            "mode": payload.get("mode", ""),
            "score": None,
        }, None

    def _lookup_semantic_sync(
        self,
        agent_id: str,
        activity_id: Optional[str],
        timestamp: int,
        options: list,
        memory_text: str,
        weather: Optional[dict],
        extra_key: str = "",
        traits_key: str = "",
    ) -> tuple[Optional[dict], Optional[str]]:
        """Branche « mémoire remplie » : similarité sémantique sur la LTM, à conditions égales.

        Le vécu de l'agent influence sa décision : on n'accepte la décision en cache que si
        la LTM courante est proche de celle qui l'avait produite (similarité ≥ seuil).
        """
        filt = self._make_filter(agent_id, activity_id, timestamp, options, weather, memory_empty=False, extra_key=extra_key, traits_key=traits_key)
        query_vector = self._embed(memory_text)
        with self._db_lock:
            candidates = self._client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
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
            "probabilities": payload.get("probabilities"),
            "mode": payload.get("mode", ""),
            "score": best.score,
        }, None

    def _empty_memory_vector(self) -> list:
        """Vecteur neutre des points « mémoire vide » : ces points sont lus par `scroll`
        (filtre seul), jamais par similarité — mais Qdrant exige un vecteur à l'insertion."""
        if self._empty_vector is None:
            self._empty_vector = [0.0] * (VECTOR_SIZE - 1) + [1.0]
        return self._empty_vector

    def _store_sync(
        self,
        agent_id: str,
        activity_id: Optional[str],
        timestamp: int,
        options: list,
        memory_text: Optional[str],
        chosen_plan_code: str,
        mode: str,
        weather: Optional[dict],
        probabilities: Optional[list[float]] = None,
        extra_key: str = "",
        traits_key: str = "",
    ):
        """Insère (upsert) un point Qdrant avec les métadonnées de la décision.

        `memory_text=None` signale une décision prise sans souvenir : le point est marqué
        `memory_empty=True` et porte un vecteur neutre (il ne sera relu que par filtre).

        `probabilities` (aligné sur `options`) est la distribution produite par le LLM :
        c'est elle qui est rejouée à chaque hit — la décision cachée n'est pas figée,
        elle est retirée au sort. `chosen_plan_code`/`mode` conservent le tirage d'origine
        (diagnostic, et relecture par les lecteurs antérieurs à la bascule).
        """
        from qdrant_client.models import PointStruct
        from datetime import datetime as _dt

        state_hash = self._make_state_hash(options, weather, extra_key, traits_key)
        time_slice = self._make_time_slice(timestamp)
        dt = _dt.fromtimestamp(timestamp)

        trajectories = [
            {"code": opt.get_code(), "mode": opt.mode_label(), "duration_ms": opt.duration or 0}
            for opt in options
        ]

        # Distribution persistée par code de plan : au relecture, les options peuvent
        # avoir changé (itinéraire disparu) — l'appariement se fait sur le code, pas
        # sur la position.
        probability_payload = None
        if probabilities is not None:
            probability_payload = [
                {"code": traj["code"], "mode": traj["mode"], "p": float(p)}
                for traj, p in zip(trajectories, probabilities)
            ]

        memory_empty = memory_text is None
        vector = self._empty_memory_vector() if memory_empty else self._embed(memory_text)

        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "agent_id": str(agent_id),
                "activity_id": str(activity_id or ""),
                "weekday": self._make_weekday(timestamp),
                "time_slice": time_slice,
                "state_hash": state_hash,
                "memory_empty": memory_empty,
                "day": dt.day,
                "month": dt.month,
                "temperature": weather.get("temperature") if weather else None,
                "weather_code": weather.get("weather_code") if weather else None,
                "weather_label": weather.get("weather_label") if weather else None,
                "precip_mm": weather.get("precip_mm") if weather else None,
                "trajectories": trajectories,
                "probabilities": probability_payload,
                "chosen_plan_code": chosen_plan_code,
                "mode": mode,
                "stored_at": time.time(),
            },
        )
        with self._db_lock:
            self._client.upsert(collection_name=COLLECTION_NAME, points=[point])

    @staticmethod
    def _redraw_from_cached(
        cached_probabilities: list,
        options: list,
        seed_parts: tuple,
    ) -> Optional[dict]:
        """Rejoue un tirage sur la distribution cachée, restreinte aux options actuelles.

        Un hit ne rend pas une décision figée : la distribution est retirée au sort à
        chaque fois, avec une graine dérivée du contexte (agent, activité, jour) — le
        même agent peut donc prendre sa voiture un jour et le bus le lendemain sans
        appel LLM, tout en gardant un run rejouable à l'identique.

        Les options disparues depuis l'écriture sont écartées et la masse restante est
        renormalisée par le tirage. Renvoie None s'il ne reste rien de tirable (le
        cache est alors considéré comme un miss → nouvel appel LLM).
        """
        p_by_code = {}
        for entry in cached_probabilities or ():
            code = (entry or {}).get("code")
            if code is None:
                continue
            try:
                p_by_code[code] = max(0.0, float(entry.get("p") or 0.0))
            except (TypeError, ValueError):
                continue

        weights = [p_by_code.get(opt.get_code(), 0.0) for opt in options]
        if sum(weights) <= 0:
            return None

        index = draw_index(weights, *seed_parts)
        modes = [opt.mode_label() for opt in options]
        return {
            "index": index,
            "mode": modes[index],
            "weights": weights,
            "distribution": mode_distribution(
                [w / sum(weights) for w in weights], modes
            ),
        }

    async def lookup(
        self,
        agent_id: str,
        activity_id: Optional[str],
        timestamp: int,
        options: list,
        memory_text: Optional[str] = None,
        weather: Optional[dict] = None,
        activity_purpose: str = "",
        seed_parts: tuple = (),
        extra_key: str = "",
        traits_key: str = "",
    ) -> Optional[dict]:
        """
        Recherche hybride dans le cache. Retourne un dict {index, mode, score} sur hit,
        None sur miss. L'index correspond à la position dans `options` tel que fourni.

        `memory_text=None` (mémoire long terme vide) → correspondance exacte sur les
        conditions factuelles, sans embedding. Sinon → recherche par similarité sémantique
        sur la LTM, à conditions factuelles égales, avec rejet sous le seuil de confiance.

        Sur hit, un point porteur d'une distribution de probabilités est **retiré au
        sort** (cf. `_redraw_from_cached`), `seed_parts` fournissant la graine du tirage.
        Les points antérieurs à la bascule (décision figée) rendent leur option d'origine.
        """
        global _LLM_CACHE_HITS, _LLM_CACHE_LOOKUPS
        _LLM_CACHE_LOOKUPS += 1
        t0 = time.perf_counter()
        try:
            if memory_text is None:
                result, miss_reason = await asyncio.to_thread(
                    self._lookup_exact_sync, agent_id, activity_id, timestamp, options, weather, extra_key,
                    traits_key
                )
            else:
                result, miss_reason = await asyncio.to_thread(
                    self._lookup_semantic_sync, agent_id, activity_id, timestamp, options, memory_text, weather, extra_key,
                    traits_key
                )
        except Exception as e:
            logger.warning(f"LLM cache lookup error: {e}")
            LLM_CACHE_MISSES.labels(reason="lookup_error").inc()
            _record_llm_miss("lookup_error")
            self._record_db_error("lookup", e)
            return None
        finally:
            LLM_CACHE_LOOKUP_SECONDS.observe(time.perf_counter() - t0)
        self._record_db_ok()

        if result is None:
            LLM_CACHE_MISSES.labels(reason=miss_reason).inc()
            _record_llm_miss(miss_reason or "unknown")
            # Diagnostic borné des miss « exact » (chemin bootstrap) : distingue un trou de
            # couverture (agent jamais stocké) d'une clé qui diffère (météo/créneau/state_hash).
            if miss_reason == "no_candidates" and memory_text is None and self._miss_diag_budget > 0:
                self._miss_diag_budget -= 1
                agent_known = str(agent_id) in self._exact_agents
                cause = "clé différente (météo/créneau/state_hash) — agent présent en cache" if agent_known \
                    else "agent ABSENT du cache — trou de couverture (jamais stocké)"
                logger.info(
                    f"[cache] miss exact no_candidates — agent={agent_id} act={activity_id} "
                    f"weekday={self._make_weekday(timestamp)} slice={self._make_time_slice(timestamp)} "
                    f"state_hash={self._make_state_hash(options, weather, extra_key, traits_key)[:12]} → {cause}"
                )
            return None

        # Point porteur d'une distribution : nouveau tirage à chaque hit.
        if result.get("probabilities"):
            drawn = self._redraw_from_cached(result["probabilities"], options, seed_parts)
            if drawn is not None:
                LLM_CACHE_HITS.labels(activity_purpose=activity_purpose).inc()
                _LLM_CACHE_HITS += 1
                return {**drawn, "score": result.get("score")}
            # Plus aucune option cachée ne survit dans la liste courante.
            LLM_CACHE_MISSES.labels(reason="code_not_in_options").inc()
            _record_llm_miss("code_not_in_options")
            return None

        chosen_code = result.get("chosen_plan_code")
        if not chosen_code:
            LLM_CACHE_MISSES.labels(reason="no_candidates").inc()
            _record_llm_miss("no_candidates")
            return None

        # Point hérité (décision figée) : on rend l'option d'origine, sans tirage.
        for i, opt in enumerate(options):
            if opt.get_code() == chosen_code:
                LLM_CACHE_HITS.labels(activity_purpose=activity_purpose).inc()
                _LLM_CACHE_HITS += 1
                return {"index": i, "mode": result["mode"], "score": result.get("score")}

        # Le code était en cache mais n'existe plus dans les options courantes (itinéraire modifié)
        LLM_CACHE_MISSES.labels(reason="code_not_in_options").inc()
        _record_llm_miss("code_not_in_options")
        return None

    async def store(
        self,
        agent_id: str,
        activity_id: Optional[str],
        timestamp: int,
        options: list,
        memory_text: Optional[str],
        chosen_plan_code: str,
        mode: str,
        weather: Optional[dict] = None,
        probabilities: Optional[list[float]] = None,
        extra_key: str = "",
        traits_key: str = "",
    ):
        """Wrapper async de _store_sync : persiste la décision dans Qdrant et enregistre la latence d'écriture.

        `memory_text=None` → décision prise sans souvenir (point `memory_empty=True`).
        `probabilities` (aligné sur `options`) → distribution rejouée à chaque hit.
        `extra_key` → signature d'anticipation, intégrée au `state_hash` (ticket 014).
        """
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
                probabilities,
                extra_key,
                traits_key,
            )
        except Exception as e:
            logger.warning(f"LLM cache store error: {e}")
            self._record_db_error("store", e)
        else:
            self._record_db_ok()
            # Tenir à jour l'ensemble des agents couverts (chemin exact) pour la classification des miss.
            if memory_text is None:
                self._exact_agents.add(str(agent_id))
        finally:
            LLM_CACHE_INSERT_SECONDS.observe(time.perf_counter() - t0)
