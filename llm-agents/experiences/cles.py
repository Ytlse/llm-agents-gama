"""Jeu de clés API d'une expérience (ticket 035, spec parallelisation_experiences, R4/R8/R9).

Le débit LLM est plafonné **par clé API** côté fournisseur : deux expériences qui partagent une
clé se disputent le même quota. Ce module dérive, d'un **modèle** épinglé, l'ensemble des
**identités de clé** que l'expérience est susceptible de solliciter — la base du garde-fou
parallèle/série (`reservations.py`).

Identité de clé d'une instance (résolution du gateway, `llm_gateway/config/settings.py`) :
`PROVIDER_KEYS[nom_instance]` s'il existe, sinon `PROVIDER_KEYS[adapter]` (adapter = champ
`adapter`, à défaut le nom de l'instance). Côté expériences, on ne connaît pas les entrées
`PROVIDER_KEYS` du gateway ; on retient donc l'**adapter** (ou le nom d'instance à défaut) comme
identité. C'est CONSERVATEUR : deux instances d'un même adapter sont réputées partager une clé
même si le gateway leur attribuait des clés distinctes — on peut sérialiser à tort, jamais
paralléliser à tort (fail-safe, cohérent avec R12). Un override par instance visible dans
l'environnement (`(LLM_GATEWAY_)PROVIDER_KEYS__<instance>`) est respecté s'il est présent.
"""

from __future__ import annotations

import os
import re

from experiences.ressources import instances_pour_modele

# Rang de clé dans un nom d'instance : `google_gemini35_key2` → « 2 ».
_RANG_CLE = re.compile(r"_key(\d+)$")


def _override_instance_present(nom_instance: str) -> bool:
    """Une clé propre à cette instance est-elle déclarée dans l'environnement ?"""
    cible = nom_instance.lower()
    for var in os.environ:
        bas = var.lower()
        for prefixe in ("provider_keys__", "llm_gateway_provider_keys__"):
            if bas.startswith(prefixe) and bas[len(prefixe) :] == cible:
                return True
    return False


def identite_cle(nom_instance: str, cfg: dict) -> str:
    """Identité de la clé API servie par une instance (cf. docstring du module)."""
    adapter = cfg.get("adapter") if isinstance(cfg, dict) else None
    # Convention <modèle>_key<N> (2026-09-08) : le nom porte le RANG de la clé, donc la clé
    # physique se lit `<adapter>_key<N>`. C'est ce qu'il faut retenir, PAS le nom d'instance :
    # `google_gemini31_key1` et `google_gemini35_key1` sont deux modèles sur UNE clé — les
    # traiter comme deux identités les ferait tourner en parallèle sur le même quota, l'erreur
    # que ce module s'interdit. Symétriquement, `…_key1` et `…_key2` sont bien deux clés, là
    # où l'ancienne règle par adapter les confondait.
    m = _RANG_CLE.search(nom_instance)
    if m and adapter:
        return f"{adapter}_key{m.group(1)}"
    if _override_instance_present(nom_instance):
        return nom_instance
    return str(adapter or nom_instance)


def jeu_de_cles(
    modele: str,
    providers: dict[str, dict],
    instances_admises: list[str] | None = None,
    portee: str | None = None,
) -> set[str]:
    """Ensemble des identités de clé qu'une expérience sur `modele` peut solliciter.

    `instances_admises`, s'il est fourni, restreint aux instances effectivement disponibles
    (clé présente, quota non épuisé) : les instances sans clé disponible ne comptent pas (R9).
    Un modèle sans instance (rejeu, décideur local, offre nulle) donne un jeu **vide** (R8/R9).

    `portee` restreint au bord épinglé par l'expérience (`local` / `distant`) : un modèle servi
    des deux côtés ne doit pas réserver le quota du distant quand l'expérience tourne en local.
    Note : toutes les instances LM Studio partagent l'adapter `openai_compatible`, donc UNE
    identité de clé — deux expériences locales se sérialisent, ce qu'on veut sur une machine.
    """
    instances = instances_pour_modele(modele, providers, portee)
    if instances_admises is not None:
        garde = set(instances_admises)
        instances = [i for i in instances if i in garde]
    return {identite_cle(i, providers.get(i, {})) for i in instances}


__all__ = ["identite_cle", "jeu_de_cles"]
