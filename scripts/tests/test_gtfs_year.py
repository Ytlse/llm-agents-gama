"""
Tests unitaires du pipeline de construction du feed GTFS annuel
(`scripts/data/gtfs_year/`).

Chaque test porte sur une décision qui, prise à l'envers, produit un feed
plausible mais faux — le mode de défaillance qui a motivé ce pipeline. Les
régressions visées sont nommées explicitement :

Fenêtre fiable (offre.py)
  - la queue tronquée d'un export est coupée
  - un creux isolé (jour férié) est CONSERVÉ : couper au premier creux amputait
    l'export de mars de six journées valides
  - un export réduit à presque rien est déclaré inutilisable, et sa propre queue
    ne contamine pas la référence qui sert à la détecter
  - deux courses de contenu identique le MÊME jour lèvent une alarme au lieu
    d'être confondues (l'offre de la journée serait amputée)

Autorité et donneurs (donneurs.py)
  - une date couverte par deux exports ne prend son offre que dans un seul
  - l'écart saisonnier est cyclique : le 31/12 est à un jour du 01/01
  - un férié cherche un autre férié avant de se rabattre sur un dimanche
  - une classe de période sans donnée bascule sur sa chaîne de repli, en
    confiance basse
  - une date déclarée sans service reste vide, et la déclaration se reconduit
    d'une année sur l'autre

Assemblage (assemblage.py)
  - PAS DE SUR-OFFRE sur recouvrement : le feed sert les courses de l'export
    autoritaire, jamais leur union (le défaut du feed en service : 13 250
    courses le 08/04/2026 contre 12 652 et 12 660 dans ses sources)
  - deux exports décrivant la même course la partagent
  - un `trip_id` recyclé pour une course différente est forké, pas arbitré
  - une géométrie divergente est DUPLIQUÉE, jamais fusionnée point par point
    (le tracé chimère de la shape 14846)
  - une journée extrapolée est la copie exacte de sa donneuse
  - `calendar.txt` reste vide et `exception_type` valant 1 — le contrat de
    `llm-agents/inputs/gtfs/reader.py`
  - fermeture référentielle, stations parentes comprises

Validation (validation.py)
  - l'empreinte d'offre ignore les identifiants et voit une course manquante
  - V2 démasque une sur-offre injectée
  - V6 démasque un tracé chimère

Fenêtrage (window_feed.py)
  - au-delà de 64 dates, refus : c'est la limite du masque binaire de GAMA
  - la fenêtre est référentiellement fermée

Aucun accès réseau : les deux APIs de calendrier sont remplacées par des
doubles. Tous les feeds sont synthétiques et écrits dans un répertoire
temporaire.
"""

from __future__ import annotations

import csv
import datetime as dt
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from scripts.data.gtfs_year import (  # noqa: E402
    assemblage,
    calendar_fr,
    donneurs,
    gtfs_io,
    offre,
    validation,
    window_feed,
)
from scripts.data.gtfs_year.gtfs_io import Export  # noqa: E402

CONFIG = yaml.safe_load(
    (REPO_ROOT / "scripts" / "data" / "gtfs_year" / "feed_year.yaml").read_text(encoding="utf-8")
)

MUET = lambda *_a, **_k: None  # noqa: E731


# ──────────────────────────────────────────────────────────────────────────────
# Fabrique de feeds synthétiques
# ──────────────────────────────────────────────────────────────────────────────


def ecrire_feed(
    dossier: Path,
    *,
    lignes: list[str],
    arrets: list[tuple],
    courses: list[dict],
    calendrier: dict[str, list[str]],
    geometries: dict[str, list[tuple]] | None = None,
    agency_id: str = "network:1",
    correspondances: list[tuple[str, str]] | None = None,
    calendrier_hebdo: list[dict] | None = None,
    retraits: list[tuple[str, str]] | None = None,
) -> Path:
    """Écrit un jeu GTFS minimal mais conforme.

    `courses` : {id, ligne, service, sens, girouette, geometrie, horaires}
    où `horaires` est une suite de (stop_id, arrivee, depart, distance).
    `arrets` : (stop_id, lat, lon, parent_station|"").
    `calendrier_hebdo` : lignes de `calendar.txt` (forme liO), chacune
    {service_id, monday…sunday, start_date, end_date}.
    `retraits` : (service_id, date) écrits en `exception_type=2`.
    """
    dossier.mkdir(parents=True, exist_ok=True)

    def table(nom, colonnes, rangs):
        with open(dossier / nom, "w", encoding="utf-8", newline="") as fichier:
            writer = csv.DictWriter(fichier, fieldnames=colonnes, lineterminator="\n")
            writer.writeheader()
            for rang in rangs:
                writer.writerow(rang)

    table("agency.txt", ["agency_id", "agency_name", "agency_timezone"],
          [{"agency_id": agency_id, "agency_name": "Test", "agency_timezone": "Europe/Paris"}])
    table("calendar.txt",
          ["service_id", "monday", "tuesday", "wednesday", "thursday", "friday",
           "saturday", "sunday", "start_date", "end_date"], calendrier_hebdo or [])
    table("routes.txt", ["route_id", "agency_id", "route_short_name", "route_type"],
          [{"route_id": r, "agency_id": agency_id, "route_short_name": r, "route_type": "3"}
           for r in lignes])
    table("stops.txt", ["stop_id", "stop_name", "stop_lat", "stop_lon", "location_type", "parent_station"],
          [{"stop_id": a[0], "stop_name": a[0], "stop_lat": f"{a[1]:.6f}", "stop_lon": f"{a[2]:.6f}",
            "location_type": "0", "parent_station": a[3] if len(a) > 3 else ""}
           for a in arrets])
    table("trips.txt", ["route_id", "service_id", "trip_id", "trip_headsign", "direction_id", "shape_id"],
          [{"route_id": c["ligne"], "service_id": c["service"], "trip_id": c["id"],
            "trip_headsign": c.get("girouette", "dest"), "direction_id": c.get("sens", "0"),
            "shape_id": c.get("geometrie", "")}
           for c in courses])
    table("stop_times.txt",
          ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence",
           "pickup_type", "drop_off_type", "stop_headsign", "shape_dist_traveled"],
          [{"trip_id": c["id"], "arrival_time": h[1], "departure_time": h[2], "stop_id": h[0],
            "stop_sequence": str(i + 1), "pickup_type": "0", "drop_off_type": "0",
            "stop_headsign": "", "shape_dist_traveled": f"{h[3]:.1f}"}
           for c in courses for i, h in enumerate(c["horaires"])])
    table("calendar_dates.txt", ["service_id", "date", "exception_type"],
          [{"service_id": s, "date": d, "exception_type": "1"}
           for s, dates in calendrier.items() for d in dates]
          + [{"service_id": s, "date": d, "exception_type": "2"} for s, d in (retraits or [])])
    table("shapes.txt",
          ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence", "shape_dist_traveled"],
          [{"shape_id": sid, "shape_pt_lat": f"{p[0]:.6f}", "shape_pt_lon": f"{p[1]:.6f}",
            "shape_pt_sequence": str(i + 1), "shape_dist_traveled": f"{p[2]:.1f}"}
           for sid, points in (geometries or {}).items() for i, p in enumerate(points)])
    table("transfers.txt", ["from_stop_id", "to_stop_id", "transfer_type"],
          [{"from_stop_id": a, "to_stop_id": b, "transfer_type": "2"}
           for a, b in (correspondances or [])])
    return dossier


