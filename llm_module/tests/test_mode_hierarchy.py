"""La hiérarchie des modes : une seule source, sourcée, et qui refuse de deviner.

Ce que ces tests verrouillent n'est pas une convention de code mais un **verdict
d'enquête** : l'ordre dans lequel un déplacement multimodal reçoit son mode principal.
Deux crans surprennent et sont donc testés nommément — le bus passe avant le train, et
toute la famille collective passe avant la voiture.

Trois gardes contre la vacuité (« l'absence de mesure produit le score parfait ») :
une ressource absente, une famille manquante et une version inattendue doivent lever, pas
se replier sur un ordre écrit en dur.
"""

from __future__ import annotations

import json

import pytest

from llm_module.core.mode_hierarchy import (DEFAULT_RESOURCE, REQUIRED_VERSION,
                                            ModeHierarchy, hierarchy)


# ── L'ordre lui-même ────────────────────────────────────────────────────────────

def test_l_ordre_est_celui_de_l_annexe_publiee():
    """Rapport AUAT/CEREMA, annexe « Hiérarchie des modes », p. 53, ramenée aux jambes."""
    assert hierarchy().families == (
        "metro", "tram", "cableway", "bus", "rail", "car", "motorbike", "bicycle", "foot")


def test_le_bus_passe_avant_le_train():
    """L'arbitrage du ticket 022 : bus Tisséo au rang 4, TER liO au rang 8.

    Mesuré sur les microdonnées : 34 des 35 déplacements mixtes bus/autocar ↔ train
    tranchés par l'enquête sont codés bus. Un itinéraire « autocar liO + TER » est donc un
    déplacement en transports collectifs de surface, et non un déplacement en train.
    """
    h = hierarchy()
    assert h.primary_family(("foot", "bus", "rail", "foot")) == "bus"
    assert h.primary_family(("foot", "rail", "foot")) == "rail"
    assert h.primary_label(("foot", "bus", "rail", "foot")) == "Transports_collectifs"
    assert h.primary_label(("foot", "rail", "foot")) == "Train"


def test_tout_le_collectif_passe_avant_la_voiture():
    """Le cran de l'axe A7 : 760 des 770 déplacements mixtes sont codés « TC ».

    C'est celui que `move_logger` avait à l'envers — il testait `_CAR_MODES` en premier.
    """
    h = hierarchy()
    for collectif in ("metro", "tram", "cableway", "bus", "rail"):
        assert h.primary_family((collectif, "car")) == collectif, collectif
    assert h.primary_label(("car", "bus")) == "Transports_collectifs"


def test_la_marche_est_le_dernier_rang():
    """Rang 36, « Marche à pied UNIQUEMENT » — et c'est mesuré, pas supposé.

    Dans les microdonnées, `MODP = 01` désigne exactement les déplacements sans aucun
    trajet mécanisé : 14 842 sur 54 585, et aucun des 39 743 déplacements détaillés.
    """
    h = hierarchy()
    assert h.family_rank["foot"] == max(h.family_rank.values())
    assert h.primary_family(("foot",)) == "foot"
    for autre in ("bus", "rail", "car", "bicycle", "metro"):
        assert h.primary_family(("foot", autre)) == autre, autre


def test_le_car_scolaire_est_un_autocar():
    """L'option synthétique du ticket 030 vaut le rang 6 (« autres autocars — scolaires »).

    Elle est donc du transport collectif, au même rang que le bus, et **pas** une voiture —
    même si GAMA l'affiche avec le marqueur `__DIRECT_CAR__` pour l'interpoler.
    """
    h = hierarchy()
    assert h.primary_family(("school_bus",)) == "bus"
    assert h.primary_label(("school_bus",)) == "Transports_collectifs"
    assert h.primary_canonical(("school_bus",)) == "public_transport"


