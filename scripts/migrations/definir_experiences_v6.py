#!/usr/bin/env python3
"""Ticket 074, lot D — (re)crée les définitions d'expériences sur la cohorte v6.

POURQUOI CE SCRIPT EXISTE. Le lot A a envoyé les 24 définitions à l'archive froide, où elles
sont restaurables et auditables, mais où la doctrine interdit de les *référencer*. La campagne
v6 ne peut donc pas « rejouer » l'existant : il faut des définitions NEUVES, qui nomment la
cohorte v6, le jeu v6 et les nouveaux noms de variantes de prompt.

CE QU'IL FAIT EXACTEMENT, ET CE QU'IL NE FAIT PAS. Il LIT les YAML archivés comme une
**spécification** — températures, graines, tolérances horaires, artefacts de modèle, drapeaux
de chaîne : des paramètres qu'aucun humain n'a envie de retaper vingt-deux fois. Il ÉCRIT des
définitions neuves. Il ne copie aucun fichier de l'archive dans la plateforme, et il ne recopie
aucune exécution : `executions_connues` repart vide, parce que la v6 n'a pas d'histoire.

TROIS SUBSTITUTIONS, ET RIEN D'AUTRE :

    population   population_1000_AAMAS_v5      → population_1000_AAMAS_v6
    jeu          …_v5_20260316                 → population_1000_AAMAS_v6_20260316_EN
    variante     expert_gem_3.8_v2             → prompt_expert_04   (via `_ancien_nom`)

La variante n'est pas devinée : elle se lit dans `prompts.yaml`, où chaque entrée garde son
`_ancien_nom`. Une table écrite à la main ici aurait dérivé du fichier à la première retouche.

Le nom de chaque expérience est ensuite CALCULÉ (`experiences.nommage`), jamais recopié : c'est
la règle N13 du dépôt, et c'est elle qui garantit qu'un dossier dit ce qu'il contient.

CE QUI EST ÉCARTÉ. Les deux expériences de la sonde `escort66` : décision du 2026-09-14, la
sonde n'est pas un bras du protocole et son substrat dérivé n'a pas été refait en v6.

    services/llm-agents/.venv/bin/python scripts/migrations/definir_experiences_v6.py
    services/llm-agents/.venv/bin/python scripts/migrations/definir_experiences_v6.py --appliquer
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE / "services" / "llm-agents") not in sys.path:
    sys.path.insert(0, str(RACINE / "services" / "llm-agents"))

SPECS = (RACINE / "archive" / "2026-09-14_avant_bascule_anglaise"
         / "plateforme" / "experiences")
CIBLE = RACINE / "data" / "experiences"
PROMPTS = (RACINE / "packages" / "mobility_llm" / "src" / "mobility_llm"
           / "prompts" / "prompts.yaml")

POPULATION_V6 = "population_1000_AAMAS_v6"
JEU_V6 = "population_1000_AAMAS_v6_20260316_EN"

#: Chemin de population tel que le CONTENEUR le voit (`data/population` y est monté sur
#: `/data/eqasim-output`). Les définitions archivées le portaient déjà ainsi.
POPULATION_CHEMIN = f"/data/eqasim-output/{POPULATION_V6}"

#: Ce qu'on n'emporte pas en v6, et pourquoi.
ECARTEES = {
    "escort66": "sonde du ticket 027, hors protocole — substrat dérivé non refait en v6",
}

#: Décideurs qui consomment du quota. Sert au classement en phases, pas au contenu.
DECIDEURS_LLM = ("passerelle", "antigravity")


def variantes_par_ancien_nom() -> dict[str, str]:
    doc = yaml.safe_load(PROMPTS.read_text(encoding="utf-8")) or {}
    table = {}
    for nom, entree in (doc.get("prompts") or {}).items():
        ancien = (entree or {}).get("_ancien_nom")
        if ancien:
            table[str(ancien)] = nom
    return table


def _traduire(spec: dict, variantes: dict[str, str]) -> tuple[dict, list[str]]:
    """Rend la définition v6 et la liste de ce qui a été changé (pour le journal)."""
    neuf = {k: v for k, v in spec.items()
            if k not in ("nom", "executions_connues", "renomme_de")}
    changements: list[str] = []

    population = dict(neuf.get("population") or {})
    avant = str(population.get("chemin") or "")
    population["chemin"] = POPULATION_CHEMIN
    neuf["population"] = population
    changements.append(f"population : {avant} → {POPULATION_CHEMIN}")

    jeu = dict(neuf.get("jeu") or {})
    avant_jeu = str(jeu.get("nom") or "")
    jeu["nom"] = JEU_V6
    jeu["dossier"] = None
    neuf["jeu"] = jeu
    changements.append(f"jeu : {avant_jeu} → {JEU_V6}")

    gabarit = dict(neuf.get("gabarit") or {})
    ancienne = gabarit.get("variante")
    if ancienne:
        nouvelle = variantes.get(str(ancienne))
        if nouvelle is None:
            raise SystemExit(
                f"REFUSÉ — la variante {ancienne!r} n'a pas d'équivalent dans prompts.yaml "
                "(aucune entrée ne porte cet `_ancien_nom`). Une définition qui désigne une "
                "variante inconnue échouerait au lancement, après la phase des témoins.")
        gabarit["variante"] = nouvelle
        neuf["gabarit"] = gabarit
        changements.append(f"variante : {ancienne} → {nouvelle}")

    # La v6 n'a pas d'histoire : aucune exécution connue, et `derive_de` désigne un nom
    # d'expérience v5 qui n'existe plus. Le garder ferait pointer la généalogie dans l'archive.
    if neuf.get("derive_de"):
        changements.append(f"derive_de : {neuf['derive_de']} → (vidé, la v5 est archivée)")
        neuf["derive_de"] = None
    return neuf, changements


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--appliquer", action="store_true",
                   help="écrit réellement (par défaut : dit seulement ce qui serait fait)")
    p.add_argument("--modele", metavar="MODELE",
                   help="force TOUS les décideurs LLM sur ce modèle (ex. gemini-3.1-flash-lite). "
                        "Par défaut chaque expérience garde le sien : le plan compare des "
                        "modèles entre eux, et les uniformiser supprime cette comparaison.")
    a = p.parse_args(argv)

    from experiences import experience as E
    from experiences import nommage as NOM

    if not SPECS.is_dir():
        raise SystemExit(f"spécifications introuvables : {SPECS}")
    variantes = variantes_par_ancien_nom()

    print("=" * 100)
    print(f"Ticket 074 — définitions v6  ·  {'ÉCRITURE' if a.appliquer else 'VÉRIFICATION'}")
    print("=" * 100)
    print(f"population : {POPULATION_CHEMIN}\njeu        : {JEU_V6}\n")

    ecrites, ignorees = [], []
    for dossier in sorted(SPECS.iterdir()):
        fichier = dossier / "experience.yaml"
        if not fichier.is_file():
            continue
        spec = yaml.safe_load(fichier.read_text(encoding="utf-8")) or {}
        ancien_nom = str(spec.get("nom") or dossier.name)

        motif = next((m for marque, m in ECARTEES.items() if marque in ancien_nom), None)
        if motif:
            ignorees.append((ancien_nom, motif))
            continue

        neuf, changements = _traduire(spec, variantes)
        if a.modele and (neuf.get("decideur") or {}).get("type") in DECIDEURS_LLM:
            dec = dict(neuf["decideur"])
            if dec.get("modele") != a.modele:
                changements.append(f"modèle : {dec.get('modele')} → {a.modele} (forcé)")
                dec["modele"] = a.modele
                neuf["decideur"] = dec
        nom = NOM.nom_canonique(neuf)
        neuf["nom"] = nom
        famille = ("LLM" if (neuf.get("decideur") or {}).get("type") in DECIDEURS_LLM
                   else "témoin")
        print(f"  [{famille:6s}] {ancien_nom}\n           → {nom}")
        for c in changements:
            print(f"             · {c}")

        if a.appliquer:
            exp = E.charger_experience_depuis_dict(neuf) if hasattr(
                E, "charger_experience_depuis_dict") else None
            cible = CIBLE / nom
            cible.mkdir(parents=True, exist_ok=True)
            (cible / "experience.yaml").write_text(
                yaml.safe_dump(neuf, allow_unicode=True, sort_keys=False, width=10**9),
                encoding="utf-8")
            del exp  # la validation passe par `experiences definir`, appelé juste après
        ecrites.append((nom, famille))

    print(f"\n{len(ecrites)} définition(s) — "
          f"{sum(1 for _, f in ecrites if f == 'témoin')} témoins, "
          f"{sum(1 for _, f in ecrites if f == 'LLM')} LLM.")
    for nom, motif in ignorees:
        print(f"  écartée : {nom}\n            {motif}")

    if not a.appliquer:
        print("\nRien n'a été écrit. Pour exécuter :"
              "\n    services/llm-agents/.venv/bin/python "
              "scripts/migrations/definir_experiences_v6.py --appliquer")
        return 0

    print(f"\nÉcrites dans {CIBLE.relative_to(RACINE)}/")
    print("⚠ Valider chacune avec `make experience-definir FICHIER=…` : ce script écrit la "
          "définition, c'est la plateforme qui la VALIDE (schéma strict, nom calculé, jeu "
          "existant). Une définition non validée échouerait au lancement.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
