"""Onglet « 🧪 Expériences » (ticket 035) : composer, lancer, suivre, relire.

Trois blocs : **Nouvelle expérience** (un formulaire, pas un fichier à éditer : population,
jeu, prompt, décideur, mode… ; « s'inspirer de » recopie une expérience existante — E4). Le
**nom ne se saisit pas** : il se calcule depuis les paramètres (`experiences.nommage`, spec
`nommage-canonique-experiences`), et le formulaire l'affiche,
**Mes expériences** (registre, barre d'avancement, pause / arrêt / reprise, rejouer, dupliquer),
**Détail** (exécution → personne → déplacement → trace, E15).

Le tableau de bord reste léger : il lit et écrit des fichiers (`experience.yaml`, `PAUSE`,
`STOP`, `progression.json`) et lance les cibles `make` de la plateforme par le registre de jobs
suivi dans l'onglet « 📟 Activités en cours » — il n'importe pas la pile du contrôleur.

Ce qui tourne est lu SUR LE DISQUE (`activites_en_cours`), pas dans le registre de jobs : une
exécution ou une construction de jeu lancée depuis un terminal est vue elle aussi.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import yaml

try:  # importé comme paquet (app.py, tests) ou à plat (Streamlit lancé depuis scripts/dashboard)
    from scripts.dashboard import lmstudio
except ImportError:  # pragma: no cover
    import lmstudio  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
DOSSIER = REPO_ROOT / "data" / "experiences"
DOSSIER_JEUX = REPO_ROOT / "data" / "jeux"
DOSSIER_POP = REPO_ROOT / "data" / "population"
PROMPTS_YAML = REPO_ROOT / "mobility_llm" / "src" / "mobility_llm" / "prompts" / "prompts.yaml"
# Même fichier que `metrics.PROVIDERS_YAML` : les deux constantes doivent rester d'accord,
# un test le garde. Le refactor du module LLM a déplacé ce fichier et celle-ci avait suivi
# à moitié, ce qui vidait la liste des modèles du formulaire sans le dire.
PROVIDERS_YAML = REPO_ROOT / "config" / "llm_gateway" / "providers.yaml"
ETAT_ARCHIVE_MANQUANTE = "archive manquante"
POP_CONTENEUR = "/data/eqasim-output"          # montage de data/population dans le contrôleur

# Le nom de l'expérience sert à construire `data/experiences/<nom>/` et à passer `EXP=<nom>`
# à `make`, qui développe `$(EXP)` SANS guillemets dans une commande shell. Ce qui est refusé
# est donc ce qui est dangereux — séparateurs de chemin, espaces, métacaractères — et non ce
# qui est inhabituel : les lettres accentuées sont sans danger et « Prompt_Éco » est valide.
# Le premier caractère est une lettre ou un chiffre, pour écarter « ../… » et « -flag ».
MOTIF_NOM = re.compile(r"^[^\W_][\w.\-]{0,63}$", re.UNICODE)

ETAT_EN_COURS = "en_cours"
ETAT_TERMINEE = "terminee"
# Les autres états que `etat.json` peut porter (définis par `experiences.archive`). Le module
# n'en nommait que deux et comparait le reste à des chaînes littérales éparpillées, si bien
# qu'« interrompue » — écrit par la réconciliation des fantômes — n'était reprenable nulle part.
ETAT_EN_PAUSE = "en_pause"
ETAT_EPUISEE = "epuisee"
ETAT_ARRETEE = "arretee"
ETAT_INTERROMPUE = "interrompue"
ETAT_EN_ATTENTE_QUOTA = "en_attente_quota"

# Une coupure réseau ne se lit JAMAIS dans l'état : le runner ne la nomme pas. Elle ne se
# reconnaît qu'au type de la dernière tentative échouée (`erreurs.jsonl`), d'où ce motif —
# les 16 lignes « Gateway LLM injoignable (ConnectError) » des archives en sont l'origine.
# Ce que le MESSAGE de la dernière tentative échouée révèle, dans cet ordre de priorité. Le
# `type` seul ne suffit pas : « Exception interne » recouvre aussi bien une variante de prompt
# inexistante (75 lignes dans les archives — une erreur de configuration) qu'une coupure DNS.
#
# La saturation passe AVANT le réseau : « passerelle_occupee: Timeout expiré » est une
# passerelle débordée, pas un câble coupé, et le mot « timeout » du motif réseau la classerait
# à tort. L'ordre de ce tuple est donc porteur de sens, pas cosmétique.
SIGNAUX_ERREUR = (
    ("prompt", "🧩", "prompt refusé : variante introuvable dans prompts.yaml",
     re.compile(r"variante de prompt.*introuvable|prompt.*introuvable|prompt refus", re.IGNORECASE)),
    ("agent", "🤖", "sous-agent Antigravity muet",
     re.compile(r"antigravity\s*:?\s*pas de r[eé]ponse|sous-agent.*muet", re.IGNORECASE)),
    ("saturation", "🚧", "passerelle saturée : aucun fournisseur disponible",
     re.compile(r"passerelle_occupee|providers? satur|satur[eé]", re.IGNORECASE)),
    ("reseau", "📡", "passerelle injoignable ou coupure réseau",
     re.compile(r"injoignable|connect(?:ion)?error|connexion|connection\s|timeout|timed out|"
                r"disconnected|name or service not known|"
                r"r[eé]seau|network|unreachable|resolve|getaddrinfo|ssl", re.IGNORECASE)),
)
# Rétro-compatibilité : ce nom désignait le seul motif existant, il vaut désormais celui du réseau.
MOTIF_RESEAU = SIGNAUX_ERREUR[-1][3]

# Les causes que le journal d'erreurs peut nommer et qui n'ont pas d'état à elles : elles ne
# remplacent qu'une cause qui ne se nomme pas elle-même (le quota garde la priorité, son heure
# de reprise valant mieux que tout diagnostic).
CAUSES_DEDUITES_DU_JOURNAL = tuple(cle for cle, *_ in SIGNAUX_ERREUR)

# Combien de lignes de la queue de `erreurs.jsonl` on relit pour compter les échecs identiques
# consécutifs : un incident isolé et un mur ne se lisent pas pareil.
ECHECS_A_RELIRE = 12

# L'ordre d'affichage des exécutions arrêtées : ce qui vient d'ailleurs (quota, réseau,
# machine) avant ce que l'utilisateur a décidé lui-même (pause).
ORDRE_CAUSES = ("quota", "prompt", "agent", "saturation", "reseau",
                "processus", "inactivite", "incomplete", "pause", "inconnue")

# Les choix du formulaire survivent au redémarrage de Streamlit : `st.session_state` meurt
# avec le serveur, et retrouver quinze réglages à la main après chaque `make dashboard` est
# le genre de friction qui fait renoncer. `experiments/` est ignoré par git.
ETAT_FORMULAIRE = REPO_ROOT / "experiments" / ".dashboard" / "formulaire_experience.yaml"

# Une construction de jeu écrit sa progression toutes les 5 s. Au-delà de cette marge plus
# personne n'écrit : le jeu est relançable, et la construction reprendra où elle s'est arrêtée.
FRAICHEUR_CONSTRUCTION_S = 120

# Une exécution tuée garde `etat.json = en_cours` : l'arrêt est coopératif (PAUSE / STOP). Sans
# repère, la tuile afficherait sa dernière barre indéfiniment. On ne diagnostique pas un gel —
# une pénurie de quota peut faire attendre — on écrit depuis quand plus rien n'a été écrit.
FRAICHEUR_EXECUTION_S = 600

# Le runner met en pause tout seul au-delà de `EXP_INACTIVITE_PAUSE_S` (7 min par défaut) sans
# le moindre déplacement réglé. On l'écrit sur la barre bien avant, pour voir venir la bascule
# au lieu de la découvrir dans l'état.
SEUIL_IMMOBILE_VISIBLE_S = 60

# Après un clic sur « construire le jeu », le dossier du jeu n'existe pas encore : on
# surveille quand même pendant ce délai, sinon l'apparition du jeu passerait inaperçue.
DELAI_SURVEILLANCE_S = 300

# Pendant la surveillance des services, sonder plus court que le cache normal (15 s) : sinon
# la sonde relit trois fois la même valeur périmée et le bandeau survit au démarrage.
DELAI_SONDE_SERVICES_S = 3

# Arrêt coopératif : le runner honore STOP en quelques secondes (délai de grâce, puis abandon
# des sollicitations en vol). Au-delà de ce délai, on refuse de lancer plutôt que de faire
# tourner deux runners sur le même quota.
DELAI_ARRET_S = 30

# Ce qui entre en concurrence avec un lancement. `root:jeu` n'y est PAS : construire un jeu ne
# consomme pas de quota LLM, son produit est ce que le lancement attend, et l'interrompre
# jetterait une heure de calcul.
LABELS_CONCURRENTS = ("root:experience-lancer", "root:experience-reprendre", "root:run")

COMPOSE = REPO_ROOT / "docker-compose.yml"

# Les services du compose dont une expérience se sert. Nommer la tête de chaîne suffit à les
# démarrer : le compose entraîne ses dépendances. Restent dehors, et c'est voulu, les cinq
# services de métrologie — Prometheus, Grafana, cAdvisor, node-exporter, Flower — dont une
# expérience n'a aucun besoin, là où `make up` les réveille tous.
SERVICE_PLATEFORME = "controller"
SERVICES_PASSERELLE = ("api", "worker")
SERVICES_ROUTAGE = ("otp1", "otp2", "otp3", "osmnx1")
SERVICES_MONITORING = ("prometheus", "grafana", "cadvisor", "node_exporter", "flower")

TOLERANCES_PROPOSEES = {"walk": "insensible", "bike": "insensible", "car": "heure", "transit": {"pas_min": 10}, "rail": {"pas_min": 10}}
TYPES_DECIDEUR = (
    "passerelle",
    "antigravity",
    "duree_minimale",
    "aleatoire",
    "rejeu",
    "modele",
    "majoritaire_voiture",
)
# Le formulaire scinde « passerelle » en deux entrées : un modèle servi par un fournisseur
# DISTANT (quota journalier, clés) ou par LM Studio sur CETTE machine (chargement, contexte).
# Le fichier écrit garde `decideur.type: passerelle` : la plateforme ne connaît qu'un décideur
# « modèle de langage », et c'est le modèle qui dit où il est servi (providers.yaml).
CHOIX_DECIDEUR = (
    "passerelle_distant",
    "passerelle_local",
    "antigravity",
    "duree_minimale",
    "aleatoire",
    "rejeu",
    "modele",
    "majoritaire_voiture",
)
LIBELLES_DECIDEUR = {
    "passerelle_distant": "modèle de langage (distant)",
    "passerelle_local": "modèle de langage (local, LM Studio)",
    "antigravity": "sous-agent Antigravity (sans quota)",
    "duree_minimale": "heuristique : durée minimale",
    "aleatoire": "tirage uniforme graîné",
    "rejeu": "rejeu d'une exécution archivée",
    "modele": "modèle LightGBM (PROGEDO)",
    "majoritaire_voiture": "a priori : majorité voiture",
}


def type_plateforme(choix: str) -> str:
    """Le `decideur.type` du fichier depuis le choix du formulaire : les deux entrées « modèle de langage » s'écrivent `passerelle`."""
    return "passerelle" if str(choix).startswith("passerelle") else str(choix)


def choix_decideur(type_fichier: str, modele: Optional[str], locaux) -> str:
    """Le choix du formulaire depuis un `decideur` de fichier : `passerelle` devient local ou distant selon qui sert le modèle."""
    if type_fichier != "passerelle":
        return str(type_fichier)
    return "passerelle_local" if modele and str(modele) in locaux else "passerelle_distant"
POLITIQUES = ("commune", "propre", "aleatoire")


# ── lecture ──────────────────────────────────────────────────────────────────

def _json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    except ValueError:
        return {}


def _yaml(p: Path) -> dict:
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {} if p.is_file() else {}
    except yaml.YAMLError:
        return {}


def populations() -> list[str]:
    """Dossiers scellés (MANIFEST.yaml) puis fichiers JSON nus, relatifs à la racine."""
    if not DOSSIER_POP.is_dir():
        return []
    scellees = sorted(str(p.relative_to(REPO_ROOT)) for p in DOSSIER_POP.iterdir() if (p / "MANIFEST.yaml").is_file())
    nues = sorted(str(p.relative_to(REPO_ROOT)) for p in DOSSIER_POP.glob("*.json"))
    return scellees + nues


def chemin_conteneur(population_hote: str) -> str:
    """`data/population/X` → `/data/eqasim-output/X` (la CLI tourne dans le contrôleur)."""
    rel = Path(population_hote)
    try:
        rel = rel.relative_to("data/population")
    except ValueError:
        return population_hote
    return f"{POP_CONTENEUR}/{rel}"


def chemin_hote(population_conteneur: str) -> str:
    if population_conteneur.startswith(POP_CONTENEUR + "/"):
        return f"data/population/{population_conteneur[len(POP_CONTENEUR) + 1:]}"
    return population_conteneur


def jeux() -> list[dict]:
    out = []
    if DOSSIER_JEUX.is_dir():
        for p in sorted(DOSSIER_JEUX.iterdir()):
            m = _yaml(p / "MANIFEST.yaml")
            if m:
                out.append({"nom": m.get("nom", p.name), "population": (m.get("population") or {}).get("nom"),
                            "jour": m.get("jour_simule"), "clos": bool(m.get("clos")),
                            "couverts": (m.get("couverts") or {}).get("deplacements"), "attendus": (m.get("attendus") or {}).get("deplacements")})
    return out


def prompt_ecarte(entree: dict) -> Optional[str]:
    """Raison pour laquelle une variante ne doit pas être proposée au choix, ou None.

    Même critère que le refus de service de `PromptManager` (spec hygiène §2.1, §4.2) :
    proposer dans le formulaire un prompt que la passerelle refusera ensuite ferait perdre un
    lancement pour rien. Reproduit ici, et non importé, parce que le tableau de bord lit le
    YAML sans monter le moteur — la duplication est verrouillée par un test de parité.
    """
    if not isinstance(entree, dict):
        return "entrée illisible"
    inv = entree.get("_invalidation")
    if isinstance(inv, dict) and inv.get("statut") == "invalide":
        regle = inv.get("regle")
        return f"invalidée{f' (règle {regle})' if regle else ''}"
    avis = entree.get("_neutralite")
    if isinstance(avis, dict):
        if avis.get("verdict") == "non_conforme":
            return "audit de neutralité : non conforme"
        scelle = str(avis.get("sha256_texte") or "")
        if scelle:
            import hashlib

            reel = hashlib.sha256(str(entree.get("content") or "").encode("utf-8")).hexdigest()
            if scelle != reel:
                return "avis d'audit périmé (texte modifié depuis)"
    return None


def variantes_prompt(*, inclure_ecartees: bool = False) -> tuple[list[str], Optional[str]]:
    """(variantes proposables, variante active).

    Les variantes invalidées, jugées non conformes ou dont l'avis d'audit est périmé sont
    retirées du choix : la passerelle les refuse au service, les proposer n'offrirait qu'un
    lancement perdu. `variantes_prompt_ecartees()` dit lesquelles et pourquoi — un retrait qui
    ne se compte pas serait une suppression déguisée.
    """
    d = _yaml(PROMPTS_YAML)
    prompts = d.get("prompts") or {}
    noms = sorted(prompts)
    if not inclure_ecartees:
        noms = [n for n in noms if prompt_ecarte(prompts.get(n) or {}) is None]
    return noms, (d.get("active") or {}).get("itinary_multi_agent")


def variantes_prompt_ecartees() -> dict[str, str]:
    """variante retirée du choix → raison, pour la rendre visible sans la proposer."""
    prompts = (_yaml(PROMPTS_YAML).get("prompts") or {})
    return {
        n: r
        for n in sorted(prompts)
        if (r := prompt_ecarte(prompts.get(n) or {})) is not None
    }


def prompts_textes() -> dict[str, dict]:
    """variante → {contenu, mots, provenance} — pour lire un prompt avant de le choisir."""
    d = _yaml(PROMPTS_YAML)
    out = {}
    for nom, entree in ((d.get("prompts") or {}).items()):
        if not isinstance(entree, dict):
            continue
        contenu = str(entree.get("content") or "")
        out[nom] = {"contenu": contenu, "mots": len(contenu.split()) if contenu else None, "provenance": entree.get("_provenance") or {}}
    return out


class _Bloc(str):
    """Chaîne rendue en bloc littéral `|` dans le YAML (lisible, diff propre)."""


def _representer_bloc(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style="|")


yaml.add_representer(_Bloc, _representer_bloc, Dumper=yaml.SafeDumper)


def ajouter_variante(nom: str, contenu: str, *, derive_de: Optional[str] = None, chemin: Path = PROMPTS_YAML,
                     role: str = "créé depuis le tableau de bord") -> Path:
    """Ajoute une variante de prompt système à `prompts.yaml` — JAMAIS d'écrasure.

    L'entrée est ajoutée à la fin du fichier (la section `prompts:` est la dernière), en bloc
    littéral, avec sa provenance ; le fichier est relu pour vérifier qu'il reste valide et que la
    clé y figure, sinon l'écriture est annulée. La passerelle lit ce fichier au démarrage de son
    worker : la recharger ensuite (`make passerelle-recharger`).
    """
    nom = nom.strip()
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*", nom):
        raise ValueError("nom de variante invalide : lettres, chiffres, `_`, `-`, `.` seulement")
    contenu = (contenu or "").strip("\n")
    if not contenu.strip():
        raise ValueError("le prompt est vide")
    existant = _yaml(chemin)
    if nom in (existant.get("prompts") or {}):
        raise ValueError(f"la variante {nom!r} existe déjà : choisissez un autre nom (jamais d'écrasure)")
    if "prompts" not in existant or list(existant.keys())[-1] != "prompts":
        raise ValueError("prompts.yaml : la section `prompts:` doit être la dernière du fichier pour y ajouter une entrée")
    entree = {nom: {"content": _Bloc(contenu + "\n"), "_provenance": {
        "role": role, "obtention": (f"édité depuis la variante {derive_de!r}" if derive_de else "saisi dans le tableau de bord"),
        "date": date.today().isoformat(), "mots": len(contenu.split()), "derive_de": derive_de,
    }}}
    bloc = yaml.safe_dump(entree, allow_unicode=True, sort_keys=False, width=100_000)
    ajout = "".join("  " + ligne + "\n" if ligne.strip() else "\n" for ligne in bloc.rstrip("\n").split("\n"))
    original = chemin.read_text(encoding="utf-8")
    nouveau = original.rstrip("\n") + "\n\n" + ajout
    chemin.write_text(nouveau, encoding="utf-8")
    relu = _yaml(chemin)
    if nom not in (relu.get("prompts") or {}) or (relu["prompts"][nom].get("content") or "").strip() != contenu.strip():
        chemin.write_text(original, encoding="utf-8")
        raise ValueError("écriture annulée : le fichier relu ne contient pas la variante attendue")
    return chemin


def etat_passerelle(url: str = "http://localhost:8000/health", timeout: float = 1.5) -> Optional[dict]:
    """Quotas du jour par instance (`/health` de la passerelle, vue de l'hôte) — None si injoignable."""
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 — URL locale fixe
            return (json.loads(r.read().decode("utf-8")) or {}).get("providers") or {}
    except Exception:  # noqa: BLE001
        return None


def quotas_par_modele(etat: Optional[dict]) -> dict[str, dict]:
    """modèle → {instances: [...], marge: requêtes/jour restantes ou None, limite: total, detail: str}."""
    d = _yaml(PROVIDERS_YAML)
    providers = d.get("providers", d) if isinstance(d, dict) else {}
    out: dict[str, dict] = {}
    for nom, cfg in (providers or {}).items():
        if not isinstance(cfg, dict) or not cfg.get("default_model"):
            continue
        limite = cfg.get("rpd_limit")
        conso = ((etat or {}).get(nom) or {}).get("daily_requests")
        m = out.setdefault(str(cfg["default_model"]), {"instances": [], "marge": 0, "limite": 0, "inconnu": False, "detail": []})
        m["instances"].append(nom)
        # « clé N » = rang de l'instance parmi celles qui servent ce modèle, pas son nom :
        # l'utilisateur raisonne en clés/seaux de quota, pas en identifiants providers.yaml.
        cle = f"clé {len(m['instances'])}"
        if limite is None:
            m["inconnu"] = True
            m["detail"].append(f"{cle} : sans limite journalière")
        elif etat is None or conso is None:
            m["limite"] += int(limite); m["inconnu"] = True
            m["detail"].append(f"{cle} : {limite}/jour (consommation inconnue)")
        else:
            m["marge"] += max(0, int(limite) - int(conso)); m["limite"] += int(limite)
            m["detail"].append(f"{cle} : {int(limite) - int(conso)} restantes sur {limite}")
    return dict(sorted(out.items()))


def debit_par_modele(etat: Optional[dict]) -> dict[str, dict]:
    """modèle → {rpm: débit cumulé des instances VIVANTES, instances: [...]}.

    Vivantes, pas déclarées : une instance sans clé est exclue de la rotation par la
    passerelle, et son débit n'existe pas. Passerelle injoignable → on retombe sur les
    instances déclarées, faute de mieux, et on le dit.
    """
    d = _yaml(PROVIDERS_YAML)
    providers = d.get("providers", d) if isinstance(d, dict) else {}
    out: dict[str, dict] = {}
    for nom, cfg in (providers or {}).items():
        if not isinstance(cfg, dict) or not cfg.get("default_model"):
            continue
        vivante = etat is None or nom in etat
        if not vivante:
            continue
        rpm = ((etat or {}).get(nom) or {}).get("rpm_limit") or cfg.get("rpm_limit") or 0
        m = out.setdefault(str(cfg["default_model"]), {"rpm": 0, "instances": [], "mesure": etat is not None})
        # Le MAXIMUM d'une instance, pas la somme : les instances d'un même modèle sont
        # consommées en SÉRIE (une clé après l'autre), donc le débit qui compte à un instant
        # donné est celui d'une seule. Sommer conseillerait un parallélisme deux fois trop
        # grand, et la moitié des tentatives repartirait en « providers saturés ».
        m["rpm"] = max(m["rpm"], int(rpm))
        m["instances"].append(nom)
    return out


