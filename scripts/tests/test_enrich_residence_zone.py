"""Pose du trait « couronne de résidence » sur une population synthétique (ticket 021).

C'est l'étape qui crée le trait : sans elle, la couronne d'un domicile reste devinée à sa
distance à l'hypercentre, et 24,4 % des personas sont comparés à la cible d'une autre zone.
Ce qui est vérifié ici :

- le trait est posé sous les noms que le journal et la synthèse relisent, avec les libellés
  de la référence EMC², **et la commune vient avec** — c'est elle qui rend le classement
  auditable ;
- **trois situations, trois écritures distinctes** : une couronne quand le domicile est dans
  le périmètre, `hors périmètre` quand il est connu et dehors, **aucun trait** quand il n'a
  pas de coordonnées. Confondre les deux dernières, c'est affirmer « dehors » de quelqu'un
  dont on ne sait rien ;
- **la commune ne s'invente jamais** : un domicile hors couche n'en reçoit pas, et une zone
  résolue mais absente de la table ne reçoit rien du tout ;
- l'enrichissement est **idempotent** : le trait est observé, pas tiré, donc rejouer ne
  change pas un octet ;
- `--check` contrôle ce que l'enrichissement maîtrise — couverture, accord entre le
  classement par CODE et le classement par APPARTENANCE géométrique, modalités, taux hors
  périmètre — et **rien d'autre** : l'écart au cadrage de population est rapporté avec son
  propre code de sortie, parce qu'il mesure le tirage (axe A9) et non ce trait ;
- **`--out` existe pour les populations épinglées** par un manifeste de jeu gelé : les
  réécrire en place casserait quatre jeux d'un coup.

Hors ligne, sans les données PROGEDO : la table des couronnes est construite à la main et
le résolveur de zones est remplacé par un doublon qui rattache selon la latitude.
"""

from __future__ import annotations

import json

import pytest

from llm_module.core.population_reference import COURONNES, OUT_OF_PERIMETER
from llm_module.core.residence_zone import (
    COMMUNE_TRAIT_KEY,
    INSEE_TRAIT_KEY,
    TRAIT_KEY,
    CouronneTable,
    ResidenceZoneError,
    ZoneCouronne,
)
from scripts.data.population import enrich_residence_zone as enrich_module

# Quatre zones fines, une par couronne, sur quatre secteurs distincts.
ZONES = [
    ZoneCouronne("101101000", "101", "Toulouse", "31555", "Toulouse"),
    ZoneCouronne("201101000", "201", "1ere couronne", "31069", "Blagnac"),
    ZoneCouronne("301101000", "301", "2eme couronne", "31088", "Bruguières"),
    ZoneCouronne("401101000", "401", "3eme couronne", "31009", "Alan"),
]


class FakeZone:
    """Ce que `ZoneResolver.resolve` rend d'utile pour ce trait : un code de zone fine."""

    def __init__(self, zf: str) -> None:
        self.zf = zf


class FakeResolver:
    """Rattache par tranche de latitude, et rend `None` hors des tranches connues.

    La latitude porte l'information : au-dessus de 44, on est « hors couche ». Ça évite
    d'embarquer la couche SIG d'accès restreint dans un test unitaire.
    """

    MAPPING = {43: "101101000", 42: "201101000", 41: "301101000", 40: "401101000"}

    def resolve(self, lat, lon):
        code = self.MAPPING.get(int(lat)) if lat is not None else None
        return FakeZone(code) if code else None


class FakeGeometry:
    """Classification de référence : ici, la vérité par construction du test."""

    def __init__(self, mapping: dict) -> None:
        self._mapping = mapping

    def classify(self, lat, lon):
        if lat is None or lon is None:
            return ""
        return self._mapping.get(int(lat), OUT_OF_PERIMETER)


GEOMETRY_TRUTH = {43: "Toulouse", 42: "1ere couronne", 41: "2eme couronne",
                  40: "3eme couronne"}


