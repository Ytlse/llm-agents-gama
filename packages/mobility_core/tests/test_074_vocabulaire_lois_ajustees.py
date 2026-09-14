"""Ticket 074 — les lois AJUSTÉES parlent la langue de l'enquête, le persona parle anglais.

Ce que ces tests protègent tient en une phrase : **une modalité qu'une loi ne reconnaît pas
ne manque nulle part**. Ses indicatrices restent à zéro, le persona tombe dans la modalité de
référence, la loi rend une probabilité parfaitement plausible, et rien — pas un compteur, pas
une ligne de journal — ne dit que la covariable a disparu.

C'est arrivé. `main_occupation` est passé à l'anglais au ticket 074 ; les trois artefacts gelés
(`driving_license.json`, `pt_subscription.json`, `bike_ownership.json`) nomment leurs variables
`occ_Travail à plein temps`, parce que c'est sur ces modalités-là que leurs coefficients ont été
ajustés. Résultat mesuré sur le vivier v6 : l'écart de `permis_adultes` à sa cible est passé de
2,52 à 5,23 points et celui de `abonnement_tc` de 2,65 à 8,45, **sans une seule erreur**.

Les artefacts ne bougent pas — ce sont des mesures gelées. C'est la lecture qui traduit.
"""

from __future__ import annotations

import logging

import pytest

from mobility_core.bike_ownership import propensity_design
from mobility_core.equipment_propensity import design_vector
from mobility_core.population_reference import occupation_enquete

# Les modalités telles que les ressources ajustées les nomment (relevées dans les trois JSON).
OCCUPATIONS_ENQUETE = (
    "Autre",
    "Chômeur/recherche d'emploi",
    "Personne au foyer",
    "Retraité",
    "Scolaire (jusqu'au Bac)",
    "Travail à plein temps",
    "Travail à temps partiel",
    "Étudiant",
)

# Le persona v6 → la modalité de l'enquête. Les sept couples que la population produit.
COUPLES = [
    ("Pupil (up to Baccalaureate)", "Scolaire (jusqu'au Bac)"),
    ("Student", "Étudiant"),
    ("Full-time worker", "Travail à plein temps"),
    ("Part-time worker", "Travail à temps partiel"),
    ("Unemployed / job seeker", "Chômeur/recherche d'emploi"),
    ("Homemaker", "Personne au foyer"),
    ("Retired", "Retraité"),
]


@pytest.mark.parametrize("anglais,francais", COUPLES)
def test_les_deux_vocabulaires_donnent_la_meme_modalite(anglais, francais):
    assert occupation_enquete(anglais) == francais
    # Le français reste reconnu tel quel : les cohortes archivées se relisent sans détour.
    assert occupation_enquete(francais) == francais


@pytest.mark.parametrize("anglais,francais", COUPLES)
def test_le_vecteur_de_design_est_identique_dans_les_deux_langues(anglais, francais):
    """La covariable doit peser PAREIL, pas seulement être reconnue."""
    features = ("age10", "female") + tuple(f"occ_{o}" for o in OCCUPATIONS_ENQUETE)
    args = (42.0, "Female", None, 1.0, 500.0, 5.0, OCCUPATIONS_ENQUETE, features, 500.0)
    en = design_vector(*args[:2], anglais, *args[3:])
    fr = design_vector(*args[:2], francais, *args[3:])
    assert en == fr
    # Et l'indicatrice attendue vaut bien 1 : un vecteur identique mais TOUT À ZÉRO des
    # deux côtés passerait ce test sans rien prouver — c'est exactement le piège.
    assert en[features.index(f"occ_{francais}")] == 1.0
    assert sum(en[2:]) == 1.0


@pytest.mark.parametrize("anglais,francais", COUPLES)
def test_la_loi_velo_lit_aussi_les_deux_vocabulaires(anglais, francais):
    en = propensity_design(1, 2, 42.0, "Female", anglais, 500.0, 5.0, OCCUPATIONS_ENQUETE)
    fr = propensity_design(1, 2, 42.0, "Female", francais, 500.0, 5.0, OCCUPATIONS_ENQUETE)
    assert en == fr
    assert en[f"occ_{francais}"] == 1.0


def test_une_modalite_inconnue_tombe_en_reference_ET_LE_DIT(caplog):
    """Le repli reste la modalité de référence — mais il cesse d'être muet."""
    features = ("age10",) + tuple(f"occ_{o}" for o in OCCUPATIONS_ENQUETE)
    with caplog.at_level(logging.ERROR):
        vecteur = design_vector(42.0, "Female", "Conducteur de dirigeable", 1.0, 500.0, 5.0,
                                OCCUPATIONS_ENQUETE, features, 500.0)
    assert sum(vecteur[1:]) == 0.0
    assert any("[ALARME]" in r.getMessage() and "Conducteur de dirigeable" in r.getMessage()
               for r in caplog.records)


def test_une_occupation_absente_ne_leve_aucune_alarme(caplog):
    """Absence ≠ modalité inconnue : un persona sans occupation n'est pas une anomalie."""
    features = ("age10",) + tuple(f"occ_{o}" for o in OCCUPATIONS_ENQUETE)
    with caplog.at_level(logging.ERROR):
        design_vector(42.0, "Female", None, 1.0, 500.0, 5.0,
                      OCCUPATIONS_ENQUETE, features, 500.0)
        design_vector(42.0, "Female", "", 1.0, 500.0, 5.0,
                      OCCUPATIONS_ENQUETE, features, 500.0)
    assert not [r for r in caplog.records if "[ALARME]" in r.getMessage()]


def test_les_ressources_gelees_gardent_leur_vocabulaire():
    """Garde-fou : si un jour quelqu'un « traduit » les artefacts, ce test tombe.

    Les traduire n'est pas une amélioration : le nom des variables fait partie de
    l'ajustement, et les cohortes déjà scellées citent le `sha256` du fichier.
    """
    import json

    from mobility_core.resources import data_path

    for nom in ("driving_license.json", "pt_subscription.json", "bike_ownership.json"):
        chemin = data_path(nom)
        if not chemin.exists():  # ressource d'accès restreint absente de ce poste
            pytest.skip(f"{nom} absent")
        texte = json.dumps(json.loads(chemin.read_text(encoding="utf-8")), ensure_ascii=False)
        assert "occ_Travail à plein temps" in texte, (
            f"{nom} ne nomme plus ses modalités dans la langue de l'enquête : les "
            f"coefficients ont été ajustés sur celles-là.")
