"""Runs enfants — ticket 095, lot D.

LE PROBLÈME, EN UN CHIFFRE
--------------------------
Les quatorze premiers jours de la campagne appariée du ticket 077 sont identiques dans les trois
bras : **44 décisions, 0 écart**. Elles sont payées trois fois. Sur onze bras au programme, c'est
environ un tiers du coût de chaque bras additionnel jeté.

LE PRINCIPE
-----------
Un run PARENT joue le socle commun jusqu'à la veille du choc et se fige. Chaque bras démarre
depuis ce point de reprise, dans SON répertoire, avec SES réglages. Les mécanismes existent
déjà : points de reprise (ticket 075), rejeu à mémoire gelée, identité de run (ticket 091). Ce
module n'ajoute que la filiation et ses garde-fous.

CE QU'UN ENFANT A LE DROIT DE CHANGER
-------------------------------------
Rien, sauf ce qu'il DÉCLARE. `CHAMPS_LIBRES` nomme les champs d'identité que ce bras fait varier
— typiquement `choc` et `mode_fenetre_changements`. Tout autre écart fait refuser le démarrage,
en nommant le champ, exactement comme une reprise mal nommée.

Le sens de la règle : un enfant hérite de la MÉMOIRE de son parent. Si la population, le modèle
ou les graines diffèrent, cette mémoire décrit une autre expérience que celle que l'enfant va
jouer — et rien, dans les sorties, ne le dirait.

⚠ **Aucune échappatoire.** Comme pour l'identité de run, les cas de mise au point se traitent à
la main, hors du code : un contournement livré dans le produit finirait par servir en mesure.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from loguru import logger
from urban_mobility_agents.utils import identite_run, reprise

# Variables d'environnement de la filiation.
ENV_PARENT = "RUN_PARENT"
ENV_CHAMPS_LIBRES = "CHAMPS_LIBRES"


class FiliationRefusee(RuntimeError):
    """L'enfant ne peut pas hériter de ce parent."""


def parent_declare() -> str:
    """Le run parent nommé, ou une chaîne vide."""
    return (os.environ.get(ENV_PARENT) or "").strip()


def champs_libres() -> tuple[str, ...]:
    """Les champs d'identité que cet enfant déclare faire varier.

    Un champ inconnu est REFUSÉ et non ignoré : `fenetre_changement` au lieu de
    `fenetre_changements_jours` laisserait passer un écart qu'on croyait avoir déclaré.
    """
    brut = (os.environ.get(ENV_CHAMPS_LIBRES) or "").strip()
    if not brut:
        return ()
    demandes = tuple(c.strip() for c in brut.split(",") if c.strip())
    inconnus = [c for c in demandes if c not in identite_run.LIBELLES]
    if inconnus:
        raise FiliationRefusee(
            f"{ENV_CHAMPS_LIBRES} nomme des champs d'identité qui n'existent pas : "
            f"{inconnus}. Champs connus : {sorted(identite_run.LIBELLES)}."
        )
    return demandes


def repertoire_parent(nom: str, racine: Path) -> Path:
    """Le répertoire du parent : un chemin tel quel, sinon un nom sous la racine des runs."""
    chemin = Path(nom)
    if chemin.is_dir():
        return chemin
    for candidat in (racine / nom, racine.parent / nom):
        if candidat.is_dir():
            return candidat
    raise FiliationRefusee(
        f"run parent introuvable : {nom!r} (cherché tel quel, puis sous {racine} et "
        f"{racine.parent})"
    )


def ecarts_interdits(
    parent: dict, courante: dict, libres: tuple[str, ...]
) -> list[str]:
    """Les écarts d'identité que cet enfant n'a PAS déclarés. Liste vide = filiation admise."""
    return [
        ecart
        for champ, ecart in _ecarts_par_champ(parent, courante).items()
        if champ not in libres
    ]


def _ecarts_par_champ(parent: dict, courante: dict) -> dict[str, str]:
    ecarts: dict[str, str] = {}
    for champ, libelle in identite_run.LIBELLES.items():
        a = parent.get(champ, identite_run.ABSENT)
        b = courante.get(champ, identite_run.ABSENT)
        if a is identite_run.ABSENT:
            ecarts[champ] = f"{libelle} : absent du run parent, {b!r} chez l'enfant"
        elif a != b:
            ecarts[champ] = f"{libelle} : {a!r} chez le parent, {b!r} chez l'enfant"
    return ecarts


