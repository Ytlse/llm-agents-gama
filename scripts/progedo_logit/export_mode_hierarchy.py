"""export_mode_hierarchy.py — La hiérarchie des modes de l'enquête, sourcée puis vérifiée.

    llm-agents/.venv/bin/python -m scripts.progedo_logit.export_mode_hierarchy
    llm-agents/.venv/bin/python -m scripts.progedo_logit.export_mode_hierarchy --check

CE QUE ÇA SERT. Un déplacement qui mêle plusieurs modes reçoit **un** mode principal. Le
dépôt en portait quatre tables et trois réponses pour le même trajet (ticket 022, M1). Ce
script gèle **une** hiérarchie dans `llm_module/data/mode_hierarchy_emc2.json`, que
`llm_module.core.mode_hierarchy` sert à tout le reste du dépôt. Le code n'a alors plus
besoin des microdonnées d'accès restreint pour tourner.

## DEUX SOURCES, ET LEUR ORDRE

**(1) L'ordre est PUBLIÉ, et il est déjà gelé ailleurs.** Le rapport AUAT/CEREMA de
l'enquête mobilité 2023 du bassin de vie toulousain donne en annexe, page 53 (« Hiérarchie
des modes »), l'ordre complet des **36 modes enquêtés**, « défini au niveau national »
(p. 12). Cette table est transcrite dans
[`scripts/AAMAS/hierarchie_modes_emc2.yaml`](../AAMAS/hierarchie_modes_emc2.yaml) (version
`hm1`) — **ce script la LIT, il ne la recopie pas**. Une seconde transcription serait la
cinquième table de modes du dépôt, et le ticket 022 existe pour les supprimer.

Ce qui est *ici* et nulle part ailleurs, c'est le **raccord** entre les libellés du rapport
et le codebook ProGEDO (`CODES_PAR_ORDRE`) : sans lui, on ne peut pas contrôler la table
sur les microdonnées. C'est une information de nature différente de l'ordre — un
dictionnaire, pas une hiérarchie.

**(2) La mesure la CONTRÔLE.** Une liste recopiée d'un PDF est un littéral, et un littéral
ne tombe jamais quand la production change (c'est l'asymétrie qui a laissé passer les
défauts Téléo et rail, cf. `scripts/tests/test_parite_modes.py`). On vérifie donc l'ordre
**sur les microdonnées** : pour chaque paire de modes co-présents dans un même déplacement,
on regarde quel mode l'enquête a retenu comme `MODP`. Une paire est *informative* quand le
`MODP` observé est l'un des deux modes de la paire ; sinon un troisième mode a gagné et la
paire ne dit rien.

Le contrôle est celui de l'axe A7 du ticket 020, généralisé à toutes les paires. A7 avait
compté 770 déplacements mêlant voiture et transports collectifs, dont 760 codés « TC » et 10
« voiture ». Ce script **rejoue exactement ce chiffre** (`--check`), et documente sa
convention : A7 comptait la voiture au sens large de `MODE_GROUP` (deux-roues motorisés
inclus) et une liste TC **sans le téléphérique ni le transport d'employeur**. Avec la liste
complète, la même mesure donne 773 / 763 / 10.

## CE QUE LA MESURE A TRANCHÉ, ET QUI N'ÉTAIT PAS SUPPOSÉ

Le bus urbain passe **avant** le train. Sur les déplacements mêlant une jambe de bus (ou
d'autocar interurbain) et une jambe de train, l'enquête code **34 fois sur 35** le bus. La
seule exception observée est un `Flixbus + TER` — et le rapport la prévoit : les cars
longue distance sont au rang 12, *sous* les trains (rangs 8 à 11). La cascade actuelle de
`move_logger._plan_transport_mode`, qui teste `_BUS_MODES` avant `_RAIL_MODES`, est donc
**conforme** ; ce sont `mode_choice` (train avant TC) et `task_worker` (train en tête) qui
divergent.

Ce que la mesure infirme aussi : la voiture est testée **en premier** par
`move_logger._plan_transport_mode`, alors qu'elle est au rang 19, sous tout le collectif.

## LES CONTRÔLES QUI AUTORISENT À PUBLIER

- **Anti-vacuité.** Sans trajets détaillés, ou sans `MODP`, la mesure ne trouverait aucune
  exception et l'accord serait « parfait » : le script exige un effectif minimal de paires
  informatives et **échoue** plutôt que de publier un accord vide.
- **Marche résiduelle.** La marche à pied est au rang 36 (« Marche à pied UNIQUEMENT ») et
  n'apparaît jamais comme trajet : `T3` ne porte aucun code `01`. On vérifie donc que les
  déplacements *sans* trajet détaillé sont **tous** codés `MODP = 01`, et qu'aucun
  déplacement *avec* trajet ne l'est. C'est ce qui fait de la marche un rang mesuré et non
  un rang supposé.
- **Cohérence publié / mesuré.** Toute paire informative dont le gagnant contredit l'ordre
  publié est listée dans `exceptions`, avec son effectif. Une seule exception structurelle
  est attendue (le Flixbus), et elle est *conforme* à l'ordre publié.

⚠ Ce script ne publie **aucune part modale** : la hiérarchie est une règle de codage, pas
une grandeur de population. Les effectifs sont donc des comptages **non pondérés** — un
`COEP` ne rendrait pas une règle plus vraie, il en pondérerait les occasions d'observation.
Le contrôle A7, lui, est reproduit non pondéré comme dans le ticket 020.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA = ROOT / "data" / "PROGEDO 2023" / "lil-1750-Donnees_CSV" / "fichiers_standards"
OUT = ROOT / "llm_module" / "data" / "mode_hierarchy_emc2.json"

logger = logging.getLogger("progedo.mode_hierarchy")

VERSION = "mh1"
RAPPORT = ("AUAT/CEREMA, Rapport final « Enquête mobilité 2023 — bassin de vie "
           "toulousain » (68 p., mai 2024), annexe « Hiérarchie des modes », p. 53")
RAPPORT_URL = ("https://www.aua-toulouse.org/wp-content/uploads/2024/05/"
               "Rapport-final-68-pages-Enquete-mobilite-2023-Bassin-de-vie-toulousain.pdf")

# ── (1) LA SOURCE : la table publiée, LUE et non recopiée ─────────────────────────
HIERARCHIE_PUBLIEE = ROOT / "scripts" / "AAMAS" / "hierarchie_modes_emc2.yaml"
VERSION_PUBLIEE_ATTENDUE = "hm1"

# Ordre publié → codes `T3` (mode d'un trajet) et `MODP` (mode principal d'un déplacement)
# des microdonnées ProGEDO. C'est le RACCORD entre les libellés du rapport et le codebook
# de l'enquête, et il n'existe qu'ici : sans lui, la table publiée ne peut pas être
# contrôlée sur les microdonnées. Un ordre sans code est un libellé que le codage ne
# distingue pas (le TAD régional partage le code 37 avec le TAD Tisséo ; « autre TER »
# partage 52 avec le TER liO ; le vélo de location n'a pas de code propre).
CODES_PAR_ORDRE: dict[int, tuple[str, ...]] = {
    1: ("33",),            # Passager métro (Tisséo)
    2: ("32",),            # Passager tramway (Tisséo)
    3: ("34",),            # Passager Téléo (téléphérique Tisséo)
    4: ("31",),            # Passager bus, navette (Tisséo)
    5: ("37",),            # TAD (Tisséo) — le code 37 couvre « U ou IU »
    6: ("41", "43"),       # autocars interurbains liO et autres autocars (scolaires)
    7: (),                 # TAD régional — pas de code distinct de 37
    8: ("52",),            # train régional liO (TER)
    9: ("51",),            # TGV
    10: (),                # autre TER — pas de code distinct de 52
    11: ("53", "54"),      # autres trains (Intercités, TET), train non précisé
    12: ("42",),           # cars longue distance (Flixbus…)
    13: ("71",),           # transport d'employeur
    14: ("61",),           # taxi
    15: ("62",),           # VTC
    16: ("81",),           # conducteur de fourgon/camionnette
    17: ("82",),           # passager de fourgon/camionnette
    18: ("95",),           # autres modes (tracteur, quad…)
    19: ("21",),           # conducteur de VP
    20: ("22",),           # passager de VP
    21: ("13", "15", "19"),   # conducteur de 2/3 roues motorisés
    22: ("14", "16", "20"),   # passager de 2/3 roues motorisés
    23: ("18",),           # VAE en libre-service
    24: ("10",),           # VLS VélôToulouse
    25: (),                # vélo de location — pas de code propre
    26: (),                # passager de vélo de location — idem
    27: ("17",),           # VAE
    28: ("11",),           # conducteur de vélo
    29: ("12",),           # passager de vélo
    30: ("96",),           # engins de déplacement personnel motorisés
    31: ("93", "97"),      # roller, skate, trottinette
    32: ("94",),           # fauteuil roulant
    33: ("38", "39"),      # passager autre réseau urbain
    34: ("91",),           # transport fluvial ou maritime
    35: ("92",),           # avion
    36: ("01",),           # marche à pied UNIQUEMENT
}

# ── Le vocabulaire de la SIMULATION, rattaché aux ordres publiés ──────────────────
# `ordres` = les ordres publiés que cette famille couvre. Son RANG est le plus petit
# d'entre eux — et il est confronté à `correspondance_simulation` de la table publiée.
# `jambes` = les valeurs de `leg.mode` que produisent OTP (`trip_helper/otp.py`,
# Transmodel v3), OSMnx (`trip_helper/osmnx_direct.py`) et le car scolaire synthétique
# (`trip_helper/school_bus.py`), plus les alias historiques encore présents dans les
# caches et les libellés (`subway`, `bike`, `walk`, `__car__`).
# `libelle_journal` = colonne « Mode de transport Choisi » de `moves.csv`.
# `mode_canonique` = vocabulaire de `llm_module.core.mode_choice.CANONICAL_MODES`.
#
# Aucun mode spéculatif : `trip_helper/otp.py` **assert** que toute jambe rendue est dans
# `SUPPORTED_MODES`, donc un mode absent de cette liste ne peut pas arriver, et l'inscrire
# créerait une obligation de parité (`test_parite_modes`) pour un cas impossible.
FAMILLES: tuple[dict, ...] = (
    {"famille": "metro", "ordres": (1,), "jambes": ("metro", "subway"),
     "libelle_journal": "Transports_collectifs", "mode_canonique": "public_transport"},
    {"famille": "tram", "ordres": (2,), "jambes": ("tram", "tramway"),
     "libelle_journal": "Transports_collectifs", "mode_canonique": "public_transport"},
    {"famille": "cableway", "ordres": (3,), "jambes": ("cableway", "gondola", "funicular"),
     "libelle_journal": "Transports_collectifs", "mode_canonique": "public_transport"},
    # `school_bus` est l'option synthétique du ticket 030 : un autocar de ramassage, donc
    # l'ordre 6 (« autres autocars — scolaires »), dans la même famille que le bus. Les
    # cars liO, eux, sortent d'OTP en `bus` (route_type=3) : pas de jambe `coach` à
    # attendre, et Tisséo (4) et liO (6) ne se distinguent que par l'exploitant.
    {"famille": "bus", "ordres": (4, 5, 6, 7), "jambes": ("bus", "school_bus"),
     "libelle_journal": "Transports_collectifs", "mode_canonique": "public_transport"},
    {"famille": "rail", "ordres": (8, 9, 10, 11), "jambes": ("rail",),
     "libelle_journal": "Train", "mode_canonique": "train"},
    # Taxi (14), VTC (15) et fourgon (16-17) sont des ordres PLUS PETITS que le VP (19) et
    # relèvent tous du même mode de jambe `car` : la famille prend donc le rang 14. Le
    # projet ne modélise ni taxi ni VTC — aucune jambe ne les atteint — mais les inscrire
    # rend l'agrégation complète et la mesure des paires interprétable.
    {"famille": "car", "ordres": (14, 15, 16, 17, 19, 20), "jambes": ("car", "__car__"),
     "libelle_journal": "Voiture Privée", "mode_canonique": "car"},
    # Absent de `correspondance_simulation` : aucune jambe de deux-roues motorisé n'est
    # produite. La famille existe quand même, parce que `mode_choice.CANONICAL_MODES` et
    # la colonne `P(Deux-roues motorisé) %` la portent : sans rang, un libellé exotique la
    # ferait tomber dans le fourre-tout sans qu'on le sache.
    {"famille": "motorbike", "ordres": (21, 22), "jambes": (),
     "libelle_journal": "Deux-roues motorisé", "mode_canonique": "motorbike"},
    {"famille": "bicycle", "ordres": (23, 24, 25, 26, 27, 28, 29), "jambes": ("bicycle", "bike"),
     "libelle_journal": "Vélo", "mode_canonique": "cycling"},
    {"famille": "foot", "ordres": (36,), "jambes": ("foot", "walk"),
     "libelle_journal": "Marche", "mode_canonique": "walking"},
)

# Effectif minimal de paires informatives sous lequel on refuse de publier : sans lui, une
# lecture cassée (jointure vide, `MODP` illisible) rendrait « zéro exception », c'est-à-dire
# l'accord parfait par absence de mesure.
MIN_PAIRES_INFORMATIVES = 500
# Effectif informatif minimal pour qu'une paire tranche à elle seule. Trois observations
# concordantes distinguent une règle d'un hasard de codage (1 chance sur 4 sous H0 pour
# 3 tirages, 1 sur 32 pour 5) ; en dessous, la paire est déclarée non tranchée par la
# mesure — et c'est l'ordre publié qui la tranche, ce qui est dit rang par rang.
MIN_INFORMATIF_DECISIF = 3

# Contrôle A7 (ticket 020). Deux lectures, parce que celle du ticket est incomplète et
# qu'il faut pouvoir le dire : A7 rangeait les deux-roues motorisés dans « voiture »
# (convention `MODE_GROUP` de `build_mode_choice_dataset.py`) et sa liste TC ne portait ni
# le téléphérique (34) ni le transport d'employeur (71).
A7_TC_TICKET = ("31", "32", "33", "37", "38", "39", "41", "42", "43", "51", "52", "53", "54")
A7_TC_COMPLET = A7_TC_TICKET + ("34", "71")
A7_VOITURE_LARGE = ("21", "22", "61", "62", "81", "82", "13", "14", "15", "16", "19", "20")
A7_VOITURE_STRICT = ("21", "22", "61", "62", "81", "82")
A7_VELO = ("10", "11", "12", "17", "18")
A7_ATTENDU = {"n": 770, "collectif": 760, "voiture": 10}
A7_VELO_ATTENDU = {"n": 58, "collectif": 58, "voiture": 0}


# ─────────────────────────────────────────────────────────────────────────────────
# Lecture des microdonnées
# ─────────────────────────────────────────────────────────────────────────────────

def charger_table_publiee(chemin: Path = HIERARCHIE_PUBLIEE) -> dict:
    """La table publiée (rapport p. 53), lue dans sa transcription gelée.

    Elle n'est PAS recopiée ici : une seconde transcription serait une cinquième table de
    modes, et le ticket 022 existe pour les supprimer. On la valide en revanche — 36
    ordres, de 1 à 36, sans trou — parce qu'une table tronquée classerait sans erreur.
    """
    if not chemin.exists():
        raise SystemExit(
            f"Table publiée absente : {chemin}. C'est la transcription de l'annexe "
            "« Hiérarchie des modes » du rapport AUAT/CEREMA ; sans elle l'ordre serait "
            "supposé.")
    doc = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    version = str(doc.get("version") or "")
    if version != VERSION_PUBLIEE_ATTENDUE:
        raise SystemExit(f"[ALARME] {chemin.name} en version {version!r}, attendu "
                         f"{VERSION_PUBLIEE_ATTENDUE!r} : relire la table avant d'exporter.")
    ordres = sorted(int(m["ordre"]) for m in doc["modes"])
    if ordres != list(range(1, 37)):
        raise SystemExit(f"[ALARME] {chemin.name} ne porte pas les 36 ordres de 1 à 36 "
                         f"({len(ordres)} trouvés) : la hiérarchie serait tronquée.")
    return doc


def rang_par_code() -> dict[str, int]:
    """Code `T3`/`MODP` → ordre publié. Un code absent du raccord n'a pas de rang."""
    return {code: ordre for ordre, codes in CODES_PAR_ORDRE.items() for code in codes}


