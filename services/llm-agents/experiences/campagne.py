"""Ticket 074, lot D — une CAMPAGNE : un lot nommé d'expériences rejouées jusqu'au bout.

Ce module **assemble**, il ne réinvente rien. Tout ce qui fait tourner une expérience existe
déjà : `lancer` réserve ses clés et dort jusqu'à la fenêtre de quota (`--attendre-fenetre`,
R4), `reservations` tient la file FIFO, `ordonnanceur.tour()` réconcilie les fantômes et
promeut. Ce qui manquait, c'est ce qui se passe AU-DESSUS : vingt-deux expériences à mener à
terme, dans un ordre qui a un sens, à travers plusieurs renouvellements de quota, sans qu'un
humain soit là pour relancer la suivante à trois heures du matin.

CE QUE LA CAMPAGNE APPORTE, ET RIEN DE PLUS
-------------------------------------------

1. **Des phases.** Une phase ne démarre que si la précédente est close. C'est la seule
   dépendance dont le ticket a besoin, et elle sert à quelque chose de précis : les quatorze
   témoins déterministes ne consomment aucun quota, ils passent donc en premier. Si le
   substrat est cassé, on l'apprend gratuitement, avant d'avoir dépensé le moindre appel LLM.

2. **Un sommeil au niveau du LOT.** `--attendre-fenetre` fait dormir UNE exécution jusqu'à sa
   fenêtre. Mais quand tout ce qui vole dort, la campagne, elle, n'a rien à faire non plus :
   elle le DIT, elle note l'heure de réveil, et elle reprend à l'expérience courante — jamais
   au début. C'est la différence entre « la machine est bloquée » et « la campagne attend
   07:00 UTC, il reste 4 h 12 ».

3. **Un état qui survit à un redémarrage.** `campagnes/<nom>/etat.json` est réécrit à chaque
   transition, atomiquement. Relancer la campagne après un `reboot` reprend où elle en était.

OÙ ÇA TOURNE. Sur l'**hôte**, comme l'ordonnanceur et pour la même raison : le lancement passe
par `docker compose exec`, qui n'a aucun sens depuis l'intérieur du conteneur. La campagne
appelle donc `ordonnanceur.tour()` à chaque tour et devient auto-suffisante — pas besoin de
faire tourner l'ordonnanceur à côté, même si le faire ne gêne pas (le tour est idempotent).

CE QU'ELLE NE FAIT PAS. Elle ne juge pas un résultat : une expérience `terminee` est faite,
point. Le score, la conformité et la comparabilité ont leurs propres outils (`score`,
`registre.comparer`, règle P6), et les mêler à l'ordonnancement rendrait les deux illisibles.

    make campagne-lancer NOM=bascule_anglaise_v6
    make campagne-etat   NOM=bascule_anglaise_v6
    make campagne-arreter NOM=bascule_anglaise_v6
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml
from experiences.archive import (
    ETAT_ARRETEE,
    ETAT_EN_ATTENTE_QUOTA,
    ETAT_EPUISEE,
    ETAT_INTERROMPUE,
    ETAT_TERMINEE,
    F_ETAT,
)
from experiences.chemins import racine_depot
from experiences.experience import dossier_experiences
from loguru import logger

VERSION_CAMPAGNE = "campagne1"

#: Intervalle entre deux tours de pilotage. Cinq secondes serait du bruit : une expérience
#: dure des minutes à des heures, et chaque tour lit une poignée de fichiers.
INTERVALLE_S = 30.0

#: Marge après l'heure de réouverture annoncée. Se réveiller à la seconde près retombe sur un
#: 429 et redort aussitôt — pour rien, en ayant consommé un appel.
MARGE_REVEIL_S = 60

#: Au-delà, ce n'est plus un quota journalier qui nous retient (une fenêtre fait 24 h).
#: Front montant : l'alarme se lève une fois par sommeil, pas à chaque tour.
SOMMEIL_SUSPECT_S = 26 * 3600

#: Temps laissé à une exécution fraîchement lancée pour écrire son premier `etat.json`.
#: Au-delà, c'est que le lancement a échoué avant d'ouvrir son dossier — on le dit et on
#: relance. Deux minutes : `lancer` rejoue les contrôles et charge la population.
DELAI_ECRITURE_ETAT_S = 120.0

#: Nombre d'échecs consécutifs sur la MÊME expérience avant de la déclarer en échec et de
#: passer à la suivante. Deux, parce qu'un échec unique est souvent un service qui redémarre.
TENTATIVES_MAX = 2

#: États depuis lesquels une expérience peut être reprise telle quelle.
ETATS_REPRENABLES = (ETAT_EPUISEE, ETAT_ARRETEE, ETAT_INTERROMPUE)

F_STOP = "STOP"
F_ETAT_CAMPAGNE = "etat.json"


class CampagneInvalide(ValueError):
    """Fichier de campagne absent, illisible, ou qui décrit quelque chose d'impossible."""


