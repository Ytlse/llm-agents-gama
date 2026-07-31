"""
sdk.py — SDK client typé du gateway LLM (phase 4 du CR de restructuration).

Remplace les dicts bruts de LLMClient.execute_async() par un TaskResult pydantic :
plus de conventions magiques ("EXPECTED_ERROR", clés "_post_ms" injectées dans la
réponse), plus de tâche _heartbeat morte, et un seul httpx.AsyncClient réutilisé
entre les appels (keep-alive) au lieu de deux créés par tâche.

Le contrat HTTP du gateway est inchangé : POST /tasks puis GET /tasks/{id}/wait.

Usage :
    client = LLMGatewayClient(base_url="http://api:8000", wait_timeout=90.0)
    result = await client.execute(payload)          # dict ou LLMRequest
    if result.ok:
        # itinary_multi_agent renvoie une distribution ; le tirage se fait via
        # llm_module.core.mode_choice (normalize_option_probabilities + draw_index).
        probabilities = result.agents[0].probabilities
    await client.aclose()
"""

from __future__ import annotations
import asyncio
import json
import time
from typing import Any, Dict, Optional, Union

import httpx
from loguru import logger
from prometheus_client import Histogram
from pydantic import BaseModel

from llm_module.core.models import AgentResponse, LLMRequest, TaskStatus
from llm_module.telemetry.alarms import fire_alarme

# ---------------------------------------------------------------------------
# Métriques côté consommateur (controller GAMA).
# Les modes/index choisis et compteurs de tâches sont déjà exposés côté worker
# (llm_transport_mode_chosen_total, llm_chosen_index_total, llm_provider_calls_*) ;
# seul le E2E, mesurable uniquement côté client, vit ici.
# ---------------------------------------------------------------------------

LLM_TASK_E2E_DURATION = Histogram(
    'llm_task_e2e_duration_seconds',
    'Durée totale POST /tasks → réponse finale (côté controller), par catégorie',
    ['category'],
    buckets=[1, 2, 5, 10, 30, 60, 120],
)

_TRANSIENT = (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError, httpx.ReadTimeout)


# ---------------------------------------------------------------------------
# Modèles de résultat
# ---------------------------------------------------------------------------

class TaskTiming(BaseModel):
    """Timings mesurés côté client + segments worker (P4/P5)."""
    post_ms: float = 0.0                          # durée du POST /tasks
    wait_ms: float = 0.0                          # durée du long-poll /wait
    timing_p5: Optional[Dict[str, Any]] = None    # segments worker (P4_4, P5_1…)


