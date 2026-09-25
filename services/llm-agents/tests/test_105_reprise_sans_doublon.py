"""Ticket 105 — une reprise à chaud ne dédouble plus les trajets rejoués.

Ce que ces tests auraient attrapé : `restaurer_si_demande` n'écartait `moves.csv` que dans la
branche « aucun point de reprise trouvé ». Quand un point EST trouvé, GAMA repart quand même de
son t0 et rejoue les jours déjà vécus ; `move_logger` n'a aucune connaissance du gel, donc les
trajets rejoués s'ajoutaient au fichier, indiscernables des originaux. C'est exactement le défaut
qui avait dédoublé 84 trajets sur le run du ticket 075 — et la fonction écrite pour l'empêcher
n'était pas appelée sur ce chemin-là.

Chaque test de la première classe vérifie d'abord que le cas est bien celui qu'on croit, puis que
le défaut n'y est plus.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from urban_mobility_agents.utils import reprise

LIGNES = (
    "Temps simulé,Mode de transport Choisi,Méthode de sélection\n1774000000,Train,LLM\n"
)


@pytest.fixture(autouse=True)
def _etat_propre():
    reprise.reinitialiser()
    yield
    reprise.reinitialiser()


def _point_valide(workdir: Path, jour: int = 17, timestamp: int = 1774000000) -> Path:
    """Un point de reprise minimal mais VALIDE : c'est `reprise.json` qui fait la validité."""
    point = workdir / reprise.POINTS / f"jour_{jour:03d}"
    point.mkdir(parents=True)
    (point / reprise.DESCRIPTION).write_text(
        json.dumps(
            {
                "jour_simule": jour,
                "timestamp_simule": timestamp,
                "horodatage_simule": "2026-04-01T03:00:00",
            }
        ),
        encoding="utf-8",
    )
    return point


class TestLesDeuxBranchesEcartentLesSorties:
    def test_avec_un_point_valide_moves_est_ecarte(self, tmp_path):
        """LE CAS CORRIGÉ : un point trouvé ne dispense pas d'écarter les mesures."""
        _point_valide(tmp_path)
        (tmp_path / "moves.csv").write_text(LIGNES, encoding="utf-8")

        meta = reprise.restaurer_si_demande(tmp_path, reprise_demandee=True)

        assert meta is not None, "le point devait être restauré"
        assert not (tmp_path / "moves.csv").exists(), (
            "moves.csv est resté en place : le rejeu va y ajouter des trajets en double"
        )
        ecartes = list(tmp_path.glob("moves.csv.*.avant_rejeu"))
        assert len(ecartes) == 1
        assert ecartes[0].read_text(encoding="utf-8") == LIGNES, (
            "les mesures ne se perdent pas"
        )

    def test_sans_point_le_comportement_du_077_est_conserve(self, tmp_path):
        """La branche qui marchait déjà ne doit pas régresser."""
        (tmp_path / "moves.csv").write_text(LIGNES, encoding="utf-8")

        meta = reprise.restaurer_si_demande(
            tmp_path, reprise_demandee=True, alarme_si_absent=True
        )

        assert meta is None
        assert not (tmp_path / "moves.csv").exists()
        assert len(list(tmp_path.glob("moves.csv.*.avant_rejeu"))) == 1


class TestCeQuiNeDoitPasChanger:
    def test_un_run_neuf_ne_touche_a_rien(self, tmp_path):
        """`reprise_demandee=False` : aucun rejeu, donc aucune mesure à écarter."""
        (tmp_path / "moves.csv").write_text(LIGNES, encoding="utf-8")

        assert reprise.restaurer_si_demande(tmp_path, reprise_demandee=False) is None

        assert (tmp_path / "moves.csv").exists()
        assert not list(tmp_path.glob("moves.csv.*.avant_rejeu"))

    def test_un_init_de_run_neuf_sans_point_ne_touche_a_rien(self, tmp_path):
        """`alarme_si_absent=False` est le `/init` d'un run neuf : il ne rejoue rien."""
        (tmp_path / "moves.csv").write_text(LIGNES, encoding="utf-8")

        assert (
            reprise.restaurer_si_demande(
                tmp_path, reprise_demandee=True, alarme_si_absent=False
            )
            is None
        )

        assert (tmp_path / "moves.csv").exists()

    def test_le_gel_est_pose_apres_la_restauration(self, tmp_path):
        """Sans gel, le rejeu réécrirait des souvenirs déjà écrits."""
        _point_valide(tmp_path, jour=17, timestamp=1774000000)

        reprise.restaurer_si_demande(tmp_path, reprise_demandee=True)

        assert reprise.gel_actif() is True
        assert reprise.point_de_reprise_timestamp() == 1774000000

    def test_le_point_le_plus_recent_gagne(self, tmp_path):
        """Retirer un point est la seule façon de reprendre plus tôt : ça doit rester vrai."""
        _point_valide(tmp_path, jour=16, timestamp=1773900000)
        _point_valide(tmp_path, jour=17, timestamp=1774000000)

        meta = reprise.restaurer_si_demande(tmp_path, reprise_demandee=True)

        assert meta["jour_simule"] == 17

    def test_un_point_sans_description_n_est_pas_valide(self, tmp_path):
        """Un point à moitié écrit serait pire que pas de point : il serait restauré en silence."""
        (tmp_path / reprise.POINTS / "jour_018").mkdir(parents=True)
        _point_valide(tmp_path, jour=17, timestamp=1774000000)

        meta = reprise.restaurer_si_demande(tmp_path, reprise_demandee=True)

        assert meta["jour_simule"] == 17, (
            "le point 018 sans description devait être ignoré"
        )
