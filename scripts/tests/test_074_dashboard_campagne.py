"""Ticket 074, lot E — l'onglet « 🔁 Campagne » du tableau de bord.

Ce volet répond à une seule question — **qu'est-ce qui reste, et quand ça reprend** — et ces
tests vérifient qu'il y répond sans mentir :

- il lit l'avancement **sur le disque**, jamais recalculé : deux sources de vérité pour un
  même chiffre finissent toujours par diverger ;
- il rend les noms calculés **lisibles** depuis leur définition, pas en redécoupant le nom ;
- il **ne fait pas disparaître l'onglet voisin** quand il tombe (E-5, précédent documenté
  dans `app.py` sur `tickets_status.yaml`).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
import yaml

os.environ.setdefault("DASHBOARD_EAGER", "1")

REPO_ROOT = Path(__file__).resolve().parents[2]
# `scripts/tests` se lance aussi bien depuis la racine que depuis `scripts/` : dans le
# second cas la racine n'est pas sur sys.path, et `scripts.dashboard` reste introuvable.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.dashboard import campagne as C  # noqa: E402


# ── Banc ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def banc(tmp_path, monkeypatch):
    campagnes = tmp_path / "campagnes"
    experiences = tmp_path / "data" / "experiences"
    campagnes.mkdir(parents=True)
    experiences.mkdir(parents=True)
    monkeypatch.setattr(C, "DOSSIER_CAMPAGNES", campagnes)
    monkeypatch.setattr(C, "DOSSIER_EXPERIENCES", experiences)
    return {"campagnes": campagnes, "experiences": experiences}


def _definir(banc, nom: str, **champs) -> None:
    d = banc["experiences"] / nom
    d.mkdir(parents=True, exist_ok=True)
    doc = {
        "nom": nom,
        "population": {"chemin": "/data/eqasim-output/population_1000_AAMAS_v6"},
        "jeu": {"nom": "population_1000_AAMAS_v6_20260316_EN"},
        "mode": "sans_simulateur",
        **champs,
    }
    (d / "experience.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")


def _etat(banc, nom: str, etat: str, *, horodatage="2026-09-14_10_00_00", raison=None) -> None:
    d = banc["experiences"] / nom / "executions" / horodatage
    d.mkdir(parents=True, exist_ok=True)
    (d / "etat.json").write_text(
        json.dumps({"etat": etat, "raison": raison, "maj": "2026-09-14T10:00:00+00:00"}),
        encoding="utf-8")


@pytest.fixture
def campagne(banc):
    for n in ("t1", "t2"):
        _definir(banc, n, decideur={"type": "aleatoire"})
    for n in ("llm1",):
        _definir(banc, n, decideur={"type": "passerelle", "modele": "gemini-3.1-flash-lite",
                                    "parametres": {"temperature": 0.0}},
                 gabarit={"categorie": "itinary_multi_agent", "variante": "prompt_expert_04"})
    (banc["campagnes"] / "c.yaml").write_text(yaml.safe_dump({
        "nom": "c", "version": "campagne1",
        "note": "une note",
        "substrat": {"population": "data/population/population_1000_AAMAS_v6"},
        "phases": [
            {"nom": "temoins", "raison": "gratuits", "experiences": ["t1", "t2"]},
            {"nom": "llm", "experiences": ["llm1"]},
        ]}, allow_unicode=True), encoding="utf-8")
    return banc


# ── Lecture ──────────────────────────────────────────────────────────────────


class TestLecture:
    def test_sans_campagne_la_liste_est_vide_pas_en_erreur(self, banc):
        assert C.campagnes_connues() == []

    def test_les_campagnes_sont_listees_par_nom_de_fichier(self, campagne):
        assert C.campagnes_connues() == ["c"]

    def test_la_vue_compte_les_faites_par_phase(self, campagne):
        _etat(campagne, "t1", "terminee")
        v = C.vue("c")
        assert v["total"] == 3 and v["faites"] == ["t1"]
        assert v["phases"][0]["faites"] == ["t1"]
        assert v["phases"][1]["faites"] == []

    def test_une_campagne_jamais_lancee_a_un_pilote_vide(self, campagne):
        v = C.vue("c")
        assert v["pilote"] == {} and v["lisible"] is True

    def test_un_yaml_illisible_ne_leve_pas_mais_le_dit(self, banc):
        (banc["campagnes"] / "c.yaml").write_text("[: pas du yaml", encoding="utf-8")
        assert C.vue("c")["lisible"] is False

    def test_une_experience_jamais_lancee_est_definie(self, campagne):
        assert C.etat_execution("t1")["etat"] == "definie"

    def test_l_etat_lu_est_celui_de_la_DERNIERE_execution(self, campagne):
        _etat(campagne, "t1", "arretee", horodatage="2026-09-14_09_00_00")
        _etat(campagne, "t1", "terminee", horodatage="2026-09-14_11_00_00")
        assert C.etat_execution("t1")["etat"] == "terminee"

    def test_une_execution_sans_etat_ecrit_est_en_cours_pas_faite(self, campagne):
        """Le dossier existe, `etat.json` pas encore : c'est un démarrage, pas un succès."""
        (campagne["experiences"] / "t1" / "executions" / "2026-09-14_12_00_00").mkdir(parents=True)
        assert C.etat_execution("t1")["etat"] == "en_cours"


