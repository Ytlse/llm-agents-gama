# 7. Réagir à ce qu'aucune variable n'encode

<!-- Dernière mise à jour : 2026-09-21 -->

**Document :** chapitre 7 de l'article AAMAS 2027 — le chapitre des régimes qu'aucune variable d'enquête ne porte : le chapitre 6 mesure l'agent sur les 21 entrées du contrat, celui-ci le mesure sur un article du jour et sur le retard de la veille.
**Statut :** `brouillon v1.0` (17 septembre 2026) — réécriture complète du brouillon hérité du manuscrit `v1.6`. Le vocabulaire « Tier 1 / 2 / 3 » sort. La formule $w_m(t)$ du manuscrit sort du texte : elle n'est pas implémentée, et le plan longitudinal en fait un modèle descriptif ajusté après coup. Les deux régimes passent dans l'ordre où le dispositif reçoit ses ingrédients : la presse d'abord, mémoire éteinte, la mémoire ensuite. Aucun résultat n'est publié : les deux campagnes ne sont pas jouées, et chaque grandeur attendue porte l'emplacement du run qui la produira.
**Statut antérieur :** `brouillon v0` (10 septembre 2026) — extrait de `MANUSCRIT_DETAILLE_2026.md` `v1.6`, § 5, Étape 3, avec la numérotation du manuscrit.
**Place dans l'article :** section 7 du plan annoncé en 1.4 de [`../en/01_introduction.md`](../en/01_introduction.md). Trame : [`../plan/PLAN.md`](../plan/PLAN.md). État d'avancement : [`../README.md`](../README.md).
**Convention :** un chiffre **entre crochets** est un emplacement vide, suivi du run qui le remplira.

---

Le chapitre 6 compare les décideurs sur les 21 variables du protocole, et les quatre références tabulaires y devancent le meilleur prompt expert, 3,60 à 4,09 de composite contre 4,49. Ces 21 variables décrivent une personne, un motif, une heure et une géométrie ; aucune ne porte la météo, aucune ne porte une durée de trajet, aucune ne porte un événement du jour. <!-- source : scripts/progedo_logit/feature_spec.json, 21 entrées : 12 persona, 2 motif, 1 heure de départ, 6 géométrie -->

Ce chapitre mesure les mêmes décideurs sur deux régimes que l'enquête ne tabule pas : un article de presse paru le matin, et un retard subi la veille. Aucune enquête ne suit les mêmes voyageurs à travers un événement toulousain daté, donc aucune valeur mesurée ici n'a de cible. Ce qui se teste est le signe d'un déplacement, l'ordre des conditions, et la monotonie d'un retour, tous trois écrits avant le premier appel au modèle.

Les deux régimes ajoutent un ingrédient à la fois au dispositif du chapitre 6. La section 7.1 ajoute un texte au contexte, mémoire éteinte comme aux chapitres 5 et 6. La section 7.2 allume la mémoire et fait subir un retard. Le chapitre ne cherche pas à isoler l'effet d'un paramètre d'oubli : les variantes de vitesse d'oubli se rapportent en annexe, au titre de la robustesse.

## 7.1 Cinq événements de presse locale, cinq conditions

### 7.1.1 Les événements

Cinq articles réels et datés de la presse locale toulousaine agissent chacun par un canal qu'aucune des 21 variables ne représente. Des rafales de vent d'Autan à plus de 80 km/h ferment les parcs clôturés de la ville et exposent les ponts sur la Garonne. Une rumeur de punaises de lit sur les sièges en tissu du métro et des bus laisse l'offre technique intacte et la crédibilité du mode entamée. Une grève illimitée des éboueurs rend les trottoirs de l'hyper-centre impraticables sans rien changer à leur géométrie. La parade de rue de La Machine piétonnise le centre devant une foule compacte. Le lancement de VélôToulouse à assistance électrique efface le dénivelé des coteaux.

