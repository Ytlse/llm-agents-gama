# Ticket 100 — questions vivantes

Ouvertes le 2026-09-21, au lot 0. Plan : [`plan.md`](plan.md). Contrat de tests :
[`tests.md`](tests.md).

Q1 à Q5 viennent du § 10 du ticket, avec l'hypothèse que l'auteur y a posée. Q6 à Q11 sont nées de
la lecture du code et n'étaient pas au ticket : chacune nomme le constat qui l'a fait apparaître.
**Toutes sont tenues sous hypothèse ; aucune ne bloque le lot 1.** Deux bloquent un lot plus loin,
et c'est dit.

---

## Reportées du ticket

| # | Question | Hypothèse tenue | Ce qu'elle engage |
|---|---|---|---|
| Q1 | Le récit du soir : un énoncé par **déplacement**, ou par **entrée brute** ? | **TRANCHÉ le 2026-09-22 : ni l'un ni l'autre — un BILAN de la journée, avec les événements importants à partager.** Lecture retenue au § « Le bilan du soir » ci-dessous | le volume du prompt de consolidation, et la nature de ce qui circule |
| Q2 | Une croyance `entendu` que le receveur **confirme ensuite par un trajet** repart-elle ? | **TRANCHÉ le 2026-09-21 : non.** Lecture stricte de D2. Sa propre journée peut créer une croyance `vecu` distincte, qui circule | R36 et R37 du contrat. Le lot 4 est débloqué sur ce point |
| Q3 | Le récit dit-il **ce qui a été décidé** ou **ce qui a été vécu** ? | **TRANCHÉ le 2026-09-21 : aucune nouvelle information.** Le récit ne porte que ce qui est déjà dans la mémoire de celui qui parle, dans ses mots. Aucune reformulation, aucun fait ajouté, aucune donnée de simulation que l'agent n'aurait pas lui-même vécue | Le récit devient une **citation**, pas un texte neuf. Conséquence forte : il n'a pas à repasser par les gardes de contenu (consigne, verdict, intention), puisque ce qu'il cite les a déjà franchies à l'écriture. C'est aussi ce qui écarte pour de bon la variante C du 078 — partager les FAITS de la journée tirés de la simulation reviendrait à faire entrer une information que le porteur n'a pas |
| Q4 | Le jugement à l'injection d'un choc change le dispositif du § 7.2 : le déclarer, ou jouer un bras sans jugement ? | **les deux** : le bras sans jugement est l'ablation déclarée `jugement: aucun`, et c'est aussi le mode du test en or | la comparabilité avec les chiffres déjà publiés du § 7.2 |
| Q5 | Le cache de décisions pendant un run à événement ? | **TRANCHÉ le 2026-09-22 : pas de cache le JOUR de l'événement.** Coupure automatique ce jour-là, sans avoir à y penser ; le reste du run garde le cache. ⚠ Réserve chiffrée au § « Ce que la coupure au jour de l'événement laisse passer » | la clé exacte du cache ne porte pas la mémoire, et la branche sémantique ne rejette qu'en dessous de 0,95 |

---

## Nées de la lecture du code

