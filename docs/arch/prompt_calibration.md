  # Calibration de prompt — `prompt_calibration`

Documentation du module de calibration automatique du prompt système `itinary_multi_agent`,
qui optimise le texte du prompt pour rapprocher la distribution des choix modaux produits
par le LLM de la référence **EMC² 2023 Toulouse** (`scripts/data/population/cerema_values.yaml`).

> **Dépôt autonome.** Le code de calibration vit désormais dans un dépôt git séparé,
> `github.com/Ytlse/prompt_calibration`, cloné à la racine du projet sous
> `prompt_calibration/` (ignoré par le dépôt principal `llm-agents-gama`). Les chemins
> `prompt_calibration/…` ci-dessous désignent ce dépôt ; les ressources partagées
> (`llm_module/`, `scripts/data/`, `experiments/`) restent dans le dépôt principal et sont
> référencées via `../../llm-agents-gama/…` depuis les configs, ou remappées dans le
> conteneur GAMA (cf. §lancement IHM). Le paquet s'importe en `prompt_calibration.calibration.*`.

**Fichiers :**

| Fichier | Rôle |
|---|---|
| `prompt_calibration/` | **Nouvelle version** (ticket 004, décision DN) — phases 0-7 livrées : package `calibration/` (models, blocks, metrics, stats, backtest, evaluation, mutation, loop, store, cli, export, importer, dashboard, tabu, bandit, shapley, pareto, islands, **publish**) + tests |
| `prompt_calibration/calibration/store.py` | Store SQLite : DAG content-addressed (nœuds/mutations/évals/ablations) — la fondation reprenable |
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
run initial + ATTRIBUTION DE CRÉDIT (contribution de chaque bloc au score —
                                     omission N+1 par défaut, Shapley en option)
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
   ──► à CHAQUE acceptation : attribution de crédit globale (jeu screen)
   ──► toutes les 5 itérations : éval validation + early stopping
   ──► toutes les COMPACT_EVERY acceptations (+ fin de run) : passe de COMPACTION
        │
        ▼
checkpoint best_checkpoint.yaml ──► publication dans prompts.yaml + diff git-like
```

### Comptages pondérés : mesurer une population, pas simuler un individu

Depuis la bascule du prompt de production vers les **probabilités par option** (cf.
`docs/arch/llm-inference.md`), une réponse d'éval contient, pour chaque persona, la
probabilité de chaque option (somme = 100).

En production, l'agent **tire au sort** dans cette distribution : c'est ce qui rend la
ville vivante. Ici, on ne simule pas un individu, on mesure une population — et tirer au
sort n'ajouterait que du **bruit d'échantillonnage autour d'une moyenne déjà connue**.
Sur ~800 personas, un tirage disperse chaque part modale de ±1,7 point : de quoi noyer
une amélioration réelle du prompt, ou faire accepter une mutation neutre par chance.

`decisions_from_agents()` (`calibration/evaluation.py`) produit donc des décisions
**pondérées** `(agent_id, mode, poids)` : chaque persona verse sa masse de probabilité à
chaque mode qui lui est accessible, pour un total de **1 par persona**. Les métriques
somment ces poids (`metrics.mode_counts`) au lieu de compter des lignes.

| | Avant (tirage) | Après (poids) |
|---|---|---|
| Un persona 60/40 | 1 décision, voiture *ou* bus | 2 lignes, 0.6 et 0.4 |
| Deux évals du même prompt | scores différents (±1,7 pt/mode) | score identique au chiffre près |
| Requêtes par éval `train` | `nb_lots` | `nb_lots` (inchangé) |

Trois points d'attention :

- **`n` reste un effectif de personas** (`metrics.stratum_size`), jamais un nombre de
  lignes ni une masse. Un persona hésitant entre trois modes produit trois lignes : c'est
  **une** personne. Les seuils (`min_count`) portent donc sur des personnes — à valeur
  égale, ils sont plus exigeants qu'avant, où ils comptaient des lignes.
- **`eval_samples` n'a plus d'effet** : sans tirage, il n'y a rien à ré-échantillonner. Le
  champ reste dans `RunConfig` pour ne pas casser les YAML existants, mais il ne figure
  plus dans `eval_params_key()`.
- **Rétrocompatibilité** : les décisions historiques sont des paires `(agent_id, mode)`,
  relues avec un poids de 1 (décision ferme). Tout backtest reste exact sur l'ancien
  comme sur le nouveau format. En revanche `eval_params_key()` porte `policy=weighted` :
  les évals antérieures, où le modèle élisait un mode, ne sont pas comparables et ne sont
  pas réutilisées.

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

**Poids : échelle vs importance, et analyse de sensibilité (2026-07-22)**. Les poids
ci-dessus sont posés à la main et **confondent deux choses** : l'*échelle* d'un terme
(une L1 sur 15 tranches d'âge, une JSD, une EMD n'ont pas la même magnitude — surtout
en loss `emd_jsd`) et son *importance* (le poids qu'on veut lui donner). Deux outils,
sans aucun appel LLM (le store conserve les décisions brutes) :

- **Poids injectables** : `L1Composite` / `EMDJSDComposite` acceptent `weights=` par
  instance (défaut = `WEIGHTS`). Le composite reste **linéaire** (`weighted_composite`),
  donc Shapley et backtest sont inchangés.
- **`calibrate weights`** (`backtest.weight_sensitivity`) reclasse les nœuds évalués
  sous plusieurs schémas — `current`, `uniform`, `informativity` (poids stratifiés
  dérivés du pouvoir discriminant de l'axe dans EMC²), `scaled` (**normalisation
  d'échelle** par le prompt seed : `w'_d = w_d / L1_seed(dim)`, chaque terme part à
  ~1.0), `strat_x2` / `strat_half` — et indique si le **meilleur prompt reste le
  meilleur** (stabilité + corrélation de rang de Spearman). Réponse chiffrée à
  « pourquoi 0.3 pour le genre ? » avant de figer un jeu de poids en production.

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

