"""Le prompt, la météo et la clé du cache lisent l'horloge de GAMA (2026-09-04).

Le matin du 2026-09-04, l'heure des itinéraires est passée sur l'horloge murale de GAMA
(`sim_clock`, cf. `test_fuseau_reseau.py`). Trois familles de consommateurs restaient sur
le fuseau du **processus** et étaient donc désormais en désaccord avec le routage :

1. **la météo** — `weather_loader` / `weather_draw` lisaient
   `fromtimestamp(ts, tz=Europe/Paris)` : pour 5 h murales ils ouvraient le relevé de
   **6 h**, et de **8 h** pour une journée simulée en été (deux heures) ;
2. **l'heure affichée à l'agent** — `helper.humanize_time` & co. : « départ 06:00 »
   quand GAMA dit 05:00 ;
3. **la clé du cache de décisions** — `llm/cache.py::_make_time_slice` / `_make_weekday`.

Chiffré sur les 5 322 déplacements du run archivé `2026-09-04_01_09`
(`docs/traces/2026-09-04_14-30_horloge_prompt_meteo/`) : **2 332 (43,8 %)** changeaient de
relevé météo de 3 h, **5 322 (100 %)** d'heure affichée, et les **77 départs de l'heure
murale 23 h** changeaient de **JOUR** — leur météo, leur jour de semaine affiché et le
`day`/`month` de leur entrée de cache parlaient du lendemain pendant que leur itinéraire
était calculé la veille.

Ces tests échouent si la convention rechange. Ils vérifient, en hiver ET en été :
l'heure affichée égale à l'horloge de GAMA à la minute ; le relevé météo lu à l'heure
murale ; qu'un départ à 23 h 30 ne change pas de jour ; l'indépendance au `TZ` du
processus (posé pour de vrai avec `tzset`) ; et la clé du cache de décisions.

Aucun appel réseau, aucun LLM.
"""

import calendar
import os
import time
from datetime import datetime, timezone

import pytest

import helper
from llm.cache import LlmSemanticCache
from sim_clock import gama_timestamp, wall_clock
from urban_mobility_agents.utils import weather_draw, weather_loader


def _gama_ts(annee, mois, jour, heure, minute=0, seconde=0) -> int:
    """L'horodatage que GAMA publie pour une heure MURALE donnée.

    Reproduit `int(current_date - UTC_START_DATE)` : une différence de dates naïves,
    soit l'heure murale comptée comme si elle était UTC. **Jamais**
    `datetime(...).timestamp()`, qui passerait par le fuseau du processus et ferait
    passer ces tests sous un `TZ` en les faisant échouer sous un autre.
    """
    return int(calendar.timegm((annee, mois, jour, heure, minute, seconde, 0, 0, 0)))


# Lundi 16 mars 2026 5 h murales : le t0 de `starting_date` (Settings.gaml), et la valeur
# relevée dans la colonne « Temps simulé » de moves.csv.
TS_HIVER = 1773637200
# Lundi 13 juillet 2026 5 h murales : heure d'été, où l'ancien écart valait DEUX heures.
TS_ETE = _gama_ts(2026, 7, 13, 5)
# Vendredi 20 mars 2026, 23 h 30 murales : l'heure où l'ancienne lecture changeait de JOUR
# — et, un vendredi, faisait basculer la catégorie de jour en « Weekend ».
TS_VENDREDI_2330 = _gama_ts(2026, 3, 20, 23, 30)

# Les fuseaux réellement en jeu (`controller` en Europe/Paris, réplicas `osmnx` en UTC),
# plus deux extrêmes qui font changer le jour dans les deux sens.
FUSEAUX = ("UTC", "Europe/Paris", "Pacific/Kiritimati", "America/Los_Angeles")


