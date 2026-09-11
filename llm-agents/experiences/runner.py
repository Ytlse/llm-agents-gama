"""Exécution sans simulateur (ticket 035, spec 03) avec ressources et reprise (spec 05).

Pour chaque personne, ses déplacements de la journée **dans l'ordre**, en appelant la décision
unique (spec 02) avec les propositions du jeu enregistré (spec 01). Aucun moteur de routage. Les
personnes avancent en parallèle (`regroupement.parallelisme`), jamais deux déplacements d'une même
personne (S4). Tout ce qui est décidé est archivé aussitôt (Q9) ; à la reprise, les décisions
archivées sont resservies et leur effet sur la chaîne des véhicules rejoué sans sollicitation (Q5).
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from experiences import decision as D
from experiences.archive import (
    ETAT_ARRETEE,
    ETAT_EN_ATTENTE_QUOTA,
    ETAT_EN_COURS,
    ETAT_EN_PAUSE,
    ETAT_EPUISEE,
    ETAT_TERMINEE,
    METHODE_INEXPLOITABLE,
    METHODE_NON_COUVERT,
    Execution,
)
from experiences.experience import Experience
from experiences.jeu import Deplacement, Jeu, deplacements_attendus
from experiences.ressources import MoniteurRessources, prochaine_fenetre_quota
from loguru import logger
from models import Person

FICHIER_PAUSE = "PAUSE"
FICHIER_STOP = "STOP"


def _env_flottant(nom: str, defaut: float) -> float:
    """Réglage d'exploitation lu dans l'environnement. Une valeur illisible ne casse rien :
    elle est signalée et le défaut s'applique."""
    brut = os.environ.get(nom)
    if brut is None or not brut.strip():
        return defaut
    try:
        return float(brut)
    except ValueError:
        logger.warning(
            f"[execution] {nom}={brut!r} illisible — défaut {defaut} conservé"
        )
        return defaut


# Délai laissé à une sollicitation DÉJÀ EN VOL quand une pause / un arrêt est demandé. Passé ce
# délai, l'appel réseau est abandonné (jamais une écriture d'archive) : le déplacement reste non
# archivé, donc redemandé tel quel à la reprise (Q5/Q6), et rien n'est sauté ni fabriqué. Sans
# cette grâce, la pause attendait le retour de l'appel — jusqu'à `remote_llm_poll_timeout`, 120 s.
DELAI_GRACE_PAUSE_S = _env_flottant("EXP_PAUSE_GRACE_S", 15.0)

# Mise en pause AUTOMATIQUE après ce délai sans le moindre déplacement réglé (0 ou négatif =
# désactivé). Une exécution qui n'avance plus se signale et se met en pause au lieu de rester
# « en cours » pour toujours ; elle reste reprenable.
INACTIVITE_PAUSE_S = _env_flottant("EXP_INACTIVITE_PAUSE_S", 420.0)

# Âge maximal de l'instantané des quotas pendant un run (0 ou négatif = désactivé). Sans ce
# rafraîchissement, `moniteur.etat` restait celui du DÉMARRAGE : une clé qui s'épuisait en
# cours de route restait « disponible », le décideur continuait de l'épingler (`force_provider`
# est strict côté passerelle, qui refuse plutôt que de substituer) et la clé suivante n'était
# jamais entamée. Le 2026-09-08, un run s'est arrêté à 70,5 % avec 500 requêtes intactes en
# réserve sur la seconde clé.
RAFRAICHIR_QUOTAS_S = _env_flottant("EXP_RAFRAICHIR_QUOTAS_S", 30.0)


@dataclass
class Controle:
    """Pause / arrêt demandés par fichier dans le dossier d'exécution, ou par signal (Q7, Q8).

    Porte aussi le **délai de grâce** : une pause demandée pendant qu'une sollicitation est en
    vol n'attend plus son retour indéfiniment. Passé `grace_s`, l'appel est abandonné — le
    déplacement, non archivé, sera redemandé à la reprise (décision du 2026-09-08, qui révise
    celle du 2026-09-07 : la pause devenait effective jusqu'à 2 min après le clic).
    """

    dossier: Path
    pause: bool = False
    arret: bool = False
    installes: bool = field(default=False, repr=False)
    grace_s: float = field(default_factory=lambda: DELAI_GRACE_PAUSE_S)
    # Pourquoi la pause : « manuelle », « inactivite:<n>s », « signal:SIGINT »… Reprise dans
    # l'état de l'exécution et dans son historique d'interruptions.
    raison: str = ""
    demande_a: float | None = field(default=None, repr=False)
    _en_vol: set[asyncio.Task] = field(default_factory=set, repr=False)
    _abandonnees: set[asyncio.Task] = field(default_factory=set, repr=False)

    def demande_pause(self) -> bool:
        return self.pause or (self.dossier / FICHIER_PAUSE).exists()

    def demande_arret(self) -> bool:
        return self.arret or (self.dossier / FICHIER_STOP).exists()

    def interrompu(self) -> bool:
        if self.demande_pause() or self.demande_arret():
            if self.demande_a is None:
                self.demande_a = time.monotonic()  # départ de la grâce
            return True
        return False

    def grace_echue(self) -> bool:
        """La grâce laissée aux sollicitations en vol est-elle écoulée ?"""
        return (
            self.demande_a is not None
            and (time.monotonic() - self.demande_a) >= self.grace_s
        )

    # ── sollicitations en vol ──
    def suivre(self, tache: asyncio.Task) -> None:
        self._en_vol.add(tache)

    def oublier(self, tache: asyncio.Task) -> None:
        self._en_vol.discard(tache)
        self._abandonnees.discard(tache)

    def abandonnee(self, tache: asyncio.Task) -> bool:
        """Cet appel a-t-il été annulé PAR NOUS ? Distingue l'abandon volontaire d'une
        annulation venue de l'extérieur, qu'il faut laisser remonter."""
        return tache in self._abandonnees

    def abandonner_en_vol(self) -> int:
        """Annule les appels au décideur encore en vol. Rend leur nombre (0 si aucun)."""
        a_annuler = [t for t in self._en_vol if not t.done()]
        for t in a_annuler:
            self._abandonnees.add(t)
            t.cancel()
        return len(a_annuler)

    def nettoyer(self) -> list[str]:
        """Retire les sentinelles d'interruption. Rend celles qui existaient (vide si aucune)."""
        retirees: list[str] = []
        for f in (FICHIER_PAUSE, FICHIER_STOP):
            try:
                (self.dossier / f).unlink()
            except FileNotFoundError:
                pass
            else:
                retirees.append(f)
        return retirees

    def installer_signaux(self) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(signal.SIGINT, self._sur_signal, "SIGINT")
            loop.add_signal_handler(signal.SIGTERM, self._sur_signal, "SIGTERM")
            self.installes = True
        except (NotImplementedError, RuntimeError, ValueError):
            self.installes = False

    def _sur_signal(self, nom: str) -> None:
        logger.warning(
            f"[execution] {nom} reçu : mise en pause — sollicitations en vol abandonnées "
            f"au plus tard dans {self.grace_s:.0f} s"
        )
        self.raison = self.raison or f"signal:{nom}"
        self.pause = True


