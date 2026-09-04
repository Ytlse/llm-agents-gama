
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional
import shutil
from loguru import logger
from pydantic import BaseModel, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

import yaml

base_dir = os.path.dirname(os.path.abspath(__file__))


def _resolve_experiments_dir(package_dir: Path) -> Path:
    """Répertoire `experiments/` du dépôt, vu depuis l'hôte comme depuis un conteneur.

    Le conteneur monte `./experiments` sur `/app/experiments`, à côté du code
    (`/app`) : `package_dir / "experiments"` est alors la bonne réponse. Sur
    l'hôte, le code vit dans `<dépôt>/llm-agents/` et les expériences dans
    `<dépôt>/experiments/` — un niveau plus haut. Prendre `package_dir` sans
    distinguer les deux cas fabriquait un `llm-agents/experiments/` parallèle,
    dont les chemins ne se résolvaient pas depuis `GAMA/CityTransport/`.

    `APP_EXPERIMENTS_DIR` court-circuite la détection si besoin.
    """
    override = os.environ.get("APP_EXPERIMENTS_DIR", "").strip()
    if override:
        return Path(override)
    parent_candidate = package_dir.parent / "experiments"
    if parent_candidate.is_dir():
        return parent_candidate
    return package_dir / "experiments"


def _run_artifacts_disabled() -> bool:
    """Vrai quand importer ce module ne doit créer aucun artefact de run.

    Une suite de tests qui importe `settings` créait un répertoire de run et
    repointait le symlink `GAMA/CityTransport/results` — volant sa sortie à la
    simulation en cours. Un import de test observe la configuration, il
    n'ouvre pas un run.
    """
    if os.environ.get("APP_NO_RUN_ARTIFACTS", "").strip().lower() in ("1", "true", "yes"):
        return True
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    import sys

    if "pytest" in sys.modules:
        return True
    # `python -m unittest` : détecté par la ligne de commande, pas par
    # sys.modules — une dépendance quelconque peut importer `unittest`.
    argv0 = os.path.basename(sys.argv[0] or "")
    return argv0 in ("pytest", "unittest") or argv0.startswith("pytest")


def merge_configs(*config_paths: str) -> Dict[str, Any]:
    """Merge multiple YAML files, with later files overriding earlier ones."""
    merged_config = {}
    
    for path in config_paths:
        if Path(path).exists():
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
                if config:
                    merged_config = deep_merge(merged_config, config)
    
    return merged_config

def deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


class WorkdirPathResolutionMixin:
    """Mixin to handle path resolution in nested models."""
    
    # Define path fields at class level
    _in_workdir_path_fields: ClassVar[List[str]] = []
    
    def resolve_paths(self, workdir: Path):
        """Resolve relative paths to absolute paths."""
        for field_name in self._in_workdir_path_fields:
            if hasattr(self, field_name):
                value = getattr(self, field_name)
                if value is not None and not Path(value).is_absolute():
                    resolved_path = workdir / value
                    setattr(self, field_name, str(resolved_path))


def _find_providers_yaml() -> Optional[Path]:
    """Cherche providers.yaml dans les emplacements standards et retourne le premier trouvé."""
    candidates = [
        Path(base_dir) / ".." / "llm_module" / "config" / "providers.yaml",
        Path("/opt/llm_module/config/providers.yaml"),
    ]
    for p in candidates:
        if p.exists():
            return p.resolve()
    return None


class ProviderConfig(BaseModel):
    api_key:           SecretStr = SecretStr("")
    rpm_limit:         int
    base_url:          str
    default_model:     str
    weight:            float = 1.0
    batch_max_agents:  int   = 5
    concurrency_limit: int   = 2
    disable_timeout:   int   = 180
    adapter:           str   = ""


