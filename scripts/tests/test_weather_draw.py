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

import calendar
import collections
import datetime as dt
import os
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "llm-agents"))

from sim_clock import wall_clock  # noqa: E402
from urban_mobility_agents.utils.weather_draw import (  # noqa: E402
    date_meteo,
    indice_agent,
    jours_eligibles,
    timestamp_meteo,
)


def mur(annee, mois, jour, heure=0, minute=0, seconde=0) -> int:
    """Horodatage GAMA d'une heure MURALE — l'inverse de `sim_clock.wall_clock`.

    ⚠ Pas `datetime(...).timestamp()` : celui-là lit l'heure dans le fuseau du
    PROCESSUS, et un test bâti dessus passe sous `TZ=UTC` en échouant sous
    `TZ=Europe/Paris` (ou l'inverse selon la saison).
    """
    return calendar.timegm(dt.datetime(annee, mois, jour, heure, minute, seconde).timetuple())

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
    """⚠ Ces tests parlent en heure MURALE, la seule convention de l'horloge de GAMA.

    Les horodatages d'entrée sont construits par :func:`mur` (`calendar.timegm`) et
    relus par :func:`sim_clock.wall_clock`, jamais par `datetime(...).timestamp()` /
    `datetime.fromtimestamp(...)` : ce couple passe par le fuseau du PROCESSUS et
    s'annulait par chance en hiver, pas en été — c'est ce qui a laissé le décalage
    invisible jusqu'au 2026-09-04.
    """

    def setUp(self) -> None:
        self.jours = jours_eligibles(*FENETRE_ENQUETE, JOURS_OUVRES)

    def test_heure_du_depart_conservee(self):
        """Le bulletin se lit par créneaux de 3 h : l'heure ne doit pas bouger."""
        for heure in (5, 8, 12, 17, 21, 23):
            depart = mur(2026, 3, 16, heure, 37, 12)
            for person_id in ("p1", "p2", "p3", "p400"):
                obtenu = wall_clock(timestamp_meteo(depart, person_id, 42, self.jours))
                self.assertEqual((obtenu.hour, obtenu.minute, obtenu.second), (heure, 37, 12))

    def test_seule_la_date_change(self):
        depart = mur(2026, 3, 16, 8, 0, 0)
        attendu = date_meteo("p7", 42, self.jours)
        obtenu = wall_clock(timestamp_meteo(depart, "p7", 42, self.jours))
        self.assertEqual((obtenu.month, obtenu.day), attendu)

    def test_le_meme_agent_garde_sa_journee_quelle_que_soit_lheure(self):
        """La météo d'un agent ne doit pas dépendre de l'heure de son départ :
        sinon ses trajets du matin et du soir vivraient deux journées."""
        matin = mur(2026, 3, 16, 8, 0, 0)
        soir = mur(2026, 3, 16, 18, 30, 0)
        a = wall_clock(timestamp_meteo(matin, "p9", 42, self.jours))
        b = wall_clock(timestamp_meteo(soir, "p9", 42, self.jours))
        self.assertEqual((a.month, a.day), (b.month, b.day))

    def test_heure_conservee_au_franchissement_ete_hiver(self):
        """La date tirée peut être d'une autre saison que la journée simulée : l'heure
        MURALE doit être conservée à la seconde dans les deux sens.

        La fenêtre d'enquête (20/09 → 18/02) traverse la bascule heure d'été/hiver.
        L'ancienne version passait par des instants (`fromtimestamp(tz=...)` puis
        `.timestamp()`), et devait donc raisonner sur des offsets UTC. L'horloge de
        GAMA n'a pas de bascule : en champs muraux la conservation est exacte, et il
        n'y a plus d'offset à recalculer.
        """
        for depart, jours_cibles in (
            (mur(2026, 9, 22, 8, 0, 0), [(12, 8)]),    # journée d'été → météo d'hiver
            (mur(2026, 12, 8, 8, 0, 0), [(9, 22)]),    # journée d'hiver → météo d'été
            (mur(2026, 3, 29, 2, 30, 0), [(12, 8)]),   # heure murale INEXISTANTE en France
        ):
            obtenu = wall_clock(timestamp_meteo(depart, "p-dst", 42, jours_cibles))
            attendu_mois, attendu_jour = jours_cibles[0]
            depart_mur = wall_clock(depart)
            self.assertEqual(
                (obtenu.month, obtenu.day, obtenu.hour, obtenu.minute, obtenu.second),
                (attendu_mois, attendu_jour, depart_mur.hour, depart_mur.minute,
                 depart_mur.second))

    def test_independant_du_fuseau_du_processus(self):
        """Le même départ doit rendre le même bulletin sous n'importe quel `TZ`.

        Le `controller` tourne en `TZ=Europe/Paris` et les réplicas `osmnx` en
        `TZ=UTC` : une météo qui dépend du fuseau du processus n'est pas reproductible
        d'un conteneur à l'autre, et une trace archivée ne se rejoue plus.
        """
        depart = mur(2026, 3, 16, 8, 37, 12)
        obtenus = {}
        initial = os.environ.get("TZ")
        try:
            for tz in ("UTC", "Europe/Paris", "Pacific/Kiritimati", "America/Los_Angeles"):
                os.environ["TZ"] = tz
                time.tzset()
                obtenus[tz] = [timestamp_meteo(depart, f"p{i}", 42, self.jours)
                               for i in range(50)]
        finally:
            if initial is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = initial
            time.tzset()

        distincts = {tuple(v) for v in obtenus.values()}
        self.assertEqual(len(distincts), 1,
                         "le tirage météo dépend du fuseau du processus")


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
        self.depart = mur(2026, 3, 16, 8, 0, 0)
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
    """Drapeau à faux → l'horloge simulée, à l'identique.

    ⚠ **« Par défaut » veut dire deux choses, et les confondre a fait échouer ces
    tests pendant une journée** (2026-09-04). Le DÉFAUT DU CODE est
    `Settings.weather_per_agent_dates = False` : rien ne bouge si personne ne le
    demande. La CONFIGURATION DU RUN, elle, l'active délibérément
    (`llm-agents/config/config.yaml`, ticket 023 lot 4 : sans tirage, les 1 000 agents
    d'une journée simulée partagent une météo et l'effet météo est par construction
    non mesurable). Un test qui lit `settings.agent.…` lit la configuration du run,
    pas le défaut du code — il affirmait donc que le dépôt n'active pas un dispositif
    que le dépôt active exprès. Chaque affirmation est ici vérifiée à sa source.
    """

    def test_defaut_du_code_desactive(self):
        """Le défaut du CODE : rien ne bouge sans intention explicite."""
        from settings import settings

        champ = type(settings.agent).model_fields["weather_per_agent_dates"]
        self.assertFalse(
            champ.default,
            "le défaut du code doit rester faux : rien ne bouge sans intention",
        )

    def test_configuration_de_run_active_le_dispositif(self):
        """La configuration du run l'active, et c'est une décision, pas un accident.

        Si ce test tombe, c'est que `config.yaml` a cessé d'activer le tirage : les
        runs suivants mesureraient l'effet météo sur un régresseur de variance nulle
        — « aucun effet » ne voudrait alors rien dire (ticket 023).
        """
        import yaml

        chemin = REPO_ROOT / "llm-agents" / "config" / "config.yaml"
        brut = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
        agent = brut.get("agent") or {}
        self.assertTrue(
            agent.get("weather_per_agent_dates"),
            f"{chemin} doit activer le tirage d'une date météo par agent",
        )

        from settings import settings

        self.assertTrue(
            settings.agent.weather_per_agent_dates,
            "la configuration lue par le runtime doit refléter config.yaml",
        )

    def test_agent_retombe_sur_lhorloge_simulee(self):
        """Drapeau à faux : `_weather_timestamp` rend l'horloge simulée, telle quelle.

        Le drapeau est forcé ici, comme le fait le test symétrique : ce qui est sous
        test est le BRANCHEMENT, pas la valeur que porte la configuration du run.

        Un doublon de contexte plutôt qu'un `Person` complet : ce qui est sous test
        est le branchement, pas la validation du modèle de personne — et un test
        qui casse quand un champ de `PersonalIdentity` bouge ne dit rien d'utile
        sur la météo.
        """
        from types import SimpleNamespace

        from settings import settings
        from urban_mobility_agents.agents.llm_agent import LlmAgent

        contexte = SimpleNamespace(
            timestamp=1773648000, person=SimpleNamespace(person_id="p1")
        )
        initial = settings.agent.weather_per_agent_dates
        settings.agent.weather_per_agent_dates = False
        try:
            self.assertEqual(LlmAgent._weather_timestamp(None, contexte), 1773648000)
        finally:
            settings.agent.weather_per_agent_dates = initial

    def test_agent_tire_une_date_quand_le_dispositif_est_actif(self):
        """Drapeau à vrai : la date change, l'heure MURALE du départ non."""
        from types import SimpleNamespace

        from settings import settings
        from urban_mobility_agents.agents.llm_agent import LlmAgent

        depart = mur(2026, 3, 16, 8, 0, 0)
        contexte = SimpleNamespace(timestamp=depart, person=SimpleNamespace(person_id="p1"))
        initial = settings.agent.weather_per_agent_dates
        settings.agent.weather_per_agent_dates = True
        try:
            obtenu = LlmAgent._weather_timestamp(None, contexte)
        finally:
            settings.agent.weather_per_agent_dates = initial

        tire = wall_clock(obtenu)
        reference = wall_clock(depart)
        self.assertEqual((tire.hour, tire.minute), (reference.hour, reference.minute))
        self.assertIn(
            (tire.month, tire.day),
            set(jours_eligibles(*FENETRE_ENQUETE, JOURS_OUVRES)),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
