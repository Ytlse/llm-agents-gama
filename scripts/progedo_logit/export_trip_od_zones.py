"""export_trip_od_zones.py — Zones fines d'origine et de destination des déplacements enquêtés.

Le jeu de choix modal (`mode_choice_{train,test}.csv`) porte les 21 variables et le mode
déclaré, mais **pas** `ZF_orig` / `ZF_dest` : `build_mode_choice_dataset.build_trips` les
dérive puis ne les exporte pas — les six variables géographiques suffisaient à
l'entraînement. L'audit unitaire du ticket 058 en a besoin : sans les deux zones, il n'y a
pas d'origine ni de destination à router, donc pas d'offre, donc rien à choisir.

Ce que le script écrit (à côté du jeu, dans un dossier gitignoré) :

    mode_choice_<split>_od.csv   4 clés + ZF_orig/ZF_dest + heures déclarées + diagnostics

**Aucune valeur n'est recalculée ici.** La troncature des codes de zone est importée de
`build_mode_choice_dataset` (`zone_key`, `ZONE_CODE_WIDTH`) : deux définitions concurrentes
de la même zone, c'est exactement ce que `feature_spec.json` existe pour empêcher.

Les microdonnées lil-1750 sont d'accès restreint. La sortie ne quitte pas le poste :
`scripts/progedo_logit/*.csv` est ignoré par git, et ce fichier porte des identifiants
d'enquêtés — il ne se versionne pas et ne se monte pas dans les conteneurs.

Usage :
    llm-agents/.venv/bin/python -m scripts.progedo_logit.export_trip_od_zones [--split test]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import locale

import pandas as pd
from loguru import logger

locale.setlocale(locale.LC_NUMERIC, "fr_FR.UTF-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_mode_choice_dataset import ZONE_CODE_WIDTH, zone_key  # noqa: E402

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
PROGEDO = RACINE / "data" / "PROGEDO 2023" / "lil-1750-Donnees_CSV" / "fichiers_standards"
COUCHE_ZONES = (
    RACINE / "packages" / "mobility_core" / "src" / "mobility_core" / "data" / "zf_zones.gpkg"
)

CLES = ["ZF", "ECH", "PER", "NDEP"]

# Sous ce taux d'appariement, l'échantillon n'est plus celui qu'on croit tirer : on le dit
# fort plutôt que de laisser un audit se construire sur un jeu amputé en silence.
SEUIL_APPARIEMENT_ALARME = 0.99
# Les codes hors périmètre d'enquête (préfixes 98x, 93x, 909) ne sont pas dans la couche :
# 4,2 % des déplacements, documentés comme devant rester non résolus.
SEUIL_ROUTABLE_ALARME = 0.90


def charger_deplacements() -> pd.DataFrame:
    """Le fichier déplacements, réduit aux colonnes dont l'audit a besoin."""
    fichier = PROGEDO / "Toulouse_2023_std_depl.csv"
    if not fichier.exists():
        raise SystemExit(
            f"Microdonnées introuvables : {fichier}\n"
            "Le dossier `data/PROGEDO 2023` n'est pas versionné (accès restreint lil-1750)."
        )
    depl = pd.read_csv(fichier, dtype=str)
    logger.info(f"Fichier déplacements lu : {len(depl):n} lignes")
    return pd.DataFrame({
        "ZF": depl["ZFD"],
        "ECH": depl["ECH"],
        "PER": depl["PER"],
        "NDEP": depl["NDEP"],
        "ZF_orig": zone_key(depl["D3"]),
        "ZF_dest": zone_key(depl["D7"]),
        # Heures déclarées au format HHMM. `departure_hour` du jeu n'en garde que l'heure
        # pleine ; l'offre TC se calcule à la minute, d'où la valeur brute ici.
        "depart_hhmm": depl["D4"],
        "arrivee_hhmm": depl["D8"],
        # Diagnostic uniquement (contaminées par le mode, ticket 005 §1) : elles servent à
        # vérifier que la zone retenue situe bien le déplacement, jamais à décider.
        "duree_declaree_min": pd.to_numeric(depl["D9"], errors="coerce"),
        "vol_oiseau_declare_km": pd.to_numeric(depl["D11"], errors="coerce") / 1000,
    })