def table() -> CouronneTable:
    return CouronneTable(ZONES)


def person(lat, lon=1.44, **traits) -> dict:
    return {"identity": {"home": {"lat": lat, "lon": lon}, "traits_json": dict(traits)}}


def traits(person_dict: dict) -> dict:
    return person_dict["identity"]["traits_json"]


# ── La pose du trait ─────────────────────────────────────────────────────────

def test_le_trait_porte_la_couronne_et_la_commune():
    people = [person(43.6), person(42.5)]
    counts = enrich_module.enrich(people, table(), FakeResolver())

    assert traits(people[0])[TRAIT_KEY] == "Toulouse"
    assert traits(people[0])[COMMUNE_TRAIT_KEY] == "Toulouse"
    assert traits(people[0])[INSEE_TRAIT_KEY] == "31555"
    assert traits(people[1])[TRAIT_KEY] == "1ere couronne"
    assert traits(people[1])[COMMUNE_TRAIT_KEY] == "Blagnac"
    assert counts["Toulouse"] == 1 and counts["1ere couronne"] == 1


def test_hors_couche_recoit_hors_perimetre_et_aucune_commune():
    """`hors périmètre` est une valeur ; la commune, elle, ne s'invente pas."""
    people = [person(44.9)]
    counts = enrich_module.enrich(people, table(), FakeResolver())

    assert traits(people[0])[TRAIT_KEY] == OUT_OF_PERIMETER
    assert COMMUNE_TRAIT_KEY not in traits(people[0])
    assert INSEE_TRAIT_KEY not in traits(people[0])
    assert counts[OUT_OF_PERIMETER] == 1
    # Et ce n'est pas une couronne : le confondre avec la 3ᵉ est l'écart A4 du ticket 020.
    assert OUT_OF_PERIMETER not in COURONNES


def test_sans_coordonnees_aucun_trait_et_l_heritage_est_retire():
    """Ni dedans ni dehors : on ne sait pas. Écrire « dehors » serait une affirmation."""
    people = [person(None, None, **{TRAIT_KEY: "Toulouse",
                                    COMMUNE_TRAIT_KEY: "Toulouse",
                                    INSEE_TRAIT_KEY: "31555"})]
    counts = enrich_module.enrich(people, table(), FakeResolver())

    assert TRAIT_KEY not in traits(people[0])
    assert COMMUNE_TRAIT_KEY not in traits(people[0])
    assert counts["sans_domicile"] == 1


def test_zone_resolue_mais_absente_de_la_table_ne_pose_rien():
    """La couche et la table ne décrivent pas le même périmètre : on ne devine pas."""
    partielle = CouronneTable([ZONES[0]])
    people = [person(42.5)]  # résolu en 201101000, absent de la table partielle
    counts = enrich_module.enrich(people, partielle, FakeResolver())

    assert TRAIT_KEY not in traits(people[0])
    assert counts["zone_hors_table"] == 1


def test_une_valeur_changee_est_comptee():
    people = [person(43.6, **{TRAIT_KEY: "3eme couronne"})]
    counts = enrich_module.enrich(people, table(), FakeResolver())

    assert traits(people[0])[TRAIT_KEY] == "Toulouse"
    assert counts["valeur_changee"] == 1


def test_l_enrichissement_est_idempotent():
    """Le trait est OBSERVÉ : deux passes ne peuvent pas différer."""
    people = [person(43.6), person(41.2), person(44.9), person(None, None)]
    enrich_module.enrich(people, table(), FakeResolver())
    premier = json.dumps(people, ensure_ascii=False, sort_keys=True)
    enrich_module.enrich(people, table(), FakeResolver())
    assert json.dumps(people, ensure_ascii=False, sort_keys=True) == premier


def test_la_structure_de_population_est_lue_ou_refusee():
    liste = [person(43.6)]
    assert enrich_module.people_of(liste) is liste
    enveloppe = {"people": liste}
    assert enrich_module.people_of(enveloppe) is liste
    with pytest.raises(ResidenceZoneError, match="structure de population"):
        enrich_module.people_of({"agents": liste})


