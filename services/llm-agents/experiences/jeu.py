"""Jeu de déplacements enregistré (ticket 035, spec 01).

Un objet **nommé, daté, transportable** — pas un cache : toutes les propositions que les moteurs
savent produire pour tous les déplacements de la journée d'une population, calculées une fois,
**sans** le filtre véhicule ni le plafond d'options (le filtre s'applique à la décision, spec 02).

Sur le disque, un dossier `data/jeux/<nom>/` :

    MANIFEST.yaml        identité (population + empreinte), dépendances, complétude, sha256 des lignes
    propositions.jsonl   une ligne JSON par déplacement (personne, activités, heure, propositions)

Règles tenues ici : J1 (population par nom + empreinte), J2 (déplacements dérivés des agendas),
J3 (sur-ensemble : tous modes, sans plafond), J5 (identité = empreinte du contenu), J7/J8
(complétude visible), J9/J10 (dépendances et péremption), J11 (reprise), J12/J13 (portable, inerte,
refus d'un jeu altéré ou malformé), J14 (immuable après clôture), J15 (journal + ALARME), J16
(aucun attribut du persona).
"""

from __future__ import annotations

import asyncio
import calendar
import json
import os
import subprocess
import time
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path

import yaml
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from chaine_activites import paires_de_la_journee
from experiences import froid
from experiences.decision import SOURCE_ENREGISTREE, SOURCE_LOCALE, Proposition
from experiences.population import InfoPopulation, sha256_fichier
from helper import shift_weekend_departure_to_monday, to_timestamp_based_on_day
from models import Location, Person, TravelPlan
from settings import settings

VERSION_JEU = "jeu1"
FICHIER_MANIFEST = "MANIFEST.yaml"
FICHIER_PROPOSITIONS = "propositions.jsonl"
FICHIER_EQUIVALENCES = (
    "EQUIVALENCES.yaml"  # jours dont l'offre TC a été MESURÉE identique à celle du jeu
)
HEURE_REFERENCE_DEPART = "depart_programme"

MOTIF_ORIGINE_EGALE_DESTINATION = "origine_egale_destination"
MOTIF_AUCUNE_PROPOSITION = "aucune_proposition"


def est_defaillance_moteur(motif: str | None) -> bool:
    """Ce motif d'absence dit-il qu'un moteur a ÉCHOUÉ, ou seulement qu'il n'y avait rien à faire ?

    Distinction structurante, et la confondre faisait mentir trois compteurs à la fois
    (ticket 045). Entre un point et lui-même il n'y a pas d'itinéraire à calculer : une
    fermeture sur place n'est pas une défaillance, c'est une propriété de la journée. Elle
    n'entre donc ni dans l'alarme de santé des moteurs, ni dans le dénominateur de la
    complétude d'un jeu.

    L'enjeu est chiffré : sur la cohorte v5, 138 des 3 299 déplacements ont leur origine pour
    destination — 77 fermetures de journée (la personne finit déjà chez elle) et 61 trajets
    intermédiaires entre deux activités au même lieu. Soit 4,2 %, tout près du seuil d'alarme
    de 5 % : les compter ferait hurler l'alarme à la moindre défaillance réelle, ce qui revient
    à l'éteindre. Le jeu v5 préparé le 2026-09-11 le confirme — 138 sans proposition, et ZÉRO
    défaillance de moteur.
    """
    return bool(motif) and motif != MOTIF_ORIGINE_EGALE_DESTINATION


# Fichiers dont l'empreinte entre dans les dépendances (J9). Relatifs au dossier GTFS en
# service pour les feeds (et le graphe OTP qui y vit), à `services/llm-agents/config` pour les règles.
_FICHIERS_GTFS = (
    "feed_info.txt",
    "calendar.txt",
    "calendar_dates.txt",
    "routes.txt",
    "stops.txt",
    "trips.txt",
    "stop_times.txt",
)
_FICHIER_GRAPHE_OTP = "graph.obj"
_FICHIERS_CONFIG = ("osmnx.yaml", "terminal_time.yaml", "school_bus.yaml")


class JeuInvalide(ValueError):
    """Le jeu ne peut pas être chargé : altéré, malformé, sans dépendances, population autre."""


class JeuClos(RuntimeError):
    """Écriture refusée : le jeu est clos (J14)."""


# ── Modèles de ligne ─────────────────────────────────────────────────────────


class Deplacement(BaseModel):
    """Un trajet d'une personne entre deux activités localisées consécutives (J2)."""

    model_config = ConfigDict(extra="forbid")

    person_id: str
    activity_id: str  # activité de DESTINATION — la clé des décisions du contrôleur
    origine_activity_id: str
    ordinal: int  # rang du déplacement dans la journée de la personne (0, 1, …)
    purpose: str
    depart_24h: int  # heure programmée de départ, secondes depuis minuit
    depart_ts: int  # horodatage GAMA (mural) du départ pour `jour_simule`
    origine: Location
    destination: Location

    @property
    def cle(self) -> tuple[str, str]:
        return (self.person_id, self.activity_id)


