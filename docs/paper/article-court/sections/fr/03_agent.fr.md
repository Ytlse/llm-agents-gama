# 3. L'agent évalué

<!-- Rendu français de 03_agent.en.md (consigne R17), article court AAMAS 2027, PLAN.md § 3.
     Rendu le 2026-09-22 par l'agent article-writer. L'anglais fait foi : ce texte en reprend
     les coupes de paragraphe, le compte de phrases, les chiffres et les commentaires de
     source. Aucun chiffre de cette section ne dépend du ticket 103 : aucun emplacement [c2].
     ⚠ Le master fr/03_Architecture.md porte une réserve de datation sur son § 3.4,
     signalée au compte-rendu. -->

Chaque agent transforme la description d'un déplacement en une préférence sur les options
proposées. Cette section dit ce qu'il reçoit, ce qu'il rend, et les deux mécanismes que
l'article met à l'épreuve, la masse de probabilité et la mémoire.

## 3.1 La boucle

Trois composants portent la simulation. Une simulation multi-agents GAMA porte le monde : la
géographie réelle des 453 communes, les réseaux, l'horloge et l'exécution physique de chaque
déplacement. OpenTripPlanner produit les itinéraires en transports collectifs sur les horaires
réels. Un calcul de plus court chemin sur le graphe OpenStreetMap produit les trajets directs à
pied, à vélo et en voiture. Un contrôleur porte le cycle de vie des agents et construit les
options disponibles à l'heure du départ. Il retient l'horloge, de sorte qu'aucun agent ne parte
sans avoir décidé. Un module de décision produit le choix. Le modèle de langue n'intervient que
dans ce module.

