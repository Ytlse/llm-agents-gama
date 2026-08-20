#!/usr/bin/env python3
"""Met à jour llm_module/config/providers.yaml depuis les quotas réels des providers.

Lancement : `make providers` (ou `make providers DRY_RUN=1` pour prévisualiser).

Sources par adapter (validées le 2026-08-03, cf. docs/setup/llm-providers.md) :
  - mistral / groq / cerebras : 1 requête sonde (max_tokens=1) par instance →
    en-têtes x-ratelimit-* de la réponse (quotas réels du compte).
      mistral  : RPM + TPM (pas de RPD/TPD ; quota mensuel non exposé → règle prorata)
      groq     : RPD + TPM (x-ratelimit-limit-requests = requêtes/JOUR ;
                 RPM et TPD absents des en-têtes → champs laissés tels quels)
      cerebras : RPM + TPM + RPD + TPD (granularités minute/heure/jour)
  - google : API Cloud Quotas (token gcloud) → RPM/TPM/RPD free tier par modèle.
    Les noms de quotas sont des FAMILLES (gemma-4-26b, gemini-3.1-flash-lite) :
    mapping par plus long préfixe sur le default_model de l'instance.
  - openai (ou toute instance sans clé dans .env) : ignorée avec avertissement.

Cycle de vie des modèles (GET /models par adapter) :
  - NOUVEAU modèle texte opérationnel (quota free tier relevable) → bloc
    provider ajouté en fin de fichier. RPD ≥ MIN_RPD_NEW_PROVIDER → en rotation
    (weight calculé) ; RPD plus faible → weight 0 = HORS ROTATION (le load
    balancer filtre weight 0), utilisable seulement via `llm.provider` forcé.
    Un modèle déjà référencé dans le fichier, même commenté, n'est jamais
    ré-ajouté (un bloc commenté = décision humaine ou obsolescence datée).
    Exception mistral : quota partagé par compte → aucun gain, information only.
  - default_model DISPARU de /models → bloc commenté avec la date + [ALARME].

Règles :
  - GARDE-FOU MISTRAL : le free tier est borné à 1 Md tokens/mois (non exposé par
    l'API). Pour ne pas consommer le mois en un jour, tpd_limit est forcé à
    MISTRAL_PRORATA_FACTOR × (quota mensuel / 30). Le RPM est borné à 60 (cadence
    documentée : 1 req/s) même si les en-têtes annoncent plus.
  - weight recalculé (convention du fichier : min(rpm, tpm/3000)/15) dès que
    rpm_limit ou tpm_limit change.
  - max_tokens_per_request suit tpm_limit quand le champ existe (requête unique
    > TPM → HTTP 413).
  - Jamais de suppression ni d'assouplissement silencieux : une sonde en échec
    laisse l'instance intacte ([ALARME] dans le bilan).

Édition chirurgicale du YAML : seules les valeurs changées sont réécrites, les
commentaires du fichier sont préservés (même approche que
llm_module/config.py::_persist_provider_max_output_tokens), écriture atomique.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import requests
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROVIDERS_YAML = PROJECT_ROOT / "llm_module" / "config" / "providers.yaml"
ENV_FILE = PROJECT_ROOT / ".env"
TIMEOUT = 30
TODAY = dt.date.today().isoformat()

# ── Garde-fou Mistral ────────────────────────────────────────────────────────
MISTRAL_MONTHLY_TOKENS = 1_000_000_000  # free tier : 1 Md tokens/mois (doc)
MISTRAL_PRORATA_FACTOR = 3              # tpd = 3 × le prorata journalier
MISTRAL_TPD = MISTRAL_PRORATA_FACTOR * MISTRAL_MONTHLY_TOKENS // 30
MISTRAL_RPM_DOC = 60                    # cadence documentée : 1 req/s

# Nouveaux modèles : seuil d'activation et défauts
MIN_RPD_NEW_PROVIDER = 100   # en-dessous, le seau n'apporte rien à la rotation
GROQ_RPM_FREE_TIER = 30      # RPM free tier Groq (console, non exposé par l'API)
DEFAULT_CONCURRENCY = {"google": 2, "groq": 3, "cerebras": 1}

# Champs pilotés par ce script, par adapter (les autres restent manuels)
MANAGED_FIELDS = {
    "mistral":  ("rpm_limit", "tpm_limit", "tpd_limit"),
    "groq":     ("tpm_limit", "rpd_limit"),
    "cerebras": ("rpm_limit", "tpm_limit", "rpd_limit", "tpd_limit"),
    "google":   ("rpm_limit", "tpm_limit", "rpd_limit"),
}

# Commentaires posés sur les lignes créées/modifiées (par champ, par adapter)
FIELD_COMMENTS = {
    ("mistral", "rpm_limit"): "# 1 req/s (doc free tier) — les en-têtes annoncent plus, borné par prudence",
    ("mistral", "tpd_limit"): f"# GARDE-FOU : {MISTRAL_PRORATA_FACTOR}× le prorata journalier du quota mensuel free tier (1 Md tokens/mois)",
    ("groq", "rpd_limit"): "# quota requêtes/jour (en-têtes x-ratelimit)",
    ("cerebras", "rpd_limit"): "# quota requêtes/jour (en-têtes x-ratelimit)",
    ("google", "rpd_limit"): "# quota requêtes/jour (free tier)",
}


# ─────────────────────────────────────────────────────────────────────────────
# Collecte des quotas
# ─────────────────────────────────────────────────────────────────────────────

def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def probe_headers(base_url: str, key: str, model: str) -> dict[str, str]:
    """Requête minimale → en-têtes x-ratelimit-* (lève en cas d'échec réseau)."""
    r = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "messages": [{"role": "user", "content": "ping"}],
              "max_tokens": 1},
        timeout=TIMEOUT,
    )
    headers = {k.lower(): v for k, v in r.headers.items() if "ratelimit" in k.lower()}
    if r.status_code != 200 and not headers:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:150]}")
    return headers


