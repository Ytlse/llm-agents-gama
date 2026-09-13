"""
Calendrier scolaire de la zone de Toulouse et jours fériés métropolitains.

Sert à classer chaque journée de l'année par SIGNATURE — le couple
(type de jour, classe de période) qui détermine le niveau d'offre du réseau.

Pourquoi c'est nécessaire : l'offre Tisséo suit le calendrier scolaire de très
près, et les bornes officielles de la zone C coïncident exactement avec les
ruptures mesurées dans les exports (chute de 12 600 à 10 535 trips le lundi
20/04/2026, retour à 12 538 le lundi 04/05, vendredi de pont 15/05 réduit à
10 877). Classer une journée sans ce calendrier reviendrait à recopier une
journée de vacances sur une journée scolaire.

Deux sources publiques, toutes deux mises en cache sur disque pour que le build
reste rejouable hors ligne :

  - data.education.gouv.fr  → vacances scolaires par zone et par localité
  - calendrier.api.gouv.fr  → jours fériés métropolitains

Un instantané validé est versionné à côté de ce module
(`calendrier_snapshot.json`) et sert de repli si le réseau est indisponible.

Ce module ne décide pas de l'offre : il ne fait qu'étiqueter des dates.
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

MODULE_DIR = Path(__file__).resolve().parent
CACHE_DIR = MODULE_DIR / "cache"
SNAPSHOT = MODULE_DIR / "calendrier_snapshot.json"

API_VACANCES = (
    "https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/"
    "fr-en-calendrier-scolaire/records"
)
API_FERIES = "https://calendrier.api.gouv.fr/jours-feries/metropole/{year}.json"

TIMEOUT_S = 30

# Classes de période. L'été est scindé car juillet et août ont des offres
# distinctes (≈ 9 910 trips un lundi de juillet, ≈ 10 418 fin août).
SCOLAIRE = "scolaire"
CLASSES_VACANCES = (
    "vac_hiver",
    "vac_printemps",
    "pont_ascension",
    "ete_juillet",
    "ete_aout",
    "vac_toussaint",
    "vac_noel",
)

# Libellé renvoyé par l'API → classe interne.
_LIBELLE_VERS_CLASSE = {
    "vacances d'hiver": "vac_hiver",
    "vacances de printemps": "vac_printemps",
    "pont de l'ascension": "pont_ascension",
    "vacances d'été": "ete",  # scindé ensuite en ete_juillet / ete_aout
    "début des vacances d'été": "ete",
    "vacances de la toussaint": "vac_toussaint",
    "vacances de noël": "vac_noel",
}

# Quand seule la date de DÉBUT des grandes vacances est publiée — le calendrier
# de l'année scolaire suivante ne l'étant pas encore —, la fin est posée au
# 31 août. C'est une hypothèse, journalisée comme telle : elle ne déplace que
# la frontière entre « vacances d'été » et « scolaire » sur les tout derniers
# jours d'août, où l'offre remonte de toute façon avant la rentrée officielle.
FIN_ETE_PAR_DEFAUT = (8, 31)

JOURS = ("lun", "mar", "mer", "jeu", "ven", "sam", "dim")


@dataclass(frozen=True)
class Periode:
    """Une plage de vacances scolaires, en dates locales inclusives."""

    classe: str
    debut: dt.date
    fin: dt.date

    def contient(self, jour: dt.date) -> bool:
        return self.debut <= jour <= self.fin


@dataclass(frozen=True)
class Signature:
    """Ce qui détermine le niveau d'offre d'une journée."""

    type_jour: str  # lun..dim, ou "ferie"
    periode: str  # scolaire, vac_*, ete_*

    def __str__(self) -> str:  # pragma: no cover - confort de lecture
        return f"{self.type_jour}/{self.periode}"


# ──────────────────────────────────────────────────────────────────────────────
# Récupération et cache
# ──────────────────────────────────────────────────────────────────────────────


def _lire_cache(nom: str) -> dict | None:
    chemin = CACHE_DIR / nom
    if chemin.exists():
        return json.loads(chemin.read_text(encoding="utf-8"))
    return None


def _ecrire_cache(nom: str, charge: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / nom).write_text(
        json.dumps(charge, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _lire_snapshot(cle: str) -> dict | None:
    if not SNAPSHOT.exists():
        return None
    return json.loads(SNAPSHOT.read_text(encoding="utf-8")).get(cle)


def _figer_instantane(cle: str, charge: dict) -> None:
    """Verse une récupération réussie dans l'instantané versionné.

    Le cache disque est jetable ; l'instantané, lui, est committé avec le
    dépôt et permet de rejouer un build à l'identique sans réseau.
    """
    contenu = {}
    if SNAPSHOT.exists():
        contenu = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    if contenu.get(cle) == charge:
        return
    contenu[cle] = charge
    SNAPSHOT.write_text(
        json.dumps(contenu, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )


def _contexte_ssl():
    """Contexte TLS avec un magasin de certificats utilisable.

    Les interpréteurs Python installés à la main sur macOS n'ont pas de magasin
    système : sans `certifi`, toute requête HTTPS échoue en
    CERTIFICATE_VERIFY_FAILED alors que `curl` passe.
    """
    import ssl

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _http_json(url: str) -> dict:
    requete = urllib.request.Request(url, headers={"User-Agent": "llm-agents-gama/gtfs_year"})
    with urllib.request.urlopen(requete, timeout=TIMEOUT_S, context=_contexte_ssl()) as reponse:
        return json.loads(reponse.read().decode("utf-8"))


def _recuperer(nom_cache: str, url: str, rafraichir: bool, journal) -> dict:
    """Cache disque → réseau → instantané versionné. Jamais d'échec muet."""
    if not rafraichir:
        depuis_cache = _lire_cache(nom_cache)
        if depuis_cache is not None:
            journal(f"    calendrier : {nom_cache} lu depuis le cache")
            return depuis_cache
    try:
        charge = _http_json(url)
        _ecrire_cache(nom_cache, charge)
        _figer_instantane(nom_cache, charge)
        journal(f"    calendrier : {nom_cache} récupéré en ligne et mis en cache")
        return charge
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        instantane = _lire_snapshot(nom_cache)
        if instantane is None:
            raise RuntimeError(
                f"[ALARME] calendrier indisponible : {url} injoignable ({err}) "
                f"et aucun instantané pour {nom_cache}"
            ) from err
        journal(f"    calendrier : {nom_cache} — réseau indisponible ({err}), repli sur l'instantané versionné")
        return instantane


