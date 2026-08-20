# LLM Agents GAMA — Claude Code Instructions

This file centralizes all instructions, conventions, and project context for Claude Code.

## Instructions at Each Code Modification

### 1. Maintain Documentation ✅
After every code change, update the documentation files affected.

**What to do:**
- Identify which `.md` files in `docs/` describe the modified behavior
- Start with `README.md` (entry point) to locate relevant docs in `docs/setup/` and `docs/arch/`
- Update those files to reflect new behavior
- Do NOT wait for the user to ask

**Why:** Documentation must stay in sync with code at all times.

---

### 2. Update Changelog 📝
Add an entry to `docs/changelog.md` after every modification.

**Format required:**
- Header: `## [YYYY-MM-DD] Functional Title`
- **New entries go at the TOP** of the file (most recent first)
- Tone: user-focused — what this unlocks or changes for the simulation
- Include "**Before/After**" blocks if observable behavior changes
- DO NOT list modified files (belongs in git commits)
- Separate entries with `---`

**Example:**
```markdown
## [2026-07-10] Cache warm-up on startup

OTP and OSMnx caches are now warmed at initialization to reduce first-request latency.
Pipeline startup is 40% faster in tests.

**Before:** First OTP/OSMnx request took 2–5 seconds
**After:** Caches ready immediately, requests respond in <100ms

---
```

**Why:** Changelog is read to understand functional changes. Technical details (files, commits) belong in git.

---

### 3. Trace Blockers & Raise Alarms 🚨
Instrument potential blocking points and raise explicit alarms on confirmed issues.

**What to do:**
- Add traces at potential bottlenecks (queues, semaphores, external calls)
- When an anomaly is confirmed (threshold crossed, repeated errors), log as **ERROR** with prefix `[ALARME]`
- Use `make error` to see all alarms at a glance
- Fire on rising edge (avoid spam), reset at low threshold

**Why:** A multi-hour simulation run degraded silently (886/901 agents backlogged, cache 0%) with no clear log signal; diagnosis had to be reconstructed afterward.

**Example:**
```python
if backlog_depth > BACKLOG_WARNING_THRESHOLD:
    logger.error(f"[ALARME] Pipeline backlog critical: {backlog_depth}/{total_agents} agents pending")
```

---

## Project Context

### h2c/Hypercorn Fix 🔧
**Status:** Applied in `docker-compose.yml`

GAMA's Java 21 HTTP client automatically adds `Upgrade: h2c` headers to all requests. uvicorn/h11 drops the body for upgrade requests, causing POST /sync to always arrive empty.

**Fix:** The `controller` service runs **hypercorn** (not uvicorn) — it supports HTTP/2 cleartext natively.

**If you touch this:**
- Keep hypercorn for port 8002
- The `/sync` handler reads `raw: Request` and uses `await raw.body()` — this is intentional
- Do NOT switch back to uvicorn without fixing h2c compatibility

**Relevant file:** `docker-compose.yml` (controller service)

---

### Startup Order ⚡
**New order (after Docker migration):**
1. `docker compose up` (starts all services: api, controller, worker, redis, otp)
2. Open GAMA model
3. Press play

**Why:** All LLM services are now containerized. The controller WebSocket client reconnects indefinitely, so it waits for GAMA as long as needed.

**Offline mode (headless, no GUI):** `make run OFFLINE=1` (alias `make run-offline`) runs GAMA in the `gama` compose service (profile `offline`, image `gamaplatform/gama:2025.06.4` — keep the tag pinned to the locally validated GAMA version). **Hot stop/resume:** `make stop-run` stops the simulation (GAMA + launcher) leaving the stack up; `make run OFFLINE=1 CONT=1` resumes in the SAME experiment dir (logs appended, state.json/checkpoints reloaded, Grafana/Prometheus/Redis kept). GAMA restarts at t0 of the sim day (no mid-trip state freeze, cf. ticket 002); caches make the replay near-instant. The launcher `scripts/gama/launch_headless.py` drives load/play via GAMA Server (port 6868) and MUST keep its WebSocket open for the whole run (GAMA Server kills experiments whose client disconnects). `GAMA_WS_URL` switches to `ws://gama:3001`. See `docs/setup/quickstart.md`.

**If agents don't move:**
- Check Docker services started before GAMA
- Check WebSocket logs in controller show successful connection to `ws://host.docker.internal:3001` (GUI mode) or `ws://gama:3001` (offline mode)
- Offline mode: check `experiments/current/gama_headless.log` for load/play errors

**Relevant file:** `handle/websocket.py` (WebSocket reconnect loop)

---

### Debug & Analysis Tools 🛠️
Quick commands for analyzing the latest run:

| Command | Purpose |
|---------|---------|
| `/debug-run` | Analyze latest run (experiments/current): errors, warnings, LLM saturation, backlog, inactive agents, timeouts, init phase |
| `make report` | Full run health report |
| `make capacity` | Pipeline capacity analysis |
| `make init` | Initialization timing breakdown |
| `make error` | Quick scan for ERROR logs and [ALARME] entries |
| `make warning` | Quick scan for WARNING logs |

**Use when:** Debugging slow runs, agent inactivity, cache misses, init bottlenecks.

---

## Reference: Transport Mode Colors 🎨
**Official palette** — use consistently across notebooks, GAMA, Grafana:

| Mode | Color |
|------|-------|
| Car | `red` |
| Bike | `purple` |
| Public Transport (bus/tram/metro) | `green` |
| Walking | `cyan` |
| Train | `purple` |
| Motor scooters | `magenta` |

**Apply in:** mobility analysis notebooks, GAMA (Inhabitant.gaml), Grafana dashboards.

**Why:** Visual coherence across all visualization sources.

---

## Files to Update When Modifying

### After changes to cache behavior:
- `docs/arch/cache-memory.md`
- `docs/changelog.md`
- `README.md` (if affects setup)

### After changes to agent lifecycle or startup:
- `docs/arch/agents-lifecycle.md`
- `docs/changelog.md`

### After changes to LLM inference:
- `docs/arch/llm-inference.md`
- `docs/changelog.md`

### After changes to memory (STM/LTM):
- `docs/arch/memory-stm-ltm.md`
- `docs/changelog.md`

### After changes to settings or configuration:
- `README.md` (setup section)
- `docs/changelog.md`

---

## See Also
- `README.md` — Project overview and setup
- `docs/setup/` — Deployment and configuration guides
- `docs/arch/` — Architecture deep dives
- `Makefile` — Build and test commands

