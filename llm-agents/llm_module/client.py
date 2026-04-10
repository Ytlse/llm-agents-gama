import json
import time
from typing import Any, Dict, Optional, Tuple

import httpx


class LLMClient:
    """
    Interface centralisée (SDK) pour interagir avec l'API Gateway du LLM Module.
    Peut être utilisée par les tests ou par l'environnement GAMA.
    """

    def __init__(self, base_url: str = "http://localhost:8000", poll_interval: float = 2.0, poll_timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout

    def check_health(self, client: httpx.Client) -> Tuple[bool, Dict[str, Any]]:
        """Vérifie l'état de santé de l'API et retourne les stats RPM."""
        try:
            resp = client.get(f"{self.base_url}/health", timeout=3.0)
            resp.raise_for_status()
            return True, resp.json()
        except Exception as e:
            return False, {"error": str(e)}

    def submit_task(self, client: httpx.Client, payload: Dict[str, Any], expect_http: int = 202, verbose: bool = False) -> Optional[str]:
        """Envoie la requête POST et retourne le task_id, ou None si erreur."""
        resp = client.post(f"{self.base_url}/tasks", json=payload)

        if resp.status_code != expect_http:
            if verbose:
                print(f"  ✗ HTTP {resp.status_code} (attendu {expect_http})")
                print(f"    {resp.text[:300]}")
            return None

        if expect_http != 202:
            if verbose:
                print(f"  ✓ Erreur attendue reçue : HTTP {resp.status_code}")
            return "EXPECTED_ERROR"

        data = resp.json()
        task_id = data["task_id"]
        if verbose:
            print(f"  → task_id : {task_id}")
        return task_id

    def get_task_status(self, client: httpx.Client, task_id: str) -> Dict[str, Any]:
        """Récupère le statut courant d'une tâche sans attendre."""
        resp = client.get(f"{self.base_url}/tasks/{task_id}")
        resp.raise_for_status()
        return resp.json()

    def poll_task(self, client: httpx.Client, task_id: str, verbose: bool = False) -> Dict[str, Any]:
        """Poll jusqu'à complétion ou timeout de manière synchrone."""
        deadline = time.monotonic() + self.poll_timeout
        attempt = 0

        while time.monotonic() < deadline:
            attempt += 1
            data = self.get_task_status(client, task_id)
            status = data["status"]

            if verbose:
                provider_info = f" provider={data.get('provider_used')}" if data.get("provider_used") else " provider= Undefined"
                print(f"  [poll #{attempt}] status={status}{provider_info}", end="")

            if status in ("success", "failed"):
                if verbose:
                    print()
                return data

            if verbose:
                print(f"  (retry dans {self.poll_interval}s...)")
            time.sleep(self.poll_interval)

        return {"status": "timeout", "error": f"Timeout après {self.poll_timeout}s"}

    def validate_format(self, data: Dict[str, Any], category: Optional[str]) -> bool:
        """Valide le format de la réponse selon la catégorie métier (itinary, perception, etc.)."""
        results = data.get("result", [])
        if not results:
            return False
        
        for agent in results:
            if category == "itinary_multi_agent":
                if agent.get("chosen_index") is None or not agent.get("mode") or not agent.get("reason"):
                    return False
            elif category == "perception_filter":
                if not agent.get("summary") or len(agent.get("summary", "")) < 10:
                    return False
        return True

    def log_dialogue(self, payload: Dict[str, Any], response: Dict[str, Any], log_file: str = "prompt_dialogue.log") -> None:
        """Enregistre la requête et la réponse sous forme de dialogue textuel détaillé."""
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"⏱ TIMESTAMP : {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"📌 CATEGORY  : {payload.get('category', 'unknown')}\n")
                f.write(f"{'-'*60}\n")
                f.write("👤 >>> REQUEST (Payload) >>>\n")
                f.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
                f.write(f"{'-'*60}\n")
                f.write("🤖 <<< RESPONSE (Result) <<<\n")
                # On stocke seulement le "result" s'il a réussi, sinon l'objet entier pour voir l'erreur
                content = response.get("result", response)
                f.write(json.dumps(content, indent=2, ensure_ascii=False) + "\n")
                f.write(f"{'='*60}\n")
        except Exception as e:
            print(f"Erreur lors de l'écriture du log de dialogue : {e}")

  

    async def execute_async(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Soumet une tâche et attend en asynchrone.
        """
        import asyncio
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.base_url}/tasks", json=payload)
            resp.raise_for_status()
            task_id = resp.json()["task_id"]
            
            deadline = time.monotonic() + self.poll_timeout
            while time.monotonic() < deadline:
                resp = await client.get(f"{self.base_url}/tasks/{task_id}")
                data = resp.json()
                if data["status"] in ("success", "failed"):
                    self.log_dialogue(payload, data)
                    return data
                await asyncio.sleep(self.poll_interval)
            return {"status": "timeout", "error": "Timeout expiré"}