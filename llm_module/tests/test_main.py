"""
tests/test_main.py — Orchestrateur global des tests end-to-end.

Exécute séquentiellement tous les scripts de tests et affiche un bilan global.
Usage: python tests/test_main.py
"""
import subprocess
import sys
import time
from pathlib import Path


def run_script(test_def: dict) -> bool:
    name = test_def["name"]
    cmd = test_def["cmd"]
    print(f"\n{'=' * 60}")
    print(f"🚀 Lancement de : {name}")
    print(f"{'=' * 60}\n")
    
    t0 = time.monotonic()
    # Lance le script de test via un sous-processus pour une isolation totale
    result = subprocess.run(cmd)
    elapsed = time.monotonic() - t0
    
    if result.returncode == 0:
        print(f"\n✅ {name} passé avec succès ({elapsed:.1f}s)")
        return True
    else:
        print(f"\n❌ {name} a échoué ({elapsed:.1f}s)")
        return False


def main():
    print("\n" + "⭐" * 30)
    print("🌟 DÉMARRAGE DE LA SUITE DE TESTS GLOBALE 🌟")
    print("⭐" * 30)
    print("\nDescription :")
    print("  LLM MODULE — Tests end-to-end complets.")
    print("    • Tests E2E complets (scénarios, fallback, routing, validation)")
    print("    • Prompt spécifique perception_filter (formatage des histoires)")
    print("    • Test de charge / Burst (micro-batching, rate-limits, circuit breaker)")
    
    current_dir = Path(__file__).parent
    
    # Liste ordonnée des tests à exécuter
    test_suite = [
        {
            "name": "test_e2e.py (Scénarios standards)",
            "cmd": [sys.executable, str(current_dir / "test_e2e.py")]
        },
        {
            "name": "test_perception.py (Filtre de perception)",
            "cmd": [sys.executable, str(current_dir / "test_perception.py")]
        },
        {
            "name": "test_e2e.py en rafale (Burst 20 requêtes)",
            "cmd": [sys.executable, str(current_dir / "test_e2e.py"), "--scenario", "1", "--burst", "20"]
        }
    ]
    
    results = {}
    t0_global = time.monotonic()
    
    for test in test_suite:
        success = run_script(test)
        results[test["name"]] = success
            
    elapsed_global = time.monotonic() - t0_global
    
    print(f"\n{'=' * 60}")
    print("📊 BILAN GLOBAL DES TESTS")
    print(f"{'=' * 60}")
    
    all_passed = True
    for name, success in results.items():
        status = "✅ SUCCÈS" if success else "❌ ÉCHEC "
        print(f"  {status} : {name}")
        if not success:
            all_passed = False
            
    print(f"\n⏱️  Temps total d'exécution : {elapsed_global:.1f}s")
    
    if all_passed:
        print("\n🎉 TOUS LES TESTS SONT PASSÉS AVEC SUCCÈS ! 🎉\n")
        sys.exit(0)
    else:
        print("\n💥 CERTAINS TESTS ONT ÉCHOUÉ ! 💥\n")
        sys.exit(1)


if __name__ == "__main__":
    main()