# ── Les portes de `--check` ──────────────────────────────────────────────────

def audit_of(people, zones=None):
    return enrich_module.audit(people, table(), zones or FakeGeometry(GEOMETRY_TRUTH))


def test_une_population_conforme_ne_declenche_aucune_porte():
    people = [person(43.6), person(42.5), person(41.2), person(40.1)]
    counts = enrich_module.enrich(people, table(), FakeResolver())
    assert enrich_module.report(counts, audit_of(people)) == []


def test_un_desaccord_avec_la_geometrie_fait_echouer():
    """La porte du ticket : le classement par code doit égaler celui par appartenance."""
    people = [person(43.6)]
    counts = enrich_module.enrich(people, table(), FakeResolver())
    menteuse = FakeGeometry({43: "2eme couronne"})

    failures = enrich_module.report(counts, audit_of(people, menteuse))
    assert failures and "APPARTENANCE" in failures[0]


def test_une_modalite_hors_referentiel_fait_echouer():
    people = [person(43.6, **{TRAIT_KEY: "4eme couronne"})]
    checks = audit_of(people)  # sans passer par enrich : le trait est déjà là, faux
    failures = enrich_module.report({}, checks)
    assert any("hors référentiel" in f for f in failures)


def test_un_persona_localise_sans_valeur_fait_echouer():
    people = [person(43.6)]  # jamais enrichi
    failures = enrich_module.report({}, audit_of(people))
    assert any("couverture" in f for f in failures)


def test_un_taux_hors_perimetre_massif_fait_echouer():
    """Au-delà du seuil d'alarme, ce n'est plus une queue : c'est un autre périmètre."""
    people = [person(44.9) for _ in range(3)] + [person(43.6) for _ in range(7)]
    counts = enrich_module.enrich(people, table(), FakeResolver())
    failures = enrich_module.report(counts, audit_of(people))
    assert any("hors périmètre" in f for f in failures)
    assert enrich_module.MAX_OUT_OF_PERIMETER_RATE == 0.15


def test_le_cadrage_exclut_le_hors_perimetre_du_denominateur():
    """Les hors-périmètre n'ont aucune cible : les diluer comparerait deux grandeurs."""
    lignes, _ = enrich_module.framing_gap({"Toulouse": 1, OUT_OF_PERIMETER: 1})
    assert lignes["Toulouse"]["observe"] == pytest.approx(100.0)
    assert set(lignes) == set(COURONNES)


def test_le_cadrage_n_est_pas_une_porte():
    """Il mesure le tirage (A9), pas ce trait : il ne peut pas faire échouer `report`."""
    people = [person(43.6) for _ in range(10)]  # 100 % à Toulouse : cadrage très faux
    counts = enrich_module.enrich(people, table(), FakeResolver())
    assert enrich_module.report(counts, audit_of(people)) == []
    assert enrich_module.print_framing(audit_of(people)) is True
    assert enrich_module.EXIT_FRAMING_GAP == 4


# ── L'écriture ───────────────────────────────────────────────────────────────

def test_destination_ecrit_en_place_par_defaut(tmp_path):
    source = tmp_path / "population_1000.json"
    assert enrich_module.destination(source, None, 1) == source


def test_destination_respecte_out_fichier_et_dossier(tmp_path):
    """`--out` protège une population épinglée par un manifeste de jeu gelé."""
    source = tmp_path / "population_1000.json"
    cible = tmp_path / "ailleurs" / "copie.json"
    assert enrich_module.destination(source, cible, 1) == cible

    dossier = tmp_path / "sorties"
    dossier.mkdir()
    assert enrich_module.destination(source, dossier, 1) == dossier / source.name
    # Plusieurs entrées : `--out` ne peut être qu'un dossier, sinon on écraserait.
    assert enrich_module.destination(source, dossier, 3) == dossier / source.name
