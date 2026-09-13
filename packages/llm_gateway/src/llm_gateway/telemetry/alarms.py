"""
telemetry/alarms.py — Compteur Prometheus des alarmes [ALARME].

Convention projet : les anomalies confirmées sont loggées en ERROR avec le
préfixe [ALARME] (cf. CLAUDE.md, `make error`). Ce module rend ces alarmes
visibles dans Grafana : chaque site d'émission appelle `fire_alarme(source)`
juste à côté de son `logger.error("[ALARME] …")`.

Portée par processus :
- controller GAMA (llm-agents + llm_gateway.sdk) : compteur direct, scrapé
  sur :8002 ;
- worker Celery : PAS ce module — le worker n'expose pas de /metrics, ses
  alarmes passent par RedisMetricsSink (clé `alarme:{source}`) et sont relues
  par WorkerMetricsCollector (api/metrics.py) sous le même nom de famille.
Le compteur est créé au premier `fire_alarme`, jamais à l'import : le processus API
peut donc importer ce module (via le SDK) sans entrer en collision avec la famille
`alarme_total` émise par son collecteur Redis.
"""

from prometheus_client import Counter

_ALARME_TOTAL: Counter | None = None


def _counter() -> Counter:
    """Le compteur n'est enregistré dans le registre Prometheus qu'au premier appel.

    Importer ce module ne doit rien enregistrer : le processus API expose déjà la famille
    `alarme_total` via le collecteur Redis (api/metrics.py), et deux déclarations de la
    même famille font échouer le démarrage (DuplicateTimeseries).
    """
    global _ALARME_TOTAL
    if _ALARME_TOTAL is None:
        try:
            _ALARME_TOTAL = Counter(
                'alarme_total',
                'Alarmes [ALARME] émises depuis le démarrage, par source',
                ['source'],
            )
        except ValueError:
            # La famille est déjà servie par le collecteur Redis de l'API dans ce processus :
            # on compte hors registre (visible dans les logs [ALARME], pas doublé au scrape).
            _ALARME_TOTAL = Counter(
                'alarme_total',
                'Alarmes [ALARME] émises depuis le démarrage, par source',
                ['source'],
                registry=None,
            )
    return _ALARME_TOTAL


def fire_alarme(source: str) -> None:
    """Incrémente le compteur d'alarmes ; `source` est un slug stable et court
    (ex. 'backlog', 'event_loop', 'cache_llm') — faible cardinalité exigée."""
    _counter().labels(source=source).inc()
