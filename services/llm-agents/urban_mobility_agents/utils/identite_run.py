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
    "routage_instances": "routage des instances par fonction",
    "variante_prompt": "variante de prompt",
    "population": "population",
    "memoire_longue": "mémoire longue",
    "auto_reflexion": "auto-réflexion",
    "choc": "choc",
    "graine_tirage": "graine de tirage",
    "graine_ordre": "graine d'ordre des options",
    "graine_meteo": "graine de météo",
    "cache_decisions": "cache de décisions",
    # Réglages d'EXPÉRIENCE (ticket 077, lot K). Ils ne vivent pas dans `config.yaml` — ils
    # appartiennent au run, qui les enregistre ici. Sans eux, trois bras aux réglages opposés
    # portaient la même identité, et rien ne permettait de dire, après coup, sous quels réglages
    # un run avait tourné.
    "chaine_vehicules": "chaînage des véhicules",
    "verrou_retour_domicile": "verrou de retour au domicile",
    "seuil_troncature": "seuil de troncature du tirage",
    "seuil_choc": "seuil de choc en mémoire",
    # Ticket 095 — le MODÈLE DE GRAVITÉ appartient à l'expérience. Deux bras qui ne donnent pas
    # la même gravité au même retard n'écrivent pas la même mémoire.
    "retard_saturation": "forme de la composante de retard",
    "retard_gravite_max": "maximum de la composante de retard",
    "retard_ref_s": "retard de référence (s)",
    "fenetre_changements_jours": "fenêtre « ce qui a changé récemment » (jours)",
    # Ticket 095, lot A — la durée d'un souvenir de choc se dérive de sa gravité. Le MODE en
    # vigueur appartient à l'identité : deux bras qui ne servent pas les souvenirs selon la même
    # règle ne mesurent pas la même chose, même à fenêtre déclarée identique.
    "mode_fenetre_changements": "mode de la fenêtre de changements",
    "seuil_service_changement": "seuil de service d'un souvenir de choc",
    "plancher_changement_jours": "plancher de durée d'un souvenir de choc (jours)",
    "plafond_changement_jours": "plafond de durée d'un souvenir de choc (jours)",
    "changements_max": "lignes du bloc « ce qui a changé récemment »",
    "reflexion_stm_min_entrees": "plancher d'entrées avant réflexion",
    "meteo_par_agent": "météo tirée par agent",
    # Ticket 100, lot 4 — deux bras dont l'un laisse le vécu d'un habitant atteindre son
    # co-résident et l'autre non n'écrivent pas la même mémoire.
    "partage_foyer": "partage de la mémoire dans le foyer",
    # 2026-09-24 — les tâches en vol bornent la taille des micro-lots : deux bras qui ne
    # fusionnent pas autant d'agents par prompt ne posent pas les mêmes questions au modèle.
    "taches_en_vol": "tâches de planification en vol",
    # ── Filiation (ticket 095, lot D) ──
    # Un enfant hérite de la MÉMOIRE de son parent : de quel parent, et ce qu'il s'autorise à
    # faire varier, appartiennent à son identité. Repris sous un autre parent, il n'est plus le
    # même bras.
    "run_parent": "run parent",
    "champs_libres": "champs déclarés libres vis-à-vis du parent",
}

# Sentinelle : le champ n'existait pas dans l'identité écrite. Ce n'est pas « réglé à None »,
# c'est « le run est antérieur au champ » — et le message de refus doit le dire, sinon on
# cherche un écart de configuration là où il n'y a qu'un écart d'âge.
ABSENT = object()


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

    # DEUX CLÉS PENDANT UNE VERSION, et l'ordre est celui de `_declaration_demandee()` :
    # `evenements` (ticket 100) d'abord, `chocs` (ticket 079) ensuite. Cette fonction ne lisait
    # QUE la seconde. Le 2026-09-22, la campagne c3 a écrit la clé neuve dans `config.yaml` — ce
    # qui est la forme canonique — et l'identité du bras TRAITÉ a enregistré « aucun » : le même
    # mot que son témoin. Deux expériences différentes passaient pour une, ce que le docstring
    # ci-dessus donne précisément pour la chose à ne pas faire.
    cfg = None
    for cle in ("evenements", "chocs"):
        bloc = getattr(reglages, cle, None)
        if bloc is not None and getattr(bloc, "enabled", False) and getattr(bloc, "fichier", None):
            cfg = bloc
            break
    if cfg is None:
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


def _routage(reglages: Any) -> tuple[list[str], dict[str, list[str]]]:
    """(instances admises, routage par catégorie) — ticket 095, lot C.

    `instances_admises` accepte une liste plate ou une table `catégorie → instances`. Un
    `sorted()` appliqué tel quel à une table rendrait ses CLÉS, c'est-à-dire des noms de
    catégories présentés comme des noms d'instances : une identité qui se compare sans jamais
    échouer, donc une vérification qui n'en est plus une.
    """
    brut = getattr(reglages.llm, "instances_admises", None)
    if isinstance(brut, dict):
        routes = {str(k): sorted(str(v) for v in (vs or [])) for k, vs in brut.items()}
        union = sorted({i for instances in routes.values() for i in instances})
        return union, routes
    return sorted(str(v) for v in (brut or [])), {}


