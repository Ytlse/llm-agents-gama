"""
worker/task_worker.py — Worker Celery avec retry et backoff exponentiel.

Le Worker est le cœur du traitement :
  1. Dépile les tâches de la file de batch (BatchQueue)
  2. Construit le prompt via le PromptManager
  3. Sélectionne le provider via le LoadBalancer
  4. Exécute l'appel LLM via l'Adapter approprié
  5. Valide la sortie structurée
  6. Persiste le résultat (TaskStore) et notifie via Pub/Sub

Les dépendances (Redis, balancer, métriques) sont composées par
worker/runtime.py au premier traitement — pas à l'import du module.

Retry avec backoff exponentiel sur les erreurs 5xx :
  tentative 1 → attente 1s
  tentative 2 → attente 2s
  tentative 3 → attente 4s
  tentative 4 → attente 8s  (max_retries=settings.max_retries dans config)
"""

from __future__ import annotations
import re
import time
from datetime import datetime, timezone

from llm_module.adapters.base import (
    ProviderClientError,
    ProviderParseError,
    ProviderServerError,
    get_adapter,
)
from llm_module.config import get_settings, learn_provider_max_output_tokens
from llm_module.core.mode_choice import (
    argmax_index,
    canonical_mode,
    mode_distribution,
    normalize_option_probabilities,
)
from llm_module.core.models import InternalRequest, Task, TaskStatus
from llm_module.prompts.manager import get_prompt_manager
from llm_module.telemetry.logger import get_logger, log_llm_call, log_llm_error, log_llm_exchange
from llm_module.worker.app import create_celery_app
from llm_module.worker.runtime import WorkerRuntime, get_worker_runtime

logger = get_logger(__name__)


class ProviderCapacityError(Exception):
    """Prompt rendu trop volumineux pour la capacité par requête du provider.

    Levée AVANT l'appel HTTP : le 413 « request too large » est évité, le slot
    RPM/TPM est restitué et le batch est rejoué sur un autre modèle (rotation).
    """

    def __init__(self, provider: str, prompt_tokens_est: int, max_tokens_per_request: int):
        self.provider = provider
        self.prompt_tokens_est = prompt_tokens_est
        self.max_tokens_per_request = max_tokens_per_request
        super().__init__(
            f"Prompt ≈{prompt_tokens_est} tokens estimés > capacité par requête "
            f"({max_tokens_per_request} tokens, sortie minimale comprise) de {provider}"
        )

# ---------------------------------------------------------------------------
# Application Celery — instance module-level requise par le CLI :
#   celery -A llm_module.worker.task_worker.celery_app worker …
# Construire l'app ne touche pas à Redis (la connexion broker est paresseuse).
# ---------------------------------------------------------------------------

celery_app = create_celery_app(get_settings())


# ---------------------------------------------------------------------------
# Tâche principale
# ---------------------------------------------------------------------------

