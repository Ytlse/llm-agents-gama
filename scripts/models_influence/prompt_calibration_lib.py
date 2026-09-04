"""Fonctions pures de calibration de prompt (extrait de prompt_calibration_V2.ipynb).

Ce module regroupe la logique réutilisable : extraction des métadonnées persona,
découpe du prompt en blocs, scoring composite vs EMC² 2023, ablation, génération de
mutations via Mistral, et visualisations.

Configuration
-------------
Les fonctions lisent leur configuration (provider, modèle, clés, référence EMC²,
schéma de réponse…) depuis des variables de module. Le notebook les renseigne une
fois via :func:`configure` après avoir chargé ``cerema``, ``RESPONSE_SCHEMA`` et
calculé ``INITIAL_PROMPT_WORD_COUNT``. Python résout les globals au moment de
l'appel : mettre à jour une variable de module via ``configure`` est donc bien vu
par les fonctions définies ici.
"""

from __future__ import annotations

import sys
import json
import time
import re
import threading
import hashlib
import colorsys
import difflib
from pathlib import Path
from itertools import groupby
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from tqdm.notebook import tqdm
from IPython.display import display, HTML
import httpx

# Le module importe llm_module → on garantit que la racine projet est sur le path,
# indépendamment du cwd de l'appelant.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from llm_module.adapters.base import (
    get_adapter, ProviderClientError, ProviderServerError, ProviderParseError,
)
from llm_module.settings.models import InternalMessage, InternalRequest

__all__ = [
    "MODES", "MODE_COLORS", "EXCLUDE_MODES", "configure",
    "categorize_mode", "infer_gender_from_name", "extract_min_distance_km",
    "distance_to_cat", "normalize_occupation", "age_to_cat", "build_metadata_cache",
    "split_entry_personas", "build_micro_batches",
    "split_sentences", "decompose_prompt", "blocks_to_prompt", "display_blocks",
    "l1_error", "compute_composite_score", "worst_strata_modes", "format_worst_strata",
    "plot_distribution_pies", "plot_score_history", "plot_bars_by_dimension",
    "plot_global_bars", "format_dimension_scores", "present_calibration_state",
    "call_entry", "call_with_retry", "run_evaluation",
    "eval_cache_key", "mutation_cache_load", "mutation_cache_append",
    "run_ablation", "format_ablation_for_mutation",
    "ablation_regression_diagnostic", "build_ablation_result",
    "generate_mutation", "apply_mutation", "highlight_prompt_ablation",
    "render_diff_html",
]

# ════════════════════════════════════════════════════════════════════════════
# Configuration (valeurs par défaut — surchargées par configure() depuis le notebook)
# ════════════════════════════════════════════════════════════════════════════
EVAL_PROVIDER  = "mistral"
EVAL_MODEL     = "mistral-small-latest"
EVAL_TEMP      = 0.2
EVAL_SAMPLES   = 2
EVAL_RPM       = 20
EVAL_WORKERS   = 4

# Génération des mutations : Gemini (generativelanguage). Plus aucune dépendance Mistral.
MUTATION_MODEL = "gemini-3.1-flash-lite-preview"
MUTATION_TEMP  = 0.8
GEMINI_API_KEY   = ""
GEMINI_BASE_URL  = "https://generativelanguage.googleapis.com/v1beta"
# Conservés pour la compat de configure() — la mutation Mistral est désactivée.
MISTRAL_API_KEY  = ""
MISTRAL_BASE_URL = "https://api.mistral.ai/v1"

MAX_RETRIES    = 5
MAX_RETRY_WAIT = 300.0

# Renseignés par le notebook via configure()
RESPONSE_SCHEMA           = None   # schéma JSON attendu par l'adaptateur
cerema                    = None   # référence EMC² 2023 (dict chargé du YAML)
INITIAL_PROMPT_WORD_COUNT = 0      # nb de mots du prompt initial (informatif, affiché)
LENGTH_PENALTY_PER_WORD   = 0.05   # poids (faible) de la pénalité longueur, comparée à 0 mot
RESULTS_DIR               = Path("calibration_results")
EVAL_CACHE_DIR            = RESULTS_DIR / "eval_cache"   # cache d'évaluation adressé par contenu
EVAL_CACHE_ENABLED        = True                          # idempotence + reprise transparente après interruption

_eval_lock = threading.Lock()  # protège l'accès concurrent au rate limiter


def configure(**kwargs) -> None:
    """Renseigne les variables de configuration du module depuis le notebook.

    Exemple : ``configure(cerema=cerema, RESPONSE_SCHEMA=schema, EVAL_TEMP=0.2, …)``.
    Toute clé inconnue lève une erreur pour éviter les fautes de frappe silencieuses.
    """
    g = globals()
    for key, value in kwargs.items():
        if key not in g:
            raise KeyError(f"Clé de configuration inconnue : {key!r}")
        g[key] = value


# ════════════════════════════════════════════════════════════════════════════
# Palette & catégorisation des modes
# ════════════════════════════════════════════════════════════════════════════
MODES         = ["marche", "voiture", "velo", "transports_collectifs"]
MODE_COLORS   = {"marche": "#00CCCC", "voiture": "#EE4444",
                 "velo": "#8844BB", "transports_collectifs": "#22AA44"}
EXCLUDE_MODES = {"autres_modes", "autres"}


UNCATEGORIZED = "Autre"

# ── Vocabulaire des modes, par catégorie EMC² ────────────────────────────────
#
# ⚠ RECOPIE de `prompt_calibration/calibration/metrics.py` (`MODE_KEYWORDS`), qui est
# l'instrument de mesure de référence. Les deux ne peuvent pas s'importer l'une l'autre
# (`prompt_calibration/` est un dépôt autonome, hors du suivi de celui-ci) : c'est
# `scripts/tests/test_parite_modes.py` qui verrouille cette copie sur le journal de
# production, LU DANS SA SOURCE. Un littéral recopié dans un test ne tombe que si
# l'instrument change, jamais si la production change — l'asymétrie qui avait laissé
# passer le Téléo (2026-08-26) puis le rail (2026-09-04).
#
# L'ORDRE du tuple EST celui de la cascade : un libellé composé porte plusieurs modes
# (« foot,bus,foot » contient aussi « foot »), le tronçon structurant qualifie le trajet.
# Le rail est rangé avec les transports collectifs, comme `frames.CHOSEN_MODE_MAP["Train"]`
# et `model_on_common_set.CANONICAL_TO_CAT["train"]` — la référence EMC² du dépôt ne publie
# pas de part « train » distincte.
#
# La correspondance se fait par MOT et non par sous-chaîne : « car » désigne un autocar en
# français, et le réseau régional liO n'est composé que d'autocars.
MODE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("transports_collectifs", (
        "bus", "autobus", "metro", "métro", "subway", "tram", "tramway",
        "cableway", "gondola", "funicular",       # Téléo (route_type=6) et cousins portés
        "school_bus", "car scolaire",             # car scolaire synthétique (ticket 030)
        "rail", "train", "ter", "intercités", "intercites",   # TER (route_type=2)
        "autocar", "car lio", "coach",                        # cars liO (route_type=3)
        "transit", "public_transport", "transports_collectifs",
        "transports en commun", "transport en commun", "tc",
    )),
    ("voiture", ("car", "__car__", "voiture", "conducteur", "driving", "taxi")),
    ("velo", ("vélo", "velo", "bicycle", "bike", "cycling")),
    ("marche", ("marche", "foot", "walk", "walking", "pied", "à pied", "a pied")),
)


def _motif(mots: tuple[str, ...]):
    """Alternation encadrée de frontières de mot (lookarounds, pas `\\b` : « __car__ »
    commence par un caractère de mot et ne franchirait jamais une frontière `\\b`)."""
    alternation = "|".join(re.escape(mot) for mot in sorted(mots, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alternation})(?!\w)")


_MODE_PATTERNS = tuple((categorie, _motif(mots)) for categorie, mots in MODE_KEYWORDS)


def categorize_mode(m: str) -> str:
    """Normalise le mode brut renvoyé par le LLM vers une catégorie Cerema."""
    if not isinstance(m, str):
        return UNCATEGORIZED
    ml = m.lower()
    for categorie, motif in _MODE_PATTERNS:
        if motif.search(ml):
            return categorie
    return UNCATEGORIZED


# ════════════════════════════════════════════════════════════════════════════
# Extraction des métadonnées persona
# ════════════════════════════════════════════════════════════════════════════
# Mapping destination → motif Cerema (selected_mode_stats convention)
_DEST_TO_MOTIF = {
    "work":      "travail",
    "education": "etudes",
    "shop":      "achats",
    # leisure, other, home → pas de correspondance directe dans cerema motif_deplacement
}

# Inférence du genre par le prénom français
_FEM_ENDINGS = ("ette", "elle", "aine", "eine", "ine", "ise", "ène", "ère",
                "ance", "ence", "ie", "ia", "ice", "ille")
