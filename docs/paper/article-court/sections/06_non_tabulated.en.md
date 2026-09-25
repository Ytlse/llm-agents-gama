# 6. Beyond the survey: one event traced to the decision

<!-- DERNIÈRE ÉCRITURE ANGLAISE : 2026-09-25 21:07:15 — le .tex correspondant porte cette date en en-tête tant qu'il en est le rendu fidèle. Voir sections/README.md. -->

<!-- Relecture des gallicismes du 2026-09-25, accord de l'auteur (« Corrige ») : tics récurrents (« against » comparatif, « one » pour « un même », « carry », « bound », « under » devant un seuil, « rejoin », « from one X to another », « execute », « brings »), faux-amis (agenda, control, hypothesis, legibility, designate, demanding, chain, globally, bends, recedes), calques de construction et typographie à la française (« 0.9 point », « [a ; b] », « 30.3 % », « 1.06 dollars »). Aucun chiffre ne change ; les prompts et le message de l'annexe D ne sont pas touchés. -->

<!-- Passe de lisibilité du 2026-09-25, à la demande de l'auteur (même exercice qu'au § 5) :
     la propension quotidienne est définie en une incise (source : moves.csv, colonne
     P(Voiture Privée) %, moyenne quotidienne) ; « oscillates between 5 and 52 % » et la bande
     témoin « 65 to 90 % » quittent la prose, la figure 5 les porte ; « during the period »
     devient « after the failure (Table 4) », les douze trajets étant les 12/38 du tableau ;
     « stays at 3 throughout » est remplacé par « does not move », pour ne pas confondre avec
     le 3 de la sécurité. Aucun chiffre ajouté. -->

<!-- Brouillon anglais, article court AAMAS 2027, PLAN.md § 6 — budget 750 mots.
     Rédigé le 2026-09-22 par l'agent article-writer. Hypothèse ticket 103 scénario 1 ;
     le ticket 103 ne touche aucun chiffre de cette section, qui ne porte donc aucun
     emplacement [c2]. Les §§ 4 et 5 sont écrits et fixent le vocabulaire employé ici.
     ⚠ Le master fr/07_Adaptation.md est un brouillon v2.3 dont le § 7.1 décrit la
     conception arrêtée au ticket 100, sans code au 22 septembre. Les phrases qui en
     viennent sont écrites ici comme conception, jamais comme mesure. Détail au
     compte-rendu. -->

This section follows one off-survey event, an engine failure, from its entry into memory to
the decisions of the days after.

## 6.1 What the 21 variables do not record

None of the 21 variables records what a person went through yesterday, or what they read
this morning. A decision-maker restricted to these inputs therefore returns, on the morning
after an incident, exactly the prediction of the day before. This holds by construction, so
there is nothing to measure.

<!-- source: fr/07_Adaptation.md, chapeau : « Aucune ne porte le vécu de la personne […]
     Un décideur qui ne reçoit que ces 21 entrées ne peut répondre à rien d'autre » ;
     § 7.2.1 pour l'écart nul par identité et l'absence de comparateur jouable. -->

## 6.2 The mechanism

An event enters the agent's memory at one of two moments. An event the agent experiences enters after the trip that produced it, and an event it reads enters when the agent wakes up. On entry, the agent rates the event on a five-point severity scale, and gives it a valence (negative or positive). The
rating is the agent's own, read against its profile, so the same incident can weigh differently on two agents. The severity alone sets how long the memory stays in the recent-events block, by the rule of
Section 3.3.

<!-- Relecture éditoriale du 2026-09-25, accord de l'auteur (point B4) : « its 2.8-day time
     constant » laissait le lecteur hésiter entre la décroissance des traces et celle du bloc
     des changements. La règle du bloc est désormais écrite au § 3.3 (seuil d'entrée 0,7,
     poids servi au-dessus de 0,35, une quinzaine de jours à 0,7) ; la phrase y renvoie. -->

