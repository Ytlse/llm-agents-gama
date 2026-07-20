  # Calibration de prompt — `prompt_calibration`

Documentation du module de calibration automatique du prompt système `itinary_multi_agent`,
qui optimise le texte du prompt pour rapprocher la distribution des choix modaux produits
par le LLM de la référence **EMC² 2023 Toulouse** (`scripts/data/population/cerema_values.yaml`).

**Fichiers :**

| Fichier | Rôle |
|---|---|
| `scripts/prompt_calibration/` | **Nouvelle version** (ticket 004, décision DN) — phases 0-7 livrées : package `calibration/` (models, blocks, metrics, stats, backtest, evaluation, mutation, loop, store, cli, export, importer, dashboard, tabu, bandit, shapley, pareto, islands, **publish**) + tests |
| `scripts/prompt_calibration/calibration/store.py` | Store SQLite : DAG content-addressed (nœuds/mutations/évals/ablations) — la fondation reprenable |
| `calibration_results/calibration.db` | Store d'une campagne (nouvelle version) |
| `scripts/models_influence/prompt_calibration.ipynb` | Ancienne version (conservée intacte) : orchestration + visualisation |
| `scripts/models_influence/prompt_calibration_lib.py` | Ancienne version (conservée intacte) : moteur |
| `scripts/models_influence/calibration_results/` | Cache d'éval, journal des mutations, checkpoint (ancienne version) |
| `experiments/current/llm_exchanges.jsonl` | Source des requêtes réelles (catégorie `itinary_multi_agent`) |
| `llm_module/prompts/prompts.yaml` | Prompt de départ et prompt calibré publié |

> Le plan d'industrialisation détaillé est dans
> `docs/tickets/ticket_004_prompt_calibration_industrialisation.md`.

---

## 1 · Vue d'ensemble du pipeline

```
llm_exchanges.jsonl ──► échantillonnage (seed fixe) ──► split train / val
        │                                                    │
        ▼                                                    ▼
métadonnées persona                                  micro-batches (≤ EVAL_BATCH_MAX
(âge, occupation, genre, motif, distance)             personas / requête LLM)
        │                                                    │
        ▼                                                    ▼
prompt seed ──► décomposition en BLOCS (1 phrase = 1 bloc, schéma JSON verrouillé)
        │
        ▼
run initial + ATTRIBUTION SHAPLEY (contribution de chaque bloc au score)
        │
        ▼
BOUCLE (recuit simulé, ≤ 50 itérations) — entonnoir phase 4 :
   bandit UCB choisit l'opérateur suggéré
   ──► mutation LLM (Gemini) : k candidats en 1 appel
   ──► filtre TABU (rejet des quasi-doublons de mutations rejetées, gratuit)
   ──► SCREENING (~20 % du train) : on garde le meilleur candidat
   ──► application ──► éval train (Mistral) ──► score composite
   ──► veto collatéral ──► accepter / rejeter (bootstrap) ──► récompense bandit
   ──► rejet → entrée tabu (tenure)
   ──► à CHAQUE acceptation : attribution de crédit Shapley globale (jeu screen)
   ──► toutes les 5 itérations : éval validation + early stopping
   ──► toutes les COMPACT_EVERY acceptations (+ fin de run) : passe de COMPACTION
        │
        ▼
checkpoint best_checkpoint.yaml ──► publication dans prompts.yaml + diff git-like
```

### Rôles des modèles (décision d'architecture)

- **Un seul modèle d'évaluation** (`google_gemini31` / `gemini-3.1-flash-lite-preview`,
  température minimale), pour le train, la validation et le test. *Pourquoi :* une
  calibration est spécifique à un modèle donné — changer de modèle d'évaluation invalide
  le prompt calibré et demande une recalibration (en repartant du prompt calibré d'un
  modèle proche). La version du modèle doit être **épinglée** (pas d'alias `-latest`).
- **Un modèle distinct pour les mutations** (`gemini-3.1-flash-lite-preview`),
  afin de ne pas consommer le quota de tokens du modèle d'évaluation, qui est la
  ressource rare de la boucle. ⚠ Depuis le passage de l'éval sur Gemini
  (2026-07-17), éval et mutation partagent le même modèle Gemini, donc le même
  quota provider ; basculer la mutation sur un autre modèle (ex. `google_gemma42`)
  rétablit la séparation des quotas si celui-ci devient contraignant.

---

## 2 · Méthodes de calcul

### 2.1 Score composite actuel (L1 pondéré)

Pour chaque dimension, l'erreur est la **distance L1 en points de %** entre la
distribution des modes produite par le LLM et la référence EMC² normalisée
(modes exclus : `autres_modes`) :

```
L1(dim) = moyenne sur les catégories cat de la dimension, avec n(cat) ≥ 5 :
          Σ_modes | part_LLM(mode | cat) − part_EMC²(mode | cat) |   (en pts de %)
```

Le composite agrège les dimensions avec des poids fixes :

| Terme | Poids | Rôle |
|---|---|---|
| `global` | 1.0 | Distribution modale toutes strates confondues |
| `absent_penalty` | 1.0 | 5 × part EMC² de chaque mode jamais choisi (mode « oublié ») |
| `age` | 0.5 | L1 moyenne par tranche d'âge |
| `occupation` | 0.5 | L1 moyenne par occupation |
| `genre` | 0.3 | L1 moyenne Homme / Femme |
| `motif` | 0.5 | L1 moyenne travail / études / achats |
| `distance` | 0.3 | L1 moyenne par bucket de distance |
| `length_penalty` | 1.0 | `0.05 × nb de mots` du prompt (incitation à la concision) |

**Minimisation du prompt (cible)** : la `length_penalty` est une incitation faible ;
le mécanisme principal d'économie de tokens est la **passe de compaction** (ticket 004
§4.5) — suppression des blocs de contribution ≈ nulle et condensation des blocs
verbeux, acceptées sous test de non-infériorité (le score ne doit pas se dégrader
significativement). Le prompt calibré étant envoyé à chaque décision d'itinéraire en
production, chaque mot compte.

**Garde-fous de la boucle** (en plus du score) :

- **Veto collatéral** : mutation refusée si une dimension non-globale se dégrade de
  plus de `COLLATERAL_TOL` points, même si le composite s'améliore.
- **Recuit simulé** : une mutation légèrement dégradante peut être acceptée tant que
  la température `T = T0 · αⁱ` est élevée (exploration en début de run).
- **Attribution Shapley** : contribution moyenne d'un bloc au score, mesurée sur
  toutes les coalitions (cf. §2.5) ; `φ > +2` = bloc utile, `φ < −2` = bloc nuisible.
- **Pires croisements strate × mode** : classés par `impact = |écart| × effectif`,
  fournis au mutateur pour cibler la strate et le mode les plus mal prédits.

### 2.2 Loss v2 : EMD (ordinal) + JSD (nominal) — **implémentée** (phase 3)