# ── Modèle ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Phase:
    nom: str
    experiences: tuple[str, ...]
    raison: str = ""


@dataclass(frozen=True)
class Campagne:
    nom: str
    phases: tuple[Phase, ...]
    note: str = ""
    substrat: dict = field(default_factory=dict)

    @property
    def toutes(self) -> tuple[str, ...]:
        return tuple(e for p in self.phases for e in p.experiences)

    def phase_de(self, exp: str) -> str | None:
        for p in self.phases:
            if exp in p.experiences:
                return p.nom
        return None


def dossier_campagnes() -> Path:
    return Path(os.getenv("CAMPAGNES_DIR") or (racine_depot() / "campagnes"))


def chemin_definition(nom: str) -> Path:
    return dossier_campagnes() / f"{nom}.yaml"


def dossier_etat(nom: str) -> Path:
    return dossier_campagnes() / nom


def charger(nom: str) -> Campagne:
    """Lit `campagnes/<nom>.yaml` et le VALIDE.

    Refuse plutôt que de corriger : une campagne qui nomme une expérience inexistante
    s'arrêterait au milieu, après avoir dépensé le quota des précédentes.
    """
    chemin = chemin_definition(nom)
    if not chemin.is_file():
        connues = (
            sorted(p.stem for p in dossier_campagnes().glob("*.yaml"))
            if dossier_campagnes().is_dir()
            else []
        )
        raise CampagneInvalide(
            f"campagne introuvable : {chemin}. "
            + (
                f"Connues : {', '.join(connues)}."
                if connues
                else "Aucune campagne définie dans campagnes/."
            )
        )
    try:
        doc = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise CampagneInvalide(f"{chemin.name} illisible : {e}") from e
    if doc.get("version") != VERSION_CAMPAGNE:
        raise CampagneInvalide(
            f"{chemin.name} en version {doc.get('version')!r}, attendu {VERSION_CAMPAGNE!r}."
        )

    phases: list[Phase] = []
    vues: set[str] = set()
    for i, brut in enumerate(doc.get("phases") or []):
        exps = tuple(str(e) for e in (brut.get("experiences") or []))
        if not exps:
            raise CampagneInvalide(
                f"{chemin.name} : la phase {brut.get('nom') or i} ne porte aucune expérience. "
                "Une phase vide bloquerait la suivante sans rien dire."
            )
        doublons = sorted(set(exps) & vues)
        if doublons:
            raise CampagneInvalide(
                f"{chemin.name} : {doublons} apparaissent dans deux phases. Une expérience "
                "menée deux fois dans la même campagne écraserait sa propre exécution."
            )
        vues |= set(exps)
        phases.append(
            Phase(
                nom=str(brut.get("nom") or f"phase{i + 1}"),
                experiences=exps,
                raison=str(brut.get("raison") or ""),
            )
        )
    if not phases:
        raise CampagneInvalide(f"{chemin.name} ne porte aucune phase.")

    campagne = Campagne(
        nom=str(doc.get("nom") or nom),
        phases=tuple(phases),
        note=str(doc.get("note") or ""),
        substrat=doc.get("substrat") or {},
    )
    manquantes = [
        e
        for e in campagne.toutes
        if not (dossier_experiences() / e / "experience.yaml").is_file()
    ]
    if manquantes:
        raise CampagneInvalide(
            f"{chemin.name} nomme {len(manquantes)} expérience(s) qui n'existent pas dans "
            f"{dossier_experiences()} : {manquantes[:5]}"
            + (" …" if len(manquantes) > 5 else "")
            + "\nDéfinissez-les d'abord (`make experience-definir`) : une campagne qui "
            "s'arrête au milieu a déjà dépensé le quota de ce qui précède."
        )
    return campagne


# ── Lecture de l'avancement, sur le disque ───────────────────────────────────


def _iso(moment: datetime | None = None) -> str:
    return (moment or datetime.now(timezone.utc)).isoformat(timespec="seconds")