class LlmConfig(BaseSettings, WorkdirPathResolutionMixin):
    model_config = SettingsConfigDict(env_nested_delimiter='__')

    redis_url:                 str   = "redis://localhost:6379/0"
    celery_broker_url:         str   = "redis://localhost:6379/1"
    celery_result_backend:     str   = "redis://localhost:6379/2"
    circuit_breaker_threshold: float = 0.95
    max_retries:               int   = 50
    backoff_base_seconds:      float = 1.0
    # Cooldown court du provider fautif lors d'un basculement (parse error / 4xx) :
    # force la rotation à choisir un autre modèle au réessai (cf. worker/task_worker).
    provider_switch_cooldown_seconds: int = 30
    batch_max_agents:          int   = 5
    batch_delay_seconds:       float = 3.0  # miroir de llm_module.config (fenêtre d'accumulation du micro-batching)

    # Clés API lues depuis l'env : PROVIDER_KEYS__groq=gsk-...
    provider_keys: Dict[str, SecretStr] = {}

    # Construit après validation depuis providers.yaml + provider_keys
    providers: Dict[str, ProviderConfig] = {}

    @model_validator(mode="after")
    def build_providers(self) -> "LlmConfig":
        """Fusionne les entrées de providers.yaml avec les clés API issues de l'env pour construire les ProviderConfig."""
        yaml_path = _find_providers_yaml()
        if yaml_path is None:
            return self
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)
        defaults = data.get("providers", {})
        result = {}
        for name, entry in defaults.items():
            adapter_name = entry.get("adapter", name)
            key = self.provider_keys.get(name) or self.provider_keys.get(adapter_name, SecretStr(""))
            result[name] = ProviderConfig(api_key=key, **entry)
        self.providers = result
        return self


class ServerConfig(BaseSettings, WorkdirPathResolutionMixin):
    # HTTP settings
    http_host: str = "localhost"
    http_port: int = 8002

    # GAMA websocket settings
    gama_ws_url: str = "ws://localhost:3001"


class WorldConfig(BaseSettings, WorkdirPathResolutionMixin):
    # General settings
    geo_crs: str = "EPSG:4326"
    geo_projection: str = "EPSG:3857"
    # Grid settings
    grid_size: int = 1000 # 1km
    time_step: int = 900 # 15 minutes
    # Dynamic throttling: min_interval = cap * min(1, n / population)^k
    # where n = itineraries in progress (backlog). Threshold relative to the
    # population so the cap is always reachable (n can never exceed population).
    # k   : convexity exponent (>1 — higher = later and steeper braking).
    #       With k=1.5, cap=30: ~1s at 10%, ~2.7s at 20%, ~5s at 30%, ~7.6s at 40%,
    #       ~10.6s at 50%, ~21.5s at 80% (where drain mode takes over and holds at
    #       cap until the backlog is back below drain_release_ratio), 30s at 100%.
    # cap : hard ceiling in seconds (keeps delay below GAMA's HTTP read timeout).
    min_internal_coeff_k: float = 1.5
    min_internal_coeff_cap: float = 30.0
    # Drain mode (hysteresis on top of the progressive brake): once the backlog
    # reaches drain_trigger_ratio of the population, every /sync response is held
    # up to `cap` seconds (GAMA's HTTP read timeout is the hard limit per response)
    # until the backlog falls back below drain_release_ratio — i.e. the pile must
    # be ~80% drained (release=0.2) before control returns to GAMA at full speed.
    # The backlog alarm ([ALARME]) fires/clears on the same thresholds.
    # drain_trigger_ratio <= 0 disables the mechanism.
    drain_trigger_ratio: float = 0.8
    drain_release_ratio: float = 0.2
    # Backlog re-sampling period (seconds) while holding a /sync response in drain mode.
    drain_poll_interval: float = 1.0
    # Number of concurrent Worker coroutines consuming the activity queue.
    # Each worker independently picks items from the same asyncio.Queue, so up to
    # worker_concurrency LLM+OTP computations run in parallel (matching the old
    # fire-and-forget asyncio.create_task approach).
    worker_concurrency: int = 8

    # Concurrence du bootstrap (/init) : au démarrage, ~N agents lancent leur premier
    # itinéraire quasi simultanément. Sans plafond, cette rafale sature les quotas
    # RPM/TPM des providers et déclenche une cascade de 429/5xx → fallbacks massifs.
    # Ce sémaphore borne les pipelines OTP+LLM en vol et étale la charge en vagues.
    bootstrap_concurrency: int = 30

    # --- Ticket 003 : ordonnancement EDF et contre-pression prédictive ---
    # Dispatcher EDF (Earliest Deadline First) : les tâches de planification sont
    # servies par échéance croissante (heure de départ simulée) via une file de
    # priorité consommée par worker_concurrency tâches, au lieu du sémaphore FIFO.
    # false = comportement historique (spawn direct + sémaphore, ordre d'arrivée).
    edf_enabled: bool = True
    # Contre-pression prédictive : ne retenir le /sync que si le temps estimé de
    # résolution de la file menace une échéance (test de faisabilité EDF), au lieu
    # du frein progressif cap·ratio^k. false = frein progressif historique.
    # Le mode drainage à hystérésis (drain_*) reste le filet de sécurité ultime.
    predictive_backpressure_enabled: bool = True
    # Constante de temps (s) de l'EWMA du débit de complétion D (tâches/s).
    # Assez court pour réagir à un effondrement de quota provider (par minute).
    throughput_ewma_tau_s: float = 90.0
    # Plancher de D (tâches/s) : évite un T_estimé = ∞ quand aucune complétion récente.
    throughput_floor_per_s: float = 0.05
    # Marge multiplicative du test de faisabilité EDF : rétention si T_k·marge > slack_k.
    predictive_margin: float = 1.4
    # Rétention prédictive cumulée (s) sur un /sync au-delà de laquelle GAMA est
    # notifié du régime dégradé (topic system/throttle, front montant).
    throttle_notify_threshold_s: float = 5.0
    # Période (s) de rafraîchissement du message system/throttle tant que le régime
    # dégradé persiste (évite le spam à chaque /sync).
    throttle_notify_refresh_s: float = 30.0

    # Cockpit : un agent est "bloqué" s'il n'a obtenu aucune planification réussie
    # depuis plus que ce nombre d'heures de temps SIMULÉ (métrique controller_agents_stuck).
    stuck_agent_threshold_hours: float = 20.0

    # Watchdog arrivées perdues : un agent "en déplacement" dont l'arrivée attendue
    # (expected_arrive_at du move poussé) est dépassée de plus que cette marge (heures
    # de temps SIMULÉ) est considéré perdu (move jamais reçu par GAMA, ex. coupure
    # WebSocket) : [ALARME] + reprise forcée du cycle par le scan de fallback.
    # 0 désactive le watchdog. La marge doit rester supérieure aux retards légitimes
    # dans GAMA (attente de véhicule TC, congestion).
    arrival_watchdog_hours: float = 1.0


