# 5. Résultats au régime nominal

<!-- Rendu français de 05_results.en.md, article court AAMAS 2027, PLAN.md § 5.
     Rendu le 2026-09-22 par l'agent article-writer, consigne R17 : l'anglais fait foi,
     le français en est le rendu fidèle. Mêmes coupes de paragraphe, mêmes chiffres,
     mêmes réserves, mêmes emplacements. Les écarts de découpage de phrase imposés par
     la longueur française sont listés au compte-rendu.
     Les chiffres marqués [c2] sont des emplacements nommés, autorisés par l'auteur pour
     cette livraison seulement, dans l'attente des scores du ticket 103. -->

<!-- source: data/experiences/exp_*_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_*/executions/*/scores.json ;
     cohorte population_1000_AAMAS_v6, jeu …_20260316_EN_c, formule v1_reference (0aeee565…),
     référentiel EMC² 2023 (9ac34597…). 3 154 décisions sur 3 299 attendues, 868 personnes mobiles. -->

Le régime nominal est une journée simulée ordinaire, celle que décrit l'enquête
ménages-déplacements, sans perturbation. Quatre constats sortent de cette journée.

1. Les quinze décideurs se séparent en cinq groupes. Aucun agent génératif ne dépasse les
   quatre références tabulaires.
2. Le réglage des critères généraux retrouve l'effet de la distance et laisse les deux
   modes minoritaires où il les a trouvés.
3. Un classifieur à sortie typée, qui n'écrit aucun texte, atteint la même bande pour un
   cinquantième du coût.
4. Deux décideurs que l'agrégat ne distingue pas diffèrent sur un déplacement sur trois.

## 5.1 Quinze décideurs sur une échelle

Les quinze décideurs se répartissent sur l'axe du composite en cinq groupes disjoints
(figure 2). Un composite plus bas signale une distribution plus proche de celle de l'enquête.
Les trois planchers occupent le haut de l'échelle, de 27,0 pour l'heuristique de durée
minimale à 50,2 pour un tirage uniforme sur les options offertes. Les quatre décideurs sous
prompt minimal se placent entre 7,0 et 14,8. Sous prompt expert, les trois modèles de langue
se placent entre 4,9 et 9,0. Les quatre références tabulaires tiennent dans un demi-point, de
3,60 à 4,09.

<!-- source: fr/06_Empirical_Evaluation.md § 6.1, tableau des quinze décideurs et sa légende
     (scores.json, composite.emd_jsd). Hasard uniforme 50,16 ; tout-voiture 30,73 ; durée
     minimale 26,97 ; prompt minimal 7,02 à 14,75 ; prompt expert LLM 4,86 à 8,98 ; tabulaires
     3,60 à 4,09. ⚠ La légende du master annonce « un facteur douze » entre le plancher aléatoire
     et le meilleur composite ; 50,16 / 3,60 vaut 13,9. Le rapport n'est pas repris ici. -->

Le prompt minimal se situe déjà sous le meilleur des trois planchers. La pire des quatre
conditions à prompt minimal vaut 14,8, contre 27,0 pour l'heuristique de durée minimale, qui
retient l'option la plus rapide offerte. Un modèle qui reçoit les faits d'un déplacement, sans
critères généraux, porte donc une information comportementale. Cette information n'est pas
celle qu'encode l'heuristique physique.

Sur deux versions d'une même famille de modèles, le modèle de fondation pèse autant que la
consigne qu'il porte. Servi tel quel à un second modèle du même fournisseur, le texte expert
laisse 4,15 points de composite entre les deux, intervalle [+2,99 ; +5,43].

<!-- source: fr/99_annexes.md, annexe H.1, ligne « gemini-3.1 − gemini-3.5, prompt expert » :
     +4,15 [+2,99 ; +5,43] composite, +5,56 [+4,12 ; +7,02] hors choix unique, +17,4 L1.
     2 000 réplicats, graine 2026, rééchantillonnage par grappe sur 868 personnes communes. -->

Rejouer une condition sous trois graines déplace son composite moins que ne le fait la cohorte
elle-même. La condition gemini-3.5 réglée obtient 4,86, 4,65 et 4,30 sur la même cohorte et le
même jeu d'évaluation. L'étendue vaut 0,56 point, contre une résolution de cohorte de
±1,3 point. La condition à prompt minimal n'a pas été rejouée sous ces graines. L'effet de la
graine sur le signe des différences appariées rapportées ici n'est donc pas mesuré. Les
étendues entre graines des autres décideurs clés valent [c2, étendue entre graines par
décideur clé].

<!-- source: fr/06_Empirical_Evaluation.md § 6.5 et son commentaire (ticket 073, axe 1) :
     graines 42, 123 et 789, composites 4,857 / 4,646 / 4,299, étendue 0,56 ; hors choix unique
     6,86 à 5,98 ; L1 13,85 à 11,97. Résolution de cohorte ±1,3 point : valeur recalculée le
     2026-09-22 sur le jeu corrigé du ticket 088, douze bras, 2 000 rééchantillonnages par
     grappe, graine 2026 (demi-largeur médiane 1,33) ; provenance complète au § 4.3. La
     demi-largeur du bras comparé ici, gemini-3.5 sous prompt expert, vaut 1,22, donc
     l'étendue de 0,56 reste sous la résolution de son propre bras.
     Réserve du master reprise telle quelle : le bras minimal n'a pas été rejoué. -->

*Figure 2 — Cinq groupes se séparent sur l'axe du composite, et le prompt minimal passe déjà
sous le plancher physique.*

## 5.2 Ce que le réglage déplace, et ce qu'il ne déplace pas

Régler les instructions qui soulignent les critères généraux améliore chaque modèle de
langue, de plus que ne bougerait une cohorte à elle seule (tableau 2). Le gain apparié sur le composite vaut
2,27 points pour gemini-3.5, intervalle [+1,40 ; +3,22], puis 3,37 points pour gemini-3.1 et
7,25 pour mistral-large. Les trois intervalles excluent zéro sur les deux lectures. Les gains
vont de une fois et demie à cinq fois et demie la résolution de cohorte.

*Tableau 2 — Gains appariés du prompt expert sur le prompt minimal, deux lectures,
intervalles à 95 %. Tous les intervalles excluent zéro.*

| Modèle de langue | Composite | L1 parts globales |
|---|---|---|
| gemini-3.5 | 2,27 [1,40 ; 3,22] | 10,2 [8,0 ; 12,5] |
| gemini-3.1 | 3,37 [2,45 ; 4,25] | 8,6 [6,8 ; 10,6] |
| mistral-large | 7,25 [5,90 ; 8,67] | 18,0 [13,5 ; 22,4] |

<!-- source: fr/99_annexes.md, annexe H.1, trois premières lignes, signes retournés en gains
     (un gain positif est une erreur plus faible). 2 000 réplicats, graine 2026, 868 personnes
     communes, tous les décideurs sur le jeu corrigé du ticket 088. -->

Le réglage crée une pente plutôt qu'un décalage de niveau (figure 3). Sous un kilomètre, la
part voiture de gemini-3.5 ne bouge pas, 9,7 % avant réglage et 10,1 % après. Entre un et
cinquante kilomètres, elle monte de six à sept points dans chaque tranche. La plus basse de
ces tranches passe de 37,7 à 43,4 %, la plus haute de 74,9 à 80,8 %. Au-delà de cinquante
kilomètres, sur dix-sept déplacements, elle recule de deux points. L'agent réglé porte alors
moins d'erreur le long de la distance que toute référence tabulaire, 14,2 points pondérés
contre 16,8 pour la forêt aléatoire. La distance est la seule dimension où un agent y
parvient.

<!-- source: fr/06_Empirical_Evaluation.md § 6.3 et son commentaire : part voiture
     prompt_minimal_02 → prompt_expert_05, 9,7 → 10,1 ; 37,7 → 43,4 ; 51,1 → 58,4 ;
     60,0 → 65,9 ; 67,5 → 74,1 ; 74,9 → 80,8 ; 63,8 → 61,8 (plus de 50 km, n = 17).
     Erreur L1 pondérée sur la dimension distance : 14,19 agent réglé, 16,79 forêt aléatoire,
     17,79 gradient boosté. ⚠ Le PLAN annonce un prompt minimal « plat entre 40 et 50 % » face
     à une cible montant « de 18 à 77 % » : aucune de ces deux courbes n'est dans les masters,
     et la source ci-dessus montre une pente. L'énoncé est remplacé par ce qui est mesuré. -->

Deux erreurs coexistent dans le même décideur, dont une seule répond à la consigne. Les trois
modèles de langue placent la part du vélo entre 6,8 et 8,1 %, là où l'enquête en compte 4,1 %.
Le réglage ne déplace cette part que de un à huit dixièmes de point. Sur les mêmes conditions,
le réglage fait reculer les transports collectifs de quatre à onze points. Une strate résiste
à tous les décideurs, celle des 15–19 ans (annexe F).

<!-- source: fr/06_Empirical_Evaluation.md § 6.3, paragraphe des deux modes minoritaires
     (scores.json, detail.<dimension>.strates). Le pic TC des 15-19 ans — 47,4 % dans
     l'enquête, 20,8 % pour l'agent réglé, 26,4 % pour la forêt aléatoire, légende de la
     figure 6.4 — part à l'annexe F (résultats par strate), relecture v1 F2. -->

*Figure 3 — Le réglage donne à l'agent une pente sur la distance, les déplacements les plus
courts restant où le prompt minimal les laissait.*

## 5.3 La délibération ne décide pas

Le classifieur à sortie typée atteint la bande des quatre références tabulaires. Son composite
sur la seconde cohorte vaut [c2, composite hors échantillon du classifieur], contre 3,60 à
4,09 points pour les quatre références tabulaires. Les différences appariées avec ces quatre
références valent [c2, quatre différences appariées avec leurs intervalles à 95 %].

<!-- source: ticket 103, lot A. Aucun chiffre en échantillon dans ce paragraphe, par consigne
     du PLAN § 5.3. Le score en échantillon du bras réglé sur la cohorte qui le note (3,65)
     n'entre pas ici et vit à l'annexe. Bande tabulaire 3,60-4,09 : fr/06_Empirical_Evaluation.md
     § 6.1. -->

La seconde cohorte croise deux modèles et trois consignes, sans partager un persona avec la
première. Chaque case est donc hors échantillon, y compris la consigne réglée pour le
classifieur. Le croisement répond à deux questions à la fois. Il mesure ce que la consigne du
classifieur fait à un modèle génératif, et l'inverse. Les six cases valent [c2, composite de
chaque case du croisement deux par trois].

<!-- source: ticket 103, Q2 et lot A. Carré 2 modèles × 3 consignes sur une seconde cohorte
     sans persona commun avec population_1000_AAMAS_v6. -->

Nous lisons ces scores comme plaçant la connaissance utile dans la lecture du contexte, et non
dans la justification rédigée ensuite. Le débat publié sur le raisonnement écrit rapporte des
gains sur des tâches à réponse vérifiable. Une part modale n'a pas de réponse vérifiable
déplacement par déplacement. Dans nos mesures, la génération de texte n'a pas contribué à la
fidélité agrégée. Nous énonçons cela comme un résultat sur ce banc, non comme une propriété
des modèles de langue.

À charge égale de 23 026 décisions, le classifieur coûte 1,06 dollar contre 49,28, soit un
facteur d'environ cinquante.

<!-- source: fr/08_Limitations.md § 8.3 : 1,06 $ contre 49,28 $ à 23 026 décisions. Le
     rapport mesuré au § 9 des masters est de quarante-cinq à cinquante-six selon la charge.
     Le détail des jetons et du tarif — 1 050 jetons d'entrée contre 629, consigne renvoyée
     entière à chaque appel, 0,042 $/M en entrée et sortie non facturée — part à l'annexe I
     (coût d'inférence détaillé), relecture v1 § 9 bis. -->

## 5.4 L'agrégat ne dit pas l'individu

Deux décideurs que l'agrégat ne distingue pas diffèrent sur un déplacement sur trois. L'agent
réglé et le gradient boosté désignent un mode le plus probable différent sur 30,3 % des
déplacements. Tous deux voient au moins deux options sur ces déplacements. Entre méthodes
tabulaires, le même désaccord va de 8,4 à 11,0 %. La distance médiane entre deux distributions
d'agent vaut quatre fois celle entre deux distributions tabulaires, 40,0 points contre 9,8.

<!-- source: fr/99_annexes.md, annexe H.5 : accord 69,7 % agent / gradient boosté, 91,6 %
     gradient boosté / régression à noyau, 89,0 % gradient boosté / forêt aléatoire ;
     2 374 à 2 479 déplacements selon la paire.
     L1 médianes corrigées le 2026-09-22 (relecture v1, item F6). Agent contre agent : lignes
     367, 368, 371, 372 et 374 du tableau H.5, valeurs 40,0 / 40,0 / 34,0 / 44,0 / 10,0,
     médiane 40,0 ; la médiane reste 40,0 si l'on ne garde que les deux paires entre modèles
     de langue (40,0 et 40,0). Tabulaire contre tabulaire : lignes 363 et 364, 8,3 (gradient
     boosté / régression à noyau) et 11,3 (gradient boosté / forêt aléatoire), médiane 9,8.
     Les 39,0 et 8,3 de la version précédente étaient l'un une paire agent / tabulaire
     (ligne 365), l'autre la plus petite des deux lignes tabulaires. Rapport 40,0 / 9,8 = 4,1. -->

Sur les journées déclarées de l'enquête, l'agent désigne le mode déclaré un peu moins souvent
que les références tabulaires (tableau 3). L'audit porte sur 9 621 déplacements de
2 930 répondants, chacun portant le mode que son répondant a déclaré. L'agent réglé atteint
67,6 % d'exactitude contre 71,5 % pour le gradient boosté, soit un écart apparié de
3,87 points, intervalle [−5,47 ; −2,28]. Son écart au logit multinomial ne se sépare de zéro
ni sur l'exactitude ni sur l'entropie croisée.

*Tableau 3 — Accord unitaire sur les journées déclarées, sept décideurs. Exactitude et rappels
en %, entropie croisée sur les 5 229 décisions que notent tous les décideurs à distribution.*

| Décideur | Exactitude | Entropie croisée | Rappel vélo | Rappel marche |
|---|---|---|---|---|
| Gradient boosté | 71,5 | 0,299 | 20,4 | 63,4 |
| Logit multinomial | 68,6 | 0,358 | 18,3 | 60,0 |
| Durée minimale | 68,1 | — | 25,8 | 19,2 |
| Prompt expert, gemini-3.5 | 67,6 | 0,341 | 22,5 | 47,2 |
| Prompt minimal, gemini-3.5 | 64,8 | 0,384 | 24,1 | 44,2 |
| Classifieur à sortie typée, consigne propre (en échantillon) | 64,7 | 0,464 | 18,1 | 56,3 |
| Classifieur à sortie typée, consigne transférée | 64,3 | 0,509 | 16,9 | 63,1 |

<!-- source: fr/06_Empirical_Evaluation.md § 6.4 et fr/99_annexes.md I.1 et I.2. Deux bras
     du classifieur, séparés sur demande de la relecture v1 (F4) : « consigne transférée » =
     la ligne « Jev, consigne gemini-3.5 », hors échantillon (64,3 / 0,509 / 16,9 / 63,1) ;
     « consigne propre » = la ligne « Jev, prompt expert », en échantillon dans le master et
     portée ici avec sa réserve (64,7 / 0,464 / 18,1 / 56,3, annexes I.1 et I.2).
     Différences appariées : annexe I.1 bis,
     prompt expert − gradient boosté −3,87 [−5,47 ; −2,28], prompt expert − logit multinomial
     −0,98 [−2,61 ; +0,58] et −0,018 [−0,039 ; +0,003]. -->

Les deux consignes placent le classifieur à sortie typée sous le plancher tout-voiture sur
l'exactitude individuelle. Sa consigne propre atteint 64,7 %, en échantillon, et la consigne
transférée de gemini-3.5 atteint 64,3 %, là où le plancher atteint 66,7 %. Les écarts appariés
à ce plancher valent 2,04 points, intervalle [−3,78 ; −0,29], et 2,42 points, intervalle
[−4,26 ; −0,62]. Aucune comparaison appariée ne sépare le bras transféré des quatre références
tabulaires sur le composite. L'autre lecture agrégée (L1) le place derrière la
régression à noyau et la forêt aléatoire. Sa masse de probabilité va à la marche plutôt qu'aux
transports collectifs, 63,1 % de rappel contre 35,0 %. La part modale agrégée masque cet
échange. Une population peut donc restituer la part modale d'un territoire en se trompant,
déplacement par déplacement, plus souvent qu'une règle qui ne regarde rien.

<!-- source: fr/99_annexes.md I.1 bis, « Jev sous consigne gemini-3.5 − tout-voiture »
     −2,42 [−4,26 ; −0,62] et « Jev prompt expert − tout-voiture » −2,04 [−3,78 ; −0,29] ;
     I.1, tout-voiture 66,7 %, Jev prompt expert 64,7 % (en échantillon) ; I.2, rappels 63,1 % marche et
     35,0 % transports collectifs. Séparation sur l'agrégat : annexe H.1, quatre lignes
     « Jev sous consigne gemini-3.5 − <référence tabulaire> ». Sur le composite les quatre
     intervalles contiennent zéro ; hors choix unique et sur les parts globales, ceux de la
     régression à noyau et de la forêt aléatoire l'excluent. Le § 9 des masters écrit « aucune
     estimation appariée ne le sépare » sans nommer la lecture ; l'annexe H.1 le contredit sur
     deux lectures sur trois, et la phrase livrée ici nomme la lecture. -->

*Figure 4 — Rappel et précision par mode : le classifieur à sortie typée échange les
transports collectifs contre la marche. La part modale agrégée ne montre pas cet échange.*

Un décideur exact sur son propre échantillon de test peut malgré tout produire une
distribution moins bonne en simulation. Une variante reconstruisait sa distance d'entrée
depuis la durée déclarée et atteignait 93,4 % d'exactitude sur son propre échantillon de
validation de 13 918 déplacements. En simulation, elle perdait contre la variante qui gardait
sa distance mesurée, 9,28 contre 7,40 sur le composite. La distance reconstruite portait le
mode. Nous notons donc un décideur là où il sert, et non là où il est facile de le noter.

<!-- source: la variante est la politique LightGBM « Distance reconstruite depuis la durée »
     (spec_version 4), dont le code a été retiré du dépôt le 2026-08-31 ; seules ses mesures
     subsistent. Exactitude 93,4 % : docs/traces/2026-08-31_second_modele_19_features/
     mode_choice_policy_matrice_vitesse.json l. 277, metrics.accuracy_weighted =
     0.934496640244722, sur metrics.n_rows = 13 918 lignes du découpage de validation de la
     politique elle-même ; valeur redérivée à l'identique depuis confusion_matrix_weighted du
     même fichier (relecture v1, item F5). ⚠ Ce n'est PAS l'audit unitaire du § 4.3
     (9 621 déplacements, 2 930 répondants) : deux jeux d'évaluation distincts, d'où
     « its own held-out sample of 13 918 trips » plutôt que « on the survey ».
     Composites : docs/traces/2026-08-31_second_modele_19_features/scores_v4.json l. 171,
     variante matrice de vitesse à 19 variables 9,282153 contre la condition centroïde à
     21 variables 7,401081. La réserve « chiffres non recoupés » de fr/README.md l. 247 tombe.
     ⚠ Ces deux composites viennent d'un scorage antérieur au jeu corrigé du ticket 088 et ne
     se comparent pas aux 3,60-4,09 du tableau 1 ; la phrase ne les compare qu'entre eux. -->

Ces quatre constats valent sur la journée ordinaire que décrit l'enquête. Une enquête ne
tabule aucune autre journée, et la section suivante quitte ce régime pour un événement
qu'aucune variable n'encode.

<!--
=== SECTION REPORT ===
Section        : 05 — Résultats au régime nominal (rendu français)
File           : docs/paper/article-court/sections/05_results.fr.md
Words / budget : 1 404 mots de prose contre 1 346 à l'anglais (+4,3 %), budget PLAN 1 400 (+0,3 %)
Skeleton       :
  Le régime nominal est une journée simulée ordinaire, celle que décrit l'enquête ménages-déplacements, sans perturbation.
  Les quinze décideurs se répartissent sur l'axe du composite en cinq groupes disjoints (figure 2).
  Le prompt minimal se situe déjà sous le meilleur des trois planchers.
  Sur deux versions d'une même famille de modèles, le modèle de fondation pèse autant que la consigne qu'il porte.
  Rejouer une condition sous trois graines déplace son composite moins que ne le fait la cohorte elle-même.
  Régler les instructions qui soulignent les critères généraux améliore chaque modèle de langue, de plus que ne bougerait une cohorte à elle seule (tableau 2).
  Le réglage crée une pente plutôt qu'un décalage de niveau (figure 3).
  Deux erreurs coexistent dans le même décideur, dont une seule répond à la consigne.
  Le classifieur à sortie typée atteint la bande des quatre références tabulaires.
  La seconde cohorte croise deux modèles et trois consignes, sans partager un persona avec la première.
  Nous lisons ces scores comme plaçant la connaissance utile dans la lecture du contexte, et non dans la justification rédigée ensuite.
  À charge égale de 23 026 décisions, le classifieur coûte 1,06 dollar contre 49,28, soit un facteur d'environ cinquante.
  Deux décideurs que l'agrégat ne distingue pas diffèrent sur un déplacement sur trois.
  Sur les journées déclarées de l'enquête, l'agent désigne le mode déclaré un peu moins souvent que les références tabulaires (tableau 3).
  Les deux consignes placent le classifieur à sortie typée sous le plancher tout-voiture sur l'exactitude individuelle.
  Un décideur exact sur son propre échantillon de test peut malgré tout produire une distribution moins bonne en simulation.
  Ces quatre constats valent sur la journée ordinaire que décrit l'enquête.
Checker        : aucun constat (R1, R2, R4, R5, R11, R14 propres, code de sortie 0). R4, R5 et
                 R11 sont des motifs anglais et ne mordent pas sur ce fichier ; la relecture
                 les a contrôlés à la main. Aucune clivée « c'est … que », aucun terme de la
                 famille lexicale proscrite (« crucial » compris, qui existe en français)
Terms defined here     : consigne propre et consigne transférée du classifieur à sortie typée
                         (glosées au § 5.4, « la consigne transférée de gemini-3.5 »)
Terms used, undefined upstream : aucun. Dépend du § 4.4 pour décideur, plancher, référence
                 tabulaire, prompt minimal, prompt expert, classifieur à sortie typée,
                 composite, résolution de cohorte, et désormais pour « critères
                 généraux », que le § 4.4 définit et dont il nomme les quatre
Figures cited  : identiques à l'anglais, chiffre pour chiffre. Voir le commentaire de source
                 attaché à chaque paragraphe. Conversions typographiques appliquées au corps,
                 aux deux tableaux et aux quatre légendes : virgule décimale, espace des
                 milliers (23 026, 13 918, 9 621, 2 930, 5 229), intervalles [+1,40 ; +3,22].
                 Les commentaires de source gardent la typographie d'origine, par consigne
Placeholders   : quatre emplacements [c2] aux §§ 5.1 et 5.3, en attente des lots A et B du
                 ticket 103. Le libellé du premier emplacement du § 5.3 est raccourci en
                 « composite hors échantillon du classifieur » pour tenir la règle R1
Left out       : rien. Le rendu suit l'anglais paragraphe par paragraphe
Flags for the author : voir le compte-rendu de livraison (choix de terminologie, écarts de
                 découpage de phrase, problèmes de fond aperçus au rendu). Report de la
                 terme de l'auteur du 2026-09-22, repris de son résumé : « consigne
                 d'arbitrage » décrit mal le prompt expert, qui nomme des circonstances vécues
                 et non une manière de pondérer les options. Les trois occurrences du corps et
                 la ligne de squelette deviennent « critères généraux », terme que le § 4.4
                 définit et dont il nomme les quatre. Cette section ne les reliste pas (R8).
                 La formulation intermédiaire de la passe précédente, « principes
                 situationnels », a disparu de tout le papier. Tranché par l'auteur le
                 2026-09-24 : la phrase de tête du § 5.2 devient « Régler les instructions qui
                 soulignent les critères généraux », rendu de « Tuning the instructions that
                 highlight », au lieu de « le réglage des critères généraux », qui disait
                 qu'on règle les critères eux-mêmes. « Soulignent » plutôt que « mettent en
                 évidence » (résumé) : la seconde forme portait la phrase à 28 mots (R1). Le mot « arbitrage » reste
                 employé au § 6.3 dans son sens ordinaire, et la collision que R12 interdit
                 est ainsi évitée.
=== END SECTION REPORT ===
-->
