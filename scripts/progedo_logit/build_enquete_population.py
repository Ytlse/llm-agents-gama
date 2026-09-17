"""build_enquete_population.py — Les journées déclarées de l'enquête, en population lisible.

L'audit unitaire du ticket 058 mesure l'accord déplacement par déplacement entre un décideur
et le mode qu'une personne réelle a déclaré. La cohorte scellée ne peut pas le porter : aucun
de ses personas n'a déclaré quoi que ce soit. La référence est donc l'enquête, et il faut la
présenter à la chaîne de décision sous la forme qu'elle sait lire — une population.

Ce que le script écrit :

    data/population/population_enquete_058_<split>/population.json   les enquêtés et leur journée
    data/population/population_enquete_058_<split>/dates_meteo.json  le jour décrit, par personne
    scripts/progedo_logit/verite_058_<split>.csv                     le mode déclaré, à part

`dates_meteo.json` vit **à côté** de la population, et non dedans : la date du jour décrit
n'est pas un trait de la personne, elle ne doit entrer ni dans le narratif ni dans la clé du
cache de décisions. Le runner la ramasse par convention quand le fichier existe, et le
dispositif « une météo par agent » lit alors le jour réel au lieu d'en tirer un.

**La vérité terrain vit dans un second fichier, et c'est structurant.** Le mode déclaré est la
réponse au problème posé au décideur. Dans la population, il finirait dans `traits_json`, donc
dans le narratif du prompt et dans la clé du cache de décisions. Il reste dehors.

## Ce qui est servi au modèle, et ce qui ne l'est pas

Le narratif de l'agent (`_build_profile_narrative`) lit sept champs : prénom, âge, occupation,
taille du ménage, revenu, motifs habituels, couronne de résidence. Quatre sortent des 21
variables du contrat de parité, et l'arbitrage de l'auteur est de servir ce que l'enquête
permet de reconstruire, sans rien fabriquer :

| Champ | Décision | Raison |
|---|---|---|
| `residence_zone` | **servi** | la couronne se déduit de la zone fine de résidence |
| `travel_purposes` | **servi** | les motifs de la journée déclarée, comme sur la cohorte |
| `name` | **tiré par graine** | voir ci-dessous : l'omettre le fait fabriquer en aval, sans graine |
| `income` | omis | EMC² Toulouse 2023 ne porte aucune variable de revenu |
| `professional_activity` | omis | sa nomenclature vient d'eqasim, pas de l'enquête ; le narratif
  retombe alors sur `main_occupation`, qui est son chemin de repli documenté |

`personal_bike` n'entre pas dans le narratif depuis le 2026-08-26, mais la règle de chaîne le
lit pour savoir si le vélo est prenable : il est donc posé depuis `has_bike`, l'une des 21.

**Le prénom ne peut pas être simplement omis.** `eqasim_loader.load_population_from_data`
remplace un `name` vide par un tirage `Faker("fr_FR")` **sans graine** : le prompt changerait
d'une exécution à l'autre, et avec lui la clé du cache de décisions. Le prénom est donc tiré
ici, par graine dérivée du `person_id`, exactement comme la cohorte v6 le fait depuis le
ticket 074. Aucune information d'enquête n'est fabriquée au passage : le prénom est synthétique
des deux côtés de la comparaison, et c'est ce qui garde au prompt la même forme.

**Le libellé de zone est écrit, et le loader le jette.** Chaque activité porte un `zone`
composé par `zone_label.py`, comme sur la cohorte. `eqasim_loader._parse_activity` construit
pourtant ses `Location` sans ce champ : sur le bras de référence v6, le prompt part donc avec
`destination_zone: None` (7 récits sur 3 161 y échappent, par un autre chemin). Le champ est
conservé ici par fidélité à la structure du fichier de cohorte, et la parité est tenue
**parce que** les deux côtés le perdent. Ce n'est pas à corriger dans le cadre de l'audit :
rendre la phrase au modèle changerait le prompt de tous les bras déjà joués.

## Les écarts au terrain, déclarés

1. **Origine et destination sont des centroïdes de zone fine.** Les microdonnées ne portent pas
   de coordonnées, et la convention `lil-1750` interdit d'en redistribuer.
2. **Les déplacements intra-zone sont écartés.** Entre deux centroïdes confondus il n'y a pas
   d'itinéraire à calculer. Ils sont courts, donc surtout à pied : le script chiffre la part de
   marche perdue pour que le biais soit lisible, pas seulement mentionné.
3. **Onze enchaînements sont rompus par l'exclusion des intra-zone.** Le constructeur de jeu
   route d'une activité à la suivante : l'origine d'un déplacement est donc la destination du
   précédent. Quand un déplacement intra-zone a été retiré au milieu d'une journée, l'origine
   routée n'est plus celle que l'enquêté a déclarée. Mesuré : 11 enchaînements sur 6 702
   (0,2 %), 11 enquêtés. Ces déplacements portent `chaine_rompue = 1` dans le fichier de vérité
   et sortent de l'audit — 11 sur 9 632 ne déplacent aucune métrique, et les garder ferait
   comparer un choix à un déplacement qui n'est pas celui-là.
4. **La journée commence là où l'enquêté était.** Les véhicules du ménage sont au domicile au
   début de journée, comme dans la règle de chaîne. Un enquêté dont le premier déplacement ne
   part pas du domicile n'a donc pas sa voiture sous la main : le compte est journalisé.

Le fichier produit porte des attributs d'enquêtés sous convention `lil-1750`. `data/.gitignore`
ignore déjà `/population/*` : il ne se versionne pas, et ne se monte pas hors de ce poste.

Usage :
    services/llm-agents/.venv/bin/python scripts/progedo_logit/build_enquete_population.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import locale
import sys
import time
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from loguru import logger

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
sys.path.insert(0, str(RACINE / "packages" / "mobility_core" / "src"))
sys.path.insert(0, str(ICI))

from faker import Faker  # noqa: E402
from mobility_core.bike_ownership import NO_BIKE, PLAIN_BIKE  # noqa: E402
from mobility_core.residence_zone import CouronneTable  # noqa: E402
from zone_label import build_zone_label  # noqa: E402

try:
    locale.setlocale(locale.LC_NUMERIC, "fr_FR.UTF-8")
except locale.Error:  # pragma: no cover — poste sans locale française
    pass

PROGEDO = RACINE / "data" / "PROGEDO 2023" / "lil-1750-Donnees_CSV" / "fichiers_standards"
COUCHE_ZONES = (
    RACINE / "packages" / "mobility_core" / "src" / "mobility_core" / "data" / "zf_zones.gpkg"
)

CLES_PERSONNE = ("ZF", "ECH", "PER")

# Identifiants stables : deux exécutions doivent produire les mêmes `person_id` et les mêmes
# `activity_id`, sinon le cache de décisions et la jointure avec la vérité terrain se cassent
# d'un run à l'autre.
NAMESPACE_058 = uuid.uuid5(uuid.NAMESPACE_URL, "llm-agents-gama/ticket-058/audit-unitaire")

# `main_occupation` de l'enquête → modalité anglaise du persona. C'est l'inverse de
# `population_reference.OCCUPATION_ENQUETE`, dont les valeurs sont figées avec les artefacts
# ajustés : on traduit la réponse de l'enquêté, on n'en invente pas une.
OCCUPATION_ANGLAIS = {
    "Scolaire (jusqu'au Bac)": "Pupil (up to Baccalaureate)",
    "Étudiant": "Student",
    "Travail à plein temps": "Full-time worker",
    "Travail à temps partiel": "Part-time worker",
    "Chômeur/recherche d'emploi": "Unemployed / job seeker",
    "Personne au foyer": "Homemaker",
    "Retraité": "Retired",
    # La cohorte n'expose pas cette modalité, mais c'est la réponse donnée par l'enquêté :
    # la traduire est une traduction, l'écarter serait une perte.
    "Autre": "Other",
}

# Motifs de la journée → libellés de `travel_purposes`, tels que le narratif les rend.
MOTIF_LIBELLE = {
    "work": "Work",
    "education": "Education",
    "shop": "Shopping",
    "leisure": "Leisure",
    "other": "Other",
    "home": None,  # le domicile n'est pas un motif de sortie
}

VRAI = {"true", "True", "1", "vrai"}

# Bandes de distance du composite agrégé (`prompt_calibration/calibration/metadata.py`,
# `_DIST_BUCKETS`). Le mode dépend d'abord de la distance : l'exclusion des intra-zone ne se
# juge donc pas sur une part de marche globale, mais bande par bande — c'est l'axe que le
# composite pondère déjà (poids 0,3).
BANDES_DISTANCE = ((1, "0-1km"), (2, "1-2km"), (5, "2-5km"), (10, "5-10km"), (20, "10-20km"),
                   (50, "20-50km"))
BANDE_LOINTAINE = "plus_50km"


def _bande(km: float) -> str:
    for seuil, nom in BANDES_DISTANCE:
        if km < seuil:
            return nom
    return BANDE_LOINTAINE

# Même locale que `utils.fake`, dont le loader se sert pour les populations sans prénom.
_FAKER = Faker("fr_FR")


def _nom(person_id: str, gender: str) -> str:
    """Un prénom stable pour un enquêté : fonction pure de (person_id, genre).

    Deux exécutions doivent servir le même prompt, donc le même prénom. Le loader, lui,
    tirerait à l'horloge — c'est le défaut que la cohorte a corrigé au ticket 074.
    """
    graine = int(hashlib.md5(person_id.encode()).hexdigest()[:8], 16)
    _FAKER.seed_instance(graine)
    if gender == "Male":
        return _FAKER.name_male()
    if gender == "Female":
        return _FAKER.name_female()
    return _FAKER.name()

# Au-delà de ce taux de journées inexploitables, l'échantillon n'est plus celui qu'on croit.
SEUIL_PERTE_ALARME = 0.05


def _bool(valeur: str | None) -> bool:
    return str(valeur or "").strip() in VRAI


def _entier(valeur: str | None, defaut: int = 0) -> int:
    try:
        return int(float(str(valeur).strip()))
    except (TypeError, ValueError):
        return defaut


def _secondes(hhmm: str | None) -> float | None:
    """`0815` → 29 700 s. Les heures de 24 à 28 sont celles du lendemain, et restent telles."""
    texte = str(hhmm or "").strip()
    if not texte.isdigit() or not 3 <= len(texte) <= 4:
        return None
    heures, minutes = divmod(int(texte), 100)
    if minutes > 59:
        return None
    return float(heures * 3600 + minutes * 60)


def centroides_wgs84() -> dict[str, tuple[float, float]]:
    """Zone fine → (lon, lat). Les centroïdes sont ceux vus à l'entraînement, reprojetés."""
    import geopandas as gpd

    couche = gpd.read_file(COUCHE_ZONES)
    colonne = "ZF" if "ZF" in couche.columns else couche.columns[0]
    # La couche porte les centroïdes en Lambert 93 ; le simulateur travaille en WGS84.
    points = gpd.GeoSeries(
        gpd.points_from_xy(couche["XL93"], couche["YL93"], crs="EPSG:2154")
    ).to_crs("EPSG:4326")
    return {
        str(zf).strip(): (float(p.x), float(p.y))
        for zf, p in zip(couche[colonne], points, strict=True)
    }


