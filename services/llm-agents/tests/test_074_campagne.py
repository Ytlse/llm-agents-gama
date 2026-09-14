"""Ticket 074, lot D — la campagne mène 22 expériences au bout, à travers les quotas.

Ce qui est vérifié ici n'est pas « le code tourne » mais les quatre promesses qui font qu'une
campagne vaut mieux qu'un humain qui relance :

1. elle **refuse** plutôt que de démarrer sur une définition qui la ferait échouer au milieu ;
2. elle respecte l'**ordre des phases** — les témoins gratuits avant le quota ;
3. elle **reprend là où elle s'est arrêtée**, jamais au début, même après un redémarrage ;
4. elle **dit** ce qu'elle fait — succès, échecs, sommeils — avec les alarmes de la doctrine.

Le temps est INJECTÉ (`dormir`, `max_tours`). Une boucle qu'on ne teste qu'en attendant
vraiment trente secondes n'est pas testée : elle est seulement lente à ne pas l'être.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from loguru import logger
from experiences import campagne as C

# ── Banc ─────────────────────────────────────────────────────────────────────


def _definir_experience(racine: Path, nom: str) -> Path:
    """Une définition minimale : la campagne ne lit que son existence."""
    d = racine / nom
    d.mkdir(parents=True, exist_ok=True)
    (d / "experience.yaml").write_text(yaml.safe_dump({"nom": nom}), encoding="utf-8")
    return d


def _poser_etat(
    racine: Path,
    nom: str,
    etat: str,
    *,
    horodatage: str = "2026-09-14_10_00_00",
    raison: str | None = None,
) -> None:
    d = racine / nom / "executions" / horodatage
    d.mkdir(parents=True, exist_ok=True)
    (d / "etat.json").write_text(
        json.dumps(
            {"etat": etat, "raison": raison, "maj": "2026-09-14T10:00:00+00:00"}
        ),
        encoding="utf-8",
    )


@pytest.fixture
def journal():
    """Les messages de loguru, que `caplog` ne voit pas (il n'écoute que `logging`)."""
    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(str(m)), level="INFO")
    try:
        yield messages
    finally:
        logger.remove(sink)


@pytest.fixture
def banc(tmp_path, monkeypatch):
    """Un dépôt de poche : des expériences définies, un dossier de campagnes, aucun Docker."""
    experiences = tmp_path / "experiences"
    campagnes = tmp_path / "campagnes"
    experiences.mkdir()
    campagnes.mkdir()
    monkeypatch.setenv("EXPERIENCES_DIR", str(experiences))
    monkeypatch.setenv("CAMPAGNES_DIR", str(campagnes))

    lances: list[str] = []
    monkeypatch.setattr(C, "_lancer_experience", lances.append)
    monkeypatch.setattr(C, "_tour_ordonnanceur", lambda: None)
    return {"experiences": experiences, "campagnes": campagnes, "lances": lances}


