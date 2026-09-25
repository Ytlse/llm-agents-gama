"""Qui a été exposé à l'événement d'un run, et quand — lu dans le run, jamais supposé.

Analyse du 2026-09-25. `modal_variation_rate.py` découpait tout run en quatre phases figées sur
un choc aux jours 8-9 (« Choc d'avarie moteur J8-9 »), et le bras traité du `2026-09-24_17_50`
— un article lu au jour 11, tiré dans une fenêtre [9, 13] par foyer — s'y lisait sous un titre
qui décrivait un autre protocole. Ce module donne à chaque agent SA fenêtre, depuis ce que le
run a réellement écrit :

- `evenements.jsonl` (ou `chocs.jsonl` pour un run du 079) : les expositions réelles, datées ;
- la population du run (`population_<N>.json`) : les foyers, pour que les co-résidents d'un
  lecteur soient rangés avec lui et non avec les agents hors de tout foyer exposé ;
- la déclaration (`evenement.yaml` ou `choc.yaml`) : l'identifiant et le libellé, pour les
  titres.

Aucune dépendance au runtime : ce module se lit sans `services/llm-agents` sur le chemin.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml


@dataclass(frozen=True)
class Fenetre:
    """La fenêtre d'exposition d'un agent : celle de son foyer, pour l'événement du run."""

    evenement_id: str
    household_id: str | None
    role: str          # « expose » (a lu, a subi) | « co_resident »
    premier_jour: str  # journée simulée « AAAA-MM-JJ »
    dernier_jour: str


def lire_evenements(chemin_run: Path) -> list[dict[str, Any]]:
    """Les lignes d'exposition, `evenements.jsonl` d'abord. Jamais les deux fichiers."""
    for nom in ("evenements.jsonl", "chocs.jsonl"):
        fichier = Path(chemin_run) / nom
        if not fichier.is_file():
            continue
        lignes = []
        for brute in fichier.read_text(encoding="utf-8").splitlines():
            brute = brute.strip()
            if not brute:
                continue
            try:
                objet = json.loads(brute)
            except json.JSONDecodeError:
                continue
            if isinstance(objet, dict):
                lignes.append(objet)
        if lignes:
            return lignes
    return []


def menages(chemin_run: Path) -> dict[str, str]:
    """person_id → household_id, depuis la population du run. Vide si elle manque."""
    for fichier in sorted(Path(chemin_run).glob("population_*.json")):
        if "_checkpoint_" in fichier.name:
            continue
        try:
            personnes = json.loads(fichier.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(personnes, list):
            continue
        return {
            str(p.get("person_id")): str((p.get("household") or {}).get("id"))
            for p in personnes
            if isinstance(p, dict) and (p.get("household") or {}).get("id")
        }
    return {}


def declaration(chemin_run: Path) -> dict[str, Any]:
    """`evenement.yaml`, sinon `choc.yaml`. Vide si le run n'en déclare aucune."""
    for nom in ("evenement.yaml", "choc.yaml"):
        fichier = Path(chemin_run) / nom
        if not fichier.is_file():
            continue
        try:
            contenu = yaml.safe_load(fichier.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if isinstance(contenu, dict):
            return contenu
    return {}


def libelle(chemin_run: Path) -> str | None:
    """« a09_vent_autan — Autan gales, parks closed », ou `None` sans déclaration."""
    decl = declaration(chemin_run)
    identifiant = decl.get("evenement") or decl.get("choc")
    if not identifiant:
        return None
    texte = decl.get("libelle")
    return f"{identifiant} — {texte}" if texte else str(identifiant)


def fenetres(chemin_run: Path,
             journee_de: Callable[[dict], str | None]) -> dict[str, Fenetre]:
    """person_id → sa fenêtre. Un agent absent du dictionnaire n'est dans aucun foyer exposé.

    `journee_de(ligne)` date une exposition (celle d'`evenement_par_jour.csv`, voir
    `calcul.journee_de_l_exposition`). Les lignes `origine: entendu` du ticket 111 ne sont pas
    des expositions : le membre informé est un co-résident, et il est rangé comme tel.
    """
    lignes = [e for e in lire_evenements(chemin_run) if e.get("origine") != "entendu"]
    if not lignes:
        return {}
    foyer_de = menages(chemin_run)
    # (événement, foyer) → première et dernière journée, lecteurs.
    par_foyer: dict[tuple[str, str], dict[str, Any]] = {}
    for e in lignes:
        agent = str(e.get("person_id") or "")
        identifiant = str(e.get("evenement_id") or e.get("choc_id") or "")
        journee = journee_de(e)
        if not (agent and identifiant and journee):
            continue
        foyer = foyer_de.get(agent) or f"seul:{agent}"
        info = par_foyer.setdefault((identifiant, foyer),
                                    {"premier": journee, "dernier": journee, "lecteurs": set()})
        info["premier"] = min(info["premier"], journee)
        info["dernier"] = max(info["dernier"], journee)
        info["lecteurs"].add(agent)

    resultat: dict[str, Fenetre] = {}
    for (identifiant, foyer), info in sorted(par_foyer.items()):
        seul = foyer.startswith("seul:")
        membres = [foyer.split(":", 1)[1]] if seul else sorted(
            p for p, h in foyer_de.items() if h == foyer)
        for p in membres:
            # Un agent de deux foyers exposés n'existe pas ; deux événements sur un même foyer
            # gardent la PREMIÈRE fenêtre, qui est celle d'avant tout changement.
            resultat.setdefault(p, Fenetre(
                evenement_id=identifiant, household_id=None if seul else foyer,
                role="expose" if p in info["lecteurs"] else "co_resident",
                premier_jour=info["premier"], dernier_jour=info["dernier"],
            ))
    return resultat
