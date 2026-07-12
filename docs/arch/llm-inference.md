# Architecture LLM — Inférence et load balancing

Le module LLM (`llm_module/`) fait office de répartiteur de charge haute performance pour les appels vers les API LLM externes. Il découple le controller des fournisseurs et absorbe les variations de débit.

---

## Vue d'ensemble

```
Controller  →  POST /tasks  →  Redis Sorted Set  →  Worker Celery  →  Provider LLM
                                (batch:{key})          (SWRR)
```

Les composants Docker impliqués :
- `api` (port 8000) : réception des tâches, démultiplexage des résultats
- `worker` : exécution Celery des appels LLM
- `redis` DB1 : broker Celery ; DB2 : backend de résultats

Concurrence active (`worker_concurrency` en settings) : 8 workers LLM+OTP parallèles.
Chaque worker peut attendre jusqu'à 120s pour une réponse LLM avant fallback.

Le module est structuré en package ports & adapters (`core/` pur, `ports/` Protocol,
`infra/redis/` + `infra/memory/`, composition explicite via `create_app()`) — voir
[llm-module-package-refactor.md](llm-module-package-refactor.md). Conséquences opérationnelles :
- la remise à zéro des fenêtres RPM est un geste du **lifespan de l'API** (un redémarrage
  de worker ne touche plus les compteurs en cours) ;
- les compteurs du worker vivent dans **un hash Redis `wmetrics`** (1 `HGETALL` par scrape
  Prometheus au lieu de dizaines de `SCAN`+`GET`) ;
- chaque adapter garde un **client httpx partagé** (keep-alive entre appels LLM) et la clé
  Google passe en header `x-goog-api-key` (plus de clé en query string dans les logs).

---

## Pipeline de batching

### File d'attente (Redis Sorted Set)

Les tâches soumises via `POST /tasks` sont insérées dans un **Sorted Set Redis** (clé `batch:{batch_key}`) trié par `priority_score = min(departure_time)` des agents. Les agents dont le départ est imminent remontent en tête de file.

La clé de hachage est : `MD5(Catégorie + Paramètres + Fournisseur_Forcé)` — les agents avec le même contexte de décision sont regroupés dans le même batch.

```text
[POST /tasks reçu]
└── Calcul priority_score = min(departure_time)
    └── Insertion dans Sorted Set batch:{batch_key}
        ├── Si taille ≥ seuil de dispatch → déclenchement immédiat
        └── Sinon → armement d'un compte à rebours Celery (batch_delay_seconds, 3s),
            dédupliqué par un flag SETNX `batch_sched:{batch_key}`
```

