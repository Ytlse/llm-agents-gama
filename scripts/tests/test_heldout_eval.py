"""Tests de l'évaluation sur jeu de retenue et de son témoin d'effectif (action A4).

Trois moitiés indépendantes, testées séparément :

- **la sélection des nœuds** (`heldout_eval.select_nodes`) : quels prompts d'une
  lignée sont mesurés, et sous quels rôles. Une lignée sans extrémités à opposer
  doit lever, pas produire une mesure dégradée dont personne ne verra qu'elle
  n'oppose rien ;
- **la description des jeux gelés** (`heldout_eval.dataset_profile`) : c'est elle
  qui établit *sur pièces* si le découpage est par personne ou par déplacement.
  Toute la portée du mot « généralisation » en dépend, et une page qui se
  tromperait là-dessus publierait l'affirmation forte à la place de la faible ;
- **le témoin d'effectif et sa consommation** (`build.resample_composite`,
  `build.resample_gain`, `build.build_generalization`, `render`) : sans lui,
  l'écart train → test se lit comme du surapprentissage alors qu'il vient en
  bonne partie du nombre de personnes observées.

Hors ligne : aucun appel LLM, aucune clé d'API, aucun store réel. Les décisions
sont fabriquées à la main.
"""

from __future__ import annotations

import json

import pytest

from scripts.synthesis import build, frames, heldout_eval, render
from scripts.synthesis.heldout_eval import (
    dataset_profile,
    select_nodes,
    split_rule,
)
from scripts.synthesis.sources import import_calibration, load_manifest

CALIBRATION, _ENGINE_ERROR = import_calibration()
needs_engine = pytest.mark.skipif(
    CALIBRATION is None, reason=f"Moteur de calibration indisponible : {_ENGINE_ERROR}")

CHAIN = ["a" * 16, "b" * 16, "c" * 16, "d" * 16]


# ── Sélection des nœuds de la lignée ─────────────────────────────────────────

def test_selection_par_defaut_prend_les_deux_extremites():
    """`ends` = le couple que la page oppose partout ailleurs, et rien d'autre."""
    picked = select_nodes(CHAIN, "ends")
    assert [p["node"] for p in picked] == [CHAIN[0], CHAIN[-1]]
    assert [p["role"] for p in picked] == ["seed", "leaf"]


def test_selection_complete_garde_l_ordre_et_nomme_les_etapes():
    picked = select_nodes(CHAIN, "all")
    assert [p["node"] for p in picked] == CHAIN
    assert [p["role"] for p in picked] == ["seed", "step", "step", "leaf"]
    assert [p["label"] for p in picked][1:3] == ["Étape 1", "Étape 2"]


def test_selection_expose_le_rang_et_la_taille_de_la_lignee():
    """La page doit pouvoir dire « 2 nœuds sur 6 » sans recompter elle-même."""
    picked = select_nodes(CHAIN, "ends")
    assert {p["n_nodes_in_lineage"] for p in picked} == {len(CHAIN)}
    assert [p["rank"] for p in picked] == [0, len(CHAIN) - 1]


def test_lignee_d_un_seul_noeud_est_refusee():
    """Mesurer une graine seule ne dit rien d'une généralisation de calibration."""
    with pytest.raises(ValueError, match="pas de graine"):
        select_nodes(["a" * 16], "ends")


def test_selection_inconnue_est_refusee():
    with pytest.raises(ValueError, match="Sélection inconnue"):
        select_nodes(CHAIN, "les-deux-premiers")


# ── Description des jeux gelés : par personne ou par déplacement ? ───────────

def _write_split(dir_path, split: str, records: list[dict]):
    (dir_path / f"{split}.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8")


def test_profil_detecte_un_decoupage_par_personne(tmp_path):
    """Aucune personne partagée → la généralisation porte sur des individus."""
    _write_split(tmp_path, "train", [{"agent_id": "A", "section": "x"},
                                     {"agent_id": "A", "section": "y"},
                                     {"agent_id": "B", "section": "z"}])
    _write_split(tmp_path, "test", [{"agent_id": "C", "section": "w"}])
    profile = dataset_profile(tmp_path, splits=("train", "test"))
    assert profile["train"]["n_records"] == 3
    assert profile["train"]["n_agents"] == 2
    assert profile["test"]["agents_shared_with_train"] == 0


