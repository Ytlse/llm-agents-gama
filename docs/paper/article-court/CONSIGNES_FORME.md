# Consignes de forme et de style — article court AAMAS 2027

Dix-huit consignes, à appliquer avant toute reprise du fond. Chacune porte son test :
soit une commande, soit une relecture dont le critère est écrit. Une consigne sans test
ne s'applique pas, elle se discute.

Les exemples cités en faute sont tous tirés de la version de septembre 2026, dans
`docs/paper/article/overleaf/chapters/`.

---

## § 0. Arbitrage avec la charte anti-IA

La skill `article-verrou` proscrit quatre familles de marqueurs de rédaction assistée.
Trois d'entre elles produisent mécaniquement le défaut signalé par le tuteur. L'arbitrage
retenu est que **la lisibilité prime**, et il lève trois interdictions.

### Ce qui est levé

**L0.1 — Le balisage de section est autorisé.** La charte proscrit la structure symétrique
et le triptyque *tout d'abord / ensuite / enfin*. Ce qui est proscrit reste la symétrie
décorative, celle qui découpe en trois un raisonnement qui n'a pas trois parties. Annoncer
en tête de section ce qu'elle fait et dans quel ordre n'est pas une symétrie, c'est une
carte. Un lecteur de conférence lit en diagonale ; sans carte il abandonne.

**L0.2 — Les connecteurs logiques sont obligatoires, pas tolérés.** La charte proscrit le
lissage sémantique, c'est-à-dire l'équilibrage systématique des arguments. Elle ne proscrit
pas *therefore*, *because*, *however*, *in contrast*. La version actuelle n'en porte presque
aucun, et le lecteur doit reconstruire chaque lien. Le lissage est une posture, le connecteur
est une information.

**L0.3 — La hiérarchie visuelle est autorisée dans les tableaux et les légendes.** La charte
proscrit le gras qui porte l'argument à la place de la phrase. Cela vaut pour la prose. Dans
un tableau, une légende ou une en-tête, le gras désigne, il n'argumente pas.

### Ce qui tient sans changement

- Le lexique prédictible reste proscrit : *crucial*, *pivotal*, *delve*, *seamless*,
  *underscore*, *il convient de noter*.
- Le cadratin comme seul outil d'apposition reste proscrit. Attention : dans la version
  actuelle, cette interdiction a été reportée sur le deux-points, qui sature à un tous les
  22 mots au chapitre 5. Voir R2.
- La formule-slogan en tête de paragraphe reste proscrite. Elle entre même en renfort de
  R7 : un paragraphe commence par ce qu'il établit, pas par une posture.
- Le chapitre ne plaide pas.
- La fabrication plutôt que la mesure n'entre pas dans le texte.

### Ce qu'il faut savoir en pratique

`make paper-style` signalera les levées L0.1 à L0.3. Le détecteur est un signal, pas une
autorité : sur ces trois points, le signalement se note et ne se corrige pas.

---

## § 1. La phrase

### R1 — Trente mots au maximum, une idée par phrase

Au-delà, la phrase se coupe. Aucune exception, y compris pour une énumération : une
énumération de plus de trois termes devient une liste ou un tableau.

En faute, § 1.6 (57 mots) :

> *Three rules, stated in Section 4.3, each close one way in which a comparison between a
> generative agent and a tabular model can be biased: the same 21 input variables on both
> sides, probability mass as the scored quantity rather than a single mode, and the
> restriction of every tabular prediction to the modes actually offered for the trip.*

Corrigé : une phrase pour l'énoncé, une liste pour les trois règles.

