# Ticket 095 — Questions vivantes

Consignées au fil du travail, à trancher par l'auteur. Chaque question dit sous quelle hypothèse
le code a avancé, pour qu'une réponse différente se traduise par un changement borné.

---

## Q1 — E4 ne peut pas s'exercer par une gravité ≥ 1,30 · TRANCHÉE PAR LE CODE

Le ticket demande « un bras avec un choc de gravité ≥ 1,30 » pour faire mordre le plafond de
30 jours. C'est impossible : `gravite.borne_0_1` plafonne la gravité à 1,0. La force maximale
issue de la gravité vaut `2,8 × 7 = 19,6` j et la durée `20,577` j — **sous** le plafond de 30.

Le plafond mord par le **renforcement au rappel** : `force_apres_rappel` ajoute un jour par rappel
jusqu'à 30, et à force = 30 la durée calculée vaut 31,495 j, ramenée à 30. C'est exactement le
premier argument du ticket en faveur du plafond (« un souvenir servi est un souvenir rappelé »).

**Hypothèse retenue :** le plafond est implémenté et exercé en test unitaire par une force de 30
(cas A6, B8). E4 en tant que RUN reste à cadrer : soit sur un souvenir suffisamment rappelé, soit
sur un bras à `MEMOIRE__FORCE_K_IMPORTANCE` relevé. **Aucun bras E4 n'est lançable tel que le
ticket l'écrit.**

---

## Q2 — Le plancher de 2 jours ne mord jamais non plus

À gravité 0, la durée vaut déjà 2,939 j. Le plancher de 2 j ne peut mordre que si `S0` descend
sous 1,905 j ou si le seuil de service monte. Il est implémenté et testé (cas A4, A5), mais c'est
une borne de sûreté, pas un réglage actif. À signaler pour que personne ne le cite comme durée
minimale observée.

---

## Q3 — RETIRÉE le 2026-09-21 : elle reposait sur une erreur de lecture

Cette question affirmait que C2, C3 et C6 partageaient un plancher déterministe de 0,50, la
composante de retard saturant à 30 minutes, et que l'ordre de leurs gravités dépendait donc du
jugement du modèle.

**C'est faux.** La composante `incident_reseau` (0,20) est portée par toute déclaration de choc
— c'est précisément ce que le ticket 079 a branché. La gravité déterministe est donc entièrement
décidée par la déclaration : 0,37 · 0,45 · 0,62 · 0,70 · 0,90 selon le retard et la
correspondance ratée. L'échelle de E3 est reproductible sans le modèle.

Ce qui reste vrai, et qui est le vrai piège : **la composante de retard sature à 30 minutes**.
Déclarer 45, 60 ou 90 minutes donne rigoureusement la même gravité. C'est pour cette raison que
C1 descend à 25 puis 12 minutes.

---

## Q3bis — Le seuil d'entrée du bloc est une lame de couteau · À TRANCHER

**Le fait.** Un souvenir n'entre dans « Ce qui a changé récemment » — et dans le vivier des chocs,
rappelé sans condition de contexte — qu'à partir de `memoire__importance_choc = 0,70`, comparaison
`>=`.

**Atténué le 2026-09-21** par la suppression du palier de retard. Avant, un choc de voiture ne
pouvait pas dépasser 0,70 — retard saturé (0,50) + incident (0,20) — et les quatre chocs les plus
courants du dépôt (C1 premier jour, C2, C4, C6) tombaient **tous exactement sur la frontière**.
Depuis, seule une déclaration à **exactement trente minutes** y tombe : C2 vaut 0,77, C4 0,86 et
C1 premier jour 0,88. Le problème est donc réduit à un cas, mais il n'est pas supprimé — et ce cas
est précisément C6, le choc de la campagne de référence.