def famille_par_code() -> dict[str, str]:
    """Code `T3`/`MODP` → famille de la simulation (codes sans contrepartie exclus)."""
    par_ordre = {ordre: f["famille"] for f in FAMILLES for ordre in f["ordres"]}
    return {code: par_ordre[ordre]
            for ordre, codes in CODES_PAR_ORDRE.items() if ordre in par_ordre
            for code in codes}


def verifier_raccord(table_publiee: dict, depl: pd.DataFrame) -> dict:
    """Le raccord libellés ↔ codes est-il complet et cohérent ? Trois contrôles.

    Sans eux, un code oublié n'aurait pas de rang, ses paires seraient muettes, et l'accord
    « 53 sur 53 » se lirait comme une confirmation alors qu'il serait un silence.
    """
    codes_plats = [c for codes in CODES_PAR_ORDRE.values() for c in codes]
    doublons = sorted({c for c in codes_plats if codes_plats.count(c) > 1})
    manquants_dans_ordre = sorted(set(CODES_PAR_ORDRE) - set(range(1, 37)))
    observes = set(depl["MODP"]) | {c for jeu in depl["jambes"].dropna() for c in jeu}
    sans_rang = sorted(observes - set(codes_plats))
    # `correspondance_simulation` de la table publiée : le rang de chaque famille doit être
    # le même des deux côtés. C'est le contrôle qui empêche les deux fichiers de dériver.
    correspondance = table_publiee.get("correspondance_simulation") or {}
    ordres_par_famille = {f["famille"]: set(f["ordres"]) for f in FAMILLES}
    desaccords, conventions = {}, {}
    for mode, node in correspondance.items():
        ordre_publie = int(node["ordre"])
        couverts = ordres_par_famille.get(mode)
        if couverts is None:
            desaccords[mode] = "mode de `correspondance_simulation` absent des FAMILLES"
        elif ordre_publie not in couverts:
            desaccords[mode] = (f"la table publiée le met à l'ordre {ordre_publie}, que la "
                                f"famille {mode} ne couvre pas ({sorted(couverts)})")
        elif ordre_publie != min(couverts):
            # Pas un désaccord : le rang d'une famille est le plus PETIT de ses ordres, là
            # où la table publiée nomme l'ordre du cas TYPIQUE (VP conducteur 19, vélo
            # personnel 28). La famille couvre aussi des ordres plus petits — taxi 14,
            # VAE en libre-service 23 — qui partagent le même mode de jambe. L'écart est
            # déclaré pour qu'il ne se lise pas comme une erreur.
            conventions[mode] = (f"ordre typique publié {ordre_publie} ; rang de la "
                                 f"famille {min(couverts)} (le plus petit de "
                                 f"{sorted(couverts)}, même mode de jambe)")
    if doublons or manquants_dans_ordre or sans_rang:
        raise SystemExit(
            f"[ALARME] Raccord libellés ↔ codes ProGEDO incohérent — doublons={doublons}, "
            f"ordres hors 1-36={manquants_dans_ordre}, codes observés sans rang={sans_rang}. "
            "Un code sans rang rend ses paires muettes et l'accord se lirait comme une "
            "confirmation.")
    if desaccords:
        raise SystemExit(
            f"[ALARME] Ce script et {HIERARCHIE_PUBLIEE.name} ne disent pas la même chose "
            f"sur le rang de certains modes : {desaccords}. Les deux fichiers ont dérivé — "
            "c'est exactement ce que le ticket 022 supprime.")
    return {"codes_raccordes": len(codes_plats),
            "codes_observes_dans_les_microdonnees": len(observes),
            "modes_confrontes_a_correspondance_simulation": sorted(correspondance),
            "ecarts_de_convention": conventions}


