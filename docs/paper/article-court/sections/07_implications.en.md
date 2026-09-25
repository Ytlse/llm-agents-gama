# 7. Implications, limitations, conclusion

<!-- DERNIÈRE ÉCRITURE ANGLAISE : 2026-09-24 15:35:31 — le .tex correspondant porte cette date en en-tête tant qu'il en est le rendu fidèle. Voir sections/README.md. -->

<!-- Brouillon anglais, article court AAMAS 2027, PLAN.md § 7 — budget 550 mots
     (7.1 250, 7.2 150, 7.3 150). Rédigé le 2026-09-22 par l'agent article-writer.
     Hypothèse ticket 103 scénario 1. Les §§ 3, 4, 5 et 6 sont écrits et fixent le
     vocabulaire employé ici ; aucun terme n'est redéfini. Aucun emplacement [c2] n'est
     écrit, mais deux énoncés en dépendent, signalés au compte-rendu.
     Pas de figure de cascade, pas de part de flux, par consigne du PLAN § 7.1. -->

## 7.1 What these results say about an architecture

With the models used, the cost of one simulated day fixes where deliberation can be afforded. One weekday over
1,000 personas asks the language model 2,108 times and consumes 3 million tokens, with
memory disabled. Turning memory on adds some 2.5 million more. Scaled to the whole study
area, one simulated day would ask 2.9 million times, for 2.6 to 4.2 billion
tokens. One published answer to that cost asks the model once per behavioural archetype rather than
once per agent (Chopra et al., 2025). There, 8.4 million agents cost some 400 queries. Agents of
one archetype share an estimated probability, and each draws its own action from it. That
saving is closed to us here, since a non-tabulated event is exactly what no attribute records.

<!-- Audit des citations du 2026-09-23. Chopra et al. est paru à AAMAS 2025 (pp. 500-509),
     d'où l'année 2025 ; c'est aussi le PDF déposé. « agents with the same attributes sharing
     one answer » disait l'inverse de la source : l'approche « does not lead to a degenerate
     solution where all agents within a group make identical decisions », l'action de chaque
     agent étant tirée d'une loi de Bernoulli de probabilité estimée par archétype.
     La version publiée écrit « only 400 queries for 8.4 million agents », à 3 requêtes par
     archétype, et ne donne pas de nombre d'archétypes. Les « cent archétypes » viennent de la
     v2 HTML d'arXiv (« we initialize 100 archetypes »), que la version publiée remplace par
     « 3 … queries per archetypes » : le chiffre est retiré plutôt que cité d'une version
     qui n'est pas celle de la bibliographie. « Eight million » devient 8.4 million. -->

<!-- source: fr/08_Limitations.md § 8.3 : « une journée de semaine sur 1,000 personas produit
     3,299 déplacements […] la journée de référence en demande 2,108 [sollicitations] […] La
     journée de référence consomme ainsi 3 millions de tokens » (compteurs.json de
     l'exécution 2026-09-15_07_02_03 ; jetons agrégés par décision depuis llm_exchanges.jsonl,
     erratum de la trace du 2026-09-17 corrigé par docs/traces/2026-09-21_13-10_cout_jev_vs_gemini/).
     Mémoire active : « une journée à mémoire active ajouterait environ 2,5 millions de
     tokens » (1,25 consolidation courte et 0,27 auto-réflexion par agent et par jour, mesurées
     sur experiments/archive/2026-09-16_15_58, 5 personas et 11 jours ; rapportées aux 894
     personas mobiles). Périmètre d'enquête : « une journée simulée demanderait 2,9 millions de
     sollicitations […] et de 2,6 à 4,2 milliards de tokens » (1,320,000 habitants de 5 ans et
     plus, 3,30 déplacements par personne, une sollicitation pour 1,5 décision).
     ⚠ Réserve de la source : les grandeurs au périmètre d'enquête sont dérivées, non mesurées.
     Le mot « would » la porte ; les 2,108 sollicitations et les 3 millions de tokens, eux, sont
     mesurés. Sortent, faute de place : les 270 requêtes de la journée, les 370,000 requêtes du
     périmètre, et le mur de débit du décideur typé, qui n'accepte qu'un état par requête.
     Chopra et al. (2024) : clé BibTeX chopra2024limits, « On the limits of agency in
     agent-based models », arXiv 2409.10568. Renvoyé ici par le PLAN § 2.2, qui le sort du
     § 2.2 et lui accorde une demi-phrase au § 7. Il porte l'alternative à la division par
     régime du paragraphe suivant ; aucune de nos mesures ne la teste.
     ⚠ Demande de l'auteur, 2026-09-23 : la demi-phrase était cryptique (« shares a single
     call between behaviourally similar agents »). Le mécanisme, vérifié sur la version HTML
     du papier (arxiv.org/html/2409.10568v2), est l'ARCHÉTYPE : les agents sont groupés par
     combinaison des attributs dont dépend le comportement, le modèle est interrogé UNE FOIS
     par archétype et par action, et chaque agent tire son action dans la distribution
     obtenue. Étude de cas New York : 8,4 millions d'agents sur CENT archétypes, soit K × A
     appels au lieu de N. La troisième phrase dit pourquoi cela ne couvre pas le § 6 : la
     collapse suppose que les attributs déterminent le comportement, ce qu'un événement non
     tabulé contredit par définition. Chiffre arrondi à « eight million » dans le corps, la
     précision décimale n'ajoutant rien. -->

