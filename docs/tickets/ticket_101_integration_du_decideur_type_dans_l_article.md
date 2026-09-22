# Ticket 101 — Faire entrer le décideur à sortie typée dans l'article, sans en faire l'égal d'un agent LLM

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-22, à la clôture de la passe d'impact sur les dix chapitres.
>
> **Ce ticket n'écrit rien de lui-même.** Chaque fichier visé est sous le verrou de
> `docs/paper/article/` : procédure de la skill `article-verrou`, diff présenté puis accord
> explicite, un accord par tâche. Le style passe par `make paper-style F=<chapitre>` après
> écriture, y compris quand l'écriture est passée par `Bash`.
>
> **Analyse complète :** `docs/traces/2026-09-22_jev_impact_papier/README.md` (hors git).
> Ce ticket en est le plan d'exécution ; il ne la recopie pas.

---

## 1. D'où vient ce ticket

Le ticket 096 a livré trois lots et trois addenda le 2026-09-21. Onze expériences Jev existent
sous `data/experiences/`, sur les deux jeux. Une version alternative du chapitre 6 à quinze
décideurs est rédigée (`fr/alternative/06_results.md`) avec ses six figures.

Son § 10 annonçait l'impact sur l'article comme portant sur le § 6.1, sa figure, la figure 6.2
et l'annexe H. **La passe du 2026-09-22 sur les dix chapitres montre que c'est très en dessous.**
Le résultat Jev contredit des phrases des chapitres 0, 1, 8 et 9, qui affirment toutes, sous une
forme ou une autre, deux choses devenues fausses :

- que la parité au régime nominal appartient aux modèles tabulaires ;
- que ce qui excède l'enquête appartient au modèle de langue.

Fusionner le chapitre 6 alternatif sans toucher aux quatre autres produirait un papier qui se
contredit d'un chapitre à l'autre.

---

## 2. La règle qui prime sur tout le reste

**Décision de l'auteur, 2026-09-22.** Un modèle System One ne doit à aucun endroit du papier se
lire comme l'équivalent d'un agent à modèle de langue.

### 2.1 L'énoncé qui tient

