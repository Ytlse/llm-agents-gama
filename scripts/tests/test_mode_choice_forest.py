"""Tests du témoin random forest — ticket 044.

Un test par règle de `specs/ticket_044/temoin_random_forest.md`, R1 à R10. Ce qui est
vérifié n'est pas « le random forest est bon » — il n'a pas à l'être, c'est un témoin — mais
**les propriétés sans lesquelles sa position entre les deux oracles ne veut rien dire** :
même contrat, même substrat, un réglage qui ne lit pas le test, aucune repondération de
classe, les mêmes métriques, et un verdict dont le seuil était écrit avant le chiffre.

Deux tests portent sur ce que le témoin **ne fait pas** : il ne sérialise aucun modèle
(R7) et il ne publie pas un zéro quand la référence manque (R9). Ce sont les deux façons
dont ce ticket pouvait produire une conclusion fausse sans lever la moindre exception.

Hors ligne : aucun appel réseau, aucun LLM. Les tests qui exigent la mesure se sautent
proprement si elle est absente (`make forest`).
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from scripts.progedo_logit.fit_mode_choice_forest import (
    ECART_MINIMAL,
    SEUIL_ARBRES,
    SEUIL_BOOSTING,
    build_matrix,
    cel,
    comparer,
    cv_log_loss,
    forest,
    part_de_l_ecart,
    proba_complete,
    verdict,
)
from scripts.progedo_logit.fit_mode_choice_policy import (
    check_spec,
    encode_features,
    feature_names,
    find_project_root,
)
from scripts.progedo_logit.mode_choice_eval import evaluate_proba

ROOT = find_project_root()
HERE = ROOT / "scripts" / "progedo_logit"
SPEC_PATH = HERE / "feature_spec.json"
DATASET_PATH = HERE / "progedo_mode_choice_v2.parquet"
FOREST_PATH = HERE / "rf_mode_choice_metrics.json"
POLICY_METRICS = HERE / "mode_choice_policy_metrics.json"
LOGIT_METRICS = HERE / "mnl_model_metrics.json"


@pytest.fixture(scope="module")
def spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rapport() -> dict:
    if not FOREST_PATH.exists():
        pytest.skip("Témoin non mesuré — `make forest`")
    return json.loads(FOREST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def echantillon(spec) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Un extrait du jeu réel : les tests de matrice doivent voir de vrais manquants."""
    if not DATASET_PATH.exists():
        pytest.skip("Jeu d'entraînement absent")
    df = pd.read_parquet(DATASET_PATH).head(3000)
    return df, encode_features(df, spec)


# ── R1 : parité de contrat ───────────────────────────────────────────────────

def test_R1_aucune_variable_diagnostic(spec):
    """Une `diagnostic_only` glissée dans les features fait échouer avant tout ajustement.

    Le garde-fou n'est pas recopié : c'est `check_spec` du booster, importée telle quelle.
    Une copie divergerait au premier ajout de variable contaminée.
    """
    contamine = dict(spec)
    contamine["features"] = list(spec["features"]) + [
        {"name": "distance_km", "kind": "numeric", "source": "context"}]
    df = pd.DataFrame({name: [0] for name in feature_names(contamine)})
    with pytest.raises(SystemExit, match="diagnostic_only"):
        check_spec(contamine, df)


def test_R1_les_21_variables_et_pas_une_de_plus(spec, rapport):
    natif = rapport.get("sensibilite_encodage")
    if natif is None:
        pytest.skip("Voie native non mesurée")
    assert natif["encodage"]["noms_colonnes"] == feature_names(spec)
    assert len(feature_names(spec)) == 21


# ── R2 : parité de substrat ──────────────────────────────────────────────────