**Le précédent.** Le 18 septembre, `memoire__importance_choc` est passé de 0,70 à 0,50 dans
`config.yaml`, dans la conviction que le choc ne franchissait pas le seuil. Il le franchissait.
Effet recherché : nul. Effet obtenu : six souvenirs de plus dans le vivier C — rappel sans aucune
condition de contexte — et une trentaine de tests rouges énonçant la règle que la configuration
venait de contredire. Annulé le 19 septembre. Le même motif existe ailleurs : un concept naît à
une confiance de 0,50 exactement, et 0,50 est le seuil au-dessous duquel il cesse d'être servi —
225 concepts sur 231 sont restés sur cette frontière.

**Ce qui est en jeu.** Toute modification d'une pondération, du seuil de saturation du retard, ou
le retrait de la composante `incident_reseau`, fait basculer d'un coup TOUS les chocs de voiture
sous le seuil. L'hystérésis disparaîtrait alors sans qu'aucune ligne ne le dise : le run tournerait,
les agents décideraient, et la seule trace serait une part modale qui ne bouge plus.

**Proposition, en deux pièces indépendantes.**

1. **Journaliser la marge au seuil, et alarmer quand elle est nulle.** À la qualification d'un
   souvenir, écrire `gravité 0,700 · seuil 0,700 · marge +0,000` et lever une `[ALARME]` quand
   la marge est inférieure à 0,02 : « ce souvenir franchit le seuil par une marge nulle ; toute
   modification de pondération le ferait basculer ». Ne change aucun comportement, rend le
   précédent du 18 septembre impossible à répéter en silence. **Recommandé sans réserve.**

2. **Déplacer le seuil dans l'intervalle vide, à 0,66.** Les valeurs qui doivent passer commencent
   à 0,70 (déterministe) et à 0,70 aussi côté modèle (`grave` = 0,75, moins l'écart de rang de
   0,05). Les valeurs qui ne doivent pas passer s'arrêtent à 0,62 (déterministe) et 0,55 côté
   modèle (`genant` = 0,50 + 0,05). L'intervalle `]0,62 ; 0,70[` est **vide de toute valeur
   atteignable**. Un seuil à 0,66 ne change donc **aucune classification** sur les valeurs connues,
   et porte la marge minimale de 0,000 à 0,04 des deux côtés.

   Coût : une constante publiée bouge. Le chapitre 7 de l'article cite 0,70 comme « le seuil
   au-delà duquel un souvenir est servi sans condition de contexte » — la phrase devrait dire
   0,66. Aucun run n'ayant encore été joué, le faire maintenant ne coûte aucune reprise.

**Hypothèse retenue faute de réponse :** le seuil reste à 0,70 et rien n'est instrumenté. C'est
l'état actuel, et c'est celui qui a déjà coûté une demi-journée en septembre.

---

## Q4 — L'annonce de sortie de fenêtre peut être consommée par l'enquête

`_annoncer_sortie` est à front montant, mémorisé par (agent, souvenir). L'enquête du soir appelle
`memoire_noyau` comme le prompt de décision : si elle passe la première, c'est elle qui déclenche
la ligne, et la ligne est alors datée du soir de l'enquête plutôt que de la décision suivante.

**Hypothèse retenue :** le comportement est conservé — la ligne est écrite une fois, son texte est
le même, et le décalage est au plus d'une soirée. La séparer par contexte ferait deux lignes pour
un seul événement, ce qui est pire.

---

## Q5 — Le défaut `derivee` change tout run qui ne déclare rien

Tranché par l'auteur le 2026-09-21 : `memoire__mode_fenetre_changements = "derivee"` par défaut.
Conséquence à assumer : **les runs déjà archivés ne sont pas comparables à un run neuf** sans
déclarer `fixe`. Les bras de contrôle méthodologique (E2, « fixe 14 ») doivent le déclarer
explicitement.

---

## Q6 — Ce que le chapitre 7 revendique de cette campagne · TRANCHÉ PAR L'AUTEUR le 2026-09-21

Le § 7.2 de l'article s'appelle désormais **« Un choc individuel, et ce que l'agent en garde »** :
la campagne de ce ticket y est présentée comme une **étude de mécanisme sur un agent**, jamais
comme une mesure de population. Ce qui en est revendiqué est arrêté, et c'est le cadre dans
lequel les chiffres du lot A et du lot B seront lus :

