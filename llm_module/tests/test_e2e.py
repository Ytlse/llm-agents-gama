"""
tests/test_e2e.py — Tests end-to-end contre l'API en local.

Lance l'API et le worker avant d'exécuter ce script :
  uvicorn llm_module.main:app --port 8000
  celery -A llm_module.worker.task_worker.celery_app worker --loglevel=info

Usage :
  python tests/test_e2e.py                  # tous les scénarios
  python tests/test_e2e.py --scenario 2     # un seul scénario
  python tests/test_e2e.py --provider mistral  # forcer un provider
"""

from __future__ import annotations
import argparse
import json
from collections import defaultdict
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import httpx

from llm_module.client import LLMClient

BASE_URL = "http://localhost:8000"
POLL_INTERVAL = 2.0   # secondes entre deux polls
POLL_TIMEOUT  = 120.0  # abandon après N secondes


# ---------------------------------------------------------------------------
# Scénarios de test
# ---------------------------------------------------------------------------

SCENARIOS_FILE = Path(__file__).parent / "scenarios.json"

with open(SCENARIOS_FILE, "r", encoding="utf-8") as f:
    SCENARIOS = json.load(f)

# ---------------------------------------------------------------------------
# Résultat d'un test
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    scenario_name: str
    task_id: Optional[str]      = None
    final_status: Optional[str] = None
    provider_used: Optional[str]= None
    latency_ms: Optional[float] = None
    agents_count: int            = 0
    error: Optional[str]        = None
    elapsed_s: float             = 0.0
    passed: bool                 = False
    valid_ok: bool               = False
    perf_ok: bool                = False


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

llm_client = LLMClient(base_url=BASE_URL, poll_interval=POLL_INTERVAL, poll_timeout=POLL_TIMEOUT)


def validate_result(data: dict, payload: dict) -> tuple[bool, bool]:
    """Retourne (valid_ok, perf_ok) basé sur les règles métier et la latence."""
    latency = data.get("latency_ms")
    perf_ok = latency is not None and latency <= 20000  # max 20s de latence LLM

    category = payload.get("category")
    valid_ok = llm_client.validate_format(data, category)
    return valid_ok, perf_ok


def check_health(client: httpx.Client) -> bool:
    success, data = llm_client.check_health(client)
    if success:
        print(f"  API : {data['status']}")
        for provider, info in data.get("providers", {}).items():
            print(f"  {provider:10s} rpm={info['current_rpm']}/{info['rpm_limit']}  available={info['available']}")
        return True
    else:
        print(f"  ✗ API inaccessible : {data.get('error')}")
        return False


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_scenario(client: httpx.Client, scenario: dict, force_provider: Optional[str] = None) -> TestResult:
    name    = scenario["name"]
    payload = scenario["payload"].copy()
    expect  = scenario.get("expect_status", 202)

    if force_provider:
        payload["force_provider"] = force_provider

    print(f"\n{'─' * 60}")
    print(f"  {name}")
    print(f"{'─' * 60}")

    result = TestResult(scenario_name=name)
    t0 = time.monotonic()

    # Soumission
    task_id = llm_client.submit_task(client, payload, expect_http=expect, verbose=True)

    if task_id is None:
        result.error   = "Soumission échouée"
        result.elapsed_s = time.monotonic() - t0
        return result

    if task_id == "EXPECTED_ERROR":
        result.passed    = True
        result.valid_ok  = True
        result.perf_ok   = True
        result.final_status = f"HTTP {expect} (attendu)"
        result.elapsed_s = time.monotonic() - t0
        return result

    result.task_id = task_id

    # Polling
    data = llm_client.poll_task(client, task_id, verbose=True)
    llm_client.log_dialogue(payload, data)
    
    result.elapsed_s  = time.monotonic() - t0
    result.final_status = data.get("status")
    result.provider_used = data.get("provider_used")
    result.latency_ms    = data.get("latency_ms")
    result.error         = data.get("error")

    if data.get("result"):
        result.agents_count = len(data["result"])
        result.valid_ok, result.perf_ok = validate_result(data, payload)
        
        print(f"\n  Checks -> Perfo: {'✓' if result.perf_ok else '⚠'} | Valide: {'✓' if result.valid_ok else '✗'}")
        print(f"\n  Réponses des agents :")
        for agent in data["result"]:
            if payload.get("category") == "itinary_multi_agent":
                print(f"    [{agent['agent_id']}] {agent.get('chosen_index')} - {agent.get('mode')}: {agent.get('reason', '')[:120]}...")
            else:
                print(f"    [{agent['agent_id']}] {agent.get('summary', '')[:120]}...")
    else:
        print(f"\n  ✗ Erreur/Timeout : {result.error or 'Aucun résultat retourné'}")

    result.passed = (result.final_status == "success") and result.valid_ok
    return result


