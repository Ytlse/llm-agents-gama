# Ticket 059 — Étape 3b : la presse locale, ce qu'un agent en fait, et ce qu'il en dit chez lui

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-13 (tâches 21 et 22 de `suivi_actions_publication.md`).
> **Élargi le 2026-09-21** : le ticket ne cadrait qu'une réponse instantanée à un texte,
> mémoire éteinte. Il porte désormais trois étages — la réponse du jour, la **persistance**
> du souvenir de lecture, et la **diffusion de l'information au sein du foyer**.
>
> **Contrat de tests à écrire AVANT le code**, dans `specs/ticket_059/tests.md`.
> Les prédictions signées des étages 2 et 3 s'y posent avant le premier run, comme celles du
> lot A du [095](ticket_095_duree_d_un_souvenir_et_enquete_du_soir.md).
>
> **Dépendances, et elles ne bloquent pas tout.** L'étage 1 ne dépend de rien et peut être
> monté aujourd'hui. L'étage 2 attend les expériences E1 à E3 du
> [095](ticket_095_duree_d_un_souvenir_et_enquete_du_soir.md) — pas son code, qui est en
> service. L'étage 3 attend les lots 1 à 3 du
> [078](ticket_078_partage_de_concepts_au_sein_du_foyer.md), qui n'a aucun code.
>
> **REVU LE 2026-09-21, second tour de relecture du chapitre 7.** L'auteur a tranché le
> dispositif : la campagne ne se joue plus sur les 3 299 déplacements à mémoire éteinte mais sur
> **quelques foyers, plusieurs jours, mémoire allumée**. L'**étage 1 disparaît** comme passe
> autonome, les conditions **C3 (paraphrase neutre) et C5 (référence tabulaire à événement
> encodé) sont retirées**, et le point de comparaison devient un **décideur à règles rigides qui
> ne lit pas**. Le détail et ce que chaque retrait coûte sont dans
> `specs/ticket_059/questions.md`, quatrième tour. Les § 2, § 3 et § 4.4 ci-dessous sont à lire
> avec ce bandeau ; le § 5 et le § 6 ne bougent pas.
>
> **Ce ticket n'écrit pas dans l'article.** Le chapitre 7 § 7.1 décrit l'étage 1 et rien d'autre ;
> les étages 2 et 3 lui manquent. Le signalement se fait par la skill `article-impact` au moment
> où une mesure existe, pas à l'élargissement du cadrage.

---

## 0 bis. Alignement sur le chapitre 7, au 2026-09-22

Le chapitre 7 a été refondu les 21 et 22 septembre. Trois choses de ce ticket ne s'y lisent plus
sous le même nom, et une quatrième n'a plus d'objet.

| Ce que le ticket dit | Ce que le chapitre porte au 22 septembre |
|---|---|
| « le chapitre 7 § 7.1 » pour la presse | c'est le **§ 7.3**. Le § 7.1 est désormais le mécanisme commun aux deux régimes, le § 7.2 le choc vécu |
| « un § 7.1 bis » à écrire pour la presse en régime longitudinal (§ 12) | **sans objet** : le § 7.3 est longitudinal d'emblée depuis le retrait de l'étage 1. Il n'y a pas de section à ajouter, il y a une campagne à jouer |
| « la barre du binomial du § 7.1.3 » | le § 7.3.3 ne publie **aucun test** : le damier des accords paraît tel quel |
| le § 7.4 « ce que les deux régimes partagent » | **retiré du chapitre le 22 septembre.** Sa colonne mesurée était déjà au § 7.2.1, et sa prédiction de stratification est remontée au § 7.1 |

⚠ **Le bras « ouï-dire » (Q3) n'a plus d'objet.** Il faisait varier
`memoire__partage_foyer_observations_min`, le seuil d'ancrage d'une croyance avant qu'elle
circule. La décision D1 du [ticket 100](ticket_100_un_seul_canal_d_evenement_pour_le_vecu_et_le_lu.md)
supprime l'ancrage : le récit du soir porte **tous** les épisodes de la journée, sans condition de
gravité ni d'observation. Il n'y a plus de seuil à mettre à zéro. Ce que ce bras mesurait —
l'amplification sans contact avec le monde — reste une question ouverte, mais elle se pose
maintenant sur le **saut unique** de D2, pas sur l'ancrage.

✅ **TRANCHÉ le 2026-09-22 : le foyer témoin n'est plus demandé.** Lecteur, co-résident et témoin
interne étaient décrits au § 7.1.4 du chapitre, que l'auteur a retiré ; le § 7.3.2 ne dit plus
qu'une chose, qu'un membre par foyer reçoit le texte. Ce ticket cesse donc d'exiger un foyer
témoin non exposé, et cesse d'exiger qu'il soit dans le même run — voir le § 6.4, réécrit.

⚠ **Ce que cela coûte, et il faut le savoir en lisant les résultats.** Le 095 § 7 bis a mesuré
un plancher de bruit **non nul** entre deux bras identiques : 1 écart de mode sur 31 décisions
appariées. Sans foyer témoin dans le run, ce plancher n'est plus mesuré par le run lui-même ; il
reste à reprendre du 095, ou à réétablir par un rejeu à l'identique. Un écart plus petit que lui
n'est pas un effet, et cette garde-là ne disparaît pas avec le témoin.

---

## 1. Contexte & enjeu scientifique

Dans le régime nominal (chapitres 5 et 6), les modèles tabulaires supervisés (LightGBM) et
économétriques (MNL) devancent le meilleur prompt expert sur les 21 variables du contrat, 3,60 à
4,09 de composite contre 4,49. Ces 21 variables décrivent une personne, un motif, une heure et une
géométrie ; **aucune ne porte la météo, aucune ne porte une durée, aucune ne porte un événement du
jour**. C'est l'incompressibilité tabulaire : ces modèles sont structurellement aveugles à toute
information textuelle, sensorielle ou contextuelle non formalisée au préalable.

L'Étape 3b mesure ce que devient cette asymétrie face à des ruptures issues de la presse locale
réelle de la métropole toulousaine — fermeture des parcs sous vent d'Autan, rumeur de punaises de
lit dans le métro, grève des éboueurs dans les ruelles, marée humaine du Minotaure, vélos partagés
électriques sur les coteaux.

**Ce que l'élargissement du 2026-09-21 ajoute.** Mesurer la réponse du jour à un texte, c'est
mesurer un modèle de langue qui lit. Ce n'est pas encore mesurer un **agent** : un agent retient,
oublie, révise, et parle à ceux avec qui il vit. Trois questions séparent les deux, et ce sont
celles qui distinguent le dispositif d'un modèle de choix discret enrichi d'une colonne « article
du jour » :

1. **Combien de temps** un article lu pèse-t-il sur les décisions ? Le lot A du 095 a fait de la
   durée d'un souvenir une conséquence de sa gravité au lieu d'un entier posé. Un article n'a pas
   de gravité — il ne fait subir aucun retard. § 5.
2. **Que devient une croyance qu'aucun trajet ne dément ?** Un agent qui évite le métro sur la foi
   d'un article ne prendra jamais le métro nominal qui l'aurait contredit. § 5.5.
3. **L'information traverse-t-elle le foyer ?** 788 agents sur 1 000 vivent avec au moins un autre
   agent de la simulation. Un seul lit le journal. § 6.

---

## 2. Trois étages, et ce qui les sépare

> ⚠ **Périmé depuis le 2026-09-21.** Le tableau ci-dessous décrit trois étages dont le premier
> se jouait hors simulateur, mémoire éteinte, sur la cohorte entière. Cet étage n'existe plus :
> tout se joue dans un run GAMA longitudinal, mémoire allumée, sur quelques foyers. Ce qui reste
> vrai du tableau est la colonne « Question » et la ligne « Dépend de ». Ce qui est faux : les
> lignes « Mémoire », « Simulateur », « Horizon » et « Unité d'analyse » pour l'étage 1, et la
> colonne « Sortie pour l'article », le § 7.1 portant désormais les trois questions à la fois.
> Conservé tel quel parce que les dépendances aux tickets 095 et 078 s'y lisent encore.


| | Étage 1 — la réponse | Étage 2 — la persistance | Étage 3 — la diffusion |
|---|---|---|---|
| Question | l'agent réagit-il au texte, et au bon sens ? | combien de temps, et comment ça s'éteint ? | qui d'autre en entend parler ? |
| Mémoire | **éteinte** | allumée | allumée |
| Simulateur | non — rejeu hors ligne | **GAMA**, hors ligne | GAMA, hors ligne |
| Horizon | un jour | 25 à 30 jours | 25 à 30 jours |
| Unité d'analyse | le déplacement | l'agent exposé | le **foyer** |
| Sortie pour l'article | § 7.1, les vingt signes | § 7.1 bis à écrire | perspective, ch. 8 |
| Dépend de | rien | 095, E1 à E3 | 078, lots 1 à 3 |
| Peut démarrer | **aujourd'hui** | après E3 | après le 078 |

