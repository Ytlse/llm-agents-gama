# prompt_calibration — nouvelle version (ticket 004)

Réécriture industrialisée de l'outil de calibration de prompt.
L'ancienne version (`scripts/models_influence/prompt_calibration.ipynb` +
`prompt_calibration_lib.py`) est **conservée intacte** comme référence.

Plan complet : `docs/tickets/ticket_004_prompt_calibration_industrialisation.md`
· Architecture : `docs/arch/prompt_calibration.md`

## État

| Phase | Contenu | État |
|---|---|---|
| 0 | Mesure fiable : métadonnées structurées, jeux gelés, temp d'éval minimale | ✅ 2026-07-13 |
| 1 | Package complet + store SQLite + CLI reprenable | ✅ 2026-07-13 |
| 2 | Dashboard Streamlit (Timeline / DAG / Distribution / Run) | ✅ 2026-07-13 |
| 3 | Loss v2 (EMD/JSD) + acceptation bootstrap + backtest rétroactif | ✅ 2026-07-14 |
| 4 | Rendement : tabu, entonnoir multi-candidats, opérateurs riches + bandit UCB, compaction | ✅ 2026-07-14 |
| 5 | Attribution de crédit Shapley (Monte-Carlo tronqué, jeu screen) | ✅ 2026-07-14 |
| 6+ | Îlots + merge + Pareto, bibliothèque d'arguments | à venir |

## Contenu

```
calibration/
  config.py       # EVAL_TEMP = 0.0, bornes des splits, seuil de couverture
  exchanges.py    # lecture robuste de llm_exchanges.jsonl (JSONL ou JSON concaténé)
  metadata.py     # jointure agent_id → traits_json (zéro inférence textuelle) ;
                  # strip_memory_section (exclusion STM/LTM des jeux val/test)
  datasets.py     # jeux train/val/test gelés (sha256(agent_id) % 100), versionnés
  # ── phase 1 ──
  models.py       # RunConfig (YAML) + pydantic (Block, Mutation, Scores, EvalResult)
  blocks.py       # decompose_prompt / blocks_to_prompt (purs, testés)
  metrics.py      # Metric (interface pluggable) + L1Composite + worst_strata
  evaluation.py   # micro-batching + appels provider + cache adressé par contenu
  mutation.py     # opérateurs (modify/delete/insert + reorder/merge/condense/split) ;
                  # multi-candidats (propose_candidates) + formatage carte de contribution
  loop.py         # boucle reprenable : entonnoir (tabu→screening→best), bandit, compaction
  store.py        # RunStore SQLite : DAG nœuds/mutations/évals/ablations/tabu/bandit
  export.py       # export lisible (nodes.csv, mutations.csv, history.md)
  importer.py     # import one-shot des artefacts de l'ancienne version
  cli.py          # calibrate run / resume / status / export / import / backtest / dashboard
  # ── phase 3 ──
  stats.py        # acceptation bootstrap appariée + non-infériorité (compaction)
  backtest.py     # recalcul rétroactif de losses sur le store (zéro LLM)
  # ── phase 4 ──
  tabu.py         # archive tabu dure (embedding local + cosinus + tenure)
  bandit.py       # bandit UCB1 de sélection d'opérateur (persisté par branche)
  # ── phase 5 ──
  shapley.py      # attribution de crédit Shapley (Monte-Carlo tronqué, jeu screen)
  # ── phase 2 ──
  dashboard_data.py # requêtes de lecture du store (pures, testées)
  dashboard.py    # dashboard Streamlit (Timeline / DAG / Distribution / Run)
  tests/          # pytest (189 tests)
check_phase0.py   # critère d'acceptation phase 0 sur une expérience réelle
run.example.yaml  # gabarit de RunConfig
```

## Utilisation

### Raccourcis Makefile

Le plus simple, depuis `scripts/prompt_calibration/` :

```bash
make run essai3      # lance ou relance/reprend l'essai 3 (branche isolée essai3)
make ui              # ouvre l'interface (dashboard Streamlit)
make status essai3   # état de l'essai 3
make export essai3   # export lisible (CSV + timeline)
make finalize essai3 # éval test + bilan avant/après (dry-run ; WRITE=1 publie)
make help            # liste toutes les cibles et options
```

Un « essai » = une **branche isolée** dans le store SQLite ; on peut donc lancer
plusieurs campagnes en parallèle et les reprendre indépendamment. Pour `essaiN` :
la branche vaut `essaiN` et la config est `runN.yaml` si le fichier existe, sinon
`run.yaml`. Options : `ITER=20`, `ISLANDS=4`, `PORT=8502`, `CONFIG=run.yaml`.

### CLI directe

Avec le venv du projet (`llm-agents/.venv`), depuis `scripts/prompt_calibration/` :

```bash

# Tests unitaires
$python  -m pytest -q

# 1. Générer une version de jeux gelés (train garde la mémoire, val/test non)
$PY -m calibration.datasets ../../experiments/current calibration_datasets v1

# 2. Lancer / reprendre une campagne (relancer la même commande reprend au point d'arrêt)
$python  -m calibration.cli run --config run.example.yaml

# 3. État, export lisible, import d'un ancien run
$python  -m calibration.cli status --config run.example.yaml
$python  -m calibration.cli export --config run.example.yaml --out calibration_results/export
$python  -m calibration.cli import ../models_influence/calibration_results --config run.yaml

# 4. Dashboard temps réel (lecteur pur du store, rafraîchissable pendant un run)
$python -m calibration.cli dashboard --config run.yaml

```markdown

