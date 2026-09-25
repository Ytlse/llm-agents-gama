# 4. The comparison bench

<!-- DERNIÈRE ÉCRITURE ANGLAISE : 2026-09-25 11:11:43 — le .tex correspondant porte cette date en en-tête tant qu'il en est le rendu fidèle. Voir sections/README.md. -->

<!-- Brouillon anglais, article court AAMAS 2027, PLAN.md § 4 — budget 900 mots.
     Rédigé le 2026-09-22 par l'agent article-writer. Hypothèse ticket 103 scénario 1.
     Le § 5 est écrit et fixe le vocabulaire ; cette section définit en amont les termes
     qu'il emploie. Les emplacements [replay pending] attendent les rejeux à graines du ticket 103, lot B ;
     aucun autre chiffre n'est un emplacement. Dépassement de budget signalé au
     compte-rendu, avec la liste des coupes possibles. -->

## 4.1 The cohort

Every score in this paper comes from one sealed cohort of 1,000 synthetic personas. A persona
is one synthetic person with a household and a day of trips. They form 499 whole households,
inside the study area. The eqasim synthesis chain (Hörl & Balać, 2021)
produced the pool of 11,329 people they were drawn from. It builds that pool from census and
national travel survey data. Their reference remains the local survey (Cerema & Tisséo
Collectivités, 2026), in which residents describe every trip of the day before.

<!-- Audit des citations du 2026-09-23. « Its input is the survey » était faux : la chaîne
     eqasim tire les individus dans le recensement INSEE, les apparie à l'ENTD 2008 (chaînes de
     déplacements, permis, abonnements), affecte le revenu FILOSOFI et localise par BAN/BDTOPO
     (services/eqasim-toulouse/config_toulouse.yml:19, hts: entd ;
     docs/arch/population-post-traitements.md). L'EMC² locale ne fournit que le périmètre, des
     traits aval et les marges de sélection. L'entrée horl2021eqasim de sample.bib renvoyait à
     un article inexistant (TRR 2675(11), DOI en 404) ; elle cite désormais Hörl & Balać,
     Transportation Research Part C 130 (2021), la référence que donne le dépôt eqasim-france.
     L'enquête est de nouveau citée, clé tisseo2023emc2 : doi:10.13144/lil-1750. -->

