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
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml
from experiences import refus as REFUS
from experiences.archive import (
    ETAT_ARRETEE,
    ETAT_EN_ATTENTE_QUOTA,
    ETAT_EN_PAUSE,
    ETAT_EPUISEE,
    ETAT_INTERROMPUE,
    ETAT_TERMINEE,
    F_ETAT,
    F_EXECUTION,
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

# Nombre de passes de REPÊCHAGE en fin de campagne. Une passe reprend tout ce qui a été
# reporté (quota épuisé alors qu'autre chose pouvait tourner) et tout ce qui a échoué, les
# compteurs de tentatives remis à zéro. Deux passes suffisent : la première rattrape le quota
# d'un fournisseur renouvelé entre-temps, la seconde couvre un second épuisement. Au-delà, ce
# n'est plus un quota, c'est une panne — et une campagne qui boucle sans fin ne se voit pas.
REPECHAGES_MAX = 2

#: États depuis lesquels une expérience peut être reprise telle quelle.
ETATS_REPRENABLES = (ETAT_EPUISEE, ETAT_ARRETEE, ETAT_INTERROMPUE)

#: Préfixe de la `raison` d'interruption posée par le chien de garde d'inactivité
#: (`runner`, `inactivite:<N>s`). C'est la trace STRUCTURÉE de la pause subie : le message
#: de `etat.json`, lui, est écrit pour des humains et peut être reformulé sans préavis.
RAISON_PAUSE_SUBIE = "inactivite:"

#: Au-delà, une expérience que la campagne croit « en vol » n'a plus donné signe de vie
#: depuis trop longtemps pour que ce soit un calcul lent : son état n'a pas bougé d'un
#: octet. Front montant, une alarme par expérience — la campagne ne tue rien, elle le DIT.
#: Trente minutes : une exécution vivante réécrit son `etat.json` à chaque archivage, et le
#: chien de garde du runner met en pause dès 420 s sans avancée.
EN_VOL_FIGE_S = 1800.0

F_STOP = "STOP"
F_ETAT_CAMPAGNE = "etat.json"

#: Ce qu'on doit retrouver dans la ligne de commande d'un pid pour le reconnaître comme une
#: campagne en cours, et non comme un pid recyclé par le système.
SIGNATURE_LANCEMENT = "campagne-lancer"

#: Code de sortie d'un lancement refusé parce que la campagne tourne déjà. Distinct de 1
#: (des expériences ont échoué) et de 130 (arrêt demandé) : ici rien n'a été tenté.
CODE_DEJA_EN_VOL = 3


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
    #: expérience → commande de lancement dédiée, quand `experiences lancer` ne convient pas.
    #: Le cas connu est le témoin random forest : la règle R7 du ticket 044 le tient HORS de
    #: `decideur_modele.FAMILLES` pour qu'il ne devienne pas un arbitre, et son lanceur
    #: dédié inscrit sa famille le temps de son propre processus. Sans cette échappatoire,
    #: la campagne le relançait indéfiniment sur un « Format d'artefact inattendu ».
    lanceurs: dict = field(default_factory=dict)

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
        lanceurs={str(k): list(v) for k, v in (doc.get("lanceurs") or {}).items()},
    )
    hors_campagne = sorted(set(campagne.lanceurs) - set(campagne.toutes))
    if hors_campagne:
        raise CampagneInvalide(
            f"{chemin.name} : `lanceurs` désigne {hors_campagne}, qui ne sont dans aucune "
            "phase. Un lanceur pour une expérience absente ne servira jamais et masque une "
            "faute de frappe.")
    from experiences.experience import trouver_dossier_experience

    manquantes = [
        e
        for e in campagne.toutes
        if not ((dossier_experiences() / e / "experience.yaml").is_file() or (trouver_dossier_experience(e) and (trouver_dossier_experience(e) / "experience.yaml").is_file()))
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


def _fige_depuis(infos: dict) -> float | None:
    """Secondes écoulées depuis la dernière écriture de l'état, ou None si indatable.

    Une exécution vivante réécrit son `etat.json` en avançant. Un état qui ne bouge plus
    est donc une exécution qui n'avance plus — sans avoir à tester la vie d'un pid, ce que
    la campagne ne peut pas faire depuis l'hôte : les pid des exécutions appartiennent au
    namespace du conteneur.
    """
    depuis = infos.get("depuis")
    if not depuis:
        return None
    try:
        quand = datetime.fromisoformat(str(depuis))
    except ValueError:
        return None
    if quand.tzinfo is None:
        quand = quand.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - quand).total_seconds()


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
        # Reportées : mises de côté parce que LEUR quota était épuisé alors que d'autres
        # expériences pouvaient encore tourner. Ce n'est pas un échec — elles repassent à la
        # passe de repêchage. Dormir 24 h devant une file pleine était le vrai défaut.
        "reportees": {},
        "repechages": 0,
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