def test_profil_detecte_un_decoupage_par_deplacement(tmp_path):
    """Personnes partagées → l'affirmation forte serait fausse, et on le voit.

    C'est le cas que la page ne doit surtout pas confondre avec le précédent :
    des trajets différents des *mêmes* individus ne démontrent pas la même chose.
    """
    _write_split(tmp_path, "train", [{"agent_id": "A", "section": "x"}])
    _write_split(tmp_path, "test", [{"agent_id": "A", "section": "y"},
                                    {"agent_id": "B", "section": "z"}])
    profile = dataset_profile(tmp_path, splits=("train", "test"))
    assert profile["test"]["agents_shared_with_train"] == 1


def test_profil_mesure_la_presence_de_la_section_historique(tmp_path):
    """Le moteur retire la mémoire des jeux de retenue : la forme d'entrée diffère.

    Ce n'est pas une différence de population mais de *prompt*, et la confondre
    avec la première ferait attribuer au changement de personnes un écart qui
    vient d'une section absente.
    """
    _write_split(tmp_path, "train", [{"agent_id": "A", "section": "**Historique :** …"},
                                     {"agent_id": "B", "section": "sans mémoire"}])
    _write_split(tmp_path, "test", [{"agent_id": "C", "section": "sans mémoire"}])
    profile = dataset_profile(tmp_path, splits=("train", "test"))
    assert profile["train"]["with_memory"] == 1
    assert profile["train"]["memory_share"] == pytest.approx(0.5)
    assert profile["test"]["memory_share"] == pytest.approx(0.0)


def test_profil_ignore_un_split_absent(tmp_path):
    """Un clone sans jeu de screening ne doit pas faire échouer la page."""
    _write_split(tmp_path, "train", [{"agent_id": "A", "section": "x"}])
    profile = dataset_profile(tmp_path, splits=("train", "test", "screen"))
    assert set(profile) == {"train"}


def test_regle_de_decoupage_absente_ne_leve_pas(tmp_path):
    assert split_rule(tmp_path) is None


def test_regle_de_decoupage_est_relue_du_manifeste(tmp_path):
    (tmp_path / "manifest.yaml").write_text("split_rule: par personne\n",
                                            encoding="utf-8")
    assert split_rule(tmp_path) == "par personne"


# ── Témoin d'effectif ────────────────────────────────────────────────────────

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


def _frame(n_agents: int, mode: str = "voiture", start: int = 0) -> list[dict]:
    """Trame de scoring : deux décisions par personne, strates variées."""
    ages = ["20-24", "30-34", "45-49", "60-64", "75-130"]
    rows = []
    for i in range(start, start + n_agents):
        for k in range(2):
            rows.append({"agent_id": f"P{i}", "mode_cat": mode, "weight": 1.0,
                         "genre": "Femme" if i % 2 else "Homme",
                         "age_cat": ages[i % len(ages)],
                         "occupation": "actif_temps_plein",
                         "motif": "travail" if k == 0 else "achats",
                         "dist_cat": "2-5km"})
    return rows


@needs_engine
def test_temoin_tire_par_personne_et_garde_tous_ses_trajets(cerema, scorer,
                                                            monkeypatch):
    """Le tirage porte sur des personnes entières : jamais un trajet isolé.

    C'est le nombre de personnes par strate qui biaise JSD et EMD, pas le nombre
    de lignes ; un tirage par décision ne neutraliserait donc pas l'effet visé,
    tout en en ayant l'air.
    """
    seen: list[list[dict]] = []
    original = scorer.score

    def spy(rows, ref):
        seen.append(rows)
        return original(rows, ref)

    monkeypatch.setattr(scorer, "score", spy)
    build.resample_composite(_frame(20), cerema, scorer, n_agents=5, n_draws=3)
    assert len(seen) == 3
    for rows in seen:
        agents = {r["agent_id"] for r in rows}
        assert len(agents) == 5
        # Deux décisions par personne dans la trame de test : aucune n'est perdue.
        assert len(rows) == 10


@needs_engine
def test_temoin_est_reproductible_a_graine_fixee(cerema, scorer):
    """La page se régénère à l'identique : un témoin qui bouge invalide le Δ affiché."""
    rows = _frame(30)
    a = build.resample_composite(rows, cerema, scorer, n_agents=8, n_draws=20)
    b = build.resample_composite(rows, cerema, scorer, n_agents=8, n_draws=20)
    assert a == b