class GTFSConfig(BaseSettings, WorkdirPathResolutionMixin):
    _in_workdir_path_fields: ClassVar[List[str]] = ["solari_cache_file"]

    mode: str = "SOLARI" # SOLARI or OTP

    # GTFS settings
    gtfs_file: str = os.path.join(base_dir, "../data/gtfs/tisseo_gtfs/")
    # `route_type` GTFS → nom du mode servi à l'agent dans son prompt (« Trajet en
    # Train 12 »). Une clé manquante s'affiche « Unknown » : le TER (route_type=2)
    # entre ici le 2026-09-04 avec le mode `rail` demandé à OTP (ticket 031, q. 16).
    gtfs_modality_name_map: dict[str, str] = {
        "0": "T1/Tram",
        "1": "Metro",
        "2": "Train",
        "3": "Bus",
        "6": "Teleo",
    }

    # RAPTOR provider settings
    solari_endpoint: str = "http://localhost:8000/v1/plan"
    solari_cache_file: str = "raptor_cache.pickle"

    # OTP provider settings
    otp_endpoint: str = "http://localhost:8080/otp/transmodel/v3"
    otp_max_concurrent: int = 30  # max simultaneous get_itineraries calls

    # OSMnx direct routing cache (walk/bike/car graphs, persisted across restarts)
    osmnx_cache_dir: str = "/app/osmnx_cache"
    # Clé du graphe OSMnx servi au runtime (`graphs_<clé>.pkl` / `boundary_<clé>.pkl` dans
    # `osmnx_cache_dir`). Vide → le graphe du polygone des 453 communes
    # (`geography.PERIMETER_CACHE_KEY`, ticket 031 partie 2). La clé du disque historique de
    # 30 km (`geography.PRODUCTION_CACHE_KEY_30KM`) reste acceptée pour un audit ; toute autre
    # clé doit avoir son pickle en cache — rien n'est téléchargé à sa place.
    osmnx_graph_key: Optional[str] = None
    # Active le cache persistant des graphes OSMnx sur disque entre les redémarrages
    # (évite de re-télécharger/reconstruire les graphes ville+distance à chaque démarrage)
    osmnx_cache_enabled: bool = True
    # Répertoire racine du cache persistant ; un sous-dossier par population y est créé
    osmnx_persistent_cache_dir: str = "/app/data/osmnx_cache"

    # number of cached itineraries per grid cell
    n_trip_in_grid: int = 5
    otp_cache_enabled: bool = True
    otp_persistent_cache_dir: str = "/app/data/cache/otp"
    recursion_search_depth: int = 0  # 0 means no recursion, 1 means one level of recursion
    search_window_m: int = 30
    transit_access_egress_modes: list[str] = ["foot"]
    max_trip_candidates: int = 6 # maximum number of trip candidates to be selected
    fixed_day: Optional[str] = None


