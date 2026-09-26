# 1. Introduction

<!-- DERNIÈRE ÉCRITURE ANGLAISE : 2026-09-26 00:10:00 — le .tex correspondant porte cette date en en-tête tant qu'il en est le rendu fidèle. Voir sections/README.md. -->

<!-- Relecture des gallicismes du 2026-09-25, accord de l'auteur (« Corrige ») : tics récurrents (« against » comparatif, « one » pour « un même », « carry », « bound », « under » devant un seuil, « rejoin », « from one X to another », « execute », « brings »), faux-amis (agenda, control, hypothesis, legibility, designate, demanding, chain, globally, bends, recedes), calques de construction et typographie à la française (« 0.9 point », « [a ; b] », « 30.3 % », « 1.06 dollars »). Aucun chiffre ne change ; les prompts et le message de l'annexe D ne sont pas touchés. -->

<!-- Brouillon anglais, article court AAMAS 2027, PLAN.md § 1 — budget 700 mots
     (1.1 180, 1.2 200, 1.3 220, 1.4 100). Rédigé le 2026-09-22 par l'agent article-writer.
     Hypothèse ticket 103 scénario 1. Les §§ 2, 3, 4, 5, 6 et 7 sont écrits : chaque promesse
     faite ici se retrouve dans une section rédigée, et aucune n'annonce une mesure absente.
     AUCUN emplacement [c2] n'est écrit : voir le compte-rendu, décision motivée.
     Nommage (R12) : ni H0, ni paliers, ni conditions étiquetées C1/C2/C3 ; les trois
     contributions du PLAN § 0 sont appelées « the first / second / third contribution ».
     ⚠ Trois dettes réglées ici, qui rendent redondantes trois phrases déjà rédigées en aval :
     la glose de « household travel survey » (§§ 2.1 et 4.1), la définition de
     « decision-maker » (§ 4, phrase d'ouverture) et la description de GTA (§ 2.2). Détail au
     compte-rendu. -->

## 1.1 What generative agents promise

Existing multi-agent simulations of multimodal urban mobility rely on machine learning
models on structured data, or on explicit rules defined by experts. The models are fitted on
household travel surveys, in which the residents of one territory describe every trip they
made on one day. In both approaches, the space of representable behaviours is fixed a priori:
a factor encoded as neither variable nor rule cannot influence any decision.

<!-- source: en/00_Abstract.md, corps v1.9 du 2026-09-21, deux premières phrases reprises mot
     pour mot, formulation du tuteur validée par l'auteur (PLAN § 1.1). « In both cases »
     devient « In both », le mot « cases » ne portant rien. La glose de l'enquête ménages est
     ajoutée ici, première occurrence du terme dans l'article court ; source de la définition,
     fr/04_Evaluation.md § 4.1 et en/02_Related_work.md § 2.1, « residents describe every trip
     of one day ». ⚠ Les §§ 2.1 et 4.1 déjà rédigés portent chacun la même glose ; les deux
     tombent si celle-ci reste. Signalé au compte-rendu. -->

This limit matters most where simulation is most useful. When a city tests a transport
policy on a simulated population before building anything, the answer it gets can only
contain the behaviours its model represents.

<!-- source: en/00_Abstract.md, corps v1.9, troisième phrase (« Yet mode choice is
     multidimensional, and integrating that complexity at city scale is difficult »), reprise
     mot pour mot. Motivation de la simulation : en/01_Introduction.md § 1.1, premier
     paragraphe, « essential to travel planning and network design […] the design of
     personalised mobility policies » (Tisséo Collectivités & AUAT, 2023). Aucun chiffre. -->

Generative agents built on language models promise to lift that limit. Trained on vast amounts of text, they carry decision heuristics that surveys do not record, and they adapt
without explicit rules. A strike, a heatwave or a news item about safety in the metro could
then influence a decision, although no survey column records it. Furthermore, generative
agents appear to possess partial knowledge of human behaviour, allowing them to simulate
choices similar to those made by humans. However, how close these choices come to real ones
remains largely untested.

<!-- source: en/00_Abstract.md, corps v1.9, quatrième phrase (« LLM-based generative agents
     promise to overcome it: fed on massive corpora, they carry decision heuristics surveys do
     not record, adapting without explicit rules »), rendue en deux phrases pour tenir R1 et R2 ;
     « LLM-based » écrit en toutes lettres, l'article court n'employant pas le sigle avant sa
     définition. Les trois exemples, en/01_Introduction.md § 1.1, sixième paragraphe, « a strike,
     a heatwave, a news item about safety in the metro ».
     Texte de l'auteur, 2026-09-25 : les deux phrases finales remplacent la promesse de
     travailler sans données de calibration locales, retirée parce que le papier défend
     l'inverse. Nuance voulue : un comportement qui ressemble à l'humain sans l'être, et un
     réalisme posé en question ouverte, sans annoncer le réglage des prompts. « Largely
     untested » s'accorde au « rarely » du § 1.2. ⚠ Le § 7.2 renvoie encore à la promesse
     retirée (« the promise of Section 1.1, that generative agents would work without local
     calibration data »). -->

## 1.2 Measuring the promise against a real population

Published evaluations of these agents rarely have a human population to compare with. Most
judge a generative agent against a rule-based agent, or against aggregate patterns the
authors produced themselves.

<!-- source: en/01_Introduction.md § 1.1, dernier paragraphe : « Most evaluations compare LLM
     agents with rule-based agents on scenario plausibility, or on aggregate patterns of their
     own making. » Le § 2 déjà rédigé porte le même constat par littérature (2.2 pour Alves
     et al., « adaptability is judged against the rule-based baseline, not against observed
     behaviour ») ; la phrase ci-dessus le dit une fois, en général, et ne cite personne. -->

GTA (Lämmer, Colley & Ebel, 2026) draws its personas from a national travel survey and lets
a language model write each persona's day plan. It then compares the simulated modal split
(the share of trips made by each mode) with that survey. GTA has no baseline of its own. It
is benchmarked instead against the observed splits of other German states, which amount to a
naive predictor, and that predictor wins. Copying Hamburg's observed shares predicts Berlin's
with a root-mean-square error of 1.99, compared with 4.07 for GTA.

<!-- Relecture éditoriale du 2026-09-25, accord de l'auteur (« Corrige », point B7) : le
     lecteur ne savait pas que la cible était Berlin, ni que « se comparer aux autres Länder »
     revenait à prendre les parts d'un autre Land pour prédicteur naïf. La phrase le dit
     maintenant, puis donne le chiffre. Aucun chiffre ne change. -->

<!-- Audit des citations du 2026-09-23 : « Its only modelled reference is the observed split
     of other regions » se contredisait, les parts des autres Länder étant des données
     observées et non modélisées. GTA, § 4 : « Lacking a direct baseline, we benchmark GTA
     against mobility data from other German states. » -->

<!-- source: en/02_Related_work.md § 2.2, troisième paragraphe (v0.14 du 2026-09-10) :
     personas alignés sur le recensement à partir de l'enquête nationale allemande par
     truncate-replicate-sample, description de persona et programme de journée rédigés par un
     LLM, un mode par déplacement parmi des itinéraires candidats ; « GTA gives itself no
     modelled reference: no discrete choice model, no supervised classifier to act as a ceiling,
     and no naive floor. Its comparator is geographical […] predicting Berlin's modal split by
     simply copying Hamburg's observed one yields an error of 1.99, less than half the 4.07 of
     the simulation. » Chiffres : arXiv:2601.16778v2, tableaux 2 et 3, recalculés le 2026-09-10 ;
     erreur quadratique moyenne sur la répartition modale, échantillon à 1 % de Berlin,
     35,769 agents. Clé BibTeX : lammer2026gta (A33).
     ⚠ Le § 2.2 déjà rédigé suppose que l'introduction a dit ce qu'est GTA ; la troisième phrase
     ci-dessus règle cette dette (compte-rendu du § 2), en portant les deux éléments qu'il
     réclame, personas tirés de l'enquête nationale et plan de journée rédigé par le modèle.
     La clause « un mode par déplacement » n'est PAS écrite ici : le § 2.2 la porte comme
     constat load-bearing (« no distributional metric applies ») et elle ne se dit qu'une fois.
     La glose de « modal split » est portée ici, première occurrence ; le § 4.3 la redonne en
     nommant les quatre modes, et les deux peuvent coexister.
     L'échantillon berlinois et les 35,769 agents sortent, faute de place. -->

A score says little about a generative agent until it has something to be compared with.
These evaluations lack four elements that give such a score its meaning. This paper supplies
them.

1. Simple baselines, such as always taking the fastest option, show the score a model reaches
   without knowing how residents choose. They form a floor.
2. Machine learning models on structured data, fitted on the territory's own survey, show the score its data make possible. We call them reference models.
3. The generative agents and the reference models read the same 21 variables for each
   trip. The language models receive a few inputs more, and only the reference models were
   fitted on the survey's trips. Section 4.2 lists both asymmetries.
4. Two agents can reproduce the same modal split while choosing differently for the same
   traveller. Only a trip-by-trip comparison reveals it.

<!-- Relecture éditoriale du 2026-09-25, accord de l'auteur (« Perfect ») : la liste disait à
     quoi sert chaque pièce sans dire ce qu'elle est, et « beneath the agents », « both sides »,
     « what it was told » renvoyaient à ce que le lecteur n'avait pas encore vu. L'amorce dit
     maintenant pourquoi ces pièces manquent : ce sont les points de comparaison de l'agent
     génératif. Le plancher est illustré par la durée minimale, non par le tout-voiture, dont
     le rappel vélo de 2,3 % (annexe I.2) dit qu'il ne met pas tout sur la voiture. « the same
     variables » et non « the same inputs » : les modèles de langue voient aussi trois choses
     qu'aucun modèle de référence n'utilise (§ 4.2). -->

<!-- source: en/01_Introduction.md § 1.1, dernier paragraphe : « What is missing is a protocol
     under which a measurement becomes attributable: a floor beneath the agents, calibrated
     tabular models above them, and the same inputs given to every model compared. » La
     quatrième pièce, la lecture sous l'agrégat, vient du PLAN § 1.2, « et une mesure qui
     descende sous l'agrégat » ; le § 5.4 déjà rédigé la livre. Les quatre pièces se retrouvent
     au § 4 : planchers et références tabulaires au § 4.4, règle 1 au § 4.2, audit unitaire au
     § 4.3. Le mot « floor » du master est rendu « baseline » ici et glosé dans la phrase ; le
     § 4.4 emploie « floors » et les nomme, sans que les deux se redisent.
     Relecture v1, G3 : la phrase d'attaque « Four things are missing from these comparisons,
     and this paper supplies them » est reformulée en une proposition unique. -->

## 1.3 What this paper does

This paper examines the place of text-based models in mobility agents, compared with the
reference models. A text-based model reads the trip description as written text, where a
reference model reads 21 variables. We compare three language models and a classifier that
returns one probability per option and writes no text. We score them against the survey on
the modal split, trip by trip, and on cost. On the ordinary day, the classifier comes
closest to the survey, within the range of the four reference models, and no language model
reaches that range. On that day, reading text therefore brings no fidelity that the
reference models lack. Text may instead matter for events that no survey variable encodes,
which we call off-survey events. Section 6 traces the channel through which one such event
reaches the decision. It shows that the channel exists, not how strong its effect is.

<!-- source: PLAN § 0, thèse : « Dans une population d'agents de mobilité, la délibération
     verbalisée n'améliore pas la fidélité au régime que l'enquête décrit ; ce qu'elle apporte,
     c'est la prise en compte d'événements qu'aucune variable n'encode, dont nous traçons le
     chemin jusqu'à la décision. » La clivée du plan est défaite, consigne R5. La glose de
     « verbalised deliberation » est écrite ici, première occurrence ; le § 5.3 et le § 6.2
     déjà rédigés emploient le terme sans le définir. Les deux énoncés de la thèse sont livrés
     aux §§ 5.3 et 6.4.
     Relecture v1, G3 : la dernière phrase, coordonnée par « , and », est coupée en deux.
     Relecture éditoriale du 2026-09-25 : la glose ne couvrait que le raisonnement écrit avant
     la réponse, alors que le § 5.3 oppose l'agent à un classifieur qui n'écrit rien, ni
     raisonnement ni justification. Elle couvre maintenant les deux : thinking_level « high »
     pour gemini-3.5 et mistral-large (annexe D.1), consigne « Justify the distribution in one
     concise sentence » des deux prompts de modèle de langue (annexes D.2 et D.3).
     Texte de l'auteur, 2026-09-25 18:31 : « does not improve fidelity » devient ce que le
     texte ne fait pas (rapprocher la répartition modale de l'enquête) et sa preuve, le
     classifieur à sortie typée du § 4 (« reads the same text […] without writing a
     sentence »). « At least as close » : le classifieur atteint la bande des références
     (§ 5.3), où aucun modèle de langue n'entre (§ 5.1). ⚠ Dépend du score du classifieur,
     encore « [re-tuning pending] » au § 5.3. Réserve finale reprise du § 6, « We therefore
     claim that this channel exists, not how strong its effect is ». Une seule clivée gardée
     (R5). ⚠ Budget : § 1.3 au-delà de 220 mots, § 1 au-delà de 700. -->

Our measurements cover one study area: the 453 municipalities (communes) around Toulouse covered by
the area's 2023 household travel survey, certified by Cerema, a French public agency. A
cohort of 1,000 synthetic personas, checked against that survey, makes the 3,299 trips of
the day we score. A persona is one simulated person with a household and a day of trips.
Fifteen decision-makers run on those trips. We call anything that turns a trip description into a probability over the options offered a decision-maker. The agents live in a GAMA
multi-agent simulation of the study area, with its actual networks and timetables. That
simulation follows the GAMA–OpenTripPlanner–LLM architecture of Vu et al. (2025).

<!-- ⚠ Remarque de relecture n° 10, 2026-09-23 : « 453 communes » réintroduit aux §§ 3.1, 4.1
     et 7.1. Le périmètre est défini ici, à sa première mention, et « the study area » le
     désigne ensuite. Le relecteur proposait le § 4.1, mais le § 3.1 l'emploie avant. -->

<!-- ⚠ Remarque de relecture n° 4, 2026-09-23 : annonce du tirage dès la définition du
     décideur. Justification au § 3.2. Tirage : mobility_llm/mode_choice.py, draw_index,
     graine = (mode_draw_seed, person_id, activity_id, horodatage),
     urban_mobility_agents/agents/llm_agent.py:1142 ; deux personas de même profil tirent
     donc indépendamment. Troncature du consideration set (seuil 0,15) désactivée par défaut
     (settings.agent.mode_choice_truncation_threshold = 0.0, drapeau troncature_15 = False) :
     la loi tirée est bien le vecteur rendu. -->

<!-- source: fr/04_Evaluation.md § 4.1 et data/population/population_1000_AAMAS_v6/MANIFEST.yaml :
     1,000 personas en 499 ménages entiers, 3,299 déplacements le jour évalué, périmètre des
     453 communes de l'enquête. Enquête EMC² 2023, doi:10.13144/lil-1750 (corrigé le 2026-09-23 : lil-0933 est l'EMD 2013 ; citation rétablie en corps, clé tisseo2023emc2) ; le sigle EMC² n'est
     pas écrit en corps de texte, faute de gloss disponible, et la citation le porte.
     Quinze décideurs : tableau 1 du § 4 déjà rédigé, quinze lignes.
     ⚠ Définition de « decision-maker » portée ici, première occurrence dans l'article (dette
     signalée au compte-rendu du § 3, qui l'emploie aux §§ 3.2 et 3.4). La phrase d'ouverture
     du § 4, « A decision-maker is anything that turns a trip description into a probability
     over the options offered », devient redondante et se coupe là-bas.
     ⚠ Une phrase annonçant le second régime a été retirée de ce paragraphe : elle redisait
     l'ouverture du § 6.1 déjà rédigée (« The household travel survey tabulates one ordinary
     day, and no other »). Le régime non tabulé est annoncé au paragraphe précédent, par la
     thèse, et une seule fois. Les deux régimes chiffrés de l'ancien § 1.6 ne sont pas
     repris.
     Relecture v1, I2 : la définition du décideur, apposée, devient une proposition
     entière ; l'exemplaire du § 4 se coupe là-bas (item Q1, autre agent).
     Relecture v1, I1 : plateforme et filiation ajoutées en fin de § 1.3. Simulation GAMA
     de l'aire toulousaine, réseaux et horaires réels : fr/03_Architecture.md § 3.1 et
     docs/arch/routing.md. Filiation : architecture GAMA–OpenTripPlanner–LLM de
     Vu, Gaudou & Oberoi (2025), arXiv:2510.19497, clé BibTeX vu2025modeling, vérifiée
     dans docs/paper/sources/sample.bib. La phrase du relecteur fait 29 mots ; elle est
     coupée en deux pour tenir R1, sans rien perdre. « multi-agent » ajouté comme glose
     de GAMA, première occurrence du nom dans l'article (consigne 10). -->

