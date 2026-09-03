# Ticket 005 — Politique de choix modal statistique (PROGEDO 2023)

Alternative non-LLM à la sélection d'itinéraire, entraînée sur l'enquête EMC² Toulouse 2023
(ProGEDO / lil-1750). Objectif : disposer d'un **bras de comparaison** crédible face à
l'agent LLM, dans le même simulateur, avec la même population et le même graphe OTP.

**Origine** : les agents non-LLM prennent aujourd'hui `plan_index = 0`
(« Hard to choice, just pick the first one », `simulation_controller.py`), ce qui ne
constitue pas une référence défendable. Les notebooks `scripts/progedo_logit/` ont établi
qu'un modèle exogène prédit correctement le mode ; il reste à en faire une politique
servie en simulation.

**État d'avancement** : phase 1 livrée le 2026-07-29 (§6), phase 3a le 2026-07-30 (§2.2),
phase 2 le 2026-07-31 (§7), réglage des hyperparamètres le 2026-08-30 (§9).

---

## 0 · Registre des décisions

### Décisions adoptées

| # | Décision | Détail |
|---|---|---|
| E1 | **Usage = bras de comparaison** (et non repli, ni prior de prompt) | La politique pilote les agents non-LLM ; le run A/B est le livrable |
| E2 | **LightGBM** comme politique servie | Retenu pour la performance prédictive, cohérent avec les notebooks d'exploration existants |
| E3 | Le modèle est assumé comme **oracle** sur les parts modales | Entraîné sur la même enquête que la cible de calibration `cerema_values.yaml` : il les reproduit par construction. Présenté comme borne supérieure, pas comme comparaison loyale |
| E4 | `od_km` (centroïdes ZF, mode-neutre) remplace `D12`/`D11` | Correctif central — voir §1 |
| E5 | Pondération par `COEP` (coefficient de redressement personne enquêtée) | L'objectif est de reproduire des *parts* : un entraînement non pondéré les biaise |
| E6 | Split **par ménage** (`hh_id = ZF_ECH`) | Un split par déplacement fuit : plusieurs déplacements du même individu |
| E7 | Pas de `is_unbalance` / `class_weight` | Détruit la calibration (cf. précision vélo 0.14 pour rappel 0.61 du smoke test). Métriques de sélection : log-loss, ECE, L1 sur parts par cellule — **pas** l'accuracy |
| E8 | Contrat de features versionné `feature_spec.json` | Seule garantie contre le train/serve skew — voir §2 |
| E9 | Évaluateur **pur Python** du booster exporté au runtime | Le conteneur `controller` est un `python:3.12-slim` sans `libgomp1` : `import lightgbm` y échouerait. Voir §3 |
| E10 | Renormalisation sur le choice set offert par OTP | C'est l'hypothèse **IIA**, assumée et documentée |
| E11 | **Réglages cherchés, pas posés** — arbres peu profonds et nombreux | Banc `tune_mode_choice_policy.py`, 96 configurations distinctes en CV groupée par ménage *dans le train*. `num_leaves` 31 → 5 : le vélo gagne significativement en vraisemblance sans que le log-loss global ni la L1 des parts modales bougent. Voir §9 |

### Décisions écartées (et pourquoi)

| Idée | Raison du rejet |
|---|---|
| Arbre de décision unique comme politique servie | Probabilités constantes par feuille, mal calibrées, forte variance. Conservé en profondeur 4 **uniquement** comme instrument d'interprétation (SHAP + carte de règles) |
| Logit multinomial comme politique servie | Écarté au profit de LightGBM (E2). Reste la référence attendue du domaine — à mentionner en limite d'article |
| Injection des règles dans le prompt système (U3) | Sans objet : un GBM n'est pas verbalisable. L'usage sort du périmètre |
| Pré-remplissage du cache LLM par le modèle | Mélangerait deux sources de décision dans un artefact déjà difficile à auditer |
| `distance_km` (D12) comme feature | Fuite démontrée — §1 |
| Repondérer les classes pour redresser le vélo | Toujours écarté (E7), et le banc du §9 le vérifie plutôt que de le supposer : son garde-fou écarte d'office toute configuration qui dégrade la L1 des parts modales de plus de 0,005. Le gain vélo est venu de la capacité, pas du poids |

---

## 1 · Le correctif central : la distance

`prepare_progedo_logit.ipynb` exporte `distance_km = D12/1000` comme feature de contexte.
`explore_progedo_walk_shapley.ipynb` §7 démontre que cette variable est contaminée :

- **D11 pour la marche** vaut exactement `durée déclarée × 58 m/min` (constant des quantiles
  5 à 95), et ne compte que 258 valeurs distinctes contre 9 824 pour la voiture ;
- corrélation avec la distance géographique : 0.99 pour vélo/voiture/transit, **0.40** pour
  la marche.

Coût mesuré, même modèle, seule la variable de distance changeant :

