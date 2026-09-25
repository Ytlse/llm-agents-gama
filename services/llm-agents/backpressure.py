"""Calcul du backpressure appliqué au /sync GAMA.

Fonctions pures, sans dépendance aux settings ni à l'app FastAPI, pour être
testables unitairement (tests/test_backpressure.py).

Deux familles :
  - frein réactif au remplissage (``compute_backpressure_interval``,
    ``update_drain_mode``) — le filet de sécurité historique ;
  - contrôle prédictif piloté par les échéances (ticket 003) :
    ``ThroughputEwma`` (débit de complétion lissé), ``time_ewma`` (lissage du
    rythme sim/réel) et ``edf_feasibility`` / ``edf_hold_needed`` (test de
    faisabilité EDF qui décide s'il faut retenir le /sync).

Plus la retenue sur départ imminent (2026-09-25) : ``departures_at_risk`` et
``hold_while`` retiennent le /sync tant qu'une décision de départ n'est pas rendue,
``late_departure_alarm_transition`` porte l'alarme des départs servis en retard.
"""

import asyncio
import math
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass


def compute_backpressure_interval(
    in_progress_count: int,
    population_size: int,
    k: float,
    cap: float,
    sans_frein: int = 0,
) -> float:
    """Délai minimal (secondes) entre deux réponses /sync, fonction du remplissage de la pile.

    Formule : ``cap * min(1, n / population)^k`` — le seuil est relatif à la
    population, ce qui garantit que le frein maximal (cap) est atteignable :
    la pile ne peut jamais dépasser la taille de la population, donc un seuil
    absolu supérieur à celle-ci rendrait le backpressure inopérant (cf. run du
    2026-07-07 : backlog 886/901 avec 0.33s de frein).

    Avec k=3.7 et cap=30 : ~0s sous 30% de backlog, ~2.3s à 50%, ~19s à 89%,
    30s à 100%.

    ⚠ SEUIL PLANCHER, AJOUTÉ LE 2026-09-22 — sans lui, un run à UN agent freinait 30 s à
    CHAQUE décision. Le ratio étant relatif à la population, une seule activité en attente sur
    une population de 1 donne 1/1 = 1, donc le frein maximal. Mesuré sur la campagne c3 : 8 s
    par pas de simulation et ~12 min par jour simulé, soit un run à un agent PLUS LENT qu'un
    run à vingt (5 s par pas). Le garde-fou calibré pour mille agents étranglait les petits.

    Ce que le plancher énonce est l'invariant réel : tant que le nombre d'activités en attente
    tient dans la capacité SIMULTANÉE de la passerelle, rien ne fait la queue, donc rien n'a
    besoin d'être freiné. En dessous de `sans_frein`, toutes les requêtes sont en vol en même
    temps ; la pile ne grossit pas. Au-dessus, la formule reprend telle quelle.

    Effet mesuré : 1/1 passe de 30,00 s à 0 s, 6/20 de 4,93 s à 0 s, et les régimes qui
    comptaient vraiment ne bougent pas — 300/1000 reste à 4,93 s, 900/1000 à 25,61 s.

    Args:
        in_progress_count: activités en attente de calcul (en vol + idle sans plan).
        population_size:   nombre total d'agents simulés.
        k:                 exposant de convexité (>1 — plus grand = frein plus tardif et abrupt).
        cap:               plafond en secondes (doit rester sous le read timeout HTTP de GAMA).
        sans_frein:        en deçà de ce nombre d'activités en attente, aucun frein. Vaut la
                           capacité simultanée de la passerelle (`world.worker_concurrency`).
                           0 rétablit le comportement d'avant le 2026-09-22.
    """
    if population_size <= 0 or in_progress_count <= 0 or cap <= 0:
        return 0.0
    if in_progress_count <= sans_frein:
        return 0.0
    ratio = min(1.0, in_progress_count / population_size)
    return cap * ratio ** k


