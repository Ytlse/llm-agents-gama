# Ajouter une catégorie

Une catégorie est un type de requête : un template de prompt, un schéma de sortie, un
modèle d'item et, si besoin, une règle de priorité et des métriques. Le gateway n'en
contient aucune. Elles sont livrées par un **bundle** — un paquet Python qui déclare un
`CategoryBundle` sous l'entry point `llm_gateway.categories`.

Deux exemples réels servent de modèle : `llm_gateway.testing` (une catégorie `echo`, le
minimum) et `mobility_llm` (quatre catégories, un modèle d'item riche, priorité, métriques).

## Ce qu'un bundle fournit

```python
from llm_gateway import CategoryBundle, CategorySpec

CategoryBundle(
    name="mon_bundle",                    # nom unique ; apparaît dans les logs et `llm-gateway categories`
    templates_dir=Path(".../templates"),  # un <catégorie>.md.j2 par catégorie
    schemas_file=Path(".../schemas.json"),# objet JSON {catégorie: JSON Schema de la sortie}
    prompts_file=Path(".../prompts.yaml"),# facultatif : variantes de prompt système (active: / prompts:)
    categories={"ma_categorie": CategorySpec(name="ma_categorie")},
)
```

Un `CategorySpec` porte trois choses, toutes facultatives sauf le nom :

| Champ | Défaut | Rôle |
|---|---|---|
| `item_model` | `AgentItem` (un `agent_id`, champs libres conservés) | modèle pydantic qui valide chaque item du payload ; un item invalide → 422 côté API |
| `priority` | `None` (pas de priorité) | `Callable[[Sequence[BaseModel]], float | None]` : score du lot, **plus bas = plus urgent** |
| `observe` | `None` | `Callable[[ObserveContext], None]` : appelé par le worker après validation de la réponse, pour compter des métriques métier dans `ctx.metrics` |

## Étape 1 — le template

`templates/ma_categorie.md.j2`, Jinja2 (`trim_blocks`, `lstrip_blocks`, pas d'autoescape sur
`.md.j2`). Deux marqueurs découpent le rendu en messages ; sans marqueur, tout devient un
message `user`.

```jinja
<!-- SYSTEM -->
Tu réponds uniquement avec le JSON attendu.

Schéma JSON attendu :
{{ schema }}

<!-- USER -->
{% for agent in agents %}
agent_id={{ agent.agent_id }}
{% for key, value in agent.items() if key != 'agent_id' and value %}{{ key }} : {{ value }}
{% endfor %}
{% endfor %}
```

Variables disponibles : `agents` (les items validés, en dicts), `agent_ids`, `parameters`
(le dict de la requête), `schema` (le JSON Schema sérialisé, indenté), `system_prompt` (la
variante active de `prompts.yaml`, ou celle demandée par `parameters.prompt_variant`, ou
`""`).

Deux conventions comptent pour le worker :

- **écrire `agent_id=<valeur>` en tête de chaque bloc d'item** : c'est ce que `FakeAdapter`
  repère pour fabriquer une réponse par agent dans les tests, et ce que le modèle recopie
  dans sa réponse ;
- **injecter `{{ schema }}`** dans le système : les adapters l'envoient aussi en *structured
  output* quand l'API le permet, mais le texte reste la seule consigne chez Mistral.

## Étape 2 — le schéma de sortie

`schemas.json`, un objet par catégorie. La réponse du modèle doit être un objet avec une
clé `agents` (liste), chaque élément portant `agent_id` ; le parseur du gateway
(`_parse_output`) exige cette forme, puis chaque élément est validé en `AgentResponse`
(`extra="allow"` : vos champs voyagent jusqu'au client).

```json
{
  "ma_categorie": {
    "type": "object",
    "properties": {
      "agents": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {"agent_id": {"type": "string"}, "summary": {"type": "string"}},
          "required": ["agent_id", "summary"]
        }
      }
    },
    "required": ["agents"]
  }
}
```

## Étape 3 — `prompts.yaml` (facultatif)

Pour faire varier le prompt système sans toucher au template :

```yaml
active:
  ma_categorie: v2
prompts:
  v1:
    content: "Première rédaction…"
  v2:
    content: "Rédaction du 2026-09-01… Schéma JSON attendu : {…}"
```

`active[catégorie]` désigne la variante servie ; une requête peut en imposer une autre avec
`parameters.prompt_variant` (inconnue → `ValueError`, jamais de substitution silencieuse).
Le bloc « Schéma JSON attendu : … » en fin de `content` est retiré au rendu : c'est
`{{ schema }}` qui l'injecte. `PromptManager.active_prompt_checksum()` donne une empreinte
des variantes actives, utile comme clé de cache côté consommateur.

!!! warning "Un template qui rend `{{ system_prompt }}` sans texte propre"
    Si la catégorie disparaît de `active:`, `system_prompt` vaut `""` et le message système se
    réduit au schéma, sans erreur. `itinary_multi_agent.md.j2` est dans ce cas : garder
    `active.itinary_multi_agent` renseigné.

## Étape 4 — le modèle d'item et les hooks

```python
from pydantic import BaseModel, ConfigDict
from llm_gateway import ObserveContext

class MonItem(BaseModel):
    model_config = ConfigDict(extra="ignore")   # ou "allow" : à vous de choisir
    agent_id: str
    texte: str
    urgence: float | None = None

def priorite(items):                             # plus bas = plus urgent ; None = pas de priorité
    scores = [i.urgence for i in items if i.urgence is not None]
    return min(scores) if scores else None

def observe(ctx: ObserveContext) -> None:        # ctx.category, ctx.provider, ctx.items, ctx.output, ctx.metrics
    for rep in ctx.output.agents:
        ctx.metrics.incr(f"ma_metrique:{ctx.provider}")
```

`observe` ne modifie ni les items ni la sortie. Une exception dans le hook est journalisée
en WARNING et **n'échoue jamais le lot**. Les compteurs écrits dans `ctx.metrics` vivent dans
le hash Redis `wmetrics` ; pour qu'ils sortent sur `/metrics`, il faut une famille dans
`WorkerMetricsCollector` (`api/metrics.py`) — aujourd'hui les familles métier de la mobilité
y sont codées en dur (hypothèse H11 du ticket 037 ; l'exposition déclarée par le bundle
viendra plus tard).

Exemple réel : `mobility_llm.persona.AgentSpec` (item), `departure_priority` (plus petit
`departure_timestamp`) et `categories.itinary_multi_agent.observe_itinary` (mode le plus
probable, masse de probabilité par mode, tranches de distance, désaccords d'étiquettes).

## Étape 5 — l'entry point

Dans le `pyproject.toml` de votre paquet :

```toml
[project.entry-points."llm_gateway.categories"]
mon_bundle = "mon_paquet:bundle"
```

où `bundle()` rend le `CategoryBundle` (un objet déjà construit est accepté aussi). Ne pas
oublier les fichiers de données dans `[tool.setuptools.package-data]` :
`prompts/*.yaml`, `prompts/*.json`, `prompts/templates/*.j2`. Réinstaller (`pip install
-e .`) pour que `importlib.metadata` voie l'entry point.

## Ce qui est vérifié au démarrage

`CategoryRegistry` est construit par `build_deps` (API) et `build_worker_runtime` (worker),
à partir de tous les entry points trouvés. Pour chaque catégorie déclarée :

- template `<catégorie>.md.j2` absent → `ValueError: Catégorie 'x' : template x.md.j2 absent de …` ;
- schéma absent de `schemas.json` → `ValueError: Catégorie 'x' : schéma de sortie absent de …` ;
- même nom dans deux bundles → `ValueError: Catégorie 'x' déclarée par deux bundles (…)` ;
- entry point qui ne rend pas un `CategoryBundle` → `TypeError`.

Le processus refuse de démarrer : mieux vaut ça qu'une première requête en échec.
`llm-gateway categories` rejoue exactement cette construction.

## Étape 6 — tester sans Redis ni réseau

`llm_gateway.testing` est fait pour ça. Le test de référence est
`mobility_llm/tests/unit/test_bundle_end_to_end.py` ; en version courte :

```python
from llm_gateway.core.models import InternalRequest
from llm_gateway.testing import FakeAdapter, InMemoryMetricsSink, build_registry
from mon_paquet import bundle

def test_du_payload_aux_metriques():
    registry = build_registry(bundle())                       # construit et VALIDE le bundle
    handle = registry.get("ma_categorie")
    items = handle.validate_items([{"agent_id": "a1", "texte": "bonjour"}])
    messages = handle.render(items, {})
    assert messages[0].role == "system" and "agent_id=a1" in messages[-1].content

    fake = FakeAdapter(responder=lambda aid: {"agent_id": aid, "summary": "ok"})
    output, tokens_in, tokens_out = fake.call(
        InternalRequest(provider="fake", messages=messages, response_schema=handle.output_schema)
    )
    metrics = InMemoryMetricsSink()
    handle.observe("fake", items, output, metrics)
    assert metrics.get("ma_metrique:fake") == 1
```

`build_registry()` sans argument charge le seul bundle `echo`. Pour tester l'API complète en
mémoire (202, 422, `/health`), reprendre la fixture `memory_deps` de
`tests/integration/conftest.py` : `create_app(settings, deps=GatewayDeps(…, registry=build_registry(bundle())))`.

## Ce que le gateway ne fera pas pour vous

Il ne sait pas ce que vos items représentent, il ne relit pas vos compteurs sur `/metrics`
sans une famille déclarée, et il n'a pas d'autre format de sortie qu'une liste `agents`
alignée sur `agent_id` (`AgentResponse` garde aussi les champs `probabilities`,
`chosen_index`, `mode`, `reason`, `summary` de la mobilité — hypothèse H5, généricisation en
itération 2). Un `agent_id` renvoyé mal formé (« PERSONA 446264 ») est réaligné sur sa partie
numérique ; un `agent_id` inconnu est perdu et journalisé en ERROR.
