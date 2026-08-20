# Ticket 009 — Calibration par algorithme génétique (population de prompts)

> Statut dans `scripts/dashboard/tickets_status.yaml` (source de vérité). Ci-dessous,
> ce qui est **dans le code**.

**Ce qui est livré** : G1–G3, et G4 (déploiement cloud) — code dans
`prompt_calibration/` (`calibration/genetic.py`, `seeding.py`, `ga_report.py`,
`notify_mail.py`, CLI `calibrate ga --loop`, `config/ga_cloud.yaml`,
`cloud/calib-ga.service`, `cloud/calib-weekly.{service,timer}`), jeu `rank` v2 gelé
(212 décisions / 44 agents — la règle « n ≥ 5 partout » exigerait 406 décisions,
3× le budget §4 : assoupli en « toute strate bien peuplée de screen reste
représentée, n ≥ 2 », cf. `rank_manifest.yaml`). Doc : §2.9 de
`docs/arch/prompt_calibration.md`. G5 (finalisation) attend la fin de campagne.

---

## 0 · L'idée d'origine, et ce que la revue en garde

Idée soumise (chiffres « au pif », à recaler) :

1. **(a)** Initialiser 9 prompts « expert » générés depuis un template (diversité, format de
   sortie obligatoire conservé) + le prompt actuel → population de 10.
   **(b)** Exécuter sur un jeu de test.
2. Garder les 5 meilleurs ; calculer la **valeur de chaque phrase par ablation simple**.
3. Éliminer les 5 pires ; générer 5 nouveaux à partir des conservés, **température haute**.
   Itérer ~2 semaines, sur le cloud (VM à réactiver), **standby quand les quotas sont atteints**.
   À chaque fin d'étape 2 : une **synthèse du meilleur** (inspirée de `docs/synthesis/index.html`)
   + un **compte rendu**.

Verdict de la revue : l'idée est saine — c'est un **(μ+λ) élitiste** classique (μ=5 survivants,
λ=5 enfants), très proche d'EvoPrompt (déjà dans la revue de littérature, §5 de
`docs/arch/prompt_calibration.md`). Elle est **complémentaire** du recuit simulé actuel : le
recuit raffine une trajectoire, la population explore l'espace des structures de prompt.
Quatre corrections s'imposent :

| # | Point de l'idée | Correction | Pourquoi |
|---|---|---|---|
| C1 | « exécuter sur un jeu de **test** » | La sélection ne voit **que des sous-ensembles du train**. `test` reste scellé jusqu'à la finalisation | Sélectionner sur le test détruit le seul chiffre publiable (généralisation). Cf. §2 |
| C2 | « température haute » comme seul moteur de génération | 3 opérateurs de reproduction, dont 2 **informés par l'ablation** ; la température haute est un opérateur parmi d'autres | La T° seule produit surtout du bruit de forme (format cassé, règles à seuil chiffré) ; l'information d'ablation qu'on paie à l'étape 2 doit **servir** à l'étape 3 |
| C3 | population 10, éval pleine à chaque génération | Évaluation **étagée** (jeu `rank` ⊂ `screen` ⊂ `train`) | Une éval train v2 complète ≈ 440 appels ≈ 1 jour de quota free tier. Population×train = 10 jours/génération : infaisable. Cf. §4 |
| C4 | « on itère 2 semaines » | Critère d'arrêt = budget **ou** stagnation (3 générations sans amélioration confirmée), premier atteint | 2 semaines est un budget, pas un objectif ; s'arrêter dès que ça n'avance plus économise le quota pour la finalisation |

## 1 · Ce qui est conservé de la version actuelle (consigne explicite)

