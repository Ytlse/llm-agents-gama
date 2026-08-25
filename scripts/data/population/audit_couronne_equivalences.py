"""audit_couronne_equivalences.py — Ticket 021, lot 0 : les deux équivalences, mesurées.

Le ticket 021 pose la couronne de résidence sur le persona en résolvant son domicile en
zone fine, puis en lisant la couronne du **secteur de tirage** que portent les trois
premiers chiffres du code `ZF`. Toute la suite du ticket repose sur deux équivalences que
la première rédaction affirmait sans les avoir mesurées :

1. classer un point par **préfixe de code de zone fine** rend la même couronne que le
   classer par **appartenance géométrique** aux polygones de couronnes ;
2. « hors de la **couche de zones fines** » (`zone_resolver.resolve()` rend `None`) désigne
   exactement le même ensemble que « hors des **quatre couronnes** » (`hors périmètre`).

Ce ne sont pas les mêmes objets : la première oppose un rattachement par code à une
jointure spatiale, la seconde oppose deux emprises construites séparément (l'union des 785
zones fines contre la dissolution des 88 secteurs). Rien n'oblige a priori les deux à
coïncider — d'où cette mesure, dont le résultat décide de la forme des lots 1 et 2.

Le script NE MODIFIE RIEN. Il mesure, écrit un rapport, et rend un code de sortie.

**Le recoupement est indépendant** (porte E) : le classement recalculé ici est opposé à la
colonne `zone_communale` de `agents_reclassement.csv`, produite le 2026-08-24 par l'autre
chemin lors du ticket 020. Un accord entre deux mesures du même chemin ne vaudrait rien.

Codes de sortie :
  0  les sept portes passent — les lots 1 à 5 peuvent être écrits tels quels
  1  ressource versionnée absente
  2  au moins une porte ÉCHOUE — le ticket doit être reconçu avant d'écrire du code
  3  au moins une porte est NON MESURABLE (données d'accès restreint absentes), et une
     porte non mesurée est une porte qui passe : le script refuse de le taire

Usage :
    make audit-couronnes
    llm-agents/.venv/bin/python -m scripts.data.population.audit_couronne_equivalences \
      --population data/population/toulouse_population_1000.json \
      --trace docs/traces/2026-08-24_couronne_equivalences
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from llm_module.core.population_reference import COURONNES, OUT_OF_PERIMETER  # noqa: E402

EXIT_OK, EXIT_RESOURCE_MISSING, EXIT_GATE_FAILED, EXIT_NOT_MEASURABLE = 0, 1, 2, 3

SIG = REPO_ROOT / "data" / "PROGEDO 2023" / "lil-1750-Documentation" / "SIG"
SIG_DTIR = SIG / "EMC2_Toulouse_2023_DTIR_17072023.shp"
SIG_ZF = SIG / "EMC2_Toulouse_2023_ZF_26052023.shp"
ZF_GPKG = REPO_ROOT / "llm_module" / "data" / "zf_zones.gpkg"
COURONNE_GEOJSON = REPO_ROOT / "llm_module" / "data" / "couronne_perimetre.geojson"
ZF_TABLE = REPO_ROOT / "llm_module" / "data" / "zf_couronne.json"
DEFAULT_POPULATION = (REPO_ROOT / "data" / "population"
                      / "toulouse_population_1000.json")
DEFAULT_ARCHIVE = (REPO_ROOT / "docs" / "traces" / "2026-08-24_perimetre_population"
                   / "agents_reclassement.csv")

NOT_MEASURABLE = "NON MESURABLE"


def title(text: str) -> None:
    print(f"\n{'─' * 78}\n{text}\n{'─' * 78}")


def person_id(person: dict) -> str:
    identity = person.get("identity") or {}
    for key in ("id", "person_id", "agent_id"):
        if person.get(key) is not None:
            return str(person[key])
        if identity.get(key) is not None:
            return str(identity[key])
    return ""


def secteur_couronne_map() -> tuple[Optional[dict], str]:
    """`secteur → couronne`, depuis la table publiée si elle existe, sinon la couche SIG.

    L'ordre compte : après le lot 1 la table `zf_couronne.json` est versionnée et cet
    audit tourne SANS les données d'accès restreint. Avant le lot 1, il n'y a que le
    shapefile — et alors les portes qui en dépendent sont déclarées non mesurables
    plutôt que sautées en silence.
    """
    if ZF_TABLE.exists():
        from llm_module.core.residence_zone import CouronneTable
        return (CouronneTable.load(ZF_TABLE).secteurs,
                f"{ZF_TABLE.name} (table versionnée)")
    if SIG_DTIR.exists():
        import geopandas as gpd
        dtir = gpd.read_file(SIG_DTIR)
        return (dict(zip(dtir["NUM_DTIR"].astype(str), dtir["NOM_D2"])),
                f"{SIG_DTIR.name} (accès restreint lil-1750)")
    return None, "aucune source de couronne par secteur"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--population", type=Path, default=DEFAULT_POPULATION)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE,
                        help="CSV de recoupement indépendant (ticket 020)")
    parser.add_argument("--trace", type=Path, default=None,
                        help="Répertoire où archiver le rapport JSON")
    args = parser.parse_args()

    for resource in (ZF_GPKG, COURONNE_GEOJSON):
        if not resource.exists():
            print(f"[ERREUR] ressource absente : {resource} "
                  f"(make zones / make communes-couronnes)", file=sys.stderr)
            return EXIT_RESOURCE_MISSING

    import geopandas as gpd
    from pyproj import Transformer

    from llm_module.core.residence_zone import CommunalZones
    from llm_module.core.zone_resolver import ZoneResolver

    secteurs, source = secteur_couronne_map()
    report: dict = {"generated_at": date.today().isoformat(), "ticket": "021",
                    "lot": 0, "source_couronne_par_secteur": source, "portes": {}}
    portes: dict[str, object] = {}

    # ── A · le rattachement zone fine → secteur ──────────────────────────────
    title("A · Rattachement par préfixe : les 785 zones fines vers les 88 secteurs")
    gpkg = gpd.read_file(ZF_GPKG)
    gpkg["prefixe"] = gpkg["ZF"].astype(str).str[:3]
    prefixes = sorted(set(gpkg["prefixe"]))

    if secteurs is None:
        print(f"{NOT_MEASURABLE} — {source}")
        portes["A · aucune zone fine orpheline"] = NOT_MEASURABLE
        portes["A · tous les secteurs atteints"] = NOT_MEASURABLE
        orphelines, sans_zone = [], []
    else:
        orphelines = sorted(set(prefixes) - set(secteurs))
        sans_zone = sorted(set(secteurs) - set(prefixes))
        inconnues = sorted(set(secteurs.values()) - set(COURONNES))
        print(f"secteurs connus                   : {len(secteurs)}")
        print(f"préfixes distincts sur 785 zones  : {len(prefixes)}")
        print(f"zones fines orphelines            : {len(orphelines)} {orphelines[:5]}")
        print(f"secteurs sans aucune zone fine    : {sans_zone or '—'}")
        print(f"modalités hors COURONNES          : {inconnues or '—'}")
        portes["A · aucune zone fine orpheline"] = not orphelines
        portes["A · tous les secteurs atteints"] = not sans_zone
    report["A"] = {"n_secteurs": len(secteurs) if secteurs else None,
                   "n_prefixes": len(prefixes), "orphelines": orphelines,
                   "secteurs_sans_zone": sans_zone}

    zones = CommunalZones.load(COURONNE_GEOJSON)

    # ── B · équivalence 1, au grain zone fine ────────────────────────────────
    title("B · Équivalence 1 — préfixe contre appartenance géométrique (785 zones)")
    desaccords_b: list[dict] = []
    if secteurs is None:
        print(f"{NOT_MEASURABLE} — {source}")
        portes["B · préfixe == géométrie sur les 785 zones"] = NOT_MEASURABLE
    else:
        to_wgs = Transformer.from_crs(2154, 4326, always_xy=True)
        for row in gpkg.itertuples():
            attendu = secteurs.get(row.prefixe)
            # Deux points par zone : le centroïde publié dans la ressource — celui que le
            # test du lot 1 utilisera — et le point représentatif du polygone, qui reste
            # dedans même pour une zone concave.
            lon_c, lat_c = to_wgs.transform(row.XL93, row.YL93)
            rep = row.geometry.representative_point()
            lon_r, lat_r = to_wgs.transform(rep.x, rep.y)
            geo_c, geo_r = zones.classify(lat_c, lon_c), zones.classify(lat_r, lon_r)
            if attendu != geo_c or attendu != geo_r:
                desaccords_b.append({"zf": str(row.ZF), "par_prefixe": attendu,
                                     "geo_centroide": geo_c,
                                     "geo_representatif": geo_r})
        accord = len(gpkg) - len(desaccords_b)
        print(f"accord : {accord}/{len(gpkg)} = {100.0 * accord / len(gpkg):.2f} %")
        for item in desaccords_b[:12]:
            print(f"  ZF {item['zf']} — préfixe « {item['par_prefixe']} » / centroïde "
                  f"« {item['geo_centroide']} » / représentatif "
                  f"« {item['geo_representatif']} »")
        portes["B · préfixe == géométrie sur les 785 zones"] = not desaccords_b
    report["B"] = {"n": len(gpkg), "desaccords": desaccords_b}

    # ── C · équivalence 1, au grain domicile ─────────────────────────────────
    title("C · Équivalence 1 — les domiciles de la population, préfixe contre géométrie")
    if not args.population.exists():
        print(f"[ERREUR] population absente : {args.population}", file=sys.stderr)
        return EXIT_RESOURCE_MISSING
    raw = json.loads(args.population.read_text(encoding="utf-8"))
    people = raw if isinstance(raw, list) else (raw.get("people") or raw.get("personas"))
    resolver = ZoneResolver.load()

    rows: list[dict] = []
    for person in people:
        home = (person.get("identity") or {}).get("home") or {}
        lat, lon = home.get("lat"), home.get("lon")
        zone = resolver.resolve(lat, lon) if lat is not None and lon is not None else None
        if zone is None:
            par_prefixe = OUT_OF_PERIMETER
        elif secteurs is None:
            par_prefixe = NOT_MEASURABLE
        else:
            par_prefixe = secteurs.get(str(zone.zf)[:3], "SECTEUR INCONNU")
        rows.append({"person_id": person_id(person),
                     "zf": str(zone.zf) if zone else "",
                     "par_prefixe": par_prefixe,
                     "geometrique": zones.classify(lat, lon)})

    if secteurs is None:
        print(f"{NOT_MEASURABLE} — {source}")
        portes["C · préfixe == géométrie sur les domiciles"] = NOT_MEASURABLE
        desaccords_c: list[dict] = []
    else:
        desaccords_c = [r for r in rows if r["par_prefixe"] != r["geometrique"]]
        accord = len(rows) - len(desaccords_c)
        print(f"accord : {accord}/{len(rows)} = {100.0 * accord / len(rows):.2f} %")
        print("répartition par préfixe :", dict(Counter(r["par_prefixe"] for r in rows)))
        print("répartition géométrique :", dict(Counter(r["geometrique"] for r in rows)))
        for item in desaccords_c[:12]:
            print(f"  {item['person_id']} ZF {item['zf'] or '—'} — préfixe "
                  f"« {item['par_prefixe']} » / géométrie « {item['geometrique']} »")
        portes["C · préfixe == géométrie sur les domiciles"] = not desaccords_c
    report["C"] = {"n": len(rows), "n_desaccords": len(desaccords_c),
                   "desaccords": desaccords_c[:50]}

    # ── D · équivalence 2, les deux emprises ─────────────────────────────────
    title("D · Équivalence 2 — hors COUCHE de zones fines contre hors PÉRIMÈTRE")
    hors_couche = {r["person_id"] for r in rows if not r["zf"]}
    hors_perimetre = {r["person_id"] for r in rows
                      if r["geometrique"] == OUT_OF_PERIMETER}
    couche_seule = sorted(hors_couche - hors_perimetre)
    perimetre_seul = sorted(hors_perimetre - hors_couche)
    print(f"hors couche de zones fines        : {len(hors_couche)}")
    print(f"hors des quatre couronnes         : {len(hors_perimetre)}")
    print(f"hors couche mais dans le périmètre: {couche_seule[:10] or '—'} "
          f"({len(couche_seule)})")
    print(f"dans la couche mais hors périmètre: {perimetre_seul[:10] or '—'} "
          f"({len(perimetre_seul)})")
    coverage = resolver.coverage()
    print(f"couverture du resolver            : {coverage}")
    portes["D · hors couche == hors périmètre"] = not (couche_seule or perimetre_seul)
    report["D"] = {"hors_couche": len(hors_couche),
                   "hors_perimetre": len(hors_perimetre),
                   "couche_seule": couche_seule, "perimetre_seul": perimetre_seul,
                   "coverage": coverage}

    # ── E · recoupement indépendant ──────────────────────────────────────────
    title("E · Recoupement contre la trace du ticket 020 (chemin indépendant)")
    if not args.archive.exists():
        print(f"{NOT_MEASURABLE} — trace absente : {args.archive}")
        portes["E · accord avec la trace du ticket 020"] = NOT_MEASURABLE
        ecarts_e: list[tuple] = []
        archive: dict = {}
    else:
        archive = {row["person_id"]: row
                   for row in csv.DictReader(args.archive.open(encoding="utf-8"))}
        apparies = [r for r in rows if r["person_id"] in archive]
        ecarts_e = [(r["person_id"], r["par_prefixe"],
                     archive[r["person_id"]]["zone_communale"])
                    for r in apparies
                    if r["par_prefixe"] != archive[r["person_id"]]["zone_communale"]]
        print(f"personas appariés                 : {len(apparies)}/{len(rows)}")
        print(f"accord préfixe ↔ colonne archivée : "
              f"{len(apparies) - len(ecarts_e)}/{len(apparies)}")
        for pid, recalcule, archive_value in ecarts_e[:12]:
            print(f"  {pid} — recalculé « {recalcule} » / archivé « {archive_value} »")
        portes["E · accord avec la trace du ticket 020"] = (
            not ecarts_e if apparies else NOT_MEASURABLE)
    report["E"] = {"n_ecarts": len(ecarts_e), "ecarts": ecarts_e[:50]}

    # ── F · la commune, que la table du lot 1 doit publier ───────────────────
    title("F · ZF → INSEE : la commune est-elle reproductible depuis le code de zone ?")
    ecarts_f: list[tuple] = []
    if not SIG_ZF.exists() and not ZF_TABLE.exists():
        print(f"{NOT_MEASURABLE} — ni {ZF_TABLE.name} ni la couche SIG des zones fines")
        portes["F · ZF → INSEE reproduit la commune archivée"] = NOT_MEASURABLE
    elif not archive:
        print(f"{NOT_MEASURABLE} — pas de trace de recoupement")
        portes["F · ZF → INSEE reproduit la commune archivée"] = NOT_MEASURABLE
    else:
        if ZF_TABLE.exists():
            from llm_module.core.residence_zone import CouronneTable
            table = CouronneTable.load(ZF_TABLE)
            zf_insee = {z: table.commune_of_zf(z)[0]
                        for z in {r["zf"] for r in rows if r["zf"]}
                        if table.commune_of_zf(z)}
        else:
            zf_shp = gpd.read_file(SIG_ZF)
            zf_insee = {str(z): str(i)
                        for z, i in zip(zf_shp["ZF"], zf_shp["INSEE"])}
        manquantes = sorted({r["zf"] for r in rows if r["zf"] and r["zf"] not in zf_insee})
        for row in rows:
            if not row["zf"] or row["person_id"] not in archive:
                continue
            attendu = archive[row["person_id"]]["INSEE"]
            obtenu = zf_insee.get(row["zf"], "")
            if attendu and obtenu != attendu:
                ecarts_f.append((row["person_id"], row["zf"], obtenu, attendu))
        print(f"zones fines sans INSEE            : {len(manquantes)}")
        print(f"écarts INSEE recalculé ↔ archivé  : {len(ecarts_f)}")
        for pid, zf, obtenu, attendu in ecarts_f[:12]:
            print(f"  {pid} ZF {zf} — recalculé {obtenu} / archivé {attendu}")
        portes["F · ZF → INSEE reproduit la commune archivée"] = not (ecarts_f
                                                                     or manquantes)
        report["F"] = {"zf_sans_insee": manquantes, "n_ecarts": len(ecarts_f),
                       "ecarts": ecarts_f[:50]}

    # ── verdict ──────────────────────────────────────────────────────────────
    title("VERDICT")
    for label, state in portes.items():
        mark = NOT_MEASURABLE if state == NOT_MEASURABLE else ("PASSE" if state
                                                               else "ÉCHOUE")
        print(f"  {mark:14} {label}")
    report["portes"] = {k: (v if v == NOT_MEASURABLE else bool(v))
                        for k, v in portes.items()}

    if args.trace:
        args.trace.mkdir(parents=True, exist_ok=True)
        out = args.trace / "couronne_equivalences.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        # `--trace` peut être relatif : `relative_to` lèverait alors, APRÈS l'écriture.
        shown = out.resolve()
        try:
            shown = shown.relative_to(REPO_ROOT)
        except ValueError:
            pass
        print(f"\nrapport → {shown}")

    if any(state is False for state in portes.values()):
        print("\n  → une porte ÉCHOUE : le ticket 021 doit être reconçu avant tout code.")
        return EXIT_GATE_FAILED
    if any(state == NOT_MEASURABLE for state in portes.values()):
        print(f"\n  → au moins une porte {NOT_MEASURABLE} : une porte non mesurée est une "
              f"porte qui passe, elle ne vaut pas verdict.")
        return EXIT_NOT_MEASURABLE
    print("\n  → les portes passent : les lots 1 à 5 peuvent être écrits tels quels.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
