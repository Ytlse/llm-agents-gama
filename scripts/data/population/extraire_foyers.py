#!/usr/bin/env python3
"""Extrait des FOYERS entiers d'une population scellée — ticket 059, lot 6.

POURQUOI UN SCRIPT DE PLUS
--------------------------
`extraire_sous_population.py` prélève des INDIVIDUS par prédicat, et c'est ce qu'il fallait
pour lire cinq mémoires (ticket 075). Ici l'objet est le foyer : extraire un membre sans
l'autre supprime la grandeur mesurée. Les cinq agents du 075 appartiennent d'ailleurs à cinq
ménages distincts, et le mécanisme de diffusion y serait strictement inobservable.

CE QUE LA POPULATION PORTE
--------------------------
Des foyers de TAILLE 2 dont les deux membres sont mobiles, répartis en deux groupes :

- **exposés** — le foyer recevra l'article ; un seul de ses deux membres le lira, et le tirage
  du lecteur appartient au canal `information`, pas à ce script ;
- **témoins** — le foyer ne recevra rien, dans le MÊME run. Le plancher de bruit mesuré au
  ticket 095 n'est pas nul (1 écart de mode sur 31 décisions appariées) : comparer à un run
  témoin lancé séparément ferait entrer ce plancher dans l'effet mesuré.

Taille 2 par défaut, et c'est un choix de mise au point : un lecteur, un co-résident, rien
d'autre à démêler. Les foyers de quatre ou cinq disent si un énoncé atteint tout le monde ou
s'arrête au premier — question des paliers P2 et P3, pas de la plomberie. `--taille` et
`--adultes` ouvrent ces paliers (2026-09-24 : famille de quatre, deux adultes, deux enfants —
le lecteur se tire parmi les adultes, cf. `llm/evenements/exposition.py`). `--menage` désigne
un foyer par son identifiant plutôt que par tirage, quand le choix a été raisonné (profils de
mobilité adaptés à l'article joué) : il reste soumis aux mêmes critères d'éligibilité.
`--taille` se répète pour mêler des foyers de tailles différentes (2026-09-25 : un couple et une
famille de quatre). `--lecteur` désigne qui lit dans un foyer désigné, au lieu du tirage parmi
les adultes : un article sur le métro doit être lu par quelqu'un qui le prend. Il est écrit au
manifeste (`expose[].lecteurs`), d'où la cohorte le reporte dans l'événement joué.

DÉTERMINISME
------------
Le tri est celui des identifiants de ménage, en ordre numérique. L'affectation exposé/témoin
est un hachage stable de `graine:household_id` : deux extractions rendent les mêmes groupes, et
changer la graine se voit au manifeste.

USAGE
-----
    services/llm-agents/.venv/bin/python -m scripts.data.population.extraire_foyers \
        --source data/population/population_1000_AAMAS_v6/population.json \
        --sortie data/population/population_20_foyers_059 \
        --exposes 6 --temoins 4 --abonnement-tc

    # Un foyer désigné, famille de quatre dont deux adultes, sans foyer témoin :
    services/llm-agents/.venv/bin/python -m scripts.data.population.extraire_foyers \
        --source data/population/population_1000_AAMAS_v6/population.json \
        --sortie data/population/population_4_foyer_133048 \
        --taille 4 --adultes 2 --menage 133048 --temoins 0

    # Deux foyers désignés de tailles différentes, un lecteur désigné dans chacun :
    services/llm-agents/.venv/bin/python -m scripts.data.population.extraire_foyers \
        --source data/population/population_1000_AAMAS_v6/population.json \
        --sortie data/population/population_6_foyers_a13 \
        --taille 2 --taille 4 --adultes 2 --menage 643030 --menage 534995 \
        --lecteur 1320713 --lecteur 1127260 --temoins 0 --motif "…"
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

TAILLE_FOYER = 2
AGE_ADULTE = 18   # le même seuil que le tirage des lecteurs (llm/evenements/exposition.py)


def _traits(personne: dict) -> dict:
    return (personne.get("identity") or {}).get("traits_json") or {}


def _mobile(personne: dict) -> bool:
    return not personne.get("immobile", False)


def _sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def _cle_de_tri(identifiant: str) -> tuple[int, int, str]:
    """Tri numérique quand l'identifiant l'est, alphabétique sinon.

    La cohorte v6 n'a que des identifiants numériques, mais `int()` sur un identifiant
    alphanumérique ferait échouer l'extraction entière sur une population de forme différente —
    un refus incompréhensible là où un ordre stable suffit.
    """
    return (0, int(identifiant), "") if identifiant.isdigit() else (1, 0, identifiant)


def _rang(graine: int, household_id: str) -> float:
    """Rang stable dans [0, 1[ — l'affectation exposé/témoin ne dépend d'aucun ordre d'exécution."""
    brut = hashlib.sha256(f"{graine}:{household_id}".encode("utf-8")).hexdigest()[:8]
    return int(brut, 16) / 0xFFFFFFFF


def _adulte(personne: dict) -> bool:
    try:
        return int(_traits(personne).get("age")) >= AGE_ADULTE
    except (TypeError, ValueError):
        return False


def foyers_eligibles(
    population: list[dict],
    *,
    abonnement_tc: bool,
    taille: int | Iterable[int] = TAILLE_FOYER,
    adultes: int | None = None,
) -> dict[str, list[dict]]:
    """Les foyers de `taille` membres (une taille ou plusieurs), tous mobiles (et `adultes`
    adultes exactement si demandé), triés par identifiant."""
    tailles = {taille} if isinstance(taille, int) else set(taille)
    par_menage: dict[str, list[dict]] = defaultdict(list)
    for personne in population:
        menage = (personne.get("household") or {}).get("id")
        if menage:
            par_menage[str(menage)].append(personne)

    retenus: dict[str, list[dict]] = {}
    for menage, membres in par_menage.items():
        if len(membres) not in tailles:
            continue
        if not all(_mobile(m) for m in membres):
            continue
        if adultes is not None and sum(_adulte(m) for m in membres) != adultes:
            continue
        if abonnement_tc and not any(_traits(m).get("has_pt_subscription") for m in membres):
            # L'article joué en premier vise les transports collectifs : un foyer où personne
            # n'en est usager n'a rien à reporter, et sa présence diluerait la mesure.
            continue
        retenus[menage] = sorted(membres, key=lambda p: _cle_de_tri(str(p["person_id"])))
    return {m: retenus[m] for m in sorted(retenus, key=_cle_de_tri)}


def choisir(
    population: list[dict],
    *,
    exposes: int,
    temoins: int,
    graine: int,
    abonnement_tc: bool,
    taille: int | Iterable[int] = TAILLE_FOYER,
    adultes: int | None = None,
    menages: list[str] | None = None,
) -> tuple[list[str], list[str], dict[str, list[dict]]]:
    eligibles = foyers_eligibles(
        population, abonnement_tc=abonnement_tc, taille=taille, adultes=adultes
    )
    if menages:
        # Foyers DÉSIGNÉS : ils sont les exposés ; les témoins se tirent parmi le reste.
        refuses = [m for m in menages if m not in eligibles]
        if refuses:
            raise SystemExit(
                f"REFUS : foyer(s) {refuses} non éligible(s) (taille {taille}, "
                f"{'adultes ' + str(adultes) + ', ' if adultes is not None else ''}tous mobiles"
                f"{', abonné TC' if abonnement_tc else ''}). Désigner un foyer ne dispense pas "
                f"des critères : la population dirait autre chose que son manifeste."
            )
        reste = sorted(
            (m for m in eligibles if m not in menages), key=lambda m: (_rang(graine, m), _cle_de_tri(m))
        )
        if len(reste) < temoins:
            raise SystemExit(f"REFUS : {len(reste)} foyers témoins possibles pour {temoins} demandés.")
        return list(menages), reste[:temoins], eligibles
    besoin = exposes + temoins
    if len(eligibles) < besoin:
        raise SystemExit(
            f"REFUS : {len(eligibles)} foyers éligibles pour {besoin} demandés → assouplissez le "
            f"critère (--abonnement-tc), ou réduisez --exposes / --temoins. Un groupe incomplet "
            f"rendrait l'un des deux bras plus petit que l'autre sans que rien ne le dise."
        )
    ordonnes = sorted(eligibles, key=lambda m: (_rang(graine, m), _cle_de_tri(m)))
    return ordonnes[:exposes], ordonnes[exposes:besoin], eligibles


def lecteurs_par_menage(
    lecteurs: list[str], exposes: list[str], eligibles: dict[str, list[dict]]
) -> dict[str, list[str]]:
    """Range les lecteurs désignés par foyer exposé ; refuse un lecteur qui ne peut pas lire.

    Un lecteur doit être un ADULTE d'un foyer exposé : c'est la règle du tirage
    (`llm/evenements/exposition.py`), et le simulateur l'écarterait sinon — au prix d'un foyer
    sans lecteur, découvert au milieu du run.
    """
    ranges: dict[str, list[str]] = {}
    refus: list[str] = []
    for pid in lecteurs:
        foyer = next(
            (m for m in exposes for p in eligibles[m] if str(p["person_id"]) == str(pid)), None
        )
        membre = next((p for p in eligibles.get(foyer, []) if str(p["person_id"]) == str(pid)), None)
        if membre is None:
            refus.append(f"{pid} (hors des foyers exposés {exposes})")
        elif not _adulte(membre):
            refus.append(f"{pid} (mineur : {_traits(membre).get('age')} ans)")
        else:
            ranges.setdefault(foyer, []).append(str(pid))
    if refus:
        raise SystemExit(f"REFUS : lecteur(s) {refus}. Un lecteur est un adulte d'un foyer exposé.")
    return ranges


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", required=True, type=Path, help="population.json scellée")
    p.add_argument("--sortie", required=True, type=Path, help="répertoire à créer")
    p.add_argument("--exposes", type=int, default=6, help="foyers qui recevront l'article")
    p.add_argument("--temoins", type=int, default=4, help="foyers qui ne recevront rien")
    p.add_argument("--graine", type=int, default=59)
    p.add_argument(
        "--taille", type=int, action="append", default=None,
        help=f"membres par foyer (répétable pour mêler des tailles ; {TAILLE_FOYER} si absent)",
    )
    p.add_argument(
        "--adultes", type=int, default=None,
        help=f"nombre EXACT d'adultes (≥ {AGE_ADULTE} ans) par foyer ; libre si absent",
    )
    p.add_argument(
        "--menage", action="append", default=None,
        help="foyer désigné (répétable) : devient exposé à la place du tirage",
    )
    p.add_argument(
        "--lecteur", action="append", default=None,
        help="lecteur désigné (répétable) : un adulte d'un foyer --menage, au lieu du tirage",
    )
    p.add_argument(
        "--motif", default=None,
        help="pourquoi ces foyers ont été désignés (écrit au manifeste) ; exigé avec --menage",
    )
    p.add_argument(
        "--abonnement-tc",
        action="store_true",
        help="n'accepter que les foyers comptant au moins un abonné aux transports collectifs",
    )
    args = p.parse_args(argv)

    if args.menage and not args.motif:
        p.error("--menage exige --motif : un choix raisonné qui ne dit pas sa raison est un tirage caché")
    if args.lecteur and not args.menage:
        p.error("--lecteur exige --menage : on ne désigne pas qui lit dans un foyer tiré")
    tailles = sorted(set(args.taille or [TAILLE_FOYER]))
    population = json.loads(args.source.read_text(encoding="utf-8"))
    exposes, temoins, eligibles = choisir(
        population,
        exposes=args.exposes,
        temoins=args.temoins,
        graine=args.graine,
        abonnement_tc=args.abonnement_tc,
        taille=tailles,
        adultes=args.adultes,
        menages=args.menage,
    )
    lecteurs = lecteurs_par_menage(args.lecteur or [], exposes, eligibles)

    agents: list[dict] = []
    for menage in exposes + temoins:
        # Les agents sont recopiés TELS QUELS : aucune normalisation, aucun champ ajouté. Une
        # population de test qui diverge du sceau dont elle sort ne prouve plus rien — et le
        # rôle (exposé, témoin) vit au manifeste, pas dans les données de l'agent.
        agents.extend(eligibles[menage])

    args.sortie.mkdir(parents=True, exist_ok=True)
    fichier = args.sortie / "population.json"
    fichier.write_text(json.dumps(agents, ensure_ascii=False, indent=2), encoding="utf-8")

    lignes: list[str] = [
        "# Population de TEST — ticket 059, lot 6. Ce n'est PAS un sceau AAMAS.",
        "#",
        f"# {len(agents)} agents ne représentent rien : ils servent à observer si une information",
        "# lue par un seul membre d'un foyer atteint l'autre, et à quelle date. Ils ne mesurent",
        "# aucune part modale. La référence de l'article reste",
        "# data/population/population_1000_AAMAS_v6.",
        "#",
        "# Les foyers témoins sont dans le MÊME fichier, donc dans le même run : le plancher de",
        "# bruit mesuré au ticket 095 n'est pas nul, et un témoin lancé séparément le ferait",
        "# entrer dans l'effet mesuré.",
        f"nom: {args.sortie.name}",
        f"extrait_le: '{datetime.now(timezone.utc).isoformat()}'",
        "source:",
        f"  fichier: {args.source.as_posix()}",
        f"  sha256: {_sha256(args.source)}",
        f"  n: {len(population)}",
        "population:",
        "  fichier: population.json",
        f"  sha256: {_sha256(fichier)}",
        f"  n: {len(agents)}",
        "selection:",
        "  methode: >-",
        f"    Foyers de taille {' ou '.join(map(str, tailles))} dont tous les membres sont mobiles"
        + (f", dont {args.adultes} adultes (≥ {AGE_ADULTE} ans)" if args.adultes is not None else "")
        + ("; exposés DÉSIGNÉS par --menage, témoins" if args.menage else ";")
        + " triés par rang stable",
        "    sha256(graine:household_id). Aucun tirage dépendant de l'ordre d'exécution.",
        "    Reproductible par scripts/data/population/extraire_foyers.py.",
        f"  graine: {args.graine}",
        f"  taille: {tailles[0] if len(tailles) == 1 else json.dumps(tailles)}",
        f"  adultes_exiges: {args.adultes if args.adultes is not None else 'null'}",
        f"  menages_designes: {json.dumps(args.menage or [])}",
        f"  lecteurs_designes: {json.dumps(args.lecteur or [])}",
        f"  motif: {json.dumps(args.motif or '', ensure_ascii=False)}",
        f"  abonnement_tc_exige: {bool(args.abonnement_tc)}",
        f"  foyers_eligibles: {len(eligibles)}",
        "groupes:",
    ]
    for role, menages in (("expose", exposes), ("temoin", temoins)):
        lignes.append(f"  {role}:")
        for menage in menages:
            membres = eligibles[menage]
            lignes.append(f"    - household_id: '{menage}'")
            if lecteurs.get(menage):
                lignes.append(f"      lecteurs: {json.dumps(lecteurs[menage])}")
            lignes.append("      membres:")
            for m in membres:
                t = _traits(m)
                lignes += [
                    f"        - person_id: '{m['person_id']}'",
                    f"          nom: {json.dumps(t.get('name', ''), ensure_ascii=False)}",
                    f"          age: {t.get('age')}",
                    f"          occupation: {json.dumps(t.get('main_occupation', ''), ensure_ascii=False)}",
                    f"          zone: {json.dumps(t.get('residence_zone', ''), ensure_ascii=False)}",
                    f"          abonnement_tc: {bool(t.get('has_pt_subscription'))}",
                    f"          voiture: {json.dumps(t.get('car_availability', ''), ensure_ascii=False)}",
                    f"          velo: {json.dumps(t.get('personal_bike', ''), ensure_ascii=False)}",
                ]
    (args.sortie / "MANIFEST.yaml").write_text("\n".join(lignes) + "\n", encoding="utf-8")

    print(
        f"{len(agents)} agents, {len(exposes)} foyers exposés et {len(temoins)} témoins, "
        f"sur {len(eligibles)} éligibles → {args.sortie}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
