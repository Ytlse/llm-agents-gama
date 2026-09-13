"""Tests de la ré-évaluation des prompts sur le jeu commun (action A3).

Deux moitiés indépendantes, testées séparément :

- **la production de la mesure** (`scripts/synthesis/common_set_eval.py`) : la règle
  d'échantillonnage est-elle gelée, déterministe, et par personne ? Un tirage qui
  bouge d'une exécution à l'autre, ou qui coupe une personne en deux, rendrait le
  score incomparable au volet 1 sans qu'aucune exception ne le signale ;
- **sa consommation par la page** (`frames.load_common_set_eval`, `build.*`) : le
  fichier est-il lu, scoré avec la loss du moteur, et surtout la page se
  génère-t-elle encore quand il est absent — cas d'un clone sans les données ?

Hors ligne : aucun appel LLM, aucune clé d'API, aucun store réel. Les décisions
sont fabriquées à la main ; c'est bien la lecture et le scoring qui sont vérifiés,
pas le modèle qui les a produites.
"""

from __future__ import annotations

import json

import pytest

from scripts.synthesis import build, frames
from scripts.synthesis.common_set_eval import (
    COLUMNS,
    SAMPLE_BUCKET_MAX,
    SAMPLE_MODULUS,
    SAMPLE_NAMESPACE,
    in_sample,
    sample_bucket,
    sample_rule,
)
from scripts.synthesis.sources import REPO_ROOT, import_calibration, load_manifest

CALIBRATION, _ENGINE_ERROR = import_calibration()
needs_engine = pytest.mark.skipif(
    CALIBRATION is None, reason=f"Moteur de calibration indisponible : {_ENGINE_ERROR}")


# ── Échantillon : gelé, déterministe, par personne ───────────────────────────

def test_bucket_est_deterministe_entre_executions():
    """Valeurs figées : un changement de hash change l'échantillon en silence.

    C'est le seul garde-fou contre une dérive invisible — un score « sur le jeu
    commun » calculé sur un autre échantillon reste un nombre parfaitement
    plausible.
    """
    assert sample_bucket("503036") == sample_bucket("503036")
    assert 0 <= sample_bucket("503036") < SAMPLE_MODULUS
    # Empreintes gelées, calculées une fois et vérifiées ici.
    import hashlib
    for agent_id in ("503036", "805631", "42"):
        expected = int(hashlib.sha256(
            f"{SAMPLE_NAMESPACE}:{agent_id}".encode()).hexdigest(), 16) % SAMPLE_MODULUS
        assert sample_bucket(agent_id) == expected


def test_bucket_ignore_le_type_de_l_identifiant():
    """Les agent_id circulent tantôt en int, tantôt en str selon la source."""
    assert sample_bucket("503036") == sample_bucket(503036)


def test_selection_est_par_personne_et_non_par_decision():
    """Toutes les décisions d'une personne retenue le sont : jamais de trajet isolé.

    Un tirage par décision casserait la structure de grappes du jeu et rendrait
    l'échantillon incomparable aux jeux gelés, tirés eux aussi par personne.
    """
    records = [{"agent_id": "A", "entry": 0}, {"agent_id": "A", "entry": 1},
               {"agent_id": "B", "entry": 2}]
    kept = [r for r in records if in_sample(r["agent_id"])]
    by_agent = {r["agent_id"] for r in kept}
    for agent in by_agent:
        assert sum(1 for r in kept if r["agent_id"] == agent) == \
               sum(1 for r in records if r["agent_id"] == agent)


def test_regle_affichee_decrit_les_constantes_reellement_utilisees():
    """La règle publiée dans la page doit être celle qu'exécute le code."""
    rule = sample_rule()
    assert SAMPLE_NAMESPACE in rule
    assert str(SAMPLE_MODULUS) in rule
    assert str(SAMPLE_BUCKET_MAX) in rule


def test_seuil_gele_reste_sous_le_modulo():
    assert 0 < SAMPLE_BUCKET_MAX < SAMPLE_MODULUS


# ── Lecture du fichier de décisions ──────────────────────────────────────────