« Jev n'a pas de mémoire » **ne tient pas**. Le rappel, la décroissance, le score à cinq termes
et les habitudes (cinq dernières observations de l'activité, ticket 093) sont **du code** ; et
`Score` / `Noul` pourraient en principe rendre la gravité et la valence — un relecteur qui ouvre
la documentation TypeSafe le verra.

Ce qui tient :

> Transformer un flux d'observations en traces épisodiques et en concepts entretenus est une
> génération de texte. `jev-1.13` n'est pas entraîné à en produire. Un décideur System One doté
> d'une mémoire est donc **nécessairement** un agent hybride, dont la mémoire est écrite par un
> modèle de langue.
>
> **L'inverse n'est pas vrai.** Un agent à modèle de langue se passe entièrement d'un modèle
> System One.

L'asymétrie est **à une voie**. C'est une propriété de conception, démontrable sans exécution,
et c'est elle qui interdit de présenter deux familles interchangeables.

### 2.2 Les trois étages, à ne pas confondre

| Étage | Contenu | Modèle de langue |
|---|---|---|
| Rappel | index vectoriel, décroissance, score à cinq termes, habitudes, entropie des choix | **non** |
| Jugements typés | gravité, valence, concept touché, opération | **non en principe** — jamais testé, bascule le bras en hybride |
| Texte du souvenir | récit à la première personne, formulation d'un concept, récit du soir, auto-réflexion | **oui, irréductiblement** |

### 2.3 Le contre-exemple à ne pas contredire

Le § 3.4 écrit déjà qu'un réajustement d'horaire « est écrit en mémoire à la première personne »
et « produit par l'écart entre l'horaire prévu et l'horaire vécu, **sans passer par le modèle de
langue** ».

**Ne jamais écrire « toute écriture en mémoire passe par le modèle de langue »** : le papier se
contredirait à deux chapitres d'écart. La borne exacte : un gabarit écrit **une** sorte d'entrée
prévue à l'avance ; il n'écrit pas le récit d'un événement quelconque, et il n'entretient aucun
concept.

### 2.4 Le piège principal — deux faits à ne jamais fusionner

| | Ce que c'est | Où |
|---|---|---|
| **Fait expérimental** | Aux chapitres 5 et 6, la mémoire est désactivée pour **tout le monde**. Vérifié sur les `experience.yaml` : `mode: sans_simulateur`, `memoire: false`, pour `exp_jev-1130_proexp05_…_EN_c_nosim` **comme** pour `exp_gemini-35-fl_proexp05_…_EN_c_t0_nosim`. Parité stricte, Jev n'est handicapé de rien. | § 4.1 ou § 5 |
| **Fait structurel** | Les autres bras **pourraient** l'activer. Jev, non. | § 2.4 et § 3.4 |

Les fusionner produit soit « Jev est désavantagé au chapitre 6 » — faux, et ça affaiblit le
résultat — soit « Jev fait aussi bien sans mémoire » avec le sous-entendu qu'il pourrait en
avoir une — faux, et c'est ce qu'il s'agit d'éviter. **Les deux phrases existent séparément.**

### 2.5 Ce que la règle fait gagner

Elle referme l'argument du papier :

> Le chapitre 6 retire au modèle de langue le crédit du régime nominal. Le chapitre 7 lui rend
> le seul crédit qui compte : il est le seul des deux à pouvoir constituer une mémoire, et c'est
> la mémoire qui produit l'adaptation.

Le § 7.2.1 le verrouille par la mesure : des quatre voies par lesquelles le passé atteint une
décision, **une seule a porté l'effet de l'avarie** — « ce qui a changé récemment », 75 prompts
sur 376. Le rappel par similarité n'a rien ramené, le concept n'a atteint aucun prompt. **La
seule voie dont on ait mesuré qu'elle produit l'hystérésis est celle qu'un décideur typé ne peut
pas alimenter.**

---

## 3. Les trois autres décisions déjà prises

| | Décision | Conséquence |
|---|---|---|
| **D1** | **Aucune campagne hybride.** Les chapitres 5 et 6 n'ont pas besoin de mémoire ; tous les résultats Jev existent. | Aucun lot de ce ticket ne dépend d'une campagne. L'agent hybride s'énonce au chapitre 8 comme architecture proposée, chiffrée par dérivation. |
| **D2** | **Jev reste un bras pur au chapitre 6.** L'hybride, s'il est présenté, l'est au chapitre 8. | Jamais de bras hybride dans le tableau du § 6.1 : le ticket 096 le dit pour son lot 3, « le bras cesserait d'être comparable aux bras LLM ». Si Jev n'apparaissait que comme composant, **le résultat du chapitre 6 disparaîtrait** — or il ne porte l'attribution causale que parce que le bras est pur. |
| **D3** | **La dépendance à la consolidation se pointe explicitement**, partout où Jev apparaît. | C'est le § 2. |

---

## 3 bis. Les retours de l'auteur du 22 septembre, et ce qu'ils défont

Passe de relecture sur les lots 0 à 6 livrés le même jour. Deux décisions de fond, deux lots
partiellement défaits, sept coupes.

**Décision A — l'hypothèse H0 est retirée du § 1.3.** Elle n'était plus un test depuis la `v0.23`
du chapitre 1 : aucune marge d'équivalence n'a jamais été écrite avant la mesure, et rien n'était
calculé à partir d'elle. Son nom appelait la machinerie du test d'hypothèse nulle, que l'article
n'emploie pas, et forçait le chapitre 6 à se défendre par avance — ce que la règle 2 du README
interdit. À sa place, le § 1.3 énonce l'échelle que le protocole mesure : bornée en haut par les
quatre modèles ajustés sur les microdonnées locales, en bas par les planchers sans connaissance
du comportement, les agents génératifs se lisant entre les deux. **Aucun chiffre ne bouge.**
Renvois restant à aligner, versés au lot 8 : `fr/README.md`, `en/01_Introduction.md`,
`overleaf/chapters/01_Introduction.tex`.

**Décision B — `prompt_expert_32` est le prompt expert de Jev.** Le chapitre publiait jusqu'ici
deux bras différents sous le même rôle : le tableau du § 6.1 donnait `prompt_expert_32` (3,65)
sous l'étiquette « prompt réglé pour lui », quand les intervalles appariés du § 6.1 et le gain du
§ 6.2 étaient calculés sur `prompt_expert_05` (4,19). L'auteur tranche pour `prompt_expert_32` :
c'est la consigne écrite pour ce porteur, elle garde sa place au § 6.1 sous le nom de prompt
expert, et son score reste en échantillon, le commentaire de source le portant.

⚠ **Conséquence à ne pas perdre.** Les différences appariées de l'annexe H.1 et le gain apparié
de l'annexe H.1 n'existent que sur `prompt_expert_05` ; l'équivalent sous `prompt_expert_32` n'a
pas été calculé. Les annexes nomment désormais ce bras « consigne `gemini-3.5` », et deux
commentaires de source le disent, au § 6.2 et en tête de H.1. Le calculer serait un lot à part.

**Ce qui est défait :** le lot 5 en entier — le chapitre 2 revient à sa `v0.19`, sans § 2.4, et
l'entrée A12 de `CITATIONS.md` avec lui ; le lot 6 pour le seul chapitre 7, qui perd ses trois
passages sur le classifieur. Le chapitre 8 et son § 8.7 sont conservés.

**Ce qui entre :** les deux bras Jev au tableau du § 6.4 et à la figure 6.5, où le classifieur
occupe les dernières places sur l'entropie croisée (0,464 et 0,552) alors qu'il tient la bande
tabulaire au § 6.1. C'est la mesure qui porte le mieux la règle du § 2 de ce ticket, et elle
manquait. Entre aussi la **dispersion entre graines**, mesurée : trois graines de l'axe 1 du
ticket 073 donnent 4,86, 4,65 et 4,30 de composite, étendue 0,56 point, ce qui lève le premier
des deux TBC du § 6.5. Le second est retiré sans être levé, le prompt minimal n'ayant pas été
rejoué sous ces graines.

**Ce qui sort du chapitre 6 :** le renvoi au § 5.2.3 dans l'ouverture, le paragraphe des gains
d'ingénierie, celui de la cinquième condition, les quatre paragraphes sous le tableau du § 6.1,
le tableau des gains appariés du § 6.2 et la figure 6.6. La figure 6.3 est resserrée à
`0.78\columnwidth` dans le rendu LaTeX.

**Point ouvert, sans décision :** la légende de la figure 6.1 porte « System One model » comme
nom de groupe, vocabulaire du fournisseur que le texte de l'article n'emploie pas. À trancher.

---

## 4. Ce qui bloque, et qui n'est pas Jev

**L'entropie croisée n'a pas la même définition dans les deux versions du chapitre 6, et le
classement s'inverse.**

| | Gradient boosté | Prompt expert `gemini-3.5` | Support |
|---|---:|---:|---|
| Chapitre de référence, § 6.5 | **0,299** | 0,342 | 5 451 décisions, support commun aux six décideurs à distribution |
| Version alternative, § 6.4 | 0,419 | **0,356** | `cel_weighted`, tous les notés |
| Annexe I.1 | **0,299** | — | support commun |

Sous la première lecture le gradient boosté devance le prompt expert ; sous la seconde le prompt
expert passe **devant les quatre méthodes tabulaires**, et la version alternative en tire une
phrase de conclusion.

Aggravant : le commentaire de la version alternative précise que sur le support commun **aux
neuf** décideurs — réduit à 5 229 décisions par l'arrivée de Jev — les deux bras Jev donnent
0,464 et 0,509, valeurs **absentes de son propre tableau**. Trois supports coexistent dans un
même chapitre.

Et c'est un motif déjà payé : le § 6.5 de référence porte une note disant que la lecture
antérieure, par sous-ensemble propre à chaque décideur, « donnait le prompt expert premier » et a
été corrigée le 2026-09-21. **La version alternative réintroduit la lecture corrigée.**

→ **Lot 0, bloquant.** Aucun appel API.

---

## 5. Les lots

### Lot 0 — trancher l'entropie croisée (bloquant, ½ j, aucun appel API)

Une seule définition pour tout le papier — support commun, recalculé sur les onze ou douze
décideurs — appliquée **simultanément** au § 6.5 de référence, à `fr/alternative/06_results.md`
et à l'annexe I.1. Trace datée, et la note du § 6.5 mise à jour pour dire quelle lecture fait
foi et pourquoi.

**Critère de sortie :** un même couple (décideur, grandeur) rend le même nombre dans les trois
fichiers, et le classement publié ne dépend plus du fichier qu'on ouvre.

### Lot 1 — les recalculs sans API (1,5 j)

| | Objet |
|---|---|
| **A1** | **Intervalles appariés sur l'audit unitaire** (exactitude, entropie croisée), même méthode que le bootstrap du 2026-09-17 : 2 000 réplicats, graine 2026, grappe au niveau de la personne. Le résultat le plus fort du papier — juste en agrégé, faux en individuel — est aujourd'hui asserté **sans intervalle** ; la version alternative le reconnaît elle-même. |
| **A3** | Annexes **H.2 et suivantes** et **I** : les deux bras Jev y sont absents. La version alternative le note (« L'annexe H ne porte pas encore les deux bras Jev »). |
| **A4** | `scripts/analysis/plot_chapitre6.py` avec les bras Jev ; fusion avec `plot_ticket096_jev.py`, laissé à part par le 096 pour ne pas changer `ch6_echelle` sous le verrou. |
| **A5** | **Décider** le décompte — 13, 15 ou 16 décideurs — et le sort de `prompt_expert_31` (composite 3,63, indistinguable de la retenue, mais deux fois plus destructeur par strate) et de `prompt_expert_32` (3,65, **en échantillon**). Décision d'auteur, pas de mesure. |

### Lot 2 — la règle de cadrage : une contrainte, pas une passe

> **Corrigé le 2026-09-22, après vérification.** Ce lot était écrit comme une passe autonome sur
> sept endroits du papier. Il ne peut pas l'être : `grep` sur les onze chapitres montre que
> **neuf ne mentionnent Jev nulle part**. Seuls le chapitre 6 et les annexes le connaissent. On
> ne qualifie pas une famille de décideurs dans un chapitre qui ne l'a pas introduite, et une
> généralisation sans motif tombe sous la règle 2 du README — le chapitre ne plaide pas contre
> une objection que personne n'a formulée.
>
> **Ce qui reste de ce lot :** la liste ci-dessous devient la **check-list des lots 3 à 6**.
> Chaque chapitre porte la règle au moment où il introduit le décideur typé, pas avant.
>
> **Fait le 2026-09-22 :** le seul endroit qui pouvait la porter tout de suite, le § 6.1 de
> `fr/alternative/06_Empirical_Evaluation.md`, l'a reçue — un paragraphe sous le tableau qui
> énonce la parité mémoire de la mesure et l'asymétrie de conception, et renvoie au chapitre 7.

Check-list, à appliquer dans le lot qui écrit chaque chapitre :

| Ch. | Ce qui s'ajoute |
|---|---|
| **1** § 1.3 | En annonçant la troisième famille : « un décideur qui ne produit aucun texte, et qui ne peut donc constituer aucun souvenir ». Une subordonnée — mais c'est là que le lecteur se forge son modèle de la comparaison. |
| **2** § 2.4 | Foyer de l'argument (lot 5). L'asymétrie à une voie s'y énonce. |
| **3** § 3.1, § 3.4 | Le plus fort, parce que structurel. $M_{i,t}$ est vide pour un décideur typé **et ne peut pas cesser de l'être sans un modèle de langue**. Ligne de partage à la consolidation, pas au rappel. Tenir compte du § 2.3. |
| **6** § 6.1 | Indispensable. Devant « Jev 4,19 / gemini 4,86 », un lecteur conclut que Jev est meilleur, point. |
| **7** ouverture | Le chapitre ne dit pas « Jev est absent », il dit « Jev est absent **par construction** ». |
| **8** | Limite **de famille**, distincte du § 8.7 qui porte les limites du **fournisseur**. |
| **9** points 1 et 2 | Point 1 : ce n'est pas le modèle de langue qui échoue, c'est la génération de texte qui ne sert à rien ici. Point 2 : la dépendance est ce qui le protège. |

### Lot 3 — les chapitres de cadrage : 0, 1, 9 (verrou)

**À faire AVANT la fusion du chapitre 6**, parce que c'est eux qu'il contredit.

- **Ch. 0.** Trois phrases touchées. Contrainte dure : le corps est déjà à **320 mots, au-delà de
  la borne OpenReview** — toute mention se compense ailleurs. Formulation candidate, qui absorbe
  le résultat sans nommer le produit : *« la parité au régime nominal ne requiert ni mémoire, ni
  génération de texte, ni données locales »*.
- **Ch. 1.** *(a)* **Intégrité de préenregistrement.** H0 porte sur les modèles de langue,
  testée et non réfutée ; le franchissement de la bande tabulaire par un décideur zéro-shot typé
  est un **résultat exploratoire**, découvert après la clôture du protocole, rapporté avec son
  intervalle apparié et **sans test d'équivalence**. Sans cet étiquetage, le papier applique deux
  standards dans le même chapitre. *(b)* **C2 devient un plan à deux facteurs** : niveau
  d'information × famille de décideur. *(c)* **C1 sort renforcé** : le protocole a absorbé une
  famille qu'il n'avait pas anticipée **sans qu'une ligne du scoreur soit touchée**. *(d)*
  **Contribution nouvelle, C4**, à arbitrer : le § 1.2 demande si une population plausible agent
  par agent peut être fausse en agrégé ; Jev fournit **la réciproque exacte, et mesurée**. Les
  deux échelles sont dissociables dans les deux sens.
- **Ch. 9.** Les cinq enseignements bougent. Le n° 3 (*noter là où le modèle sert*) est celui qui
  gagne le plus : il troque une illustration artefactuelle — une variante à 93,4 % d'exactitude
  trahie par une fuite de cible — contre un cas **propre**. Le n° 1 porte encore les chiffres
  7,30 / 29,81 d'un run d'août sur deux substrats différents, avec sa propre réserve écrite : à
  traiter dans la même passe.

### Lot 4 — fusionner le chapitre 6 (verrou)

`fr/alternative/06_results.md` → `fr/06_results.md`, **après** les lots 0, 1, 2 et 3. Le § 6.1
porte la phrase de parité mémoire ; les chiffres sont ceux du lot 0 ; les figures celles du
lot 1.

Deux mises en garde pour la relecture :

- **Le rejeu à l'identique de Jev ne lève pas les `TBC` du § 6.6.** Il porte sur une autre
  famille, à graine identique. Les `TBC` portent sur la dispersion *entre graines* d'un *modèle
  de langue*. **Hors sujet Jev :** deux bras `gemini-35-fl_proexp05` multi-graines subsistent
  (`go123`, `go789`), un seul scoré à 4,646 contre 4,86 publié — c'est le ticket 073 axe 1 en
  cours. `go456` et `go2026` ont été supprimés le 2026-09-22 : l'axe s'arrête à trois graines.
- **Le § 6.4 gagne son cas extrême** : Jev s'accorde avec le gradient boosté sur 72,2 % des modes
  les plus probables **et 71,7 % des modes tirés**, contre 69,7 % et 61,4 % au bras LLM. Son
  accord ne se défait pas au tirage. Les deux grandeurs du § 6.4 se séparent sur lui plus que
  sur n'importe quel autre décideur.

### Lot 5 — LIVRÉ le 2026-09-22

Le § 2.4 est écrit, « Décideurs zéro-shot à sortie typée », et **il n'introduit aucune référence
nouvelle**. La règle de tenue de `CITATIONS.md` en interdisait une : une citation ne reste que si
son PDF est au corpus et sa clé BibTeX existe, et le corpus de 63 entrées ne porte rien sur la
classification zéro-shot ni sur la calibration des classifieurs.

La sortie n'est pas d'aller chercher ces PDF mais de dire ce qui est vrai, et c'est l'arbitrage
de l'auteur du 22 septembre : **ce n'est pas encore une technologie soutenue par une littérature
scientifique établie, c'est un produit de recherche appliquée en lancement précoce, aux résultats
principalement auto-déclarés par son éditeur.** La section le porte tel quel, refuse le
vocabulaire commercial du fournisseur et nomme l'objet par sa fonction.

Cette absence commande sa place : il entre dans l'article **comme décideur mesuré et non comme
résultat cité**, sous le même protocole et contre la même enquête certifiée que les autres. Ce
que le chapitre 6 en rapporte devient une mesure indépendante là où il n'en existait pas — ce qui
est une contribution plutôt qu'une faiblesse.

L'ancrage se fait sur Meister et al. (2024), déjà au corpus et déjà cité au § 2.3 : verbaliser ou
échantillonner une distribution, auxquelles une sortie typée oppose une troisième voie, la lire
en sortie. La section déclare aussi que l'attribution reste partielle, le modèle et la forme de
sa sortie variant ensemble entre les bras — c'est **C1**, toujours hors périmètre.

`CITATIONS.md` : la phrase citante du § 2.4 est ajoutée à l'entrée A12.

### Lot 5 — le plan tel qu'il avait été écrit (verrou, + travail bibliographique)

**Le chapitre le plus démuni, et le risque principal pour l'acceptation.** Aucune des trois
sections n'accueille un classifieur zéro-shot à sortie typée : ni modèle de choix discret (rien
d'estimé), ni agent génératif (rien de généré), ni échantillon silicone (aucune population
simulée).

Trois problèmes, par gravité :

1. **Aucune publication.** Pas d'article, pas de poids, architecture et données d'entraînement
   inconnues. La littérature citable est une documentation produit.
2. **« System One » est une marque, pas un concept établi.** Emprunt à Kahneman non validé.
   Nommer l'objet par ce qu'il fait — *classifieur zéro-shot à sortie typée et probabilités
   calibrées* — et mettre la marque à distance.
3. **L'ancrage académique existe et n'est pas cité.** Classification zéro-shot par implication
   textuelle ; calibration des classifieurs ; et surtout **Meister et al. (2024), déjà cité au
   § 2.3** — un modèle peut connaître une distribution qu'il ne sait pas tirer, et les
   distributions verbalisées s'alignent mieux que les échantillonnées. Jev pousse la ligne d'un
   cran : une distribution **ni verbalisée ni échantillonnée, mais lue en sortie typée**. Le fil
   est déjà dans le papier.

Le § 2.4 situe l'objet entre 2.1 (probabilités calibrées, mais estimées localement) et 2.3
(connaissance du monde, mais verbalisée), énonce l'asymétrie du § 2.1 de ce ticket, déclare
l'absence de littérature évaluée par les pairs comme une limite du **bras** et non du protocole,
et renvoie au § 8.7.

### Lot 6 — LIVRÉ le 2026-09-22

**Chapitre 7, `brouillon v2.2`.** Le chapeau annonce le second comparateur et dit que les deux
régimes ne se rangent pas du même côté sur lui. Le § 7.1 énonce que la chaîne qu'il décrit
demande un modèle qui écrive, et sépare **constituer** un souvenir de le **rappeler** : le rappel,
l'index, la décroissance et les habitudes se calculent depuis le journal, et le § 3.4 écrit déjà
sans modèle le réajustement d'horaire. Le régime du § 7.2 est donc fermé par construction, et
c'est un argument qui ne coûte aucune campagne. Le § 7.3 borne en conséquence ce qu'il établit :
aucune variable tabulaire n'encode ces cinq événements, **et non** que les lire demande de savoir
écrire — le bras témoin du lot 7 n'a pas été joué, et le texte le dit à l'endroit où la nuance
porte. Aucun chiffre ne bouge.

**Chapitre 8, `brouillon v0.4`.** Le § 8.3 publie le coût des trois familles : 1,06 $ contre
49,28 $ à charge égale de 23 026 décisions, alors que l'entrée par décision du décideur typé est
**plus grosse** (1 050 jetons contre 629), l'écart venant du tarif et de la sortie non facturée.
Au périmètre d'enquête, il rencontre un mur d'une autre nature, un état par requête, soit
2,9 M de requêtes et quelque quarante heures pour environ 130 $ : le prix cesse d'être la
contrainte, le débit la devient. Le § 8.4 lui donne l'étage tabulaire de la cascade, qui ne
demande alors aucune enquête locale, et décrit le second découpage possible, par fonction plutôt
que par aiguillage, qui se passe du critère manquant ; son chiffrage dérivé donne 2 $ contre 7 $
par journée, soit sept dixièmes d'économie et non un facteur cinquante, la mémoire portant la
quasi-totalité de ce qui reste. Deux garde-fous sont écrits : la confiance n'est pas validée, et
le critère d'habitude du § 8.5 se mesure avant de se coder. Le § 8.7 est créé, et il sépare la
limite **de famille** de la limite **de fournisseur**.

### Lot 6 — le plan tel qu'il avait été écrit

**Ch. 7.** *(a)* L'argument gratuit : l'hystérésis est **hors d'atteinte par construction**,
doublée par la mesure du § 7.2.1. *(b)* Le trou réel : le § 7.3, l'article lu le matin, **n'est
pas** structurellement hors d'atteinte — Jev accepte 32 000 jetons de `state` textuel. Tel quel,
le § 7.3 **ne peut pas conclure que la sensibilité au contexte textuel est propre aux agents
génératifs**. Deux issues : le bras témoin du lot 7, ou restreindre explicitement la portée à
« aucune variable tabulaire n'encode ceci ». Ne rien faire est à écarter : un relecteur qui a lu
le chapitre 6 posera la question.

**Ch. 8.**

- **§ 8.3, trois familles.** Le § cite déjà la trace `2026-09-21_13-10_cout_jev_vs_gemini/`
  comme source de son erratum, **sans en publier un chiffre Jev**. À corriger. Points à faire
  passer : le rapport de coût n'est pas un rapport de volume (Jev envoie 1 050 jetons d'entrée
  par décision contre 629 à Gemini — il **n'amortit rien** ; le facteur 45–56 vient du tarif) ;
  le temps de Gemini mesure des quotas, celui de Jev un débit réel ; et *dérivé, à vérifier* :
  au périmètre, 2,9 M de sollicitations × 1 050 jetons ≈ **3,0 G jetons ≈ 128 $ par journée
  simulée**, et comme Jev n'accepte **qu'un `state` par requête**, 2,9 M de requêtes à
  1 200/min ≈ **40 h** — le mur n'est plus le prix, c'est le débit.
- **§ 8.4, la cascade.** *(a)* L'étage 2 a un second candidat, qui **ne demande aucune enquête
  locale** — le § 1.1 ouvre sur cette pénurie, la cascade y répond, avec la réserve « non mesuré
  hors de Toulouse ». *(b)* **L'agent hybride comme second découpage** : par fonction (Jev décide
  toujours, le modèle de langue écrit toujours la mémoire) plutôt que par aiguillage. Il **se
  passe du critère d'aiguillage**, justement ce que le papier traîne en `[xx]`. Chiffrage
  *dérivé* : journée tout-Gemini 7,14 $, journée hybride 2,00 $, **72 % d'économie** — mais la
  mémoire pèse alors **94 % du coût hybride**. Le facteur 45–56 ne survit pas à l'allumage de la
  mémoire, et le § 8.3 y gagne une conclusion qu'il n'a pas : **le plancher de coût d'un agent à
  mémoire, c'est la mémoire.** Statut : architecture proposée, **aucune campagne** (D1).
  Précautions : ne pas router sur une confiance non validée (elle est archivée sans être
  utilisée, décision du 096, aucun diagramme de fiabilité) ; le § 8.5 pose déjà le bon critère,
  l'habitude, qui se **mesure** avant de se coder et qui ne demande aucun modèle.
