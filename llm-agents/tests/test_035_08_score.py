"""Ticket 035 — scoring composite d'une exécution (R1, R2, R5, R6, R8, R15, R17, R18, R21).

Voir `specs/scoring_composite_experiences.md`. Substrat : une vraie exécution terminée du
dépôt, copiée en tmp pour que les écritures ne polluent pas `data/`.
"""

import json
import shutil
from pathlib import Path

import pytest
from experiences import formule as F
from experiences import score as S

REPO = Path(__file__).resolve().parents[2]


def _exec_reelle() -> Path | None:
    """La première exécution terminée et exploitable du dépôt, quel que soit son nom.

    Pointée en dur, la référence disparaissait avec l'expérience qui la portait (une
    suppression depuis le tableau de bord suffit) et TOUTE la suite se mettait à
    skipper sans que rien ne le signale : des tests verts qui ne testent rien.
    """
    racine = REPO / "data" / "experiences"
    for exp in sorted(racine.iterdir()) if racine.is_dir() else []:
        for d in sorted((exp / "executions").iterdir()) if (exp / "executions").is_dir() else []:
            if not (d / "moves.csv").exists() or not (d / "synthese.json").exists():
                continue
            try:
                synthese = json.loads((d / "synthese.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if (synthese.get("etat") or {}).get("etat") == "terminee":
                return d
    return None


EXEC_REELLE = _exec_reelle()

CHAMPS_OBLIGATOIRES = (
    "execution",
    "volet",
    "formule",
    "moves_sha256",
    "couverture",
    "composite",
    "scores_bruts",
    "detail",
)


pytestmark = pytest.mark.skipif(
    EXEC_REELLE is None,
    reason="aucune exécution terminée dans data/experiences (substrat absent)",
)


@pytest.fixture
def exec_tmp(tmp_path):
    dst = tmp_path / EXEC_REELLE.name
    shutil.copytree(EXEC_REELLE, dst)
    # Substrat propre : retirer d'éventuels artefacts de score déjà présents dans
    # l'exécution réelle (un `score --toutes` a pu en écrire), sinon les tests qui
    # vérifient l'absence de scores.json partent biaisés.
    for f in ("scores.json", "synthese_scores.html"):
        (dst / f).unlink(missing_ok=True)
    return dst


@pytest.fixture(scope="module")
def registre():
    return F.charger()


def test_R1_composite_vient_du_scorer(exec_tmp, registre):
    # Le composite de calculer() égale celui d'un Scorer appliqué à la même trame.
    contenu = S.calculer(exec_tmp, registre.reference)
    scorer, _ = S.scorer_pour(registre.reference)
    rows, _ = S.frames.read_moves(
        exec_tmp / "moves.csv", S.EXCLURE_METHODES, first_day_only=True
    )
    attendu = S.frames.simulation_frames(rows)["attendu"]
    cerema = S.frames.load_cerema(
        S._resoudre_cerema(json.loads((exec_tmp / "synthese.json").read_text()))
    )
    direct = scorer.score(attendu, cerema)["emd_jsd"]["composite"]
    assert abs(contenu["composite"]["emd_jsd"] - direct) < 1e-9


def test_R2_length_penalty_hors_composite(exec_tmp, registre):
    from calibration import metrics as m

    contenu = S.calculer(exec_tmp, registre.reference)
    emd = contenu["scores_bruts"]["emd_jsd"]
    poids = registre.reference.poids_scorer()
    assert "length_penalty" not in poids
    # Le composite est exactement la somme pondérée sur les 7 dimensions ; ajouter un
    # poids length_penalty via les poids de formule est impossible (R19), donc il n'entre
    # jamais : la valeur stockée coïncide avec la somme sur les 7 dimensions.
    assert (
        abs(contenu["composite"]["emd_jsd"] - m.weighted_composite(emd, poids)) < 1e-9
    )


def test_R5_scores_json_complet(exec_tmp, registre):
    contenu = S.calculer(exec_tmp, registre.reference)
    for champ in CHAMPS_OBLIGATOIRES:
        assert champ in contenu, f"champ obligatoire manquant : {champ}"
    # détail par strate : cible / obtenu / L1 / effectif présents
    strate = contenu["detail"]["age"]["strates"][0]
    for cle in ("cat", "n", "actual", "target", "l1"):
        assert cle in strate


def test_R6_rejeu_exact(exec_tmp, registre):
    ref = S.calculer(exec_tmp, registre.reference)
    poids_alt = {**registre.reference.poids, "age": 0.9, "distance": 0.1}
    alt = F.Formule("alt", poids_alt, F.empreinte(poids_alt))
    rejoue = S.rejouer(ref, alt)
    frais = S.calculer(exec_tmp, alt)
    assert abs(rejoue["composite"]["emd_jsd"] - frais["composite"]["emd_jsd"]) < 1e-9
    assert abs(rejoue["composite"]["l1"] - frais["composite"]["l1"]) < 1e-9
    assert rejoue["formule"]["sha256"] == alt.sha256


def test_R8_dimension_vide_non_mesuree(registre):
    # Une trame dont une dimension n'a aucune strate mesurée : le moteur la déclare
    # `undefined` (repli perte max), jamais un 0 silencieux, et le composite ne tombe pas à 0.
    scorer, _ = S.scorer_pour(registre.reference)
    cerema = S.frames.load_cerema(S.CEREMA_DEPOT)
    # Une seule décision, sans catégorie de distance ni d'âge renseignée.
    rows = [
        {
            "agent_id": "a1",
            "mode_cat": "voiture",
            "weight": 1.0,
            "genre": "Homme",
            "age_cat": None,
            "occupation": "actif_temps_plein",
            "motif": "travail",
            "dist_cat": None,
            "lieu_residence": None,
            "type_logement": None,
        }
    ]
    scores, mesure = scorer.primary.compute_detailed(scorer._pd.DataFrame(rows), cerema)
    assert mesure.undefined, "au moins une dimension doit être déclarée non mesurée"
    assert scores.composite != 0.0


def test_R15_routage_volet(exec_tmp):
    # L'exécution de référence n'est PAS choisie en dur (cf. _exec_reelle) : son décideur
    # est celui de la première exécution terminée du dépôt, `passerelle` ou `modele` selon
    # ce qui s'y trouve ce jour-là. Poser `== "1"` sur elle telle quelle, c'était tester ce
    # tirage plutôt que la règle — la suite est passée au rouge le 2026-09-08 dès que
    # `Light_GBM` (décideur `modele`, premier dans l'ordre alphabétique) a produit une
    # exécution terminée. On fixe donc le type explicitement, et les DEUX branches de R15
    # sont couvertes quoi qu'il y ait sur disque.
    synthese = json.loads((exec_tmp / "synthese.json").read_text())
    synthese["empreintes"]["decideur"]["type"] = "modele"
    assert S.volet_pour(synthese) == "3"
    synthese["empreintes"]["decideur"]["type"] = "passerelle"
    assert S.volet_pour(synthese) == "1"


def test_R17_substrat_lie_moves(exec_tmp, registre):
    S.score_execution(exec_tmp, registre.reference)
    assert not S.scores_perimes(exec_tmp)
    (exec_tmp / "moves.csv").write_text("Référence\nmodifié\n", encoding="utf-8")
    assert S.scores_perimes(exec_tmp)


def test_R21_partielle_non_scoree(exec_tmp, registre):
    synthese = json.loads((exec_tmp / "synthese.json").read_text())
    synthese["etat"]["etat"] = "interrompue"
    (exec_tmp / "synthese.json").write_text(json.dumps(synthese), encoding="utf-8")
    assert S.score_execution(exec_tmp, registre.reference) is None
    assert not (exec_tmp / "scores.json").exists()


def _racine_avec(exec_tmp, tmp_path) -> Path:
    racine = tmp_path / "experiences"
    (racine / "Exp" / "executions").mkdir(parents=True)
    shutil.copytree(exec_tmp, racine / "Exp" / "executions" / exec_tmp.name)
    return racine


def test_R10_recalcul_hors_ligne(exec_tmp, tmp_path, registre, monkeypatch):
    # Une exécution déjà scorée (moves inchangé) se recalcule par REJEU, sans
    # reconstruire le Scorer : on le prouve en faisant échouer scorer_pour.
    racine = _racine_avec(exec_tmp, tmp_path)
    cible = racine / "Exp" / "executions" / exec_tmp.name
    S.score_execution(cible, registre.reference)  # premier calcul (une fois)

    def _interdit(*a, **k):
        raise AssertionError(
            "scorer_pour ne doit pas être appelé sur le chemin de rejeu (R10)"
        )

    monkeypatch.setattr(S, "scorer_pour", _interdit)
    poids = {**registre.reference.poids, "motif": 0.8}
    alt = F.Formule("alt", poids, F.empreinte(poids))
    bilan = S.rescorer_tout(alt, registre, racine=racine)
    assert bilan["rejouees"] == 1 and bilan["calculees"] == 0
    rescore = json.loads((cible / "scores.json").read_text())
    assert rescore["formule"]["sha256"] == alt.sha256


def test_rescorer_tout_ignore_partielles(exec_tmp, tmp_path, registre):
    racine = _racine_avec(exec_tmp, tmp_path)
    cible = racine / "Exp" / "executions" / exec_tmp.name
    synthese = json.loads((cible / "synthese.json").read_text())
    synthese["etat"]["etat"] = "interrompue"
    (cible / "synthese.json").write_text(json.dumps(synthese), encoding="utf-8")
    bilan = S.rescorer_tout(registre.reference, registre, racine=racine)
    assert bilan["ignorees"] == 1
    assert not (cible / "scores.json").exists()


def test_R7_est_reference_derive(exec_tmp, registre):
    contenu = S.calculer(exec_tmp, registre.reference)
    assert S.est_reference(contenu, registre)
    # Simuler une formule de référence différente sans toucher au scores.json.
    autre = F.Formule(
        "autre",
        {**registre.reference.poids, "genre": 0.99},
        F.empreinte({**registre.reference.poids, "genre": 0.99}),
    )
    faux_registre = F.RegistreFormules([autre], "autre")
    assert not S.est_reference(contenu, faux_registre)


def test_R6_rejeu_dans_un_interprete_vierge(exec_tmp, registre, tmp_path):
    """Le rejeu hors-ligne ne dépend d'aucun `scorer_pour` préalable.

    Seul `scorer_pour` met `prompt_calibration/` sur `sys.path`. En le supposant déjà
    fait, `rejouer` mourait en ModuleNotFoundError dans un processus qui n'avait rien
    calculé — exactement le cas de `score --toutes` et du bouton « Recalculer toutes
    les expériences » quand la première exécution rencontrée est déjà scorée.
    """
    import subprocess
    import sys as _sys

    fichier = tmp_path / "scores.json"
    fichier.write_text(
        json.dumps(S.calculer(exec_tmp, registre.reference)), encoding="utf-8"
    )
    code = (
        "import json;"
        "from experiences import formule as F, score as S;"
        "reg = F.charger();"
        f"s = json.load(open({str(fichier)!r}));"
        "print(S.rejouer(s, reg.reference)['composite']['emd_jsd'])"
    )
    proc = subprocess.run(
        [_sys.executable, "-c", code],
        cwd=REPO / "llm-agents",
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    attendu = S.rejouer(json.loads(fichier.read_text()), registre.reference)
    assert abs(float(proc.stdout.strip()) - attendu["composite"]["emd_jsd"]) < 1e-9
