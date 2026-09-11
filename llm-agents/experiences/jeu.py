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
import hashlib
import json
import os
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Sequence

import yaml
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from experiences.decision import SOURCE_ENREGISTREE, SOURCE_LOCALE, Proposition
from experiences.population import InfoPopulation, sha256_fichier
from helper import shift_weekend_departure_to_monday, to_timestamp_based_on_day
from models import Activity, Location, Person, TravelPlan
from settings import settings

VERSION_JEU = "jeu1"
FICHIER_MANIFEST = "MANIFEST.yaml"
FICHIER_PROPOSITIONS = "propositions.jsonl"
FICHIER_EQUIVALENCES = "EQUIVALENCES.yaml"    # jours dont l'offre TC a été MESURÉE identique à celle du jeu
HEURE_REFERENCE_DEPART = "depart_programme"

MOTIF_ORIGINE_EGALE_DESTINATION = "origine_egale_destination"
MOTIF_AUCUNE_PROPOSITION = "aucune_proposition"

# Fichiers dont l'empreinte entre dans les dépendances (J9). Relatifs au dossier GTFS en
# service pour les feeds (et le graphe OTP qui y vit), à `llm-agents/config` pour les règles.
_FICHIERS_GTFS = ("feed_info.txt", "calendar.txt", "calendar_dates.txt", "routes.txt", "stops.txt", "trips.txt", "stop_times.txt")
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
    activity_id: str                 # activité de DESTINATION — la clé des décisions du contrôleur
    origine_activity_id: str
    ordinal: int                     # rang du déplacement dans la journée de la personne (0, 1, …)
    purpose: str
    depart_24h: int                  # heure programmée de départ, secondes depuis minuit
    depart_ts: int                   # horodatage GAMA (mural) du départ pour `jour_simule`
    origine: Location
    destination: Location

    @property
    def cle(self) -> tuple[str, str]:
        return (self.person_id, self.activity_id)