# ──────────────────────────────────────────────────────────────────────────────
# Jours fériés
# ──────────────────────────────────────────────────────────────────────────────


def feries(annee: int, rafraichir: bool = False, journal=print) -> dict[str, str]:
    """Jours fériés métropolitains de l'année, en `YYYYMMDD` → libellé."""
    charge = _recuperer(f"feries_{annee}.json", API_FERIES.format(year=annee), rafraichir, journal)
    return {k.replace("-", ""): v for k, v in charge.items()}


# ──────────────────────────────────────────────────────────────────────────────
# Vacances scolaires
# ──────────────────────────────────────────────────────────────────────────────


def _date_locale(horodatage: str) -> dt.date:
    """Convertit un horodatage UTC de l'API en date locale Europe/Paris.

    L'API publie `2026-04-17T22:00:00+00:00` pour des vacances qui commencent le
    18/04 à 00:00 heure de Paris. Ignorer ce décalage décalerait toutes les
    bornes d'un jour.

    Le +2 h vaut aussi en hiver, pour une autre raison : l'API publie alors
    `23:00Z` (heure d'hiver = UTC+1), et +2 h donne 01:00 le lendemain — même
    date locale. Un décalage dépendant de la saison serait donc inutile ici, et
    seule la DATE du résultat est lue.
    """
    moment = dt.datetime.fromisoformat(horodatage)
    return (moment + dt.timedelta(hours=2)).date()


def vacances(
    annee: int,
    localite: str = "Toulouse",
    rafraichir: bool = False,
    journal=print,
) -> list[Periode]:
    """Périodes de vacances scolaires touchant l'année, classe par classe.

    On interroge une fenêtre large (année-1 à année+1) pour attraper les
    vacances de Noël à cheval sur deux années civiles.
    """
    where = (
        f'location="{localite}" '
        f'and end_date>="{annee - 1}-06-01" '
        f'and start_date<="{annee + 1}-06-30"'
    )
    url = API_VACANCES + "?" + urllib.parse.urlencode(
        {
            "where": where,
            "limit": 100,
            "select": "description,start_date,end_date,zones,population",
            "order_by": "start_date",
        }
    )
    charge = _recuperer(f"vacances_{localite}_{annee}.json", url, rafraichir, journal)

    brut: list[Periode] = []
    vus: set[tuple[str, dt.date, dt.date]] = set()
    for enreg in charge.get("results", []):
        libelle = (enreg.get("description") or "").strip().lower()
        classe = _LIBELLE_VERS_CLASSE.get(libelle)
        if classe is None:
            journal(f"    calendrier : période ignorée, libellé inconnu — {libelle!r}")
            continue
        # L'été est publié deux fois (élèves / enseignants) : on garde la plage
        # la plus large, celle qui borne réellement l'offre de transport.
        debut = _date_locale(enreg["start_date"])
        fin = _date_locale(enreg["end_date"]) - dt.timedelta(days=1)
        if fin < debut:
            if classe == "ete":
                # Entrée ponctuelle « Début des vacances d'été » : la fin n'est
                # pas publiée tant que le calendrier de l'année suivante ne
                # l'est pas.
                fin = dt.date(debut.year, *FIN_ETE_PAR_DEFAUT)
                journal(
                    f"    calendrier : {libelle} du {debut} sans date de fin publiée, "
                    f"bornée au {fin} par hypothèse"
                )
            else:
                # Période d'un seul jour (un pont isolé).
                fin = debut
        cle = (classe, debut, fin)
        if cle in vus:
            continue
        vus.add(cle)
        brut.append(Periode(classe, debut, fin))

    # Fusion des doublons de même classe qui se chevauchent (été élèves /
    # enseignants), puis scission de l'été.
    fusionnees: dict[str, Periode] = {}
    for periode in brut:
        cle = f"{periode.classe}:{periode.debut.year}:{periode.debut.month}"
        deja = fusionnees.get(cle)
        if deja is None:
            fusionnees[cle] = periode
        else:
            fusionnees[cle] = Periode(
                periode.classe, min(deja.debut, periode.debut), max(deja.fin, periode.fin)
            )

    resultat: list[Periode] = []
    for periode in fusionnees.values():
        if periode.classe != "ete":
            resultat.append(periode)
            continue
        bascule = dt.date(periode.debut.year, 8, 1)
        if periode.debut < bascule <= periode.fin:
            resultat.append(Periode("ete_juillet", periode.debut, bascule - dt.timedelta(days=1)))
            resultat.append(Periode("ete_aout", bascule, periode.fin))
        else:
            resultat.append(
                Periode("ete_aout" if periode.debut >= bascule else "ete_juillet", periode.debut, periode.fin)
            )

    resultat.sort(key=lambda p: p.debut)
    return resultat