def amorcer(workdir: Path, parent_dir: Path, identite_courante: dict) -> dict:
    """Vérifie la filiation, puis copie le point de reprise du parent chez l'enfant.

    Rend la description du point copié. Lève `FiliationRefusee` plutôt que de démarrer un bras
    qui hériterait d'une mémoire produite sous d'autres réglages.
    """
    libres = champs_libres()
    identite_parent = identite_run.lire(parent_dir)
    if identite_parent is None:
        raise FiliationRefusee(
            f"le run parent {parent_dir.name} ne porte pas d'identité "
            f"({identite_run.FICHIER} absent ou illisible) : impossible de dire de quelle "
            f"expérience vient sa mémoire."
        )

    interdits = ecarts_interdits(identite_parent, identite_courante, libres)
    if interdits:
        raise FiliationRefusee(
            f"l'enfant diffère de son parent {parent_dir.name} sur des champs NON déclarés "
            f"dans {ENV_CHAMPS_LIBRES} :\n  - " + "\n  - ".join(interdits)
            + f"\nChamps déclarés libres : {list(libres) or 'aucun'}."
        )

    trouve = reprise.dernier_point(parent_dir)
    if trouve is None:
        raise FiliationRefusee(
            f"le run parent {parent_dir.name} n'a AUCUN point de reprise valide : il n'y a "
            f"rien dont hériter. Un parent se joue jusqu'à la veille du choc, puis se fige."
        )
    source, meta = trouve

    destination = Path(workdir) / reprise.POINTS / source.name
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    logger.info(
        f"[filiation] {Path(workdir).name} hérite de {parent_dir.name} au jour simulé "
        f"{meta.get('jour_simule')} ({meta.get('horodatage_simule')}) — champs libres : "
        f"{list(libres) or 'aucun'}"
    )
    return meta


def decisions(workdir: Path, jusqu_a: float | None = None) -> dict[tuple[str, str, float], str]:
    """Les décisions tracées d'un run, indexées par (personne, activité, instant).

    C'est la trace du ticket 090, déjà écrite pendant la vie normale de tout run — aucune
    instrumentation neuve n'est nécessaire pour comparer un enfant à son parent.
    """
    fichier = Path(workdir) / "decisions_rejeu.jsonl"
    vues: dict[tuple[str, str, float], str] = {}
    if not fichier.is_file():
        return vues
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            trace = json.loads(ligne)
        except ValueError:
            continue
        instant = float(trace.get("instant", 0.0))
        if jusqu_a is not None and instant > jusqu_a:
            continue
        cle = (str(trace.get("personne")), str(trace.get("activite")), instant)
        vues[cle] = str(trace.get("code_plan"))
    return vues


def ecarts_de_reproduction(
    parent_dir: Path, workdir: Path, jusqu_a: float | None
) -> list[str]:
    """Les décisions qui diffèrent entre parent et enfant sur les jours COMMUNS.

    Liste vide = l'enfant a bien rejoué le socle de son parent. Un seul écart et l'économie
    est un mensonge : les deux bras ne partagent plus la baseline qu'on croit leur avoir
    donnée, et la comparaison porte sur deux histoires différentes.
    """
    du_parent = decisions(parent_dir, jusqu_a)
    de_l_enfant = decisions(workdir, jusqu_a)
    ecarts: list[str] = []
    for cle, code in sorted(du_parent.items(), key=lambda kv: kv[0][2]):
        if cle not in de_l_enfant:
            ecarts.append(f"{cle[0]} · {cle[1]} : décidée chez le parent, absente chez l'enfant")
        elif de_l_enfant[cle] != code:
            ecarts.append(
                f"{cle[0]} · {cle[1]} : {code!r} chez le parent, {de_l_enfant[cle]!r} chez l'enfant"
            )
    return ecarts


def verifier_reproduction(parent_dir: Path, workdir: Path, jusqu_a: float | None) -> None:
    """Journalise la recette de reproduction. Une divergence lève une `[ALARME]`, chiffrée."""
    ecarts = ecarts_de_reproduction(parent_dir, workdir, jusqu_a)
    communes = len(decisions(parent_dir, jusqu_a))
    if not ecarts:
        logger.info(
            f"[filiation] rejeu conforme : {communes} décision(s) du parent "
            f"{parent_dir.name} reproduites à l'identique."
        )
        return
    logger.error(
        f"[ALARME] [filiation] {len(ecarts)}/{communes} décision(s) du socle commun DIFFÈRENT "
        f"entre {parent_dir.name} et {Path(workdir).name} — les deux bras ne partagent plus la "
        f"baseline qu'on croit leur avoir donnée :\n  - " + "\n  - ".join(ecarts[:10])
        + ("\n  - …" if len(ecarts) > 10 else "")
    )
