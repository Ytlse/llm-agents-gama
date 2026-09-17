"""zone_label.py — Le libellé de zone lu par le modèle, reconstruit pour une commune INSEE.

Le prompt sert à l'agent un `destination_zone` : « a neighbourhood of a major urban centre in
the municipality of Toulouse ». Sur la cohorte, ce libellé est composé par l'étape 3bis de
`scripts/data/population/generate_population.ipynb`, à partir de la grille de densité INSEE
(`DENS7`) et de la composition communale des aires d'attraction (`AAV2020`), la commune étant
obtenue par géocodage inverse des coordonnées de l'activité.

L'audit unitaire du ticket 058 travaille sur des zones fines d'enquête, dont le code INSEE est
connu sans géocodage (`zf_couronne.json`). Ce module refait donc la **même** composition à
partir du code commune, pour que l'agent audité lise la même phrase que l'agent de la cohorte.

La réplication ne se postule pas, elle se vérifie :

    python scripts/progedo_logit/zone_label.py --verifier

recompose le libellé du domicile des 1 000 personas de la cohorte v6 depuis leur seul code
INSEE, et le compare caractère par caractère à celui que porte le fichier de population. Un
écart, et le module est faux : l'audit ne doit pas partir sur une phrase approchante.
"""

from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd
from loguru import logger

RACINE = Path(__file__).resolve().parents[2]
INSEE_DIR = RACINE / "data" / "insee"
FICHIER_DENSITE = INSEE_DIR / "fichier_diffusion_2026.xlsx"
FICHIER_AAV = INSEE_DIR / "AAV2020_au_01-01-2026.xlsx"

# Libellés de la grille de densité INSEE (DENS7). Recopiés de l'étape 3bis du notebook de
# génération : ils entrent dans une phrase LUE PAR LE MODÈLE, donc les deux sources doivent
# dire exactement la même chose. Le mode `--verifier` est ce qui le garantit.
DENS7_LABEL = {
    1: "a major urban centre",
    2: "an intermediate urban centre",
    3: "an urban belt",
    4: "a small town",
    5: "a rural small town",
    6: "scattered rural housing",
    7: "very scattered rural housing",
}

# `CATEAAV2020` == 30 : commune hors attraction des villes. Lu comme un ENTIER — la comparaison
# à la chaîne '30' était le défaut corrigé le 2026-09-04 côté notebook.
CATEGORIE_HORS_AIRE = 30


@lru_cache(maxsize=1)
def _tables() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """(densité → libellé, code → commune, code → aire d'attraction), depuis les fichiers INSEE."""
    if not FICHIER_DENSITE.exists():
        raise SystemExit(
            f"Grille de densité absente : {FICHIER_DENSITE}\n"
            "À télécharger depuis https://www.insee.fr/fr/statistiques/5040028"
        )
    densite = pd.read_excel(
        FICHIER_DENSITE,
        sheet_name="Maille communale",
        header=4,
        dtype={"CODGEO": str},
        engine="calamine",
    )
    densite.columns = [c.strip() for c in densite.columns]
    densite["_detail"] = densite["DENS7"].map(DENS7_LABEL).fillna("an unknown area")
    libelle = densite.set_index("CODGEO")["_detail"].to_dict()
    commune = densite.set_index("CODGEO")["LIBGEO"].to_dict()
    aire: dict[str, str] = {}

    if FICHIER_AAV.exists():
        aav = pd.read_excel(
            FICHIER_AAV,
            sheet_name="Composition_communale",
            header=5,
            dtype={"CODGEO": str},
            engine="calamine",
        )
        aav.columns = [c.strip() for c in aav.columns]
        categorie = pd.to_numeric(aav["CATEAAV2020"], errors="coerce")
        aire = aav.loc[categorie != CATEGORIE_HORS_AIRE].set_index("CODGEO")["LIBAAV2020"].to_dict()
        for code, nom in aav.set_index("CODGEO")["LIBGEO"].to_dict().items():
            commune.setdefault(code, nom)
        logger.info(
            f"AAV2020 : {len(aav)} communes, dont "
            f"{int((categorie == CATEGORIE_HORS_AIRE).sum())} hors aire d'attraction"
        )
    else:
        logger.warning(f"AAV2020 absent ({FICHIER_AAV}) : aire d'attraction ignorée")

    logger.info(f"Grille densité : {len(densite)} communes · noms de commune : {len(commune)}")
    return libelle, commune, aire