def update_drain_mode(
    drain_active: bool,
    backlog_ratio: float,
    trigger_ratio: float,
    release_ratio: float,
) -> bool:
    """Hystérésis du mode drainage de la pile.

    Le mode s'enclenche quand le remplissage de la pile atteint ``trigger_ratio``
    et ne se relâche que lorsqu'il repasse sous ``release_ratio`` (release=0.2 :
    on attend que la pile soit vidée à 80 % avant de rendre la main à GAMA).
    Un ``trigger_ratio`` <= 0 désactive le mécanisme.

    Args:
        drain_active:  état courant du mode drainage.
        backlog_ratio: remplissage de la pile (activités en attente / population).
        trigger_ratio: seuil d'enclenchement (front montant).
        release_ratio: seuil de relâchement (doit être < trigger_ratio).
    """
    if trigger_ratio <= 0:
        return False
    if drain_active:
        return backlog_ratio > release_ratio
    return backlog_ratio >= trigger_ratio


def backlog_alarm_transition(
    alarm_active: bool,
    backlog_ratio: float,
    trigger_ratio: float,
    release_ratio: float,
    late_count: int,
    overdue_decisions: int,
) -> str:
    """Transition de l'alarme ``[ALARME] Backlog critique`` (ticket 010, A2).

    Un backlog au-dessus du seuil n'est une saturation que si des décisions
    d'itinéraire souffrent réellement : départs servis en retard
    (``late_count``) ou tâches plan/refill dont l'échéance sim est dépassée
    (``overdue_decisions``). Sinon — pile dominée par des réflexions STM ou par
    des pré-planifications à échéance lointaine, cas du drainage nocturne — le
    fonctionnement est nominal : l'appelant logge la composition en INFO.

    Retourne :
      - ``"fire"``    : front montant de l'alarme (ERROR) ;
      - ``"release"`` : alarme levée (backlog repassé sous ``release_ratio``) ;
      - ``"benign"``  : pile au-dessus du seuil mais rien d'urgent en souffrance ;
      - ``"none"``    : rien à faire.
    """
    if trigger_ratio <= 0:
        return "none"
    if alarm_active:
        return "release" if backlog_ratio < release_ratio else "none"
    if backlog_ratio < trigger_ratio:
        return "none"
    if late_count > 0 or overdue_decisions > 0:
        return "fire"
    return "benign"


# =============================================================================
# Contrôle prédictif piloté par les échéances (ticket 003)
# =============================================================================


class ThroughputEwma:
    """Débit de complétion (tâches/s) lissé exponentiellement.

    Estimateur de taux d'événements à décroissance exponentielle : chaque
    complétion injecte une impulsion ``1/tau`` dans l'accumulateur, qui décroît
    en ``exp(-Δt/tau)``. Pour un processus de complétions au débit λ, l'espérance
    de ``rate()`` converge vers λ (dR/dt = -R/tau + λ/tau → R = λ à l'équilibre).

    Choix EWMA (et non moyenne glissante 5 min) : les quotas providers sont par
    minute ; à l'épuisement, le débit s'effondre en secondes. Une moyenne 5 min
    continuerait d'annoncer un débit sain → pause déclenchée trop tard. L'EWMA
    réagit en ~tau.

    Args:
        tau_s:       constante de temps (s) — plus grand = plus lisse, plus lent.
        floor_per_s: plancher du débit rendu par ``rate`` (jamais 0 : évite un
                     T_estimé = ∞ dans le test de faisabilité).
    """

    def __init__(self, tau_s: float, floor_per_s: float):
        self.tau_s = max(1e-6, float(tau_s))
        self.floor_per_s = max(0.0, float(floor_per_s))
        self._rate = 0.0
        self._last: float | None = None

    def _decay(self, now: float) -> None:
        if self._last is None:
            self._last = now
            return
        dt = now - self._last
        if dt > 0:
            self._rate *= math.exp(-dt / self.tau_s)
            self._last = now

    def mark_completion(self, now: float) -> None:
        """Enregistre la complétion d'une tâche à l'instant ``now`` (monotonic/wall)."""
        self._decay(now)
        self._rate += 1.0 / self.tau_s

    def rate(self, now: float) -> float:
        """Débit courant (tâches/s), borné par le plancher (>= floor_per_s)."""
        self._decay(now)
        return max(self.floor_per_s, self._rate)


