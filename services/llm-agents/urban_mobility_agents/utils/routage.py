"""Quelles instances de passerelle servent quelle FONCTION — ticket 095, lot C.

CE QUI EXISTAIT DÉJÀ
--------------------
La plomberie est complète : `LLMRequest` porte `force_provider` et `instances_admises`, tous
deux traversant `api/routes.py`, `config/settings.py` et `worker/task_worker.py`, et le SDK
accepte `instances_admises` **par appel** dans le payload. Ce qui manquait tenait en un endroit :
l'appelant lisait une liste globale unique, et les 751 requêtes de la campagne du ticket 077 sont
donc toutes parties sur la même famille de modèles.

LA RÈGLE
--------
`settings.llm.instances_admises` accepte une table `catégorie → instances` en plus d'une liste
plate. La clé `defaut` sert de repli à toute catégorie non nommée.

**JAMAIS `force_provider`.** `task_worker.py` ne retente que si `force_provider is None` : un
épinglage dur supprime le repli. Les quatorze `HTTP 503 high demand` de la campagne sont passés
précisément parce qu'il restait une seconde clé. D'où le minimum de DEUX instances par
catégorie, et une alarme en deçà — une liste blanche à une entrée est un épinglage dur qui ne
dit pas son nom.
"""

from __future__ import annotations

from loguru import logger
from settings import settings

# Clé de repli dans la table. Sans elle, une catégorie non nommée ne serait restreinte par rien.
CLE_DEFAUT = "defaut"
# En deçà, un 503 est un échec sec : il n'existe pas de seconde clé vers laquelle basculer.
INSTANCES_MIN = 2

_ALARMES_DITES: set[str] = set()


def reinitialiser() -> None:
    """Oublie les alarmes déjà levées. Réservé aux tests."""
    _ALARMES_DITES.clear()


def table() -> dict[str, list[str]]:
    """Le routage déclaré, sous forme de table. Vide quand une liste plate est déclarée."""
    brut = getattr(settings.llm, "instances_admises", None)
    if isinstance(brut, dict):
        return {str(k): [str(v) for v in (vs or [])] for k, vs in brut.items()}
    return {}


def liste_plate() -> list[str]:
    """La liste plate déclarée, ou le `defaut` de la table. Vide = aucune restriction."""
    brut = getattr(settings.llm, "instances_admises", None)
    if isinstance(brut, dict):
        return [str(v) for v in (brut.get(CLE_DEFAUT) or [])]
    return [str(v) for v in (brut or [])]


def toutes_les_instances() -> list[str]:
    """L'union de tout ce qui est admis, quel que soit le format. Sert à l'identité du run."""
    vues: set[str] = set(liste_plate())
    for instances in table().values():
        vues.update(instances)
    return sorted(vues)


def instances_pour(categorie: str | None) -> list[str]:
    """Les instances admises à servir cette catégorie. Liste vide = aucune restriction.

    Une catégorie absente de la table retombe sur `defaut`, jamais sur rien : un repli sur la
    liste vide lèverait la restriction au moment précis où on croit l'avoir resserrée.
    """
    routes = table()
    if routes:
        admises = routes.get(str(categorie)) if categorie else None
        if admises is None:
            admises = routes.get(CLE_DEFAUT) or []
    else:
        admises = liste_plate()
    admises = list(dict.fromkeys(str(a) for a in admises if a))
    if admises and len(admises) < INSTANCES_MIN:
        _alarme(
            f"min:{categorie}",
            f"[ALARME] [routage] la catégorie {categorie!r} n'a qu'UNE instance admise "
            f"({admises}) — un HTTP 503 devient alors un échec sec, sans repli. Déclarer au "
            f"moins {INSTANCES_MIN} instances, ou n'en restreindre aucune.",
        )
    return admises


def _alarme(cle: str, message: str) -> None:
    if cle in _ALARMES_DITES:
        return
    _ALARMES_DITES.add(cle)
    logger.error(message)


def journal_du_routage() -> str:
    """Une ligne lisible du routage en vigueur, à poser au démarrage."""
    routes = table()
    if not routes:
        plate = liste_plate()
        return (
            f"liste plate pour toutes les catégories : {plate}" if plate
            else "aucune restriction — la cascade choisit librement"
        )
    return " · ".join(f"{cat}={instances}" for cat, instances in sorted(routes.items()))
