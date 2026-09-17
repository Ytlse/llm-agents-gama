"""Identité d'un run — ticket 091.

POURQUOI
--------
Rien ne reliait une mémoire stockée au run qui l'avait produite. Contenu réel d'un point de
reprise du 2026-09-16 : jour simulé, horodatage, ancre, compteurs — ni modèle, ni prompt, ni
population, ni choc. Et la reprise suivait le lien `experiments/current`, qui a pointé deux fois
dans la même journée sur un run autre que celui qu'on croyait. Un `make run CONT=1` pouvait donc
restaurer la mémoire d'une AUTRE expérience sans qu'une seule ligne ne le signale.

LE PRINCIPE
-----------
Par défaut on ne réutilise rien. La reprise se demande en NOMMANT le run, et n'a lieu que si
l'expérience est la même. Une identité qui diffère fait refuser le lancement, en nommant le champ
fautif — jamais un repli silencieux.

⚠ **Aucune échappatoire n'est prévue.** Les cas de mise au point se traitent à la main, hors du
code : un contournement livré dans le produit finirait par servir en mesure, et c'est précisément
ce qu'on cherche à rendre impossible.

CE QUE L'IDENTITÉ RETIENT
-------------------------
Ce qui rend deux mesures comparables, et rien d'autre. L'heure d'écriture et les compteurs n'en
font pas partie : ils diffèrent toujours et feraient refuser toutes les reprises.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

FICHIER = "identite_run.json"

# Libellés lisibles : un refus doit nommer ce qui diffère dans les mots de l'utilisateur,
# pas dans ceux du code.
LIBELLES = {
    "modeles_admis": "modèle(s)",
    "instances_admises": "instances admises",
    "variante_prompt": "variante de prompt",
    "population": "population",
    "memoire_longue": "mémoire longue",
    "auto_reflexion": "auto-réflexion",
    "choc": "choc",
    "graine_tirage": "graine de tirage",
    "graine_ordre": "graine d'ordre des options",
    "graine_meteo": "graine de météo",
    "cache_decisions": "cache de décisions",
}


class IdentiteIncompatible(RuntimeError):
    """La reprise demandée ne porte pas sur la même expérience."""


def _empreinte_du_choc(reglages: Any) -> str:
    """L'empreinte du choc DÉCLARÉ, lue sur le fichier et non sur le registre.

    ⚠ Le registre de chocs n'est initialisé qu'au `/init` de GAMA, donc APRÈS l'écriture de
    l'identité au démarrage du contrôleur. L'interroger ici rendait « aucun » même quand un choc
    était déclaré — un champ qui ne discrimine jamais, exactement le défaut que ce module corrige
    par ailleurs pour le modèle. L'empreinte est donc recalculée comme `chocs.charger` la
    calcule : sha256 des octets du fichier.
    """
    import hashlib

    cfg = getattr(reglages, "chocs", None)
    if cfg is None or not getattr(cfg, "enabled", False):
        return "aucun"
    chemin = getattr(cfg, "fichier", None)
    if not chemin:
        return "aucun"
    p = Path(str(chemin))
    if not p.is_file():
        # Un choc déclaré mais introuvable fera échouer le chargement plus loin ; ici on refuse
        # surtout de rendre « aucun », qui ferait passer deux expériences différentes pour une.
        return f"declare-introuvable:{p.name}"
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _modeles_des_instances(reglages: Any, admises: list[str]) -> list[str]:
    """Les modèles servis par les instances admises. Vide quand rien n'est restreint."""
    fournisseurs = getattr(reglages.llm, "providers", {}) or {}
    modeles = set()
    for nom in admises:
        cfg = fournisseurs.get(nom)
        modele = getattr(cfg, "default_model", None) if cfg is not None else None
        if modele:
            modeles.add(str(modele))
    return sorted(modeles)