def derniere_execution(exp: str) -> Path | None:
    """Dossier de la dernière exécution d'une expérience, ou None.

    Les dossiers d'exécution sont horodatés (`2026-09-14_22_43_19`) : l'ordre lexical EST
    l'ordre chronologique, et le rester est une propriété du format, pas une chance.
    """
    executions = dossier_experiences() / exp / "executions"
    if not executions.is_dir():
        return None
    candidats = sorted(p for p in executions.iterdir() if p.is_dir())
    return candidats[-1] if candidats else None


def etat_experience(exp: str) -> dict:
    """État de la dernière exécution : `{etat, raison, depuis, dossier}`.

    `etat` vaut `"definie"` quand l'expérience n'a jamais tourné — c'est un état réel du
    vocabulaire de la plateforme, pas un repli inventé ici.
    """
    dossier = derniere_execution(exp)
    if dossier is None:
        return {"etat": "definie", "raison": None, "depuis": None, "dossier": None}
    fichier = dossier / F_ETAT
    try:
        brut = json.loads(fichier.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # Une exécution qui vient de naître n'a pas encore écrit son état. Ce n'est pas une
        # anomalie : on le dit « en_cours » plutôt que de la compter faite ou échouée.
        return {
            "etat": "en_cours",
            "raison": "état non encore écrit",
            "depuis": None,
            "dossier": str(dossier),
        }
    return {
        "etat": brut.get("etat", "?"),
        "raison": brut.get("raison"),
        "depuis": brut.get("maj"),
        "dossier": str(dossier),
    }


# ── État persistant de la campagne ───────────────────────────────────────────


def etat_par_defaut(campagne: Campagne) -> dict:
    return {
        "campagne": campagne.nom,
        "version": VERSION_CAMPAGNE,
        "demarree_le": _iso(),
        "maj": _iso(),
        "phase_courante": campagne.phases[0].nom,
        "courante": None,
        "faites": [],
        "restantes": list(campagne.toutes),
        "echouees": {},
        "sommeils": [],
        "pid": os.getpid(),
        "terminee_le": None,
    }


def lire_etat(nom: str) -> dict | None:
    chemin = dossier_etat(nom) / F_ETAT_CAMPAGNE
    if not chemin.is_file():
        return None
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"[campagne] état illisible ({chemin}) : {e} — repart de zéro")
        return None


def ecrire_etat(nom: str, etat: dict) -> None:
    """Écriture ATOMIQUE. Un `etat.json` tronqué par une coupure de courant ferait repartir
    la campagne du début, c'est-à-dire redépenser tout le quota déjà consommé."""
    base = dossier_etat(nom)
    base.mkdir(parents=True, exist_ok=True)
    etat["maj"] = _iso()
    temp = base / f".{F_ETAT_CAMPAGNE}.tmp"
    temp.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temp, base / F_ETAT_CAMPAGNE)


def demande_arret(nom: str) -> bool:
    return (dossier_etat(nom) / F_STOP).exists()


def arreter(nom: str) -> bool:
    """Pose le drapeau d'arrêt. L'exécution en vol se termine ; aucune autre n'est lancée."""
    base = dossier_etat(nom)
    base.mkdir(parents=True, exist_ok=True)
    (base / F_STOP).write_text(_iso() + "\n", encoding="utf-8")
    logger.info(f"[campagne] {nom} : arrêt demandé — l'exécution en cours se termine")
    return True


def _lever_arret(nom: str) -> None:
    (dossier_etat(nom) / F_STOP).unlink(missing_ok=True)


# ── Fenêtre de quota ─────────────────────────────────────────────────────────


def prochain_reveil(maintenant: datetime | None = None) -> tuple[str, int]:
    """Prochaine réouverture de quota, en ISO UTC, et le nombre de secondes d'ici là.

    On prend le MINIMUM sur les fuseaux en jeu : dormir jusqu'au plus tardif ferait perdre
    les heures pendant lesquelles un autre fournisseur a déjà rouvert. Le défaut Pacifique
    est celui du free tier Gemini (`ressources.FUSEAU_QUOTA_DEFAUT`) ; UTC est ajouté parce
    que c'est le repli de la passerelle quand un fournisseur ne déclare pas de fuseau.
    """
    from experiences.ressources import FUSEAU_QUOTA_DEFAUT
    from llm_gateway.core.quota import next_quota_reset

    now = maintenant or datetime.now(timezone.utc)
    candidats = [next_quota_reset(f, now) for f in (FUSEAU_QUOTA_DEFAUT, None)]
    tot = min(candidats)
    return tot.isoformat(timespec="seconds"), max(0, int((tot - now).total_seconds()))