- **§ 8.7, à créer — limites du fournisseur**, distinctes de la limite de famille : modèle
  propriétaire sans publication ni poids, hébergé à distance, sans auto-hébergement documenté ;
  données d'entraînement inconnues (**même réserve que pour les bras LLM**, à énoncer et non à
  contourner) ; version épinglée, alias refusés à la validation ; débits « ajustés dynamiquement,
  sans préavis » ; **le bras peut devenir irrejouable avant AAMAS 2027**, parade en place
  (réponse entière archivée, `DecideurRejeu`) ; quasi-déterminisme non documenté par le
  fournisseur et **mesuré ici** (0,013 d'écart moyen par option, bascule d'argmax sur 5,5 % des
  décisions, **toutes des quasi-égalités**).

### Lot 7 — les bras Jev supplémentaires (coût dérisoire)

| | Objet | Ce que ça tranche | Coût |
|---|---|---|---|
| **B2** | **Jev sur les cinq articles de presse** (C1/C2/C3), texte inséré dans `state`, sans mémoire | **La priorité du lot.** La sensibilité au texte est-elle propre au générateur, ou seule la consolidation l'est-elle ? Publiable dans les deux sens, comme le 096. | ~0,05 $ |
| **B1** | **Jev multi-graines** sur la cohorte scellée | Borne à l'échelle de la cohorte la sensibilité à l'ordre mesurée à 0,072/option au lot 0 du 096. Ne lève pas les `TBC`. | ~0,11 $ / graine |
| **B4** | **Rejeu de la contre-épreuve « state resserré »** sous `prompt_expert_05`, jeu complet | Chiffre la faiblesse documentée « large, irrelevant state ». La mesure existante est sous `prompt_expert_16` et sur 200 décisions. | ~0,12 $ |
| **B3′** | *(optionnel)* Renvoyer à Jev les `state` **archivés** de l'agent exposé du § 7.2 (`llm_exchanges.jsonl`, blocs mémoire déjà écrits) | « Jev réagit-il à un souvenir qu'on lui donne ? » Sans GAMA, sans écriture. À vérifier : que le flux archivé soit rejouable — `DecideurRejeu` existe, le ticket 059 Q20 retient déjà le rejeu hors ligne depuis `moves.csv`. | ~0,05 $ |