**État (2026-07-21)** : la loss `emd_jsd` est livrée (`calibration/metrics.py`) et
sélectionnable par `RunConfig.loss` (`get_metric`) ; c'est désormais le **défaut**
(code et YAML). `l1_composite` reste disponible pour comparaison (backtest).
Composition :

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
     changer de bloc-cible, combiner), **sans inventer** de leçon de fond ;
   - `[dégrade]` (**requalification par magnitude**, 2026-07-28) → le candidat **aggrave
     nettement** l'écart : le **levier lui-même est réfuté**, pas seulement sa formulation.
     Consigne inverse de `[bruit]` : abandonner le levier, ne pas le reformuler.

   ⚠ **Le défaut que corrige `[dégrade]`.** L'étiquetage initial classait en `[bruit]` *tout*
   rejet portant un `Δ=`, quelle que soit son ampleur : un `Δ=+9.89` sur un composite de 42.7
   (soit −23 % de qualité, mesuré dès le palier à 25 %) recevait la même étiquette qu'un
   `Δ=+0.30`, donc la même consigne — « l'idée n'est pas invalidée, garde le levier ». La boucle
   **ordonnait au mutateur de persévérer sur une piste que la mesure venait de réfuter**. En
   campagne 7, cinq itérations consécutives ont ainsi reformulé le même levier sur `consigne_s3`.
   La requalification compare désormais le Δ ponctuel à `_DEGRADE_REL_TOL` (10 %) du composite
   courant — seuil calibré sur les rejets réels de cette campagne (+2.22 → +9.89), qui sépare les
   dégradations franches des Δ marginaux encore dans le bruit d'un palier partiel. L'intervalle
   de confiance de `rejected_stat` (`IC90 Δ=[…]`) est volontairement ignoré : ce n'est pas un
   point, et une amélioration non significative n'est pas une dégradation.

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
   conséquence. Cette synthèse est **empilée** dans `state["lessons"]` (`_absorb_reflection`
   dans `loop.py`) — une **liste roulante des 5 dernières** synthèses (chacune bornée à
   `lessons_max_chars`, anti-ancrage), **persistée** dans `run_state` (reprise gratuite) et
   **réinjectée** numérotée au tour suivant (`format_lessons` → `build_mutation_user_msg`).
   *(Rétro-compat : un `run_state` snapshoté avec une leçon unique — ancien format chaîne — est
   repris comme liste d'un élément.)* La synthèse est produite dans le **même appel** que la proposition
   (coût quasi nul, pas d'appel LLM dédié) ; sur le chemin entonnoir, elle est commune aux
   candidats et suit celui qui est retenu. Au rejeu depuis le store (reprise), la mutation
   reconstruite n'a pas de champ `reflection` → l'absorption est un no-op (aucune leçon fantôme).

#### 2.4.3 Contexte concret pour le mutateur : snippets entiers & matrice bloc × mode — **implémenté**

Le mutateur raisonnait uniquement sur des **agrégats** (distributions, écarts, contributions) ;
deux évolutions lui donnent du **concret**, sans aucun appel LLM supplémentaire (données déjà
persistées, uniquement du calcul et du formatage) :

> **Note (2026-07-21) — allègement et réécriture du contexte du mutateur.** Le message envoyé
> au mutateur a été refondu pour aller à l'essentiel et parler le langage « ingénieur prompt » :
> - **Phrase d'intro** : le message s'ouvre sur la mission (« Tu es ingénieur prompt : ta mission
>   est d'optimiser le prompt système ci-dessous… »).
> - Le bloc *hard negatives* (exemples individuels persona → mode) est **retiré** (redondant avec
>   les « pires écarts strate × mode ») ; le bloc « DEUX leviers prioritaires » (mode global le plus
>   mal prédit à renforcer/atténuer) est aussi retiré (info portée par les écarts strate × mode et
>   la consigne système).
> - En-tête `Distribution LLM actuelle :` **sans** le compte de décisions ; **top 10** des pires
>   écarts (au lieu de 6) **sans** l'effectif `n=` ; suppression de la ligne `Score composite actuel`.
> - **Terminologie « écart »** partout (au lieu de « composite »/« score ») : l'historique affiche
>   `écart total=… (par dimension : global …, âge …, occupation …, …)`, **en toutes lettres**.
> - **Présentation unifiée du prompt** (`format_prompt_with_contrib`) : les blocs sont donnés **dans
>   leur ordre d'application**, chacun avec son **contenu entier** ET sa contribution (`Δ écart`,
>   dimensions aidées/dégradées, effet sur les modes — **sans abréviations**), **blocs fixes inclus**
>   (signalés non modifiables). Cette présentation **remplace** l'ancienne table markdown + le dump
>   séparé « Blocs modifiables » (seule subsiste la liste des cibles valides près de la consigne JSON).
> - **Mémoire de leçons** : jusqu'aux **5 dernières** synthèses de rejet, numérotées (cf. §2.4.2),
>   placées **juste après** l'« Historique des mutations » (en-tête « Historique des mutations et
>   enseignements ») dont elles sont le prolongement.
> - Le rappel d'opérateur ne suggère « garde de la diversité » qu'en **multi-candidats**. La ligne
>   `💡 Opérateur à privilégier ce tour` clôt le message (juste après la consigne JSON).
> - La section « Diversité des cibles » (rappel anti-fixation listant les blocs récemment modifiés)
>   a été **retirée** : le garde-fou anti-resoumission (tabu + prescreen, §2.4.2) couvre déjà la
>   ré-application triviale sur le même bloc.

1. **Snippets fournis en entier** (`SNIPPET_MAX_CHARS` = 300, cap de sécurité) — la bibliothèque
   d'arguments (DL) est un *matériau de réécriture* : tronquée à 110 caractères comme avant, elle
   forçait le mutateur à halluciner la fin des arguments. Le contenu est désormais fourni en
   entier (ellipse seulement au-delà du cap).

2. **Matrice bloc × mode** — ligne « effet sur les modes » de la présentation par bloc
   (cf. §2.5, décomposition Shapley par part modale) : quel mode chaque bloc favorise ou freine.
   La présentation par bloc fournit aussi le **contenu entier** de chaque bloc, dans l'ordre,
   blocs fixes compris.

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

### 2.5 Attribution de crédit aux blocs — **implémentée** (phase 5, DB)

Après chaque acceptation (et à l'init), la contribution de chaque bloc au score est
recalculée sur le jeu `screen`. Deux méthodes, réglées par **`attribution_method`** :

| Méthode | Coût par passe | Ce qu'elle donne |
|---|---|---|
| **`omission`** (défaut) | **`N+1` coalitions** | Retrait bloc-à-bloc : `score(prompt − bloc) − score(prompt)`. Budget fixe et prévisible ; suffit à **classer** les blocs — tout ce dont le ciblage a besoin. |
| `shapley` (option) | ≈ `2 + M·N` coalitions (~25×) | Répartition **exacte** du gain, redondances et synergies comprises. |

Les deux écrivent dans `ablations` au même format (`method` les distingue) et
**partagent le cache content-addressed** : basculer de l'une à l'autre ne jette aucune
éval, les coalitions « complet moins un bloc » étant communes.

**Pourquoi l'omission ne suffit pas toujours** — mesurer `score(prompt − bloc_i)`
suppose les blocs **indépendants** et se trompe dans deux cas : **redondance** (deux
blocs équivalents paraissent chacun inutile pris isolément, alors qu'en retirer les
deux coûte) et **synergie** (le retrait depuis le prompt complet attribue *toute* la
synergie à *chaque* bloc → la somme dépasse le gain réel). La **valeur de Shapley**
répartit exactement le gain total entre les blocs, redondances et synergies comprises.

**Pourquoi l'omission est malgré tout le défaut** — le recalcul global après chaque
acceptation est le poste qui consomme le quota LLM journalier (campagne 7 : « RPD
reached » après 27 itérations sur 200). Un classement correct à `N+1` évals fait
avancer la boucle ; une attribution exacte à 25× le prix l'arrête. Shapley reste
disponible pour une passe d'analyse ponctuelle, hors boucle.

Le reste de cette section décrit l'implémentation Shapley, la plus riche des deux.

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
  répétées (entre permutations, entre runs) sont gratuites. Une coalition n'est
  mise en cache que si son df d'éval est **non vide** : un lot noyé d'erreurs
  réseau (df vide) n'est jamais persisté → il est recalculé à la reprise. C'est
  pourquoi un run relancé après épuisement de quota reprend exactement à la
  première coalition non payée (les précédentes étant servies par le cache).
- **Coupe-circuit d'épuisement de quota** (`eval_max_consecutive_errors`, défaut 3)
  — l'`Evaluator` compte les échecs de lot **consécutifs** dans l'ordre
  d'achèvement, cumulés d'une coalition à l'autre ; tout succès remet le compteur
  à zéro (une erreur réseau transitoire isolée ne déclenche donc pas). Au seuil,
  les lots en attente sont annulés et `EvaluationAborted` est levée, interceptée
  par `cmd_run` pour un **arrêt propre** (message clair, aucune trace, cache
  intact). But : exploiter le quota journalier jusqu'à la première salve d'erreurs
  franche, puis s'arrêter sans marteler l'API. `0` désactive le garde-fou.
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

### 2.8 Mutation décomposée : cibler / diagnostiquer / rédiger — **implémentée** (phase 8)

Un appel unique demandait au mutateur d'être **simultanément** analyste de ses échecs,
sélecteur de cible et rédacteur, avec tout le contexte servi d'un bloc (carte des 11
blocs annotés, historique, leçons, bibliothèque). La proposition est désormais scindée
en trois étages, chacun ne voyant que ce qui le concerne.

**Étage A — ciblage (code, 0 appel LLM, `calibration/targeting.py`).**
`select_target()` désigne le bloc et le levier par `argmax` sur des grandeurs **déjà
mesurées** : nocivité Shapley (−Δ), désalignement modal (le bloc pousse-t-il un mode
déjà sur-représenté ?), pires strates. *Pourquoi en code :* faire relire une table à un
LLM pour qu'il en renvoie le maximum dépense un appel à reproduire un calcul, avec le
risque qu'il se trompe. Deux garde-fous s'y greffent :

- **Cooldown par bloc** (`target_cooldown_rejects`, `target_cooldown_span`) : après *k*
  rejets **consécutifs**, un bloc sort du jeu des cibles pour *n* itérations. Le tabu ne
  filtrait que la similarité **textuelle** d'une proposition, jamais l'**acharnement sur
  une cible** — d'où les cinq itérations consécutives sur `consigne_s3` en campagne 7.
  Une acceptation remet le compteur à zéro. Si *tous* les blocs sont en cooldown, le
  meilleur est conservé : une itération sans cible serait une itération perdue.
- **Leviers réfutés** : les rationales des rejets `[dégrade]` du bloc sont réinjectées
  comme interdits explicites.

Effet de bord voulu : le prompt perd la carte de contribution des blocs **non ciblés**
(`format_prompt_with_contrib(..., focus=...)`), qui n'a plus d'objet une fois la cible
choisie. Les autres blocs gardent leur **contenu** — indispensable pour ne pas créer de
redite ou de contradiction. Mesuré sur les branches du store : −6 à −19 % de caractères.

**Étages B/C — diagnostic puis rédaction (`decomposed_mutation`, défaut `false`).**
B reçoit le seul bloc-cible, son levier, les échecs **sur ce bloc** et (à venir) les
justifications verbatim ; il sort du **JSON contraint** `{mecanisme, directive,
interdits}` et **ne rédige pas**. C reçoit le prompt complet *sans appareil analytique*,
plus la directive, et écrit. Mesuré sur la campagne 7 : le plus long des deux appels
tombe de 15 586 à 6 782 caractères (**−56 %**), et la **somme** des deux vaut 0,57× le
monolithique — la décomposition est donc moins chère en tokens *malgré* l'appel
supplémentaire.

Coût : +1 appel sur le seau `mutation_provider`, **distinct** de celui de l'éval (le
quota journalier Gemini est *par modèle*) — donc sans effet sur le facteur limitant.
`diagnosis_model` permet de placer un modèle plus capable sur B, le maillon dont
l'erreur se propage à la rédaction.