def jours_declares() -> dict[tuple[str, ...], str]:
    """(ZF, ECH, PER) → date du jour décrit, `AAAA-MM-JJ`.

    L'enquête porte sur la veille de l'entretien, et c'est cette journée-là que le fichier
    personnes date : le jour de semaine calculé depuis `AN/MOIS/DATE` vaut `JOUR` (« jour des
    déplacements ») pour 20 462 personnes sur 20 463, et ne tombe jamais un samedi.
    """
    fichier = PROGEDO / "Toulouse_2023_std_pers.csv"
    jours: dict[tuple[str, ...], str] = {}
    with fichier.open(encoding="utf-8", errors="replace") as flux:
        for ligne in csv.DictReader(flux):
            an, mois, jour = (
                (ligne.get("AN") or "").strip(),
                (ligne.get("MOIS") or "").strip(),
                (ligne.get("DATE") or "").strip(),
            )
            if not (an and mois and jour):
                continue
            cle = (
                (ligne.get("ZFP") or "").strip(),
                (ligne.get("ECH") or "").strip(),
                (ligne.get("PER") or "").strip(),
            )
            jours[cle] = f"{an}-{int(mois):02d}-{int(jour):02d}"
    logger.info(f"Dates de journée décrite chargées : {len(jours):n} personnes")
    return jours


