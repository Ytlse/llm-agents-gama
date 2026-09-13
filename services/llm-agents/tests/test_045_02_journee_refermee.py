"""Ticket 045, bloc A — la journée se referme (alerte A1).

R1 : une seule fonction énumère la chaîne, et elle referme le cycle comme le contrôleur.
R2 : une fermeture dont l'origine et la destination sont le même lieu est inexploitable.
R3 : sur la v5, l'énumération rend 3 299 déplacements attendus.
R4 : l'heure de départ de la fermeture suit la règle du contrôleur.

Le défaut corrigé : `deplacements_attendus` énumérait les **paires consécutives** d'activités,
soit n − 1 déplacements par personne, quand le contrôleur de simulation referme le cycle avec
`(i + 1) % n` et en joue n. La plateforme ne décidait donc jamais le retour au domicile — 27 %
de la journée sur la v1 — et l'omission n'était pas aléatoire : elle retirait exactement le
trajet où la contrainte de chaîne des véhicules mord le plus.

Ce que les données disent, et qui rend la correction simple (mesuré le 2026-09-11 sur les deux
cohortes scellées, 1 894 personnes, zéro écart) : `scheduled_start_time` de l'activité `(i+1) % n`
vaut `end_time` de l'activité `i`, **bouclage compris**. La convention de la plateforme (heure
programmée de la destination) et celle du contrôleur (fin de l'activité d'origine) donnent donc
le même nombre, pour la fermeture comme pour le reste. Il n'y a pas deux règles à réconcilier,
seulement une paire à ne plus oublier.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from chaine_activites import activite_suivante, paires_de_la_journee
from experiences import jeu as J
from models import Person

HOME = {"lon": 1.4400, "lat": 43.6000, "public_transport": True, "zone": "centre"}
WORK = {"lon": 1.4500, "lat": 43.6100, "public_transport": True, "zone": "nord"}
GYM = {"lon": 1.4600, "lat": 43.6200, "public_transport": False, "zone": "est"}

RACINE = Path(__file__).resolve().parents[3]
POP_V5 = RACINE / "data" / "population" / "population_1000_AAMAS_v5" / "population.json"
# La v1 a été ARCHIVÉE par le lot 1 : elle ne se lit plus que sur dérogation motivée, et ce
# test en est une — il conserve le chiffre que le ticket cite (2 693 → 3 693).
POP_V1 = (
    RACINE / "data" / "population" / "archive" / "population_1000_AAMAS" / "population.json"
)


def _act(aid, purpose, start, end, loc, scheduled=None):
    return {
        "id": aid,
        "scheduled_start_time": scheduled,
        "start_time": float(start),
        "end_time": float(end),
        "purpose": purpose,
        "location": loc,
    }


def _entry(pid, activities):
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
    return {
        "person_id": pid,
        "identity": {"traits_json": traits, "home": HOME, "activities": activities},
        "state": {"last_activity_index": 0},
        "is_llm_based": True,
    }


def _personne(pid, activities) -> Person:
    from inputs.population.eqasim_loader import EqasimJSONPopulationLoader

    return EqasimJSONPopulationLoader().load_population_from_data(
        [_entry(pid, activities)], max_size=1, bbox=None
    )[0]


def _trois_activites() -> Person:
    """home → work → gym → (retour home). Trois activités, donc TROIS déplacements."""
    return _personne(
        "p3",
        [
            _act("a0", "home", 0, 8 * 3600, HOME, 20 * 3600),
            _act("a1", "work", 9 * 3600, 17 * 3600, WORK, 8 * 3600),
            _act("a2", "leisure", 18 * 3600, 20 * 3600, GYM, 17 * 3600),
        ],
    )


# ── R1 : une seule énumération, et elle referme ──────────────────────────────


def test_r1_trois_activites_donnent_trois_deplacements_pas_deux():
    """Le cœur de l'alerte A1 : n activités valent n déplacements, pas n − 1."""
    personne = _trois_activites()
    paires = paires_de_la_journee(personne.identity.activities)
    assert len(paires) == 3
    assert [(o.id, d.id) for o, d in paires] == [
        ("a0", "a1"),
        ("a1", "a2"),
        ("a2", "a0"),
    ]


def test_r1_la_derniere_paire_est_le_retour_au_domicile():
    """La fermeture va de la dernière activité à la première, qui est le domicile."""
    personne = _trois_activites()
    origine, destination = paires_de_la_journee(personne.identity.activities)[-1]
    assert (
        origine.purpose.value if hasattr(origine.purpose, "value") else origine.purpose
    )
    assert origine.id == "a2"
    assert destination.id == "a0"


def test_r1_activite_suivante_boucle_comme_le_controleur():
    """`activite_suivante` applique `(i + 1) % n`, la règle des trois sites du contrôleur."""
    acts = _trois_activites().identity.activities
    assert activite_suivante(acts, acts[0]).id == "a1"
    assert activite_suivante(acts, acts[1]).id == "a2"
    assert activite_suivante(acts, acts[2]).id == "a0"


