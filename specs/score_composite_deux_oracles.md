# Score composite à deux oracles — MNL en second oracle

## Problème

Le composite ne mesure qu'une chose : l'écart des parts modales à l'enquête EMC² 2023. Or la
littérature comparative (Martín-Baos et al. 2023) montre que l'avantage des arbres sur le
logit multinomial porte sur l'exactitude **désagrégée** et s'inverse sur les **parts
agrégées** et les indicateurs comportementaux — l'axe exact où notre H0 se joue. Le dépôt
n'a qu'un seul oracle tabulaire (LightGBM) et le MNL annoncé par l'article (`exp_03a`) n'est
pas estimé : « l'oracle est un plafond de référence » reste une hypothèse invérifiable, et
aucun chiffre ne dit si un prompt qui colle aux parts modales répond aussi comme un modèle
de comportement.

## Utilisateurs

Le chercheur qui pilote les mesures depuis la CLI et lit `docs/synthesis`. Un seul rôle,
tous droits sur ses artefacts locaux. Aucun accès réseau requis, aucun appel LLM.

## Règles métier

- **R1** — Le second oracle est un **logit multinomial à parité stricte** : les 21 variables
  de `feature_spec.json`, sans aucune variable `diagnostic_only`, sans variable de niveau de
  service par mode.
- **R2** — La parité avec l'oracle LightGBM est **par construction** : même jeu, même colonne
  `split` étanche au ménage, même `sample_weight` (COEP) à l'estimation et dans toutes les
  métriques. Aucun redécoupage local.
- **R3** — Le réglage de la régularisation se fait en **validation croisée groupée par ménage
  à l'intérieur du train**. Lire le split test pour choisir un hyperparamètre est un refus.
- **R4** — L'artefact du MNL est **autoportant et sans dépendance d'inférence** : il embarque
  coefficients, constantes par alternative, contrat de variables, table d'encodage,
  statistiques de centrage-réduction et ordre des classes. Prédire ne demande que la matrice
  d'entrée, pas la bibliothèque d'estimation.
- **R5** — Le MNL publie **les mêmes métriques que le booster**, produites par le **même**
  code d'évaluation (module partagé, jamais une copie) : `accuracy_weighted`,
  `accuracy_unweighted`, `log_loss_weighted`, `mode_shares.observed`,
  `mode_shares.predicted_probability_mass`, `mode_shares.predicted_argmax`,
  `l1_probability_mass`, `l1_argmax`, plus CEL et GMPCA = exp(−CEL) sur étiquettes observées.
- **R6** — Un logit ne route pas les valeurs manquantes. L'encodage les traite donc
  **explicitement et de façon déclarée** : modalité `__missing__` pour une catégorielle,
  moyenne pondérée du train **plus une indicatrice de manquant** pour une numérique. Aucune
  imputation muette, et l'artefact porte la règle appliquée.