class DataConfig(BaseSettings, WorkdirPathResolutionMixin):
    _in_workdir_path_fields: ClassVar[List[str]] = ["population_cache_prefix", "state_file"]

    # Agent settings
    population_size: Optional[int] = 1
    population_cache_prefix: str = "./population_"
    # Seed déterministe pour l'échantillonnage aléatoire des agents depuis la sortie
    # eqasim : garantit le même sous-ensemble d'agents (donc les mêmes trajets) d'un run
    # à l'autre → le cache OSMnx est réutilisable au rejeu.
    population_sample_seed: int = 42
    # Population SCELLÉE (article AAMAS, docs/arch/controle-population-jeu-de-test.md) :
    # chemin d'un fichier de population à utiliser tel quel, à la place de la recherche
    # `{eqasim_output_dir}/{prefix}population_{population_size}.json` et de tout appel à
    # eqasim. Le fichier est pris ENTIER : s'il ne compte pas exactement
    # `population_size` agents (après filtre bbox éventuel), le chargement REFUSE plutôt
    # que de ré-échantillonner — un sceau ne se rogne pas en silence.
    population_file: Optional[str] = None
    state_file: str = "./state.json"
    number_of_llm_based_agents: Optional[int] = 0

    # Eqasim settings
    synthetic_file_prefix: str = "toulouse_"
    eqasim_output_dir: str = "/data/eqasim-output"
    generate_personality_traits: bool = False

    # Debug
    debug_people_ids: Optional[list[str]] = None


