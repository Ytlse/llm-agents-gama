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
        # mobility_llm.mode_choice (normalize_option_probabilities + draw_index).
        probabilities = result.agents[0].probabilities
    await client.aclose()
"""

from __future__ import annotations

from datetime import datetime

import asyncio
import json
import time
from typing import Any

import httpx
from loguru import logger
from prometheus_client import Gauge, Histogram
from pydantic import BaseModel

from llm_gateway.core.models import AgentResponse, LLMRequest, TaskStatus
from llm_gateway.telemetry.alarms import fire_alarme

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

LLM_GATEWAY_CIRCUIT_OPEN = Gauge(
    'llm_gateway_circuit_open',
    'Disjoncteur du client gateway LLM (1=ouvert : les soumissions sont suspendues '
    'en attendant le rétablissement, une sonde re-teste périodiquement)',
)

LLM_GATEWAY_CIRCUIT_WAITERS = Gauge(
    'llm_gateway_circuit_waiters',
    'Soumissions LLM suspendues derrière le disjoncteur ouvert (en attente du rétablissement)',
)

_TRANSIENT = (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError, httpx.ReadTimeout)


# ---------------------------------------------------------------------------
# Modèles de résultat
# ---------------------------------------------------------------------------

class TaskTiming(BaseModel):
    """Timings mesurés côté client + segments worker (P4/P5)."""
    post_ms: float = 0.0                          # durée du POST /tasks
    wait_ms: float = 0.0                          # durée du long-poll /wait
    timing_p5: dict[str, Any] | None = None    # segments worker (P4_4, P5_1…)


class TaskResult(BaseModel):
    """Résultat typé d'une tâche gateway — plus de comparaisons de strings."""
    status: TaskStatus
    agents: list[AgentResponse] = []
    error: str | None = None
    # Nature de l'échec quand le gateway la connaît : "quota_journalier" + l'heure de
    # réouverture de la fenêtre. Permet à l'appelant d'ATTENDRE la fenêtre au lieu de
    # relancer toutes les 30 s une clé fermée pour la journée (incident du 2026-09-08).
    error_kind: str | None = None
    resume_at: datetime | None = None
    provider_used: str | None = None
    timing: TaskTiming | None = None
    task_id: str | None = None

    @property
    def quota_journalier_epuise(self) -> bool:
        """L'échec est-il un quota journalier confirmé par le fournisseur ?"""
        return self.error_kind == "quota_journalier"

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
        dialogue_log_file: str | None = None,   # journal texte des payloads : données personnelles potentielles, opt-in
        transport: httpx.AsyncBaseTransport | None = None,
        backpressure_max_inflight: int = 0,
        backpressure_release_ratio: float = 0.2,
        circuit_failure_threshold: int = 10,
        circuit_probe_interval: float = 60.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._wait_timeout = wait_timeout
        self._dialogue_log_file = dialogue_log_file
        self._transport = transport  # injectable pour les tests (MockTransport)
        self._client: httpx.AsyncClient | None = None
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
        # Disjoncteur : après N échecs consécutifs (panne durable — quotas épuisés,
        # gateway/réseau down), les soumissions sont SUSPENDUES : chaque appelant
        # attend tranquillement le rétablissement (renouvellement des quotas, retour
        # du service) au lieu de brûler des tentatives vouées à l'échec et de dégrader
        # les décisions en index par défaut. Une sonde demi-ouverte re-teste le
        # gateway toutes les circuit_probe_interval secondes ; le premier succès
        # referme le disjoncteur et tous les appels suspendus repartent sur le chemin
        # nominal. circuit_failure_threshold=0 → disjoncteur désactivé.
        self._circuit_failure_threshold = circuit_failure_threshold
        self._circuit_probe_interval = circuit_probe_interval
        self._circuit_open_since: float | None = None
        self._circuit_next_probe_at = 0.0
        self._circuit_probe_inflight = False
        self._circuit_waiters = 0

    @property
    def circuit_open(self) -> bool:
        """True si le disjoncteur est ouvert (gateway LLM considéré en panne durable)."""
        return self._circuit_open_since is not None

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

    async def execute(
        self, request: LLMRequest | dict[str, Any], *, wait_timeout: float | None = None
    ) -> TaskResult:
        """
        Soumet une tâche et attend son état terminal (long-poll Pub/Sub côté serveur).

        Ne lève pas sur un échec de tâche : le TaskResult porte status/error.
        Lève httpx.HTTPStatusError si le gateway refuse la soumission (4xx/5xx).

        `wait_timeout` surcharge l'attente pour CET appel. Le défaut du client vaut pour un
        fournisseur distant ; un modèle local sert un appel à la fois et fait patienter les
        suivants, si bien que l'attente d'une tâche n'est pas sa durée de génération mais
        celle de la file. Le 2026-09-08, une course sur Muse Glimmer (28B, une génération de
        40 à 120 s, un seul appel simultané) a vu chaque tâche au-delà de la première expirer
        à 120 s, puis le disjoncteur s'ouvrir. L'appelant qui épingle une instance lui passe
        donc son `wait_timeout` (champ du fichier des fournisseurs).
        """
        payload = request.model_dump(exclude_none=True) if isinstance(request, LLMRequest) else request
        category = payload.get("category", "unknown")

        # Disjoncteur ouvert : la soumission est SUSPENDUE jusqu'au rétablissement du
        # gateway (aucune décision dégradée — on attend le renouvellement des quotas).
        # L'un des appelants suspendus devient périodiquement la sonde (demi-ouvert)
        # qui traverse pour tester si le gateway est rétabli.
        is_probe = await self._circuit_gate()

        # Backpressure : si l'alarme gateway est active, on attend le drainage de
        # la pile in-flight avant de rendre la main (soumettre cette tâche).
        # La sonde ne s'y soumet pas : elle doit partir sans délai.
        if not is_probe and self._backpressure_active and self._backpressure_max_inflight > 0:
            await self._await_backpressure_drain()

        self._inflight += 1
        _e2e_start = time.monotonic()
        try:
            try:
                task_id = await self._submit(payload)
            except httpx.HTTPStatusError as e:
                # 4xx = payload invalide (erreur de programmation) : on propage sans
                # compter d'échec. 5xx = gateway malade : échec comptabilisé (alarme,
                # backpressure, disjoncteur) puis rendu au caller comme TaskResult.
                if e.response.status_code < 500:
                    raise
                result = TaskResult(
                    status=TaskStatus.FAILED,
                    error=f"Gateway error {e.response.status_code} à la soumission",
                    timing=TaskTiming(),
                )
                self._observe(result, payload, category, _e2e_start, 0.0)
                return result
            except _TRANSIENT as e:
                # Gateway injoignable (coupure réseau, service down) : sans ce
                # comptage, une panne franche ne déclenchait NI l'alarme NI le
                # disjoncteur (l'exception court-circuitait _observe).
                result = TaskResult(
                    status=TaskStatus.FAILED,
                    error=f"Gateway LLM injoignable ({type(e).__name__})",
                    timing=TaskTiming(),
                )
                self._observe(result, payload, category, _e2e_start, 0.0)
                return result
            post_ms = (time.monotonic() - _e2e_start) * 1000

            wait_start = time.monotonic()
            result = await self._wait(task_id, wait_timeout)
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
            if is_probe:
                self._circuit_probe_inflight = False

    async def _circuit_gate(self) -> bool:
        """Retient l'appelant tant que le disjoncteur est ouvert.

        Retourne True si cet appel devient la sonde (il traverse pour tester le
        gateway) ; False sinon — soit le disjoncteur était fermé, soit il vient de
        se refermer (sonde d'un autre appelant réussie) et l'appel repart sur le
        chemin nominal. Aucune tâche n'échoue ni n'est dégradée pendant l'attente :
        la simulation attend le renouvellement des quotas / le retour du service.
        """
        if not self.circuit_open:
            return False
        waiting = False
        try:
            while self.circuit_open:
                now = time.monotonic()
                if now >= self._circuit_next_probe_at and not self._circuit_probe_inflight:
                    self._circuit_probe_inflight = True
                    logger.info(
                        f"[circuit] Sonde vers le gateway LLM (disjoncteur demi-ouvert, "
                        f"{self._circuit_waiters} soumission(s) en attente)"
                    )
                    return True
                if not waiting:
                    waiting = True
                    self._circuit_waiters += 1
                    LLM_GATEWAY_CIRCUIT_WAITERS.set(self._circuit_waiters)
                    logger.debug("[circuit] Soumission suspendue en attente du rétablissement du gateway")
                await asyncio.sleep(min(1.0, max(0.1, self._circuit_next_probe_at - now)))
        finally:
            if waiting:
                self._circuit_waiters -= 1
                LLM_GATEWAY_CIRCUIT_WAITERS.set(self._circuit_waiters)
        return False

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

    async def _submit(self, payload: dict[str, Any]) -> str:
        """POST /tasks — retry jusqu'à 3 fois sur les erreurs réseau transitoires."""
        client = await self._http()
        for attempt in range(3):
            try:
                resp = await client.post(f"{self._base_url}/tasks", json=payload, timeout=30.0)
                resp.raise_for_status()
                return str(resp.json()["task_id"])
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
        raise RuntimeError("unreachable: la dernière tentative relève ou retourne")  # pragma: no cover

    async def _wait(self, task_id: str, wait_timeout: float | None = None) -> TaskResult:
        """GET /tasks/{id}/wait — attend l'état terminal ou le timeout.

        Le délai de lecture httpx est posé PAR REQUÊTE : le client partagé est construit sur
        l'attente par défaut, et une attente plus longue serait sinon coupée par lui avant
        que le long-poll ne rende la main."""
        attente = self._wait_timeout if wait_timeout is None else float(wait_timeout)
        client = await self._http()
        try:
            resp = await client.get(
                f"{self._base_url}/tasks/{task_id}/wait",
                params={"timeout": attente},
                timeout=httpx.Timeout(attente + 30),
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
            error_kind=data.get("error_kind"),
            resume_at=data.get("resume_at"),
            provider_used=data.get("provider_used"),
            timing=TaskTiming(timing_p5=data.get("timing_p5")),
        )

    def _observe(self, result: TaskResult, payload: dict[str, Any], category: str, e2e_start: float, wait_ms: float) -> None:
        """Métriques + log de dialogue — comportement identique à l'ancien client."""
        LLM_TASK_E2E_DURATION.labels(category=category).observe(time.monotonic() - e2e_start)
        self._log_dialogue(payload, result)

        if result.ok:
            self._consecutive_failures = 0
            # La gateway répond de nouveau → on désarme toute backpressure en cours.
            self._backpressure_active = False
            if self.circuit_open:
                downtime = time.monotonic() - (self._circuit_open_since or time.monotonic())
                self._circuit_open_since = None
                LLM_GATEWAY_CIRCUIT_OPEN.set(0)
                logger.info(
                    f"[circuit] Gateway LLM rétabli après {downtime:.0f}s de disjoncteur ouvert — "
                    f"reprise des {self._circuit_waiters} soumission(s) suspendue(s)"
                )
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
            now = time.monotonic()
            if self.circuit_open:
                # Sonde (ou requête en vol à l'ouverture) en échec : la prochaine
                # sonde attendra un intervalle complet.
                self._circuit_next_probe_at = now + self._circuit_probe_interval
            elif (
                self._circuit_failure_threshold > 0
                and self._consecutive_failures >= self._circuit_failure_threshold
            ):
                self._circuit_open_since = now
                self._circuit_next_probe_at = now + self._circuit_probe_interval
                LLM_GATEWAY_CIRCUIT_OPEN.set(1)
                fire_alarme("gateway_llm_circuit")
                logger.error(
                    f"[ALARME] Disjoncteur gateway LLM OUVERT après {self._consecutive_failures} échecs "
                    f"consécutifs (dernier : {error_msg}). Les soumissions LLM sont SUSPENDUES — la "
                    f"simulation attend le rétablissement (renouvellement des quotas / retour du service), "
                    f"aucune décision n'est dégradée. Une sonde re-testera le gateway toutes les "
                    f"{self._circuit_probe_interval:.0f}s ; la reprise est automatique."
                )

    def _log_dialogue(self, payload: dict[str, Any], result: TaskResult) -> None:
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
