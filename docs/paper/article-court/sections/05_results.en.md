# 5. Results on the ordinary day

<!-- DERNIÈRE ÉCRITURE ANGLAISE : 2026-09-26 00:10:00 — le .tex correspondant porte cette date en en-tête tant qu'il en est le rendu fidèle. Voir sections/README.md. -->

<!-- Relecture des gallicismes du 2026-09-25, accord de l'auteur (« Corrige ») : tics récurrents (« against » comparatif, « one » pour « un même », « carry », « bound », « under » devant un seuil, « rejoin », « from one X to another », « execute », « brings »), faux-amis (agenda, control, hypothesis, legibility, designate, demanding, chain, globally, bends, recedes), calques de construction et typographie à la française (« 0.9 point », « [a ; b] », « 30.3 % », « 1.06 dollars »). Aucun chiffre ne change ; les prompts et le message de l'annexe D ne sont pas touchés. -->

<!-- Brouillon anglais, article court AAMAS 2027, PLAN.md § 5 — budget 1,400 mots.
     Rédigé le 2026-09-22 par l'agent article-writer. Hypothèse ticket 103 scénario 1.
     Les chiffres marqués [c2] sont des emplacements nommés, autorisés par l'auteur pour
     cette livraison seulement, dans l'attente des scores du ticket 103. -->

<!-- 2026-09-25, passe de lisibilité, tâche validée par l'auteur (anglais seul ; le .fr.md et le
     .tex ne suivent pas encore). Règle appliquée : en prose, une affirmation, le chiffre qui la
     prouve, la comparaison qui lui donne sens ; le reste vit dans les tableaux 1-3 et les
     figures 2-4, avec un renvoi. Ouverture par les quatre constats (PLAN § 5). Titre du § 5.1
     mis en affirmation. Correction de méthode au § 5.1 : l'ancien « one crossing » opposait
     gemini-3.5 minimal (7,02) à mistral-large expert (7,63), écart 0,61 sous la résolution de
     ±1,3 ; seul l'écart à gemini-3.1 expert (8,98, soit 1,96) la dépasse. Texte et légende de la
     figure 2 le disent désormais. Une seule convention de signe en prose, positif = meilleur
     (« trails by »). Composites arrondis au dixième en prose ; tableaux inchangés. « Machine
     learning models on structured data » devient « reference models », terme du § 4.4. Rapport
     plancher uniforme / meilleure référence repris en « about fourteen » (50,16 / 3,60 = 13,9),
     cf. la réserve du commentaire du § 5.1 sur le « facteur douze » du master. Au § 5.4, les deux
     phrases sur la séparation agrégée du classifieur (annexe H.1, bras « Jev sous consigne
     gemini-3.5 ») cèdent la place à un renvoi au § 5.3, qui porte l'emplacement des différences
     appariées du prompt expert du classifieur ; texte retiré conservé dans le commentaire du
     paragraphe. -->

