# 3. The agent under evaluation

<!-- DERNIÈRE ÉCRITURE ANGLAISE : 2026-09-25 11:17:13 — le .tex correspondant porte cette date en en-tête tant qu'il en est le rendu fidèle. Voir sections/README.md. -->

<!-- Brouillon anglais, article court AAMAS 2027, PLAN.md § 3 — budget 450 mots.
     Rédigé le 2026-09-22 par l'agent article-writer. Les §§ 4, 5 et 6 sont écrits ;
     cette section définit en amont ce qu'ils emploient sans le définir : la masse de
     probabilité (dette du § 4, règle 2), les quatre voies par lesquelles le passé
     atteint une décision, le bloc « ce qui a changé récemment », le rappel par
     similarité, la croyance et la consolidation du soir (dette du § 6.4).
     Aucun chiffre de cette section ne dépend du ticket 103 : aucun emplacement [c2].
     ⚠ Le master fr/03_Architecture.md porte une réserve de datation sur son § 3.4,
     signalée au compte-rendu. -->

An agent is one simulated person, in three parts. Its body lives in the simulation: a
position, a daily schedule, the household's vehicles and the trips it physically executes.
Its state, its memory and where its vehicles stand, lives in the controller. Its
decision-maker turns one trip description into a probability over the options offered. The comparison of Section 4 swaps
only the decision-maker, and we name an agent after it.

<!-- ⚠ Remarque de relecture n° 2, 2026-09-23 : « agent » désignait tour à tour l'entité GAMA
     qui se déplace, l'ensemble personne + mémoire (§§ 3.3, 3.4) et le décideur comparé
     (§ 5, « the tuned agent »). La relecture proposait deux couches ; le code en a trois.
     Corps : espèce GAMA (position, planning, véhicules, exécution physique, retours
     arrival / tc_timeout). État : controller Python — mémoire STM/LTM
     (docs/arch/memory-stm-ltm.md, ChromaDB par agent) et chaîne de véhicules
     (docs/arch/vehicle-chain.md). Décideur : LlmAgent.evaluate_and_choose_travel_plan ou
     tout décideur de experiences/decideurs.py ; le tirage (draw_index) est fait côté
     controller, et la décision est poussée à GAMA par WebSocket
     (docs/arch/agents-lifecycle.md, § Arbre d'exécution et § Points d'injection).
     « Decision-maker » reste défini au § 1.3 ; il est ici situé dans l'agent. La règle de
     nommage (« we name an agent after it ») couvre les emplois du § 5, « the tuned agent »,
     « two agents also differ », sans les réécrire. -->

## 3.1 The loop

Three components make up the simulation. The world runs on GAMA, a multi-agent simulation platform
(Taillandier et al., 2019). It holds the real geography of the study area, the networks,
the clock and the physical execution of every trip. OpenTripPlanner, an open-source multimodal
router (OpenTripPlanner contributors, 2025), produces the public transport itineraries on the
real timetables. A fastest-path search with
OSMnx (Boeing, 2025) on the OpenStreetMap graph produces the direct itineraries by
foot, bicycle and car. Each edge is weighted by its free-flow travel time, at a speed set per
mode and road class. Signal delays and, for the car, hourly congestion are added to the path
found. A trip is one move of a persona, from an origin to a destination, for one activity at
one hour. An itinerary is one physical way to make it, with its mode, its lines and its path.
The two engines turn each trip into several itineraries, six at most. The options are those
the vehicle chain allows (Section 3.4).

<!-- Remarque du tuteur, PDF annoté v1 KOI, p. 4 : « carries » surligné, répété. Le § 3.1 le
     portait trois fois en trois phrases, le § 3.2 deux fois de suite. Le 2026-09-25 : « make
     up », « holds », « runs » au § 3.1 ; « gives », « lists » au § 3.2. Restent « The draw thus
     carries » (§ 3.2) et « The prompt carries the past » (§ 3.3), isolés. -->

<!-- ⚠ Remarque de relecture n° 7, 2026-09-23 : « trip » et « itinerary » employés sans
     définition, et « the direct trips » pour ce qui est un itinéraire. Six au plus :
     experience.yaml, max_candidats: 6 (source du § 4.2). Filtre par la chaîne : verrou de
     sortie par mode véhiculé passé à OTP (experiences/decision.py:124-160, include_*).
     « Option » = itinéraire offert, un seul mot par concept pour la suite. -->

A controller runs the agent lifecycle, holds each agent's state and builds the
options available at the departure hour. A decision module hosts the decision-maker. The language model
is called at five points of the loop. It makes the decision, rates an event as it enters
memory, consolidates memory in the evening and runs a multi-day self-reflection. If required,
it also answers an opinion survey held outside any decision. Section 5 tests the decision alone, from a blank memory. Section 6 follows
one event from its rating to the decisions of the days after, and reads the opinions the agent
declares.

