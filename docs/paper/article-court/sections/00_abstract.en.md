# 0. Abstract

<!-- DERNIÈRE ÉCRITURE ANGLAISE : 2026-09-26 00:10:00 — le .tex correspondant porte cette date en en-tête tant qu'il en est le rendu fidèle. Voir sections/README.md. -->

<!-- Relecture des gallicismes du 2026-09-25, accord de l'auteur (« Corrige ») : tics récurrents (« against » comparatif, « one » pour « un même », « carry », « bound », « under » devant un seuil, « rejoin », « from one X to another », « execute », « brings »), faux-amis (agenda, control, hypothesis, legibility, designate, demanding, chain, globally, bends, recedes), calques de construction et typographie à la française (« 0.9 point », « [a ; b] », « 30.3 % », « 1.06 dollars »). Aucun chiffre ne change ; les prompts et le message de l'annexe D ne sont pas touchés. -->

<!-- Brouillon anglais, article court AAMAS 2027, PLAN.md § 10, ligne « 0 Abstract » —
     budget 300 mots. Rédigé le 2026-09-22 par l'agent article-writer. Hypothèse ticket 103
     scénario 1. Les §§ 1 à 7 sont écrits : chaque énoncé ci-dessous est porté par une section
     rédigée, avec la même valeur, la même unité et la même réserve.
     AUCUN emplacement [c2] n'est écrit. La phrase sur le classifieur à sortie typée est
     alignée sur le § 5.3 et rendue sans chiffre du ticket 103, comme la conclusion du § 7.3 ;
     décision motivée au compte-rendu.
     Repris du master en/00_Abstract.md v1.9 : la thèse du § 1 (modèles tabulaires ou règles
     d'experts, espace des comportements fixé a priori, promesse des agents génératifs), les
     3,299 déplacements, et l'idée de division du travail du § 4. Reformulés et non recopiés :
     le § 1.1 déjà rédigé porte les phrases du master mot pour mot, et le lecteur les lirait
     deux fois sur la même page. Sortis : le résultat « très proches des modèles
     traditionnels », l'article de presse sur les punaises de lit et la phrase d'architecture
     hybride ; chacun promet ce que le corps rédigé ne livre pas. Détail au compte-rendu. -->

<!-- TEXTE DE L'AUTEUR, repris mot pour mot le 2026-09-24 15:01:17 à sa demande : il remplace
     les quatre paragraphes du brouillon. Tenu sur une seule ligne pour que le diff avec le
     texte fourni soit exact. Les commentaires « source » et le compte-rendu ci-dessous
     décrivent la version précédente ; ils ne sont pas repris. -->

<!-- Relecture éditoriale du 2026-09-25, accord de l'auteur : langue corrigée (accords, calques « pass », « pro and contra », « time survey »), « rule-based approach » remplacé par « a baseline that sends everyone by car » (contresens : le lecteur comprenait les règles d'experts de la phrase 1), phrases de plus de 30 mots coupées. Retirés faute de correspondre au corps : « calibrated the internal models » et « simulated several days » (le banc porte sur un jour). Message final arbitré par l'auteur le même jour (point 1.5) : le papier évalue les agents génératifs, et les modèles de référence comme le classifieur typé sont des points de comparaison. La dernière phrase ne recommande donc plus de confier le jour ordinaire à un décideur qui ne délibère pas, et le résultat du classifieur est dit pour ce qu'il apprend de l'agent génératif (§ 5.3). Le texte de l'auteur du 2026-09-24 est dans git. -->

<!-- Passe sur les affirmations (claims pass) du 2026-09-25 (soir) : alignement sur le .tex. Causalité retirée sur le texte rédigé (« matching the survey thus does not require writing text » au lieu de « the text ... is thus not what makes it faithful »), « fiftieth » rattaché à l'agent réglé, baseline All-car précisée (« takes the car when offered »), cas mémoire formulé comme trace (« We trace ... »). -->

In agent-based simulations of urban mobility, agents choose their travel mode with machine learning models on structured data, fitted on travel surveys, or with rules written by domain experts. Both approaches fix the space of possible behaviours before the simulation runs: a factor that is neither a variable nor a rule cannot change any decision. Generative agents built on large language models (LLMs) promise to lift this limit, because they carry decision heuristics that surveys do not record. To our knowledge, this promise has rarely been tested against a real population. We assess what LLM-based agents gain and lose when they reproduce human mode choices. We built an agent-based model of daily mobility in the Toulouse urban area (France), populated with 1,000 residents drawn from a realistic synthetic population. Fifteen decision-makers, from simple baselines to machine learning models and LLMs under two prompts, chose modes for the same 3,299 trips. We compare their choices with the area's 2023 household travel survey. Even with a prompt tuned to draw attention to general criteria such as comfort and constraints, the best generative agent comes close to the machine learning models without outperforming them. A classifier that reads the same trip description but writes no text reaches their range for about a fiftieth of that agent's cost. On the ordinary day, matching the survey thus does not require writing text. Matching the modal split does not mean matching individual choices either, since that same classifier gets more trips wrong than a baseline that takes the car when offered. Generative agents, however, can respond to an event described in words. We trace a suspicious noise in the car engine through one agent's memory to its later decisions. Their value should be sought where the survey is silent, not in the ordinary day it describes.

