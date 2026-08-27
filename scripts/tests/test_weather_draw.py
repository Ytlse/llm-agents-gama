"""
Tests unitaires du tirage d'une date météo par agent
(`llm-agents/urban_mobility_agents/utils/weather_draw.py`).

Le dispositif existe parce que, sur une seule journée simulée, les 1 000 agents
partagent une seule météo : le régresseur a une variance nulle, et « aucun effet
mesuré » ne veut alors rien dire (ticket 023). Chaque test verrouille une
propriété sans laquelle le dispositif serait faux plutôt qu'absent :

  - **Déterminisme.** Même graine, même agent → même journée. Sans ça, deux runs
    identiques ne se reproduisent plus et une trace archivée n'est pas rejouable.
  - **L'heure du départ est conservée.** Le bulletin se lit par créneaux de 3 h :
    un départ à 08:00 doit continuer de lire le relevé de 06 h, quelle que soit
    la date tirée. Substituer le timestamp entier casserait le créneau.
  - **La fenêtre est respectée**, week-ends exclus quand l'enquête l'exige — elle
    ne compte que des jours ouvrés.
  - **Une fenêtre à cheval sur le Nouvel An fonctionne** : celle de l'enquête
    EMC² court du 20 septembre au 18 février.
  - **Couverture** : 1 000 agents doivent atteindre toutes les journées
    éligibles, sinon le dispositif perd la variance qu'il est censé apporter.
  - **Non-régression** : drapeau à faux → comportement strictement identique à
    l'existant.

Aucun accès réseau, aucun LLM.
"""

from __future__ import annotations

import collections
import datetime as dt
import os
import sys
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Paris")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "llm-agents"))

from urban_mobility_agents.utils.weather_draw import (  # noqa: E402
    date_meteo,
    indice_agent,
    jours_eligibles,
    timestamp_meteo,
)

FENETRE_ENQUETE = ("2022-09-20", "2023-02-18")
JOURS_OUVRES = (1, 2, 3, 4, 5)


class TestJoursEligibles(unittest.TestCase):
    def test_fenetre_a_cheval_sur_le_nouvel_an(self):
        jours = jours_eligibles(*FENETRE_ENQUETE, JOURS_OUVRES)
        self.assertEqual(len(jours), 109)
        # Septembre et février doivent tous deux être présents : une fenêtre
        # traitée comme un intervalle d'entiers en perdrait un des deux bouts.
        mois = {m for m, _ in jours}
        self.assertEqual(mois, {9, 10, 11, 12, 1, 2})

    def test_week_ends_exclus(self):
        jours = jours_eligibles(*FENETRE_ENQUETE, JOURS_OUVRES)
        # On revérifie sur les dates réelles de la fenêtre, pas sur les couples.
        premier = dt.date.fromisoformat(FENETRE_ENQUETE[0])
        dernier = dt.date.fromisoformat(FENETRE_ENQUETE[1])
        attendus = set()
        jour = premier
        while jour <= dernier:
            if jour.isoweekday() in JOURS_OUVRES:
                attendus.add((jour.month, jour.day))
            jour += dt.timedelta(days=1)
        self.assertEqual(set(jours), attendus)

    def test_sans_filtre_toute_lannee(self):
        # Année pivot bissextile : le 29 février doit être tirable.
        jours = jours_eligibles("2024-01-01", "2024-12-31", None)
        self.assertEqual(len(jours), 366)
        self.assertIn((2, 29), jours)

    def test_fenetre_vide_refusee(self):
        with self.assertRaises(ValueError):
            jours_eligibles("2026-03-10", "2026-03-01", None)

    def test_fenetre_sans_jour_eligible_refusee(self):
        # Un week-end seul, filtré sur les jours ouvrés : aucun jour ne reste.
        with self.assertRaises(ValueError):
            jours_eligibles("2026-03-21", "2026-03-22", JOURS_OUVRES)

    def test_pas_de_doublon(self):
        jours = jours_eligibles("2024-01-01", "2024-12-31", None)
        self.assertEqual(len(jours), len(set(jours)))