Les trois étages se jouent sur le **même corpus gelé** et la **même grille de signes**. C'est ce
qui rend leurs résultats comparables : l'étage 1 donne le signe attendu, l'étage 2 dit combien de
temps il tient, l'étage 3 dit jusqu'où il va.

⚠ **Un étage ne remplace pas le précédent.** L'étage 1 est la seule mesure qui porte sur les
3 299 déplacements de la cohorte entière ; les étages 2 et 3 portent sur quelques dizaines de
foyers et ne mesurent **aucune part modale publiable** — ils mesurent un mécanisme. Les présenter
autrement serait le défaut que le 078 § 10 nomme déjà : douze agents n'ont jamais mesuré une part.

---

## 3. Étage 1 — le protocole à cinq conditions

Pour répondre aux objections classiques des relecteurs (*« le modèle obéit à une consigne
lexicale »*, *« il réagit à n'importe quel texte injecté »*, *« la comparaison est déloyale, la
référence tabulaire n'a rien reçu »*), chaque événement est joué sous **cinq conditions** sur les
mêmes déplacements de la cohorte scellée, mémoire éteinte, l'ordre des itinéraires proposés étant
retiré au hasard à chaque requête.

| # | Condition | Ce que le décideur reçoit | Ce que la condition sépare |
|---|---|---|---|
| **C1** | Agent, journée nominale | aucun article | le niveau de référence |
| **C2** | Agent, article brut | le texte de presse tel qu'il a paru | l'effet total de l'événement |
| **C3** | Agent, texte témoin | un texte d'actualité sans lien plausible avec le choix modal, apparié en longueur, le même pour les cinq | l'effet du contenu, de l'effet d'ajouter un texte |

**Trois conditions depuis le 2026-09-21, et non plus cinq.** L'ancienne C3 (paraphrase neutre) et
l'ancienne C5 (référence tabulaire à événement encodé) sont retirées par l'auteur ; l'ancienne C4
(texte témoin) prend le numéro C3. Toute référence à « C4 » ou « C5 » ailleurs dans ce ticket,
dans `plan.md` ou dans `tests.md` désigne l'ancienne numérotation et se lit avec cette phrase.
Attention : dans `specs/ticket_059/tests.md`, les identifiants C1 à C9 numérotent des **cas de
test du corpus**, pas des conditions du protocole — les deux séries ne se confondent pas.

**Le point de comparaison est un décideur à règles rigides qui ne lit pas.** Il ne figure pas au
tableau parce qu'il ne reçoit aucune des trois entrées ci-dessus. Aucune de ses variables ne bouge
entre la veille et le jour de parution, et sa part modale est donc identique des deux côtés. C'est
ce qui remplace l'ancienne C5 : au lieu de traduire l'événement dans l'offre pour voir ce que la
référence en fait, on montre qu'elle n'a pas d'endroit où répondre.

<!-- PÉRIMÉ le 2026-09-21, conservé parce que la règle 3 du protocole s'y lit : la condition C5
traduisait l'événement dans l'offre, liens coupés et fréquences dégradées, seul canal par lequel
un événement atteignait une référence tabulaire. La parade de La Machine s'y traduisait en
coupures de graphe, la rumeur des punaises pas du tout, et C5 y était identique à C1.
C5 n'existait que lorsque l'événement modifiait l'offre. Les 21 variables ne portant ni météo ni
durée, le seul canal par lequel un événement atteint une référence tabulaire est la règle 3 du
protocole : un mode retiré de l'offre sort de la prédiction, qui se renormalise sur les modes
restants. La parade de La Machine se traduit en coupures de graphe ; la rumeur des punaises de lit
ne se traduit pas, et **C5 y est identique à C1**. Ce n'est pas une faiblesse du protocole, c'est
la mesure elle-même — et elle se publie plutôt qu'elle ne se suppose. -->

---

## 4. Le corpus gelé, la grille, et les critères de réfutation

### 4.1 Corpus pré-enregistré

Le corpus complet de **30 scénarios réels** avec liens sources archivés et sélection du **Top 5
d'expertise comportementale** est pré-enregistré dans
[`docs/paper/sources/actualites/RAPPORT_SCENARIOS_QUALITATIFS_TOULOUSE.md`](../paper/sources/actualites/RAPPORT_SCENARIOS_QUALITATIFS_TOULOUSE.md).
Les 30 sources sont archivées en HTML et PDF sous `articles_html/`, avec `index_articles.json`.

Ce rapport définit a priori la matrice des élasticités quadri-modales attendues (voiture, vélo,
marche, TC) cotées de 0 à 3 étoiles, **gelée avant la campagne de requêtes**.

### 4.2 Ce qui manque encore au gel, et qui se fait sans un appel au modèle

| # | Manque | Constat |
|---|---|---|
| M1 | **`articles_txt/` n'existe pas.** `experiments.yaml` l'annonce, le dépôt ne l'a pas | les textes de C2, C3 et C4 ne sont écrits nulle part ; seuls les HTML bruts sont archivés |
| M2 | **Trois cellules sur vingt sont ambiguës** dans le rapport | marche sous La Machine (« polarité duale »), voiture sous la grève des éboueurs (« ralentissement et contournement »), marche sous VélôToulouse (« réduction d'effort ») |
| M3 | **Aucun texte témoin n'est choisi** | C4 demande cinq articles locaux réels, appariés en longueur, sans lien plausible avec la mobilité |
| M4 | **Aucune paraphrase n'est écrite ni vérifiable** | C3 n'a de sens que si le retrait du lexique de mobilité est **contrôlable**, pas affirmé |
| M5 | `experiments.yaml` porte encore les trois événements antérieurs | Minotaure, canicule, coupure de rocade, lignes 459 à 790, sur `gemini-3.1-flash-lite` |

⚠ **M2 est le point dur.** « Polarité duale » n'est pas un signe : c'est deux signes opposés selon
le motif du déplacement. Deux issues, et il faut en choisir une **avant** le premier appel :
soit la cellule se dédouble en deux prédictions conditionnées au motif (loisir *vs* travail), et
la grille passe de 20 à 22 ou 23 signes ; soit elle se déclare **« pas d'effet net attendu »**,
ce qui est une prédiction falsifiable en soi — un déplacement significatif dans un sens ou dans
l'autre la réfute. La seconde est plus honnête et moins coûteuse. Ce qui n'est pas admissible,
c'est de lire le signe après la mesure.

### 4.3 Métriques de validation directionnelle

1. **Taux d'accord de signe $S_{\text{sign}}$** : part des déplacements modaux observés dont la
   direction concorde avec la prédiction pré-enregistrée. Sur vingt prédictions, la barre du test
   binomial contre le hasard se situe à **quinze** signes concordants ($p = 0{,}021$) ; quatorze
   ne suffisent pas ($p = 0{,}058$).
2. **$\kappa$ pondéré** sur l'intensité ordinale (0 à 3 étoiles). Publié **sans être testé** :
   vingt items ne le permettent pas.

### 4.4 Critères formels de réfutation de $H_3$

$H_3$ (adaptation contextuelle écologique supérieure de l'agent à mémoire) est réfutée si :

1. le **texte témoin** (C3, ex-C4) produit une perturbation modale d'amplitude comparable à
   l'article actif — défaut de spécificité ;
2. aucun **décrochage** ne suit la parution, ou le retour ne suit pas le décrochage — la forme
   annoncée par le chapitre 7 n'est pas produite ;
3. le signe observé contredit la grille sur la majorité des cellules.

⚠ **Le critère n° 2 a changé le 2026-09-21.** Il portait la paraphrase neutre : « la paraphrase
détruit la réallocation modale sur la majorité des cellules — l'agent exécute un ordre lexical,
il ne raisonne pas. » Cette condition est retirée du protocole, et **l'objection lexicale n'a
donc plus de contrôle**. Elle se traite au chapitre des limites ou par le corpus, pas par une
condition ; c'est la Q21 des questions vivantes. Le critère n° 2 est remplacé par la forme, que
le chapitre 7 revendique désormais explicitement.

⚠ **La barre des quinze signes sur vingt ne s'applique plus.** Elle supposait un test binomial
sur la cohorte entière ; l'étage 1 a disparu, et les vingt cellules se lisent sur quelques
foyers, sans test. Le taux d'accord se publie tel quel.

⚠ **Il manque un quatrième contrôle, et il ne coûte rien** : le **rejeu à l'identique** de la
journée nominale, qui donne le bruit propre du décideur. Sans lui, « C4 déplace moins que C2 » se
compare à zéro au lieu de se comparer au bruit. Le ticket 080 § 3.1 bis le décrit comme prêt sans
code. Le plancher mesuré le 2026-09-21 sur l'agent à mémoire — **1 écart de mode sur 31 décisions
appariées, soit 3,2 %** (095 § 7 bis) — dit que ce bruit n'est pas nul et qu'il se déclare.

---

## 5. Étage 2 — un article n'est pas un choc, et c'est tout le problème

### 5.1 Le trou technique, chiffré

Le [079](ticket_079_chocs_declares_vecus_par_les_agents.md) a livré le canal qui manquait : un
choc, c'est **un retard chiffré** plus **une phrase vécue**. La gravité qui en découle décide de
tout le reste sans une ligne de plus — force du souvenir, vivier de rappel, durée de service dans
le bloc « Ce qui a changé récemment ».

Un article de presse **ne fait subir aucun retard**. Passé tel quel par le canal du 079 :

| | Choc C3 (panne du réseau) | Article « punaises de lit » |
|---|---:|---:|
| Retard subi | 45 min → composante 0,50 | **0 min → 0,00** |
| Correspondance ratée | 0,20 | 0,00 |
| Incident réseau | 0,20 | 0,00 |
| **Gravité** | **0,90** | **0,00** |
| Force du souvenir | 17,9 j | **2,8 j** |
| Servi dans le bloc jusqu'à | ~19 j | **~3 j** |

**Un article lu sortirait du prompt le surlendemain.** L'étage 2 n'aurait rien à mesurer, et son
silence serait pris pour une absence d'effet — exactement le défaut que le lot B du 095 a trouvé
dans l'enquête du soir avant qu'elle ne tourne.

### 5.2 La gravité d'une information : l'agent décide — arrêté le 2026-09-21

Trois options avaient été pesées, dont une constante unique à 0,70 pour les cinq articles.
**L'auteur les a toutes écartées : c'est l'agent qui juge ce qu'il vient de lire.**

Ce n'est pas un mécanisme à inventer, et c'est ce qui rend la réponse bonne marché. `llm/gravite.py`
sépare déjà deux sources et les arbitre :

> les **entrées brutes** reçoivent une gravité déterministe, calculée depuis ce que la simulation
> mesure ; les **concepts** reçoivent un niveau nommé jugé par le modèle. Et une règle de sécurité
> les arbitre : `I = max(I_llm, I_det)` — le fait mesuré l'emporte toujours sur le jugement.

Un article ne porte **aucun fait mesuré** : ni retard, ni correspondance ratée, ni contrainte de
mode. Son terme déterministe vaut donc zéro, et `max(I_llm, 0) = I_llm` : **le jugement décide
seul, sans qu'aucune règle nouvelle soit écrite.** Le cas de la presse est le cas limite d'une
mécanique qui existe, pas une exception qu'on lui ajoute.

L'échelle est celle des cinq échelons, ancrés par une conséquence observable et non par une
intensité ressentie — c'est ce qui rend comparables un article du jour 9 et un retard du jour 3 :

| Échelon | Ancre | Gravité | Durée servie |
|---|---|---:|---:|
| anodin | *Everything went as I had planned.* | 0,10 | 4 j |
| notable | *A noticeable deviation, with no consequence.* | 0,30 | 8 j |
| gênant | *It cost me time, or forced me to shift a schedule.* | 0,50 | 11 j |
| grave | *It made me miss something, or put me in difficulty.* | 0,75 | 16 j |
| marquant | *I will remember this in a month; it changes how I travel.* | 1,00 | 23 j |

**Trois gains, et ils comptent pour l'article.**

1. **La durée de l'effet cesse d'être un réglage.** C'est exactement ce que le lot A du 095
   cherchait pour les chocs, obtenu ici sans constante à défendre devant un relecteur.
2. **Deux agents ne retiennent pas la même chose du même article**, et l'écart se mesure. La
   distribution des échelons devient une sortie de l'expérience : *comment cinq personnes
   reçoivent-elles le même texte ?* Aucune constante ne pouvait produire cette grandeur.
3. **Un article peut ne rien faire.** Si tous les lecteurs le jugent anodin, l'effet est faible et
   court. C'est un résultat, il s'accepte d'avance, et il ne se corrige pas en remontant un
   paramètre.

### L'échelle — arrêtée par l'auteur le 2026-09-21

Les cinq échelons du dépôt mesurent une **intensité de contrariété** : anodin, notable, gênant,
grave, marquant. Ils suffisent pour un retard subi, qui ne peut que dégrader une journée. Ils ne
savent pas dire qu'un article est une **bonne** nouvelle — or le lancement du vélo partagé en est
une, et la grille lui prédit un signe positif sur le vélo. Une échelle qui ne descend jamais en
dessous de zéro ne peut pas porter la moitié du corpus.

L'agent note donc sur une échelle **signée**, et il dit **quels modes** sont touchés :

| Libellé servi au modèle | Valeur | Importance en mémoire |
|---|---:|---:|
| à ne pas manquer | **+1,00** | 1,00 |
| génial | +0,75 | 0,75 |
| super | +0,50 | 0,50 |
| bien | +0,25 | 0,25 |
| on s'en moque | **0,00** | 0,10 |
| préoccupant | −0,25 | 0,25 |
| gênant | −0,50 | 0,50 |
| effrayant | −0,75 | 0,75 |
| très grave | **−1,00** | 1,00 |

Deux grandeurs sortent d'un seul jugement, et elles ne servent pas à la même chose :

- **l'importance** — la valeur absolue — alimente la mémoire telle quelle. `gravite_concept(|v|, 0)`
  rend `|v|`, la force suit, la durée de service aussi. Rien à écrire de plus.
- **le signe, par mode** — c'est la nouveauté, et c'est ce qui rend le jugement confrontable. La
  grille pré-enregistrée prédit vingt signes ; l'agent en produit un par mode qu'il nomme. **On
  peut donc comparer ce que l'agent dit du texte à ce que la grille prédit, sans attendre qu'il
  se déplace.**

C'est un troisième niveau de mesure, qui n'existait dans aucune version antérieure du protocole :

| Niveau | Grandeur | Ce qu'il dit |
|---|---|---|
| 1 | part modale observée | ce que l'agent **fait** |
| 2 | scores d'affinité de l'enquête du soir (095, lot B) | ce que l'agent **croit** |
| **3** | **signe et intensité déclarés à la lecture** | ce que l'agent **a compris du texte** |

Un désaccord entre les niveaux 3 et 1 est le résultat le plus intéressant que ce ticket puisse
produire : l'agent a lu correctement — il annonce le bon signe — et ne se déplace pas pour autant.
C'est exactement l'écart que le chapitre 6 mesure entre déclaration et comportement, transposé à
un texte que nulle variable ne code.

⚠ **Le jugement ne remplace pas la grille.** Un agent qui déclarerait « très grave, mode voiture »
sur l'article des punaises se tromperait, et c'est mesurable. Le taux d'accord entre les signes
déclarés et la grille devient une sortie à part entière — et un accord parfait serait suspect
avant d'être rassurant : il dirait que le modèle relit la grille dans le texte.

**Deux points restent à trancher**, et ils sont au § 13 :

- **quand** le jugement est demandé — à la lecture, par un appel dédié, ou le soir à la
  consolidation. La proposition est *à la lecture* : le soir, l'entrée aurait déjà vécu la journée
  à gravité nulle, donc n'aurait pas pesé sur les décisions du jour de parution, celui-là même où
  l'article est censé agir (Q16) ;
- **que faire d'un échelon hors grille.** `gravite_jugee` rend `None` et retombe sur le
  déterministe, qui vaut zéro ici : un article s'effacerait en trois jours parce que le modèle a mal
  répondu, et l'effet nul se lirait comme un résultat. Proposition : refus explicite et `[ALARME]`,
  jamais de repli silencieux (Q17).

⚠ **Ce que cela coûte en contrepartie.** La gravité devient une variable aléatoire du dispositif,
donc les bras ne sont plus comparables sur ce terme : deux runs du même article peuvent donner deux
durées. C'est le prix d'une durée qui n'est plus un paramètre, et il se paie en journalisant
l'échelon de chaque lecteur — sans quoi une différence entre bras serait inexplicable.

### 5.3 Le point d'injection : le matin, avant la première décision

Le choc du 079 s'applique **à l'arrivée**, après la décision — c'est ce qui rend le jour du choc
muet sur le choix. Un article ne peut pas suivre ce chemin : il est **lu le matin**, et le
chapitre 7 § 7.1 le dit déjà (*« un article paru le matin »*). L'agent doit décider **en le
sachant**.

Conséquence de code : le canal `information` ne se branche pas au même endroit que le canal
`choc`. Le point disponible est la bascule de journée du contrôleur, à 3 h simulées, au voisinage
de `_ecrire_point_de_reprise` et du déclenchement de l'enquête du soir
(`simulation_controller.py`, ≈ l. 1760-1795) — c'est-à-dire **avant** le réveil de tout agent.

⚠ **Deux régimes se séparent ici, et il faut le dire dans l'article.** Le choc du 079 est *subi*
et laisse le jour du choc muet. L'article est *su avant de décider* : le jour de parution mesure
donc bien un choix. C'est le régime « anticipé » que le 079 § 3 avait explicitement laissé de
côté — sauf qu'ici il ne demande **aucune dégradation de l'offre** : le monde ne change pas, seule
l'information change. C'est la version la moins chère et la plus propre du régime anticipé, et
elle tombe dans le périmètre de ce ticket.

### 5.4 Ce que l'agent reçoit exactement

Une entrée de mémoire, portée à la première décision du jour de parution, dans les mots de
l'agent, jamais en consigne :

```
[ PRESSE ] Ce matin, j'ai lu dans le journal : « Face aux signalements répétés sur les
réseaux sociaux concernant la présence supposée de punaises de lit sur les sièges en tissu
du métro toulousain, Tisséo multiplie les opérations de désinfection vapeur. […] »
```

**Les trois gardes de contenu du 079 s'appliquent, et une quatrième s'ajoute.**

| Garde | Refusé au chargement |
|---|---|
| Pas de consigne | « évite le métro demain » |
| Pas de verdict | « ce réseau n'est pas fiable » |
| Pas d'intention | « à partir de maintenant je prendrai la voiture » |
| **Pas de réécriture** *(nouvelle)* | le texte de C2 doit être **identique** au texte archivé, à l'empreinte près |

La quatrième garde n'existe pas pour les chocs et elle est indispensable ici : un `vecu` est écrit
par nous, un article est **cité**. Une reformulation « qui rend le texte plus lisible pour le
modèle » ferait de C2 une sixième condition non déclarée. L'empreinte du texte injecté se
journalise à côté de celle du fichier source.

### 5.5 La prédiction la plus intéressante : l'évitement se protège lui-même

Le monde simulé ne change pas. Un agent qui, sur la foi de l'article, cesse de prendre le métro
**ne prendra plus jamais le métro nominal qui aurait démenti sa croyance**. Or le 095 a établi que
le retour se fait par **contradiction**, pas par oubli : la croyance née de la lecture vaut 0,50
(succession de Laplace, aucune observation à son actif) et une seule contradiction la fait tomber
à 0,33, hors service.

Il en découle une prédiction signée, falsifiable, et qu'aucune des cinq conditions de l'étage 1 ne
peut produire :

> **L'effet s'éteint d'autant plus vite que l'agent a continué d'utiliser le mode visé.** Chez
> ceux qui l'évitent complètement, aucun démenti n'arrive, et l'effet ne s'éteint que par l'usure
> de la fenêtre — donc à la date que la constante de gravité prédit, et pas avant.

**Ce qui la falsifierait :** une extinction simultanée chez les évitants et les persistants (le
retour ne vient pas de la contradiction), ou une extinction chez les évitants **avant** la date
prédite par la force du souvenir (une autre mécanique agit, et il faut la trouver).

⚠ Cette prédiction a une conséquence de protocole : **il faut des agents pour qui le mode visé
n'est pas substituable**. Un captif du métro sans permis continuera de le prendre, et fournira les
contradictions ; un automobiliste abonné pourra l'éviter à coût nul. Les deux profils doivent
être présents dans l'échantillon, et la mesure se stratifie sur eux.

---

## 6. Étage 3 — la diffusion dans le foyer

### 6.1 Le constat qui commande tout le reste : en l'état, un article NE se diffuse PAS

Le [078](ticket_078_partage_de_concepts_au_sein_du_foyer.md) fait du foyer un canal, à la
consolidation journalière, sans un appel de modèle supplémentaire. Deux de ses règles bloquent
l'article, et il faut les lire ensemble :

- **§ 1 — seuls les concepts passent.** Une entrée épisodique (« j'ai lu ce matin que… ») reste
  strictement personnelle. L'article lui-même ne traverse jamais.
- **R1 — l'ancrage : `observations ≥ 1`.** Un concept né de la consolidation du soir part à
  **zéro observation**. Seul un `confirmer` l'incrémente, c'est-à-dire seule une journée où
  l'agent a **revécu la chose**. Une croyance née d'une lecture ne repart donc pas dans le foyer
  tant que son porteur ne l'a pas vérifiée par un déplacement réel.

✅ **RÉSOLU par la décision D1 du ticket 100** (auteur, 2026-09-21), et le § 6.2 tombe avec.
L'auteur avait redemandé cette diffusion explicitement — *« il doit partager ces souvenirs avec
sa famille »* — et les deux règles ci-dessus l'empêchaient. La sortie n'a été aucune des trois
envisagées en Q18 : **un second canal a été ouvert**. Le *récit du soir* porte tous les épisodes
de la journée de chaque membre, sans condition d'ancrage, lecture du matin comprise. Il n'y a
donc plus rien à lever, et plus de seuil à mettre à zéro.

**L'ancrage reste, et il gouverne un autre canal.** R1 continue de s'appliquer aux **croyances** :
une croyance ne circule qu'ancrée dans un déplacement réel — le 078 § 4.1 l'écrit pour les
conversations, et cela vaut mot pour mot pour la presse. Ce qui a changé, c'est que le récit du
soir n'est pas une croyance : c'est une citation de ce que l'autre a écrit de sa journée.

**Ce que cela fait à la prédiction de délai**, qui faisait tout l'intérêt de l'étage 3 — elle
raccourcit, et elle reste réfutable :

> Le co-résident n'entend pas une croyance ancrée, il entend le **bilan du soir** du lecteur, dès
> le soir de la parution. La séquence attendue devient : parution → décision du lecteur dans la
> journée → récit du soir → consolidation du co-résident la même nuit → **sa première décision le
> lendemain au plus tôt**. Quatre jalons, dans cet ordre, datés.

**Ce qui la falsifierait :** un co-résident qui bouge **le jour même de la parution**, avant le
soir. Il n'a rien pu entendre à ce moment-là : le canal observé ne serait alors pas la mémoire,
et le § 6.3 nomme le suspect.

### 6.2 ~~Deux régimes d'ancrage~~ — RETIRÉ le 2026-09-22

Ce paragraphe posait deux bras, en faisant varier `memoire__partage_foyer_observations_min` : un
bras **ancré** (seuil 1) et un bras **ouï-dire** (seuil 0), pour mesurer ce que l'ancrage évite.

**Il n'a plus d'objet.** D1 du ticket 100 fait porter au récit du soir tous les épisodes de la
journée, sans condition d'ancrage : ce que le bras ouï-dire cherchait à observer — qu'une
information circule sans avoir été vérifiée — se produit désormais dans le régime nominal. Il
n'y a plus de seuil à mettre à zéro pour l'obtenir.

⚠ **Le réglage reste dans le code, et R1 avec lui.** L'ancrage continue de gouverner la
circulation des **croyances**, qui est un canal distinct du récit. Ce qui disparaît est le bras
d'expérience, pas la règle — et la question que le bras posait reste ouverte, mais elle se pose
maintenant sur le **saut unique** de D2 : ce qui est entendu ne repart jamais, même confirmé
ensuite. C'est cela qui empêche l'amplification, et non plus l'ancrage seul.

⚠ **Le second bras est une mesure, pas une option.** Sans lui, « l'ancrage protège de la chambre
d'écho » est une affirmation de conception, pas un résultat. Avec lui, la mesure n° 3 du 078 —
reformulation circulaire, concepts distincts partageant des mots-clés dans un même foyer et un
même panier `(mode, motif)` — a enfin deux régimes à comparer.

### 6.3 Le confondant qu'il faut tuer avant de mesurer : la voiture du foyer

Le chaînage des véhicules est **actif** depuis le 2026-09-21. Si le lecteur cesse de prendre la
voiture, **il la libère** pour son co-résident, dont les options changent sans qu'aucune
information n'ait circulé. Un effet mécanique se lirait alors comme un effet informationnel, et
la figure de diffusion serait fausse dans le sens qui arrange.

Trois parades, à combiner :

1. **Choisir l'article et les foyers de sorte que le mode visé ne soit pas un véhicule partagé.**
   L'article « punaises de lit » vise les transports collectifs : nul ne les libère en n'y montant
   pas. C'est la raison de fond pour en faire **le premier article joué**.
2. **Un bras à chaînage coupé**, si un article vise la voiture ou le vélo. Il diverge du bras
   nominal par autre chose que l'information, et cela se déclare.
3. **Journaliser la cause de chaque contrainte de mode** (`retour_force`, `sortie_bloquee`,
   `passager`) chez le co-résident, jour par jour. Un changement de mode concomitant à une
   contrainte de chaîne **ne compte pas** comme diffusion. Le champ existe déjà dans la gravité
   (`CONTRAINTES_MODE_FORCE`) ; il faut le porter dans la sortie de mesure.

### 6.4 Deux rôles, et le témoin n'est plus exigé (révisé le 2026-09-22)

| Rôle | Définition | Ce qu'il mesure |
|---|---|---|
| **Lecteur** | membre désigné d'un foyer exposé, reçoit l'entrée `[ PRESSE ]` | l'effet direct |
| **Co-résident** | autre membre du **même** foyer, ne reçoit rien | la diffusion |

**Un seul lecteur par foyer.** On lit le journal seul ; et un foyer où tout le monde a lu n'a plus
de co-résident, donc plus rien à mesurer. Le lecteur est désigné par tirage à graine fixe parmi
les membres mobiles du foyer, et **le tirage est journalisé**.

**Le foyer témoin non exposé n'est plus obligatoire** (décision de l'auteur, 2026-09-22). Le
chapitre ne l'annonce plus, et le ticket cesse de l'exiger — y compris l'exigence qu'il soit dans
le même run. Les foyers exposés peuvent donc être joués seuls.

⚠ **Ce que le témoin portait ne disparaît pas pour autant, et ne se devine pas.** Le 095 § 7 bis
a mesuré un plancher de bruit **non nul** entre deux bras identiques : 1 écart de mode sur 31
décisions appariées. Un écart plus petit que ce plancher n'est pas un effet. Sans témoin dans le
run, ce plancher ne s'y lit plus : il faut le reprendre du 095, ou le réétablir par un rejeu à
l'identique, et **le déclarer avec le résultat**. `scripts/analysis/presse/scoring.py` l'exige
déjà comme paramètre (`plancher_de_bruit`) : il ne se tait pas, il se déclare.

⚠ **Un foyer témoin lancé séparément ne vaut pas un témoin interne.** Si l'on en reprend un un
jour, il faudra qu'il soit dans le même run : comparer deux runs distincts ferait entrer le
plancher de bruit dans l'effet mesuré. C'est la raison qui avait fait choisir le témoin interne,
et elle reste vraie — c'est l'exigence qui tombe, pas la raison.

---

## 7. Le plan d'expérience

### 7.1 Le calendrier d'un run

L'utilisateur propose deux ou trois jours de simulation avant la parution. **C'est insuffisant, et
pour une raison mesurable**, pas par prudence : la conformité à l'habitude se calcule sur les
**cinq dernières observations de la même activité** (ticket 093). Une activité quotidienne atteint
cinq observations au cinquième jour ouvré ; une activité qui n'a lieu que deux fois par semaine
n'y arrive qu'à la troisième semaine. À trois jours, aucune habitude n'est formée, et « rupture
d'habitude » ne veut rien dire.

Calendrier proposé, ancré sur le lundi de la simulation :

| Jour | Ce qui se passe | Pourquoi ce jour |
|---:|---|---|
| J1-J12 | baseline, aucun article | l'habitude par activité est formée au J7 pour les activités quotidiennes ; J12 laisse une marge |
| **J12** | **jalon d'enquête** — l'état avant | dernier jour ouvré de la baseline, comme au 095 |
| **J13** | **parution**, au matin, avant la première décision | mardi ; jamais un lundi, où la reprise de la veille est déjà atypique |
| J14-J16 | fenêtre de diffusion attendue | la séquence des cinq jalons du § 6.1 s'y déroule |
| **J17** | **jalon d'enquête** — l'état chaud | quatre jours après parution |
| J17-J27 | extinction | la constante 0,70 prédit une sortie de fenêtre au J28 |
| **J28** | **jalon d'enquête** — le jour prédit de sortie | le seul jalon dont la date est une **prédiction** |
| J29-J35 | après | |
| **J35** | **jalon d'enquête** — l'état froid | assez tard pour lire une trace permanente |

`EXPERIMENT_SURVEY_DAYS="12,17,28,35"`. Les jalons se déclarent, ils ne se codent pas en dur — la
leçon est déjà écrite dans `enquetes.py`.

⚠ **Ce calendrier est celui de la mesure (P2 et P3), pas celui de la mise au point.** P0 et P1 le
compriment — baseline J1-J8, parution J9, observation jusqu'à J25 — et P0 coupe l'enquête. Un
calendrier court ne forme pas l'habitude, et c'est assumé : ces deux paliers ne mesurent pas une
habitude, ils vérifient qu'une mécanique s'allume et donnent une variance. § 7.3.

### 7.2 Un article à la fois — et les blocs seulement à la fin

Une version antérieure de ce ticket proposait de jouer les **cinq articles dans un seul run**, sur
cinq groupes de foyers disjoints. L'argument tenait : le foyer étant le seul canal entre agents,
aucun effet ne traverse d'un bloc à l'autre, et le coût se divisait par cinq.

**L'auteur l'a écarté comme mode de travail le 2026-09-21, et il a raison.** Un run à cinq blocs
ne se débogue pas : une anomalie dans un bloc oblige à tout rejouer, cinq articles compris, et la
facture d'appels se paie à chaque itération. On ne met pas cinq expériences dans le même run tant
qu'on n'est pas certain qu'une seule tourne.

**Règle d'ordre, et elle ne s'inverse pas :**

| Étape | Forme | Ce qu'on y cherche | Ce qui autorise la suivante |
|---|---|---|---|
| Mise au point | **aucun run** — tests unitaires | format, gardes, exposition, empreinte, construction du bloc | la suite au vert |
| Plomberie | **1 article, 4 agents, 12 jours** | l'entrée entre-t-elle, le concept naît-il, le foyer l'entend-il | les trois observés au moins une fois |
| Mécanisme | **1 article**, une vingtaine d'agents | délai de diffusion, extinction, **variance** | un effet au-dessus du plancher de bruit |
| Mesure | **1 article à la fois**, effectif dimensionné sur la variance ci-dessus | l'effet et son intervalle | le premier article a montré quelque chose |
| Campagne | **les cinq en blocs disjoints**, un seul run | les vingt signes en régime longitudinal | plus rien n'itère |

Le plan en blocs reste donc au dossier, **mais comme forme finale**, jouée une fois, quand le
protocole est gelé. Ses trois conditions restent celles du § 7.2 d'origine : analyse par bloc
jamais sur la part globale, inférence par grappe au niveau du foyer, affectation des foyers aux
blocs tirée à graine fixe et appariée sur ce qui compte pour l'article.

⚠ **Un deuxième article ne se joue pas parce qu'il est prêt, mais parce que le premier a montré
quelque chose.** Cinq articles qui ne déplacent rien coûtent cinq fois le prix d'un seul qui ne
déplace rien.

### 7.3 Combien ça coûte, poste par poste — et où est le vrai gros poste

La réaction de l'auteur au premier dimensionnement était « ça va coûter cher ». Le chiffrage
ci-dessous lui donne raison sur un poste, et pas celui qu'on croit : **les runs GAMA ne sont pas
le problème, l'étage 1 l'est.**

Base de calcul : **6,2 requêtes par agent-jour** en run GAMA, relevé sur la campagne du 095
(≈ 122 décisions, 105 à 123 réflexions STM, 13 auto-réflexions et 20 enquêtes pour un agent sur
42 jours). Et **une requête par déplacement et par condition** hors simulateur.

#### Étage 1 — le poste à surveiller

La cohorte porte 3 299 déplacements. C1 se joue **une seule fois** pour les cinq articles ; C5 est
tabulaire et ne coûte aucun appel. Reste C2, C3 et C4, soit trois conditions par article :

| Périmètre | Calcul | Requêtes |
|---|---|---:|
| Cohorte entière, cinq articles | 3 299 + 3 × 5 × 3 299 | **52 784** |
| Cohorte entière, un article | 3 299 + 3 × 3 299 | 13 196 |
| **600 déplacements stratifiés, cinq articles** | 600 + 3 × 5 × 600 | **9 600** |
| **200 déplacements, un article, C1 et C2 seuls** | 200 + 200 | **400** |

**52 784 requêtes, c'est vingt-six jours de campagne au plafond de 2 000 par jour** — pour une
mesure dont on ne sait pas encore si elle déplace quoi que ce soit. L'escalier suivant s'impose, et
chaque marche décide de la suivante :

| | Périmètre | Conditions | Requêtes | Décide |
|---|---|---|---:|---|
| **E1-a** | 200 déplacements, 1 article | C1, C2 | **400** | l'effet existe-t-il, et de quelle taille |
| **E1-b** | les mêmes 200 | C3, C4 | **400** | est-il spécifique — sans quoi rien d'autre ne vaut |
| **E1-c** | 600 déplacements, 5 articles | C1 à C4 | **9 600** | les vingt signes |
| **E1-d** | cohorte entière | C1 à C4 | 52 784 | **ne se lance que si un relecteur l'exige**, ou si E1-c laisse un intervalle trop large |

⚠ **E1-a et E1-b coûtent 800 requêtes à eux deux**, soit moins d'une demi-journée de quota. C'est
le premier chiffre du chapitre 7 qui devient atteignable, et il l'est cette semaine.

⚠ **Le sous-échantillon se stratifie, il ne se tire pas au hasard.** 200 déplacements pris au
hasard dans 3 299 peuvent ne contenir aucun trajet du mode que l'article vise. La strate se
déclare avant le tirage : mode de référence, motif, tranche horaire, zone de résidence. La graine
est journalisée, et **les mêmes déplacements servent à toutes les conditions** — c'est
l'appariement qui fait la puissance, pas l'effectif.

#### Étages 2 et 3 — les runs GAMA, revus à la baisse

| | Foyers exposés | Foyers témoins | Agents | Jours | Enquête | Requêtes |
|---|---:|---:|---:|---:|---|---:|
| **P0 — la plomberie** | 1 | 1 | **4** | 12 | coupée | **~300** |
| **P1 — le mécanisme** | 6 | 4 | **20** | 25 | 3 jalons | **~3 100** |
| **P2 — la mesure**, un article | 16 | 10 | ~55 | 30 | 4 jalons | **~10 200** |
| **P3 — la campagne**, cinq articles en blocs | 60 | 12 | ~200 | 35 | 4 jalons | ~43 000 |

Le dimensionnement précédent partait à 12 foyers exposés pour P1 et à 12 000 requêtes ; **P1 tombe
à 20 agents et 3 100 requêtes** en tenant deux règles :

- **Des foyers de taille 2 uniquement** en P0 et P1. Un lecteur, un co-résident, et rien d'autre à
  démêler. Les foyers de quatre ou cinq disent si un énoncé atteint tout le monde ou s'arrête au
  premier — c'est une question de P2, pas de mise au point. La v6 en porte 122 de taille 2 parmi
  les 217 exploitables, le vivier n'est pas contraignant.
- **Vingt-cinq jours au lieu de trente-cinq** en P1 : baseline J1-J8, parution J9, observation
  jusqu'à J25. L'extinction prédite par la constante 0,70 tombe au J24, elle reste dans la fenêtre.
  L'habitude n'est formée que pour les activités quotidiennes — c'est assumé, P1 ne mesure pas
  l'habitude, il mesure un délai et une variance.

#### Ce que le debug ne coûte pas

**L'essentiel de la mise au point ne consomme aucun appel.** Le 079 a livré son canal avec 34 tests
et zéro run. Se testent sans simulateur et sans modèle : le format de déclaration et ses refus, les
quatre gardes de contenu, les trois règles d'exposition, le tirage du lecteur et sa graine, la
construction du bloc du foyer et ses six règles, l'empreinte du texte injecté, les colonnes du
sixième CSV, et le calcul des jours relatifs à la parution.

Ce qui exige un run, et rien d'autre : que l'entrée `[ PRESSE ]` arrive **avant** la première
décision du jour, qu'elle survive au point de reprise de 3 h, et qu'un concept en naisse à la
consolidation du soir. C'est P0, et c'est 300 requêtes.

⚠ **Le cache reste coupé** (`CACHE=0`) pendant toutes ces campagnes : sa clé ne porte ni l'article
ni le souvenir, et une décision prise avant la parution serait resservie après. Il ne sert de toute
façon que 0 % en régime nominal — l'économie qu'on croirait faire n'existe pas.

### 7.4 Les foyers existent, et ils sont comptés

Mesuré sur `data/population/toulouse_population_1000_AAMAS_v6.json` le 2026-09-21 :

| Vivier | Foyers | Agents |
|---|---:|---:|
| Ménages multi-membres | 287 | 788 |
| Multi-membres dont **tous** les membres sont mobiles | **217** | **590** |
| ↳ dont au moins un abonné TC **et** un non-abonné | 89 | 258 |
| ↳ dont au moins un avec vélo **et** un sans | 73 | 227 |
| ↳ résidant tous à Toulouse ville | 63 | 168 |
| ↳ résidant tous en 1re couronne, au moins une voiture | 85 | 230 |
| Sans aucune voiture dans le foyer | 16 | 47 |

Tailles des 217 foyers exploitables : 122 à deux membres, 48 à trois, 33 à quatre, 14 à cinq.

**Le vivier n'est jamais le facteur limitant** — le quota l'est. P0 demande 2 foyers, P1 en
demande 10, P2 en demande 26, tous de taille 2 : la v6 en porte **122**. Les foyers à quatre ou
cinq disent si un énoncé atteint tout le monde ou s'arrête au premier ; cette question appartient à
P2 et à P3, où la stratification par taille se déclare avant le tirage. En P0 et P1, **taille 2
uniquement** : un lecteur, un co-résident, rien d'autre à démêler.

⚠ **Les 16 foyers sans voiture sont précieux** : ils rendent le confondant du § 6.3 structurellement
impossible. Ils sont trop peu nombreux pour porter un bloc à eux seuls, mais ils font un
sous-groupe de contrôle qu'il faut nommer et suivre séparément.

### 7.5 Ce qui invalide la campagne, écrit avant

1. **Le plancher de bruit n'est pas chiffré.** Le 095 l'a mesuré sur **deux** témoins et un seul
   persona : 1/31. Il faut les trois ou quatre témoins supplémentaires que le 095 diffère, sinon
   aucun effet inférieur à ~5 points n'est attribuable. La campagne peut se préparer sans, elle ne
   se conclut pas sans.
2. **Un effet apparaît chez les témoins.** Les foyers du bloc T ne reçoivent rien ; tout écart
   systématique entre eux et l'avant-parution dit que quelque chose d'autre a bougé dans le run.
3. **La garde de vacuité.** Un accord intra-foyer calculé sur deux ou trois concepts sort parfait
   par absence de matière. Effectif minimal déclaré, verdict **« non concluant »** en dessous, sur
   le modèle de `slope_verdict` du ticket 031. *Dans ce dépôt, l'absence de mesure produit le score
   parfait* — c'est un motif récurrent, et il a déjà menti.
4. **L'écologie bouge à l'enquête.** Question témoin du lot B du 095 : aucun des articles ne la
   vise. Si elle bouge, l'agent a exprimé une humeur globale et l'instrument entier est invalide.

---

## 8. Ce qu'on mesure, et les figures

### 8.1 Les sorties

`make mesures RUN=…` écrit déjà cinq CSV (ticket 093). Il en faut **un sixième**, calqué sur
`choc_par_jour.csv` :

`presse_par_jour.csv` — clé `(jour, agent)` :

| Colonne | Ce qu'elle porte |
|---|---|
| `article_id`, `bloc` | quel texte, quel groupe de foyers |
| `role` | `lecteur` · `coresident` · `temoin` |
| `foyer_id` | l'unité de grappe de toute l'inférence |
| `jour_relatif_parution` | l'abscisse de toutes les courbes (−12 … +22) |
| `souvenir_article_servi` | l'entrée `[ PRESSE ]` était-elle dans le bloc noyau ce jour-là |
| `concepts_issus_lecture` | créés, confirmés, contredits, **et lesquels portent le mode visé** |
| `enonces_foyer_emis` / `_recus` | le volume du canal du 078, par nuit |
| `contrainte_chaine` | `retour_force` · `sortie_bloquee` · `passager` · vide — **le garde-fou du § 6.3** |
| `part_mode_vise` | la grandeur mesurée |

⚠ Les règles de lecture du 093 s'appliquent sans exception : la journée commence à 3 h, « la
veille » est le jour **vécu** précédent, une cellule vide n'est pas un zéro, et les jours relatifs
se redérivent des horodatages du journal — jamais d'une colonne écrite pendant le run.

### 8.2 Les six figures

Toutes en anglais, légende comprise, et toutes regénérables par script versionné — la figure se
livre avec l'analyse, pas après.

| | Figure | Ce qu'elle montre | Modèle existant |
|---|---|---|---|
| **F1** | **Part du mode visé par jour relatif à la parution**, trois courbes (lecteur, co-résident, témoin), IC bootstrap par foyer | l'effet et sa diffusion, d'un coup d'œil | `scripts/analysis/figure_fenetre_choc.py` |
| **F2** | **La chronologie de la diffusion** — une ligne par foyer, cinq jalons datés : parution, 1ʳᵉ décision infléchie du lecteur, ancrage du concept, énoncé transmis, 1ʳᵉ décision infléchie du co-résident | **la figure de l'étage 3** ; elle rend le délai visible et son absence aussi | à écrire |
| **F3** | **Profil d'enquête** — six critères × mode visé, par jalon, trois rôles ; l'écologie en filigrane | la croyance, pas seulement le comportement | lot B du 095 |
| **F4** | **Matrice des vingt signes**, prédit *vs* observé, cinq articles × quatre modes | l'étage 1, et le $S_{\text{sign}}$ | `ch7_presse.png` |
| **F5** | **Extinction *vs* usage** — date de sortie d'effet en fonction du nombre de trajets effectués dans le mode visé après parution | la prédiction du § 5.5 | à écrire |
| **F6** | **Opérations de concept cumulées**, lecteur *vs* co-résident *vs* témoin | où la croyance se forme, se confirme, se contredit | `memoire_par_jour.csv` |

**F3 est celle que l'utilisateur demande explicitement** : confiance dans les transports, confort,
sécurité. L'instrument existe déjà et il est aligné sur Adam & Gaudou (2025) — six critères,
Likert 0-10, un prompt par mode, plus un vecteur de priorités. L'article « punaises de lit »
prédit une chute du **confort** et de la **sécurité** du TC, et **aucun mouvement de la rapidité
ni du coût** : l'offre est intacte, rien dans le texte ne parle de durée ni de prix. C'est un test
de spécificité fort, et il ne coûte que vingt prompts par bras.

### 8.3 Les métriques, et le seuil sous lequel on ne conclut pas

| Métrique | Définition | Garde |
|---|---|---|
| $S_{\text{sign}}$ | accord de signe sur la grille gelée | ≥ 15/20, binomial |
| $\kappa$ pondéré | concordance ordinale des intensités | publié, non testé |
| **Délai de diffusion** | jours entre la 1ʳᵉ décision infléchie du lecteur et celle du co-résident | non concluant si moins de 6 foyers présentent les deux événements |
| **Écart lecteur/témoin** | points de part modale | doit dépasser le plancher de bruit, déclaré avec |
| **JSD intra-foyer** | divergence des perceptions déclarées entre membres d'un même foyer, comparée à l'inter-foyers | effectif minimal déclaré, verdict « non concluant » en dessous |
| **Taux d'énoncés stériles** | part des lignes du bloc foyer ne déclenchant aucune opération | indicateur de lecture, jamais un seuil qui agit |

---

## 9. Prédictions pré-enregistrées des étages 2 et 3

À recopier dans `specs/ticket_059/tests.md` **avant le premier run**, et à ne pas réécrire après
mesure.

| # | Prédiction | Ce qui la falsifie |
|---|---|---|
| **P1** | Chez le lecteur, la part du mode visé s'écarte du témoin dès le lendemain de la parution, d'une amplitude supérieure au plancher de bruit | un écart dans le bruit, ou de signe contraire à la grille gelée |
| **P2** | Le co-résident ne bouge **pas** avant l'ancrage du concept chez le lecteur | un co-résident qui bouge à J+1, ou en même temps que le lecteur → le canal n'est pas la mémoire (§ 6.3) |
| **P3** | L'effet s'éteint plus vite chez ceux qui ont continué d'utiliser le mode visé | extinction simultanée chez évitants et persistants |
| **P4** | À l'enquête, le confort et la sécurité du mode visé chutent ; la rapidité, le coût et **l'écologie** ne bougent pas | l'écologie bouge → instrument invalide, § 7.5 |
| **P5** | Le texte témoin (C4) ne déplace ni le comportement ni les scores déclarés | il en déplace autant que l'article → $H_3$ réfutée, § 4.4 |
| **P6** | Le bras « ouï-dire » (seuil 0) diffuse plus vite **et** produit plus de reformulations circulaires que le bras ancré | pas de différence → R1 ne protège de rien, et le 078 doit le dire |
| **P7** | La divergence intra-foyer des perceptions déclarées baisse dans les foyers exposés à partage actif, sans que baisse la divergence inter-foyers | tout le monde converge → c'est le modèle qui parle, pas les agents (078, § 6 n° 5) |

---

## 10. Ce qui est codable dès maintenant, sans attendre le 095

Sept lots, aucun ne touche la mémoire, aucun ne demande un run.

| Lot | Contenu | Coût | Dépend de |
|---|---|---|---|
| **0** | **Décisions de l'auteur** : les questions du § 13 | — | humain |
| **1** | **Le corpus textuel** — `docs/paper/sources/actualites/articles_txt/` : 5 textes bruts extraits des HTML archivés, 5 paraphrases sans indice modal, 5 témoins appariés en longueur, `MANIFEST.yaml` avec empreinte de chacun. **Plus un test de lexique** : une paraphrase qui contient un mot de mobilité (liste déclarée : métro, bus, vélo, voiture, marche, trottoir, chaussée, rame, ligne…) est **refusée**, pas signalée | M | lot 0 |
| **2** | **La grille gelée** — `grille_signes.yaml`, vingt (ou vingt-trois) cellules, un signe par cellule ou « pas d'effet attendu » explicite ; les trois cellules ambiguës du § 4.2 tranchées ; test de complétude | S | lot 0 |
| **3** | **L'étage 1** — `scripts/analysis/eval_presse_locale.py` : injection hors simulateur des cinq conditions, appariement sur les mêmes déplacements, $S_{\text{sign}}$, binomial, $\kappa$ pondéré, rejeu à l'identique pour le bruit. **C'est le ticket 064**, et il ne dépend que des lots 1 et 2 | L | 1, 2 |
| **4** | **Le canal `information`** — `llm/informations.py`, frère de `llm/chocs.py` : format YAML, exposition `foyers` \| `agents` \| `tirage`, injection à la bascule de journée, gravité constante déclarée, quatre gardes de contenu (§ 5.4), levée du refus de `experience.py:677-680` pour le seul `type: information`. Testable **sans run** | M | lot 0 |
| **5** | **La mesure** — `presse_par_jour.csv` (§ 8.1) dans `scripts/analysis/mesures/`, et le rôle porté jusque dans Prometheus | S | lot 4 |
| **6** | **La population** — `population_N_foyers_059` par `scripts/data/population/extraire_sous_population.py`, `MANIFEST.yaml` sur le modèle du 075, stratification déclarée, tirage du lecteur à graine fixe et journalisé | S | lot 0 |
| **7** | **Les figures F1, F2, F3** sur données de forme, avant tout run : une figure dont le script n'existe qu'après la mesure se taille sur ce qu'elle a trouvé | M | 5 |

### État au 2026-09-21

| Lot | État | Ce qui est au dépôt |
|---|---|---|
| **2** | **livré** | `grille_signes.yaml` gelée, 20 cellules avec motif et empreinte ; `scripts/analysis/presse/grille.py` ; 11 tests |
| **1** | **à moitié** | `extraire_textes.py` (extraire · sceller · verifier), les 5 articles en français et en anglais, les 5 paraphrases dans les deux langues, le lexique FR+EN, le chargeur, le README. **20 textes scellés sur 30 — il ne manque que les témoins** |
| **6** | **livré** | `extraire_foyers.py`, `population_20_foyers_059` (6 exposés, 4 témoins), 11 tests |
| **3** | **à moitié** | `scripts/analysis/presse/scoring.py` — écart apparié, accord de signe et binomial exact, kappa pondéré, garde de vacuité et plancher de bruit obligatoire ; 14 tests. Restent les sous-commandes `echantillon` et `jouer`, qui demandent le corpus complet |
| **4** | bloqué | Q1, Q2, Q5, Q6 |
| **5**, **7** | à faire | dépendent du lot 4 |

⚠ **C3 corrigée le 2026-09-21 — le sujet se nomme, les modes de report disparaissent.** La
première écriture interdisait tout mot de mobilité, sujet compris : elle racontait le lancement du
vélo partagé sans nommer le vélo. L'objection à réfuter n'est pas « le texte parle de transport »,
c'est « le texte dit à l'agent quel mode prendre ». Chaque article déclare donc ses mots exemptés —
métro et rame pour les punaises, vélo et station pour VélôToulouse, aucun pour les trois autres —
avec deux gardes : un mot ne s'exempte que s'il figure dans le texte brut, et aucun article
n'exempte un mode vers lequel son événement pousserait.

⚠ **Ce qui bloque le lot 1, et donc le lot 3 : les cinq textes témoins de C4.** Ils ne peuvent
pas venir du corpus des trente — celui-ci a été constitué article par article **pour** son lien
avec la mobilité, et un témoin doit n'en avoir aucun. Il faut cinq articles locaux neufs, sans
lien plausible avec le choix modal, appariés en longueur. C'est une collecte, et elle demande une
décision (Q14).

⚠ **Le lot 4 est le seul qui touche le chemin de production.** Il ajoute un canal ; il ne modifie
ni la gravité, ni l'oubli, ni les viviers, ni les concepts, ni un seuil. Drapeau éteint par défaut,
comme les autres leviers de mémoire, pour que tout ce qui a été mesuré avant reste comparable.

---

## 11. Ce qui attend, et ce que ça attend exactement

| Ce qui bloque | Ce qui est bloqué | Pourquoi |
|---|---|---|
| **095, E1** — plancher de bruit sur trois ou quatre témoins de plus | la **conclusion** de P1 et de l'écart lecteur/témoin | sans plancher chiffré, un écart de 5 points ne s'attribue pas |
| **095, E2 et E3** — la fenêtre dérivée vérifiée, la durée qui suit la gravité | l'étage 2 en entier | la constante de gravité du § 5.2 n'a de sens que si la durée en dérive réellement |
| **078, lots 1 à 3** — le repère `foyer_lu_jusqu_a`, le bloc du soir, les six règles, l'instrumentation | l'étage 3 en entier | le canal n'existe pas ; le 078 n'a aucun code |
| **078, lot 0** — `population_12_foyers_078` | rien ici — notre lot 6 est indépendant et vise d'autres foyers | à ne pas confondre : deux populations, deux objets |

**Ce que ce ticket n'attend pas :** les lots A, B, D et E du 095 sont **en service** (fenêtre
dérivée avec mode déclaré, enquête du soir à cinq prompts et bloc mémoire complet, filiation des
runs enfants, modèle journalisé par décision). Ce sont les **expériences** du 095 qui restent, pas
son code.

---

## 12. Documentation et article

### À écrire dans `docs/`

| Fichier | Ce qui s'y ajoute |
|---|---|
| `docs/arch/presse-locale.md` *(nouveau)* | le canal `information`, le format, les quatre gardes, le point d'injection, la constante de gravité et pourquoi elle est unique |
| `docs/arch/chocs-declares.md` | un renvoi : deux canaux, deux régimes — subi à l'arrivée, su au matin |
| `docs/arch/memory-stm-ltm.md` | ce qu'une entrée de lecture devient en mémoire, et pourquoi elle ne traverse pas le foyer sans ancrage |
| `docs/arch/mesures-personas.md` | le sixième CSV et les trois rôles |
| `docs/changelog.md` | à chaque lot livré, en haut, au format du dépôt |

⚠ **Un dossier de documentation ne se crée pas sans demander** ; `docs/arch/` existe, un fichier
de plus y entre sans cérémonie.

### Ce que l'article devra dire, et ce qu'il ne dit pas encore

Le chapitre 7 § 7.1 décrit **l'étage 1 seul**, et le fait bien. Rien n'y porte les étages 2 et 3.
Quatre ajouts se dessinent, aucun ne s'écrit avant qu'une mesure existe, et tous passent par le
verrou :

1. **Un § 7.1 bis** — la presse en régime longitudinal : l'article comme information sans
   dégradation de l'offre, la constante de gravité assumée et déclarée, la prédiction d'extinction
   par contradiction (§ 5.5).
2. **La limite du § 5.3 du manuscrit se déplace.** Le régime subi du 079 ne déclare l'événement
   qu'une fois, en langue. Le canal de presse le déclare aussi une seule fois, **mais l'agent le
   sait avant de décider** : c'est un régime distinct des deux que l'article nomme, et le texte
   doit l'écrire plutôt que de le laisser passer pour le même.
3. **La diffusion au foyer est une perspective du chapitre 8**, comme la note de travail du
   chapitre 7 le dit déjà pour le 078 — et elle y gagne une figure (F2) le jour où la mesure
   existe.
4. **Les trois cellules ambiguës** de la grille : la décision du § 4.2 change le dénominateur du
   $S_{\text{sign}}$ annoncé (vingt signes, quinze pour passer). Si la grille passe à vingt-trois,
   la barre bouge, et l'annonce du § 7.1.3 avec elle.

**Note de travail du chapitre 7 déjà couverte par ce ticket :** les points 1 (grille ambiguë),
3 (`articles_txt/` absent) et 4 (script d'injection) tombent avec les lots 1, 2 et 3. Le point 2
(`experiments.yaml` sur les trois événements antérieurs) relève du lot 1. Les points 5 à 8
restent au chapitre et au 095.

---

## 13. Questions ouvertes pour l'auteur

Ces questions ne bloquent pas les lots 1, 2 et 6, qui peuvent commencer sous les hypothèses
proposées. Elles se tranchent avant le lot 4.

| # | Question | Hypothèse retenue faute de réponse |
|---|---|---|
| Q1 | La constante de gravité des articles | **TRANCHÉ — l'agent décide** (§ 5.2). Reste Q16 (quand le jugement est demandé) et Q17 (échelon hors grille) |
| Q2 | Un lecteur par foyer | **TRANCHÉ — un seul**, tiré à graine fixe et journalisé (§ 6.4) |
| ~~Q3~~ | ~~**Le bras ouï-dire** (`observations_min = 0`) fait-il partie de P1 ?~~ | **SANS OBJET depuis le 2026-09-22.** D1 du ticket 100 fait porter au récit du soir tous les épisodes, sans ancrage : il n'y a plus de seuil à mettre à zéro. Voir le § 6.2 |
| Q4 | **Les trois cellules ambiguës** : dédoublées par motif, ou « pas d'effet attendu » ? | « pas d'effet attendu », et la grille reste à vingt (§ 4.2) |
| Q5 | Parution unique ou répétée | **TRANCHÉ — tirée au sort.** Jour de parution tiré par foyer, à graine fixe : un effet de calendrier ne peut plus se confondre avec l'effet de l'article. Reste Q15 (par foyer, ou un seul jour pour le run) |
| Q6 | Le chaînage des véhicules | **TRANCHÉ — actif partout.** Le confondant du § 6.3 ne se supprime donc pas, il se MESURE : `contrainte_chaine` devient obligatoire, et un changement de mode concomitant à une contrainte de chaîne ne compte pas comme diffusion |
| Q7 | **Le cache de décisions** pendant une campagne de presse | coupé, comme pour les chocs — la clé ne porte ni l'article ni le souvenir |
| Q8 | **P0 est-il obligatoire** avant d'engager P1 ? | oui — 300 requêtes pour savoir si le canal s'allume (§ 7.3) |
| Q9 | **L'étage 1 démarre-t-il par E1-a** (200 déplacements, un article, 800 requêtes avec E1-b) plutôt que par la cohorte entière (52 784) ? | oui — et E1-d ne se lance que si un relecteur l'exige (§ 7.3) |
| Q10 | **Les strates du sous-échantillon** : mode de référence, motif, tranche horaire, zone de résidence — faut-il en retirer ou en ajouter ? | ces quatre, graine journalisée, mêmes déplacements pour toutes les conditions |

---

## 14. Ce que ce ticket refuse

**Refusé : dégrader l'offre en même temps qu'on injecte l'article.** Le monde ne change pas, seule
l'information change. Un article qui couperait aussi les liens OTP mêlerait l'adaptation à la
contrainte et l'inertie de la croyance, et rendrait les deux inséparables — c'est le raisonnement
du 079 § 3, et il vaut ici mot pour mot. La condition C5 de l'étage 1 encode l'événement dans
l'offre ; **elle ne s'applique pas aux étages 2 et 3**.

**Refusé : reformuler le texte de presse pour le rendre plus lisible.** Quatrième garde du § 5.4.
Un texte reformulé est une condition de plus, non déclarée.

**Refusé : une gravité par article.** § 5.2 — cela ramènerait la durée de l'effet au rang de
réglage, ce que le lot A du 095 vient de corriger.

**Refusé : écrire l'article dans la mémoire du co-résident.** L'étage 3 passe par la consolidation
du 078 et par rien d'autre. Une croyance qu'on n'a ni formulée ni confrontée n'est pas une
croyance, c'est une injection — le 078 § 9 l'a déjà écrit.

**Refusé : étendre la diffusion au-delà du foyer.** Le foyer est le seul groupe qui porte un
identifiant dans les données. Un graphe social inventé produirait des résultats qui parlent du
graphe.

**Refusé : conclure sur une part modale à l'échelle des étages 2 et 3.** Deux cents agents dans
soixante-douze foyers observent un mécanisme ; ils ne mesurent pas une part modale.
`population_1000_AAMAS_v6` reste la référence, et l'étage 1 la seule mesure qui la traverse.

---

## 15. Livrables

1. **Corpus gelé** : `articles_txt/` complet, `MANIFEST.yaml`, test de lexique pour C3 (lot 1).
2. **Grille gelée** : `grille_signes.yaml`, cellules ambiguës tranchées (lot 2).
3. **Étage 1** : `scripts/analysis/eval_presse_locale.py` et son rapport — c'est le
   [ticket 064](ticket_064_campagne_experimentale_presse_locale_et_scoring.md) (lot 3).
4. **Canal `information`** : `llm/informations.py`, format, gardes, injection (lot 4).
5. **Mesure et figures** : `presse_par_jour.csv`, F1, F2, F3 (lots 5 et 7).
6. **Population** : `population_N_foyers_059` et son manifeste (lot 6).
7. **Section 7.1 et 7.1 bis du chapitre 7**, sous le verrou, quand les mesures existent.
8. **Annexe F** : la matrice des 30 scénarios en annexe méthodologique.

---

## 16. Références

- [Ticket 064](ticket_064_campagne_experimentale_presse_locale_et_scoring.md) — la campagne et le
  scoring de l'étage 1 ; il ne dépend que des lots 1 à 3 de ce ticket.
- [Ticket 078](ticket_078_partage_de_concepts_au_sein_du_foyer.md) — le canal du foyer, dont
  l'étage 3 dépend entièrement. Aucun code à ce jour.
- [Ticket 079](ticket_079_chocs_declares_vecus_par_les_agents.md) — le canal des chocs subis, dont
  le canal de presse est le frère ; format, gardes de contenu, séparation des deux retards.
- [Ticket 093](ticket_093_personas_mesurables_et_suivi_des_habitudes.md) — les mesures par jour,
  leurs quatre règles de lecture, et le sixième CSV à y ajouter.
- [Ticket 095](ticket_095_duree_d_un_souvenir_et_enquete_du_soir.md) — la durée dérivée de la
  gravité, l'enquête du soir, les runs enfants, et le plancher de bruit non nul.
- Carole Adam & Benoit Gaudou (2025), *A survey about perceptions of mobility, to inform an
  agent-based simulator of modal choice*, arXiv:2502.12058 — les six critères de l'enquête.
- `docs/paper/sources/actualites/RAPPORT_SCENARIOS_QUALITATIFS_TOULOUSE.md` — le corpus et la
  grille pré-enregistrée.
