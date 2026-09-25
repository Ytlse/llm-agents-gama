# 2. Related work

<!-- DERNIÈRE ÉCRITURE ANGLAISE : 2026-09-25 21:07:15 — le .tex correspondant porte cette date en en-tête tant qu'il en est le rendu fidèle. Voir sections/README.md. -->

<!-- Relecture des gallicismes du 2026-09-25, accord de l'auteur (« Corrige ») : tics récurrents (« against » comparatif, « one » pour « un même », « carry », « bound », « under » devant un seuil, « rejoin », « from one X to another », « execute », « brings »), faux-amis (agenda, control, hypothesis, legibility, designate, demanding, chain, globally, bends, recedes), calques de construction et typographie à la française (« 0.9 point », « [a ; b] », « 30.3 % », « 1.06 dollars »). Aucun chiffre ne change ; les prompts et le message de l'annexe D ne sont pas touchés. -->

<!-- Brouillon anglais, article court AAMAS 2027, PLAN.md § 2 — budget 450 mots
     (2.1 130, 2.2 180, 2.3 140). Rédigé le 2026-09-22 par l'agent article-writer.
     Les §§ 3, 4, 5, 6 et 7 sont écrits ; cette section les précède en ordre de lecture et
     ne cite aucun de leurs résultats. Aucun chiffre du ticket 103 n'y entre : aucun
     emplacement [c2].
     Citations écrites en auteur-année, comme les masters ; la clé BibTeX de chacune est
     portée dans le commentaire source qui suit son paragraphe, pour que la passe LaTeX
     résolve (CITATIONS.md, entrées A1 à A17 et A33).
     Reprise du 2026-09-22 sur la RELECTURE_V1 : R1 (habitude et inertie, § 2.1), R2 (CitySim
     et MATSim rétablis, § 2.2 ; MATSim ressorti le 2026-09-25, voir l'audit du § 2.2),
     R3 (débat sur le raisonnement rédigé, § 2.3), R4 (GAMA nommé chez Alves et al.), § 9 bis sixième ligne (clause de défense supprimée au § 2.3), G3
     (une phrase coordonnée sur trois rompue) et G2 (bloc de compte-rendu en fin de fichier).
     ⚠ Les quatre clés ajoutées ce jour dans sample.bib — garling2003habitual,
     verplanken1997habit, wei2022chain, sprague2024cot — portent une note « entry written from
     memory », à vérifier avant soumission ; signalé au compte-rendu. -->

Three bodies of work meet in this paper, and none of them measures whether verbalised
deliberation helps agents reproduce the mode shares of a real territory.

## 2.1 Discrete choice and perception filters

Transport research has predicted mode choice for more than fifty years with discrete choice
models, which are statistically strong and behaviourally rigid. Such a model gives each mode a
probability computed from travel time, cost and the traveller's attributes (McFadden, 1974;
Ben-Akiva & Lerman, 1985). Analysts fit it on travel surveys. Once each mode has its own
intercept, the fitted model reproduces the survey's mode shares on the sample it was
estimated on (Train, 2009). Its behaviour, however, is frozen at estimation. The traveller
takes the mode of highest utility, and the weights given to time and cost, or their spread
across travellers, never change afterwards.

<!-- Relecture éditoriale du 2026-09-25, accord de l'auteur (« Corrige », point B8) : « one
     constant per mode » et « taste parameters, or their distribution » supposaient une culture
     d'économètre des transports que le lectorat AAMAS n'a pas. Glosés : constante spécifique
     = « its own intercept » ; paramètres de goût = « the weights given to time and cost » ;
     leur distribution (logit mixte) = « their spread across travellers ». Même source, même
     portée (Train, 2009, § 3.7.1). -->

<!-- Audit des citations du 2026-09-23. « for fifty years » devient « for more than fifty
     years » : McFadden (1974) cite déjà Warner (1962) sur le choix modal urbain. La phrase de
     Train est bornée à ce que dit la source, 2e éd., § 3.7.1, p. 62 : un logit estimé par
     maximum de vraisemblance avec un jeu complet de constantes spécifiques reproduit les parts
     observées sur l'échantillon d'estimation. « inherits » affirmait la propriété sans ses
     conditions. -->