| # | Question | Hypothèse tenue | Constat qui l'a fait apparaître |
|---|---|---|---|
| Q6 | Le jugement retarde-t-il le traitement de l'arrivée, ou part-il dans la file du soir ? | **TRANCHÉ le 2026-09-22 : dans la file du soir.** Lecture retenue et conséquences au § « Le jugement dans la file du soir » | aucun appel sur un chemin critique ; la force du souvenir doit être **recalculée avec** l'importance, jamais après elle |
| Q7 | Où vit le corpus pour le conteneur ? Montage en lecture seule de `articles_txt`, ou copie sous `config/evenements/textes/` ? | **montage étroit en lecture seule**, sur le modèle de `experience_plan` déjà au compose | une copie dans `config/` dédoublerait le texte et rendrait la garde de citation circulaire — elle vérifierait l'empreinte de sa propre copie |
| Q8 | `Person.household_id` : champ propre, ou trait ajouté à `traits_json` ? | **champ propre** sur `Person` | `traits_json` porte les attributs de persona servis au prompt ; l'appartenance au foyer est une propriété de simulation, pas un trait de personnage. La mettre dans les traits la ferait entrer dans un prompt un jour |
| Q9 | Un événement dont un jour dû tombe dans la **fenêtre de rejeu** d'une reprise à chaud : refus au chargement, ou report ? | **refus** au chargement, `[ALARME]` si le gel est actif à une injection due | `gel_actif()` renvoie l'écriture sans rien faire : un report silencieux déplacerait le protocole d'un ou deux jours sans que rien ne le dise. Un report **déclaré** serait défendable, mais il n'a pas été demandé |
| Q10 | Le renommage des colonnes de `moves.csv` : double graphie acceptée pendant une version, ou bascule franche avec réécriture des archives ? | **double graphie** en lecture, une seule en écriture, la graphie trouvée journalisée | quatre lecteurs au dépôt, plus les notebooks. Une bascule franche rendrait les runs archivés du § 7.2 indépouillables — or ce sont eux qui portent les chiffres publiés |
| Q11 | `llm/chocs.py` disparaît-il **au lot 6**, ou survit-il une version de plus comme adaptateur ? | suppression au lot 6, **après** un run court de non-régression sur `c6_voiture_suspecte` | le test en or rejoue une trace, pas un run : il ne dit rien du chemin GAMA. Supprimer avant ce run laisserait la seule intégration non vérifiée sans filet |
| Q13 | **Née au lot 2, et corrigée le jour même.** La prise `reveil` n'écrivait qu'en mémoire courte, que la décision ne lit pas : l'article n'atteignait aucune décision du jour. Écrire aussi en mémoire longue, ou forcer une consolidation du lecteur à l'injection ? | **écrire aussi en mémoire longue**, à l'injection, texte cité verbatim et qualifié. La double écriture est délibérée : la mémoire courte pour que la réflexion du soir voie l'article, la longue pour que les décisions du jour le trouvent | Forcer une consolidation coûterait un appel LLM par lecteur à 3 h, et écrirait une réflexion sur une journée qui n'a pas encore eu lieu. Voir le § « Défaut trouvé le 2026-09-22 » |
| Q15 | **Née de D7, 2026-09-22.** Le plancher `max(estimée, mesurée)` est levé : plus rien ne signale un jugement aberrant. Quelle garde le remplace, et à quel seuil ? | **journaliser l'écart, jamais le corriger** — proposition de l'auteur, livrée le jour même. `ecart_au_fait = estimée − mesurée` sur chaque jugement, écrit dans `evenements.jsonl`, et `[ALARME]` sous `memoire__ecart_jugement_alarme = 0,30` | Le seuil vaut **plus d'un échelon** : les marches de l'échelle valent 0,20 à 0,25, donc un tel écart ne vient pas d'une hésitation entre deux niveaux voisins ; « anodin » sur un dépannage de 30 min vaut −0,60. Alarmer plus bas noierait le journal, plus haut laisserait passer le cas qui compte. **Corriger la valeur est exclu** : cela rétablirait le plancher sous un autre nom, et la campagne mesurerait la garde au lieu de l'agent. ⚠ Le seuil reste à confirmer — c'est le seul chiffre de cette garde que personne n'a mesuré |
| Q14 | **Née le 2026-09-22.** Les marqueurs de VERDICT refuseraient un article rapportant « users say the service is unreliable ». Aucun des cinq ne le fait — le cas est hypothétique | l'exemption déclarée de Q12 le couvre : même mécanisme, même motif écrit, même caducité avec l'empreinte | Un article qui **rapporte** un jugement d'usagers n'est pas un article qui **conclut** à la place de l'agent, mais la liste ne sait pas les distinguer. À rouvrir si un article du prochain corpus tombe dessus |
| Q12 | **Née au lot 2.** Les marqueurs de consigne refusent « make sure » dans `a09_vent_autan`, où la phrase est « City staff must first inspect each site to make sure there is no danger » — le sujet est le personnel municipal, pas le lecteur. Relâcher la liste pour le canal `lu`, exempter au cas par cas, ou ré-extraire le texte sans la phrase ? | **exemption déclarée**, sous `texte.marqueurs_exemptes`, avec motif obligatoire, refus si le marqueur n'est pas dans le texte, et caducité avec l'empreinte. C'est le précédent du 059 lot 1 sur les mots interdits de la paraphrase | Relâcher la liste ouvrirait la porte au cas qui compte vraiment — « residents are urged to avoid the metro » — qui pousse un mode et fabriquerait le résultat. Ré-extraire le texte reviendrait à choisir ce que l'article dit, ce que la garde de citation existe pour interdire. **Mesuré : une seule occurrence sur les cinq articles**, et aucune adresse à la deuxième personne, qui reste inexemptable |