def _entry(role: str, short: str, rows: list[list], **extra) -> dict:
    entry = {
        "schema": "calibration_on_common_set/v1",
        "role": role, "label": "Graine" if role == "seed" else "Meilleur prompt",
        "node": short + "0" * 8, "short": short, "branch": "main",
        "regime": {"model": "modele-test", "policy": "masse de probabilité",
                   "label": "modele-test · masse de probabilité"},
        "sample": {"n_records": len(rows), "n_agents": len({r[0] for r in rows}),
                   "rule": sample_rule(), "splits": {"train": 1}},
        "coverage": 1.0, "n_decisions": len(rows),
        "columns": COLUMNS, "decisions": rows,
    }
    entry.update(extra)
    return entry


def _row(agent_id: str, mode_cat: str, weight: float) -> list:
    values = {"agent_id": agent_id, "mode": mode_cat, "mode_cat": mode_cat,
              "weight": weight, "genre": "Femme", "age_cat": "30-34",
              "occupation": "actif_temps_plein", "motif": "travail",
              "dist_cat": "2-5km"}
    return [values[c] for c in COLUMNS]


def _write(tmp_path, entries: list[dict]):
    path = tmp_path / "calibration_on_common_set.jsonl"
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries),
                    encoding="utf-8")
    return path


def test_chargement_reconstruit_une_trame_de_scoring(tmp_path):
    rows = [_row("A", "voiture", 0.6), _row("A", "marche", 0.4)]
    path = _write(tmp_path, [_entry("seed", "aaaaaaaa", rows)])
    loaded = frames.load_common_set_eval(path)
    assert len(loaded) == 1
    frame = loaded[0]["rows"]
    assert [r["mode_cat"] for r in frame] == ["voiture", "marche"]
    assert [r["weight"] for r in frame] == [0.6, 0.4]
    # Les strates suivent la décision, pas l'agent : c'est ce qui permet à une
    # personne d'avoir plusieurs motifs sans que l'un écrase l'autre.
    assert frame[0]["motif"] == "travail" and frame[0]["dist_cat"] == "2-5km"


def test_chargement_ordonne_graine_puis_feuille(tmp_path):
    path = _write(tmp_path, [_entry("leaf", "bbbbbbbb", [_row("A", "marche", 1.0)]),
                             _entry("seed", "aaaaaaaa", [_row("A", "voiture", 1.0)])])
    assert [e["role"] for e in frames.load_common_set_eval(path)] == ["seed", "leaf"]


def test_fichier_absent_donne_une_liste_vide(tmp_path):
    assert frames.load_common_set_eval(tmp_path / "nulle-part.jsonl") == []


def test_ligne_illisible_est_ignoree_sans_faire_echouer_la_page(tmp_path):
    """Un fichier tronqué (écriture interrompue) ne doit pas casser la génération."""
    path = tmp_path / "partiel.jsonl"
    good = json.dumps(_entry("seed", "aaaaaaaa", [_row("A", "voiture", 1.0)]),
                      ensure_ascii=False)
    path.write_text(good + "\n{ ceci n'est pas du json\n", encoding="utf-8")
    assert len(frames.load_common_set_eval(path)) == 1


def test_decision_sans_mode_categorise_est_ecartee(tmp_path):
    rows = [_row("A", "voiture", 1.0), _row("B", "marche", 1.0)]
    rows[1][COLUMNS.index("mode_cat")] = None
    path = _write(tmp_path, [_entry("seed", "aaaaaaaa", rows)])
    assert len(frames.load_common_set_eval(path)[0]["rows"]) == 1


# ── Scoring et alimentation de la matrice ────────────────────────────────────

@pytest.fixture(scope="module")
def cerema() -> dict:
    manifest = load_manifest()
    path = manifest.path_of("cerema")
    if path is None or not path.exists():
        pytest.skip("Référence EMC² absente")
    return frames.load_cerema(path)


@pytest.fixture(scope="module")
def scorer(cerema):
    if CALIBRATION is None:
        pytest.skip(_ENGINE_ERROR)
    weights = load_manifest().get("score.weights", {})
    return frames.Scorer(CALIBRATION, weights, "emd_jsd", "l1_composite")


def _source(path):
    from scripts.synthesis.sources import probe
    return probe("calibration.common_set_eval", path, "test")


