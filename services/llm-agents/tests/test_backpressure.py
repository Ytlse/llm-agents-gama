"""Tests du backpressure /sync : seuil relatif à la population et délai
croissant avec le remplissage de la pile (cf. run du 2026-07-07 où la formule
à seuil absolu laissait 0.33s de frein avec 886/901 agents en attente).

Lancement : cd llm-agents && .venv/bin/python -m pytest tests/test_backpressure.py
"""

import pytest

from backpressure import (
    ThroughputEwma,
    backlog_alarm_transition,
    compute_backpressure_interval,
    edf_feasibility,
    edf_hold_needed,
    time_ewma,
    update_drain_mode,
)

K = 1.5
CAP = 30.0


class TestSeuilRelatifPopulation:
    """Le frein dépend du ratio backlog/population, pas d'un seuil absolu."""

    def test_meme_ratio_meme_delai_quelle_que_soit_la_population(self):
        # 50% de backlog → même délai pour 100, 1 000 ou 10 000 agents
        d100 = compute_backpressure_interval(50, 100, k=K, cap=CAP)
        d1k = compute_backpressure_interval(500, 1000, k=K, cap=CAP)
        d10k = compute_backpressure_interval(5000, 10000, k=K, cap=CAP)
        assert d100 == pytest.approx(d1k) == pytest.approx(d10k)

    def test_cap_atteint_a_pile_pleine_pour_toute_population(self):
        # Le frein maximal doit être atteignable : backlog = population → cap.
        # (L'ancienne formule à seuil absolu 120*pop/100 exigeait un backlog
        # de 3× la population pour atteindre le cap — donc jamais.)
        for pop in (100, 901, 1000, 10000):
            assert compute_backpressure_interval(pop, pop, k=K, cap=CAP) == pytest.approx(CAP)

    def test_backlog_superieur_a_la_population_clampe_au_cap(self):
        assert compute_backpressure_interval(1500, 1000, k=K, cap=CAP) == pytest.approx(CAP)


class TestDelaiRelatifRemplissage:
    """Le délai croît avec le remplissage de la pile, quasi nul à faible charge."""

    def test_croissance_monotone_avec_le_backlog(self):
        pop = 1000
        delais = [
            compute_backpressure_interval(n, pop, k=K, cap=CAP)
            for n in (0, 100, 300, 500, 700, 886, 1000)
        ]
        assert delais == sorted(delais)
        assert delais[0] == 0.0
        assert delais[-1] == pytest.approx(CAP)

    def test_frein_precoce_montee_progressive(self):
        # k=1.5 : freinage dès les faibles remplissages (courbe demandée le 2026-07-08)
        # 10%→~0.9s, 20%→~2.7s, 30%→~4.9s, 40%→~7.6s
        pop = 1000
        assert compute_backpressure_interval(100, pop, k=K, cap=CAP) == pytest.approx(0.95, abs=0.05)
        assert compute_backpressure_interval(200, pop, k=K, cap=CAP) == pytest.approx(2.68, abs=0.05)
        assert compute_backpressure_interval(300, pop, k=K, cap=CAP) == pytest.approx(4.93, abs=0.05)
        assert compute_backpressure_interval(400, pop, k=K, cap=CAP) == pytest.approx(7.59, abs=0.05)

    def test_frein_moyen_a_50_pourcent(self):
        # 30 * 0.5^1.5 ≈ 10.6s
        assert compute_backpressure_interval(500, 1000, k=K, cap=CAP) == pytest.approx(10.61, abs=0.05)

    def test_frein_fort_sur_le_cas_du_run_2026_07_07(self):
        # 886 en attente sur 1000 : 30 * 0.886^1.5 ≈ 25.0s
        # (au lieu des 0.33s observés avec l'ancienne formule à seuil absolu)
        delai = compute_backpressure_interval(886, 1000, k=K, cap=CAP)
        assert delai == pytest.approx(25.0, abs=0.3)


class TestCasLimites:
    def test_backlog_nul(self):
        assert compute_backpressure_interval(0, 1000, k=K, cap=CAP) == 0.0

    def test_population_nulle_ou_negative(self):
        assert compute_backpressure_interval(50, 0, k=K, cap=CAP) == 0.0
        assert compute_backpressure_interval(50, -1, k=K, cap=CAP) == 0.0

    def test_cap_nul_desactive_le_backpressure(self):
        assert compute_backpressure_interval(1000, 1000, k=K, cap=0.0) == 0.0