Garde-fous de la chaîne : un diagnostic **sans directive** court-circuite l'étage C
(on ne fait pas rédiger sans consigne) et fait **retomber sur le chemin monolithique**
dans la même itération ; un rédacteur qui répond hors cible est **refusé sans éval**
(`_single_prescreen`) plutôt que réétiqueté — réétiqueter appliquerait à un bloc un
texte rédigé pour un autre.

`targeting_enabled: false` / `decomposed_mutation: false` restaurent le comportement
historique : ce sont les **bras témoins** de l'ablation *mutation décomposée vs
monolithique, à budget d'éval égal*.

#### 2.8.1 Garde-fou : aucune règle à seuil chiffré — **implémenté**

La contrainte « jamais de seuil chiffré ni de table distance→mode » n'existait que
comme **consigne en langage naturel** dans `_MUTATION_SYSTEM` : rien ne l'appliquait.
Conséquence mesurée dans le store : un bloc « privilégie les modes actifs […] pour tout
déplacement **inférieur à 2 km** » avait été accepté, **capitalisé en snippet** (gain
134.4, taggé `marche`) puis **réinjecté à chaque itération** comme exemple à imiter — le
pipeline enseignait la règle qu'il interdit.

`find_numeric_threshold()` (`mutation.py`) applique la règle en code, à trois points :
validation du candidat **avant éval** (chemins single et entonnoir), **capture** de
snippet, et **service** des snippets — ce dernier neutralisant les snippets pollués des
campagnes antérieures **sans migration du store**.