def _decalage_calendrier(exp: Experience, jeu: Jeu) -> int:
    """Politique `commune` : la date de l'expérience décale les horodatages de jours entiers ;
    l'offre de transport reste celle du jeu (question 11). Autres politiques : la date par
    personne est tirée par les réglages météo (`weather_per_agent_dates`), pas ici."""
    if exp.calendrier.politique != "commune":
        return 0
    return (
        date.fromisoformat(exp.calendrier.date) - date.fromisoformat(jeu.jour_simule)
    ).days * 86400


def _anticipation(person: Person, activity_id: str, departure_time: int) -> dict | None:
    """Même bloc d'anticipation que la simulation (ticket 014) — ou rien si indisponible."""
    from settings import settings

    if not settings.agent.agenda_anticipation_enabled:
        return None
    act = next(
        (a for a in (person.identity.activities or []) if a.id == activity_id), None
    )
    if act is None:
        return None
    try:
        from urban_mobility_agents.simulation_controller import _build_anticipation

        return _build_anticipation(person, act, departure_time)
    except Exception as e:  # noqa: BLE001 — l'anticipation est un contexte, pas une règle : on le dit
        logger.warning(
            f"[execution] anticipation indisponible pour {person.person_id}: {e}"
        )
        return None


def _methode_moves(decision: D.Decision, decideur) -> str:
    if decision.methode == D.METHODE_CHOIX_UNIQUE:
        return "Un seul itinéraire disponible"
    if decision.methode == D.METHODE_SANS_SOLUTION:
        return "Pas de solution de déplacement"
    if decision.methode == D.METHODE_REPLI_UNIFORME:
        return "LLM Error (Default index) — repli uniforme"
    if decision.methode == D.METHODE_MODELE_NON_IMPUTABLE:
        # Non-décision du modèle (hors domaine) : sans mode choisi, exclue du score.
        return "Modèle : hors domaine (non imputable)"
    return (
        "LLM"
        if not getattr(decideur, "sans_quota", True)
        else f"Décideur {getattr(decideur, 'nom', '?')}"
    )


FICHIER_PROGRESSION = (
    "progression.json"  # lu par le tableau de bord (barre d'avancement)
)