<!-- source: en/00_Abstract.md, corps v1.9 du 2026-09-21, §§ 1 et 2, et le § 1.1 de l'article
     court déjà rédigé. Aucun chiffre. La glose de l'enquête ménages est la même qu'aux
     §§ 1.1 et 4.1, raccourcie en apposition (« surveys of declared trips ») : la glose
     complète du § 1.1 se lirait deux fois sur la même page. « Whether the promise survives une
     comparaison » reprend le constat du § 1.2 (évaluations publiées sans population humaine
     de référence) sans citer GTA, qui ne tient pas en un résumé. -->

<!-- source: fr/04_Evaluation.md § 4.1 et data/population/population_1000_AAMAS_v6/MANIFEST.yaml :
     1,000 personas en 499 ménages entiers, treize marges contrôlées toutes conformes à
     ±1 point, 3,299 déplacements le jour évalué, périmètre des 453 communes. Enquête EMC² 2023,
     doi:10.13144/lil-1750 ; EMC² = Enquête Mobilité Certifiée Cerema, d'où « Cerema-certified
     2023 » en corps de texte. Corrigé le 2026-09-23 : lil-0933 est le DOI de l'EMD 2013 ; le
     Cerema s'écrit en casse mixte et certifie une enquête produite avec Tisséo Collectivités. Le sigle EMC² n'est pas écrit (§ 1.3), la citation en
     note de bas de page du `.tex` le porte. Quinze décideurs : tableau 1 du § 4.
     Règle 1 (21 variables) et règle 2 (masse de probabilité) : § 4.2. La règle 3 n'est pas
     citée, faute de place ; elle ne porte aucun énoncé du résumé. -->

<!-- source: § 5.1 pour la bande tabulaire 3,60-4,09 et le meilleur agent réglé à 4,86,
     « no generative agent passes the four tabular references » ; § 5.2 pour les gains
     appariés du prompt expert. La phrase 1 du PLAN § 0, « atteint les modèles tabulaires
     sans les dépasser », est rendue en deux énoncés — « moves […] close to » puis « None of
     our agents passes them » — pour que le résumé reste vrai du chiffre : le meilleur agent
     réglé est à 4,86, la bande tabulaire à 3,60-4,09, et aucun agent n'y entre. ⚠ Écart de
     formulation avec le PLAN, signalé au compte-rendu.
     Classifieur à sortie typée : § 5.3, phrase de tête sous le scénario 1, et § 7.3. Aucun
     chiffre du ticket 103 n'est écrit. « Matches them » porte la lecture composite, où les
     quatre intervalles appariés contiennent zéro ; sur les deux autres lectures agrégées le
     § 5.4 le place derrière la régression à noyau et la forêt aléatoire. Facteur cinquante : fr/08_Limitations.md § 8.3,
     1,06 $ contre 49,28 $ à 23,026 décisions, mesure indépendante du ticket 103.
     Une décision sur trois : annexe H.5, 30,3 % de désaccord sur le mode le plus probable
     entre l'agent réglé et le gradient boosté, contre 8,4 à 11,0 % entre tabulaires (§ 5.4).
     Sous le plancher : fr/99_annexes.md I.1 bis, 64,3 % contre 66,7 %, écart apparié
     −2,42 point [−4,26 ; −0,62] (§ 5.4).
     « Points a model at the lived circumstances of a trip » : texte du prompt expert,
     packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml, prompt_expert_05, en-tête
     « Situational trade-off principles » et ses quatre puces (friction de chaîne, autonomie
     des personnes âgées, logistique de portage, temps de vie des actifs). Le prompt ne donne
     aucune règle de pondération des options ; la formulation précédente, « tells a model how
     to weigh the options », était fausse. Correction de l'auteur du 2026-09-22, appliquée
     aussi aux §§ 4.4 et 5. -->

<!-- source: § 6.3 et § 6.4 : un agent joué deux fois, avarie moteur, propension à la voiture
     de 90 % la veille à 40 % le jour même, retour dans la bande du témoin le 15 avril, soit
     quinze jours après l'avarie du 30 mars ; durée de service du souvenir 15,29 jours
     (llm/noyau.py, duree_service_jours, gravité 0,70), récit présent dans les prompts
     jusqu'au quinzième jour (§ 6.4) ; le récit présent dans 75 des 376 prompts de décision, par le bloc « ce qui
     a changé récemment », le rappel par similarité et la croyance consolidée n'ayant porté
     aucun effet. Aucun chiffre du § 6 n'est repris dans le résumé : la section revendique le
     chemin, pas l'amplitude, et aucun de ses nombres ne porte d'intervalle (§ 7.2).
     § 6.1 pour l'écart nul par identité d'un décideur restreint aux 21 variables.
     Dernière phrase : division du travail du § 7.1, « a deterministic stage […] a tabular
     model or a typed classifier then holds the nominal regime […] the language model receives
     what no variable carries, rates it, and writes it into memory ». Le choix du décideur
     nominal n'est pas tranché ici, le § 7.1 disant qu'il ne l'est pas par nos mesures.
     ⚠ La presse n'est pas annoncée : la campagne n'a pas tourné (§ 6.4). -->