Our measurements suggest a division of labour by regime rather than one decision-maker
everywhere. We propose this as a possible implementation, though not yet implemented in our system. A
deterministic stage would remove the options a person cannot take, for want of a licence, of
a vehicle parked elsewhere, or of an itinerary. A machine learning model on structured data would then hold the nominal
regime. A typed classifier would rate the severity of what happens. It would also say whether the case has left that regime
(Section 6.2), and choose the itinerary once it has. The language model would receive what no variable carries and write it
into memory.

<!-- source: fr/08_Limitations.md § 8.4, premier paragraphe : « un premier étage déterministe
     élague les alternatives physiquement ou légalement impossibles, absence de permis,
     véhicule garé ailleurs, absence d'offre ; un second étage tabulaire traite les
     déplacements de routine en régime nominal […] un troisième étage n'appelle le modèle de
     langue que sur rupture ».
     ⚠ ARCHITECTURE RÉÉCRITE sur proposition de l'auteur, 2026-09-23. Le paragraphe ne
     proposait que trois étages et laissait l'étage nominal indécis (« a tabular model OR a
     typed classifier »). Il en propose désormais quatre, et donne au classifieur à sortie
     typée un rôle qu'aucune version antérieure ne lui donnait : noter la gravité de ce qui
     arrive ET dire si le cas est sorti du régime nominal, donc AIGUILLER vers le modèle de
     langue. L'étage nominal revient au modèle tabulaire seul.
     ⚠ Cohérence avec le § 6.2, vérifiée : le § 6.2 dit que le modèle de langue rend la
     gravité aujourd'hui et qu'un classifieur à sortie typée peut la rendre, la notation
     n'étant pas une génération de texte. Le § 7.1 propose donc exactement ce que le § 6.2
     ouvre. La clause « a task the language model carries today » porte la différence entre
     ce qui EST et ce qui est PROPOSÉ ; sans elle les deux sections se contrediraient.
     ⚠ Auteur, 2026-09-23, seconde passe. Deux ajouts. Le classifieur à sortie typée ne fait
     plus que noter et aiguiller : il DÉCIDE aussi l'itinéraire quand le contexte est atypique.
     Le modèle de langue ne décide donc plus rien dans cette architecture, il reçoit et il
     écrit. C'est la « seconde division du travail » du § 8.4 des masters, où le classifieur
     décide tout et le modèle de langue n'écrit que la mémoire, pour deux dollars la journée
     contre sept — montants dérivés, non mesurés, et laissés hors du corps.
     Et tout le paragraphe passe au CONDITIONNEL (« would »), à la demande de l'auteur : c'est
     une implémentation proposée, pas un dispositif. La phrase « We propose this as a possible
     implementation, though not yet implemented in our system » le dit en toutes lettres, parce
     que le seul « suggest » de la phrase d'attaque ne suffisait pas à porter quatre étages.
     Formulation de l'auteur, reprise mot pour mot le 2026-09-23.
     ⚠ Ce que la proposition n'a pas : aucune mesure. Aucun bras du banc n'a joué le
     classifieur en aiguilleur ni en décideur d'itinéraire, et la règle d'aiguillage n'est
     écrite nulle part. Ce qui la rend plausible est ailleurs : le classifieur tient la bande
     tabulaire pour un cinquantième du coût (§ 5.3), et la notation de gravité n'est pas une
     génération de texte (§ 6.2). Ni l'un ni l'autre ne la teste.
     Sort de ce paragraphe, la phrase imposée par la relecture v1 P1 (« Rating its severity
     is its task in the current design, though the traced case did not exercise it ») : sa
     réserve vit désormais au § 6.2, qui la porte avec sa raison. -->

The second stage forces a choice our measurements do not settle. A machine learning model on structured data holds both
scales, though it does not exist before the survey that fits it. The typed classifier needs
no such survey to run, and still matches, on the aggregate, the band of the machine learning models on structured
data. A survey is what
calibrates it, and without one its realism rests on weights trained elsewhere rather than on
any reading of this territory. And on individual trips it falls below the all-car floor
(Section 5.4). An architecture that placed it at the nominal stage would buy aggregate fidelity cheaply and lose individual fidelity. A decision-maker
that reads the context, needs no local survey, holds the aggregate and beats that floor does
not exist in our measurements. We do not estimate the
share of trips each stage would take.