Le flag `batch_sched:{batch_key}` (SETNX + TTL) garantit qu'exactement un dispatch différé est armé par cycle de batch : sans lui, deux requêtes simultanées sur une file vide pouvaient chacune observer une taille > 1 et aucune n'armait le compte à rebours (tâches bloquées jusqu'au timeout client). Le worker libère le flag juste avant de dépiler la file ; le TTL sert de filet de sécurité si le message Celery se perd.

#### Seuil de dispatch vs capacité de pop

Deux limites distinctes gouvernent le batching :

- **Seuil de dispatch** (`Settings.get_dispatch_threshold`, côté API) : taille de file
  qui déclenche un dispatch immédiat. Provider forcé → sa capacité exacte ; provider
  dynamique → `batch_target_agents` (10), borné par la capacité du plus gros provider.
  Historiquement ce seuil était le **min** des providers, soit 1 à cause des petits
  TPM Groq : chaque tâche partait immédiatement, la fenêtre d'accumulation ne jouait
  jamais et le ratio agents/prompt plafonnait à ~2 (batching accidentel par backlog).
- **Capacité de pop** (`batch_max_agents` par provider, côté worker) : une fois le
  provider sélectionné, le worker dépile jusqu'à sa capacité réelle.

`batch_max_agents` est calculé au démarrage : `max(1, min(tpm_limit / tokens_per_agent, rpm_limit, max_batch_agents))`,
avec `tokens_per_agent = assumed_prompt_tokens + assumed_output_tokens` (3 000 — calé
sur les ~1 600 tokens/agent mesurés + 25 % de marge).

#### Budget de sortie (max_tokens) proportionnel au batch

Le `max_tokens` envoyé par le client (défaut 4096) est un budget **par tâche** (1 agent).
Le worker le multiplie par le nombre d'agents fusionnés dans le batch, borné par
`settings.max_output_tokens` (16 384, plafond global) puis par le
`max_output_tokens` **du provider** (plafond de complétion du modèle, déclaré dans
`providers.yaml`) puis par le budget de capacité par requête (voir ci-dessous).
Sans ce scaling, un batch `stm_reflection` de 10 agents (~500-1800 tokens de sortie
chacun) saturait le plafond de 4096 : le JSON était coupé en plein milieu et échouait
en `JSONDecodeError` à offset constant (~13-14k chars ≈ 4096 tokens).

#### Capacité par requête (max_tokens_per_request) — garde-fou 413

Le free tier groq rejette en **HTTP 413** toute requête unique dont
`prompt + max_tokens` dépasse le TPM du modèle. Chaque provider groq déclare donc
`max_tokens_per_request` (= son `tpm_limit`) dans `providers.yaml` — un test de config
l'exige. Trois protections s'articulent (`_fit_request_budget` dans
`worker/task_worker.py`) :

1. **Dimensionnement du batch** : `max_tokens_per_request` borne `batch_max_agents`
   au même titre que le TPM — un batch qui ne tient pas dans une requête n'est
   jamais constitué.
2. **Clamp dynamique de max_tokens** : après rendu du prompt, le worker confronte
   sa taille **réelle** (`prompt_chars / token_chars_ratio`) à la capacité et rogne
   `max_tokens` au budget restant. L'ancien clamp statique
   (`cap - assumed_prompt_tokens`) sous-estimait d'un facteur 2 les prompts
   `stm_reflection` (~4 500 tokens vs 2 200 supposés) : sur le run 2026-07-11,
   38 des 63 erreurs LLM étaient des 413 et `groq_openai_120` n'a servi qu'un
   batch sur tout le run.
3. **Reroutage préventif** : si même `min_output_tokens` (512) ne tient plus dans
   le budget, le worker lève `ProviderCapacityError` **avant l'appel HTTP** : slot
   RPM/TPM restitué, cooldown court du provider, batch rejoué sur un autre modèle
   via la rotation (même chemin que les 4xx non récupérables). Compteur Prometheus :
   `llm_capacity_reroute_total{provider}`.

#### Plafond de complétion par provider (max_output_tokens) — auto-appris

Chaque modèle a sa propre limite du paramètre `max_tokens` (8 192 pour
`llama-4-scout` sur Groq, 16 384 pour `gpt-4o-mini`, 65 536 pour `gpt-oss`…). Dépasser
cette limite provoque un HTTP 400 non retryable (``"`max_tokens` must be less than or
equal to `8192`"``) qui faisait échouer tout le batch. Trois mécanismes s'articulent :

1. **Déclaration** : le champ optionnel `max_output_tokens` de `providers.yaml` porte
   le plafond de complétion du modèle. Absent = pas de limite connue (fallback
   `settings.max_output_tokens`). Le worker borne le `max_tokens` envoyé à cette valeur.
2. **Apprentissage automatique** : si un provider répond quand même 400 avec un message
   `max_tokens must be ≤ N` (formats Groq/OpenAI/Google reconnus par
   `_parse_max_tokens_limit`), le worker apprend N via
   `learn_provider_max_output_tokens()` : config en mémoire ajustée immédiatement
   **et** ligne `max_output_tokens` écrite dans `providers.yaml` (édition chirurgicale
   préservant les commentaires, écriture atomique — le bind mount `./llm_module`
   persiste la valeur sur l'hôte). Le batch est alors rejoué : le prochain essai est
   plafonné correctement ou part sur un autre provider via la rotation. Si la limite
   était déjà connue (rien de nouveau à apprendre), l'échec reste définitif pour ne
   pas boucler sur la même 400.
3. **Routage** : le client transmet son budget `max_tokens` par tâche ; le load
   balancer (`select_provider(min_output=…)`) écarte les providers dont
   `max_output_tokens` ne peut pas servir la sortie d'une seule tâche — même
   mécanique que le filtre `min_tpm`.

En complément, tous les adapters au format OpenAI (mistral, groq, cerebras, openai)
vérifient `finish_reason == "length"` via `BaseAdapter._check_openai_finish_reason` et
lèvent une erreur typée `max_tokens_truncation` (503, éligible au retry) au lieu de
laisser le parse échouer avec un message trompeur — même pattern que l'adapter Google
avec `finishReason == MAX_TOKENS`. Ce check attrape aussi le cas des modèles « thinking »
(GLM-4.7 sur Cerebras) dont le budget est épuisé pendant le raisonnement (`content` vide
→ `Expecting value: char 0`).

### Exécution Worker

```text
[Worker Celery déclenché]
└── Sélection provider via SWRR
    ├── Circuit Breaker : provider désactivé ?
    ├── Vérification quota RPM (script Lua atomique)
    └── Réservation du slot
└── ZPOPMIN jusqu'à batch_max_agents tâches
└── Rendu prompt unifié via Jinja2 (schéma JSON injecté)
└── Appel HTTP vers l'API du provider
└── Réalignement des agent_id (le LLM renvoie parfois `PERSONA 446264` ou un nom →
    réaligné sur l'id réel via sa partie numérique, sinon résultat perdu)
└── Démultiplexage par agent_id → DB2 Redis + Pub/Sub
```

#### Source des prompts système

Le texte du prompt système n'est plus codé en dur dans les templates Jinja. Il provient
d'une **source unique** : `llm_module/prompts/prompts.yaml`, fusionnée avec l'historique
du pipeline de calibration (`scripts/models_influence/prompt_calibration_V3.ipynb`, qui y
écrit chaque variante calibrée).

- `active:` mappe chaque catégorie de template vers la clé de la variante en production
  (ex. `itinary_multi_agent: expert`). Promouvoir un nouveau prompt = changer cette valeur,
  sans modifier le code.
- `prompts:` contient les variantes (`content`), schéma JSON inclus. À l'exécution,
  `PromptManager.get_system_prompt(category)` retire le bloc « Schéma JSON attendu »
  (réinjecté dynamiquement via `{{ schema }}` depuis `schemas.json`) et passe le texte au
  template via la variable `system_prompt`.
- Les catégories absentes de `active:` (ex. `perception_filter`) conservent leur section
  `<!-- SYSTEM -->` en dur dans leur template.

#### Isolation du cache LLM par version de prompt

Le cache sémantique LLM (`data/cache/llm/`) est partitionné par empreinte du prompt système
actif : `data/cache/llm/<checksum>/<population>/`. Le checksum vient de
`PromptManager.active_prompt_checksum()` (SHA-256 tronqué des prompts système actifs). Si le
prompt actif change (nouvelle variante calibrée promue dans `active:`), le checksum change et
le cache repart à neuf au lieu de réutiliser des décisions prises avec l'ancien prompt. Les
anciens répertoires de cache sont conservés (retour arrière possible).

---

## Load balancing SWRR

L'algorithme **Smooth Weighted Round Robin** distribue les requêtes entre providers actifs proportionnellement à leur `weight`. Un provider avec `weight: 2.0` reçoit deux fois plus de requêtes qu'un provider à `weight: 1.0`.

**Convention de poids** (depuis 2026-07-10) : `weight = min(rpm_limit, tpm_limit / 3000) / 15`,
où 3 000 ≈ tokens (in+out) d'une requête moyenne et 15 = RPM de référence. Le poids reflète
ainsi la **capacité effective** : pour les providers à petit TPM (flotte Groq free tier),
c'est le TPM qui borne le débit réel, pas le RPM affiché. Avant ce recalage, les poids
étaient décorrélés des quotas — mistral (47 % de la capacité totale) ne recevait que ~8 %
du trafic pendant que les petits providers Groq saturaient (429, violations TPM). À
recalculer à chaque changement de `rpm_limit`/`tpm_limit` (cf. en-tête de `providers.yaml`).

À chaque sélection :
1. Vérification du Circuit Breaker (provider exclu ?)
2. Vérification du **quota journalier** (RPD/TPD) : provider écarté jusqu'à minuit UTC si épuisé
3. Réservation atomique **RPM + TPM** via un unique script Lua (compare `now` au compteur
   glissant Redis ; toute étape qui échoue annule les réservations déjà posées)
4. Réservation atomique du slot de concurrence

Si aucun provider n'est disponible, le worker attend en polling jusqu'à 60s avant d'échouer.

### Garde-fou TPM (fenêtre glissante 60 s)

Le limiter applique une **réservation de tokens par minute** en plus du RPM. Sans elle,
`tpm_limit` n'était qu'un filtre de routage : un provider dont le `rpm_limit` dépassait
largement sa capacité tokens (ex. Groq free tier — `rpm_limit: 60` mais `tpm_limit: 6000`,
soit ~2 requêtes/min de ~2 500 tokens) recevait ~30× trop de requêtes et récoltait un flot
de **429**. Désormais :

- chaque provider expose `tpm_estimate_per_request` (calculé au démarrage :
  `batch_max_agents × (assumed_prompt_tokens + assumed_output_tokens)`) ;
- à la réservation, ce budget estimé est ajouté à un compteur `tpm:{provider}` (fenêtre
  60 s) ; si le total dépasse `tpm_limit`, la réservation est refusée et le routeur passe
  au provider suivant ;
- sur échec d'appel, `release_slot` restitue la réservation TPM (comme le slot RPM), pour
  ne pas sur-freiner ;
- les providers sans `tpm_limit` (`tpm_limit: null`, ex. Gemma) ne sont pas bridés.

**Recalage à la taille réelle** (depuis 2026-07-10) : le forfait statique est corrigé en
deux temps par le worker (`adjust_tokens`) :

1. **Après rendu du prompt** — la réservation devient
   `len(prompt en caractères) / token_chars_ratio + n_agents × assumed_output_tokens`.
   Le ratio `token_chars_ratio = 3.0` a été mesuré sur un run réel (427 échanges,
   prompts français + JSON : p50 = 3,24 chars/token, p10 = 3,05 → ~8 % de marge).
   Un petit batch rend immédiatement du headroom aux autres workers ; un batch de
   réflexions STM (~4 500 tokens_in/agent, soit 2× le forfait) réserve son vrai coût —
   c'est ce sous-comptage qui faisait dépasser le TPM réel des petits providers.
2. **Après la réponse** — la réservation est recalée sur `tokens_in + tokens_out`
   facturés. Si le réel dépasse l'estimation de +25 %, un WARNING signale une dérive
   du ratio (`token_chars_ratio` / `assumed_output_tokens` à revoir).

Le forfait statique ne sert plus qu'à la réservation initiale (avant que le contenu du
batch soit connu) et reste distinct du comptage a posteriori des tokens réels qui
alimente le quota journalier `tpd_limit`.

### Quotas journaliers (RPD / TPD)

Les free tiers imposent aussi des quotas **par jour** (`rpd_limit` requêtes/jour,
`tpd_limit` tokens/jour, ex. Google Gemini : 500 req/jour). Contrairement aux fenêtres
RPM/TPM (60 s glissantes qui se réinitialisent seules), un quota journalier épuisé reste
mort jusqu'à minuit — sur un run de plusieurs heures, les providers tombaient un par un et
le pipeline dégénérait (cascade de timeouts → décisions par défaut). Ces quotas sont
désormais **appliqués** (`infra/*/rate_limiter.py`) :

- chaque réservation incrémente un compteur journalier UTC (`rpd:{provider}:{jour}`) ;
  les tokens réellement consommés sont comptés après l'appel (`record_tokens` →
  `tpd:{provider}:{jour}`) ;
- au premier dépassement, un flag `quota_exhausted:{provider}` (TTL = secondes jusqu'à
  minuit UTC) écarte le provider de la rotation **sans re-sollicitation** toutes les
  `disable_timeout` secondes ;
- `/health` (`get_status`) expose `daily_requests`, `daily_tokens`, `rpd_limit`,
  `tpd_limit` et `quota_exhausted` par provider.

---

## Gestion des pannes — Circuit Breaker

| Événement | Comportement |
|-----------|-------------|
| Erreur réseau / HTTP 5xx | `mark_cooldown` 60s + retry exponentiel (1s→30s, max 10 essais) |
| HTTP 429 (rate limit) | Cooldown calé sur le délai renvoyé par le provider, cherché dans l'ordre : header `retry-after` (secondes brutes), `x-ratelimit-reset-tokens` (les 429 Groq portent sur les tokens TPM/TPD), `x-ratelimit-reset-requests`, `x-ratelimit-reset`. À défaut de header, le délai est extrait du corps JSON (Google Gemini : `error.details[].retryDelay` ; Groq/Gemini : messages `"retry in Xs"` / `"try again in XhYmZ.Ws"`, formats `h`/`m`/`s`/`ms`). Fallback 60s si rien n'est trouvé ; cooldown clampé à [10s, 1h]. La tâche est requeue et re-routée vers un autre provider via la rotation SWRR |
| HTTP 4xx non récupérable (hors 429/max_tokens) | **Bascule de modèle** : le provider fautif est mis en cooldown court (`provider_switch_cooldown_seconds`, 30s) et le batch est rejoué **sans `force_provider`** → la rotation SWRR sélectionne un autre modèle. Borné à ≈`len(providers)` tentatives ; échec définitif seulement si tous les modèles rejettent la requête |
| Réponse illisible / hors-schéma (`ProviderParseError`) | **Bascule de modèle** identique : un modèle différent peut produire un JSON valide. En dernier recours (tous épuisés), la réponse brute est remontée au client |
| > 30 échecs consécutifs | Exclusion totale du routage SWRR pendant 120-180s glissantes |

Les tâches en échec sont réinsérées dans le Sorted Set avec leur score d'origine.

L'événement `ratelimit_reset` est tracé dans `llm_errors.jsonl`.

### Alarmes de saturation

Trois alarmes (niveau ERROR, préfixe `[ALARME]`, visibles via `make error`) signalent
un pipeline LLM qui ne draine plus :

- **Worker gateway** : quand tous les providers sont saturés/en cooldown et qu'un batch
  est abandonné, avec la liste des providers en cooldown (`task_worker.py`).
- **SDK client** (`llm_module/sdk.py`) : après 10 tâches échouées d'affilée côté
  controller (timeouts gateway inclus). Cette alarme **arme la backpressure SDK**
  (ci-dessous).
- **Backpressure `/sync`** (`handle/application.py`) : alignée sur les seuils du mode
  drainage — se déclenche quand le backlog atteint `drain_trigger_ratio` (défaut 80 %)
  de la population, donne le `min_interval` appliqué et les coefficients
  `min_internal_coeff_*` ; elle est aussi poussée vers la console GAMA et se réarme
  quand le backlog repasse sous `drain_release_ratio` (défaut 20 %).

### Backpressure /sync

Le délai minimal entre deux réponses `/sync` (donc entre deux steps GAMA) est calculé
par `compute_backpressure_interval()` (`backpressure.py`, testé dans
`tests/test_backpressure.py`) :

```
min_interval = cap × min(1, backlog / population)^k
```

Le seuil est **relatif à la population** : le backlog ne pouvant jamais dépasser le
nombre d'agents, un seuil absolu supérieur à la population rendrait le frein
inatteignable (cause de l'engorgement du run 2026-07-07 : 886/901 agents en attente
avec 0.33 s de frein). Avec les valeurs par défaut (`k=1.5`, `cap=30`), le frein monte
tôt et progressivement : ~1 s à 10 % de backlog, ~2.7 s à 20 %, ~5 s à 30 %, ~7.6 s à
40 %, ~10.6 s à 50 %, ~21.5 s à 80 % (où le mode drainage prend le relais), 30 s à
pile pleine.

### Mode drainage /sync (hystérésis)

Le frein progressif seul ne suffit pas quand la pile continue de monter malgré le
ralentissement : le temps simulé avance plus vite que le pipeline ne draine et les
agents ratent leurs heures de départ. Le **mode drainage** (`update_drain_mode()`,
`backpressure.py`) ajoute une barrière à hystérésis :

- **Enclenchement** : pile ≥ `world.drain_trigger_ratio` (défaut **80 %** — l'alarme
  backlog `[ALARME]` se déclenche au même seuil).
- **Comportement** : chaque réponse `/sync` est retenue jusqu'à `cap` secondes (la
  limite dure par réponse reste le read timeout HTTP du client GAMA — on ne peut pas
  bloquer indéfiniment une seule réponse), en ré-échantillonnant la pile toutes les
  `world.drain_poll_interval` s (défaut 1 s) pour rendre la main dès qu'elle est vidée.
