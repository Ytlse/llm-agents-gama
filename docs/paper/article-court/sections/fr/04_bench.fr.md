# 4. Le banc de comparaison

<!-- Rendu français de 04_bench.en.md (consigne R17), article court AAMAS 2027, PLAN.md § 4.
     Rendu le 2026-09-22 par l'agent article-writer. Hypothèse ticket 103 scénario 1.
     L'anglais fait foi : ce texte en reprend les coupes de paragraphe, le compte de phrases,
     les chiffres, l'équation, la structure du tableau 1 et les commentaires de source. Les
     emplacements [replay pending] attendent les rejeux à graines du ticket 103, lot B ;
     aucun autre chiffre n'est un emplacement. -->

Nous comparons quinze décideurs sur une même cohorte, sous un même protocole, avec un même jeu
de mesures.

## 4.1 La cohorte

Tous les scores de cet article viennent d'une même cohorte scellée de 1 000 personas
synthétiques. Un persona est une personne synthétique dotée d'un ménage et d'une journée de
déplacements. Ces personas forment 499 ménages entiers, tirés d'un vivier synthétique de
11 329 personnes, dans les 453 communes de notre référence. Cette référence est l'enquête
ménages-déplacements toulousaine, où les habitants décrivent chacun de leurs déplacements de la
veille.

<!-- source: fr/04_Evaluation.md § 4.1 : data/population/population_1000_AAMAS_v6/MANIFEST.yaml,
     selection.menages_retenus.n = 499, selection.vivier.n = 11329 ; vivier produit par la
     chaîne de synthèse eqasim (Hörl & Balać, 2021) à partir du recensement, des revenus
     fiscaux et de l'enquête ; périmètre des 453 communes, polygone communal. Enquête EMC² 2023,
     doi:10.13144/lil-0933. Le ménage est l'unité de tirage. -->

Treize marges de la cohorte sont contrôlées contre l'enquête. Les treize sont conformes. Une
marge est la part d'un trait, comme la classe d'âge ou la motorisation. La borne d'indifférence
valait un point, fixée avant la mesure. L'écart le plus grand vaut 0,50 point (annexe A).

<!-- source: fr/04_Evaluation.md § 4.1, tableau des treize marges et son commentaire
     (CONTROLE.md de la cohorte, scellé le 2026-09-14 ; 13 conformes, 0 à publier, 0 non
     mesurable). Borne d'indifférence de 1 point annoncée avant la mesure ; écart absolu
     maximal 0,50 point, sur la classe d'âge et sur l'occupation. -->

La cohorte se déplace un peu moins que la population de l'enquête, 3,30 déplacements par
persona et 3,69 par persona mobile contre 3,53 et 3,95. Le jour évalué porte 3 299
déplacements.

<!-- source: fr/04_Evaluation.md § 4.1 : MANIFEST.yaml, controle.menages_et_mobilite et
     reference_enquete ; chaînes d'activités cycliques, 3 299 déplacements le jour évalué,
     3,30 / 3,69 contre 3,53 / 3,95 ; 10,6 % d'immobiles des deux côtés, non repris ici.
     ⚠ Deux comptes coexistent en aval : le manifeste donne 3 161 déplacements portant une
     décision modale (138 à origine et destination confondues), le scoreur du § 6 en note
     3 154. L'écart de sept n'est expliqué nulle part dans les masters, et aucun des deux
     comptes n'est écrit ici. -->

Notre convention de recherche interdit de transmettre les microdonnées de l'enquête, ou tout
fichier qui les reproduit. Nous diffusons le protocole, le code et les graines. La diffusion de
la cohorte synthétique, dérivée de l'enquête par la chaîne de synthèse, n'est pas tranchée.

<!-- source: fr/99_annexes.md, annexe G, « Conséquence sur le matériel supplémentaire » et
     dernier paragraphe : convention lil-1750 ; l'archive porte code, configurations, graines et
     cohorte scellée v6 avec son manifeste ; elle ne porte ni les microdonnées, ni le jeu de
     test scellé de 13 045 trajets ; le statut des ressources dérivées (lois agrégées par
     couronne, découpages de zones fines) « n'est pas tranché à ce jour ». La cohorte sort de la
     chaîne de synthèse eqasim, qui lit l'enquête : son statut est celui des autres ressources
     dérivées, et aucun engagement de diffusion n'est pris ici (relecture v1, item Q2 ;
     SOUMISSION_AAMAS_2027.md l. 81). -->