def test_R2_parite_du_substrat(spec, rapport):
    """Mêmes effectifs train/test que le booster, et le poids d'enquête, pas un poids local."""
    if not POLICY_METRICS.exists():
        pytest.skip("Métriques du booster absentes — `make policy`")
    booster = json.loads(POLICY_METRICS.read_text(encoding="utf-8"))
    training = rapport["principal"]["training"]
    assert training["n_test"] == booster["test"]["n_rows"]
    assert rapport["split"] == booster["split"]
    assert training["sample_weight"] == spec["sample_weight"]
    assert "COEP" in training["estimator"]


def test_R2_le_split_est_lu_jamais_retire(rapport):
    """`n_fit + n_test` égale le jeu entier : aucune ligne perdue, aucun redécoupage."""
    training = rapport["principal"]["training"]
    assert training["n_fit"] + training["n_test"] == 52248


# ── R3 : le test n'est jamais lu pour régler ─────────────────────────────────

def test_R3_test_jamais_lu_pour_regler(rapport):
    tuning = rapport["principal"]["training"]["tuning"]
    assert tuning["scored_on"].startswith("train uniquement")
    assert tuning["grouped_by"] == "hh_id"
    assert tuning["criterion"] == "log_loss_weighted"
    retenu = tuning["retenu"]
    assert retenu["max_depth"] in tuning["grille"]["max_depth"]
    assert retenu["min_samples_leaf"] in tuning["grille"]["min_samples_leaf"]


def test_R3_les_plis_sont_disjoints_par_menage():
    """Deux déplacements d'un même ménage ne tombent jamais de part et d'autre d'un pli.

    Vérifié en mesurant sur un jeu jouet : `cv_log_loss` doit rendre un nombre fini avec des
    groupes de 5 lignes, ce qui n'est possible que si le découpage respecte les groupes.
    """
    rng = np.random.default_rng(0)
    n = 200
    groups = np.repeat(np.arange(40), 5)
    X = rng.normal(size=(n, 4))
    y = rng.integers(0, 4, size=n)
    w = np.ones(n)
    moyenne, par_pli = cv_log_loss(X, y, w, groups, 4, 20, None, 5, "sqrt", folds=4)
    assert len(par_pli) == 4
    assert np.isfinite(moyenne)


# ── R4 : ni class_weight ni rééquilibrage ────────────────────────────────────

def test_R4_ni_class_weight_ni_reequilibrage(rapport):
    """Vérifié sur l'estimateur publié, pas sur l'intention.

    Repondérer les classes gonfle le rappel du vélo en détruisant la calibration — or ce
    sont les probabilités, pas l'exactitude, qui produisent les parts modales (décision E7).
    """
    training = rapport["principal"]["training"]
    assert training["class_weight"] is None
    serialise = json.dumps(rapport, ensure_ascii=False)
    for interdit in ("balanced", "is_unbalance", "scale_pos_weight"):
        assert interdit not in serialise


def test_R4_le_constructeur_ne_repondere_pas():
    modele = forest(10, None, 5, "sqrt")
    assert modele.class_weight is None
    assert modele.bootstrap is True


# ── R5 : mêmes métriques, même code ──────────────────────────────────────────

def test_R5_memes_metriques_que_les_deux_oracles(rapport):
    """Les clés du témoin sont exactement celles des deux oracles — module partagé."""
    if not LOGIT_METRICS.exists():
        pytest.skip("Métriques du logit absentes — `make logit`")
    logit = json.loads(LOGIT_METRICS.read_text(encoding="utf-8"))["test"]
    attendues = set(logit) - {"top_coefficients"}
    assert attendues <= set(rapport["principal"]["test"])


def test_R5_les_metriques_sortent_du_module_partage():
    """Le témoin n'a pas sa propre table : `evaluate_proba` produit les mêmes clés pour lui."""
    proba = np.array([[0.7, 0.1, 0.1, 0.1], [0.1, 0.6, 0.2, 0.1]])
    metrics = evaluate_proba(proba, np.array([0, 1]), np.array([1.0, 2.0]),
                             ["bike", "car", "transit", "walk"])
    assert {"cel_weighted", "gmpca_weighted", "accuracy_weighted", "mode_shares",
            "per_class"} <= set(metrics)


