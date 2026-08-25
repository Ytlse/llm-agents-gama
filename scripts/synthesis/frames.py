"""Adaptateurs de données : chaque volet produit la même « trame de décision ».

Le principe de toute la page tient en une phrase : les trois volets sont rendus
comparables en les ramenant au **même tableau** — une ligne par (décision, mode
envisagé), portant une masse de probabilité — puis en leur appliquant la **même
loss** que le moteur de calibration (``calibration.metrics``).

Colonnes de la trame : ``agent_id``, ``mode_cat``, ``weight``, ``genre``,
``age_cat``, ``occupation``, ``motif``, ``dist_cat`` (+ ``lieu_residence``,
hors composite).
"""
from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone

from llm_module.core.population_reference import OUT_OF_PERIMETER
from pathlib import Path
from typing import Any, Optional

import yaml

from llm_module.core.housing_type import (
    MODALITY_KEYS as HOUSING_MODALITY_KEYS,
    REFERENCE_KEYS as HOUSING_REFERENCE_KEYS,
    key_for as housing_key_for,
)

from .sources import REPO_ROOT, Manifest, probe

# ── Conventions de correspondance (moves.csv → catégories EMC²) ──────────────

# Colonne de probabilité → catégorie EMC². Le train est rangé avec les transports
# collectifs (c'est un mode collectif) ; les deux-roues motorisés et « autres »
# sortent du périmètre scoré, comme dans la référence EMC² où ils forment le
# résidu « autres ». La masse ainsi écartée est mesurée et affichée.
PROBA_COLUMNS = {
    "P(Marche) %": "marche",
    "P(Vélo) %": "velo",
    "P(Voiture Privée) %": "voiture",
    "P(Transports_collectifs) %": "transports_collectifs",
    "P(Train) %": "transports_collectifs",
    "P(Deux-roues motorisé) %": "autres",
    "P(Autres modes) %": "autres",
}

CHOSEN_MODE_MAP = {
    "Marche": "marche",
    "Vélo": "velo",
    "Voiture Privée": "voiture",
    "Transports_collectifs": "transports_collectifs",
    "Train": "transports_collectifs",
    "Deux-roues motorisé": "autres",
    "Autres modes": "autres",
}


def parse_offered_modes(value: str) -> list[str]:
    """« Modes proposés au LLM » → catégories EMC², dédoublonnées, dans l'ordre.

    La colonne liste **un libellé par itinéraire OTP**, séparés par ` | ` : plusieurs
    options partagent souvent un mode (six itinéraires dont quatre en transports
    collectifs). C'est l'ensemble des modes qui compte ici, pas leur multiplicité.

    Un libellé hors table (mode inattendu) est ignoré plutôt que rangé dans
    « autres » : « autres » est une catégorie de la référence EMC², pas un fourre-tout
    pour les valeurs qu'on ne sait pas lire.
    """
    out: list[str] = []
    for label in (value or "").split("|"):
        cat = CHOSEN_MODE_MAP.get(label.strip())
        if cat is not None and cat not in out:
            out.append(cat)
    return out


def departure_hour(value: str) -> Optional[int]:
    """Heure de départ (0-23) depuis « Heure de départ » du journal.

    Le journal écrit un horodatage `YYYY-MM-DD HH:MM:SS` rendu depuis l'horloge
    **simulée** : l'heure lue est bien l'heure locale du déplacement, celle que
    l'enquête déclare en D4.
    """
    text = (value or "").strip()
    if not text:
        return None
    try:
        return int(text.split(" ")[1].split(":")[0])
    except (IndexError, ValueError):
        return None

# `Motifs de déplacement` mélange libellés traduits et bruts selon la source ;
# home / leisure / other n'ont pas d'équivalent EMC² et sortent de la dimension.
MOTIF_MAP = {
    "Travail": "travail", "work": "travail",
    "Etude": "etudes", "Étude": "etudes", "education": "etudes",
    "Achats": "achats", "shop": "achats",
    "Accompagnement": "accompagnement", "escort": "accompagnement",
}

# Dimensions affichées. `scored` : entre dans le composite comparable.
DIMENSIONS = [
    {"key": "age", "column": "age_cat", "cerema": "Age", "label": "Âge",
     "kind": "ordinal", "scored": True},
    {"key": "distance", "column": "dist_cat", "cerema": "distance", "label": "Distance",
     "kind": "ordinal", "scored": True},
    {"key": "genre", "column": "genre", "cerema": "genre", "label": "Genre",
     "kind": "nominal", "scored": True},
    {"key": "occupation", "column": "occupation", "cerema": "occupation",
     "label": "Occupation", "kind": "nominal", "scored": True},
    {"key": "motif", "column": "motif", "cerema": "motif_deplacement",
     "label": "Motif de déplacement", "kind": "nominal", "scored": True},
    {"key": "lieu_residence", "column": "lieu_residence", "cerema": "lieu_residence",
     "label": "Lieu de résidence", "kind": "nominal", "scored": False},
    {"key": "type_logement", "column": "type_logement", "cerema": "type_logement",
     "label": "Type de logement", "kind": "nominal", "scored": False},
]