def _to_int(v: str | None) -> int | None:
    try:
        return int(v) if v is not None else None
    except ValueError:
        return None


def quotas_mistral(headers: dict) -> dict[str, int]:
    out: dict[str, int] = {"tpd_limit": MISTRAL_TPD}
    rpm = _to_int(headers.get("x-ratelimit-limit-req-minute"))
    if rpm:
        out["rpm_limit"] = min(rpm, MISTRAL_RPM_DOC)
    tpm = _to_int(headers.get("x-ratelimit-limit-tokens-minute"))
    if tpm:
        out["tpm_limit"] = tpm
    return out


def quotas_groq(headers: dict) -> dict[str, int]:
    # x-ratelimit-limit-requests = requêtes/JOUR chez Groq (doc console)
    out: dict[str, int] = {}
    rpd = _to_int(headers.get("x-ratelimit-limit-requests"))
    if rpd:
        out["rpd_limit"] = rpd
    tpm = _to_int(headers.get("x-ratelimit-limit-tokens"))
    if tpm:
        out["tpm_limit"] = tpm
    return out


def quotas_cerebras(headers: dict) -> dict[str, int]:
    mapping = {
        "rpm_limit": "x-ratelimit-limit-requests-minute",
        "tpm_limit": "x-ratelimit-limit-tokens-minute",
        "rpd_limit": "x-ratelimit-limit-requests-day",
        "tpd_limit": "x-ratelimit-limit-tokens-day",
    }
    return {f: v for f, h in mapping.items() if (v := _to_int(headers.get(h)))}


