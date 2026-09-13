# Première requête

De zéro à une réponse LLM validée, en local, avec la catégorie `perception_filter` du bundle
`mobility_llm`. Durée : une dizaine de minutes, dont l'essentiel à attendre les modèles.

Prérequis : Python 3.12, Docker (pour Redis), au moins une clé API d'un fournisseur de
`providers.yaml` (Mistral, Groq, Google, Cerebras ou OpenAI).

## 1. Installer les paquets

Depuis la racine du dépôt :

```bash
pip install -e ./mobility_core -e ./llm_gateway[test] -e ./mobility_llm
```

L'ordre n'a pas d'importance ; `mobility_llm` déclare `llm-gateway>=1.1` et
`mobility-core>=0.1` comme dépendances. L'installation en editable suffit pour que l'entry
point `llm_gateway.categories` soit visible de `importlib.metadata`.

## 2. Lancer Redis

```bash
docker run -d --name redis-gateway -p 6379:6379 redis:7-alpine
```

Le gateway attend Redis sur `redis://localhost:6379/0` (tâches, files, quotas), `/1`
(broker Celery) et `/2` (résultats Celery). Ces trois URL sont des réglages
(`LLM_GATEWAY_REDIS__URL`, `LLM_GATEWAY_EXECUTOR__CELERY_BROKER_URL`, `LLM_GATEWAY_EXECUTOR__CELERY_RESULT_BACKEND` ; les anciens noms sans préfixe sont encore lus avec un avertissement).

## 3. Donner une clé API

Les clés ne sont jamais dans `providers.yaml` : elles viennent de l'environnement, une par
fournisseur, sous la forme `PROVIDER_KEYS__<nom>`. Le nom est celui de l'instance dans
`providers.yaml` (`google_gemini31_key2`), sinon celui de l'adapter (`mistral`, `groq`, `google`,
`cerebras`, `openai`).

```bash
cp llm_gateway/.env.example .env      # toutes les variables lues, commentées
export PROVIDER_KEYS__mistral=...      # ou éditer .env puis `set -a; source .env`
llm-gateway config validate
```

Attendu : `OK — 1 provider(s) avec clé : mistral`. Les instances sans clé sont écartées au
démarrage avec un avertissement, elles ne bloquent rien.

## 4. Regarder ce que le gateway sait servir

```bash
llm-gateway categories
```

Avec `mobility_llm` installé :

```
itinary_multi_agent   (bundle=mobility, items=AgentSpec)
ltm_self_reflection   (bundle=mobility, items=AgentSpec)
perception_filter     (bundle=mobility, items=AgentSpec)
stm_reflection        (bundle=mobility, items=AgentSpec)
```

