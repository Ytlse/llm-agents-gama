#!/usr/bin/env python3
"""
run_report.py — Rapport de santé « agent-ready » du dernier run.

Agrège en un seul artefact markdown dense les signaux essentiels au debug
d'un run (par défaut `experiments/current/`) :

  - erreurs / warnings de app.log (normalisés, top-N)
  - santé LLM : erreurs par provider × http_status, taux de 429, tokens
  - latence pipeline (percentiles) + détection de backlog
  - activité des agents (inactifs dans le temps)
  - décisions : distribution modale, méthodes de sélection, fallbacks
  - arrivées : timeouts, retards de départ
  - ALARMES : anomalies dérivées avec seuils

Usage :
    python3 scripts/debug/run_report.py [RUN_DIR] [--top N] [--out FICHIER]

RUN_DIR par défaut : experiments/current (résolu depuis la racine du repo).
Sans --out, le rapport est écrit sur stdout.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

# ── Seuils d'ALARME (ajustables) ────────────────────────────────────────────
TH_PIPELINE_P95_S = 300.0       # latence pipeline p95 au-delà → backlog
TH_RATE_LIMIT_SHARE = 0.30      # part de 429 dans les erreurs LLM → saturation
TH_FALLBACK_SHARE = 0.05        # part de décisions en fallback LLM → qualité dégradée
TH_INACTIVE_FINAL_SHARE = 0.20  # part d'agents inactifs en fin de run → agents bloqués
TH_MISSED_ACTIVITY_SHARE = 0.05 # part d'activités attendues non exécutées un jour donné
SIM_DAY_SECONDS = 86400
TOP_DEFAULT = 12

# ── Normalisation des messages (repris de scripts/errors.py) ────────────────
_NORMALIZE = [
    (re.compile(r"\btask_id=[0-9a-f-]{36}\b"), ""),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"), "{uuid}"),
    (re.compile(r"\[timestamp:[^\]]+\]"), ""),
    (re.compile(r"\blon=-?[\d.]+\s+lat=-?[\d.]+"), ""),
    (re.compile(r"from=\(-?[\d.]+,-?[\d.]+\)\s+to=\(-?[\d.]+,-?[\d.]+\)"), ""),
    (re.compile(r"\(\d+,\)\s+\(\d+,\)"), "({n},) ({m},)"),
    (re.compile(r"\b(waited|timeout)=[\d.]+s\b"), ""),
    (re.compile(r"\bpublic_transport=(True|False)\b"), ""),
    (re.compile(r"\bpour \d+:"), "pour {id}:"),
    (re.compile(r"\bperson \d+\b"), "person {id}"),
    (re.compile(r"\bfor \d+\b"), "for {id}"),
    (re.compile(r"\bto \d+\b"), "to {id}"),
    (re.compile(r"\b\d{4,}\b"), "{n}"),
    (re.compile(r"  +"), " "),
]
_LOG_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| (\w+)\s+\| (.+)$")


def _normalize(msg: str) -> str:
    for pattern, replacement in _NORMALIZE:
        msg = pattern.sub(replacement, msg)
    return msg.strip().rstrip("|").strip()


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, int(len(s) * q))
    return s[idx]


def _fmt_dur(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def _iter_jsonl(path: Path):
    """Yield objets d'un JSONL (une ligne = un objet)."""
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _iter_json_concat(path: Path):
    """Yield objets d'un fichier de JSON concaténés/pretty-printed (llm_exchanges)."""
    buf = ""
    with path.open(encoding="utf-8") as f:
        for line in f:
            buf += line
            try:
                yield json.loads(buf)
                buf = ""
            except json.JSONDecodeError:
                continue


# ── Sections du rapport ─────────────────────────────────────────────────────

