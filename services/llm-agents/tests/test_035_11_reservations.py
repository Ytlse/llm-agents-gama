"""Ticket 035, spec parallelisation_experiences — clés, réservation, file (R1–R12).

Un test par règle, nommé par son numéro. Aucun conteneur, aucun réseau : le registre de
réservation et la file vivent dans un `EXPERIENCES_DIR` temporaire.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from experiences import reservations as R
from experiences.archive import ETAT_EN_COURS, ETAT_INTERROMPUE, Execution
from experiences.cles import identite_cle, jeu_de_cles

PROVIDERS = {
    "mistral": {"default_model": "mistral-small-latest"},
    "google_35": {"adapter": "google", "default_model": "gemini-3.5-flash"},
    "google_36": {"adapter": "google", "default_model": "gemini-3.6-flash"},
    "cerebras_x": {"adapter": "cerebras", "default_model": "gpt-oss-120b"},
    "sans_cle": {"adapter": "orphelin", "default_model": "modele-sans-cle"},
}


@pytest.fixture
def experiences_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIENCES_DIR", str(tmp_path))
    return tmp_path


def _execution(experiences_dir, nom_exp="Exp"):
    """Crée une archive d'exécution minimale mais valide (execution.yaml + etat.json)."""
    dossier_exp = experiences_dir / nom_exp
    ex = Execution.creer(
        dossier_exp,
        experience={"nom": nom_exp},
        empreintes={},
        regime_demande={},
        sources_alea={},
    )
    return ex


# ── R4 : dérivation modèle → identité de clé ──────────────────────────────────


def test_R4_meme_fournisseur_meme_cle():
    assert jeu_de_cles("gemini-3.5-flash", PROVIDERS) == {"google"}
    assert jeu_de_cles("gemini-3.6-flash", PROVIDERS) == {"google"}
    # Deux modèles DIFFÉRENTS partageant l'adapter `google` → clés NON disjointes (conflit).
    assert jeu_de_cles("gemini-3.5-flash", PROVIDERS) & jeu_de_cles(
        "gemini-3.6-flash", PROVIDERS
    )


def test_R4_fournisseurs_distincts_cles_disjointes():
    assert jeu_de_cles("mistral-small-latest", PROVIDERS) == {"mistral"}
    assert jeu_de_cles("gpt-oss-120b", PROVIDERS) == {"cerebras"}
    assert not (
        jeu_de_cles("mistral-small-latest", PROVIDERS)
        & jeu_de_cles("gpt-oss-120b", PROVIDERS)
    )


def test_R4_identite_par_adapter_sinon_nom():
    assert identite_cle("google_35", PROVIDERS["google_35"]) == "google"
    assert identite_cle("mistral", PROVIDERS["mistral"]) == "mistral"


# ── R8 / R9 : jeu de clés vide ────────────────────────────────────────────────


def test_R8_modele_sans_instance_jeu_vide():
    assert jeu_de_cles("modele-inexistant", PROVIDERS) == set()


def test_R9_instances_indisponibles_exclues():
    # Aucune instance admise (toutes épuisées / sans clé) → jeu vide.
    assert jeu_de_cles("mistral-small-latest", PROVIDERS, instances_admises=[]) == set()


# ── R1 / R3 : clés disjointes → parallèle ─────────────────────────────────────


def test_R1_R3_cles_disjointes_parallele(experiences_dir):
    a = _execution(experiences_dir, "A")
    b = _execution(experiences_dir, "B")
    assert R.reserver({"mistral"}, a.dossier, "A") is True
    assert R.reserver({"cerebras"}, b.dossier, "B") is True
    assert R.cles_reservees() == {"mistral", "cerebras"}
    assert {e["exp"] for e in R.actives()} == {"A", "B"}


# ── R2 / R6 : clé commune → file, admission atomique ──────────────────────────