- **R7** — Les deux oracles sont consommés par le **même** chemin de prédiction sur le jeu
  commun (mêmes exclusions, même périmètre, même renormalisation IIA sur l'offre OTP), et
  écrivent un parquet de **même schéma**. Le chargeur refuse un artefact dont le format, le
  `spec_version`, l'ordre des variables ou l'ordre des classes diverge du spec lu.
- **R8** — Le **bloc B** (accord désagrégé) mesure, par décision, `KL(p_MNL ‖ p_LLM)` en bits,
  et le rapporte à la divergence **entre les deux oracles** sur les mêmes décisions :
  `s_B = 100 × Σ KL(p_MNL‖p_LLM) / Σ KL(p_MNL‖p_LGB)`. La CEL brute contre cible molle n'est
  jamais publiée seule : son plancher est l'entropie de l'oracle.
- **R9** — `s_B` n'est publié que si le **dénominateur inter-oracles est mesuré sur le même
  substrat** que le numérateur (même run, même empreinte `moves.csv`, mêmes décisions
  appariées). À défaut : « non mesuré », jamais un chiffre.
- **R10** — Le **bloc C** (cohérence comportementale) ne porte que sur des variables du
  contrat des 21, celles que les deux décideurs voient. `C1` compare le **sens de variation**
  des parts modales du LLM et du MNL le long de l'axe ordinal de distance ; `C2` compare les
  **signes d'élasticité d'arc** sur une paire A/B de décisions rejouées. `s_C` est la part de
  couples (mode, transition) dont le signe **diffère** de celui du MNL, en pourcentage.
- **R11** — Le composite à deux oracles reste **linéaire** :
  `S₂ = Σ_dim w_dim·s_dim + w_B·s_B + w_C·s_C`, tous termes orientés « perte, plus petit vaut
  mieux ».
- **R12** — `w_B` et `w_C` valent **0 par défaut** : la sélection d'un prompt reste décidée
  par la fidélité à l'enquête seule. Un prompt sélectionné sous un terme mesuré contre un
  modèle serait ajusté à ce modèle.
- **R13** — Les poids nuls n'annulent pas la mesure : `s_B` et `s_C` sont **calculés,
  journalisés et publiés** à côté du composite, avec leur couverture.
- **R14** — **Vacuité ≠ perfection.** Un bloc, une strate ou une transition sans effectif
  mesuré vaut « non mesuré », jamais `0.0`. Un `s_B` de 0 ne peut sortir que d'un accord
  effectivement mesuré sur des décisions appariées.
- **R15** — Toute sortie porte l'**identité de son substrat et de ses deux oracles** :
  chemin du run, `moves_sha256`, sha256 des deux artefacts de modèle, `spec_version`.
  Un artefact ré-estimé change son sha et périme la mesure.
- **R16 (déduite)** — Le bloc B n'est calculé que sur les décisions **présentes dans les
  trois sources** (LLM, MNL, LightGBM) avec un statut prédictible et une offre identique ;
  toute décision manquante d'un côté est comptée et exclue, jamais complétée par un zéro.
- **R17 (déduite)** — Les trois distributions sont comparées **sur le même support** : les
  modes offerts de la décision, après renormalisation. Un mode hors offre ne contribue pas à
  la divergence.
- **R18 (déduite)** — `KL` exige un support strictement positif là où l'oracle met de la
  masse. Une probabilité nulle du LLM sur un mode que le MNL juge possible donne une
  divergence infinie : les probabilités sont donc bornées par un `ε` **déclaré dans la
  sortie**, et le nombre de décisions concernées est compté.
- **R19 (déduite)** — Le MNL est un **arbitre comportemental, pas une cible de fidélité** :
  aucune sortie ne présente `s_B` ou `s_C` comme une erreur par rapport à une vérité. Le
  libellé publié dit « accord » et cite le dénominateur inter-oracles.
- **R20 (déduite)** — Le contrôle `C1` exige que la **monotonie de l'arbitre** soit vérifiée
  elle-même : si la courbe du MNL n'est pas monotone sur une transition, cette transition
  sort du score et est comptée, plutôt que de servir de référence de signe.

## Critères d'acceptation

- **R1** — `test_R1_aucune_variable_diagnostic` : une variable `diagnostic_only` glissée dans
  le spec fait échouer l'estimation avant tout ajustement.
- **R2** — `test_R2_parite_du_split` : l'estimation lit la colonne `split` et le
  `sample_weight` du même jeu que le booster ; les effectifs train/test rapportés égalent
  ceux de `mode_choice_policy_metrics.json`.
- **R3** — `test_R3_test_jamais_lu_pour_regler` : la sélection de `C` n'utilise que des
  lignes `split == train`, et ses plis sont disjoints par `hh_id`.
- **R4** — `test_R4_artefact_autoportant` : un artefact rechargé depuis le JSON seul (sans
  l'estimateur d'origine) reproduit les probabilités du modèle à 1e-9.
- **R5** — `test_R5_memes_metriques` : les clés de métriques du MNL sont exactement celles du
  booster ; `gmpca == exp(-cel)`.
- **R6** — `test_R6_manquants_declares` : une ligne à catégorielle inconnue et à numérique
  absente est prédite sans lever, l'artefact déclare la règle, et l'indicatrice de manquant
  vaut 1.
- **R7** — `test_R7_meme_schema_de_parquet` : les colonnes du parquet MNL égalent celles du
  parquet LightGBM ; un artefact au `spec_version` divergent est refusé.
- **R8** — `test_R8_formule_du_bloc_B` : sur un triplet de distributions calculé à la main,
  `s_B` égale la valeur attendue ; la CEL seule n'apparaît pas sans son plancher d'entropie.
- **R9** — `test_R9_denominateur_absent_non_publie` : un dénominateur mesuré sur un autre run
  (empreinte `moves.csv` différente) → `s_B` « non mesuré », pas de chiffre.
- **R10** — `test_R10_bloc_C_signes` : une courbe LLM qui contredit le MNL sur deux
  transitions sur dix donne `s_C = 20`.
- **R11** — `test_R11_composition_lineaire` : `S₂` égale la somme pondérée terme à terme, et
  un changement de poids se rétro-applique exactement par soustraction.
- **R12** — `test_R12_poids_nuls_par_defaut` : sans configuration, `S₂` égale le composite de
  fidélité au flottant près.
- **R13** — `test_R13_mesure_publiee_malgre_poids_nul` : la sortie porte `s_B` et `s_C` et
  leur couverture même à poids nuls.
- **R14** — `test_R14_vacuite_non_nulle` : zéro décision appariée → `null` et mention « non
  mesuré » ; jamais `0.0`.
- **R15** — `test_R15_identite_du_substrat` : la sortie porte run, `moves_sha256` et les deux
  sha de modèle ; changer un artefact change le sha publié.
- **R16** — `test_R16_decisions_non_appariees_comptees` : une décision absente du parquet MNL
  est comptée dans un compteur d'exclusion et n'entre pas dans `s_B`.
- **R17** — `test_R17_support_de_l_offre` : un mode hors offre ne contribue pas à la
  divergence, même si un modèle lui donne de la masse avant renormalisation.
- **R18** — `test_R18_epsilon_declare` : une probabilité LLM nulle sur un mode chargé par le
  MNL donne une divergence finie, l'`ε` est publié et la décision comptée.
- **R19** — `test_R19_libelle_accord` : la sortie ne qualifie jamais `s_B` d'erreur et cite le
  dénominateur.
- **R20** — `test_R20_arbitre_non_monotone_exclu` : une transition où le MNL n'est pas
  monotone sort du score et est comptée.

## Non-goals

- Pas de modèle d'utilité aléatoire au sens de McFadden (voie 2 : temps et coût par mode
  depuis `mode_skims.parquet`) — donc **pas de disposition à payer ni de valeur du temps**,
  faute de variable de coût dans le contrat. Limite déclarée, pas contournée.