---

## ⚠ Défaut trouvé le 2026-09-22 : une entrée au réveil n'atteint aucune décision du jour

**Mesuré dans le code, pas supposé.** La décision d'un agent ne lit **que** la mémoire longue :
`query_past_experiences_for_travel` interroge `long_term_memory.aquery_user_memories`
(`llm_agent.py:807`), et le tampon de mémoire courte n'entre nulle part dans le prompt de
décision. Or la consolidation du soir **consomme** ce tampon (`remove_batch`,
`llm_agent.py:1939`) et n'écrit en mémoire longue que la réflexion et les concepts : le texte
brut injecté n'y arrive **jamais tel quel** — c'est d'ailleurs pourquoi l'appariement d'un choc
à son souvenir échoue déjà, la réflexion le reformule (`mesures/calcul.py`).

**Conséquence sur le lot 2 tel qu'il a été livré :** un article déposé à 3 h en mémoire courte
n'est vu par aucune décision de la journée. Il n'atteint la mémoire longue que le soir, sous
forme reformulée, et ne pèse qu'à partir du **lendemain**. La phrase « l'agent sait avant de
décider » serait donc fausse, et le contraste entre les deux régimes se réduirait à quelques
heures et à l'absence d'un retard mesuré.

**Ce n'est pas un défaut du régime subi.** Un choc s'applique après la décision : que son effet
ne commence que le lendemain est exactement ce qu'on veut, et c'est ce qui rend les jours
suivants imputables au seul souvenir.

**Correction retenue : la prise `reveil` écrit AUSSI en mémoire longue, à l'injection.** Le
texte cité y entre verbatim, qualifié, donc interrogeable par les décisions du jour même et
servable par le bloc « Ce qui a changé récemment » dès que sa gravité passe le seuil. L'entrée
de mémoire courte reste, pour que la réflexion du soir la voie et puisse en tirer une croyance.

L'asymétrie entre les deux prises est assumée et elle est le régime lui-même : ce qui est
**commun** aux deux canaux est la qualification — gravité par la règle du maximum, valence,
origine, force, durée de service — pas le chemin d'écriture. Le ticket disait « un seul aval » ;
à la lecture du code, l'aval commun commence à la qualification, pas à l'écriture.

---

## Le jugement dans la file du soir — lecture du 2026-09-22

L'auteur tranche Q6 : **dans la file du soir**. Aucun appel au modèle sur un chemin critique.

**Lecture retenue : le jugement n'est pas un appel de plus, il est DANS la réflexion qui a déjà
lieu.** Le gabarit `stm_reflection` demande déjà `severity` et `valence` — sur les concepts. Il
suffit de les demander aussi sur les événements de la journée. Coût marginal : **zéro appel
LLM**, ce qui est la doctrine du 078 (« pas un seul appel supplémentaire ») et ce que « la file
du soir » veut dire de plus économique.

**La conséquence à ne pas manquer.** La force d'un souvenir est fixée **à l'écriture**
(`aadd_memory`, `longterm.py:434`). Si le jugement arrive le soir, l'entrée a déjà été écrite
avec la gravité déterministe. Requalifier, c'est donc recalculer **l'importance ET la force
ensemble**, en une seule opération datée et journalisée. Relever la seule importance laisserait
un souvenir qui porte une gravité et vit selon une autre — le piège nommé quand la question
était posée, et il devient réel maintenant que la réponse est « différé ».

