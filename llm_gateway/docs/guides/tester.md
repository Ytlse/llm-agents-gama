# Tester

La suite du gateway est rangée en quatre étages, chacun dans son dossier de `tests/`. Le
dossier **pose le marqueur** (`tests/conftest.py`) ; `--strict-markers` refuse tout marqueur
non déclaré dans `pyproject.toml`. 233 tests collectés le 2026-09-07 ; couverture exigée
80 % (`fail_under`), `testing/`, `cli.py` et `main.py` exclus du calcul.

| Étage | Dossier | Ce qu'il exige | Ce qu'il couvre |
|---|---|---|---|
| `unit` | `tests/unit/` | rien | modèles, clé de lot et priorité, séquence SWRR (dont propriétés hypothesis), configuration (`batch_max_agents`, seuil de dispatch), parseur tolérant et son corpus, helpers du worker (garde-fou 413, délais 429, limite 400 apprise), SDK sur `httpx.MockTransport` (résultat typé, journal de dialogue, backpressure, disjoncteur) |
| `contract` | `tests/contract/` | rien ; Redis réel si `LLM_GATEWAY_TEST_REDIS_URL` | la **même suite** sur chaque implémentation des ports `TaskStore`, `BatchQueue`, `RateLimiter`, `MetricsSink` : mémoire, fakeredis (scripts Lua via lupa), Redis réel |
| `integration` | `tests/integration/` | rien | l'API composée sur des ports mémoire (202, 422 catégorie inconnue, 422 item invalide, 404, `/health`), le chemin complet d'un lot dans le worker avec `FakeAdapter` (démultiplexage, réalignement d'`agent_id`, hook `observe` en erreur), l'adapter Google sur transport simulé (troncatures, tokens de pensée) |
| `e2e` | `tests/e2e/` | un gateway et des providers réels (`LLM_GATEWAY_E2E_URL`) | le dossier existe et est marqué ; il ne contient **aucun test** aujourd'hui — le test de bout en bout vit dans `mobility_llm/tests/e2e/test_perception.py` |

## Lancer

```bash
cd llm_gateway
pytest                                   # tout ; e2e sautés faute de LLM_GATEWAY_E2E_URL
pytest -m "not e2e" --cov                # ce que fait la CI, avec couverture
pytest -m unit                           # un étage
pytest tests/contract -k rate_limiter    # un contrat
LLM_GATEWAY_TEST_REDIS_URL=redis://localhost:6379/15 pytest tests/contract   # + backend Redis réel
LLM_GATEWAY_E2E_URL=http://localhost:8000 pytest -m e2e                      # exige api + worker + clés
```

Depuis la racine du dépôt, avec l'interpréteur du projet (`PKG_PYTHON`, défaut
`llm-agents/.venv/bin/python`) :

| Cible | Effet |
|---|---|
| `make test-gateway` | `pytest` dans `llm_gateway/` |
| `make test-mobility` | `pytest` dans `mobility_core/` puis `mobility_llm/` |
| `make test-all` | les trois paquets puis `lint-imports` |
| `make lint` | `ruff check` sur les trois paquets |
| `make typecheck` | `mypy` strict sur `core`, `ports`, `sdk` |
| `make lint-imports` | les 5 contrats de `.importlinter` |

`asyncio_mode = "auto"` : une fonction de test `async def` tourne sans décorateur.
`filterwarnings = error::DeprecationWarning:llm_gateway.*` : la bibliothèque ne consomme
jamais ses propres shims dépréciés — un `DeprecationWarning` émis par `llm_gateway` fait
échouer le test.

## Les contrats de ports

`tests/contract/conftest.py` paramètre la fixture `ports` sur `BACKENDS = ["memory",
"fakeredis"]`, plus `"redis"` si la variable est définie (base dédiée, `flushdb` avant chaque
test). Un test de contrat n'appelle que les méthodes des `Protocol` de `llm_gateway.ports`.
C'est ce qui garantit qu'un consommateur peut remplacer Redis par la mémoire (tests, mode
embarqué) sans changement de comportement observable. La CI ajoute un service Redis 7 pour
exercer l'implémentation réelle, scripts Lua compris.

