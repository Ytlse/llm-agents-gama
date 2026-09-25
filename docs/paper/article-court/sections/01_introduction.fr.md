# 1. Introduction

<!-- Rendu français de `01_introduction.en.md` (consigne R17), article court AAMAS 2027.
     Injecté le 2026-09-23 par outils/injecter_traduction.py
     depuis 01_introduction.traduit.txt. L'anglais fait foi : mêmes coupes de paragraphe,
     mêmes chiffres, mêmes commentaires de source. Aucune décision de fond
     n'est prise ici ; un problème de fond se signale et se corrige en anglais. -->

## 1.1 Les promesses des agents génératifs

Les simulations multi-agents existantes de mobilité urbaine multimodale reposent sur des
modèles tabulaires estimés à partir d'enquêtes de mobilité des ménages, ou sur des règles
explicites définies par des experts du domaine. Une enquête de mobilité des ménages demande aux
habitants d'un territoire de décrire tous leurs déplacements d'une journée. Dans les deux cas,
l'espace des comportements représentables est fixé a priori : un facteur non codé comme
variable ou règle ne peut influencer aucune décision.

<!-- source: en/00_Abstract.md, corps v1.9 du 2026-09-21, deux premières phrases reprises mot
     pour mot, formulation du tuteur validée par l'auteur (PLAN § 1.1). « In both cases »
     devient « In both », le mot « cases » ne portant rien. La glose de l'enquête ménages est
     ajoutée ici, première occurrence du terme dans l'article court ; source de la définition,
     fr/04_Evaluation.md § 4.1 et en/02_Related_work.md § 2.1, « residents describe every trip
     of one day ». ⚠ Les §§ 2.1 et 4.1 déjà rédigés portent chacun la même glose ; les deux
     tombent si celle-ci reste. Signalé au compte-rendu. -->

Cet espace comportemental fixé limite précisément le domaine où la simulation est censée être
utile. Une ville teste une politique de transport sur une population simulée avant
d'entreprendre toute construction. Le résultat obtenu est limité par les comportements que son
modèle peut représenter. Le choix du mode de transport étant multidimensionnel, l'intégration
de cette complexité à l'échelle de la ville est difficile.

<!-- source: en/00_Abstract.md, corps v1.9, troisième phrase (« Yet mode choice is
     multidimensional, and integrating that complexity at city scale is difficult »), reprise
     mot pour mot. Motivation de la simulation : en/01_Introduction.md § 1.1, premier
     paragraphe, « essential to travel planning and network design […] the design of
     personalised mobility policies » (Tisséo Collectivités & AUAT, 2023). Aucun chiffre. -->

Les agents génératifs construits sur des modèles de langage promettent de surmonter cette
difficulté. Alimentés par des corpus massifs, ils intègrent des heuristiques de décision que
les enquêtes n'enregistrent pas et s'adaptent sans règles explicites. Une grève, une vague de
chaleur ou un article de presse sur la sécurité dans le métro pourraient alors influencer une
décision qu'aucune enquête ne permet de prendre en compte. Ces systèmes promettent également de
fonctionner sans les données d'étalonnage locales requises par les modèles à base d'agents. Des
ensembles de données détaillés sur les trajectoires multimodales n'existent que pour quelques
grandes métropoles.

<!-- source: en/00_Abstract.md, corps v1.9, quatrième phrase (« LLM-based generative agents
     promise to overcome it: fed on massive corpora, they carry decision heuristics surveys do
     not record, adapting without explicit rules »), rendue en deux phrases pour tenir R1 et R2 ;
     « LLM-based » écrit en toutes lettres, l'article court n'employant pas le sigle avant sa
     définition. Les trois exemples, en/01_Introduction.md § 1.1, sixième paragraphe, « a strike,
     a heatwave, a news item about safety in the metro ».
     Données de calibration : en/01_Introduction.md § 1.1, troisième paragraphe (Liu, Yang & Yin,
     2024 ; Feng et al., 2024 ; Fourez et al., 2025). ⚠ Réserve de la source portée dans la
     phrase par le verbe « promise » : la v0.11 du master a retiré comme fausse l'affirmation
     que ces données sont inaccessibles ; la rareté ne porte que sur les jeux de trajectoires
     détaillées, et les microdonnées d'enquête, elles, s'obtiennent. -->

## 1.2 Évaluation de la promesse face à une population réelle

Les évaluations publiées de ces agents se basent rarement sur une population humaine pour
comparaison. La plupart comparent un agent génératif à un agent basé sur des règles, ou à des
modèles agrégés produits par les auteurs eux-mêmes. Un système se distingue.

<!-- source: en/01_Introduction.md § 1.1, dernier paragraphe : « Most evaluations compare LLM
     agents with rule-based agents on scenario plausibility, or on aggregate patterns of their
     own making. » Le § 2 déjà rédigé porte le même constat par littérature (2.2 pour Alves
     et al., « adaptability is judged against the rule-based baseline, not against observed
     behaviour ») ; la phrase ci-dessus le dit une fois, en général, et ne cite personne. -->

