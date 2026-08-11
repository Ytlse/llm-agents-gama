# Ticket 007 — Procédure : nouvelle population → nouveau run → page de synthèse à jour

Runbook opérationnel pour produire un jeu de données de référence complet et régénérer
`docs/synthesis/index.html` dessus. À suivre dans l'ordre : chaque phase a des
**vérifications de sortie** qui conditionnent la suivante.

**Pourquoi ce ticket** : la page de synthèse est adossée à un run **épinglé par chemin
d'archive** (action A1). En changer est une opération à effets multiples — trois volets, un
coût LLM, et des traits de population qui ne se remplissent qu'à ce moment-là. Le
ticket [006](ticket_006_relance_run_reference.md) dit *quand* le faire et *pourquoi* ;
celui-ci dit *comment*.

**Durée de référence** : le run épinglé actuel (1 000 agents) a tourné de 18:34 à 22:56,
soit **~4 h 20**. Une population de 10 000 est d'un autre ordre de grandeur.

**Coût LLM total de la procédure** : **128 appels** (uniquement la phase 5.2). Tout le
reste est local et gratuit.

---

## 0 · Décisions structurantes à connaître avant de commencer

| # | Point | Conséquence opératoire |
|---|---|---|
| G1 | Le run est épinglé **par chemin d'archive**, jamais par le symlink `experiments/current` (action A1) | Épingler est un geste **explicite** dans `sources.yaml`. Un nouveau run ne change rien à la page tant qu'on ne l'a pas fait |
| G2 | Les traits de population ne rétroagissent pas | Type de logement, couronnes de résidence, disponibilité du vélo : tout est figé **à la journalisation**. Un run ne corrige jamais un run passé |
| G3 | L'échantillon du volet 2 est tiré du run épinglé | Changer de run **invalide** `calibration_on_common_set.jsonl` : à reproduire (128 appels). Le cache du store est indexé sur l'empreinte de l'échantillon (`common_set_v1@<empreinte>`), il ne peut donc plus resservir la mesure du run précédent — corrigé le 2026-07-31, cf. `docs/arch/score-synthesis.md` |
| G4 | Les jeux gelés `train`/`val`/`test` sont indépendants du run | Les actions A4, A5 et A10 ne sont **pas** à refaire |
| G5 | Le quota Google se réinitialise à **minuit Pacific (07:00 UTC)** | Planifier la phase 5.2 en conséquence. Ce n'est pas minuit UTC — l'erreur a déjà coûté une journée |

---

## 1 · Pré-vol — à faire avant tout

### 1.1 Committer le correctif du véhicule fantôme ⚠️ bloquant

C'est **la** raison d'être de la relance ; l'oublier revient à reproduire le run à
l'identique.

```bash
git status --short llm-agents/urban_mobility_agents/simulation_controller.py llm-agents/models.py
```

Attendu : `M` sur les deux. Ces fichiers portent la cohérence de chaîne des véhicules
(`_vehicle_available()`, `_park_vehicles()`, `_settle_vehicles_at_home()`,
`PersonState.planning_vehicle_at`) en copie de travail, **jamais commitée** (vérifiable :
`git log -S "planning_vehicle_at"` ne retourne rien). Voir ticket 006 §3 et
[../arch/vehicle-chain.md](../arch/vehicle-chain.md).

Sans ce correctif, le nouveau run reproduira les **352 trajets à vélo fantôme sur 1 086**,
soit 5,9 points de part modale — et, côté voiture, une disponibilité inconditionnelle
partout et à toute heure.

Vérification rapide avant de committer :

```bash
cd llm-agents && .venv/bin/python -m pytest tests/test_vehicle_chain.py -q
```

### 1.2 Décider du périmètre des traits

Ne relancez qu'une fois. Passez en revue ce qui doit être dans la population :

