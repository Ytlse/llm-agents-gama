# 6. Résultats

<!-- Dernière mise à jour : 2026-09-17 -->

**Document :** chapitre 6 de l'article AAMAS 2027 — le chapitre de **résultats** : le chapitre 5 définit les conditions comparées, celui-ci dit ce que la comparaison établit.
**Statut :** `brouillon v0.4` (17 septembre 2026) — le chapitre est resserré sur les enseignements, sur demande de l'auteur : les tableaux de détail, les strates une à une et les écarts secondaires partent à l'**annexe H**, que ce chapitre cite. Cinq sections, quatre figures en anglais régénérées par `scripts/analysis/plot_chapitre6.py`. La section qui portait l'écart au plafond tabulaire disparaît : cet écart se lit désormais sous le tableau du § 6.1, et la variation de cohorte tient une section à elle.
**Statut antérieur :** `brouillon v0.3` (17 septembre 2026) — réorganisation en cinq sections autour du couple modèle-consigne, vocabulaire aligné sur le dépôt (décideur, prompt minimal, prompt expert), coût d'exécution déplacé au chapitre 9. `brouillon v0.2` (16 septembre 2026) — réécriture sur les scores recalculés depuis le dépôt. `projet v0.1` (15 septembre 2026) — première rédaction au titre du [ticket 080](../../../tickets/ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md).
**Place dans l'article :** section 6 du plan annoncé en 1.4 de [`../en/01_introduction.md`](../en/01_introduction.md). Trame : [`../plan/PLAN.md`](../plan/PLAN.md). État d'avancement : [`../README.md`](../README.md).
**Convention :** un chiffre suivi de **TBD** est à consolider. Un chiffre **en gras entre crochets** est un emplacement vide.

---

Le chapitre 5 a décrit quatre façons de décider d'un mode de déplacement à partir du même état. Ce chapitre les confronte à l'enquête, sur la cohorte de 1 000 personas et les 3 154 décisions scorées du jour évalué.

