"""Tests des parties pures de décomposition/recomposition de blocs (phase 1)."""

from calibration.blocks import (blocks_to_prompt, decompose_prompt,
                                prompt_word_count, split_sentences)
from calibration.models import blocks_hash

PROMPT = (
    "Tu incarnes des personas toulousains. Choisis le mode de déplacement.\n\n"
    "Instructions :\n"
    "1. Filtrage strict des options.\n"
    "2. Matrice de coût par attribut.\n\n"
    "Critères de confort :\n"
    "- La marche est fluide et sans friction.\n"
    "- Le vélo est contraignant sous la pluie.\n\n"
    '{"type": "object", "properties": {"agents": {}}}'
)


def test_split_sentences():
    assert split_sentences("Un chat. Deux chiens. Trois.") == [
        "Un chat.", "Deux chiens.", "Trois."]


def test_decompose_produces_named_blocks():
    blocks = decompose_prompt(PROMPT)
    names = [b["name"] for b in blocks]
    assert "intro_s1" in names
    assert any(n.startswith("instr_") for n in names)
    assert any(n.startswith("bullet_") for n in names)
    # Le schéma JSON est isolé et verrouillé.
    schema = [b for b in blocks if b["name"] == "json_schema"]
    assert len(schema) == 1 and schema[0]["mutable"] is False


def test_roundtrip_idempotent():
    """decompose∘recompose est idempotent (re-décomposer donne le même texte)."""
    p1 = blocks_to_prompt(decompose_prompt(PROMPT))
    p2 = blocks_to_prompt(decompose_prompt(p1))
    assert p1 == p2


def test_hash_stable_across_roundtrip():
    b1 = decompose_prompt(PROMPT)
    b2 = decompose_prompt(blocks_to_prompt(b1))
    assert blocks_hash(b1) == blocks_hash(b2)


def test_empty_blocks_ignored():
    blocks = [{"name": "intro_s1", "mutable": True, "content": "Bonjour."},
              {"name": "intro_s2", "mutable": True, "content": "   "}]
    assert blocks_to_prompt(blocks) == "Bonjour."


def test_word_count():
    blocks = [{"name": "intro_s1", "mutable": True, "content": "un deux trois"}]
    assert prompt_word_count(blocks) == 3
