"""
tests/test_perception.py — Test spécifique pour la collecte du filtre de perception.

Usage:
  python tests/test_perception.py
  python tests/test_perception.py --base-url http://staging:8000
"""
import argparse
import sys
import time
import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
MIN_SUMMARY_LENGTH = 20 

PAYLOAD = {
    "category": "perception_filter",
    "parameters": {},
    "agents": [
        {
            "agent_id": "ag_marc",
            "role": "38y, Aeronautical Engineer, Pibrac.",
            "goal": "Travel time reliability to avoid unpredictable traffic congestion.",
            "context": "Daily home-work commute to city center; car used only for weekend leisure.",
            "constraints": "Strict dependence on SNCF schedules and connections at Matabiau station.",
            "history": [
                "Accident sur la voie : 1h de retard, impossible de prévenir à temps, journée gâchée."
            ],
            "feeling": "Mode Private Car: Cost: 0.6, Time: 0.3, Ease: 0.5, Safety: 0.9, Comfort: 0.9, Ecology: 0.4\nMode Train: Cost: 0.8, Time: 0.9, Ease: 0.8, Safety: 0.9, Comfort: 0.8, Ecology: 0.9"
        },
        {
            "agent_id": "ag_sarah",
            "role": "21y, Master's student, Borderouge.",
            "goal": "Radical minimization of travel costs.",
            "context": "Trips to Rangueil campus and Jean Jaurès; grocery shopping on foot.",
            "constraints": "No personal vehicle or license; budget limited to Tisséo social fares.",
            "history": [
                "Bus en retard, a dû courir 15 minutes sous la pluie pour ne pas rater son examen."
            ],
            "feeling": "Mode Walking: Cost: 1.0, Time: 0.6, Ease: 0.9, Safety: 0.7, Comfort: 0.6, Ecology: 1.0\nMode Bus / Metro: Cost: 1.0, Time: 0.9, Ease: 1.0, Safety: 0.8, Comfort: 0.7, Ecology: 0.9"
        },
        {
            "agent_id": "ag_thomas",
            "role": "38y, Private Banker, lives in Vieille-Toulouse.",
            "goal": "Reflect professional success and enjoy a high-end sensory experience during commutes.",
            "context": "Primarily a direct commute between home and the city center or Labège.",
            "constraints": "None",
            "history": [
                "Bouchon monstre : 50 min de trajet, stress max, arrivée en retard et énervé.",
                "Trajet fluide : 18 min, climatisation allumée, arrivée frais et reposé."
            ],
            "feeling": "Mode Walking: Cost: Perfect, Time: Very Good, Ease: Perfect, Safety: Very Good, Comfort: Good, Ecology: Perfect\nMode Private Car: Cost: Fair, Time: Unsatisfactory, Ease: Average, Safety: Excellent, Comfort: Excellent, Ecology: Subpar"
        }
    ]
}


def main(base_url: str) -> None:
    print(f"\n{'═' * 60}")
    print("  TEST PERCEPTION FILTER")
    print(f"  {base_url}")
    print(f"{'═' * 60}")
    t0 = time.monotonic()
    max_latency_ms = 20_000

    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{base_url}/tasks", json=PAYLOAD)
        if resp.status_code != 202:
            print(f"  ✗ Erreur soumission (HTTP {resp.status_code}) : {resp.text}")
            sys.exit(1)

        task_id = resp.json()["task_id"]
        print(f"  → Tâche {task_id} acceptée. En attente...")

        for attempt in range(30):
            time.sleep(1.5)
            res = client.get(f"{base_url}/tasks/{task_id}").json()
            status = res["status"]
            print(f"  [poll #{attempt + 1}] Status: {status}...")

            if status == "success":
                elapsed = time.monotonic() - t0
                print(f"\n  ✓ Succès HTTP ! Terminé en {elapsed:.2f}s")

                # 1. Vérification performance
                latency_ms = res.get("latency_ms", 0)
                if latency_ms > max_latency_ms:
                    print(f"  ⚠ Latence LLM élevée ({latency_ms:.0f}ms > {max_latency_ms}ms)")
                else:
                    print(f"  ✓ Perfo OK ({latency_ms:.0f}ms)")

                # 2. Validation du contenu
                results = res.get("result", [])
                if not results:
                    print("  ✗ Résultat vide !")
                    sys.exit(1)

                all_ok = True
                for agent in results:
                    summary = agent.get("summary", "")
                    print(f"    - Agent ID : {agent.get('agent_id')}")
                    print(f"    - Summary  : {summary}")
                    if not summary or len(summary) < MIN_SUMMARY_LENGTH:
                        print(f"  ✗ 'summary' vide ou trop court (< {MIN_SUMMARY_LENGTH} chars) !")
                        all_ok = False

                if not all_ok:
                    sys.exit(1)

                print("\n  ✓ Tous les checks (perfo & validation) sont passés.")
                sys.exit(0)

            elif status == "failed":
                print(f"\n  ✗ Échec de la tâche : {res.get('error')}")
                sys.exit(1)

        print("\n  ✗ Timeout expiré avant la fin de la tâche.")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test perception filter end-to-end")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"URL de base de l'API (défaut : {DEFAULT_BASE_URL})",
    )
    args = parser.parse_args()
    main(args.base_url)