<!-- ⚠ Le PDF déposé sous Train_2009_Discrete_Choice_Simulation.pdf est un brouillon de la
     première édition (« Version dated March 8, 2002 ») ; la propriété y est p. 72. -->


<!-- source: en/02_Related_work.md § 2.1, premier paragraphe (v0.19 du 2026-09-21) :
     utilité aléatoire (McFadden, 1974 ; Ben-Akiva & Lerman, 1985), logit multinomial et
     mixte exprimant la probabilité de chaque mode en fonction du temps, du coût et des
     attributs socio-économiques, estimés sur enquête (Train, 2009) ; force statistique,
     « calibrated on the population they describe », et faiblesse comportementale,
     « taste heterogeneity is represented by static distributions, and the decision rule is a
     maximisation ». Clés BibTeX : mcfadden1974conditional (A1), benakiva1985discrete (A2),
     train2009discrete (A3).
     ⚠ La glose « travel surveys, in which residents describe every trip of one day » est
     portée ici, première occurrence du terme dans l'article. Le § 4.1 déjà rédigé porte la
     même glose sur « household travel survey » ; l'une des deux doit tomber. Signalé au
     compte-rendu. La clivée du master, « Their strength is statistical. Their weakness is
     behavioural. », est réécrite selon la table de R5. Le mot « logit » n'est pas écrit ici,
     faute de place pour sa glose. -->

Behavioural research documents departures that no survey records, habit among them.
Travellers with a strong mode habit acquire less information about the alternatives and use simpler decision strategies (Verplanken, Aarts & van Knippenberg, 1997). Experience also
filters perception. Adam & Gaudou (2025) surveyed 650 respondents and found that car users
rate the car as more affordable than non-users do. A model fitted on surveys cannot represent such perception filters, and generative agents have been proposed to fill that gap.

<!-- Audit des citations du 2026-09-23.
     Verplanken et al. (1997), résumé : les participants à forte habitude « acquired less
     information and gave evidence of less elaborate choice strategies ». La phrase écrivait
     « Habit makes a repeated mode choice automatic. The traveller then acquires… » : l'article
     ne teste pas l'automatisme, et « then » posait une séquence causale que le dispositif,
     corrélationnel, n'établit pas. Gärling & Axhausen (2003), éditorial du numéro spécial
     « Habitual travel choice », est retiré le 2026-09-24 sur décision de l'auteur : son texte
     n'est pas au dépôt et aucune de ses phrases n'a pu être vérifiée.
     Adam & Gaudou (2025) : 650 réponses, p. 5. La sous-estimation du prix de la voiture par les
     automobilistes « convaincus » vient de leur revue de littérature (Rocci, p. 2), pas de leur
     enquête. Leur propre résultat, tableau 5 p. 6 : les usagers de la voiture notent son
     accessibilité financière 3,84 sur 10, contre 2,38 pour les non-usagers. -->


<!-- source: en/02_Related_work.md § 2.1, second paragraphe : enquête en ligne de
     650 répondants, sous-estimation du prix de la voiture chez les automobilistes habitués,
     perception des autres modes à travers l'habitude, filtres de perception modulant une
     décision multicritère dans leur modèle à base d'agents ; « household travel surveys do not
     record them […] and LLM agents are often proposed as the way to fill this gap ».
     Clé BibTeX : adam2025survey (A4).
     Deuxième phrase ajoutée le 2026-09-22 sur la RELECTURE_V1, item R1 : la seule référence
     comportementale du paragraphe était une auto-citation. Habitude, automatisme et recherche
     d'information réduite dans le choix modal, Verplanken, Aarts & van Knippenberg (1997) ;
     numéro spécial sur le choix de déplacement habituel, Gärling & Axhausen (2003). Clés
     BibTeX : verplanken1997habit, garling2003habitual.
     ⚠ Les deux entrées ont été versées dans sample.bib de mémoire et portent la note
     « verify volume, pages and DOI before submission » ; signalé au compte-rendu.
     Dernière phrase reformulée en subordonnée (G3, tic du « , and » à queue courte).
     Sortent, faute de place : le modèle à base d'agents que les auteurs construisent, et la
     réserve du master sur le caractère conditionnel de ces effets. -->

