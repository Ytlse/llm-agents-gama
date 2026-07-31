"""Lecture du type de logement par la page de synthèse, et loi exportée (action A2).

Le trait traverse trois modules écrits séparément — la génération de population le
pose, le journal l'écrit, la page le joint à la référence — et la seule chose qui les
tienne ensemble est la table de modalités de `llm_module.core.housing_type`. Les tests
ci-dessous vérifient les deux bouts de la chaîne côté page :

- **la jointure**. La colonne porte le libellé de l'enquête, la référence l'indexe par
  clé : une correspondance ratée ne lève rien, elle vide l'axe. Et « Autres », connu de
  l'enquête mais absent de la ventilation publiée, doit être compté hors référentiel
  plutôt que de disparaître ;
- **l'aveu**. L'avertissement de la page doit dire lequel des deux vides il constate :
  un journal qui n'écrit pas la colonne, ou un run antérieur à l'action.

Plus, sans les données PROGEDO, les propriétés de la loi exportée : lissage
hiérarchique et lois qui restent des distributions.
"""

from __future__ import annotations

import csv

import numpy as np
import pytest

from llm_module.core.housing_type import LABEL_BY_KEY, MODALITY_KEYS
from scripts.synthesis import build, frames

HEADERS = ["Mode de transport Choisi", "Méthode de sélection", "Type de logement",
           "Occupation principale", "Motifs de déplacement", "Genre", "Âge",
           "Distance parcourue", "Lieu de résidence", "ID Personne", "ID Activité",
           "Heure de départ", "Modes proposés au LLM"]


def _moves(tmp_path, logements: list[str]):
    path = tmp_path / "moves.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADERS)
        writer.writeheader()
        for i, logement in enumerate(logements):
            writer.writerow({
                "Mode de transport Choisi": "Voiture Privée",
                "Méthode de sélection": "LLM",
                "Type de logement": logement,
                "Occupation principale": "Travail à plein temps",
                "Motifs de déplacement": "Travail",
                "Genre": "Homme", "Âge": "40", "Distance parcourue": "5.0",
                "Lieu de résidence": "Toulouse", "ID Personne": str(i),
                "ID Activité": "a", "Heure de départ": "2024-01-08 08:00:00",
                "Modes proposés au LLM": "Voiture Privée | Marche",
            })
    return path


class TestNormalisation:

    @pytest.mark.parametrize("key", MODALITY_KEYS)
    def test_le_libelle_du_journal_retrouve_sa_cle(self, key):
        assert frames.normalize_housing(LABEL_BY_KEY[key])[0] == key

    def test_les_quatre_modalites_de_reference_sont_referencees(self):
        for key in ("individuel_isole", "individuel_accole",
                    "petit_habitat_collectif", "grand_habitat_collectif"):
            assert frames.normalize_housing(LABEL_BY_KEY[key])[1] is True

    def test_autres_est_une_cle_valide_mais_hors_reference(self):
        assert frames.normalize_housing("Autres") == ("autres", False)

    def test_une_cle_deja_normalisee_est_acceptée(self):
        """Relecture d'un journal écrit autrement : on ne perd pas la ligne."""
        assert frames.normalize_housing("petit_habitat_collectif") == (
            "petit_habitat_collectif", True)

    def test_vide_et_inconnu_ne_donnent_pas_de_categorie(self):
        assert frames.normalize_housing("") == (None, False)
        assert frames.normalize_housing("   ") == (None, False)
        assert frames.normalize_housing("Maison de ville") == (None, False)


class TestLectureDuJournal:

    def test_la_colonne_alimente_la_dimension(self, tmp_path):
        path = _moves(tmp_path, ["Grand habitat collectif"] * 3 + ["Individuel isolé"] * 2)
        rows, stats = frames.read_moves(path, [])
        assert [r["type_logement"] for r in rows].count("grand_habitat_collectif") == 3
        assert stats.get("type_logement_vide", 0) == 0

    def test_les_cellules_vides_sont_comptees(self, tmp_path):
        rows, stats = frames.read_moves(_moves(tmp_path, ["", "Individuel isolé", ""]), [])
        assert stats["type_logement_vide"] == 2
        assert [r["type_logement"] for r in rows] == [None, "individuel_isole", None]

    def test_autres_est_compte_hors_referentiel(self, tmp_path):
        _, stats = frames.read_moves(_moves(tmp_path, ["Autres", "Individuel isolé"]), [])
        assert stats["type_logement_hors_referentiel"] == 1
        assert stats.get("type_logement_vide", 0) == 0


class TestVentilation:

    @pytest.fixture(scope="class")
    def cerema(self) -> dict:
        from scripts.synthesis.sources import load_manifest
        path = load_manifest().path_of("cerema")
        if path is None or not path.exists():
            pytest.skip("Référence EMC² absente")
        return frames.load_cerema(path)

    def test_la_dimension_se_joint_a_la_reference(self, tmp_path, cerema):
        """Le bout du bout : des libellés écrits par le journal produisent des
        effectifs sous les catégories de la référence, et pas un axe vide."""
        path = _moves(tmp_path, ["Individuel isolé"] * 4 + ["Grand habitat collectif"] * 6)
        rows, _ = frames.read_moves(path, [])
        dim = next(d for d in frames.DIMENSIONS if d["key"] == "type_logement")
        detail = {d["cat"]: d["n"]
                  for d in frames.dimension_detail(
                      frames.simulation_frames(rows)["attendu"], cerema, dim)}
        assert detail["individuel_isole"] == 4
        assert detail["grand_habitat_collectif"] == 6
        assert detail["petit_habitat_collectif"] == 0

    def test_autres_ne_pollue_pas_la_ventilation(self, tmp_path, cerema):
        rows, _ = frames.read_moves(_moves(tmp_path, ["Autres"] * 5), [])
        dim = next(d for d in frames.DIMENSIONS if d["key"] == "type_logement")
        detail = frames.dimension_detail(
            frames.simulation_frames(rows)["attendu"], cerema, dim)
        assert {d["cat"] for d in detail} == set(
            cerema["parts_modales_2023"]["type_logement"])
        assert all(d["n"] == 0 for d in detail)


