"""Espaces de travail du registre d'expériences — spec `espaces-de-travail-experiences.md`.

Un espace est une **vue** : il restreint ce que le registre affiche, il ne range rien (R7).
Aucun fichier d'expérience n'est lu, écrit ni déplacé ici — ce module ne connaît que des
noms, et un nom n'y sert qu'à filtrer un tableau.

**Il échoue ouvert.** Fichier absent, illisible, mal formé, entrée sans nom : le module
journalise et rend ce qu'il peut, jusqu'à la liste vide. Le registre reste alors sur
« Toutes les expériences » et demeure utilisable (R13). Un fichier de confort ne doit jamais
fermer la porte du tableau de bord.

Le nom d'une expérience se calcule depuis ses paramètres (spec `nommage-canonique-experiences`)
et ne peut donc pas porter sa phase. C'est l'étiquette `phase` de chaque entrée qui fait le
lien, et elle ne vit que dans cette vue (R6a).
"""

from __future__ import annotations

import logging
import unicodedata
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
FICHIER = Path(__file__).resolve().parent / "espaces_experiences.yaml"

#: L'espace qui n'en est pas un : toujours en tête du menu, toujours présent (R2, R3).
TOUTES = "Toutes les expériences"


def _sain(nom: object) -> Optional[str]:
    """Le nom d'expérience s'il est utilisable comme libellé, sinon None.

    Le fichier est écrit à la main : il est faillible par accident plus que par
    malveillance. On refuse quand même tout ce qui pourrait sortir de `data/experiences/`
    si un appelant s'avisait d'en faire un chemin — séparateurs, remontées, caractères de
    contrôle — parce qu'une garde ici coûte trois lignes et qu'une garde oubliée se paie
    ailleurs (spec, § Sécurité).
    """
    if not isinstance(nom, str):
        return None
    n = nom.strip()
    if not n or n in (".", ".."):
        return None
    if "/" in n or "\\" in n or "\x00" in n:
        return None
    if any(unicodedata.category(c) == "Cc" for c in n):
        return None
    return n


def _lire(chemin: Optional[Path] = None) -> dict:
    """Le contenu brut du fichier, ou {} — jamais d'exception vers l'appelant (R13)."""
    p = Path(chemin) if chemin is not None else FICHIER
    if not p.is_file():
        logger.info("[espaces] aucun fichier d'espaces (%s) : seul « %s » sera proposé", p, TOUTES)
        return {}
    try:
        contenu = yaml.safe_load(p.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        logger.warning("[espaces] fichier illisible (%s) : %s — repli sur « %s »", p, e, TOUTES)
        return {}
    if not isinstance(contenu, dict):
        logger.warning("[espaces] contenu inattendu dans %s (%s, attendu un dictionnaire) — repli sur « %s »",
                       p, type(contenu).__name__, TOUTES)
        return {}
    return contenu


def espaces(chemin: Optional[Path] = None) -> list[dict]:
    """Les espaces définis, dans l'ordre du fichier. Liste vide si rien n'est exploitable.

    Une entrée sans nom d'expérience utilisable est ignorée AVEC un message : la taire
    ferait disparaître une ligne du registre sans que rien ne le dise.
    """
    brut = _lire(chemin)
    liste = brut.get("espaces")
    if not isinstance(liste, list):
        if liste is not None:
            logger.warning("[espaces] clé `espaces` de type %s (attendu une liste) — ignorée", type(liste).__name__)
        return []
    resultat: list[dict] = []
    vus: set[str] = set()
    for i, e in enumerate(liste):
        if not isinstance(e, dict):
            logger.warning("[espaces] entrée %d ignorée : %s au lieu d'un espace", i, type(e).__name__)
            continue
        nom = _sain(e.get("nom"))
        if not nom:
            logger.warning("[espaces] espace %d ignoré : nom absent ou invalide (%r)", i, e.get("nom"))
            continue
        if nom == TOUTES or nom in vus:
            logger.warning("[espaces] espace %r ignoré : nom réservé ou déjà défini", nom)
            continue
        entrees = []
        brutes = e.get("entrees")
        if not isinstance(brutes, list):
            if brutes is not None:
                logger.warning("[espaces] espace %r : `entrees` de type %s (attendu une liste)",
                               nom, type(brutes).__name__)
            brutes = []
        for j, x in enumerate(brutes):
            if isinstance(x, str):           # forme courte : le nom seul, sans phase
                x = {"experience": x}
            if not isinstance(x, dict):
                logger.warning("[espaces] espace %r, entrée %d ignorée : %s", nom, j, type(x).__name__)
                continue
            exp = _sain(x.get("experience"))
            if not exp:
                logger.warning("[espaces] espace %r, entrée %d ignorée : nom d'expérience invalide (%r)",
                               nom, j, x.get("experience"))
                continue
            entrees.append({
                "experience": exp,
                "phase": (x.get("phase") or "").strip() or None,
                "optionnel": bool(x.get("optionnel")),
                "note": (x.get("note") or "").strip() or None,
            })
        resultat.append({"nom": nom, "note": (e.get("note") or "").strip() or None, "entrees": entrees})
        vus.add(nom)
    return resultat


def noms(chemin: Optional[Path] = None) -> list[str]:
    """Les libellés du menu déroulant : « Toutes les expériences » d'abord, toujours (R2)."""
    return [TOUTES, *(e["nom"] for e in espaces(chemin))]


def espace(nom: Optional[str], chemin: Optional[Path] = None) -> Optional[dict]:
    """L'espace de ce nom, ou None — y compris pour `TOUTES`, qui n'a pas de définition."""
    if not nom or nom == TOUTES:
        return None
    for e in espaces(chemin):
        if e["nom"] == nom:
            return e
    return None


def entrees(nom: Optional[str], chemin: Optional[Path] = None) -> list[dict]:
    """Les entrées de cet espace, dans l'ordre du fichier. Vide si l'espace est inconnu."""
    e = espace(nom, chemin)
    return list(e["entrees"]) if e else []


def index(nom: Optional[str], chemin: Optional[Path] = None) -> dict[str, dict]:
    """Les entrées indexées par nom d'expérience — ce que le registre interroge par ligne."""
    return {x["experience"]: x for x in entrees(nom, chemin)}


def actif_valide(nom: Optional[str], chemin: Optional[Path] = None) -> str:
    """Le nom d'espace à utiliser réellement, `TOUTES` si celui-ci n'existe plus (R14)."""
    if not nom or nom == TOUTES:
        return TOUTES
    if espace(nom, chemin) is None:
        logger.warning("[espaces] l'espace mémorisé %r n'existe plus — retour à « %s »", nom, TOUTES)
        return TOUTES
    return nom


def filtrer(lignes: list[dict], nom: Optional[str], chemin: Optional[Path] = None,
            cle: str = "experience") -> list[dict]:
    """Les lignes du registre que cet espace laisse voir (R4). `TOUTES` ne filtre rien (R3)."""
    if not nom or nom == TOUTES:
        return list(lignes)
    dedans = index(nom, chemin)
    return [l for l in lignes if l.get(cle) in dedans]


def manquantes(presentes: set[str] | list[str], nom: Optional[str],
               chemin: Optional[Path] = None) -> list[str]:
    """Les expériences citées par l'espace et absentes du disque (R9).

    Ce n'est PAS une erreur : l'espace se remplit avant les dossiers, et la liste sert à
    l'annoncer. Elle vaut aussi alarme discrète le jour où un dossier disparaît.
    """
    vues = set(presentes)
    return [x["experience"] for x in entrees(nom, chemin) if x["experience"] not in vues]
