#!/usr/bin/env python3
"""Orchestrateur séquentiel de cohorte avec clonage contrefactuel A/B et reprise à chaud garantie.

Ticket 077 — Rejeu Haute Fidélité (Choc c6_voiture_suspecte).

Principes d'architecture :
1. Exécution séquentielle de N runs de 1 habitant (évite toute saturation TPM/RPD).
2. Clonage contrefactuel par fork de simulation :
   - Branche A (Traité) : avec choc moteur aux J8-9.
   - Branche B (Témoin) : sans choc, conditions strictement identiques.
3. Reprise à chaud garantie par persona (CONT=1 étanche par workdir).
4. Étanchéité absolue de la mémoire (les enquêtes ne polluent ni STM ni LTM).
5. Neutralité du mode principal (1000 habitants non impactés).

⚠ CE SCRIPT EST LE SEUL LANCEUR DE LA CAMPAGNE (depuis le 2026-09-19).

Les réglages d'expérience — chaînage des véhicules, verrou de retour, seuil de troncature du
tirage, plancher de réflexion — ne sont plus dans `config/config.yaml` : posés là, ils étaient
devenus le défaut du dépôt et ne figuraient dans aucune identité de run. Ils sont posés ici, par
l'environnement, et `identite_run.json` les enregistre (ticket 077, lot K).

Conséquence à ne pas manquer : un `make run OFFLINE=1 CHOC=…` lancé À LA MAIN tourne désormais
aux valeurs par défaut du dépôt — chaînage actif, aucune troncature, réflexion à 10 entrées.
C'est voulu, et c'est l'inverse du piège précédent : un run manuel ne porte plus en silence les
réglages d'une expérience. Pour reproduire un bras, passer par ce script.

Les jalons d'enquête se déclarent par `EXPERIMENT_SURVEY_DAYS` ; leur défaut suit le protocole
en vigueur (J12, J17, J29, J40).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

# Le détecteur d'extinction vit dans son propre module — il est pur, et ses tests l'exercent
# sans run. Deux chemins d'import parce que ce fichier s'exécute en script (sys.path[0] vaut
# alors `scripts/experiment/`) ET s'importe en module depuis les tests.
try:
    from arret_sur_extinction import analyser as analyser_extinction
except ImportError:  # pragma: no cover — dépend du mode d'invocation, pas du code
    from scripts.experiment.arret_sur_extinction import analyser as analyser_extinction

COHORTE_10_PERSONAS = [
    "899549",   # Corinne (sujet historique Ticket 077)
    "1250941",  # Victoire
    "1016834",
    "1090400",
    "1165279",
    "1172810",
    "1254308",
    "1261543",
    "1298811",
    "1314647",
]

# Le choc de référence, VERSIONNÉ et testé (`specs/ticket_077/tests.md`, section H) : texte
# vécu sans verdict ni intention, `cadence: jour`. La cohorte en DÉRIVE un fichier par persona,
# où seule la ligne `agents:` change — elle ne redéfinit jamais le texte.
#
# ⚠ Jusqu'au 2026-09-19, ce module portait sa propre copie du choc, et il l'écrivait dans le
# workdir, que le contrôleur ne lit pas. Deux conséquences : les corrections apportées au fichier
# de référence ne parvenaient pas à la campagne, et la commande `make run` ne portait AUCUN
# `CHOC=` — donc la branche témoin tournait avec le choc déclaré dans `config.yaml`. Le bras de
# contrôle n'en était pas un.
# Les réglages du bras d'expérience, en UNE table : ce qu'on pose, et ce que l'identité du run
# doit porter en retour. Deux listes séparées auraient divergé — c'est la nature même du défaut
# que ce lot corrige.
#
# ⚠ NOM NU, sans préfixe `AGENT__`. Les sous-configurations de `settings.py` sont des
# `BaseSettings` sans préfixe : `VEHICLE_CHAIN_ENABLED` est lu, `AGENT__VEHICLE_CHAIN_ENABLED`
# ne l'est par personne. Ce script a posé la seconde forme pendant des semaines, sans effet, et
# le run du 2026-09-19 16:45 a tourné aux valeurs par défaut du dépôt.
#
# ⚠ Ces variables doivent aussi être déclarées en passe-plat dans `infra/docker-compose.yml` :
# compose ne transmet au conteneur que ce qu'il déclare.
REGLAGES_CAMPAGNE: dict[str, tuple[str, str, Any]] = {
    # variable d'environnement : (valeur posée, champ d'identite_run.json, valeur attendue)
    # ⚠ RÉACTIVÉS le 2026-09-21, sur décision de l'auteur. Coupés, ils produisaient des
    # enchaînements physiquement impossibles — rentrer en voiture d'un trajet fait en bus —
    # et les parts modales qui en sortaient n'étaient pas défendables.
    "VEHICLE_CHAIN_ENABLED": ("true", "chaine_vehicules", True),
    "VEHICLE_RETURN_HOME_LOCK": ("true", "verrou_retour_domicile", True),
    "MODE_CHOICE_TRUNCATION_THRESHOLD": ("0.15", "seuil_troncature", 0.15),
    "STM_REFLECTION_MIN_ENTRIES": ("5", "reflexion_stm_min_entrees", 5),
    "WEATHER_PER_AGENT_DATES": ("false", "meteo_par_agent", False),
}

# Combien de temps on accepte d'attendre l'identité du run (elle est écrite en ~20 s), et le
# run lui-même (mesuré : 2 h 50 pour 31 journées de mobilité).
ATTENTE_IDENTITE_S = 180
ATTENTE_RUN_S = 6 * 3600
# Au-delà d'un persona, le délai de garde suit le volume : 90 s par agent et par jour simulé.
# Six heures couvraient un habitant sur 42 jours ; vingt habitants sur quinze jours sur un
# fournisseur à ~4 requêtes/min en demandent davantage, et un bras coupé à la sixième heure
# serait compté en échec alors qu'il avançait.
DELAI_PAR_AGENT_JOUR_S = 90
HORIZON_JOURS_DEFAUT = 42


def delai_de_garde(taille: int, horizon_jours: int) -> int:
    """Le délai au-delà duquel un bras est déclaré bloqué. Jamais sous `ATTENTE_RUN_S`."""
    return max(ATTENTE_RUN_S, int(taille) * int(horizon_jours) * DELAI_PAR_AGENT_JOUR_S)

PAS_DE_SONDAGE_S = 30
PAS_DE_JOURNAL_S = 300
# Jours VÉCUS observés après l'extinction du souvenir déclaré avant de couper le run. Sept :
# une semaine simulée complète, assez pour voir si le comportement revient à celui d'avant, et
# c'est la durée déjà retenue par `arret_sur_extinction.py` en ligne de commande.
JOURS_APRES_EXTINCTION = 7

# L'événement joué par défaut : celui du ticket 077, pour que la commande d'hier rende le même
# run qu'hier. `--evenement` en désigne un autre (campagne du 2026-09-22 : `c3_panne_reseau`).
CHOC_REFERENCE = "c6_voiture_suspecte"
# Le répertoire CANONIQUE depuis le ticket 100 ; `config/chocs/` reste lu en second, les cinq cas
# du 079 y vivant encore. Le fichier dérivé, lui, part toujours dans le canonique : le Makefile
# préfère celui-ci quand le nom existe des deux côtés.
EVENEMENTS_DIR = Path("services/llm-agents/config/evenements")
CHOCS_DIR = Path("services/llm-agents/config/chocs")
# Les populations se résolvent depuis la RACINE du dépôt, jamais depuis le répertoire courant :
# c'est ce dossier que le conteneur monte sous `/data/eqasim-output`.
REPO_ROOT = Path(__file__).resolve().parents[2]
POPULATIONS_DIR = REPO_ROOT / "data" / "population"


def source_evenement(evenement: str) -> Path:
    """Le fichier de déclaration de cet événement, canonique d'abord, hérité ensuite."""
    canonique = EVENEMENTS_DIR / f"{evenement}.yaml"
    if canonique.is_file():
        return canonique
    herite = CHOCS_DIR / f"{evenement}.yaml"
    if herite.is_file():
        return herite
    livres = sorted(p.stem for p in EVENEMENTS_DIR.glob("*.yaml"))
    raise FileNotFoundError(
        f"événement introuvable : {evenement} — ni dans {EVENEMENTS_DIR} ni dans {CHOCS_DIR}. "
        f"Les cas livrés : {', '.join(livres)}"
    )