**Ce que cela change pour la prise `reveil`.** À 3 h simulées, rien n'attend : aucune arrivée à
traiter, aucun agent réveillé. Le jugement d'un article peut donc se faire **à l'injection**
sans retarder quoi que ce soit — ce qui est l'intention de la réponse (« ne rien bloquer »),
pas sa contradiction. Et c'est nécessaire : différé au soir, l'article passerait la journée à
gravité 0,00, donc hors du bloc « Ce qui a changé récemment », donc sans effet le jour même —
ce que le défaut ci-dessus vient d'établir. **À confirmer** : jugement à l'injection au réveil,
dans la file du soir à l'arrivée.

---

## La boucle dans le foyer — exigence de l'auteur, 2026-09-22

> « Attention aux boucles infinies au sein de la famille. L'agent doit reconnaître une
> information déjà connue. »

Quatre gardes, dont trois existent déjà. Elles sont listées ensemble parce qu'aucune ne suffit
seule, et parce que le lot 4 ne se livre qu'avec les quatre.

| # | Garde | État |
|---|---|---|
| G1 | **Un récit n'est jamais servi deux fois au même receveur.** Le repère `foyer_lu_jusqu_a` est par receveur ; une réflexion source déjà servie ne repart pas, même si son auteur ne consolide pas ce soir-là | à écrire (lot 4) |
| G2 | **Le receveur voit ce qu'il croit déjà** dans le même appel : `known_beliefs` est dans le prompt de réflexion depuis le lot 3 du 071, avec `times_observed` et `times_contradicted`. C'est là que l'agent reconnaît une information connue, et le vocabulaire pour le dire existe — `confirm` plutôt que `create` | **existe** |
| G3 | **Ce qui est entendu ne repart jamais** : `origine: entendu`, décision D2, même après confirmation ultérieure (Q2) | champ livré au lot 1, règle au lot 4 |
| G4 | **Le détecteur de reformulation circulaire** : dans un même foyer et un même panier `(mode, motif)`, combien de concepts distincts coexistent et combien de mots-clés ils partagent. ⚠ Indicateur qui ALERTE, jamais un seuil qui coupe — le 071 et le 077 ont tous deux refusé qu'une mesure de similarité décide à la place d'une règle | à écrire (lot 4, mesure n° 3 du 078) |

**Ce que G3 garantit, et ce qu'il ne garantit pas.** Il rend impossible le cycle *A dit → B
croit → B dit → A croit*. Il ne rend pas impossible que A répète la même chose tous les soirs
et que B accumule des reformulations : c'est G2 qui doit l'empêcher, et G4 qui doit le rendre
visible si G2 échoue. **La mesure passe donc avant la conclusion** : si G4 montre une famille
qui redit la même chose sous quatre formes, c'est R2 du 078 qui se durcit — on ne l'invente pas
avant de l'avoir vu.

---

## Le bilan du soir — lecture du 2026-09-22

L'auteur répond à Q1 : le récit du soir est **« un bilan de la journée avec les événements
importants à partager »**. Ce n'est aucune des deux granularités proposées, et c'est mieux que
les deux.

**Ce bilan existe déjà, et l'agent l'écrit lui-même.** Le champ `reflection` de
`stm_reflection` est exactement cela : *a text summarising what happened today*, 200 mots au
plus, écrit chaque soir par chaque agent, et rangé en mémoire longue comme entrée de type
`REFLECTION`. Le récit du soir n'a donc **rien à rédiger** : il cite la réflexion que l'autre
membre a produite, plus les événements qui ont été déposés chez lui dans la journée — le choc
subi, l'article lu.

C'est la seule lecture compatible avec Q3 (« aucune nouvelle information »). Un bilan que nous
composerions serait une reformulation, donc un texte neuf, donc une information que le porteur
n'a pas dite. Un bilan qu'il a écrit lui-même est une citation.

Trois conséquences, et elles ferment trois questions d'un coup :

