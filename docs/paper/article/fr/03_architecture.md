# 3. Le dispositif : décider dans une ville contrainte

<!-- Dernière mise à jour : 2026-09-11 -->

**Document :** chapitre 3 de l'article AAMAS 2027, **première rédaction en français**. Le maître anglais [`en/03_architecture.md`](../en/03_architecture.md) et le rendu LaTeX [`overleaf/03_architecture.tex`](../overleaf/03_architecture.tex) seront écrits après validation de ce texte ; la parité ne s'applique donc pas encore.
**Statut :** `brouillon v0.4` (11 septembre 2026) — reprises de l'auteur conservées ; quatre phrases reformulées (planning fixe, énumération des aléas, périmètre de l'enquête, attaque du paragraphe sur la sortie du modèle) et le contrat de variables réécrit en clair, la formulation antérieure étant incompréhensible.
**Statut antérieur :** `brouillon v0.3` (11 septembre 2026) — retour au style narratif de la `v0.1`, les corrections de la `v0.2` conservées. Deux ajouts issus d'une vérification dans le code : la formule « GAMA contraint la décision » était un raccourci — ce que GAMA produit, ce sont les conséquences, l'écart entre le trajet planifié et le trajet vécu ; et l'agent **ajuste ses horaires** quand il arrive en retard, ce que le chapitre passait sous silence.
**Statut antérieur :** `brouillon v0.2` (11 septembre 2026) — relecture de l'auteur, quatorze points. Retirés comme hors sujet à huit pages : le détail des appels aux moteurs, le fuseau horaire, le contrôle de rattachement au graphe, le car scolaire, les aménagements de la chaîne. Corrigés : un agent qui ne conduit pas peut être passager ; le modèle ne rend pas un indice mais une probabilité par option. · `brouillon v0.1` (11 septembre 2026) — première rédaction ; chapitre neuf, ni l'arbre `article/` ni le manuscrit figé `v1.6` ne décrivaient le dispositif évalué.
**Place dans l'article :** section 3 du plan annoncé en 1.4 de [`../en/01_introduction.md`](../en/01_introduction.md). État d'avancement : [`../README.md`](../README.md).
**Convention des tags :** un chiffre écrit **[xx.y | exp_id]** est un emplacement à remplir depuis l'export de [`../../methode/experience_plan/experiments.yaml`](../../methode/experience_plan/experiments.yaml). Un chiffre laissé en clair se recalcule depuis un fichier du dépôt ; sa source est donnée en commentaire HTML à côté.
**Sources d'architecture :** [`docs/arch/agents-lifecycle.md`](../../../arch/agents-lifecycle.md), [`routing.md`](../../../arch/routing.md), [`memory-stm-ltm.md`](../../../arch/memory-stm-ltm.md), [`vehicle-chain.md`](../../../arch/vehicle-chain.md).
**À appliquer (Action de rédaction) :** Remplacer la description narrative du dispositif par une formalisation propre en un bloc compact : $\text{Agent}_i = \langle P_i, M_{i,t}, C_i, \pi_\theta \rangle$ où $P_i$ est le persona socio-démographique scellé, $M_{i,t}$ le registre de mémoire bi-composante (STM circulaire, LTM vectorielle), $C_i$ l'état de la chaîne de véhicules du ménage, et $\pi_\theta(a \mid o_t, M_{i,t})$ la distribution verbalisée sur l'espace d'action restreint $\mathcal{A}(o_t, C_i)$. Voir [`../actions.md`](../actions.md) § 3 et [`../ameliorations.md`](../ameliorations.md) § 7.

---

## 3.1 Vue d'ensemble

Le dispositif couple trois composants. Une simulation multi-agents GAMA porte le monde : la géographie réelle de l'aire toulousaine, les réseaux, l'horloge, et l'exécution physique des déplacements. Un contrôleur porte le cycle de vie des agents : il détecte qu'un agent doit partir et construit l'offre d'itinéraires réellement disponible à cette heure-là. Un module de décision porte le choix lui-même : c'est là, et seulement là, qu'intervient le modèle de langue.

La boucle est fermée. Un agent immobile déclenche une planification ; il reçoit les itinéraires qui existent pour ce déplacement et répartit sa préférence entre eux ; sa décision part vers la simulation, qui exécute le trajet sur le réseau et renvoie ce qui s'est réellement passé — correspondances, attentes, heure d'arrivée. Ces retours alimentent la mémoire de l'agent, qui pèsera sur la décision suivante.

L'agent a un planning fixe, et il doit l'accomplir avec ce que la ville offre à cette heure, à cet endroit, et avec les véhicules dont il dispose — ces bornes sont posées par le contrôleur, avant que la question ne soit posée au modèle. Ce que la simulation ajoute est d'une autre nature : elle produit les conséquences. Le trajet vécu n'est pas le trajet planifié ; un bus manqué, une correspondance ratée, un bouchon né d'un incident, un quart d'heure de retard sont des faits produits par l'exécution, et ce sont eux qui reviennent dans la boucle. C'est ce qui distingue le dispositif d'un classifieur interrogé hors sol, et ce qui rend le plancher et le plafond du chapitre 4 comparables à l'agent : tous trois décident sur le même substrat.

## 3.2 Le terrain

Les itinéraires proposés à l'agent viennent de deux sources. OpenTripPlanner produit les itinéraires en transport collectif — bus, tram, métro, TER, cars interurbains — sur les horaires réels des réseaux. Un calcul de plus court chemin sur le graphe OpenStreetMap produit les trajets directs : marche, vélo, voiture. Le périmètre est celui de l'enquête de référence, l'EMC² 2023 du CEREMA : les 453 communes du bassin de vie toulousain. <!-- source: docs/arch/routing.md, § Vue d'ensemble -->

