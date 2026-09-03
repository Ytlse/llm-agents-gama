"""Rejeu du sous-jeu « report marche → transports collectifs » sous dix prompts modifiés.

    python -m scripts.synthesis.alt_prompt_replay subset            # sélection seule, 0 appel
    python -m scripts.synthesis.alt_prompt_replay replay --dry-run  # plan d'appels
    python -m scripts.synthesis.alt_prompt_replay replay            # les 10 bras
    python -m scripts.synthesis.alt_prompt_replay render            # les 10 pages

**La question.** Le run épinglé produit un report de la marche vers les transports
collectifs (−14,5 points de marche, +11,9 de TC contre l'enquête EMC² 2023). Ce script
isole les décisions où ce report s'est joué — celles où le modèle a retenu un transport
collectif alors que la MARCHE lui était proposée — et redemande la même décision, sur le
même texte, sous dix prompts modifiés.

**Le sous-jeu.** Trois conditions, appliquées après les trois coupes du périmètre commun
(cf. ``docs/arch/score-synthesis.md``) : mode tiré = transports collectifs, marche
présente dans « Modes proposés au LLM », et décision retrouvée dans
``llm_exchanges.jsonl``. La troisième n'est pas une commodité : sans le lot d'origine, le
prompt utilisateur devrait être reconstruit, et on mesurerait alors la reconstruction en
même temps que la variante.

**L'appariement.** ``moves.csv`` et ``llm_exchanges.jsonl`` n'ont pas de clé commune. On
joint sur (``ID Personne``, ``Heure de calcul``) avec une tolérance de 5 secondes — le
journal horodate la fin du lot, la ligne de trajet sa propre écriture — puis on VÉRIFIE
l'appariement en comparant le jeu d'options des deux côtés. Un appariement ambigu est
écarté et compté, jamais deviné : une décision rattachée au mauvais trajet rejouerait un
autre prompt sous la même étiquette.

**Ce que le rejeu ne rejoue pas.** L'offre d'itinéraires OTP et la chaîne de véhicules du
jour sont celles du run, gelées dans le texte. On mesure l'effet du prompt sur la
DÉCISION, pas ce que la simulation aurait fait ensuite d'un agent qui marche (autres
horaires d'arrivée, autre chaîne, autre mémoire).

**Pas de bras témoin** (décision de l'utilisateur, 2026-08-26). L'écart publié se lit donc
contre le run lui-même, qui a tourné sur quatre fournisseurs alors que les variantes
tournent sur un seul : il mélange l'effet du prompt et celui du changement de modèle.
Chaque page le dit en tête. Pour trancher, il faudrait un onzième bras rejouant le prompt
INCHANGÉ dans les mêmes conditions.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import random
import sys
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from . import charts, frames, render
from .alt_prompt_variants import VARIANTS, VARIANTS_BY_ID, directive, system_prompt
from .sources import REPO_ROOT, import_calibration, load_manifest

# ── Réglages du rejeu ────────────────────────────────────────────────────────

# Lots de 8 personas. Même valeur que `common_set_eval` : à 15, le modèle rend un
# JSON valide mais amputé de personas (mesuré par l'action A10). Le découpage ne
# change pas la mesure — chaque persona voit exactement le même texte — seulement
# le nombre d'appels.
BATCH = 8

# Deux clés Google, MÊME modèle `gemini-3.5-flash-lite`. Le quota gratuit est de
# 500 requêtes/jour PAR PROJET ET PAR MODÈLE : une seule clé plafonnerait à ~500
# quand les dix bras en demandent ~620. Les variantes sont donc réparties entre les
# deux clés, qui tournent en parallèle. Ce n'est pas un changement de modèle — même
# nom, même version, même température — seulement un second seau de quota.
PROVIDERS = ["google2_35", "google_gemini35"]
MODEL = "gemini-3.5-flash-lite"
RPM = 15

# Le fournisseur `google2_35` tire sa clé de PROVIDER_KEYS__google2_35, qui n'est
# volontairement dans aucun fichier : le secret n'est pas dupliqué (cf. le commentaire
# de llm_module/config/providers.yaml). On la dérive au lancement.
KEY_ALIASES = {"PROVIDER_KEYS__google2_35": "PROVIDER_KEYS__google2"}

TRACE_DIR = REPO_ROOT / "docs/traces/2026-08-26_report_marche_tc"
PAGE_DIR = REPO_ROOT / "docs/synthesis"
PAGE_PREFIX = "detail_simulation_26_08_alternative"
ORIGIN_PAGE = "detail_simulation.html"

MATCH_TOLERANCE_S = 5.0

MODES = frames.MODES
MODE_LABELS = render.MODE_LABELS


# ── Journal ──────────────────────────────────────────────────────────────────

_t0 = time.monotonic()


def log(msg: str) -> None:
    print(f"[{time.monotonic() - _t0:7.1f}s] {msg}", flush=True)


def alarm(msg: str) -> None:
    print(f"[{time.monotonic() - _t0:7.1f}s] 🚨 [ALARME] {msg}", file=sys.stderr, flush=True)


# ── Environnement ────────────────────────────────────────────────────────────

def load_env() -> None:
    """Charge ``.env`` sans écraser l'environnement, puis dérive les clés alias."""
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())
    for alias, source in KEY_ALIASES.items():
        if not os.environ.get(alias) and os.environ.get(source):
            os.environ[alias] = os.environ[source]


def import_engine():
    """Rend le moteur de calibration importable (adaptateurs LLM, records, loss)."""
    repo = REPO_ROOT / "prompt_calibration"
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


# ── Sélection du sous-jeu ────────────────────────────────────────────────────

def row_key(agent_id: str, activity_id: str) -> str:
    return f"{agent_id}#{activity_id}"


def option_categories(section: str) -> set:
    """Catégories EMC² du jeu d'options d'un bloc persona (contrôle d'appariement)."""
    from calibration.evaluation import parse_option_modes
    from calibration.metrics import categorize_mode
    return {categorize_mode(m) for m in parse_option_modes(section).values()}