# ── Un seul lancement à la fois ──────────────────────────────────────────────


def _ligne_de_commande(pid: int) -> str | None:
    """La ligne de commande du processus `pid`, ou None — soit qu'il n'existe plus, soit
    qu'on n'ait pas pu le demander. Les deux cas rendent None À DESSEIN : le garde-fou
    ci-dessous échoue OUVERT. Un doute sur l'état d'un pid ne doit jamais empêcher une
    campagne de démarrer ; il n'y a qu'une seule chose pire que deux campagnes en parallèle,
    c'est zéro campagne parce qu'un `ps` a hoqueté."""
    try:
        vu = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning(
            f"[campagne] pid {pid} non interrogeable ({e}) — le garde-fou du double "
            "lancement laisse passer, à vous de vérifier qu'aucune campagne ne tourne déjà.")
        return None
    return vu.stdout.strip() or None


def _est_lancement_de(ligne: str, nom: str) -> bool:
    """Cette ligne de commande est-elle un `campagne-lancer` de la campagne `nom` ?

    On compare le nom sur le JETON qui suit `--nom`, pas en sous-chaîne : une campagne
    nommée `c` se reconnaîtrait dans à peu près n'importe quoi, à commencer par le nom de
    toutes les autres.
    """
    if SIGNATURE_LANCEMENT not in ligne:
        return False
    jetons = ligne.replace("--nom=", "--nom ").split()
    return any(a == "--nom" and b == nom for a, b in zip(jetons, jetons[1:]))


def campagne_en_vol(nom: str) -> int | None:
    """Le pid d'un `campagne-lancer {nom}` DÉJÀ en cours sur cette machine, sinon None.

    Pourquoi : deux processus lancés sur la même campagne écrivent le MÊME `etat.json`, à
    tour de rôle, sans se voir. Le 2026-09-16, deux lancements à vingt minutes d'intervalle
    se sont disputé les mêmes expériences pendant une demi-journée, en ont marqué deux
    « arrêt demandé — 0/3299 archivées », puis ont déclaré la campagne TERMINÉE alors qu'un
    bras n'avait jamais tourné. Rien dans le journal ne le disait.

    Le pid seul ne suffit pas à conclure : le système les recycle. On confirme sur la ligne
    de commande, qui doit porter `campagne-lancer` ET le nom de la campagne.
    """
    etat = lire_etat(nom)
    if not etat or etat.get("terminee_le"):
        return None
    pid = etat.get("pid")
    if not isinstance(pid, int) or pid == os.getpid():
        return None
    ligne = _ligne_de_commande(pid)
    if not ligne or not _est_lancement_de(ligne, nom):
        return None
    return pid


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


def journal_lancement(exp: str) -> Path:
    """Où va la sortie d'un lancement détaché.

    Elle allait dans `/dev/null`, et c'est ainsi que le premier lancement de chaque
    expérience a échoué SANS UN MOT le 2026-09-15 : `lancer --reprendre` refuse quand il n'y
    a rien à reprendre, il le disait sur sa sortie standard, et personne ne la lisait. Un
    lancement détaché dont on jette la sortie est un lancement dont on ignore le sort.
    """
    base = dossier_experiences() / exp / "lancements"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{datetime.now(timezone.utc):%Y-%m-%d_%H_%M_%S}.log"


