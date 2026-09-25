#!/usr/bin/env python3
"""Orchestrateur contrefactuel A/B pour les expériences mémoire — Ticket 109.

DÉCISION D3 : Les deux runs (traité puis témoin apparié) sont exécutés consécutivement.
L'expérience n'est marquée comme « terminee » que si les deux ont été joués avec succès.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "services" / "llm-agents"))
from experiences import memoire, rejeu_ab

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("orchestrateur_memoire")


# Code rendu par `run_sequential_cohort.py` pour un bras suspendu par le garde-fou (ticket 105).
CODE_BRAS_SUSPENDU = 7


def _foyers_avec_relais(evenement: str) -> int:
    """Nombre de foyers exposés d'une déclaration qui porte un relais (ticket 111), sinon 0."""
    if not evenement or evenement == "0":
        return 0
    chemin = memoire.DOSSIER_EVENEMENTS / f"{evenement}.yaml"
    if not chemin.is_file():
        return 0
    try:
        import yaml

        data = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 — une estimation ne fait pas tomber le lancement
        return 0
    if not data.get("relais"):
        return 0
    return len((data.get("exposition") or {}).get("foyers") or [])


def estimer_cout(config: dict[str, Any]) -> dict[str, Any]:
    """Estime le volume d'appels LLM pour les deux bras consécutifs."""
    horizon = int(config.get("horizon_jours", 42))
    pop = str(config.get("population", "899549"))
    # L'effectif LU, pas deviné : un jeu de vingt foyers comptait jusqu'ici pour un persona, et
    # l'estimation sous-évaluait la campagne d'un facteur vingt.
    nb_personas = memoire.decrire_population(pop)["agents"]

    appels_decision = nb_personas * horizon * 4
    appels_stm = nb_personas * horizon * 1
    appels_ltm = nb_personas * (horizon // 1)
    appels_enquetes = nb_personas * horizon * 5
    appels_jugement = nb_personas * 2  # ~2 expositions max
    # Ticket 111 — un appel de relais par foyer exposé, et un jugement par membre informé
    # (au plus les autres membres du foyer ; compté large, un par agent non lecteur).
    foyers_relais = _foyers_avec_relais(str(config.get("evenement", "")))
    appels_relais = foyers_relais
    if foyers_relais:
        appels_jugement += nb_personas

    par_bras = {
        "itinary_multi_agent": appels_decision,
        "stm_reflection": appels_stm,
        "ltm_self_reflection": appels_ltm,
        "enquete_affinite": appels_enquetes,
        "evenement_jugement": appels_jugement,
        "evenement_relais": appels_relais,
    }
    total_bras = sum(par_bras.values())
    total_ab = total_bras * 2  # Facteur 2 pour A/B (traité + témoin)

    return {
        "nb_personas": nb_personas,
        "horizon_jours": horizon,
        "appels_par_bras": par_bras,
        "total_requetes_par_bras": total_bras,
        "total_requetes_experience_ab": total_ab,
        "estimation_jetons": total_ab * 1500,  # ~1 500 jetons par appel en moyenne
    }


RACINE_REJEU = REPO_ROOT / "experiments" / "rejeu_ab"


def espace_rejeu(nom_exp: str, config: dict[str, Any]) -> str | None:
    """L'espace de rejeu de l'expérience : son nom, si elle déclare `rejeu_ab: true`."""
    return nom_exp if config.get("rejeu_ab") else None


def mettre_de_cote_magasin(nom_exp: str) -> Path | None:
    """Un traité qui repart de zéro ne doit pas rejouer une tentative précédente.

    Le magasin d'une tentative avortée est RENOMMÉ, jamais effacé : ses réponses ont été payées
    et disent ce que le modèle a répondu. Rien à faire s'il est absent ou vide.
    """
    magasin = RACINE_REJEU / nom_exp
    if not magasin.is_dir() or not any(magasin.glob("*.json")):
        return None
    cible = RACINE_REJEU / f"{nom_exp}.mis_de_cote_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    magasin.rename(cible)
    logger.warning(
        f"[{nom_exp}] magasin de rejeu d'une tentative précédente mis de côté → {cible.name} : "
        f"le traité repart de zéro, il ne rejoue pas l'ancien."
    )
    return cible


def archive_du_bras(nom_exp: str, branche: str) -> Path | None:
    """Le répertoire d'archive qu'a produit le bras, d'après le manifeste de la cohorte."""
    manifeste = REPO_ROOT / "experiments" / "runs" / f"{nom_exp}_{branche}" / "manifeste.json"
    try:
        entrees = json.loads(manifeste.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for e in reversed(entrees):
        if e.get("branche") == branche and e.get("archive"):
            return Path(e["archive"])
    return None


def controler_rejeu(nom_exp: str, racine_bras: Path) -> dict[str, Any] | None:
    """Après le témoin : chaque appel d'avant l'événement doit avoir été servi par rejeu."""
    archive = archive_du_bras(nom_exp, "control")
    journal = archive / "llm_exchanges.jsonl" if archive else None
    if journal is None or not journal.is_file():
        logger.error(
            f"[ALARME] [{nom_exp}] rejeu : journal des échanges du témoin introuvable "
            f"({journal or 'aucune archive au manifeste'}) — le rejeu ne peut pas être vérifié."
        )
        return None
    date_evt = rejeu_ab.date_premiere_injection(racine_bras / "traite" / "evenements.jsonl")
    resultat = rejeu_ab.bilan(rejeu_ab.lire_echanges(journal), date_evt)
    resultat["consignes"] = len(list((RACINE_REJEU / nom_exp).glob("*.json")))
    resultat["archive_temoin"] = str(archive)
    if resultat["payes_avant_evenement"]:
        logger.error(
            f"[ALARME] [{nom_exp}] rejeu : {resultat['payes_avant_evenement']} appel(s) du témoin "
            f"PAYÉS avant l'événement ({date_evt}) — les bras ont divergé pour une autre raison "
            f"que lui. Premiers : {resultat['premiers_payes_avant'][:3]}"
        )
    else:
        logger.info(
            f"[{nom_exp}] rejeu conforme : témoin servi à {resultat['servis']}/"
            f"{resultat['servis'] + resultat['payes']} par rejeu, aucun appel payé avant "
            f"l'événement ({date_evt}) ; {resultat['consignes']} réponses consignées."
        )
    return resultat


def executer_bras(
    nom_exp: str,
    branche: str,
    config: dict[str, Any],
    workdir_cible: Path,
    dry_run: bool = False,
) -> int:
    """Exécute un bras (treated ou control) via run_sequential_cohort.py."""
    logger.info(f"[{nom_exp}] >>> Démarrage du Bras : {branche.upper()}")
    workdir_cible.mkdir(parents=True, exist_ok=True)

    pop = str(config.get("population", "899549"))
    personas_arg = ["all"] if pop == "cohorte_10" else [pop]
    evenement_arg = str(config.get("evenement", "c6_voiture_suspecte")) if branche == "treated" else "0"

    # Construction de la table de routage instances_admises
    routage = memoire.resoudre_instances_admises(
        config.get("modeles", {}), adaptateur=config.get("adaptateur") or None
    )
    # Un modèle déclaré qu'aucune instance ne sert — ou que le filtre de fournisseur a écarté —
    # partirait sur le défaut du conteneur, c'est-à-dire sur un autre modèle, sans un mot.
    orphelins = [
        f"{cat} → {mod}" for cat, mod in (config.get("modeles") or {}).items()
        if mod and mod != "aucun" and not routage.get(cat)
    ]
    if orphelins:
        logger.error(
            f"[ALARME] [{nom_exp}_{branche}] aucune instance "
            f"{'« ' + config['adaptateur'] + ' » ' if config.get('adaptateur') else ''}ne sert : "
            f"{', '.join(orphelins)} — bras refusé."
        )
        return 2
    logger.info(f"[{nom_exp}_{branche}] routage des instances : {json.dumps(routage)}")

    env = dict(os.environ)
    if routage:
        env["INSTANCES_ADMISES"] = json.dumps(routage)
    # Rejeu à prompt exact : le MÊME espace pour les deux bras, sinon le témoin ne voit rien.
    espace = espace_rejeu(nom_exp, config)
    env["REJEU_AB"] = espace or ""
    if espace:
        logger.info(f"[{nom_exp}_{branche}] rejeu à prompt exact : espace {espace}")
    if "memoire_importance_choc" in config:
        env["MEMOIRE__IMPORTANCE_CHOC"] = str(config["memoire_importance_choc"])
    if "stm_reflection_min_entries" in config:
        env["STM_REFLECTION_MIN_ENTRIES"] = str(config["stm_reflection_min_entries"])
    if "graine_tirage" in config:
        env["AGENT__MODE_CHOICE_SEED"] = str(config["graine_tirage"])
    # Toujours posé, vrai ou faux : le lanceur le compare alors à `identite_run.json`, et un
    # conteneur qui ne l'aurait pas reçu arrête le bras au lieu de tourner sans partage.
    env["MEMOIRE__PARTAGE_FOYER_ENABLED"] = "true" if config.get("partage_foyer") else "false"
    # Micro-batching au maximum : autant de tâches en vol que d'agents, pour qu'une vague de
    # départs parte en UN lot au lieu de lots de 8. Plancher 8 = le défaut historique.
    env["WORLD__WORKER_CONCURRENCY"] = str(
        max(8, int(memoire.decrire_population(str(config.get("population", "899549")))["agents"] or 0))
    )

    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "experiment" / "run_sequential_cohort.py"),
        "--personas",
        *personas_arg,
        "--branch",
        branche,
        "--evenement",
        evenement_arg,
        "--experiment-id",
        f"{nom_exp}_{branche}",
        "--horizon-jours",
        str(int(config.get("horizon_jours", 42))),
    ]

    if config.get("arret_sur_extinction"):
        cmd.append("--arret-sur-extinction")
        cmd.extend(["--jours-apres-extinction", str(config.get("jours_apres_extinction", 5))])

    if dry_run:
        cmd.append("--dry-run")
        logger.info(f"[{nom_exp}_{branche}] [DRY-RUN] Commande : {' '.join(cmd)}")
        # Création de traces synthétiques pour valider le pipeline
        (workdir_cible / "moves.csv").write_text("jour,mode,person_id\n1,car,899549\n", encoding="utf-8")
        (workdir_cible / "evenements.jsonl").write_text(
            json.dumps({"evenement_id": evenement_arg, "jour_run": 15, "person_id": pop}) + "\n"
            if branche == "treated" else ""
        )
        (workdir_cible / "agent_memory_events.jsonl").write_text('{"event": "test"}\n')
        (workdir_cible / "identite_run.json").write_text(json.dumps({"branche": branche, "dry_run": True}))
        (workdir_cible / "temoin_souvenir.jsonl").write_text(
            json.dumps({"evenement_id": evenement_arg, "retrouve": True, "branche": branche}) + "\n"
            if branche == "treated" else ""
        )
        return 0

    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env)
    if proc.returncode != 0:
        logger.error(f"[{nom_exp}_{branche}] Échec de run_sequential_cohort (code {proc.returncode})")
        return proc.returncode

    # Rapatriement des données depuis experiments/runs/ vers le workdir cible
    dossier_source = REPO_ROOT / "experiments" / "runs" / f"{nom_exp}_{branche}"
    if dossier_source.is_dir():
        for sous in dossier_source.iterdir():
            if sous.is_dir():
                for f in ["moves.csv", "evenements.jsonl", "agent_memory_events.jsonl", "identite_run.json", "temoin_souvenir.jsonl", "app.log"]:
                    source_f = sous / f
                    if source_f.is_file():
                        shutil.copy2(source_f, workdir_cible / f)
                if (sous / "reports").is_dir():
                    shutil.copytree(sous / "reports", workdir_cible / "reports", dirs_exist_ok=True)
    return 0


