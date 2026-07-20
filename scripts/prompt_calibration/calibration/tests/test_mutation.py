"""Tests de l'application de mutations (pure) et du formatage du contexte — phase 1."""

import pandas as pd

from calibration.mutation import (LEGEND_AND_SIGNS, _MUTATION_SYSTEM,
                                  _history_summary, _recent_blocks, apply_mutation,
                                  build_mutation_user_msg,
                                  extract_reflection, format_ablation_for_mutation,
                                  format_contrib_table, format_dim_detail,
                                  format_hard_negatives, format_lessons,
                                  format_mode_push, format_snippets_for_mutation,
                                  modes_from_stored, reject_kind)

BLOCKS = [
    {"name": "intro_s1", "mutable": True, "content": "Intro."},
    {"name": "bullet_1", "mutable": True, "content": "- puce"},
    {"name": "json_schema", "mutable": False, "content": '{"type":"object"}'},
]


def test_modify_replaces_content():
    out = apply_mutation(BLOCKS, {"target_block": "intro_s1", "action": "modify",
                                  "new_content": "Nouvelle intro."})
    assert out[0]["content"] == "Nouvelle intro."


def test_delete_removes_block():
    out = apply_mutation(BLOCKS, {"target_block": "bullet_1", "action": "delete"})
    assert all(b["name"] != "bullet_1" for b in out)


def test_insert_after_target_with_unique_name():
    out = apply_mutation(BLOCKS, {"target_block": "intro_s1", "action": "insert",
                                  "new_content": "Bloc inséré."})
    names = [b["name"] for b in out]
    assert names == ["intro_s1", "inserted_1", "bullet_1", "json_schema"]


def test_insert_empty_is_invalid():
    assert apply_mutation(BLOCKS, {"target_block": "intro_s1", "action": "insert",
                                   "new_content": "   "}) is None


def test_unknown_block_is_invalid():
    assert apply_mutation(BLOCKS, {"target_block": "nope", "action": "modify",
                                   "new_content": "x"}) is None


def test_non_mutable_modify_is_invalid():
    assert apply_mutation(BLOCKS, {"target_block": "json_schema", "action": "modify",
                                   "new_content": "x"}) is None


def test_delete_schema_is_invalid():
    assert apply_mutation(BLOCKS, {"target_block": "json_schema",
                                   "action": "delete"}) is None


# ── Formatage du détail par dimension (crochet compact) ──────────────────────

def test_format_dim_detail_filters_and_orders():
    detail = {"global": -10.2, "age": 6.4, "occupation": -13.1, "genre": 0.4,
              "motif": 3.0, "distance": -0.9}
    out = format_dim_detail(detail)
    # Positifs puis négatifs, magnitude décroissante ; |v| < 1 filtré.
    assert out == "[ag+6 mo+3 | oc-13 g-10]"
    assert format_dim_detail({"genre": 0.4}) == ""
    assert format_dim_detail({}) == ""
    assert format_dim_detail(None) == ""


def test_format_contrib_table_is_markdown_block_x_dim():
    results = [
        {"bloc": "b1", "delta": 4.2, "useful": True, "harmful": False, "diag": "",
         "detail": {"motif": 3.1, "occupation": -2.4, "genre": 0.3}},
        {"bloc": "b2", "delta": -5.0, "useful": False, "harmful": True, "diag": "",
         "detail": {"global": -5.0}},
    ]
    table = format_contrib_table(results)
    lines = table.splitlines()
    # En-tête markdown : colonnes « nom (abrév) » + Δ total.
    assert lines[0].startswith("| bloc |") and lines[0].endswith("| Δ tot |")
    assert "occupation (oc)" in lines[0] and "âge (ag)" in lines[0]
    assert set(lines[1].replace(" ", "")) <= {"|", "-"}          # ligne de séparation
    # Blocs triés par Δ décroissant (utile en tête) ; signes explicites.
    assert lines[2].startswith("| b1 |") and lines[3].startswith("| b2 |")
    assert "+3.1" in lines[2] and "-2.4" in lines[2]
    assert "·" in lines[2]           # genre 0.3 sous le seuil → point médian
    assert "-5.0" in lines[3]


