"""measure_couronne_v7.py — Ce que la correction des couronnes change (ticket 021, lot 4).

Chiffre l'effet du reclassement des couronnes de résidence **à décisions constantes**, sur
le jeu gelé `v7` — dernière base de référence du registre `avancement.yaml`.

**Aucun appel LLM.** Les décisions de `v7` sont déjà dans le store de calibration
(`evals.decisions` = `[[agent_id, mode, poids], …]`, prompt de production, T=0,0, modèle
épinglé). La couronne n'entrant ni dans le prompt du persona (liste blanche de
`_build_profile_narrative`) ni dans la clé du cache de décisions (options + météo +
agent/activité/créneau), le reclassement ne peut déplacer aucune décision : « à décisions
constantes » est ici **structurel**, pas une précaution. Seule l'AGRÉGATION change.

**Ce qui est comparé.** Les mêmes records, deux classements du même domicile :

- `metrique` — distance à l'hypercentre (8 / 20 / 40 km), ce que le journal écrivait
  jusqu'au ticket 021 ;
- `communal` — la couronne de la **commune** du domicile, définition de l'enquête, plus
  `hors périmètre` pour un domicile hors des 453 communes.

**Le score n'est PAS un composite.** `lieu_residence` n'est ni une dimension de
l'évaluateur des jeux gelés ni une dimension notée de `frames` : le composite comparable ne
bouge pas d'un millième, et publier ce zéro serait prendre l'absence de mesure pour une
mesure. La grandeur portée au registre est le **L1 moyen pondéré par zone**.

**Ce que `v7` ne peut pas mesurer.** Ses 930 personas sont filtrés par bbox : aucun domicile
hors périmètre. `v7` chiffre donc l'axe **A2 seul**. L'axe **A4** est chiffré à part, sur la
population de référence (1 021 personas, dont 45 dehors), et le rapport le dit au lieu de
laisser croire à une mesure complète.

⚠ La population de `v7` est épinglée par le sha256 des manifestes de `v5` à `v8` : ce script
la lit et **ne l'écrit jamais**. Il republie son empreinte dans le rapport, pour que la
non-modification soit vérifiée et pas seulement promise.

Usage :
    make couronne-v7
    llm-agents/.venv/bin/python -m scripts.synthesis.measure_couronne_v7 \\
      --trace docs/traces/2026-08-24_couronne_v7
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "prompt_calibration"))

from llm_module.core.geo_reference import residence_zone as metric_zone  # noqa: E402
from llm_module.core.population_reference import (  # noqa: E402
    COURONNES, OUT_OF_PERIMETER, couronne_population_shares)
from llm_module.core.residence_zone import CouronneTable  # noqa: E402
from scripts.synthesis.frames import (  # noqa: E402
    MODES, load_cerema, reference_shares)

STORE = REPO_ROOT / "prompt_calibration" / "calibration_results" / "ab_chaine.db"
POPULATION = (REPO_ROOT / "experiments" / "archive" / "2026-08-19_14_36"
              / "population_1000.json")
REFERENCE_POPULATION = (REPO_ROOT / "data" / "population"
                        / "toulouse_population_1000.json")
CEREMA = REPO_ROOT / "scripts" / "data" / "population" / "cerema_values.yaml"
MANIFESTS = REPO_ROOT / "prompt_calibration" / "calibration_datasets"

# Splits retenus pour le chiffrage par zone. `rank` ne porte que 75 agents : découpé en
# quatre couronnes, ses strates tomberaient sous l'effectif où `frames` accepte de
# publier une cellule (n ≥ 5). Le chiffre par zone se lit donc sur `train` + `val`, et
# `rank` est rapporté à part pour mémoire — jamais mélangé au composite du registre.
SCORING_SPLITS = ("train", "val")
MIN_CELL = 5

# Libellés des lignes de synthèse des CSV. Le second est recopié à l'identique de
# `docs/traces/2026-08-24_perimetre_population/parts_modales_par_zone.csv` : même
# grandeur, même nom.
L1_CADRAGE_ROW = "— L1 pondéré par le cadrage —"
L1_MASSE_ROW = "— L1 moyen pondéré —"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mode_group(label: str) -> str:
    """Chaîne d'options du jeu gelé → mode scoré.

    Importée de `calibration.metrics`, jamais réimplémentée : une seconde table de
    correspondance finirait par classer « foot,bus,foot » autrement que le moteur de
    calibration, et le chiffre publié ne serait plus celui qu'il optimise.
    """
    from calibration.metrics import categorize_mode
    return categorize_mode(label)


def load_decisions(store: Path, dataset_filter: str = "ds=v7") -> dict:
    """`{split: [[agent_id, mode, poids], …]}` depuis le store de calibration."""
    if not store.exists():
        raise SystemExit(f"store absent : {store}")
    con = sqlite3.connect(store)
    rows = con.execute(
        "select dataset, decisions, params_key, node_hash, eval_model, eval_temp, "
        "created_at from evals where params_key like ?", (f"%{dataset_filter}%",)
    ).fetchall()
    if not rows:
        raise SystemExit(
            f"aucune évaluation `{dataset_filter}` dans {store.name}. Le chiffrage par "
            f"zone exige des décisions DÉJÀ stockées : ce script n'appelle aucun LLM.")
    out, meta = {}, {}
    for dataset, decisions, params_key, node_hash, model, temp, created in rows:
        out[dataset] = json.loads(decisions)
        meta[dataset] = {"params_key": params_key, "node": node_hash,
                         "model": model, "temp": temp, "created_at": created}
    return {"decisions": out, "meta": meta}


def classify_population(path: Path, table: CouronneTable, resolver) -> dict:
    """`{agent_id: {…}}` — les deux classements du même domicile, côte à côte."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    people = raw if isinstance(raw, list) else (raw.get("people") or raw.get("personas"))
    out = {}
    for person in people:
        identity = person.get("identity") or {}
        home = identity.get("home") or {}
        lat, lon = home.get("lat"), home.get("lon")
        agent_id = str(person.get("person_id") or identity.get("person_id")
                       or person.get("id") or identity.get("id") or "")
        zone = resolver.resolve(lat, lon) if lat is not None and lon is not None else None
        communal = (table.couronne_of_zf(zone.zf) if zone is not None
                    else OUT_OF_PERIMETER)
        commune = table.commune_of_zf(zone.zf) if zone is not None else None
        out[agent_id] = {
            "agent_id": agent_id, "lat": lat, "lon": lon,
            "zf": zone.zf if zone else "",
            "secteur": zone.zf[:3] if zone else "",
            "couronne": communal or "",
            "insee": commune[0] if commune else "",
            "commune": commune[1] if commune else "",
            "couronne_metrique": metric_zone(lat, lon),
        }
    return out


