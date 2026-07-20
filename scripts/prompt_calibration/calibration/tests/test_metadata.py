"""Tests de la phase 0.1 — parsing sur extraits réels des deux formats,
buckets Cerema, jointure population (genre sans inférence)."""

import json

import pytest

from calibration.metadata import (
    GENDER_MAP, OCCUPATION_MAP, DEST_TO_MOTIF,
    age_to_cat, distance_to_cat, extract_min_distance_km,
    split_entry_personas, parse_persona_header,
    load_population, build_decision_records,
)

# ── Extraits réels ────────────────────────────────────────────────────────────

# Format courant (llm_exchanges.jsonl du 2026-07-11)
CURRENT_MSG = """**Contexte :** Météo : 3°C, Ciel dégagé/Ensoleillé. Pas de précipitations prévues.

--- agent_id=503036 | Destination : leisure | Départ : 15:53 ---

Noël, 67 ans, Retraité (famille de 2 pers., revenu élevé)
Mobilité : conducteur·trice, voiture toujours dispo | sans abonnement TC | sans vélo personnel Contraintes : None

**Options de trajet :**
- [0] foot: Temps de trajet : 6 minutes, dont 6 minutes de marche.
- [2] car: Durée estimée : 5 minutes. Distance : 522 m.
- [5] foot: Durée estimée : 7 minutes. Distance : 583 m.

Réponds avec l'objet JSON final contenant les recommandations pour 1 persona(s)."""

# Format legacy (attendu par l'ancienne lib)
LEGACY_MSG = """**Contexte :** Météo : 12°C, pluie légère.

--- PERSONA 5327 | Destination : education | Départ : 08:05 ---

Thibaut Maurice, 12 ans, Scolaire (jusqu'au Bac)

**Options de trajet :**
- [0] foot: Durée estimée : 24 minutes. Distance : 2.1 km.
- [1] bicycle: Durée estimée : 9 minutes. Distance : 2.3 km.

--- PERSONA 19826 | Destination : work | Départ : 08:30 ---

Marie Dupont, 34 ans, Travail à plein temps

**Options de trajet :**
- [0] car: Durée estimée : 15 minutes. Distance : 8.4 km."""


def test_split_and_header_format_courant():
    preamble, sections = split_entry_personas(CURRENT_MSG)
    assert preamble.startswith("**Contexte :** Météo : 3°C")
    assert len(sections) == 1
    assert parse_persona_header(sections[0]) == ("503036", "leisure")


def test_split_and_header_format_legacy():
    preamble, sections = split_entry_personas(LEGACY_MSG)
    assert "12°C" in preamble
    assert len(sections) == 2
    assert parse_persona_header(sections[0]) == ("5327", "education")
    assert parse_persona_header(sections[1]) == ("19826", "work")


def test_header_non_parsable():
    assert parse_persona_header("--- n'importe quoi ---") is None


def test_extract_min_distance_km():
    _, sections = split_entry_personas(CURRENT_MSG)
    assert extract_min_distance_km(sections[0]) == pytest.approx(0.522)  # m → km
    _, legacy = split_entry_personas(LEGACY_MSG)
    assert extract_min_distance_km(legacy[0]) == pytest.approx(2.1)
    assert extract_min_distance_km("aucune option chiffrée") is None


# ── Buckets Cerema ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("age,cat", [
    (5, "5-9"), (9, "5-9"), (10, "10-14"), (19, "15-19"), (20, "20-24"),
    (74, "70-74"), (75, "75-130"), (98, "75-130"),
])
def test_age_to_cat(age, cat):
    assert age_to_cat(age) == cat


@pytest.mark.parametrize("km,cat", [
    (0.0, "0-1km"), (0.99, "0-1km"), (1.0, "1-2km"), (4.9, "2-5km"),
    (10.0, "10-20km"), (49.9, "20-50km"), (50.0, "plus_50km"),
])
def test_distance_to_cat(km, cat):
    assert distance_to_cat(km) == cat


# ── Jointure population ───────────────────────────────────────────────────────

def _population_file(tmp_path, persons):
    path = tmp_path / "population_2.json"
    path.write_text(json.dumps(persons), encoding="utf-8")
    return path


def _person(pid, name, age, gender, occupation, household=2):
    return {"person_id": pid, "identity": {"traits_json": {
        "name": name, "age": age, "gender": gender,
        "main_occupation": occupation, "household_size": household}}}


def test_load_population_join(tmp_path):
    path = _population_file(tmp_path, [
        # « Noël » : l'heuristique prénom de l'ancienne lib se trompait ;
        # ici le genre vient de traits_json.gender, point final.
        _person("503036", "Noël Fabre", 67, "Female", "Retraité"),
        _person("5327", "Thibaut Maurice", 12, "Male", "Scolaire (jusqu'au Bac)"),
    ])
    traits = load_population(path)
    assert traits["503036"] == {"genre": "Femme", "age": 67, "age_cat": "65-69",
                                "occupation": "Retraité", "household_size": 2}
    assert traits["5327"]["occupation"] == "scolaire"
    assert traits["5327"]["genre"] == "Homme"


def test_load_population_valeur_inconnue(tmp_path):
    path = _population_file(
        tmp_path, [_person("1", "X", 30, "Male", "Astronaute")])
    with pytest.raises(ValueError, match="Occupation inconnue"):
        load_population(path)


def _entry(user_msg):
    return {"task_id": "t1", "messages": [
        {"role": "system", "content": ""},
        {"role": "user", "content": user_msg}]}


def test_build_decision_records_les_deux_formats(tmp_path):
    traits = load_population(_population_file(tmp_path, [
        _person("503036", "Noël Fabre", 67, "Male", "Retraité"),
        _person("5327", "Thibaut Maurice", 12, "Male", "Scolaire (jusqu'au Bac)"),
        _person("19826", "Marie Dupont", 34, "Female", "Travail à plein temps"),
    ]))
    records, anomalies = build_decision_records(
        [_entry(CURRENT_MSG), _entry(LEGACY_MSG)], traits)
    assert anomalies == []
    assert len(records) == 3

    by_id = {r["agent_id"]: r for r in records}
    noel = by_id["503036"]
    assert noel["motif"] is None            # leisure : hors référence Cerema
    assert noel["dist_cat"] == "0-1km"      # 522 m
    assert noel["context"].startswith("Météo : 3°C")
    assert noel["genre"] == "Homme"

    thibaut = by_id["5327"]
    assert thibaut["motif"] == "etudes"
    assert thibaut["occupation"] == "scolaire"
    assert by_id["19826"]["motif"] == "travail"


def test_build_decision_records_anomalies(tmp_path):
    traits = load_population(_population_file(
        tmp_path, [_person("1", "X", 30, "Male", "Retraité")]))
    records, anomalies = build_decision_records([_entry(CURRENT_MSG)], traits)
    assert records == []
    assert anomalies[0]["cause"] == "agent_hors_population"
    assert anomalies[0]["agent_id"] == "503036"


def test_mappings_complets():
    # Valeurs observées dans population_1000.json (2026-07-13)
    observed_occupations = {
        "Chômeur/recherche d'emploi", "Personne au foyer", "Retraité",
        "Scolaire (jusqu'au Bac)", "Travail à plein temps",
        "Travail à temps partiel", "Étudiant"}
    assert observed_occupations == set(OCCUPATION_MAP)
    assert set(GENDER_MAP) == {"Male", "Female"}
    assert set(DEST_TO_MOTIF.values()) == {"travail", "etudes", "achats"}