- **Relâchement** : pile < `world.drain_release_ratio` (défaut **20 %**, soit une pile
  vidée à 80 %). Entre les deux seuils le drainage reste actif (hystérésis) : GAMA est
  bridé à ~1 step par `cap` tant que la pile n'est pas réellement drainée.
- `drain_trigger_ratio: 0` désactive le mécanisme (retour au frein progressif seul).

Points de trace : `[drain]` en WARNING à l'enclenchement et à chaque cap atteint,
INFO au relâchement avec la durée de rétention.

Nota : avec l'horizon glissant 24h (~5 activités/agent pré-calculées), un agent qui
termine son trajet reçoit **immédiatement** son move suivant (push à l'arrivée,
`handle_observation` → `_push_planned_move`) et passe `ready` sans transiter durablement
par `inactive`. Un taux d'`inactive` élevé et durable signifie donc que le précalcul ne
suit pas le rythme. La jauge du drainage, `activities_to_compute_count` (trajets en vol
+ agents idle sans plan), mesure ce même retard côté Python — les deux indicateurs
doivent rester cohérents. Seule exception légitime : deux activités consécutives au même
endroit (`legs=[]`), où GAMA garde volontairement `is_ready=false` pour éviter un
deadlock (`Inhabitant.gaml`).

### Backpressure SDK (drainage sur alarme)

