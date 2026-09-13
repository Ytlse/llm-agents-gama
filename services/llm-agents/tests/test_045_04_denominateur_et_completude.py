"""Ticket 045, bloc C — un dénominateur qui ne dépend pas du déroulé (alerte A3).

R9 : l'ensemble des déplacements inexploitables est DÉRIVÉ DU JEU à l'ouverture de
     l'exécution, pas accumulé au fil des décisions.

Et trois conséquences de la journée refermée (bloc A), qu'il faut solder ici parce qu'elles
touchent le même décompte :

- `Jeu.est_complet` devenait inatteignable : `couverture()` comptait la fermeture domicile →
  domicile dans les attendus mais jamais dans les couverts, alors qu'elle ne PEUT pas être
  couverte. Un jeu parfaitement préparé se déclarait incomplet.
- La progression affichait 80 % sur une exécution terminée : le numérateur excluait les
  inexploitables, le dénominateur non. Toute exécution complète serait restée sous 100 % dans
  le tableau de bord.
- L'alarme « déplacements sans proposition » se déclenchait à la moindre préparation de jeu :
  sur la cohorte v5, 138 des 3 299 déplacements ont leur origine pour destination, soit 4,2 %
  pour un seuil à 5 %. Or une origine égale à sa destination n'est pas une défaillance :
  il n'y a pas d'itinéraire à calculer entre un point et lui-même. La compter dans une alarme
  de santé des moteurs, c'est noyer le signal qu'elle sert à porter.

Le fil commun : `origine_egale_destination` et `aucune_proposition` sont deux choses. La
première est une propriété connue de la journée, la seconde est un échec. Les additionner
faisait mentir trois compteurs à la fois.
"""

from __future__ import annotations

import asyncio
import hashlib
import json

import pytest
import yaml

from experiences import jeu as J
from experiences.jeu import (
    MOTIF_AUCUNE_PROPOSITION,
    MOTIF_ORIGINE_EGALE_DESTINATION,
    est_defaillance_moteur,
)
from experiences.population import charger_population
from models import Transit, TransitLocation, TravelPlan

HOME = {"lon": 1.4400, "lat": 43.6000, "public_transport": True, "zone": "centre"}
WORK = {"lon": 1.4500, "lat": 43.6100, "public_transport": True, "zone": "nord"}


def _act(aid, purpose, start, end, loc, scheduled):
    return {
        "id": aid,
        "scheduled_start_time": float(scheduled),
        "start_time": float(start),
        "end_time": float(end),
        "purpose": purpose,
        "location": loc,
    }


def _population():
    """Une personne, journée bouclée sur le domicile : home → work → home.

    Trois activités, donc trois déplacements. Le dernier (a2 → a0) va du domicile au
    domicile : il est inexploitable, et c'est exactement le cas que ce fichier éprouve.
    Les heures respectent le bouclage des populations scellées
    (`scheduled_start_time` de la première == `end_time` de la dernière).
    """
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
        _act("a0", "home", 0, 8 * 3600, HOME, 20 * 3600),
        _act("a1", "work", 9 * 3600, 17 * 3600, WORK, 8 * 3600),
        _act("a2", "home", 18 * 3600, 20 * 3600, HOME, 17 * 3600),
    ]
    return [
        {
            "person_id": "p1",
            "identity": {"traits_json": traits, "home": HOME, "activities": acts},
            "state": {"last_activity_index": 0},
            "is_llm_based": True,
        }
    ]


def _plan(mode, origin, dest, dep_ts, duration=600):
    loc_o = TransitLocation(stop="", lat=origin.lat, lon=origin.lon)
    loc_d = TransitLocation(stop="", lat=dest.lat, lon=dest.lon)
    leg = Transit(
        start_time=dep_ts * 1000,
        end_time=(dep_ts + duration) * 1000,
        duration=duration,
        distance=1500.0,
        mode=mode,
        start_location=loc_o,
        end_location=loc_d,
        transit_route=f"__DIRECT_{mode.upper()}__",
    )
    return TravelPlan(
        id=f"{mode}-{dep_ts}",
        start_location=origin,
        end_location=dest,
        start_time=dep_ts * 1000,
        end_time=(dep_ts + duration) * 1000,
        duration=duration,
        legs=[leg],
    )


class MoteurFactice:
    """Rend toujours marche, vélo et voiture — aucune défaillance, pour isoler le sujet."""

    async def get_itineraries(self, origin, destination, departure_time, **_):
        return [
            _plan("foot", origin, destination, departure_time, 1800),
            _plan("bicycle", origin, destination, departure_time, 900),
            _plan("car", origin, destination, departure_time, 600),
        ]