def charger(data: Path = DATA) -> pd.DataFrame:
    """Un déplacement par ligne, doté du jeu de codes de ses trajets.

    Clé du déplacement : `(ZFD, ECH, PER, NDEP)` côté déplacements, `(ZFT, ECH, PER, NDEP)`
    côté trajets — `ECH` seul n'est pas unique d'une zone fine à l'autre, la même remarque
    qu'`export_bike_ownership` et `export_terminal_time`.
    """
    depl = pd.read_csv(data / "Toulouse_2023_std_depl.csv", dtype=str, low_memory=False)
    traj = pd.read_csv(data / "Toulouse_2023_std_traj.csv", dtype=str, low_memory=False)
    for frame in (depl, traj):
        for colonne in frame.columns:
            frame[colonne] = frame[colonne].astype(str).str.strip()
    depl["cle"] = depl.ZFD + "|" + depl.ECH + "|" + depl.PER + "|" + depl.NDEP
    traj["cle"] = traj.ZFT + "|" + traj.ECH + "|" + traj.PER + "|" + traj.NDEP
    if depl["cle"].duplicated().any():
        raise ValueError("Clé de déplacement non unique — la jointure des trajets serait fausse.")
    jambes = traj.groupby("cle")["T3"].apply(frozenset)
    depl = depl.set_index("cle")
    depl["jambes"] = jambes
    logger.info("Déplacements : %d, dont %d avec trajets détaillés ; trajets : %d",
                len(depl), int(depl["jambes"].notna().sum()), len(traj))
    return depl