@celery_app.task(
    name="process_batch_task",
    bind=True,
    max_retries=get_settings().max_retries,
)
def process_batch_task(self, batch_key: str, force_provider: str | None = None, min_tpm_required: int | None = None, min_output_required: int | None = None) -> None:
    """
    Point d'entrée Celery pour le traitement par lot (micro-batching).
    `bind=True` pour accéder à `self.retry()`.
    """
    rt = get_worker_runtime()
    settings = rt.settings

    # Attendre un slot provider en boucle locale plutôt que via self.retry().
    # self.retry() crée un nouveau message Celery + round-trips Redis à chaque tentative ;
    # un simple time.sleep() dans le même worker est bien moins coûteux.
    _MAX_PROVIDER_WAIT_SECS = 8
    _PROVIDER_POLL_SECS = 2.0
    # 2 retries : 8s + 12s + 8s + 12s + 8s = 48s < 60s remote_llm_poll_timeout côté client.
    _MAX_SATURATION_RETRIES = 2
    deadline = time.monotonic() + _MAX_PROVIDER_WAIT_SECS
    provider_name: str | None = None
    _p5_provider_wait_start = time.monotonic()
    while True:
        try:
            provider_name = rt.balancer.select_provider(force=force_provider, min_tpm=min_tpm_required, min_output=min_output_required)
            break
        except RuntimeError:
            if time.monotonic() >= deadline:
                if self.request.retries < _MAX_SATURATION_RETRIES:
                    logger.warning(
                        f"Providers saturés depuis {_MAX_PROVIDER_WAIT_SECS}s, "
                        f"retry dans 25s | batch_key={batch_key} "
                        f"attempt={self.request.retries + 1}/{_MAX_SATURATION_RETRIES}"
                    )
                    raise self.retry(countdown=12)
                tasks = rt.queue.pop(batch_key, 100)
                _statuses = rt.balancer.get_status()
                _cooldowns = [n for n, s in _statuses.items() if s.get("cooldown")]
                # Le worker n'expose pas de /metrics : l'alarme transite par Redis
                # et ressort en alarme_total{source} via WorkerMetricsCollector.
                rt.metrics.incr("alarme:providers_satures")
                logger.error(
                    f"[ALARME] Tous les providers LLM saturés ou indisponibles — "
                    f"{len(tasks)} tâche(s) abandonnée(s) | batch_key={batch_key} "
                    f"providers_en_cooldown={_cooldowns or 'aucun'} "
                    f"(quotas RPM/TPM épuisés ? voir /health)"
                )
                for t in tasks:
                    _fail_task(rt, t, f"Providers saturés ou indisponibles après {_MAX_PROVIDER_WAIT_SECS}s ({_MAX_SATURATION_RETRIES} retries épuisés)")
                return
            time.sleep(_PROVIDER_POLL_SECS)
    _p5_provider_wait_ms = (time.monotonic() - _p5_provider_wait_start) * 1000

    # ------------------------------------------------------------------
    # Début du tracking d'occupation du provider
    # ------------------------------------------------------------------
    rt.limiter.incr_active(provider_name)
    try:
        batch_limit = settings.providers[provider_name].batch_max_agents

        # Libère le flag de dispatch différé AVANT le pop : toute tâche ajoutée
        # ensuite pourra replanifier son propre dispatch (cf. BatchQueue.try_mark_scheduled).
        rt.queue.clear_scheduled(batch_key)
        tasks = rt.queue.pop(batch_key, batch_limit)
        if not tasks:
            # Aucune requête ne partira : restituer le slot RPM + TPM réservé
            # par select_provider (sinon il reste consommé 60s pour rien).
            rt.limiter.release_slot(provider_name)
            return

        # Marquer comme en cours
        for task in tasks:
            task.status = TaskStatus.RUNNING
            task.updated_at = datetime.now(timezone.utc)
            rt.store.save_sync(task)

        batch_id = f"batch_{tasks[0].task_id[:8]}_{len(tasks)}"

        try:
            _execute_batch(rt, tasks, batch_id, provider_name, _p5_provider_wait_ms, self.request.retries)

        except ProviderCapacityError as e:
            # Détectée avant l'appel HTTP (et avant le recalage TPM) : le slot
            # RPM/TPM réservé par select_provider n'a servi à rien, on le restitue.
            rt.limiter.release_slot(provider_name)
            rt.metrics.incr(f"capacity_reroute_total:{provider_name}")
            _switch_provider_or_fail(
                self, rt, tasks, batch_key, e, provider_name,
                reason="Prompt trop volumineux pour la capacité par requête",
                min_tpm_required=min_tpm_required,
                min_output_required=min_output_required,
            )

        except ProviderServerError as e:
            # Erreur 5xx → exclusion temporaire, backoff exponentiel et retry
            rt.limiter.cooldown(e.provider, seconds=60)
            delay = min(settings.backoff_base_seconds * (2 ** self.request.retries), 30.0)
            logger.warning(
                f"Erreur serveur provider, retry planifié | task_id={batch_id} "
                f"provider={e.provider} http_status={e.status_code} "
                f"retry_in={delay:.1f}s attempt={self.request.retries + 1}"
            )
            if self.request.retries < self.max_retries:
                rt.queue.requeue(batch_key, tasks)
                raise self.retry(exc=e, countdown=delay)
            else:
                for t in tasks:
                    _fail_task(rt, t, f"Max retries dépassé suite à une erreur 5xx sur {e.provider}")

        except ProviderClientError as e:
            if e.status_code == 429:
                # Rate limit (Too Many Requests) → cooldown calé sur x-ratelimit-reset si disponible
                cooldown_secs = _parse_ratelimit_reset_seconds(getattr(e, "ratelimit_reset", None))
                rt.limiter.cooldown(e.provider, seconds=cooldown_secs)
                delay = min(settings.backoff_base_seconds * (2 ** self.request.retries), 30.0)
                logger.warning(
                    f"Rate limit (429) atteint, provider en cooldown, retry planifié | "
                    f"task_id={batch_id} provider={e.provider} "
                    f"cooldown={cooldown_secs}s ratelimit_reset={getattr(e, 'ratelimit_reset', None)} "
                    f"retry_in={delay:.1f}s attempt={self.request.retries + 1}"
                )
                if self.request.retries < self.max_retries:
                    rt.queue.requeue(batch_key, tasks)
                    raise self.retry(exc=e, countdown=delay)
                else:
                    for t in tasks:
                        _fail_task(rt, t, f"Max retries dépassé({self.max_retries}) suite aux Rate Limits sur {e.provider}")
            elif (limit := _parse_max_tokens_limit(str(e))) and learn_provider_max_output_tokens(e.provider, limit):
                # 400 "max_tokens must be ≤ N" → limite de complétion apprise
                # (config mémoire + providers.yaml). Le batch est rejoué : le
                # prochain essai plafonne max_tokens à N (ou part sur un autre
                # provider via la rotation). Si la limite était déjà connue
                # (learn → False), on retombe dans l'échec définitif ci-dessous
                # pour ne pas boucler sur la même 400.
                logger.warning(
                    f"max_tokens au-dessus de la limite du modèle, batch rejoué avec la "
                    f"limite apprise | task_id={batch_id} provider={e.provider} "
                    f"max_output_tokens={limit} attempt={self.request.retries + 1}"
                )
                if self.request.retries < self.max_retries:
                    rt.queue.requeue(batch_key, tasks)
                    raise self.retry(exc=e, countdown=1)
                else:
                    for t in tasks:
                        _fail_task(rt, t, f"Max retries dépassé({self.max_retries}) sur {e.provider} : {str(e)}")
            else:
                # Autre erreur 4xx → souvent liée au provider/modèle : on tente un
                # autre modèle avant d'abandonner (échec définitif si tous épuisés).
                _switch_provider_or_fail(
                    self, rt, tasks, batch_key, e, e.provider,
                    reason="Erreur 4xx non récupérable",
                    min_tpm_required=min_tpm_required,
                    min_output_required=min_output_required,
                )

        except RuntimeError as e:
            logger.exception(f"RuntimeError inattendue dans le worker | task_id={batch_id}")
            for t in tasks:
                _fail_task(rt, t, f"RuntimeError interne : {str(e)}")

        except ProviderParseError as e:
            # Réponse illisible/hors-schéma : fréquemment propre au modèle. On tente un
            # autre modèle avant d'abandonner ; en dernier recours on remonte le brut.
            logger.warning(
                f"Erreur de parsing de la réponse du provider, bascule tentée | "
                f"task_id={batch_id} detail={str(e)} raw_preview={str(e.raw)[:300]!r}"
            )
            _switch_provider_or_fail(
                self, rt, tasks, batch_key, e, e.provider,
                reason="Erreur de parsing de la réponse LLM",
                min_tpm_required=min_tpm_required,
                min_output_required=min_output_required,
                final_error_msg=f"{str(e)}\nRaw LLM response:\n{e.raw}",
            )

        except Exception as e:
            # Cas générique — on logue avec stacktrace complète via logger.exception
            logger.exception(f"Exception inattendue dans le worker | task_id={batch_id} error={e}")
            for t in tasks:
                _fail_task(rt, t, f"Exception interne : {str(e)}")

        else:
            # Succès complet : relancer un worker s'il reste des éléments dans cette file
            if rt.queue.size(batch_key) > 0:
                process_batch_task.delay(batch_key, force_provider, min_tpm_required, min_output_required)
    finally:
        # Quoi qu'il arrive (succès, échec, retry, timeout...), on libère le slot !
        rt.limiter.decr_active(provider_name)