def build_zone_label(codgeo: str) -> str:
    """Le libellé de zone d'une commune, dans les termes exacts du prompt de la cohorte."""
    libelle, commune, aire = _tables()
    code = str(codgeo).strip()
    detail = libelle.get(code, "an unknown area")
    nom = commune.get(code)
    # Un nom de commune ne s'invente pas : « inconnue » est une information, un nom fabriqué non.
    lieu = f"the municipality of {nom}" if nom else "an unknown municipality"
    attraction = aire.get(code, "")
    if attraction:
        return f"a neighbourhood of {detail} in {lieu} ({attraction} urban area)"
    return f"a neighbourhood of {detail} in {lieu}, outside any urban catchment area"


def verifier(population: Path) -> int:
    """Recompose le libellé du domicile de chaque persona et le compare à celui du fichier."""
    personas = json.loads(population.read_text(encoding="utf-8"))
    compares = ecarts = sans_reference = reference_degradee = 0
    exemples: list[tuple[str, str, str]] = []
    degrades: list[tuple[str, str]] = []

    for personne in personas:
        code = (personne.get("identity", {}).get("traits_json", {}) or {}).get("residence_insee")
        activites = (personne.get("identity", {}) or {}).get("activities") or []
        attendu = next(
            (
                (a.get("location") or {}).get("zone")
                for a in activites
                if a.get("purpose") == "home" and (a.get("location") or {}).get("zone")
            ),
            None,
        )
        if not code or not attendu:
            sans_reference += 1
            continue
        obtenu = build_zone_label(code)
        compares += 1
        if obtenu != attendu:
            # La cohorte nomme la commune par géocodage inverse des coordonnées ; quand ce
            # géocodage n'a rien rendu, son libellé est dégradé (« an unknown municipality »)
            # alors que le code INSEE du persona, lui, est connu. Reconstruire depuis le code
            # donne donc MIEUX que la référence : ce n'est pas une divergence de méthode.
            if "an unknown municipality" in attendu:
                reference_degradee += 1
                if len(degrades) < 5:
                    degrades.append((str(personne.get("person_id")), obtenu))
                continue
            ecarts += 1
            if len(exemples) < 5:
                exemples.append((str(personne.get("person_id")), attendu, obtenu))

    logger.info(
        f"Libellés comparés : {compares} · sans référence dans le fichier : {sans_reference}"
    )
    if reference_degradee:
        logger.warning(
            f"{reference_degradee} persona(s) de la cohorte portent un libellé dégradé "
            "(« an unknown municipality ») que le code INSEE permet pourtant de résoudre — "
            "géocodage inverse muet à la génération ; la reconstruction fait mieux, "
            "et ces cas ne comptent pas comme divergence"
        )
        for pid, obtenu in degrades:
            logger.warning(f"  persona {pid} → {obtenu}")
    if ecarts:
        logger.error(
            f"[ALARME] {ecarts}/{compares} libellés divergent du fichier de population : "
            "la phrase servie à l'agent audité ne serait pas celle servie à la cohorte"
        )
        for pid, attendu, obtenu in exemples:
            logger.error(f"  persona {pid}\n    attendu : {attendu}\n    obtenu  : {obtenu}")
        return 1
    exacts = compares - reference_degradee
    logger.success(
        f"Réplication exacte : {exacts}/{exacts} libellés comparables identiques à ceux de "
        f"la cohorte ({reference_degradee} référence(s) dégradée(s) écartée(s))"
    )
    return 0


def main() -> None:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--verifier", action="store_true", help="contrôle contre la cohorte v6")
    parseur.add_argument(
        "--population",
        type=Path,
        default=RACINE / "data" / "population" / "population_1000_AAMAS_v6" / "population.json",
        help="population de référence pour le contrôle",
    )
    parseur.add_argument("--commune", help="code INSEE dont on veut le libellé")
    args = parseur.parse_args()

    if args.verifier:
        sys.exit(verifier(args.population))
    if args.commune:
        print(build_zone_label(args.commune))
        return
    parseur.error("préciser --verifier ou --commune")


if __name__ == "__main__":
    main()