<!-- source: fr/03_Architecture.md § 3.1, premier paragraphe : simulation GAMA (géographie
     réelle de l'aire toulousaine, réseaux, horloge, exécution physique), contrôleur du cycle
     de vie retenant l'horloge tant qu'un agent n'a pas décidé, module de décision « c'est là,
     et seulement là, qu'intervient le modèle de langue » (clivée du master retirée par R5).
     Les deux moteurs viennent du § 3.2 du master : OpenTripPlanner sur les horaires réels des
     réseaux, plus court chemin sur le graphe OpenStreetMap pour la marche, le vélo et la
     voiture. Les 453 communes sont le périmètre de l'EMC² 2023, § 3.1 du master et § 4.1 de
     cet article. Sources d'architecture : docs/arch/agents-lifecycle.md, docs/arch/routing.md
     § Vue d'ensemble.
     Nommage des plateformes en corps de texte : demandé par la relecture v1, item T1, qui
     lève la consigne antérieure de ne pas les écrire. Le paragraphe est repris de T1 mot pour
     mot, à deux exceptions imposées par R1 : « the transport networks » devient « the
     networks » (26 mots) et la phrase du contrôleur est coupée en deux (27 mots). -->

La boucle se referme sur les retours de la simulation. Un agent qui doit partir déclenche une
planification, reçoit les itinéraires que les deux moteurs produisent, et répartit sa
préférence. La simulation exécute le trajet et renvoie ce qui s'est passé, les correspondances,
les attentes, l'heure d'arrivée. Ces retours alimentent la mémoire qui pèse sur la décision
suivante.

<!-- source: fr/03_Architecture.md § 3.1, troisième paragraphe (boucle fermée).
     « The routing engines » renvoie aux deux moteurs nommés au paragraphe précédent (T1) ;
     le manque signalé à la version 1 est comblé.
     Sortent, par le PLAN § 3.1 : le quadruplet formel, l'ordonnancement par échéance
     croissante, le planning fixe et le week-end sans activité. La rétention de l'horloge, que
     le plan faisait sortir, revient en corps de texte par T1. -->

*Figure 1 — Le modèle de langue intervient en un point de la boucle, celui que cet article met
à l'épreuve.*

<!-- source: PLAN § 9, figure 1, pleine largeur, images/architecture_GAMA_Agents.jpg ;
     affirmation de légende reprise du plan. -->

## 3.2 Ce que l'agent reçoit et ce qu'il rend

L'agent reçoit une observation par déplacement et rend un nombre par option. L'observation
porte un profil court de la personne et de son ménage, la destination, l'heure de départ et la
météo à venir. Elle porte aussi les trajets restants avant le retour au domicile, les souvenirs
jugés pertinents, et la liste numérotée des itinéraires viables.

<!-- source: fr/03_Architecture.md § 3.3, première phrase : prénom, âge, occupation,
     composition du ménage, niveau de revenu, destination et zone, heure de départ, météo du
     moment et des tranches restantes, trajets restants avant le retour, souvenirs jugés
     pertinents, liste numérotée des itinéraires avec mode et étapes. L'espace d'action formel
     A(o_t, C_i,t) ⊆ O(o_t) sort, par le PLAN § 3.1. -->

Le modèle répartit une masse de probabilité sur cette liste, une entrée par option. La masse de
probabilité est la part de préférence placée sur une option. Les entrées d'une même décision
somment à un. La décision jouée est un tirage au hasard dans ce vecteur, jamais l'option la
mieux classée. Les options sont présentées dans un ordre tiré au hasard, pour que leur rang ne
devienne pas une préférence. Un décideur qui rend un vecteur peut être noté contre une
distribution.

<!-- source: fr/03_Architecture.md § 3.3, deuxième paragraphe : vecteur p_t sur le simplexe
     des options viables, tirage catégoriel a_t ~ Cat(p_t) de graine dérivée du contexte,
     ordre des options tiré au hasard « pour que leur rang ne devienne pas une préférence » ;
     mobility_llm/src/mobility_llm/mode_choice.py (draw_index, argmax_index) ;
     categories/itinary_multi_agent/output_schema.json. La dernière phrase est la seule
     justification de la comparaison distributionnelle ici ; la raison du tirage plutôt que de
     l'argmax vit à la règle 2 du § 4 et n'est pas redite. -->

## 3.3 Deux registres de mémoire

Deux registres retiennent ce qu'un agent a vécu. Un tampon court terme reçoit les décisions et
l'expérience physique que la simulation renvoie. Une consolidation verse chaque soir ce tampon
dans le registre long terme. Une trace épisodique dit ce qui est arrivé et quand, avec un poids
qui décroît d'une constante de temps de 2,8 jours. Une croyance dit ce que l'agent tient pour
vrai, ne s'érode pas, et vit sur une confiance que les observations déplacent. Le soir, chaque
membre du ménage raconte sa journée aux autres, et ce récit entre dans leur réflexion.

<!-- source: fr/03_Architecture.md § 3.4 : tampon circulaire de cent entrées au plus,
     partitionné par activité, recevant décisions et expérience physique ; consolidation à dix
     entrées et de toute façon une fois par jour simulé en fin de soirée
     (settings.agent.stm_reflection_min_entries = 10, stm_reflection_daily_floor_hour = 22) ;
     index vectoriel par agent ; traces épisodiques érodées depuis le dernier rappel, constante
     de temps 2,8 jours, allongée par la gravité et plafonnée à trente jours ; concepts non
     érodés vivant sur une confiance (distinction de Tulving).
     ⚠ « Concept » dans les masters est écrit ici « belief » : le § 6 déjà rédigé n'emploie que
     « belief », et R12 impose un seul mot par concept. Signalé au compte-rendu.
     Récit du soir et saut unique par le ménage : fr/07_Adaptation.md § 7.1 (ticket 100,
     décisions D1 et D2, champ de provenance distinguant une croyance entendue d'une croyance
     vécue). Phrase ajoutée par la relecture v1, item T2, mot pour mot ; sa place de
     conception est ici, le § 6.2 la raccourcit d'autant (item N1).
     ⚠ Aucun code au 22 septembre pour le saut par le ménage : écrit au présent de conception,
     jamais au passé de mesure ; le § 6.2 porte la mention que le cas tracé ne l'exerce pas.
     ⚠ Réserve de datation : le § 3.4 du master a été écrit en avance sur le code (statut
     v0.5, ticket 071) ; les quatre blocs et la durée de service sont, eux, mesurés au § 6.
     Sortent, par le PLAN § 3.3 : la figure des deux horloges, le score de rappel à cinq
     termes, le réajustement d'horaire à 75 %, l'allongement de la constante par la gravité. -->

Quatre blocs du prompt portent le passé jusqu'à une décision, et une mesure peut dire lequel a
agi. Ce sont les habitudes de l'agent, ses croyances, ce qui a changé récemment, et trois
souvenirs rappelés par similarité. Le bloc « ce qui a changé récemment » porte les
événements dont la fenêtre reste ouverte, fenêtre que la gravité fixe à l'entrée. Les mesures
d'une journée ordinaire tournent avec cette mémoire désactivée.

<!-- source: fr/03_Architecture.md § 3.4, dernier paragraphe des voies : « mes habitudes, ce
     que l'agent fait le plus souvent ; ce que je sais, les croyances au-dessus du seuil de
     service, six au plus, classées par confiance puis par nombre d'observations ; ce qui a
     changé récemment, le bloc où figurent les événements dont la fenêtre est encore ouverte ;
     et les souvenirs rappelés par similarité, trois, choisis pour ce déplacement »
     (llm/noyau.py, bloc_habitudes, bloc_connaissances, bloc_changements). Gravité fixant la
     durée de service : llm/gravite.py, llm/noyau.py duree_service_jours, ticket 095 lot A.
     Le seuil de six croyances n'est pas écrit ici, faute de place.
     Mémoire désactivée sur le banc : fr/08_Limitations.md § 8.3, « les expériences d'ablation
     tournent mémoire désactivée ». Cette phrase règle la dette signalée au § 4 ; la clause
     équivalente du § 6.3 déjà rédigé devient redondante et doit être coupée. -->

## 3.4 La chaîne de véhicules

Décider chaque déplacement isolément produit des journées physiquement impossibles. Un agent
parti travailler à vélo n'a pas de voiture au bureau le soir. Le contrôleur tient donc la
position de chaque véhicule personnel. Un véhicule n'est proposé que depuis l'endroit où il est
garé, après quoi il suit son utilisateur. Sur un trajet de retour, un véhicule laissé au départ
restreint ce trajet à son mode.

<!-- source: fr/03_Architecture.md § 3.5 et docs/arch/vehicle-chain.md, § Les trois règles :
     un mode véhiculé n'est proposé que si le véhicule est garé au point de départ ; le
     véhicule du mode retenu suit son utilisateur à destination, les autres restent où ils
     sont ; sur un trajet de retour, si un véhicule attend au départ, les itinéraires candidats
     sont restreints à ce mode. Troisième règle : elle filtre les options et n'ajoute pas de
     décision. Sort : l'éligibilité (permis, majorité, passager d'un ménage motorisé), § 3.2
     du master. -->