# ---------------------------------------------------------------------------
# Logique métier
# ---------------------------------------------------------------------------

def _execute_batch(rt: WorkerRuntime, tasks: list[Task], batch_id: str, provider_name: str, p5_provider_wait_ms: float = 0.0, retries: int = 0) -> None:
    settings = rt.settings
    base_req = tasks[0].request
    merged_agents = []
    for t in tasks:
        merged_agents.extend(t.request.agents)

    # 2. Construction du prompt
    prompt_manager = get_prompt_manager()
    _t_prompt = time.monotonic()
    messages = prompt_manager.render(
        category=base_req.category,
        agents=merged_agents,
        parameters=base_req.parameters,
    )
    schema = prompt_manager.get_output_schema(base_req.category)
    p5_prompt_ms = (time.monotonic() - _t_prompt) * 1000

    # 3. Assemblage de la requête interne
    # max_tokens envoyé par le client est un budget PAR tâche (1 agent) : le batch
    # fusionne N agents et la sortie croît linéairement (stm_reflection ≈ 500-1800
    # tokens/agent). Sans scaling, un batch de 10 sature 4096 et le JSON est
    # tronqué en plein milieu → JSONDecodeError. Borné par max_output_tokens
    # (limite de complétion des modèles) puis par la capacité du provider.
    per_task_tokens = base_req.parameters.get("max_tokens", 4096)
    max_tokens = min(per_task_tokens * max(1, len(merged_agents)), settings.max_output_tokens)
    provider_cfg = settings.providers.get(provider_name)
    if provider_cfg and provider_cfg.max_output_tokens:
        max_tokens = min(max_tokens, provider_cfg.max_output_tokens)
    # Garde-fou 413 : la capacité par requête est confrontée à la taille RÉELLE du
    # prompt rendu, pas à assumed_prompt_tokens — les prompts stm_reflection font
    # ~2× l'estimation statique et partaient condamnés vers les providers à petit
    # quota (38 HTTP 413 sur le run 2026-07-11). Si même la sortie minimale ne
    # tient plus dans le budget, on rejoue ailleurs AVANT de brûler l'appel.
    prompt_chars = sum(len(m.content or "") for m in messages)
    prompt_tokens_est = int(prompt_chars / settings.token_chars_ratio)
    max_tokens = _fit_request_budget(
        provider_cfg, prompt_tokens_est, max_tokens, settings.min_output_tokens, provider_name
    )
    internal_req = InternalRequest(
        provider=provider_name,
        messages=messages,
        response_schema=schema,
        temperature=base_req.parameters.get("temperature", 0.7),
        max_tokens=max_tokens,
    )

    # ── Recalage de la réservation TPM sur la taille réelle du batch ────────
    # select_provider() a réservé l'estimation statique tpm_estimate_per_request
    # (forfait batch plein) AVANT de connaître le contenu du batch. Maintenant que
    # le prompt est rendu, on corrige la fenêtre glissante : un petit batch rend
    # du headroom aux autres workers, un batch de réflexions (~4 500 tokens_in/agent)
    # réserve son vrai coût au lieu du forfait 2 200 — c'est ce sous-comptage qui
    # faisait dépasser le TPM réel des providers à petit quota (429).
    reserved_tokens: int | None = None
    if provider_cfg and provider_cfg.tpm_limit:
        reserved_tokens = (
            prompt_tokens_est
            + len(merged_agents) * settings.assumed_output_tokens
        )
        rt.limiter.adjust_tokens(
            provider_name,
            reserved_tokens - (provider_cfg.tpm_estimate_per_request or 0),
        )

    # 4. Appel LLM via l'adapter approprié
    adapter = get_adapter(provider_name)
    start_ts = time.monotonic()

    try:
        llm_output, tokens_in, tokens_out = adapter.call(internal_req)
    except Exception as exc:
        # Restitue le montant effectivement réservé (recalé ci-dessus), pas le forfait.
        rt.limiter.release_slot(provider_name, reserved_tokens)
        logger.error(f"Error with provider | task_id={batch_id} provider={provider_name}")
        rt.metrics.incr(f"llm_calls_err_total:{provider_name}")
        error_type = getattr(exc, "error_type", "unknown")
        http_status = getattr(exc, "status_code", None)
        log_llm_error(
            task_id=batch_id,
            provider=provider_name,
            error_type=error_type,
            error_message=str(exc),
            http_status=http_status,
            ratelimit_reset=getattr(exc, "ratelimit_reset", None),
        )
        rt.metrics.incr(f"llm_errors_by_type:{provider_name}:{error_type}")
        # Ring buffer texte relu par /errors/recent (cockpit Grafana).
        rt.metrics.push_error({
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "provider": provider_name,
            "error_type": error_type,
            "http_status": http_status,
            "message": str(exc)[:500],
            "task_id": batch_id,
        })
        consecutive = rt.limiter.record_failure(provider_name)
        if consecutive >= 30:
            cfg = settings.providers.get(provider_name)
            timeout = cfg.disable_timeout if cfg else 180
            rt.limiter.disable(provider_name, seconds=timeout)
            logger.error(
                f"Provider désactivé pendant {timeout}s après {consecutive} erreurs consécutives | "
                f"provider={provider_name}"
            )
        raise

    rt.limiter.record_success(provider_name)

    # ── Recalage final : la fenêtre TPM reflète la consommation réelle ──────
    if reserved_tokens is not None:
        actual_total = (tokens_in or 0) + (tokens_out or 0)
        if actual_total > 0:
            rt.limiter.adjust_tokens(provider_name, actual_total - reserved_tokens)
            if actual_total > reserved_tokens * 1.25:
                logger.warning(
                    f"Estimation TPM sous-évaluée de {actual_total - reserved_tokens} tokens "
                    f"(réservé={reserved_tokens}, réel={actual_total}) — vérifier "
                    f"token_chars_ratio/assumed_output_tokens | provider={provider_name} "
                    f"category={base_req.category} batch={len(merged_agents)} agents"
                )

    # ── Réalignement des agent_id renvoyés par le LLM ────────────────────────
    # Le modèle renvoie parfois un agent_id mal formé ("PERSONA 446264", voire le
    # nom du persona) au lieu de l'identifiant attendu. Sans correction, le
    # démultiplexage (résultats matchés par agent_id exact) jette silencieusement
    # ces agents : ils ne reçoivent aucune recommandation. On réaligne sur l'id
    # réel via sa partie numérique.
    _expected_ids = [str(a.agent_id) for a in merged_agents]
    _expected_set = set(_expected_ids)
    _by_digits: dict[str, str] = {}
    for _eid in _expected_ids:
        _digits = re.sub(r"\D", "", _eid)
        if _digits:
            _by_digits.setdefault(_digits, _eid)
    for agent_resp in llm_output.agents:
        aid = str(agent_resp.agent_id)
        if aid in _expected_set:
            continue
        resolved = _by_digits.get(re.sub(r"\D", "", aid))
        if resolved:
            logger.warning(
                f"agent_id mal formé par le LLM, réaligné | got={aid!r} → {resolved!r} | "
                f"provider={provider_name} category={base_req.category}"
            )
            agent_resp.agent_id = resolved
        else:
            logger.error(
                f"agent_id non résolu renvoyé par le LLM (résultat perdu) | got={aid!r} | "
                f"expected={_expected_ids} provider={provider_name} category={base_req.category}"
            )

    # ── Métriques métier : mode de transport et tranche de distance ──────────
    # Le LLM renvoie une distribution sur les options, pas un choix : les compteurs
    # historiques (mode/index « choisis ») sont alimentés par l'option la plus probable,
    # tandis que `mode_probability_pct` accumule la masse de probabilité par mode. Le
    # tirage effectif a lieu côté simulation (llm-agents), le worker ne le connaît pas.
    _REFLECTION_CATEGORIES = frozenset(("stm_reflection", "ltm_self_reflection"))
    if base_req.category not in _REFLECTION_CATEGORIES:
        agent_specs_by_id = {a.agent_id: a for a in merged_agents}
        for agent_resp in llm_output.agents:
            spec = agent_specs_by_id.get(agent_resp.agent_id)
            trajectories = spec.trajectories if spec else []
            idx = agent_resp.chosen_index  # repli : réponse à l'ancien format

            if agent_resp.probabilities and trajectories:
                # Les modes viennent des trajectoires envoyées (source de vérité),
                # pas de ceux recopiés par le LLM. Ils servent aussi à réaligner les
                # index hors bornes d'un modèle qui a renuméroté les options.
                traj_modes = [t.get("mode") for t in trajectories]
                weights = normalize_option_probabilities(
                    agent_resp.probabilities, len(trajectories),
                    modes=traj_modes,
                    context=f"agent={agent_resp.agent_id} provider={provider_name}",
                )
                for mode, mass in mode_distribution(weights, traj_modes).items():
                    rt.metrics.incr(f"mode_probability_pct:{mode}", amount=round(mass * 100))
                idx = argmax_index(weights)
                _count_mode_mismatches(rt, agent_resp, traj_modes, provider_name)

            raw_mode = (
                trajectories[idx].get("mode")
                if (idx is not None and trajectories and 0 <= idx < len(trajectories))
                else agent_resp.mode
            )
            primary_mode = _extract_primary_mode(raw_mode or "unknown")
            rt.metrics.incr(f"transport_mode_chosen:{primary_mode}")
            rt.metrics.incr(f"mode_by_provider:{primary_mode}:{provider_name}")

            if idx is not None and trajectories and 0 <= idx < len(trajectories):
                dist_m = float(trajectories[idx].get("total_distance_m") or 0)
                bracket = _get_distance_bracket(dist_m)
                rt.metrics.incr(f"trip_distance_bracket:{bracket}")
                rt.metrics.incr(f"mode_by_distance:{primary_mode}:{bracket}")
                rt.metrics.incr(f"chosen_index:{idx}")

    latency_ms = (time.monotonic() - start_ts) * 1000
    p5_llm_ms = latency_ms

    # Métriques: appel réussi + batching (agents reçus → 1 prompt envoyé)
    rt.metrics.incr(f"llm_calls_ok_total:{provider_name}")
    rt.metrics.incr(f"prompts_sent_total:{base_req.category}")
    rt.metrics.incr(f"agents_batched_total:{base_req.category}", amount=len(merged_agents))

    # Métriques tokens
    rt.metrics.incr(f"tokens_in_total:{provider_name}", amount=tokens_in)
    rt.metrics.incr(f"tokens_out_total:{provider_name}", amount=tokens_out)
    rt.metrics.incr("tokens_in_total:__all__", amount=tokens_in)
    rt.metrics.incr("tokens_out_total:__all__", amount=tokens_out)

    # Quota journalier tokens (tpd_limit) : comptage a posteriori des tokens réels.
    rt.limiter.record_tokens(provider_name, tokens_in + tokens_out)

    tokens_in_per_agent = tokens_in / len(merged_agents) if merged_agents else tokens_in
    if tokens_in_per_agent > settings.assumed_prompt_tokens:
        logger.warning(
            f"[worker] tokens_in dépasse assumed_prompt_tokens | "
            f"tokens_in_per_agent={tokens_in_per_agent:.0f} "
            f"assumed={settings.assumed_prompt_tokens} "
            f"provider={provider_name} batch_id={batch_id}"
        )

    # 6. Log de l'échange LLM (prompt + réponse + tokens) dans workdir/llm_exchanges.jsonl
    # sim_ts = timestamp simulé (departure_timestamp porté par AgentSpec) du 1er agent du batch,
    # pour pouvoir ventiler la consommation par jour de simulation.
    sim_ts = next((a.departure_timestamp for a in merged_agents if getattr(a, "departure_timestamp", None)), None)
    log_llm_exchange(
        task_id=batch_id,
        provider=provider_name,
        messages=[{"role": m.role, "content": m.content} for m in messages],
        response=[a.model_dump() if hasattr(a, "model_dump") else a for a in llm_output.agents],
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        category=base_req.category,
        sim_ts=sim_ts,
    )

    # 7. Télémétrie métriques
    log_llm_call(
        task_id=batch_id,
        provider=provider_name,
        status="success",
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        http_status=200,
    )

    # 7. Démultiplexage et Persistance des résultats
    # P5_5: demux computation time (dict build + result extraction, before Redis saves)
    _t_demux = time.monotonic()
    results_by_agent = {}
    for a in llm_output.agents:
        aid = a.get("agent_id") if isinstance(a, dict) else getattr(a, "agent_id", None)
        if aid:
            results_by_agent[aid] = a

    n = len(tasks)
    base_in,  rem_in  = divmod(tokens_in,  n)
    base_out, rem_out = divmod(tokens_out, n)

    # Build per-task results before saves so P5_5 is measured once
    task_bundles = []
    for i, t in enumerate(tasks):
        t_agent_ids = [a.agent_id for a in t.request.agents]
        t_results   = [results_by_agent[aid] for aid in t_agent_ids if aid in results_by_agent]
        t_tokens_in  = base_in  + (rem_in  if i == n - 1 else 0)
        t_tokens_out = base_out + (rem_out if i == n - 1 else 0)
        task_bundles.append((t, t_results, t_tokens_in, t_tokens_out))

    p5_5_ms = (time.monotonic() - _t_demux) * 1000

    for t, t_results, t_tokens_in, t_tokens_out in task_bundles:
        # P4_4: micro-batch wait = elapsed since task creation minus all worker phases
        # time.time() (epoch), pas time.monotonic() : created_at est un timestamp epoch.
        # created_at peut être naïf (tâches créées avant migration) → on le force en UTC.
        created = t.created_at if t.created_at.tzinfo else t.created_at.replace(tzinfo=timezone.utc)
        elapsed_since_create = (time.time() - created.timestamp()) * 1000
        p4_4_ms = max(0.0, elapsed_since_create - p5_provider_wait_ms - p5_prompt_ms - p5_llm_ms - p5_5_ms)

        t.status        = TaskStatus.SUCCESS
        t.result        = t_results
        t.provider_used = provider_name
        t.latency_ms    = latency_ms
        t.tokens_in     = t_tokens_in
        t.tokens_out    = t_tokens_out
        t.updated_at    = datetime.now(timezone.utc)
        t.timing_p5     = {
            "P4_4_ms":    round(p4_4_ms, 2),
            "P5_1_ms":    round(p5_provider_wait_ms, 2),
            "P5_3_ms":    round(p5_prompt_ms, 2),
            "P5_4_ms":    round(p5_llm_ms, 2),
            "P5_5_ms":    round(p5_5_ms, 2),
            "provider":   provider_name,
            "retries":    retries,
            "tokens_in":  t_tokens_in,
            "tokens_out": t_tokens_out,
        }
        rt.store.save_sync(t)
        rt.store.publish_done_sync(t)

    logger.info(
        f"Batch terminé avec succès | task_id={batch_id} tasks_merged={len(tasks)} "
        f"provider={provider_name} latency_ms={latency_ms:.1f} agents_count={len(llm_output.agents)}"
    )