def _traits(
    ligne: dict[str, str], couronne: str | None, motifs: list[str], nom: str
) -> dict[str, Any]:
    """Les traits servis à l'agent : les 12 variables persona, la couronne, les motifs."""
    occupation_fr = (ligne.get("main_occupation") or "").strip()
    return {
        "name": nom,
        "age": _entier(ligne.get("age")),
        "gender": (ligne.get("gender") or "").strip(),
        "household_size": _entier(ligne.get("household_size")),
        "has_driving_license": _bool(ligne.get("has_driving_license")),
        "has_pt_subscription": _bool(ligne.get("has_pt_subscription")),
        "number_of_cars": _entier(ligne.get("number_of_cars")),
        "car_availability": (ligne.get("car_availability") or "").strip(),
        "socioprofessional_class": (ligne.get("socioprofessional_class") or "").strip(),
        "main_occupation": OCCUPATION_ANGLAIS.get(occupation_fr, occupation_fr),
        "employed": _bool(ligne.get("employed")),
        "studies": _bool(ligne.get("studies")),
        # Hors narratif depuis le 2026-08-26, mais lu par la règle de chaîne.
        "personal_bike": PLAIN_BIKE if _bool(ligne.get("has_bike")) else NO_BIKE,
        "residence_zone": couronne,
        "travel_purposes": motifs,
    }