_MASC_ENDINGS = ("eau", "ry", "rd", "rt", "ux", "nt", "nc", "nd", "lt",
                 "ct", "st", "ot", "at", "au")
# Prénoms masculins courants se terminant par 'e' (exceptions à la règle du 'e' final)
_MASC_E_EXCEPTIONS = {
    "alexandre", "maxime", "guillaume", "baptiste", "claude", "dominique",
    "camille", "charlie", "gabriel", "sacha", "théodore", "philippe",
    "christophe", "luc", "marc", "olivier", "pierre", "xavier", "yves",
    "stéphane", "stephane", "jérôme", "jerome", "cédric", "cedric",
}


def infer_gender_from_name(first_name: str) -> str:
    """Renvoie 'Homme' ou 'Femme' par heuristique sur le prénom français."""
    name = first_name.strip().lower()
    for end in _FEM_ENDINGS:
        if name.endswith(end):
            return "Femme"
    for end in _MASC_ENDINGS:
        if name.endswith(end):
            return "Homme"
    if name.endswith("e") and name not in _MASC_E_EXCEPTIONS:
        return "Femme"
    return "Homme"


# Extraction de la distance minimale des options de trajet
_DIST_RE = re.compile(r'Distance\s*:\s*([\d.]+)\s*(km|m)\b', re.IGNORECASE)


def extract_min_distance_km(text: str) -> float | None:
    """Extrait la distance minimale (en km) parmi toutes les options de trajet du bloc persona."""
    dists = []
    for m in _DIST_RE.finditer(text):
        val = float(m.group(1))
        if m.group(2).lower() == "m":
            val /= 1000.0
        dists.append(val)
    return min(dists) if dists else None


def distance_to_cat(dist_km: float) -> str:
    """Bucket distance en catégories Cerema (labels identiques à cerema_values.yaml)."""
    for bp, label in [(1, "0-1km"), (2, "1-2km"), (5, "2-5km"),
                      (10, "5-10km"), (20, "10-20km"), (50, "20-50km")]:
        if dist_km < bp:
            return label
    return "plus_50km"


# Parser de métadonnées persona
# Groupes : (agent_id, destination, prénom+nom complet, âge, occupation)
PERSONA_RE = re.compile(
    r"---\s*PERSONA\s+(\d+)\s*\|\s*Destination\s*:\s*(\w+)\s*\|[^-]+---\s*\n\s*"
    r"([^,\n]+),\s*(\d+)\s*ans\s*,\s*([^(\n]+)",
    re.IGNORECASE
)

_OCC_MAP = [
    (["scolaire", "jusqu'au bac"],   "scolaire"),
    (["étudiant", "etudiant"],        "etudiant"),
    (["temps plein"],                  "actif_temps_plein"),
    (["temps partiel"],                "actif_temps_partiel"),
    (["chômeur", "recherche"],        "chomeur_recherche_emploi"),
    (["retraité", "retraite"],        "Retraité"),
    (["foyer"],                        "personne_au_foyer"),
]


def normalize_occupation(raw: str) -> str:
    occ = raw.strip().lower()
    for keys, label in _OCC_MAP:
        if any(k in occ for k in keys):
            return label
    return "autre"


def age_to_cat(age: int) -> str:
    for bp, label in [(9, "5-9"), (14, "10-14"), (19, "15-19"), (24, "20-24"), (29, "25-29"),
                      (34, "30-34"), (39, "35-39"), (44, "40-44"), (49, "45-49"), (54, "50-54"),
                      (59, "55-59"), (64, "60-64"), (69, "65-69"), (74, "70-74")]:
        if age <= bp:
            return label
    return "75-130"


def build_metadata_cache(entries: list[dict]) -> dict:
    cache = {}
    for entry in entries:
        full_msg = entry["messages"][1]["content"]
        # Découpe par bloc persona pour associer les distances au bon agent
        sections = re.split(r'(?=--- PERSONA)', full_msg)
        for section in sections:
            m = PERSONA_RE.match(section.lstrip())
            if not m:
                continue
            agent_id, dest_raw, name_raw, age_str, occ_raw = (
                m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
            )
            first_name = re.split(r'[-\s]', name_raw.strip())[0]
            dist_km    = extract_min_distance_km(section)
            cache[agent_id] = {
                "age":        int(age_str),
                "age_cat":    age_to_cat(int(age_str)),
                "occupation": normalize_occupation(occ_raw),
                "genre":      infer_gender_from_name(first_name),
                "motif":      _DEST_TO_MOTIF.get(dest_raw.lower()),
                "dist_km":    dist_km,
                "dist_cat":   distance_to_cat(dist_km) if dist_km is not None else None,
            }
    return cache


# ════════════════════════════════════════════════════════════════════════════
# Micro-batching des personas (météo injectée par bloc persona)
# ════════════════════════════════════════════════════════════════════════════
def split_entry_personas(user_msg: str) -> tuple[str, list[str]]:
    """Sépare le message utilisateur en (préambule contexte, [sections persona]).

    Le préambule (ex. « **Contexte :** Météo … ») précède le premier bloc PERSONA
    et sert de clé de regroupement. Chaque section persona commence par
    ``--- PERSONA``. Avec re.split en lookahead, seul le premier fragment peut être
    le préambule ; tous les autres sont des personas.
    """
    preamble = ""
    personas = []
    for part in re.split(r'(?=--- PERSONA)', user_msg):
        chunk = part.strip()
        if chunk.startswith('--- PERSONA'):
            personas.append(chunk)
        elif chunk:
            preamble = chunk
    return preamble, personas


_AGENT_ID_RE = re.compile(r'--- PERSONA\s+(\S+)')


def _persona_agent_id(section: str) -> str:
    """Extrait l'agent_id d'une section persona (`--- PERSONA <id> | … ---`)."""
    m = _AGENT_ID_RE.search(section)
    return m.group(1) if m else ""


def _inject_weather(section: str, preamble: str) -> str:
    """Insère le contexte météo (issu du préambule partagé de l'entrée) directement
    dans le bloc persona, juste après la ligne d'en-tête ``--- PERSONA … ---``.

    C'est ce qui rend possible la fusion de personas de météos DIFFÉRENTES dans un
    même lot : chacun conserve son propre contexte au lieu de dépendre d'un préambule
    commun au lot. Le label ``**Contexte :**`` est retiré (le bloc résultant commence
    déjà par « Météo : … »). Sans préambule, la section est renvoyée inchangée.
    """
    ctx = preamble.replace("**Contexte :**", "").strip()
    if not ctx:
        return section
    header, sep, rest = section.partition("\n")
    return f"{header}\n{ctx}\n{rest}" if sep else f"{header}\n{ctx}"


def build_micro_batches(entries: list[dict], batch_max_agents: int) -> list[dict]:
    """Regroupe les personas de plusieurs entrées en lots de taille ≤ ``batch_max_agents``.

    But : réduire drastiquement le nombre de requêtes LLM, essentiel pour un provider
    à faible RPM comme Gemini (15 req/min) où une requête par persona serait prohibitif.

    Le contexte météo de chaque entrée est injecté DANS le bloc persona correspondant
    (cf. :func:`_inject_weather`) plutôt que placé en préambule partagé. Des personas de
    météos différentes peuvent donc cohabiter dans un même lot sans perdre leur contexte
    propre, ce qui permet de remplir les lots jusqu'à la capacité du provider (et non
    plus jusqu'à épuisement d'un même préambule météo — qui limitait à ~2 personas/lot).

    Le multiset complet de personas est préservé (même pondération que l'échantillonnage
    d'origine), MAIS un même ``agent_id`` n'apparaît jamais deux fois dans un même lot :
    sinon la réponse JSON (un objet par agent_id) écraserait l'un des doublons. Les copies
    d'un agent récurrent sont donc réparties sur des lots distincts (placement glouton).

    Chaque lot retourné est une entrée synthétique compatible :func:`call_entry` :
    ``messages=[{"role":"system","content":""}, {"role":"user","content":<personas>}]``.
    """
    cap = max(1, batch_max_agents)
    # Pool global : chaque persona porte désormais sa propre météo → aucune contrainte
    # de regroupement par préambule, les lots se remplissent jusqu'à `cap`.
    sections_pool: list[str] = []
    for entry in entries:
        preamble, personas = split_entry_personas(entry["messages"][1]["content"])
        for section in personas:
            sections_pool.append(_inject_weather(section, preamble))

    # Lots ouverts : (liste de sections, set des agent_id présents) — placement glouton.
    open_batches: list[tuple[list[str], set[str]]] = []
    for section in sections_pool:
        aid = _persona_agent_id(section)
        placed = False
        for sections, ids in open_batches:
            if len(sections) < cap and aid not in ids:
                sections.append(section)
                ids.add(aid)
                placed = True
                break
        if not placed:
            open_batches.append(([section], {aid}))

    batches = []
    for sections, _ in open_batches:
        content = "\n\n".join(sections)
        batches.append({"messages": [
            {"role": "system", "content": ""},
            {"role": "user",   "content": content},
        ]})
    return batches


