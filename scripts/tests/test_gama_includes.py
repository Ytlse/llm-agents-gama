"""Tests des deux recettes qui alimentent `GAMA/CityTransport/includes/`
(`scripts/data/gama/export_gtfs_layers.py` et `export_trip_info.py`).

LA RÉGRESSION VISÉE
-------------------
Le 2026-09-04, `routes.shp` portait **les trois réseaux** — 730 tracés dont 34 en
`route_type=2` — et `trip_info.json`, produit à la main cinq mois plus tôt, **le
seul Tisséo** : 39 343 courses, aucune en `route_type=2`. GAMA dessinait donc
34 lignes de TER et 68 gares où **aucun train ne roulerait**. Rien ne le disait :
une ligne visible et morte se lit comme une ligne sans passage.

Ces tests portent chacun sur une décision qui, prise à l'envers, produit un
fichier **plausible mais faux** :

  * un `route_type` tracé dans la couche mais sans course → la recette ÉCHOUE, et
    `trip_info.json` n'est pas écrit (le défaut des cinq mois) ;
  * un `route_type` tracé dont aucune course ne roule LE JOUR SIMULÉ → même refus :
    porter des courses en juin ne fait pas rouler un train en mars ;
  * la date simulée hors de la fenêtre → refus, là où GAMA se contente d'un `warn`
    et ne planifie plus rien ;
  * une fenêtre plus large que le masque binaire 64 bits du modèle → refus ;
  * deux réseaux qui numérotent leurs services pareil (`SVC_0001` : **224
    collisions** mesurées entre les feeds TER et liO) → les calendriers restent
    séparés, les cars ne lisent pas l'horaire des trains ;
  * un `shapes.txt` réduit à son en-tête n'est pas une géométrie publiée — le
    tester par sa seule existence rendait zéro tracé pour le TER, sans un mot ;
  * un réseau sans géométrie reçoit **un tracé par suite d'arrêts distincte**, et
    non un par (ligne, sens) : `build_trips` force le dernier segment jusqu'au
    dernier point du tracé, donc une course Toulouse → Tarbes posée sur le tracé
    Toulouse → Pau roulerait jusqu'à Pau ;
  * une course sans `direction_id` ne disparaît pas (6 courses TER s'évaporaient,
    leur `shape_id` valant `NaN`) ;
  * les deux recettes fabriquent les MÊMES `shape_id` — c'est ce qui empêche la
    couche et les courses de diverger en silence.

Feeds synthétiques minimaux : aucun accès réseau, aucun gros fichier, aucune
dépendance aux données du dépôt.
"""

from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.data.gama import export_trip_info as recette  # noqa: E402
from scripts.data.gama import gtfs_traces  # noqa: E402

# Dates de la fenêtre d'essai. Le jour simulé est le premier.
JOUR_SIMULE = "2026-03-16"
D0, D1, D2 = "20260316", "20260317", "20260318"

# Un coin de la carte toulousaine, pour que les longueurs en mètres soient réalistes.
LON0, LAT0 = 1.44, 43.60


def _ecrire(chemin: Path, colonnes: list[str], lignes: list[dict]) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="") as fh:
        ecrivain = csv.DictWriter(fh, fieldnames=colonnes, extrasaction="ignore")
        ecrivain.writeheader()
        for ligne in lignes:
            ecrivain.writerow({c: ligne.get(c, "") for c in colonnes})


def _arrets(prefixe: str, noms: list[str]) -> list[dict]:
    """Des arrêts alignés d'ouest en est, à 2 km l'un de l'autre environ."""
    return [
        {"stop_id": f"{prefixe}{nom}", "stop_name": f"Arrêt {prefixe}{nom}",
         "stop_lat": f"{LAT0}", "stop_lon": f"{LON0 + 0.025 * i}", "location_type": "0"}
        for i, nom in enumerate(noms)
    ]