# ── La boucle de pilotage ────────────────────────────────────────────────────


def _lancer_experience(exp: str) -> None:
    """Démarre une expérience, détachée, par le même chemin que l'ordonnanceur.

    On ne réimplémente pas le lancement : `ordonnanceur._lancer_detache` sait déjà passer
    par `docker compose exec`, et `lancer` sait déjà réserver ses clés ou se mettre en file.
    `attendre_fenetre` n'est pas transmis : c'est le DÉFAUT du runner, et l'ordonnanceur ne
    transmet que son refus explicite.
    """
    from experiences import ordonnanceur as O

    O._lancer_detache({"exp": exp, "args": {"reprendre": True}})


def _tour_ordonnanceur() -> None:
    """Réconcilie les fantômes et promeut la file.

    La campagne appelle le tour elle-même pour être auto-suffisante : sans cela, une
    expérience mise en file par un conflit de clé y resterait jusqu'à ce qu'un humain
    lance `make experience-ordonnancer`. Le tour est idempotent, donc faire tourner
    l'ordonnanceur à côté ne gêne pas.
    """
    from experiences import ordonnanceur as O

    try:
        O.tour()
    except Exception as e:  # noqa: BLE001 — un tour raté ne doit pas tuer la campagne
        logger.warning(f"[campagne] tour d'ordonnanceur en échec : {e}")


@dataclass
class _Vue:
    """Ce que la campagne voit à un instant t, une fois les états lus sur le disque."""

    faites: list[str] = field(default_factory=list)
    en_vol: list[str] = field(default_factory=list)
    dorment: list[str] = field(default_factory=list)   # en_vol ET en attente de quota
    a_reprendre: list[str] = field(default_factory=list)
    jamais_lancees: list[str] = field(default_factory=list)


def _observer(experiences: list[str], echouees: dict) -> _Vue:
    vue = _Vue()
    for exp in experiences:
        if exp in echouees:
            continue
        etat = etat_experience(exp)["etat"]
        if etat == ETAT_TERMINEE:
            vue.faites.append(exp)
        elif etat == "definie":
            vue.jamais_lancees.append(exp)
        elif etat in ETATS_REPRENABLES:
            vue.a_reprendre.append(exp)
        else:  # en_cours, en_pause, en_attente_quota, en_attente_agent
            vue.en_vol.append(exp)
            if etat == ETAT_EN_ATTENTE_QUOTA:
                vue.dorment.append(exp)
    return vue