def time_ewma(prev_value: float | None, prev_time: float | None,
              sample: float, now: float, tau_s: float) -> float:
    """Lissage EWMA temporel d'une valeur échantillonnée à des instants irréguliers.

    Utilisé pour le rythme ``R`` (s sim / s réel, échantillonné à chaque /sync) :
    ``α = 1 - exp(-Δt/tau)`` pondère l'échantillon en fonction du temps écoulé,
    de sorte qu'un /sync espacé compte davantage qu'un /sync rapproché.

    ``prev_value`` None (premier échantillon) retourne directement ``sample``.
    """
    if prev_value is None or prev_time is None:
        return sample
    tau = max(1e-6, tau_s)
    dt = max(0.0, now - prev_time)
    alpha = 1.0 - math.exp(-dt / tau)
    return prev_value + alpha * (sample - prev_value)


@dataclass(frozen=True)
class EdfFeasibility:
    """Résultat du test de faisabilité EDF sur un snapshot de la file.

    hold:            True si au moins une échéance risque d'être manquée (avec marge).
    t_estimate_s:    pire T_k = N / D — temps réel pour résoudre toute la file.
    min_slack_sim_s: échéance la plus proche moins le temps sim courant (secondes SIM,
                     indépendant de R — sert de diagnostic « marge minimale »).
    """
    hold: bool
    t_estimate_s: float
    min_slack_sim_s: float


def edf_feasibility(
    deadlines: list[float],
    now_sim: float,
    throughput_per_s: float,
    sim_ratio: float,
    margin: float,
) -> EdfFeasibility:
    """Test de faisabilité EDF : la file tient-elle ses échéances au débit courant ?

    Avec les échéances triées ``d_1 ≤ … ≤ d_N`` (temps SIM), le débit réel ``D``
    (tâches/s) et le rythme ``R`` (s sim / s réel) :

        pour k = 1..N :
            T_k     = k / D                   # temps réel pour résoudre les k plus urgentes
            slack_k = (d_k − now_sim) / R     # temps réel avant expiration de d_k
        retenir si ∃k : T_k · marge > slack_k

    Insight : retenir le /sync gèle le temps simulé (il n'avance que si Python
    répond), donc la pause « achète » réellement du temps vis-à-vis des deadlines.

    File vide, D <= 0 ou R <= 0 → pas de rétention (T_estimé indéfini). O(N log N)
    à cause du tri (N ≤ population, négligeable au /sync).
    """
    if not deadlines or throughput_per_s <= 0 or sim_ratio <= 0:
        return EdfFeasibility(hold=False, t_estimate_s=0.0, min_slack_sim_s=0.0)

    ordered = sorted(deadlines)
    n = len(ordered)
    t_estimate_s = n / throughput_per_s
    min_slack_sim_s = ordered[0] - now_sim

    hold = False
    for k, d_k in enumerate(ordered, start=1):
        t_k = k / throughput_per_s
        slack_k = (d_k - now_sim) / sim_ratio
        if t_k * margin > slack_k:
            hold = True
            break

    return EdfFeasibility(hold=hold, t_estimate_s=t_estimate_s, min_slack_sim_s=min_slack_sim_s)


def edf_hold_needed(
    deadlines: list[float],
    now_sim: float,
    throughput_per_s: float,
    sim_ratio: float,
    margin: float,
) -> bool:
    """Décision booléenne de rétention du /sync (cf. ``edf_feasibility``)."""
    return edf_feasibility(deadlines, now_sim, throughput_per_s, sim_ratio, margin).hold


