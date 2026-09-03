"""bare_prompt_replay.py — Le plancher « prompt nu » : que reste-t-il sans la personne ?

## La question

Le volet 1 vaut 16,16 sur le run épinglé. Combien de ce score vient de la machinerie
construite autour du LLM — persona, mémoire, météo, agenda, directives de décision — et
combien viendrait de n'importe quel modèle à qui l'on tend une liste d'itinéraires ?

Ce script mesure la seconde borne. Il rejoue **les mêmes décisions**, sur le **même
périmètre**, avec un prompt dépouillé de tout ce qui décrit la personne et de toute
consigne comportementale. Ne restent que la destination, l'heure de départ, et les
options qu'OTP a proposées.

## Trois planchers, et ils ne mesurent pas la même chose

| Plancher | Ce qu'il isole | Coût |
|---|---|---|
| **tirage uniforme** (`--uniform`) | le vrai hasard : une option au sort parmi celles offertes | 0 appel |
| **prompt nu** (`replay`) | les a priori propres du modèle, sans rien savoir de la personne | ~3 250 appels |
| volet 1 de la page | la chaîne complète | le run |

L'écart uniforme → nu dit ce qu'apportent les a priori du modèle ; l'écart nu → volet 1
dit ce qu'apportent le persona et les directives. Sans les deux bornes, on ne sait pas
laquelle des deux contributions on mesure.

⚠ **« Prompt nu » n'est pas « aléatoire ».** Un modèle sans persona garde des a priori
forts — il lira les durées et prendra le plus rapide. Nommer cette mesure « aléatoire »
présenterait un biais systématique comme du hasard. Le tirage uniforme, lui, est le
hasard, et c'est pour ça que les deux existent.

## Comment le bloc utilisateur est dépouillé

Le texte n'est **pas reconstruit** : il est rendu par le moteur de calibration, puis
FILTRÉ ligne à ligne. C'est délibéré — reconstruire la liste d'options ferait mesurer la
reconstruction en même temps que la variante, le piège que `alt_prompt_replay` documente
déjà pour son propre sous-jeu.

Sont retirés : la ligne de persona (« Odette, 41 ans, Travail à temps partiel… »), le
bloc météo, la météo à venir, l'agenda des trajets suivants, l'historique de mémoire, et
la zone entre parenthèses de la destination. Sont gardés : `agent_id`, destination,
heure de départ, la liste `- [n]` intacte avec ses sous-puces, et les consignes de sortie.

Le prompt système est la variante **`b_min`** de `prompts.yaml`, qui existe déjà pour ce
rôle (« prompt courant dépouillé de toute consigne comportementale ; ne restent que la
tâche et le format »).

## Un seul modèle

`--provider` sert un modèle unique, et c'est une exigence, pas un défaut de conception :
le run épinglé a réparti ses appels entre deux Gemini, et un plancher hérité du même
mélange ne serait comparable à rien.

Usage :
    python -m scripts.synthesis.bare_prompt_replay uniform            # 0 appel
    python -m scripts.synthesis.bare_prompt_replay replay --dry-run   # plan d'appels
    python -m scripts.synthesis.bare_prompt_replay replay --limit 40  # essai court
    python -m scripts.synthesis.bare_prompt_replay replay             # le plancher
    python -m scripts.synthesis.bare_prompt_replay score              # scorer une trace
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.synthesis import frames                                    # noqa: E402
from scripts.synthesis.sources import (import_calibration,              # noqa: E402
                                       load_manifest)

BATCH = 4
RPM = 14
SYSTEM_VARIANT = "b_min"
TRACE_DIR = REPO_ROOT / "docs/traces/2026-08-28_prompt_nu"


# Les clés vivent dans `prompt_calibration/.env` (dépôt autonome), pas dans le `.env`
# de la racine qui ne porte que les réglages vLLM. Sans ce chargement, tous les
# fournisseurs sont écartés en amont et l'erreur qui remonte est « Adapter inconnu » —
# message dont la cause réelle est ailleurs.
ENV_FILES = (REPO_ROOT / "prompt_calibration" / ".env", REPO_ROOT / ".env")
# `google2_35` partage la clé de `google2` : le quota est PAR MODÈLE, donc la même clé
# ouvre un second seau (cf. le commentaire de providers.yaml).
KEY_ALIASES = {"PROVIDER_KEYS__google2_35": "PROVIDER_KEYS__google2"}


def load_env() -> int:
    """Charge les `.env` sans écraser l'environnement. Renvoie le nombre de clés vues."""
    import os
    for path in ENV_FILES:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    for alias, source in KEY_ALIASES.items():
        if not os.environ.get(alias) and os.environ.get(source):
            os.environ[alias] = os.environ[source]
    return sum(1 for k in os.environ if k.startswith("PROVIDER_KEYS__"))


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} | {msg}", flush=True)