## 4.2 Le protocole en trois règles

Trois règles ferment trois manières de biaiser la comparaison entre un agent génératif et un
modèle tabulaire.

La règle 1 donne à chaque décideur les mêmes 21 variables. Douze décrivent la personne et son
ménage, trois le déplacement, six la géométrie (annexe B).

La règle 2 note la masse de probabilité qu'un décideur place sur chaque option, et non l'option
qu'il classe première. Le seul classement ferait partir dans le même mode tous les personas
d'un même profil.

La règle 3 restreint chaque prédiction tabulaire aux modes réellement proposés pour ce
déplacement, puis la renormalise à 100 %.

<!-- source: fr/04_Evaluation.md § 4.3, règles 1 à 3 : 21 variables (12 personne et ménage,
     3 déplacement, 6 géométrie), scripts/progedo_logit/feature_spec.json ; masse de probabilité
     comme grandeur scorée, justification Meister et al. (2024), « retenir le mode le plus
     probable ferait partir dans le même mode tous les personas d'un même profil » ;
     renormalisation sur l'offre, probabilités écrites avant et après correction. Six options
     au plus par déplacement (experience.yaml, max_candidats: 6). -->

Nous égalisons les 21 variables, non l'information que chaque côté détient. L'agent reçoit
trois choses qu'aucun modèle tabulaire ne peut recevoir. Il voit l'agenda de ses trajets
restants, la météo des heures à venir, et chaque itinéraire étape par étape. Les références
tabulaires ont reçu ce que l'agent n'a jamais reçu, les 39 203 déplacements d'enquête sur
lesquels elles ont été estimées. L'asymétrie d'exposition joue en sens inverse, ce qui en fait
des références hautes.

<!-- source: fr/04_Evaluation.md § 4.3, deuxième et troisième paragraphes de la règle 1 :
     persona.py, champs agenda, day_outlook et trajectories ; exposition tabulaire
     mode_choice_policy_metrics.json, training.n_fit 31 279 + training.n_valid 7 924 = 39 203,
     les 13 045 trajets de test hors compte. « Le protocole égalise les 21 variables ; l'agent
     reçoit davantage d'information. » -->

## 4.3 Ce qui est mesuré

Nous mesurons à deux échelles, la part modale de la cohorte et l'accord sur chaque déplacement.
La part modale est la part des déplacements faits en voiture, en transports collectifs, à pied
et à vélo. L'enquête donne la part de référence, globalement et dans chacune de cinq strates,
une strate étant une tranche de la population ou des déplacements.

<!-- source: fr/04_Evaluation.md § 4.2 : quatre modes scorés, référence EMC² 2023 recalculée
     pour chaque strate — classe d'âge, occupation, genre, motif du déplacement, classe de
     distance —, puis agrégée en composite. Les cinq strates ne sont pas énumérées ici, faute
     de place ; elles sont nommées au § 5 et en annexe C. -->

Un seul nombre composite porte la lecture agrégée. Il ajoute à la divergence globale la moyenne
pondérée des divergences de chaque strate.
$$\mathcal{C}_{\text{EMD–JSD}} = \mathrm{JSD}^{\text{global}} + \sum_{d\ \text{nominal}} w_d\,\overline{\mathrm{JSD}}^{\,d} + \sum_{d\ \text{ordinal}} w_d\,\overline{\mathrm{EMD}}^{\,d}$$

La divergence est celle de Jensen-Shannon sur les strates nominales, et la distance de
transport optimal sur les strates ordonnées, qui respecte l'ordre des classes. Un composite
plus bas signifie une répartition plus proche de l'enquête.

<!-- source: fr/04_Evaluation.md § 4.2, formules et poids : prompt_calibration/calibration/
     metrics.py, WEIGHTS (global 1.0, âge 0.5, occupation 0.5, motif 0.5, genre 0.3,
     distance 0.3), STRATUM_MIN_PERSONAS = 5 ; la barre est la moyenne non pondérée sur les
     catégories de la strate, les catégories de moins de cinq personas étant écartées. Ce
     dernier détail et les trois autres métriques vivent en annexe C. -->