def select_subset(run_dir: Path, exclude_methods: list[str]) -> tuple[list[dict], list[dict], dict]:
    """``(rows, pairs, stats)`` — toutes les décisions du run, et le sous-jeu apparié.

    ``rows`` est la trame complète du volet 1 (elle sert de fond : seules les lignes
    du sous-jeu changeront). ``pairs`` porte, pour chaque décision retenue,
    la ligne de ``moves.csv``, le record d'évaluation et la clé de substitution.
    """
    from calibration.exchanges import itinerary_entries
    from calibration.metadata import build_decision_records, load_population

    t = time.monotonic()
    moves_path = run_dir / "moves.csv"
    rows, read_stats = frames.read_moves(moves_path, exclude_methods)
    kept_day = read_stats.get("jour_retenu")
    log(f"moves.csv lu : {len(rows)} décisions retenues, jour simulé {kept_day} "
        f"({read_stats.get('exclues_jour', 0)} lignes hors jour, "
        f"{read_stats.get('exclues_methode', 0)} sans décision modale)")

    # Les lignes brutes, pour « Heure de calcul » et « Raisonnement » que la trame
    # de scoring ne porte pas.
    #
    # ⚠ La coupe au premier jour simulé est indispensable ICI AUSSI. Le journal
    # déborde du jour retenu (bootstrap, horizon glissant) et le couple
    # (personne, activité) y réapparaît le lendemain : indexer sans couper garderait
    # la ligne du jour 2, dont l'« Heure de calcul » est celle d'un autre lot — et
    # 211 décisions du sous-jeu se retrouvaient alors « sans lot retrouvé » alors
    # que leur lot existe. `latest_attempts` ne les sépare pas : sa clé porte le
    # jour, c'est justement ce qui distingue une reprise d'une répétition.
    with moves_path.open(encoding="utf-8") as fh:
        raws = list(csv.DictReader(fh))
    raws, _ = frames.latest_attempts(raws)
    raws = [r for r in raws
            if not kept_day or frames.simulated_day(r.get("Temps simulé") or "") == kept_day]
    raw_by_key = {row_key((r.get("ID Personne") or "").strip(),
                          (r.get("ID Activité") or "").strip()): r for r in raws}

    population = next(run_dir.glob("population_*[0-9].json"))
    entries = [e for e in itinerary_entries(run_dir / "llm_exchanges.jsonl")
               if e.get("sim_day") == kept_day]
    traits = load_population(population)
    records: list[dict] = []
    anomalies_total = 0
    for entry in entries:
        recs, anomalies = build_decision_records([entry], traits, weather=None)
        anomalies_total += len(anomalies)
        stamp = dt.datetime.fromisoformat(entry["time"])
        for rec in recs:
            rec["_time"] = stamp
            rec["_task_id"] = entry.get("task_id")
            records.append(rec)
    if anomalies_total:
        alarm(f"{anomalies_total} bloc(s) persona non rattaché(s) à la population : "
              f"ces décisions ne pourront pas être rejouées.")
    log(f"llm_exchanges.jsonl lu : {len(entries)} lots du {kept_day}, "
        f"{len(records)} blocs persona reconstruits")

    by_agent: dict[str, list[dict]] = {}
    for rec in records:
        by_agent.setdefault(str(rec["agent_id"]), []).append(rec)

    # Compteurs pré-armés à zéro : un bilan qui omet ses comptes nuls se lit mal —
    # « 0 ambiguës » et « rubrique absente » ne sont pas la même information.
    stats = Counter({k: 0 for k in (
        "tc_sans_marche_proposee", "sous_jeu_brut", "ligne_brute_introuvable",
        "sans_heure_de_calcul", "non_apparie_absent", "non_apparie_ambigu", "apparie")})
    pairs: list[dict] = []
    for row in rows:
        if row["chosen"] != "transports_collectifs":
            continue
        if "marche" not in row["offered"]:
            stats["tc_sans_marche_proposee"] += 1
            continue
        stats["sous_jeu_brut"] += 1
        key = row_key(row["agent_id"], row["activity_id"])
        raw = raw_by_key.get(key)
        if raw is None:
            stats["ligne_brute_introuvable"] += 1
            continue
        computed = (raw.get("Heure de calcul") or "").strip()
        if not computed:
            stats["sans_heure_de_calcul"] += 1
            continue
        stamp = dt.datetime.fromisoformat(computed)
        wanted = set(row["offered"])
        near = [r for r in by_agent.get(row["agent_id"], [])
                if abs((r["_time"] - stamp).total_seconds()) <= MATCH_TOLERANCE_S]
        exact = [r for r in near if option_categories(r["section"]) == wanted]
        if len(exact) != 1:
            # Ambiguïté ou absence : on écarte. Rattacher au petit bonheur ferait
            # rejouer le prompt d'un AUTRE trajet sous l'étiquette de celui-ci.
            stats["non_apparie_ambigu" if len(exact) > 1 else "non_apparie_absent"] += 1
            continue
        pairs.append({"key": key, "row": row, "raw": raw, "record": exact[0]})
        stats["apparie"] += 1

    log(f"sous-jeu : {stats['sous_jeu_brut']} décisions « TC tiré + marche proposée », "
        f"{stats['apparie']} appariées à leur prompt exact "
        f"({stats['non_apparie_absent']} sans lot retrouvé, "
        f"{stats['non_apparie_ambigu']} ambiguës, "
        f"{stats['ligne_brute_introuvable']} sans ligne brute) "
        f"— sélection faite en {time.monotonic() - t:.1f}s")
    if not pairs:
        alarm("sous-jeu vide : aucune décision à rejouer.")

    # Deux décisions ne peuvent pas partager un bloc persona. Si cela arrivait, le
    # rejeu perdrait l'une des deux SANS RIEN DIRE : la jointure décision → ligne
    # passe par l'identité du record, et deux clés pour un même objet n'en laissent
    # qu'une. Le contrôle d'options rend le cas improbable, pas impossible — et un
    # sous-jeu amputé produit des parts modales parfaitement présentables.
    seen: dict[int, str] = {}
    for pair in pairs:
        marker = id(pair["record"])
        if marker in seen:
            raise SystemExit(
                f"[ALARME] les décisions {seen[marker]} et {pair['key']} sont "
                f"appariées au MÊME bloc persona : l'une des deux serait perdue "
                f"silencieusement au rejeu. Sélection refusée.")
        seen[marker] = pair["key"]

    stats["run_decisions"] = len(rows)
    stats["jour_retenu"] = kept_day
    return rows, pairs, dict(stats)


