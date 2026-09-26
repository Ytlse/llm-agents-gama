"""Modèle de données, nommage canonique et persistance pour les expériences mémoire — Ticket 109.

DÉCISIONS DE L'AUTEUR (2026-09-24) :
  (D1) Onglet dédié dans le tableau de bord Streamlit : scripts/dashboard/memoire.py.
  (D2) 6 fonctions cognitives configurables (itinéraire, jugement, STM, LTM, enquêtes, relais au
  foyer — ticket 111)
       avec persistance des choix du formulaire d'une session à l'autre.
  (D3) Orchestration contrefactuelle A/B consécutive : bras traité (avec événement)
       puis bras témoin apparié (sans événement). L'expérience n'est terminée que si les deux
       sont joués.
  (D4) Nom canonique calculé depuis les paramètres (règle N1) sans champ libre.
  (D5) Sélection stricte sur le catalogue existant dans config/evenements/.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Racine du dépôt (ce fichier vit dans services/llm-agents/experiences/)
REPO_ROOT = Path(__file__).resolve().parents[3]
DOSSIER_MEMOIRE = (
    Path(os.getenv("EXPERIENCES_MEMOIRE_DIR"))
    if os.getenv("EXPERIENCES_MEMOIRE_DIR")
    else REPO_ROOT / "data" / "experiences" / "evenements_non_tabules"
)
DOSSIER_EVENEMENTS = REPO_ROOT / "services" / "llm-agents" / "config" / "evenements"
DOSSIER_CHOCS = REPO_ROOT / "services" / "llm-agents" / "config" / "chocs"
ETAT_FORMULAIRE_MEMOIRE = (
    REPO_ROOT / "experiments" / ".dashboard" / "formulaire_memoire.yaml"
)
PROVIDERS_YAML = REPO_ROOT / "config" / "llm_gateway" / "providers.yaml"

# Les fonctions cognitives exposées (D2) ; la sixième, `evenement_relais`, vient du ticket 111.
CATEGORIES_COGNITIVES = (
    "itinary_multi_agent",
    "evenement_jugement",
    "stm_reflection",
    "ltm_self_reflection",
    "enquete_affinite",
    "evenement_relais",
)

LIBELLES_CATEGORIES: dict[str, str] = {
    "itinary_multi_agent": "1. Choix modal / Itinéraire",
    "evenement_jugement": "2. Jugement d'événement (injection)",
    "stm_reflection": "3. Mémoire court terme / Soir (STM)",
    "ltm_self_reflection": "4. Auto-réflexion long terme (LTM)",
    "enquete_affinite": "5. Enquêtes d'affinité / Perception",
    "evenement_relais": "6. Transmission au foyer (relais du lecteur)",
}

DESCRIPTIONS_CATEGORIES: dict[str, str] = {
    "itinary_multi_agent": "Décision de transport quotidienne à chaque déplacement.",
    "evenement_jugement": "Évalue sévérité et valence au moment où l'agent vit ou lit l'événement.",
    "stm_reflection": "Consolidation nocturne, formation des croyances et récit du soir au foyer.",
    "ltm_self_reflection": "Synthèse périodique (24 h) des croyances et concepts en mémoire longue.",
    "enquete_affinite": "Réponse aux questionnaires d'affinité modale quotidiens ou périodiques.",
    "evenement_relais": "Le lecteur écrit ce qu'il dit de l'article à chaque membre de son foyer (un appel par foyer exposé, ticket 111).",
}

# Cohorte de référence historique (Ticket 077/095)
COHORTE_10_PERSONAS = [
    "899549",  # Corinne
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

ETATS_EXPERIENCE = (
    "en_cours",
    "traite_ok",
    "partielle",
    "terminee",
    "suspendue",
    "echec",
    "arretee",
)


def slugify(texte: str) -> str:
    """Normalise une chaîne pour le nom canonique : minuscules, tirets, pas d'espaces."""
    s = str(texte).strip().lower()
    s = re.sub(r"[^\w.\-]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def raccourcir_modele(modele: str) -> str:
    """Abrège les noms de modèles fréquents pour garder le nom canonique compact."""
    m = slugify(modele)
    m = m.replace("gemini-3.8-flash", "gem38f")
    m = m.replace("gemini-3.1-flash-lite", "gem31flite")
    m = m.replace("gemini-3.5-flash", "gem35f")
    m = m.replace("gpt-5.6-luna", "gpt56luna")
    m = m.replace("qwen-3.8-27b", "qwen38-27b")
    return m


def raccourcir_evenement(evenement: str) -> str:
    """Abrège l'identifiant d'événement pour le nom canonique."""
    e = slugify(evenement)
    for pfx in (
        "c6-voiture-suspecte",
        "c3-panne-reseau",
        "c1-bouchon-rocade",
        "c2-crevaison",
        "c4-train-supprime",
        "c5-orage-grele",
    ):
        if e.startswith(pfx):
            return pfx[:2] + e[len(pfx) :]
    for pfx in (
        "a13-punaises-metro",
        "a07-greve-eboueurs",
        "a09-vent-autan",
        "a18-la-machine",
        "a25-velotoulouse",
    ):
        if e.startswith(pfx):
            return pfx[:3] + e[len(pfx) :]
    return e


def nom_canonique(
    canal: str,
    evenement: str,
    modele_decision: str,
    population: str,
    horizon_jours: int,
    indice: int = 1,
    partage_foyer: bool = False,
) -> str:
    """Calcule le nom canonique d'une expérience mémoire (Règle N1 & D4).

    Format : exp_mem_<canal>_<evt>_<modele>_<pop>_<horizon>j[_foyer][_<indice>]

    `_foyer` marque le partage de la mémoire dans le foyer (ticket 100, lot 4). Sans lui, deux
    expériences qui ne diffèrent que par ce réglage ne se distingueraient que par leur indice.
    """
    tag_canal = "choc" if canal == "vecu" else "presse"
    tag_evt = raccourcir_evenement(evenement) or "sans-evt"
    tag_mod = raccourcir_modele(modele_decision) or "mod"
    tag_pop = slugify(population).replace(".json", "")
    if len(tag_pop) > 16:
        tag_pop = tag_pop[:16]
    base = f"exp_mem_{tag_canal}_{tag_evt}_{tag_mod}_{tag_pop}_{horizon_jours}j"
    if partage_foyer:
        base += "_foyer"
    if indice > 1:
        return f"{base}_{indice}"
    return base


def trouver_dossier_experience(nom: str) -> Path | None:
    """Trouve le dossier d'une expérience mémoire (directe ou en sous-dossier chocs/presse)."""
    direct = DOSSIER_MEMOIRE / nom
    if direct.is_dir():
        return direct
    if DOSSIER_MEMOIRE.is_dir():
        for f in DOSSIER_MEMOIRE.rglob("experience_memoire.yaml"):
            if "archive" in f.parts or ".system_generated" in f.parts:
                continue
            if f.parent.name == nom:
                return f.parent
    legacy = REPO_ROOT / "data" / "experiences_memoire"
    if legacy.is_dir() and legacy != DOSSIER_MEMOIRE:
        if (legacy / nom).is_dir():
            return legacy / nom
        for f in legacy.rglob("experience_memoire.yaml"):
            if "archive" in f.parts or ".system_generated" in f.parts:
                continue
            if f.parent.name == nom:
                return f.parent
    return None


def sous_dossier_categorie(config: dict[str, Any]) -> Path:
    """Détermine le chemin cible selon le type d'événement mémoire."""
    nom = str(config.get("nom", ""))
    canal = str(config.get("canal", ""))
    evt = str(config.get("evenement", ""))

    if "choc" in nom.lower() or canal == "vecu" or evt.lower().startswith("c"):
        cat = "chocs_reseau"
        if "c1" in nom.lower() or evt.lower() == "c1":
            evt_dir = "C1_bouchon_rocade_42j"
        elif "c2" in nom.lower() or evt.lower() == "c2":
            evt_dir = "C2_crevaison_42j"
        elif "c6" in nom.lower() or evt.lower() == "c6":
            evt_dir = "C6_voiture_suspecte_42j"
        else:
            evt_dir = evt or "autres_chocs"
    else:
        cat = "articles_presse"
        if "a09" in nom.lower() or "vent" in nom.lower() or evt.lower() == "a09":
            evt_dir = "A09_vent_autan_15j"
        elif "a13" in nom.lower() or "punaises" in nom.lower() or evt.lower() == "a13":
            evt_dir = "A13_punaises_metro_25j"
        else:
            evt_dir = evt or "autres_articles"
    return DOSSIER_MEMOIRE / cat / evt_dir


def nom_disponible(
    canal: str,
    evenement: str,
    modele_decision: str,
    population: str,
    horizon_jours: int,
    nom_existant: str | None = None,
    partage_foyer: bool = False,
) -> str:
    """Trouve un nom canonique disponible dans data/experiences_memoire/."""
    base = nom_canonique(
        canal,
        evenement,
        modele_decision,
        population,
        horizon_jours,
        partage_foyer=partage_foyer,
    )
    if nom_existant and nom_existant.startswith(base):
        return nom_existant
    if not trouver_dossier_experience(base):
        return base
    idx = 2
    while trouver_dossier_experience(f"{base}_{idx}"):
        idx += 1
    return f"{base}_{idx}"


attribuer_nom = nom_disponible


def decrire_population(population: str) -> dict[str, int]:
    """Effectif et nombre de foyers d'au moins deux membres, lus sur `data/population/`.

    Sert à chiffrer une expérience et à refuser le partage dans le foyer là où il n'a pas d'objet.
    `cohorte_10` est la liste de dix personas unitaires du rejeu séquentiel : dix agents, aucun
    foyer partagé. Un identifiant sans dossier compte pour un agent.
    """
    if population == "cohorte_10":
        return {"agents": 10, "foyers_partages": 0}
    racine = REPO_ROOT / "data" / "population"
    for dossier in (racine / population, racine / f"population_1_{population}"):
        fichier = dossier / "population.json"
        if fichier.is_file():
            data = json.loads(fichier.read_text(encoding="utf-8"))
            membres: dict[str, int] = {}
            for p in data:
                foyer = (
                    (p.get("household") or {}).get("id")
                    if isinstance(p, dict)
                    else None
                )
                if foyer is not None:
                    membres[str(foyer)] = membres.get(str(foyer), 0) + 1
            return {
                "agents": len(data),
                "foyers_partages": sum(1 for n in membres.values() if n >= 2),
            }
    return {"agents": 1, "foyers_partages": 0}


def catalogue_evenements(canal: str | None = None) -> list[dict[str, Any]]:
    """Liste tous les événements du catalogue (config/evenements/ et chocs).

    Filtre par canal ('vecu' ou 'lu') si demandé (D5).
    """
    evts: list[dict[str, Any]] = []
    dossiers = [DOSSIER_EVENEMENTS]
    if DOSSIER_CHOCS.is_dir():
        dossiers.append(DOSSIER_CHOCS)

    vus: set[str] = set()
    for dossier in dossiers:
        if not dossier.is_dir():
            continue
        for f in sorted(dossier.glob("*.yaml")):
            stem = f.stem
            if stem in vus or stem.endswith("__banc") or stem.endswith("__banc_juge"):
                continue
            vus.add(stem)
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            c = (
                str(data.get("canal") or ("vecu" if stem.startswith("c") else "lu"))
                .strip()
                .lower()
            )
            if canal and c != canal:
                continue
            libelle = str(data.get("libelle") or stem)
            evts.append(
                {
                    "id": stem,
                    "canal": c,
                    "moment": str(
                        data.get("moment") or ("arrivee" if c == "vecu" else "reveil")
                    ),
                    "libelle": libelle,
                    "source": str(data.get("source") or ""),
                    "fichier": str(f.relative_to(REPO_ROOT)),
                    "jugement": str(data.get("jugement") or "aucun"),
                }
            )
    return evts


def defauts() -> dict[str, Any]:
    """Valeurs par défaut du formulaire d'expérience mémoire."""
    return {
        "canal": "vecu",
        "evenement": "c6_voiture_suspecte",
        # Répartition 3.1 / 3.5 du 2026-09-24, la même que le défaut de la cohorte : la STM
        # (49 % des requêtes mesurées sur 861500) seule sur la 3.5, tout le reste sur la 3.1
        # (décision 43 %, enquêtes 5 %, LTM 3 %). `gemini-3.8-flash` n'a que 20 requêtes par
        # jour : un défaut qu'aucune expérience ne pouvait tenir.
        "modeles": {
            "itinary_multi_agent": "gemini-3.1-flash-lite",
            "evenement_jugement": "gemini-3.1-flash-lite",
            "stm_reflection": "gemini-3.5-flash-lite",
            "ltm_self_reflection": "gemini-3.1-flash-lite",
            "enquete_affinite": "gemini-3.1-flash-lite",
            # Ticket 111 — même modèle que le jugement par défaut : les deux appels portent sur
            # le même article, au même instant.
            "evenement_relais": "gemini-3.1-flash-lite",
        },
        "temperature_decision": 0.0,
        "variante_prompt": "prompt_expert_05",
        "population": "899549",
        "horizon_jours": 42,
        "arret_sur_extinction": False,
        "jours_apres_extinction": 5,
        "graine_calendrier": 42,
        "graine_tirage": 42,
        "memoire_importance_choc": 0.70,
        "stm_reflection_min_entries": 5,
        "contrefactuel_ab": True,
        "partage_foyer": False,
        # 2026-09-25 — rejeu à prompt exact entre les deux bras (llm_gateway/core/rejeu_ab.py).
        # Vrai pour une expérience NEUVE ; une déclaration sans la clé tourne sans rejeu.
        "rejeu_ab": True,
        "adaptateur": None,
    }


def charger_etat_formulaire() -> dict[str, Any]:
    """Recharge la dernière configuration enregistrée ou jouée (D2)."""
    base = defauts()
    if ETAT_FORMULAIRE_MEMOIRE.is_file():
        try:
            d = yaml.safe_load(ETAT_FORMULAIRE_MEMOIRE.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                merged = {**base, **d}
                if "modeles" in d and isinstance(d["modeles"], dict):
                    merged["modeles"] = {**base.get("modeles", {}), **d["modeles"]}
                return merged
        except Exception as e:
            logger.warning(
                f"formulaire_memoire.yaml illisible ({e}) — retour aux défauts"
            )
    return base


def sauver_etat_formulaire(valeurs: dict[str, Any]) -> bool:
    """Persiste les choix actuels pour la prochaine session (D2). True si modifié."""
    ETAT_FORMULAIRE_MEMOIRE.parent.mkdir(parents=True, exist_ok=True)
    try:
        contenu = yaml.safe_dump(valeurs, allow_unicode=True, sort_keys=False)
        if (
            ETAT_FORMULAIRE_MEMOIRE.is_file()
            and ETAT_FORMULAIRE_MEMOIRE.read_text(encoding="utf-8") == contenu
        ):
            return False
        ETAT_FORMULAIRE_MEMOIRE.write_text(contenu, encoding="utf-8")
        return True
    except Exception as e:
        logger.warning(f"Impossible de sauver formulaire_memoire.yaml : {e}")
        return False


def adaptateurs_disponibles(providers_yaml_path: Path | None = None) -> list[str]:
    """Les fournisseurs (`adapter`) déclarés dans providers.yaml, triés."""
    f = providers_yaml_path or PROVIDERS_YAML
    try:
        p_data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as e:
        logger.error(f"Erreur lecture providers.yaml : {e}")
        return []
    providers = p_data.get("providers", p_data) if isinstance(p_data, dict) else {}
    return sorted(
        {
            str(cfg["adapter"])
            for cfg in providers.values()
            if isinstance(cfg, dict) and cfg.get("adapter") and cfg.get("default_model")
        }
    )


def modeles_servis(
    adaptateur: str, providers_yaml_path: Path | None = None
) -> set[str]:
    """Les modèles qu'au moins une instance de ce fournisseur sert."""
    f = providers_yaml_path or PROVIDERS_YAML
    try:
        p_data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return set()
    providers = p_data.get("providers", p_data) if isinstance(p_data, dict) else {}
    return {
        str(cfg["default_model"]).strip()
        for cfg in providers.values()
        if isinstance(cfg, dict)
        and cfg.get("default_model")
        and str(cfg.get("adapter", "")).strip() == adaptateur
    }


def resoudre_instances_admises(
    modeles_dict: dict[str, str],
    providers_yaml_path: Path | None = None,
    adaptateur: str | None = None,
) -> dict[str, list[str]]:
    """Convertit un dictionnaire catégorie -> modèle en table de routage instances_admises.

    Utilise les déclarations de providers.yaml pour trouver les instances de clés.
    Chaque catégorie reçoit au moins les instances servant son modèle.

    `adaptateur` (ex. `groq`) ne garde que les instances de ce fournisseur. Un même nom de modèle
    peut être servi par deux fournisseurs — `qwen/qwen3.8-27b` l'est par Groq ET par LM Studio —
    et sans ce filtre une expérience déclarée « tout Groq » enverrait une partie de ses appels
    ailleurs. Une catégorie que le filtre laisse vide est rendue vide : c'est à l'appelant de la
    refuser, pas à cette fonction de la remplir d'autorité.
    """
    f = providers_yaml_path or PROVIDERS_YAML
    instances_par_modele: dict[str, list[str]] = {}
    if f.is_file():
        try:
            p_data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            providers = (
                p_data.get("providers", p_data) if isinstance(p_data, dict) else {}
            )
            for inst_nom, cfg in providers.items():
                if isinstance(cfg, dict) and cfg.get("default_model"):
                    if adaptateur and str(cfg.get("adapter", "")).strip() != adaptateur:
                        continue
                    mod = str(cfg["default_model"]).strip()
                    instances_par_modele.setdefault(mod, []).append(inst_nom)
        except Exception as e:
            logger.error(f"Erreur lecture providers.yaml : {e}")

    routage: dict[str, list[str]] = {}
    for cat in CATEGORIES_COGNITIVES:
        mod = modeles_dict.get(cat, "")
        if mod == "aucun" or not mod:
            routage[cat] = []
            continue
        insts = instances_par_modele.get(mod, [])
        routage[cat] = sorted(insts)

    # Repli 'defaut' = instances du modèle de décision
    mod_dec = modeles_dict.get("itinary_multi_agent", "")
    routage["defaut"] = sorted(instances_par_modele.get(mod_dec, []))
    return routage


def enregistrer_experience(config: dict[str, Any]) -> tuple[Path, bool]:
    """Enregistre l'expérience mémoire dans data/experiences_memoire/<categorie>/<evenement>/<nom>/."""
    nom = config.get("nom")
    if not nom or not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._\-]{2,127}$", nom):
        raise ValueError(f"Nom d'expérience invalide : {nom!r}")

    existant = trouver_dossier_experience(nom)
    if existant:
        exp_dir = existant
    else:
        exp_dir = sous_dossier_categorie(config) / nom
    exp_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = exp_dir / "experience_memoire.yaml"

    contenu = yaml.safe_dump(config, allow_unicode=True, sort_keys=False)
    modifie = True
    if yaml_path.is_file() and yaml_path.read_text(encoding="utf-8") == contenu:
        modifie = False
    else:
        yaml_path.write_text(contenu, encoding="utf-8")

    # Initialise etat.json s'il n'existe pas
    etat_path = exp_dir / "etat.json"
    if not etat_path.is_file():
        etat_initial = {
            "nom": nom,
            "etat": "en_attente",
            "cree_le": datetime.now(timezone.utc).isoformat(),
            "traite": {"etat": "en_attente"},
            "temoin": {"etat": "en_attente"},
        }
        etat_path.write_text(json.dumps(etat_initial, indent=2), encoding="utf-8")

    sauver_etat_formulaire(config)
    return exp_dir, modifie


def lister_experiences() -> list[dict[str, Any]]:
    """Balaie data/experiences_memoire/ récursivement et rend la liste ordonnée des expériences."""
    if not DOSSIER_MEMOIRE.is_dir():
        return []

    exp_dirs = []
    for cfg_file in DOSSIER_MEMOIRE.rglob("experience_memoire.yaml"):
        if "archive" in cfg_file.parts or ".system_generated" in cfg_file.parts:
            continue
        exp_dirs.append(cfg_file.parent)

    resultats: list[dict[str, Any]] = []
    for exp_dir in sorted(exp_dirs, key=lambda p: p.name, reverse=True):
        cfg_file = exp_dir / "experience_memoire.yaml"
        if not cfg_file.is_file():
            continue
        try:
            cfg = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
        except Exception:
            cfg = {}

        etat_file = exp_dir / "etat.json"
        etat_data: dict[str, Any] = {}
        if etat_file.is_file():
            try:
                etat_data = json.loads(etat_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Vérification des sous-dossiers traite et temoin
        dir_traite = exp_dir / "traite"
        dir_temoin = exp_dir / "temoin"

        def _statut_bras(cle: str, dossier: Path) -> str:
            # L'état déclaré prime quand il dit « suspendu » : un moves.csv resté d'une tentative
            # précédente ne fait pas d'un bras interrompu par le quota un bras abouti.
            declare = etat_data.get(cle, {}).get("etat", "en_attente")
            if declare == "suspendu":
                return declare
            return "ok" if (dossier / "moves.csv").is_file() else declare

        statut_traite = _statut_bras("traite", dir_traite)
        statut_temoin = _statut_bras("temoin", dir_temoin)

        if "suspendu" in (statut_traite, statut_temoin):
            global_statut = "suspendue"
        elif statut_traite == "ok" and statut_temoin == "ok":
            global_statut = "terminee"
        elif statut_traite == "ok":
            global_statut = "traite_ok"
        else:
            global_statut = etat_data.get("etat") or "en_attente"

        # Témoin Ticket 106
        temoin_106 = "—"
        temoin_file = dir_traite / "temoin_souvenir.jsonl"
        if temoin_file.is_file():
            try:
                lignes = [
                    json.loads(l)
                    for l in temoin_file.read_text().splitlines()
                    if l.strip()
                ]
                if any(x.get("retrouve") for x in lignes):
                    temoin_106 = "✅ Retrouvé"
                else:
                    temoin_106 = "❌ Non retrouvé"
            except Exception:
                temoin_106 = "⚠️ Erreur"

        resultats.append(
            {
                "nom": exp_dir.name,
                "dossier": exp_dir,
                "canal": cfg.get("canal", "—"),
                "evenement": cfg.get("evenement", "—"),
                "modele_decision": cfg.get("modeles", {}).get(
                    "itinary_multi_agent", "—"
                ),
                "modele_jugement": cfg.get("modeles", {}).get(
                    "evenement_jugement", "—"
                ),
                "modele_stm": cfg.get("modeles", {}).get("stm_reflection", "—"),
                "population": cfg.get("population", "—"),
                "horizon_jours": cfg.get("horizon_jours", "—"),
                "etat": global_statut,
                "statut_traite": statut_traite,
                "statut_temoin": statut_temoin,
                "temoin_106": temoin_106,
                "modifie_le": datetime.fromtimestamp(cfg_file.stat().st_mtime),
                "config": cfg,
                "etat_data": etat_data,
            }
        )
    return resultats


def execution_vivante(nom_exp: str, exp_dir: Optional[Path] = None) -> bool:
    """Détermine si l'expérience mémoire est réellement en train de tourner sur la machine."""
    import subprocess
    import time

    # 1. Processus orchestrateur ou runner actif
    try:
        res = subprocess.run(
            ["pgrep", "-f", f"orchestrateur_memoire.*{nom_exp}|run_sequential_cohort.*{nom_exp}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0 and res.stdout.strip():
            return True
    except Exception:
        pass

    # 2. Vérifier etat.json : si elle n'est pas marquée en_cours, elle ne tourne pas sans process
    dossier = exp_dir or (DOSSIER_MEMOIRE / nom_exp)
    etat_file = dossier / "etat.json"
    if not etat_file.is_file():
        return False
    try:
        data = json.loads(etat_file.read_text(encoding="utf-8"))
        if data.get("etat") != "en_cours":
            return False
    except Exception:
        return False

    # 3. Si etat == "en_cours", vérifier si experiments/current ou etat.json a été écrit récemment
    lien_current = REPO_ROOT / "experiments" / "current"
    if lien_current.is_symlink() or lien_current.exists():
        try:
            cible = lien_current.resolve()
            app_log = cible / "app.log"
            if app_log.is_file() and (time.time() - app_log.stat().st_mtime) < 180:
                runs_dir = REPO_ROOT / "experiments" / "runs"
                if any(p.name.startswith(nom_exp) for p in runs_dir.iterdir() if p.is_dir()):
                    return True
        except Exception:
            pass

    return (time.time() - etat_file.stat().st_mtime) < 180



def enchainement_nuit_en_cours() -> Optional[dict[str, Any]]:
    """Détecte si une campagne de nuit (enchainer_experiences_memoire.sh) est en cours."""
    import subprocess

    dossier_exp = REPO_ROOT / "experiments"
    if not dossier_exp.is_dir():
        return None
    journaux = sorted(
        dossier_exp.glob("enchainement_nuit_*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not journaux:
        return None
    plus_recent = journaux[0]

    vivant = False
    try:
        res = subprocess.run(
            ["pgrep", "-f", "enchainer_experiences_memoire.sh"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        vivant = res.returncode == 0 and bool(res.stdout.strip())
    except Exception:
        pass

    derniere = ""
    try:
        lignes = plus_recent.read_text(encoding="utf-8", errors="ignore").splitlines()
        derniere = lignes[-1] if lignes else ""
    except Exception:
        pass

    detail = plus_recent.with_suffix(".detail.txt")
    return {
        "fichier": plus_recent,
        "detail": detail if detail.is_file() else plus_recent,
        "derniere_ligne": derniere,
        "vivant": vivant,
        "nom": plus_recent.stem,
        "maj": plus_recent.stat().st_mtime,
    }


def progression_memoire(nom_exp: str, cfg: dict[str, Any], etat_data: dict[str, Any]) -> dict[str, Any]:
    """Calcule l'état d'avancement d'une expérience mémoire (jours simulés, branche, etc.)."""
    import os
    import time

    try:
        horizon = int(cfg.get("horizon_jours", 42))
    except (ValueError, TypeError):
        horizon = 42

    branche = etat_data.get("branche_active")
    if not branche:
        if etat_data.get("traite", {}).get("etat") == "en_cours":
            branche = "treated"
        elif etat_data.get("temoin", {}).get("etat") == "en_cours":
            branche = "control"
        else:
            branche = (
                "treated"
                if etat_data.get("traite", {}).get("etat") != "ok"
                else "control"
            )

    derniere_journee = "Amorçage…"
    jours_faits = 0
    current = REPO_ROOT / "experiments" / "current"
    if current.exists():
        try:
            cible = current.resolve()
            checkpoints = list(cible.glob("population_1_checkpoint_*.json"))
            if checkpoints:
                jours_faits = len(checkpoints)

            app_log = cible / "app.log"
            if app_log.is_file():
                try:
                    with open(app_log, "rb") as f:
                        f.seek(0, os.SEEK_END)
                        taille = f.tell()
                        f.seek(max(0, taille - 16384))
                        queue = f.read().decode("utf-8", errors="ignore")
                    for ligne in reversed(queue.splitlines()):
                        if "[sync] END sim_time=" in ligne:
                            derniere_journee = (
                                ligne.split("sim_time=", 1)[1]
                                .split(" state_update", 1)[0]
                                .strip()
                            )
                            break
                        if "[bootstrap]" in ligne or "INITIALISATION" in ligne:
                            derniere_journee = "Amorçage simulation…"
                            break
                except Exception:
                    pass
        except Exception:
            pass

    pourcent = (
        min(100.0, (jours_faits / horizon) * 100.0) if horizon > 0 else 0.0
    )

    debut_iso = (
        etat_data.get("traite", {}).get("debut")
        if branche == "treated"
        else (
            etat_data.get("temoin", {}).get("debut")
            or etat_data.get("debut")
        )
    ) or etat_data.get("debut")
    ecoule_s = None
    if debut_iso:
        try:
            t0 = datetime.fromisoformat(
                debut_iso.replace("Z", "+00:00")
            ).timestamp()
            ecoule_s = max(0.0, time.time() - t0)
        except Exception:
            pass

    return {
        "branche": branche,
        "branche_label": (
            "A (Traité)" if branche in ("treated", "traite") else "B (Témoin)"
        ),
        "jours_faits": jours_faits,
        "horizon_jours": horizon,
        "pourcent": pourcent,
        "derniere_journee": derniere_journee,
        "ecoule_s": ecoule_s,
    }


def tail_log(nom_exp: str, nb_lignes: int = 40) -> tuple[str, str]:
    """Extrait la queue du journal le plus pertinent pour une expérience mémoire.
    Rend (contenu, source_path_str).
    """
    import os

    dash_dir = REPO_ROOT / "experiments" / ".dashboard"
    if dash_dir.is_dir():
        candidats = sorted(
            dash_dir.glob("*-root-experience-memoire-lancer*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for c in candidats:
            try:
                entete = c.open("r", encoding="utf-8", errors="ignore").read(500)
                if nom_exp in entete:
                    lignes = c.read_text(
                        encoding="utf-8", errors="replace"
                    ).splitlines()
                    return (
                        "\n".join(lignes[-nb_lignes:])
                        if lignes
                        else "(journal vide)",
                        str(c.relative_to(REPO_ROOT)),
                    )
            except Exception:
                pass

    runs_dir = REPO_ROOT / "experiments" / "runs"
    if runs_dir.is_dir():
        candidats = sorted(
            runs_dir.glob(f"{nom_exp}_*/**/run_orchestrateur.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if candidats:
            try:
                lignes = candidats[0].read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
                return (
                    "\n".join(lignes[-nb_lignes:])
                    if lignes
                    else "(journal vide)",
                    str(candidats[0].relative_to(REPO_ROOT)),
                )
            except Exception:
                pass

    app_log = REPO_ROOT / "experiments" / "current" / "app.log"
    if app_log.is_file():
        try:
            with open(app_log, "rb") as f:
                f.seek(0, os.SEEK_END)
                taille = f.tell()
                f.seek(max(0, taille - 24576))
                bloc = f.read().decode("utf-8", errors="replace")
            lignes = bloc.splitlines()
            return (
                "\n".join(lignes[-nb_lignes:]) if lignes else "(journal vide)",
                "experiments/current/app.log",
            )
        except Exception:
            pass

    dossier_exp = REPO_ROOT / "experiments"
    if dossier_exp.is_dir():
        nuit_logs = sorted(
            dossier_exp.glob("enchainement_nuit_*.detail.txt"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if nuit_logs:
            try:
                with open(nuit_logs[0], "rb") as f:
                    f.seek(0, os.SEEK_END)
                    taille = f.tell()
                    f.seek(max(0, taille - 24576))
                    bloc = f.read().decode("utf-8", errors="replace")
                lignes = bloc.splitlines()
                return (
                    "\n".join(lignes[-nb_lignes:])
                    if lignes
                    else "(journal vide)",
                    str(nuit_logs[0].relative_to(REPO_ROOT)),
                )
            except Exception:
                pass

    local_log = DOSSIER_MEMOIRE / nom_exp / "traite" / "app.log"
    if local_log.is_file():
        try:
            lignes = local_log.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
            return (
                "\n".join(lignes[-nb_lignes:]) if lignes else "(journal vide)",
                f"data/experiences_memoire/{nom_exp}/traite/app.log",
            )
        except Exception:
            pass

    return ("Aucun journal disponible pour le moment.", "—")


def activites_en_cours() -> list[dict[str, Any]]:
    """Retourne la liste des expériences mémoire en cours d'exécution."""
    exps = lister_experiences()
    en_cours = []
    for e in exps:
        nom = e["nom"]
        etat = e["etat"]
        vivante = execution_vivante(nom, e["dossier"])
        if etat == "en_cours" or (vivante and etat not in ("terminee", "arretee")):
            prog = progression_memoire(nom, e["config"], e["etat_data"])
            log_tail, log_src = tail_log(nom, nb_lignes=35)
            en_cours.append(
                {
                    **e,
                    "vivante": vivante,
                    "progression": prog,
                    "log_tail": log_tail,
                    "log_src": log_src,
                }
            )
    return en_cours


def interrompues() -> list[dict[str, Any]]:
    """Retourne les expériences mémoire suspendues, arrêtées ou en échec."""
    exps = lister_experiences()
    arretees = []
    for e in exps:
        etat = e["etat"]
        vivante = execution_vivante(e["nom"], e["dossier"])
        if etat in ("suspendue", "arretee", "echec") or (
            etat == "en_cours" and not vivante
        ):
            etat_data = e["etat_data"]
            note = etat_data.get("note", "")
            traite_etat = etat_data.get("traite", {}).get("etat", "")
            temoin_etat = etat_data.get("temoin", {}).get("etat", "")
            cause_libelle = "Arrêtée"
            cause_icone = "⏹"
            if etat == "suspendue" or "suspendu" in (traite_etat, temoin_etat):
                cause_libelle = "Suspendue (quota / 503)"
                cause_icone = "⏸"
            elif etat == "echec":
                cause_libelle = "Échec d'exécution"
                cause_icone = "🔴"
            elif etat == "en_cours" and not vivante:
                cause_libelle = "Processus interrompu"
                cause_icone = "⏹"

            detail = note or (
                f"Bras traité : {traite_etat} · Bras témoin : {temoin_etat}"
            )
            arretees.append(
                {
                    **e,
                    "cause_icone": cause_icone,
                    "cause_libelle": cause_libelle,
                    "cause_detail": detail,
                }
            )
    return arretees


def terminees() -> list[dict[str, Any]]:
    """Retourne les expériences mémoire terminées."""
    exps = lister_experiences()
    return [e for e in exps if e["etat"] == "terminee"]