| Trait | État | Action |
|---|---|---|
| Type de logement | ✅ **déjà posé** sur les populations existantes (2026-07-31) | rien — voir 2.3 |
| Possession de vélo (`personal_bike`) | ✅ présent, 46,5 % sans vélo | rien, sauf raffinement volontaire (ticket 006 §7) |
| Profession antérieure des retraités | ❌ absent, 16,2 % des personas | **décision requise** — eqasim peut-il la fournir ? (ticket 006 §5.3) |
| Hypercentre unifié | ✅ code livré (A9) | s'applique automatiquement au prochain run |

### 1.3 Sanctuariser l'état actuel

```bash
# Archiver la page avant modification (convention du dépôt)
mkdir -p docs/synthesis/archive/$(date +%Y-%m-%d_%H%M)
cp docs/synthesis/index.html docs/synthesis/data.json \
   docs/synthesis/archive/$(date +%Y-%m-%d_%H%M)/

# Noter le run actuellement épinglé, pour pouvoir y revenir
grep -A2 "^common_set:" scripts/synthesis/sources.yaml
```

Le run actuel est `experiments/archive/2026-07-29_18_34`. **Ne le supprimez pas** : c'est
le seul moyen de revenir en arrière si le nouveau run est mauvais.

### 1.4 Ne pas lancer `make purge_cache`

```makefile
rm -f data/population/*.json   # ← supprime TOUTES les populations générées
```

Cette cible détruit les populations, y compris celles que l'action A2 vient d'enrichir.
Si vous devez purger les caches OSMnx/eqasim, faites-le sélectivement.

---

## 2 · Phase 1 — Générer la population

> **À sauter** si vous réutilisez une population existante. Les quatre fichiers de
> `data/population/` sont générés **et enrichis** (2026-07-31). Passez au §3.

### 2.1 Démarrer le service eqasim

```bash
docker compose up eqasim
```

Port **8003**. Le notebook s'arrête avec un message explicite après 3 tentatives si le
service ne répond pas.

### 2.2 Exécuter le notebook

`scripts/data/population/generate_population.ipynb`

Paramètres, cellule 2 :

| Paramètre | Valeur usuelle | Rôle |
|---|---|---|
| `POPULATION_SIZES` | `[1000]` | Tailles à générer (multiples de 100) |
| `FORCE_REGENERATE` | `False` | `True` → rappelle eqasim en ignorant son cache |
| `FORCE_STEP` | `None` | Reprise forcée à partir d'une étape et de toutes les suivantes |
| `BBOX` | `None` | `None` = département 31 |
| `GENERATE_PERSONALITY` | `False` | Big Five — lent, non requis par la page |

Pipeline à checkpoints — chaque étape est **ignorée si sa sortie existe déjà** :

| Étape | Entrée | Sortie |
|---|---|---|
| 1 — Génération eqasim | API eqasim | `Temp/1_raw/` |
| 2 — Validation activités | `Temp/1_raw/` | `Temp/2_fixed/` |
| 3 — Enrichissement TC | `Temp/2_fixed/` | `Temp/3_pt_enriched/` |
| 3bis — Enrichissement zone (AAV2020 + densité) | `Temp/3_pt_enriched/` | `Temp/4_zone_enriched/` |
| 4 — Itinéraires OSMnx | `Temp/4_zone_enriched/` | `Temp/5_scheduled/` |
| Export final | `Temp/5_scheduled/` | `data/population/toulouse_population_<n>.json` |

**Vérification de sortie**

```bash
llm-agents/.venv/bin/python -c "
import json; p=json.load(open('data/population/toulouse_population_1000.json'))
print(len(p),'personas'); print(sorted(p[0]['identity']['traits_json']))"
```

Les traits doivent inclure `age`, `gender`, `household_size`, `has_driving_license`,
`has_pt_subscription`, `number_of_cars`, `car_availability`, `personal_bike`,
`socioprofessional_class`, `main_occupation`, `employed`, `studies`.

### 2.3 Enrichir avec le type de logement

**Déjà fait** sur les populations existantes. À rejouer seulement si vous régénérez.

```bash
# 1. (Re)construire la loi par zone fine — exige les données PROGEDO (accès restreint)
make housing-type

# 2. Poser le trait sur la population — déterministe, aucun appel LLM, en place
llm-agents/.venv/bin/python -m scripts.data.population.enrich_housing_type \
  data/population/toulouse_population_1000.json --dry-run   # chiffrer d'abord
llm-agents/.venv/bin/python -m scripts.data.population.enrich_housing_type \
  data/population/toulouse_population_1000.json
```

