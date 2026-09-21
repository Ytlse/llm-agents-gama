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