# ════════════════════════════════════════════════════════════════════════════
# Décomposition du prompt en blocs
# ════════════════════════════════════════════════════════════════════════════
# Regex de découpe en phrases françaises : split après .!? suivi d'espace/newline + majuscule
_SENT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-ZÀÂÄÉÈÊËÎÏÔÙÛÜ])')


def split_sentences(txt: str) -> list[str]:
    """Découpe un texte en phrases sur frontière .!? + majuscule."""
    return [s.strip() for s in _SENT_RE.split(txt.strip()) if s.strip()]


def decompose_prompt(text: str) -> list[dict]:
    """Décompose le prompt en blocs au niveau phrase. Le schéma JSON est non-mutable."""
    blocks = []
    sections = [s.strip() for s in re.split(r'\n\n+', text) if s.strip()]

    # Localiser le schéma JSON (non-mutable)
    schema_start = None
    for i, s in enumerate(sections):
        if ('"type"' in s and '"properties"' in s) or 'Schéma JSON' in s:
            schema_start = i
            break

    content_secs = sections[:schema_start] if schema_start is not None else sections
    schema_text  = '\n\n'.join(sections[schema_start:]) if schema_start is not None else None

    bullet_count = 0
    intro_count  = 0
    block_idx    = 0

    for section in content_secs:
        lines = [l.strip() for l in section.split('\n') if l.strip()]
        if not lines:
            continue

        if any(l.startswith('- ') for l in lines):
            # Section avec puces : traite les lignes dans l'ordre pour préserver
            # la position relative des puces (ex: bullet entre étape 2 et étape 3).
            i = 0
            while i < len(lines):
                if lines[i].startswith('- '):
                    bullet_count += 1
                    blocks.append({"name": f"bullet_{bullet_count}", "mutable": True, "content": lines[i]})
                    i += 1
                else:
                    # Collecte un run continu de lignes non-puce
                    header_run = []
                    while i < len(lines) and not lines[i].startswith('- '):
                        header_run.append(lines[i])
                        i += 1
                    for sent in split_sentences('\n'.join(header_run)):
                        idx = sum(1 for b in blocks if b['name'].startswith('consigne_s'))
                        blocks.append({"name": f"consigne_s{idx + 1}", "mutable": True, "content": sent})

        elif re.search(r'Instructions\s*:', section) or (lines and re.match(r'\d+\.', lines[0])):
            # Bloc instructions : header séparé + chaque item numéroté = un bloc
            instr_m = re.match(r'^(Instructions\s*:)\s*\n?', section)
            remainder = section
            if instr_m:
                blocks.append({"name": "instr_header", "mutable": True,
                               "content": instr_m.group(1)})
                remainder = section[instr_m.end():]
            for item in re.split(r'\n(?=\d+\.)', remainder.strip()):
                item = item.strip()
                if not item:
                    continue
                m = re.match(r'^(\d+)\.', item)
                name = f"instr_{m.group(1)}" if m else "instr_misc"
                blocks.append({"name": name, "mutable": True, "content": item})

        elif not any(b['name'].startswith('intro_s') for b in blocks):
            # Premier bloc de prose → intro, une phrase = un bloc
            for sent in split_sentences(section):
                intro_count += 1
                blocks.append({"name": f"intro_s{intro_count}", "mutable": True, "content": sent})

        else:
            # Autres sections prose → block_N_sM
            block_idx += 1
            for i, sent in enumerate(split_sentences(section), 1):
                blocks.append({"name": f"block_{block_idx}_s{i}", "mutable": True, "content": sent})

    if schema_text:
        blocks.append({"name": "json_schema", "mutable": False, "content": schema_text})

    return blocks


def blocks_to_prompt(blocks: list[dict]) -> str:
    """Reconstruit le prompt. Les phrases d'un même groupe (même préfixe) sont réunies en paragraphe."""
    def group_key(name: str) -> str:
        if re.match(r'intro_s\d+', name):       return "intro"
        if re.match(r'consigne_s\d+', name):    return "consigne"
        if re.match(r'instr_', name):            return "instr"
        m = re.match(r'(block_\d+)_s\d+', name)
        if m:                                    return m.group(1)
        return name  # bullet_N, json_schema → paragraphe isolé

    paragraphs = []
    for key, group in groupby((b for b in blocks if b["content"].strip()), key=lambda b: group_key(b["name"])):
        items = [b["content"].strip() for b in group]
        # Puces et instructions : séparées par \n ; prose : séparée par espace
        sep = "\n" if key.startswith("bullet") or key == "instr" else " "
        paragraphs.append(sep.join(items))
    return "\n\n".join(paragraphs)


def display_blocks(blocks: list[dict]) -> None:
    print("═" * 65)
    for b in blocks:
        icon = "🔒" if not b["mutable"] else "✏ "
        print(f"\n{icon} [{b['name']}]")
        print("─" * 40)
        print(b["content"])
    print("\n" + "═" * 65)


# ════════════════════════════════════════════════════════════════════════════
# Scoring composite vs EMC² 2023
# ════════════════════════════════════════════════════════════════════════════
def l1_error(actual: pd.Series, reference: dict) -> float:
    """Erreur L1 entre distribution LLM et référence Cerema (en points de %)."""
    ref = {k: v for k, v in reference.items() if k not in EXCLUDE_MODES}
    ref_sum = sum(ref.values())
    if ref_sum == 0:
        return 0.0
    ref_norm = {k: v * 100.0 / ref_sum for k, v in ref.items()}
    total = actual.sum()
    if total == 0:
        return sum(ref_norm.values())
    return sum(abs(actual.get(m, 0) / total * 100 - ref_norm.get(m, 0)) for m in MODES)


def compute_composite_score(df: pd.DataFrame, cerema: dict,
                            prompt_text: str = "") -> dict:
    """Score composite sur toutes les dimensions Cerema disponibles + pénalité longueur."""
    if df.empty or "mode_cat" not in df.columns:
        return {"global": 0.0, "age": 0.0, "occupation": 0.0, "genre": 0.0,
                "motif": 0.0, "distance": 0.0, "absent_penalty": 0.0,
                "length_penalty": 0.0, "composite": 0.0}

    parts  = cerema["parts_modales_2023"]
    scores = {}

    # ── Global ───────────────────────────────────────────────────────────────
    scores["global"] = l1_error(df["mode_cat"].value_counts(), parts["global"])

    # ── Pénalité mode absent (×5 de la cible Cerema) ─────────────────────────
    mode_counts = df["mode_cat"].value_counts()
    cerema_g    = parts["global"]
    scores["absent_penalty"] = float(sum(
        5 * cerema_g.get(m, 0) for m in MODES if mode_counts.get(m, 0) == 0
    ))

    # ── Par âge ──────────────────────────────────────────────────────────────
    age_errs = [
        l1_error(df[df["age_cat"] == cat]["mode_cat"].value_counts(), ref)
        for cat, ref in parts["Age"].items()
        if df[df["age_cat"] == cat]["mode_cat"].count() >= 5
    ]
    scores["age"] = float(np.mean(age_errs)) if age_errs else 0.0

    # ── Par occupation ───────────────────────────────────────────────────────
    occ_errs = [
        l1_error(df[df["occupation"] == occ]["mode_cat"].value_counts(), ref)
        for occ, ref in parts["occupation"].items()
        if df[df["occupation"] == occ]["mode_cat"].count() >= 5
    ]
    scores["occupation"] = float(np.mean(occ_errs)) if occ_errs else 0.0

    # ── Par genre (Homme / Femme) ─────────────────────────────────────────────
    if "genre" in df.columns:
        genre_errs = [
            l1_error(df[df["genre"] == cat]["mode_cat"].value_counts(), ref)
            for cat, ref in parts["genre"].items()
            if df[df["genre"] == cat]["mode_cat"].count() >= 5
        ]
        scores["genre"] = float(np.mean(genre_errs)) if genre_errs else 0.0
    else:
        scores["genre"] = 0.0

    # ── Par motif de déplacement (travail / etudes / achats) ─────────────────
    if "motif" in df.columns:
        motif_errs = [
            l1_error(df[df["motif"] == cat]["mode_cat"].value_counts(), ref)
            for cat, ref in parts["motif_deplacement"].items()
            if df[df["motif"] == cat]["mode_cat"].count() >= 5
        ]
        scores["motif"] = float(np.mean(motif_errs)) if motif_errs else 0.0
    else:
        scores["motif"] = 0.0

    # ── Par distance ─────────────────────────────────────────────────────────
    if "dist_cat" in df.columns:
        dist_errs = [
            l1_error(df[df["dist_cat"] == cat]["mode_cat"].value_counts(), ref)
            for cat, ref in parts["distance"].items()
            if df[df["dist_cat"] == cat]["mode_cat"].count() >= 5
        ]
        scores["distance"] = float(np.mean(dist_errs)) if dist_errs else 0.0
    else:
        scores["distance"] = 0.0

    # ── Pénalité longueur du prompt ──────────────────────────────────────────
    # Comparée à 0 mot (longueur totale), avec un poids volontairement faible :
    # simple incitation à la concision, jamais au point d'écraser un gain de score.
    if prompt_text:
        scores["length_penalty"] = len(prompt_text.split()) * LENGTH_PENALTY_PER_WORD
    else:
        scores["length_penalty"] = 0.0

    scores["composite"] = (
        scores["global"]
        + scores["absent_penalty"]
        + scores["age"]        * 0.5
        + scores["occupation"] * 0.5
        + scores["genre"]      * 0.3
        + scores["motif"]      * 0.5
        + scores["distance"]   * 0.3
        + scores["length_penalty"]
    )
    return scores