The paper makes three contributions. The first is a comparison benchmark between
generative agents and reference models that read the same 21 variables, on a synthetic cohort
checked against that survey. The second is the position of fifteen decision-makers on that
benchmark, and two cases where equal modal shares hide different individual decisions. The
third is the channel through which an off-survey event reaches the decision, traced inside a
generative agent with memory.

<!-- source: PLAN § 0, tableau des trois contributions, une ligne chacune, portées par les
     §§ 3-4, § 5 et § 6. Elles sont nommées « the first / second / third contribution » et
     jamais étiquetées C1, C2, C3 : consigne R12 et PLAN § 1.3, un seul système de noms.
     ⚠ La deuxième contribution dépend du ticket 103, lot A : sous le scénario 3, l'une des
     deux dissociations tombe et la phrase passe à une seule. Aucun chiffre n'est écrit ici,
     donc aucun emplacement à remplir. -->

<!-- § 1.4 Organisation retiré le 2026-09-23 à la demande de l'auteur (relecture « phrases inutiles ») : les titres de section et les transitions de fin de chapitre en tiennent lieu. -->
<!-- source: PLAN § 1.4, six lignes, une par section, sans reprendre le contenu. Six renvois
     vers l'aval, assumés : la consigne R9 proscrit le renvoi vers l'avant, et la levée L0.1 du
     § 0 des consignes autorise la carte de lecture, que le PLAN impose ici. Signalé au
     compte-rendu. -->

