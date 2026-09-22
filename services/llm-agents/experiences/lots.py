"""Du déplacement à la requête : le facteur de regroupement de la passerelle.

Une expérience se compte en **déplacements** — un déplacement, une décision modale à prendre.
Un quota fournisseur se compte en **requêtes**. Les deux ne sont pas la même chose : la
passerelle fusionne plusieurs agents dans un seul appel (micro-batching), et la clé de lot
(`llm_gateway/core/batching.compute_batch_key`) est bâtie sur la catégorie, les paramètres,
l'instance forcée et les instances admises — toutes constantes à l'intérieur d'un bras. Toutes
les décisions d'une expérience partagent donc le même lot.

Jusqu'au 2026-09-22, l'estimation posait « une requête par déplacement » et surestimait donc
le quota consommé d'un facteur de l'ordre de huit — repère retenu au ticket 073 § 4 : environ
310 requêtes pour un bras complet, soit à peu près 0,3 jour de quota. Ce module fournit le
diviseur manquant, et surtout **dit d'où il vient** :

- le **plafond** se dérive : `batch_max_agents` que la passerelle calcule pour l'instance
  visée, borné par le parallélisme de l'expérience en mode sans simulateur (le lot ne peut
  pas contenir plus d'agents qu'il n'y a de tâches en vol) ;
- le **facteur observé** se mesure sur les exécutions archivées du même gabarit.

Les deux répondent à des questions différentes et aucun ne remplace l'autre : le plafond est
une borne structurelle jamais atteinte, la mesure est bruitée. Ce qui décide d'un lancement
est le chiffre **prudent** (cf. `facteurs`), jamais le plafond.
"""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from experiences.ressources import FUSEAU_QUOTA_DEFAUT
from loguru import logger

#: Une mesure de regroupement est une moyenne : elle ne vaut rien sur deux requêtes. On exige
#: que l'exécution archivée ait porté au moins ce nombre de lots PLEINS, faute de quoi une
#: poignée de requêtes de bruit déplace le rapport du simple au double. Dérivé du plafond, pas
#: un volume écrit en dur : `sollicitations >= LOTS_MINIMUM * plafond`.
LOTS_MINIMUM_POUR_MESURER = 10

#: Motifs d'écartement d'une exécution archivée, pour que le rejet soit lisible plutôt que muet.
MOTIFS = (
    "reglages",  # même gabarit, mais autre parallélisme ou autre troncature
    "sans_compteur",  # ni delta mesuré ni compteur journalier
    "trop_courte",  # moins de LOTS_MINIMUM_POUR_MESURER lots
    "fenetre_traversee",  # le compteur journalier s'est remis à zéro pendant le run
    "hors_bornes",  # rapport hors [1, plafond] : le compteur ne décrit pas ce run
    "run_non_probant",  # repris, interrompu ou quota épuisé : le compteur du jour ment
)


# ── Plafond dérivé ───────────────────────────────────────────────────────────


def _plafond_instance(cfg: dict, etat: dict | None) -> tuple[int | None, str]:
    """Plafond de lot d'une instance : la passerelle d'abord, la formule ensuite.

    `/health` publie `batch_max_agents` depuis le 2026-09-22 : c'est la valeur **autoritaire**,
    calculée au démarrage du conteneur qui sert réellement les requêtes. Le repli recalcule la
    même formule depuis `providers.yaml` — avec les défauts de `BatchingSettings`, qui peuvent
    différer de l'environnement du worker. D'où la source distincte : un chiffre recalculé ne
    doit pas se faire passer pour un chiffre relevé.
    """
    publie = (etat or {}).get("batch_max_agents")
    if publie:
        try:
            return int(publie), "passerelle"
        except (TypeError, ValueError):
            pass
    try:
        from llm_gateway.config.settings import BatchingSettings
        from llm_gateway.core.batching import compute_batch_max_agents
    except ImportError as e:  # paquet absent : on le dit, on ne devine pas
        logger.warning(f"[lots] llm_gateway indisponible ({e}) : plafond de lot inconnu")
        return None, "indisponible"
    b = BatchingSettings()
    rpm = cfg.get("rpm_limit")
    if not rpm:
        return None, "indisponible"
    return (
        compute_batch_max_agents(
            tpm_limit=cfg.get("tpm_limit"),
            rpm_limit=int(rpm),
            max_tokens_per_request=cfg.get("max_tokens_per_request"),
            tokens_per_agent=b.assumed_prompt_tokens + b.assumed_output_tokens,
            plafond=b.max_batch_agents,
        ),
        "providers.yaml (formule de la passerelle, défauts de batching)",
    )