1. **Le volume est borné par construction** — 200 mots par membre, la borne du gabarit, sans
   règle de troncature à inventer. `memoire__recit_soir_max` devient un garde-fou sur le nombre
   de MEMBRES cités, pas sur le nombre d'énoncés.
2. **Le tri par gravité décroissante n'a plus d'objet** : c'est l'agent qui a décidé, en
   écrivant sa réflexion, de ce qui méritait d'y figurer. « Les événements importants à
   partager » sont ceux qu'il a lui-même retenus.
3. **L'ordre entre membres reste indifférent**, comme au 078 § 2 : le repère `foyer_lu_jusqu_a`
   sert la dernière réflexion disponible de chaque autre membre. Un membre qui n'a pas encore
   consolidé sera entendu la nuit suivante, matière intacte — jamais perdue.

⚠ **Un point à confirmer.** Cette lecture dit « la réflexion du soir de l'autre », et la
décision D1 du ticket disait « tous les épisodes de la journée, sans restriction de gravité ».
Les deux se rejoignent si l'on admet que la réflexion **est** le résumé de tous les épisodes —
ce qu'elle prétend être. Elles divergent si l'auteur voulait que les épisodes bruts circulent
en plus. L'hypothèse tenue est la première ; c'est aussi la seule qui ne triple pas le prompt.

---

## Ce que la coupure au jour de l'événement laisse passer

L'auteur tranche Q5 : **pas de cache le jour de l'événement**. C'est implémenté, automatique, et
sans rien à penser au lancement.

Reste une réserve qu'il faut poser, parce qu'elle porte sur ce que l'expérience mesure. Le jour
de l'événement n'est pas le jour qu'on mesure : **c'est la fenêtre d'après**. Un choc au jour 15
se lit sur les décisions des jours 16 à 30, et c'est là que le souvenir pèse — ou cesse de
peser. Or la clé exacte du cache ne porte ni la date ni la mémoire : une décision prise au
jour 5, mêmes options, même météo, mêmes traits, même tranche horaire, reste servable au
jour 20.

Ce qui protège cette fenêtre n'est pas la coupure du jour de l'événement, c'est la **branche
sémantique** : dès que la mémoire longue de l'agent est non vide, le cache exige 0,95 de
similarité entre le bloc de mémoire d'aujourd'hui et celui qui avait produit la décision. Quinze
jours d'écart déplacent beaucoup ce bloc, et la décision ratera probablement. **Probablement :
personne ne l'a mesuré.**

D'où le compromis retenu, qui ne discute pas la décision mais la rend lisible : la coupure au
jour de l'événement est automatique, et le journal compte, **par jour de la fenêtre**, combien de
décisions ont été servies depuis le cache. Si ce compte est nul, la réserve est sans objet et on
le saura. S'il ne l'est pas, on saura sur quoi porte le doute avant de publier la courbe, au
lieu de l'apprendre en relisant.

---

## Retours de l'auteur du 2026-09-21, et ce qu'ils appellent

**Q1 — « qu'est-ce que ce ticket change ? »** Aujourd'hui, **rien ne circule** entre membres d'un
foyer : le ticket 078 n'a aucune ligne de code, et un agent consolide seul. Le récit du soir est
donc entièrement neuf, et D1 le veut sans filtre de gravité : toute la journée de chaque autre
membre présent. Ce que Q1 tranche n'est pas s'il existe, mais sa **granularité**. Une journée ne
produit pas une entrée par déplacement : elle en produit plusieurs — l'entrée de décision, celle
d'arrivée, celle de contrainte de chaîne le cas échéant. « Par entrée brute » multiplie donc le
bloc par environ trois pour la même information. Ordre de grandeur, sur le manifeste de la
cohorte (3,30 déplacements par persona et par jour) et un foyer de quatre : une dizaine
d'énoncés par soir à la granularité « déplacement », une trentaine à la granularité « entrée »,
dans un prompt de consolidation que le 077 a mesuré stagnant vers 2 100 jetons. C'est le seul
volume du ticket qu'aucune règle d'ancrage ne borne.