def rapprochement_injections(config: dict[str, Any], workdir_traite: Path) -> dict[str, Any]:
    """Contrôle Ticket 108 : rapprochement des injections déclarées vs produites."""
    evenement_id = config.get("evenement", "")
    dossier_evt = REPO_ROOT / "services" / "llm-agents" / "config" / "evenements"
    # L'événement JOUÉ est le dérivé que la cohorte a écrit pour cette population (même nom que
    # `nom_choc_derive`) : c'est lui qui porte les foyers réellement exposés. La déclaration de
    # base peut viser une autre population.
    derive = dossier_evt / f"{evenement_id}__{config.get('population', '')}.yaml"
    fichier_evt = derive if derive.is_file() else dossier_evt / f"{evenement_id}.yaml"
    if not fichier_evt.is_file():
        fichier_evt = REPO_ROOT / "services" / "llm-agents" / "config" / "chocs" / f"{evenement_id}.yaml"

    declarees = 0
    if fichier_evt.is_file():
        try:
            raw = yaml.safe_load(fichier_evt.read_text(encoding="utf-8")) or {}
            expo = raw.get("exposition") or {}
            if "jours" in raw and isinstance(raw["jours"], list):
                declarees = len(raw["jours"])
            elif "calendrier" in raw:
                # Un article se lit une fois par LECTEUR : un par foyer exposé (règle `foyers`),
                # un par agent désigné (règle `agents`). Compter 1 faisait passer six lectures
                # attendues pour une seule.
                if expo.get("regle") == "foyers" and expo.get("lecteurs"):
                    # Lecteurs désignés : chacun lit une fois, quel que soit son foyer.
                    declarees = len(expo.get("lecteurs") or [])
                elif expo.get("regle") == "foyers":
                    declarees = len(expo.get("foyers") or []) * int(expo.get("lecteurs_par_foyer") or 1)
                elif expo.get("regle") == "agents":
                    declarees = len(expo.get("agents") or [])
                else:
                    declarees = 1
        except (OSError, yaml.YAMLError) as exc:
            logger.error(f"[ALARME] [108] déclaration {fichier_evt} illisible ({exc!r})")

    produites = 0
    evt_jsonl = workdir_traite / "evenements.jsonl"
    if evt_jsonl.is_file():
        try:
            lignes = [json.loads(l) for l in evt_jsonl.read_text().splitlines() if l.strip()]
            # Ticket 111 : un membre informé par le lecteur a sa ligne (`origine: entendu`),
            # mais ce n'est pas une lecture. La compter masquerait une lecture manquante :
            # dix lectures sur vingt et dix informés passeraient pour « conforme ».
            produites = sum(1 for l in lignes if l.get("origine") != "entendu")
        except Exception:
            pass

    return {
        "evenement_id": evenement_id,
        "declarees": declarees,
        "produites": produites,
        "manquantes": max(0, declarees - produites),
        "conforme": produites >= declarees and declarees > 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Orchestrateur d'expérience mémoire A/B (Ticket 109).")
    parser.add_argument("--experience", required=True, help="Nom de l'expérience mémoire")
    parser.add_argument("--estimer", action="store_true", help="Estime le coût sans rien lancer")
    parser.add_argument("--dry-run", action="store_true", help="Validation à blanc sans simulation GAMA")
    parser.add_argument("--branche", choices=["both", "treated", "control"], default="both", help="Branches à jouer")

    args = parser.parse_args()
    nom_exp = args.experience
    exp_dir = memoire.DOSSIER_MEMOIRE / nom_exp
    cfg_path = exp_dir / "experience_memoire.yaml"

    if not cfg_path.is_file():
        logger.error(f"Fichier de configuration introuvable : {cfg_path}")
        sys.exit(1)

    config = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    # Le partage dans le foyer n'a d'objet que s'il y a des foyers à plusieurs. Activé sur un
    # persona seul, il tournerait sans rien partager et le run se lirait comme « rien ne se
    # transmet » — une absence de mesure qui passerait pour un résultat.
    pop = str(config.get("population", ""))
    if config.get("partage_foyer") and memoire.decrire_population(pop)["foyers_partages"] == 0:
        logger.error(
            f"[ALARME] [{nom_exp}] partage_foyer activé sur « {pop} », qui ne compte aucun foyer "
            f"d'au moins deux membres — expérience refusée."
        )
        sys.exit(2)

    if args.estimer:
        bilan = estimer_cout(config)
        print("\n" + "=" * 60)
        print(f"🧮 ESTIMATION DU COÛT — EXPÉRIENCE MÉMOIRE {nom_exp}")
        print("=" * 60)
        print(f"Population : {bilan['nb_personas']} persona(s) | Horizon : {bilan['horizon_jours']} jours")
        print("\nRépartition par fonction cognitive (par bras) :")
        for cat, count in bilan["appels_par_bras"].items():
            print(f"  - {memoire.LIBELLES_CATEGORIES.get(cat, cat):<35} : {count:>5} requêtes")
        print("-" * 60)
        print(f"Total par bras               : {bilan['total_requetes_par_bras']:>6} requêtes")
        print(f"Total Campagne A/B (x2)      : {bilan['total_requetes_experience_ab']:>6} requêtes")
        print(f"Jetons estimés (ordre de grandeur) : ~{bilan['estimation_jetons']:,} tokens")
        print("=" * 60 + "\n")
        return

    # État : on REPART de celui qui existe. Une relance après une suspension ne doit ni rejouer
    # un bras déjà abouti, ni effacer la trace de ce qui s'est passé.
    etat_path = exp_dir / "etat.json"
    try:
        precedent = json.loads(etat_path.read_text(encoding="utf-8")) if etat_path.is_file() else {}
    except (OSError, ValueError):
        precedent = {}
    maintenant = datetime.now(timezone.utc).isoformat()
    etat_data = {
        **precedent,
        "nom": nom_exp,
        "etat": "en_cours",
        "debut": precedent.get("debut") or maintenant,
        "traite": precedent.get("traite") or {"etat": "en_attente"},
        "temoin": precedent.get("temoin") or {"etat": "en_attente"},
    }

    # Un essai à blanc ne touche ni à l'état ni aux dossiers des bras. Le 2026-09-24, celui du
    # c6 avait marqué l'expérience « terminee » en 50 ms et déposé un faux `moves.csv` dans
    # `traite/` et `temoin/` : le registre la montrait aboutie, une vraie relance aurait sauté
    # les deux bras, et un archivage pour le papier aurait emporté des traces synthétiques.
    def ecrire_etat() -> None:
        if not args.dry_run:
            etat_path.write_text(json.dumps(etat_data, indent=2), encoding="utf-8")

    racine_bras = exp_dir / "essai_a_blanc" if args.dry_run else exp_dir
    ecrire_etat()

    branches = ["treated", "control"] if args.branche == "both" else [args.branche]

    for br in branches:
        cle = "traite" if br == "treated" else "temoin"
        cible = racine_bras / cle
        if etat_data[cle].get("etat") == "ok" and not args.dry_run:
            logger.info(f"[{nom_exp}] bras {br} déjà abouti ({etat_data[cle].get('fin')}) — non rejoué.")
            continue
        reprise = etat_data[cle].get("etat") == "suspendu"
        etat_data["branche_active"] = br
        etat_data[cle]["etat"] = "en_cours"
        etat_data[cle].setdefault("debut", datetime.now(timezone.utc).isoformat())
        ecrire_etat()
        if reprise:
            logger.info(f"[{nom_exp}] reprise du bras {br}, suspendu le {etat_data[cle].get('suspendu_le')}.")
        elif br == "treated" and espace_rejeu(nom_exp, config) and not args.dry_run:
            mettre_de_cote_magasin(nom_exp)

        ret = executer_bras(nom_exp, br, config, cible, dry_run=args.dry_run)
        if ret == CODE_BRAS_SUSPENDU:
            # Option A (2026-09-24) : ni succès ni échec — le bras se reprend à la relance, et
            # le suivant n'est PAS lancé sur un quota épuisé.
            etat_data["etat"] = "suspendue"
            etat_data[cle]["etat"] = "suspendu"
            etat_data[cle]["suspendu_le"] = datetime.now(timezone.utc).isoformat()
            ecrire_etat()
            logger.error(
                f"[ALARME] [{nom_exp}] bras {br} SUSPENDU par le garde-fou (quota ou replis) — "
                f"le bras suivant n'est pas lancé. Relancer la même expérience le reprendra."
            )
            sys.exit(ret)
        if ret != 0:
            logger.error(f"[ALARME] Échec sur le bras {br} (code {ret}) — arrêt de la campagne.")
            etat_data["etat"] = "echec"
            etat_data["traite" if br == "treated" else "temoin"]["etat"] = "echec"
            ecrire_etat()
            sys.exit(ret)

        etat_data["traite" if br == "treated" else "temoin"]["etat"] = "ok"
        etat_data["traite" if br == "treated" else "temoin"]["fin"] = datetime.now(timezone.utc).isoformat()
        ecrire_etat()

    # Synthèse post-run et contrôles qualité
    rappr = rapprochement_injections(config, racine_bras / "traite")
    if "treated" in branches and not args.dry_run and not rappr["conforme"]:
        logger.error(
            f"[ALARME] [108] [{nom_exp}] injections produites {rappr['produites']} / déclarées "
            f"{rappr['declarees']} — le bras traité n'a pas reçu l'événement qu'il déclare : "
            f"ne pas le lire comme une mesure de son effet."
        )
    # D3 : terminée seulement si LES DEUX bras ont tourné. Un bras joué seul (debug, reprise)
    # laisse l'expérience « partielle », pour qu'elle ne passe jamais pour une mesure A/B.
    # On lit l'état des bras, pas la liste de cette invocation : un témoin joué seul après un
    # traité abouti la veille termine bien l'expérience.
    traite_ok = etat_data["traite"].get("etat") == "ok"
    temoin_ok = etat_data["temoin"].get("etat") == "ok"
    if traite_ok and temoin_ok:
        etat_data["etat"] = "terminee"
    else:
        etat_data["etat"] = "traite_ok" if traite_ok else "partielle"
    etat_data["fin"] = datetime.now(timezone.utc).isoformat()
    etat_data["rapprochement_ticket108"] = rappr
    if traite_ok and temoin_ok and espace_rejeu(nom_exp, config) and not args.dry_run:
        etat_data["rejeu_ab"] = controler_rejeu(nom_exp, racine_bras)
    ecrire_etat()

    logger.info("=" * 60)
    if args.dry_run:
        logger.info(
            f"✅ ESSAI À BLANC de {nom_exp} réussi ({', '.join(branches)}) — aucune simulation, "
            f"aucun appel ; état de l'expérience INCHANGÉ, traces synthétiques dans {racine_bras}."
        )
    elif len(branches) == 2:
        logger.info(f"✅ CAMPAGNE MÉMOIRE {nom_exp} TERMINÉE AVEC SUCCÈS (LES 2 BRAS ONT TOURNÉ).")
    else:
        logger.info(
            f"✅ Bras {branches[0]} de {nom_exp} terminé — expérience PARTIELLE "
            f"(l'autre bras n'a pas été joué)."
        )
    logger.info(f"Rapprochement injections (Ticket 108) : {rappr['produites']}/{rappr['declarees']} produites.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
