"""Tests de la politique de choix modal PROGEDO
(`scripts/progedo_logit/fit_mode_choice_policy.py`).

Ce qui est verrouillé ici, ce sont les invariants dont la violation ne lève aucune
exception mais produit un modèle silencieusement faux :

- aucune variable `diagnostic_only` n'entre dans le modèle (fuite du ticket 005 §1) ;
- l'ordre des variables et des classes de l'artefact sérialisé est **exactement** celui
  de `feature_spec.json` — un décalage d'une colonne donne des probabilités plausibles
  et fausses ;
- l'encodage catégoriel publié est celui du spec, et une modalité inconnue devient
  manquante plutôt que d'être repliée sur un code voisin ;
- l'artefact se recharge et prédit une distribution sur les 4 classes **sans relire le
  parquet** — c'est le contrat que consomme l'action A8.

Aucun ré-entraînement du vrai modèle : les tests qui en ont besoin le sautent
proprement s'il est absent (il est produit par `make policy`), et un modèle jouet de
quelques arbres couvre le reste.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from scripts.progedo_logit.fit_mode_choice_policy import (
    POLICY_FORMAT,
    POLICY_FORMAT_VERSION,
    build_policy,
    categorical_encoding,
    categorical_indices,
    check_spec,
    encode_features,
    feature_names,
    find_project_root,
    train_booster,
)

ROOT = find_project_root()
HERE = ROOT / "scripts" / "progedo_logit"
SPEC_PATH = HERE / "feature_spec.json"
POLICY_PATH = HERE / "mode_choice_policy.json"


@pytest.fixture(scope="module")
def spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def policy() -> dict:
    if not POLICY_PATH.exists():
        pytest.skip(f"Modèle non entraîné ({POLICY_PATH.name}) — `make policy`")
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def synthetic_rows(spec: dict, n: int = 8) -> pd.DataFrame:
    """Lignes fabriquées depuis le seul spec — jamais depuis le parquet.

    C'est le point du test : si prédire exigeait de relire les micro-données, le
    contrat d'artefact autoportant ne tiendrait pas.
    """
    rng = np.random.default_rng(0)
    data = {}
    for feature in spec["features"]:
        name, kind = feature["name"], feature["kind"]
        if kind == "categorical":
            data[name] = list(rng.choice(feature["categories"], size=n))
        elif kind == "bool":
            data[name] = list(rng.random(n) > 0.5)
        else:
            data[name] = list(rng.uniform(0, 20, size=n))
    return pd.DataFrame(data)


# ── Fuite : les variables de diagnostic ──────────────────────────────────────

class TestDiagnosticOnly:

    def test_spec_ne_declare_aucune_variable_contaminee_en_feature(self, spec):
        """distance_km / crow_km / duration_min sont hors du modèle, par construction."""
        assert set(spec["diagnostic_only"]) == {"distance_km", "crow_km", "duration_min"}
        assert not set(spec["diagnostic_only"]) & set(feature_names(spec))

    def test_check_spec_refuse_une_variable_contaminee(self, spec):
        polluted = dict(spec)
        polluted["features"] = spec["features"] + [
            {"name": "distance_km", "kind": "numeric", "source": "context"}]
        df = synthetic_rows(spec)
        df["distance_km"] = 1.0
        df["mode"] = "car"
        df["sample_weight"] = 1.0
        df["split"] = "train"
        df["hh_id"] = "x"
        with pytest.raises(SystemExit, match="diagnostic_only"):
            check_spec(polluted, df)

    @pytest.mark.parametrize("banned", ["distance_km", "crow_km", "duration_min"])
    def test_modele_serialise_ignore_les_variables_contaminees(self, policy, banned):
        assert banned not in [f["name"] for f in policy["features"]]


# ── Encodage ─────────────────────────────────────────────────────────────────

class TestEncodage:

    def test_ordre_des_colonnes_impose_par_le_spec(self, spec):
        df = synthetic_rows(spec)
        # Colonnes délibérément mélangées : c'est le spec qui doit trancher.
        shuffled = df[list(reversed(df.columns))]
        assert list(encode_features(shuffled, spec).columns) == feature_names(spec)

    def test_categorielle_encodee_selon_le_spec(self, spec):
        cat = next(f for f in spec["features"] if f["kind"] == "categorical")
        df = synthetic_rows(spec)
        df[cat["name"]] = cat["categories"][-1]
        encoded = encode_features(df, spec)[cat["name"]]
        assert (encoded == len(cat["categories"]) - 1).all()

    def test_modalite_inconnue_devient_manquante(self, spec):
        """Jamais de code de repli : « inattendu » n'est pas « le plus fréquent »."""
        cat = next(f for f in spec["features"] if f["kind"] == "categorical")
        df = synthetic_rows(spec)
        df[cat["name"]] = "modalité qui n'existe pas"
        assert encode_features(df, spec)[cat["name"]].isna().all()

    def test_booleen_en_zero_un_et_manquant_preserve(self, spec):
        bools = [f["name"] for f in spec["features"] if f["kind"] == "bool"]
        df = synthetic_rows(spec)
        # dtype object : une colonne bool native n'accepte pas la valeur manquante,
        # alors que le jeu commun la produira (trait absent d'un persona).
        df[bools[0]] = pd.Series([True, False] * (len(df) // 2), dtype="object")
        df.loc[0, bools[0]] = None
        encoded = encode_features(df, spec)[bools[0]]
        assert pd.isna(encoded.iloc[0])
        assert set(encoded.dropna().unique()) <= {0.0, 1.0}

    def test_indices_categoriels_pointent_les_bonnes_colonnes(self, spec):
        names = feature_names(spec)
        expected = {f["name"] for f in spec["features"] if f["kind"] == "categorical"}
        assert {names[i] for i in categorical_indices(spec)} == expected


# ── Contrat de l'artefact sérialisé ──────────────────────────────────────────

class TestArtefact:

    def test_format_et_versions_declares(self, policy, spec):
        assert policy["format"] == POLICY_FORMAT
        assert policy["format_version"] == POLICY_FORMAT_VERSION
        # Le runtime refuse un modèle entraîné sous un autre contrat de features.
        assert policy["spec_version"] == spec["spec_version"]

    def test_ordre_des_variables_identique_au_spec(self, policy, spec):
        assert [f["name"] for f in policy["features"]] == feature_names(spec)
        assert [f["kind"] for f in policy["features"]] == \
               [f["kind"] for f in spec["features"]]

    def test_ordre_des_classes_identique_au_spec(self, policy, spec):
        assert policy["target"]["classes"] == spec["target"]["classes"]

    def test_table_d_encodage_complete_et_conforme(self, policy, spec):
        assert policy["encoding"]["categorical"] == categorical_encoding(spec)
        for feature in policy["features"]:
            if feature["kind"] == "categorical":
                assert feature["categories"] == \
                       [f for f in spec["features"] if f["name"] == feature["name"]][0]["categories"]

    def test_booster_embarque_sous_les_deux_formes(self, policy):
        """dump_model pour l'évaluateur pur Python (E9), texte pour un rechargement exact."""
        assert policy["booster"]["dump_model"]["num_class"] == \
               len(policy["target"]["classes"])
        assert policy["booster"]["model_text"].startswith("tree")

    def test_reference_geographique_recopiee(self, policy, spec):
        """Sans elle, impossible de vérifier que od_km est calculé au même centre."""
        assert policy["geo_reference"] == spec["geo_reference"]


class TestPredictionSansParquet:

    def test_rechargement_et_probabilites_sommant_a_un(self, policy, spec):
        lgb = pytest.importorskip("lightgbm")
        booster = lgb.Booster(model_str=policy["booster"]["model_text"])
        assert booster.feature_name() == [f["name"] for f in policy["features"]]

        rows = synthetic_rows(spec, n=32)
        proba = booster.predict(encode_features(rows, spec))
        assert proba.shape == (32, len(policy["target"]["classes"]))
        assert np.allclose(proba.sum(axis=1), 1.0)
        assert (proba >= 0).all()

    def test_valeurs_manquantes_acceptees(self, policy, spec):
        """La densité est absente pour 81 zones sur 785 : prédire doit rester possible."""
        lgb = pytest.importorskip("lightgbm")
        booster = lgb.Booster(model_str=policy["booster"]["model_text"])
        rows = synthetic_rows(spec, n=4)
        rows["density_orig"] = np.nan
        rows["density_dest"] = np.nan
        proba = booster.predict(encode_features(rows, spec))
        assert np.allclose(proba.sum(axis=1), 1.0)


# ── Modèle jouet : le contrat tient sans l'artefact réel ─────────────────────

class TestModeleJouet:
    """Même chaîne, sur quelques arbres et des données synthétiques.

    Couvre `train_booster` / `build_policy` même quand le vrai modèle n'a pas été
    entraîné, sans jamais payer un entraînement complet.
    """

    @pytest.fixture(scope="class")
    def jouet(self, spec):
        pytest.importorskip("lightgbm")
        rows = synthetic_rows(spec, n=200)
        X = encode_features(rows, spec)
        rng = np.random.default_rng(1)
        y = rng.integers(0, len(spec["target"]["classes"]), size=len(rows))
        w = np.ones(len(rows))
        is_valid = np.zeros(len(rows), dtype=bool)
        is_valid[150:] = True
        params = {"objective": "multiclass", "metric": "multi_logloss",
                  "num_leaves": 4, "min_data_in_leaf": 5, "verbosity": -1,
                  "num_threads": 1, "deterministic": True, "force_row_wise": True,
                  "seed": 0}
        booster, training = train_booster(X, y, w, is_valid, spec, params)
        return booster, training

    def test_policy_construite_est_serialisable_et_relisible(self, jouet, spec, tmp_path):
        booster, training = jouet
        policy = build_policy(booster, spec, SPEC_PATH, HERE / "dataset.parquet",
                              training, metrics={})
        path = tmp_path / "policy.json"
        path.write_text(json.dumps(policy, ensure_ascii=False), encoding="utf-8")

        reloaded = json.loads(path.read_text(encoding="utf-8"))
        assert [f["name"] for f in reloaded["features"]] == feature_names(spec)
        assert reloaded["target"]["classes"] == spec["target"]["classes"]

        lgb = pytest.importorskip("lightgbm")
        proba = lgb.Booster(model_str=reloaded["booster"]["model_text"]).predict(
            encode_features(synthetic_rows(spec, n=5), spec))
        assert proba.shape == (5, len(spec["target"]["classes"]))
        assert np.allclose(proba.sum(axis=1), 1.0)


# ── Garde-fous de check_spec ─────────────────────────────────────────────────

class TestCheckSpec:

    @pytest.fixture
    def frame(self, spec):
        df = synthetic_rows(spec, n=4)
        df["mode"] = "car"
        df["sample_weight"] = 1.0
        df["split"] = "train"
        df["hh_id"] = ["a", "a", "b", "b"]
        return df

    def test_jeu_conforme_accepte(self, spec, frame):
        check_spec(spec, frame)  # ne lève pas

    def test_colonne_manquante_refusee(self, spec, frame):
        with pytest.raises(SystemExit, match="Colonnes absentes"):
            check_spec(spec, frame.drop(columns=["od_km"]))

    def test_ponderation_manquante_refusee(self, spec, frame):
        with pytest.raises(SystemExit, match="sample_weight"):
            check_spec(spec, frame.drop(columns=["sample_weight"]))

    def test_modalite_hors_spec_refusee(self, spec, frame):
        frame["purpose"] = "téléportation"
        with pytest.raises(SystemExit, match="Modalités hors spec"):
            check_spec(spec, frame)

    def test_classe_cible_hors_spec_refusee(self, spec, frame):
        frame["mode"] = "hélicoptère"
        with pytest.raises(SystemExit, match="cible hors du spec"):
            check_spec(spec, frame)
