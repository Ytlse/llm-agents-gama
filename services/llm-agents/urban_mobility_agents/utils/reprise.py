"""Reprise à chaud d'un run long — ticket 075.

LE PROBLÈME, EN UNE PHRASE
--------------------------
`make run OFFLINE=1 CONT=1` réutilise le répertoire du run — donc **retrouve la mémoire
pleine** — pendant que GAMA repart à son t0 et **rejoue** les jours déjà vécus. Sur un run
ordinaire, sans conséquence. Sur un run dont la mémoire EST l'objet, les jours rejoués
réécriraient des souvenirs déjà écrits : épisodes en double, compteurs d'observations et de
contre-exemples incrémentés deux fois, concepts mis à l'écart sur des contradictions comptées
deux fois. La mémoire du jour 40 ne serait plus celle qu'un run continu aurait produite.

LA RÉPONSE, EN DEUX PIÈCES
--------------------------
1. **Un point de reprise par jour simulé**, écrit à 3 h — après le drainage nocturne des
   réflexions et après le plancher de consolidation de 22 h, quand les tampons de mémoire courte
   sont vides et que presque personne n'est en trajet. C'est le seul instant de la journée où un
   instantané est cohérent sans machinerie de gel.
2. **Le rejeu à mémoire gelée** : au redémarrage, l'état est restauré au dernier point, puis
   tout ce qui ÉCRIT la mémoire est suspendu jusqu'à ce que l'horloge simulée dépasse ce point.
   Les agents circulent, décident, mais n'apprennent rien de ce qu'ils ont déjà appris.

CE QUI EST GELÉ, ET CE QUI NE L'EST PAS
---------------------------------------
Gelé : l'écriture de mémoire courte (donc, mécaniquement, toute consolidation, puisqu'un tampon
vide ne rend aucun agent éligible), l'auto-réflexion long terme, et le journal de mémoire.
Pas gelé : les décisions, les itinéraires, les déplacements — ils doivent avoir lieu pour que la
simulation retrouve son état. Le cache de décisions les sert sans appel au modèle.

⚠ **L'écriture d'un point est ATOMIQUE** : répertoire temporaire, puis renommage. Un point
interrompu en cours d'écriture n'est jamais retenu comme valide — un point à moitié écrit serait
pire que pas de point du tout, parce qu'il serait restauré en silence.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from loguru import logger
from sim_clock import wall_clock
from urban_mobility_agents.utils import identite_run
from urban_mobility_agents.utils.ancre_run import ancre, ancrer

# Nom du répertoire des points de reprise, dans le workdir du run.
POINTS = "checkpoints_memoire"
# Fichier de description d'un point. Sa présence fait la validité du point : il est écrit en
# dernier, après la copie des données.
DESCRIPTION = "reprise.json"

# Ce qui est copié dans un point, relativement au workdir. La mémoire long terme (index
# vectoriel et métadonnées par agent) et le journal de mémoire.
_A_COPIER = ("long_term_memory", "memoires")

# État du gel, au niveau du processus. Le contrôleur le pose à la restauration et le lève quand
# l'horloge simulée dépasse le point ; l'agent le consulte sur le chemin d'écriture.
_gel_jusqu_a: int | None = None
_gel_jour: int | None = None
_degel_signale = False


# ── Gel ──────────────────────────────────────────────────────────────────────────────────


def geler_jusqu_a(timestamp_simule: int, jour: int) -> None:
    global _gel_jusqu_a, _gel_jour, _degel_signale
    _gel_jusqu_a = int(timestamp_simule)
    _gel_jour = int(jour)
    _degel_signale = False
    logger.warning(
        f"[reprise] MÉMOIRE GELÉE jusqu'au {wall_clock(_gel_jusqu_a)} (jour simulé {jour}) : "
        f"les jours déjà vécus sont rejoués sans être réappris. Les décisions, elles, ont lieu."
    )


def gel_actif() -> bool:
    """Le rejeu est-il en cours ? Consulté sur le chemin d'écriture de la mémoire."""
    return _gel_jusqu_a is not None


def point_de_reprise_timestamp() -> int | None:
    """L'instant simulé jusqu'auquel on rejoue, ou None hors reprise.

    Ticket 090 : borne la trace de décisions. Au-delà de cet instant le run redevient vivant,
    et resservir une décision y serait un cache, pas un rejeu.
    """
    return _gel_jusqu_a