<!-- ⚠ Remarque de relecture n° 5, point E, 2026-09-23 : la durée de service dépendait de la
     gravité sans que la règle soit dite, et le « quinzième jour » du § 6.4 ne se reliait à
     rien. Règle servie : force = min(S0 × (1 + k × gravité), 30), S0 = 2,8 j, k = 6
     (llm/gravite.py:333-343, settings.py memoire__force_k_importance) ; durée de service =
     force × 1,0498. Gravité du run 0,700 → force 14,56 j → 15,29 j servis
     (experiments_results.md, entrée des durées dérivées). Le facteur 6 n'est pas écrit :
     choix de conception, déclaré comme tel au § 3.3, non défendu (décision de l'auteur). -->

<!-- source: fr/07_Adaptation.md § 7.1 : deux prises (après un déplacement, au réveil),
     estimation d'importance et de valence à l'entrée, « cette estimation, et elle seule,
     fixe la gravité de l'entrée » (llm/gravite.py, cinq intensités ; ticket 100, D3, D4 et
     D7 du 2026-09-22, qui retire le plancher par le fait mesuré).
     ⚠ Correction de l'auteur, 2026-09-23 : la gravité est l'estimation de l'AGENT, et la
     phrase doit dire d'où elle vient. Les cinq échelons sont ancrés par une conséquence
     observable (llm/gravite.py, NIVEAUX et ANCRES, de « anodin » 0,10 à « marquant » 1,00) ;
     l'appel de jugement reçoit le récit d'identité de l'agent comme perception
     (urban_mobility_agents/simulation_controller.py:1638, qui passe
     get_person_identity_description(person) à llm/evenements/jugement.py:juger), d'où
     « read against its profile ». « Profile » est le mot déjà posé au § 3.2 (« a short
     profile of the person and household ») : aucun terme nouveau n'entre (R12).
     La réserve « la campagne rapportée est antérieure à la décision D4 » ne disparaît pas,
     elle passe au § 6.3 sous la forme d'une anticipation marquée [TBC], par consigne de
     l'auteur du 2026-09-23. Elle est vérifiée en run réel : experiments_results.md,
     « 2026-09-23 — Campagne c3 (v3) », où importance_retenue vaut la gravité jugée par
     l'agent (0,75) et non le fait mesuré (0,8667). -->