def _fit_request_budget(
    provider_cfg,
    prompt_tokens_est: int,
    max_tokens: int,
    min_output_tokens: int,
    provider_name: str,
) -> int:
    """Confronte le prompt rendu à la capacité par requête du provider.

    Retourne max_tokens, éventuellement rogné pour tenir sous max_tokens_per_request
    (les providers groq free tier comptent prompt + max_tokens dans la limite 413).
    Lève ProviderCapacityError si même min_output_tokens ne tient plus dans le budget.
    """
    if not (provider_cfg and provider_cfg.max_tokens_per_request):
        return max_tokens
    output_budget = provider_cfg.max_tokens_per_request - prompt_tokens_est
    if output_budget < min_output_tokens:
        raise ProviderCapacityError(provider_name, prompt_tokens_est, provider_cfg.max_tokens_per_request)
    return min(max_tokens, output_budget)


def _switch_provider_or_fail(
    celery_task,
    rt: WorkerRuntime,
    tasks: list[Task],
    batch_key: str,
    exc: Exception,
    provider: str,
    reason: str,
    min_tpm_required: int | None,
    min_output_required: int | None,
    final_error_msg: str | None = None,
) -> None:
    """Bascule le batch vers un AUTRE modèle plutôt que d'échouer sec.

    Utilisé pour les erreurs souvent spécifiques au provider (parse error, 4xx non
    récupérable) : on met le provider fautif en cooldown court puis on rejoue le batch
    SANS force_provider, pour que la rotation SWRR sélectionne un autre modèle. Borné à
    ~len(providers) tentatives afin de ne pas boucler sur une erreur déterministe (une
    requête réellement invalide finit par échouer sur tous les providers).
    """
    settings = rt.settings
    rt.limiter.cooldown(provider, seconds=settings.provider_switch_cooldown_seconds)
    max_switches = min(celery_task.max_retries, max(1, len(settings.providers) - 1))
    if celery_task.request.retries < max_switches:
        logger.warning(
            f"{reason} sur {provider} — bascule vers un autre modèle | "
            f"attempt={celery_task.request.retries + 1}/{max_switches} "
            f"error={str(exc)[:200]}"
        )
        rt.queue.requeue(batch_key, tasks)
        raise celery_task.retry(
            exc=exc,
            countdown=1,
            args=[batch_key],
            kwargs={
                "force_provider": None,
                "min_tpm_required": min_tpm_required,
                "min_output_required": min_output_required,
            },
        )
    terminal_msg = final_error_msg or f"{reason} — échec après {max_switches} bascule(s) de provider : {exc}"
    for t in tasks:
        _fail_task(rt, t, terminal_msg)