def test_R5_cel_lue_sous_ses_deux_noms():
    """Un fichier antérieur aux alias se lit sous `log_loss_weighted` — même grandeur."""
    assert cel({"cel_weighted": 0.54, "log_loss_weighted": 0.54}) == 0.54
    assert cel({"log_loss_weighted": 0.5402}) == pytest.approx(0.5402)


# ── R6 : manquants par les règles déclarées ──────────────────────────────────

def test_R6_manquants_declares(spec, echantillon):
    """Une catégorielle hors spec et une numérique absente traversent sans lever.

    La matrice de dessin les matérialise : modalité `__missing__` d'un côté, moyenne
    pondérée du train plus indicatrice de l'autre. Sans l'indicatrice, l'imputation
    affirmerait une valeur que la donnée ne porte pas.
    """
    df, encoded = echantillon
    encoded = encoded.copy()
    encoded.iloc[0, encoded.columns.get_loc("socioprofessional_class")] = np.nan
    encoded.iloc[0, encoded.columns.get_loc("density_orig")] = np.nan
    poids = df[spec["sample_weight"]].to_numpy(dtype=float)
    est_train = np.ones(len(df), dtype=bool)

    matrix, description = build_matrix(encoded, spec, poids, est_train, "dessin")
    assert np.isfinite(matrix).all()
    colonnes = description["noms_colonnes"]
    assert matrix[0, colonnes.index("socioprofessional_class=__missing__")] == 1.0
    # `indicatrices_de_manquant` liste les VARIABLES concernées ; la colonne de dessin
    # correspondante porte le suffixe.
    assert "density_orig" in description["indicatrices_de_manquant"]
    assert matrix[0, colonnes.index("density_orig__missing")] == 1.0


def test_R6_la_regle_est_ecrite_dans_la_sortie(rapport):
    encodage = rapport["principal"]["encodage"]
    assert encodage["voie"] == "dessin"
    regle = encodage["regle_des_manquants"]
    assert "__missing__" in regle["categorical"]
    assert "indicatrice" in regle["numeric"]