def test_R2_cle_commune_met_en_file(experiences_dir):
    a = _execution(experiences_dir, "A")
    b = _execution(experiences_dir, "B")
    assert R.admettre({"google"}, a.dossier, "A") == "lance"
    assert R.admettre({"google"}, b.dossier, "B") == "file"
    assert [e["exp"] for e in R.lister_file()] == ["B"]
    assert R.reserver({"google"}, b.dossier, "B") is False


def test_R6_admission_atomique_concurrente(experiences_dir):
    execs = [_execution(experiences_dir, f"E{i}") for i in range(12)]

    def tenter(ex):
        return R.reserver({"google"}, ex.dossier, ex.dossier.name)

    with ThreadPoolExecutor(max_workers=12) as pool:
        gagnants = list(pool.map(tenter, execs))
    assert gagnants.count(True) == 1  # exactement un réserve la clé partagée


def test_R2b_promotion_fifo_a_la_liberation(experiences_dir):
    a = _execution(experiences_dir, "A")
    b = _execution(experiences_dir, "B")
    c = _execution(experiences_dir, "C")
    assert R.admettre({"google"}, a.dossier, "A") == "lance"
    assert R.admettre({"google"}, b.dossier, "B") == "file"
    assert R.admettre({"google"}, c.dossier, "C") == "file"
    # Rien n'est prêt tant que A tient la clé.
    assert R.promouvoir_pretes() == []
    R.liberer(a.dossier)
    promues = R.promouvoir_pretes()
    assert [e["exp"] for e in promues] == ["B"]  # FIFO : B avant C
    assert [e["exp"] for e in R.lister_file()] == ["C"]


def test_R2e_retrait_de_la_file(experiences_dir):
    a = _execution(experiences_dir, "A")
    b = _execution(experiences_dir, "B")
    R.admettre({"google"}, a.dossier, "A")
    R.admettre({"google"}, b.dossier, "B")
    assert R.retirer_file("B") is True
    assert R.lister_file() == []
    R.liberer(a.dossier)
    assert R.promouvoir_pretes() == []  # B retirée : jamais promue


# ── R7 : réconciliation d'un fantôme (pid mort) ───────────────────────────────


def test_R7_pid_mort_reconcilie_et_libere(experiences_dir):
    a = _execution(experiences_dir, "A")
    a.changer_etat(ETAT_EN_COURS)
    pid_mort = 2**31 - 1  # certainement absent
    assert R.reserver({"google"}, a.dossier, "A", pid=pid_mort) is True
    liberees = R.reconcilier()
    assert liberees == ["google"]
    assert R.cles_reservees() == set()
    assert Execution.ouvrir(a.dossier).etat()["etat"] == ETAT_INTERROMPUE


# ── R8 : jeu de clés vide toujours admis ──────────────────────────────────────


def test_R8_jeu_vide_toujours_lance(experiences_dir):
    a = _execution(experiences_dir, "A")
    b = _execution(experiences_dir, "B")
    R.reserver({"google"}, a.dossier, "A")
    assert (
        R.admettre(set(), b.dossier, "B") == "lance"
    )  # aucune clé → jamais en conflit


# ── R5 : arrêt des services conditionné à l'absence d'expérience active ────────


def test_R5_actives_est_vide_code_retour(experiences_dir):
    import argparse

    from experiences.cli import cmd_actives

    # Rien d'actif → code 0 (les services partagés sont arrêtables).
    assert cmd_actives(argparse.Namespace(est_vide=True)) == 0
    a = _execution(experiences_dir, "A")
    R.reserver({"google"}, a.dossier, "A")
    # Une expérience tient une clé → code 1 (laisser les services up).
    assert cmd_actives(argparse.Namespace(est_vide=True)) == 1


# ── R11 : aucune valeur de secret dans le registre ────────────────────────────


def test_R11_registre_sans_secret(experiences_dir):
    a = _execution(experiences_dir, "A")
    R.reserver({"google", "mistral"}, a.dossier, "A")
    for entree in R.actives():
        # Seules l'identité de clé (adapter) et des métadonnées non sensibles circulent.
        assert set(entree) == {"execution", "exp", "cles"}
        assert entree["cles"] == ["google", "mistral"]