**Q4 — TRANCHÉ le 2026-09-22 : la prochaine campagne REMPLACERA l'existante.** Pas de bras sans
jugement à faire tourner en parallèle : les courbes du § 7.2 seront refaites sous le nouveau
dispositif, et ce sont celles-là qui seront publiées. Deux conséquences. (1) `jugement: aucun`
reste dans le vocabulaire — c'est sous lui que tourne le test en or de la migration — mais il
n'est plus un bras de campagne. (2) **Signalement article dû** : les chiffres du § 7.2 et les
figures qui en viennent deviendront caducs le jour où la campagne tournera, et l'article devra
dire que l'agent juge désormais ce qu'il subit. Rien à corriger tant que la campagne n'a pas eu
lieu — mais rien à publier non plus depuis l'ancienne, une fois la nouvelle lancée.

La question, telle qu'elle avait été reformulée : *Les courbes du § 7.2 ont été
mesurées sur des agents qui ne jugeaient pas ce qu'ils subissaient. Quand ils jugeront, le même
choc déclaré pourra laisser un souvenir qui vit cinq jours de plus, donc déplacer la date
d'extinction que ces courbes montrent. La prochaine campagne **remplace-t-elle** ces courbes —
et l'article écrit alors que le dispositif a changé entre les deux — ou les **double-t-elle**
d'un bras où l'agent ne juge pas, pour que l'écart entre les deux régimes soit mesuré au lieu
d'être supposé ?* Le chiffrage qui la motive :

**Q4 — le détail (2026-09-21).** La gravité d'un choc est aujourd'hui **purement déterministe** : pour le
jour 15 de `c6_voiture_suspecte`, 30 minutes de retard (0,50) plus l'incident réseau (0,20) font
0,70, et la force du souvenir vaut **14,56 jours**. Avec D4, l'agent juge aussi, et
`gravite_concept` prend le maximum des deux — la protection est asymétrique, elle ne joue que
vers le bas. Conséquence chiffrée, sur ce même choc et ces mêmes 30 minutes :

| Ce que l'agent juge | Gravité retenue | Force du souvenir |
|---|---|---|
| `anodin`, `notable`, `genant` | 0,70 (le fait mesuré tient le plancher) | 14,56 j |
| `grave` | 0,75 | 15,40 j |
| `marquant` | 1,00 | **19,60 j** |
| *aucun jugement (état actuel)* | 0,70 | 14,56 j |

La date d'extinction de l'effet peut donc se déplacer de **cinq jours** sur un choc déclaré à
l'identique. Or c'est exactement ce que le § 7.2 mesure. Les chiffres publiés ont été obtenus
sans jugement : soit on l'écrit dans l'article et la prochaine campagne change de dispositif,
soit on joue un bras sans jugement pour mesurer l'écart. L'hypothèse tenue reste **les deux** —
et le bras sans jugement n'est pas un pis-aller, c'est `jugement: aucun`, l'ablation déclarée,
sous laquelle tourne déjà le test en or du lot 1.

**Q6 — « l'événement impacte la prise de décision ? Si la mémoire est différente le cache est
utilisé ? »** Deux réponses, vérifiées dans `llm/cache.py` le 2026-09-21.

*L'événement impacte-t-il la décision ?* Pas le jour même, sur la prise `arrivee` : il tombe
**après** le choix, c'est la définition du régime subi et c'est ce qui rend les jours suivants
imputables au seul souvenir. Sur la prise `reveil` (lot 2), **oui, dès la première décision du
jour** — l'agent sait avant de choisir. C'est tout le contraste entre les deux régimes.

*Le cache est-il utilisé si la mémoire diffère ?* Il y a deux branches, et une seule regarde la
mémoire.

| Branche | Quand | Ce que la clé porte |
|---|---|---|
| **exacte** (`_lookup_exact_sync`) | mémoire longue vide, ou rejeu gelé | agent, activité, tranche de 10 min, options, météo, traits, anticipation. **Pas la mémoire** |
| **sémantique** (`_lookup_semantic_sync`) | mémoire longue remplie | les mêmes conditions factuelles, **plus** une similarité d'embedding sur le bloc de mémoire, rejetée sous **0,95** |