**Dashboard** (phase 2) : cinq vues — **Timeline** (toutes les mutations depuis
l'origine, score composite ET par dimension, filtres + courbe du meilleur score),
**DAG** (graphe de lignée coloré par score, sélection d'un nœud → prompt, diff vs
parent, ablation), **Distribution** (parts modales actuel vs EMC² + pires
croisements strate × mode), **Run** (itération, modèles/températures, volumétrie),
**Maintenance** (les commandes `status` / `export` / `import` depuis l'UI :
statut lisible, export lisible avec boutons de téléchargement, import d'un ancien
run derrière une case de confirmation car il **écrit** dans le store).
La vue est pilotable par query param (`?view=DAG`) pour des liens partageables.
La logique de requête (`dashboard_data.py`) est pure et testée ; `dashboard.py`
ne fait que le rendu. Le dashboard n'écrit **jamais** dans le store (lecture WAL
concurrente pendant un run). Nécessite `streamlit` (`pip install streamlit`).

**Essai unique + paliers progressifs (défaut, `n_candidates: 1`)** : à chaque
itération, un **seul essai** est proposé, puis filtré par des **paliers à 25/50/75 %**
(`racing_rungs`) du train — dès qu'un palier n'améliore pas le composite du prompt
courant sur le même sous-échantillon, l'essai est **abandonné** (`rejected_race`) sans
payer l'éval complète ni les paliers suivants ; sinon il passe l'**éval complète** +
le test bootstrap. L'opérateur suggéré au mutateur est arbitré par un **bandit UCB1**
(récompense = acceptation). Toutes les `compact_every` acceptations (+ en fin de
campagne), une **passe de compaction** retire les blocs de contribution ≈ nulle sous
test de **non-infériorité** (« réduire tant que ça ne dégrade pas le score »). Tout est
visible au dashboard et réversible par lignage.

**Entonnoir multi-candidats (phase 4, `n_candidates > 1`)** : le mutateur produit
`n_candidates` candidats en **un seul appel** ; ils passent un entonnoir — (1) **filtre
tabu** gratuit (quasi-doublons de mutations déjà rejetées, ré-éligibles après
`tabu_tenure` acceptations), (2) sélection du meilleur par **screening** (`screen`,
~20 % du train) ou, si `racing_enabled: true`, par un **racing ciblé par strate**
(*gate* sur la strate la plus mal représentée puis *successive halving* sur des
fractions croissantes, garde-fou : pas d'élimination sous `racing_min_gap` ni si l'IC
bootstrap chevauche), (3) **éval complète** + test bootstrap sur ce seul candidat. Voir
`docs/arch/prompt_calibration.md` §2.4.

**Attribution de crédit Shapley (phase 5)** : après **chaque** acceptation (et à
l'init), la contribution de chaque bloc est recalculée **globalement** par une **valeur
de Shapley** (`shapley.py`) — contribution marginale moyenne sur des permutations
aléatoires, qui répartit exactement le gain entre blocs (redondances et synergies
comprises, là où le retrait un-bloc-à-la-fois se trompe). Échantillonnage **Monte-Carlo
tronqué** (`shapley_permutations`, arrêt dès que la loss complète est atteinte) sur le
jeu `screen`, coalitions servies par le cache content-addressed (le coût du recalcul à
chaque acceptation est ainsi amorti). Résultats dans `ablations` (`method='shapley'`).

**Contexte fourni au mutateur** : le prompt **système** du mutateur porte une
**légende unique** (abréviations des dimensions + **conventions de signe** : composite =
perte à minimiser ; Δ>0 = bloc utile ; dans les crochets/colonnes, « + » = le bloc aide
la dimension, « − » = il la dégrade) — plus de légende répétée au coup par coup. La
contribution des blocs est présentée en **table markdown bloc × dimension**
(`format_contrib_table`) plutôt qu'en crochets compacts, complétée du diagnostic mode
des seuls blocs nuisibles. Enfin, une **consigne de diversité** rappelle les blocs
récemment modifiés (`_recent_blocks`) et pousse à cibler d'autres blocs ; en mode
multi-candidats, chaque candidat doit porter sur un **bloc distinct**, et l'entonnoir
écarte sans éval les doublons de bloc (verdict `rejected_dup_block`) — ça casse la
tendance du mutateur à toujours retoucher le même bullet.

**Reprise** : toute la campagne vit dans un unique `calibration.db` (DAG
content-addressed). Tuer le process puis relancer `run`/`resume` repart à
l'itération suivante — évals servies par le cache, mutations rejouées : zéro appel
LLM redondant. L'init n'est refaite que si le store est vide pour la branche.

Les jeux gelés ne sont **jamais modifiés** : toute évolution crée `v2/`, avec son
`manifest.yaml`. Le jeu `test` n'est évalué qu'une fois, en fin de campagne.