def section_meta(run: Path, out: list[str], alarms: list[str]) -> None:
    out.append(f"# 🩺 Rapport de run — `{run.name}`\n")
    out.append(f"_Généré {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · dossier `{run}`_\n")

    params = {}
    for name in ("scenario_params.yaml",):
        p = run / name
        if p.exists():
            for line in p.read_text().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    params[k.strip()] = v.strip()

    meta = []
    if params:
        pop = params.get("population_size", "?")
        agents = params.get("number_of_llm_based_agents", "?")
        ltm = params.get("long_term_memory_enabled", "?")
        meta.append(f"- Population : **{pop}** · agents LLM : **{agents}** · LTM : {ltm}")

    # Durée simulée (via moves.csv "Temps simulé") + durée mur (via app.log)
    out.append("\n".join(meta) + "\n" if meta else "")


def _discover_logs(run: Path) -> list[Path]:
    """Fichiers `*.log` à la racine du run (un par service : app, api, worker, …).

    On exclut gama_results/ (controller.log y duplique app.log), les archives .bak et
    les fichiers de rotation loguru (`worker.<timestamp>.log`, dont le stem contient un
    point). app.log (controller) est présenté en premier s'il existe.
    """
    logs = sorted(
        p for p in run.glob("*.log")
        if p.is_file() and "." not in p.stem  # exclut les artefacts de rotation
    )
    logs.sort(key=lambda p: (p.name != "app.log", p.name))
    return logs


def section_logs(run: Path, out: list[str], alarms: list[str], top: int) -> None:
    logs = _discover_logs(run)
    if not logs:
        out.append("## 📜 Logs\n_Aucun fichier .log dans le run._\n")
        return

    # Compteurs combinés (tous services) + totaux par service pour l'en-tête.
    counts = {"ERROR": Counter(), "WARNING": Counter()}
    per_service: dict[str, Counter] = {}
    first_ts = last_ts = None

    for log in logs:
        service = log.stem  # app, api, worker, …
        stotals = per_service.setdefault(service, Counter())
        with log.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                m = _LOG_RE.match(line.rstrip())
                if not m:
                    continue
                level, msg = m.group(1), m.group(2)
                stotals[level] += 1
                ts = line[:19]
                if first_ts is None or ts < first_ts:
                    first_ts = ts
                if last_ts is None or ts > last_ts:
                    last_ts = ts
                if level in counts:
                    # Tag [service] pour tracer l'origine dans le top combiné.
                    counts[level][f"[{service}] {_normalize(msg)}"] += 1

    dur = ""
    if first_ts and last_ts:
        try:
            t0 = datetime.strptime(first_ts, "%Y-%m-%d %H:%M:%S")
            t1 = datetime.strptime(last_ts, "%Y-%m-%d %H:%M:%S")
            if t1 > t0:
                dur = f" · durée mur **{_fmt_dur((t1 - t0).total_seconds())}**"
        except ValueError:
            pass

    services = ", ".join(f"`{s}.log`" for s in per_service)
    out.append(f"## 📜 Logs — {len(logs)} service(s) : {services}{dur}\n")
    out.append("| Service | ERROR | WARNING | INFO |")
    out.append("|:--|--:|--:|--:|")
    for service, st in per_service.items():
        out.append(f"| {service} | {st['ERROR']} | {st['WARNING']} | {st['INFO']} |")

    for level, emoji in (("ERROR", "🔴"), ("WARNING", "🟠")):
        c = counts[level]
        if not c:
            continue
        out.append(f"\n### {emoji} Top {level} (normalisés, tous services)\n")
        out.append(f"| # | Source · {level.title()} |")
        out.append("|--:|:--|")
        for msg, n in c.most_common(top):
            out.append(f"| {n} | {msg[:150]} |")
        out.append(f"\n_{sum(c.values())} occurrences, {len(c)} types distincts._\n")