- **revendiqué** — le **signe** du déplacement, et sa **forme** : un décrochage le jour du choc,
  puis un retour progressif vers le niveau d'avant ;
- **non revendiqué** — l'**ampleur** du décrochage, la **date exacte** du retour, et tout
  réalisme de l'un ou de l'autre.

Conséquence directe pour la rédaction des résultats : la phrase « elle revient dans la bande de
l'agent non exposé le 15 avril » se garde comme **observation datée**, et non comme prédiction
vérifiée. La durée de service calculée (15,29 jours pour une gravité de 0,70) reste ce qui fait
que le récit quitte le contexte ; elle ne prédit pas la date du retour comportemental, et le
chapitre écrit qu'un jour sépare les deux.

**Ce que cela retire du ticket :** rien à coder. **Ce que cela ajoute :** toute phrase de résultat
qui chiffrerait une amplitude comme si elle était réaliste est hors cadre, et le lot B doit rendre
la forme lisible — d'où le point suivant.

---

## Q7 — L'enquête du soir passe au quotidien pour la campagne suivante · TRANCHÉ le 2026-09-21

La campagne du 2026-09-21 a interrogé l'agent à **quatre jalons**. Les trois critères de la
voiture reviennent à l'entier près entre la deuxième et la troisième interrogation, et cet
intervalle est **précisément** celui où le récit du choc quitte le bloc de contexte : la dynamique
du retour n'est donc pas observée là où elle se joue.

La forme que le chapitre 7 revendique (décrochage puis retour progressif) ne se lit pas sur quatre
points. **L'enquête passe au quotidien** pour la campagne suivante.

**Coût à assumer :** une enquête par agent et par jour s'ajoute aux 6,2 requêtes par agent-jour
relevées sur cette campagne. Sur un run de 40 jours et 20 agents, c'est 800 requêtes de plus, à
mettre en regard des ~5 000 du run. **À journaliser :** le nombre d'enquêtes servies par jour, de
sorte qu'un run à cadence mixte se repère au dépouillement.

---

## Q7 — E3 et E4 : les trois sorties, reposées le 2026-09-22 · E3 TRANCHÉE, E4 OUVERTE

> 📄 **Exposé complet, lisible seul, sans codes : [`expose_duree_d_un_souvenir.md`](expose_duree_d_un_souvenir.md).**

**TRANCHÉ PAR L'AUTEUR LE 2026-09-22 — sortie 2 retenue pour E3.** La gravité est celle de
l'agent, et E3 se rejoue sur la gravité JUGÉE. Deux conditions posées avec la décision :

1. **Un garde-fou en amont.** « Il faudrait s'assurer que quand l'agent décide, on soit au niveau
   de ce qu'on avait imaginé lors de l'analyse de l'article. Si l'agent a un jugement
   inapproprié, ça ne va pas passer. » Donc : une grille d'attendus déclarée AVANT de voir les
   réponses, et un test fonctionnel qui refuse de lancer la campagne si le jugement sort de la
   plage. Forme proposée au § 6 de l'exposé — **à valider avant tout code**.
2. **La variation par profil est attendue, pas corrigée.** « Peut-être que selon le profil de la
   personne, la réponse ne sera pas systématiquement la même. » Le garde-fou la MESURE donc au
   lieu de la traiter comme du bruit.

⚠ **Défaut trouvé en rédigeant l'exposé, antérieur à D7 et indépendant d'elle :** les trois
incidents de E3 tels qu'ils sont déclarés donnent des gravités mesurées de 0,768 / 0,700 / 1,000,
soit des durées servies de 16,5 / 15,3 / 20,6 jours. La crevaison, censée être le cas faible,
arrive à un jour de la panne moteur — la part du retard est fortement concave (30 min → 0,50,
45 min → 0,64, 60 min → 0,68). **Le protocole d'origine ne produisait déjà pas 8 / 15 / 19.**