La L1 traite toutes les catégories comme interchangeables : déplacer la préférence
bus des 15-19 ans vers les 20-24 ans coûte autant que la déplacer vers les 50-54 ans.
Les dimensions **ordinales** (âge, distance) doivent utiliser une métrique qui
respecte l'ordre des catégories.

**État (2026-07-14)** : la loss `emd_jsd` est livrée (`calibration/metrics.py`) et
sélectionnable par `RunConfig.loss` (`get_metric`) ; `l1_composite` reste
disponible pour comparaison. Composition :

| Dimension | Métrique | Fonction |
|---|---|---|
| `age`, `distance` (ordinales) | EMD du profil de chaque mode le long de l'axe (`Σ_k |ΔCDF|`, ×100/longueur d'axe, pondéré par effectif du mode) | `emd_ordinal_dim` / `emd_1d` |
| `global`, `occupation`, `genre`, `motif` (nominales) | JSD inter-modes (base 2, bornée), **pondérée en continu par effectif** (plus de seuil `n ≥ 5`) | `jsd_nominal_dim` / `jsd` |
| `absent_penalty`, `length_penalty` | identiques à la L1 | — |

Le composite réutilise les poids de dimension de la L1 (mêmes rôles) ; les échelles
JSD/EMD sont ramenées en ×100 pour rester du même ordre de grandeur que les points
de %. Le store conservant les décisions brutes, cette loss est **backtestable**
rétroactivement sur tout l'historique (`calibrate backtest`, zéro appel LLM).

| Métrique | Type de dimension | Principe | Usage cible |
|---|---|---|---|
| **EMD / Wasserstein-1** | ordinale | Coût de transport de la masse de probabilité entre bins ; sur catégories ordonnées : `Σ_k | CDF_LLM(k) − CDF_ref(k) |` | Profil de chaque mode le long de l'axe âge et de l'axe distance |
| **RPS** (Ranked Probability Score) | ordinale | `Σ_k ( CDF_LLM(k) − CDF_ref(k) )²` — variante quadratique de l'EMD, proper scoring rule classique en prévision météo | Alternative/complément à l'EMD |
| **Jensen-Shannon (JSD)** | nominale | Divergence symétrique et bornée `½ KL(P‖M) + ½ KL(Q‖M)` avec `M = ½(P+Q)` | Distribution inter-modes au sein d'une strate (les modes n'ont pas d'ordre) |
| **Log-vraisemblance multinomiale / G-test** | toutes | `2 Σ n·p_LLM · ln(p_LLM / p_ref)` — intègre naturellement l'effectif de la strate | Pondération continue par effectif (remplace le seuil binaire `n ≥ 5`) |