<!-- source: fr/07_Adaptation.md § 7.1, récit du soir et saut unique (ticket 100, D1 et D2,
     champ de provenance distinguant une croyance entendue d'une croyance vécue).
     Relecture v1, N1 : la description de conception (récit du soir, entrée dans la réflexion
     des auditeurs) vit désormais au § 3.3 (item T2) ; il ne reste ici que l'existence du saut
     et le fait qu'il n'est pas exercé.
     ⚠ Aucun code au 22 septembre : la note de travail du master interdit de passer ce
     passage au passé avant le lot 4 du ticket 100 et une campagne jouée. Écrit ici au
     présent de conception, et borné par la dernière phrase. -->

The effect of an event on later decisions can end in two ways, and our measurements
distinguish them. It ends by contradiction when the agent makes the same trip again and the
incident does not recur. It ends by expiry when the memory leaves the prompt.

<!-- source: fr/07_Adaptation.md § 7.1, troisième paragraphe : extinction par contradiction
     ou par usure, « et elles se distinguent à la mesure ». La prédiction stratifiée du
     master (contradiction datée chez ceux qui continuent d'utiliser le mode) n'est pas
     reprise : elle n'est pas mesurée sur le cas tracé. -->

<!-- Relecture éditoriale du 2026-09-25, accord de l'auteur (« Corrige », point C2) : le
     paragraphe « The language model does two kinds of work in this mechanism » était une
     digression prospective au milieu de la description du mécanisme. Il passe au § 7.1, à
     la suite de l'architecture à deux étages qu'il prolonge, avec ses commentaires. -->

## 6.3 The setup

We simulate the same agent **[TBC — persona and models]** twice, once exposed to an incident
and once as a control, and measure the difference between the two runs. The incident is an engine
failure that imposes a half-hour delay on a car trip. It falls on 30 March, the fifteenth
simulated day. Unlike the benchmark runs (Section 4.1), both runs keep memory enabled and last
several weeks. The car remains offered the next
morning, so what we measure here is a choice. **[TBC — A campaign now under way]**

<!-- source: fr/07_Adaptation.md § 7.2.2 : un agent joué deux fois, avarie moteur,
     « le véhicule reste offert le lendemain, ce qui est la condition
     pour mesurer un arbitrage plutôt qu'une contrainte, et ce qu'une avarie moteur ne
     produirait pas dans le monde réel » (ticket 079). Relecture v1, § 9 bis : la phrase sur
     l'immobilisation réelle du véhicule est une limite et part au § 7.2 (agent voisin) ; la
     clause « mémoire désactivée sur le banc » est dite une fois au § 3.3 et n'est plus
     répétée ici.
     ⚠ CORRECTION DE FAIT, 2026-09-23. « then a smaller delay the next day » est SUPPRIMÉ :
     ce second retard n'a jamais été joué. experiments/archive/2026-09-18_19_27/chocs.jsonl ne
     contient que le jour 15 ; le jour 16 est déclaré dans c6_voiture_suspecte.yaml et ne
     s'est pas appliqué. Relevé n° 1 de docs/paper/NOTE_AU_REDACTEUR.md, recoupé dans
     experiments_results.md, « 2026-09-23 — Relecture de la campagne c6 ». Le master de
     l'article long porte encore l'erreur ; il est verrouillé, la note la porte pour lui.
     « half-hour » remplace le chiffre nu : retard_injecte_s = 1800 dans l'archive.
     ⚠ Auteur, 2026-09-23, seconde passe. Deux coupes dans ce paragraphe. « and not a
     constraint » sort : le contraste était une défense contre une objection non formulée, et
     « what we measure HERE is an arbitration » dit la même chose en affirmant. La phrase
     d'anticipation sort du corps et ne laisse que son marqueur, « [TBC — A campaign now under
     way] », formulé par l'auteur : tant que le rejeu n'a pas tourné, la campagne est une note
     de travail et non une phrase d'article.
     ⚠ Ce que le [TBC] annonce : la campagne d'attribution c3 (bras exposé et bras témoin,
     experiments/runs/e_c3_attribution_861500_v4) rejoue le dispositif sous
     « jugement: a_l_injection », donc avec la gravité estimée par l'agent. Deux choses ont
     bougé depuis l'archive citée : c6_voiture_suspecte.yaml déclare aujourd'hui retard_min 45
     et non 30, et le régime de saturation est passé de « palier » à « asymptote » le
     2026-09-21. Rejoué depuis le dépôt d'aujourd'hui, le cas rend 0,6427 et 14,27 jours au
     lieu de 0,700 et 15,29 — d'où le gras sur la durée et sur les deux chiffres qui en
     dépendent. Relevé n° 2 de NOTE_AU_REDACTEUR.md. -->

Opinions are collected every simulated evening, independently of any decision. The agent rates each
mode out of ten on six items: comfort, cost, environment, practicality, speed and safety. The
environment item, which no incident targets, serves as the control question.

<!-- 2026-09-25, décision de l'auteur : le questionnaire passe à une passation QUOTIDIENNE,
     texte écrit par anticipation du run qui la jouera. Côté code : jalons déclarés par
     EXPERIMENT_SURVEY_DAYS (tous les jours du run), passation à 21 h (HEURE_ENQUETE_H),
     cinq prompts par passation, un par mode et un de priorités
     (urban_mobility_agents/enquetes.py). Les quatre jalons du run mesuré (27 mars, 1er avril,
     15 avril, 24 avril) sortent du corps ; le commentaire qui suit les documente. -->