MODES = ["marche", "voiture", "velo", "transports_collectifs"]
MODE_LABELS = {"marche": "Marche", "voiture": "Voiture", "velo": "Vélo",
               "transports_collectifs": "Transports collectifs"}
MODE_COLORS = {"marche": "#00CCCC", "voiture": "#EE4444",
               "velo": "#8844BB", "transports_collectifs": "#22AA44"}

_AGE_BUCKETS = [(9, "5-9"), (14, "10-14"), (19, "15-19"), (24, "20-24"),
                (29, "25-29"), (34, "30-34"), (39, "35-39"), (44, "40-44"),
                (49, "45-49"), (54, "50-54"), (59, "55-59"), (64, "60-64"),
                (69, "65-69"), (74, "70-74")]
_DIST_BUCKETS = [(1, "0-1km"), (2, "1-2km"), (5, "2-5km"),
                 (10, "5-10km"), (20, "10-20km"), (50, "20-50km")]

OCCUPATION_MAP = {
    "Scolaire (jusqu'au Bac)": "scolaire",
    "Étudiant": "etudiant",
    "Travail à plein temps": "actif_temps_plein",
    "Travail à temps partiel": "actif_temps_partiel",
    "Chômeur/recherche d'emploi": "chomeur_recherche_emploi",
    "Personne au foyer": "personne_au_foyer",
    "Retraité": "Retraité",
}


# Clé de la modalité hors périmètre. ASCII et sans accent, comme les clés de
# `cerema_values.yaml` (`1ere_couronne`) : la sortie brute de `normalize_place`
# donnerait `hors_périmètre`, qui ne joindrait rien et disparaîtrait sans un mot.
OUT_OF_PERIMETER_KEY = "hors_perimetre"

# Nom de la ligne qui porte la masse hors référentiel d'une dimension. Elle n'a ni
# cible ni L1 : elle existe pour que « exclu des cibles » ne se confonde jamais avec
# « inexistant ». `global_view` fait la même chose de sa masse hors modes scorés.
OFF_REFERENCE_ROW = "— hors référentiel —"

# Les clés de cerema_values.yaml sont des identifiants, pas des libellés : on les
# rend lisibles à l'affichage sans jamais toucher aux clés elles-mêmes.
CAT_LABELS = {
    "scolaire": "Scolaire", "etudiant": "Étudiant",
    "actif_temps_plein": "Actif à temps plein",
    "actif_temps_partiel": "Actif à temps partiel",
    "chomeur_recherche_emploi": "Chômeur / recherche d'emploi",
    "personne_au_foyer": "Personne au foyer", "Retraité": "Retraité",
    "travail": "Travail", "etudes": "Études", "achats": "Achats",
    "accompagnement": "Accompagnement",
    "Toulouse": "Toulouse", "1ere_couronne": "1re couronne",
    "2eme_couronne": "2e couronne", "3eme_couronne": "3e couronne",
    "individuel_isole": "Individuel isolé", "individuel_accole": "Individuel accolé",
    "petit_habitat_collectif": "Petit habitat collectif",
    "grand_habitat_collectif": "Grand habitat collectif",
    "plus_50km": "plus de 50 km", "75-130": "75 ans et plus",
    # Recopie de la modalité canonique (`population_reference.OUT_OF_PERIMETER`), pas une
    # reformulation : c'est la même chaîne que le journal écrit et que la trace archive.
    OUT_OF_PERIMETER_KEY: OUT_OF_PERIMETER,
}


def pretty_cat(cat: str) -> str:
    return CAT_LABELS.get(cat, str(cat))


def age_to_cat(age: float) -> Optional[str]:
    try:
        a = int(float(age))
    except (TypeError, ValueError):
        return None
    for bp, label in _AGE_BUCKETS:
        if a <= bp:
            return label
    return "75-130"


def distance_to_cat(km: float) -> Optional[str]:
    try:
        d = float(km)
    except (TypeError, ValueError):
        return None
    for bp, label in _DIST_BUCKETS:
        if d < bp:
            return label
    return "plus_50km"



def normalize_place(value: str) -> tuple[Optional[str], bool]:
    """« Lieu de résidence » du journal → clé EMC², et le fait qu'elle soit référencée.

    Depuis le ticket 021 la colonne porte quatre couronnes **et** `hors périmètre` : un
    domicile connu, situé hors des 453 communes de l'enquête. Ce n'est pas une couronne
    — le ranger en 3ᵉ a fait publier un stratum dont 76 % des habitants n'étaient pas
    dans l'enquête —, il n'a donc **aucune cible** par zone, et le second membre du
    couple dit qu'il ne joindra aucune ligne de référence. C'est ce qui permet de le
    COMPTER plutôt que de le voir disparaître, exactement comme `normalize_housing` le
    fait de la modalité « Autres ».
    """
    text = (value or "").strip()
    if not text:
        return None, False
    if text == OUT_OF_PERIMETER:
        return OUT_OF_PERIMETER_KEY, False
    return text.replace(" ", "_"), True