class AgentConfig(BaseSettings, WorkdirPathResolutionMixin):
    _in_workdir_path_fields: ClassVar[List[str]] = ["long_term_memory_storage_dir", "chat_log_dir"]

    embedding_model: Optional[str] = None
    chat_log_dir: str = "chat_logs"
    long_term_memory_storage_dir: str = "long_term_memory"
    long_term_memory_filter_by_datetime: bool = False
    long_term_memory_enabled: bool = True #surchargé par la valeur GAMA
    long_term_max_entries_query: int = 3
    long_term_max_days_query: int = 30
    # Plafond du cache LRU des métadonnées LTM. Doit rester au-dessus du nombre
    # d'agents : en dessous, chaque décision provoque une éviction (relecture +
    # réécriture disque) puisque les agents sont parcourus en round-robin.
    # Les métadonnées pèsent ~3 Ko/agent, donc 5 000 agents ≈ 15 Mo en mémoire.
    long_term_max_loaded_metadata: int = 5000
    long_term_reflect_interval: int = 6 * 3600  # 6 hours (legacy — non utilisé si stm_reflection_min_entries > 0)
    stm_reflection_min_entries: int = 10        # déclenche la réflexion STM dès que N entrées accumulées
    # Échéance FALLBACK (temps SIMULÉ) d'une réflexion STM, utilisée seulement si
    # l'agent n'a aucune activité horodatée. Depuis le ticket 010, l'échéance EDF
    # normale est le RÉVEIL de l'agent (première activité planifiée du jour
    # suivant) : les décisions du soir passent devant et le stock se draine
    # pendant la nuit simulée. L'échéance est conservée entre les retentatives
    # (échec gateway → re-soumission au sync suivant, même deadline).
    stm_reflection_deadline_sim_s: int = 12 * 3600

    long_term_retrieval__sim_weight: float = 0.4
    long_term_retrieval__keyword_weight: float = 0.3
    long_term_retrieval__time_weight: float = 0.3
    long_term_retrieval__default_reflection_importance_score: float = 0.2
    long_term_retrieval__time_decay: float = 0.7

    long_term_self_reflect_enabled: bool = True #surchargé par la valeur GAMA
    long_term_self_reflect_interval_days: int = 3
    long_term_self_reflect_window_days: int = 5

    # Le LLM ne choisit plus un itinéraire : il attribue une probabilité à chaque
    # option, et le mode effectif est tiré au sort dans cette distribution (y compris
    # à chaque relecture du cache sémantique). La graine du tirage est dérivée de
    # (cette valeur, agent, activité, jour simulé) : à graine égale, un run rejoué
    # reproduit exactement les mêmes trajets ; la changer explore un autre tirage
    # sans réappeler le LLM.
    mode_draw_seed: int = 42

    # ── Une date météo par agent (ticket 023, suite) ───────────────────────────
    # Sur une seule journée simulée, tous les agents partagent une seule météo :
    # le régresseur a une variance nulle, et « aucun effet mesuré » ne veut alors
    # rien dire. Activé, chaque agent lit le bulletin d'un jour de l'année tiré
    # déterministement depuis son identifiant — seule la DATE du bulletin change,
    # l'heure du départ est conservée, et l'offre de transport reste celle de la
    # journée simulée. Dispositif ceteris paribus : la graine du tirage de mode,
    # elle, n'est pas touchée.
    # DÉSACTIVÉ PAR DÉFAUT : rien ne bouge sans intention explicite.
    weather_per_agent_dates: bool = False
    # "enquete" lit la fenêtre de collecte EMC² et ses jours enquêtés depuis
    # llm_module.core.population_reference (pas de bornes recopiées) ; "annee"
    # prend les 365 jours ; sinon un couple ["AAAA-MM-JJ", "AAAA-MM-JJ"].
    weather_window: Any = "enquete"
    # L'enquête ne porte que des jours ouvrés ; sans effet si la fenêtre est
    # "annee" et ce drapeau est faux.
    weather_weekdays_only: bool = True
    weather_draw_seed: int = 42

    llm_params: dict[str, Any] = {
        "temperature": 0,
        "top_p": 1.0,
        "max_tokens": 4096,
    }
    llm_retry_count: int = 3
    llm_retry_delay: int = 5  # seconds

    # Scheduler settings
    reschedule_activity__version: int = 2
    reschedule_activity_departure_time: bool = True
    reschedule_transition_ratio: float = 0.75
    reschedule_activity_v2__k: float = 0.02
    max_reschedule_amount: int = 3600  # 1 hour
    pre_schedule_duration: int = 0

    # Aucun déplacement ne démarre le week-end : un départ tombant un samedi ou un
    # dimanche est reporté au lundi suivant à la même heure.
    no_weekend_departures: bool = True

    # --- Anticipation de la chaîne de la journée (ticket 014) ---
    # Le bloc persona du prompt de choix modal est enrichi de trois éléments :
    # la météo des tranches restantes de la journée (tous les agents), l'agenda
    # glissant des trajets restants et la position des véhicules personnels
    # (uniquement les agents qui ont quelque chose à chaîner : conducteurs avec
    # voiture, possesseurs de vélo — jamais les passagers). Le choix reste trajet
    # par trajet ; les verrous de chaîne restent le filet de sécurité.
    # False rétablit le prompt myope, pour l'A/B contre un run de référence.
    agenda_anticipation_enabled: bool = True

    # --- Cohérence de chaîne des véhicules personnels (vélo, voiture) ---
    # Un véhicule est un lieu : il reste garé où l'agent l'a laissé, n'est proposé comme
    # mode que depuis cette position, et est ramené au domicile en fin de boucle.
    # False rétablit le comportement historique (possession = disponibilité partout),
    # utile pour mesurer l'effet du correctif sur les parts modales à population égale.
    vehicle_chain_enabled: bool = True
    # Verrou de retour : un trajet vers le domicile au départ d'un lieu où un véhicule est
    # garé est restreint aux itinéraires de ce mode (l'agent ramène son vélo / sa voiture).
    vehicle_return_home_lock: bool = True
    # Rattrapage des véhicules laissés à une étape intermédiaire : ramenés au domicile
    # quand l'agent y rentre. Sans lui, un agent perd sa voiture pour tous les jours suivants.
    vehicle_orphan_reset_at_home: bool = True
    # Alarme [ALARME] si la part des retours au domicile laissant un véhicule orphelin
    # dépasse ce ratio (sur au moins N retours observés, pour éviter le bruit de démarrage).
    vehicle_orphan_alarm_ratio: float = 0.05
    vehicle_orphan_alarm_min_returns: int = 200

    quantify_time_window: bool = True
    reflection_custom_guidelines: Optional[str] = None

    # Remote LLM settings
    # 120s laisse au worker le temps d'absorber un cooldown 5xx (120s) + backoff et de
    # basculer sur un autre provider AVANT que le client abandonne (sinon fallback).
    remote_llm_poll_timeout: float = 120.0  # timeout (secondes) d'une tâche LLM
    stm_reflection_min_tpm: Optional[int] = 30000  # exclut les providers sous ce seuil TPM pour la STM reflection
    # Backpressure : quand le client SDK lève l'alarme (N échecs consécutifs), il
    # bloque les nouvelles soumissions jusqu'à ce que la pile in-flight retombe
    # sous ce ratio de worker_concurrency (0.2 = 20 %). 0 désactive la backpressure.
    remote_llm_backpressure_ratio: float = 0.2
    # Disjoncteur du client gateway : après N échecs consécutifs (pénurie de tokens,
    # gateway/réseau down), les soumissions LLM sont SUSPENDUES : la simulation attend
    # tranquillement le rétablissement (renouvellement des quotas, retour du service)
    # au lieu de brûler des tentatives vouées à l'échec (120 s de timeout chacune) et
    # de dégrader les décisions en index par défaut. Aucune décision n'est prise hors
    # du chemin nominal (cache exact ou LLM) pendant l'attente. Une sonde re-teste le
    # gateway périodiquement ; le premier succès referme le disjoncteur et tout repart
    # automatiquement. 0 désactive le disjoncteur (comportement historique : chaque
    # décision échoue après son timeout et part sur l'index par défaut).
    remote_llm_circuit_failure_threshold: int = 10
    remote_llm_circuit_probe_interval: float = 60.0  # secondes entre deux sondes


