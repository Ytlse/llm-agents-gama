# SDK Python

`llm_gateway.sdk.client.LLMGatewayClient`, réexporté par la façade : `from llm_gateway import
LLMGatewayClient, TaskResult, TaskTiming`. Asynchrone (httpx), un seul `AsyncClient`
réutilisé entre les appels ; `aclose()` à l'arrêt du consommateur. Signatures détaillées :
[API Python](api-python.md).

## Constructeur

```python
LLMGatewayClient(
    base_url="http://localhost:8000", *,
    wait_timeout=120.0, dialogue_log_file=None, transport=None,
    backpressure_max_inflight=0, backpressure_release_ratio=0.2,
    circuit_failure_threshold=10, circuit_probe_interval=60.0,
)
```

| Paramètre | Défaut | Rôle |
|---|---|---|
| `base_url` | `http://localhost:8000` | racine du gateway ; le `/` final est retiré |
| `wait_timeout` | `120.0` s | valeur passée à `GET /tasks/{id}/wait?timeout=` ; le timeout de lecture httpx vaut `wait_timeout + 30` |
| `dialogue_log_file` | `None` | fichier texte où chaque requête **et** sa réponse sont ajoutées ; désactivé par défaut depuis 1.3.0, opt-in |
| `transport` | `None` | `httpx.AsyncBaseTransport` injectable (tests : `MockTransport`) |
| `backpressure_max_inflight` | `0` (désactivé) | quand l'alarme « 10 échecs consécutifs » est active, les nouvelles soumissions attendent que les tâches en vol retombent sous `release_ratio × max_inflight` |
| `backpressure_release_ratio` | `0.2` | seuil de relâchement (au moins 1) |
| `circuit_failure_threshold` | `10` | échecs consécutifs qui ouvrent le disjoncteur ; `0` désactive |
| `circuit_probe_interval` | `60.0` s | intervalle entre deux sondes quand le disjoncteur est ouvert |

!!! warning "`prompt_dialogue.log` contient des données personnelles potentielles"
    Le journal de dialogue écrit le payload complet (donc la fiche des personas : âge,
    profession, lieu de résidence, historique) et la réponse du modèle, en clair, dans le
    répertoire courant du processus. Il n'est pas versionné (`*.log` dans `.gitignore`) et,
    depuis 1.3.0, il est **désactivé par défaut** : ne le passer qu'en débogage, avec un chemin
    dans le dossier du run. Le journal des échanges côté worker suit la même règle
    (`telemetry.exchanges_enabled`, rédacteur `telemetry.redactor`).

## `execute(request) -> TaskResult`

`request` : un `LLMRequest` ou un `dict` de même forme. Séquence : passage du disjoncteur
→ éventuelle attente de backpressure → `POST /tasks` (3 tentatives sur erreur réseau
transitoire, attente 1 s puis 2 s) → `GET /tasks/{id}/wait` → métriques et journal.

Ne lève **pas** sur un échec de tâche : le `TaskResult` porte `status` et `error`. Lève
`httpx.HTTPStatusError` si le gateway refuse la soumission avec un **4xx** (payload invalide
ou catégorie inconnue : erreur de programmation, non comptée comme échec). Un **5xx** à la
soumission ou un gateway injoignable après 3 tentatives rendent un `TaskResult` en `failed`
et comptent comme échec (alarme, backpressure, disjoncteur).

### `TaskResult`

| Champ | Type | Sens |
|---|---|---|
| `status` | `TaskStatus` | `success` ou `failed` ; un long-poll expiré sans état terminal devient `failed` avec `error="Timeout expiré"` |
| `agents` | `list[AgentResponse]` | les résultats de cette tâche, alignés sur ses `agent_id` |
| `error` | `str | None` | message du worker ou du client (`Gateway error 503 à la soumission`, `Gateway LLM injoignable (ConnectError)`, `Réponse gateway non-JSON (HTTP …)`) |
| `provider_used` | `str | None` | instance de provider ayant servi le lot |
| `timing` | `TaskTiming | None` | `post_ms` (durée du POST), `wait_ms` (durée du long-poll), `timing_p5` (segments du worker) |
| `task_id` | `str | None` | identifiant côté gateway |
| `ok` | propriété | `status is SUCCESS and bool(agents)` |

## Disjoncteur

Après `circuit_failure_threshold` échecs consécutifs, le disjoncteur s'ouvre : les appels à
`execute` sont **suspendus** (ils attendent, ils n'échouent pas, aucune décision n'est
dégradée). Toutes les `circuit_probe_interval` secondes, l'un des appelants en attente devient
la sonde et traverse ; s'il réussit, le disjoncteur se referme et tous les appels suspendus
repartent sur le chemin nominal ; s'il échoue, la prochaine sonde attend un intervalle
complet. Un succès quelconque remet le compteur d'échecs à zéro.

Cette politique est celle du projet : en pénurie de quota, on attend le renouvellement, on ne
remplace pas la décision du modèle par un repli.

Journal : `[circuit] Sonde vers le gateway LLM…`, `[circuit] Gateway LLM rétabli après Ns…`.
Alarmes : `[ALARME] Gateway LLM : 10 tâches échouées d'affilée…` (source `gateway_llm`) puis
`[ALARME] Disjoncteur gateway LLM OUVERT…` (source `gateway_llm_circuit`), toutes deux sur
front montant.

## Backpressure

Indépendante du disjoncteur et **désactivée par défaut** (`backpressure_max_inflight=0`).
Quand elle est armée par l'alarme des 10 échecs, une nouvelle soumission attend que le
nombre de tâches en vol retombe à `max(1, int(max_inflight × release_ratio))`, puis la
backpressure se désarme et le backlog repart d'un coup. Le premier succès la désarme aussi.
La sonde du disjoncteur ne s'y soumet pas.

## Métriques Prometheus côté client

Déclarées à l'import de `llm_gateway.sdk.client` (pas de la façade `llm_gateway`) dans le
registre par défaut du processus consommateur — c'est le contrôleur GAMA, scrapé sur `:8002`,
qui les expose :

| Famille | Type | Labels | Sens |
|---|---|---|---|
| `llm_task_e2e_duration_seconds` | histogramme, seaux 1 · 2 · 5 · 10 · 30 · 60 · 120 s | `category` | durée `POST /tasks` → état terminal |
| `llm_gateway_circuit_open` | gauge 0/1 | — | disjoncteur ouvert |
| `llm_gateway_circuit_waiters` | gauge | — | soumissions suspendues derrière le disjoncteur |
| `alarme_total` | compteur | `source` | créé au premier `fire_alarme`, cf. [Erreurs et alarmes](erreurs-alarmes.md) |

Les compteurs par mode, par index ou par provider sont exposés côté worker, pas ici.

## Ce que le SDK ne fait pas

Il n'a pas d'API synchrone. Il ne connaît pas les catégories (il ne valide pas le payload
avant l'envoi : c'est l'API qui répond 422). Il ne tire pas le mode dans la distribution
renvoyée par `itinary_multi_agent` : c'est `mobility_llm.mode_choice.draw_index`, côté
simulation.