| variable de distance | PR-AUC marche |
|---|---|
| D12 (réseau du mode utilisé) | 0.985 |
| D11 (vol d'oiseau déclaré) | 0.985 |
| `od_km` (centroïdes ZF, mode-neutre) | 0.804 |

Une prédiction quasi parfaite d'un phénomène social signale une fuite, pas un bon modèle.

**Aggravation côté simulation** : au moment du choix il n'existe pas de « distance du
trajet » — il existe *k* options OTP ayant chacune la sienne. Utiliser la distance d'une
option reviendrait à injecter la réponse. La seule distance calculable des deux côtés est
la distance origine→destination à vol d'oiseau, mode-neutre.

Coût assumé : `od_km` n'est calculable que pour les déplacements dont les deux zones fines
sont dans le périmètre d'enquête (~51 % des déplacements).

---

## 2 · Le contrat de features (`feature_spec.json`)

Une feature n'entre dans le modèle que si elle est calculable **à l'instant de la décision
en simulation**. Trois sources :

| Source | Features |
|---|---|
| `traits_json` du persona | `age`, `gender`, `household_size`, `has_driving_license`, `has_pt_subscription`, `number_of_cars`, `car_availability`, `has_bike` (dérivé de `personal_bike`), `socioprofessional_class`, `main_occupation`, `employed`, `studies` |
| Contexte de l'activité | `purpose`, `purpose_origin` (motif de l'activité précédente), `departure_hour`, `weekday` |
| Géométrie (coordonnées + zones fines) | `od_km`, `same_zone`, `dist_center_orig_km`, `dist_center_dest_km`, `density_orig`, `density_dest` |

