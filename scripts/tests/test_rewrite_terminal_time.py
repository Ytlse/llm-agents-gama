"""Réécriture du temps terminal d'un jeu gelé (alignement sur EMC²).

Ce qui est verrouillé ici, ce sont les propriétés sans lesquelles la mesure ne vaudrait
rien :

- **l'invariant du rendu** : le total affiché est EXACTEMENT la somme des sous-étapes
  affichées. C'est le critère d'acceptation 2 du ticket 013, et il tient parce que toutes
  les valeurs écrites sont des multiples de 60 s — `floor(a + k·60) == floor(a) + k` ;
- **le temps de conduite est intact** : on ne sait pas le recalculer sans rejouer le
  routage, donc y toucher invaliderait la comparaison ;
- **le tirage est déterministe** : deux exécutions donnent le même jeu, sinon le cache
  d'éval du store devient faux ;
- **une seule variable bouge** : la structure du rendu est préservée, sous-puces nulles
  comprises. Supprimer les composantes à zéro serait un second changement, et l'A/B
  mesurerait deux choses à la fois ;
- **la couronne est lue, pas devinée** : c'est l'égression appliquée par la config qui
  l'identifie.

Hors ligne, sans les données PROGEDO : la loi est un doublon dont on connaît la réponse.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import pytest

CALIB = Path(__file__).resolve().parents[2] / "prompt_calibration"
if str(CALIB) not in sys.path:
    sys.path.insert(0, str(CALIB))

rewrite = pytest.importorskip("rewrite_terminal_time")


class _Law:
    """Loi de test : `minutes` est certain, ce qui rend chaque assertion exacte."""

    def __init__(self, minutes: int):
        self._pmf = {str(minutes): 1.0}

    def pmf(self, mode: str, end: str, crown):  # noqa: ARG002 — signature du vrai objet
        return dict(self._pmf)


OPTION = """--- agent_id=42 | Destination : work ---
- [0] foot: Durée estimée : 25 minutes. Distance : 2.0 km.
- [1] car: Temps de trajet : 15 minutes, dont 10 minutes d'accès et de stationnement. Distance : 5.0 km.
    · Rejoindre la voiture : 3 minutes.
    · Conduite : 5 minutes.
    · Stationnement et marche jusqu'à 'work' : 7 minutes.
- [2] bicycle: Temps de trajet : 12 minutes, dont 2 minutes d'accès et d'attache. Distance : 2.0 km.
    · Déverrouiller le vélo : 1 minute.
    · Trajet à vélo : 10 minutes.
    · Attacher le vélo à 'work' : 1 minute.
"""


def _minutes(text: str) -> int:
    return rewrite.to_seconds(text) // 60


def _car_block(section: str) -> str:
    match = rewrite.CAR_OPTION.search(section)
    assert match, "option voiture introuvable"
    return match.group(0)


def _rewrite(minutes: int, section: str = OPTION,
             modes: tuple[str, ...] = ("car",)) -> tuple[str, Counter]:
    stats: Counter = Counter()
    out = rewrite.rewrite_section(section, _Law(minutes), "42", "0", stats, modes)
    return out, stats


class TestInvariantDuRendu:

    @pytest.mark.parametrize("minutes", [0, 1, 2, 5])
    def test_le_total_est_la_somme_des_sous_etapes(self, minutes):
        """L'invariant du ticket 013, sur lequel tout le rendu repose."""
        out, _ = _rewrite(minutes)
        block = _car_block(out)
        # Ne capturer QUE la durée de tête : `[^.]+` avalerait aussi la clause
        # « dont X minutes d'accès », et `to_seconds` sommerait les deux nombres —
        # le test annoncerait 25 minutes là où l'en-tête en affiche 15.
        head = re.search(r"Temps de trajet\s*:\s*([^,.]+(?:,\s*\d+\s*minutes?)?)",
                         block).group(1)
        head = re.split(r",\s*dont", head)[0]
        total = _minutes(head)
        steps = [_minutes(m.group(1)) for m in
                 re.finditer(r"·[^:]+:\s*([^.\n]+)\.", block)]
        assert total == sum(steps), (total, steps, block)

    @pytest.mark.parametrize("minutes", [0, 1, 3])
    def test_le_temps_de_conduite_est_intact(self, minutes):
        """On ne sait pas le recalculer : y toucher invaliderait la comparaison."""
        out, _ = _rewrite(minutes)
        drive = rewrite.DRIVE_STEP.search(_car_block(out))
        assert _minutes(drive.group("val")) == 5

    def test_la_clause_terminale_disparait_quand_le_terminal_est_nul(self):
        """« dont 0 minute d'accès » serait du bruit : la clause s'efface."""
        out, _ = _rewrite(0)
        assert "d'accès et de stationnement" not in _car_block(out)

    def test_la_clause_terminale_est_presente_sinon(self):
        out, _ = _rewrite(2)
        block = _car_block(out)
        assert "dont 4 minutes d'accès et de stationnement" in block

    def test_la_distance_est_conservee(self):
        out, _ = _rewrite(1)
        assert "Distance : 5.0 km." in _car_block(out)


