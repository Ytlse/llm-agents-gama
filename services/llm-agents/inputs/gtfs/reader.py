from collections import defaultdict
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel
from models import BBox, Location
# from scipy.spatial import KDTree
import zipfile
import os
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
from loguru import logger
from settings import settings
# `table_traces` ne dépend de rien du paquet : l'importer ici ne referme pas de
# cycle, même si `inputs/gtfs/__init__.py` est en train d'importer CE fichier.
from inputs.gtfs import table_traces


STRING_COLUMNS = [
    'route_id', 'service_id', 'trip_id', 'shape_id', 'stop_id', 'date',
]


class Stop(BaseModel):
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float


def _correct_color_hex_string(value):
    value = str(value)
    if value == 'nan':
        return "#222222"
    if value.startswith('#'):
        return value
    if len(value) == 6:
        return '#' + value
    if len(value) == 3:
        return '#' + ''.join([c * 2 for c in value])
    return value

def _lire_table_gtfs(feed: "Path", nom: str):
    """Lit une table d'un feed GTFS, que le feed soit un répertoire ou un zip.

    Rend `None` si la table n'existe pas : un feed sans `routes.txt` n'est pas une erreur,
    c'est un feed qui n'a rien à dire sur les lignes.
    """
    if feed.is_dir():
        chemin = feed / nom
        return pd.read_csv(chemin, dtype=str) if chemin.exists() else None
    if feed.suffix == ".zip":
        with zipfile.ZipFile(feed) as archive:
            if nom not in archive.namelist():
                return None
            with archive.open(nom) as f:
                return pd.read_csv(f, dtype=str)
    return None


