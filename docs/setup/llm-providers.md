# Providers LLM

Configuration des fournisseurs LLM disponibles dans `config/llm_gateway/providers.yaml` (configuration de déploiement, hors du paquet ; désignée par `LLM_GATEWAY_PROVIDERS_FILE`).

La charge est distribuée entre les providers actifs selon leur `weight` via l'algorithme SWRR (Smooth Weighted Round Robin). Voir [docs/arch/llm-inference.md](../arch/llm-inference.md) pour le détail du mécanisme.

---

## Structure d'un provider

```yaml
providers:
  <nom_unique>:
    adapter: <openai|google|groq|cerebras|mistral>  # facultatif si = nom
    rpm_limit: 15              # requêtes par minute max
    tpm_limit: 200000          # tokens par minute (pour calcul batch_max_agents)
    rpd_limit: 500             # requêtes par jour (fenêtre UTC)
    tpd_limit: 2000000         # tokens par jour
    base_url: https://...      # endpoint de l'API
    default_model: gpt-4o-mini
    weight: 1.0                # poids de sélection SWRR = min(rpm, tpm/3000)/15
                               # 0 = HORS ROTATION : défini mais jamais tiré par le
                               # load balancer ; utilisable via `llm.provider` forcé
    concurrency_limit: 3       # batches simultanés max
    disable_timeout: 180       # durée (s) de mise à l’écart du provider après 30 erreurs consécutives (pas un timeout HTTP)
```

`batch_max_agents` est calculé automatiquement au démarrage :
`max(1, min(tpm_limit / tokens_per_agent, rpm_limit, max_batch_agents))`

---

## Mise à jour automatique des quotas — `make providers`

```bash
make providers            # sonde les providers et met à jour providers.yaml
make providers DRY_RUN=1  # affiche le bilan sans écrire
```

Le script `scripts/providers/refresh.py` relève les quotas **réels** et les écrit
dans le YAML (édition chirurgicale : commentaires préservés, écriture atomique).

Il gère aussi le **cycle de vie des modèles** (`GET /models` par adapter) :

- **Nouveau modèle texte opérationnel** → bloc provider ajouté en fin de fichier
  avec ses quotas relevés (daté). RPD ≥ 100 (constante `MIN_RPD_NEW_PROVIDER`) →
  **en rotation** avec weight calculé ; RPD plus faible (ex. gemini-3.6-flash à
  20 req/jour) → ajouté **hors rotation** (`weight: 0`), utilisable seulement en
  `llm.provider` forcé. Garde-fous : un modèle déjà référencé dans le fichier, **même commenté**, n'est
  jamais ré-ajouté (bloc commenté = décision humaine ou obsolescence datée) ; un
  modèle Google de la même famille de quota qu'une instance active est ignoré
  (ex. `gemini-3.1-flash-lite` stable partage le seau du `-preview` : l'activer
  doublerait la pression locale sur les 500 req/jour) ; les modèles Mistral ne
  sont jamais ajoutés (quota partagé par compte → aucun gain de capacité).
- **`default_model` disparu de `/models`** → bloc **commenté avec la date** et la
  raison, plus une `[ALARME]` dans le bilan (la capacité totale baisse).

Sources par adapter :