def section_llm(run: Path, out: list[str], alarms: list[str], top: int) -> None:
    errors_path = run / "llm_errors.jsonl"
    out.append("\n## 🤖 Santé LLM\n")

    by_provider = Counter()
    by_status = Counter()
    by_sig = Counter()
    total_err = 0
    rate_limited = 0
    if errors_path.exists():
        for o in _iter_jsonl(errors_path):
            total_err += 1
            prov = o.get("provider", "?")
            status = o.get("http_status")
            by_provider[prov] += 1
            by_status[str(status)] += 1
            if status == 429:
                rate_limited += 1
            by_sig[(prov, str(status), str(o.get("error_type", ""))[:44])] += 1

        share_429 = rate_limited / total_err if total_err else 0.0
        out.append(
            f"**{total_err} erreurs LLM** · dont **{rate_limited} rate-limit (429)** "
            f"({share_429:.0%})\n"
        )
        if total_err and share_429 >= TH_RATE_LIMIT_SHARE:
            alarms.append(
                f"🔴 Saturation LLM : {share_429:.0%} des erreurs sont des 429 "
                f"(demande > capacité providers)."
            )

        out.append("\n**Erreurs par provider** · **par statut HTTP**\n")
        out.append("| Provider | Err | | HTTP | Err |")
        out.append("|:--|--:|--|:--|--:|")
        prov_rows = by_provider.most_common()
        stat_rows = by_status.most_common()
        for i in range(max(len(prov_rows), len(stat_rows))):
            pl = f"{prov_rows[i][0]} | {prov_rows[i][1]}" if i < len(prov_rows) else " | "
            sl = f"{stat_rows[i][0]} | {stat_rows[i][1]}" if i < len(stat_rows) else " | "
            out.append(f"| {pl} | | {sl} |")

        out.append("\n**Top signatures d'erreur**\n")
        out.append("| # | Provider | HTTP | Type |")
        out.append("|--:|:--|:--|:--|")
        for (prov, status, etype), n in by_sig.most_common(top):
            out.append(f"| {n} | {prov} | {status} | {etype} |")
    else:
        out.append("_llm_errors.jsonl absent._\n")

    # Cache & débit d'échanges
    hits_path = run / "llm_cache_hits.jsonl"
    exch_path = run / "llm_exchanges.jsonl"
    n_hits = sum(1 for _ in _iter_jsonl(hits_path)) if hits_path.exists() else 0
    n_exch = 0
    tok_in = tok_out = 0
    prov_calls = Counter()
    exch_times: list[datetime] = []
    if exch_path.exists():
        for o in _iter_json_concat(exch_path):
            n_exch += 1
            tok_in += int(o.get("tokens_in") or 0)
            tok_out += int(o.get("tokens_out") or 0)
            prov_calls[o.get("provider", "?")] += 1
            t = o.get("time")
            if t:
                try:
                    exch_times.append(datetime.fromisoformat(t))
                except ValueError:
                    pass

    total_decisions = n_hits + n_exch
    hit_rate = n_hits / total_decisions if total_decisions else 0.0
    out.append(
        f"\n**Cache** : {n_hits} hits / {total_decisions} décisions → "
        f"**{hit_rate:.0%} hit rate**\n"
    )
    if n_exch:
        rate_line = ""
        if len(exch_times) >= 2:
            span_min = (max(exch_times) - min(exch_times)).total_seconds() / 60
            if span_min > 0:
                rate_line = f" · débit moyen **{n_exch / span_min:.0f} req/min** (mur)"
        out.append(
            f"**Appels LLM** : {n_exch} échanges · "
            f"{tok_in:,} tokens_in · {tok_out:,} tokens_out{rate_line}\n"
        )


