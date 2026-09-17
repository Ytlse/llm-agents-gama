#!/usr/bin/env python3
"""Extrait une petite population de test depuis une population scellée (ticket 075).

POURQUOI
--------
Observer la mémoire d'un agent sur soixante jours demande de la LIRE, agent par agent. À mille
agents, personne ne lit ; à cinq, tout se lit. Ce script prélève cinq habitants d'un sceau
existant **sans toucher à leurs champs** : les agents extraits sont les agents du sceau, pas des
agents fabriqués pour l'occasion.

CE QUE CE N'EST PAS
-------------------
Le fichier produit n'est **pas un sceau AAMAS** et son MANIFEST le dit. Cinq agents ne
représentent rien : ils servent à observer un mécanisme, jamais à mesurer une part modale.
`data/population/population_1000_AAMAS_v6` reste la référence de l'article.

DÉTERMINISME
------------
Aucun tirage aléatoire. Chaque profil est un PRÉDICAT ; l'agent retenu est le premier qui le
satisfait dans l'ordre des identifiants numériques. Deux extractions de la même source rendent
les mêmes cinq identifiants, et le critère de chaque choix est écrit dans le MANIFEST.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Profils recherchés, dans l'ordre. Le but est le CONTRASTE : cinq mémoires qui ne peuvent pas
# converger par construction, parce que les vécus qui les alimentent n'ont rien en commun.
# Chaque profil porte la raison pour laquelle il est là — un profil sans raison serait un
# cinquième agent tiré au hasard sous un nom savant.
PROFILS: list[tuple[str, str, Callable[[dict], bool]]] = []


def _traits(personne: dict) -> dict:
    return (personne.get("identity") or {}).get("traits_json") or {}


def _activites(personne: dict) -> list:
    return (personne.get("identity") or {}).get("activities") or []


def _motifs(personne: dict) -> set:
    return {a.get("purpose") for a in _activites(personne)} - {"home", None}


def _profil(nom: str, raison: str):
    def decorateur(predicat: Callable[[dict], bool]):
        PROFILS.append((nom, raison, predicat))
        return predicat

    return decorateur


@_profil(
    "pendulaire_voiture",
    "Travail à temps plein, voiture toujours disponible, permis, sans abonnement de "
    "transport collectif, domicile hors de Toulouse : le cas où la voiture est le choix "
    "par défaut et où la mémoire doit peser fort pour en faire dévier.",
)
def _pendulaire_voiture(p: dict) -> bool:
    t = _traits(p)
    return (
        t.get("main_occupation") == "Full-time worker"
        and t.get("car_availability") == "all"
        and bool(t.get("has_driving_license"))
        and not t.get("has_pt_subscription")
        and t.get("residence_zone") != "Toulouse"
        and "work" in _motifs(p)
        and len(_activites(p)) >= 4
    )


@_profil(
    "cycliste_urbain",
    "Vélo personnel, domicile à Toulouse, voiture peu ou pas disponible : le profil le plus "
    "sensible à la météo et aux incidents, donc celui où les souvenirs marquants doivent "
    "apparaître le plus vite.",
)
def _cycliste_urbain(p: dict) -> bool:
    t = _traits(p)
    return (
        t.get("personal_bike") not in (None, "", "No bike")
        and t.get("residence_zone") == "Toulouse"
        and t.get("car_availability") in ("none", "some")
        and bool(_motifs(p) & {"work", "education"})
        and len(_activites(p)) >= 4
    )


@_profil(
    "usager_transport_collectif",
    "Abonnement de transport collectif et aucune voiture : la mémoire porte ici sur la "
    "fiabilité des lignes, c'est-à-dire sur des concepts qui se confirment et se contredisent.",
)
def _usager_tc(p: dict) -> bool:
    t = _traits(p)
    return (
        bool(t.get("has_pt_subscription"))
        and t.get("car_availability") == "none"
        and len(_activites(p)) >= 4
    )


@_profil(
    "scolaire",
    "Élève mineur avec une activité d'études : trajets très réguliers, donc un cas où une "
    "habitude doit se former nettement et où toute rupture se voit.",
)
def _scolaire(p: dict) -> bool:
    t = _traits(p)
    age = t.get("age")
    return (
        t.get("main_occupation") == "Pupil (up to Baccalaureate)"
        and "education" in _motifs(p)
        and isinstance(age, int)
        and age < 18
    )


@_profil(
    "retraite_multi_motifs",
    "Retraité avec au moins deux motifs distincts hors domicile : agenda irrégulier, donc "
    "une mémoire qui ne peut pas se réduire à un aller-retour répété.",
)
def _retraite_multi_motifs(p: dict) -> bool:
    t = _traits(p)
    return (
        t.get("main_occupation") == "Retired"
        and len(_motifs(p)) >= 2
        and len(_activites(p)) >= 4
    )


def _cle_tri(personne: dict) -> tuple:
    """Ordre stable : l'identifiant numérique quand il l'est, sinon l'ordre lexical."""
    pid = str(personne.get("person_id", ""))
    return (0, int(pid), "") if pid.isdigit() else (1, 0, pid)