def composer(
    reglages: Any,
    empreinte_choc: str | None = None,
    *,
    run_parent: str = "",
    champs_libres: tuple[str, ...] = (),
) -> dict:
    """L'identité de l'expérience telle que la configuration courante la décrit."""
    params = dict(getattr(reglages.agent, "llm_params", {}) or {})
    admises, routes = _routage(reglages)
    return {
        # Le modèle n'est pas un réglage à part : il est porté par les instances admises. Le
        # dériver plutôt que de lire un champ qui n'existe pas évite une clé toujours vide —
        # un champ qui ne discrimine jamais donne l'illusion d'une vérification.
        "modeles_admis": _modeles_des_instances(reglages, admises),
        "instances_admises": admises,
        # Ticket 095, lot C — le binding fonction → modèle appartient à l'expérience. Deux bras
        # qui ne routent pas les réflexions vers le même modèle n'écrivent pas la même mémoire,
        # donc ne prennent pas les mêmes décisions : l'écart mesuré cesserait d'être
        # attribuable au choc. Vide = liste plate, donc pas de routage.
        "routage_instances": routes,
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
        # ── Réglages d'expérience (lot K) ──
        "chaine_vehicules": bool(getattr(reglages.agent, "vehicle_chain_enabled", True)),
        "verrou_retour_domicile": bool(
            getattr(reglages.agent, "vehicle_return_home_lock", True)
        ),
        "seuil_troncature": float(
            getattr(reglages.agent, "mode_choice_truncation_threshold", 0.0)
        ),
        "seuil_choc": float(getattr(reglages.agent, "memoire__importance_choc", 0.7)),
        "retard_saturation": str(
            getattr(reglages.agent, "memoire__retard_saturation", "asymptote")
        ),
        "retard_gravite_max": float(
            getattr(reglages.agent, "memoire__retard_gravite_max", 0.70)
        ),
        "retard_ref_s": int(getattr(reglages.agent, "memoire__retard_ref_s", 1800)),
        "fenetre_changements_jours": int(
            getattr(reglages.agent, "memoire__fenetre_changements_jours", 14)
        ),
        "changements_max": int(getattr(reglages.agent, "memoire__changements_max", 3)),
        "mode_fenetre_changements": str(
            getattr(reglages.agent, "memoire__mode_fenetre_changements", "derivee")
        ),
        "seuil_service_changement": float(
            getattr(reglages.agent, "memoire__seuil_service_changement", 0.35)
        ),
        "plancher_changement_jours": float(
            getattr(reglages.agent, "memoire__plancher_changement_jours", 2.0)
        ),
        "plafond_changement_jours": float(
            getattr(reglages.agent, "memoire__plafond_changement_jours", 30.0)
        ),
        "reflexion_stm_min_entrees": int(
            getattr(reglages.agent, "stm_reflection_min_entries", 10)
        ),
        "meteo_par_agent": bool(getattr(reglages.agent, "weather_per_agent_dates", True)),
        "partage_foyer": bool(getattr(reglages.agent, "memoire__partage_foyer_enabled", False)),
        "taches_en_vol": int(getattr(getattr(reglages, "world", None), "worker_concurrency", 8)),
        # 2026-09-25 — espace de rejeu à prompt exact. Consigné, et vérifié au lancement par la
        # cohorte, mais HORS de `LIBELLES` : les deux bras d'un A/B le partagent, et un run
        # antérieur au champ doit rester reprenable. Rejouer ne change pas ce qu'un bras mesure,
        # seulement qui paie la réponse.
        "rejeu_ab": str(getattr(getattr(reglages, "llm", None), "rejeu_ab", "") or ""),
        # ── Filiation (lot D) ──
        "run_parent": str(run_parent or ""),
        "champs_libres": sorted(champs_libres or ()),
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
        # Muet jusqu'au 2026-09-19, et ce silence a coûté un bras de campagne : le nom du
        # répertoire de run a une granularité à la MINUTE, deux contrôleurs démarrés dans la
        # même minute le partagent, et c'est l'identité du PREMIER qui reste. Le 19 septembre
        # à 16:57, celle d'un contrôleur lancé sans les réglages d'expérience ni le choc.
        logger.info(
            f"[identite] {cible.name} déjà posée — laissée en place. Attendu à la REPRISE "
            f"d'un run nommé ; sinon, un autre contrôleur a ouvert ce répertoire avant celui-ci "
            f"et c'est SON identité qui fait foi."
        )
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
        a = attendue.get(champ, ABSENT)
        b = actuelle.get(champ, ABSENT)
        if a is ABSENT:
            # Le run repris est antérieur à ce champ : on ne SAIT PAS sous quelle valeur il a
            # tourné. Le dire ainsi, plutôt que « None au run repris », envoie chercher la
            # bonne cause — l'âge du run, pas un réglage différent.
            ecarts.append(f"{libelle} : absent du run repris, {b!r} maintenant")
            continue
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