<!-- Relecture éditoriale du 2026-09-25 : dates, items et échelle ajoutés pour que le tableau 4
     et la figure 5 se lisent. Jour 15 = 30 mars : chocs.jsonl, un seul jour injecté, et
     commentaires du § 0. Items : fr/07_Adaptation.md § 7.2.3 (sécurité, praticité, confort,
     rapidité, coût, écologie), échelle 0-10. Jalons : configuration d'enquête du run que lit
     scripts/analysis/ch7_choc_figures.py l. 26 (exposé experiments/archive/2026-09-21_15_13,
     témoin 2026-09-21_11_11).
     ⚠ [TBC] À TRANCHER PAR L'AUTEUR : ce script lit un autre run que celui que cite le
     commentaire du § 6.3 (experiments/archive/2026-09-18_19_27). Selon identite_run.json des
     runs du script, persona 861500 (58 ans, cadre à temps plein, ménage de deux, deux
     voitures), décisions par gemini-3.1-flash-lite sous prompt_expert_05, mémoire et enquête
     par gemini-3.5-flash-lite, 16 mars → 27 avril. Le run du 18 septembre porte un autre
     persona (899549), des modèles groq et quatre injections. Les dates de jalons sont à
     confirmer sur le run qui fait foi. -->

<!-- source: fr/07_Adaptation.md § 7.2.3 : affinites_declarees.csv, échelle de Likert 0-10,
     critères d'Adam & Gaudou (2025), un questionnaire par mode, jalons aux jours 12, 17,
     31 et 40. -->

## 6.4 Results

Although the car is offered as often as before the failure, it is taken far less often. The
exposed agent takes it nine times out of ten before the failure, and three times out of ten after.
The control agent holds its rate throughout.

*Table 4. Car taken when the car is offered, exposed and control agent. The periods split at
the failure (30 March) and at the recovery of the car propensity (15 April).*

| Period | Exposed agent | Control agent |
|---|---:|---:|
| Before the failure | 94% (34/36) | 90% (28/31) |
| After the failure | 32% (12/38) | 92% (45/49) |
| After the recovery | 88% (35/40) | 87% (40/46) |

<!-- Relecture éditoriale du 2026-09-25 : « After the return » devient « After the recovery »,
     et la légende date les coupures. ⚠ Aucune source ne date les périodes. Recomptage : les
     coupures après le trajet de 05:42 du 30 mars et au 14/15 avril redonnent la colonne de
     l'agent exposé, pas celle du témoin (28/31, 46/51, 39/44 au lieu de 45/49 et 40/46).
     À vérifier par l'auteur. -->

<!-- source: fr/07_Adaptation.md § 7.2.3, premier paragraphe : moves.csv des deux exécutions,
     colonne « Modes proposés au LLM », décisions du modèle seules. Fractions du master
     reprises telles quelles, converties en pourcentages par consigne R13. ⚠ Le master ne
     date pas les trois fenêtres : il écrit « avant l'incident », « ensuite », « puis ». Les
     trois libellés de période sont écrits ici, la troisième fenêtre étant rapprochée du
     retour daté du 15 avril. À faire confirmer.
     Relecture v1, N2 : tableau numéroté « Table 4 » par cohérence avec les trois autres. Si
     la compilation (G4) dépasse 8 pages, il redevient une phrase, déjà rédigée : « The car is
     taken on 94 %, 32 % then 88 % of the trips where it is offered, against 90, 92 and 87 %
     for the control agent. » -->

The daily car propensity is the probability the model gives the car, averaged over the day's
decisions. It falls on the day of the failure and recovers **fifteen days** later (Figure 5).
It drops from 90% the day before to 40% that day, and stays below the range of the control agent until it returns to it.

<!-- source: fr/07_Adaptation.md § 7.2.3 et figure 7.1 : moves.csv, colonne
     P(Voiture Privée) %, moyenne quotidienne des décisions du jour, aucun découpage en
     phases. -->

*Figure 5. The effect lasts as long as the memory stays in the prompt.*

