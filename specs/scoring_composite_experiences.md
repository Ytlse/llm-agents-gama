# Scoring composite, formule révisable, décideur LightGBM — plateforme d'expériences

## Problème

Une exécution de la plateforme d'expériences (`llm-agents/experiences`) produit ses parts
modales mais **aucun score composite ni détail par sous-catégorie** — le tableau « Mes
expériences » ne peut donc pas classer les exécutions, et la page de synthèse par genre /
occupation / lieu / âge / motif / distance qui existait dans `docs/synthesis` n'a pas
d'équivalent par exécution. De plus la formule du composite doit pouvoir être révisée sans
rejouer les décisions, et l'on doit distinguer un score obtenu sous une formule qui n'est plus
la référence. Enfin le modèle statistique LightGBM ne peut pas encore être utilisé comme
décideur d'une expérience.

## Utilisateurs

Le chercheur qui pilote les expériences depuis le dashboard (lecture des résultats, édition de
la formule, relance d'une expérience) et depuis la CLI `experiences`. Un seul rôle, tous droits
sur ses propres expériences locales.

## Règles métier

- **R1** — Le composite est calculé par le `Scorer` importé de
  `prompt_calibration/calibration/metrics.py` (via `frames.Scorer`), jamais par une loss
  réécrite dans `experiences`.
- **R2** — La formule pondère **7 dimensions** : `global`, `absent_penalty`, `age`,
  `occupation`, `genre`, `motif`, `distance`. `length_penalty` reste à poids nul et n'entre
  jamais dans le composite d'une expérience.
- **R3** — Une formule porte un `formule_sha256` **canonique** : deux définitions aux mêmes
  poids donnent le même SHA quel que soit l'ordre des clés ou l'écriture des flottants ; un
  poids différent donne un SHA différent.
- **R4** — Le registre des formules déclare **exactement une** formule `reference: true`.
  Zéro ou plusieurs → refus bruyant au chargement.
- **R5** — Le scoring d'une exécution écrit un `scores.json` portant : composite `emd_jsd`
  **et** `l1`, les **scores bruts par dimension** `s[dim]`, le **détail par strate** de chaque
  dimension (`cible`, `obtenu`, `l1`, `emd`, `effectif`), la `couverture`, le `volet`
  (`1` ou `3`), le bloc `formule` (`nom`, `sha256`), et l'empreinte `moves_sha256` du substrat.
  Un champ obligatoire manquant → refus.
- **R6** — Le rejeu d'une formule est **exact et hors-ligne** : le composite recomposé par
  `rescale_composite` depuis les scores bruts stockés égale (au flottant près) le composite
  recalculé de zéro sous la même formule. Aucun appel LLM, aucun réseau.
- **R7** — Le drapeau « formule périmée » est **dérivé à la lecture** en comparant le
  `formule_sha256` stocké au SHA de la formule de référence **courante** ; éditer la formule de
  référence fait basculer toutes les lignes non re-scorées en « périmée » sans les modifier.
- **R8** — Une dimension ou une strate **sans effectif mesuré** n'est jamais rendue comme un
  score parfait (`0.0`) : elle est marquée « non mesuré » et citée à côté du composite
  (vacuité ≠ perfection).
- **R9** — Tout affichage d'un composite (tableau et page) porte sa **couverture** à côté ; un
  résultat partiel n'est jamais présenté ni classé comme complet (RG-3 / EF-76).
- **R10** — « Recalculer toutes les expériences » ne fait **aucun** appel LLM ni réseau et est
  déterministe.
- **R11** — Le décideur modèle emprunte le **même chemin de décision** que le décideur LLM
  (RG-1), avec ou sans simulateur : il rend une trace de même forme (`presentees`,
  `distribution`, `poids`, `retenue`).
- **R12** — La version du modèle LightGBM est **scellée par SHA** dans `empreintes.decideur` :
  relancer avec un autre artefact donne un SHA différent, le même artefact donne le même SHA.
- **R13** — Le décideur modèle traite les cas **non imputables** (OD hors couche de zones,
  offre sans mode prédictible, persona introuvable) comme une **non-décision explicite**,
  comptée et motivée, jamais un repli silencieux vers un mode (RG-2).
- **R14** — Un décideur modèle **refuse de démarrer** si `mode_choice_policy.json` (l'artefact
  épinglé) ou `llm_module/data/zf_zones.gpkg` manque : l'exécution ne commence pas dégradée.
- **R15** — Le rendu suit le décideur : type `modele` → page **volet 3** (avec le SHA du
  modèle) ; tout autre type → page **volet 1**.
- **R16** — Le détail par sous-catégorie inclut `lieu_residence` et `type_logement` en
  **affichage hors composite** (non pondérés), comme dans `docs/synthesis`.
- **R17 (déduite)** — `scores.json` est lié à `moves_sha256` : si le `moves.csv` de l'exécution
  a changé depuis, le score est réputé **périmé** et re-calculé, jamais servi en silence.
- **R18 (déduite)** — Si le moteur de calibration (`prompt_calibration/calibration/metrics.py`)
  est indisponible, aucun `scores.json` n'est produit et le tableau affiche « — » (pas `0`),
  avec un message ; la page se génère sans scores.
- **R19 (déduite)** — Une formule éditée est **validée** avant usage : dimensions dans les 7
  admises, poids numériques ≥ 0, sinon refus au chargement. La formule n'est jamais évaluée
  comme du code.
- **R20 (déduite)** — Toute formule ayant servi de référence reste une **entrée nommée retenue**
  dans le registre, pour que n'importe quel `formule_sha256` estampillé se résolve en poids
  lisibles (sinon un vieux score cite un SHA que plus rien n'explique).
- **R21 (tranchée Q1)** — **Seules les exécutions clôturées** (`etat == terminee`) sont scorées.
  Une exécution partielle ou interrompue n'a pas de `scores.json` et affiche « — » (pas de
  composite), sa couverture restant visible par ailleurs.
- **R22 (tranchée Q2)** — Le re-score après changement de formule est déclenché **uniquement**
  par le bouton global « Recalculer toutes les expériences » ; il n'y a pas de re-score par
  ligne.
- **R23 (tranchée 2026-09-07)** — Le **premier** score d'une exécution ne se demande pas : il
  est calculé **automatiquement à la clôture**, par le runner, dès que l'exécution passe
  `terminee` (R21 vaut ici aussi : une exécution arrêtée n'est pas scorée, même largement
  remplie). Le calcul est hors-ligne (aucun appel LLM ni réseau) et **fail-open** : toute
  panne du scoring laisse l'exécution `terminee` sans `scores.json`, journalise une `[ALARME]`
  nommant l'expérience et l'exécution, et laisse le bouton global comme porte de secours.
  Une exécution qui a produit toutes ses décisions n'est jamais mise en échec par un rendu.

## Critères d'acceptation

- **R1** — `test_R1_composite_vient_du_scorer` : le composite d'une exécution égale au centième
  celui produit par `frames.Scorer` sur la même trame.
- **R2** — `test_R2_length_penalty_hors_composite` : changer le poids `length_penalty` ne change
  pas le composite d'une exécution.
- **R3** — `test_R3_sha_canonique` : deux YAML aux mêmes poids (ordre de clés inversé, `0.5` vs
  `0.50`) → SHA identique ; un poids modifié → SHA différent.
- **R4** — `test_R4_une_seule_reference` : registre à 0 ou 2 `reference:true` → exception au
  chargement.
- **R5** — `test_R5_scores_json_complet` : un `scores.json` amputé d'un champ obligatoire est
  rejeté ; un complet est accepté.
- **R6** — `test_R6_rejeu_exact` : `rescale_composite` depuis les bruts == score frais sous la
  nouvelle formule.
- **R7** — `test_R7_badge_perime_derive` : après édition de la formule de référence, une ligne
  non re-scorée est marquée « périmée » sans que son `scores.json` ait changé.
- **R8** — `test_R8_strate_vide_non_mesuree` : une exécution avec une strate d'effectif nul
  affiche « non mesuré » pour cette strate, jamais `0.0`, et le composite cite la dimension.
- **R9** — `test_R9_couverture_a_cote` : le rendu tableau et la page portent la couverture ; une
  exécution partielle n'est pas classée comme complète.
- **R10** — `test_R10_recalcul_hors_ligne` : le recalcul global ne déclenche aucun appel réseau
  (moniteur d'appels à zéro) et est reproductible.
- **R11** — `test_R11_decideur_modele_meme_trace` : une décision du décideur modèle produit une
  trace validée par `valider_trace`, de même forme qu'une décision LLM.
- **R12** — `test_R12_sha_modele_scelle` : deux artefacts différents → `empreintes.decideur.sha256`
  différents ; artefact identique → SHA identique.
- **R13** — `test_R13_non_decision_comptee` : une décision à OD hors couche est archivée comme
  non-décision motivée, exclue des parts, comptée dans un compteur.
- **R14** — `test_R14_refus_sans_dependance` : construire un décideur modèle sans policy ou sans
  couche de zones lève une erreur claire avant toute décision.
- **R15** — `test_R15_routage_volet` : décideur `modele` → volet 3 ; `passerelle` → volet 1.
- **R16** — `test_R16_lieu_logement_hors_composite` : `lieu_residence` et `type_logement`
  apparaissent dans la page mais ne pèsent pas dans le composite.
- **R17** — `test_R17_substrat_lie_moves` : modifier `moves.csv` marque le score à recalculer.
- **R18** — `test_R18_sans_moteur_pas_de_zero` : sans le module de calibration, aucune ligne
  n'affiche de composite chiffré (« — », pas `0`).
- **R19** — `test_R19_formule_invalide_refusee` : un YAML avec une dimension inconnue ou un poids
  non numérique est refusé.
- **R20** — `test_R20_sha_ancien_resoluble` : un `formule_sha256` d'une ancienne référence se
  résout encore en ses poids via le registre.
- **R21** — `test_R21_partielle_non_scoree` : une exécution `etat != terminee` ne produit pas de
  `scores.json` et affiche « — » dans le tableau.
- **R23** — `test_R23_execution_terminee_scoree_a_la_cloture` : `executer()` laisse un
  `scores.json` et sa page sans qu'aucune commande de scoring soit lancée ;
  `test_R23_fail_open_moteur_absent` et `test_R23_fail_open_erreur_inattendue` : moteur absent
  ou panne quelconque → aucune exception, pas de `scores.json`, état `terminee` conservé,
  `[ALARME]` journalisée. `test_R6_rejeu_dans_un_interprete_vierge` : le rejeu hors-ligne
  aboutit dans un processus qui n'a construit aucun `Scorer`.
- **R22** — `test_R22_rescore_global_seul` : le recalcul n'est offert que globalement ; aucune
  action de re-score n'est attachée à une ligne.

## Non-goals

- Ne pas réimplémenter ni redéfinir la loss (`emd_jsd` / `l1` restent ceux du moteur).
- Ne pas toucher aux scores de `docs/synthesis` (pipeline séparé, run épinglé).
- Pas de poids **par strate** : la révision se fait au niveau des 7 dimensions seulement.
- Pas de scoring parallèle LLM + modèle sur une même exécution : le modèle est un décideur.
- Pas d'entraînement du modèle LightGBM (`make policy` existe déjà).
- Pas de nouvelle logique de comparaison multi-exécutions (EF-73 existe).

## Sécurité

- La formule éditée depuis le dashboard est **validée** (R19) et n'est jamais exécutée comme du
  code ; elle est une configuration humaine versionnée en git — rien du réseau ni d'un LLM n'y
  entre (zero-trust mémoire persistante).
- `moves.csv`, `scores.json` et le champ `reponse_brute` d'un décideur sont lus comme
  **données**, jamais interprétés comme instructions.
- L'artefact modèle chargé est vérifié (format, contrat de features) avant usage ; un artefact
  au contrat divergent est refusé (déjà assuré par `load_policy`).
- Aucun secret ni donnée personnelle dans `scores.json` ni dans la page de synthèse.

## Questions ouvertes

Aucune — les questions ont été tranchées avec l'utilisateur et figées en R21 (seules les
exécutions terminées sont scorées ; les exécutions arrêtées ne sont pas prises en compte),
R22 (re-score par bouton global seul) et R23 (premier score automatique à la clôture,
fail-open).