Ces cinq événements sont retenus dans une matrice de trente articles candidats dont chaque cellule porte un impact modal coté de zéro à trois, une échelle spatiale et une source vérifiée. <!-- source : docs/paper/sources/actualites/RAPPORT_SCENARIOS_QUALITATIFS_TOULOUSE.md, § 2 la matrice, § 3 les cinq retenus ; la matrice complète va en annexe --> La matrice entière paraît en annexe ; le chapitre n'évalue que les cinq.

### 7.1.2 Les cinq conditions

Chaque événement est joué sous cinq conditions sur les mêmes 3 299 déplacements de la cohorte scellée, à mémoire éteinte, l'ordre des itinéraires proposés étant retiré au hasard à chaque requête. <!-- source : population_1000_AAMAS_v6 ; option_order_seed, contrôle rendu nécessaire par la sensibilité à l'ordre que mesure SILICA (Bin Tareaf, 2026) -->

| # | Condition | Ce que le décideur reçoit | Ce que la condition sépare |
|---|---|---|---|
| C1 | Agent, journée nominale | aucun article | le niveau de référence de la journée |
| C2 | Agent, article brut | le texte de presse tel qu'il a paru | l'effet total de l'événement |
| C3 | Agent, paraphrase neutre | le même fait, réécrit sans aucune mention de mode ni de voirie | l'exécution d'une consigne lexicale de l'inférence sur la situation |
| C4 | Agent, texte témoin | un article local réel de longueur comparable, sans lien plausible avec le choix modal | l'effet du contenu de l'effet d'ajouter un texte |
| C5 | Référence tabulaire, événement encodé | l'événement traduit dans l'offre : liens coupés, fréquences dégradées | ce qu'une référence tabulaire fait de l'événement quand il l'atteint |

La condition C5 n'existe que lorsque l'événement modifie l'offre. Les 21 variables ne portant ni météo ni durée, le seul canal par lequel un événement atteint une référence tabulaire est la règle 3 du protocole : un mode retiré de l'offre sort de la prédiction, qui se renormalise sur les modes restants. La parade de La Machine se traduit ainsi en coupures dans le graphe et en modes retirés ; la rumeur des punaises de lit ne se traduit pas, et C5 y est identique à C1. La portée se mesure et se publie plutôt qu'elle ne se suppose : sur une coupure de rocade, 18,2 % des trajets voiture de 7 h à 9 h empruntent l'axe touché. <!-- source : trace 2026-09-14_11-20_exposition_rocade_lot0bis ; la mesure porte sur un événement écarté depuis, elle donne l'ordre de grandeur, pas la valeur des cinq -->

### 7.1.3 Prédictions et mesure

Pour chaque événement et chaque mode, le sens attendu du déplacement est écrit avant le premier appel, soit vingt prédictions signées. La grandeur mesurée est l'écart de part modale entre C2 et C1, apparié sur les mêmes déplacements, avec un intervalle obtenu par rééchantillonnage par grappe au niveau de la personne (§ 4.1).

Sur vingt prédictions, la barre du test binomial contre le hasard se situe à quinze signes concordants ($p = 0{,}021$) ; quatorze ne suffisent pas ($p = 0{,}058$). Le chapitre publie ce taux, **[xx/20 | exp_05a-e]**, et le $\kappa$ pondéré sur l'intensité attendue sans le tester, vingt items ne le permettant pas.

Deux contrôles bornent la lecture. Le texte témoin donne l'amplitude d'un déplacement modal sans contenu pertinent, **[x.x | C4 − C1]** point, à comparer au rejeu à l'identique de la journée nominale, qui donne le bruit propre du décideur. <!-- source : ticket 080 § 3.1 bis, rejeu à l'identique prêt sans code ; la dispersion inter-graines n'est pas mesurée (§ 6.1), elle ne peut pas servir de référence de bruit --> La paraphrase donne la part du déplacement qui survit au retrait de tout lexique de mobilité, **[xx]** % de l'amplitude de C2.

Les prédictions tombent si le taux de signes n'atteint pas quinze sur vingt, si le texte témoin déplace autant que l'article, ou si la paraphrase perd le signe de l'article sur la majorité des cellules.

![Réponse modale sous les cinq conditions, cinq événements par quatre modes](../images/ch7_presse.png)

