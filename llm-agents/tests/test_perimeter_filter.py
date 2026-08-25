"""Le filtre d'admission de la population porte sur le PÉRIMÈTRE, pas sur un rectangle.

Ticket 026, étage 3. Ce qui est verrouillé ici :

- **le trait décide, pas la géométrie** : un domicile de 3ᵉ couronne à 60 km du Capitole
  est admis, alors que le rectangle des arrêts Tisséo l'écartait. Mesuré au ticket 026 :
  ce rectangle ne contenait que 221 des 453 communes de l'enquête ;
- **`hors périmètre` est un rejet explicite**, pas un oubli : le domicile est connu et il
  est hors des 453 communes, il n'a aucune cible par zone ;
- **une population sans le trait ne passe pas en silence** : le filtre retombe sur la
  bbox — comportement d'avant — et une **alarme** dit que le périmètre n'est pas garanti.
  Sans elle, on croirait filtrer sur l'enquête alors qu'on filtre sur le réseau TC ;
- **le filtre reste sur les 453 communes**, même quand le cadre de tirage est restreint à
  la Haute-Garonne : graver la limitation du cadre dans le runtime obligerait à la
  déterrer quand le cadre s'élargira.
"""

from __future__ import annotations

import pytest

from llm_module.core.population_reference import COURONNES, OUT_OF_PERIMETER
from models import BBox, Location, PersonalIdentity, Person, PersonState

# Le rectangle historique : emprise des arrêts Tisséo ± 0,05°.
TISSEO_BBOX = BBox(min_lon=1.1010, min_lat=43.3464, max_lon=1.7405, max_lat=43.7999)

# Un domicile de 3ᵉ couronne au sud du périmètre — dans l'enquête, hors du rectangle.
LOIN = (43.20, 1.30)
# Un domicile toulousain, dans les deux.
CENTRE = (43.6045, 1.4440)


def person(lat, lon, zone=None, pid="p1") -> Person:
    traits = {"name": "Test"}
    if zone is not None:
        traits["residence_zone"] = zone
    return Person(
        person_id=pid,
        identity=PersonalIdentity(
            name="Test", traits_json=traits,
            home=Location(lon=lon, lat=lat), activities=[]),
        state=PersonState(last_location=None, last_activity_index=0),
    )


def verdict(p, bbox=TISSEO_BBOX):
    from inputs.population.eqasim_loader import _perimeter_verdict

    return _perimeter_verdict(p, bbox)


# ── Le trait décide ──────────────────────────────────────────────────────────

def test_toutes_les_couronnes_sont_admises_meme_hors_du_rectangle():
    for zone in COURONNES:
        admis, motif = verdict(person(*LOIN, zone=zone))
        assert admis, f"{zone} rejetée alors qu'elle est dans l'enquête ({motif})"


def test_hors_perimetre_est_un_rejet_explicite():
    admis, motif = verdict(person(*CENTRE, zone=OUT_OF_PERIMETER))
    assert not admis
    assert motif == OUT_OF_PERIMETER
    # Et ce n'est pas la géométrie qui a tranché : le point est en plein centre.
    assert TISSEO_BBOX.min_lat <= CENTRE[0] <= TISSEO_BBOX.max_lat


def test_une_valeur_de_zone_inconnue_est_rejetee_en_le_disant():
    admis, motif = verdict(person(*CENTRE, zone="4eme couronne"))
    assert not admis
    assert "zone inconnue" in motif


def test_sans_domicile_pas_d_admission():
    p = person(*CENTRE, zone="Toulouse")
    p.identity.home = None
    admis, motif = verdict(p)
    assert not admis and motif == "sans domicile"


# ── Le repli, et son alarme ──────────────────────────────────────────────────

def test_sans_trait_le_filtre_retombe_sur_la_bbox():
    """Comportement d'avant le ticket 021, conservé pour les populations anciennes."""
    assert verdict(person(*CENTRE))[0] is True
    admis, motif = verdict(person(*LOIN))
    assert not admis and "trait absent" in motif


def test_sans_trait_ni_bbox_tout_passe():
    """Aucun critère disponible : on n'invente pas un rejet."""
    assert verdict(person(*LOIN), bbox=None)[0] is True


@pytest.fixture
def alarmes():
    """Capture les ERROR de loguru — `caplog` ne les voit pas (pas de propagation)."""
    from loguru import logger

    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(m), level="ERROR")
    yield messages
    logger.remove(sink)


def test_une_population_sans_trait_leve_une_alarme(alarmes):
    from inputs.population.eqasim_loader import _apply_perimeter_filter

    people = [person(*CENTRE, pid="a"), person(*CENTRE, zone="Toulouse", pid="b")]
    retenus = _apply_perimeter_filter(people, TISSEO_BBOX, "test")
    assert len(retenus) == 2
    assert any("[ALARME]" in m and "residence_zone" in m for m in alarmes), (
        "une population non enrichie doit alarmer : sinon on croit filtrer sur "
        "l'enquête alors qu'on filtre sur le réseau TC")


def test_une_population_enrichie_n_alarme_pas(alarmes):
    from inputs.population.eqasim_loader import _apply_perimeter_filter

    people = [person(*LOIN, zone="3eme couronne", pid="a"),
              person(*CENTRE, zone="Toulouse", pid="b"),
              person(*CENTRE, zone=OUT_OF_PERIMETER, pid="c")]
    retenus = _apply_perimeter_filter(people, TISSEO_BBOX, "test")
    assert [p.person_id for p in retenus] == ["a", "b"]
    assert not [m for m in alarmes if "[ALARME]" in m]


# ── Le cadre de tirage n'est pas le filtre ───────────────────────────────────

def test_le_filtre_porte_sur_les_453_pas_sur_le_cadre_restreint():
    """Un domicile d'une commune du périmètre hors Haute-Garonne reste admissible.

    Le cadre de tirage de la version légère du ticket 026 est restreint au 31, mais le
    filtre d'admission ne l'est pas : sinon l'élargissement du cadre demanderait de
    modifier le runtime, et la limitation serait gravée là où personne ne la cherche.
    """
    from llm_module.core.residence_zone import CommuneTable

    table = CommuneTable.load()
    hors_31 = [c for c in table.communes() if not c.startswith("31")]
    assert hors_31, "le périmètre couvre bien plusieurs départements"
    # La couronne de l'une d'elles suffit à décider de l'admission.
    zone = table.couronne_of_insee(hors_31[0])
    assert verdict(person(*LOIN, zone=zone))[0] is True