# ── Pires croisements strate × mode (granularité fine pour la mutation) ─────
# Dimensions strate : (label, colonne df, clé cerema parts_modales_2023)
_STRATA_DIMS = [
    ("age",        "age_cat",    "Age"),
    ("occupation", "occupation", "occupation"),
    ("genre",      "genre",      "genre"),
    ("motif",      "motif",      "motif_deplacement"),
    ("distance",   "dist_cat",   "distance"),
]


def worst_strata_modes(df: pd.DataFrame, cerema: dict, top_k: int = 6,
                       min_count: int = 5) -> list[dict]:
    """Pires croisements strate x mode (ecart signe actuel-cible le plus fort).

    Parcourt chaque dimension/categorie disposant d'au moins `min_count` decisions,
    calcule pour chaque mode l'ecart en points de % vs la reference Cerema normalisee,
    et renvoie les `top_k` plus gros ecarts en valeur absolue. C'est cette information
    fine (perdue dans la moyenne de compute_composite_score) qui permet au LLM de
    mutation de cibler la strate ET le mode les plus mal predits.
    """
    if df.empty or "mode_cat" not in df.columns:
        return []
    parts = cerema["parts_modales_2023"]
    rows = []
    for dim_label, col, cerema_key in _STRATA_DIMS:
        if col not in df.columns or cerema_key not in parts:
            continue
        for cat, ref in parts[cerema_key].items():
            sub   = df[df[col] == cat]["mode_cat"]
            total = sub.count()
            if total < min_count:
                continue
            ref_clean = {k: v for k, v in ref.items() if k not in EXCLUDE_MODES}
            ref_sum   = sum(ref_clean.values())
            if ref_sum == 0:
                continue
            counts = sub.value_counts()
            for m in MODES:
                actual = counts.get(m, 0) / total * 100
                target = ref_clean.get(m, 0) * 100.0 / ref_sum
                diff = actual - target
                rows.append({
                    "dim": dim_label, "cat": cat, "mode": m,
                    "actual": actual, "target": target,
                    "diff": diff, "n": int(total),
                    # #6 — impact ≈ écart × effectif : une strate n=40 pèse bien plus
                    # sur la distribution globale qu'une strate n=5 au même écart.
                    "impact": abs(diff) * int(total),
                })
    rows.sort(key=lambda r: r["impact"], reverse=True)
    return rows[:top_k]


def format_worst_strata(rows: list[dict]) -> str:
    """Formate les pires strate x mode pour le user_msg de mutation."""
    if not rows:
        return ""
    lines = ["\n⚠️ Pires ecarts strate x mode (actuel vs cible EMC2, impact |Δ|×n decroissant) :"]
    for r in rows:
        direction = "sur-represente" if r["diff"] > 0 else "sous-represente"
        lines.append(
            f"  {r['dim']}[{r['cat']}] · {r['mode']:22s} : {r['diff']:+5.1f} pts "
            f"({direction}, actuel={r['actual']:.0f}% cible={r['target']:.0f}%, n={r['n']})"
        )
    return "\n".join(lines) + "\n"


def _normalized_global_gaps(dist_counts: pd.Series, cerema: dict) -> dict:
    """Écart (actuel − cible) en points de % par mode vs EMC² global normalisé."""
    ref = {k: v for k, v in cerema["parts_modales_2023"]["global"].items()
           if k not in EXCLUDE_MODES}
    ref_sum = sum(ref.values()) or 1
    total   = dist_counts.sum() or 1
    gaps = {}
    for m in MODES:
        actual = dist_counts.get(m, 0) / total * 100
        target = ref.get(m, 0) * 100.0 / ref_sum
        gaps[m] = actual - target
    return gaps


# ════════════════════════════════════════════════════════════════════════════
# Évaluation parallèle d'un prompt
# ════════════════════════════════════════════════════════════════════════════
def _parse_ratelimit_reset(value: str | None, default: int = 60) -> int:
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


def call_entry(entry: dict, system_prompt: str) -> list[dict]:
    raw = entry["messages"]
    msgs = [InternalMessage(role=m["role"],
                            content=(system_prompt if i == 0 else m["content"]))
            for i, m in enumerate(raw)]
    req = InternalRequest(provider=EVAL_PROVIDER, messages=msgs,
                          response_schema=RESPONSE_SCHEMA, temperature=EVAL_TEMP)
    out, _, _ = get_adapter(EVAL_PROVIDER).call(req)
    return [{"agent_id": a.agent_id, "mode": a.mode} for a in out.agents]


def call_with_retry(entry: dict, system_prompt: str) -> list[dict]:
    parse_tries = 0
    for attempt in range(MAX_RETRIES + 1):
        try:
            return call_entry(entry, system_prompt)
        except ProviderClientError as exc:
            if exc.status_code == 429 and attempt < MAX_RETRIES:
                wait = _parse_ratelimit_reset(getattr(exc, "ratelimit_reset", None))
                if wait > MAX_RETRY_WAIT:
                    raise
                print(f"  Rate limit → {wait}s")
                time.sleep(wait)
            else:
                raise
        except ProviderServerError:
            if attempt < MAX_RETRIES:
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


def eval_cache_key(entries: list[dict], system_prompt: str) -> str:
    """Clé de cache adressée par contenu pour une évaluation.

    Couvre tout ce qui détermine le résultat : le prompt système, le contenu de chaque
    entrée (micro-batch) et les paramètres de décodage/provider. Deux évaluations
    distinctes (run initial, ablation, itération, validation) qui partagent le même
    prompt ET les mêmes entrées tombent donc sur la même clé — et ne sont calculées
    qu'une seule fois.
    """
    h = hashlib.sha256()
    h.update(system_prompt.encode("utf-8"))
    h.update(f"|temp={EVAL_TEMP}|samples={EVAL_SAMPLES}"
             f"|prov={EVAL_PROVIDER}|model={EVAL_MODEL}".encode("utf-8"))
    for e in entries:
        h.update(b"\x00")
        h.update(e["messages"][1]["content"].encode("utf-8"))
    return h.hexdigest()[:16]