def degeler_si_depasse(timestamp_simule: int) -> bool:
    """Lève le gel dès que l'horloge simulée dépasse le point de reprise. Rend `True` au dégel."""
    global _gel_jusqu_a, _gel_jour, _degel_signale
    if _gel_jusqu_a is None or int(timestamp_simule) < _gel_jusqu_a:
        return False
    logger.info(
        f"[reprise] DÉGEL au {wall_clock(int(timestamp_simule))} — le rejeu du jour "
        f"{_gel_jour} est terminé, la mémoire réapprend à partir d'ici."
    )
    _gel_jusqu_a = None
    _gel_jour = None
    _degel_signale = True
    return True


def reinitialiser() -> None:
    """Oublie l'état de gel. Réservé aux tests."""
    global _gel_jusqu_a, _gel_jour, _degel_signale
    _gel_jusqu_a = None
    _gel_jour = None
    _degel_signale = False


# ── Points de reprise ────────────────────────────────────────────────────────────────────


def _repertoire_points(workdir: Path) -> Path:
    return Path(workdir) / POINTS


def ecrire_point(
    workdir: Path,
    jour: int,
    timestamp_simule: int,
    *,
    compteurs: dict | None = None,
    foyer: dict | None = None,
) -> Path | None:
    """Écrit un point de reprise complet. Rend son chemin, ou `None` si rien n'a pu être écrit.

    Une erreur d'écriture ne remonte pas : perdre un point de reprise coûte au pire le rejeu
    d'une journée, faire tomber le run coûte les soixante.
    """
    workdir = Path(workdir)
    cible = _repertoire_points(workdir) / f"jour_{int(jour):03d}"
    provisoire = cible.with_suffix(".en_cours")
    try:
        if provisoire.exists():
            shutil.rmtree(provisoire)
        provisoire.mkdir(parents=True)
        for nom in _A_COPIER:
            source = workdir / nom
            if source.is_dir():
                shutil.copytree(source, provisoire / nom, dirs_exist_ok=True)
        # La description est écrite EN DERNIER : c'est elle qui rend le point valide.
        (provisoire / DESCRIPTION).write_text(
            json.dumps(
                {
                    "jour_simule": int(jour),
                    "timestamp_simule": int(timestamp_simule),
                    "horodatage_simule": wall_clock(int(timestamp_simule)).isoformat(),
                    "ancre_run": ancre(),
                    "ecrit_le": datetime.now().astimezone().isoformat(),
                    "compteurs": compteurs or {},
                    # Ticket 100, lot 4 — le repère de lecture du foyer, par receveur, et les
                    # croyances déjà montrées. Sans lui, une reprise à chaud ferait
                    # RÉ-ENTENDRE au foyer entier plusieurs nuits déjà entendues : le défaut
                    # que ce ticket a corrigé pour la mémoire, à ne pas réintroduire par la
                    # porte du foyer.
                    "foyer": foyer or {},
                    # Ticket 091 — l'identité du run voyage AVEC le point. Sans elle, un point
                    # restauré ne dit pas de quelle expérience il vient, et rien n'empêche de
                    # rendre à un run la mémoire d'un autre.
                    "identite": identite_run.lire(workdir) or {},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if cible.exists():
            shutil.rmtree(cible)
        os.replace(provisoire, cible)
        logger.info(
            f"[reprise] point de reprise écrit : {cible} (jour simulé {jour}, "
            f"{wall_clock(int(timestamp_simule))})"
        )
        return cible
    except OSError as err:
        logger.error(
            f"[ALARME] [reprise] point de reprise du jour {jour} NON écrit ({err}) — une "
            f"interruption ferait repartir du point précédent, ou du début s'il n'y en a pas."
        )
        shutil.rmtree(provisoire, ignore_errors=True)
        return None


def dernier_point(workdir: Path) -> tuple[Path, dict] | None:
    """Le point valide le plus récent, ou `None`. Un point sans description n'est pas valide."""
    repertoire = _repertoire_points(Path(workdir))
    if not repertoire.is_dir():
        return None
    points: list[tuple[int, Path, dict]] = []
    for chemin in repertoire.iterdir():
        description = chemin / DESCRIPTION
        if not description.is_file():
            continue
        try:
            meta = json.loads(description.read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            logger.warning(f"[reprise] point illisible ignoré : {chemin} ({err})")
            continue
        points.append((int(meta.get("jour_simule", 0)), chemin, meta))
    if not points:
        return None
    _, chemin, meta = max(points, key=lambda t: t[0])
    return chemin, meta


# Sorties par trajet qu'un rejeu RÉÉCRIT sans prévenir. Ce ne sont pas des journaux : ce sont
# les mesures. Une ligne rejouée y est indiscernable d'une ligne originale.
_SORTIES_PAR_TRAJET = ("moves.csv",)


def ecarter_les_sorties_du_rejeu(workdir: Path) -> list[Path]:
    """Met de côté les sorties par trajet avant un rejeu — ticket 077, lot E6.

    Une reprise sans point de reprise valide fait repartir GAMA de t0 : les premiers jours sont
    rejoués et REDÉCIDÉS. Sur le run du ticket 075, **84 trajets** des 16 au 21 mars se sont
    ainsi retrouvés une seconde fois dans `moves.csv`, sans qu'aucune colonne ne les distingue
    des originaux. Toute part modale calculée sur ce fichier compte ces jours deux fois.

    Le fichier n'est pas supprimé — il porte des mesures — mais horodaté et mis de côté, à la
    manière de `archive_log.py`. Le rejeu écrit alors dans un fichier neuf, et les deux séries
    restent lisibles séparément.
    """
    workdir = Path(workdir)
    ecartes: list[Path] = []
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    for nom in _SORTIES_PAR_TRAJET:
        source = workdir / nom
        if not source.is_file():
            continue
        destination = source.with_name(f"{source.name}.{horodatage}.avant_rejeu")
        try:
            os.rename(source, destination)
            ecartes.append(destination)
            logger.warning(
                f"[reprise] {nom} mis de côté sous {destination.name} avant le rejeu — "
                f"les trajets redécidés auraient été indiscernables des originaux"
            )
        except OSError as err:
            logger.error(
                f"[ALARME] [reprise] {nom} n'a PAS pu être mis de côté ({err}) — le rejeu "
                f"va y ajouter des trajets en double, et toute part modale calculée dessus "
                f"comptera les jours rejoués deux fois"
            )
    return ecartes


def restaurer_si_demande(
    workdir: Path, *, reprise_demandee: bool, alarme_si_absent: bool = False
) -> dict | None:
    """Restaure le dernier point et pose le gel. À appeler AVANT toute ouverture de la mémoire.

    L'ordre n'est pas négociable : l'index vectoriel est ouvert à la construction de l'agent, et
    remplacer ses fichiers sous lui donnerait une base ouverte sur des octets qui ne sont plus là.

    ⚠ **Le bon moment est le `/init` de GAMA, pas le démarrage du contrôleur.** Défaut trouvé en
    testant la reprise le 2026-09-14 : `make run OFFLINE=1 CONT=1` ne redémarre QUE GAMA — le
    conteneur `controller` continue de tourner, son `startup_event` n'est pas rejoué, et la
    restauration n'avait donc jamais lieu. Ce qui redémarre, dans une reprise, c'est la
    SIMULATION ; et une simulation qui redémarre envoie un `/init`.

    `alarme_si_absent` distingue les deux appelants : une reprise explicitement demandée
    (`CONTINUE_RUN`) sans point de reprise mérite une alarme ; un `/init` de run neuf, non.
    """
    if not reprise_demandee:
        return None
    trouve = dernier_point(workdir)
    if trouve is None:
        if alarme_si_absent:
            logger.error(
                "[ALARME] [reprise] reprise demandée mais AUCUN point de reprise valide dans "
                f"{_repertoire_points(Path(workdir))} — la mémoire déjà présente serait "
                "réécrite par le rejeu. Le run repart donc sans gel : vérifiez que c'est bien "
                "voulu."
            )
            # Ticket 077, lot E6 — le rejeu va redécider les premiers jours. Ses trajets ne
            # doivent pas s'ajouter aux originaux dans le même fichier de mesures.
            ecarter_les_sorties_du_rejeu(Path(workdir))
        else:
            logger.info(
                f"[reprise] aucun point de reprise dans {_repertoire_points(Path(workdir))} : "
                f"run neuf, rien à restaurer."
            )
        return None
    chemin, meta = trouve
    workdir = Path(workdir)
    try:
        for nom in _A_COPIER:
            source = chemin / nom
            if not source.is_dir():
                continue
            destination = workdir / nom
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(source, destination)
    except OSError as err:
        logger.error(
            f"[ALARME] [reprise] restauration IMPOSSIBLE depuis {chemin} ({err}) — le run "
            f"repart sur l'état en place, qui peut être postérieur au point."
        )
        return None

    if meta.get("ancre_run"):
        # L'ancre AVANT tout : elle doit être posée avant que le rejeu ne fasse observer son
        # premier timestamp, sinon la progression météo de tous les agents rembobine.
        ancrer(int(meta["ancre_run"]), origine="point de reprise")
    geler_jusqu_a(int(meta["timestamp_simule"]), int(meta.get("jour_simule", 0)))
    logger.info(
        f"[reprise] état restauré depuis {chemin} — jour simulé {meta.get('jour_simule')}, "
        f"{meta.get('horodatage_simule')}"
    )
    return meta