class PropositionEnregistree(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = SOURCE_ENREGISTREE
    plan: dict                       # TravelPlan.model_dump() — relu par TravelPlan.model_validate


class LigneJeu(Deplacement):
    propositions: list[PropositionEnregistree] = Field(default_factory=list)
    motif_absence: Optional[str] = None

    def vers_propositions(self) -> list[Proposition]:
        return [Proposition(TravelPlan.model_validate(p.plan), p.source) for p in self.propositions]


# ── Déplacements attendus (J2, E22) ──────────────────────────────────────────

def jour_base_ts(jour_simule: str) -> int:
    """Minuit du jour simulé, en horodatage GAMA (heure murale encodée comme UTC, cf. sim_clock)."""
    return calendar.timegm(datetime.strptime(jour_simule, "%Y-%m-%d").timetuple())


def _purpose_str(purpose) -> str:
    return str(getattr(purpose, "value", purpose) or "")


def deplacements_attendus(personnes: Sequence[Person], jour_simule: str) -> list[Deplacement]:
    """Dérive de l'agenda de chaque personne ses déplacements de la journée — jamais saisi (J2).

    Même règle d'heure que le contrôleur : départ à `scheduled_start_time` (sinon `end_time`) de
    l'activité de destination, résolu sur le jour simulé ; une heure déjà passée quand la personne
    arrive à l'activité précédente bascule au lendemain ; un départ de week-end est reporté au lundi
    quand `agent.no_weekend_departures` l'exige. Une activité sans localisation n'est ni origine ni
    destination.
    """
    base = jour_base_ts(jour_simule)
    attendus: list[Deplacement] = []
    for personne in personnes:
        precedente: Optional[Activity] = None
        ordinal = 0
        for act in personne.identity.activities or []:
            if act.location is None:
                continue
            if precedente is None:
                precedente = act
                continue
            cible_24h = act.scheduled_start_time if act.scheduled_start_time is not None else act.end_time
            maintenant = base + int(precedente.start_time)
            depart = to_timestamp_based_on_day(int(cible_24h), maintenant)
            if depart < maintenant:
                depart += 86400
            if settings.agent.no_weekend_departures:
                depart = shift_weekend_departure_to_monday(depart)
            attendus.append(Deplacement(
                person_id=personne.person_id, activity_id=act.id, origine_activity_id=precedente.id,
                ordinal=ordinal, purpose=_purpose_str(act.purpose), depart_24h=int(cible_24h) % 86400,
                depart_ts=int(depart), origine=precedente.location, destination=act.location,
            ))
            ordinal += 1
            precedente = act
    return attendus


# ── Dépendances (J9, J10) ────────────────────────────────────────────────────

def _racine_depot() -> Path:
    return Path(__file__).resolve().parents[2]


def _git(*args: str) -> Optional[str]:
    try:
        out = subprocess.run(["git", *args], cwd=_racine_depot(), capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _sha_si_present(chemin: Path) -> Optional[str]:
    return sha256_fichier(chemin) if chemin.is_file() else None


def dependances_courantes(dossier_gtfs: Optional[Path] = None, dossier_config: Optional[Path] = None) -> dict:
    """Ce dont dépendent les propositions : données de réseau, graphe, règles de routage, dépôt.

    Une dépendance introuvable vaut `None` — enregistrée telle quelle, jamais inventée ; la
    comparaison (`perime`) la range alors dans « non vérifiable ».
    """
    gtfs = Path(dossier_gtfs) if dossier_gtfs else Path(settings.gtfs.gtfs_file)
    config = Path(dossier_config) if dossier_config else Path(__file__).resolve().parents[1] / "config"
    statut = _git("status", "--porcelain", "--untracked-files=no")
    return {
        "commit": _git("rev-parse", "HEAD"),
        "arbre_propre": (statut == "") if statut is not None else None,
        "gtfs": {nom: _sha_si_present(gtfs / nom) for nom in _FICHIERS_GTFS},
        "otp_graph_sha256": _sha_si_present(gtfs / _FICHIER_GRAPHE_OTP),
        "osmnx_graph_key": settings.gtfs.osmnx_graph_key,
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


def comparer_dependances(enregistrees: dict, courantes: dict) -> tuple[list[str], list[str]]:
    """(dépendances qui diffèrent, dépendances non vérifiables). `arbre_propre` n'est qu'informatif."""
    a, b = _aplatir(enregistrees), _aplatir(courantes)
    differentes, non_verifiables = [], []
    for cle in sorted(set(a) | set(b)):
        if cle == "arbre_propre":
            continue
        va, vb = a.get(cle), b.get(cle)
        if va is None or vb is None:
            if va is not None or vb is not None:
                non_verifiables.append(cle)
        elif va != vb:
            differentes.append(cle)
    return differentes, non_verifiables


# ── Lecture / écriture des lignes ────────────────────────────────────────────

def _lire_lignes(chemin: Path, *, tolerer_troncature: bool) -> tuple[list[LigneJeu], int]:
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
        except (ValueError, ValidationError) as e:   # json.JSONDecodeError est un ValueError
            derniere = octets_valides + len(ligne) >= len(brut.rstrip(b"\n"))
            if tolerer_troncature and derniere:
                logger.warning(f"[jeu] Dernière ligne de {chemin.name} tronquée ou malformée (ligne {numero}) — écartée, elle sera recalculée")
                return lignes, octets_valides
            raise JeuInvalide(f"{chemin.name} ligne {numero} : contenu malformé ({str(e).splitlines()[0][:120]})") from e
        octets_valides += len(ligne) + 1
    return lignes, min(octets_valides, len(brut))


def _ecrire_yaml_atomique(chemin: Path, contenu: dict) -> None:
    tmp = chemin.with_suffix(chemin.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(contenu, allow_unicode=True, sort_keys=False), encoding="utf-8")
    os.replace(tmp, chemin)


def _maintenant_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── Préparation ──────────────────────────────────────────────────────────────

class JeuEnPreparation:
    """Un jeu ouvert en écriture : append ligne par ligne, reprise, clôture (J11, J14, J15)."""

    def __init__(self, dossier: Path, manifest: dict, cles: set[tuple[str, str]], lignes: list[LigneJeu]):
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
        dependances: Optional[dict] = None,
    ) -> "JeuEnPreparation":
        dossier = Path(dossier)
        dossier.mkdir(parents=True, exist_ok=True)
        chemin_manifest = dossier / FICHIER_MANIFEST
        if chemin_manifest.exists():
            manifest = yaml.safe_load(chemin_manifest.read_text(encoding="utf-8")) or {}
            if manifest.get("clos"):
                raise JeuClos(f"le jeu {manifest.get('nom')!r} est clos : corriger produit un NOUVEAU jeu (J14)")
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
                "dependances": dependances if dependances is not None else dependances_courantes(),
            }
            _ecrire_yaml_atomique(chemin_manifest, manifest)
        lignes, octets = _lire_lignes(dossier / FICHIER_PROPOSITIONS, tolerer_troncature=True)
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
        self._fh.write((json.dumps(ligne.model_dump(mode="json"), ensure_ascii=False) + "\n").encode("utf-8"))
        self._fh.flush()
        os.fsync(self._fh.fileno())
        self.cles.add(ligne.cle)
        self._lignes.append(ligne)

    def clore(self, attendus: Sequence[Deplacement], personnes_total: int) -> dict:
        """Fige le jeu : complétude, liste des sans-proposition, empreinte du contenu (J5, J7, J14)."""
        self._fh.close()
        cles_attendues = {d.cle for d in attendus}
        couvertes = [l for l in self._lignes if l.cle in cles_attendues and l.propositions]
        sans = [l for l in self._lignes if l.cle in cles_attendues and not l.propositions]
        self.manifest.update({
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
                {"person_id": l.person_id, "activity_id": l.activity_id, "motif": l.motif_absence or MOTIF_AUCUNE_PROPOSITION}
                for l in sans
            ],
            "propositions_sha256": sha256_fichier(self.dossier / FICHIER_PROPOSITIONS),
        })
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
    fabrique_locale: Optional[Callable[..., Optional[TravelPlan]]] = None,
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
    activites = {(p.person_id, a.id): a for p in personnes for a in (p.identity.activities or [])}
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
            motif: Optional[str] = None
            if abs(dep.origine.lat - dep.destination.lat) < 1e-9 and abs(dep.origine.lon - dep.destination.lon) < 1e-9:
                motif = MOTIF_ORIGINE_EGALE_DESTINATION
                compteurs["ignores_meme_lieu"] += 1
            else:
                try:
                    itineraires = await trip_helper.get_itineraries(
                        origin=dep.origine, destination=dep.destination, departure_time=dep.depart_ts,
                        include_car=True, include_bike=True, arrive_by=False,
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
                    props.append(PropositionEnregistree(source=SOURCE_ENREGISTREE, plan=it.model_dump()))
                personne = par_personne.get(dep.person_id)
                activite = activites.get((dep.person_id, dep.activity_id))
                if personne is not None and activite is not None:
                    try:
                        locale = fabrique_locale(
                            person=personne, from_location=dep.origine, next_activity=activite,
                            timestamp=dep.depart_ts, departure_time=dep.depart_ts,
                        )
                    except Exception as e:  # noqa: BLE001
                        locale = None
                        logger.warning(f"[jeu] proposition locale impossible pour {dep.person_id}/{dep.activity_id} : {e}")
                    if locale is not None:
                        locale.purpose = dep.purpose
                        props.append(PropositionEnregistree(source=SOURCE_LOCALE, plan=locale.model_dump()))
                        compteurs["locales"] += 1
                if not props:
                    motif = MOTIF_AUCUNE_PROPOSITION
            prep.ecrire(LigneJeu(**dep.model_dump(), propositions=props, motif_absence=motif))
            compteurs["calcules"] += 1
            if not props:
                compteurs["sans_proposition"] += 1
                part = compteurs["sans_proposition"] / max(1, len(attendus))
                if part > seuil_sans_proposition and not alarme_levee:
                    alarme_levee = True
                    logger.error(
                        f"[ALARME] Jeu {prep.nom!r} : {compteurs['sans_proposition']} déplacements sans proposition "
                        f"sur {len(attendus)} attendus ({100 * part:.1f} % > {100 * seuil_sans_proposition:.1f} %)"
                    )

    def ecrire_progression() -> None:
        faits = compteurs["calcules"] + compteurs["erreurs"]
        ecoule = time.monotonic() - debut
        debit = faits / ecoule if ecoule > 0 else 0.0
        reste = (len(restants) - faits) / debit if debit > 0 else None
        contenu = {
            "jeu": prep.nom, "faits": faits + (len(attendus) - len(restants)), "total": len(attendus), "restants_au_depart": len(restants),
            "pourcent": round(100 * (faits + len(attendus) - len(restants)) / len(attendus), 1) if attendus else None,
            "sans_proposition": int(compteurs["sans_proposition"]), "erreurs": int(compteurs["erreurs"]),
            "ecoule_s": round(ecoule, 1), "reste_s": (round(reste) if reste is not None else None),
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
            logger.info(f"[jeu] {faits}/{len(restants)} déplacements traités · {ecoule:.0f} s écoulées · reste ≈ {reste:.0f} s")
            ecrire_progression()

    ecrire_progression()
    suivi = asyncio.create_task(progression())
    try:
        await asyncio.gather(*(traiter(d) for d in restants))
    finally:
        suivi.cancel()
        ecrire_progression()
    duree = time.monotonic() - debut
    compteurs["restants_apres"] = len(attendus) - len(prep.cles & {d.cle for d in attendus})
    if compteurs["sans_proposition"]:
        logger.warning(
            f"[jeu] {compteurs['sans_proposition']} déplacement(s) sans AUCUNE proposition des moteurs sur {len(attendus)} "
            f"({100 * compteurs['sans_proposition'] / max(1, len(attendus)):.1f} %) — inexploitables, ils seront exclus des "
            f"attendus des expériences (décision du 2026-09-06) ; détail : `consulter-jeu`"
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
                logger.warning(f"[jeu] clé en double {l.cle} dans {self.dossier.name} — première occurrence gardée")
                continue
            self._index[l.cle] = l
        self._par_personne: dict[str, list[LigneJeu]] = {}
        for l in self._index.values():
            self._par_personne.setdefault(l.person_id, []).append(l)
        for lst in self._par_personne.values():
            lst.sort(key=lambda x: (x.depart_ts, x.ordinal))

    @classmethod
    def charger(cls, dossier: str | Path, *, verifier: bool = True) -> "Jeu":
        dossier = Path(dossier)
        chemin_manifest = dossier / FICHIER_MANIFEST
        if not chemin_manifest.is_file():
            raise JeuInvalide(f"aucun {FICHIER_MANIFEST} dans {dossier}")
        try:
            manifest = yaml.safe_load(chemin_manifest.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise JeuInvalide(f"{FICHIER_MANIFEST} illisible : {e}") from e
        if manifest.get("version") != VERSION_JEU:
            raise JeuInvalide(f"version de jeu inconnue : {manifest.get('version')!r} (attendu {VERSION_JEU!r})")
        if not isinstance(manifest.get("dependances"), dict) or not manifest["dependances"]:
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
        lignes, _ = _lire_lignes(chemin_lignes, tolerer_troncature=not manifest.get("clos"))
        return cls(dossier, manifest, lignes)

    # ── identité ──
    @property
    def nom(self) -> str:
        return str(self.manifest.get("nom"))

    @property
    def empreinte(self) -> Optional[str]:
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

    def ligne_valide_le(self, jour: str, cle: tuple[str, str]) -> Optional[bool]:
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

    def verifier_population(self, info: InfoPopulation) -> Optional[str]:
        """Message de refus si la population n'est pas celle du jeu (G1, E6), sinon None."""
        attendu = self.population.get("sha256")
        if attendu != info.sha256:
            return (
                f"le jeu {self.nom!r} a été préparé pour la population {self.population.get('nom')!r} "
                f"(empreinte {str(attendu)[:12]}…), pas pour {info.nom!r} (empreinte {info.sha256[:12]}…)"
            )
        return None

    # ── lecture ──
    def ligne(self, person_id: str, activity_id: str) -> Optional[LigneJeu]:
        return self._index.get((person_id, activity_id))

    def propositions(self, person_id: str, activity_id: str) -> Optional[list[Proposition]]:
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
        attendus = (self.manifest.get("attendus") or {})
        couverts = (self.manifest.get("couverts") or {})
        n_attendus = int(attendus.get("deplacements") or 0)
        n_couverts = int(couverts.get("deplacements") or sum(1 for l in self._index.values() if l.propositions))
        return {
            "deplacements_attendus": n_attendus,
            "deplacements_couverts": n_couverts,
            "personnes_total": int(attendus.get("personnes_total") or 0),
            "personnes_avec_deplacement": int(attendus.get("personnes_avec_deplacement") or 0),
            "personnes_couvertes": int(couverts.get("personnes") or len({l.person_id for l in self._index.values() if l.propositions})),
            "sans_proposition": list(self.manifest.get("sans_proposition") or []),
            "non_calcules": int(self.manifest.get("non_calcules") or 0),
            "taux": (n_couverts / n_attendus) if n_attendus else None,
        }

    @property
    def est_complet(self) -> bool:
        c = self.couverture()
        return bool(c["deplacements_attendus"]) and c["deplacements_couverts"] == c["deplacements_attendus"]

    def resume(self) -> str:
        c = self.couverture()
        taux = f"{100 * c['taux']:.1f} %".replace(".", ",") if c["taux"] is not None else "n/a"
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
            lignes.append(f"  INEXPLOITABLES (aucune proposition des moteurs, exclus des attendus d'une expérience) : "
                          f"{len(c['sans_proposition'])} — " + ", ".join(f"{m} × {n}" for m, n in motifs.most_common()))
        if c["non_calcules"]:
            lignes.append(f"  NON CALCULÉS : {c['non_calcules']} (préparation interrompue : reprendre)")
        return "\n".join(lignes)


def _signature_tc(propositions: Sequence[Proposition]) -> list[tuple]:
    """Ce qui distingue une offre de transports collectifs d'une autre : lignes empruntées, durée à la minute."""
    from urban_mobility_agents.candidats import _primary_mode
    return sorted(
        (p.plan.get_code() if p.plan.legs else p.plan.id, p.mode, (p.plan.duration or 0) // 60)
        for p in propositions if _primary_mode(p.plan) == "transit"
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

    decalage = (_date.fromisoformat(jour) - _date.fromisoformat(jeu.jour_simule)).days * 86400
    lignes = [l for l in jeu._index.values() if any(_signature_tc(l.vers_propositions()))]
    rng = _random.Random(graine)
    tirees = rng.sample(lignes, min(echantillon, len(lignes))) if lignes else []
    sem = asyncio.Semaphore(max(1, concurrence))
    resultats: list[dict] = []

    async def un(ligne: LigneJeu) -> None:
        async with sem:
            avant = _signature_tc(ligne.vers_propositions())
            try:
                its = await trip_helper.get_itineraries(
                    origin=ligne.origine, destination=ligne.destination, departure_time=ligne.depart_ts + decalage,
                    include_car=True, include_bike=True, arrive_by=False,
                )
            except Exception as e:  # noqa: BLE001
                resultats.append({"cle": list(ligne.cle), "erreur": f"{type(e).__name__}: {e}"})
                return
            apres = _signature_tc([Proposition(it, SOURCE_ENREGISTREE) for it in its or []])
            resultats.append({"cle": list(ligne.cle), "identique": avant == apres, "avant": avant, "apres": apres})

    await asyncio.gather(*(un(l) for l in tirees))
    identiques = sum(1 for r in resultats if r.get("identique"))
    erreurs = sum(1 for r in resultats if "erreur" in r)
    compares = len(resultats) - erreurs
    return {
        "jeu": jeu.nom, "jour_jeu": jeu.jour_simule, "jour": jour, "echantillon": len(tirees), "graine": graine,
        "compares": compares, "identiques": identiques, "differents": compares - identiques, "erreurs": erreurs,
        "part_identique": (identiques / compares) if compares else None,
        "equivalent": bool(compares) and identiques == compares and erreurs == 0,
        "mesure_le": _maintenant_iso(),
        "differences": [r for r in resultats if r.get("identique") is False][:20],
    }


def perime(jeu: Jeu, courantes: Optional[dict] = None) -> tuple[list[str], list[str]]:
    """J10 — (dépendances changées depuis la préparation, dépendances non vérifiables)."""
    return comparer_dependances(jeu.manifest.get("dependances") or {}, courantes if courantes is not None else dependances_courantes())


__all__ = [
    "VERSION_JEU", "FICHIER_MANIFEST", "FICHIER_PROPOSITIONS", "HEURE_REFERENCE_DEPART",
    "MOTIF_ORIGINE_EGALE_DESTINATION", "MOTIF_AUCUNE_PROPOSITION",
    "JeuInvalide", "JeuClos", "Deplacement", "PropositionEnregistree", "LigneJeu",
    "jour_base_ts", "deplacements_attendus", "dependances_courantes", "comparer_dependances",
    "JeuEnPreparation", "preparer", "Jeu", "perime", "comparer_offre_jour", "FICHIER_EQUIVALENCES",
]
