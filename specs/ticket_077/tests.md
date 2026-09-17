# Ticket 077 — Spécification des tests fonctionnels

> Écrite le 2026-09-15, **avant le code**. Même convention que les lots du 071 et du 075 : le
> contrat est écrit d'abord, le code ensuite, et la validation se fait par l'échec — casser une
> règle doit casser un test nommé.
>
> Objet du ticket : la mémoire apprend sur des observations fausses et ne peut pas se corriger.
> Chaque règle ci-dessous est tirée d'un constat mesuré sur `experiments/archive/2026-09-14_23_58`.

---

## A. Le vocabulaire des modes

`mode_canonique()` n'acceptait que les **étiquettes de jambes** de la hiérarchie AUAT/CEREMA
(`foot`, `bus`, `bicycle`), alors que le schéma JSON de `stm_reflection` impose au modèle les
**modes canoniques** (`walking`, `cycling`, `public_transport`…). Un seul mot sur sept traversait.

| # | Cas | Attendu |
|---|---|---|
| A1 | `walking`, `cycling`, `car`, `public_transport`, `train`, `motorbike` | rendus **tels quels** : un mode déjà canonique est son propre canonique |
| A2 | `foot`, `bus`, `bicycle`, `metro`, `rail`, `school_bus` | inchangés par rapport à avant le ticket — `walking`, `public_transport`, `cycling`, `public_transport`, `train`, `public_transport` |
| A3 | `foot,bus,foot` | `public_transport` : le mode principal continue de l'emporter, la règle de hiérarchie n'est pas touchée |
| A4 | `any` | `None` — le schéma le définit comme « pas à propos d'un mode », il ne doit pas devenir un axe |
| A5 | mot hors des deux vocabulaires (`teleport`) | `None`, **compté** dans `MODES_INCONNUS` et journalisé une seule fois |
| A6 | `None`, chaîne vide, chaîne d'espaces | `None`, sans exception |
| A7 | la liste des modes canoniques acceptés | **dérivée de la ressource gelée** (`mode_canonique` du JSON), jamais écrite en dur dans `axes.py` |
| A8 | casse et espaces (`  Walking `, `PUBLIC_TRANSPORT`) | reconnus comme leur forme canonique |
| A9 | concept écrit avec un `mode` renseigné par le modèle | `axe_objet` non vide — **règle de garde du ticket** : c'est le test qui aurait dû échouer au run du 14 septembre |

---

## B. Ce que GAMA raconte à la mémoire

### B1 — L'attente avant le départ n'est pas une marche

`step_started_at` était posé à la réception du plan, alors que l'agent attend `schedule_at` pour
bouger : le premier segment absorbait l'attente. 398 événements sur 412 avaient une distance nulle
et une durée exactement égale au retard au départ.

| # | Cas | Attendu |
|---|---|---|
| B1.1 | plan reçu à `t`, départ prévu à `t + 3600`, premier segment de 5 min | l'observation de marche porte **300 s**, pas 3900 |
| B1.2 | plan reçu et départ immédiat (`schedule_at <= t`) | durée inchangée par rapport à avant le ticket |
| B1.3 | l'attente avant départ | n'apparaît **dans aucune** observation de type `transfer` |
| B1.4 | segments suivants du même trajet | non affectés : leur chronomètre repart à la fin du segment précédent |

### B2 — La voiture n'est pas un transport collectif

Le marqueur `__DIRECT_CAR__` passait par `submit_ob_transit`, puis par un gabarit qui interrogeait
le GTFS et rendait « Trip by Unknown Unknown » — 253 fois sur le run.

| # | Cas | Attendu |
|---|---|---|
| B2.1 | segment `__DIRECT_CAR__` | observation de type `car`, rendue `[ CAR ]` avec durée et distance |
| B2.2 | segment `__DIRECT_BIKE__` | observation de type `bike`, rendue `[ BIKE ]` |
| B2.3 | segment de bus dont la ligne existe au GTFS | inchangé : `[ PUBLIC TRANSPORT ] Trip by Bus L2 …` |
| B2.4 | segment collectif dont la ligne est **introuvable** au GTFS | l'observation est produite sans nom de ligne inventé, et le cas est **journalisé** — jamais « Unknown Unknown » |
| B2.5 | aucune observation rendue au modèle | ne contient la chaîne `Unknown Unknown` |