Une autre lecture accompagne le composite, et les deux sont publiées ensemble : l'erreur
L1 sur les parts globales, la somme des écarts absolus en points de pourcentage.

<!-- source: colonnes du tableau du § 6.1 des masters : composite.emd_jsd,
     composite.emd_jsd_hors_choix_unique, global.l1 ; définition de l'erreur L1,
     fr/04_Evaluation.md § 4.2 ; lecture hors choix unique reprise du ticket 047, « quand un
     seul itinéraire est proposé, le décideur n'est pas interrogé ». ⚠ Aucun master ne définit
     cette lecture en prose : elle n'y est qu'un en-tête de colonne. La phrase ci-dessus est
     écrite ici pour la première fois. -->

Un écart entre deux décideurs ne compte que s'il dépasse ce qu'une nouvelle cohorte
déplacerait. Une autre cohorte de 1 000 personas de même construction déplacerait un composite
de ±1,3 point. La résolution varie selon le décideur, de 0,9 point pour les conditions réglées
et tabulaires à 2,1 pour celles à prompt minimal. Les déplacements d'une même personne ne sont
pas indépendants, si bien que chaque intervalle vient d'un rééchantillonnage par grappe au
niveau de la personne. Une différence appariée compare deux décideurs sur les personnes que
tous deux notent, à 95 %.

<!-- source: résolution recalculée le 2026-09-22 sur le jeu corrigé du ticket 088 (relecture
     v1, items G5 et Q3) : douze bras, 2 000 rééchantillonnages par grappe au niveau de la
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

L'audit unitaire pose l'autre question, sur les journées que les enquêtés ont réellement
décrites. Il porte sur 9 621 déplacements de 2 930 enquêtés, chacun portant son mode déclaré.
Nous publions l'exactitude, l'entropie croisée, puis le rappel et la précision par mode.
L'entropie croisée baisse à mesure qu'un décideur accorde plus de probabilité au mode déclaré.
Le rappel est la part des déplacements déclarés d'un mode qu'il désigne.

<!-- source: fr/05_Protocol.md § 5.4 : 2 930 personnes, 9 621 déplacements portant le mode
     déclaré, offre reconstruite par les mêmes moteurs, contrainte de chaîne appliquée ;
     grandeurs publiées, fr/04_Evaluation.md § 4.2, « exactitude, entropie croisée mesurée sur
     les décisions que tous les décideurs comparés notent, puis le rappel et la précision par
     mode ». -->

## 4.4 Planchers, références, décideurs

Trois planchers donnent le niveau qu'un décideur atteint sans connaissance comportementale. Le
premier tire uniformément sur les options proposées, le deuxième met tout sur la voiture, mode
majoritaire du territoire. Le troisième, l'heuristique de durée minimale, retient l'itinéraire
le plus rapide proposé.

<!-- source: fr/05_Protocol.md § 5.3 : hasard uniforme (1/|O_i|), a priori empirique sur le
     mode majoritaire du territoire, heuristique de durée minimale sur les graphes de
     transport. -->

Quatre références tabulaires donnent le niveau qu'atteint une estimation sur l'enquête. Ce sont
un logit multinomial, le modèle de choix discret usuel, un gradient boosté, une régression
logistique à noyau et une forêt aléatoire. Nous estimons les quatre à parité stricte, sur le
même découpage de l'enquête. Aucune ne mène sur les deux lectures, si bien que le plafond se
lit lecture par lecture.

<!-- source: fr/04_Evaluation.md § 4.4 : quatre méthodes ajustées sur les microdonnées de
     l'enquête, parité stricte (même fichier, même découpage par ménage, mêmes poids de
     redressement, même encodage, mêmes métriques issues d'un module partagé) ; « aucune
     méthode ne mène sur les trois axes » ; « le plafond se lit axe par axe : sur chacun, le
     meilleur score du tableau ». Gradient boosté = LightGBM (Ke et al., 2017) ; noyau RBF et
     approximation de Nyström pour la régression logistique à noyau. -->

