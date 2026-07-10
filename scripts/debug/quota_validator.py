#!/usr/bin/env python3
"""
Valide les limites RPM/TPM sur chaque minute isolée (fenêtres glissantes 60s).
Pour chaque provider, vérifie que les quotas ne sont jamais franchis,
sinon diagnostic des seuils violés et timestamps problématiques.
Inclut aussi comptage des cooldowns (erreurs 5xx/429).
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

# Providers configuration
PROVIDERS_CONFIG = {
    "google_gemini31": {"rpm_limit": 15, "tpm_limit": 250000},
    "google_gemma42": {"rpm_limit": 15, "tpm_limit": float('inf')},
    "google_gemma43": {"rpm_limit": 15, "tpm_limit": float('inf')},
    "groq_llama3": {"rpm_limit": 30, "tpm_limit": 12000},
    "groq_llama4": {"rpm_limit": 30, "tpm_limit": 30000},
    "groq_qwen": {"rpm_limit": 2, "tpm_limit": 6000},
    "groq_llama31": {"rpm_limit": 2, "tpm_limit": 6000},
    "groq_openai_120": {"rpm_limit": 30, "tpm_limit": 8000},
    "groq_openai_20": {"rpm_limit": 30, "tpm_limit": 8000},
    "cerebras_gpt-oss-120b": {"rpm_limit": 5, "tpm_limit": 30000},
    "cerebras_zai-glm-4.7": {"rpm_limit": 5, "tpm_limit": 30000},
    "openai": {"rpm_limit": 15, "tpm_limit": 200000},
    "mistral": {"rpm_limit": 90, "tpm_limit": 500000},
}


def parse_timestamp(ts_str):
    """Parse ISO format timestamp."""
    try:
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        return datetime.fromisoformat(ts_str)
    except:
        return None


def load_llm_exchanges(run_dir):
    """Load llm_exchanges.jsonl from run directory (supports pretty-printed JSON)."""
    log_file = Path(run_dir) / "llm_exchanges.jsonl"
    if not log_file.exists():
        print(f"❌ Fichier non trouvé: {log_file}")
        return []

    exchanges = []
    with open(log_file, "r") as f:
        content = f.read()

    # Parse multi-line JSON objects
    current_obj = ""
    depth = 0

    for char in content:
        current_obj += char
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(current_obj.strip())
                    exchanges.append(obj)
                except json.JSONDecodeError:
                    pass
                current_obj = ""

    return exchanges


def count_cooldowns(exchanges):
    """Compte les cooldowns par provider (erreurs 5xx et 429 qui déclenchent disable_timeout)."""
    cooldowns = defaultdict(int)

    for exchange in exchanges:
        provider = exchange.get("provider")
        if not provider:
            continue

        # Un cooldown est déclenché par une erreur HTTP
        error = exchange.get("error") or exchange.get("error_message")
        status = exchange.get("http_status")

        # Cooldown sur 5xx (erreurs serveur) et 429 (rate limit)
        if error and any(code in str(error) for code in ["500", "503", "429"]):
            cooldowns[provider] += 1
        elif status and str(status) in ["429", "500", "503"]:
            cooldowns[provider] += 1

    return dict(cooldowns)


def calculate_batch_metrics(exchanges, provider):
    """Calcule les statistiques de batching pour un provider."""
    provider_exchanges = [
        e for e in exchanges
        if e.get("provider") == provider and e.get("tokens_in") is not None
    ]

    if not provider_exchanges:
        return None

    # Grouper par task_id (batch)
    batches = {}
    for ex in provider_exchanges:
        task_id = ex.get("task_id", "unknown")
        if task_id not in batches:
            batches[task_id] = []
        batches[task_id].append(ex)

    batch_sizes = [len(batch) for batch in batches.values()]

    if not batch_sizes:
        return None

    return {
        "batch_count": len(batches),
        "total_exchanges": len(provider_exchanges),
        "batch_min": min(batch_sizes),
        "batch_max": max(batch_sizes),
        "batch_mean": statistics.mean(batch_sizes),
        "batch_median": statistics.median(batch_sizes),
        "utilization": (len(provider_exchanges) / len(batches)) if len(batches) > 0 else 0,
    }


def calculate_sliding_window_metrics(exchanges, provider, window_seconds=60):
    """
    Calcule les métriques RPM/TPM sur des fenêtres glissantes de 60s.
    Retourne: (violations, metrics_by_minute)
    """
    config = PROVIDERS_CONFIG.get(provider, {"rpm_limit": float('inf'), "tpm_limit": float('inf')})
    rpm_limit = config["rpm_limit"]
    tpm_limit = config["tpm_limit"]

    # Filtrer les échanges pour ce provider
    provider_exchanges = [
        e for e in exchanges
        if e.get("provider") == provider and e.get("tokens_in") is not None
    ]

    if not provider_exchanges:
        return [], {}

    # Trier par timestamp
    provider_exchanges.sort(key=lambda x: x.get("time", ""))

    violations = []
    metrics_by_minute = {}

    # Créer une timeline complète
    timestamps = [parse_timestamp(e.get("time", "")) for e in provider_exchanges]
    timestamps = [t for t in timestamps if t]

    if not timestamps:
        return [], {}

    min_time = timestamps[0]
    max_time = timestamps[-1]

    # Fenêtres de 1 minute (minute entière)
    current_time = min_time.replace(second=0, microsecond=0)

    while current_time <= max_time:
        window_start = current_time
        window_end = current_time + timedelta(seconds=59, microseconds=999999)

        # Récupérer tous les échanges dans cette fenêtre
        window_exchanges = [
            e for e, ts in zip(provider_exchanges, timestamps)
            if window_start <= ts <= window_end
        ]

        if window_exchanges:
            rpm_count = len(window_exchanges)
            tpm_count = sum(e.get("tokens_in", 0) + e.get("tokens_out", 0) for e in window_exchanges)

            minute_key = window_start.strftime("%Y-%m-%d %H:%M")
            metrics_by_minute[minute_key] = {
                "rpm": rpm_count,
                "tpm": tpm_count,
                "rpm_limit": rpm_limit,
                "tpm_limit": tpm_limit,
                "exchanges": len(window_exchanges),
                "timestamp": window_start.isoformat(),
            }

            # Détection de violations
            if rpm_count > rpm_limit:
                violations.append({
                    "type": "RPM",
                    "minute": minute_key,
                    "value": rpm_count,
                    "limit": rpm_limit,
                    "excess": rpm_count - rpm_limit,
                })

            if tpm_limit != float('inf') and tpm_count > tpm_limit:
                violations.append({
                    "type": "TPM",
                    "minute": minute_key,
                    "value": tpm_count,
                    "limit": tpm_limit,
                    "excess": tpm_count - tpm_limit,
                })

        current_time += timedelta(minutes=1)

    return violations, metrics_by_minute


def generate_report(run_dir):
    """Génère le rapport de validation des quotas."""
    print("=" * 90)
    print("📊 VALIDATION DES QUOTAS RPM/TPM (fenêtres glissantes 60s)")
    print("=" * 90)

    exchanges = load_llm_exchanges(run_dir)

    if not exchanges:
        print("❌ Aucun échange LLM trouvé")
        return

    print(f"✅ {len(exchanges)} échanges LLM chargés\n")

    # Grouper par provider
    providers_in_log = set(e.get("provider") for e in exchanges if e.get("provider"))
    print(f"Providers dans les logs: {sorted(providers_in_log)}\n")

    # Compter les cooldowns
    cooldowns = count_cooldowns(exchanges)
    total_cooldowns = sum(cooldowns.values())
    if total_cooldowns > 0:
        print(f"⚠️  Cooldowns détectés: {total_cooldowns} total")
        for provider, count in sorted(cooldowns.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                print(f"   {provider}: {count}")
        print()

    all_violations = {}
    all_metrics = {}

    for provider in sorted(providers_in_log):
        if provider not in PROVIDERS_CONFIG:
            continue

        violations, metrics = calculate_sliding_window_metrics(exchanges, provider)
        all_violations[provider] = violations
        all_metrics[provider] = metrics

        config = PROVIDERS_CONFIG[provider]
        rpm_limit = config["rpm_limit"]
        tpm_limit = config["tpm_limit"]

        print(f"\n{'='*90}")
        print(f"🔹 Provider: {provider}")
        print(f"   Limites: RPM={rpm_limit}, TPM={'∞' if tpm_limit == float('inf') else tpm_limit}")

        if not metrics:
            print(f"   ⚠️  Aucun échange")
            continue

        # Stats
        rpm_values = [m["rpm"] for m in metrics.values()]
        tpm_values = [m["tpm"] for m in metrics.values()]

        print(f"\n   Statistiques RPM (requêtes/minute):")
        print(f"     • Min: {min(rpm_values)}, Max: {max(rpm_values)}, Moy: {statistics.mean(rpm_values):.1f}")

        print(f"\n   Statistiques TPM (tokens/minute):")
        if tpm_limit == float('inf'):
            print(f"     • Min: {min(tpm_values)}, Max: {max(tpm_values)}, Moy: {statistics.mean(tpm_values):.1f}")
            print(f"     • Quota illimité (pas de plafond TPM)")
        else:
            print(f"     • Min: {min(tpm_values)}, Max: {max(tpm_values)}, Moy: {statistics.mean(tpm_values):.1f}")

        if cooldowns.get(provider, 0) > 0:
            print(f"\n   ⚠️  Cooldowns: {cooldowns[provider]} (provider écartée {cooldowns[provider]}x)")

        if violations:
            print(f"\n   🚨 VIOLATIONS DÉTECTÉES: {len(violations)}")

            for v in violations[:5]:  # Top 5
                print(f"     • {v['type']:3s} @ {v['minute']}: {v['value']:5d} / {v['limit']:5d} (excess: +{v['excess']})")

            if len(violations) > 5:
                print(f"     ... et {len(violations) - 5} autres violations")
        else:
            print(f"   ✅ AUCUNE VIOLATION (quotas respectés)")

    # Tableau récapitulatif complet
    print(f"\n{'='*90}")
    print("📊 TABLEAU RÉCAPITULATIF - TOUS LES PROVIDERS")
    print(f"{'='*90}\n")

    # Préparer les données
    table_data = []
    for provider in sorted(providers_in_log):
        if provider not in PROVIDERS_CONFIG:
            continue

        config = PROVIDERS_CONFIG[provider]
        rpm_limit = config["rpm_limit"]
        tpm_limit = config["tpm_limit"]
        metrics = all_metrics.get(provider, {})
        violations = all_violations.get(provider, [])
        batch_metrics = calculate_batch_metrics(exchanges, provider)

        if not metrics:
            table_data.append({
                "provider": provider,
                "rpm_max": 0,
                "tpm_max": 0,
                "rpm_mean": 0,
                "tpm_mean": 0,
                "batch_count": 0,
                "batch_mean": 0,
                "cooldown_count": 0,
                "violations": "—",
            })
            continue

        rpm_values = [m["rpm"] for m in metrics.values()]
        tpm_values = [m["tpm"] for m in metrics.values()]

        rpm_max = max(rpm_values)
        tpm_max = max(tpm_values)
        rpm_mean = statistics.mean(rpm_values)
        tpm_mean = statistics.mean(tpm_values)

        batch_count = batch_metrics.get("batch_count", 0) if batch_metrics else 0
        batch_mean = batch_metrics.get("batch_mean", 0) if batch_metrics else 0

        violation_str = "✅" if not violations else f"🚨 {len(violations)}"
        cooldown_count = cooldowns.get(provider, 0)

        table_data.append({
            "provider": provider,
            "rpm_max": rpm_max,
            "rpm_limit": rpm_limit,
            "tpm_max": tpm_max,
            "tpm_limit": tpm_limit,
            "rpm_mean": rpm_mean,
            "tpm_mean": tpm_mean,
            "batch_count": batch_count,
            "batch_mean": batch_mean,
            "cooldown_count": cooldown_count,
            "violations": violation_str,
        })

    # Afficher le tableau
    print(f"{'Provider':<25} {'RPM':<16} {'TPM':<20} {'Batch':<12} {'Cooldown':<12} {'Violations':<12}")
    print(f"{'':<25} {'Max/L/Moy':<16} {'Max/L/Moy':<20} {'Nbre/Moy':<12} {'':<12} {'':<12}")
    print("─" * 127)

    for row in table_data:
        provider = row["provider"][:24]

        rpm_info = f"{row['rpm_max']}/{row['rpm_limit']}/{row['rpm_mean']:.1f}"

        if row["tpm_limit"] == float('inf'):
            tpm_info = f"{row['tpm_max']}/∞/{row['tpm_mean']:.0f}"
        else:
            tpm_info = f"{row['tpm_max']}/{row['tpm_limit']}/{row['tpm_mean']:.0f}"

        batch_info = f"{row['batch_count']}/{row['batch_mean']:.1f}"
        cooldown_info = f"{row['cooldown_count']}" if row['cooldown_count'] > 0 else "—"
        violations_str = row["violations"]

        print(f"{provider:<25} {rpm_info:<16} {tpm_info:<20} {batch_info:<12} {cooldown_info:<12} {violations_str:<12}")

    print()

    # Résumé global
    print(f"\n{'='*90}")
    print("📋 RÉSUMÉ GLOBAL")
    print(f"{'='*90}")

    total_violations = sum(len(v) for v in all_violations.values())
    providers_violated = [p for p, v in all_violations.items() if v]

    if total_violations == 0:
        print("✅ SUCCÈS: Aucune violation de quota détectée")
    else:
        print(f"🚨 ALERTE: {total_violations} violations détectées")

    if total_cooldowns > 0:
        print(f"⚠️  {total_cooldowns} cooldowns detectés (errors 5xx/429)")

    print()


if __name__ == "__main__":
    run_dir = sys.argv[1] if len(sys.argv) > 1 else "experiments/current"
    generate_report(run_dir)