def mutation_cache_load(path: Path) -> dict:
    """Recharge le journal des mutations (JSONL) en dict {iteration: mutation}."""
    cache: dict[int, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            cache[int(rec["iteration"])] = rec["mutation"]
    return cache


def mutation_cache_append(path: Path, iteration: int, mutation: dict) -> None:
    """Ajoute une mutation au journal JSONL (append-only, une ligne par itération)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"iteration": iteration, "mutation": mutation},
                           ensure_ascii=False) + "\n")


def run_evaluation(entries: list[dict], system_prompt: str,
                   metadata_cache: dict, desc: str = "Eval") -> pd.DataFrame:
    """Exécute les entrées en parallèle (EVAL_WORKERS threads) avec rate limiting.

    Idempotent : le résultat est mis en cache sur disque, adressé par le contenu
    (cf. :func:`eval_cache_key`). Sur une ré-exécution (même après redémarrage de la
    machine), un résultat déjà calculé est rechargé du disque — aucun appel LLM — et
    signalé par « retrieved from previous session ». C'est ce qui rend toute la
    pipeline reprenable au point d'interruption sans recalcul.
    """
    cache_path = None
    if EVAL_CACHE_ENABLED:
        EVAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = EVAL_CACHE_DIR / f"{eval_cache_key(entries, system_prompt)}.csv"
        if cache_path.exists():
            df_cached = pd.read_csv(cache_path, dtype={"agent_id": str})
            print(f"  ↺ retrieved from previous session — {desc} "
                  f"({len(df_cached)} décisions, key={cache_path.stem})")
            return df_cached

    inter_req_delay = 60.0 / EVAL_RPM  # délai minimum entre requêtes
    rows = []
    last_call_time = [0.0]  # mutable pour closure

    def _throttled_call(entry):
        with _eval_lock:
            elapsed = time.monotonic() - last_call_time[0]
            wait = inter_req_delay - elapsed
            if wait > 0:
                time.sleep(wait)
            last_call_time[0] = time.monotonic()
        return call_with_retry(entry, system_prompt)

    with ThreadPoolExecutor(max_workers=EVAL_WORKERS) as executor:
        # #1 — chaque entrée est tirée EVAL_SAMPLES fois ; toutes les décisions
        # sont mises en commun pour estimer la distribution avec moins de variance.
        futures = {executor.submit(_throttled_call, e): e
                   for e in entries for _ in range(EVAL_SAMPLES)}
        for fut in tqdm(as_completed(futures), total=len(futures), desc=desc):
            try:
                for a in fut.result():
                    entry = futures[fut]
                    meta  = metadata_cache.get(str(a["agent_id"]), {})
                    rows.append({
                        "agent_id":   a["agent_id"],
                        "mode":       a["mode"],
                        "mode_cat":   categorize_mode(a["mode"]),
                        "age":        meta.get("age"),
                        "age_cat":    meta.get("age_cat"),
                        "occupation": meta.get("occupation"),
                        "genre":      meta.get("genre"),
                        "motif":      meta.get("motif"),
                        "dist_cat":   meta.get("dist_cat"),
                    })
            except Exception as exc:
                print(f"  ⚠ {exc}")

    df = pd.DataFrame(rows)
    # On ne met en cache qu'un résultat non vide : un df vide signale un échec réseau
    # (toutes les requêtes ont raté) qu'il faut pouvoir ré-essayer au run suivant.
    if cache_path is not None and not df.empty:
        df.to_csv(cache_path, index=False)
    return df


# ════════════════════════════════════════════════════════════════════════════
# Ablation des blocs
# ════════════════════════════════════════════════════════════════════════════
def ablation_regression_diagnostic(ref_scores: dict, abl_scores: dict,
                                    ref_df: pd.DataFrame | None,
                                    abl_df: pd.DataFrame | None,
                                    cerema: dict) -> str:
    """Explique EN QUOI un bloc nuisible fait régresser le score.

    Un bloc est « nuisible » quand sa suppression améliore le composite. Cette fonction
    remonte les deux canaux de régression exploitables par le mutateur :
      • les dimensions L1 qui s'améliorent le plus à la suppression du bloc ;
      • le mode dont l'écart EMC² se résorbe le plus (le bloc le sur- ou sous-pousse).
    """
    parts = []

    # Dimensions L1 qui s'améliorent à la suppression (delta négatif = mieux sans le bloc)
    dims = ["global", "age", "occupation", "genre", "motif", "distance"]
    dim_deltas = [(d, abl_scores.get(d, 0.0) - ref_scores.get(d, 0.0)) for d in dims]
    improved = sorted([x for x in dim_deltas if x[1] < -0.5], key=lambda x: x[1])[:2]
    if improved:
        parts.append("dim " + ", ".join(f"{d} {v:+.1f}" for d, v in improved))

    # Mode EMC² sur/sous-poussé : réduction du |écart| à la suppression
    if (ref_df is not None and abl_df is not None
            and not ref_df.empty and not abl_df.empty):
        g_ref = _normalized_global_gaps(ref_df["mode_cat"].value_counts(), cerema)
        g_abl = _normalized_global_gaps(abl_df["mode_cat"].value_counts(), cerema)
        reductions = [(m, abs(g_ref[m]) - abs(g_abl[m])) for m in MODES]
        reductions.sort(key=lambda x: x[1], reverse=True)
        m, gain = reductions[0]
        if gain > 1.0:
            sens = "sur-pousse" if g_ref[m] > 0 else "sous-pousse"
            parts.append(f"{sens} {m} ({g_ref[m]:+.0f}→{g_abl[m]:+.0f} pts vs cible)")

    return " · ".join(parts)


def build_ablation_result(bloc: str, content: str, abl_scores: dict, ref_score: float,
                          ref_scores: dict | None = None,
                          abl_df: pd.DataFrame | None = None,
                          ref_df: pd.DataFrame | None = None,
                          cerema: dict | None = None) -> dict:
    """Construit le dict de résultat d'ablation d'un bloc, avec diagnostic de régression.

    Utilisé à la fois par run_ablation (recalcul complet) et par la mise à jour locale
    de l'ablation dans la boucle d'optimisation — garantit un format identique.
    """
    delta = abl_scores["composite"] - ref_score
    diag  = ""
    if delta < -2 and ref_scores is not None and cerema is not None:
        diag = ablation_regression_diagnostic(ref_scores, abl_scores, ref_df, abl_df, cerema)
    return {
        "bloc":    bloc,
        "content": content,
        "score":   abl_scores["composite"],
        "delta":   delta,
        "useful":  delta > 2,
        "harmful": delta < -2,
        "diag":    diag,
    }


def _ablation_verdict(delta: float) -> str:
    if delta > 2:
        return "🔑 UTILE     — supprimer ↑ dégrade  → garder"
    if delta < -2:
        return "🗑  NUISIBLE — supprimer ↓ améliore → réécrire/supprimer"
    return "≈  neutre"


def run_ablation(blocks: list[dict], entries: list[dict], metadata_cache: dict,
                 reference: dict, ref_score: float,
                 ref_scores: dict | None = None, ref_df: pd.DataFrame | None = None,
                 label: str = "Ablation") -> list[dict]:
    """Supprime chaque bloc mutable un par un et évalue l'impact sur le score.

    `ref_scores` / `ref_df` (scores et distribution du prompt de référence) servent au
    diagnostic de régression des blocs nuisibles (cf. ablation_regression_diagnostic).

    L'idempotence et la reprise sont entièrement déléguées au cache adressé par contenu
    de :func:`run_evaluation` : chaque prompt ablaté a une clé distincte, donc un bloc
    déjà évalué (même après redémarrage) est rechargé du disque sans appel LLM.
    """
    results = []
    for block in blocks:
        if not block["mutable"]:
            continue

        ablated        = [b for b in blocks if b["name"] != block["name"]]
        ablated_prompt = blocks_to_prompt(ablated)
        df_abl         = run_evaluation(entries, ablated_prompt, metadata_cache,
                                        desc=f"{label} [{block['name']}]")
        scores = compute_composite_score(df_abl, reference, prompt_text=ablated_prompt)
        result = build_ablation_result(block["name"], block["content"], scores, ref_score,
                                       ref_scores=ref_scores, abl_df=df_abl,
                                       ref_df=ref_df, cerema=reference)
        delta = result["delta"]

        content_preview = block["content"].replace("\n", " ")
        print(f"  {block['name']:22s}  Δ={delta:+7.2f}  {_ablation_verdict(delta)}")
        if result.get("diag"):
            print(f"    ↳ régression : {result['diag']}")
        print(f"    ↳ {content_preview[:110]}{'…' if len(block['content']) > 110 else ''}")

        results.append(result)

    return sorted(results, key=lambda r: r["delta"], reverse=True)


def format_ablation_for_mutation(ablation_results: list[dict]) -> str:
    """Formate les résultats d'ablation pour guider le prompt de mutation.

    Pour chaque bloc NUISIBLE, remonte aussi le diagnostic de régression (dimensions
    et mode EMC² dégradés) afin que le mutateur cible le bon levier.
    """
    if not ablation_results:
        return ""
    harmful = [r for r in ablation_results if r["harmful"]]
    useful  = [r for r in ablation_results if r["useful"]]
    lines   = ["\nAnalyse d'ablation initiale (impact de chaque bloc sur le score) :"]
    if harmful:
        lines.append("  🗑 Blocs NUISIBLES — supprimer ou réécrire en priorité :")
        for r in harmful:
            preview = r["content"].replace("\n", " ")[:90]
            diag    = f" — fait régresser via {r['diag']}" if r.get("diag") else ""
            lines.append(f"    • {r['bloc']} (Δ={r['delta']:+.1f}){diag} : {preview}")
    if useful:
        lines.append("  🔑 Blocs UTILES — modifier avec précaution :")
        for r in useful:
            preview = r["content"].replace("\n", " ")[:90]
            lines.append(f"    • {r['bloc']} (Δ={r['delta']:+.1f}) : {preview}")
    return "\n".join(lines) + "\n"


# ════════════════════════════════════════════════════════════════════════════
# Génération de mutations via Mistral
# ════════════════════════════════════════════════════════════════════════════
_MUTATION_SYSTEM = """\
Tu es un expert en calibration de prompts pour des agents LLM simulant des comportements de déplacement urbain à Toulouse.

Ton rôle : proposer des modifications textuelles ciblées au prompt système afin de rapprocher la distribution modale produite par le LLM de la référence EMC² 2023 Toulouse.

Contraintes absolues :
- N'introduis JAMAIS de pourcentages, de fréquences ou de parts modales explicites dans le prompt.
- N'introduis JAMAIS de règle à seuil chiffré ni de table de correspondance distance→mode (p. ex. « si trajet < 1 km alors marche », « au-delà de X km, exclure le vélo »). Le choix doit rester un raisonnement comportemental contextuel, jamais un automatisme déterministe lié à la distance.
- Les modifications doivent reposer uniquement sur des facteurs comportementaux (coût, confort, santé, praticité, sécurité, habitudes, contraintes familiales…).
- Modifie UN SEUL bloc à la fois, avec l'action "modify", "delete" ou "insert".
  • "modify" : remplace le contenu d'un bloc existant par un nouveau texte.
  • "delete" : supprime un bloc nuisible ou redondant.
  • "insert" : crée un nouveau bloc inséré APRÈS target_block (ne pas utiliser après "json_schema").
- Ne répète pas une mutation déjà rejetée.
- La mutation doit aider le LLM à considérer TOUS les modes disponibles (marche, voiture, vélo, transports collectifs). Deux leviers comptent autant l'un que l'autre : RENFORCER les arguments comportementaux d'un mode sous-représenté ET ATTÉNUER ceux qui poussent vers un mode sur-représenté. Cible en priorité les deux modes signalés dans le message utilisateur.
- Deux priorités, dans cet ordre : (1) réduire l'écart à la distribution EMC² (le score composite) ; (2) raccourcir le prompt — cherche à condenser et à retirer le superflu dès que possible, sans jamais dégrader le score. Si rallonger un bloc fait baisser le score, fais-le : la concision reste une priorité secondaire.

Tu réponds UNIQUEMENT avec un objet JSON valide, sans markdown ni texte supplémentaire.\
"""


def _build_gap_description(df: pd.DataFrame | None) -> tuple[str, str, str]:
    """Construit la description de la distribution actuelle, des écarts et du mode prioritaire."""
    cerema_g = cerema["parts_modales_2023"]["global"]
    if df is None or len(df) == 0:
        return "(premier run, pas de données)", "(inconnu)", ""
    total = len(df)
    dist  = df["mode_cat"].value_counts()
    dist_lines = [
        f"  {m}: {dist.get(m, 0) / total * 100:.1f}%  (cible EMC²: {cerema_g.get(m, '?')}%)"
        for m in MODES
    ]
    gaps = []
    for m in MODES:
        actual = dist.get(m, 0) / total * 100
        target = cerema_g.get(m, 0)
        diff   = actual - target
        if abs(diff) > 2:
            direction = "sur-représenté" if diff > 0 else "sous-représenté"
            gaps.append(f"{m} {direction} de {abs(diff):.1f} pts")

    def pct(m):
        return dist.get(m, 0) / total * 100

    # #6 — deux leviers prioritaires : le mode le plus sous-représenté (à renforcer)
    # et le plus sur-représenté (à atténuer). Auparavant un seul mode était ciblé,
    # ce qui faisait sur-pousser la marche en ignorant l'excès de vélo.
    under = min(MODES, key=lambda m: pct(m) - cerema_g.get(m, 0))   # plus négatif = plus sous-représenté
    over  = max(MODES, key=lambda m: pct(m) - cerema_g.get(m, 0))   # plus positif  = plus sur-représenté
    under_absent = " (ABSENT)" if dist.get(under, 0) == 0 else ""
    worst_str = (
        "⚠️ DEUX leviers prioritaires (les deux comptent autant) :\n"
        f"  • RENFORCER : {under}{under_absent} "
        f"(actuel={pct(under):.1f}%, cible={cerema_g.get(under, '?')}%, "
        f"manque {cerema_g.get(under, 0) - pct(under):+.1f} pts)\n"
        f"  • ATTÉNUER  : {over} "
        f"(actuel={pct(over):.1f}%, cible={cerema_g.get(over, '?')}%, "
        f"excès {pct(over) - cerema_g.get(over, 0):+.1f} pts)"
    )

    return "\n".join(dist_lines), "\n  ".join(gaps) if gaps else "  proche de la cible", worst_str


def format_dimension_scores(scores: dict) -> str:
    """Résumé des scores L1 par dimension (↓ mieux, contribution = L1 × poids).

    Utilisé à la fois pour guider la mutation et pour l'affichage de présentation.
    """
    if not scores:
        return ""
    dims = [
        ("global",         scores.get("global",         0.0), 1.0),
        ("age",            scores.get("age",            0.0), 0.5),
        ("occupation",     scores.get("occupation",     0.0), 0.5),
        ("genre",          scores.get("genre",          0.0), 0.3),
        ("motif",          scores.get("motif",          0.0), 0.5),
        ("distance",       scores.get("distance",       0.0), 0.3),
        ("absent_penalty", scores.get("absent_penalty", 0.0), 1.0),
        ("length_penalty", scores.get("length_penalty", 0.0), 1.0),
    ]
    lines = ["\nScores L1 par dimension (↓ mieux, contribution = L1 × poids) :"]
    for name, val, weight in dims:
        contrib = val * weight
        bar     = "█" * min(int(contrib / 2), 20)
        lines.append(f"  {name:20s}  L1={val:5.1f}  ×{weight:.1f}  → {contrib:5.1f}  {bar}")
    lines.append(f"  {'COMPOSITE':20s}                   = {scores.get('composite', 0.0):5.1f}")
    return "\n".join(lines) + "\n"


# Alias interne historique (le prompt de mutation appelle encore ce nom).
_build_dimension_str = format_dimension_scores


def _build_history_summary(history: list[dict]) -> str:
    """Résumé compact des mutations passées (20 dernières) pour guider Mistral."""
    past = [h for h in history if h.get("mutation") and h["iteration"] > 0]
    if not past:
        return ""
    lines = []
    for h in past[-20:]:
        m    = h["mutation"]
        icon = "✅" if h["kept"] else "↩"
        s    = h["scores"]
        # #7 — détail par dimension : le mutateur voit QUELLE dimension sa tentative a dégradée
        # (ex : une poussée pro-marche qui fait exploser 'motif'), pour ne pas répéter l'erreur.
        dims = (f"g{s.get('global',0):.0f} ag{s.get('age',0):.0f} oc{s.get('occupation',0):.0f} "
                f"ge{s.get('genre',0):.0f} mo{s.get('motif',0):.0f} di{s.get('distance',0):.0f}")
        lines.append(
            f"  iter {h['iteration']:>2} | {icon} | bloc={m.get('target_block','?'):18s} | "
            f"comp={s['composite']:.1f} [{dims}] | {m.get('rationale', '')[:80]}"
        )
    return (
        "\nHistorique des mutations (✅=acceptée ↩=rejetée — ne répète pas une tentative rejetée).\n"
        "Codes dimensions L1 (↓ mieux) : g=global ag=âge oc=occupation ge=genre mo=motif di=distance :\n"
        + "\n".join(lines) + "\n"
    )


def generate_mutation(blocks: list[dict], df_current: pd.DataFrame | None,
                      best_score: float | None, history: list[dict] | None = None,
                      ablation_results: list[dict] | None = None,
                      dim_scores: dict | None = None) -> dict:
    """Appelle Mistral pour proposer une mutation d'un bloc, avec retry sur 429."""
    dist_str, gap_str, worst_str = _build_gap_description(df_current)
    dim_str       = _build_dimension_str(dim_scores) if dim_scores else ""
    mutable_names = [b["name"] for b in blocks if b["mutable"]]
    blocks_display = "\n\n".join(
        f"=== {b['name']} ===\n{b['content']}"
        for b in blocks if b["mutable"]
    )
    score_str    = f"Score composite actuel (meilleur) : {best_score:.2f}" if best_score is not None else "Premier run"
    history_str  = _build_history_summary(history) if history else ""
    ablation_str = format_ablation_for_mutation(ablation_results) if ablation_results else ""
    worst_strata_str = (format_worst_strata(worst_strata_modes(df_current, cerema))
                        if df_current is not None else "")

    user_msg = f"""Distribution LLM actuelle ({len(df_current) if df_current is not None else 0} décisions) :
{dist_str}

Écarts vs EMC² 2023 :
  {gap_str}

{worst_str}
{worst_strata_str}
{score_str}
{dim_str}
{history_str}{ablation_str}
Blocs modifiables (état actuel du meilleur prompt) :
{blocks_display}

Options de bloc : {mutable_names}

Propose UNE modification sur UN SEUL bloc agissant sur les DEUX leviers prioritaires ci-dessus (renforcer le mode sous-représenté ET/OU atténuer le mode sur-représenté), sans jamais introduire de seuil chiffré ni de règle distance→mode. JSON attendu :
{{"target_block":"<nom>","action":"modify"|"delete"|"insert","new_content":"<texte si modify/insert>","rationale":"<1 phrase>"}}"""

    print("\n── user_msg envoyé au LLM de mutation ──")
    print(user_msg)
    print("─" * 60)

    # API Gemini (generativelanguage) : le system prompt va dans systemInstruction,
    # le JSON est forcé via generationConfig.response_mime_type.
    payload = {
        "contents": [{"role": "user", "parts": [{"text": user_msg}]}],
        "systemInstruction": {"parts": [{"text": _MUTATION_SYSTEM}]},
        "generationConfig": {
            "temperature":        MUTATION_TEMP,
            "maxOutputTokens":    1024,
            "response_mime_type": "application/json",
        },
    }
    url = f"{GEMINI_BASE_URL}/models/{MUTATION_MODEL}:generateContent?key={GEMINI_API_KEY}"

    for attempt in range(MAX_RETRIES + 1):
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, headers={"Content-Type": "application/json"}, json=payload)
        if resp.status_code == 429 and attempt < MAX_RETRIES:
            wait = _parse_ratelimit_reset(
                resp.headers.get("retry-after") or resp.headers.get("x-ratelimit-reset-requests"),
                default=60,
            )
            wait = min(wait, MAX_RETRY_WAIT)
            print(f"  Rate limit mutation → {wait}s (tentative {attempt + 1}/{MAX_RETRIES})")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        candidate = resp.json()["candidates"][0]
        return json.loads(candidate["content"]["parts"][0]["text"])

    resp.raise_for_status()
    return {}


