# Périmètre de score — un déplacement compté une fois, et une seule

Ticket 057. Corrige la coupe au premier jour simulé, qui retirait 866 décisions sur 3 299
(dont 797 départs du matin) sur des exécutions sans simulateur ne portant aucun doublon.

## Le défaut

`frames.read_moves(first_day_only=True)` ne garde que le plus petit jour simulé du journal.
La coupe existe pour absorber les répétitions d'un horizon glissant en simulation GAMA : un
même couple (personne, activité) réapparaît le lendemain et pèserait deux fois.

En mode sans simulateur à horizon d'un jour, il n'y a aucune répétition — mais la coupe retire
quand même les déplacements datés du lendemain. Or `experiences/jeu.py:deplacements_attendus()`
date du lendemain le **premier déplacement de la journée** de 797 personas sur 894 : l'heure de
départ est résolue contre `precedente.start_time`, qui pour la première paire est l'activité
« home » enjambant minuit. Le périmètre scoré perd donc ses départs du matin et passe à 56,9 %
de retours au domicile, contre 43,8 % sur la journée entière et 39,0 % dans l'enquête.

## Règles

- **R1 — unicité.** Un couple (`ID Personne`, `ID Activité`) n'entre qu'une fois dans le
  périmètre de score. C'est l'invariant ; tout le reste sert à choisir *quelle* occurrence.
- **R2 — quand couper.** La coupe au premier jour simulé s'applique si l'exécution déclare
  `horizon_jours > 1`, **ou** si le journal porte au moins un couple présent sur plus d'un
  jour simulé. Les deux critères, pas un seul : le premier couvre un run multi-jours dont
  chaque journée diffère, le second un débordement qu'aucun réglage n'annonce.
- **R3 — sinon, ne rien couper.** Une exécution d'un jour sans répétition garde toutes ses
  lignes. Aucun déplacement unique n'est écarté pour cause de date.
- **R4 — filet.** Si un couple subsiste malgré tout sur plusieurs jours, seule l'occurrence du
  plus petit jour simulé est gardée. R1 tient alors même si R2 se trompe.
- **R5 — dire ce qui a été fait.** `scores.json` publie le motif appliqué
  (`horizon`, `repetitions`, `aucune`, ou `forcee` quand l'appelant impose la coupe), le
  nombre de couples répétés, et le nombre de lignes écartées par chaque règle.
- **R6 — rétrocompatibilité.** Les appelants qui passent `first_day_only=True` ou `False`
  gardent exactement le comportement d'avant ; la règle nouvelle est `"auto"`, et c'est ce
  que le scoreur passe.
- **R7 — aucun rejeu.** La règle s'applique à la LECTURE du journal. Les `moves.csv` existants
  portent déjà toutes les lignes : un rescoring hors ligne suffit, y compris pour les bras à
  décideur LLM. Aucun appel de modèle, aucun quota.

## Ce qui n'est pas corrigé ici

L'horodatage lui-même. Le premier déplacement de la journée gardera une date J+1 incohérente
avec les retours du même agenda. Sans effet sur le score une fois R1–R4 en place, mais tout
traitement qui trie par heure absolue s'en trouve affecté. Le corriger impose de rejouer les
exécutions ; décision distincte, laissée ouverte au ticket.
