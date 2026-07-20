"""Évaluation d'un prompt (micro-batching + appels provider + cache) — phase 1.

Le poste recalculé à chaque mutation, donc le plus coûteux (D4). On le minimise :
- **micro-batching** : plusieurs personas par requête (contrainte : un ``agent_id``
  unique par lot, sinon la réponse JSON écraserait un doublon) — la météo est
  **réinjectée dans chaque bloc persona** (même format ``**Contexte :**`` que le
  template de production ``itinary_multi_agent.md.j2``), ce qui permet de mélanger
  des météos différentes dans un même lot et de remplir les lots jusqu'à la
  capacité provider ;
- **cache adressé par contenu** dans le store : une éval (nœud × dataset × params)
  déjà calculée n'est jamais recalculée (idempotence + reprise sans réappel LLM).

Les fonctions de micro-batching sont **pures** (testables sans réseau) ; les appels
provider passent par ``llm_module`` et sont injectables (``call_fn``) pour les tests.
"""

from __future__ import annotations

import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional
from tqdm import tqdm

import pandas as pd

from .metrics import Metric, categorize_mode
from .models import EvalResult, RunConfig, Scores
from .store import RunStore

# Accès à llm_module (adapters provider) — même mécanisme que l'ancienne lib.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_eval_lock = threading.Lock()

# ── Micro-batching (pur) ─────────────────────────────────────────────────────

_AGENT_ID_RE = re.compile(r'---\s*(?:agent_id=|PERSONA\s+)(\S+?)\s*\|')


def persona_agent_id(section: str) -> str:
    """Extrait l'``agent_id`` de l'en-tête d'une section persona (deux formats)."""
    m = _AGENT_ID_RE.search(section)
    return m.group(1) if m else ""


def inject_context(section: str, context: str) -> str:
    """Insère le contexte (météo) juste après la ligne d'en-tête de la section.

    La météo est réinjectée **dans chaque bloc persona**, au format ``**Contexte :**``
    identique à celui du template de production (``itinary_multi_agent.md.j2``) : un
    lot peut ainsi mélanger des personas de contextes différents, chacun gardant le
    sien au lieu de dépendre d'un préambule commun au lot.
    """
    ctx = (context or "").replace("**Contexte :**", "").strip()
    if not ctx:
        return section
    line = f"**Contexte :** {ctx}"
    header, sep, rest = section.partition("\n")
    return f"{header}\n{line}\n{rest}" if sep else f"{header}\n{line}"


def batches_from_records(records: list[dict], cap: int) -> list[dict]:
    """Regroupe les records (frozen dataset) en lots ≤ ``cap`` personas.

    Chaque lot est ``{"messages": [...], "meta": {agent_id: record}}`` : ``meta``
    permet de rejoindre chaque décision à ses métadonnées **par lot** (correct
    même quand un agent récurrent a plusieurs motifs/distances selon le trajet).
    Placement glouton garantissant l'unicité de l'``agent_id`` dans un lot.
    """
    cap = max(1, cap)
    open_batches: list[dict] = []  # chaque: {"sections": [...], "meta": {aid: rec}}
    for rec in records:
        section = inject_context(rec["section"], rec.get("context", ""))
        aid = rec["agent_id"]
        placed = False
        for batch in open_batches:
            if len(batch["sections"]) < cap and aid not in batch["meta"]:
                batch["sections"].append(section)
                batch["meta"][aid] = rec
                placed = True
                break
        if not placed:
            open_batches.append({"sections": [section], "meta": {aid: rec}})

    entries = []
    for batch in open_batches:
        entries.append({
            "messages": [{"role": "system", "content": ""},
                         {"role": "user", "content": "\n\n".join(batch["sections"])}],
            "meta": batch["meta"],
        })
    return entries


def _record_metadata(rec: dict) -> dict:
    """Extrait du record les colonnes de scoring (strates)."""
    return {k: rec.get(k) for k in
            ("age", "age_cat", "occupation", "genre", "motif", "dist_cat")}


def decisions_to_df(decisions: list[tuple[str, str]],
                    metadata_by_id: dict[str, dict]) -> pd.DataFrame:
    """Reconstruit le df de scoring à partir de décisions brutes + métadonnées.

    Sert au recalcul rétroactif (backtest phase 3) et à la reconstruction du df
    sur un cache hit. La jointure est par ``agent_id`` (attributs démographiques
    constants ; motif/distance = dernier record vu si l'agent est récurrent).
    """
    rows = []
    for agent_id, mode in decisions:
        meta = metadata_by_id.get(str(agent_id), {})
        rows.append({"agent_id": agent_id, "mode": mode,
                     "mode_cat": categorize_mode(mode), **meta})
    return pd.DataFrame(rows)


# ── Appels provider ──────────────────────────────────────────────────────────

def _parse_ratelimit_reset(value: Optional[str], default: int = 60) -> int:
    if not value:
        return default
    m = re.match(r'^(\d+)s?$', str(value).strip())
    if m:
        return int(m.group(1)) + 2
    m = re.match(r'^(\d+)m(\d+)s?$', str(value).strip())
    if m:
        return int(m.group(1)) * 60 + int(m.group(2)) + 2
    try:
        return int(value) + 2
    except (ValueError, TypeError):
        return default