### Lot 8 — anglais et LaTeX

`en/` et `overleaf/` ne portent **aucune mention** de Jev, hors un commentaire de source dans
`en/08_limits_and_hybrid.md`. Après stabilisation du français, qui fait foi.

---

## 6. Ce qui n'est PAS de ce ticket

Deux manques sont réels, coûteux, et **hors périmètre tant que l'auteur ne les a pas arbitrés**.
Ils sont ici pour être décidés, pas pour être faits.

| | Objet | Pourquoi ça compte |
|---|---|---|
| **C1** | **Un bras LLM à sortie typée** : `gemini-3.5` contraint à rendre sa distribution par lecture de logprobs sur les indices d'option, plutôt que verbalisée | **Le confondant central.** Jev diffère des bras LLM par **deux** choses à la fois — le modèle, et la forme de la sortie. Aucune expérience du dépôt ne les sépare. Tant qu'elles ne le sont pas, « ce n'est pas le jeu de rôle génératif qui achète la performance » reste une hypothèse plausible, **pas un résultat**. |
| **C2** | **Un second décideur zéro-shot typé, ouvert** | Le § 2.4 n'aurait sinon qu'un seul point d'appui, fermé, sans publication, et susceptible de disparaître. Un bras ouvert rend la **famille** défendable indépendamment du fournisseur. |