Ce qui est visé, c'est la **règle** (comparateur + quantité), pas la mention d'un
nombre : « moins de 2 km » est bloqué, « la règle des 48 heures » passe. Les variantes
en toutes lettres (« sous deux kilomètres ») et les parts modales explicites (`26 %`,
« 26 pour cent ») sont couvertes. *Pourquoi cette règle est structurante :* un seuil
chiffré transforme le choix modal en **automatisme déterministe** — le prompt cesse de
simuler un raisonnement comportemental et encode directement la réponse attendue, ce qui
détruit la validité de la calibration hors du jeu d'évaluation (cf. la limite « matcher
les marginales ≠ faire raisonner juste » du `TODO.md`). Une règle sur la distance est en
outre **structurellement incapable** de corriger les plus gros écarts de la campagne 7,
qui sont des écarts de **genre** (`genre[Femme]·marche −21.7`).

---

## 3 · Extraction des métadonnées persona

Chaque décision LLM est rattachée aux attributs du persona pour le scoring par strate.
**La cible est implémentée** (phase 0, 2026-07-13) dans
`prompt_calibration/calibration/metadata.py` — l'ancienne lib garde son
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

**Parité du traitement des options (2026-07-30)** — `prod_option_handling`, défaut `true`.
Les jeux gelés rendent les étapes d'un itinéraire (« - Marche jusqu'à 'work' ») en puces de
**même niveau** que la ligne d'option `- [n] mode: …` : plusieurs modèles les comptent alors
comme des options, renumérotent tout le bloc et placent leurs probabilités hors bornes
(cf. `docs/arch/llm-inference.md`). La mesure portait donc, pour une part des personas, sur
une répartition **uniforme** qu'aucun prompt n'avait produite. Deux alignements sur la
production, sous un seul drapeau :

- `render_option_substeps()` ré-indente les étapes en sous-puces « · » et annonce le nombre
  d'options, **au moment de bâtir le lot** — comme `inject_context` réinjecte la météo. Le
  jeu sur disque n'est pas modifié : transformation idempotente, lignes d'option intactes
  (`parse_option_modes` et l'extraction de distance lisent la même chose avant/après —
  vérifié sur les 803 records de `v1`). Coût : +3 à +6 % de caractères par section.
- `decisions_from_agents(realign_out_of_range=True)` réaligne une probabilité hors bornes sur
  l'option que son libellé de mode désigne, au lieu de l'écarter.

Le drapeau entre dans `eval_params_key()` (`opt=prod` / `opt=legacy`) : le prompt envoyé
**et** la masse comptée changeant tous les deux, les évals des deux régimes ne se mélangent
jamais dans le store. Le passer à `false` restaure le régime historique — c'est ce qu'il
faut faire pour reprendre une campagne sur ses évals déjà payées. Au moment du correctif la
question ne se posait pas : les deux stores ne contenaient **aucune** éval sous
`policy=weighted` (toutes antérieures, en `samples=3`), donc rien à re-payer.

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

