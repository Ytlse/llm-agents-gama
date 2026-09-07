# Batching, SWRR, disjoncteur

Trois mécanismes décident, pour chaque lot, *avec qui* il part, *quand*, et *à quelle
taille*. Ils partagent un même but : tirer le maximum de fournisseurs free tier aux quotas
petits et hétérogènes, sans jamais dégrader une décision.

## Micro-batching

**La clé de lot.** `compute_batch_key(request)` = `<catégorie>:MD5(catégorie, parameters
triés, force_provider, min_tpm_required)`. Deux requêtes ne fusionnent que si elles sont
parfaitement compatibles : même template, mêmes paramètres (donc même `prompt_variant`,
même `max_tokens`), même contrainte de provider. `context` n'entre **pas** dans la clé : il
est réinjecté dans chaque bloc d'agent par le template mobilité.

**La file.** Une file Redis par clé, triée par score de priorité (plus bas = plus urgent).
Le score vient de la catégorie ; sans catégorie qui en définit, la constante de repli
9 999 999 999 place le lot en fin de file. Le worker dépile les plus urgentes d'abord.

**La fenêtre.** Côté API, si la file atteint `get_dispatch_threshold` — `batch_target_agents`
(10) borné par le plus gros `batch_max_agents` des providers, ou la capacité exacte du
provider forcé — le dispatch est immédiat. Sinon un flag `SETNX` (TTL = `batch_delay_seconds`
+ 30) garantit qu'exactement un dispatch différé de `batch_delay_seconds` (3 s) est planifié,
quel que soit l'ordre d'arrivée des requêtes concurrentes. Les 3 s viennent d'une mesure :
inter-arrivée des prompts p50 = 1,4 s sur le run 2026-07-10 ; 1 s ne captait presque rien.

**Le plafond au pop.** Côté worker, la taille réelle du lot est `batch_max_agents` **du
provider sélectionné** :

```
tokens_per_agent  = assumed_prompt_tokens + assumed_output_tokens        # 2 200 + 800 = 3 000
batch_max_agents  = max(1, min(tpm_limit // 3 000  (ou rpm_limit si pas de TPM),
                               max_tokens_per_request // 3 000  (ou max_batch_agents),
                               rpm_limit, max_batch_agents = 20))
```

Mistral (500 000 TPM, 60 RPM) → 20 ; `google_gemma42` (16 000 TPM) → 5 ;
`groq_openai_120` (8 000 TPM) → 2. C'est pourquoi le seuil de dispatch ne prend pas le
*minimum* des providers (1, à cause des petits TPM) : la fenêtre d'accumulation ne jouerait
jamais. Après un lot réussi, s'il reste des tâches dans la file, le worker relance
immédiatement un `process_batch_task` pour la même clé.

## SWRR — Smooth Weighted Round-Robin

`core/selection.build_swrr_sequence(weights)` construit une séquence de rotation une fois :
100 créneaux répartis proportionnellement aux poids (au moins un par provider), entrelacés
à la manière de NGINX pour éviter les rafales sur un même fournisseur. `{"mistral": 4.0,
"openai": 1.0, "google_gemini31": 1.0}` donne une séquence où Mistral revient deux fois sur
trois, jamais deux fois d'affilée si un autre est disponible. Le `LoadBalancer` garde un
curseur circulaire sous verrou ; **`weight: 0` retire le provider de la séquence** (hors
rotation, utilisable seulement en `force_provider`).

La convention de poids est dans `providers.yaml` : `weight = min(rpm, tpm / 3000) / 15`. Le
poids suit la capacité réellement soutenable, pas le RPM affiché.

**Sélection.** `select_provider(force, min_tpm, min_output)` parcourt la séquence à partir
du curseur ; pour chaque candidat : provider connu, `tpm_limit ≥ min_tpm` (si les deux sont
définis), `max_output_tokens ≥ min_output` (idem), puis `limiter.try_reserve`. Le premier qui
réserve gagne. Aucun sur un tour complet → `RuntimeError` « Tous les fournisseurs LLM sont
saturés… », que le worker gère par attente locale (`provider_wait_seconds`, un essai toutes les
`saturation_poll_seconds`) puis `saturation_retries` réessais. Ensuite, **occupé n'est pas en
panne** : si un provider éligible n'est ni en cooldown, ni désactivé, ni au quota du jour, le lot
continue d'attendre la fenêtre (borné par `max_retries`) au lieu d'être abandonné ; il n'est
échoué que si tous sont réellement indisponibles, ou si `abandon_when_busy` l'impose.

## Réservation RPM/TPM atomique

`RedisRateLimiter.try_reserve` vérifie d'abord, hors script : pas désactivé, pas en
cooldown, `active_workers < concurrency_limit`, quota du jour non épuisé, RPM courant sous
la limite. Puis **un script Lua** fait en une opération :