def test_format_ablation_uses_table_and_harmful_diag():
    results = [
        {"bloc": "b1", "content": "utile", "delta": 4.2, "useful": True,
         "harmful": False, "diag": "", "detail": {"motif": 3.1, "occupation": -2.4}},
        {"bloc": "b2", "content": "nuisible", "delta": -5.0, "useful": False,
         "harmful": True, "diag": "sur-pousse voiture", "detail": {"global": -5.0}},
    ]
    out = format_ablation_for_mutation(results)
    assert "| bloc |" in out                      # table de contribution
    assert "occupation (oc)" in out               # en-tête « nom (abrév) »
    # Caption de lecture des signes, en termes d'écart, autoportant (indépendant
    # de la légende du prompt système).
    assert "réduit l'écart" in out and "creuse l'écart" in out
    assert "Blocs nuisibles" in out               # diagnostic mode conservé
    assert "b2 : sur-pousse voiture" in out
    assert format_ablation_for_mutation([]) == ""


def test_legend_and_signs_in_mutation_system():
    # Points 1 & 2 : la légende des abréviations ET la convention de signe sont
    # injectées une fois pour toutes dans le prompt système du mutateur.
    assert LEGEND_AND_SIGNS in _MUTATION_SYSTEM
    assert "ag=âge" in _MUTATION_SYSTEM and "oc=occupation" in _MUTATION_SYSTEM
    assert "PLUS IL EST BAS, MIEUX C'EST" in _MUTATION_SYSTEM
    assert "AIDE cette dimension" in _MUTATION_SYSTEM


def test_recent_blocks_dedup_most_recent_first():
    history = [
        {"iteration": 1, "mutation": {"target_block": "bullet_1"}},
        {"iteration": 2, "mutation": {"target_block": "bullet_1"}},
        {"iteration": 3, "mutation": None},
        {"iteration": 4, "mutation": {"target_block": "intro_s2"}},
    ]
    assert _recent_blocks(history) == ["intro_s2", "bullet_1"]
    assert _recent_blocks(None) == []
    assert _recent_blocks([]) == []


def test_diversity_nudge_in_user_msg():
    history = [{"iteration": 1, "mutation": {"target_block": "bullet_1"},
                "scores": {"composite": 100.0}, "kept": True}]
    msg = build_mutation_user_msg(BLOCKS, None, 100.0, {"parts_modales_2023": {"global": {}}},
                                  history=history, n_candidates=4)
    assert "Diversité des cibles" in msg and "bullet_1" in msg
    assert "bloc-cible DIFFÉRENT" in msg


# ── Réflexion sur les rejets (mémoire de leçons) ─────────────────────────────

def test_reject_kind_from_verdict_and_heuristic():
    # Verdict explicite (états récents).
    assert reject_kind("vetoed", "motif +12") == "fond"
    assert reject_kind("rejected_stat", "") == "bruit"
    assert reject_kind("rejected_race", "Δ=+0.30@n=25") == "bruit"
    assert reject_kind("rejected_tabu", "cos=0.93") == "doublon"
    assert reject_kind("rejected_score", "") == "seuil"
    # Repli heuristique (états snapshotés sans verdict).
    assert reject_kind(None, "cos=0.91") == "doublon"
    assert reject_kind(None, "Δ=+0.5@n=10") == "bruit"
    assert reject_kind(None, "motif +8") == "fond"
    assert reject_kind(None, "") == ""


def test_history_summary_labels_reject_category():
    history = [
        {"iteration": 1, "kept": False, "verdict": "vetoed", "reject_cause": "motif +12",
         "mutation": {"action": "modify", "target_block": "bullet_1", "rationale": "x"},
         "scores": {"composite": 90.0}},
        {"iteration": 2, "kept": False, "verdict": "rejected_stat", "reject_cause": "ns",
         "mutation": {"action": "modify", "target_block": "bullet_1", "rationale": "y"},
         "scores": {"composite": 91.0}},
    ]
    out = _history_summary(history)
    assert "✗ [fond]" in out
    assert "✗ [bruit]" in out


def test_format_lessons_and_extract_reflection():
    assert format_lessons("") == ""
    assert format_lessons(None) == ""
    rendered = format_lessons("Le levier vélo bute sur le motif travail.")
    assert "Mémoire des leçons" in rendered and "motif travail" in rendered
    assert extract_reflection({"reflection": "  synthèse  ", "target_block": "b"}) == "synthèse"
    assert extract_reflection({"target_block": "b"}) == ""
    assert extract_reflection("pas un dict") == ""


def test_reflection_field_toggle_in_user_msg():
    cerema = {"parts_modales_2023": {"global": {}}}
    on = build_mutation_user_msg(BLOCKS, None, 100.0, cerema,
                                 lessons="ancienne leçon", reflect=True)
    assert '"reflection"' in on and "ancienne leçon" in on
    assert "Mémoire des leçons" in on
    off = build_mutation_user_msg(BLOCKS, None, 100.0, cerema,
                                  lessons="ancienne leçon", reflect=False)
    assert '"reflection"' not in off and "ancienne leçon" not in off


