"""Tests des métriques métier de la catégorie itinary_multi_agent.

Ces helpers vivaient dans llm_module/worker/task_worker.py ; ils sont désormais le hook
`observe` du bundle mobilité (ticket 037). Aucun appel Celery/Redis/LLM.
"""


from mobility_llm.categories.itinary_multi_agent import (
    count_mode_mismatches as _count_mode_mismatches,
)
from mobility_llm.categories.itinary_multi_agent import (
    distance_bracket as _get_distance_bracket,
)
from mobility_llm.categories.itinary_multi_agent import (
    extract_primary_mode as _extract_primary_mode,
)


class TestExtractPrimaryMode:
    # Modes simples
    def test_bus(self):
        assert _extract_primary_mode("bus") == "bus"

    def test_car(self):
        assert _extract_primary_mode("car") == "car"

    def test_walking(self):
        assert _extract_primary_mode("walking") == "walking"

    def test_foot(self):
        assert _extract_primary_mode("foot") == "walking"

    def test_cycling(self):
        assert _extract_primary_mode("cycling") == "cycling"

    def test_velo(self):
        assert _extract_primary_mode("vélo") == "cycling"

    def test_train(self):
        assert _extract_primary_mode("train") == "train"

    def test_ter(self):
        assert _extract_primary_mode("ter") == "train"

    def test_metro(self):
        assert _extract_primary_mode("metro") == "metro"

    def test_tram(self):
        assert _extract_primary_mode("tram") == "tram"

    # Modes composés — priorité
    def test_bus_with_foot_is_bus(self):
        assert _extract_primary_mode("foot,bus,foot") == "bus"

    def test_bus_beats_train(self):
        """Le BUS gagne contre le train — c'est l'ordre de l'enquête, pas une intuition.

        Inversé le 2026-09-04 (ticket 022). L'annexe « Hiérarchie des modes » du rapport
        AUAT/CEREMA (p. 53) met le bus Tisséo au rang 4 et le TER au rang 8, et les
        microdonnées le confirment : sur 35 déplacements mixtes bus/autocar ↔ train
        tranchés par l'enquête, 34 sont codés bus. Un itinéraire « autocar liO + TER » est
        donc un déplacement en transports collectifs de surface, pas un déplacement en
        train.
        """
        assert _extract_primary_mode("bus,train") == "bus"
        assert _extract_primary_mode("foot,bus,rail,foot") == "bus"

    def test_metro_beats_bus(self):
        assert _extract_primary_mode("bus,metro") == "metro"

    def test_tram_beats_bus(self):
        assert _extract_primary_mode("tram,foot") == "tram"

    def test_train_beats_car(self):
        assert _extract_primary_mode("car,rail") == "train"

    def test_collectif_beats_car(self):
        """La voiture est au rang 19, sous tout le collectif (rangs 1 à 13).

        760 des 770 déplacements mixtes voiture + transports collectifs de l'enquête sont
        codés « transports collectifs ».
        """
        assert _extract_primary_mode("car,bus") == "bus"
        assert _extract_primary_mode("car,metro") == "metro"

    def test_cableway_nest_plus_range_dans_other(self):
        """Le Téléo et le car scolaire avaient leur propre étiquette nulle part.

        Ils tombaient dans `other` **avec un ERROR à chaque décision** : un mode réellement
        offert, journalisé comme une anomalie.
        """
        assert _extract_primary_mode("foot,cableway,foot") == "cableway"
        assert _extract_primary_mode("school_bus") == "bus"

    def test_mixed_case_normalised(self):
        assert _extract_primary_mode("BUS") == "bus"

    # Cas limites
    def test_empty_string_returns_unknown(self):
        assert _extract_primary_mode("") == "unknown"

    def test_unknown_literal_returns_unknown(self):
        assert _extract_primary_mode("unknown") == "unknown"

    def test_unrecognised_mode_returns_other(self):
        assert _extract_primary_mode("hovercraft") == "other"

    def test_voiture(self):
        assert _extract_primary_mode("voiture") == "car"

    def test_driving(self):
        assert _extract_primary_mode("driving") == "car"

    def test_tc(self):
        assert _extract_primary_mode("tc") == "bus"

    def test_transports_en_commun(self):
        assert _extract_primary_mode("transports en commun") == "bus"

    def test_subway(self):
        assert _extract_primary_mode("subway") == "metro"

    def test_tramway(self):
        assert _extract_primary_mode("tramway") == "tram"

    def test_intercites(self):
        assert _extract_primary_mode("intercités") == "train"


# ---------------------------------------------------------------------------
# _get_distance_bracket
# ---------------------------------------------------------------------------