| Adapter | Source | Champs mis à jour |
|---------|--------|-------------------|
| mistral | 1 requête sonde (`max_tokens=1`) → en-têtes `x-ratelimit-*` | `rpm_limit` (borné à 60 : cadence doc 1 req/s), `tpm_limit`, `tpd_limit` (garde-fou, voir ci-dessous) |
| groq | idem — attention `x-ratelimit-limit-requests` = requêtes/**jour** | `tpm_limit`, `rpd_limit` (RPM et TPD absents des en-têtes → manuels) |
| cerebras | idem (granularités minute/heure/jour) | `rpm_limit`, `tpm_limit`, `rpd_limit`, `tpd_limit` |
| google | API Cloud Quotas (`gcloud auth print-access-token`, projet actif) | `rpm_limit`, `tpm_limit`, `rpd_limit` |
| openai | aucune (pas de clé) | — |

Le `weight` est recalculé (convention `min(rpm, tpm/3000)/15`) dès que
`rpm_limit` ou `tpm_limit` change, et `max_tokens_per_request` suit `tpm_limit`
quand le champ existe. Une sonde en échec laisse l'instance **intacte** et lève
une ligne `[ALARME]` dans le bilan (jamais d'assouplissement silencieux).

**Garde-fou Mistral** : le free tier est plafonné à **1 milliard de tokens/mois**
(quota non exposé par l'API, et aucun quota journalier côté Mistral). Pour éviter
de consommer le mois en une journée, le script force
`tpd_limit = 3 × (1 Md / 30) = 100 M tokens/jour` (facteur et quota mensuel :
constantes `MISTRAL_PRORATA_FACTOR` / `MISTRAL_MONTHLY_TOKENS` du script).

La doc Google (`ai.google.dev/gemini-api/docs/rate-limits`) ne publie plus les
tableaux par modèle — l'API Cloud Quotas est la seule source programmatique ;
les noms de quotas y sont des familles (`gemma-4-26b`, `gemini-3.1-flash-lite`),
mappées par plus long préfixe sur les `default_model`.

---

## Providers actifs

Quotas free tier relevés par `make providers` (2026-08-03) :

| Provider | Adapter | Modèle par défaut | RPM | TPM | RPD | TPD | Poids |
|----------|---------|-------------------|-----|-----|-----|-----|-------|
| `openai` | openai | gpt-4o-mini | 15 | 200K | — | 2M | 1.0 |
| `mistral` | mistral | mistral-small-latest | 60 | 500K | — | 100M† | 4.0 |
| `google_gemini31_key1` | google | gemini-3.1-flash-lite | 15 | 250K | 500 | — | 1.0 |
| `google_gemini35_key1` | google | gemini-3.5-flash-lite | 15 | 250K | 500 | — | 1.0 |
| `google_gemini31_key2` | google | gemini-3.1-flash-lite | 15 | 250K | 500 | — | 1.0 |
| `google_gemini35_key2` | google | gemini-3.5-flash-lite | 15 | 250K | 500 | — | 1.0 |
| `google_gemma42_key1` | google | gemma-4-26b-a4b-it | 30 | 16K | 14 400 | — | 0.36 |
| `google_gemma43_key1` | google | gemma-4-31b-it | 30 | 16K | 14 400 | — | 0.36 |
| `groq_llama3` | groq | llama-3.3-70b-versatile | 30 | 12K | 1 000 | 100K | 0.27 |
| `groq_llama31` | groq | llama-3.1-8b-instant | 2‡ | 6K | 14 400 | 500K | 0.13 |
| `groq_openai_120_key1` | groq | openai/gpt-oss-120b | 30 | 8K | 1 000 | 200K | 0.18 |
| `cerebras_gptoss120b_key1` | cerebras | gpt-oss-120b | 5 | 30K | 2 400 | 1M | 0.33 |
| `cerebras_zai-glm-4.7` | cerebras | zai-glm-4.7 | 5 | 30K | 2 400 | 1M | 0.33 |
| `cerebras_gemma_4_31b_key1`* | cerebras | gemma-4-31b | 5 | 30K | 2 400 | 1M | 0.33 |
| `groq_qwen_qwen3_6_27b_key1`* | groq | qwen/qwen3.6-27b | 30 | 8K | 1 000 | — | 0.18 |
| `google_gemini_3_flash_preview_key1`* | google | gemini-3-flash-preview | 5 | 250K | 20 | — | **0 (hors rotation)** |
| `google_gemini_3_5_flash_key1`* | google | gemini-3.5-flash | 5 | 250K | 20 | — | **0 (hors rotation)** |
| `google_gemini_3_6_flash_key1`* | google | gemini-3.6-flash | 5 | 250K | 20 | — | **0 (hors rotation)** |

† garde-fou local (3× le prorata journalier du milliard de tokens/mois), pas un quota Mistral.
‡ auto-restriction locale : le TPM 6 000 ne soutient que ~2 req/min (le vrai RPM Groq est 30).
\* ajoutés automatiquement par `make providers` le 2026-08-03 (seaux de quota indépendants : le gemma-4-31b Cerebras ne consomme pas le quota Google de `google_gemma43_key1`).

Cerebras applique aussi une limite **horaire** (150 req/h, 1 M tokens/h) non
modélisée dans le YAML. Mistral n'a pas de seau par modèle : le quota est
partagé entre tous les modèles du compte.

---

## Modèles locaux — LM Studio

Depuis le 2026-09-08, les modèles chargés dans LM Studio sur la machine hôte sont déclarés dans
`providers.yaml` comme des instances `lmstudio_<modèle>_key1` de l'adapter `openai_compatible`.
Aucun code : LM Studio parle le dialecte OpenAI sur `http://host.docker.internal:1234/v1`
(`localhost` désignerait le conteneur lui-même).

| Instance | `default_model` (identifiant `lms ls`) | Taille | Contexte max |
|---|---|---|---|
| `lmstudio_mistral_small_3_2_key1` | `mistralai/mistral-small-3.2` | 24B, 4 bit | 131k |
| `lmstudio_mistral_nemo_12b_key1` | `mistralai/mistral-nemo-instruct-2407` | 12B, Q4_K_M | 1M |
| `lmstudio_mistral_7b_v0_3_key1` | `mistralai/mistral-7b-instruct-v0.3` | 7B, Q4_K_M | 32k |
| `lmstudio_gemma_4_e4b_key1` | `google/gemma-4-e4b` | 7.5B (4B effectifs), Q4_K_M | 131k |
| `lmstudio_qwen3_vl_8b_key1` | `qwen3-vl-8b-instruct-mlx` | 8B, MLX 6 bit | 262k |
| `lmstudio_qwen3_vl_32b_key1` | `qwen3-vl-32b-instruct-mlx` | 32B, MLX 4 bit | 262k |
| `lmstudio_qwen3_8_27b_key1` | `qwen3.8-27b-local` (alias, voir ci-dessous) | 27B, MLX 4 bit | 262k |
| `lmstudio_muse_glimmer_28b_key1` | `meta/muse-glimmer` | 28B, Q4_K_M | 131k |

Toutes ont `weight: 0`, donc **hors rotation** : ni la cascade du mode GAMA ni une expérience
épinglée sur un autre modèle ne les sollicitent. Seule une expérience dont `decideur.modele` est
exactement leur `default_model` les utilise (`force_provider`). C'est voulu : un seul modèle est
chargé à la fois, et la cascade ferait charger les autres à la volée jusqu'à saturer la mémoire.

**Même identifiant qu'un fournisseur distant → alias local.** `qwen/qwen3.8-27b` est aussi le
`default_model` de `groq_qwen_qwen3_8_27b_key1`. L'épinglage se faisant par égalité de modèle, une
expérience sur ce nom tournerait sur Groq *et* en local : deux quantifications mélangées, et du quota
Groq consommé. Le modèle local se charge donc sous un alias qui devient son `default_model` :
`make lmstudio-charger MODELE=qwen/qwen3.8-27b IDENTIFIANT=qwen3.8-27b-local`. Sans ce chargement
explicite, LM Studio ne connaît pas l'alias et répond 404 (pas de chargement à la volée sous un alias).
Règle de l'alias : `<dernier segment de la clé>-local` — le tableau de bord retrouve la clé source en
retirant le suffixe et en cherchant la clé dont le dernier segment correspond.

**Depuis le tableau de bord** (`make dashboard`, onglet Expériences) : le décideur « modèle de langage
(local, LM Studio) » ne liste que ces modèles, avec leur taille et leur état dans LM Studio ; un bloc
« Modèle local » sous les services dit s'il est chargé et avec quel contexte, le charge d'un clic
(`make lmstudio-charger`, 16 384 jetons), décharge un voisin qui occupe la mémoire, et « Lancer »
reste grisé avec le motif tant que le modèle n'est pas prêt. Détails : `docs/arch/dashboard.md`.

Ce que LM Studio impose, vérifié le 2026-09-08 :

- **`structured_output: json_schema`** : `response_format: json_object` est refusé
  (« 'response_format.type' must be 'json_schema' or 'text' »). L'adapter envoie alors le format
  natif OpenAI (`json_schema` + `strict`), et `schema_in_system: true` recopie le schéma dans le
  message system par sécurité.
- **Le contexte se fixe au chargement**, 4 096 jetons par défaut : trop court pour un lot de deux
  agents (≈ 4 400 jetons de prompt) plus la réponse. `make lmstudio-charger MODELE=<id>` charge le
  modèle avec 16 384 jetons (`CTX=` pour changer). Un modèle déchargé après 1 h d'inactivité et
  rechargé à la volée par LM Studio repart à 4 096.
- **`wait_timeout: 600`** : combien de temps le CLIENT attend une tâche servie par cette
  instance. Réglage d'appelant, pas de routage — la passerelle ne le lit pas, elle le publie et
  le SDK le reçoit par appel (`execute(wait_timeout=…)`). Un modèle local ne sert qu'un appel à
  la fois : l'attente d'une tâche est celle de la FILE, pas de la génération. Au défaut de 120 s,
  toute tâche au-delà de la première expirait et le disjoncteur s'ouvrait (2026-09-08).
- **Le parallélisme d'une expérience se règle sur le nombre d'appels simultanés**, pas sur un
  débit par minute : 1 pour les modèles à `concurrency_limit: 1`. Mesuré sur Muse Glimmer,
  passer de 8 à 1 a fait monter le débit de 0,5 à 1,34 décision/minute et supprimé les attentes,
  parce que sans file chaque requête ne porte plus qu'une personne au lieu de deux.
- **Le lot est borné par `max_tokens_per_request: 6000`** (2 agents par requête), pas par
  `tpm_limit` qui briderait aussi le débit à la minute. `concurrency_limit` (2, ou 1 pour le 32B)
  est le vrai frein ; `rpm_limit: 30` n'est jamais atteint en local. Pas de quota journalier.

Activation : `PROVIDER_KEYS__lmstudio=lmstudio` dans `.env` (valeur libre, LM Studio ne vérifie pas
la clé) ; `docker-compose.yml` la propage à toutes les instances `lmstudio_*`. Vide ou absente, elles sont exclues au
démarrage. Une variable ajoutée à `.env` n'entre dans les conteneurs qu'à leur **recréation**
(`docker compose up -d --no-deps api worker`), pas à un simple `restart`. Ensuite
`make lmstudio-etat` montre les modèles chargés et ce que la passerelle voit.

Lancer une expérience sur un modèle local :

```bash
make lmstudio-charger MODELE=mistralai/mistral-small-3.2      # contexte 16 384
make experience-estimer EXP=exp_mistral-s-32_minper_jtir_p2_t0_nosim
make experience-lancer  EXP=exp_mistral-s-32_minper_jtir_p2_t0_nosim
```

Une définition existe pour chacun des huit modèles (`data/experiences/exp_<modèle>_minper_jtir_p2_t0_nosim`,
dérivées de `exp_qwen36-27b_minper_jtir_t0_nosim` avec `regroupement.parallelisme: 2` — le segment `p2` du nom le dit). Le temps
par requête doit rester sous les 120 s de l'adaptateur : si les journaux montrent des
`network_timeout`, passer `max_tokens_per_request` à 3000 (un agent par requête).

En mode GAMA (`make run OFFLINE=1 JEU=…`), la cascade ignore les instances à `weight: 0` : pour y
utiliser un modèle local, passer son `weight` à une valeur > 0 dans `providers.yaml` et blanchir les
clés distantes (`PROVIDER_KEYS__google="" … make run …`).

Ajouter un modèle téléchargé plus tard : copier une entrée `lmstudio_*`, recopier l'identifiant
de `lms ls` dans `default_model` (ou un alias, si cet identifiant existe déjà chez un fournisseur
distant), ajouter la ligne `PROVIDER_KEYS__lmstudio_<nom>_key1:
${PROVIDER_KEYS__lmstudio:-}` dans `docker-compose.yml`, recréer `api` et `worker`, puis dupliquer
une définition d'expérience avec `--decideur-modele <identifiant>`.

---

## Clés API

Les clés sont injectées via des variables d'environnement dans `.env`, **jamais** dans le YAML :

```
PROVIDER_KEYS__openai=sk-...
PROVIDER_KEYS__groq=gsk-...
PROVIDER_KEYS__google=AIza...
PROVIDER_KEYS__mistral=...
PROVIDER_KEYS__cerebras=...
PROVIDER_KEYS__lmstudio=lmstudio   # modèles locaux LM Studio : valeur libre, sert d'interrupteur
```

La résolution est `PROVIDER_KEYS__<nom_instance>`, puis repli sur `PROVIDER_KEYS__<adapter>`
pour une instance **non suffixée**.

### Convention de nommage : `<modèle>_key<N>`

Depuis le 2026-09-08, chaque instance porte son modèle et son rang de clé :
`google_gemini35_key1` et `google_gemini35_key2` sont le même modèle sur deux clés,
`google_gemini31_key1` et `google_gemini35_key1` deux modèles sur une seule.

Ce n'est pas cosmétique :

- **la clé physique se lit dans le nom.** Le garde-fou des expériences parallèles en déduit
  quelles instances se disputent le même quota (`experiences/cles.py`). Avant, `google2` et
  `google2_35` passaient pour deux clés distinctes alors que c'était la même ;
- **l'ordre de consommation devient lisible.** Les instances d'un modèle sont servies en série,
  triées par nom : `_key1` avant `_key2`. Avec les anciens noms, `google2` passait avant
  `google_gemini31` parce que « 2 » précède « _ » dans la table ASCII — le seau vidé en premier
  dépendait du nommage, pas d'une décision ;
- **une instance suffixée `_keyN` exige sa propre variable.** Pas de repli sur la clé de
  l'adaptateur : sans `PROVIDER_KEYS__<nom_instance>`, l'instance est écartée de la rotation et
  le démarrage le dit (`[ALARME]` si la clé de l'adaptateur existait, sinon un avertissement).
  Le repli silencieux avait déjà fait partir des appels sur la mauvaise clé.

Le mapping des 17 instances vers les 5 variables sources vit dans `docker-compose.yml` ; ce qui
s'édite dans `.env` reste les sources ci-dessus.

Les runs archivés portent les anciens noms — ce sont des mesures, elles ne se réécrivent pas.

---

## Sélectionner un provider dans la config d'expérience

Le fichier YAML de l'expérience peut forcer un provider spécifique :

```yaml
llm:
  provider: groq_llama3        # force ce provider pour toute la simulation
  model: llama-3.3-70b-versatile  # surcharge le modèle par défaut
```

Si `provider` est absent, le load balancer SWRR distribue entre tous les providers actifs.

---

## Ajouter un nouveau provider

1. Ajouter une entrée dans `config/llm_gateway/providers.yaml` (configuration de déploiement, hors du paquet ; désignée par `LLM_GATEWAY_PROVIDERS_FILE`)
2. Renseigner la clé dans `.env` : `PROVIDER_KEYS__<adapter>=...`
3. Si l'adapter n'existe pas encore, implémenter la classe dans `llm_gateway/src/llm_gateway/adapters/`
4. Lancer `make providers DRY_RUN=1` pour vérifier quotas et existence du modèle