def google_freetier_quotas() -> dict[str, dict[str, int]]:
    """Quotas free tier par FAMILLE de modèle via l'API Cloud Quotas.

    Nécessite gcloud authentifié ; le projet actif sert de référence (les
    valeurs free tier sont des défauts par modèle, identiques entre projets).
    """
    token = subprocess.check_output(
        ["gcloud", "auth", "print-access-token"], text=True, timeout=60
    ).strip()
    project = subprocess.check_output(
        ["gcloud", "config", "get-value", "project"], text=True, timeout=30
    ).strip()
    url = (f"https://cloudquotas.googleapis.com/v1/projects/{project}/locations/"
           "global/services/generativelanguage.googleapis.com/quotaInfos")
    infos, page = [], None
    while True:
        params = {"pageSize": 300}
        if page:
            params["pageToken"] = page
        d = requests.get(url, params=params,
                         headers={"Authorization": f"Bearer {token}"},
                         timeout=TIMEOUT)
        d.raise_for_status()
        d = d.json()
        infos += d.get("quotaInfos", [])
        page = d.get("nextPageToken")
        if not page:
            break

    def per_model(quota_id: str) -> dict[str, int]:
        for q in infos:
            if q["quotaId"] != quota_id:
                continue
            out = {}
            for di in q.get("dimensionsInfos", []):
                model = (di.get("dimensions") or {}).get("model")
                v = _to_int(di.get("details", {}).get("value"))
                if model and v and v > 0:  # -1 = illimité, None = pas d'accès
                    out[model] = v
            return out
        return {}

    rpm = per_model("GenerateRequestsPerMinutePerProjectPerModel-FreeTier")
    tpm = per_model("GenerateContentInputTokensPerModelPerMinute-FreeTier")
    rpd = per_model("GenerateRequestsPerDayPerProjectPerModel-FreeTier")
    quotas: dict[str, dict[str, int]] = {}
    for family in set(rpm) | set(tpm) | set(rpd):
        q = {}
        if family in rpm:
            q["rpm_limit"] = rpm[family]
        if family in tpm:
            q["tpm_limit"] = tpm[family]
        if family in rpd:
            q["rpd_limit"] = rpd[family]
        quotas[family] = q
    return quotas


def match_google_family(model: str, families: dict[str, dict]) -> str | None:
    """Plus long préfixe : gemma-4-26b-a4b-it → gemma-4-26b,
    gemini-3.1-flash-lite-preview → gemini-3.1-flash-lite."""
    best = None
    for family in families:
        if model == family or model.startswith(family + "-"):
            if best is None or len(family) > len(best):
                best = family
    return best


def list_models(adapter: str, base_url: str, key: str) -> list[str] | None:
    try:
        if adapter == "google":
            r = requests.get(f"{base_url}/models",
                             params={"key": key, "pageSize": 1000}, timeout=TIMEOUT)
            r.raise_for_status()
            return sorted(m["name"].removeprefix("models/")
                          for m in r.json().get("models", []))
        r = requests.get(f"{base_url}/models",
                         headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT)
        r.raise_for_status()
        return sorted(m["id"] for m in r.json().get("data", []))
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Édition chirurgicale du YAML
# ─────────────────────────────────────────────────────────────────────────────

_COMMENT_PREFIX = re.compile(r"^  (?:#\s?)+")


def _is_block_header(line: str) -> bool:
    """Début d'un bloc provider — actif OU déjà commenté.

    Les blocs commentés doivent compter comme des frontières. Sans eux, la portée
    d'un bloc actif s'étendait jusqu'au bloc ACTIF suivant, en enjambant les blocs
    commentés intermédiaires : `comment_out` les re-commentait au passage et le
    fichier se remplissait de `# # groq_llama4:` (constaté le 2026-08-18 sur
    providers.yaml). Un bloc commenté est une décision humaine ou une obsolescence
    datée : on ne le réécrit pas parce qu'un voisin devient obsolète.

    Discriminant : marqueurs de commentaire retirés, la clé d'un BLOC est à
    l'indentation 2 (`groq_x:`) alors qu'un CHAMP est à 4 ou plus (`#   rpm_limit:`).
    C'est exactement la forme que `comment_out` écrit lui-même.
    """
    if re.match(r"^  [A-Za-z0-9_.\-]+:", line):
        return True
    return bool(re.match(r"^[A-Za-z0-9_.\-]+:", _COMMENT_PREFIX.sub("", line)))


