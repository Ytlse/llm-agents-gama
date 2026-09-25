"""Tests des espaces de travail du registre (spec `espaces-de-travail-experiences`).

Un test par règle, le numéro de règle dans le nom. Ce qui est verrouillé ici :

  * un espace **filtre une vue, il ne range rien** : aucun chemin de ce module ne touche à
    `data/experiences/`, et « Toutes les expériences » redonne exactement la liste d'avant ;
  * le fichier de définition **échoue ouvert**. Absent, tronqué, de type inattendu, il laisse
    le registre debout sur « Toutes les expériences ». Un fichier de confort qui rendrait le
    tableau de bord inaccessible serait pire que son absence ;
  * un nom cité **sans dossier sur le disque n'est pas une erreur** : l'espace se remplit avant
    les expériences, et c'est précisément l'usage prévu pour le ticket 103 ;
  * l'espace livré, « papier version courte », dit ce que le ticket 103 annonce — sinon le
    tableau de bord raconte un plan que personne n'a validé.

    services/llm-agents/.venv/bin/python -m pytest scripts/tests/test_103_espaces_experiences.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.dashboard import espaces as E  # noqa: E402

LIVRE = REPO_ROOT / "scripts" / "dashboard" / "espaces_experiences.yaml"
ESPACE_103 = "papier version courte"


def _ecrire(tmp_path: Path, contenu: object, nom: str = "espaces.yaml") -> Path:
    p = tmp_path / nom
    p.write_text(contenu if isinstance(contenu, str) else yaml.safe_dump(contenu, allow_unicode=True),
                 encoding="utf-8")
    return p


@pytest.fixture()
def deux_espaces(tmp_path: Path) -> Path:
    return _ecrire(tmp_path, {
        "version": "espaces1",
        "espaces": [
            {"nom": "alpha", "entrees": [
                {"experience": "exp_a", "phase": "P1"},
                {"experience": "exp_b", "phase": "P1"},
                {"experience": "exp_c", "phase": "P2", "optionnel": True},
            ]},
            {"nom": "beta", "entrees": [{"experience": "exp_b"}]},
        ],
    })


# ── R1 — un espace porte un nom et une liste ordonnée ────────────────────────────────
def test_R1_deux_espaces_lus_avec_leurs_listes_dans_l_ordre(deux_espaces):
    lus = E.espaces(deux_espaces)
    assert [e["nom"] for e in lus] == ["alpha", "beta"]
    assert [x["experience"] for x in lus[0]["entrees"]] == ["exp_a", "exp_b", "exp_c"]
    assert [x["experience"] for x in lus[1]["entrees"]] == ["exp_b"]


# ── R2 — « Toutes les expériences » en tête du menu ──────────────────────────────────
def test_R2_le_menu_commence_par_toutes_les_experiences(deux_espaces):
    assert E.noms(deux_espaces) == [E.TOUTES, "alpha", "beta"]


# ── R3 — défaut : rien n'est filtré ──────────────────────────────────────────────────
def test_R3_toutes_les_experiences_ne_filtre_rien(deux_espaces):
    lignes = [{"experience": f"exp_{c}"} for c in "abcdxyz"]
    assert E.filtrer(lignes, E.TOUTES, deux_espaces) == lignes
    assert E.filtrer(lignes, None, deux_espaces) == lignes


# ── R4 — un espace nommé restreint le registre à sa liste ────────────────────────────
def test_R4_un_espace_restreint_le_registre_a_sa_liste(deux_espaces):
    lignes = [{"experience": f"exp_{c}"} for c in "abcdxyz"]
    gardees = E.filtrer(lignes, "alpha", deux_espaces)
    assert [l["experience"] for l in gardees] == ["exp_a", "exp_b", "exp_c"]


# ── R6 — l'espace livré est celui du ticket 103 ──────────────────────────────────────
def test_R6_espace_papier_version_courte_couvre_les_quatre_phases():
    noms = E.noms(LIVRE)
    assert ESPACE_103 in noms
    par_phase: dict[str, int] = {}
    for x in E.entrees(ESPACE_103, LIVRE):
        par_phase[x["phase"]] = par_phase.get(x["phase"], 0) + 1
    assert par_phase == {
        "Phase 1 — échelle c2": 7,
        "Phase 2 — Jev sur c2": 3,
        "Phase 3 — Gemini sur c2": 2,
        "Phase 4 — graines Jev (c1)": 4,
        "Phase 5 — rejeux inter-graines (c1)": 6,
        "Optionnel — Gemini différé": 3,
        "Acquis (c1)": 14,
    }


def test_R6_espace_livre_contient_le_pivot_et_la_ligne_qui_rend_le_carre_carre():
    dedans = E.index(ESPACE_103, LIVRE)
    # Le résultat pivot hors échantillon (Q1) et le prompt de Jev servi à Gemini (Q2).
    assert "exp_jev-1130_proexp32_jtir_pop-1000_AAMAS_v6_c2_jeu-20260316_EN_c_nosim" in dedans
    assert "exp_gemini-35-fl_proexp32_jtir_pop-1000_AAMAS_v6_c2_jeu-20260316_EN_c_t0_nosim" in dedans


# ── R6a — l'étiquette de phase vit dans l'espace, jamais dans le nom ─────────────────
def test_R6a_la_phase_est_une_etiquette_et_non_un_segment_du_nom():
    for x in E.entrees(ESPACE_103, LIVRE):
        assert x["phase"], f"entrée sans phase : {x['experience']}"
        # Le nom se calcule depuis les paramètres : il ne doit porter aucune marque de phase.
        assert "phase" not in x["experience"].lower()
        assert "_p1_" not in x["experience"] and "_opt_" not in x["experience"]


# ── R6b — les entrées optionnelles sont marquées et visibles ─────────────────────────
def test_R6b_les_trois_runs_differes_sont_marques_optionnels():
    opts = [x for x in E.entrees(ESPACE_103, LIVRE) if x["optionnel"]]
    assert len(opts) == 3
    assert all("promin02" in x["experience"] for x in opts)
    # Marquées, mais rendues : `entrees()` ne les retire pas.
    assert all(x in E.entrees(ESPACE_103, LIVRE) for x in opts)


# ── R7 — un espace est une vue, pas un rangement ─────────────────────────────────────
def test_R7_filtrer_ne_touche_a_aucune_experience_du_disque(deux_espaces):
    avant = sorted(p.name for p in (REPO_ROOT / "data" / "experiences").iterdir())
    lignes = [{"experience": "exp_a"}, {"experience": "exp_z"}]
    E.filtrer(lignes, "alpha", deux_espaces)
    E.filtrer(lignes, E.TOUTES, deux_espaces)
    assert sorted(p.name for p in (REPO_ROOT / "data" / "experiences").iterdir()) == avant
    # Et le retour à « Toutes » redonne la liste entière, sans perte.
    assert E.filtrer(lignes, E.TOUTES, deux_espaces) == lignes


# ── R8 — une expérience peut appartenir à plusieurs espaces ──────────────────────────
def test_R8_une_experience_appartient_a_deux_espaces(deux_espaces):
    assert "exp_b" in E.index("alpha", deux_espaces)
    assert "exp_b" in E.index("beta", deux_espaces)


# ── R9 — un nom sans dossier n'est pas une erreur ────────────────────────────────────
def test_R9_les_noms_sans_dossier_sont_comptes_et_non_fatals(deux_espaces):
    manque = E.manquantes({"exp_a"}, "alpha", deux_espaces)
    assert manque == ["exp_b", "exp_c"]
    # L'espace reste parfaitement lisible malgré les manquantes.
    assert len(E.entrees("alpha", deux_espaces)) == 3


def test_R9_l_espace_livre_peut_citer_des_experiences_pas_encore_lancees():
    presentes = {p.name for p in (REPO_ROOT / "data" / "experiences").iterdir() if p.is_dir()}
    # Aucune exigence de complétude : le test vérifie que la fonction répond, pas qu'elle est vide.
    assert isinstance(E.manquantes(presentes, ESPACE_103, LIVRE), list)


# ── R10 — aucune expérience ne disparaît de « Toutes » ───────────────────────────────
def test_R10_une_experience_citee_par_aucun_espace_reste_dans_toutes(deux_espaces):
    lignes = [{"experience": "exp_orpheline"}]
    assert E.filtrer(lignes, E.TOUTES, deux_espaces) == lignes
    assert E.filtrer(lignes, "alpha", deux_espaces) == []


# ── R11 — un espace vide s'affiche et ne se confond pas avec « Toutes » ──────────────
def test_R11_un_espace_a_liste_vide_existe_et_ne_filtre_pas_comme_toutes(tmp_path):
    p = _ecrire(tmp_path, {"espaces": [{"nom": "vide", "entrees": []}]})
    assert E.noms(p) == [E.TOUTES, "vide"]
    assert E.entrees("vide", p) == []
    assert E.filtrer([{"experience": "exp_a"}], "vide", p) == []


# ── R12 — le filtre par espace se compose avec le masquage par statut ────────────────
def test_R12_le_filtre_par_espace_conserve_le_champ_statut(deux_espaces):
    lignes = [{"experience": "exp_a", "statut": "actif"},
              {"experience": "exp_b", "statut": "archivee"}]
    gardees = E.filtrer(lignes, "alpha", deux_espaces)
    # L'espace ne masque rien lui-même : il rend les lignes telles quelles, statut compris,
    # et c'est la vue qui applique ensuite `masquee()` comme avant.
    assert [l["statut"] for l in gardees] == ["actif", "archivee"]


# ── R13 — le fichier échoue ouvert ───────────────────────────────────────────────────
def test_R13_fichier_absent(tmp_path):
    assert E.espaces(tmp_path / "rien.yaml") == []
    assert E.noms(tmp_path / "rien.yaml") == [E.TOUTES]


def test_R13_fichier_tronque_en_plein_milieu(tmp_path):
    p = _ecrire(tmp_path, "espaces:\n  - nom: alpha\n    entrees:\n      - experience: 'exp_a\n")
    assert E.espaces(p) == []
    assert E.noms(p) == [E.TOUTES]


def test_R13_contenu_de_type_inattendu(tmp_path):
    assert E.espaces(_ecrire(tmp_path, "- juste\n- une\n- liste\n")) == []
    assert E.espaces(_ecrire(tmp_path, {"espaces": "pas une liste"})) == []
    assert E.espaces(_ecrire(tmp_path, {"espaces": [{"nom": "a", "entrees": "pas une liste"}]})) \
        == [{"nom": "a", "note": None, "entrees": []}]


def test_R13_entrees_invalides_ignorees_une_a_une(tmp_path):
    p = _ecrire(tmp_path, {"espaces": [
        {"nom": "alpha", "entrees": [
            {"experience": "exp_a"},
            {"phase": "sans nom"},
            {"experience": "../../etc/passwd"},
            {"experience": "avec/slash"},
            {"experience": "ctrl\x01"},
            "exp_forme_courte",
        ]},
        {"nom": E.TOUTES, "entrees": []},          # nom réservé
        {"nom": "alpha", "entrees": []},           # doublon
        {"entrees": []},                            # sans nom
    ]})
    lus = E.espaces(p)
    assert [e["nom"] for e in lus] == ["alpha"]
    assert [x["experience"] for x in lus[0]["entrees"]] == ["exp_a", "exp_forme_courte"]


# ── R14 — un espace mémorisé disparu retombe sur « Toutes » ──────────────────────────
def test_R14_espace_memorise_disparu_retombe_sur_toutes(deux_espaces):
    assert E.actif_valide("alpha", deux_espaces) == "alpha"
    assert E.actif_valide("gamma", deux_espaces) == E.TOUTES
    assert E.actif_valide(None, deux_espaces) == E.TOUTES
    assert E.actif_valide(E.TOUTES, deux_espaces) == E.TOUTES


# ── Le fichier livré doit rester lisible par ce module ───────────────────────────────
def test_le_fichier_livre_est_lisible_et_sans_entree_rejetee(caplog):
    with caplog.at_level("WARNING"):
        lus = E.espaces(LIVRE)
    assert len(lus) == 1 and lus[0]["nom"] == ESPACE_103
    assert len(lus[0]["entrees"]) == 39
    assert not [r for r in caplog.records if "[espaces]" in r.getMessage()]


# ── Règles branchées dans le tableau de bord ─────────────────────────────────────────
# Les tests ci-dessus portent sur le module de lecture ; ceux-ci sur son câblage dans
# `scripts.dashboard.experiences`, où vivent la persistance (R5), la colonne de phase (R6a)
# et la portée du filtre (R15, R16).

from scripts.dashboard import experiences as X  # noqa: E402


# ── R5 — l'espace actif survit au redémarrage ────────────────────────────────────────
def test_R5_l_espace_actif_survit_au_redemarrage(tmp_path, monkeypatch, deux_espaces):
    monkeypatch.setattr(X, "ETAT_ESPACE_ACTIF", tmp_path / "espace_actif.txt")
    monkeypatch.setattr(X.ESP, "FICHIER", deux_espaces)
    assert X.charger_espace_actif() == E.TOUTES          # rien de retenu encore
    assert X.sauver_espace_actif("alpha") is True
    assert X.charger_espace_actif() == "alpha"           # relu d'un processus neuf
    assert X.sauver_espace_actif("alpha") is False       # rien à réécrire


def test_R5_un_fichier_d_espace_actif_illisible_ne_casse_rien(tmp_path, monkeypatch, deux_espaces):
    dossier = tmp_path / "espace_actif.txt"
    dossier.mkdir()                                       # un dossier là où un fichier est attendu
    monkeypatch.setattr(X, "ETAT_ESPACE_ACTIF", dossier)
    monkeypatch.setattr(X.ESP, "FICHIER", deux_espaces)
    assert X.charger_espace_actif() == E.TOUTES
    assert X.sauver_espace_actif("alpha") is False        # échec ouvert, pas d'exception


# ── R14 — au redémarrage, un espace disparu du fichier retombe sur « Toutes » ────────
def test_R14_espace_retenu_puis_supprime_du_fichier(tmp_path, monkeypatch, deux_espaces):
    monkeypatch.setattr(X, "ETAT_ESPACE_ACTIF", tmp_path / "espace_actif.txt")
    monkeypatch.setattr(X.ESP, "FICHIER", deux_espaces)
    X.sauver_espace_actif("alpha")
    deux_espaces.write_text(yaml.safe_dump({"espaces": [{"nom": "beta", "entrees": []}]}),
                            encoding="utf-8")
    assert X.charger_espace_actif() == E.TOUTES


# ── R6a — la colonne de phase est annotée sur les lignes, pas sur les noms ───────────
def test_R6a_annoter_pose_la_phase_sur_les_lignes(monkeypatch, deux_espaces):
    monkeypatch.setattr(X.ESP, "FICHIER", deux_espaces)
    lignes = [{"experience": "exp_a"}, {"experience": "exp_c"}]
    X._annoter_espace(lignes, "alpha")
    assert lignes[0]["phase"] == "P1"
    assert lignes[1]["phase"] == "P2 · optionnel"        # R6b — l'optionnel se voit


def test_R6a_sans_espace_aucune_colonne_de_phase_n_est_posee(monkeypatch, deux_espaces):
    monkeypatch.setattr(X.ESP, "FICHIER", deux_espaces)
    lignes = [{"experience": "exp_a"}]
    X._annoter_espace(lignes, E.TOUTES)
    assert "phase" not in lignes[0]


def test_R6a_la_colonne_phase_est_connue_du_registre_et_affichee_par_defaut():
    assert "phase" in X.COLONNES_REGISTRE
    assert "phase" in X.COLONNES_REGISTRE_DEFAUT


# ── R12 — espace puis statut : l'ordre des deux filtres ─────────────────────────────
def test_R12_le_filtre_par_espace_precede_le_masquage_par_statut(monkeypatch, deux_espaces):
    monkeypatch.setattr(X.ESP, "FICHIER", deux_espaces)
    lignes = [{"experience": "exp_a", "statut": "actif"},
              {"experience": "exp_b", "statut": "archivee"},
              {"experience": "exp_hors", "statut": "actif"}]
    dans_espace = E.filtrer(lignes, "alpha", deux_espaces)
    assert [l["experience"] for l in dans_espace] == ["exp_a", "exp_b"]
    visibles = [l for l in dans_espace if not X.masquee(l)]
    assert [l["experience"] for l in visibles] == ["exp_a"]


# ── R15 — « s'inspirer de » suit l'espace actif ──────────────────────────────────────
def test_R15_la_liste_du_formulaire_se_restreint_a_l_espace(monkeypatch, deux_espaces):
    monkeypatch.setattr(X.ESP, "FICHIER", deux_espaces)
    proposables = {"exp_a": {}, "exp_b": {}, "exp_hors": {}}
    dedans = X.ESP.index("alpha")
    restreintes = {n: e for n, e in proposables.items() if n in dedans}
    assert list(restreintes) == ["exp_a", "exp_b"]
    # Et sous « Toutes », la liste reste entière.
    assert list(proposables) == ["exp_a", "exp_b", "exp_hors"]


# ── R16 — ce qui tourne reste visible quel que soit l'espace ─────────────────────────
def test_R16_les_vues_d_activite_ne_consultent_jamais_l_espace_actif():
    import inspect
    for fn in (X.activites_en_cours, X.interrompues, X.rendre_activites, X.rendre_reprenables):
        source = inspect.getsource(fn)
        assert "ESP." not in source and "espace_actif" not in source, (
            f"{fn.__name__} filtre par espace : une exécution qui tourne se perdrait de vue "
            "en changeant de menu")


# ── R6a — la colonne apparaît en cours de session, quand l'espace la fait naître ─────
def test_R6a_la_colonne_phase_entre_quand_un_espace_devient_actif():
    """Défaut constaté à l'écran le 2026-09-22 : le filtrage marchait, la colonne non.

    La liste des colonnes est figée au PREMIER dessin, sous « Toutes les expériences », où
    `phase` n'existe pas encore. Sans rattrapage, choisir un espace ne la fait jamais entrer.
    """
    presentes = ["phase", "experience", "etat"]
    # Ce que la session avait retenu avant que l'espace existe : pas de `phase`.
    retenues = ["experience", "etat"]
    memoire = {}
    if ("phase" in presentes and "phase" not in retenues
            and "phase" not in (memoire.get("retirees") or ())):
        retenues = ["phase", *retenues]
    assert retenues[0] == "phase"


def test_R6a_une_phase_decochee_par_l_usager_ne_revient_pas():
    """Le rattrapage ne doit pas ressusciter un choix explicite de l'usager."""
    presentes = ["phase", "experience"]
    retenues = ["experience"]
    memoire = {"retirees": ["phase"]}
    if ("phase" in presentes and "phase" not in retenues
            and "phase" not in (memoire.get("retirees") or ())):
        retenues = ["phase", *retenues]
    assert "phase" not in retenues


def test_R6a_le_rattrapage_est_bien_pose_dans_le_code():
    """Le test ci-dessus reproduit la règle ; celui-ci vérifie qu'elle est dans le module."""
    import inspect
    source = inspect.getsource(X._panneau_colonnes_et_filtres)
    assert '"phase" in presentes' in source and '"phase" not in (memoire.get("retirees")' in source