### 4.1 Régime de mesure : ce qu'un composite stocké permet de comparer

Un store accumule les **régimes de mesure**, et un composite n'est comparable
qu'aux composites du même régime. Trois choses le définissent, toutes portées par
`eval_params_key()` (`prov | model | temp | policy`) :

| Ce qui change | Effet | Réparable après coup ? |
|---|---|---|
| la **loss** (L1 → EMD/JSD) | le score, pas les décisions | **oui** — `backtest` / `rescore`, zéro LLM (les décisions brutes sont conservées) |
| le **modèle** d'éval (mistral → gemini) | les décisions | **non** — il faut réinterroger |
| la **politique** de décision (mode élu → masse de probabilité) | les décisions | **non** — idem |

D'où la lecture du store actuel : le prompt seed vaut **176,7** sous
`mistral-small-latest` et **25,9** sous `gemini-3.1-flash-lite-preview`, pour le
*même texte*. Ramener les deux à la loss courante réduit l'écart — il venait pour
l'essentiel de losses différentes — mais ne réconcilie pas les décisions. Une
trajectoire tracée à travers les régimes mesure donc autant le changement
d'instrument que l'effet du prompt.

**`calibrate reeval`** (`calibration/reeval.py`) rejoue pour cette raison une
**lignée entière** — la chaîne des mutations acceptées, de la graine à la feuille —
sous la clé de la config courante :

```bash
calibrate reeval --config run.yaml --branch essai2 --dry-run   # plan + coût
calibrate reeval --config run.yaml --branch essai2 --workers 8 # mesure
```

| Option | Rôle |
|---|---|
| `--node <préfixe>` | feuille explicite ; défaut = dernier nœud **accepté** de la branche |
| `--dataset` | jeu gelé (défaut `train`) |
| `--batch N` | personas par requête. **Mettre 8** : à 15 (capacité déduite du TPM), le modèle omet des personas de sa réponse — voir ci-dessous. N'entre pas dans `eval_params_key()`, donc ne change pas la mesure, seulement le nombre d'appels. |
| `--workers N` | requêtes en vol. Le facteur limitant d'un rejeu est la **latence**, pas le RPM : à 2 requêtes en vol pour ~2 min de génération, on ne consomme qu'~1 req/min sur les 15 autorisées. N'entre pas dans `eval_params_key()` — la mesure est inchangée. |
| `--provider` | seconde clé (`google2`), pour finir une lignée quand le RPD de la clé 1 est épuisé. La page de synthèse regroupe les régimes par **modèle · politique**, pas par `params_key` : deux clés sur le même modèle restent **une seule courbe**. Le cache, lui, est bien distinct (le provider entre dans `eval_params_key()`) — les nœuds déjà payés sur la clé 1 seront donc **repayés** sur la clé 2. |

#### Le lot incomplet : ce que l'instrumentation a montré (2026-07-31, action A10)

Sous la politique pondérée, une éval de lignée « n'avançait plus » sans qu'aucune erreur
ne remonte. L'hypothèse consignée ici — sortie ~5× plus longue → dépassement du timeout
de 240 s de l'adaptateur Google — **était fausse**. Les trois grandeurs relevées sur des
lots réels du jeu `train`, prompt de la feuille `0fc427e7`, modèle
`gemini-3.1-flash-lite-preview` :

| Lot | Latence | `finishReason` | Tokens de complétion | Décisions rendues |
|---|---|---|---|---|
| 3 personas | 2,6 s | `STOP` | 762 | 3/3 |
| 8 personas | 5,0 s | `STOP` | 1 637 | 8/8 |
| 15 personas (lot 0) | 7,2 s | `STOP` | 2 737 | 15/15 |
| 15 personas (lot 3) | **3,8 s** | **`STOP`** | **1 287** | **6/15** |
| 15 personas (lot 8) | 3,6 s | `STOP` | 1 200 | **5/15** |

- **Ni timeout** : 3,6 à 8,8 s pour une limite de 240 s — deux ordres de grandeur de marge.
- **Ni troncature** : `finishReason=STOP` partout, 2 742 tokens de complétion au pire pour
  un plafond de 4 096 (`InternalRequest.max_tokens`). Le chemin `MAX_TOKENS` n'a jamais
  été emprunté.
- **Le modèle omet des personas.** Il rend un JSON valide, conforme au schéma, complet de
  son point de vue — mais qui ne contient que 5 à 8 des 15 personas demandés. Sur
  12 lots de 15, **4 étaient amputés** (33 personas perdus sur 180, soit 18 % de la
  population). Un échantillon de 10 lots de 8 était complet — mais le rejeu entier de la
  lignée a montré que **les lots incomplets à 8 restent courants** (jusqu'à 1 persona
  rendu sur 8). La taille de lot atténue, elle ne garantit pas.

Rien dans la chaîne ne voyait ce cas : ce n'est ni une erreur HTTP, ni une troncature, ni
un défaut de schéma. Le lot passait pour un **succès**, remettait à zéro le compteur
d'échecs consécutifs du coupe-circuit, et l'éval était calculée puis **mise en cache** sur
une sous-population — indistinguable en base d'une mesure complète.