def nom_choc_derive(persona_id: str, evenement: str = CHOC_REFERENCE) -> str:
    """Le nom du choc dérivé pour ce persona. Pur : ne touche à rien."""
    return f"{evenement}__{persona_id}"


class PopulationIntrouvable(RuntimeError):
    """La population désignée n'existe pas, ou ne se lit pas : aucun run ne doit partir."""


def resoudre_population_et_taille(persona_or_pop_id: str) -> tuple[str, int, bool, list[str]]:
    """Le chemin CONTENEUR du JSON de population, sa taille, s'il s'agit d'un jeu, ses identifiants.

    Trois formes acceptées, dans cet ordre :
    1. un jeu scellé par son nom de dossier — `population_20_foyers_059` ;
    2. un persona unitaire par son identifiant — `861500` → `population_1_861500` ;
    3. un chemin vers un `population.json` sous `data/population/`.

    Un jeu est une population de PLUSIEURS agents. `population_1_861500` désigné par son nom de
    dossier reste unitaire : ce qui décide est l'effectif lu, pas la forme du nom.

    ⚠ LES CHEMINS SONT ANCRÉS SUR LA RACINE DU DÉPÔT. La première version de cette fonction lisait
    `data/population` relativement au répertoire courant : lancée d'ailleurs, elle ne trouvait
    rien, retombait sur le cas unitaire, et le bras exposait un « agent » nommé
    `population_20_foyers_059` — c'est-à-dire personne, sans un mot. D'où la règle : un
    identifiant NUMÉRIQUE sans dossier reste le repli historique (le fichier peut n'exister que
    dans le conteneur), tout autre nom introuvable est une erreur, et un fichier illisible aussi.
    """
    nom = str(persona_or_pop_id)
    direct_dir = POPULATIONS_DIR / nom
    unitaire_dir = POPULATIONS_DIR / f"population_1_{nom}"
    comme_chemin = Path(nom) if Path(nom).is_absolute() else REPO_ROOT / nom

    if (direct_dir / "population.json").is_file():
        cible = direct_dir / "population.json"
    elif (unitaire_dir / "population.json").is_file():
        cible = unitaire_dir / "population.json"
    elif comme_chemin.is_file():
        cible = comme_chemin
    elif nom.isdigit():
        logger.warning(
            f"[population] {POPULATIONS_DIR / f'population_1_{nom}'} absent sur l'hôte — repli "
            f"unitaire sur le chemin conteneur, sans vérification possible de l'effectif."
        )
        return f"/data/eqasim-output/population_1_{nom}/population.json", 1, False, [nom]
    else:
        message = (
            f"[ALARME] [population] « {nom} » introuvable : ni {direct_dir}/population.json, ni "
            f"{unitaire_dir}/population.json, ni un fichier. Aucun bras ne part sur une "
            f"population qu'on ne sait pas lire."
        )
        logger.error(message)
        raise PopulationIntrouvable(message)

    try:
        relatif = cible.resolve().relative_to(POPULATIONS_DIR.resolve())
    except ValueError as exc:
        raise PopulationIntrouvable(
            f"[ALARME] [population] {cible} est hors de {POPULATIONS_DIR} : le conteneur ne le "
            f"voit pas (seul ce dossier est monté sous /data/eqasim-output)."
        ) from exc
    try:
        data = json.loads(cible.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        message = f"[ALARME] [population] {cible} illisible ({exc})"
        logger.error(message)
        raise PopulationIntrouvable(message) from exc

    ids = [
        str(item.get("person_id") or (item.get("identity") or {}).get("person_id"))
        for item in data
        if isinstance(item, dict)
        and (item.get("person_id") or (item.get("identity") or {}).get("person_id"))
    ]
    if len(ids) != len(data):
        message = (
            f"[ALARME] [population] {cible} : {len(data)} entrées mais {len(ids)} `person_id` "
            f"lisibles — on ne sait pas qui cibler."
        )
        logger.error(message)
        raise PopulationIntrouvable(message)
    return f"/data/eqasim-output/{relatif.as_posix()}", len(ids), len(ids) > 1, ids


def foyers_de_la_population(persona_or_pop_id: str) -> tuple[set[str], list[str]]:
    """(foyers présents dans la population, foyers « expose » de son MANIFEST).

    Le manifeste est la source des foyers exposés d'une population de foyers (ticket 059,
    lot 6) : c'est lui qui les a choisis, avec leur motif. Vide s'il n'y a pas de manifeste.
    """
    import yaml

    direct = POPULATIONS_DIR / str(persona_or_pop_id)
    fichier = direct / "population.json"
    presents: set[str] = set()
    if fichier.is_file():
        for p in json.loads(fichier.read_text(encoding="utf-8")):
            foyer = (p.get("household") or {}).get("id") if isinstance(p, dict) else None
            if foyer:
                presents.add(str(foyer))
    exposes: list[str] = []
    manifeste = direct / "MANIFEST.yaml"
    if manifeste.is_file():
        groupes = (yaml.safe_load(manifeste.read_text(encoding="utf-8")) or {}).get("groupes") or {}
        exposes = [str(g["household_id"]) for g in (groupes.get("expose") or []) if g.get("household_id")]
    return presents, exposes


def lecteurs_du_manifeste(persona_or_pop_id: str, foyers: list[str]) -> list[str]:
    """Les lecteurs que le MANIFEST désigne pour ces foyers exposés (`expose[].lecteurs`).

    Vide si le manifeste n'en désigne pas : le lecteur se tire alors parmi les adultes.
    """
    import yaml

    manifeste = POPULATIONS_DIR / str(persona_or_pop_id) / "MANIFEST.yaml"
    if not manifeste.is_file():
        return []
    groupes = (yaml.safe_load(manifeste.read_text(encoding="utf-8")) or {}).get("groupes") or {}
    voulus = {str(f) for f in foyers}
    return [
        str(pid)
        for g in (groupes.get("expose") or [])
        if str(g.get("household_id")) in voulus
        for pid in (g.get("lecteurs") or [])
    ]


def choc_pour_persona(persona_id: str, evenement: str = CHOC_REFERENCE) -> str:
    """Écrit l'événement de référence restreint à ce run, et rend son nom pour `make run`.

    Le fichier dérivé porte le même texte, la même cadence et les mêmes jours que la référence.
    Seule l'exposition change, et seulement pour un run UNITAIRE : il ne porte qu'un habitant, et
    désigner les autres ne ferait qu'ajouter des identifiants inertes dans la déclaration.

    ⚠ RUN UNITAIRE — LA RÈGLE EST FORCÉE À `agents`, et pas seulement complétée. Jusqu'au
    2026-09-22 cette fonction posait `exposition.agents` en laissant `regle` intacte : sur
    `c3_panne_reseau` (`regle: mode`) la liste d'agents aurait été écrite, acceptée, et IGNORÉE.
    Sur une population d'un seul habitant le résultat est le même par accident, ce qui est la
    pire des situations : la déclaration dit autre chose que ce qu'elle fait.

    ⚠ JEU DE PLUSIEURS AGENTS — L'EXPOSITION DÉCLARÉE EST GARDÉE TELLE QUELLE, et seules deux
    règles sont admises. `foyers` (les foyers exposés ET leurs co-résidents témoins sont dans la
    déclaration, tirés du manifeste de la population) et `agents` (dont au moins un doit être
    dans la population). Toute autre règle — `mode`, un tirage — est REFUSÉE : la réécrire en
    `agents` désignerait le nom de la population comme un habitant, et le run se déroulerait sans
    que personne ne soit exposé.

    `modes` est CONSERVÉ s'il est déclaré. La branche `agents` le lit et restreint l'agent
    désigné à ses trajets dans ces modes — c'est ce qui garde 861500 exposé à la panne de métro
    sur ses seuls trajets en transports collectifs, et pas au volant de sa voiture.
    """
    import yaml

    source = source_evenement(evenement)
    declaration = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    exposition = declaration.setdefault("exposition", {})
    regle_origine = exposition.get("regle")

    _, taille, est_un_jeu, ids = resoudre_population_et_taille(persona_id)
    if est_un_jeu:
        if regle_origine not in ("foyers", "agents"):
            message = (
                f"[ALARME] [{persona_id}] « {evenement} » déclare `regle: {regle_origine}` : sur "
                f"un jeu de {taille} agents, seules `foyers` et `agents` désignent quelqu'un. "
                f"Déclarer l'exposition dans l'événement, pas la laisser deviner."
            )
            logger.error(message)
            raise ValueError(message)
        if regle_origine == "foyers":
            foyers_pop, exposes_manifeste = foyers_de_la_population(persona_id)
            declares = [str(f) for f in exposition.get("foyers") or []]
            if foyers_pop and not set(declares) & foyers_pop:
                # Les foyers déclarés sont ceux d'UNE autre population (a09 porte ceux de
                # population_20_foyers_059) : sur celle-ci, personne ne lirait. Le manifeste de
                # la population désigne les siens ; à défaut, le bras est refusé.
                if not exposes_manifeste:
                    message = (
                        f"[ALARME] [{persona_id}] « {evenement} » expose les foyers {declares}, "
                        f"AUCUN n'est dans la population, et son MANIFEST n'en désigne pas — le run "
                        f"se déroulerait sans lecteur."
                    )
                    logger.error(message)
                    raise ValueError(message)
                logger.warning(
                    f"[{persona_id}] « {evenement} » : foyers déclarés {declares} absents de la "
                    f"population — exposition prise au MANIFEST : {exposes_manifeste}."
                )
                exposition["foyers"] = exposes_manifeste
            # Les lecteurs désignés viennent du même manifeste que les foyers. Ceux que déclare
            # l'événement, s'ils ne sont pas dans la population, sont ceux d'une autre.
            du_manifeste = lecteurs_du_manifeste(persona_id, exposition.get("foyers") or [])
            declares_l = [str(x) for x in exposition.get("lecteurs") or []]
            if declares_l and not set(declares_l) & set(ids):
                if not du_manifeste:
                    message = (
                        f"[ALARME] [{persona_id}] « {evenement} » désigne les lecteurs "
                        f"{declares_l}, AUCUN n'est dans la population, et son MANIFEST n'en "
                        f"désigne pas — le run se déroulerait sans lecteur."
                    )
                    logger.error(message)
                    raise ValueError(message)
                declares_l = []
            if du_manifeste and not declares_l:
                exposition["lecteurs"] = du_manifeste
                logger.info(
                    f"[{persona_id}] « {evenement} » : lecteurs désignés par le MANIFEST : "
                    f"{du_manifeste} (au lieu d'un tirage parmi les adultes)."
                )
        if regle_origine == "agents":
            presents = set(map(str, exposition.get("agents") or [])) & set(ids)
            if not presents:
                message = (
                    f"[ALARME] [{persona_id}] « {evenement} » désigne "
                    f"{exposition.get('agents')} et AUCUN n'est dans la population — le run "
                    f"se déroulerait sans exposé."
                )
                logger.error(message)
                raise ValueError(message)
        portee = f"l'exposition déclarée (`{regle_origine}`) est conservée sur {taille} agents"
    else:
        exposition["regle"] = "agents"
        exposition["agents"] = [ids[0]]
        # `part` et `graine` n'ont de sens que pour un tirage : les laisser serait déclarer un
        # paramètre sans effet, ce que la garde de chargement reproche déjà aux textes.
        for inerte in ("part", "graine"):
            exposition.pop(inerte, None)
        portee = (
            f"l'exposition est restreinte au persona {ids[0]} ; la règle passe de "
            f"`{regle_origine}` à `agents`, les modes déclarés sont conservés"
        )

    nom = nom_choc_derive(persona_id, evenement)
    cible = EVENEMENTS_DIR / f"{nom}.yaml"
    cible.write_text(
        f"# ENGENDRÉ par scripts/experiment/run_sequential_cohort.py — ne pas éditer.\n"
        f"# Source : {source.name}. {portee[0].upper() + portee[1:]}.\n"
        + yaml.safe_dump(declaration, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    logger.info(
        f"[{persona_id}] événement dérivé de {source.name} → {cible.name} "
        f"(règle {regle_origine} → {exposition.get('regle')}, modes {exposition.get('modes') or 'tous'})"
    )
    return nom


def verifier_reprise_possible(workdir: Path) -> bool:
    """Ce workdir porte-t-il un bras SUSPENDU à reprendre ?

    Seul `reprise.json`, écrit à la suspension, le dit : il nomme le run à reprendre, et une
    reprise se nomme (ticket 091). La version précédente concluait à une reprise dès qu'un
    `moves.csv` et un `decisions_rejeu.jsonl` étaient là — c'est-à-dire après un bras TERMINÉ,
    dont les livrables sont copiés ici — puis lançait `CONT=1` sans nom, que le contrôleur refuse.
    """
    if reprise_en_attente(workdir) is not None:
        return True
    if (workdir / "moves.csv").is_file():
        logger.warning(
            f"[reprise] {workdir} porte les livrables d'un bras déjà TERMINÉ, sans "
            f"`{FICHIER_REPRISE}` : il est rejoué à neuf, pas repris."
        )
    return False


def preparer_workdir(
    workdir: Path,
    persona_id: str,
    branch: str,
    force_fresh: bool = False,
    horizon_jours: int = HORIZON_JOURS_DEFAUT,
) -> bool:
    """Initialise le dossier d'exécution isolé pour ce persona et cette branche."""
    workdir.mkdir(parents=True, exist_ok=True)
    # Le choc se déclare à `make run` (CHOC=…), pas en posant un fichier dans le workdir : le
    # contrôleur y écrit SA copie de la déclaration en fin de course, il ne l'y lit jamais.

    pop_file_container, pop_size, is_dataset, _ = resoudre_population_et_taille(persona_id)

    # 1. Configurer sim_params.yaml pour population_size
    sim_params_path = Path("services/GAMA/CityTransport/config/sim_params.yaml")
    if sim_params_path.is_file():
        import re
        text = sim_params_path.read_text(encoding="utf-8")
        text = re.sub(r"^population_size:\s*\d+", f"population_size: {pop_size}", text, flags=re.MULTILINE)
        text = re.sub(
            r"^simulation_max_days:\s*\d+",
            f"simulation_max_days: {int(horizon_jours)}",
            text,
            flags=re.MULTILINE,
        )
        sim_params_path.write_text(text, encoding="utf-8")

    # 2. Configurer config.yaml pour pointer sur le fichier de population résolu
    config_yaml_path = Path("services/llm-agents/config/config.yaml")
    if config_yaml_path.is_file():
        import re
        c_text = config_yaml_path.read_text(encoding="utf-8")
        c_text = re.sub(
            r"population_file:\s*/data/eqasim-output/.*",
            f"population_file: {pop_file_container}",
            c_text,
        )
        config_yaml_path.write_text(c_text, encoding="utf-8")

    is_resume = verifier_reprise_possible(workdir)
    if is_resume and not force_fresh:
        logger.info(f"[{persona_id}_{branch}] Reprise à chaud détectée dans {workdir} (CONT=1 activable).")
        return True
    elif force_fresh and workdir.exists():
        logger.info(f"[{persona_id}_{branch}] Mode --force-fresh actif : démarrage à neuf.")
        return False
    return False


def executer_run_persona(
    persona_id: str,
    branch: str,
    workdir: Path,
    is_resume: bool,
    dry_run: bool = False,
    extra_env: dict[str, str] | None = None,
    arret_extinction: bool = False,
    jours_apres_extinction: int = JOURS_APRES_EXTINCTION,
    evenement: str = CHOC_REFERENCE,
    horizon_jours: int = HORIZON_JOURS_DEFAUT,
) -> int:
    """Lance un run GAMA/Python de `horizon_jours` jours calendaires (42 par défaut)."""
    env = os.environ.copy()
    env["WORKDIR"] = str(workdir.resolve())
    env["EXPERIMENT_SURVEY_ENABLED"] = "1"
    # Ticket 105 — arme les deux motifs d'arrêt : quota journalier ET replis consécutifs.
    # Toute campagne est donc protégée d'office, sans levier à penser au lancement.
    env["EXPERIMENT_STOP_ON_FALLBACK"] = "1"
    pop_file_container, pop_size, is_dataset, agent_ids = resoudre_population_et_taille(persona_id)
    if is_dataset and agent_ids:
        env["EXPERIMENT_TARGET_PERSONAS"] = ",".join(agent_ids)
    else:
        env["EXPERIMENT_TARGET_PERSONAS"] = str(persona_id)
    for nom, (valeur, _champ, _attendu) in REGLAGES_CAMPAGNE.items():
        env[nom] = valeur
    env["NO_WEEKEND_DEPARTURES"] = "true"
    # ⚠ `MEMOIRE__IMPORTANCE_CHOC=0.50` RETIRÉ le 2026-09-19. Le choc du J15 vaut exactement
    # 0,70 et la comparaison est `>=` : il franchit le seuil d'origine sans qu'on l'abaisse.
    # L'abaisser n'élargissait que le vivier C, c'est-à-dire le rappel hors contexte.
    # Ticket 095, lot C — UN MODÈLE PAR FONCTION, adopté le 2026-09-21.
    #
    # Jusqu'ici, une liste plate unique : les 751 requêtes de la campagne du ticket 077 sont
    # toutes parties sur la même famille, et les deux plus gros postes — la décision et la
    # réflexion du soir, 46 % des jetons d'entrée chacun — se disputaient la même clé.
    #
    # La DÉCISION est la variable mesurée de l'article : elle garde `gemini-3.1`, inchangé, pour
    # rester comparable aux campagnes précédentes. L'auto-réflexion la suit — rare (13 par run)
    # et à fort enjeu, elle relit toute la mémoire longue. La réflexion du soir et l'enquête
    # passent sur `gemini-3.5`.
    #
    # ⚠ LE NOM EST `INSTANCES_ADMISES`, le nom NU du champ. Ce module a posé
    # `LLM__INSTANCES_ADMISES` du 2026-09-08 au 2026-09-21 : mauvais nom, absent du passe-plat
    # compose, et `config.yaml` primait de toute façon. La restriction des campagnes de
    # septembre venait donc de `config.yaml`, pas d'ici — aucun bras n'a jamais déclaré la
    # sienne. Vérifié sur `identite_run.json` du 2026-09-21 09:23.
    #
    # ⚠ DEUX INSTANCES MINIMUM PAR CATÉGORIE, et jamais `force_provider` : le worker ne retente
    # que si aucune instance n'est épinglée. Les quatorze `HTTP 503 high demand` de la campagne
    # du 19 septembre sont passés précisément parce qu'il restait une seconde clé.
    #
    # ⚠ CE N'EST PAS UN RÉGLAGE D'INFRASTRUCTURE. Changer le modèle des réflexions change le
    # contenu de la mémoire, donc les décisions. Le binding entre dans `identite_run.json` et
    # doit rester IDENTIQUE dans tous les bras d'une campagne — sinon l'écart mesuré n'est plus
    # attribuable au choc.
    if "INSTANCES_ADMISES" in os.environ and os.environ["INSTANCES_ADMISES"]:
        env["INSTANCES_ADMISES"] = os.environ["INSTANCES_ADMISES"]
    else:
        env["INSTANCES_ADMISES"] = json.dumps(
            {
                "defaut": ["google_gemini31_key1", "google_gemini31_key2"],
                "itinary_multi_agent": ["google_gemini31_key1", "google_gemini31_key2"],
                "ltm_self_reflection": ["google_gemini31_key1", "google_gemini31_key2"],
                "stm_reflection": ["google_gemini35_key1", "google_gemini35_key2"],
                # 2026-09-24 : les enquêtes rejoignent la 3.1. Mesuré sur 861500 : la STM pèse
                # 49 % des requêtes et la décision 43 % — la 3.5 seule portait STM + enquêtes.
                "enquete_affinite": ["google_gemini31_key1", "google_gemini31_key2"],
            }
        )
    env["DATA__POPULATION_SIZE"] = str(pop_size)

    # Ticket 091 — une reprise se NOMME. `CONT=1` seul fait refuser le démarrage du contrôleur
    # (`CONTINUE_RUN sans REPRISE`) : c'est le nom du run suspendu, écrit dans `reprise.json`,
    # qui fait la reprise.
    reprise = reprise_en_attente(workdir) if is_resume else None
    if is_resume and reprise is None:
        logger.error(
            f"[ALARME] [{persona_id}_{branch}] reprise demandée sans `{FICHIER_REPRISE}` dans "
            f"{workdir} — on ne sait pas quel run reprendre. Bras REFUSÉ."
        )
        return 8

    # Le bras d'ablation de la fenêtre passe par ici :
    #   extra_env={"MEMOIRE__FENETRE_CHANGEMENTS_JOURS": "7"}
    # Tout ce qui est posé dans `env` se retrouve dans `identite_run.json` (ticket 077, lot K),
    # donc un bras ne peut plus se confondre avec un autre après coup.
    if extra_env is None:
        extra_env = {}
        for var in [
            "MEMOIRE__FENETRE_CHANGEMENTS_JOURS",
            "MEMOIRE__CHANGEMENTS_MAX",
            "MEMOIRE__IMPORTANCE_CHOC",
            # Ticket 095, lot A — le bras « fenêtre dérivée » et le bras de contrôle
            # « fenêtre fixe » se déclarent par MEMOIRE__MODE_FENETRE_CHANGEMENTS.
            "MEMOIRE__MODE_FENETRE_CHANGEMENTS",
            "MEMOIRE__SEUIL_SERVICE_CHANGEMENT",
            "MEMOIRE__PLANCHER_CHANGEMENT_JOURS",
            "MEMOIRE__PLAFOND_CHANGEMENT_JOURS",
            # Le modèle de gravité : c'est lui qui décide ce que vaut un retard long.
            "MEMOIRE__RETARD_SATURATION",
            "MEMOIRE__RETARD_GRAVITE_MAX",
            "MEMOIRE__RETARD_REF_S",
            # Ticket 100, lot 4 — le partage dans le foyer appartient à l'expérience.
            "MEMOIRE__PARTAGE_FOYER_ENABLED",
            # Tâches en vol : elles fixent la taille des micro-lots, donc les prompts servis.
            "WORLD__WORKER_CONCURRENCY",
            # 2026-09-25 — espace de rejeu à prompt exact, partagé par les deux bras.
            "REJEU_AB",
        ]:
            if var in os.environ:
                extra_env[var] = os.environ[var]

    if extra_env:
        env.update(extra_env)

    # CHOC : c'est ICI que les deux branches se séparent. Sans lui, `make run` laisse la
    # déclaration de `config.yaml` en place et le témoin subit le choc du bras traité.
    # CACHE=0 : la clé du cache sémantique ne porte aucune durée, une décision prise avant le
    # choc pourrait être resservie pendant.
    choc = nom_choc_derive(persona_id, evenement) if branch == "treated" else "0"
    cmd = ["make", "run", "OFFLINE=1", "CACHE=0", f"CHOC={choc}"]
    if reprise:
        cmd.append(f"REPRISE={reprise['archive']}")

    delai = delai_de_garde(pop_size, horizon_jours)
    logger.info(
        f"[{persona_id}_{branch}] Démarrage de la simulation ({horizon_jours} jours calendaires, "
        f"{pop_size} agent(s), délai de garde {delai / 3600:.1f} h)..."
    )
    logger.info(f"[{persona_id}_{branch}] Workdir : {workdir}")
    logger.info(
        f"[{persona_id}_{branch}] Reprise à chaud : "
        f"{('REPRISE=' + reprise['archive']) if reprise else 'non'}"
    )
    logger.info(f"[{persona_id}_{branch}] Commande : {' '.join(cmd)}")

    if dry_run:
        logger.info(f"[dry-run] Rien n'est lancé pour {persona_id}_{branch}.")
        return 0

    if lanceur_en_cours():
        logger.error(
            f"[ALARME] [{persona_id}_{branch}] un lanceur GAMA tourne déjà — bras REFUSÉ. "
            f"`make run` se contenterait d'écrire « Lancement ignoré » et de rendre 0, et ce "
            f"bras regarderait le run d'un autre. Arrêter d'abord : make stop-run"
        )
        return 3

    if branch == "treated":
        choc_pour_persona(persona_id, evenement)


    # Exécution du processus. L'instant de lancement date les marqueurs : seul un marqueur
    # d'attente écrit APRÈS lui suspend ce bras.
    lance_a = time.time()
    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    log_path = workdir / "run_orchestrateur.log"
    with open(log_path, "a", encoding="utf-8") as lf:
        if process.stdout:
            for line in process.stdout:
                lf.write(line)
                if any(k in line for k in ["[enquete]", "[hibernation]", "[choc]", "ERROR", "WARNING", "✅", "⏳", "🚀", "🛑", "♻️", "Services prêts", "Controller", "API prête", "Lancement"]):
                    sys.stdout.write(f"[{persona_id}_{branch}] {line}")
                    sys.stdout.flush()

    process.wait()
    retcode = process.returncode
    if retcode != 0:
        logger.error(f"[ALARME] [{persona_id}_{branch}] `make run` a rendu {retcode} — bras abandonné.")
        return retcode

    # ⚠ `make run` a rendu la main, PAS le run : il lance GAMA en arrière-plan. Tout ce qui suit
    # se passe pendant que la simulation tourne.

    # 1. Vérifier les réglages AVANT de payer trois heures. L'identité est écrite en ~20 s.
    archive = attendre_identite(
        controller_demarre_a(), reprise=reprise["archive"] if reprise else None
    )
    if archive is None:
        logger.error(
            f"[ALARME] [{persona_id}_{branch}] aucune identité de run POSTÉRIEURE au "
            f"démarrage du contrôleur après {ATTENTE_IDENTITE_S} s — sans elle on ne peut rien "
            f"affirmer de ce bras. Arrêt. (Un contrôleur lancé avant `make run`, par exemple "
            f"par `make up`, peut avoir posé une identité périmée dans le même répertoire.)"
        )
        subprocess.run(["make", "stop-run"], check=False)
        return 4

    attendus = reglages_attendus(extra_env)
    ecarts = ecarts_de_reglages(archive, attendus)
    if ecarts:
        logger.error(
            f"[ALARME] [{persona_id}_{branch}] le bras ne tourne pas avec ses réglages — "
            f"arrêt immédiat :\n  - " + "\n  - ".join(ecarts)
            + f"\n  ({archive / 'identite_run.json'})\n"
            f"  Vérifier que ces variables sont déclarées en passe-plat dans "
            f"infra/docker-compose.yml : compose ne transmet que ce qu'il déclare."
        )
        subprocess.run(["make", "stop-run"], check=False)
        return 5
    logger.info(
        f"[{persona_id}_{branch}] réglages conformes ({len(attendus)} vérifiés) — "
        f"{archive.name}"
    )
    journaliser_qui_sert(persona_id, branch, archive)

    # 2. Attendre la VRAIE fin du run.
    if not attendre_fin_du_run(
        persona_id,
        branch,
        archive,
        timeout_s=delai,
        arret_extinction=arret_extinction,
        jours_apres_extinction=jours_apres_extinction,
    ):
        return 6

    # Le lanceur a disparu — ce qui arrive AUSSI quand le garde-fou du ticket 105 a arrêté le
    # contrôleur. Le 2026-09-24, ce cas a été compté comme un succès : l'orchestrateur a lancé le
    # témoin sur le quota épuisé, puis marqué l'expérience « terminée » après un jour simulé.
    suspension = suspension_du_run(archive, depuis=lance_a)
    if suspension is not None:
        (workdir / FICHIER_REPRISE).write_text(
            json.dumps(
                {"archive": archive.name, **suspension,
                 "suspendu_le": datetime.now().isoformat(timespec="seconds")},
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        logger.error(
            f"[ALARME] [{persona_id}_{branch}] bras SUSPENDU par le garde-fou "
            f"(motif {suspension.get('motif')}, jour simulé {suspension.get('jour_simule')}, "
            f"réouverture {suspension.get('resume_at') or 'non annoncée'}) — run {archive.name}. "
            f"Relancer la même expérience le reprendra (REPRISE={archive.name})."
        )
        return CODE_BRAS_SUSPENDU

    reprise_faite = workdir / FICHIER_REPRISE
    if reprise_faite.is_file():
        # Le bras repris est allé au bout : on garde la trace de la suspension, sous un nom qui
        # ne déclenchera plus de reprise.
        reprise_faite.rename(workdir / f"reprise_faite_{datetime.now():%Y%m%d_%H%M%S}.json")
    logger.info(f"[{persona_id}_{branch}] Bras terminé.")
    return 0


# Code de retour d'un bras que le garde-fou du ticket 105 a SUSPENDU (quota ou replis) : ni un
# succès — le run n'est pas allé au bout —, ni un échec définitif — il se reprend.
CODE_BRAS_SUSPENDU = 7
FICHIER_REPRISE = "reprise.json"


def suspension_du_run(archive: Path | None, depuis: float | None = None) -> dict | None:
    """Le marqueur d'attente que le contrôleur a posé PENDANT ce bras, ou None.

    ⚠ Un bras repris rejoue dans le MÊME répertoire que celui qui s'était arrêté : le marqueur de
    l'arrêt précédent y est encore. Seul un marqueur écrit depuis le lancement de ce bras dit que
    CE bras a été suspendu.
    """
    if archive is None:
        return None
    marqueur = archive / "en_attente_quota.json"
    if not marqueur.is_file():
        return None
    if depuis is not None and marqueur.stat().st_mtime < depuis - 5:
        return None
    try:
        return json.loads(marqueur.read_text(encoding="utf-8")) or {"motif": "inconnu"}
    except (OSError, ValueError):
        return {"motif": "illisible"}


def reprise_en_attente(workdir: Path) -> dict | None:
    """Le bras suspendu que ce workdir doit reprendre (`reprise.json`), ou None."""
    fichier = workdir / FICHIER_REPRISE
    if not fichier.is_file():
        return None
    try:
        donnees = json.loads(fichier.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return donnees if donnees.get("archive") else None


def lanceur_en_cours() -> bool:
    """Un lanceur GAMA headless tourne-t-il déjà ?

    `make run` se contente d'écrire « Lancement ignoré » sur sa sortie standard et rend 0 :
    sans ce garde, un bras croirait tourner alors qu'il regarde le run d'un autre.
    """
    return (
        subprocess.run(
            ["pgrep", "-f", "launch_headless.py"], capture_output=True, text=True
        ).returncode
        == 0
    )


def derniere_journee_simulee(archive: Path | None) -> str:
    """La dernière journée simulée atteinte, pour journaliser un avancement et non un silence.

    ⚠ `[sync] END` n'apparaît qu'une fois la boucle de simulation démarrée. Pendant l'amorçage —
    peuplement, itinéraires initiaux, qui durent d'autant plus que le cache OSMnx est froid — il
    n'y a rien à lire, et le battement affichait « ? ». Sur un run de six heures, « ? » ne
    distingue pas « ça amorce » de « c'est bloqué », ce qui est précisément la question que ce
    battement existe pour trancher. Il dit donc maintenant l'amorçage quand c'est là qu'on en est.
    """
    if archive is None:
        return "?"
    log = archive / "app.log"
    if not log.is_file():
        return "journal pas encore écrit"
    try:
        lignes = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "?"
    for ligne in reversed(lignes[-4000:]):
        if "[sync] END sim_time=" in ligne:
            return ligne.split("sim_time=", 1)[1].split(" state_update", 1)[0].strip()
    # Détection précoce d'une erreur fatale à l'initialisation (évite de tourner à blanc)
    for ligne in reversed(lignes[-4000:]):
        if any(err in ligne for err in ["[ALARME] [population]", "RuntimeError: [population]", "Error in ASGI Framework"]):
            return f"échec initialisation — {ligne.strip()[:70]}"
    # Pas encore un seul cycle : dire où en est l'amorçage plutôt que de rendre un point
    # d'interrogation, qui se lit comme une panne.
    for ligne in reversed(lignes[-4000:]):
        if "[bootstrap]" in ligne:
            return f"amorçage — {ligne.split('[bootstrap]', 1)[1].strip()[:70]}"
        if "INITIALISATION" in ligne:
            return f"amorçage — {ligne.split('INITIALISATION', 1)[1].strip()[:70]}"
    return "aucun cycle, aucun amorçage journalisé"


def date_du_souvenir_declare(archive: Path | None) -> str | None:
    """La date simulée de la DERNIÈRE application de l'événement déclaré, ou None.

    C'est elle que l'arrêt anticipé surveille — pas « plus aucun souvenir de choc ne pèse »,
    qui n'arrive qu'en toute fin de run puisque l'agent fabrique ses propres souvenirs de
    gravité de choc (le bras témoin, qui ne subit rien, en produit trois).

    La DERNIÈRE et non la première : un événement à deux jours (c6 : J15 puis J16) n'est éteint
    que quand le second souvenir est sorti. Surveiller le premier arrêterait le run alors que
    l'agent porte encore le second dans son contexte.

    Rend None tant que la trace est vide — un run dont l'événement ne s'est pas encore appliqué
    ne peut pas s'être éteint, et l'attente continue.
    """
    if archive is None:
        return None
    trace = archive / "evenements.jsonl"
    if not trace.is_file():
        return None
    dates: list[str] = []
    try:
        with open(trace, encoding="utf-8", errors="replace") as f:
            for ligne in f:
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    horodatage = json.loads(ligne).get("horodatage_simule")
                except json.JSONDecodeError:
                    continue  # ligne tronquée : le fichier s'écrit pendant qu'on le lit
                if isinstance(horodatage, str) and len(horodatage) >= 10:
                    dates.append(horodatage[:10])
    except OSError:
        return None
    return max(dates) if dates else None


def journaliser_qui_sert(persona_id: str, branch: str, archive: Path | None) -> None:
    """Dit QUELS MODÈLES vont produire ce bras, au lancement et pas après coup.

    La restriction d'instances est déclarée par catégorie dans `infra/docker-compose.yml` et
    n'apparaissait nulle part dans la sortie du lanceur : il fallait entrer dans le conteneur ou
    ouvrir `identite_run.json` pour savoir que les décisions passaient par deux clés Gemini 3.1
    flash-lite et rien d'autre. Le 2026-09-22, cela a valu une annonce fausse — « le pool
    complet » — pendant que le run tournait sur deux clés d'un seul modèle, lesquelles se sont
    mises à rendre 503.

    Un bras dont on ne sait pas qui l'a produit ne se compare à rien. La ligne est donc au
    journal, au moment où le bras démarre.
    """
    if archive is None:
        return
    identite = archive / "identite_run.json"
    if not identite.is_file():
        logger.warning(
            f"[{persona_id}_{branch}] identite_run.json absent : impossible de dire quels "
            f"modèles servent ce bras."
        )
        return
    try:
        d = json.loads(identite.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"[{persona_id}_{branch}] identite_run.json illisible ({exc}).")
        return
    modeles = d.get("modeles_admis") or ["(non déclaré)"]
    routage = d.get("routage_instances") or {}
    logger.info(f"[{persona_id}_{branch}] modèles admis : {', '.join(modeles)}")
    for categorie in ("itinary_multi_agent", "stm_reflection", "ltm_self_reflection"):
        instances = routage.get(categorie)
        if instances:
            logger.info(f"[{persona_id}_{branch}]   {categorie} ← {', '.join(instances)}")
    if not routage:
        logger.info(
            f"[{persona_id}_{branch}]   aucune restriction de routage : toutes les instances "
            f"déclarées peuvent servir."
        )


def attendre_fin_du_run(
    persona_id: str,
    branch: str,
    archive: Path | None,
    timeout_s: int = ATTENTE_RUN_S,
    arret_extinction: bool = False,
    jours_apres_extinction: int = JOURS_APRES_EXTINCTION,
) -> bool:
    """Attend que le lanceur GAMA ait disparu. Rend False si le délai de garde est dépassé.

    ⚠ `make run OFFLINE=1` NE BLOQUE PAS : sa recette lance `launch_headless.py` en arrière-plan
    (`&`) et rend la main en une vingtaine de secondes. Le 2026-09-19, l'orchestrateur a pris
    cela pour la fin du run, est passé au bras suivant, dont le `make stop-run` a tué le premier
    trente-quatre secondes après son démarrage.

    Le lanceur, lui, vit exactement le temps du run : GAMA Server tue l'expérience dès que son
    client WebSocket se déconnecte. C'est le signal franc.

    ⚠ `arret_extinction` RACCOURCIT LE BRAS, et deux bras de longueurs différentes ne se
    comparent pas jour à jour. Le témoin ne subit aucun événement déclaré : sa trace est vide,
    aucune date n'est trouvée, et il ira donc jusqu'à son horizon complet pendant que le bras
    traité s'arrêtera plus tôt. C'est voulu — les jours payés après l'extinction n'apprennent
    rien — mais l'analyse DOIT tronquer les deux bras au même jour simulé. Le fichier
    `arret_sur_extinction.json` écrit dans le répertoire du run porte ce jour ; c'est lui qu'on
    lit, pas la longueur du journal.
    """
    debut = time.monotonic()
    dernier_journal = 0.0
    souvenir_du: str | None = None
    extinction_annoncee = False
    dernier_examen = -PAS_DE_JOURNAL_S  # premier examen au premier tour, sans attendre 5 min
    while lanceur_en_cours():
        ecoule = time.monotonic() - debut
        if ecoule > timeout_s:
            logger.error(
                f"[ALARME] [{persona_id}_{branch}] délai de garde dépassé "
                f"({timeout_s // 3600} h) et le lanceur tourne toujours. Le run n'est PAS tué : "
                f"un run lent n'est pas un run mort, c'est à l'auteur de trancher."
            )
            return False
        if ecoule - dernier_journal >= PAS_DE_JOURNAL_S:
            dernier_journal = ecoule
            derniere = derniere_journee_simulee(archive)
            logger.info(
                f"[{persona_id}_{branch}] en cours depuis {int(ecoule // 60)} min — "
                f"journée simulée : {derniere}"
            )
            if "échec initialisation" in derniere:
                logger.error(
                    f"[ALARME] [{persona_id}_{branch}] Échec d'initialisation détecté dans app.log — arrêt du run."
                )
                subprocess.run(["make", "stop-run"], check=False)
                return False
        # Arrêt anticipé : le souvenir déclaré est sorti du bloc depuis N jours VÉCUS.
        # Vérifié au pas du journal (5 min) et non à celui du sondage (30 s) : la détection relit
        # tout app.log, qui atteint des dizaines de méga-octets sur une campagne de cinquante
        # jours. L'extinction est un événement à l'échelle de la journée simulée — cinq minutes de
        # latence ne coûtent rien, soixante relectures inutiles par demi-heure, si.
        if arret_extinction and archive and (ecoule - dernier_examen) >= PAS_DE_JOURNAL_S:
            dernier_examen = ecoule
            if souvenir_du is None:
                souvenir_du = date_du_souvenir_declare(archive)
                if souvenir_du:
                    logger.info(
                        f"[{persona_id}_{branch}] arrêt sur extinction armé — souvenir déclaré "
                        f"du {souvenir_du}, observation de {jours_apres_extinction} jours vécus "
                        f"après sa sortie du bloc « ce qui a changé récemment »."
                    )
            journal = archive / "app.log"
            if souvenir_du and journal.is_file():
                try:
                    with open(journal, encoding="utf-8", errors="replace") as f:
                        vue, ecoules = analyser_extinction(f, souvenir_du)
                except OSError:
                    vue, ecoules = False, 0
                if vue and not extinction_annoncee:
                    extinction_annoncee = True
                    logger.info(
                        f"[{persona_id}_{branch}] extinction du souvenir du {souvenir_du} "
                        f"détectée — encore {jours_apres_extinction} jours vécus à observer."
                    )
                if vue and ecoules >= jours_apres_extinction:
                    dernier_jour = derniere_journee_simulee(archive)
                    logger.info(
                        f"[{persona_id}_{branch}] {ecoules} jours vécus depuis l'extinction du "
                        f"{souvenir_du} (dernier jour simulé : {dernier_jour}) — arrêt anticipé. "
                        f"Tronquer le bras témoin à ce jour pour comparer."
                    )
                    try:
                        (archive / "arret_sur_extinction.json").write_text(
                            json.dumps(
                                {
                                    "souvenir_du": souvenir_du,
                                    "jours_apres_extinction": ecoules,
                                    "seuil_jours": jours_apres_extinction,
                                    "dernier_jour_simule": dernier_jour,
                                    "persona": persona_id,
                                    "branche": branch,
                                },
                                ensure_ascii=False,
                                indent=2,
                            ),
                            encoding="utf-8",
                        )
                    except OSError as exc:
                        logger.error(
                            f"[ALARME] [{persona_id}_{branch}] arrêt anticipé décidé mais la "
                            f"preuve n'a pas pu être écrite ({exc}) : le bras est tronqué et "
                            f"rien ne dit à quel jour. L'analyse appariée est compromise."
                        )
                    time.sleep(3)
                    subprocess.run(["make", "stop-run"], check=False)
                    break

        # Détection de fin de simulation via gama_headless.log (sécurité anti-blocage)
        if archive:
            gama_log = archive / "gama_headless.log"
            if gama_log.is_file():
                try:
                    tail_txt = gama_log.read_text(encoding="utf-8", errors="replace")[-3000:]
                    if "Simulation stopped after" in tail_txt:
                        logger.info(
                            f"[{persona_id}_{branch}] 'Simulation stopped after' détecté dans {gama_log.name} — "
                            f"arrêt propre du run."
                        )
                        time.sleep(3)
                        subprocess.run(["make", "stop-run"], check=False)
                        break
                except OSError:
                    pass
        time.sleep(PAS_DE_SONDAGE_S)
    logger.info(
        f"[{persona_id}_{branch}] lanceur terminé après "
        f"{int((time.monotonic() - debut) // 60)} min."
    )
    return True


COMPOSE = [
    "docker", "compose", "-f", "infra/docker-compose.yml", "--project-directory", ".",
]


def controller_demarre_a() -> float | None:
    """Instant de démarrage du conteneur contrôleur, en secondes epoch. None si indisponible."""
    try:
        cid = subprocess.run(
            [*COMPOSE, "ps", "-q", "controller"], capture_output=True, text=True, timeout=30
        ).stdout.strip().splitlines()
        if not cid:
            return None
        brut = subprocess.run(
            ["docker", "inspect", cid[0], "--format", "{{.State.StartedAt}}"],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not brut:
        return None
    # RFC3339 à la nanoseconde : `datetime.fromisoformat` s'arrête à la microseconde.
    brut = brut.replace("Z", "+00:00")
    if "." in brut:
        tete, reste = brut.split(".", 1)
        frac, _, fuseau = reste.partition("+")
        brut = f"{tete}.{frac[:6]}+{fuseau}"
    try:
        return datetime.fromisoformat(brut).timestamp()
    except ValueError:
        return None


def attendre_identite(
    depuis: float | None = None,
    timeout_s: int = ATTENTE_IDENTITE_S,
    reprise: str | None = None,
) -> Path | None:
    """Attend une identité de run écrite APRÈS `depuis`, et rend le répertoire qui la porte.

    ⚠ La fraîcheur n'est pas un luxe. Le nom du répertoire de run a une granularité à la
    MINUTE : deux contrôleurs démarrés dans la même minute le partagent, et `identite_run.ecrire`
    laisse en place l'identité déjà posée — c'est la règle du ticket 091, et elle est bonne.
    Conséquence mesurée le 2026-09-19 à 16:57 : un contrôleur lancé par `make up` (sans les
    réglages d'expérience, sans le choc) a écrit l'identité à 16:57:12, le contrôleur du run l'a
    remplacé à 16:57:35 — et le bras a été jugé sur l'identité du premier, qui annonçait
    « choc : aucun » et les valeurs par défaut.
    """
    debut = time.monotonic()
    prevenu = False
    while time.monotonic() - debut < timeout_s:
        archive = archive_du_run()
        fichier = (archive / "identite_run.json") if archive else None
        if reprise is not None:
            # REPRISE NOMMÉE : l'identité est celle du run repris, posée à son premier départ et
            # laissée en place par la règle du ticket 091 — elle est donc ANTÉRIEURE au contrôleur,
            # par construction. Ce qui fait foi ici est le NOM du répertoire servi.
            if archive is not None and archive.name == reprise and fichier and fichier.is_file():
                return archive
            time.sleep(2)
            continue
        if fichier and fichier.is_file():
            if depuis is None or fichier.stat().st_mtime >= depuis - 5:
                return archive
            if not prevenu:
                prevenu = True
                logger.info(
                    f"[identite] {fichier} est antérieure au démarrage du contrôleur — "
                    f"identité d'un contrôleur précédent, on attend la bonne."
                )
        time.sleep(2)
    return None


def ecarts_de_reglages(archive: Path, attendus: dict[str, Any]) -> list[str]:
    """Les réglages du run qui ne sont pas ceux demandés, nommés un par un."""
    fichier = archive / "identite_run.json"
    try:
        identite = json.loads(fichier.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"identite_run.json illisible ({exc})"]
    ecarts = []
    for champ, attendu in attendus.items():
        obtenu = identite.get(champ, "<absent>")
        if isinstance(attendu, float) and isinstance(obtenu, (int, float)):
            identique = abs(float(obtenu) - attendu) < 1e-9
        else:
            identique = obtenu == attendu
        if not identique:
            ecarts.append(f"{champ} : attendu {attendu!r}, obtenu {obtenu!r}")
    return ecarts


def reglages_attendus(extra_env: dict[str, str] | None = None) -> dict[str, Any]:
    """Ce que l'identité du run doit porter, déduit de ce qu'on a posé — jamais écrit en dur."""
    attendus = {champ: valeur for _, (_, champ, valeur) in REGLAGES_CAMPAGNE.items()}
    for nom, brut in (extra_env or {}).items():
        if nom == "MEMOIRE__FENETRE_CHANGEMENTS_JOURS":
            attendus["fenetre_changements_jours"] = int(brut)
        elif nom == "MEMOIRE__CHANGEMENTS_MAX":
            attendus["changements_max"] = int(brut)
        elif nom == "MEMOIRE__IMPORTANCE_CHOC":
            attendus["seuil_choc"] = float(brut)
        elif nom == "MEMOIRE__MODE_FENETRE_CHANGEMENTS":
            attendus["mode_fenetre_changements"] = brut
        elif nom == "MEMOIRE__SEUIL_SERVICE_CHANGEMENT":
            attendus["seuil_service_changement"] = float(brut)
        elif nom == "MEMOIRE__PLANCHER_CHANGEMENT_JOURS":
            attendus["plancher_changement_jours"] = float(brut)
        elif nom == "MEMOIRE__PLAFOND_CHANGEMENT_JOURS":
            attendus["plafond_changement_jours"] = float(brut)
        elif nom == "MEMOIRE__RETARD_SATURATION":
            attendus["retard_saturation"] = brut
        elif nom == "MEMOIRE__RETARD_GRAVITE_MAX":
            attendus["retard_gravite_max"] = float(brut)
        elif nom == "MEMOIRE__RETARD_REF_S":
            attendus["retard_ref_s"] = int(brut)
        elif nom == "MEMOIRE__PARTAGE_FOYER_ENABLED":
            attendus["partage_foyer"] = str(brut).strip().lower() in ("1", "true", "yes", "on")
        elif nom == "WORLD__WORKER_CONCURRENCY":
            attendus["taches_en_vol"] = int(brut)
        elif nom == "REJEU_AB":
            # Un conteneur qui ne l'a pas reçu paierait tout le témoin sans le dire.
            attendus["rejeu_ab"] = brut
    return attendus


def archive_du_run() -> Path | None:
    """Le répertoire où le run vient RÉELLEMENT d'écrire.

    ⚠ `WORKDIR` n'est lu par personne : le contrôleur crée toujours
    `experiments/archive/<AAAA-MM-JJ>_<HH_MM>` et y fait pointer `experiments/current`. Le
    `workdir` par branche de ce script est donc une commodité de bookkeeping, pas une
    destination. Le § 10.7 du ticket 077 le dit autrement : « `experiments/current` ne prouve
    rien » — on le résout ici, tout de suite après le run, tant qu'il pointe encore au bon
    endroit, et on l'écrit dans le manifeste de campagne.
    """
    lien = Path("experiments/current")
    if not lien.exists():
        return None
    try:
        return lien.resolve()
    except OSError:
        return None


def consigner_au_manifeste(base_dir: Path, persona_id: str, branch: str, archive: Path | None) -> None:
    """Le manifeste de campagne : quel bras a produit quel répertoire d'archive."""
    manifeste = base_dir / "manifeste.json"
    entrees = []
    if manifeste.is_file():
        try:
            entrees = json.loads(manifeste.read_text(encoding="utf-8"))
        except ValueError:
            entrees = []
    entrees.append(
        {
            "persona": str(persona_id),
            "branche": branch,
            "archive": str(archive) if archive else None,
            "identite": str(archive / "identite_run.json") if archive else None,
            "horodatage": datetime.now().isoformat(timespec="seconds"),
        }
    )
    manifeste.parent.mkdir(parents=True, exist_ok=True)
    manifeste.write_text(json.dumps(entrees, ensure_ascii=False, indent=2), encoding="utf-8")
    if archive is None:
        logger.error(
            f"[ALARME] [{persona_id}_{branch}] répertoire d'archive introuvable après le run : "
            f"le bras ne pourra pas être apparié à son identité."
        )
    else:
        logger.info(f"[{persona_id}_{branch}] archive du bras : {archive}")


def generer_analyses_post_run(workdir: Path, persona_id: str, branch: str) -> None:
    """Génère les graphiques et le rapport dynamique après la fin du run."""
    moves_csv = workdir / "moves.csv"
    if not moves_csv.is_file():
        logger.warning(f"[{persona_id}_{branch}] moves.csv introuvable dans {workdir} — analyse ignorée.")
        return

    reports_dir = workdir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "scripts/analysis/modal_variation_rate.py",
        str(moves_csv),
        "-o",
        str(reports_dir),
    ]
    logger.info(f"[{persona_id}_{branch}] Génération du rapport de transition modale dans {reports_dir}...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        logger.info(f"[{persona_id}_{branch}] Graphiques et rapport SVG générés avec succès.")
    else:
        logger.error(f"[{persona_id}_{branch}] Erreur lors de l'analyse : {res.stderr}")

    plot_script = Path("scripts/analysis/plot_agent_itineraries.py")
    if plot_script.is_file():
        cmd_html = [
            sys.executable,
            str(plot_script),
            "--moves-csv",
            str(moves_csv),
            "--html-report",
            str(reports_dir / "itineraires.html"),
            "--export-svg",
            "--output-dir",
            str(reports_dir / "svg"),
        ]
        logger.info(f"[{persona_id}_{branch}] Génération du visualiseur interactif HTML et des SVG...")
        subprocess.run(cmd_html, capture_output=True, text=True)

    # Rapport de mémoire cognitive
    cmd_mem = [
        sys.executable,
        "-m",
        "scripts.analysis.memoire.rapport",
        str(workdir if (workdir / "agent_memory_events.csv").is_file() else archive_du_run() or workdir),
        "-o",
        str(reports_dir / "rapport_memoire.html"),
    ]
    subprocess.run(cmd_mem, capture_output=True, text=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Orchestrateur séquentiel de cohorte A/B pour le rejeu haute fidélité (Ticket 077)."
    )
    parser.add_argument(
        "--personas",
        nargs="+",
        default=["899549"],
        help="Identifiants des personas à tester (défaut : 899549 Corinne ; ou 'all' pour les 10)",
    )
    parser.add_argument(
        "--branch",
        choices=["both", "treated", "control"],
        default="both",
        help="Branche à exécuter : treated (choc), control (témoin), ou both (A/B fork)",
    )
    parser.add_argument(
        "--experiment-id",
        default=None,
        help="Identifiant de la campagne (défaut : exp_cohort_YYYY-MM-DD_HH_MM)",
    )
    parser.add_argument(
        "--force-fresh",
        action="store_true",
        help="Force un redémarrage à neuf en ignorant les points de reprise existants",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche le plan d'exécution sans lancer les simulations",
    )
    parser.add_argument(
        "--evenement",
        default=CHOC_REFERENCE,
        help=f"Événement joué par le bras traité, par son nom de fichier sans extension "
             f"(défaut : {CHOC_REFERENCE}). Cherché dans config/evenements/ puis config/chocs/. "
             f"Le bras témoin n'en reçoit aucun, quel que soit ce réglage.",
    )
    parser.add_argument(
        "--horizon-jours",
        type=int,
        default=HORIZON_JOURS_DEFAUT,
        help=f"Jours calendaires simulés (défaut : {HORIZON_JOURS_DEFAUT}). Écrit dans "
             f"sim_params.yaml ; le délai de garde du bras en dépend.",
    )
    parser.add_argument(
        "--arret-sur-extinction",
        action="store_true",
        help="Coupe le bras une fois le souvenir DÉCLARÉ sorti du bloc « ce qui a changé "
             "récemment » depuis --jours-apres-extinction jours vécus. Le bras est alors plus "
             "court que son témoin : l'analyse doit tronquer les deux au jour écrit dans "
             "arret_sur_extinction.json. Sans ce drapeau, le run va jusqu'à son horizon.",
    )
    parser.add_argument(
        "--jours-apres-extinction",
        type=int,
        default=JOURS_APRES_EXTINCTION,
        help=f"Jours VÉCUS observés après l'extinction avant de couper "
             f"(défaut : {JOURS_APRES_EXTINCTION})",
    )

    args = parser.parse_args()

    # Résolution des personas
    if args.personas == ["all"]:
        personas = COHORTE_10_PERSONAS
    else:
        personas = args.personas

    exp_id = args.experiment_id or f"exp_cohort_{datetime.now().strftime('%Y-%m-%d_%H_%M')}"
    base_dir = Path("experiments/runs") / exp_id

    branches = ["treated", "control"] if args.branch == "both" else [args.branch]

    print("=" * 75)
    print(f"ORCHESTRATEUR SÉQUENTIEL DE COHORTE — REJEU TICKET 077")
    print("=" * 75)
    print(f"Campagne        : {exp_id}")
    print(f"Personas ({len(personas)}) : {', '.join(personas)}")
    print(f"Branches        : {', '.join(branches)}")
    print(f"Dossier racine  : {base_dir}")
    print(f"Événement       : {args.evenement} (bras traité seul)")
    print(f"Horizon         : {args.horizon_jours} jours calendaires")
    _jalons = os.getenv("EXPERIMENT_SURVEY_DAYS") or "12,17,29,40 (défaut)"
    print(f"Jalons enquêtes : {_jalons} — 21h00, étanchéité mémoire absolue")
    if args.arret_sur_extinction:
        print(f"Arrêt anticipé  : ARMÉ — {args.jours_apres_extinction} jours vécus après "
              f"l'extinction du souvenir déclaré (bras plus court que son témoin)")
    else:
        print("Arrêt anticipé  : désarmé — chaque bras va jusqu'à son horizon")
    print("=" * 75)

    for i, pid in enumerate(personas, 1):
        for br in branches:
            print(f"\n>>> [{i}/{len(personas)}] Traitement du persona {pid} — Branche : {br.upper()}")
            workdir = base_dir / f"{pid}_{br}"
            is_resume = preparer_workdir(
                workdir, pid, br, force_fresh=args.force_fresh, horizon_jours=args.horizon_jours
            )

            ret = executer_run_persona(
                persona_id=pid,
                branch=br,
                workdir=workdir,
                is_resume=is_resume,
                dry_run=args.dry_run,
                arret_extinction=args.arret_sur_extinction,
                jours_apres_extinction=args.jours_apres_extinction,
                evenement=args.evenement,
                horizon_jours=args.horizon_jours,
            )

            if not args.dry_run and ret == 0:
                archive = archive_du_run()
                consigner_au_manifeste(base_dir, pid, br, archive)
                generer_analyses_post_run(archive or workdir, pid, br)
                if archive and archive.is_dir() and workdir.resolve() != archive.resolve():
                    # Tout ce que l'orchestrateur mémoire relit : sans `evenements.jsonl`, son
                    # rapprochement du ticket 108 comptait zéro injection produite sur un bras
                    # où l'article avait bien été lu.
                    for fname in [
                        "moves.csv", "decisions_rejeu.jsonl", "identite_run.json",
                        "evenements.jsonl", "agent_memory_events.jsonl",
                        "temoin_souvenir.jsonl", "affinites_declarees.csv", "app.log",
                    ]:
                        if (archive / fname).is_file():
                            shutil.copy2(archive / fname, workdir / fname)
                    if (archive / "reports").is_dir():
                        shutil.copytree(archive / "reports", workdir / "reports", dirs_exist_ok=True)
                    logger.info(f"[{pid}_{br}] Livrables copiés de {archive.name} vers {workdir}")
            elif ret != 0:
                # On s'ARRÊTE. Enchaîner sur le bras suivant après un échec, c'est ce qui a
                # produit le 2026-09-19 un « témoin » qui avait tué le bras traité.
                logger.error(
                    f"[ALARME] Bras {pid}_{br} en échec (code {ret}) — CAMPAGNE INTERROMPUE. "
                    f"Les bras suivants ne sont pas lancés : un bras qui échoue laisse la pile "
                    f"dans un état dont le suivant hériterait."
                )
                sys.exit(ret)

    print("\n" + "=" * 75)
    print("TOUTES LES ITÉRATIONS DE LA COHORTE SONT TERMINÉES.")
    print("=" * 75)


if __name__ == "__main__":
    main()