class CacheConfig(BaseSettings, WorkdirPathResolutionMixin):
    _in_workdir_path_fields: ClassVar[List[str]] = []

    enabled: bool = True
    cache_dir: str = "/app/data/llm_cache"
    semantic_threshold: float = 0.95
    embed_model_name: str = "all-MiniLM-L6-v2"
    # Mémoïsation exacte des réflexions STM/LTM (ticket 012) : sert la réflexion
    # déjà payée quand le prompt effectif est byte-identique (re-runs déterministes).
    # Correspondance exacte uniquement — jamais de rapprochement inter-agents.
    reflection_memo_enabled: bool = True


class AppConfig(BaseSettings, WorkdirPathResolutionMixin):
    _in_workdir_path_fields: ClassVar[List[str]] = ["agent_memory_events_jsonl", "agent_memory_events_csv", "log_file", "llm_exchanges_file", "llm_cache_hits_file", "pipeline_log_file"]

    # Agent memory events log (STM + LTM observations, reflections, concepts)
    agent_memory_events_jsonl: str = "agent_memory_events.jsonl"
    agent_memory_events_csv: str = "agent_memory_events.csv"

    # LLM exchange log (service, prompt, response, tokens)
    llm_exchanges_file: str = "llm_exchanges.jsonl"

    # LLM cache hit log (décisions servies depuis le cache sémantique → aucun appel LLM,
    # donc absentes de llm_exchanges.jsonl ; nécessaire pour mesurer l'économie de tokens)
    llm_cache_hits_file: str = "llm_cache_hits.jsonl"

    # Application log
    log_file: str = "app.log"
    log_level: str = "INFO"

    # Pipeline timing CSV log (T0 → Fin, LLM agents only)
    pipeline_log_enabled: bool = True
    pipeline_log_file: str = "pipeline_timing.csv"