*Figure 7.1 — Écart de part modale par rapport à la journée nominale, pour les cinq événements et les quatre modes. Chaque cellule porte trois marqueurs, article brut, paraphrase et texte témoin, avec leur intervalle ; le signe attendu est en filigrane. La condition C5 n'apparaît que sur les cellules où l'événement atteint l'offre.*

## 7.2 Cinq jours, un retard subi le deuxième

### 7.2.1 Le dispositif

Un sous-échantillon de la cohorte scellée est joué trois fois sur cinq jours ouvrés dans GAMA, en mode hors ligne, avec le même calendrier, la même météo, la même offre et les mêmes graines. Le tirage se fait par ménages entiers, pour que la chaîne des véhicules du foyer reste cohérente, à 200 agents dont au moins 60 abonnés ou captifs des transports collectifs. <!-- source : docs/paper/methode/experience_plan/ETAPE_3A_PLAN_LONGITUDINAL.md § 4.3 et § 4.6 ; l'effectif est calibré sur la puissance du contraste apparié, pas sur le budget -->

Le deuxième jour à 17 h, une panne du réseau impose 45 minutes de retard aux usagers du métro concernés. L'incident est déclaré une fois et produit deux choses : un retard effectivement subi dans la simulation, et une observation écrite dans les mots de l'agent, jamais sous forme de consigne. <!-- source : ticket 079, format de déclaration et garde de contenu au lot 1 ; un texte impératif est refusé au chargement --> Le réseau est nominal à partir du troisième jour.

Trois conditions partagent ces tirages : l'agent à mémoire, le même agent dont la mémoire est éteinte, et la référence tabulaire, sans état par construction. L'unité d'analyse est l'agent exposé, celui qui a vécu le retard ; son effectif se publie avec le résultat.

### 7.2.2 Ce que le dispositif prédit

Trois mécanismes déjà en service décident de ce qui peut être observé, et leurs constantes bornent les prédictions.

La gravité de l'incident se calcule depuis ce que la simulation mesure. Un retard qui sature le plafond de 30 minutes vaut 0,50 et l'incident de réseau 0,20, soit 0,70, le seuil au-delà duquel un souvenir est servi sans condition de contexte. La durée de vie de la trace passe alors de 2,8 à 14,6 jours : trois jours après le choc, elle pèse encore 81 % de son poids initial. <!-- source : llm/gravite.py, force = min(S0 × (1 + 6·I), 30) avec S0 = 2,8 j ; llm/chocs.py § 1 ; settings.agent.memoire__importance_choc = 0,7 --> La trace ne s'efface donc pas dans la fenêtre de l'expérience, et l'oubli à l'horloge n'explique aucun retour.

La consolidation du soir peut en tirer un concept, qui naît sans observation à son actif et vaut donc 0,50 sous la règle de succession de Laplace, le seuil au-dessous duquel un concept cesse d'être servi. <!-- source : llm/concepts.py, confiance = (obs + 1) / (obs + contre + 2), memoire__confiance_seuil_service = 0,5 ; mesuré au ticket 077 : 225 concepts sur 231 restés à 0,50 --> Une seule contradiction le fait tomber à 0,33 et le met hors service.

Contredire cette croyance suppose un trajet en métro sans retard. Le retour se fait donc agent par agent, au rythme des ré-essais, et non par une décroissance commune.

Les prédictions suivent. Le deuxième jour après 17 h, les trois conditions évitent le mode perturbé, l'offre étant dégradée pour toutes. Le troisième jour, l'offre étant redevenue nominale, la part du mode perturbé chez les exposés place l'agent à mémoire sous les deux autres, qui restent dans l'intervalle de leur régime d'avant le choc : **[xx.x | exp_04a]** contre **[xx.x | exp_04b]** et **[xx.x | exp_04c]**. Du troisième au cinquième jour, le retour de l'agent à mémoire est monotone ; il s'ajuste par $\delta_t = A e^{-t/\tau} + c$, dont la constante **[x.x]** jour et la part permanente **[x.x]** point se publient avec leur intervalle par bootstrap sur les agents. Les pertes permanentes de part relevées après une grève de transport, de 0,3 à 2,5 %, servent d'ordre de grandeur et non de cible.