def section_pipeline(run: Path, out: list[str], alarms: list[str]) -> None:
    path = run / "pipeline_timing.csv"
    if not path.exists():
        return
    lat = []
    retries = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                t0 = float(row["T0"])
                tf = float(row["T_fin"])
                if tf > t0:
                    lat.append(tf - t0)
            except (ValueError, KeyError, TypeError):
                pass
            try:
                retries.append(int(row.get("P5_llm_retries") or 0))
            except ValueError:
                pass

    if not lat:
        return
    p50, p95, mx = _pct(lat, 0.50), _pct(lat, 0.95), max(lat)
    out.append("\n## ⏱️ Latence pipeline (bout-en-bout, T0→T_fin)\n")
    out.append(
        f"n={len(lat)} · p50 **{p50:.0f}s** · p95 **{p95:.0f}s** · max **{mx:.0f}s**"
    )
    if retries:
        r_total = sum(1 for r in retries if r > 0)
        out.append(f" · retries LLM sur {r_total} tâches")
    out.append("\n")
    if p95 >= TH_PIPELINE_P95_S:
        alarms.append(
            f"🔴 Backlog pipeline : latence p95 = {p95:.0f}s "
            f"(> {TH_PIPELINE_P95_S:.0f}s) — la file de planif s'accumule."
        )


def section_agents(run: Path, out: list[str], alarms: list[str]) -> None:
    path = run / "gama_results" / "agent_states.csv"
    if not path.exists():
        return
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    if not rows:
        return

    def _i(r, k):
        try:
            return int(r[k])
        except (ValueError, KeyError, TypeError):
            return 0

    first, last = rows[0], rows[-1]
    peak_inactive = max(_i(r, "inactive") for r in rows)
    total = _i(last, "total") or 1
    final_inactive = _i(last, "inactive")
    out.append("\n## 👥 Activité des agents\n")
    out.append(
        f"{len(rows)} steps ({first.get('sim_time', '?')} → {last.get('sim_time', '?')}) · "
        f"total {total} · inactifs : début {_i(first, 'inactive')}, "
        f"pic {peak_inactive}, fin **{final_inactive}** "
        f"({final_inactive / total:.0%})\n"
    )
    if final_inactive / total >= TH_INACTIVE_FINAL_SHARE:
        alarms.append(
            f"🟠 {final_inactive}/{total} agents ({final_inactive / total:.0%}) "
            f"encore inactifs en fin de run — vérifier planifs non abouties."
        )


def section_decisions(run: Path, out: list[str], alarms: list[str]) -> None:
    path = run / "moves.csv"
    if not path.exists():
        return
    modes = Counter()
    methods = Counter()
    total = 0
    fallbacks = 0
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            total += 1
            modes[row.get("Mode de transport Choisi", "?")] += 1
            method = row.get("Méthode de sélection", "?")
            methods[method] += 1
            if "Error" in method or "Default" in method:
                fallbacks += 1
    if not total:
        return
    # Ratio « erreur définitive LLM » : fallbacks rapportés aux seules décisions
    # passées par le LLM (choix réel + fallback), pas aux mono-choix/no-move.
    llm_decisions = methods.get("LLM", 0) + fallbacks
    llm_fallback_share = fallbacks / llm_decisions if llm_decisions else 0.0
    out.append("\n## 🧭 Décisions de mobilité\n")
    out.append(
        f"{total} trajets · fallback LLM : **{fallbacks}** ({fallbacks / total:.1%} des trajets, "
        f"{llm_fallback_share:.1%} des {llm_decisions} décisions LLM)\n"
    )
    out.append("\n**Modes** · **Méthodes de sélection**\n")
    out.append("| Mode | n | | Méthode | n |")
    out.append("|:--|--:|--|:--|--:|")
    ml = modes.most_common()
    sl = methods.most_common()
    for i in range(max(len(ml), len(sl))):
        left = f"{ml[i][0]} | {ml[i][1]}" if i < len(ml) else " | "
        right = f"{sl[i][0][:32]} | {sl[i][1]}" if i < len(sl) else " | "
        out.append(f"| {left} | | {right} |")
    if fallbacks / total >= TH_FALLBACK_SHARE:
        alarms.append(
            f"🟠 {fallbacks}/{total} décisions ({fallbacks / total:.1%}) en fallback "
            f"(LLM KO → index par défaut) — qualité de planif dégradée."
        )
    if llm_decisions and llm_fallback_share >= TH_FALLBACK_SHARE:
        alarms.append(
            f"🟠 {fallbacks}/{llm_decisions} décisions LLM ({llm_fallback_share:.1%}) retombées "
            f"sur l'index par défaut (erreur définitive LLM) — vérifier providers et cache."
        )