# ─────────────────────────────────────────────────────────────────────────────────
# Les contrôles
# ─────────────────────────────────────────────────────────────────────────────────

def controle_marche_residuelle(depl: pd.DataFrame) -> dict:
    """La marche est-elle le rang 36 *mesuré*, ou seulement le rang 36 recopié ?

    Deux faits doivent tenir ensemble : aucun trajet n'est codé « marche à pied » (`T3`
    ne porte pas de `01` — l'accès à pied est une durée `T2`/`T6`, pas un trajet), et
    `MODP = 01` désigne exactement les déplacements sans trajet mécanisé.
    """
    sans = depl[depl["jambes"].isna()]
    avec = depl[depl["jambes"].notna()]
    trajets_marche = sum(1 for jeu in avec["jambes"] if "01" in jeu)
    return {
        "question": "La marche à pied est-elle le résidu, c'est-à-dire le dernier rang ?",
        "deplacements_sans_trajet": int(len(sans)),
        "sans_trajet_dont_modp_marche": int((sans["MODP"] == "01").sum()),
        "deplacements_avec_trajet": int(len(avec)),
        "avec_trajet_dont_modp_marche": int((avec["MODP"] == "01").sum()),
        "trajets_codes_marche": int(trajets_marche),
        "verdict": ("rang mesuré : MODP=01 ⇔ aucun trajet mécanisé"
                    if int((sans["MODP"] == "01").sum()) == len(sans)
                    and int((avec["MODP"] == "01").sum()) == 0
                    else "SUSPECT — la marche n'est pas le résidu, la lecture est fausse"),
    }


