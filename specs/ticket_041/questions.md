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

---

## Ajouts de la révision du 2026-09-15

Les questions Q1 à Q10 ci-dessus restent ouvertes, sauf Q6 (tranchée : la formule reste
descriptive, et le bras de sensibilité λ est **supprimé** — ticket 071 § 2.6, issue C) et Q3
(reformulée en Q15).

## Q11 — Quel choc pour le chapitre 7 ? (bloque toute campagne)
**Contexte :** un choc **météo** est jouable aujourd'hui sans une ligne de code (canicule des 11-12
août 2025 à 43 et 42 °C, ou neige des 20-21 novembre), grâce à la progression de date du ticket 075.
La **panne de métro** que l'article annonce demande 1 à 2 jours : `banned` est déjà déclaré dans la
requête OTP et jamais lié, plus une garde de cache OTP et la levée du refus E6.
**Hypothèse retenue :** météo pour la répétition générale du dispositif d'analyse, panne de métro
pour la mesure publiée. **Alternative :** tout jouer en météo et réécrire le chapitre.

## Q12 — Le sort de l'oracle (bloque le dispositif à trois bras)
Le bras M ne vit que dans GAMA, le bras O que dans la plateforme, et aucun chemin ne les compare
terme à terme. **Hypothèse retenue :** rejeu hors ligne des décisions du run GAMA par l'oracle depuis
`moves.csv` (pont de format, pas de décideur nouveau). **Alternatives :** brancher le décideur
`modele` dans le contrôleur GAMA (propre, coûteux) ; ou assumer la comparaison indirecte.

## Q13 — Effectif de la campagne
Cinq agents lisent une mémoire mais ne mesurent aucune part modale ; cent agents mesurent mais le
temps réel GAMA à cette échelle n'a jamais été observé (11,4 min par jour simulé à 5 agents).
**Hypothèse retenue :** palier intermédiaire à 20 agents pour mesurer le débit et le regroupement
avant d'engager 100.

## Q14 — Les week-ends dans l'horizon
`no_weekend_departures: true` reporte tout départ de samedi et dimanche au lundi : sur 60 jours
calendaires, ~17 journées sont quasi vides et les lundis surchargés. **Hypothèse retenue :** ne
compter que les jours ouvrés dans l'horizon (cohérent avec Q1), et le déclarer dans le manifeste du
run. **Alternative :** garder les 60 jours calendaires et publier l'horizon effectif.

## Q15 — Un modèle ou deux (choix / mémoire)
**Hypothèse retenue :** un seul modèle pour tout, tant que le regroupement n'est pas mesuré à
l'échelle — la mesure du 14 septembre montre que la mémoire ne pèse que 39 % des appels, et non le
double annoncé. **Alternative :** confier les consolidations à Mistral (sans plafond journalier) si
le palier à 20 agents montre que le quota est bien le facteur limitant.