def _lancer_experience(exp: str, lanceurs: dict | None = None) -> None:
    """Démarre une expérience, détachée, par le même chemin que l'ordonnanceur.

    On ne réimplémente pas le lancement : `lancer` sait réserver ses clés ou se mettre en
    file, et `attendre_fenetre` est son défaut — l'ordonnanceur ne transmet que son refus.

    `--reprendre` N'EST PASSÉ QUE S'IL Y A DE QUOI REPRENDRE. La CLI refuse le drapeau sur
    une expérience qui n'a jamais tourné (« rien à reprendre : aucune exécution pour cette
    expérience »), et le passer d'office faisait échouer le PREMIER lancement de chacune des
    vingt — donc la campagne entière, sur sa toute première action.
    """
    from experiences import ordonnanceur as O

    dedie = (lanceurs or {}).get(exp)
    if dedie:
        argv = [str(m).replace("{exp}", exp) for m in dedie]
        logger.info(f"[campagne] lancement DÉDIÉ de {exp} : {' '.join(argv)}")
    else:
        reprendre = derniere_execution(exp) is not None
        argv = O._argv_lancer({"exp": exp, "args": {"reprendre": reprendre}})
    sortie = journal_lancement(exp)
    if not dedie:
        logger.info(f"[campagne] lancement de {exp}"
                    f"{' (reprise)' if reprendre else ' (première exécution)'} — "
                    f"sortie dans {sortie.parent.name}/{sortie.name}")
    with sortie.open("w", encoding="utf-8") as flux:
        subprocess.Popen(
            argv, cwd=str(racine_depot()), stdout=flux, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True,
            env={**os.environ, "TERM": "dumb", "NO_COLOR": "1", "PYTHONUNBUFFERED": "1"},
        )


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