def base_system_prompt(run_dir: Path) -> str:
    """Le prompt système du run, verbatim. Refuse si le run n'en porte pas un seul."""
    from calibration.exchanges import itinerary_entries
    seen = {}
    for entry in itinerary_entries(run_dir / "llm_exchanges.jsonl"):
        content = entry["messages"][0]["content"]
        seen.setdefault(hashlib.sha256(content.encode()).hexdigest(), content)
    if len(seen) != 1:
        raise SystemExit(
            f"[ALARME] {len(seen)} prompts système distincts dans le run : il n'y a pas "
            f"de « prompt de production » unique à modifier, et l'écart mesuré "
            f"mélangerait les variantes avec les prompts d'origine. Rejeu refusé.")
    return next(iter(seen.values()))


# ── Rejeu ────────────────────────────────────────────────────────────────────

class QuotaExhausted(RuntimeError):
    """Le quota JOURNALIER de la clé est épuisé : ce bras ne se terminera pas aujourd'hui.

    Distincte d'un échec ordinaire : elle ne se retente pas, elle retire la clé de
    la rotation. Le bras est laissé SANS trace — une trace partielle serait relue
    comme une mesure, et la reprise la servirait sans jamais la compléter.
    """


def replay_variant(variant: dict, pairs: list[dict], base_prompt: str,
                   provider: str, dry_run: bool = False) -> dict:
    """Rejoue le sous-jeu sous une variante. Renvoie la trace complète du bras."""
    from calibration.evaluation import batches_from_records, classify_quota_error
    from calibration.metrics import categorize_mode
    from calibration.models import RunConfig
    from calibration.evaluation import make_provider_call

    prompt = system_prompt(base_prompt, variant)
    records = [p["record"] for p in pairs]
    # `batches_from_records` garantit un agent_id unique par lot : c'est ce qui rend
    # la jointure décision → record possible via `meta`. Un agent qui a plusieurs
    # trajets dans le sous-jeu voit donc ses trajets répartis sur des lots distincts.
    batches = batches_from_records(records, BATCH, prod_option_handling=True)
    for batch in batches:
        batch["messages"][0]["content"] = prompt

    if dry_run:
        return {"variant": variant["id"], "n_batches": len(batches),
                "n_records": len(records), "dry_run": True}

    # `max_retry_wait` court À DESSEIN. Le défaut (300 s) fait dormir la boucle de
    # retry jusqu'à 5 minutes par tentative, 5 fois : un quota JOURNALIER épuisé —
    # dont le `retryDelay` annoncé ne vaut rien, le seau ne se remplit qu'au reset —
    # bloquerait alors un bras une demi-heure avant d'échouer. Au-delà de 30 s, on
    # lève : le bras s'arrête franchement et la clé est déclarée morte.
    config = RunConfig(eval_provider=provider, eval_model=MODEL, eval_temp=0.0,
                       eval_batch_max=BATCH, prod_option_handling=True,
                       max_retry_wait=30.0,
                       schemas_path=str(REPO_ROOT / "llm_module/prompts/schemas.json"),
                       category="itinary_multi_agent")
    schema = json.loads(Path(config.schemas_path).read_text(encoding="utf-8"))[config.category]
    call = make_provider_call(config, schema)

    # Un record est identifié par (agent_id, task_id d'origine, entry) : deux trajets
    # du même agent tombent dans deux lots, et c'est le lot qui les distingue.
    key_of = {id(p["record"]): p["key"] for p in pairs}
    out: dict[str, dict] = {}
    interval = 60.0 / RPM
    t_start = time.monotonic()
    n_failed = 0
    consecutive = 0
    exhausted = False
    for i, batch in enumerate(batches, 1):
        next_at = time.monotonic() + interval
        try:
            decisions = call(batch)
            consecutive = 0
        except Exception as exc:                     # noqa: BLE001 — on journalise et on continue
            n_failed += 1
            consecutive += 1
            _retry_after, is_daily = classify_quota_error(exc)
            if is_daily:
                # Quota JOURNALIER : le seau ne se remplit qu'au reset. Insister
                # ne rend pas une décision de plus et masque la cause derrière une
                # série d'échecs qui ressemblent à des erreurs réseau.
                alarm(f"V{variant['id']} [{provider}] QUOTA JOURNALIER ÉPUISÉ au lot "
                      f"{i}/{len(batches)} — bras abandonné avec "
                      f"{len(out)}/{len(records)} décisions. La clé ne resservira "
                      f"qu'après le reset (minuit heure du Pacifique).")
                exhausted = True
                break
            alarm(f"V{variant['id']} [{provider}] lot {i}/{len(batches)} perdu "
                  f"({len(batch.get('meta') or {})} personas) : {exc!r}")
            if consecutive >= 3:
                alarm(f"V{variant['id']} [{provider}] 3 lots consécutifs perdus — "
                      f"arrêt du bras pour ne pas marteler l'API. "
                      f"{len(out)}/{len(records)} décisions obtenues.")
                break
            time.sleep(interval)
            continue
        meta = batch.get("meta") or {}
        for decision in decisions:
            rec = meta.get(str(decision["agent_id"]))
            if rec is None:
                continue
            key = key_of.get(id(rec))
            if key is None:
                continue
            cat = categorize_mode(decision["mode"])
            bucket = out.setdefault(key, {})
            bucket[cat] = bucket.get(cat, 0.0) + float(decision["weight"])
        if i % 10 == 0 or i == len(batches):
            log(f"  V{variant['id']} [{provider}] {i}/{len(batches)} lots — "
                f"{len(out)}/{len(records)} décisions")
        sleep_for = next_at - time.monotonic()
        if sleep_for > 0:
            time.sleep(sleep_for)

    elapsed = time.monotonic() - t_start
    coverage = len(out) / len(records) if records else 0.0
    if exhausted:
        # Un bras incomplet ne s'écrit PAS : une trace partielle serait relue plus
        # tard comme une mesure, et la reprise la servirait sans jamais la compléter.
        raise QuotaExhausted(
            f"V{variant['id']} interrompue par le quota journalier de {provider} "
            f"({len(out)}/{len(records)} décisions) — rien n'est écrit.")
    if coverage < 0.98:
        alarm(f"V{variant['id']} couverture {coverage:.1%} "
              f"({len(out)}/{len(records)}) — sous le plancher de 98 %. La page le dira.")
    else:
        log(f"✓ V{variant['id']} « {variant['slug']} » terminée : "
            f"{len(out)}/{len(records)} décisions ({coverage:.1%}), "
            f"{len(batches) - n_failed}/{len(batches)} lots, {elapsed / 60:.1f} min")
    return {
        "variant": variant["id"], "slug": variant["slug"], "title": variant["title"],
        "provider": provider, "model": MODEL, "temperature": 0.0, "batch": BATCH,
        "n_records": len(records), "n_decisions": len(out), "coverage": coverage,
        "n_batches": len(batches), "n_batches_failed": n_failed,
        "elapsed_s": round(elapsed, 1),
        "system_prompt": prompt,
        "directive": directive(variant),
        "decisions": out,
    }


