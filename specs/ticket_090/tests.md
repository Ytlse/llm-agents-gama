# Ticket 090 — Contrat de tests

Écrit AVANT le code.

## Le besoin

À la reprise à chaud, GAMA repart de son `starting_date` et rejoue les jours déjà vécus pour
reconstruire son état. La mémoire, elle, est gelée jusqu'au point de reprise (ticket 075) : les
agents circulent et décident sans rien réapprendre. Mais **ils redécident**, et avec le cache
sémantique coupé — condition d'un run journalisé sur son périmètre complet — chaque décision
rejouée est repayée au modèle. Mesuré le 2026-09-16 : huit jours rejoués, ~117 décisions,
trois quarts d'heure d'attente réseau pour retrouver un état déjà connu.

## Ce qui est ajouté

Une **trace de rejeu** propre au run, écrite pendant la vie normale et relue pendant la fenêtre
de gel. Ce n'est pas le cache sémantique, et la distinction fait tout l'intérêt du lot :

| | Cache sémantique | Trace de rejeu |
|---|---|---|
| Source | répertoire partagé entre runs | le workdir de CE run |
| Clé | empreinte d'état, **non indexée par modèle** | `(personne, activité)` |
| Portée | tout le run | seulement tant que `reprise.gel_actif()` |
| Absence de correspondance | recalcul silencieux | comptée, et alarmée au-delà d'un seuil |

⚠ **Le journal `llm_exchanges.jsonl` ne peut PAS servir de source.** Il est écrit côté worker et
son `sim_ts` vaut `min(departure_timestamp)` du LOT, pas de chaque agent : cinq agents d'un même
lot y partagent un horodatage. Le contrôleur ne peut donc pas prédire, avant l'appel, la clé sous
laquelle sa réponse sera consignée. La trace doit être écrite côté contrôleur, là où
`(personne, activité)` est connu.

## Cas

| Cas | Ce qui est vérifié |
|---|---|
| A1 | Hors fenêtre de gel, une décision est tracée avec sa clé `(personne, activité)` |
| A2 | Hors fenêtre de gel, aucune décision n'est servie depuis la trace — le modèle est appelé |
| A3 | En fenêtre de gel, une clé connue est servie depuis la trace, **sans appel au modèle** |
| A4 | En fenêtre de gel, la réponse servie est identique à celle tracée (index, mode, probabilités) |
| A5 | En fenêtre de gel, une clé inconnue déclenche un appel normal : le run ne cale pas |
| A6 | En fenêtre de gel, rien n'est ajouté à la trace — un jour rejoué ne se trace pas deux fois |
| A7 | La sortie du gel rebascule sur le modèle, même pour une clé présente dans la trace |

| Cas | Comptage et alarme |
|---|---|
| B1 | Les servies et les manquées sont comptées séparément |
| B2 | Au-delà du seuil de manquées, une `[ALARME]` nomme le taux — un rejeu qui diverge est un fait à voir, pas un détail |
| B3 | Le bilan est journalisé à la sortie du gel : servies, manquées, appels épargnés |

| Cas | Ce qui ne doit pas casser |
|---|---|
| C1 | Sans trace sur disque (premier run), le comportement est celui d'avant le ticket |
| C2 | Une trace illisible ou tronquée ne fait pas échouer le run : elle est ignorée, et le dit |
| C3 | `ecarter_les_sorties_du_rejeu` ne supprime pas la trace |

## Ce que le ticket ne fait PAS

Supprimer le rejeu lui-même. Faire démarrer GAMA à une date arbitraire supposerait de lui
transmettre l'état de la chaîne des véhicules — où se trouve la voiture de chacun —, que seul le
contrôleur connaît. C'est le correctif de fond, il aura son ticket.

Il ne rend pas non plus le run du 2026-09-16 rattrapable : la trace n'existe pas pour les jours
déjà vécus. Le lot vaut pour les reprises futures.