def controle_a7(depl: pd.DataFrame, avec: tuple[str, ...], collectif: tuple[str, ...],
                autre: tuple[str, ...]) -> dict:
    """Rejeu de l'axe A7 : déplacements mêlant `avec` et `collectif`, et leur `MODP`."""
    detail = depl[depl["jambes"].notna()]
    mixtes = detail[[bool(jeu & set(avec)) and bool(jeu & set(collectif))
                     for jeu in detail["jambes"]]]
    modp = Counter(mixtes["MODP"])
    n_collectif = sum(v for k, v in modp.items() if k in collectif)
    n_autre = sum(v for k, v in modp.items() if k in autre)
    # A7 ne comptait que deux issues : « transports collectifs » ou « voiture ». Sa colonne
    # TC est donc « tout ce qui n'est pas voiture », y compris un MODP hors de sa propre
    # liste TC (téléphérique, transport d'employeur). Les deux lectures sont publiées :
    # c'est l'écart entre elles qui explique les 760 du ticket contre 759 mesurés en
    # appartenance stricte.
    return {"n": int(len(mixtes)), "collectif": int(n_collectif), "autre": int(n_autre),
            "collectif_au_sens_non_autre": int(len(mixtes) - n_autre),
            "modp": dict(sorted(modp.items()))}


# ─────────────────────────────────────────────────────────────────────────────────
# La mesure : dominance par paire de codes
# ─────────────────────────────────────────────────────────────────────────────────

def dominance(depl: pd.DataFrame) -> list[dict]:
    """Pour chaque paire de codes co-présents : qui l'enquête retient comme `MODP`.

    Une observation est *informative* pour la paire `(a, b)` quand le déplacement porte les
    deux et que son `MODP` est `a` ou `b`. Sinon un troisième mode a gagné : l'observation
    renseigne les paires de ce troisième mode, pas celle-ci.
    """
    detail = depl[depl["jambes"].notna()]
    codes = sorted({code for jeu in detail["jambes"] for code in jeu})
    jeux = list(detail["jambes"])
    modes_principaux = list(detail["MODP"])
    resultats = []
    for a, b in itertools.combinations(codes, 2):
        contient = informatif = gagne_a = gagne_b = 0
        for jeu, modp in zip(jeux, modes_principaux):
            if a not in jeu or b not in jeu:
                continue
            contient += 1
            if modp == a:
                informatif += 1
                gagne_a += 1
            elif modp == b:
                informatif += 1
                gagne_b += 1
        if not contient:
            continue
        resultats.append({"a": a, "b": b, "contient": contient, "informatif": informatif,
                          "gagne_a": gagne_a, "gagne_b": gagne_b})
    return resultats