<!-- ⚠ Relecture de l'auteur, 2026-09-25 : paragraphe jugé inutile et retiré du corps. Il
     disait : « The four blocks by which the past reaches a decision can be told apart, and the
     trace names the one that carried this effect. The account of the failure appears in the
     block of what has changed recently, in 75 of 376 decision prompts. It stays there from the
     day of the failure to the fifteenth day after. That span follows from the severity. [TBC —
     The campaign under way reads what the three other blocks carry.] » Ses sources restent
     ci-dessous pour mémoire.
     source: fr/07_Adaptation.md § 7.2.1 : llm_exchanges.jsonl, 75 prompts sur 376 ;
     trace_rappel.jsonl, aucune occurrence parmi les souvenirs servis ; llm/noyau.py,
     bloc_connaissances et duree_service_jours, 15,29 jours pour une gravité de 0,70, valeur
     écrite avant l'exécution (specs/ticket_095/tests.md) ; sélection par confiance puis
     nombre d'observations, six croyances retenues. Les quatre voies sont celles du § 3.4 des
     masters ; le § 3 de l'article court les nomme.
     ⚠ Consigne de l'auteur, 2026-09-23 : ne pas écrire l'état courant comme un constat
     d'absence. Les deux phrases retirées disaient « Recall by similarity never brought the
     memory back, and the belief drawn by the evening consolidation reached no prompt ». Ce
     que la mesure dit est conservé — une seule voie a porté l'effet — mais écrit par ce
     qu'elle établit, et la suite est annoncée. Le fait retiré du corps, pour mémoire : sur
     cette exécution, trace_rappel.jsonl ne porte aucune occurrence du souvenir parmi ceux
     servis, et la croyance née de l'événement, seule observation à son actif, ne passe pas
     la sélection à six classée par confiance puis par nombre d'observations. Ce n'est pas un
     défaut du dispositif, c'est ce que la sélection fait d'un événement unique.
     ⚠ Ce qui est en gras, et ce qui ne l'est pas. Le gras marque ce qui n'est pas encore
     acquis, et rien d'autre : la durée de quinze jours, que le dépôt d'aujourd'hui rendrait à
     14,27 jours (NOTE_AU_REDACTEUR.md, relevé n° 2), et le paragraphe entier de la seconde
     expérience, dont aucune mesure n'existe. 75 sur 376 N'EST PAS en gras : il est vérifié et
     insensible au nombre d'injections du jour, le bloc étant journalier (« Vérifié et indemne
     au 2026-09-23 »), comme les comptes du tableau 4. Un gras qui couvrirait toute la section
     ne dirait plus rien à l'auteur.
     ⚠ Auteur, 2026-09-23, seconde passe : « not from a number set by hand » sort. La phrase
     se défendait contre l'idée qu'on aurait posé quinze jours à la main ; « That span follows
     from the severity » suffit. Et la dernière phrase passe en marqueur [TBC], comme au
     § 6.3 : ce que la campagne lira n'est pas encore un résultat. -->

Our measurements separate the two ways an effect can end, and this one ended by expiry. The
agent took the car twelve times after the failure (Table 4), twelve occasions for
contradiction. **[TBC — at this time, no contradiction of the belief born of the
failure. Add an experiment?]** The memory of the failure leaves the decision prompts after
13 April, and the propensity returns to the control band on 15 April.