*(À noter aussi : la clé `google_gemini31` avait son RPD de 500 épuisé. Un quota mort
produit un 429 explicite, correctement traité — ce n'était pas la cause du silence.)*

#### Les trois défenses ajoutées

1. **Comparaison demandé/reçu, à chaque lot.** `make_provider_call` confronte les
   `agent_id` envoyés à ceux rendus. C'est la seule défense possible : le défaut est
   invisible à tous les autres étages.
2. **Re-tir par moitiés** (`split_entry`). Redemander le même lot à température 0 redonne
   le même résultat : il faut **réduire la demande**. Le lot incomplet est coupé en deux
   et rappelé, récursivement. Mesuré en conditions réelles : un lot à 5/15 revient à
   **15/15 en 3 appels**. Le découpage n'entre pas dans `eval_params_key()` — il ne change
   **pas la mesure**, seulement le nombre d'appels.
3. **Garde de couverture** (`eval_min_coverage`, défaut 0,98). Si, malgré le rattrapage,
   l'éval n'a pas couvert assez de personas, elle lève `InsufficientCoverage` **avant**
   toute écriture. Le store ne conserve pas le nombre de personas vus : un score calculé
   sur 60 % du jeu y entrerait indistinguable d'un score complet et fausserait toute la
   trajectoire. Mieux vaut un nœud « manquant », qui est vrai.

Enfin, l'**échec silencieux** proprement dit est refermé : la boucle de retry de
`call_with_retry` rendait une **liste vide** en sortie de boucle, que l'appelant prenait
pour un lot légitimement sans décision. Elle lève désormais `RetriesExhausted` avec une
ERREUR `[ALARME]`.

> **Choix de lot recommandé** : `--batch 8`. Il ne supprime pas les lots incomplets — le
> rattrapage reste le filet — mais il en déclenche assez peu pour que le surcoût reste
> modeste. Mesuré sur le rejeu complet de la lignée `essai2` (6 nœuds × 62 lots) :
> **40 lots incomplets sur 372**, tous rattrapés, pour **432 appels** au lieu de 372 —
> soit **+16 %**.

#### Ce que le rejeu a produit (2026-07-31)

```bash
calibrate reeval --config run.yaml --branch essai2 --provider google2 --batch 8 --workers 4
```

432 appels, ~25 min, sur la **seconde clé** Google (le RPD de la première était épuisé).
Trajectoire sur `train`, sous `gemini-3.1-flash-lite-preview · masse de probabilité` —
composites tels que stockés par le moteur (loss `emd_jsd`, poids de la campagne) :

| # | Nœud | Branche | Composite | Δ graine |
|---|---|---|---|---|
| 0 | `4c2ea89428` | main | 23,58 | — |
| 1 | `00ea9b077a` | main | 24,99 | +1,41 |
| 2 | `2663e10eb9` | essai2 | 22,02 | −1,56 |
| 3 | `6b39f690a9` | essai2 | 20,62 | −2,96 |
| 4 | `d1c9508f68` | essai2 | 22,18 | −1,40 |
| 5 | `0fc427e7b5` | essai2 | **21,40** | **−2,18** (−9,2 %) |

La page de synthèse recalcule ces composites avec ses propres poids « comparables »
(`length_penalty` neutralisée), d'où des niveaux légèrement différents — 24,35 → 22,24,
gain 2,12 — pour la même trajectoire.

**Les deux régimes s'accordent.** Sous `mistral-small-latest · mode élu`, la même lignée
gagne 7,60 points (24,9 % du niveau de la graine) ; sous le régime de production, 2,12
points (8,7 %). Près de trois fois moins en part, mais **dans le même sens** : le gain de
la calibration n'est pas un artefact de l'instrument qui l'a guidée. Son ampleur, en
revanche, ne se transporte pas — c'est le chiffre du régime de production qui fait foi.

Deux points de conception :

- **La lignée est reconstruite par les arêtes de mutation, pas par la seule
  colonne `parent`.** Les nœuds étant adressés par contenu, un prompt déjà produit
  sur une autre branche est réutilisé tel quel, avec le `parent` de sa *première*
  création — souvent aucun. C'est le cas du deuxième nœud de la lignée `essai2`,
  apparu sur `main` trois jours plus tôt : chaîner par `parent` seul s'arrête là et
  **perd la graine**, c'est-à-dire la référence à laquelle toute la trajectoire se
  compare. `lineage_chain` replie donc sur `mutations(node_to → node_from)`.
- **Le rejeu est reprenable sans réflexion.** Une éval n'est mise en cache qu'une
  fois complète ; relancer la commande après un épuisement de quota repart au
  premier nœud non payé, les précédents étant servis par le cache. Un abort quota
  écrit le cooldown comme `run`, et la commande refuse de démarrer tant qu'il court.

```
prompt_calibration/calibration/
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
  reeval.py       # rejeu d'une lignée sous un régime d'éval unique (§4.1)
  export.py       # export lisible (nodes.csv, mutations.csv, history.md)
  importer.py     # import one-shot des artefacts de l'ancienne version
  cli.py          # run / resume / status / export / import / backtest / reeval / dashboard
  dashboard_data.py  # requêtes de lecture du store (pures, testées) — phase 2
  dashboard.py       # dashboard Streamlit (rendu seul) — phase 2
```

**CLI** (venv du projet, depuis `prompt_calibration/`) :

```bash
calibrate run --config run.yaml       # lance/reprend une campagne (sur une branche)
calibrate run --config cloud.yaml --loop  # daemon autonome : dort au quota, reprend seul (§7)
calibrate run --islands 3             # k îlots parallèles dans le même store (phase 6)
calibrate resume --config run.yaml    # reprise explicite (= run)
calibrate status --config run.yaml    # meilleur nœud, itération, #évals
calibrate export --config run.yaml    # vue lisible du store
calibrate import <legacy_dir> --config run.yaml   # récupère un ancien run
calibrate backtest --metrics l1_composite,emd_jsd # recalcule des losses (zéro LLM)
calibrate reeval --branch essai2       # rejoue une lignée sous le modèle d'éval épinglé (§4.1)
calibrate reeval --node 0fc427e7 --dry-run  # plan + coût en appels, sans rien payer
calibrate finalize --config run.yaml  # éval test unique + bilan avant/après (dry-run)
calibrate finalize --write --activate # publie le prompt calibré dans prompts.yaml
calibrate dashboard --config run.yaml # dashboard Streamlit (lecteur pur du store)
```

(remplacer `calibrate` par `../../llm-agents-gama/llm-agents/.venv/bin/python -m calibration.cli`)

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
   │  subprocess détaché, cwd = /app/prompt_calibration :
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
`prompt_calibration`, avec le venv du projet) reste inchangé.

