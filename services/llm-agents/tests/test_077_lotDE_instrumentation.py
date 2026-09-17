"""Ticket 077, lots D2 et E — concentration des rappels, et l'instrumentation du prochain run.

Contrat : `specs/ticket_077/tests.md` § D et § E.

Le run de trente jours du 075 ne permet pas de dire si la mémoire change les décisions : les
scores du rappel ne sont écrits nulle part, l'index retenu n'existe que pour 66 trajets sur 514,
et une décision servie par le cache est indiscernable d'un appel direct.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from llm import trace_rappel
from llm.trace_rappel import (
    SEUIL_CONCENTRATION_BAS,
    SEUIL_CONCENTRATION_HAUT,
    TETE_CONCENTRATION,
    tracer_rappel,
)
from urban_mobility_agents.utils.move_logger import CSV_HEADERS, _options_descriptif


def _servi(doc_id: str, vivier: str = "A", memory_type: str = "concept"):
    return SimpleNamespace(
        metadata={"doc_id": doc_id, "vivier": vivier, "memory_type": memory_type}
    )


@pytest.fixture(autouse=True)
def _etat_propre():
    trace_rappel.reinitialiser()
    yield
    trace_rappel.reinitialiser()


class TestD2ConcentrationDesRappels:
    """D2 — le rappel s'auto-renforce ; la mesure doit le dire."""

    def test_D2_1_la_concentration_est_mesuree(self):
        """Les dix mêmes souvenirs servis en boucle, alors que d'autres étaient disponibles."""
        servis = [_servi(f"d{i}") for i in range(TETE_CONCENTRATION)]
        # Un vivier assez large pour que « les dix mêmes » soit un CHOIX, plus quelques
        # souvenirs servis une fois : sans eux, la mesure n'a pas de quoi se prononcer.
        for i in range(TETE_CONCENTRATION * 2):
            tracer_rappel("609", 1773637201, [_servi(f"rare{i}")], {}, candidats=40)
        for _ in range(60):
            tracer_rappel("609", 1773637201, servis, {}, candidats=40)
        etat = trace_rappel._ETATS["609"]
        concentration = etat.noter([], candidats=40)
        assert concentration is not None and concentration > 0.9, (
            f"dix souvenirs servis en boucle : la concentration doit être proche de 1 "
            f"(obtenu {concentration})"
        )

    def test_D2_2_l_alarme_est_sur_front_montant(self):

        from loguru import logger

        messages: list[str] = []
        sink = logger.add(lambda m: messages.append(m), level="ERROR")
        try:
            servis = [_servi(f"d{i}") for i in range(TETE_CONCENTRATION)]
            for i in range(TETE_CONCENTRATION * 2):
                tracer_rappel("609", 1773637201, [_servi(f"rare{i}")], {}, candidats=40)
            for _ in range(60):
                tracer_rappel("609", 1773637201, servis, {}, candidats=40)
        finally:
            logger.remove(sink)
        alarmes = [m for m in messages if "concentration des rappels" in m]
        assert len(alarmes) == 1, (
            f"l'alarme doit être levée UNE fois tant que le seuil reste franchi, "
            f"pas à chaque rappel — {len(alarmes)} levées"
        )
        assert "[ALARME]" in alarmes[0]

    def test_D2_3_le_retour_sous_le_seuil_bas_rearme(self):
        servis = [_servi(f"d{i}") for i in range(TETE_CONCENTRATION)]
        for i in range(TETE_CONCENTRATION * 2):
            tracer_rappel("609", 1773637201, [_servi(f"rare{i}")], {}, candidats=40)
        for _ in range(60):
            tracer_rappel("609", 1773637201, servis, {}, candidats=40)
        assert trace_rappel._ETATS["609"].en_alarme is True
        # Beaucoup de souvenirs DIFFÉRENTS : la tête ne pèse plus grand-chose.
        for i in range(400):
            tracer_rappel("609", 1773637201, [_servi(f"neuf{i}")], {}, candidats=40)
        assert trace_rappel._ETATS["609"].en_alarme is False

    def test_D2_4_un_agent_sans_rappel_ne_leve_rien(self):
        tracer_rappel("inconnu", None, [], {}, candidats=0)
        assert trace_rappel._ETATS["inconnu"].noter([], candidats=0) is None

    def test_D2_les_premiers_rappels_ne_declenchent_pas(self):
        """Une concentration de 1 sur douze rappels est le comportement NORMAL d'un début."""
        tracer_rappel("neuf", 1, [_servi("d1"), _servi("d2")], {}, candidats=2)
        assert trace_rappel._ETATS["neuf"].en_alarme is False

    def test_D2_un_rappel_sans_choix_ne_compte_pas(self):
        """Le faux positif trouvé en faisant tourner le module, le 2026-09-15.

        Au cinquième jour simulé, l'alarme s'est levée à 100 % pour quatre agents. Elle
        disait vrai et ne mesurait rien : un agent qui possède onze souvenirs et en sert dix
        les sert TOUS. La « concentration » ne mesurait que la taille de sa mémoire.
        """
        servis = [_servi(f"d{i}") for i in range(TETE_CONCENTRATION)]
        for _ in range(60):
            # Vivier de 10 candidats pour 10 servis : aucune sélection n'a eu lieu.
            tracer_rappel("jeune", 1773637201, servis, {}, candidats=TETE_CONCENTRATION)
        assert trace_rappel._ETATS["jeune"].en_alarme is False, (
            "un rappel qui sert tout ce qui existe n'est pas une concentration"
        )

    def test_D2_les_seuils_ont_une_hysteresis(self):
        assert SEUIL_CONCENTRATION_BAS < SEUIL_CONCENTRATION_HAUT, (
            "sans hystérésis, une valeur qui oscille autour du seuil inonde le journal"
        )