def run_burst(client: httpx.Client, scenario: dict, count: int, force_provider: Optional[str] = None) -> list[TestResult]:
    """Soumet le scénario 'count' fois en rafale sans délai, puis poll les résultats."""
    name    = scenario["name"]
    payload = scenario["payload"].copy()
    expect  = scenario.get("expect_status", 202)

    if force_provider:
        payload["force_provider"] = force_provider

    print(f"\n{'─' * 60}")
    print(f"  BURST TEST : Envoi de {count} requêtes en rafale pour : {name}")
    print(f"{'─' * 60}")

    t0 = time.monotonic()
    task_ids = []

    # 1. Soumission en rafale immédiate
    for i in range(count):
        print(f"  [Rafale #{i+1}/{count}] ", end="")
        task_id = llm_client.submit_task(client, payload, expect_http=expect, verbose=False)
        if task_id and task_id != "EXPECTED_ERROR":
            task_ids.append(task_id)

    if not task_ids:
        return [TestResult(
            scenario_name=f"{name} (Rafale de {count})",
            passed=True if expect != 202 else False,
            valid_ok=True,
            perf_ok=True,
            final_status=f"HTTP {expect} (attendu)" if expect != 202 else "Échec de soumission",
            elapsed_s=time.monotonic() - t0
        )]

    # 2. Polling groupé pour bien observer l'effet du micro-batching
    print(f"\n  [Attente groupée] Polling de {len(task_ids)} tâches simultanément...")
    pending_ids = list(task_ids)
    completed_data = {}
    
    # On augmente le timeout en fonction de la taille de la rafale
    deadline = time.monotonic() + POLL_TIMEOUT + (count * 2.0)
    attempt = 0

    while pending_ids and time.monotonic() < deadline:
        attempt += 1
        print(f"  [poll #{attempt}] Il reste {len(pending_ids):02d} tâches en cours... ", end="")
        sys.stdout.flush()
        
        just_finished = []
        for tid in list(pending_ids):
            try:
                data = llm_client.get_task_status(client, tid)
                if data["status"] in ("success", "failed"):
                    just_finished.append(data)
                    pending_ids.remove(tid)
                    # On journalise le dialogue dès que le batch est terminé
                    llm_client.log_dialogue(payload, data)
            except Exception:
                pass
                    
        print(f"({len(just_finished)} terminées à cet instant)")
        
        for data in just_finished:
            completed_data[data["task_id"]] = data

        if pending_ids:
            time.sleep(POLL_INTERVAL)

    if pending_ids:
        print(f"\n  ✗ Timeout expiré : {len(pending_ids)} tâches inachevées sur {count}.")

    # 3. Compilation des résultats
    results = []
    for i, tid in enumerate(task_ids):
        result = TestResult(scenario_name=f"{name} (Rafale {i+1}/{count})", task_id=tid)
        data = completed_data.get(tid)
        
        if data:
            result.final_status  = data.get("status")
            result.provider_used = data.get("provider_used")
            result.latency_ms    = data.get("latency_ms")
            result.error         = data.get("error")
            if data.get("result"):
                result.agents_count = len(data["result"])
                result.valid_ok, result.perf_ok = validate_result(data, payload)
        else:
            result.final_status = "timeout"
            result.error = "Timeout expiré avant la fin du traitement"
            
        result.passed = (result.final_status == "success") and result.valid_ok
        result.elapsed_s = time.monotonic() - t0
        results.append(result)

        
    return results