# ──────────────────────────────────────────────────────────────────────────────
# Signatures
# ──────────────────────────────────────────────────────────────────────────────


def dates_annee(annee: int) -> list[str]:
    """Toutes les dates de l'année en `YYYYMMDD`."""
    jour = dt.date(annee, 1, 1)
    fin = dt.date(annee, 12, 31)
    sortie = []
    while jour <= fin:
        sortie.append(jour.strftime("%Y%m%d"))
        jour += dt.timedelta(days=1)
    return sortie


def to_date(datestr: str) -> dt.date:
    return dt.date(int(datestr[:4]), int(datestr[4:6]), int(datestr[6:8]))


def signature(
    datestr: str,
    periodes: Iterable[Periode],
    jours_feries: dict[str, str],
    decalages: dict[str, int] | None = None,
) -> Signature:
    """Signature d'une date : (type de jour, classe de période).

    `decalages` reporte le début d'une période de N jours ; il est APPRIS sur
    les dates réelles par `ajuster_bornes`, jamais postulé.
    """
    jour = to_date(datestr)
    decalages = decalages or {}

    classe = SCOLAIRE
    for periode in periodes:
        debut = periode.debut + dt.timedelta(days=decalages.get(periode.classe, 0))
        if debut <= jour <= periode.fin:
            classe = periode.classe
            break

    type_jour = "ferie" if datestr in jours_feries else JOURS[jour.weekday()]
    return Signature(type_jour, classe)


def ajuster_bornes(
    periodes: list[Periode],
    jours_feries: dict[str, str],
    offre_reelle: dict[str, int],
    decalages_testes: list[int],
    journal=print,
) -> dict[str, int]:
    """Apprend le décalage de début de chaque période sur les dates réelles.

    La borne officielle des vacances ne coïncide pas toujours avec la bascule
    d'offre : le samedi 18/04/2026, premier jour officiel des vacances de
    printemps, roule encore en samedi scolaire (8 194 trips, comme les samedis
    scolaires du 04/04 et du 11/04, contre 8 470 le samedi de vacances suivant).
    Mais l'été bascule dès son premier samedi. Plutôt que de trancher a priori,
    on retient pour chaque période le décalage qui minimise la dispersion
    relative du nombre de trips à l'intérieur de chaque signature.

    Renvoie {classe_de_période: décalage_en_jours}.
    """
    if not offre_reelle:
        return {}

    def dispersion(decalages: dict[str, int]) -> float:
        groupes: dict[str, list[int]] = {}
        for datestr, trips in offre_reelle.items():
            sig = str(signature(datestr, periodes, jours_feries, decalages))
            groupes.setdefault(sig, []).append(trips)
        total = 0.0
        for valeurs in groupes.values():
            if len(valeurs) < 2:
                continue
            moyenne = sum(valeurs) / len(valeurs)
            if moyenne <= 0:
                continue
            etendue = max(valeurs) - min(valeurs)
            total += etendue / moyenne
        return total

    decalages: dict[str, int] = {}
    for periode in periodes:
        # Sans date réelle dans la période, aucun décalage n'est mesurable.
        couvert = any(
            periode.debut <= to_date(d) <= periode.fin for d in offre_reelle
        )
        if not couvert:
            continue
        meilleur, score_min = 0, None
        for decalage in decalages_testes:
            essai = dict(decalages, **{periode.classe: decalage})
            score = dispersion(essai)
            if score_min is None or score < score_min - 1e-9:
                meilleur, score_min = decalage, score
        if meilleur:
            journal(
                f"    calendrier : début de {periode.classe} recalé de +{meilleur} j "
                f"({periode.debut} → {periode.debut + dt.timedelta(days=meilleur)}), appris sur les dates réelles"
            )
        decalages[periode.classe] = meilleur
    return decalages
