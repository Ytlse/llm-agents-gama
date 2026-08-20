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
"""

import math
from dataclasses import dataclass


def compute_backpressure_interval(
    in_progress_count: int,
    population_size: int,
    k: float,
    cap: float,
) -> float:
    """Délai minimal (secondes) entre deux réponses /sync, fonction du remplissage de la pile.

    Formule : ``cap * min(1, n / population)^k`` — le seuil est relatif à la
    population, ce qui garantit que le frein maximal (cap) est atteignable :
    la pile ne peut jamais dépasser la taille de la population, donc un seuil
    absolu supérieur à celle-ci rendrait le backpressure inopérant (cf. run du
    2026-07-07 : backlog 886/901 avec 0.33s de frein).

    Avec k=3.7 et cap=30 : ~0s sous 30% de backlog, ~2.3s à 50%, ~19s à 89%,
    30s à 100%.

    Args:
        in_progress_count: activités en attente de calcul (en vol + idle sans plan).
        population_size:   nombre total d'agents simulés.
        k:                 exposant de convexité (>1 — plus grand = frein plus tardif et abrupt).
        cap:               plafond en secondes (doit rester sous le read timeout HTTP de GAMA).
    """
    if population_size <= 0 or in_progress_count <= 0 or cap <= 0:
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