@needs_engine
def test_temoin_encadre_sa_moyenne(cerema, scorer):
    rows = _frame(30)
    out = build.resample_composite(rows, cerema, scorer, n_agents=8, n_draws=40)
    assert out["p05"] <= out["median"] <= out["p95"]
    assert out["p05"] <= out["mean"] <= out["p95"]
    assert out["n_agents"] == 8 and out["n_agents_source"] == 30


@needs_engine
def test_temoin_refuse_un_echantillon_plus_grand_que_la_source(cerema, scorer):
    """Tirer 66 personnes parmi 30 n'a pas de sens : mieux vaut rien qu'un chiffre."""
    assert build.resample_composite(_frame(10), cerema, scorer, n_agents=50) is None
    assert build.resample_composite([], cerema, scorer, n_agents=5) is None


@needs_engine
def test_temoin_du_gain_est_apparie(cerema, scorer):
    """Les deux prompts sont scorés sur LES MÊMES personnes tirées.

    C'est tout l'intérêt de ce second témoin : le bruit d'échantillonnage se
    compense entre les deux prompts, là où il domine le témoin par nœud. Deux
    trames identiques doivent donc donner un gain rigoureusement nul à chaque
    tirage — ce qui ne serait pas le cas si les tirages étaient indépendants.
    """
    rows = _frame(30)
    out = build.resample_gain(rows, list(rows), cerema, scorer,
                              n_agents=8, n_draws=15)
    assert out["p05"] == pytest.approx(0.0)
    assert out["p95"] == pytest.approx(0.0)
    assert out["n_agents_paired"] == 30


@needs_engine
def test_temoin_du_gain_n_apparie_que_les_personnes_communes(cerema, scorer):
    """Deux évals partielles ne doivent pas produire un tirage non apparié."""
    out = build.resample_gain(_frame(30), _frame(20), cerema, scorer,
                              n_agents=8, n_draws=5)
    assert out["n_agents_paired"] == 20


# ── Assemblage : le bloc de généralisation ───────────────────────────────────

REGIME = "modele-test · masse de probabilité"


def _row(short: str, dataset: str, composite: float) -> dict:
    return {"hash": short + "0" * 8, "short": short, "branch": "essai",
            "created_at": "2026-07-31", "verdict": "accepted",
            "eval_model": "modele-test", "store": "local", "dataset": dataset,
            "regime": REGIME, "regime_key": "k", "recomputed": composite,
            "stored": composite, "dims": {"composite": composite}}


def _profile(train_agents=30, held_agents=8, shared=0, memory=(0.9, 0.0)) -> dict:
    return {
        "train": {"n_records": train_agents * 2, "n_agents": train_agents,
                  "with_memory": 0, "memory_share": memory[0],
                  "agents_shared_with_train": None},
        "test": {"n_records": held_agents * 2, "n_agents": held_agents,
                 "with_memory": 0, "memory_share": memory[1],
                 "agents_shared_with_train": shared},
    }


def _generalization(cerema, scorer, *, held_seed=40.0, held_leaf=30.0, shared=0,
                    n_draws=25):
    """Assemblage complet, tirages réduits.

    ``n_draws`` est ramené à 25 : la page en fait 200, mais chaque tirage coûte un
    score complet et ce qui est vérifié ici est le *câblage*, pas la précision du
    témoin — laquelle est testée directement sur ``resample_composite``.
    """
    chain = ["1" * 16, "2" * 16]
    by_key = {
        ("11111111", REGIME, "train"): _row("11111111", "train", 25.0),
        ("22222222", REGIME, "train"): _row("22222222", "train", 22.0),
        ("11111111", REGIME, "test"): _row("11111111", "test", held_seed),
        ("22222222", REGIME, "test"): _row("22222222", "test", held_leaf),
    }
    frames_by_key = {
        ("11111111", REGIME, "train"): _frame(30, "voiture"),
        ("22222222", REGIME, "train"): _frame(30, "marche"),
    }
    return build.build_generalization(
        chain, by_key, frames_by_key, cerema, scorer,
        _profile(shared=shared), REGIME, "règle de test", "test",
        n_draws=n_draws)