def _ecrire_campagne(banc, nom: str, phases: list[dict], **extra) -> None:
    doc = {"nom": nom, "version": C.VERSION_CAMPAGNE, "phases": phases, **extra}
    (banc["campagnes"] / f"{nom}.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


@pytest.fixture
def deux_phases(banc):
    for n in ("t1", "t2", "llm1", "llm2"):
        _definir_experience(banc["experiences"], n)
    _ecrire_campagne(
        banc,
        "c",
        [
            {"nom": "temoins", "raison": "gratuits", "experiences": ["t1", "t2"]},
            {"nom": "llm", "experiences": ["llm1", "llm2"]},
        ],
    )
    return banc


# ── 1. Elle refuse plutôt que d'échouer au milieu ────────────────────────────


class TestRefus:
    def test_une_campagne_absente_dit_lesquelles_existent(self, banc):
        _ecrire_campagne(banc, "reelle", [{"nom": "p", "experiences": ["x"]}])
        _definir_experience(banc["experiences"], "x")
        with pytest.raises(C.CampagneInvalide, match="reelle"):
            C.charger("fantome")

    def test_une_version_inattendue_est_refusee(self, banc):
        (banc["campagnes"] / "c.yaml").write_text(
            yaml.safe_dump(
                {
                    "nom": "c",
                    "version": "campagne0",
                    "phases": [{"nom": "p", "experiences": ["x"]}],
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(C.CampagneInvalide, match="campagne0"):
            C.charger("c")

    def test_une_experience_inexistante_est_refusee_AVANT_de_depenser(self, banc):
        _definir_experience(banc["experiences"], "existe")
        _ecrire_campagne(banc, "c", [{"nom": "p", "experiences": ["existe", "manque"]}])
        with pytest.raises(C.CampagneInvalide, match="manque"):
            C.charger("c")

    def test_une_phase_vide_est_refusee(self, banc):
        _ecrire_campagne(banc, "c", [{"nom": "vide", "experiences": []}])
        with pytest.raises(C.CampagneInvalide, match="aucune expérience"):
            C.charger("c")

    def test_une_experience_dans_deux_phases_est_refusee(self, banc):
        _definir_experience(banc["experiences"], "x")
        _ecrire_campagne(
            banc,
            "c",
            [{"nom": "a", "experiences": ["x"]}, {"nom": "b", "experiences": ["x"]}],
        )
        with pytest.raises(C.CampagneInvalide, match="deux phases"):
            C.charger("c")


# ── 2. L'ordre des phases ────────────────────────────────────────────────────


class TestPhases:
    def test_la_phase_2_ne_demarre_pas_avant_la_fin_de_la_phase_1(self, deux_phases):
        C.lancer("c", max_tours=3, dormir=lambda _s: None)
        # Une seule expérience en vol à la fois, et c'est une expérience de la phase 1.
        assert deux_phases["lances"] == ["t1"], deux_phases["lances"]

    def test_la_phase_2_demarre_quand_la_phase_1_est_close(self, deux_phases):
        for n in ("t1", "t2"):
            _poser_etat(deux_phases["experiences"], n, "terminee")
        C.lancer("c", max_tours=4, dormir=lambda _s: None)
        assert deux_phases["lances"] == ["llm1"], deux_phases["lances"]
        etat = C.lire_etat("c")
        assert etat["phase_courante"] == "llm"
        assert set(etat["faites"]) == {"t1", "t2"}

    def test_une_campagne_toute_faite_se_declare_terminee(self, deux_phases):
        for n in ("t1", "t2", "llm1", "llm2"):
            _poser_etat(deux_phases["experiences"], n, "terminee")
        assert C.lancer("c", max_tours=10, dormir=lambda _s: None) == 0
        etat = C.lire_etat("c")
        assert etat["terminee_le"]
        assert len(etat["faites"]) == 4 and not etat["restantes"]
        assert deux_phases["lances"] == []


# ── 3. La reprise ────────────────────────────────────────────────────────────


class TestReprise:
    def test_elle_reprend_ou_elle_en_etait_pas_au_debut(self, deux_phases):
        """La promesse D-3, et la seule qui compte quand un sommeil dure la nuit."""
        _poser_etat(deux_phases["experiences"], "t1", "terminee")
        C.lancer("c", max_tours=2, dormir=lambda _s: None)
        assert deux_phases["lances"] == ["t2"]

        # Redémarrage : l'état est relu sur le disque, t1 n'est pas rejouée.
        deux_phases["lances"].clear()
        C.lancer("c", max_tours=2, dormir=lambda _s: None)
        assert "t1" not in deux_phases["lances"]

    def test_une_execution_interrompue_est_reprise(self, deux_phases):
        _poser_etat(
            deux_phases["experiences"], "t1", "interrompue", raison="processus mort"
        )
        C.lancer("c", max_tours=2, dormir=lambda _s: None)
        assert "t1" in deux_phases["lances"]

    def test_recommencer_ignore_l_etat_existant(self, deux_phases):
        C.ecrire_etat(
            "c",
            {
                **C.etat_par_defaut(C.charger("c")),
                "faites": ["t1", "t2"],
                "phase_courante": "llm",
            },
        )
        C.lancer("c", reprendre=False, max_tours=2, dormir=lambda _s: None)
        assert C.lire_etat("c")["phase_courante"] == "temoins"

    def test_l_etat_survit_a_un_json_tronque(self, deux_phases):
        (deux_phases["campagnes"] / "c").mkdir(parents=True, exist_ok=True)
        (deux_phases["campagnes"] / "c" / "etat.json").write_text(
            "{tronqué", encoding="utf-8"
        )
        assert C.lire_etat("c") is None  # dit, et repart de zéro — sans lever


# ── 4. Échecs, arrêt, sommeil ────────────────────────────────────────────────


class TestEchecsEtSommeil:
    def test_deux_echecs_de_suite_alarment_et_la_campagne_continue(
        self, deux_phases, caplog
    ):
        _poser_etat(deux_phases["experiences"], "t1", "arretee", raison="clé absente")
        import logging

        with caplog.at_level(logging.ERROR):
            C.lancer("c", max_tours=4, dormir=lambda _s: None)
        etat = C.lire_etat("c")
        assert "t1" in etat["echouees"]
        assert etat["echouees"]["t1"]["tentatives"] > C.TENTATIVES_MAX
        # Et la suivante part quand même : un échec n'annule pas le reste.
        assert "t2" in deux_phases["lances"]

    def test_un_arret_pose_PENDANT_la_boucle_sort_en_130(self, deux_phases):
        """Un arrêt demandé en cours de route est honoré au tour suivant."""

        def dormir_puis_arreter(_s):
            C.arreter("c")

        assert C.lancer("c", max_tours=5, dormir=dormir_puis_arreter) == 130
        # Une seule expérience a été lancée : l'arrêt a empêché la suite.
        assert deux_phases["lances"] == ["t1"], deux_phases["lances"]

    def test_lancer_leve_un_arret_precedent(self, deux_phases):
        C.arreter("c")
        assert C.demande_arret("c")
        C.lancer("c", max_tours=1, dormir=lambda _s: None)
        assert not C.demande_arret("c")

    def test_tout_en_attente_de_quota_met_la_campagne_en_sommeil(
        self, deux_phases, monkeypatch
    ):
        _poser_etat(deux_phases["experiences"], "t1", "en_attente_quota")
        _poser_etat(deux_phases["experiences"], "t2", "en_attente_quota")
        dormi: list[float] = []
        C.lancer("c", max_tours=2, dormir=dormi.append)
        etat = C.lire_etat("c")
        assert etat["sommeils"], "un sommeil doit être consigné, pas subi en silence"
        assert etat["sommeils"][0]["jusqu"], "l'heure de réveil doit être écrite"
        assert dormi and dormi[0] > 0

    def test_une_seule_en_attente_ne_met_PAS_la_campagne_en_sommeil(self, deux_phases):
        """Le piège : dormir parce qu'UNE exécution dort gèlerait la campagne pour rien."""
        _poser_etat(deux_phases["experiences"], "t1", "en_attente_quota")
        _poser_etat(deux_phases["experiences"], "t2", "en_cours")
        C.lancer("c", max_tours=2, dormir=lambda _s: None)
        assert not (C.lire_etat("c")["sommeils"])

    def test_un_sommeil_trop_long_leve_une_alarme(
        self, deux_phases, monkeypatch, journal
    ):
        monkeypatch.setattr(
            C,
            "prochain_reveil",
            lambda *a, **k: ("2026-09-17T00:00:00+00:00", 40 * 3600),
        )
        _poser_etat(deux_phases["experiences"], "t1", "en_attente_quota")
        _poser_etat(deux_phases["experiences"], "t2", "en_attente_quota")
        C.lancer("c", max_tours=3, dormir=lambda _s: None)
        assert sum("[ALARME]" in m and "24" in m for m in journal) == 1, \
            "une alarme par sommeil, pas une par tour"


# ── Lecture ──────────────────────────────────────────────────────────────────


class TestLecture:
    def test_etat_lisible_ne_leve_pas_sur_une_campagne_jamais_lancee(self, deux_phases):
        vue = C.etat_lisible("c")
        assert vue["etat"] is None and vue["total"] == 4 and vue["faites"] == []
        assert [p["nom"] for p in vue["phases"]] == ["temoins", "llm"]

    def test_etat_lisible_compte_les_faites_par_phase(self, deux_phases):
        _poser_etat(deux_phases["experiences"], "t1", "terminee")
        vue = C.etat_lisible("c")
        assert vue["phases"][0]["faites"] == ["t1"]
        assert vue["faites"] == ["t1"]

    def test_une_experience_jamais_lancee_est_definie_pas_echouee(self, deux_phases):
        assert C.etat_experience("t1")["etat"] == "definie"

    def test_la_derniere_execution_est_la_plus_recente(self, deux_phases):
        _poser_etat(
            deux_phases["experiences"],
            "t1",
            "arretee",
            horodatage="2026-09-14_09_00_00",
        )
        _poser_etat(
            deux_phases["experiences"],
            "t1",
            "terminee",
            horodatage="2026-09-14_11_00_00",
        )
        assert C.etat_experience("t1")["etat"] == "terminee"

    def test_prochain_reveil_rend_une_date_future_et_ses_secondes(self):
        quand, secondes = C.prochain_reveil()
        assert quand.endswith("+00:00") and 0 < secondes <= 24 * 3600