def normalize_housing(value: str) -> tuple[Optional[str], bool]:
    """« Type de logement » du journal → clé EMC², et le fait qu'elle soit référencée.

    Le journal écrit le **libellé** de l'enquête (« Petit habitat collectif ») ; la
    référence l'indexe par clé (`petit_habitat_collectif`). La correspondance vient de
    `llm_module.core.housing_type`, unique déclaration des modalités, partagée avec la
    génération de population et le journal — trois recopies indépendantes finiraient
    par diverger sans que rien ne le signale.

    Renvoie `(clé, référencée)`. `autres` existe dans l'enquête mais pas dans la
    ventilation EMC² publiée : la clé est rendue quand même, et le second membre dit
    qu'elle ne joindra aucune ligne de référence — c'est ce qui permet de la compter
    plutôt que de la voir disparaître silencieusement.
    """
    text = (value or "").strip()
    if not text:
        return None, False
    key = housing_key_for(text)
    if key is None:
        # Déjà une clé (relecture d'un journal écrit autrement), sinon inconnue.
        key = text if text in HOUSING_MODALITY_KEYS else None
    if key is None:
        return None, False
    return key, key in HOUSING_REFERENCE_KEYS


# ── Référence EMC² ───────────────────────────────────────────────────────────

def load_cerema(path: Path) -> dict:
    with Path(path).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def reference_shares(cerema: dict, dim_key: str, cat: Optional[str] = None) -> dict:
    """Parts modales cibles, renormalisées sur les 4 modes scorés (en %)."""
    parts = cerema.get("parts_modales_2023", {})
    node = parts.get("global", {}) if dim_key == "global" else \
        (parts.get(dim_key) or {}).get(cat, {})
    kept = {m: float(node.get(m, 0.0)) for m in MODES}
    total = sum(kept.values())
    if total <= 0:
        return {}
    return {m: v * 100.0 / total for m, v in kept.items()}


# ── Volet 1 : simulation ─────────────────────────────────────────────────────

def resolve_run(manifest: Manifest) -> dict:
    """Localise le run servant de jeu commun et ses fichiers."""
    run_cfg = manifest.get("common_set.run", "experiments/current")
    run_dir = Path(run_cfg)
    if not run_dir.is_absolute():
        run_dir = REPO_ROOT / run_dir
    info: dict[str, Any] = {"configured": str(run_cfg), "exists": run_dir.exists()}
    if not run_dir.exists():
        return info
    resolved = run_dir.resolve()
    try:
        info["run_id"] = resolved.name
        info["path"] = str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        info["run_id"] = resolved.name
        info["path"] = str(resolved)

    moves = resolved / manifest.get("common_set.moves", "moves.csv")
    info["moves"] = manifest.track(
        "common_set.moves", moves, "Décisions modales du run (volet simulation)").to_dict()

    pop_cfg = manifest.get("common_set.population")
    if pop_cfg:
        pop = Path(pop_cfg) if Path(pop_cfg).is_absolute() else REPO_ROOT / pop_cfg
    else:
        candidates = sorted(p for p in resolved.glob("population_*.json")
                            if "checkpoint" not in p.name)
        pop = candidates[0] if candidates else resolved / "population_unknown.json"
    info["population"] = manifest.track(
        "common_set.population", pop,
        "Personas du run (traits, géolocalisation) — socle du volet modèle").to_dict()
    return info