def _is_llm_fallback(method: str) -> bool:
    """Décision retombée sur l'index par défaut faute de réponse LLM."""
    return "Error" in method or "Default" in method


def section_activity_coverage(run: Path, out: list[str], alarms: list[str]) -> None:
    """Couverture des activités par jour simulé.

    Les activités sont récurrentes et non datées : on vérifie que CHAQUE activité
    d'un agent s'exécute CHAQUE jour de sa plage d'activité. Deux façons de « rater »
    une activité :
      - dégradée : décidée sans réponse LLM (fallback → index par défaut) ;
      - manquée  : aucune exécution ce jour-là (agent bloqué / planif non aboutie).

    L'univers d'activités d'un agent = ensemble des ID d'activité vus pour lui sur
    tout le run ; « manquée » = activité de l'univers absente un jour de sa plage.
    """
    path = run / "moves.csv"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        if not {"ID Personne", "ID Activité", "Temps simulé"} <= set(cols):
            out.append("\n## 🎯 Couverture des activités\n")
            out.append(
                "_Indisponible : nécessite les colonnes `ID Personne` / `ID Activité` / "
                "`Temps simulé` du move-log (runs récents uniquement)._\n"
            )
            return
        # (person, day) → set d'activités exécutées ; (person,day) → fallbacks
        executed: dict[tuple[str, int], set[str]] = {}
        fallback_exec: dict[tuple[str, int], set[str]] = {}
        universe: dict[str, set[str]] = {}
        person_days: dict[str, set[int]] = {}
        per_day_total: Counter = Counter()
        per_day_fallback: Counter = Counter()
        for row in reader:
            person = (row.get("ID Personne") or "").strip()
            activity = (row.get("ID Activité") or "").strip()
            if not person or not activity:
                continue
            try:
                day = int(float(row["Temps simulé"])) // SIM_DAY_SECONDS
            except (ValueError, KeyError, TypeError):
                continue
            method = row.get("Méthode de sélection", "?")
            executed.setdefault((person, day), set()).add(activity)
            universe.setdefault(person, set()).add(activity)
            person_days.setdefault(person, set()).add(day)
            per_day_total[day] += 1
            if _is_llm_fallback(method):
                per_day_fallback[day] += 1
                fallback_exec.setdefault((person, day), set()).add(activity)

    if not per_day_total:
        return

    # Activités manquées : pour chaque agent, sur sa plage de jours [min, max],
    # activités de l'univers absentes un jour donné.
    per_day_expected: Counter = Counter()
    per_day_missed: Counter = Counter()
    for person, acts in universe.items():
        days = person_days[person]
        span = range(min(days), max(days) + 1)
        for day in span:
            per_day_expected[day] += len(acts)
            done = executed.get((person, day), set())
            per_day_missed[day] += len(acts - done)

    tot_expected = sum(per_day_expected.values())
    tot_missed = sum(per_day_missed.values())
    tot_decisions = sum(per_day_total.values())
    tot_fallback = sum(per_day_fallback.values())

    out.append("\n## 🎯 Couverture des activités (par jour simulé)\n")
    out.append(
        f"{tot_decisions} exécutions · dégradées (sans LLM) **{tot_fallback}** "
        f"({tot_fallback / tot_decisions:.1%}) · attendues {tot_expected} · "
        f"manquées **{tot_missed}** ({tot_missed / tot_expected:.1%} des attendues)"
        if tot_expected else f"{tot_decisions} exécutions · dégradées {tot_fallback}"
    )
    out.append("\n| Jour | Exécutées | Sans LLM (fallback) | Attendues | Manquées |")
    out.append("|--:|--:|--:|--:|--:|")
    for day in sorted(per_day_total):
        n = per_day_total[day]
        fb = per_day_fallback[day]
        exp = per_day_expected.get(day, 0)
        miss = per_day_missed.get(day, 0)
        fb_s = f"{fb} ({fb / n:.0%})" if n else str(fb)
        miss_s = f"{miss} ({miss / exp:.0%})" if exp else str(miss)
        out.append(f"| {day} | {n} | {fb_s} | {exp} | {miss_s} |")
    out.append("")

    if tot_decisions and tot_fallback / tot_decisions >= TH_FALLBACK_SHARE:
        alarms.append(
            f"🟠 {tot_fallback}/{tot_decisions} activités ({tot_fallback / tot_decisions:.1%}) "
            f"décidées sans réponse LLM (fallback index par défaut)."
        )
    if tot_expected and tot_missed / tot_expected >= TH_MISSED_ACTIVITY_SHARE:
        alarms.append(
            f"🟠 {tot_missed}/{tot_expected} activités-jours ({tot_missed / tot_expected:.1%}) "
            f"non exécutées (activité récurrente sautée un jour donné)."
        )