def course(id_, *, ligne="L1", service="S", geometrie="SH1", girouette="dest",
           depart="08:00:00", arrivee="08:10:00", arrets=("A", "B")) -> dict:
    return {
        "id": id_, "ligne": ligne, "service": service, "geometrie": geometrie,
        "girouette": girouette,
        "horaires": [(arrets[0], depart, depart, 0.0), (arrets[1], arrivee, arrivee, 1000.0)],
    }


GEOM = {"SH1": [(43.600000, 1.440000, 0.0), (43.610000, 1.450000, 1000.0)]}
ARRETS = [("A", 43.600000, 1.440000), ("B", 43.610000, 1.450000)]


def export_de(dossier: Path) -> Export:
    return Export(chemin=dossier, etiquette=dossier.name, empreinte="md5-" + dossier.name)


class BaseTemporaire(unittest.TestCase):
    def setUp(self) -> None:
        self.racine = Path(tempfile.mkdtemp(prefix="gtfs_year_"))
        self.addCleanup(shutil.rmtree, self.racine, ignore_errors=True)


# ──────────────────────────────────────────────────────────────────────────────
# Fenêtre fiable
# ──────────────────────────────────────────────────────────────────────────────


class TestFenetreFiable(BaseTemporaire):
    """La queue tronquée doit tomber, le creux d'un férié doit rester."""

    def _export(self, offre_par_date: dict[str, int]) -> offre.IndexExport:
        """Un export où chaque date active `n` lignes distinctes."""
        lignes = [f"L{i}" for i in range(1, 1 + max(offre_par_date.values()))]
        courses, calendrier = [], {}
        for date, nb in offre_par_date.items():
            service = f"SVC_{date}"
            calendrier[service] = [date]
            for i in range(nb):
                courses.append(course(f"T_{date}_{i}", ligne=lignes[i], service=service,
                                      depart=f"{6 + i // 6:02d}:{(i % 6) * 10:02d}:00"))
        dossier = ecrire_feed(
            self.racine / f"exp_{len(list(self.racine.iterdir()))}",
            lignes=lignes, arrets=ARRETS, courses=courses,
            calendrier=calendrier, geometries=GEOM,
        )
        return offre.indexer(export_de(dossier), MUET)

    @staticmethod
    def _semaines(depart: str, profil: list[int]) -> dict[str, int]:
        premier = calendar_fr.to_date(depart)
        return {
            (premier + dt.timedelta(days=i)).strftime("%Y%m%d"): nb
            for i, nb in enumerate(profil)
        }

    def test_queue_tronquee_coupee(self):
        # 21 jours pleins (le profil de référence), puis 7 jours à 2 lignes.
        profil = [20] * 21 + [2] * 7
        index = self._export(self._semaines("20260302", profil))
        retenues = offre.fenetre_fiable(index, CONFIG["fiabilite"], MUET)
        self.assertEqual(len(retenues), 21)
        self.assertEqual(retenues[-1], "20260322")

    def test_creux_isole_conserve(self):
        # Un férié au 15e jour : effondrement suivi d'un retour à la normale.
        profil = [20] * 14 + [2] + [20] * 6 + [2] * 7
        profil_date = self._semaines("20260302", profil)
        index = self._export(profil_date)
        retenues = offre.fenetre_fiable(index, CONFIG["fiabilite"], MUET)
        creux = (calendar_fr.to_date("20260302") + dt.timedelta(days=14)).strftime("%Y%m%d")
        self.assertIn(creux, retenues, "un creux isolé n'est pas une troncature")
        self.assertEqual(len(retenues), 21)

    def test_export_sans_queue_entierement_retenu(self):
        index = self._export(self._semaines("20260302", [20] * 28))
        self.assertEqual(len(offre.fenetre_fiable(index, CONFIG["fiabilite"], MUET)), 28)

    def test_export_trop_court_declare_inutilisable(self):
        # Le profil de référence est pris sur le début : ici tout est bas, donc
        # rien n'est « sous le seuil » et l'export est retenu tel quel. Mais un
        # export dont il ne reste que 3 jours après la coupe est écarté.
        # Un export livré tardivement : trois journées pleines, puis 25 jours de
        # queue. Il ne reste pas assez de matière fiable — et la référence NE DOIT
        # PAS être contaminée par la queue, sinon rien ne serait coupé.
        profil = [20] * 3 + [2] * 25
        index = self._export(self._semaines("20260302", profil))
        self.assertEqual(offre.fenetre_fiable(index, CONFIG["fiabilite"], MUET), [])


