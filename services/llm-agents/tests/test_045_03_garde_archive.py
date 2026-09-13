"""Ticket 045, bloc F — une population archivée ne se lit pas par accident.

R15 : `resoudre_population` refuse un chemin sous `data/population/archive/`, sauf mention
explicite `archivee_confirmee`, et le refus nomme la cohorte de référence.

Pourquoi un refus dans le code, et pas seulement une phrase dans un README : les 36 exécutions
de la plateforme ont toutes lu la cohorte v1 alors que la référence de l'article est la v5, et
rien ne s'y est opposé. Un garde-fou qui n'existe que dans la prose ne se déclenche jamais. Le
refus doit être bruyant, et sa levée doit laisser une trace — un motif écrit dans la définition,
pas un drapeau booléen qu'on coche sans y penser.
"""

from __future__ import annotations

import hashlib
import json

import pytest
import yaml

from experiences.population import (
    PopulationArchivee,
    charger_population,
    info_population,
    resoudre_population,
)

HOME = {"lon": 1.4400, "lat": 43.6000, "public_transport": True, "zone": "centre"}
WORK = {"lon": 1.4500, "lat": 43.6100, "public_transport": True, "zone": "nord"}


def _population_minimale() -> list[dict]:
    traits = {
        "age": 35,
        "gender": "Female",
        "main_occupation": "actif",
        "household_size": 1,
        "number_of_cars": 1,
        "has_driving_license": True,
        "personal_bike": "vélo normal",
        "residence_zone": "Toulouse",
    }
    acts = [
        {
            "id": "a0",
            "scheduled_start_time": 20 * 3600.0,
            "start_time": 0.0,
            "end_time": 8 * 3600.0,
            "purpose": "home",
            "location": HOME,
        },
        {
            "id": "a1",
            "scheduled_start_time": 8 * 3600.0,
            "start_time": 9 * 3600.0,
            "end_time": 20 * 3600.0,
            "purpose": "work",
            "location": WORK,
        },
    ]
    return [
        {
            "person_id": "p1",
            "identity": {"traits_json": traits, "home": HOME, "activities": acts},
            "state": {"last_activity_index": 0},
            "is_llm_based": True,
        }
    ]


def _cohorte(racine, nom: str):
    """Écrit une cohorte scellée sous `racine/nom` et rend son dossier."""
    d = racine / nom
    d.mkdir(parents=True)
    fichier = d / "population.json"
    fichier.write_text(json.dumps(_population_minimale()), encoding="utf-8")
    sha = hashlib.sha256(fichier.read_bytes()).hexdigest()
    (d / "MANIFEST.yaml").write_text(
        yaml.safe_dump(
            {"nom": nom, "population": {"fichier": "population.json", "sha256": sha}}
        ),
        encoding="utf-8",
    )
    return d


@pytest.fixture
def arborescence(tmp_path):
    """`data/population/` avec une cohorte vivante et une cohorte archivée."""
    pop = tmp_path / "data" / "population"
    vivante = _cohorte(pop, "population_1000_AAMAS_v5")
    archivee = _cohorte(pop / "archive", "population_1000_AAMAS")
    return {"racine": pop, "vivante": vivante, "archivee": archivee}


# ── Le refus ────────────────────────────────────────────────────────────────


def test_r15_une_cohorte_archivee_est_refusee(arborescence):
    with pytest.raises(PopulationArchivee):
        resoudre_population(arborescence["archivee"])


def test_r15_le_refus_nomme_le_chemin_et_la_marche_a_suivre(arborescence):
    """Un refus qui ne dit pas quoi faire se contourne au jugé, ou se subit."""
    with pytest.raises(PopulationArchivee) as e:
        resoudre_population(arborescence["archivee"])
    message = str(e.value)
    assert "population_1000_AAMAS" in message
    assert "archive" in message
    assert "archivee_confirmee" in message, "le refus doit dire comment le lever"


def test_r15_le_fichier_nu_sous_archive_est_refuse_aussi(arborescence):
    """Le garde porte sur l'emplacement, pas sur la forme : un JSON nu sous `archive/` aussi."""
    nu = arborescence["racine"] / "archive" / "vieille_population.json"
    nu.write_text(json.dumps(_population_minimale()), encoding="utf-8")
    with pytest.raises(PopulationArchivee):
        resoudre_population(nu)


def test_r15_un_sous_dossier_profond_de_archive_est_refuse(arborescence):
    """`archive/2026/pop/` est sous archive : la profondeur ne contourne pas le garde."""
    profonde = _cohorte(arborescence["racine"] / "archive" / "2026", "vieille")
    with pytest.raises(PopulationArchivee):
        resoudre_population(profonde)


# ── La levée explicite ──────────────────────────────────────────────────────


def test_r15_un_motif_explicite_leve_le_refus(arborescence):
    fichier, manifest = resoudre_population(
        arborescence["archivee"], archivee_confirmee="témoin du ticket 045"
    )
    assert fichier.is_file()
    assert manifest is not None


def test_r15_la_levee_est_journalisee_avec_son_motif(arborescence, caplog):
    """Le motif doit apparaître dans le journal : une dérogation silencieuse n'en est pas une."""
    from loguru import logger

    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(str(m)), level="WARNING")
    try:
        resoudre_population(
            arborescence["archivee"], archivee_confirmee="témoin du ticket 045"
        )
    finally:
        logger.remove(sink)
    assert any("témoin du ticket 045" in m for m in messages), messages


def test_r15_un_motif_vide_ne_leve_rien(arborescence):
    """`archivee_confirmee: ""` ou `True` n'est pas un motif : il faut dire POURQUOI."""
    for faux_motif in ("", "   ", None):
        with pytest.raises(PopulationArchivee):
            resoudre_population(arborescence["archivee"], archivee_confirmee=faux_motif)


# ── Ce que le garde ne doit pas casser ──────────────────────────────────────


def test_r15_une_cohorte_vivante_se_charge_sans_rien_demander(arborescence):
    fichier, manifest = resoudre_population(arborescence["vivante"])
    assert fichier.is_file()
    assert manifest is not None
    info = info_population(arborescence["vivante"])
    assert info.scellee and info.n == 1


def test_r15_un_dossier_nomme_archives_ailleurs_nest_pas_vise(tmp_path):
    """Le garde vise le segment `archive` d'un chemin de populations, pas le mot où qu'il soit.

    Une cohorte dont le nom contient « archive » reste lisible : c'est l'emplacement qui
    décide, jamais une correspondance de texte.
    """
    pop = tmp_path / "data" / "population"
    d = _cohorte(pop, "population_archivistes_2026")
    fichier, _ = resoudre_population(d)
    assert fichier.is_file()


def test_r15_charger_population_propage_le_garde(arborescence):
    with pytest.raises(PopulationArchivee):
        charger_population(arborescence["archivee"])
    personnes, info = charger_population(
        arborescence["archivee"], archivee_confirmee="témoin du ticket 045"
    )
    assert len(personnes) == 1 and info.n == 1
