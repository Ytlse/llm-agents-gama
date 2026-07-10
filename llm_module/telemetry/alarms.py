"""
telemetry/alarms.py — Compteur Prometheus des alarmes [ALARME].

Convention projet : les anomalies confirmées sont loggées en ERROR avec le
préfixe [ALARME] (cf. CLAUDE.md, `make error`). Ce module rend ces alarmes
visibles dans Grafana : chaque site d'émission appelle `fire_alarme(source)`
juste à côté de son `logger.error("[ALARME] …")`.

Portée par processus :
- controller GAMA (llm-agents + llm_module.sdk) : compteur direct, scrapé
  sur :8002 ;
- worker Celery : PAS ce module — le worker n'expose pas de /metrics, ses
  alarmes passent par RedisMetricsSink (clé `alarme:{source}`) et sont relues
  par WorkerMetricsCollector (api/metrics.py) sous le même nom de famille.
Ne pas importer ce module dans le processus API : la famille `alarme_total`
y est déjà émise par le collecteur Redis (collision de noms au scrape sinon).
"""

from prometheus_client import Counter

ALARME_TOTAL = Counter(
    'alarme_total',
    'Alarmes [ALARME] émises depuis le démarrage, par source',
    ['source'],
)


def fire_alarme(source: str) -> None:
    """Incrémente le compteur d'alarmes ; `source` est un slug stable et court
    (ex. 'backlog', 'event_loop', 'cache_llm') — faible cardinalité exigée."""
    ALARME_TOTAL.labels(source=source).inc()
