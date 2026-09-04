# Ticket 011 — Arrivées perdues : moves poussés jamais exécutés par GAMA

Des moves poussés par le controller (WebSocket 3001, canal `llm_agent_async`) ne sont
jamais exécutés côté GAMA : aucune arrivée ne revient, le watchdog force la reprise du
cycle de l'agent ~1 h simulée après l'arrivée attendue. Le filet de sécurité fonctionne,
mais la cause amont n'est pas comprise — et un agent est resté durablement bloqué.

**Pourquoi ce ticket** : campagne du 2026-08-03 (1 000 agents, mode `OFFLINE=1`,
GAMA 2025.06.4 en conteneur) — **5 alarmes « Arrivée perdue »** sur 3 060 pushs (0,16 %),
toutes récupérées par le watchdog, **zéro coupure WebSocket** sur tout le run (aucun 1006,
aucun reconnect). La perte est donc applicative, pas transport.

---

## Chronologie des 5 pertes (run de référence 2026-08-03_10_22)

| Push (réel) | Agent | Vers | Contexte d'envoi |
|---|---|---|---|
| 10:27:34 | 1440367 | leisure | Rafale post-bootstrap (1 339 pushs en 16 min) |
| 10:28:44 | 273334 | home | Rafale post-bootstrap |
| 10:37:14 | 1431408 | home | Queue de rafale |
| 12:50:44 | 1440367 | work | **Régime établi** (~81 pushs/h) — push de rattrapage du même agent |
| 13:52:23 | 375953 | home | **Régime établi** — agent jusque-là sain (2 moves exécutés) |

**Le cas 1440367 est le plus instructif** : côté GAMA, dernier signe de vie à 8h16
simulées (« finished the plan », log GAMA) ; les **3 pushs suivants ont tous été ignorés**
(10:27, 12:50, puis 13:56). Ce n'est pas une perte de message isolée : l'inhabitant GAMA
semble resté dans un état où il n'exécute plus les moves reçus. Les cas 273334/1431408/
375953 (1 seule perte chacun, reprise ensuite) ressemblent davantage à une perte de
message ponctuelle.

## Hypothèses à instruire

- **H1 — Boîte aux lettres du skill network sous rafale** : le reflex GAMA qui dépile les
  messages WebSocket les traite-t-il tous par cycle, ou peut-il en écraser/sauter quand
  plusieurs arrivent entre deux cycles ? Corrélation observée : pertes pendant la rafale
  post-bootstrap ET pendant les phases où la simulation cycle très vite (~3 min réelles
  par heure simulée, sim quasi vide d'événements).
- **H2 — État bloquant de l'inhabitant** (cas 1440367) : move reçu mais ignoré parce que
  l'agent GAMA est dans un état incompatible (on_vehicle résiduel, moving_id orphelin,
  cible non résolue…). À inspecter à chaud.
- **H3 — Sérialisation/parsing** : un contenu de move particulier (itinéraire long,
  caractère spécial) silencieusement rejeté par le parsing GAML.

## Mesure du 2026-09-04 — le phénomène s'aggrave et il n'est pas transport

Deux journées complètes de 1 000 agents, tirées le même jour, avec le même GAMA et le même
launcher :

| Run | Pushs | Arrivées perdues | Taux | Journée simulée |
|---|---:|---:|---:|---|
| 2026-08-03_10_22 (référence du ticket) | 3 060 | 5 | **0,16 %** | complète |
| 2026-09-04_01_09 (population v4) | 3 250 | 21 | **0,65 %** | complète |
| 2026-09-04_16_25 (population v5) | 3 139 | 36 | **1,15 %** | complète |

**Le transport est hors de cause, confirmé une seconde fois.** Sur le run du 16 h 25, les seules
traces WebSocket sont **quatre tentatives de connexion entre 16:25:12 et 16:25:32**, avant que
GAMA Server n'écoute — aucun 1006, aucune reconnexion pendant les 1 h 40 du run. La perte est
applicative.