## L'outillage `llm_gateway.testing`

Importable par n'importe quel consommateur (`pip install llm-gateway` suffit ; pytest n'est
pas requis) :

| Nom | Rôle |
|---|---|
| `echo_bundle()` | un bundle d'une catégorie `echo` : le modèle répète chaque item (`{"agent_id", "summary"}`) |
| `build_registry(*bundles)` | un `CategoryRegistry` construit à la main, sans entry point ; sans argument : `echo` seul |
| `FakeAdapter(responder=None)` | adapter sans réseau ; répond pour chaque `agent_id=…` trouvé dans le prompt ; `responder(aid) -> dict` fabrique la réponse ; `.calls` garde les `InternalRequest` reçus |
| `InMemoryTaskStore`, `InMemoryBatchQueue`, `InMemoryRateLimiter`, `InMemoryMetricsSink` | les ports en mémoire, réexportés d'`infra.memory` |
| `ECHO_TEMPLATES_DIR`, `ECHO_SCHEMAS_FILE`, `load_echo_schema()` | les fichiers du bundle echo |

Recette pour une API complète en mémoire (`tests/integration/conftest.py`) :

```python
store = InMemoryTaskStore(); limiter = InMemoryRateLimiter(settings.providers)
deps = GatewayDeps(settings=settings, store=store, queue=InMemoryBatchQueue(store), limiter=limiter,
                   metrics=InMemoryMetricsSink(), balancer=LoadBalancer(settings.providers, limiter),
                   registry=build_registry())
app = create_app(settings, deps=deps)          # puis httpx.AsyncClient(transport=httpx.ASGITransport(app=app))
```

Le dispatch Celery est remplacé par un stub (`monkeypatch.setattr(tw, "process_batch_task",
stub)`) : aucun broker n'est contacté. Un lot se rejoue directement par
`tw._execute_batch(runtime, tasks, "batch_test", "fake")` après `monkeypatch.setattr(tw,
"get_adapter", lambda name: fake)`.

## Ajouter un cas au corpus du parseur

`tests/data/llm_outputs.json` liste des sorties LLM réelles ou reconstituées ; chaque entrée
porte `expect` = nombre d'agents attendus, ou `"error"` si `_parse_output` doit refuser
(`ProviderParseError`). Un nouveau format de sortie cassant ou réparable se documente là, pas
dans un test ad hoc.

## Qualité et CI

`.github/workflows/ci.yml`, déclenché sur `llm_gateway/**`, `mobility_core/**`,
`mobility_llm/**`, `.importlinter` :

| Job | Contenu |
|---|---|
| `quality` | `ruff check`, `ruff format --check` (informatif, H10), `mypy` strict sur `core`/`ports`/`sdk`, `lint-imports` |
| `test-gateway` | `pytest -m "not e2e" --cov` avec un service Redis (`LLM_GATEWAY_TEST_REDIS_URL=redis://localhost:6379/15`), rapport `coverage.xml` en artefact |
| `test-mobility` | `mobility_core` puis `mobility_llm` (`-m "not e2e"`) |
| `build` | `python -m build` des trois paquets, wheels et sdist en artefact |
| `docs` | `mkdocs build --strict` dans `llm_gateway/` |

Filet local : `.pre-commit-config.yaml` (ruff `--fix`, gitleaks, check-yaml,
end-of-file-fixer, trailing-whitespace) restreint aux trois paquets — `pip install
pre-commit && pre-commit install`.

Les suites des paquets frères : `mobility_core` (199 tests, marqueurs `unit` et
`needs_data` ; les tests de parité se sautent d'eux-mêmes sans la couche `zf_zones.gpkg`) et
`mobility_llm` (134 tests, `unit` et `e2e`).