Trois familles de décideurs sont sous test. Le prompt minimal donne à un modèle de langue les
faits du déplacement et le format de sortie, sans critères généraux. Le prompt expert garde ce
format et attire l'attention du modèle sur quatre critères généraux. Deux portent sur le
confort, la marche et l'attente qu'ajoutent vraiment les transports en commun, et le rythme
tranquille d'un voyageur âgé. Les deux autres portent sur des contraintes, des sacs de courses
lourds à porter et une journée de travail sans marge. La troisième famille est un classifieur
zéro-shot à sortie typée (TypeSafe System One, jev-1.13.0). Il lit ce même texte et rend une
probabilité par option sans écrire une phrase.

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
     (R12), rendu en français par « critères généraux » ; le prompt est dit attirer
     l'attention du modèle sur ces critères. Les quatre puces sont rendues dans le registre
     du résumé de l'auteur : confort pour la friction de chaîne et l'autonomie des personnes
     âgées, contrainte pour la logistique de portage et le temps de vie des actifs. Aucune
     n'est une opportunité.
     ⚠ prompt_expert_32, réglée POUR le classifieur typé, porte une cinquième notion
     (exposition réelle à la météo, puce « Chain friction » réécrite à deux versants). Les
     quatre principes énoncés ici sont ceux du prompt servi aux modèles de langue ; le
     § 5.3 mesure la consigne du classifieur sans la décrire. Signalé au compte-rendu.
     fr/06_Empirical_Evaluation.md l. 21 pour le classifieur à sortie typée, « qui rend une
     probabilité par option sans produire de texte ». Les trois consignes lui sont servies
     amputées de leur bloc de sortie, le type Choice le remplaçant. Identité du décideur :
     docs/tickets/ticket_096_jev_typesafe_troisieme_famille_de_decideur.md § 1,
     « classifieur zéro-shot à sortie typée », modèle jev-1.13.0, POST
     https://api.typesafe.ai/v1/systemone ; « zéro-shot » est porteur, ce décideur n'ayant
     rien vu de Toulouse, ce qui fonde la clause « se passe d'enquête locale » du § 7.1.
     Modèles de fondation :
     gemini-3.1-flash-lite, gemini-3.5-flash-lite, mistral-large-2512, jev-1.13.0. -->

Nous avons obtenu le prompt expert par mutations successives d'un texte unique, sous une seule
contrainte. Son texte ne contient ni seuil chiffré ni formule. Chaque itération lit les écarts
par strate du prompt en service, propose une réécriture ciblée, et la retient quand le mode
sur-représenté reflue. Chaque réécriture est évaluée, comme toute évaluation ici, selon la
masse de probabilité de la règle 2. Le texte a été réglé contre un seul modèle de
langue sur une population de calibration séparée, puis servi tel quel aux autres (annexe D).

<!-- source: fr/05_Protocol.md § 5.2.2 pour la procédure de mutation (écarts par strate,
     hypothèse sur le mécanisme, rejeu apparié contre un bras témoin, motif du rejet consigné)
     et § 5.2.3 pour les trois garde-fous (aucun seuil chiffré, aucune étiquette d'enquête,
     mesure sur les distributions verbalisées, le tirage dispersant chaque part de ±1,7 point ;
     l'article court n'en garde qu'une depuis le 2026-09-24, « ni seuil chiffré ni formule »,
     et renvoie la notation à la règle 2, cf. 04_bench.en.md) ;
     fr/06_Empirical_Evaluation.md l. 25 pour la provenance : « prompt_expert_05 a été réglé
     contre gemini-3.5-flash-lite sur une population de calibration tirée séparément de la
     cohorte scellée, puis soumis tel quel aux autres porteurs ».
     ⚠ CONTRADICTION ENTRE MASTERS, signalée au compte-rendu. fr/05_Protocol.md § 5.2.3, daté du
     21 septembre, écrit l'inverse : « les écarts qui pilotent les mutations ont été lus sur la
     cohorte scellée du chapitre 4 elle-même… Les scores du prompt expert rapportés au
     chapitre 6 sont donc des scores en échantillon. » Le texte ci-dessus suit le master du
     22 septembre, le PLAN § 4.4 et le § 5.2 déjà rédigé ; il est faux si c'est le master du
     21 septembre qui fait foi. -->