<!-- source: fr/07_Adaptation.md § 7.2.3, troisième et quatrième paragraphes :
     agent_memory_events.jsonl de l'exécution exposée, zéro contradiction de concept ;
     llm_exchanges.jsonl, dernière occurrence du récit ; moves.csv pour le retour.
     ⚠ Réserve du master, note de travail : le « zéro contradiction » vient du ticket 095 § 1
     (campagne du 077) et reste à recouper sur l'archive 2026-09-21 qui produit les autres
     chiffres. C'est ce qui lui vaut le gras : la campagne d'attribution le rendra sur la même
     exécution que le reste.
     ⚠ Auteur, 2026-09-23, seconde passe : le « zéro contradiction » quitte le gras pour un
     marqueur, « [TBC — at this time, no contradiction of the belief born of the failure. Add
     an experiment?] », formulé par l'auteur. Le gras en faisait un résultat provisoire ; le
     marqueur en fait ce qu'il est, un constat daté assorti d'une décision à prendre — ouvrir
     ou non un bras qui mette une croyance SERVIE en position d'être démentie. La réserve
     UNRULED du drapeau 1 ci-dessous est la même question, vue depuis la provenance du chiffre.
     ⚠ Consigne de l'auteur, 2026-09-23 : la phrase « The belief born of the failure was never
     served, so nothing contradicted it » est retirée du corps. Elle expliquait le zéro par
     une absence, ce qui le vide de sa portée avant même qu'il soit recoupé. Le fait tient et
     vit ici : la croyance née de l'avarie n'a pas atteint les prompts de décision, faute
     d'observations en nombre. Ce que la campagne d'attribution doit établir est si une
     croyance SERVIE se fait démentir — c'est la prédiction stratifiée du master (§ 7.1),
     laissée hors du corps faute de mesure. -->

Stated opinions drop after the failure and come back **[TBC after the daily run]**. On the
car, **[n]** of the six items fall after the failure, and safety drops the most, by **[k]**
points. Each item's daily series shows the day it regains its starting value, which can be
set against the day the propensity returns to the control band. The environment item, the
control question, does not move, and the control agent's ratings of the car do not change on
any of the six items. Both
agents drift on the four other modes without a common pattern, leaving the car as the only
mode that separates them.

<!-- 2026-09-25, questionnaire quotidien anticipé : tout ce paragraphe attend le run qui le
     jouera, d'où le [TBC] en tête ; la phrase témoin et celle des quatre autres modes gardent
     le constat des quatre jalons tant qu'il n'est pas remesuré. Valeurs du run à quatre jalons,
     pour mémoire : cinq critères sur six baissent au jalon suivant l'avarie, sécurité 8 → 3,
     et les cinq ont retrouvé leur valeur de départ aux deux jalons suivants. La passation
     quotidienne lève la réserve du master ci-dessous : la dynamique entre deux jalons devient
     observable. -->

<!-- source: fr/07_Adaptation.md § 7.2.3, cinquième et sixième paragraphes : sécurité 8 → 3,
     praticité 9 → 6, confort 8 → 5, rapidité 9 → 8, coût 6 → 5 ; écologie à 3 aux quatre
     jalons ; dix-neuf des trente séries dérivent chez l'exposé, seize chez le témoin. Deux
     critères sur cinq sont cités, faute de place. ⚠ Le master note que la dynamique entre le
     deuxième et le troisième jalon n'est pas observée, et que cet intervalle est celui où le
     récit quitte le contexte. -->

**A second experiment extends the same channel to information that is only read. Now under
way, it presents five dated Toulouse press articles and tests twenty predictions of the sign
of their effect, written down before any call to the model (Appendix E).**

<!-- source: fr/07_Adaptation.md § 7.3 : cinq articles de la presse toulousaine, conditions
     C1 à C3, vingt signes préenregistrés (figure 7.3). Deux phrases et aucun chiffre de
     résultat, par consigne du PLAN § 6.4 ; la campagne exp_05a-e n'a pas tourné.
     ⚠ Auteur, 2026-09-23 : le paragraphe passe EN ENTIER au gras. C'est le seul du chapitre
     dont rien n'est mesuré — le dispositif est écrit, la campagne annoncée, aucun chiffre ne
     tombe. Le gras dit donc ici ce qu'il dit ailleurs, à l'échelle du paragraphe au lieu du
     chiffre : à confirmer par une exécution. -->

The channel traced here rests on one agent and one event. We therefore claim that this
channel exists, not how strong its effect is.