<!--
=== SECTION REPORT ===
Section        : 00 — Abstract
File           : docs/paper/article-court/sections/00_abstract.en.md
Words / budget : 297 / 300 (-1.0 %)
Skeleton       : Multi-agent simulations of urban mobility choose travel modes with tabular
                 models fitted on surveys of declared trips, or with rules written by domain
                 experts.
                 We measure it on the Toulouse area, against its Cerema-certified 2023
                 household travel survey.
                 Tuning the prompt that points a model at the lived circumstances of a trip
                 moves a generative agent close to the tabular models.
                 Verbalised deliberation earns its place outside that ordinary day.
Checker        : none. verifier_forme.py exits 0 after the author's corrections of 2026-09-22 ;
                 R1, R2, R4, R5, R9, R10, R11 and R14 report nothing. The reworded third
                 topic sentence is 23 words, the engine-failure sentence 17.
Terms defined here     : decision-maker (implicit, by use); typed classifier (own definition,
                 kept here because the abstract is a standalone text, review § 9 bis);
                 household travel survey (glossed in apposition, "surveys of declared trips");
                 sealed cohort of synthetic personas; margin (control margin of the cohort)
Terms used, undefined upstream : none. The abstract precedes every section, so each term it
                 uses carries its own half-sentence gloss or is a common LLM term (prompt,
                 language model, classifier)
Figures cited  : 1,000 synthetic personas — fr/04_Evaluation.md § 4.1 and the cohort MANIFEST
                 — no reservation
                 thirteen margins — same source — all within ±1 point
                 3,299 trips — same source — the scored day only
                 21 input variables — § 4.2, rule 1 — no reservation
                 fifteen decision-makers — Table 1 of § 4 — no reservation
                 one trip in three — Appendix H.5, 30.3 % disagreement on the most probable
                 mode — measured on the scored cohort
                 a fiftieth of the cost — fr/08_Limitations.md § 8.3, 1.06 against 49.28
                 dollars at 23,026 decisions — independent of ticket 103
Placeholders   : none written. The typed-classifier sentence carries no [c2] figure; it will
                 take its out-of-sample status from review item A2 once § 5.3 is filled
Left out       : the press campaign (not run, § 6.4); the hybrid-architecture sentence and the
                 "very close to traditional models" result of the master abstract, both
                 promising more than the drafted body delivers
Flags for the author :
  - Wording gap with PLAN § 0, already flagged in the source comment: the plan says the
    generative agent "reaches the tabular models without passing them"; the measured best
    tuned agent is at 4.86 against a tabular band of 3.60 to 4.09, so the abstract says
    "moves close to" and then "None of our agents passes them".
  - "Matches them for a fiftieth of the cost" holds on the composite reading, where the four
    paired intervals contain zero; on the two other aggregate readings § 5.4 places the typed
    classifier behind kernel regression and random forest. Review item A2 will add the
    out-of-sample status of that claim.
  - Review item G3 (the ", and" tic), second pass: three coordinations were found, one was
    broken. "It gives them the same 21 input variables, and it scores the probability each
    places on every option offered" becomes two sentences, the two protocol rules unchanged.
    The two left carry a long second clause rather than a short maxim tail: the relative
    clause of the classifier sentence, and the division of labour that closes the abstract.
  - Review item A3 (thousands separators) verified, not redone: 1,000, 3,299, 21 and 23,026
    are correct and no French thin space remains in the file.
  - Author's corrections of 2026-09-22, applied here. First, the expert prompt is no longer
    described as telling a model how to weigh the options: its own header reads "Situational
    trade-off principles" and its four bullets name lived circumstances, not weights. The
    abstract now says the prompt "points a model at the lived circumstances of a trip", and
    the four principles are named once, in 4.4. Second, "held the agent away from the car for
    a fortnight" becomes "discouraged car use for fifteen days": the car stays offered
    throughout (6.3), and fifteen days is the measured figure, the failure falling on 30 March
    and the propensity rejoining the control band on 15 April.
  - "the models fitted on the survey" becomes "the tabular models" to keep the reworded topic
    sentence under 25 words. The gloss is in the first paragraph, "tabular models fitted on
    surveys of declared trips", so the term is defined before it is reused.
  - The abstract keeps "a classifier that reads the same context under a fixed output type",
    its own standalone wording. It does not say "zero-shot", which 4.4 now does and which
    7.1's "needs no local survey" leans on. Worth one word here if the author wants the
    abstract to carry that property.
-->