def shares_by_zone(decisions: list, personas: dict, key: str, cerema: dict) -> dict:
    """Parts modales par zone et L1 aux cibles, sous le classement `key`.

    Les zones sans cible EMC² — `hors périmètre` — sont **exclues** du L1 et leur masse
    est comptée à part : les garder comparerait une part à une grandeur qui n'existe pas.
    """
    mass: dict[str, Counter] = defaultdict(Counter)
    agents: dict[str, set] = defaultdict(set)
    inconnus = Counter()
    for agent_id, label, weight in decisions:
        persona = personas.get(str(agent_id))
        if persona is None:
            inconnus["persona absent"] += 1
            continue
        zone = persona[key] or "zone inconnue"
        mode = mode_group(label)
        if mode not in MODES:
            inconnus["mode hors des quatre"] += 1
            continue
        mass[zone][mode] += float(weight)
        agents[zone].add(str(agent_id))

    rows, l1_weighted, weight_total = [], 0.0, 0.0
    excluded_mass = 0.0
    # Second jeu de poids, et c'est celui qui décide. Pondérer par la MASSE observée
    # compare deux classements dont les poids bougent en même temps que les strates :
    # sur `v7`, la masse quitte Toulouse (L1 ≈ 59) pour la 1ʳᵉ couronne (L1 ≈ 32), et la
    # moyenne s'améliore de 0,26 pt alors que CHAQUE strate se dégrade. Ce n'est pas un
    # gain, c'est un déplacement de poids. Les parts de population du CADRAGE sont, elles,
    # identiques des deux côtés : elles rendent la comparaison stable.
    cadrage = couronne_population_shares()
    l1_cadrage, cadrage_total = 0.0, 0.0
    for zone in (*COURONNES, OUT_OF_PERIMETER, "zone inconnue"):
        if zone not in mass:
            continue
        total = sum(mass[zone].values())
        actual = {m: 100.0 * mass[zone].get(m, 0.0) / total for m in MODES}
        cat = zone.replace(" ", "_")
        target = (reference_shares(cerema, "lieu_residence", cat)
                  if zone in COURONNES else {})
        if not target:
            # Aucune cible : la masse sort du L1 et se compte. C'est l'axe A4.
            excluded_mass += total
            rows.append({"zone": zone, "n": len(agents[zone]), "masse": total,
                         "parts": actual, "cible": None, "l1": None,
                         "couverte": False})
            continue
        l1 = sum(abs(actual[m] - target.get(m, 0.0)) for m in MODES)
        covered = len(agents[zone]) >= MIN_CELL
        rows.append({"zone": zone, "n": len(agents[zone]), "masse": total,
                     "parts": actual, "cible": target, "l1": l1, "couverte": covered})
        if covered:
            l1_weighted += l1 * total
            weight_total += total
            l1_cadrage += l1 * cadrage[zone]
            cadrage_total += cadrage[zone]
    manquantes = [z for z in COURONNES if z not in mass]
    return {"classement": key, "zones": rows,
            "l1_pondere_masse": (l1_weighted / weight_total) if weight_total else None,
            "l1_pondere_cadrage": (l1_cadrage / cadrage_total) if cadrage_total else None,
            "poids_cadrage_couvert": cadrage_total,
            "couronnes_absentes": manquantes,
            "masse_scoree": weight_total, "masse_exclue": excluded_mass,
            "ecartes": dict(inconnus)}