def _fail_task(rt: WorkerRuntime, task: Task, error_msg: str) -> None:
    task.status     = TaskStatus.FAILED
    task.error      = error_msg
    task.updated_at = datetime.now(timezone.utc)
    rt.store.save_sync(task)
    rt.store.publish_done_sync(task)
    logger.error(f"Tâche échouée | task_id={task.task_id} error={error_msg}")


# ---------------------------------------------------------------------------
# Helpers métriques métier
# ---------------------------------------------------------------------------

# Au-delà de ce taux d'options mal étiquetées sur la fenêtre observée, on lève une
# alarme : ce n'est plus du bruit, le modèle ne lit plus la liste qu'on lui envoie.
_MODE_MISMATCH_ALARM_RATIO = 0.05
_MODE_MISMATCH_MIN_SAMPLE = 200


def _count_mode_mismatches(rt, agent_resp, traj_modes: list, provider_name: str) -> None:
    """Compare le mode recopié par le LLM à celui de l'option, index par index.

    Ce champ est redondant côté production (le mode réel vient des trajectoires), mais
    c'est justement ce qui en fait un témoin : un désaccord ne signale pas un libellé
    approximatif, il signale que **le modèle a lu une autre option que celle qu'il
    croit noter** — ses probabilités sont alors attribuées aux mauvais index, et la
    distribution est fausse sans que rien d'autre ne le montre.

    La comparaison se fait sur le mode canonique (« BUS » vs « foot,bus,foot » n'est pas
    un désaccord), et seules les entrées portant une étiquette sont comparées.
    """
    total = mismatched = 0
    for entry in agent_resp.probabilities or ():
        announced = getattr(entry, "mode", None)
        if not announced:
            continue
        try:
            i = int(getattr(entry, "index", None))
        except (TypeError, ValueError):
            continue
        if not 0 <= i < len(traj_modes):
            continue
        total += 1
        if canonical_mode(announced) != canonical_mode(traj_modes[i]):
            mismatched += 1
            logger.warning(
                f"Mode annoncé par le LLM ≠ mode de l'option | index={i} "
                f"annoncé={announced!r} réel={traj_modes[i]!r} "
                f"agent={agent_resp.agent_id} provider={provider_name}"
            )

    if not total:
        return
    rt.metrics.incr("mode_label_checked", amount=total)
    if mismatched:
        rt.metrics.incr("mode_label_mismatch", amount=mismatched)

    checked = rt.metrics.get("mode_label_checked") or 0
    bad = rt.metrics.get("mode_label_mismatch") or 0
    if checked >= _MODE_MISMATCH_MIN_SAMPLE and bad / checked > _MODE_MISMATCH_ALARM_RATIO:
        # Front montant : l'alarme ne part qu'une fois (pas de spam à chaque lot).
        # Le worker n'expose pas de /metrics : elle transite par Redis et ressort en
        # alarme_total{source} via WorkerMetricsCollector.
        if not rt.metrics.get("alarme:mode_label_mismatch"):
            rt.metrics.incr("alarme:mode_label_mismatch")
            logger.error(
                f"[ALARME] Étiquettes de mode incohérentes : {bad}/{checked} "
                f"({100 * bad // checked} %) des options notées portent un mode qui n'est "
                f"pas celui de l'option. Le modèle confond les options : les probabilités "
                f"sont attribuées aux mauvais index et la répartition modale est fausse."
            )