def make_provider_call(config: RunConfig, response_schema) -> Callable[[dict], list[dict]]:
    """Fabrique la fonction d'appel provider (un lot → décisions), avec retry.

    Isolée derrière une fabrique pour rester injectable dans les tests (le loop
    et l'Evaluator ne dépendent que de la signature ``entry -> [{agent_id, mode}]``).
    """
    from llm_module.adapters.base import (
        get_adapter, ProviderClientError, ProviderServerError, ProviderParseError)
    from llm_module.settings.models import InternalMessage, InternalRequest

    def call_entry(entry: dict) -> list[dict]:
        raw = entry["messages"]
        msgs = [InternalMessage(role=m["role"], content=m["content"]) for m in raw]
        req = InternalRequest(provider=config.eval_provider, messages=msgs,
                              response_schema=response_schema,
                              temperature=config.eval_temp)
        out, _, _ = get_adapter(config.eval_provider).call(req)
        return [{"agent_id": a.agent_id, "mode": a.mode} for a in out.agents]

    def call_with_retry(entry: dict) -> list[dict]:
        parse_tries = 0
        for attempt in range(config.max_retries + 1):
            try:
                return call_entry(entry)
            except ProviderClientError as exc:
                if getattr(exc, "status_code", None) == 429 and attempt < config.max_retries:
                    wait = _parse_ratelimit_reset(getattr(exc, "ratelimit_reset", None))
                    if wait > config.max_retry_wait:
                        raise
                    time.sleep(wait)
                else:
                    raise
            except ProviderServerError:
                if attempt < config.max_retries:
                    time.sleep(2 ** attempt)
                else:
                    raise
            except ProviderParseError:
                if parse_tries < 1:
                    parse_tries += 1
                    time.sleep(2.0)
                else:
                    raise
        return []

    return call_with_retry


# ── Évaluateur ───────────────────────────────────────────────────────────────

class Evaluator:
    """Évalue un prompt sur un jeu de records, avec cache store + métrique active.

    ``call_fn`` (un lot → ``[{agent_id, mode}]``) est injectable : en production
    ``make_provider_call`` ; dans les tests, un double déterministe.
    """

    def __init__(self, config: RunConfig, store: RunStore, metric: Metric,
                 cerema: dict, metadata_by_id: dict[str, dict],
                 call_fn: Callable[[dict], list[dict]]):
        self.config = config
        self.store = store
        self.metric = metric
        self.cerema = cerema
        self.metadata_by_id = metadata_by_id
        self.call_fn = call_fn

    def evaluate(self, node_hash: str, blocks: list[dict], dataset: str,
                 records: list[dict], desc: str = "eval",
                 ) -> tuple[EvalResult, pd.DataFrame]:
        """Évalue ``blocks`` sur ``records``. Cache hit → aucun appel LLM.

        Renvoie ``(EvalResult, df)`` : le df (correct par décision) sert au
        diagnostic de mutation ; sur cache hit il est reconstruit des décisions.
        """
        from .blocks import blocks_to_prompt
        params_key = self.config.eval_params_key()
        cached = self.store.cached_eval(node_hash, dataset, params_key)
        if cached is not None:
            return cached, decisions_to_df(cached.decisions, self.metadata_by_id)

        prompt = blocks_to_prompt(blocks)
        cap = self.config.eval_batch_max or len(records)
        batches = batches_from_records(records, cap)

        inter_req_delay = 60.0 / max(1, self.config.eval_rpm)
        last_call = [0.0]

        def _throttled(entry: dict) -> tuple[dict, list[dict]]:
            with _eval_lock:
                wait = inter_req_delay - (time.monotonic() - last_call[0])
                if wait > 0:
                    time.sleep(wait)
                last_call[0] = time.monotonic()
            # Le prompt système du lot = le prompt calibré à évaluer.
            entry = {"messages": [{"role": "system", "content": prompt},
                                  entry["messages"][1]], "meta": entry["meta"]}
            return entry, self.call_fn(entry)

        rows, decisions = [], []
        with ThreadPoolExecutor(max_workers=self.config.eval_workers) as ex:
            # Chaque entrée est tirée eval_samples fois ; toutes les décisions sont
            # mises en commun pour estimer la distribution avec moins de variance.
            futures = [ex.submit(_throttled, b)
                       for b in batches for _ in range(self.config.eval_samples)]
            for fut in tqdm(as_completed(futures), total=len(futures), desc=desc, unit="lot"):
                try:
                    entry, out = fut.result()
                except Exception as exc:  # noqa: BLE001 — on log et on continue
                    print(f"  ⚠ éval: {exc}")
                    continue
                meta = entry["meta"]
                for a in out:
                    aid = str(a["agent_id"])
                    decisions.append((aid, a["mode"]))
                    rec = meta.get(aid) or self.metadata_by_id.get(aid, {})
                    rows.append({"agent_id": aid, "mode": a["mode"],
                                 "mode_cat": categorize_mode(a["mode"]),
                                 **_record_metadata(rec)})

        df = pd.DataFrame(rows)
        scores = self.metric.compute(df, self.cerema, prompt_text=prompt)
        result = EvalResult(node_hash=node_hash, dataset=dataset, decisions=decisions,
                            scores=scores, eval_model=self.config.eval_model,
                            eval_temp=self.config.eval_temp)
        # On ne met en cache qu'un résultat non vide : un df vide = échec réseau à réessayer.
        if not df.empty:
            self.store.record_eval(result, params_key)
        return result, df