La consigne du classifieur a été réglée sur la première cohorte. Chaque croisement de modèles
et de consignes est donc mesuré sur une seconde cohorte, qui ne partage aucun persona avec la
première.

<!-- source: fr/06_Empirical_Evaluation.md l. 23 et l. 25 (prompt_expert_32 muté sur les écarts
     par strate de Jev lus sur la cohorte qui le note, six textes mesurés, cinq écartés) ;
     ticket 103 § 0 et lot A pour la seconde cohorte, data/population/population_1000_AAMAS_v6_c2
     et son jeu, « sans un seul persona commun avec c1 », « aucun prompt n'a été réglé sur c2 :
     tout ce qui s'y mesure est hors échantillon, pour les deux modèles à la fois ». La réserve
     « en échantillon » est portée par le libellé de ligne du tableau 1, et nulle part ailleurs
     (relecture v1, § 9 bis). -->

*Tableau 1 — Les quinze décideurs sur les deux lectures, avec l'étendue inter-graines là où
elle a été mesurée.*

| Décideur | Composite | L1 sur les parts globales | Étendue inter-graines |
|---|---:|---:|---|
| Hasard uniforme | 50,16 | 86,80 | déterministe |
| Tout-voiture | 30,73 | 58,00 | déterministe |
| Durée minimale | 26,97 | 53,62 | déterministe |
| Prompt minimal, mistral-large | 14,75 | 44,71 | non rejoué |
| Prompt minimal, classifieur à sortie typée | 13,75 | 42,76 | non rejoué |
| Prompt minimal, gemini-3.1 | 12,38 | 39,88 | non rejoué |
| Prompt minimal, gemini-3.5 | 7,02 | 24,08 | [replay pending] |
| Prompt expert, gemini-3.1 | 8,98 | 31,25 | non rejoué |
| Prompt expert, mistral-large | 7,63 | 26,64 | non rejoué |
| Prompt expert, gemini-3.5 | 4,86 | 13,85 | 0,56 |
| Logit multinomial | 4,02 | 8,99 | déterministe |
| Forêt aléatoire | 4,09 | 5,28 | déterministe |
| Prompt expert, classifieur à sortie typée (en échantillon) | 3,65 | 10,48 | [replay pending] |
| Régression logistique à noyau | 3,61 | 6,69 | déterministe |
| Gradient boosté | 3,60 | 9,49 | déterministe |

<!-- source: fr/06_Empirical_Evaluation.md § 6.1, tableau des quinze décideurs (scores.json,
     composite.emd_jsd, composite.emd_jsd_hors_choix_unique, global.l1 ; jeu corrigé du
     ticket 088). Étendue inter-graines 0,56 : § 6.5, graines 42 / 123 / 789, composites
     4,857 / 4,646 / 4,299. [replay pending] = les deux décideurs dont le ticket 103, lot B, doit rejouer
     les graines 123 et 789. « not replayed » = aucune graine supplémentaire jouée, l'effet de
     la graine sur ces lignes n'étant pas mesuré. La ligne « Expert prompt, typed classifier »
     est prompt_expert_32, en échantillon, et ne concourt à aucun classement. -->

Tous les scores qui suivent sortent de ce banc, à commencer par la journée ordinaire que
l'enquête décrit.

<!--
=== SECTION REPORT ===
Section        : 04 — Le banc de comparaison (rendu français de 04_bench.en.md)
File           : docs/paper/article-court/sections/04_bench.fr.md
Words / budget : 1 090 mots de prose, contre 1 014 à l'anglais (+7,5 %, dilatation ordinaire
                 du français). Budget PLAN § 4 = 900 mots : +21,1 %, quand l'anglais vaut
                 +12,7 %. Un resserrement du français ne se décide pas au rendu ; il suivra
                 celui de l'anglais, les coupes se décidant sur la langue qui fait foi.