Ces prédictions tombent si l'agent sans mémoire montre la même inertie au troisième jour, si le retour n'est pas monotone, ou si l'effectif d'exposés passe sous le seuil déclaré, auquel cas le résultat se rapporte comme non concluant.

![Part du mode perturbé chez les agents exposés, du premier au cinquième jour](../images/ch7_hysteresis.png)

*Figure 7.2 — Part du mode perturbé chez les agents exposés, trois conditions, avec intervalles. Le choc frappe le deuxième jour à 17 h ; l'offre est nominale à partir du troisième.*

### 7.2.3 Ce que la mémoire montre pendant ces cinq jours

Le dispositif journalise, par agent exposé et par jour, si le souvenir du choc a été servi à la décision, et les opérations que la consolidation applique aux concepts : création, confirmation, contradiction. <!-- source : memoire_par_jour.csv, choc_par_jour.csv, habitudes_par_activite.csv ; docs/arch/mesures-personas.md § 3 --> La prédiction est que la courbe de retour suit la courbe cumulée des contradictions, et non l'âge de la trace.

Un pilote de dix jours sur cinq agents donne la mesure de ce que cette prédiction demande : 38 créations, 61 confirmations et une seule contradiction, celle de l'agent exposé au choc le jour même. <!-- source : run du 2026-09-16, ticket 093 --> Si les exposés ne ré-essaient pas le mode perturbé, la croyance reste en service et le retour n'a pas de moteur ; c'est un résultat mesurable du dispositif, au même titre que le retour.

## 7.3 Ce que ce chapitre transmet

Les deux régimes donnent à lire ce que les 21 variables du protocole ne portent pas : la réaction à un texte paru le matin, et la persistance d'un retard subi la veille. Leur portée est bornée par ce que le dispositif encode : un seul choc, un seul modèle, une condition tabulaire informée seulement là où l'événement atteint l'offre, et un effectif d'exposés qui décide de ce qui est mesurable.

Le chapitre 8 discute les limites du protocole et les implications pour des conceptions hybrides ; le coût d'exécution des conditions à modèle de langue est au chapitre 9.

---

### Tickets associés à ce chapitre

- [Ticket 041](../../../tickets/ticket_041_etape_3a_hysteresis_longitudinale.md) — protocole longitudinal, bras, effectif, calendrier et prédictions préenregistrées
- [Ticket 048](../../../tickets/ticket_048_calendrier_de_consolidation_et_echelle_d_oubli.md) — plancher de consolidation à 22 h et constante d'oubli en jours ; clos le 21 septembre 2026, son reliquat est le lot F du ticket 095
- [Ticket 059](../../../tickets/ticket_059_etape_3b_presse_locale_et_predictions_preenregistrees.md) — protocole à cinq conditions, corpus de presse et métriques de concordance
- [Ticket 063](../../../tickets/ticket_063_campagne_experimentale_hysteresis_longitudinale.md) — campagne longitudinale d'hystérésis
- [Ticket 064](../../../tickets/ticket_064_campagne_experimentale_presse_locale_et_scoring.md) — campagne de presse locale et scoring
- [Ticket 071](../../../tickets/ticket_071_evolution_memoire_du_code_actuel_a_l_etat_vise.md) — gravité déterministe, viviers de rappel et durée de vie des souvenirs
- [Ticket 077](../../../tickets/ticket_077_la_memoire_apprend_sur_des_observations_fausses.md) — intégrité des observations dont la mémoire apprend
- [Ticket 079](../../../tickets/ticket_079_chocs_declares_vecus_par_les_agents.md) — déclaration d'un choc subi et du souvenir qu'il laisse
- [Ticket 093](../../../tickets/ticket_093_personas_mesurables_et_suivi_des_habitudes.md) — mesures par jour simulé, habitudes et opérations de concept
- [Ticket 095](../../../tickets/ticket_095_duree_d_un_souvenir_et_enquete_du_soir.md) — durée d'un souvenir dérivée de sa gravité, enquête du soir, et le calendrier de consolidation repris du 048

