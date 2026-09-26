# 2. Travaux connexes

<!-- Rendu français de `02_related_work.en.md` (consigne R17), article court AAMAS 2027.
     Injecté le 2026-09-23 par outils/injecter_traduction.py
     depuis 02_related_work.a-traduit.txt. L'anglais fait foi : mêmes coupes de paragraphe,
     mêmes chiffres, mêmes commentaires de source. Aucune décision de fond
     n'est prise ici ; un problème de fond se signale et se corrige en anglais. -->

Trois courants de recherche convergent dans cet article, et aucun n'évalue si la délibération
verbalisée aide les agents à reproduire les parts modales d'un territoire réel.

## 2.1 Choix discret et filtres de perception

Depuis cinquante ans, la recherche sur les transports prédit les choix modaux à l'aide de
modèles de choix discrets, statistiquement robustes et rigides sur le plan comportemental. Un
tel modèle attribue à chaque mode une probabilité calculée à partir du temps de trajet, du coût
et des caractéristiques du voyageur (McFadden, 1974 ; Ben-Akiva et Lerman, 1985). Les analystes
l'ajustent aux enquêtes de mobilité, dans lesquelles les résidents décrivent chaque déplacement
d'une journée, de sorte qu'il hérite de leurs parts modales (Train, 2009). Sa règle de
décision, cependant, consiste en une maximisation sur des distributions fixes de préférences.

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

La recherche comportementale documente des départs non enregistrés par les enquêtes. L'habitude
automatise un choix modal répété. Le voyageur acquiert alors moins d'informations sur les
alternatives (Verplanken, Aarts et van Knippenberg, 1997 ; Gärling et Axhausen, 2003). Adam et
Gaudou (2025) ont interrogé 650 personnes et ont constaté que les automobilistes réguliers
sous-estimaient le prix d'une voiture. Un modèle basé sur des enquêtes ne pouvant intégrer de
tels filtres de perception, des agents génératifs sont proposés pour combler cette lacune.

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

## 2.2 Agents génératifs dans la simulation de mobilité

Les modèles de langage ont fait leur apparition dans la simulation de mobilité en tant que
composante délibérative absente des simulateurs précédents. Park et al. (2023) intègrent le
modèle à l'agent, lui conférant une mémoire épisodique et une capacité de réflexion. Liu, Yang
et Yin (2024) transposent cette approche à la demande de transport, sous la forme d'un système
hybride combinant des composants existants. CitySim (Bougie et Watanabe, 2025) déploie ces
agents à l'échelle d'une ville et les valide en fonction de l'utilisation du temps. Aucune
expérience ne confronte une répartition modale simulée à une répartition observée. Dans les
simulateurs antérieurs tels que MATSim (Horni et al., 2016), l'équilibre résulte de
l'attribution de scores aux plans plutôt que de la délibération d'un agent.

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

GTA (Lämmer, Colley & Ebel, 2026) est le système publié le plus proche en termes d'évaluation,
et trois de ses options limitent ce qu'il peut afficher. Chaque agent renvoie un seul mode par
trajet plutôt qu'une distribution, de sorte qu'aucune métrique distributionnelle ne s'applique.
Ses jours sont également indépendants. Ses auteurs indiquent que la mémoire multi-jours fera
l'objet de travaux futurs. Nous ajoutons des points de référence : un seuil de performance
minimal défini par des modèles non intelligents (heuristiques simples telles que le plus court
chemin ou la sélection aléatoire), et un seuil maximal établi par deux modèles tabulaires et un
modèle basé sur des données réelles. En plus de ce cadre d'évaluation, nous incluons un score
de distribution et une mémoire qui conserve les événements sur plusieurs jours.

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
     de 5,42 à 8,23, et son équilibre usager dynamique recalé sur des comptages. -->

Alves et al. (2026) sont les plus proches du point de vue de la plateforme, bien que leur
évaluation ne repose sur aucune vérité humaine de terrain. Ils couplent la plateforme GAMA à un
module de modélisation du langage doté d'une mémoire persistante, qui détermine, en cas de
perturbation, si un agent doit replanifier sa stratégie. Ils évaluent l'adaptabilité par
rapport à une base de référence fondée sur des règles, et non par rapport au comportement
observé.

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

## 2.3 Alignement distributionnel des populations de modèles de langage