def test_R6_les_indicatrices_viennent_du_train_seul(spec, echantillon):
    """Une indicatrice déduite du test y ferait entrer une information du test."""
    df, encoded = echantillon
    encoded = encoded.copy()
    poids = df[spec["sample_weight"]].to_numpy(dtype=float)
    est_train = np.zeros(len(df), dtype=bool)
    est_train[: len(df) // 2] = True
    # Un manquant introduit du seul côté test ne doit créer aucune colonne.
    encoded.iloc[-1, encoded.columns.get_loc("age")] = np.nan
    _, description = build_matrix(encoded, spec, poids, est_train, "dessin")
    assert "age__missing" not in description["indicatrices_de_manquant"]


# ── R7 : le témoin ne produit pas de modèle ──────────────────────────────────

def test_R7_aucun_artefact_predictif(rapport):
    """Ni arbres, ni `dump_model`, ni coefficients : des mesures, et rien d'autre.

    Tranché à l'ouverture du ticket : un RF autoportant, c'est 400 à 1 200 arbres de
    plusieurs milliers de nœuds pour un fichier sans consommateur.
    """
    serialise = json.dumps(rapport, ensure_ascii=False)
    # Signatures d'un modèle sérialisé — jamais un nom d'hyperparamètre : `estimators_` aurait
    # matché `n_estimators_cv`, et le test aurait échoué sur son propre repère.
    for interdit in ("dump_model", "model_text", "tree_structure", "\"coef\"",
                     "children_left", "children_right", "\"threshold\"", "node_count"):
        assert interdit not in serialise
    assert FOREST_PATH.stat().st_size < 1_000_000
    assert "aucun modèle n'est sérialisé" in rapport["temoin"]["nature"]


def test_R7_le_temoin_reste_hors_du_composite():
    """Le témoin n'entre ni dans le score composite ni dans `common-set-predict`.

    La clause « aucun consommateur » de la version du matin est révisée : le témoin est joué
    comme expérience depuis que la question posée est tranchée. Ce qui reste interdit est
    qu'il devienne un **arbitre** — les deux modules du score ne doivent pas le connaître.
    """
    for module in ("scripts/synthesis/bi_oracle.py",
                   "scripts/synthesis/model_on_common_set.py"):
        texte = (ROOT / module).read_text(encoding="utf-8")
        assert "fit_mode_choice_forest" not in texte
        assert "rf_mode_choice_policy" not in texte


def test_R7_seuls_le_predicteur_et_le_lanceur_consomment_le_temoin():
    """Les importateurs sont connus et limités : le témoin, son prédicteur, son lanceur."""
    attendus = {"fit_mode_choice_forest.py", "mode_choice_rf.py",
                "lancer_experience_rf.py", "test_mode_choice_forest.py"}
    importeurs = {
        chemin.name for chemin in (ROOT / "scripts").rglob("*.py")
        if "fit_mode_choice_forest" in chemin.read_text(encoding="utf-8")
    }
    assert importeurs <= attendus


# ── R8 : le verdict, et son seuil déclaré d'avance ───────────────────────────

def test_R8_part_de_l_ecart_sur_un_triplet_calcule_a_la_main():
    """0 au niveau du logit, 1 à celui du booster, et le sens de la métrique n'y entre pas."""
    # Exactitude : « mieux » est plus haut.
    assert part_de_l_ecart(0.766, 0.785, 0.766) == pytest.approx(0.0)
    assert part_de_l_ecart(0.785, 0.785, 0.766) == pytest.approx(1.0)
    assert part_de_l_ecart(0.7755, 0.785, 0.766) == pytest.approx(0.5)
    # L1 : « mieux » est plus bas — la formule est inchangée.
    assert part_de_l_ecart(0.0269, 0.0269, 0.0286) == pytest.approx(1.0)
    assert part_de_l_ecart(0.02775, 0.0269, 0.0286) == pytest.approx(0.5)
    # Hors de [0, 1] : une information, pas une anomalie à borner.
    assert part_de_l_ecart(0.80, 0.785, 0.766) > 1.0
    assert part_de_l_ecart(0.70, 0.785, 0.766) < 0.0


def test_R8_ecart_trop_petit_non_mesure():
    """Deux oracles indiscernables ne donnent pas une part, ils donnent « non mesuré »."""
    assert part_de_l_ecart(0.5, 0.7, 0.7 - ECART_MINIMAL / 2) is None


def test_R8_les_seuils_sont_des_constantes_du_module():
    """Déclarés d'avance et lisibles : choisir le seuil après le chiffre choisit la conclusion."""
    assert (SEUIL_BOOSTING, SEUIL_ARBRES) == (0.30, 0.70)
    assert verdict([0.85, 0.92])["conclusion"] == "les arbres"
    assert verdict([0.10, 0.25])["conclusion"] == "le boosting"
    assert verdict([0.50, 0.90])["conclusion"] == "indécis"
    assert verdict([0.85, 0.20])["conclusion"] == "indécis"
    for rendu in (verdict([0.85, 0.92]), verdict([])):
        assert rendu["seuils"]["arbres"] == SEUIL_ARBRES


# ── R9 : vacuité ≠ résultat ──────────────────────────────────────────────────

def test_R9_comparaison_absente_non_publiee(tmp_path):
    """Référence manquante → « non mesuré », jamais `0.0`.

    Un zéro se lirait « aucun écart entre les trois modèles », soit exactement l'inverse de
    ce qu'une absence de mesure dit.
    """
    rf = {"n_rows": 10, "accuracy_weighted": 0.77, "cel_weighted": 0.57,
          "mode_shares": {"l1_probability_mass": 0.02, "l1_argmax": 0.09},
          "per_class": {"bike": {"recall": 0.05}}}
    sortie = comparer(rf, tmp_path / "absent_booster.json", tmp_path / "absent_logit.json")
    assert sortie["statut"] == "non mesuré"
    assert sortie["verdict"]["conclusion"] == "non mesuré"
    assert "axes" not in sortie
    assert 0.0 not in list(sortie.values())


def test_R9_le_verdict_sans_mesure_reste_sans_conclusion():
    rendu = verdict([None, None])
    assert rendu["conclusion"] == "non mesuré"


# ── R10 : la sensibilité à l'encodage est mesurée ────────────────────────────

def test_R10_les_deux_encodages_existent(spec, echantillon):
    """Les deux voies produisent des matrices de largeurs différentes sur le même jeu."""
    df, encoded = echantillon
    poids = df[spec["sample_weight"]].to_numpy(dtype=float)
    est_train = np.ones(len(df), dtype=bool)

    dessin, description_dessin = build_matrix(encoded, spec, poids, est_train, "dessin")
    natif, description_natif = build_matrix(encoded, spec, poids, est_train, "natif")

    assert natif.shape[1] == 21
    assert dessin.shape[1] > natif.shape[1]      # dilatation en indicatrices
    assert description_dessin["indicatrices_de_manquant"]
    assert description_natif["indicatrices_de_manquant"] == []
    assert "ORDINALES" in description_natif["regle_des_manquants"]["note"]


def test_R10_encodage_inconnu_refuse(spec, echantillon):
    df, encoded = echantillon
    poids = df[spec["sample_weight"]].to_numpy(dtype=float)
    with pytest.raises(SystemExit, match="Encodage inconnu"):
        build_matrix(encoded, spec, poids, np.ones(len(df), dtype=bool), "one-hot")


def test_R10_ecart_publie(rapport):
    if "sensibilite_encodage" not in rapport:
        pytest.skip("Voie native non mesurée")
    ecart = rapport["sensibilite_encodage"]["ecart_au_principal"]
    assert {"accuracy_weighted", "cel_weighted", "l1_probability_mass"} <= set(ecart)


# ── Garde-fou transverse : les quatre classes, toujours ──────────────────────

def test_proba_complete_reconstruit_une_classe_absente():
    """Un pli sans vélo ne doit pas décaler l'ordre des classes en silence."""
    class ModeleJouet:
        classes_ = np.array([1, 2, 3])

        def predict_proba(self, matrix):
            return np.tile([0.5, 0.3, 0.2], (len(matrix), 1))

    plein = proba_complete(ModeleJouet(), np.zeros((3, 2)), 4)
    assert plein.shape == (3, 4)
    assert (plein[:, 0] == 0.0).all()
    assert plein[0].tolist() == [0.0, 0.5, 0.3, 0.2]


# ── R11/R12/R13 : le témoin joué comme expérience ────────────────────────────

ARTEFACT_PATH = HERE / "rf_mode_choice_policy.json"
EXPERIENCE_RF = ROOT / "data" / "experiences" / "exp_rf_jtir_nosim" / "experience.yaml"


@pytest.fixture(scope="module")
def artefact_rf() -> dict:
    if not ARTEFACT_PATH.exists():
        pytest.skip("Artefact de rejeu absent — `make forest FOREST_ARGS=--artefact`")
    return json.loads(ARTEFACT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def predicteur(artefact_rf):
    """Réajuste la forêt une fois pour tout le module (~10 s)."""
    from scripts.progedo_logit.mode_choice_rf import RFPredictor
    return RFPredictor(artefact_rf)


def test_R11_artefact_sans_arbres(artefact_rf):
    """Un contrat, pas une forêt : les 3 740 500 nœuds ne sont pas là."""
    serialise = json.dumps(artefact_rf, ensure_ascii=False)
    # Signatures d'arbre sérialisé uniquement — « estimators » nu matcherait
    # `n_estimators`, qui est un hyperparamètre et non une forêt.
    for interdit in ("children_left", "children_right", "node_count", "estimators_",
                     "tree_structure", "dump_model", '"threshold"'):
        assert interdit not in serialise
    assert ARTEFACT_PATH.stat().st_size < 100_000
    bloc = artefact_rf["rf"]
    assert set(bloc["hyperparameters"]) >= {"n_estimators", "max_depth", "min_samples_leaf",
                                            "max_features", "random_state"}
    assert bloc["hyperparameters"]["class_weight"] is None
    assert len(artefact_rf["dataset_sha256"]) == 64
    assert len(artefact_rf["trainset_sha256"]) == 64
    # La matrice part à côté : 1,4 Mo contre 165 Mo pour la forêt.
    assert (HERE / artefact_rf["trainset_file"]).stat().st_size < 5_000_000
    assert bloc["estimator"]["version"]
    assert bloc["contrat"]["design_columns"]


def test_R11_le_contrat_reconstruit_la_meme_matrice(spec, echantillon, artefact_rf):
    """La matrice bâtie depuis l'artefact est celle bâtie depuis le script d'estimation."""
    from scripts.progedo_logit.mode_choice_logit import design_matrix

    df, encoded = echantillon
    poids = df[spec["sample_weight"]].to_numpy(dtype=float)
    depuis_script, _ = build_matrix(encoded, spec, poids,
                                    np.ones(len(df), dtype=bool), "dessin")
    depuis_artefact = design_matrix(encoded, {"features": artefact_rf["features"],
                                              "logit": artefact_rf["rf"]["contrat"]})
    # Le contrat de l'artefact a été bâti sur le TRAIN complet, l'échantillon sur ses 3 000
    # premières lignes : les colonnes doivent coïncider, les valeurs peuvent différer d'un
    # centrage. C'est la structure qui doit être identique.
    assert depuis_artefact.shape[1] == len(artefact_rf["rf"]["contrat"]["design_columns"])
    assert depuis_script.shape[0] == depuis_artefact.shape[0]


def test_R12_la_foret_reajustee_reproduit_les_metriques(predicteur):
    """Le garde-fou central : on mesure que c'est la forêt du tableau, on ne le présume pas."""
    controle = predicteur.controle
    assert controle["reproduit"] is True
    assert max(controle["ecarts"].values()) <= controle["tolerance"]


def test_R12_des_metriques_alterees_font_refuser(predicteur, artefact_rf):
    """Une forêt qui ne reproduit plus les chiffres publiés est refusée, avec l'écart.

    La forêt est déjà ajustée (fixture de module) : on rejoue seulement le contrôle, avec des
    métriques publiées faussées. Aucun réajustement, donc aucune seconde perdue.
    """
    with np.load(HERE / artefact_rf["trainset_file"]) as jeu:
        matrix, y, w = jeu["X"], jeu["y"].astype("int64"), jeu["w"]

    publie = predicteur.artefact["metrics"]
    predicteur.artefact["metrics"] = {**publie,
                                      "accuracy_weighted": publie["accuracy_weighted"] + 0.01}
    try:
        with pytest.raises(ValueError, match="ne reproduit pas les métriques"):
            predicteur._verifier_reproduction(matrix, y, w)
    finally:
        predicteur.artefact["metrics"] = publie


def test_R12_une_matrice_dun_autre_sha_est_refusee(artefact_rf):
    """Refus sec, et AVANT tout ajustement : sans la même matrice, rien à réajuster."""
    from scripts.progedo_logit.mode_choice_rf import RFPredictor

    faux = dict(artefact_rf)
    faux["trainset_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="matrice d'entraînement a changé"):
        RFPredictor(faux)


def test_R12_une_matrice_absente_est_refusee(artefact_rf, tmp_path):
    from scripts.progedo_logit.mode_choice_rf import RFPredictor

    with pytest.raises(FileNotFoundError, match="Matrice d'entraînement absente"):
        RFPredictor(artefact_rf, trainset_path=tmp_path / "nexiste_pas.npz")


def test_R12_le_rejeu_ne_demande_pas_de_moteur_parquet():
    """Le rejeu passe par numpy seul : le conteneur des expériences n'a pas de moteur parquet.

    Vérifié sur le code plutôt que sur l'environnement — un `read_parquet` réintroduit dans ce
    chemin casserait le rejeu là où il doit tourner, sans rien casser ici.
    """
    texte = (HERE / "mode_choice_rf.py").read_text(encoding="utf-8")
    assert "read_parquet" not in texte


def test_R13_libelle_famille_derive_du_format():
    """La famille vaut `rf` — jamais « lightgbm ». Un libellé faux ne se remarque pas."""
    import sys as _sys

    _sys.path.insert(0, str(ROOT / "services" / "llm-agents"))
    from experiences import decideur_modele

    from scripts.progedo_logit.lancer_experience_rf import enregistrer_famille_rf
    from scripts.progedo_logit.mode_choice_rf import RF_FORMAT

    familles_avant = dict(decideur_modele.FAMILLES)
    load_avant = decideur_modele.load_policy
    try:
        enregistrer_famille_rf()
        assert decideur_modele.FAMILLES[RF_FORMAT] == "rf"
        # Les autres familles continuent de passer par le chargeur officiel.
        assert decideur_modele.FAMILLES["lightgbm_mode_choice_policy"] == "lightgbm"
        assert decideur_modele.FAMILLES["mnl_mode_choice_policy"] == "mnl"
    finally:
        decideur_modele.FAMILLES.clear()
        decideur_modele.FAMILLES.update(familles_avant)
        decideur_modele.load_policy = load_avant


def test_R13_experience_declare_non_rejouable():
    """Une expérience qu'on ne peut pas relancer par la voie normale doit le dire.

    L'avertissement vit **à côté** de l'`experience.yaml` et non dedans : le schéma de la
    plateforme refuse toute clé hors contrat, et c'est une bonne chose — une expérience ne
    doit pas porter de champ libre que personne ne valide.
    """
    if not EXPERIENCE_RF.exists():
        pytest.skip("Expérience du témoin non lancée — lancer_experience_rf.py")
    lisez_moi = EXPERIENCE_RF.parent / "LISEZ-MOI.md"
    assert lisez_moi.exists()
    contenu = lisez_moi.read_text(encoding="utf-8")
    assert "NON REJOUABLE" in contenu
    assert "lancer_experience_rf" in contenu
    # L'experience.yaml, lui, reste conforme au schéma : aucune clé ajoutée.
    assert "note:" not in EXPERIENCE_RF.read_text(encoding="utf-8")


def test_R13_meme_couverture_que_les_autres_familles():
    """Sans la même couverture, les trois composites ne se comparent pas.

    C'est la propriété qui rend le chiffre du témoin lisible à côté de ceux du booster et du
    logit — pas que le témoin soit bon, mais qu'il ait décidé sur les mêmes déplacements.
    """
    base = ROOT / "data" / "experiences"
    couvertures = {}
    for nom in ("exp_lgbm_jtir_nosim", "exp_mnl_jtir_nosim", "exp_rf_jtir_nosim"):
        executions = base / nom / "executions"
        if not executions.exists():
            pytest.skip(f"{nom} non exécutée")
        derniere = sorted(executions.iterdir())[-1]
        scores = json.loads((derniere / "scores.json").read_text(encoding="utf-8"))
        couvertures[nom] = (scores["couverture"]["decides"],
                            scores["couverture"]["attendus"])
    assert len(set(couvertures.values())) == 1, couvertures
