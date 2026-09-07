# mobility-llm

Les catégories LLM de la simulation de mobilité. Ce paquet est la colle entre le gateway
générique (`llm_gateway`) et le domaine de l'enquête EMC² (`mobility_core`) : il apporte le
modèle de persona, les templates, les schémas de sortie, les variantes de prompt système, le
tirage du mode dans la distribution renvoyée par le LLM et les métriques métier du worker.
Version 0.1.0 (ticket 037).

## Le bundle

Le gateway découvre ce paquet par l'entry point déclaré dans `pyproject.toml` :

```toml
[project.entry-points."llm_gateway.categories"]
mobility = "mobility_llm:bundle"
```

`bundle()` rend un `CategoryBundle` nommé `mobility` : chaque catégorie vit dans
`categories/<nom>/` (`template.md.j2`, `output_schema.json`, et `observe.py` pour les métriques
métier de l'itinéraire) ; les variantes de prompt restent dans `prompts/prompts.yaml`. Quatre
`CategorySpec` :

| Catégorie | Item | Priorité du lot | Hook `observe` |
|---|---|---|---|
| `itinary_multi_agent` | `AgentSpec` | plus petit `departure_timestamp` | `observe_itinary` : mode le plus probable, masse de probabilité par mode canonique, tranche de distance, désaccords d'étiquette de mode |
| `perception_filter` | `AgentSpec` | idem | — |
| `stm_reflection` | `AgentSpec` | idem | — |
| `ltm_self_reflection` | `AgentSpec` | idem | — |

Le gateway valide chaque catégorie au démarrage (template `<catégorie>.md.j2` et entrée de
`schemas.json` présents). `llm-gateway categories` liste les quatre avec `bundle=mobility,
items=AgentSpec`.

## Modules

| Module | Une ligne |
|---|---|
| `mobility_llm/__init__.py` | le bundle (`bundle()`, `CATEGORIES`, `BUNDLE_NAME`) et `prompt_manager()` pour les consommateurs hors gateway |
| `persona.py` | `AgentSpec`, l'item des catégories mobilité (ex-`llm_module.core.models.AgentSpec`) et `departure_priority` |
| `categories/itinary_multi_agent.py` | ce que le worker observe d'une décision d'itinéraire : compteurs Redis `transport_mode_chosen:*`, `mode_probability_pct:*`, `trip_distance_bracket:*`, `mode_by_distance:*`, `mode_by_provider:*`, `chosen_index:*`, `mode_label_checked` / `mode_label_mismatch` ; alarme au-delà de 5 % de désaccords sur 200 options |
| `mode_choice.py` | du vecteur de probabilités au mode tiré : `normalize_option_probabilities`, `mode_distribution` sur les modes canoniques, `draw_index` (graine déterministe dérivée du contexte), `argmax_index`, `canonical_mode` |
| `prompts/__init__.py` | les chemins : `TEMPLATES_DIR`, `SCHEMAS_FILE`, `PROMPTS_FILE` |

## `AgentSpec`

Un persona dans un lot de décision. Obligatoires : `agent_id`, `perception`. Facultatifs :
`destination`, `destination_zone`, `departure_time`, `departure_timestamp` (Unix, score de
priorité), `current_time`, `context`, `history`, `trajectories`, `goal`, `constraints`,
`feeling`, `day_outlook`, `agenda`. `extra="ignore"` : un champ non déclaré est perdu en
silence, comme avant le découpage — déclarer le champ ici est la seule façon de le faire
voyager jusqu'au template. Un persona sans `perception` est refusé par l'API en 422.

## Prompts, schémas, templates

Tout est à plat dans `src/mobility_llm/prompts/` (hypothèse H6 du ticket 037 :
`prompt_calibration` et les expériences citent `prompts.yaml`) :

- `templates/<catégorie>.md.j2` — marqueurs `<!-- SYSTEM -->` / `<!-- USER -->`,
  `{{ schema }}` injecté depuis `schemas.json`. `itinary_multi_agent.md.j2` n'a **pas** de
  texte système propre : il rend `{{ system_prompt }}`, donc la variante active.
- `schemas.json` — un JSON Schema de sortie par catégorie (`agents: [{agent_id, …}]`).
- `prompts.yaml` — `active: {itinary_multi_agent: expert_chaine}` et `prompts: {clé:
  {content: …}}` ; une vingtaine de variantes (`expert`, `persona_v1`…`v5`,
  `calibrated_2026…`, `b0_pristine`, `b_min`, `expert_chaine`, `minimal_persona`).

**Ajouter une variante de prompt** : une entrée sous `prompts:` avec `content:` ; la
désigner soit comme active (`active.itinary_multi_agent`), soit par requête
(`parameters.prompt_variant`, qui entre dans la clé de lot du gateway). Le bloc « Schéma JSON
attendu : {…} » en fin de `content` est retiré au rendu. Une variante inconnue lève
`ValueError` : jamais de substitution silencieuse. `prompt_manager().variantes()` liste les
clés, `prompt_manager().active_prompt_checksum()` donne l'empreinte du prompt actif (clé du
cache LLM du contrôleur).

## Pour les consommateurs Python

```python
from mobility_llm import prompt_manager, AgentSpec
from mobility_llm.mode_choice import normalize_option_probabilities, draw_index

pm = prompt_manager()                       # PromptManager du gateway chargé avec le contenu mobilité
pm.active_prompt_checksum("itinary_multi_agent")
weights = normalize_option_probabilities(result.agents[0].probabilities, n_options, modes=modes)
index = draw_index(weights, agent_id, sim_day)   # même contexte → même tirage
```

## Installation et tests

```bash
pip install -e ./mobility_core -e ./llm_gateway -e ./mobility_llm[test]   # depuis la racine du dépôt
cd mobility_llm && pytest -m "not e2e"                                    # ou `make test-mobility` à la racine
LLM_GATEWAY_E2E_URL=http://localhost:8000 pytest -m e2e                   # perception_filter sur un gateway réel
```

134 tests collectés le 2026-09-07 (`unit` : rendu des prompts, variantes, persona, choix
modal, métriques d'itinéraire ; `e2e` : sauté sans la variable).
`tests/unit/test_bundle_end_to_end.py` est l'exemple d'usage de `llm_gateway.testing` :
`build_registry(bundle())`, `FakeAdapter(responder=…)`, `InMemoryMetricsSink`, du payload au
hook de métriques sans Redis ni réseau.

Contrat d'architecture (import-linter, `.importlinter` à la racine) : ce paquet n'importe
pas la coquille `llm_module`. Historique : `CHANGELOG.md`.