GTA (Lämmer, Colley et Ebel, 2026) confronte une répartition modale simulée à une enquête
nationale sur les déplacements. La répartition modale correspond à la part des déplacements
effectués par chaque mode. GTA construit ses profils d'utilisateurs à partir de cette enquête.
Un modèle de langage rédige le plan de journée de chacun. Sa seule référence modélisée est la
répartition observée dans d'autres régions. Copier les parts de marché de Hambourg génère une
erreur quadratique moyenne de 1,99 par rapport à Berlin, contre 4,07 pour sa propre simulation.

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

Cet article apporte quatre éléments manquants à ces comparaisons. Une ligne de base sous les
agents indique la décision qu'un décideur prendrait sans connaissance comportementale du
territoire. Les modèles ajustés sur l'enquête propre à ce territoire indiquent ce que
confirment ses données. Les mêmes entrées de part et d'autre créent un écart attribuable au
décideur plutôt qu'aux informations qui lui ont été fournies. Une lecture sous l'agrégat
indique si deux décideurs produisant les mêmes parts de marché prennent des décisions
similaires.

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

## 1.3 Ce que cet article apporte

Cet article évalue la place de la délibération verbalisée dans un agent de mobilité. La
délibération verbalisée consiste pour le modèle à formaliser son raisonnement par écrit avant
de répondre. Dans une population d'agents de mobilité, elle n'améliore pas la fidélité au
régime ordinaire décrit par l'enquête. Elle introduit des événements qu'aucune variable
n'encode. Nous retraçons le cheminement d'un tel événement jusqu'à la décision.

<!-- source: PLAN § 0, thèse : « Dans une population d'agents de mobilité, la délibération
     verbalisée n'améliore pas la fidélité au régime que l'enquête décrit ; ce qu'elle apporte,
     c'est la prise en compte d'événements qu'aucune variable n'encode, dont nous traçons le
     chemin jusqu'à la décision. » La clivée du plan est défaite, consigne R5. La glose de
     « verbalised deliberation » est écrite ici, première occurrence ; le § 5.3 et le § 6.2
     déjà rédigés emploient le terme sans le définir. Les deux énoncés de la thèse sont livrés
     aux §§ 5.3 et 6.4.
     Relecture v1, G3 : la dernière phrase, coordonnée par « , and », est coupée en deux. -->

Nous effectuons des mesures sur un territoire, la région toulousaine, en nous basant sur son
enquête certifiée sur les déplacements des ménages de 2023. Une cohorte contrôlée de 1 000
profils synthétiques réalise les 3 299 déplacements du jour que nous analysons. Quinze
décideurs interviennent sur ces déplacements. Nous considérons comme décideur tout agent qui
transforme la description d'un déplacement en une probabilité parmi les options proposées. Les
agents évoluent dans une simulation multi-agents GAMA de la région toulousaine, avec ses
réseaux et horaires réels. Cette simulation suit l'architecture GAMA–OpenTripPlanner–LLM de Vu
et al. (2025).

<!-- source: fr/04_Evaluation.md § 4.1 et data/population/population_1000_AAMAS_v6/MANIFEST.yaml :
     1,000 personas en 499 ménages entiers, 3,299 déplacements le jour évalué, périmètre des
     453 communes de l'enquête. Enquête EMC² 2023, doi:10.13144/lil-0933 ; le sigle EMC² n'est
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

Cet article repose sur trois contributions. La première est un banc d'essai comparatif avec des
entrées identiques entre agents génératifs et modèles tabulaires, sur une cohorte synthétique
contrôlée par rapport à cette enquête. La deuxième est la position des quinze décideurs sur ce
banc d'essai, et deux dissociations que les parts agrégées ne révèlent pas. La troisième est le
cheminement d'un événement non tabulé jusqu'à la décision, au sein d'un agent génératif doté de
mémoire.

<!-- source: PLAN § 0, tableau des trois contributions, une ligne chacune, portées par les
     §§ 3-4, § 5 et § 6. Elles sont nommées « the first / second / third contribution » et
     jamais étiquetées C1, C2, C3 : consigne R12 et PLAN § 1.3, un seul système de noms.
     ⚠ La deuxième contribution dépend du ticket 103, lot A : sous le scénario 3, l'une des
     deux dissociations tombe et la phrase passe à une seule. Aucun chiffre n'est écrit ici,
     donc aucun emplacement à remplir. -->

## 1.4 Organisation

L'article suit l'ordre des mesures. La section 2 situe l'étude dans trois contextes
bibliographiques. La section 3 décrit ce que l'agent évalué reçoit et restitue. La section 4
présente le banc d'essai et son protocole. La section 5 décrit une journée type. La section 6
traite de l'événement non tabulé. La section 7 tire les implications, les limites et la
conclusion.

<!-- source: PLAN § 1.4, six lignes, une par section, sans reprendre le contenu. Six renvois
     vers l'aval, assumés : la consigne R9 proscrit le renvoi vers l'avant, et la levée L0.1 du
     § 0 des consignes autorise la carte de lecture, que le PLAN impose ici. Signalé au
     compte-rendu. -->

