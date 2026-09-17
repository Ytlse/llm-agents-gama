"""Ticket 077, lot A — le vocabulaire des modes.

Contrat : `specs/ticket_077/tests.md` § A. Les identifiants de cas (A1, A7…) y renvoient.

Ces tests auraient échoué avant le 2026-09-15 : le run de trente jours du ticket 075 a produit
231 concepts dont 211 sans axe d'objet, parce que `mode_canonique` ne connaissait que les
étiquettes de jambes alors que le schéma de réflexion impose les modes canoniques.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm.axes import MODES_INCONNUS, mode_canonique
from mobility_core.mode_hierarchy import hierarchy

# Les sept valeurs que le schéma JSON de `stm_reflection` autorise dans le champ `mode`.
# Recopiées ici À DESSEIN : si le schéma change, ce test doit échouer et non s'adapter en
# silence — c'est le seul endroit qui relie les deux fichiers.
MODES_DU_SCHEMA = (
    "walking",
    "cycling",
    "car",
    "public_transport",
    "train",
    "motorbike",
    "any",
)


@pytest.mark.parametrize(
    "mode",
    [m for m in MODES_DU_SCHEMA if m != "any"],
)
def test_A1_un_mode_canonique_est_son_propre_canonique(mode):
    """A1 — les six modes du schéma qui désignent un mode se rendent tels quels."""
    assert mode_canonique(mode) == mode


@pytest.mark.parametrize(
    "jambe, attendu",
    [
        ("foot", "walking"),
        ("bus", "public_transport"),
        ("bicycle", "cycling"),
        ("metro", "public_transport"),
        ("rail", "train"),
        ("school_bus", "public_transport"),
    ],
)
def test_A2_les_etiquettes_de_jambes_sont_inchangees(jambe, attendu):
    """A2 — la lecture des jambes ne bouge pas : c'est elle qui porte les parts modales."""
    assert mode_canonique(jambe) == attendu


def test_A3_le_mode_principal_l_emporte_toujours():
    """A3 — « foot,bus,foot » reste un trajet en transport collectif, pas une marche."""
    assert mode_canonique("foot,bus,foot") == "public_transport"
    assert mode_canonique("foot,metro,foot,bus,foot") == "public_transport"


def test_A4_any_ne_devient_pas_un_axe():
    """A4 — `any` dit « ce concept ne porte pas sur un mode » : il ne doit produire aucun axe."""
    assert mode_canonique("any") is None


def test_A4bis_any_n_est_pas_compte_comme_un_mode_inconnu():
    """A4 — et il n'est pas une anomalie : le compter noierait le compteur des vraies."""
    MODES_INCONNUS.pop("any", None)
    mode_canonique("any")
    assert "any" not in MODES_INCONNUS


def test_A5_un_mot_hors_des_deux_vocabulaires_est_compte():
    """A5 — l'inconnu reste `None`, compté, et jamais rangé dans un fourre-tout."""
    MODES_INCONNUS.pop("teleport", None)
    assert mode_canonique("teleport") is None
    assert MODES_INCONNUS.get("teleport") == 1
    mode_canonique("teleport")
    assert MODES_INCONNUS.get("teleport") == 2


@pytest.mark.parametrize("vide", [None, "", "   ", ",", " , "])
def test_A6_les_valeurs_vides_ne_levent_pas(vide):
    """A6 — un champ absent ne doit jamais faire tomber une consolidation."""
    assert mode_canonique(vide) is None


def test_A7_la_liste_des_canoniques_vient_de_la_ressource_gelee():
    """A7 — aucune liste de modes écrite en dur dans `axes.py`.

    Le test lit la ressource et vérifie que TOUT ce qu'elle déclare traverse. Une liste
    recopiée dans le module divergerait le jour où la hiérarchie bouge.
    """
    for canonique in hierarchy().canonical_order():
        assert mode_canonique(canonique) == canonique

    source = (Path(__file__).resolve().parents[1] / "llm" / "axes.py").read_text(
        encoding="utf-8"
    )
    for canonique in hierarchy().canonical_order():
        if canonique == "car":
            continue  # apparaît légitimement dans la prose du module
        assert f'"{canonique}"' not in source, (
            f"« {canonique} » est écrit en dur dans axes.py : la liste doit venir de la "
            f"ressource gelée, pas du module"
        )


@pytest.mark.parametrize(
    "brut, attendu",
    [
        ("  walking ", "walking"),
        ("PUBLIC_TRANSPORT", "public_transport"),
        ("Car", "car"),
        (" FOOT", "walking"),
    ],
)
def test_A8_casse_et_espaces(brut, attendu):
    """A8 — le modèle ne garantit ni la casse ni l'absence d'espaces."""
    assert mode_canonique(brut) == attendu


def test_A9_garde_aucun_concept_sans_axe_objet_quand_le_mode_est_renseigne():
    """A9 — la règle de garde du ticket, celle qui aurait dû échouer le 14 septembre.

    Tout mode que le schéma autorise, `any` excepté, doit produire un axe d'objet. C'est
    exactement ce qui manquait : six valeurs sur sept rendaient `None`, et les alarmes émises
    par le module n'ont averti personne au milieu de 355 000 lignes de journal.
    """
    sans_axe = [
        m for m in MODES_DU_SCHEMA if m != "any" and mode_canonique(m) is None
    ]
    assert not sans_axe, (
        f"ces modes du schéma ne produisent aucun axe d'objet : {sans_axe} — les concepts "
        f"qui les portent seraient invisibles au panier et à la correction"
    )
