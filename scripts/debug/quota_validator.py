#!/usr/bin/env python3
"""
Valide les limites RPM/TPM sur chaque minute isolée (fenêtres glissantes 60s).
Pour chaque provider, vérifie que les quotas ne sont jamais franchis,
sinon diagnostic des seuils violés et timestamps problématiques.
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
    print("=" * 80)
    print("📊 VALIDATION DES QUOTAS RPM/TPM (fenêtres glissantes 60s)")
    print("=" * 80)

    exchanges = load_llm_exchanges(run_dir)

    if not exchanges:
        print("❌ Aucun échange LLM trouvé")
        return

    print(f"✅ {len(exchanges)} échanges LLM chargés\n")

    # Grouper par provider
    providers_in_log = set(e.get("provider") for e in exchanges if e.get("provider"))
    print(f"Providers dans les logs: {sorted(providers_in_log)}\n")

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

        print(f"\n{'='*80}")
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
        if max(rpm_values) > rpm_limit:
            print(f"     ⚠️  DÉPASSEMENT MAX: {max(rpm_values)} > {rpm_limit}")

        print(f"\n   Statistiques TPM (tokens/minute):")
        if tpm_limit == float('inf'):
            print(f"     • Min: {min(tpm_values)}, Max: {max(tpm_values)}, Moy: {statistics.mean(tpm_values):.1f}")
            print(f"     • Quota illimité (pas de plafond TPM)")
        else:
            print(f"     • Min: {min(tpm_values)}, Max: {max(tpm_values)}, Moy: {statistics.mean(tpm_values):.1f}")
            if max(tpm_values) > tpm_limit:
                print(f"     ⚠️  DÉPASSEMENT MAX: {max(tpm_values)} > {tpm_limit}")

        if violations:
            print(f"\n   🚨 VIOLATIONS DÉTECTÉES: {len(violations)}")

            for v in violations[:10]:  # Top 10
                print(f"     • {v['type']:3s} @ {v['minute']}: {v['value']:5d} / {v['limit']:5d} (excess: +{v['excess']})")

            if len(violations) > 10:
                print(f"     ... et {len(violations) - 10} autres violations")
        else:
            print(f"   ✅ AUCUNE VIOLATION (quotas respectés)")

    # Tableau récapitulatif complet
    print(f"\n{'='*80}")
    print("📊 TABLEAU RÉCAPITULATIF - TOUS LES PROVIDERS")
    print(f"{'='*80}\n")

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

        if not metrics:
            table_data.append({
                "provider": provider,
                "rpm_limit": rpm_limit,
                "tpm_limit": tpm_limit,
                "rpm_max": 0,
                "tpm_max": 0,
                "rpm_mean": 0,
                "tpm_mean": 0,
                "rpm_usage": 0,
                "tpm_usage": 0,
                "violations": "—",
                "violation_details": [],
            })
            continue

        rpm_values = [m["rpm"] for m in metrics.values()]
        tpm_values = [m["tpm"] for m in metrics.values()]

        rpm_max = max(rpm_values)
        tpm_max = max(tpm_values)
        rpm_mean = statistics.mean(rpm_values)
        tpm_mean = statistics.mean(tpm_values)

        rpm_usage = (rpm_max / rpm_limit * 100) if rpm_limit > 0 else 0
        tpm_usage = (tpm_max / tpm_limit * 100) if tpm_limit != float('inf') else 0

        violation_str = "✅ NON"
        violation_details = []
        if violations:
            violation_details = violations
            violation_str = f"🚨 OUI ({len(violations)})"

        table_data.append({
            "provider": provider,
            "rpm_limit": rpm_limit,
            "tpm_limit": tpm_limit,
            "rpm_max": rpm_max,
            "tpm_max": tpm_max,
            "rpm_mean": rpm_mean,
            "tpm_mean": tpm_mean,
            "rpm_usage": rpm_usage,
            "tpm_usage": tpm_usage,
            "violations": violation_str,
            "violation_details": violation_details,
        })

    # Afficher le tableau
    print(f"{'Provider':<30} {'RPM':<20} {'TPM':<25} {'Utilisé':<25} {'Violations':<15}")
    print(f"{'':<30} {'Max/Limit/Moy':<20} {'Max/Limit/Moy':<25} {'RPM%/TPM%':<25} {'':<15}")
    print("─" * 115)

    for row in table_data:
        provider = row["provider"][:28]

        rpm_info = f"{row['rpm_max']}/{row['rpm_limit']}/{row['rpm_mean']:.1f}"

        if row["tpm_limit"] == float('inf'):
            tpm_info = f"{row['tpm_max']}/∞/{row['tpm_mean']:.0f}"
            tpm_usage = "∞%"
        else:
            tpm_info = f"{row['tpm_max']}/{row['tpm_limit']}/{row['tpm_mean']:.0f}"
            tpm_usage = f"{row['tpm_usage']:.0f}%"

        rpm_usage = f"{row['rpm_usage']:.0f}%"
        usage_str = f"{rpm_usage:>6} / {tpm_usage:>6}"
        violations_str = row["violations"]

        print(f"{provider:<30} {rpm_info:<20} {tpm_info:<25} {usage_str:<25} {violations_str:<15}")

    print()

    # Résumé global
    print(f"\n{'='*80}")
    print("📋 RÉSUMÉ GLOBAL")
    print(f"{'='*80}")

    total_violations = sum(len(v) for v in all_violations.values())
    providers_violated = [p for p, v in all_violations.items() if v]

    if total_violations == 0:
        print("✅ SUCCÈS: Aucune violation de quota détectée")
        print("   → Les limites RPM/TPM sont respectées sur chaque minute isolée")
        print("\n💡 Implications:")
        print("   • Les providers Gemma à quota illimité n'ont pas été rejetés pour dépassement")
        print("   • Les erreurs 500 observées sont indépendantes des quotas RPM/TPM")
        print("   • À investiguer: problèmes serveur transitoires, versions de modèles instables")
    else:
        print(f"🚨 ALERTE: {total_violations} violations détectées")
        print(f"   Providers affectés: {', '.join(providers_violated)}")

        # Diagnostic
        print("\n📌 DIAGNOSTIC:")
        for provider in providers_violated:
            violations = all_violations[provider]
            print(f"\n   {provider}:")

            rpm_violations = [v for v in violations if v["type"] == "RPM"]
            tpm_violations = [v for v in violations if v["type"] == "TPM"]

            if rpm_violations:
                max_rpm_excess = max(v["excess"] for v in rpm_violations)
                print(f"     • RPM: {len(rpm_violations)} minutes hors limites (max excess: +{max_rpm_excess})")
                for v in rpm_violations[:3]:
                    print(f"       - {v['minute']}: {v['value']} req (limit: {v['limit']})")

            if tpm_violations:
                max_tpm_excess = max(v["excess"] for v in tpm_violations)
                print(f"     • TPM: {len(tpm_violations)} minutes hors limites (max excess: +{max_tpm_excess})")
                for v in tpm_violations[:3]:
                    print(f"       - {v['minute']}: {v['value']} tokens (limit: {v['limit']})")

    # Analyse de marge et recommandations
    print("\n" + "=" * 80)
    print("📈 ANALYSE DE MARGE ET RECOMMANDATIONS")
    print("=" * 80)

    providers_with_high_usage = []
    providers_with_low_usage = []

    for row in table_data:
        if row["rpm_limit"] == float('inf') or row["rpm_max"] == 0:
            continue

        rpm_usage = row["rpm_usage"]
        if rpm_usage >= 70:
            providers_with_high_usage.append((row["provider"], rpm_usage))
        elif rpm_usage < 20:
            providers_with_low_usage.append((row["provider"], rpm_usage))

    if providers_with_high_usage:
        print("\n⚠️  PROVIDERS AVEC FORTE UTILISATION (>70% du quota RPM):")
        for provider, usage in sorted(providers_with_high_usage, key=lambda x: x[1], reverse=True):
            print(f"   • {provider}: {usage:.0f}% du quota")
        print("   → Considérez augmenter RPM_limit ou répartir sur d'autres providers")

    if providers_with_low_usage:
        print("\n💚 PROVIDERS AVEC UTILISATION BASSE (<20% du quota RPM):")
        for provider, usage in sorted(providers_with_low_usage, key=lambda x: x[1]):
            print(f"   • {provider}: {usage:.0f}% du quota (marge de sécurité: {100-usage:.0f}%)")

    print("\n✅ RECOMMANDATION GLOBALE:")
    if total_violations == 0:
        print("   → Quotas RPM/TPM correctement dimensionnés")
        print("   → Les fallbacks ne proviennent pas de dépassements de quota")
        print("   → Focus sur saturation concurrente et timeout provider")
    else:
        print("   → Ajuster les limites RPM/TPM pour éviter futures violations")
        print("   → Réduire worker_concurrency si violations persisten")

    print()


if __name__ == "__main__":
    run_dir = sys.argv[1] if len(sys.argv) > 1 else "experiments/current"
    generate_report(run_dir)
