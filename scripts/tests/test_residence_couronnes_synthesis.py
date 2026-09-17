"""Les six colonnes traduites du journal, relues dans les deux vocabulaires (ticket 082).

La bascule anglaise du ticket 074 a changé la langue de plusieurs colonnes de
`moves.csv` — celles qui sont SERVIES AU MODÈLE dans le récit de persona. Les tables de
correspondance du scoreur ont suivi pour l'occupation et le logement ; la couronne de
résidence a été oubliée, et `normalize_place` se contentait de souligner les espaces.
`1st ring` devenait `1st_ring`, une clé que `cerema_values.yaml` ne ventile pas : sur les
15 exécutions v6 scorées au 2026-09-15, la dimension « lieu de résidence » ne publiait
plus qu'une strate sur
quatre. Aucune ligne ne manquait, aucune alarme ne partait — les trois couronnes étaient
comptées « hors référentiel », c'est-à-dire nulle part de visible.

Ce que ces tests tiennent :

- **la symétrie des deux vocabulaires**. Une ligne v5 et une ligne v6 décrivant le même
  persona doivent produire la MÊME trame de décision, sur les six colonnes traduites. Un
  test paramétré vaut mieux qu'une lecture du diff : il échoue le jour où une septième
  colonne bascule sans sa table ;
- **le refus de traverser**. Un libellé qu'aucune table ne connaît sort de la dimension,
  se compte, et se dit en `[ALARME]` à sa première occurrence. C'est la propriété qui
  aurait fait découvrir le ticket 082 le jour de la bascule au lieu de six semaines après ;
- **les quatre couronnes**, sur une trame de résidence complète.
"""

from __future__ import annotations

import csv
import logging

import pytest

from mobility_core.population_reference import (
    COURONNES,
    COURONNES_FR,
    OUT_OF_PERIMETER,
    OUT_OF_PERIMETER_FR,
)
from scripts.synthesis import frames

HEADERS = ["Mode de transport Choisi", "Méthode de sélection", "Type de logement",
           "Occupation principale", "Motifs de déplacement", "Genre", "Âge",
           "Distance parcourue", "Lieu de résidence", "ID Personne", "ID Activité",
           "Heure de départ", "Modes proposés au LLM", "Temps simulé"]

# Le MÊME persona, décrit dans les deux vocabulaires du journal. Les six colonnes que le
# ticket 074 a pu traduire y figurent ; `Genre`, `Mode de transport Choisi` et `Modes
# proposés au LLM` sont restés français des deux côtés, et le test le constate plutôt que
# de le supposer — c'est ce constat qui rendra la bascule visible si elle arrive.
PERSONA_V5 = {
    "Lieu de résidence": "2eme couronne",
    "Occupation principale": "Travail à plein temps",
    "Type de logement": "Individuel isolé",
    "Motifs de déplacement": "Travail",
    "Mode de transport Choisi": "Voiture Privée",
    "Modes proposés au LLM": "Voiture Privée | Marche",
}
PERSONA_V6 = {
    "Lieu de résidence": "2nd ring",
    "Occupation principale": "Full-time worker",
    "Type de logement": "Detached house",
    "Motifs de déplacement": "Travail",
    "Mode de transport Choisi": "Voiture Privée",
    "Modes proposés au LLM": "Voiture Privée | Marche",
}

# Ce que la trame doit porter, quelle que soit la langue lue.
COLONNES_TRADUITES = ["lieu_residence", "occupation", "type_logement", "motif",
                      "chosen", "offered"]

EXCLURE_METHODES = ["Pas de déplacement (même localisation)",
                    "Pas de solution de déplacement", "LLM Error (Default index)"]


def _moves(tmp_path, lignes: list[dict], nom: str = "moves.csv"):
    """Écrit un `moves.csv` minimal : une ligne par entrée, tout le reste constant."""
    path = tmp_path / nom
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADERS)
        writer.writeheader()
        for i, ligne in enumerate(lignes):
            writer.writerow({
                "Méthode de sélection": "LLM",
                "Genre": "Homme", "Âge": "40", "Distance parcourue": "5.0",
                "ID Personne": str(i), "ID Activité": "a",
                "Heure de départ": "2024-01-08 08:00:00",
                "Temps simulé": "2024-01-08 08:00:00",
                **ligne,
            })
    return path


@pytest.fixture(autouse=True)
def _compteurs_neufs():
    """Chaque test part de compteurs vides : l'alarme est à front montant."""
    frames.reinitialiser_compteurs_libelles()
    yield
    frames.reinitialiser_compteurs_libelles()