Sont **exclues** malgré leur pouvoir prédictif, faute d'équivalent runtime :
`education_level`, `hh_relationship`, `secondary_occupation`, `n_children`, `n_bikes`,
`bikes_per_person`, `n_motorbikes`, `cars_per_licensed`, `housing_type`, `housing_tenure`,
`car_night_parking`, `works_from_home`, `commute_crow_km`, `car_avail_commute`,
`car_parking_work`, `n_stops_tour`, `survey_month`, ainsi que tout le Block B (fréquences
d'usage déclarées).

Le fichier `feature_spec.json` fige la liste, l'ordre, le type et les modalités
catégorielles. Il est lu à l'entraînement **et** au runtime : toute divergence lève une
erreur au chargement plutôt que de produire silencieusement des prédictions fausses.

Les couches géographiques (densité par ZF, distance à l'hypercentre) doivent être
embarquées comme ressource de données pour être disponibles en simulation.

### 2.1 · La jointure spatiale est obligatoire, pas optionnelle

Vérifié le 2026-07-29 sur `data/population/toulouse_population_1000.json` :

- `geopandas==1.1.3` est **déjà** dans `llm-agents/requirements.txt` : la jointure
  spatiale est disponible dans le conteneur `controller`, sans dépendance nouvelle ;
- **95,5 %** des localisations de la population et **95,1 %** des paires
  origine-destination consécutives tombent dans la couche ZF. La contrainte de périmètre
  ne bloque donc pas en simulation, contrairement aux 49 % perdus à l'entraînement
  (l'enquête contient des déplacements sortant du périmètre, la population synthétique
  vit dedans — ce qui confirme le biais de sélection décrit au §6).

**Le piège `od_km`.** En simulation on dispose des coordonnées exactes, donc la tentation
est de calculer une distance haversine origine→destination. Ce serait faux : à
l'entraînement `od_km` est une distance **entre centroïdes de zones fines**, avec
imputation `0.5 × √surface` en intra-zone. Écart mesuré entre les deux définitions sur la
population simulée :

| | distance exacte | formule d'entraînement |
|---|---|---|
| médiane globale | 2.98 km | 3.36 km |
| corrélation | 0.989 | |
| **intra-zone (16,8 % des paires)** | **0.65 km** | **1.29 km** |

L'écart global paraît bénin, mais sur les trajets intra-zone c'est un facteur 2 — or ce
sont exactement les trajets courts où marche, vélo et voiture sont en concurrence, donc là
où le modèle décide réellement, et `od_km` est de loin sa première feature.

→ Le runtime **doit** répliquer la formule d'entraînement : rattachement du point à sa
zone fine, distance entre centroïdes, imputation intra-zone. Une fois cette jointure
faite, `density_*` et `dist_center_*` en dérivent gratuitement. La phase 3 doit donc
exposer un `ZoneResolver` unique (point → zone, centroïde, surface, densité, distance au
centre), plus un repli explicite pour les ~5 % de localisations hors couche.

**Approximation par centroïde le plus proche : rejetée.** Embarquer seulement un tableau
des 785 centroïdes (et rattacher chaque point au plus proche) aurait évité la couche
polygonale et la dépendance `geopandas`. Mesuré sur les 2 403 localisations distinctes de
`toulouse_population_1000.json` :

| mesure | résultat |
|---|---|
| accord avec l'appartenance réelle au polygone | **72,9 %** |
| écart médian entre les deux centroïdes en cas de désaccord | 1,19 km (p95 : 4,03 km) |

Un point sur quatre mal rattaché, avec un déplacement médian de 1,19 km sur un `od_km` de
médiane 3 km : la première feature du modèle serait corrompue. La cause est géométrique —
le centroïde le plus proche revient à un découpage de Voronoï, qui ne ressemble pas à des
zones administratives allongées, non convexes et très inégales en taille. **La jointure
point-dans-polygone est donc requise.**

**Le repli hors périmètre est un cas net.** Les 5,1 % de localisations non couvertes sont à
22,8 km en médiane (p95 : 42,6 km) de la zone la plus proche : ce sont des communes
franchement extérieures, pas des cas limites au bord du périmètre. La détection est donc
sans ambiguïté, et le repli n'a pas à arbitrer de rattachement approximatif.

**Hypercentre : deux définitions concurrentes.** La phase 1 le calcule comme centroïde des
zones du secteur 01 (lat 43.5973 / lon 1.4450) ; `move_logger.py` codait en dur
43.6047 / 1.4442 — 820 m d'écart. La valeur doit être écrite dans `feature_spec.json` et
lue de là, jamais redéclarée. **Résolu le 2026-07-30 (action A9)** :
`llm_module/core/geo_reference.py` est l'unique point de lecture du bloc `geo_reference`
du spec — il sert à la fois le garde-fou de `ZoneResolver.load` (§2.2) et les couronnes de
résidence du move-log, et se replie sur la valeur publiée recopiée en constante quand le
spec est absent (données PROGEDO d'accès restreint). Les couronnes déjà écrites dans les
`moves.csv` archivés restent celles de l'ancien centre : la colonne est figée à la
journalisation, seuls les runs postérieurs changent.

### 2.2 · Le résolveur livré (2026-07-30, action A7)

`llm_module/core/zone_resolver.py` expose le `ZoneResolver` demandé ci-dessus, servi par
une ressource dérivée `llm_module/data/zf_zones.gpkg` que produit
`scripts/progedo_logit/export_zone_layer.py` (`make zones`).

Deux choix structurent l'implémentation :

- **La ressource n'est pas recalculée**, elle est exportée en réutilisant le `build_geo()`
  du constructeur du jeu d'entraînement. Densités, centroïdes et distances au centre sont
  donc identiques par construction à celles vues à l'entraînement — impossible de faire
  diverger les deux définitions. Le fichier `zf_zones.meta.json` recopie le bloc
  `geo_reference` produit par `build_geo` ; `ZoneResolver.load(feature_spec=…)` le compare
  à celui du spec et lève au chargement en cas d'écart. C'est le garde-fou contre les deux
  hypercentres concurrents ci-dessus.
- **La ressource est dérivée, pas la source.** `data/PROGEDO 2023/` porte les microdonnées
  d'accès restreint, n'est pas versionné et n'est pas monté dans le conteneur
  `controller` ; la couche exportée ne contient que des agrégats à la zone et vit sous
  `llm_module/`, déjà monté partout où le résolveur tourne. Elle reste hors dépôt
  (`.gitignore`), au même titre que sa source, et se régénère avec `make zones`.

`geopandas` n'entre pas dans les dépendances de base de `llm_module` — le gateway et le
worker n'en ont pas l'usage. Il est déclaré en extra `geo`, et le conteneur `controller`
l'a déjà par `llm-agents/requirements.txt`.

**Couverture mesurée avec le résolveur livré**, sur `toulouse_population_1000.json` :

| mesure | résultat |
|---|---|
| localisations rattachées (toutes occurrences) | 95,5 % (4 685 / 4 907) |
| localisations rattachées (points distincts) | 94,9 % (2 280 / 2 403) |
| paires origine-destination exploitables | 95,1 % (3 694 / 3 886) |
| `od_km` médian, formule d'entraînement | 3,36 km (distance exacte : 2,98 km) |
| dont intra-zone (16,8 % des paires) | 1,29 km (distance exacte : 0,65 km) |

Les valeurs reproduisent celles du §2.1 : le résolveur calcule bien ce que le modèle a vu
à l'entraînement, facteur 2 intra-zone compris.

**Densité manquante, jamais imputée.** 81 des 785 zones n'ont aucun ménage enquêté, et
concernent 5,5 % des paires exploitables. `density_*` y vaut `None` et non `0` : le
booster route nativement les valeurs manquantes, là où un `0` affirmerait « zone déserte ».

**Alarme de couverture.** Le résolveur suit son taux hors couche et émet un
`logger.error("[ALARME] …")` au-delà de 15 % sur au moins 200 rattachements (front montant,
réarmé sous 8 %) : une population hors périmètre rendrait les features géo massivement
manquantes sans qu'aucune erreur ne remonte. Le compteur Prometheus `fire_alarme` n'est
volontairement pas appelé ici — `llm_module.core` est importé par le processus API, où la
famille `alarme_total` est déjà émise par le collecteur Redis.

---

## 3 · Sérialisation et service

`lightgbm` et `scikit-learn` sont présents dans le `.venv` local mais **absents de
`llm-agents/requirements.txt`**. Le conteneur `controller` est bâti sur `python:3.12-slim`,
sans `libgomp1` : un `pip install lightgbm` s'y installerait mais échouerait à l'import.

Deux options :

- **A** — ajouter `lightgbm` aux dépendances **et** `libgomp1` au `Dockerfile`. Simple,
  au prix d'un rebuild d'image et d'une dépendance C++ dans le conteneur de simulation.
- **B** (retenue, E9) — exporter le booster (`dump_model()`) en JSON et écrire un
  évaluateur pur Python (~120 lignes : traversée d'arbres, routage des valeurs manquantes,
  catégorielles). Aucune dépendance ajoutée, artefact diffable en git, coût négligeable
  devant les ~100 ms d'un appel OTP.

**Garde-fou obligatoire de l'option B** : un test de parité prédit 5 000 lignes held-out
avec LightGBM et avec l'évaluateur, et exige `max|Δ| < 1e-9`. Sans ce test, l'approche ne
tient pas et on bascule sur l'option A.

---

## 4 · De P(mode) aux poids sur options

Le pipeline n'attend pas une distribution sur les modes mais un vecteur de poids sur les
*k* options OTP — plusieurs options partagent souvent un mode. Trois étapes :

1. **Prédiction** : `P(mode)` sur les 4 classes ProGEDO (`car`, `bike`, `walk`, `transit`) ;
2. **Restriction et renormalisation** sur les modes réellement offerts (hypothèse IIA, E10) ;
3. **Allocation intra-mode** entre les options partageant un mode.

Limite structurelle à documenter : `CANONICAL_MODES` compte 6 modes côté simulation
(`walking`, `cycling`, `car`, `public_transport`, `train`, `motorbike`) là où le recodage
ProGEDO en fusionne certains (`train` dans transit, `motorbike` dans car). Ces deux modes
sont donc **structurellement inaccessibles** à la politique statistique.

---

## 5 · Phases

| Phase | Livrable | État |
|---|---|---|
| 1 | `scripts/progedo_logit/build_mode_choice_dataset.py` → parquet + `feature_spec.json` | **livrée** (§6) |
| 2 | `scripts/progedo_logit/fit_mode_choice_policy.py` → `mode_choice_policy.json` | **livrée** (§7) — script versionné et non notebook ; la carte de règles reste à faire |
| 3a | `llm_module/core/zone_resolver.py` + `scripts/progedo_logit/export_zone_layer.py` | **livrée** (§2.2) |
| — | `scripts/synthesis/model_on_common_set.py` → prédictions sur le jeu commun, renormalisées sur l'offre OTP | **livrée** (§8) — hors pipeline : c'est la page de synthèse qui consomme, pas la simulation |
| 3b | `llm_module/core/mode_choice_model.py` (pur, testé) + test de parité | à faire |
| 4 | `settings.agent.mode_choice_policy: "llm" \| "model" \| "llm_with_model_fallback"` | à faire |
| 5 | Run A/B, `docs/arch/mode-choice-model.md`, changelog | à faire |

Phase 4 — le branchement conserve le format actuel de `moves.csv` (la répartition par mode
est écrite telle quelle) afin que les outils d'analyse existants fonctionnent sans
modification. `selection_method` distingue les bras.

Phase 5 — mesures des deux bras à population, graphe OTP et graine identiques : parts
modales, **parts par cellule motif × distance × âge** (dimensions absentes de
`cerema_values.yaml`, donc non triviales sous l'hypothèse oracle E3), distances parcourues,
courbe de charge horaire, coût et latence.

---

## 6 · Résultats de la phase 1 (2026-07-29)

`build_mode_choice_dataset.py` produit `progedo_mode_choice_v2.parquet` et
`feature_spec.json` (spec v1, 21 features, 4 classes).

**Volumétrie** — 54 585 déplacements au départ, 27 886 retenus. La perte (−49 %) vient
presque entièrement de l'exigence `od_km` : les deux zones fines doivent être dans le
périmètre d'enquête. C'est le coût assumé de E4.

**Parts modales du jeu retenu**

| mode | brut | pondéré COEP | `cerema_values.yaml` (agglo) |
|---|---|---|---|
| car | 54.8 % | 56.0 % | 55 % |
| walk | 31.5 % | 30.1 % | 26 % |
| transit | 9.7 % | 9.8 % | 12 % |
| bike | 4.0 % | 4.1 % | 4 % |

**Réserve sur l'hypothèse oracle (E3)** : l'écart sur la marche (+4 pts) et sur les
transports collectifs (−2 pts) n'est pas du bruit — il vient de la restriction au
périmètre d'enquête, qui surreprésente les zones denses où l'on marche davantage. Le jeu
d'entraînement n'est donc **pas** représentatif de l'agglomération entière : la politique
sera un oracle sur une sous-population, pas sur la cible de calibration. À écrire tel quel
dans l'article, et à garder en tête en phase 5 lors de la comparaison des deux bras.

**Vérification de la fuite (smoke test LightGBM multiclasse, split par ménage)**

| mesure | valeur |
|---|---|
| log-loss | 0.5432 |
| accuracy | 0.7987 |
| L1 sur parts modales (test, pondéré) | 0.0329 |

Les valeurs sont plausibles pour un phénomène social — à comparer aux PR-AUC de 0.985
obtenues avec la distance contaminée. **E7 est validé** : sans aucune repondération de
classe, les parts prédites s'écartent de 3,3 points cumulés des parts observées, là où le
`class_weight="balanced"` du notebook d'origine produisait une précision vélo de 0.14.

Importances (top) : `od_km`, `age`, `density_dest`, `density_orig`,
`dist_center_orig_km`, `dist_center_dest_km`, `departure_hour`. Les quatre variables
géographiques pèsent lourd — elles devront être embarquées comme ressource de données
pour la phase 3 (cf. §2).

---

## 7 · Résultats de la phase 2 (2026-07-31, action A6)

> **Réglages dépassés depuis le 2026-08-30 (§9).** Les chiffres de cette section décrivent
> le modèle à 31 feuilles entraîné sur le spec v1 (20 901 lignes de train). Ils sont conservés
> tels quels : c'est l'état à partir duquel le §9 mesure.

`scripts/progedo_logit/fit_mode_choice_policy.py` (`make policy`) entraîne le booster et
écrit `mode_choice_policy.json` + `mode_choice_policy_metrics.json`. Script versionné et
non notebook : la reproductibilité est le livrable, pas la narration. La cible `make policy`
n'exige **pas** les données PROGEDO brutes — le parquet et le spec sont dans le dépôt.

**Réglages** — `multiclass` à 4 classes, `learning_rate` 0.05, `num_leaves` 31,
`min_data_in_leaf` 50, `feature_fraction` 0.9, `lambda_l2` 1.0, aucune repondération de
classe (E7). `deterministic` + `force_row_wise` + graines fixées : deux exécutions
produisent un booster identique à l'octet. Arrêt anticipé (patience 50, plafond 2 000) sur
une part de validation de 20 % **redécoupée dans le train, par ménage** — arrêter sur le
test reviendrait à le sélectionner. Retenu : **79 itérations**, soit 316 arbres.

**Split** — lu dans la colonne `split` du parquet, jamais refait (étanchéité ménage
vérifiée : 0 `hh_id` commun). Train 20 901, test 6 985.

**Test (6 985 déplacements, pondéré COEP)**

| mesure | valeur | smoke test §6 |
|---|---|---|
| log-loss | **0.5363** | 0.5432 |
| accuracy | **0.7947** | 0.7987 |
| L1 parts modales, masse de probabilité | **0.0210** | — |
| L1 parts modales, mode élu | **0.0871** | 0.0329 |

Les deux premières lignes confirment le smoke test. La quatrième **ne le confirme pas** :
0.0871 contre 0.0329 annoncés. Les réglages diffèrent (le smoke test n'est pas décrit), et
l'écart vient du durcissement — l'argmax d'un classifieur bien calibré exagère les classes
dominantes et écrase le vélo. La mesure utile pour le pipeline est celle en masse de
probabilité (0.0210), puisque c'est une distribution, et non un mode élu, qui est
consommée en aval (§4). Le chiffre du §6 est conservé tel quel plutôt que réécrit.

**Parts modales (test, pondérées)**

| mode | observé | masse de probabilité | mode élu |
|---|---|---|---|
| car | 56.2 % | 57.3 % | 60.6 % |
| walk | 29.8 % | 29.5 % | 29.3 % |
| transit | 10.2 % | 9.7 % | 8.9 % |
| bike | 3.8 % | 3.5 % | 1.2 % |

Le vélo est la classe où le durcissement coûte le plus : 3.5 % en masse contre 1.2 % en
mode élu, pour 3.8 % observés. **E7 tient** : sans repondération de classe, la masse de
probabilité reste calibrée. Une repondération améliorerait le rappel vélo en détruisant
exactement ce qui sert ici.

**Contrôle de fuite, mesuré** — mêmes réglages, en ajoutant `distance_km` et
`duration_min` aux variables :

| variables | log-loss | accuracy |
|---|---|---|
| les 21 du spec | 0.5363 | 79.5 % |
| + `distance_km`, `duration_min` | **0.2397** | **92.1 %** |

Le régime de fuite est donc parfaitement reconnaissable, et le modèle livré n'y est pas.
C'est le contrôle qui manquait pour affirmer que les chiffres du §7 décrivent un
phénomène social et non une réponse recopiée.

**Importances (gain)** — `od_km` 37.2 %, `has_pt_subscription` 7.9 %, `number_of_cars`
7.7 %, `same_zone` 5.7 %, `dist_center_orig_km` 5.7 %, `dist_center_dest_km` 5.1 %,
`car_availability` 3.9 %, `age` 3.4 %. Aucune variable ne domine au point de faire
soupçonner une fuite : `od_km` à 37 % est attendu et mode-neutre par construction (E4).

**L'artefact est autoportant.** `mode_choice_policy.json` embarque `format` et
`format_version` (structure), `spec_version` (contrat de features), l'ordre exact des 21
variables, la table modalité → code de chaque catégorielle, l'ordre des 4 classes, le bloc
`geo_reference` recopié, les métriques, et le booster sous **deux** formes : `dump_model`
pour l'évaluateur pur Python de la phase 3b (E9), et `model_text` pour un rechargement
exact via `lgb.Booster(model_str=…)` là où la bibliothèque est disponible. Un consommateur
prédit sans jamais relire le parquet — c'est ce qu'a fait l'action A8 (§8). Taille : 6,8 Mo
indentés.

**Encodage** — catégorielle → index dans la liste fermée du spec ; modalité inconnue →
manquante, **jamais** un code de repli ; booléen → 0/1 ; valeurs manquantes non imputées
(le booster les route, et `density_*` est légitimement absente pour 81 zones sur 785).

**Tests** — `scripts/tests/test_mode_choice_policy.py` verrouille l'exclusion des variables
`diagnostic_only`, l'ordre des variables et des classes de l'artefact, la conformité de la
table d'encodage, et le rechargement + prédiction sur des lignes fabriquées depuis le seul
spec (probabilités ≥ 0 sommant à 1 sur les 4 classes). Aucun ré-entraînement du vrai
modèle : skip propre si l'artefact est absent, modèle jouet de quelques arbres sinon.

**Reste à faire** — la carte de règles annoncée en phase 2 (arbre de profondeur 4 +
SHAP, instrument d'interprétation seulement) n'est pas produite. `lightgbm` et
`scikit-learn` sont déclarés dans `scripts/requirements.txt`, volontairement **pas** dans
`llm-agents/requirements.txt` (E9).

---

## 8 · Première application hors enquête (2026-07-31, action A8)

`scripts/synthesis/model_on_common_set.py` (`make common-set-predict`) applique la
politique aux **5 945 décisions du run épinglé** de la page de synthèse, hors ligne et de
façon déterministe. C'est la première mise à l'épreuve de la chaîne complète — artefact
autoportant (§7), résolveur de zone fine (§2.2), renormalisation sur l'offre (§4) —
ailleurs que sur le split test de l'enquête.

**§4 étape 2, mesurée.** La restriction à l'offre OTP puis la renormalisation (hypothèse
IIA, E10) portent sur une masse réelle : 96,6 % de la probabilité prédite tombe en moyenne
sur des modes effectivement proposés (médiane 99,8 %, minimum 0,8 %). La correction déplace
le mode le plus probable sur 142 décisions et ramène l'écart cumulé aux parts EMC² de 17,9
à 14,1 points. Elle n'est donc ni négligeable ni dominante.

**La limite structurelle du §4 se paie, et de façon dissymétrique.** `train` est rangé dans
`transit` par la politique et dans les transports collectifs par la référence EMC² : les
deux s'accordent. `motorbike` est rangé dans `car` par la politique et dans « autres » par
la référence, qui l'exclut du périmètre scoré : compter une offre deux-roues comme une
offre de voiture gonflerait la part voiture du seul modèle. Elle est donc **retirée de
l'offre**. Le run épinglé n'en propose aucune — le cas est traité par contrat, pas par
constat.

**Le vélo se comporte comme au §7.** En masse de probabilité les parts prédites restent
plausibles ; en mode élu, le durcissement l'écrase (6,5 % contre 3,8 %, et 25,98 points de
L1 global contre 14,1). Les deux lectures sont publiées, pour la même raison qu'au §7 : la
distribution est ce que le pipeline consomme, l'argmax ce qu'un lecteur pressé regarderait.

**Couverture du résolveur : 100 % sur ce run**, contre 95,1 % annoncés au §2.2. Ce n'est
pas une contradiction — les 95 % ont été mesurés sur `toulouse_population_1000.json`, un
autre tirage de population. Les 11 890 localisations du run épinglé tombent toutes dans le
périmètre d'enquête. Le repli « pas de zone » reste posé et testé.

**Un écart de vocabulaire à trancher.** 15,5 % des décisions n'ont pas de
`socioprofessional_class` : la population synthétique porte `Retired`, que le recodage
`SOCIPRO` de la phase 1 ne produit jamais (les retraités y tombent dans `Other Inactive`).
L'encodage la rend manquante, conformément au contrat — jamais un code de repli. Le choix
est conservateur et documenté plutôt que corrigé à l'aveugle : `main_occupation`
= « Retraité » porte la même information et, elle, est dans le spec. À trancher pour la
phase 3b, où la même divergence se présentera à chaque décision.

**Tests** — `scripts/tests/test_model_on_common_set.py` verrouille la correspondance des
quatre vocabulaires de modes (y compris la divergence `motorbike`), la renormalisation et
ses cas limites (offre vide, mode unique, masse nulle sur l'offre), le refus de charger un
artefact dont le contrat, l'ordre des variables ou l'ordre des classes diverge du spec, la
cyclicité de la chaîne d'activités, et la génération de la page quand le parquet est
absent.

---

## 9 · Réglage des hyperparamètres (2026-08-30)

**Question de départ** : peut-on améliorer les modes sous-représentés — le vélo, 4,3 % des
déplacements — sans repondérer les classes, puisque E7 l'interdit ?

**Réponse : oui, en réduisant la capacité du modèle.** Les réglages d'origine n'avaient
jamais été cherchés. `scripts/progedo_logit/tune_mode_choice_policy.py` (`make policy-tune`)
les a cherchés sur **96 configurations distinctes** (114 essais : la référence et les
gagnants sont rejoués d'une passe à l'autre), en validation croisée à 5 plis par ménage
**entièrement à l'intérieur du train** — le split test n'est jamais lu par le banc, et
l'arrêt anticipé est refait dans chaque pli.

**Le diagnostic qui oriente tout.** Le vélo n'a pas un problème de repondération : sa masse
de probabilité manque de 13 %, pas d'un facteur. Ce qui lui manque est du pouvoir
discriminant — PR-AUC 0,241 contre 0,78 à 0,93 pour les trois autres modes. Un déficit de
discrimination ne se corrige pas en poussant la classe vers le haut. Le rappel argmax du
vélo (0,16) ne mesure d'ailleurs presque rien d'autre que sa prévalence : sur une classe à
4 %, l'argmax d'un classifieur calibré s'effondre par construction. Les critères retenus
sont donc la **NLL restreinte à la classe** et la **PR-AUC un-contre-tous**.

**Garde-fou** : toute configuration dégradant la L1 des parts modales de plus de 0,005 est
écartée d'office, quel que soit son gain sur le vélo — 22 des 49 configurations de la
première passe y sont tombées. C'est ce qui empêche la recherche de redécouvrir la
repondération de classes par une porte dérobée.

**Ce qui a été trouvé : le modèle était en sur-capacité.** Deux passes successives ont fait
sortir leurs gagnants sur la borne *basse* de `num_leaves` (15, puis 7) — un optimum sur un
bord de grille n'en est pas un. Une troisième passe à réglages figés a localisé le plateau,
une quatrième a relevé le plafond de tours parce que `num_leaves = 3` l'atteignait sans que
l'arrêt anticipé se déclenche (chiffre tronqué, pas convergé).

| `num_leaves` | log-loss | NLL vélo | PR-AUC vélo | L1 parts | ECE | tours |
|---|---|---|---|---|---|---|
| 31 *(avant)* | 0,5403 | 2,5380 | 0,2410 | 0,0117 | 0,0180 | 122 |
| 10 | 0,5308 | 2,3878 | 0,2713 | 0,0069 | 0,0098 | 672 |
| **5** *(retenu)* | **0,5324** | **2,3430** | **0,2757** | **0,0050** | **0,0078** | **1 461** |
| 3 | 0,5367 | 2,3334 | 0,2751 | 0,0044 | 0,0078 | 2 297 |

**Réglages retenus** — `learning_rate` 0,015 · `num_leaves` 5 · `min_data_in_leaf` 10 ·
`feature_fraction` 0,5 · `bagging_fraction` 0,9 (`freq` 1) · `lambda_l1` 0,5 ·
`lambda_l2` 10 · `cat_smooth` 50 · `min_data_per_group` 50 · `path_smoothing` 5.
Arrêt anticipé à **1 500 itérations**, soit 6 000 arbres. Plafond porté de 2 000 à 4 000
tours pour qu'il reste franchement au-dessus de l'arrêt réel.

Beaucoup d'arbres peu profonds valent mieux ici que peu d'arbres profonds : une classe à
4,3 % ne peuple pas assez les feuilles d'un arbre à 31 feuilles pour que sa probabilité y
soit estimée sur autre chose que du bruit.

**Test (13 045 déplacements, 2 349 ménages, pondéré COEP)** — bootstrap apparié par ménage,
2 000 tirages :

| mesure | avant | après | Δ | IC 95 % | verdict |
|---|---|---|---|---|---|
| log-loss global | 0,5392 | 0,5402 | +0,0009 | [−0,0048, +0,0066] | dans le bruit |
| L1 parts modales | 0,0236 | 0,0269 | +0,0033 | [−0,0043, +0,0089] | dans le bruit |
| **NLL vélo** | 2,4222 | **2,3512** | **−0,0710** | [−0,1331, −0,0075] | **significatif** |
| NLL voiture | 0,3267 | 0,3337 | +0,0070 | [+0,0022, +0,0120] | significatif |
| NLL transport collectif | 0,7928 | 0,7939 | +0,0011 | [−0,0211, +0,0219] | dans le bruit |
| NLL marche | 0,5917 | 0,5903 | −0,0014 | [−0,0149, +0,0105] | dans le bruit |

Le seul effet net est un **transfert de vraisemblance de la classe dominante vers la classe
rare** : le vélo gagne 0,071, la voiture perd 0,007 — un ordre de grandeur d'écart, et la
voiture part de dix fois moins haut. ECE global 0,0142 → 0,0118 ; NLL macro (les 4 modes à
égalité) 1,0333 → 1,0173.

**Les gains de CV ne se retrouvent pas tels quels sur le test**, et c'est reporté ainsi
plutôt que lissé. La CV note chacune des 39 203 lignes du train hors-échantillon ; le test
est un tirage unique de 13 045 lignes. La CV a servi à choisir — c'est le protocole ; le
test est le chiffre de généralisation, et il donne la borne prudente.

**Prix payé** — 6 000 arbres au lieu de 560, artefact 18,9 Mo au lieu de 12,2, prédiction
43,9 µs/ligne au lieu de 9,9. Sans conséquence pour le pipeline actuel ; le point de
vigilance est **l'évaluateur pur Python de la phase 3b** (E9), pas encore écrit, qui
traversera environ six fois plus de travail. Repli documenté si ce coût gêne :
`num_leaves = 10`, 2 688 arbres, les trois quarts du gain vélo.

**Ce que le réglage ne corrige pas** — le vélo reste à 1,2 % en mode élu pour 4,0 %
observés, avant comme après : c'est une propriété de l'argmax sur une classe rare (§7), pas
un défaut du modèle. Et le vélo reste la classe la plus mal séparée des quatre ; ce qui lui
manque tient probablement à une variable absente du spec, pas à un hyperparamètre.

**Traces** — [`docs/traces/2026-08-30_reglage_lightgbm/`](../traces/2026-08-30_reglage_lightgbm/)
archive les quatre passes, les métriques avant/après et le bootstrap.

---

## 10 · Audit du jeu d'entraînement (2026-08-31)

`scripts/progedo_logit/explore_mode_choice_dataset.ipynb` exporte le parquet en deux CSV
(`mode_choice_train.csv`, `mode_choice_test.csv`, ignorés par git) et les **recharge depuis
le CSV** avant de les passer au crible. Le round-trip est volontaire : les types sont
réimposés depuis `feature_spec.json`, jamais devinés — sans quoi un booléen revient en
chaîne et une modalité absente d'un split disparaît silencieusement des tableaux.

**Ce que l'audit établit.**

| Contrôle | Verdict |
|---|---|
| Découpage étanche au ménage | ✅ 0 ménage à cheval (7 044 / 2 349), 0 personne |
| Part de test | ✅ 25,0 % pour 25 % annoncés |
| Colonnes contaminées entraînées | ✅ aucune |
| Représentativité numérique (SMD) | ✅ max 0,037 (`household_size`), seuil 0,25 |
| Représentativité catégorielle (TVD) | ✅ max 2,55 pts (`socioprofessional_class`), seuil 3 |
| Impossibilités de domaine (10 règles) | ✅ 0 ligne |
| Saturation d'une variable retenue | ✅ aucune |
| Cases test `mode × distance` sous 30 obs. | ⚠ **9 cases** |

**Le seul défaut est un défaut d'effectif, et il est structurel.** Le test ne contient
qu'**1 marche au-delà de 10 km, 0 au-delà de 20 km, 2 vélos entre 20 et 50 km, 1 transport
collectif au-delà de 50 km**. Ces cases ne supportent aucune lecture — et c'est exactement
le mécanisme qui fait qu'une tranche de distance à un seul déplacement pèse autant qu'une
tranche à 856 dans l'EMD ordinale de la page de synthèse (`emd_ordinal_dim_measured` filtre
les tranches sur la seule présence d'une **référence**, jamais sur l'effectif du candidat,
là où le chemin nominal pondère en continu par effectif). Le notebook rend le trou visible
**avant** de scorer.

**Trois lectures des valeurs aberrantes**, parce qu'aucune ne suffit seule : IQR pour les
queues, z-score pour les points isolés, et **règles de domaine** pour ce que les deux
premières ne verront jamais — une valeur centrale mais impossible. Les règles sont séparées
en *impossibilités* (tout effectif non nul est un bug amont) et *invraisemblances* (rares
mais vraies, on surveille le volume) : 223 déplacements en `car` sans permis ni voiture au
foyer sont des **passagers**, 235 en `bike` sans vélo nominatif sont des **vélos partagés
ou empruntés**. Les confondre ferait corriger des lignes justes.

Un quatrième test, la **saturation** — la valeur la plus fréquente de chaque variable
continue — trouve `duration_min` à 17,6 % sur la seule valeur « 10 minutes » (arrondi
déclaratif), `distance_km` et `crow_km` à 6,6 % sur une même valeur. Les trois sont
`diagnostic_only` : les artefacts d'arrondi sont **confinés aux colonnes déjà exclues**,
aucune variable retenue n'en porte.

---

## Voir aussi

- `scripts/synthesis/model_on_common_set.py` — application au jeu commun (§8)

- `scripts/progedo_logit/fit_mode_choice_policy.py` — entraînement de la politique (§7, §9)
- `scripts/progedo_logit/tune_mode_choice_policy.py` — banc de réglage des hyperparamètres (§9)
- `scripts/progedo_logit/explore_mode_choice_dataset.ipynb` — audit du jeu train/test (§10)
- `scripts/progedo_logit/prepare_progedo_logit.ipynb` — préparation initiale (contient la
  fuite D12, corrigée ici)
- `scripts/progedo_logit/explore_progedo_walk_shapley.ipynb` §7 — diagnostic de fuite
- `docs/arch/prompt_calibration.md` — cible de calibration `cerema_values.yaml`
- `llm_module/core/mode_choice.py` — politique de décision partagée (normalisation, tirage)
- `llm_module/core/zone_resolver.py` — rattachement point → zone fine et variables géo (§2.2)
- `scripts/progedo_logit/export_zone_layer.py` — export de la couche servie (`make zones`)