def parallelisme_conseille(modele: str, etat: Optional[dict]) -> Optional[dict]:
    """Le parallélisme qu'un modèle peut réellement absorber, ou None si on l'ignore.

    Demander huit décisions simultanées à une instance qui accepte quinze requêtes par
    minute produit une moitié de tentatives perdues : la passerelle répond « saturés » et la
    plateforme remet le déplacement en attente. On conseille donc un cinquième du débit par
    minute, borné à [1, 16] — une décision durant quelques secondes, c'est l'ordre de
    grandeur qui sature sans gâcher.

    Le débit retenu est celui d'UNE instance, la mieux dotée : les clés d'un même modèle se
    consomment en série, l'une après l'autre, jamais en parallèle.
    """
    d = _yaml(PROVIDERS_YAML)
    locales = lmstudio.modeles_locaux(d).get(modele)
    if locales:
        # Un modèle local ne se mesure pas en requêtes par minute : LM Studio sert au plus
        # `concurrency_limit` appels à la fois par instance, le reste attend et la passerelle
        # répond « saturés ». Le conseil, c'est ce nombre d'appels — un ou deux sur un Mac.
        providers = d.get("providers", d) if isinstance(d, dict) else {}
        appels = sum(int((providers.get(i) or {}).get("concurrency_limit") or 2) for i in locales)
        return {"valeur": max(1, min(16, appels)), "rpm": None, "instances": list(locales), "mesure": False, "local": True}
    info = debit_par_modele(etat).get(modele)
    if not info or not info["rpm"]:
        return None
    conseil = max(1, min(16, round(info["rpm"] / 5)))
    return {"valeur": conseil, "rpm": info["rpm"], "instances": info["instances"],
            "mesure": info["mesure"]}