@pytest.fixture(scope="module")
def generalization(cerema, scorer):
    """Assemblage de référence, calculé une seule fois pour toute la classe."""
    if CALIBRATION is None:
        pytest.skip(_ENGINE_ERROR)
    return _generalization(cerema, scorer)


@needs_engine
def test_bloc_oppose_le_train_au_jeu_de_retenue(generalization):
    gen = generalization
    assert gen["available"] is True
    assert gen["seed"]["train"] == 25.0 and gen["seed"]["held"] == 40.0
    assert gen["leaf"]["train"] == 22.0 and gen["leaf"]["held"] == 30.0
    assert gen["gain_train"] == pytest.approx(3.0)
    assert gen["gain_held"] == pytest.approx(10.0)


@needs_engine
def test_ecart_corrige_se_lit_contre_le_temoin_et_non_contre_le_train(generalization):
    """L'écart publiable est la différence au témoin, pas au score d'entraînement.

    Sans cette correction, un jeu de retenue plus petit ferait apparaître un
    surapprentissage même à décisions strictement inchangées.
    """
    leaf = generalization["leaf"]
    assert leaf["gap_raw"] == pytest.approx(leaf["held"] - leaf["train"])
    assert leaf["gap_controlled"] == pytest.approx(
        leaf["held"] - leaf["control"]["mean"])
    assert leaf["gap_controlled"] != pytest.approx(leaf["gap_raw"])


@needs_engine
def test_bloc_declare_un_decoupage_par_personne(generalization):
    assert generalization["by_person"] is True


@needs_engine
def test_bloc_declare_un_decoupage_par_deplacement(cerema, scorer):
    """Une personne partagée suffit à retirer l'affirmation forte."""
    assert _generalization(cerema, scorer, shared=1, n_draws=3)["by_person"] is False


@needs_engine
def test_bloc_absent_quand_aucun_noeud_n_est_mesure_sur_la_retenue(cerema, scorer):
    """Pas de demi-mesure : la page affiche sa carte « Données manquantes »."""
    by_key = {("11111111", REGIME, "train"): _row("11111111", "train", 25.0)}
    out = build.build_generalization(
        ["1" * 16, "2" * 16], by_key, {}, cerema, scorer, _profile(), REGIME,
        None, "test")
    assert out is None


@needs_engine
def test_bloc_absent_sans_regime_epingle(cerema, scorer):
    """Sans régime, on comparerait deux instruments de mesure — donc rien."""
    assert build.build_generalization(
        ["1" * 16, "2" * 16], {}, {}, cerema, scorer, _profile(), None, None,
        "test") is None


# ── Rendu ────────────────────────────────────────────────────────────────────

@needs_engine
def test_rendu_affiche_les_deux_temoins_et_la_nature_du_decoupage(generalization):
    html = render._generalization_block({"generalization": generalization})
    assert "Généralisation" in html
    assert "par personne" in html
    assert "témoin" in html.lower()
    assert "tirages appariés" in html
    # Le régime de mesure est cité : deux instruments ne se soustraient pas.
    assert REGIME in html


@needs_engine
def test_rendu_signale_la_section_historique_absente_de_la_retenue(generalization):
    """La confusion résiduelle doit être écrite, pas laissée au lecteur."""
    html = render._generalization_block({"generalization": generalization})
    assert "Historique" in html


def test_rendu_sans_mesure_donne_une_carte_manquante():
    html = render._generalization_block({"generalization": {
        "available": False, "dataset": "test", "regime": REGIME,
        "reason": "Aucun nœud évalué.", "action": "make heldout-eval"}})
    assert "Données manquantes" in html
    assert "make heldout-eval" in html


def test_matrice_renvoie_vers_le_bloc_sans_y_ajouter_de_colonne():
    """Le jeu de retenue est un TROISIÈME substrat : il n'entre pas dans la matrice.

    L'y coller ferait voisiner une colonne de 66 personnes avec des colonnes de
    881 — exactement la confusion que l'action A3 a corrigée.
    """
    payload = {
        "arms": {
            "simulation": {"status": "missing"},
            "calibration": {"status": "ok", "stores": [],
                            "common_set": {"available": False},
                            "generalization": {"available": True, "dataset": "test"}},
            "model": {"predictions": {"available": False}},
        },
        "score_def": {"primary": "emd_jsd"},
    }
    syn = build.build_synthesis(payload)
    assert syn["generalization_available"] is True
    assert syn["generalization_dataset"] == "test"
    assert not any("test" in (a["label"] or "").lower() for a in syn["arms"])