Donc : le cache n'est pas aveugle à la mémoire, mais il n'est sensible qu'**au-delà d'un seuil
sur le bloc entier**. Une ligne de souvenir ajoutée à un bloc qui en compte des dizaines ne fait
pas nécessairement tomber le cosinus sous 0,95 — rien ne le garantit, et personne ne l'a mesuré.
Un run à événement avec cache actif peut donc resservir une décision d'avant l'événement. D'où
`CACHE=0` et l'`[ALARME]`, qui dit désormais *pourquoi* : le texte de l'alarme du 079 parlait de
« durée », ce qui était le mauvais motif. Ce n'est pas une dégradation qu'on refuse, c'est une
mesure qu'on ne saurait pas interpréter.

---

## Ce qui bloque, et ce qui ne bloque pas

- **Rien ne bloque le lot 1.** Q8 et Q9 l'orientent, les deux hypothèses sont tenables et
  réversibles.
- **Q6 bloque le lot 3.** Un jugement différé et un jugement bloquant ne produisent pas la même
  entrée : l'un fixe la force à l'écriture sur la gravité déterministe, l'autre sur la gravité
  retenue. Ce n'est pas un réglage, c'est deux mécaniques.
- **Q1, Q2, Q3 et Q5 sont tranchées** (2026-09-21 et 2026-09-22). Le lot 4 n'attend plus rien,
  sous réserve du point à confirmer au § « Le bilan du soir ».
- **Q6 est tranchée** (2026-09-22) : dans la file du soir. Le lot 3 n'est plus bloqué, sous
  réserve du point à confirmer au § « Le jugement dans la file du soir ».
- **Q13 est corrigée** le jour même de sa découverte : la prise `reveil` écrit aussi en mémoire
  longue. Le régime fait désormais ce qu'il annonce.
- **D7 est appliquée au code** (2026-09-22) : la gravité est l'estimation de l'agent, seule. Le
  contrat est repris — R26 retirée, R26 bis posée — et la garde de remplacement est livrée avec.
  Seul son **seuil** reste à confirmer (Q15).
- **Le bras « ouï-dire » du 059 est retiré** (auteur, 2026-09-22) : D1 fait porter au récit du
  soir tous les épisodes, il n'y a plus de seuil à mettre à zéro. ⚠ Le réglage
  `memoire__partage_foyer_observations_min` **reste dans le code** et R1 avec lui : l'ancrage
  gouverne les **croyances**, qui sont un canal distinct du récit. C'est le bras d'expérience
  qui disparaît, pas la règle.
- **Le foyer témoin n'est plus exigé** (auteur, 2026-09-22), ni dans le même run. Le rôle
  `temoin` reste écrit dans `moves.csv` quand un tel foyer est présent — c'est une étiquette,
  plus une obligation. ⚠ Le plancher de bruit du 095 (3,2 %, **une** mesure, **un** persona) ne
  se lit alors plus dans le run : il se reprend ou se réétablit, et **se déclare avec le
  résultat**.
- **Les articles peuvent nommer des modes de transport** (auteur, 2026-09-22). Ce module ne l'a
  jamais interdit ; la liste de mots qui l'interdit est celle du 059 lot 1, et elle porte sur la
  **paraphrase** (C3) et le **témoin** (C4), pas sur l'article cité. La note est désormais en
  tête de `gardes.py`, là où quelqu'un ira la chercher.
- **Q10 bloque le lot 5** pour la seule partie « relecture des archives ». Le reste du lot avance.

---

## Ce qui reste à faire avant la première ligne de code

La validation humaine de [`plan.md`](plan.md). Le ticket la demande au lot 0, et le § 1 du plan
contient trois constats que le ticket n'avait pas — `Person` sans `household.id`, la prise
`arrivee` qui annexe au lieu d'écrire, le gel du rejeu — dont le premier déplace du travail du
lot 4 vers le lot 1.