class TestDrainMode:
    """Hystérésis du mode drainage : enclenché à trigger, relâché sous release."""

    TRIGGER = 0.8
    RELEASE = 0.2

    def test_enclenchement_au_seuil(self):
        assert update_drain_mode(False, 0.8, self.TRIGGER, self.RELEASE) is True
        assert update_drain_mode(False, 0.79, self.TRIGGER, self.RELEASE) is False

    def test_reste_actif_entre_release_et_trigger(self):
        # Une fois enclenché, un backlog à 50% (sous trigger mais au-dessus de
        # release) maintient le drainage : c'est l'hystérésis qui garantit que
        # la pile est bien vidée à 80% avant de rendre la main.
        assert update_drain_mode(True, 0.5, self.TRIGGER, self.RELEASE) is True

    def test_relachement_sous_release(self):
        assert update_drain_mode(True, 0.2, self.TRIGGER, self.RELEASE) is False
        assert update_drain_mode(True, 0.21, self.TRIGGER, self.RELEASE) is True

    def test_inactif_reste_inactif_sous_trigger(self):
        assert update_drain_mode(False, 0.5, self.TRIGGER, self.RELEASE) is False

    def test_trigger_nul_desactive_le_mecanisme(self):
        assert update_drain_mode(True, 1.0, 0.0, self.RELEASE) is False
        assert update_drain_mode(False, 1.0, -1.0, self.RELEASE) is False


class TestBacklogAlarmTransition:
    """Ticket 010 (A2) : l'alarme backlog ne crie que sur une vraie saturation
    de décisions — pas sur le drainage nocturne des réflexions STM."""

    TRIGGER = 0.8
    RELEASE = 0.2

    def _t(self, active, ratio, late=0, overdue=0):
        return backlog_alarm_transition(
            active, ratio, self.TRIGGER, self.RELEASE,
            late_count=late, overdue_decisions=overdue,
        )

    def test_profil_2026_08_03_pile_pleine_mais_rien_en_souffrance(self):
        # 803 tâches (80% de la population), late=0, aucune échéance dépassée :
        # drainage nocturne nominal → INFO (benign), plus d'ERROR à 13:52.
        assert self._t(False, 0.80, late=0, overdue=0) == "benign"

    def test_depart_en_retard_declenche_toujours(self):
        assert self._t(False, 0.80, late=1, overdue=0) == "fire"

    def test_echeance_de_decision_depassee_declenche_toujours(self):
        assert self._t(False, 0.80, late=0, overdue=5) == "fire"

    def test_sous_le_seuil_rien(self):
        # Même avec des retards, l'alarme backlog reste liée au remplissage de
        # la pile (les retards isolés ont leur propre compteur deadline_misses).
        assert self._t(False, 0.5, late=3, overdue=2) == "none"

    def test_hysteresis_alarme_active(self):
        # Active : pas de re-déclenchement tant que la pile n'est pas résorbée…
        assert self._t(True, 0.85, late=4, overdue=9) == "none"
        assert self._t(True, 0.5) == "none"
        # …et levée sous le seuil de relâchement.
        assert self._t(True, 0.19) == "release"

    def test_trigger_nul_desactive_le_mecanisme(self):
        assert backlog_alarm_transition(False, 1.0, 0.0, self.RELEASE, 5, 5) == "none"


# =============================================================================
# Ticket 003 — contrôle prédictif piloté par les échéances
# =============================================================================


class TestThroughputEwma:
    """L'EWMA de débit converge vers le débit réel et décroît vers le plancher."""

    TAU = 90.0
    FLOOR = 0.05

    def test_convergence_vers_debit_constant(self):
        # Complétions régulières à 2 tâches/s pendant ~5 tau : rate() ≈ 2.0
        ewma = ThroughputEwma(tau_s=self.TAU, floor_per_s=self.FLOOR)
        t = 0.0
        step = 0.5  # 2 tâches/s
        for _ in range(int(5 * self.TAU / step)):
            ewma.mark_completion(t)
            t += step
        assert ewma.rate(t) == pytest.approx(2.0, rel=0.1)

    def test_decroissance_vers_le_plancher_sans_completion(self):
        ewma = ThroughputEwma(tau_s=self.TAU, floor_per_s=self.FLOOR)
        for i in range(50):
            ewma.mark_completion(i * 0.5)
        rate_actif = ewma.rate(25.0)
        assert rate_actif > self.FLOOR
        # Plus aucune complétion pendant 20 tau → retombe au plancher
        assert ewma.rate(25.0 + 20 * self.TAU) == pytest.approx(self.FLOOR)

    def test_plancher_jamais_zero(self):
        # Jamais sollicitée : rate() rend le plancher, pas 0 (évite T=∞)
        ewma = ThroughputEwma(tau_s=self.TAU, floor_per_s=self.FLOOR)
        assert ewma.rate(0.0) == pytest.approx(self.FLOOR)
        assert ewma.rate(1000.0) == pytest.approx(self.FLOOR)

    def test_reactivite_effondrement_en_moins_de_tau(self):
        # Débit établi à 4/s puis effondrement : après 1 tau, le débit estimé a
        # chuté d'au moins ~60 % (facteur exp(-1) ≈ 0.37).
        ewma = ThroughputEwma(tau_s=self.TAU, floor_per_s=self.FLOOR)
        t = 0.0
        for _ in range(int(5 * self.TAU / 0.25)):
            ewma.mark_completion(t)
            t += 0.25  # 4 tâches/s
        rate_avant = ewma.rate(t)
        rate_apres_tau = ewma.rate(t + self.TAU)
        assert rate_apres_tau < 0.4 * rate_avant