class TestGetDistanceBracket:
    def test_under_1km(self):
        assert _get_distance_bracket(0) == "0-1km"
        assert _get_distance_bracket(999) == "0-1km"

    def test_1_to_2km(self):
        assert _get_distance_bracket(1_000) == "1-2km"
        assert _get_distance_bracket(1_999) == "1-2km"

    def test_2_to_5km(self):
        assert _get_distance_bracket(2_000) == "2-5km"
        assert _get_distance_bracket(4_999) == "2-5km"

    def test_5_to_10km(self):
        assert _get_distance_bracket(5_000) == "5-10km"
        assert _get_distance_bracket(9_999) == "5-10km"

    def test_10_to_20km(self):
        assert _get_distance_bracket(10_000) == "10-20km"
        assert _get_distance_bracket(19_999) == "10-20km"

    def test_20_to_50km(self):
        assert _get_distance_bracket(20_000) == "20-50km"
        assert _get_distance_bracket(49_999) == "20-50km"

    def test_above_50km(self):
        assert _get_distance_bracket(50_000) == ">50km"
        assert _get_distance_bracket(100_000) == ">50km"

    def test_exact_boundaries(self):
        # Les bornes sont exclusives à gauche (distance < N)
        assert _get_distance_bracket(1_000) == "1-2km"   # >= 1000 → plus 0-1km
        assert _get_distance_bracket(5_000) == "5-10km"  # >= 5000 → plus 2-5km


# ---------------------------------------------------------------------------
# _parse_ratelimit_reset_seconds
# ---------------------------------------------------------------------------

class _Metrics:
    """MetricsSink minimal (compteurs en mémoire)."""

    def __init__(self):
        self.counters = {}

    def incr(self, name, amount=1):
        self.counters[name] = self.counters.get(name, 0) + amount

    def get(self, name):
        return self.counters.get(name, 0)


class _Rt:
    def __init__(self):
        self.metrics = _Metrics()


class _Prob:
    def __init__(self, index, mode):
        self.index = index
        self.mode = mode


class _Resp:
    def __init__(self, probabilities):
        self.agent_id = "a1"
        self.probabilities = probabilities


TRAJ = ["foot", "foot,bus,foot", "car"]


class TestCountModeMismatches:

    def _run(self, entries, traj=TRAJ, rt=None):
        rt = rt or _Rt()
        _count_mode_mismatches(rt.metrics, _Resp(entries), traj, "provider_x")
        return rt.metrics.counters

    def test_etiquettes_correctes_aucun_desaccord(self):
        c = self._run([_Prob(0, "foot"), _Prob(1, "foot,bus,foot"), _Prob(2, "car")])
        assert c["mode_label_checked"] == 3
        assert "mode_label_mismatch" not in c

    def test_libelle_different_mais_meme_mode_canonique(self):
        """« BUS » pour « foot,bus,foot » n'est pas un désaccord : même mode canonique."""
        c = self._run([_Prob(1, "BUS"), _Prob(2, "voiture")])
        assert c["mode_label_checked"] == 2
        assert "mode_label_mismatch" not in c

    def test_option_confondue_detectee(self):
        """Le LLM annonce « car » sur l'index 1, qui est un bus → il note une autre option."""
        c = self._run([_Prob(0, "foot"), _Prob(1, "car")])
        assert c["mode_label_checked"] == 2
        assert c["mode_label_mismatch"] == 1

    def test_entrees_sans_etiquette_ou_hors_bornes_ignorees(self):
        c = self._run([_Prob(0, None), _Prob(9, "car"), _Prob("x", "car"), _Prob(0, "foot")])
        assert c["mode_label_checked"] == 1
        assert "mode_label_mismatch" not in c

    def test_aucune_entree_ne_compte_rien(self):
        assert self._run([]) == {}

    def test_alarme_sous_le_seuil_d_echantillon(self):
        """Quelques désaccords isolés ne déclenchent rien : sous 200 options, c'est du bruit."""
        rt = _Rt()
        for _ in range(50):
            self._run([_Prob(1, "car")], rt=rt)
        assert rt.metrics.get("mode_label_mismatch") == 50
        assert rt.metrics.get("alarme:mode_label_mismatch") == 0

    def test_alarme_au_dela_du_seuil(self):
        rt = _Rt()
        for _ in range(100):
            self._run([_Prob(0, "foot"), _Prob(1, "car"), _Prob(2, "car")], rt=rt)
        assert rt.metrics.get("mode_label_checked") == 300
        assert rt.metrics.get("mode_label_mismatch") == 100      # 33 % > seuil 5 %
        # Front montant : une seule alarme malgré 100 lots.
        assert rt.metrics.get("alarme:mode_label_mismatch") == 1