<!--
=== SECTION REPORT ===
Section        : 01 — Introduction (rendu français)
File           : docs/paper/article-court/sections/01_introduction.fr.md
Words / budget : 709 mots de prose française, contre 646 à l'anglais (+9,8 %), écart normal
                 de foisonnement. Budget du PLAN § 1 : 700 mots, soit +1,3 %. Par
                 sous-section, français contre anglais : 226/197, 200/180, 220/213, 63/56.
                 Les groupes « 1 000 » et « 3 299 » comptent chacun pour deux mots dans
                 verifier_forme.py ; à séparateur anglais la prose ferait 707 mots.
Skeleton       :
  Les simulations multi-agents existantes de mobilité urbaine multimodale reposent sur des
    modèles tabulaires estimés depuis des enquêtes ménages-déplacements.
  L'espace des comportements fixé contraint là même où la simulation est censée aider.
  Les agents génératifs fondés sur des modèles de langue promettent de lever cette
    difficulté.
  Les évaluations publiées de ces agents ont rarement une population humaine à qui se
    comparer.
  GTA (Lämmer, Colley & Ebel, 2026) confronte une part modale simulée à une enquête ménages
    nationale.
  Cet article fournit quatre pièces qui manquent à ces comparaisons.
  Cet article mesure où la délibération verbalisée gagne sa place dans un agent de mobilité.
  Nous mesurons sur un territoire, l'aire toulousaine, face à son enquête
    ménages-déplacements certifiée de 2023.
  L'article repose sur trois contributions.
  L'article suit l'ordre de la mesure.
Checker        : aucun constat. verifier_forme.py sort en 0 ; R1, R2, R4, R5, R9, R10, R11 et
                 R14 ne signalent rien. Les motifs R5 du script sont anglais ; relecture à la
                 main, aucune clivée « c'est … que » dans la section.
Terms defined here     : aucun. Les quatre gloses de l'anglais sont rendues à leur place :
                 enquête ménages-déplacements (1.1), part modale (1.2), délibération
                 verbalisée (1.3), décideur (1.3).
Terms used, undefined upstream : aucun. GAMA porte sa glose d'un mot, « simulation
                 multi-agents », à sa première occurrence.
Figures cited  : 1,99 et 4,07, erreur quadratique moyenne de GTA sur la répartition modale de
                   Berlin — commentaire source dans le corps, en/02_Related_work.md 2.2,
                   arXiv:2601.16778v2 tableaux 2 et 3, recalculés le 2026-09-10 — sans réserve
                 1 000 personas et 3 299 déplacements de la journée évaluée — commentaire
                   source dans le corps, fr/04_Evaluation.md 4.1 et le MANIFEST de la cohorte
                   v6 — sans réserve
                 quinze décideurs — commentaire source dans le corps, tableau 1 de la
                   section 4
                 Vu et al. (2025), filiation de l'architecture — commentaire source dans le
                   corps, clé vu2025modeling — citation, pas une mesure
Placeholders   : aucun. Aucun chiffre [c2] n'est écrit dans cette section.
Left out       : rien. Les neuf paragraphes de l'anglais sont rendus en entier.
Flags for the author :
  1. Découpage, § 1.1 premier paragraphe : l'anglais fait trois phrases, le français cinq.
     Deux coupures, toutes deux imposées par R1. La première phrase rendue en entier fait
     29 mots, d'où « […] enquêtes ménages-déplacements. D'autres reposent sur des règles
     explicites définies par des experts du domaine. » La dernière, reprise du master
     fr/00_Abstract.md, fait 26 mots avec son deux-points, d'où la coupure devant « Un
     facteur encodé ni comme variable ni comme règle ». Cette coupure fait tomber le seul
     deux-points de la section.
  2. « In both » de l'anglais est rendu « Dans les deux cas », formulation du master
     fr/00_Abstract.md. « Dans les deux » seul n'est pas français. L'anglais avait retiré
     « cases » comme ne portant rien ; le français ne peut pas suivre.
  3. Terminologie choisie ici, à suivre dans les autres rendus : « baseline » (§ 1.2) →
     « référence basse », et non « plancher », réservé par la table des termes à « floor »
     du § 4.4. L'anglais distingue les deux mots à dessein et le français les distingue
     donc aussi.
  4. Terminologie sous contrainte : la table impose « modal split » → « part modale ». Les
     masters écrivent « répartition modale » dans cette phrase même sur GTA
     (fr/02_Related_work.md § 2.2). Le rendu applique la table et écrit « part modale » pour
     la grandeur, en gardant « la répartition observée d'autres régions » là où l'anglais
     écrit « the observed split of other regions ». Décision à confirmer par l'auteur.
  5. Problème de fond, non corrigé ici et déjà signalé au compte-rendu anglais : la glose
     de l'enquête ménages-déplacements est écrite trois fois dans l'article, au § 1.1, au
     § 2.1 et au § 4.1. Le rendu français reproduit les deux premières telles quelles.
=== END SECTION REPORT ===
-->