# ── Snippets fournis en entier (matériau de réécriture) ──────────────────────

def test_snippets_full_content_with_safety_cap():
    long_arg = "Argument comportemental complet sur le confort du vélo. " * 4  # ~230 car.
    out = format_snippets_for_mutation(
        [{"content": long_arg, "tag_mode": "velo", "gain": 3.0}])
    # Contenu entier (> ancien cap de 110) : rien à halluciner pour le mutateur.
    assert long_arg.strip() in out
    # Cap de sécurité : un contenu anormalement long est tronqué avec ellipse.
    huge = "x" * 400
    capped = format_snippets_for_mutation([{"content": huge, "tag_mode": "velo",
                                            "gain": 3.0}])
    assert "…" in capped and "x" * 301 not in capped


# ── Matrice bloc × mode (colonne « modes poussés ») ──────────────────────────

def test_format_mode_push_abbrev_threshold_order():
    out = format_mode_push({"velo": 4.2, "voiture": -3.1, "marche": 0.4,
                            "transports_collectifs": -1.6})
    # Abréviations, tri par magnitude, seuil de bruit (marche 0.4 masquée).
    assert out == "vélo+4 voit-3 TC-2"
    assert format_mode_push({}) == "·"
    assert format_mode_push(None) == "·"
    assert format_mode_push({"marche": 0.2}) == "·"


def test_contrib_table_has_mode_push_column():
    results = [
        {"bloc": "b1", "delta": 4.2, "useful": True, "harmful": False, "diag": "",
         "detail": {"motif": 3.1}, "modes": {"velo": 5.0, "voiture": -4.0}},
        {"bloc": "b2", "delta": -5.0, "useful": False, "harmful": True, "diag": "",
         "detail": {"global": -5.0}},                     # sans modes (rétro-compat)
    ]
    table = format_contrib_table(results)
    lines = table.splitlines()
    assert "| modes poussés |" in lines[0] and lines[0].endswith("| Δ tot |")
    assert "vélo+5 voit-4" in lines[2]
    assert lines[3].count("·") >= 1                       # b2 : cellule modes = ·
    # La légende de lecture explique la colonne.
    out = format_ablation_for_mutation(results)
    assert "modes poussés" in out and "PRÉSENCE" in out


def test_modes_from_stored_roundtrip():
    stored = {"age": 3.0, "mode:velo": 4.0, "mode:voiture": -2.0}
    assert modes_from_stored(stored) == {"velo": 4.0, "voiture": -2.0}
    assert modes_from_stored({"age": 3.0}) == {}


# ── Hard negatives (exemples réels de décisions à corriger) ──────────────────

_HN_CEREMA = {
    "parts_modales_2023": {
        "global": {"marche": 25, "voiture": 50, "velo": 5,
                   "transports_collectifs": 20},
        "genre": {"Femme": {"marche": 40, "voiture": 30, "velo": 10,
                            "transports_collectifs": 20}},
    }
}


def _hn_df():
    # 6 femmes, toutes en voiture (cible voiture Femme = 30 %) → sur-représentation
    # massive de la strate genre[Femme] × voiture.
    rows = [{"agent_id": str(i), "mode_cat": "voiture", "genre": "Femme",
             "age": 30 + i, "occupation": "actif_temps_plein", "motif": "travail",
             "dist_cat": "1-2km"} for i in range(6)]
    return pd.DataFrame(rows)


def test_format_hard_negatives_shows_personas():
    out = format_hard_negatives(_hn_df(), _HN_CEREMA, k=2)
    assert "Exemples réels" in out
    # Persona concret → mode choisi, avec la strate et l'écart.
    assert "Femme, 30 ans, actif_temps_plein, travail, 1-2km → voiture" in out
    assert "genre[Femme]" in out
    # Déterministe (ordre du df) et borné à k.
    assert out.count("→ voiture") == 2
    assert out == format_hard_negatives(_hn_df(), _HN_CEREMA, k=2)


def test_format_hard_negatives_disabled_or_empty():
    assert format_hard_negatives(_hn_df(), _HN_CEREMA, k=0) == ""
    assert format_hard_negatives(None, _HN_CEREMA) == ""
    assert format_hard_negatives(pd.DataFrame(), _HN_CEREMA) == ""


def test_hard_negatives_in_user_msg():
    msg = build_mutation_user_msg(BLOCKS, _hn_df(), 100.0, _HN_CEREMA)
    assert "Exemples réels" in msg and "→ voiture" in msg
    off = build_mutation_user_msg(BLOCKS, _hn_df(), 100.0, _HN_CEREMA,
                                  hard_negatives_k=0)
    assert "Exemples réels" not in off