def alarm(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} | [ALARME] {msg}",
          file=sys.stderr, flush=True)


# ── Dépouillement du bloc utilisateur ────────────────────────────────────────

_HEADER = re.compile(r"^--- agent_id=(?P<id>\S+)\s*\|\s*Destination\s*:\s*(?P<dest>.*?)"
                     r"(?:\s*\((?P<zone>[^)]*)\))?\s*(?:\|\s*Départ\s*:\s*(?P<dep>[^|]*?))?\s*---\s*$")

# Blocs dont le titre ouvre une section à supprimer jusqu'à la ligne vide suivante.
_DROP_SECTIONS = ("**Trajets suivants prévus aujourd'hui :**", "**Historique :**")
# Lignes à supprimer seules.
_DROP_PREFIXES = ("**Contexte :**", "**Météo plus tard :**")

# ⚠ La mention d'abonnement TC n'est PAS sur la ligne de persona : depuis le
# 2026-08-26 elle est accolée à l'OPTION (`_pt_subscription_note`), donc à l'intérieur
# d'une ligne `- [n]` qu'on veut par ailleurs garder intacte. Un dépouillement qui ne
# traite que les lignes de persona laisse donc filtrer « cette personne a / n'a pas
# d'abonnement » — le prompt n'est plus nu, et rien ne le signale.
_PT_NOTE = re.compile(r"\s*(?:Abonné aux transports en commun|"
                      r"Pas d'abonnement aux transports en commun)\.")


def strip_user_block(text: str) -> tuple[str, dict]:
    """Retire du bloc utilisateur tout ce qui décrit la personne.

    Renvoie ``(texte_nu, compteur)``. Le compteur est retourné plutôt que journalisé :
    un dépouillement qui ne retire rien est un bug silencieux, et l'appelant doit
    pouvoir le voir.
    """
    out: list[str] = []
    counts = {"personas": 0, "contexte": 0, "agenda": 0, "historique": 0,
              "perception": 0, "zone": 0, "options": 0, "abonnement": 0}
    lines = text.split("\n")
    i, n = 0, len(lines)
    in_options = False
    while i < n:
        line = lines[i]
        m = _HEADER.match(line)
        if m:
            counts["personas"] += 1
            if m.group("zone"):
                counts["zone"] += 1
            head = f'--- agent_id={m.group("id")} | Destination : {m.group("dest").strip()}'
            if m.group("dep"):
                head += f' | Départ : {m.group("dep").strip()}'
            out.append(head + " ---")
            in_options = False
            # La ligne de perception suit l'en-tête (après un éventuel bloc météo) et
            # ne porte aucun marqueur : on la reconnaît à sa position, c'est-à-dire
            # comme la première ligne non vide qui n'est ni un bloc `**…**` ni une
            # option. La sauter ici est le seul endroit où l'ordre du gabarit compte.
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            while j < n and lines[j].startswith(_DROP_PREFIXES):
                counts["contexte"] += 1
                j += 1
                while j < n and not lines[j].strip():
                    j += 1
            if (j < n and lines[j].strip() and not lines[j].startswith("**")
                    and not lines[j].lstrip().startswith(("- [", "·"))):
                counts["perception"] += 1
                j += 1
            i = j
            continue
        if line.startswith(_DROP_PREFIXES):
            counts["contexte"] += 1
            i += 1
            continue
        if line.strip() in _DROP_SECTIONS:
            counts["agenda" if "Trajets" in line else "historique"] += 1
            i += 1
            while i < n and lines[i].strip():
                i += 1
            continue
        if line.startswith("**Options de trajet**"):
            in_options = True
        if in_options and line.lstrip().startswith("- ["):
            counts["options"] += 1
            stripped, n_pt = _PT_NOTE.subn("", line)
            if n_pt:
                counts["abonnement"] += n_pt
                line = stripped
        out.append(line)
        i += 1

    # Compacte les lignes vides consécutives laissées par les suppressions.
    clean: list[str] = []
    for line in out:
        if not line.strip() and clean and not clean[-1].strip():
            continue
        clean.append(line)
    return "\n".join(clean).strip() + "\n", counts


