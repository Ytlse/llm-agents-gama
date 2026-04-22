import json
import time
from typing import Any, Dict, Optional, Tuple

import httpx
from loguru import logger
from prometheus_client import Counter, Gauge

TASKS_IN_PROGRESS = Gauge('llm_tasks_in_progress', 'Number of tasks currently in progress')
TASKS_SENT = Counter('llm_tasks_sent_total', 'Total number of tasks sent')
TASKS_RESPONSES = Counter('llm_tasks_responses_total', 'Total number of task responses received')
TASKS_RESPONSES_SUCCESS = Counter('llm_tasks_responses_success_total', 'Total number of successful task responses')
TASKS_RESPONSES_FAILURE = Counter('llm_tasks_responses_failure_total', 'Total number of failed task responses')
MODE_CHOSEN = Counter('llm_mode_chosen_total', 'Distribution of chosen modes', ['mode'])
INDEX_CHOSEN = Counter('llm_index_chosen_total', 'Distribution of chosen plan indices', ['index'])


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
        category = payload.get("category", "unknown")
        agents_count = len(payload.get("agents", []))

        TASKS_SENT.inc()
        TASKS_IN_PROGRESS.inc()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # logger.debug(
                #     f"Submitting task to LLM gateway | url={self.base_url}/tasks "
                #     f"category={category} agents={agents_count}"
                # )
                try:
                    resp = await client.post(f"{self.base_url}/tasks", json=payload)
                    resp.raise_for_status()
                except httpx.ConnectError as e:
                    logger.error(
                        f"Cannot connect to LLM gateway | url={self.base_url} error={e}"
                    )
                    raise
                except httpx.HTTPStatusError as e:
                    logger.error(
                        f"LLM gateway returned HTTP error | status={e.response.status_code} "
                        f"url={self.base_url}/tasks body={e.response.text[:300]}"
                    )
                    raise

                task_id = resp.json()["task_id"]
                # logger.debug(f"Task submitted | task_id={task_id} category={category}")

                poll_start = time.monotonic()
                deadline = poll_start + self.poll_timeout
                _last_status_log = poll_start
                while time.monotonic() < deadline:
                    resp = await client.get(f"{self.base_url}/tasks/{task_id}")
                    data = resp.json()
                    if data["status"] in ("success", "failed"):
                        wait_s = time.monotonic() - poll_start
                        self.log_dialogue(payload, data)
                        TASKS_RESPONSES.inc()
                        if data.get("status") == "success" and data.get("result"):
                            TASKS_RESPONSES_SUCCESS.inc()
                            results = data.get("result", [])
                            for agent in results:
                                mode = agent.get("mode")
                                if mode:
                                    MODE_CHOSEN.labels(mode=mode).inc()
                                chosen_index = agent.get("chosen_index")
                                if chosen_index is not None:
                                    INDEX_CHOSEN.labels(index=str(chosen_index)).inc()
                            # logger.debug(
                            #     f"Task completed successfully | task_id={task_id} category={category} wait={wait_s:.1f}s"
                            # )
                        else:
                            TASKS_RESPONSES_FAILURE.inc()
                            error_detail = data.get("error", "No error detail")
                            logger.error(
                                f"Task failed | task_id={task_id} category={category} "
                                f"wait={wait_s:.1f}s error={error_detail}"
                            )
                        return data
                    # Log a waiting heartbeat every 30s so we can see the task is alive
                    now = time.monotonic()
                    if now - _last_status_log >= 30.0:
                        waited = now - poll_start
                        logger.warning(
                            f"Task still pending | task_id={task_id} category={category} "
                            f"waited={waited:.0f}s task_status={data.get('status')} "
                            f"provider={data.get('provider_used', 'unassigned')}"
                        )
                        _last_status_log = now
                    await asyncio.sleep(self.poll_interval)
                TASKS_RESPONSES_FAILURE.inc()
                waited = time.monotonic() - poll_start
                logger.warning(
                    f"Task timed out | task_id={task_id} category={category} "
                    f"waited={waited:.0f}s timeout={self.poll_timeout}s"
                )
                return {"status": "timeout", "error": "Timeout expiré"}
        finally:
            TASKS_IN_PROGRESS.dec()