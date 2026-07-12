"""
tests/test_core.py — Tests unitaires du domaine pur (core/).

Couvre :
  - compute_batch_key   : stabilité, sensibilité aux paramètres
  - compute_priority_score : min(departure_timestamp), fallback
  - build_swrr_sequence : pondération, entrelacement

Aucun appel Redis/Celery/LLM.
"""

from collections import Counter

from llm_module.core.batching import compute_batch_key, compute_priority_score
from llm_module.core.models import _FALLBACK_PRIORITY_SCORE, AgentSpec, LLMRequest
from llm_module.core.selection import build_swrr_sequence


def _request(**overrides) -> LLMRequest:
    base = dict(
        category="itinary_multi_agent",
        agents=[AgentSpec(agent_id="a1", perception="p")],
        parameters={"temperature": 0.7},
    )
    base.update(overrides)
    return LLMRequest(**base)


class TestComputeBatchKey:
    def test_stable_for_identical_requests(self):
        assert compute_batch_key(_request()) == compute_batch_key(_request())

    def test_prefixed_by_category(self):
        assert compute_batch_key(_request()).startswith("itinary_multi_agent:")

    def test_parameter_order_does_not_matter(self):
        a = _request(parameters={"a": 1, "b": 2})
        b = _request(parameters={"b": 2, "a": 1})
        assert compute_batch_key(a) == compute_batch_key(b)

    def test_differs_on_parameters(self):
        assert compute_batch_key(_request(parameters={"temperature": 0.2})) != compute_batch_key(_request())

    def test_differs_on_force_provider(self):
        assert compute_batch_key(_request(force_provider="groq_llama4")) != compute_batch_key(_request())

    def test_differs_on_min_tpm(self):
        assert compute_batch_key(_request(min_tpm_required=30000)) != compute_batch_key(_request())

    def test_agents_do_not_change_key(self):
        # Des agents différents avec le même contexte doivent tomber dans le même batch
        other = _request(agents=[AgentSpec(agent_id="zz", perception="q")])
        assert compute_batch_key(other) == compute_batch_key(_request())


class TestComputePriorityScore:
    def test_min_departure(self):
        agents = [
            AgentSpec(agent_id="a", perception="p", departure_timestamp=200.0),
            AgentSpec(agent_id="b", perception="p", departure_timestamp=100.0),
        ]
        assert compute_priority_score(agents) == 100.0

    def test_ignores_missing_timestamps(self):
        agents = [
            AgentSpec(agent_id="a", perception="p"),
            AgentSpec(agent_id="b", perception="p", departure_timestamp=42.0),
        ]
        assert compute_priority_score(agents) == 42.0

    def test_fallback_when_no_timestamp(self):
        agents = [AgentSpec(agent_id="a", perception="p")]
        assert compute_priority_score(agents) == _FALLBACK_PRIORITY_SCORE


class TestBuildSwrrSequence:
    def test_empty(self):
        assert build_swrr_sequence({}) == []

    def test_single_provider(self):
        seq = build_swrr_sequence({"solo": 1.0})
        assert set(seq) == {"solo"}

    def test_weights_proportional(self):
        # Les poids sont normalisés en pourcentages arrondis (67/33) : on
        # vérifie le ratio approximatif, pas l'égalité exacte.
        seq = build_swrr_sequence({"heavy": 2.0, "light": 1.0})
        counts = Counter(seq)
        ratio = counts["heavy"] / counts["light"]
        assert 1.8 <= ratio <= 2.2

    def test_interleaving_no_long_runs(self):
        # SWRR doit entrelacer : pas de rafale du provider lourd plus longue que nécessaire
        seq = build_swrr_sequence({"a": 1.0, "b": 1.0})
        assert all(seq[i] != seq[i + 1] for i in range(len(seq) - 1))

    def test_all_providers_present(self):
        seq = build_swrr_sequence({"a": 1.0, "b": 5.0, "c": 0.3})
        assert set(seq) == {"a", "b", "c"}