Distincte de la backpressure `/sync` (qui freine le rythme des steps GAMA), la
backpressure **SDK** (`llm_module/sdk.py`) protège la gateway déjà saturée. Quand
l'alarme « 10 tâches échouées d'affilée » se déclenche, le client suspend toute nouvelle
soumission LLM (`_await_backpressure_drain`) tant que la pile in-flight n'est pas retombée
sous `remote_llm_backpressure_ratio × worker_concurrency` (défaut **20 %**, soit 4 tâches
pour 20). Une fois la pile drainée, la backpressure se désarme et le backlog repart ; toute
réponse réussie la désarme aussi (la gateway répond de nouveau). Objectif : laisser les
tâches en vol se terminer/timeouter avant de re-charger, au lieu d'entretenir la saturation.

### Timeout des tâches LLM

Le timeout de long-poll d'une tâche (`remote_llm_poll_timeout`) est de **60 s** : la fenêtre
est assez large pour que le worker absorbe un cooldown 5xx (60 s) + backoff, ou **bascule sur
un autre modèle** (parse error / 4xx), **avant** que le client abandonne et retombe sur le plan
par défaut. Sous une valeur trop courte, un incident pourtant récupérable côté gateway se
traduisait par des fallbacks massifs (itinéraire le plus rapide non arbitré par le LLM). Le
budget de saturation-retry du worker (`_MAX_SATURATION_RETRIES = 2`) est calé pour rester **sous**
ce timeout (≈48 s : 8 s + 12 s + 8 s + 12 s + 8 s), afin que l'état terminal côté worker précède
l'abandon client.

---

## Polling côté controller

Après soumission, le controller attend le résultat via long-poll Pub/Sub Redis (canal `task_done:{task_id}`). Si la socket pubsub est interrompue (`redis.exceptions.TimeoutError`) avant la fin du timeout, le serveur se reconnecte automatiquement et reprend l'attente jusqu'à épuisement du budget de temps — évitant les faux-timeouts (`waited=Xs timeout=30s`) lorsque la socket Redis se déconnecte brièvement. Les métriques de timing sont tracées dans le pipeline de mesure (voir [docs/pipeline.md](../../pipeline.md)).

---

## Configuration

```yaml
# dans le fichier de config d'expérience
llm:
  provider: groq_llama4        # force un provider (sinon SWRR automatique)
  model: meta-llama/llama-4-scout-17b-16e-instruct
```

Voir [docs/setup/llm-providers.md](../setup/llm-providers.md) pour la liste complète des providers et leur paramétrage.
