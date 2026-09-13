# Ticket 008 — Run 24 h corrigé → re-mesure des trois volets → `docs/synthesis/index.html`

**Destinataire** : développeur externe, sans connaissance préalable du dépôt.
**Prérequis de lecture** : [ticket 007](ticket_007_procedure_nouveau_run.md) (runbook de
relance de run — ce ticket-ci en est une variante, il n'en recopie pas les phases),
[docs/arch/vehicle-chain.md](../arch/vehicle-chain.md),
[docs/arch/score-synthesis.md](../arch/score-synthesis.md).

## 0 · Objectif

Produire un run de simulation de **24 heures simulées** sur une population corrigée, puis
régénérer les trois volets de la page de synthèse et `docs/synthesis/index.html` dessus.

Le run épinglé actuel (`experiments/archive/2026-07-31_15_45`) souffre de sept défauts
identifiés par une analyse d'écarts. Ce ticket les corrige tous, dans cet ordre : le code
d'abord (lot A), le run ensuite (lot B), les mesures enfin (lot C).

**Ce ticket ne demande aucune re-calibration de prompt.** La boucle de recuit simulé
n'est pas touchée ; seule la **ré-évaluation** de la lignée déjà retenue est refaite.

---

## 1 · Décisions déjà prises — ne pas les rouvrir

| # | Décision | Conséquence |
|---|---|---|
| D1 | Correction de population : **garde-fous eqasim ET script de surface** | Le run n'attend pas l'accès aux données eqasim. Voir A1 |
| D2 | Météo : **nouveaux jeux gelés v2**, lignée re-mesurée dessus | La comparabilité avec les scores v1 est perdue et c'est assumé. Voir A7 et §6.3 |
| D3 | Verrou de retour : seuil à **1 km** | Valeur en dur documentée, pas de réglage exposé. Voir A3 |
| D4 | Modèles : **cascade multi-providers conservée** | Le composite reste un mélange de politiques. Ne pas tenter de forcer un mono-modèle |
| D5 | Enfants passagers : **v1** (mode passager sans modélisation du ménage) | Pas de `household_id`, pas de trajet d'accompagnement généré. Voir A2 |

---

## 2 · Baseline — chiffres du run actuel

Toute la vérification du lot A se fait par comparaison à ces valeurs, mesurées sur
`experiments/archive/2026-07-31_15_45` (6 510 lignes, 6 333 scorées, 901 agents actifs,
3 jours simulés).

**Parts modales globales**, mode tiré, référence EMC² renormalisée sur 4 modes :

| Mode | Observé | Référence | Écart |
|---|---:|---:|---:|
| Marche | 9,4 % | 26,8 % | **−17,4** |
| Voiture | 51,5 % | 56,7 % | −5,2 |
| Vélo | 16,3 % | 4,1 % | **+12,2** |
| Transports collectifs | 22,8 % | 12,4 % | **+10,5** |

**Méthodes de sélection** :

| Méthode | n | part |
|---|---:|---:|
| LLM | 4 140 | 63,6 % |
| Un seul itinéraire disponible | 1 762 | 27,1 % |
| LLM Error (Default index) | 431 | 6,6 % |
| Pas de déplacement / pas de solution | 177 | 2,7 % |

**Anomalies chiffrées à faire disparaître** :

| Anomalie | Valeur actuelle | Cible |
|---|---:|---|
| Trajets voiture conduits par un &lt; 18 ans | 480 (14,7 % des trajets voiture) | 0 en conducteur, reclassés passager |
| Trajets voiture conduits par un &lt; 14 ans | 310 (9,5 %) | 0 en conducteur |
| Trajets voiture sans permis | 197 (6,0 %) | 0 en conducteur |
| Mineurs &lt; 14 ans avec `has_driving_license: true` | 79 / 96 | 0 |
| Activités `education` dans la population | 48 (pour ~150 scolaires) | &gt; 120 |
| Trajets d'agents « Scolaire » avec motif `Travail` | 214 | 0 |
| Retours domicile sans décision (« un seul itinéraire ») | 1 680 / 2 442 (68,8 %) | en baisse, mesurée |
| Retours automatiques &lt; 1 km en voiture | 59,5 % (marche 7,6 %) | verrou désactivé sous 1 km |
| Véhicules orphelins au retour | 5,0 % — **alarme déclenchée** | &lt; 5 % |
| Météo : jours avec précipitations | 0 / 3 | au moins la variabilité du jeu gelé v2 |

---

## 3 · Lot A — corrections de code

Sept chantiers indépendants sauf mention contraire. **Chacun doit être committé
séparément**, avec sa propre entrée de changelog (§7).

### A1 · Population : permis d'enfants et purposes scolaires

**Symptôme** : 79 des 96 enfants de moins de 14 ans portent `has_driving_license: true` ;
les agents « Scolaire (jusqu'au Bac) » cumulent 103 activités `work` contre 18
`education` ; un écolier de 9 ans arrive au LLM avec `travel_purposes: ["Travail"]` et une
chaîne `home → work → home → leisure`.

**Cause racine** — l'appariement HTS perd l'âge :

1. [`eqasim-toulouse/config_toulouse.yml:40`](../../eqasim-toulouse/config_toulouse.yml)
   ne demande que `departments: ["31"]`, et `filter_hts` vaut `True` par défaut
   ([`data/hts/entd/filtered.py:13`](../../eqasim-toulouse/data/hts/entd/filtered.py)).
   L'ENTD est réduit aux seuls répondants de Haute-Garonne : le vivier de donneurs passe
   de ~18 000 à quelques centaines.
2. Les attributs d'appariement par défaut sont
   `["sex", "any_cars", "age_class", "socioprofessional_class", "departement_id"]`
   ([`synthesis/population/matched.py:22`](../../eqasim-toulouse/synthesis/population/matched.py)),
   avec `matching_minimum_observations = 20`.
3. La dégradation retire les colonnes **par la fin** (`column_indices[:level]`,
   [`matched.py:86`](../../eqasim-toulouse/synthesis/population/matched.py)). Vivier
   réduit ⇒ les niveaux 5/4/3 n'atteignent pas 20 observations ⇒ on retombe au niveau 2
   (`sex`, `any_cars`) voire 1 (`sex`) : **`age_class` est éliminé**. Un enfant hérite
   d'un donneur adulte, avec son permis et sa chaîne d'activités.
4. **Aggravant** :
   [`synthesis/population/llm_agents.py:469`](../../eqasim-toulouse/synthesis/population/llm_agents.py)
   écrit `bool(row.get("has_license", False))`. Le défaut `False` ne s'applique que si la
   **colonne** manque, jamais si la **valeur** est `NaN` — et `bool(nan)` vaut `True`.
   Toute personne non appariée reçoit donc le permis.

Le mapping ENTD est correct et n'est **pas** en cause : `PURPOSE_MAP` porte bien
`("1.11", "education")`
([`data/hts/entd/cleaned.py:15`](../../eqasim-toulouse/data/hts/entd/cleaned.py)).

#### A1.a — Garde-fous dans le code eqasim (racine)

⚠️ **Non exécutable en l'état** : `config_toulouse.yml:28` pointe
`data_path: /Users/yvesb/Documents/eqasim-france/data`, hors dépôt et absent des machines
de développement. Livrer le code, ne pas tenter de le faire tourner sans avoir obtenu
l'accès aux données. Ces correctifs servent au prochain cycle de génération.

1. `config_toulouse.yml` : ajouter `filter_hts: false` ; déclarer explicitement
   `matching_attributes` avec **`age_class` en tête** (la dégradation retire par la fin,
   donc l'âge devient le dernier critère abandonné) ; abaisser
   `matching_minimum_observations`.
2. `llm_agents.py:469` : `bool(pd.notna(v) and v)` **et** garde d'âge
   `age_val >= 18`. Même traitement défensif pour `has_pt_subscription:470` (même
   motif `NaN`).
3. `enriched.py:80` : exclure les moins de 18 ans du `groupby(...).sum()` des
   `number_of_licenses` avant de dériver `car_availability` — sinon les permis fantômes
   font basculer des ménages de `some` vers `all`.
4. Optionnel : `enriched.py:119`, pas de `VAE` sous 14 ans (`personal_bike` est un tirage
   aléatoire sans filtre d'âge).

#### A1.b — Script de surface (débloque le run)

**C'est ce livrable qui alimente le run du lot B.** Créer
`scripts/data/population/fix_minor_traits.py`, sur le modèle exact de
[`enrich_housing_type.py`](../../scripts/data/population/enrich_housing_type.py) : même
CLI, même `--dry-run`, même écriture en place, même idempotence.

Entrée : `data/population/toulouse_population_1000.json`. Transformations, dans l'ordre :

| # | Règle | Condition |
|---|---|---|
| 1 | `has_driving_license → false` | `age < 18` |
| 2 | `purpose: "work" → "education"` | l'agent a `professional_activity ∈ {student, under14}` ou `main_occupation == "Scolaire (jusqu'au Bac)"` |
| 3 | Recalcul de `travel_purposes` | après (2), via le même mapping que [`llm_agents.py:446`](../../eqasim-toulouse/synthesis/population/llm_agents.py) : `work→"Travail"`, `education→"Etude"`, `shop→"Achats"` |
| 4 | Recalcul de `car_availability` par ménage | ménage = **coordonnées du domicile** (pas de `household_id` disponible) ; `cars >= licences adultes → "all"`, `< → "some"`, `cars == 0 → "none"` |
| 5 | `personal_bike: "VAE" → "vélo normal"` | `age < 14` |

**Ce que le script ne corrige pas, et doit l'écrire dans son rapport de sortie** : les
chaînes d'activités restent celles de donneurs adultes (horaires de départ d'actifs,
destinations d'actifs). Renommer `work` en `education` ne rapproche pas l'école du
domicile. C'est la limite assumée de D1 ; seul A1.a la lève.

**Vérification de sortie** :

```bash
llm-agents/.venv/bin/python -c "
import json; from collections import Counter
p=json.load(open('data/population/toulouse_population_1000.json'))
minors=[x for x in p if x['identity']['traits_json']['age']<18]
print('mineurs avec permis :', sum(1 for x in minors if x['identity']['traits_json']['has_driving_license']))
print('purposes :', Counter(a['purpose'] for x in p for a in x['identity']['activities']))
"
```

Attendu : `0` mineur avec permis ; `education` &gt; 120.

### A2 · Mode passager v1 — les enfants vont à l'école en voiture

**Principe** : un agent qui ne peut pas conduire peut quand même **monter** dans la
voiture du foyer. EMC² compte le passager dans « voiture », donc la part modale reste
comparable ; ce qui change, c'est que la voiture ne se gare plus à l'école et que l'enfant
n'est plus tenu de la ramener.

Fichier : [`llm-agents/urban_mobility_agents/simulation_controller.py`](../../llm-agents/urban_mobility_agents/simulation_controller.py),
section « Cohérence de chaîne des véhicules personnels » (à partir de la ligne 254).

1. **Nouveau prédicat** `_can_drive(traits) -> bool` :
   `traits.get("has_driving_license", False) and traits.get("age", 0) >= 18`.
2. **Nouveau prédicat** `_is_car_passenger(person) -> bool` : `not _can_drive(...)`
   **et** `number_of_cars > 0` **et** `household_size > 1` (il faut quelqu'un pour
   conduire). Un adulte sans permis vivant seul n'est donc pas passager.
3. **`_vehicle_available(person, "car", from_location)`** ([:298](../../llm-agents/urban_mobility_agents/simulation_controller.py#L298)) :
   - si `_can_drive` → comportement actuel inchangé (possession + position) ;
   - sinon si `_is_car_passenger` → **`True` sans test de position** (ce n'est pas sa
     voiture, un tiers l'amène) ;
   - sinon → `False`. **C'est le verrou dur** : plus aucun mineur ni sans-permis ne
     conduit.
4. **`_park_vehicles`** ([:336](../../llm-agents/urban_mobility_agents/simulation_controller.py#L336)) :
   sortie immédiate si `_is_car_passenger(person)` et que le mode retenu est `car`. La
   voiture ne bouge pas — elle repart avec son conducteur.
5. **Verrou de retour** ([:1874](../../llm-agents/urban_mobility_agents/simulation_controller.py#L1874)) :
   aucune modification nécessaire. `_vehicles_parked_at` exclut déjà le domicile, et comme
   (4) ne gare jamais la voiture à destination, le passager ne déclenche pas de retour
   forcé. **À couvrir par un test explicite** — c'est le point le plus facile à casser.
6. **Métrique** : nouvel `event="passenger"` sur `VEHICLE_CHAIN`
   (déclaré [:113](../../llm-agents/urban_mobility_agents/simulation_controller.py#L113)),
   incrémenté à chaque trajet passager retenu. À documenter dans le tableau des events de
   [vehicle-chain.md](../arch/vehicle-chain.md).
7. **Narratif de persona** :
   [`agents/llm_agent.py:131-147`](../../llm-agents/urban_mobility_agents/agents/llm_agent.py).
   Les branches `car_avail == "…" and not has_license` doivent dire explicitement que le
   trajet en voiture se fait **conduit par un adulte du foyer**, pas « voiture dispo ». Ne
   pas toucher aux branches conducteur.

**Le mode reste `Voiture Privée` dans `moves.csv`** — la traçabilité passe par la colonne
de A4 (valeur `passager`). Ne pas créer de septième mode : ça casserait
`CHOSEN_MODE_MAP` de [`scripts/synthesis/frames.py:47`](../../scripts/synthesis/frames.py)
et la comparaison EMC².

**Tests** : étendre `llm-agents/tests/test_vehicle_chain.py` (52 tests existants). Cas
minimaux à couvrir : enfant de 12 ans avec 3 voitures au foyer → voiture proposée, non
garée à l'école, retour non forcé ; adulte sans permis seul → voiture jamais proposée ;
adulte avec permis → aucun changement de comportement.

```bash
cd llm-agents && .venv/bin/python -m pytest tests/test_vehicle_chain.py -q
```

### A3 · Seuil de distance sur le verrou de retour (1 km)

**Symptôme** : sur les retours au domicile de moins d'1 km décidés automatiquement, 59,5 %
se font en voiture et 7,6 % à pied, contre 76 % de marche attendus par EMC².

Dans le bloc du verrou de retour
([:1874-1893](../../llm-agents/urban_mobility_agents/simulation_controller.py#L1874)),
ajouter une condition de distance : **si la distance origine→destination est inférieure à
1 km, le verrou ne s'applique pas** — tous les modes restent offerts, et si l'agent rentre
autrement le véhicule devient orphelin (il sera rattrapé par
`_settle_vehicles_at_home`, mécanisme existant).

**Distance à utiliser** : le verrou s'exécute **avant** le choix, donc `plan.distance`
n'existe pas encore. Utiliser la distance à vol d'oiseau × 1,3, exactement la convention
de `_estimate_fallback_duration`
([:223](../../llm-agents/urban_mobility_agents/simulation_controller.py#L223)) — factoriser
le calcul haversine plutôt que le recopier.

⚠️ **Écart attendu et normal** : la colonne « Distance parcourue » de `moves.csv` est la
distance du plan retenu (`_plan_distance_km`,
[`move_logger.py:160`](../../llm-agents/urban_mobility_agents/utils/move_logger.py#L160)),
pas cette estimation. Quelques trajets près du seuil seront donc classés d'un côté par le
verrou et de l'autre par les stats. Ne pas chercher à les faire coïncider ; le mentionner
dans la doc.

Documenter le seuil dans le tableau des réglages de
[vehicle-chain.md](../arch/vehicle-chain.md). D3 dit : valeur en dur, pas de réglage
exposé dans `settings.py`.

### A4 · Colonne de traçabilité dans `moves.csv`

Ajouter une colonne **`Contrainte de chaîne`** à
[`move_logger.py`](../../llm-agents/urban_mobility_agents/utils/move_logger.py) : liste
d'en-têtes (lignes 40-79), signature de la fonction d'écriture (à partir de la ligne 240)
et les deux points d'écriture (lignes ~247 et ~292).

Valeurs, une seule par ligne :

| Valeur | Signification |
|---|---|
| *(vide)* | Aucune contrainte : le jeu de choix est celui d'OTP |
| `retour_force` | Verrou de retour appliqué — options restreintes au mode du véhicule garé |
| `passager` | Trajet en voiture conduite par un tiers (A2) |
| `sortie_bloquee` | Un mode véhiculé possédé a été écarté faute de véhicule sur place |

**Ces lignes restent dans le scoring** — la colonne sert à expliquer, pas à filtrer. C'est
une demande explicite. La page de synthèse doit en revanche **afficher la répartition**
dans son bilan de lecture, à côté des méthodes de sélection.

Placer la colonne **après** « Méthode de sélection » pour la lisibilité. Vérifier qu'aucun
consommateur ne lit `moves.csv` par index de colonne : `frames.read_moves` utilise
`csv.DictReader` (par nom), donc l'ajout est sûr — le confirmer avant de committer.

### A5 · Arrêt du run à 24 h simulées

Deux défauts distincts, les deux bloquants :

1. **Le paramètre n'est pas transmis.** `simulation_max_days` est lu depuis le fichier de
   config de scénario
   ([`Settings.gaml:100`](../../GAMA/CityTransport/models/Settings.gaml) et
   [`:131`](../../GAMA/CityTransport/models/Settings.gaml)), avec un défaut de **7**. Le
   `scenario_params.yaml` du run actuel ne contient que quatre clés
   (`long_term_memory_enabled`, `long_term_self_reflect_enabled`,
   `number_of_llm_based_agents`, `population_size`) — **pas** `simulation_max_days`. Il
   faut le poser à `1`.
2. **L'arrêt n'est pas armé.** Dans
   [`City.gaml:127-130`](../../GAMA/CityTransport/models/City.gaml), le reflex
   `stop_after_max_days` écrit un message mais l'instruction `do halt;` est **commentée**.
   En l'état, `simulation_max_days: 1` n'arrête rien.

Décommenter `do halt;`, vérifier que l'arrêt laisse le temps aux écritures de
`moves.csv` / `llm_exchanges.jsonl` de se terminer (sinon la dernière ligne peut être
tronquée — à contrôler sur un run court de test), et documenter la manœuvre dans
[ticket 007 §3](ticket_007_procedure_nouveau_run.md).

**Rappel** : `starting_date` est le **lundi 16 mars 2026 à 5 h**
([`Settings.gaml:27`](../../GAMA/CityTransport/models/Settings.gaml)). 24 h simulées vont
donc du lundi 5 h au mardi 5 h.

### A6 · Périmètre de scoring de la page

Deux filtres, **tous deux au niveau des sources**, pour que les trois volets héritent du
même périmètre.

#### A6.a — Exclure les replis d'erreur LLM

Les 431 lignes `LLM Error (Default index)` ne sont pas des décisions : le repli prend
l'itinéraire par défaut, et **100 % d'entre elles retiennent le plus rapide**, soit 64,7 %
de voiture. Les garder revient à faire noter au prompt un choix qu'il n'a pas fait.

Ajouter `"LLM Error (Default index)"` à `common_set.exclude_selection_methods` dans
[`scripts/synthesis/sources.yaml`](../../scripts/synthesis/sources.yaml). Le mécanisme
d'exclusion existe déjà (`frames.read_moves`,
[frames.py:280](../../scripts/synthesis/frames.py#L280)) et compte les exclusions dans
`stats` — vérifier que le compteur remonte bien jusqu'au bilan de lecture affiché, et
l'expliciter dans la page (« replis d'erreur exclus : N »).

#### A6.b — Ne garder que le premier jour simulé

Même si le run est censé s'arrêter à 24 h (A5), le filtre doit exister : le bootstrap 24 h
et l'horizon glissant font déborder la planification au-delà.

**Deux points d'entrée, pas un** :

| Volet | Fichier source | Point d'intervention |
|---|---|---|
| 1 (simulation) et 3 (PROGEDO) | `moves.csv` | `frames.read_moves` ([frames.py:273](../../scripts/synthesis/frames.py#L273)) — filtrer sur la colonne `Temps simulé` |
| 2 (calibration) | `llm_exchanges.jsonl` | `common_set_eval.build_sample` ([common_set_eval.py:137](../../scripts/synthesis/common_set_eval.py#L137)) — filtrer sur le champ **`sim_day`**, déjà présent dans chaque enregistrement |

`build.py` et `model_on_common_set.py` appellent tous deux `frames.read_moves`
([build.py:377](../../scripts/synthesis/build.py#L377),
[model_on_common_set.py:490](../../scripts/synthesis/model_on_common_set.py#L490)) : une
seule modification les couvre. Le volet 2, lui, ne lit pas `moves.csv` — il reconstruit
son échantillon depuis `llm_exchanges.jsonl` via `calibration.metadata.build_decision_records`.
**Oublier ce second point ferait porter aux trois volets des périmètres différents, sans
que rien ne le signale.**

Le premier jour = la plus petite date présente, pas une date en dur. Journaliser la date
retenue et le nombre de lignes écartées dans le bilan de lecture.

> **Contexte chiffré** : sur le run actuel, 2 538 couples (personne, activité)
> apparaissent plusieurs fois (2,17 occurrences en moyenne, même mode dans 57,8 % des
> cas). C'est ce que ce filtre supprime.

### A7 · Météo tirée aléatoirement dans les jeux gelés (v2)

**Constat** : les jeux gelés `prompt_calibration/calibration_datasets/v1` ne contiennent
que **5 valeurs météo, toutes « Ciel dégagé / Pas de précipitations »** (train : 6 °C ×349,
15 °C ×132, puis 12/3/13 °C pour 14 records). Le prompt a été calibré dans un monde où il
ne pleut jamais. Côté simulation, ce n'est pas un bug : la source
[`data/weather/meteo_toulouse_12_mois.csv`](../../data/weather/meteo_toulouse_12_mois.csv)
contient 365 jours dont **155 avec précipitations** (max 15,6 mm) — la fenêtre 16-18 mars
2026 est simplement sèche et ensoleillée (code 113).

**Travail demandé** : geler une **v2** des jeux `train` / `val` / `test` / `screen` dans
laquelle le champ `context` porte une météo **tirée au sort** dans le CSV annuel, avec une
graine reproductible.

- Point d'intervention : `build_decision_records`,
  [`prompt_calibration/calibration/metadata.py:215`](../../prompt_calibration/calibration/metadata.py)
  (`"context": preamble.replace("**Contexte :**", "").strip()`).
- Tirage seedé sur `agent_id + entry` — deux régénérations doivent produire le même jeu.
  Consigner la graine dans le manifeste écrit par `build_datasets`
  ([datasets.py:141](../../prompt_calibration/calibration/datasets.py#L141)).
- Reprendre la mise en forme de `weather_to_natural_language`
  ([`weather_loader.py:100`](../../llm-agents/urban_mobility_agents/utils/weather_loader.py#L100))
  pour que la phrase injectée soit **identique** à celle que produit la simulation.
  Ne pas importer le module (dépôts disjoints) : recopier la mise en forme et ajouter un
  test qui compare les deux sorties sur quelques cas.

⚠️ **Piège bloquant, à traiter en premier.** Le format des échanges a changé : dans le run
actuel, le **préambule est vide** et `**Contexte :** Météo…` se trouve déjà **à
l'intérieur de chaque bloc persona**. En l'état, `metadata.py:215` produirait
`context == ""` pour tous les records d'une v2, et `inject_context()`
([evaluation.py:73](../../prompt_calibration/calibration/evaluation.py#L73)) deviendrait
un no-op silencieux. Il faut donc **extraire la météo depuis la section persona et l'en
retirer** avant de la remplacer — sur le modèle de `strip_memory_section`
([metadata.py:115](../../prompt_calibration/calibration/metadata.py#L115)).

Vérification de sortie : la distribution des conditions météo dans `train.jsonl` doit
refléter celle du CSV annuel (≈ 42 % de jours avec précipitations), et aucun record ne
doit avoir un `context` vide.

```bash
cd prompt_calibration && .venv/bin/python -m calibration.datasets \
  ../experiments/current calibration_datasets v2
```

Génération refusée si une version du même nom existe (gel strict,
[datasets.py:113](../../prompt_calibration/calibration/datasets.py#L113)) — c'est voulu.

> **Volet 3 non concerné** : `feature_spec.json` ne contient aucune variable météo
> (features : persona + géo + `purpose` / `departure_hour` / `od_km`). Ne pas chercher à y
> injecter la météo.

---

## 4 · Lot B — exécution du run

Suivre [ticket 007](ticket_007_procedure_nouveau_run.md) **phases 1 à 3**, avec ces
différences :

| Étape 007 | Différence pour ce ticket |
|---|---|
| §1.3 Sanctuariser | Archiver `docs/synthesis/` **et** noter le run épinglé actuel : `experiments/archive/2026-07-31_15_45` |
| §2 Générer la population | **Ne pas régénérer.** Réutiliser `data/population/toulouse_population_1000.json` et lui appliquer le script A1.b |
| §3.1 Config | `make run CONFIG=config_baseline_1000_current.yaml` (⚠️ le défaut du Makefile est la population de 10 000) |
| §3.2 Lancer | Poser `simulation_max_days: 1` dans le fichier de scénario **avant** de presser play (A5) |
| §3.4 Vérifications | Ajouter les contrôles de §6.1 ci-dessous |

**Ordre de démarrage impératif** : `docker compose up` d'abord, GAMA ensuite, play enfin.
Le client WebSocket du contrôleur se reconnecte indéfiniment et attend GAMA aussi
longtemps qu'il faut.

**Pendant le run**, surveiller :

```bash
make error      # ERROR et [ALARME]
make warning
```

Le run précédent a déclenché 21 alarmes gateway (« 10 tâches échouées d'affilée »), une
alarme de backlog critique (802 activités en attente, backpressure à 21,55 s) et 566
erreurs providers — dominées par des HTTP 429 sur les clés Google et des troncatures 503
sur cerebras. D4 conserve la cascade, donc ces erreurs resteront présentes : ce qui compte
est qu'elles restent **sous le niveau du run précédent** (6,6 % de replis), et A6.a les
sort du scoring de toute façon.

---

## 5 · Lot C — re-mesure et page

Suivre [ticket 007 §4 et §5](ticket_007_procedure_nouveau_run.md), dans cet ordre.

1. **Épingler le run** dans `scripts/synthesis/sources.yaml` (`common_set.run`), par
   chemin d'archive — **jamais** `experiments/current`, qui est un symlink mouvant.
2. **Volet 3 — PROGEDO** (local, gratuit) : `make common-set-predict`. Le modèle consomme
   `has_driving_license`, `car_availability`, `number_of_cars`, `main_occupation`,
   `studies`, `purpose` : ses prédictions changent mécaniquement avec A1. Attendu, à
   signaler dans le changelog.
3. **Volet 2 — calibration sur le jeu commun** : `make common-set-eval`, **précédé de
   `DRY_RUN=1`** pour chiffrer. Le cache du store est indexé sur l'empreinte de
   l'échantillon (`common_set_v1@<empreinte>`) : changer de run l'invalide, la mesure
   précédente ne peut pas resservir.
4. **Re-mesure de la lignée sur les jeux v2** (conséquence de D2) : `make heldout-eval`,
   là encore **chiffrer d'abord avec `DRY_RUN=1`**. Le quota Google se réinitialise à
   **minuit Pacific (07:00 UTC)**, pas à minuit UTC — planifier en conséquence.
5. **Régénérer la page** : `make synthesis`, puis `make synthesis-open`.

---

## 6 · Critères d'acceptation

### 6.1 Sur le run

- [ ] `moves.csv` ne couvre qu'un seul `sim_day`
- [ ] **0** trajet voiture en conducteur par un agent de moins de 18 ans ou sans permis
- [ ] Les trajets voiture d'enfants existent toujours, marqués `passager` en colonne
      `Contrainte de chaîne`, et leur part reste du même ordre qu'avant (EMC² compte le
      passager dans « voiture » — un effondrement de la part voiture chez les 5-14 ans
      signalerait une régression, pas un progrès)
- [ ] La part de « Un seul itinéraire disponible » **baisse** par rapport à 27,1 %
- [ ] Sur les retours domicile de moins d'1 km, la part de marche remonte au-dessus de
      7,6 %
- [ ] Alarme véhicules orphelins **non déclenchée** (&lt; 5 % des retours), ou déclenchée
      avec une explication écrite : A3 augmente mécaniquement les orphelins, c'est le
      compromis accepté
- [ ] `agent_vehicle_chain_total{event="passenger"}` non nul
- [ ] Aucun `[ALARME]` non expliqué dans `make error`

### 6.2 Sur la population corrigée

- [ ] 0 mineur avec `has_driving_license: true`
- [ ] &gt; 120 activités `education`
- [ ] 0 trajet d'agent « Scolaire » avec motif `Travail` dans `moves.csv`

### 6.3 Sur la page

- [ ] Les trois volets portent le **même** périmètre : même run, même jour, mêmes
      exclusions. Le vérifier en comparant les `n` affichés, pas en le supposant
- [ ] Le bilan de lecture affiche : replis d'erreur exclus, lignes écartées par le filtre
      de jour, répartition de `Contrainte de chaîne`
- [ ] Le régime météo v2 est **visible dans la page** — sans quoi un lecteur comparera des
      scores v1 et v2 sans savoir qu'ils ne mesurent pas la même chose. C'est la
      contrepartie de D2 et ce n'est pas optionnel
- [ ] `docs/synthesis/index.html` régénéré, ancienne version archivée sous
      `docs/synthesis/archive/<date>/`

---

## 7 · Documentation — obligatoire à chaque lot

Convention du dépôt, définie dans `.claude/CLAUDE.md`, **non négociable** :

1. **Mettre à jour la doc d'architecture concernée** à chaque modification de code :
   - A2, A3, A4 → [`docs/arch/vehicle-chain.md`](../arch/vehicle-chain.md) (les trois
     règles, le tableau des events, le tableau des réglages)
   - A6 → [`docs/arch/score-synthesis.md`](../arch/score-synthesis.md)
   - A7 → [`docs/arch/prompt_calibration.md`](../arch/prompt_calibration.md)
   - A1, A5 → [`ticket 007`](ticket_007_procedure_nouveau_run.md) (procédure) et
     `README.md` si le setup change
2. **Ajouter une entrée dans [`docs/changelog.md`](../changelog.md)**, en **haut** du
   fichier, format `## [YYYY-MM-DD] Titre fonctionnel`, ton orienté usage, avec un bloc
   **Avant/Après** dès qu'un comportement observable change. **Ne pas y lister les
   fichiers modifiés** — ça appartient aux commits.
3. **Instrumenter les points bloquants** : toute nouvelle condition de rejet ou de
   restriction doit être comptée par une métrique, et lever une `logger.error` préfixée
   `[ALARME]` au franchissement d'un seuil, sur front montant.

---

## 8 · Risques et retour arrière

| Risque | Probabilité | Mitigation |
|---|---|---|
| A2 casse le verrou de retour pour les adultes | moyenne | Les 52 tests de `test_vehicle_chain.py` doivent passer **avant** l'ajout des nouveaux |
| A3 fait exploser les véhicules orphelins au-dessus de 5 % | **élevée** — c'est l'effet attendu du seuil | Mesurer, et arbitrer avec le demandeur entre le seuil et le taux d'orphelins. Ne pas monter `vehicle_orphan_alarm_ratio` pour faire taire l'alarme |
| A7 : `context` vide sur toute la v2 | **élevée** si le piège du §A7 est ignoré | Vérifier `context` non vide sur 100 % des records **avant** de lancer la moindre éval |
| A6.b appliqué au volet 1 mais pas au volet 2 | moyenne | Comparer les `n` des trois volets, ils doivent être cohérents |
| Coût LLM de la re-mesure sous-estimé | moyenne | `DRY_RUN=1` **systématique** avant `common-set-eval` et `heldout-eval` |
| Le run 24 h ne s'arrête pas | moyenne | A5 point 2 : `do halt;` est commenté. Tester sur un run court avant le run de référence |

**Retour arrière** : le run épinglé actuel est `experiments/archive/2026-07-31_15_45`.
**Ne pas le supprimer** — c'est le seul moyen de revenir en arrière. Restaurer
`sources.yaml` et la page archivée suffit à retrouver l'état antérieur ; les jeux gelés v1
ne sont jamais écrasés (gel strict).

---

## Voir aussi

- [ticket 006](ticket_006_relance_run_reference.md) — *pourquoi* relancer un run
- [ticket 007](ticket_007_procedure_nouveau_run.md) — *comment* relancer un run
- [ticket 005](ticket_005_mode_choice_model.md) — modèle de choix modal PROGEDO
- [docs/arch/vehicle-chain.md](../arch/vehicle-chain.md) — les trois règles de la chaîne
- [docs/arch/score-synthesis.md](../arch/score-synthesis.md) — construction des trois volets
