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
PAS_DE_SONDAGE_S = 30
PAS_DE_JOURNAL_S = 300
# Jours VÉCUS observés après l'extinction du souvenir déclaré avant de couper le run. Sept :
# une semaine simulée complète, assez pour voir si le comportement revient à celui d'avant, et
# c'est la durée déjà retenue par `arret_sur_extinction.py` en ligne de commande.
JOURS_APRES_EXTINCTION = 7

CHOC_REFERENCE = "c6_voiture_suspecte"
CHOCS_DIR = Path("services/llm-agents/config/chocs")


def nom_choc_derive(persona_id: str) -> str:
    """Le nom du choc dérivé pour ce persona. Pur : ne touche à rien."""
    return f"{CHOC_REFERENCE}__{persona_id}"


def choc_pour_persona(persona_id: str) -> str:
    """Écrit le choc de référence restreint à ce persona, et rend son nom pour `make run CHOC=`.

    Le fichier dérivé porte le même texte, la même cadence et les mêmes jours que la référence.
    Seule l'exposition change : un run de cohorte ne porte qu'un habitant, et désigner les autres
    ne ferait qu'ajouter des identifiants inertes dans la déclaration.
    """
    import yaml

    source = CHOCS_DIR / f"{CHOC_REFERENCE}.yaml"
    declaration = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    declaration.setdefault("exposition", {})["agents"] = [str(persona_id)]
    nom = nom_choc_derive(persona_id)
    cible = CHOCS_DIR / f"{nom}.yaml"
    cible.write_text(
        f"# ENGENDRÉ par scripts/experiment/run_sequential_cohort.py — ne pas éditer.\n"
        f"# Source : {source.name}. Seule l'exposition est restreinte au persona {persona_id}.\n"
        + yaml.safe_dump(declaration, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    logger.info(f"[{persona_id}] choc dérivé de {source.name} → {cible.name}")
    return nom


def verifier_reprise_possible(workdir: Path) -> bool:
    """Vérifie si un point de reprise à chaud intègre existe dans le workdir."""
    if not workdir.is_dir():
        return False
    checkpoints_dir = workdir / "checkpoints"
    if checkpoints_dir.is_dir():
        points = list(checkpoints_dir.glob("reprise_*.json")) or list(checkpoints_dir.glob("population_*_checkpoint_*.json"))
        if points:
            return True
    if (workdir / "moves.csv").is_file() and (workdir / "decisions_rejeu.jsonl").is_file():
        return True
    return False


def preparer_workdir(workdir: Path, persona_id: str, branch: str, force_fresh: bool = False) -> bool:
    """Initialise le dossier d'exécution isolé pour ce persona et cette branche."""
    workdir.mkdir(parents=True, exist_ok=True)
    # Le choc se déclare à `make run` (CHOC=…), pas en posant un fichier dans le workdir : le
    # contrôleur y écrit SA copie de la déclaration en fin de course, il ne l'y lit jamais.

    # 1. Configurer sim_params.yaml pour population_size = 1
    sim_params_path = Path("services/GAMA/CityTransport/config/sim_params.yaml")
    if sim_params_path.is_file():
        import re
        text = sim_params_path.read_text(encoding="utf-8")
        text = re.sub(r"^population_size:\s*\d+", "population_size: 1", text, flags=re.MULTILINE)
        text = re.sub(r"^simulation_max_days:\s*\d+", "simulation_max_days: 42", text, flags=re.MULTILINE)
        sim_params_path.write_text(text, encoding="utf-8")

    # 2. Configurer config.yaml pour pointer sur le fichier population_1_{persona_id}
    config_yaml_path = Path("services/llm-agents/config/config.yaml")
    if config_yaml_path.is_file():
        import re
        c_text = config_yaml_path.read_text(encoding="utf-8")
        c_text = re.sub(
            r"population_file:\s*/data/eqasim-output/.*",
            f"population_file: /data/eqasim-output/population_1_{persona_id}/population.json",
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
) -> int:
    """Lance un run GAMA/Python de 30 jours ouvrés (42j calendaires) pour un persona donné."""
    env = os.environ.copy()
    env["WORKDIR"] = str(workdir.resolve())
    env["EXPERIMENT_SURVEY_ENABLED"] = "1"
    env["EXPERIMENT_HIBERNATE_ON_QUOTA"] = "1"
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
    env["INSTANCES_ADMISES"] = json.dumps(
        {
            "defaut": ["google_gemini31_key1", "google_gemini31_key2"],
            "itinary_multi_agent": ["google_gemini31_key1", "google_gemini31_key2"],
            "ltm_self_reflection": ["google_gemini31_key1", "google_gemini31_key2"],
            "stm_reflection": ["google_gemini35_key1", "google_gemini35_key2"],
            "enquete_affinite": ["google_gemini35_key1", "google_gemini35_key2"],
        }
    )
    env["DATA__POPULATION_SIZE"] = "1"

    if is_resume:
        env["CONT"] = "1"
        env["CONTINUE_RUN"] = "1"

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
        ]:
            if var in os.environ:
                extra_env[var] = os.environ[var]

    if extra_env:
        env.update(extra_env)

    # CHOC : c'est ICI que les deux branches se séparent. Sans lui, `make run` laisse la
    # déclaration de `config.yaml` en place et le témoin subit le choc du bras traité.
    # CACHE=0 : la clé du cache sémantique ne porte aucune durée, une décision prise avant le
    # choc pourrait être resservie pendant.
    choc = nom_choc_derive(persona_id) if branch == "treated" else "0"
    cmd = ["make", "run", "OFFLINE=1", "CACHE=0", f"CHOC={choc}"]
    if is_resume:
        cmd.append("CONT=1")

    logger.info(f"[{persona_id}_{branch}] Démarrage de la simulation (42 jours calendaires)...")
    logger.info(f"[{persona_id}_{branch}] Workdir : {workdir}")
    logger.info(f"[{persona_id}_{branch}] Reprise à chaud (CONT=1) : {is_resume}")
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
        choc_pour_persona(persona_id)


    # Exécution du processus
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
    archive = attendre_identite(controller_demarre_a())
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

    # 2. Attendre la VRAIE fin du run.
    if not attendre_fin_du_run(
        persona_id,
        branch,
        archive,
        arret_extinction=arret_extinction,
        jours_apres_extinction=jours_apres_extinction,
    ):
        return 6

    logger.info(f"[{persona_id}_{branch}] Bras terminé.")
    return 0


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
    """La dernière journée simulée atteinte, pour journaliser un avancement et non un silence."""
    if archive is None:
        return "?"
    log = archive / "app.log"
    if not log.is_file():
        return "?"
    try:
        lignes = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "?"
    for ligne in reversed(lignes[-4000:]):
        if "[sync] END sim_time=" in ligne:
            return ligne.split("sim_time=", 1)[1].split(" state_update", 1)[0].strip()
    return "?"


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
            logger.info(
                f"[{persona_id}_{branch}] en cours depuis {int(ecoule // 60)} min — "
                f"journée simulée : {derniere_journee_simulee(archive)}"
            )
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
    depuis: float | None = None, timeout_s: int = ATTENTE_IDENTITE_S
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
            is_resume = preparer_workdir(workdir, pid, br, force_fresh=args.force_fresh)

            ret = executer_run_persona(
                persona_id=pid,
                branch=br,
                workdir=workdir,
                is_resume=is_resume,
                dry_run=args.dry_run,
                arret_extinction=args.arret_sur_extinction,
                jours_apres_extinction=args.jours_apres_extinction,
            )

            if not args.dry_run and ret == 0:
                archive = archive_du_run()
                consigner_au_manifeste(base_dir, pid, br, archive)
                generer_analyses_post_run(archive or workdir, pid, br)
                if archive and archive.is_dir() and workdir.resolve() != archive.resolve():
                    for fname in ["moves.csv", "decisions_rejeu.jsonl", "identite_run.json"]:
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