<!-- source: fr/08_Limitations.md § 8.4, cinquième paragraphe : « un modèle tabulaire n'existe
     pas avant l'enquête qui l'ajuste ; le classifieur à sortie typée tient le régime nominal
     sans avoir lu une ligne du territoire qu'il décrit […] Deux réserves l'accompagnent : la
     mesure porte sur un seul territoire, et le § 6.4 montre que la fidélité agrégée de ce
     décideur ne se retrouve pas à l'échelle individuelle. »
     ⚠ Objection de l'auteur, 2026-09-23, portée dans le texte : « needs no such survey » était
     trop large. Le classifieur se passe d'enquête pour TOURNER — rien ne l'ajuste sur le
     territoire — mais il en faut une pour le CALER et pour savoir ce qu'il vaut : c'est
     l'enquête qui a produit la bande tabulaire à laquelle on le compare, et sans elle son
     réalisme ne repose que sur ce que ses poids ont appris ailleurs, sans aucune perception
     locale. La distinction compte pour l'architecture : l'étage nominal sans enquête n'est
     pas un étage sans enquête, il est un étage dont on ignore l'erreur.
     ⚠ Auteur, 2026-09-23, seconde passe : dire d'où viennent les poids. Le modèle est entraîné
     sur un corpus global ; rien en lui n'est ajusté aux habitudes, aux particularités ni à la
     culture d'un territoire donné. Formulation prudente à dessein — « nothing in them is
     fitted to » et non « il n'en sait rien » : un corpus global CONTIENT du texte sur
     Toulouse, ce qui n'en fait pas un ajustement. L'énoncé fort serait indéfendable en
     relecture, l'énoncé prudent tient. Chute sous le plancher tout-voiture :
     fr/99_annexes.md I.1 bis, −2,42 point [−4,26 ; −0,62], repris au § 5.4 déjà rédigé.
     Parts de flux non mesurées : même section, troisième paragraphe, « aucun compteur du
     dispositif ne sépare les décisions de routine des décisions de rupture ». Le motif sort du
     texte par la relecture v1, § 9 bis, dernière ligne ; seul le constat reste.
     ⚠ Le PLAN § 7.1 écrit « un décideur qui lise le contexte, tienne l'agrégat et batte la
     constante sur l'individu n'existe pas dans nos mesures ». Pris à la lettre, l'énoncé est
     faux : le gradient boosté lit les 21 variables, tient l'agrégat (3,60) et bat le plancher
     tout-voiture (71,5 % contre 66,7 %). La clause « needs no local survey » est ajoutée ici
     pour que l'énoncé soit vrai ; signalé au compte-rendu.
     Sort, faute de place : la seconde division du travail du § 8.4, où le classifieur décide
     tout et le modèle de langue n'écrit que la mémoire, pour deux dollars la journée contre
     sept ; ces deux montants sont dérivés et non mesurés. -->

## 7.2 Limitations

Four limitations bound what these measurements support. The machine learning models on structured data train on
39,203 survey trips the agents never read, so no result here compares two
decision-makers at equal information. What the bench establishes is narrower. A decision-maker
that reads the 21 variables alone cannot react to an event none of them carries, whatever its
accuracy. We show that an agent reacts to such an event. We do not show that it decides
better. The incident of Section 6 leaves the car usable, where a real engine failure would
immobilise it. Our research convention forbids passing on
the survey microdata, so re-estimating our machine learning models on structured data requires obtaining the survey
under the same terms. The reference itself is the fourth limitation. The survey describes one
weekday outside school holidays, collected as what respondents recall of the day before, for residents aged five and over. Nothing here therefore bears on weekends, on
holiday periods, or on trips its respondents did not report.