# =============================================================================
# Retenue sur départ imminent (2026-09-25)
# =============================================================================
#
# Le 2026-09-24 (bras traité 2026-09-24_17_50, quatre agents), la décision du départ de 17:01
# de l'agent 286921 est restée en vol pendant ~70 s réelles — un HTTP 503 « high demand » de
# Google. Aucun des freins ci-dessus ne la voyait : la file EDF ne contient plus une tâche
# qu'un consommateur a dépilée pour l'exécuter, et le ratio de la pile (1 sur 4) restait sous
# tous les seuils. GAMA a filé jusqu'à 18:15, le trajet est parti avec 74 min de retard, la
# journée de l'agent a glissé d'un jour, et cinq trajets manquent face au témoin.


@dataclass(frozen=True)
class PendingDeparture:
    """Décision de départ demandée et pas encore rendue (en file OU en cours d'exécution).

    key:           identifiant unique de la demande (ordre d'envoi au dispatcher).
    departure_sim: heure de départ du trajet, en temps SIMULÉ (même calcul que la décision).
    kind:          "plan" | "refill".
    requested_sim: temps simulé connu au moment de la demande.
    requested_wall: instant réel (monotonic) de la demande — sert à dire depuis combien de
                   temps la décision est attendue.
    """

    key: int
    person_id: str
    activity_id: str | None
    purpose: str | None
    departure_sim: float
    kind: str
    requested_sim: float
    requested_wall: float


def departures_at_risk(
    pending: Iterable[PendingDeparture],
    now_sim: float,
    lookahead_sim_s: float,
) -> list[PendingDeparture]:
    """Décisions en attente dont le départ tombe avant ``now_sim + lookahead_sim_s``.

    Triées par départ croissant : la première est la plus urgente. Un départ déjà dépassé
    (``departure_sim < now_sim``) est toujours à risque. ``lookahead_sim_s`` <= 0 ne garde
    que les départs déjà atteints ou dépassés.
    """
    horizon = now_sim + max(0.0, lookahead_sim_s)
    return sorted(
        (p for p in pending if p.departure_sim <= horizon),
        key=lambda p: (p.departure_sim, p.key),
    )


async def hold_while(
    predicate: Callable[[], bool],
    budget_s: float,
    poll_s: float,
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> float:
    """Attend tant que ``predicate()`` est vrai, au plus ``budget_s`` secondes réelles.

    Même motif que la boucle du mode drainage : ré-échantillonnage toutes les ``poll_s``
    secondes, sortie dès que la condition tombe. Rend la durée effectivement attendue.
    ``budget_s`` <= 0 ou condition fausse d'entrée : aucune attente.
    """
    start = clock()
    if budget_s <= 0 or not predicate():
        return 0.0
    while predicate():
        elapsed = clock() - start
        if elapsed >= budget_s:
            break
        await sleep(min(max(poll_s, 0.01), budget_s - elapsed))
    return clock() - start


def late_departure_alarm_transition(
    active: bool,
    late_count: int,
    now_sim: float,
    last_late_sim: float | None,
    rearm_sim_s: float,
) -> str:
    """Transition de l'alarme ``[ALARME] Départ servi en retard`` (run classique).

    - ``"fire"``    : premier départ servi en retard alors que l'alarme est au repos ;
    - ``"release"`` : alarme active et aucun retard depuis ``rearm_sim_s`` secondes simulées ;
    - ``"none"``    : rien à faire (y compris un nouveau retard pendant un épisode en cours,
                      qui se journalise en WARNING sans nouvelle ERROR).
    """
    if late_count > 0:
        return "none" if active else "fire"
    if active and last_late_sim is not None and now_sim - last_late_sim >= rearm_sim_s:
        return "release"
    return "none"