<!-- source: fr/03_Architecture.md § 3.1, premier paragraphe : simulation GAMA (géographie
     réelle de l'aire toulousaine, réseaux, horloge, exécution physique), contrôleur du cycle
     de vie, module de décision.
     ⚠ Deux corrections de l'auteur, 2026-09-23. La rétention de l'horloge (« It holds the
     clock, so that no agent leaves before deciding ») est retirée du corps : elle y était
     revenue par la relecture v1, item T1, contre le PLAN § 3.1 qui la faisait sortir. Le plan
     l'emporte, l'auteur ayant tranché.
     ⚠ « The language model intervenes only in that module » est FAUX et disparaît, avec la
     clivée du master dont elle venait (« c'est là, et seulement là, qu'intervient le modèle de
     langue »). docs/arch/llm-inference.md, ticket 092, recense trois sites d'appel par run, au
     seuil unique de LLMGatewayClient.execute : itinary_multi_agent (le choix d'itinéraire),
     stm_reflection (la consolidation mémoire du soir) et ltm_self_reflection (l'auto-réflexion
     multi-jours). Le ticket dit pourquoi le décompte compte : mesuré le 2026-09-16, un run
     servait ses décisions par google_gemini31_key1 et sa stm_reflection par mistral_key1, les
     souvenirs étant donc rédigés par un modèle non déclaré. La phrase du corps affirmait
     l'inverse de ce que l'architecture fait. La légende de la figure 1 portait la même erreur
     (« intervenes at one point of the loop ») et est refaite. La restriction de portée du
     papier tient toujours, mais par une autre voie : le banc tourne mémoire désactivée
     (§ 3.3, fr/08_Limitations.md § 8.3), donc seul l'appel de décision y est exercé. Cette
     précision n'est pas écrite ici, le § 3.3 la portant déjà.
     ⚠ Auteur, 2026-09-24 : « three points » et « This paper tests the decision » étaient
     faux tous deux, et la phrase est remplacée par le texte de l'auteur. Sa phrase des cinq
     appels (38 mots) est coupée en trois pour R1, coupe choisie par l'auteur le même jour. Le
     code expose cinq fonctions cognitives, services/llm-agents/experiences/memoire.py,
     CATEGORIES_COGNITIVES : itinary_multi_agent, evenement_jugement (gravité et valence à
     l'entrée, ticket 100, § 6.2), stm_reflection, ltm_self_reflection, enquete_affinite
     (opinions déclarées, § 6.3-6.4). Le tableau de docs/arch/llm-inference.md (ticket 092)
     n'en recense que trois, d'où le décompte de la version précédente. La restriction au
     banc mémoire désactivée ne valait que pour le § 5 ; le § 6 exerce le jugement, la
     mémoire et l'enquête, et le § 1.3 en fait la troisième contribution. Ce que la phrase
     ne revendique pas : aucun résultat ne dépend de l'auto-réflexion multi-jours, et le
     jugement de gravité est exercé sans être comparé à une référence. « If required » :
     l'enquête ne tourne que si EXPERIMENT_SURVEY_ENABLED=1, défaut désactivé
     (urban_mobility_agents/enquetes.py, is_enquete_due), aux jalons EXPERIMENT_SURVEY_DAYS. Légende de la figure 1 alignée.
     ⚠ Remarque de relecture n° 1, 2026-09-23 : « shortest-path » laissait lire une distance
     minimale. Vérifié dans le code : trip_helper/osmnx_direct.py, ox.routing.shortest_path(G,
     orig, dest, weight="travel_time") — Dijkstra sur le temps libre de chaque arête ; vitesse
     speed_kph tirée de config/osmnx.yaml par mode et par type de voie OSM (highway), et non
     du tag maxspeed ; pénalités de nœud (feux, stops, cédez-le-passage) et congestion TomTom
     horaire par zone d'arête (voiture seule) ajoutées à la durée du chemin trouvé, hors de la
     recherche : le chemin ne contourne pas la congestion. Aucune pénalité de tourne-à-gauche,
     contrairement à ce que suggérait la relecture. Source : docs/arch/routing.md, § Modes et
     coupures et § Congestion par zone d'arête.
     Les deux moteurs viennent du § 3.2 du master : OpenTripPlanner sur les horaires réels des
     réseaux, plus court chemin sur le graphe OpenStreetMap pour la marche, le vélo et la
     voiture. Les 453 communes sont le périmètre de l'EMC² 2023, § 3.1 du master et § 4.1 de
     cet article. Sources d'architecture : docs/arch/agents-lifecycle.md, docs/arch/routing.md
     § Vue d'ensemble.
     Nommage des plateformes en corps de texte : demandé par la relecture v1, item T1, qui
     lève la consigne antérieure de ne pas les écrire. Le paragraphe est repris de T1 mot pour
     mot, à deux exceptions imposées par R1 : « the transport networks » devient « the
     networks » (26 mots) et la phrase du contrôleur est coupée en deux (27 mots). -->

The loop closes on the simulation's returns. When a body is due to leave, the controller
requests the itineraries from the routing engines and writes the trip description. The
decision-maker spreads its preference over those itineraries, and the controller draws the
option the body will take. The simulation executes the trip and returns what happened, the
transfers, the waits, the arrival time. Those returns feed the memory that weighs on the
next decision.

<!-- source: fr/03_Architecture.md § 3.1, troisième paragraphe (boucle fermée).
     « The routing engines » renvoie aux deux moteurs nommés au paragraphe précédent (T1) ;
     le manque signalé à la version 1 est comblé.
     Sortent, par le PLAN § 3.1 : le quadruplet formel, l'ordonnancement par échéance
     croissante, le planning fixe et le week-end sans activité. La rétention de l'horloge, que
     le plan faisait sortir, revient en corps de texte par T1. -->

The loop comes from Vu et al. (2025). They coupled GAMA to a separate Python server of
generative agents, over HTTP for the clock and agent positions, and WebSocket for actions and
returns.
OpenTripPlanner routed their public transport, and a reflection at the end of each day wrote
short-term memory into a long-term store. Five agents rode the Toulouse transit network for
one month. The study scored how quickly the chosen itineraries stabilised and how late agents arrived, and
left validation against survey data to future work.

<!-- Audit des citations du 2026-09-23, Vu et al. : le canal HTTP porte le « State Sharing »,
     soit « the simulation timestamp and … the spatial location of each agent » (§ 3.5), d'où
     l'ajout des positions. La réflexion quotidienne est exacte : « the reflection from
     perception data to long-term memory happens every day », une seconde réflexion
     d'abstraction tournant en plus tous les 7 jours (§ 4.2.4).
     § 3.1 : OpenTripPlanner est cité par son entrée logicielle (version 2.8.1, celle que le
     projet exécute), au lieu de l'URL en ligne. OSMnx passe de Boeing (2017) à Boeing (2025),
     Geographical Analysis 57(4) : c'est l'article que la documentation d'OSMnx demande de citer,
     et le code appelle l'API 2.x (ox.routing.shortest_path). Clés : opentripplanner2025,
     boeing2025osmnx, ajoutées à sample.bib le même jour. -->

This paper changes five things in that loop. The original agents chose among transit
itineraries only. Walking, cycling and driving now enter through the OpenStreetMap search
above, bound by the vehicle chain of Section 3.4. The decision returns a probability mass over
the options instead of one itinerary (Section 3.2). The long-term memory gives each belief a
confidence that observations move, and lets a household member's day reach the others
(Section 3.3). Retrieval ranks the traces on five terms instead of three, adding severity and
the match with the current trip (Section 3.3). Lastly, the decision module accepts decision-makers that are not language
models, which the bench of Section 4 needs.

<!-- ⚠ Remarque de relecture n° 3, 2026-09-23 : la filiation n'était dite qu'au § 1.3
     (« follows the GAMA–OpenTripPlanner–LLM architecture of Vu et al. »), sans dire ce qui
     est repris ni ce qui est ajouté. Vu et al. n'apparaissent pas non plus au § 2.
     source Vu, Gaudou & Oberoi (2025), arXiv:2510.19497, PDF
     docs/paper/sources/etat_de_lart/Vu_2025_Generative_Agents_Toulouse.pdf :
     § 3.1 et § 3.5 (serveur Python distinct, HTTP synchrone pour le partage d'état et
     l'horodatage, WebSocket pour l'envoi d'actions et la boucle de retour) ; § 3.3
     (OpenTripPlanner, réseau TC de Toulouse) ; § 3.2, algorithme 1 (jambes « transfer » ou
     « transit » seulement) ; § 3.4 (STM, LTM en concepts et réflexions, rappel par score
     cosinus + BLEU-2 + récence) ; § 3.6 et algorithme 2 (réflexion en fin de journée) ;
     § 4.1 (5 agents, mars 2025, un mois simulé ; ChangeRate et ArrivalLateTime) ; § 6,
     « validating agent behavior against real-world survey data » en travail futur ; § 3.6,
     le LLM « selects the most suitable travel route », un seul itinéraire.
     Extensions, côté dépôt : trip_helper/osmnx_direct.py et docs/arch/vehicle-chain.md
     (modes directs et chaîne) ; mobility_llm/mode_choice.py (masse de probabilité, tirage) ;
     fr/03_Architecture.md § 3.4 (confiance des croyances, distinction de Tulving) ;
     ticket 100 (récit du soir au ménage, au présent de conception : aucun code au
     22 septembre, cf. commentaire du § 3.3) ; services/llm-agents/experiences/decideurs.py
     et decideur_modele.py (décideurs sans modèle de langue branchés sur la même interface).
     Non revendiqué comme nouveau : l'érosion des souvenirs dans le temps, que le score de
     récence de Vu et al. portait déjà (λ^(T−t)).
     ⚠ Double aveugle : la v0.12 de l'introduction du master avait reformulé la filiation
     pour qu'elle ne se lise pas comme une équipe poursuivant son propre travail. Le
     paragraphe parle de Vu et al. à la troisième personne, comme d'un travail publié qu'on
     étend, ce que les consignes AAMAS admettent ; à confirmer par l'auteur. -->

*Figure 1 — The three components of the loop. Section 5 tests the decision module, Section 6
the memory that feeds it.*

<!-- source: PLAN § 9, figure 1, pleine largeur, images/architecture_GAMA_Agents.jpg ;
     affirmation de légende reprise du plan. -->

## 3.2 What the agent receives, and what it returns

The agent receives one trip description and returns one probability per option. The
description gives a profile of the person and household, the destination, the
departure time and the weather ahead. It also lists the trips left before returning home,
the relevant memories, and the numbered list of options.

<!-- source: fr/03_Architecture.md § 3.3, première phrase : prénom, âge, occupation,
     composition du ménage, niveau de revenu, destination et zone, heure de départ, météo du
     moment et des tranches restantes, trajets restants avant le retour, souvenirs jugés
     pertinents, liste numérotée des itinéraires avec mode et étapes. L'espace d'action formel
     A(o_t, C_i,t) ⊆ O(o_t) sort, par le PLAN § 3.1.
     ⚠ Correction de l'auteur, 2026-09-23 : la phrase d'attaque était incompréhensible. Deux
     mots la portaient. « Observation » était le terme du master (le o_t du formalisme, dont
     la formule est justement sortie du corps), donc du jargon sans glose, et il entrait en
     collision avec l'autre emploi du mot trente lignes plus bas, « a confidence that
     observations move », où une observation est une preuve à l'appui d'une croyance
     (R12). « One number per option » ne disait pas quel nombre, alors que le paragraphe
     suivant établit que c'est une masse de probabilité sommant à un. Le terme retenu est
     « trip description », déjà posé au § 1.3 (« anything that turns a trip description into a
     probability over the options offered ») : aucun mot nouveau n'entre dans le papier. Le
     couple reçu/rendu de la phrase est conservé, le titre du § 3.2 le promettant. -->

The model spreads a probability mass over that list, one entry per option. Probability mass
is the share of preference placed on an option. The entries of one decision sum to one. The
decision played is a random draw from those probabilities, and not the option ranked first.

<!-- Remarque du tuteur, PDF annoté v1 KOI, p. 5 : « vector » entouré. Le vecteur p_t est sorti
     avec le formalisme, mais « that vector » et « returns a vector » restaient sans antécédent.
     Remplacés le 2026-09-25 par « those probabilities » et « one probability per option ». -->

That draw is a modelling hypothesis, and discrete choice models already make it. A logit also
returns one probability per option. Drawing from it amounts to maximising a utility whose
unobserved part follows an independent extreme-value law (McFadden, 1974). The draw thus carries what the trip description
does not say about the person. Playing the first-ranked option would send every persona of
one profile into the same mode. The spread the survey records within that profile would
vanish. The options are listed in a random order, so that rank does not become preference. A
decision-maker that returns one probability per option can then be scored against a distribution, as Section 4
does.

<!-- ⚠ Remarque de relecture n° 4, 2026-09-23 : le tirage apparaissait comme un détail
     d'implémentation, justifié seulement au § 4, règle 2, et sans lien avec les modèles de
     choix discret. Le relecteur lisait un PDF périmé (« never an arg max », § 3.3) ; le
     master portait déjà le vecteur au § 3.2 et la définition au § 1.3, mais pas la raison.
     Équivalence tirage logit / maximisation d'une utilité à terme aléatoire de Gumbel :
     McFadden (1974), déjà cité au § 2.1 (clé mcfadden1974conditional au .bib, à vérifier).
     Argument d'hétérogénéité : repris de la règle 2 du § 4 (fr/04_Evaluation.md § 4.3,
     « retenir le mode le plus probable ferait partir dans le même mode tous les personas d'un
     même profil »), déplacé ici, où se joue la décision ; la règle 2 renvoie désormais ici.
     Tirage : mobility_llm/mode_choice.py, draw_index, graine dérivée du contexte.
     Audit des citations du 2026-09-23 : McFadden (1974), lemmes 1 et 2 p. 111-112,
     n'établit l'équivalence entre probabilités logit et maximisation d'utilité que pour un
     terme inobservé i.i.d. de loi de Weibull (valeur extrême de type I) ; « random » seul
     l'étendait à tout terme aléatoire. -->

<!-- source: fr/03_Architecture.md § 3.3, deuxième paragraphe : vecteur p_t sur le simplexe
     des options viables, tirage catégoriel a_t ~ Cat(p_t) de graine dérivée du contexte,
     ordre des options tiré au hasard « pour que leur rang ne devienne pas une préférence » ;
     mobility_llm/src/mobility_llm/mode_choice.py (draw_index, argmax_index) ;
     categories/itinary_multi_agent/output_schema.json. La dernière phrase est la seule
     justification de la comparaison distributionnelle ici ; la raison du tirage plutôt que de
     l'argmax vit à la règle 2 du § 4 et n'est pas redite. -->

## 3.3 Two memory stores

<!-- ⚠ Paragraphe d'ouverture SUPPRIMÉ le 2026-09-24 sur décision de l'auteur. Il disait
     « Section 5 scores one day, and a one-day run has almost nothing to recall […] Section 6
     turns memory on ». Trois défauts : « one day » laissait croire à une seule journée, alors
     que chaque persona joue un jour de semaine tiré sur septembre 2022 – février 2023 (§ 4.1) ;
     la justification sonnait comme une excuse ; deux renvois vers l'avant (R9). Le constat
     passe au § 4.1, sous la forme « mémoire vierge » retenue par l'auteur : le score est
     identique à celui de la mémoire coupée qui a tourné (memoire: false →
     long_term_memory_enabled = False, experiences/cli.py ; ni rappel ni bloc noyau, ni
     consolidation). Le mot « vierge » vaut aussi au § 3.1. Le § 7.1 garde « memory
     disabled » : il chiffre le coût, et une mémoire allumée coûte 2,5 M de tokens de plus. -->

<!-- ⚠ Remarque de relecture n° 11, 2026-09-23 : la mémoire coupée n'était dite qu'en fin de
     section, après toute la machinerie. Justification proposée par le relecteur (« équité
     stricte avec les modèles tabulaires ») REJETÉE : elle contredit le § 4.2 (« We equalise
     the 21 variables, not the information each side holds »). Raison retenue, vérifiée :
     horizon_jours: 1 et memoire: false dans les experience.yaml du banc ; consolidation à
     dix entrées de mémoire courte ou à 22 h (settings.agent.stm_reflection_min_entries = 10,
     stm_reflection_daily_floor_hour = 22), pour 3,30 déplacements par persona (§ 4.1) : la
     mémoire longue est vide à presque toutes les décisions du jour. La phrase de fin de
     section (« …switched off, so no result of Section 5 depends on the 2.8-day constant »)
     est remontée ici. -->

Two stores hold what an agent has been through. A short-term buffer receives the decisions
and the physical experience the simulation returns. A consolidation pass writes from that
buffer into the long-term store each evening. An episodic trace says what happened and
when, with a weight that decays on a 2.8-day time constant. A belief says what the agent holds
true, does not decay, and lives on a confidence that observations move. Trace and belief map
onto the episodic and semantic memories that Sumers et al. (2024) distinguish in language agents.
The first keeps the experience of earlier decisions, the second what the agent knows of the world
and of itself. Memory research has long held episodic memory more exposed to forgetting than
semantic memory (Renoult & Rugg, 2020). We therefore let only traces decay.
The exponential form also appears in MemoryBank (Zhong et al., 2024), but the 2.8-day constant
is a design choice, not a fitted value. It leaves the trace of an uneventful trip less than a tenth
of its weight after a week. The evening pass adapts the reflection of Park et al. (2023), which
fires when recent events pass an importance threshold. In the evening each
household member tells the others their day, and that account enters the hearers'
reflection.

<!-- Remarques du tuteur sur la version longue (PDF annoté AAMAS_2027___LLM_v1_KOI, p. 6),
     reprises le 2026-09-25 sur accord de l'auteur.
     « why episodic traces and concepts behave differently? » : deux phrases ajoutées après
     Sumers et al. La première rend leurs deux définitions, CoALA § 4.1, vérifiées dans
     sources/etat_de_lart/Sumers_2024_CoALA.pdf : « Episodic memory stores experience from
     earlier decision cycles » ; « Semantic memory stores an agent's knowledge about the world
     and itself ». CoALA ne dit rien de l'oubli : la raison de l'asymétrie vient donc d'une
     autre source. Renoult & Rugg (2020), Neuropsychologia 139, 107366,
     doi:10.1016/j.neuropsychologia.2020.107366 (Crossref vérifié ; manuscrit accepté déposé le
     2026-09-25 sous sources/etat_de_lart/Renoult_2020_Tulving_Episodic_Semantic.pdf ; clé
     renoult2020historical, sources/sample.bib), p. 10 du manuscrit : « in the 1972 chapter,
     Tulving assumed that semantic memory was less vulnerable to loss of information,
     interference and forgetting than episodic memory », les travaux ultérieurs de Tulving
     (1983, p. 45) tenant l'épisodique pour plus fragile, et la littérature actuelle
     rejoignant l'idée d'un oubli rapide de l'épisodique. D'où « has long held ».
     Option B de l'auteur, 2026-09-25 : on cite la seule source lue, Renoult & Rugg, et non
     Tulving (1972), dont le chapitre n'est toujours pas au dépôt (décision du 2026-09-24).
     « We therefore let only traces decay » garde la règle pour un choix de conception
     appuyé sur la littérature, non pour un résultat de Renoult & Rugg.
     ⚠ Report LaTeX : ajouter renoult2020historical à overleaf/sample.bib.
     « registers » (surligné) devient « stores », au titre comme dans le corps : le mot est
     celui de la figure 1 (« Short-term memory », « Long-term memory ») et de CoALA. -->

<!-- Audit des citations du 2026-09-23, Park et al. (2023), § 4.2 : la réflexion se déclenche
     « when the sum of the importance scores for the latest events … exceeds a threshold (150) »,
     soit deux à trois fois par jour ; elle n'a lieu ni le soir ni sur le récit des autres.
     « follows » devient « adapts », et la phrase dit le déclencheur d'origine.
     La phrase « The split follows Tulving's (1972) distinction between episodic and semantic
     memory » est retirée le 2026-09-24 sur décision de l'auteur : le chapitre de Tulving n'est
     pas au dépôt, et l'attribution n'a pas pu être vérifiée. -->

<!-- Citations ajoutées le 2026-09-24 sur accord de l'auteur, vérifiées contre les PDF de
     sources/etat_de_lart/ (clés sumers2024coala et zhong2024memorybank, sources/sample.bib).
     Sumers et al. (2024), CoALA, TMLR 02/2024, § 4.1 : « Episodic memory stores experience
     from earlier decision cycles » ; la mémoire sémantique garde ce que l'agent sait du monde
     et de lui-même, et l'agent peut y écrire ce que le modèle en déduit. « map onto » et non
     « follows » : la séparation vient de Park et al. adaptés par Vu et al., pas de CoALA.
     CoALA occupe la place laissée par Tulving, avec une source au dépôt.
     Zhong et al. (2024), MemoryBank, AAAI-24, § 2.3 : R = e^(−t/S), t remis à zéro et S
     augmenté de 1 à chaque rappel. Forme commune avec la nôtre (Δt depuis le dernier rappel,
     § score ci-dessous) ; différence : notre τ s'allonge avec la gravité, pas avec le nombre
     de rappels. « also appears » et non « follows » : la valeur de 2,8 jours ne vient pas de
     MemoryBank (voir la remarque n° 5 ci-dessous). Paragraphe porté de 130 à 170 mots. -->

<!-- ⚠ Remarque de relecture n° 5, 2026-09-23 : l'asymétrie trace / croyance et la constante
     de 2,8 jours étaient posées sans justification.
     Asymétrie : Tulving (1972) oppose les deux systèmes sur plusieurs traits, dont la
     vulnérabilité de l'épisodique à la transformation et à la perte d'information, plus forte
     que celle du sémantique. ⚠ Paraphrase de mémoire, PDF absent de etat_de_lart/ : à vérifier
     contre le chapitre (Organization of Memory, p. 381–403) avant le report LaTeX. Tulving ne
     dit PAS que le sémantique ne s'oublie jamais : « does not decay » reste un choix de
     conception, d'où la formulation « revised … not worn down by the calendar ».
     2,8 jours : AUCUN fondement empirique ni expérimental. Valeur = 1 / ln(1/0,7) = 2,8034,
     reconversion exacte de l'ancienne base 0,7 par jour (ticket 048, settings.py:586-593),
     héritée de l'implémentation de Vu et al. ; leur article (arXiv:2510.19497, éq. 3) donne la
     formule λ^(T−t) sans la valeur (docs/arch/memory-stm-ltm.md l. 1360-1365 et l. 1837).
     Règle de conception écrite a posteriori le 2026-09-14 : exp(-7/2,8) = 0,08 < 10 % à une
     semaine. Point de sensibilité prévu à 8,3 j (Park et al., 0,995/h) : aucun résultat
     publié, donc non cité. L'origine « implémentation de Vu et al. » n'est pas écrite : elle
     n'est vérifiable que par qui a le code, ce qui lèverait l'anonymat.
     Aucun chiffre du § 5 n'en dépend : le banc tourne mémoire coupée
     (fr/08_Limitations.md § 8.3), d'où l'ajout au dernier paragraphe de la section. -->

<!-- ⚠ Remarque de relecture n° 3, point E3 et E4, 2026-09-23 : GAMA, OpenTripPlanner et OSMnx
     étaient employés sans référence, la séparation trace / croyance sans Tulving, la
     consolidation du soir sans Park et al.
     Clés présentes dans docs/paper/sources/sample.bib : taillandier2019gama,
     park2023generative (PDF etat_de_lart/Park_2023_Generative_Agents.pdf).
     Réglé le 2026-09-24 par l'audit des citations : OSMnx est cité par boeing2025osmnx
     (Geographical Analysis 57(4), l'article que la documentation d'OSMnx demande de citer,
     notice Crossref vérifiée) et non plus par Boeing (2017) ; OpenTripPlanner par l'entrée
     logicielle opentripplanner2025 (version 2.8.1) ; Tulving est retiré du corps, faute de
     chapitre au dépôt pour vérifier l'attribution.
     « Distinction de Tulving » : fr/03_Architecture.md § 3.4. OSMnx :
     trip_helper/osmnx_direct.py (ox.routing.shortest_path). Consolidation du soir comme
     réflexion à la Park et al. : c'est aussi la filiation que revendiquent Vu et al. (§ 2.1
     de leur article). -->

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

The prompt carries the past in four blocks. They hold the agent's habits, its beliefs, its
recent events, and three episodic traces. A score ranks the traces, with weights set by design
and not fitted.

$$s = 0.3\,e^{-d(q, x)} + 0.2\,e^{-\Delta t/\tau} + 0.2\,g + 0.2\,a + 0.1\,m$$

Here $d(q, x) = 1 - \cos(q, x)$ is the cosine distance between the all-MiniLM-L6-v2 sentence
embeddings of the trip description and of the trace. The trace was last retrieved $\Delta t$ days ago, and $\tau$ is its time constant. The term $g$
is its severity, and $a \in [0, 1]$ its match with the current mode, place, time slot and
purpose. The term $m$ is one when the weather matches, zero otherwise. Not every candidate
comes from similarity. Traces that bear an offered mode, and the most severe ones, enter the
ranking whatever their text.

<!-- ⚠ Remarque de relecture n° 6, 2026-09-23 : « three memories retrieved via similarity »
     était une boîte noire. Score servi : llm/longterm.py:884-961 (rank_nodes), cinq
     composantes en valeur absolue, sans normalisation min-max (ticket 048), somme des poids
     1,00 : sim 0,30, time 0,20, importance 0,20, affinite 0,20, keyword 0,10
     (settings.py:569-582, « valeurs de départ à calibrer, pas un résultat »).
     ⚠ docs/arch/memory-stm-ltm.md § Étape 2 est PÉRIMÉ (0,4 / 0,3 / 0,3, BLEU-2) : ne pas le
     citer. keyword_weight ne pèse plus un recouvrement lexical mais la seule météo
     (llm/axes.py:253, arbitrage du 2026-09-14). Plongement : all-MiniLM-L6-v2
     (llm/longterm.py:21, MODELE_PLONGEMENT_DEFAUT ; settings.agent.embedding_model vaut null
     dans les runs). ⚠ settings.py:931, cité ici jusqu'au 2026-09-24, est le modèle du cache
     LLM (CacheConfig.embed_model_name), pas celui de la mémoire longue : même nom, autre
     paramètre. ⚠ Le terme servi n'est pas cos mais exp(−d), d = 1 − cos : Chroma travaille
     en espace cosinus (llm/longterm.py:72) et l'adaptateur llama-index-vector-stores-chroma
     0.4.2 convertit la distance par math.exp(-distance) (base.py:432, vérifié dans le
     conteneur controller le 2026-09-24). Plage [e⁻², 1] ; cos 0 donne 0,37 et non 0 ; la
     borne [0, 1] de rank_nodes (llm/longterm.py:899) ne mord jamais. Les candidats des
     viviers B et C reçoivent 0 exactement. La formule écrivait 0,3 cos jusqu'au 2026-09-24.
     Δt depuis le dernier rappel, τ = min(2,8 × (1 + 6 g), 30)
     (llm/gravite.py). a = 0,50 mode + 0,20 lieu + 0,15 créneau + 0,15 motif, bonus jamais
     veto (llm/axes.py:198-250). Viviers : A sémantique, B par mode offert (8 par mode),
     C chocs (5, sans condition) — settings.py:707-710. Trois traces servies :
     memoire__episodiques_avec_noyau = 3 (settings.py:717), parmi un top-K de 10
     (long_term_max_entries_query). Le PLAN § 3.3 sortait ce score faute de place ; il
     rentre à la demande du relecteur. La phrase d'origine (26 mots, faute R1) disparaît.
     Point E de la même remarque : « last recalled » devient « last retrieved », « recall »
     étant aux §§ 4 et 5 la métrique de rappel par mode ; le paragraphe « changes five
     things » du § 3.1 compte désormais le score (Vu et al., éq. 4 : cosinus + BLEU-2 +
     récence ; ici le BLEU-2 cède la place à la météo, gravité et affinité d'axes s'ajoutent). -->

The 'recent events' block contains occurrences that remain active within a time window determined by their initial severity.

<!-- ⚠ Remarque de relecture n° 5, point E, 2026-09-23 : retrait de « The specific influence
     of each block on the final decision can be quantified. » Promesse non tenue par l'article :
     la campagne qui lit ce que portent les autres voies est encore marquée « à confirmer » au § 6.4. -->

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

## 3.4 The vehicle chain

Deciding each trip on its own produces physically impossible days. An agent who cycled to
work has no car at the office in the evening. The controller therefore tracks where each
personal vehicle stands. A vehicle is offered only from where it is parked, after which it
follows its user. On a return trip, a vehicle left at the start restricts that trip to its
mode.

<!-- source: fr/03_Architecture.md § 3.5 et docs/arch/vehicle-chain.md, § Les trois règles :
     un mode véhiculé n'est proposé que si le véhicule est garé au point de départ ; le
     véhicule du mode retenu suit son utilisateur à destination, les autres restent où ils
     sont ; sur un trajet de retour, si un véhicule attend au départ, les itinéraires candidats
     sont restreints à ce mode. Troisième règle : elle filtre les options et n'ajoute pas de
     décision. Sort : l'éligibilité (permis, majorité, passager d'un ménage motorisé), § 3.2
     du master. -->

These rules bind every decision-maker we compare, machine learning models on structured data included, since
without them we would compare decisions taken in different worlds.

<!-- source: fr/03_Architecture.md § 3.5, dernier paragraphe : « Le plancher et le plafond du
     chapitre 4 sont soumis aux mêmes contraintes » ; PLAN § 3.4, « elle s'applique à tous les
     décideurs comparés, tabulaires compris ». Renormalisation sur l'offre au § 4, règle 3 :
     la chaîne est amont, la renormalisation aval ; les deux ne se redisent pas. -->

<!--
=== SECTION REPORT ===
Section        : 03 — The agent under evaluation
File           : docs/paper/article-court/sections/03_agent.en.md
Words / budget : 583 / 450 (+29.6 %) — hors marge ±15 %, par la relecture v1 §§ 5 et 10
                 (T1 +110, T2 +20), dont l'arithmétique paie l'ajout par des coupes aux
                 §§ 5, 6 et 7 et non ici. Le budget § 3 du PLAN est à porter de 450 à 580.
Skeleton       : Each agent turns one trip description into a preference over the options offered.
                 Three components make up the simulation.
                 The loop closes on the simulation's returns.
                 The agent receives one trip description and returns one probability per option.
                 The model spreads a probability mass over that list, one entry per option.
                 Two stores hold what an agent has been through.
                 Four blocks of the prompt carry the past into a decision, and a measurement can tell which one acted.
                 Deciding each trip on its own produces physically impossible days.
                 These rules bind every decision-maker we compare, tabular models included.
Checker        : aucune consigne mécanique en faute après la seconde passe G3 du 2026-09-22
                 (R1, R2, R4, R5, R9, R11, R14 propres ; verifier_forme.py sort 0).
                 G1 : grep des séparateurs de milliers à espace fine = 0.
                 G3 : six coordinations à queue courte relevées, quatre rompues — la phrase
                 du module de décision (deux phrases ; sa seconde moitié est refaite le
                 2026-09-23, voir le commentaire du § 3.1), la légende de la figure 1
                 (apposition, refaite le 2026-09-23), « …whose
                 window is still open, a window set by severity at entry » (apposition) et
                 « …tabular models included, since without them… » (subordonnée). Restent la
                 phrase du saut par le ménage (T2) et « Four blocks of the prompt carry the
                 past into a decision, and a measurement can tell which one acted », dont les
                 deux membres portent chacun un énoncé repris au § 6.4.
Terms defined here     : probability mass, episodic trace, belief, consolidation pass,
                 the four prompt blocks, vehicle chain.
Terms used, undefined upstream : none. « decision-maker » est défini au § 1.3 ;
                 « commune » n'est pas glosé (plus petite unité administrative française),
                 signalé ci-dessous.
Figures cited  : 453 communes — fr/03_Architecture.md § 3.1 et périmètre EMC² 2023, aucune
                 réserve ; 2,8 jours (constante de temps épisodique) — fr/03_Architecture.md
                 § 3.4, réserve de datation du master (§ 3.4 écrit en avance sur le code,
                 v0.5) portée au commentaire de source, la durée de service étant mesurée
                 au § 6 ; Figure 1 — PLAN § 9, images/architecture_GAMA_Agents.jpg.
Placeholders   : none. Aucun chiffre de la section ne dépend du ticket 103.
Left out       : le quadruplet formel, l'ordonnancement par échéance croissante, le planning
                 fixe et le week-end sans activité (PLAN § 3.1) ; l'espace d'action formel
                 (PLAN § 3.2) ; la figure des deux horloges, le score de rappel à cinq termes,
                 le réajustement d'horaire à 75 % (PLAN § 3.3) ; l'éligibilité au permis
                 (PLAN § 3.4). La rétention de l'horloge, que le PLAN faisait sortir, revient
                 en corps de texte sur demande de T1.
Flags for the author :
  1. « Three components carry the simulation » puis quatre briques nommées (GAMA, les deux
     moteurs, le contrôleur, le module de décision). Le compte est celui du texte T1, repris
     mot pour mot ; un relecteur peut compter quatre. Correction possible : « Four components ».
  2. Deux phrases de T1 dépassaient 25 mots (R1) : « the transport networks » est écrit
     « the networks » (26 → 25) et la phrase du contrôleur est coupée en deux (27 → 15 + 12).
     Aucun autre mot de T1 n'est touché.
  3. « Commune » n'est pas glosé, faute de place et parce que le chiffre sert de périmètre
     plus que de notion. À trancher par l'auteur.
  4. La phrase du § 3.3 « The measurements of an ordinary day run with this memory switched
     off » rend redondante la clause équivalente du § 6.3 (relecture v1, § 9 bis : « Both runs
     keep memory enabled »). Rien à faire ici.
     ⚠ Réécriture du paragraphe par l'auteur le 2026-09-23 : cette phrase avait disparu, et
     avec elle le seul endroit du papier disant que le banc tourne mémoire désactivée. Le
     § 6.3 en dépend explicitement (son compte-rendu, point 4), sa propre clause ayant été
     coupée à la relecture au motif que le § 3.3 la portait. Elle est remise mot pour mot, à
     la demande de l'auteur, sans toucher au reste du paragraphe réécrit. Restent ouverts et
     NON corrigés, l'auteur n'en retenant qu'un : « four distinct modules » entre en collision
     avec « a decision module » du § 3.1 et de la figure 1 (R12), le § 6.1 renvoie encore au
     « block of what has changed recently » que ce paragraphe nomme désormais « recent
     events », la phrase d'attaque fait 26 mots (R1), et « a measurement can tell which one
     acted » est devenu « can be quantified », plus faible que ce que le § 6.1 établit.
  5. T2 est écrit au présent de conception : aucun code au 22 septembre pour le saut par le
     ménage. Le § 6.2 doit garder, après N1, la mention que le cas tracé ne l'exerce pas.
=== FIN ===
-->