class TestTirage(unittest.TestCase):
    def setUp(self) -> None:
        self.jours = jours_eligibles(*FENETRE_ENQUETE, JOURS_OUVRES)

    def test_deterministe(self):
        for person_id in ("p1", "agent-42", "toulouse_000123"):
            self.assertEqual(
                date_meteo(person_id, 42, self.jours),
                date_meteo(person_id, 42, self.jours),
            )

    def test_graine_differente_tirage_different(self):
        # Pas une garantie par agent, mais l'ensemble des attributions doit bouger.
        a = [date_meteo(f"p{i}", 42, self.jours) for i in range(200)]
        b = [date_meteo(f"p{i}", 43, self.jours) for i in range(200)]
        self.assertNotEqual(a, b)

    def test_toujours_dans_la_fenetre(self):
        autorises = set(self.jours)
        for i in range(2000):
            self.assertIn(date_meteo(f"p{i}", 42, self.jours), autorises)

    def test_mille_agents_couvrent_toutes_les_journees(self):
        tirages = collections.Counter(date_meteo(f"p{i}", 42, self.jours) for i in range(1000))
        self.assertEqual(
            len(tirages), len(self.jours),
            "toutes les journées éligibles doivent être atteintes, sinon la variance promise n'est pas là",
        )
        self.assertGreaterEqual(min(tirages.values()), 1)

    def test_indice_borne(self):
        for cardinal in (1, 2, 109, 366):
            for i in range(50):
                self.assertTrue(0 <= indice_agent(42, f"p{i}", cardinal) < cardinal)
        with self.assertRaises(ValueError):
            indice_agent(42, "p0", 0)


class TestTimestamp(unittest.TestCase):
    def setUp(self) -> None:
        self.jours = jours_eligibles(*FENETRE_ENQUETE, JOURS_OUVRES)

    def test_heure_du_depart_conservee(self):
        """Le bulletin se lit par créneaux de 3 h : l'heure ne doit pas bouger."""
        for heure in (5, 8, 12, 17, 21):
            depart = int(dt.datetime(2026, 3, 16, heure, 37, 12).timestamp())
            for person_id in ("p1", "p2", "p3", "p400"):
                obtenu = dt.datetime.fromtimestamp(
                    timestamp_meteo(depart, person_id, 42, self.jours)
                )
                self.assertEqual((obtenu.hour, obtenu.minute, obtenu.second), (heure, 37, 12))

    def test_seule_la_date_change(self):
        depart = int(dt.datetime(2026, 3, 16, 8, 0, 0).timestamp())
        attendu = date_meteo("p7", 42, self.jours)
        obtenu = dt.datetime.fromtimestamp(timestamp_meteo(depart, "p7", 42, self.jours))
        self.assertEqual((obtenu.month, obtenu.day), attendu)

    def test_le_meme_agent_garde_sa_journee_quelle_que_soit_lheure(self):
        """La météo d'un agent ne doit pas dépendre de l'heure de son départ :
        sinon ses trajets du matin et du soir vivraient deux journées."""
        matin = int(dt.datetime(2026, 3, 16, 8, 0, 0).timestamp())
        soir = int(dt.datetime(2026, 3, 16, 18, 30, 0).timestamp())
        a = dt.datetime.fromtimestamp(timestamp_meteo(matin, "p9", 42, self.jours))
        b = dt.datetime.fromtimestamp(timestamp_meteo(soir, "p9", 42, self.jours))
        self.assertEqual((a.month, a.day), (b.month, b.day))

    def test_heure_conservee_au_franchissement_ete_hiver(self):
        """Un départ réel en heure d'été tiré sur une météo d'hiver (ou l'inverse)
        doit relire la même heure d'horloge — pas une heure décalée par un offset
        UTC figé sur la date d'origine. Le fuseau appliqué doit être celui que
        `weather_loader.get_weather` utilise pour relire le bulletin substitué."""
        depart_ete = int(dt.datetime(2026, 9, 22, 8, 0, 0, tzinfo=TZ).timestamp())
        jours_hiver = [(12, 8)]
        obtenu = dt.datetime.fromtimestamp(
            timestamp_meteo(depart_ete, "p-dst", 42, jours_hiver), tz=TZ
        )
        self.assertEqual((obtenu.month, obtenu.day, obtenu.hour), (12, 8, 8))