def cmd_replay(args) -> int:
    manifest = load_manifest()
    run_dir = REPO_ROOT / manifest.get("common_set.run")
    exclude = manifest.get("common_set.exclude_selection_methods", [])
    load_env()
    import_engine()

    _rows, pairs, stats = select_subset(run_dir, exclude)
    base = base_system_prompt(run_dir)
    wanted = ([VARIANTS_BY_ID[i] for i in args.variants] if args.variants else VARIANTS)

    n_batches = -(-len(pairs) // BATCH)
    log(f"plan : {len(wanted)} bras × {n_batches} lots de {BATCH} = "
        f"{len(wanted) * n_batches} appels, modèle {MODEL}, {RPM} req/min et par clé, "
        f"{len(PROVIDERS)} clés en parallèle → ≳ "
        f"{len(wanted) * n_batches / (RPM * len(PROVIDERS)):.0f} min")
    if args.dry_run:
        for v in wanted:
            print(f"  V{v['id']:<3} {v['slug']:<16} {v['title']}")
        return 0

    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    (TRACE_DIR / "subset.json").write_text(json.dumps({
        "run": str(run_dir.relative_to(REPO_ROOT)),
        "sim_day": stats.get("jour_retenu"),
        "stats": {k: v for k, v in stats.items()},
        "keys": [p["key"] for p in pairs],
        "base_system_prompt": base,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # UNE file commune, un fil par clé. Pas d'affectation figée des bras aux clés :
    # une clé dont le quota journalier s'épuise sort de la rotation, et ses bras
    # restants sont repris par les survivantes. Avec une affectation statique — le
    # premier dispositif — l'épuisement de la clé 1 condamnait les cinq bras qui lui
    # étaient attribués alors que la clé 2 avait encore du quota.
    results: dict[int, dict] = {}
    pending: list[dict] = []
    for v in wanted:
        out_path = TRACE_DIR / f"variante_{v['id']:02d}_{v['slug']}.json"
        if out_path.exists() and not args.force:
            log(f"V{v['id']} déjà rejouée ({out_path.name}) — reprise sans appel")
            results[v["id"]] = json.loads(out_path.read_text(encoding="utf-8"))
        else:
            pending.append(v)
    if not pending:
        log("tous les bras demandés ont déjà leur trace — aucun appel.")
    queue = list(pending)
    lock = threading.Lock()
    dead: list[str] = []

    def worker(provider: str) -> None:
        while True:
            with lock:
                if not queue:
                    return
                v = queue.pop(0)
            log(f"→ V{v['id']} « {v['slug']} » sur {provider}")
            try:
                result = replay_variant(v, pairs, base, provider)
            except QuotaExhausted as exc:
                with lock:
                    queue.insert(0, v)          # rendu à la file pour une autre clé
                    dead.append(provider)
                    survivors = [p for p in PROVIDERS if p not in dead]
                alarm(f"{exc} Clé retirée de la rotation ; "
                      f"{len(queue)} bras rendus à la file, "
                      f"{len(survivors)} clé(s) encore active(s).")
                return
            except Exception as exc:            # noqa: BLE001 — un bras perdu n'arrête pas les autres
                alarm(f"V{v['id']} « {v['slug']} » abandonnée sur {provider} : {exc!r}")
                continue
            path = TRACE_DIR / f"variante_{v['id']:02d}_{v['slug']}.json"
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            with lock:
                results[v["id"]] = result

    threads = [threading.Thread(target=worker, args=(p,), daemon=False)
               for p in PROVIDERS]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    done = sorted(results)
    total_dec = sum(r.get("n_decisions", 0) for r in results.values())
    log(f"✓ rejeu terminé : {len(done)}/{len(wanted)} bras "
        f"(V{', V'.join(str(i) for i in done)}), {total_dec} décisions rejouées, "
        f"traces dans {TRACE_DIR.relative_to(REPO_ROOT)}")
    missing = [v["id"] for v in wanted if v["id"] not in results]
    if missing:
        alarm(f"bras sans résultat : V{', V'.join(str(i) for i in missing)}"
              + (f" — les {len(dead)} clé(s) {', '.join(dead)} ont épuisé leur quota "
                 f"journalier. Relancer la MÊME commande après le reset (minuit "
                 f"heure du Pacifique) : les bras déjà payés sont repris sans appel."
                 if dead else "."))
        return 1
    return 0


def cmd_subset(args) -> int:
    """Sélection seule — aucun appel LLM. Sert à vérifier le périmètre avant de payer."""
    manifest = load_manifest()
    run_dir = REPO_ROOT / manifest.get("common_set.run")
    import_engine()
    rows, pairs, stats = select_subset(
        run_dir, manifest.get("common_set.exclude_selection_methods", []))
    mass = Counter()
    for p in pairs:
        probas = p["row"]["probas"]
        total = sum(probas.values()) or 1.0
        for mode, weight in probas.items():
            mass[mode] += 100.0 * weight / total
    n = len(pairs) or 1
    print("\nMasse moyenne dans le sous-jeu apparié :")
    for mode in MODES:
        print(f"  {MODE_LABELS[mode]:<24} {mass.get(mode, 0.0) / n:5.1f} %")
    print(f"\nFond inchangé : {len(rows) - len(pairs)} décisions du run "
          f"conservées telles quelles.")
    return 0


# ── Recomposition et rendu ───────────────────────────────────────────────────

def substitute(rows: list[dict], decisions: dict[str, dict],
               variant_id: int) -> tuple[list[dict], dict]:
    """Remplace la masse des décisions rejouées, laisse le reste du run intact.

    Le mode TIRÉ des lignes remplacées est re-tiré dans la nouvelle distribution,
    avec une graine dérivée de (variante, clé de ligne) : sans cela la lecture
    « tiré » de la page continuerait d'afficher le tirage de l'ancienne masse, et
    les deux lectures de la même page se contrediraient.
    """
    stats = Counter()
    out = []
    for row in rows:
        key = row_key(row["agent_id"], row["activity_id"])
        if key not in decisions:
            out.append(row)
            stats["inchangees"] += 1
            continue
        # Le bras a vu cette décision. Une masse vide ou nulle n'est PAS une raison
        # de retirer la ligne du scoring : elle en sortirait les parts modales sans
        # qu'aucune décision ait changé d'avis. On garde celle du run, et on compte.
        new = decisions[key] or {}
        total = sum(new.values())
        if total <= 0:
            out.append(row)
            stats["masse_nulle"] += 1
            continue
        probas = {m: 100.0 * w / total for m, w in new.items()}
        rng = random.Random(f"alt{variant_id}:{key}")
        modes = sorted(probas)
        drawn = rng.choices(modes, weights=[probas[m] for m in modes], k=1)[0]
        replaced = dict(row)
        replaced["probas"] = probas
        replaced["chosen"] = drawn
        out.append(replaced)
        stats["remplacees"] += 1
        if drawn == "marche":
            stats["retirage_marche"] += 1
    return out, dict(stats)


def subset_mass(rows: list[dict], keys: set) -> dict:
    """Parts modales moyennes sur les seules lignes du sous-jeu (masse, en %)."""
    mass = Counter()
    n = 0
    for row in rows:
        if row_key(row["agent_id"], row["activity_id"]) not in keys:
            continue
        probas = row["probas"]
        total = sum(probas.values())
        if total <= 0:
            continue
        n += 1
        for mode, weight in probas.items():
            mass[mode] += 100.0 * weight / total
    return {m: (mass.get(m, 0.0) / n if n else 0.0) for m in MODES} | {"n": n}


def build_payload(rows: list[dict], cerema: dict, scorer, engine_note: str) -> dict:
    from .build import build_simulation
    return {
        "generated_at": dt.datetime.now().strftime("%d/%m/%Y à %H:%M"),
        "engine_note": engine_note,
        "arms": {"simulation": build_simulation(rows, cerema, scorer)},
    }


def _pct(value: Optional[float], digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _signed(value: Optional[float], digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:+.{digits}f}"


def render_page(variant: dict, trace: dict, base_arm: dict, alt_arm: dict,
                before: dict, after: dict, payload: dict, stats: dict,
                subset_stats: dict) -> str:
    """La page de la variante : en-tête de dispositif, prompt complet, puis le
    sous-chapitre « Détail par sous-catégorie » rendu par la MÊME fonction que
    ``detail_simulation.html``. Aucun chiffre n'est recopié d'une page à l'autre."""
    from html import escape

    details = (alt_arm.get("details") or {})
    body = render._dimension_blocks(details, "sim")

    def scores(arm: dict) -> dict:
        return ((arm.get("variants") or {}).get("attendu", {}).get("scores", {}) or {})

    def composite(arm: dict, metric: str) -> Optional[float]:
        return (scores(arm).get(metric) or {}).get("composite")

    base_g = (base_arm.get("variants") or {})["attendu"]["global"]
    alt_g = (alt_arm.get("variants") or {})["attendu"]["global"]
    c_base, c_alt = composite(base_arm, "emd_jsd"), composite(alt_arm, "emd_jsd")
    l_base, l_alt = composite(base_arm, "l1_composite"), composite(alt_arm, "l1_composite")
    d_comp = None if (c_base is None or c_alt is None) else c_alt - c_base
    d_l1 = None if (l_base is None or l_alt is None) else l_alt - l_base

    def verdict(delta: Optional[float]) -> str:
        if delta is None:
            return "score indisponible"
        if delta < -0.5:
            return "composite amélioré"
        if delta > 0.5:
            return "composite dégradé"
        return "composite inchangé (|Δ| ≤ 0,5)"

    tiles = f"""<div class="tiles">
<div class="tile"><div class="k">Composite emd_jsd</div><div class="v">{_pct(c_alt, 2)}</div>
<div class="u">run&nbsp;: {_pct(c_base, 2)} · Δ {_signed(d_comp, 2)}</div></div>
<div class="tile"><div class="k">Composite L1 (points)</div><div class="v">{_pct(l_alt, 2)}</div>
<div class="u">run&nbsp;: {_pct(l_base, 2)} · Δ {_signed(d_l1, 2)}</div></div>
<div class="tile"><div class="k">Part marche produite</div><div class="v">{_pct(alt_g['actual']['marche'])}&nbsp;%</div>
<div class="u">run&nbsp;: {_pct(base_g['actual']['marche'])} · EMC²&nbsp;: {_pct(base_g['target'].get('marche'))}</div></div>
<div class="tile"><div class="k">Part TC produite</div><div class="v">{_pct(alt_g['actual']['transports_collectifs'])}&nbsp;%</div>
<div class="u">run&nbsp;: {_pct(base_g['actual']['transports_collectifs'])} · EMC²&nbsp;: {_pct(base_g['target'].get('transports_collectifs'))}</div></div>
</div>"""

    global_rows = "".join(
        f"<tr><td><strong>{escape(MODE_LABELS[m])}</strong></td>"
        f"<td class=\"num\">{_pct(base_g['actual'][m])}</td>"
        f"<td class=\"num\">{_pct(alt_g['actual'][m])}</td>"
        f"<td class=\"num\">{_signed(alt_g['actual'][m] - base_g['actual'][m])}</td>"
        f"<td class=\"num\">{_pct(base_g['target'].get(m))}</td>"
        f"<td class=\"num\">{_signed(alt_g['gaps'][m])}</td></tr>" for m in MODES)

    subset_rows = "".join(
        f"<tr><td><strong>{escape(MODE_LABELS[m])}</strong></td>"
        f"<td class=\"num\">{_pct(before[m])}</td>"
        f"<td class=\"num\">{_pct(after[m])}</td>"
        f"<td class=\"num\">{_signed(after[m] - before[m])}</td></tr>" for m in MODES)

    others = " · ".join(
        f'<a href="{PAGE_PREFIX}{v["id"]}.html">V{v["id"]}</a>' if v["id"] != variant["id"]
        else f'<strong>V{v["id"]}</strong>' for v in VARIANTS)

    coverage = trace.get("coverage", 0.0)
    coverage_note = ""
    if coverage < 0.98:
        coverage_note = (
            f'<p class="warn-note">⚠ Couverture du rejeu&nbsp;: '
            f'{100 * coverage:.1f}&nbsp;% ({trace["n_decisions"]}/{trace["n_records"]} '
            f'décisions rendues). Les décisions non rendues gardent la masse du run, '
            f'ce qui atténue mécaniquement l\'écart affiché.</p>')

    prompt_html = escape(trace["system_prompt"]).replace(
        escape(trace["directive"]),
        f'<mark class="added">{escape(trace["directive"])}</mark>')

    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Alternative {variant['id']} — {escape(variant['title'])}</title>
<style>{render.CSS}
.solo{{max-width:1040px;margin:0 auto;padding:32px 40px 96px}}
.solo h1{{font-size:21px;font-weight:500;margin:0 0 4px;letter-spacing:-.015em}}
.solo .sub{{font-size:13px;color:var(--ink3);margin-bottom:18px}}
.solo .links{{display:flex;flex-wrap:wrap;gap:14px;font-size:13px;margin-bottom:22px}}
pre.prompt{{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:16px 18px;overflow-x:auto;white-space:pre-wrap;word-break:break-word;
font-family:var(--mono);font-size:12px;line-height:1.6;color:var(--ink2);margin:12px 0}}
mark.added{{background:#fdf0d5;color:var(--ink);padding:2px 0;border-radius:2px;
box-shadow:0 0 0 3px #fdf0d5}}
@media (prefers-color-scheme:dark){{mark.added{{background:#3a2f18;color:var(--ink);
box-shadow:0 0 0 3px #3a2f18}}}}
@media(max-width:880px){{.solo{{padding:24px 20px 64px}}}}
</style></head>
<body><main class="solo">
<h1>Alternative {variant['id']} — {escape(variant['title'])}</h1>
<div class="sub">Volet 1 — Simulation (LLM + tirage), sous-jeu du report
marche&nbsp;→&nbsp;transports collectifs rejoué sous prompt modifié</div>
<div class="links"><a href="{ORIGIN_PAGE}">← Page d'origine (run inchangé)</a>
<a href="index.html">Synthèse complète</a>
<span style="color:var(--ink3)">Alternatives&nbsp;: {others}</span></div>
<p style="color:var(--ink3);font-size:12.5px;margin-bottom:24px">
Généré le {escape(payload['generated_at'])} · {escape(payload['engine_note'])}</p>

<section id="dispositif">
<h2>Ce qui a été rejoué, et ce qui ne l'a pas été</h2>
<p class="lede">Sur les <strong>{stats['sous_jeu_brut']} décisions</strong> du run où le
modèle a retenu un transport collectif <em>alors que la marche lui était proposée</em>,
<strong>{stats['apparie']}</strong> ont été retrouvées dans le journal d'échanges et
redemandées au modèle sous le prompt ci-dessous — même persona, même météo, même agenda,
mêmes itinéraires OTP, seul le prompt système change. Les
<strong>{stats['run_decisions'] - stats['apparie']}</strong> autres décisions du run sont
conservées telles quelles&nbsp;: les profils ci-dessous portent donc sur le run entier,
dont une part rejouée.</p>
{tiles}
{coverage_note}
<div class="note"><div class="t">Ce que cette page ne permet pas de conclure</div>
<ul>
<li><strong>Aucun bras témoin.</strong> Le run a tourné sur quatre fournisseurs&nbsp;;
les variantes tournent sur un seul ({escape(trace['model'])}, température 0). L'écart lu
mélange donc l'effet du prompt et celui du changement de modèle. Il faudrait un bras
rejouant le prompt <em>inchangé</em> dans ces mêmes conditions pour les séparer.</li>
<li><strong>Le sous-jeu est sélectionné sur un tirage.</strong> Le critère est le mode
<em>tiré</em>, pas la masse&nbsp;: sur les {stats['apparie']} décisions retenues, la masse
de transport collectif valait déjà {_pct(before['transports_collectifs'])}&nbsp;% en
moyenne, mais une partie d'entre elles avaient un autre mode en tête et c'est le tirage
qui a sorti le TC. Sélectionner sur un aléa puis remplacer la masse introduit un effet de
sélection qui gonfle l'écart apparent.</li>
<li><strong>Levier de niveau, pas de pente.</strong> Le défaut chiffré du modèle est une
élasticité à la distance quasi nulle. Un ajout de prompt qui déplace la masse à toutes
les distances peut améliorer l'agrégat en dégradant les tranches longues&nbsp;: c'est le
<em>détail par tranche de distance</em>, plus bas, qui le dit — pas les tuiles.</li>
<li><strong>La simulation n'est pas rejouée.</strong> On mesure l'effet du prompt sur la
décision, pas ce que la ville aurait fait ensuite d'un agent qui marche (horaires
d'arrivée, chaîne de véhicules, mémoire).</li>
</ul></div>

<h3>Parts modales globales</h3>
<table><thead><tr><th>Mode</th><th class="num">Run</th><th class="num">Variante</th>
<th class="num">Δ</th><th class="num">EMC² 2023</th><th class="num">Écart à EMC²</th></tr></thead>
<tbody>{global_rows}</tbody></table>
<p style="font-size:12.5px;color:var(--ink3)">{escape(verdict(d_comp))}.
Masse rejouée&nbsp;: {subset_stats.get('remplacees', 0)} lignes remplacées,
{subset_stats.get('inchangees', 0)} inchangées.</p>

<h3>Effet sur le sous-jeu seul ({before['n']} décisions rejouées)</h3>
<p>C'est ici que l'ajout agit&nbsp;; le tableau précédent dilue cet effet dans les
{stats['run_decisions'] - stats['apparie']} décisions non rejouées.</p>
<table><thead><tr><th>Mode</th><th class="num">Masse avant</th>
<th class="num">Masse après</th><th class="num">Δ</th></tr></thead>
<tbody>{subset_rows}</tbody></table>
</section>

<section id="prompt">
<h2>Le prompt système complet de la variante</h2>
<p class="lede">Le prompt du run, mot pour mot, plus la section
<mark class="added">surlignée</mark>. Rien n'a été retiré. Argument du modèle que
l'ajout vise&nbsp;: <em>{escape(variant['targets'])}</em>.</p>
<pre class="prompt">{prompt_html}</pre>
<p style="font-size:12.5px;color:var(--ink3)">Modèle&nbsp;:
<code>{escape(trace['model'])}</code> · fournisseur <code>{escape(trace['provider'])}</code>
· température 0 · lots de {trace['batch']} personas ·
{trace['n_batches']} appels{'' if not trace['n_batches_failed'] else f", dont {trace['n_batches_failed']} perdu(s)"}.</p>
</section>

<section id="detail">
<h2>Détail par sous-catégorie</h2>
<p class="lede">Le même sous-chapitre que
<a href="{ORIGIN_PAGE}">{escape(ORIGIN_PAGE)}</a>, recalculé sur le run dont les
{stats['apparie']} décisions du sous-jeu ont été remplacées. Barres = parts modales de la
population simulée, repère de référence = EMC² 2023. Les dimensions marquées
<span class="badge ok">dans le composite</span> entrent dans le score&nbsp;; celles
marquées <span class="badge">hors composite</span> sont rapportées pour lecture seulement.
<strong>Plus l'écart au repère est faible, meilleur c'est.</strong></p>
{body}
</section>
<footer>Régénérer&nbsp;:
<code>python -m scripts.synthesis.alt_prompt_replay render</code> ·
Traces du rejeu&nbsp;: <code>docs/traces/2026-08-26_report_marche_tc/</code> ·
Page d'origine&nbsp;: <code>docs/synthesis/{escape(ORIGIN_PAGE)}</code></footer>
</main></body></html>"""


def cmd_render(args) -> int:
    manifest = load_manifest()
    run_dir = REPO_ROOT / manifest.get("common_set.run")
    import_engine()

    cerema_path = REPO_ROOT / manifest.get("cerema")
    cerema = frames.load_cerema(cerema_path)
    calibration, engine_error = import_calibration(
        manifest.get("arms.calibration.repo", "prompt_calibration"))
    if calibration is None:
        alarm(f"moteur de calibration indisponible ({engine_error}) : les pages "
              f"sortiraient sans score. Rendu refusé.")
        return 2
    scorer = frames.Scorer(calibration, manifest.get("score.weights", {}),
                           manifest.get("score.metric", "emd_jsd"),
                           manifest.get("score.secondary", "l1_composite"))
    engine_note = "Loss importée du moteur de calibration"

    rows, pairs, stats = select_subset(
        run_dir, manifest.get("common_set.exclude_selection_methods", []))
    keys = {p["key"] for p in pairs}
    before = subset_mass(rows, keys)

    base_payload = build_payload(rows, cerema, scorer, engine_note)
    base_arm = base_payload["arms"]["simulation"]
    log(f"référence recalculée depuis le run : composite "
        f"{_pct((base_arm['variants']['attendu']['scores'].get('emd_jsd') or {}).get('composite'), 2)}")

    PAGE_DIR.mkdir(parents=True, exist_ok=True)
    wanted = ([VARIANTS_BY_ID[i] for i in args.variants] if args.variants else VARIANTS)
    written, skipped, summary = [], [], []
    for variant in wanted:
        trace_path = TRACE_DIR / f"variante_{variant['id']:02d}_{variant['slug']}.json"
        if not trace_path.exists():
            skipped.append(variant["id"])
            alarm(f"V{variant['id']} sans trace de rejeu ({trace_path.name}) : "
                  f"page non écrite. Lancer d'abord `replay --variants {variant['id']}`.")
            continue
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        alt_rows, sub_stats = substitute(rows, trace["decisions"], variant["id"])
        after = subset_mass(alt_rows, keys)
        payload = build_payload(alt_rows, cerema, scorer, engine_note)
        html = render_page(variant, trace, base_arm, payload["arms"]["simulation"],
                           before, after, payload, stats, sub_stats)
        out = PAGE_DIR / f"{PAGE_PREFIX}{variant['id']}.html"
        out.write_text(html, encoding="utf-8")
        written.append(out.name)
        alt_arm = payload["arms"]["simulation"]
        alt_scores = (alt_arm["variants"]["attendu"]["scores"].get("emd_jsd") or {})
        alt_g = alt_arm["variants"]["attendu"]["global"]
        summary.append({
            "id": variant["id"], "slug": variant["slug"],
            "composite": alt_scores.get("composite"),
            "marche_global": alt_g["actual"]["marche"],
            "tc_global": alt_g["actual"]["transports_collectifs"],
            "voiture_global": alt_g["actual"]["voiture"],
            "marche_sousjeu": after["marche"], "tc_sousjeu": after["transports_collectifs"],
            "voiture_sousjeu": after["voiture"],
            "coverage": trace.get("coverage", 0.0),
        })
        log(f"✓ {out.name} — marche {_pct(after['marche'])} % sur le sous-jeu "
            f"(avant {_pct(before['marche'])}), composite "
            f"{_pct(alt_scores.get('composite'), 2)}")

    log(f"✓ rendu terminé : {len(written)} page(s) écrite(s) dans "
        f"{PAGE_DIR.relative_to(REPO_ROOT)}"
        + (f", {len(skipped)} sans trace (V{', V'.join(map(str, skipped))})" if skipped else ""))

    if summary:
        base_g = (base_arm.get("variants") or {})["attendu"]["global"]
        c_base = ((base_arm["variants"]["attendu"]["scores"].get("emd_jsd") or {})
                  .get("composite"))
        # La colonne VOITURE n'est pas décorative : la masse retirée aux transports
        # collectifs ne va pas forcément à la marche. Sans elle, un bras qui déplace
        # l'excédent d'un canal à l'autre — le « gaming de la distribution » de la
        # campagne ref1 — se lit comme un succès.
        print("\n── Les dix bras, lus contre le run ─────────────────────────────────────")
        print(f"{'':<5}{'variante':<16}{'compo':>8}{'Δ':>7}"
              f"{'marche':>8}{'TC':>7}{'voit.':>7}{'  │':>3}"
              f"{'marche':>8}{'TC':>7}{'voit.':>7}{'  couv.':>8}")
        print(f"{'':<5}{'':<16}{'':>8}{'':>7}{'——— global ———':>22}{'  │':>3}"
              f"{'——— sous-jeu ———':>22}")
        print(f"{'run':<5}{'(inchangé)':<16}{_pct(c_base, 2):>8}{'—':>7}"
              f"{_pct(base_g['actual']['marche']):>8}"
              f"{_pct(base_g['actual']['transports_collectifs']):>7}"
              f"{_pct(base_g['actual']['voiture']):>7}{'  │':>3}"
              f"{_pct(before['marche']):>8}{_pct(before['transports_collectifs']):>7}"
              f"{_pct(before['voiture']):>7}{'—':>8}")
        for s in sorted(summary, key=lambda r: -(r["marche_sousjeu"] or 0)):
            delta = (None if (c_base is None or s["composite"] is None)
                     else s["composite"] - c_base)
            print(f"V{s['id']:<4}{s['slug']:<16}{_pct(s['composite'], 2):>8}"
                  f"{_signed(delta, 2):>7}{_pct(s['marche_global']):>8}"
                  f"{_pct(s['tc_global']):>7}{_pct(s['voiture_global']):>7}{'  │':>3}"
                  f"{_pct(s['marche_sousjeu']):>8}{_pct(s['tc_sousjeu']):>7}"
                  f"{_pct(s['voiture_sousjeu']):>7}{100 * s['coverage']:>7.0f}%")
        print(f"\nCible EMC² 2023 : marche {_pct(base_g['target'].get('marche'))} %, "
              f"TC {_pct(base_g['target'].get('transports_collectifs'))} %, "
              f"voiture {_pct(base_g['target'].get('voiture'))} %. "
              f"Composite : plus bas = plus proche de l'enquête.")
        print("⚠ Sans bras témoin, ces Δ mélangent l'effet du prompt et celui du "
              "changement de modèle (cf. docs/arch/report-marche-tc.md, §5).")

    return 1 if skipped and not written else 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sub = sub.add_parser("subset", help="sélectionner le sous-jeu (aucun appel LLM)")
    p_sub.set_defaults(func=cmd_subset)

    p_rep = sub.add_parser("replay", help="rejouer le sous-jeu sous les variantes")
    p_rep.add_argument("--variants", type=lambda s: [int(x) for x in s.split(",")],
                       default=None, help="ex. 1,4,10 (défaut : les dix)")
    p_rep.add_argument("--dry-run", action="store_true", help="plan d'appels, sans appel")
    p_rep.add_argument("--force", action="store_true",
                       help="re-payer un bras dont la trace existe déjà")
    p_rep.set_defaults(func=cmd_replay)

    p_ren = sub.add_parser("render", help="écrire les pages depuis les traces")
    p_ren.add_argument("--variants", type=lambda s: [int(x) for x in s.split(",")],
                       default=None)
    p_ren.set_defaults(func=cmd_render)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
