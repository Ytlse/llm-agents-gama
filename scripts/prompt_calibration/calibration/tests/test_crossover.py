"""Tests du merge / crossover (phase 6.3) — assemblage pur + génération injectée."""

from calibration.blocks import blocks_to_prompt
from calibration.models import RunConfig
from calibration.mutation import (MutationGenerator, _extract_crossover_text,
                                  assemble_crossover)
from .test_metrics import CEREMA

LOCKED = {"name": "json_schema", "mutable": False, "content": '{"type":"object"}'}


def _parent(intro):
    return [{"name": "intro_s1", "mutable": True, "content": intro}, dict(LOCKED)]


def test_extract_crossover_text_variants():
    assert _extract_crossover_text("brut") == "brut"
    assert _extract_crossover_text({"merged_prompt": "m"}) == "m"
    assert _extract_crossover_text({"prompt": "p"}) == "p"
    assert _extract_crossover_text({"autre": "x"}) == ""


def test_assemble_crossover_keeps_locked_and_drops_schema():
    merged = assemble_crossover("Une phrase fusionnee.", [dict(LOCKED)])
    # Le schéma verrouillé est réattaché exactement une fois, en fin.
    locked = [b for b in merged if b["name"] == "json_schema"]
    assert len(locked) == 1 and locked[0]["mutable"] is False
    assert merged[-1]["name"] == "json_schema"
    # Le corps est mutable et non vide.
    body = [b for b in merged if b["name"] != "json_schema"]
    assert body and all(b["mutable"] for b in body)


def test_propose_crossover_uses_injected_fn():
    # Un crossover_fn déterministe : renvoie la concaténation des deux parents.
    def fake_cross(user_msg):
        return {"merged_prompt": "Bloc A fort. Bloc B fort."}

    gen = MutationGenerator(RunConfig(), CEREMA, mutate_fn=lambda m: {},
                            crossover_fn=fake_cross)
    merged, msg = gen.propose_crossover(_parent("Bloc A fort."),
                                        _parent("Bloc B fort."))
    assert merged is not None
    text = blocks_to_prompt(merged)
    assert "Bloc A fort" in text and "Bloc B fort" in text
    assert any(not b["mutable"] for b in merged)      # schéma préservé
    assert "PARENT A" in msg and "PARENT B" in msg    # message construit


def test_propose_crossover_empty_output_returns_none():
    gen = MutationGenerator(RunConfig(), CEREMA, mutate_fn=lambda m: {},
                            crossover_fn=lambda m: {"merged_prompt": "  "})
    merged, _ = gen.propose_crossover(_parent("A"), _parent("B"))
    assert merged is None


def test_crossover_user_msg_includes_ablation_hint():
    from calibration.mutation import build_crossover_user_msg
    msg = build_crossover_user_msg(
        _parent("A"), _parent("B"),
        ablation_a=[{"bloc": "intro_s1", "delta": 4.0}],
        ablation_b=[{"bloc": "intro_s1", "delta": 3.0}])
    assert "intro_s1 (+4.0)" in msg