---

## 7 · Lancement sur une VM cloud gratuite

La campagne peut tourner en autonomie sur une **VM Google Cloud « Always Free »**
(`e2-micro`), sans stack GAMA/controller/Redis : c'est un simple process batch
reprenable (`python -m calibration.cli run`). Tout le nécessaire est dans
`prompt_calibration/cloud/` :

| Élément | Rôle |
|---|---|
| `cloud/README_CLOUD.md` | Guide pas à pas « pour les nuls » (VM, upload, clé, cron) |
| `config/cloud.yaml` | `RunConfig` côté cloud — les chemins relatifs par défaut fonctionnent tels quels après `git clone` (disposition du dépôt identique) |
| `cloud/setup_vm.sh` | Bootstrap VM Ubuntu : git + venv + `pip install -e llm_module` + deps |
| `cloud/run_daily.sh` | Lance/reprend la campagne ; appelé par un `cron` quotidien |
| `cloud/env.example` | Gabarit du fichier de clé (`PROVIDER_KEYS__google_gemini31`) |
| `cloud/data_to_upload.tar.gz` | Jeux gelés `v1` (gitignorés, donc absents du clone) à envoyer à la VM |
| `cloud/calib.service` | **Unité systemd** du daemon autonome (`run --loop`) |

**Principe de reprise / quota** : le free tier Gemini plafonne à **500 requêtes/jour**.
Quand le quota est épuisé, l'éval lève des 429 ; au bout de `eval_max_consecutive_errors`
échecs de lot consécutifs, le coupe-circuit lève `EvaluationAborted` (arrêt propre, cache
intact). Les `try/except` de mutation de `loop.py` **ne persistent pas**
`state["iteration"]`, donc la reprise repart de la dernière itération réellement
travaillée jusqu'à `max_iterations`.

**Cooldown quota & lancement autonome (2026-07-23)** — deux modes, tous deux pilotés par
un **cooldown persisté** (`cooldown` dans le store, portée *globale* : le quota provider
est partagé entre branches/îlots) :

- À l'abort, `cli._resume_after` calcule l'instant de reprise autorisé et
  `store.set_cooldown` le persiste. La durée vient du **429 lui-même**
  (`classify_quota_error` extrait le `retryDelay` et détecte le marqueur *journalier*
  `PerDay`). Nuance clé : le `retryDelay` de Gemini est fiable pour le **RPM** (quelques
  secondes) mais **pas** pour le quota **journalier** (il sous-estime le temps jusqu'au
  reset). Donc, si le 429 est identifié `is_daily_quota`, on vise le **prochain minuit
  local** (`quota_reset_tz`, défaut `America/Los_Angeles`, DST géré par `zoneinfo`) au
  lieu du délai annoncé — c'est ce qui maximise le RPD : on reprend pile à l'ouverture du
  quota frais. Repli (`cooldown_fallback_seconds`, court) si aucun délai exploitable ;
  plafond `cooldown_max_seconds` anti-veille infinie.
- **Daemon (`run --loop`, recommandé cloud)** : le process ne s'arrête pas — il dort par
  tranches (`daemon_sleep_chunk_seconds`, heartbeat `💤`) jusqu'au `resume_after`, puis
  reprend. `cloud/calib.service` le maintient en vie (`systemctl enable --now calib` :
  redémarrage au boot + après crash, back-off `StartLimitBurst` contre la boucle sur clé
  invalide). Supervision réduite à `journalctl -u calib`. C'est le mode qui exploite au
  mieux RPD/TPD sans ordonnanceur externe.
- **Cron one-shot (`run_daily.sh`, alternative)** : inchangé, mais bénéficie de la même
  garde — `cmd_run` sort proprement si un cooldown est encore actif, au lieu de re-taper
  l'API. Ne pas activer daemon *et* cron simultanément.

**Contrainte dimensionnante** : le poste rare est le **quota LLM**, pas le CPU/RAM
(travail I/O-bound). Une `e2-micro` gratuite suffit ; passer l'API Gemini en payant est
le seul levier pour terminer en heures plutôt qu'en jours (coût de l'ordre de quelques
dollars pour une campagne, `gemini-flash-lite`).

---

## 8 · Notifications Discord (supervision du daemon cloud)

Le daemon `run --loop` tourne sans surveillance sur la VM. Un module de
notification **best-effort** remonte les transitions d'état sur un salon Discord,
pour savoir « où en est la campagne » sans se connecter en SSH.

**Transport** (`calibration/notify.py`) : POST d'un embed sur un **webhook
Discord** (pas de bot), en `urllib` stdlib (zéro dépendance), sous timeout court.
Tout échec d'envoi est **avalé** — une notification perdue n'influe jamais sur la
campagne ; le store SQLite reste la seule source de vérité et `journalctl -u
calib` garde la trace complète.