1. **lissage** : refus (`-1`) si la dernière requête date de moins de `min_interval = 60 /
   rpm_limit` secondes — pas de rafale en début de fenêtre ;
2. **réservation TPM** : `INCRBY tpm:<p>` des tokens estimés dans la fenêtre glissante 60 s
   ; dépassement → rollback et refus (`0`) ; ignoré si pas de `tpm_limit` ;
3. **réservation RPM** : `INCR rpm:<p>` ; dépassement → rollback des deux et refus ;
4. horodatage de la dernière requête.

La réservation TPM initiale est le forfait `tpm_estimate_per_request = batch_max_agents ×
3 000`, posé avant de connaître le contenu du lot. Une fois le prompt rendu, le worker la
**recale** sur le coût réel estimé (`caractères / token_chars_ratio` + `n_agents ×
assumed_output_tokens`) ; après la réponse, il la recale sur la consommation facturée. Un
appel échoué **restitue** RPM et TPM (`release_slot`) pour que les erreurs ne consomment pas
de quota. Si le réel dépasse la réservation de plus de 25 %, un WARNING invite à revoir
`token_chars_ratio` / `assumed_output_tokens`.

**Quotas journaliers.** `rpd_limit` est compté à la réservation (`rpd:<p>:<jourUTC>`),
`tpd_limit` a posteriori sur les tokens réels (`record_tokens`). Le premier dépassement pose
un flag `quota_exhausted:<p>` avec TTL jusqu'à minuit UTC : le provider sort de la rotation
sans être re-sondé toutes les `disable_timeout` secondes.

## Cooldown, désactivation, bascule

Trois durées d'exclusion, du plus court au plus long :

| Mécanisme | Déclencheur | Durée | Où |
|---|---|---|---|
| **cooldown** | 5xx ou troncature → 60 s ; 429 → délai annoncé par le provider (borné à [10, 3600] s, défaut 60) ; bascule → `provider_switch_cooldown_seconds` (30 s) | clé Redis `cooldown:<p>` à TTL | `try_reserve` refuse tant que la clé existe |
| **désactivation** | 30 appels échoués consécutifs (`record_failure`) | `disable_timeout` du provider (180 s par défaut, 120 pour la plupart des instances) ; compteur remis à zéro | `disabled:<p>` à TTL ; `llm_provider_state` = 1 |
| **quota du jour** | `rpd_limit` ou `tpd_limit` atteint | jusqu'à minuit UTC | `quota_exhausted:<p>` |

**La bascule** (`_switch_provider_or_fail`) traite les erreurs qui tiennent au *modèle*
plutôt qu'à sa charge : réponse hors schéma, 4xx non récupérable, prompt trop volumineux pour
la capacité par requête. Le fautif reçoit le cooldown court, le lot retourne en file et est
rejoué sans `force_provider` ; la rotation choisit alors un autre modèle. Au plus
`min(max_retries, len(providers) − 1)` bascules, puis échec définitif : une requête
réellement invalide ne boucle pas.

Côté client, le **disjoncteur du SDK** joue le rôle symétrique : après 10 échecs consécutifs
il suspend les soumissions (sans les faire échouer) et re-sonde toutes les 60 s ; la
simulation attend le renouvellement des quotas plutôt que de remplacer les décisions du
modèle par un repli ([SDK Python](../reference/sdk-python.md)).

## Apprentissage de `max_output_tokens`

Le `max_tokens` envoyé au provider est `min(parameters.max_tokens (défaut 4096) × n_agents,
settings.max_output_tokens (16 384), provider.max_output_tokens)`, puis rogné pour tenir
dans `max_tokens_per_request − prompt_estimé` (`_fit_request_budget`) ; si même
`min_output_tokens` (512) ne tient plus, `ProviderCapacityError` avant l'appel — le 413 est
évité et le lot part ailleurs (38 HTTP 413 sur le run 2026-07-11 ont motivé ce garde-fou).

Quand un provider répond 400 « `max_tokens` must be less than or equal to N » (Groq),
« supports at most N completion tokens » (OpenAI) ou « … limited to N » (Google), le worker
**apprend N** : `learn_provider_max_output_tokens` met la config du processus à jour et
réécrit la ligne `max_output_tokens: N  # auto-ajusté le AAAA-MM-JJ (HTTP 400 du provider)`
dans `providers.yaml` (édition chirurgicale, commentaires préservés, écriture atomique), puis
rejoue le lot après 1 s. Si la limite était déjà connue, pas de retry : bascule. Le fichier
réécrit est celui **du paquet installé** (hypothèse H8) — en développement et dans les
conteneurs c'est le fichier du dépôt, monté ; sur une installation en wheel ce serait
`site-packages`, et un système de fichiers en lecture seule produit une `[ALARME]` sans
bloquer le lot.