class TestUneSeuleVariable:

    def test_les_sous_puces_nulles_sont_conservees(self):
        """Supprimer les composantes à zéro changerait la STRUCTURE en même temps que
        les durées : l'A/B mesurerait deux choses à la fois."""
        out, _ = _rewrite(0)
        block = _car_block(out)
        assert "Rejoindre la voiture : 0 minute." in block
        assert "Stationnement et marche jusqu'à 'work' : 0 minute." in block

    def test_les_autres_modes_ne_sont_pas_touches(self):
        """Le vélo et la marche portent aussi un temps terminal ; il n'est pas l'objet
        de cette réécriture, et le modifier confondrait deux corrections."""
        out, _ = _rewrite(0)
        assert "- [0] foot: Durée estimée : 25 minutes. Distance : 2.0 km." in out
        assert "· Déverrouiller le vélo : 1 minute." in out
        assert "dont 2 minutes d'accès et d'attache" in out

    def test_le_nombre_doptions_est_inchange(self):
        out, _ = _rewrite(2)
        assert out.count("- [") == OPTION.count("- [")


class TestDeterminisme:

    def test_deux_reecritures_donnent_le_meme_texte(self):
        first, _ = _rewrite(2)
        second, _ = _rewrite(2)
        assert first == second

    def test_le_tirage_suit_la_loi(self):
        """Sur beaucoup de clés, la fréquence tirée doit approcher la loi servie."""
        pmf = {"0": 0.9, "5": 0.1}
        drawn = Counter(rewrite.draw_minutes(pmf, f"clé-{i}") for i in range(4000))
        assert 0.86 < drawn[0] / 4000 < 0.94, drawn

    def test_une_loi_certaine_rend_sa_valeur(self):
        assert rewrite.draw_minutes({"3": 1.0}, "quelconque") == 3

    def test_deux_bouts_tirent_independamment(self):
        """Accès et égression ont des clés distinctes : sinon ils seraient corrélés à 1
        et le temps terminal ne porterait qu'une seule source de variation."""
        pmf = {"0": 0.5, "4": 0.5}
        pairs = {(rewrite.draw_minutes(pmf, f"{i}:access"),
                  rewrite.draw_minutes(pmf, f"{i}:egress")) for i in range(200)}
        assert len(pairs) == 4, pairs


class TestLectureDeLaCouronne:

    def test_l_egression_identifie_la_couronne_de_destination(self):
        """C'est la table inverse de `terminal_time.yaml`, et elle est identifiante."""
        assert rewrite.EGRESS_TO_CROWN[7] == "Toulouse"
        assert rewrite.EGRESS_TO_CROWN[4] == "1ere couronne"
        assert rewrite.EGRESS_TO_CROWN[3] == "2eme couronne"
        assert rewrite.EGRESS_TO_CROWN[1] == "3eme couronne"

    def test_la_couronne_lue_est_comptee(self):
        _, stats = _rewrite(1)
        assert stats["couronne_dest:Toulouse"] == 1, dict(stats)

    def test_une_option_non_decomposee_est_laissee_telle_quelle(self):
        """Mieux vaut une option identifiable qu'une décomposition inventée."""
        section = ("- [0] car: Durée estimée : 27 minutes. Distance : 11.3 km.\n")
        out, stats = _rewrite(3, section)
        assert out == section
        assert stats["options_car_non_decomposees"] == 1


