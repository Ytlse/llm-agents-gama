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
        """« Autres » ne devient pas une strate — mais sa masse est COMPTÉE.

        Le ticket 019 exigeait la première moitié : la modalité existe dans l'enquête,
        la ventilation EMC² publiée l'ignore, elle ne doit donc pas recevoir de cible ni
        peser dans un L1. Le ticket 021 a ajouté la seconde : une masse exclue des cibles
        et invisible se confond avec une masse inexistante. `dimension_detail` rend donc
        une ligne supplémentaire, sans cible ni L1 et jamais « couverte », qui porte cette
        masse — le même geste que `global_view` fait de sa masse hors modes scorés.
        """
        rows, _ = frames.read_moves(_moves(tmp_path, ["Autres"] * 5), [])
        dim = next(d for d in frames.DIMENSIONS if d["key"] == "type_logement")
        detail = frames.dimension_detail(
            frames.simulation_frames(rows)["attendu"], cerema, dim)

        strates = [d for d in detail if d["cat"] != frames.OFF_REFERENCE_ROW]
        assert {d["cat"] for d in strates} == set(
            cerema["parts_modales_2023"]["type_logement"])
        assert all(d["n"] == 0 for d in strates)

        hors = [d for d in detail if d["cat"] == frames.OFF_REFERENCE_ROW]
        assert len(hors) == 1, "la masse hors référentiel doit être publiée, pas diluée"
        assert hors[0]["excluded_mass"] > 0
        assert hors[0]["l1"] is None and hors[0]["covered"] is False


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
    def households(self):
        """Un secteur (1001) à deux zones, et un gradient de taille net.

        La zone 100100000 est bien enquêtée et entièrement en grand collectif ; la zone
        100199000 n'a qu'un répondant, en individuel isolé. Les ménages d'une personne
        sont en collectif, ceux de quatre en individuel : c'est ce gradient que le levier
        de taille doit retrouver.
        """
        pd = pytest.importorskip("pandas")
        rows = []
        for index in range(100):
            size = 1 if index < 60 else 4
            housing = "grand_habitat_collectif" if size == 1 else "individuel_isole"
            rows.append({"ZF": "100100000", "housing": housing, "weight": 1.0,
                         "size": size, "bucket": size})
        rows.append({"ZF": "100199000", "housing": "individuel_isole", "weight": 1.0,
                     "size": 2, "bucket": 2})
        rows.append({"ZF": "100199000", "housing": "petit_habitat_collectif",
                     "weight": 1.0, "size": 3, "bucket": 3})
        return pd.DataFrame(rows)

    def test_les_lois_sont_des_distributions(self, export, households):
        table = export.build_table(households)
        assert table["modalities"] == list(MODALITY_KEYS)
        assert sum(table["global"]) == pytest.approx(1.0, abs=1e-3)
        for node in list(table["zones"].values()) + list(table["sectors"].values()):
            assert sum(node["shares"]) == pytest.approx(1.0, abs=1e-3)

    def test_la_ressource_est_versionnee_pour_le_module(self, export, households):
        """Le module refuse une v1 : l'export doit donc annoncer la v2, et servir les
        quatre leviers — sans quoi la ressource produite serait illisible pour lui."""
        from llm_module.core.housing_type import MIN_RESOURCE_VERSION, SIZE_MAX
        table = export.build_table(households)
        assert table["version"] >= MIN_RESOURCE_VERSION
        assert sorted(table["size_leverage"]) == [
            str(size) for size in range(1, SIZE_MAX + 1)]

    def test_une_zone_mince_est_tiree_vers_son_secteur(self, export, households):
        """Sans lissage, une zone à 1 répondant servirait 100 % d'individuel isolé :
        du bruit d'échantillonnage présenté comme de la géographie."""
        table = export.build_table(households)
        index = MODALITY_KEYS.index("individuel_isole")
        thin = table["zones"]["100199000"]["shares"][index]
        assert thin < 0.45
        assert table["zones"]["100199000"]["n"] == 2

    def test_une_zone_bien_enquetee_garde_sa_loi(self, export, households):
        table = export.build_table(households)
        index = MODALITY_KEYS.index("grand_habitat_collectif")
        assert table["zones"]["100100000"]["shares"][index] > 0.5

    def test_le_lissage_est_une_combinaison_convexe(self, export):
        observed = np.array([1.0, 0.0, 0.0, 0.0, 0.0])
        prior = np.array([0.0, 1.0, 0.0, 0.0, 0.0])
        smoothed = export._smooth(observed, export.PRIOR_WEIGHT, prior)
        assert smoothed[0] == pytest.approx(0.5)
        assert smoothed[1] == pytest.approx(0.5)
        assert sum(smoothed) == pytest.approx(1.0)

    def test_l_effectif_enquete_est_publie_avec_la_loi(self, export, households):
        """Aucun seuil ne masque rien : le lecteur voit sur quoi la loi repose."""
        table = export.build_table(households)
        assert table["zones"]["100100000"]["n"] == 100
        assert table["meta"]["n_households"] == 102