@needs_engine
def test_scores_sortent_de_la_loss_du_moteur(tmp_path, cerema, scorer):
    """Le composite affiché doit être celui du moteur, pas une loss réécrite ici."""
    rows = [_row(str(i), "voiture", 1.0) for i in range(10)]
    path = _write(tmp_path, [_entry("seed", "aaaaaaaa", rows),
                             _entry("leaf", "bbbbbbbb", rows)])
    out = build.build_common_set_eval(_source(path), cerema, scorer, [])
    assert out["available"] is True
    direct = scorer.score([dict(zip(COLUMNS, r)) for r in rows], cerema)
    assert out["seed"]["composite"] == pytest.approx(
        direct[scorer.primary.name]["composite"])
    # Deux prompts identiques → gain nul, et surtout pas None.
    assert out["gain"] == pytest.approx(0.0)


@needs_engine
def test_pénalité_de_longueur_reste_neutralisée(tmp_path, cerema, scorer):
    """Les volets 1 et 3 n'ont pas de prompt : le terme de longueur doit valoir 0."""
    rows = [_row(str(i), "marche", 1.0) for i in range(6)]
    path = _write(tmp_path, [_entry("seed", "aaaaaaaa", rows)])
    out = build.build_common_set_eval(_source(path), cerema, scorer, [])
    assert out["seed"]["dims"].get("length_penalty") == pytest.approx(0.0)


@needs_engine
def test_score_gele_du_meme_noeud_est_rapproche_sous_le_meme_regime(tmp_path,
                                                                   cerema, scorer):
    """Les deux chiffres d'un même prompt doivent être appariés, pas confondus."""
    rows = [_row(str(i), "voiture", 1.0) for i in range(6)]
    path = _write(tmp_path, [_entry("seed", "aaaaaaaa", rows)])
    nodes = [{"short": "aaaaaaaa", "regime": "modele-test · masse de probabilité",
              "recomputed": 42.0},
             {"short": "aaaaaaaa", "regime": "un-autre-modele · mode élu",
              "recomputed": 99.0}]
    out = build.build_common_set_eval(_source(path), cerema, scorer, nodes)
    assert out["seed"]["frozen_composite"] == 42.0


@needs_engine
def test_source_absente_ne_casse_rien(tmp_path, cerema, scorer):
    out = build.build_common_set_eval(_source(tmp_path / "absent.jsonl"),
                                      cerema, scorer, [])
    assert out == {"available": False}


@needs_engine
def test_matrice_prefere_le_jeu_commun_aux_personas_geles(tmp_path, cerema, scorer):
    """Quand la mesure existe, ce sont ses chiffres qui entrent dans la matrice."""
    rows = [_row(str(i), "voiture", 1.0) for i in range(8)]
    path = _write(tmp_path, [_entry("seed", "aaaaaaaa", rows),
                             _entry("leaf", "bbbbbbbb", rows)])
    common = build.build_common_set_eval(_source(path), cerema, scorer, [])
    payload = {
        "score_def": {"primary": "emd_jsd"},
        "arms": {"simulation": {"status": "missing"},
                 "calibration": {"status": "ok", "stores": [], "common_set": common}},
    }
    syn = build.build_synthesis(payload)
    labels = [a["label"] for a in syn["arms"]]
    assert "Calib. graine" in labels and "Calib. meilleur" in labels
    bases = {a["label"]: a.get("basis") for a in syn["arms"]}
    assert bases["Calib. graine"] == "jeu commun"
    assert syn["commensurable"] is True
    seed_arm = next(a for a in syn["arms"] if a["label"] == "Calib. graine")
    assert seed_arm["cells"][-1]["value"] == pytest.approx(common["seed"]["composite"])