# Famille de la hiérarchie de l'enquête → étiquette des compteurs du worker. Le
# vocabulaire de ces compteurs est FIN (métro, tram et bus distincts, contrairement aux
# quatre catégories du scoring EMC²) : c'est un compteur de diagnostic, pas une part
# modale. Les noms existants sont conservés pour que les séries Redis restent lisibles
# d'un run à l'autre ; `cableway` est nouveau — le Téléo et le car scolaire tombaient
# jusqu'ici dans `other`, avec un ERROR à chaque décision.
_WORKER_MODE_LABEL = {
    "metro": "metro", "tram": "tram", "cableway": "cableway", "bus": "bus",
    "rail": "train", "car": "car", "motorbike": "motorbike",
    "bicycle": "cycling", "foot": "walking",
}
# Synonymes en toutes lettres que la hiérarchie ne connaît pas (elle porte les modes de
# JAMBE d'OTP/OSMnx, pas les libellés que le LLM peut écrire). Ils restent ici, faute de
# quoi une réponse « voiture » tomberait dans `other`.
_WORKER_MODE_ALIASES = {
    "train": "rail", "ter": "rail", "intercités": "rail", "intercites": "rail",
    "tc": "bus", "transports en commun": "bus", "transport en commun": "bus",
    "voiture": "car", "driving": "car", "conducteur": "car",
    "vélo": "bicycle", "velo": "bicycle", "cycling": "bicycle",
    "marche": "foot", "walking": "foot", "à pied": "foot", "a pied": "foot",
    "pied": "foot",
}