**E4 reste ouverte** et sa question est reformulée au § 7 de l'exposé : elle ne porte pas sur la
gravité (impossible d'atteindre le plafond par là — 20,6 j au maximum absolu contre 30) mais sur
l'ENTRETIEN par le rappel.

---

### Les trois sorties, telles qu'elles étaient posées

D7 a levé la prémisse d'origine : la gravité d'une entrée d'événement n'est plus celle qu'on
déclare, c'est celle que l'agent estime. Le banc du ticket 100 a mesuré ce que le jugement fait
réellement (38 appels sur Groq, zéro réponse vide) — les trois sorties sont donc à relire avec
un chiffre en main plutôt qu'avec une crainte.

### Sortie 1 — jouer E3 et E4 sous `jugement: aucun`

Le protocole d'origine tient mot pour mot : C2, C6 et C3 gardent leurs gravités déterministes, et
l'attendu 8 / 15 / 19 jours reste posé tel quel.

**Ce qu'il faut accepter :** la campagne mesure alors un dispositif qui n'est **pas** celui des
campagnes de l'article, où l'article de presse — qui ne fait rien subir — vaudrait zéro.

**Question :** l'article a-t-il besoin que E3 porte sur le dispositif des campagnes, ou lui
suffit-il que la loi durée ↔ gravité soit exercée quelque part, fût-ce sur un chemin de service ?

### Sortie 2 — réécrire l'attendu sur la gravité JUGÉE

Ce n'est plus « la durée suit la gravité déclarée » mais « la durée suit la gravité jugée », et
la prédiction se pose sur l'intensité rendue, lue dans `evenements.jsonl`.

**Ce que la mesure du 22/09 apporte :** trois échelons distincts sur cinq articles, un jugement
reproductible à quatre répétitions (amplitude 0 jour), et un agent qui **surestime** la panne
moteur (0,75 jugé contre 0,53 mesuré) au lieu de la minorer. Les durées SERVIES 4,70 / 8,23 /
11,76 / 16,17 jours couvrent l'étalement attendu (4,48 / 7,84 / 11,20 / 15,40 sont les FORCES,
qu'il faut multiplier par `ln(1/0,35)` pour obtenir une durée).

**Ce qui manque encore :** la reproductibilité mesurée l'est à **texte identique, même persona,
même journée**. Une date d'extinction dépend de la stabilité du jugement **entre agents** et
**au fil d'un run** — jamais mesurée. Trois personas suffisent à le savoir pour ~9 appels.

**Question :** accepte-t-on de poser la prédiction sur une quantité que le run produit lui-même
(l'intensité jugée) plutôt que sur une quantité déclarée avant le run ? C'est une expérience
plus honnête vis-à-vis du dispositif, et plus faible comme falsification : elle ne peut plus être
contredite par « les trois chocs vivent le même temps », seulement par « la durée ne suit pas
l'intensité que l'agent a lui-même rendue ».

### Sortie 3 — les retirer

**Ce qu'on perd :** le § du chapitre 7 sur la durée d'un souvenir n'a plus de campagne, et le
plafond de 30 jours reste du code non exercé hors test unitaire (cf. Q1).

**Question :** le chapitre en a-t-il encore besoin, maintenant que l'ambition affichée est « la
mémoire est un élément, pas une preuve causale isolée » ?

### Et E4, qui a son propre problème

Q1 l'a déjà établi et rien ne l'a changé : **aucun bras E4 n'est lançable tel que le ticket
l'écrit**, parce que `borne_0_1` plafonne la gravité à 1,0 et que la durée maximale qui en
découle (20,6 j) passe **sous** le plafond de 30. E4 ne mord que par le renforcement au rappel.

**Question :** E4 devient-elle « un souvenir suffisamment rappelé atteint le plafond » — ce qui
est exactement le premier argument du ticket en faveur du plafond — ou un bras à
`MEMOIRE__FORCE_K_IMPORTANCE` relevé, qui mesure le réglage et non le souvenir ?