**Vérification de sortie** — distribution attendue, proche de :

| Modalité | Part |
|---|---|
| Individuel isolé | ~36 % |
| Petit habitat collectif | ~22 % |
| Grand habitat collectif | ~21 % |
| Individuel accolé | ~16 % |
| *(absent — hors couche de zones)* | ~4,4 % |

Les ~4,4 % sans trait sont **normaux et voulus** : hors de la couche de zones fines, rien
n'est deviné. L'imputation est conditionnée à la zone fine du domicile et déterministe
(hachage SHA-256 de l'**adresse**, pour que deux personas d'un même foyer ne se retrouvent
pas l'un en maison et l'autre en tour).

### 2.4 Rendre aux mineurs leur âge ⚠️ obligatoire sur toute population antérieure

Correctif de surface, introduit par le [ticket 008](ticket_008_run_24h_mesures_synthese.md)
(A1.b). L'appariement HTS perdait `age_class` et un `bool(nan)` valant `True` distribuait
le permis : **131 des 165 mineurs** de `toulouse_population_1000.json` portaient
`has_driving_license: true`, et les scolaires arrivaient au LLM avec la chaîne d'activités
d'un actif.

```bash
llm-agents/.venv/bin/python -m scripts.data.population.fix_minor_traits \
  data/population/toulouse_population_1000.json --dry-run   # chiffrer d'abord
llm-agents/.venv/bin/python -m scripts.data.population.fix_minor_traits \
  data/population/toulouse_population_1000.json
```

Le script est **idempotent** : le relancer ne change rien. Il retire le permis sous 18 ans,
reclasse `work → education` pour les scolaires, recalcule `travel_purposes` et
`car_availability` par ménage (regroupé sur les coordonnées du domicile, faute de
`household_id`), et déclasse les VAE sous 14 ans.

**Vérification de sortie** : `0` mineur avec permis, `> 120` activités `education`.