class TestCalendrierHebdomadaire(BaseTemporaire):
    """`calendar.txt` hebdomadaire — la forme publiée par liO.

    Tisséo et le TER n'emploient que des dates explicites ; liO déclare des
    services hebdomadaires que `calendar_dates.txt` corrige dans les deux sens.
    Chaque test porte sur une lecture qui, prise à l'envers, fait rouler des
    cars un jour où l'opérateur dit qu'ils ne roulent pas — ou l'inverse.
    """

    SEMAINE = {"service_id": "S", "monday": "1", "tuesday": "1", "wednesday": "1",
               "thursday": "1", "friday": "1", "saturday": "0", "sunday": "0",
               "start_date": "20260316", "end_date": "20260322"}

    def _indexer(self, calendrier=None, **extra):
        dossier = ecrire_feed(
            self.racine / f"hebdo_{len(list(self.racine.iterdir()))}", lignes=["L1"],
            arrets=ARRETS, courses=[course("T1")], calendrier=calendrier or {},
            geometries=GEOM, **extra,
        )
        return offre.indexer(export_de(dossier), MUET)

    def test_semaine_depliee_en_dates(self):
        index = self._indexer(calendrier_hebdo=[dict(self.SEMAINE)])
        # Du lundi 16 au vendredi 20 mars : cinq jours, samedi et dimanche exclus.
        self.assertEqual(index.dates, ["20260316", "20260317", "20260318", "20260319", "20260320"])
        self.assertEqual(index.nb_trips("20260318"), 1)

    def test_exception_type_2_retire_une_date(self):
        index = self._indexer(calendrier_hebdo=[dict(self.SEMAINE)], retraits=[("S", "20260318")])
        self.assertNotIn("20260318", index.dates)
        self.assertEqual(len(index.dates), 4)

    def test_exception_type_1_ajoute_un_jour_hors_semaine(self):
        index = self._indexer(calendrier_hebdo=[dict(self.SEMAINE)], calendrier={"S": ["20260321"]})
        self.assertIn("20260321", index.dates)   # un samedi ajouté à la main
        self.assertEqual(index.nb_trips("20260321"), 1)

    def test_service_borne_a_l_envers_ignore(self):
        borne = dict(self.SEMAINE, start_date="20260322", end_date="20260316")
        index = self._indexer(calendrier_hebdo=[borne])
        self.assertEqual(index.dates, [])

    def test_dates_explicites_seules_inchangees(self):
        """Sans `calendar.txt`, l'index reste celui de Tisséo et du TER."""
        index = self._indexer(calendrier={"S": ["20260316", "20260317"]})
        self.assertEqual(index.dates, ["20260316", "20260317"])


# ──────────────────────────────────────────────────────────────────────────────
# Calendrier
# ──────────────────────────────────────────────────────────────────────────────


class TestCalendrier(unittest.TestCase):
    PERIODES = [
        calendar_fr.Periode("vac_printemps", dt.date(2026, 4, 18), dt.date(2026, 5, 3)),
        calendar_fr.Periode("ete_juillet", dt.date(2026, 7, 4), dt.date(2026, 7, 31)),
    ]
    FERIES = {"20260501": "1er mai", "20260406": "Lundi de Pâques"}

    def test_signature_hors_vacances(self):
        sig = calendar_fr.signature("20260316", self.PERIODES, self.FERIES)
        self.assertEqual((sig.type_jour, sig.periode), ("lun", "scolaire"))

    def test_signature_en_vacances(self):
        sig = calendar_fr.signature("20260420", self.PERIODES, self.FERIES)
        self.assertEqual((sig.type_jour, sig.periode), ("lun", "vac_printemps"))

    def test_ferie_a_son_propre_type_de_jour(self):
        # Un férié n'est pas un lundi, et n'est pas non plus un dimanche : le
        # 14/07 sert 5 674 courses contre 4 683 à 5 054 les dimanches de juillet.
        sig = calendar_fr.signature("20260406", self.PERIODES, self.FERIES)
        self.assertEqual(sig.type_jour, "ferie")

    def test_decalage_reporte_le_debut_de_periode(self):
        sans = calendar_fr.signature("20260418", self.PERIODES, self.FERIES)
        avec = calendar_fr.signature("20260418", self.PERIODES, self.FERIES, {"vac_printemps": 1})
        self.assertEqual(sans.periode, "vac_printemps")
        self.assertEqual(avec.periode, "scolaire")

    def test_date_locale_corrige_le_decalage_utc(self):
        # L'API publie 22:00 UTC pour des vacances qui s'ouvrent le lendemain à
        # Paris ; l'ignorer décalerait toutes les bornes d'un jour.
        self.assertEqual(calendar_fr._date_locale("2026-04-17T22:00:00+00:00"), dt.date(2026, 4, 18))

    def test_bornes_apprises_sur_les_donnees(self):
        # Le samedi d'ouverture roule encore en samedi scolaire : le décalage
        # qui minimise la dispersion doit être +1.
        offre_reelle = {
            "20260404": 8194, "20260411": 8194, "20260418": 8194,  # samedis scolaires
            "20260425": 8470, "20260502": 8470,                    # samedis de vacances
        }
        decalages = calendar_fr.ajuster_bornes(
            self.PERIODES, self.FERIES, offre_reelle,
            CONFIG["calendrier"]["decalages_debut_testes"], MUET,
        )
        self.assertEqual(decalages.get("vac_printemps"), 1)

    def test_ecart_saisonnier_est_cyclique(self):
        self.assertEqual(donneurs.ecart_saisonnier("20261231", "20260101"), 1)
        self.assertEqual(donneurs.ecart_saisonnier("20260101", "20260311"), 69)
        self.assertEqual(
            donneurs.ecart_saisonnier("20270316", "20260316"),
            0,
            "la même date d'une autre année est à distance nulle",
        )


# ──────────────────────────────────────────────────────────────────────────────
# Autorité et donneurs
# ──────────────────────────────────────────────────────────────────────────────