**Interrupteur** : l'URL est lue de l'environnement `DISCORD_WEBHOOK_URL` (un
**secret** — dans `~/calib.env`, jamais en config ni journalisé). Absente →
`notify` est un **no-op silencieux** (runs locaux et tests ne notifient rien).

**Événements de transition d'état** (le heartbeat `💤` de veille n'est **jamais**
notifié : anti-spam) :

| Événement | Déclencheur (`cli.py`) | Niveau |
|---|---|---|
| 🟢 `daemon_start` | démarrage du daemon — **d'où l'on part** : itération de reprise, best connu, acceptées, veille en cours le cas échéant | info |
| ⏸️ `quota_paused` | quota épuisé → cooldown : heure de reprise, raison, **étape interrompue** et bilan de la passe | warn |
| ⚠️ `quota_marker` | abort quota **sans** marqueur « per day » → cooldown court (détection dégradée : le libellé Gemini a peut-être changé, cf. `_DAILY_QUOTA_RE`) | warn |
| 🟢 `resume` | réveil effectif après une veille quota | good |
| 🏆 `new_best` | le meilleur composite a baissé pendant la passe (une fois **par passe**, pas par itération) | good |
| ✅ `campaign_done` | budget d'itérations atteint (+ bilan de la passe) | good |
| ☠️ `daemon_failed` | **process mort** (crash / OOM / clé invalide → back-off systemd) — via `OnFailure=` (voir plus bas) | error |
| 📊 `digest` | digest quotidien (voir plus bas) | info |

### 8.1 · Suivi d'avancement (`calibration/progress.py`)

Les transitions ci-dessus disent **que** le daemon travaille, pas **où il en
est** : entre « Daemon démarré » et « Quota épuisé », six heures de silence. Un
tracker **in-process** (singleton `progress.session()`) tient l'étape courante et
les compteurs de la **passe** (un réveil du daemon), alimenté par toutes les
couches du moteur — `loop.py` pour les étapes, `run_shapley` pour les coalitions,
`Evaluator.evaluate` pour les évals payées/servies par le cache et les lots.

| Événement | Déclencheur | Contenu |
|---|---|---|
| ▶️ `pass_start` | moteur assemblé, avant la 1ʳᵉ requête | itération de départ → cible, best, prompt courant (composite, mots, blocs mutables), tailles des jeux, modèle d'éval, coalitions Shapley attendues |
| 🔹 `stage` | changement d'étape principale | éval initiale, reprise, proposition de mutation, gate de strate, screening, palier de racing, éval complète, validation, compaction |
| ⏳ `progress` | battement de cœur intra-étape (`notify_heartbeat_seconds`, 15 min) | « attribution Shapley (init, jeu screen) · 124/253 (49 %) · 87 payée(s) · 37 cache · depuis 2 h 10 » + compteurs de passe |
| 🔁 `iteration` / ⚖️ `verdict` | début et issue de chaque itération | opérateur, bloc ciblé, rationale, T° / verdict, composite, Δ, cause de rejet |
| 🔷 `shapley_done` | fin d'une passe Shapley | coalitions payées vs cache, blocs les plus / moins utiles, durée |
| 📊 `validation` / ✂️ `compaction` | éval de validation, passe de compaction | composite val + compteur d'early stopping / blocs retirés et mots gagnés |

**Pourquoi un singleton** : les couches profondes (`Evaluator`) comptent leurs
appels sans qu'on fasse circuler un objet de plus dans toutes les signatures, et
le tracker survit à la remontée de `EvaluationAborted` — c'est ce qui permet au
message de veille de dire *à quelle étape et à quel point de cette étape* le
quota s'est éteint (le quota s'éteint rarement sur une frontière propre).

**Réglages** (`RunConfig`) : `notify_stages` (étapes), `notify_iterations`
(itérations), `notify_heartbeat_seconds` (0 = pas de battement de cœur),
`notify_min_interval_seconds` (anti-rafale sur les seuls messages d'étape — les
jalons passent toujours). Sans webhook, tout cela reste des compteurs mémoire.

**Cas « process mort » (hors Python)** : une notification in-process ne peut pas
partir si le process est mort. C'est couvert **au niveau systemd** :
`calib.service` porte `OnFailure=calib-notify-fail.service`, qui exécute
`cloud/notify_fail.sh` (un simple `curl` du webhook). C'est le seul chemin qui
survit à un OOM de l'`e2-micro` (1 Go).

**Digest quotidien** (`calibrate digest`, timer `calib-digest.timer`) : lit le
store (itération, meilleur composite, évals payées et mutations acceptées sur
24 h, cooldown en cours — **zéro éval LLM**), fait reformuler le récapitulatif
par **Mistral** (`digest_provider`/`digest_model`, modèle **distinct** du quota
d'éval Gemini → n'entame pas le budget de la campagne), et poste un message. Si
Mistral est indisponible, repli sur un **texte templaté** (chiffres bruts) ; si
le webhook est absent, le digest s'affiche sur stdout.

**Limites assumées** : livraison best-effort (message perdu si VM/Discord hors
ligne — jamais rejoué) ; le webhook est un secret partageable (dans `calib.env`,
`chmod 600`) ; aucun contenu de prompt ni clé n'est envoyé (uniquement des
métriques agrégées). Installation des unités : `cloud/setup_vm.sh` (étape C) et
en-têtes des fichiers `cloud/calib-*.service` / `.timer`.

---

## Voir aussi

- `docs/tickets/ticket_004_prompt_calibration_industrialisation.md` — plan d'industrialisation
- `docs/arch/llm-inference.md` — pipeline d'inférence LLM
- `scripts/data/population/cerema_values.yaml` — référence EMC² 2023