@pytest.mark.parametrize("alias,famille", [
    ("subway", "metro"), ("tramway", "tram"), ("gondola", "cableway"),
    ("funicular", "cableway"), ("bike", "bicycle"), ("walk", "foot"),
    ("__car__", "car"), ("METRO", "metro"), (" bus ", "bus"),
])
def test_les_alias_historiques_sont_reconnus(alias, famille):
    """Les caches et les libellés portent encore ces écritures : les ignorer les perdrait."""
    assert hierarchy().family_of(alias) == famille


# ── Ce qui ne doit PAS être deviné ──────────────────────────────────────────────

def test_un_mode_inconnu_rend_none_et_non_le_fourre_tout_d_a_cote():
    """`None` est une réponse à compter, pas un défaut à absorber.

    Le défaut du Téléo (2026-08-26) et celui du TER (2026-09-04) sont tous deux des modes
    tombés dans la catégorie d'à côté sans une ligne de journal.
    """
    h = hierarchy()
    assert h.family_of("hovercraft") is None
    assert h.family_of("") is None
    assert h.family_of(None) is None
    assert h.primary_family(()) is None
    assert h.primary_family(("hovercraft", "zeppelin")) is None
    assert h.primary_label(("hovercraft",)) is None
    # Un mode inconnu ne masque pas un mode connu.
    assert h.primary_family(("hovercraft", "bus")) == "bus"


def test_une_ressource_absente_leve():
    with pytest.raises(FileNotFoundError, match="Hiérarchie des modes absente"):
        ModeHierarchy.load(DEFAULT_RESOURCE.parent / "il_ny_a_pas_de_fichier_ici.json")


def test_une_version_inattendue_leve(tmp_path):
    """Une ressource d'une autre version n'a pas été contrôlée sur les microdonnées."""
    doc = json.loads(DEFAULT_RESOURCE.read_text(encoding="utf-8"))
    doc["version"] = "mh0"
    chemin = tmp_path / "vieille.json"
    chemin.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match=REQUIRED_VERSION):
        ModeHierarchy.load(chemin)


def test_une_famille_manquante_leve(tmp_path):
    """Garde anti-vacuité : sans le rail, « foot,rail,foot » deviendrait de la marche."""
    doc = json.loads(DEFAULT_RESOURCE.read_text(encoding="utf-8"))
    doc["ordre_familles"] = [f for f in doc["ordre_familles"] if f != "rail"]
    chemin = tmp_path / "sans_rail.json"
    chemin.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="rail"):
        ModeHierarchy.load(chemin)


def test_une_ressource_sans_mode_de_jambe_leve(tmp_path):
    """Elle ne classerait rien, donc elle ne signalerait aucune erreur."""
    doc = json.loads(DEFAULT_RESOURCE.read_text(encoding="utf-8"))
    doc["rang_jambe"] = {}
    chemin = tmp_path / "vide.json"
    chemin.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="aucun mode de jambe"):
        ModeHierarchy.load(chemin)


# ── Les vocabulaires servis ─────────────────────────────────────────────────────

def test_l_ordre_canonique_derive_de_l_ordre_des_familles():
    """C'est cet ordre que doit suivre la cascade de `mode_choice._MODE_KEYWORDS`."""
    assert hierarchy().canonical_order() == (
        "public_transport", "train", "car", "motorbike", "cycling", "walking")


def test_l_ordre_des_libelles_derive_de_l_ordre_des_familles():
    assert hierarchy().label_order() == (
        "Transports_collectifs", "Train", "Voiture Privée", "Deux-roues motorisé",
        "Vélo", "Marche")


def test_la_ressource_porte_sa_provenance():
    """Une cible gelée sans provenance n'est pas recoupable — même règle que les autres."""
    doc = json.loads(DEFAULT_RESOURCE.read_text(encoding="utf-8"))
    provenance = doc["provenance"]
    assert provenance["fichiers"], "empreintes des microdonnées absentes"
    assert all(len(h) == 64 for h in provenance["fichiers"].values()), provenance
    assert provenance["gele_le"] and provenance["par"].endswith("export_mode_hierarchy.py")
    assert doc["source_publiee"]["page"] == 53