Les itinéraires en transport collectif sont demandés en **arrivée contrainte** : la question posée au calculateur n'est pas « que puis-je faire si je pars maintenant », mais « comment être à l'heure à cette activité ». C'est la forme que prend, dans le dispositif, une contrainte d'agenda.

Tous les modes ne sont pas offerts à tous, et cette restriction s'opère avant la décision. La voiture et le vélo ne sont proposés que si l'agent les possède et qu'ils se trouvent au point de départ. Conduire demande en outre le permis et la majorité — mais un agent qui ne conduit pas peut voyager en voiture comme **passager** d'un ménage motorisé, et l'option lui reste ouverte à ce titre. <!-- source: docs/arch/routing.md, § Modes disponibles par agent ; docs/arch/vehicle-chain.md, § 1 bis -->

## 3.3 Le point de décision

Au moment de choisir, l'agent reçoit un profil court — prénom, âge, occupation, composition du ménage, niveau de revenu —, la destination et sa zone, l'heure de départ, la météo du moment et celle des tranches restantes de la journée, les trajets qu'il lui reste à faire avant de rentrer, les souvenirs jugés pertinents pour ce déplacement, et enfin la liste numérotée des itinéraires, chacun avec son mode et le détail de ses étapes.

Le modèle de langue ne désigne pas un itinéraire : il **répartit une masse de probabilité sur les options**, une entrée par option, chacune avec sa justification. La décision est un tirage dans cette masse, de graine dérivée du contexte du déplacement — reproductible à l'identique, sans être un maximum. Les options lui sont présentées dans un ordre tiré au hasard pour que leur rang ne devienne pas une préférence. Ce détail décide de la nature de ce que nous mesurons : c'est une distribution que le modèle produit. <!-- source: mobility_llm/src/mobility_llm/mode_choice.py (draw_index, argmax_index) ; categories/itinary_multi_agent/output_schema.json -->

Le profil n'est pas rédigé librement. La liste des variables qui décrivent la personne et son déplacement est fixée d'avance, et c'est exactement sur ces variables que sont ajustés les modèles statistiques auxquels l'agent sera comparé : les deux voient la même chose. Le chapitre 4 en fait la première des trois règles du contrat d'évaluation. <!-- source: scripts/progedo_logit/feature_spec.json, 21 variables -->

## 3.4 La mémoire

Sans mémoire, un agent redécide chaque matin à l'identique, et aucune dynamique n'est observable. Le dispositif en porte deux niveaux.

La mémoire courte est un tampon circulaire par agent, cent entrées au plus, partitionné par activité. Elle n'enregistre pas que des décisions : elle reçoit l'expérience physique que la simulation produit — correspondances, attentes à l'arrêt, heures d'arrivée, les évènements de la journée. C'est par là que le vécu entre dans le raisonnement, et non par une description que l'agent se ferait de lui-même.

Au-delà d'un seuil d'entrées, une réflexion est produite et versée dans la mémoire longue, un index vectoriel propre à chaque agent. La récupération n'y est pas une simple recherche de similarité : elle combine proximité sémantique, recouvrement lexical et décroissance temporelle, pondérés 0,4 / 0,3 / 0,3, sur une fenêtre de trente jours, et ne rend que les dix meilleures entrées. La décroissance dans le temps est ce qui permet à un souvenir de peser moins qu'hier sans disparaître. Périodiquement, une auto-réflexion consolide ces traces en énoncés de plus haut niveau — des habitudes, au sens propre. <!-- source: docs/arch/memory-stm-ltm.md, § Résumé des paramètres clés -->

L'agent ne se contente pas de se souvenir qu'il est arrivé en retard : il en tire une conséquence. Une arrivée tardive avance sa cible horaire pour cette activité, de 75 % du retard constaté, dans la limite d'un quart d'heure par ajustement et sans jamais empiéter sur l'activité précédente ni sur la suivante. Le réajustement lui est écrit en mémoire à la première personne, si bien qu'il pourra le relire en décidant demain. C'est la forme la plus élémentaire d'apprentissage que porte le dispositif, et elle ne doit rien au modèle de langue : elle est produite par l'écart entre l'horaire prévu et l'horaire vécu. <!-- source: llm-agents/urban_mobility_agents/simulation_controller.py, reschedule_amount ; settings.agent.reschedule_transition_ratio = 0.75, plafond 15 min -->

## 3.5 La journée est une chaîne, pas une suite de tirages

Un agent parti travailler à vélo n'a pas de voiture au bureau le soir. Cette évidence n'en est pas une pour un système qui déciderait chaque déplacement indépendamment, et c'est ce qui sépare le dispositif d'un classifieur appelé une fois par trajet.

Le contrôleur tient donc, pour chaque agent, la position de ses véhicules personnels, et il en tire trois règles : un mode véhiculé n'est proposé que si le véhicule est garé au point de départ ; le véhicule du mode retenu suit son utilisateur à destination, les autres restent où ils sont ; et sur un trajet de retour, si un véhicule attend au départ, les itinéraires candidats sont restreints à ce mode. Cette dernière règle filtre les options, elle n'ajoute pas de décision. <!-- source: docs/arch/vehicle-chain.md, § Les trois règles -->

Il faut en tirer la conséquence méthodologique, et le chapitre 6 y revient : une part de la répartition modale simulée est produite **sous** ces contraintes, pour être plus représentative des situations réelles. Un agent dont la voiture est restée au domicile ne choisit pas de ne pas conduire, il ne peut pas. C'est pourquoi le plancher et le plafond du chapitre 4 sont soumis exactement aux mêmes contraintes : sans cela, nous comparerions des décisions prises dans des mondes différents.