Le génétique est un **orchestrateur de plus** (`calibration/genetic.py`, au même rang
qu'`islands.py`), pas une réécriture. Il consomme la machinerie existante telle quelle :

- **Scoring inchangé** : loss `emd_jsd` (EMD ordinal + JSD nominal), comptage **pondéré**
  (masse de probabilité, `policy=weighted`), poids de dimensions actuels, `eval_params_key()`
  et régime de mesure unique — modèle d'éval **épinglé** toute la campagne
  (`gemini-3.1-flash-lite-preview`, temp min, `prod_option_handling: true`). Ne jamais changer
  de modèle en cours de campagne (invalide les évals et le cache).
- **Store SQLite / DAG content-addressed** : chaque individu = un nœud ; chaque
  génération = des arêtes de mutation (`ga_init` / `ga_cross` / `ga_mutate`). Dédoublonnage
  gratuit (deux enfants identiques = un seul nœud), reprise exacte, évals jamais repayées.
- **Défenses d'éval (A10)** : comparaison demandé/reçu, re-tir par moitiés, garde de
  couverture (`eval_min_coverage`), `--batch 8`.
- **Acceptation statistique** : bootstrap apparié sur les agents (`stats.bootstrap_delta`)
  pour départager les individus proches au moment de la coupe (cf. §3.2).
- **Ablation par omission** (`attribution_method: omission`, N+1 coalitions) — c'est
  exactement « la valeur de chaque phrase » de l'étape 2 : le découpage existant fait déjà
  **1 phrase = 1 bloc** (`blocks.py`), et les coalitions passent par le cache.
- **Garde-fous de génération** : `find_numeric_threshold` (aucune règle à seuil chiffré),
  décomposition/validation des blocs, blocs `json_schema` verrouillés réattachés en code
  (⇒ le **format de sortie obligatoire est garanti par construction**, pas par consigne),
  tabu contre la resoumission de textes déjà rejetés.
- **Bandit UCB1** (`bandit.py`) : recyclé pour choisir l'**opérateur de reproduction**
  (récompense = l'enfant survit à la sélection suivante).
- **Infra cloud** : daemon `--loop`, cooldown persisté (reprise à minuit Pacific sur quota
  journalier), systemd `calib.service`, notifications Discord (`notify.py`, `progress.py`),
  dashboard Streamlit (les individus sont des nœuds ordinaires : Timeline/DAG/Comparaison
  fonctionnent sans modification).
- **Finalisation** (`publish.py`) : éval test unique, bilan avant/après, publication
  explicite dans `prompts.yaml`.

Le recuit simulé n'est **pas supprimé** : les deux orchestrateurs partagent le store, et une
campagne future peut enchaîner génétique (exploration) → recuit (raffinage du champion).

## 2 · Discipline scientifique des jeux (consigne explicite)

Jeux gelés **v2** (météo tirée dans l'année climatique — décision D2 du ticket 008),
découpage **par personne** (`sha256(agent_id) % 100` : train [0,70), val [70,85),
test [85,100), intersections vides vérifiées par `dataset_profile`) :

| Jeu | Records v2 | Rôle dans le génétique | Qui le voit |
|---|---|---|---|
| `rank` *(nouveau)* | ~120 | Classement générationnel des individus + coalitions d'ablation | La sélection, à chaque génération |
| `screen` | 569 | **Confirmation** du champion et du challenger de la génération | La sélection, 2 individus/génération |
| `train` | 3 024 | Éval pleine du champion final avant finalisation (optionnelle) | Une fois en fin de campagne |
| `val` | 634 | Early stopping : le meilleur confirmé est évalué toutes les 2 générations ; 3 mesures sans amélioration → arrêt | Le critère d'arrêt uniquement — **jamais la sélection** |
| `test` | 628 | **Une seule éval** du champion + de la graine, à la finalisation. Chiffre publiable | Personne pendant la campagne |

- **`rank` ⊂ `screen` ⊂ `train`** (emboîtement strict) : aucune fuite — toute pression de
  sélection ne voit que des personas du train. (Chaque jeu garde son label d'éval propre :
  l'emboîtement garantit l'étanchéité des splits, pas un partage de cache inter-jeux.)
- Construction de `rank` : même recette que le `common_set` de la page de synthèse —
  échantillonnage **par personne**, espace de hachage **dédié** (`sha256("ga_rank_v2:" +
  agent_id) % 1000 < seuil`), seuil choisi par la **couverture** (toutes les strates Cerema
  présentes dans `screen` doivent garder `n ≥ 5`), gel strict + `manifest.yaml`.
- **Ce que 120 personas permettent** : classer 10 individus dont les composites diffèrent de
  plusieurs points ; pas de départager deux individus à < ~2 points (l'IC bootstrap
  chevauche 0). C'est assumé : la pression de sélection d'un AG tolère ce bruit au milieu du
  classement ; ce qui doit être fiable — le sort du **meilleur** — est confirmé sur `screen`
  (§3.2), et l'élitisme (§3.4) interdit de perdre le champion sur une mesure bruitée.
- Les **témoins d'effectif** existants (`build.resample_composite`, `resample_gain`) sont
  repris tels quels à la finalisation pour lire l'écart train/test sans le confondre avec du
  surapprentissage.

## 3 · L'algorithme, étape par étape

### 3.1 Génération 0 — initialisation diversifiée (9 + 1)

- **1 élite** : le prompt calibré courant (feuille de la meilleure lignée du store).
- **9 variants « expert »** : générés par le **modèle de mutation** (quota **séparé** de
  l'éval — prendre le meilleur flash-lite disponible en free tier, ex. `gemini-3.6-flash-lite`
  s'il existe avec du quota : le modèle de mutation **n'entre pas dans le régime de mesure**,
  seul le modèle d'éval est épinglé ; les mutations sont persistées puis rejouées du store,
  donc changer de modèle de mutation en cours de campagne est sans danger), température ~1.0,
  un appel par variant. La diversité est **pilotée** par un **axe imposé par appel**, pas
  espérée de la seule température. Les blocs `json_schema` sont réattachés en code → format
  de sortie garanti par construction.

  **Le template de seeding** (concret — même contrat strict que le crossover existant,
  `_CROSSOVER_SYSTEM` dans `mutation.py` : mêmes « Contraintes absolues », même forme de
  réponse que `{"merged_prompt": …}`) :

  ```
  SYSTÈME (température ~1.0)
  Tu es un expert en calibration de prompts pour des agents LLM simulant des
  comportements de déplacement urbain à Toulouse.

  Ton rôle : RÉÉCRIRE intégralement le prompt système de référence ci-dessous
  selon l'AXE imposé, sans changer sa mission (le persona répartit 100 points de
  probabilité entre les options d'itinéraire proposées).

  Contraintes absolues :
  - N'introduis JAMAIS de pourcentages, de fréquences ou de parts modales explicites.
  - N'introduis JAMAIS de règle à seuil chiffré ni de table distance→mode. Le choix
    reste un raisonnement comportemental contextuel.
  - Ne réécris PAS le schéma JSON (il sera réattaché automatiquement) : ne produis
    que le corps du prompt système.
  - Une consigne par phrase, longueur totale ≤ {max_mots} mots.

  Tu réponds UNIQUEMENT avec un objet JSON valide, sans markdown ni texte
  supplémentaire : {"seeded_prompt": "<corps du prompt système, sans le schéma
  JSON>", "intention": "<1 phrase : ce que cet axe change>"}

  UTILISATEUR
  PROMPT DE RÉFÉRENCE :
  {prompt_expert_sans_schema}
  AXE IMPOSÉ : {axe}
  ```

  La réponse suit le chemin du crossover : `seeded_prompt` est **décomposé en code**
  (`decompose_prompt` — le « 1 phrase = 1 bloc » est appliqué par le découpeur, jamais
  demandé au modèle), les blocs verrouillés sont réattachés, puis validation avant toute
  éval (`find_numeric_threshold`, longueur, dédoublonnage par hash). `intention` est
  persistée comme `rationale` de l'arête `ga_init` (visible Timeline/DAG et rapport).

  Les 9 axes (1 par variant) : **identification** (raisonner à la première personne du
  persona) ; **arbitrage explicite** coût / temps / confort ; **habitudes & inertie** (le
  mode d'hier) ; **météo & saison** en premier filtre ; **contraintes de chaîne**
  (accompagnement, courses, véhicule déjà engagé) ; **socio-économique** (revenu, coût,
  abonnements) ; **lentilles démographiques** (âge, genre, occupation) ; **minimaliste**
  (le moins de consignes possible) ; **enquêteur** (produire une répartition plausible à
  l'échelle d'une population, sans aucun chiffre).
- **Validation avant toute éval** : `decompose_prompt` réussit, `find_numeric_threshold`
  vide, longueur bornée, dédoublonnage par hash. Un variant invalide est régénéré (3 essais
  max, sinon la population démarre à N−1 — jamais bloquée).
- `pareto.diversified_seeds` (farthest-point sur le front existant) peut fournir 1-2 graines
  supplémentaires issues des campagnes passées — gratuit, le store les connaît déjà.

### 3.2 Évaluation & sélection (étape 1b + coupe de l'étape 3)

1. Chaque individu **nouveau** est évalué sur `rank` (les survivants ont déjà leur éval :
   cache). Classement par composite.
2. **Coupe** : les 5 meilleurs survivent. Aux positions frontières (4-5-6), si l'IC bootstrap
   du Δ chevauche 0 **et** Δ < `racing_min_gap`, égalité → départage déterministe : d'abord
   l'ancienneté (stabilité), puis le **moins de mots** (sert l'objectif de compaction).
3. **Confirmation** : le meilleur au classement `rank` et son challenger sont évalués sur
   `screen` (cache s'ils y sont déjà passés). C'est le composite `screen` qui définit le
   **champion** de la génération — celui du rapport, de l'early stopping et de l'élitisme.

### 3.3 Ablation des survivants (étape 2)

Pour chaque survivant **entrant** (pas encore ablaté — les anciens ont leur carte en cache) :
omission N+1 sur `rank` (~11 blocs mutables → 12 coalitions). Produit la **carte de valeur
par phrase** : Δ composite du retrait, détail par dimension et par mode (machinerie
`ablations` existante, `method='omission'`). Cette carte a trois consommateurs : la
reproduction (§3.4), le rapport de génération (§5), la passe de compaction finale.

### 3.4 Reproduction (étape 3) — 5 enfants, 3 opérateurs

**Élitisme strict** : le champion confirmé est copié tel quel dans la génération suivante
(il compte dans les 5 survivants ; on ne peut jamais régresser).

Les 5 enfants sont produits par 3 opérateurs, choisis par le **bandit UCB1** (récompense :
l'enfant survit à la coupe suivante) :

| Opérateur | Mécanisme | Réutilise |
|---|---|---|
| `ga_cross` — croisement informé | Deux parents **complémentaires** (dimensions fortes disjointes, via le front de Pareto) ; le mutateur fusionne en privilégiant les blocs à **forte valeur d'ablation** de chacun et en écartant les blocs nuisibles (φ < 0 des deux cartes fournies dans le contexte) | `complementary_pair`, `propose_crossover`, cartes §3.3 |
| `ga_cross_greedy` — croisement déterministe | **Sans LLM** : l'enfant est assemblé bloc à bloc en prenant, à chaque position sémantique, le bloc au meilleur φ des deux parents. Coût mutateur nul ; sert de **témoin** au croisement LLM (le bandit mesure lequel produit des survivants) | cartes §3.3, `blocks_to_prompt` |
| `ga_mutate` — mutation ciblée | Un parent tiré parmi les survivants ; cible = son **pire bloc** (argmax nocivité/désalignement) ; réécriture guidée par les pires strates | `select_target` (targeting.py), opérateurs de `mutation.py` |
| `ga_explore` — exploration **dirigée** | Un parent + un **levier comportemental absent** du prompt (tiré d'un catalogue : sécurité perçue, normes sociales, fatigue, fiabilité horaire, charge mentale, image de soi…, filtré contre le contenu des blocs existants) ; consigne = **insérer/développer ce levier**, température ~1.0. La T° haute seule ne produit que des variations de surface (paraphrase, réordonnancement) : l'originalité vient du levier imposé, la T° ne fait qu'élargir la formulation | `propose_candidates`, bibliothèque de snippets |

**Anti-doublon intra-prompt (risque propre au croisement)** : fusionner deux parents peut
produire deux phrases au même contenu (chacun avait sa phrase météo). Trois défenses, dans
l'ordre : (1) **avant éval**, similarité cosinus entre paires de blocs de l'enfant
(`hash_embedding`, la machinerie du tabu) — une paire > seuil déclenche une passe `condense`
sur les deux blocs, et à défaut le rejet `invalid` (zéro éval payée) ; (2) le verdict
`rejected_dup_block` existant couvre la mutation qui recrée une cible déjà couverte ;
(3) en dernier ressort, l'ablation attribue φ ≈ 0 au doublon survivant et la **compaction**
finale le retire — mais c'est le filet, pas la défense (il coûte des évals).

Tous les enfants passent les mêmes garde-fous que la génération 0 (+ tabu : un enfant
quasi-identique à un individu déjà éliminé est rejeté sans éval, `rejected_tabu`). La
bibliothèque de **snippets** (arguments capitalisés des campagnes passées) est fournie au
mutateur comme matériau, comme aujourd'hui.

**Profils ordinaux reconstruits pour le parent muté (emprunt à la page de synthèse).**
La loss v2 mesure sur `age` et `distance` une **EMD**, c'est-à-dire une *forme* de profil —
or le contexte actuel du mutateur ne montre que des écarts ponctuels (top 10 strate × mode) :
il raisonne en L1 sur une loss qui juge en EMD. On reconstruit donc, **depuis les décisions
stockées du parent** (zéro appel LLM, exactement comme les petits multiples de
`docs/synthesis/index.html`), le profil du mode ciblé le long de l'axe ordinal le plus
dégradé, rendu en table texte compacte observé vs EMC² :

```
Profil vélo × âge (part du mode dans la tranche, % — LLM / EMC²) :
15-24: 12/6 · 25-34: 14/8 · 35-49: 9/7 · 50-64: 3/5 · 65+: 0/3
→ le vélo est concentré sur les 15-34 ans et disparaît après 50 ; l'enquête
  l'étale jusqu'aux 65+.
```

**Sélectif, pas exhaustif** : uniquement le mode et l'axe visés par le levier du tour
(étage B du chemin décomposé ; section unique sur le chemin monolithique), pour respecter
la décision d'allègement du contexte mutateur (note du 2026-07-21 — le contexte a été
délibérément dégraissé, on n'y remet pas un dashboard). L'option « joindre les graphiques
en image » (les modèles Gemini sont multimodaux) est écartée : une table texte est plus
fiable pour le raisonnement, moins chère, et ne dépend pas du support image des
adaptateurs provider.

### 3.5 Diversité : le garde-fou anti-convergence prématurée

Avec 10 individus et une troncature élitiste à 50 %, le mode d'échec classique d'un AG est
la **convergence prématurée** : au bout de 3-4 générations, les 5 survivants sont des
quasi-clones du champion et la population n'explore plus rien. Le tabu ne protège pas de
ça (il ne compare qu'aux **éliminés**). Deux mécanismes, tous deux **à coût LLM nul**
(embeddings locaux) :

- **Crowding à la coupe** : au moment de retenir les 5 survivants, si deux d'entre eux ont
  une similarité cosinus > `ga_crowding_threshold` (~0.92), on garde le meilleur des deux
  et on **promeut le premier individu distinct** du classement. La coupe sélectionne donc
  « les 5 meilleurs *représentants distincts* », pas les 5 meilleurs scores bruts.
- **Immigrant aléatoire** : si la diversité moyenne de la population passe sous un seuil
  (`ga_min_diversity`), un des 5 enfants de la génération est remplacé par un **variant
  frais** de la génération 0 (nouveau tirage d'axe, template §3.1). Coût : 1 éval `rank`
  (~18 appels) — l'assurance-exploration la moins chère du système.

### 3.6 Boucle et arrêt

```
gen 0 : init (9+1) ──► éval rank ──► top 5 ──► ablation ──► RAPPORT ──► 5 enfants
gen n : éval rank (nouveaux) ──► coupe (bootstrap aux frontières) ──► confirmation screen
        ──► ablation (entrants) ──► RAPPORT + compte rendu ──► reproduction ──► gen n+1
arrêt : budget épuisé (~2 semaines free tier) OU val sans amélioration 3 mesures
        ──► [option] éval train pleine du champion ──► finalize (éval test unique, bilan,
            publication dry-run → --write --activate à la main)
```

## 4 · Budget quota (v2, batch 8, retries +16 %, free tier 500 RPD/clé)

Coûts unitaires d'une éval : `rank` ~18 appels · `screen` ~82 · `val` ~92 · `train` ~440 ·
`test` ~91. Coalition d'ablation = 1 éval `rank` (~18).

| Poste | Détail | Appels |
|---|---|---|
| **Génération 0** | 10 évals `rank` (180) + ablation 5 survivants (5 × 12 × 18 = 1 080) + confirmation 2 × `screen` (164) | **≈ 1 420** (~3 j) |
| **Génération courante** | 5 enfants × `rank` (90) + ablation ~2 entrants (432) + confirmation (0–164, cache sinon) + `val`/2 gén. (46) | **≈ 570–730** (~1,3 j) |
| **Finalisation** | `test` × 2 (champion + graine) + option `train` plein champion | **≈ 620** |
| **Total 2 semaines** | gen 0 + ~9 générations + finalisation | **≈ 7 000 ≈ 14 × 500 RPD** ✓ |

- La **génération d'enfants** (9 + ≤5/gén. appels mutateur) vit sur le quota du **modèle
  de mutation** (clé 2, flash-lite le plus récent disponible) : n'entame pas le budget
  d'éval.
- **Leviers d'accélération** : passer l'API en payant (~quelques $ la campagne, terminée en
  heures) ; le nombre de générations passe alors de ~10 à ce que le stall autorise.
- L'ablation étant le poste dominant, `ga_ablate_top` (défaut 5) peut être abaissé à 3
  (seuls les parents probables ont besoin d'une carte) : ~−40 % sur le poste.

## 5 · Rapport de génération (fin d'étape 2, à chaque génération)

Deux livrables, **zéro appel LLM d'éval** (tout est recalculé des décisions brutes du store,
comme la page de synthèse) :

1. **Synthèse HTML autonome** — `calibration_results/ga_reports/gen_NN.html`, même facture
   que `docs/synthesis/index.html` (SVG inline via `charts.py`, palette modes du projet,
   page auto-portante) :
   - courbe du **meilleur composite confirmé** par génération (la trajectoire de l'AG) ;
   - table de population : composite par dimension, verdict (champion / survivant / éliminé /
     enfant), lignée (parents, opérateur), nombre de mots ;
   - **prompt champion annoté phrase par phrase** : la carte d'ablation en dégradé
     vert/rouge, avec Δ par dimension et modes poussés ;
   - parts modales du champion vs EMC² (global + 5 pires strates) ;
   - encadré budget : appels payés / servis par le cache / quota restant estimé, régime de
     mesure affiché en clair (modèle, politique, version de jeu — exigence D2).
2. **Compte rendu Discord** — nouvel événement `generation_done` (`notify.py`), reformulé
   par Mistral comme le digest existant (repli templaté si indisponible) : n° de génération,
   champion (composite screen, Δ vs génération précédente), entrées/sorties de la
   population, phrase la plus utile / la plus nuisible, budget consommé, prochaine étape.
3. **Envoi par e-mail** — après chaque éval de génération (même point d'accrochage que le
   rapport), `gen_NN.html` est envoyé à **yves.bru@gmail.com** : nouveau
   `calibration/notify_mail.py`, `smtplib` stdlib en SSL **port 465** via le SMTP Gmail
   (GCP ne bloque en sortie que le port 25 — 465/587 passent depuis l'`e2-micro`).
   Secrets dans `~/calib.env` (`SMTP_USER`, `SMTP_APP_PASSWORD` — **mot de passe
   d'application** Gmail, jamais le mot de passe du compte ; `chmod 600` comme le webhook) ;
   le destinataire est en config (`notify_mail_to`, pas un secret). Même contrat que
   Discord : **best-effort**, échec avalé, jamais bloquant pour la campagne ; corps = le
   compte rendu templaté, pièce jointe = le HTML autonome. **Anti-spam** : un seul mail
   par génération, jamais de mail de heartbeat ; si le daemon dort sur quota > 24 h, c'est
   le digest quotidien existant qui le signale (option `digest_mail: true` pour le recevoir
   aussi par mail).

## 6 · Exécution cloud (VM à réactiver)

Réutilisation intégrale de `cloud/` : `setup_vm.sh`, `calib.service` (pointé sur
`calibrate ga --config config/ga_cloud.yaml --loop`), `calib-digest.timer`,
`notify_fail.sh`. Le **standby quota** est l'existant : coupe-circuit
`eval_max_consecutive_errors` → `EvaluationAborted` → cooldown persisté (minuit Pacific si
quota journalier) → le daemon dort par tranches et reprend seul. Points d'attention connus
(mémoire projet) : layout `parents[2]`, fichier de clé `~/calib.env` (`chmod 600`,
webhook Discord = secret), User-Agent Discord, cooldown **global** alors que les seaux sont
par clé (effacer la ligne `cooldown` pour basculer de clé). Envoyer les jeux v2 + `rank`
dans un nouveau `data_to_upload.tar.gz`.

## 7 · Architecture code & persistance

```
calibration/genetic.py     # orchestrateur GA (nouveau, ~au rang d'islands.py)
calibration/seeding.py     # génération 0 : variants « expert » pilotés par axe (nouveau)
calibration/ga_report.py   # rendu HTML de génération (nouveau, réutilise charts.py-like)
cli.py                     # sous-commande `calibrate ga` (+ `--loop`)
config/ga_cloud.yaml       # RunConfig + clés ga_*
```

- **État GA persisté** sous la clé réservée `__ga__` du `run_state` (miroir de
  `__islands__`) : n° de génération, hashes de la population, étape courante
  (init / eval / ablation / report / breed). **Reprise exacte** : toute éval est
  content-addressed, tout individu est un nœud — un crash ou un quota en pleine ablation
  reprend à la première coalition non payée.
- Individus visibles au dashboard sans modification (nœuds + arêtes ordinaires,
  branche `ga`) ; une vue « Générations » est un nice-to-have ultérieur.
- Nouvelles clés `RunConfig` (défauts) : `ga_population: 10`, `ga_survivors: 5`,
  `ga_ablate_top: 5`, `ga_rank_dataset: rank`, `ga_seed_temp: 1.0`, `ga_breed_temp: 0.9`,
  `ga_val_every: 2`, `ga_stall_generations: 3`, `ga_max_generations: 0` (0 = budget).

## 8 · Phasage de livraison

| Phase | Contenu | Critère d'acceptation |
|---|---|---|
| **G1** | Jeu `rank` gelé (couverture strates vérifiée, manifest) ; `genetic.py` : gen 0 + éval + coupe + reprise ; CLI `calibrate ga` | Une gen 0 complète tourne en local sur v2, reprenable après kill -9 |
| **G2** | Reproduction (3 opérateurs + bandit + tabu/garde-fous) ; ablation branchée sur les entrants | 3 générations bout à bout, cache d'ablation > 50 % en gen 2+ |
| **G3** | Rapport HTML + `generation_done` Discord | Rapport gen N régénérable hors ligne, identique à l'octet |
| **G4** | VM réactivée, `ga_cloud.yaml`, service systemd, tarball v2 ; campagne 2 semaines | Daemon survit à ≥ 1 cycle quota (pause → reprise) sans intervention |
| **G5** | Finalisation : éval test unique champion + graine, témoins d'effectif, bilan, publication | Chiffre test publié dans le rapport final ; `prompts.yaml` inchangé sans `--write` |

## 9 · Décisions ouvertes (recommandation en gras)

1. **Taille de `rank`** : **~120 personas** (au seuil de couverture des strates) ; monter à
   ~200 si le classement s'avère trop bruité (coût +65 %/génération).
2. **Free tier vs payant** : **démarrer free tier** (~10 générations en 2 semaines) ;
   basculer en payant si la courbe val progresse encore au stall du budget.
3. **`ga_ablate_top`** : **5** (fidèle à l'idée d'origine) ; 3 si le quota devient le goulot.
4. **Enchaînement post-AG** : **recuit simulé court sur le champion** (l'existant), pour
   raffiner localement ce que la population a trouvé structurellement.
5. **Héritage de la carte d'ablation** (option d'économie) : un enfant hérite du φ parental
   pour ses blocs **inchangés** (approximation assumée — le contexte du bloc a changé) et
   ne paie l'ablation exacte que sur ses blocs nouveaux/modifiés : ~2-3 coalitions au lieu
   de 12 par entrant, soit ~−70 % sur le poste dominant du budget. **Recommandé en
   deuxième itération**, une fois la version exacte validée (sinon on ne saura pas si un
   défaut vient de l'AG ou de l'approximation).

## 10 · Taille de population : justification des 10 / 5

Les chiffres « au pif » de l'idée d'origine tiennent, pour des raisons qu'on peut
expliciter :

- **Population 10** : c'est la taille d'EvoPrompt (référence du domaine), et c'est ce que
  le quota autorise — à budget fixe, **plus de générations bat plus d'individus** (la
  sélection a besoin d'itérations pour agir ; 10 × 10 générations explore mieux que
  20 × 5). Descendre à 8 libère ~1 génération de plus ; monter à 15 coûte ~2 générations.
- **μ=5 / λ=5** (troncature 50 %) : pression de sélection standard pour un (μ+λ). Plus
  agressif (μ=3) convergerait trop vite avec si peu d'individus ; plus doux (μ=7) dilue
  le signal d'un classement déjà bruité à 120 personas. Le paramètre **le plus sensible
  n'est pas μ mais la diversité maintenue** — d'où le crowding et l'immigrant (§3.5),
  qui protègent mieux qu'un réglage fin de μ.

## 11 · Mécanismes d'AG non retenus, et pourquoi

| Mécanisme | Retenu ? | Justification |
|---|---|---|
| Sélection par roulette / tournoi | ✗ | À 10 individus avec un fitness bruité (120 personas), la troncature + bootstrap aux frontières est plus robuste ; la roulette sur-échantillonne le bruit. À reconsidérer si la population grossit |
| Fitness sharing / niching | ✓ **allégé** | Version crowding à la coupe (§3.5) — le sharing complet (pénalité continue de similarité dans le fitness) mélangerait deux grandeurs (qualité et diversité) dans le composite, qu'on veut garder pur |
| Random immigrants | ✓ | §3.5, conditionnel au seuil de diversité |
| Croisement positionnel (1-point, uniforme) | ✗ | Les blocs n'ont pas de loci fixes entre deux prompts restructurés ; le croisement est **sémantique** (LLM) ou **greedy par valeur** (`ga_cross_greedy`), les deux mis en concurrence par le bandit |
| Taux de mutation auto-adaptatifs | ~ | Pas de « taux » avec des opérateurs LLM ; l'équivalent est le **bandit UCB1** sur les opérateurs, déjà retenu |
| Îlots / migration | ✗ (phase 1) | Existe déjà (`islands.py`) mais multiplie le budget par k ; à activer (k=2, migration du champion) seulement si passage à l'API payante |
| Multi-objectif NSGA-II | ✗ | Le composite pondéré est la cible métier assumée (cf. `calibrate weights` pour la sensibilité aux poids) ; à 10 individus un front NSGA n'a pas la place d'exister. L'archive de Pareto existante joue déjà le rôle utile : fournir des **parents complémentaires** |
| Hyper-mutation (PromptBreeder : faire évoluer le meta-prompt de mutation) | ✗ (option) | Élégant et sur quota mutation (pas d'éval en plus), mais ajoute un étage de variance difficile à diagnostiquer ; à tenter si les opérateurs plafonnent (le bandit le montrera : récompenses uniformément basses) |
| Générations chevauchantes | ✓ | C'est le (μ+λ) lui-même : les survivants restent en lice avec leurs évals en cache |

## 12 · Revue critique — objections retenues et parades

Issues d'une passe de revue contradictoire (panel multi-profils, 2026-08-02). Seules les
objections qui changent quelque chose sont listées ; le reste (Goodhart « matcher les
marginales ≠ raisonner juste ») est déjà couvert par les garde-fous existants (§2.8.1 de
`docs/arch/prompt_calibration.md`, jeu test scellé).

| Objection | Statut | Parade |
|---|---|---|
| **Classement bruité à 120 personas** : au milieu du peloton, la coupe est proche du tirage au sort | **Assumé + mesuré** | Un AG tolère du bruit de sélection (c'est une forme d'exploration) ; ce qui doit être fiable — le champion — est confirmé sur `screen`. Le rapport de génération publie la **corrélation de rang rank ↔ screen** quand les deux existent : si elle s'effondre, agrandir `rank` (décision §9.1) |
| **φ d'ablation bruité** : sur 120 personas, la plupart des blocs ont \|φ\| dans le bruit — guider le croisement avec serait de l'astrologie | **Corrigé** | Bootstrap sur les coalisions (décisions stockées, zéro LLM) : seuls les φ dont l'IC exclut 0 sont donnés au mutateur comme « utile »/« nuisible » ; les autres sont transmis « indéterminé » (et ne guident rien) |
| **Surapprentissage du jeu `rank`** : la sélection revoit les mêmes 120 personas à chaque génération | **Assumé + surveillé** | C'est le prix du cache (changer de jeu jetterait toutes les évals). Parades : confirmation `screen`, arrêt sur `val`, chiffre final sur `test` ; le rapport trace l'**écart rank − screen du champion par génération** — une dérive croissante est le signal d'alarme |
| **Analyses intermédiaires répétées sur `val`** (inflation du risque de conclure « ça progresse ») | **Assumé** | `val` ne décide que l'arrêt, jamais la sélection ni le chiffre publié ; l'unique éval `test` finale reste le seul verdict |
| **Pas de bras témoin** : impossible d'attribuer le gain à l'AG plutôt qu'au budget d'évals dépensé | **Corrigé** | Le témoin existe déjà : la lignée du recuit simulé, re-mesurée sous le même régime (`calibrate reeval`, évals en cache). Le bilan final compare **gain AG vs gain SA à budget d'éval comparable** |
| **Si une génération s'étale sur 3 jours de quota, silence radio** | **Corrigé** | Le mail n'est envoyé que par génération (anti-spam), mais le **digest quotidien** existant couvre les jours creux (état, cooldown, itération) — option `digest_mail` pour le recevoir aussi par e-mail |

## Voir aussi

- `docs/arch/prompt_calibration.md` — moteur, loss, store, cloud, notifications
- `docs/arch/score-synthesis.md` — page de synthèse, common set, témoins d'effectif
- `docs/tickets/ticket_004_prompt_calibration_industrialisation.md` — industrialisation
- `docs/tickets/ticket_008_run_24h_mesures_synthese.md` — décision D2 (jeux v2)
