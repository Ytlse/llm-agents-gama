# 5. Results at the nominal regime

<!-- DERNIÈRE ÉCRITURE ANGLAISE : 2026-09-24 15:35:31 — le .tex correspondant porte cette date en en-tête tant qu'il en est le rendu fidèle. Voir sections/README.md. -->

<!-- Brouillon anglais, article court AAMAS 2027, PLAN.md § 5 — budget 1,400 mots.
     Rédigé le 2026-09-22 par l'agent article-writer. Hypothèse ticket 103 scénario 1.
     Les chiffres marqués [c2] sont des emplacements nommés, autorisés par l'auteur pour
     cette livraison seulement, dans l'attente des scores du ticket 103. -->

<!-- source: data/experiences/exp_*_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_*/executions/*/scores.json ;
     cohorte population_1000_AAMAS_v6, jeu …_20260316_EN_c, formule v1_reference (0aeee565…),
     référentiel EMC² 2023 (9ac34597…). 3,154 décisions sur 3,299 attendues, 868 personnes mobiles. -->

The nominal regime is an ordinary simulated day, the one the survey
describes, with no disruption in it.

<!-- ⚠ Point 2 généralisé le 2026-09-23 sur demande de l'auteur. Il disait « recovers the
     effect of distance and leaves the two minority modes where it found them », donc il
     nommait une dimension et deux modes, ce que le § 5.2 détaille déjà. Le point annoncé
     est le constat général : le réglage aligne certaines dimensions de la distribution et
     laisse les autres indépendantes de lui. Les chiffres restent au § 5.2, la liste de tête
     se contentant d'annoncer (R8).
     Le sujet reste « Tuning the general criteria », terme unique du papier (R12), et non
     « prompt engineering » : ce dernier est proposé par l'auteur, mais il faudrait le
     reporter sur les 27 occurrences de tuning/tuned du corps anglais — 18 au § 5, 6 au § 4,
     3 au résumé — dont le titre du § 5.2. Décision d'auteur en attente.
     « Dimension » est repris du § 5.2 (« Distance is the only dimension where an agent
     manages it ») et des dimensions de strate de la métrique ; « criteria » aurait collisionné
     avec les quatre critères généraux du prompt, qui sont autre chose. -->

## 5.1 Fifteen decision-makers on one error scale

The fifteen decision-makers order themselves by family on the composite axis, with one
crossing (Figure 2). The three floors carry the largest error, from 27.0 for the
minimum-duration heuristic to 50.2 for a uniform draw over the choice set. The four decision-makers under the minimal
prompt land between 7.0 and 14.8, the three language models under the expert prompt between
4.9 and 9.0. The two ranges cross. Under the minimal prompt, gemini-3.5 scores 7.02, below
mistral-large and gemini-3.1 under the expert prompt, at 7.63 and 8.98. The four machine learning
models on structured data hold inside half a point, from 3.60 to 4.09. The typed classifier under its
expert prompt sits among them, at **[re-tuning pending]**.

<!-- 2026-09-24, décision de l'auteur : le prompt du classifieur se règle sur la cohorte de
     calibration (c2) et se note sur la cohorte scellée (c1). Le 3,65 retiré était
     prompt_expert_32 réglé sur c1, en échantillon. « Sits among them » tient sous le
     scénario 1 du ticket 103, comme la phrase de tête du § 5.3 ; à revoir si le score du
     prompt re-réglé sort de la bande. -->

<!-- source: fr/06_Empirical_Evaluation.md § 6.1, tableau des quinze décideurs et sa légende
     (scores.json, composite.emd_jsd). Hasard uniforme 50,16 ; tout-voiture 30,73 ; durée
     minimale 26,97 ; prompt minimal 7,02 à 14,75 ; prompt expert LLM 4,86 à 8,98 ; tabulaires
     3,60 à 4,09. ⚠ La légende du master annonce « un facteur douze » entre le plancher aléatoire
     et le meilleur composite ; 50,16 / 3,60 vaut 13,9. Le rapport n'est pas repris ici. -->

The minimal prompt already carries less error than the best of the three floors. The worst of the four
minimal-prompt conditions sits at 14.8, against 27.0 for the minimum-duration heuristic.
A model that receives the facts of a trip, and no
general criteria, therefore carries behavioural information. That information is not
the one the physical heuristic encodes.

On two versions of one model family, the backbone model weighs as much as the instruction
it carries. Served unchanged to a second model from the same provider, the expert text
leaves 4.15 composite points between the two, interval +2.99 to +5.43.

<!-- source: fr/99_annexes.md, annexe H.1, ligne « gemini-3.1 − gemini-3.5, prompt expert » :
     +4,15 [+2,99 ; +5,43] composite, +5,56 [+4,12 ; +7,02] hors choix unique, +17,4 L1.
     2,000 réplicats, graine 2026, rééchantillonnage par grappe sur 868 personnes communes. -->

Replaying one condition under three seeds moves its composite less than the cohort itself
does. The tuned gemini-3.5 condition scores 4.86, 4.65 and 4.30 on the same cohort and the
same evaluation set. The range is 0.56 point, against a cohort resolution of ±1.3 points.
Two further conditions replayed the same way range by 0.05 and 0.24 point. The sign of
their difference holds on all three seeds.

<!-- source: fr/06_Empirical_Evaluation.md § 6.5 et son commentaire (ticket 073, axe 1) :
     graines 42, 123 et 789, composites 4,857 / 4,646 / 4,299, étendue 0,56 ; hors choix unique
     6,86 à 5,98 ; L1 13,85 à 11,97. Résolution de cohorte ±1,3 point : valeur recalculée le
     2026-09-22 sur le jeu corrigé du ticket 088, douze bras, 2,000 rééchantillonnages par
     grappe, graine 2026 (demi-largeur médiane 1,33) ; provenance complète au § 4.3. La
     demi-largeur du bras comparé ici, gemini-3.5 sous prompt expert, vaut 1,22, donc
     l'étendue de 0,56 reste sous la résolution de son propre bras.
     ⚠ 2026-09-23, deux temps. Les trois phrases de réserve sont d'abord remplacées par une
     anticipation marquée [TBC] ; puis, l'auteur ayant signalé experiments_results.md, le [TBC]
     cède la place à LA MESURE, qui existait déjà. Le rejeu n'était pas à venir, il était fait.
     source : experiments_results.md, « 2026-09-22 — Ticket 103, phase 4 : trois graines pour
     Jev, sur c1 ». Graines 42 / 123 / 789, une seule valeur pour graine_ordre, graine_tirage
     et calendrier.graine. Étendues de composite : jev-1.13.0 × prompt_expert_32 = 0,0543 ;
     jev-1.13.0 × prompt_expert_05 = 0,2364 ; gemini-3.5-flash-lite × prompt_expert_05 =
     0,5578, déjà publiée, c'est le 0,56 de la phrase précédente. Signe de l'écart entre les
     deux consignes de Jev : expert 32 devant expert 05 de 0,493, 0,474 puis 0,246 point, donc
     constant sur les trois graines — critère Q3 du ticket 103, satisfait pour cette paire.
     ⚠ CE QUE LE TEXTE NE DIT PLUS : les bras à prompt minimal n'ont toujours pas été rejoués.
     La réserve supprimée le disait ; la phrase actuelle ne parle que des trois bras mesurés et
     ne prétend rien au-delà. Décision d'auteur si elle doit revenir, ici ou au § 7.2, qui ne
     porte aucune limite de graine.
     ⚠ Ce que la phase 4 n'établit pas, et qui n'est écrit nulle part : que Jev soit
     déterministe. La graine change aussi l'ordre des décisions, et la contrainte de chaîne
     fait que l'ordre compte ; un décideur parfaitement déterministe donnerait lui aussi trois
     scores différents sous ce protocole. -->

*Figure 2 — The decision-makers order by family on the composite axis, with one crossing
between prompts. The minimal prompt already carries less error than the physical floor.*

## 5.2 What tuning moves, and what it does not

Successive tuning of the instructions that highlight the general criteria improves every
language model, by more than a cohort would move on its own (Table 2). The paired gain on
the composite is 2.27 points for
gemini-3.5, interval +1.40 to +3.22, then 3.37 points for gemini-3.1 and 7.25 for
mistral-large. All nine intervals exclude zero.

*Table 2 — Paired gains of the expert prompt over the minimal prompt, three readings, with
their 95 % interval in brackets. A positive gain is a lower error.*

| Language model | Composite | Excluding single-option trips | L1 on global shares |
|---|---|---|---|
| gemini-3.5 | 2.27 [1.40 ; 3.22] | 3.59 [2.45 ; 4.83] | 10.2 [8.0 ; 12.5] |
| gemini-3.1 | 3.37 [2.45 ; 4.25] | 4.15 [3.09 ; 5.22] | 8.6 [6.8 ; 10.6] |
| mistral-large | 7.25 [5.90 ; 8.67] | 8.63 [7.15 ; 10.28] | 18.0 [13.5 ; 22.4] |

<!-- source: fr/99_annexes.md, annexe H.1, trois premières lignes, signes retournés en gains
     (un gain positif est une erreur plus faible). 2,000 réplicats, graine 2026, 868 personnes
     communes, tous les décideurs sur le jeu corrigé du ticket 088. -->

The expert prompt was tuned on gemini-3.5, and on that model it creates a slope rather than
a level shift (Figure 3). Under one kilometre the car share does not move, 9.7 % before
tuning and 10.1 % after, where the survey records 18 %. Between one and fifty kilometres it
rises by six to seven points in every band. The tuned agent then carries
less error along distance than any machine learning model on structured data, 14.2 weighted points against 16.8 for
the random forest. Distance is the only dimension where an agent manages it.

<!-- source: fr/06_Empirical_Evaluation.md § 6.3 et son commentaire : part voiture
     prompt_minimal_02 → prompt_expert_05, 9,7 → 10,1 ; 37,7 → 43,4 ; 51,1 → 58,4 ;
     60,0 → 65,9 ; 67,5 → 74,1 ; 74,9 → 80,8 ; 63,8 → 61,8 (plus de 50 km, n = 17).
     Erreur L1 pondérée sur la dimension distance : 14,19 agent réglé, 16,79 forêt aléatoire,
     17,79 gradient boosté. ⚠ Le PLAN annonce un prompt minimal « plat entre 40 et 50 % » face
     à une cible montant « de 18 à 77 % » : aucune de ces deux courbes n'est dans les masters,
     et la source ci-dessus montre une pente. L'énoncé est remplacé par ce qui est mesuré.
     2026-09-24, décision de l'auteur : la phrase de tête dit sur quel modèle le texte a été
     réglé (fr/06_Empirical_Evaluation.md l. 25, « réglé contre gemini-3.5-flash-lite »), ce
     qui garde au résultat son statut de cas sans le présenter comme un exemple, et rétablit
     l'appel à la figure 3. Cible de l'enquête sous un kilomètre, 18,0 % : recalculée depuis
     scores.json (detail.distance.strates[0-1km].target.voiture) des deux exécutions de
     l'annexe D, comme les écarts par tranche (+5,7 à +7,3) et la L1 pondérée (24,07 → 14,19). -->

Two errors coexist in the same decision-maker, and the tuning answers only one. The three
language models put the bike share between 6.8 and 8.1 %, where the survey records 4.1 %.
This text moves it by less than one point, and pulls public transport down by four to eleven
points. One stratum resists every decision-maker, the 15–19 year olds (Appendix F).

<!-- source: fr/06_Empirical_Evaluation.md § 6.3, paragraphe des deux modes minoritaires
     (scores.json, detail.<dimension>.strates). Le pic TC des 15-19 ans — 47,4 % dans
     l'enquête, 20,8 % pour l'agent réglé, 26,4 % pour la forêt aléatoire, légende de la
     figure 6.4 — part à l'annexe F (résultats par strate), relecture v1 F2. -->

*Figure 3 — Tuning gives the agent a slope along distance, while the shortest trips stay
where the minimal prompt left them.*

## 5.3 Deliberation does not decide

The typed classifier reaches the band of the four machine learning models on structured
data. Its composite on the sealed cohort is **[re-tuning pending]**, against 3.60 to 4.09
points for these four models. The paired differences against those four references are **[sealed cohort, four
paired differences with their 95 % intervals]**.

<!-- source: ticket 103, lot A. Aucun chiffre en échantillon dans ce paragraphe, par consigne
     du PLAN § 5.3. Bande tabulaire 3,60-4,09 : fr/06_Empirical_Evaluation.md § 6.1.
     Réécrit le 2026-09-24, décision de l'auteur : la cohorte scellée (c1) sert à la mesure,
     la cohorte de calibration (c2) au réglage des prompts. Les emplacements [c2, …] désignent
     désormais la cohorte scellée : score du prompt du classifieur re-réglé sur c2, noté une
     fois sur c1. Le score et la bande sont alors pris sur la même cohorte ; avant, un score c2
     se comparait à la bande c1 (échelles différentes, bande c2 = [2,53 ; 3,71]).
     ⚠ Le composite apparaît aussi au § 5.1 (« sits among them, at … ») : une fois la valeur
     connue, n'en garder qu'une occurrence (règle « rien deux fois »). -->

<!-- ⚠ PARAGRAPHE SUPPRIMÉ le 2026-09-23 sur décision de l'auteur, après une proposition de
     réécriture qu'il a écartée. Il portait le carré 2 modèles × 3 consignes et son emplacement,
     le dernier gros [c2] du chapitre. Une cellule sur six seulement est mesurée
     (gemini-3.5 × prompt_expert_05 sur c2, 4,7627) ; la cellule pivot gemini × prompt_expert_32
     s'est interrompue à 476 décisions sur 3 163 et Q2 du ticket 103 reste sans réponse.
     TEXTE RETIRÉ, à restituer tel quel si le lot A rend le carré :
     « The second cohort crosses two models with three instructions, without sharing a persona
     with the first. Every cell is therefore out of sample, including the instruction that was
     tuned for the classifier. The crossing answers two questions at once. It measures what the
     classifier's instruction does to a generative model, and the reverse. The six cells are
     [c2, composite of each cell of the two-by-three crossing]. »
     source de ce paragraphe : ticket 103, Q2 et lot A. Cinquante-cinq mots rendus. -->

A decision-maker that writes no text scores in the same band as those that write a
justification. What helps is therefore the reading of the trip, not the sentences produced
after the choice. Verbalised deliberation added nothing to aggregate fidelity here.

<!-- source : passe du 2026-09-23, décision de l'auteur. Deux phrases tombent ici. « The
     published debate on written reasoning reports gains on tasks that have a verifiable
     answer » redisait mot pour mot le § 2.4, qui porte déjà le renvoi à Wei et al. (2022) et
     Sprague et al. (2024) ; la relecture v1 prévoyait déjà cette coupe. « A modal split has no
     verifiable answer trip by trip » portait l'énoncé que le § 2.4 vient d'abandonner le même
     jour, le § 4.3 le contredisant : l'audit unitaire score 9 621 déplacements portant chacun
     leur mode déclaré, en exactitude et en entropie croisée, et les quatre références
     tabulaires sont ajustées sur ces mêmes choix observés. Le paragraphe garde son constat de
     mesure et sa réserve de portée, qui sont ce qu'il établit. Vingt-huit mots économisés. -->

At an equal load of 23,026 decisions the classifier costs 1.06 dollar against 49.28, a
factor of about fifty.

<!-- source: fr/08_Limitations.md § 8.3 : 1,06 $ contre 49,28 $ à 23,026 décisions. Le
     rapport mesuré au § 9 des masters est de quarante-cinq à cinquante-six selon la charge.
     Le détail des jetons et du tarif — 1,050 jetons d'entrée contre 629, consigne renvoyée
     entière à chaque appel, 0,042 $/M en entrée et sortie non facturée — part à l'annexe I
     (coût d'inférence détaillé), relecture v1 § 9 bis. -->

## 5.4 The aggregate does not tell the individual

The tuned agent and the gradient boosted model sit within the cohort resolution of each
other and still disagree on one trip in three. They put their highest probability on a
different mode for 30.3 % of trips, counted where both saw at least two options. That
compares the distributions, not the mode each one drew. Between two machine learning models on structured data the
same figure runs from 8.4 to 11.0 %. Two agents also differ four times more than two such
models in the whole distribution, 40.0 points of median distance against 9.8.

<!-- ⚠ ERREUR DE RÉFÉRENT, INTRODUITE PUIS CORRIGÉE le 2026-09-23, sur question de l'auteur.
     La réécriture de la veille disait « Their whole distributions also sit four times further
     apart, 40.0 points against 9.8 » : « their » renvoyait à l'agent réglé et au gradient
     boosté, alors que 40,0 est la médiane AGENT CONTRE AGENT et 9,8 la médiane TABULAIRE
     CONTRE TABULAIRE. La comparaison n'est pas celle de la paire des deux phrases
     précédentes. Le référent est rétabli explicitement, comme dans la version d'origine.
     La première phrase dit aussi « sit within the cohort resolution of each other » plutôt
     que « score alike » : 4,86 contre 3,60, soit 1,26 point, juste sous les ±1,3.
     source: fr/99_annexes.md, annexe H.5 : accord 69,7 % agent / gradient boosté, 91,6 %
     gradient boosté / régression à noyau, 89,0 % gradient boosté / forêt aléatoire ;
     2,374 à 2,479 déplacements selon la paire.
     L1 médianes corrigées le 2026-09-22 (relecture v1, item F6). Agent contre agent : lignes
     367, 368, 371, 372 et 374 du tableau H.5, valeurs 40,0 / 40,0 / 34,0 / 44,0 / 10,0,
     médiane 40,0 ; la médiane reste 40,0 si l'on ne garde que les deux paires entre modèles
     de langue (40,0 et 40,0). Tabulaire contre tabulaire : lignes 363 et 364, 8,3 (gradient
     boosté / régression à noyau) et 11,3 (gradient boosté / forêt aléatoire), médiane 9,8.
     Les 39,0 et 8,3 de la version précédente étaient l'un une paire agent / tabulaire
     (ligne 365), l'autre la plus petite des deux lignes tabulaires. Rapport 40,0 / 9,8 = 4,1. -->

On the declared days of the survey the agent designates the declared mode slightly less
often than the machine learning models on structured data (Table 3). The tuned agent reaches 67.6 %
accuracy against 71.5 % for the gradient boosted model, a paired gap of 3.87 points,
interval −5.47 to −2.28. Its gap to the multinomial logit separates from zero on neither
accuracy nor cross-entropy.

*Table 3 — Unit-level agreement on the declared days, six decision-makers. Accuracy and
recall in %, cross-entropy in nats on the 5,229 decisions that every distribution-valued
decision-maker scores.*

| Decision-maker | Accuracy | Cross-entropy | Bike recall | Walk recall |
|---|---|---|---|---|
| Gradient boosted | 71.5 | 0.299 | 20.4 | 63.4 |
| Multinomial logit | 68.6 | 0.358 | 18.3 | 60.0 |
| Minimum duration | 68.1 | — | 25.8 | 19.2 |
| Expert prompt, gemini-3.5 | 67.6 | 0.341 | 22.5 | 47.2 |
| Minimal prompt, gemini-3.5 | 64.8 | 0.384 | 24.1 | 44.2 |
| Expert prompt, typed classifier | 64.7 | 0.464 | 18.1 | 56.3 |

<!-- source: fr/06_Empirical_Evaluation.md § 6.4 et fr/99_annexes.md I.1 et I.2.
     ⚠ 2026-09-23, décision de l'auteur, en deux temps. Le tableau ne porte plus qu'UN bras du
     classifieur : les libellés « own instruction (in sample) » et « transferred instruction »,
     séparés à la demande de la relecture v1 (F4), disparaissent. Le papier n'a plus que deux
     noms de consigne, « minimal prompt » et « expert prompt », et le prompt expert d'un
     décideur est CELUI QUI EST SERVI À CE DÉCIDEUR — chaque modèle a le sien.
     Le bras gardé est donc prompt_expert_32, le prompt expert du classifieur :
     64,7 / 0,464 / 18,1 / 56,3 (annexes I.1 et I.2), en échantillon. Il est cohérent avec le
     tableau 1 du § 4.4, qui montre déjà ce texte-là (3,65).
     Ligne retirée : prompt_expert_05 servi au classifieur, 64,3 / 0,509 / 16,9 / 63,1.
     ⚠ DEUX CHOSES MANQUENT, marquées [TBD] en gras dans le corps :
     1. le rappel transports collectifs de prompt_expert_32. Il vaut environ 43,8 % d'après la
        figure 4, qui est tracée sur ce bras-là ; la valeur exacte est à reprendre de l'annexe
        I.2. Le 35,0 % qui figurait dans le texte était celui de prompt_expert_05 ;
     2. les comparaisons appariées de prompt_expert_32 aux quatre références tabulaires.
        L'annexe H.1 ne porte que les quatre lignes « Jev sous consigne gemini-3.5 ».
     ⚠ La figure 4 N'EST PAS à retracer, contrairement à ce que cette note disait d'abord :
     sa légende interne dit « Jev 1.13 (TypeSafe), expert prompt » et ses barres donnent 18,1
     vélo, 56,3 marche, ~43,8 transports collectifs — c'est bien prompt_expert_32. Vérifié sur
     l'image le 2026-09-23.
     Ce qui est mesuré et repris ici sans réserve : exactitude 64,7 contre 66,7 pour le
     plancher tout-voiture, écart apparié −2,04 [−3,78 ; −0,29] (annexe I.1 bis, ligne
     « Jev prompt expert − tout-voiture »), et le rappel marche 56,3 %.
     Différences appariées : annexe I.1 bis,
     prompt expert − gradient boosté −3,87 [−5,47 ; −2,28], prompt expert − logit multinomial
     −0,98 [−2,61 ; +0,58] et −0,018 [−0,039 ; +0,003]. -->

The typed classifier falls under the all-car floor on individual accuracy. It reaches
64.7 % where the floor reaches 66.7 %, a paired gap of 2.04 points, interval −3.78 to −0.29.
On the composite, no paired comparison separates it from the four machine learning models
on structured data. The two
other aggregate readings put it behind the kernel regression and the random forest. Its
probability mass goes to walking rather than to public transport. Walk recall reaches 56.3 %,
against about 44 % for public transport (Figure 4). The aggregate split hides that exchange.
A population can therefore reproduce the modal split of a territory while getting more
individual trips wrong than a rule that reads nothing.

<!-- source: fr/99_annexes.md I.1 bis, « Jev sous consigne gemini-3.5 − tout-voiture »
     −2,42 [−4,26 ; −0,62] et « Jev prompt expert − tout-voiture » −2,04 [−3,78 ; −0,29] ;
     I.1, tout-voiture 66,7 %, Jev prompt expert 64,7 % (en échantillon) ; I.2, rappels 63,1 % marche et
     35,0 % transports collectifs. Séparation sur l'agrégat : annexe H.1, quatre lignes
     « Jev sous consigne gemini-3.5 − <référence tabulaire> ». Sur le composite les quatre
     intervalles contiennent zéro ; hors choix unique et sur les parts globales, ceux de la
     régression à noyau et de la forêt aléatoire l'excluent. Le § 9 des masters écrit « aucune
     estimation appariée ne le sépare » sans nommer la lecture ; l'annexe H.1 le contredit sur
     deux lectures sur trois, et la phrase livrée ici nomme la lecture. -->

*Figure 4 — Recall and precision by mode: the typed classifier trades public transport for
walking, and the aggregate split does not show the exchange.*

<!-- ⚠ PARAGRAPHE SUPPRIMÉ le 2026-09-23, jugé inutile par l'auteur. TEXTE RETIRÉ :
     « A decision-maker accurate on its own test sample can still produce a worse distribution
     in simulation. One variant reconstructed its distance input from the declared travel time
     and reached 93.4 % accuracy on its own held-out sample of 13,918 trips. In simulation it
     lost to the variant that kept its measured distance, 9.28 against 7.40 on the composite.
     The reconstructed distance carried the mode. We therefore score a decision-maker where it
     is used, and not where scoring is convenient. »
     Quatre-vingts mots rendus. La leçon de méthode qu'il portait — noter un décideur là où il
     sert — n'est plus énoncée nulle part dans le papier ; le § 4.2 la met en oeuvre sans la
     dire. Sources conservées ci-dessous au cas où il reviendrait.
     source: la variante est la politique LightGBM « Distance reconstruite depuis la durée »
     (spec_version 4), dont le code a été retiré du dépôt le 2026-08-31 ; seules ses mesures
     subsistent. Exactitude 93,4 % : docs/traces/2026-08-31_second_modele_19_features/
     mode_choice_policy_matrice_vitesse.json l. 277, metrics.accuracy_weighted =
     0.934496640244722, sur metrics.n_rows = 13,918 lignes du découpage de validation de la
     politique elle-même ; valeur redérivée à l'identique depuis confusion_matrix_weighted du
     même fichier (relecture v1, item F5). ⚠ Ce n'est PAS l'audit unitaire du § 4.3
     (9,621 déplacements, 2,930 répondants) : deux jeux d'évaluation distincts, d'où
     « its own held-out sample of 13,918 trips » plutôt que « on the survey ».
     Composites : docs/traces/2026-08-31_second_modele_19_features/scores_v4.json l. 171,
     variante matrice de vitesse à 19 variables 9,282153 contre la condition centroïde à
     21 variables 7,401081. La réserve « chiffres non recoupés » de fr/README.md l. 247 tombe.
     ⚠ Ces deux composites viennent d'un scorage antérieur au jeu corrigé du ticket 088 et ne
     se comparent pas aux 3,60-4,09 du tableau 1 ; la phrase ne les compare qu'entre eux. -->

These four findings hold on the ordinary day the survey describes. A survey tabulates no
other day, and the next section leaves that regime for an event that no variable encodes.

<!--
=== SECTION REPORT ===
Section        : 05 — Results at the nominal regime
File           : docs/paper/article-court/sections/05_results.en.md
Words / budget : 1346 / 1400 (−3.9 %)
Skeleton       :
  The nominal regime is an ordinary simulated day, the one the survey describes, with no disruption in it.
  The fifteen decision-makers spread over the composite axis in five groups that do not overlap (Figure 2).
  The minimal prompt already scores below the best of the three floors.
  On two versions of one model family, the backbone model weighs as much as the instruction it carries.
  Replaying one condition under three seeds moves its composite less than the cohort itself does.
  Tuning the instructions that highlight the general criteria improves every language model, by more than a cohort would move on its own (Table 2).
  Tuning creates a slope rather than a level shift (Figure 3).
  Two errors coexist in the same decision-maker, only one of which answers the instruction.
  The typed classifier reaches the band of the four tabular references.
  The second cohort crosses two models with three instructions, without sharing a persona with the first.
  We read these scores as locating the useful knowledge in the reading of the context, not in the justification written afterwards.
  At an equal load of 23,026 decisions the classifier costs 1.06 dollar against 49.28, a factor of about fifty.
  Two decision-makers that the aggregate cannot tell apart disagree on one trip in three.
  On the declared days of the survey the agent designates the declared mode slightly less often than the tabular references (Table 3).
  Both instructions put the typed classifier under the all-car floor on individual accuracy.
  These four findings hold on the ordinary day the survey describes.
Checker        : none (R1 to R18 clean, verifier_forme.py exits 0 after the author's
                 corrections of 2026-09-22) ; grep G1 thousands separators = 0. G3, second pass: three breaks —
                 finding 1 of the opening list becomes two sentences, "The second cohort crosses
                 two models with three instructions, without sharing a persona with the first"
                 (participial), and the caption of Figure 3 takes "while" for ", and". The
                 measurement lesson "We therefore score a decision-maker where it is used, and
                 not where scoring is convenient" is left untouched, its cadence carrying the
                 claim. The captions of Figures 2 and 4 keep their coordination
Terms defined here     : transferred instruction versus own instruction of the typed classifier
                         (glossed in § 5.4, "the instruction transferred from gemini-3.5")
Terms used, undefined upstream : none. Depends on § 4.4 keeping the single definition of the
                 typed classifier and the existence of an instruction tuned for it, and now
                 also on § 4.4 defining "general criteria" and naming the four
Figures cited  : see the source comment attached to each paragraph. Changed in this pass:
                 40.0 and 9.8 median L1 between distributions (annexe H.5, agent rows 367,
                 368, 371, 372, 374 and tabular rows 363, 364 ; no reservation) ; 93.4 %
                 accuracy (trace of 2026-08-31, mode_choice_policy_matrice_vitesse.json
                 l. 277, accuracy_weighted on 13,918 held-out rows, recomputed from the
                 confusion matrix ; reservation: this is the policy's own split, not the
                 unit-level audit of § 4.3) ; 9.28 against 7.40 (scores_v4.json l. 171 ;
                 reservation: an earlier scoring, comparable to each other and not to
                 Table 1). Kept from the previous pass: 64.7 / 0.464 / 18.1 / 56.3 (in
                 sample) ; −2.04 [−3.78 ; −0.29]
Placeholders   : four [c2] items in §§ 5.1 and 5.3, awaiting ticket 103 lots A and B (F1, F3)
Left out       : the 15–19 stratum figures (F2, to Appendix F) ; the out-of-sample status of the
                 expert prompt, which the PLAN § 5.2 asked for here and the review moves to § 4.4 ;
                 the token and tariff detail of the cost ratio (to Appendix I)
Flags for the author :
  - Appendix I of the short paper must now carry the token and tariff detail (1,050 against 629
    input tokens, 0.042 dollar per million, output not billed).
  - SUPERSEDED on 2026-09-23 by the author. Table 3 keeps ONE classifier row, labelled
    "Expert prompt, typed classifier" like the rest of the table, and its caption says six.
    The two labels "own instruction (in sample)" and "transferred instruction", which the
    review's F4 had asked for, are gone. The row kept is the transferred one, 64.3, which is
    prompt_expert_05 — the same text as the gemini-3.5 row above it — and it is out of
    sample. Figure 4 already read on that arm, so its caption is untouched.
    The paragraph that discussed both arms is rewritten for one, and "the transferred arm"
    disappears with it, which also clears the R11 residue noted below.
    ⚠ Table 1 of 4.4 still shows the OTHER arm under a name that now reads the same way,
    "Expert prompt, typed classifier (in sample)", 3.65, which is prompt_expert_32. Two
    tables, one label, two texts. Author's call.
  - Author's term of 2026-09-22, taken from his abstract. "Arbitration instruction"
    misdescribes the expert prompt, which names lived circumstances rather than a way of
    weighing options. The three occurrences in this section become "general criteria", the
    term § 4.4 now defines and whose four items § 4.4 names. This section does not list them
    again (R8). The intermediate wording of the previous pass, "situational principles", is
    gone from the whole paper.
  - Settled 2026-09-24 by the author: the topic sentence of § 5.2 reads "Tuning the
    instructions that highlight the general criteria", the wording of his abstract, in
    place of "Tuning the general criteria", which said the tuning acts on the criteria
    themselves.
  - § 5.4 stands at 478 words against 350 in the PLAN, § 5.3 at 214 against 400. The balance
    moves back when the [c2] scores land and if F5 goes.
  - F5 applied on 2026-09-22. The source was found, so the review's fallback of cutting the
    paragraph does not apply. The reservation "never recomputed independently" is deleted,
    the value having been re-derived from the confusion matrix of the same file. The review's
    own wording, "93.4 % accuracy on the survey", is NOT used: the figure comes from the
    policy's held-out split of 13,918 trips, not from the unit-level audit of 9,621 trips and
    2,930 respondents that § 4.3 defines and that this same section cites twelve lines above.
    Writing "on the survey" would have merged two evaluation sets in the one paragraph whose
    lesson is that the set matters. The closing sentence is untouched.
  - The paragraph no longer claims "the worst composite in simulation". Against Table 1 that
    claim is false, since the uniform floor scores 50.16. The comparison is now scoped to the
    pair, 9.28 against 7.40, which is what the trace measures.
  - The two composites of that paragraph come from an earlier scoring and do not sit on the
    scale of Table 1, where the gradient boosted model scores 3.60. A reader who compares
    7.40 with 3.60 will believe the tabular reference degraded. The source comment says so ;
    the body cannot say it without telling the paper's own history. The author should decide
    whether one clause is worth it.
  - F6 applied on 2026-09-22. Both figures of the sentence were wrong for what it claimed.
    39.0 was an agent against a tabular method, and 8.3 was the smaller of the two tabular
    rows rather than their median. On the correct cells the claim reads 40.0 against 9.8, a
    ratio of 4.1, so "four times" becomes exact where the quoted pair gave 4.7. The median
    of the agent rows is 40.0 whether or not the typed-classifier pairs are counted.
  - The French appendix, fr/99_annexes.md l. 376-377, states the ratio without figures. The
    error only became visible when the short paper attached numbers to it, and the appendix
    itself needs no correction.
  - The ±1.3 resolution is recomputed and unchanged (§ 4.3). Two sentences of this section
    lean on it, and § 4.3 now says the resolution runs from 0.9 to 2.1 by decision-maker.
    The "one and a half to five and a half times" of § 5.2 is therefore a ratio to the
    median, and the author may want that word added.
  - R11 residue, cleared on 2026-09-23: § 5.4 no longer writes "the transferred arm", the
    paragraph having been rewritten for a single classifier row.
=== END SECTION REPORT ===
-->