def zones_de_la_couche() -> set[str]:
    """Les codes de zone que la couche embarquée sait situer."""
    if not COUCHE_ZONES.exists():
        logger.warning(f"Couche de zones absente ({COUCHE_ZONES}) : routabilité non vérifiée")
        return set()
    import geopandas as gpd

    couche = gpd.read_file(COUCHE_ZONES)
    colonne = "ZF" if "ZF" in couche.columns else couche.columns[0]
    return set(couche[colonne].astype(str).str.strip())


def exporter(split: str) -> Path:
    debut = time.monotonic()
    logger.info(f"=== Export des zones OD — split « {split} » ===")

    jeu_fichier = ICI / f"mode_choice_{split}.csv"
    if not jeu_fichier.exists():
        raise SystemExit(f"Jeu introuvable : {jeu_fichier}")
    jeu = pd.read_csv(jeu_fichier, dtype={c: str for c in CLES})
    logger.info(f"Jeu « {split} » : {len(jeu):n} déplacements")

    depl = charger_deplacements()

    doublons = int(depl.duplicated(CLES).sum())
    if doublons:
        logger.error(
            f"[ALARME] {doublons} clés en double dans le fichier déplacements "
            f"({CLES}) : la jointure serait ambiguë, export interrompu"
        )
        raise SystemExit(1)

    fusion = jeu[CLES].merge(depl, on=CLES, how="left", indicator=True)
    apparies = int((fusion["_merge"] == "both").sum())
    taux = apparies / len(fusion) if len(fusion) else 0.0
    logger.info(
        f"Appariement sur {'/'.join(CLES)} : {apparies:n}/{len(fusion):n} ({taux:.1%})"
    )
    if taux < SEUIL_APPARIEMENT_ALARME:
        logger.error(
            f"[ALARME] Appariement dégradé : {taux:.1%} < {SEUIL_APPARIEMENT_ALARME:.0%} "
            f"— {len(fusion) - apparies} déplacements du split « {split} » sans ligne source ; "
            "l'échantillon tiré ne serait pas celui du jeu scellé"
        )

    sortie = fusion[fusion["_merge"] == "both"].drop(columns="_merge").copy()

    connues = zones_de_la_couche()
    if connues:
        sortie["orig_situee"] = sortie["ZF_orig"].isin(connues)
        sortie["dest_situee"] = sortie["ZF_dest"].isin(connues)
        sortie["routable"] = sortie["orig_situee"] & sortie["dest_situee"]
        n_routable = int(sortie["routable"].sum())
        part = n_routable / len(sortie) if len(sortie) else 0.0
        logger.info(
            f"Zones situées dans la couche ({len(connues)} zones, codes à "
            f"{ZONE_CODE_WIDTH} chiffres) : {n_routable:n}/{len(sortie):n} "
            f"déplacements routables ({part:.1%})"
        )
        logger.info(
            f"  origine hors couche : {int((~sortie['orig_situee']).sum()):n} · "
            f"destination hors couche : {int((~sortie['dest_situee']).sum()):n}"
        )
        if part < SEUIL_ROUTABLE_ALARME:
            logger.error(
                f"[ALARME] Routabilité {part:.1%} < {SEUIL_ROUTABLE_ALARME:.0%} : "
                "le tirage de l'audit perdrait plus d'un déplacement sur dix"
            )

    intra = int((sortie["ZF_orig"] == sortie["ZF_dest"]).sum())
    logger.info(
        f"Déplacements intra-zone (origine = destination après troncature) : {intra:n} "
        f"({intra / len(sortie):.1%}) — centroïdes confondus, non routables tels quels"
    )

    fichier_sortie = ICI / f"mode_choice_{split}_od.csv"
    sortie.to_csv(fichier_sortie, index=False)
    logger.success(
        f"Écrit : {fichier_sortie.name} — {len(sortie):n} lignes, "
        f"{len(sortie.columns)} colonnes, en {time.monotonic() - debut:.1f} s"
    )
    return fichier_sortie


def main() -> None:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument(
        "--split",
        default="test",
        choices=["test", "train"],
        help="partition à enrichir (défaut : test, celle de l'audit unitaire)",
    )
    exporter(parseur.parse_args().split)


if __name__ == "__main__":
    main()