def services_actifs(timeout: float = 8.0) -> Optional[set[str]]:
    """Services docker compose en cours d'exécution — None si docker est injoignable."""
    import subprocess
    try:
        r = subprocess.run(["docker", "compose", "ps", "--status", "running", "--services"], cwd=str(REPO_ROOT),
                           capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return {l.strip() for l in r.stdout.splitlines() if l.strip()}


def progression_jeu(nom: str) -> dict:
    return _json(DOSSIER_JEUX / nom / "progression.json")


# Les familles de fournisseurs, telles qu'on veut les LIRE dans le tableau. La famille est
# l'`adapter` de l'instance, jamais son nom : celui-ci porte un suffixe `_key1` et il y a onze
# instances Google pour un même fournisseur. `openai_compatible` est l'adapter des instances
# LM Studio — c'est leur `base_url` qui les désigne comme locales, pas leur adapter.
FOURNISSEUR_LOCAL = "local"
FOURNISSEUR_ANTIGRAVITY = "antigravity"
FOURNISSEUR_INCONNU = "inconnu"
SANS_FOURNISSEUR = "—"

_PORTEE_CACHE: dict = {}
_FAMILLES_CACHE: dict = {}


def modeles_par_portee() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """(modèles locaux → instances LM Studio, modèles distants → instances), lus dans providers.yaml.

    Mis en cache sur la date du fichier : un rendu du formulaire pose la question six fois.
    """
    try:
        cle = (str(PROVIDERS_YAML), Path(PROVIDERS_YAML).stat().st_mtime_ns)
    except OSError:
        cle = (str(PROVIDERS_YAML), None)
    if _PORTEE_CACHE.get("cle") != cle:
        d = _yaml(PROVIDERS_YAML)
        _PORTEE_CACHE.update(cle=cle, valeur=(lmstudio.modeles_locaux(d), lmstudio.modeles_distants(d)))
    return _PORTEE_CACHE["valeur"]


# Charge de référence d'une expérience du plan courant, pour juger l'aptitude d'un modèle :
# ~2 285 sollicitations, ~1 289 jetons d'entrée et ~400 de sortie par sollicitation (mesuré sur
# les demandes archivées, cf. specs/hygiene-prompts-et-plateforme-experiences.md §6).
CHARGE_REFERENCE = {"sollicitations": 2285, "jetons_entree": 1289, "jetons_sortie": 400,
                    "max_tokens_demande": 4096}

_APTITUDE_CACHE: dict[str, object] = {}


def _module_aptitude():
    """Charge `llm-agents/experiences/aptitude.py` PAR SON CHEMIN, une seule fois.

    Un `from experiences import aptitude` ne marche pas ici : ce module-ci s'appelle lui aussi
    `experiences`, l'import résout sur lui-même et échoue en `ImportError` — avalé par un
    `except`, il laissait le filtre silencieusement inerte. `aptitude.py` n'importe rien de son
    propre paquet, il se charge donc seul sans monter tout `llm-agents`.
    """
    if "module" in _APTITUDE_CACHE:
        return _APTITUDE_CACHE["module"]
    mod = None
    try:
        import importlib.util

        chemin = REPO_ROOT / "llm-agents" / "experiences" / "aptitude.py"
        spec = importlib.util.spec_from_file_location("_aptitude_experiences", chemin)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
    except Exception:  # noqa: BLE001 — un diagnostic absent ne doit pas vider le formulaire
        mod = None
    _APTITUDE_CACHE["module"] = mod
    return mod


# Réglage COURANT de l'API Gemini 3 : un niveau, pas un nombre. « high » EST le maximum —
# relevé dans ai.google.dev/gemini-api/docs/thinking le 2026-09-10. Les niveaux acceptés
# varient selon le modèle (`minimal` n'existe pas sur 3.7 ni 3.8), d'où la déclaration par
# instance dans providers.yaml.
LIBELLES_NIVEAU = {
    "minimal": "minimal — pas de réflexion",
    "low": "faible",
    "medium": "moyen",
    "high": "maximum (high)",
}
CHOIX_NIVEAU_DEFAUT = "défaut du modèle"

# Héritage : budget numérique. L'API l'accepte encore mais recommande le niveau, et les deux
# ensemble rendent 400 — le formulaire n'en propose donc qu'un à la fois.
CHOIX_REFLEXION = ("défaut du fournisseur", "désactivée (0)", "laissée au modèle (-1)", "budget fixe")
CHOIX_REFLEXION_MAX = "maximum du modèle"


def niveaux_reflexion(modele: str) -> list[str]:
    """Niveaux de réflexion DÉCLARÉS pour un modèle, dans l'ordre canonique.

    Intersection des niveaux de toutes les instances qui le servent : un niveau accepté par
    l'une et refusée par l'autre ferait échouer l'appel selon la clé tirée. Vide si une seule
    instance ne les déclare pas — on ne devine pas une liste.
    """
    providers = _yaml(PROVIDERS_YAML).get("providers") or {}
    instances = modeles().get(modele) or []
    if not instances:
        return []
    listes = [(providers.get(i) or {}).get("thinking_levels") for i in instances]
    if not listes or any(not l for l in listes):
        return []
    commun = set(listes[0])
    for l in listes[1:]:
        commun &= set(l)
    return [n for n in ("minimal", "low", "medium", "high") if n in commun]


def plafond_reflexion(modele: str) -> Optional[int]:
    """Plafond de réflexion DÉCLARÉ pour un modèle (`thinking_budget_max`), ou None.

    Le plus petit des plafonds des instances qui le servent : demander plus ferait refuser
    l'appel sur la plus contrainte d'entre elles. None dès qu'une instance ne le déclare pas —
    on ne déduit pas un plafond d'un sous-ensemble.
    """
    providers = _yaml(PROVIDERS_YAML).get("providers") or {}
    instances = modeles().get(modele) or []
    if not instances:
        return None
    plafonds = [(providers.get(i) or {}).get("thinking_budget_max") for i in instances]
    if not plafonds or any(p is None for p in plafonds):
        return None
    try:
        return min(int(p) for p in plafonds)
    except (TypeError, ValueError):
        return None


def choix_reflexion_pour(modele: str) -> tuple[tuple[str, ...], Optional[int]]:
    """(choix proposables, plafond déclaré). « maximum » n'apparaît que s'il est mesuré."""
    plafond = plafond_reflexion(modele)
    if plafond:
        return (*CHOIX_REFLEXION, f"{CHOIX_REFLEXION_MAX} ({plafond} jetons)"), plafond
    return CHOIX_REFLEXION, None


def _index_reflexion(courant: Optional[int], plafond: Optional[int] = None) -> int:
    """Index du choix correspondant à une valeur enregistrée (None / 0 / -1 / plafond / n)."""
    if courant is None:
        return 0
    if courant == 0:
        return 1
    if courant == -1:
        return 2
    if plafond and int(courant) == int(plafond):
        return 4   # relu comme « maximum », pas comme un budget fixe qui vaudrait le plafond
    return 3


def _valeur_reflexion(choix: str, courant: Optional[int], colonne, k,
                      plafond: Optional[int] = None) -> Optional[int]:
    """Valeur à écrire dans `parametres`, ou None pour « ne rien demander ».

    « maximum » résout vers le plafond DÉCLARÉ, pas vers un mot magique : l'empreinte porte
    ainsi un nombre concret et vérifiable, et non une valeur que le fournisseur aurait pu
    raboter sans le dire.
    """
    if choix == CHOIX_REFLEXION[0]:
        return None
    if choix == CHOIX_REFLEXION[1]:
        return 0
    if choix == CHOIX_REFLEXION[2]:
        return -1
    if choix.startswith(CHOIX_REFLEXION_MAX):
        return int(plafond) if plafond else None
    defaut = int(courant) if courant and courant > 0 else 1024
    haut = int(plafond) if plafond else 32768
    return int(colonne.number_input("Jetons de pensée", 1, haut, min(defaut, haut), 128,
                                    key=k("refl-n")))


def modeles_inaptes() -> dict[str, str]:
    """modèle → raison de son inaptitude, pour les retirer du choix sans les taire.

    S'appuie sur `experiences.aptitude`, le même module qui fait refuser
    `experience-estimer` et `experience-lancer` : proposer dans le formulaire un modèle que le
    lancement refusera ensuite ne mène qu'à un aller-retour perdu. Best-effort — si le module
    n'est pas importable, aucun modèle n'est écarté : mieux vaut un choix trop large qu'un
    formulaire vide.
    """
    APT = _module_aptitude()
    if APT is None:
        return {}
    providers = _yaml(PROVIDERS_YAML).get("providers") or {}
    out: dict[str, str] = {}
    for modele, instances in modeles().items():
        try:
            refus, _ = APT.verifier(modele=modele, providers=providers,
                                    instances=instances, **CHARGE_REFERENCE)
        except Exception:  # noqa: BLE001
            continue
        if refus:
            out[modele] = refus[0]
    return out


def familles_par_modele() -> dict[str, list[str]]:
    """modèle → familles de fournisseurs qui le servent (`local`, `google`, `groq`, `mistral`…).

    Lu dans `providers.yaml`, mis en cache sur la date du fichier : un rendu du registre pose la
    question une fois par ligne. Un modèle servi par deux familles les porte toutes les deux —
    c'est le cas quand une même référence est offerte par deux passerelles distantes.
    """
    try:
        cle = (str(PROVIDERS_YAML), Path(PROVIDERS_YAML).stat().st_mtime_ns)
    except OSError:
        cle = (str(PROVIDERS_YAML), None)
    if _FAMILLES_CACHE.get("cle") != cle:
        familles: dict[str, set[str]] = {}
        for nom, cfg in lmstudio._providers(_yaml(PROVIDERS_YAML)).items():
            if not isinstance(cfg, dict) or not cfg.get("default_model"):
                continue
            famille = (FOURNISSEUR_LOCAL if lmstudio.est_instance_lmstudio(cfg)
                       else str(cfg.get("adapter") or nom.split("_")[0]))
            familles.setdefault(str(cfg["default_model"]), set()).add(famille)
        _FAMILLES_CACHE.update(cle=cle, valeur={m: sorted(f) for m, f in sorted(familles.items())})
    return _FAMILLES_CACHE["valeur"]


def fournisseur_de(dec: Optional[dict]) -> str:
    """Qui sert les décisions de ce décideur — `local`, `google`, `antigravity`, `—`…

    `antigravity` l'emporte sur le nom du modèle : la décision passe par un sous-agent, pas par
    la passerelle, même quand le modèle porte un nom distant (`gemini-3.8-flash`). Un décideur
    sans LLM (tirage, durée minimale, modèle statistique, rejeu) ne sollicite personne et rend
    `—` : la colonne `decideur` dit déjà l'heuristique. Un modèle qu'aucune instance de
    `providers.yaml` ne sert rend `inconnu` — le dire vaut mieux que l'inventer.
    """
    dec = dec or {}
    if dec.get("type") == "antigravity":
        return FOURNISSEUR_ANTIGRAVITY
    if dec.get("type") != "passerelle":
        return SANS_FOURNISSEUR
    familles = familles_par_modele().get(str(dec.get("modele") or ""))
    return " · ".join(familles) if familles else FOURNISSEUR_INCONNU


def modeles() -> dict[str, list[str]]:
    """modèle → instances de passerelle qui le servent."""
    d = _yaml(PROVIDERS_YAML)
    providers = d.get("providers", d) if isinstance(d, dict) else {}
    out: dict[str, list[str]] = {}
    for nom, cfg in (providers or {}).items():
        if isinstance(cfg, dict) and cfg.get("default_model"):
            out.setdefault(str(cfg["default_model"]), []).append(nom)
    return dict(sorted(out.items()))


def derniere_utilisation(dossier: Path) -> float:
    """Quand cette expérience a servi pour la dernière fois (0.0 si elle n'a jamais tourné).

    C'est la date de dernière ÉCRITURE d'un `etat.json`, pas le nom du dossier d'exécution :
    celui-ci porte l'heure de CRÉATION, si bien qu'une exécution reprise ce soir mais ouverte
    ce matin passerait pour vieille. `etat.json` est réécrit à chaque changement d'état, donc
    à chaque reprise, pause ou clôture.

    Une seule `stat()` par exécution, aucun fichier ouvert : la liste est relue à chaque rendu
    du formulaire.
    """
    dernier = 0.0
    try:
        executions = [d for d in (dossier / "executions").iterdir() if d.is_dir()]
    except OSError:
        return 0.0
    for d in executions:
        try:
            dernier = max(dernier, (d / "etat.json").stat().st_mtime)
        except OSError:  # exécution sans état lisible : le dossier fait foi
            try:
                dernier = max(dernier, d.stat().st_mtime)
            except OSError:
                continue
    return dernier


def experiences() -> dict[str, dict]:
    """Les expériences définies, de la plus récemment utilisée à la moins récente.

    L'ordre alphabétique mettait en tête des expériences oubliées depuis des semaines, alors
    que « S'inspirer de » sert d'abord à repartir de ce qu'on vient de faire. Celles qui n'ont
    jamais tourné viennent après, par ordre alphabétique : elles n'ont pas d'usage à dater.
    """
    if not DOSSIER.is_dir():
        return {}
    trouvees = []
    for p in sorted(DOSSIER.iterdir()):
        e = _yaml(p / "experience.yaml")
        if e:
            trouvees.append((derniere_utilisation(p), e.get("nom", p.name), e))
    # Jamais utilisée ⇒ 0.0 : le tri décroissant la renverrait en tête, on la range donc à
    # part, derrière, par nom croissant.
    utilisees = sorted((t for t in trouvees if t[0]), key=lambda t: t[0], reverse=True)
    jamais = sorted((t for t in trouvees if not t[0]), key=lambda t: t[1])
    return {nom: e for _quand, nom, e in [*utilisees, *jamais]}


# ── Scores composites (spec scoring_composite_experiences) ───────────────────
# Le paquet `experiences` vit sous llm-agents/ ; on l'ajoute au path à la demande,
# sans le rendre obligatoire (le dashboard reste debout si le scoring est absent).
LLM_AGENTS = REPO_ROOT / "llm-agents"


def _bootstrap_experiences() -> None:
    if str(LLM_AGENTS) not in sys.path:
        sys.path.insert(0, str(LLM_AGENTS))


def _nommage():
    """Le module `experiences.nommage`, ou None s'il est introuvable.

    Il ne dépend que de la bibliothèque standard, justement pour être importable depuis
    l'hôte : son absence est une anomalie d'installation, pas un mode de fonctionnement —
    elle est DITE (`nommer`) au lieu de laisser le formulaire inventer un nom.
    """
    _bootstrap_experiences()
    try:
        from experiences import nommage

        return nommage
    except ImportError:
        return None


def _formule_reference_sha() -> Optional[str]:
    try:
        _bootstrap_experiences()
        from experiences import formule as F

        return F.charger().reference.sha256
    except Exception:  # noqa: BLE001 — la liste reste lisible sans formule
        return None


def formule_reference() -> Optional[dict]:
    """Nom, SHA et poids de la formule de référence courante (pour le panneau)."""
    try:
        _bootstrap_experiences()
        from experiences import formule as F

        ref = F.charger().reference
        return {"nom": ref.nom, "sha256": ref.sha256, "poids": ref.poids}
    except Exception as exc:  # noqa: BLE001
        return {"erreur": str(exc)}


def recalculer_scores() -> dict:
    """Recalcule toutes les exécutions terminées sous la formule de référence (R10, R22).

    Hors-ligne : rejeu depuis les scores bruts quand c'est possible, aucun appel LLM.
    Régénère aussi les pages de synthèse des exécutions désormais scorées.
    """
    _bootstrap_experiences()
    from experiences import formule as F
    from experiences import rendu_scores, score

    reg = F.charger()
    bilan = score.rescorer_tout(reg.reference, reg, racine=DOSSIER)
    for d in score._executions(DOSSIER):
        rendu_scores.ecrire(d, reg)
    return bilan


def _panneau_formule(st) -> None:
    """Panneau « Formule » : poids de référence, empreinte, bouton de recalcul global (R22)."""
    import pandas as pd

    ref = formule_reference() or {}
    with st.expander("⚖️ Formule de score composite", expanded=False):
        if ref.get("erreur"):
            st.warning(f"Formule indisponible : {ref['erreur']}")
            return
        st.caption(
            f"Référence **{ref['nom']}** · empreinte `{ref['sha256'][:12]}`. "
            "Édition des poids dans `llm-agents/experiences/formules/reference.yaml` "
            "(versionné en git), puis recalcul ci-dessous — instantané, hors-ligne."
        )
        poids = ref.get("poids") or {}
        st.dataframe(
            pd.DataFrame([{"dimension": k, "poids": v} for k, v in poids.items()]),
            hide_index=True, width="content",
        )
        if st.button("♻️ Recalculer toutes les expériences", key="recalc-scores"):
            with st.spinner("Recalcul hors-ligne (rejeu depuis les scores bruts)…"):
                bilan = recalculer_scores()
            st.success(
                f"Recalcul terminé : {bilan['rejouees']} rejouées, "
                f"{bilan['calculees']} calculées, {bilan['ignorees']} ignorées."
            )
            st.rerun(scope="app")


def _lignes_selectionnees(event, total: Optional[int] = None) -> list[int]:
    """Indices de lignes sélectionnées dans un `st.dataframe(on_select=...)`, tous formats.

    Bornés par `total` quand il est donné. Streamlit garde la sélection PAR INDICE sous la clé
    du tableau, et cet indice survit au rétrécissement du tableau — filtre saisi, ligne retirée,
    exécution disparue : `df.iloc[indice]` levait alors « single positional indexer is
    out-of-bounds » et la page entière tombait (vu le 2026-09-07 après un retrait de ligne).
    """
    sel = getattr(event, "selection", None)
    if sel is None and isinstance(event, dict):
        sel = event.get("selection")
    if sel is None:
        return []
    rows = sel.get("rows") if isinstance(sel, dict) else getattr(sel, "rows", None)
    rows = list(rows or [])
    return [i for i in rows if 0 <= i < total] if total is not None else rows


def _apercu_ligne_selectionnee(st, event, df) -> None:
    """Rend inline la page de scores de la ligne cliquée dans le tableau (EF-75)."""
    import pandas as pd

    rows = _lignes_selectionnees(event, len(df))
    if not rows:
        return
    ligne = df.iloc[rows[0]].to_dict()
    if pd.isna(ligne.get("composite_emd")):
        st.caption(f"« {ligne.get('experience')} / {ligne.get('execution')} » n'est pas scorée "
                   "(exécution non terminée) — pas de détail par sous-catégorie.")
        return
    page = Path(ligne["dossier"]) / "synthese_scores.html"
    if not page.exists():
        try:
            _bootstrap_experiences()
            from experiences import formule as F
            from experiences import rendu_scores

            rendu_scores.ecrire(Path(ligne["dossier"]), F.charger())
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Page de scores indisponible : {exc}")
            return
    if page.exists():
        import streamlit.components.v1 as components

        st.markdown(f"**📊 {ligne.get('experience')} / {ligne.get('execution')}** — détail par sous-catégorie")
        components.html(page.read_text(encoding="utf-8"), height=900, scrolling=True)


def _decideur_label(dec: Optional[dict]) -> str:
    """Le décideur affiché : le modèle seul pour la passerelle (le préfixe « passerelle: » est
    du bruit), sinon « type:modele » (ex. rejeu, aleatoire) ; vide si aucun type."""
    dec = dec or {}
    t = dec.get("type")
    if not t:
        return ""
    if t == "passerelle":
        return dec.get("modele") or "passerelle"
    return f"{t}:{dec.get('modele') or ''}".rstrip(":")


def _prompt_affiche(variante: Optional[str], dec: Optional[dict]) -> str:
    """Le prompt système AFFICHÉ : la variante seulement si le décideur en lit un.

    Seule la passerelle lit un prompt système : `experiences/cli.py` ne transmet
    `parameters.prompt_variant` que sous `decideur.type == "passerelle"`. Pour un modèle
    statistique, un rejeu, un tirage ou l'heuristique de durée, `gabarit.variante` est un
    résidu du formulaire que l'exécution ignore, et l'afficher laissait croire le contraire :
    le 2026-09-08, `exp_lgbm_jtir_nosim` (décideur LightGBM) annonçait « minimal_persona »
    alors qu'aucune phrase n'a été envoyée — le dossier d'exécution ne porte pas un seul
    échange LLM. Même règle que N5 du nommage, qui retire pour cette raison le segment de
    prompt du nom canonique (`exp_lgbm_jtir_nosim`, et non `exp_lgbm_minper_jtir_nosim`).
    """
    if (dec or {}).get("type") not in ("passerelle", "antigravity"):
        return "—"
    return variante or "actif"  # sans variante désignée : le prompt ACTIF de la passerelle


def decideur_de(nom: str) -> str:
    """Label du décideur défini dans `experience.yaml` d'une expérience (vide si inconnue)."""
    exp = experiences().get(nom)
    return _decideur_label((exp or {}).get("decideur")) if exp else ""


# ── entrées retirées du tableau ──────────────────────────────────────────────
# Retirer une ligne du registre ne touche PAS au disque : une archive vaut des heures de calcul
# et des décisions déjà payées, et un clic de trop les effaçait sans retour. Les entrées
# retirées vivent dans ce fichier, à côté des autres registres cachés du dossier
# (`.file.json`, `.reservations.json`) ; la restitution est à un clic, si bien que rien ne
# disparaît en silence (E20).
NOM_MASQUES = ".masques.json"


def _fichier_masques(dossier: Optional[Path] = None) -> Path:
    """Résolu à l'APPEL, comme le défaut de `lister()` : une redirection de `DOSSIER` est suivie."""
    return (Path(dossier) if dossier is not None else DOSSIER) / NOM_MASQUES


def _cle_masque(experience, execution) -> tuple[str, str]:
    """Une ligne du tableau, c'est une paire (expérience, exécution) — « definie » n'en a pas."""
    return (str(experience or ""), str(execution or ""))


def masques(dossier: Optional[Path] = None) -> list[dict]:
    """Les entrées retirées du tableau, dans l'ordre où elles l'ont été."""
    contenu = _json(_fichier_masques(dossier))
    entrees = contenu if isinstance(contenu, list) else []
    return [e for e in entrees if isinstance(e, dict) and e.get("experience")]


def _ecrire_masques(entrees: list[dict], dossier: Optional[Path] = None) -> None:
    chemin = _fichier_masques(dossier)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    provisoire = chemin.with_name(chemin.name + ".tmp")
    provisoire.write_text(json.dumps(entrees, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(provisoire, chemin)


def masquer(experience: str, execution: Optional[str] = None,
            dossier: Optional[Path] = None) -> dict:
    """Retire du registre la LIGNE (expérience, exécution) — sans rien effacer sur le disque.

    Portée : cette ligne seulement. Retirer une exécution d'une expérience laisse ses autres
    exécutions dans le tableau ; retirer une expérience sans exécution retire sa définition du
    tableau, pas son dossier. Refuse une exécution encore vivante : elle sortirait du panneau
    « en cours » pendant qu'elle écrit, et plus personne ne saurait qu'il faut l'arrêter.
    Rend l'entrée retirée. Idempotent : retirer deux fois la même ligne n'écrit rien de plus.
    """
    lignes = lister() if dossier is None else lister(dossier)
    vivantes = [l for l in lignes
                if l["experience"] == experience and (l.get("execution") or None) == (execution or None)
                and l.get("etat") == ETAT_EN_COURS and execution_vivante(l["dossier"])]
    if vivantes:
        raise ValueError(
            f"« {experience} / {execution} » tourne encore : mettez-la en pause ou attendez sa "
            "fin avant de la retirer du tableau")
    entree = {"experience": experience, "execution": execution,
              "retiree_le": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    deja = masques(dossier)
    cle = _cle_masque(experience, execution)
    if not any(_cle_masque(e["experience"], e.get("execution")) == cle for e in deja):
        _ecrire_masques(deja + [entree], dossier)
    return entree


def demasquer_tout(dossier: Optional[Path] = None) -> int:
    """Rend au tableau toutes les entrées retirées, et annonce combien."""
    n = len(masques(dossier))
    if n:
        _ecrire_masques([], dossier)
    return n


def _statut_experience(exp_dir: Path) -> dict:
    """Statut d'une expérience, best-effort — un marqueur illisible vaut « actif »."""
    st = _json(exp_dir / "statut.json")
    statut = st.get("statut")
    if statut not in ("actif", "archivee", "invalide"):
        return {"statut": "actif", "motif": None}
    return {"statut": statut, "motif": st.get("motif")}


def masquee(ligne: dict) -> bool:
    """Vrai si la ligne sort des vues par défaut (archivée ou invalidée)."""
    return ligne.get("statut") in ("archivee", "invalide")


def lister(dossier: Optional[Path] = None) -> list[dict]:
    # Défaut résolu à l'APPEL : lié à l'import, il ignorait une redirection de `DOSSIER`,
    # alors que toutes les autres lectures du module la respectent.
    dossier = Path(dossier) if dossier is not None else DOSSIER
    lignes: list[dict] = []
    if not dossier.is_dir():
        return lignes
    ref_sha = _formule_reference_sha()  # pour dériver le drapeau « périmée » (R7)
    for exp_dir in sorted(p for p in dossier.iterdir() if (p / "experience.yaml").is_file()):
        exp = _yaml(exp_dir / "experience.yaml")
        base_variante = (exp.get("gabarit") or {}).get("variante")
        # Statut de l'expérience (spec hygiène §3.2) : `lister()` ne masque RIEN ici — plusieurs
        # vues (activités en cours, reprise) doivent voir toutes les lignes. Le champ est exposé,
        # et c'est la vue qui décide de filtrer.
        _st = _statut_experience(exp_dir)
        base = {"experience": exp.get("nom", exp_dir.name), "mode": exp.get("mode"),
                "statut": _st.get("statut", "actif"), "statut_motif": _st.get("motif"),
                "decideur": _decideur_label(exp.get("decideur")),
                "fournisseur": fournisseur_de(exp.get("decideur")),
                "prompt": _prompt_affiche(base_variante, exp.get("decideur")),
                "jeu": (exp.get("jeu") or {}).get("nom"),
                "jeu_etat": etat_du_jeu((exp.get("jeu") or {}).get("nom") or ""),
                "derive_de": exp.get("derive_de")}
        sur_disque = sorted(p.name for p in (exp_dir / "executions").iterdir()) if (exp_dir / "executions").is_dir() else []
        for nom in sur_disque:
            d = exp_dir / "executions" / nom
            etat, compteurs, synth, conf = _json(d / "etat.json"), _json(d / "compteurs.json"), _json(d / "synthese.json"), _yaml(d / "execution.yaml")
            couv = compteurs.get("couverture") or {}
            parts = (synth.get("parts_modales") or {}).get("pourcent") or {}
            scores = _json(d / "scores.json")
            comp = scores.get("composite") or {}
            f_score = scores.get("formule") or {}
            f_sha = f_score.get("sha256")
            # R6 — le décideur affiché est celui RÉELLEMENT utilisé, figé dans le snapshot de
            # l'exécution, pas celui (mutable) de la définition courante : deux exécutions d'une
            # même expérience peuvent porter des décideurs différents.
            exp_fige = conf.get("experience") or {}
            dec_fige = _decideur_label(exp_fige.get("decideur")) or base["decideur"]
            # R6 vaut aussi pour le prompt : c'est le décideur FIGÉ qui dit si un prompt a été
            # lu — une même expérience peut avoir été décidée par la passerelle, puis par le
            # modèle statistique. Un snapshot sans décideur retombe sur la définition.
            prompt_fige = (
                _prompt_affiche((exp_fige.get("gabarit") or {}).get("variante") or base_variante,
                                exp_fige.get("decideur"))
                if exp_fige.get("decideur") else base["prompt"])
            # Le fournisseur suit le décideur FIGÉ, comme lui et comme le prompt : deux
            # exécutions d'une même expérience peuvent avoir tourné sur des fournisseurs
            # différents, et afficher celui de la définition courante mentirait sur l'archive.
            fournisseur_fige = (fournisseur_de(exp_fige.get("decideur")) if exp_fige.get("decideur")
                                else base["fournisseur"])
            lignes.append({**base, "decideur": dec_fige, "prompt": prompt_fige,
                           "fournisseur": fournisseur_fige,
                           "execution": nom, "etat": etat.get("etat", "?"), "raison": etat.get("raison"),
                           "reprise_possible_a": etat.get("reprise_possible_a"), "date": conf.get("cree_le"),
                           "decides": couv.get("decides"), "attendus": couv.get("attendus"), "couverture": couv.get("taux"),
                           # Scores (R5, R7, R9) : None → « — », jamais 0 ; drapeau périmée dérivé.
                           "composite_emd": comp.get("emd_jsd"), "composite_l1": comp.get("l1"),
                           "volet": scores.get("volet"), "formule": f_score.get("nom"),
                           "formule_perimee": bool(f_sha and ref_sha and f_sha != ref_sha),
                           **{f"part_{m}": v for m, v in parts.items()}, "dossier": str(d)})
        for nom in sorted(set(exp.get("executions_connues") or []) - set(sur_disque)):
            lignes.append({**base, "execution": nom, "etat": ETAT_ARCHIVE_MANQUANTE, "raison": "dossier disparu",
                           "dossier": str(exp_dir / "executions" / nom)})
        if not sur_disque and not exp.get("executions_connues"):
            lignes.append({**base, "execution": None, "etat": "definie", "dossier": str(exp_dir)})
    # Obsolète : une exécution qu'une plus récente de la MÊME expérience a remplacée. C'est un
    # état de VUE, jamais écrit dans `etat.json` — le runner reste seul propriétaire de l'état
    # réel. Il existe parce que la CLI ne sait reprendre que la dernière exécution
    # (`_derniere_execution`) : sans ce drapeau, « ▶ Reprendre » promettait sur une ligne plus
    # ancienne une reprise que le noyau refuse.
    dernieres: dict[str, str] = {}
    for l in lignes:
        if l.get("execution") and l["execution"] > dernieres.get(l["experience"], ""):
            dernieres[l["experience"]] = l["execution"]
    for l in lignes:
        l["derniere"] = bool(l.get("execution")) and l["execution"] == dernieres.get(l["experience"])
        l["obsolete"] = bool(l.get("execution")) and not l["derniere"]

    # Ce qui tourne reste visible même retiré du tableau : une exécution relancée en console
    # (`make experience-reprendre`) sur une ligne retirée écrirait sinon sans que personne ne
    # la voie ni ne puisse l'arrêter. Le retrait la reprendra quand elle se sera tue.
    caches = {_cle_masque(e["experience"], e.get("execution")) for e in masques(dossier)}
    return [l for l in lignes
            if _cle_masque(l["experience"], l.get("execution")) not in caches
            or (l.get("etat") == ETAT_EN_COURS and execution_vivante(l["dossier"]))]


def est_terminee(ligne: dict) -> bool:
    """Cette ligne du registre est-elle une exécution MENÉE À TERME ?

    Strictement l'état `terminee`. `epuisee`, `arretee` et `interrompue` sont des états
    *finaux* — plus rien n'écrit — mais pas *terminés* : la couverture y est partielle et
    l'exécution reste reprenable. Les confondre reviendrait à présenter un résultat partiel
    comme complet (E14), ce que le tableau se refuse à faire partout ailleurs.
    """
    return (ligne or {}).get("etat") == ETAT_TERMINEE


def decisions(dossier_execution: Path) -> list[dict]:
    p = Path(dossier_execution) / "decisions.jsonl"
    out = []
    if p.is_file():
        for ligne in p.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(ligne))
            except ValueError:
                continue
    return out


def synthese(dossier_execution: Path) -> dict:
    return _json(Path(dossier_execution) / "synthese.json")


def progression(dossier_execution: Path) -> dict:
    return _json(Path(dossier_execution) / "progression.json")


def _n(valeur) -> str:
    """Une valeur venue d'un fichier écrit par le conteneur : inconnue → « ? », jamais une exception."""
    return "?" if valeur is None else f"{valeur:,}".replace(",", " ") if isinstance(valeur, int) else str(valeur)


def _duree(secondes) -> str:
    """Une durée en `hh:mm:ss` — « reste ≈ 6765 s » ne se lit pas, « 01:52:45 » se lit.

    Les heures ne sont pas bornées à 24 : une construction de jeu de 31 heures s'écrit
    « 31:20:05 », jamais « 07:20:05 ». Valeur illisible ou négative → « ? », jamais d'exception :
    ces nombres viennent d'un fichier écrit par le conteneur pendant qu'on le lit.
    """
    try:
        total = int(float(secondes))
    except (TypeError, ValueError):
        return "?"
    if total < 0:
        return "?"
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def _avancement(p: dict, *, faits: str, total: str) -> dict:
    """L'avancement d'un fichier de progression, borné et tolérant.

    Ces fichiers sont écrits par le conteneur pendant qu'on les lit : tronqués, vides ou
    incomplets, ils ne doivent pas casser la page. Champ absent → None (affiché « ? »),
    pourcentage ramené dans [0, 100].
    """
    fait, attendu, pourcent = p.get(faits), p.get(total), p.get("pourcent")
    if pourcent is None and isinstance(fait, (int, float)) and isinstance(attendu, (int, float)) and attendu:
        pourcent = 100.0 * fait / attendu
    try:
        pourcent = None if pourcent is None else max(0.0, min(100.0, float(pourcent)))
    except (TypeError, ValueError):
        pourcent = None
    return {"faits": fait, "total": attendu, "pourcent": pourcent, "reste_s": p.get("reste_s"),
            "maj": p.get("maj"), "erreurs": p.get("erreurs"), "attentes": p.get("attentes"),
            "attentes_par_type": p.get("attentes_par_type") or {}, "mesure": bool(p)}


def _age_s(maj) -> Optional[float]:
    """Âge en secondes d'un horodatage ISO de progression — None s'il est illisible."""
    if not maj:
        return None
    try:
        moment = datetime.fromisoformat(str(maj))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - moment).total_seconds()


def _demande_depuis(fichier: Path) -> Optional[float]:
    """Secondes depuis qu'une demande d'interruption a été déposée (PAUSE / STOP), ou None
    si elle ne l'a pas été. Le fichier est le seul canal partagé avec le runner : sa seule
    existence permet d'afficher « demandée » sans attendre le prochain état écrit."""
    try:
        return max(0.0, time.time() - fichier.stat().st_mtime)
    except OSError:
        return None


def nommer(exp: dict) -> tuple[Optional[object], Optional[str]]:
    """(attribution, raison d'échec) — le nom que ces paramètres imposent (N1, N10).

    Le nom n'est plus saisi : deux expériences qui diffèrent d'un paramètre nommé portent
    deux noms, et une définition identique à une existante EST cette expérience (N10). Le
    2026-09-07, trois modèles ont été mesurés sous « Prompt_Minimaliste » parce que le nom
    était libre ; le calculer supprime la classe entière de ce défaut.

    La raison d'échec est faite pour être affichée telle quelle sous le bouton grisé : un
    formulaire sans modèle choisi ne peut pas nommer son expérience, et doit le dire.
    """
    N = _nommage()
    if N is None:
        return None, ("le module de nommage (llm-agents/experiences/nommage.py) est "
                      "introuvable : le nom d'une expérience ne peut pas être calculé")
    try:
        return N.attribuer_nom(exp, DOSSIER), None
    except N.NommageImpossible as e:
        return None, str(e)


def nom_jeu_attendu(population: str, date_simulee) -> str:
    """Le nom du jeu qu'une population attend pour un jour donné (R2, R7).

    Même règle que la cible `make jeu` du bouton de warm-up : `<population>_<AAAAMMJJ>`. Une
    expérience enregistrée avant que ce jeu existe le nomme donc déjà, et devient lançable
    sans retouche dès qu'il est clos.
    """
    return f"{Path(population).name.replace('.json', '')}_{str(date_simulee).replace('-', '')}"


def etat_du_jeu(nom: str) -> str:
    """« absent », « en construction » ou « clos et prêt » — ce que l'écran doit dire (R4)."""
    if not nom:
        return "absent"
    j = next((j for j in jeux() if j["nom"] == nom), None)
    if j is None:
        return "absent"
    return "clos et prêt" if j["clos"] else "en construction"


def executions_connues(nom_experience: str) -> int:
    """Combien d'exécutions porte déjà ce nom d'expérience (R6)."""
    if not nom_experience:
        return 0
    dossier = DOSSIER / nom_experience / "executions"
    return sum(1 for p in dossier.iterdir() if p.is_dir()) if dossier.is_dir() else 0


def jeux_de(population: str) -> list[dict]:
    """Les jeux d'une population, clos ou non — la liste que propose le formulaire (R17)."""
    return [j for j in jeux() if j["population"] == population]


def libelle_jeu(j: dict) -> str:
    """Le libellé d'un jeu dans la liste : sa couverture, et s'il est encore en construction.

    `couverts` et `attendus` n'entrent dans le manifeste qu'à la clôture : un jeu en
    construction n'en a pas, et les interpoler bruts affichait « None/None déplacements »
    précisément dans le cas que R17 vient rendre visible.
    """
    return (f"{j['nom']} — jour {_n(j.get('jour'))} · {_n(j.get('couverts'))}/{_n(j.get('attendus'))} déplacements"
            + ("" if j["clos"] else " (EN PRÉPARATION)"))


def jeux_en_preparation(population: Optional[str] = None) -> list[dict]:
    """Les jeux non clos (facultativement d'une seule population), avec leur progression.

    Le manifeste est écrit dès l'ouverture du jeu avec `clos: false` : un jeu en cours de
    construction est donc visible, et il DOIT l'être — sinon le formulaire annonce « aucun
    jeu préparé » pendant l'heure que dure le warm-up (R17).
    """
    sortie = []
    for j in jeux():
        if j["clos"] or (population is not None and j["population"] != population):
            continue
        p = progression_jeu(j["nom"])
        sortie.append({**j, **_avancement(p, faits="faits", total="total"),
                       "sans_proposition": p.get("sans_proposition"), "age_s": _age_s(p.get("maj"))})
    return sortie


def construction_active(nom_jeu: str) -> Optional[str]:
    """Motif si une construction du jeu `nom_jeu` tourne en ce moment, None sinon (R19).

    Le signal est la fraîcheur de `progression.json`, pas le registre de jobs : une
    construction lancée dans un terminal compte autant qu'un clic. Un jeu non clos dont
    plus rien n'écrit la progression reste relançable — la construction reprend.
    """
    p = progression_jeu(nom_jeu)
    if not p:
        return None
    age = _age_s(p.get("maj"))
    if age is None or age > FRAICHEUR_CONSTRUCTION_S:
        return None
    return (f"une construction est déjà en cours ({_n(p.get('faits'))} / {_n(p.get('total'))} déplacements, "
            f"progression écrite il y a {int(age)} s)")


def services_requis(exp: dict, *, jeu_a_construire: bool = False) -> list[str]:
    """Les services que CETTE expérience utilise, sans les autres.

    La plateforme tourne dans `controller`. La passerelle — `api` et `worker` — ne sert qu'à
    un décideur « modèle de langage » : une heuristique, un tirage ou un rejeu n'a rien à
    attendre d'elle. Les moteurs de routage ne servent qu'à construire un jeu.
    """
    requis = [SERVICE_PLATEFORME]
    if (exp.get("decideur") or {}).get("type") == "passerelle":
        requis += list(SERVICES_PASSERELLE)
    if jeu_a_construire:
        requis += list(SERVICES_ROUTAGE)
    return requis


def services_a_arreter(exp: dict, *, jeu_a_construire: bool = False) -> list[str]:
    """Ce qu'il faut arrêter pour rendre la RAM : les services requis ET leurs dépendances.

    La mémoire est dans les dépendances, pas dans la tête de chaîne : mesuré le 2026-09-07,
    `osmnx1` porte 3,5 Gio de graphe et chacun des trois OTP de 1,2 à 1,5 Gio, contre 1,0 Gio
    pour `controller` et 0,1 pour la passerelle. Arrêter le seul contrôleur ne rendrait rien.
    """
    requis = services_requis(exp, jeu_a_construire=jeu_a_construire)
    return requis + services_entraines(requis)


def dependances_compose(chemin: Optional[Path] = None) -> dict[str, list[str]]:
    """Le `depends_on` déclaré dans le compose, lu sur le fichier — jamais par un sous-processus."""
    conf = _yaml(Path(chemin) if chemin is not None else COMPOSE)
    services = conf.get("services") or {} if isinstance(conf, dict) else {}
    graphe = {}
    for nom, definition in services.items():
        dep = (definition or {}).get("depends_on") or {}
        graphe[nom] = sorted(dep) if isinstance(dep, (dict, list)) else []
    return graphe


def services_entraines(requis: list[str], chemin: Optional[Path] = None) -> list[str]:
    """Ce que `docker compose up` démarrera EN PLUS des services nommés, par leurs dépendances.

    L'annoncer évite de faire croire qu'on démarre trois conteneurs quand on en démarre huit.
    """
    graphe = dependances_compose(chemin)
    vus, pile = set(requis), list(requis)
    while pile:
        for dep in graphe.get(pile.pop(), []):
            if dep not in vus:
                vus.add(dep)
                pile.append(dep)
    return sorted(vus - set(requis))


def execution_vivante(dossier) -> bool:
    """Cette exécution écrit-elle encore ? « en cours » dans `etat.json` ne suffit pas.

    Un runner tué laisse cet état pour toujours : l'arrêt est coopératif, personne ne le
    corrige. Traiter une exécution morte comme vivante a fait du dégât le 2026-09-07 — un
    `STOP` écrit dans une exécution déjà morte, honoré à la reprise suivante, qui a clôturé
    l'exécution en « arrêtée » donc NON reprenable, avec 209 décisions payées dedans.
    """
    chemin = Path(dossier)
    age = _age_s(progression(chemin).get("maj"))
    if age is not None:
        return age <= FRAICHEUR_EXECUTION_S
    try:  # pas encore de progression : une exécution qui vient de naître écrit son état
        return (time.time() - (chemin / "etat.json").stat().st_mtime) <= FRAICHEUR_EXECUTION_S
    except OSError:
        return False


def archive_close(dossier) -> bool:
    """L'archive porte-t-elle sa clôture ? Une archive clôturée est IMMUABLE (E19).

    `etat.json` ne suffit pas à en juger : la clôture vit dans `execution.yaml`, avec les
    empreintes des fichiers. Une exécution clôturée refuse toute écriture, donc la reprise y
    échoue toujours sur « archive clôturée : immuable ». La proposer serait une boucle.
    """
    return bool(_yaml(Path(dossier) / "execution.yaml").get("cloture"))


def est_reprenable(ligne: dict) -> bool:
    """Une exécution qu'on peut poursuivre sans repayer ses décisions acquises.

    « en pause » et « épuisée » le disent d'elles-mêmes. S'y ajoute une exécution restée sur
    « en cours » que plus rien n'écrit : c'est un runner tué, et sans cela la page n'offre
    aucun chemin propre — elle ne propose que « Rejouer », qui repaie tout.

    S'y ajoutent « interrompue » — écrit par la réconciliation des fantômes quand le pid est
    mort — et « en attente de quota » qu'on a tuée pendant son sommeil : la CLI reprend toute
    archive non clôturée, et ces deux états manquaient ici. Une exécution qui dort VRAIMENT en
    attente de quota n'y figure pas : elle repartira toute seule à l'heure dite.

    Rien n'est reprenable si l'archive est clôturée, quoi que dise `etat.json` : la reprise
    échouerait sur E19 à la première décision à écrire. Rien n'est reprenable non plus sur une
    exécution OBSOLÈTE : `make experience-reprendre` ne porte que sur la dernière exécution de
    l'expérience, et proposer la reprise d'une plus ancienne serait une promesse en l'air.
    """
    dossier = ligne.get("dossier") or ""
    if archive_close(dossier) or ligne.get("obsolete"):
        return False
    etat = ligne.get("etat")
    if etat in (ETAT_EN_PAUSE, ETAT_EPUISEE, ETAT_INTERROMPUE):
        return True
    return etat in (ETAT_EN_COURS, ETAT_EN_ATTENTE_QUOTA) and not execution_vivante(dossier)


def decisions_archivees(dossier) -> int:
    """Combien de décisions cette exécution a déjà payées et rangées."""
    chemin = Path(dossier)
    nombre = _json(chemin / "etat.json").get("decisions_archivees")
    if isinstance(nombre, int) and nombre > 0:
        return nombre
    try:
        with open(chemin / "decisions.jsonl", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def cause_interruption(ligne: dict) -> dict:
    """Pourquoi cette exécution s'est arrêtée — dérivé de ce qui est ÉCRIT, jamais devine.

    L'état dit ce que le runner a constaté (quota épuisé, pause voulue, pause du chien de
    garde) ; il ne nomme JAMAIS une coupure réseau ni un PC éteint. Ces deux-là se lisent
    ailleurs : le premier dans le type de la dernière tentative échouée, le second dans le fait
    que plus rien n'est écrit alors que l'état dit « en cours ».

    Le `detail` cite toujours la ficelle brute — raison écrite, heure de reprise annoncée par
    le fournisseur, type et horodatage du dernier échec : l'écran ne remplace pas la source, il
    dit sur quoi il se fonde. Une cause qu'on ne sait pas nommer s'affiche « inconnue » avec
    son état ; rien n'est inventé pour combler le trou.
    """
    dossier = Path(ligne.get("dossier") or ".")
    etat, raison = ligne.get("etat"), str(ligne.get("raison") or "")
    reprise = ligne.get("reprise_possible_a")
    vivante = execution_vivante(dossier)
    echecs = _dernieres_lignes_json(dossier / "erreurs.jsonl", ECHECS_A_RELIRE)
    derniere = echecs[-1] if echecs else {}
    message = str(derniere.get("message") or "").strip()
    signal = f"{derniere.get('type') or ''} {message}"
    # Le premier motif qui reconnaît le message l'emporte : l'ordre de SIGNAUX_ERREUR compte.
    revele = next(((cle, icone, libelle) for cle, icone, libelle, motif in SIGNAUX_ERREUR
                   if motif.search(signal)), None)
    # Combien de fois de suite le MÊME échec, en remontant depuis la fin : un incident isolé et
    # un mur ne se lisent pas pareil, et c'est ce qui dit s'il faut agir sur la cause.
    repetitions = 0
    for e in reversed(echecs):
        if str(e.get("message") or "").strip() != message:
            break
        repetitions += 1

    if etat == ETAT_EPUISEE or (etat == ETAT_EN_ATTENTE_QUOTA and not vivante):
        cle, icone, libelle = "quota", "🪫", "quota épuisé"
        if etat == ETAT_EN_ATTENTE_QUOTA:
            libelle = "quota épuisé — l'attente de la fenêtre a été interrompue"
    elif etat == ETAT_INTERROMPUE or (etat == ETAT_EN_COURS and not vivante):
        cle, icone, libelle = "processus", "🔌", "PC ou conteneur arrêté — le runner ne répond plus"
    elif etat == ETAT_EN_PAUSE and raison.startswith("pause automatique"):
        cle, icone, libelle = "inactivite", "⏳", "pause automatique — plus rien n'avançait"
    elif etat == ETAT_EN_PAUSE and raison.startswith("incomplète"):
        cle, icone, libelle = "incomplete", "⏸", "arrêtée incomplète — reprise attendue"
    elif etat == ETAT_EN_PAUSE:
        cle, icone, libelle = "pause", "⏸", "mise en pause"
    else:
        cle, icone, libelle = "inconnue", "❔", f"arrêtée dans l'état « {etat} »"

    # Ce que le journal révèle ne prend la place que d'une cause qui ne se nomme pas elle-même :
    # « pause automatique — plus rien n'avançait » sur une exécution dont toutes les requêtes
    # échouaient sur une variante de prompt inexistante décrivait le symptôme, pas la cause. Le
    # quota, lui, se nomme et porte son heure de reprise : la remplacer ferait perdre
    # l'information la plus utile de la ligne.
    if revele and cle in ("processus", "inactivite", "incomplete", "inconnue"):
        cle, icone, libelle = revele

    age = _age_s(progression(dossier).get("maj"))
    # Le message ENTIER (tronqué à 220 caractères, le plus long des archives en fait 483 avec la
    # liste des variantes connues), pas seulement son type : c'est lui qui dit quoi corriger.
    # L'instance vient du champ `fournisseur` de l'erreur — `cerebras_gemma_4_31b_key1`,
    # `antigravity:gemini-3.8-flash` : elle dit QUI a lâché, ce que la famille ne dit pas.
    if derniere:
        # `≥` quand la répétition remplit toute la fenêtre relue : on ne sait pas combien il y en
        # a avant, et écrire « 12 fois de suite » sur un mur de 800 lignes serait faux.
        borne = "≥" if repetitions >= ECHECS_A_RELIRE else ""
        tete = "dernier échec" + (f" ({borne}{repetitions} fois de suite)" if repetitions > 1 else "")
        echec = f"{tete} : {(message or str(derniere.get('type') or 'erreur'))[:220]}"
        # Le type n'est répété que s'il n'est pas déjà dans le message : en pratique il le
        # préfixe (`passerelle_occupee: …`, `Exception interne : …`), mais rien ne le garantit.
        typ = str(derniere.get("type") or "")
        if typ and typ not in message:
            echec += f" [{typ[:60]}]"
        if derniere.get("fournisseur"):
            echec += f" · {str(derniere['fournisseur'])[:60]}"
        if derniere.get("horodatage"):
            echec += f" · à {str(derniere['horodatage'])[11:19]}"
    else:
        echec = None
    detail = " · ".join(x for x in (
        raison[:160] or None,
        f"reprise possible à {reprise}" if reprise else None,
        echec,
        f"plus rien d'écrit depuis {_duree(age)}" if isinstance(age, (int, float)) and not vivante else None,
    ) if x)
    return {"cle": cle, "icone": icone, "libelle": libelle, "detail": detail, "reprise_a": reprise,
            "echecs_consecutifs": repetitions, "message": message[:220],
            "instance": str(derniere.get("fournisseur") or "")}


def interrompues() -> dict:
    """Les exécutions arrêtées qu'on peut relancer, chacune avec la cause de son arrêt.

    N'y figurent pas : une archive scellée (arrêt définitif, exécution menée à terme), qui est
    immuable (E19) ; une exécution qui tourne ou qui dort en attente de quota, qui n'a rien à
    relancer ; une exécution obsolète, que la reprise ne toucherait pas. Ces dernières sont
    COMPTÉES, pas escamotées : `obsoletes` porte leur nombre pour que l'écran le dise.

    Rangées par cause — ce qui vient d'ailleurs (quota, réseau, machine) avant ce que
    l'utilisateur a décidé — puis par exécution la plus récente.
    """
    lignes, obsoletes = [], 0
    for ligne in lister():
        if not ligne.get("execution"):
            continue
        if ligne.get("obsolete"):
            # Elle aurait été reprenable si une plus récente ne l'avait pas remplacée : c'est
            # ce cas-là qu'il faut compter, pas les archives terminées ou scellées.
            if est_reprenable({**ligne, "obsolete": False}):
                obsoletes += 1
            continue
        if not est_reprenable(ligne):
            continue
        p = progression(Path(ligne["dossier"]))
        lignes.append({**ligne, "cause": cause_interruption(ligne),
                       "decisions": decisions_archivees(ligne["dossier"]),
                       **_avancement(p, faits="faits", total="attendus"),
                       "age_s": _age_s(p.get("maj"))})
    lignes.sort(key=lambda e: e["execution"], reverse=True)
    lignes.sort(key=lambda e: ORDRE_CAUSES.index(e["cause"]["cle"])
                if e["cause"]["cle"] in ORDRE_CAUSES else len(ORDRE_CAUSES))
    return {"lignes": lignes, "obsoletes": obsoletes}


def concurrents(jobs: Optional[Callable[[], list]] = None) -> dict:
    """Ce qui tourne et entrerait en concurrence avec un lancement (R1, R2, R9).

    Les exécutions sont lues sur le disque, donc une exécution orpheline — son
    `docker compose exec` tué sur l'hôte sans que le processus meure dans le conteneur — est
    vue elle aussi. Mais seule une exécution qui ÉCRIT ENCORE compte : une exécution morte
    n'entre en concurrence avec rien, et lui écrire un `STOP` la rendrait non reprenable.
    La construction d'un jeu n'en fait jamais partie.
    """
    executions = [{"experience": l["experience"], "execution": l["execution"], "dossier": l["dossier"]}
                  for l in lister()
                  if l.get("etat") == ETAT_EN_COURS and execution_vivante(l["dossier"])]
    lots = []
    if jobs is not None:
        lots = [j for j in jobs()
                if j.running and any(j.label.startswith(prefixe) for prefixe in LABELS_CONCURRENTS)]
    return {"executions": executions, "jobs": lots}


def libelle_concurrents(conc: dict) -> str:
    """Ce que la case à cocher annonce qu'elle arrêtera (R3)."""
    morceaux = [f"{e['experience']} / {e['execution']}" for e in conc["executions"]]
    morceaux += [f"job `{j.label}`" for j in conc["jobs"]]
    return " · ".join(morceaux)


def arreter_concurrents(conc: dict, arreter_job: Optional[Callable[[str], bool]] = None) -> list[str]:
    """Demande l'arrêt, et rend ce qui a été demandé (R4, R5, R7).

    Les exécutions reçoivent un fichier `STOP`, honoré en quelques secondes : le résultat
    partiel reste exploitable. Aucun processus n'est tué dans le conteneur — un signal y
    laisserait l'état à « en cours » pour toujours.
    """
    arretes = []
    for e in conc["executions"]:
        signaler(Path(e["dossier"]), "STOP")
        arretes.append(f"exécution {e['experience']} / {e['execution']} (STOP, effectif en quelques secondes)")
    for j in conc["jobs"]:
        if arreter_job is not None and arreter_job(j.id):
            arretes.append(f"job `{j.label}`")
    return arretes


def _encore_en_cours(executions: list[dict]) -> list[dict]:
    return [e for e in executions
            if _json(Path(e["dossier"]) / "etat.json").get("etat") == ETAT_EN_COURS]


def attendre_arret(executions: list[dict], *, delai_s: int = DELAI_ARRET_S, pas_s: float = 1.0) -> list[str]:
    """Attend que les exécutions quittent « en cours ». Rend celles qui y sont encore (R6)."""
    fin = time.time() + delai_s
    restantes = _encore_en_cours(executions)
    while restantes and time.time() < fin:
        time.sleep(pas_s)
        restantes = _encore_en_cours(restantes)
    return [f"{e['experience']} / {e['execution']}" for e in restantes]


def motifs_indisponibilite(exp: dict, *, jeu_clos: bool, controleur_ok: bool, registre: bool,
                           construction: Optional[str] = None,
                           ecrasement: Optional[str] = None,
                           modele_local: Optional[str] = None,
                           docker_ok: bool = True) -> dict[str, list[str]]:
    """Ce qui manque, bouton par bouton (R20).

    Un bouton grisé sans motif se lit comme une panne : le 2026-09-06, « Lancer » était
    interdit sans qu'on sache que c'était le nom de l'expérience qui manquait.
    """
    nom_refuse = []
    if not exp.get("nom"):
        # Le nom se calcule (N1) : s'il est vide, c'est le nommage qui a refusé, et sa raison
        # nomme le champ à corriger. « le nom est vide » n'apprendrait plus rien.
        _attribution, raison = nommer(exp)
        nom_refuse.append(raison or "le nom de l'expérience n'a pas pu être calculé")
    elif not MOTIF_NOM.match(exp["nom"]):
        nom_refuse.append("le nom ne peut porter ni espace ni séparateur de chemin — lettres, "
                          "chiffres, accents, tiret, souligné et point, 64 au plus, en commençant "
                          "par une lettre ou un chiffre : il devient un dossier et la valeur de "
                          "`EXP=` pour `make`")
    # Enregistrer ne demande QUE un nom recevable : le schéma de la plateforme accepte une
    # expérience qui nomme un jeu pas encore construit, et écrire son plan avant de lancer
    # une heure de warm-up est le cas d'usage normal (R1, R5).
    sans_jeu = [] if exp["jeu"]["nom"] else ["aucun jeu de déplacements n'est préparé pour cette population"]
    sans_controleur = [] if controleur_ok else ["le service `controller` ne tourne pas"]
    # Un contrôleur éteint ne bloque plus « Lancer » ni « Warm-up » : la cible make démarre
    # elle-même les services requis et attend qu'ils soient sains. Ce qui bloque, c'est un
    # démon Docker muet — là, personne ne peut rien démarrer. « Estimer », lui, garde le
    # verrou du contrôleur : il lit la sortie de la cible en synchrone et ne peut pas attendre
    # plusieurs minutes de chargement de graphes.
    sans_docker = [] if docker_ok else ["le démon Docker ne répond pas (ouvrez Docker Desktop)"]
    sans_registre = [] if registre else ["le registre de lancements est absent"]
    non_clos = [] if jeu_clos or not exp["jeu"]["nom"] else [f"le jeu « {exp['jeu']['nom']} » n'est pas encore clos"]
    # « Estimer » et « Lancer » écrivent aussi la définition (enregistrer() en amont) : le même
    # garde-fou d'écrasement (R6) doit les couvrir, sinon on change une définition qui a déjà
    # tourné sans passer par la confirmation — le décideur d'une expérience basculait ainsi en
    # silence au lancement d'un run modifié.
    ecr = [ecrasement] if ecrasement else []
    # Un modèle LM Studio absent ou chargé trop court n'interdit que le lancement : enregistrer
    # et estimer n'appellent pas le modèle (2026-09-08 : sept minutes sans décision, sinon).
    local = [modele_local] if modele_local else []
    return {
        "enregistrer": nom_refuse + ecr,
        "estimer": nom_refuse + sans_jeu + sans_controleur + ecr,
        "lancer": nom_refuse + sans_jeu + non_clos + sans_docker + sans_registre + ecr + local,
        "construire": sans_docker + sans_registre + ([construction] if construction else []),
    }


def activites_en_cours() -> dict:
    """Ce qui tourne, lu sur le disque : exécutions d'expérience et jeux en préparation.

    Indépendant du registre de jobs — une exécution lancée depuis un terminal, ou survivante
    d'un redémarrage du tableau de bord, est vue elle aussi.
    """
    lignes = lister()
    executions = []
    for ligne in lignes:
        if ligne.get("etat") != ETAT_EN_COURS:
            continue
        p = progression(Path(ligne["dossier"]))
        dossier = Path(ligne["dossier"])
        executions.append({
            "experience": ligne["experience"], "execution": ligne["execution"], "dossier": ligne["dossier"],
            "fournisseur": ligne.get("fournisseur"),
            **_avancement(p, faits="faits", total="attendus"),
            "personnes": p.get("personnes"), "personnes_terminees": p.get("personnes_terminees"),
            "sollicitations": p.get("sollicitations"), "ecoule_s": p.get("ecoule_s"),
            "age_s": _age_s(p.get("maj")),
            # L'interruption est demandée par fichier : son existence est un retour IMMÉDIAT,
            # sans attendre que le runner ait réécrit son état. Sans ça, un clic sur Pause
            # n'affichait rien jusqu'au changement d'état.
            "pause_demandee": _demande_depuis(dossier / "PAUSE"),
            "arret_demande": _demande_depuis(dossier / "STOP"),
            "immobile_depuis_s": p.get("immobile_depuis_s"),
        })
    return {"executions": executions, "jeux": jeux_en_preparation(),
            "definies": len({l["experience"] for l in lignes}),
            "terminees": sum(1 for l in lignes if l.get("etat") == ETAT_TERMINEE)}


def _derniere_ligne_json(p: Path) -> Optional[dict]:
    """La dernière ligne JSON d'un fichier `.jsonl`, sans le relire en entier.

    `erreurs.jsonl` grossit tout au long d'un run : on ne lit que la queue du fichier et
    on remonte jusqu'à une ligne exploitable. Tronquée ou illisible → None, jamais d'exception.
    """
    try:
        with open(p, "rb") as f:
            f.seek(0, os.SEEK_END)
            taille = f.tell()
            f.seek(max(0, taille - 8192))
            queue = f.read().decode("utf-8", errors="ignore")
    except OSError:
        return None
    for ligne in reversed(queue.splitlines()):
        ligne = ligne.strip()
        if ligne:
            try:
                return json.loads(ligne)
            except ValueError:
                return None
    return None


def _dernieres_lignes_json(p: Path, n: int) -> list[dict]:
    """Les `n` dernières lignes exploitables d'un `.jsonl`, de la plus ancienne à la plus récente.

    Même lecture que `_derniere_ligne_json` — la queue du fichier, jamais son entier : les
    journaux d'erreurs grossissent tout au long d'un run. Une ligne illisible est ignorée, pas
    fatale : le fichier est écrit par le conteneur pendant qu'on le lit.
    """
    try:
        with open(p, "rb") as f:
            f.seek(0, os.SEEK_END)
            taille = f.tell()
            f.seek(max(0, taille - 8192))
            queue = f.read().decode("utf-8", errors="ignore")
    except OSError:
        return []
    out = []
    for ligne in queue.splitlines():
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            out.append(json.loads(ligne))
        except ValueError:
            continue  # première ligne tronquée par la lecture partielle, ou écriture en cours
    return out[-n:]


def derniere_erreur_llm() -> Optional[dict]:
    """La dernière tentative LLM échouée, toutes exécutions en cours confondues — une seule.

    Lue en fin de `erreurs.jsonl` de chaque exécution vivante ; la plus récente par
    horodatage l'emporte. None si rien n'a échoué. Sert la ligne unique « dernière erreur
    LLM » de l'onglet Activités en cours, remplacée à chaque nouvelle.
    """
    candidates = []
    for ligne in lister():
        if ligne.get("etat") != ETAT_EN_COURS:
            continue
        derniere = _derniere_ligne_json(Path(ligne["dossier"]) / "erreurs.jsonl")
        if derniere:
            candidates.append({**derniere, "experience": ligne["experience"], "execution": ligne["execution"]})
    if not candidates:
        return None
    return max(candidates, key=lambda e: str(e.get("horodatage") or ""))


# ── composition d'une expérience ─────────────────────────────────────────────

def defauts() -> dict:
    """Valeurs de départ du formulaire — celles de l'exemple, sans rien d'implicite dans le fichier écrit."""
    variantes, active = variantes_prompt()
    return {
        # Pas de « nom » : il se calcule (N1). Ce dictionnaire est aussi la liste des champs
        # retenus dans le brouillon du formulaire (R21) — un nom saisi n'y a plus sa place.
        "population": (populations() or [""])[0], "jeu": (jeux() or [{"nom": ""}])[0]["nom"],
        "variante": active or (variantes[0] if variantes else ""), "decideur_type": "passerelle_distant",
        "modele": next(iter(modeles_par_portee()[1]), "") or next(iter(modeles()), ""), "temperature": 0.0, "graine_decideur": 42, "rejeu_de": "", "artefact": "",
        "mode": "sans_simulateur", "politique": "commune", "date": "2026-03-16", "graine_calendrier": 42,
        "horizon_jours": 1, "memoire": False, "graine_ordre": 42, "graine_tirage": 42, "parallelisme": 8,
        "max_candidats": 6, "attente_max_s": 120, "tolerances": dict(TOLERANCES_PROPOSEES), "derive_de": None,
    }


logger = logging.getLogger(__name__)


def depuis_experience(e: dict) -> dict:
    """Recopie une expérience existante dans les champs du formulaire (E4 : dupliquer, s'inspirer)."""
    d = defauts()
    dec, cal, gab = e.get("decideur") or {}, e.get("calendrier") or {}, e.get("gabarit") or {}
    d.update({
        "population": chemin_hote(str((e.get("population") or {}).get("chemin", d["population"]))),
        "jeu": (e.get("jeu") or {}).get("nom", d["jeu"]), "variante": gab.get("variante") or d["variante"],
        "decideur_type": choix_decideur(dec.get("type", "passerelle"), dec.get("modele"), modeles_par_portee()[0]),
        "modele": dec.get("modele") or d["modele"],
        "temperature": float((dec.get("parametres") or {}).get("temperature", d["temperature"])),
        "reflexion": (dec.get("parametres") or {}).get("thinking_budget", None),
        "niveau_reflexion": (dec.get("parametres") or {}).get("thinking_level", None),
        "graine_decideur": dec.get("graine") if dec.get("graine") is not None else d["graine_decideur"],
        "rejeu_de": dec.get("rejeu_de") or "", "artefact": dec.get("artefact") or "", "mode": e.get("mode", d["mode"]),
        "politique": cal.get("politique", d["politique"]), "date": str(cal.get("date", d["date"])),
        "graine_calendrier": cal.get("graine", d["graine_calendrier"]), "horizon_jours": e.get("horizon_jours", 1),
        "memoire": bool(e.get("memoire", False)), "graine_ordre": e.get("graine_ordre", 42), "graine_tirage": e.get("graine_tirage", 42),
        "parallelisme": (e.get("regroupement") or {}).get("parallelisme", 8), "max_candidats": e.get("max_candidats", 6),
        "attente_max_s": e.get("attente_max_s", 120), "tolerances": e.get("tolerances_horaires") or dict(TOLERANCES_PROPOSEES),
        "derive_de": e.get("nom"),
        # Aucun nom recopié : il se recalcule des paramètres (N1). Une copie qui ne change
        # rien retombe donc sur l'expérience source, et le formulaire le DIT au lieu de la
        # réécrire — c'était l'accident de « Prompt_Minimaliste » le 2026-09-07.
    })
    return d


# Bornes des champs numériques du formulaire : un fichier de reprise hors bornes ferait
# lever `st.number_input`, donc on le ramène dans l'intervalle au lieu de casser la page.
_BORNES = {"temperature": (0.0, 2.0, float), "graine_decideur": (0, 10**9, int), "horizon_jours": (1, 31, int),
           "parallelisme": (1, 64, int), "graine_ordre": (0, 10**9, int), "graine_tirage": (0, 10**9, int),
           "graine_calendrier": (0, 10**9, int), "max_candidats": (1, 20, int), "attente_max_s": (1, 3600, int)}


def _valider_base(brut: dict) -> dict:
    """Un état de formulaire relu, ramené à ce qui existe encore (R21b).

    Chaque valeur inconnue — population effacée, décideur renommé, graine hors bornes —
    revient à son défaut, les autres sont conservées : une reprise partielle vaut mieux
    qu'un formulaire vide.
    """
    base = defauts()
    for cle, valeur in (brut or {}).items():
        if cle not in base:
            continue  # champ disparu du formulaire depuis l'enregistrement
        if cle in _BORNES:
            bas, haut, convertir = _BORNES[cle]
            try:
                valeur = min(haut, max(bas, convertir(valeur)))
            except (TypeError, ValueError):
                continue
        elif cle == "decideur_type":
            if valeur == "passerelle":  # brouillon d'avant la scission distant/local : tranché après la boucle
                valeur = "passerelle_distant"
            elif valeur not in CHOIX_DECIDEUR:
                continue
        elif cle == "politique" and valeur not in POLITIQUES:
            continue
        elif cle == "mode" and valeur not in ("sans_simulateur", "simulateur"):
            continue
        elif cle == "population" and valeur not in populations():
            continue
        elif cle == "date":
            try:
                valeur = date.fromisoformat(str(valeur)).isoformat()
            except (TypeError, ValueError):
                continue
        elif cle == "tolerances" and not isinstance(valeur, dict):
            continue
        elif cle in ("nom", "jeu", "variante", "modele", "rejeu_de") and not isinstance(valeur, str):
            continue
        # Une chaîne qui ne désigne plus rien doit revenir au défaut, pas être conservée :
        # le `selectbox` retomberait sinon sur son premier choix (b0_pristine pour le prompt),
        # substitution silencieuse qui finirait écrite dans `experience.yaml`.
        elif cle == "variante" and valeur not in variantes_prompt()[0]:
            continue
        elif cle == "modele" and valeur not in modeles():
            continue
        elif cle == "jeu" and valeur not in {j["nom"] for j in jeux()}:
            continue
        base[cle] = valeur
    if type_plateforme(base["decideur_type"]) == "passerelle":
        # Un brouillon d'avant la scission — ou un modèle qui a changé de bord depuis — se range
        # du côté qui le sert AUJOURD'HUI : le libellé du sélecteur ne doit pas mentir.
        base["decideur_type"] = choix_decideur("passerelle", base.get("modele"), modeles_par_portee()[0])
    return base


def charger_etat_formulaire() -> dict:
    """Les choix du dernier formulaire, ou {} s'il n'y en a pas (R21).

    Un fichier illisible n'est pas une erreur : `_yaml` rend {} et le formulaire repart
    de ses défauts.
    """
    brut = _yaml(ETAT_FORMULAIRE)
    return _valider_base(brut) if isinstance(brut, dict) and brut else {}


def _empreinte_formulaire(valeurs: dict) -> str:
    """Les champs du formulaire, et eux seuls, sous une forme texte stable : c'est le brouillon (R21)
    et c'est ce qui dit si le formulaire a été retouché depuis une recopie."""
    retenu = {cle: valeurs[cle] for cle in defauts() if cle in valeurs}
    return yaml.safe_dump(retenu, allow_unicode=True, sort_keys=True)


def sauver_etat_formulaire(valeurs: dict) -> bool:
    """Retient les choix du formulaire pour le prochain démarrage. True si le fichier a changé.

    Seuls les champs du formulaire sont retenus — ni le jeu lu sur disque, ni le nom du jeu
    à préparer, qui se redéduisent. Aucune expérience n'est créée : c'est un brouillon (R22).
    """
    texte = _empreinte_formulaire(valeurs)
    try:
        if ETAT_FORMULAIRE.is_file() and ETAT_FORMULAIRE.read_text(encoding="utf-8") == texte:
            return False
        ETAT_FORMULAIRE.parent.mkdir(parents=True, exist_ok=True)
        provisoire = ETAT_FORMULAIRE.with_name(ETAT_FORMULAIRE.name + ".tmp")
        provisoire.write_text(texte, encoding="utf-8")
        os.replace(provisoire, ETAT_FORMULAIRE)
        return True
    except OSError:
        return False  # la mémoire du formulaire est un confort, jamais un blocage


def construire_experience(v: dict) -> dict:
    """Le fichier `experience.yaml` complet (E1 : tous les champs) depuis les valeurs du formulaire."""
    type_ = type_plateforme(v["decideur_type"])  # « distant » et « local » s'écrivent tous deux `passerelle`
    decideur = {"type": type_, "modele": None, "parametres": {}, "rejeu_de": None, "graine": None}
    if type_ == "passerelle":
        params = {"temperature": float(v["temperature"]), "top_p": 1.0, "max_tokens": 4096}
        # Clé ABSENTE quand la réflexion n'est pas pilotée : une clé à None donnerait deux
        # empreintes différentes pour un même réglage, selon qu'on a ouvert le formulaire ou non.
        # Jamais les deux : l'API rend 400 si `thinking_level` et `thinking_budget` coexistent.
        if v.get("niveau_reflexion"):
            params["thinking_level"] = str(v["niveau_reflexion"])
        elif v.get("reflexion") is not None:
            params["thinking_budget"] = int(v["reflexion"])
        decideur.update({"modele": v["modele"], "parametres": params})
    elif type_ == "aleatoire":
        decideur["graine"] = int(v["graine_decideur"])
    elif type_ == "rejeu":
        decideur["rejeu_de"] = v["rejeu_de"] or None
    elif type_ == "modele":
        # Modèle LightGBM comme décideur : artefact vide → version par défaut du dépôt.
        decideur["artefact"] = (v.get("artefact") or "").strip() or None
    exp = {
        "nom": "",  # calculé plus bas, quand tous les paramètres sont posés (N1)
        "population": {"chemin": chemin_conteneur(v["population"])},
        "jeu": {"nom": v["jeu"] or nom_jeu_attendu(v["population"], v["date"])},
        "gabarit": {"categorie": "itinary_multi_agent", "variante": v["variante"] or None},
        "decideur": decideur,
        "mode": v["mode"],
        "calendrier": {"politique": v["politique"], "date": str(v["date"]), "graine": int(v["graine_calendrier"])},
        "horizon_jours": int(v["horizon_jours"]), "memoire": bool(v["memoire"]), "evenements": [],
        "graine_ordre": int(v["graine_ordre"]), "graine_tirage": int(v["graine_tirage"]),
        "regroupement": {"parallelisme": int(v["parallelisme"])},
        "tolerances_horaires": v["tolerances"], "max_candidats": int(v["max_candidats"]), "attente_max_s": int(v["attente_max_s"]),
        "derive_de": v.get("derive_de"),
    }
    attribution, _raison = nommer(exp)
    # Nom vide = le nommage a refusé (modèle non choisi, module absent) : `motifs_indisponibilite`
    # en redonne la raison sous les boutons. Rien n'est inventé pour combler le trou.
    exp["nom"] = attribution.nom if attribution else ""
    return exp


def enregistrer(exp: dict) -> tuple[Path, bool]:
    # Deuxième garde, après celle du formulaire : `enregistrer` est aussi appelée par
    # « Estimer » et « Lancer », et un nom sert à construire un chemin.
    if not MOTIF_NOM.match(str(exp.get("nom", ""))):
        raise ValueError(
            f"nom d'expérience refusé : {exp.get('nom')!r} — ni espace ni séparateur de chemin, "
            f"64 caractères au plus, en commençant par une lettre ou un chiffre, puisqu'il devient "
            f"un dossier et la valeur de EXP= pour make"
        )
    d = DOSSIER / exp["nom"]
    d.mkdir(parents=True, exist_ok=True)
    chemin = d / "experience.yaml"
    contenu = yaml.safe_dump(exp, allow_unicode=True, sort_keys=False)
    if chemin.is_file() and chemin.read_text(encoding="utf-8") == contenu:
        return chemin, False  # rien n'a bougé : ne pas l'annoncer comme un enregistrement
    provisoire = chemin.with_name("experience.yaml.tmp")
    provisoire.write_text(contenu, encoding="utf-8")
    os.replace(provisoire, chemin)
    return chemin, True


def signaler(dossier_execution: Path, fichier: str) -> None:
    """PAUSE / STOP : le runner (dans le conteneur, même dossier monté) l'honore en quelques
    secondes — il laisse un délai de grâce (`EXP_PAUSE_GRACE_S`, 15 s) aux sollicitations déjà
    en vol, puis les abandonne. Le fichier reste le retour immédiat pour l'affichage."""
    (Path(dossier_execution) / fichier).touch()


def supprimer_experience(nom: str) -> Path:
    """Efface définitivement `data/experiences/<nom>/` — la définition ET ses exécutions archivées.

    Irréversible : les décisions déjà payées disparaissent avec l'archive. Refuse tant qu'une
    exécution de l'expérience écrit encore (runner vivant) : détruire ses fichiers sous ses pieds
    la ferait échouer de façon illisible. Rend le dossier supprimé.

    N'est PLUS branchée au tableau de bord : le 🗑 du registre retire la ligne (`masquer`) sans
    toucher au disque, parce qu'un clic y effaçait des heures de calcul sans retour possible.
    Reste l'effacement volontaire, appelé depuis un script ou une console.
    """
    dossier = next((p for p in DOSSIER.iterdir()
                    if (p / "experience.yaml").is_file()
                    and _yaml(p / "experience.yaml").get("nom", p.name) == nom), None) if DOSSIER.is_dir() else None
    if dossier is None:
        raise ValueError(f"« {nom} » : aucune expérience de ce nom à supprimer")
    vivantes = [l["execution"] for l in lister()
                if l["experience"] == nom and l.get("etat") == ETAT_EN_COURS
                and execution_vivante(l["dossier"])]
    if vivantes:
        raise ValueError(f"« {nom} » a une exécution encore active ({', '.join(vivantes)}) : "
                         "mettez-la en pause ou attendez sa fin avant de supprimer")
    import shutil

    shutil.rmtree(dossier)
    return dossier


# ── rendu Streamlit ──────────────────────────────────────────────────────────

def _qui(e: dict) -> str:
    """« antigravity / », « google / », ou rien du tout.

    Rien du tout sur un décideur qui ne sollicite aucun LLM : un préfixe « — / » n'apprendrait
    rien et ferait croire à une information manquante.
    """
    f = str(e.get("fournisseur") or "").strip()
    return f"{f} / " if f and f != SANS_FOURNISSEUR else ""


def rendre_activites(st, act: dict, *, compact: bool = False) -> None:
    """Les barres d'avancement de ce qui tourne.

    Même présentation dans la vue d'ensemble et dans l'onglet Activités en cours : deux
    rendus différents du même état finiraient par se contredire.
    """
    executions, en_preparation = act["executions"], act["jeux"]
    if not executions and not en_preparation:
        st.markdown(f"⚪ Aucune expérience en cours · **{act['definies']}** définie(s) · "
                    f"**{act['terminees']}** exécution(s) terminée(s)")
        return
    for index, e in enumerate(executions):
        texte = (f"🧪 **{_qui(e)}{e['experience']} / {e['execution']}** — {_n(e['faits'])} / {_n(e['total'])} déplacements"
                 + (f" · {e['pourcent']:.0f} %" if e["pourcent"] is not None else ""))
        if not compact:
            texte += f" · {_n(e['personnes_terminees'])} / {_n(e['personnes'])} personnes"
        if isinstance(e.get("reste_s"), (int, float)):
            texte += f" · reste ≈ {_duree(e['reste_s'])}"
        # Une tentative réessayée est une ATTENTE : la plateforme ne saute aucun déplacement.
        # L'annoncer « erreur » faisait lire 128 erreurs sur un run qui n'en avait aucune.
        if e.get("attentes"):
            détail = ", ".join(sorted(e.get("attentes_par_type") or {})) or "transitoires"
            texte += f" · {_n(e['attentes'])} attentes ({détail})"
        if e.get("erreurs"):
            texte += f" · ⚠ {_n(e['erreurs'])} ÉCHECS DÉFINITIFS"
        # Ce qui est demandé mais pas encore effectif, et ce qui n'avance plus : le chien de
        # garde met en pause tout seul au-delà du seuil, autant voir venir.
        if isinstance(e.get("arret_demande"), (int, float)):
            texte += f" · ⏹ arrêt demandé il y a {int(e['arret_demande'])} s, en cours"
        elif isinstance(e.get("pause_demandee"), (int, float)):
            texte += f" · ⏸ pause demandée il y a {int(e['pause_demandee'])} s, en cours"
        immobile = e.get("immobile_depuis_s")
        if isinstance(immobile, (int, float)) and immobile >= SEUIL_IMMOBILE_VISIBLE_S:
            texte += f" · ⏳ immobile depuis {int(immobile // 60)} min"
        age = e.get("age_s")
        if isinstance(age, (int, float)) and age > FRAICHEUR_EXECUTION_S:
            texte += f" · ⚠ plus rien d'écrit depuis {int(age // 60)} min"
        elif isinstance(age, (int, float)):
            texte += f" · écrit il y a {int(age)} s" if compact else f" · progression écrite il y a {int(age)} s"
        st.progress(min(1.0, (e["pourcent"] or 0) / 100), text=texte)
        if not compact:
            _boutons_arret(st, e, index)
    for j in en_preparation:
        _ligne_jeu(st, j, compact=compact)


def _boutons_arret(st, e: dict, index: int, prefixe: str = "act") -> None:
    """Pause et Arrêter sur une exécution en cours, avec la différence écrite.

    Elle n'est pas cosmétique : la pause laisse l'exécution reprenable, l'arrêt **scelle**
    l'archive (E19) et la ferme pour toujours. Confondre les deux a coûté 209 décisions le
    2026-09-07 ; la case de confirmation qui gardait l'arrêt a été retirée le 2026-09-09 à la
    demande de l'auteur, la garde restante est donc le libellé et la légende sous les boutons.

    Les deux boutons disparaissent sur une exécution qui n'écrit plus : sur un runner tué,
    une sentinelle n'interrompt rien et ne fait que piéger la reprise suivante.
    """
    cle = f"{prefixe}-{e['experience']}-{e['execution']}-{index}"
    deja = isinstance(e.get("pause_demandee"), (int, float)) or isinstance(e.get("arret_demande"), (int, float))
    # Interrompre n'a de sens que sur une exécution qui écrit encore. `etat.json` dit « en
    # cours » pour toujours quand le runner a été tué net (conteneur arrêté) : déposer
    # une sentinelle dans ce cadavre ne pause rien, et elle attend la reprise suivante pour
    # la saboter — un PAUSE la remet en pause aussitôt, un STOP scelle l'archive. C'est ce
    # qui a coûté 209 décisions le 2026-09-07 puis bloqué une reprise le 2026-09-08.
    vivante = execution_vivante(e["dossier"])
    if not vivante:
        st.caption(
            "⏸/⏹ retirés : cette exécution n'écrit plus (runner tué), il n'y a rien à "
            "interrompre. Reprenez-la avec **▶ Reprendre** — ses décisions acquises sont "
            "conservées et ne seront pas repayées."
        )
        return
    pause, arret = st.columns([1, 1], vertical_alignment="center")
    if pause.button("⏸ Pause" if not deja else "⏸ Pause demandée", key=f"pause-{cle}", width="stretch",
                    disabled=deja,
                    help="Effective en quelques secondes : les sollicitations encore en vol sont "
                         "abandonnées, leurs déplacements non archivés et redemandés à la reprise. "
                         "L'exécution reste REPRENABLE : l'archive n'est pas scellée, les décisions "
                         "acquises ne seront pas repayées."):
        signaler(Path(e["dossier"]), "PAUSE")
        st.toast("Pause demandée — effective en quelques secondes")
    if arret.button("⏹ Arrêter", key=f"stop-{cle}", width="stretch",
                    help="Scelle l'archive en quelques secondes : le résultat partiel reste "
                         "exploitable, mais l'exécution ne peut plus être reprise. Pour la "
                         "poursuivre plus tard, utilisez la pause."):
        signaler(Path(e["dossier"]), "STOP")
        st.toast("Arrêt demandé — le résultat partiel restera exploitable, l'archive sera scellée")
    st.caption("⏸ **Pause** laisse l'exécution reprenable — ses décisions acquises ne seront pas "
               "repayées. ⏹ **Arrêter** scelle l'archive : le résultat partiel reste exploitable, "
               "mais l'exécution ne pourra plus être reprise.")


def services_requis_de(nom_experience: str) -> list[str]:
    """Les services dont l'expérience nommée a besoin, lus sur sa définition.

    Sert à passer `REQUIS=` à `make` : le lancement démarre lui-même ce qui manque, il faut
    donc lui dire quoi. Définition introuvable → le contrôleur seul, où la plateforme tourne :
    c'est le plancher, jamais rien de moins.
    """
    exp = experiences().get(nom_experience)
    return services_requis(exp) if exp else [SERVICE_PLATEFORME]


def rendre_reprenables(st, act: dict, *, lancer: Optional[Callable[[str, dict], None]] = None) -> None:
    """Les exécutions arrêtées et leur cause, chacune avec son bouton de reprise.

    Elles ne s'affichaient nulle part dans « Activités en cours » : une exécution qui s'arrête
    — quota épuisé, passerelle injoignable, PC éteint, pause — disparaissait de l'onglet à la
    seconde même, et il fallait aller la chercher dans le registre de l'onglet Expériences.
    """
    lignes, obsoletes = act["lignes"], act["obsoletes"]
    if not lignes:
        st.markdown("⚪ Aucune exécution arrêtée à relancer"
                    + (f" · **{obsoletes}** obsolète(s) laissée(s) de côté" if obsoletes else ""))
        return
    st.markdown(f"**⏹ {len(lignes)} exécution(s) arrêtée(s), reprenable(s)**")
    for e in lignes:
        cause = e["cause"]
        texte = (f"{cause['icone']} **{_qui(e)}{e['experience']} / {e['execution']}** — {cause['libelle']}"
                 f" · {_n(e['decisions'])} décision(s) déjà archivée(s)")
        if e.get("pourcent") is not None:
            texte += f" · {e['pourcent']:.0f} % de {_n(e['total'])} déplacements"
        gauche, bouton = st.columns([5, 1], vertical_alignment="center")
        gauche.markdown(texte)
        if cause["detail"]:
            gauche.caption(cause["detail"])
        if bouton.button("▶ Reprendre", key=f"reprendre-{e['experience']}-{e['execution']}",
                         width="stretch", disabled=not lancer,
                         help="`make experience-reprendre` : poursuit CETTE exécution sans "
                              "redemander une décision déjà acquise — elles ne seront pas "
                              "repayées. Les services nécessaires sont démarrés d'abord."):
            lancer("experience-reprendre",
                   {"EXP": e["experience"], "REQUIS": " ".join(services_requis_de(e["experience"]))})
            st.toast(f"Reprise de « {e['experience']} / {e['execution']} » lancée")
    if obsoletes:
        st.caption(f"🙈 {obsoletes} exécution(s) arrêtée(s) non listée(s) : une exécution plus "
                   "récente de la même expérience existe, et la reprise ne porte que sur la "
                   "dernière. Elles sont marquées « obsolète » dans le registre de 🧪 Expériences.")


def _ligne_jeu(st, j: dict, *, compact: bool = False) -> None:
    """Un jeu en préparation : sa barre, ou le simple constat qu'il vient d'être ouvert."""
    if not j["mesure"]:
        st.markdown(f"🔥 « {j['nom']} » en préparation (pas encore de progression)")
        return
    texte = (f"🔥 **warm-up « {j['nom']} »** — {_n(j['faits'])} / {_n(j['total'])} déplacements"
             + (f" · {j['pourcent']:.0f} %" if j["pourcent"] is not None else ""))
    if j.get("sans_proposition"):
        texte += f" · {_n(j['sans_proposition'])} sans proposition"
    if j.get("erreurs"):
        texte += f" · {_n(j['erreurs'])} erreurs"
    if isinstance(j.get("reste_s"), (int, float)):
        texte += f" · reste ≈ {_duree(j['reste_s'])}"
    age = j.get("age_s")
    if isinstance(age, (int, float)) and age > FRAICHEUR_CONSTRUCTION_S:
        # Un warm-up dont le conteneur a été tué garde `clos: false` : sans ce repère, sa
        # dernière barre resterait affichée indéfiniment (R24, moitié « jeux »).
        texte += f" · ⚠ plus rien d'écrit depuis {int(age // 60)} min"
    elif isinstance(age, (int, float)):
        texte += f" · écrit il y a {int(age)} s" if compact else f" · progression écrite il y a {int(age)} s"
    st.progress(min(1.0, (j["pourcent"] or 0) / 100), text=texte)


def _suivi_des_services(st, requis: list[str]) -> None:
    """Le bloc des services : ce qui tourne, ce qui manque — et plus aucun bouton.

    Le démarrage n'est plus une action de l'utilisateur : `make experience-lancer` et `make
    jeu` garantissent eux-mêmes les services dont ils ont besoin (cible `services-pretes`,
    `docker compose up -d --wait`), depuis le tableau de bord comme depuis un terminal. Un
    bouton « démarrer » n'était qu'une étape à ne pas oublier avant de cliquer sur « Lancer ».

    Le bloc reste, en lecture seule : savoir AVANT de lancer que six conteneurs sont éteints,
    c'est savoir que le lancement commencera par plusieurs minutes de chargement de graphes
    OTP/OSMnx. Il se rafraîchit seul tant qu'il en manque un, sans quoi le bandeau « le
    contrôleur ne tourne pas » survivrait à son démarrage : il n'est recalculé qu'à la
    prochaine réexécution du script, donc au prochain clic, et le cache de 15 s peut même
    rendre la valeur périmée à ce moment-là. Dès que l'ensemble des services manquants change,
    on vide le cache et on recharge la page entière : le bandeau du haut est calculé là.
    """
    cle = "_services_signature"
    lance_a = float(st.session_state.get("_services_lance_a", 0))

    def dessiner() -> None:
        services = _services_cache(st, ttl_s=DELAI_SONDE_SERVICES_S)
        manquants = [s for s in requis if services is not None and s not in services]
        signature = (None if services is None else tuple(manquants))
        connue = st.session_state.get(cle, "jamais")
        st.session_state[cle] = signature
        if connue != "jamais" and connue != signature:
            st.session_state.pop("_services", None)  # le bandeau du haut doit relire, pas relire le cache
            st.rerun(scope="app")

        with st.container(border=True):
            if services is None:
                st.markdown("**🐳 Services nécessaires** — état inconnu (docker injoignable) : "
                            + " · ".join(f"`{s}`" for s in requis))
            else:
                st.markdown("**🐳 Services nécessaires** — "
                            + " · ".join(f"{'🟢' if s in services else '⚪'} `{s}`" for s in requis))
            if manquants:
                st.caption(f"{len(manquants)} service(s) à démarrer — **« ▶ Lancer » les démarre "
                           f"d'abord** (`docker compose up -d --no-recreate --wait` : rien de ce qui "
                           f"tourne n'est recréé) puis enchaîne. `controller` "
                           f"attend `api`, `otp1-3`, `eqasim` et `osmnx1` en bonne santé : comptez "
                           f"plusieurs minutes de chargement des graphes, visibles dans le journal "
                           f"du lancement.")
            elif services is None:
                st.caption("Le démon Docker ne répond pas : ni cet état ni un lancement ne sont "
                           "possibles. Ouvrez Docker Desktop.")
            elif (time.time() - lance_a) < DELAI_SURVEILLANCE_S:
                st.caption("Tous les services nécessaires tournent.")

    services_vus = st.session_state.get("_services")
    manque_maintenant = bool(services_vus and services_vus[1] is not None
                             and [s for s in requis if s not in services_vus[1]])
    surveiller = (manque_maintenant or services_vus is None
                  or (time.time() - lance_a) < DELAI_SURVEILLANCE_S)
    st.fragment(run_every="5s" if surveiller else None)(dessiner)()


def modele_local_de(exp: dict) -> Optional[str]:
    """Le modèle de l'expérience s'il est servi par LM Studio (providers.yaml), sinon None."""
    dec = exp.get("decideur") or {}
    if dec.get("type") != "passerelle" or not dec.get("modele"):
        return None
    return str(dec["modele"]) if str(dec["modele"]) in modeles_par_portee()[0] else None


def _suivi_lmstudio(st, modele: str, lancer) -> None:
    """Le bloc du modèle local : chargé ou non, avec quel contexte, et les boutons qui y remédient.

    Même contrat que le bloc des services : il se rafraîchit seul tant que le modèle n'est pas
    prêt, et la page se recharge dès que l'état change, pour que « Lancer » se dégrise sans clic.
    Le 2026-09-08, une expérience a tourné sept minutes sans une décision parce que rien ne
    disait que le modèle n'était pas chargé, puis qu'il l'était avec 4 096 jetons de contexte.
    """
    cle = "_lmstudio_signature"

    def dessiner() -> None:
        etat = _etat_lmstudio_cache(st, ttl_s=DELAI_SONDE_SERVICES_S)
        d = lmstudio.diagnostic(modele, etat)
        signature = (d.pret, d.motif, d.contexte, tuple(d.autres_charges))
        connue = st.session_state.get(cle, "jamais")
        st.session_state[cle] = signature
        if connue != "jamais" and connue != signature:
            st.rerun(scope="app")  # « Lancer » et son motif sont calculés ailleurs : la page entière doit relire
        with st.container(border=True):
            fiche = " · ".join(str(x) for x in (d.params, d.quant or d.format) if x)
            st.markdown(f"**🖥️ Modèle local (LM Studio)** — `{modele}`" + (f" ({fiche})" if fiche else "") + f" : {d.etat_court}")
            if d.motif:
                st.caption(d.motif)
            if d.autres_charges:
                st.caption("Aussi en mémoire : " + ", ".join(f"`{a}`" for a in d.autres_charges)
                           + " — deux modèles chargés peuvent saturer la mémoire de la machine.")
            c_charger, c_decharger = st.columns(2)
            if not d.pret and d.source:
                ctx = f"{lmstudio.CTX_CHARGEMENT:,}".replace(",", " ")
                libelle = (f"🔄 Recharger « {modele} » avec {ctx} jetons" if d.recharger
                           else f"⬇️ Charger « {modele} » ({ctx} jetons de contexte)")
                if c_charger.button(libelle, disabled=not lancer, width="stretch", type="primary", key="lmstudio-charger",
                                    help="`make lmstudio-charger` : charge le modèle dans LM Studio avec un contexte suffisant pour "
                                         "deux agents par requête ; une à trois minutes, suivi dans 📟 Activités en cours"):
                    lancer("lmstudio-charger", lmstudio.variables_chargement(modele, d.source, recharger=d.recharger))
                    st.toast("Chargement dans LM Studio — suivi ici et dans 📟 Activités en cours")
                    st.rerun(scope="app")
            for i, autre in enumerate(d.autres_charges[:2]):
                if c_decharger.button(f"⏏️ Décharger « {autre} »", disabled=not lancer, width="stretch", key=f"lmstudio-decharger-{i}",
                                      help="`make lmstudio-decharger` : rend la mémoire de ce modèle"):
                    lancer("lmstudio-decharger", {"MODELE": autre})
                    st.toast(f"Déchargement de {autre} — suivi dans 📟 Activités en cours")
                    st.rerun(scope="app")
            if not lancer:
                st.caption("Actions indisponibles : le registre de lancements est absent.")

    connue = st.session_state.get(cle)
    pret = isinstance(connue, tuple) and connue[0] is True
    st.fragment(run_every=None if pret else "5s")(dessiner)()


def _panneau_statuts(st, toutes: list[dict]) -> None:
    """Compte et explique les expériences retirées du tableau par leur statut.

    Le retrait doit rester lisible : une expérience qui disparaît sans motif laisse croire à
    une perte de données, alors que tout est intact sur le disque. On donne donc le compte, le
    détail au dépli, et la possibilité de tout revoir.
    """
    retirees = [l for l in toutes if masquee(l)]
    if not retirees:
        return
    par_exp: dict[str, dict] = {}
    for l in retirees:
        par_exp.setdefault(l["experience"], l)
    inv = [l for l in par_exp.values() if l.get("statut") == "invalide"]
    arc = [l for l in par_exp.values() if l.get("statut") == "archivee"]
    resume = " · ".join(
        p for p in (f"{len(inv)} invalidée(s)" if inv else "", f"{len(arc)} archivée(s)" if arc else "")
        if p
    )
    with st.expander(f"🗄 {len(par_exp)} expérience(s) hors tableau — {resume}"):
        st.caption("Retirées de la vue, pas du disque : définitions, exécutions, traces et scores "
                   "sont intacts et vérifiables. `make registre TOUT=1` les liste en ligne de commande.")
        for l in sorted(par_exp.values(), key=lambda x: (x.get("statut") or "", x["experience"])):
            marque = "⛔" if l.get("statut") == "invalide" else "📦"
            st.markdown(f"{marque} **{l['experience']}** — {l.get('statut_motif') or 'sans motif consigné'}")


def _panneau_masques(st, *, vide: bool = False) -> None:
    """Ce qui a été retiré se compte et se rend — sinon le retrait serait une suppression déguisée.

    Se rend AUSSI quand il ne reste plus rien à afficher : la dernière ligne retirée emporterait
    autrement le seul bouton capable de la rendre.
    """
    caches = masques()
    if not caches:
        return
    c_txt, c_btn = st.columns([3, 1])
    c_txt.caption(f"🙈 {len(caches)} entrée(s) retirée(s) du tableau — les définitions et archives "
                  "correspondantes sont intactes sur le disque."
                  + (" Rendez-les pour les revoir." if vide else ""))
    if c_btn.button("↩ Tout réafficher", width="stretch", key="act-demasquer"):
        n = demasquer_tout()
        st.toast(f"{n} entrée(s) rendue(s) au tableau")
        st.rerun()


def _suivi_du_registre(st, pd) -> None:
    """Le registre et les exécutions en cours, vivants tant que quelque chose tourne.

    Sans cela une exécution qui se termine reste affichée « en cours » jusqu'au prochain clic :
    vu le 2026-09-07 sur un run terminé à 99,8 % de couverture que la page ignorait encore.
    Le fragment ne bat que si une exécution tourne, pour ne pas gêner la navigation dans le
    détail, et il recharge la page une fois quand un état change — les avertissements du
    formulaire et le bouton « Reprendre » sont calculés ailleurs.
    """
    cle = "_registre_signature"

    def dessiner() -> None:
        # Filtré ICI et pas seulement à l'appelant : c'est ce tableau qui s'affiche. Le
        # `lister()` de « Mes expériences » ne sert qu'au test de vacuité — filtrer là-bas
        # laissait les archivées et les invalidées dans le tableau, exactement ce que le
        # retrait devait éviter.
        lignes = [l for l in lister() if not masquee(l)]
        signature = tuple(sorted(
            (l.get("experience") or "", l.get("execution") or "", l.get("etat") or "") for l in lignes))
        connue = st.session_state.get(cle)
        st.session_state[cle] = signature
        if connue is not None and connue != signature:
            st.rerun(scope="app")

        _panneau_formule(st)

        df = pd.DataFrame(lignes)
        # Icône « résultats » : 📊 sur les lignes scorées ; cliquer la ligne ouvre le
        # détail par sous-catégorie juste en dessous (plus de menu séparé).
        if "composite_emd" in df.columns:
            # pd.notna, pas `is not None` : une valeur absente devient NaN dans le DataFrame,
            # et `NaN is not None` serait vrai → l'icône apparaîtrait sur les lignes non scorées.
            df["scores"] = ["📊" if pd.notna(v) else "" for v in df["composite_emd"]]
        # `date` retirée : c'est `cree_le` de l'exécution, soit l'horodatage que `execution`
        # porte déjà dans son nom (`2026-09-09_13_05_09`). Deux colonnes pour une information,
        # et le nom de dossier est l'identifiant — c'est lui qui reste.
        colonnes = [c for c in ("scores", "experience", "execution", "etat", "decideur", "fournisseur", "prompt",
                                "jeu", "jeu_etat", "mode", "couverture", "composite_emd",
                                "composite_l1", "formule")
                    if c in df.columns]
        triables = [c for c in colonnes if c != "scores"]
        c1, c2, c3 = st.columns([2, 1, 1], vertical_alignment="bottom")
        filtre = c1.text_input("Filtrer (sous-chaîne sur toutes les colonnes)", "", key="exp-filtre")
        # Tri par défaut sur `execution` : son nom est l'horodatage, l'ordre lexicographique
        # est donc l'ordre chronologique — ce que `date` donnait avant son retrait.
        tri = c2.selectbox("Trier par", triables,
                           index=triables.index("execution") if "execution" in triables else 0,
                           key="exp-tri")
        # Un filtre de VUE, décoché d'un clic — sans rapport avec « 🗑 Retirer du tableau »,
        # qui écrit dans `.masques.json`. Le panneau de progression plus bas parcourt les
        # lignes NON filtrées : cocher cette case ne peut pas faire perdre de vue une
        # exécution qui tourne, ni ses boutons Pause / Arrêter — une exécution qui tourne est
        # de toute façon la dernière de son expérience, donc jamais obsolète.
        masquer_obsoletes = c3.checkbox(
            "Masquer les obsolètes", value=True, key="exp-obsoletes",
            help="retire les exécutions qu'une plus récente de la même expérience a "
                 "remplacées ; la dernière exécution de chaque expérience reste toujours "
                 "visible. Le nombre de lignes masquées est dit sous le tableau.")
        df = df.sort_values(tri, ascending=False, na_position="last").reset_index(drop=True)
        vue = df[colonnes].copy()
        # Obsolète : suffixe sur la colonne `etat`, avec ce que cela coûte. Une exécution
        # obsolète MENÉE À TERME garde un résultat complet et comparable — seul le libellé
        # change ; une obsolète partielle, elle, ne sera jamais reprise (la reprise ne porte
        # que sur la dernière exécution). Confondre les deux ferait passer un résultat
        # exploitable pour un déchet.
        if "etat" in vue.columns and "obsolete" in df.columns:
            vue["etat"] = [
                (f"{e} · obsolète ({'résultat complet' if est_terminee(l) else 'partielle'})"
                 if l.get("obsolete") else e)
                for e, l in zip(df["etat"], df.to_dict("records"))
            ]
        # Formule périmée : suffixe visible ⚠ sur la colonne formule (R7).
        if "formule" in vue.columns and "formule_perimee" in df.columns:
            vue["formule"] = [
                (f"{f} ⚠périmée" if p else f) if f else "—"
                for f, p in zip(df["formule"], df["formule_perimee"])
            ]
        if filtre:
            garde = vue.astype(str).apply(lambda col: col.str.contains(filtre, case=False, na=False)).any(axis=1)
            vue, df = vue[garde].reset_index(drop=True), df[garde].reset_index(drop=True)
        masquees = 0
        if masquer_obsoletes and len(df):
            garde = [not l.get("obsolete") for l in df.to_dict("records")]
            masquees = len(garde) - sum(garde)
            vue, df = vue[garde].reset_index(drop=True), df[garde].reset_index(drop=True)
        if masquees:
            # Rien ne disparaît en silence, même derrière un filtre de vue : le nombre se dit,
            # comme le fait le panneau des entrées retirées.
            st.caption(f"🙈 {masquees} ligne(s) obsolète(s) masquée(s) par la case "
                       "« Masquer les obsolètes » — décochez-la pour les revoir.")
        st.caption("📊 = résultats disponibles : cliquez la ligne pour voir le détail par "
                   "sous-catégorie. La couverture accompagne chaque score ; une exécution non "
                   "scorée affiche « — », jamais 0.")
        event = st.dataframe(vue, width="stretch", hide_index=True,
                             on_select="rerun", selection_mode="single-row", key="exp-table")

        # Les actions portent sur la LIGNE COCHÉE du tableau (plus de sélecteur séparé), et
        # se dessinent AU-DESSUS du détail par sous-catégorie : on agit sur ce qu'on regarde.
        rows = _lignes_selectionnees(event, len(df))
        if rows:
            ligne_choisie = df.iloc[rows[0]].to_dict()
            choix = ligne_choisie.get("experience")
            # Une exécution absente devient NaN dans le DataFrame : on ne garde que du texte,
            # sinon la ligne « definie » se retirerait sous la clé « nan » au lieu de « rien ».
            execution_choisie = ligne_choisie.get("execution")
            execution_choisie = execution_choisie if isinstance(execution_choisie, str) else None
            lancer_fn = st.session_state.get("_lancer")
            reprenable = any(est_reprenable(l) for l in lignes
                             if l["experience"] == choix and l.get("execution"))
            st.markdown(f"**Actions sur « {choix} »**")
            a1, a2, a3, a4 = st.columns(4)
            if a1.button("🔁 Rejouer", disabled=not lancer_fn, width="stretch", key="act-rejouer",
                         help="nouvelle exécution de la même expérience (jamais d'écrasure)"):
                lancer_fn("experience-lancer",
                          {"EXP": choix, "REQUIS": " ".join(services_requis_de(choix))})
                st.toast(f"Nouvelle exécution de « {choix} » lancée")
            if a2.button("▶ Reprendre", disabled=not (lancer_fn and reprenable), width="stretch", key="act-reprendre",
                         help="reprend sans redemander une décision acquise : en pause, épuisée, ou runner tué"):
                lancer_fn("experience-reprendre",
                          {"EXP": choix, "REQUIS": " ".join(services_requis_de(choix))})
                st.toast(f"Reprise de « {choix} » lancée")
            if a3.button("📋 Dupliquer", width="stretch", key="act-dupliquer",
                         help="recopie ses réglages dans le formulaire ci-dessus ; changez ce que vous voulez"):
                exps = experiences()
                if choix in exps:
                    st.session_state["exp_base"] = depuis_experience(exps[choix])
                    st.session_state["exp_version"] = int(st.session_state.get("exp_version", 0)) + 1
                    st.rerun()
            # UN clic, et le disque n'est pas touché : la ligne sort du tableau, l'archive reste
            # là où elle est. Le retrait se restitue plus bas ; la suppression définitive, elle,
            # ne se fait plus d'ici (`supprimer_experience` reste appelable en console).
            if a4.button("🗑 Retirer du tableau", width="stretch", key="act-masquer",
                         help="retire cette seule ligne du registre ; la définition et les "
                              "exécutions archivées restent intactes sur le disque"):
                try:
                    masquer(choix, execution_choisie)
                    st.toast(f"« {choix}"
                             + (f" / {execution_choisie}" if execution_choisie else "")
                             + " » retirée du tableau (données conservées)")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            if not reprenable:
                st.caption("Aucune exécution reprenable pour cette expérience : ni en pause, ni "
                           "épuisée, ni interrompue, ni abandonnée en cours — et une exécution "
                           "obsolète ne se reprend pas, la reprise ne portant que sur la dernière.")
        else:
            st.caption("Cliquez une ligne du tableau pour agir dessus (rejouer, reprendre, dupliquer) ou voir son détail.")

        _panneau_masques(st)

        # Les contrôles ⏸ Pause / ⏹ Arrêter d'une exécution EN COURS sont eux aussi remontés
        # au-dessus du détail par sous-catégorie. Ils portent sur l'exécution qui tourne (arrêter
        # n'a de sens que sur elle) : quand la ligne cochée est justement celle-ci, tout est réuni.
        for index, l in enumerate(l for l in lignes if l.get("etat") == ETAT_EN_COURS):
            p = progression(Path(l["dossier"]))
            st.markdown(f"**⏳ {l['experience']} / {l['execution']}** — en cours")
            if p:
                st.progress(min(1.0, (p.get("pourcent") or 0) / 100),
                            text=f"{p.get('faits')} / {p.get('attendus')} déplacements · "
                                 f"{p.get('personnes_terminees')} / {p.get('personnes')} personnes · "
                                 f"{p.get('ecoule_s', 0):.0f} s écoulées"
                                 + (f" · reste ≈ {_duree(p['reste_s'])}" if p.get("reste_s") is not None else "")
                                 + f" · {p.get('sollicitations')} sollicitations"
                                 + (f" · {p.get('attentes')} attentes" if p.get("attentes") else ""))
            _boutons_arret(st, l, index, prefixe="reg")

        _apercu_ligne_selectionnee(st, event, df)

    vivant = any(l.get("etat") == ETAT_EN_COURS for l in lister())
    st.fragment(run_every="5s" if vivant else None)(dessiner)()


def _suivi_des_jeux(st, pop_nom: str) -> None:
    """Le warm-up de cette population, rafraîchi seul, la page rechargée quand la liste bouge (R18).

    Sans cela, un warm-up qui se termine pendant que la page est ouverte laisse à l'écran
    « aucun jeu préparé » et un bouton de construction actif — ce qui s'est produit le
    2026-09-06 : jeu clos à 21 h 36, formulaire resté sur l'état de 20 h 33.
    """
    cle = f"_jeux_signature_{pop_nom}"
    surveiller = bool(jeux_en_preparation(pop_nom)) or \
        (time.time() - float(st.session_state.get("_warmup_lance_a", 0))) < DELAI_SURVEILLANCE_S

    def dessiner() -> None:
        courants = jeux_de(pop_nom)
        signature = tuple(sorted((j["nom"], bool(j["clos"])) for j in courants))
        connue = st.session_state.get(cle)
        st.session_state[cle] = signature
        if connue is not None and connue != signature:
            st.rerun(scope="app")  # un jeu est apparu, ou vient d'être clos : la page doit le voir
        for j in jeux_en_preparation(pop_nom):
            _ligne_jeu(st, j)

    st.fragment(run_every="5s" if surveiller else None)(dessiner)()


def _formulaire(st, base: dict, version: int) -> dict:
    k = lambda nom: f"exp-{version}-{nom}"  # noqa: E731 — clés remises à neuf à chaque « s'inspirer de »
    v = dict(base)
    c1, c2 = st.columns([2, 3])
    # Le nom ne se saisit plus : il se calcule (N1). La place est réservée ici et remplie à la
    # FIN du formulaire, quand modèle, température, calendrier et mode sont connus — c'est
    # d'eux que le nom est fait.
    zone_nom = c1.empty()
    pops = populations()
    v["population"] = c2.selectbox("Population", pops, index=pops.index(base["population"]) if base["population"] in pops else 0, key=k("pop")) if pops else c2.text_input("Population", value=base["population"], key=k("pop"))
    pop_nom = Path(v["population"]).name.replace(".json", "")
    pour_cette_pop = jeux_de(pop_nom)
    noms_jeux = [j["nom"] for j in pour_cette_pop]
    c1, c2 = st.columns([3, 2])
    if noms_jeux:
        v["jeu"] = c1.selectbox("Jeu de déplacements de cette population", noms_jeux,
                                index=noms_jeux.index(base["jeu"]) if base["jeu"] in noms_jeux else 0, key=k("jeu"),
                                format_func=lambda n: next((libelle_jeu(j) for j in pour_cette_pop if j["nom"] == n), n))
        v["sans_jeu"] = False
    else:
        v["jeu"] = ""
        # Un drapeau, pas un nom : le nom se calcule plus bas, quand la date CHOISIE est
        # connue. Le calculer ici le figeait sur la date d'ouverture du formulaire.
        v["sans_jeu"] = True
        c1.warning(f"Aucun jeu de déplacements préparé pour « {pop_nom} » : il faut d'abord le construire (warm-up), "
                   f"c'est long mais ça se fait une fois et ça reprend si on l'interrompt. "
                   f"L'expérience, elle, peut être enregistrée dès maintenant : elle nommera le jeu qu'elle attend.")
    v["jeu_courant"] = next((j for j in pour_cette_pop if j["nom"] == v["jeu"]), None)
    _suivi_des_jeux(st, pop_nom)
    variantes, active = variantes_prompt()
    textes = prompts_textes()
    c1, c2, c3 = st.columns(3)
    if variantes:
        def _lib(x: str) -> str:
            t = textes.get(x) or {}
            mots = t.get("mots")
            return f"{x}{' · actif' if x == active else ''}{' · minimaliste' if x == 'b_min' else ''}" + (f" · {mots} mots" if mots else "")
        v["variante"] = c1.selectbox("Prompt système", variantes, index=variantes.index(base["variante"]) if base["variante"] in variantes else 0,
                                     key=k("variante"), format_func=_lib, help="les variantes de `prompts:` dans mobility_llm/prompts/prompts.yaml")
    else:
        v["variante"] = c1.text_input("Prompt système", value=base["variante"], key=k("variante"))
    v["decideur_type"] = c2.selectbox("Décideur", CHOIX_DECIDEUR,
                                      index=CHOIX_DECIDEUR.index(base["decideur_type"]) if base["decideur_type"] in CHOIX_DECIDEUR else 0,
                                      key=k("dtype"), format_func=lambda x: LIBELLES_DECIDEUR.get(x, x),
                                      help="« distant » : un fournisseur d'API (quota journalier, clés) ; « local » : un modèle servi par "
                                           "LM Studio sur cette machine — à charger avec assez de contexte, sans quota.")
    if type_plateforme(v["decideur_type"]) == "passerelle":
        local = v["decideur_type"] == "passerelle_local"
        locaux, distants = modeles_par_portee()
        quotas = quotas_par_modele(_etat_passerelle_cache(st))
        # Une liste par bord : le même sélecteur mêlait modèles à quota et modèles locaux, et
        # les libellés « req/jour » n'avaient aucun sens pour un modèle servi par cette machine.
        noms = [m for m in quotas if m in (locaux if local else distants)]
        # Retrait des modèles que le lancement refuserait (quota hors d'atteinte, plafond de
        # jetons par requête insuffisant). Compté et rendu juste sous le sélecteur : un retrait
        # muet ferait croire à une disparition inexpliquée.
        inaptes = modeles_inaptes()
        ecartes = [m for m in noms if m in inaptes]
        noms = [m for m in noms if m not in inaptes]
        if local:
            etat_lm = _etat_lmstudio_cache(st)
            def _lib_modele(m: str) -> str:
                d = lmstudio.diagnostic(m, etat_lm)
                fiche = " · ".join(str(x) for x in (d.params, d.quant or d.format) if x)
                return f"{m} — {fiche + ' · ' if fiche else ''}{d.etat_court}"
            libelle, cle_widget = "Modèle local (LM Studio : chargé ? contexte ?)", "modele-local"
        else:
            def _lib_modele(m: str) -> str:
                q = quotas[m]
                if q["inconnu"] and not q["marge"]:
                    dispo = f"{q['limite']} req/jour, consommation inconnue (passerelle injoignable)" if q["limite"] else "sans limite journalière"
                else:
                    dispo = f"{q['marge']} req/jour disponibles sur {q['limite']}"
                # On expose le modèle, pas les clés API : une instance de providers.yaml mêle
                # clé + modèle + seau de quota, mais l'utilisateur choisit un MODÈLE. Le nombre
                # de clés qui le servent (= seaux de quota cumulés) suffit ; le détail par clé
                # est dans la légende sous le sélecteur.
                n = len(q["instances"])
                return f"{m} — {dispo} · {n} clé{'s' if n > 1 else ''}"
            libelle, cle_widget = "Modèle (RPD = requêtes/jour restantes)", "modele-distant"
        v["modele"] = c3.selectbox(libelle, noms, index=noms.index(base["modele"]) if base["modele"] in noms else 0,
                                   key=k(cle_widget), format_func=_lib_modele) if noms else c3.text_input("Modèle", value=base["modele"], key=k(cle_widget))
        if ecartes:
            with c3.expander(f"🚫 {len(ecartes)} modèle(s) écarté(s) — inutilisables pour une expérience"):
                for m in ecartes:
                    st.caption(f"**{m}** — {inaptes[m]}")
        if not noms:
            c3.caption("Aucun modèle local : déclarez une instance LM Studio dans providers.yaml (docs/setup/llm-providers.md)." if local
                       else "Aucun modèle distant utilisable : aucune instance à clé dans providers.yaml, ou toutes écartées.")
        v["temperature"] = c3.number_input("Température", 0.0, 2.0, float(base["temperature"]), 0.1, key=k("temp"))
        # Profondeur de réflexion. Seuls les fournisseurs Google savent l'appliquer aujourd'hui ;
        # ailleurs la passerelle avertit que le réglage n'est pas transmis plutôt que de
        # l'ignorer en silence — un paramètre scellé dans l'empreinte et jamais appliqué est le
        # défaut trouvé sur `temperature` du canal antigravity le 2026-09-10.
        # Niveau quand le modèle en déclare — c'est le réglage courant de l'API, et « high »
        # EST le maximum. Le budget numérique n'apparaît qu'à défaut : l'API le tolère encore
        # mais rend 400 si les deux partent ensemble, donc on n'en propose qu'un.
        niveaux = niveaux_reflexion(v["modele"])
        v["reflexion"] = None
        v["niveau_reflexion"] = None
        if niveaux:
            options = [CHOIX_NIVEAU_DEFAUT, *niveaux]
            courant = base.get("niveau_reflexion")
            choix_n = c3.selectbox(
                "Profondeur de réflexion", options,
                index=options.index(courant) if courant in options else 0, key=k("refl-niv"),
                format_func=lambda x: LIBELLES_NIVEAU.get(x, x),
                help="réglage courant de l'API : un niveau, pas un nombre. « maximum (high) » "
                     "est la réflexion la plus poussée que le modèle accepte. « défaut du "
                     "modèle » n'envoie rien. La pensée est prélevée sur le budget de sortie : "
                     "la passerelle relève le plafond en conséquence. Niveaux relevés dans la "
                     "documentation du fournisseur, par modèle.")
            v["niveau_reflexion"] = None if choix_n == CHOIX_NIVEAU_DEFAUT else choix_n
        else:
            choix_refl, plafond_refl = choix_reflexion_pour(v["modele"])
            choix = c3.selectbox("Profondeur de réflexion (budget, héritage)", choix_refl,
                                 index=min(_index_reflexion(base.get("reflexion"), plafond_refl),
                                           len(choix_refl) - 1), key=k("refl"),
                                 help="aucun niveau n'est déclaré pour ce modèle : on retombe "
                                      "sur le budget numérique, que l'API accepte encore mais "
                                      "ne recommande plus. Déclarez `thinking_levels` dans "
                                      "providers.yaml pour obtenir le réglage par niveau.")
            v["reflexion"] = _valeur_reflexion(choix, base.get("reflexion"), c3, k, plafond_refl)
            c3.caption("Aucun `thinking_levels` déclaré pour ce modèle : relevez-les dans la "
                       "documentation du fournisseur pour régler la réflexion par niveau."
                       + ("" if plafond_refl else " Et sans `thinking_budget_max`, un budget "
                          "au-delà du plafond réel serait raboté sans être signalé."))
        if (v["reflexion"] is not None or v["niveau_reflexion"] is not None) and local:
            c3.caption("⚠ Ce réglage n'est transmis que par les fournisseurs Google : sur un "
                       "modèle local il sera scellé dans l'empreinte sans être appliqué.")
    elif v["decideur_type"] == "aleatoire":
        v["graine_decideur"] = c3.number_input("Graine du tirage", 0, 10**9, int(base["graine_decideur"]), key=k("gdec"))
    elif v["decideur_type"] == "rejeu":
        v["rejeu_de"] = c3.text_input("Dossier d'exécution à rejouer", value=base["rejeu_de"], key=k("rejeu"), placeholder="/app/data/experiences/<exp>/executions/<horodatage>")
    elif v["decideur_type"] == "modele":
        v["artefact"] = c3.text_input("Artefact LightGBM (vide = version par défaut)", value=base.get("artefact", ""),
                                      key=k("artefact"), placeholder="scripts/progedo_logit/mode_choice_policy.json")
        c3.caption("Le modèle décide à la place du LLM (masse renormalisée sur l'offre). "
                   "Sa version est scellée par SHA dans l'exécution ; exige la couche de zones (make zones).")
    # Le sélecteur reste offert quel que soit le décideur (lire un prompt avant de le choisir
    # est utile en soi), mais il ne se présente plus comme un réglage de l'exécution quand
    # celle-ci n'en lira rien : c'est ici que « minimal_persona » entrait dans un
    # `experience.yaml` de décideur LightGBM, et de là dans le tableau (cf. `_prompt_affiche`).
    lit_un_prompt = type_plateforme(v["decideur_type"]) == "passerelle"
    t = textes.get(v["variante"]) or {}
    prov = t.get("provenance") or {}
    st.markdown(f"**📜 Prompt système « {v['variante']} »**" + (f" — {t['mots']} mots" if t.get("mots") else "")
                + (f" · {prov.get('role')}" if prov.get("role") else "")
                + ("" if lit_un_prompt else " — **non lu par ce décideur**"))
    if not lit_un_prompt:
        st.caption("Ce décideur ne lit aucun prompt système : il décide sans texte. Le choix "
                   "ci-dessus n'entrera ni dans le nom calculé de l'expérience, ni dans la "
                   "colonne « prompt » du registre — vous pouvez le lire et l'éditer ici, il "
                   "ne changera pas l'exécution.")
    if prov.get("obtention") or prov.get("date"):
        st.caption(" · ".join(str(x) for x in (prov.get("obtention"), prov.get("date"), prov.get("note")) if x))
    with st.container(border=True):
        st.markdown(t.get("contenu") or "_(contenu introuvable)_")
    with st.expander("✏️ Éditer"):
        nouveau_texte = st.text_area("Texte du nouveau prompt système", value=t.get("contenu") or "", height=320, key=k("edit"),
                                     help="Le bloc « Schéma JSON attendu » est retiré au rendu : le gabarit injecte le schéma lui-même.")
        c1, c2, c3 = st.columns([2, 1, 1], vertical_alignment="bottom")
        nouveau_nom = c1.text_input("Nom de la nouvelle variante", value="", key=k("newname"), placeholder=f"{v['variante']}_v2")
        if c2.button("💾 Enregistrer la variante", disabled=not nouveau_nom.strip(), width="stretch", key=k("save"),
                     help="donnez un nom à la nouvelle variante pour pouvoir l'enregistrer"):
            try:
                ajouter_variante(nouveau_nom, nouveau_texte, derive_de=v["variante"])
                base_maj = dict(base); base_maj["variante"] = nouveau_nom.strip()
                st.session_state["exp_base"] = base_maj
                st.session_state["exp_version"] = version + 1
                st.session_state["exp_msg"] = (f"variante « {nouveau_nom.strip()} » ajoutée à mobility_llm/prompts/prompts.yaml — "
                                               "rechargez la passerelle pour qu'elle la serve (bouton ci-contre).")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
        if c3.button("♻️ Recharger la passerelle", width="stretch", key=k("reload"), disabled=st.session_state.get("_lancer") is None,
                     help="`make passerelle-recharger` : la passerelle lit prompts.yaml au démarrage de son worker "
                          "— indisponible sans registre de lancements"):
            st.session_state["_lancer"]("passerelle-recharger", {})
            st.toast("Passerelle en cours de rechargement — suivi dans 📟 Activités en cours")

    # ── temps : mode, calendrier, puis le jour SEULEMENT si la date est commune ──
    c1, c2, c3, c4 = st.columns(4)
    v["mode"] = c1.radio("Mode", ("sans_simulateur", "simulateur"), index=0 if base["mode"] == "sans_simulateur" else 1, key=k("mode"),
                         format_func=lambda x: "sans simulateur (rapide)" if x == "sans_simulateur" else "avec GAMA")
    v["politique"] = c2.selectbox("Calendrier", POLITIQUES, index=POLITIQUES.index(base["politique"]), key=k("pol"),
                                  format_func=lambda x: {"commune": "date commune à tous", "propre": "date par personne (tirée)", "aleatoire": "jour représentatif tiré"}[x])
    jour_jeu = (v.get("jeu_courant") or {}).get("jour") or str(base["date"])
    if v["politique"] == "commune":
        v["date"] = c3.date_input("Jour simulé", value=date.fromisoformat(str(base["date"])), key=k("date"),
                                  help="l'offre de transport du jeu vaut pour son jour ; un autre jour recalcule les TC (ou : vérifier-jours)").isoformat()
        if v["date"] != jour_jeu and v.get("jeu_courant"):
            c3.caption(f"⚠ le jeu a été préparé pour le {jour_jeu}")
    else:
        v["date"] = str(jour_jeu)
        c3.caption(f"Jour de l'offre : celui du jeu ({jour_jeu}). La date de chaque personne est tirée dans la fenêtre d'enquête (graine du calendrier).")
    v["horizon_jours"] = c4.number_input("Horizon (jours)", 1, 31, int(base["horizon_jours"]), key=k("hor"), disabled=(v["mode"] == "sans_simulateur"),
                                         help="un seul jour sans simulateur ; l'horizon ne vaut qu'avec GAMA")
    if v["mode"] == "sans_simulateur":
        v["horizon_jours"] = 1
    with st.expander("Réglages avancés (graines, regroupement, tolérances horaires)"):
        c1, c2, c3, c4 = st.columns(4)
        v["memoire"] = c1.checkbox("Mémoire des agents (GAMA seulement)", value=bool(base["memoire"]), key=k("mem"), disabled=(v["mode"] == "sans_simulateur"),
                                   help="la mémoire des agents n'existe que dans GAMA : sans simulateur, il n'y a pas d'agent qui se souvienne")
        v["parallelisme"] = c2.number_input("Personnes en parallèle", 1, 64, int(base["parallelisme"]), key=k("par"))
        # Aligner la demande sur la capacité réelle du modèle : au-delà, la passerelle répond
        # « saturés » et la moitié des tentatives part en pure perte.
        conseil = parallelisme_conseille(str(v.get("modele") or ""), _etat_passerelle_cache(st))
        if conseil and conseil.get("local"):
            c2.caption(f"Conseillé : **{conseil['valeur']}** — modèle local : {conseil['valeur']} appel(s) simultané(s) "
                       f"acceptés par LM Studio (`concurrency_limit` de {len(conseil['instances'])} instance(s)) ; "
                       "au-delà, les requêtes attendent et la passerelle répond « saturés ».")
        elif conseil:
            source = "mesuré sur la passerelle" if conseil["mesure"] else "déclaré dans providers.yaml"
            c2.caption(f"Conseillé : **{conseil['valeur']}** — {conseil['rpm']} requêtes/minute cumulées "
                       f"sur {len(conseil['instances'])} instance(s) ({source}).")
            if conseil["valeur"] != int(v["parallelisme"]) and c2.button(
                    f"Utiliser {conseil['valeur']}", key=k("par-conseil"),
                    help="Aligne le parallélisme sur le débit du modèle choisi."):
                st.session_state["exp_base"] = {**defauts(), **v, "parallelisme": conseil["valeur"]}
                st.session_state["exp_version"] = version + 1
                st.rerun()
        v["graine_ordre"] = c3.number_input("Graine d'ordre des options", 0, 10**9, int(base["graine_ordre"]), key=k("go"))
        v["graine_tirage"] = c4.number_input("Graine du tirage de mode", 0, 10**9, int(base["graine_tirage"]), key=k("gt"))
        c1, c2, c3 = st.columns(3)
        v["graine_calendrier"] = c1.number_input("Graine du calendrier", 0, 10**9, int(base["graine_calendrier"]), key=k("gc"))
        v["max_candidats"] = c2.number_input("Options présentées au plus", 1, 20, int(base["max_candidats"]), key=k("mc"))
        v["attente_max_s"] = c3.number_input("Attente max d'une ressource (s)", 1, 3600, int(base["attente_max_s"]), key=k("att"))
        tol = st.text_area("Tolérances horaires (YAML)", value=yaml.safe_dump(base["tolerances"], sort_keys=False), key=k("tol"), height=140,
                           help="insensible · heure (recalcul si l'heure pleine change) · {pas_min: N}")
        try:
            v["tolerances"] = yaml.safe_load(tol) or {}
        except yaml.YAMLError as e:
            st.error(f"Tolérances illisibles : {e}")
            v["tolerances"] = base["tolerances"]
    if v["mode"] == "simulateur":
        st.info("Avec GAMA, le lancement passe par `make run OFFLINE=1 JEU=<jeu>` : GAMA lit le prompt **actif** de la passerelle, "
                "pas la variante choisie ici, et n'utilise pas le fichier d'expérience (limite connue, docs/arch/plateforme-experiences.md).")

    # Le nom calculé, écrit dans la place réservée en tête. Il ne se corrige pas : il change
    # quand un paramètre change, ce qui est tout l'intérêt — le 2026-09-07, un nom libre a
    # laissé trois modèles se mesurer sous une seule identité (R31, supprimée par N1).
    exp_provisoire = construire_experience(v)
    attribution, raison = nommer(exp_provisoire)
    with zone_nom.container():
        st.markdown("**Nom de l'expérience** — calculé depuis les paramètres")
        if attribution is None:
            st.warning(raison or "le nom n'a pas pu être calculé")
        else:
            st.code(attribution.nom, language=None)
            if attribution.reutilise:
                deja = executions_connues(attribution.reutilise)
                st.info(f"Ces paramètres sont **déjà** ceux de « {attribution.reutilise} » "
                        f"({deja} exécution(s)) : lancer ajoutera une exécution à cette "
                        f"expérience, sans rien réécrire. Changez un paramètre pour en ouvrir "
                        f"une autre.")
            elif attribution.indice > 1:
                st.warning(f"« {attribution.base} » est déjà pris par une autre définition : "
                           f"un indice a été ajouté, comme pour une copie de fichier.")
            elif attribution.voisins:
                st.caption("Variantes déjà nommées sur cette base : "
                           + " · ".join(attribution.voisins))
    return v


DELAI_VALIDATION_S = 20  # `experience-definir` ne fait que valider un schéma : c'est large


def motif_sans_validation(services: Optional[set[str]], inline: Optional[Callable[..., str]]) -> Optional[str]:
    """Pourquoi la validation ne sera pas tentée, ou None si elle peut l'être (R10).

    L'inconnu n'est pas traité comme un « oui » : quand `docker compose ps` ne répond pas, la
    validation n'est pas tentée du tout. Sinon un démon Docker qui pend ferait attendre
    l'enregistrement, et son erreur viendrait s'ajouter au message.
    """
    if inline is None:
        return "l'exécution en direct n'est pas disponible dans ce contexte"
    if services is None:
        return "l'état des services Docker est inconnu (docker injoignable)"
    if "controller" not in services:
        return "le service `controller` ne tourne pas"
    return None


def _enregistrer_et_dire(exp: dict, *, inline: Optional[Callable[..., str]],
                         sans_validation: Optional[str]) -> str:
    """Écrit le fichier, puis tente la validation. Rend ce qu'il faut afficher (R3, R4, R8).

    L'écriture est locale et n'attend jamais Docker. `sans_validation` porte le motif quand la
    validation ne peut pas être tentée : on le DIT, au lieu de laisser une erreur Docker se
    lire comme un enregistrement raté (R10, R11).
    """
    chemin, change = enregistrer(exp)
    try:
        relatif = chemin.relative_to(REPO_ROOT)
    except ValueError:
        relatif = chemin  # dossier d'expériences configuré hors du dépôt : chemin absolu
    lignes = [f"{'écrit' if change else 'inchangé (le fichier disait déjà cela)'} : {relatif}"]
    nom_jeu = exp["jeu"]["nom"]
    lignes.append(f"jeu attendu « {nom_jeu} » : {etat_du_jeu(nom_jeu)}")
    if sans_validation is None:
        # Étiquette explicite : ce qui suit est le résultat de la VALIDATION, pas celui de
        # l'enregistrement, qui est déjà annoncé au-dessus (R11).
        sortie = inline("experience-definir", {"FICHIER": str(relatif)}, timeout=DELAI_VALIDATION_S).strip()
        lignes.append(f"validation par la plateforme :\n{sortie}")
    else:
        lignes.append(f"validation non tentée : {sans_validation}. L'expérience est enregistrée ; "
                      f"relancez « Enregistrer » quand ce sera possible.")
    return "\n".join(lignes)


def _etat_passerelle_cache(st, ttl_s: float = 30.0) -> Optional[dict]:
    import time
    cache = st.session_state.get("_passerelle")
    if cache and time.time() - cache[0] < ttl_s:
        return cache[1]
    etat = etat_passerelle()
    st.session_state["_passerelle"] = (time.time(), etat)
    return etat


def _etat_lmstudio_cache(st, ttl_s: float = 10.0) -> Optional[dict]:
    """L'état de LM Studio (`/api/v1/models`, vu de l'hôte), None s'il est injoignable — cache court : un chargement change tout en une minute."""
    import time
    cache = st.session_state.get("_lmstudio")
    if cache and time.time() - cache[0] < ttl_s:
        return cache[1]
    etat = lmstudio.etat_lmstudio()
    st.session_state["_lmstudio"] = (time.time(), etat)
    return etat


def _services_cache(st, ttl_s: float = 15.0) -> Optional[set[str]]:
    import time
    cache = st.session_state.get("_services")
    if cache and time.time() - cache[0] < ttl_s:
        return cache[1]
    actifs = services_actifs()
    st.session_state["_services"] = (time.time(), actifs)
    return actifs


def _panneau_lancements(st, jobs, filtre=("root:jeu", "root:experience-lancer", "root:experience-reprendre",
                                          "root:experience-lancer-arret", "root:run", "root:run-arret",
                                          "root:passerelle-recharger", "root:lmstudio-charger",
                                          "root:lmstudio-decharger")) -> None:
    """Les jobs de la plateforme en cours, avec leur dernière ligne — sans changer d'onglet.

    Vivant tant qu'un job tourne : sinon la dernière ligne de journal se figeait au premier
    affichage, et un job terminé restait annoncé « en cours » jusqu'au prochain clic.
    """
    if jobs is None:
        return

    def _en_cours():
        return [j for j in jobs() if j.running and any(j.label.startswith(f) for f in filtre)]

    def dessiner() -> None:
        actifs = _en_cours()
        if not actifs:
            return
        st.markdown(f"**⏳ {len(actifs)} lancement(s) en cours**")
        for j in actifs:
            derniere = ""
            try:
                lignes = j.log_path.read_text(encoding="utf-8", errors="ignore").rstrip().splitlines()
                derniere = lignes[-1][-160:] if lignes else ""
            except OSError:
                pass
            st.caption(f"`{j.label}` · {int(j.duration)} s · {derniere}")

    st.fragment(run_every="5s" if _en_cours() else None)(dessiner)()


RESERVATIONS_JSON = DOSSIER / ".reservations.json"
FILE_JSON = DOSSIER / ".file.json"


def _reservations_actives() -> list[dict]:
    """Réservations en cours, groupées par expérience (lecture directe du registre partagé)."""
    brut = _json(RESERVATIONS_JSON)
    par_exp: dict[str, dict] = {}
    for cle, e in (brut or {}).items():
        ref = par_exp.setdefault(e.get("exp", "?"), {"exp": e.get("exp", "?"), "cles": []})
        ref["cles"].append(cle)
    for ref in par_exp.values():
        ref["cles"].sort()
    return sorted(par_exp.values(), key=lambda r: r["exp"])


def _file_attente() -> list[dict]:
    contenu = _json(FILE_JSON)
    return contenu if isinstance(contenu, list) else []


def _panneau_file_reservations(st, lancer, jobs) -> None:
    """Ordonnancement par clé (spec parallelisation_experiences) : qui tient quelle clé, qui
    attend, et l'ordonnanceur qui démarre la file dès qu'une clé se libère."""
    actives = _reservations_actives()
    attente = _file_attente()
    if not actives and not attente:
        return
    ordonnanceur_up = bool(
        jobs and any(j.running and "experience-ordonnancer" in j.label for j in jobs())
    )
    titre = f"🔑 Clés : {len(actives)} en cours · {len(attente)} en file"
    with st.expander(titre, expanded=bool(attente)):
        if actives:
            st.markdown("**En cours (clés tenues)**")
            for r in actives:
                st.caption(f"`{r['exp']}` → {', '.join(r['cles'])}")
        if attente:
            st.markdown("**En attente (FIFO)** — démarrées dès que leurs clés se libèrent")
            for i, e in enumerate(attente):
                c1, c2 = st.columns([5, 1], vertical_alignment="center")
                c1.caption(
                    f"{i + 1}. `{e.get('exp', '?')}` — clé(s) : {', '.join(e.get('cles') or []) or '—'}"
                )
                if lancer and c2.button("Retirer", key=f"defiler-{i}-{e.get('exp')}",
                                        help="Retire de la file : ne sera pas démarrée automatiquement (R2e)"):
                    lancer("experience-defiler", {"EXP": e.get("exp", "")})
        if attente and not ordonnanceur_up:
            st.warning("Aucun ordonnanceur ne tourne : la file ne démarrera pas seule.")
            if lancer and st.button("▶️ Démarrer l'ordonnanceur", key="start-ordonnanceur",
                                    help="Boucle hôte qui promeut la file dès qu'une clé se libère"):
                lancer("experience-ordonnancer", {})
        elif ordonnanceur_up:
            st.caption("🟢 Ordonnanceur actif — la file avance automatiquement.")


def _popup_estimation(st, sortie: str) -> None:
    """Popup réduit à l'essentiel : le nombre de requêtes LLM que coûterait l'expérience.

    `experience-estimer` imprime un JSON riche (jetons, quota, durée) suivi d'un éventuel
    bloc « REFUS ». On n'en garde à l'écran que le compteur de requêtes ; le reste (durée,
    part de quota) tient en une ligne de légende, et un refus éventuel est signalé.
    """
    brut = sortie or ""
    i = brut.find("REFUS")
    try:
        est = json.loads(brut[:i] if i != -1 else brut)
    except ValueError:
        est = None

    @st.dialog("🧮 Estimation du coût")
    def _contenu() -> None:
        if est and isinstance(est.get("sollicitations"), dict):
            st.metric("Requêtes LLM", _n(est["sollicitations"].get("valeur")))
            duree = (est.get("duree_s") or {}).get("valeur")
            if duree:
                st.caption(f"Durée estimée ≈ {int(duree // 60)} min ({int(duree)} s) au débit courant.")
            part = (est.get("quota") or {}).get("part")
            if isinstance(part, (int, float)):
                st.caption(f"Soit {part * 100:.0f} % de la marge de quota du jour.")
        else:
            st.code(brut or "estimation indisponible", language="json")
        if i != -1:
            st.warning(brut[i:].strip())

    _contenu()


SANS_SOURCE = "— partir de zéro —"


def _recopier_source(st, *, depuis_la_liste: bool = False) -> None:
    """Recopie dans le formulaire l'expérience choisie dans « S'inspirer de » (spec inspirer-recopie-immediate).

    Rappel `on_change` du sélecteur (R1, R2) et action de « ↺ Recopier à nouveau » (R5). Il ne
    fait que poser la base et remettre les clés des widgets à neuf via `exp_version` : c'est le
    formulaire, dessiné ensuite, qui repart de cette base. Rien n'est écrit sur le disque (R9).
    `exp_source_recopiee` retient d'où vient le formulaire, pour repérer une source supprimée
    après coup (R10) ; `exp_source_avis` est une légende dite une fois (R8).
    """
    choix = st.session_state.get("exp-source", SANS_SOURCE)
    existantes = experiences()  # relu maintenant, pas au rendu de la liste : une expérience a pu disparaître (R6)
    if choix == SANS_SOURCE:
        base, avis = defauts(), ("caption", "Formulaire remis aux défauts de la plateforme — le nom se recalcule.")
    else:
        e = existantes.get(choix)
        if e is None:
            logger.warning("« S'inspirer de » : l'expérience %r n'existe plus, formulaire inchangé", choix)
            st.session_state["exp_source_avis"] = ("warning", f"L'expérience « {choix} » n'existe plus : formulaire inchangé.")
            # La liste doit revenir sur ce que le formulaire contient encore. L'écrire ICI, dans le
            # rappel du sélecteur lui-même, fait perdre la légende au run suivant : c'est le corps
            # de la page qui rabat, avant de dessiner le sélecteur (cf. render).
            encore = st.session_state.get("exp_source_recopiee")
            st.session_state["exp_source_rabattre"] = encore if encore in existantes else SANS_SOURCE
            return
        # Même validation que le brouillon relu (R21b) : une valeur qui ne désigne plus rien revient
        # à son défaut, une valeur hors bornes est ramenée dans l'intervalle du champ (R7).
        base = _valider_base(depuis_experience(e))
        avis = ("caption", f"Réglages de « {choix} » recopiés — le nom se recalcule des paramètres.")
    st.session_state["exp_base"] = base
    st.session_state["exp_version"] = int(st.session_state.get("exp_version", 0)) + 1
    st.session_state["exp_source_recopiee"] = None if choix == SANS_SOURCE else choix
    st.session_state["exp_source_avis"] = avis
    logger.info("« S'inspirer de » : %s (formulaire version %d)", avis[1], st.session_state["exp_version"])


def _afficher_avis_source(st, zone, valeurs: dict) -> None:
    """La légende de « S'inspirer de » (R8) ou l'avertissement d'une source disparue (R6, R10).

    Affiché tant que le formulaire est celui qu'il décrit — son empreinte est prise au premier
    affichage — et effacé à la première retouche : une légende « recopiés » sur un formulaire
    retouché mentirait. Ne pas le consommer à l'affichage : les suivis de la page (jeux,
    registre) relancent le script en plein run, et un avis consommé au premier passage n'atteint
    jamais l'écran.
    """
    avis = st.session_state.get("exp_source_avis")
    if not avis:
        return
    niveau, texte, empreinte = (*avis, None)[:3]
    courante = _empreinte_formulaire(valeurs)
    if empreinte is None:
        st.session_state["exp_source_avis"] = (niveau, texte, courante)
    elif empreinte != courante:
        del st.session_state["exp_source_avis"]
        return
    (zone.warning if niveau == "warning" else zone.caption)(texte)


def render(st, pd, *, lancer: Optional[Callable[[str, dict], None]] = None, inline: Optional[Callable[..., str]] = None,
           jobs: Optional[Callable[[], list]] = None, arreter: Optional[Callable[[str], bool]] = None) -> None:
    """`lancer(cible, variables)` démarre un job make (onglet Activités en cours) ; `inline` rend la sortie d'une cible courte ;
    `jobs()` liste les jobs du registre ; `arreter(id)` en arrête un (avant un lancement concurrent)."""
    st.session_state["_lancer"] = lancer
    st.subheader("🧪 Nouvelle expérience")
    services = _services_cache(st)
    controleur_ok = services is None or "controller" in services
    if services is not None and "controller" not in services:
        st.info("Le service `controller` ne tourne pas : la plateforme s'exécute dans ce conteneur. "
                "**« ▶ Lancer » le démarre lui-même** (avec ses dépendances) avant de lancer "
                "l'expérience. Seul « 🧮 Estimer le coût » l'exige tout de suite : il lit la "
                "réponse de la plateforme en direct.")
    elif services is None:
        st.caption("**Le démon Docker ne répond pas** : ouvrez Docker Desktop, sans quoi tout "
                   "lancement échouera sur `failed to connect to the docker API`. L'enregistrement "
                   "d'une configuration, lui, n'attend pas Docker et ne le sollicite pas.")
    _panneau_lancements(st, jobs)
    _panneau_file_reservations(st, lancer, jobs)
    existantes = experiences()
    # La source recopiée a pu être supprimée du disque APRÈS avoir été choisie (R10) : le dire une
    # fois, et remettre la liste d'aplomb AVANT de la dessiner — Streamlit la rabattrait en silence.
    recopiee = st.session_state.get("exp_source_recopiee")
    if recopiee and recopiee not in existantes:
        logger.warning("« S'inspirer de » : l'expérience %r, recopiée dans le formulaire, n'existe plus", recopiee)
        st.session_state["exp_source_avis"] = ("warning", (f"L'expérience « {recopiee} », recopiée dans le formulaire, n'existe plus : "
                                                           "le formulaire garde ses réglages, la liste repart de « — partir de zéro — »."))
        st.session_state["exp_source_recopiee"] = None
        st.session_state["exp_source_rabattre"] = SANS_SOURCE
    rabattre = st.session_state.pop("exp_source_rabattre", None)
    if rabattre is not None:  # avant le dessin du sélecteur : après, Streamlit refuserait l'écriture
        st.session_state["exp-source"] = rabattre
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    # Le choix recopie AUSSITÔT (R1) : le rappel tourne au début du run suivant, avant ce code.
    # `exp_version` se lit donc APRÈS le sélecteur — c'est lui qui remet les clés à neuf.
    source = c1.selectbox("S'inspirer d'une expérience existante", [SANS_SOURCE, *existantes], key="exp-source",
                          on_change=_recopier_source, args=(st,), kwargs={"depuis_la_liste": True},
                          help="Choisir une expérience recopie aussitôt tous ses réglages dans le formulaire ; "
                               "« — partir de zéro — » remet les défauts. Le nom, lui, se recalcule.")
    # `and source in existantes` : un clic parti avant la disparition de la source arrive quand même,
    # sur un bouton pourtant dessiné grisé — il ne doit pas remettre le formulaire aux défauts (R11).
    if c2.button("↺ Recopier à nouveau", disabled=(source not in existantes), width="stretch",
                 help="réapplique les réglages de l'expérience choisie, après des retouches à la main") \
            and source in existantes:
        _recopier_source(st)  # le formulaire est dessiné plus bas dans CE run : aucun rerun nécessaire
    zone_avis = st.empty()  # remplie APRÈS le formulaire : l'avis ne s'affiche que tant qu'il est vrai (R8)
    version = int(st.session_state.get("exp_version", 0))
    base = st.session_state.get("exp_base") or charger_etat_formulaire() or defauts()
    valeurs = _formulaire(st, base, version)
    _afficher_avis_source(st, zone_avis, valeurs)
    sauver_etat_formulaire(valeurs)  # brouillon : les choix survivent au redémarrage (R21)
    exp = construire_experience(valeurs)

    # Ce que CETTE expérience utilise et son état — pas les cinq conteneurs de métrologie que
    # `make up` réveille. Plus de bouton : le lancement démarre lui-même ce qui manque, ce bloc
    # ne fait que le dire à l'avance (un démarrage à froid coûte plusieurs minutes de graphes).
    requis = services_requis(exp, jeu_a_construire=bool(valeurs.get("sans_jeu")))
    _suivi_des_services(st, requis)
    # Puis le modèle local, s'il y en a un : chargé ? avec assez de contexte ? Un bouton le charge.
    modele_local = modele_local_de(exp)
    if modele_local:
        _suivi_lmstudio(st, modele_local, lancer)

    jeu_clos = bool((valeurs.get("jeu_courant") or {}).get("clos"))
    if exp["jeu"]["nom"] and not jeu_clos and not valeurs.get("sans_jeu"):
        st.warning(f"Le jeu « {exp['jeu']['nom']} » est encore en préparation : l'expérience pourra être lancée quand il sera clos.")
    nom_warmup = nom_jeu_attendu(valeurs["population"], exp["calendrier"]["date"])
    if valeurs.get("sans_jeu"):
        st.info(f"Étape préalable : construire le jeu « {nom_warmup} » pour « {Path(valeurs['population']).name} », "
                f"jour {exp['calendrier']['date']}. L'expérience peut être **enregistrée dès maintenant** : "
                f"elle nomme ce jeu, et deviendra lançable sans retouche dès qu'il sera clos.")
    construction = construction_active(nom_warmup)

    # Une exécution reprenable existe : « Lancer » en créerait une DEUXIÈME et repaierait ses
    # décisions. Le dire, plutôt que de le laisser découvrir sur la facture de quota.
    a_reprendre = [l for l in lister()
                   if l["experience"] == exp["nom"] and l.get("execution") and est_reprenable(l)]
    if a_reprendre:
        derniere = a_reprendre[-1]
        st.warning(
            f"« {exp['nom']} » a une exécution reprenable : `{derniere['execution']}` "
            f"({derniere['etat']}, {decisions_archivees(derniere['dossier'])} décisions déjà "
            f"archivées). « ▶ Lancer » en créerait une **nouvelle** et repaierait ces décisions. "
            f"Pour la poursuivre : « ▶ Reprendre », dans « Mes expériences » plus bas."
        )

    # Rendre la RAM aux autres applications quand l'expérience est finie. L'arrêt est CHAÎNÉ
    # dans la commande lancée, pas surveillé par la page : il a lieu même navigateur fermé.
    a_rendre = services_a_arreter(exp, jeu_a_construire=bool(valeurs.get("sans_jeu")))
    arret_fin = st.checkbox(
        f"Arrêter les services Docker à la fin de l'expérience ({len(a_rendre)} services, rend la RAM)",
        value=False, key="arret-services-fin",
        help="Chaîné dans le lancement : l'arrêt a lieu même si le tableau de bord est fermé. "
             "`docker compose stop`, donc conteneurs et volumes restent et le redémarrage est "
             "rapide. Services arrêtés : " + ", ".join(a_rendre) + ". La métrologie n'est pas "
             "touchée — `make down` reste la voie pour tout couper.",
    )

    diag_local = lmstudio.diagnostic(modele_local, _etat_lmstudio_cache(st)) if modele_local else None
    motif_local = None if diag_local is None or diag_local.pret else f"modèle local : {diag_local.motif}"
    motifs = motifs_indisponibilite(exp, jeu_clos=jeu_clos, controleur_ok=controleur_ok,
                                    registre=bool(lancer), construction=construction, modele_local=motif_local,
                                    docker_ok=services is not None)
    bloc_enregistrer, bloc_estimer = motifs["enregistrer"], motifs["estimer"]
    bloc_lancer, bloc_construire = motifs["lancer"], motifs["construire"]
    sans_jeu = bool(valeurs.get("sans_jeu"))

    b1, b2, b3, b4 = st.columns(4)
    if b1.button("💾 Enregistrer", disabled=bool(bloc_enregistrer), width="stretch",
                 help="écrit data/experiences/<nom>/experience.yaml sans rien lancer ; la validation "
                      "par la plateforme suit quand le service `controller` tourne"):
        st.session_state["exp_msg"] = _enregistrer_et_dire(
            exp, inline=inline, sans_validation=motif_sans_validation(services, inline))
    if b2.button("🧮 Estimer le coût", disabled=bool(bloc_estimer), width="stretch", help="`make experience-estimer` (enregistre d'abord)"):
        enregistrer(exp)
        _popup_estimation(st, inline("experience-estimer", {"EXP": exp["nom"]}) if inline else "")
    if b3.button("▶ Lancer", type="primary", disabled=bool(bloc_lancer), width="stretch",
                 help="`make experience-lancer` (sans simulateur) ou `make run OFFLINE=1` (avec GAMA). "
                      "Les services nécessaires sont démarrés d'abord s'ils ne tournent pas."):
        enregistrer(exp)
        services_fin = " ".join(a_rendre)
        # `REQUIS=` : ce que la cible doit garantir avant de lancer. `SERVICES=` reste la liste
        # de ce qu'on ARRÊTE à la fin — deux listes différentes, deux variables distinctes.
        besoins = " ".join(requis)
        if exp["mode"] == "sans_simulateur":
            if arret_fin:
                lancer("experience-lancer-arret", {"EXP": exp["nom"], "SERVICES": services_fin, "REQUIS": besoins})
            else:
                lancer("experience-lancer", {"EXP": exp["nom"], "REQUIS": besoins})
        elif arret_fin:
            lancer("run-arret", {"JEU": exp["jeu"]["nom"], "SERVICES": services_fin})
        else:
            lancer("run", {"OFFLINE": "1", "JEU": exp["jeu"]["nom"]})
        if arret_fin:
            st.session_state["exp_msg"] = f"les services seront arrêtés à la fin : {services_fin}"
        st.toast(f"Expérience « {exp['nom']} » lancée — suivi ci-dessous et dans 📟 Activités en cours")
    # Le warm-up n'apparaît que lorsqu'aucun jeu n'existe encore : préparer un SECOND jeu pour
    # une population déjà servie ne se fait pas d'ici (cas rare, source de confusion).
    if sans_jeu and b4.button("🔥 Warm-up : construire le jeu", type="primary",
                 disabled=bool(bloc_construire), width="stretch",
                 help=f"`make jeu POP=… NOM={nom_warmup} JOUR={exp['calendrier']['date']}` : toutes les options de tous les déplacements du jour (long, reprenable)"):
        lancer("jeu", {"POP": valeurs["population"], "NOM": nom_warmup,
                       "JOUR": str(exp["calendrier"]["date"]), "REQUIS": " ".join(requis)})
        st.session_state["_warmup_lance_a"] = time.time()
        st.toast(f"Construction du jeu « {nom_warmup} » lancée — suivi ci-dessus et dans 📟 Activités en cours")
        # Sans ce rerun, le drapeau ci-dessus ne serait lu qu'au prochain clic de l'utilisateur :
        # le fragment de suivi a déjà été créé plus haut dans CE run, avec run_every=None.
        st.rerun()

    boutons = [("💾 Enregistrer", bloc_enregistrer), ("🧮 Estimer le coût", bloc_estimer),
               ("▶ Lancer", bloc_lancer)]
    if sans_jeu:
        boutons.append(("🔥 Warm-up : construire le jeu", bloc_construire))
    for libelle, motifs in boutons:
        if motifs:
            st.caption(f"**{libelle}** indisponible : " + " · ".join(dict.fromkeys(motifs)))
    if st.session_state.get("exp_msg"):
        st.code(st.session_state["exp_msg"], language="log")
    if not lancer:
        st.caption("Lancement indisponible dans ce contexte (registre de jobs absent).")

    st.divider()
    st.subheader("📚 Mes expériences")
    # Les expériences archivées ou invalidées (gabarit obsolète) sortent du tableau : elles ne
    # portent rien sur quoi s'appuyer. Rien n'est supprimé — le panneau ci-dessous les compte,
    # dit pourquoi, et permet de les revoir (spec hygiène §3.2, §5).
    toutes = lister()
    lignes = [l for l in toutes if not masquee(l)]
    _panneau_statuts(st, toutes)
    if not lignes:
        st.info("Aucune expérience enregistrée. Remplissez le formulaire ci-dessus, puis « Enregistrer » ou « Lancer ».")
        _panneau_masques(st, vide=True)
        return
    _suivi_du_registre(st, pd)