<!--
=== SECTION REPORT ===
Section        : 01 — Introduction
File           : docs/paper/article-court/sections/01_introduction.en.md
Words / budget : 647 / 700 (-7.6 %)
Skeleton       :
  Existing multi-agent simulations of multimodal urban mobility rely on tabular models
  estimated from household travel surveys, or on explicit rules defined by domain experts.
  The fixed behaviour space binds precisely where simulation is asked to help.
  Generative agents built on language models promise to overcome that difficulty.
  Published evaluations of these agents rarely have a human population to compare with.
  GTA (Lämmer, Colley & Ebel, 2026) confronts a simulated modal split with a national
  travel survey.
  This paper supplies four things missing from these comparisons.
  This paper measures where verbalised deliberation earns its place in a mobility agent.
  We measure on one territory, the Toulouse area, against its certified 2023 household
  travel survey.
  The paper rests on three contributions.
  The paper follows the order of the measurement.
Checker        : none. verifier_forme.py exits 0 on the prose after the second G3 pass of
  2026-09-22 ; R1, R2, R4, R5, R9, R10, R11 and R14 are clean. G3: four coordinations found,
  two broken — "Mode choice is multidimensional, and integrating…" becomes a subordinate
  ("Because mode choice is multidimensional, integrating…"), and "GTA draws its personas from
  that survey, and a language model writes…" becomes two sentences. The two left are the
  participial sentence on massive corpora and the enumeration of the second contribution.