class GTFSData:
    # D'où vient la table des tracés :
    #   "annexe" — le fichier publié par la recette (le cas du runtime) ;
    #   "feed"   — recalculée depuis les tables chargées, sans lire le fichier annexe.
    #              C'est le mode de la RECETTE elle-même : c'est elle qui produit le
    #              fichier, elle ne peut pas le lire pour l'écrire.
    SOURCE_ANNEXE = "annexe"
    SOURCE_FEED = "feed"

    def __init__(self, **kwargs):
        self.stop_times = kwargs["stop_times"]
        self.stops = kwargs["stops"]
        self.routes = kwargs["routes"]
        self.trips = kwargs["trips"]
        self.shapes = kwargs["shapes"]
        self.calendar_dates = kwargs["calendar_dates"]
        self.calendar = kwargs["calendar"]
        self._source_demandee = kwargs.get("table_traces", self.SOURCE_ANNEXE)

        # Init lookup maps
        self.init_route_lookup_maps()
        self.init_shape_lookup_maps()

        # init the KDTree for the stops
        # TODO: remove these lines, this is used for python RAPTOR implementation
        # which is deprecated
        # if kwargs.get("index_stop_area") is not True:
        #     self.indexed_stops_df = self.stops[self.stops['location_type'] != 1]
        # else:
        #     self.indexed_stops_df = self.stops.copy()
        # points = self.indexed_stops_df[['stop_lon', 'stop_lat']].values
        # points = points.astype(float)
        # self.stop_kdtree = KDTree(points)

    def init_route_lookup_maps(self):
        self.route_name_id_map = {
            str(row['route_short_name']): str(row['route_id'])
            for _, row in self.routes.iterrows()
        }

        self.route_id_map = {
            str(row['route_id']): {
                "route_short_name": str(row['route_short_name']),
                "route_long_name": str(row['route_long_name']),
                "route_type": settings.gtfs.gtfs_modality_name_map.get(str(row['route_type']), "Unknown"),
            }
            for _, row in self.routes.iterrows()
        }
        return self._joindre_catalogues_des_autres_feeds()

    def _joindre_catalogues_des_autres_feeds(self) -> dict:
        """Ajoute au dictionnaire des lignes le catalogue des AUTRES feeds en service.

        Le lecteur ne charge qu'un feed (`settings.gtfs.gtfs_file`, Tisséo), alors que le
        graphe OTP en porte trois depuis le 2026-09-04 : Tisséo, le TER et le car régional
        liO. Un identifiant de ligne liO ou TER ne se trouvait donc dans aucune table, et le
        prompt de l'agent lisait « Trajet en **Unknown 392** » pour les 319 lignes des deux
        réseaux régionaux — le mode ET le numéro perdus, alors que la table des modes connaît
        le train (`route_type` 2) et le bus (3) depuis le même jour.

        Seul le CATALOGUE DES LIGNES est joint, pas les horaires ni les arrêts : c'est tout ce
        dont le prompt a besoin, et les tables lourdes du feed primaire restent intactes.

        La jointure se fait par `route_id`, mesuré **sans collision** entre les trois feeds ;
        les noms courts, eux, collisionnent (une ligne « 1 » existe partout), d'où deux
        dictionnaires traités différemment : par identifiant on complète, par nom court on
        garde le feed primaire et on compte. Une collision d'identifiant, elle, est une
        ambiguïté réelle : elle s'alarme.
        """
        from trip_helper.otp import feeds_en_service

        primaire = Path(settings.gtfs.gtfs_file)
        journal = {"feeds": {}, "lignes_ajoutees": 0,
                   "collisions_identifiant": 0, "collisions_nom_court": 0}
        for feed in feeds_en_service(str(primaire)):
            if feed.resolve() == primaire.resolve():
                continue
            try:
                routes = _lire_table_gtfs(feed, "routes.txt")
            except (OSError, ValueError, KeyError) as exc:
                logger.error(f"[ALARME] catalogue de lignes illisible dans {feed.name} : "
                             f"{exc} — les lignes de ce réseau resteront « Unknown » dans le prompt")
                continue
            if routes is None:
                continue
            ajoutees = 0
            for _, row in routes.iterrows():
                rid = str(row['route_id'])
                if rid in self.route_id_map:
                    journal["collisions_identifiant"] += 1
                    continue
                self.route_id_map[rid] = {
                    "route_short_name": str(row.get('route_short_name', '')),
                    "route_long_name": str(row.get('route_long_name', '')),
                    "route_type": settings.gtfs.gtfs_modality_name_map.get(
                        str(row.get('route_type', '')), "Unknown"),
                }
                nom = str(row.get('route_short_name', ''))
                if nom in self.route_name_id_map:
                    journal["collisions_nom_court"] += 1
                else:
                    self.route_name_id_map[nom] = rid
                ajoutees += 1
            journal["feeds"][feed.name] = ajoutees
            journal["lignes_ajoutees"] += ajoutees

        if journal["collisions_identifiant"]:
            logger.error(
                f"[ALARME] {journal['collisions_identifiant']} identifiant(s) de ligne "
                f"revendiqué(s) par deux feeds GTFS : le catalogue du feed primaire est "
                f"conservé, l'autre ignoré. Le mode et le numéro affichés dans le prompt "
                f"peuvent désigner la mauvaise ligne."
            )
        # Le succès se journalise aussi : sans cette ligne, on ne distingue pas « les trois
        # réseaux sont là » de « le lecteur n'a rien trouvé à joindre ».
        logger.info(
            f"[GTFS] catalogue des lignes : {len(self.route_id_map)} ligne(s) au total, dont "
            f"{journal['lignes_ajoutees']} venue(s) des autres feeds en service "
            f"({journal['feeds'] or 'aucun'}) ; {journal['collisions_nom_court']} nom(s) court(s) "
            f"déjà pris, gardés au feed primaire"
        )
        return journal

    def init_shape_lookup_maps(self):
        """Charge la table des tracés — le fichier publié par la recette d'abord.

        C'est cette table que `get_shape_id_from_route_info` interroge pour poser
        un `shape_id` sur la jambe d'un itinéraire, et c'est ce `shape_id` que
        `Inhabitant.gaml` compare à celui du véhicule pour faire MONTER l'agent.

        Construite depuis le seul feed primaire — ce qu'elle a été jusqu'au
        2026-09-04 — elle ignorait 80 des 199 lignes portant des courses (17 TER,
        58 cars liO, 5 lignes circulaires) : `get_shape_id_from_route_info`
        rendait `[]`, indistinguable d'« aucun tracé pour ce couple d'arrêts ».
        Voir `inputs/gtfs/table_traces.py` pour le pourquoi du fichier annexe.

        Le repli sur le feed primaire subsiste — sans lui, un fichier annexe
        manquant priverait la simulation de TOUT transport en commun — mais il
        est **annoncé en [ALARME]**, la table est marquée partielle, et chaque
        ligne qu'elle ne sait pas désigner s'alarme à son tour (front montant).
        Le silence était le défaut ; le repli muet en aurait été un autre.
        """
        # Compteurs des alarmes de désignation (voir `_alarme_ligne_indesignable`).
        self._lignes_indesignables: set = set()
        self._appels_sans_trace = 0
        self._appels_sans_arret = 0

        if self._source_demandee == self.SOURCE_FEED:
            self.route_id_shape_lookup_map = self._table_traces_depuis_le_feed()
            self.arrets_hors_feed_primaire = {}
            self.source_table_traces = self.SOURCE_FEED
            self.table_traces_partielle = False
            self.journal_table_traces = {"source": self.SOURCE_FEED}
            logger.info(
                f"[GTFS] table des tracés recalculée depuis les tables chargées "
                f"(mode recette) : {len(self.route_id_shape_lookup_map)} route_id, "
                f"{sum(len(v) for v in self.route_id_shape_lookup_map.values())} tracé(s)")
            return

        chemin = Path(settings.gtfs.shape_lookup_file)
        try:
            table, arrets, journal = table_traces.charger(chemin)
        except table_traces.TableTracesInvalide as exc:
            self.route_id_shape_lookup_map = self._table_traces_depuis_le_feed()
            self.arrets_hors_feed_primaire = {}
            self.source_table_traces = f"feed_primaire:{exc.motif}"
            self.table_traces_partielle = True
            self.journal_table_traces = {"source": self.source_table_traces,
                                         "motif": exc.motif, "detail": exc.detail}
            logger.error(
                f"[ALARME] table des tracés inutilisable ({exc.motif}) : {exc.detail}. "
                f"Repli sur le SEUL feed primaire ({settings.gtfs.gtfs_file}) : "
                f"{len(self.route_id_shape_lookup_map)} route_id désignables. Les lignes "
                f"des autres réseaux (TER, cars liO) rouleront dans GAMA sans qu'aucun "
                f"agent puisse y monter."
            )
            return

        self.route_id_shape_lookup_map = table
        self.arrets_hors_feed_primaire = arrets
        self.source_table_traces = self.SOURCE_ANNEXE
        self.table_traces_partielle = False
        self.journal_table_traces = {"source": self.SOURCE_ANNEXE, **journal}
        # Le succès se journalise explicitement : sans cette ligne, on ne distingue
        # pas « la table des trois réseaux est en place » de « le runtime n'a rien lu ».
        logger.info(
            f"[GTFS] table des tracés lue dans {chemin} (générée le "
            f"{journal.get('genere_le')} par {journal.get('recette')}) : "
            f"{journal['comptes']['route_id']} route_id, {journal['comptes']['traces']} "
            f"tracé(s), {journal['arrets_catalogue']} arrêt(s) au catalogue ; "
            f"réseaux {journal.get('reseaux') or 'non détaillés'} ; fraîcheur vérifiée "
            f"sur {', '.join(journal['temoins'])}"
        )

    def _table_traces_depuis_le_feed(self) -> dict:
        """`route_id → {shape_id → {stop_id: stop_sequence}}` depuis les tables chargées.

        Le calcul historique, désormais réservé à deux usages : la RECETTE, qui
        s'en sert pour produire le fichier annexe depuis le feed fusionné des
        trois réseaux, et le repli alarmé quand ce fichier manque.
        """
        stops = self.trips.groupby('shape_id').agg({
            'route_id': 'first',
            'trip_id': 'first',
        }).reset_index()\
        .merge(
            self.stop_times[['trip_id', 'stop_sequence', 'stop_id']],
            on='trip_id',
            how='left',
        ).merge(
            self.stops[['stop_id', 'stop_name']],
            on='stop_id',
            how='left',
        )

        m = defaultdict(dict)
        for _, row in stops.iterrows():
            if row['shape_id'] not in m[row['route_id']]:
                m[row['route_id']][row['shape_id']] = {}
            m[row['route_id']][row['shape_id']][row['stop_id']] = row['stop_sequence']
        return m

    def table_traces_serialisable(self) -> tuple[dict, dict]:
        """La table et le catalogue d'arrêts, en types JSON — pour la recette.

        `stop_sequence` arrive de pandas en `int64`, que `json` refuse ; les
        `shape_id` d'un feed sans géométrie sont déjà des chaînes. La conversion
        est faite ici, au plus près du calcul, et non dans la recette : c'est la
        même table qui sert au runtime.
        """
        table = {
            str(route_id): {
                str(shape_id): {str(stop_id): int(rang) for stop_id, rang in stops.items()}
                for shape_id, stops in par_trace.items()
            }
            for route_id, par_trace in self.route_id_shape_lookup_map.items()
        }
        arrets_utiles = {stop_id for par_trace in table.values()
                         for stops in par_trace.values() for stop_id in stops}
        arrets = {}
        for _, row in self.stops.iterrows():
            stop_id = str(row['stop_id'])
            if stop_id not in arrets_utiles:
                continue
            arrets[stop_id] = {"stop_name": str(row['stop_name']),
                               "stop_lat": float(row['stop_lat']),
                               "stop_lon": float(row['stop_lon'])}
        return table, arrets

    def load_world_bounding_box(self) -> BBox:
        min_lon, min_lat, max_lon, max_lat = self.get_bounding_box()
        buffer = 0.05  # degrees ~ 5km
        return BBox(
            min_lon=min_lon - buffer,
            min_lat=min_lat - buffer,
            max_lon=max_lon + buffer,
            max_lat=max_lat + buffer,
        )

    def get_shape_id_from_route_info(self, route_id: str, from_stop_id: Optional[str], to_stop_id: Optional[str]) -> list[str]:
        """Les `shape_id` de la ligne `route_id` qui desservent les deux arrêts dans l'ordre.

        Une liste vide veut dire « aucun véhicule de cette ligne ne peut être
        désigné » : `Inhabitant.gaml` ne trouvera personne à faire monter. Deux
        causes se confondaient dans ce silence — un couple d'arrêts qui n'existe
        sur aucun tracé (normal), et une ligne que la table ne connaît pas du
        tout (le défaut). La seconde s'alarme désormais, sur front montant :
        une fois par `route_id`, pour dire la ligne sans noyer le journal.
        """
        if not from_stop_id or not to_stop_id:
            self._appels_sans_arret += 1
            self._alarme_ligne_indesignable(
                route_id, "arret non resolu",
                f"jambe sans identifiant d'arrêt (de={from_stop_id!r}, vers={to_stop_id!r}) : "
                f"l'arrêt rendu par OTP n'a pas été retrouvé dans les tables GTFS")
            return []
        if route_id not in self.route_id_shape_lookup_map:
            self._appels_sans_trace += 1
            self._alarme_ligne_indesignable(
                route_id, "ligne absente de la table",
                f"aucun tracé connu pour cette ligne ; la table vient de "
                f"{self.source_table_traces} et porte "
                f"{len(self.route_id_shape_lookup_map)} route_id")
            return []

        results = []
        for shape_id, stops in self.route_id_shape_lookup_map[route_id].items():
            if from_stop_id not in stops or to_stop_id not in stops:
                continue
            if stops[from_stop_id] < stops[to_stop_id]:
                results.append(shape_id)
        return results

    def _alarme_ligne_indesignable(self, route_id: str, motif: str, detail: str) -> None:
        """[ALARME] sur front montant : une fois par ligne, pas une fois par itinéraire.

        Un agent peut demander des dizaines d'itinéraires sur la même ligne ; la
        cause, elle, est unique. On alarme donc à la PREMIÈRE occurrence de
        chaque `route_id` et on compte les suivantes, que le rapport de fin de
        run relève (`resume_table_traces`).
        """
        cle = (route_id, motif)
        if cle in self._lignes_indesignables:
            return
        self._lignes_indesignables.add(cle)
        nom = self.get_route_short_name_by_id(route_id)
        mode = self.get_route_type_string_by_id(route_id)
        logger.error(
            f"[ALARME] itinéraire indésignable — ligne {route_id} ({mode} {nom}) : {motif}. "
            f"{detail}. Aucun agent ne pourra monter dans un véhicule de cette ligne : "
            f"le véhicule roule dans GAMA, l'itinéraire ne le nomme pas."
        )

    def resume_table_traces(self) -> dict:
        """De quoi reconstituer après coup ce que la table a su et n'a pas su désigner."""
        return {
            "source": getattr(self, "source_table_traces", "inconnue"),
            "partielle": getattr(self, "table_traces_partielle", None),
            "route_id_connus": len(self.route_id_shape_lookup_map),
            "lignes_indesignables": sorted({rid for rid, _ in self._lignes_indesignables}),
            "appels_ligne_absente": self._appels_sans_trace,
            "appels_arret_non_resolu": self._appels_sans_arret,
            "journal": getattr(self, "journal_table_traces", {}),
        }

    def resoudre_route_id(self, identifiant_otp: str) -> str:
        """L'identifiant de ligne d'OTP ramené à celui du GTFS, par le CATALOGUE.

        OTP préfixe ses identifiants du nom du feed : `tisseo:line:8`,
        `ter:FR:Line::68c586ae-…`, `lio:305`. `parse_gtfs_entity_id` retire
        « le premier segment quand il y a au moins deux `:` » — une règle qui
        marche pour les deux premiers et **échoue pour le troisième** : le
        `route_id` d'un car liO ne contient aucun `:`, donc `lio:305` traverse
        intact et ne correspond à rien. Mesuré le 2026-09-04 sur un itinéraire
        rendu par l'OTP en service : `transit_route='lio:305'` là où la ligne
        s'appelle `305` dans le GTFS, dans `trip_info.json` et donc dans
        `ROUTE_VEHICLE_MAP` — l'agent ne pouvait ni désigner le tracé ni trouver
        le véhicule.

        On ne devine donc plus la forme de l'identifiant : on essaie le brut,
        puis on retire les préfixes un par un, et on garde le premier candidat
        que le CATALOGUE DES LIGNES connaît (les trois feeds y sont depuis le
        2026-09-04). Aucun candidat reconnu : on rend le brut débarrassé de son
        premier segment — l'ancien comportement — et l'appel suivant alarmera.
        """
        candidats = [identifiant_otp]
        reste = identifiant_otp
        while ":" in reste:
            reste = reste.split(":", 1)[1]
            candidats.append(reste)
        for candidat in candidats:
            if candidat in self.route_id_map:
                return candidat
        return candidats[1] if len(candidats) > 1 else identifiant_otp

    def get_route_id_by_name(self, route_name: str) -> str:
        # Get the route id by route name
        if route_name in self.route_name_id_map:
            return self.route_name_id_map[route_name]
        raise ValueError(f"Route {route_name} not found")
    
    def get_route_type_string_by_id(self, route_id: str) -> str:
        return self.route_id_map.get(route_id, {}).get("route_type", "Unknown")
    
    def get_route_long_name_by_id(self, route_id: str) -> str:
        return self.route_id_map.get(route_id, {}).get("route_long_name", "Unknown")
    
    def get_route_short_name_by_id(self, route_id: str) -> str:
        return self.route_id_map.get(route_id, {}).get("route_short_name", "Unknown")

    def get_bounding_box(self) -> tuple[float, float, float, float]:
        # Get the bounding box of the stops
        min_lon = self.stops['stop_lon'].min()
        max_lon = self.stops['stop_lon'].max()
        min_lat = self.stops['stop_lat'].min()
        max_lat = self.stops['stop_lat'].max()
        return min_lon, min_lat, max_lon, max_lat

    # def get_nearest_stops(self, lon, lat, stops_count=5) -> tuple[list[Stop], list[float]]:
    #     # Find the nearest stops using KDTree
    #     distances, indices = self.stop_kdtree.query([lon, lat], k=stops_count)
    #     nearest_stops = self.indexed_stops_df.iloc[indices]
    #     stops = [Stop.model_validate(row) for row in nearest_stops.to_dict(orient="records")]
    #     return stops, distances
    
    def get_stop_id_by_name(self, stop_name: str) -> Optional[str]:
        match = self.stops[self.stops['stop_name'] == stop_name]
        if match.empty:
            return None
        return str(match.iloc[0]['stop_id'])

    def get_stop(self, stop_id: str) -> Stop:
        """L'arrêt, cherché dans le feed primaire PUIS dans le catalogue annexe.

        Le catalogue annexe porte les arrêts des trois réseaux servis par les
        tracés publiés (gares TER, points d'arrêt des cars liO). Sans lui,
        `_resolve_gtfs_stop` (`trip_helper/otp.py`) ne retrouvait pas la gare
        rendue par OTP, la jambe partait avec `stop_id=None`, et
        `get_shape_id_from_route_info` rendait `[]` avant même de consulter la
        table : le second maillon de la chaîne qui empêchait de monter dans un
        train.

        ⚠ Ce catalogue est tenu à l'ÉCART de `self.stops`, exprès :
        `get_bounding_box` en déduit l'emprise du monde de la simulation
        (`urban_mobility_agents/factory/factory.py`), et y verser des gares de
        toute l'Occitanie l'étendrait bien au-delà du périmètre d'enquête.
        """
        stop = self.stops[self.stops['stop_id'] == stop_id]
        if stop.empty:
            annexe = getattr(self, "arrets_hors_feed_primaire", {}).get(stop_id)
            if annexe is not None:
                return Stop(stop_id=stop_id, stop_name=annexe["stop_name"],
                            stop_lat=annexe["stop_lat"], stop_lon=annexe["stop_lon"])
            raise ValueError(f"Stop {stop_id} not found")
        stop = stop.iloc[0]
        return Stop.model_validate(stop.to_dict())
    
    def all_stop_locations(self) -> list[Location]:
        # Get all stop locations
        return [
            Location(lon=row['stop_lon'], lat=row['stop_lat'])
            for _, row in self.stops.iterrows()
        ]

    @classmethod
    def _read_gtfs_file_as_pd(cls, file):
        df = pd.read_csv(file, dtype={col: str for col in STRING_COLUMNS}, low_memory=False)
        return df

    @classmethod
    def read_df_from_zip(cls, zip_path, file_name):
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            if file_name in zip_ref.namelist():
                with zip_ref.open(file_name) as file:
                    df = cls._read_gtfs_file_as_pd(file)
                    return df
            else:
                raise ValueError(f"File {file_name} not found in {zip_path}")
            
    @classmethod
    def read_file(cls, dir, file_name):
        if not os.path.exists(dir):
            raise ValueError(f"Dir {dir} not found")
        
        if os.path.isdir(dir):
            with open(os.path.join(dir, file_name), 'r') as file:
                return cls._read_gtfs_file_as_pd(file)
        if os.path.isfile(dir) and dir.endswith('.zip'):
            return cls.read_df_from_zip(dir, file_name)
        
        raise ValueError(f"Dir {dir} is not a directory or a zip file")

    @classmethod
    def from_gtfs_files(cls, dir, table_traces=SOURCE_ANNEXE):
        """Charge un feed GTFS depuis un répertoire ou un zip.

        `table_traces="feed"` recalcule la table des tracés depuis les tables
        chargées au lieu de lire le fichier annexe : c'est le mode de la recette
        `scripts/data/gama/export_trip_info.py`, qui lit le feed FUSIONNÉ des
        trois réseaux pour produire ce fichier — elle ne peut pas le lire pour
        l'écrire, et la table qu'elle publie doit venir du feed qu'elle a
        réellement fusionné.
        """
        data = GTFSData(**{
            'table_traces': table_traces,
            # 'agency': read_file(dir, 'agency.txt'),
            'stops': cls.read_file(dir, 'stops.txt'),
            'shapes': cls.read_file(dir, 'shapes.txt'),
            'trips': cls.read_file(dir, 'trips.txt'),
            'stop_times': cls.read_file(dir, 'stop_times.txt'),
            'routes': cls.read_file(dir, 'routes.txt'),
            # TODO: support calendar.txt
            # for now, we pretend that all services are available, and calendar.txt file is empty
            'calendar_dates': cls.read_file(dir, 'calendar_dates.txt'),
            'calendar': cls.read_file(dir, 'calendar.txt'),
        })
        assert len(data.calendar) == 0, "calendar.txt is not supported yet"
        assert data.calendar_dates['exception_type'].unique().tolist() == [1], "calendar_dates.txt only supports exception_type = 1"

        return data
    
    @classmethod
    def DEFAULT(cls):
        # Get the GTFS data from the settings
        if not hasattr(cls, "_instance"):
            cls._instance = GTFSData.from_gtfs_files(settings.gtfs.gtfs_file)
        return cls._instance

    def to_stops_shape_file(self, output_path, crs=4326):
        stops_df = self.stops.copy()        
        routes_df = self.routes[['route_id', 'route_type']]
        trips_df = self.trips[['route_id', 'trip_id']]
        stop_times_df = self.stop_times[['stop_id', 'trip_id']]

        route_type_df = trips_df.merge(routes_df, on='route_id', how='left')
        stop_times_df = stop_times_df.merge(route_type_df, on='trip_id', how='left')
        stop_times_df = stop_times_df.groupby('stop_id').agg({'route_type': 'min'}).reset_index()

        stops_df = stops_df[['stop_id', 'stop_name', 'location_type', 'wheelchair_boarding', 'stop_lon', 'stop_lat']]
        stops_df = stops_df.merge(stop_times_df[['stop_id', 'route_type']], on='stop_id', how='left')
        # stops_df['route_type'] = stops_df['route_type'].fillna(-1).astype(float)
        stops_df.dropna(subset=['route_type'], inplace=True)
        gdf = gpd.GeoDataFrame(
            stops_df, geometry=gpd.points_from_xy(stops_df['stop_lon'], stops_df['stop_lat'], z=0)
        )
        gdf.set_crs(epsg=crs, inplace=True)

        gdf.drop(columns=['stop_lon', 'stop_lat'], inplace=True)

        # Save as Shapefile
        gdf.to_file(os.path.join(output_path, 'stops.shp'))
        gdf.to_file(os.path.join(output_path, 'stops.geojson'), driver='GeoJSON')

    def to_route_shape_file(self, output_path, crs=4326):
        shapes_df = self.shapes
        routes_df = self.routes
        trips_df = self.trips

        shapes_list = shapes_df.groupby("shape_id").apply(
            lambda l: LineString(zip(l['shape_pt_lon'], l['shape_pt_lat']))
        )
        shapes_all = pd.DataFrame({
            'shape_id': shapes_list.index,
            'geometry': shapes_list.values
        })
        
        trips_df = trips_df[['route_id', 'service_id', 'trip_id', 'shape_id']].groupby("shape_id").agg(lambda x: x.iloc[0])
        shapes_all = shapes_all.merge(trips_df, on='shape_id', how='left')
        shapes_all = shapes_all.merge(routes_df, on='route_id', how='left')

        # compact the column names
        shapes_all.rename(columns={
            'shape_id': 'shape_id',
            'route_id': 'route_id',
            'service_id': 'service_id',
            'trip_id': 'trip_id',
            'route_short_name': 'short_name',
            'route_long_name': 'long_name',
            'route_color': 'color',
            'route_text_color': 'text_color',
            'route_type': 'route_type',
        }, inplace=True)

        # correct the color hex string
        shapes_all['color'] = shapes_all['color'].apply(_correct_color_hex_string)
        shapes_all['text_color'] = shapes_all['text_color'].apply(_correct_color_hex_string)

        gdf = gpd.GeoDataFrame(shapes_all)
        gdf.set_crs(epsg=crs, inplace=True)

        # Save as Shapefile
        gdf.to_file(os.path.join(output_path, 'routes.shp'))
        gdf.to_file(os.path.join(output_path, 'routes.geojson'), driver='GeoJSON')


if __name__ == '__main__':
    gtfs = GTFSData.from_gtfs_files("../data/gtfs/tisseo_gtfs/")

    output_dir = "../data/exports/gtfs/"
    os.makedirs(output_dir, exist_ok=True)
    gtfs.to_stops_shape_file(output_dir)
    gtfs.to_route_shape_file(output_dir)