Une autre littérature s'interroge sur la capacité des populations de modèles de langage à se
substituer à des échantillons humains. Argyle et al. (2023) ont conditionné un modèle à partir
d'attributs sociodémographiques et ont retrouvé les schémas de réponse de la sous-population
correspondante. Meister et al. (2024) ont constaté qu'un modèle verbalisant une distribution
s'aligne mieux que le même modèle échantillonné de manière répétée. C'est pourquoi notre
protocole évalue une distribution verbalisée.

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

Cette même littérature met en garde contre l'interprétation de ces populations comme étant des
populations humaines. Flint Ashery, Aiello et Baronchelli (2025) mettent en évidence des biais
collectifs dans des populations modèles décentralisées, biais qu'aucun agent individuel ne
manifeste. Ils contestent le statut de proxy humain. L'instrument SILICA (Bin Tareaf, 2026)
certifie ces populations à l'aide d'une bibliothèque de perturbations, incluant l'ordre des
options. Nous adoptons sa grille de lecture et son contrôle de l'ordre des options.

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

L'intérêt de rédiger un raisonnement avant de répondre fait débat, aucun résultat ne permettant
de trancher la question pour une distribution de population. Les gains observés pour le
raisonnement écrit proviennent de tâches admettant une réponse unique vérifiable (Wei et al.,
2022 ; Sprague et al., 2024). Les parts modales d'un territoire ne peuvent être déterminées
trajet par trajet. Nous posons donc la question à une population de mobilité, construite comme
décrit dans la section suivante.

<!-- source : RELECTURE_V1, item R3, appliqué le 2026-09-22. Le raisonnement rédigé avant la
     réponse, Wei et al. (2022) ; concentration des gains sur les tâches à réponse unique
     vérifiable, mathématiques et raisonnement symbolique, Sprague et al. (2024), « To CoT or
     not to CoT », qui est la source de la phrase portant la citation. Clés BibTeX :
     wei2022chain, sprague2024cot.
     ⚠ Les deux entrées ont été versées dans sample.bib le 2026-09-22 de mémoire et portent la
     note « entry written from memory, not from a deposited PDF » ; à vérifier avant soumission.
     ⚠ La clé sprague2024cot porte year = {2025} (ICLR 2025) alors que le corps écrit
     « Sprague et al., 2024 », d'après la relecture et la préimpression arXiv de 2024 : l'un
     des deux doit céder avant la passe LaTeX. Signalé au compte-rendu.
     Le § 5.3 déjà rédigé porte deux phrases qui disent la même chose (« The published debate on
     written reasoning reports gains on tasks that have a verifiable answer. A modal split has
     no verifiable answer trip by trip ») ; elles deviennent redondantes et se coupent là-bas,
     le constat de mesure du § 5.3 restant.
     Dernière phrase : test du fil (règle 17), sans renvoi numéroté vers l'aval, consigne R9. -->

<!--
=== SECTION REPORT ===
Section        : 02 — Travaux liés (rendu français)
File           : docs/paper/article-court/sections/02_related_work.fr.md
Words / budget : 674 mots de prose française, contre 591 à l'anglais (+14,0 %), écart normal
                 de foisonnement. Par sous-section, français contre anglais : 24/24, 171/149,
                 261/227, 218/191. Budget du PLAN § 2 : 450 mots, soit +50 %. Ce dépassement
                 est celui de l'anglais, dont le compte-rendu établit que le budget du plan
                 est périmé depuis la RELECTURE_V1 (items R1, R2, R3) ; le rendu français
                 n'ajoute rien et ne retranche rien.
Skeleton       :
  Trois littératures se croisent ici, et aucune ne mesure si la délibération verbalisée aide
    des agents à reproduire les parts modales d'un territoire réel.
  La recherche en transport prédit le choix modal depuis cinquante ans avec des modèles de
    choix discrets, statistiquement solides et comportementalement rigides.
  La recherche comportementale documente des écarts qu'aucune enquête n'enregistre.
  Les modèles de langue sont entrés dans la simulation de mobilité comme la part délibérante
    qui manquait aux simulateurs antérieurs.
  GTA (Lämmer, Colley & Ebel, 2026) est, côté évaluation, le système publié le plus proche,
    et trois de ses choix bornent ce qu'il peut montrer.
  Alves et al. (2026) sont les plus proches du côté de la plateforme, quoique leur évaluation
    n'ait pas de vérité terrain humaine.
  Une littérature distincte demande si des populations de modèles de langue peuvent tenir
    lieu d'échantillons humains.
  La même littérature met en garde contre la lecture de ces populations comme des populations
    humaines.
  Que le fait d'écrire le raisonnement avant de répondre aide est débattu, et aucun résultat
    ne tranche pour une distribution de population.