**Test :** `verifier_forme.py` signale toute phrase de plus de 30 mots (seuil relevé de 25 à 26 le 2026-09-24, puis de 26 à 30 le 2026-09-25, décisions de l'auteur). Un titre de paragraphe en ligne (`**Titre court.**` en Markdown, `\paragraph{…}` en LaTeX) ne compte pas dans la phrase qui le suit.

### R2 — Un deux-points par paragraphe au maximum, jamais deux dans une phrase

Le deux-points sert aujourd'hui à énumérer, expliciter, opposer, définir et conclure. Un
signe qui porte cinq fonctions n'en porte plus aucune, et c'est une cause directe de
l'impression de texte brut.

Densité mesurée, hors commentaires :

| Chapitre | Deux-points | Mots | Un tous les |
|---|---:|---:|---:|
| 3 | 51 | 1 940 | 38 mots |
| 4 | 51 | 2 182 | 43 mots |
| 5 | 99 | 2 222 | **22 mots** |
| 6 | 48 | 2 311 | 48 mots |
| 7 | 30 | 2 228 | 74 mots |

Cible : un tous les 150 mots au moins.

En faute, § 3.4, deux deux-points dans une phrase, ce qui est agrammatical en anglais :

> *It does not record decisions alone: it receives the physical experience the simulation
> produces: transfers, waits at the stop, arrival times, the events of the day.*

**Test :** `verifier_forme.py` compte les deux-points par paragraphe et signale les doubles.

### R3 — Un connecteur explicite entre deux phrases liées

La juxtaposition sans connecteur oblige le lecteur à reconstruire le lien logique. Répétée,
elle transforme un raisonnement en liste de constats.

En faute, § 2.2 : quatre affirmations, trois liens implicites.

> *The loop runs offline and the agent does not deliberate; a plan is selected by its score,
> and the score is a function written in advance.*

**Test :** relecture. Pour chaque point-virgule et chaque phrase courte qui suit une autre
phrase courte, poser la question « quel est le lien ? ». S'il faut y réfléchir plus d'une
seconde, le connecteur manque.

### R4 — Le référent avant le pronom

Aucune phrase ne commence par un démonstratif dont le nom n'a pas été écrit juste avant.

En faute : *That obvious fact is not obvious to…* (quel fait ?), *This detail settles the
nature of what we measure* (quel détail ?), *That rating, and it alone, sets the severity*,
*The methodological consequence has to be drawn* (laquelle ?).

**Test :** `verifier_forme.py` signale les phrases ouvrant sur *This / That / These / Those
/ Such* suivi d'un nom abstrait.

### R5 — Pas de clivée ni d'inversion littéraire

Une clivée par section au maximum, et seulement pour souligner un contraste que la phrase
plate ne rendrait pas.

| En faute | Corrigé |
|---|---|
| *What is equalised is the inputs, not the exposure.* | *We equalise the inputs, not the exposure.* |
| *It is there, and only there, that the language model intervenes.* | *The language model intervenes only at this point.* |
| *It is against that ceiling that an agent compares.* | *We compare each agent against that ceiling.* |
| *What the model produces is a distribution.* | *The model produces a distribution.* |
| *Their strength is statistical. Their weakness is behavioural.* | *These models are statistically strong and behaviourally weak.* |

**Test :** `verifier_forme.py` signale les motifs `What is … is`, `It is … that`,
`What … does is`.

### R6 — Voix active, sujet réel

*We measure*, *the controller serves*, *the agent receives*. Pas *the measurement is
conducted*, *it is observed that*. La voix passive reste admise quand l'agent de l'action
n'a aucune importance.

**Test :** relecture. Compter les passives par paragraphe ; au-delà de deux, réécrire.

---

## § 2. Le paragraphe et la section

### R7 — La première phrase du paragraphe dit ce que le paragraphe établit

C'est la consigne la plus importante du document, et celle qui répond directement à
*« ideas are not properly structured »*. Un relecteur de conférence lit la première phrase
de chaque paragraphe et décide s'il lit le reste. Dans la version actuelle, aucune première
phrase ne dit son sujet : la conclusion arrive en dernier, quand elle arrive.

En faute, § 3.5 :

> *An agent who cycled to work has no car at the office in the evening. That obvious fact is
> not obvious to a system that would decide each trip independently, and it is what separates
> the device from a classifier called once per trip.*

Le paragraphe est bien écrit et il est illisible en diagonale : il faut lire les trois
phrases pour savoir de quoi il parle.

Corrigé : *Deciding each trip independently produces physically impossible days. An agent who
cycled to work has no car at the office in the evening.*

Cette consigne ne contredit pas la charte anti-IA : celle-ci proscrit la formule-slogan en
tête de paragraphe, et exige précisément qu'un paragraphe commence par ce qu'il établit.

**Test :** `verifier_forme.py --squelette` imprime la première phrase de chaque paragraphe
d'une section, bout à bout. Si ce squelette ne raconte pas la section à lui seul, les
phrases-sujets manquent.

### R8 — Chaque section annonce en deux phrases au plus ce qu'elle fait

Ce qu'elle établit, et dans quel ordre. Ni plus long, ni absent. Le chapitre 6 actuel
enchaîne cinq sous-sections sans dire au début quelles questions il traite.

**Test :** relecture. Lire uniquement les deux premières phrases de chaque section ; la
succession doit donner le plan de l'article.

### R9 — Aucun renvoi vers l'avant

Un renvoi ne va que vers l'amont. La version actuelle en porte une trentaine dans les deux
sens : le chapitre 3 renvoie aux chapitres 4 et 6, le chapitre 4 renvoie aux chapitres 5 et 6,
le chapitre 5 renvoie au chapitre 4 et au chapitre 6. Plus rien ne se comprend à sa place.

Si une notion est nécessaire avant sa section, c'est que l'ordre des sections est faux, ou
que la notion doit être définie en une phrase à son premier emploi.

**Test :** `verifier_forme.py` signale tout `\ref` ou `§` pointant vers une section
postérieure.

### R10 — Le budget de mots est fixé avant d'écrire, section par section

8 pages AAMAS, figures et tableaux compris, valent environ **6 500 mots de prose moins la
place des floats**. La version actuelle en compte 20 603 hors annexes. Un budget écrit
avant la rédaction évite d'écrire trois fois trop, puis de compresser, puis de produire le
texte télégraphique que le tuteur a lu.

Le budget s'écrit dans le plan de l'étape 3 et il ne se dépasse pas : un dépassement se
compense dans la même section, pas ailleurs.

**Test :** `verifier_forme.py` imprime le nombre de mots par section et le compare au budget
s'il est déclaré dans le plan.

---

## § 3. Le lexique et le nommage

### R11 — Un mot pour un concept, et pas de vocabulaire maison

Les termes ci-dessous sont des calques du français ou des inventions internes. Un relecteur
anglophone ne peut pas les deviner. Table de conversion, à appliquer sans exception.

| Proscrit | À écrire | Pourquoi |
|---|---|---|
| the device, the agentic device | the system, the framework | calque de « dispositif » ; n'existe pas dans ce sens |
| the offer, the itinerary supply | the choice set, the available options | calque de « l'offre » |
| the carrier | the language model, the backbone model | incompréhensible ; *the carrier weighs as much as the instruction* est indéchiffrable |
| plates | panels, figures | *plate* signifie assiette ou plaque photographique |
| the field (§ 3.2) | the option set | calque de « le champ » |
| an arm | a condition, an experimental arm | admis en essai clinique, jamais introduit ici |
| a couple (model + prompt) | a pair | calque de « un couple » |
| the ladder | the ablation levels | métaphore non définie |
| agnosticity predicate | territory-agnostic constraint | terme inventé |
| guard-rails | constraints | jargon |
| an adaptability | adaptability | agrammatical avec l'article |
| an agent compares | we compare each agent | il manque le réfléchi ou la passive |

**Test :** `verifier_forme.py` signale chaque terme de la colonne de gauche.

### R12 — Un seul système de nommage, sans collision

La version actuelle donne cinq sens à la lettre C dans un texte de 8 pages : les trois
contributions C1-C3, les trois conditions presse C1-C3, la condition C5, la chaîne de
véhicules $C_{i,t}$ et les composites $\mathcal{C}_{L1}$.

Elle fait par ailleurs coexister quatre systèmes parallèles pour la même gradation :
`Level 0/1/2/3`, `floor / ceiling`, `minimal prompt / expert prompt`, `rule 1/2/3`, plus H0
et les étapes SILICA *exploratory / robust / transferable*.

Consigne : **un seul système survit**, les autres disparaissent du texte. Le choix se fait
au plan, à l'étape 3, et il s'écrit dans un tableau unique placé à sa première utilisation.

**Test :** relecture. Écrire la liste de tous les identifiants du papier sur une page. Si
deux lignes portent le même symbole, réécrire.

### R13 — Tout chiffre est interprété dans la phrase qui le porte

Un chiffre brut sans son unité, son pourcentage ou sa comparaison oblige le lecteur à
calculer. Répété, c'est le paroxysme du texte brut.

En faute, § 7.2.3 : six fractions en deux phrases, aucun pourcentage, aucune interprétation.

> *the exposed agent retains it 34 times out of 36 before the incident, 12 out of 38
> afterwards, then 35 out of 40. The unexposed agent stays at 28 out of 31, 45 out of 49
> and 40 out of 46.*

Corrigé : un tableau, avec les pourcentages (94 %, 32 %, 88 %) et une phrase qui dit ce
qu'on doit y voir.

Corollaire : les effectifs du papier doivent se réconcilier. La version actuelle donne
3 299 puis 3 154 décisions sur le même jour évalué, sans expliquer les 145 manquantes,
et fait coexister 9 621, 5 451, 13 045, 39 203, 2 930, 2 502 et 3 111 sans table de
correspondance. Une seule table, à la première occurrence.

**Test :** relecture. Pour chaque chiffre, vérifier qu'il porte son unité et qu'une phrase
dit ce qu'il établit.

---

## § 4. La livraison

### R14 — Zéro placeholder dans le texte livré

`\newcommand{\todo}[1]{\textbf{[#1]}}` imprime les placeholders **en gras dans le PDF**. La
version lue par le tuteur en portait six, dont deux dans l'introduction. Un placeholder livré
se lit comme un brouillon envoyé par erreur, et il coûte plus cher que la phrase qu'il
remplace.

Consigne : une mesure qui n'existe pas ne s'annonce pas. La phrase qui la porterait sort du
texte jusqu'à ce que la campagne ait tourné.

**Test :** `verifier_forme.py` signale tout `\todo`, `TBC`, `TODO`, `xx.y`, `[à mesurer]`.

### R15 — Tout élément essentiel est dans les 8 pages

Règle AAMAS explicite : *« Toute information essentielle à la compréhension ou à l'évaluation
du papier doit obligatoirement figurer dans les 8 pages »*
([SOUMISSION_AAMAS_2027.md:78](../article/SOUMISSION_AAMAS_2027.md)). La version actuelle
pose H0 en page 2 et renvoie sa conclusion à l'annexe H, laquelle n'est pas jointe au projet
Overleaf et s'imprime `??`.

Consigne : toute hypothèse posée dans le corps est tranchée dans le corps, en toutes lettres,
avec le mot « rejetée » ou « non rejetée ». L'annexe porte le détail, jamais la conclusion.

**Test :** compiler et chercher `??` dans le PDF. Aucun renvoi ne doit rester non résolu.

### R16 — Une figure porte une affirmation, et la légende l'énonce

Cible : cinq figures et trois tableaux au maximum. La version actuelle en porte douze et
neuf, dont huit floats au seul chapitre 6 pour moins d'une page de texte courant, ce qui
fait apparaître les planches un à trois chapitres après le texte qui les appelle. Cela suffit
à rendre un papier incompréhensible, indépendamment de son style.

Consigne, pour chaque figure retenue : la légende commence par l'affirmation que la figure
établit, en une phrase. Si cette phrase ne s'écrit pas, la figure sort.

**Test :** lire les seules légendes. Elles doivent former la liste des résultats du papier.

### R17 — L'anglais se rédige d'abord, le français en est le rendu

Décision de l'auteur du 2026-09-22, qui inverse la convention de l'article actuel (français
source de vérité, anglais aligné). La version anglaise de la première version était un
décalque phrase à phrase du français : même découpage, mêmes points-virgules, même ordre des
propositions. C'est la cause directe du *« sentences seem very brut »*. Le relecteur lit
l'anglais ; c'est donc l'anglais qui se rédige.

Consigne : chaque section de l'article court s'écrit en anglais depuis le sens de l'entrée du
plan. La version française s'en déduit ensuite, paragraphe par paragraphe, comme un rendu
fidèle : mêmes coupes, mêmes chiffres, même registre que les masters actuels. Un problème de
fond découvert au rendu se signale dans le compte-rendu, il ne se corrige pas dans le français.

**Test :** aligner un paragraphe anglais et son rendu français. Les phrases se correspondent
une à une, et c'est voulu : le sens a été fixé en anglais. Si le français dit quelque chose que
l'anglais ne dit pas, la passe a dérivé.

---

### R18 — Un seul artefact fait foi, et c'est celui qui est relu

Le rendu LaTeX est aujourd'hui en retard sur ses masters, et l'écart porte sur le fond.

| Fichier | Version déclarée | Master correspondant |
|---|---|---|
| `01_Introduction.tex` | v0.27, 22 septembre | `fr/01_Introduction.md` v0.29 |
| `03_Architecture.tex` | v0.7, 17 septembre | plus récent |
| `04_Evaluation.tex` | v0.18, 17 septembre | plus récent |
| `05_Protocol.tex` | v0.10, 17 septembre | plus récent |
| `06_Empirical_Evaluation.tex` | v0.4, 17 septembre | plus récent |

Conséquence vérifiée : l'hypothèse H0 a été retirée du § 1.3 français le 22 septembre, et
elle est toujours dans `01_Introduction.tex` l. 78, donc dans le PDF. Le tuteur a lu une
version que l'auteur avait déjà corrigée, et une partie de ses remarques peut porter sur du
texte qui n'existe plus.

Consigne : le `.tex` se régénère depuis son master **avant toute relecture externe**, et la
version déclarée en tête des deux fichiers doit coïncider. Envoyer un PDF périmé coûte un
cycle de relecture entier.

**Test :** comparer la version en tête de chaque `.tex` et celle de son master. Aucune paire
ne doit diverger avant un envoi.

---

## § 5. Ce qui se vérifie à la machine, ce qui se vérifie à la relecture

| Consigne | Machine | Relecture |
|---|:---:|:---:|
| R1 longueur de phrase | oui | |
| R2 deux-points | oui | |
| R3 connecteurs | | oui |
| R4 référent avant pronom | partiel | oui |
| R5 clivées | oui | |
| R6 voix active | | oui |
| R7 phrase-sujet | `--squelette` | oui |
| R8 annonce de section | | oui |
| R9 renvois vers l'avant | oui | |
| R10 budget de mots | oui | |
| R11 lexique | oui | |
| R12 collisions de nommage | | oui |
| R13 chiffres interprétés | | oui |
| R14 placeholders | oui | |
| R15 renvois non résolus | oui, à la compilation | |
| R16 figures | | oui |
| R17 anglais d'abord, français en rendu | | oui |
| R18 synchronisation LaTeX / master | oui | |

Huit consignes sur dix-huit se contrôlent à la commande. Les dix autres se contrôlent en
lisant, et c'est le squelette de R7 qui en révèle le plus par unité de temps.

```bash
python3 docs/paper/article-court/verifier_forme.py docs/paper/article/en/03_Architecture.md
python3 docs/paper/article-court/verifier_forme.py --squelette docs/paper/article/en/03_Architecture.md
```