def construire(split: str, limite: int | None = None, suffixe: str = "") -> tuple[Path, Path]:
    debut = time.monotonic()
    logger.info(f"=== Population d'enquêtés — split « {split} » ===")

    variables = {}
    with (ICI / f"mode_choice_{split}.csv").open(encoding="utf-8") as flux:
        for ligne in csv.DictReader(flux):
            variables[tuple(ligne[c] for c in (*CLES_PERSONNE, "NDEP"))] = ligne
    logger.info(f"Jeu de choix modal : {len(variables):n} déplacements")

    deplacements: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    intra = 0
    marche_totale = Counter()
    par_bande: dict[str, Counter] = defaultdict(Counter)
    with (ICI / f"mode_choice_{split}_od.csv").open(encoding="utf-8") as flux:
        for ligne in csv.DictReader(flux):
            cle = tuple(ligne[c] for c in (*CLES_PERSONNE, "NDEP"))
            mode = (variables.get(cle) or {}).get("mode", "")
            bande = _bande(float(ligne.get("vol_oiseau_declare_km") or 0.0))
            marche_totale["tous"] += 1
            marche_totale["tous_walk"] += mode == "walk"
            par_bande[bande]["tous"] += 1
            par_bande[bande]["tous_walk"] += mode == "walk"
            if ligne["ZF_orig"] == ligne["ZF_dest"]:
                intra += 1
                continue
            marche_totale["retenus"] += 1
            marche_totale["retenus_walk"] += mode == "walk"
            par_bande[bande]["retenus"] += 1
            par_bande[bande]["retenus_walk"] += mode == "walk"
            deplacements[tuple(ligne[c] for c in CLES_PERSONNE)].append(ligne)

    part_avant = marche_totale["tous_walk"] / max(marche_totale["tous"], 1)
    part_apres = marche_totale["retenus_walk"] / max(marche_totale["retenus"], 1)
    logger.info(
        f"Intra-zone écartés : {intra:n} · retenus : {marche_totale['retenus']:n} "
        f"pour {len(deplacements):n} enquêtés"
    )
    logger.info(
        f"Biais d'échantillon mesuré — part de la marche déclarée : "
        f"{part_avant:.1%} sur tous les déplacements, {part_apres:.1%} sur les retenus "
        f"({(part_apres - part_avant) * 100:+.1f} pt)"
    )

    logger.info(
        "Rétention et part de marche par bande de distance déclarée "
        "(l'axe du composite agrégé) :"
    )
    for bande in [nom for _, nom in BANDES_DISTANCE] + [BANDE_LOINTAINE]:
        compteur = par_bande.get(bande)
        if not compteur or not compteur["tous"]:
            continue
        garde = compteur["retenus"] / compteur["tous"]
        marche_t = compteur["tous_walk"] / compteur["tous"]
        marche_r = compteur["retenus_walk"] / max(compteur["retenus"], 1)
        logger.info(
            f"  {bande:9s} {compteur['retenus']:5d}/{compteur['tous']:5d} gardés ({garde:4.0%}) "
            f"· marche {marche_t:5.1%} → {marche_r:5.1%}"
        )

    centroides = centroides_wgs84()
    couronnes = CouronneTable.load()
    dates = jours_declares()

    personnes: list[dict[str, Any]] = []
    verite: list[dict[str, Any]] = []
    compte = Counter()

    retenues = sorted(deplacements.items())
    if limite:
        # Essai à blanc : les premiers enquêtés dans l'ordre des clés, donc toujours les mêmes.
        retenues = retenues[:limite]
        logger.info(f"Limite d'essai : {limite:n} enquêté(s) sur {len(deplacements):n}")

    for cle, trajets in retenues:
        trajets.sort(key=lambda t: _entier(t["NDEP"]))
        zf_residence = cle[0]

        horaires = [(_secondes(t["depart_hhmm"]), _secondes(t["arrivee_hhmm"])) for t in trajets]
        if any(depart is None or arrivee is None for depart, arrivee in horaires):
            compte["journee_horaires_illisibles"] += 1
            continue
        if any(t["ZF_orig"] not in centroides or t["ZF_dest"] not in centroides for t in trajets):
            compte["journee_zone_hors_couche"] += 1
            continue

        person_id = str(uuid.uuid5(NAMESPACE_058, "|".join(cle)))
        premier = variables[(*cle, trajets[0]["NDEP"])]

        # Motifs de la journée : ceux des destinations, hors domicile, dans l'ordre d'apparition.
        motifs: list[str] = []
        for trajet in trajets:
            libelle = MOTIF_LIBELLE.get(
                (variables[(*cle, trajet["NDEP"])].get("purpose") or "").strip()
            )
            if libelle and libelle not in motifs:
                motifs.append(libelle)

        couronne = couronnes.couronne_of_zf(zf_residence)
        if couronne is None:
            compte["couronne_inconnue"] += 1

        activites: list[dict[str, Any]] = []

        def _lieu(zf: str) -> dict[str, Any]:
            lon, lat = centroides[zf]
            commune = couronnes.commune_of_zf(zf)
            return {
                "lon": lon,
                "lat": lat,
                # Laissé à None VOLONTAIREMENT : le moteur calcule lui-même si un arrêt est
                # atteignable (`otp._has_reachable_stop`) quand le drapeau est absent. Le
                # préremplir depuis une autre source y substituerait une valeur fabriquée.
                "public_transport": None,
                "zone": build_zone_label(commune[0]) if commune else None,
            }

        # Activité d'origine du premier déplacement : son motif est celui de l'origine déclarée.
        origine_motif = (premier.get("purpose_origin") or "other").strip() or "other"
        activites.append({
            "id": str(uuid.uuid5(NAMESPACE_058, f"{person_id}|0")),
            "scheduled_start_time": 0.0,
            "start_time": 0.0,
            "end_time": horaires[0][0],
            "purpose": origine_motif,
            "location": _lieu(trajets[0]["ZF_orig"]),
        })

        for index, (trajet, (depart, arrivee)) in enumerate(zip(trajets, horaires, strict=True), 1):
            motif = (variables[(*cle, trajet["NDEP"])].get("purpose") or "other").strip()
            # L'origine routée est la destination du déplacement retenu précédent. Si un
            # intra-zone a été retiré entre les deux, ce n'est plus l'origine déclarée.
            rompue = index > 1 and trajet["ZF_orig"] != trajets[index - 2]["ZF_dest"]
            if rompue:
                compte["enchainement_rompu"] += 1
            depart_suivant = horaires[index][0] if index < len(horaires) else 86400.0
            activites.append({
                "id": str(uuid.uuid5(NAMESPACE_058, f"{person_id}|{index}")),
                "scheduled_start_time": arrivee,
                "start_time": arrivee,
                "end_time": max(depart_suivant, arrivee),
                "purpose": motif or "other",
                "location": _lieu(trajet["ZF_dest"]),
            })
            verite.append({
                "person_id": person_id,
                "activity_id": activites[-1]["id"],
                "ordinal": index - 1,
                "ZF": cle[0],
                "ECH": cle[1],
                "PER": cle[2],
                "NDEP": trajet["NDEP"],
                "mode_declare": variables[(*cle, trajet["NDEP"])]["mode"],
                "chaine_rompue": int(rompue),
                "sample_weight": variables[(*cle, trajet["NDEP"])]["sample_weight"],
                "purpose": motif,
                # Distance déclarée à vol d'oiseau (`D11`). Sert à ranger le déplacement dans
                # une bande de distance — l'axe sur lequel l'exactitude se publie — et vient
                # du terrain, donc indépendamment de ce qu'un décideur a choisi.
                "vol_oiseau_declare_km": trajet["vol_oiseau_declare_km"],
                "depart_hhmm": trajet["depart_hhmm"],
                "jour_declare": dates.get(cle, ""),
            })
            if depart >= 86400:
                compte["deplacement_apres_minuit"] += 1

        if origine_motif != "home":
            compte["journee_ne_commence_pas_au_domicile"] += 1
        if cle not in dates:
            compte["date_inconnue"] += 1

        lon_dom, lat_dom = centroides.get(zf_residence, centroides[trajets[0]["ZF_orig"]])
        nom = _nom(person_id, (premier.get("gender") or "").strip())
        personnes.append({
            "person_id": person_id,
            "immobile": False,
            "enquete": {
                "zf": cle[0],
                "ech": cle[1],
                "per": cle[2],
                "jour_declare": dates.get(cle, ""),
                "zf_residence": zf_residence,
            },
            "identity": {
                "name": nom,
                "traits_json": _traits(premier, couronne, motifs, nom),
                "home": {"lon": lon_dom, "lat": lat_dom, "public_transport": None},
                "activities": activites,
            },
            "state": {},
            "is_llm_based": True,
        })
        compte["journees_retenues"] += 1

    perdues = sum(compte[c] for c in ("journee_horaires_illisibles", "journee_zone_hors_couche"))
    taux_perte = perdues / max(len(retenues), 1)
    logger.info(
        f"Journées retenues : {compte['journees_retenues']:n} · écartées : {perdues:n} "
        f"({taux_perte:.2%}) · déplacements avec vérité terrain : {len(verite):n}"
    )
    for motif in ("journee_horaires_illisibles", "journee_zone_hors_couche", "date_inconnue"):
        if compte[motif]:
            logger.info(f"  {motif} : {compte[motif]:n}")
    if compte["journee_ne_commence_pas_au_domicile"]:
        logger.info(
            f"Journées qui ne commencent pas au domicile : "
            f"{compte['journee_ne_commence_pas_au_domicile']:n} — la voiture du ménage y est "
            "garée au domicile, donc hors de portée du premier déplacement (règle de chaîne)"
        )
    if compte["enchainement_rompu"]:
        logger.warning(
            f"{compte['enchainement_rompu']:n} enchaînement(s) rompu(s) par le retrait d'un "
            "intra-zone : l'origine routée n'est pas l'origine déclarée. Marqués "
            "`chaine_rompue = 1` dans le fichier de vérité, à exclure de l'audit"
        )
    if compte["deplacement_apres_minuit"]:
        logger.info(
            f"Déplacements déclarés à 24 h ou plus : {compte['deplacement_apres_minuit']:n} "
            "— horaires conservés tels quels, au-delà de la journée de 86 400 s"
        )
    if compte["couronne_inconnue"]:
        logger.warning(
            f"{compte['couronne_inconnue']:n} enquêté(s) sans couronne : `residence_zone` "
            "restera nul pour eux, le narratif omettra la ligne"
        )
    if taux_perte > SEUIL_PERTE_ALARME:
        logger.error(
            f"[ALARME] {taux_perte:.1%} des journées écartées (> {SEUIL_PERTE_ALARME:.0%}) : "
            "l'échantillon audité ne représente plus la partition de test"
        )

    dossier = RACINE / "data" / "population" / f"population_enquete_058_{split}{suffixe}"
    dossier.mkdir(parents=True, exist_ok=True)
    fichier_population = dossier / "population.json"
    fichier_population.write_text(
        json.dumps(personnes, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    dates_meteo = {
        p["person_id"]: p["enquete"]["jour_declare"]
        for p in personnes
        if p["enquete"]["jour_declare"]
    }
    fichier_dates = dossier / "dates_meteo.json"
    fichier_dates.write_text(
        json.dumps(dates_meteo, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    logger.info(
        f"Dates météo déclarées écrites : {len(dates_meteo):n} personne(s) sur "
        f"{len(personnes):n} — {fichier_dates.name}"
    )

    fichier_verite = ICI / f"verite_058_{split}{suffixe}.csv"
    with fichier_verite.open("w", encoding="utf-8", newline="") as flux:
        graveur = csv.DictWriter(flux, fieldnames=list(verite[0].keys()))
        graveur.writeheader()
        graveur.writerows(verite)

    logger.success(
        f"Écrits : {fichier_population.relative_to(RACINE)} "
        f"({len(personnes):n} enquêtés) et {fichier_verite.name} "
        f"({len(verite):n} modes déclarés), en {time.monotonic() - debut:.1f} s"
    )
    return fichier_population, fichier_verite


def main() -> None:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--split", default="test", choices=["test", "train"])
    parseur.add_argument(
        "--limite", type=int, help="n'écrire que les N premiers enquêtés (essai à blanc)"
    )
    parseur.add_argument(
        "--suffixe", default="", help="suffixe du dossier et du fichier de vérité (ex. _essai)"
    )
    args = parseur.parse_args()
    construire(args.split, args.limite, args.suffixe)


if __name__ == "__main__":
    main()