Skeleton       : Nous comparons quinze décideurs sur une même cohorte, sous un même protocole, avec un même jeu de mesures.
                 Tous les scores de cet article viennent d'une même cohorte scellée de 1 000 personas synthétiques.
                 Treize marges de la cohorte sont contrôlées contre l'enquête.
                 La cohorte se déplace un peu moins que la population de l'enquête.
                 Notre convention de recherche interdit de transmettre les microdonnées de l'enquête.
                 Trois règles ferment trois manières de biaiser la comparaison entre un agent génératif et un modèle tabulaire.
                 La règle 1 donne à chaque décideur les mêmes 21 variables.
                 La règle 2 note la masse de probabilité qu'un décideur place sur chaque option.
                 La règle 3 restreint chaque prédiction tabulaire aux modes réellement proposés pour ce déplacement.
                 Nous égalisons les 21 variables, non l'information que chaque côté détient.
                 Nous mesurons à deux échelles, la part modale de la cohorte et l'accord sur chaque déplacement.
                 Un seul nombre composite porte la lecture agrégée.
                 La divergence est celle de Jensen-Shannon sur les strates nominales, et la distance de transport optimal sur les strates ordonnées.
                 Une autre lecture accompagne le composite, et les deux sont publiées ensemble.
                 Un écart entre deux décideurs ne compte que s'il dépasse ce qu'une nouvelle cohorte déplacerait.
                 L'audit unitaire pose l'autre question, sur les journées que les enquêtés ont réellement décrites.
                 Trois planchers donnent le niveau qu'un décideur atteint sans connaissance comportementale.
                 Quatre références tabulaires donnent le niveau qu'atteint une estimation sur l'enquête.
                 Trois familles de décideurs sont sous test.
                 Nous avons obtenu le prompt expert par mutations successives d'un texte unique, sous trois contraintes.
                 La consigne du classifieur a été réglée sur la première cohorte.
                 Tous les scores qui suivent sortent de ce banc, à commencer par la journée ordinaire que l'enquête décrit.
                 Le squelette français répond ligne pour ligne au squelette anglais.
Checker        : verifier_forme.py sort 0 après les corrections de l'auteur du 2026-09-22 ;
                 --squelette lu d'une traite. Les quatre critères généraux se nomment
                 désormais en deux phrases de deux termes, comme à l'anglais, ce qui satisfait
                 aussi la règle R1 sur les énumérations de plus de trois termes. La phrase
                 unique de quatre termes a disparu, et avec elle le choix assumé consigné à la
                 passe précédente. Une seule reprise avait été
                 nécessaire au rendu initial : la phrase de la règle 1 comptait 28 mots en français
                 (24 en anglais) et a été coupée en deux (R1), sans perte de sens. Les motifs
                 R5 du script sont anglais ; relecture manuelle des clivées françaises :
                 aucune. R2 : un deux-points au plus par paragraphe, aucun en corps de texte
                 hors commentaires de source.
