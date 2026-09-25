# 6. Évaluation empirique

<!-- Dernière mise à jour : 2026-09-17 -->

**Document :** chapitre 6 de l'article AAMAS 2027 — le chapitre de **résultats** : le chapitre 5 définit les conditions comparées, celui-ci dit ce que la comparaison établit.
**Statut :** `brouillon v0.14` (22 septembre 2026) — deux planches suivent les décisions de la `v0.13`. **Figure 6.2 :** les symboles disaient encore l'inverse du texte. Le prompt expert de Jev, publié au § 6.1, était dessiné en carré estompé parmi les variantes écartées, et la flèche s'arrêtait sur la consigne reçue de `gemini-3.5` ; il prend le disque plein des consignes publiées, la flèche finit sur lui, et une note de pied porte ce que le symbole ne dit plus, cette consigne ayant été réglée sur la cohorte qui la note. La consigne de `gemini-3.5` servie à Jev descend en carré, avec les autres variantes que le chapitre ne publie pas. **Figure 6.5 :** restreinte au plafond tabulaire et au prompt expert de chaque famille, trois séries au lieu de cinq ; les prompts minimaux et le plancher tout-voiture restent à l'annexe I. Sa légende suit. Aucun chiffre ne bouge. Ticket 101, retours de l'auteur du 22 septembre.
**Statut antérieur :** `brouillon v0.13` (22 septembre 2026) — passe de retours de l'auteur, sept coupes et deux ajouts. **Sortent :** le renvoi aux interdits du § 5.2.3 dans la phrase d'ouverture ; le paragraphe qui chiffrait ce que l'ingénierie de prompt rapproche et ce que pèse le porteur ; le paragraphe de la cinquième condition ; les quatre paragraphes sous le tableau du § 6.1, dont les différences appariées et l'énoncé H0, qui vivent à l'annexe H.1 et dont le § 1.3 ne porte plus l'hypothèse ; le tableau des gains appariés du § 6.2, que sa figure porte ; la figure 6.6 et sa légende. **Entrent :** les deux bras du classifieur à sortie typée au tableau du § 6.4 et à la figure 6.5, où il occupe les dernières places sur l'entropie croisée alors qu'il tient la bande tabulaire au § 6.1, et **la dispersion entre graines, mesurée**, qui lève le premier des deux TBC du § 6.5 : trois graines donnent 4,86, 4,65 et 4,30 de composite, une étendue de 0,56 point. **Décision de l'auteur :** `prompt_expert_32` est le prompt expert de Jev, et la ligne du § 6.1 le dit au lieu de « prompt réglé pour lui ». Son score reste en échantillon, le commentaire de source le porte, et les différences appariées de l'annexe H.1 restent mesurées sur `prompt_expert_05`. Ticket 101, retours de l'auteur du 22 septembre.
**Statut antérieur :** `brouillon v0.12` (22 septembre 2026) — le chapitre passe à quinze décideurs. Les deux bras du classifieur à sortie typée entrent au § 6.1, son gain de consigne au § 6.2, et les quatre figures sont régénérées par `scripts/analysis/plot_chapitre6.py --avec-jev`. Le chapeau, le titre et les deux légendes suivent, ainsi que le paragraphe de lecture sous le tableau, qui ajoute que ce décideur n'est séparable d'aucune des quatre méthodes tabulaires là où `gemini-3.5` l'est de deux. Les chiffres des treize autres décideurs sont inchangés. Ticket 101, lots 1 et 3.
**Statut antérieur :** `brouillon v0.11` (22 septembre 2026) — le § 6.4 cessait d'être soutenu par la mesure sur un point : il donnait le prompt expert devant le logit multinomial sur l'entropie croisée, quand l'écart vaut −0,018 [−0,039 ; +0,003] et ne se sépare pas de zéro. La phrase dit maintenant ce qui est établi, un retard séparable sur le gradient boosté et la forêt aléatoire, et renvoie à l'annexe I.1 bis, qui publie les treize différences appariées de l'audit unitaire. Ticket 101, lot 1.
**Statut antérieur :** `brouillon v0.10` (22 septembre 2026) — le support commun de l'entropie croisée passe de 5 451 à 5 229 décisions : les trois bras Jev joués sur ce jeu le définissent désormais avec les six autres décideurs à distribution. Deux valeurs du tableau du § 6.4 bougent d'un millième, 0,342 à 0,341 et 0,383 à 0,384 ; le classement, le paragraphe de lecture et les figures restent tels quels. L'annexe I suit. Ticket 101, lot 0.
**Statut antérieur :** `brouillon v0.9` (22 septembre 2026) — la section d'accord entre décideurs est supprimée à la demande de l'auteur : son tableau de trois paires, son paragraphe de lecture et son commentaire de source partent avec elle. Les deux sections suivantes remontent d'un cran, l'audit unitaire devenant le **§ 6.4** et la variation de cohorte le **§ 6.5**. Le chapitre compte cinq sections et garde ses six figures, numérotées indépendamment des sections. Les renvois de la conclusion et des annexes suivent. Aucun chiffre des sections restantes ne bouge.
**Statut antérieur :** `brouillon v0.8` (21 septembre 2026) — l'entropie croisée du § 6.5 change de valeur et de conclusion. Chaque décideur y était noté sur les seules décisions où sa distribution laissait une masse non nulle au mode déclaré, c'est-à-dire sur un ensemble qu'il se choisissait en tranchant plus ou moins dur, de 5 923 à 6 588 décisions. Sur le support commun aux six décideurs comparés, 5 451 décisions, le prompt expert ne devance plus que le logit multinomial là où il passait devant les quatre méthodes tabulaires. Le tableau, sa légende et le paragraphe suivent ; l'annexe I et le § 4.2 aussi. Mesure refaite par `scripts/progedo_logit/audit_unitaire_058.py`, corrigé le même jour.
**Statut antérieur :** `brouillon v0.7` (21 septembre 2026) — le paragraphe de lecture du § 6.5 est réécrit, à la demande de l'auteur : il n'était pas compréhensible. Il disait « grandeur lue » et « masse » sans les gloser et repartait vers le § 6.1 sans transition. Il dit maintenant le résultat, l'agent se trompe de mode aussi souvent que les méthodes tabulaires mais accordait davantage de probabilité au mode déclaré quand il se trompe, et laisse les valeurs au tableau qui le précède. L'incise sur la cohorte synthétique sort du paragraphe d'ouverture. `brouillon v0.6` (21 septembre 2026) — passage du chapitre au crible des trois règles du [README](README.md), à la demande de l'auteur. Sortent en règle 1, la maxime qui ouvrait le § 6.4 et l'annonce négative de la figure 6.6 ; le § 6.5 commence par ce qu'il mesure au lieu de ce que la cohorte n'a pas. Sortent en règle 2, le réglage déclaré et le compte d'itérations du § 6.2, qui descendent en commentaire, la généralité du § 6.5 sur la moitié des individus, que le tableau contredit à 67,6 % d'exactitude, et le paragraphe des deux asymétries, que le chapitre 8 porte. La légende de la figure 6.1 passe de sept phrases à quatre sans perdre de constat. La prose tombe de 1 439 à 1 277 mots. Aucun chiffre ne bouge. Corrigé au passage : le § 6.6 renvoyait encore aux différences appariées du § 6.1, qui n'en porte plus. `brouillon v0.5` (21 septembre 2026) — le chapitre est resserré une seconde fois, sur demande de l'auteur : le chapeau perd son rappel du chapitre 5, les trois paragraphes sous le tableau du § 6.1 sortent, et le § 6.3 est ramené à ce que ses deux figures établissent. L'audit unitaire quitte le § 6.4 et tient une section à lui, le **§ 6.5**, la variation de cohorte devenant le § 6.6. Six sections, six figures en anglais, inchangées. Aucun chiffre ne bouge. L'estimation appariée qui rapportait H0 sort du chapitre avec le § 6.1 ; le § 1.3 et le résumé y renvoient encore. `brouillon v0.4` (17 septembre 2026) — le chapitre est resserré sur les enseignements, sur demande de l'auteur : les tableaux de détail, les strates une à une et les écarts secondaires partent à l'**annexe H**, que ce chapitre cite. Cinq sections, six figures en anglais : quatre régénérées par `scripts/analysis/plot_chapitre6.py`, les deux de l'audit unitaire par `scripts/analysis/plot_audit_unitaire.py`. La section qui portait l'écart au plafond tabulaire disparaît : cet écart se lit désormais sous le tableau du § 6.1, et la variation de cohorte tient une section à elle. `brouillon v0.3` (17 septembre 2026) — réorganisation en cinq sections autour du couple modèle-consigne, vocabulaire aligné sur le dépôt (décideur, prompt minimal, prompt expert), coût d'exécution déplacé au chapitre 9. `brouillon v0.2` (16 septembre 2026) — réécriture sur les scores recalculés depuis le dépôt. `projet v0.1` (15 septembre 2026) — première rédaction au titre du [ticket 080](../../../tickets/ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md).
**Place dans l'article :** section 6 du plan annoncé en 1.4 de [`../en/01_Introduction.md`](../en/01_Introduction.md). Trame : [`../plan/PLAN.md`](../plan/PLAN.md). État d'avancement : [`../README.md`](../README.md).
**Convention :** un chiffre suivi de **TBD** est à consolider. Un chiffre **en gras entre crochets** est un emplacement vide.

