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

Le `max_tokens` envoyé par le client (défaut **8192** depuis le 2026-08-26, 4096 avant)
est un budget **par tâche** (1 agent). Le relèvement accompagne la justification **par
option** : mesurée sur 437 appels, la complétion valait 2 825 tokens en moyenne et
3 921 au pic pour des lots de 15 personas avec une seule raison par persona ; à
5,39 options par persona en moyenne (jusqu'à 9), une raison par option franchit 4096 et
se fait tronquer en silence.
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

#### Sortie du LLM : une distribution, pas un choix

Pour la catégorie `itinary_multi_agent`, le LLM **ne choisit plus** d'itinéraire : il
attribue à *chaque* option proposée la probabilité (en %) que le persona la retienne, la
somme valant 100. Le schéma (`llm_module/prompts/schemas.json`) exige donc un tableau
`probabilities` de `{index, mode, probability, reason}` — une entrée par option, `0` pour
une option jugée impossible — en lieu et place de l'ancien `chosen_index`.

**`reason` est passé du persona à l'option le 2026-08-26.** Le schéma portait une raison
unique par persona (« justifie la répartition en une phrase concise, en précisant si c'est
le cas pourquoi la marche n'obtient pas la plus forte probabilité ») : elle ne disait pas
pourquoi telle option perdait contre telle autre, et la clause sur la marche orientait la
justification vers un mode en particulier. La consigne est désormais « justifie la
répartition en une phrase concise par option », et chaque entrée de `probabilities` porte
sa raison — « une phrase justifiant la probabilité de CETTE option par rapport aux
autres ». Conséquence à ne pas oublier : la sortie est ~5 fois plus longue, d'où le
relèvement de `max_tokens` (voir ci-dessus).

Le post-traitement vit dans `llm_module/core/mode_choice.py`, partagé par tous les
consommateurs pour qu'ils appliquent la **même** politique de décision :

| Étape | Fonction | Rôle |
|---|---|---|
| Normalisation | `normalize_option_probabilities` | Doublons, valeurs négatives, somme ≠ 100, index renumérotés : le vecteur brut est ramené à une distribution sur les options réellement proposées (repli sur l'uniforme si rien n'est exploitable, tracé en `[ALARME]`) |
| Répartition | `mode_distribution` | Agrège les options par **mode canonique** (`walking`, `cycling`, `car`, `public_transport`, `train`, `motorbike`). Un mode qu'aucune option ne propose — la marche quand le trajet est trop long — reste présent à **0 %**, ce qui rend deux répartitions comparables |
| Tirage | `draw_index` | Tire une option proportionnellement à sa probabilité, avec une graine dérivée de `(agent.mode_draw_seed, agent_id, activity_id, jour simulé)` |

Le tirage a lieu **côté simulation** (`llm-agents`), sur la liste triée par code de plan :
il ne dépend donc pas du mélange anti-biais-de-position appliqué au prompt. Conséquences :

- **rejouabilité** — à graine égale, un run relancé reproduit exactement les mêmes trajets ;
- **variabilité réaliste** — le jour simulé entrant dans la graine, un même agent placé
  deux jours de suite dans le même contexte peut prendre sa voiture puis le bus ;
- **exploration gratuite** — changer `agent.mode_draw_seed` explore un autre tirage sans
  réappeler le LLM.

La répartition ayant servi au tirage est tracée **par demande d'itinéraire** dans
`moves.csv`, à raison d'**une colonne par mode** : `P(Marche) %`, `P(Vélo) %`,
`P(Voiture Privée) %`, `P(Transports_collectifs) %`, `P(Train) %`,
`P(Deux-roues motorisé) %`, `P(Autres modes) %` (somme = 100, directement agrégeables).
Distinguer deux cas à la lecture : **`0`** = le LLM a explicitement écarté ce mode ;
**cellule vide** = la décision n'a pas produit de répartition (mono-choix, absence
d'itinéraire, erreur LLM, point de cache hérité).

Le worker, lui, ne tire pas : il alimente `llm_transport_mode_chosen_total` et
`llm_chosen_index_total` avec l'option **la plus probable**, et cumule la masse de
probabilité par mode dans `llm_mode_probability_pct_total` (répartition *attendue*, que le
tirage reproduit en espérance). Une réponse à l'ancien format (`chosen_index`) reste
acceptée partout : elle est traitée sans tirage.

##### Une ligne « - [n] » = une option

Les options sont rendues en puces `- [n] mode: description`, et la description d'un
itinéraire détaille ses étapes. Ces étapes étaient rendues en puces `- ` de **même niveau**
que la ligne d'option : plusieurs modèles (mistral, llama 3.1, gemma) les lisaient comme
des options supplémentaires et renumérotaient le bloc entier — index `0..35` pour 6 options,
donc masse de probabilité placée **hors bornes** et décision perdue. Deux garde-fous :

1. **Rendu** (`itinary_multi_agent.md.j2`) — les étapes deviennent des sous-puces indentées
   « · », l'en-tête annonce le nombre d'options et la plage d'index, et la consigne finale
   rappelle que seules les lignes `- [n]` sont des options et que les index repartent de 0
   dans chaque bloc persona.
2. **Réalignement** (`normalize_option_probabilities(…, modes=…)`) — une entrée hors bornes
   est replacée sur l'option que **son libellé de mode** désigne (égalité de chaîne, puis
   égalité de mode canonique) ; si plusieurs options partagent ce mode, la masse est
   répartie entre elles — indéterminé quant à l'itinéraire, fidèle à la part modale.
   Sans `modes`, ou libellé non reconnu, la masse est écartée (tracée) plutôt que placée
   sur la mauvaise option. Les entrées hors bornes à probabilité nulle sont ignorées en
   `DEBUG` : elles ne coûtent rien et noyaient les vraies pertes.

Les deux appelants de production passent les modes **envoyés** (source de vérité) :
`llm_agent.py` depuis le payload rendu, `task_worker.py` depuis `spec.trajectories`. Rejoué
sur le run du 2026-07-29 (36 agents touchés), le réalignement ramène les replis uniformes de
12 à 1 et l'écart de part modale à l'intention du modèle de 0,41 à 0,02.

Le pipeline de calibration applique **le même** traitement à ses jeux gelés — rendu et
réalignement — sous le drapeau `prod_option_handling` (cf. `docs/arch/prompt_calibration.md`) :
sans lui, la mesure porterait sur un prompt que la production n'envoie plus.

Témoin complémentaire déjà en place : `llm_mode_label_mismatch_total` / `llm_mode_label_checked_total`
(mode annoncé ≠ mode de l'option, cf. `docs/arch/monitoring.md`) — même symptôme vu depuis
les index restés *dans* les bornes.

#### Contexte (météo/trafic) réinjecté par persona

Dans `itinary_multi_agent.md.j2`, le contexte factuel (météo, trafic) est rendu **à
l'intérieur de chaque bloc persona** (`**Contexte :** …` juste sous l'en-tête `--- agent_id=… ---`),
et non plus une seule fois en préambule commun au lot. La source par persona est
`agent.context` si elle est fournie, sinon le contexte partagé de la requête
(`request.context` puis `parameters.context`).

La météo est donc **portée par l'agent** (`AgentSpec.context`), plus par les `parameters`
de la requête : c'est `build_travel_plan_payload` (côté `llm-agents`) qui la place dans le
bloc agent. Comme la clé de batch (`compute_batch_key`) ne hache que `request.parameters`
(catégorie, params LLM, provider forcé, min-TPM), la météo n'y intervient plus : **des
demandes de météos différentes peuvent désormais être fusionnées dans un même appel LLM**,
chaque persona conservant la sienne dans le prompt. Le worker fusionne les agents des tâches
compatibles (`_execute_batch`) et rend le lot avec les `parameters` communs — corrects
puisque identiques par construction de la clé.

Le pipeline de calibration applique le **même format** d'injection
(`calibration/evaluation.py::inject_context`), pour que la mesure reflète exactement le
prompt de production.

#### Anticipation de la chaîne de la journée (ticket 014)

Le choix reste **trajet par trajet**, mais le bloc persona est enrichi de trois éléments
construits par le contrôleur (`_build_anticipation`, `simulation_controller.py`) et rendus
par `itinary_multi_agent.md.j2` :

- `**Météo plus tard :**` — la météo des tranches restantes de la journée
  (`day_weather_outlook`, tranches matin/après-midi/soirée du CSV météo), pour **tous**
  les agents : sortir le vélo le matin quand il pleuvra le soir devient un choix informé ;
- `**Trajets suivants prévus aujourd'hui :**` — l'agenda **glissant** des trajets restants
  (heure planifiée, motif, distance vol d'oiseau × 1,3, météo prévue si différente), en
  puces « · » pour ne jamais ressembler à une ligne d'option `- [n]`.

L'agenda n'est généré que pour les agents qui ont **quelque chose à chaîner**
(conducteurs possédant une voiture, possesseurs de vélo — jamais les passagers, dont la
voiture n'est pas positionnelle). Les trois verrous de chaîne (ticket 008) restent
inchangés : le bloc informe, il ne contraint pas.

**La position des véhicules n'est volontairement PAS énoncée dans le prompt.** La
première version portait une ligne « Vos véhicules : votre vélo est au domicile, avec
vous » : mesurée sur le run `2026-08-19_13_17`, elle a gonflé la part vélo de +5,5 points
(écart EMC² +13,8 → +19,6) — le libellé agissait comme une invitation, pas comme une
information, et la disponibilité réelle est déjà portée par le jeu d'options via les
verrous. La règle de chaîne vit désormais dans le **prompt système** (variante
`expert_chaine` de `prompts.yaml`, seed `expert`). Reformulée le **2026-08-26** : elle
énonçait « pense au stationnement et aux déplacements du reste de la journée, jusqu'au
retour au domicile », ce qui se lisait comme une obligation de garder le véhicule toute la
journée. Elle dit désormais la vraie contrainte — la **continuité de position** :

> l'usage d'un moyen de déplacement personnel conditionne l'ensemble de vos déplacements
> journaliers, car chaque nouveau trajet doit obligatoirement repartir du lieu de
> stationnement précédent. Il est donc nécessaire d'anticiper l'enchaînement de tous vos
> parcours prévus pour valider la faisabilité globale de la journée, même si certains
> trajets intermédiaires s'effectuent par d'autres moyens.

La dernière clause est celle qui manquait : laisser la voiture au travail et aller déjeuner
à pied est un enchaînement valide, que l'ancienne formulation décourageait. Cette phrase
est un **segment calibrable** (à couvrir par le catalogue de mutations), pas une constante. La colonne `Anticipation` de `moves.csv`
trace ce que le prompt de chaque trajet contenait (`agenda` / `meteo` / vide), et la
**signature** déterministe des textes entre dans la clé du cache de décisions (cf.
`docs/arch/cache-memory.md`). Flag : `settings.agent.agenda_anticipation_enabled`
(défaut `True` ; `False` rétablit le prompt myope pour l'A/B).

#### Le bloc persona allégé — 2026-08-26

La ligne `Mobilité : … | … | …` a été **retirée**, et avec elle `Contraintes : None`. Ce
que chacun portait, et pourquoi il part :

| Élément | Sort | Motif |
|---|---|---|
| `car_availability` + statut de conducteur | retiré | le jeu d'options dit déjà si la voiture est prenable (`_owns_car` / `_can_drive`), et le canal narratif a été **mesuré puis rejeté** : +0,12 pt de part voiture, au niveau du bruit (ticket 018) |
| vélo personnel | retiré | même raison ; l'option vélo n'est proposée que si le vélo est là |
| abonnement TC | **déplacé sur l'option** | il n'est *pas* déductible du jeu d'options — une option bus existe qu'on soit abonné ou non — mais il ne pèse que là où un TC est offert |
| `Contraintes : None` | retiré | littéral codé en dur (`constraints = "None"`, TODO d'origine), jamais implémenté : mesuré constant sur **2 487 records sur 2 487** |

Ne reste que l'identité sociale — prénom, âge, occupation, taille du foyer, revenu — seule
information que les options ne portent pas.

L'abonnement s'accole à la **première ligne** de la description de l'option
(`_pt_subscription_note`, `llm_agent.py`), jamais aux sous-puces « · » : collé à une étape,
il passerait pour une étape.

```
- [0] foot,bus,foot: Temps de trajet : 1 h 36, dont 13 minutes de marche. Pas d'abonnement aux transports en commun.
    · Marche jusqu'à 'Mairie Aussonne' : 3 minutes.
```

⚠ **Deux pertes assumées.** (1) Un agent possédant un vélo garé ailleurs n'a pas d'option
vélo, et le prompt ne dit plus qu'il en possède un — comme il ne peut pas s'en servir,
l'information ne portait aucune décision. (2) Les libellés de voiture n'étaient pas
binaires (« peut conduire, voiture à partager dans le foyer, conditionné par la
nécessité », « sans permis et seul·e au foyer »…) : ces nuances ne se déduisent pas de la
seule présence d'une option voiture. Elles disparaissent.

Ordre de grandeur de ce qui change : la phrase « ne conduit pas : se déplace en voiture
uniquement en passager·ère… » portait sur **384 records sur 1 810 (21,2 %)** du jeu gelé,
dont 330 de mineurs — un enfant de 5 ans s'y voyait décrire comme passager d'une voiture
toujours disponible.

⚠ **À mesurer avant d'être crédité d'un gain.** La campagne du ticket 024 a établi que le
modèle réagit à la **mise en forme** du contexte plus qu'à son contenu : son témoin nul de
reformulation coûte 2,03 de composite, plus que le retrait de *tout* le contexte (2,52).
Retirer des segments et rendre une mention conditionnelle sont des changements de mise en
forme : leur effet se lit contre ce plancher-là, pas contre zéro.

#### Météo : résolution de 3 h, rafales et verglas — 2026-08-26

**La lecture du moment passe de quatre relevés à huit.** La source porte 0, 3, 6, 9, 12,
15, 18 et 21 h ; le code n'en lisait que quatre (3, 6, 12, 18 h), si bien qu'un départ à
11 h recevait la météo de 6 h et un départ à 17 h celle de 12 h. Or **le code météo diffère
entre 12 h et 15 h sur 159 jours sur 365** : pour les trajets d'après-midi, le prompt
annonçait couramment un temps qui n'était plus celui-là.

Deux rôles sont désormais séparés, et ils ne doivent pas être confondus :

- `_reading_bucket` — **huit** créneaux, le relevé le plus proche en arrière de l'heure de
  départ. C'est la météo du moment ;
- `_BUCKET_ORDER` — **quatre** tranches, délibérément laissées grossières : la ligne
  « Météo plus tard » et le cadre du jour (amplitude, créneaux précipitants). Les affiner
  en même temps referait le paquet de deux changements du bras `v10c` (ticket 023), que la
  mesure n'a pas su départager.

**Le bulletin porte deux aléas de plus**, au franchissement d'un seuil seulement :

- `rafales à N km/h` si `WINDSPEED_MAX_KMH` ≥ **30** (vent frais, Beaufort 5) ;
- `risque de verglas` si le minimum du jour est sous **3 °C**.

Les deux viennent du bras `v10c` rejeté, où ils annotaient *chaque étape* — emplacement
inadapté pour le vent, qui est un **maximum journalier** et se répétait donc à l'identique
partout. Le bulletin est sa place.

```
Météo : 2°C, Partiellement nuageux. Aujourd'hui 2°C à 11°C, lever 06:41, coucher 19:18, rafales à 33 km/h, risque de verglas. Pas de précipitations prévues.
```

Une journée sans aléa garde sa phrase **mot pour mot**, et un jeu gelé antérieur au
2026-08-26 — dépourvu du champ `wind_max_kmh` — se relit à l'identique : sinon sa
ré-évaluation ne porterait plus sur ce qui a été mesuré. Un test le verrouille, comme il
verrouille l'égalité de la phrase entre `weather_loader.py` (production) et
`calibration/weather.py` (jeux gelés).

#### Une date météo par agent — variance du régresseur (`weather_per_agent_dates`) — 2026-08-26

Le ticket 023 a mesuré le bulletin météo enrichi « à pleine masse » et conclu à aucun
effet. La cause est instrumentale, pas substantielle : **sur une seule journée simulée,
les 1 000 agents partagent une seule météo** — le régresseur a une variance nulle, et
« aucun effet mesuré » ne veut alors rien dire.

`urban_mobility_agents/utils/weather_draw.py` (activé par `Settings.weather_per_agent_dates`,
désactivé par défaut) tire, pour chaque agent, un jour de l'année dans la fenêtre déclarée
par `Settings.weather_window` (`"enquete"` par défaut — la fenêtre de collecte EMC²,
lue depuis `llm_module.core.population_reference`, pas recopiée en dur), et ne substitue
que la **date** du bulletin lu par `weather_loader.get_weather` : l'heure du départ est
conservée (le bulletin se lit par créneaux de 3 h, cf. ci-dessus), et tout le reste de la
simulation — horaires GTFS, véhicules, itinéraires, agendas — reste sur la journée
simulée. Le tirage est une fonction pure de `(weather_draw_seed, person_id)` : deux runs
identiques produisent exactement les mêmes météos.

C'est un dispositif distinct du jeton d'exclusion / bulletin enrichi du ticket 023 : celui-ci
porte sur la fenêtre météo des **jeux gelés de calibration** (hors ligne), quand
`weather_per_agent_dates` porte sur le tirage météo **en simulation GAMA**, pour rendre
l'effet météo mesurable sur un run donné plutôt que de le confondre avec l'absence de
variance de l'instrument.

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
  drainage — armée quand le backlog atteint `drain_trigger_ratio` (défaut 80 %) de la
  population, **mais ne crie que sur une vraie saturation de décisions** (ticket 010) :
  départs servis en retard (`late_since_last_sync > 0`) ou tâches plan/refill dont
  l'échéance sim est dépassée. Un backlog dominé par des réflexions STM ou des
  pré-planifications à échéance lointaine pendant la nuit simulée est le **drainage
  nominal** : log INFO avec composition (`N décisions (dont X à échéance dépassée) +
  M réflexions STM`), pas ERROR — cf. run 2026-08-03 où l'alarme criait au feu sur un
  embouteillage bénin (803 tâches, late=0, cache 99 %, providers sains). L'ERROR donne
  la composition, le `min_interval` appliqué et les coefficients `min_internal_coeff_*` ;
  elle est aussi poussée vers la console GAMA et se réarme quand le backlog repasse
  sous `drain_release_ratio` (défaut 20 %). Logique pure et testée :
  `backpressure.backlog_alarm_transition()`.

### Panne durable — disjoncteur client : on attend le renouvellement

Les mécanismes ci-dessus absorbent les incidents **courts** (un provider en cooldown,
une rafale de 429). Une **panne durable** — pénurie de tokens (tous les quotas
journaliers épuisés), gateway ou réseau coupé pendant des heures — posait deux
problèmes distincts :

1. **Gâchis** : chaque décision brûlait une tentative vouée à l'échec (8 s d'attente
   de slot + retries worker, ou 120 s de poll timeout côté client) avant d'échouer.
2. **Intégrité scientifique** : chaque échec dégénérait la décision en « premier
   itinéraire de la liste » (`llm_fallback`) — sur 24 h de rupture, un biais modal
   massif et non maîtrisé dans `moves.csv`.

Le **disjoncteur client** (`llm_module/sdk.py`, réglages
`agent.remote_llm_circuit_failure_threshold` / `remote_llm_circuit_probe_interval`)
répond aux deux en choisissant **l'attente, pas la dégradation** : après N échecs
consécutifs (défaut 10) — **erreurs réseau incluses** (gateway injoignable, 5xx à la
soumission), qui échappaient auparavant au comptage — les soumissions LLM sont
**suspendues**. Aucune tâche n'échoue, aucune décision n'est prise hors du chemin
nominal (cache exact ou LLM) : les appelants attendent, et la contre-pression `/sync`
existante retient GAMA en conséquence (le temps simulé n'avance plus tant que les
décisions ne reviennent pas — cf. mode drainage). L'un des appelants suspendus devient
périodiquement la **sonde** (demi-ouvert, toutes les `probe_interval` secondes, défaut
60 s) : au premier succès — renouvellement des quotas à minuit UTC, retour du service —
le disjoncteur se referme et **toutes les soumissions suspendues repartent**, avec de
vraies décisions LLM. Aucun redémarrage, aucune intervention.

Observabilité : `[ALARME]` sur front montant à l'ouverture
(`alarme_total{source="gateway_llm_circuit"}`), gauges Prometheus
`llm_gateway_circuit_open` et `llm_gateway_circuit_waiters` (soumissions en attente),
log INFO à la fermeture avec la durée de la panne.

`remote_llm_circuit_failure_threshold: 0` désactive le disjoncteur (comportement
historique : chaque décision échoue après son timeout puis part sur l'index par
défaut `llm_fallback`).

### Instrumentation d'un appel Google (Gemini)

Un appel structuré peut échouer de trois façons qui se ressemblent toutes de
l'extérieur — « ça n'avance plus » — et se soignent différemment. L'adaptateur Google
relève donc **trois grandeurs sur chaque appel**, avant toute levée d'exception :

| Grandeur | Ce qu'elle tranche |
|---|---|
| **Tokens de complétion** (`candidatesTokenCount` + `thoughtsTokenCount`) | Plafond `maxOutputTokens` sous-dimensionné, ou non |
| **`finishReason`** | `STOP` (le modèle a fini) vs `MAX_TOKENS` (tronqué) vs `SAFETY` (bloqué) |
| **Latence** de l'appel | Génération réellement longue vs échec instantané |

Elles sont tracées en DEBUG à chaque appel, et **rappelées dans le message de chaque
exception** — un timeout dit combien de temps il a attendu et quel budget il demandait,
une troncature dit combien de tokens ont été produits pour quel plafond.

> **Les tokens de raisonnement comptent dans la sortie.** `thoughtsTokenCount` est
> facturé **et** décompté du plafond `maxOutputTokens`. Il est donc additionné aux
> tokens de complétion dans le `tokens_out` renvoyé au worker : l'ignorer sous-estimait
> la consommation réelle et masquait la cause d'une troncature sur les modèles à
> raisonnement.

**Alarme de troncature.** Une troncature isolée est un aléa (WARNING). Au-delà de
**3 troncatures `MAX_TOKENS` consécutives** sur la même instance de provider,
l'adaptateur lève une ERREUR `[ALARME]` — sur **front montant** : une seule par
épisode, réarmée par la première complétion propre. Sans ce signal, le retry de
l'appelant rejoue la même troncature à l'identique jusqu'à épuisement (le décodage
étant quasi-déterministe à température 0), sans qu'aucune ligne ne le dise.

**Le timeout de 240 s n'est pas la contrainte usuelle.** Mesuré le 2026-07-31 sur
`gemini-3.1-flash-lite-preview`, lots de 15 personas avec distribution complète par
persona : **3,6 à 8,8 s** par appel et **2 742 tokens** de complétion au pire. Deux
ordres de grandeur de marge. Ne pas le rallonger sans mesure : un appel réellement
bloqué doit finir par rendre la main.

### Réponse valide mais incomplète

Un piège propre aux appels **multi-agents** : le modèle peut rendre un JSON
parfaitement valide, conforme au schéma, `finishReason=STOP`, très en deçà du plafond
de tokens — et pourtant **amputé d'une partie des agents demandés**. Mesuré le
2026-07-31 sur `gemini-3.1-flash-lite-preview` : sur 12 lots de 15 personas, **4 lots
n'ont rendu que 5 à 8 décisions sur 15** (dont un à 1 287 tokens de complétion pour
4 096 autorisés).

**Réduire la taille du lot atténue le phénomène mais ne l'élimine pas.** Sur un rejeu
complet à 8 personas par lot (372 requêtes de base), les lots incomplets restent
courants — jusqu'à un lot ne rendant qu'**1 persona sur 8**. La taille de lot est donc
un levier de coût, pas une garantie de complétude.

Aucune des défenses habituelles ne voit ce cas : ce n'est ni une erreur HTTP, ni une
troncature, ni un défaut de schéma. **C'est à l'appelant de comparer ce qu'il a demandé
à ce qu'il a reçu** — le nombre d'agents envoyés contre le nombre de décisions rendues —
puis de redemander les manquants dans une requête plus petite. Voir
[prompt_calibration.md](prompt_calibration.md) pour la façon dont le moteur de
calibration s'en protège (re-tir par moitiés, puis garde de couverture).

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
  backlog `[ALARME]` est armée au même seuil, mais ne passe en ERROR que si des
  décisions sont réellement en souffrance, cf. « Alarmes de saturation »).
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
