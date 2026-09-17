"""Ticket 057 — le premier déplacement de la journée est daté du jour simulé, pas du lendemain.

Les chaînes d'activités de la cohorte sont cycliques : la première activité « home » commence
la veille au soir et se referme le lendemain. Son `start_time` (72 449 s, soit 20:07, chez la
personne 609 de la v6) appartient donc au jour PRÉCÉDENT. Ancré sur `base`, il plaçait le
curseur à 20:07 du jour simulé, et le départ du matin — antérieur — basculait au lendemain par
la ligne de report.

Effet mesuré avant correction, sur les huit exécutions du 2026-09-14 : **797 des 894 personas**
perdaient leur premier déplacement, que la coupe du scoreur écartait ensuite (866 décisions sur
3 299), et le jeu enregistrait pour eux un itinéraire calculé au mauvais jour — comme la météo
servie au prompt des bras LLM, 12 °C le 16 mars contre 15 °C le 17.
"""

import json
from pathlib import Path

import pytest
from experiences.jeu import deplacements_attendus
from models import Person

REPO = Path(__file__).resolve().parents[3]
JOUR = "2026-03-16"
BASE = 1773619200  # minuit du 16 mars 2026, horodatage GAMA
COHORTE = REPO / "data" / "population" / "population_1000_AAMAS_v6" / "population.json"


def _personne(activites: list[dict]) -> Person:
    return Person.model_validate(
        {
            "person_id": "test",
            "identity": {
                "name": "Test",
                "home": {"lat": 43.6, "lon": 1.44},
                "traits_json": {"age": 40, "has_driving_license": True, "number_of_cars": 1},
                "activities": activites,
            },
        }
    )


def _activite(aid: str, purpose: str, debut: int, fin: int, prevu: int) -> dict:
    return {
        "id": aid,
        "purpose": purpose,
        "start_time": debut,
        "end_time": fin,
        "scheduled_start_time": prevu,
        "location": {"lat": 43.6 + int(aid), "lon": 1.44},
    }


def test_une_activite_qui_enjambe_minuit_ne_repousse_pas_le_depart_du_matin():
    """Le cas de la cohorte : « home » commence à 20:07 et se ferme à 08:59 le lendemain.

    Les horaires sont ceux de la personne 609 de la v6, bouclage compris — le
    `scheduled_start_time` de la première activité égale l'`end_time` de la dernière, comme
    l'encodent les populations scellées. Sans cette structure, la paire de fermeture ne tombe
    pas au bon endroit et le test ne mesure plus ce qu'il croit.
    """
    personne = _personne(
        [
            _activite("0", "home", 72449, 32384, 71316),  # 20:07 → 08:59, enjambe minuit
            _activite("1", "work", 33516, 46416, 32384),
            _activite("2", "home", 47549, 71316, 46416),
        ]
    )
    deps = deplacements_attendus([personne], JOUR)
    assert deps, "aucun déplacement dérivé"
    premier = next(d for d in deps if d.ordinal == 0)
    assert premier.depart_ts == BASE + 32384, (
        f"le départ du matin devrait tomber à 08:59 du jour simulé, il vaut {premier.depart_ts}"
    )
    assert all(BASE <= d.depart_ts < BASE + 86400 for d in deps), (
        "un déplacement sort du jour simulé"
    )


def test_le_report_au_lendemain_joue_encore_quand_il_doit():
    """La correction ne désarme pas la règle de report : une cible antérieure à l'arrivée sur
    l'activité d'origine bascule toujours au lendemain. Sans ce test, supprimer la ligne de
    report entièrement passerait aussi."""
    personne = _personne(
        [
            _activite("0", "home", 25200, 32384, 21600),  # 07:00 → 08:59, ordinaire
            _activite("1", "work", 33516, 46416, 21600),  # cible 06:00, AVANT l'arrivée
            _activite("2", "home", 47549, 21600, 46416),
        ]
    )
    deps = deplacements_attendus([personne], JOUR)
    premier = next(d for d in deps if d.ordinal == 0)
    assert premier.depart_ts == BASE + 86400 + 21600, (
        "une cible antérieure à l'arrivée doit basculer au lendemain"
    )


@pytest.mark.skipif(not COHORTE.exists(), reason="cohorte v6 absente du dépôt")
def test_la_cohorte_v6_tient_entiere_dans_son_jour_simule():
    """Le contrôle qui compte : sur les 894 personas mobiles, aucun déplacement ne déborde.

    Avant la correction, 866 des 3 299 déplacements tombaient au 17 mars, dont 797 de rang 0.
    """
    brut = json.loads(COHORTE.read_text(encoding="utf-8"))
    gens = brut if isinstance(brut, list) else (brut.get("people") or list(brut.values())[0])
    personnes = [Person.model_validate(p) for p in gens]
    deps = deplacements_attendus(personnes, JOUR)
    hors = [d for d in deps if not (BASE <= d.depart_ts < BASE + 86400)]
    assert not hors, f"{len(hors)} déplacement(s) hors du jour simulé, dont {sum(1 for d in hors if d.ordinal == 0)} de rang 0"
    assert len(deps) == 3299
