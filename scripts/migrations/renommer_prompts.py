#!/usr/bin/env python3
"""Ticket 074, C-4/C-5/C-6 — aligne les noms des variantes de prompt sur un schéma unique.

Les 22 noms actuels mélangent quatre conventions : `prompt_optimise_v5`, `expert_chaine_m7`,
`b_min`, `b0_pristine`, `persona_v3`, `expert`. Un lecteur extérieur ne peut en déduire ni la
famille, ni la place dans la série. Le schéma retenu est `prompt_<famille>_<nn>`.

**L'ordre est celui de la GÉNÉALOGIE**, pas l'alphabet ni la date. Chaque variante déclare son
parent (`_provenance.derive_de`) ; le parcours descend chaque lignée depuis sa racine, et les
racines sont prises par date de création. Un lecteur qui suit les numéros suit donc l'histoire
des mutations — `prompt_expert_04` dérive de `prompt_expert_03`. L'alphabet n'aurait rien dit,
et la date seule aurait dispersé les lignées (les cinq `persona_*` portent toutes la date de leur
archivage, pas de leur écriture).

**Rien n'est perdu.** Chaque entrée garde `_ancien_nom`, et `PromptManager` continue de résoudre
un ancien nom **en lecture** — avec un avertissement qui nomme le nom canonique. C'est ce qui rend
les traces archivées relisibles : les définitions d'expériences gelées portent `variante:
expert_gem_3.8_v2`, et elles ne seront jamais réécrites (l'archive est froide).

    services/llm-agents/.venv/bin/python scripts/migrations/renommer_prompts.py              # dit ce qu'il ferait
    services/llm-agents/.venv/bin/python scripts/migrations/renommer_prompts.py --appliquer  # écrit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

RACINE = Path(__file__).resolve().parents[2]
PROMPTS = (RACINE / "packages" / "mobility_llm" / "src" / "mobility_llm"
           / "prompts" / "prompts.yaml")
DOSSIER_EXPERIENCES = RACINE / "data" / "experiences"

# Familles → segment du nom. La famille se lit dans `familles:` et dans le champ `famille:` de
# l'entrée, jamais devinée du nom — c'est précisément le défaut que ce renommage corrige.
SEGMENT = {"minimale": "minimal", "experte": "expert"}


def _famille(nom: str, entree: dict, declarees: dict) -> str:
    """Famille d'une variante : l'entrée d'abord, la déclaration globale ensuite, le défaut enfin.

    L'ordre compte. `minimal_persona` n'est pas listée dans `familles.minimale` mais porte
    `famille: minimale` dans son entrée, avec un commentaire qui l'explique : c'est cette
    déclaration-là qui la rend jugeable par les règles M1-M4, et donc non conforme.
    """
    propre = entree.get("famille") or (entree.get("_neutralite") or {}).get("famille")
    if propre:
        return str(propre)
    if nom in (declarees.get("minimale") or []):
        return "minimale"
    return str(declarees.get("defaut") or "experte")


def _parent(entree: dict) -> str | None:
    prov = entree.get("_provenance") or {}
    for source in (prov.get("derive_de"), entree.get("derive_de"),
                   (entree.get("_calibration") or {}).get("seed")):
        if source:
            return str(source)
    return None


def _date(entree: dict) -> str:
    prov = entree.get("_provenance") or {}
    arch = entree.get("_archive") or {}
    return str(prov.get("date") or arch.get("le") or "9999-99-99")


def ordre_genealogique(prompts: dict, declarees: dict) -> list[str]:
    """Les variantes, lignée par lignée, chaque racine suivie de sa descendance.

    Parcours en profondeur. Les racines sont prises par date de création puis par nom ; les
    enfants d'un même parent, de même. Une lignée dont le parent n'existe pas (nom d'un autre
    dépôt, variante supprimée) est traitée comme une racine — mieux vaut une racine de plus
    qu'une variante qui disparaît du renommage sans bruit.
    """
    enfants: dict[str, list[str]] = {}
    racines: list[str] = []
    for nom, entree in prompts.items():
        parent = _parent(entree)
        if parent and parent in prompts and parent != nom:
            enfants.setdefault(parent, []).append(nom)
        else:
            racines.append(nom)

    def cle(n: str) -> tuple:
        return (_date(prompts[n]), n)

    ordonne: list[str] = []
    vus: set[str] = set()

    def descendre(n: str) -> None:
        if n in vus:
            return
        vus.add(n)
        ordonne.append(n)
        for enfant in sorted(enfants.get(n, []), key=cle):
            descendre(enfant)

    for racine in sorted(racines, key=cle):
        descendre(racine)
    # Filet : une lignée circulaire laisserait des variantes de côté, en silence.
    for nom in prompts:
        if nom not in vus:
            ordonne.append(nom)
    return ordonne


def correspondance(prompts: dict, declarees: dict) -> dict[str, str]:
    """ancien nom → nouveau nom, numéroté par famille dans l'ordre généalogique."""
    compteur: dict[str, int] = {}
    table: dict[str, str] = {}
    for nom in ordre_genealogique(prompts, declarees):
        fam = _famille(nom, prompts[nom], declarees)
        seg = SEGMENT.get(fam, SEGMENT["experte"])
        compteur[seg] = compteur.get(seg, 0) + 1
        table[nom] = f"prompt_{seg}_{compteur[seg]:02d}"
    return table