class Settings(BaseSettings):
    app: AppConfig = AppConfig()
    server: ServerConfig = ServerConfig()
    data: DataConfig = DataConfig()
    world: WorldConfig = WorldConfig()
    gtfs: GTFSConfig = GTFSConfig()
    agent: AgentConfig = AgentConfig()
    llm: LlmConfig = LlmConfig()
    cache: CacheConfig = CacheConfig()

    # Directory settings
    workdir: Path = Path.cwd()

    # @field_validator('workdir', mode='before')
    # @classmethod
    # def resolve_workdir(cls, v):
    #     """Ensure workdir is an absolute Path."""
    #     return Path(v).resolve()
    
    @model_validator(mode='after')
    def resolve_all_paths(self):
        """Résout tous les chemins relatifs des sous-configs par rapport à workdir après validation Pydantic."""
        # This will only be triggered if you instantiate Settings via pydantic's validation process,
        # e.g., Settings(**data), not when you subclass or access attributes directly.
        # If you use Settings.from_yaml_files or FactorySettings, it will be triggered.
        # If you instantiate Settings without validation, it won't.
        for field_name, field_value in self.__dict__.items():
            if isinstance(field_value, WorkdirPathResolutionMixin):
                field_value.resolve_paths(self.workdir)
        return self
    
    def _resolve_nested_paths(self, model_instance: BaseModel, path_fields: list):
        """Resolve paths in a nested model instance."""
        for path_field in path_fields:
            if hasattr(model_instance, path_field):
                current_value = getattr(model_instance, path_field)
                if current_value is not None and not Path(current_value).is_absolute():
                    resolved_path = self.workdir / current_value
                    setattr(model_instance, path_field, str(resolved_path))

    @classmethod
    def from_yaml_files(cls, *yaml_paths: str, workdir: str = None) -> 'Settings':
        """Load and merge multiple YAML files."""
        merged_data = merge_configs(*yaml_paths)
        # Remove workdir from YAML data — it is now derived from the config file name
        merged_data.pop('workdir', None)
        if workdir:
            merged_data['workdir'] = Path(workdir).resolve()
        return cls(**merged_data)