---

<!-- NOTE DE TRAVAIL — à traiter, ne fait pas partie du texte

ORDRE DES DEUX RÉGIMES. Ce chapitre passe la presse avant l'hystérésis ; le § 1.4 et
`plan/PLAN.md` les annoncent dans l'ordre inverse. Deux phrases du chapitre 1 et trois lignes
du plan restent à aligner, sous leur propre accord.

AVANT LE PREMIER APPEL, § 7.1.
1. La grille des vingt signes n'en est pas encore une : trois cellules sur vingt sont
   ambiguës dans le rapport de scénarios (marche sous La Machine, « polarité duale » ;
   voiture sous la grève des éboueurs, « ralentissement et contournement » ; marche sous
   VélôToulouse, « réduction d'effort »). Un signe par cellule, ou une règle explicite pour
   l'absence d'effet attendu, avant tout appel au modèle.
2. `docs/paper/methode/experience_plan/experiments.yaml` porte encore les trois événements
   antérieurs (Minotaure, canicule, coupure de rocade) sur `gemini-3.1-flash-lite`, lignes 459
   à 790. À régénérer pour les cinq événements du § 1.3 et le modèle du chapitre 6.
3. Les textes des conditions C2, C3 et C4 n'existent pas au dépôt : `articles_txt/` est
   annoncé par `experiments.yaml` et absent. Le texte témoin s'apparie en longueur.
4. Le script d'injection du contexte de presse n'existe pas (ticket 064).

AVANT LE PREMIER APPEL, § 7.2.
5. Les trois conditions ne sont pas jouables dans le même mode : l'agent à mémoire ne vit que
   dans GAMA, les références tabulaires que sur la plateforme, et aucun chemin outillé ne les
   compare terme à terme (plan longitudinal, révision du 2026-09-15, § 3). Trois issues :
   brancher les décideurs tabulaires dans le contrôleur GAMA, rejouer hors ligne les décisions
   du run GAMA depuis moves.csv, ou assumer la condition tabulaire par construction. Le rejeu
   hors ligne garde une mesure là où la troisième issue donne une constante.
6. Le lot F4 du ticket 095 bloque l'expérience tant que les déclarations `memory_decay_lambda`
   et `memory_horizon_days` d'`experiments.yaml` n'ont pas été converties vers
   `long_term_retrieval__force_base_jours`. Le ticket 048, qui portait ce blocage, est clos
   depuis le 2026-09-21 ; la conversion reste à faire.
7. Le cas C3 du ticket 079 (panne du réseau) est écrit sur deux jours d'affilée ; le § 1.3
   annonce un choc au jour 2 et un réseau nominal dès le jour 3. Aligner l'un ou l'autre.
8. Le ticket 077 a livré ses lots A et B le 2026-09-15 (92 tests) : l'axe des concepts et les
   observations que GAMA envoie sont réparés, et les opérations de concept du § 7.2.3 ont de
   quoi mesurer. Ce qui reste au 077 est son lot D1, un arbitrage sur le service de
   l'auto-réflexion dans le bloc noyau ; il ne conditionne pas ce chapitre.

TRANSMISSION AU SEIN DU FOYER. Le ticket 078 n'a pas de code et son run macro est différé au
titre d'une campagne. Sa dépendance au 077 est levée depuis le 2026-09-21, les lots A et B de
celui-ci étant livrés. Il ne figure pas dans ce chapitre ; sa place, le jour où il aura une
mesure, est une perspective du chapitre 8.

CITATIONS. Aucune référence nouvelle n'entre ici. Les deux ordres de grandeur du § 7.2.2
(perte permanente de part après une grève) viennent de van Exel & Rietveld (2001) et Larcom,
Rauch & Willems (2017), cités par le plan longitudinal ; ils n'ont ni PDF au dépôt ni entrée
au bib, la phrase les porte donc sans appel de citation. À instruire dans CITATIONS.md avant
de les nommer dans le texte.
-->
