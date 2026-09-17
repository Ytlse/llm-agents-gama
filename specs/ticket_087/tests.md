# Ticket 087 — Contrat de tests

Écrit AVANT le code. Deux lots indépendants.

## Lot A — la restriction d'instances couvre tous les appels du run

Contexte : `llm_agent.py` appelle la passerelle à trois endroits (décision d'itinéraire,
réflexion STM, auto-réflexion LTM). Le ticket 084 n'a posé `instances_admises` que sur le
premier. Mesuré le 2026-09-16 sur le run `2026-09-16_12_48` : 5 décisions servies par
`google_gemini31_key1`, 1 `stm_reflection` servie par `mistral_key1`.

La restriction devient une propriété du CLIENT, appliquée au seuil unique par lequel les
trois appels sortent (`LLMGatewayClient.execute`), et non une ligne à recopier sur chaque
payload — un quatrième site d'appel reproduirait l'oubli.

| Cas | Ce qui est vérifié |
|---|---|
| A1 | Un client construit avec une restriction la pose sur un payload `itinary_multi_agent` |
| A2 | …sur un payload `stm_reflection` |
| A3 | …sur un payload `ltm_self_reflection` |
| A4 | Un payload qui porte DÉJÀ sa propre restriction n'est pas écrasé par celle du client |
| A5 | Un client sans restriction n'ajoute AUCUNE clé au payload (comportement d'avant le ticket) |
| A6 | Une liste vide vaut « aucune restriction » : aucune clé ajoutée |
| A7 | La restriction du client est annoncée une fois au démarrage, avec la liste |

## Lot B — le lanceur tolère les pauses normales de GAMA

Contexte : `websockets.connect` par défaut ferme la connexion si un ping reste sans réponse
20 s. Or GAMA se bloque pendant qu'il attend les décisions du LLM, et cette attente est le
régime NORMAL en `CACHE=0` — davantage encore en pénurie de jetons, où la règle du dépôt est
d'attendre le renouvellement plutôt que de dégrader. Mesuré sur le run `2026-09-16_12_48` :
23 pauses, médiane 9,0 s, maximum 40,9 s, trois au-dessus de 20 s. Le run est mort à la
troisième, tué par GAMA Server qui arrête l'expériment dont le client s'est déconnecté.

| Cas | Ce qui est vérifié |
|---|---|
| B1 | `connect` reçoit un `ping_timeout` d'au moins 20 minutes |
| B2 | `connect` garde un `ping_interval` fini : une connexion vraiment morte reste détectée |
| B3 | Le seuil est lisible et modifiable par variable d'environnement, valeur par défaut 1200 s |

Ce que le lot B ne fait PAS : masquer les pauses. Elles restent journalisées telles quelles.
