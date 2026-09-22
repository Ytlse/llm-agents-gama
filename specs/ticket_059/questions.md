# Ticket 059 — questions vivantes

Ouvert le 2026-09-21, à l'élargissement du ticket aux trois étages. Les lots 1, 2 et 6 peuvent
commencer sous les hypothèses ci-dessous ; **le lot 4 (canal `information`) ne se code pas avant
les réponses à Q1, Q2, Q5 et Q6.**

| # | Question | Hypothèse tenue faute de réponse | Ce qu'elle engage |
|---|---|---|---|
| Q1 | Constante de gravité des articles : 0,70 pour les cinq ? | oui, plus deux bras de sensibilité à 0,35 et 1,00 | la durée de l'effet, donc l'horizon de tous les runs |
| Q2 | Un seul lecteur par foyer, ou tous les membres d'un foyer exposé ? | un seul, tiré à graine fixe et journalisé | sans co-résident, l'étage 3 n'a pas d'objet |
| Q3 | Le bras « ouï-dire » (`memoire__partage_foyer_observations_min = 0`) entre-t-il dès P1 ? | oui | c'est lui qui transforme le constat « l'ouï-dire ne circule pas » en mesure |
| Q4 | Les trois cellules ambiguës de la grille : dédoublées par motif, ou « pas d'effet attendu » ? | « pas d'effet attendu », grille à vingt signes | le dénominateur du taux de signe, donc la barre du binomial |
| Q5 | Parution un jour unique, ou répétée sur plusieurs jours comme le choc C1 ? | un jour unique | une parution répétée mêle la persistance du souvenir à la répétition du stimulus |
| Q6 | Chaînage des véhicules actif partout, ou coupé dans les blocs visant la voiture ? | actif, premier article visant les TC, bras coupé si un article voiture est joué | le confondant « le lecteur libère la voiture du foyer » |
| Q7 | Cache de décisions pendant une campagne de presse ? | coupé, comme pour les chocs | la clé ne porte ni l'article ni le souvenir |
| Q8 | P0 (3 foyers, ~1 400 requêtes) est-il obligatoire avant P1 ? | oui | 1 400 requêtes pour savoir si le canal est vide, contre 43 000 pour l'apprendre trop tard |

---

## Ce qui reste à écrire avant le code

`specs/ticket_059/tests.md` — le contrat de tests, et les sept prédictions signées du § 9 du
ticket. Il s'écrit au démarrage du lot 0, une fois les questions ci-dessus tranchées, et **avant**
la première ligne de code. Les prédictions ne se réécrivent pas après mesure.

---

## Ajout du 2026-09-21, après le premier retour de l'auteur

L'auteur a écarté le run à cinq blocs comme mode de travail (« pas efficace pour du debug, coûteux
en appels si je dois itérer ») et demandé un échantillon plus petit. Le § 7.2 et le § 7.3 du ticket
sont réécrits en conséquence : un article à la fois, les blocs seulement en forme finale, et un
escalier de paliers dont chaque marche décide de la suivante.

| # | Question | Hypothèse tenue faute de réponse |
|---|---|---|
| Q9 | L'étage 1 démarre-t-il par E1-a — 200 déplacements, un article, C1 et C2, **400 requêtes** — plutôt que par la cohorte entière à 52 784 ? | oui ; E1-d (cohorte entière) ne se lance que si un relecteur l'exige ou si l'intervalle de E1-c est trop large |
| Q10 | Strates du sous-échantillon : mode de référence, motif, tranche horaire, zone de résidence ? | ces quatre, graine journalisée, et les **mêmes** déplacements pour toutes les conditions |
| Q11 | P1 à 20 agents (10 foyers de taille 2) sur 25 jours suffit-il pour donner la variance qui dimensionne P2 ? | oui, sous réserve que P0 ait montré le canal allumé |

---

## Ajout du 2026-09-21, à l'écriture du plan d'architecture