def bare_system_prompt() -> str:
    """La variante `b_min` de prompts.yaml — le rôle est déjà défini là-bas."""
    import yaml
    doc = yaml.safe_load((REPO_ROOT / "llm_module/prompts/prompts.yaml")
                         .read_text(encoding="utf-8")) or {}
    node = (doc.get("prompts") or {}).get(SYSTEM_VARIANT)
    if not node:
        raise SystemExit(f"variante « {SYSTEM_VARIANT} » absente de prompts.yaml")
    content = node.get("content") if isinstance(node, dict) else node
    if not content:
        raise SystemExit(f"variante « {SYSTEM_VARIANT} » vide")
    return content


# ── Périmètre ────────────────────────────────────────────────────────────────

def load_perimeter(manifest) -> tuple[Path, list[dict], dict]:
    run = frames.resolve_run(manifest)
    if not run.get("exists"):
        raise SystemExit(f"run introuvable : {manifest.get('common_set.run')}")
    run_dir = REPO_ROOT / run["path"]
    rows, stats = frames.read_moves(
        REPO_ROOT / run["moves"]["path"],
        manifest.get("common_set.exclude_selection_methods", []))
    return run_dir, rows, stats


def build_records(run_dir: Path, exclude: list[str]) -> list:
    """Les records du moteur, pour le périmètre du volet 1."""
    from calibration.exchanges import itinerary_entries
    from calibration.metadata import build_decision_records, load_population

    traits = load_population(next(run_dir.glob("population_*[0-9].json")))
    rows, read_stats = frames.read_moves(run_dir / "moves.csv", exclude)
    kept_day = read_stats.get("jour_retenu")
    entries = [e for e in itinerary_entries(run_dir / "llm_exchanges.jsonl")
               if e.get("sim_day") == kept_day]

    # `build_decision_records` s'appelle LOT PAR LOT et renvoie `(records, anomalies)`.
    # L'appeler sur la liste entière rend un tuple de deux éléments qu'une lecture
    # distraite prend pour deux records — le script tournait alors sur 2 décisions en
    # annonçant qu'il couvrait le périmètre.
    import datetime as _dt
    records, anomalies_total = [], 0
    for entry in entries:
        recs, anomalies = build_decision_records([entry], traits, weather=None)
        anomalies_total += len(anomalies)
        stamp = _dt.datetime.fromisoformat(entry["time"])
        for rec in recs:
            # L'heure du LOT : c'est elle qui désambiguïse deux décisions du même agent
            # offrant les mêmes modes. Sans elle, 1 356 décisions sont ambiguës et le
            # plancher tombe à 165 sur 3 249.
            rec["_time"] = stamp
            records.append(rec)
    if anomalies_total:
        alarm(f"{anomalies_total} bloc(s) persona non rattaché(s) à la population : "
              f"ces décisions ne seront pas rejouées.")
    log(f"périmètre : {len(rows)} décisions du volet 1 · "
        f"{len(entries)} lots du {kept_day} · {len(records)} blocs reconstruits")
    if len(records) < 0.5 * len(rows):
        alarm(f"seulement {len(records)} blocs pour {len(rows)} décisions : le plancher "
              f"porterait sur la moitié du périmètre. Vérifier la coupe au jour simulé.")
    return records


# ── Scoring ──────────────────────────────────────────────────────────────────