def section_arrivals(run: Path, out: list[str], alarms: list[str]) -> None:
    path = run / "gama_results" / "gama_arrivals.csv"
    if not path.exists():
        return
    total = 0
    timed_out = 0
    dep_delays = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            total += 1
            if str(row.get("timed_out", "")).strip().lower() == "true":
                timed_out += 1
            try:
                dep_delays.append(int(row["departure_delay_s"]))
            except (ValueError, KeyError, TypeError):
                pass
    if not total:
        return
    out.append("\n## 🚦 Arrivées\n")
    line = f"{total} arrivées · **{timed_out} timed_out** ({timed_out / total:.1%})"
    if dep_delays:
        line += (
            f" · retard départ p95 {_pct([float(d) for d in dep_delays], 0.95):.0f}s "
            f"max {max(dep_delays)}s"
        )
    out.append(line + "\n")
    if timed_out:
        alarms.append(
            f"🟠 {timed_out} trajets timed_out — planif non livrée avant l'échéance simulée."
        )


def section_alarms(out: list[str], alarms: list[str]) -> None:
    banner = ["\n## 🚨 ALARMES\n"]
    if not alarms:
        banner.append("_Aucune anomalie franchissant les seuils._\n")
    else:
        for a in alarms:
            banner.append(f"- {a}")
        banner.append("")
    # Insérer les alarmes juste après le titre (position 1)
    out[1:1] = banner


# ── Entrée ──────────────────────────────────────────────────────────────────

def resolve_run(arg: str | None) -> Path:
    if arg:
        return Path(arg).resolve()
    # Racine du repo = deux niveaux au-dessus de ce fichier (scripts/debug/)
    repo = Path(__file__).resolve().parents[2]
    return (repo / "experiments" / "current").resolve()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", nargs="?", help="Dossier du run (défaut experiments/current)")
    ap.add_argument("--top", type=int, default=TOP_DEFAULT, help="Nombre de lignes top-N")
    ap.add_argument("--out", help="Écrire le rapport dans ce fichier au lieu de stdout")
    args = ap.parse_args()

    run = resolve_run(args.run_dir)
    if not run.exists():
        print(f"❌ Dossier de run introuvable : {run}", file=sys.stderr)
        return 1

    out: list[str] = []
    alarms: list[str] = []

    section_meta(run, out, alarms)
    section_logs(run, out, alarms, args.top)
    section_llm(run, out, alarms, args.top)
    section_pipeline(run, out, alarms)
    section_agents(run, out, alarms)
    section_decisions(run, out, alarms)
    section_activity_coverage(run, out, alarms)
    section_arrivals(run, out, alarms)
    section_alarms(out, alarms)  # doit rester en dernier (insère en tête)

    report = "\n".join(out).rstrip() + "\n"
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"✅ Rapport écrit : {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