| # | Question | Hypothèse tenue faute de réponse |
|---|---|---|
| Q12 | **Les cinq articles sont français ; le dispositif est anglais depuis le 074.** Traduit-on ? | **TRANCHÉ le 2026-09-21 — on traduit, avec mention « traduit du français ».** Les deux versions sont gelées avec leurs empreintes, la traduction est faite une fois, le manifeste nomme qui l'a faite et quand, et l'entrée servie à l'agent porte la mention. `plan.md`, lot 1 |
| Q13 | « Corrige les articles » du retour de l'auteur | **TRANCHÉ le 2026-09-21 — il s'agit des chapitres du papier AAMAS**, pas du corpus de presse. Traité sous le verrou de l'article, diff présenté et accord demandé séparément |
| Q14 | **Les cinq textes témoins de C4 n'existent pas et ne peuvent pas venir du corpus des trente** — il a été constitué pour son lien avec la mobilité. Faut-il collecter cinq articles locaux neufs (culture, économie, fait divers sans transport), ou la condition C4 se réduit-elle autrement ? | collecter cinq articles neufs, appariés en longueur à ±15 % ; sans eux, le contrôle de spécificité du § 4.4 n'a pas de support et $H_3$ perd un de ses trois critères de réfutation |


---

## Réponses de l'auteur, 2026-09-21 (second tour)

| # | Question | Réponse | Ce qu'elle change |
|---|---|---|---|
| **Q1** | Constante de gravité des articles | **L'AGENT DÉCIDE.** Pas de constante, pas de bras de sensibilité | Le mécanisme existe déjà — `gravite_jugee` note sur cinq échelons ancrés par une conséquence observable, et `gravite_concept` applique `max(jugement, déterministe)`. Un article ne porte aucun fait mesuré, donc le jugement décide seul : c'est la règle en vigueur, appliquée à un cas où le terme déterministe vaut zéro. **Q1 cesse d'être un paramètre à justifier dans l'article** |
| **Q2** | Un lecteur par foyer | **oui** | `lecteurs_par_foyer: 1`, tirage déterministe journalisé |
| **Q5** | Parution unique ou répétée | **« Random »** — lu comme : le jour de parution est TIRÉ AU SORT | Tirage par foyer, à graine fixe, dans une fenêtre déclarée. Effet de bord favorable : un effet de calendrier ne peut plus se confondre avec l'effet de l'article, puisque les foyers ne lisent pas le même jour. À confirmer — voir Q15 |
| **Q6** | Chaînage des véhicules | **actif partout** | Le confondant « le lecteur libère la voiture du foyer » ne se supprime donc pas : il se MESURE. La colonne `contrainte_chaine` devient obligatoire, et un changement de mode concomitant à une contrainte de chaîne ne compte pas comme diffusion |
| **Q12** | Traduction des articles | **traduire, avec mention « traduit du français »** | Appliqué : 10 textes traduits, mention `[Translated from French]`, manifeste nommant le traducteur |
| **Q13** | « corrige les articles » | **les chapitres du papier AAMAS** | Fait sous accord : § 7.1.2 FR et EN, notes de travail |
| **C3** | Faut-il cacher le mode dont l'article parle ? | **NON — « ça serait ridicule de le cacher »** | Le sujet se nomme, les modes de report disparaissent. Exemptions déclarées par article avec deux gardes |

### Ce que Q1 ouvre, et qui reste à trancher

| # | Question | Hypothèse |
|---|---|---|
| Q15 | **Q5 « Random » — jour de parution tiré au sort par foyer, ou un seul jour tiré pour tout le run ?** | par foyer, ce qui décorrèle l'effet du calendrier ; un seul jour tiré ne ferait que déplacer une date choisie |
| Q16 | **Quand l'agent juge-t-il l'article ?** À la lecture, par un appel dédié — un par lecteur et par parution, cinq appels en P1 — ou à la consolidation du soir, sans aucun appel neuf ? | **à la lecture.** Le soir, l'entrée aurait déjà vécu la journée à gravité nulle, donc n'aurait pas pesé sur les décisions du jour de parution — celui-là même où l'article est censé agir |
| Q17 | **Que faire d'un échelon hors grille ?** `gravite_jugee` rend `None` et retombe sur le déterministe, qui vaut ici zéro — donc un souvenir de trois jours | refus explicite et `[ALARME]`, jamais de repli silencieux : un article qui s'efface parce que le modèle a mal répondu produirait un effet nul qu'on lirait comme un résultat |