!!! note "Sans bundle, rien n'est servi"
    Si vous n'installez que `llm_gateway`, la commande imprime « Aucune catégorie enregistrée
    (aucun bundle sous l'entry point llm_gateway.categories) » et rend le code 1. L'API
    démarre quand même, mais **toute** requête `POST /tasks` reçoit un 422 :
    `Catégorie inconnue 'perception_filter'. Catégories enregistrées : []`. Le gateway ne
    contient aucun prompt ; c'est voulu ([ADR 0002](../adr/0002-hook-de-categorie.md)).

## 5. Démarrer l'API et le worker

Deux terminaux :

```bash
llm-gateway serve --port 8000
```

```bash
llm-gateway worker --loglevel info --concurrency 25 --pool threads
```

Ce sont les mêmes commandes que `docker-compose.yml` (`uvicorn llm_gateway.main:app` et
`celery -A llm_gateway.worker.task_worker.celery_app worker … -P threads`). Au démarrage,
l'API remet à zéro les fenêtres RPM/TPM et le registre journalise
`Bundle de catégories enregistré | bundle=mobility categories=[…]`.

```bash
curl -s localhost:8000/health | python -m json.tool
```

Chaque provider avec clé apparaît avec `current_rpm`, `rpm_limit`, `available`.

## 6. Soumettre un lot

`perception_filter` transforme la fiche d'un persona en un court récit à la première
personne. Son modèle d'item est `AgentSpec` : seuls `agent_id` et `perception` sont
obligatoires, tout le reste a une valeur par défaut.

```bash
curl -s -X POST localhost:8000/tasks -H 'Content-Type: application/json' -d '{
  "category": "perception_filter",
  "agents": [
    {"agent_id": "ag_1", "perception": "34 ans, cadre, Compans-Caffarelli, sans voiture, abonnée Tisséo."}
  ]
}'
```

Réponse immédiate, code **202** :

```json
{"task_id": "3f1c…", "status": "pending", "provider_used": null,
 "message": "Tâche acceptée. Pollez GET /tasks/3f1c… pour le résultat."}
```

Ce qui vient de se passer côté API : la catégorie a été trouvée dans le registre, l'item
validé par `AgentSpec`, la tâche persistée, puis ajoutée à la file de son lot. Une seule
tâche est sous le seuil de dispatch immédiat (10) : le dispatch est planifié dans
`batch_delay_seconds` = 3 s pour laisser d'autres requêtes compatibles s'agréger.

## 7. Attendre le résultat

```bash
curl -s "localhost:8000/tasks/<task_id>/wait?timeout=120" | python -m json.tool
```

Long-poll sur Redis Pub/Sub : la réponse arrive dès que le worker publie l'état terminal.
Attendu, après 3 s de fenêtre plus la latence du modèle :

```json
{
  "task_id": "3f1c…",
  "status": "success",
  "result": [{"agent_id": "ag_1", "summary": "I'm 34, an executive living near Compans-Caffarelli…"}],
  "provider_used": "mistral",
  "latency_ms": 1843.2,
  "timing_p5": {"P4_4_ms": 3012.4, "P5_1_ms": 0.3, "P5_3_ms": 4.1, "P5_4_ms": 1843.2, "P5_5_ms": 0.1,
                "provider": "mistral", "retries": 0, "tokens_in": 412, "tokens_out": 96}
}
```

`P4_4_ms` est l'attente en file (la fenêtre de 3 s), `P5_4_ms` l'appel LLM. Le champ
`summary` est celui exigé par le schéma de sortie de cette catégorie (`categories/perception_filter/output_schema.json`) ; une réponse hors schéma
aurait été rejouée sur un autre provider puis, à défaut, rendue en `status: failed` avec le
brut dans `error`.

## 8. Voir ce qui a été envoyé

Le worker journalise chaque échange (prompt rendu, réponse, tokens) en JSONL dans
`<telemetry.workdir>/llm_exchanges.jsonl` (`LLM_GATEWAY_TELEMETRY__WORKDIR`, répertoire courant du worker par défaut) et les erreurs
dans `llm_errors.jsonl`. `GET /metrics` expose les compteurs Prometheus, dont
`llm_prompts_sent_total{category="perception_filter"}` et `llm_agents_batched_total`.

## 9. La même chose depuis Python

```python
import asyncio
from llm_gateway import LLMGatewayClient, LLMRequest

async def main() -> None:
    client = LLMGatewayClient("http://localhost:8000", wait_timeout=90.0, dialogue_log_file=None)
    result = await client.execute(LLMRequest(
        category="perception_filter",
        agents=[{"agent_id": "ag_1", "perception": "34 ans, cadre, sans voiture, abonnée Tisséo."}],
    ))
    print(result.status, result.provider_used, result.agents[0].summary if result.ok else result.error)
    await client.aclose()

asyncio.run(main())
```

`dialogue_log_file=None` désactive le journal de dialogue local (par défaut
`prompt_dialogue.log` dans le répertoire courant, qui contient les payloads envoyés — donc
potentiellement des données personnelles). Détails : [SDK Python](../reference/sdk-python.md).

## Ce qui peut coincer

| Symptôme | Cause probable |
|---|---|
| `422 Catégorie inconnue … Catégories enregistrées : []` | aucun bundle installé dans l'environnement de l'**API** |
| `422 Items invalides pour la catégorie 'perception_filter'` | il manque `perception` (modèle `AgentSpec`) |
| `status: failed`, `Providers saturés ou indisponibles après 8s` | aucun provider avec clé, ou tous en cooldown/quota : voir `/health` |
| la réponse tarde 3 s de plus qu'attendu | fenêtre d'accumulation `batch_delay_seconds` — normal pour une requête isolée |
| `Fournisseur 'x' exclu : clé API manquante` | `PROVIDER_KEYS__x` absent ; le nom doit être celui de l'instance ou de l'adapter |