def apply_mutation(blocks: list[dict], mutation: dict) -> list[dict] | None:
    """Applique la mutation. Retourne None si la mutation est invalide."""
    target  = mutation.get("target_block", "")
    action  = mutation.get("action", "modify")
    content = mutation.get("new_content", "")

    target_block = next((b for b in blocks if b["name"] == target), None)
    if target_block is None:
        print(f"  ⚠ Bloc inconnu : {target!r}")
        return None
    # Pour "insert", on insère APRÈS target — la mutabilité de la cible n'est pas requise.
    if action not in ("insert",) and not target_block["mutable"]:
        print(f"  ⚠ Bloc non-mutable : {target!r}")
        return None
    if action in ("delete", "insert") and target == "json_schema":
        print(f"  ⚠ Action interdite sur le schéma JSON")
        return None

    if action == "insert":
        if not content.strip():
            print(f"  ⚠ Contenu vide pour l'insertion")
            return None
        n_ins     = sum(1 for b in blocks if b["name"].startswith("inserted_"))
        new_name  = f"inserted_{n_ins + 1}"
        new_block = {"name": new_name, "mutable": True, "content": content}
        new_blocks = []
        for b in blocks:
            new_blocks.append(b)
            if b["name"] == target:
                new_blocks.append(new_block)
        return new_blocks

    new_blocks = []
    for b in blocks:
        if b["name"] == target:
            if action != "delete":
                new_blocks.append({**b, "content": content})
        else:
            new_blocks.append(b)
    return new_blocks