Checker        : aucun constat. verifier_forme.py sort en 0 ; R1, R2, R4, R5, R9, R10, R11 et
                 R14 ne signalent rien. Les motifs R5 du script sont anglais ; relecture à la
                 main, aucune clivée « c'est … que » dans la section.
Terms defined here     : aucun. Les quatre gloses de l'anglais sont rendues à leur place :
                 modèle de choix discret (2.1, par sa règle de décision), filtre de perception
                 (2.1, par l'exemple du prix sous-estimé), métrique distributionnelle (2.2,
                 par contraste avec un mode unique par déplacement), distribution verbalisée
                 (2.3).
Terms used, undefined upstream : aucun. GAMA est nommé sans glose ici, le § 1.3 l'ayant glosé
                 « simulation multi-agents ».
Figures cited  : 650 répondants, Adam & Gaudou (2025) — commentaire source dans le corps,
                   en/02_Related_work.md 2.1, clé adam2025survey — sans réserve
                 aucun autre chiffre. Le 1,99 et le 4,07 de GTA restent au § 1.2.
Placeholders   : aucun. Aucun chiffre [c2] n'est écrit dans cette section.
Left out       : rien. Les neuf paragraphes de l'anglais sont rendus en entier, citations
                 comprises et aux mêmes places.
Flags for the author :
  1. Découpage, § 2.1 premier paragraphe : l'anglais fait quatre phrases, le français cinq.
     La coupure est imposée par R1 et par la typographie française des citations. Rendue en
     une phrase, la deuxième fait 29 mots comptés par verifier_forme.py, l'espace insécable
     devant le point-virgule de « 1974 ; Ben-Akiva » valant un mot de plus qu'en anglais.
     Le rendu écrit donc « Un tel modèle donne à chaque mode une probabilité (McFadden,
     1974 ; Ben-Akiva & Lerman, 1985). Cette probabilité se calcule depuis le temps de
     trajet, le coût et les attributs du voyageur. » Les deux citations restent à leur place
     et la quatrième phrase, « Le modèle s'estime sur des enquêtes déplacements […] », garde
     Train (2009) à la sienne. C'est le seul endroit des trois rendus où la citation
     française coûte une phrase.
  2. Phrase d'ouverture de la section : « in this paper » est rendu « ici ». Le rendu
     complet, « dans cet article », porte la phrase à 26 mots et casse R1 ; la variante qui
     tenait dans 25 mots supprimait « des agents », qui est load-bearing.
  3. Phrase de tête sur GTA : l'ordre des groupes change, « est, côté évaluation, le système
     publié le plus proche », pour tenir exactement 25 mots. Le rendu direct, « est le
     système publié le plus proche du côté de l'évaluation », en fait 27. Aucun mot n'est
     perdu.
  4. Terminologie choisie ici, à suivre dans les autres rendus : « fitted references »
     (§ 2.2) → « références ajustées », mot des masters (« les quatre références tabulaires
     ajustées sur les microdonnées »), et non « références tabulaires », que la table réserve
     à « tabular references » ; « language-model module » (§ 2.2) → « module de modèle de
     langue » ; « rule-based baseline » (§ 2.2) → « référence à base de règles », mot du
     master fr/02_Related_work.md.
  5. Terminologie sous contrainte, même point qu'au § 1.2 : « modal split » est rendu « part
     modale » par la table, là où les masters écrivent « répartition modale ». La phrase
     « Aucune expérience n'y confronte une part modale simulée à une part observée » est le
     cas où la contrainte se sent le plus. Décision à confirmer par l'auteur.
  6. Problèmes de fond vus au rendu, non corrigés, et déjà au compte-rendu anglais : la
     glose de l'enquête déplacements est écrite une deuxième fois au § 2.1 après le § 1.1 ;
     la clé sprague2024cot porte 2025 quand le corps écrit 2024 ; quatre entrées de
     sample.bib (garling2003habitual, verplanken1997habit, wei2022chain, sprague2024cot)
     ont été écrites de mémoire et restent à vérifier avant soumission.
=== END SECTION REPORT ===
-->