## 2.2 Generative agents in mobility simulation

Park et al. (2023) place a language model inside the agent, with a memory stream of its
experiences and a reflection step. Liu, Yang & Yin (2025) extend the design to travel demand modelling, and propose a hybrid with established components as a near-term step. CitySim (Bougie & Watanabe, 2025) scales such
agents to a city. It validates them against time-use, travel, place-popularity and
crowd-density data, but no experiment there compares a simulated modal split with an observed
one. Its successor CityReal (Bougie, Ye & Watanabe, 2026) does, after tuning the textual
instructions toward target population statistics while keeping the model frozen. Its
reference data are proprietary, however, and its agents are not compared with any reference model on mode choice.

<!-- Audit des citations du 2026-09-23.
     Park et al. : le mot « episodic » n'apparaît pas dans l'article (0 occurrence), qui parle
     de « memory stream » ; ce flux porte aussi réflexions et plans.
     Liu et al. : version publiée, Artificial Intelligence for Transportation 1 (2025), d'où
     l'année 2025. Leur cadre est entièrement fondé sur des agents LLM ; l'hybride n'est
     proposé que comme « near-term integration strategy » (résumé, § 6.2).
     CitySim : version publiée, EMNLP 2025 Industry Track. Validation sur l'emploi du temps
     (§ 4.1), les déplacements horaires (§ 4.3), la fréquentation des lieux (§ 4.4) et la
     densité de foule (§ 4.6) ; « validates them on time use » la sous-estimait.
     CityReal (ajout du 2026-09-24, clé bougie2026cityreal) : arXiv:2608.16897v1, 8 juillet 2026.
     « we learn textual adapters with Monte Carlo Tree Search to calibrate agent decisions
     toward target population statistics while keeping the LLM frozen » (résumé) ; JSD entre
     parts modales simulées et observées (tableaux 4 et 5). Données de déplacement : « a
     proprietary city-scale dataset » (§ 4.3). Son seul XGBoost prédit des classes de
     bien-être (tableau 1), pas le mode : d'où « on mode choice ».
     MATSim : les agents choisissent bien parmi leurs plans selon un score et replanifient ;
     « rather than from an agent's deliberation » laissait croire à des agents sans choix.
     Supprimé le 2026-09-25 à la demande de l'auteur, avec la phrase d'ouverture du § 2.2
     (« Language models entered mobility simulation as the deliberating part that earlier
     simulators did not have. ») qui l'introduisait. La phrase MATSim opposait un simulateur à
     l'équilibre à des décideurs : ce n'est pas l'axe du papier, déjà posé au § 2.1 par les
     modèles de choix discret. Elle ne répondait pas non plus à « pourquoi pas MATSim ? », qui
     porte sur la plateforme, et « earlier simulators » datait un outil toujours maintenu.
     L'ouverture redisait la fin du § 2.1 (« generative agents have been proposed to fill that
     gap »). Le § 2.2 s'ouvre sur Park et al. ; « the model » devient « a language model », faute
     d'antécédent. R2 de la RELECTURE_V1 est défait pour moitié : CitySim reste, MATSim sort,
     comme le prévoyait le PLAN § 2.2. La clé horni2016matsim n'est plus citée ; l'entrée reste
     dans sample.bib, que BibTeX n'imprime pas sans citation. −36 mots. -->