class TestAutoriteEtDonneurs(BaseTemporaire):
    def _index(self, nom: str, calendrier: dict[str, list[str]], courses: list[dict]):
        dossier = ecrire_feed(
            self.racine / nom, lignes=["L1"], arrets=ARRETS, courses=courses,
            calendrier=calendrier, geometries=GEOM,
        )
        return offre.indexer(export_de(dossier), MUET)

    def test_une_seule_source_par_date(self):
        ancien = self._index("ancien", {"S": ["20260316", "20260317"]},
                             [course("T1", service="S"), course("T2", service="S")])
        recent = self._index("recent", {"S": ["20260317", "20260318"]},
                             [course("T3", service="S")])
        choix = donneurs.autorite(
            {"ancien": ancien, "recent": recent},
            {"ancien": ["20260316", "20260317"], "recent": ["20260317", "20260318"]},
            MUET,
        )
        self.assertEqual(choix["20260316"], "ancien")
        self.assertEqual(choix["20260318"], "recent")
        self.assertEqual(choix["20260317"], "recent", "le plus récemment publié fait autorité")

    def _plan(self, dates_reelles: list[str], annee=2026, dates_sans_service=None,
              periodes=None, feries=None):
        index = self._index(
            "src", {f"S{d}": [d] for d in dates_reelles},
            [course(f"T{d}", service=f"S{d}") for d in dates_reelles],
        )
        return donneurs.plan_annee(
            annee=annee,
            dates_annee=calendar_fr.dates_annee(annee),
            source_par_date={d: "src" for d in dates_reelles},
            index_par_export={"src": index},
            periodes=periodes if periodes is not None else TestCalendrier.PERIODES,
            feries=feries if feries is not None else TestCalendrier.FERIES,
            decalages={},
            config_extrap=CONFIG["extrapolation"],
            dates_sans_service=dates_sans_service or set(),
            journal=MUET,
        )

    def test_date_reelle_en_confiance_haute(self):
        plan = self._plan(["20260316"])
        self.assertEqual(plan["20260316"].mode, donneurs.REEL)
        self.assertEqual(plan["20260316"].confiance, donneurs.HAUTE)
        self.assertEqual(plan["20260316"].date_source, "20260316")

    def test_donneur_de_signature_exacte_le_plus_proche(self):
        # Trois lundis scolaires réels ; le 09/03 doit prendre le plus proche.
        plan = self._plan(["20260316", "20260323", "20260921"])
        provenance = plan["20260309"]
        self.assertEqual(provenance.mode, donneurs.EXTRAPOLE)
        self.assertEqual(provenance.date_source, "20260316")
        self.assertEqual(provenance.motif, "signature exacte")

    def test_ferie_cherche_un_ferie_avant_un_dimanche(self):
        # 06/04 est férié, 05/04 est un dimanche : le 01/05, férié, doit prendre
        # le férié et non le dimanche, bien qu'ils soient à un jour d'écart.
        plan = self._plan(["20260405", "20260406"],
                          periodes=[], feries={"20260406": "Pâques", "20260501": "1er mai"})
        self.assertEqual(plan["20260501"].date_source, "20260406")

    def test_repli_de_periode_en_confiance_basse(self):
        # Un seul lundi réel, en vacances de printemps. Un lundi de période
        # scolaire n'a pas de donneur exact : « scolaire » n'a pas de repli
        # déclaré, donc la journée reste sans service plutôt qu'inventée.
        plan = self._plan(["20260420"])
        self.assertEqual(plan["20260420"].mode, donneurs.REEL)
        scolaire = plan["20260316"]
        self.assertEqual(scolaire.mode, donneurs.SANS_SERVICE)
        self.assertEqual(scolaire.confiance, donneurs.BASSE)

    def test_repli_inverse_vers_les_vacances(self):
        # Symétrique : un lundi de vacances d'hiver se rabat sur les vacances de
        # printemps, en confiance basse et en le disant.
        periodes = TestCalendrier.PERIODES + [
            calendar_fr.Periode("vac_hiver", dt.date(2026, 2, 21), dt.date(2026, 3, 8))
        ]
        plan = self._plan(["20260420"], periodes=periodes)
        hiver = plan["20260223"]
        self.assertEqual(hiver.mode, donneurs.EXTRAPOLE)
        self.assertEqual(hiver.date_source, "20260420")
        self.assertEqual(hiver.confiance, donneurs.BASSE)
        self.assertIn("repli", hiver.motif)

    def test_date_sans_service_reste_vide(self):
        plan = self._plan(["20260420", "20260427"], dates_sans_service={"20260501"})
        provenance = plan["20260501"]
        self.assertEqual(provenance.mode, donneurs.SANS_SERVICE)
        self.assertEqual(provenance.date_source, "")
        self.assertEqual(provenance.confiance, donneurs.HAUTE)

    def test_annee_entiere_couverte(self):
        plan = self._plan(["20260316"])
        self.assertEqual(len(plan), 365)
        self.assertEqual(sorted(plan)[0], "20260101")
        self.assertEqual(sorted(plan)[-1], "20261231")

    def test_declaration_sans_service_reconduite(self):
        from scripts.data.gtfs_year.build_year_feed import dates_sans_service

        parametres = {"dates_sans_service_confirme": ["20260501"]}
        self.assertEqual(dates_sans_service(parametres, 2026, MUET), {"20260501"})
        self.assertEqual(dates_sans_service(parametres, 2027, MUET), {"20270501"})


# ──────────────────────────────────────────────────────────────────────────────
# Assemblage
# ──────────────────────────────────────────────────────────────────────────────