class TestAvertissementDeLaPage:
    """L'aveu doit être exact : le journal écrit-il la colonne, ou le run est-il vieux ?"""

    def _warnings(self, tmp_path, monkeypatch, logements: list[str]) -> list[str]:
        path = _moves(tmp_path, logements)
        run_dir = path.parent
        monkeypatch.setattr(frames, "resolve_run", lambda manifest: {
            "exists": True, "configured": str(run_dir), "path": str(run_dir),
            "run_id": run_dir.name,
            "moves": {"exists": True, "path": str(path), "mtime": "2026-07-29"},
            "population": {"exists": True},
        })
        monkeypatch.setattr(build, "REPO_ROOT", type(path)("/"))

        class _Manifest:
            def get(self, key, default=None):
                return default
        common, _ = build.build_common_set(_Manifest(), {})
        return common["warnings"]

    def test_colonne_vide_partout_impute_le_vide_a_l_anciennete_du_run(
            self, tmp_path, monkeypatch):
        warnings = self._warnings(tmp_path, monkeypatch, ["", "", ""])
        message = next(w for w in warnings if "type de logement" in w)
        assert "renseigne désormais" in message
        assert "avant" in message

    def test_colonne_partiellement_vide_designe_le_hors_couche(
            self, tmp_path, monkeypatch):
        warnings = self._warnings(tmp_path, monkeypatch,
                                  ["Individuel isolé", "", "Individuel accolé"])
        message = next(w for w in warnings if "type de logement" in w)
        assert message.startswith("1 trajets")
        assert "hors de la couche" in message

    def test_colonne_remplie_ne_produit_aucun_avertissement(self, tmp_path, monkeypatch):
        warnings = self._warnings(tmp_path, monkeypatch, ["Individuel isolé"] * 3)
        assert not [w for w in warnings if "type de logement" in w]

    def test_autres_est_signale(self, tmp_path, monkeypatch):
        warnings = self._warnings(tmp_path, monkeypatch,
                                  ["Autres", "Individuel isolé"])
        assert any("« Autres »" in w for w in warnings)


class TestLoiExportee:
    """Propriétés de l'export, vérifiées sans les données d'accès restreint."""

    @pytest.fixture(scope="class")
    def export(self):
        return pytest.importorskip(
            "scripts.progedo_logit.export_housing_type",
            reason="l'export exige geopandas/sklearn (extra 'geo')")

    @pytest.fixture
    def persons(self):
        pd = pytest.importorskip("pandas")
        # Un secteur (1001) à deux zones : l'une bien enquêtée et entièrement en
        # grand collectif, l'autre à un seul répondant en individuel isolé.
        rows = ([{"ZF": "100100000", "housing": "grand_habitat_collectif", "weight": 1.0}] * 100
                + [{"ZF": "100199000", "housing": "individuel_isole", "weight": 1.0}])
        return pd.DataFrame(rows)

    def test_les_lois_sont_des_distributions(self, export, persons):
        table = export.build_table(persons)
        assert table["modalities"] == list(MODALITY_KEYS)
        assert sum(table["global"]) == pytest.approx(1.0, abs=1e-3)
        for node in list(table["zones"].values()) + list(table["sectors"].values()):
            assert sum(node["shares"]) == pytest.approx(1.0, abs=1e-3)

    def test_une_zone_mince_est_tiree_vers_son_secteur(self, export, persons):
        """Sans lissage, une zone à 1 répondant servirait 100 % d'individuel isolé :
        du bruit d'échantillonnage présenté comme de la géographie."""
        table = export.build_table(persons)
        index = MODALITY_KEYS.index("individuel_isole")
        thin = table["zones"]["100199000"]["shares"][index]
        assert thin < 0.15
        assert table["zones"]["100199000"]["n"] == 1

    def test_une_zone_bien_enquetee_garde_sa_loi(self, export, persons):
        table = export.build_table(persons)
        index = MODALITY_KEYS.index("grand_habitat_collectif")
        assert table["zones"]["100100000"]["shares"][index] > 0.9

    def test_le_lissage_est_une_combinaison_convexe(self, export):
        observed = np.array([1.0, 0.0, 0.0, 0.0, 0.0])
        prior = np.array([0.0, 1.0, 0.0, 0.0, 0.0])
        smoothed = export._smooth(observed, export.PRIOR_WEIGHT, prior)
        assert smoothed[0] == pytest.approx(0.5)
        assert smoothed[1] == pytest.approx(0.5)
        assert sum(smoothed) == pytest.approx(1.0)

    def test_l_effectif_enquete_est_publie_avec_la_loi(self, export, persons):
        """Aucun seuil ne masque rien : le lecteur voit sur quoi la loi repose."""
        table = export.build_table(persons)
        assert table["zones"]["100100000"]["n"] == 100
        assert table["meta"]["n_persons"] == 101