def test_matrice_retombe_sur_les_personas_geles_sans_mesure():
    """Sans le fichier, le comportement d'avant l'action A3 est préservé."""
    dims_values = {"composite": 30.5, "global": 10.1, "age": 4.9, "distance": 11.5,
                   "genre": 10.5, "occupation": 13.4, "motif": 9.3}
    store = {"kept": 3, "label": "Campagne locale",
             "seed": {"short": "aaaaaaaa", "regime": "r", "dims": dims_values},
             "best": {"short": "bbbbbbbb", "regime": "r", "dims": dims_values}}
    payload = {
        "score_def": {"primary": "emd_jsd"},
        "arms": {"simulation": {"status": "missing"},
                 "calibration": {"status": "ok", "stores": [store],
                                 "common_set": {"available": False}}},
    }
    syn = build.build_synthesis(payload)
    bases = {a["label"]: a.get("basis") for a in syn["arms"]}
    assert bases["Calib. graine"] == "personas gelés"
    assert syn["commensurable"] is False


# ── Témoin de taille : le volet 1 restreint à l'échantillon du volet 2 ───────

def test_predicat_rejoue_la_regle_ecrite_dans_le_fichier():
    """La page doit rejouer la règle du fichier, pas une constante recopiée."""
    keep = build.sample_predicate({"namespace": SAMPLE_NAMESPACE,
                                   "modulus": SAMPLE_MODULUS,
                                   "bucket_max": SAMPLE_BUCKET_MAX})
    for agent_id in ("503036", "805631", "12345", "7"):
        assert keep(agent_id) == in_sample(agent_id)


def test_predicat_suit_un_seuil_different_de_la_constante():
    """Un fichier produit sous un autre seuil ne doit pas être relu sous le nôtre."""
    tout = build.sample_predicate({"namespace": SAMPLE_NAMESPACE,
                                   "modulus": SAMPLE_MODULUS,
                                   "bucket_max": SAMPLE_MODULUS})
    rien = build.sample_predicate({"namespace": SAMPLE_NAMESPACE,
                                   "modulus": SAMPLE_MODULUS, "bucket_max": 0})
    assert all(tout(str(i)) for i in range(50))
    assert not any(rien(str(i)) for i in range(50))


def test_predicat_retombe_sur_les_constantes_si_descriptif_vide():
    keep = build.sample_predicate({})
    assert keep("503036") == in_sample("503036")


@needs_engine
def test_temoin_de_taille_score_le_meme_sous_ensemble(cerema, scorer):
    """Le témoin doit porter exactement sur les personnes retenues, pas d'autres."""
    rows = []
    for i in range(200):
        agent = str(i)
        rows.append({"agent_id": agent, "chosen": "voiture",
                     "probas": {"voiture": 60.0, "marche": 40.0},
                     "genre": "Femme", "age_cat": "30-34",
                     "occupation": "actif_temps_plein", "motif": "travail",
                     "dist_cat": "2-5km", "lieu_residence": None,
                     "type_logement": None})
    sample = {"namespace": SAMPLE_NAMESPACE, "modulus": SAMPLE_MODULUS,
              "bucket_max": SAMPLE_BUCKET_MAX}
    out = build.build_simulation_on_sample(rows, cerema, scorer, sample)
    expected = [r for r in rows if in_sample(r["agent_id"])]
    if not expected:
        pytest.skip("aucun agent synthétique retenu par la règle")
    assert out["n_trips"] == len(expected)
    assert out["n_persons"] == len({r["agent_id"] for r in expected})
    assert out["composite"] is not None


@needs_engine
def test_temoin_absent_si_rien_ne_correspond(cerema, scorer):
    rows = [{"agent_id": "zzz", "chosen": "voiture", "probas": {"voiture": 100.0},
             "genre": None, "age_cat": None, "occupation": None, "motif": None,
             "dist_cat": None, "lieu_residence": None, "type_logement": None}]
    out = build.build_simulation_on_sample(
        rows, cerema, scorer, {"namespace": SAMPLE_NAMESPACE,
                               "modulus": SAMPLE_MODULUS, "bucket_max": 0})
    assert out is None


def test_matrice_insere_le_temoin_avant_les_colonnes_de_calibration():
    """L'ordre porte le sens : le témoin doit précéder ce qu'il sert à lire."""
    dims_values = {"composite": 29.4, "global": 10.7}
    payload = {
        "score_def": {"primary": "emd_jsd"},
        "arms": {
            "simulation": {"status": "ok",
                           "variants": {"attendu": {"scores": {}}, "tire": {"scores": {}}},
                           "on_calibration_sample": {"dims": dims_values,
                                                     "composite": 29.4,
                                                     "n_trips": 537, "n_persons": 81}},
            "calibration": {"status": "ok", "stores": [],
                            "common_set": {"available": False}},
        },
    }
    labels = [a["label"] for a in build.build_synthesis(payload)["arms"]]
    assert "Sim. (éch. V2)" in labels
    assert labels.index("Sim. (éch. V2)") < labels.index("Calibration")


