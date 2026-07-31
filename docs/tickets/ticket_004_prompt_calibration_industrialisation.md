# Ticket 004 — Industrialisation de `prompt_calibration`

Plan de refonte du module de calibration de prompt (`scripts/models_influence/`)
issu du brainstorming du 2026-07-13. Documentation associée :
`docs/arch/prompt_calibration.md`.

**Objectif global** : passer d'un notebook expérimental à un moteur de calibration
robuste, reprenable à tout moment, multi-branches, avec une mesure fiable et un
tableau de bord persistant.

**État d'avancement** : Phases 0-7 livrées (0-5 les 2026-07-13/14 ; 6 et outillage 7
le 2026-07-15) dans le nouveau package `scripts/prompt_calibration/` (voir DN
ci-dessous). Reste opérationnel : lancer la campagne de validation complète et publier
le prompt gagnant (l'outillage `calibrate finalize` est prêt).

---

## 0 · Registre des décisions

### Décisions adoptées

| # | Décision | Détail |
|---|---|---|
| D1 | Loss pluggable EMD/JSD/vraisemblance | Documentée dans `docs/arch/prompt_calibration.md` §2.2 — implémentation en phase 3 |
| D2 | Store **SQLite** (justification §1 ci-dessous) + export lisible | Historique = DAG git-like, décisions brutes conservées |
| D3 | Archive tabu **dure** des mutations rejetées, avec tenure | Rejet avant éval par similarité ; re-éligibilité après N mutations acceptées |
| D4 | Maximiser le groupement des **requêtes d'évaluation** (itinéraires) | C'est l'éval qui est recalculée à chaque mutation → gros batches, pas de requête unitaire |
| D5 | Dashboard **Streamlit** | Timeline de TOUTES les mutations depuis l'origine avec score associé + vue DAG |
| D6 | Métadonnées structurées (jointure `agent_id → population.json`) ; jeux train/val/test gelés et versionnés ; température d'éval **minimale** (pas de mesure de plancher de bruit par répétition — trop cher en tokens) | Le genre existe déjà dans `traits_json.gender` : `infer_gender_from_name` est supprimée |
| D7 | Branches parallèles (îlots) + merge | Assumé malgré le surcoût d'éval |
| D8 | Revue de littérature avec scores de similarité | Faite — tableau dans `docs/arch/prompt_calibration.md` §5 |
| DA | Test statistique d'acceptation (bootstrap) | Phase 3 |
| DB | Attribution de crédit **Shapley** (développée §6 ci-dessous) | Remplace l'ablation globale périodique |
| DC | Archive **Pareto** légère (expliquée §7 ci-dessous) | Le composite reste le critère d'acceptation ; le Pareto sert à choisir les points de départ des branches |
| DD | Multi-candidats par appel de mutation + entonnoir de screening | Phase 4 |
| DE | Opérateurs de mutation riches + bandit UCB | Phase 4 |
| DF | Extraction du moteur en package Python testé + CLI | Phase 1 — prérequis de tout le reste |
| DG | **Un seul** modèle d'évaluation (épinglé, même modèle pour train/val/test) + **un** modèle distinct pour les mutations | La calibration est spécifique à un modèle ; le modèle de mutation est séparé pour préserver le quota d'éval |
| DL | Bibliothèque d'arguments comportementaux capitalisée | Phase 6 |
| DM | **Minimisation du prompt à score constant** (économie de tokens) | Passes de compaction dédiées — phase 4 §4.5 |
| DN | La nouvelle version est développée dans **`scripts/prompt_calibration/`** (décision du 2026-07-13) | L'ancienne version (`scripts/models_influence/prompt_calibration.ipynb` + `prompt_calibration_lib.py`) est **conservée intacte** comme référence jusqu'à la bascule complète — aucune modification de l'ancien code, le nouveau package n'en hérite simplement pas les défauts (globals, regex fragiles, inférence du genre) |

### Décisions écartées (et pourquoi)

| Idée | Raison du rejet |
|---|---|
| Calibration multi-modèles / test de transfert | Une calibration = un modèle. Changer de modèle ⇒ recalibration en partant du prompt d'un modèle proche |
| Comptabilité coût/budget par itération | Non prioritaire |
| Observabilité `[ALARME]` / logs structurés dédiés | Non prioritaire |
| Reproductibilité étendue (seeds multiples, hash des données dans chaque nœud) | Non prioritaire — la reprise par store suffit |
| Garde-fou sémantique automatique sur les contraintes du mutateur | Non prioritaire — les contraintes restent dans le system prompt du mutateur |
| Mesure du plancher de bruit par évals répétées | Trop cher en tokens → température d'évaluation minimale à la place |
| DTW comme métrique | Inadapté aux distributions catégorielles (métrique de séries temporelles) — remplacé par EMD |

---

## 1 · Pourquoi SQLite et pas des CSV lisibles ?

Question légitime — réponse en 4 points, puis la mitigation lisibilité :

1. **L'historique est un DAG, pas une table.** Avec les branches (D7) et les merges,
   un nœud a 1 ou 2 parents ; les évals, mutations, ablations et scores se rattachent
   aux nœuds. En CSV plat il faudrait 5 fichiers reliés par des IDs maintenus à la
   main — c'est une base relationnelle dessinée en ASCII, avec les bugs en plus.
2. **Écritures concurrentes sûres.** Le run écrit pendant que le dashboard Streamlit
   lit (D5). SQLite est ACID (journal WAL) ; un CSV lu pendant une écriture peut être
   tronqué, et un crash en cours d'append le corrompt silencieusement.
3. **Requêtes du dashboard.** « Toutes les mutations de la branche B triées par score »,
   « les évals du nœud X », « le front de Pareto » = un `SELECT` avec jointure. En CSV :
   tout charger en mémoire et recoder les jointures en pandas à chaque refresh.
4. **Zéro infrastructure.** Un seul fichier `calibration.db`, stdlib Python
   (`sqlite3`), pas de serveur.

**Mitigation lisibilité** (le vrai besoin derrière le CSV) :
- commande `calibrate export` → CSV/Markdown par table dans `calibration_results/export/` ;
- le dashboard EST la vue lisible de l'historique ;
- au besoin, [datasette](https://datasette.io) ou DB Browser for SQLite ouvrent le
  fichier directement.

**Verdict : SQLite retenu**, avec export lisible fourni dès la phase 1.

### Schéma cible (esquisse)

```sql
-- Un prompt = un nœud, identifié par le hash de son texte (comme un commit git)
CREATE TABLE nodes (
  hash        TEXT PRIMARY KEY,          -- sha256(prompt_text)[:16]
  prompt_text TEXT NOT NULL,
  blocks_json TEXT NOT NULL,             -- décomposition en blocs
  parent      TEXT REFERENCES nodes,     -- NULL pour le seed
  parent2     TEXT REFERENCES nodes,     -- non-NULL pour un merge
  branch      TEXT NOT NULL,             -- nom de l'îlot ("main", "isl-1", …)
  iteration   INTEGER,
  created_at  TEXT
);

CREATE TABLE mutations (
  id          INTEGER PRIMARY KEY,
  node_from   TEXT REFERENCES nodes,
  node_to     TEXT,                      -- NULL si mutation invalide/rejetée avant éval
  operator    TEXT,                      -- modify / delete / insert / reorder / merge_blocks / condense / crossover
  target_block TEXT,
  new_content TEXT,
  rationale   TEXT,
  verdict     TEXT,                      -- accepted / rejected_score / rejected_stat / rejected_tabu / vetoed / invalid
  reject_cause TEXT                      -- ex : "motif +12.3" — nourrit le mutateur
);

-- Décisions BRUTES conservées → toute métrique est recalculable rétroactivement
CREATE TABLE evals (
  id          INTEGER PRIMARY KEY,
  node_hash   TEXT REFERENCES nodes,
  dataset     TEXT,                      -- train / val / test / screen
  decisions   TEXT NOT NULL,             -- JSON [(agent_id, mode), …]
  scores_json TEXT NOT NULL,             -- scores calculés avec la loss active
  eval_model  TEXT, eval_temp REAL,
  created_at  TEXT
);

-- Score par BLOC × CRITÈRE (le « score pour chaque phrase pour chaque critère »
-- du brainstorming) : delta composite ET détail par dimension
CREATE TABLE ablations (
  node_hash   TEXT REFERENCES nodes,
  block_name  TEXT,
  method      TEXT,                      -- loo (leave-one-out) / shapley
  value       REAL,                      -- delta composite ou valeur de Shapley
  scores_json TEXT,                      -- deltas par dimension : {global, age, occupation, genre, motif, distance}
  diag        TEXT
);

CREATE TABLE tabu (
  embedding   BLOB,                      -- embedding de (target_block + new_content)
  mutation_id INTEGER REFERENCES mutations,
  expires_after_accepted INTEGER         -- tenure : re-éligible après N acceptations
);
```

---

## 2 · Phase 0 — Fiabiliser la mesure *(prérequis absolu : on n'optimise pas contre une mesure fausse)*

### 0.1 Métadonnées structurées (remplace le parsing regex)

Constat (vérifié dans le code le 2026-07-13) :
- le genre **existe** dans `traits_json.gender` de `population_N.json`, mais
  `_build_profile_narrative` (`llm-agents/urban_mobility_agents/agents/llm_agent.py:111`)
  ne le rend pas dans le texte → la lib l'infère du prénom (`infer_gender_from_name`),
  avec des erreurs connues ;
- **dérive de format** : les logs actuels utilisent `--- agent_id=503036 | … ---`,
  la lib attend `--- PERSONA <id> | … ---` → `PERSONA_RE` et `split_entry_personas`
  ne matchent plus les logs récents.

Tâches :
- [x] Charger `population_N.json` de l'expérience source et construire
      la jointure `agent_id → traits_json`
      (gender, age, main_occupation, household_size, …) — le texte du persona
      ne sert plus qu'au LLM, jamais au scoring.
      → `calibration/metadata.py` (`load_population`, `build_decision_records`)
- [x] Adapter le split des sections au format d'en-tête courant
      (`--- agent_id=… | Destination : … ---`), en gardant la distance min
      extraite des options de trajet (seule métadonnée réellement textuelle).
      → les DEUX formats (courant + legacy `PERSONA`) sont supportés ; lecture
      robuste du journal (JSONL strict OU objets pretty-printed concaténés —
      le format réel du fichier courant) dans `calibration/exchanges.py`
- [x] `infer_gender_from_name`, `PERSONA_RE`, `normalize_occupation` : absentes
      du nouveau package (DN : l'ancienne lib est conservée intacte, on ne la
      modifie pas). L'occupation vient des traits via un mapping 1:1 vérifié ;
      toute valeur hors table lève une erreur au lieu de deviner.
- [x] Tests unitaires de parsing sur des extraits réels des deux formats —
      `calibration/tests/` (28 tests, pytest vert).

**Critère d'acceptation** : 100 % des entrées `itinary_multi_agent` du
`llm_exchanges.jsonl` courant sont rattachées à leurs métadonnées exactes ;
le genre provient de `traits_json.gender` (zéro inférence).
✅ **Vérifié le 2026-07-13** (`check_phase0.py` sur `experiments/current`) :
720/720 sections rattachées (209 entrées, 436 agents distincts).

### 0.2 Jeux gelés, stratifiés, versionnés

✅ **Implémenté le 2026-07-13** — `calibration/datasets.py` : affectation
`sha256(agent_id) % 100` (stable inter-process, contrairement à `hash()`),
gel dur (réécrire une version existante lève une erreur), `manifest.yaml`
(hash des sources, date, effectifs par jeu et par strate), rapport de
couverture sur les marginales Cerema avec warning explicite par strate sous
le seuil. CLI : `python -m calibration.datasets <experiment> <out> <version>`.
La génération est **refusée** si la jointure n'est pas à 100 %.

Proposition (répond à « tu proposes quoi ? ») :

- **Affectation stable par hash** : `hash(agent_id) % 100` → `[0-69]` train,
  `[70-84]` val, `[85-99]` test. Un agent ne change jamais de jeu, même si on
  régénère les fichiers ou qu'on ajoute des données.
- **Stratification par quotas** : l'échantillonnage dans chaque jeu vise les
  marginales EMC² (âge × occupation × distance × motif) pour qu'aucune strate ne
  passe sous le seuil d'effectif. Rapport de couverture imprimé à la génération
  (strates manquantes = warning explicite).
- **Gel et versionnage** : `calibration_datasets/v1/{train,val,test}.jsonl`
  + `manifest.yaml` (hash du fichier source, date, seed, effectifs par strate).
  Un jeu n'est **jamais modifié** — toute évolution = `v2/` + nouveau manifest.
  Le store enregistre la version de dataset utilisée par chaque éval.
- **Rôles** : train = boucle d'optimisation ; val = early stopping (toutes les
  5 itérations, comme aujourd'hui) ; **test = une seule éval, à la fin d'une
  campagne**, jamais vu par la boucle — c'est le chiffre publiable.

Tâche restante :
- [x] **Ne pas envoyer les sections mémoire (STM/LTM) dans les évals val et
      test** ✅ 2026-07-13 : `strip_memory_section` (`calibration/metadata.py`)
      retire la section `**Historique :**` du persona ; `build_datasets` l'applique
      aux jeux **val** et **test** uniquement (le train la conserve). Vérifié sur
      `experiments/current` : val 0/119 et test 0/106 personas conservent
      `**Historique :**` (train inchangé). La mesure de référence ne dépend plus
      que du profil démographique, du contexte météo et des options de trajet.

### 0.3 Température d'évaluation minimale

- [x] `EVAL_TEMP = 0.0` pour train/val/test → `calibration/config.py`.
- [x] Noter dans la doc : le non-déterminisme résiduel du provider existe ; c'est le
      test statistique (phase 3) qui protège contre le bruit d'échantillon restant.
      → docstring de `calibration/config.py` + `docs/arch/prompt_calibration.md` §2.3.

**Effort phase 0 : S-M (2-3 j).** ✅ **Phase 0 livrée le 2026-07-13**
(`scripts/prompt_calibration/`, voir DN) — reste une tâche ajoutée a posteriori :
exclusion des sections mémoire STM/LTM des jeux val/test (§0.2).

---

## 3 · Phase 1 — Package `calibration/` + store SQLite *(la fondation)*

### 1.1 Extraction du moteur (DF)

Cible : en finir avec `configure()` + globals de module (non testable, état invisible).

```
scripts/prompt_calibration/calibration/     # emplacement acté par DN
  __init__.py
  models.py       # pydantic : Block, BlockSet, Mutation, EvalResult, Scores, RunConfig
  blocks.py       # decompose_prompt, blocks_to_prompt (pur, testé)
  metadata.py     # jointure population, buckets Cerema (phase 0)
  datasets.py     # génération/chargement des jeux gelés (phase 0)
  metrics.py      # interface Metric + L1Composite (puis EMD/JSD/… en phase 3)
  evaluation.py   # micro-batching, appels provider, retry, cache
  mutation.py     # génération, opérateurs, application, tabu
  store.py        # RunStore (SQLite) : nodes/mutations/evals/ablations/tabu
  loop.py         # boucle d'optimisation (recuit → phases 4-6 la font évoluer)
  cli.py          # calibrate run / resume / export / status
  tests/
```

- [x] Tout paramètre passe par `RunConfig` (pydantic, chargé d'un YAML) — plus
      aucun global mutable. → `calibration/models.py`
- [ ] Le notebook devient un client : il importe le package, lance/reprend un run
      et affiche les visualisations. Aucune logique métier dans les cellules.
      *(La CLI `calibrate` couvre run/resume/export ; la bascule du notebook en
      simple client de visualisation est à finaliser avec le dashboard phase 2.)*
- [x] Tests unitaires sur les parties pures ✅ 2026-07-13 (65 tests verts) :
      décomposition/reconstruction de blocs (aller-retour **idempotent**),
      métriques (strate sous le seuil, mode absent, df vide), application des
      mutations (modify/delete/insert + cas invalides), micro-batching
      (agent_id unique/lot, agent récurrent réparti).

### 1.2 RunStore SQLite (D2)

- [x] Schéma du §1 ✅ 2026-07-13 (`calibration/store.py`) ; API :
      `get_or_create_node`, `cached_eval` / `record_eval`, `record_mutation` /
      `update_mutation`, `record_ablation`, `lineage`, `best(branch)`,
      `save_run_state` / `resume_state`. Journal WAL (lecture concurrente pour le
      dashboard). Tables `tabu` / `parent2` présentes pour les phases 4/6.
- [x] **Reprise** ✅ 2026-07-13 : la boucle snapshote son état à chaque itération
      (`run_state`) et repart exactement à l'itération suivante ; l'init (run
      initial + ablation) ne s'exécute que si le store n'a pas d'état pour la
      branche — « ne refaire l'init que si on part de 0 ». Testé de bout en bout
      (`test_loop.py` : reprise = zéro appel provider ni mutation redondant).
- [x] Cache d'éval adressé par contenu ✅ 2026-07-13 : clé =
      (hash prompt) × dataset × (params provider/modèle/temp/samples), rangé dans
      `evals` avec les décisions brutes.
- [x] Script d'import one-shot ✅ 2026-07-13 (`calibration/importer.py`,
      `calibrate import`) : rejoue `mutations.jsonl` sur le seed et attache les
      scores de `calibration_history.csv` (les décisions brutes de l'ancien run ne
      sont pas récupérables — l'ancien `eval_cache` est adressé par un hash
      incompatible ; l'import assure la continuité de l'historique, pas le
      recalcul rétroactif de l'ancien run).

### 1.3 Export lisible

- [x] `calibrate export` ✅ 2026-07-13 (`calibration/export.py`) → `export/nodes.csv`,
      `export/mutations.csv`, `export/history.md` (timeline lisible : branche,
      itération, opérateur, bloc, verdict, composite, rationale).

**Critère d'acceptation** ✅ **atteint le 2026-07-13** : la reprise (`calibrate
resume`) repart à l'itération suivante sans aucun appel LLM redondant (vérifié par
`test_loop.py` avec évaluateur/mutateur déterministes) ; `pytest` vert (65 tests) ;
l'historique complet est requêtable en SQL et exportable.

**Effort phase 1 : L (4-6 j).** ✅ **Phase 1 livrée le 2026-07-13.**
Restes mineurs reportés : bascule du notebook en simple client de visualisation
(à faire avec le dashboard phase 2).

---

## 4 · Phase 2 — Dashboard Streamlit (D5)

Lecteur pur du store (aucune écriture), rafraîchi pendant les runs.

✅ **Phase 2 livrée le 2026-07-13** — `calibration/dashboard.py` (rendu Streamlit)
+ `calibration/dashboard_data.py` (requêtes de lecture **pures**, 11 tests). La
logique de requête est isolée du rendu → testable sans Streamlit. La vue est
pilotable par query param (`?view=DAG`, lien partageable). Synchronisation
bidirectionnelle URL ↔ radio.

- [x] **Vue Timeline** *(demande explicite)* : toutes les mutations **depuis
      l'origine** — itération, branche, opérateur, bloc ciblé, rationale, verdict,
      **score composite et par dimension** — avec filtres (branche, verdict,
      opérateur, plage d'itérations) et courbe du meilleur score superposée
      (min cumulé, ignorant les mutations vétoées/non évaluées).
- [x] **Vue DAG** : graphe de lignée des prompts (plotly), un axe par branche,
      merges (`parent2`) en tireté, nœud coloré par composite ; sélection d'un
      nœud → prompt complet, diff vs parent (difflib), scores tous jeux, carte
      d'ablation. Nœuds d'ablation (sans itération) exclus du DAG affiché.
- [x] **Vue Distribution** : barres actuel vs EMC² (global) reconstruites depuis
      les **décisions brutes** stockées (zéro réappel LLM) ; pires croisements
      strate × mode (`worst_strata_modes`).
- [x] **Vue Run** : branche active, itération courante, acceptées, meilleur
      composite/val, modèles/températures d'éval et de mutation, volumétrie
      d'éval par jeu, early-stopping val (`val_no_improve`). *(Le hit-rate de
      cache instrumenté n'est pas persisté par la boucle — reporté ; la vue
      montre les comptages d'éval réels du store.)*
- [x] Lancement : `calibrate dashboard` (wrapper `streamlit run`).
- [x] **Vue Maintenance** *(ajout 2026-07-13, demande utilisateur)* : exécute
      depuis l'UI les commandes `calibrate status / export / import` — statut
      lisible, export lisible avec boutons de téléchargement, import d'un ancien
      run derrière une case de confirmation (l'import **écrit** dans le store,
      seule exception au lecteur pur). Helpers `export_readable` /
      `import_legacy_run` / `seed_blocks_for` dans `dashboard_data.py` (testés).
      Vérifié de bout en bout dans le navigateur : export → 3 fichiers + message +
      téléchargements ; import → 8 mutations écrites dans le store.
- [x] **Bug CLI corrigé** : `--config` / `--branch` n'étaient acceptés qu'avant la
      sous-commande (argparse) → désormais acceptés **avant ou après**
      (`default=SUPPRESS` sur les sous-parsers). `calibrate dashboard --config x`
      fonctionne.

**Critère d'acceptation** ✅ **vérifié le 2026-07-13** : les quatre vues rendues de
bout en bout dans un navigateur sur un store peuplé (Timeline/DAG/Distribution/Run
sans erreur) ; le dashboard est un lecteur WAL concurrent, donc chaque mutation
écrite par la boucle apparaît au rafraîchissement suivant ; l'historique complet
d'un run est explorable sans notebook.

**Note dépendance** : `streamlit` requiert `websockets>=12`, or `gama-client`
épingle `websockets~=10.3`. Le venv du projet reste sur 10.3 (le contrôleur GAMA
prime) ; le serveur Streamlit fonctionne malgré tout (vérifié : HTTP 200 + rendu).

**Effort phase 2 : M (3-4 j).**

---

## 5 · Phase 3 — Loss v2 + acceptation statistique (D1, DA)

✅ **Phase 3 livrée le 2026-07-14** — loss v2 (`calibration/metrics.py`),
acceptation bootstrap (`calibration/stats.py`), backtest rétroactif
(`calibration/backtest.py` + `calibrate backtest`). 23 nouveaux tests verts
(`test_metrics_v2.py`, `test_stats.py`, `test_backtest.py`, +chemin bootstrap
dans `test_loop.py`).

- [x] Interface `Metric` : `compute(decisions_df, reference) -> Scores` ; la loss
      active est choisie dans `RunConfig.loss` (`get_metric`). `L1Composite`
      (historique) reste disponible pour comparaison ; `emd_jsd` (v2) est la
      nouvelle option.
- [x] `EMDOrdinal` (`emd_ordinal_dim`) : pour âge et distance — par mode, EMD du
      profil du mode le long de l'axe ordinal (`Σ_k |ΔCDF|`, `emd_1d`), normalisé
      par la longueur de l'axe et pondéré par l'effectif du mode.
- [x] `JSDNominal` (`jsd_nominal_dim`) : divergence de Jensen-Shannon (`jsd`, base 2,
      bornée) inter-modes au sein d'une strate (global/occupation/genre/motif).
- [x] Pondération continue par effectif (`Σ n·jsd / Σ n`) en remplacement du seuil
      binaire `min_count = 5` : une strate peu peuplée pèse moins au lieu d'être
      ignorée d'un coup.
- [x] **Backtest rétroactif** (`calibrate backtest --metrics l1_composite,emd_jsd`) :
      recalcule les losses sur tout l'historique du store depuis les décisions
      brutes (zéro appel LLM), écrit un CSV et un résumé (valeurs finales, minima,
      **corrélation de rang Spearman** L1 vs EMD/JSD). Vérifié sur le store réel
      (15 nœuds, Spearman 0.95).
- [x] **Test d'acceptation bootstrap (DA)** (`calibration/stats.py`,
      `accept_test: bootstrap`) : rééchantillonnage **apparié sur les agents**
      (B = 1000), IC à 90 % sur `Δcomposite` ; une mutation n'est acceptée que si
      `p_improve ≥ seuil`. Verdict `rejected_stat` distinct dans le store. Le recuit
      n'assouplit que le seuil de signification (`significance_threshold`, de 0.90 à
      froid à 0.55 à chaud), **jamais le signe** : une mutation qui dégrade le
      composite (`Δ ≥ 0`) n'est jamais acceptée.

**Critère d'acceptation** ✅ **vérifié le 2026-07-14** : le cas de test dédié
(`test_emd_ordinal_adjacent_less_severe_than_distant`) confirme que la loss ordinale
classe « moins grave » un décalage bus 15-19→20-24 qu'un décalage 15-19→50-54, là où
la loss nominale les traite à l'identique
(`test_l1_treats_adjacent_and_distant_equally`). L'acceptation bootstrap ne conserve
que les améliorations significatives (`rejected_stat` pour le bruit) → moins de
mutations acceptées-puis-régressives.

**Effort phase 3 : M (3-4 j).**

---

## 6 · Phase 4 — Rendement de la boucle (D3, D4, DD, DE)

✅ **Phase 4 livrée le 2026-07-14** — entonnoir de mutation (tabu → screening →
meilleur candidat), opérateurs riches + bandit UCB1, passes de compaction.
Modules : `calibration/tabu.py`, `calibration/bandit.py`, opérateurs dans
`calibration/mutation.py`, orchestration dans `calibration/loop.py`, jeu `screen`
dans `calibration/datasets.py`, non-infériorité dans `calibration/stats.py`.
26 nouveaux tests verts (`test_operators.py` ×12, `test_tabu.py` ×4,
`test_bandit.py` ×5, non-infériorité dans `test_stats.py` ×3, entonnoir +
compaction dans `test_loop.py` ×2). Au passage, comblé un manque de la phase 2 :
les helpers `seed_blocks_for` / `export_readable` / `import_legacy_run` de
`dashboard_data.py` (attendus par 4 tests jusque-là rouges) sont implémentés et
la **vue Maintenance** correspondante est câblée dans `dashboard.py`. **124 tests
verts au total.** Le chemin single-candidat (`n_candidates=1`) reproduit la
phase 3, ce qui garde les tests de reprise inchangés.

### 4.1 Tabu dur (D3)

- [x] À chaque proposition : embedding de la signature `(opérateur, target_block,
      new_content)` (`hash_embedding` — feature hashing local, aucune dépendance,
      **injectable**) ; similarité cosinus > `tabu_threshold` (0.9) avec une mutation
      rejetée **non expirée** → rejet immédiat (`rejected_tabu`), **zéro éval payée**.
      → `calibration/tabu.py` (`TabuArchive`), table `tabu` du store.
- [x] Tenure : `expires_after_accepted = accepted + tabu_tenure` (10) — l'entrée
      expire après N acceptations et redevient éligible.
- [x] La cause du rejet (`reject_cause`) est injectée dans l'historique fourni au
      mutateur (`_history_summary` : `✗ <cause>` sur les mutations rejetées).

### 4.2 Multi-candidats + entonnoir (DD)

- [x] Le mutateur produit **k candidats divers en un seul appel** (JSON array,
      `MutationGenerator.propose_candidates`, `n_candidates=4` par défaut) — un appel
      de mutation au lieu de k.
- [x] Entonnoir : filtre tabu (gratuit) → éval de **screening** sur le jeu `screen`
      (~20 % du train, gelé, sous-ensemble strict du train) → seul le meilleur
      candidat passe l'éval complète + le test bootstrap. → `loop._select_candidate`.
- [x] Les scores de screening sont enregistrés (`dataset='screen'`) et ne comptent
      jamais comme verdict final.

### 4.3 Opérateurs riches + bandit (DE)

- [x] Nouveaux opérateurs (purs, testés) : `reorder` (déplacer un bloc après un
      ancrage), `merge_blocks` (fusionner deux blocs), `condense` (réécrire plus
      court à sens constant), `split` (scinder un bloc fourre-tout).
      → `calibration/mutation.py` (`apply_mutation`).
- [x] Sélection de l'opérateur suggéré par **bandit UCB1** : bras = opérateurs,
      récompense = 1 si la mutation a été acceptée. Stats persistées par branche
      (table `bandit`, requêtable en SQL). → `calibration/bandit.py`. *(Une vue
      dashboard dédiée aux stats par opérateur reste à ajouter.)*

### 4.4 Groupement maximal des requêtes d'évaluation (D4 — reformulée)

L'éval des itinéraires est LE poste recalculé à chaque mutation → la minimiser :

- [x] `eval_batch_max` poussé à la **capacité réelle du provider** d'éval
      (`llm_config.get_batch_max_agents`, déjà en place depuis la phase 1 ; `0` →
      lecture à l'exécution).
- [x] Les évals (screening comme complètes) partagent le pool de threads
      (`eval_workers`) sous le budget RPM commun — chaque lot est indépendant.
- [ ] Ordonnancement du contenu pour maximiser le **prompt caching** provider —
      *reporté* (dépend du provider ; le préfixe système est déjà stable en tête).
- [ ] **Batch API** du provider pour les gros lots hors chemin critique
      (ablation/Shapley, backtests) — *reporté* (les backtests sont déjà zéro-LLM ;
      l'ablation reste sur le chemin d'éval standard avec cache).

### 4.5 Passes de compaction : minimiser le prompt à score constant (DM)

Le prompt calibré est envoyé à **chaque décision d'itinéraire en production** : chaque
mot économisé est payé des millions de fois. La `length_penalty` (0.05/mot) est une
incitation trop faible ; un mécanisme dédié la complète :

- [x] **Passe de compaction périodique** (toutes les `compact_every = 10` mutations
      acceptées + systématiquement en fin de campagne) : candidats = blocs de valeur
      d'ablation ≈ 0 (`|Δ| < compact_abl_tol`), triés du plus long au plus court.
      → `loop._compaction_pass`.
- [x] Pour chaque candidat : suppression tentée, puis **test de non-infériorité
      bootstrap** — le bloc est retiré si la borne haute de l'IC90 du Δ composite
      reste sous `compact_margin` (« réduire tant que ça ne dégrade pas le score »).
      → `stats.noninferiority_verdict`.
- [~] L'opérateur `condense` (réécriture plus courte) est disponible au mutateur et
      arbitré par le bandit ; la passe de compaction dédiée n'applique pour l'instant
      que la **suppression** sous non-infériorité (la condensation systématique des
      blocs verbeux est une extension légère à venir).
- [x] Les suppressions sont des mutations normales dans le store
      (`operator='compact_delete'`) : visibles au dashboard, réversibles par lignage.
- [x] Le **nombre de mots** du meilleur prompt est calculé et affiché en fin de run
      (`prompt_word_count`). *(La courbe « nb de mots » dédiée au dashboard reste à
      ajouter — les données sont dans le store.)*

**Effort phase 4 : M-L (5-6 j, compaction incluse).**

---

## 7 · Phase 5 — Attribution de crédit Shapley (DB — développée)

✅ **Phase 5 livrée le 2026-07-14** — `calibration/shapley.py` (Monte-Carlo tronqué,
pur et testé) + `run_shapley` dans `calibration/loop.py` (câblage cache + store),
sélectionnable par `RunConfig.shapley_*`. 10 nouveaux tests verts
(`test_shapley.py` : additivité, redondance, synergie, efficacité, troncature,
intégration Evaluator + cache, câblage `_update_ablation`). **134 tests verts au
total.** Le recalcul global d'ablation passe en Shapley (sur le jeu `screen`) toutes
les `shapley_every` acceptations ; l'ablation locale du bloc touché reste en LOO.
`shapley_enabled=False` reproduit le recalcul global LOO de la phase 1.

### Pourquoi remplacer l'ablation un-bloc-à-la-fois

L'ablation actuelle mesure `score(prompt − bloc_i) − score(prompt)` : elle suppose
les blocs **indépendants**. Deux cas réels la mettent en défaut :

- **Redondance** : deux blocs disent la même chose → retirer l'un ne change rien
  (l'autre compense), chacun paraît inutile, alors qu'en retirer *les deux* serait
  coûteux. L'ablation naïve conclut « supprimez les deux ».
- **Synergie** : un bloc « pense au vélo » n'agit que combiné au bloc « par beau
  temps » ; isolément chacun semble neutre.

### Principe

Chaque bloc = un **joueur** ; la « valeur » d'une coalition de blocs = le score du
prompt reconstruit avec ces blocs seulement. La **valeur de Shapley** d'un bloc est
sa contribution marginale moyenne sur tous les ordres d'ajout possibles — elle
répartit exactement le score total entre les blocs, redondances et synergies
comprises (c'est le cadre utilisé par HiveMind pour ses agents).

### Implémentation budgétée

- [x] **Échantillonnage par permutations** ✅ (`shapley_values`) : M permutations
      aléatoires (`shapley_permutations=25`) ; pour chacune, ajout des blocs un à un
      et mesure des marginaux (`v(coalition) − v(coalition ∪ {bloc})`, réduction de
      loss → **même signe que le delta d'ablation LOO**, positif = utile).
- [x] **Troncature** ✅ (TMC-Shapley) : dès que `|v_full − v_courant| <
      shapley_truncation_tol`, les blocs restants de la permutation ont un marginal
      ≈ 0 et **ne sont pas évalués**.
- [x] **Réutilisation du cache** ✅ : une coalition = un prompt = un nœud
      content-addressed ; `run_shapley` passe par l'`Evaluator` (cache store) + un
      mémo local par calcul → coalitions répétées gratuites (vérifié : 2ᵉ appel =
      zéro appel provider).
- [x] **Jeu de screening** ✅ : les évals Shapley tournent sur le jeu `screen`
      (`screen_dataset`, ~20 %) quand il est fourni ; repli sur `train` sinon.
- [x] **Fréquence** ✅ : remplace le recalcul global d'ablation dans
      `_update_ablation` — toutes les `shapley_every` (=5) acceptations. L'ablation
      locale rapide (1 bloc touché) **reste en leave-one-out** après chaque
      acceptation.
- [x] Stockage dans `ablations` avec `method='shapley'` ✅ (`build_shapley_results` →
      `record_ablation`) ; le contexte du mutateur (`format_ablation_for_mutation`),
      la passe de compaction et la carte du dashboard (colonne `method`) consomment
      indifféremment `loo` ou `shapley`.

**Ordre de grandeur du coût** : M=25 permutations × ~8 marginaux utiles (troncature)
sur 20 % des personas ≈ 40 évals-équivalent-train — comparable à une ablation
complète naïve (~25 blocs × 1 éval), pour une information bien plus juste.

**Effort phase 5 : M (3 j).**

---

## 8 · Phase 6 — Branches parallèles, merge, Pareto, bibliothèque (D7, DC, DL)

✅ **Phase 6 livrée le 2026-07-15** — archive de Pareto (`calibration/pareto.py`, pure),
îlots parallèles + migration en anneau + merge/crossover (`calibration/islands.py`,
`IslandRunner`), bibliothèque d'arguments (table `snippets` + capture/feed dans
`loop.py`), opérateur `crossover` (nœud à deux parents) et `propose_crossover` dans
`mutation.py`, vue **Pareto** du dashboard (`dashboard.py` + `dashboard_data.py`).
CLI : `calibrate run --islands k`. 29 nouveaux tests verts (`test_pareto.py` ×11,
`test_islands.py` ×6, `test_crossover.py` ×5, `test_snippets.py` ×5, Pareto/snippets
dans `test_dashboard_data.py` ×2). **163 tests verts au total.** Le chemin
mono-branche (`n_islands=1`) reproduit exactement les phases 1-5 → tests de reprise
inchangés. Le composite + bootstrap **reste le seul critère d'acceptation** dans
chaque branche ; le Pareto ne sert qu'aux départs d'îlots et aux parents de merge.

### 8.1 Le front de Pareto, expliqué (DC — « pas compris »)

Aujourd'hui, 6 dimensions sont écrasées en **un seul chiffre** (le composite) via des
poids arbitraires (0.5, 0.3…). Conséquence : un prompt excellent sur `âge` mais moyen
sur `motif` et un prompt inverse peuvent avoir **le même composite** — et on en jette
un, alors qu'ils contiennent des acquis complémentaires.

**Dominance** : un prompt A *domine* B si A est au moins aussi bon que B sur toutes
les dimensions ET strictement meilleur sur au moins une. Si A est meilleur sur `âge`
mais moins bon sur `motif`, aucun ne domine l'autre : les deux sont des compromis
légitimes.

**Front de Pareto** = l'ensemble des prompts non dominés. Exemple à 2 dimensions :

```
motif ↑ (mieux)      × B (motif fort, âge faible)
                  × C (équilibré)          ← A, B, C = front de Pareto
                          × A (âge fort)
        ° D (dominé par C : moins bon partout) → éliminé
                              âge → (mieux)
```

**Usage retenu (léger)** : le composite + bootstrap **reste le critère
d'acceptation** dans chaque branche (simple, un seul chiffre à suivre). En parallèle,
le store maintient l'**archive des nœuds non dominés** toutes branches confondues.
Elle sert à :
1. choisir des **points de départ diversifiés** pour les branches (au lieu de cloner
   k fois le même champion) — c'est le mécanisme central de GEPA ;
2. fournir des **parents complémentaires** aux merges (un fort en `âge` × un fort en
   `motif`) ;
3. rendre le veto collatéral moins critique : une mutation qui sacrifie une dimension
   pour une autre reste archivée si elle est non dominée, au lieu d'être perdue.

### 8.2 Îlots (D7)

- [x] `calibrate run --islands 3` : k branches évoluent en parallèle dans le même
      store (colonne `branch`), chacune avec sa boucle, initialisées depuis des
      points diversifiés de l'archive Pareto (`diversified_seeds`, farthest-point)
      ou le seed au premier run. → `IslandRunner` (`calibration/islands.py`).
- [x] Rotation : l'ordonnanceur fait avancer les îlots à tour de rôle par rondes de
      `migrate_every` itérations sous le budget RPM partagé (k× la durée). N° de
      ronde snapshoté (clé `__islands__`) → reprise exacte à la ronde suivante.
- [x] **Migration** : toutes les `migrate_every` itérations, le meilleur nœud d'un
      îlot est proposé (pas imposé) à l'îlot suivant en anneau (`operator='migrate'`,
      adopté seulement s'il améliore la destination). **Idempotente** à la reprise.

### 8.3 Merge (crossover)

- [x] Opérateur `crossover` : deux parents (choisis dans l'archive Pareto pour leur
      complémentarité, `complementary_pair`) → le modèle de mutation fusionne le corps,
      informé des valeurs ablation/Shapley des blocs de chaque parent
      (`propose_crossover`, système dédié `_CROSSOVER_SYSTEM`).
- [x] Le merge produit un nœud à **deux parents** (colonne `parent2`), évalué comme
      n'importe quel candidat — aucun merge n'est accepté sans éval (adopté seulement
      s'il améliore le composite de l'îlot cible).
- [~] La fréquence du crossover est pilotée par `crossover_every` (rondes de
      migration), pas encore arbitrée par le bandit UCB comme un opérateur par
      itération (le crossover exige deux parents Pareto, hors du chemin single-parent
      du bandit) — extension à venir.

### 8.4 Bibliothèque d'arguments comportementaux (DL)

- [x] Table `snippets` : chaque bloc inséré/réécrit **accepté avec gain composite ≥
      `snippet_min_gain`** y entre, taggé (mode ciblé = mode le plus sous-représenté,
      gain observé, nœud d'origine, branche). → `store.record_snippet`,
      `loop._capture_snippet`.
- [x] Le mutateur reçoit les meilleurs snippets pour le levier du moment (mode
      sous-représenté, repli global) comme matériau de réécriture
      (`format_snippets_for_mutation`, `loop._top_snippets`) — les îlots se
      fertilisent même sans merge.
- [x] Bonus : la banque est persistée dans le store → une campagne future
      (même store) démarre avec elle ; l'export réutilisable inter-campagnes est
      une extension légère (copier la table `snippets`).

**Critère d'acceptation phase 6** : sur une campagne de 50 itérations-équivalent,
le meilleur score test (éval unique finale) des 3 îlots + merges bat la boucle
mono-branche à budget d'éval égal.

**Effort phase 6 : L (5-7 j).**

---

## 9 · Phase 7 — Consolidation

✅ **Outillage phase 7 livré le 2026-07-15** — `calibration/publish.py` +
`calibrate finalize` : éval **test unique** du meilleur prompt (toutes branches,
`store.best_overall`) + du seed, bilan chiffré avant/après (`campaign_report`,
`build_comparison` : composite par jeu, détail test par dimension, nb de mots, évals
consommées, durée) et **publication** dans `prompts.yaml` (`publish_prompt`, clé
`calibrated_{horodatage}`, `--write`/`--activate`, dry-run par défaut). 8 nouveaux
tests verts (`test_publish.py`). **171 tests verts au total.** Les évals test passent
par le cache → finalisation idempotente.

- [x] **Outillage** de la campagne de validation : seed → éval test unique →
      publication `prompts.yaml`, avec comparaison chiffrée avant/après (score par
      jeu, détail par dimension, nb d'évals consommées, durée). → `calibrate finalize`.
- [~] **Exécution** de la campagne de validation complète (seed → 50 itér → test) :
      opérationnelle, à lancer par l'utilisateur avec des clés provider (heures de
      run, quota LLM) — l'outillage est prêt, le chiffre publiable en sort en une
      commande.
- [x] Mise à jour de `docs/arch/prompt_calibration.md` (§2.6 îlots/Pareto, §2.7
      finalisation) + `docs/changelog.md` + README package.
- [~] Spike **GEPA** ([github.com/gepa-ai/gepa](https://github.com/gepa-ai/gepa)) :
      était prévu *avant* la phase 6 ; la phase 6 ayant été codée nativement (îlots +
      Pareto + merge réflexif + bibliothèque), le spike devient une évaluation
      *a posteriori* optionnelle (déléguer à la lib plutôt que maintenir le code) —
      non bloquant, à ouvrir en ticket dédié si le besoin se confirme.

**Pistes optionnelles, volontairement non planifiées** (issues de la littérature —
à ouvrir en tickets dédiés si le besoin se confirme après la phase 6) :
- étage final d'optimisation **globale** du prompt une fois les blocs stabilisés
  (MASS) — réécriture d'ensemble soumise à l'entonnoir complet ;
- tandem proposeur + **critique** en amont de l'éval (MARS) — utile seulement si le
  taux de mutations invalides/rejetées reste élevé malgré tabu + entonnoir.

---

## 10 · Ordre, dépendances, estimation globale

```
Phase 0  Mesure fiable          ██        (2-3 j)   ← rien ne sert d'optimiser avant
Phase 1  Package + store        ████      (4-6 j)   ← fondation de tout
Phase 2  Dashboard              ███       (3-4 j)   ← dès que le store existe, aide au debug de la suite
Phase 3  Loss v2 + bootstrap    ███       (3-4 j)   ← backtest rétroactif grâce au store
Phase 4  Rendement + compaction ████      (5-6 j)
Phase 5  Shapley                ███       (3 j)
Phase 6  Îlots + merge + Pareto █████     (5-7 j)   ← spike GEPA avant
Phase 7  Consolidation          ██        (2 j)
                                          ≈ 27-35 j
```

Dépendances dures : 1→{2,3,4,5,6} ; 0→3 (la loss v2 a besoin des vraies
métadonnées) ; 4.2 (screening)→5 et →6 (Shapley et îlots consomment l'entonnoir).
Les phases 2 et 3 sont permutables ; 4 et 5 aussi.