class TestAssemblage(BaseTemporaire):
    IDENTITE = {"feed_id": "test", "publisher": "Test", "url": "https://x", "version": "v1"}

    def _index(self, nom, calendrier, courses, geometries=None, arrets=None,
               correspondances=None):
        dossier = ecrire_feed(
            self.racine / nom, lignes=["L1", "L2"], arrets=arrets or ARRETS,
            courses=courses, calendrier=calendrier,
            geometries=geometries if geometries is not None else GEOM,
            correspondances=correspondances,
        )
        return offre.indexer(export_de(dossier), MUET)

    def _construire(self, plan, index_par_export):
        sortie = self.racine / "sortie"
        stats = assemblage.construire(sortie, plan, index_par_export, CONFIG, self.IDENTITE, MUET)
        return sortie, stats, offre.indexer(export_de(sortie), MUET)

    @staticmethod
    def _reel(date, export, **extra):
        return donneurs.Provenance(
            date=date, signature="lun/scolaire", mode=donneurs.REEL,
            confiance=donneurs.HAUTE, export=export, date_source=date, **extra,
        )

    @staticmethod
    def _extrapole(date, export, source):
        return donneurs.Provenance(
            date=date, signature="lun/scolaire", mode=donneurs.EXTRAPOLE,
            confiance=donneurs.MOYENNE, export=export, date_source=source,
        )

    def test_pas_de_suroffre_sur_recouvrement(self):
        """Le défaut central : l'union de deux exports fabrique de l'offre.

        Sur le feed en service, le 08/04/2026 sert 13 250 courses là où ses deux
        sources en donnent 12 652 et 12 660.
        """
        # Chaque course a son propre horaire : deux courses distinctes d'une
        # même journée ne doivent pas être confondues par leur contenu.
        ancien = self._index("ancien", {"S": ["20260316"]},
                             [course("T1", service="S", depart="08:00:00"),
                              course("T2", service="S", depart="08:30:00")])
        recent = self._index("recent", {"S": ["20260316"]},
                             [course("T2", service="S", depart="08:30:00"),
                              course("T3", service="S", depart="09:00:00")])
        plan = {"20260316": self._reel("20260316", "recent")}
        _, _, sortie = self._construire(plan, {"ancien": ancien, "recent": recent})
        self.assertEqual(
            sortie.nb_trips("20260316"), 2,
            "le feed doit servir les 2 courses de l'export autoritaire, pas les 3 de l'union",
        )
        self.assertEqual(set(sortie.trips_par_date["20260316"]), {"T2", "T3"})

    def test_meme_contenu_dans_deux_exports_fusionne(self):
        a = self._index("a", {"S": ["20260316"]}, [course("T1", service="S")])
        b = self._index("b", {"S": ["20260323"]}, [course("T1", service="S")])
        plan = {
            "20260316": self._reel("20260316", "a"),
            "20260323": self._reel("20260323", "b"),
        }
        _, stats, sortie = self._construire(plan, {"a": a, "b": b})
        self.assertEqual(stats.trips_ecrits, 1)
        self.assertEqual(stats.trips_fusionnes, 1)
        self.assertEqual(stats.trips_forkes, 0)
        self.assertEqual(sortie.nb_trips("20260316"), 1)
        self.assertEqual(sortie.nb_trips("20260323"), 1)

    def test_doublon_de_contenu_du_meme_export_preserve(self):
        """Deux courses identiques d'un même export sont deux courses.

        liO en publie 45 le lundi 14/09/2026 : deux numéros de mission pour un
        même horaire sur une même ligne. Les confondre retirerait une course de
        l'offre de la journée — et V2, qui compare l'offre produite à celle de
        la source, le refuserait.
        """
        index = self._index(
            "doublons", {"S": ["20260316"]},
            [course("T1", service="S", depart="08:00:00"),
             course("T1bis", service="S", depart="08:00:00")],
        )
        plan = {"20260316": self._reel("20260316", "doublons")}
        _, stats, sortie = self._construire(plan, {"doublons": index})
        self.assertEqual(stats.doublons_de_contenu, 1)
        self.assertEqual(stats.trips_fusionnes, 0)
        self.assertEqual(stats.collisions_meme_jour, 0)
        self.assertEqual(sortie.nb_trips("20260316"), 2)

    def test_jours_disjoints_restent_fusionnes(self):
        """Le même contenu sur des jours disjoints reste UNE course.

        C'est la compression du feed : un opérateur découpe son calendrier en
        périodes et republie la même course dans chacune. Les distinguer
        gonflerait le feed sans rien ajouter à l'offre — mesuré sur Tisséo
        2026 : 29,4 Mo au lieu de 22,1 Mo.
        """
        index = self._index(
            "periodes", {"S1": ["20260316"], "S2": ["20260323"]},
            [course("T1", service="S1", depart="08:00:00"),
             course("T2", service="S2", depart="08:00:00")],
        )
        plan = {"20260316": self._reel("20260316", "periodes"),
                "20260323": self._reel("20260323", "periodes")}
        _, stats, sortie = self._construire(plan, {"periodes": index})
        self.assertEqual(stats.doublons_de_contenu, 0)
        self.assertEqual(stats.trips_ecrits, 1)
        self.assertEqual(sortie.nb_trips("20260316"), 1)
        self.assertEqual(sortie.nb_trips("20260323"), 1)

    def test_doublon_de_contenu_preserve_l_empreinte_de_la_journee(self):
        """Le contrôle V2 passe : l'offre produite égale celle de la source."""
        index = self._index(
            "doublons_v2", {"S": ["20260316"]},
            [course("T1", service="S", depart="08:00:00"),
             course("T1bis", service="S", depart="08:00:00")],
        )
        plan = {"20260316": self._reel("20260316", "doublons_v2")}
        _, _, sortie = self._construire(plan, {"doublons_v2": index})
        produite = validation.empreintes_par_date(
            sortie.export, sortie.trips_par_date, {"20260316"}, CONFIG, MUET
        )
        source = validation.empreintes_par_date(
            index.export, index.trips_par_date, {"20260316"}, CONFIG, MUET
        )
        self.assertEqual(produite, source)

    def test_identifiant_recycle_est_forke(self):
        """Un `trip_id` réutilisé pour une autre course ne doit pas être arbitré.

        Le `trip_id` n'est pas stable sur l'année : l'indice de Jaccard entre un
        mardi de mars et un mardi de septembre vaut 0.00.
        """
        a = self._index("a", {"S": ["20260316"]}, [course("T1", service="S", depart="08:00:00")])
        b = self._index("b", {"S": ["20260921"]}, [course("T1", service="S", depart="09:00:00")])
        plan = {
            "20260316": self._reel("20260316", "a"),
            "20260921": self._reel("20260921", "b"),
        }
        _, stats, sortie = self._construire(plan, {"a": a, "b": b})
        self.assertEqual(stats.trips_forkes, 1)
        self.assertEqual(stats.trips_ecrits, 2)
        self.assertEqual(sortie.trips_par_date["20260316"], ["T1"])
        self.assertEqual(sortie.trips_par_date["20260921"], ["T1__b"])

    def test_geometrie_divergente_dupliquee_jamais_fusionnee(self):
        """Le tracé chimère : dédupliquer sur (shape_id, shape_pt_sequence)
        entrelace deux géométries et casse le lien avec les distances d'arrêt.
        """
        geom_a = {"SH1": [(43.60, 1.44, 0.0), (43.61, 1.45, 1000.0)]}
        geom_b = {"SH1": [(43.60, 1.44, 0.0), (43.62, 1.46, 1500.0), (43.63, 1.47, 2000.0)]}
        a = self._index("a", {"S": ["20260316"]}, [course("T1", service="S")], geometries=geom_a)
        b = self._index("b", {"S": ["20260921"]}, [course("T9", service="S")], geometries=geom_b)
        plan = {
            "20260316": self._reel("20260316", "a"),
            "20260921": self._reel("20260921", "b"),
        }
        sortie, stats, _ = self._construire(plan, {"a": a, "b": b})
        self.assertEqual(stats.shapes_dupliquees, 1)

        points = {}
        for ligne in gtfs_io.lire(export_de(sortie), "shapes.txt"):
            points.setdefault(ligne["shape_id"], []).append(ligne)
        self.assertEqual(sorted(points), ["SH1", "SH1__b"])
        self.assertEqual(len(points["SH1"]), 2)
        self.assertEqual(len(points["SH1__b"]), 3)
        # Chaque géométrie garde une séquence complète repartant de 1 : c'est
        # exactement ce que l'entrelacement détruisait.
        for identifiant, rangs in points.items():
            sequences = sorted(int(r["shape_pt_sequence"]) for r in rangs)
            self.assertEqual(sequences, list(range(1, len(rangs) + 1)), identifiant)

        par_trip = {l["trip_id"]: l["shape_id"] for l in gtfs_io.lire(export_de(sortie), "trips.txt")}
        self.assertEqual(par_trip["T1"], "SH1")
        self.assertEqual(par_trip["T9"], "SH1__b")

    def test_journee_extrapolee_est_une_copie_exacte(self):
        source = self._index("src", {"S": ["20260316"]},
                             [course("T1", service="S"), course("T2", service="S")])
        plan = {
            "20260316": self._reel("20260316", "src"),
            "20261214": self._extrapole("20261214", "src", "20260316"),
        }
        _, _, sortie = self._construire(plan, {"src": source})
        self.assertEqual(
            sortie.trips_par_date["20261214"], sortie.trips_par_date["20260316"]
        )

    def test_calendrier_regroupe_par_ensemble_de_dates(self):
        # T1 et T2 roulent les mêmes jours → un seul service ; T3 un autre jour.
        source = self._index(
            "src", {"SA": ["20260316", "20260317"], "SB": ["20260318"]},
            [course("T1", service="SA", depart="08:00:00"),
             course("T2", service="SA", depart="08:30:00"),
             course("T3", service="SB", depart="09:00:00")],
        )
        plan = {d: self._reel(d, "src") for d in ("20260316", "20260317", "20260318")}
        sortie, stats, _ = self._construire(plan, {"src": source})
        self.assertEqual(stats.services, 2)
        # 2 dates pour le service de T1/T2, 1 pour celui de T3.
        self.assertEqual(stats.lignes_calendrier, 3)
        services = {}
        for ligne in gtfs_io.lire(export_de(sortie), "trips.txt"):
            services[ligne["trip_id"]] = ligne["service_id"]
        self.assertEqual(services["T1"], services["T2"])
        self.assertNotEqual(services["T1"], services["T3"])

    def test_contrat_du_lecteur_du_depot(self):
        """`calendar.txt` vide et `exception_type=1` : les deux asserts de
        `llm-agents/inputs/gtfs/reader.py`."""
        source = self._index("src", {"S": ["20260316"]}, [course("T1", service="S")])
        sortie, _, _ = self._construire({"20260316": self._reel("20260316", "src")}, {"src": source})
        self.assertEqual(list(gtfs_io.lire(export_de(sortie), "calendar.txt")), [])
        exceptions = {l["exception_type"] for l in gtfs_io.lire(export_de(sortie), "calendar_dates.txt")}
        self.assertEqual(exceptions, {"1"})

    def test_fermeture_referentielle_et_station_parente(self):
        arrets = [("A", 43.60, 1.44, "GARE"), ("B", 43.61, 1.45, ""), ("GARE", 43.60, 1.44, ""),
                  ("Z", 43.70, 1.50, "")]
        source = self._index("src", {"S": ["20260316"]}, [course("T1", service="S")],
                             arrets=arrets, correspondances=[("A", "B"), ("A", "Z")])
        sortie, stats, _ = self._construire({"20260316": self._reel("20260316", "src")}, {"src": source})
        self.assertEqual(sum(stats.orphelins.values()), 0)
        arrets_sortie = {l["stop_id"] for l in gtfs_io.lire(export_de(sortie), "stops.txt")}
        self.assertEqual(arrets_sortie, {"A", "B", "GARE"}, "la station parente suit ses quais")
        transferts = {(l["from_stop_id"], l["to_stop_id"])
                      for l in gtfs_io.lire(export_de(sortie), "transfers.txt")}
        self.assertEqual(transferts, {("A", "B")}, "la correspondance vers un arrêt écarté tombe")

    def test_arret_deplace_leve_une_alarme(self):
        a = self._index("a", {"S": ["20260316"]}, [course("T1", service="S")])
        b = self._index(
            "b", {"S": ["20260323"]}, [course("T2", service="S")],
            arrets=[("A", 43.601000, 1.440000), ("B", 43.610000, 1.450000)],  # ~111 m
        )
        plan = {
            "20260316": self._reel("20260316", "a"),
            "20260323": self._reel("20260323", "b"),
        }
        _, stats, _ = self._construire(plan, {"a": a, "b": b})
        self.assertTrue(stats.arrets_deplaces)
        identifiants = {s for s, _ in stats.arrets_deplaces}
        self.assertIn("A", identifiants)