Terms defined here : household travel survey (1.1) ; modal split (1.2) ; verbalised
  deliberation (1.3) ; decision-maker (1.3, full clause since review item I2).
Terms used, undefined upstream : none. GAMA carries a one-word gloss, "multi-agent
  simulation", at its first occurrence ; section 3.1 describes the platform after item T1.
Figures cited :
  1.99 and 4.07, root-mean-square error of GTA on Berlin's modal split. Source comment in
    the body, en/02_Related_work.md 2.2, arXiv:2601.16778v2 tables 2 and 3, recomputed
    2026-09-10. No reservation.
  1,000 personas and 3,299 trips of the scored day. Source comment in the body,
    fr/04_Evaluation.md 4.1 and the MANIFEST of the v6 cohort. No reservation.
  Fifteen decision-makers. Source comment in the body, Table 1 of section 4.
  Vu, Gaudou & Oberoi (2025), lineage of the architecture. Source comment in the body,
    key vu2025modeling, arXiv:2510.19497, verified in docs/paper/sources/sample.bib.
    A citation, not a measurement.
Placeholders : none. No [c2] figure is written in this section.
Left out :
  The Berlin sample and its 35,769 agents, for want of room.
  The two quantified regimes of the former 1.6, per the plan.
  The naming of the platform of Alves et al., which belongs to section 2.2.
Flags for the author :
  1. The review did not rule on the earlier flag about "the same inputs on both sides"
     (1.2) against "the same 21 input variables". The wording is left untouched and the
     question stays open.
  2. The sentence prescribed by item I1 runs to 29 words and breaks R1. It is split in
     two, and "multi-agent" is added as the gloss of GAMA. Nothing is lost.
  3. "the Toulouse area" now appears twice in the same paragraph of 1.3, the review's
     wording being kept.
  4. GAMA is named here and again in 3.1 after item T1. Both were asked for, so the
     second occurrence should not redefine the platform.
  5. Item I2 leaves the deletion of the section 4 copy to another agent. Should that
     deletion not happen, the definition stands twice against rule 8.
=== END SECTION REPORT ===
-->