### Troisième tour, 2026-09-21

| Point | Décision |
|---|---|
| **L'échelle de jugement** | **Signée et qualitative**, neuf échelons de « très grave » à « à ne pas manquer », plus « on s'en moque » au centre. Les cinq échelons du dépôt ne mesurent qu'une intensité de contrariété : ils ne savent pas dire qu'un article est une bonne nouvelle, alors que la grille prédit un signe positif au vélo sur VélôToulouse |
| **Les modes impactés** | L'agent **nomme les modes** qu'il estime touchés et leur attribue le score. Conséquence : son jugement devient directement confrontable à la grille pré-enregistrée, sans attendre qu'il se déplace — un troisième niveau de mesure, après le comportement et l'enquête du soir |
| **Le témoin de C4** | **Un seul, commun aux cinq articles** : la dépêche France 24 du 2026-09-19 sur le tilcayo. Apparié en longueur aux cinq (0,5 % à 8 % d'écart), aucun mot de mobilité |

⚠ **Le témoin n'est pas de la presse locale**, et le protocole l'annonçait ainsi. Une dépêche
internationale de sciences naturelles et un fait divers toulousain ne sont pas interchangeables :
un agent peut traiter différemment ce qui se passe chez lui et ce qui se passe à 9 000 km. À
écrire dans le texte plutôt qu'à laisser croire.

### Quatrième tour, 2026-09-21 — la diffusion au foyer, redemandée par l'auteur

> « Un membre du foyer lit le journal, et l'information atteint les autres. Oui ça doit être ça.
> Il doit partager ces souvenirs avec sa famille. »

**C'est prévu** — c'est l'étage 3, et il repose entièrement sur le ticket 078. **Mais en l'état il
ne marcherait pas**, et le constat est au § 6.1 du ticket :

- le 078 ne fait circuler que les **concepts**, jamais les entrées épisodiques. Un souvenir de
  lecture — « ce matin j'ai lu que… » — reste strictement personnel, par construction ;
- sa règle R1 exige `observations ≥ 1` : un concept né d'une lecture part à **zéro** observation,
  donc il ne repart pas dans le foyer tant que son porteur ne l'a pas vérifié par un déplacement
  réel.

Ces deux règles ne sont pas des détails d'implémentation : c'est la garantie anti-chambre d'écho du
078, celle qui interdit qu'une croyance s'amplifie sans contact avec le monde. La demande de
l'auteur la met en tension, et cela se tranche.

| # | Question | Options |
|---|---|---|
| **Q18** | **Comment l'article atteint-il la famille ?** | **(a)** `memoire__partage_foyer_observations_min = 0` — tout circule, ouï-dire compris. C'est le bras « ouï-dire » déjà prévu au § 6.2, un paramètre, zéro code. **(b)** Exception pour les concepts nés d'une lecture, qui circulent une fois sans ancrage — du code, et une brèche dans la garantie. **(c)** Garder R1 : le lecteur vérifie par un trajet, puis raconte ; le **délai** devient la mesure |

**Recommandation : jouer (a) ET (c), ce sont les deux bras du § 6.2 et ils sont déjà au protocole.**
La demande de l'auteur est satisfaite par (a), et (c) dit ce que l'ancrage coûte en vitesse et ce
qu'il évite en reformulation circulaire. Sans les deux, « l'ancrage protège de la chambre d'écho »
reste une affirmation de conception au lieu d'être un résultat.

⚠ **Aucun des trois ne fonctionne avant que le 078 ait du code.** Il n'en a aucun à ce jour : ni
repère de lecture, ni bloc du soir, ni les six règles. C'est le seul vrai bloquant de l'étage 3.

---

## Quatrième tour, 2026-09-21 — relecture du chapitre 7, second passage

L'auteur a relu le § 7.1 tel qu'il venait d'être écrit et a tranché **le dispositif**, pas
seulement la rédaction. Trois décisions, et elles déplacent le ticket plus qu'aucune des
précédentes.

| Point | Décision | Ce qu'elle change dans ce ticket |
|---|---|---|
| **L'étage 1 disparaît** | La campagne de presse ne se joue **pas** sur les 3 299 déplacements à mémoire éteinte. Elle se joue sur **quelques foyers, plusieurs jours, mémoire allumée** | Le § 2 n'a plus trois étages mais deux : la réponse et la persistance se mesurent dans le même run longitudinal, et la diffusion avec. E1-a à E1-d (Q9, Q10) sont **sans objet** : il n'y a plus de passe hors simulateur. Le calendrier du § 7.1 et l'escalier de paliers du § 7.3 deviennent le plan de la **première** campagne, pas de la troisième |
| **C3 et C5 sont retirées** | Il reste **trois** conditions : C1 journée nominale, C2 article brut, et le témoin, **renuméroté C3** | Le § 3 passe de cinq à trois lignes. La paraphrase neutre et la référence tabulaire à événement encodé sortent du protocole. Le lot 1 n'a plus à écrire de paraphrase ; `lexique_mobilite` ne sert plus qu'à vérifier le témoin |
| **Le point de comparaison** | Un **décideur à règles rigides qui ne lit pas**. Il n'est pas une condition : son écart est nul par construction | Remplace ce que C5 apportait. Le § 4.4 doit être réécrit en conséquence |

⚠ **Ce que le retrait de C3 coûte, et il faut le savoir avant de coder.** La paraphrase neutre
était le seul contrôle qui répondait à l'objection « le modèle obéit au mot *métro* présent dans
le texte ». Le critère de réfutation n° 2 de $H_3$ (§ 4.4) perd son support : il ne reste que le
texte témoin (spécificité) et le taux de signe. Deux issues, à trancher au lot 1 : porter
l'objection au chapitre des limites, ou la désamorcer par le corpus. **Aucun code ne dépend de ce
choix**, mais la rédaction, si.

⚠ **Ce que le retrait de l'étage 1 coûte.** L'étage 1 était la seule mesure portant sur une
population. Plus aucune part modale de ce ticket n'est publiable comme part de population : le
chapitre le dit désormais explicitement (« sur des foyers dont le nombre ne permet aucune part de
population »). Le dimensionnement du § 7.3 reste valable, mais son objet change — il ne prépare
plus une mesure de masse, il dimensionne une étude de mécanisme.

### Ce que le chapitre 7 revendique désormais, et ce qu'il ne revendique pas

Arrêté le 2026-09-21, et c'est le cadre dans lequel toute mesure de ce ticket sera lue :

- **revendiqué** — le **signe** du déplacement, contre la grille pré-enregistrée des vingt
  cellules ; et la **forme**, un décrochage le jour de la parution suivi d'un retour progressif
  vers le niveau d'avant ;
- **non revendiqué** — l'**ampleur** du déplacement, la date exacte du retour, et tout réalisme
  de l'un ou de l'autre. L'intensité de la grille se publie sans être testée.

| # | Question ouverte par ce tour | Hypothèse tenue faute de réponse |
|---|---|---|
| Q19 | Combien de foyers à la première campagne ? Le § 7.3 propose P0 à 3 foyers puis P1 à 10 foyers de taille 2 | P0 puis P1, inchangés : l'escalier survit au retrait de l'étage 1, c'est son objet qui change |
| Q20 | Le décideur à règles rigides tourne-t-il **dans** GAMA, ou se rejoue-t-il hors ligne depuis `moves.csv` ? | rejeu hors ligne : il garde une mesure là où la troisième issue (l'assumer par construction) ne donne qu'une constante. Note 9 des notes de travail du chapitre 7 |
| Q21 | L'objection « consigne lexicale », désormais sans contrôle : limites, ou corpus ? | chapitre des limites, et le dire dans le chapitre 7 plutôt que de le laisser au relecteur |