<!-- source: en/02_Related_work.md § 2.2, premier et deuxième paragraphes : Park et al. (2023)
     « place the language model inside the agent, with an episodic memory stream, retrieval,
     reflection and planning ; the systems below carry that architecture into mobility » ;
     Liu, Yang & Yin (2024), cadre conceptuel où des agents LLM tiennent lieu de voyageurs dans
     les modèles de demande à base d'activités, « hybrid modelling, LLM agents combined with
     established components, as the realistic near-term integration path ». Clés BibTeX :
     park2023generative (A5), liu2024toward (A7).
     Troisième et quatrième phrases rétablies le 2026-09-22 sur la RELECTURE_V1, item R2, dans
     les termes que la relecture donne mot pour mot : CitySim est le seul autre système LLM à
     l'échelle d'une ville, et c'est la lacune que ce papier comble. Sources : en/02_Related_work.md
     § 2.2 (CitySim, agents à l'échelle urbaine validés sur des motifs d'emploi du temps, sans
     confrontation d'une répartition modale simulée à une répartition observée ; MATSim,
     boucle co-évolutive atteignant un équilibre par notation des plans, sans délibération de
     l'agent). Clés BibTeX : bougie2025citysim, horni2016matsim, toutes deux déjà au dépôt.
     ⚠ Ces deux phrases débordent le PLAN § 2.2, qui les faisait sortir ; la relecture prime,
     et le dépassement de budget est chiffré au compte-rendu.
     Sortent, par le PLAN § 2.2 : Chopra et al. (2024) sur les archétypes. La preuve de concept
     de Liu et al. tombe faute de place. -->

GTA (Section 1.2) is the closest published system on the evaluation side, and two of its choices limit what it can show. Each of its agents returns one mode per trip
rather than a distribution, so no distributional metric applies. It also simulates a single
day, and its authors name multi-day memory as future work. We add a baseline beneath the
agents and four reference models above them. Our metric scores a whole distribution, not one
mode per trip. Our agents keep events in memory across days.

<!-- source: en/02_Related_work.md § 2.2, troisième paragraphe (v0.14 du 2026-09-10) :
     personas alignés sur l'enquête nationale allemande par truncate-replicate-sample, un modèle
     de langue écrit la description du persona et le plan de journée, puis choisit un mode par
     déplacement parmi des itinéraires candidats ; « Each agent returns a single mode rather
     than a distribution, so no distributional metric is available ; days are independent, and
     the authors name multi-day memory and adaptation as future work. »
     Clé BibTeX : lammer2026gta (A33).
     ⚠ Chiffres délibérément absents : l'erreur de 4,07 sur la répartition modale et la
     comparaison de Hambourg à 1,99 appartiennent au § 1.2, par consigne du PLAN § 2.2.
     L'absence de référence modélisée (ni modèle de choix discret, ni plancher naïf) est laissée
     au § 1.2 ; la phrase « We add… » la couvre en creux et nomme les trois ajouts que le PLAN
     demande. Sortent, faute de place : la description de GTA (le § 1.2 la porte), ses ablations
     de 5,42 à 8,23, et son équilibre usager dynamique recalé sur des comptages.
     Audit des citations du 2026-09-23 : « three of its choices » n'en nommait que deux ;
     « Its days are also independent » supposait plusieurs jours, alors que GTA en simule un
     seul, le multi-jours n'apparaissant qu'en travaux futurs (§ 6.4). -->

<!-- Audit des citations du 2026-09-23, Alves et al. : la comparaison à la baseline à règles
     existe (§ 5.1), mais les auteurs écartent explicitement d'en faire un jugement, p. 8,
     « Rather than a direct performance comparison with a rule-based model… ». « They judge
     adaptability against a rule-based baseline » disait l'inverse. -->

Alves et al. (2026) stand closest on the platform side, though their evaluation has no human
ground truth. They couple the GAMA platform to a language-model module with a persistent
memory, which decides, when a disruption occurs, whether an agent replans. They compare its
behaviour with a rule-based baseline, but never with observed behaviour.

<!-- source: en/02_Related_work.md § 2.2, quatrième paragraphe : couplage de GAMA à un module
     LLM externe décidant sur chaque événement de perturbation si l'agent replanifie son
     itinéraire, mémoire persistante, comparaison d'agents à règles et d'agents assistés par LLM
     sur des scénarios de blocage routier et plusieurs tailles de population ; « their
     evaluation, however, has no human ground truth : adaptability is judged against the
     rule-based baseline, not against observed behaviour, and no distributional metric is
     computed. » Clé BibTeX : alves2026evaluating (A9).
     Plateforme nommée le 2026-09-22 sur la RELECTURE_V1, item R4 : nommer une plateforme ne
     désanonymise pas. Le § 3.1 nomme GAMA au même moment, item T1 de la même relecture, donc
     les deux sections concordent. Première phrase passée en subordonnée concessive (G3).
     Sort, faute de place : la phrase du master qui déclare la position que ni GTA ni Alves
     et al. n'occupent, le § 1.3 la portant. -->

## 2.3 Distributional alignment of LLM populations

A separate literature asks whether populations of language models can stand in for human
samples. Argyle et al. (2023) conditioned a model on sociodemographic attributes and recovered
response patterns of the matching subpopulation. Meister et al. (2025) found that a model
verbalising a distribution aligns better than its token probabilities or the samples it
writes. Our protocol scores a verbalised distribution for
that reason.

<!-- Audit des citations du 2026-09-23, Meister et al. : version publiée, NAACL 2025, d'où
     l'année 2025. Les deux méthodes comparées à la distribution verbalisée sont les
     log-probabilités du modèle et une sortie unique portant « a sequence of 30 samples »
     (§ 3.1) ; « sampled repeatedly » décrivait un échantillonnage requête par requête que
     l'article ne mesure pas. -->

<!-- source: en/02_Related_work.md § 2.3, premier paragraphe : Argyle et al. (2023),
     conditionnement sociodémographique reproduisant certains motifs de réponse, pratique dite
     silicon sampling ; Meister et al. (2024), « asked to verbalise a distribution over options,
     models align better than when they are sampled, and a model may know a distribution it
     cannot sample from ». Clés BibTeX : argyle2023outofone (A11), meister2024benchmarking (A12).
     La phrase « Our protocol scores a verbalised distribution for that reason » est la
     justification que le PLAN § 2.3 réclame pour la règle 2 du protocole ; elle ne nomme ni la
     règle ni sa section, consigne R9.
     ⚠ Sortent, faute de place, et signalés au compte-rendu : Kambhatla et al. (2025) et Huang,
     Li & Shao (2025), que le PLAN § 2.3 demande, ainsi que Nguyen, Tschiatschek & Singla (2025)
     et l'expression « silicon sampling ». Aucun énoncé du papier ne repose sur ces quatre
     références. Clés BibTeX disponibles : kambhatla2025improving (A13),
     huang2025distribution (A14), nguyen2025prompt (A15). -->

The same literature also studies these populations for what they do, not as human stand-ins.
Flint Ashery, Aiello & Baronchelli (2025) find that collective biases can emerge in
decentralised model populations even when no agent is biased individually. The SILICA
instrument (Bin Tareaf, 2026) grades claims about such populations. One of its perturbations
swaps the order in which actions are listed, and we adapt that control by randomising the
order of the options.

<!-- Audit des citations du 2026-09-23.
     Flint Ashery et al., résumé : des biais collectifs forts « can emerge … even when agents
     exhibit no bias individually » ; l'article rapporte aussi des cas où des biais individuels
     existent et sont amplifiés. « that no individual agent shows » généralisait. Introduction :
     « our work does not treat LLMs as proxies for human participants » délimite le périmètre de
     leur étude ; ce n'est pas une mise en garde, d'où la phrase d'attaque réécrite.
     SILICA, § 3.8 p. 10 : « The instrument grades a claim rather than a model » ; il ne certifie
     pas des populations. La perturbation d'ordre inverse deux actions (« action-label order =
     swapped »), dans le dilemme du prisonnier seulement. Notre protocole tire l'ordre des
     options au hasard : il adapte ce contrôle plus qu'il ne l'adopte. « We adopt its reading
     grid » tombe : aucune section ne lit ses résultats sur les paliers de SILICA. -->