def plafond_lot(
    providers: dict[str, dict],
    instances: list[str],
    *,
    parallelisme: int | None = None,
    etat_passerelle: dict[str, dict] | None = None,
) -> tuple[int, str]:
    """(plafond, source) : le plus d'agents qu'une requête de cette expérience puisse porter.

    Minimum sur les instances admises — le décideur les épuise EN SÉRIE (une instance forcée
    par requête, cf. `DecideurPasserelle._prochaine_instance`), donc la plus petite capacité
    finit par servir et c'est elle qui borne prudemment.

    `parallelisme` borne à son tour, et c'est le bornage qui explique les mesures : en mode
    sans simulateur, `regroupement.parallelisme` personnes avancent de front et les
    déplacements d'une personne sont sériels — il ne peut donc jamais y avoir plus de
    `parallelisme` tâches en attente de fusion. Passer `None` retire ce bornage : en mode
    simulateur c'est GAMA qui alimente la file, et des lots de 15 agents s'y observent pour un
    parallélisme déclaré de 8.
    """
    if not instances:
        return 1, "aucune instance admise : aucun regroupement supposé"
    valeurs, sources = [], set()
    for i in instances:
        v, src = _plafond_instance(providers.get(i) or {}, (etat_passerelle or {}).get(i))
        if v:
            valeurs.append(v)
            sources.add(src)
    if not valeurs:
        return 1, "plafond de lot inconnu : aucun regroupement supposé"
    plafond = min(valeurs)
    source = f"batch_max_agents={plafond} (min sur {len(valeurs)} instance(s), {', '.join(sorted(sources))})"
    if parallelisme and parallelisme < plafond:
        source = (
            f"parallélisme {parallelisme} de l'expérience (sous batch_max_agents={plafond}, "
            f"{', '.join(sorted(sources))})"
        )
        plafond = int(parallelisme)
    return plafond, source


# ── Mesure sur les exécutions archivées ──────────────────────────────────────


def _date_locale(iso: str | None, fuseau: str) -> Any:
    if not iso:
        return None
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(fuseau)
    except Exception:  # noqa: BLE001 — fuseau inconnu / tzdata absente
        tz = None
    try:
        d = datetime.fromisoformat(str(iso))
    except ValueError:
        return None
    return (d.astimezone(tz) if tz else d).date()


def fenetre_quota_traversee(debut: str | None, fin: str | None, fuseau: str) -> bool:
    """L'exécution a-t-elle franchi le minuit qui remet les compteurs journaliers à zéro ?

    Elle l'a franchi ⇒ `daily_requests` relevé à la clôture ne compte qu'une partie du run, le
    rapport « déplacements ÷ requêtes » explose, et le regroupement paraît meilleur qu'il n'est.
    C'est le seul biais de cette mesure qui aille dans le sens de l'imprudence : on écarte.

    Une borne illisible est traitée comme un franchissement : dans le doute, on écarte.
    """
    d1, d2 = _date_locale(debut, fuseau), _date_locale(fin, fuseau)
    if d1 is None or d2 is None:
        return True
    return d1 != d2


def _compteur_journalier_probant(conf: dict, compteurs: dict) -> str | None:
    """Ce compteur du JOUR peut-il tenir lieu de coût de CE run ? Sinon, pourquoi.

    Il ne le peut qu'à trois conditions, et l'oublier coûte cher : lu tel quel sur l'exécution
    `2026-09-21_17_00_49`, qui avait épuisé son quota (`key1` à 506 pour une limite de 500), il
    annonce 2,4 agents/requête là où le regroupement réel est de l'ordre de 8 — les réessais et
    les autres runs du jour gonflent le dénominateur.

    - **terminée** : une exécution arrêtée en route a consommé des requêtes que ses
      sollicitations archivées ne reflètent pas ;
    - **sans reprise** : une reprise resert des décisions archivées sans rien solliciter, et ses
      requêtes s'ajoutent à celles de la tentative précédente ;
    - **quota non épuisé** : au plafond, le fournisseur a refusé des requêtes qui ont pourtant
      été comptées.
    """
    if (conf.get("cloture") or {}).get("etat") != "terminee":
        return "exécution non terminée"
    if conf.get("interruptions"):
        return "exécution interrompue ou reprise"
    for ligne in compteurs.get("quota") or []:
        if not isinstance(ligne, dict):
            continue
        if ligne.get("epuisee"):
            return f"quota épuisé sur {ligne.get('instance')}"
        servies, plafond = ligne.get("requetes_jour"), ligne.get("limite_jour")
        if servies is not None and plafond and int(servies) >= int(plafond):
            return (
                f"{ligne.get('instance')} au plafond du jour "
                f"({servies}/{plafond}) : des refus ont été comptés"
            )
    return None