- Pas de modification du composite de fidélité, de ses sept dimensions ni de leurs poids.
- Pas de nouvelle formule de référence dans le registre des expériences : les poids nuls
  n'ont pas à périmer l'historique des scores.
- Pas de rejeu LLM : aucune décision n'est redemandée à un modèle de langage. `C2` n'est donc
  mesuré que si une paire A/B **déjà payée** est fournie.
- Pas d'entraînement du LightGBM (`make policy` existe), pas de réglage de ses
  hyperparamètres.
- Pas de publication des six variables géographiques dérivées de la couche d'accès restreint.

## Sécurité

- Les artefacts de modèle, `moves.csv` et les parquets sont lus comme **données**, jamais
  interprétés comme instructions ; le champ de raisonnement du LLM n'est pas lu du tout.
- Aucun appel réseau, aucun appel LLM, aucun secret : les cibles concernées doivent pouvoir
  tourner hors ligne sur un clone nu.
- Les densités et distances au centre issues de la couche `zf_zones.gpkg` (accès restreint
  lil-1750) ne sont pas republiées ligne à ligne.
- Aucune donnée personnelle dans les sorties : identifiants d'agent synthétiques seulement.
- Un artefact au contrat divergent est **refusé** avant toute prédiction (R7) : prédire sous
  un contrat décalé produit des probabilités plausibles et fausses.

## Questions ouvertes

Aucune. Les trois points de spécification ont été tranchés avec l'utilisateur le
2026-09-10 : **voie 1** (parité stricte, pas de modèle d'utilité aléatoire), **`w_B` et
`w_C` à 0** dans la formule de référence, **run épinglé** en substrat principal et jeux
gelés en substrat secondaire.