<!-- ⚠ eqasim nommé en corps de texte le 2026-09-23, sur remarque de l'auteur. La chaîne était
     citée dans les masters (fr/ et en/04_Evaluation.md § 4.1, « la chaîne de synthèse eqasim
     (Hörl & Balać, 2021) ») et la clé horl2021eqasim est dans sample.bib depuis l'origine,
     mais l'article court ne la citait nulle part : le § 4.1 disait « a synthetic pool » puis
     « the synthesis chain », un défini sans antécédent, et aucun autre chapitre ne la nomme.
     Une dépendance tierce du dispositif restait donc non créditée. Deux phrases au lieu
     d'une, la version d'un seul tenant faisant 28 mots (R1).
     source: fr/04_Evaluation.md § 4.1 : data/population/population_1000_AAMAS_v6/MANIFEST.yaml,
     selection.menages_retenus.n = 499, selection.vivier.n = 11329 ; vivier produit par la
     chaîne de synthèse eqasim (Hörl & Balać, 2021) à partir du recensement, des revenus
     fiscaux et de l'ENTD 2008 (corrigé le 2026-09-23 : « et de l'enquête » désignait à tort
     l'EMC²) ; périmètre des 453 communes, polygone communal. Enquête EMC² 2023,
     doi:10.13144/lil-1750 (corrigé le 2026-09-23 : lil-0933 est l'EMD 2013). Le ménage est
     l'unité de tirage. -->

Thirteen margins of the cohort are controlled against the survey. All thirteen conform. Each
margin is the share of one trait, such as age class or car ownership. The equivalence bound
was one point, set before measuring. The largest gap is 0.50 point (Appendix A).

<!-- source: fr/04_Evaluation.md § 4.1, tableau des treize marges et son commentaire
     (CONTROLE.md de la cohorte, scellé le 2026-09-14 ; 13 conformes, 0 à publier, 0 non
     mesurable). Borne d'indifférence de 1 point annoncée avant la mesure ; écart absolu
     maximal 0,50 point, sur la classe d'âge et sur l'occupation. -->

The cohort travels slightly less than the survey population: 3.30 trips per persona and 3.69
per persona who travels at all, against 3.53 and 3.95. That makes 3,299 trips per day.

The weather and the transport offer are those of a weekday of the survey's collection period,
from September 2022 to February 2023. That weekday is drawn for each persona, so the cohort
covers the whole period. Each persona starts that day with a blank memory, and no recollection
reaches its prompt during the day. No bench score therefore depends on the memory constants of
Section 3.3.

<!-- Ajout du 2026-09-24, décision de l'auteur : remplace le paragraphe d'ouverture du § 3.3,
     supprimé (renvois vers l'avant, « one day » trompeur, justification défensive). « Blank »
     est le mot retenu par l'auteur, le score étant strictement celui du run : ce qui a tourné
     est une mémoire COUPÉE (memoire: false dans les experience.yaml du banc →
     settings.agent.long_term_memory_enabled = False, services/llm-agents/experiences/cli.py ;
     registre long terme non créé, ni rappel ni bloc noyau dans le prompt, consolidation du
     soir sautée, urban_mobility_agents/agents/llm_agent.py). Pas de clause sur la
     consolidation du soir : avec une mémoire allumée, le bloc des habitudes se remplirait à
     chaque arrivée (seuil de trois trajets, llm/noyau.py), pas à la consolidation. -->

<!-- ⚠ Remarque de relecture n° 8, 2026-09-23 : « the day evaluated » ne disait ni quel jour ni
     pourquoi un seul. Correction demandée par l'auteur : dire le tirage du jour sur la période
     de l'enquête ; rédaction de l'auteur reprise le 2026-09-23, justification « same sky »
     retirée à sa demande. ⚠ Arbitrage de l'auteur, 2026-09-23 : « weather and transport offer »
     est gardé, l'offre d'un jour ouvré ordinaire étant jugée quasi identique d'un jour à
     l'autre. Dans le code, seul le bulletin météo est tiré ; l'offre est celle du jeu, datée du
     2026-03-16, hors de la fenêtre de collecte. Détail ci-dessous. VÉRIFIÉ, avec une précision : seul le BULLETIN MÉTÉO est tiré, l'offre de
     transport et l'horloge restent celles du jeu (lundi 2026-03-16, hors vacances de la zone C).
     Tirage : calendrier.politique: aleatoire sur les 74 expériences de data/experiences/
     (experiences/cli.py:597 → weather_per_agent_dates) ; llm_agent.py:647-690, date tirée
     déterministement depuis person_id parmi les jours ouvrés de la fenêtre de collecte
     (llm_agent.py:149-179, weather_weekdays_only). Fenêtre : 2022-09-20 → 2023-02-18,
     veille du lundi au vendredi (scripts/data/population/population_emc2_2023.yaml:28-40).
     Le tirage n'écarte pas les vacances scolaires comprises dans la fenêtre : non écrit.
     Chaînes cycliques : fr/04_Evaluation.md § 4.1. L'argument « un jour contre un jour » est
     l'unité de l'EMC² elle-même (un jour décrit par enquêté) ; la variabilité interjournalière
     d'une même personne n'est pas mesurée, limite déjà portée au § 7 (« one weekday »). -->

The survey records one mode per trip, not an itinerary. Every score therefore sums the probability of the
options that share a mode.

<!-- ⚠ Remarque de relecture n° 7 : passage de l'itinéraire au mode. Agrégation par mode
     canonique : packages/mobility_llm/src/mobility_llm/mode_choice.py:327 (mode_distribution),
     appelée par experiences/decideurs.py:42 pour tous les décideurs. -->

<!-- source: fr/04_Evaluation.md § 4.1 : MANIFEST.yaml, controle.menages_et_mobilite et
     reference_enquete ; chaînes d'activités cycliques, 3,299 déplacements le jour évalué,
     3,30 / 3,69 contre 3,53 / 3,95 ; 10,6 % d'immobiles des deux côtés, non repris ici.
     ⚠ Deux comptes coexistent en aval : le manifeste donne 3,161 déplacements portant une
     décision modale (138 à origine et destination confondues), le scoreur du § 6 en note
     3,154. L'écart de sept n'est expliqué nulle part dans les masters, et aucun des deux
     comptes n'est écrit ici. -->

We release the protocol, the code, the seeds and the sealed cohort in an repository[^depot]. Our research convention
forbids passing on the survey microdata themselves. The survey is obtained from the
PROGEDO-ADISP archive, on individual request (Cerema & Tisséo Collectivités, 2026).

<!-- ⚠ Paragraphe tranché par l'auteur le 2026-09-23, et il tranche dans les deux sens.
     (a) La cohorte se diffuse. L'annexe G disait le statut des ressources dérivées « pas
     tranché à ce jour » et la relecture v1 (item Q2) n'avait pas de réponse ; la réserve
     tombe, la cohorte entre dans la liste de ce qui se publie. La phrase précédente
     (« Whether the synthetic cohort […] can be released is not settled. ») est supprimée.
     (b) Les microdonnées ne se cèdent pas, mais le lecteur a une route : dépôt sur demande
     individuelle. La phrase que l'auteur avait retirée le 2026-09-22 revient donc amputée de
     ce qui la rendait sèche, et elle est suivie du moyen d'obtenir l'enquête.
     source : fr/99_annexes.md, annexe G, « Conséquence sur le matériel supplémentaire » :
     convention lil-1750 de Quetelet-Progedo-Diffusion, non-cession des microdonnées ;
     l'archive porte code, configurations, graines et cohorte scellée v6 avec son manifeste ;
     elle ne porte ni les microdonnées, ni le jeu de test scellé de 13,045 trajets.
     Route de diffusion donnée par l'auteur : https://www.progedo.fr/donnees-disponibles/
     donnees-localisees/ — rendue en note de bas de page dans 04_Bench.tex, sur le modèle de
     la note d'enquête du résumé, et absente du corps pour ne pas coûter de mots. À préserver
     en cas de régénération du .tex.
     ⚠ Le § 7.2 porte la limite corrélée (« re-estimating our tabular references requires
     obtaining the survey under the same terms »). Elle reste vraie et gagne son antécédent :
     les « same terms » sont maintenant nommés ici. Non modifié.
     ⚠ 2026-09-24, demande de l'auteur (« rajoute un lien vers un projet TBD de
     https://anonymous.4open.science/ ») : le lien s'accroche à la phrase de diffusion
     existante plutôt qu'à une phrase neuve du § 1.3, qui aurait redit cette diffusion
     (règle 8). Cinq mots de corps ; l'URL part en note de bas de page, comme celle de
     PROGEDO. « TBD » est à remplacer par l'identifiant du dépôt anonymisé avant la
     soumission (R14). -->

[^depot]: https://anonymous.4open.science/r/TBD

## 4.2 The protocol in three rules

Three rules close three ways of biasing a comparison between a generative agent and a
machine learning model on structured data.

Rule 1 gives every decision-maker the same 21 variables, twelve for the person and
household, three for the trip, six for geometry (Appendix B).

Rule 2 scores the probability mass a decision-maker puts on each option, not the option it
ranks first. The option ranked first is not the decision the simulation plays
(Section 3.2).

Rule 3 restricts each prediction of a machine learning model on structured data to the
modes offered for that trip, then rescales it to 100 %. Such a model predicts over
every mode, whereas a language model sees
only the options offered. The share of a mode is split evenly among its options.

<!-- ⚠ Remarque de relecture n° 7, et point E de la remarque 4 : la règle 3 était posée sans
     sa raison. Répartition égale de la masse d'une catégorie entre ses propositions :
     experiences/decideur_modele.py:240-248. -->

<!-- source: fr/04_Evaluation.md § 4.3, règles 1 à 3 : 21 variables (12 personne et ménage,
     3 déplacement, 6 géométrie), scripts/progedo_logit/feature_spec.json ; masse de probabilité
     comme grandeur scorée, justification Meister et al. (2024), « retenir le mode le plus
     probable ferait partir dans le même mode tous les personas d'un même profil » ;
     renormalisation sur l'offre, probabilités écrites avant et après correction. Six options
     au plus par déplacement (experience.yaml, max_candidats: 6). -->

We equalise the 21 variables, not the information each side holds. The language-based
decision-makers receive three things no machine learning model on structured data can receive. They see the agenda of
the remaining trips, the weather of the coming hours, and each itinerary step by step. The
machine learning models on structured data received something the language-based decision-makers never did, the 39,203 survey trips on which they were estimated. The
exposure asymmetry runs the other way, which makes those models high references.

<!-- source: fr/04_Evaluation.md § 4.3, deuxième et troisième paragraphes de la règle 1 :
     persona.py, champs agenda, day_outlook et trajectories ; exposition tabulaire
     mode_choice_policy_metrics.json, training.n_fit 31,279 + training.n_valid 7,924 = 39,203,
     les 13,045 trajets de test hors compte. « Le protocole égalise les 21 variables ; l'agent
     reçoit davantage d'information. » -->

## 4.3 What we measure

We measure at two scales, the modal split of the cohort and the agreement on each trip. The modal split is the share of trips made by car, public transport, walking and
cycling. The survey gives the reference share globally, then inside five strata. Three are nominal,
occupation, gender and trip purpose. Two are ordered, age class and distance class.

<!-- source: fr/04_Evaluation.md § 4.2 : quatre modes scorés, référence EMC² 2023 recalculée
     pour chaque strate — classe d'âge, occupation, genre, motif du déplacement, classe de
     distance —, puis agrégée en composite.
     ⚠ Les cinq strates sont nommées ici depuis le 2026-09-23, sur demande de l'auteur ; la
     passe précédente les renvoyait au § 5 et à l'annexe C faute de place. Cinq termes font
     une énumération que R1 veut en liste : elles sont donc réparties sur deux phrases de
     trois et deux termes, comme les quatre critères du § 4.4, et non mises en puces — une
     liste coûterait du blanc dans un papier déjà à dix pages.
     Le partage nominal / ordonné vient de metrics.py : JSD sur occupation, genre et motif,
     EMD sur classe d'âge et classe de distance, l'EMD respectant l'ordre des classes. Il est
     dit ici plutôt que déduit de la phrase des métriques deux paragraphes plus bas, qui
     oppose « nominal strata » et « ordered ones » sans dire lesquelles sont lesquelles.
     ⚠ Coût : cinq mots. La glose « a stratum being a slice of the population or trips »
     disparaît, les cinq noms la rendant inutile — trois découpent la population, deux les
     déplacements, et le lecteur le voit. Le terme reste défini ici, par énumération. -->

One composite number carries the aggregate reading. It adds the global divergence to the
weighted mean divergence of each stratum.
$$\mathcal{C}_{\text{EMD–JSD}} = \mathrm{JSD}^{\text{global}} + \sum_{d\ \text{nominal}} w_d\,\overline{\mathrm{JSD}}^{\,d} + \sum_{d\ \text{ordinal}} w_d\,\overline{\mathrm{EMD}}^{\,d}$$

Each $d$ is a stratum, $w_d$ its weight, and the bar the mean divergence over that stratum.

<!-- Remarque du tuteur sur la version longue (PDF annoté AAMAS_2027___LLM_v1_KOI, p. 5,
     « describe all the mathematical notations in the text »), reprise le 2026-09-25 : d, w_d
     et la barre n'étaient nommés nulle part. La phrase les glose avant que le paragraphe
     suivant dise comment chaque moyenne se pondère et quelles valeurs prennent les poids. -->

The divergence is Jensen–Shannon (Lin, 1991) in base 2 on nominal strata. Ordered strata take
the earth mover's distance (Rubner, Tomasi & Guibas, 2000), which respects the class order. Both lie in [0, 1], the distance once divided
by the number of class steps, and both are multiplied by 100. A nominal stratum averages its
classes, each weighted by its number of personas. An ordered one averages the four modes, each
weighted by its survey share. The weights are set by design, not fitted. The global term
weighs 1, age, occupation and purpose 0.5 each, gender and distance 0.3 each. A lower
composite means a distribution closer to the survey.

<!-- ⚠ Remarque de relecture n° 9, 2026-09-23 : poids w_d et normalisation non dits.
     Vérifié dans prompt_calibration/calibration/metrics.py : jsd() base 2, bornée [0, 1]
     (l. 824-844) ; emd_1d() = Σ|ΔCDF| en pas de classe (l. 847), divisée par K − 1 et × 100
     (l. 939) ; global JSD × 100 (l. 1001). Moyenne de strate : nominale pondérée par effectif
     de personas (jsd_nominal_dim_measured, l. 858-885, « remplace le seuil binaire n ≥ 5 ») ;
     ordinale, moyenne des profils de mode pondérée par la masse de RÉFÉRENCE du mode (A-EMD,
     l. 894-944). ⚠ Le commentaire de source ci-dessous (« moyenne non pondérée, catégories de
     moins de cinq personas écartées ») est PÉRIMÉ sur ce point.
     Poids servis par le banc : services/llm-agents/experiences/formules/reference.yaml,
     formule v1_reference — global 1,0 ; âge, occupation, motif 0,5 ; genre, distance 0,3.
     Aucune justification empirique : poids hérités de la page de synthèse historique
     (docs/synthesis, sources.yaml score.weights), déclarés comme choix de conception
     (arbitrage de l'auteur, remarque 5). Composite linéaire (weighted_composite, l. 306) :
     un lecteur peut repondérer depuis les termes publiés.
     ⚠ Écart non écrit : la même formule porte absent_penalty: 1,0 (metrics.py le met à 0,0
     par défaut). Sans effet sur les chiffres publiés : 272 scores sur 272 dans
     data/experiences/ ont absent_penalty = 0,0, aucun mode n'étant jamais à masse nulle
     sur la cohorte. -->

<!-- source: fr/04_Evaluation.md § 4.2, formules et poids : prompt_calibration/calibration/
     metrics.py, WEIGHTS (global 1.0, âge 0.5, occupation 0.5, motif 0.5, genre 0.3,
     distance 0.3), STRATUM_MIN_PERSONAS = 5 ; la barre est la moyenne non pondérée sur les
     catégories de la strate, les catégories de moins de cinq personas étant écartées. Ce
     dernier détail et les trois autres métriques vivent en annexe C. -->

Two other readings accompany the composite, all three published together. The first
recomputes it without the trips that offered a single option, where no preference is
expressed. The second is the L1 error on the global shares, the sum of absolute gaps in
percentage points.

<!-- source: colonnes du tableau du § 6.1 des masters : composite.emd_jsd,
     composite.emd_jsd_hors_choix_unique, global.l1 ; définition de l'erreur L1,
     fr/04_Evaluation.md § 4.2 ; lecture hors choix unique reprise du ticket 047, « quand un
     seul itinéraire est proposé, le décideur n'est pas interrogé ». ⚠ Aucun master ne définit
     cette lecture en prose : elle n'y est qu'un en-tête de colonne. La phrase ci-dessus est
     écrite ici pour la première fois. -->

A difference between two decision-makers counts only when it exceeds what a new cohort would
move. Another cohort of 1,000 personas built the same way would shift a composite by ±1.3
points. Resolution varies by decision-maker, from 0.9 point for the typed classifier under its
expert prompt to 2.1 under its minimal prompt.

<!-- ⚠ Remarque de relecture n° 2, point E, 2026-09-23 : « agent » désignait ici un décideur
     sans dire lequel parmi quinze. « tuned » était employé ici avant toute définition ; les deux bornes sont celles du commentaire de source ci-dessous : classifieur typé sous sa consigne 0,86, sous prompt minimal 2,05. --> Trips of one person are not independent, so
every interval comes from resampling clusters at the person level. A paired difference
compares two decision-makers on the persons both scored, at 95 %.

<!-- source: résolution recalculée le 2026-09-22 sur le jeu corrigé du ticket 088 (relecture
     v1, items G5 et Q3) : douze bras, 2,000 rééchantillonnages par grappe au niveau de la
     personne, graine 2026, 868 personnes communes, scoreur officiel formule.reference /
     emd_jsd.composite ; machinerie de
     docs/traces/2026-09-21_ticket096_lot2/scripts/paired_avec_jev.py avec la lecture
     marginale par bras de
     docs/traces/2026-09-15_09-20_ticket080_idee_directrice_chapitre6/scripts/bootstrap.py.
     Demi-largeur médiane 1,33 (écart-type bootstrap médian 0,68) : la valeur ne bouge pas,
     et la réserve « mesuré avant le rescorage » tombe.
     Demi-largeurs par bras : classifieur typé sous sa consigne 0,86 ; régression à noyau 1,04 ;
     forêt aléatoire 1,04 ; gradient boosté 1,08 ; logit multinomial 1,14 ; gemini-3.5 expert
     1,22 ; puis les bras à prompt minimal, 1,43 / 1,44 / 1,45 / 1,77 / 1,97 et 2,05 pour le
     classifieur typé sous prompt minimal. D'où la clause « from 0.9 point … to 2.1 » : ±1,3
     est une médiane, pas une borne uniforme. Différences appariées, mêmes réplicats. -->

The unit-level audit asks the other question, on the days respondents actually described. It covers 9,621 trips of 2,930 respondents, each carrying its declared mode. We publish
accuracy, cross-entropy in nats, and recall and precision per mode. Cross-entropy falls as a
decision-maker puts more probability on the declared mode. Recall is the share of a mode's
declared trips that it designates.

<!-- ⚠ Remarque de relecture n° 9, point E, 2026-09-23 : unité de l'entropie croisée non dite.
     Nats vérifiés : scripts/progedo_logit/mode_choice_eval.py:92-97, sklearn log_loss
     (logarithme naturel), commentaire « la même grandeur, en nats » ; appelée par
     scripts/progedo_logit/audit_unitaire_058.py (evaluate_proba). -->

<!-- source: fr/05_Protocol.md § 5.4 : 2,930 personnes, 9,621 déplacements portant le mode
     déclaré, offre reconstruite par les mêmes moteurs, contrainte de chaîne appliquée ;
     grandeurs publiées, fr/04_Evaluation.md § 4.2, « exactitude, entropie croisée mesurée sur
     les décisions que tous les décideurs comparés notent, puis le rappel et la précision par
     mode ». -->

## 4.4 Floors, references, decision-makers

Three floors give the level a decision-maker reaches without behavioural knowledge. One
draws uniformly over the options offered, another puts everything on the car, the area's
majority mode. The third, the minimum-duration heuristic, keeps the fastest option offered.

<!-- source: fr/05_Protocol.md § 5.3 : hasard uniforme (1/|O_i|), a priori empirique sur le
     mode majoritaire du territoire, heuristique de durée minimale sur les graphes de
     transport. -->

Four reference models, all machine learning models on structured data, give the level that
estimation on the survey reaches. They are a
multinomial logit, the standard discrete-choice model, and three learned models. These are
LightGBM gradient boosting (Ke et al., 2017), a kernel logistic regression (Zhu & Hastie, 2005)
and a random forest (Breiman, 2001). We estimate the four at strict parity, on the
same survey partition. None of them leads on all three readings, so we read the ceiling
one reading at a time.

<!-- Audit des citations du 2026-09-23 : les trois modèles appris étaient nommés sans
     référence alors qu'ils portent le plafond du tableau 1. Gradient boosting = LightGBM
     (scripts/progedo_logit, fit_mode_choice_policy.py) ; régression logistique à noyau RBF
     approchée par Nyström (fit_mode_choice_klr.py) ; forêt aléatoire
     (fit_mode_choice_forest.py). Divergence de Jensen–Shannon, Lin (1991) ; distance du
     cantonnier, Rubner, Tomasi & Guibas (2000). Clés : ke2017lightgbm, zhu2005kernel,
     breiman2001random, lin1991divergence, rubner2000earth, métadonnées vérifiées sur Crossref. -->

<!-- source: fr/04_Evaluation.md § 4.4 : quatre méthodes ajustées sur les microdonnées de
     l'enquête, parité stricte (même fichier, même découpage par ménage, mêmes poids de
     redressement, même encodage, mêmes métriques issues d'un module partagé) ; « aucune
     méthode ne mène sur les trois axes » ; « le plafond se lit axe par axe : sur chacun, le
     meilleur score du tableau ». Gradient boosté = LightGBM (Ke et al., 2017) ; noyau RBF et
     approximation de Nyström pour la régression logistique à noyau. -->

Three families of decision-makers are under test. The minimal prompt gives a language model
the facts of the trip and the output format, with no general criteria. The expert prompt
keeps that format and draws the model's attention to four general criteria. Two bear on
comfort, the walking and waiting public transport really adds, and an unhurried pace for an
older traveller. The other two bear on constraints, heavy shopping bags to carry and a
working day with no slack. The third family is a zero-shot classifier with typed output
(TypeSafe System One, jev-1.13.0). It reads that same text and returns one probability per
option without writing a sentence.

<!-- source: fr/05_Protocol.md §§ 5.1 et 5.2 pour les deux prompts (prompt_minimal_02, 82 mots ;
     prompt_expert_05, 277 mots). Les quatre principes sont nommés d'après le texte servi,
     packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml, prompt_expert_05, en-tête
     « Situational trade-off principles » : « Chain friction » (reconstituer la durée réelle
     porte-à-porte, marche d'accès, attente, correspondance), « Autonomy of older people »
     (marche continue à son rythme contre les secousses, les marches, l'attente debout),
     « Carrying logistics » (courses et sacs lourds rendant les transports en commun
     rebutants), « Working people's life time » (journée serrée, temps pris sur la vie
     personnelle). Aucune de ces puces ne donne de règle de pondération des options : la
     formulation « quatre principes d'arbitrage » est remplacée le 2026-09-22 sur correction
     de l'auteur, et le terme unique retenu pour tout le papier est « general criteria »
     (R12), le prompt étant dit attirer l'attention du modèle sur ces critères. Les quatre
     puces sont rendues dans le registre du résumé de l'auteur : confort pour la friction de
     chaîne et l'autonomie des personnes âgées, contrainte pour la logistique de portage et
     le temps de vie des actifs. Aucune n'est une opportunité.
     ⚠ prompt_expert_32, réglée POUR le classifieur typé, réécrit la puce « Chain friction »
     à deux versants : la marche directe, quand elle est elle-même la longue part du trajet,
     « is paid in time and fatigue ». CORRIGÉ le 2026-09-24 : cette note et la phrase de corps
     attribuaient à prompt_expert_32 une cinquième notion, l'exposition réelle à la météo ;
     elle n'y est pas. La puce météo est celle de prompt_expert_25, réglée pour gemini-3.1 et
     absente de l'article. Vérifié sur le texte de prompts.yaml, reproduit en annexe D.4. Les
     quatre principes énoncés ici sont ceux du prompt servi aux modèles de langue ; le
     § 5.3 mesure la consigne du classifieur sans la décrire. La réécriture de la puce est
     dite en corps de texte, au paragraphe de la seconde cohorte (phrase posée le 2026-09-23
     sur demande de l'auteur, corrigée le 2026-09-24) : « four » reste exact pour les deux
     prompts experts, qui portent chacun quatre puces.
     fr/06_Empirical_Evaluation.md l. 21 pour le classifieur à sortie typée, « qui rend une
     probabilité par option sans produire de texte ». Les trois consignes lui sont servies
     amputées de leur bloc de sortie, le type Choice le remplaçant. Identité du décideur :
     docs/tickets/ticket_096_jev_typesafe_troisieme_famille_de_decideur.md § 1,
     « classifieur zéro-shot à sortie typée », modèle jev-1.13.0, POST
     https://api.typesafe.ai/v1/systemone ; « zéro-shot » est porteur, ce décideur n'ayant
     rien vu de Toulouse, ce qui fonde la clause « needs no local survey » du § 7.1.
     Modèles de fondation :
     gemini-3.1-flash-lite, gemini-3.5-flash-lite, mistral-large-2512, jev-1.13.0. -->

We obtained the expert prompt by successive mutations of one text, under a single constraint.
Its text contains no numerical threshold or formula. Each iteration reads the gaps per
stratum of the prompt in service, proposes one targeted rewrite, and keeps it when the
over-represented mode recedes. Each rewrite is evaluated, like any other evaluation here,
according to the probability mass of Rule 2. One criterion of the expert prompt thus reads:
"For elderly or frail people, a continuous, unhurried walk at one's own pace is the natural
mode of independence for short distances, against the strain and stress of public transport (jolting, risk of falling, steps
to climb, standing while waiting with no bench)." We call tuned agent the expert prompt served
to gemini-3.5, the best-scoring language-model condition in Table 1.

<!-- Ajout du 2026-09-24, format demandé par l'auteur : la phrase des contraintes reste
     telle quelle, suivie d'un exemple. Citation mot pour mot de la puce « Autonomy of older
     people » de prompt_expert_05 (packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml,
     texte identique dans ses dérivés 31 à 34). Elle illustre la contrainte sur les seuils :
     « short distances » au lieu d'une borne chiffrée.
     Retrait du 2026-09-24, décision de l'auteur : la contrainte « forbid naming a survey
     category » est retirée du texte, trois contraintes deviennent deux. Juxtaposée à
     « elderly or frail people », elle se lisait comme contredite. Le garde-fou existe
     toujours dans le protocole (article_old_do_not_maintain/fr/05_Protocol.md l. 111 : ni
     catégorie professionnelle, ni tranche d'âge, ni commune cible) et prompt_expert_05 le
     respecte : aucune tranche d'âge, aucun « retired », aucune commune, aucun chiffre.
     Réécriture du 2026-09-24, texte de l'auteur, option B : « under a single constraint: its
     text contains no numerical threshold or formula » réunit les règles C1 (aucun seuil
     chiffré) et C2 (aucune formule mathématique : ni fonction d'utilité, ni pondération, ni
     ratio) de .claude/agents/prompt-auditor.md. « logical rules », proposé d'abord, a été
     écarté : la jurisprudence C1 n° 3 (2026-09-10) admet la conditionnelle prescriptive sans
     nombre, et la puce citée juste après en est une. « verbalised distributions » cède la place
     au renvoi à la règle 2 du § 4.2 : l'adjectif désigne ailleurs la délibération verbalisée,
     et la notation du réglage n'est que la règle 2 appliquée à chaque réécriture. -->


<!-- ⚠ Remarque de relecture n° 2, point E, 2026-09-23 : « agent » désignait ici un décideur
     sans dire lequel parmi quinze. « The tuned agent » (§§ 5.2, 5.4, 5.5) n'était défini nulle part ; le lecteur ne pouvait pas savoir s'il s'agissait du classifieur à consigne réglée ou du prompt expert. Vérifié : § 5.5 donne 67,6 % au « tuned agent » et le tableau 3 à « Expert prompt, gemini-3.5 » ; § 5.2 fait porter la pente de distance sur gemini-3.5 (prompt_minimal_02 → prompt_expert_05). Meilleur des modèles de langue au tableau 1 : 4,86 contre 7,63 et 8,98. La phrase s'appuie sur la règle de nommage du § 3 (« we name an agent after it »). -->

<!-- source: fr/05_Protocol.md § 5.2.2 pour la procédure de mutation (écarts par strate,
     hypothèse sur le mécanisme, rejeu apparié contre un bras témoin, motif du rejet consigné)
     et § 5.2.3 pour les trois garde-fous (aucun seuil chiffré, aucune étiquette d'enquête,
     mesure sur les distributions verbalisées, le tirage dispersant chaque part de ±1,7 point) ;
     fr/06_Empirical_Evaluation.md l. 25 pour la provenance : « prompt_expert_05 a été réglé
     contre gemini-3.5-flash-lite sur une population de calibration tirée séparément de la
     cohorte scellée, puis soumis tel quel aux autres porteurs ».
     ⚠ CONTRADICTION ENTRE MASTERS, signalée au compte-rendu. fr/05_Protocol.md § 5.2.3, daté du
     21 septembre, écrit l'inverse : « les écarts qui pilotent les mutations ont été lus sur la
     cohorte scellée du chapitre 4 elle-même… Les scores du prompt expert rapportés au
     chapitre 6 sont donc des scores en échantillon. » Le texte ci-dessus suit le master du
     22 septembre, le PLAN § 4.4 et le § 5.2 déjà rédigé ; il est faux si c'est le master du
     21 septembre qui fait foi. -->

Since each model has its own biases, the tuning of an expert prompt differs from one model
to the next. The classifier has its own expert prompt, tuned on a calibration cohort that
shares no persona with the sealed cohort. That prompt rewrites the criterion on walking and
waiting, so that a long direct walk also counts as a cost. Every crossing of models and
prompts is therefore measured on the sealed cohort alone. Appendix D gives the three prompts
in full, with one trip decided under each.

<!-- Phrase d'ouverture ajoutée le 2026-09-24 sur texte de l'auteur, qui l'appuie sur ses
     propres expériences : pour un même prompt, chaque modèle rend des parts agrégées
     différentes, donc un réglage fin se fait sur mesure. Décision de l'auteur : la phrase
     pose le principe SANS chiffre ; n'en ajouter aucun. Le § 5.1 le montre déjà (même texte
     expert servi à gemini-3.1 : 4,15 points de composite d'écart). La calibration fine par
     modèle se poursuit, d'autres prompts propres suivront.
     Deux retouches sur le texte fourni, à revoir par l'auteur : « each classifier » →
     « each model » (le papier ne nomme classifieur que Jev) ; « calibrating the prompt using
     an expert prompt is different » → « the tuning of an expert prompt differs » (terme unique
     « tuned » du paragraphe précédent ; le prompt expert est le produit du réglage).
     Rôle des deux cohortes, décision de l'auteur du 2026-09-24 : la cohorte scellée du § 4.1
     est population_1000_AAMAS_v6, jeu population_1000_AAMAS_v6_20260316_EN_c (référence, mesure
     seule) ; la cohorte de calibration est population_1000_AAMAS_v6_c2, jeu
     population_1000_AAMAS_v6_c2_20260316_EN_c (réglage des prompts). « Calibration cohort » et
     « sealed cohort » sont les deux termes uniques ; le verbe reste « tuned ».
     ⚠ CONDITION POUR QUE LE PARAGRAPHE SOIT VRAI : prompt_expert_32 a été réglé le 2026-09-21
     sur la cohorte SCELLÉE (docs/traces/2026-09-21_jev_mutations/README.md, « les écarts qui
     pilotent les mutations sont lus sur la cohorte scellée elle-même »), c2 n'existant que
     depuis le 2026-09-22. Le prompt du classifieur doit être re-réglé sur c2 puis noté une
     fois sur c1. Le tableau 1 porte [re-tuning pending] sur cette ligne en attendant.
     ⚠ « Every crossing … on the sealed cohort » : sur c1, gemini-3.5 × prompt_expert_32 n'est
     pas mesuré. -->


<!-- source: fr/06_Empirical_Evaluation.md l. 23 et l. 25 (prompt_expert_32 muté sur les écarts
     par strate de Jev lus sur la cohorte qui le note, six textes mesurés, cinq écartés) ;
     ticket 103 § 0 et lot A pour la seconde cohorte, data/population/population_1000_AAMAS_v6_c2
     et son jeu, « sans un seul persona commun avec c1 », « aucun prompt n'a été réglé sur c2 :
     tout ce qui s'y mesure est hors échantillon, pour les deux modèles à la fois ».
     ⚠ Ce rôle de c2 (mesure hors échantillon) est INVERSÉ par la décision de l'auteur du
     2026-09-24 : c2 est la cohorte de calibration, c1 la cohorte scellée de mesure. La réserve
     « en échantillon », que la relecture v1 (§ 9 bis) faisait porter au seul libellé de ligne
     du tableau 1, disparaît avec le re-réglage. -->

*Table 1 — The fifteen decision-makers on the three readings, with the inter-seed range where
it was measured.*

| Decision-maker | Composite | Excluding single option | L1 on global shares | Inter-seed range |
|---|---:|---:|---:|---|
| Uniform random | 50.16 | 57.90 | 86.80 | deterministic |
| All-car | 30.73 | 28.41 | 58.00 | deterministic |
| Minimum duration | 26.97 | 23.93 | 53.62 | deterministic |
| Minimal prompt, mistral-large | 14.75 | 20.72 | 44.71 | not replayed |
| Minimal prompt, typed classifier | 13.75 | 19.84 | 42.76 | not replayed |
| Minimal prompt, gemini-3.1 | 12.38 | 16.65 | 39.88 | not replayed |
| Minimal prompt, gemini-3.5 | 7.02 | 10.39 | 24.08 | **[pending]** |
| Expert prompt, gemini-3.1 | 8.98 | 12.39 | 31.25 | not replayed |
| Expert prompt, mistral-large | 7.63 | 12.27 | 26.64 | not replayed |
| Expert prompt, gemini-3.5 | 4.86 | 6.86 | 13.85 | 0.56 |
| Multinomial logit | 4.02 | 6.63 | 8.99 | deterministic |
| Random forest | 4.09 | 5.81 | 5.28 | deterministic |
| Expert prompt, typed classifier | **[re-tuning pending]** | **[re-tuning pending]** | **[re-tuning pending]** | **[re-tuning pending]** |
| Kernel logistic regression | 3.61 | 5.61 | 6.69 | deterministic |
| Gradient boosting | 3.60 | 5.84 | 9.49 | deterministic |

<!-- source: fr/06_Empirical_Evaluation.md § 6.1, tableau des quinze décideurs (scores.json,
     composite.emd_jsd, composite.emd_jsd_hors_choix_unique, global.l1 ; jeu corrigé du
     ticket 088). Étendue inter-graines 0,56 : § 6.5, graines 42 / 123 / 789, composites
     4,857 / 4,646 / 4,299. [replay pending] = les deux décideurs dont le ticket 103, lot B, doit rejouer
     les graines 123 et 789. « not replayed » = aucune graine supplémentaire jouée, l'effet de
     la graine sur ces lignes n'étant pas mesuré.
     [re-tuning pending] = ligne « Expert prompt, typed classifier », décision de l'auteur du
     2026-09-24 : le prompt du classifieur se règle sur la cohorte de calibration (c2) et se
     note une fois sur la cohorte scellée (c1). Le libellé « (in sample) » tombe avec ce
     protocole. Valeurs retirées, à ne PAS restituer : prompt_expert_32 réglé sur c1 le
     2026-09-21, donc en échantillon — composite 3,65, hors choix unique 6,58, L1 10,48,
     étendue inter-graines 0,05 (graines 42 / 123 / 789 : 3,6470 / 3,7014 / 3,6926). L'étendue
     est à rejouer aussi, sur le prompt re-réglé. -->

<!--
=== SECTION REPORT ===
Section        : 04 — The comparison bench
File           : docs/paper/article-court/sections/04_bench.en.md
Words / budget : 1027 / 900 (+14.1 %)
Skeleton       :
  We compare fifteen decision-makers on one cohort, under one protocol, with one set of
  measurements.
  Every score in this paper comes from one sealed cohort of 1,000 synthetic personas.
  Thirteen margins of the cohort are controlled against the survey.
  The cohort travels slightly less than the survey population, 3.30 trips per persona and
  3.69 per mobile persona against 3.53 and 3.95.
  We release the protocol, the code, the seeds and the sealed cohort.
  Three rules close three ways of biasing a comparison between a generative agent and a
  tabular model.
  Rule 1 gives every decision-maker the same 21 variables.
  Rule 2 scores the probability mass a decision-maker puts on each option.
  Rule 3 restricts every tabular prediction to the modes actually offered for that trip.
  We equalise the 21 variables, not the information each side holds.
  We measure at two scales, the modal split of the cohort and the agreement on each trip.
  One composite number carries the aggregate reading.
  The divergence is Jensen-Shannon on nominal strata, and the earth mover's distance on
  ordered ones.
  Two other readings accompany the composite.
  A difference between two decision-makers counts only when it exceeds what a new cohort
  would move.
  The unit-level audit asks the other question, on the days respondents actually described.
  Three floors give the level a decision-maker reaches without behavioural knowledge.
  Four tabular references give the level that estimation on the survey reaches.
  Three families of decision-makers are under test.
  We obtained the expert prompt by successive mutations of one text, under three
  constraints.
  The classifier has its own expert prompt, tuned on the first cohort.
  Every score that follows comes off this bench, starting with the ordinary day the survey
  describes.
Checker        : none. verifier_forme.py exits 0 after the author's corrections of
  2026-09-23 ; R1, R2, R4, R5, R9, R10, R11 and R14 are clean. Squelette reads in one go.
  The four general criteria are now named over two sentences of two terms each, 20 and 18
  words, which also settles R1's rule that an enumeration of more than three terms becomes
  a list. The previous single sentence of four terms is gone, and with it the judgement
  call recorded in the previous pass.
Terms defined here : persona (4.1) ; margin (4.1) ; modal split, reference share and
  stratum (4.3) ; composite, Jensen-Shannon divergence and earth mover's distance (4.3) ;
  L1 error on the global shares (4.3) ; cross-entropy and recall (4.3) ; floor and tabular
  reference (4.4) ; minimal prompt, expert prompt, general criteria and typed
  classifier (4.4, the single definition of the classifier for the body, per review item on
  the fourfold definition) ; in sample and out of sample (4.4, by use). "Zero-shot" is used
  without a gloss, the target reader knowing language models.
Terms used, undefined upstream : none. decision-maker is defined in 1.3 and is no longer
  redefined here (review item Q1) ; household travel survey is glossed in 1.1 ; renormali-
  sation is written as "rescales it to 100 %" rather than named.
Figures cited  :
  1,000 personas, 499 households, 11,329-person pool, 453 communes. Source comment in the
    body, fr/04_Evaluation.md 4.1 and the cohort MANIFEST. No reservation.
  Thirteen margins, one-point equivalence bound, largest gap 0.50 point. Source comment in
    the body, CONTROLE.md of the cohort. Bound announced before measuring.
  3.30 and 3.69 trips against 3.53 and 3.95 ; 3,299 trips on the day evaluated. Source
    comment in the body. The comment carries an unexplained seven-trip gap between two
    downstream counts ; neither count is written in the text.
  21 variables, twelve/three/six. Source comment in the body, feature_spec.json.
  39,203 survey trips of tabular exposure. Source comment in the body,
    mode_choice_policy_metrics.json, 31,279 + 7,924.
  +/-1.3 points of composite resolution, and a per-decision-maker spread from 0.9 to 2.1.
    Source comment in the body: recomputed on 2026-09-22 on the set corrected by ticket 088,
    twelve conditions, 2,000 cluster resamples at the person level, seed 2026, official
    scorer. Median half-width 1.33, median bootstrap SD 0.68, 868 persons common to all.
    Reservation lifted: the sentence "That estimate predates the correction of the scoring
    set." is deleted, the value being unchanged on the corrected set (review item G5/Q3).
  9,621 trips of 2,930 respondents, unit-level audit. Source comment in the body,
    fr/05_Protocol.md 5.4. No reservation.
  Table 1, fifteen decision-makers on three readings ; inter-seed range 0.56 on one row.
    Source comment under the table, fr/06_Empirical_Evaluation.md 6.1, scores.json on the
    set corrected by ticket 088.
Placeholders   : ONE [pending] cell left in Table 1, the minimal-prompt gemini-3.5 row, and
  the (in sample) row label,
  both left untouched pending lot B of ticket 103 (review item Q4).
Left out       : nothing new. The five strata are named in 5 and in Appendix C, not here,
  for want of room ; the thirteen-margin table stays in Appendix A, per the plan.
Flags for the author :
  1. The contradiction between masters is unresolved and the review did not rule on it.
     fr/05_Protocol.md 5.2.3, dated 21 September, says the mutations of the expert prompt
     read the gaps on the sealed cohort itself, so its scores in chapter 6 are in sample.
     fr/06_Empirical_Evaluation.md line 25, dated 22 September, says the text was tuned
     against one model on a calibration population drawn apart from the scored cohort.
     Section 4.4 follows the 22 September master, as does the plan and 5.2 as drafted. If
     the 21 September master holds, the sentence "The text was tuned against one language
     model on a separate calibration population" is false, and the out-of-sample status of
     the expert-prompt scores falls with it.
  2. The review's replacement sentence for the second-cohort passage runs to 30 words and
     breaks R1. It is split into two sentences, with the semicolon turned into a full stop.
     No word of the meaning is lost.
  3. CLOSED on 2026-09-23 by the author. The release sentence is no longer weaker than
     7.2: the cohort is released, and 7.2's "under the same terms" now has an antecedent,
     the archive being named here. 7.2 is unchanged and stays true — re-estimating the
     tabular references still means obtaining the survey oneself.
  4. Review item G3, the ", and <short tail>." tic. First pass: the heuristic count went
     from 2 to 0. Second pass, on a scan that also reads coordinations wrapped across lines:
     three more were found and all three broken — "…set before measuring. The largest gap is
     0.50 point" (two sentences), "…runs the other way, which makes those models high
     references" (relative), "Two other readings accompany the composite, all three published
     together" (rewording). What is left in this section is enumeration, not the tic.
  5. The typed classifier is now defined once in the body, here in 4.4. Sections 5.3 and
     7.3 still carry their own wordings ; they belong to other agents, and the definition
     here is the one they should point to.
  6. G5/Q3 applied on 2026-09-22. The value does not move, so no figure of 5 changes. One
     clause was added, and it is a judgement call recorded here: the recomputation shows the
     resolution to be decision-maker dependent, from 0.86 for the typed classifier under its
     own instruction to 2.05 for the same classifier under the minimal prompt. Section 5
     leans on +/-1.3 twice, once against a seed range of 0.56 and once as the unit of the
     "one and a half to five and a half times" ratio. Without the clause a reviewer reads
     +/-1.3 as a uniform bound and the two claims look safer than the widest conditions
     allow. The clause states the extremes and nothing more.
  7. The ratio of 5.2, "one and a half to five and a half times the cohort resolution", is
     computed against the median 1.3. Against the widest condition of that comparison, the
     minimal prompt, the multiplier falls. The author may want 5.2 to say "times the median
     resolution", which costs one word.
  8. The seed range of 0.56 in 5.1 is compared to +/-1.3. The half-width of the condition
     concerned, gemini-3.5 under the expert prompt, is 1.22, so the claim holds on its own
     condition as well as on the median. Recorded in the source comment of 5.1.
  9. Author's corrections of 2026-09-22, applied here. "Four qualitative arbitration
     principles" is wrong about the text served: the prompt's own header reads "Situational
     trade-off principles" and its bullets describe lived circumstances rather than a way of
     weighing options. The paper now uses one term, "general criteria", here and in 5 (5's
     lead list, 5.1, 5.2), and the prompt is said to draw the model's attention to them.
     4.4 is the one place that names the four, so 5 refers to them without listing them again.
  10. The term is the author's, taken from the abstract he wrote on 2026-09-22. It replaces
     the "situational principles" of the previous pass, which was this agent's coinage and
     pulled against the abstract. The adjective "general" is kept at all five occurrences in
     the body: it is what separates these criteria, which hold for any trip, from the facts
     of the trip that the minimal prompt already carries. Dropping it in 5.1 would turn "no
     general criteria" into "no criteria", which says the opposite of that paragraph.
  11. The typed classifier gains its vendor identity at its first occurrence, "a zero-shot
     classifier with typed output (TypeSafe System One, jev-1.13.0)". "Zero-shot" is
     load-bearing: this decision-maker has seen nothing of Toulouse, which is what separates
     it from the four tabular references and what 7.1's "needs no local survey" rests on.
     Every other occurrence in the paper still reads "the typed classifier".
  12. APPLIED on 2026-09-23, the author asking for the proposals of this report to be
     carried out. Two expert prompts exist and they differ. The text served to the language
     models carries four criteria ; the variant tuned for the typed classifier carries a
     fifth notion, real exposure to the weather, through a rewritten chain-friction bullet.
     The paper's "four" stays correct for the language models' prompt. The sentence "That
     instruction adds a fifth general criterion, real exposure to the weather." is added
     after "The classifier's instruction was tuned on the first cohort.", as this report
     proposed. It is a sentence of its own, not a trailing ", and …" clause, review item G3
     having cleared those from this section. Cost: eleven words.
     ⚠ CORRECTED on 2026-09-24. This item was wrong on the text: prompt_expert_32 carries no
     weather bullet. Its chain-friction bullet is rewritten on two sides, the long direct
     walk becoming a cost too. The weather bullet belongs to prompt_expert_25, tuned for
     gemini-3.1 and absent from the paper. The body sentence now reads "That prompt rewrites
     the criterion on walking and waiting, so that a long direct walk also counts as a
     cost." Both expert prompts carry four criteria. Appendix D.4 prints the rewritten
     bullet.
  13. Section 4 now runs 1,027 words against a 900-word budget, +14.1 %. The two changes of
     2026-09-23 cost nineteen words net: plus eight on the release paragraph, plus eleven on
     the fifth criterion. The section is still inside the +/-15 % bracket, with 27 words of
     margin left, and 4.4 is its longest subsection at 362 words. The trigger written in the
     previous pass has fired — the compile does overrun, at ten pages against eight — but
     the remedy written with it is not applied: moving the two sentences that name the four
     criteria to Appendix D buys eighteen words where two pages are wanted, and the floats
     hold 2.36 pages. The page count is not a section-4 problem and is not treated as one.
  14. Author's decision of 2026-09-23 on availability, applied to 4.1. The sealed cohort is
     released ; the survey microdata are not ours to pass on ; the survey itself is obtained
     from the Quetelet-PROGEDO-Diffusion archive on individual request. Appendix G of the
     masters left the status of derived resources open, and review item Q2 had no answer:
     both are settled by this decision, and the sentence "Whether the synthetic cohort […]
     can be released is not settled." is gone. The archive's URL is set as a footnote in
     04_Bench.tex rather than in the body, on the model of the survey footnote of the
     abstract, so that it costs no words. Regenerating that file must preserve it.
=== END SECTION REPORT ===
-->