def print_summary(results: list[TestResult]) -> None:
    print(f"\n{'═' * 60}")
    print("  RÉSUMÉ DÉTAILLÉ & BATCHING")
    print(f"{'═' * 60}")

    # 1. Regrouper les requêtes par (provider, latency, error) pour déduire les lots (batches)
    batches = defaultdict(list)
    for r in results:
        key = (r.provider_used, r.latency_ms, r.error)
        batches[key].append(r)

    batch_count = 0
    total_latency = 0.0
    valid_batches = 0

    for (provider, latency, error), group in batches.items():
        batch_count += 1
        is_success = all(r.passed for r in group)
        status_icon = "✓" if is_success else "✗"
        provider_str = f"[{provider}]" if provider else "[Aucun]"
        latency_str = f"{latency:.0f}ms" if latency else "N/A"
        error_str = f" | Erreur : {error}" if error else ""

        if latency and is_success:
            total_latency += latency
            valid_batches += 1

        # Extraire le nom de base du scénario (sans le suffixe " (Rafale X/Y)")
        scenario_name = group[0].scenario_name.split(" (Rafale")[0]
        
        print(f"  {status_icon} Batch #{batch_count:02d} {provider_str} - {latency_str}{error_str}")
        print(f"      Scénario : {scenario_name}")
        print(f"      Taille   : {len(group)} requêtes regroupées")
        
        # Afficher uniquement les 8 premiers caractères des ID pour plus de lisibilité
        task_ids = [r.task_id[:8] for r in group if r.task_id]
        if task_ids:
            print(f"      IDs      : {', '.join(task_ids[:10])}{' ...' if len(task_ids) > 10 else ''}")
            
        slow_reqs = sum(1 for r in group if r.passed and not r.perf_ok)
        invalid_reqs = sum(1 for r in group if r.final_status == "success" and not r.valid_ok)
        if slow_reqs > 0:
             print(f"      ⚠ {slow_reqs} requêtes avec une latence LLM élevée (> 20s)")
        if invalid_reqs > 0:
             print(f"      ✗ {invalid_reqs} requêtes avec validation métier échouée")
        print()

    print(f"{'─' * 60}")
    print("  STATISTIQUES GLOBALES")
    
    passed = sum(1 for r in results if r.passed)
    total  = len(results)
    
    avg_batch_size = total / batch_count if batch_count else 0
    avg_latency = total_latency / valid_batches if valid_batches else 0

    print(f"  • Total requêtes     : {total} ({passed} succès)")
    print(f"  • Total appels LLM   : {batch_count} batchs (appels HTTP réels)")
    print(f"  • Taille moy. batch  : {avg_batch_size:.1f} requêtes / batch")
    print(f"  • Latence moy. (LLM) : {avg_latency:.0f} ms")

    total_time = results[-1].elapsed_s if results else 0.0
    print(f"\n  Test terminé en {total_time:.1f}s")
    print(f"{'═' * 60}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    global BASE_URL

    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=int, help="Numéro du scénario (1-based)")
    parser.add_argument("--provider", type=str, help="Forcer un provider pour tous les scénarios")
    parser.add_argument("--base-url", type=str, default=BASE_URL)
    parser.add_argument("--burst", type=int, default=1, help="Nombre de fois à envoyer chaque scénario en rafale")
    args = parser.parse_args()

    BASE_URL = args.base_url
    llm_client.base_url = BASE_URL

    print(f"\n{'═' * 60}")
    print("  LLM MODULE — Tests end-to-end")
    print(f"  {BASE_URL}")
    print(f"{'═' * 60}")

    with httpx.Client(timeout=90.0) as client:

        # Healthcheck
        print("\n[Healthcheck]")
        if not check_health(client):
            print("\nArrêt : l'API n'est pas joignable.")
            sys.exit(1)

        # Sélection des scénarios
        scenarios = SCENARIOS
        if args.scenario:
            idx = args.scenario - 1
            if idx < 0 or idx >= len(SCENARIOS):
                print(f"Scénario {args.scenario} inexistant (1-{len(SCENARIOS)}).")
                sys.exit(1)
            scenarios = [SCENARIOS[idx]]

        # Exécution
        results = []
        for scenario in scenarios:
            if args.burst > 1:
                burst_results = run_burst(client, scenario, args.burst, force_provider=args.provider)
                results.extend(burst_results)
            else:
                result = run_scenario(client, scenario, force_provider=args.provider)
                results.append(result)

        print_summary(results)

    failed = sum(1 for r in results if not r.passed)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()