<!-- source, limite 1 : fr/08_Limitations.md § 8.2, dernier paragraphe des asymétries :
     « Les quatre méthodes tabulaires ont lu 39,203 déplacements réels de l'enquête locale, et
     l'agent n'en a lu aucun. […] Ce que le dispositif établit est qu'un agent fait quelque
     chose qu'un classifieur trajet par trajet ne peut pas faire, et non qu'il fasse mieux à
     information égale. » Le § 4.2 déjà rédigé déclare l'asymétrie ; la phrase ci-dessus dit ce
     qu'elle interdit de conclure, et ne la redit pas (règle 8).
     ⚠ LIMITE RETIRÉE le 2026-09-23, à la demande de l'auteur : « je ne saurais pas défendre
     ce point ». Les trois phrases sur l'indépendance des alternatives non pertinentes sortent
     du corps. Elles disaient : la règle 3 restreint la prédiction tabulaire aux modes offerts
     puis la réechelonne à 100 %, ce qui suppose que retirer un mode indisponible laisse
     inchangé le rapport entre deux modes gardés ; le logit multinomial le vérifie par
     construction, le gradient boosté, la régression logistique à noyau et la forêt aléatoire
     non ; l'erreur que l'hypothèse porte dans leurs prédictions réechelonnées n'est pas bornée.
     LE FAIT RESTE VRAI ET IL N'EST PAS PERDU : il vit dans fr/08_Limitations.md § 8.2,
     dernière phrase, et le § 4.2 de cet article décrit la règle 3 sans la commenter. Ce qui
     change est que l'article ne DÉCLARE plus cette limite. Un relecteur qui la soulève
     trouvera l'auteur sans phrase préparée ; c'est la décision de l'auteur, prise en
     connaissance de cause, et elle se réexamine à tout moment.
     source, limite 2 (clause du véhicule) : fr/07_Adaptation.md § 7.2.2, « ce qu'une avarie
     moteur ne produirait pas dans le monde réel » (ticket 079). Phrase déplacée depuis le
     § 6.3 par la relecture v1, § 9 bis, ligne 6.3, qui la veut une seule fois et ici.
     ⚠ LIMITE RETIRÉE le 2026-09-23, sur décision de l'auteur : « elle ne devrait plus exister
     dans deux ou trois jours ». La phrase disait « The non-tabulated regime is traced on one
     agent, one event and one seed, so no number of Section 6 carries an interval », et le
     [TBC] qui la suivait annonçait l'élargissement à plusieurs agents, plusieurs chocs et
     plusieurs familles d'articles. Les deux sortent ensemble : sans la limite, le marqueur
     n'annonce plus rien.
     ⚠ CE QUE CE RETRAIT ENGAGE, et c'est une échéance, pas une opinion. Le § 6 livré repose
     toujours sur une exécution unique (archive 2026-09-18_19_27, un agent, un choc) et aucun
     de ses chiffres ne porte d'intervalle. Le retrait n'est juste que si la campagne
     d'attribution élargie rend ses chiffres AVANT la soumission. Si elle glisse, l'article
     part en affirmant un parcours sur un cas sans le déclarer, ce qu'un relecteur verra au
     § 6.4 — un tableau à trois lignes et aucune dispersion. La phrase est ci-dessus, mot pour
     mot, pour être remise en dix secondes.
     source d'origine : fr/07_Adaptation.md, chapeau, « Le chapitre ne prétend à aucun réalisme
     sur l'ampleur ni sur la forme du report ».
     source, limite 3 : fr/99_annexes.md, annexe G, convention lil-1750 de
     Quetelet-Progedo-Diffusion, non-cession des microdonnées. Le § 4.1 déjà rédigé dit ce qui
     se diffuse ; la phrase ci-dessus dit ce que la non-diffusion coûte à la reproduction.
     ⚠ INCIDENT, 2026-09-23 : cette limite a été SUPPRIMÉE par erreur en réécrivant
     le paragraphe, puis restaurée mot pour mot. Elle n'a jamais quitté le .tex. Cause : le
     bloc remplacé courait jusqu'à la fin du paragraphe et la phrase suivait sans coupure de
     source, limite 4 — L'ENQUÊTE ELLE-MÊME (ajoutée le 2026-09-23 à la demande de l'auteur ;
     elle portait le rang 5 jusqu'au retrait de la limite sur l'IIA, le même jour).
     Méthodologie EMC² du Cerema, vérifiée en ligne et non reprise d'un exemple. Trois faits.
     1) Le jour décrit. Le recueil se fait du mardi au samedi, hors jours fériés et vacances
        scolaires, sur les déplacements de la veille, soit du lundi au vendredi. Donc un jour
        de semaine ouvrable, hors vacances scolaires ; le week-end est hors du tronc commun.
        https://www.cerema.fr/fr/actualites/enquetes-mobilite-certifiees-cerema-methodologie
     2) Le mode de recueil. Enquête en face-à-face ou par téléphone, sur échantillon aléatoire
        stratifié géographiquement de ménages en résidence principale : ce sont des
        déplacements DÉCLARÉS de mémoire, jamais observés ni tracés. Même source.
     3) L'âge. « La mobilité de la population résidente âgée de 5 ans et plus » ; en
        face-à-face toutes les personnes de 5 ans et plus du ménage sont interrogées, au
        téléphone une ou deux personnes sont tirées.
        https://www.cerema.fr/sites/default/files/inline-files/rapport-final-68-pages-enquete-mobilite-2023-bassin-de-vie-.pdf
     ⚠ ZERO-TRUST : ces trois faits viennent du WEB, pas du dépôt. Ils ne sont entrés ni dans
     CLAUDE.md ni dans un fichier de mémoire. À valider par l'auteur sur le guide
     méthodologique du Cerema avant soumission ; les URL sont là pour cela.
     ⚠ Ce que je n'ai PAS écrit, faute de l'avoir vérifié sur l'enquête toulousaine de 2023 :
     sa taille d'échantillon exacte en ménages et en personnes, et ses dates de terrain. Les
     ordres de grandeur trouvés en ligne portent sur d'autres territoires ; les citer ici
     serait fabriquer un chiffre. Le rapport final du Cerema cité ci-dessus les porte.
     ⚠ Pourquoi ces trois faits et pas d'autres : ce sont ceux qui bornent CE papier. Le jour
     ouvrable hors vacances dit que rien ici ne porte sur un week-end ni sur l'été — ce qui
     vaut aussi pour le régime non tabulé du § 6, dont l'enquête ne peut rien valider. Le
     caractère déclaratif dit que « fidélité à l'enquête » est fidélité à des déclarations. Le
     seuil de cinq ans borne la population décrite. Les autres limites plausibles des enquêtes
     ménages — sous-déclaration des trajets courts à pied, effet du mode de recueil — ne sont
     documentées NULLE PART dans ce que j'ai lu : elles ne sont pas écrites.
     ⚠ INCIDENT, 2026-09-23 : ce bloc de sources a été perdu une première fois, un lot
     d'écriture ayant échoué sur une autre substitution et n'ayant donc rien écrit du tout,
     corps ET commentaire. Seul le corps a été réappliqué ensuite. Rétabli ici.

     Contrôle ajouté depuis : relire le paragraphe entier après chaque réécriture de
     bloc, et non seulement la phrase visée. -->