def confronter(paires: list[dict], rangs: dict[str, int]) -> dict:
    """La mesure confirme-t-elle l'ordre publié ? Liste les paires et les exceptions."""
    testees = conformes = 0
    exceptions, non_tranchees = [], []
    for paire in paires:
        a, b, ga, gb = paire["a"], paire["b"], paire["gagne_a"], paire["gagne_b"]
        if a not in rangs or b not in rangs:
            continue
        if paire["informatif"] < MIN_INFORMATIF_DECISIF:
            non_tranchees.append({**paire, "rang_a": rangs[a], "rang_b": rangs[b]})
            continue
        testees += 1
        # Rang le plus petit = gagne. Le publié attend donc `attendu` victoires côté a.
        attendu_a = rangs[a] < rangs[b]
        observe_a = ga > gb
        contre = gb if attendu_a else ga
        if attendu_a == observe_a:
            conformes += 1
        if contre:
            exceptions.append({**paire, "rang_a": rangs[a], "rang_b": rangs[b],
                               "contre_l_ordre_publie": int(contre)})
    return {
        "paires_testees": testees,
        "paires_conformes": conformes,
        "paires_non_tranchees_faute_d_effectif": len(non_tranchees),
        "seuil_informatif_decisif": MIN_INFORMATIF_DECISIF,
        "observations_informatives": sum(p["informatif"] for p in paires),
        "exceptions": sorted(exceptions, key=lambda e: -e["contre_l_ordre_publie"]),
        "non_tranchees": sorted(non_tranchees, key=lambda p: -p["contient"])[:40],
    }


def dominance_familles(depl: pd.DataFrame, familles: dict[str, str]) -> list[dict]:
    """La même mesure, agrégée aux familles de la simulation — la matrice à publier."""
    detail = depl[depl["jambes"].notna()]
    jeux = [frozenset(familles[c] for c in jeu if c in familles) for jeu in detail["jambes"]]
    principaux = [familles.get(m) for m in detail["MODP"]]
    noms = sorted({f for jeu in jeux for f in jeu})
    resultats = []
    for a, b in itertools.combinations(noms, 2):
        contient = gagne_a = gagne_b = 0
        for jeu, principal in zip(jeux, principaux):
            if a not in jeu or b not in jeu:
                continue
            contient += 1
            if principal == a:
                gagne_a += 1
            elif principal == b:
                gagne_b += 1
        if not contient:
            continue
        resultats.append({"a": a, "b": b, "contient": contient,
                          "informatif": gagne_a + gagne_b,
                          "gagne_a": gagne_a, "gagne_b": gagne_b})
    return sorted(resultats, key=lambda r: -r["informatif"])


# ─────────────────────────────────────────────────────────────────────────────────
# Assemblage
# ─────────────────────────────────────────────────────────────────────────────────

def empreintes(data: Path = DATA) -> dict[str, str]:
    fichiers = ("Toulouse_2023_std_depl.csv", "Toulouse_2023_std_traj.csv")
    table = {nom: hashlib.sha256((data / nom).read_bytes()).hexdigest() for nom in fichiers}
    table[HIERARCHIE_PUBLIEE.name] = hashlib.sha256(
        HIERARCHIE_PUBLIEE.read_bytes()).hexdigest()
    return table