@pytest.fixture
def banc_jeu(tmp_path):
    """Un jeu clos, préparé sur une journée qui boucle sur le domicile."""
    pop_dir = tmp_path / "pop"
    pop_dir.mkdir()
    fichier = pop_dir / "population.json"
    fichier.write_text(json.dumps(_population()), encoding="utf-8")
    sha = hashlib.sha256(fichier.read_bytes()).hexdigest()
    (pop_dir / "MANIFEST.yaml").write_text(
        yaml.safe_dump(
            {
                "nom": "pop_test",
                "population": {"fichier": "population.json", "sha256": sha},
            }
        ),
        encoding="utf-8",
    )
    personnes, info = charger_population(pop_dir)
    prep = J.JeuEnPreparation.ouvrir(
        tmp_path / "jeu",
        "jeu_test",
        info,
        "2026-03-16",
        dependances={"commit": "abc", "gtfs": {"calendar.txt": "c1"}},
    )
    asyncio.run(
        J.preparer(
            prep,
            personnes,
            MoteurFactice(),
            fabrique_locale=lambda **_: None,
            progression_s=100,
        )
    )
    attendus = J.deplacements_attendus(personnes, "2026-03-16")
    prep.clore(attendus, len(personnes))
    return {"jeu": J.Jeu.charger(tmp_path / "jeu"), "attendus": attendus}


# ── Le partage des motifs, d'où tout découle ────────────────────────────────


def test_une_fermeture_sur_place_nest_pas_une_defaillance_de_moteur():
    """Entre un point et lui-même il n'y a pas d'itinéraire à trouver : rien n'a échoué."""
    assert est_defaillance_moteur(MOTIF_ORIGINE_EGALE_DESTINATION) is False


def test_aucune_proposition_est_une_defaillance_de_moteur():
    """Là, les moteurs ont été interrogés et n'ont rien rendu : c'est un échec, il s'alarme."""
    assert est_defaillance_moteur(MOTIF_AUCUNE_PROPOSITION) is True


def test_un_deplacement_servi_na_pas_de_motif_et_nest_pas_une_defaillance():
    assert est_defaillance_moteur(None) is False


# ── R9 : le dénominateur se lit sur le jeu, pas sur le déroulé ──────────────


def test_r9_les_inexploitables_se_derivent_du_jeu(banc_jeu):
    """Un déplacement sans proposition dans le jeu est inexploitable, avant toute décision."""
    jeu, attendus = banc_jeu["jeu"], banc_jeu["attendus"]
    inexploitables = jeu.inexploitables(attendus)
    attendus_sans_props = {
        (d.person_id, d.activity_id)
        for d in attendus
        if (l := jeu.ligne(d.person_id, d.activity_id)) is not None
        and not l.propositions
    }
    assert inexploitables == attendus_sans_props
    assert inexploitables, "le banc doit contenir au moins une fermeture sur place"


def test_r9_un_deplacement_non_couvert_nest_pas_un_inexploitable(banc_jeu):
    """Absent du jeu et présent-mais-vide sont deux choses.

    Le premier est un trou de préparation (`non_couvert`), le second une propriété du
    déplacement. Les confondre ferait varier le dénominateur avec la complétude du jeu.
    """
    jeu, attendus = banc_jeu["jeu"], banc_jeu["attendus"]
    inexploitables = jeu.inexploitables(attendus)
    for person_id, activity_id in inexploitables:
        assert jeu.ligne(person_id, activity_id) is not None


def test_r9_le_denominateur_est_le_meme_quel_que_soit_le_sort_de_lexecution(banc_jeu):
    """Le cœur d'A3 : deux exécutions sur le même couple (population, jeu) comptent pareil.

    On dérive deux fois, sans rien exécuter entre les deux : le nombre ne peut pas dépendre
    de ce qui n'a pas eu lieu.
    """
    jeu, attendus = banc_jeu["jeu"], banc_jeu["attendus"]
    assert jeu.inexploitables(attendus) == jeu.inexploitables(attendus)
    assert len(attendus) - len(jeu.inexploitables(attendus)) > 0


# ── La complétude d'un jeu ──────────────────────────────────────────────────


def test_un_jeu_dont_toutes_les_fermetures_sont_sur_place_est_complet(banc_jeu):
    """Ce qui ne peut pas être couvert ne doit pas empêcher un jeu d'être complet.

    Sinon aucun jeu ne le serait jamais plus, pour toute population dont les journées
    reviennent au domicile — c'est-à-dire toutes.
    """
    jeu = banc_jeu["jeu"]
    couv = jeu.couverture()
    assert couv["deplacements_exploitables"] < couv["deplacements_attendus"]
    assert couv["deplacements_couverts"] == couv["deplacements_exploitables"]
    assert jeu.est_complet is True


def test_la_couverture_publie_les_deux_denominateurs(banc_jeu):
    """Brut et exploitable, tous les deux : un seul chiffre mélangerait deux questions."""
    couv = banc_jeu["jeu"].couverture()
    assert couv["deplacements_attendus"] >= couv["deplacements_exploitables"]
    assert couv["taux"] == pytest.approx(
        couv["deplacements_couverts"] / couv["deplacements_exploitables"]
    )