# ════════════════════════════════════════════════════════════════════════════
# Visualisations
# ════════════════════════════════════════════════════════════════════════════
def plot_distribution_pies(df: pd.DataFrame, title: str = "") -> None:
    """Camemberts LLM vs Cerema global (inspiré de selected_mode_stats.ipynb)."""
    if df.empty or "mode_cat" not in df.columns:
        print(f"[{title}] Aucune donnée disponible.")
        return
    cerema_g = {k: v for k, v in cerema["parts_modales_2023"]["global"].items()
                if k not in EXCLUDE_MODES}
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, label, data in [
        (axes[0], "Agent LLM", df["mode_cat"].value_counts()),
        (axes[1], "EMC² 2023 Toulouse", pd.Series(cerema_g)),
    ]:
        series = data.reindex(MODES).fillna(0)
        total = series.sum()
        series = series / total * 100 if total > 0 else series
        colors = [MODE_COLORS.get(m, "#999") for m in MODES]
        wedges, texts, autotexts = ax.pie(series, labels=MODES, colors=colors,
                                           autopct='%1.1f%%', startangle=90)
        for at in autotexts:
            at.set_fontsize(9)
        ax.set_title(label, fontsize=12, fontweight='bold')
    if title:
        fig.suptitle(title, fontsize=13)
    plt.tight_layout()
    plt.show()
    plt.close()


def plot_score_history(history: list[dict]) -> None:
    """Évolution du score de calibration.

    Chaque mutation est marquée d'un point : vert si elle a été conservée, rouge si
    elle a été rejetée. La courbe verte suit le meilleur score atteint.
    """
    if len(history) < 2:
        return
    iters = [h["iteration"] for h in history]
    bests = [h["best_score"] for h in history]

    # Mutations conservées (vert) vs rejetées (rouge) — l'itération 0 est le run initial.
    kept_x   = [h["iteration"] for h in history if h["iteration"] > 0 and h["kept"]]
    kept_y   = [h["scores"]["composite"] for h in history if h["iteration"] > 0 and h["kept"]]
    rej_x    = [h["iteration"] for h in history if h["iteration"] > 0 and not h["kept"]]
    rej_y    = [h["scores"]["composite"] for h in history if h["iteration"] > 0 and not h["kept"]]

    fig, ax = plt.subplots(figsize=(13, 4))
    ax.plot(iters, bests, '-', color='#22AA44', linewidth=2.0, alpha=0.7,
            label='Meilleur score', zorder=1)
    if rej_x:
        ax.scatter(rej_x, rej_y, color='#EE4444', s=55, zorder=3,
                   edgecolors='white', linewidths=0.6, label='Mutation rejetée')
    if kept_x:
        ax.scatter(kept_x, kept_y, color='#22AA44', s=70, zorder=4,
                   edgecolors='white', linewidths=0.6, label='Mutation conservée')

    ax.set_xlabel("Itération")
    ax.set_ylabel("Score composite L1 (↓ mieux)")
    ax.set_title("Évolution du score de calibration")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
    plt.close()


def plot_global_bars(df: pd.DataFrame, title: str = "") -> None:
    """Barres comparant la distribution modale actuelle (LLM) à la cible EMC² (hachurée)."""
    if df.empty or "mode_cat" not in df.columns:
        print(f"[{title}] Aucune donnée disponible.")
        return
    cerema_g = {k: v for k, v in cerema["parts_modales_2023"]["global"].items()
                if k not in EXCLUDE_MODES}
    ref_sum  = sum(cerema_g.values()) or 1
    counts   = df["mode_cat"].value_counts()
    total    = counts.sum() or 1

    llm_vals = [counts.get(m, 0) / total * 100 for m in MODES]
    emc_vals = [cerema_g.get(m, 0) * 100.0 / ref_sum for m in MODES]
    colors   = [MODE_COLORS.get(m, "#999") for m in MODES]

    x     = np.arange(len(MODES))
    width = 0.38
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(x - width / 2, llm_vals, width, color=colors, label="Agent LLM (actuel)")
    ax.bar(x + width / 2, emc_vals, width, color=colors, alpha=0.45,
           hatch="//", edgecolor="white", label="EMC² 2023 (cible)")

    for xi, (lv, ev) in enumerate(zip(llm_vals, emc_vals)):
        ax.text(xi - width / 2, lv + 0.8, f"{lv:.0f}", ha="center", fontsize=8)
        ax.text(xi + width / 2, ev + 0.8, f"{ev:.0f}", ha="center", fontsize=8, color="#555")

    ax.set_xticks(x)
    ax.set_xticklabels(MODES, rotation=15, ha="right")
    ax.set_ylabel("Part modale (%)")
    ax.set_title(title or "Distribution modale — actuel vs EMC² 2023")
    ax.legend(loc="upper right")
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.show()
    plt.close()


def present_calibration_state(blocks: list[dict], ablation_results: list[dict],
                              df: pd.DataFrame, scores: dict, *,
                              history: list[dict] | None = None,
                              title: str = "", show_card: bool = True,
                              show_history: bool = True) -> None:
    """Tableau de bord de présentation pour une étape de calibration.

    Affiche, dans l'ordre :
      1. la CARTE D'ABLATION colorée (vert = utile, rouge = nuisible) ;
      2. les méta-informations : où sont les écarts les plus importants
         (pires croisements strate × mode vs EMC²) ;
      3. le score global (composite) ;
      4. les scores L1 par dimension (↓ mieux, contribution = L1 × poids) ;
      5. les barres distribution actuelle vs EMC² (hachurée) ;
      6. l'évolution du score de calibration (points verts conservés / rouges rejetés).
    """
    if title:
        print("\n" + "═" * 65)
        print(f"  {title}")
        print("═" * 65)

    # 1. Carte d'ablation
    if show_card:
        print("\nCARTE D'ABLATION   vert=utile · rouge=nuisible")
        highlight_prompt_ablation(blocks, ablation_results)

    # 2. Méta : pires écarts strate × mode (où le prompt se trompe le plus)
    meta = format_worst_strata(worst_strata_modes(df, cerema))
    print(meta if meta else "\n(pas assez de données par strate pour les méta-écarts)")

    # 3. Score global + 4. scores L1 par dimension
    print(f"\n★ Score global (composite L1, ↓ mieux) : {scores.get('composite', 0.0):.2f}")
    print(format_dimension_scores(scores))

    # 5. Barres actuel vs EMC²
    plot_global_bars(df, title=f"{title} — actuel vs EMC²" if title else "")

    # 6. Évolution du score
    if show_history and history:
        plot_score_history(history)