def construire(depl: pd.DataFrame) -> dict:
    table_publiee = charger_table_publiee()
    raccord = verifier_raccord(table_publiee, depl)
    rangs = rang_par_code()
    familles = famille_par_code()

    paires = dominance(depl)
    accord = confronter(paires, rangs)
    if accord["observations_informatives"] < MIN_PAIRES_INFORMATIVES:
        raise SystemExit(
            f"[ALARME] {accord['observations_informatives']} observations informatives "
            f"seulement (seuil {MIN_PAIRES_INFORMATIVES}) : l'ordre publié serait déclaré "
            "conforme faute de mesure. Vérifiez la jointure trajets ↔ déplacements.")

    marche = controle_marche_residuelle(depl)
    if marche["verdict"].startswith("SUSPECT"):
        raise SystemExit(f"[ALARME] {marche['verdict']}")

    # Rang d'une famille = le plus PETIT ordre publié qu'elle couvre. Deux familles ne
    # peuvent pas partager un ordre : ce serait une ambiguïté silencieuse.
    ordre_publie_de_famille = {f["famille"]: min(f["ordres"]) for f in FAMILLES}
    if len(set(ordre_publie_de_famille.values())) != len(FAMILLES):
        raise SystemExit(f"[ALARME] Deux familles partagent un rang : "
                         f"{ordre_publie_de_famille}")
    ordre = sorted(ordre_publie_de_famille, key=ordre_publie_de_famille.get)

    jambes: dict[str, int] = {}
    for index, nom in enumerate(ordre, start=1):
        for jambe in next(f for f in FAMILLES if f["famille"] == nom)["jambes"]:
            jambes[jambe] = index

    a7_ticket = controle_a7(depl, A7_VOITURE_LARGE, A7_TC_TICKET, A7_VOITURE_LARGE)
    a7_complet = controle_a7(depl, A7_VOITURE_STRICT, A7_TC_COMPLET, A7_VOITURE_STRICT)
    a7_velo = controle_a7(depl, A7_VELO, A7_TC_COMPLET, A7_VELO)
    a7_velo_ticket = controle_a7(depl, A7_VELO, A7_TC_TICKET, A7_VELO)

    detail = depl[depl["jambes"].notna()]
    n_familles = [len({familles[c] for c in jeu if c in familles}) for jeu in detail["jambes"]]

    return {
        "version": VERSION,
        "titre": "Hiérarchie des modes — mode principal d'un déplacement, EMC² Toulouse 2023",
        "avertissement": (
            "GELÉ : produit par scripts/progedo_logit/export_mode_hierarchy.py. Ne pas "
            "éditer à la main. L'ordre vient du rapport publié (p. 53) ; les effectifs "
            "viennent des microdonnées ProGEDO lil-1750 (accès restreint)."),
        # Le contrat machine : famille → rang, jambe → rang, et les deux tables de libellés.
        "ordre_familles": ordre,
        "rang_famille": {nom: index for index, nom in enumerate(ordre, start=1)},
        "rang_jambe": dict(sorted(jambes.items(), key=lambda kv: (kv[1], kv[0]))),
        "libelle_journal": {f["famille"]: f["libelle_journal"] for f in FAMILLES},
        "mode_canonique": {f["famille"]: f["mode_canonique"] for f in FAMILLES},
        "jambes_par_famille": {f["famille"]: list(f["jambes"]) for f in FAMILLES},
        "codes_emc2_par_famille": {
            nom: sorted(c for c, f in familles.items() if f == nom) for nom in ordre},
        "source_publiee": {
            "rapport": RAPPORT, "url": RAPPORT_URL, "page": 53,
            "renvoi": "« un seul des modes est pris en compte […] : c'est le "
                      "« mode principal », qui découle d'une hiérarchisation des modes "
                      "définie au niveau national » (p. 12)",
            "transcription": {
                "fichier": str(HIERARCHIE_PUBLIEE.relative_to(ROOT)),
                "version": table_publiee["version"],
                "regle": table_publiee.get("regle"),
            },
            # Les 36 ordres, tels que la transcription les porte, dotés de leur raccord au
            # codebook ProGEDO et de la famille simulée qui les couvre.
            "ordre": [
                {"rang": int(m["ordre"]), "libelle": m["libelle"],
                 "categorie_publiee": m.get("categorie"),
                 "codes": list(CODES_PAR_ORDRE.get(int(m["ordre"]), ())),
                 "famille": next((f["famille"] for f in FAMILLES
                                  if int(m["ordre"]) in f["ordres"]), None)}
                for m in sorted(table_publiee["modes"], key=lambda m: int(m["ordre"]))],
            "rangs_sans_contrepartie_simulee": [
                {"rang": int(m["ordre"]), "libelle": m["libelle"],
                 "codes": list(CODES_PAR_ORDRE.get(int(m["ordre"]), ()))}
                for m in sorted(table_publiee["modes"], key=lambda m: int(m["ordre"]))
                if not any(int(m["ordre"]) in f["ordres"] for f in FAMILLES)],
            "raccord_codebook_progedo": raccord,
        },
        "mesure": {
            "unite": "déplacement de l'enquête, comptage NON pondéré (règle de codage, "
                     "pas grandeur de population)",
            "n_deplacements": int(len(depl)),
            "n_deplacements_detailles": int(len(detail)),
            "n_familles_par_deplacement": {str(k): int(v) for k, v in
                                           sorted(Counter(n_familles).items())},
            "accord_avec_l_ordre_publie": accord,
            "matrice_familles": dominance_familles(depl, familles),
            "paires_de_codes": sorted(paires, key=lambda p: -p["informatif"]),
        },
        "controles": {
            "marche_residuelle": marche,
            "a7_voiture_tc_convention_ticket_020": {
                **a7_ticket, "attendu": A7_ATTENDU,
                "convention": "voiture au sens MODE_GROUP (deux-roues motorisés inclus) ; "
                              "liste TC sans le téléphérique (34) ni le transport "
                              "d'employeur (71)",
                "verdict": ("rejeu exact"
                            if (a7_ticket["n"] == A7_ATTENDU["n"]
                                and a7_ticket["autre"] == A7_ATTENDU["voiture"]
                                and a7_ticket["collectif_au_sens_non_autre"]
                                == A7_ATTENDU["collectif"])
                            else "ÉCART — la convention d'A7 n'est pas reproduite")},
            "a7_voiture_tc_listes_completes": {
                **a7_complet,
                "convention": "voiture stricte (deux-roues motorisés à part) ; liste TC "
                              "complète, téléphérique et transport d'employeur inclus"},
            # ⚠ Les deux chiffres d'A7 n'ont PAS été calculés avec la même liste TC : les
            # 770 déplacements voiture + TC s'obtiennent sans le téléphérique ni le
            # transport d'employeur, les 58 vélo + TC les incluent. Les deux lectures sont
            # publiées, c'est la seule façon de recouper le ticket sans le recopier.
            "a7_velo_tc": {**a7_velo, "attendu": A7_VELO_ATTENDU,
                           "convention": "liste TC complète",
                           "verdict": ("rejeu exact"
                                       if a7_velo["n"] == A7_VELO_ATTENDU["n"]
                                       else "ÉCART — convention non reproduite")},
            "a7_velo_tc_convention_ticket_020": {
                **a7_velo_ticket,
                "convention": "liste TC sans téléphérique ni transport d'employeur — "
                              "celle qui rejoue les 770 de voiture + TC"},
        },
        "provenance": {
            "source": "ordre publié (rapport AUAT/CEREMA p. 53, transcrit dans scripts/AAMAS/hierarchie_modes_emc2.yaml) contrôlé sur les "
                      "microdonnées EMC² 2023 (ProGEDO lil-1750), fichiers déplacements "
                      "× trajets, comptage non pondéré",
            "fichiers": empreintes(),
            "gele_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "par": "scripts/progedo_logit/export_mode_hierarchy.py",
        },
    }