<!-- source: en/02_Related_work.md § 2.3, second paragraphe : Flint Ashery, Aiello &
     Baronchelli (2025), conventions et biais collectifs absents des agents individuels, « they
     state that their work does not treat LLMs as proxies for human participants » ; SILICA
     (Bin Tareaf, 2026), « certification procedure with an explicit perturbation library, option
     order included ; we adopt it as a reading grid ». La randomisation de l'ordre des options
     est attribuée à SILICA depuis la v0.10 (CITATIONS.md A18) ; le § 3 déjà rédigé applique ce
     contrôle sans le sourcer, et la phrase ci-dessus le source sans le redire.
     Clés BibTeX : baronchelli2025emergent (A17), bintareaf2026silica (A16).
     Clause finale « and we claim no agreement with its results on games » supprimée le
     2026-09-22 sur la RELECTURE_V1, § 9 bis, sixième ligne du tableau de la justification
     d'implémentation : elle défendait le papier contre une objection que personne ne forme,
     le paragraphe disant déjà que SILICA certifie des jeux. La consigne du PLAN § 2.3 tient
     toujours par le négatif, l'article court n'écrivant nulle part « en accord avec SILICA ».
     Sort : Flint Ashery et al. (2025) sur l'effet de la taille du groupe (A18), faute de
     place. -->