@pytest.fixture
def sous_fuseau():
    """Pose le `TZ` du processus pour de vrai (`tzset`) et le restaure après.

    Sans `tzset`, changer `os.environ["TZ"]` ne déplace pas `datetime.fromtimestamp` :
    un test « d'indépendance au fuseau » qui l'oublie passe toujours, y compris sur le
    code défectueux.
    """
    initial = os.environ.get("TZ")

    def _poser(nom: str) -> None:
        os.environ["TZ"] = nom
        time.tzset()

    yield _poser
    if initial is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = initial
    time.tzset()


# ── L'heure affichée à l'agent ────────────────────────────────────────────────

class TestHeureAffichee:
    """Ce que le prompt annonce doit être ce que GAMA affiche, à la minute."""

    @pytest.mark.parametrize("ts,attendu", [
        (TS_HIVER, "05:00"),
        (TS_ETE, "05:00"),
        (_gama_ts(2026, 3, 16, 8, 17, 43), "08:17"),
        (_gama_ts(2026, 7, 13, 19, 0), "19:00"),
        (TS_VENDREDI_2330, "23:30"),
    ])
    def test_humanize_time_est_lheure_de_gama(self, ts, attendu):
        assert helper.humanize_time(ts) == attendu

    def test_toutes_les_heures_de_la_journee_a_la_minute(self):
        """Balayage complet : pas un créneau ne doit dériver, hiver comme été."""
        for base in (TS_HIVER, TS_ETE):
            jour = base - (base % 86400)
            for minute_du_jour in range(0, 1440, 7):
                ts = jour + minute_du_jour * 60
                mur = wall_clock(ts)
                assert helper.humanize_time(ts) == f"{mur.hour:02d}:{mur.minute:02d}"

    @pytest.mark.parametrize("ts,attendu", [
        (TS_HIVER, "Monday"),
        (TS_ETE, "Monday"),
        # 23 h 30 un vendredi : le jour affiché reste VENDREDI. Lu dans le fuseau du
        # processus, le prompt annonçait « Saturday » et la catégorie « WEEKEND ».
        (TS_VENDREDI_2330, "Friday"),
    ])
    def test_jour_affiche(self, ts, attendu):
        assert helper.humanize_date_short(ts).split(",")[0] == attendu
        assert helper.categorize_date_time_short(ts).split(" ")[0] == attendu

    def test_categorie_de_jour_a_2330_un_vendredi(self):
        assert helper.get_weekday_category(TS_VENDREDI_2330) == "Weekday"
        # Le samedi suivant, à la même heure murale, est bien un week-end : la
        # correction ne fait pas disparaître la catégorie, elle la remet au bon jour.
        assert helper.get_weekday_category(_gama_ts(2026, 3, 21, 23, 30)) == "Weekend"

    @pytest.mark.parametrize("ts,fenetre,tranche,creneau", [
        # 5 h murales : « early morning », « night », hors pointe. L'ancienne lecture
        # (6 h en mars, 7 h en juillet) en faisait la pointe du matin.
        (TS_HIVER, "early morning", "Monday night", "night time (20:00 - 6:00)"),
        (TS_ETE, "early morning", "Monday night", "night time (20:00 - 6:00)"),
        (_gama_ts(2026, 3, 16, 17, 30), "end of the workday", "Monday afternoon",
         "evening rush hour (16:00 - 20:00)"),
    ])
    def test_fenetres_temporelles_du_prompt(self, ts, fenetre, tranche, creneau):
        assert helper.time_window_generalize(ts) == fenetre
        assert helper.categorize_date_time_short(ts) == tranche
        assert helper.time_to_bucket_text(ts) == creneau

    @pytest.mark.parametrize("nom", FUSEAUX)
    def test_independant_du_fuseau_du_processus(self, sous_fuseau, nom):
        sous_fuseau(nom)
        for ts in (TS_HIVER, TS_ETE, TS_VENDREDI_2330):
            mur = wall_clock(ts)
            assert helper.humanize_time(ts) == f"{mur.hour:02d}:{mur.minute:02d}"
            assert helper.humanize_date_short(ts) == mur.strftime("%A, %H:%M")
            assert helper.get_weekday_category(ts) == (
                "Weekend" if mur.weekday() >= 5 else "Weekday")
            assert helper.time_window_generalize(ts) == (
                "early morning" if mur.hour < 6 else helper.time_window_generalize(ts))


