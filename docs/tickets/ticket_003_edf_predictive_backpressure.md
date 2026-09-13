# Ticket 003 — Ordonnancement EDF et contre-pression prédictive pilotée par les échéances

## Description

La désynchronisation entre le pas de temps GAMA et la latence variable des API LLM
provoque des dépassements d'échéance (agents dont le trajet arrive après l'heure de
départ prévue) et l'effondrement de la simulation à l'épuisement des quotas réseau.

Deux causes dans l'architecture actuelle :

1. **Service FIFO côté contrôleur** : les tâches de planification acquièrent le
   sémaphore `_worker_sem` (`simulation_controller.py`, `worker_concurrency=20`) dans
   l'ordre de création. Un refill d'horizon (`_precompute_one`, échéance à J+1) peut
   occuper un jeton pendant qu'une replanification urgente (`_plan_one`, départ dans
   10 min sim) attend derrière.
2. **Contre-pression réactive et aveugle aux échéances** : le frein `/sync` actuel
   (`backpressure.py`) est fonction du seul taux de remplissage de la pile
   (`cap·ratio^k` + mode drainage à hystérésis). Il ne sait pas si le backlog est
   urgent ou non : il freine trop tard quand le débit LLM s'effondre (quota), et
   freine pour rien quand le backlog est composé de refills non urgents.

**Insight qui rend la boucle de contrôle saine** : les échéances sont en temps simulé,
et le temps simulé n'avance que si Python répond au `/sync`. Retenir le `/sync` gèle
donc les échéances elles-mêmes — la pause « achète » réellement du temps par rapport
aux deadlines, contrairement à un système temps-réel classique.

## Objectifs

1. **EDF (Earliest Deadline First)** : servir les tâches de planification par échéance
   croissante (heure de départ simulée) et non par ordre d'arrivée.
