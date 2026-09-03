"""Applique la politique PROGEDO au jeu commun, sur l'offre OTP (action A8).

    python -m scripts.synthesis.model_on_common_set [--dry-run]

**Le problème.** Le volet 3 de la page de synthèse dispose d'un modèle entraîné
(action A6) et d'un résolveur de zone fine (action A7), mais il n'a été appliqué à
aucune décision du run épinglé : sa colonne de la matrice comparative est vide. Or un
modèle qu'on n'a pas confronté au même substrat que les deux autres volets ne dit rien
de comparable.

**Ce que fait ce script.** Il rejoue chaque décision du run épinglé — le même périmètre
que le volet 1, construit par le même ``frames.read_moves`` — reconstruit les 21
variables du contrat de features, prédit ``P(mode)`` sur les 4 classes de la politique,
puis **restreint et renormalise la prédiction sur les modes réellement proposés par
OTP** pour ce trajet-là. Le résultat est écrit dans le parquet déclaré au manifeste
(``arms.model.predictions``), avec les probabilités **avant et après** renormalisation :
l'effet de la correction doit rester auditable.

**Pourquoi renormaliser.** La politique prédit sur 4 classes sans savoir ce qui était
offert. La simulation, elle, ne choisit que parmi les itinéraires qu'OTP a proposés.
Comparer les deux sans correction reviendrait à reprocher au LLM de n'avoir pas choisi
un mode qu'on ne lui a jamais offert, ou à créditer le modèle d'une option inexistante.
C'est l'hypothèse IIA du ticket 005 §4 (décision E10) : la préférence relative entre
deux modes offerts ne dépend pas de la présence d'un troisième.

**Ce qu'il n'impute pas.** Trois situations sortent du périmètre scoré, et elles sont
comptées plutôt que réparées en silence :

- **hors couche de zones** — le résolveur d'A7 renvoie « pas de zone » pour ~5 % des
  localisations, à 22 km en médiane du périmètre d'enquête. ``od_km`` est de loin la
  première variable du modèle et l'entraînement l'exigeait (``CRITICAL``) : prédire
  avec un ``od_km`` manquant serait une extrapolation hors domaine, pas une prédiction ;
- **offre vide de mode prédictible** — un trajet dont aucun mode proposé n'appartient
  aux 4 classes (deux-roues motorisé seul, par exemple) n'a pas de distribution à
  renormaliser ;
- **persona introuvable** — une décision qu'on ne sait pas rattacher à ses traits.

Ces lignes sont **écrites quand même** dans le parquet, avec leur ``status`` et sans
probabilité : la masse exclue se recompte depuis le fichier, elle n'est pas un chiffre
qu'il faut croire sur parole.

Déterministe : aucun tirage, aucun appel réseau, aucune clé d'API. Deux exécutions
produisent le même parquet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import frames
from .sources import REPO_ROOT, load_manifest

SCHEMA = "progedo_on_common_set/v1"

# ── Correspondance des modes — LE point unique ───────────────────────────────
#
# Quatre vocabulaires se croisent ici, et une correspondance approximative ne lève
# aucune exception : elle produit des probabilités plausibles et fausses.
#
#   classes de la politique   bike · car · transit · walk
#   modes canoniques du sim   walking · cycling · car · public_transport · train ·
#                             motorbike · other        (llm_module.core.mode_choice)
#   libellés du moves.csv     Marche · Vélo · Voiture Privée · Transports_collectifs ·
#                             Train · Deux-roues motorisé · Autres modes
#   catégories de la page     marche · velo · voiture · transports_collectifs · autres
#
# La page est le pivot : `frames.CHOSEN_MODE_MAP` traduit déjà les libellés du CSV en
# catégories, et c'est en catégories que le volet 1 est scoré. On n'a donc à définir
# ici qu'un seul pont, celui des classes de la politique.
POLICY_CLASS_TO_CAT = {
    "bike": "velo",
    "car": "voiture",
    "transit": "transports_collectifs",
    "walk": "marche",
}
CAT_TO_POLICY_CLASS = {v: k for k, v in POLICY_CLASS_TO_CAT.items()}

# Modes canoniques du simulateur → catégories de la page. Recopié de la table du
# journal de déplacements (`move_logger._CANONICAL_FR` + `frames.CHOSEN_MODE_MAP`), et
# vérifié par un test : c'est la seule façon de savoir que les deux ne divergent pas.
CANONICAL_TO_CAT = {
    "walking": "marche",
    "cycling": "velo",
    "car": "voiture",
    "public_transport": "transports_collectifs",
    "train": "transports_collectifs",
    "motorbike": "autres",
    "other": "autres",
}

# Deux fusions dissymétriques, à garder à l'esprit en lisant les chiffres :
#
# - `train` : la politique le range dans `transit`, la page dans
#   `transports_collectifs`. Les deux disent la même chose, le pont tient.
# - `motorbike` : la politique le range dans `car`, la page dans « autres » — hors des
#   4 modes scorés. Une offre « deux-roues motorisé » est donc **retirée de l'offre**
#   plutôt que comptée comme une offre de voiture : le volet 3 doit renormaliser sur
#   le même périmètre de modes que celui sur lequel le volet 1 est scoré, faute de
#   quoi les colonnes cessent d'être comparables. Le run épinglé n'en propose aucune.
PREDICTABLE_CATS = tuple(POLICY_CLASS_TO_CAT.values())

# Statuts d'une décision. `ok` seul entre dans le score ; les autres sont écrits avec
# leur raison, pour que la masse exclue se recompte depuis le parquet.
STATUS_OK = "ok"
STATUS_NO_ZONE = "hors_couche_zones"
STATUS_NO_OFFER = "offre_sans_mode_predictible"
STATUS_NO_PERSONA = "persona_introuvable"

# Colonnes de métadonnées recopiées du volet 1 : le parquet doit être scorable seul,
# sans relire moves.csv — même principe que le jsonl de l'action A3.
META_COLUMNS = ("genre", "age_cat", "occupation", "motif", "dist_cat",
                "lieu_residence", "type_logement")


# ── Traits du persona → variables du contrat ─────────────────────────────────

def has_bike(personal_bike: Any) -> Optional[bool]:
    """``personal_bike`` du persona → booléen ``has_bike`` du spec.

    À l'entraînement, ``has_bike`` vaut « le ménage déclare au moins un vélo »
    (``M21 > 0``). Le persona porte une chaîne à trois valeurs, dont la seule négative
    est « Pas de vélo » ; le VAE compte comme un vélo, l'enquête ne permettant pas de
    l'isoler (M22 non renseigné).
    """
    if personal_bike is None:
        return None
    text = str(personal_bike).strip().lower()
    if not text:
        return None
    return text != "pas de vélo"


def persona_features(traits: dict) -> dict:
    """Les 12 variables ``source: persona`` du spec, lues dans ``traits_json``.

    Aucune valeur n'est inventée : une clé absente reste absente, et
    ``encode_features`` la routera en manquante. Une modalité hors spec (le
    ``socioprofessional_class = "Retired"`` de la population synthétique, que le
    recodage de l'enquête ne produit jamais) devient elle aussi manquante — c'est le
    contrat explicite du spec, « modalité inattendue » n'étant pas « modalité la plus
    fréquente ». L'information n'est pas perdue pour autant : ``main_occupation``
    porte « Retraité », qui est dans le spec.
    """
    return {
        "age": traits.get("age"),
        "gender": traits.get("gender"),
        "household_size": traits.get("household_size"),
        "has_driving_license": traits.get("has_driving_license"),
        "has_pt_subscription": traits.get("has_pt_subscription"),
        "number_of_cars": traits.get("number_of_cars"),
        "car_availability": traits.get("car_availability"),
        "has_bike": has_bike(traits.get("personal_bike")),
        "socioprofessional_class": traits.get("socioprofessional_class"),
        "main_occupation": traits.get("main_occupation"),
        "employed": traits.get("employed"),
        "studies": traits.get("studies"),
    }


def activity_index(population: list[dict]) -> dict[str, dict]:
    """``(personne, activité) → contexte du déplacement qui y mène``.

    L'origine d'un déplacement est l'activité **précédente** dans la chaîne du persona.
    La chaîne est cyclique — ``activities[i-1].end_time == activities[i]
    .scheduled_start_time`` pour tout ``i``, y compris ``i = 0`` — donc l'origine du
    premier déplacement est la dernière activité, et non « rien ». Vérifié sur le run
    épinglé : 3 562 maillons, aucun rompu.
    """
    index: dict[str, dict] = {}
    for person in population:
        identity = person.get("identity") or {}
        traits = identity.get("traits_json") or {}
        activities = identity.get("activities") or []
        traits_features = persona_features(traits)
        for i, activity in enumerate(activities):
            origin = activities[i - 1]
            index[f'{person.get("person_id")}/{activity.get("id")}'] = {
                "traits": traits_features,
                "purpose": activity.get("purpose"),
                "purpose_origin": origin.get("purpose"),
                "origin": _lat_lon(origin.get("location")),
                "destination": _lat_lon(activity.get("location")),
            }
    return index


def _lat_lon(location: Optional[dict]) -> Optional[tuple[float, float]]:
    if not location:
        return None
    try:
        return float(location["lat"]), float(location["lon"])
    except (KeyError, TypeError, ValueError):
        return None


# ── Renormalisation sur l'offre ──────────────────────────────────────────────

def renormalize(probabilities: dict[str, float],
                offered: list[str]) -> Optional[dict[str, float]]:
    """Restreint ``probabilities`` aux modes offerts, puis renormalise à 100 %.

    ``probabilities`` et ``offered`` sont en **catégories de la page**. Renvoie ``None``
    quand l'intersection est vide (rien à renormaliser) ou quand la masse offerte est
    nulle — un modèle qui n'accorde exactement aucune chance à tout ce qui est offert
    ne fournit pas une distribution, il fournit une division par zéro.

    Un mode unique offert donne ``{mode: 1.0}`` : ce n'est pas une prédiction, c'est le
    constat qu'il n'y avait pas de choix. La simulation est dans le même cas, et le
    volet 1 compte ces trajets — les écarter d'un seul côté déséquilibrerait la
    comparaison.
    """
    kept = {m: probabilities.get(m, 0.0) for m in offered
            if m in probabilities}
    total = sum(kept.values())
    if not kept or total <= 0:
        return None
    return {m: v / total for m, v in kept.items()}


def offered_mass(probabilities: dict[str, float], offered: list[str]) -> float:
    """Masse de probabilité brute tombant sur les modes offerts, dans [0, 1].

    C'est le facteur de renormalisation, et la mesure directe de l'effet de la
    correction : 1,0 signifie qu'OTP offrait tout ce que le modèle envisageait.
    """
    return sum(probabilities.get(m, 0.0) for m in offered if m in probabilities)


# ── Chargement du modèle ─────────────────────────────────────────────────────

def load_policy(path: Path, spec: dict) -> tuple[Any, dict]:
    """Recharge le booster depuis l'artefact, après vérification du contrat.

    Le rechargement se fait par ``model_text`` (format natif LightGBM), qui restitue le
    booster à l'identique. La forme ``dump_model`` du même artefact existe pour
    l'évaluateur pur Python du conteneur ``controller``, qui n'a pas ``libgomp1`` ;
    ici, l'interpréteur de la page a LightGBM.

    Trois refus, tous silencieux si on ne les pose pas : un format d'artefact inconnu,
    un ``spec_version`` qui diverge de celui du spec lu, et un ordre de variables ou de
    classes qui ne serait pas celui du spec — un décalage d'une colonne donne des
    probabilités parfaitement plausibles.
    """
    import lightgbm as lgb

    artefact = json.loads(Path(path).read_text(encoding="utf-8"))
    if artefact.get("format") != "lightgbm_mode_choice_policy":
        raise ValueError(f"Format d'artefact inattendu : {artefact.get('format')!r}.")
    if artefact.get("spec_version") != spec.get("spec_version"):
        raise ValueError(
            f"Le modèle a été entraîné sous le contrat de features v"
            f"{artefact.get('spec_version')}, le spec lu est en v{spec.get('spec_version')}. "
            "Ré-entraînez la politique (make policy) plutôt que de prédire sous un "
            "contrat qui a changé.")

    names = [f["name"] for f in spec["features"]]
    if [f["name"] for f in artefact.get("features") or ()] != names:
        raise ValueError("L'ordre des variables de l'artefact diffère de celui du spec.")
    classes = list(spec["target"]["classes"])
    if list((artefact.get("target") or {}).get("classes") or ()) != classes:
        raise ValueError("L'ordre des classes de l'artefact diffère de celui du spec.")
    unknown = sorted(set(classes) - set(POLICY_CLASS_TO_CAT))
    if unknown:
        raise ValueError(f"Classes sans correspondance de mode : {unknown}.")

    booster = lgb.Booster(model_str=artefact["booster"]["model_text"])
    if list(booster.feature_name()) != names:
        raise ValueError("Le booster rechargé n'attend pas les variables du spec.")
    return booster, artefact


# ── Construction du jeu de prédiction ────────────────────────────────────────

def build_rows(moves: list[dict], index: dict[str, dict], resolver) -> list[dict]:
    """Une ligne par décision du périmètre du volet 1, enrichie de son contexte.

    ``resolver`` peut être ``None`` : les six variables géographiques sont alors
    absentes partout et toutes les décisions sortent en ``hors_couche_zones``. C'est
    volontaire — une couche manquante doit produire un fichier honnête et vide de
    prédictions, pas des prédictions sans géographie.
    """
    rows: list[dict] = []
    pending: list[int] = []
    origins: list[tuple[float, float]] = []
    destinations: list[tuple[float, float]] = []

    for move in moves:
        key = f'{move["agent_id"]}/{move["activity_id"]}'
        context = index.get(key)
        offered = [m for m in move["offered"] if m in PREDICTABLE_CATS]
        row: dict[str, Any] = {
            "agent_id": move["agent_id"],
            "activity_id": move["activity_id"],
            "offered": "|".join(move["offered"]),
            "offered_predictable": "|".join(offered),
            "n_offered": len(offered),
            "sim_chosen": move["chosen"],
            "departure_hour": move["departure_hour"],
            **{c: move.get(c) for c in META_COLUMNS},
        }
        if context is None:
            row["status"] = STATUS_NO_PERSONA
        elif not offered:
            row["status"] = STATUS_NO_OFFER
        else:
            row["status"] = STATUS_OK
            row.update(context["traits"])
            row["purpose"] = context["purpose"]
            row["purpose_origin"] = context["purpose_origin"]
            if resolver is not None and context["origin"] and context["destination"]:
                pending.append(len(rows))
                origins.append(context["origin"])
                destinations.append(context["destination"])
            else:
                row["status"] = STATUS_NO_ZONE
        rows.append(row)

    if pending:
        geo = resolver.geo_features_many(origins, destinations)
        for position, features in zip(pending, geo):
            if features is None:
                rows[position]["status"] = STATUS_NO_ZONE
            else:
                rows[position].update(features.as_dict())
    return rows


def predict(rows: list[dict], booster, spec: dict) -> dict[str, int]:
    """Ajoute ``p_raw_*`` puis ``p_*`` (renormalisées) aux lignes prédictibles.

    L'encodage est celui du script d'entraînement — ``encode_features`` importée telle
    quelle, jamais réécrite : c'est le meilleur moyen d'introduire un décalage
    silencieux entre entraînement et prédiction.

    Renvoie, par variable, le nombre de valeurs manquantes **après encodage**. Une
    modalité que le persona porte mais que le spec ne connaît pas y apparaît : c'est
    le seul endroit où l'écart de vocabulaire entre population synthétique et enquête
    devient visible, l'encodage la rendant manquante sans rien lever.
    """
    import pandas as pd

    from scripts.progedo_logit.fit_mode_choice_policy import encode_features

    classes = list(spec["target"]["classes"])
    predictable = [r for r in rows if r["status"] == STATUS_OK]
    if not predictable:
        return {}

    matrix = encode_features(pd.DataFrame(predictable), spec)
    missing = {name: int(matrix[name].isna().sum()) for name in matrix.columns}
    proba = booster.predict(matrix)
    for row, distribution in zip(predictable, proba):
        raw = {POLICY_CLASS_TO_CAT[c]: float(p) for c, p in zip(classes, distribution)}
        offered = [m for m in row["offered_predictable"].split("|") if m]
        row["p_offered_mass"] = offered_mass(raw, offered)
        renormalized = renormalize(raw, offered)
        for cat in PREDICTABLE_CATS:
            row[f"p_raw_{cat}"] = raw[cat]
            row[f"p_{cat}"] = (renormalized or {}).get(cat, 0.0)
        if renormalized is None:
            # Le modèle n'accorde aucune masse à ce qui était offert : il n'y a pas de
            # distribution à écrire. Cas jamais rencontré sur le run épinglé, mais il
            # doit sortir du score plutôt que d'y entrer en zéros.
            row["status"] = STATUS_NO_OFFER
            for cat in PREDICTABLE_CATS:
                row[f"p_{cat}"] = None
            continue
        row["argmax_raw"] = max(raw, key=raw.get)
        row["argmax"] = max(renormalized, key=renormalized.get)
    return {k: v for k, v in missing.items() if v}


# ── Écriture ─────────────────────────────────────────────────────────────────

# Ordre des colonnes du parquet : identifiants, offre, statut, probabilités avant
# puis après renormalisation, contexte, strates de scoring.
#
# Les six variables géographiques sont **délibérément absentes**. Elles sont calculées
# depuis `zf_zones.gpkg`, tenue hors dépôt au même titre que sa source PROGEDO (accès
# restreint lil-1750) : les réécrire ligne à ligne ici republierait, pour toutes les
# zones traversées par le run, les densités et distances au centre de cette ressource.
# Elles ne servent ni au score ni à la jointure avec le volet 1 ; qui veut auditer les
# entrées de la prédiction relance le script avec la couche en place.
COLUMNS = (
    ["agent_id", "activity_id", "status", "offered", "offered_predictable",
     "n_offered", "sim_chosen", "argmax_raw", "argmax", "p_offered_mass"]
    + [f"p_raw_{c}" for c in PREDICTABLE_CATS]
    + [f"p_{c}" for c in PREDICTABLE_CATS]
    + ["departure_hour"]
    + list(META_COLUMNS)
)


def _digest(path: Optional[Path]) -> Optional[str]:
    """sha256 d'un fichier, ou ``None`` s'il est illisible. Sert d'empreinte de modèle."""
    if path is None or not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_parquet(rows: list[dict], path: Path, meta: dict) -> None:
    """Écrit le parquet et y attache son descriptif (schéma, run, modèle, exclusions).

    Le descriptif voyage **dans** le fichier plutôt qu'à côté : le manifeste ne déclare
    qu'un chemin, et un parquet qu'on ne peut pas rattacher à son run ne prouve rien.
    """
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    df = pd.DataFrame(rows)
    for column in COLUMNS:
        if column not in df.columns:
            df[column] = None
    table = pa.Table.from_pandas(df[COLUMNS], preserve_index=False)
    table = table.replace_schema_metadata({
        **(table.schema.metadata or {}),
        b"progedo_on_common_set": json.dumps(meta, ensure_ascii=False).encode(),
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def summarize(rows: list[dict]) -> dict:
    """Comptes du run : statuts, taille des jeux de choix, effet de la renormalisation."""
    statuses = Counter(r["status"] for r in rows)
    scored = [r for r in rows if r["status"] == STATUS_OK]
    masses = sorted(r["p_offered_mass"] for r in scored) if scored else []
    single = sum(1 for r in scored if r["n_offered"] == 1)
    shifted = sum(1 for r in scored if r.get("argmax_raw") != r.get("argmax"))
    return {
        "n_moves": len(rows),
        "n_scored": len(scored),
        "n_agents": len({r["agent_id"] for r in rows}),
        "n_agents_scored": len({r["agent_id"] for r in scored}),
        "status_counts": dict(statuses),
        "excluded_pct": 100.0 * (len(rows) - len(scored)) / max(1, len(rows)),
        "offer_sizes": dict(Counter(r["n_offered"] for r in scored)),
        "n_single_offer": single,
        "n_argmax_shifted": shifted,
        "offered_mass_mean": (sum(masses) / len(masses)) if masses else None,
        "offered_mass_min": masses[0] if masses else None,
        "offered_mass_p10": masses[len(masses) // 10] if masses else None,
        "offered_mass_median": masses[len(masses) // 2] if masses else None,
    }


def shares(rows: list[dict], key: str) -> dict[str, float]:
    """Parts modales en % sur les lignes scorées, en masse (`p_`) ou brutes (`p_raw_`)."""
    scored = [r for r in rows if r["status"] == STATUS_OK]
    total = sum(sum(r[f"{key}{c}"] for c in PREDICTABLE_CATS) for r in scored)
    if total <= 0:
        return {}
    return {c: 100.0 * sum(r[f"{key}{c}"] for r in scored) / total
            for c in PREDICTABLE_CATS}


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", help="manifeste de sources (défaut : sources.yaml)")
    parser.add_argument("--out", help="parquet de sortie (défaut : celui du manifeste)")
    parser.add_argument("--dry-run", action="store_true",
                        help="affiche le périmètre et les comptes, sans rien écrire")
    args = parser.parse_args(argv)

    manifest = load_manifest(args.config)
    spec_path = manifest.path_of("arms.model.feature_spec")
    policy_path = manifest.path_of("arms.model.policy")
    zones_path = manifest.path_of("arms.model.zones")
    out_path = Path(args.out or manifest.get("arms.model.predictions"))
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path

    for label, path in (("feature_spec", spec_path), ("policy", policy_path)):
        if path is None or not path.exists():
            print(f"[erreur] {label} introuvable : {path}", file=sys.stderr)
            return 2

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    booster, artefact = load_policy(policy_path, spec)

    # ── Périmètre : celui du volet 1, construit par le même code ─────────────
    run = frames.resolve_run(manifest)
    if not run.get("exists") or not run.get("moves", {}).get("exists"):
        print(f"[erreur] Run introuvable ou sans moves.csv : "
              f"{manifest.get('common_set.run')}", file=sys.stderr)
        return 2
    moves_path = REPO_ROOT / run["moves"]["path"]
    moves, stats = frames.read_moves(
        moves_path, manifest.get("common_set.exclude_selection_methods", []))
    population_path = REPO_ROOT / run["population"]["path"]
    if not population_path.exists():
        print(f"[erreur] Population du run introuvable : {population_path}",
              file=sys.stderr)
        return 2
    population = json.loads(population_path.read_text(encoding="utf-8"))

    print(f"Run épinglé : {run['path']}")
    print(f"Périmètre du volet 1 : {len(moves)} décisions, "
          f"{len({m['agent_id'] for m in moves})} personnes "
          f"(sur {stats.get('total')} lignes du journal)")
    print(f"Modèle : spec v{spec['spec_version']}, "
          f"{len(spec['features'])} variables, "
          f"{len(spec['target']['classes'])} classes, "
          f"{artefact['booster']['best_iteration']} itérations")

    # ── Résolveur de zone fine ───────────────────────────────────────────────
    resolver = None
    resolver_error = ""
    if zones_path is not None and zones_path.exists():
        try:
            from llm_module.core.zone_resolver import ZoneResolver
            resolver = ZoneResolver.load(zones_path, feature_spec=spec_path)
        except Exception as exc:  # ressource illisible, geopandas absent…
            resolver_error = str(exc)
            print(f"⚠ Résolveur de zone fine indisponible : {exc}", file=sys.stderr)
    else:
        resolver_error = f"couche de zones absente ({zones_path}) — `make zones`"
        print(f"⚠ {resolver_error}", file=sys.stderr)

    rows = build_rows(moves, activity_index(population), resolver)
    if args.dry_run:
        print(f"\n--dry-run : {Counter(r['status'] for r in rows)}")
        return 0
    missing = predict(rows, booster, spec)

    summary = summarize(rows)
    if missing:
        print(f"\n⚠ Variables manquantes après encodage (sur "
              f"{summary['n_scored']} décisions scorées) : {missing}")
    print(f"\nStatuts : {summary['status_counts']}")
    print(f"Scorées : {summary['n_scored']}/{summary['n_moves']} décisions "
          f"({100 - summary['excluded_pct']:.1f} %), "
          f"{summary['n_agents_scored']}/{summary['n_agents']} personnes")
    print(f"Taille du jeu de choix (modes offerts) : {summary['offer_sizes']}")
    if summary["offered_mass_mean"] is not None:
        print(f"Masse offerte avant renormalisation : moyenne "
              f"{summary['offered_mass_mean']:.3f}, médiane "
              f"{summary['offered_mass_median']:.3f}, p10 "
              f"{summary['offered_mass_p10']:.3f}, min "
              f"{summary['offered_mass_min']:.3f}")
    print(f"Mode le plus probable déplacé par la renormalisation : "
          f"{summary['n_argmax_shifted']} décision(s)")

    before, after = shares(rows, "p_raw_"), shares(rows, "p_")
    print("\nParts modales prédites (masse de probabilité) :")
    print(f"  {'mode':22s} {'avant':>8s} {'après':>8s} {'écart':>8s}")
    for cat in PREDICTABLE_CATS:
        b, a = before.get(cat, 0.0), after.get(cat, 0.0)
        print(f"  {cat:22s} {b:7.1f}% {a:7.1f}% {a - b:+7.1f}")

    meta = {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run": run.get("path"),
        "moves_sha256": (run.get("moves") or {}).get("sha256"),
        "spec_version": spec["spec_version"],
        "policy_generated_at": artefact.get("generated_at"),
        # Empreinte de la POLITIQUE, et pas seulement sa date. `spec_version` ne bouge
        # que si le contrat de variables change : un ré-entraînement à variables
        # identiques — plus d'itérations, jeu d'entraînement corrigé — le laisse à sa
        # valeur, et la page servait alors un parquet périmé comme courant, en silence.
        # C'est le défaut symétrique de celui fermé le 2026-08-25 pour le run, sur l'axe
        # du modèle. Mesuré le 2026-08-27 : corriger la granularité des codes de zone a
        # porté le jeu d'entraînement de 27 886 à 52 248 déplacements sans toucher au
        # spec — exactement le cas que cette empreinte rend visible.
        "policy_sha256": _digest(policy_path),
        "classes": list(spec["target"]["classes"]),
        "class_to_cat": POLICY_CLASS_TO_CAT,
        "exclude_selection_methods":
            manifest.get("common_set.exclude_selection_methods", []),
        "zones": (manifest.get("arms.model.zones") if resolver is not None else None),
        "zones_error": resolver_error or None,
        "zone_coverage": resolver.coverage() if resolver is not None else None,
        "summary": summary,
        "feature_missing": missing,
        "shares_before": before,
        "shares_after": after,
    }
    write_parquet(rows, out_path, meta)
    rel = out_path.relative_to(REPO_ROOT) if out_path.is_relative_to(REPO_ROOT) else out_path
    print(f"\nÉcrit : {rel} ({len(rows)} lignes)")
    print("Régénérer la page : make synthesis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