class Progression:
    """Avancement visible (S6) : journal toutes les `periode_s` secondes ET `progression.json` du dossier."""

    def __init__(
        self,
        attendus: int,
        personnes: int,
        deja: int,
        periode_s: float = 5.0,
        dossier: Path | None = None,
    ):
        self.attendus, self.personnes, self.deja, self.periode_s = (
            attendus,
            personnes,
            deja,
            periode_s,
        )
        self.dossier = dossier
        self.debut = time.monotonic()
        self.compteurs: Counter = Counter()
        self.personnes_terminees = 0
        # Deux compteurs, deux sens (décision du 2026-09-07). R1 ne saute JAMAIS un
        # déplacement : une tentative qui échoue est réessayée jusqu'à décision. La compter
        # comme une « erreur » faisait lire 128 erreurs sur un run qui n'en avait aucune, et
        # cachait le vrai signal — le débit du fournisseur.
        #   attentes_par_type : tentatives échouées PUIS réessayées (le cas nominal)
        #   erreurs_par_type  : échec définitif, déplacement clos sans décision. Reste vide
        #                       tant que R1 tient : une valeur non nulle DÉNONCE une violation.
        self.attentes_par_type: Counter = Counter()
        self.erreurs_par_type: Counter = Counter()
        # Déplacements qui attendent une ressource transitoire (R3) : (person, activity) → (t0, type).
        self._attentes: dict[tuple[str, str], tuple[float, str]] = {}
        self._attente_quota_jusqu: str | None = (
            None  # fenêtre quota en cours (R4), ISO UTC ou None
        )
        # Horloge d'immobilité du chien de garde : instant du dernier déplacement réglé.
        self._avancement_vu = 0
        self._avancement_t = self.debut

    def avancement(self) -> int:
        """Nombre de déplacements RÉGLÉS depuis le départ, quelle qu'en soit l'issue — décidé,
        resservi depuis l'archive, non couvert, inexploitable, sans solution. C'est ce compteur
        qui bouge quand l'exécution avance ; s'il ne bouge plus, elle n'avance plus."""
        return (
            self.traites()
            + int(self.compteurs["resservies"])
            + int(self.compteurs["inexploitables"])
        )

    def immobile_depuis(self) -> float | None:
        """Secondes écoulées sans le moindre déplacement réglé, ou `None` quand l'immobilité est
        VOULUE — attente de la fenêtre de quota (R4, `--attendre-fenetre`) : là, ne rien faire
        est le comportement demandé, le chien de garde se tait."""
        if self._attente_quota_jusqu is not None:
            return None
        vu = self.avancement()
        if vu != self._avancement_vu:
            self._avancement_vu, self._avancement_t = vu, time.monotonic()
            return 0.0
        return time.monotonic() - self._avancement_t

    def entrer_attente(self, dep, type_err: str) -> None:
        """Un déplacement commence (ou poursuit) une attente transitoire — l'horloge part au 1er échec."""
        self._attentes.setdefault(
            (dep.person_id, dep.activity_id), (time.monotonic(), type_err)
        )

    def sortir_attente(self, dep) -> None:
        self._attentes.pop((dep.person_id, dep.activity_id), None)

    def entrer_attente_quota(self, reprise_a: str) -> None:
        self._attente_quota_jusqu = reprise_a

    def sortir_attente_quota(self) -> None:
        self._attente_quota_jusqu = None

    def _attente_la_plus_ancienne(self) -> dict | None:
        now = time.monotonic()
        candidates = [
            (now - t0, pid, aid, typ)
            for (pid, aid), (t0, typ) in self._attentes.items()
        ]
        if not candidates:
            return None
        depuis, pid, aid, typ = max(candidates)
        return {
            "person_id": pid,
            "activity_id": aid,
            "depuis_s": round(depuis, 1),
            "type": typ,
        }

    def etat(self) -> dict:
        faits = self.deja + self.traites()
        ecoule = time.monotonic() - self.debut
        debit = self.traites() / ecoule if ecoule > 0 else 0.0
        reste = (self.attendus - faits) / debit if debit > 0 else None
        en_attente = self._attente_la_plus_ancienne()
        return {
            "faits": faits,
            "attendus": self.attendus,
            "pourcent": round(100 * faits / self.attendus, 1)
            if self.attendus
            else None,
            "personnes_terminees": self.personnes_terminees,
            "personnes": self.personnes,
            "ecoule_s": round(ecoule, 1),
            "reste_s": (round(reste) if reste is not None else None),
            "sollicitations": int(self.compteurs["sollicitations"]),
            "attentes": int(sum(self.attentes_par_type.values())),
            "attentes_par_type": dict(self.attentes_par_type),
            "erreurs": int(sum(self.erreurs_par_type.values())),
            "erreurs_par_type": dict(self.erreurs_par_type),
            "en_attente_depuis_s": (en_attente["depuis_s"] if en_attente else 0.0),
            "en_attente": en_attente,
            "en_attente_quota_jusqu": self._attente_quota_jusqu,
            # Lu par le tableau de bord : « immobile depuis N min » avant que le chien de
            # garde ne mette en pause. None pendant une fenêtre de quota (immobilité voulue).
            "immobile_depuis_s": (
                round(immobile, 1)
                if (immobile := self.immobile_depuis()) is not None
                else None
            ),
            "maj": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    def ecrire(self) -> None:
        if self.dossier is None:
            return
        try:
            tmp = self.dossier / (FICHIER_PROGRESSION + ".tmp")
            tmp.write_text(
                json.dumps(self.etat(), ensure_ascii=False), encoding="utf-8"
            )
            os.replace(tmp, self.dossier / FICHIER_PROGRESSION)
        except OSError as e:
            logger.warning(f"[execution] progression.json non écrit : {e}")

    def traites(self) -> int:
        return (
            self.compteurs["decides"]
            + self.compteurs["non_couverts"]
            + self.compteurs["sans_solution"]
        )

    def ligne(self) -> str:
        faits = self.deja + self.traites()
        ecoule = time.monotonic() - self.debut
        debit = self.traites() / ecoule if ecoule > 0 else 0.0
        reste = (self.attendus - faits) / debit if debit > 0 else float("nan")
        return (
            f"[execution] {faits}/{self.attendus} déplacements ({100 * faits / max(1, self.attendus):.1f} %) · "
            f"{self.personnes_terminees}/{self.personnes} personnes · {ecoule:.0f} s écoulées · reste ≈ {reste:.0f} s · "
            f"sollicitations {self.compteurs['sollicitations']} · attentes {sum(self.attentes_par_type.values())} "
            f"{dict(self.attentes_par_type) if self.attentes_par_type else ''}"
            + (
                f" · ERREURS {sum(self.erreurs_par_type.values())} {dict(self.erreurs_par_type)}"
                if self.erreurs_par_type
                else ""
            )
        )

    async def boucle(self) -> None:
        while True:
            await asyncio.sleep(self.periode_s)
            logger.info(self.ligne())
            self.ecrire()


PAS_ATTENTE_S = (
    0.5  # granularité d'un sommeil interruptible : rend la main vite à PAUSE/STOP
)
PAUSE_BASE_S = (
    5.0  # pause de la 1re tentative ; croît (× tentative) jusqu'au plafond (R1)
)
PAUSE_PLAFOND_S = 60.0  # plafond de la pause croissante entre deux tentatives (R1)


async def _dormir_interruptible(
    duree_s: float, controle: Controle, epuise: asyncio.Event
) -> None:
    """Dort `duree_s`, mais rend la main dès qu'une interruption (PAUSE/STOP/SIGINT) ou un
    épuisement est demandé — c'est ce qui rend l'attente d'un déplacement interruptible (R1)."""
    reste = duree_s
    while reste > 0:
        if controle.interrompu() or epuise.is_set():
            return
        await asyncio.sleep(min(PAS_ATTENTE_S, reste))
        reste -= PAS_ATTENTE_S


def _confirme_epuise(
    moniteur: MoniteurRessources | None, *, annonce_par_fournisseur: bool = False
) -> bool:
    """L'épuisement est-il RÉEL ?

    `annonce_par_fournisseur` (429 « per day », cf. `genre_erreur`) tranche seul : le moniteur
    lit `/health`, donc un compteur qui ne voit QUE le trafic de ce gateway. Le 2026-09-08 il
    affichait 49 requêtes sur 500 — instance « disponible » — pendant que Google refusait pour
    dépassement des 500 ; l'exécution a attendu 15 min une clé fermée jusqu'à 09:00.

    Sinon : sans moniteur, un 429/402 fait foi ; avec moniteur, seule sa vue rafraîchie tranche
    (une instance encore disponible ⇒ le 429 était transitoire).
    """
    if annonce_par_fournisseur:
        return True
    if moniteur is None:
        return True
    moniteur.rafraichir()
    return moniteur.epuise()


async def executer(
    exp: Experience,
    jeu: Jeu,
    personnes: Sequence[Person],
    execution: Execution,
    decideur,
    *,
    moniteur: MoniteurRessources | None = None,
    controle: Controle | None = None,
    ecrire_moves: bool = True,
    # Par défaut on attend la fenêtre (2026-09-08) : la réouverture est désormais connue et
    # bornée (heure annoncée par le fournisseur, ou minuit dans son fuseau), donc une
    # expérience lancée le soir se termine seule au lieu de mourir à 10 % sur un quota du
    # jour. L'attente reste visible (état `en_attente_quota`, `en_attente_quota_jusqu` dans
    # progression.json) et interruptible (PAUSE/STOP/SIGINT).
    attendre_fenetre: bool = True,
    periode_progression_s: float = 5.0,
) -> dict:
    """Déroule (ou reprend) l'exécution ; rend les compteurs (S8).

    Aucun déplacement n'est jamais sauté (R1) : une erreur transitoire est réessayée indéfiniment,
    pause croissante plafonnée à 60 s, interruptible par PAUSE/STOP/SIGINT ; le déplacement reste
    non archivé donc repris tel quel. `attente_max_s` ne borne plus l'attente — c'est un seuil
    d'`[ALARME]` (décision a). Seul un épuisement de quota CONFIRMÉ arrête (ou, si `attendre_fenetre`,
    fait dormir jusqu'à la fenêtre de reprise — R4)."""
    debut = time.monotonic()
    controle = controle or Controle(execution.dossier)
    # Un PAUSE/STOP résiduel se purge AVANT de commencer, pas seulement à la clôture : un
    # runner tué net (conteneur arrêté) laisse sa sentinelle sur le disque, et sans ce
    # nettoyage la reprise se remettait en pause en quelques secondes — l'exécution paraissait
    # irréprenable. La demande d'interruption ne vaut que pour le run qui l'a reçue.
    residus = controle.nettoyer()
    if residus:
        logger.info(
            f"[execution] sentinelle(s) d'interruption résiduelle(s) purgée(s) avant reprise : "
            f"{', '.join(residus)} — elles venaient d'un run précédent, pas de celui-ci"
        )
    controle.installer_signaux()
    attendus = deplacements_attendus(personnes, jeu.jour_simule)
    par_personne: dict[str, list[Deplacement]] = {}
    for d in attendus:
        par_personne.setdefault(d.person_id, []).append(d)
    for lst in par_personne.values():
        lst.sort(key=lambda d: d.ordinal)
    deja = len(execution.decisions)
    reprise = deja > 0
    decalage = _decalage_calendrier(exp, jeu)
    prog = Progression(
        len(attendus),
        len(par_personne),
        deja,
        periode_progression_s,
        dossier=execution.dossier,
    )
    prog.ecrire()
    moves = execution.journal_moves() if ecrire_moves else None

    if reprise:
        interruptions = execution.config.get("interruptions") or []
        derniere = interruptions[-1]["instant"] if interruptions else None
        # Exécution laissée `en_cours` = processus tué sans clôture (panne, kill) : on le consigne
        # avant de reprendre, sinon l'arrêt brutal ne laisse aucune trace (R3).
        if execution.etat().get("etat") == ETAT_EN_COURS:
            execution.ajouter_interruption("arret_force", depuis=derniere)
            logger.warning(
                f"[execution] {execution.nom} rouverte alors qu'elle était `en_cours` — "
                f"arrêt forcé consigné (processus interrompu sans clôture)"
            )
        execution.ajouter_interruption("reprise", depuis=derniere)
    execution.changer_etat(ETAT_EN_COURS)
    execution.mettre_a_jour_regime(
        parallelisme=exp.regroupement.parallelisme,
        unite_sollicitation="deplacement",
        decideur=getattr(decideur, "nom", "?"),
        reprise=reprise,
    )
    logger.info(
        f"[execution] Début {execution.nom} ({exp.nom}) : {len(attendus)} déplacements attendus, "
        f"{len(par_personne)} personnes, {deja} décisions déjà archivées, décideur {getattr(decideur, 'nom', '?')}"
    )

    epuise = asyncio.Event()
    raison_epuisement: dict = {}
    sem = asyncio.Semaphore(max(1, exp.regroupement.parallelisme))
    quota_lock = (
        asyncio.Lock()
    )  # R4 : un seul dormeur attend la fenêtre, les autres re-vérifient

    def _par_code(props: list[D.Proposition], code: str | None) -> D.Proposition | None:
        return next((p for p in props if p.code == code), None) if code else None

    async def _attendre_fenetre_quota(
        raison: str, reprise_annoncee: str | None = None
    ) -> None:
        """R4 : dort en process jusqu'à la réouverture de la fenêtre de quota, puis rafraîchit le
        moniteur et repart. Interruptible (PAUSE/STOP/SIGINT). Un seul coroutine dort à la fois ;
        les autres re-testent l'épuisement et repartent aussitôt si le quota a rouvert. Aucune
        substitution, aucune décision par défaut : on ATTEND (RG-2, Q3).

        `reprise_annoncee` est l'heure que le FOURNISSEUR a donnée (429 « per day ») : elle
        l'emporte sur le calcul local. Viser minuit UTC en dur réveillait l'exécution à 02:00
        heure de Paris pour un quota Gemini qui ne rouvre qu'à 09:00 — sept heures de refus.
        """
        async with quota_lock:
            if controle.interrompu() or not _confirme_epuise(
                moniteur, annonce_par_fournisseur=bool(reprise_annoncee)
            ):
                return
            reprise_a = reprise_annoncee or prochaine_fenetre_quota()
            execution.changer_etat(ETAT_EN_ATTENTE_QUOTA, raison, reprise_a)
            prog.entrer_attente_quota(reprise_a)
            logger.error(
                f"[ALARME] [execution] {execution.nom} en attente de la fenêtre quota "
                f"jusqu'à {reprise_a} — {raison}"
            )
            cible = datetime.fromisoformat(reprise_a)
            while datetime.now(timezone.utc) < cible:
                if controle.interrompu() or epuise.is_set():
                    break
                restant = (cible - datetime.now(timezone.utc)).total_seconds()
                await asyncio.sleep(min(PAS_ATTENTE_S * 10, max(0.0, restant)))
            prog.sortir_attente_quota()
            if moniteur is not None:
                moniteur.rafraichir()
            if not controle.interrompu() and not epuise.is_set():
                execution.changer_etat(ETAT_EN_COURS)
                logger.info(
                    f"[execution] {execution.nom} : fenêtre quota atteinte, reprise"
                )

    async def traiter_personne(personne: Person, deps: list[Deplacement]) -> None:
        async with sem:
            personne.state.planning_vehicle_at = {}  # la journée commence au domicile (D4)
            for dep in deps:
                if controle.interrompu() or epuise.is_set():
                    return
                props = jeu.propositions(dep.person_id, dep.activity_id)
                archivee = execution.decision(dep.person_id, dep.activity_id)
                if archivee is not None:
                    prog.compteurs["resservies"] += 1
                    retenue = _par_code(
                        props or [], (archivee.get("retenue") or {}).get("code")
                    )
                    if retenue is not None:
                        D.avancer_chaine(
                            personne,
                            retenue.plan,
                            dep.origine,
                            dep.destination,
                            dep.purpose,
                        )
                    continue
                if not props:
                    # props is None : le jeu ne couvre pas ce déplacement (non couvert, dans les attendus).
                    # props == []  : couvert, mais les moteurs n'ont AUCUNE proposition — trajet
                    # inexploitable par quelque décideur que ce soit : exclu des attendus, remonté
                    # en avertissement (décision de l'auteur, 2026-09-06, question 3).
                    methode = (
                        METHODE_NON_COUVERT if props is None else METHODE_INEXPLOITABLE
                    )
                    trace = D.construire_trace(
                        personne,
                        D.ContexteDecision(
                            timestamp=dep.depart_ts + decalage,
                            activity_id=dep.activity_id,
                            purpose=dep.purpose,
                            departure_time=dep.depart_ts + decalage,
                            from_location=dep.origine,
                            destination=dep.destination,
                            graine_ordre=exp.graine_ordre,
                            graine_tirage=exp.graine_tirage,
                            max_candidats=exp.max_candidats,
                        ),
                        [],
                        [],
                        None,
                        methode,
                        None,
                        "",
                    )
                    if props is not None:
                        ligne = jeu.ligne(dep.person_id, dep.activity_id)
                        trace["motif_absence"] = (
                            ligne.motif_absence if ligne is not None else None
                        )
                    execution.ajouter_decision(trace)
                    prog.compteurs[
                        "non_couverts" if props is None else "inexploitables"
                    ] += 1
                    continue
                ctx = D.ContexteDecision(
                    timestamp=dep.depart_ts + decalage,
                    activity_id=dep.activity_id,
                    purpose=dep.purpose,
                    departure_time=dep.depart_ts + decalage,
                    from_location=dep.origine,
                    destination=dep.destination,
                    anticipation=_anticipation(
                        personne, dep.activity_id, dep.depart_ts + decalage
                    ),
                    graine_ordre=exp.graine_ordre,
                    graine_tirage=exp.graine_tirage,
                    max_candidats=exp.max_candidats,
                )
                # R1 — on réessaie jusqu'à obtenir une décision : JAMAIS de saut. Le déplacement
                # n'est archivé que décidé ; interrompu, il reste non archivé donc repris tel quel.
                decision: D.Decision | None = None
                attente_totale = 0.0
                tentative = 0
                alarme_levee = False
                while True:
                    if controle.interrompu() or epuise.is_set():
                        return  # point sûr : rien de partiel archivé (Q7/Q8)
                    tentative += 1
                    # La sollicitation est une tâche SUIVIE : passé le délai de grâce, une
                    # pause/arrêt l'abandonne (`abandonner_en_vol`). L'annulation ne touche que
                    # l'appel réseau — aucune écriture d'archive n'est jamais interrompue.
                    appel = asyncio.ensure_future(
                        D.decider(personne, ctx, props, decideur)
                    )
                    controle.suivre(appel)
                    try:
                        decision = await appel
                    except asyncio.CancelledError:
                        if controle.abandonnee(appel):
                            return  # point sûr : le déplacement reste non archivé (Q7/Q8)
                        raise  # annulation venue d'ailleurs : elle doit remonter
                    finally:
                        controle.oublier(appel)
                    if decision.sollicite:
                        prog.compteurs["sollicitations"] += 1
                    if decision.est_decision:
                        break
                    erreur = str(decision.trace.get("erreur") or "")
                    type_err = erreur.split(":")[0].strip() or "erreur"
                    # Tentative réessayée : une ATTENTE, pas une erreur. Le déplacement n'est
                    # pas clos, il repassera par cette boucle jusqu'à obtenir sa décision (R1).
                    prog.attentes_par_type[type_err] += 1
                    execution.ajouter_erreur(
                        {
                            "horodatage": datetime.now(timezone.utc).isoformat(
                                timespec="seconds"
                            ),
                            "person_id": dep.person_id,
                            "activity_id": dep.activity_id,
                            "tentative": tentative,
                            "type": type_err,
                            "message": erreur[:500],
                            "fournisseur": (
                                decision.reponse.fournisseur if decision.reponse else ""
                            )
                            or "",
                            "attente_s": round(attente_totale, 1),
                        }
                    )
                    # Épuisement de quota CONFIRMÉ : soit le fournisseur l'a annoncé (429
                    # « per day », qui porte son heure de reprise), soit 429/402 + moniteur épuisé.
                    reprise_annoncee = (
                        decision.reponse.reprise_a if decision.reponse else None
                    )
                    if type_err == "epuise" and _confirme_epuise(
                        moniteur, annonce_par_fournisseur=bool(reprise_annoncee)
                    ):
                        if attendre_fenetre:
                            await _attendre_fenetre_quota(
                                erreur, reprise_annoncee
                            )  # R4 : dort jusqu'à la fenêtre, puis retente
                            continue
                        raison_epuisement.update(
                            {
                                "raison": erreur,
                                "reprise": reprise_annoncee or prochaine_fenetre_quota(),
                            }
                        )
                        epuise.set()
                        return
                    if type_err == "substitution_refusee":
                        continue  # une autre instance, tout de suite (Q3)
                    # Erreur transitoire (passerelle occupée, timeout, 429 non confirmé…) : on ATTEND,
                    # pause croissante plafonnée (R1) ; `attente_max_s` ne borne plus, il ALARME.
                    pause = min(PAUSE_BASE_S * tentative, PAUSE_PLAFOND_S)
                    attente_totale += pause
                    prog.entrer_attente(dep, type_err)
                    if attente_totale > exp.attente_max_s and not alarme_levee:
                        logger.error(
                            f"[ALARME] [execution] attente {attente_totale:.0f}s > seuil "
                            f"{exp.attente_max_s}s pour {dep.person_id}/{dep.activity_id} "
                            f"({type_err}) — on continue d'attendre, aucun déplacement n'est sauté"
                        )
                        alarme_levee = True
                    await _dormir_interruptible(pause, controle, epuise)
                prog.sortir_attente(dep)
                execution.ajouter_decision(decision.trace)
                prog.compteurs["decides"] += 1
                prog.compteurs[decision.methode] += 1
                if decision.retenue is not None:
                    D.avancer_chaine(
                        personne,
                        decision.retenue.plan,
                        dep.origine,
                        dep.destination,
                        dep.purpose,
                    )
                if moves is not None:
                    plus_rapide = min(
                        (p.plan for p in props),
                        key=lambda pl: pl.duration or float("inf"),
                        default=None,
                    )
                    await moves.ecrire(
                        person=personne,
                        plan=decision.retenue.plan if decision.retenue else None,
                        purpose=dep.purpose,
                        selection_method=_methode_moves(decision, decideur),
                        provider_model=(
                            decision.reponse.fournisseur if decision.reponse else ""
                        ),
                        faster_itinerary=plus_rapide,
                        reasoning=(decision.reponse.raison if decision.reponse else ""),
                        chain_constraint=decision.trace.get("contrainte_chaine", ""),
                        anticipation=(ctx.anticipation or {}).get("trace", "")
                        if ctx.anticipation
                        else "",
                        move_id=f"{dep.person_id}:{dep.activity_id}",
                        simulated_time=ctx.timestamp,
                        start_time=(
                            decision.retenue.plan.start_time
                            if decision.retenue
                            else None
                        ),
                        available_options=[p.plan for p in props],
                        activity_id=dep.activity_id,
                        mode_probabilities=(
                            decision.reponse.distribution if decision.reponse else None
                        ),
                        sources=",".join(
                            f"{k}:{v}"
                            for k, v in sorted(
                                Counter(
                                    str(v).split(":")[0]
                                    for v in decision.trace["sources"].values()
                                ).items()
                            )
                        ),
                        ecartees=D.resumer_ecartees(decision.trace["ecartees"]),
                        lot=str(decision.trace.get("identifiant_lot") or ""),
                    )
            prog.personnes_terminees += 1

    async def surveiller() -> None:
        """Le seul endroit qui regarde les demandes d'interruption et l'inactivité.

        Deux devoirs, tous les `PAS_ATTENTE_S` :

        1. **chien de garde** — au-delà de `INACTIVITE_PAUSE_S` sans le moindre déplacement
           réglé, l'exécution se met en pause d'elle-même en le disant en ERROR, plutôt que
           de rester « en cours » indéfiniment. Elle reste reprenable ;
        2. **grâce** — la demande passée, une fois `controle.grace_s` écoulé, les
           sollicitations encore en vol sont abandonnées : la pause devient effective en
           quelques secondes au lieu d'attendre le retour d'un appel (jusqu'à 120 s).
        """
        silence_annonce = False
        while True:
            await asyncio.sleep(PAS_ATTENTE_S)
            demande = controle.interrompu()
            if not demande and INACTIVITE_PAUSE_S > 0:
                immobile = prog.immobile_depuis()
                if immobile is not None and immobile >= INACTIVITE_PAUSE_S:
                    attente = prog._attente_la_plus_ancienne()
                    detail = (
                        f"plus vieille attente {attente['person_id']}/{attente['activity_id']} "
                        f"({attente['type']}) depuis {attente['depuis_s']:.0f} s"
                        if attente
                        else "aucune attente déclarée — décideur muet ou bloqué"
                    )
                    logger.error(
                        f"[ALARME] [execution] {execution.nom} : {immobile:.0f} s sans avancée "
                        f"(seuil {INACTIVITE_PAUSE_S:.0f} s) — mise en pause automatique ; "
                        f"{prog.deja + prog.traites()}/{prog.attendus} archivées, {detail}"
                    )
                    controle.raison = f"inactivite:{int(immobile)}s"
                    controle.pause = True
                    demande = True
            if demande and controle.grace_echue():
                nb = controle.abandonner_en_vol()
                if nb:
                    logger.warning(
                        f"[execution] {nb} sollicitation(s) en vol abandonnée(s) après "
                        f"{controle.grace_s:.0f} s de grâce — déplacements non archivés, "
                        f"redemandés tels quels à la reprise"
                    )
                elif not silence_annonce:
                    silence_annonce = True
                    logger.info(
                        f"[execution] {execution.nom} : interruption prise, aucune "
                        f"sollicitation en vol à abandonner"
                    )

    async def veiller_quotas() -> None:
        """Garde l'instantané des quotas frais, pour que le décideur cesse d'épingler une
        clé épuisée et entame la suivante (incident du 2026-09-08).

        Tâche à part de `surveiller` : celle-ci tourne toutes les 0,5 s pour la grâce de
        pause et le chien de garde, alors qu'une lecture de `/health` coûte jusqu'à 5 s. Le
        `to_thread` est indispensable — `lire_etat_passerelle` est un `httpx.get` bloquant,
        qui figerait la boucle d'événements, donc la pause et le chien de garde avec elle.

        Fail-open de bout en bout : une passerelle injoignable laisse l'instantané précédent
        en place et ne doit jamais interrompre le run, ni cette veille.
        """
        if moniteur is None or RAFRAICHIR_QUOTAS_S <= 0:
            return
        from experiences.decideurs import rang_en_mots

        precedentes = list(moniteur.instances_disponibles())
        alarme_epuisement = False
        while True:
            await asyncio.sleep(min(RAFRAICHIR_QUOTAS_S, 5.0))
            try:
                lu = await asyncio.to_thread(
                    moniteur.rafraichir_si_perime, RAFRAICHIR_QUOTAS_S
                )
            except Exception as e:  # noqa: BLE001 — la veille ne fait jamais tomber un run
                logger.warning(
                    f"[execution] lecture des quotas impossible ({type(e).__name__}: {e}) — "
                    f"instantané précédent conservé, nouvelle tentative dans "
                    f"{RAFRAICHIR_QUOTAS_S:.0f} s"
                )
                continue
            if not lu:
                continue
            courantes = list(moniteur.instances_disponibles())
            if courantes == precedentes:
                continue  # rien à dire : on ne journalise que les changements
            if courantes:
                # Le RANG dans l'ordre déclaré, jamais le nom : il désigne un compte.
                rang = moniteur.instances.index(courantes[0]) + 1
                logger.warning(
                    f"[execution] {execution.nom} : quotas relus — passage sur la "
                    f"{rang_en_mots(rang)} clé ({rang}/{len(moniteur.instances)}), "
                    f"{len(courantes)} clé(s) encore disponible(s) ; la précédente a épuisé "
                    f"son quota du jour"
                )
                alarme_epuisement = False
            elif not alarme_epuisement:
                # Front montant : une seule alarme, pas une par tour de veille.
                alarme_epuisement = True
                logger.error(
                    f"[ALARME] [execution] {execution.nom} : plus aucune clé disponible — "
                    f"{moniteur.raison_epuisement()}"
                )
            precedentes = courantes

    suivi = asyncio.create_task(prog.boucle())
    garde = asyncio.create_task(surveiller())
    quotas = asyncio.create_task(veiller_quotas())
    try:
        await asyncio.gather(
            *(
                traiter_personne(p, par_personne[p.person_id])
                for p in personnes
                if p.person_id in par_personne
            )
        )
    finally:
        suivi.cancel()
        garde.cancel()
        quotas.cancel()
        prog.ecrire()

    # ── bilan ──
    duree = time.monotonic() - debut
    hors_decision = (
        METHODE_NON_COUVERT,
        METHODE_INEXPLOITABLE,
        D.METHODE_SANS_SOLUTION,
    )
    decides_total = sum(
        1 for t in execution.decisions if t.get("methode") not in hors_decision
    )
    non_couverts_total = sum(
        1 for t in execution.decisions if t.get("methode") == METHODE_NON_COUVERT
    )
    inexploitables = [
        t for t in execution.decisions if t.get("methode") == METHODE_INEXPLOITABLE
    ]
    sans_solution_total = sum(
        1 for t in execution.decisions if t.get("methode") == D.METHODE_SANS_SOLUTION
    )
    attendus_exploitables = len(attendus) - len(inexploitables)
    if inexploitables:
        motifs = Counter(str(t.get("motif_absence")) for t in inexploitables)
        logger.warning(
            f"[execution] {len(inexploitables)} déplacement(s) INEXPLOITABLES exclus des attendus — aucune proposition des "
            f"moteurs ({', '.join(f'{m} × {n}' for m, n in motifs.most_common())}) ; "
            f"personnes : {', '.join(sorted({str(t.get('person_id')) for t in inexploitables})[:10])}"
            f"{'…' if len({t.get('person_id') for t in inexploitables}) > 10 else ''}"
        )
    compteurs = {
        "attendus": len(attendus),
        "inexploitables": len(inexploitables),
        "attendus_exploitables": attendus_exploitables,
        "decides": decides_total,
        "non_couverts": non_couverts_total,
        "sans_solution": sans_solution_total,
        "choix_unique": sum(
            1 for t in execution.decisions if t.get("methode") == D.METHODE_CHOIX_UNIQUE
        ),
        "replis_uniformes": sum(
            1
            for t in execution.decisions
            if t.get("methode") == D.METHODE_REPLI_UNIFORME
        ),
        "attentes": int(sum(prog.attentes_par_type.values())),
        "attentes_par_type": dict(prog.attentes_par_type),
        "erreurs": int(sum(prog.erreurs_par_type.values())),
        "erreurs_par_type": dict(prog.erreurs_par_type),
        "sollicitations": int(prog.compteurs["sollicitations"]),
        "resservies": int(prog.compteurs["resservies"]),
        "substitution_refusee": int(moniteur.compteurs["substitution_refusee"])
        if moniteur
        else 0,
        "couverture": {
            "decides": decides_total,
            "attendus": attendus_exploitables,
            "attendus_bruts": len(attendus),
            "inexploitables_exclus": len(inexploitables),
            "taux": (decides_total / attendus_exploitables)
            if attendus_exploitables
            else None,
        },
        "duree_s": round(duree, 3),
        "quota": (
            {"sans_quota": True}
            if getattr(decideur, "sans_quota", False)
            else (moniteur.tableau() if moniteur else {})
        ),
    }
    execution.ecrire_compteurs(compteurs)
    nb_archivees = len(execution.decisions)
    complet = nb_archivees >= len(attendus)

    if epuise.is_set():
        # Épuisée = reprenable : pas de clôture, l'archive reste ouverte pour la reprise (Q4, Q5).
        execution.ajouter_interruption(
            "epuisement", raison=raison_epuisement.get("raison")
        )
        execution.changer_etat(
            ETAT_EPUISEE,
            raison_epuisement.get("raison"),
            raison_epuisement.get("reprise"),
        )
        logger.error(
            f"[ALARME] [execution] {execution.nom} épuisée — {raison_epuisement.get('raison')} ; "
            f"reprise possible à {raison_epuisement.get('reprise')} ; {nb_archivees}/{len(attendus)} archivées"
        )
        etat = ETAT_EPUISEE
    elif controle.demande_arret():
        execution.ajouter_interruption("arret", raison=controle.raison or "manuelle")
        execution.cloturer(
            ETAT_ARRETEE, f"arrêt demandé — {nb_archivees}/{len(attendus)} archivées"
        )
        etat = ETAT_ARRETEE
    elif controle.demande_pause() and not complet:
        # `raison` distingue la pause voulue de celle décidée par le chien de garde : sans
        # elle, une exécution retrouvée « en pause » ne dit pas si quelqu'un a cliqué ou si
        # elle a cessé d'avancer.
        raison = controle.raison or "manuelle"
        execution.ajouter_interruption("pause", raison=raison)
        auto = raison.startswith("inactivite:")
        execution.changer_etat(
            ETAT_EN_PAUSE,
            (
                f"pause automatique — {raison.split(':', 1)[1]} sans avancée ; "
                f"{nb_archivees}/{len(attendus)} archivées"
                if auto
                else f"pause — {nb_archivees}/{len(attendus)} archivées"
            ),
        )
        etat = ETAT_EN_PAUSE
    elif complet:
        # Plus aucun déplacement n'est sauté (R1) : complet ⇒ terminée. `erreurs` ne compte que des
        # tentatives échouées (toutes suivies d'une décision), plus jamais des trous.
        execution.cloturer(ETAT_TERMINEE)
        etat = ETAT_TERMINEE
    else:
        execution.changer_etat(
            ETAT_EN_PAUSE,
            f"incomplète : {nb_archivees}/{len(attendus)} archivées — reprendre",
        )
        etat = ETAT_EN_PAUSE
    controle.nettoyer()
    execution.fermer()
    try:
        from experiences.registre import ecrire_synthese

        ecrire_synthese(execution.dossier)
    except Exception as e:  # noqa: BLE001 — la synthèse est un rendu, son échec ne perd aucune décision
        logger.warning(f"[execution] synthèse non écrite pour {execution.nom} : {e}")
    if etat == ETAT_TERMINEE:
        # R23 — une exécution clôturée porte son composite sans qu'on le demande. Le calcul
        # est hors-ligne (aucun appel LLM ni réseau) et fail-open : `scorer_a_la_cloture` ne
        # lève pas, un scoring en échec laisse l'exécution terminée sans `scores.json`.
        from experiences import score as _score

        _score.scorer_a_la_cloture(execution.dossier)
    niveau = logger.info if etat == ETAT_TERMINEE else logger.warning
    niveau(
        f"[execution] {'Exécution terminée' if etat == ETAT_TERMINEE else 'Exécution ' + etat} {execution.nom} en {duree:.1f} s — "
        f"décidés {compteurs['decides']}, non couverts {compteurs['non_couverts']}, inexploitables exclus {compteurs['inexploitables']}, "
        f"sans solution {compteurs['sans_solution']}, choix unique {compteurs['choix_unique']}, replis {compteurs['replis_uniformes']}, "
        f"attentes {compteurs['attentes']} · erreurs {compteurs['erreurs']} · "
        f"sollicitations {compteurs['sollicitations']}, resservies {compteurs['resservies']}"
    )
    compteurs["etat"] = etat
    return compteurs


__all__ = [
    "DELAI_GRACE_PAUSE_S",
    "FICHIER_PAUSE",
    "FICHIER_PROGRESSION",
    "FICHIER_STOP",
    "INACTIVITE_PAUSE_S",
    "Controle",
    "Progression",
    "executer",
]