# ── Libellés ─────────────────────────────────────────────────────────────────


class TestLibelle:
    def test_un_bras_llm_dit_son_modele_son_prompt_et_sa_cohorte(self, campagne):
        lu = C.libelle("llm1")
        assert "gemini-3.1-flash-lite" in lu
        assert "prompt_expert_04" in lu
        assert "population_1000_AAMAS_v6" in lu

    def test_un_temoin_dit_ce_qu_il_fait(self, campagne):
        assert "aléatoire" in C.libelle("t1")

    def test_un_decideur_inconnu_garde_son_nom_plutot_que_de_disparaitre(self, banc):
        _definir(banc, "x", decideur={"type": "chose_nouvelle"})
        assert "chose_nouvelle" in C.libelle("x")

    def test_sans_definition_le_nom_brut_est_rendu_tel_quel(self, banc):
        assert C.libelle("exp_inconnue") == "exp_inconnue"

    def test_la_chaine_coupee_se_voit_dans_le_libelle(self, banc):
        _definir(banc, "x", decideur={"type": "aleatoire"},
                 vehicule_chaine=False, verrou_retour=False)
        lu = C.libelle("x")
        assert "chaîne des véhicules coupée" in lu and "verrou de retour coupé" in lu


# ── Quota ────────────────────────────────────────────────────────────────────


class TestQuota:
    def test_le_prochain_renouvellement_est_futur_et_dans_les_24h(self):
        quand, secondes = C.secondes_avant_renouvellement()
        assert quand.endswith("+00:00")
        assert 0 < secondes <= 24 * 3600, "une fenêtre de quota fait au plus 24 h"


# ── E-1 / E-2 / E-5 : le câblage dans l'application ──────────────────────────


class TestCablage:
    def _source(self) -> str:
        return (REPO_ROOT / "scripts" / "dashboard" / "app.py").read_text(encoding="utf-8")

    def test_l_onglet_est_declare_avec_son_slug(self):
        assert '("campagne", "🔁 Campagne")' in self._source()

    def test_l_onglet_est_rendu_paresseusement(self):
        assert '_should_render("campagne")' in self._source()

    def test_le_rendu_est_garde_par_un_except(self):
        """E-5 : sans cette garde, une faute de frappe ici ferait disparaître l'onglet voisin."""
        src = self._source()
        bloc = src[src.index("with tab_campagne:"):src.index("with tab_travaux:")]
        assert "try:" in bloc and "except Exception" in bloc
        assert "campagne.render(" in bloc

    def test_le_module_est_importe(self):
        assert "import campagne, experiences" in self._source()