Également hors périmètre : un second territoire sans enquête locale (validerait la portée du
§ 8.4 ; à énoncer en travaux futurs) ; toute campagne hybride (**D1**) ; tout usage de la
confiance de Jev dans une décision ; la levée des `TBC` du § 6.6 (ticket 073 axe 1).

---

## 7. Ordre et dépendances

```
Lot 0 (bloquant, entropie)              LIVRÉ le 2026-09-22
   └─> Lot 1 (recalculs)                A1 et A3 partiels ; A5 clos sans action
          └─> Lot 3 (ch. 0, 1, 9)       <── le lot 2 n'est plus une étape :
                 └─> Lot 4 (fusion)         sa check-list ride avec les lots 3 à 6
                        ├─> Lot 6 (ch. 7 et 8)      <── Lot 7 (B2) alimente le ch. 7
                        └─> Lot 5 (§ 2.4)           <── C2 le renforcerait
                               └─> Lot 8 (en/ + overleaf)
```

**DÉPEND DE :** rien d'extérieur. Les lots 1 et 7 sont exécutables immédiatement. Les lots 3
à 6 passent par le verrou de l'article, un accord par tâche.

**Ce que le papier ne doit dire nulle part.** Que Jev « remplace » quoi que ce soit — le 096 le
place hors périmètre. Que sa confiance est exploitable — archivée sans être validée. Que le
rejeu à l'identique lève les `TBC` — autre famille, graine identique. Que « toute écriture en
mémoire passe par le modèle de langue » — le § 3.4 dit le contraire pour un cas. Que Jev
« comprend » le contexte — rien de mesuré ne le montre, et sa documentation liste les durées,
les distances et les dates parmi ses faiblesses connues.

---

## 8. Tickets liés

- [Ticket 096](ticket_096_jev_typesafe_troisieme_famille_de_decideur.md) — le décideur, ses
  lots, ses mesures et ses trois addenda. **Ce ticket 101 est la suite article de son § 10.**
- [Ticket 094](ticket_094_alignement_de_l_article_apres_la_reecriture_du_chapitre_7.md) —
  précédent d'un ticket d'alignement sous verrou.
- [Ticket 080](ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md) — idée
  directrice du chapitre 6 et décisions d'auteur.
- [Ticket 058](ticket_058_perimetre_et_methode_audit_unitaire.md) — périmètre et méthode de
  l'audit unitaire ; le lot 0 et A1 y touchent.
- [Ticket 073](ticket_073_reproductibilite_prompt_calibre_multi_graines_multi_populations.md) —
  rejeu à l'identique et dispersion inter-graines ; porte les `TBC` du § 6.6, que ce ticket ne
  lève pas.
- [Ticket 100](ticket_100_un_seul_canal_d_evenement_pour_le_vecu_et_le_lu.md) — canal unique
  d'événement ; le § 7.1 le décrit sans code, et le lot 6 ne l'attend pas.
