# Ticket 090 — La reprise à chaud ne repaie plus les décisions déjà prises

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert et **livré le 2026-09-16**, 13 tests dédiés. Contrat : `specs/ticket_090/tests.md`,
> écrit avant le code.

---

## 1. Le problème

À la reprise à chaud, GAMA repart de son `starting_date` et **rejoue** les jours déjà vécus pour
reconstruire son état — positions des agents, et surtout où se trouve la voiture de chacun. La
mémoire, elle, est gelée depuis le ticket 075 : les agents circulent sans rien réapprendre.

Mais ils **redécident**. Et avec le cache sémantique coupé — condition d'un run journalisé sur
son périmètre complet — chaque décision rejouée est repayée au modèle.

Mesuré le 2026-09-16, après une coupure réseau volontaire au 8ᵉ jour d'un run de 20 : huit jours
à rejouer, une centaine de décisions, trois quarts d'heure d'attente réseau pour retrouver un état
déjà connu.

---

## 2. Ce qui est fait

Une **trace de rejeu** propre au run : chaque décision vivante est consignée sous la clé
`(personne, activité, instant)` dans `<workdir>/decisions_rejeu.jsonl`. Pendant la fenêtre de gel,
elle est resservie sans appel au modèle.

```
décision vivante ──▶ rejeu_decisions.tracer()  ──▶ decisions_rejeu.jsonl
                                                          │
reprise à chaud ──▶ gel_actif() ──▶ rejeu_decisions.chercher() ──┘
```

---

## 3. Pourquoi ce n'est pas « rallumer le cache »

C'est la question que ce ticket doit trancher, puisque le cache est coupé **délibérément** sur les
runs de mesure.

| | Cache sémantique | Trace de rejeu |
|---|---|---|
| Source | répertoire partagé entre runs | le workdir de **ce** run |
| Clé | empreinte d'état, **non indexée par modèle** | `(personne, activité, instant)` |
| Portée | tout le run | seulement tant que `gel_actif()` |
| Rien ne correspond | recalcul silencieux | compté, puis **alarmé** au-delà de 20 % |

Le cache peut resservir une décision produite par un autre modèle sous un autre prompt — c'est
exactement ce qui a fait le couper. Ici on ne ressert que ce que ce run a lui-même produit, et
uniquement pour rejouer des journées qu'il a déjà vécues. Hors de la fenêtre de gel, la trace
n'est **jamais** consultée : sans cette condition, elle deviendrait un cache permanent et le run
cesserait d'être journalisé sur son périmètre complet.

---

## 4. Une clé manquée n'est pas un échec, mais elle se voit

Le run appelle le modèle et continue — caler un run de vingt jours sur une clé absente serait
pire que le coût qu'on économise. Mais les manquées sont comptées, et au-delà de 20 % une
`[ALARME]` dit le taux : **un rejeu qui ne retrouve pas ses propres choix ne reconstruit pas
l'état qu'on croit reprendre.** L'alarme se lève sur front montant, une fois, pas à chaque miss.

---

## 5. Le piège qui a orienté le dessin

La première idée était de rejouer depuis `llm_exchanges.jsonl`, qui contient déjà prompts et
réponses. Impossible : ce journal est écrit **côté worker**, et son horodatage vaut
`min(departure_timestamp)` du **lot**.

```python
sim_ts = min(_scores) if _scores else None   # task_worker.py:580
```

Vérifié sur le fichier d'un run : un enregistrement porte un seul `sim_ts` pour cinq agents. Le
contrôleur ne peut donc pas prédire, avant d'appeler, la clé sous laquelle sa réponse sera
consignée — il ignore dans quel lot elle atterrira. La trace devait être écrite là où la clé est
connue : côté contrôleur, au moment de la décision.

---

## 6. Ce que le ticket ne fait pas

**Il ne supprime pas le rejeu**, seulement son coût. Faire démarrer GAMA directement au jour
voulu suppose de lui transmettre l'état de la chaîne des véhicules, que seul le contrôleur
connaît ; `starting_date` est en dur dans `Settings.gaml` et l'horizon se compte en secondes
depuis cette date. C'est le correctif de fond, et il aura son ticket.

**Il ne rattrape pas le run du 2026-09-16** : la trace n'existe pas pour les journées déjà vécues.
Le lot vaut pour les reprises futures.