def score_frame(rows: list[dict], manifest, label: str) -> dict:
    cerema = frames.load_cerema(manifest.path_of("cerema"))
    calib, err = import_calibration(manifest.get("arms.calibration.repo",
                                                 "prompt_calibration"))
    if calib is None:
        raise SystemExit(f"moteur de calibration indisponible : {err}")
    scorer = frames.Scorer(calib, manifest.get("score.weights", {}),
                           manifest.get("score.metric", "emd_jsd"),
                           manifest.get("score.secondary", "l1_composite"))
    scores = scorer.score(rows, cerema)
    view = frames.global_view(rows, cerema)
    primary = manifest.get("score.metric", "emd_jsd")
    print(f"\n══ {label} ══")
    print(f"  composite {primary} : {scores[primary]['composite']:.3f}")
    print(f"  l1_composite       : {scores['l1_composite']['composite']:.2f}")
    print("  parts modales :")
    for mode in frames.MODES:
        actual = (view.get("actual") or {}).get(mode, 0.0)
        target = (view.get("target") or {}).get(mode, 0.0)
        print(f"    {mode:22s} {actual:5.1f} %   cible {target:5.1f}   "
              f"écart {actual - target:+5.1f}")
    return {"scores": scores, "global": view}


# ── Commandes ────────────────────────────────────────────────────────────────

def cmd_uniform(args) -> int:
    """Plancher du hasard : masse répartie à parts égales sur les modes OFFERTS.

    Sur les modes offerts et non sur les quatre : on ne crédite pas le hasard d'une
    option qu'OTP n'a pas proposée, exactement comme la renormalisation du volet 3 ne
    l'accorde pas au modèle statistique.
    """
    import pyarrow.parquet as pq
    manifest = load_manifest(args.config)
    table = pq.read_table(manifest.path_of("arms.model.predictions"))
    attrs = ("genre", "age_cat", "occupation", "motif", "dist_cat",
             "lieu_residence", "type_logement")
    rows, n_dec = [], 0
    for rec in table.to_pylist():
        if rec.get("status") != "ok":
            continue
        offered = [m for m in (rec.get("offered_predictable") or "").split("|") if m]
        if not offered:
            continue
        n_dec += 1
        base = {k: rec.get(k) for k in attrs}
        base["agent_id"] = rec.get("agent_id")
        # Deux hasards, et l'écart entre eux mesure ce que l'offre OTP apporte à elle
        # seule : le hasard CONTRAINT ne peut pas proposer un mode qu'OTP n'offrait pas,
        # le hasard NU l'ignore. Le second est le plancher absolu — aucune information
        # d'aucune sorte n'y entre, pas même la faisabilité du trajet.
        spread = frames.MODES if args.all_modes else offered
        for mode in spread:
            rows.append({**base, "mode_cat": mode, "weight": 1.0 / len(spread)})
    label = ("TIRAGE UNIFORME — 4 modes, offre ignorée" if args.all_modes
             else "TIRAGE UNIFORME — modes offerts par OTP")
    log(f"{n_dec} décisions · {len(rows)} lignes de trame")
    score_frame(rows, manifest, label)
    return 0