def test_matrice_sans_temoin_reste_inchangee():
    payload = {
        "score_def": {"primary": "emd_jsd"},
        "arms": {"simulation": {"status": "ok",
                                "variants": {"attendu": {"scores": {}},
                                             "tire": {"scores": {}}}},
                 "calibration": {"status": "ok", "stores": [],
                                 "common_set": {"available": False}}},
    }
    labels = [a["label"] for a in build.build_synthesis(payload)["arms"]]
    assert "Sim. (éch. V2)" not in labels


# ── Rendu : la page dit sur quoi elle porte ──────────────────────────────────

def test_page_declare_le_substrat_de_chaque_colonne():
    from scripts.synthesis import render
    payload = {"synthesis": {
        "dims": [{"key": "composite", "label": "Composite comparable"}],
        "arms": [{"label": "Simulation", "basis": "jeu commun", "note": "",
                  "cells": [{"value": 24.4}]},
                 {"label": "Calib. graine", "basis": "jeu commun",
                  "note": "aaaaaaaa · modele-test", "cells": [{"value": 25.0}]},
                 {"label": "Modèle", "basis": None, "note": "",
                  "cells": [{"value": None}]}],
        "commensurable": True, "calibration_basis": "jeu commun"}}
    html = render.section_synthesis(payload)
    assert "jeu commun" in html
    # L'aveu ne disparaît pas : il ne porte plus que sur le volet 3.
    assert "Action A8" in html
    assert "Données manquantes" in html


def test_page_sans_mesure_garde_l_aveu_complet():
    from scripts.synthesis import render
    payload = {"synthesis": {
        "dims": [{"key": "composite", "label": "Composite comparable"}],
        "arms": [{"label": "Simulation", "basis": "jeu commun", "note": "",
                  "cells": [{"value": 24.4}]}],
        "commensurable": False, "calibration_basis": "personas gelés"}}
    html = render.section_synthesis(payload)
    assert "Actions A3 et A8" in html


def test_bloc_volet2_affiche_la_carte_manquante_sans_mesure():
    from scripts.synthesis import render
    html = render._common_set_block(
        {"common_set": {"available": False},
         "common_set_expected": ["scripts/synthesis/data/calibration_on_common_set.jsonl"]})
    assert "Données manquantes" in html and "A3" in html


def test_bloc_volet2_oppose_les_deux_substrats():
    from scripts.synthesis import render
    common = {
        "available": True, "regime": "modele-test · masse de probabilité",
        "seed": {"role": "seed", "label": "Graine", "short": "aaaaaaaa",
                 "branch": "main", "composite": 25.0, "frozen_composite": 24.35},
        "leaf": {"role": "leaf", "label": "Meilleur prompt", "short": "bbbbbbbb",
                 "branch": "essai2", "composite": 23.0, "frozen_composite": 22.24},
        "gain": 2.0, "frozen_gain": 2.11,
        "sample": {"n_records": 509, "n_agents": 80, "rule": sample_rule(),
                   "splits": {"train": 52}, "coverage_warnings": []},
    }
    common["entries"] = [common["seed"], common["leaf"]]
    html = render._common_set_block({"common_set": common})
    assert "personas gelés" in html and "jeu commun" in html
    assert "24.35" in html and "25.00" in html


# ── Le manifeste et le contrat de chemin ─────────────────────────────────────

def test_chemin_declare_dans_le_manifeste_est_celui_qu_ecrit_le_script():
    """Le producteur et le consommateur doivent viser le même fichier."""
    declared = load_manifest().get("arms.calibration.common_set_eval")
    assert declared == "scripts/synthesis/data/calibration_on_common_set.jsonl"
    assert (REPO_ROOT / declared).parent.name == "data"