**Loss hiérarchique cible** : pour chaque strate, JSD (ou L1) inter-modes pondérée par
le poids population de la strate ; **plus**, pour chaque mode, EMD de son profil le
long de chaque axe ordinal (ex. « qui prend le bus, par tranche d'âge » vs EMC²).
Les métriques sont **pluggables** (interface commune) pour pouvoir comparer plusieurs
losses sur un même historique — le store conserve les décisions brutes, tout score
est recalculable rétroactivement.

*Écarté (DTW)* : le Dynamic Time Warping est conçu pour l'alignement élastique de
séries temporelles ; l'analogue correct pour des distributions catégorielles
ordonnées est l'EMD.

### 2.3 Acceptation statistique — **implémentée** (phase 3)

Une amélioration du composite inférieure au bruit d'échantillonnage ne doit pas être
acceptée. Test livré (`calibration/stats.py`, activé par `accept_test: bootstrap`) :
**bootstrap apparié sur les agents** (`bootstrap_delta`, B = 1000) — on rééchantillonne
les agents avec remise, on recalcule le `Δcomposite` (prompt muté − prompt courant) sur
chaque tirage des **mêmes** agents des deux côtés, d'où un IC à 90 % sur l'amélioration.
Une mutation n'est conservée que si `p_improve ≥ seuil`.

Le recuit (`significance_threshold`) n'assouplit que le **seuil de signification** — de
0.90 à froid (IC 90 %) à 0.55 à chaud (exploration) — **jamais le signe** : une mutation
qui dégrade le composite (`Δ ≥ 0`) est toujours rejetée (`rejected_score`), une
amélioration non significative est rejetée `rejected_stat`, ce qui la distingue dans le
store et nourrit le mutateur. La température d'évaluation minimale réduit la variance de
sampling du LLM ; le bootstrap couvre le bruit résiduel dû à la taille finie de
l'échantillon de personas. Le rééchantillonnage porte sur les décisions brutes déjà
stockées → aucun appel LLM. Le recuit simple (`accept_test: sa`, phase 1) reste
disponible.

### 2.4 Rendement de la boucle : entonnoir, tabu, bandit, compaction — **implémenté** (phase 4)

Le poste coûteux est l'**éval des itinéraires**, recalculée à chaque mutation. La
phase 4 maximise l'information par éval payée via un **entonnoir** (`calibration/
loop.py`, `tabu.py`, `bandit.py`) :

1. **Bandit UCB1 (DE)** — chaque **opérateur** (`modify / delete / insert / reorder /
   merge_blocks / condense / split`) est un bras ; récompense = 1 si la mutation
   proposée avec cet opérateur a été acceptée. À chaque tour on suggère au mutateur
   le bras UCB1 (`moyenne + c·√(ln N / nᵢ)`, bras neufs prioritaires). Stats
   persistées par branche (table `bandit`, requêtables en SQL ; vue dashboard
   dédiée à venir).
2. **Multi-candidats (DD)** — le mutateur produit **k candidats en un seul appel**
   (`propose_candidates`, JSON array) au lieu de k appels.
3. **Filtre tabu dur (D3)** — signature `(opérateur, bloc, contenu)` de chaque
   candidat → **embedding local** (feature hashing de n-grammes, `hash_embedding`,
   aucune dépendance, injectable). Similarité cosinus > `tabu_threshold` avec une
   mutation **rejetée non expirée** → rejet immédiat (`rejected_tabu`), **zéro éval
   payée**. **Tenure** : une entrée expire après `tabu_tenure` acceptations
   (`expires_after_accepted = accepted + tenure`) — la retentative redevient
   légitime quand le contexte a changé. La cause du rejet (`reject_cause`) est
   réinjectée dans l'historique fourni au mutateur.
4. **Screening (DD)** — les candidats survivants sont évalués sur le jeu **`screen`**
   (~20 % du train, gelé, sous-ensemble strict du train → cache partagé) ;
   seul le meilleur composite passe l'**éval complète + le test bootstrap**. Les
   scores de screening sont stockés (`dataset='screen'`) mais ne comptent jamais
   comme verdict final.
5. **Passe de compaction (DM)** — toutes les `compact_every` acceptations (+ en fin
   de campagne), les blocs de contribution ≈ nulle (`|Δ ablation| < compact_abl_tol`,
   du plus long au plus court) sont retirés (`operator='compact_delete'`) sous test
   de **non-infériorité bootstrap** : on retire si la borne haute de l'IC90 du Δ
   composite reste sous `compact_margin` — « réduire tant que ça ne dégrade pas le
   score ». Le prompt calibré étant envoyé à chaque décision en production, chaque
   mot compte ; le nombre de mots du meilleur prompt est suivi en fin de run.

Tout reste dans le store (mutations `rejected_tabu` / `compact_delete`, table
`bandit`) : visible au dashboard, réversible par lignage, **reprenable**
(l'entonnoir ne s'exécute que pour les itérations non encore jouées). Le chemin
**single-candidat** (`n_candidates=1`) reproduit exactement le comportement phase 3.

#### 2.4.2 Réflexion sur les rejets : mémoire de leçons — **implémentée**

Les causes de rejet (`reject_cause`) étaient déjà réinjectées brutes dans l'historique
fourni au mutateur, mais restaient opaques (`Δ=+0.30@n=25`, `motif +12`, `cos=0.93`) : le
mutateur les voyait sans les généraliser, d'où la tendance à re-cibler le même bloc tant
que le levier dominant ne bougeait pas. Deux mécanismes y remédient (activés par défaut,
`reflection_enabled`, désactivables pour A/B) :

1. **Étiquetage fond vs bruit** — chaque rejet de l'historique est annoté de sa **catégorie**
   (`reject_kind` dans `mutation.py`, dérivée du `verdict` désormais persisté dans l'historique) :
   - `[fond]` (`vetoed`, `invalid`, `rejected_dup_block`, `rejected_gate`) → une **vraie leçon**
     existe (une dimension protégée régresse, mutation inapplicable, cible déjà couverte, strate
     visée non améliorée) : ne pas y retourner à l'identique ;
   - `[bruit]`/`[seuil]`/`[doublon]` (`rejected_stat`, `rejected_race`, `rejected_score`,
     `rejected_tabu`) → l'idée **n'est pas invalidée sur le fond** : garder le **levier**, mais
     **ne jamais resoumettre le même texte ni une variante triviale** (même verdict, essai
     gaspillé) — la proposition concrète doit **différer matériellement** (renforcer l'argument,
     changer de bloc-cible, combiner), **sans inventer** de leçon de fond.

3. **Garde-fou dur anti-resoumission (toute config)** — la règle « ne resoumets jamais le même
   texte ni une variante triviale » n'est pas qu'une consigne : elle est **appliquée en code** dans
   **les deux chemins**. Sur l'entonnoir (`n_candidates > 1`), le filtre tabu de `_select_candidate`
   l'assurait déjà. Sur le chemin **single-candidat (défaut)**, `_single_prescreen` (`loop.py`) écarte
   désormais **avant toute éval** : (a) une proposition qui ne change rien (prompt muté = prompt
   courant → `invalid`) ; (b) un quasi-doublon d'un rejet non expiré (`rejected_tabu`, similarité
   cosinus ≥ `tabu_threshold`). Symétriquement, **tout rejet** (`_TABU_ON_REJECT` : `rejected_score`,
   `rejected_stat`, `rejected_race`, `vetoed`) **entre au tabu quelle que soit la config** — sa
   ré-soumission triviale sera bloquée jusqu'à expiration de la **tenure** (`tabu_tenure`
   acceptations : le contexte a changé, la retentative redevient légitime). Master switch :
   `tabu_enabled` (défaut `True` → garde-fou actif dans toutes les configs par défaut). Même tabu
   désactivé, une resoumission **exacte** ne coûte aucun appel LLM (nœud content-addressed → éval
   servie par le cache).

   C'est le garde-fou clé : sans lui, le mutateur rationalise un rejet purement statistique
   (« renforcer le vélo ne marche pas ») là où le bootstrap n'a constaté qu'une non-significativité,
   et abandonne à tort des pistes correctes.

2. **Mémoire de leçons roulante** — à chaque tour, le mutateur renseigne un champ `reflection`
   (2-3 phrases) synthétisant les raisons **récurrentes** de rejet + ce qu'il change en
   conséquence. Cette synthèse est **absorbée** dans `state["lessons"]` (`_absorb_reflection`
   dans `loop.py`), **bornée** à `lessons_max_chars` (anti-ancrage), **persistée** dans
   `run_state` (reprise gratuite) et **réinjectée** au tour suivant (`format_lessons` →
   `build_mutation_user_msg`). La synthèse est produite dans le **même appel** que la proposition
   (coût quasi nul, pas d'appel LLM dédié) ; sur le chemin entonnoir, elle est commune aux
   candidats et suit celui qui est retenu. Au rejeu depuis le store (reprise), la mutation
   reconstruite n'a pas de champ `reflection` → l'absorption est un no-op (aucune leçon fantôme).

#### 2.4.3 Contexte concret pour le mutateur : hard negatives & snippets entiers — **implémenté**

Le mutateur raisonnait uniquement sur des **agrégats** (distributions, écarts, contributions) ;
trois évolutions lui donnent du **concret**, sans aucun appel LLM supplémentaire (données déjà
persistées, uniquement du calcul et du formatage) :

1. **Hard negatives** (`format_hard_negatives`, `hard_negatives_k`, défaut 4, 0 → désactivé) —
   pour les pires croisements strate × mode **sur-représentés**, le contexte montre jusqu'à `k`
   décisions **individuelles réelles** du prompt courant (persona → mode choisi), ex.
   `Femme, 30 ans, actif_temps_plein, travail, 1-2km → voiture (genre[Femme] : +70 pts vs cible)`.
   Le mutateur voit à quoi ressemble une erreur type et corrige le schéma comportemental de
   manière ciblée. Sélection **déterministe** (ordre du df) → reprenable sans variance.

2. **Snippets fournis en entier** (`SNIPPET_MAX_CHARS` = 300, cap de sécurité) — la bibliothèque
   d'arguments (DL) est un *matériau de réécriture* : tronquée à 110 caractères comme avant, elle
   forçait le mutateur à halluciner la fin des arguments. Le contenu est désormais fourni en
   entier (ellipse seulement au-delà du cap).

3. **Matrice bloc × mode** — colonne « modes poussés » de la table de contribution
   (cf. §2.5, décomposition Shapley par part modale) : quel mode chaque bloc favorise ou freine.

#### 2.4.0 Paliers progressifs sur un essai unique — **défaut actuel** (`n_candidates=1`)

Le mode par défaut évalue **un seul essai par itération** (pas de parallélisation de
candidats). Cet essai est filtré par **arrêt précoce** le long des paliers `racing_rungs`
(défaut `[0.25, 0.50, 0.75]`) : à chaque palier `f`, le composite de l'essai est comparé
à celui du **prompt courant** (`sa_node`) sur **le même sous-échantillon** (`train[:f·N]`).
Dès qu'un palier n'apporte **aucune amélioration** (`Δ = essai − courant ≥ 0`), l'essai
est **abandonné** (`rejected_race`, `_rung_gate` dans `loop.py`), sans jamais payer l'éval
complète ni les paliers suivants ; s'il franchit les trois paliers, la boucle enchaîne
l'éval complète (`train`) puis le test bootstrap habituel. Les évals partielles ont leur
propre label (`race:{f}`, distinct de `train`) et passent par le cache content-addressed :
le baseline `sa_node` est mis en cache et réutilisé tant qu'aucune mutation n'est acceptée.
`racing_enabled=False` retire les paliers (éval complète directe, comportement phase 3).

#### 2.4.1 Racing ciblé par strate (successive halving) — **implémenté** (phase 4.6, multi-candidats)

Quand plusieurs candidats sont proposés (`n_candidates > 1`), le **screening one-shot**
laisse une **unique mesure bruitée** décider du gagnant, et juge sur le composite
**global** : un candidat qui corrige justement une strate en échec (ex.
`genre[femme] × marche` sous-représenté) n'est pas favorisé. `racing_enabled=True`
(`RunConfig`, défaut) remplace alors le bloc « screening » de `_select_candidate` par un
**racing multi-tours** précédé d'un **gate de strate** (`_race_candidates`). *(Avec le
défaut `n_candidates=1`, c'est le mode « essai unique + paliers » du §2.4.0 qui
s'applique ; `_race_candidates` n'est appelé qu'à partir de deux survivants.)*

1. **Gate strate (tour 0)** — périodique (`i % racing_target_every == 0`, si
   `racing_target_gate`). La pire strate est `metrics.worst_strata_modes(sa_df)[0]`
   (`dim, cat`) ; les candidats sont évalués **uniquement** sur les agents de cette
   strate (`_stratum_records`, label de dataset dédié `gate:{dim}:{cat}`) et ceux qui
   **n'améliorent pas son écart L1** (`_stratum_gap`) sont éliminés (`rejected_gate`).
   Auto-arrêt bon marché. **Garde-fous** : strate trop petite (`< racing_min_n`) →
   gate sauté ; le gate **vide la liste** → **repli global** (tous repassent en racing,
   aucun `rejected_gate` — l'itération n'est jamais bloquée).
2. **Racing (successive halving)** — pour chaque fraction croissante de `racing_rungs`
   (ex. `[0.15, 0.35, 0.70, 1.0]`), les survivants sont évalués sur les `f·|train|`
   premiers records ; on garde la meilleure moitié (`racing_keep_frac`). Le jeu partiel
   a son propre label (`race:{f}`), et **seule** la fraction complète (`f≥1.0`) réutilise
   le label `train` — l'éval complète du gagnant est ainsi **servie par le cache** quand
   la boucle la refait. **Garde-fou statistique** : on ne départage jamais deux candidats
   à moins de `racing_min_gap` de composite, ni dont l'**IC bootstrap** du Δ chevauche 0
   (`stats.bootstrap_delta`) — sinon `rejected_race`.

Le racing est une **approximation assumée** (on classe sur des sous-échantillons
bruités → on peut éliminer un candidat qui aurait gagné sur le train complet), d'où le
garde-fou statistique obligatoire ; le gate change l'**objectif local** (attaquer la
pire strate) au risque de ralentir la baisse du composite global, d'où son caractère
**périodique** et le repli global. Les verdicts `rejected_gate` / `rejected_race` sont
persistés comme les autres (colorés au dashboard) pour le diagnostic. `racing_enabled=False`
→ **screening one-shot strictement inchangé** (multi-candidats) / éval complète directe
(essai unique).

| Paramètre `RunConfig` | Défaut | Rôle |
|---|---|---|
| `racing_enabled` | `True` | Active les paliers (essai unique) / le racing (multi-candidats) |
| `racing_rungs` | `[0.25, 0.50, 0.75]` | Fractions croissantes du train (paliers d'arrêt précoce) |
| `racing_keep_frac` | `0.5` | (multi-candidats) part conservée à chaque palier (≥ 1 candidat) |
| `racing_target_gate` | `True` | Tour 0 = gate sur la pire strate |
| `racing_target_every` | `2` | 1 itération sur N en mode ciblé |
| `racing_min_gap` | `1.0` | Écart composite mini pour départager |
| `racing_min_n` | `8` | Taille mini de la strate cible (sinon gate sauté) |

### 2.5 Attribution de crédit Shapley — **implémentée** (phase 5, DB)

Mesurer `score(prompt − bloc_i) − score(prompt)` (retrait bloc-à-bloc) suppose les
blocs **indépendants** et se trompe dans deux cas : **redondance** (deux blocs
équivalents paraissent chacun inutile pris isolément alors qu'en retirer les deux
coûte) et **synergie** (le retrait depuis le prompt complet attribue *toute* la
synergie à *chaque* bloc → la somme dépasse le gain réel). La **valeur de Shapley**
répartit exactement le gain total entre les blocs, redondances et synergies
comprises.

**Implémentation** (`calibration/shapley.py`, pure et testée ; câblage
`run_shapley` dans `loop.py`) :

- **Joueurs** = blocs mutables ; valeur d'une coalition = loss (composite) du
  prompt reconstruit avec ces blocs (les blocs verrouillés, `json_schema`, sont
  toujours présents, dans l'ordre du prompt — **quel que soit l'ordre d'ajout de
  la permutation**). `φ_bloc` = moyenne des `v(coalition) − v(coalition ∪ {bloc})`
  = **réduction de loss** apportée par le bloc (positif = utile).
- **Monte-Carlo tronqué** (TMC-Shapley, Ghorbani & Zou 2019) : `shapley_permutations`
  (=25) permutations aléatoires ; dans chacune, dès que
  `|v_full − v_courant| < shapley_truncation_tol`, les blocs restants ont un
  marginal ≈ 0 et **ne sont pas évalués**.
- **Cache** : une coalition = un prompt = un nœud content-addressed → les évals
  passent par le cache du store (et un mémo local par calcul) ; les coalitions
  répétées (entre permutations, entre runs) sont gratuites.
- **Échantillonnage cumulatif à graine fixe (2026-07-20)** — deux régimes selon
  `shapley_addon_per_accept` :
  - **historique** (`0`, défaut du code) : ré-échantillonnage complet à chaque
    recalcul (graine = nb d'acceptations), M constant — estimation renouvelée,
    mais peu de cache hits après mutation (les permutations changent) ;
  - **cumulatif** (`> 0`, activé dans `run.yaml`/`cloud.yaml`) : **graine fixe**
    → le socle de `shapley_permutations` permutations est rejoué à l'identique à
    chaque passe. Les permutations sont **stables par préfixe** (un RNG séquentiel,
    un `shuffle` par tour) : après un `modify`, toute coalition sans le bloc muté
    a le même texte → **cache hit, zéro token** ; on ne paie que les coalitions
    contenant du contenu nouveau (+ la frange de troncature mobile). S'y ajoutent
    `addon × acceptations` permutations fraîches, plafonnées à
    `shapley_max_permutations` — la précision de φ croît au fil de la campagne
    (common random numbers : les Δφ entre prompts successifs sont appariés, donc
    peu bruités), pour un coût par passe borné. Le **plafond est modifiable en
    cours de campagne** (relu du YAML à chaque reprise ; hausse = extension de la
    séquence, baisse = préfixe — jamais d'invalidation de cache). Rien n'est
    persisté : le plan `(m, graine)` est recalculé de `(config, accepted)` à
    chaque passe (`planned_permutations`, pure et testée).
- **Jeu de screening** : les évals Shapley tournent sur le jeu `screen` (~20 %),
  pas sur le train complet (repli sur `train` si aucun jeu de screening).
- **Fréquence** : recalcul **global** de tous les blocs dans `_update_ablation`
  après **chaque** acceptation (et à l'init). Le cache amortit le coût : les
  coalitions déjà évaluées ne rappellent pas le LLM.
- **Stockage** : `ablations` avec `method='shapley'` ; le contexte du mutateur, la
  passe de compaction et la carte du dashboard (colonne `method`) consomment la
  méthode `shapley`.
- **Décomposition par dimension (2026-07-15)** : le composite étant **linéaire**
  dans les dimensions, `φ_composite = Σ_d w_d·φ_d` exactement — les mêmes évals de
  coalitions donnent donc gratuitement une valeur de Shapley **par dimension**
  (`shapley_scores`). Chaque résultat porte un champ `detail` : contributions **pondérées**
  (`w_d × φ_d`, en pts de composite, sommant au Δ du bloc), persistées dans
  `ablations.scores_json` pour les lignes `shapley`. Le contexte du mutateur les
  affiche en crochet compact filtré à ±1 pt — ex. `bloc_meteo (Δ=+4.2)
  [mo+3 ag+2 | oc-2]` — avec une **légende** des abréviations (g=global,
  ab=modes absents, ag=âge, oc=occupation, ge=genre, mo=motif, di=distance,
  lg=longueur), également rappelée dans l'historique des mutations. Le mutateur
  peut ainsi réécrire un bloc pour garder sa dimension forte et corriger son
  effet secondaire, au lieu de choisir entre garder et supprimer. **Rétro-compat** :
  à la reprise d'une campagne dont l'état a été snapshoté avant cette évolution,
  le détail manquant est reconstitué depuis la table `ablations`
  (`_backfill_ablation_detail`, zéro éval) — les prompts de mutation *déjà
  stockés* (Timeline) restent en revanche figés tels qu'ils ont été générés. Le niveau
  **catégorie** (ex. quelle tranche d'âge derrière `ag+2`) reste porté par la
  section « pires écarts strate × mode » (calculée sur l'éval complète, moins
  bruitée qu'une tranche de Shapley sur le jeu screen).
- **Matrice bloc × mode (2026-07-17)** : les **parts modales** de chaque coalition
  sont ajoutées comme composantes supplémentaires (`mode:{m}`) au vecteur renvoyé
  par `scores_fn` — `shapley_scores` les décompose donc **sur les mêmes évals**
  (zéro appel LLM en plus). Chaque résultat porte un champ `modes` : l'effet de la
  **présence** du bloc sur la part de chaque mode, en pts de % (poussée = `−φ_mode`,
  φ mesurant une réduction). Le contexte du mutateur l'affiche en colonne
  « modes poussés » de la table de contribution (ex. `vélo+4 voit-3`, abréviations
  mar/vélo/TC/voit, seuil de bruit ±1 pt) : le mutateur voit directement *quel mode*
  un bloc favorise ou freine, au lieu de deviner la corrélation depuis les seules
  dimensions. Persistance : clés `mode:{m}` dans `ablations.scores_json`
  (ignorées par `detail_from_stored`, extraites par `modes_from_stored`) ;
  **rétro-compat** : les états snapshotés sans `modes` sont complétés à la reprise
  (`_backfill_ablation_detail`, zéro éval).

### 2.6 Îlots parallèles, merge, Pareto, bibliothèque — **implémentée** (phase 6, D7/DC/DL)

Une seule trajectoire de recuit peut se piéger dans un optimum local et jette les
prompts complémentaires (même composite, dimensions fortes différentes). La phase 6
fait évoluer **plusieurs branches en parallèle** dans le même store et capitalise les
acquis (`calibration/islands.py`, `pareto.py`).

- **Îlots (D7)** (`IslandRunner`, `calibrate run --islands k`) : `n_islands` branches
  `{prefix}-0 … {prefix}-(k-1)`, chacune sa boucle reprenable. L'orchestrateur les fait
  avancer **à tour de rôle** par rondes de `migrate_every` itérations, sous le budget
  RPM commun (k× la durée, pas k× le débit). Son avancement (n° de ronde) est snapshoté
  sous une clé réservée `__islands__` → reprise exacte à la ronde suivante.
- **Migration** : entre deux rondes, le meilleur nœud de chaque îlot est **proposé**
  (pas imposé) à l'îlot suivant en anneau — adopté seulement s'il améliore le composite
  courant de la destination (l'acceptation reste locale). Arête `operator='migrate'`,
  **idempotente** à la reprise (une migration déjà écrite n'est pas redoublée ; l'éval
  du migrant est un cache hit, le prompt ayant déjà été évalué).
- **Merge / crossover (8.3)** (`crossover_every > 0`) : toutes les N rondes, deux
  parents **complémentaires** du front de Pareto (`complementary_pair`) sont fusionnés
  par le modèle de mutation (`propose_crossover`, système dédié) en un nœud à **deux
  parents** (`parent2`), soumis à l'éval de l'îlot cible comme tout candidat. Le corps
  fusionné est décomposé en blocs ; le schéma JSON verrouillé du parent A est réattaché.
- **Archive de Pareto (DC)** (`pareto.py`, pur) : le composite + bootstrap **reste le
  seul critère d'acceptation** dans chaque branche. En parallèle, le front des nœuds
  **non dominés** (au moins aussi bon partout, strictement meilleur quelque part, sur
  `pareto_dims`) est calculé **à la demande** depuis les évals (`store.pareto_candidates`
  → `pareto_front` ; jamais une table maintenue qui dériverait). Il sert à (1) des
  **départs d'îlots diversifiés** (`diversified_seeds`, farthest-point), (2) des
  **parents de merge complémentaires**, (3) atténuer le veto collatéral (un compromis
  non dominé reste archivé au lieu d'être perdu).
- **Bibliothèque d'arguments (DL)** (table `snippets`) : chaque bloc inséré/réécrit
  **accepté avec gain composite ≥ `snippet_min_gain`** y entre, taggé par le mode qu'il
  a aidé (le plus sous-représenté au moment de l'acceptation). Les `snippet_topk` plus
  rentables (pour le levier du moment, repli global) sont fournis au mutateur comme
  **matériau de réécriture** — les îlots se fertilisent même sans merge, et une future
  campagne peut démarrer avec la banque.

Le chemin **mono-branche** (`n_islands=1`) reproduit exactement les phases 1-5.

### 2.7 Finalisation & publication — **implémentée** (phase 7)

La consolidation d'une campagne est outillée par `calibration/publish.py` et
`calibrate finalize` :

- **Éval test unique** : le meilleur prompt (plus faible composite `train`, **toutes
  branches confondues**, `store.best_overall`) est évalué **une seule fois** sur le
  jeu `test` gelé — jamais vu par la boucle, c'est le chiffre publiable. Le prompt
  seed est évalué sur le même jeu → base de comparaison **avant/après**. Les évals
  passent par le cache : une finalisation rejouée ne rappelle pas le LLM.
- **Bilan chiffré** (`campaign_report`, `build_comparison`) : composite par jeu
  (train/val/test) du seed et du meilleur + delta, détail test par dimension, nombre
  de mots avant/après, évals LLM consommées (par jeu + total), acceptées, durée
  approximative (premier→dernier horodatage d'éval).
- **Publication** (`publish_prompt`) : avec `--write`, le prompt calibré est **ajouté**
  à `prompts.yaml` sous `{publish_prefix}_{horodatage}` (convention historique, aucune
  entrée existante modifiée) ; `--activate` met à jour le champ `active`. Par défaut la
  commande est un **dry-run** (le fichier de production n'est pas touché) — l'écriture
  est un effet durable, donc explicite.

Reste opérationnel (hors code, à la charge de l'utilisateur avec des clés provider) :
lancer la campagne de validation complète et publier le prompt gagnant ; le **spike
GEPA** (§5) était prévu *avant* la phase 6 — la phase 6 ayant été codée nativement, il
devient une piste d'évaluation *a posteriori* si l'on veut déléguer îlots+Pareto à la lib.

---

## 3 · Extraction des métadonnées persona

Chaque décision LLM est rattachée aux attributs du persona pour le scoring par strate.
**La cible est implémentée** (phase 0, 2026-07-13) dans
`scripts/prompt_calibration/calibration/metadata.py` — l'ancienne lib garde son
comportement historique :

| Attribut | Ancienne lib (conservée) | Nouvelle version (implémentée) |
|---|---|---|
| âge, occupation | regex sur le texte du persona | `traits_json` de la population (jointure par `agent_id`) ; mapping occupation 1:1 vérifié, valeur inconnue = erreur explicite |
| genre | ⚠ heuristique sur le prénom (`infer_gender_from_name`) | `traits_json.gender` — zéro inférence |
| motif | mapping destination → motif Cerema | idem (depuis l'en-tête structuré de section) |
| distance | regex sur les options de trajet | idem + buckets Cerema (seule métadonnée restée textuelle) |

**Dérive de format résorbée** : la nouvelle version parse les deux formats
d'en-tête (`--- agent_id=… | Destination : … ---` courant et
`--- PERSONA <id> | … ---` legacy), et lit le journal qu'il soit en JSONL strict
ou en objets JSON pretty-printed concaténés (format réel des logs courants).
Critère d'acceptation vérifié : 100 % des sections de `experiments/current`
rattachées (`check_phase0.py`).

**Mémoire STM/LTM exclue des jeux val/test** : la section `**Historique :**` d'un
persona (souvenirs datés + concepts `[Concept]`) est spécifique au run source et
non reproductible ; elle est retirée des personas des jeux **val** et **test** à
leur génération (`strip_memory_section`), pour que la mesure de référence ne
dépende que du profil démographique, du contexte météo et des options de trajet.
Le jeu **train** la conserve (il ne sert qu'à la boucle d'optimisation).

---

## 4 · Reprise & persistance

| Mécanisme | Fichier | Ce qu'il garantit |
|---|---|---|
| Cache d'évaluation adressé par contenu | `calibration_results/eval_cache/<sha>.csv` | Toute éval (prompt × entrées × params) n'est calculée qu'une fois, même après redémarrage |
| Journal des mutations | `calibration_results/mutations.jsonl` | Les mutations LLM (temp 0.8, non reproductibles) sont rejouées à l'identique |
| Checkpoint du meilleur prompt | `calibration_results/best_checkpoint.yaml` | Reprise du meilleur état + archivage dans `prompts.yaml` |

**Implémenté (phase 1, ticket 004)** : un store SQLite unique
(`calibration/store.py`) où l'historique est un **DAG content-addressed** (un
prompt = un nœud identifié par son hash, une mutation = une arête, un merge = un
nœud à deux parents), avec les décisions brutes de chaque éval. Permet : reprise
exacte à tout moment (`calibrate resume` — cache d'éval par contenu + rejeu des
mutations, zéro appel LLM redondant ; l'init n'est refaite que si on part de
zéro), recalcul rétroactif de toute métrique (décisions brutes conservées), et
alimente le dashboard temps réel (phase 2). Branches parallèles et merges
(phase 6) : la boucle multi-îlots (`islands.py`) fait évoluer plusieurs `branch`
dans le même store, avec migration en anneau et merge produisant des nœuds à deux
parents (`parent2`).

```
scripts/prompt_calibration/calibration/
  models.py       # RunConfig (YAML) + pydantic (Block, Mutation, Scores, EvalResult)
  blocks.py       # decompose_prompt / blocks_to_prompt (purs, testés)
  metrics.py      # Metric pluggable : L1Composite + EMDJSDComposite (v2, phase 3)
  stats.py        # acceptation bootstrap appariée sur les agents (phase 3, DA)
  backtest.py     # recalcul rétroactif de losses sur le store (phase 3, zéro LLM)
  evaluation.py   # micro-batching + appels provider + cache adressé par contenu
  mutation.py     # opérateurs (modify/delete/insert + reorder/merge/condense/split),
                  #   multi-candidats (propose_candidates), formatage carte de contribution
  tabu.py         # archive tabu dure : embedding local + cosinus + tenure (phase 4.1)
  bandit.py       # bandit UCB1 de sélection d'opérateur, persisté (phase 4.3)
  shapley.py      # attribution de crédit Shapley (Monte-Carlo tronqué) — phase 5 (DB)
  pareto.py       # dominance + front de Pareto (pur) — phase 6 (DC)
  islands.py      # îlots parallèles + migration + merge/crossover — phase 6 (D7)
  publish.py      # finalisation : éval test unique, bilan avant/après, publication — phase 7
  loop.py         # boucle reprenable : entonnoir (tabu→screening→best), bandit, compaction, Shapley, snippets
  store.py        # RunStore SQLite (nœuds / mutations / évals / ablations / tabu / bandit / snippets)
  export.py       # export lisible (nodes.csv, mutations.csv, history.md)
  importer.py     # import one-shot des artefacts de l'ancienne version
  cli.py          # run / resume / status / export / import / backtest / dashboard
  dashboard_data.py  # requêtes de lecture du store (pures, testées) — phase 2
  dashboard.py       # dashboard Streamlit (rendu seul) — phase 2
```

**CLI** (venv du projet, depuis `scripts/prompt_calibration/`) :

```bash
calibrate run --config run.yaml       # lance/reprend une campagne (sur une branche)
calibrate run --islands 3             # k îlots parallèles dans le même store (phase 6)
calibrate resume --config run.yaml    # reprise explicite (= run)
calibrate status --config run.yaml    # meilleur nœud, itération, #évals
calibrate export --config run.yaml    # vue lisible du store
calibrate import <legacy_dir> --config run.yaml   # récupère un ancien run
calibrate backtest --metrics l1_composite,emd_jsd # recalcule des losses (zéro LLM)
calibrate finalize --config run.yaml  # éval test unique + bilan avant/après (dry-run)
calibrate finalize --write --activate # publie le prompt calibré dans prompts.yaml
calibrate dashboard --config run.yaml # dashboard Streamlit (lecteur pur du store)
```

(remplacer `calibrate` par `../../llm-agents/.venv/bin/python -m calibration.cli`)

**Dashboard (phase 2, implémenté 2026-07-13)** : lecteur **pur** du store
(aucune écriture ; lecture WAL concurrente pendant un run), lancé par
`calibrate dashboard` (wrapper `streamlit run`).

**Filtre d'expérience (barre latérale)** : un selectbox unique `Expérience`
restreint **toutes les vues** à une branche (les îlots `isl-0`, `isl-1`… sont les
« expériences »), ou « Toutes les branches » pour lever le filtre. Sa clé de
session (`exp_filter`) est stable, donc la sélection **persiste au changement de
vue** — plus besoin de refiltrer à chaque page. Les vues multi-branches (Timeline,
DAG, Distribution, Comparaison, Pareto) s'y restreignent ; les vues mono-branche
(Run, Maintenance) prennent la branche filtrée, sinon la première. (Le filtre de
branche local à la Timeline est supprimé au profit de ce filtre global.)

Vues :

- **Timeline** — toutes les mutations depuis l'origine (itération, branche,
  opérateur, bloc, rationale, verdict, score composite **et** par dimension),
  filtres (branche/verdict/opérateur/plage d'itérations) et courbe du meilleur
  score (min cumulé) superposée ;
- **DAG** — graphe de lignée des prompts, un axe par branche, nœud coloré par
  composite, merges (`parent2`) en tireté ; sélection d'un nœud → prompt complet,
  diff vs parent, scores tous jeux, carte d'ablation **avec le détail par
  dimension** (une colonne par dimension, contribution pondérée au Δ du bloc,
  dégradé vert/rouge ; détail Shapley relu tel quel du store) ;
- **Distribution** — parts modales actuel vs EMC² (global) reconstruites depuis
  les **décisions brutes** stockées (zéro réappel LLM) + pires croisements
  strate × mode ;
- **Comparaison** — barres comparant les parts modales de **plusieurs prompts**
  (défaut : seed + meilleur composite ; sélection libre) à la **vérité terrain
  EMC²**, en global ou par strate (âge, occupation, genre, motif, distance :
  un graphique par catégorie, effectifs affichés, catégories issues du YAML de
  référence). Reconstruit depuis les décisions brutes ; les nœuds sans décisions
  stockées sont signalés et ignorés (`comparison_view` dans `dashboard_data.py`,
  pure et testée) ;
- **Pareto** *(phase 6)* — nuage des nœuds évalués (front non dominé en évidence,
  choix des deux axes de dimension) + table du front + **bibliothèque de snippets**
  (arguments comportementaux capitalisés, triés par gain) ;
- **Run** — itération courante, acceptées, meilleur composite/val, modèles et
  températures d'éval/mutation, volumétrie d'éval ;
- **Maintenance** — exécution depuis l'UI des commandes CLI `status` / `export` /
  `import` : statut lisible (nœuds, mutations, meilleur nœud SQL), export lisible
  (nodes.csv / mutations.csv / history.md, avec boutons de téléchargement), et
  import d'un ancien run. L'import **écrit dans le store** (seule exception au
  principe de lecteur pur) : il est protégé par une case de confirmation et un
  avertissement, et déconseillé pendant qu'une campagne écrit sur la même branche.

La vue est pilotable par query param (`?view=DAG`) pour des liens partageables.
La logique de requête et les actions (`export_readable`, `import_legacy_run`)
vivent dans `dashboard_data.py` (fonctions pures/testées sans Streamlit) ;
`dashboard.py` ne fait que le rendu.

---

## 5 · Revue de littérature

Similarité = proximité avec ce projet sur 4 axes : objectif (alignement de
distribution vs accuracy), granularité (blocs de prompt), mécanisme de recherche,
attribution de crédit. Score subjectif sur 100.

### Papiers analysés (fournis)

| Papier | Similarité | Ce qui est commun | Différences clés | À réutiliser |
|---|---|---|---|---|
| **GEPA** — Reflective Prompt Evolution (ICLR 2026, [arXiv 2507.19457](https://arxiv.org/abs/2507.19457), [code](https://github.com/gepa-ai/gepa)) | **55 %** | Évolution de prompt avec mutation réflexive nourrie de feedback textuel riche ; économie de rollouts (35× moins que le RL) | Objectif accuracy par tâche, pas distribution agrégée ; prompts de modules d'un système composé | Front de Pareto + mutation réflexive ; **lib open source à évaluer avant de coder les îlots** |
| **HiveMind** — Contribution-Guided Online Prompt Opt (S2 `acedf1c…`) | **45 %** | Attribution de crédit par prompt via **valeurs de Shapley** ; DAG-Shapley réduit les appels de ~80 % | Multi-agents en ligne (trading), crédit par agent et non par bloc de texte | Shapley échantillonné pour remplacer l'ablation un-bloc-à-la-fois (capture redondances/synergies) |
| **RePrompt** ([arXiv 2406.11132](https://arxiv.org/abs/2406.11132)) | **40 %** | Optimisation itérative guidée par le feedback intermédiaire, sans vérificateur final coûteux | Tâches de planification d'agent ; « gradient » extrait des traces de dialogue | Structurer nos diagnostics par strate comme un gradient textuel explicite |
| **MAPGD** — Multi-Agent Prompt Gradient Descent ([arXiv 2509.11361](https://arxiv.org/abs/2509.11361)) | **40 %** | Agents spécialisés par dimension + détection de conflits entre propositions — miroir de notre loss multi-dimension et du veto collatéral | Benchmarks de classification ; machinerie de fusion de gradients sémantiques | Un proposeur de mutation par dimension de la loss, avec arbitrage |
| **MASS** — Multi-Agent Design ([arXiv 2502.02533](https://arxiv.org/abs/2502.02533)) | **35 %** | Optimisation par étages : prompts locaux par bloc → global — valide notre découpage en blocs | Optimise aussi la topologie d'un système multi-agents ; objectif accuracy | Étage final d'optimisation **globale** du prompt une fois les blocs stabilisés |
| **MARS** — Socratic Guidance (AAAI 2025, Zhang et al.) | **30 %** | APO multi-agents : planificateur / enseignant / critique dialoguent avant de payer l'évaluation | Tâches QA génériques ; pas de cible distributionnelle | Tandem proposeur + critique en amont de l'éval (mutations mieux filtrées) |

### Papiers ajoutés (pertinents, non fournis)

| Papier | Similarité | Apport pour ce projet |
|---|---|---|
| **EvoPrompt** (Guo et al. 2023, [arXiv 2309.08532](https://arxiv.org/abs/2309.08532)) | **50 %** | Algorithmes génétiques sur prompts : population, croisement, sélection — le cadre canonique des « branches » (idée îlots) |
| **« Out of One, Many »** (Argyle et al. 2023, [arXiv 2209.06899](https://arxiv.org/abs/2209.06899)) | **50 %** | *Silicon sampling* : fidélité distributionnelle de personas LLM vs enquêtes humaines — c'est notre **objectif**, sans l'optimisation automatique ; méthodo d'évaluation des biais à reprendre |
| **ProTeGi** (Pryzant et al. 2023, [arXiv 2305.03495](https://arxiv.org/abs/2305.03495)) | **45 %** | « Gradients textuels » + beam search : l'ancêtre commun de la moitié des papiers ci-dessus ; le beam = notre entonnoir multi-candidats |
| **Benchmarking Distributional Alignment of LLMs** (Meister et al. 2024, [arXiv 2411.05403](https://arxiv.org/abs/2411.05403)) | **45 %** | Mesure l'alignement de distributions d'opinions LLM vs groupes démographiques — métriques et pièges directement transposables |
| **PromptBreeder** (Fernando et al. 2023, [arXiv 2309.16797](https://arxiv.org/abs/2309.16797)) | **35 %** | Auto-référence : les *mutation-prompts* évoluent aussi — applicable à notre `_MUTATION_SYSTEM` |
| **OPRO** (Yang et al. 2023, [arXiv 2309.03409](https://arxiv.org/abs/2309.03409)) | **30 %** | Le LLM optimiseur reçoit l'historique (score, solution) trié — valide notre `_build_history_summary`, avec des astuces de formatage |
| **DSPy / MIPROv2** (Opsahl-Ong et al. 2024, [arXiv 2406.11695](https://arxiv.org/abs/2406.11695)) | **25 %** | Optimisation bayésienne des instructions ; surdimensionné ici mais référence d'ingénierie |

**Positionnement** : aucun papier APO n'optimise un objectif d'**alignement de
distribution agrégée** pour de la simulation sociale — c'est l'originalité de ce
module. La littérature APO fournit les mécanismes de recherche ; la littérature
*silicon sampling / distributional alignment* fournit l'objectif et ses pièges.
Ce projet est à l'intersection des deux.

---

## 6 · Lancement depuis l'IHM GAMA

La calibration peut être déclenchée sans quitter GAMA, via un bouton de
l'expérience `e` (fichier `GAMA/CityTransport/models/City.gaml`).

```
IHM GAMA (bouton "Lancer la calibration du prompt")
   │  paramètre "Calibration - cycles (itérations)" → calibration_cycles
   ▼
llm_agent_sync.launch_calibration  (LLMAgent.gaml)
   │  POST /calibrate {"iterations": calibration_cycles}
   ▼
controller  (handle/application.py, port 8002)
   │  subprocess détaché, cwd = /app/scripts/prompt_calibration :
   │  python -m calibration.cli --config config/gama_container.yaml run --iterations N
   ▼
campagne en tâche de fond → journal experiments/current/calibration.log
```

**Points clés :**

| Élément | Détail |
|---|---|
| Endpoint | `POST /calibrate` — corps `{"iterations": N}`, non bloquant, réponse `calibration_started` (pid, cycles, journal). Un seul run à la fois (`calibration_busy` sinon). |
| Montage | `docker-compose.yml` monte `./scripts:/app/scripts` dans le conteneur `controller` (le package de calibration n'y était pas auparavant). |
| Config conteneur | `config/gama_container.yaml` — surcharge les chemins sensibles à la disposition (`llm_module` sous `/opt`, non `/app`). Les défauts relatifs de `RunConfig` restent valables pour un lancement CLI depuis l'hôte. |
| Journal | `experiments/current/calibration.log` (stdout + stderr de la campagne). |
| Prérequis | Jeux gelés `calibration_datasets/<version>/` générés et clés providers dans `.env`. À défaut, la campagne s'arrête avec une erreur explicite dans le journal. |

Le lancement CLI historique (`python -m calibration.cli run --iterations N` depuis
`scripts/prompt_calibration`, avec le venv du projet) reste inchangé.

---

## 7 · Lancement sur une VM cloud gratuite

La campagne peut tourner en autonomie sur une **VM Google Cloud « Always Free »**
(`e2-micro`), sans stack GAMA/controller/Redis : c'est un simple process batch
reprenable (`python -m calibration.cli run`). Tout le nécessaire est dans
`scripts/prompt_calibration/cloud/` :

| Élément | Rôle |
|---|---|
| `cloud/README_CLOUD.md` | Guide pas à pas « pour les nuls » (VM, upload, clé, cron) |
| `config/cloud.yaml` | `RunConfig` côté cloud — les chemins relatifs par défaut fonctionnent tels quels après `git clone` (disposition du dépôt identique) |
| `cloud/setup_vm.sh` | Bootstrap VM Ubuntu : git + venv + `pip install -e llm_module` + deps |
| `cloud/run_daily.sh` | Lance/reprend la campagne ; appelé par un `cron` quotidien |
| `cloud/env.example` | Gabarit du fichier de clé (`PROVIDER_KEYS__google_gemini31`) |
| `cloud/data_to_upload.tar.gz` | Jeux gelés `v1` (gitignorés, donc absents du clone) à envoyer à la VM |

**Principe de reprise / quota** : le free tier Gemini plafonne à **500 requêtes/jour**.
Quand le quota est épuisé, l'éval lève un 429 dont le délai de reset dépasse
`max_retry_wait` (300 s) → le process s'arrête ; les `try/except` de mutation de
`loop.py` **ne persistent pas** `state["iteration"]`, donc la reprise repart de la
dernière itération réellement travaillée. Le `cron` relance chaque nuit et la campagne
progresse « un peu par jour » jusqu'à `max_iterations`. Aucune surveillance requise.

**Contrainte dimensionnante** : le poste rare est le **quota LLM**, pas le CPU/RAM
(travail I/O-bound). Une `e2-micro` gratuite suffit ; passer l'API Gemini en payant est
le seul levier pour terminer en heures plutôt qu'en jours (coût de l'ordre de quelques
dollars pour une campagne, `gemini-flash-lite`).

---

## Voir aussi

- `docs/tickets/ticket_004_prompt_calibration_industrialisation.md` — plan d'industrialisation
- `docs/arch/llm-inference.md` — pipeline d'inférence LLM
- `scripts/data/population/cerema_values.yaml` — référence EMC² 2023