def composer(reglages: Any, empreinte_choc: str | None = None) -> dict:
    """L'identité de l'expérience telle que la configuration courante la décrit."""
    params = dict(getattr(reglages.agent, "llm_params", {}) or {})
    admises = sorted(getattr(reglages.llm, "instances_admises", []) or [])
    return {
        # Le modèle n'est pas un réglage à part : il est porté par les instances admises. Le
        # dériver plutôt que de lire un champ qui n'existe pas évite une clé toujours vide —
        # un champ qui ne discrimine jamais donne l'illusion d'une vérification.
        "modeles_admis": _modeles_des_instances(reglages, admises),
        "instances_admises": admises,
        "variante_prompt": str(params.get("prompt_variant", "")),
        "population": str(getattr(reglages.data, "population_file", "")),
        "memoire_longue": bool(getattr(reglages.agent, "long_term_memory_enabled", False)),
        "auto_reflexion": bool(
            getattr(reglages.agent, "long_term_self_reflect_enabled", False)
        ),
        "choc": empreinte_choc if empreinte_choc else _empreinte_du_choc(reglages),
        "graine_tirage": int(getattr(reglages.agent, "mode_draw_seed", 0)),
        "graine_ordre": int(getattr(reglages.agent, "option_order_seed", 0)),
        "graine_meteo": int(getattr(reglages.agent, "weather_draw_seed", 0)),
        "cache_decisions": bool(getattr(reglages.cache, "enabled", False)),
    }


def chemin(workdir: str | Path) -> Path:
    return Path(workdir) / FICHIER


def ecrire(workdir: str | Path, identite: dict, *, ecraser: bool = False) -> bool:
    """Écrit l'identité. Sans `ecraser`, une identité déjà posée est LAISSÉE EN PLACE.

    C'est la règle du ticket : l'identité d'un run repris est la référence contre laquelle on
    compare, pas un journal qu'on réécrit à chaque redémarrage. La réécrire reviendrait à faire
    disparaître la différence qu'on cherche à détecter.
    """
    cible = chemin(workdir)
    if cible.exists() and not ecraser:
        return False
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(
        json.dumps(identite, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8"
    )
    logger.info(f"[identite] identité du run écrite dans {cible.name}")
    return True


def lire(workdir: str | Path) -> dict | None:
    """L'identité posée, ou None si elle est absente ou illisible (les deux font refuser)."""
    cible = chemin(workdir)
    if not cible.is_file():
        return None
    try:
        charge = json.loads(cible.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        logger.error(f"[identite] {cible.name} illisible ({e})")
        return None
    return charge if isinstance(charge, dict) else None


def differences(attendue: dict, actuelle: dict) -> list[str]:
    """Les champs qui diffèrent, en clair. Liste vide = même expérience.

    TOUS les écarts sont rendus, pas seulement le premier : corriger un champ pour buter sur le
    suivant au lancement d'après ferait perdre trois quarts d'heure à chaque tour.
    """
    ecarts = []
    for champ, libelle in LIBELLES.items():
        a = attendue.get(champ)
        b = actuelle.get(champ)
        if a != b:
            ecarts.append(f"{libelle} : {a!r} au run repris, {b!r} maintenant")
    return ecarts


def verifier(workdir: str | Path, actuelle: dict) -> None:
    """Lève `IdentiteIncompatible` si la reprise ne porte pas sur la même expérience."""
    attendue = lire(workdir)
    if attendue is None:
        raise IdentiteIncompatible(
            f"le run {Path(workdir).name} ne porte pas de fichier d'identité "
            f"({FICHIER}) : impossible de vérifier qu'il s'agit de la même expérience. "
            f"Un run antérieur au ticket 091 ne peut pas être repris."
        )
    ecarts = differences(attendue, actuelle)
    if ecarts:
        raise IdentiteIncompatible(
            f"le run {Path(workdir).name} n'est pas la même expérience que celle demandée — "
            + " ; ".join(ecarts)
        )
