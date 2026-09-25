"""Tests du suivi des expériences mémoire et de leurs logs dans l'onglet 📟 Activités en cours.

Vérifie :
1. La détection des exécutions mémoire en cours, suspendues et terminées.
2. Le calcul d'avancement (branche A/B, jours simulés, pourcentage).
3. L'extraction du log d'exécution pour la mémoire et les expériences classiques.
4. Le rendu Streamlit des composants mémoire (barre de progression, fiche de modèles, log, bouton arrêt/reprendre).
5. La résolution du modèle de décision dans _job_decideur pour les cibles mémoire.
6. Les métadonnées des cibles make mémoire dans makefiles.py.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "services" / "llm-agents"))

from experiences import memoire as service_memoire  # noqa: E402
from scripts.dashboard import app, experiences, makefiles, memoire as dash_memoire, runner  # noqa: E402


class FauxSt:
    """Simulateur Streamlit léger pour capturer les éléments affichés."""

    def __init__(self):
        self.barres: list[tuple[float, str]] = []
        self.textes: list[str] = []
        self.boutons: list[str] = []
        self.legendes: list[str] = []
        self.codes: list[tuple[str, str]] = []
        self.toasts: list[str] = []
        self.expanders: list[str] = []

    def progress(self, valeur: float, text: str = ""):
        self.barres.append((valeur, text))

    def markdown(self, texte: str):
        self.textes.append(texte)

    def caption(self, texte: str, **_k):
        self.legendes.append(texte)

    def code(self, texte: str, language: str = ""):
        self.codes.append((texte, language))

    def columns(self, spec, **_k):
        largeur = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
        return [self] * largeur

    def button(self, label: str, **_k):
        self.boutons.append(label)
        return False

    def toast(self, message: str, **_k):
        self.toasts.append(message)

    def expander(self, label: str, **_k):
        self.expanders.append(label)
        return self

    def container(self, **_k):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.fixture
def dossier_memoire_test(tmp_path, monkeypatch):
    """Crée un environnement isolé data/experiences_memoire/ et experiments/."""
    d_mem = tmp_path / "data" / "experiences_memoire"
    d_mem.mkdir(parents=True)
    d_exp = tmp_path / "experiments"
    d_exp.mkdir(parents=True)

    monkeypatch.setattr(service_memoire, "DOSSIER_MEMOIRE", d_mem)
    monkeypatch.setattr(service_memoire, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(dash_memoire, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(app, "REPO_ROOT", tmp_path)
    return tmp_path, d_mem, d_exp


def test_detection_activites_memoire_en_cours(dossier_memoire_test):
    """Une expérience mémoire avec etat='en_cours' et modifiée récemment est détectée."""
    tmp_path, d_mem, d_exp = dossier_memoire_test

    nom_exp = "exp_mem_choc_c1_gem38f_899549_42j"
    dir_exp = d_mem / nom_exp
    dir_exp.mkdir()

    cfg = {
        "nom": nom_exp,
        "canal": "vecu",
        "evenement": "c1_bouchon_rocade",
        "horizon_jours": 42,
        "population": "899549",
        "modeles": {
            "itinary_multi_agent": "gemini-3.8-flash",
            "evenement_jugement": "gemini-3.8-flash",
            "stm_reflection": "gemini-3.8-flash",
        },
    }
    (dir_exp / "experience_memoire.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")

    etat_data = {
        "nom": nom_exp,
        "etat": "en_cours",
        "branche_active": "treated",
        "debut": "2026-09-25T06:00:00+00:00",
        "traite": {"etat": "en_cours", "debut": "2026-09-25T06:00:00+00:00"},
        "temoin": {"etat": "en_attente"},
    }
    (dir_exp / "etat.json").write_text(json.dumps(etat_data), encoding="utf-8")

    # Simulation d'un current run avec checkpoints
    archive_dir = d_exp / "archive" / "2026-09-25_06_00"
    archive_dir.mkdir(parents=True)
    for j in range(1, 11):
        (archive_dir / f"population_1_checkpoint_2026-03-{16+j}.json").write_text("{}", encoding="utf-8")
    (archive_dir / "app.log").write_text("[sync] END sim_time=26 March 2026, 20:00 state_update\n", encoding="utf-8")

    link_current = d_exp / "current"
    link_current.symlink_to(archive_dir)

    runs_dir = d_exp / "runs" / f"{nom_exp}_treated"
    runs_dir.mkdir(parents=True)

    en_cours = service_memoire.activites_en_cours()
    assert len(en_cours) == 1, en_cours
    act = en_cours[0]
    assert act["nom"] == nom_exp
    assert act["canal"] == "vecu"
    assert act["modele_decision"] == "gemini-3.8-flash"

    prog = act["progression"]
    assert prog["branche"] == "treated"
    assert "A (Traité)" in prog["branche_label"]
    assert prog["jours_faits"] == 10
    assert prog["horizon_jours"] == 42
    assert abs(prog["pourcent"] - (10 / 42 * 100)) < 1e-4
    assert "26 March 2026" in prog["derniere_journee"]
    assert "26 March 2026" in act["log_tail"]


def test_rendre_activites_memoire_streamlit(dossier_memoire_test):
    """Le composant rendre_activites dessine la barre, les détails, le stop et le log."""
    st = FauxSt()
    activites = [
        {
            "nom": "exp_mem_test_42j",
            "canal": "vecu",
            "evenement": "c1_bouchon",
            "modele_decision": "gemini-3.8-flash",
            "modele_jugement": "gemini-3.8-flash",
            "modele_stm": "gemini-3.8-flash",
            "population": "899549",
            "progression": {
                "branche_label": "A (Traité)",
                "jours_faits": 14,
                "horizon_jours": 42,
                "pourcent": 33.3,
                "derniere_journee": "30 March 2026",
                "ecoule_s": 1200.0,
            },
            "log_tail": "2026-09-25 07:00:00 | INFO | decision ok",
            "log_src": "experiments/current/app.log",
        }
    ]

    dash_memoire.rendre_activites(st, activites)

    # 1 barre de progression
    assert len(st.barres) == 1
    val, txt = st.barres[0]
    assert abs(val - 0.333) < 0.01
    assert "exp_mem_test_42j" in txt
    assert "Bras A (Traité) en cours" in txt
    assert "14 / 42 j" in txt

    # Fiche de modèles et temps
    legendes_jointes = " ".join(st.legendes)
    assert "gemini-3.8-flash" in legendes_jointes
    assert "30 March 2026" in legendes_jointes
    assert "en cours depuis 20 min" in legendes_jointes

    # Bouton stop
    assert any("Arrêter" in b for b in st.boutons)

    # Expander de log avec le contenu du log
    assert any("Journal du run mémoire" in exp for exp in st.expanders)
    assert any("decision ok" in code for code, _ in st.codes)


def test_interrompues_et_terminees_memoire(dossier_memoire_test):
    """Les expériences suspendues/arrêtées et terminées sont bien identifiées."""
    tmp_path, d_mem, _ = dossier_memoire_test

    # 1. Expérience suspendue
    dir_susp = d_mem / "exp_mem_suspendue"
    dir_susp.mkdir()
    (dir_susp / "experience_memoire.yaml").write_text("nom: exp_mem_suspendue\n", encoding="utf-8")
    (dir_susp / "etat.json").write_text(json.dumps({
        "nom": "exp_mem_suspendue",
        "etat": "suspendue",
        "note": "Quota journalier épuisé",
    }), encoding="utf-8")

    # 2. Expérience terminée
    dir_term = d_mem / "exp_mem_terminee"
    dir_term.mkdir()
    (dir_term / "experience_memoire.yaml").write_text("nom: exp_mem_terminee\n", encoding="utf-8")
    (dir_term / "etat.json").write_text(json.dumps({
        "nom": "exp_mem_terminee",
        "etat": "terminee",
        "traite": {"etat": "ok"},
        "temoin": {"etat": "ok"},
    }), encoding="utf-8")
    (dir_term / "traite").mkdir()
    (dir_term / "temoin").mkdir()
    (dir_term / "traite" / "moves.csv").write_text("a,b\n", encoding="utf-8")
    (dir_term / "temoin" / "moves.csv").write_text("a,b\n", encoding="utf-8")

    inter = service_memoire.interrompues()
    assert len(inter) == 1
    assert inter[0]["nom"] == "exp_mem_suspendue"
    assert inter[0]["cause_icone"] == "⏸"
    assert "Quota journalier épuisé" in inter[0]["cause_detail"]

    term = service_memoire.terminees()
    assert len(term) == 1
    assert term[0]["nom"] == "exp_mem_terminee"

    # Vérification du rendu des reprenables avec bouton Reprendre
    st = FauxSt()
    lances = []
    dash_memoire.rendre_reprenables(st, inter, lancer=lambda cible, val: lances.append((cible, val)))
    assert any("exp_mem_suspendue" in t for t in st.textes)
    assert any("Reprendre" in b for b in st.boutons)

    # Vérification du rendu des terminées
    st_term = FauxSt()
    dash_memoire.rendre_terminees(st_term, term)
    assert any("exp_mem_terminee" in t for t in st_term.textes)


def test_job_decideur_memoire(dossier_memoire_test):
    """_job_decideur extrait le modèle de décision depuis experience_memoire.yaml."""
    tmp_path, d_mem, _ = dossier_memoire_test
    nom_exp = "exp_mem_test_job"
    dir_exp = d_mem / nom_exp
    dir_exp.mkdir()
    cfg = {
        "nom": nom_exp,
        "modeles": {"itinary_multi_agent": "gemini-3.1-flash-lite"},
    }
    (dir_exp / "experience_memoire.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")

    class FauxJob:
        def __init__(self, label: str, argv: list[str]):
            self.label = label
            self.argv = argv

    job_mem = FauxJob("root:experience-memoire-lancer", ["make", "experience-memoire-lancer", f"EXP={nom_exp}"])
    decideur = app._job_decideur(job_mem)
    assert "gemini-3.1-flash-lite" in decideur
    assert "mémoire" in decideur

    job_nuit = FauxJob("root:experience-memoire-nuit", ["make", "experience-memoire-nuit"])
    assert "campagne mémoire" in app._job_decideur(job_nuit)


def test_makefiles_meta_cibles_memoire():
    """Les cibles make mémoire sont déclarées avec leurs drapeaux (long, llm) dans makefiles.py."""
    meta = makefiles._META
    assert ("root", "experience-memoire-lancer") in meta
    groupe, flags, vars_opt = meta[("root", "experience-memoire-lancer")]
    assert groupe == "Expériences Mémoire"
    assert "long" in flags
    assert "llm" in flags
    assert "EXP" in vars_opt

    assert ("root", "experience-memoire-nuit") in meta
    groupe_n, flags_n, _ = meta[("root", "experience-memoire-nuit")]
    assert "long" in flags_n
    assert "llm" in flags_n


def test_classic_experience_a_un_volet_log(tmp_path):
    """Une exécution classique dispose désormais d'un expander log dans rendre_activites."""
    st = FauxSt()
    exp_dir = tmp_path / "exp_classique" / "executions" / "exec_1"
    exp_dir.mkdir(parents=True)
    (exp_dir / "execution.log").write_text("ligne 1\nligne 2\nligne 3\n", encoding="utf-8")

    act = {
        "executions": [
            {
                "experience": "exp_classique",
                "execution": "exec_1",
                "dossier": str(exp_dir),
                "fournisseur": "google",
                "faits": 50,
                "total": 100,
                "pourcent": 50.0,
                "personnes": 10,
                "personnes_terminees": 5,
                "conditions": "sans conditions",
            }
        ],
        "jeux": [],
        "definies": 1,
        "terminees": 0,
    }

    experiences.rendre_activites(st, act, compact=False)
    # L'expander de log doit être présent
    assert any("Journal d'exécution" in exp for exp in st.expanders)
    # Le contenu du log doit avoir été extrait
    assert any("ligne 3" in code for code, _ in st.codes)
