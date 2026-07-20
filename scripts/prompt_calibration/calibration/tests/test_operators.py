"""Opérateurs de mutation riches — phase 4.3 du ticket 004 (DE).

``apply_mutation`` est pur : on teste reorder / merge_blocks / condense / split /
compact_delete sur des cas valides ET invalides, sans réseau.
"""

from calibration.blocks import blocks_to_prompt
from calibration.mutation import apply_mutation


def _blocks():
    return [
        {"name": "intro_s1", "mutable": True, "content": "Alpha."},
        {"name": "intro_s2", "mutable": True, "content": "Beta."},
        {"name": "bullet_1", "mutable": True, "content": "- gamma"},
        {"name": "json_schema", "mutable": False, "content": '{"type":"object"}'},
    ]


def _names(blocks):
    return [b["name"] for b in blocks]


# ── reorder ──────────────────────────────────────────────────────────────────

def test_reorder_after_anchor():
    out = apply_mutation(_blocks(), {"target_block": "intro_s1", "action": "reorder",
                                     "anchor": "bullet_1"})
    assert _names(out) == ["intro_s2", "bullet_1", "intro_s1", "json_schema"]


def test_reorder_to_start():
    out = apply_mutation(_blocks(), {"target_block": "bullet_1", "action": "reorder",
                                     "anchor": "__start__"})
    assert _names(out)[0] == "bullet_1"


def test_reorder_rejects_self_and_unknown_and_schema():
    assert apply_mutation(_blocks(), {"target_block": "intro_s1", "action": "reorder",
                                      "anchor": "intro_s1"}) is None
    assert apply_mutation(_blocks(), {"target_block": "intro_s1", "action": "reorder",
                                      "anchor": "nope"}) is None
    assert apply_mutation(_blocks(), {"target_block": "intro_s1", "action": "reorder",
                                      "anchor": "json_schema"}) is None


# ── merge_blocks ─────────────────────────────────────────────────────────────

def test_merge_blocks_removes_second():
    out = apply_mutation(_blocks(), {"target_block": "intro_s1", "action": "merge_blocks",
                                     "second_block": "intro_s2",
                                     "new_content": "Alpha et Beta."})
    assert "intro_s2" not in _names(out)
    got = next(b for b in out if b["name"] == "intro_s1")
    assert got["content"] == "Alpha et Beta."


def test_merge_blocks_rejects_schema_or_missing():
    assert apply_mutation(_blocks(), {"target_block": "intro_s1", "action": "merge_blocks",
                                      "second_block": "json_schema",
                                      "new_content": "x"}) is None
    assert apply_mutation(_blocks(), {"target_block": "intro_s1", "action": "merge_blocks",
                                      "second_block": "absent", "new_content": "x"}) is None
    # contenu vide → invalide
    assert apply_mutation(_blocks(), {"target_block": "intro_s1", "action": "merge_blocks",
                                      "second_block": "intro_s2", "new_content": " "}) is None


# ── condense (= modify plus court, nom distinct) ─────────────────────────────

def test_condense_replaces_content():
    out = apply_mutation(_blocks(), {"target_block": "intro_s1", "action": "condense",
                                     "new_content": "A."})
    assert next(b for b in out if b["name"] == "intro_s1")["content"] == "A."


def test_condense_empty_is_invalid():
    assert apply_mutation(_blocks(), {"target_block": "intro_s1", "action": "condense",
                                      "new_content": "  "}) is None


# ── split ────────────────────────────────────────────────────────────────────

def test_split_creates_extra_blocks():
    out = apply_mutation(_blocks(), {"target_block": "intro_s1", "action": "split",
                                     "new_content": "Part un.\n\nPart deux."})
    names = _names(out)
    assert names[0] == "intro_s1"
    assert next(b for b in out if b["name"] == "intro_s1")["content"] == "Part un."
    assert any(b["content"] == "Part deux." for b in out if b["name"].startswith("inserted_"))


def test_split_needs_two_parts():
    assert apply_mutation(_blocks(), {"target_block": "intro_s1", "action": "split",
                                      "new_content": "une seule partie"}) is None


# ── compact_delete (= delete, nom distinct) ──────────────────────────────────

def test_compact_delete_removes_block():
    out = apply_mutation(_blocks(), {"target_block": "intro_s2",
                                     "action": "compact_delete"})
    assert "intro_s2" not in _names(out)
    assert "json_schema" in _names(out)


def test_compact_delete_protects_schema():
    assert apply_mutation(_blocks(), {"target_block": "json_schema",
                                      "action": "compact_delete"}) is None


def test_operators_keep_schema_last_and_reconstruct():
    # Un aller-retour sur un opérateur riche produit toujours un prompt valide.
    out = apply_mutation(_blocks(), {"target_block": "intro_s1", "action": "merge_blocks",
                                     "second_block": "intro_s2", "new_content": "AB."})
    assert isinstance(blocks_to_prompt(out), str)