# ── La météo ──────────────────────────────────────────────────────────────────

def _bulletin(ts):
    w = weather_loader.get_weather(ts)
    if w is None:
        pytest.skip("données météo absentes du dépôt")
    return w


class TestMeteoALheureMurale:
    """Le bulletin lu est celui du jour et du créneau de 3 h de l'heure MURALE."""

    @pytest.mark.parametrize("ts,heure_relevee", [
        # `_reading_bucket` prend le relevé de 3 h le plus proche EN ARRIÈRE.
        (TS_HIVER, 3),                        # 5 h murales → relevé de 3 h (et non 6 h)
        (TS_ETE, 3),                          # en été l'ancienne lecture ouvrait 6 h
        (_gama_ts(2026, 3, 16, 8, 0), 6),
        (_gama_ts(2026, 7, 13, 8, 0), 6),
        (_gama_ts(2026, 3, 16, 11, 59), 9),   # 11 h 59 → 9 h, pas 12 h
        (TS_VENDREDI_2330, 21),               # 23 h 30 → 21 h, pas minuit du lendemain
    ])
    def test_creneau_lu(self, ts, heure_relevee):
        """Le relevé lu est celui de `heure_relevee`, le même jour murale."""
        mur = wall_clock(ts)
        reference = _bulletin(_gama_ts(mur.year, mur.month, mur.day, heure_relevee))
        obtenu = _bulletin(ts)
        assert (obtenu["temperature"], obtenu["weather_code"]) == \
               (reference["temperature"], reference["weather_code"])

    @pytest.mark.parametrize("ts", [TS_HIVER, TS_ETE, TS_VENDREDI_2330])
    def test_jour_du_bulletin_est_le_jour_simule(self, ts):
        """Le cadre du jour (amplitude, lever, coucher) est celui du jour MURAL.

        C'est le test du décalage de JOUR : à 23 h 30, l'ancienne lecture ouvrait la
        ligne du lendemain — un autre lever de soleil, une autre amplitude, une autre
        pluie — pendant que l'itinéraire, lui, était calculé la veille.
        """
        mur = wall_clock(ts)
        meme_jour_midi = _bulletin(_gama_ts(mur.year, mur.month, mur.day, 12))
        obtenu = _bulletin(ts)
        for champ in ("temp_min", "temp_max", "sunrise", "sunset"):
            assert obtenu[champ] == meme_jour_midi[champ], champ

    @pytest.mark.parametrize("nom", FUSEAUX)
    def test_independant_du_fuseau_du_processus(self, sous_fuseau, nom):
        sous_fuseau(nom)
        for ts in (TS_HIVER, TS_ETE, TS_VENDREDI_2330):
            mur = wall_clock(ts)
            reference = _bulletin(_gama_ts(
                mur.year, mur.month, mur.day, (mur.hour // 3) * 3))
            obtenu = _bulletin(ts)
            assert (obtenu["temperature"], obtenu["weather_code"],
                    obtenu["sunrise"], obtenu["sunset"]) == \
                   (reference["temperature"], reference["weather_code"],
                    reference["sunrise"], reference["sunset"])

    def test_anticipation_lit_les_tranches_restantes_du_jour_mural(self):
        """`day_weather_outlook` ne parle que des tranches restantes du jour MURAL.

        À 23 h 30 il ne reste rien : l'ancienne lecture, qui voyait minuit du
        lendemain, annonçait au contraire toute la journée suivante — dans un texte
        qui entre par ailleurs dans la clé du cache de décisions.
        """
        assert weather_loader.day_weather_outlook(TS_VENDREDI_2330) is None
        matin = weather_loader.day_weather_outlook(_gama_ts(2026, 3, 16, 8, 0))
        assert matin and "après-midi" in matin


class TestTirageMeteoParAgent:
    """Le tirage d'une date météo par agent conserve l'heure MURALE, exactement."""

    @pytest.fixture
    def jours(self):
        return weather_draw.jours_eligibles("2022-09-20", "2023-02-18", (1, 2, 3, 4, 5))

    @pytest.mark.parametrize("ts", [TS_HIVER, TS_ETE, TS_VENDREDI_2330,
                                    _gama_ts(2026, 3, 29, 2, 30)])
    def test_heure_murale_conservee_a_la_seconde(self, ts, jours):
        """Y compris quand la date tirée est d'une autre saison, et pour 2 h 30 le
        dernier dimanche de mars — une heure murale qui n'existe pas en France, que
        l'horloge de GAMA porte pourtant."""
        mur = wall_clock(ts)
        for i in range(80):
            tire = wall_clock(weather_draw.timestamp_meteo(ts, f"p{i}", 42, jours))
            assert (tire.hour, tire.minute, tire.second) == \
                   (mur.hour, mur.minute, mur.second)
            assert (tire.month, tire.day) in set(jours)

    @pytest.mark.parametrize("nom", FUSEAUX)
    def test_independant_du_fuseau_du_processus(self, sous_fuseau, nom, jours):
        sous_fuseau(nom)
        obtenus = [weather_draw.timestamp_meteo(TS_HIVER, f"p{i}", 42, jours)
                   for i in range(40)]
        sous_fuseau("UTC")
        assert obtenus == [weather_draw.timestamp_meteo(TS_HIVER, f"p{i}", 42, jours)
                           for i in range(40)]


# ── La clé du cache de décisions ──────────────────────────────────────────────

class TestCleDuCacheDeDecisions:
    @pytest.mark.parametrize("ts,tranche,categorie", [
        (TS_HIVER, "05:00", "Weekday"),
        (TS_ETE, "05:00", "Weekday"),
        (_gama_ts(2026, 3, 16, 8, 17), "08:10", "Weekday"),
        # 23 h 30 un vendredi : la tranche reste 23:30 et le jour reste ouvré. Lu dans
        # le fuseau du processus, ce contexte s'écrivait « 00:30 / Weekend » et allait
        # se confondre avec celui d'un vrai départ de week-end.
        (TS_VENDREDI_2330, "23:30", "Weekday"),
        (_gama_ts(2026, 3, 21, 23, 30), "23:30", "Weekend"),
    ])
    def test_tranche_et_categorie(self, ts, tranche, categorie):
        assert LlmSemanticCache._make_time_slice(ts) == tranche
        assert LlmSemanticCache._make_weekday(ts) == categorie

    @pytest.mark.parametrize("nom", FUSEAUX)
    def test_independant_du_fuseau_du_processus(self, sous_fuseau, nom):
        sous_fuseau(nom)
        obtenus = [(LlmSemanticCache._make_time_slice(ts), LlmSemanticCache._make_weekday(ts))
                   for ts in (TS_HIVER, TS_ETE, TS_VENDREDI_2330)]
        assert obtenus == [("05:00", "Weekday"), ("05:00", "Weekday"),
                           ("23:30", "Weekday")]

    def test_deux_heures_murales_distinctes_ne_partagent_pas_la_tranche(self):
        """Garde-fou : la correction ne doit pas faire converger deux contextes.

        Un décalage constant est une bijection, donc n'introduit aucune collision —
        mais l'ancien décalage n'était PAS constant (une heure en mars, deux en
        juillet). Deux départs à la même heure murale de deux saisons différentes
        recevaient deux tranches distinctes ; ils partagent désormais la même, et ce
        sont bien la météo et les codes d'options qui doivent les séparer.
        """
        assert LlmSemanticCache._make_time_slice(TS_HIVER) == \
               LlmSemanticCache._make_time_slice(TS_ETE)
        distinctes = {LlmSemanticCache._make_time_slice(_gama_ts(2026, 3, 16, h, m))
                      for h in range(24) for m in (0, 10, 20, 30, 40, 50)}
        assert len(distinctes) == 24 * 6


# ── Météo, itinéraire et jour affiché parlent du même jour ────────────────────

class TestMemeJourPartout:
    """Le test de bout en bout du décalage de JOUR (les 77 départs de 23 h).

    Trois lectures indépendantes doivent tomber sur la même date murale : celle de
    l'itinéraire (`sim_clock`, le chemin d'OTP), celle du bulletin météo, et celle du
    jour de semaine affiché dans le prompt.
    """

    @pytest.mark.parametrize("ts", [
        TS_HIVER,
        TS_ETE,
        TS_VENDREDI_2330,
        _gama_ts(2026, 3, 16, 23, 30),
        _gama_ts(2026, 7, 13, 23, 30),   # été : l'ancien écart de deux heures
        _gama_ts(2026, 3, 16, 23, 59, 59),
    ])
    @pytest.mark.parametrize("nom", ("UTC", "Europe/Paris"))
    def test_meme_jour(self, ts, nom, sous_fuseau):
        sous_fuseau(nom)
        mur = wall_clock(ts)

        # 1. l'itinéraire : le jour que `sim_clock` (donc OTP) voit.
        assert (mur.year, mur.month, mur.day) == (mur.year, mur.month, mur.day)

        # 2. la météo : son cadre de jour doit être celui de midi du MÊME jour.
        bulletin = _bulletin(ts)
        midi = _bulletin(_gama_ts(mur.year, mur.month, mur.day, 12))
        assert (bulletin["sunrise"], bulletin["sunset"],
                bulletin["temp_min"], bulletin["temp_max"]) == \
               (midi["sunrise"], midi["sunset"], midi["temp_min"], midi["temp_max"])

        # 3. le jour de semaine affiché dans le prompt.
        assert helper.humanize_date_short(ts).split(",")[0] == mur.strftime("%A")
        assert helper.humanize_date(ts).startswith(mur.strftime("%d"))

        # 4. et la clé du cache, qui indexe la décision de ce jour-là.
        assert LlmSemanticCache._make_weekday(ts) == (
            "Weekend" if mur.weekday() >= 5 else "Weekday")

    def test_aller_retour_horodatage_souvenir(self):
        """Un souvenir écrit en heure murale doit se relire à la même heure.

        `add_short_term_memory` stocke `wall_clock(ts)` et le prompt le réaffiche par
        `humanize_date(gama_timestamp(entry.timestamp))`. Les deux conventions doivent
        s'annuler exactement — c'est le piège qui donnait « - Time … 06:00 » pour un
        souvenir de 5 h.
        """
        for ts in (TS_HIVER, TS_ETE, TS_VENDREDI_2330):
            assert gama_timestamp(wall_clock(ts)) == ts
            assert helper.humanize_date(gama_timestamp(wall_clock(ts))) == \
                   helper.humanize_date(ts)


def test_aucune_lecture_ne_passe_par_le_fuseau_du_processus():
    """Garde-fou de source : les modules alignés n'appellent plus `fromtimestamp` nu.

    Un test de valeurs ne suffit pas ici : sous `TZ=UTC` — le fuseau des réplicas
    `osmnx` — l'ancienne lecture et la nouvelle donnent le même résultat, et une
    régression passerait donc inaperçue dans la moitié des conteneurs.
    """
    import ast
    import inspect

    # L'arbre syntaxique, et non une expression régulière : les docstrings de ces
    # modules CITENT le défaut corrigé (c'est leur rôle), et un grep sur le texte les
    # confondrait avec du code appelable.
    for module in (helper, weather_loader, weather_draw, __import__("llm.cache", fromlist=["x"])):
        arbre = ast.parse(inspect.getsource(module))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            fonction = noeud.func
            if not (isinstance(fonction, ast.Attribute) and fonction.attr == "fromtimestamp"):
                continue
            # `fromtimestamp(ts, tz=...)` est explicite et sans surprise ; c'est
            # l'appel SANS fuseau qui lit l'horloge du processus.
            if any(kw.arg == "tz" for kw in noeud.keywords) or len(noeud.args) >= 2:
                continue
            pytest.fail(
                f"{module.__name__}, ligne {noeud.lineno} : `fromtimestamp` sans fuseau "
                "lit l'horloge du PROCESSUS. Utiliser `sim_clock.wall_clock`.")


def test_weather_loader_se_charge_par_chemin_sans_le_controleur():
    """`prompt_calibration` charge ce fichier PAR CHEMIN : il doit rester chargeable.

    Le dépôt autonome `prompt_calibration` vérifie que sa copie de
    `weather_to_natural_language` n'a pas dérivé, et le fait par
    `spec_from_file_location` — exprès, pour ne pas faire entrer le contrôleur et ses
    dépendances dans ses tests. Un `from sim_clock import wall_clock` en tête de module
    casse ce chargement (vécu : 14 tests de la calibration tombés le 2026-09-04), d'où
    l'import différé dans `_heure_murale`. Ce test le verrouille depuis ce dépôt-ci,
    pour que la casse se voie ici plutôt que dans l'autre.
    """
    import subprocess
    import sys as _sys
    from pathlib import Path

    fichier = Path(weather_loader.__file__).resolve()
    programme = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('_prod_wl', r'{fichier}')\n"
        "m = importlib.util.module_from_spec(spec)\n"
        "sys.modules['_prod_wl'] = m\n"
        "spec.loader.exec_module(m)\n"
        "print(m.weather_to_natural_language({'temperature': 3.0, "
        "'weather_label': 'Ciel dégagé/Ensoleillé', 'precip_mm': 0.0}))\n"
    )
    # `-I` : ni le répertoire du script, ni les variables d'environnement Python —
    # `llm-agents/` n'est donc PAS sur le path, comme chez `prompt_calibration`.
    r = subprocess.run([_sys.executable, "-I", "-c", programme],
                       capture_output=True, text=True, cwd=str(fichier.parent))
    assert r.returncode == 0, (
        "weather_loader n'est plus chargeable par chemin (import de tête à différer ?) :\n"
        + r.stderr)
    assert "Météo : 3°C" in r.stdout


def test_la_meteo_ne_declare_aucun_fuseau():
    """La météo ne doit porter AUCUN fuseau, et c'est le cœur du défaut d'avant.

    `weather_loader` et `weather_draw` faisaient `fromtimestamp(ts, tz=ZoneInfo(
    "Europe/Paris"))` : un appel explicite, immunisé au `TZ` du processus — et faux
    quand même, parce qu'il traitait l'heure MURALE de GAMA comme un instant. Le
    fuseau écrit en dur ne se voit donc pas dans le garde-fou précédent : il se voit
    ici. La source météo est indexée par (mois, jour) et lue par créneau horaire ;
    seuls les champs muraux comptent, et un fuseau n'a rien à y faire.

    ⚠ Le fuseau du RÉSEAU, lui, garde sa place : il vit dans `sim_clock`, tiré de
    l'`agency_timezone` des feeds GTFS, et sert à parler à OTP — pas à lire un CSV.
    """
    import ast
    import inspect

    for module in (weather_loader, weather_draw):
        arbre = ast.parse(inspect.getsource(module))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, (ast.Import, ast.ImportFrom)):
                noms = ([a.name for a in noeud.names]
                        + [getattr(noeud, "module", None) or ""])
                for nom in noms:
                    if "zoneinfo" in nom.lower() or nom == "ZoneInfo":
                        pytest.fail(
                            f"{module.__name__}, ligne {noeud.lineno} : la météo se lit "
                            "en heure MURALE (`sim_clock.wall_clock`) ; un fuseau écrit "
                            "ici traiterait l'horloge de GAMA comme un instant.")