def test_matrice_sans_mesure_de_retenue_ne_revendique_rien():
    payload = {
        "arms": {
            "simulation": {"status": "missing"},
            "calibration": {"status": "ok", "stores": [],
                            "common_set": {"available": False},
                            "generalization": {"available": False}},
            "model": {"predictions": {"available": False}},
        },
        "score_def": {"primary": "emd_jsd"},
    }
    assert build.build_synthesis(payload)["generalization_available"] is False


# ── Liste d'actions : ce que le titre promet doit rester vrai ────────────────
#
# A4 était la dernière action « à engager ». Le compteur de la page est calculé,
# mais son titre — « ce qu'il reste à FAIRE » — ne l'était pas : il annonçait un
# chantier ouvert même quand tout le reste attendait une condition extérieure.

def _actions_html(actions: list[dict]) -> str:
    return render.section_provenance({"sources": [], "actions": actions})


def test_liste_d_actions_ne_promet_pas_un_travail_qui_n_existe_plus():
    """Tout le reste est « entamé » → il n'y a rien à engager, et la page le dit."""
    html = _actions_html([
        {"id": "A1", "title": "Faite", "detail": "d", "cost": "5 min",
         "unlocks": "u", "done": "ok"},
        {"id": "A2", "title": "Entamée", "detail": "d", "cost": "1 j", "unlocks": "u",
         "progress": {"acquis": "a", "reste": "un nouveau run"}},
    ])
    assert "1 en\nattente" in html or "1 en attente" in html
    assert "Plus aucune action n'attend qu'on l'engage" in html


def test_liste_d_actions_reste_franche_quand_du_travail_attend():
    html = _actions_html([
        {"id": "A1", "title": "Ouverte", "detail": "d", "cost": "1 j", "unlocks": "u"},
        {"id": "A2", "title": "Entamée", "detail": "d", "cost": "1 j", "unlocks": "u",
         "progress": {"acquis": "a", "reste": "r"}},
    ])
    assert "Plus aucune action n'attend qu'on l'engage" not in html


def test_liste_d_actions_tout_faite():
    html = _actions_html([{"id": "A1", "title": "Faite", "detail": "d", "cost": "5 min",
                           "unlocks": "u", "done": "ok"}])
    assert "Toutes les actions listées sont faites" in html


def test_action_a4_est_marquee_faite_avec_son_resultat():
    """La liste est la source de vérité entre la doc et le rendu (cf. build.ACTIONS).

    Ce test ne vérifie pas qu'un travail a été fait — il vérifie que l'entrée dit
    ce que la mesure a donné, y compris ce qu'elle ne démontre pas. Une entrée
    `done` qui se contenterait d'annoncer « mesuré » laisserait croire à un
    résultat que les 66 personnes du jeu de test ne portent pas.
    """
    a4 = next(a for a in build.ACTIONS if a["id"] == "A4")
    assert a4.get("done"), "A4 doit être marquée faite"
    assert "PAR PERSONNE" in a4["done"], "la nature du découpage doit être publiée"
    assert "témoin" in a4["done"], "le contrôle d'effectif doit être publié"


# ── Cohérence avec le dépôt réel ─────────────────────────────────────────────

def test_jeux_geles_du_depot_sont_bien_decoupes_par_personne():
    """Le fait sur lequel repose tout le vocabulaire de la page, vérifié ici.

    Si un jour les jeux étaient régénérés avec un découpage par déplacement, la
    page continuerait de fonctionner — mais dirait « par déplacement », et ce
    test rappellerait que l'affirmation publiée a changé de nature.
    """
    dataset_dir = load_manifest().path_of("arms.calibration.datasets")
    if dataset_dir is None or not (dataset_dir / "test.jsonl").exists():
        pytest.skip("Jeux gelés absents de ce clone")
    profile = dataset_profile(dataset_dir)
    assert profile["test"]["agents_shared_with_train"] == 0
    assert profile["val"]["agents_shared_with_train"] == 0
    # `screen` est au contraire un sous-ensemble STRICT du train — c'est voulu, et
    # c'est pourquoi il ne peut pas servir de jeu de retenue.
    assert profile["screen"]["agents_shared_with_train"] == profile["screen"]["n_agents"]
