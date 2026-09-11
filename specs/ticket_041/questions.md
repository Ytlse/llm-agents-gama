# Questions vivantes — ticket 041 (Étape 3a longitudinale)

Avancé sous hypothèses (règle « questions vivantes »). À trancher avant le lot qui les porte.

## Q1 — Calendrier : jours ouvrés seulement ? (bloque L1)
**Hypothèse retenue :** on ne simule que les jours ouvrés ; la date saute du vendredi au lundi
pour que GTFS et météo restent datés correctement. 60 jours simulés = 12 semaines.
**Alternative :** simuler les 7 jours avec les mêmes chaînes d'activités (irréaliste le
week-end, mais horizon de 2 mois = 60 jours calendaires). **Pourquoi ça compte :** la
« demi-vie » se mesure en jours simulés ; le choix change son unité.

## Q2 — Effectif et stratification (bloque L0 → G1)
**Hypothèse :** N = 200 avec quota ≥ 60 agents captifs ou abonnés TC, repondération pour les
agrégats. **Alternative :** N = 100 sans quota (moins cher, pas de puissance sur le choc métro),
ou chocs à exposition choisie seulement (I3 rocade, I4 chute).

## Q3 — Deux modèles : choix sur Gemini, mémoire sur Mistral ? (bloque L0)
**Hypothèse :** oui, pour lever le goulot RPD ; même modèle de mémoire sur tous les bras ;
bras de contrôle « mémoire écrite par le modèle de choix » au palier minimal.
**Alternative :** un seul modèle partout (33 jours de quota au lieu de 14 pour le palier
étendu à 5 bras).

## Q4 — Jour du choc : météo neutre imposée ou météo réelle du calendrier ?
**Hypothèse :** météo réelle (même sur tous les bras), entrée comme covariable ; on vérifie
au pilote que le jour choisi n'est pas un jour de pluie forte.

## Q5 — Cache de décisions pendant la campagne : exact, coupé, ou sémantique ?
**Hypothèse :** correspondance exacte (ou coupé) ; reprise par rejeu des décisions archivées.
Le mode sémantique est **refusé** : risque de servir une décision pré-choc après le choc.

## Q6 — Statut de la formule w_m(t) du manuscrit
**Hypothèse :** modèle descriptif ajusté a posteriori ; jamais dans le prompt ; §5.1 à réécrire.
**Alternative :** l'implémenter comme registre d'habitudes explicite (variante M4) — alors elle
est un bras, pas la référence.

## Q7 — Palier de campagne principal : standard (26 j) ou étendu (60 j) d'emblée ?
**Hypothèse :** standard d'abord ; G4 décide l'étendu au vu des demi-vies mesurées.

## Q8 — Chocs individuels : quelle fraction des cyclistes frappée ?
**Hypothèse :** 30 %, tirage à graine fixe ; les 70 % restants sont témoins internes.

## Q9 — Encodage physique de la panne métro : suppression des légs ligne A ou +45 min ?
**Hypothèse :** suppression après 17 h le jour J (offre réellement absente, comme une panne
totale) ; le retard vécu (+45 min) ne concerne que les agents déjà en cours de trajet.

## Q10 — Faut-il un bras M-bis sur une seconde famille de modèles au palier minimal ?
**Hypothèse :** oui si le budget le permet après G2 (Tier 2 SILICA) ; sinon déclaré comme limite.