class TestTableDeCorrespondance:
    """`normalize_place` — les deux vocabulaires, et le refus du libellé inconnu."""

    @pytest.mark.parametrize(("libelle", "attendu"), [
        ("1st ring", "1ere_couronne"),
        ("2nd ring", "2eme_couronne"),
        ("3rd ring", "3eme_couronne"),
        ("Toulouse", "Toulouse"),
        ("1ere couronne", "1ere_couronne"),
        ("2eme couronne", "2eme_couronne"),
        ("3eme couronne", "3eme_couronne"),
    ])
    def test_les_deux_vocabulaires_donnent_la_cle_de_l_enquete(self, libelle, attendu):
        assert frames.normalize_place(libelle) == (attendu, True)

    @pytest.mark.parametrize("canonique", COURONNES)
    def test_toute_modalite_canonique_est_traduite(self, canonique):
        """La couverture vient du module de population, pas d'une liste recopiée ici."""
        cle, referencee = frames.normalize_place(canonique)
        assert referencee and cle is not None

    @pytest.mark.parametrize("ancienne", COURONNES_FR)
    def test_toute_modalite_d_avant_la_bascule_est_traduite(self, ancienne):
        cle, referencee = frames.normalize_place(ancienne)
        assert referencee and cle is not None

    def test_une_cle_deja_normalisee_est_son_propre_antecedent(self):
        """Relire une page regénérée depuis une trace réécrite ne doit rien perdre."""
        assert frames.normalize_place("1ere_couronne") == ("1ere_couronne", True)

    @pytest.mark.parametrize("libelle", [OUT_OF_PERIMETER, OUT_OF_PERIMETER_FR])
    def test_hors_perimetre_est_compte_jamais_joint(self, libelle):
        """Aucune cible par zone (ticket 021) : la clé existe, la jointure non."""
        assert frames.normalize_place(libelle) == (frames.OUT_OF_PERIMETER_KEY, False)

    def test_un_libelle_inconnu_ne_traverse_pas(self, caplog):
        with caplog.at_level(logging.ERROR, logger="synthesis.frames"):
            assert frames.normalize_place("Mars") == (None, False)
        assert frames.PLACES_INCONNUES["Mars"] == 1
        assert any("[ALARME]" in r.message and "Mars" in r.message
                   for r in caplog.records)

    def test_l_alarme_part_sur_front_montant(self, caplog):
        """Trois mille lignes fautives ne font pas trois mille alarmes — mais un compteur
        à 3 000. Noyer le journal, c'est le rendre illisible le jour où il compte."""
        with caplog.at_level(logging.ERROR, logger="synthesis.frames"):
            for _ in range(5):
                frames.normalize_place("Mars")
        assert frames.PLACES_INCONNUES["Mars"] == 5
        assert sum("[ALARME]" in r.message for r in caplog.records) == 1

    def test_une_colonne_vide_n_est_pas_un_libelle_inconnu(self):
        """Une population enrichie avant le ticket 021 écrit la colonne vide : c'est un
        cas normal, il ne doit ni alarmer ni compter comme un défaut de traduction."""
        assert frames.normalize_place("") == (None, False)
        assert not frames.PLACES_INCONNUES

    def test_les_cles_fantomes_sont_exactement_les_formes_anglaises(self):
        """La signature que `experiences.score` utilise pour périmer un scores.json."""
        assert frames.PLACE_CLES_FANTOMES == {"1st_ring", "2nd_ring", "3rd_ring"}


class TestSymetrieV5V6:
    """Une ligne v5 et une ligne v6 du même persona produisent la même trame."""

    @pytest.mark.parametrize("colonne", COLONNES_TRADUITES)
    def test_la_meme_cle_des_deux_cotes(self, tmp_path, colonne):
        v5, _ = frames.read_moves(_moves(tmp_path, [PERSONA_V5], "v5.csv"),
                                  EXCLURE_METHODES)
        v6, _ = frames.read_moves(_moves(tmp_path, [PERSONA_V6], "v6.csv"),
                                  EXCLURE_METHODES)
        assert v5[0][colonne] == v6[0][colonne]

    def test_aucun_libelle_illisible_dans_les_deux_cohortes(self, tmp_path):
        """Le corollaire : la symétrie serait aussi vraie si les DEUX étaient perdues."""
        for nom, persona in (("v5.csv", PERSONA_V5), ("v6.csv", PERSONA_V6)):
            _, stats = frames.read_moves(_moves(tmp_path, [persona], nom),
                                         EXCLURE_METHODES)
            assert stats.get("lieu_residence_inconnu", 0) == 0
            assert stats.get("type_logement_inconnu", 0) == 0
            assert stats.get("occupation_inconnue", 0) == 0
            assert stats.get("motif_inconnu", 0) == 0

    def test_la_cohorte_v6_joint_bien_la_couronne(self, tmp_path):
        """Le test qui aurait échoué avant le ticket 082 : `2nd ring` → `2eme_couronne`."""
        v6, _ = frames.read_moves(_moves(tmp_path, [PERSONA_V6], "v6.csv"),
                                  EXCLURE_METHODES)
        assert v6[0]["lieu_residence"] == "2eme_couronne"