def plot_bars_by_dimension(df: pd.DataFrame, title: str = "") -> None:
    """Barres LLM vs Cerema par occupation et âge (inspiré bar_graph)."""
    fig = make_subplots(rows=1, cols=2,
                         subplot_titles=("Par occupation", "Par tranche d'âge"),
                         horizontal_spacing=0.1)
    parts = cerema["parts_modales_2023"]

    def add_traces(ref_dict, x_col, col_idx, show_legend):
        categories = list(ref_dict.keys())
        for mode in MODES:
            color = MODE_COLORS.get(mode, "#999")
            llm_vals, cer_vals = [], []
            for cat in categories:
                sub = df[df[x_col] == cat]["mode_cat"].value_counts()
                tot = sub.sum()
                llm_vals.append(sub.get(mode, 0) / tot * 100 if tot > 0 else 0)
                ref = ref_dict[cat]
                ref_s = sum(v for k, v in ref.items() if k not in EXCLUDE_MODES)
                cer_vals.append(ref.get(mode, 0) / ref_s * 100 if ref_s > 0 else 0)
            fig.add_trace(go.Bar(x=categories, y=llm_vals, name=mode, marker_color=color,
                                  legendgroup=mode, showlegend=show_legend,
                                  opacity=0.9, offsetgroup=mode), row=1, col=col_idx)
            fig.add_trace(go.Bar(x=categories, y=cer_vals, name=f"{mode} (EMC²)",
                                  marker_color=color, legendgroup=f"{mode}_ref",
                                  showlegend=False, opacity=0.35,
                                  marker_pattern_shape="/", offsetgroup=f"{mode}_ref"),
                          row=1, col=col_idx)

    add_traces(parts["occupation"], "occupation", 1, True)
    age_cats = {k: v for k, v in parts["Age"].items() if k in df["age_cat"].unique()}
    add_traces(age_cats, "age_cat", 2, False)

    fig.update_layout(barmode="group", height=500, width=1300,
                       title_text=title or "Comparaison LLM vs EMC² 2023",
                       yaxis_title="%", yaxis2_title="%")
    fig.show()


def highlight_prompt_ablation(blocks: list[dict], ablation_results: list[dict]) -> None:
    """Affiche le prompt coloré par delta centré sur 0, avec le delta en exposant discret."""
    delta_map = {r["bloc"]: r["delta"] for r in ablation_results}
    if not delta_map:
        print("(aucun résultat d'ablation)")
        return

    vmax = max(abs(d) for d in delta_map.values()) or 1.0
    cmap = plt.cm.RdYlGn
    norm = mcolors.TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)

    def darken(hex_color: str, max_l: float = 0.38) -> str:
        h_color = hex_color.lstrip("#")
        r, g, b = (int(h_color[i:i+2], 16) / 255 for i in (0, 2, 4))
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        r2, g2, b2 = colorsys.hls_to_rgb(h, min(l, max_l), s)
        return "#{:02x}{:02x}{:02x}".format(int(r2 * 255), int(g2 * 255), int(b2 * 255))

    parts = [
        "<div style='font-family:monospace;font-size:13px;line-height:1.7;"
        "white-space:pre-wrap;border:1px solid #ccc;padding:12px;border-radius:6px;background:#fff;'>"
    ]
    for block in blocks:
        name    = block["name"]
        escaped = block["content"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if name in delta_map:
            delta  = delta_map[name]
            color  = darken(mcolors.to_hex(cmap(norm(delta))))
            sign   = "+" if delta >= 0 else ""
            sup    = f"<sup style='font-size:9px;opacity:0.5;margin-left:3px;'>({sign}{delta:.0f})</sup>"
            parts.append(
                f"<div style='color:{color};padding:3px 8px;margin:2px 0;border-left:3px solid {color};'>"
                f"{escaped}{sup}</div>"
            )
        else:
            parts.append(
                f"<div style='color:#bbb;padding:3px 8px;margin:2px 0;border-left:3px solid #ddd;'>"
                f"{escaped}</div>"
            )
    parts.append("</div>")
    display(HTML("".join(parts)))


# ════════════════════════════════════════════════════════════════════════════
# Diff git-like (prompt initial vs calibré)
# ════════════════════════════════════════════════════════════════════════════
def _word_diff_html(old_line: str, new_line: str) -> tuple[str, str]:
    """Retourne (html_old, html_new) avec les mots changés surlignés en inline."""
    def tokenize(s):
        return re.findall(r'\S+|\s+', s)

    old_tokens = tokenize(old_line)
    new_tokens = tokenize(new_line)
    sm = difflib.SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    old_parts, new_parts = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        old_chunk = "".join(old_tokens[i1:i2])
        new_chunk = "".join(new_tokens[j1:j2])
        if tag == "equal":
            old_parts.append(esc(old_chunk))
            new_parts.append(esc(new_chunk))
        elif tag == "replace":
            old_parts.append(f'<span style="background:#f8b4b4;border-radius:2px">{esc(old_chunk)}</span>')
            new_parts.append(f'<span style="background:#80e88a;border-radius:2px">{esc(new_chunk)}</span>')
        elif tag == "delete":
            old_parts.append(f'<span style="background:#f8b4b4;border-radius:2px">{esc(old_chunk)}</span>')
        elif tag == "insert":
            new_parts.append(f'<span style="background:#80e88a;border-radius:2px">{esc(new_chunk)}</span>')

    return "".join(old_parts), "".join(new_parts)


def render_diff_html(lines: list[str]) -> str:
    # Regroupe les blocs -/+ consécutifs pour faire du diff intra-ligne
    parts = []
    i = 0
    while i < len(lines):
        line = lines[i]
        esc = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        if line.startswith("+++") or line.startswith("---"):
            parts.append(
                f'<div style="color:#555;font-weight:bold;background:#f6f6f6;'
                f'font-family:monospace;font-size:13px;white-space:pre-wrap;'
                f'padding:1px 6px;border-bottom:1px solid #eee">{esc}</div>'
            )
            i += 1

        elif line.startswith("@@"):
            parts.append(
                f'<div style="color:#0055cc;background:#ddeeff;'
                f'font-family:monospace;font-size:13px;white-space:pre-wrap;'
                f'padding:1px 6px;border-bottom:1px solid #eee">{esc}</div>'
            )
            i += 1

        elif line.startswith("-") and not line.startswith("---"):
            # Collecter toutes les lignes - suivantes puis les + correspondantes
            rem_lines, add_lines = [], []
            while i < len(lines) and lines[i].startswith("-") and not lines[i].startswith("---"):
                rem_lines.append(lines[i][1:])
                i += 1
            while i < len(lines) and lines[i].startswith("+") and not lines[i].startswith("+++"):
                add_lines.append(lines[i][1:])
                i += 1

            # Diff intra-ligne si même nombre de lignes supprimées/ajoutées
            if len(rem_lines) == len(add_lines):
                for old, new in zip(rem_lines, add_lines):
                    html_old, html_new = _word_diff_html(old.rstrip("\n"), new.rstrip("\n"))
                    parts.append(
                        f'<div style="color:#a01010;background:#ffeef0;'
                        f'font-family:monospace;font-size:13px;white-space:pre-wrap;'
                        f'padding:1px 6px;border-bottom:1px solid #eee">-{html_old}</div>'
                    )
                    parts.append(
                        f'<div style="color:#166a16;background:#e6ffed;'
                        f'font-family:monospace;font-size:13px;white-space:pre-wrap;'
                        f'padding:1px 6px;border-bottom:1px solid #eee">+{html_new}</div>'
                    )
            else:
                # Nombres différents : diff ligne classique
                for old in rem_lines:
                    esc_old = old.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    parts.append(
                        f'<div style="color:#a01010;background:#ffeef0;'
                        f'font-family:monospace;font-size:13px;white-space:pre-wrap;'
                        f'padding:1px 6px;border-bottom:1px solid #eee">-{esc_old}</div>'
                    )
                for new in add_lines:
                    esc_new = new.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    parts.append(
                        f'<div style="color:#166a16;background:#e6ffed;'
                        f'font-family:monospace;font-size:13px;white-space:pre-wrap;'
                        f'padding:1px 6px;border-bottom:1px solid #eee">+{esc_new}</div>'
                    )

        elif line.startswith("+") and not line.startswith("+++"):
            parts.append(
                f'<div style="color:#166a16;background:#e6ffed;'
                f'font-family:monospace;font-size:13px;white-space:pre-wrap;'
                f'padding:1px 6px;border-bottom:1px solid #eee">{esc}</div>'
            )
            i += 1

        else:
            parts.append(
                f'<div style="color:#333;background:#fff;'
                f'font-family:monospace;font-size:13px;white-space:pre-wrap;'
                f'padding:1px 6px;border-bottom:1px solid #eee">{esc}</div>'
            )
            i += 1

    return (
        '<div style="border:1px solid #ccc;border-radius:6px;overflow:hidden;'
        'max-height:600px;overflow-y:auto;margin:8px 0">'
        + "".join(parts) + "</div>"
    )