---

<!-- source: data/experiences/exp_*_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_*/executions/*/scores.json ; cohorte population_1000_AAMAS_v6, jeu population_1000_AAMAS_v6_20260316_EN_c, formule v1_reference (0aeee565…), référentiel EMC² 2023 (9ac34597…). 3 154 décisions sur 3 299 attendues, 868 personnes mobiles ; 138 déplacements inexploitables sont exclus par le scoreur. Tous les décideurs sont mesurés sur ce jeu : la campagne de rejeu du ticket 088 s'est terminée le 2026-09-17 à 09:25, et plus aucun chiffre du chapitre n'est lu sur le substrat antérieur. -->

Les résultats de ce chapitre portent sur un couple : un décideur et une consigne d'arbitrage, portée par son prompt système. Trois de ces décideurs sont des modèles de langue ; le quatrième, Jev 1.13, est un classifieur à sortie typée qui rend une probabilité par option sans produire de texte.

<!-- source: docs/traces/2026-09-21_jev_mutations/README.md — prompt_expert_32, réglé le 2026-09-21 par mutations successives sur les écarts par strate de exp_jev-1130_proexp05_…_c_nosim/2026-09-21_06_25_29, selon la procédure du § 5.2.2. Six textes mesurés, cinq écartés, chacun audité conforme avant lancement par l'agent prompt-auditor ; l'un d'eux a été refusé en première rédaction (C4 : il conditionnait l'arbitrage au statut de conducteur, donnée retirée du récit de persona depuis le 2026-08-26). La mutation retenue réécrit la clause « Chain friction » à deux versants : le prompt publié énumérait tous les coûts de la chaîne et aucun de la marche continue. -->

<!-- ⚠ ASYMÉTRIE À CONNAÎTRE, décision de l'auteur du 22 septembre 2026 : prompt_expert_32 EST le prompt expert de Jev, et c'est lui que le § 6.1 publie. Il n'a pas été obtenu comme les autres. prompt_expert_05 a été réglé contre gemini-3.5-flash-lite sur une population de calibration tirée séparément de la cohorte scellée, puis soumis tel quel aux autres porteurs ; prompt_expert_32 a été muté contre les écarts par strate de Jev lus sur la cohorte qui le note, et son score est donc EN ÉCHANTILLON. Le bras Jev sous prompt_expert_05 reste mesuré et vit à l'annexe H.6 et à l'annexe I ; c'est lui, et non prompt_expert_32, que portent les différences appariées de l'annexe H.1. -->


## 6.1 Quinze décideurs sur la même échelle

Les trois lectures définies au § 4.2 sont publiées pour chaque décideur.

![Les quinze décideurs sur l'axe du composite EMD–JSD, par groupe](../images/ch6_echelle.png)

*Figure 6.1 — Les quinze décideurs sur l'axe du composite EMD–JSD. L'échelle couvre un facteur douze entre le plancher aléatoire et le meilleur composite, et cinq groupes s'y séparent. Les planchers occupent la moitié haute, de 27 à 50. Le prompt minimal place les modèles de langue entre 7,0 et 14,8, contre 27,0 à l'heuristique de durée minimale : les faits seuls, sans consigne d'arbitrage, portent déjà une information comportementale, distincte de celle que l'enquête enregistre. Le prompt expert ramène les mêmes modèles entre 4,9 et 9,0. Le classifieur à sortie typée parcourt la plus grande distance entre ses deux consignes, de 13,75 à 3,65. Les quatre méthodes tabulaires tiennent dans un intervalle d'un demi-point, de 3,60 à 4,09 ; son bras expert s'y range, à 0,05 point du meilleur. La bande grise donne la variation de cohorte, de l'ordre de 1,3 point.*

| Décideur | Composite EMD–JSD | Hors choix unique | L1 parts globales |
|---|---:|---:|---:|
| Hasard uniforme | 50,16 | 57,90 | 86,80 |
| Tout-voiture | 30,73 | 28,41 | 58,00 |
| Durée minimale | 26,97 | 23,93 | 53,62 |
| Prompt minimal, `mistral-large-2512` | 14,75 | 20,72 | 44,71 |
| Prompt minimal, `jev-1.13.0` | 13,75 | 19,84 | 42,76 |
| Prompt minimal, `gemini-3.1-flash-lite` | 12,38 | 16,65 | 39,88 |
| Prompt minimal, `gemini-3.5-flash-lite` | 7,02 | 10,39 | 24,08 |
| Prompt expert, `gemini-3.1-flash-lite` | 8,98 | 12,39 | 31,25 |
| Prompt expert, `mistral-large-2512` | 7,63 | 12,27 | 26,64 |
| Prompt expert, `gemini-3.5-flash-lite` | 4,86 | 6,86 | 13,85 |
| Logit multinomial | 4,02 | 6,63 | 8,99 |
| Forêt aléatoire | 4,09 | 5,81 | **5,28** |
| Prompt expert, `jev-1.13.0` | 3,65 | 6,58 | 10,48 |
| Régression logistique à noyau | 3,61 | **5,61** | 6,69 |
| Gradient boosté (LightGBM) | **3,60** | 5,84 | 9,49 |

<!-- sources: scores.json, composite.emd_jsd, composite.emd_jsd_hors_choix_unique, global.l1. Prompt minimal = prompt_minimal_02 ; prompt expert = prompt_expert_05, promu le 2026-09-17 (prompt_expert_04 supprimé du dépôt le même jour, à la demande de l'auteur). Dans cette campagne, prompt_expert_05 a été réglé contre gemini-3.5-flash-lite puis soumis tel quel aux trois autres porteurs ; rien dans le protocole n'impose une consigne unique, et un réglage par porteur reste ouvert. Les trois consignes sont servies à Jev amputées de leur bloc de sortie, le type Choice le remplaçant ; le sha du texte effectivement envoyé est scellé dans l'empreinte de chaque exécution. La ligne « Prompt expert, jev-1.13.0 » est prompt_expert_32 (exp_jev-1130_proexp32_…_c_nosim, exécution 2026-09-21_10_14_52) : les écarts par strate qui ont guidé ses mutations ont été lus sur cette cohorte même, son score est donc en échantillon et elle ne concourt pas au gras. Le bras prompt_expert_05 est épinglé sur son exécution 2026-09-21_06_25_29 : un rejeu à l'identique en a créé une seconde le même jour, et « la dernière exécution » aurait déplacé ce chiffre publié de 4,19 à 4,14 sans qu'une ligne du chapitre bouge. En gras, le meilleur score de chaque colonne. -->

<!-- Quatre paragraphes retirés le 22 septembre 2026 à la demande de l'auteur : la lecture des trois
     colonnes, la parité de mémoire entre familles, les différences appariées et le paragraphe H0.
     Rien n'est perdu. Les différences appariées et leurs intervalles sont à l'annexe H.1, calculées
     dans docs/traces/2026-09-21_ticket096_lot2/ (script paired_avec_jev.py, 2 000 réplicats, graine
     2026, rééchantillonnage par grappe au niveau de la personne sur les 868 personnes communes aux
     onze bras, vingt paires) et docs/traces/2026-09-17_09-40_ch6_jeu_corrige_complet/ pour les
     quatorze paires d'origine, que ce passage a recalculées à l'identique au centième près. Le bras
     Jev de ces paires est prompt_expert_05, et non le prompt_expert_32 que publie le tableau
     ci-dessus. L'énoncé sur l'absence de test d'équivalence part avec l'hypothèse H0, retirée du
     § 1.3 le même jour. -->

## 6.2 Ce que l'ingénierie de prompt déplace

![Trajectoire de l'ingénierie de prompt pour quatre porteurs](../images/ch6_ingenierie.png)

*Figure 6.2 — Ce que l'ingénierie de prompt fait parcourir à chaque porteur. Le cercle creux est le prompt minimal, le cercle plein la consigne que le § 6.1 publie pour ce porteur, les carrés les autres variantes mesurées. La bande verte donne l'intervalle des quatre méthodes tabulaires. Les quatre porteurs partent d'endroits différents et avancent de montants différents ; deux entrent au contact de la bande, et celui qui part du plus loin arrive le plus près. Le classifieur à sortie typée est le seul dont la consigne publiée a été réglée pour lui, et elle l'a été sur la cohorte qui le note ; le carré qui la suit est la consigne de `gemini-3.5`, servie telle quelle.*

Ces déplacements sont mesurés à personas, offre d'itinéraires, graine et modèle de fondation identiques, la consigne seule changeant. Les intervalles appariés des quatre porteurs excluent zéro sur les trois lectures, et le gain va de une fois et demie à sept fois et demie la variation de cohorte ([annexe H.1](99_annexes.md)).

<!-- source: docs/traces/2026-09-17_09-40_ch6_jeu_corrige_complet/ ; 2 000 réplicats, graine 2026, 868 personnes communes, tous les décideurs sur le jeu corrigé. Un gain positif est une erreur plus faible. Le tableau des quatre gains appariés a été retiré du corps le 22 septembre 2026 à la demande de l'auteur, la figure le portant : +2,27 [+1,40 ; +3,22] pour gemini-3.5-flash-lite, +3,37 [+2,45 ; +4,25] pour gemini-3.1-flash-lite, +7,25 [+5,90 ; +8,67] pour mistral-large-2512 et +9,71 [+7,80 ; +11,66] pour jev-1.13.0, tous à l'annexe H.1. ⚠ La ligne Jev de ces gains est prompt_expert_05 − prompt_minimal_02, et non prompt_expert_32 − prompt_minimal_02 que publierait le tableau du § 6.1 ; l'écart apparié sous prompt_expert_32 n'a pas été calculé. Une douzaine d'itérations d'ingénierie sur gemini-3.5-flash-lite et deux ou trois sur chacun des deux autres modèles, ordre de grandeur déclaré par l'auteur ; la variante mesurée a été réglée contre gemini-3.5 ; le § 5.2 décrit la procédure, l'annexe H porte les variantes et leurs scores. Les écarts entre porteurs sous chaque consigne, le renversement de classement entre gemini-3.1 et mistral-large, et l'ablation de la clause de justification sont à l'annexe H. -->

## 6.3 Le détail des résultats agrégés, sur Gemini 3.5

![Part de la voiture par tranche de distance](../images/ch6_distance.png)

*Figure 6.3 — La part de la voiture par tranche de distance : la cible d'enquête, `gemini-3.5` sous prompt minimal puis sous prompt expert, et la méthode tabulaire la plus proche de la cible sur cette dimension.*

<!-- source: scores.json des deux exécutions du jeu corrigé, detail.distance.strates, part voiture prompt_minimal_02 → prompt_expert_05 : 9,7 → 10,1 (0-1 km) ; 37,7 → 43,4 ; 51,1 → 58,4 ; 60,0 → 65,9 ; 67,5 → 74,1 ; 74,9 → 80,8 ; 63,8 → 61,8 (plus de 50 km, n = 17). Le levier de coût fixe du véhicule (« Fixed frictions of the car ») appartient à prompt_expert_08, pas à prompt_expert_05 que la figure trace : la pente est mesurée, son attribution à ce levier ne l'est pas. -->

![Transports collectifs et vélo par âge et par occupation](../images/ch6_residu.png)

*Figure 6.4 — Les deux modes qui portent le résidu, lus par âge et par occupation. Le pic de transports collectifs des 15–19 ans, 47,4 % dans l'enquête, n'est reproduit par aucun décideur : l'agent en place 20,8 % après réglage et la forêt aléatoire 26,4 %. Le vélo suit le chemin inverse sur la même strate, 19,7 % chez l'agent contre 4,1 % observés, et le réglage ne le déplace pas.*

Les deux modes minoritaires portent une erreur que la consigne ne corrige pas. Les trois modèles de langue placent le vélo entre 6,8 et 8,1 % quand l'enquête en compte 4,1 %, et l'ingénierie de prompt ne déplace cette part que de un dixième à huit dixièmes de point, là où elle fait reculer les transports collectifs de quatre à onze points : deux erreurs coexistent dans le même décideur, et une seule répond à la consigne.

Les résultats détaillés sont à l'[annexe H](99_annexes.md) : l'erreur par dimension et par décideur, les parts modales de chacun, les strates que le réglage dégrade sur les trois modèles, et quatre planches, la part voiture sur six dimensions et les quatre modes lus par distance, par occupation et par motif.

<!-- source: scores.json, detail.<dimension>.strates et global.actual/target ; tous les décideurs sur le jeu corrigé …_20260316_EN_c. La figure compare prompt_minimal_02 et prompt_expert_05, régénérée le 2026-09-17 par scripts/analysis/plot_chapitre6.py. Erreur L1 pondérée sur la dimension distance, moyenne des strates couvertes pondérée par leur effectif : 14,19 pour gemini-3.5 sous prompt expert, 16,79 à la forêt aléatoire, 17,79 au gradient boosté, 18,09 à la régression à noyau, 20,73 au logit multinomial. Les 15-19 ans et les déplacements de plus de 50 km résistent à tous les décideurs, méthodes tabulaires comprises : 34 à 59 et 42 à 72 points d'erreur. Annexe H. -->

## 6.4 Décision individuelle

L'exactitude unitaire annoncée au § 4.2 se mesure sur les journées réellement décrites par les enquêtés, selon le protocole du § 5.4 : 9 621 déplacements de 2 930 personnes, chacun portant le mode qu'elles ont déclaré.

| Décideur | Exactitude | Entropie croisée | Rappel vélo | Rappel marche |
|---|---:|---:|---:|---:|
| Gradient boosté | 71,5 | **0,299** | 20,4 | 63,4 |
| Logit multinomial | 68,6 | 0,358 | 18,3 | 60,0 |
| Durée minimale | 68,1 | — | 25,8 | 19,2 |
| Prompt expert `gemini-3.5` | 67,6 | 0,341 | 22,5 | 47,2 |
| Prompt minimal `gemini-3.5` | 64,8 | 0,384 | 24,1 | 44,2 |
| Prompt expert `jev-1.13.0` | 64,7 | 0,464 | 18,1 | 56,3 |
| Prompt minimal `jev-1.13.0` | 56,6 | 0,552 | 19,0 | 43,3 |

*Sept décideurs sur douze, en pourcentage sauf l'entropie croisée, mesurée sur les 5 229 décisions que tous les décideurs à distribution du jeu notent. Les cinq autres et les colonnes de précision sont à l'annexe I.*

Le prompt expert désigne le mode déclaré un peu moins souvent que les méthodes tabulaires. Sur l'entropie croisée, qui pèse la probabilité qu'un décideur accordait au mode finalement déclaré, il reste derrière le gradient boosté et la forêt aléatoire, et son écart au logit multinomial ne se sépare pas de zéro (annexe I.1 bis). Le classement dépend donc de la grandeur lue sans amener l'agent devant, et aucune de ces deux lectures ne se lit sur le composite du § 6.1, qui ne compare que des parts agrégées.

Le classifieur à sortie typée se range autrement. Il atteint les méthodes ajustées sur l'enquête quand on lit des parts agrégées (§ 6.1), et il occupe ici les dernières places : dernier sur l'entropie croisée, et sous le prompt minimal à modèle de langue sur l'exactitude. La fidélité d'une répartition et la justesse d'une décision ne se déduisent donc pas l'une de l'autre, et l'écart entre les deux lectures est plus grand chez lui que chez tout autre décideur du tableau.

![Rappel et précision par mode](../images/ch6_audit_modes.png)

*Figure 6.5 — Rappel et précision par mode, pour le plafond tabulaire et le prompt expert de chaque famille. Le modèle de langue rappelle le vélo mieux que la méthode ajustée, 22,5 contre 20,4 %, et le paie en précision, 15,0 contre 27,3. Sur la marche le rapport s'inverse, rappel 47,2 contre 63,4 et précision 62,9 contre 53,2, la meilleure des trois. Le classifieur à sortie typée partage son erreur autrement : il rend six points de rappel sur la marche au modèle de langue, 56,3 contre 47,2, et lui en cède onze en transports collectifs, 43,8 contre 55,2. Les prompts minimaux et le plancher tout-voiture sont à l'annexe I.*

Le détail par mode des douze décideurs, la matrice de confusion et le plafond de l'audit sont à l'annexe I.

<!-- sources: entropie croisée recalculée le 2026-09-22 sur le support commun, les 5 229 décisions arbitrées que notent les neuf décideurs à distribution joués sur ce jeu, les trois bras Jev du ticket 096 compris : ils définissent le support sans figurer au tableau, et l'y faire entrer coûte 222 décisions sur les 5 451 de la mesure précédente, pour un déplacement d'au plus 0,001 sur un chiffre publié. La lecture antérieure notait chaque décideur sur son propre sous-ensemble, de 5 923 à 6 588 décisions selon qu'il tranchait plus ou moins dur, et donnait le prompt expert premier — traces docs/traces/2026-09-21_11-45_ticket058_entropie_support_commun/ puis docs/traces/2026-09-22_lot0_entropie_support_unique/, ticket 101 lot 0. Exactitudes unitaires, scripts/progedo_logit/audit_unitaire_058.py sur les exécutions du jeu enquete_058_test_20260316, douze décideurs, 9 612 à 9 618 déplacements notés selon le décideur ; figure 6.5 régénérée par scripts/analysis/plot_audit_unitaire.py --avec-jev, restreinte le 2026-09-22 au plafond tabulaire et aux deux prompts experts, les prompts minimaux et le plancher tout-voiture restant à l'annexe I (9 621 déclarés, moins ceux sans offre et les enchaînements rompus). La figure 6.6, l'accord unitaire par tranche de distance, a été retirée du chapitre le 22 septembre 2026 à la demande de l'auteur ; le script la produit toujours. Les deux lignes Jev du tableau sont exp_jev-1130_{proexp32,promin02}_jtir_pop-enquete_058_test_… : prompt_expert_32 est le prompt expert de Jev, décision de l'auteur du 22 septembre, et c'est le même bras qu'au § 6.1. Les deux bras LLM sont exp_gemini-35-fl_{promin02,proexp05}_jtir_pop-enquete_058_test_… terminés les 2026-09-18 et 2026-09-19, 12 562 décisions chacun, aucune erreur. Ces valeurs ne sont commensurables ni avec les composites (jeu différent, support différent) ni avec les repères de la partition de test cités au § 5.3 : ceux-ci valent hors contrainte de chaîne et sans plafond d'options, et donnent 76,6 à 78,5 % aux mêmes méthodes tabulaires qui font ici 68,6 à 71,5 %. -->

## 6.5 Variation de cohorte et dispersion entre graines

Une cohorte de 1 000 personas ne mesure un composite qu'à ±1,3 point près : c'est l'intervalle de confiance à 95 % obtenu en rééchantillonnant les personnes avec remise, et il borne ce que le tableau du § 6.1 permet de départager. L'écart-type apparié de ce terme vaut ≈ 0,7, de sorte qu'aucune marge d'équivalence inférieure à 1,4 point ne se conclura d'un run sur cette cohorte ; seules des cohortes supplémentaires l'abaissent. C'est la raison pour laquelle toutes les comparaisons de ce chapitre sont appariées : jouer les deux décideurs sur les mêmes personas fait agir ce terme des deux côtés, où il s'annule.

La dispersion entre graines est plus petite que ce terme. Le prompt expert sur `gemini-3.5` a été rejoué à l'identique sur la même cohorte et le même jeu sous deux autres graines : son composite vaut 4,86, 4,65 et 4,30, soit une étendue de 0,56 point, moins de la moitié de la variation de cohorte. Les deux autres lectures suivent, 6,86 à 5,98 hors choix unique et 13,85 à 11,97 sur les parts globales. Le prompt minimal n'a pas été rejoué sous ces graines, de sorte que l'effet de ce terme sur le signe des différences appariées du § 6.2 et de l'annexe H reste non mesuré.

<!-- source: ticket 073, axe 1. Trois graines de bout en bout — ordre, tirage et contexte de décision alignés : 42 (référence, exp_gemini-35-fl_proexp05_…_c_t0_nosim/2026-09-16_22_20_25, le bras que publie le § 6.1), 123 (…_c_go123_gt123_gc123_t0_nosim/2026-09-21_17_00_49) et 789 (…_c_go789_gt789_gc789_t0_nosim/2026-09-21_22_26_36), les trois terminées avec 3 299 décisions archivées. Composite / hors choix unique / L1 : 4,857 / 6,858 / 13,853 ; 4,646 / 5,982 / 11,969 ; 4,299 / 6,079 / 12,125. L'axe s'arrête à ces trois graines, décision de l'auteur du 2026-09-22 : les définitions 456 et 2026 sont supprimées de data/experiences/, recopiées dans docs/traces/2026-09-22_12-12_suppression_graines_456_2026_ticket073/. Les deux **TBC** que ce paragraphe portait depuis le 2026-09-17 sont levés pour le premier énoncé et retirés pour le second, qui demandait un rejeu du bras minimal sous les mêmes graines et n'a pas été joué. -->

Deux mesures antérieures majoraient ce terme sans pouvoir l'isoler. Le même prompt, sur le même modèle et avec la même graine, rejoué sur un substrat corrigé, déplace son composite de 0,24 à 1,17 point selon le décideur, quand les décideurs déterministes bougent de moins de 0,12 ; et deux exécutions du même prompt sur deux cohortes successives s'accordent sur 86,1 % des modes les plus probables. L'une et l'autre confondent le non-déterminisme du modèle avec le changement de substrat, que le rejeu à l'identique ci-dessus sépare.

<!-- source : ±1,3 point et écart-type apparié de 0,7 du ticket 080 § 0.3, écarts de substrat lus dans les scores.json des deux jeux, accord de 86,1 % issu de deux exécutions du même prompt sur deux cohortes successives. -->

---

### Tickets associés à ce chapitre

- [Ticket 080](../../../tickets/ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md) — idée directrice, décisions de l'auteur, impact sur le reste du papier
- [Ticket 088](../../../tickets/ticket_088_jeu_corrige_et_rejeu_complet.md) — jeu corrigé et rejeu des décideurs à modèle de langue
- [Ticket 073](../../../tickets/ticket_073_reproductibilite_prompt_calibre_multi_graines_multi_populations.md) — rejeu à l'identique, dispersion inter-graines, cohortes supplémentaires
- [Ticket 074](../../../tickets/ticket_074_bascule_anglaise_archivage_et_reprise_de_campagne.md) — campagne v6, substrat des chiffres publiés
- [Ticket 055](../../../tickets/ticket_055_benchmark_multimodeles_et_variabilite.md) — banc d'essai multi-modèles
- [Ticket 057](../../../tickets/ticket_057_audit_et_reflexion_double_lecture_tabulaire.md) — contrainte de chaîne des véhicules et périmètre de score
- [Ticket 058](../../../tickets/ticket_058_perimetre_et_methode_audit_unitaire.md) — audit unitaire, accord aux choix observés, attributions de Shapley
- [Ticket 046](../../../tickets/ticket_046_asymetrie_informationnelle_du_contrat_d_evaluation.md) — asymétrie d'information entre l'agent et les méthodes tabulaires
- [Ticket 081](../../../tickets/ticket_081_garde_fou_du_scoreur_sur_journal_tronque.md) — garde-fou du scoreur sur journal tronqué