def simulated_day(value: str) -> Optional[str]:
    """Jour simulé (``YYYY-MM-DD``) d'une ligne, depuis « Temps simulé ».

    Même convention que le champ ``sim_day`` de ``llm_exchanges.jsonl`` (UTC, cf.
    ``llm_module/telemetry/logger.py``) : c'est ce qui permet aux volets 1/3 et au
    volet 2 de découper le run sur la même frontière de journée.
    """
    text = (value or "").strip()
    if not text:
        return None
    try:
        ts = int(float(text))
    except ValueError:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def first_simulated_day(path: Path) -> Optional[str]:
    """Plus petit jour simulé présent dans un moves.csv.

    Déterminé par lecture, jamais codé en dur : le run de référence peut démarrer
    n'importe quel jour, et une date en dur ferait silencieusement passer un run
    entier pour vide.
    """
    days = set()
    with Path(path).open(encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            day = simulated_day(raw.get("Temps simulé") or "")
            if day:
                days.add(day)
    return min(days) if days else None


def attempt_stamp(raw: dict) -> str:
    """« Heure de calcul » d'une ligne : c'est elle qui identifie la tentative.

    Deux lignes du même couple (personne, activité, jour simulé) qui ne diffèrent
    que par cet horodatage sont deux tentatives de la MÊME décision, pas deux
    décisions.
    """
    return (raw.get("Heure de calcul") or "").strip()


def latest_attempts(raws: list[dict]) -> tuple[list[dict], dict]:
    """Ne garde que la tentative la plus récente de chaque décision.

    Un run repris à chaud (``make run OFFLINE=1 CONT=1``) rejoue le jour simulé
    depuis t0 dans le MÊME dossier d'expérience : ``moves.csv`` porte alors deux
    fois les mêmes couples (personne, activité), une ligne par tentative, toutes
    deux datées du même jour simulé. La coupe au premier jour simulé ne les sépare
    pas — elle les garde toutes les deux — et le score les compte deux fois. Sur
    le run repris du 2026-08-19, 1 469 lignes en doublon faisaient passer le
    composite de 24,09 à 24,43, soit l'ordre de grandeur des gains que la
    calibration cherche à mesurer.

    La clé porte le **jour simulé** en plus du couple (personne, activité), et ce
    n'est pas un détail : sans lui, la décision du jour 1 et sa répétition du jour
    2 — que l'horizon glissant de planification produit pour 442 couples sur ce
    run — passeraient pour deux tentatives de la même décision. On garderait alors
    celle du jour 2, que la coupe au premier jour simulé écarte ensuite : la
    décision disparaîtrait du score au lieu d'y entrer une fois.
    ``model_compare.latest_attempts`` applique la même règle, sur le même piège.

    Une ligne sans identifiant de personne ou d'activité ne peut être appariée à
    aucune autre : elle est gardée telle quelle, faute de quoi un journal qui ne
    porte pas ces colonnes s'effondrerait sur une seule ligne.
    """
    best: dict[tuple[str, str, Optional[str]], dict] = {}
    unpaired: set[int] = set()
    for raw in raws:
        person = (raw.get("ID Personne") or "").strip()
        activity = (raw.get("ID Activité") or "").strip()
        if not person or not activity:
            unpaired.add(id(raw))
            continue
        key = (person, activity, simulated_day(raw.get("Temps simulé") or ""))
        held = best.get(key)
        # Journal sans « Heure de calcul » (runs antérieurs) : tous les horodatages
        # sont vides, la comparaison est fausse partout et c'est la première ligne
        # qui reste. Faute de tentative datée, il n'y a pas de choix moins arbitraire.
        if held is None or attempt_stamp(raw) > attempt_stamp(held):
            best[key] = raw
    kept_ids = {id(raw) for raw in best.values()} | unpaired
    kept = [raw for raw in raws if id(raw) in kept_ids]
    stamps = sorted({attempt_stamp(raw)[:10] for raw in raws if attempt_stamp(raw)})
    return kept, {
        "n_dropped": len(raws) - len(kept),
        # Deux jours de calcul pour un seul jour simulé : le run a été repris.
        "reprise": len(stamps) > 1,
        "jours_de_calcul": stamps,
    }


def read_moves(path: Path, exclude_methods: list[str],
               first_day_only: bool = True) -> tuple[list[dict], dict]:
    """Lit moves.csv et annote chaque trajet de ses catégories EMC².

    ``first_day_only`` borne la lecture au **premier jour simulé** du run. Même
    quand le run est censé s'arrêter à 24 h, le bootstrap et l'horizon glissant de
    planification débordent au-delà : sur le run de référence, 2 538 couples
    (personne, activité) réapparaissaient un jour plus tard, avec le même mode dans
    57,8 % des cas. Ces répétitions ne sont pas des décisions supplémentaires, elles
    pèsent seulement deux fois dans les parts modales. Le volet 2 applique la même
    coupe sur ``sim_day`` (``common_set_eval.build_sample``) : c'est ce qui garantit
    aux trois volets un périmètre unique.

    Cette coupe ne suffit pas sur un run **repris à chaud** : la reprise rejoue
    le jour simulé dans le même dossier d'expérience, et les deux tentatives
    portent le même jour simulé. ``latest_attempts`` ne garde que la plus
    récente, en amont de la coupe ; le nombre de lignes ainsi écartées sort dans
    ``exclues_reprise``.
    """
    kept_day = first_simulated_day(path) if first_day_only else None
    rows: list[dict] = []
    stats = Counter()
    if kept_day:
        stats["jour_retenu"] = kept_day
    with Path(path).open(encoding="utf-8") as fh:
        raws = list(csv.DictReader(fh))
    stats["total"] = len(raws)
    raws, reprise = latest_attempts(raws)
    stats["exclues_reprise"] = reprise["n_dropped"]
    if reprise["reprise"]:
        stats["reprise"] = True
        stats["jours_de_calcul"] = reprise["jours_de_calcul"]
    for raw in raws:
        if kept_day and simulated_day(raw.get("Temps simulé") or "") != kept_day:
            stats["exclues_jour"] += 1
            continue
        if raw.get("Méthode de sélection") in exclude_methods:
            stats["exclues_methode"] += 1
            continue
        chosen = CHOSEN_MODE_MAP.get((raw.get("Mode de transport Choisi") or "").strip())
        if chosen is None:
            stats["sans_mode"] += 1
            continue
        occupation = OCCUPATION_MAP.get((raw.get("Occupation principale") or "").strip())
        if occupation is None:
            stats["occupation_inconnue"] += 1
        motif = MOTIF_MAP.get((raw.get("Motifs de déplacement") or "").strip())
        probas = {}
        for col, mode in PROBA_COLUMNS.items():
            value = (raw.get(col) or "").strip()
            if value == "":
                continue
            try:
                probas[mode] = probas.get(mode, 0.0) + float(value)
            except ValueError:
                continue
        if probas:
            stats["avec_distribution"] += 1
        else:
            stats["sans_distribution"] += 1
        logement, logement_reference = normalize_housing(
            raw.get("Type de logement") or "")
        if logement is None:
            stats["type_logement_vide"] += 1
        elif not logement_reference:
            # Modalité connue de l'enquête mais absente de la ventilation publiée
            # (« Autres ») : elle ne joindra aucune ligne de référence. On la
            # compte ici, faute de quoi elle disparaîtrait du bilan.
            stats["type_logement_hors_referentiel"] += 1
        lieu_residence, lieu_reference = normalize_place(
            raw.get("Lieu de résidence") or "")
        if lieu_residence is None:
            stats["lieu_residence_vide"] += 1
        elif not lieu_reference:
            # `hors périmètre` (ticket 021) : domicile connu, hors des 453 communes de
            # l'enquête. Aucune cible par zone, donc exclu des strates — mais compté
            # ici, faute de quoi il se diluerait sans laisser de trace.
            stats["lieu_residence_hors_perimetre"] += 1
        offered = parse_offered_modes(raw.get("Modes proposés au LLM") or "")
        if not offered:
            stats["sans_offre"] += 1
        # Contrainte de chaîne des véhicules (colonne écrite depuis le ticket 008,
        # A4 ; vide sur les runs antérieurs). Elle EXPLIQUE une décision, elle ne
        # la disqualifie pas : ces lignes restent dans le scoring, et la page en
        # publie seulement la répartition.
        contrainte = (raw.get("Contrainte de chaîne") or "").strip()
        stats["contrainte::" + (contrainte or "aucune")] += 1
        rows.append({
            "contrainte": contrainte or None,
            "agent_id": (raw.get("ID Personne") or "").strip(),
            "activity_id": (raw.get("ID Activité") or "").strip(),
            "chosen": chosen,
            "probas": probas,
            # Jeu de choix réellement soumis à la décision : c'est lui qui borne
            # le volet 3 (renormalisation sur l'offre OTP), et lui seul distingue
            # « mode écarté » de « mode jamais proposé ».
            "offered": offered,
            "departure_hour": departure_hour(raw.get("Heure de départ") or ""),
            "genre": (raw.get("Genre") or "").strip() or None,
            "age_cat": age_to_cat(raw.get("Âge")),
            "occupation": occupation,
            "motif": motif,
            "dist_cat": distance_to_cat(raw.get("Distance parcourue")),
            "lieu_residence": lieu_residence,
            "type_logement": logement,
        })
    return rows, dict(stats)


def simulation_frames(rows: list[dict]) -> dict[str, list[dict]]:
    """Deux lectures du même run : masse de probabilité, et mode effectivement tiré.

    ``attendu`` est la grandeur que la calibration optimise (elle ne dépend
    d'aucun tirage) ; ``tire`` est ce que la simulation a réellement joué. L'écart
    entre les deux mesure le bruit d'échantillonnage introduit par le tirage.
    """
    attrs = ("genre", "age_cat", "occupation", "motif", "dist_cat",
             "lieu_residence", "type_logement")
    expected: list[dict] = []
    drawn: list[dict] = []
    for row in rows:
        meta = {k: row[k] for k in attrs}
        meta["agent_id"] = row["agent_id"]
        total = sum(row["probas"].values())
        if total > 0:
            for mode, mass in row["probas"].items():
                if mass <= 0:
                    continue
                expected.append({**meta, "mode_cat": mode, "weight": mass / total})
        else:
            expected.append({**meta, "mode_cat": row["chosen"], "weight": 1.0})
        drawn.append({**meta, "mode_cat": row["chosen"], "weight": 1.0})
    return {"attendu": expected, "tire": drawn}


# ── Volet 2 : calibration de prompt ──────────────────────────────────────────

def load_dataset_metadata(dataset_dir: Path) -> dict[str, dict]:
    """``agent_id → attributs``, reconstruit depuis les jeux gelés."""
    cols = ("age_cat", "occupation", "genre", "motif", "dist_cat")
    meta: dict[str, dict] = {}
    for split in ("train", "val", "test", "screen"):
        path = Path(dataset_dir) / f"{split}.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            meta[str(rec["agent_id"])] = {c: rec.get(c) for c in cols}
    return meta


def eval_regime(params_key: str, eval_model: str) -> dict:
    """Régime de mesure d'une éval : ce qui doit être identique pour comparer.

    Le modèle ne suffit pas à identifier un régime. La bascule vers les comptages
    pondérés a changé la **politique de décision** : le modèle renvoyait un mode
    élu par persona, il renvoie désormais la distribution complète, comptée en
    masse de probabilité. Deux évals du même modèle sous ces deux politiques ne
    mesurent pas la même chose — les décisions brutes elles-mêmes diffèrent, donc
    aucun recalcul de loss ne les rend comparables.

    C'est ``eval_params_key`` du moteur qui porte l'information (``policy=weighted``
    depuis la bascule, ``samples=N`` avant) ; on en dérive un libellé lisible.
    """
    key = params_key or ""
    if key == "legacy_import":
        policy = "import hérité"
    elif "policy=weighted" in key:
        policy = "masse de probabilité"
    else:
        policy = "mode élu"
    model = eval_model or "modèle non renseigné"
    return {"key": key or f"{model}?", "model": model, "policy": policy,
            "label": f"{model} · {policy}"}


def read_store_history(db_path: Path, keep_verdicts: list[str]) -> dict:
    """Trajectoire des prompts non rejetés d'un store, avec décisions brutes.

    Le regroupement par ``params_key`` n'est pas cosmétique : deux nœuds évalués
    par des modèles différents ne sont pas comparables, même après recalcul du
    score — ce sont les *décisions* qui changent, pas seulement la loss.

    ``edges`` porte les arêtes réellement parcourues (``node_to`` → ``node_from``
    des mutations). Elles complètent la colonne ``parent`` des nœuds, vide dès
    qu'un prompt a été **dédoublonné** : les nœuds étant adressés par contenu, un
    texte déjà produit sur une autre branche est réutilisé avec le parent de sa
    première création. Sans ces arêtes, une lignée reconstruite perd son seed.

    Les noms de jeu **qualifiés par version** (``test@v2``) sont retenus au même
    titre que les noms nus : depuis que deux versions de jeux gelés coexistent, le
    store distingue ``test`` de ``test@v2`` — sans quoi une mesure v1 serait
    resservie pour une demande v2. Le filtre doit suivre, sinon la mesure payée
    reste invisible à la page. ``screen`` reste exclu : c'est un sous-ensemble
    strict du train, il ne porte pas de score de généralisation.
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        verdict_by_node: dict[str, str] = {}
        for row in conn.execute("SELECT node_to, verdict FROM mutations"):
            if row["node_to"]:
                verdict_by_node[row["node_to"]] = row["verdict"]
        nodes = []
        query = """
            SELECT n.hash, n.branch, n.iteration, n.created_at, n.parent,
                   e.dataset, e.params_key, e.scores_json, e.decisions,
                   e.eval_model, e.created_at AS eval_at
            FROM nodes n JOIN evals e ON e.node_hash = n.hash
            WHERE e.dataset IN ('train', 'val', 'test')
               OR e.dataset LIKE 'train@%'
               OR e.dataset LIKE 'val@%'
               OR e.dataset LIKE 'test@%'
            ORDER BY n.created_at, e.created_at
        """
        for row in conn.execute(query):
            verdict = verdict_by_node.get(row["hash"], "seed")
            if keep_verdicts and verdict not in keep_verdicts and verdict != "seed":
                continue
            try:
                scores = json.loads(row["scores_json"])
                decisions = json.loads(row["decisions"])
            except (TypeError, ValueError):
                continue
            nodes.append({
                "hash": row["hash"], "short": row["hash"][:8],
                "branch": row["branch"], "iteration": row["iteration"],
                "created_at": row["created_at"], "eval_at": row["eval_at"],
                "dataset": row["dataset"], "params_key": row["params_key"],
                "eval_model": row["eval_model"], "verdict": verdict,
                "stored_scores": scores, "decisions": decisions,
                "parent": row["parent"],
            })
        counts = {r["verdict"]: r["n"] for r in conn.execute(
            "SELECT verdict, COUNT(*) AS n FROM mutations GROUP BY verdict")}
        totals = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("nodes", "mutations", "evals")}
        edges = {}
        for row in conn.execute(
                "SELECT node_to, node_from FROM mutations WHERE node_to IS NOT NULL "
                "AND node_from IS NOT NULL ORDER BY iteration, id"):
            edges.setdefault(row["node_to"], row["node_from"])
    finally:
        conn.close()
    return {"nodes": nodes, "verdict_counts": counts, "totals": totals,
            "edges": edges}


def lineage_chain(leaf: str, parents: dict[str, Optional[str]],
                  edges: dict[str, str]) -> list[str]:
    """Chaîne seed → ``leaf``, en repliant sur les arêtes de mutation.

    ``parents`` vient de la colonne ``parent`` des nœuds, ``edges`` de la table
    des mutations (cf. ``read_store_history``). La garde sur les nœuds déjà vus
    protège d'un cycle qu'un store réparé à la main pourrait porter.
    """
    chain: list[str] = []
    seen: set[str] = set()
    cur: Optional[str] = leaf
    while cur and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        cur = parents.get(cur) or edges.get(cur)
    return list(reversed(chain))


def decisions_frame(decisions: list, metadata: dict[str, dict],
                    categorize) -> list[dict]:
    """Décisions stockées → trame de scoring (jointure par ``agent_id``)."""
    out = []
    for item in decisions:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        agent_id, mode = str(item[0]), item[1]
        weight = float(item[2]) if len(item) > 2 else 1.0
        meta = metadata.get(agent_id, {})
        out.append({"agent_id": agent_id, "mode_cat": categorize(mode),
                    "weight": weight, **meta})
    return out


def load_common_set_eval(path: Path) -> list[dict]:
    """Prompts ré-évalués sur le jeu commun (action A3) → trames de scoring.

    Le fichier est produit par ``scripts/synthesis/common_set_eval.py`` : une ligne
    par prompt mesuré, portant ses décisions sous forme compacte (``columns`` +
    ``decisions``) et le descriptif de l'échantillon.

    Deux différences avec les décisions lues du store (``decisions_frame``), et
    elles vont dans le même sens — être plus exact, pas moins :

    - les strates sont portées **par décision** et non rejointes par ``agent_id``.
      Une personne qui fait trois trajets garde ses trois motifs et ses trois
      distances, là où une jointure par agent n'en retiendrait qu'un ;
    - ``mode_cat`` est déjà catégorisé par le moteur au moment de l'éval, donc
      identique à ce qui a servi à calculer le composite stocké.

    Un fichier absent ou illisible renvoie une liste vide : la page retombe alors
    sur sa carte « Données manquantes », elle n'échoue pas.
    """
    p = Path(path)
    if not p.exists():
        return []
    out: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        columns = entry.get("columns") or []
        rows = []
        for raw in entry.get("decisions") or ():
            row = dict(zip(columns, raw))
            if row.get("mode_cat") is None:
                continue
            row["weight"] = float(row.get("weight") or 0.0)
            rows.append(row)
        if not rows:
            continue
        entry["rows"] = rows
        out.append(entry)
    # Graine d'abord, feuille ensuite : c'est le sens de lecture de la trajectoire.
    order = {"seed": 0, "leaf": 1}
    out.sort(key=lambda e: (order.get(e.get("role"), 9), e.get("short", "")))
    return out


# ── Volet 3 : modèle PROGEDO ─────────────────────────────────────────────────

def load_model_predictions(path: Path) -> Optional[dict]:
    """Prédictions du modèle sur le jeu commun (action A8) → trames de scoring.

    Le parquet est produit par ``scripts/synthesis/model_on_common_set.py`` : une ligne
    par décision du périmètre du volet 1, portant les probabilités **avant** et
    **après** renormalisation sur l'offre OTP, ainsi que les strates de scoring
    recopiées du journal. Il est donc scorable seul, sans relire ``moves.csv`` — même
    principe que le jsonl de l'action A3, et pour la même raison : les strates suivent
    la décision, pas l'agent.

    Deux lectures sont produites, comme pour le volet 1 :

    - ``attendu`` — une ligne par mode offert, pondérée par sa probabilité
      renormalisée. C'est la grandeur que le modèle calibre le mieux ;
    - ``elu`` — une ligne par décision, sur le mode le plus probable. Le modèle
      n'élit presque jamais le vélo (rappel 0,128 à l'entraînement) alors qu'il le
      calibre bien en masse : afficher les deux est la seule lecture honnête.

    ``brut`` complète le tableau : la même masse de probabilité **avant**
    renormalisation, pour que l'effet de la correction OTP soit mesurable et pas
    seulement affirmé.

    Fichier absent, illisible, ou pyarrow indisponible → ``None`` : la page retombe
    sur sa carte « Données manquantes », elle n'échoue pas.
    """
    p = Path(path)
    if not p.exists():
        return None
    try:
        import pyarrow.parquet as pq
        table = pq.read_table(p)
    except Exception:  # parquet tronqué, pyarrow absent…
        return None
    raw_meta = (table.schema.metadata or {}).get(b"progedo_on_common_set")
    try:
        meta = json.loads(raw_meta) if raw_meta else {}
    except ValueError:
        meta = {}
    records = table.to_pylist()

    attrs = ("genre", "age_cat", "occupation", "motif", "dist_cat",
             "lieu_residence", "type_logement")
    expected: list[dict] = []
    raw_expected: list[dict] = []
    elected: list[dict] = []
    for rec in records:
        if rec.get("status") != "ok":
            continue
        base = {k: rec.get(k) for k in attrs}
        base["agent_id"] = rec.get("agent_id")
        for mode in MODES:
            weight = rec.get(f"p_{mode}")
            if weight:
                expected.append({**base, "mode_cat": mode, "weight": float(weight)})
            raw_weight = rec.get(f"p_raw_{mode}")
            if raw_weight:
                raw_expected.append({**base, "mode_cat": mode,
                                     "weight": float(raw_weight)})
        if rec.get("argmax"):
            elected.append({**base, "mode_cat": rec["argmax"], "weight": 1.0})
    if not expected:
        return None
    return {"meta": meta,
            "variants": {"attendu": expected, "elu": elected, "brut": raw_expected},
            "n_rows": len(records)}


def read_prompt_variants(path: Path) -> dict:
    """Variantes historiques de prompts.yaml et leurs scores archivés."""
    with Path(path).open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    active = (doc.get("active") or {}).get("itinary_multi_agent")
    variants = []
    for name, node in (doc.get("prompts") or {}).items():
        calib = (node or {}).get("_calibration") or {}
        content = (node or {}).get("content") or ""
        variants.append({
            "name": name, "active": name == active,
            "words": len(content.split()),
            "seed": calib.get("seed"), "date": calib.get("date"),
            "iterations": calib.get("iterations"),
            "sample_size": calib.get("sample_size"),
            "score_initial": calib.get("score_initial"),
            "score_final": calib.get("score_final"),
            "has_archived_score": bool(calib.get("score_final")),
        })
    variants.sort(key=lambda v: (v["date"] or "", v["name"]))
    return {"active": active, "variants": variants}


# ── Scoring commun ───────────────────────────────────────────────────────────

def dimension_detail(rows: list[dict], cerema: dict, dim: dict) -> list[dict]:
    """Par catégorie : effectif, parts observées, parts cibles, écart L1."""
    parts = cerema.get("parts_modales_2023", {}).get(dim["cerema"]) or {}
    column = dim["column"]
    by_cat: dict[str, dict] = defaultdict(lambda: {"mass": Counter(), "agents": set()})
    for row in rows:
        cat = row.get(column)
        if cat is None or row.get("mode_cat") not in MODES:
            continue
        bucket = by_cat[cat]
        bucket["mass"][row["mode_cat"]] += float(row.get("weight", 1.0))
        bucket["agents"].add(row.get("agent_id"))

    # Ce que la boucle ci-dessous ne verra pas : les catégories que la référence ne
    # ventile pas (`hors périmètre` pour la zone, « Autres » pour le logement). Elles
    # n'ont aucune cible et sortent donc des strates — mais leur masse est publiée, au
    # lieu de disparaître dans un dénominateur.
    off_reference = {cat: {"mass": sum(bucket["mass"].values()),
                           "n": len(bucket["agents"])}
                     for cat, bucket in by_cat.items() if cat not in parts}

    out = []
    for cat in parts.keys():
        target = reference_shares(cerema, dim["cerema"], cat)
        bucket = by_cat.get(cat)
        if not bucket or sum(bucket["mass"].values()) <= 0:
            out.append({"cat": cat, "n": 0, "actual": {}, "target": target,
                        "l1": None, "covered": False})
            continue
        total = sum(bucket["mass"].values())
        actual = {m: bucket["mass"].get(m, 0.0) * 100.0 / total for m in MODES}
        l1 = sum(abs(actual.get(m, 0.0) - target.get(m, 0.0)) for m in MODES)
        n = len(bucket["agents"])
        out.append({"cat": cat, "n": n, "actual": actual, "target": target,
                    "l1": l1, "covered": n >= 5})
    if off_reference:
        excluded_mass = sum(row["mass"] for row in off_reference.values())
        out.append({"cat": OFF_REFERENCE_ROW, "n": sum(row["n"] for row
                                                       in off_reference.values()),
                    "actual": {}, "target": {}, "l1": None, "covered": False,
                    "excluded_mass": excluded_mass, "categories": off_reference})
    return out


def global_view(rows: list[dict], cerema: dict) -> dict:
    """Parts modales globales observées vs EMC², plus la masse hors périmètre."""
    mass = Counter()
    excluded = 0.0
    agents = set()
    for row in rows:
        mode = row.get("mode_cat")
        weight = float(row.get("weight", 1.0))
        if mode in MODES:
            mass[mode] += weight
            agents.add(row.get("agent_id"))
        else:
            excluded += weight
    total = sum(mass.values())
    target = reference_shares(cerema, "global")
    actual = {m: (mass.get(m, 0.0) * 100.0 / total if total else 0.0) for m in MODES}
    return {
        "actual": actual, "target": target,
        "gaps": {m: actual[m] - target.get(m, 0.0) for m in MODES},
        "l1": sum(abs(actual[m] - target.get(m, 0.0)) for m in MODES),
        "mass": total, "excluded_mass": excluded, "n_agents": len(agents),
    }


def worst_strata(details: dict[str, list[dict]], top_k: int = 8) -> list[dict]:
    """Pires croisements dimension × catégorie × mode, pondérés par effectif."""
    out = []
    for dim_key, rows in details.items():
        for entry in rows:
            if not entry.get("covered"):
                continue
            for mode in MODES:
                actual = entry["actual"].get(mode)
                target = entry["target"].get(mode)
                if actual is None or target is None:
                    continue
                diff = actual - target
                out.append({"dim": dim_key, "cat": entry["cat"], "mode": mode,
                            "actual": actual, "target": target, "diff": diff,
                            "n": entry["n"], "impact": abs(diff) * entry["n"]})
    out.sort(key=lambda r: r["impact"], reverse=True)
    return out[:top_k]


class Scorer:
    """Applique les loss du moteur de calibration à une trame de décision."""

    def __init__(self, calibration_module, weights: dict, primary: str,
                 secondary: str):
        from calibration import metrics as m
        self._m = m
        self._pd = __import__("pandas")
        self.weights = dict(weights)
        self.categorize = m.categorize_mode
        self.primary = self._build(primary)
        self.secondary = self._build(secondary) if secondary else None

    def _build(self, name: str):
        m = self._m
        cls = m.EMDJSDComposite if name in ("emd_jsd", "emd", "jsd") else m.L1Composite
        # length_penalty à 0 dans les poids : le composite reste défini pour un
        # volet sans prompt, et les trois volets sont sur la même échelle.
        return cls(weights=self.weights)

    def score(self, rows: list[dict], cerema: dict) -> dict:
        if not rows:
            return {}
        df = self._pd.DataFrame(rows)
        out: dict[str, Any] = {}
        primary = self.primary.compute(df, cerema, "")
        out[self.primary.name] = primary.model_dump(by_alias=True)
        if self.secondary is not None:
            secondary = self.secondary.compute(df, cerema, "")
            out[self.secondary.name] = secondary.model_dump(by_alias=True)
        return out


def coverage_matrix(rows: list[dict], cerema: dict) -> dict:
    """Effectif (en personnes) par dimension × catégorie, pour le seuil n ≥ 5."""
    out: dict[str, dict] = {}
    for dim in DIMENSIONS:
        parts = cerema.get("parts_modales_2023", {}).get(dim["cerema"]) or {}
        seen: dict[str, set] = defaultdict(set)
        for row in rows:
            cat = row.get(dim["column"])
            if cat is not None:
                seen[cat].add(row.get("agent_id"))
        out[dim["key"]] = {cat: len(seen.get(cat, ())) for cat in parts.keys()}
    return out