class FactorySettings:
    _instance: Optional[Settings] = None
    _creation_time: Optional[datetime] = None

    @classmethod
    def get(cls) -> Settings:
        """Retourne le singleton Settings, en le créant depuis les fichiers YAML au premier appel."""
        if cls._instance is not None:
            return cls._instance

        # Une seule configuration de run, toujours chargée depuis ce chemin fixe —
        # plus de sélection via APP_CONFIG_PATH/CONFIG=... : pour changer de config,
        # éditer directement llm-agents/config/config.yaml.
        base_config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "config/config.yaml",
        )
        yaml_files = [base_config_path]

        # Le workdir d'expérience (experiments/archive/<YYYY-MM-DD>_<HH_MM>) est
        # créé et archivé inconditionnellement à chaque démarrage.
        now = datetime.now()
        cls._creation_time = now
        experiments_dir = _resolve_experiments_dir(Path(base_config_path).resolve().parent.parent)
        # Reprise à chaud (`make run CONT=1` → CONTINUE_RUN=1) : on réutilise le
        # workdir du run précédent (cible du symlink experiments/current) au lieu
        # d'en créer un nouveau. Les journaux s'y APPENDENT (moves.csv garde son
        # en-tête, app.log continue), state.json et les checkpoints de population
        # y sont retrouvés par les chemins _in_workdir_path_fields. La simulation
        # GAMA, elle, repart à t0 du jour simulé (pas de gel d'état côté GAMA,
        # cf. ticket 002) — les caches rendent le rejeu quasi instantané.
        _resume = os.environ.get("CONTINUE_RUN", "").strip().lower() in ("1", "true", "yes")
        _current_link = experiments_dir / "current"
        if _resume and _current_link.is_symlink() and _current_link.resolve().is_dir():
            workdir = str(_current_link.resolve())
        else:
            if _resume:
                logger.warning(
                    "CONTINUE_RUN demandé mais experiments/current ne pointe vers aucun "
                    "run existant — démarrage d'un run neuf."
                )
            exp_name = f"{now.strftime('%Y-%m-%d')}_{now.strftime('%H_%M')}"
            workdir = str(experiments_dir / "archive" / exp_name)

        cls._instance = Settings.from_yaml_files(*yaml_files, workdir=workdir)

        if _run_artifacts_disabled():
            logger.info(
                "Import sous test : aucun répertoire de run créé, symlinks "
                "experiments/current et GAMA/CityTransport/results laissés en place."
            )
            return cls._instance

        # Create workdir, write the full config into it, and update "current" symlink
        cls._instance.workdir.mkdir(parents=True, exist_ok=True)

        cls.save_static_config()

        current_link = experiments_dir / "current"
        # Plusieurs processus importent ce module dans la même seconde (workers de routage du
        # notebook, workers hypercorn) : unlink puis symlink n'est pas atomique, et le second
        # arrivant tombait sur FileExistsError — trois workers spawnés ensemble, deux morts à
        # l'initialisation, BrokenProcessPool (2026-09-03). Un lien temporaire propre à ce
        # processus, puis os.replace : atomique, et le dernier écrit gagne.
        _tmp_link = experiments_dir / f".current.{os.getpid()}"
        _tmp_link.unlink(missing_ok=True)
        _tmp_link.symlink_to(Path("archive") / cls._instance.workdir.name)
        os.replace(_tmp_link, current_link)

        # Redirect GAMA results into this experiment's workdir.
        gama_results_dir = cls._instance.workdir / "gama_results"
        gama_results_dir.mkdir(parents=True, exist_ok=True)
        gama_results_link = Path(base_dir).parent / "GAMA" / "CityTransport" / "results"
        if gama_results_link.parent.exists():
            # Le lien est écrit ici mais LU ailleurs — par GAMA sur l'hôte, ou par le
            # conteneur `gama` (qui monte ./GAMA sur /GAMA et ./experiments sur
            # /experiments). Sa cible doit donc s'exprimer dans la disposition du
            # dépôt, pas dans celle du contrôleur : depuis GAMA/CityTransport, deux
            # niveaux au-dessus donnent la racine, puis experiments/. Un calcul par
            # `relpath` depuis le workdir du contrôleur (/app/experiments/…) donnerait
            # un lien correct dans ce conteneur seulement, et pendant partout ailleurs.
            within_experiments = os.path.relpath(gama_results_dir, experiments_dir)
            relative_target = Path("../../experiments") / within_experiments
            # Plusieurs workers hypercorn importent ce module en parallèle :
            # unlink/symlink doivent tolérer qu'un autre worker soit passé avant.
            if gama_results_link.is_symlink():
                gama_results_link.unlink(missing_ok=True)
            elif gama_results_link.exists():
                gama_results_link.rename(gama_results_link.parent / "results_legacy")
            try:
                gama_results_link.symlink_to(relative_target)
            except FileExistsError:
                pass
            # Le lien ne se résout pas depuis ce processus (le contrôleur ne voit
            # pas /experiments) : ce qu'on peut vérifier, c'est l'invariant qui
            # l'avait cassé — le workdir doit vivre sous un répertoire nommé
            # `experiments` à la racine du dépôt. Sinon le lien pend, et GAMA échoue
            # sur `save` par une I/O error qui ne nomme pas la cause.
            if experiments_dir.name == "experiments" and not within_experiments.startswith(".."):
                logger.info(
                    f"Sorties GAMA redirigées : {gama_results_link} → {relative_target}"
                )
            else:
                logger.error(
                    f"[ALARME] Symlink de sortie GAMA pendant : {gama_results_link} → "
                    f"{relative_target} ne résoudra aucun répertoire depuis "
                    f"GAMA/CityTransport (workdir : {gama_results_dir}, experiments_dir : "
                    f"{experiments_dir}). GAMA échouera sur `save` en I/O error."
                )

        # logger.info(f"Settings loaded from: {yaml_files}")
        # logger.info(f"All settings: {cls._instance.model_dump_json(indent=2)}")
        return cls._instance
    
    @classmethod
    def save_static_config(cls) -> None:
        """
        Sauvegarde l'état actuel de la configuration dans le fichier static_config.yaml.
        À appeler après que la simulation GAMA ait surchargé les paramètres.
        """
        if cls._instance and cls._instance.workdir and cls._instance.workdir.exists():
            static_config_path = cls._instance.workdir / "static_config.yaml"
            with open(static_config_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    cls._instance.model_dump(mode="json"), 
                    f, 
                    default_flow_style=False, 
                    allow_unicode=True,
                    sort_keys=False
                )
            logger.info(f"Configuration statique mise à jour : {static_config_path}")

    def __getattribute__(self, name):
        """Délègue tous les accès d'attributs au singleton Settings sous-jacent."""
        # Handle special methods and private attributes directly
        if name.startswith('_') or name in ('get', 'force_reload', 'force_reload_paths', 'save_static_config'):
            return super().__getattribute__(name)
        
        # Delegate all other attributes to the Settings instance
        return getattr(self.get(), name)
    
    @classmethod
    def force_reload(cls) -> Settings:
        """Force reload the settings."""
        cls._instance = None
        return cls.get()
    
    @classmethod
    def force_reload_paths(cls) -> Settings:
        """Force le rechargement complet des settings (alias de force_reload)."""
        cls._instance = None
        return cls.get()


settings = FactorySettings()