## 7.3 Conclusion

We asked what verbalised deliberation brings to urban simulation, and where it earns its
place in a mobility agent. It does not earn that place on the ordinary day. A calibrated generative agent reaches the machine learning models on structured data, fitted on
that survey, without passing them. A typed classifier that writes no text reaches the same
band, for a fiftieth of the cost. Neither result justifies billions of tokens per simulated
day. Deliberation
earns its price on what the survey does not tabulate, and a hybrid architecture is what
confines it there. An event no variable carries enters the agent's memory and bends its
choices over time, then fades. We show through which channel, on one case traced end to end,
within a population calibrated to that survey.

<!-- source: PLAN § 0, « Ce que le papier établit, en quatre phrases », rendues dans l'ordre.
     Les quatre chiffres qui les portent vivent aux §§ 5.1, 5.3, 5.4 et 6.4 ; la conclusion
     n'en réécrit aucun, par l'exception de la règle 8 (une phrase par résultat).
     ⚠ CONCLUSION REFAITE le 2026-09-23, l'auteur la jugeant faible. Trois défauts nommés.
     « This paper establishes four things » annonçait une liste puis la déroulait : le lecteur
     comptait au lieu de lire. Les quatre résultats se suivaient sans ordre, le dernier
     (« Nothing else did that in our measurements ») tombant à plat faute d'être rattaché à ce
     qui précède. Et rien ne refermait sur le § 7.1, si bien que l'architecture proposée
     mourait deux paragraphes plus haut.
     Ce que la version actuelle fait : elle ouvre sur l'énoncé que le papier défend
     (« Aggregate fidelity does not say who should decide »), donne les quatre résultats comme
     preuves de cet énoncé, pose une charnière au milieu (« The separation appears where the
     survey stops ») et referme sur la conséquence, la division du travail par régime du
     § 7.1. Aucun chiffre nouveau, aucun résultat nouveau : la même matière, ordonnée.
     ⚠ SECONDE REFONTE, 2026-09-23, 17 h. Neuf versions ont été proposées sur trois passes ;
     l'auteur a écrit la sienne en français en croisant les versions E (le prix) et F (la
     question de départ), et ce paragraphe en est le rendu anglais. La version « Aggregate
     fidelity does not say who should decide » est abandonnée ; elle reste dans l'historique
     git de ce fichier.
     Ce que la version de l'auteur change par rapport à toutes les précédentes :
     1) La question d'ouverture est ÉLARGIE. Elle ne demande plus seulement où la délibération
        gagne sa place, mais ce qu'elle apporte à la simulation urbaine, et si elle sait lire
        des signaux absents des données tabulaires. Rendue en deux phrases, la seconde étant
        une interrogative directe — la seule du papier.
     2) Le coût devient un VERDICT et non une mesure : « Neither result justifies billions of
        tokens, nor the wait they impose. » Aucune version antérieure ne jugeait le coût.
     3) L'enquête est nommée et datée dans le corps de la conclusion.
     ⚠ TROISIÈME PASSE, 2026-09-23 18 h, sur une version réécrite par l'auteur. Quatre
     changements retenus, trois amendés.
     RETENU tel quel : « latency » remplace « the wait » (mot du domaine) ; la concession sur
       le prix passe de deux phrases à une incise, ce qui rend 16 mots ; « over time » marque
       que l'effet du § 6.4 dure (quinze jours) avant de s'éteindre.
     AMENDÉ 1 : l'auteur écrivait « even at falling prices » entre parenthèses. Virgules, et
       la raison remise en subordonnée — sans « which lower both sides of that ratio », la
       concession est une affirmation ; avec, c'est l'argument d'invariance d'échelle du
       point 4 ci-dessous, qu'un relecteur ne peut pas contester.
     AMENDÉ 2 : « Deliberation is justified because the survey does not tabulate through
       hybrid architectures » n'était pas grammaticale — elle disait que l'enquête ne tabule
       pas À TRAVERS des architectures hybrides. Deux idées télescopées. La phrase installée
       les sépare et gagne au passage la chute sur le § 7.1 qui manquait à toutes les versions
       antérieures : l'architecture hybride est ce qui CONFINE la délibération au non-tabulé.
     AMENDÉ 3, le plus important. L'auteur remplaçait la dernière phrase par « These results
       are based on a numerical study of a representative population of a large metropolis ».
       Écartée pour trois raisons. (i) Elle abandonnait le CANAL, seule contribution propre à
       ce papier (§ 6.4, une route sur quatre porte tout l'effet et la trace la nomme) ; la
       conclusion se serait refermée sur un effet constaté. (ii) « representative » est un
       terme d'enquêteur ; ce qui est démontrable, ce sont treize marges contrôlées à ±1 point
       sur 1,000 personas en 499 ménages (§ 4.1), d'où « calibrated to that survey ».
       (iii) « These results » couvre le § 6, qui repose sur UN agent et un événement — la
       limite retirée du § 7.2 le 2026-09-23 sur la foi de la campagne élargie. L'y adosser
       aurait écrit la phrase que le relecteur cite. Le compromis installé garde le canal et
       porte le périmètre en clause finale.
     4) LE PRIX QUI BAISSE, demandé le 2026-09-23 : « précise y compris si le prix baisse ».
        La clause ajoutée ne s'appuie pas sur une prévision de tarif mais sur la nature du
        chiffre. Le cinquantième du § 5.4 est un RAPPORT entre deux façons de produire la même
        bande ; une baisse du prix du jeton abaisse les deux membres et laisse le rapport
        intact. La seconde raison est la latence, qui ne dépend pas du tarif. L'argument est
        donc invariant d'échelle, ce qui est plus solide que de parier sur le prix courant.
     ⚠ TROIS POINTS À TRANCHER, chacun tenant en un mot :
     a) LA LATENCE — TRANCHÉ le 2026-09-23, la clause RESTE. J'avais signalé qu'aucune latence
        n'est mesurée dans ce papier : le seul temps chronométré est celui d'un run à UN agent
        (4,7 min par jour simulé, experiments_results.md), dont le journal dit que l'essentiel
        est du temps de simulateur et non d'attente de modèle. L'auteur répond que l'attente
        des grands modèles est de notoriété publique et garde la phrase. Ce qui la rend
        défendable sans mesure : elle ne porte AUCUN chiffre et ne dit pas « we measured » ;
        elle qualifie une conséquence du volume, et ce volume-là est dans le papier
        (2,9 millions de sollicitations pour un jour simulé, § 7.1). Si un relecteur la
        conteste, la réponse est ce chiffre, pas un chronomètre. Ne pas transformer cette
        clause en durée : le jour où elle porterait des minutes, elle deviendrait un résultat
        et exigerait une mesure de latence à l'échelle de la cohorte, que nous n'avons pas.
     b) « sans les analyser » de la version française a été rendu par « without passing them »
        (sans les DÉPASSER), qui est le résultat mesuré au § 5.1. Si l'auteur voulait dire que
        l'agent n'a pas lu l'enquête, c'est également vrai (§ 4.2, zéro déplacement lu sur
        39,203) et les deux tiennent dans une clause : « …without passing them, having read
        none of it ». Choix de l'auteur.
     c) « qui ne produit aucune donnée » a été rendu par « writes no text ». Le classifieur à
        sortie typée PRODUIT une donnée, une probabilité par option — c'est même la condition
        pour être sur ce banc (§ 3.2). Ce qu'il ne produit pas, c'est de la prose. La
        traduction littérale aurait contredit le § 4.4.
     ⚠ Ce que j'ai REMIS et que la version française laissait tomber : « then fades ».
     L'extinction est le résultat qui fait du § 6 un parcours tracé et non un simple effet
     constaté, et elle est mesurée sur deux sources indépendantes (§ 6.4). Trois mots.
     ⚠ La deuxième phrase dépend du ticket 103, lot A : elle est écrite sous le scénario 1 et
     ne porte aucun chiffre, le composite hors échantillon du classifieur restant un
     emplacement au § 5.3. Sous le scénario 3 elle sort de la conclusion. -->