class TestCompteursDeLecture:
    """Vide et illisible sont deux pannes différentes, et portent deux compteurs."""

    def test_un_lieu_illisible_se_compte_a_part(self, tmp_path):
        path = _moves(tmp_path, [{**PERSONA_V6, "Lieu de résidence": "Mars"}])
        rows, stats = frames.read_moves(path, EXCLURE_METHODES)
        assert stats["lieu_residence_inconnu"] == 1
        assert "lieu_residence_vide" not in stats
        assert rows[0]["lieu_residence"] is None

    def test_un_lieu_vide_reste_un_lieu_vide(self, tmp_path):
        path = _moves(tmp_path, [{**PERSONA_V6, "Lieu de résidence": ""}])
        _, stats = frames.read_moves(path, EXCLURE_METHODES)
        assert stats["lieu_residence_vide"] == 1
        assert "lieu_residence_inconnu" not in stats

    def test_un_logement_illisible_se_compte_a_part(self, tmp_path):
        path = _moves(tmp_path, [{**PERSONA_V6, "Type de logement": "Yurt"}])
        _, stats = frames.read_moves(path, EXCLURE_METHODES)
        assert stats["type_logement_inconnu"] == 1
        assert "type_logement_vide" not in stats

    @pytest.mark.parametrize("motif", ["home", "leisure", "other"])
    def test_les_motifs_sans_equivalent_ne_sont_pas_des_defauts(self, tmp_path, motif):
        """`home` n'a pas de cible EMC² : il sort de la dimension sans rien signaler."""
        path = _moves(tmp_path, [{**PERSONA_V6, "Motifs de déplacement": motif}])
        rows, stats = frames.read_moves(path, EXCLURE_METHODES)
        assert rows[0]["motif"] is None
        assert "motif_inconnu" not in stats

    def test_un_motif_hors_table_se_dit(self, tmp_path):
        path = _moves(tmp_path, [{**PERSONA_V6, "Motifs de déplacement": "pilgrimage"}])
        _, stats = frames.read_moves(path, EXCLURE_METHODES)
        assert stats["motif_inconnu"] == 1

    def test_une_occupation_illisible_se_dit(self, tmp_path):
        path = _moves(tmp_path, [{**PERSONA_V6, "Occupation principale": "Jedi"}])
        _, stats = frames.read_moves(path, EXCLURE_METHODES)
        assert stats["occupation_inconnue"] == 1
        assert frames.OCCUPATIONS_INCONNUES["Jedi"] == 1


class TestQuatreCouronnes:
    """La dimension publie quatre strates, et plus une ligne « hors référentiel »."""

    def _detail(self, tmp_path, couronnes):
        # Cinq personas par couronne : `dimension_detail` ne déclare « couverte » qu'au-delà.
        lignes = [{**PERSONA_V6, "Lieu de résidence": c}
                  for c in couronnes for _ in range(5)]
        rows, _ = frames.read_moves(_moves(tmp_path, lignes), EXCLURE_METHODES)
        cerema = frames.load_cerema(
            frames.REPO_ROOT / "scripts" / "data" / "population" / "cerema_values.yaml")
        dim = next(d for d in frames.DIMENSIONS if d["key"] == "lieu_residence")
        return frames.dimension_detail(
            frames.simulation_frames(rows)["attendu"], cerema, dim)

    def test_les_quatre_couronnes_sont_publiees(self, tmp_path):
        detail = self._detail(tmp_path, COURONNES)
        strates = {d["cat"]: d for d in detail if d["cat"] != frames.OFF_REFERENCE_ROW}
        assert set(strates) == {"Toulouse", "1ere_couronne", "2eme_couronne",
                                "3eme_couronne"}
        assert all(d["n"] == 5 and d["covered"] for d in strates.values())

    def test_plus_aucune_masse_hors_referentiel(self, tmp_path):
        """Avant le ticket 082, trois couronnes sur quatre finissaient dans cette ligne."""
        detail = self._detail(tmp_path, COURONNES)
        assert not [d for d in detail if d["cat"] == frames.OFF_REFERENCE_ROW]

    def test_hors_perimetre_reste_hors_referentiel(self, tmp_path):
        """La correction ne doit pas ramener dans les strates ce que le ticket 021 en a
        sorti : un domicile hors des 453 communes n'a aucune cible par zone."""
        detail = self._detail(tmp_path, [*COURONNES, OUT_OF_PERIMETER])
        hors = [d for d in detail if d["cat"] == frames.OFF_REFERENCE_ROW]
        assert len(hors) == 1
        assert set(hors[0]["categories"]) == {frames.OUT_OF_PERIMETER_KEY}