class TestVarianceLiberee(unittest.TestCase):
    """Le test qui dit pourquoi le dispositif existe.

    Sur la journée simulée seule, la météo est une constante. Le tirage doit
    produire une vraie dispersion, sinon il ne sert à rien.
    """

    def setUp(self) -> None:
        try:
            from urban_mobility_agents.utils.weather_loader import get_weather
        except Exception as err:  # pragma: no cover
            self.skipTest(f"chargeur météo indisponible : {err}")
        self.get_weather = get_weather
        self.jours = jours_eligibles(*FENETRE_ENQUETE, JOURS_OUVRES)
        self.depart = int(dt.datetime(2026, 3, 16, 8, 0, 0).timestamp())
        if self.get_weather(self.depart) is None:
            self.skipTest("données météo absentes du dépôt")

    def test_variance_nulle_sans_dispositif(self):
        temperatures = {self.get_weather(self.depart)["temperature"] for _ in range(100)}
        self.assertEqual(len(temperatures), 1, "sans dispositif, une seule météo pour tous")

    def test_dispersion_avec_dispositif(self):
        temperatures, precipitants = [], 0
        for i in range(500):
            meteo = self.get_weather(timestamp_meteo(self.depart, f"p{i}", 42, self.jours))
            if meteo is None:
                continue
            temperatures.append(meteo["temperature"])
            precipitants += meteo["precip_mm"] > 0
        self.assertGreater(len(set(temperatures)), 20)
        self.assertGreater(max(temperatures) - min(temperatures), 15)
        self.assertGreater(precipitants, 50, "une part substantielle doit voir de la pluie")


class TestNonRegression(unittest.TestCase):
    """Drapeau à faux → l'horloge simulée, à l'identique."""

    def test_dispositif_desactive_par_defaut(self):
        from settings import settings

        self.assertFalse(
            settings.agent.weather_per_agent_dates,
            "le dispositif doit être désactivé par défaut : rien ne bouge sans intention",
        )

    def test_agent_retombe_sur_lhorloge_simulee(self):
        """Drapeau à faux : `_weather_timestamp` rend l'horloge simulée, telle quelle.

        Un doublon de contexte plutôt qu'un `Person` complet : ce qui est sous test
        est le branchement, pas la validation du modèle de personne — et un test
        qui casse quand un champ de `PersonalIdentity` bouge ne dit rien d'utile
        sur la météo.
        """
        from types import SimpleNamespace

        from settings import settings
        from urban_mobility_agents.agents.llm_agent import LlmAgent

        self.assertFalse(settings.agent.weather_per_agent_dates)
        contexte = SimpleNamespace(
            timestamp=1773648000, person=SimpleNamespace(person_id="p1")
        )
        self.assertEqual(LlmAgent._weather_timestamp(None, contexte), 1773648000)

    def test_agent_tire_une_date_quand_le_dispositif_est_actif(self):
        """Drapeau à vrai : la date change, l'heure du départ non."""
        from types import SimpleNamespace

        from settings import settings
        from urban_mobility_agents.agents.llm_agent import LlmAgent

        depart = int(dt.datetime(2026, 3, 16, 8, 0, 0).timestamp())
        contexte = SimpleNamespace(timestamp=depart, person=SimpleNamespace(person_id="p1"))
        initial = settings.agent.weather_per_agent_dates
        settings.agent.weather_per_agent_dates = True
        try:
            obtenu = LlmAgent._weather_timestamp(None, contexte)
        finally:
            settings.agent.weather_per_agent_dates = initial

        tire = dt.datetime.fromtimestamp(obtenu)
        reference = dt.datetime.fromtimestamp(depart)
        self.assertEqual((tire.hour, tire.minute), (reference.hour, reference.minute))
        self.assertIn(
            (tire.month, tire.day),
            set(jours_eligibles(*FENETRE_ENQUETE, JOURS_OUVRES)),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