2. **Contre-pression prédictive** : ne retenir le `/sync` que si le temps estimé de
   résolution de la file menace une échéance (avec marge) — vitesse maximale sinon
   (non-régression : c'est déjà le comportement sous 30 % de backlog).
3. **Notification GAMA** : quand la simulation est ralentie au-delà d'un seuil, envoyer
   à GAMA un message structuré indiquant le débit LLM réel et la vitesse de simulation,
   affiché dans la console GAMA (et réutilisable dans l'UI).
4. **Observabilité** : débit estimé, T_estimé, slack minimal et rétentions exposés en
   métriques Prometheus avant même d'activer le contrôle (phase d'observation).
5. **Filet de sécurité conservé** : le mode drainage à hystérésis existant reste actif
   en dernier recours (EDF en surcharge permanente > 100 % d'utilisation produit un
   effet domino — le gel par ratio reste la protection ultime).

## Existant réutilisable

- **EDF déjà implémenté côté `llm_module`** : les batchs sont triés par
  `priority_score = min(departure_timestamp)` (`llm_module/core/batching.py:25`) et
  `pop()` dépile les plus urgents (`llm_module/ports/batch_queue.py`). La deadline
  circule donc déjà de bout en bout — seul le maillon contrôleur est FIFO.
- **`backpressure.py`** : module pur et testé (`tests/test_backpressure.py`) — y
  ajouter les nouvelles fonctions pures (EWMA, test de faisabilité EDF).
- **Boucle de rétention du mode drainage** (`application.py` `/sync`) : le pattern
  « retenir la réponse, ré-échantillonner toutes les `drain_poll_interval` s, borner
  par le read timeout HTTP de GAMA (`min_internal_coeff_cap`) » est réutilisé tel quel
  pour la rétention prédictive.
- **`send_log` / topic `system/log`** (`application.py`) : canal Python → GAMA existant,
  affiché par `LLMAgent.gaml:199`. Le nouveau topic `system/throttle` suit le même chemin.
- **Métriques de succès déjà en place** : `_late_count` (arrivées après l'heure de
  départ prévue, `expected_arrive_at < timestamp`) et `SIM_WALL_CLOCK_RATIO`
  (accélération effective sim/réel) mesurent directement l'amélioration.

## Solution technique

### 1. Dispatcher EDF côté contrôleur

Remplacer le couple « spawn direct + sémaphore FIFO » par une file de priorité
consommée par N workers :

```python
# simulation_controller.py
self._edf_heap: list[tuple[float, int, _EdfJob]] = []   # (deadline_sim, seq, job)
self._edf_event: asyncio.Event                           # réveil des consommateurs
self._edf_consumers: list[asyncio.Task]                  # worker_concurrency tâches
```

- `_EdfJob` = coroutine factory + méta (`person_id`, `deadline_sim`, type
  `plan|refill|push`). Le `seq` monotone départage les égalités (heapq exige un
  tri total).
- **Deadlines** — déjà disponibles aux points de spawn, aucun calcul nouveau :
  - `_plan_one(person, activity, timestamp)` → `deadline_sim = timestamp`
    (base de départ du trajet : `act_end_ts` au site ligne ~385, `timestamp`
    aux sites `_try_schedule_person` / scan de fallback) ;
  - `_precompute_one(...)` → `from_act_end_ts` (calculé aujourd'hui dans la
    coroutine : le remonter à l'appelant) — naturellement dépriorisé car lointain ;
  - `_push_planned_move` → `deadline_sim = 0` (toujours prioritaire : le calcul
    est déjà fait, il ne reste qu'à pousser).
- **Consommateurs** : `worker_concurrency` tâches qui dépilent le plus urgent et
  exécutent la coroutine. Elles remplacent le sémaphore (le nombre de consommateurs
  EST la limite de concurrence). Enregistrées dans `_inflight_tasks` → annulées par
  `stop_worker()` au remplacement de scénario (cf. changelog 2026-07-09) ; la file
  est vidée au même moment.
- **Invariants préservés** :
  - `scheduling_in_progress` / `precompute_in_progress` : posés au spawn comme
    aujourd'hui (une tâche en file compte comme « en vol ») ;
  - `_worker_in_progress` et `activities_to_compute_count` : sémantique inchangée
    (file + en exécution), le drainage et le frein continuent de les lire ;
  - le bootstrap (`bootstrap_all_agents`) reste hors dispatcher : il est awaité par
    `/init` et déjà ordonné par vagues.
- Feature flag `world.edf_enabled` (défaut `true`) — `false` = spawn direct actuel,
  pour comparaison A/B.

### 2. Moniteur de débit (D) — EWMA, pas de moyenne 5 min

> La spec initiale proposait une moyenne glissante 5 min : **rejeté**. Les quotas
> providers sont par minute ; pendant un épuisement, D s'effondre en secondes et une
> moyenne 5 min continuerait d'annoncer un débit sain → pause déclenchée trop tard
> (exactement le scénario d'effondrement à corriger).

```python
# backpressure.py — pur, testable
class ThroughputEwma:
    """Débit de complétion (tâches/s) lissé exponentiellement.

    tau : constante de temps (s). À chaque complétion, incrémente ;
    la lecture applique la décroissance depuis la dernière mise à jour.
    """
    def __init__(self, tau_s: float, floor_per_s: float): ...
    def mark_completion(self, now: float) -> None: ...
    def rate(self, now: float) -> float:  # >= floor_per_s (jamais 0 : évite T=∞)
```

- **Point de mesure** : fin de `_plan_one` / `_precompute_one` (le pipeline complet
  OTP + LLM est l'unité qui draine la file — c'est ce débit-là qui détermine
  T_estimé, pas le débit API brut). Les hits du cache sémantique complètent en ms
  et gonflent naturellement D : c'est correct, ils drainent réellement la file.
- `tau_s` configurable (`world.throughput_ewma_tau_s`, défaut **90 s**),
  `floor_per_s` (`world.throughput_floor_per_s`, défaut 0.05 ≈ 3 tâches/min).

### 3. Test de faisabilité EDF et rétention prédictive du `/sync`

Condition de rétention = test de faisabilité EDF classique. Avec les deadlines en
file triées `d_1 ≤ d_2 ≤ … ≤ d_N` (snapshot du heap), le débit `D` (tâches/s réel)
et le rythme `R` (s sim / s réel, EWMA du `SIM_WALL_CLOCK_RATIO`) :

```
pour k = 1..N :
    T_k     = k / D                        # temps réel pour résoudre les k plus urgentes
    slack_k = (d_k − now_sim) / R          # temps réel avant expiration de d_k
retenir le /sync si ∃k : T_k · marge > slack_k
```

- O(N) après tri (N ≤ population, ~1 s de calcul négligeable au `/sync`) ; subsume le
  `T_estimé = N_urgent / D` de la spec initiale (le « N_urgent » n'a plus besoin d'être
  défini par un seuil arbitraire : chaque préfixe de la file est testé).
- `marge` : `world.predictive_margin`, défaut **1.4**.
- Fonction pure `edf_hold_needed(deadlines, now_sim, D, R, margin) -> bool` dans
  `backpressure.py` + tests unitaires.
- **Intégration dans `/sync`** (`application.py`) :
  - si `edf_hold_needed` → retenir la réponse comme le mode drainage (boucle de
    ré-échantillonnage toutes les `drain_poll_interval` s, borne dure
    `min_internal_coeff_cap` — le read timeout GAMA s'applique toujours) ;
  - sinon → **réponse immédiate** (le frein progressif `cap·ratio^k` est court-circuité
    quand `world.predictive_backpressure_enabled=true`) ;
  - le mode drainage par ratio (`drain_trigger_ratio`) reste évalué en dernier
    recours, seuils inchangés.
- Pendant la rétention, `R` mesuré s'effondre : le calcul du slack utilise le `R`
  EWMA figé à l'entrée en rétention (pas de rétroaction du frein sur sa propre
  condition de sortie).

### 4. Message GAMA — topic `system/throttle`

Quand la rétention prédictive dépasse un seuil, GAMA est informé du régime dégradé
avec les deux débits demandés (LLM et simulation).

**Déclenchement (hystérésis, pas de spam)** :
- front montant : rétention cumulée sur le `/sync` courant ≥
  `world.throttle_notify_threshold_s` (défaut **5 s**) → message `active: true` ;
- rafraîchissement : toutes les `world.throttle_notify_refresh_s` (défaut **30 s**)
  tant que le régime dégradé persiste ;
- front descendant : premier `/sync` servi sans rétention → message `active: false`
  (levée).

**Payload** (même canal WebSocket que `system/log`) :

```json
{
  "topic": "system/throttle",
  "payload": {
    "active": true,
    "llm_rate_per_min": 42.5,        // D × 60 (EWMA complétions)
    "sim_ratio": 18.2,               // R : secondes simulées par seconde réelle
    "backlog": 340,                  // tâches en file + en vol
    "t_estimate_s": 480.0,           // pire T_k du test de faisabilité
    "min_slack_sim_s": 5400,         // échéance la plus proche (temps sim)
    "message": "⏳ Simulation bridée : débit LLM 42.5/min, vitesse sim ×18.2, 340 tâches en file (T≈8min)"
  }
}
```

**Côté GAMA** (`LLMAgent.gaml`, reflex `get_message`, à côté du bloc `system/log`
ligne ~199) :

```gaml
if topic = "system/throttle" {
    map<string, unknown> t <- map<string, unknown>(payload_data["payload"]);
    THROTTLE_ACTIVE  <- bool(t["active"]);
    LLM_RATE_PER_MIN <- float(t["llm_rate_per_min"]);
    SIM_RATIO_PYTHON <- float(t["sim_ratio"]);
    write "[Python][throttle] " + string(t["message"]);
    continue;
}
```

Les trois globales (`Settings.gaml`) permettent d'afficher l'état dans l'UI de
l'expérience (monitor ou overlay) sans dépendre de la console. Le champ `message`
reste autoporteur : un GAMA qui ne gère pas le topic peut le traiter comme un log.

### 5. Configuration (`settings.py`, `WorldSettings`)

| Clé | Défaut | Rôle |
|---|---|---|
| `edf_enabled` | `true` | Dispatcher EDF (false = spawn direct FIFO actuel) |
| `predictive_backpressure_enabled` | `true` | Rétention prédictive (false = frein `ratio^k` actuel) |
| `throughput_ewma_tau_s` | `90.0` | Constante de temps de l'EWMA de débit |
| `throughput_floor_per_s` | `0.05` | Plancher de D (évite T_estimé = ∞) |
| `predictive_margin` | `1.4` | Marge multiplicative du test de faisabilité |
| `throttle_notify_threshold_s` | `5.0` | Rétention mini avant notification GAMA |
| `throttle_notify_refresh_s` | `30.0` | Période de rafraîchissement du message |

Les seuils existants (`min_internal_coeff_cap`, `drain_*`) sont inchangés.

### 6. Métriques Prometheus (nouvelles)

| Métrique | Type | Description |
|---|---|---|
| `controller_throughput_tasks_per_min` | Gauge | D (EWMA) × 60 |
| `controller_t_estimate_seconds` | Gauge | Pire T_k du dernier test de faisabilité |
| `controller_min_slack_sim_seconds` | Gauge | Échéance la plus proche − temps sim courant |
| `controller_predictive_hold_seconds` | Gauge | Rétention appliquée au dernier `/sync` |
| `controller_edf_queue_depth` | Gauge | Profondeur de la file EDF |
| `controller_deadline_misses_total` | Counter | Expose `_late_count` (existant, non exporté) |

## Fichiers concernés

- `llm-agents/backpressure.py` — `ThroughputEwma`, `edf_hold_needed()` (purs)
- `llm-agents/urban_mobility_agents/simulation_controller.py` — heap EDF,
  consommateurs, plumbing des deadlines aux sites de spawn, marquage des complétions,
  vidage de la file dans `stop_worker()`
- `llm-agents/handle/application.py` — branche prédictive du `/sync`, notification
  `system/throttle` (hystérésis), nouvelles gauges
- `llm-agents/settings.py` — 7 clés `WorldSettings` (tableau §5)
- `GAMA/CityTransport/models/LLMAgent.gaml` — handler `system/throttle`
- `GAMA/CityTransport/models/Settings.gaml` — globales `THROTTLE_ACTIVE`,
  `LLM_RATE_PER_MIN`, `SIM_RATIO_PYTHON`
- `llm-agents/tests/test_backpressure.py` — EWMA + faisabilité EDF
- Docs : `docs/arch/agents-lifecycle.md` (§ sémaphore → § dispatcher EDF),
  `docs/arch/monitoring.md` (métriques), `docs/changelog.md` (fin de fichier)

## Tests

**Unitaires (purs, sans I/O)**
- `ThroughputEwma` : convergence vers un débit constant, décroissance vers le plancher
  quand les complétions cessent, réactivité < tau à un effondrement de débit.
- `edf_hold_needed` : pas de rétention file vide / deadlines lointaines ; rétention si
  une deadline proche est infaisable ; sensibilité à la marge ; cas D au plancher.
- Ordre EDF : le heap sert les deadlines croissantes, un refill lointain ne passe
  jamais devant un `_plan_one` proche, `_push_planned_move` passe devant tout.

**Intégration (via `/test/init`, sans GAMA)**
- Charge saturée avec latence LLM artificielle : le taux de deadlines manquées
  (`controller_deadline_misses_total`) doit baisser vs `edf_enabled=false` (A/B).
- Effondrement de D simulé → la rétention s'engage avant l'expiration de la première
  échéance ; retour de D → relâche en ≤ 1 cycle `/sync`.
- Notification : franchissement du seuil → 1 message `active: true`, rafraîchi à la
  période, 1 message `active: false` à la levée (pas de spam intermédiaire).
- Remplacement de scénario pendant rétention : file vidée, consommateurs annulés,
  aucune action périmée poussée (non-régression du changelog 2026-07-09).

**Manuel (avec GAMA)**
- Console GAMA : `[Python][throttle] …` visible au ralentissement, levée affichée.
- Grafana : les 6 nouvelles gauges renseignées ; `sim_wall_clock_ratio` remonte plus
  vite après un épuisement de quota qu'avant le changement.

## Phasage recommandé

1. **Phase 1 — Dispatcher EDF** (meilleur ratio valeur/risque, indépendant du reste) :
   heap + consommateurs + flag. Validable seul par l'A/B sur `_late_count`.
2. **Phase 2 — Moniteur en observation** : EWMA + gauges, aucun effet sur le contrôle.
   Laisser tourner un run complet pour calibrer `tau` et `predictive_margin` sur les
   courbes réelles.
3. **Phase 3 — Rétention prédictive + notification GAMA** : activer
   `predictive_backpressure_enabled`, brancher `system/throttle` des deux côtés.

## Priorité

Haute — c'est le mécanisme qui protège les runs longs contre l'effondrement sur
épuisement de quota, et qui supprime le freinage inutile quand le backlog n'est
composé que de refills non urgents.

## Risques / limites assumées

- **EDF en surcharge permanente** : au-delà de 100 % d'utilisation, EDF fait tout
  rater plutôt que sacrifier les moins urgents — couvert par le gel (drainage ratio)
  conservé en filet.
- **Granularité de la pause** : une rétention = un `/sync`, bornée par le read timeout
  HTTP de GAMA ; un gel long est une suite de rétentions (pattern drainage existant).
- **D bimodal** (hit cache = ms, miss = s) : l'EWMA lisse, mais si le taux de hit
  change brutalement, T_estimé est faussé pendant ~tau. Amélioration possible hors
  périmètre : EWMA séparées miss LLM / OTP.
- Les échéances des agents *idle sans plan* (pas encore en file) ne sont pas vues par
  le test de faisabilité — le scan de fallback (30 s) les y injecte ; ce délai est
  couvert par la marge.