class YamlEditor:
    """Modifie des champs scalaires d'un bloc provider sans toucher au reste."""

    def __init__(self, path: Path):
        self.path = path
        self.lines = path.read_text().splitlines(keepends=True)
        self.changes: list[str] = []

    def _block_range(self, name: str) -> tuple[int, int] | None:
        start = None
        for i, line in enumerate(self.lines):
            if re.match(rf"^  {re.escape(name)}:\s*(#.*)?$", line):
                start = i
                break
        if start is None:
            return None
        end = len(self.lines)
        for j in range(start + 1, len(self.lines)):
            # bloc suivant : clé indentée à 2 espaces, commentée ou non (cf.
            # `_is_block_header` — un bloc commenté borne aussi le précédent)
            if _is_block_header(self.lines[j]):
                end = j
                break
        return start, end

    def get(self, name: str, field: str) -> int | None:
        rng = self._block_range(name)
        if rng is None:
            return None
        for i in range(rng[0] + 1, rng[1]):
            m = re.match(rf"^(\s+){re.escape(field)}:(\s+)(\S+)", self.lines[i])
            if m and not self.lines[i].lstrip().startswith("#"):
                return _to_int(m.group(3))
        return None

    def set(self, name: str, field: str, value: int, comment: str | None = None):
        """Remplace la valeur (commentaire existant préservé, sauf '# TBC') ou
        insère le champ après rpm_limit/tpm_limit avec l'indentation du bloc."""
        rng = self._block_range(name)
        if rng is None:
            raise KeyError(f"bloc provider introuvable : {name}")
        start, end = rng
        pattern = re.compile(
            rf"^(\s+)({re.escape(field)}:)(\s+)(\S+)(\s*)(#.*)?$")
        for i in range(start + 1, end):
            if self.lines[i].lstrip().startswith("#"):
                continue
            m = pattern.match(self.lines[i].rstrip("\n"))
            if not m:
                continue
            old = m.group(4)
            if _to_int(old) == value:
                return  # déjà à jour
            indent, key, gap, _, _, old_comment = m.groups()
            kept = old_comment
            if old_comment and "TBC" in old_comment:
                kept = None  # la valeur est désormais vérifiée
            final_comment = kept or comment
            new_line = f"{indent}{key}{gap}{value}"
            if final_comment:
                new_line += f"  {final_comment}"
            self.lines[i] = new_line + "\n"
            self.changes.append(f"{name}.{field}: {old} → {value}")
            return
        # champ absent → insertion après le premier champ quota du bloc,
        # valeur alignée sur la colonne de la ligne d'ancrage
        anchor = None
        indent, value_col = "    ", None
        for i in range(start + 1, end):
            m = re.match(r"^(\s+)(rpm_limit|tpm_limit):(\s+)\S", self.lines[i])
            if m:
                anchor, indent = i, m.group(1)
                value_col = len(m.group(1)) + len(m.group(2)) + 1 + len(m.group(3))
        if anchor is None:
            anchor = start
        head = f"{indent}{field}:"
        pad = " " * max(1, (value_col or 0) - len(head))
        new_line = f"{head}{pad}{value}"
        if comment:
            new_line += f"  {comment}"
        self.lines.insert(anchor + 1, new_line + "\n")
        self.changes.append(f"{name}.{field}: (absent) → {value}")

    def set_weight(self, name: str, rpm: int, tpm: int | None):
        cap = rpm if tpm is None else min(rpm, tpm / 3000)
        weight = round(cap / 15, 2)
        detail = (f"min({rpm}, {tpm}/3000)/15" if tpm is not None else f"{rpm}/15")
        rng = self._block_range(name)
        if rng is None:
            return
        pattern = re.compile(r"^(\s+)(weight:)(\s+)(\S+)(\s*)(#.*)?$")
        for i in range(rng[0] + 1, rng[1]):
            if self.lines[i].lstrip().startswith("#"):
                continue
            m = pattern.match(self.lines[i].rstrip("\n"))
            if not m:
                continue
            old = m.group(4)
            try:
                if abs(float(old) - weight) < 0.005:
                    return
            except ValueError:
                pass
            indent, key, gap = m.group(1), m.group(2), m.group(3)
            self.lines[i] = (f"{indent}{key}{gap}{weight}"
                             f"   # {detail} = {weight} — maj {TODAY}\n")
            self.changes.append(f"{name}.weight: {old} → {weight}")
            return

    def has_model(self, model: str) -> bool:
        """Le modèle est-il déjà référencé — bloc actif OU commenté ? (un bloc
        commenté = décision humaine ou obsolescence : on ne le ré-ajoute pas)"""
        pat = re.compile(rf"default_model:\s+{re.escape(model)}\s*(#.*)?$")
        return any(pat.search(line) for line in self.lines)

    def comment_out(self, name: str, reason: str):
        """Commente tout le bloc d'un provider (avec la date et la raison)."""
        rng = self._block_range(name)
        if rng is None:
            return
        start, end = rng
        # ne pas emporter les lignes vides/commentaires de fin de bloc
        while end - 1 > start and not self.lines[end - 1].strip():
            end -= 1
        self.lines.insert(start, f"  # [obsolète {TODAY}] {reason}\n")
        for i in range(start + 1, end + 1):
            stripped = self.lines[i].rstrip("\n")
            if stripped.strip():
                self.lines[i] = "  # " + stripped.removeprefix("  ") + "\n"
        self.changes.append(f"{name}: bloc commenté ({reason})")

    def append_provider(self, name: str, adapter: str, base_url: str,
                        model: str, quotas: dict[str, int],
                        concurrency: int, weight_override: float | None = None,
                        weight_comment: str | None = None):
        """Ajoute en fin de fichier un bloc provider ACTIF, quotas relevés.
        weight_override=0.0 = hors rotation (le load balancer filtre weight 0)."""
        rpm, tpm = quotas.get("rpm_limit"), quotas.get("tpm_limit")
        if weight_override is not None:
            weight = weight_override
        else:
            weight = round(min(rpm, tpm / 3000) / 15, 2) if rpm and tpm else 1.0

        def line(field: str, value, comment: str = "") -> str:
            s = f"    {field}:{' ' * max(1, 19 - len(field))}{value}"
            return s + (f"  {comment}" if comment else "") + "\n"

        block = [f"\n  # Ajouté par make providers le {TODAY} — quotas free tier relevés\n",
                 f"  {name}:\n",
                 line("adapter", adapter)]
        if rpm:
            block.append(line("rpm_limit", rpm))
        if tpm:
            block.append(line("tpm_limit", tpm))
        if "rpd_limit" in quotas:
            block.append(line("rpd_limit", quotas["rpd_limit"],
                              "# quota requêtes/jour (free tier)"))
        if "tpd_limit" in quotas:
            block.append(line("tpd_limit", quotas["tpd_limit"]))
        if tpm and tpm <= 16000:
            block.append(line("max_tokens_per_request", tpm,
                              "# = TPM free tier (requête unique au-delà → HTTP 413)"))
        block.append(line("base_url", base_url))
        block.append(line("default_model", model))
        default_wc = f"# min({rpm}, {tpm}/3000)/15" if rpm and tpm else ""
        block.append(line("weight", weight, weight_comment or default_wc))
        block.append(line("concurrency_limit", concurrency))
        block.append(line("disable_timeout", 120))
        self.lines += block
        status = "HORS ROTATION (weight 0)" if weight == 0 else "ACTIVÉ"
        self.changes.append(f"nouveau provider {status} : {name} → {model}")

    def write(self):
        # `mkstemp` crée en 0600 : sans report du mode d'origine, providers.yaml
        # passerait de 644 à 600 au premier `make providers`, et le fichier est monté
        # en lecture dans les conteneurs.
        mode = self.path.stat().st_mode & 0o7777 if self.path.exists() else None
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            f.writelines(self.lines)
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, self.path)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="affiche le bilan sans écrire providers.yaml")
    args = parser.parse_args()

    env = load_env(ENV_FILE)
    cfg = yaml.safe_load(PROVIDERS_YAML.read_text())["providers"]
    editor = YamlEditor(PROVIDERS_YAML)
    alarms: list[str] = []
    infos: list[str] = []

    # Quotas Google (une seule fois, partagés entre instances)
    google_quotas: dict[str, dict[str, int]] = {}
    if any(c.get("adapter", n) == "google" for n, c in cfg.items()):
        try:
            google_quotas = google_freetier_quotas()
        except Exception as e:
            alarms.append(f"[ALARME] Cloud Quotas inaccessible (gcloud ?) — "
                          f"instances google inchangées : {e}")

    models_cache: dict[tuple, list[str] | None] = {}

    for name, c in cfg.items():
        adapter = c.get("adapter", name)
        base_url, model = c["base_url"], c["default_model"]
        key = env.get(f"PROVIDER_KEYS__{name}") or env.get(f"PROVIDER_KEYS__{adapter}")
        if not key:
            infos.append(f"· {name}: pas de clé PROVIDER_KEYS__ — ignoré")
            continue

        # 1. Le default_model existe-t-il encore ?
        ck = (adapter, base_url, key)
        if ck not in models_cache:
            models_cache[ck] = list_models(adapter, base_url, key)
        models = models_cache[ck]
        if models is None:
            alarms.append(f"[ALARME] {name}: GET /models en échec — instance inchangée")
            continue
        if model not in models:
            editor.comment_out(name, f"default_model '{model}' absent de /models")
            alarms.append(f"[ALARME] {name}: default_model '{model}' ABSENT de "
                          f"/models — bloc commenté, capacité réduite")
            continue

        # 2. Quotas
        try:
            if adapter == "google":
                family = match_google_family(model, google_quotas)
                if not google_quotas:
                    continue  # alarme déjà levée
                if family is None:
                    alarms.append(f"[ALARME] {name}: aucune famille Cloud Quotas "
                                  f"ne correspond à '{model}' — inchangé")
                    continue
                quotas = google_quotas[family]
            else:
                headers = probe_headers(base_url, key, model)
                quotas = {"mistral": quotas_mistral, "groq": quotas_groq,
                          "cerebras": quotas_cerebras}[adapter](headers)
        except Exception as e:
            alarms.append(f"[ALARME] {name}: sonde en échec — inchangé : {e}")
            continue

        # 3. Application (champs pilotés uniquement)
        before = len(editor.changes)
        old_tpm = editor.get(name, "tpm_limit")
        for field in MANAGED_FIELDS.get(adapter, ()):
            if field in quotas:
                editor.set(name, field, quotas[field],
                           comment=FIELD_COMMENTS.get((adapter, field)))

        new_tpm = quotas.get("tpm_limit", old_tpm)
        if len(editor.changes) > before:
            # max_tokens_per_request suit le TPM quand le champ existe
            if (new_tpm and editor.get(name, "max_tokens_per_request") is not None
                    and editor.get(name, "max_tokens_per_request") != new_tpm):
                editor.set(name, "max_tokens_per_request", new_tpm,
                           comment="# = TPM free tier (requête unique au-delà → HTTP 413)")
            rpm = quotas.get("rpm_limit") or editor.get(name, "rpm_limit")
            if rpm:
                editor.set_weight(name, rpm, new_tpm)

    # ── Nouveaux modèles opérationnels → providers ACTIVÉS, quotas relevés ──
    used = {c["default_model"] for c in cfg.values()}
    fresh_by_adapter: dict[str, set[str]] = {}
    adapter_ctx: dict[str, tuple[str, str]] = {}  # adapter → (base_url, key)
    for (adapter, base_url, key), models in models_cache.items():
        adapter_ctx.setdefault(adapter, (base_url, key))
        for m in models or []:
            if (m not in used
                    and re.search(r"(gemini-3|gemma-4|llama|gpt|qwen|glm|mistral|ministral)", m)
                    and not re.search(r"(embed|tts|image|live|audio|robotics|guard|whisper|ocr|voxtral|transcribe|customtools)", m)):
                fresh_by_adapter.setdefault(adapter, set()).add(m)

    def slug(adapter: str, model: str) -> str:
        return f"{adapter}_" + re.sub(r"[^a-z0-9]+", "_", model.lower()).strip("_")

    for adapter, fresh in sorted(fresh_by_adapter.items()):
        if adapter == "mistral":
            # quota PAR COMPTE, partagé entre modèles : un modèle de plus
            # n'apporte aucune capacité — information seulement
            infos.append(f"· mistral: {len(fresh)} modèles texte non référencés "
                         "(quota partagé par compte → aucun gain de capacité)")
            continue
        base_url, key = adapter_ctx[adapter]
        for model in sorted(fresh):
            if editor.has_model(model):
                continue  # déjà référencé (même commenté = décision humaine)
            try:
                if adapter == "google":
                    family = match_google_family(model, google_quotas)
                    # même famille = MÊME seau de quota (ex. -preview et stable) :
                    # activer les deux ferait dépasser le seau par le limiteur local
                    twin = next((n for n, c in cfg.items()
                                 if c.get("adapter", n) == "google"
                                 and match_google_family(c["default_model"],
                                                         google_quotas) == family),
                                None)
                    if twin:
                        infos.append(f"· google/{model}: ignoré — même seau de "
                                     f"quota que l'instance active '{twin}'")
                        continue
                    quotas = dict(google_quotas.get(family or "", {}))
                else:
                    headers = probe_headers(base_url, key, model)
                    quotas = {"groq": quotas_groq,
                              "cerebras": quotas_cerebras}[adapter](headers)
                    if adapter == "groq":
                        # RPM non exposé par l'API — 30 pour tous les modèles
                        # chat free tier (console Groq, relevé 2026-08-03)
                        quotas.setdefault("rpm_limit", GROQ_RPM_FREE_TIER)
            except Exception as e:
                infos.append(f"· {adapter}/{model}: sonde impossible, non ajouté ({e})")
                continue
            rpd = quotas.get("rpd_limit")
            if not quotas.get("rpm_limit"):
                continue  # pas d'accès free tier → pas opérationnel
            if rpd is not None and rpd < MIN_RPD_NEW_PROVIDER:
                # trop petit pour la rotation → défini mais HORS ROTATION
                # (weight 0), utilisable via `llm.provider` forcé
                editor.append_provider(
                    slug(adapter, model), adapter, base_url, model, quotas,
                    concurrency=DEFAULT_CONCURRENCY.get(adapter, 1),
                    weight_override=0.0,
                    weight_comment=f"# HORS ROTATION : RPD free tier {rpd}/j "
                                   f"< {MIN_RPD_NEW_PROVIDER} — llm.provider forcé uniquement",
                )
                continue
            editor.append_provider(slug(adapter, model), adapter, base_url,
                                   model, quotas,
                                   concurrency=DEFAULT_CONCURRENCY.get(adapter, 1))

    # ── Bilan ──
    print("═" * 72)
    print(f"BILAN make providers — {TODAY}"
          + ("  (DRY-RUN, rien n'est écrit)" if args.dry_run else ""))
    print("═" * 72)
    if editor.changes:
        print(f"\n{len(editor.changes)} changement(s) :")
        for ch in editor.changes:
            print(f"  ✎ {ch}")
    else:
        print("\n✓ providers.yaml déjà à jour (aucun changement)")
    for line in infos:
        print(line)
    if alarms:
        print()
        for a in alarms:
            print(f"  🚨 {a}")

    if editor.changes and not args.dry_run:
        editor.write()
        print(f"\n→ {PROVIDERS_YAML.relative_to(PROJECT_ROOT)} mis à jour "
              f"(pense à recharger les services : make restart)")
    print()
    return 1 if alarms else 0


if __name__ == "__main__":
    sys.exit(main())