<!-- source: le décideur manquant, § 7.1 ci-dessus, reformulé en une phrase ; la campagne de
     presse, fr/07_Adaptation.md § 7.3, cinq articles de la presse toulousaine et vingt signes
     préenregistrés, campagne exp_05a-e non tournée au 2026-09-22. Répétition assumée du
     dernier paragraphe du § 6.4, autorisée par la règle 8 pour la conclusion. -->

<!--
=== SECTION REPORT ===
Section        : 07 — Implications, limitations, conclusion
File           : docs/paper/article-court/sections/07_implications.en.md
Words / budget : 767 / 550 (+39.5 %) — 7.1 338/250, 7.2 231/150, 7.3 176/150.
  ⚠ R10 EN FAUTE, et c'est le seul point de cette passe que l'auteur doit trancher. La
  tolérance est de ±15 %, soit 632 mots. Les huit demandes du 2026-09-23 ajoutent 170 mots
  nets : le mécanisme de Chopra (+35), le quatrième étage d'architecture (+6), la nuance de
  calibration (+22), ce que le banc établit (+20), la règle 3 (+12), la cinquième limite sur
  l'enquête (+45), la conclusion refaite (+33). Aucune n'est retirable sans perdre ce qui a
  été demandé. Le menu de coupe, avec son coût, est au drapeau 6.