class PropositionEnregistree(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = SOURCE_ENREGISTREE
    plan: dict  # TravelPlan.model_dump() — relu par TravelPlan.model_validate


class LigneJeu(Deplacement):
    propositions: list[PropositionEnregistree] = Field(default_factory=list)
    motif_absence: str | None = None

    def vers_propositions(self) -> list[Proposition]:
        return [
            Proposition(TravelPlan.model_validate(p.plan), p.source)
            for p in self.propositions
        ]


# ── Déplacements attendus (J2, E22) ──────────────────────────────────────────


def jour_base_ts(jour_simule: str) -> int:
    """Minuit du jour simulé, en horodatage GAMA (heure murale encodée comme UTC, cf. sim_clock)."""
    return calendar.timegm(datetime.strptime(jour_simule, "%Y-%m-%d").timetuple())


def _purpose_str(purpose) -> str:
    return str(getattr(purpose, "value", purpose) or "")


def deplacements_attendus(
    personnes: Sequence[Person], jour_simule: str
) -> list[Deplacement]:
    """Dérive de l'agenda de chaque personne ses déplacements de la journée — jamais saisi (J2).

    **La journée se referme** (ticket 045, A1). L'énumération passe par `paires_de_la_journee`,
    la même chaîne cyclique que le contrôleur de simulation : n activités valent n déplacements,
    le dernier étant le retour à la première activité. Auparavant cette fonction s'arrêtait à la
    dernière activité et rendait n − 1, si bien que le retour au domicile n'était jamais décidé —
    27 % de la journée sur la v1, et précisément la part où la contrainte de chaîne des véhicules
    contraint le plus le choix.

    Même règle d'heure que le contrôleur : départ à `scheduled_start_time` (sinon `end_time`) de
    l'activité de destination, résolu sur le jour simulé ; une heure déjà passée quand la personne
    arrive à l'activité précédente bascule au lendemain ; un départ de week-end est reporté au lundi
    quand `agent.no_weekend_departures` l'exige. Pour la fermeture, cette règle désigne le même
    instant que « fin de la dernière activité » : les populations scellées encodent le bouclage
    (`scheduled_start_time` de la première activité == `end_time` de la dernière, sans écart sur
    les 1 894 personnes des cohortes v1 et v5). Une activité sans localisation n'est ni origine ni
    destination.
    """
    base = jour_base_ts(jour_simule)
    attendus: list[Deplacement] = []
    for personne in personnes:
        for ordinal, (precedente, act) in enumerate(
            paires_de_la_journee(personne.identity.activities or [])
        ):
            cible_24h = (
                act.scheduled_start_time
                if act.scheduled_start_time is not None
                else act.end_time
            )
            maintenant = base + int(precedente.start_time)
            depart = to_timestamp_based_on_day(int(cible_24h), maintenant)
            if depart < maintenant:
                depart += 86400
            if settings.agent.no_weekend_departures:
                depart = shift_weekend_departure_to_monday(depart)
            attendus.append(
                Deplacement(
                    person_id=personne.person_id,
                    activity_id=act.id,
                    origine_activity_id=precedente.id,
                    ordinal=ordinal,
                    purpose=_purpose_str(act.purpose),
                    depart_24h=int(cible_24h) % 86400,
                    depart_ts=int(depart),
                    origine=precedente.location,
                    destination=act.location,
                )
            )
    return attendus


# ── Dépendances (J9, J10) ────────────────────────────────────────────────────


def _racine_depot() -> Path:
    # Ancre plutôt que compte de crans — cf. `experiences.chemins` (ticket 039).
    from experiences.chemins import racine_depot

    return racine_depot()


# État du dépôt transmis par l'HÔTE au conteneur (R7). `git` n'est pas installé dans l'image
# `controller`, si bien que `_git` y rendait toujours `None` : les 36 exécutions de la
# plateforme portent `empreintes.depot = {commit: null, arbre_propre: null}` et aucune ne peut
# être rattachée à un état du code. Le Makefile renseigne ces deux variables au lancement.
ENV_COMMIT = "EXP_DEPOT_COMMIT"
ENV_ARBRE_PROPRE = "EXP_DEPOT_ARBRE_PROPRE"


def etat_depot() -> tuple[str | None, bool | None]:
    """(commit, arbre propre) — depuis l'environnement s'il le porte, sinon depuis `git`.

    L'environnement d'abord : c'est le seul canal disponible dans le conteneur, et quand il
    est renseigné c'est que l'hôte a mesuré l'état du dépôt au moment du lancement, ce qui
    est précisément la question. `git` reste le repli pour un lancement direct sur l'hôte.

    Ni l'un ni l'autre ne devine : une valeur absente vaut `None` et se lit comme « non
    vérifiable », jamais comme « propre ».
    """
    commit = (os.getenv(ENV_COMMIT) or "").strip() or None
    brut = (os.getenv(ENV_ARBRE_PROPRE) or "").strip().lower()
    propre = {"1": True, "true": True, "oui": True, "0": False, "false": False, "non": False}.get(brut)
    if commit is not None:
        return commit, propre
    statut = _git("status", "--porcelain", "--untracked-files=no")
    return _git("rev-parse", "HEAD"), ((statut == "") if statut is not None else None)


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=_racine_depot(),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _cle_graphe_osmnx() -> str | None:
    """Clé du graphe OSMnx réellement servi, ou `None` si le module de routage est absent.

    Import différé et tolérant : `dependances_courantes` doit rester appelable sur un hôte
    sans la chaîne de routage complète (tests, outillage). Mais l'indisponibilité se
    journalise — un `None` silencieux est exactement le défaut qu'on corrige ici.
    """
    try:
        from trip_helper.osmnx_direct import graph_key

        return graph_key()
    except Exception as e:  # noqa: BLE001 — une dépendance non lisible se dit, elle ne s'invente pas
        logger.warning(
            f"[jeu] clé du graphe OSMnx non lisible ({e}) : la dépendance sera enregistrée "
            f"comme non vérifiable, et un changement de graphe ne périmera pas ce jeu."
        )
        return None


def chemin_graphe_otp(dossier_flux: Path) -> Path | None:
    """Le `graph.obj` qu'OTP charge réellement, ou `None` s'il n'y en a pas.

    OTP est lancé avec `--load /var/otp/toulouse`, où `data/gtfs` est monté : le graphe est
    donc à la RACINE de ce dossier, pas dans le sous-dossier d'un flux. Chercher sous
    `settings.gtfs.gtfs_file` — qui désigne le flux Tisséo — tombait sur un homonyme périmé :
    84,3 Mo du 4 septembre à la racine, 79,3 Mo du 19 mai dans le flux, deux empreintes
    différentes, et le manifeste nommait la mauvaise (constaté le 2026-09-11).

    La péremption (J10) ne pouvait donc jamais voir une reconstruction du graphe en service.
    C'est aussi plus complet de surveiller celui-ci : il embarque les TROIS flux — Tisséo, liO,
    TER — et le fond OSM, quand les empreintes de fichiers texte ne couvrent que Tisséo.

    Le dossier du flux reste un repli, pour un dépôt organisé autrement. Une absence totale se
    journalise : rendre `None` en silence est indistinguable d'un graphe inchangé.
    """
    dossier_flux = Path(dossier_flux)
    for candidat in (dossier_flux.parent / _FICHIER_GRAPHE_OTP, dossier_flux / _FICHIER_GRAPHE_OTP):
        if candidat.is_file():
            return candidat
    logger.warning(
        f"[jeu] {_FICHIER_GRAPHE_OTP} introuvable (ni {dossier_flux.parent}, ni {dossier_flux}) : "
        f"la dépendance sera enregistrée comme non vérifiable, et une reconstruction du graphe "
        f"ne périmera pas ce jeu."
    )
    return None


def _sha_si_present(chemin: Path) -> str | None:
    return sha256_fichier(chemin) if chemin.is_file() else None


def dependances_courantes(
    dossier_gtfs: Path | None = None, dossier_config: Path | None = None
) -> dict:
    """Ce dont dépendent les propositions : données de réseau, graphe, règles de routage, dépôt.

    Une dépendance introuvable vaut `None` — enregistrée telle quelle, jamais inventée ; la
    comparaison (`perime`) la range alors dans « non vérifiable ».
    """
    gtfs = Path(dossier_gtfs) if dossier_gtfs else Path(settings.gtfs.gtfs_file)
    config = (
        Path(dossier_config)
        if dossier_config
        else Path(__file__).resolve().parents[1] / "config"
    )
    commit, arbre_propre = etat_depot()
    if commit is None:
        logger.warning(
            "[jeu] état du dépôt non vérifiable : ni "
            f"${ENV_COMMIT} ni `git` ne répondent. La mesure ne pourra pas être rattachée "
            "à un état du code (ticket 045, A4)."
        )
    return {
        "commit": commit,
        "arbre_propre": arbre_propre,
        "gtfs": {nom: _sha_si_present(gtfs / nom) for nom in _FICHIERS_GTFS},
        # Le graphe QU'OTP CHARGE, pas un homonyme du dossier de flux (ticket 045).
        "otp_graph_sha256": (
            _sha_si_present(chemin) if (chemin := chemin_graphe_otp(gtfs)) else None
        ),
        # La clé EFFECTIVE, pas le réglage brut (R8). `settings.gtfs.osmnx_graph_key` vaut
        # `None` dans le cas courant — le graphe servi est alors celui du polygone des 453
        # communes — et le manifeste enregistrait donc « rien » précisément quand tout allait
        # bien. Une dépendance non enregistrée ne se compare pas : la péremption d'un jeu ne
        # pouvait pas voir un changement de graphe.
        "osmnx_graph_key": _cle_graphe_osmnx(),
        "config": {nom: _sha_si_present(config / nom) for nom in _FICHIERS_CONFIG},
    }


def _aplatir(d: dict, prefixe: str = "") -> dict[str, object]:
    plat: dict[str, object] = {}
    for k, v in (d or {}).items():
        cle = f"{prefixe}/{k}" if prefixe else str(k)
        if isinstance(v, dict):
            plat.update(_aplatir(v, cle))
        else:
            plat[cle] = v
    return plat


def comparer_dependances(
    enregistrees: dict, courantes: dict
) -> tuple[list[str], list[str]]:
    """(dépendances qui diffèrent, dépendances non vérifiables). `arbre_propre` et `commit` sont informatifs (audit trail)."""
    a, b = _aplatir(enregistrees), _aplatir(courantes)
    differentes, non_verifiables = [], []
    for cle in sorted(set(a) | set(b)):
        if cle in ("arbre_propre", "commit"):
            continue
        va, vb = a.get(cle), b.get(cle)
        if va is None or vb is None:
            if va is not None or vb is not None:
                non_verifiables.append(cle)
        elif va != vb:
            differentes.append(cle)
    return differentes, non_verifiables


# ── Lecture / écriture des lignes ────────────────────────────────────────────


def _lire_lignes(
    chemin: Path, *, tolerer_troncature: bool
) -> tuple[list[LigneJeu], int]:
    """Lignes valides + octets de la dernière ligne complète (pour tronquer une ligne à moitié écrite).

    Une ligne malformée est une erreur qui nomme sa position (J13) — sauf, en préparation, la
    dernière ligne d'un fichier interrompu en cours d'écriture, écartée avec un WARNING (J11).
    """
    lignes: list[LigneJeu] = []
    if not chemin.exists():
        return lignes, 0
    octets_valides = 0
    with open(chemin, "rb") as f:
        brut = f.read()
    for numero, ligne in enumerate(brut.split(b"\n"), start=1):
        if not ligne.strip():
            octets_valides += len(ligne) + 1
            continue
        try:
            lignes.append(LigneJeu.model_validate(json.loads(ligne.decode("utf-8"))))
        except (
            ValueError,
            ValidationError,
        ) as e:  # json.JSONDecodeError est un ValueError
            derniere = octets_valides + len(ligne) >= len(brut.rstrip(b"\n"))
            if tolerer_troncature and derniere:
                logger.warning(
                    f"[jeu] Dernière ligne de {chemin.name} tronquée ou malformée (ligne {numero}) — écartée, elle sera recalculée"
                )
                return lignes, octets_valides
            raise JeuInvalide(
                f"{chemin.name} ligne {numero} : contenu malformé ({str(e).splitlines()[0][:120]})"
            ) from e
        octets_valides += len(ligne) + 1
    return lignes, min(octets_valides, len(brut))


def _ecrire_yaml_atomique(chemin: Path, contenu: dict) -> None:
    tmp = chemin.with_suffix(chemin.suffix + ".tmp")
    tmp.write_text(
        yaml.safe_dump(contenu, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    os.replace(tmp, chemin)


def _maintenant_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── Préparation ──────────────────────────────────────────────────────────────


class JeuEnPreparation:
    """Un jeu ouvert en écriture : append ligne par ligne, reprise, clôture (J11, J14, J15)."""

    def __init__(
        self,
        dossier: Path,
        manifest: dict,
        cles: set[tuple[str, str]],
        lignes: list[LigneJeu],
    ):
        self.dossier = Path(dossier)
        self.manifest = manifest
        self.cles = cles
        self._lignes = lignes
        self._fh = open(self.dossier / FICHIER_PROPOSITIONS, "ab")

    @classmethod
    def ouvrir(
        cls,
        dossier: str | Path,
        nom: str,
        population: InfoPopulation,
        jour_simule: str,
        *,
        heure_reference: str = HEURE_REFERENCE_DEPART,
        dependances: dict | None = None,
    ) -> JeuEnPreparation:
        dossier = Path(dossier)
        dossier.mkdir(parents=True, exist_ok=True)
        chemin_manifest = dossier / FICHIER_MANIFEST
        if chemin_manifest.exists():
            manifest = yaml.safe_load(chemin_manifest.read_text(encoding="utf-8")) or {}
            if manifest.get("clos"):
                raise JeuClos(
                    f"le jeu {manifest.get('nom')!r} est clos : corriger produit un NOUVEAU jeu (J14)"
                )
            if (manifest.get("population") or {}).get("sha256") != population.sha256:
                raise JeuInvalide(
                    f"le dossier {dossier} porte un jeu pour une autre population "
                    f"({(manifest.get('population') or {}).get('sha256', '?')[:12]}… ≠ {population.sha256[:12]}…)"
                )
        else:
            manifest = {
                "version": VERSION_JEU,
                "nom": nom,
                "cree_le": _maintenant_iso(),
                "clos": False,
                "clos_le": None,
                "population": population.as_dict(),
                "jour_simule": jour_simule,
                "heure_reference": heure_reference,
                "dependances": dependances
                if dependances is not None
                else dependances_courantes(),
            }
            _ecrire_yaml_atomique(chemin_manifest, manifest)
        lignes, octets = _lire_lignes(
            dossier / FICHIER_PROPOSITIONS, tolerer_troncature=True
        )
        chemin_lignes = dossier / FICHIER_PROPOSITIONS
        if chemin_lignes.exists() and octets < chemin_lignes.stat().st_size:
            with open(chemin_lignes, "r+b") as f:
                f.truncate(octets)
        return cls(dossier, manifest, {l.cle for l in lignes}, lignes)

    @property
    def nom(self) -> str:
        return str(self.manifest.get("nom"))

    def ecrire(self, ligne: LigneJeu) -> None:
        if self.manifest.get("clos"):
            raise JeuClos("jeu clos")
        if ligne.cle in self.cles:
            return
        self._fh.write(
            (
                json.dumps(ligne.model_dump(mode="json"), ensure_ascii=False) + "\n"
            ).encode("utf-8")
        )
        self._fh.flush()
        os.fsync(self._fh.fileno())
        self.cles.add(ligne.cle)
        self._lignes.append(ligne)

    def clore(self, attendus: Sequence[Deplacement], personnes_total: int) -> dict:
        """Fige le jeu : complétude, liste des sans-proposition, empreinte du contenu (J5, J7, J14)."""
        self._fh.close()
        cles_attendues = {d.cle for d in attendus}
        couvertes = [
            l for l in self._lignes if l.cle in cles_attendues and l.propositions
        ]
        sans = [
            l for l in self._lignes if l.cle in cles_attendues and not l.propositions
        ]
        self.manifest.update(
            {
                "clos": True,
                "clos_le": _maintenant_iso(),
                "attendus": {
                    "deplacements": len(cles_attendues),
                    "personnes_total": int(personnes_total),
                    "personnes_avec_deplacement": len({d.person_id for d in attendus}),
                },
                "couverts": {
                    "deplacements": len(couvertes),
                    "personnes": len({l.person_id for l in couvertes}),
                },
                "non_calcules": len(cles_attendues) - len(couvertes) - len(sans),
                "sans_proposition": [
                    {
                        "person_id": l.person_id,
                        "activity_id": l.activity_id,
                        "motif": l.motif_absence or MOTIF_AUCUNE_PROPOSITION,
                    }
                    for l in sans
                ],
                "propositions_sha256": sha256_fichier(
                    self.dossier / FICHIER_PROPOSITIONS
                ),
            }
        )
        _ecrire_yaml_atomique(self.dossier / FICHIER_MANIFEST, self.manifest)
        return self.manifest

    def fermer(self) -> None:
        if not self._fh.closed:
            self._fh.close()


async def preparer(
    prep: JeuEnPreparation,
    personnes: Sequence[Person],
    trip_helper,
    *,
    concurrence: int = 8,
    seuil_sans_proposition: float = 0.05,
    fabrique_locale: Callable[..., TravelPlan | None] | None = None,
    progression_s: float = 5.0,
) -> dict:
    """Calcule toutes les propositions des déplacements non encore enregistrés (J3, J11, J15).

    `trip_helper.get_itineraries(origin, destination, departure_time, include_car, include_bike,
    arrive_by)` est appelé **tous modes ouverts**, sans plafond. `fabrique_locale` (par défaut le
    car scolaire synthétique) ajoute les propositions produites sans moteur. Une erreur de moteur
    n'écrit rien : le déplacement reste à calculer à la prochaine reprise.
    """
    debut = time.monotonic()
    jour = str(prep.manifest["jour_simule"])
    attendus = deplacements_attendus(personnes, jour)
    restants = [d for d in attendus if d.cle not in prep.cles]
    par_personne = {p.person_id: p for p in personnes}
    activites = {
        (p.person_id, a.id): a for p in personnes for a in (p.identity.activities or [])
    }
    logger.info(
        f"[jeu] Préparation de {prep.nom!r} : {len(attendus)} déplacements attendus pour "
        f"{len(personnes)} personnes — {len(attendus) - len(restants)} déjà enregistrés, reste {len(restants)}"
    )
    if fabrique_locale is None:
        from trip_helper.school_bus import build_school_bus_option

        fabrique_locale = build_school_bus_option

    compteurs: Counter = Counter()
    sem = asyncio.Semaphore(max(1, concurrence))
    alarme_levee = False

    async def traiter(dep: Deplacement) -> None:
        nonlocal alarme_levee
        async with sem:
            props: list[PropositionEnregistree] = []
            motif: str | None = None
            if (
                abs(dep.origine.lat - dep.destination.lat) < 1e-9
                and abs(dep.origine.lon - dep.destination.lon) < 1e-9
            ):
                motif = MOTIF_ORIGINE_EGALE_DESTINATION
                compteurs["ignores_meme_lieu"] += 1
            else:
                try:
                    itineraires = await trip_helper.get_itineraries(
                        origin=dep.origine,
                        destination=dep.destination,
                        departure_time=dep.depart_ts,
                        include_car=True,
                        include_bike=True,
                        arrive_by=False,
                    )
                except Exception as e:  # noqa: BLE001 — journalisé avec de quoi agir, jamais enregistré
                    compteurs["erreurs"] += 1
                    logger.error(
                        f"[jeu] Erreur moteur pour {dep.person_id}/{dep.activity_id} "
                        f"({dep.origine.lat:.5f},{dep.origine.lon:.5f} → {dep.destination.lat:.5f},{dep.destination.lon:.5f} "
                        f"à {dep.depart_ts}) : {type(e).__name__}: {e}"
                    )
                    return
                for it in itineraires or []:
                    it.purpose = dep.purpose
                    it.start_location = dep.origine
                    it.end_location = dep.destination
                    props.append(
                        PropositionEnregistree(
                            source=SOURCE_ENREGISTREE, plan=it.model_dump()
                        )
                    )
                personne = par_personne.get(dep.person_id)
                activite = activites.get((dep.person_id, dep.activity_id))
                if personne is not None and activite is not None:
                    try:
                        locale = fabrique_locale(
                            person=personne,
                            from_location=dep.origine,
                            next_activity=activite,
                            timestamp=dep.depart_ts,
                            departure_time=dep.depart_ts,
                        )
                    except Exception as e:  # noqa: BLE001
                        locale = None
                        logger.warning(
                            f"[jeu] proposition locale impossible pour {dep.person_id}/{dep.activity_id} : {e}"
                        )
                    if locale is not None:
                        locale.purpose = dep.purpose
                        props.append(
                            PropositionEnregistree(
                                source=SOURCE_LOCALE, plan=locale.model_dump()
                            )
                        )
                        compteurs["locales"] += 1
                if not props:
                    motif = MOTIF_AUCUNE_PROPOSITION
            prep.ecrire(
                LigneJeu(**dep.model_dump(), propositions=props, motif_absence=motif)
            )
            compteurs["calcules"] += 1
            if not props:
                compteurs["sans_proposition"] += 1
                # L'alarme porte sur la SANTÉ DES MOTEURS, donc seules les vraies défaillances
                # y entrent : une fermeture sur place n'a pas d'itinéraire à calculer et ne dit
                # rien d'OTP ni d'OSMnx. Les compter ferait franchir le seuil de 5 % à chaque
                # préparation (5,5 % de fermetures sur place sur la cohorte v5), ce qui revient
                # à éteindre l'alarme en la faisant hurler tout le temps.
                if est_defaillance_moteur(motif):
                    compteurs["defaillances_moteur"] += 1
                    part = compteurs["defaillances_moteur"] / max(1, len(attendus))
                    if part > seuil_sans_proposition and not alarme_levee:
                        alarme_levee = True
                        logger.error(
                            f"[ALARME] Jeu {prep.nom!r} : {compteurs['defaillances_moteur']} déplacements sans "
                            f"proposition des moteurs sur {len(attendus)} attendus "
                            f"({100 * part:.1f} % > {100 * seuil_sans_proposition:.1f} %) — "
                            f"hors fermetures sur place, qui n'ont pas d'itinéraire à calculer"
                        )

    def ecrire_progression() -> None:
        faits = compteurs["calcules"] + compteurs["erreurs"]
        ecoule = time.monotonic() - debut
        debit = faits / ecoule if ecoule > 0 else 0.0
        reste = (len(restants) - faits) / debit if debit > 0 else None
        contenu = {
            "jeu": prep.nom,
            "faits": faits + (len(attendus) - len(restants)),
            "total": len(attendus),
            "restants_au_depart": len(restants),
            "pourcent": round(
                100 * (faits + len(attendus) - len(restants)) / len(attendus), 1
            )
            if attendus
            else None,
            "sans_proposition": int(compteurs["sans_proposition"]),
            "erreurs": int(compteurs["erreurs"]),
            "ecoule_s": round(ecoule, 1),
            "reste_s": (round(reste) if reste is not None else None),
            "maj": _maintenant_iso(),
        }
        try:
            tmp = prep.dossier / "progression.json.tmp"
            tmp.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, prep.dossier / "progression.json")
        except OSError as e:
            logger.warning(f"[jeu] progression.json non écrit : {e}")

    async def progression() -> None:
        while True:
            await asyncio.sleep(progression_s)
            faits = compteurs["calcules"] + compteurs["erreurs"]
            ecoule = time.monotonic() - debut
            debit = faits / ecoule if ecoule > 0 else 0.0
            reste = (len(restants) - faits) / debit if debit > 0 else float("nan")
            logger.info(
                f"[jeu] {faits}/{len(restants)} déplacements traités · {ecoule:.0f} s écoulées · reste ≈ {reste:.0f} s"
            )
            ecrire_progression()

    ecrire_progression()
    suivi = asyncio.create_task(progression())
    try:
        await asyncio.gather(*(traiter(d) for d in restants))
    finally:
        suivi.cancel()
        ecrire_progression()
    duree = time.monotonic() - debut
    compteurs["restants_apres"] = len(attendus) - len(
        prep.cles & {d.cle for d in attendus}
    )
    if compteurs["sans_proposition"]:
        # Deux natures, deux phrases : une fermeture sur place est ATTENDUE (elle n'a pas
        # d'itinéraire), une défaillance de moteur ne l'est pas. Les additionner sous
        # « sans AUCUNE proposition des moteurs » accusait les moteurs d'un fait de la journée.
        logger.warning(
            f"[jeu] {compteurs['sans_proposition']} déplacement(s) inexploitables sur {len(attendus)} "
            f"({100 * compteurs['sans_proposition'] / max(1, len(attendus)):.1f} %) — dont "
            f"{compteurs['ignores_meme_lieu']} fermeture(s) sur place (origine = destination, aucun "
            f"itinéraire à calculer) et {compteurs['defaillances_moteur']} sans proposition des moteurs. "
            f"Tous exclus des attendus des expériences (décision du 2026-09-06) ; détail : `consulter-jeu`"
        )
    niveau = logger.error if compteurs["erreurs"] else logger.info
    niveau(
        f"[jeu] {'Préparation terminée' if not compteurs['erreurs'] else 'Préparation INCOMPLÈTE'} pour {prep.nom!r} en {duree:.1f} s — "
        f"calculés {compteurs['calcules']}, sans proposition {compteurs['sans_proposition']}, "
        f"même lieu {compteurs['ignores_meme_lieu']}, locales {compteurs['locales']}, erreurs {compteurs['erreurs']}, "
        f"reste {compteurs['restants_apres']}"
    )
    compteurs["duree_s"] = round(duree, 3)
    return dict(compteurs)


# ── Chargement ───────────────────────────────────────────────────────────────


class Jeu:
    """Un jeu clos (ou en cours), lu depuis le disque, en lecture seule (J6, J7, J12)."""

    def __init__(self, dossier: Path, manifest: dict, lignes: list[LigneJeu]):
        self.dossier = Path(dossier)
        self.manifest = manifest
        self._index: dict[tuple[str, str], LigneJeu] = {}
        for l in lignes:
            if l.cle in self._index:
                logger.warning(
                    f"[jeu] clé en double {l.cle} dans {self.dossier.name} — première occurrence gardée"
                )
                continue
            self._index[l.cle] = l
        self._par_personne: dict[str, list[LigneJeu]] = {}
        for l in self._index.values():
            self._par_personne.setdefault(l.person_id, []).append(l)
        for lst in self._par_personne.values():
            lst.sort(key=lambda x: (x.depart_ts, x.ordinal))

    @classmethod
    def charger(
        cls,
        dossier: str | Path,
        *,
        verifier: bool = True,
        archive_confirmee: str | None = None,
    ) -> Jeu:
        """Ouvre un jeu scellé. Point de passage UNIQUE de toute lecture de jeu.

        `archive_confirmee` (ticket 074, A-4) porte le MOTIF d'une lecture en archive froide —
        la garde de comparabilité D-7, par exemple, qui compare les chaînes d'activités de la
        v6 à celles de la v5 gelée. Sans motif, un jeu rangé sous `archive/` est refusé : c'est
        ici que le refus se pose, parce que c'est ici que tout le monde passe.
        """
        dossier = Path(dossier)
        froid.verifier(
            dossier,
            archive_confirmee,
            quoi="un jeu scellé",
            comment_lever="passer `archive_confirmee=\"<motif>\"` à `Jeu.charger`",
        )
        chemin_manifest = dossier / FICHIER_MANIFEST
        if not chemin_manifest.is_file():
            raise JeuInvalide(f"aucun {FICHIER_MANIFEST} dans {dossier}")
        try:
            manifest = yaml.safe_load(chemin_manifest.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise JeuInvalide(f"{FICHIER_MANIFEST} illisible : {e}") from e
        if manifest.get("version") != VERSION_JEU:
            raise JeuInvalide(
                f"version de jeu inconnue : {manifest.get('version')!r} (attendu {VERSION_JEU!r})"
            )
        if (
            not isinstance(manifest.get("dependances"), dict)
            or not manifest["dependances"]
        ):
            raise JeuInvalide("jeu sans bloc `dependances` : refusé (J9)")
        if not (manifest.get("population") or {}).get("sha256"):
            raise JeuInvalide("jeu sans empreinte de population : refusé (J1)")
        chemin_lignes = dossier / FICHIER_PROPOSITIONS
        if manifest.get("clos") and verifier:
            attendu = manifest.get("propositions_sha256")
            reel = sha256_fichier(chemin_lignes) if chemin_lignes.exists() else None
            if not attendu or attendu != reel:
                raise JeuInvalide(
                    f"jeu {manifest.get('nom')!r} altéré : empreinte {str(reel)[:12]}… ≠ MANIFEST {str(attendu)[:12]}… (J12)"
                )
        lignes, _ = _lire_lignes(
            chemin_lignes, tolerer_troncature=not manifest.get("clos")
        )
        return cls(dossier, manifest, lignes)

    # ── identité ──
    @property
    def nom(self) -> str:
        return str(self.manifest.get("nom"))

    @property
    def empreinte(self) -> str | None:
        return self.manifest.get("propositions_sha256")

    @property
    def clos(self) -> bool:
        return bool(self.manifest.get("clos"))

    @property
    def population(self) -> dict:
        return dict(self.manifest.get("population") or {})

    @property
    def jour_simule(self) -> str:
        return str(self.manifest.get("jour_simule"))

    def jours_equivalents(self) -> list[str]:
        """Jours (AAAA-MM-JJ) dont l'offre de transport a été mesurée identique à celle du jeu.

        Déclarés par `verifier-jours --declarer` dans `EQUIVALENCES.yaml`, à côté du MANIFEST (qui
        reste immuable, J14). Sans ce fichier, aucun autre jour n'est réputé équivalent : la
        simulation recalcule alors les transports collectifs pour tout autre jour (décision 18).
        """
        p = self.dossier / FICHIER_EQUIVALENCES
        if not p.is_file():
            return []
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return []
        return [str(j) for j in (data.get("jours_equivalents") or [])]

    def _equivalences(self) -> dict:
        p = self.dossier / FICHIER_EQUIVALENCES
        if not p.is_file():
            return {}
        try:
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return {}

    def declarer_jour_equivalent(self, jour: str, mesure: dict) -> None:
        """Le jour entier est équivalent (offre TC mesurée identique sur échantillon, méthode « moteurs »)."""
        data = self._equivalences()
        jours = [str(j) for j in (data.get("jours_equivalents") or [])]
        if jour not in jours:
            jours.append(jour)
        data["jours_equivalents"] = sorted(jours)
        data.setdefault("mesures", {})[jour] = mesure
        _ecrire_yaml_atomique(self.dossier / FICHIER_EQUIVALENCES, data)

    def declarer_verification_jour(self, jour: str, resultat: dict) -> None:
        """Validité PAR DÉPLACEMENT pour `jour` (méthode « gtfs_existence ») : ce qui manque est nommé.

        Si tout est valide, le jour devient aussi équivalent ; sinon seuls les déplacements
        listés `invalides` verront leurs transports collectifs recalculés ce jour-là.
        """
        data = self._equivalences()
        data.setdefault("par_jour", {})[jour] = {
            k: v for k, v in resultat.items() if k not in ("invalides_detail",)
        }
        if resultat.get("equivalent"):
            jours = [str(j) for j in (data.get("jours_equivalents") or [])]
            if jour not in jours:
                jours.append(jour)
            data["jours_equivalents"] = sorted(jours)
        _ecrire_yaml_atomique(self.dossier / FICHIER_EQUIVALENCES, data)

    def ligne_valide_le(self, jour: str, cle: tuple[str, str]) -> bool | None:
        """Les propositions TC de ce déplacement valent-elles pour `jour` ?

        True : jour du jeu, jour déclaré équivalent, ou déplacement vérifié valide ce jour ;
        False : vérifié et une course manque ; None : rien n'a été vérifié pour ce jour.
        """
        if jour == self.jour_simule or jour in self.jours_equivalents():
            return True
        par_jour = (self._equivalences().get("par_jour") or {}).get(jour)
        if not par_jour:
            return None
        return f"{cle[0]}|{cle[1]}" not in set(par_jour.get("invalides_cles") or [])

    def verifier_population(self, info: InfoPopulation) -> str | None:
        """Message de refus si la population n'est pas celle du jeu (G1, E6), sinon None."""
        attendu = self.population.get("sha256")
        if attendu != info.sha256:
            return (
                f"le jeu {self.nom!r} a été préparé pour la population {self.population.get('nom')!r} "
                f"(empreinte {str(attendu)[:12]}…), pas pour {info.nom!r} (empreinte {info.sha256[:12]}…)"
            )
        return None

    # ── lecture ──
    def ligne(self, person_id: str, activity_id: str) -> LigneJeu | None:
        return self._index.get((person_id, activity_id))

    def propositions(
        self, person_id: str, activity_id: str
    ) -> list[Proposition] | None:
        """Propositions brutes du déplacement — `None` si le jeu ne le couvre pas, `[]` si aucune."""
        l = self._index.get((person_id, activity_id))
        return None if l is None else l.vers_propositions()

    def couvre(self, person_id: str, activity_id: str) -> bool:
        l = self._index.get((person_id, activity_id))
        return l is not None and bool(l.propositions)

    def consulter(self, person_id: str) -> list[LigneJeu]:
        return list(self._par_personne.get(person_id, []))

    def personnes(self) -> list[str]:
        return sorted(self._par_personne)

    def __len__(self) -> int:
        return len(self._index)

    # ── complétude (J7, J8) ──
    def couverture(self) -> dict:
        attendus = self.manifest.get("attendus") or {}
        couverts = self.manifest.get("couverts") or {}
        n_attendus = int(attendus.get("deplacements") or 0)
        n_couverts = int(
            couverts.get("deplacements")
            or sum(1 for l in self._index.values() if l.propositions)
        )
        # Un déplacement dont l'origine est sa destination ne PEUT pas être couvert : il n'y
        # a pas d'itinéraire à calculer. Le laisser au dénominateur rendait `est_complet`
        # inatteignable dès que la journée se referme sur le domicile, c'est-à-dire toujours
        # (ticket 045). Le compte se relit sur les motifs du MANIFEST, donc les jeux déjà
        # scellés se lisent sans être retouchés.
        n_hors_portee = sum(
            1
            for s in (self.manifest.get("sans_proposition") or [])
            if not est_defaillance_moteur(s.get("motif"))
        )
        n_exploitables = max(0, n_attendus - n_hors_portee)
        return {
            "deplacements_attendus": n_attendus,
            "deplacements_exploitables": n_exploitables,
            "deplacements_couverts": n_couverts,
            "personnes_total": int(attendus.get("personnes_total") or 0),
            "personnes_avec_deplacement": int(
                attendus.get("personnes_avec_deplacement") or 0
            ),
            "personnes_couvertes": int(
                couverts.get("personnes")
                or len({l.person_id for l in self._index.values() if l.propositions})
            ),
            "sans_proposition": list(self.manifest.get("sans_proposition") or []),
            "non_calcules": int(self.manifest.get("non_calcules") or 0),
            # Le taux se mesure sur ce qui POUVAIT être couvert : sinon un jeu parfait
            # plafonne sous 100 % du seul fait que les journées reviennent au domicile.
            "taux": (n_couverts / n_exploitables) if n_exploitables else None,
        }

    @property
    def est_complet(self) -> bool:
        """Tout ce qui POUVAIT être couvert l'est.

        Le dénominateur est `deplacements_exploitables`, pas les attendus bruts : une
        fermeture sur place n'a pas d'itinéraire, l'exiger rendrait la complétude
        inatteignable pour toute population dont les journées reviennent au domicile.
        """
        c = self.couverture()
        return (
            bool(c["deplacements_exploitables"])
            and c["deplacements_couverts"] == c["deplacements_exploitables"]
        )

    def inexploitables(self, attendus) -> set[tuple[str, str]]:
        """Les déplacements que ce jeu couvre mais SANS aucune proposition (R9).

        Dérivé du jeu, donc connu à l'ouverture d'une exécution et identique d'une
        exécution à l'autre. C'est la correction de l'alerte A3 : le dénominateur était
        jusqu'ici accumulé au fil des décisions, si bien qu'une exécution interrompue
        n'annonçait pas le même nombre qu'une exécution complète sur le même couple
        (population, jeu), et que deux colonnes cessaient d'être comparables.

        Un déplacement ABSENT du jeu n'en fait pas partie : c'est un trou de préparation
        (`non_couvert`), une autre catégorie, qui ne doit pas varier avec celle-ci.
        """
        hors = set()
        for d in attendus:
            ligne = self._index.get((d.person_id, d.activity_id))
            if ligne is not None and not ligne.propositions:
                hors.add((d.person_id, d.activity_id))
        return hors

    def resume(self) -> str:
        c = self.couverture()
        taux = (
            f"{100 * c['taux']:.1f} %".replace(".", ",")
            if c["taux"] is not None
            else "n/a"
        )
        etat = "clos" if self.clos else "EN PRÉPARATION"
        pop = self.population
        lignes = [
            f"Jeu {self.nom!r} — {etat}, empreinte {str(self.empreinte)[:12] if self.empreinte else 'non figée'}…",
            f"  population : {pop.get('nom')} ({'scellée' if pop.get('scellee') else 'non scellée'}, {str(pop.get('sha256'))[:12]}…)",
            f"  jour simulé : {self.jour_simule} · heure de référence : {self.manifest.get('heure_reference')}",
            f"  couverture : {c['deplacements_couverts']} / {c['deplacements_attendus']} déplacements ({taux}) · "
            f"{c['personnes_couvertes']} / {c['personnes_avec_deplacement']} personnes avec déplacement "
            f"(population : {c['personnes_total']})",
        ]
        if c["sans_proposition"]:
            motifs = Counter(s.get("motif") for s in c["sans_proposition"])
            lignes.append(
                f"  INEXPLOITABLES (aucune proposition des moteurs, exclus des attendus d'une expérience) : "
                f"{len(c['sans_proposition'])} — "
                + ", ".join(f"{m} × {n}" for m, n in motifs.most_common())
            )
        if c["non_calcules"]:
            lignes.append(
                f"  NON CALCULÉS : {c['non_calcules']} (préparation interrompue : reprendre)"
            )
        return "\n".join(lignes)


def _signature_tc(propositions: Sequence[Proposition]) -> list[tuple]:
    """Ce qui distingue une offre de transports collectifs d'une autre : lignes empruntées, durée à la minute."""
    from urban_mobility_agents.candidats import _primary_mode

    return sorted(
        (
            p.plan.get_code() if p.plan.legs else p.plan.id,
            p.mode,
            (p.plan.duration or 0) // 60,
        )
        for p in propositions
        if _primary_mode(p.plan) == "transit"
    )


async def comparer_offre_jour(
    jeu: Jeu,
    trip_helper,
    jour: str,
    *,
    echantillon: int = 100,
    graine: int = 42,
    concurrence: int = 8,
) -> dict:
    """Décision 18 — l'offre TC de `jour` est-elle celle du jour du jeu ? MESURÉ, jamais supposé.

    Tire `echantillon` déplacements couverts (graine déclarée), demande aux moteurs les propositions
    à la même heure le jour `jour`, et compare les transports collectifs (lignes, durées à la minute)
    à celles enregistrées. Rend le détail ; c'est l'appelant qui décide de déclarer l'équivalence.
    """
    import random as _random
    from datetime import date as _date

    decalage = (
        _date.fromisoformat(jour) - _date.fromisoformat(jeu.jour_simule)
    ).days * 86400
    lignes = [
        l for l in jeu._index.values() if any(_signature_tc(l.vers_propositions()))
    ]
    rng = _random.Random(graine)
    tirees = rng.sample(lignes, min(echantillon, len(lignes))) if lignes else []
    sem = asyncio.Semaphore(max(1, concurrence))
    resultats: list[dict] = []

    async def un(ligne: LigneJeu) -> None:
        async with sem:
            avant = _signature_tc(ligne.vers_propositions())
            try:
                its = await trip_helper.get_itineraries(
                    origin=ligne.origine,
                    destination=ligne.destination,
                    departure_time=ligne.depart_ts + decalage,
                    include_car=True,
                    include_bike=True,
                    arrive_by=False,
                )
            except Exception as e:  # noqa: BLE001
                resultats.append(
                    {"cle": list(ligne.cle), "erreur": f"{type(e).__name__}: {e}"}
                )
                return
            apres = _signature_tc(
                [Proposition(it, SOURCE_ENREGISTREE) for it in its or []]
            )
            resultats.append(
                {
                    "cle": list(ligne.cle),
                    "identique": avant == apres,
                    "avant": avant,
                    "apres": apres,
                }
            )

    await asyncio.gather(*(un(l) for l in tirees))
    identiques = sum(1 for r in resultats if r.get("identique"))
    erreurs = sum(1 for r in resultats if "erreur" in r)
    compares = len(resultats) - erreurs
    return {
        "jeu": jeu.nom,
        "jour_jeu": jeu.jour_simule,
        "jour": jour,
        "echantillon": len(tirees),
        "graine": graine,
        "compares": compares,
        "identiques": identiques,
        "differents": compares - identiques,
        "erreurs": erreurs,
        "part_identique": (identiques / compares) if compares else None,
        "equivalent": bool(compares) and identiques == compares and erreurs == 0,
        "mesure_le": _maintenant_iso(),
        "differences": [r for r in resultats if r.get("identique") is False][:20],
    }


def perime(jeu: Jeu, courantes: dict | None = None) -> tuple[list[str], list[str]]:
    """J10 — (dépendances changées depuis la préparation, dépendances non vérifiables)."""
    return comparer_dependances(
        jeu.manifest.get("dependances") or {},
        courantes if courantes is not None else dependances_courantes(),
    )


__all__ = [
    "FICHIER_EQUIVALENCES",
    "FICHIER_MANIFEST",
    "FICHIER_PROPOSITIONS",
    "HEURE_REFERENCE_DEPART",
    "MOTIF_AUCUNE_PROPOSITION",
    "MOTIF_ORIGINE_EGALE_DESTINATION",
    "VERSION_JEU",
    "Deplacement",
    "Jeu",
    "JeuClos",
    "JeuEnPreparation",
    "JeuInvalide",
    "LigneJeu",
    "PropositionEnregistree",
    "comparer_dependances",
    "comparer_offre_jour",
    "dependances_courantes",
    "deplacements_attendus",
    "jour_base_ts",
    "perime",
    "preparer",
]