def choisir(population: list[dict]) -> list[tuple[str, str, dict]]:
    """Un agent par profil, sans doublon, dans l'ordre des profils déclarés."""
    candidats = sorted(
        (p for p in population if not p.get("immobile") and len(_activites(p)) >= 2),
        key=_cle_tri,
    )
    retenus: list[tuple[str, str, dict]] = []
    deja: set[str] = set()
    for nom, raison, predicat in PROFILS:
        for personne in candidats:
            pid = str(personne.get("person_id"))
            if pid in deja or not predicat(personne):
                continue
            retenus.append((nom, raison, personne))
            deja.add(pid)
            break
        else:
            raise SystemExit(
                f"Aucun agent ne satisfait le profil « {nom} » dans cette source. "
                f"Le profil n'est pas relâché en silence : corrigez son prédicat ou "
                f"changez de source."
            )
    return retenus


def sha256(chemin: Path) -> str:
    empreinte = hashlib.sha256()
    with chemin.open("rb") as flux:
        for bloc in iter(lambda: flux.read(1 << 20), b""):
            empreinte.update(bloc)
    return empreinte.hexdigest()


def main() -> None:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--source", required=True, type=Path, help="population.json scellée")
    parseur.add_argument("--sortie", required=True, type=Path, help="répertoire à créer")
    args = parseur.parse_args()

    population = json.loads(args.source.read_text(encoding="utf-8"))
    retenus = choisir(population)

    args.sortie.mkdir(parents=True, exist_ok=True)
    fichier = args.sortie / "population.json"
    # Les agents sont recopiés TELS QUELS : aucune normalisation, aucun champ ajouté. Une
    # population de test qui diverge du sceau dont elle sort ne prouve plus rien.
    fichier.write_text(
        json.dumps([p for _, _, p in retenus], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lignes = [
        "# Population de TEST — ticket 075. Ce n'est PAS un sceau AAMAS.",
        "#",
        "# Cinq agents ne représentent rien : ils servent à LIRE l'évolution d'une mémoire,",
        "# jamais à mesurer une part modale. La référence de l'article reste",
        "# data/population/population_1000_AAMAS_v6.",
        f"nom: {args.sortie.name}",
        f"extrait_le: '{datetime.now(timezone.utc).isoformat()}'",
        "source:",
        f"  fichier: {args.source.as_posix()}",
        f"  sha256: {sha256(args.source)}",
        f"  n: {len(population)}",
        "population:",
        "  fichier: population.json",
        f"  sha256: {sha256(fichier)}",
        f"  n: {len(retenus)}",
        "selection:",
        "  methode: >-",
        "    Aucun tirage aléatoire. Chaque profil est un prédicat ; l'agent retenu est le",
        "    premier qui le satisfait dans l'ordre des identifiants numériques. Reproductible",
        "    par scripts/data/population/extraire_sous_population.py.",
        "  profils:",
    ]
    for nom, raison, personne in retenus:
        traits = _traits(personne)
        lignes += [
            f"    - profil: {nom}",
            f"      person_id: '{personne.get('person_id')}'",
            f"      nom_persona: {json.dumps(traits.get('name', ''), ensure_ascii=False)}",
            f"      age: {traits.get('age')}",
            f"      occupation: {json.dumps(traits.get('main_occupation', ''), ensure_ascii=False)}",
            f"      commune: {json.dumps(traits.get('residence_commune', ''), ensure_ascii=False)}",
            f"      zone: {json.dumps(traits.get('residence_zone', ''), ensure_ascii=False)}",
            f"      voiture: {json.dumps(traits.get('car_availability', ''), ensure_ascii=False)}",
            f"      velo: {json.dumps(traits.get('personal_bike', ''), ensure_ascii=False)}",
            f"      abonnement_tc: {bool(traits.get('has_pt_subscription'))}",
            f"      activites: {len(_activites(personne))}",
            f"      motifs: {json.dumps(sorted(m for m in _motifs(personne)), ensure_ascii=False)}",
            f"      raison: >-",
            f"        {raison}",
        ]
    (args.sortie / "MANIFEST.yaml").write_text("\n".join(lignes) + "\n", encoding="utf-8")

    print(f"{len(retenus)} agents écrits → {fichier}")
    for nom, _, personne in retenus:
        traits = _traits(personne)
        print(
            f"  {nom:28s} person_id={personne.get('person_id'):>5s}  "
            f"{traits.get('name', ''):24s} {traits.get('main_occupation', '')}"
        )


if __name__ == "__main__":
    main()