class TaskResult(BaseModel):
    """Résultat typé d'une tâche gateway — plus de comparaisons de strings."""
    status: TaskStatus
    agents: list[AgentResponse] = []
    error: Optional[str] = None
    provider_used: Optional[str] = None
    timing: Optional[TaskTiming] = None
    task_id: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status is TaskStatus.SUCCESS and bool(self.agents)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class LLMGatewayClient:
    """
    SDK asynchrone du gateway. Un seul httpx.AsyncClient réutilisé entre les
    appels ; aclose() à l'arrêt du consommateur.
    """

    # Nombre d'échecs consécutifs avant de lever l'alarme "gateway en échec continu"
    _FAILURE_ALARM_THRESHOLD = 10

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        *,
        wait_timeout: float = 120.0,
        dialogue_log_file: str | None = "prompt_dialogue.log",
        transport: httpx.AsyncBaseTransport | None = None,
        backpressure_max_inflight: int = 0,
        backpressure_release_ratio: float = 0.2,
    ):
        self._base_url = base_url.rstrip("/")
        self._wait_timeout = wait_timeout
        self._dialogue_log_file = dialogue_log_file
        self._transport = transport  # injectable pour les tests (MockTransport)
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()
        self._consecutive_failures = 0
        # Backpressure : quand l'alarme se déclenche (N échecs consécutifs), on
        # suspend les nouvelles soumissions jusqu'à ce que la pile in-flight
        # retombe sous backpressure_release_ratio × backpressure_max_inflight.
        # backpressure_max_inflight=0 → backpressure désactivée.
        self._backpressure_max_inflight = backpressure_max_inflight
        self._backpressure_release_ratio = backpressure_release_ratio
        self._backpressure_active = False
        self._inflight = 0

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    # Timeout de lecture calé sur le long-poll /wait (+ marge)
                    self._client = httpx.AsyncClient(
                        timeout=httpx.Timeout(self._wait_timeout + 30),
                        transport=self._transport,
                    )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------

    async def execute(self, request: Union[LLMRequest, Dict[str, Any]]) -> TaskResult:
        """
        Soumet une tâche et attend son état terminal (long-poll Pub/Sub côté serveur).

        Ne lève pas sur un échec de tâche : le TaskResult porte status/error.
        Lève httpx.HTTPStatusError si le gateway refuse la soumission (4xx/5xx).
        """
        payload = request.model_dump(exclude_none=True) if isinstance(request, LLMRequest) else request
        category = payload.get("category", "unknown")

        # Backpressure : si l'alarme gateway est active, on attend le drainage de
        # la pile in-flight avant de rendre la main (soumettre cette tâche).
        if self._backpressure_active and self._backpressure_max_inflight > 0:
            await self._await_backpressure_drain()

        self._inflight += 1
        _e2e_start = time.monotonic()
        try:
            task_id = await self._submit(payload)
            post_ms = (time.monotonic() - _e2e_start) * 1000

            wait_start = time.monotonic()
            result = await self._wait(task_id)
            wait_ms = (time.monotonic() - wait_start) * 1000

            result.task_id = task_id
            if result.timing is None:
                result.timing = TaskTiming()
            result.timing.post_ms = round(post_ms, 2)
            result.timing.wait_ms = round(wait_ms, 2)

            self._observe(result, payload, category, _e2e_start, wait_ms)
            return result
        finally:
            self._inflight -= 1

    async def _await_backpressure_drain(self) -> None:
        """Suspend la coroutine appelante tant que la pile in-flight dépasse
        backpressure_release_ratio × backpressure_max_inflight. Une fois drainée,
        désarme la backpressure : le backlog en attente repart d'un coup."""
        threshold = max(1, int(self._backpressure_max_inflight * self._backpressure_release_ratio))
        if self._inflight <= threshold:
            self._backpressure_active = False
            return
        logger.warning(
            f"[BACKPRESSURE] Alarme gateway active — soumissions LLM suspendues "
            f"jusqu'au drainage de la pile ({self._inflight} en vol → ≤ {threshold})"
        )
        while self._inflight > threshold:
            await asyncio.sleep(0.5)
        self._backpressure_active = False
        logger.info(
            f"[BACKPRESSURE] Pile drainée ({self._inflight} en vol ≤ {threshold}) — "
            f"reprise des soumissions LLM"
        )

    # ------------------------------------------------------------------
    # Étapes internes
    # ------------------------------------------------------------------

    async def _submit(self, payload: Dict[str, Any]) -> str:
        """POST /tasks — retry jusqu'à 3 fois sur les erreurs réseau transitoires."""
        client = await self._http()
        for attempt in range(3):
            try:
                resp = await client.post(f"{self._base_url}/tasks", json=payload, timeout=30.0)
                resp.raise_for_status()
                return resp.json()["task_id"]
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"LLM gateway returned HTTP error | status={e.response.status_code} "
                    f"url={self._base_url}/tasks body={e.response.text[:300]}"
                )
                raise
            except _TRANSIENT as e:
                if attempt == 2:
                    logger.error(
                        f"Cannot connect to LLM gateway after 3 attempts | url={self._base_url} error={e}"
                    )
                    raise
                wait = 2 ** attempt
                logger.warning(
                    f"LLM gateway POST failed (attempt {attempt + 1}/3), retry in {wait}s "
                    f"| error={type(e).__name__}"
                )
                await asyncio.sleep(wait)

    async def _wait(self, task_id: str) -> TaskResult:
        """GET /tasks/{id}/wait — attend l'état terminal ou le timeout."""
        client = await self._http()
        try:
            resp = await client.get(
                f"{self._base_url}/tasks/{task_id}/wait",
                params={"timeout": self._wait_timeout},
            )
        except _TRANSIENT as e:
            logger.error(f"LLM gateway wait request failed | task_id={task_id} error={e}")
            return TaskResult(status=TaskStatus.FAILED, error="Timeout expiré", timing=TaskTiming())

        if resp.status_code >= 500:
            logger.error(
                f"LLM gateway wait returned HTTP {resp.status_code} | task_id={task_id} body={resp.text[:300]}"
            )
            return TaskResult(status=TaskStatus.FAILED, error=f"Gateway error {resp.status_code}", timing=TaskTiming())
        try:
            data = resp.json()
        except json.JSONDecodeError:
            logger.error(
                f"LLM gateway returned non-JSON response | task_id={task_id} status={resp.status_code} body={resp.text[:300]}"
            )
            return TaskResult(status=TaskStatus.FAILED, error=f"Réponse gateway non-JSON (HTTP {resp.status_code})", timing=TaskTiming())

        status = TaskStatus(data["status"]) if data.get("status") in TaskStatus._value2member_map_ else TaskStatus.FAILED
        if status not in (TaskStatus.SUCCESS, TaskStatus.FAILED):
            # Budget de long-poll épuisé sans état terminal
            return TaskResult(status=TaskStatus.FAILED, error="Timeout expiré", timing=TaskTiming())

        return TaskResult(
            status=status,
            agents=[AgentResponse(**a) for a in (data.get("result") or [])],
            error=data.get("error"),
            provider_used=data.get("provider_used"),
            timing=TaskTiming(timing_p5=data.get("timing_p5")),
        )

    def _observe(self, result: TaskResult, payload: Dict[str, Any], category: str, e2e_start: float, wait_ms: float) -> None:
        """Métriques + log de dialogue — comportement identique à l'ancien client."""
        LLM_TASK_E2E_DURATION.labels(category=category).observe(time.monotonic() - e2e_start)
        self._log_dialogue(payload, result)

        if result.ok:
            self._consecutive_failures = 0
            # La gateway répond de nouveau → on désarme toute backpressure en cours.
            self._backpressure_active = False
        else:
            error_msg = result.error or "No error detail"
            _log = logger.warning if "saturés" in error_msg or "indisponibles" in error_msg else logger.error
            _log(
                f"Task failed | task_id={result.task_id} category={category} "
                f"wait={wait_ms / 1000:.1f}s error={error_msg}"
            )
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._FAILURE_ALARM_THRESHOLD:
                # Arme la backpressure : les prochaines soumissions attendront le
                # drainage de la pile in-flight avant de repartir.
                self._backpressure_active = True
                if self._consecutive_failures == self._FAILURE_ALARM_THRESHOLD:
                    fire_alarme("gateway_llm")
                    logger.error(
                        f"[ALARME] Gateway LLM : {self._consecutive_failures} tâches échouées d'affilée "
                        f"(dernière : {error_msg}) — plus aucune décision LLM ne revient. "
                        f"Providers en rate-limit ou gateway indisponible : vérifier /health "
                        f"et docker logs llm_module."
                    )

    def _log_dialogue(self, payload: Dict[str, Any], result: TaskResult) -> None:
        """Enregistre la requête et la réponse sous forme de dialogue textuel détaillé."""
        if not self._dialogue_log_file:
            return
        try:
            with open(self._dialogue_log_file, "a", encoding="utf-8") as f:
                f.write(f"\n{'=' * 60}\n")
                f.write(f"⏱ TIMESTAMP : {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"📌 CATEGORY  : {payload.get('category', 'unknown')}\n")
                f.write(f"{'-' * 60}\n")
                f.write("👤 >>> REQUEST (Payload) >>>\n")
                f.write(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")
                f.write(f"{'-' * 60}\n")
                f.write("🤖 <<< RESPONSE (Result) <<<\n")
                content = [a.model_dump() for a in result.agents] if result.agents else result.model_dump(exclude={"agents"})
                f.write(json.dumps(content, indent=2, ensure_ascii=False, default=str) + "\n")
                f.write(f"{'=' * 60}\n")
        except Exception as e:
            logger.warning(f"Erreur lors de l'écriture du log de dialogue : {e}")