Skeleton       :
  The ordinary day and the traced event bear on how a mobility agent should be built, and on
  what we cannot claim.
  The cost of one simulated day fixes where deliberation can be afforded.
  Our measurements suggest a division of labour by regime rather than one decision-maker
  everywhere.
  The second stage forces a choice our measurements do not settle.
  Four limitations bound what these measurements support.
  We asked what verbalised deliberation brings to urban simulation, and where it earns its
  place in a mobility agent.
  Two things stay open.
Checker        : verifier_forme.py — « Aucune consigne mécanique en faute » après la seconde
  passe G3 du 2026-09-22. --squelette lu d'une traite : les sept phrases-sujets racontent la
  section. G3 : cinq coordinations relevées, trois rompues — « …in the current design, though
  the traced case did not exercise it » (concessive), « …lets it fade. Nothing else did that
  in our measurements. » (deux phrases) et, pour la phrase nommée par l'auteur, « We hand on
  the search for the missing decision-maker, one that would hold both scales without a local
  survey. » Restent la phrase d'ouverture de la section, dont les deux membres coordonnent
  deux compléments, et la troisième phrase de la conclusion.
Terms defined here     : aucun. Tous les termes employés (décideur, plancher tout-voiture,
  composite, classifieur à sortie typée, régime nominal, événement non tabulé) sont définis
  aux §§ 1, 3, 4, 5 et 6. Aucune glose n'est plus portée ici : celle de
  l'indépendance des alternatives non pertinentes est sortie du corps avec sa limite, le
  2026-09-23.
Terms used, undefined upstream : aucun.
Figures cited  :
  2,108 sollicitations et 3 millions de tokens — fr/08_Limitations.md § 8.3 — mesurés.
  2,5 millions de tokens supplémentaires — même source — dérivés de 5 personas sur 11 jours.
  453 communes, 2,9 millions de sollicitations, 2,6 à 4,2 milliards de tokens — même source —
    ⚠ dérivés, non mesurés ; le mot « would » porte la réserve dans la phrase.
  39,203 déplacements d'enquête — fr/08_Limitations.md § 8.2 — mesuré, repris du § 4.2.
  Chute sous le plancher tout-voiture (§ 5.4) — fr/99_annexes.md I.1 bis — mesuré en
    échantillon pour le prompt expert du classifieur (réserve portée par le § 5.4).
Placeholders   : aucun. Le [TBC] du § 7.2 est parti le 2026-09-23 avec la limite qu'il
  annonçait. Aucun [c2] écrit. Deux énoncés
  dépendent du ticket 103 :
  la deuxième phrase de la conclusion (scénario 1 supposé ; elle sort sous le scénario 3) ;
  le § 7.2, qui recevra la phrase P2 sur ce que couvrent les trois graines du § 5 après le
  lot B. P2 n'est pas appliqué à ce stade, par consigne.
Left out       : la figure de cascade et les parts de flux par étage (PLAN § 7.1, consigne
  explicite) ; la seconde division du travail du § 8.4 (deux dollars la journée contre sept),
  montants dérivés et sans place ; le mur de débit du décideur typé.