class TestTimeEwma:
    """Lissage temporel du rythme R (sim/réel)."""

    def test_premier_echantillon_passe_tel_quel(self):
        assert time_ewma(None, None, 18.0, 10.0, tau_s=30.0) == 18.0

    def test_converge_vers_nouvel_echantillon(self):
        v, t = 10.0, 0.0
        for i in range(1, 200):
            t = i * 1.0
            v = time_ewma(v, (i - 1) * 1.0, 20.0, t, tau_s=30.0)
        assert v == pytest.approx(20.0, abs=0.5)

    def test_dt_nul_ne_bouge_pas(self):
        # α = 0 si Δt = 0 → la valreur précédente est conservée
        assert time_ewma(10.0, 5.0, 99.0, 5.0, tau_s=30.0) == pytest.approx(10.0)


class TestEdfFeasibility:
    """Test de faisabilité EDF : rétention si une échéance proche est infaisable."""

    MARGIN = 1.4

    def test_file_vide_pas_de_retention(self):
        assert edf_hold_needed([], now_sim=0.0, throughput_per_s=1.0, sim_ratio=10.0, margin=self.MARGIN) is False

    def test_deadlines_lointaines_pas_de_retention(self):
        # 5 tâches, D=1/s → T_5=5s réel. Échéances dans 10h sim, R=10 → slack=3600s réel.
        deadlines = [36000.0, 36000.0, 36000.0, 36000.0, 36000.0]
        assert edf_hold_needed(deadlines, now_sim=0.0, throughput_per_s=1.0, sim_ratio=10.0, margin=self.MARGIN) is False

    def test_deadline_proche_infaisable_retention(self):
        # 10 tâches, D=0.1/s → T_10=100s réel. Échéance dans 60s sim, R=1 → slack=60s réel.
        # T·marge (140) > slack (60) → rétention.
        deadlines = [60.0] * 10
        assert edf_hold_needed(deadlines, now_sim=0.0, throughput_per_s=0.1, sim_ratio=1.0, margin=self.MARGIN) is True

    def test_sensibilite_a_la_marge(self):
        # Cas limite : T_k = slack_k exactement. marge>1 → rétention, marge=1 → non.
        # 1 tâche, D=1 → T=1s. Échéance 10s sim, R=10 → slack=1s.
        deadlines = [10.0]
        assert edf_hold_needed(deadlines, 0.0, throughput_per_s=1.0, sim_ratio=10.0, margin=1.0) is False
        assert edf_hold_needed(deadlines, 0.0, throughput_per_s=1.0, sim_ratio=10.0, margin=1.4) is True

    def test_debit_au_plancher_ne_divise_pas_par_zero(self):
        # D très faible (plancher) → T énorme → rétention, sans exception.
        deadlines = [100.0, 200.0]
        rep = edf_feasibility(deadlines, 0.0, throughput_per_s=0.05, sim_ratio=10.0, margin=self.MARGIN)
        assert rep.hold is True
        assert rep.t_estimate_s == pytest.approx(2 / 0.05)

    def test_debit_nul_ou_ratio_nul_pas_de_retention(self):
        # Garde-fous : D<=0 ou R<=0 → indéfini → pas de rétention (pas de division).
        assert edf_hold_needed([10.0], 0.0, throughput_per_s=0.0, sim_ratio=10.0, margin=self.MARGIN) is False
        assert edf_hold_needed([10.0], 0.0, throughput_per_s=1.0, sim_ratio=0.0, margin=self.MARGIN) is False

    def test_report_t_estimate_et_min_slack(self):
        deadlines = [300.0, 100.0, 200.0]  # non trié en entrée
        rep = edf_feasibility(deadlines, now_sim=50.0, throughput_per_s=2.0, sim_ratio=5.0, margin=self.MARGIN)
        assert rep.t_estimate_s == pytest.approx(3 / 2.0)
        # min_slack = échéance la plus proche (100) - now_sim (50), en secondes SIM
        assert rep.min_slack_sim_s == pytest.approx(50.0)

    def test_prefixe_urgent_detecte_meme_si_reste_lointain(self):
        # 2 tâches urgentes (échéance 5s sim) + 100 lointaines : le préfixe k=2
        # doit déclencher la rétention même si la moyenne globale semble saine.
        deadlines = [5.0, 5.0] + [100000.0] * 100
        assert edf_hold_needed(deadlines, 0.0, throughput_per_s=0.2, sim_ratio=1.0, margin=self.MARGIN) is True