<!--
=== SECTION REPORT ===
Section        : 02 — Related work
File           : docs/paper/article-court/sections/02_related_work.en.md
Words / budget : 583 / 450 (+30 %), against 619 before the 2026-09-25 cut of the opening
  and MATSim sentences of 2.2 (−36), 517 before the review pass and 590 after it.
  The 2026-09-23 pass on 2.3 cut 19 words ; the rest of the gap to 613 is the author's own
  hand-edited sentence at line 102 (see the checker line).
  Historic arithmetic of the review pass : The review's own
  arithmetic for section 2 is +85 words of additions (R1 25, R2 50, R3 10) and −10 of
  deletion (9 bis, sixth row), that is +75 net on 517, or 592. The section lands at 590.
  The plan's 450 for section 2 is therefore stale and needs rewriting to 590, not the
  section rewriting itself : nothing was padded, and nothing was cut elsewhere to hide
  the overrun. The whole-paper balance of review section 10 stays as computed there.
Skeleton       :
  Three literatures meet in this paper, and none of them measures whether verbalised
    deliberation helps agents reproduce the mode shares of a real territory.
  Transport research has predicted mode choice for fifty years with discrete choice
    models, which are statistically strong and behaviourally rigid.
  Behavioural research documents departures that no survey records.
  Park et al. (2023) place a language model inside the agent, with a memory stream of its
    experiences and a reflection step. (Opening sentence and MATSim sentence cut on
    2026-09-25, at the author's request.)
  GTA (Lämmer, Colley & Ebel, 2026) is the closest published system on the evaluation
    side, and three of its choices bound what it can show.
  Alves et al. (2026) stand closest on the platform side, though their evaluation has no
    human ground truth.
  A separate literature asks whether populations of language models can stand in for
    human samples.
  The same literature warns against reading these populations as human ones.
  Whether writing the reasoning before answering helps is debated, with no result
    settling it for a population distribution. (Paragraph cut to three sentences on
    2026-09-23 : the justification that followed asserted a property of trips that section
    4.3 contradicts, and a gap is stated, not demonstrated.)
Checker        : none. The R1 finding of 2026-09-23 at line 102 is fixed, on the author's
  confirmation that four tabular models are used. The hand-edited sentence ran to 35 words
  against 25, carried the paragraph's only colon plus two parentheticals, opened on "a
  benchmarks", said two tabular models where section 4.4 names four, and offered "one model
  based on ground truth", which names nothing in this paper : the long article retired that
  oracle at its draft v0.18, where section 4.4 became four tabular references. It also wrote
  "distribution score" for the "distributional metric" defined three lines above, an R12
  collision. Rewritten as three sentences of 16, 11 and 7 words, in the vocabulary section 1.2
  already uses, baseline beneath and models fitted on the survey above ; 57 words become 34.
  Otherwise verifier_forme.py exits clean on the prose after the second G3 pass
  of 2026-09-22 ; R1, R2, R4, R5, R9, R10, R11 and R14 report nothing. Two R1 findings raised
  during the first pass were fixed, both at 29 words : the new habit sentence and the CitySim
  sentence (see the flags). The two sentences rewritten in the second pass are 21 and 18
  words.
Terms defined here : discrete choice model (2.1, by its decision rule) ; perception filter
  (2.1, by the example of the underestimated car price) ; distributional metric (2.2, by
  contrast with one mode per trip) ; verbalised distribution (2.3).
Terms used, undefined upstream : none. GAMA is named without a gloss here, section 1.3
  having glossed it as a multi-agent simulation ; section 3.1 describes it after item T1.
  "Household travel survey" is glossed in section 1.1 ; the relative clause kept here
  ("travel surveys, in which residents describe every trip of one day") is now a second
  statement of it (see the flags).
Figures cited  :
  650 respondents, Adam & Gaudou (2025). Source comment in the body,
    en/02_Related_work.md 2.1, key adam2025survey. No reservation.
  No other number. GTA's 1.99 and 4.07 stay in section 1.2, by the plan.
Placeholders   : none. No [c2] figure is written in this section.
Left out       :
  Kambhatla et al. (2025), Huang, Li & Shao (2025) and Nguyen, Tschiatschek & Singla
    (2025), asked for by plan 2.3, for want of room. No statement of the paper rests on
    them. Keys kambhatla2025improving, huang2025distribution, nguyen2025prompt.
  Chopra et al. (2024) on archetypes, by plan 2.2.
  The description of GTA and its error figures, carried by section 1.2.
Flags for the author :
  1. The two sentences of item R2 are restored with one departure from the verbatim : the
     CitySim sentence ran to 29 words and broke R1, so its "but" coordination became a full
     stop ("…on time use. No experiment there confronts…"). The words and the claim are
     unchanged. The MATSim sentence is verbatim, its ", and the agent does not deliberate"
     tail included, so it was not counted in the G3 quota.
  2. Item R1 is applied as two sentences rather than one, for the same R1 reason, and it
     costs 28 words instead of 25. Both keys, garling2003habitual and verplanken1997habit,
     were verified on 2026-09-23 against their Crossref records, as were wei2022chain and
     sprague2024cot of item R3. Titles, authors, journals, volumes, issues, pages, years and
     DOIs are confirmed. No entry of this section still carries the "written from memory"
     caveat, in any of the three copies of sample.bib.
  3. Resolved on 2026-09-23. The key sprague2024cot carries year = {2024} in all three
     copies of sample.bib, so the printed citation will read 2024 and agree with the body ;
     the reservation recorded here was itself wrong. The paper did appear at ICLR 2025, and
     citing the published version rather than the arXiv deposit would mean rewriting the
     body citation. Author's call, not taken here.
  4b. Duplication with section 1.2, raised by the 2026-09-23 fix and NOT acted on. Section
     1.2 already announces the same bench in the same words : "A baseline beneath the agents
     says what a decision-maker reaches with no behavioural knowledge of the territory.
     Models fitted on that territory's own survey say what its data support." The rewritten
     sentence here restates both. Cutting it would save 16 words and cost nothing the reader
     has not been told, but it is the author's own addition and was left standing.
  4. Rule 8 debt, not a review item, so left untouched : section 1.1 glosses the household
     travel survey, and 2.1 still carries "travel surveys, in which residents describe
     every trip of one day". Section 4.1 carries a third statement. Two of the three should
     fall ; removing the one here would save 11 words, which is why it was not done in this
     pass.
  5. G3, first pass : "Because a model fitted on surveys cannot carry…" (subordinate),
     "Its days are also independent. Its authors name…" (two sentences), "though their
     evaluation has no human ground truth" (concessive), plus the CitySim split of flag 1.
     G3, second pass : the MATSim sentence, which the first pass had kept because the review
     gives it verbatim, is reworded into "In earlier simulators such as MATSim (Horni et al.,
     2016), equilibrium comes from scoring plans rather than from an agent's deliberation" ;
     the opening of 2.3's last paragraph becomes "…is debated, with no result settling it for
     a population distribution". Six breaks in all. The opening sentence of the section, the
     topic sentence on GTA and the enumeration of what we add keep their coordination, each
     carrying a long second clause or a list rather than a short tail.
  6. G1 verified, not redone : no thousands separator appears in the prose of this section.
  7. R4 is applied and agrees with section 3.1, which names GAMA for our own platform after
     item T1. Should T1 be reversed, this sentence becomes the only named platform in the
     paper and should be reversed with it.
=== END SECTION REPORT ===
-->