---

## C. Les trajets à itinéraire unique

116 trajets sur 514 n'écrivaient aucune entrée de décision en mémoire courte, et le journal des
habitudes remontait au dernier `axe_objet` trouvé dans le tampon — donc au trajet précédent.

| # | Cas | Attendu |
|---|---|---|
| C1 | trajet à une seule option (aucun appel LLM) | une entrée `TRAVEL_PLAN` est écrite en STM, avec ses axes, et sa méthode de sélection est lisible |
| C2 | le contenu de cette entrée | dit explicitement que le choix était **contraint**, jamais qu'un modèle a choisi |
| C3 | arrivée d'un trajet `home` suivant un aller `work` | le journal des habitudes enregistre `home`, avec le créneau de **cette** arrivée |
| C4 | arrivée sans entrée de décision retrouvable | rien n'est enregistré, et l'écart est journalisé — jamais d'attribution au trajet précédent |
| C5 | agent dont tous les retours sont contraints | son bloc « Mes habitudes » porte autant de motifs que de motifs réellement parcourus |
| C6 | nombre d'entrées du journal après N arrivées | égal au nombre d'arrivées porteuses d'une décision, et non à une fraction |

---

## D. Ce que le rappel sert

Le lot D1 (servir l'auto-réflexion ou l'éteindre) attend une décision de l'auteur et **n'est pas
couvert ici**. Seule la mesure est contractée.

| # | Cas | Attendu |
|---|---|---|
| D2.1 | fenêtre glissante de décisions | la **concentration des rappels** est journalisée : part du top-K occupée par les dix souvenirs les plus servis |
| D2.2 | concentration au-delà du seuil | alarme `[ALARME]` sur **front montant**, une seule fois tant que le seuil reste franchi |
| D2.3 | retour sous le seuil bas | l'alarme se réarme |
| D2.4 | agent sans aucun rappel | aucune division par zéro, aucune alarme |

---

## E. L'instrumentation du prochain run

| # | Cas | Attendu |
|---|---|---|
| E1 | décision servie par la mémoire | chaque souvenir du top-K est tracé avec son identifiant, son type, son **vivier d'origine** (A/B/C), son score composite et son rang |
| E2 | toute décision, quelle que soit la méthode | l'index proposé et l'index retenu sont dans `moves.csv` — aujourd'hui `plan_selected_index` n'existe que pour 66 trajets sur 514 |
| E3 | options présentées | leur descriptif (mode, durée, correspondances) est tracé à la décision, sans passer par le texte du prompt |
| E4 | appel de réflexion | les `known_beliefs` montrés et l'opération demandée par le modèle sont tracés, pour mesurer le taux de confirmation **possible** contre **réalisé** |
| E5 | décision servie par le cache | tracée comme telle, distinctement d'un appel direct |
| E6 | run repris sans point de reprise valide | n'écrit **pas** dans le même `moves.csv` que le run rejoué — les 84 trajets rejoués du 14 septembre y figuraient deux fois |
| E7 | tout ce qui précède, réglages éteints | aucun coût, aucun fichier, aucune exception |

---

## F. Le rapport d'analyse

| # | Cas | Attendu |
|---|---|---|
| F1 | run comportant un rejeu | les trajets rejoués sont **exclus** et le rapport le déclare, avec leur nombre |
| F2 | `llm_exchanges.jsonl` en JSON concaténé multi-lignes | lu sans erreur (ce n'est pas du JSONL malgré l'extension) |
| F3 | trajet dont l'option n'est pas retrouvée dans les prompts | colonne grise **déclarée**, jamais une case vide muette |
| F4 | tableau d'itinéraires | une ligne par itinéraire distinct, une colonne par jour, bleu clair proposé et bleu foncé retenu |
| F5 | palette des modes | celle du dépôt (voiture rouge, vélo violet, TC vert, marche cyan) |
| F6 | agent sans aucun concept | section produite, vide et déclarée comme telle — l'absence de mesure ne doit pas produire un rapport parfait |
| F7 | rapport produit deux fois sur le même run | octet pour octet identique (aucun horodatage de génération dans le corps) |