<!-- ⚠ Auteur, 2026-09-23 : la phrase de transition vers le § 7 est SUPPRIMÉE (« The next
     section reads these measurements, together with those of the ordinary day, for what they
     imply about where deliberation belongs »). Le chapitre se referme sur sa portée. Si le
     § 7 comptait sur cette annonce pour son attaque, c'est à lui de la porter — vérifié :
     07_implications.en.md ouvre sur son propre énoncé et ne renvoie pas en arrière. -->

<!--
=== SECTION REPORT ===
Section        : 06 — The non-tabulated regime: a single-agent event traced to the decision
File           : docs/paper/article-court/sections/06_non_tabulated.en.md
Words / budget : 796 / 750 (+6.1 %)
Skeleton       :
  The household travel survey tabulates one ordinary day and no other.
  None of the 21 variables records what a person went through yesterday, or what they read this morning.
  An event enters the agent's memory at one of two moments.
  A rated event travels beyond its owner, through the household in the evening.
  An effect ends in one of two ways, which measurement tells apart.
  Two links of this chain are text generation.
  We play one agent twice, exposed and control, and read the gap between the two runs.
  Opinions are collected outside any decision, on six declared criteria, at four milestones.
  Although the car is offered as often as before the failure, it stops being taken.
  The daily propensity to the car falls on the day of the failure and returns fifteen days later (Figure 5).
  Measurement separates the two ways an effect can end, and this one ended by wear.
  Declared opinions drop after the failure and come back.
  A second experiment carries the same channel to information that is only read. (en gras)
  The path traced here rests on one agent and one event.
Checker        : aucune consigne mécanique en faute après la seconde passe G3 du 2026-09-22
                 (R1, R2, R5, R9, R11, R14 : rien ; verifier_forme.py sort 0).
                 G1 vérifié sur ce fichier : aucun séparateur de milliers à l'espace.
                 G3 : dix coordinations à queue courte relevées, huit rompues — la phrase
                 d'ouverture (virgule retirée), « …suffered or welcome. The severity alone
                 sets… » (deux phrases), « …in one of two ways, which measurement tells
                 apart » (relative), « …return both, though no experiment here tested it »
                 (concessive), « …during the period, with no belief contradiction recorded »
                 (participiale), « …without a common pattern, leaving the car as the only
                 mode… » (participiale), « Now under way, it serves five dated Toulouse press articles… »
                 (antéposition, item nommé par l'auteur) et « …one agent and one event. We
                 claim the path… » (deux phrases). Restent les coordinations qui apparient
                 deux faits parallèles, notamment les deux dates du 13 et du 15 avril.
Terms defined here     : severity and valence at entry ; extinction by contradiction and
                 by wear ; the exposed / control pair ; the control question on the
                 environment criterion.
Terms used, undefined upstream : none. The four prompt blocks, the recently-changed block,
                 recall by similarity, belief and evening consolidation come from § 3.3 ;
                 probability mass and the vehicle chain from § 3.2 and § 3.4 ; the 21
                 variables and the bench from § 4.
Figures cited  : 94 / 32 / 88 % and 90 / 92 / 87 % (Table 4) — fr/07_Adaptation.md § 7.2.3,
                 moves.csv of the two runs — period labels written here, third window tied
                 to the dated return of 15 April, to be confirmed.
                 90 % → 40 %, then 5 to 52 %, control band 65 to 90 %, return 15 April
                 (Figure 5) — fr/07_Adaptation.md § 7.2.3 and figure 7.1 — daily mean, no
                 phase cutting in the source.
                 Twelve car trips, zero belief contradiction — agent_memory_events.jsonl —
                 RESERVATION, see flags.
                 Safety 8 → 3 on a scale of ten, environment at 3 at the four milestones —
                 fr/07_Adaptation.md § 7.2.3 — two of five falling criteria cited, for space.
                 Five press articles, twenty signs — fr/07_Adaptation.md § 7.3 — campaign
                 running, no result figure by PLAN § 6.4.
Placeholders   : two [TBC] markers, both worded by the author on 2026-09-23 — "A campaign
                 now under way" (§ 6.3) and "at this time, no contradiction of the belief born
                 of the failure. Add an experiment?" (§ 6.4). The third, "The campaign under
                 way reads what the three other blocks carry", left with its paragraph on
                 2026-09-25. Two bold spans remain, and they
                 mark what is not yet acquired: the fifteen-day duration, twice, and the whole
                 second-experiment paragraph, of which nothing is measured.
                 Ticket 103 touches no figure of this section.
Left out       : the master's stratified prediction on dated contradiction (not measured on
                 the traced case) ; the drift counts on the four other modes (19 of 30 series
                 exposed, 16 control) ; three of the five falling car criteria.