class TestE1TraceDesSouvenirsServis:
    """E1 — chaque souvenir servi est tracé avec son vivier, son score et son rang."""

    def test_E1_la_trace_porte_vivier_score_et_rang(self, tmp_path, monkeypatch):
        from settings import settings

        cible = tmp_path / "trace_rappel.jsonl"
        monkeypatch.setattr(settings.agent, "trace_rappel_enabled", True, raising=False)
        monkeypatch.setattr(settings.app, "trace_rappel_file", str(cible), raising=False)

        tracer_rappel(
            "609",
            1773637201,
            [_servi("d1", "A"), _servi("d2", "B"), _servi("d3", "C")],
            {"d1": 0.81, "d2": 0.42, "d3": 0.13},
            candidats=57,
        )
        import json

        ligne = json.loads(cible.read_text(encoding="utf-8").strip())
        assert ligne["person_id"] == "609"
        assert ligne["candidats"] == 57
        assert [s["rang"] for s in ligne["servis"]] == [0, 1, 2]
        assert [s["vivier"] for s in ligne["servis"]] == ["A", "B", "C"]
        assert ligne["servis"][0]["score"] == pytest.approx(0.81)

    def test_E7_eteinte_la_trace_n_ecrit_rien(self, tmp_path, monkeypatch):
        from settings import settings

        cible = tmp_path / "trace_rappel.jsonl"
        monkeypatch.setattr(settings.agent, "trace_rappel_enabled", False, raising=False)
        monkeypatch.setattr(settings.app, "trace_rappel_file", str(cible), raising=False)
        tracer_rappel("609", 1, [_servi("d1")], {"d1": 0.5}, candidats=1)
        assert not cible.exists()

    def test_la_trace_ne_leve_jamais(self, monkeypatch):
        from settings import settings

        monkeypatch.setattr(settings.agent, "trace_rappel_enabled", True, raising=False)
        monkeypatch.setattr(
            settings.app, "trace_rappel_file", "/interdit/trace.jsonl", raising=False
        )
        tracer_rappel("609", 1, [_servi("d1")], {"d1": 0.5}, candidats=1)


class TestE2E3E5ColonnesDeMoves:
    """E2, E3 et E5 — ce que `moves.csv` doit désormais porter."""

    def test_E2_index_retenu_et_options_presentees(self):
        assert "Index retenu" in CSV_HEADERS
        assert "Options présentées" in CSV_HEADERS

    def test_E5_origine_de_la_decision(self):
        assert "Origine de la décision" in CSV_HEADERS

    def test_E3_descriptif_des_options(self):
        assert "Options (descriptif)" in CSV_HEADERS

    def test_les_colonnes_sont_ajoutees_en_fin(self):
        """Aucun consommateur ne lit `moves.csv` par index, mais l'ordre reste une promesse."""
        anciennes = CSV_HEADERS[: CSV_HEADERS.index("Index retenu")]
        assert anciennes[-1] == "Identifiant lot"

    def test_E3_le_descriptif_porte_index_mode_duree_distance(self):
        option = SimpleNamespace(
            start_time=1_000_000,
            end_time=1_487_000,
            distance=6512.0,
            legs=[],
            mode_label=lambda: "car",
        )
        descriptif = _options_descriptif([option])
        assert descriptif.startswith("0:car:487s:")
        assert descriptif.endswith("km")

    def test_E3_sans_option_le_descriptif_est_vide(self):
        assert _options_descriptif(None) == ""
        assert _options_descriptif([]) == ""


class TestE4CroyancesMontrees:
    """E4 — le dénominateur qui innocente le modèle, et la garde du lot A."""

    def test_E4_le_compteur_existe_et_porte_une_alarme(self):
        source = (
            RACINE / "urban_mobility_agents" / "agents" / "llm_agent.py"
        ).read_text(encoding="utf-8")
        assert "_compter_croyances_montrees" in source
        corps = source.split("def _compter_croyances_montrees")[1].split(
            "\n    async def"
        )[0]
        assert "[ALARME]" in corps
        assert "_alarme_croyances_vides" in corps

    def test_E4_le_compteur_est_appele_avec_le_nombre_de_poignees(self):
        source = (
            RACINE / "urban_mobility_agents" / "agents" / "llm_agent.py"
        ).read_text(encoding="utf-8")
        assert (
            "self._compter_croyances_montrees(context.person.person_id, len(_par_poignee))"
            in source
        )


class TestE6RejeuEtMesures:
    """E6 — un rejeu n'ajoute pas ses trajets aux originaux."""

    def test_E6_moves_est_mis_de_cote(self, tmp_path):
        from urban_mobility_agents.utils.reprise import ecarter_les_sorties_du_rejeu

        (tmp_path / "moves.csv").write_text("Référence,Trajet\nrun,1\n", encoding="utf-8")
        ecartes = ecarter_les_sorties_du_rejeu(tmp_path)
        assert len(ecartes) == 1
        assert not (tmp_path / "moves.csv").exists()
        assert ecartes[0].read_text(encoding="utf-8").startswith("Référence")

    def test_E6_sans_fichier_rien_ne_se_passe(self, tmp_path):
        from urban_mobility_agents.utils.reprise import ecarter_les_sorties_du_rejeu

        assert ecarter_les_sorties_du_rejeu(tmp_path) == []

    def test_E6_l_ecartement_est_appele_quand_aucun_point_n_est_valide(self):
        source = (RACINE / "urban_mobility_agents" / "utils" / "reprise.py").read_text(
            encoding="utf-8"
        )
        bloc = source.split("AUCUN point de reprise valide")[1].split("return None")[0]
        assert "ecarter_les_sorties_du_rejeu" in bloc