def _extract_primary_mode(mode: str) -> str:
    """Réduit une chaîne de modes composée (« foot,bus,foot ») au mode principal.

    L'ordre de priorité n'est plus écrit ici : il vient de
    `llm_module.core.mode_hierarchy`, donc de l'annexe « Hiérarchie des modes » du rapport
    de l'enquête (p. 53), contrôlée sur les microdonnées. Concrètement, métro > tram >
    téléphérique > bus > **train** > voiture > deux-roues motorisé > vélo > marche.

    ⚠ Le train est passé DERRIÈRE le bus le 2026-09-04 (ticket 022). Une chaîne
    « bus,train » comptait `train` ; elle compte désormais `bus`, comme l'enquête code
    ses propres déplacements mixtes (34 sur 35). Ces compteurs sont des séries de
    diagnostic, aucune part modale publiée n'en dépend.
    """
    if not mode or mode == "unknown":
        return "unknown"
    from llm_module.core.mode_hierarchy import hierarchy

    parts = {m.strip().lower() for m in mode.split(",")}
    jambes = {_WORKER_MODE_ALIASES.get(p, p) for p in parts}
    family = hierarchy().primary_family(jambes)
    if family is None:
        logger.error(f"Mode de transport inconnu ou non standard dans la réponse LLM | mode={mode}")
        return "other"
    return _WORKER_MODE_LABEL[family]