Author's instructions applied, 2026-09-23 :
  A. § 6.2 now says WHERE the severity comes from: the agent rates it itself, against its own
     profile, so one incident weighs differently on two agents. Grounded on ticket 100 D4/D7
     and on the call site that passes the agent's identity narrative to the judgment
     (simulation_controller.py:1638). The master's reservation left the body and became the
     [TBC] of § 6.3.
  B. "Rating the severity is not established as one" was unreadable and is replaced by its
     reason, in two passes. The first gave the reason and kept the wrong subject; the author
     objected that the language model does rate the severity today, which the sentence hid.
     The body now says both, in that order: the model rates it, and that link is still not
     text generation, because the rating is one level in a closed grid. The ticket 101 hedge
     survives as an open question rather than as a count of experiments not run.
  C. Sweep for sentences that state the current state as a settled absence. Three removed:
     "Recall by similarity never brought the memory back, and the belief drawn by the evening
     consolidation reached no prompt"; "The belief born of the failure was never served, so
     nothing contradicted it"; and, by the author's own hand before this pass, "The
     single-agent case below does not exercise that step". Each fact is kept in the source
     comment above its paragraph, none is contradicted, and the sentence that replaces it
     says what the measurement establishes and what the campaign under way will add.
     Checked and left alone, being scope and not defect: "A decision-maker that receives
     those inputs alone can answer nothing else" (§ 6.1, the point of the chapter) and "We
     claim the path rather than its amplitude" (§ 6.4, the claim the paper makes).
  D. Author's second pass, same day, seven edits: the severity sentence above (B); the two
     anticipations reduced to bare [TBC] markers (§ 6.3, § 6.4); "and not a constraint" and
     "not from a number set by hand" dropped, both being defences against objections nobody
     raised; the zero contradiction turned from a bold figure into a dated [TBC] carrying a
     decision to take; the second-experiment paragraph set entirely in bold; and the
     transition to § 7 removed, § 7 opening on its own statement.
  E. FACT CORRECTED, not asked for but found on the way. "then a smaller delay the next day"
     described a second incident that never ran: the archive holds day 15 only. See the
     source comment of § 6.3 and NOTE_AU_REDACTEUR.md n° 1. The long article still carries
     the error and is locked.

Flags for the author :
  1. UNRULED, re-raised. The "zero belief contradiction" figure comes from the ticket 095 § 1
     campaign (077), not from the 2026-09-21 archive that produces every other figure of
     § 6.4. The extinction-by-wear claim rests on it. The sentence is left as it stands, as
     instructed. A cross-check on the archive would settle it.
  2. Table 4 is a fourth table where the plan caps the paper at three. Fallback sentence,
     ready if G4 returns more than 8 pages: "The car is taken on 94 %, 32 % then 88 % of the
     trips where it is offered, against 90, 92 and 87 % for the control agent."
  3. § 6.2 now depends on § 3.3 carrying the household account (review item T2), written by
     another agent. If T2 is not applied, the evening account is described nowhere.
  4. § 6.3 now depends on § 3.3 stating that the bench runs with memory off. That sentence
     is present in the current § 3.3.
  5. The limitation removed from § 6.3 (a real engine failure would immobilise the vehicle)
     must appear once in § 7.2, which another agent handles.
  6. § 6.1 falls to 47 words against the plan's 80, the deletion of N3 being the cause. The
     paragraph still establishes its point.
-->
