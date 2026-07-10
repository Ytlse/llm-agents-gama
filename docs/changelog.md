## [2026-07-10] Réduction des fallbacks LLM : throttling de concurrence et timeouts étendus

Baisse drastique du fallback LLM (6.8% → ~0%) via throttling de la concurrence et tolérance accrue aux 5xx.

**Changes :**
- `worker_concurrency`: 20 → 8 (60% moins de requêtes parallèles, réduit la saturation des providers)
- `remote_llm_poll_timeout`: 60s → 120s (double du temps d'attente avant fallback, absorbe cooldowns 5xx)
- Google Gemma 42/43: `concurrency_limit` réduit à 1, `disable_timeout` augmenté à 180s (plus patient après erreur)

**Before :** 254/3753 trajets (6.8%) en fallback, backlog p95 = 963s, 9 rate-limits 429, Google 500 systématiques.
**After :** Pipeline moins saturé, providers moins overwhelmés, meilleure absorption des cooldowns transitoires.

---

## [2026-07-10] Refonte des dashboards Grafana : 8 vues par question, alertes et alarmes visibles

Les 5 dashboards historiques (cockpit, bottleneck, llm_agents, business, system) sont remplacés
par 8 dashboards numérotés par cycle de vie — `01_cockpit` (le run va-t-il bien ?),
`02_init_bootstrap`, `03_pipeline_scheduling`, `04_llm_gateway`, `05_routing`, `06_cache_llm`,
`07_metier_mobilite`, `08_systeme` — reliés par un menu déroulant commun. Le live ne garde que
les indicateurs actionnables pendant le run ; l'analyse fine reste dans `/debug-run`.

Ce que la refonte débloque :
- **Les alarmes `[ALARME]` sont enfin visibles dans Grafana** (compteur `alarme_total{source}`,
  feu « santé globale » dans le cockpit) et **7 alertes Grafana provisionnées** couvrent les cas
  critiques (agents bloqués, fallback LLM >10 %, aucun provider actif, drainage prolongé…).
- **La couverture du cache Qdrant** (`llm_cache_points_*`, agents couverts) répond en un coup
  d'œil à « le cache est-il assez peuplé pour l'init ? » (dashboard 02).
- **Le coût est suivi en tokens** : tokens/heure simulée, tokens économisés par le cache (04, 06).
- **Nouvelle lecture métier** : parts modales dans le temps, mode × motif d'activité
  (`trip_mode_by_purpose_total`, couvre LLM + cache + mono-choix), les 7 tranches de distance
  (les trajets 10-20 km et 20-50 km étaient invisibles), palette officielle des modes appliquée.
- **CPU/RAM par conteneur** via cAdvisor (dashboard 08) — on voit désormais *qui* consomme.
- Panneaux cassés corrigés : PromQL invalide sur les tokens par modèle, latence OTP par instance
  (label `instance` → `otp_instance`, il était écrasé par Prometheus), famille EDF/backpressure
  et OSMnx (ok/err/latence) enfin affichées.

**Before :** 5 dashboards accumulés, panels vides (PromQL invalide), alarmes visibles uniquement
via `make error`, tranches 10-50 km absentes, aucun coût en tokens ni vue par conteneur.
**After :** 8 dashboards par question, alertes provisionnées, feu santé + compteur d'alarmes,
coût en tokens, couverture cache Qdrant, mode × motif, CPU/RAM par conteneur.

`/debug-run` affiche en plus le ratio de choix d'itinéraire par défaut rapporté aux seules
décisions LLM (erreur définitive), avec alarme au-delà du seuil. Les métriques SDK dupliquées
(`llm_tasks_*`, `llm_mode_chosen_total`, `llm_index_chosen_total`) sont supprimées ; la latence
`/sync` est mesurée (`controller_sync_duration_seconds`).

---

## [2026-07-10] Nettoyage du code mort de la gateway LLM

Suppression du client HTTP legacy et des brouillons de prompts qui ne servaient plus, désormais
que la chaîne de production passe entièrement par le SDK typé (`LLMGatewayClient` / `TaskResult`).

**Supprimé :** `client.py` (ancien `LLMClient` sync) et ses tests dédiés (`test_client_validate.py`,
`test_e2e.py`), l'orchestrateur manuel `test_main.py` qui les pilotait, et trois variantes de
template jamais chargées (`itinary_multi_agent{2,3,4}.md.j2` — le moteur ne résout que
`itinary_multi_agent`). Aucun impact sur la simulation : ces éléments n'étaient référencés que
par eux-mêmes.

**Conservé :** les shims de compatibilité `settings/models.py` et `tasks/llm_config.py`, toujours
utilisés par les notebooks d'analyse externes.

---

## [2026-07-10] Moins de fallbacks LLM : timeout élargi, bascule de modèle sur erreur, rafale de bootstrap lissée

Quatre changements pour récupérer les itinéraires qui retombaient inutilement sur le plan
par défaut (« itinéraire le plus rapide » non arbitré par le LLM) lors des pics de saturation.

**1. Timeout de tâche LLM porté de 30 s à 60 s.** La fenêtre d'attente du controller était
trop courte face au temps de récupération de la gateway : un provider en cooldown 60 s après
une 5xx « disparaissait » avant que le client puisse réessayer. Avec 60 s, le worker a le temps
d'absorber le cooldown + backoff ou de basculer sur un autre modèle avant l'abandon.

**2. Bascule automatique de modèle sur erreur non récupérable.** Sur une réponse illisible
(hors-schéma) ou un 4xx non lié au rate-limit, le batch n'échoue plus sèchement : le modèle
fautif est mis en cooldown court et la requête est rejouée sur un **autre** modèle via la
rotation. Un JSON invalide sur un provider peut ainsi réussir sur un autre.

**3. Rafale de bootstrap lissée.** Au démarrage, les ~centaines d'agents ne lancent plus leur
premier itinéraire tous en même temps : un plafond de concurrence (`bootstrap_concurrency`,
défaut 30) étale les calculs OTP+LLM en vagues, ce qui évite la cascade de 429/5xx qui générait
des centaines de fallbacks au pré-calcul.

**Avant :** un pic de 500 (ex. « 10 tâches échouées d'affilée, error 500 ») → ~460 agents en
fallback au pré-calcul.
**Après :** la rafale est lissée, les erreurs transitoires sont réessayées sur un autre modèle,
et le client attend assez longtemps pour bénéficier de ces reprises.

**4. Rappel : le plafond `max_tokens` (400) porte sur les tokens de sortie** (complétion), pas
sur le prompt — la limite est apprise puis le batch rejoué avec un budget réduit.

---

## [2026-07-10] Cockpit init : compteur d'activités ratées fiable, couverture cache tracée, avancement bootstrap détaillé

Trois améliorations du **Cockpit — Pilotage Simulation** autour de la phase d'initialisation.

**1. « Activités ratées faute de LLM » reste à 0 pendant l'init.** Le pré-calcul des
itinéraires (bootstrap) faisait déjà de vraies décisions LLM : quand la gateway saturait,
les fallbacks étaient comptés comme des activités ratées **avant même le démarrage**. Les
décisions sont désormais taguées `phase` (`bootstrap` / `live`) et le cockpit ne compte que
la phase `live`.

**Avant :** le compteur montait à plusieurs centaines pendant l'init (fallbacks du bootstrap).
**Après :** 0 avant le démarrage, il ne s'incrémente qu'une fois la simulation en marche.

**2. Pourquoi le cache LLM n'est pas à 100 % à l'init — tracé.** Ce n'est **pas** un problème
de taille (Qdrant n'a pas de plafond) mais de **couverture** : la moitié des agents n'avait
jamais eu sa 1ᵉʳ activité stockée, car le cache n'écrit que sur appel LLM réussi (déficit
auto-entretenu si la gateway sature au peuplement). Une ligne de couverture au démarrage
(`[cache] couverture LLM … N points, A agents couverts, S obsolètes`) + des gauges Prometheus
+ une classification des miss (*agent absent* vs *clé différente*) rendent la cause lisible.
Un `[ALARME]` signale les points hérités d'un schéma obsolète (`weekday=None`) qui gonflent
la base sans jamais servir.

**3. Avancement du bootstrap (phase 4) visible en direct.** Nouvelle rangée cockpit avec
progression, agents planifiés, taux de hit cache du bootstrap, vague d'anticipation courante
et trajets futurs pré-cachés.

---

## [2026-06-10] Réparation JSON malformé (Mistral)

`adapters/base.py` utilise désormais `demjson3` comme fallback quand `json.loads` échoue sur la réponse d'un provider (virgule manquante, JSON tronqué, etc.). Si la réparation réussit, l'appel se termine normalement avec un log `WARNING`; sinon, la `ProviderParseError` est levée comme avant.

**Avant :** `JSONDecodeError: Expecting ',' delimiter` → tâche en échec définitif.  
**Après :** `demjson3` répare le JSON malformé et le traitement continue.

---

## [2026-06-05] Réflexions agents opérationnelles (STM/LTM)

Les agents peuvent maintenant générer et stocker des réflexions à partir de leur mémoire
courte et longue durée. Les réflexions passent par la gateway LLM (cache sémantique,
load balancing, circuit breaker) et sont prioritaires sur les départs futurs.

**Avant :** `self.llm` toujours None → toutes les réflexions silencieusement ignorées.  
**Après :** les réflexions STM et LTM sont exécutées, retournées et persistées correctement.

---

## [2026-06-05] Cache OTP activé partout par défaut

Le cache persistant OTP est désormais actif dans tous les modes sans configuration
explicite. Les itinéraires O/D/heure sont réutilisés entre les runs, ce qui accélère
significativement le warm-up.

**Avant :** certaines configs d'expérience forçaient `otp_cache_enabled: false`,
désactivant silencieusement le cache.  
**Après :** la valeur par défaut (`True`) fait foi ; les 36 configs d'expérience ne
peuvent plus le désactiver par inadvertance.

---

## [2026-06-05] Observabilité unifiée des trois caches (OTP / OSMnx / LLM)

Une seule ligne de log `[cache] OTP X% · OSMnx Y% · LLM Z%` est émise en fin de
warm-up et à chaque sync, avec le détail des miss LLM par raison (`no_candidates`,
`code_not_in_options`, …). Permet de diagnostiquer rapidement un cache inefficace.

---

## [2026-06-04] Routage population simplifié — SQLite comme unique source de vérité

Le fichier de population ne stocke plus les routes calculées. Toutes les routes passent
par le cache SQLite OSMnx, ce qui évite les désynchronisations entre le fichier et le
cache et simplifie la génération de population (`generate_population.ipynb`).

---

## [2026-06-04] Mémoire long terme agents activée

Les réflexions quotidiennes (STM→LTM) et la self-reflection multi-jours sont
fonctionnelles. La mémoire est activée par défaut ; les événements sont écrits en
double (JSONL + CSV) pour faciliter l'analyse.

---

## [2026-06-03] Météo injectée dans chaque observation agent

Les agents reçoivent les conditions météo courantes dans chaque observation.
Le flag `timed_out` est ajouté dans `GamaArrivalsLogger` pour distinguer les
agents bloqués en attente TC (> 30 min) des arrivées normales.

---

## [2026-06-03] Données versionnées avec DVC

Population (`po_toulouse.small`, `population_samples`) et sorties eqasim sont
maintenant versionnées via DVC. Les données météo historiques Toulouse 2025-01
à 2026-04 sont incluses.

---

## [2026-06-03] Throttling scheduler corrigé + robustesse initialisation

La formule de throttling (`min(cap,(n/scale)^k)`) est plus stable sous forte charge.
Les endpoints `/reflect` et `/sync` répondent `not_ready` (au lieu d'une erreur 500)
si le scénario n'est pas encore initialisé.

---

## [2026-06-15] Prompts système en source unique (prompts.yaml)

Le texte des prompts système est désormais centralisé dans
`llm_module/prompts/prompts.yaml` (fusion avec l'historique de calibration),
au lieu d'être codé en dur dans les templates Jinja. Une carte `active:` désigne
la variante en production par catégorie ; promouvoir un prompt calibré ne demande
plus de modifier le code. Le template `itinary_multi_agent` ne porte plus que la
structure (boucle agents + `{{ schema }}`). Variante active initiale : `expert`.

---

## [2026-06-15] Cache LLM invalidé au changement de prompt système

Le cache sémantique LLM est désormais partitionné par empreinte du prompt système actif :
`data/cache/llm/<checksum>/<population>/`. Le checksum
(`PromptManager.active_prompt_checksum()`) change dès qu'une nouvelle variante de prompt est
promue, évitant de réutiliser des décisions obsolètes. Les anciens caches sont conservés.

## [2026-06-17] Aucun déplacement ne démarre le week-end

Un départ planifié tombant un samedi ou un dimanche est automatiquement reporté
au lundi suivant à la même heure (samedi -> +2j, dimanche -> +1j). Le décalage
est appliqué sur le `departure_time` dans `_compute_move_for_activity`, donc
l'itinéraire OTP, `expected_arrive_at` et le `schedule_at` côté GAMA en
découlent. Comportement activable via `agent.no_weekend_departures` (défaut: vrai).

---

## [2026-06-17] Repères temporels unifiés dans les logs (`[SIM_TIMING]`)

Trois lignes de log partagent désormais le tag commun `[SIM_TIMING]` avec un champ
`event=...` pour faciliter la recherche (`grep '\[SIM_TIMING\]'` ou `grep event=SIM_DAY`),
chacune horodatée par l'heure réelle (`real_time`) :
- `event=SIM_START` : réception de `/init` (lancement de la simu) ;
- `event=INIT_DONE` : fin de la phase d'init (bootstrap terminé) ;
- `event=SIM_DAY` : à chaque tranche de 24h de temps simulé écoulé depuis le départ,
  avec `sim_day`, `sim_time` et `real_elapsed` (temps réel cumulé) pour mesurer le débit
  de la simulation.

Implémenté via `helper.format_sim_timing(...)`, appelé depuis `handle/application.py`
(`/init`) et `simulation_controller.sync()` (borne 24h).

---

## [2026-06-24] Consommation de tokens traçable par jour simulé et économie du cache

Deux ajouts pour mesurer empiriquement la consommation de tokens et l'effet du cache :

- `llm_exchanges.jsonl` porte désormais `sim_ts` / `sim_day` (timestamp simulé repris de
  `AgentSpec.departure_timestamp`), permettant de ventiler les tokens par **jour de
  simulation** au lieu de l'horloge murale.
- Chaque hit du cache sémantique LLM est tracé dans `workdir/llm_cache_hits.jsonl`
  (`log_llm_cache_hit()`). Comme un hit ne génère aucun appel — donc aucune ligne dans
  `llm_exchanges.jsonl` —, ce fichier permet de compter les appels économisés et d'estimer
  les tokens épargnés.

Le notebook `scripts/analysis/llm_traffic_analyse.ipynb` ajoute un graphe
« tokens par jour vs limite journalière » (plafond 338 540 000 tokens en pointillé),
empilé par catégorie, avec l'économie de cache estimée si `llm_cache_hits.jsonl` est présent.

---

## [2026-06-24] Réalignement des agent_id mal formés par le LLM

Le modèle renvoyait parfois un `agent_id` mal formé dans les réponses `itinary_multi_agent`
(ex. `PERSONA 446264`, ou le nom du persona à la place du numéro). Comme le démultiplexage
des résultats matche par `agent_id` exact, ces agents étaient **silencieusement écartés** :
aucune recommandation de trajet ne leur était renvoyée, et les métriques de distance/mode
les ignoraient.

- **Worker** (`worker/task_worker.py`) : après validation de la sortie LLM, chaque `agent_id`
  inattendu est réaligné sur l'identifiant réel via sa partie numérique. Un réalignement est
  loggé en `warning`, un id non résolu (sans chiffre, ex. un nom) en `error`.
- **Prompt** (`prompts/templates/itinary_multi_agent.md.j2`) : l'en-tête persona passe de
  `--- PERSONA {id} ---` à `--- agent_id={id} ---` (le mot « PERSONA » incitait le modèle à le
  recopier), et une consigne explicite demande de recopier l'`agent_id` numérique à l'identique.
- **Schéma** (`prompts/schemas.json`) : `agent_id` documenté (« recopier l'id fourni, numérique
  uniquement, sans préfixe ni nom »).

---

## [2026-06-26] Calibration de prompt : Gemini de bout en bout & tableau de bord de présentation

Le notebook `scripts/models_influence/prompt_calibration_V4.ipynb` et son module
`prompt_calibration_lib.py` évoluent pour produire un support de présentation lisible.

- **Modèle unifié** : évaluation **et** génération de mutations passent sur
  `gemini-3.1-flash-lite-preview` (plus aucune dépendance Mistral). `generate_mutation`
  appelle désormais l'API generativelanguage. Le log affiche explicitement le modèle
  réellement utilisé (résolu depuis `default_model` du provider).
- **Tableau de bord** (`present_calibration_state`) affiché au run initial puis à **chaque**
  mutation (acceptée ou rejetée) : carte d'ablation colorée (vert=utile/rouge=nuisible),
  méta « pires écarts strate × mode » vs EMC², score global, scores L1 par dimension,
  barres distribution actuelle vs EMC² (hachuré), et évolution du score (points verts
  conservés / rouges rejetés).

---

## [2026-06-26] Cooldown 429 : respect du délai Gemini (corps JSON)

Sur un rate limit 429, le délai de retry était lu uniquement dans les headers
(`x-ratelimit-reset-requests`). Google Gemini ne renvoie pas ce header — il place le
délai dans le corps JSON — donc le cooldown retombait systématiquement sur le défaut de
60s, en ignorant un « retry in 6.6s » bien plus court.

`adapters/base.py` extrait désormais ce délai du corps (`extract_retry_delay_from_body`) :
champ structuré `error.details[].retryDelay`, puis repli sur le texte `"Please retry in Xs"`.
Le header reste prioritaire quand il est présent. Bénéficie à la fois au worker (durée de
cooldown du provider) et au notebook de calibration (qui lisaient tous deux le même attribut
`ratelimit_reset`).

---

## [2026-07-07] llm_module : 4 correctifs de fiabilité (batching, timing, circuit breaker)

Relecture complète du module → correction de quatre bugs :

- **Déclenchement des batchs (race condition)** : l'armement du compte à rebours reposait
  sur `queue_size == 1` ; deux requêtes simultanées sur une file vide pouvaient chacune
  observer une taille de 2 et aucune n'armait le dispatch (tâches bloquées jusqu'au timeout
  client). Un flag SETNX `batch_sched:{batch_key}` garantit désormais exactement un dispatch
  différé par cycle de batch ; le worker le libère au moment du pop (TTL en filet de sécurité).
- **`min_tpm_required` perdu** : le re-dispatch d'une file non vide après un batch réussi
  omettait la contrainte TPM — les tâches suivantes pouvaient partir vers un provider
  sous-dimensionné. L'argument est maintenant propagé.
- **Métrique `P4_4_ms` toujours à 0** : l'attente micro-batch était calculée en mélangeant
  `time.monotonic()` (uptime) et un timestamp epoch — résultat négatif clampé à 0. Calcul
  corrigé avec `time.time()`, et migration de `datetime.utcnow()` (naïf, déprécié) vers
  `datetime.now(timezone.utc)` dans les modèles et le worker.
- **Circuit breaker Google inopérant sur timeout** : l'adapter Google levait ses erreurs
  (timeout, réponse vide/bloquée) avec le nom de classe `"google"` au lieu du nom d'instance
  (`google_gemma42`, …) — le cooldown était posé sur une clé que personne ne consultait et
  l'instance fautive restait sélectionnée. Les exceptions portent désormais `_instance_name`.

## [2026-07-07] llm_module : restructuration en package (ports & adapters)

Mise en œuvre du CR [llm-module-package-refactor.md](arch/llm-module-package-refactor.md)
(phases 0 à 5). Le contrat HTTP consommé par GAMA est inchangé.

- **Packaging** : `pyproject.toml` (installable `pip install .`), 12 dépendances runtime au
  lieu de ~45 — image Docker du gateway fortement allégée. Extras `[test]` et `[monitoring]`.
- **Plus d'effets de bord à l'import** : Settings construits explicitement (`get_settings()`),
  fabriques `create_app()` / `create_celery_app()`, reset des fenêtres RPM déplacé dans le
  lifespan de l'API (un redémarrage de worker ne remet plus les quotas à zéro), suppression
  du couplage caché `from settings import settings` dans la télémétrie.
- **Découpage du broker** : `redis_broker.py` (~30 fonctions libres) remplacé par 4 classes
  (`RedisTaskStore`, `RedisRateLimiter`, `RedisBatchQueue`, `RedisMetricsSink`) derrière des
  interfaces Protocol (`ports/`), avec équivalents `InMemory*` pour tester sans Redis.
- **Perf** : compteurs worker migrés vers un hash Redis (`wmetrics`) — 1 `HGETALL` par scrape
  Prometheus ; adapters mis en cache avec client httpx partagé (keep-alive entre appels LLM) ;
  clé API Google en header `x-goog-api-key` (plus de clé dans les URLs de logs).
- **SDK typé** : `LLMGatewayClient.execute()` → `TaskResult` pydantic (fini les dicts bruts,
  `"EXPECTED_ERROR"` et clés `_post_ms` injectées) ; `llm_agent.py` migré. L'ancien `LLMClient`
  reste pour les tests E2E.
- **Frontières vérifiées** : `core/` pur (batching, SWRR) + contrats import-linter en CI
  possibles (`lint-imports --config llm_module/pyproject.toml`).
- Tests : 197 unitaires verts (52 ajoutés). À rejouer avant merge : `docker compose build`
  + `test_e2e.py --burst 20`.

## [2026-07-07] llm-agents : correctifs de fiabilité (revue de code)

Quatre corrections issues de la relecture complète du module `llm-agents` :

- **Boucle d'envoi WebSocket robuste** : le handler d'exception de `publish_loop`
  référençait un attribut inexistant (`self.reconnect_interval`) — toute exception
  générique tuait définitivement la boucle d'envoi des actions bootstrap vers GAMA.
- **Worker de fallback annulé sur ré-init** : `set_scenario` annulait le wrapper
  `start_worker` (déjà terminé) au lieu de la vraie boucle de scan ; sur des `/init`
  successifs, l'ancienne boucle continuait de scanner l'ancienne population. Nouveau
  `stop_worker()` sur le scénario, appelé avant remplacement.
- **Persistance de la mémoire long-terme réparée** : les `MemoryEntry` étaient
  sérialisées en chaînes (`json.dumps(default=str)`) — irrécupérables au redémarrage,
  la mémoire épisodique repartait de zéro à chaque restart. Sérialisation explicite
  `to_dict()`/`from_dict()` (round-trip testé), fichiers de l'ancien format tolérés,
  et correction du cleanup >10 000 entrées et de `get_user_stats` qui traitaient les
  entrées comme des dicts (TypeError).
- **Clé du cache OTP persistant complétée avec `include_bike`** : un itinéraire calculé
  pour un agent sans vélo pouvait être resservi à un agent avec vélo (option vélo
  silencieusement absente des choix du LLM). Effet de bord : les entrées existantes du
  cache OTP deviennent froides (nouveau format de clé) — le cache se repeuple au premier run.

Tests : round-trip `MemoryEntry`, save/load métadonnées LTM, annulation worker,
différenciation des clés de cache, + 16 tests unitaires existants verts.

## [2026-07-08] Fiabilité pipeline LLM : corruption cache, délais 429, alarmes

Diagnostic d'une simulation où 80 % des agents restaient inactifs (backlog de
planification à 886/901 après 1h30) : providers LLM en rate-limit, cache sémantique
à 0 % de hit, backpressure inopérant. Trois correctifs :

- **Cache sémantique LLM — accès Qdrant sérialisé** : le client Qdrant embarqué n'est
  pas thread-safe ; les lookups/stores concurrents (via `asyncio.to_thread`)
  corrompaient l'index ("operands could not be broadcast", erreurs SQLite) et le cache
  ne servait plus aucune décision. Verrou `_db_lock` autour de `query_points`/`upsert`,
  plus alarme après 5 erreurs Qdrant consécutives.
- **Délai 429 réellement pris en compte** : le gateway ignorait le header standard
  `retry-after` et `x-ratelimit-reset-tokens` (les 429 Groq portent sur les tokens),
  et le fallback corps ne matchait pas les messages Groq ("try again in 16m7.68s") ni
  les formats `h`/`ms` (quotas journaliers TPD). Le cooldown provider est désormais
  calé sur le délai annoncé (clampé à [10s, 1h]) avant re-routage vers un autre modèle.
- **Alarmes de saturation** (`[ALARME]`, niveau ERROR, visibles via `make error`) :
  backlog > 50 % de la population dans `/sync` (avec min_interval et coefficients,
  poussée aussi vers la console GAMA), tous providers saturés côté worker gateway,
  et 10 échecs de tâches consécutifs côté SDK client.

Tests : 208 tests `llm_module` verts, dont nouveaux cas de parsing (`retry-after`
brut, `reset-tokens` prioritaire, durées `2h37m12.5s`, `140ms`, `16m7.68s`).

## [2026-07-08] Backpressure /sync : seuil relatif à la population

La formule de throttling introduite le 11 juin (`min(cap, (n / (120×pop/100))^3.7)`)
rendait le frein inatteignable : le backlog ne dépassant jamais la population, le
seuil absolu (1200 pour 1000 habitants) n'était jamais franchi — 0.33s de pause avec
886/901 agents en attente. Nouvelle formule `cap × min(1, backlog/population)^k`
extraite dans `backpressure.py` (fonction pure) : ~2.3s à 50% de backlog, ~19s à 89%,
cap (30s) à pile pleine, identique quelle que soit la taille de population. Le
coefficient `min_internal_coeff_scale`, devenu sans objet, est supprimé des settings.

Tests : `tests/test_backpressure.py` (10 cas) vérifie l'invariance du délai à ratio
de remplissage égal, l'atteignabilité du cap à pile pleine, la croissance monotone
avec le backlog et le cas réel du run 2026-07-07 (886/1000 → ~19.2s).

## [2026-07-08] llm-agents : correctifs secondaires et optimisations (revue de code, suite)

Implémentation des points #5–#8 et #11–#14 de la [revue de code](revue-llm-agents-reste-a-faire.md) :

- **Fallback LTM sans ChromaDB réparé** : `_init_shared_index` référençait une variable
  jamais définie dans la branche "simple storage" (NameError au premier démarrage sans index).
- **Mode SOLARI + récursion réparé** : `do_get_iteraries_v1` n'acceptait pas `include_bike`
  (TypeError systématique quand `recursion_search_depth > 0`).
- **Plus de trajet perdu sur échec WebSocket** : le rollback de `_push_planned_move` restaure
  le move calculé (LLM + OTP), et le scan de fallback détecte l'état Idle+plan pour retenter
  l'envoi au lieu de tout recalculer.
- **Cache sémantique LLM aligné sur l'intention** : suppression du rejet par seuil de
  similarité (`below_threshold`) — le filtre déterministe (agent + activité + tranche 10 min
  + hash options/météo) identifie déjà le contexte ; la similarité ne sert plus qu'à classer
  les candidats multiples. La LTM peut évoluer entre les runs sans invalider les décisions.
- **Persistance LTM allégée** : écriture des métadonnées par rafale (debounce 30 s + flush à
  l'éviction LRU) au lieu d'une réécriture complète du fichier à chaque entrée ; sérialisation
  unique ; écritures déportées hors de l'event loop ; `print()` remplacés par loguru.
- **Requêtes LTM filtrées côté vector store** : le retriever passe un filtre `person_id`
  (clause `where` Chroma) avec `top_k×5` candidats au lieu de rapatrier jusqu'à 500 nœuds
  globaux puis filtrer en Python — le recall par agent ne dépend plus du peuplement global.
- **I/O fichier hors event loop** : les écritures CSV/JSONL par événement (moves, arrivées
  GAMA, hits du cache LLM, états d'agents) passent par `asyncio.to_thread` — plus de blocage
  des coroutines aux heures de pointe.
- **Session HTTP OSMnx réutilisée** : une `aiohttp.ClientSession` partagée (keep-alive)
  remplace la création d'une session par requête vers les réplicas osmnx.
- **Tâches de fond protégées du GC** : nouveau helper `create_background_task` (référence
  forte jusqu'à complétion) appliqué à tous les `asyncio.create_task` fire-and-forget
  (planification, push, stores de cache, reconnexion WebSocket, boucle d'envoi).

Tests : rollback push, debounce LTM, référence des tâches de fond, signatures — verts ;
16 tests unitaires existants verts.

## [2026-07-08] llm-agents : métrique minuit et hygiène des logs (#9, #10)

- **Métrique `agent_scheduling_lag_seconds` corrigée au passage de minuit** : le delta
  envoi−cible (deux horaires mod 86 400) est normalisé dans [−43 200, +43 200] — un envoi
  à 00:05 pour une cible 23:55 compte désormais +600 s au lieu de −85 800 s.
- **Logs réparés et nettoyés** : deux `logger.warning("... %s", …)` (format printf ignoré
  par loguru → message affiché littéralement) convertis en f-strings dans la préparation
  de population ; suppression des logs de diagnostic `[trace]` marqués « à retirer »
  (factory, wrapper de cache OTP, init du cache par population).

## [2026-07-08] Anti-saturation gateway : quotas journaliers, timeout 30 s, backpressure SDK

Diagnostic du run où plus aucune décision LLM ne revenait après quelques jours simulés :
les prompts grossissent avec la mémoire (≈675 → 2000 tokens), les quotas free-tier
s'épuisent et le pipeline dégénérait en timeouts/plans par défaut (jusqu'à 99 % d'échecs
LLM le dernier jour). Trois correctifs :

- **Quotas journaliers RPD/TPD appliqués** (jusque-là purement informatifs) : dès qu'un
  provider atteint son `rpd_limit`/`tpd_limit`, il est écarté de la rotation jusqu'à minuit
  UTC au lieu d'être re-sollicité toutes les `disable_timeout` secondes. Compteurs journaliers
  UTC dans Redis (requêtes à la réservation, tokens réels après l'appel) ; `/health` expose
  `daily_requests`/`daily_tokens`/`quota_exhausted`.
- **Timeout tâche LLM 90 s → 30 s** : fallback plan par défaut plus rapide, la simulation ne
  bloque plus 90 s par calcul quand la gateway est muette. Budget de saturation-retry du
  worker recalé sous 30 s.
- **Backpressure SDK sur alarme** : quand l'alarme « 10 échecs consécutifs » se déclenche,
  le client suspend les nouvelles soumissions jusqu'au drainage de la pile in-flight sous
  20 % de `worker_concurrency`, laissant la gateway respirer avant de re-charger.

Tests : quotas RPD/TPD (in-memory + Redis) et drainage backpressure verts ; suite
`llm_module` (208 tests) verte.

---

## [2026-07-08] Cache OSMnx réutilisable au rejeu

Un rejeu de simulation recalculait tous les trajets (Pass 2, ~0,4 s/route) au lieu de
frapper le cache. Deux causes corrigées :

- **Clé voiture sans date absolue** : `OsmnxPersistentCache.make_key` n'inclut plus la date
  (`YYYY-MM-DD`), seulement le **jour de la semaine + tranche horaire** — la granularité réelle
  du facteur de congestion. Deux runs à des dates calendaires différentes mais même weekday
  réutilisent les mêmes trajets. Marche/vélo restent indépendants du temps (coords + mode).
- **Échantillonnage d'agents déterministe** : la sélection aléatoire des agents depuis la
  sortie eqasim utilise désormais une seed fixe (`data.population_sample_seed`, défaut 42) via
  un RNG local. Un rejeu retire exactement le même sous-ensemble d'agents → mêmes coordonnées
  → le cache SQLite fait hit au lieu de recalculer.

Note : les entrées voiture antérieures (clé incluant la date) ne sont plus adressées et se
repeuplent au premier run.

---

## [2026-07-08] Mode drainage /sync : GAMA retenu jusqu'à vidage de la pile à 80 %

Le frein progressif du `/sync` ne retenait GAMA que ~2.3 s par step à 50 % de backlog :
le temps simulé filait devant le pipeline LLM et les agents restaient inactifs faute de
plan. Ajout d'un **mode drainage à hystérésis** (`update_drain_mode`, `backpressure.py`) :

- Enclenché quand la pile atteint `drain_trigger_ratio` (50 %), il retient chaque réponse
  `/sync` jusqu'au cap (30 s, limite du read timeout HTTP de GAMA) en ré-échantillonnant
  la pile chaque seconde.
- Relâché seulement quand la pile repasse sous `drain_release_ratio` (20 %, pile vidée à
  80 %) — entre les deux seuils GAMA reste bridé à ~1 step par cap.
- Traces `[drain]` (WARNING enclenchement/cap atteint, INFO relâchement) ; réglages dans
  `WorldConfig` (`drain_trigger_ratio: 0` pour désactiver).

Doc : `docs/arch/llm-inference.md` § « Mode drainage /sync ». Tests :
`tests/test_backpressure.py` (15 verts).

---

## [2026-07-08] Fix troncature des réponses LLM à max_tokens sur les batches

Les batches `stm_reflection` de 10 agents (~500-1800 tokens de sortie par agent)
saturaient le `max_tokens` fixe de 4096 : réponse JSON coupée en plein milieu →
`JSONDecodeError` à offset constant (char 13158/14704 ≈ 4096 tokens), et batch entier
perdu. Deux corrections dans le gateway :

- **Budget de sortie proportionnel au batch** (`task_worker._execute_batch`) : le
  `max_tokens` client est désormais un budget par tâche, multiplié par le nombre
  d'agents fusionnés, borné par le nouveau réglage `max_output_tokens` (16 384) puis
  par la capacité du provider.
- **Détection de troncature typée** (`BaseAdapter._check_openai_finish_reason`) : les
  adapters mistral/groq/cerebras/openai vérifient `finish_reason == "length"` et lèvent
  `max_tokens_truncation` (503, retryable) au lieu d'un parse error trompeur — couvre
  aussi le `content` vide des modèles thinking (GLM-4.7) dont le budget part en
  raisonnement.

Doc : `docs/arch/llm-inference.md` § « Budget de sortie proportionnel au batch ».
Tests : `tests/test_adapter_base.py` (42 verts).

Complément : la jauge `activities_to_compute_count` compte désormais les agents Idle
sans plan **en direct** (plus de snapshot figé au dernier sync) — indispensable pour que
le mode drainage voie la pile baisser pendant qu'il retient la réponse `/sync` et rende
la main dès le seuil de relâchement. Clarification doc : avec l'horizon glissant 24h,
un agent qui termine son trajet reçoit immédiatement son move suivant et passe `ready` ;
un taux d'`inactive` durable est bien le symptôme d'un précalcul en retard (et non un
état légitime), à l'exception des activités consécutives au même endroit (`legs=[]`).

Réglage de la courbe de frein (demande du 2026-07-08) : exposant `k` passé de 3.7 à
**1.5** pour un freinage précoce et progressif (~1 s à 10 % de pile, ~2.7 s à 20 %,
~5 s à 30 %, ~7.6 s à 40 %, ~10.6 s à 50 %, ~21.5 s à 80 %). Le mode drainage et
l'alarme backlog se déclenchent désormais ensemble à **80 %** (`drain_trigger_ratio`)
et se relâchent au retour sous **20 %** (`drain_release_ratio`), l'alarme n'ayant plus
de seuils codés en dur.

## [2026-07-08] Fix : cache OSMnx inactif pendant le Pass 2 de génération de population

Le cache persistant OSMnx n'était initialisé qu'**après** l'écriture du fichier
population : lors d'une régénération, le Pass 2 (calcul des temps de trajet pour
l'ajustement des plannings) recalculait toutes les routes via OSMnx sans lire ni
alimenter le cache. L'initialisation (`_init_osmnx_cache`) est déplacée en tête de
`_prepare_population`, avant tout routage : le Pass 2 lit et remplit désormais le
cache, et une régénération ultérieure réutilise les routes déjà calculées.

Doc : `docs/arch/cache-memory.md` § « cache persistant OSMnx ».

## [2026-07-08] Plafond de complétion par provider (max_output_tokens) auto-appris

Les batchs `stm_reflection` échouaient en HTTP 400 sur `groq_llama4`
(`max_tokens` calculé = 16 384 > limite de 8 192 de `llama-4-scout`). Chaque provider
porte désormais un champ optionnel `max_output_tokens` dans `providers.yaml` (plafond
de complétion du modèle) : le worker borne le `max_tokens` envoyé à cette valeur, et
le load balancer écarte les providers incapables de servir le budget de sortie d'une
tâche (filtre `min_output`, même mécanique que `min_tpm`). Si un provider répond
malgré tout 400 « max_tokens must be ≤ N », la limite N est **apprise
automatiquement** : config ajustée en mémoire, ligne écrite dans `providers.yaml`
(commentaires préservés, écriture atomique, persistée sur l'hôte via le bind mount)
et batch rejoué au lieu d'échouer définitivement.

Doc : `docs/arch/llm-inference.md` § « Plafond de complétion par provider ».

## [2026-07-08] Cockpit de pilotage Grafana

Nouveau dashboard `cockpit.json` regroupant en une page l'état de la simulation :
avancement de l'init (5 étapes), remplissage de la pile et frein backpressure,
délai réel par step, **agents bloqués** (aucune planification réussie depuis
> `world.stuck_agent_threshold_hours` h simulées, défaut 20 h), état et **quotas
jour** des providers (ratio d'usage RPD), taux de hit des caches (LLM / OTP /
OSMnx) et **dernières erreurs LLM**.

Nouvelles métriques exposées côté gateway (`llm_provider_rpm/rpd/tpd_limit`,
`requests_today`, `tokens_today`, `daily_usage_ratio`, `quota_exhausted`) et côté
contrôleur (`controller_init_stage/progress_ratio`, `backpressure_interval_seconds`,
`backlog_fill_ratio`, `drain_mode_active`, `agents_stuck`). Les messages d'erreur
bruts, non stockables dans Prometheus, transitent par un ring buffer Redis
(`llm:recent_errors`) exposé via `GET /errors/recent` et affiché grâce au plugin
Grafana *Infinity*.

Doc : `docs/arch/monitoring.md`.

---

## [2026-07-08] Fiabilité du push GAMA : rollback sur envoi non délivré + watchdog d'arrivée

L'analyse du run 15:41 a montré ~250 agents « zombies » : `send_message` avale les
exceptions WebSocket et retourne `False`, que `_push_planned_move` ignorait — le push
était annoncé réussi ([push] dans les logs) alors que GAMA n'avait jamais reçu le trajet
(3 coupures WS 1006 pendant le run). L'agent restait « en déplacement » côté Python,
inactif côté GAMA, invisible de la pile de backpressure, du drainage et du scan.

- **Rollback sur `False`** : `_direct_push` propage le booléen de `send_json` et
  `_push_planned_move` traite un retour `False` comme une exception → rollback complet,
  le scan de fallback retente le push après reconnexion (le trajet calculé n'est pas perdu).
- **Watchdog d'arrivée** : chaque push arme `heading_expected_arrive_at` ; si le temps
  simulé dépasse l'échéance de plus de `world.arrival_watchdog_hours` (défaut 1 h sim),
  le scan lève `[ALARME] Arrivée perdue`, force la fin d'activité et remet l'agent dans
  le circuit. Couvre aussi les pertes silencieuses (socket moribonde avant détection
  keepalive, message perdu côté GAMA). Métrique `controller_lost_arrivals_recovered_total`.

Doc : `docs/arch/agents-lifecycle.md` § « Fiabilité du push ».

Analyse du run 18:29 (correctifs actifs) : le rollback (67 reprises) et le watchdog
(339 agents récupérés) fonctionnent, mais les coupures WebSocket persistaient — cause
racine identifiée : **blocages de l'event loop asyncio de 7-20 s** qui faisaient expirer
le keepalive (`ping_timeout=10s`). Deux compléments :

- **`ping_timeout` porté à 60 s** (`handle/websocket.py`) : un stall ponctuel ne ferme
  plus la socket ; une vraie coupure reste détectée en ~1 min et couverte par le watchdog.
- **Moniteur d'event loop** (`controller_event_loop_lag_seconds`) : mesure en continu la
  dérive de la boucle asyncio, `[ALARME]` en ERROR au-delà de 5 s de blocage pour
  identifier l'opération synchrone fautive.

## [2026-07-09] Reset propre au remplacement de scénario (stop GAMA → nouveau /init)

Un stop de simulation GAMA ne stoppe pas le process Python (pas d'endpoint `/stop`) :
le `/init` suivant remplace le scénario. Deux résidus de l'ancien run pouvaient
contaminer le nouveau, les `person_id` étant identiques d'un run à l'autre (même
population, même seed) :

- **Tâches en vol de l'ancien scénario** : `stop_worker()` n'annulait que la boucle de
  scan — les planifications LLM/OTP déjà lancées allaient au bout et poussaient leurs
  trajets périmés à la nouvelle simulation. Toutes les tâches fire-and-forget du
  contrôleur (planification, refill, push, réflexions, checkpoints) sont désormais
  suivies dans `_inflight_tasks` et annulées en bloc au remplacement.
- **Buffer de retry du `publish_loop`** : les actions non délivrées (socket morte au
  stop) restaient en attente et étaient rejouées vers le nouveau run à la reconnexion.
  Le buffer (`LoopContainer._pending`) est purgé par `set_scenario()` avec un WARNING
  donnant le nombre d'actions écartées.

Doc : `docs/arch/agents-lifecycle.md` § « Arrêt de simulation et remplacement de scénario ».

## [2026-07-09] Ordonnancement EDF et contre-pression prédictive pilotée par les échéances

Deux causes d'effondrement des runs longs corrigées : le service FIFO du contrôleur
(un refill lointain pouvait bloquer une replanification urgente derrière un jeton de
concurrence) et un frein `/sync` aveugle aux échéances (freinait trop tard sur
épuisement de quota, et pour rien quand le backlog n'était que des refills non urgents).

- **Dispatcher EDF** (`simulation_controller.py`) : les tâches de planification sont
  servies par échéance croissante (heure de départ simulée) via une file de priorité
  (`_edf_heap`) consommée par `world.worker_concurrency` tâches, au lieu du sémaphore
  FIFO. Une replanification urgente passe devant un refill d'horizon lointain ; un push
  déjà calculé (deadline 0) passe devant tout. Flag `world.edf_enabled` (défaut `true`,
  `false` = spawn direct historique). File vidée et consommateurs annulés au
  remplacement de scénario. Le sémaphore reste utilisé par le bootstrap.
- **Contre-pression prédictive** (`backpressure.py`, `application.py`) : le `/sync`
  n'est retenu que si le test de faisabilité EDF (`edf_feasibility` : `T_k = k/D` vs
  `slack_k = (d_k − now_sim)/R`, marge `world.predictive_margin`) annonce une échéance
  menacée — vitesse maximale sinon (le frein `cap·ratio^k` est court-circuité). Le débit
  `D` est une EWMA des complétions (`ThroughputEwma`, `tau` = `world.throughput_ewma_tau_s`,
  plancher `world.throughput_floor_per_s`), le rythme `R` une EWMA du `sim_wall_clock_ratio`
  figée pendant la rétention. Le mode drainage à hystérésis reste le filet de sécurité ultime.
- **Notification GAMA** (topic `system/throttle`, hystérésis) : au-delà de
  `world.throttle_notify_threshold_s` de rétention cumulée, Python pousse le débit LLM
  réel et la vitesse de simulation, rafraîchi toutes les `world.throttle_notify_refresh_s`,
  levé au premier `/sync` sans rétention. Globales GAMA `THROTTLE_ACTIVE` /
  `LLM_RATE_PER_MIN` / `SIM_RATIO_PYTHON` (`Settings.gaml`, `LLMAgent.gaml`).
- **Observabilité** : 6 nouvelles jauges Prometheus (`controller_throughput_tasks_per_min`,
  `controller_edf_queue_depth`, `controller_t_estimate_seconds`,
  `controller_min_slack_sim_seconds`, `controller_predictive_hold_seconds`,
  `controller_deadline_misses_total`), renseignées même contrôle prédictif désactivé
  (phase d'observation pour calibrer `tau` et la marge).

Doc : `docs/arch/agents-lifecycle.md` (§ Dispatcher EDF, § Contre-pression prédictive),
`docs/arch/monitoring.md` (métriques + réglages). Tests : `tests/test_backpressure.py`
(EWMA + faisabilité EDF), `tests/test_edf_dispatcher.py` (ordre EDF).

## Outil de debug — Rapport de santé du dernier run

- **`scripts/debug/run_report.py`** : génère un rapport markdown « agent-ready » condensant
  les signaux essentiels au debug d'un run (`experiments/current` par défaut) — top erreurs/
  warnings normalisés d'`app.log`, matrice santé LLM (erreurs par provider × statut HTTP,
  taux de 429), latence pipeline (percentiles + détection de backlog), activité des agents
  (inactifs dans le temps), décisions modales & fallbacks, arrivées & timeouts. Une section
  `🚨 ALARMES` en tête synthétise les anomalies franchissant les seuils (ajustables en tête
  de script). Stdlib only, tolérant aux fichiers manquants.
- Exposé via `make report [RUN=… OUT=…]` et la skill Claude `/debug-run`.
- Limite connue : ne lit que les artefacts sur disque ; les logs des conteneurs Docker
  (api, worker, otp, osmnx) ne sont pas encore centralisés dans `app.log` (chantier suivant).

## Logging centralisé par service + analyse capacité LLM + digest live GAMA

- **Logs centralisés par conteneur** : `configure_logging()` (`llm_module/telemetry/logger.py`)
  ajoute un sink fichier `APP_WORKDIR/<SERVICE_NAME>.log` (même format qu'`app.log`) quand
  `SERVICE_NAME` est défini. `docker-compose.yml` renseigne `SERVICE_NAME`/`APP_WORKDIR` pour
  `api` (→ `api.log`) et `worker` (→ `worker.log`) ; le controller garde `app.log`. Tous
  atterrissent dans le dossier du run et sont agrégés (avec tag `[service]`) par
  `scripts/debug/run_report.py`. Sinks non-Python (`otp*`, `osmnx*`, `redis`) : via
  `docker compose logs`.
- **`scripts/debug/llm_capacity.py`** (`make capacity`, skill `/debug-run`) : analyse
  « débit vs capacité » LLM du run, 100 % à partir des logs existants — demande avant/après
  micro-batching (agents/min vs prompts/min via le champ `response` de `llm_exchanges`),
  contre-pression prédictive EDF parsée depuis `[predictive]` (débit D, pile, T d'écoulement,
  `slack_min` = temps simulé restant sur la tâche critique), épisodes `[BACKPRESSURE]` /
  `[ALARME] Gateway`, et saturation 429 par minute et par provider. Section `🚨 ALARMES`
  en tête (risque d'échéance, saturation soutenue).
- **Digest de capacité poussé à GAMA** (`handle/application.py`) : tous les 10 `/sync`, le
  controller envoie sur `system/log` une ligne synthétique `📊 [cycle N] cache LLM … · débit
  … req/min · backlog … · agents actifs/inactifs`. Signaux cheaply available en-process
  (débit `throughput_per_s`, cache `get_llm_cache_stats`, états agents) ; émission gardée
  (n'échoue jamais un `/sync`). Intervalle : constante `_DIGEST_EVERY_N_SYNC`.

## Outil de debug — Analyse de la phase d'initialisation

- **`scripts/debug/init_report.py`** (`make init`, skill `/debug-run`) : rapport markdown
  ciblé sur le **démarrage** de la simulation, complémentaire de `run_report` (santé globale)
  et `llm_capacity` (débit LLM). Dérivé 100 % d'`app.log`, stdlib only, tolérant aux fichiers
  manquants. Contenu :
  - **Timeline des 5 étapes d'INITIALISATION** (SIM_START → INIT_DONE) avec la durée et la
    part de chacune ; repère l'étape dominante (quasi toujours le bootstrap `4/5`).
  - **Câblage & réchauffage des 3 caches persistants** (OTP, OSMnx, LLM sémantique) :
    activés ? chemins ? taux de hit atteint en fin d'init via la ligne de résumé combiné
    `[cache] OTP … · OSMnx … · LLM …` ; coût du chargement du modèle d'embedding.
  - **Bootstrap** : nombre d'agents pré-calculés, vagues d'anticipation, futurs déplacements
    pré-cachés, montée du taux de hit cache (cold → warm) et coût par type d'activité.
  - **Bugs d'init** avec section `🚨 ALARMES INIT` en tête : stalls de l'event loop
    (I/O synchrone du bootstrap → coupures WebSocket 1006), thrashing du cache métadonnées
    LTM (évictions + `gc.collect()` en boucle, `llm/longterm.py`), OD injoignables.
  - Exposé via `make init [RUN=… OUT=…]` et intégré à la skill `/debug-run`. Seuils
    d'alarme ajustables en tête de script.

## Cache LLM hybride et optimisation de la phase d'initialisation

L'init d'une population de 901 agents prenait ~19 min alors que les caches (OTP, OSMnx, LLM)
affichaient un taux de hit de ~100 % et que seuls 75 appels LLM réels avaient lieu. Le temps
était intégralement consommé par la machinerie entourant le cache, entièrement sérialisée :
un embedding `all-MiniLM-L6-v2` (~318 ms, sérialisé par `_embed_lock`) et une requête
ChromaDB de mémoire long terme étaient payés sur *chaque* décision, y compris les cache hits.

- **Cache sémantique LLM hybride.** Le lookup applique d'abord un filtre déterministe sur les
  conditions factuelles (agent, activité, catégorie de jour, tranche de 10 min, hash des
  options et de la météo), puis :
  - *LTM vide* (tout le bootstrap) : correspondance exacte par `scroll` clé-valeur, **sans
    embedding** (~0,1 ms contre ~324 ms). Sans souvenir, deux décisions prises dans les mêmes
    conditions sont identiques.
  - *LTM remplie* : recherche par similarité cosinus entre la mémoire courante de l'agent et
    celle qui a produit la décision stockée, avec rejet sous `cache.semantic_threshold`.
    L'agent tient donc compte de son vécu au lieu de rejouer indéfiniment sa première
    décision — ce que faisait l'ancienne clé, aveugle à la mémoire.
  Les deux familles de points sont étanches (`memory_empty` fait partie du filtre).
- **Le payload LLM (et sa requête ChromaDB) n'est plus construit sur le chemin nominal**
  quand la mémoire est vide : uniquement en cas de miss.
- **Nouveau champ de filtre `weekday`** : semaine et week-end ne partagent plus leurs décisions.
- **Fin du thrashing du cache métadonnées LTM** : `long_term_max_loaded_metadata` passe de 200
  à 5000 (nouveau réglage `agent.long_term_max_loaded_metadata`, jusqu'ici non câblé). En
  dessous du nombre d'agents, chaque décision provoquait une éviction. Le `gc.collect()` par
  éviction (~110 ms, exécuté dans l'event loop, ~2600 fois par init) est supprimé : il causait
  les stalls de la boucle asyncio (jusqu'à 148 s) et les coupures WebSocket 1006.

⚠️ Le filtre du cache gagne les champs `weekday` et `memory_empty` : les caches antérieurs ne
les portent pas et ne seront jamais retrouvés. Supprimer `data/llm_cache/` avant un run.

## Garde-fou TPM & débit des providers Groq

- **Réservation TPM glissante (60 s)** ajoutée au rate-limiter, en plus du RPM. `tpm_limit`
  devient un plafond dur appliqué avant chaque appel (réservation atomique RPM+TPM en un seul
  script Lua, restituée sur échec), et non plus un simple filtre de routage. Chaque provider
  expose `tpm_estimate_per_request = batch_max_agents × (assumed_prompt_tokens +
  assumed_output_tokens)`. Élimine le flot de **429** des providers dont le `rpm_limit`
  dépassait la capacité tokens réelle. Providers sans `tpm_limit` non bridés.
- **`groq_qwen` / `groq_llama31`** (free tier, TPM 6 000 → ~2 req/min) : `rpm_limit` ramené de
  60/30 à **2** et `weight` de 1.0 à **0.5**, alignés sur leur vraie capacité — ils causaient
  ~78 % des 429 pour une contribution marginale.

## Indicateur d'activités ratées faute de réponse LLM

- Nouveau compteur `agent_activity_decisions_total{outcome}` (issue de chaque activité
  planifiée : `llm`, `llm_fallback`, `single`, `no_solution`, `no_move`) émis au point de
  décision du contrôleur. Le **cockpit ③** (« Agents bloqués ») gagne une rangée : part et
  nombre d'activités dégradées faute de LLM (`llm_fallback` → index par défaut) et le débit
  fallback/min.
- Le **move-log** (`moves.csv`) porte désormais `ID Personne` et `ID Activité`. Le rapport de
  run (`run_report.py`, skill `/debug-run`) ajoute une section **« Couverture des activités
  par jour »** : les activités étant récurrentes et non datées, on vérifie que chaque activité
  d'un agent s'exécute chaque jour de sa plage — décomptant les activités *dégradées* (sans
  LLM) et *manquées* (aucune exécution ce jour-là), avec alarmes dédiées.