def feed_avec_geometrie(dossier: Path, *, route_type: str = "3", dates=(D0, D1, D2),
                        service: str = "SVC_0001") -> Path:
    """Un réseau qui publie son `shapes.txt` : deux courses sur un tracé de 5 points."""
    dossier.mkdir(parents=True, exist_ok=True)
    stops = _arrets("B", ["1", "2", "3"])
    _ecrire(dossier / "stops.txt",
            ["stop_id", "stop_name", "stop_lat", "stop_lon", "location_type"], stops)
    _ecrire(dossier / "routes.txt",
            ["route_id", "route_short_name", "route_long_name", "route_type",
             "route_color", "route_text_color"],
            [{"route_id": "B1", "route_short_name": "B1", "route_long_name": "Ligne bus",
              "route_type": route_type, "route_color": "112233", "route_text_color": "FFFFFF"}])
    # Le tracé a 5 points ; les arrêts tombent sur les points 0, 2 et 4.
    points = [(LON0 + 0.0125 * i, LAT0) for i in range(5)]
    cumule = recette._cumul(points)
    _ecrire(dossier / "shapes.txt",
            ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence",
             "shape_dist_traveled"],
            [{"shape_id": "SH1", "shape_pt_lat": f"{lat}", "shape_pt_lon": f"{lon}",
              "shape_pt_sequence": str(i), "shape_dist_traveled": f"{cumule[i]}"}
             for i, (lon, lat) in enumerate(points)])
    _ecrire(dossier / "trips.txt",
            ["route_id", "service_id", "trip_id", "direction_id", "shape_id"],
            [{"route_id": "B1", "service_id": service, "trip_id": "bus_1",
              "direction_id": "0", "shape_id": "SH1"},
             {"route_id": "B1", "service_id": service, "trip_id": "bus_2",
              "direction_id": "0", "shape_id": "SH1"}])
    horaires = []
    for trip, heure in (("bus_1", 7), ("bus_2", 8)):
        for rang, (arret, point) in enumerate(zip(stops, (0, 2, 4))):
            horaires.append({"trip_id": trip, "stop_sequence": str(rang),
                             "stop_id": arret["stop_id"],
                             "arrival_time": f"{heure:02d}:{rang * 10:02d}:00",
                             "departure_time": f"{heure:02d}:{rang * 10:02d}:00",
                             "shape_dist_traveled": f"{cumule[point]}"})
    _ecrire(dossier / "stop_times.txt",
            ["trip_id", "stop_sequence", "stop_id", "arrival_time", "departure_time",
             "shape_dist_traveled"], horaires)
    _ecrire(dossier / "calendar_dates.txt", ["service_id", "date", "exception_type"],
            [{"service_id": service, "date": d, "exception_type": "1"} for d in dates])
    (dossier / "calendar.txt").write_text(
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\n", encoding="utf-8")
    return dossier


def feed_sans_geometrie(dossier: Path, *, route_type: str = "2", dates=(D0,),
                        service: str = "SVC_0001") -> Path:
    """Un réseau à la façon du TER : `shapes.txt` réduit à son en-tête.

    Trois courses sur la même ligne :
      * `rail_complet` dessert R1 R2 R3 R4 ;
      * `rail_partiel` s'arrête à R2 — c'est elle qui, posée sur le tracé de la
        course complète, roulerait jusqu'à R4 ;
      * `rail_sans_sens` n'a pas de `direction_id`.
    """
    dossier.mkdir(parents=True, exist_ok=True)
    stops = _arrets("R", ["1", "2", "3", "4"])
    _ecrire(dossier / "stops.txt",
            ["stop_id", "stop_name", "stop_lat", "stop_lon", "location_type"], stops)
    _ecrire(dossier / "routes.txt",
            ["route_id", "route_short_name", "route_long_name", "route_type",
             "route_color", "route_text_color"],
            [{"route_id": "R1", "route_short_name": "TER1", "route_long_name": "Ligne TER",
              "route_type": route_type, "route_color": "AA00AA", "route_text_color": "FFFFFF"}])
    # L'en-tête SEUL : le feed TER en publie un comme celui-ci.
    (dossier / "shapes.txt").write_text(
        "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence,shape_dist_traveled\n",
        encoding="utf-8")
    _ecrire(dossier / "trips.txt",
            ["route_id", "service_id", "trip_id", "direction_id", "shape_id"],
            [{"route_id": "R1", "service_id": service, "trip_id": "rail_complet",
              "direction_id": "0", "shape_id": ""},
             {"route_id": "R1", "service_id": service, "trip_id": "rail_partiel",
              "direction_id": "0", "shape_id": ""},
             {"route_id": "R1", "service_id": service, "trip_id": "rail_sans_sens",
              "direction_id": "", "shape_id": ""}])
    dessertes = {"rail_complet": ["R1", "R2", "R3", "R4"],
                 "rail_partiel": ["R1", "R2"],
                 "rail_sans_sens": ["R4", "R3", "R1"]}
    horaires = []
    for heure, (trip, suite) in enumerate(dessertes.items(), start=6):
        for rang, arret in enumerate(suite):
            horaires.append({"trip_id": trip, "stop_sequence": str(rang), "stop_id": arret,
                             "arrival_time": f"{heure:02d}:{rang * 15:02d}:00",
                             "departure_time": f"{heure:02d}:{rang * 15:02d}:00",
                             "shape_dist_traveled": ""})
    _ecrire(dossier / "stop_times.txt",
            ["trip_id", "stop_sequence", "stop_id", "arrival_time", "departure_time",
             "shape_dist_traveled"], horaires)
    _ecrire(dossier / "calendar_dates.txt", ["service_id", "date", "exception_type"],
            [{"service_id": service, "date": d, "exception_type": "1"} for d in dates])
    (dossier / "calendar.txt").write_text(
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\n", encoding="utf-8")
    return dossier


def couche_depuis_feeds(feeds: dict[str, Path], chemin: Path,
                        garder=lambda shape_id, route_type: True) -> Path:
    """Fabrique un `routes.shp` d'essai, avec les `shape_id` du module partagé.

    `garder` permet d'en retirer des tracés : c'est ainsi qu'on reproduit une
    couche qui porte un `route_type` que les courses ignorent, ou l'inverse.
    """
    import geopandas as gpd
    from shapely.geometry import LineString

    lignes = []
    for reseau, feed in feeds.items():
        stops = {l["stop_id"]: (float(l["stop_lon"]), float(l["stop_lat"]))
                 for l in recette._lire_csv(feed / "stops.txt")}
        types = {l["route_id"]: l["route_type"]
                 for l in recette._lire_csv(feed / "routes.txt")}
        trips = recette._lire_csv(feed / "trips.txt")
        horaires = recette._lire_csv(feed / "stop_times.txt")
        if recette._a_des_geometries(feed):
            points: dict[str, list] = {}
            for l in recette._lire_csv(feed / "shapes.txt"):
                points.setdefault(l["shape_id"], []).append(
                    (int(l["shape_pt_sequence"]), float(l["shape_pt_lon"]),
                     float(l["shape_pt_lat"])))
            traces = {sid: [(lo, la) for _, lo, la in sorted(v)] for sid, v in points.items()}
            route_de = {l["shape_id"]: l["route_id"] for l in trips}
        else:
            suites = gtfs_traces.suites_depuis_stop_times(horaires)
            motifs, course_vers_trace, _ = gtfs_traces.traces_par_suite_d_arrets(
                trips, suites, journal=lambda *_a, **_k: None)
            traces = {sid: [stops[s] for s in suite] for sid, suite in motifs.items()}
            route_de = {course_vers_trace[l["trip_id"]]: l["route_id"]
                        for l in trips if l["trip_id"] in course_vers_trace}
        for shape_id, pts in traces.items():
            route_type = types[route_de[shape_id]]
            if not garder(shape_id, route_type):
                continue
            lignes.append({"shape_id": shape_id, "route_id": route_de[shape_id],
                           "route_type": route_type, "reseau": reseau,
                           "geometry": LineString(pts)})
    chemin.parent.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame(lignes, crs="EPSG:4326").to_file(chemin)
    return chemin


class BaseTemporaire(unittest.TestCase):
    def setUp(self):
        self.racine = Path(tempfile.mkdtemp(prefix="gama_includes_"))
        self.addCleanup(shutil.rmtree, self.racine, ignore_errors=True)
        self.feeds = {
            "bus": feed_avec_geometrie(self.racine / "feed_bus"),
            "rail": feed_sans_geometrie(self.racine / "feed_rail"),
        }
        self.sortie = self.racine / "trip_info.json"

    def lancer(self, *, couche: Path, jours: int = 64, date_simulee: str = JOUR_SIMULE,
               debut: str | None = None, sortie: Path | None = None) -> int:
        argv = ["--routes", str(couche), "--sortie", str(sortie or self.sortie),
                "--date-simulee", date_simulee, "--jours", str(jours)]
        if debut:
            argv += ["--debut", debut]
        for nom, chemin in self.feeds.items():
            argv += ["--feed", f"{nom}={chemin}"]
        return recette.main(argv)

    def produit(self, sortie: Path | None = None) -> dict:
        with open(sortie or self.sortie, encoding="utf-8") as fh:
            return json.load(fh)


class TestCoherenceCoucheCourses(BaseTemporaire):
    """Le décalage de cinq mois : une couche et des courses qui ne parlent pas des
    mêmes types de ligne."""

    def test_type_trace_sans_course_fait_echouer_la_recette(self):
        # La couche porte le rail ; les courses, non — exactement l'état du
        # 2026-09-04 (34 tracés de TER, zéro course de type 2).
        couche = couche_depuis_feeds(self.feeds, self.racine / "couche.shp")
        self.feeds.pop("rail")
        code = self.lancer(couche=couche)
        self.assertEqual(code, recette.CODE_REFUS)
        self.assertFalse(self.sortie.exists(),
                         "trip_info.json ne doit PAS être écrit quand un type tracé "
                         "n'a aucune course")

    def test_type_trace_sans_course_LE_JOUR_SIMULE_fait_echouer(self):
        # Le rail ne roule que le 18 ; le jour simulé est le 16. Le fichier
        # porterait des courses de type 2 — un compte non nul, donc rassurant —
        # dont aucune ne roulerait le jour de la simulation.
        self.feeds["rail"] = feed_sans_geometrie(self.racine / "feed_rail_tardif",
                                                 dates=(D2,), service="SVC_0009")
        couche = couche_depuis_feeds(self.feeds, self.racine / "couche.shp")
        code = self.lancer(couche=couche)
        self.assertEqual(code, recette.CODE_REFUS)
        self.assertFalse(self.sortie.exists())

    def test_cas_nominal_les_deux_types_roulent_le_jour_simule(self):
        couche = couche_depuis_feeds(self.feeds, self.racine / "couche.shp")
        self.assertEqual(self.lancer(couche=couche), 0)
        produit = self.produit()
        du_jour = recette.courses_du_jour(produit, D0.replace("-", ""))
        self.assertEqual(set(du_jour), {"2", "3"},
                         "les deux types de ligne de la couche doivent rouler le jour simulé")
        self.assertEqual(du_jour["2"], 3)
        self.assertEqual(du_jour["3"], 2)

    def test_course_dont_le_trace_manque_a_la_couche_est_ecartee(self):
        # Un `shape_id` absent de la couche rend `route first_with (...)` nil dans
        # `PublicTransport.gaml` : le véhicule naîtrait sans géométrie.
        couche = couche_depuis_feeds(
            self.feeds, self.racine / "couche.shp",
            garder=lambda sid, rt: not sid.endswith(
                gtfs_traces.empreinte_suite(["R1", "R2"])))
        self.assertEqual(self.lancer(couche=couche), 0)
        traces_couche = set(recette.types_de_la_couche(couche)[0])
        for trip in self.produit()["trip_list"]:
            self.assertIn(trip["shape_id"], traces_couche)
        self.assertNotIn("rail_partiel",
                         {t["trip_id"] for t in self.produit()["trip_list"]})

    def test_desaccord_de_nombre_de_points_fait_echouer(self):
        """Les `shape_segments` sont des indices dans `r.shape.points`.

        Une couche dont un tracé compte moins de points que le feed ferait sortir
        GAMA de la liste des sommets — au mieux une erreur, au pire un véhicule
        immobile.
        """
        import geopandas as gpd
        from shapely.geometry import LineString

        couche = couche_depuis_feeds(self.feeds, self.racine / "couche.shp")
        gdf = gpd.read_file(couche)
        cible = gdf.index[gdf["shape_id"] == "SH1"][0]
        gdf.loc[cible, "geometry"] = LineString(list(gdf.loc[cible, "geometry"].coords)[:3])
        tronquee = self.racine / "couche_tronquee.shp"
        gdf.to_file(tronquee)
        self.assertEqual(self.lancer(couche=tronquee), recette.CODE_REFUS)
        self.assertFalse(self.sortie.exists())


class TestFenetreEtMasqueBinaire(BaseTemporaire):
    """Le calendrier de GAMA est un masque de 64 bits, et il doit contenir la date
    simulée : hors calendrier, `is_trip_available_today` se contente d'un `warn`."""

    def test_date_simulee_hors_fenetre_refusee(self):
        couche = couche_depuis_feeds(self.feeds, self.racine / "couche.shp")
        code = self.lancer(couche=couche, debut="2026-06-01", jours=64)
        self.assertEqual(code, recette.CODE_REFUS)
        self.assertFalse(self.sortie.exists())

    def test_fenetre_plus_large_que_le_masque_refusee(self):
        couche = couche_depuis_feeds(self.feeds, self.racine / "couche.shp")
        self.assertEqual(self.lancer(couche=couche, jours=65), recette.CODE_REFUS)
        self.assertFalse(self.sortie.exists())

    def test_le_calendrier_produit_tient_dans_64_bits(self):
        couche = couche_depuis_feeds(self.feeds, self.racine / "couche.shp")
        self.assertEqual(self.lancer(couche=couche), 0)
        calendrier = self.produit()["calendar"]
        self.assertLessEqual(len(calendrier["dates"]), recette.LIMITE_MASQUE)
        self.assertIn(D0, calendrier["dates"])

    def test_date_simulee_lue_dans_settings_gaml(self):
        """La date ne se recopie pas dans la recette : deux sources divergent, et la
        conséquence d'une divergence est un réseau vide sans message d'erreur."""
        lue = recette.date_simulee_de_settings()
        self.assertIsNotNone(lue, "starting_date doit être lisible dans Settings.gaml")
        self.assertEqual(lue.isoformat(), JOUR_SIMULE)

    def test_settings_illisible_ne_produit_pas_de_date_plausible(self):
        faux = self.racine / "Settings.gaml"
        faux.write_text("global { int x <- 1; }\n", encoding="utf-8")
        self.assertIsNone(recette.date_simulee_de_settings(faux))


class TestFusionDesReseaux(BaseTemporaire):
    def test_service_id_collisionnant_ne_melange_pas_les_calendriers(self):
        """Les feeds TER et liO numérotent tous deux leurs services `SVC_0001` :
        224 collisions mesurées. Fusionnés tels quels, les cars liraient
        l'horaire des trains."""
        # Le bus roule les 16, 17 et 18 ; le rail le seul 17. Même `SVC_0001`.
        self.feeds["rail"] = feed_sans_geometrie(self.racine / "feed_rail_j2",
                                                 dates=(D1,), service="SVC_0001")
        couche = couche_depuis_feeds(self.feeds, self.racine / "couche.shp")
        self.assertEqual(
            self.lancer(couche=couche, date_simulee="2026-03-17", debut=JOUR_SIMULE), 0)
        produit = self.produit()
        self.assertEqual(recette.courses_du_jour(produit, D0), {"3": 2},
                         "aucun train ne roule le 16 : le rail n'a de service que le 17")
        self.assertEqual(recette.courses_du_jour(produit, D1), {"2": 3, "3": 2})
        services = {t["service_id"] for t in produit["trip_list"]}
        self.assertEqual(services, {"bus:SVC_0001", "rail:SVC_0001"})

    def test_les_cles_de_jointure_avec_otp_ne_sont_jamais_renommees(self):
        """`shape_id`, `route_id`, `trip_id` sont les clés de jointure avec les
        itinéraires rendus par OTP (`Inhabitant.gaml` : `shape_id_list contains
        each.shape_id`). Les préfixer ferait monter un agent dans le vide."""
        couche = couche_depuis_feeds(self.feeds, self.racine / "couche.shp")
        self.assertEqual(self.lancer(couche=couche), 0)
        for trip in self.produit()["trip_list"]:
            self.assertFalse(trip["trip_id"].startswith(("bus:", "rail:")))
            self.assertFalse(trip["shape_id"].startswith(("bus:", "rail:")))
            self.assertFalse(trip["route_id"].startswith(("bus:", "rail:")))


class TestReseauSansGeometrie(BaseTemporaire):
    """Le TER ne publie ni `shapes.txt` peuplé ni `trips.shape_id`."""

    def test_shapes_txt_reduit_a_son_entete_n_est_pas_une_geometrie(self):
        self.assertFalse(recette._a_des_geometries(self.feeds["rail"]))
        self.assertTrue(recette._a_des_geometries(self.feeds["bus"]))

    def test_un_trace_par_suite_d_arrets_distincte(self):
        trips = recette._lire_csv(self.feeds["rail"] / "trips.txt")
        suites = gtfs_traces.suites_depuis_stop_times(
            recette._lire_csv(self.feeds["rail"] / "stop_times.txt"))
        traces, course_vers_trace, mesures = gtfs_traces.traces_par_suite_d_arrets(
            trips, suites, journal=lambda *_a, **_k: None)
        self.assertEqual(mesures["courses_tracees"], 3)
        self.assertEqual(len(traces), 3, "trois dessertes distinctes, trois tracés")
        self.assertNotEqual(course_vers_trace["rail_complet"], course_vers_trace["rail_partiel"])

    def test_une_course_partielle_ne_roule_pas_jusqu_au_bout_de_la_ligne(self):
        """`build_trips` force `shape_segments[-1]` au dernier point du tracé.

        Avec un tracé par (ligne, sens), la course R1→R2 hériterait du tracé
        R1→R2→R3→R4 et roulerait jusqu'à R4 dans le temps de parcours de R2 :
        du mouvement fabriqué. Avec un tracé par desserte, son dernier segment
        EST son dernier arrêt.
        """
        couche = couche_depuis_feeds(self.feeds, self.racine / "couche.shp")
        self.assertEqual(self.lancer(couche=couche), 0)
        points = recette.types_de_la_couche(couche)[0]
        partielle = next(t for t in self.produit()["trip_list"]
                         if t["trip_id"] == "rail_partiel")
        self.assertEqual(len(partielle["stop_times"]), 2)
        self.assertEqual(points[partielle["shape_id"]], 2,
                         "le tracé de la course partielle n'a que ses deux arrêts")
        self.assertEqual(partielle["shape_segments"], [1])

    def test_course_sans_direction_id_ne_disparait_pas(self):
        """6 courses TER n'ont aucun `direction_id` ; leur `shape_id` valait `NaN`,
        et le regroupement les écartait sans un mot."""
        couche = couche_depuis_feeds(self.feeds, self.racine / "couche.shp")
        self.assertEqual(self.lancer(couche=couche), 0)
        identifiants = {t["trip_id"] for t in self.produit()["trip_list"]}
        self.assertIn("rail_sans_sens", identifiants)
        shape = next(t["shape_id"] for t in self.produit()["trip_list"]
                     if t["trip_id"] == "rail_sans_sens")
        self.assertIn(f":{gtfs_traces.SENS_ABSENT}:", shape)

    def test_sens_normalise_couvre_les_trois_formes_de_valeur_absente(self):
        for absent in (None, "", "nan", "NaN", "None", float("nan")):
            self.assertEqual(gtfs_traces.sens_normalise(absent), gtfs_traces.SENS_ABSENT)
        self.assertEqual(gtfs_traces.sens_normalise("0"), "0")
        self.assertEqual(gtfs_traces.sens_normalise(1), "1")

    def test_empreinte_du_motif_est_stable_et_distingue_les_dessertes(self):
        self.assertEqual(gtfs_traces.empreinte_suite(["A", "B"]),
                         gtfs_traces.empreinte_suite(["A", "B"]))
        self.assertNotEqual(gtfs_traces.empreinte_suite(["A", "B"]),
                            gtfs_traces.empreinte_suite(["B", "A"]))


class TestRecettesAlignees(BaseTemporaire):
    def test_les_deux_recettes_fabriquent_les_memes_shape_id(self):
        """C'est l'invariant qui empêche le décalage de cinq mois de revenir : la
        couche et les courses passent par le MÊME module pour nommer un tracé."""
        from scripts.data.gama import export_gtfs_layers

        couche_routes, _stops, _comptes = export_gtfs_layers.couches(
            {nom: chemin for nom, chemin in self.feeds.items()},
            journal=lambda *_a, **_k: None)
        couche = couche_depuis_feeds(self.feeds, self.racine / "couche.shp")
        self.assertEqual(self.lancer(couche=couche), 0)
        des_courses = {t["shape_id"] for t in self.produit()["trip_list"]}
        self.assertTrue(des_courses <= set(couche_routes["shape_id"]),
                        "tout tracé porté par une course doit exister dans la couche "
                        "produite par l'autre recette")


if __name__ == "__main__":
    unittest.main()