# ──────────────────────────────────────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────────────────────────────────────


class TestValidation(BaseTemporaire):
    IDENTITE = TestAssemblage.IDENTITE

    def _index(self, nom, calendrier, courses, geometries=None):
        dossier = ecrire_feed(
            self.racine / nom, lignes=["L1"], arrets=ARRETS, courses=courses,
            calendrier=calendrier, geometries=geometries if geometries is not None else GEOM,
        )
        return offre.indexer(export_de(dossier), MUET)

    def test_empreinte_ignore_les_identifiants(self):
        """Deux feeds servant la même offre sous des identifiants différents
        doivent avoir la même empreinte — c'est ce qui rend V2 utilisable
        alors que les `service_id` sont réécrits par construction."""
        a = self._index("a", {"SX": ["20260316"]}, [course("T1", service="SX")])
        b = self._index("b", {"SY": ["20260316"]}, [course("T999", service="SY")])
        empreinte_a = validation.empreintes_par_date(
            a.export, a.trips_par_date, {"20260316"}, CONFIG, MUET)
        empreinte_b = validation.empreintes_par_date(
            b.export, b.trips_par_date, {"20260316"}, CONFIG, MUET)
        self.assertEqual(empreinte_a["20260316"], empreinte_b["20260316"])

    def test_empreinte_voit_une_course_manquante(self):
        a = self._index("a", {"S": ["20260316"]},
                        [course("T1", service="S"), course("T2", service="S", depart="09:00:00")])
        b = self._index("b", {"S": ["20260316"]}, [course("T1", service="S")])
        self.assertNotEqual(
            validation.empreintes_par_date(a.export, a.trips_par_date, {"20260316"}, CONFIG, MUET),
            validation.empreintes_par_date(b.export, b.trips_par_date, {"20260316"}, CONFIG, MUET),
        )

    def test_v2_demasque_une_suroffre_injectee(self):
        source = self._index("src", {"S": ["20260316"]}, [course("T1", service="S")])
        plan = {"20260316": TestAssemblage._reel("20260316", "src")}
        sortie = self.racine / "sortie"
        assemblage.construire(sortie, plan, {"src": source}, CONFIG, self.IDENTITE, MUET)

        violations, _, _ = validation.controler(sortie, plan, {"src": source}, CONFIG, MUET)
        self.assertEqual([v for v in violations if v.gravite == validation.BLOQUANT], [])

        # On injecte une course supplémentaire ce jour-là, comme le ferait une
        # fusion par union de deux exports.
        service = next(iter(gtfs_io.lire(export_de(sortie), "calendar_dates.txt")))["service_id"]
        with open(sortie / "trips.txt", "a", encoding="utf-8") as fichier:
            fichier.write(f"L1,{service},TDOUBLON,dest,0,SH1\n")
        with open(sortie / "stop_times.txt", "a", encoding="utf-8") as fichier:
            fichier.write("TDOUBLON,1,08:00:00,08:00:00,0,0,,0.0,A\n")

        violations, _, _ = validation.controler(sortie, plan, {"src": source}, CONFIG, MUET)
        codes = {v.code for v in violations if v.gravite == validation.BLOQUANT}
        self.assertIn("V2", codes, "une sur-offre doit être bloquante")

    def test_v6_demasque_un_trace_chimere(self):
        """Une distance d'arrêt au-delà de la longueur du tracé est la signature
        d'une géométrie entrelacée — le défaut de la shape 14846."""
        source = self._index("src", {"S": ["20260316"]}, [course("T1", service="S")])
        plan = {"20260316": TestAssemblage._reel("20260316", "src")}
        sortie = self.racine / "sortie"
        assemblage.construire(sortie, plan, {"src": source}, CONFIG, self.IDENTITE, MUET)

        # On raccourcit la géométrie sans toucher aux horaires : le dernier arrêt
        # est désormais au-delà de la fin du tracé.
        lignes = list(gtfs_io.lire(export_de(sortie), "shapes.txt"))
        gtfs_io.ecrire_table(
            sortie / "shapes.txt",
            ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence", "shape_dist_traveled"],
            [{**l, "shape_dist_traveled": "10.0"} for l in lignes],
        )
        violations, _, _ = validation.controler(sortie, plan, {"src": source}, CONFIG, MUET)
        self.assertIn("V6", {v.code for v in violations if v.gravite == validation.BLOQUANT})

    def test_v6_defaut_deja_publie_par_la_source_nest_pas_bloquant(self):
        """Un `shape_dist_traveled` trop long chez l'opérateur n'est pas un
        tracé chimère : le build l'a recopié, il ne l'a pas fabriqué. liO en
        publie 29 sur 7 715 courses ; bloquer là-dessus reviendrait à exiger du
        pipeline qu'il répare la source."""
        source = self._index("src", {"S": ["20260316"]}, [course("T1", service="S")],
                             geometries={"SH1": [(43.60, 1.44, 0.0), (43.61, 1.45, 10.0)]})
        plan = {"20260316": TestAssemblage._reel("20260316", "src")}
        sortie = self.racine / "sortie"
        assemblage.construire(sortie, plan, {"src": source}, CONFIG, self.IDENTITE, MUET)
        violations, _, _ = validation.controler(sortie, plan, {"src": source}, CONFIG, MUET)
        codes_bloquants = {v.code for v in violations if v.gravite == validation.BLOQUANT}
        self.assertNotIn("V6", codes_bloquants)
        self.assertIn("V6", {v.code for v in violations if v.gravite == validation.ALARME})

    def test_v7_demasque_une_copie_infidele(self):
        """Une journée extrapolée doit servir exactement l'offre de son donneur."""
        source = self._index("src", {"S": ["20260316"]}, [course("T1", service="S")])
        plan = {"20260317": TestAssemblage._extrapole("20260317", "src", "20260316")}
        sortie = self.racine / "sortie"
        assemblage.construire(sortie, plan, {"src": source}, CONFIG, self.IDENTITE, MUET)
        violations, _, _ = validation.controler(sortie, plan, {"src": source}, CONFIG, MUET)
        self.assertNotIn("V7", {v.code for v in violations if v.gravite == validation.BLOQUANT})

        # Une course de plus le jour copié : la copie n'est plus verbatim.
        service = next(iter(gtfs_io.lire(export_de(sortie), "calendar_dates.txt")))["service_id"]
        with open(sortie / "trips.txt", "a", encoding="utf-8") as fichier:
            fichier.write(f"L1,{service},TDOUBLON,dest,0,SH1\n")
        with open(sortie / "stop_times.txt", "a", encoding="utf-8") as fichier:
            fichier.write("TDOUBLON,1,08:00:00,08:00:00,0,0,,0.0,A\n")
        violations, _, _ = validation.controler(sortie, plan, {"src": source}, CONFIG, MUET)
        self.assertIn("V7", {v.code for v in violations if v.gravite == validation.BLOQUANT})

    def test_v8_signale_une_journee_sans_offre(self):
        source = self._index("src", {"S": ["20260316"]}, [course("T1", service="S")])
        plan = {
            "20260316": TestAssemblage._reel("20260316", "src"),
            # Une date planifiée mais dont l'export ne dit rien : le feed ne
            # servira rien ce jour-là.
            "20260317": TestAssemblage._extrapole("20260317", "src", "20260401"),
        }
        sortie = self.racine / "sortie"
        assemblage.construire(sortie, plan, {"src": source}, CONFIG, self.IDENTITE, MUET)
        violations, _, _ = validation.controler(sortie, plan, {"src": source}, CONFIG, MUET)
        self.assertIn("V8", {v.code for v in violations})