def lancer(
    nom: str,
    *,
    reprendre: bool = True,
    intervalle_s: float = INTERVALLE_S,
    max_tours: int | None = None,
    dormir: Callable[[float], None] = time.sleep,
) -> int:
    """Mène la campagne à son terme. Rend 0 au succès, 1 si des expériences ont échoué,
    130 si l'arrêt a été demandé.

    `max_tours` et `dormir` existent pour les tests : la logique est la même, seul le temps
    est injecté. Une boucle qui ne se teste qu'en attendant vraiment trente secondes ne se
    teste pas.
    """
    campagne = charger(nom)
    _lever_arret(nom)

    etat = (lire_etat(nom) if reprendre else None) or etat_par_defaut(campagne)
    etat["pid"] = os.getpid()
    if reprendre and etat.get("terminee_le"):
        logger.info(f"[campagne] {nom} était déjà terminée le {etat['terminee_le']} — "
                    "relancez avec --recommencer pour la rejouer.")
        return 0
    ecrire_etat(nom, etat)

    total = len(campagne.toutes)
    logger.info(
        f"[campagne] {nom} démarrée — {total} expérience(s) en {len(campagne.phases)} phase(s) : "
        + " · ".join(f"{p.nom} ({len(p.experiences)})" for p in campagne.phases)
    )
    if campagne.note:
        logger.info(f"[campagne] {campagne.note}")

    tours = 0
    tentatives: dict[str, int] = {}
    depuis: dict[str, float] = {}
    alarme_sommeil = False
    # Une expérience qu'on vient de lancer n'a pas encore écrit son `etat.json` : le temps
    # que `lancer` démarre, réserve ses clés et ouvre son dossier d'exécution, elle se lit
    # encore « definie ». Sans ce délai de grâce, la campagne la relançait à chaque tour —
    # et une expérience lancée deux fois écrase sa propre exécution.
    lancees: dict[str, float] = {}

    while True:
        if max_tours is not None and tours >= max_tours:
            logger.info(f"[campagne] {nom} : {max_tours} tours atteints (mode borné) — sortie")
            return 0
        tours += 1

        if demande_arret(nom):
            logger.info(f"[campagne] {nom} ARRÊTÉE sur demande — {len(etat['faites'])}/{total} "
                        "faites ; l'exécution en cours se termine seule.")
            ecrire_etat(nom, etat)
            return 130

        _tour_ordonnanceur()

        # ── Où en est-on ? ────────────────────────────────────────────────────
        phase = next((p for p in campagne.phases if p.nom == etat["phase_courante"]), None)
        if phase is None:  # phase disparue du fichier entre deux lancements
            raise CampagneInvalide(
                f"l'état de {nom} désigne la phase {etat['phase_courante']!r}, absente du "
                "fichier de campagne. Corrigez le fichier, ou relancez avec --recommencer.")
        vue = _observer(list(phase.experiences), etat["echouees"])
        # Ce qu'on vient de lancer compte comme en vol tant que son état n'est pas écrit.
        for exp, quand in list(lancees.items()):
            if exp in vue.faites or exp in vue.en_vol or exp in vue.a_reprendre:
                lancees.pop(exp, None)
            elif time.time() - quand > DELAI_ECRITURE_ETAT_S:
                lancees.pop(exp, None)
                logger.warning(
                    f"[campagne] {exp} lancée il y a plus de "
                    f"{DELAI_ECRITURE_ETAT_S:.0f} s sans avoir écrit d'état — on la relance.")
            elif exp in vue.jamais_lancees:
                vue.jamais_lancees.remove(exp)
                vue.en_vol.append(exp)

        for exp in vue.faites:
            if exp not in etat["faites"]:
                duree = time.time() - depuis.pop(exp, time.time())
                etat["faites"].append(exp)
                etat["restantes"] = [e for e in etat["restantes"] if e != exp]
                if etat.get("courante") == exp:
                    etat["courante"] = None
                logger.info(
                    f"[campagne] ✅ {exp} terminée en {duree:.0f} s — "
                    f"{len(etat['faites'])}/{total} faites, "
                    f"{len(etat['restantes'])} restantes, {len(etat['echouees'])} en échec")
                ecrire_etat(nom, etat)

        # ── Phase close ? ─────────────────────────────────────────────────────
        reste = [e for e in phase.experiences
                 if e not in etat["faites"] and e not in etat["echouees"]]
        if not reste:
            suivantes = [p for p in campagne.phases
                         if campagne.phases.index(p) > campagne.phases.index(phase)]
            if not suivantes:
                etat["terminee_le"] = _iso()
                etat["courante"] = None
                ecrire_etat(nom, etat)
                echecs = len(etat["echouees"])
                logger.info(
                    f"[campagne] {nom} TERMINÉE — {len(etat['faites'])}/{total} faites, "
                    f"{echecs} en échec, {len(etat['sommeils'])} mise(s) en sommeil, "
                    f"{tours} tour(s).")
                if echecs:
                    for exp, det in etat["echouees"].items():
                        logger.error(f"[campagne] échec non résolu : {exp} — {det.get('motif')}")
                    return 1
                return 0
            etat["phase_courante"] = suivantes[0].nom
            ecrire_etat(nom, etat)
            logger.info(f"[campagne] phase {phase.nom!r} close — passage à "
                        f"{suivantes[0].nom!r} ({len(suivantes[0].experiences)} expériences)"
                        + (f" : {suivantes[0].raison}" if suivantes[0].raison else ""))
            continue

        # ── Reprises et échecs ────────────────────────────────────────────────
        for exp in vue.a_reprendre:
            tentatives[exp] = tentatives.get(exp, 0) + 1
            motif = etat_experience(exp).get("raison") or etat_experience(exp)["etat"]
            if tentatives[exp] > TENTATIVES_MAX:
                etat["echouees"][exp] = {"motif": str(motif),
                                         "tentatives": tentatives[exp], "le": _iso()}
                etat["restantes"] = [e for e in etat["restantes"] if e != exp]
                if etat.get("courante") == exp:
                    etat["courante"] = None
                logger.error(
                    f"[ALARME] [campagne] {exp} échoue pour la {tentatives[exp]}ᵉ fois "
                    f"({motif}) — déclarée en échec, la campagne passe à la suivante. "
                    "Les expériences restantes ne sont PAS annulées.")
                ecrire_etat(nom, etat)
            else:
                logger.info(f"[campagne] ↻ reprise de {exp} "
                            f"(tentative {tentatives[exp]}/{TENTATIVES_MAX}, motif : {motif})")
                depuis[exp] = time.time()
                etat["courante"] = exp
                ecrire_etat(nom, etat)
                lancees[exp] = time.time()
                _lancer_experience(exp)
            vue.en_vol.append(exp)

        # ── Sommeil de quota : tout ce qui vole dort ──────────────────────────
        if vue.en_vol and vue.dorment and len(vue.dorment) == len(vue.en_vol):
            quand, secondes = prochain_reveil()
            if secondes > SOMMEIL_SUSPECT_S and not alarme_sommeil:
                alarme_sommeil = True
                logger.error(
                    f"[ALARME] [campagne] {nom} dormirait {secondes / 3600:.1f} h — une "
                    "fenêtre de quota en fait 24. Ce n'est probablement pas un quota : "
                    "vérifiez l'horloge de la machine et les fuseaux des fournisseurs.")
            etat["sommeils"].append({"depuis": _iso(), "jusqu": quand, "duree_s": secondes,
                                     "motif": f"quota épuisé sur {len(vue.dorment)} "
                                              f"exécution(s) en vol"})
            ecrire_etat(nom, etat)
            logger.info(
                f"[campagne] 💤 {nom} en sommeil : les {len(vue.dorment)} exécution(s) en vol "
                f"attendent toutes la fenêtre de quota. Réveil à {quand} "
                f"(dans {secondes / 3600:.1f} h). La reprise se fera sur l'expérience "
                "courante, pas au début.")
            dormir(min(secondes + MARGE_REVEIL_S, 3600))
            continue
        alarme_sommeil = False

        # ── Rien en vol ? On lance la suivante ────────────────────────────────
        if not vue.en_vol:
            suivante = next((e for e in phase.experiences if e in reste), None)
            if suivante is not None:
                depuis[suivante] = time.time()
                etat["courante"] = suivante
                ecrire_etat(nom, etat)
                logger.info(
                    f"[campagne] ▶ {suivante} (phase {phase.nom}, "
                    f"{len(etat['faites']) + 1}/{total})")
                lancees[suivante] = time.time()
                _lancer_experience(suivante)

        if tours % 20 == 0:
            logger.info(
                f"[campagne] {nom} vivante — {len(etat['faites'])}/{total} faites, "
                f"en vol : {vue.en_vol or '—'}, {tours} tours")
        dormir(intervalle_s)