def cmd_replay(args) -> int:
    n_keys = load_env()
    log(f"{n_keys} clé(s) de fournisseur chargée(s)")
    if not n_keys:
        alarm("aucune clé PROVIDER_KEYS__* — vérifier prompt_calibration/.env")
        return 1
    manifest = load_manifest(args.config)
    # `calibration` vit dans un dépôt autonome : c'est `import_calibration` qui le met
    # sur le chemin. L'importer avant cet appel échoue, et le message ne dit pas
    # pourquoi — d'où l'ordre imposé ici.
    calib, err = import_calibration(manifest.get("arms.calibration.repo",
                                                 "prompt_calibration"))
    if calib is None:
        raise SystemExit(f"moteur de calibration indisponible : {err}")
    from calibration.evaluation import batches_from_records, make_provider_call
    from calibration.models import RunConfig

    run_dir, perimeter_rows, _ = load_perimeter(manifest)
    records = build_records(
        run_dir, manifest.get("common_set.exclude_selection_methods", []))
    if args.limit:
        records = records[:args.limit]
        log(f"⚠ --limit {args.limit} : essai court, PAS un plancher publiable")

    system = bare_system_prompt()
    batches = batches_from_records(records, BATCH, prod_option_handling=True)

    total = {"personas": 0, "perception": 0, "contexte": 0, "agenda": 0,
             "historique": 0, "zone": 0, "options": 0, "abonnement": 0}
    for batch in batches:
        batch["messages"][0]["content"] = system
        bare, counts = strip_user_block(batch["messages"][1]["content"])
        batch["messages"][1]["content"] = bare
        for k in total:
            total[k] += counts[k]

    log(f"dépouillement : {total['personas']} blocs · {total['perception']} lignes de "
        f"persona · {total['contexte']} blocs météo · {total['agenda']} agendas · "
        f"{total['historique']} historiques · {total['zone']} zones · "
        f"{total['options']} options conservées · "
        f"{total['abonnement']} mentions d'abonnement retirées")
    if total["personas"] and not total["perception"]:
        alarm("aucune ligne de persona retirée alors que des blocs existent — le "
              "gabarit a changé, le prompt n'est PAS nu. Arrêt.")
        return 2

    if args.dry_run:
        print(f"\n--dry-run : {len(batches)} lots, {len(records)} décisions, "
              f"~{len(batches) * 60.0 / RPM / 60:.0f} min à {RPM} req/min.")
        print("\n════════ exemple de bloc utilisateur nu ════════")
        print(batches[0]["messages"][1]["content"][:900])
        print("\n════════ prompt système ════════")
        print(system[:400])
        return 0

    config = RunConfig(eval_provider=args.provider, eval_model=args.model,
                       eval_temp=0.0, eval_batch_max=BATCH,
                       prod_option_handling=True, max_retry_wait=30.0,
                       schemas_path=str(REPO_ROOT / "llm_module/prompts/schemas.json"),
                       category="itinary_multi_agent")
    schema = json.loads(Path(config.schemas_path).read_text(
        encoding="utf-8"))[config.category]
    call = make_provider_call(config, schema)

    # Appariement record → ligne de `moves.csv`, pour connaître les strates de scoring.
    # La clé est (agent_id, jeu d'options) : le journal et le trajet n'ont pas de clé
    # commune, et c'est le jeu d'options qui VÉRIFIE l'appariement plutôt que de le
    # supposer. Un agent dont deux décisions offrent exactement les mêmes modes est
    # ambigu : on l'écarte et on le compte — apparier au hasard ferait porter le
    # plancher sur des strates fausses sans que rien ne le signale.
    from calibration.metrics import categorize_mode
    from collections import defaultdict
    # `section` est une CHAÎNE (le bloc d'options rendu), pas une liste de dicts :
    # son parsing vit déjà dans `alt_prompt_replay.option_categories`. Le réécrire
    # ferait deux lectures du même format à tenir d'accord.
    from scripts.synthesis.alt_prompt_replay import option_categories
    rows_by_key = defaultdict(list)
    for row in perimeter_rows:
        rows_by_key[(str(row["agent_id"]), frozenset(row["offered"]))].append(row)
    ambiguous = sum(len(v) - 1 for v in rows_by_key.values() if len(v) > 1)
    strata = {k: v[0] for k, v in rows_by_key.items() if len(v) == 1}
    log(f"appariement : {len(strata)} clés uniques, {ambiguous} décisions ambiguës écartées")

    ATTRS = ("genre", "age_cat", "occupation", "motif", "dist_cat",
             "lieu_residence", "type_logement")
    frame, matched, unmatched = [], 0, 0
    decisions, n_failed, consecutive = {}, 0, 0
    interval = 60.0 / RPM
    t0 = time.monotonic()
    for i, batch in enumerate(batches, 1):
        next_at = time.monotonic() + interval
        try:
            returned = call(batch) or []
            meta = batch.get("meta") or {}
            for dec in returned:
                rec = meta.get(str(dec["agent_id"]))
                if rec is None:
                    continue
                modes = frozenset(option_categories(rec["section"]))
                row = strata.get((str(dec["agent_id"]), modes))
                if row is None:
                    unmatched += 1
                    continue
                base = {a: row.get(a) for a in ATTRS}
                base["agent_id"] = str(dec["agent_id"])
                frame.append({**base, "mode_cat": categorize_mode(dec["mode"]),
                              "weight": float(dec["weight"])})
                decisions[f'{dec["agent_id"]}|{sorted(modes)}'] = True
                matched += 1
            consecutive = 0
        except Exception as exc:                                # noqa: BLE001
            n_failed += 1
            consecutive += 1
            alarm(f"lot {i}/{len(batches)} en échec : {exc}")
            if consecutive >= 5:
                # Ne PAS nommer la cause : cinq échecs d'affilée peuvent être un quota
                # épuisé, une clé absente, un fournisseur mal nommé ou le réseau. La
                # première version de ce message affirmait « quota probablement épuisé »
                # et a envoyé chercher un renouvellement alors qu'aucune clé n'était
                # exportée. Une alarme qui devine sa cause fait perdre plus de temps
                # qu'elle n'en gagne : on rend le message du fournisseur, tel quel.
                alarm(f"5 lots consécutifs en échec — arrêt à {i}/{len(batches)}, "
                      f"{len(decisions)} décision(s) obtenues. Dernier message du "
                      f"fournisseur : {exc}")
                break
        if i % 25 == 0 or i == len(batches):
            rate = i / max(time.monotonic() - t0, 1e-9) * 60
            log(f"{i}/{len(batches)} lots · {len(decisions)} décisions · "
                f"{rate:.1f} lots/min · {n_failed} échecs")
        sleep = next_at - time.monotonic()
        if sleep > 0:
            time.sleep(sleep)

    log(f"décisions rattachées : {matched} · non appariées : {unmatched}")
    if frame:
        score_frame(frame, manifest, f"PROMPT NU — {args.model}")

    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    trace = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run": str(run_dir.relative_to(REPO_ROOT)),
        "system_variant": SYSTEM_VARIANT,
        "provider": args.provider, "model": args.model,
        "n_records": len(records), "n_batches": len(batches),
        "n_failed_batches": n_failed, "n_decisions": len(decisions),
        "strip_counts": total,
        "decisions": decisions,
    }
    out = TRACE_DIR / f"prompt_nu_{args.model}.json"
    out.write_text(json.dumps(trace, ensure_ascii=False), encoding="utf-8")
    log(f"trace écrite : {out.relative_to(REPO_ROOT)}")
    if n_failed:
        alarm(f"{n_failed} lots perdus sur {len(batches)} : le plancher porte sur "
              f"{len(decisions)} décisions, pas sur {len(records)}. Le dire avant de "
              f"citer le chiffre.")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", help="manifeste (défaut : sources.yaml)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_u = sub.add_parser("uniform", help="plancher du hasard (aucun appel)")
    p_u.add_argument("--all-modes", action="store_true",
                     help="répartir sur les 4 modes en ignorant l'offre OTP — "
                          "le plancher absolu, aucune information n'y entre")
    p_u.set_defaults(func=cmd_uniform)

    p_r = sub.add_parser("replay", help="plancher « prompt nu » (consomme du quota)")
    # ⚠ C'est une CLÉ de providers.yaml, pas un nom d'adaptateur. Si sa clé API n'est
    # pas exportée, `llm_module.config` l'écarte en amont et l'erreur qui remonte est
    # « Adapter inconnu » — message trompeur dont la vraie cause est la clé absente.
    p_r.add_argument("--provider", default="google2",
                     help="clé de fournisseur dans providers.yaml (défaut : google2) ; "
                          "sa variable PROVIDER_KEYS__<clé> doit être exportée")
    p_r.add_argument("--model", default="gemini-3.1-flash-lite-preview")
    p_r.add_argument("--limit", type=int, help="essai court sur N décisions")
    p_r.add_argument("--dry-run", action="store_true")
    p_r.set_defaults(func=cmd_replay)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