Author's requests applied, 2026-09-23 (huit points) :
  A. Chopra et al. (2024) expliqué : l'archétype, une interrogation par combinaison
     d'attributs et non par agent, 8,4 millions d'agents sur cent archétypes. Vérifié sur la
     version HTML du papier, pas sur le résumé. Une troisième phrase dit pourquoi le procédé
     ne couvre pas le § 6.
  B. Architecture réécrite sur la proposition de l'auteur : quatre étages, l'étage nominal
     revenant au modèle tabulaire seul et le classifieur à sortie typée recevant la notation
     de gravité ET l'aiguillage hors régime nominal. Voir le commentaire du paragraphe pour
     la cohérence avec le § 6.2, qui ouvre exactement cela.
  C. « needs no such survey » corrigé : le classifieur s'en passe pour TOURNER, pas pour être
     CALÉ. Sans enquête locale, son réalisme ne tient qu'à ce que ses poids ont appris
     ailleurs, sans perception du territoire.
  D. « Our bench establishes what a trip-by-trip classifier cannot do » remplacé : le raccourci
     nommait une catégorie que l'article n'avait pas définie. La phrase dit maintenant ce
     qu'elle voulait dire — un décideur qui ne lit que les 21 variables ne peut pas réagir à
     un événement qu'aucune ne porte, quelle que soit sa précision.
  E. Règle 3 explicitée avant son hypothèse : ce que la règle FAIT (restreindre puis
     réechelonner à 100 %) précède ce qu'elle SUPPOSE. Le logit multinomial est nommé comme
     celui qui satisfait l'hypothèse par construction, là où le texte disait « trois sur
     quatre ne la garantissent pas » sans dire qui était le quatrième.
  F. Le régime tracé au § 6 est nommé « the non-tabulated regime », le titre même du § 6, et
     la limite d'un agent / un événement / une graine est suivie d'un [TBC] qui annonce
     plusieurs agents, plusieurs chocs et plusieurs familles d'articles.
  G. Cinquième limite ajoutée, l'enquête de référence elle-même. Trois faits vérifiés en
     ligne sur les pages du Cerema, avec leurs URL dans le commentaire de source, et une
     réserve zero-trust : ils n'entrent dans aucun fichier de mémoire et restent à valider
     par l'auteur sur le guide méthodologique.
  H. Conclusion refaite. Voir le commentaire du § 7.3 : le défaut n'était pas la matière mais
     l'ordre, et l'absence de chute sur le § 7.1.

Flags for the author :
  1. NON TRANCHÉ, à reconfirmer. Le PLAN § 7.1 écrit « un décideur qui lise le contexte,
     tienne l'agrégat et batte la constante sur l'individu n'existe pas dans nos mesures ».
     Pris à la lettre l'énoncé est faux : le gradient boosté lit les 21 variables, tient
     l'agrégat (3,60) et bat le plancher tout-voiture (71,5 % contre 66,7 %). La clause
     « needs no local survey » a été ajoutée pour rendre l'énoncé vrai. La relecture v1 n'a
     pas statué ; la clause reste dans le texte, non confirmée par l'auteur.
  2. Chopra et al. (2024) est ajouté au premier paragraphe du § 7.1, par le PLAN § 2.2 qui
     lui réserve une demi-phrase au § 7. Il y gagne sa place comme réponse concurrente au
     même coût d'inférence : partager un appel entre agents proches, là où nos mesures
     suggèrent de diviser par régime. Aucune de nos mesures ne compare les deux.
  3. « in the current design » subsiste ici par la formulation imposée en P1, alors que le
     § 9 bis le retire du § 6.2. Cohérence à vérifier à la relecture d'ensemble.
  4. La phrase sur l'avarie moteur qui n'immobilise pas le véhicule est reprise du § 6.3 ;
     elle doit disparaître de ce § 6.3, sans quoi la règle 8 est en faute.
  5. Le § 7.2 dit que la section 6 ne porte aucun intervalle. Ce constat est de l'agent
     rédacteur sur la section livrée, non une phrase des masters.
  6. R10 EN FAUTE : 767 mots contre 632 tolérés. Menu de coupe, du moins coûteux au plus
     coûteux, avec ce que chaque ligne rend :
     — le second paragraphe du § 7.3 (« Two things stay open… »), 39 mots. C'est la coupe la
       plus sûre : le décideur manquant est déjà dans la conclusion refaite, et la campagne de
       presse est déjà au dernier paragraphe du § 6.4, en gras. Doublon net.
     — « This paper leaves the problem open. We do not estimate the share of trips each stage
       would take. », 21 mots. La première phrase ne dit rien que le paragraphe n'ait dit ; la
       seconde est un non-résultat.
     — la mise à l'échelle des 453 communes, 23 mots. Ce sont les seules grandeurs DÉRIVÉES du
       § 7.1 ; les 2,108 sollicitations et les 3 millions de jetons, eux, sont mesurés et
       suffisent à l'argument du coût.
     — la troisième phrase sur Chopra, 19 mots. Elle explique pourquoi l'archétype ne couvre
       pas le § 6 ; sans elle la citation redevient une demi-phrase sans portée.
     Les quatre ensemble rendent 102 mots et laissent 665, encore au-dessus de 632. Atteindre
     la tolérance demande d'entamer une des huit demandes du jour, ce que je ne fais pas sans
     décision de l'auteur. Rappel du contexte : le papier compile en 10 pages pour 8.
=== FIN DU COMPTE-RENDU ===
-->