<!-- source: data/experiences/exp_*_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_*/executions/*/scores.json ; cohorte population_1000_AAMAS_v6, jeu population_1000_AAMAS_v6_20260316_EN_c, formule v1_reference (0aeee565…), référentiel EMC² 2023 (9ac34597…). 3 154 décisions sur 3 299 attendues, 868 personnes mobiles ; 138 déplacements inexploitables sont exclus par le scoreur. Tous les décideurs sont mesurés sur ce jeu : la campagne de rejeu du ticket 088 s'est terminée le 2026-09-17 à 09:25, et plus aucun chiffre du chapitre n'est lu sur le substrat antérieur. -->

Chaque résultat de ce chapitre porte sur un couple : un modèle de langue et une consigne d'arbitrage, portée par son prompt système et soumise aux interdits du § 5.3.4, dont celui de tout seuil chiffré. L'ingénierie de ce prompt rapproche `gemini-3.5-flash-lite` de 2,3 points de composite de la distribution d'enquête et `mistral-large-2512` de 7,3, quand la variation de cohorte est de l'ordre de 1,3 point. Le porteur pèse autant que la consigne : soumise telle quelle à un second modèle du même fournisseur, la variante réglée contre `gemini-3.5-flash-lite` laisse 4,2 points d'écart entre les deux, davantage que ce qu'elle apporte au moins bon d'entre eux. Des trois couples mesurés, un seul vient à un point et demi du plafond tabulaire, séparable de deux des quatre méthodes de référence et non séparable des deux autres, et cette proximité des marges recouvre un désaccord décision par décision que les méthodes tabulaires, entre elles, ne connaissent pas.

## 6.1 Treize décideurs sur la même échelle

Les trois lectures définies au § 4.2 sont publiées pour chaque décideur.

![Les treize décideurs sur l'axe du composite EMD–JSD, par groupe](../images/ch6_echelle.png)

*Figure 6.1 — Les treize décideurs sur l'axe du composite EMD–JSD. L'échelle couvre un facteur quatorze entre le plancher aléatoire et le meilleur composite, et quatre groupes s'y séparent nettement. Les planchers occupent la moitié haute, de 27 à 50. Le prompt minimal place les modèles de langue entre 7,0 et 14,8, contre 27,0 à l'heuristique de durée minimale : les faits seuls, sans consigne d'arbitrage, portent déjà une information comportementale, distincte de celle que l'enquête enregistre. Le prompt expert ramène les mêmes modèles entre 4,9 et 9,0. Les quatre méthodes tabulaires tiennent dans un intervalle d'un demi-point, de 3,60 à 4,09. La bande grise donne la variation de cohorte, de l'ordre de 1,3 point.*

| Décideur | Composite EMD–JSD | Hors choix unique | L1 parts globales |
|---|---:|---:|---:|
| Hasard uniforme | 50,16 | 57,90 | 86,80 |
| Tout-voiture | 30,73 | 28,41 | 58,00 |
| Durée minimale | 26,97 | 23,93 | 53,62 |
| Prompt minimal, `mistral-large-2512` | 14,75 | 20,72 | 44,71 |
| Prompt minimal, `gemini-3.1-flash-lite` | 12,38 | 16,65 | 39,88 |
| Prompt minimal, `gemini-3.5-flash-lite` | 7,02 | 10,39 | 24,08 |
| Prompt expert, `gemini-3.1-flash-lite` | 8,98 | 12,39 | 31,25 |
| Prompt expert, `mistral-large-2512` | 7,63 | 12,27 | 26,64 |
| Prompt expert, `gemini-3.5-flash-lite` | 4,86 | 6,86 | 13,85 |
| Logit multinomial | 4,02 | 6,63 | 8,99 |
| Forêt aléatoire | 4,09 | 5,81 | **5,28** |
| Régression logistique à noyau | 3,61 | **5,61** | 6,69 |
| Gradient boosté (LightGBM) | **3,60** | 5,84 | 9,49 |

<!-- sources: scores.json, composite.emd_jsd, composite.emd_jsd_hors_choix_unique, global.l1. Prompt minimal = prompt_minimal_02 ; prompt expert = prompt_expert_05, promu le 2026-09-17 (prompt_expert_04 supprimé du dépôt le même jour, à la demande de l'auteur). Dans cette campagne, prompt_expert_05 a été réglé contre gemini-3.5-flash-lite puis soumis tel quel aux deux autres modèles ; rien dans le protocole n'impose une consigne unique, et un réglage par modèle reste ouvert. En gras, le meilleur score de chaque colonne. -->

Le composite porte sur toutes les décisions du jour, déplacements contraints compris ; la lecture hors choix unique retire celles où une seule option existait ; le L1 sur les parts globales ne regarde que les quatre parts modales agrégées, sans stratification.

Deux scores distants d'un point ne se départagent pas sur ce tableau, la variation de cohorte étant du même ordre (§ 6.5). Jouer deux décideurs sur les mêmes personas retire ce terme, puisqu'il agit alors des deux côtés : appariés ainsi, `gemini-3.5` sous prompt expert est derrière le gradient boosté de **1,35 point [+0,28 ; +2,47]** et derrière la régression à noyau de **1,38 [+0,32 ; +2,45]**, sans être séparable de la forêt aléatoire, +0,94 [−0,06 ; +1,98], ni du logit multinomial, +0,96 [−0,18 ; +2,17]. Les deux autres modèles restent à **4,07 [+2,47 ; +5,75]** et **5,50 [+4,19 ; +6,93]** du gradient boosté. Un seul des trois couples vient donc à portée du plafond tabulaire, et son écart y exclut zéro face à deux des quatre méthodes de référence. L'ingénierie de prompt a porté sur `gemini-3.5` : la distance des deux autres mesure ce qu'une consigne transporte, non ce que produirait un réglage conduit sur eux.

Aucun test d'équivalence n'est rapporté : la marge n'a pas été écrite avant la mesure, et une marge choisie maintenant le serait après avoir vu les chiffres. L'hypothèse H0 du § 1.3 se présente en conséquence comme une estimation appariée, de signe, d'amplitude et d'intervalle.

<!-- source: docs/traces/2026-09-17_09-40_ch6_jeu_corrige_complet/ — quatorze différences appariées recalculées après la fin de la campagne de rejeu, tous les décideurs sur le jeu corrigé, 2 000 réplicats, graine 2026, rééchantillonnage par grappe au niveau de la personne sur 868 personnes communes. Les quatorze différences et leurs trois lectures sont à l'annexe H. -->

## 6.2 Ce que l'ingénierie de prompt déplace

![Trajectoire de l'ingénierie de prompt pour trois modèles](../images/ch6_ingenierie.png)

*Figure 6.2 — Ce que l'ingénierie de prompt fait parcourir à chaque modèle. Le cercle creux est le prompt minimal, le cercle plein le prompt expert évalué hors échantillon, les carrés deux variantes ajustées au vu de la cohorte évaluée. La bande verte donne l'intervalle des quatre méthodes tabulaires. Les trois modèles partent d'endroits différents, avancent de montants différents, et un seul entre au contact de la bande.*

| Gain apparié, prompt expert − prompt minimal | Composite | Hors choix unique | L1 parts globales |
|---|---|---|---|
| `gemini-3.5-flash-lite` | **+2,27 [+1,40 ; +3,22]** | **+3,59 [+2,45 ; +4,83]** | **+10,2 [+8,0 ; +12,5]** |
| `gemini-3.1-flash-lite` | **+3,37 [+2,45 ; +4,25]** | **+4,15 [+3,09 ; +5,22]** | **+8,6 [+6,8 ; +10,6]** |
| `mistral-large-2512` | **+7,25 [+5,90 ; +8,67]** | **+8,63 [+7,15 ; +10,28]** | **+18,0 [+13,5 ; +22,4]** |

Une douzaine d'itérations d'ingénierie sur `gemini-3.5-flash-lite` et deux ou trois sur chacun des deux autres modèles produisent ces déplacements, mesurés à personas, offre d'itinéraires, graine et modèle de fondation identiques, la consigne seule changeant. Les trois intervalles excluent zéro sur les trois lectures, et le gain va de une fois et demie à cinq fois et demie la variation de cohorte. La variante mesurée ici a été réglée contre `gemini-3.5`, puis soumise telle quelle aux deux autres modèles : soumise ainsi à `gemini-3.1`, elle laisse ce dernier derrière `gemini-3.5` de **4,15 points [+2,99 ; +5,43]**, davantage que les 3,37 points qu'elle lui apporte, de sorte qu'un banc d'essai conduit sous une seule consigne mesure le couple modèle-consigne et non le modèle. Le gain lui-même ne va pas au modèle contre lequel la consigne a été réglée : `gemini-3.1` en retire 3,37 points et `gemini-3.5` 2,27, alors que le second reste devant le premier de 4,15 points après réglage. Ce que l'ingénierie de prompt déplace et le niveau qu'elle atteint sont deux grandeurs distinctes.

<!-- source: docs/traces/2026-09-17_09-40_ch6_jeu_corrige_complet/ ; 2 000 réplicats, graine 2026, 868 personnes communes, tous les décideurs sur le jeu corrigé. Un gain positif est une erreur plus faible. Le nombre d'itérations est l'ordre de grandeur déclaré par l'auteur ; le § 5.3 décrit la procédure, l'annexe H porte les variantes et leurs scores. Les écarts entre porteurs sous chaque consigne, le renversement de classement entre gemini-3.1 et mistral-large, et l'ablation de la clause de justification sont à l'annexe H. -->

## 6.3 Le détail des résultats agrégés, sur Gemini 3.5

Ce qui suit est mesuré sur `gemini-3.5-flash-lite`, le modèle contre lequel l'ingénierie de prompt a été conduite ; les amplitudes du § 6.2 montrent que chaque modèle répond à sa façon.

![Part de la voiture par tranche de distance](../images/ch6_distance.png)

*Figure 6.3 — La part de la voiture par tranche de distance : la cible d'enquête, `gemini-3.5` sous prompt minimal puis sous prompt expert, et la méthode tabulaire la plus proche de la cible sur cette dimension. Le § 5.3 décrit le levier introduit contre une part voiture plate d'une tranche à l'autre : engager un véhicule coûte un forfait payé en entier quelle que soit la longueur du trajet, donc d'autant plus lourd que le trajet est bref.*

Le levier produit ce qu'il visait, et il crée une pente plutôt qu'il ne décale un niveau : la part voiture reste sous un kilomètre où elle était, à huit points sous la cible, et se relève de huit à quatorze points aux distances longues. `gemini-3.5` sous prompt expert passe là devant les quatre méthodes ajustées sur l'enquête, 14,2 points d'erreur pondérée contre 16,8 à la forêt aléatoire et 17,8 au gradient boosté : c'est la seule dimension où un agent y parvient, et celle contre laquelle le levier a été écrit.

![Transports collectifs et vélo par âge et par occupation](../images/ch6_residu.png)

*Figure 6.4 — Les deux modes qui portent le résidu, lus par âge et par occupation. Le pic de transports collectifs des 15–19 ans, 47,4 % dans l'enquête, n'est reproduit par aucun décideur : l'agent en place 20,8 % après réglage et la forêt aléatoire 26,4 %. Le vélo suit le chemin inverse sur la même strate, 19,7 % chez l'agent contre 4,1 % observés, et le réglage ne le déplace pas.*

Ce que le réglage ne corrige pas se concentre sur ces deux modes et sur les strates scolarisées. Les 15–19 ans, les élèves et les étudiants sont les trois strates où l'agent place le plus de vélo, jusqu'à cinq fois la part observée, et où il manque le plus de transports collectifs. Les leviers du prompt sont écrits pour des arbitrages d'adulte motorisé, coût d'engagement d'un véhicule, valeur du temps sous contrainte horaire, pénibilité sous intempérie, et ils ne portent pas sur une population dont l'enquête place près de la moitié des déplacements en transports collectifs.

Les deux modes minoritaires portent une erreur que la consigne ne corrige pas. Les trois modèles de langue placent le vélo entre 6,8 et 8,1 % quand l'enquête en compte 4,1 %, et l'ingénierie de prompt ne déplace cette part que de un dixième à huit dixièmes de point, là où elle fait reculer les transports collectifs de quatre à onze points : deux erreurs coexistent dans le même décideur, et une seule répond à la consigne. Enfin, les deux dimensions absentes du cycle de calibration comme du composite, la couronne de résidence et le type de logement, sont celles où l'agent décroche le plus, de huit et de sept points face au gradient boosté.

**Les résultats détaillés sont à l'[annexe H](99_annexes.md)** : l'erreur par dimension et par décideur, les parts modales de chacun, les strates que le réglage dégrade sur les trois modèles, et quatre planches — la part voiture sur six dimensions, et les quatre modes lus par distance, par occupation et par motif.

<!-- source: scores.json, detail.<dimension>.strates et global.actual/target ; tous les décideurs sur le jeu corrigé …_20260316_EN_c. La figure compare prompt_minimal_02 et prompt_expert_05, régénérée le 2026-09-17 par scripts/analysis/plot_chapitre6.py. Erreur L1 pondérée sur la dimension distance, moyenne des strates couvertes pondérée par leur effectif : 14,19 pour gemini-3.5 sous prompt expert, 16,79 à la forêt aléatoire, 17,79 au gradient boosté, 18,09 à la régression à noyau, 20,73 au logit multinomial. Les 15-19 ans et les déplacements de plus de 50 km résistent à tous les décideurs, méthodes tabulaires comprises : 34 à 59 et 42 à 72 points d'erreur. Annexe H. -->

## 6.4 Décider pareil, décider autrement

Deux décideurs peuvent produire les mêmes parts agrégées sans jamais décider la même chose. À offre égale, sur les déplacements où les deux ont réellement choisi, l'accord se mesure sur le mode le plus probable et sur le mode effectivement tiré.

| Paire | Accord, mode le plus probable | Accord, mode tiré |
|---|---:|---:|
| Gradient boosté / régression à noyau | 91,6 % | 90,5 % |
| Prompt expert `gemini-3.5` / gradient boosté | 69,7 % | 61,4 % |
| Prompt expert `gemini-3.5` / prompt expert `gemini-3.1` | 79,6 % | 72,8 % |

Les quatre méthodes tabulaires forment un bloc, à neuf accords sur dix. Aucun agent n'y entre, et les agents n'en forment pas un second : les deux modèles de langue comparés ici s'accordent aussi peu entre eux qu'avec une méthode tabulaire. Un déplacement sur trois reçoit deux réponses différentes de deux décideurs que les parts agrégées donnent pour voisins.

Lequel des deux a raison sur un déplacement donné ne se lit pas sur la cohorte synthétique, qui ne porte aucune vérité individuelle. L'exactitude unitaire annoncée au § 4.2 se mesure sur la partition de test de l'enquête, 13 045 déplacements découpés par ménage et redressés : l'a priori « toujours la voiture » y obtient 57,1 %, le logit multinomial 76,6 %, la forêt aléatoire 77,6 %, la régression logistique à noyau 78,4 % et le gradient boosté 78,5 %. L'agent est en cours de mesure sur la même partition, par le protocole du § 5.5 : **[xx]** pour le prompt minimal, **[xx]** pour le prompt expert. Un décideur peut restituer la répartition d'un territoire en se trompant sur la moitié des individus, et l'inverse vaut aussi : le composite du § 6.1 ne départage donc pas deux décideurs qui décident différemment un déplacement sur trois.

<!-- sources: moves.csv des exécutions du jeu corrigé, déplacements portant au moins deux options offertes aux deux décideurs, 2 374 à 2 479 selon la paire ; les six paires et l'écart médian entre distributions sont à l'annexe H. Exactitudes : scripts/progedo_logit/{mode_choice_policy,klr_model,rf_mode_choice,mnl_model}_metrics.json, test.accuracy_weighted sur 13 045 déplacements (découpage par ménage, graine 0, poids de redressement) ; l'exactitude de l'a priori vaut la part observée de la voiture. Ces valeurs ne sont pas commensurables avec les composites : jeu différent, support différent. Pour l'agent, l'expérience exp_gemini-35-fl_promin02_jtir_pop-enquete_058_test_… a été lancée le 2026-09-17 à 07:02 et interrompue à 822 déplacements ; le prompt expert n'a pas encore d'exécution. La jointure du journal de décisions aux modes déclarés de l'enquête reste à outiller : ticket 058. -->

## 6.5 Variation de cohorte et dispersion entre graines

Une cohorte de 1 000 personas ne mesure un composite qu'à ±1,3 point près : c'est l'intervalle de confiance à 95 % obtenu en rééchantillonnant les personnes avec remise, et il borne ce que le tableau du § 6.1 permet de départager. L'écart-type apparié de ce terme vaut ≈ 0,7, de sorte qu'aucune marge d'équivalence inférieure à 1,4 point ne se conclura d'un run sur cette cohorte ; seules des cohortes supplémentaires l'abaissent, et trois sont prévues au [ticket 073](../../../tickets/ticket_073_reproductibilite_prompt_calibre_multi_graines_multi_populations.md), axe 2. C'est la raison pour laquelle toutes les comparaisons de ce chapitre sont appariées : jouer les deux décideurs sur les mêmes personas fait agir ce terme des deux côtés, où il s'annule.

La dispersion entre graines, elle, laisse les écarts de ce chapitre où ils sont **TBC**. Rejoué sur la même cohorte avec d'autres graines, un décideur à modèle de langue reste dans la variation de cohorte, et aucune des différences appariées des §§ 6.1 et 6.2 n'y change de signe **TBC**. Le protocole qui l'établit est celui du même ticket, axe 1.

Deux mesures en donnent déjà l'ordre de grandeur. Le même prompt, sur le même modèle et avec la même graine, rejoué sur le substrat corrigé du [ticket 088](../../../tickets/ticket_088_jeu_corrige_et_rejeu_complet.md), déplace son composite de 0,24 à 1,17 point selon le décideur, quand les décideurs déterministes bougent de moins de 0,12 ; et deux exécutions du même prompt sur deux cohortes successives s'accordent sur 86,1 % des modes les plus probables. L'une et l'autre confondent le non-déterminisme du modèle avec le changement de substrat, et c'est le rejeu à l'identique qui les sépare.

Deux asymétries du dispositif restent déclarées plutôt que corrigées. Les méthodes tabulaires ont été ajustées sur des journées réelles, elles-mêmes chaînées, et les jouer sous la contrainte de chaîne applique cette contrainte une seconde fois (§ 4.4). L'agent voit l'agenda de sa journée là où les méthodes tabulaires décident chaque déplacement isolément (§ 4.3, repris au chapitre 8).

<!-- ATTENTION RELECTURE : les deux **TBC** du deuxième paragraphe anticipent un résultat qui n'est pas encore mesuré. Décision de l'auteur du 2026-09-17 : écrire le chapitre en considérant la dispersion inter-graines comme acquise et similaire, et lever les TBC quand le ticket 073 axe 1 aura rendu son rejeu à l'identique. Aucun chiffre n'est avancé tant que la mesure n'existe pas. Le reste est mesuré : ±1,3 point et écart-type apparié de 0,7 du ticket 080 § 0.3, écarts de substrat lus dans les scores.json des deux jeux, accord de 86,1 % issu de deux exécutions du même prompt sur deux cohortes successives. -->

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