# ──────────────────────────────────────────────────────────────────────────────
# Fenêtrage
# ──────────────────────────────────────────────────────────────────────────────


class TestFenetrage(BaseTemporaire):
    def _feed_annuel(self) -> Path:
        dates = [
            (dt.date(2026, 3, 16) + dt.timedelta(days=i)).strftime("%Y%m%d") for i in range(120)
        ]
        courses, calendrier = [], {}
        for i, date in enumerate(dates):
            service = f"SVC_{i:04d}"
            calendrier[service] = [date]
            courses.append(course(f"T{i}", service=service))
        return ecrire_feed(
            self.racine / "annuel", lignes=["L1"], arrets=ARRETS, courses=courses,
            calendrier=calendrier, geometries=GEOM,
        )

    def test_refuse_au_dela_du_masque_binaire(self):
        """GAMA encode le calendrier en masque 64 bits : au-delà, l'export
        échoue (`assert len(all_dates) <= 64` dans inputs/gtfs/gama.py)."""
        code = window_feed.fenetrer(self._feed_annuel(), "20260316", 90, self.racine / "f", MUET)
        self.assertEqual(code, 2)

    def test_fenetre_bornee_et_fermee(self):
        source = self._feed_annuel()
        sortie = self.racine / "fenetre"
        self.assertEqual(window_feed.fenetrer(source, "20260316", 64, sortie, MUET), 0)

        index = offre.indexer(export_de(sortie), MUET)
        self.assertEqual(index.dates[0], "20260316")
        self.assertEqual(len(index.dates), 64)
        self.assertLessEqual(
            len(index.dates), window_feed.LIMITE_MASQUE, "le masque binaire ne tient pas au-delà"
        )
        # Aucun trip hors fenêtre, et pas de service pendant.
        services_calendrier = {
            l["service_id"] for l in gtfs_io.lire(export_de(sortie), "calendar_dates.txt")
        }
        services_trips = {l["service_id"] for l in gtfs_io.lire(export_de(sortie), "trips.txt")}
        self.assertEqual(services_trips, services_calendrier)

    def test_fenetre_hors_calendrier_refusee(self):
        code = window_feed.fenetrer(self._feed_annuel(), "20250101", 64, self.racine / "f", MUET)
        self.assertEqual(code, 2)