def test_r1_une_personne_a_une_seule_activite_ne_se_deplace_pas():
    """Le garde `len <= 1` du contrôleur : pas de trajet d'une activité vers elle-même."""
    personne = _personne("p1", [_act("c0", "home", 0, 86400, HOME, 86400)])
    acts = personne.identity.activities
    assert activite_suivante(acts, acts[0]) is None
    assert paires_de_la_journee(acts) == []


def test_r1_deplacements_attendus_utilise_la_chaine_partagee():
    """La plateforme ne réimplémente pas l'énumération : mêmes paires des deux côtés."""
    personne = _trois_activites()
    attendus = J.deplacements_attendus([personne], "2026-03-16")
    paires = paires_de_la_journee(personne.identity.activities)
    assert [(d.origine_activity_id, d.activity_id) for d in attendus] == [
        (o.id, dst.id) for o, dst in paires
    ]


# ── R2 : une fermeture sur place n'est pas un déplacement exploitable ────────


def test_r2_fermeture_origine_egale_destination_est_inexploitable():
    """Une personne dont la dernière activité est déjà au domicile ferme sur place.

    Le déplacement existe (il compte dans les attendus bruts), mais il n'a pas de
    proposition possible : c'est le motif `origine_egale_destination` que le jeu connaît déjà.
    Sur la v5, 77 personnes mobiles ferment ainsi leur journée. (Le jeu compte 138
    déplacements à origine égale destination : ces 77 fermetures, plus 61 trajets
    intermédiaires entre deux activités situées au même endroit.)
    """
    personne = _personne(
        "pferme",
        [
            _act("d0", "home", 0, 8 * 3600, HOME, 18 * 3600),
            _act("d1", "work", 9 * 3600, 17 * 3600, WORK, 8 * 3600),
            _act("d2", "home", 18 * 3600, 20 * 3600, HOME, 17 * 3600),
        ],
    )
    attendus = J.deplacements_attendus([personne], "2026-03-16")
    assert len(attendus) == 3
    fermeture = attendus[-1]
    assert (fermeture.origine_activity_id, fermeture.activity_id) == ("d2", "d0")
    assert (fermeture.origine.lat, fermeture.origine.lon) == (
        fermeture.destination.lat,
        fermeture.destination.lon,
    )


# ── R3 : les chiffres des cohortes scellées ─────────────────────────────────


@pytest.mark.skipif(not POP_V5.is_file(), reason="cohorte v5 absente du disque")
def test_r3_la_cohorte_v5_rend_3299_deplacements_attendus():
    from experiences.population import charger_population

    personnes, _ = charger_population(POP_V5.parent)
    assert len(J.deplacements_attendus(personnes, "2026-03-16")) == 3299


@pytest.mark.skipif(not POP_V1.is_file(), reason="cohorte v1 absente du disque")
def test_r3_la_cohorte_v1_rend_3693_deplacements_attendus():
    """Conservé comme témoin du chiffre cité par le ticket : 2 693 → 3 693, soit 27 % de journée
    jamais décidée avant cette correction."""
    from experiences.population import charger_population

    personnes, _ = charger_population(
        POP_V1.parent, archivee_confirmee="témoin du ticket 045"
    )
    assert len(J.deplacements_attendus(personnes, "2026-03-16")) == 3693


# ── R4 : l'heure de départ de la fermeture ───────────────────────────────────


def test_r4_le_depart_de_la_fermeture_suit_la_fin_de_la_derniere_activite():
    """Les deux conventions coïncident : heure programmée de la destination == fin de l'origine.

    Ce n'est pas une coïncidence d'implémentation mais une propriété des populations
    scellées, vérifiée sur les 1 894 personnes des deux cohortes sans un seul écart.
    """
    personne = _trois_activites()
    fermeture = J.deplacements_attendus([personne], "2026-03-16")[-1]
    acts = {a.id: a for a in personne.identity.activities}
    assert fermeture.depart_24h == int(acts["a2"].end_time)
    assert fermeture.depart_24h == int(acts["a0"].scheduled_start_time)


@pytest.mark.skipif(not POP_V5.is_file(), reason="cohorte v5 absente du disque")
def test_r4_le_bouclage_horaire_est_une_propriete_de_la_cohorte():
    """`scheduled_start_time` de la première activité == `end_time` de la dernière, pour tous."""
    pop = json.loads(POP_V5.read_text(encoding="utf-8"))
    ecarts = [
        p.get("person_id")
        for p in pop
        if len(p["identity"]["activities"] or []) >= 2
        and int(p["identity"]["activities"][-1]["end_time"])
        != int(p["identity"]["activities"][0]["scheduled_start_time"])
    ]
    assert ecarts == []