class TestHumanize:

    @pytest.mark.parametrize("seconds,expected", [
        (0, "0 minute"), (60, "1 minute"), (120, "2 minutes"),
        (3600, "1 hour"), (3660, "1 hour, 1 minute"), (7320, "2 hours, 2 minutes"),
    ])
    def test_rendu_des_durees(self, seconds, expected):
        assert rewrite.humanize(seconds) == expected

    def test_aller_retour_secondes(self):
        for seconds in (0, 60, 300, 3600, 3660):
            assert rewrite.to_seconds(rewrite.humanize(seconds)) == seconds


# ── Alignement multi-mode (jeu v7) ───────────────────────────────────────────

class TestPerimetreDesModes:
    """Le périmètre réécrit doit être celui qu'on déclare, ni plus ni moins.

    C'est le défaut qui a motivé cette classe : la correction livrée en production
    (`tt3`) alignait la voiture ET le vélo, alors que le jeu mesuré (`v6`) n'alignait
    que la voiture. Le chiffre publié ne décrivait donc pas ce qui tournait.
    """

    def test_voiture_seule_laisse_le_velo_intact(self):
        out, stats = _rewrite(0, modes=("car",))
        assert "· Déverrouiller le vélo : 1 minute." in out
        assert "· Attacher le vélo à 'work' : 1 minute." in out
        assert "dont 2 minutes d'accès et d'attache" in out
        assert stats["options_bicycle"] == 0

    def test_les_deux_modes_alignent_les_deux(self):
        out, stats = _rewrite(0, modes=("car", "bicycle"))
        assert "· Déverrouiller le vélo : 0 minute." in out
        assert "· Attacher le vélo à 'work' : 0 minute." in out
        assert "· Rejoindre la voiture : 0 minute." in out
        assert stats["options_car"] == 1 and stats["options_bicycle"] == 1

    def test_chaque_mode_garde_sa_clause_terminale(self):
        """« d'accès et de stationnement » pour la voiture, « d'accès et d'attache »
        pour le vélo : les intervertir donnerait un texte que la production n'écrit
        jamais."""
        out, _ = _rewrite(2, modes=("car", "bicycle"))
        assert "dont 4 minutes d'accès et de stationnement" in out
        assert "dont 4 minutes d'accès et d'attache" in out

    def test_le_temps_de_trajet_de_chaque_mode_est_intact(self):
        """Conduite et trajet à vélo ne se recalculent pas sans rejouer le routage."""
        out, _ = _rewrite(0, modes=("car", "bicycle"))
        assert "· Conduite : 5 minutes." in out
        assert "· Trajet à vélo : 10 minutes." in out

    def test_la_marche_nest_jamais_touchee(self):
        """La marche est porte-à-porte : elle n'a pas de temps terminal à aligner."""
        for modes in (("car",), ("car", "bicycle")):
            out, _ = _rewrite(0, modes=modes)
            assert "- [0] foot: Durée estimée : 25 minutes. Distance : 2.0 km." in out

    def test_les_deux_modes_tirent_independamment(self):
        """La clé de tirage porte le mode : sans ce préfixe, voiture et vélo d'une même
        option recevraient le MÊME temps terminal, et le jeu ne porterait qu'une seule
        source de variation au lieu de deux."""
        pmf = {"0": 0.5, "4": 0.5}
        pairs = {(rewrite.draw_minutes(pmf, f"car:{i}:access"),
                  rewrite.draw_minutes(pmf, f"bicycle:{i}:access")) for i in range(200)}
        assert len(pairs) == 4, pairs

    def test_un_mode_inconnu_est_refuse(self):
        with pytest.raises(KeyError):
            _rewrite(0, modes=("scooter",))

    def test_les_specs_couvrent_les_deux_modes_vehicules(self):
        assert set(rewrite.MODE_SPECS) == {"car", "bicycle"}
        for mode, spec in rewrite.MODE_SPECS.items():
            assert {"option", "access", "egress", "main", "clause",
                    "spatialise"} <= set(spec)
        # Seule la voiture est spatialisée : le vélo n'a que 2 047 trajets enquêtés,
        # ses cellules par couronne seraient trop minces.
        assert rewrite.MODE_SPECS["car"]["spatialise"] is True
        assert rewrite.MODE_SPECS["bicycle"]["spatialise"] is False