# ──────────────────────────────────────────────────────────────────────────────
# Configuration livrée
# ──────────────────────────────────────────────────────────────────────────────


class TestConfigurationLivree(unittest.TestCase):
    """Le YAML livré doit porter toutes les clés que le code lit.

    Sans ce test, retirer une clé de `feed_year.yaml` ne casse rien avant le
    prochain build complet — et le build dure deux minutes.
    """

    def test_cles_attendues_presentes(self):
        for chemin in [
            ("fiabilite", "ratio_lignes_min"),
            ("fiabilite", "ratio_plancher_lignes"),
            ("fiabilite", "jours_min_par_export"),
            ("calendrier", "localite"),
            ("calendrier", "decalages_debut_testes"),
            ("extrapolation", "repli_periodes"),
            ("extrapolation", "repli_ferie"),
            ("extrapolation", "confiance", "moyenne_si_ecart_jours_max"),
            ("controles", "deplacement_arret_max_m"),
            ("controles", "dispersion_signature_max"),
            ("controles", "ratio_lignes_min_jour_ouvre"),
            ("controles", "dates_confiance_basse_max"),
            ("controles", "holdout_ecart_max"),
            ("canonicalisation", "decimales_coordonnees"),
            ("canonicalisation", "decimales_distance"),
        ]:
            noeud = CONFIG
            for cle in chemin:
                self.assertIn(cle, noeud, f"clé manquante : {' → '.join(chemin)}")
                noeud = noeud[cle]

    def test_chaque_classe_de_periode_a_un_repli(self):
        replis = CONFIG["extrapolation"]["repli_periodes"]
        for classe in calendar_fr.CLASSES_VACANCES + (calendar_fr.SCOLAIRE,):
            self.assertIn(classe, replis, f"classe sans chaîne de repli déclarée : {classe}")

    def test_reseaux_declares_ont_une_identite(self):
        from scripts.data.gtfs_year.build_year_feed import IDENTITES

        for reseau in CONFIG["reseaux"]:
            self.assertIn(reseau, IDENTITES, f"réseau sans identité de feed : {reseau}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