def resumer(doc: dict) -> None:
    accord = doc["mesure"]["accord_avec_l_ordre_publie"]
    print(f"\nHiérarchie {doc['version']} — {len(doc['ordre_familles'])} familles simulées :")
    for index, nom in enumerate(doc["ordre_familles"], start=1):
        codes = doc["codes_emc2_par_famille"][nom]
        print(f"  {index}. {nom:10s} → « {doc['libelle_journal'][nom]:22s} » "
              f"codes EMC² {codes or '—'}")
    print(f"\nAccord mesure ↔ ordre publié : {accord['paires_conformes']}/"
          f"{accord['paires_testees']} paires de codes conformes, "
          f"{accord['observations_informatives']} observations informatives, "
          f"{len(accord['exceptions'])} exception(s), "
          f"{accord['paires_non_tranchees_faute_d_effectif']} paire(s) non tranchée(s) "
          f"(< {accord['seuil_informatif_decisif']} obs.)")
    for exception in accord["exceptions"][:8]:
        print(f"    exception {exception['a']}+{exception['b']} "
              f"(rangs {exception['rang_a']}/{exception['rang_b']}) : "
              f"{exception['contre_l_ordre_publie']} déplacement(s) contre l'ordre publié")
    print("\nMatrice des déplacements mixtes, par famille simulée "
          "(effectif informatif ≥ 1) :")
    print(f"    {'paire':26s} {'contient':>8s} {'inform.':>8s} {'gagnant':>10s}")
    for ligne in doc["mesure"]["matrice_familles"]:
        gagnant = (ligne["a"] if ligne["gagne_a"] > ligne["gagne_b"]
                   else ligne["b"] if ligne["gagne_b"] > ligne["gagne_a"] else "—")
        print(f"    {ligne['a'] + ' / ' + ligne['b']:26s} {ligne['contient']:8d} "
              f"{ligne['informatif']:8d} {gagnant:>10s} "
              f"({ligne['gagne_a']}–{ligne['gagne_b']})")
    a7 = doc["controles"]["a7_voiture_tc_convention_ticket_020"]
    print(f"\nContrôle A7 (convention du ticket 020) : n={a7['n']} "
          f"collectif={a7['collectif_au_sens_non_autre']} voiture={a7['autre']} "
          f"— attendu {a7['attendu']} → {a7['verdict']}")
    complet = doc["controles"]["a7_voiture_tc_listes_completes"]
    print(f"Contrôle A7 (listes complètes)          : n={complet['n']} "
          f"collectif={complet['collectif']} voiture={complet['autre']}")
    velo = doc["controles"]["a7_velo_tc"]
    print(f"Contrôle A7 vélo + TC (liste complète)  : n={velo['n']} "
          f"collectif={velo['collectif_au_sens_non_autre']} vélo={velo['autre']} "
          f"— attendu {velo['attendu']} → {velo['verdict']}")
    print(f"Marche résiduelle : {doc['controles']['marche_residuelle']['verdict']}")


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--check", action="store_true",
                        help="mesure et compare à la ressource gelée, sans l'écrire")
    args = parser.parse_args(argv)

    if not DATA.exists():
        raise SystemExit(
            f"Microdonnées absentes : {DATA}. Elles sont d'accès restreint (ProGEDO/ADISP "
            "lil-1750). La ressource gelée suffit pour faire tourner le dépôt ; ce script "
            "ne sert qu'à la reproduire.")

    doc = construire(charger())
    resumer(doc)

    if args.check:
        if not args.out.exists():
            raise SystemExit(f"[ALARME] Ressource gelée absente : {args.out}")
        gele = json.loads(args.out.read_text(encoding="utf-8"))
        ecarts = [cle for cle in ("ordre_familles", "rang_famille", "rang_jambe",
                                  "libelle_journal", "mode_canonique")
                  if gele.get(cle) != doc[cle]]
        # La SUBSTANCE de la table publiée, pas son empreinte : un commentaire retouché
        # dans le YAML ne doit pas exiger une ré-exportation (qui demanderait les
        # microdonnées d'accès restreint), mais un ordre déplacé doit la forcer.
        for cle in ("transcription", "ordre"):
            if (gele.get("source_publiee") or {}).get(cle) != doc["source_publiee"][cle]:
                ecarts.append(f"source_publiee.{cle}")
        if ecarts:
            raise SystemExit(f"[ALARME] La ressource gelée diverge de la mesure sur "
                             f"{ecarts} — ré-exportez-la.")
        print(f"\n--check : la ressource gelée {args.out.name} est conforme à la mesure.")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"\nÉcrit {args.out} ({args.out.stat().st_size / 1024:.0f} ko)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
