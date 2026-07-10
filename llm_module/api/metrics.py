"""
api/metrics.py — Métriques Prometheus côté API.

Le worker Celery n'expose pas de /metrics : ses compteurs sont persistés dans
le hash Redis `wmetrics` (cf. infra/redis/metrics.py) et relus ici par un
collecteur custom — un seul HGETALL par scrape.
"""

from __future__ import annotations
from typing import Optional

from prometheus_client import REGISTRY, Counter
from prometheus_client.metrics_core import CounterMetricFamily, GaugeMetricFamily

from llm_module.api.deps import GatewayDeps
from llm_module.config import load_provider_defaults
from llm_module.telemetry.logger import get_logger

logger = get_logger(__name__)

# Agents reçus depuis GAMA (avant mini-batching)
AGENTS_RECEIVED = Counter(
    'gama_agents_received_total',
    'Total agents reçus depuis GAMA (avant mini-batching)',
    ['category'],
)


def _by_prefix(counters: dict[str, int], prefix: str) -> dict[str, int]:
    """Sous-ensemble des compteurs dont le nom commence par `prefix` (retiré)."""
    return {k[len(prefix):]: v for k, v in counters.items() if k.startswith(prefix)}


class WorkerMetricsCollector:
    """
    Collecteur Prometheus qui lit les compteurs persistants du Worker depuis Redis.
    Expose :
      - llm_provider_calls_ok_total   {provider}  : appels LLM réussis par provider
      - llm_provider_calls_err_total  {provider}  : appels LLM échoués par provider
      - llm_prompts_sent_total        {category}  : prompts LLM envoyés par catégorie
      - llm_agents_batched_total      {category}  : agents batchés par catégorie
      … ainsi que les métriques métier (modes, distances) et l'état des providers.
    """

    def __init__(self, deps: Optional[GatewayDeps] = None) -> None:
        self.deps = deps

    def collect(self):
        if self.deps is None:
            return
        try:
            yield from self._collect()
        except Exception as exc:
            logger.error(f"WorkerMetricsCollector.collect() failed: {exc}")

    def _collect(self):
        deps = self.deps
        settings = deps.settings
        counters = deps.metrics.items()   # un seul HGETALL par scrape

        # ── Appels LLM par provider ──────────────────────────────────────────
        ok_fam  = CounterMetricFamily('llm_provider_calls_ok_total',  'Appels LLM réussis par provider',  labels=['provider'])
        err_fam = CounterMetricFamily('llm_provider_calls_err_total', 'Appels LLM échoués par provider',  labels=['provider'])
        ok_by_provider  = _by_prefix(counters, "llm_calls_ok_total:")
        err_by_provider = _by_prefix(counters, "llm_calls_err_total:")
        # Union : un provider peut avoir des erreurs sans succès (et inversement) ;
        # les providers configurés mais sans appel apparaissent à 0.
        seen = set(ok_by_provider) | set(err_by_provider) | set(settings.providers)
        for provider in seen:
            ok_fam.add_metric([provider], ok_by_provider.get(provider, 0))
            err_fam.add_metric([provider], err_by_provider.get(provider, 0))
        yield ok_fam
        yield err_fam

        # ── Prompts envoyés vs agents batchés (ratio mini-batch) ─────────────
        prompts_fam = CounterMetricFamily('llm_prompts_sent_total',   'Prompts LLM envoyés par catégorie', labels=['category'])
        batched_fam = CounterMetricFamily('llm_agents_batched_total', 'Agents batchés par catégorie',      labels=['category'])
        batched_by_cat = _by_prefix(counters, "agents_batched_total:")
        for category, count in _by_prefix(counters, "prompts_sent_total:").items():
            prompts_fam.add_metric([category], count)
            batched_fam.add_metric([category], batched_by_cat.get(category, 0))
        yield prompts_fam
        yield batched_fam

        # ── Tokens consommés par provider ─────────────────────────────────────
        tok_in_fam  = CounterMetricFamily('llm_tokens_in_total',  'Tokens en entrée (prompt) consommés par provider', labels=['provider'])
        tok_out_fam = CounterMetricFamily('llm_tokens_out_total', 'Tokens en sortie (completion) consommés par provider', labels=['provider'])
        tokens_out_by_provider = _by_prefix(counters, "tokens_out_total:")
        for provider, val_in in _by_prefix(counters, "tokens_in_total:").items():
            tok_in_fam.add_metric([provider], val_in)
            tok_out_fam.add_metric([provider], tokens_out_by_provider.get(provider, 0))
        yield tok_in_fam
        yield tok_out_fam

        # ── Erreurs par provider ET type d'erreur ────────────────────────────
        err_type_fam = CounterMetricFamily(
            'llm_provider_errors_by_type_total',
            'Erreurs LLM par provider et type (rate_limit, tpm_exceeded, quota_exceeded, …)',
            labels=['provider', 'error_type'],
        )
        for suffix, val in _by_prefix(counters, "llm_errors_by_type:").items():
            parts = suffix.split(":", 1)
            if len(parts) == 2:
                err_type_fam.add_metric(parts, val)
        yield err_type_fam

        # ── Mode de transport choisi ──────────────────────────────────────────
        mode_fam = CounterMetricFamily(
            'llm_transport_mode_chosen_total',
            'Modes de transport principaux choisis par le LLM',
            labels=['mode'],
        )
        for mode, val in _by_prefix(counters, "transport_mode_chosen:").items():
            mode_fam.add_metric([mode], val)
        yield mode_fam

        # ── Tranches de distance ──────────────────────────────────────────────
        dist_fam = CounterMetricFamily(
            'llm_trip_distance_bracket_total',
            'Nombre de trajets par tranche de distance',
            labels=['bracket'],
        )
        for bracket, val in _by_prefix(counters, "trip_distance_bracket:").items():
            dist_fam.add_metric([bracket], val)
        yield dist_fam

        # ── Mode par tranche de distance ──────────────────────────────────────
        mode_dist_fam = CounterMetricFamily(
            'llm_mode_by_distance_total',
            'Modes de transport par tranche de distance',
            labels=['mode', 'bracket'],
        )
        for suffix, val in _by_prefix(counters, "mode_by_distance:").items():
            parts = suffix.split(":", 1)
            if len(parts) == 2:
                mode_dist_fam.add_metric(parts, val)
        yield mode_dist_fam

        # ── Mode par provider ─────────────────────────────────────────────────
        mode_prov_fam = CounterMetricFamily(
            'llm_mode_by_provider_total',
            'Modes de transport choisis par provider LLM',
            labels=['mode', 'provider'],
        )
        for suffix, val in _by_prefix(counters, "mode_by_provider:").items():
            parts = suffix.split(":", 1)
            if len(parts) == 2:
                mode_prov_fam.add_metric(parts, val)
        yield mode_prov_fam

        # ── Indice de trajectoire choisi ──────────────────────────────────────
        idx_fam = CounterMetricFamily(
            'llm_chosen_index_total',
            'Distribution des indices de trajectoire choisis par le LLM (0 = premier choix proposé)',
            labels=['index'],
        )
        for idx, val in _by_prefix(counters, "chosen_index:").items():
            idx_fam.add_metric([idx], val)
        yield idx_fam

        # ── Alarmes [ALARME] worker (le controller expose les siennes en direct) ─
        alarme_fam = CounterMetricFamily(
            'alarme_total',
            'Alarmes [ALARME] émises depuis le démarrage, par source',
            labels=['source'],
        )
        for source, val in _by_prefix(counters, "alarme:").items():
            alarme_fam.add_metric([source], val)
        yield alarme_fam

        # ── État des providers ─────────────────────────────────────────────────
        # 0=sans_cle_api, 1=desactive_temporairement (disable TTL), 2=cooldown, 3=actif
        state_fam = GaugeMetricFamily(
            'llm_provider_state',
            'État du provider: 0=sans_cle_api, 1=desactive_tmp, 2=cooldown, 3=actif',
            labels=['provider'],
        )
        for provider in load_provider_defaults():
            if provider not in settings.providers:
                state_fam.add_metric([provider], 0)
            elif deps.limiter.is_disabled(provider):
                state_fam.add_metric([provider], 1)
            elif deps.limiter.is_in_cooldown(provider):
                state_fam.add_metric([provider], 2)
            else:
                state_fam.add_metric([provider], 3)
        yield state_fam

        # ── TTL restant désactivation temporaire ───────────────────────────────
        disable_ttl_fam = GaugeMetricFamily(
            'llm_provider_disable_ttl_seconds',
            'Secondes avant réactivation automatique du provider (0 si actif)',
            labels=['provider'],
        )
        for provider in settings.providers:
            disable_ttl_fam.add_metric([provider], deps.limiter.disabled_ttl(provider))
        yield disable_ttl_fam

        # ── Profondeur des files de batch Redis (tâches PENDING par batch_key) ─
        queue_fam = GaugeMetricFamily(
            'llm_task_queue_depth',
            'Tâches en attente dans les files de batch Redis (clés batch:*)',
            labels=['batch_key'],
        )
        for batch_key, depth in deps.queue.depths().items():
            queue_fam.add_metric([batch_key], depth)
        yield queue_fam

        # ── Taux d'utilisation workers Celery par provider ────────────────────
        util_fam = GaugeMetricFamily(
            'celery_worker_utilization_ratio',
            'active_workers / concurrency_limit par provider (1.0 = saturation)',
            labels=['provider'],
        )
        for provider, cfg in settings.providers.items():
            active = deps.limiter.active_workers(provider)
            limit = cfg.concurrency_limit
            util_fam.add_metric([provider], active / limit if limit > 0 else 0.0)
        yield util_fam

        # ── Info statique providers (modèle, adapter) ──────────────────────────
        info_fam = GaugeMetricFamily(
            'llm_provider_info',
            'Informations statiques du provider (modèle, adapter)',
            labels=['provider', 'model', 'adapter'],
        )
        for provider, cfg in settings.providers.items():
            adapter = cfg.adapter or provider
            info_fam.add_metric([provider, cfg.default_model, adapter], 1)
        yield info_fam

        # ── Limites configurées (RPM / RPD / TPD) ─────────────────────────────
        rpm_limit_fam = GaugeMetricFamily('llm_provider_rpm_limit', 'Limite requêtes/minute configurée', labels=['provider'])
        rpd_limit_fam = GaugeMetricFamily('llm_provider_rpd_limit', 'Limite requêtes/jour configurée (0 = illimité)', labels=['provider'])
        tpd_limit_fam = GaugeMetricFamily('llm_provider_tpd_limit', 'Limite tokens/jour configurée (0 = illimité)', labels=['provider'])
        for provider, cfg in settings.providers.items():
            rpm_limit_fam.add_metric([provider], cfg.rpm_limit)
            rpd_limit_fam.add_metric([provider], cfg.rpd_limit or 0)
            tpd_limit_fam.add_metric([provider], cfg.tpd_limit or 0)
        yield rpm_limit_fam
        yield rpd_limit_fam
        yield tpd_limit_fam

        # ── Consommation du jour (UTC) et ratio d'usage ───────────────────────
        req_today_fam = GaugeMetricFamily('llm_provider_requests_today', 'Requêtes consommées aujourd\'hui (fenêtre UTC)', labels=['provider'])
        tok_today_fam = GaugeMetricFamily('llm_provider_tokens_today', 'Tokens consommés aujourd\'hui (fenêtre UTC)', labels=['provider'])
        rpd_ratio_fam = GaugeMetricFamily('llm_provider_daily_usage_ratio', 'requests_today / rpd_limit (1.0 = quota jour atteint)', labels=['provider'])
        exhausted_fam = GaugeMetricFamily('llm_provider_quota_exhausted', 'Provider écarté jusqu\'à minuit UTC pour quota jour atteint (1=épuisé)', labels=['provider'])
        for provider, cfg in settings.providers.items():
            req_today = deps.limiter.daily_requests(provider)
            tok_today = deps.limiter.daily_tokens(provider)
            req_today_fam.add_metric([provider], req_today)
            tok_today_fam.add_metric([provider], tok_today)
            if cfg.rpd_limit:
                rpd_ratio_fam.add_metric([provider], req_today / cfg.rpd_limit)
            exhausted_fam.add_metric([provider], 1 if deps.limiter.is_quota_exhausted(provider) else 0)
        yield req_today_fam
        yield tok_today_fam
        yield rpd_ratio_fam
        yield exhausted_fam


# Le REGISTRY prometheus est global au process : on n'enregistre le collecteur
# qu'une fois, et on repointe ses deps si create_app() est rappelé (tests).
_collector: Optional[WorkerMetricsCollector] = None


def install_collector(deps: GatewayDeps) -> WorkerMetricsCollector:
    global _collector
    if _collector is None:
        _collector = WorkerMetricsCollector(deps)
        REGISTRY.register(_collector)
    else:
        _collector.deps = deps
    return _collector