def _get_distance_bracket(distance_m: float) -> str:
    """Classe une distance en mètres dans une tranche prédéfinie."""
    if distance_m < 1_000:
        return "0-1km"
    if distance_m < 2_000:
        return "1-2km"
    if distance_m < 5_000:
        return "2-5km"
    if distance_m < 10_000:
        return "5-10km"
    if distance_m < 20_000:
        return "10-20km"
    if distance_m < 50_000:
        return "20-50km"
    return ">50km"


# Messages 400 renvoyés quand max_tokens dépasse le plafond de complétion du modèle.
# La limite N est capturée pour être apprise (cf. learn_provider_max_output_tokens).
_MAX_TOKENS_LIMIT_PATTERNS = (
    # Groq : "`max_tokens` must be less than or equal to `8192`, the maximum..."
    re.compile(r"max_tokens`? must be less than or equal to `?(\d+)`?"),
    # OpenAI : "max_tokens is too large: 20000. This model supports at most 16384 completion tokens"
    re.compile(r"supports at most (\d+) (?:completion|output) tokens"),
    # Google : "max_output_tokens must be ... limited to 8192" / variantes "limited to N"
    re.compile(r"max(?:_output)?_?tokens[^.]{0,80}?limited to (\d+)", re.IGNORECASE),
)


def _parse_max_tokens_limit(error_message: str) -> int | None:
    """Extrait la limite de complétion N d'un message d'erreur 400 max_tokens.

    Retourne None si le message ne correspond à aucun format connu.
    """
    for pattern in _MAX_TOKENS_LIMIT_PATTERNS:
        m = pattern.search(error_message)
        if m:
            return int(m.group(1))
    return None


def _parse_ratelimit_reset_seconds(value: str | None, default: int = 60) -> int:
    """Parse le délai avant reset (header retry-after / x-ratelimit-reset-* ou corps 429).

    Formats supportés :
      - Groq : "1h13m4s", "59m17.087999999s", "6m0s", "45s", "140ms"
        (les quotas journaliers TPD renvoient des délais en heures)
      - retry-after standard : nombre brut de secondes ("13")
      - OpenAI : ISO 8601 "2026-05-28T17:01:00Z"

    Retourne `default` si la valeur est absente ou non parseable.
    Valeur retournée clampée à [10, 3600].
    """
    if not value:
        return default

    value = value.strip()

    # Format durée composée : "XhYmZ.Ws", "Xs", "Xms" (Groq)
    m = re.fullmatch(r'(?:(\d+)h)?(?:(\d+)m(?!s))?(?:(\d+(?:\.\d+)?)s)?(?:(\d+(?:\.\d+)?)ms)?', value)
    if m and any(m.groups()):
        hours   = int(m.group(1) or 0)
        minutes = int(m.group(2) or 0)
        seconds = float(m.group(3) or 0)
        millis  = float(m.group(4) or 0)
        total = int(hours * 3600 + minutes * 60 + seconds + millis / 1000) + 2  # +2s de marge
        return max(10, min(total, 3600))

    # Nombre brut de secondes (header retry-after standard)
    try:
        total = int(float(value)) + 2
        return max(10, min(total, 3600))
    except ValueError:
        pass

    # Format ISO 8601 timestamp (OpenAI)
    try:
        reset_dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        delta = (reset_dt - datetime.now(timezone.utc)).total_seconds()
        total = int(delta) + 2
        return max(10, min(total, 3600))
    except (ValueError, TypeError):
        pass

    return default