def _refus_du_dernier_lancement(exp: str) -> tuple[str | None, list[str]]:
    """Ce que le dernier lancement refusé a déposé, ou `(None, [])` s'il n'a rien dit.

    On ne lit QUE le marqueur le plus récent, et seulement s'il est postérieur au dernier
    journal de lancement : un marqueur d'hier ne dit rien du lancement d'aujourd'hui.
    """
    base = dossier_experiences() / exp / "lancements"
    if not base.is_dir():
        return None, []
    marqueurs = sorted(base.glob(f"*{REFUS.SUFFIXE_MARQUEUR}"))
    if not marqueurs:
        return None, []
    journaux = sorted(p for p in base.glob("*.log"))
    if journaux and journaux[-1].stem > marqueurs[-1].name.split(".")[0]:
        return None, []
    try:
        contenu = json.loads(marqueurs[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, []
    return contenu.get("classe"), list(contenu.get("motifs") or [])


def _reporter_experience(exp: str) -> bool:
    """Arrête une expérience endormie sur son quota, pour rendre la main à la suivante.

    Passe par le fichier STOP de son dossier d'exécution — le mécanisme d'arrêt existant, que
    le runner surveille déjà. L'exécution se clôt en `arretee`, donc reprenable : c'est ce qui
    permet à la passe de repêchage de la relancer là où elle s'était arrêtée, sans rien perdre.
    """
    dossier = derniere_execution(exp)
    if dossier is None:
        return False
    try:
        (dossier / "STOP").write_text(
            "campagne: quota épuisé, expérience reportée à la passe de repêchage\n",
            encoding="utf-8",
        )
    except OSError as exc:  # pragma: no cover - dépend du système de fichiers
        logger.error(f"[campagne] report de {exp} impossible ({exc})")
        return False
    return True


def _reste_ailleurs(
    campagne: Campagne, etat: dict, phase: Phase, en_vol: list[str]
) -> list[str]:
    """Ce qui pourrait tourner MAINTENANT si on laissait tomber ce qui dort sur son quota.

    La phase courante d'abord, puis toutes les suivantes : un quota épuisé chez un fournisseur
    ne dit rien des autres, et une campagne multi-fournisseurs n'a aucune raison d'attendre
    la fenêtre de l'un pour lancer les bras de l'autre.
    """
    index = campagne.phases.index(phase)
    a_venir = [phase, *campagne.phases[index + 1:]]
    return [
        e
        for p in a_venir
        for e in p.experiences
        if e not in etat["faites"]
        and e not in etat["echouees"]
        and e not in etat["reportees"]
        # Ce qui vole DÉJÀ n'est pas « autre chose à faire » : sans cette exclusion, les
        # expériences endormies se compteraient elles-mêmes comme une alternative à
        # elles-mêmes, et la campagne ne dormirait jamais.
        and e not in en_vol
    ]


def _pause_est_subie(dossier: str | Path | None) -> bool:
    """Cette exécution en pause attend-elle qu'on la reprenne, ou qu'on la laisse ?

    `en_pause` recouvre trois situations que le runner distingue, mais que l'état seul
    confond :

    * le **chien de garde** a coupé après 420 s sans avancée — le processus est mort, plus
      personne ne la reprendra ;
    * l'exécution s'est arrêtée **incomplète** sans que personne ne demande de pause — même
      chose, son propre message dit « reprendre » ;
    * un **humain** a demandé la pause — elle attend une décision humaine, pas la campagne.

    Les deux premières sont *subies* : la campagne les reprend. La troisième ne se reprend
    pas dans le dos de celui qui l'a demandée. Le discriminant est la trace structurée
    `interruptions[].raison`, pas le message de `etat.json` : celui-ci s'adresse à des
    humains et peut être reformulé sans que rien ne casse visiblement.

    Mesuré le 2026-09-16 : sans cette distinction, une pause de chien de garde figeait la
    campagne pour de bon — comptée « en vol », elle n'était ni reprise, ni déclarée en échec,
    et les expériences derrière elle n'étaient jamais lancées. Six heures de silence.

    Un `execution.yaml` illisible ou absent rend `True`. Un blocage silencieux et sans borne
    est pire qu'une reprise de trop : la reprise est plafonnée par `TENTATIVES_MAX`, après
    quoi l'expérience est déclarée en échec et la campagne continue. Le blocage, lui, n'a
    aucun plafond.
    """
    if dossier is None:
        return True
    try:
        config = yaml.safe_load((Path(dossier) / F_EXECUTION).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return True
    if not isinstance(config, dict):
        return True
    pauses = [
        i
        for i in (config.get("interruptions") or [])
        if isinstance(i, dict) and i.get("cause") == "pause"
    ]
    if not pauses:
        # Aucune pause demandée, et pourtant l'exécution est en pause : c'est le cas
        # « incomplète — reprendre » du runner.
        return True
    return str(pauses[-1].get("raison") or "").startswith(RAISON_PAUSE_SUBIE)


def _observer(experiences: list[str], echouees: dict, reportees: dict | None = None) -> _Vue:
    vue = _Vue()
    reportees = reportees or {}
    for exp in experiences:
        if exp in echouees or exp in reportees:
            continue
        infos = etat_experience(exp)
        etat = infos["etat"]
        if etat == ETAT_TERMINEE:
            vue.faites.append(exp)
        elif etat == "definie":
            vue.jamais_lancees.append(exp)
        elif etat in ETATS_REPRENABLES or (
            etat == ETAT_EN_PAUSE and _pause_est_subie(infos["dossier"])
        ):
            vue.a_reprendre.append(exp)
        else:  # en_cours, pause demandée, en_attente_quota, en_attente_agent
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

    # AVANT de toucher quoi que ce soit — en particulier avant de lever le drapeau d'arrêt,
    # qu'un second lancement effacerait sous les pieds du premier.
    deja = campagne_en_vol(nom)
    if deja is not None:
        logger.error(
            f"[ALARME] [campagne] {nom} TOURNE DÉJÀ (pid {deja}) — ce lancement s'arrête "
            "sans rien toucher. Deux processus sur la même campagne écrivent le même "
            "etat.json sans se voir : ils se disputent les expériences et finissent par en "
            f"déclarer perdues qui n'ont jamais tourné. Suivre celle qui tourne : "
            f"make campagne-etat NOM={nom} — l'arrêter : make campagne-arreter NOM={nom}")
        return CODE_DEJA_EN_VOL

    _lever_arret(nom)

    etat = (lire_etat(nom) if reprendre else None) or etat_par_defaut(campagne)
    # Un état écrit avant l'introduction du report ne porte pas ces clés : les poser ici évite
    # de faire dépendre la reprise d'une migration de fichier.
    etat.setdefault("reportees", {})
    etat.setdefault("repechages", 0)
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
    # Front montant de l'alarme « en vol mais figé », une entrée par expérience : sans elle
    # le message repartirait à chaque tour, soit deux fois par minute, et noierait le journal
    # qu'il est censé rendre lisible.
    alarme_en_vol: set[str] = set()
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
        vue = _observer(list(phase.experiences), etat["echouees"], etat["reportees"])

        # ── En vol, vraiment ? ────────────────────────────────────────────────
        # Le délai de grâce ci-dessous ne surveille que les lancements de CE processus
        # (`lancees`) : une exécution bloquée avant un redémarrage de la campagne échappait
        # à toute surveillance. Ici on ne suppose rien du pid — on regarde si l'état bouge.
        # La campagne ne tue rien et ne relance rien : elle le DIT, et c'est déjà ce qui
        # manquait le 2026-09-16, où six heures se sont passées sans un mot.
        #
        # Ce qui DORT sur son quota est exclu : son état ne bouge pas non plus, mais c'est
        # une attente comprise, déjà consignée par le sommeil de lot et son alarme des 26 h.
        # L'alarmer ici doublerait le message et ferait passer une attente normale pour une
        # anomalie — exactement ce qu'une alarme doit éviter.
        for exp in [e for e in vue.en_vol if e not in vue.dorment]:
            fige = _fige_depuis(etat_experience(exp))
            if fige is None or fige < EN_VOL_FIGE_S:
                alarme_en_vol.discard(exp)
                continue
            if exp in alarme_en_vol:
                continue
            alarme_en_vol.add(exp)
            infos = etat_experience(exp)
            logger.error(
                f"[ALARME] [campagne] {exp} est comptée EN VOL, mais son état n'a pas bougé "
                f"depuis {fige / 60:.0f} min — état {infos['etat']!r}, motif : "
                f"{infos.get('raison')!r}, dossier {infos['dossier']}. La campagne ne la "
                f"touche pas et attend derrière elle. Reprendre : "
                f"make experience-reprendre EXP={exp} — arrêter : "
                f"make experience-arreter EXP={exp}"
            )

        # Ce qu'on vient de lancer compte comme en vol tant que son état n'est pas écrit.
        for exp, quand in list(lancees.items()):
            if exp in vue.faites or exp in vue.en_vol or exp in vue.a_reprendre:
                lancees.pop(exp, None)
            elif time.time() - quand > DELAI_ECRITURE_ETAT_S:
                lancees.pop(exp, None)
                # Un lancement qui n'écrit jamais d'état est un lancement qui a ÉCHOUÉ, pas
                # un lancement lent. Il compte donc comme une tentative — sans quoi la
                # campagne le relance indéfiniment : mesuré le 2026-09-15, 178 relances en
                # six heures sur un témoin dont l'artefact était refusé, la phase bloquée et
                # les bras LLM jamais atteints. Un blocage silencieux vaut moins qu'un échec
                # déclaré : au moins l'échec laisse passer la suite.
                # …SAUF quand le lanceur a dit pourquoi il refusait. Il dépose alors un
                # marqueur à côté de son journal : une pénurie de quota du jour n'est pas une
                # panne, elle se REPORTE sans consommer de tentative, et la passe de repêchage
                # la reprendra. Le 2026-09-16, quatre bras ont été déclarés cassés pour cette
                # seule raison qu'on ne lisait pas ce que le refus disait.
                classe, motifs = _refus_du_dernier_lancement(exp)
                if classe is not None and REFUS.est_reportable(classe):
                    etat["reportees"][exp] = {
                        "motif": "; ".join(motifs)[:300] or classe, "classe": classe,
                        "le": _iso()}
                    if etat.get("courante") == exp:
                        etat["courante"] = None
                    ecrire_etat(nom, etat)
                    logger.info(
                        f"[campagne] ⏭ {exp} REPORTÉE au lancement — {classe} : le lanceur a "
                        f"refusé de créer l'exécution faute de quota du jour. Aucune tentative "
                        f"décomptée ; elle repassera à la passe de repêchage.")
                    continue
                tentatives[exp] = tentatives.get(exp, 0) + 1
                journal = dossier_experiences() / exp / "lancements"
                if classe is not None:
                    # Le refus a une raison connue : la dire, plutôt que « sans jamais écrire
                    # d'état », qui envoie chercher une panne inexistante.
                    etat["echouees"][exp] = {
                        "motif": f"lancement refusé ({classe}) : " + "; ".join(motifs)[:300],
                        "classe": classe, "tentatives": tentatives[exp], "le": _iso()}
                    etat["restantes"] = [e for e in etat["restantes"] if e != exp]
                    if etat.get("courante") == exp:
                        etat["courante"] = None
                    ecrire_etat(nom, etat)
                    logger.error(
                        f"[ALARME] [campagne] {exp} : lancement refusé — {classe}. "
                        + "; ".join(motifs)[:200])
                    continue
                if tentatives[exp] > TENTATIVES_MAX:
                    etat["echouees"][exp] = {
                        "motif": f"lancée {tentatives[exp]} fois sans jamais écrire d'état "
                                 f"— voir {journal}",
                        "tentatives": tentatives[exp], "le": _iso()}
                    etat["restantes"] = [e for e in etat["restantes"] if e != exp]
                    if etat.get("courante") == exp:
                        etat["courante"] = None
                    ecrire_etat(nom, etat)
                    logger.error(
                        f"[ALARME] [campagne] {exp} lancée {tentatives[exp]} fois sans jamais "
                        f"écrire d'état — déclarée en échec, la campagne passe à la suivante. "
                        f"Le refus est dans {journal}.")
                else:
                    logger.warning(
                        f"[campagne] {exp} lancée il y a plus de "
                        f"{DELAI_ECRITURE_ETAT_S:.0f} s sans avoir écrit d'état — relance "
                        f"{tentatives[exp]}/{TENTATIVES_MAX}. Le refus éventuel est dans "
                        f"{journal}.")
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
                 if e not in etat["faites"]
                 and e not in etat["echouees"]
                 and e not in etat["reportees"]]
        if not reste:
            suivantes = [p for p in campagne.phases
                         if campagne.phases.index(p) > campagne.phases.index(phase)]
            if not suivantes:
                # ── Repêchage : rien n'est abandonné sans une seconde chance ───────
                # Tout ce qui a été reporté (quota) ou déclaré en échec repasse, compteurs de
                # tentatives remis à zéro. Sans cette passe, un quota épuisé en milieu de
                # campagne coûtait l'expérience pour de bon : elle sortait de l'observation et
                # n'y revenait pas, même en relançant la campagne.
                a_repecher = list(etat["reportees"]) + list(etat["echouees"])
                if a_repecher and etat["repechages"] < REPECHAGES_MAX:
                    etat["repechages"] += 1
                    reportees, echouees = dict(etat["reportees"]), dict(etat["echouees"])
                    etat["reportees"], etat["echouees"] = {}, {}
                    for exp in reportees:
                        # Un report n'est pas une tentative ratée : compteur remis à neuf.
                        tentatives.pop(exp, None)
                    for exp in echouees:
                        # Un échec réel n'a droit qu'à UNE relance par passe de repêchage, pas
                        # à un compteur neuf : sans cela une expérience cassée se relancerait
                        # TENTATIVES_MAX fois à chaque passe, et le plafond ne voudrait plus rien.
                        tentatives[exp] = TENTATIVES_MAX - 1
                    premiere = next(
                        (p for p in campagne.phases
                         if any(e in a_repecher for e in p.experiences)),
                        campagne.phases[0],
                    )
                    etat["phase_courante"] = premiere.nom
                    etat["courante"] = None
                    ecrire_etat(nom, etat)
                    logger.info(
                        f"[campagne] ↺ REPÊCHAGE {etat['repechages']}/{REPECHAGES_MAX} — "
                        f"{len(reportees)} reportée(s) et {len(echouees)} en échec repassent, "
                        f"depuis la phase {premiere.nom!r} : "
                        + " · ".join(a_repecher)
                    )
                    continue

                etat["terminee_le"] = _iso()
                etat["courante"] = None
                ecrire_etat(nom, etat)
                echecs = len(etat["echouees"])
                reports = len(etat["reportees"])
                logger.info(
                    f"[campagne] {nom} TERMINÉE — {len(etat['faites'])}/{total} faites, "
                    f"{echecs} en échec, {reports} encore reportée(s), "
                    f"{etat['repechages']} repêchage(s), "
                    f"{len(etat['sommeils'])} mise(s) en sommeil, {tours} tour(s).")
                for exp, det in etat["reportees"].items():
                    logger.error(
                        f"[ALARME] [campagne] {exp} reste REPORTÉE après "
                        f"{etat['repechages']} repêchage(s) — {det.get('motif')}. Son quota ne "
                        "s'est pas rouvert dans la campagne : relancez-la seule plus tard.")
                if echecs or reports:
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
                _lancer_experience(exp, campagne.lanceurs)
            vue.en_vol.append(exp)

        # ── Quota épuisé : reporter plutôt que dormir devant une file pleine ──
        # Dormir est juste quand il n'y a RIEN d'autre à faire, et faux dès qu'une autre
        # expérience pourrait tourner — un quota épuisé chez un fournisseur ne dit rien des
        # autres. Mesuré le 2026-09-15 : une campagne à trois fournisseurs dormait jusqu'à 24 h
        # sur le quota du premier, les bras des deux autres à l'arrêt derrière.
        if vue.en_vol and vue.dorment and len(vue.dorment) == len(vue.en_vol):
            ailleurs = _reste_ailleurs(campagne, etat, phase, vue.en_vol)
            if ailleurs:
                for exp in vue.dorment:
                    motif = etat_experience(exp).get("raison") or ETAT_EN_ATTENTE_QUOTA
                    if _reporter_experience(exp):
                        etat["reportees"][exp] = {"motif": str(motif), "le": _iso()}
                        if etat.get("courante") == exp:
                            etat["courante"] = None
                        logger.info(
                            f"[campagne] ⏭ {exp} REPORTÉE (quota : {motif}) — "
                            f"{len(ailleurs)} expérience(s) peuvent tourner sans elle. "
                            "Elle repassera à la passe de repêchage, reprise là où elle "
                            "s'est arrêtée."
                        )
                ecrire_etat(nom, etat)
                dormir(intervalle_s)
                continue
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
                _lancer_experience(suivante, campagne.lanceurs)

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
        "reportees": (etat or {}).get("reportees", {}),
        "repechages": (etat or {}).get("repechages", 0),
        "etat": etat,
        "arret_demande": demande_arret(nom),
        "par_experience": par_experience,
        "prochain_reveil": quand,
        "secondes_avant_reveil": secondes,
    }


__all__ = [
    "CODE_DEJA_EN_VOL",
    "INTERVALLE_S",
    "VERSION_CAMPAGNE",
    "Campagne",
    "CampagneInvalide",
    "Phase",
    "arreter",
    "campagne_en_vol",
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
    "journal_lancement",
    "lire_etat",
    "prochain_reveil",
]