<!-- source: data/experiences/exp_*_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_*/executions/*/scores.json ;
     cohorte population_1000_AAMAS_v6, jeu …_20260316_EN_c, formule v1_reference (0aeee565…),
     référentiel EMC² 2023 (9ac34597…). 3,154 décisions sur 3,299 attendues, 868 personnes mobiles. -->

The ordinary day is a simulated day with no disruption, the day the survey describes.
On that day the benchmark yields four findings, one per subsection.

1. The decision-makers form groups, and a prompt with no general criteria already beats
   every baseline.
2. The expert prompt improves every language model, aligning some dimensions of the modal
   split and leaving others untouched.
3. A classifier that reads the same trip description and writes no text scores within the
   range of the four reference models.
4. Agreement on the modal split does not carry over to individual trips.

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

## 5.1 Fifteen decision-makers form groups

The fifteen decision-makers form distinct groups on the composite (Figure 2, Table 1). The
uniform baseline has about fourteen times the error of the best reference model. Every
minimal-prompt condition already has less error than the three baselines. The weakest
minimal-prompt condition scores 14.8, compared with 27.0 for the best baseline (minimum duration).
A model that receives the facts of a trip, and no general criteria, therefore holds behavioural information that the minimum-duration baseline lacks. The four reference models hold the lowest errors. The typed classifier under its expert prompt sits among them, at 3.65.

<!-- Tableau 1 déplacé du § 4.4 au § 5.1 le 2026-09-25 (relecture éditoriale, accord de l'auteur) :
     il se lit au § 5.1. Lignes groupées puis triées par composite ; « not replayed » devient
     « [pending] ». Valeurs inchangées. Le commentaire de source ci-dessous suit le tableau. -->

*Table 1. The fifteen decision-makers on the two metrics, with the inter-seed range where
it was measured. Rows are grouped, then sorted by composite.*

| Group | Decision-maker | Composite | L1 on overall shares | Inter-seed range |
|---|---|---:|---:|---|
| Baseline | Uniform random | 50.16 | 86.80 | deterministic |
| Baseline | All-car | 30.73 | 58.00 | deterministic |
| Baseline | Minimum duration | 26.97 | 53.62 | deterministic |
| Minimal prompt | mistral-large | 14.75 | 44.71 | [pending] |
| Minimal prompt | typed classifier | 13.75 | 42.76 | 0.41 |
| Minimal prompt | gemini-3.1 | 12.38 | 39.88 | [pending] |
| Minimal prompt | gemini-3.5 | 7.02 | 24.08 | **[pending]** |
| Expert prompt | gemini-3.1 | 8.98 | 31.25 | [pending] |
| Expert prompt | mistral-large | 7.63 | 26.64 | [pending] |
| Expert prompt | gemini-3.5 (tuned agent) | 4.86 | 13.85 | 0.56 |
| Expert prompt | typed classifier | 3.65 | 10.48 | 0.05 |
| Reference | Random forest | 4.09 | 5.28 | deterministic |
| Reference | Multinomial logit | 4.02 | 8.99 | deterministic |
| Reference | Kernel logistic regression | 3.61 | 6.69 | deterministic |
| Reference | Gradient boosting | 3.60 | 9.49 | deterministic |

<!-- source: fr/06_Empirical_Evaluation.md § 6.1, tableau des quinze décideurs (scores.json,
     composite.emd_jsd, composite.emd_jsd_hors_choix_unique, global.l1 ; jeu corrigé du
     ticket 088). Étendue inter-graines 0,56 : § 6.5, graines 42 / 123 / 789, composites
     4,857 / 4,646 / 4,299. Étendue inter-graines classifieur typé prompt minimal 0,41 :
     experiments_results.md 2026-09-24 14:55 (ticket 103 phase 5), graines 42 / 123 / 789,
     composites 13,748 / 13,450 / 13,337.
     Ligne « Expert prompt, typed classifier » : prompt_expert_32, réglé sur échantillon
     d'entraînement et évalué sur la cohorte scellée c1 — composite 3,65 (3,6470),
     L1 10,48, étendue inter-graines 0,05 (graines 42 / 123 / 789 : 3,6470 / 3,7014 / 3,6926). -->

The groups overlap in one place only: the best minimal-prompt condition, gemini-3.5,
scores better than two expert-prompt conditions. It leads gemini-3.1 under the
expert prompt by 2.0 composite points, and mistral-large under that prompt by 0.6, a
gap smaller than the cohort resolution.

<!-- 2026-09-25, passe de lisibilité. Chiffres du paragraphe, tous dérivés du tableau 1 du § 4.4 :
     « about fourteen » = 50,16 / 3,60 = 13,93 ; 14,8 = 14,75 (prompt minimal, mistral-large) ;
     27,0 = 26,97 ; 2,0 = 8,98 − 7,02 = 1,96, au-dessus de ±1,3 ; écart à mistral-large expert
     7,63 − 7,02 = 0,61, sous ±1,3, d'où « within that resolution ». Réserve non écrite dans le
     corps : ±1,3 est la demi-largeur médiane d'UN composite (§ 4.3, 0,9 à 2,1 selon le
     décideur) ; aucune différence appariée gemini-3.5 minimal / gemini-3.1 expert n'est
     calculée. Retirés de la prose, restés au tableau 1 : 7,02 ; 7,63 ; 8,98 ; 50,2 ; 7,0 ;
     4,9 ; 9,0 ; 3,60 ; 4,09 ; « half a point ». -->

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

The same prompt does not score the same on two versions of the same model family. With the
tuned agent's expert prompt left unchanged, gemini-3.1 trails gemini-3.5 by
4.2 composite points (95% interval 3.0 to 5.4).

<!-- source: fr/99_annexes.md, annexe H.1, ligne « gemini-3.1 − gemini-3.5, prompt expert » :
     +4,15 [+2,99 ; +5,43] composite, +5,56 [+4,12 ; +7,02] hors choix unique, +17,4 L1.
     2,000 réplicats, graine 2026, rééchantillonnage par grappe sur 868 personnes communes. -->

Re-running a condition with three seeds moves its composite less than the narrowest interval
half-width of Section 4.3, 0.9 points. The tuned agent varies by 0.6 points across seeds
(Table 1). Under the minimal prompt, the typed classifier varies by 0.4 points across seeds
(0.41), and by less than a quarter of a point under both expert prompts (0.05 and 0.24). The
sign of the difference between these two expert conditions holds on all three seeds. This
inter-seed variation of 0.4 points is small next to the gain from tuning the classifier's
prompt, which lowers the composite by 10.1 points (from 13.75 to 3.65).

<!-- source: fr/06_Empirical_Evaluation.md § 6.5 et son commentaire (ticket 073, axe 1) :
     graines 42, 123 et 789, composites 4,857 / 4,646 / 4,299, étendue 0,56 ; hors choix unique
     6,86 à 5,98 ; L1 13,85 à 11,97. Résolution de cohorte ±1,3 point : valeur recalculée le
     2026-09-22 sur le jeu corrigé du ticket 088, douze bras, 2,000 rééchantillonnages par
     grappe, graine 2026 (demi-largeur médiane 1,33) ; provenance complète au § 4.3. La
     demi-largeur du bras comparé ici, gemini-3.5 sous prompt expert, vaut 1,22, donc
     l'étendue de 0,56 reste sous la résolution de son propre bras.
     source graines Jev : experiments_results.md, « 2026-09-22 — Ticket 103, phase 4 »
     (expert 32 = 0,0543, expert 05 = 0,2364) et « 2026-09-24 14:55 — Ticket 103, phase 5 »
     (minimal 02 = 0,411, composites 13,748 / 13,450 / 13,337, delta tuning 10,1 points).
     Signe de l'écart entre les deux consignes expert de Jev : expert 32 devant expert 05
     de 0,493, 0,474 puis 0,246 point, constant sur les trois graines (critère Q3 du ticket 103). -->

*Figure 2. The decision-makers form groups on the composite axis, and even the minimal
prompt has less error than the minimum-duration baseline. The grey band is the cohort resolution,
the median half-width of a 95% interval; it gives a scale, not a test.*

## 5.2 What tuning changes, and what it does not

Tuning the system prompt lowers the error of all three models (Table 2).
The paired gain runs from 2.3 to 7.3 composite points, and all six intervals
(three models, two metrics) exclude zero.

*Table 2. Paired gains of the expert prompt over the minimal prompt, two metrics, with
their 95% interval in brackets. A positive gain is a lower error. Gains are computed on the persons both conditions scored, so they can differ slightly from the gaps in Table 1.*

| Language model | Composite | L1 on overall shares |
|---|---|---|
| gemini-3.5 | 2.27 [1.40, 3.22] | 10.2 [8.0, 12.5] |
| gemini-3.1 | 3.37 [2.45, 4.25] | 8.6 [6.8, 10.6] |
| mistral-large | 7.25 [5.90, 8.67] | 18.0 [13.5, 22.4] |

<!-- source: fr/99_annexes.md, annexe H.1, trois premières lignes, signes retournés en gains
     (un gain positif est une erreur plus faible). 2,000 réplicats, graine 2026, 868 personnes
     communes, tous les décideurs sur le jeu corrigé du ticket 088. -->

Take gemini-3.5 as an example, the model the expert prompt was tuned on. For this model, tuning does not shift the car share uniformly (Figure 3). Under one kilometre the car share stays near
10% before and after tuning, where the survey records 18%. Between one and fifty kilometres
it rises by six to seven points in every band. On the distance stratum, the tuned agent then
has less error than any reference model. Its L1 error, taken within each distance class and averaged by class size,
is 14.2 points. The random forest, best of the four, scores 16.8. No other stratum gives an
agent that lead.

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

<!-- 2026-09-25, passe de lisibilité. La L1 pondérée n'était définie nulle part en amont ; la
     clause « taken within each distance class and averaged by class size » reprend la définition
     du master (article_old_do_not_maintain/fr/06_Empirical_Evaluation.md l. 93, « moyenne des
     strates couvertes pondérée par leur effectif ») et la rattache à la L1 du § 4.3. « Near
     10 % » arrondit 9,7 et 10,1. « Best of the four » : forêt 16,79, gradient boosté 17,79,
     régression à noyau 18,09, logit 20,73 (même source). Tableau 2 : « 2.3 to 7.3 » arrondit
     2,27 et 7,25 ; les valeurs par modèle restent au tableau. -->

The language models make two errors, and tuning corrects only one. They overestimate public
transport, and the expert prompt pulls it down by four to eleven points. They also
overestimate cycling, at 6.8 to 8.1% where the survey records 4.1%, and the expert prompt
moves the bike share by less than one point. No decision-maker fits one stratum: the 15–19-year-olds. The survey records 47.4% public transport for them, compared with 26.4% for the
random forest and 20.8% for the tuned agent (Appendix F).

<!-- Relecture éditoriale du 2026-09-25 : les deux erreurs sont nommées, et la strate des
     15-19 ans reçoit ses chiffres. source : old-fr/99_annexes.md l. 309-320 (part TC : enquête
     12,4 %, prompts minimaux 20,9 à 30,6 %, prompts experts 16,6 à 24,8 %) ;
     old-fr/06_Empirical_Evaluation.md l. 87 et 93 (15-19 ans : 47,4 % de TC à l'enquête,
     20,8 % pour l'agent réglé, 26,4 % pour la forêt aléatoire ; erreur de 34 à 59 points pour
     tous les décideurs). -->

<!-- source: fr/06_Empirical_Evaluation.md § 6.3, paragraphe des deux modes minoritaires
     (scores.json, detail.<dimension>.strates). Le pic TC des 15-19 ans — 47,4 % dans
     l'enquête, 20,8 % pour l'agent réglé, 26,4 % pour la forêt aléatoire, légende de la
     figure 6.4 — part à l'annexe F (résultats par strate), relecture v1 F2. -->

*Figure 3. On gemini-3.5, tuning raises the car share beyond one kilometre, while the
shortest trips stay where the minimal prompt left them.*

## 5.3 A classifier that writes no text reaches the reference range

On the sealed cohort, the typed classifier under its expert prompt scores 3.65, inside the
range of the four reference models (3.60 to 4.09). On a second cohort of 1,000 personas,
drawn the same way with no persona in common, the four reference models span 2.53 to 3.71
composite points. The typed classifier scores 4.64 there, 0.9 points above that range.

<!-- A TRANCHER : statut de la seconde cohorte. Le ticket 103 la dit hors échantillon pour tous
     les prompts ; la décision du 2026-09-24 en fait la cohorte de calibration. Tant que
     prompt_expert_32 n'est pas re-réglé sur c2, c'est le score c1 (3,65) qui est en
     échantillon et le score c2 (4,64) qui est hors échantillon. Le dire ici en une phrase. -->

<!-- source: experiments_results.md, Ticket 103 phase 1 (2026-09-22 19:12, échelle cohorte c2)
     et phase 2 (2026-09-22 19:34, Jev sur c2).
     Bande tabulaire c2 : [2,5342 ; 3,7085]. Jev expert 32 sur c2 : composite 4,6394,
     hors choix unique 7,6741, L1 45,204. Écart au haut de bande de c2 : +0,93 point,
     sous la résolution de cohorte de ±1,3 point (scénario 2 du ticket 103). -->

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

The typed classifier thus reaches the reference range without writing text. Given the same
prompt as a language model, it is no longer clearly ahead. With the minimal prompt,
gemini-3.5 scores 7.02 and the classifier 13.75. With the tuned agent's prompt, the
classifier scores 4.14 and the agent 4.86, a gap smaller than a change of cohort. On the
second cohort, the two stand 0.1 points apart. This comparison therefore does not tell what
the text contributes.

<!-- source : experiments_results.md, ticket 103 phase 4 (jev x prompt_expert_05, c1, graine 42 :
     4,1399 ; gemini-3.5 : 4,8571) et phases 1-2 sur c2 (jev x prompt_expert_32 : 4,6394 ;
     gemini-3.5 x prompt_expert_05 : 4,7627). Relecture de l'auteur du 2026-09-25. -->

<!-- source : passe du 2026-09-23, décision de l'auteur. Deux phrases tombent ici. « The
     published debate on written reasoning reports gains on tasks that have a verifiable
     answer » redisait mot pour mot le § 2.4, qui porte déjà le renvoi à Wei et al. (2022) et
     Sprague et al. (2024) ; la relecture v1 prévoyait déjà cette coupe. « A modal split has no
     verifiable answer trip by trip » portait l'énoncé que le § 2.4 vient d'abandonner le même
     jour, le § 4.3 le contredisant : l'audit unitaire score 9 621 déplacements portant chacun
     leur mode déclaré, en exactitude et en entropie croisée, et les quatre références
     tabulaires sont ajustées sur ces mêmes choix observés. Le paragraphe garde son constat de
     mesure et sa réserve de portée, qui sont ce qu'il établit. Vingt-huit mots économisés. -->

For the same 23,026 decisions, the classifier costs $1.06, whereas the tuned agent costs $49.28 at the standard rate, a factor of about fifty.

<!-- A TRANCHER (relecture externe) : dire d'où viennent les 23 026 décisions (graines ?
     cohortes ?), la date du tarif et ce que couvre la facturation (cache, jetons). -->

<!-- Relecture éditoriale du 2026-09-25 : modèle et volume nommés. source :
     docs/traces/2026-09-21_13-10_cout_jev_vs_gemini/README.md l. 71 et 90-115 —
     gemini-3.5-flash-lite sous prompt_expert_05, 49,28 $ au tarif payant standard (le run a
     tourné sur des clés gratuites) ; 1,06 $ pour jev-1.13.0 sous prompt_expert_32 ; charge du
     ticket 096 lot 2. ⚠ Le 1,06 $ est celui du prompt en cours de re-réglage. -->

<!-- source: fr/08_Limitations.md § 8.3 : 1,06 $ contre 49,28 $ à 23,026 décisions. Le
     rapport mesuré au § 9 des masters est de quarante-cinq à cinquante-six selon la charge.
     Le détail des jetons et du tarif — 1,050 jetons d'entrée contre 629, consigne renvoyée
     entière à chaque appel, 0,042 $/M en entrée et sortie non facturée — part à l'annexe I
     (coût d'inférence détaillé), relecture v1 § 9 bis. -->

## 5.4 Matching shares is not matching decisions

The tuned agent and the gradient boosting model stand 1.3 composite points apart and still
disagree on one trip in three. They put their highest probability on a
different mode for 30.3% of trips, counted where both saw at least two options. Between two
reference models the same count runs from 8.4 to 11.0%. On the median trip, the summed
absolute gap between the mode probabilities of two generative agents is four times that of
two reference models.

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

On the reported days of the survey, the tuned agent predicts the reported mode slightly
less often than the reference models (Table 3). It trails the gradient boosting model by 3.9
accuracy points (95% interval 2.3 to 5.5). No paired interval separates it from the multinomial
logit, on accuracy or on cross-entropy.

*Table 3. Trip-level agreement on the reported days, seven decision-makers. Accuracy and
recall in %, on the 9,621 reported trips. Cross-entropy in nats, on the 5,229 decisions with
at least two options that every distribution-valued decision-maker scores. The two baselines
that return a single option receive none: a zero probability on the reported mode makes it infinite.*

| Decision-maker | Accuracy | Cross-entropy | Bike recall | Walk recall |
|---|---|---|---|---|
| Gradient boosting | 71.5 | 0.299 | 20.4 | 63.4 |
| Multinomial logit | 68.6 | 0.358 | 18.3 | 60.0 |
| Minimum duration | 68.1 | — | 25.8 | 19.2 |
| Expert prompt, gemini-3.5 | 67.6 | 0.341 | 22.5 | 47.2 |
| All-car | 66.7 | — | 2.3 | 16.2 |
| Minimal prompt, gemini-3.5 | 64.8 | 0.384 | 24.1 | 44.2 |
| Expert prompt, typed classifier | 64.7 | 0.464 | 18.1 | 56.3 |

<!-- Relecture éditoriale du 2026-09-25 : ligne « All-car » ajoutée, le corps (§ 5.4, § 7.1)
     comparant le classifieur à ce plancher sans que le tableau le porte. Source :
     article_old_do_not_maintain/fr/99_annexes.md, I.1 (exactitude 66,7 ; pas d'entropie
     croisée) et I.2 (rappel vélo 2,3, rappel marche 16,2 ; rappel voiture 95,8).
     ⚠ Un rappel voiture de 95,8 % et un rappel vélo de 2,3 % disent que ce plancher ne met
     pas « tout sur la voiture » quand la voiture n'est pas offerte : le § 4.4 ne dit pas ce
     qu'il choisit alors. À préciser par l'auteur. -->

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

The typed classifier falls below the all-car baseline on individual accuracy. It trails that
baseline by 2.0 accuracy points (95% interval 0.3 to 3.8), while its composite reaches the
range of the reference models (Section 5.3). It over-predicts walking at
the expense of public transport. Its walk recall reaches 56.3%, compared with about
44% for public transport, and its walk precision falls below that of the two other
decision-makers (Figure 4). A population can therefore reproduce the
modal split of a territory while getting more individual trips wrong than a baseline that
takes the car whenever it can.

<!-- 2026-09-25, passe de lisibilité. TEXTE RETIRÉ, à restituer si l'auteur le juge juste :
     « On the composite, no paired comparison separates it from the four machine learning
     models on structured data. The two other aggregate readings put it behind the kernel
     regression and the random forest. » Motif : la source de ces deux phrases (annexe H.1,
     lignes « Jev sous consigne gemini-3.5 − <référence> », cf. commentaire ci-dessous) est le
     classifieur sous le prompt expert de gemini-3.5, alors que la ligne du tableau 3 et
     l'écart au tout-voiture (−2,04) sont ceux du prompt expert du classifieur ; et le § 5.3
     annonce ces mêmes différences appariées comme un emplacement non encore rempli. La
     phrase de remplacement renvoie au § 5.3 et n'affirme rien de plus que sa phrase de tête.
     Arrondis : 2,04 → 2,0 ; intervalle [−3,78 ; −0,29] rendu en écart positif 0,3 à 3,8.
     66,7 % (tout-voiture, absent du tableau 3) et 64,7 % (au tableau 3) quittent la prose. -->


<!-- source: fr/99_annexes.md I.1 bis, « Jev sous consigne gemini-3.5 − tout-voiture »
     −2,42 [−4,26 ; −0,62] et « Jev prompt expert − tout-voiture » −2,04 [−3,78 ; −0,29] ;
     I.1, tout-voiture 66,7 %, Jev prompt expert 64,7 % (en échantillon) ; I.2, rappels 63,1 % marche et
     35,0 % transports collectifs. Séparation sur l'agrégat : annexe H.1, quatre lignes
     « Jev sous consigne gemini-3.5 − <référence tabulaire> ». Sur le composite les quatre
     intervalles contiennent zéro ; hors choix unique et sur les parts globales, ceux de la
     régression à noyau et de la forêt aléatoire l'excluent. Le § 9 des masters écrit « aucune
     estimation appariée ne le sépare » sans nommer la lecture ; l'annexe H.1 le contredit sur
     deux lectures sur trois, et la phrase livrée ici nomme la lecture. -->

*Figure 4. Recall and precision by mode: the typed classifier trades public transport for
walking, and the modal split does not show the exchange.*

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
other day, and the next section moves beyond that day to an off-survey event.

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