def _requetes_de_lexecution(compteurs: dict) -> tuple[int | None, bool]:
    """(requêtes consommées, mesure fiable ?) pour une exécution archivée.

    Deux sources, et elles ne se valent pas :

    1. `compteurs["requetes"]["delta"]` — différence des compteurs de la passerelle entre
       l'ouverture et la clôture, écrite par le runner depuis le 2026-09-22 : c'est le nombre
       de requêtes de CE run.
    2. `compteurs["quota"][].requetes_jour` — compteur JOURNALIER relevé à la clôture. Il
       agrège tout ce que l'instance a servi ce jour-là : les autres runs, les réflexions, les
       réessais. Il surestime donc les requêtes du run, et sous-estime le regroupement — dans
       le sens prudent, ce qui le rend utilisable, mais jamais comme une mesure.
    """
    r = compteurs.get("requetes")
    if isinstance(r, dict) and r.get("fiable") and r.get("delta"):
        return int(r["delta"]), True
    q = compteurs.get("quota")
    if isinstance(q, list) and q:
        total = sum(int(l.get("requetes_jour") or 0) for l in q if isinstance(l, dict))
        if total > 0:
            return total, False
    return None, False


def mesures_archivees(
    empreinte_gabarit_: str,
    *,
    parallelisme: int | None,
    troncature: bool,
    plafond: int,
    providers: dict[str, dict] | None = None,
    dossier_experiences_: Path | str | None = None,
) -> dict | None:
    """Facteurs de regroupement relevés sur les exécutions comparables déjà jouées.

    Comparable = même gabarit, même parallélisme, même troncature du *consideration set* : ce
    sont les trois réglages qui déplacent le coût en jetons d'un agent, donc la taille des
    lots ; les mélanger produirait une moyenne qui ne décrit aucun d'eux.

    Rend `{minimum, mediane, n, fiabilite, source, ecartees}` ou `None` si rien n'est retenu.
    """
    from experiences.experience import dossier_experiences

    racine = (
        Path(dossier_experiences_) if dossier_experiences_ else dossier_experiences()
    )
    if not racine.is_dir():
        return None
    seuil = LOTS_MINIMUM_POUR_MESURER * max(1, plafond)
    ratios: list[float] = []
    fiables = 0
    ecartees: dict[str, int] = {}
    sources: list[str] = []

    def ecarter(motif: str) -> None:
        ecartees[motif] = ecartees.get(motif, 0) + 1

    for exec_yaml in sorted(racine.glob("*/executions/*/execution.yaml")):
        try:
            conf = yaml.safe_load(exec_yaml.read_text(encoding="utf-8")) or {}
        except (yaml.YAMLError, OSError):
            continue
        emp = (conf.get("empreintes") or {}).get("gabarit") or {}
        exp = conf.get("experience") or {}
        if emp.get("sha256") != empreinte_gabarit_:
            continue
        par = (exp.get("regroupement") or {}).get("parallelisme")
        if parallelisme is not None and par is not None and int(par) != int(parallelisme):
            ecarter("reglages")
            continue
        if bool(exp.get("troncature_15", False)) != bool(troncature):
            ecarter("reglages")
            continue
        chemin_compteurs = exec_yaml.parent / "compteurs.json"
        if not chemin_compteurs.is_file():
            ecarter("sans_compteur")
            continue
        try:
            compteurs = json.loads(chemin_compteurs.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            ecarter("sans_compteur")
            continue
        sollicitations = int(compteurs.get("sollicitations") or 0)
        requetes, fiable = _requetes_de_lexecution(compteurs)
        if not sollicitations or not requetes:
            ecarter("sans_compteur")
            continue
        if sollicitations < seuil:
            ecarter("trop_courte")
            continue
        if not fiable:
            motif = _compteur_journalier_probant(conf, compteurs)
            if motif:
                logger.debug(f"[lots] {exec_yaml.parent.name} écartée : {motif}")
                ecarter("run_non_probant")
                continue
            # Le compteur journalier n'a de sens que si le run tient dans une seule fenêtre.
            instances = [
                str(l.get("instance"))
                for l in (compteurs.get("quota") or [])
                if isinstance(l, dict) and l.get("instance")
            ]
            fuseau = next(
                (
                    str(((providers or {}).get(i) or {}).get("quota_reset_tz"))
                    for i in instances
                    if ((providers or {}).get(i) or {}).get("quota_reset_tz")
                ),
                FUSEAU_QUOTA_DEFAUT,
            )
            if fenetre_quota_traversee(
                conf.get("cree_le"), (conf.get("cloture") or {}).get("le"), fuseau
            ):
                ecarter("fenetre_traversee")
                continue
        ratio = sollicitations / requetes
        if ratio < 1 or ratio > plafond:
            # < 1 : le compteur décrit plus que ce run. > plafond : il en décrit moins que ce
            # run (remise à zéro, redémarrage de la passerelle). Ni l'un ni l'autre ne mesure
            # le regroupement — et le second irait dans le sens de l'imprudence.
            ecarter("hors_bornes")
            continue
        ratios.append(ratio)
        fiables += 1 if fiable else 0
        sources.append(str(exec_yaml.parent.relative_to(racine)))

    if not ratios:
        if ecartees:
            logger.info(
                f"[lots] aucune exécution archivée exploitable pour le regroupement "
                f"({', '.join(f'{m} × {n}' for m, n in sorted(ecartees.items()))})"
            )
        return None
    fiabilite = "mesurée" if fiables == len(ratios) else "minorée (compteur journalier)"
    return {
        "minimum": min(ratios),
        "mediane": statistics.median(ratios),
        "n": len(ratios),
        "fiabilite": fiabilite,
        "ecartees": ecartees,
        "source": (
            f"{len(ratios)} exécution(s) archivée(s) du même gabarit, même parallélisme, "
            f"même troncature — {fiabilite}"
            + (f" ; {sum(ecartees.values())} écartée(s)" if ecartees else "")
        ),
    }


# ── Synthèse : les trois chiffres, et celui qui décide ───────────────────────


def facteurs(
    *,
    providers: dict[str, dict],
    instances: list[str],
    parallelisme: int | None,
    empreinte_gabarit_: str | None = None,
    troncature: bool = False,
    etat_passerelle: dict[str, dict] | None = None,
    dossier_experiences_: Path | str | None = None,
) -> dict:
    """Les facteurs de regroupement à appliquer, chacun avec sa source.

    Trois chiffres, et un seul décide :

    - `plafond` — borne structurelle, jamais atteinte. Sert à afficher un plancher de requêtes,
      **jamais** à autoriser un lancement.
    - `attendu` — médiane des exécutions comparables, à défaut le plafond. C'est le chiffre
      qu'on lit pour savoir ce que le bras coûtera vraiment.
    - `prudent` — minimum des exécutions comparables, à défaut **1**. C'est lui qui alimente
      l'avertissement de quota, la part de quota et la durée. Sans mesure, il vaut 1 : la
      prudence retombe exactement sur le comportement d'avant cette correction, jamais en
      dessous. Une estimation trop optimiste ferait lancer un bras qui n'irait pas au bout ; le
      plafond dérivé ne peut donc pas tenir ce rôle.
    """
    plafond, source_plafond = plafond_lot(
        providers, instances, parallelisme=parallelisme, etat_passerelle=etat_passerelle
    )
    mesure = (
        mesures_archivees(
            empreinte_gabarit_,
            parallelisme=parallelisme,
            troncature=troncature,
            plafond=plafond,
            providers=providers,
            dossier_experiences_=dossier_experiences_,
        )
        if empreinte_gabarit_
        else None
    )
    if mesure:
        return {
            "plafond": plafond,
            "attendu": round(mesure["mediane"], 2),
            "prudent": round(mesure["minimum"], 2),
            "decide_par": "prudent",
            "fiabilite": mesure["fiabilite"],
            "source": f"{mesure['source']} ; plafond : {source_plafond}",
            "mesures": {k: mesure[k] for k in ("n", "minimum", "mediane", "ecartees")},
        }
    return {
        "plafond": plafond,
        "attendu": float(plafond),
        "prudent": 1.0,
        "decide_par": "prudent",
        "fiabilite": "aucune mesure",
        "source": (
            f"aucune exécution archivée comparable : attendu = plafond dérivé "
            f"({source_plafond}), prudent = 1 requête par déplacement"
        ),
        "mesures": None,
    }


def requetes(deplacements: int, facteur: float) -> int:
    """Nombre de requêtes fournisseur pour ce nombre de déplacements, arrondi vers le haut."""
    if deplacements <= 0:
        return 0
    return max(1, math.ceil(deplacements / max(1.0, float(facteur))))


__all__ = [
    "LOTS_MINIMUM_POUR_MESURER",
    "MOTIFS",
    "facteurs",
    "fenetre_quota_traversee",
    "mesures_archivees",
    "plafond_lot",
    "requetes",
]
