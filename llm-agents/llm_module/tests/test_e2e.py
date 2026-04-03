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
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

BASE_URL = "http://localhost:8000"
POLL_INTERVAL = 1.0   # secondes entre deux polls
POLL_TIMEOUT  = 60.0  # abandon après N secondes


# ---------------------------------------------------------------------------
# Scénarios de test
# ---------------------------------------------------------------------------

SCENARIOS = [
    {
        "name": "Scénario 1 — Deux agents, mobilité matin",
        "payload": {
            "category": "default",
            "agents": [
                {"agent_id": "ag_01", "role": "navetteur quotidien", "context": "habite à 15km du centre, possède une voiture"},
                {"agent_id": "ag_02", "role": "étudiant", "context": "sans voiture, carte de transport mensuelle"},
            ],
            "parameters": {
                "scenario": "choix modal matin",
                "time_of_day": "08h00",
                "weather": "pluie légère",
            },
        },
    },
    {
        "name": "Scénario 2 — Agent unique, trajet exceptionnel",
        "payload": {
            "category": "default",
            "agents": [
                {"agent_id": "ag_solo", "role": "senior à mobilité réduite", "context": "rendez-vous médical en centre-ville"},
            ],
            "parameters": {
                "scenario": "déplacement médical",
                "time_of_day": "14h30",
            },
        },
    },
    {
        "name": "Scénario 3 — Cinq agents, diversité de profils",
        "payload": {
            "category": "default",
            "agents": [
                {"agent_id": "prof_01", "role": "professeur", "context": "habite à 3km de l'école, vélo disponible"},
                {"agent_id": "tele_01", "role": "télétravailler 3j/5", "context": "préfère éviter les transports aux heures de pointe"},
                {"agent_id": "livr_01", "role": "livreur à vélo", "context": "connait bien le réseau cyclable"},
                {"agent_id": "tour_01", "role": "touriste", "context": "ne connait pas la ville, smartphone disponible"},
                {"agent_id": "peri_01", "role": "habitant de périphérie", "context": "gare RER à 10 min à pied"},
            ],
            "parameters": {
                "scenario": "retour domicile soir",
                "time_of_day": "18h30",
                "weather": "beau temps",
            },
        },
    },
    {
        "name": "Scénario 4 — Requête malformée (test 422)",
        "payload": {
            "category": "default",
            "agents": [],          # Liste vide → doit échouer à la validation Pydantic
            "parameters": {},
        },
        "expect_status": 422,
    },
    {
        "name": "Scénario 5 — Provider forcé (mistral)",
        "payload": {
            "category": "default",
            "agents": [
                {"agent_id": "ag_test", "role": "cycliste urbain", "context": "militant vélo"},
            ],
            "parameters": {"scenario": "test provider forcé"},
            "force_provider": "mistral",
        },
    },
]


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


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

def submit_task(client: httpx.Client, payload: dict, expect_http: int = 202) -> Optional[str]:
    """Envoie la requête POST et retourne le task_id, ou None si erreur attendue."""
    resp = client.post(f"{BASE_URL}/tasks", json=payload)

    if resp.status_code != expect_http:
        print(f"  ✗ HTTP {resp.status_code} (attendu {expect_http})")
        print(f"    {resp.text[:300]}")
        return None

    if expect_http != 202:
        print(f"  ✓ Erreur attendue reçue : HTTP {resp.status_code}")
        return "EXPECTED_ERROR"

    data = resp.json()
    task_id = data["task_id"]
    print(f"  → task_id : {task_id}")
    return task_id


def poll_task(client: httpx.Client, task_id: str) -> dict:
    """Poll jusqu'à completion ou timeout."""
    deadline = time.monotonic() + POLL_TIMEOUT
    attempt  = 0

    while time.monotonic() < deadline:
        attempt += 1
        resp = client.get(f"{BASE_URL}/tasks/{task_id}")
        resp.raise_for_status()
        data = resp.json()

        status = data["status"]
        print(f"  [poll #{attempt}] status={status}", end="")

        if status in ("success", "failed"):
            print()
            return data

        print(f"  (retry dans {POLL_INTERVAL}s...)")
        time.sleep(POLL_INTERVAL)

    return {"status": "timeout", "error": f"Timeout après {POLL_TIMEOUT}s"}


def check_health(client: httpx.Client) -> bool:
    try:
        resp = client.get(f"{BASE_URL}/health", timeout=3.0)
        data = resp.json()
        print(f"  API : {data['status']}")
        for provider, info in data.get("providers", {}).items():
            print(f"  {provider:10s} rpm={info['current_rpm']}/{info['rpm_limit']}  available={info['available']}")
        return True
    except Exception as e:
        print(f"  ✗ API inaccessible : {e}")
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
    task_id = submit_task(client, payload, expect_http=expect)

    if task_id is None:
        result.error   = "Soumission échouée"
        result.elapsed_s = time.monotonic() - t0
        return result

    if task_id == "EXPECTED_ERROR":
        result.passed    = True
        result.final_status = f"HTTP {expect} (attendu)"
        result.elapsed_s = time.monotonic() - t0
        return result

    result.task_id = task_id

    # Polling
    data = poll_task(client, task_id)
    result.elapsed_s  = time.monotonic() - t0
    result.final_status = data.get("status")
    result.provider_used = data.get("provider_used")
    result.latency_ms    = data.get("latency_ms")
    result.error         = data.get("error")

    if data.get("result"):
        result.agents_count = len(data["result"])
        print(f"\n  Réponses des agents :")
        for agent in data["result"]:
            print(f"    [{agent['agent_id']}] {agent['reponse'][:120]}{'...' if len(agent['reponse']) > 120 else ''}")

    result.passed = result.final_status == "success"
    return result


def print_summary(results: list[TestResult]) -> None:
    print(f"\n{'═' * 60}")
    print("  RÉSUMÉ")
    print(f"{'═' * 60}")

    passed = sum(1 for r in results if r.passed)
    total  = len(results)

    for r in results:
        icon = "✓" if r.passed else "✗"
        provider = f"[{r.provider_used}]" if r.provider_used else ""
        latency  = f"{r.latency_ms:.0f}ms" if r.latency_ms else ""
        print(f"  {icon} {r.scenario_name}")
        if r.error and not r.passed:
            print(f"      erreur : {r.error}")
        elif r.passed:
            details = " | ".join(filter(None, [provider, latency, f"{r.agents_count} agents" if r.agents_count else None]))
            print(f"      {details}")

    print(f"\n  {passed}/{total} scénarios passés  ({r.elapsed_s:.1f}s total)")
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
    args = parser.parse_args()

    BASE_URL = args.base_url

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
            result = run_scenario(client, scenario, force_provider=args.provider)
            results.append(result)

        print_summary(results)

    failed = sum(1 for r in results if not r.passed)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()