**Ce qu'il ne corrige pas**, et qu'il redit à chaque exécution : les *chaînes d'activités*
restent celles de donneurs adultes (horaires et destinations d'actifs). Renommer `work` en
`education` ne rapproche pas l'école du domicile. Seuls les garde-fous eqasim
(`config_toulouse.yml`, `llm_agents.py`, `enriched.py` — ticket 008 A1.a) lèvent la limite,
et ils ne prennent effet qu'à une **régénération complète** de la population, laquelle exige
l'accès aux données eqasim (hors dépôt).

---

## 3 · Phase 2 — Lancer la simulation

### 3.1 Choisir la configuration

La taille de population lue découle de la config, via
`settings.data.population_size` et `synthetic_file_prefix: toulouse_` → le simulateur
charge `toulouse_population_<size>.json`.

```makefile
CONFIG ?= config_baseline_10000_current.yaml   # défaut du Makefile
```

⚠️ **Le défaut est la population de 10 000**, bien plus longue que celle de 1 000. Pour
reproduire le run de référence :

```bash
make run CONFIG=config_baseline_1000_current.yaml
```

#### Run destiné à alimenter la page de synthèse : désactiver le cache LLM

```bash
make run CONFIG=config_baseline_1000_nocache.yaml
```

**Pourquoi.** Une décision servie par le cache sémantique ne laisse **aucune trace** dans
`llm_exchanges.jsonl` — seulement une ligne dans `llm_cache_hits.jsonl`. Or c'est ce
journal, et lui seul, que le **volet 2** relit pour reconstruire son échantillon. Mesuré
sur le run du 2026-08-02 : 2 325 décisions servies par le cache, d'où 3 084 décisions dans
les volets 1 et 3 contre **23** dans le volet 2, et 27 strates sous le seuil d'effectif.
Les trois volets ne portaient plus le même run.

Le cache reste le bon réglage en production — il divise le coût LLM d'un run par plusieurs.
Il n'est désactivé que pour produire un **run de référence mesurable de bout en bout**.
Conséquence à anticiper : le run est plus lent, consomme beaucoup plus de quota, et
déclenche davantage d'alarmes de backlog et de 429.

#### Clé Google de la simulation

La simulation tourne sur la **clé 2** (`google2`, `google2_35`) : `docker-compose.yml`
blanchit `PROVIDER_KEYS__google` pour les conteneurs `api`, `controller` et `worker`. Un
provider sans clé est exclu de la rotation, donc `google_gemini31` et `google_gemini35`
sortent de la cascade — mistral, groq et cerebras restent en place (décision D4).

L'intérêt : les quotas free tier Gemini se comptent par projet **et par modèle**, et les
mesures du lot C (`common-set-eval`, `heldout-eval`) interrogent `google_gemini31`,
c'est-à-dire la **clé 1**. Elles tournent sur l'hôte, hors conteneurs, et gardent donc
leurs 500 requêtes/jour intactes pendant que la simulation consomme celles de la clé 2.

Pour rendre la clé 1 à la simulation le temps d'un run :

```bash
SIM_PROVIDER_KEYS__google="$PROVIDER_KEYS__google" make run CONFIG=...
```

Le Makefile avertit immédiatement si le fichier de config n'existe pas — les conteneurs
démarreraient alors avec des réglages par défaut (mode SOLARI, mauvais endpoints).

### 3.1 bis Fixer l'horizon d'arrêt ⚠️ avant de presser play

`simulation_max_days` est lu au démarrage depuis `GAMA/CityTransport/config/sim_params.yaml`
(`Settings.gaml`, `load_sim_config`), puis réécrit par GAMA au cycle 2. **Poser la valeur
dans ce fichier avant de lancer**, ou l'ajuster dans le panneau « Simulation » de l'IHM :

```yaml
# GAMA/CityTransport/config/sim_params.yaml
simulation_max_days: 1     # 24 h simulées : lundi 16 mars 5 h → mardi 5 h
```

`starting_date` est le **lundi 16 mars 2026 à 5 h** (`Settings.gaml`), un horizon de 1 jour
va donc du lundi 5 h au mardi 5 h.

Depuis le ticket 008 (A5), deux choses ont changé et rendent ce réglage effectif :

- le reflex `stop_after_max_days` exécute enfin **`do pause;`** — l'appel était commenté,
  le reflex écrivait un message et la simulation continuait : `simulation_max_days`
  n'arrêtait rien, et un run « de 24 h » en produisait trois ;
- la valeur est **transmise au contrôleur** au `/init` et consignée dans le
  `scenario_params.yaml` du répertoire d'expérience. Sans elle, rien dans un run archivé ne
  disait sur quel horizon il était censé porter.

⚠️ **Le reflex vit dans `global`, pas dans `experiment`.** `pause` est une action de
l'agent *simulation* ; l'agent expérience ne l'expose pas (ni `pause`, ni `halt`) et le
modèle **ne compile pas** si on l'y place. C'est d'ailleurs pourquoi l'instruction d'origine
était commentée : à sa place initiale, elle n'aurait jamais pu compiler. Les modèles livrés
avec GAMA emploient tous la même forme.

⚠️ **`pause`, pas `die`.** L'horloge s'arrête sans tuer les agents : les sorties restent
inspectables, et le contrôleur Python n'est pas interrompu — ses écritures en cours
(`moves.csv`, `llm_exchanges.jsonl`) se terminent normalement. Un `die` les couperait net.
**Le vérifier néanmoins sur un run court avant le run de référence** — une dernière ligne
tronquée se repère à la lecture, pas après coup.

La simulation étant en pause et non terminée, GAMA reste ouvert : arrêter les conteneurs
(`make down`) une fois le journal complet.

### 3.2 Lancer

```bash
make run CONFIG=config_baseline_1000_current.yaml
```

La cible enchaîne, dans cet ordre :
1. arrêt et suppression de Grafana/Prometheus, purge de `data/grafana_data` et
   `data/prometheus_data` (métriques repartant de zéro) ;
2. purge des compteurs Redis `wmetrics:*` ;
3. `make up` — tous les services (api, controller, worker, redis, otp, osmnx) ;
4. `make wait-ready` — attend l'API (8000, max 300 s), le controller (8002) et Grafana (3000) ;
5. lancement de GAMA : `/Applications/GAMA.app/Contents/MacOS/GAMA -p GAMA/CityTransport -o models/City.gaml -e e`.

**Ordre de démarrage impératif** : Docker **avant** GAMA. Le client WebSocket du controller
se reconnecte indéfiniment, il attend GAMA aussi longtemps qu'il faut — l'inverse n'est pas
vrai. Si les agents ne bougent pas, vérifiez dans les logs du controller la connexion à
`ws://host.docker.internal:3001`.

### 3.3 Surveiller pendant le run

```bash
make logs        # flux docker
make error       # ERROR + entrées [ALARME]  ← à consulter régulièrement
make warning
```

Les `[ALARME]` signalent un point de contention franchi (backlog pipeline, saturation LLM,
cache). Un run précédent s'est dégradé silencieusement pendant des heures — 886 agents sur
901 en attente, cache à 0 % — sans signal clair ; c'est ce qui a motivé cette
instrumentation. **Ne laissez pas tourner 4 h sans regarder `make error`.**

### 3.4 Vérifications de sortie

```bash
ls -la experiments/current                     # symlink → archive/<date>
ls experiments/current/
make report                                    # rapport de santé du run
make init                                      # découpage du temps d'initialisation
make capacity                                  # débit vs capacité LLM
```

Le dossier doit contenir au minimum `moves.csv`, `population_<n>.json`, `app.log`,
`llm_exchanges.jsonl`, `scenario_params.yaml`, `static_config.yaml`.

**L'horizon d'arrêt doit figurer dans `scenario_params.yaml`** (`simulation_max_days`,
depuis le ticket 008 A5) et le journal ne doit couvrir que cet horizon :

```bash
grep simulation_max_days experiments/current/scenario_params.yaml
llm-agents/.venv/bin/python - <<'EOF'
import csv, collections
from datetime import datetime, timezone
rows = list(csv.DictReader(open('experiments/current/moves.csv', encoding='utf-8')))
jours = collections.Counter(
    datetime.fromtimestamp(int(r['Temps simulé']), tz=timezone.utc).date().isoformat()
    for r in rows if r['Temps simulé'])
print('jours simulés :', dict(jours))
print('contraintes de chaîne :',
      dict(collections.Counter(r.get('Contrainte de chaîne', '') for r in rows)))
EOF
```

Un seul jour attendu. La colonne « Contrainte de chaîne » doit porter des `passager` non
nuls : à zéro, le mode passager n'a jamais été emprunté et c'est une régression, pas un
succès (cf. [vehicle-chain.md](../arch/vehicle-chain.md)).

**Contrôles métier — à faire avant d'épingler** (ils décident si le run est bon) :

```bash
RUN=experiments/current llm-agents/.venv/bin/python - <<'EOF'
import json, csv, collections, os
run = os.environ['RUN']
pop = json.load(open(f'{run}/population_1000.json'))
bike = {str(p['person_id']): p['identity']['traits_json'].get('personal_bike','')
        for p in pop}
rows = list(csv.DictReader(open(f'{run}/moves.csv')))
tot = collections.Counter(); velo = collections.Counter()
logement = collections.Counter()
for r in rows:
    owns = bike.get(str(r['ID Personne']), '').lower() != 'pas de vélo'
    tot[owns] += 1
    if r['Mode de transport Choisi'].strip() == 'Vélo': velo[owns] += 1
    logement[r.get('Type de logement', '').strip() or '<VIDE>'] += 1
print(f"part vélo globale : {100*sum(velo.values())/len(rows):.1f} %  (cible EMC² 4,1)")
print(f"vélo chez les non-propriétaires : {velo[False]} (doit être 0)")
print("type de logement :", dict(logement))
EOF
```

| Contrôle | Attendu | Si échec |
|---|---|---|
| Part vélo globale | **~12,9 %** (contre 18,8 % avant) | le correctif §1.1 n'est pas actif → ne pas épingler |
| Vélo chez les non-propriétaires | **0** | régression du garde de possession |
| Type de logement | 4 modalités peuplées, ~4,4 % vides | la population n'a pas été enrichie (§2.3) |

---

## 4 · Phase 3 — Épingler le run

Le run ne devient la référence de la page qu'ici.

```bash
# 1. Résoudre le symlink en chemin réel
readlink experiments/current        # → archive/2026-XX-XX_HH_MM

# 2. Éditer le manifeste
$EDITOR scripts/synthesis/sources.yaml
```

```yaml
common_set:
  # Chemin d'archive explicite, et non experiments/current : le symlink bouge à
  # chaque run, la page doit rester reproductible.
  run: experiments/archive/2026-XX-XX_HH_MM     # ← mettre à jour
```

**Ne mettez jamais `experiments/current`.** La page suivrait le symlink et décrirait un run
différent à chaque régénération ; c'est précisément ce que l'action A1 a supprimé.

Pour tester un run sans l'adopter : `make synthesis RUN=experiments/archive/<run>`.

---

## 5 · Phase 4 — Régénérer les trois volets

L'ordre compte : les deux premières commandes produisent les données que la troisième lit.

### 5.1 Volet 3 — modèle PROGEDO (local, gratuit)

```bash
make common-set-predict
```

Applique `mode_choice_policy.json` aux personas du run, dérive les six variables
géographiques par le résolveur de zone fine, renormalise sur les modes réellement proposés
par OTP, écrit `scripts/synthesis/data/progedo_on_common_set.parquet`.

**Prérequis** : `llm_module/data/zf_zones.gpkg` (hors dépôt, `make zones`, données PROGEDO
requises). Sans elle, le résolveur refuse de démarrer.

Si le contrat de features a changé, ré-entraîner d'abord : `make policy` (le parquet
d'entraînement est versionné — pas besoin des données brutes).

### 5.2 Volet 2 — calibration sur le jeu commun (128 appels LLM)

⚠️ **Seule étape coûteuse.** Quota Google : RPD 500 par projet et par modèle, réinitialisé
à **minuit Pacific = 07:00 UTC**. Deux clés (`PROVIDER_KEYS__google`,
`PROVIDER_KEYS__google2`), seaux distincts.

```bash
DRY_RUN=1 make common-set-eval    # chiffrer sans émettre un seul appel
make common-set-eval              # 2 évals × 64 lots de 8 personas, ~20 min
```

**Ne sondez pas les quotas.** Un seau épuisé laisse passer une petite rafale : une sonde de
4 appels a déjà répondu 4/4 sur une clé qui s'est effondrée en `429 · limit: 500` après
~59 appels — perdus, car la garde de couverture est tout-ou-rien et n'écrit rien tant que
l'éval n'est pas complète. Seul le 429 lu dans le corps de la réponse est fiable.

**Le cooldown est global, les seaux ne le sont pas.** À l'épuisement d'une clé, le script
écrit une ligne `cooldown` de portée `global` dans `calibration.db` — qui bloque aussi
`PROVIDER=google2`, dont le seau est pourtant distinct. Pour basculer sur la seconde clé
sans attendre le reset, effacer la ligne :

```bash
llm-agents/.venv/bin/python -c "import sqlite3; c=sqlite3.connect('prompt_calibration/calibration_results/calibration.db'); c.execute('delete from cooldown'); c.commit()"
```

Comptez ~23 % de lots revenant amputés, rattrapés automatiquement par re-tir en moitiés
(mécanisme de l'action A10) — c'est déjà dans le chiffrage.

### 5.3 Régénérer la page

```bash
make synthesis
```

**Vérification de sortie** : `Sources : 13 présentes, 0 manquantes`.

### 5.4 Ce qu'il ne faut PAS refaire

| Commande | Pourquoi |
|---|---|
| `make heldout-eval` | Le jeu de test gelé est indépendant du run (G4). Rejouer = brûler du quota pour rien |
| `make policy` | Le modèle est entraîné sur l'enquête, pas sur le run |
| `make zones`, `make housing-type` | Ressources dérivées de PROGEDO, indépendantes du run |

---

## 6 · Phase 5 — Contrôle final

```bash
# Suite de tests — référence actuelle : 672 passed
llm-agents/.venv/bin/python -m pytest scripts/tests llm_module/tests llm-agents/tests -q

# Dépôt autonome de calibration — référence actuelle : 350 passed, 14 skipped
cd prompt_calibration && .venv/bin/python -m pytest calibration/tests -q; cd -

# La page est-elle reproductible ? Deux générations doivent coïncider hors horodatage
make synthesis && make synthesis
```

Ouvrir `docs/synthesis/index.html` (`make synthesis-open`) et vérifier :

- [ ] Le bandeau « Jeu d'évaluation commun » affiche le **nouveau** run et son empreinte.
- [ ] Il annonce un **jour simulé** unique, et les trois volets s'accordent sur ce jour et
      sur leurs effectifs — le vérifier en comparant les `n`, pas en le supposant.
- [ ] Le bilan de lecture affiche les **replis d'erreur LLM exclus** et les lignes écartées
      par le filtre de jour.
- [ ] La ventilation **Contrainte de chaîne** apparaît et n'est pas à 100 % « aucune ».
- [ ] L'axe **Type de logement** de la couverture n'est plus à zéro.
- [ ] La part **vélo** du volet 1 est retombée (~12,9 % attendu).
- [ ] Les couronnes de **lieu de résidence** sont recalculées sur l'hypercentre unifié.
- [ ] La matrice comparative porte ses **sept colonnes**, chacune déclarant son substrat,
      son effectif et son régime.
- [ ] La liste d'actions ne revendique rien de faux.

⚠️ **Piège de lecture** : les scores ne sont comparables qu'à effectif comparable. JSD et
EMD sont biaisées vers le haut sur les petits échantillons — la simulation restreinte aux
personnes de l'échantillon du volet 2 perd **+5,0 points** sans qu'aucune décision change.
C'est le rôle de la colonne « Sim. (éch. V2) ». Ne comparez jamais une colonne à 5 945
décisions à une colonne à 509 sans passer par elle.

---

## 7 · Retour arrière

Aucune étape n'est destructive tant que le manifeste n'est pas modifié.

```bash
# 1. Restaurer l'ancien run dans sources.yaml
$EDITOR scripts/synthesis/sources.yaml     # run: experiments/archive/2026-07-29_18_34

# 2. Restaurer les artefacts du volet 2 (l'échantillon dépend du run)
#    → soit depuis git, soit en rejouant make common-set-eval (128 appels)

# 3. Régénérer
make common-set-predict && make synthesis
```

Les pages archivées sous `docs/synthesis/archive/<date>/` permettent de comparer avant/après
sans rien rejouer.

---

## 8 · Récapitulatif — chemin le plus court

Population existante déjà enrichie, correctif vélo commité :

```bash
make run CONFIG=config_baseline_1000_current.yaml   # ~4 h 20 (1 000 agents)
make error                                          # à surveiller pendant le run
readlink experiments/current                        # → chemin à épingler
$EDITOR scripts/synthesis/sources.yaml              # common_set.run
make common-set-predict                             # volet 3, gratuit
DRY_RUN=1 make common-set-eval && make common-set-eval   # volet 2, 128 appels
make synthesis                                      # 13 sources, 0 manquante
llm-agents/.venv/bin/python -m pytest scripts/tests llm_module/tests llm-agents/tests -q
```

---

## Voir aussi

- [`ticket_006_relance_run_reference.md`](ticket_006_relance_run_reference.md) — **pourquoi** et **quand** relancer
- [`ticket_005_mode_choice_model.md`](ticket_005_mode_choice_model.md) — politique PROGEDO (volet 3)
- `docs/arch/score-synthesis.md` — définition du score et des trois volets
- `docs/changelog.md` — actions A1 à A10
- `.claude/CLAUDE.md` — ordre de démarrage, `[ALARME]`, outils de diagnostic