def write_join_table(path: Path, personas: dict) -> None:
    fields = ["agent_id", "lat", "lon", "zf", "secteur", "couronne", "insee",
              "commune", "couronne_metrique"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in sorted(personas.values(), key=lambda r: r["agent_id"]):
            writer.writerow({k: row[k] for k in fields})


def write_zone_table(path: Path, results: dict) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["classement", "zone", "n_agents", "masse",
                         *MODES, "l1_vs_cible"])
        for key, block in results.items():
            for row in block["zones"]:
                writer.writerow([key, row["zone"], row["n"], f"{row['masse']:.2f}",
                                 *[f"{row['parts'][m]:.2f}" for m in MODES],
                                 "" if row["l1"] is None else f"{row['l1']:.2f}"])
            # « — L1 moyen pondéré — » est le libellé DÉJÀ archivé par la trace du
            # ticket 020 pour la pondération par la masse : on le recopie tel quel plutôt
            # que d'en écrire une variante, sinon deux traces du même dépôt nommeraient
            # différemment la même grandeur. Le second libellé est nouveau parce que la
            # grandeur est nouvelle.
            for etiquette, valeur in ((L1_CADRAGE_ROW, block["l1_pondere_cadrage"]),
                                      (L1_MASSE_ROW, block["l1_pondere_masse"])):
                writer.writerow([key, etiquette, "", "", "", "", "", "",
                                 "" if valeur is None else f"{valeur:.2f}"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, default=None,
                        help="Répertoire d'archivage (CSV + JSON)")
    parser.add_argument("--store", type=Path, default=STORE)
    parser.add_argument("--population", type=Path, default=POPULATION)
    args = parser.parse_args()

    from llm_module.core.zone_resolver import ZoneResolver

    sha_avant = sha256_of(args.population)
    table = CouronneTable.load()
    resolver = ZoneResolver.load()
    cerema = load_cerema(CEREMA)

    store = load_decisions(args.store)
    personas = classify_population(args.population, table, resolver)

    print(f"Population `v7` : {len(personas)} personas, sha256 {sha_avant[:16]}…")
    for split, meta in sorted(store["meta"].items()):
        print(f"  décisions {split:6s} : {len(store['decisions'][split]):5d} lignes "
              f"— {meta['model']} T={meta['temp']} node={meta['node'][:10]}")

    retenues = [d for split in SCORING_SPLITS
                for d in store["decisions"].get(split, [])]
    if not retenues:
        raise SystemExit(f"aucune décision sur les splits {SCORING_SPLITS}.")

    results = {key: shares_by_zone(retenues, personas, key, cerema)
               for key in ("couronne_metrique", "couronne")}

    print(f"\nSplits retenus : {', '.join(SCORING_SPLITS)} — "
          f"{len(retenues)} lignes de décision, "
          f"{len({d[0] for d in retenues})} agents")
    for key, block in results.items():
        etiquette = "métrique (publié)" if key == "couronne_metrique" else "communal (correct)"
        print(f"\n── classement {etiquette}")
        for row in block["zones"]:
            l1 = "—" if row["l1"] is None else f"{row['l1']:6.2f}"
            flag = "" if row["couverte"] or row["l1"] is None else "  (sous-effectif)"
            print(f"   {row['zone']:16s} n={row['n']:4d} masse={row['masse']:7.1f} "
                  f"L1={l1}{flag}")
        print(f"   L1 pondéré par le CADRAGE : {block['l1_pondere_cadrage']:.2f} pt"
              f"   (poids couvert {block['poids_cadrage_couvert']:.1f} %"
              f"{', couronnes absentes : ' + ', '.join(block['couronnes_absentes'])
                 if block['couronnes_absentes'] else ''})")
        print(f"   L1 pondéré par la masse   : {block['l1_pondere_masse']:.2f} pt"
              f"   (masse exclue : {block['masse_exclue']:.1f})")

    par_zone = {row["zone"]: row["l1"] for row in results["couronne"]["zones"]}
    par_zone_m = {row["zone"]: row["l1"] for row in
                  results["couronne_metrique"]["zones"]}
    print("\n── par strate, ce que le reclassement fait vraiment")
    for zone in COURONNES:
        avant, apres = par_zone_m.get(zone), par_zone.get(zone)
        if avant is None and apres is None:
            continue
        if avant is None:
            print(f"   {zone:16s}    —    → {apres:6.2f}   (strate qui APPARAÎT)")
        elif apres is None:
            print(f"   {zone:16s} {avant:6.2f} →    —")
        else:
            print(f"   {zone:16s} {avant:6.2f} → {apres:6.2f}   ({apres - avant:+.2f})")

    delta = (results["couronne"]["l1_pondere_cadrage"]
             - results["couronne_metrique"]["l1_pondere_cadrage"])
    delta_masse = (results["couronne"]["l1_pondere_masse"]
                   - results["couronne_metrique"]["l1_pondere_masse"])
    print(f"\nEffet du reclassement, pondéré par le CADRAGE : {delta:+.2f} pt "
          f"({results['couronne_metrique']['l1_pondere_cadrage']:.2f} → "
          f"{results['couronne']['l1_pondere_cadrage']:.2f})")
    print(f"Pondéré par la masse observée : {delta_masse:+.2f} pt — À NE PAS PUBLIER "
          f"comme un gain : les poids bougent avec les strates (la masse quitte la pire "
          f"strate), si bien que la moyenne s'améliore alors que chaque strate se dégrade.")
    reclasses = sum(1 for p in personas.values()
                    if p["couronne"] != p["couronne_metrique"])
    print(f"Personas reclassés : {reclasses}/{len(personas)} "
          f"({100.0 * reclasses / len(personas):.1f} %)")

    # A4 n'est pas mesurable ici : la population de `v7` est filtrée par bbox.
    a4 = {"mesurable_sur_v7": False, "hors_perimetre_v7": sum(
        1 for p in personas.values() if p["couronne"] == OUT_OF_PERIMETER)}
    if REFERENCE_POPULATION.exists():
        ref = classify_population(REFERENCE_POPULATION, table, resolver)
        a4.update({
            "population_reference": str(REFERENCE_POPULATION.relative_to(REPO_ROOT)),
            "n_personas": len(ref),
            "hors_perimetre": sum(1 for p in ref.values()
                                  if p["couronne"] == OUT_OF_PERIMETER),
            "en_3eme_couronne_metrique": sum(
                1 for p in ref.values()
                if p["couronne"] == OUT_OF_PERIMETER
                and p["couronne_metrique"] == "3eme couronne"),
        })
        print(f"\nA4, sur la population de référence ({a4['n_personas']} personas) : "
              f"{a4['hors_perimetre']} domiciles hors périmètre, dont "
              f"{a4['en_3eme_couronne_metrique']} que le classement métrique rangeait en "
              f"3ᵉ couronne. Non mesurable sur `v7` (bbox).")

    sha_apres = sha256_of(args.population)
    if sha_apres != sha_avant:
        raise SystemExit("la population épinglée a changé pendant la mesure — arrêt.")

    report = {
        "generated_at": date.today().isoformat(), "ticket": "021", "lot": 4,
        "jeu": "v7", "splits": list(SCORING_SPLITS),
        "n_decisions": len(retenues),
        "n_agents_decides": len({d[0] for d in retenues}),
        "store": {"path": str(args.store.relative_to(REPO_ROOT)),
                  "meta": store["meta"]},
        "population": {"path": str(args.population.relative_to(REPO_ROOT)),
                       "sha256": sha_apres, "inchangee": True,
                       "n_personas": len(personas), "reclasses": reclasses},
        "resultats": results,
        "delta_l1_pondere_cadrage": delta,
        "delta_l1_pondere_masse": delta_masse,
        "avertissement_ponderation": (
            "La moyenne pondérée par la MASSE observée n'est pas une comparaison "
            "valide entre deux classements : les poids se déplacent avec les strates. "
            "Sur `v7` elle rend −0,26 pt alors que les quatre strates se dégradent. La "
            "grandeur publiée est pondérée par les parts de population du CADRAGE, "
            "identiques des deux côtés."),
        "composite": "inchangé par construction — `lieu_residence` n'est ni une "
                     "dimension de l'évaluateur des jeux gelés ni une dimension notée "
                     "de `frames`",
        "a4": a4,
        "rank_pour_memoire": {
            "n_decisions": len(store["decisions"].get("rank", [])),
            "n_agents": len({d[0] for d in store["decisions"].get("rank", [])}),
            "raison_exclusion": "75 agents : les strates par couronne tombent sous "
                                "l'effectif minimal de publication (n ≥ 5)",
        },
    }

    if args.trace:
        args.trace.mkdir(parents=True, exist_ok=True)
        write_join_table(args.trace / "agent_couronne.csv", personas)
        write_zone_table(args.trace / "parts_modales_par_zone.csv", results)
        (args.trace / "resultats.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\ntrace → {args.trace}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