Ces règles s'appliquent à tous les décideurs comparés, modèles tabulaires compris, car sans
elles nous comparerions des décisions prises dans des mondes différents. La section suivante
dit ce que cette comparaison égalise par ailleurs.

<!-- source: fr/03_Architecture.md § 3.5, dernier paragraphe : « Le plancher et le plafond du
     chapitre 4 sont soumis aux mêmes contraintes » ; PLAN § 3.4, « elle s'applique à tous les
     décideurs comparés, tabulaires compris ». Renormalisation sur l'offre au § 4, règle 3 :
     la chaîne est amont, la renormalisation aval ; les deux ne se redisent pas. -->

<!--
=== SECTION REPORT ===
Section        : 03 — L'agent évalué (rendu français de 03_agent.en.md)
File           : docs/paper/article-court/sections/03_agent.fr.md
Words / budget : 629 mots de prose, contre 583 à l'anglais (+7,9 %, dilatation ordinaire du
                 français). Budget PLAN § 3 = 450 mots ; l'anglais le dépasse déjà de 29,6 %
                 par la relecture v1 (items T1 et T2) et propose de porter le budget à 580.
                 Le français vaut +8,4 % sur ce budget révisé.
Skeleton       : Chaque agent transforme la description d'un déplacement en une préférence sur les options proposées.
                 Trois composants portent la simulation.
                 La boucle se referme sur les retours de la simulation.
                 L'agent reçoit une observation par déplacement et rend un nombre par option.
                 Le modèle répartit une masse de probabilité sur cette liste, une entrée par option.
                 Deux registres retiennent ce qu'un agent a vécu.
                 Quatre blocs du prompt portent le passé jusqu'à une décision, et une mesure peut dire lequel a agi.
                 Décider chaque déplacement isolément produit des journées physiquement impossibles.
                 Ces règles s'appliquent à tous les décideurs comparés, modèles tabulaires compris.
                 Le squelette français répond ligne pour ligne au squelette anglais.
Checker        : verifier_forme.py sort 0 ; --squelette lu d'une traite. Une seule reprise a
                 été nécessaire : « Le bloc « ce qui a changé récemment » porte… » comptait
                 26 mots (R1), les guillemets étant comptés ; écrit « Le bloc de ce qui a
                 changé récemment porte… », 25 mots, sens inchangé. Les motifs R5 du script
                 sont anglais ; relecture manuelle des clivées françaises (« c'est … que »,
                 « ce qui … c'est ») : aucune. « Ce sont les habitudes de l'agent… » rend
                 « They are the agent's habits… », présentatif d'énumération et non clivée.
Terms defined here     : masse de probabilité, trace épisodique, croyance, consolidation,
                 les quatre blocs du prompt, chaîne de véhicules.
Terms used, undefined upstream : aucun. « décideur » est défini au § 1.3 ; « commune » n'est
                 pas glosé, comme en anglais.
Figures cited  : 453 communes — fr/03_Architecture.md § 3.1 et périmètre EMC² 2023, aucune
                 réserve ; 2,8 jours — fr/03_Architecture.md § 3.4, réserve de datation du
                 master portée au commentaire de source ; Figure 1 — PLAN § 9.
Placeholders   : aucun.
Left out       : rien de plus que l'anglais ; le rendu ne retranche ni n'ajoute.
Flags for the author :
  1. Rendu, non réécriture : les cinq signalements du compte-rendu anglais restent ouverts
     et ne sont pas repris ici (compte de « trois composants », glose de « commune », T2
     écrit au présent de conception, redondance avec le § 6.3).
  2. « belief » est rendu « croyance ». Les masters écrivent « concept » au § 3.4 ; le § 6
     anglais n'emploie que « belief », et R12 impose un mot par concept. Le français suit
     l'anglais, et « croyance » est déjà le mot du master fr/03_Architecture.md § 3.4 et du
     fr/07_Adaptation.md.
  3. Les commentaires de source sont repris à l'identique, y compris leurs citations de
     l'anglais (« the transport networks » → « the networks ») : ils documentent la
     provenance du texte anglais et ne se retraduisent pas.
=== FIN ===
-->