class TestLevierDeTailleExporte:
    """Le bloc que le ticket 019 ajoute à la ressource, et son test interne."""

    @pytest.fixture(scope="class")
    def export(self):
        return pytest.importorskip(
            "scripts.progedo_logit.export_housing_type",
            reason="l'export exige geopandas/sklearn (extra 'geo')")

    @pytest.fixture
    def households(self):
        """Deux zones identiques en géographie, opposées en composition de ménages :
        le levier de taille est la SEULE chose qui puisse les distinguer."""
        pd = pytest.importorskip("pandas")
        rows = []
        for zone in ("100100000", "100200000"):
            for index in range(200):
                size = 1 if index % 2 else 4
                # Les personnes seules en collectif, les familles en individuel.
                housing = ("grand_habitat_collectif" if size == 1
                           else "individuel_isole")
                rows.append({"ZF": zone, "housing": housing, "weight": 1.0,
                             "size": size, "bucket": size})
        return pd.DataFrame(rows)

    def test_le_levier_va_dans_le_sens_de_la_composition(self, export, households):
        table = export.build_table(households)
        isole = MODALITY_KEYS.index("individuel_isole")
        assert table["size_leverage"]["1"]["leverage"][isole] < 1.0
        assert table["size_leverage"]["4"]["leverage"][isole] > 1.0

    def test_les_effectifs_de_cellule_sont_ecrits(self, export, households):
        """« Effectifs de cellule écrits dans la ressource, comme aujourd'hui pour les
        zones ; toute cellule sous 30 observations pondérées est signalée. »"""
        table = export.build_table(households)
        cells = {cell["modality"]: cell
                 for cell in table["size_leverage"]["1"]["cells"]}
        assert cells["grand_habitat_collectif"]["n"] == 200
        assert cells["grand_habitat_collectif"]["thin"] is False
        assert cells["individuel_isole"]["n"] == 0
        assert cells["individuel_isole"]["thin"] is True

    def test_le_test_interne_mesure_le_mecanisme_livre(self, export, households):
        """Sur une population où la taille explique TOUT, le levier doit ramener
        l'erreur à zéro là où la loi de zone seule se trompe de plein fouet."""
        table = export.build_table(households)
        delivered = table["validation"]["delivered"]
        zone_seule = next(row for row in table["validation"]["baselines"]
                          if "ménages" in row["label"])
        assert delivered["mean_abs_error_pt"] < 0.5
        assert zone_seule["mean_abs_error_pt"] > 10.0
        assert table["validation"]["passes"] is True

    def test_le_test_interne_publie_les_20_cellules(self, export, households):
        from llm_module.core.housing_type import SIZE_MAX
        table = export.build_table(households)
        cells = table["validation"]["delivered"]["cells"]
        # Deux tailles peuplées dans ce jeu : 5 modalités chacune.
        assert len(cells) == 2 * len(MODALITY_KEYS)
        assert {cell["size"] for cell in cells} == {1, SIZE_MAX}
        assert all("observed_pct" in cell and "imputed_pct" in cell for cell in cells)

    def test_la_marginale_d_ensemble_n_est_pas_deplacee(self, export, households):
        """Si le levier écrasait la zone, la marginale bougerait — c'est le garde-fou
        du ticket : « le raking ne doit pas déplacer la géographie »."""
        table = export.build_table(households)
        delivered = table["validation"]["delivered"]
        for observed, imputed in zip(delivered["overall_marginal_observed_pct"],
                                     delivered["overall_marginal_imputed_pct"]):
            assert abs(observed - imputed) < 1.5

    def test_le_mecanisme_precedent_est_rejoue_quand_on_donne_les_personnes(
            self, export, households):
        """La comparaison avant/après vit dans la ressource : sans elle, « quatre fois
        moins d'erreur » ne serait qu'une phrase."""
        pd = pytest.importorskip("pandas")
        persons = pd.concat([households.assign(weight=households["size"])] * 1)
        table = export.build_table(households, persons)
        labels = [row["label"] for row in table["validation"]["baselines"]]
        assert any("pondération personnes" in label for label in labels)