def _references_experiences() -> dict[str, list[Path]]:
    """Définitions d'expériences VIVANTES qui désignent une variante, par nom de variante.

    L'archive froide n'est pas parcourue, et c'est le principe même : ses définitions gardent
    les anciens noms, et c'est `_ancien_nom` qui les rend relisibles.
    """
    par_variante: dict[str, list[Path]] = {}
    if not DOSSIER_EXPERIENCES.is_dir():
        return par_variante
    import yaml as _yaml

    for definition in sorted(DOSSIER_EXPERIENCES.glob("*/experience.yaml")):
        try:
            doc = _yaml.safe_load(definition.read_text(encoding="utf-8")) or {}
        except _yaml.YAMLError:
            continue
        variante = ((doc.get("gabarit") or {}).get("variante"))
        if variante:
            par_variante.setdefault(str(variante), []).append(definition)
    return par_variante


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--appliquer", action="store_true",
                        help="écrit réellement (par défaut : dit seulement ce qui serait fait)")
    a = parser.parse_args(argv)

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 10**9
    yaml.indent(mapping=2, sequence=4, offset=2)
    doc = yaml.load(PROMPTS.read_text(encoding="utf-8"))
    prompts = doc["prompts"]
    declarees = doc.get("familles") or {}

    table = correspondance(prompts, declarees)
    refs = _references_experiences()

    deja = [n for n in prompts if n in table.values()]
    if deja and all(table[n] == n for n in deja):
        print("Déjà renommé : les noms sont conformes au schéma. Rien à faire.")
        return 0

    print("=" * 96)
    print(f"Ticket 074 C-4 — renommage des prompts  ·  "
          f"{'EXÉCUTION' if a.appliquer else 'VÉRIFICATION'}")
    print("=" * 96)
    print(f"\n{'ancien nom':34s} → {'nouveau nom':20s} {'famille':9s} {'parent':30s} usages")
    for ancien in ordre_genealogique(prompts, declarees):
        entree = prompts[ancien]
        parent = _parent(entree) or "—"
        usages = len(refs.get(ancien, []))
        fam = _famille(ancien, entree, declarees)
        marque = "  ← ACTIVE" if doc["active"].get("itinary_multi_agent") == ancien else ""
        print(f"{ancien:34s} → {table[ancien]:20s} {fam:9s} {parent:30s} "
              f"{usages if usages else '-':>6}{marque}")

    if refs:
        print(f"\n{sum(len(v) for v in refs.values())} définition(s) d'expérience VIVANTE(s) à "
              f"réécrire ({len(refs)} variante(s) désignée(s)).")
    else:
        print("\nAucune définition d'expérience vivante ne désigne de variante "
              "(data/experiences est vide — substrat en archive froide).")
    print("Les définitions ARCHIVÉES ne sont pas touchées : `_ancien_nom` les rend relisibles.")

    if not a.appliquer:
        print("\nRien n'a été écrit. Pour exécuter :"
              "\n    services/llm-agents/.venv/bin/python scripts/migrations/"
              "renommer_prompts.py --appliquer")
        return 0

    # ── Écriture ─────────────────────────────────────────────────────────────────────────
    neuf = CommentedMap()
    for ancien, entree in prompts.items():
        nouveau = table[ancien]
        entree["_ancien_nom"] = ancien
        prov = entree.get("_provenance")
        if isinstance(prov, dict) and prov.get("derive_de") in table:
            prov["derive_de"] = table[prov["derive_de"]]
        if entree.get("derive_de") in table:
            entree["derive_de"] = table[entree["derive_de"]]
        calib = entree.get("_calibration")
        if isinstance(calib, dict) and calib.get("seed") in table:
            calib["seed"] = table[calib["seed"]]
        inval = entree.get("_invalidation")
        if isinstance(inval, dict) and inval.get("remplace_par") in table:
            inval["remplace_par"] = table[inval["remplace_par"]]
        neuf[nouveau] = entree
    doc["prompts"] = neuf

    actif = doc["active"].get("itinary_multi_agent")
    if actif in table:
        doc["active"]["itinary_multi_agent"] = table[actif]
    if "minimale" in declarees:
        declarees["minimale"] = [table.get(n, n) for n in declarees["minimale"]]

    with PROMPTS.open("w", encoding="utf-8") as f:
        yaml.dump(doc, f)
    print(f"\n{len(table)} variantes renommées dans {PROMPTS.relative_to(RACINE)}")

    import yaml as _yaml
    reecrites = 0
    for ancien, chemins in refs.items():
        for chemin in chemins:
            texte = chemin.read_text(encoding="utf-8")
            doc_exp = _yaml.safe_load(texte) or {}
            doc_exp.setdefault("gabarit", {})["variante"] = table[ancien]
            chemin.write_text(
                _yaml.safe_dump(doc_exp, allow_unicode=True, sort_keys=False, width=10**9),
                encoding="utf-8",
            )
            reecrites += 1
    if reecrites:
        print(f"{reecrites} définition(s) d'expérience réécrite(s)")
    print("\n⚠ Le nom d'une expérience encode la variante (`promin`, `expgem38v2`) : relancer")
    print("   `make experiences-renommer` pour réaligner les noms sur les nouvelles abréviations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