# ── Lecture pour affichage (CLI et tableau de bord) ──────────────────────────


def etat_lisible(nom: str) -> dict:
    """Tout ce qu'il faut pour afficher une campagne, sans rien décider.

    Ne lève pas quand la campagne n'a jamais tourné : `etat` vaut alors None et l'appelant
    le dit — une campagne définie mais jamais lancée n'est pas une erreur.
    """
    campagne = charger(nom)
    etat = lire_etat(nom)
    quand, secondes = prochain_reveil()
    par_experience = {e: etat_experience(e) for e in campagne.toutes}
    faites = [e for e, s in par_experience.items() if s["etat"] == ETAT_TERMINEE]
    return {
        "nom": campagne.nom,
        "note": campagne.note,
        "substrat": campagne.substrat,
        "phases": [{"nom": p.nom, "raison": p.raison,
                    "experiences": list(p.experiences),
                    "faites": [e for e in p.experiences if e in faites]}
                   for p in campagne.phases],
        "total": len(campagne.toutes),
        "faites": faites,
        "etat": etat,
        "arret_demande": demande_arret(nom),
        "par_experience": par_experience,
        "prochain_reveil": quand,
        "secondes_avant_reveil": secondes,
    }


__all__ = [
    "INTERVALLE_S",
    "VERSION_CAMPAGNE",
    "Campagne",
    "CampagneInvalide",
    "Phase",
    "arreter",
    "etat_lisible",
    "lancer",
    "charger",
    "chemin_definition",
    "derniere_execution",
    "dossier_campagnes",
    "dossier_etat",
    "ecrire_etat",
    "etat_experience",
    "etat_par_defaut",
    "lire_etat",
    "prochain_reveil",
]