**Ce que la répartition dans la journée apprend.** Les 21 pertes du run de 01 h 09 tiennent dans
**vingt minutes** (02:17 → 02:37 réelles), ce qui allait dans le sens de H1 (rafale). Les 36 pertes
du run de 16 h 25 sont au contraire **étalées sur toute la journée simulée** — de 09:21 le 16 mars
à 02:22 le 17 — donc H1 seule n'explique pas ce profil-ci ; un run rapide (1 h 41 au lieu de 9 h 36,
grâce au cache de routes enfin partagé) cycle vite en permanence, et pas seulement pendant la
rafale d'amorçage. La corrélation reste avec la **vitesse de cyclage**, pas avec la rafale.

**Le profil « agent bloqué » de H2 est reproduit, et plus marqué.** L'agent **461441** perd
**6 arrivées** sur la journée (work, home, work, home, other, home, work), toutes suivies de
`[worker] ANOMALIE push — Idle avec plan non envoyé → nouvelle tentative d'envoi` ; 279721 en perd
4, cinq autres agents 2 chacun. Le filet tient à chaque fois — 36 pertes, 36 reprises forcées — au
prix d'environ une heure simulée de retard par perte.

**Conséquence pour le protocole** : à 1,15 %, l'ordre de grandeur reste faible mais le retard
imposé (≈ 1 h simulée) touche 36 déplacements sur 5 257, soit 0,7 % du journal. À déclarer tant que
l'ACK applicatif (A2) n'est pas livré.

## Actions

### A1 — Prérequis outillage : relais d'expressions dans le launcher headless
GAMA Server ne laisse **que la socket créatrice** interroger un expériment (vérifié le
2026-08-03 : `UnableToExecuteRequest` depuis une connexion tierce). Ajouter au launcher
`scripts/gama/launch_headless.py` un petit relais (fichier de requêtes ou endpoint local)
qui transmet des expressions GAML et renvoie le résultat. Débloque l'inspection à chaud :
`first(inhabitant where (each.person_id = '…'))`, état, moving_id, on_vehicle.

### A2 — Accusé de réception applicatif des moves
GAMA renvoie un ACK (person_id + move_id) à la réception de chaque move ; le controller
marque « envoyé-et-reçu » et **retente immédiatement** un move non acquitté après N
cycles, au lieu d'attendre le watchdog (~1 h simulée de retard pour l'agent). L'ACK
transforme aussi le diagnostic : perte AVANT réception (H1/H3) vs move reçu mais jamais
exécuté (H2) devient lisible dans les logs.

### A3 — Compteur de réception côté GAMA
Dans le reflex de réception de `llm_agent_async`, compter les messages dépilés par cycle
et l'exposer (write périodique). Rapproché du compteur de pushs controller, il départage
H1 immédiatement.

### A4 — Reproduction sous rafale
Test de charge : rejouer ~1 300 pushs en quelques minutes contre un GAMA Server headless
et mesurer le taux de réception (A3). Si H1 se confirme, étaler la rafale post-bootstrap
(pacing) ou dépiler exhaustivement par cycle côté GAML.

## Critères d'acceptation

1. Cause identifiée et documentée pour les deux profils (perte ponctuelle vs agent bloqué).
2. Run 24 h : zéro « Arrivée perdue » non expliquée, ou reprise en < 5 min simulées via ACK
   (A2) au lieu de ~1 h.
3. Le cas « agent bloqué » (type 1440367) est soit corrigé côté GAML, soit détecté et
   réinitialisé proprement par le controller.

## Dimensionnement

À 10 000 agents, la rafale post-bootstrap est ~10× plus grosse : au taux observé (0,16 %),
~50 agents perdraient leur premier move et repartiraient avec ~1 h simulée de retard —
non négligeable pour les mesures du matin. Ce ticket gagne à passer avant le premier
run 10 000 en mode offline.

## Références

- Run : `experiments/archive/2026-08-03_10_22` (app.log : `grep "Arrivée perdue"`)
- Canal : `GAMA/CityTransport/models/LLMAgent.gaml` (`llm_agent_async`, websocket_server 3001)
- Watchdog : `simulation_controller.py` (« Arrivée perdue », « ANOMALIE push »)
- Limite GAMA Server multi-clients : constatée le 2026-08-03 (voir ticket, action A1)