Terms defined here : persona (4.1) ; marge (4.1) ; part modale, part de référence et strate
                 (4.3) ; composite, divergence de Jensen-Shannon et distance de transport
                 optimal (4.3) ; erreur L1 sur les parts globales (4.3) ; entropie croisée et
                 rappel (4.3) ; plancher et référence tabulaire (4.4) ; prompt minimal,
                 prompt expert, critères généraux et classifieur à sortie typée (4.4) ; en échantillon (4.4,
                 par l'usage, au libellé du tableau 1).
Terms used, undefined upstream : aucun. « décideur » est défini au § 1.3 ; « enquête
                 ménages-déplacements » est glosée au § 1.1.
Figures cited  : tous les chiffres de l'anglais, aux mêmes places, avec la même unité et la
                 même réserve ; seule la typographie change (espace de milliers, virgule
                 décimale). 1 000 personas, 499 ménages, vivier de 11 329, 453 communes ;
                 treize marges, borne d'un point, écart maximal 0,50 point ; 3,30 / 3,69
                 contre 3,53 / 3,95 et 3 299 déplacements ; 21 variables ; 39 203 déplacements
                 d'enquête ; ±1,3 point de résolution, de 0,9 à 2,1 selon le décideur, valeur
                 recalculée le 2026-09-22 (commentaire de source conservé intact) ; 9 621
                 déplacements de 2 930 enquêtés ; les quarante-cinq scores du tableau 1 et
                 l'étendue inter-graines de 0,56.
Placeholders   : deux cellules [replay pending] au tableau 1 et le libellé « (en
                 échantillon) », laissés tels quels dans l'attente du lot B du ticket 103.
                 Le libellé anglais est conservé mot pour mot, pour qu'il se retrouve par
                 recherche dans les deux langues.
Left out       : rien de plus que l'anglais ; le rendu ne retranche ni n'ajoute.
Flags for the author :
  1. Les huit signalements du compte-rendu anglais restent ouverts, à commencer par la
     contradiction entre masters sur le réglage du prompt expert (fr/05_Protocol.md § 5.2.3
     du 21 septembre contre fr/06_Empirical_Evaluation.md du 22 septembre). Le rendu suit
     l'anglais et ne tranche pas.
  2. Les commentaires de source sont repris à l'identique, comme demandé. Ils portent donc
     encore des séparateurs de milliers à l'anglaise (« 3 299 déplacements », « 13 045
     trajets », « 2 000 rééchantillonnages », « 31 279 + 7 924 = 39 203 »), qui se lisent
     comme des décimales dans un fichier français. Le corps du texte, lui, est converti.
  3. « renormalise à 100 % » rend « rescales it to 100 % ». L'anglais évitait de nommer la
     renormalisation pour le lecteur non transporteur ; en français, le verbe est celui des
     masters (§ 4.3, règle 3) et reste transparent. Écart de vocabulaire assumé, à confirmer.
  4. « equivalence bound » est rendu « borne d'indifférence », terme du master
     fr/04_Evaluation.md § 4.1 pour cette borne même, plutôt que le calque « borne
     d'équivalence ». Le test reste un test d'équivalence ; la borne, elle, porte ce
     nom-là en français.
  5. « modal split » est rendu « part modale », comme l'impose la table de terminologie. Les
     masters écrivent plutôt « répartition modale » quand la grandeur désigne la distribution
     entre les quatre modes, et « part » pour un mode isolé. La phrase de définition du § 4.3
     s'en ressent un peu.
  6. Terme retenu pour tout le papier, celui de l'auteur, repris de son résumé du
     2026-09-22 : « general criteria » est rendu par « critères généraux ». Il remplace les
     « principes situationnels » de la passe précédente, qui étaient une invention de l'agent
     et tiraient contre le résumé. « Principes d'arbitrage » reste écarté, l'anglais ayant
     abandonné « arbitration », calque d'« arbitrage » visé par R11, et le mot gardant au
     § 6.3 son sens ordinaire, collision que R12 interdit. L'adjectif « généraux » est gardé
     aux cinq occurrences du corps : il sépare ces critères, valables pour tout déplacement,
     des faits du déplacement que le prompt minimal porte déjà.
  7. Le prompt expert n'ajoute plus « quatre principes d'arbitrage qualitatifs » : son en-tête
     s'intitule « Situational trade-off principles » et ses puces nomment des circonstances
     vécues. Il attire désormais l'attention du modèle sur quatre critères généraux, que deux
     phrases nomment. Le § 4.4 est le seul endroit du papier qui le fasse ; le § 5 s'y réfère
     sans les relister.
  8. Deux prompts experts existent et ils diffèrent. Le texte servi aux modèles de langue
     porte quatre critères ; la variante réglée pour le classifieur typé en porte une
     cinquième, l'exposition réelle à la météo. Le « quatre » du papier est donc vrai du
     prompt des modèles de langue. Aucune clause n'a été ajoutée, l'anglais n'en ajoutant pas.
  9. Le classifieur reçoit son identité de produit à sa première occurrence, « classifieur
     zéro-shot à sortie typée (TypeSafe System One, jev-1.13.0) ». « Zéro-shot » est porteur :
     ce décideur n'a rien vu de Toulouse, ce qui fonde la clause « se passe d'enquête locale »
     du § 7.1. Partout ailleurs le texte garde « classifieur à sortie typée ».
 10. Le § 4 passe à 1 090 mots contre 900 au budget, soit +21,1 %, hors de la fourchette de
     ±15 %. L'anglais, lui, tient à +12,7 %. L'écart vient de la dilatation du français et non
     d'un ajout ; il se règle sur l'anglais, la langue qui fait foi. Nommer les quatre
     critères généraux en deux phrases a coûté vingt-trois mots au français et dix-huit à
     l'anglais.
=== FIN ===
-->
