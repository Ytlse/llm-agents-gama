"""Onglet « 🗂️ Mes travaux » — suivi personnel de l'avancement des expériences.

Croise **le plan** (les fiches de `docs/paper/methode/experience_plan/experiments.yaml`) avec
**les runs réels** lus sur disque (`data/experiences/<exp>/executions/<ref>/`).

Cocher une fiche = l'associer à un run RÉEL terminé. Au moment de l'association, la
config de la fiche est comparée à celle réellement exécutée (`execution.yaml`). Les
écarts sont montrés **tous d'un coup** ; l'utilisateur tranche champ par champ —
*écraser la fiche* (réécrit `experiments.yaml` en préservant les commentaires) ou
*rejeter* (la fiche n'est pas validée). Le **score composite L1** est lu dans
`scores.json` (jamais saisi à la main) et figé sur la fiche.

Un bouton **➕** à côté de chaque phase permet d'ajouter un bloc de travail libre,
suivi et associable comme une fiche du plan.

L'état personnel est écrit dans `scripts/dashboard/mes_travaux.yaml` (fichier possédé
par le tableau de bord, réécrit en entier — pas de fusion à l'octet nécessaire).

Champs VÉRIFIÉS (diff bloquant) : `model`, `temperature`, `seed`.
Champs INFORMATIFS (affichés, non comparés — absents ou de sémantique divergente dans
`execution.yaml`) : `provider`, `instance`, `batch_size`, `max_parallel_requests`.
Cf. `specs/mes_travaux/questions.md`.
"""

from __future__ import annotations

import io
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from ruamel.yaml import YAML

# Exécuté par `streamlit run scripts/dashboard/app.py` : le dossier du script est sur
# sys.path mais pas la racine — même repli que app.py pour retrouver le package.
try:  # pragma: no cover
    from scripts.dashboard import experiences
except ImportError:  # pragma: no cover
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.dashboard import experiences

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = REPO_ROOT / "docs" / "paper" / "experience_plan" / "experiments.yaml"
ETAT_PATH = Path(__file__).resolve().parent / "mes_travaux.yaml"

# Ordre et libellés des phases connues ; toute phase inconnue est rendue en fin,
# titre dérivé de sa clé (pour ne jamais masquer une fiche d'une phase non listée).
_PHASES: list[tuple[str, str]] = [
    ("phase_0_planchers", "Phase 0 — Planchers statistiques & heuristiques"),
    ("phase_1_bare_llm", "Phase 1 — Modèles nus (Bare LLM)"),
    ("phase_2_prompt_calibration", "Phase 2 — Prompt calibré & few-shot"),
    ("phase_3_baselines_statistiques", "Phase 3 — Plafond tabulaire supervisé"),
    ("phase_4_hysteresis", "Phase 4 — Hystérésis post-incident"),
    ("phase_5_presse_locale", "Phase 5 — Évaluation écologique presse locale"),
]
_TITRE_PHASE = dict(_PHASES)

# Champs comparés fiche ↔ run. Getter côté run = chemin dans execution.yaml.
_CHAMPS_VERIFIES: list[tuple[str, str]] = [
    ("model", "Modèle"),
    ("temperature", "Température"),
    ("seed", "Graine"),
]


# ── État personnel (mes_travaux.yaml) ─────────────────────────────────────────
def _maintenant() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def charger_etat() -> dict:
    """Lit `mes_travaux.yaml` ; garantit les clés `fiches` et `blocs`."""
    data: dict = {}
    if ETAT_PATH.is_file():
        try:
            data = yaml.safe_load(ETAT_PATH.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            data = {}
    data.setdefault("fiches", {})
    data.setdefault("blocs", {})
    return data


def sauver_etat(etat: dict) -> None:
    """Réécrit le fichier en entier (nous en sommes seul auteur)."""
    entete = (
        "# Suivi personnel de l'avancement — onglet « Mes travaux » du Pilotage.\n"
        "# Écrit par le tableau de bord. `fiches` : associations fiche→run validées.\n"
        "# `blocs` : blocs de travail ajoutés à la main, par phase.\n"
    )
    corps = yaml.safe_dump(etat, allow_unicode=True, sort_keys=False)
    ETAT_PATH.write_text(entete + corps, encoding="utf-8")


# ── Plan (experiments.yaml) ───────────────────────────────────────────────────
def charger_plan() -> list[dict]:
    """Liste des fiches du plan, dans l'ordre du fichier."""
    try:
        data = yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    return list(data.get("experiments") or [])


def ecraser_champ_fiche(fid: str, champ: str, valeur) -> bool:
    """Écrit `engine.<champ> = valeur` dans la fiche `fid` de experiments.yaml.

    Round-trip ruamel : commentaires, ordre et style des autres fiches préservés.
    Renvoie True si la fiche a été trouvée et modifiée.
    """
    yml = YAML()
    yml.preserve_quotes = True
    yml.width = 4096
    # Coller au style du fichier source (séquences indentées de 4, tiret à 2)
    # pour qu'écrire un seul champ ne reflowe pas tout le fichier.
    yml.indent(mapping=2, sequence=4, offset=2)
    # ruamel émet None comme un blanc ; le fichier source écrit « null ». Sans ça,
    # chaque `x: null` non touché deviendrait `x:` — un faux diff à chaque écriture.
    yml.representer.add_representer(
        type(None),
        lambda r, _d: r.represent_scalar("tag:yaml.org,2002:null", "null"),
    )
    data = yml.load(PLAN_PATH.read_text(encoding="utf-8"))
    for exp in data.get("experiments", []):
        if exp.get("id") == fid:
            eng = exp.get("engine")
            if eng is None:
                return False
            eng[champ] = valeur
            buf = io.StringIO()
            yml.dump(data, buf)
            PLAN_PATH.write_text(buf.getvalue(), encoding="utf-8")
            return True
    return False


# ── Runs réels ────────────────────────────────────────────────────────────────
def _index_runs() -> dict[str, dict]:
    """Index des exécutions sur disque par référence (nom de dossier)."""
    idx: dict[str, dict] = {}
    for r in experiences.lister():
        nom = r.get("execution")
        if nom and r.get("dossier"):
            idx[nom] = {
                "execution": nom,
                "experience": r.get("experience"),
                "dossier": r.get("dossier"),
                "score_l1": r.get("composite_l1"),
                "etat": r.get("etat"),
            }
    return idx


def _normaliser_ref(ref: str) -> str:
    """Accepte la date ISO (2026-09-07T14:35:03+00:00) ou le nom de dossier
    (2026-09-07_14_35_03) et renvoie la forme « nom de dossier »."""
    s = (ref or "").strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})[T_ ](\d{2})[:_](\d{2})[:_](\d{2})", s)
    if m:
        return f"{m.group(1)}_{m.group(2)}_{m.group(3)}_{m.group(4)}"
    return s


def trouver_run(ref: str) -> Optional[dict]:
    """Retrouve une exécution par la référence saisie (aucune association auto)."""
    idx = _index_runs()
    for cand in (ref.strip() if ref else "", _normaliser_ref(ref)):
        if cand and cand in idx:
            return idx[cand]
    return None


def _config_run(dossier: str) -> dict:
    p = Path(dossier) / "execution.yaml"
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _val_fiche(eng: dict, champ: str):
    return (eng or {}).get(champ)


def _val_run(conf: dict, champ: str):
    exp = (conf or {}).get("experience") or {}
    dec = exp.get("decideur") or {}
    if champ == "model":
        return dec.get("modele")
    if champ == "temperature":
        return (dec.get("parametres") or {}).get("temperature")
    if champ == "seed":
        sa = (conf or {}).get("sources_alea") or {}
        graine = sa.get("graine_tirage")
        if graine is None:
            graine = (exp.get("calendrier") or {}).get("graine")
        return graine
    return None


def _norm(champ: str, v):
    if v is None:
        return None
    if champ == "temperature":
        try:
            return round(float(v), 6)
        except (TypeError, ValueError):
            return v
    if champ == "seed":
        try:
            return int(v)
        except (TypeError, ValueError):
            return v
    return str(v).strip()


def _coercer(champ: str, v):
    """Valeur écrite dans la fiche lorsqu'on écrase avec la valeur du run."""
    if champ == "temperature":
        try:
            return float(v)
        except (TypeError, ValueError):
            return v
    if champ == "seed":
        try:
            return int(v)
        except (TypeError, ValueError):
            return v
    return None if v is None else str(v)


def diff_fiche_run(eng: dict, conf: dict) -> list[tuple[str, str, object, object]]:
    """Écarts sur les champs vérifiés, uniquement là où la fiche déclare le champ."""
    out = []
    for champ, lib in _CHAMPS_VERIFIES:
        vf = _val_fiche(eng, champ)
        if vf is None:  # fiche non-LLM (heuristique/tabulaire) ou bloc libre : rien à vérifier
            continue
        vr = _val_run(conf, champ)
        if _norm(champ, vf) != _norm(champ, vr):
            out.append((champ, lib, vf, vr))
    return out


# ── Rendu Streamlit ───────────────────────────────────────────────────────────
# Pastille de type reprenant les couleurs du plan (LLM violet, heuristique vert…).
_PASTILLE = {
    "llm": "🟣 LLM",
    "heuristic": "🟢 Heuristique",
    "tabular_ml": "🟠 Tabulaire ML",
}
def _fiches_par_phase(plan: list[dict], etat: dict) -> dict[str, list[dict]]:
    """Fiches du plan + blocs ajoutés, groupés par phase (ordre : plan puis inconnues)."""
    groupes: dict[str, list[dict]] = {}
    for fiche in plan:
        groupes.setdefault(fiche.get("phase") or "sans_phase", []).append(fiche)
    for phase, blocs in (etat.get("blocs") or {}).items():
        for bloc in blocs:
            groupes.setdefault(phase, []).append({**bloc, "ajoute": True})
    return groupes


def _zone_ajout(col, st, phase: str):
    if hasattr(st, "popover"):
        return col.popover("➕", help="Ajouter un bloc à cette phase")
    return col.expander("➕ bloc")


def _form_ajout_bloc(zone, st, etat: dict, phase: str) -> None:
    with zone:
        with st.form(key=f"add_{phase}", clear_on_submit=True):
            titre = st.text_input("Titre du bloc")
            desc = st.text_area("Description (optionnelle)", height=68)
            if st.form_submit_button("Ajouter") and titre.strip():
                bid = f"bloc_{int(time.time() * 1000)}"
                etat.setdefault("blocs", {}).setdefault(phase, []).append(
                    {"id": bid, "title": titre.strip(), "description": desc.strip(),
                     "phase": phase, "engine": {}}
                )
                sauver_etat(etat)
                st.rerun()


def _bloc_ecart(st, lib: str, v_fiche, v_run) -> None:
    """Rend un écart de façon voyante : valeur fiche en rouge → valeur run en vert."""
    st.markdown(f"**{lib}**  ·  :grey[fiche] ➜ :grey[run]")
    st.markdown(f"### :red[{v_fiche}]  ➜  :green[{v_run}]")


def _render_fiche(st, fiche: dict, etat: dict) -> None:
    fid = fiche.get("id") or "?"
    e = (etat.get("fiches") or {}).get(fid, {})
    fait = bool(e.get("fait"))
    eng = fiche.get("engine") or {}
    pastille = _PASTILLE.get(eng.get("type"), "➕ Bloc" if fiche.get("ajoute") else "•")

    with st.container(border=True):
        c1, c2 = st.columns([8, 2])
        checked = c1.checkbox(f"**{fiche.get('title', fid)}**", value=fait, key=f"chk_{fid}")
        c2.markdown(f"<div style='text-align:right'>{pastille}</div>", unsafe_allow_html=True)
        st.caption(f"`{fid}`" + (f" — {fiche['description']}" if fiche.get("description") else ""))
        st.markdown(
            f"**Modèle** `{eng.get('model', '—')}` · **T** `{eng.get('temperature', '—')}` · "
            f"**seed** `{eng.get('seed', '—')}`"
        )
        st.caption(
            f"provider `{eng.get('provider', '—')}` · instance `{eng.get('instance', '—')}` · "
            f"batch `{(fiche.get('execution') or {}).get('batch_size', '—')}` · "
            f"parallèle `{(fiche.get('execution') or {}).get('max_parallel_requests', '—')}` — non vérifiés"
        )

        # Coche décochée sur une fiche faite → dissocier.
        if fait and not checked:
            etat.get("fiches", {}).pop(fid, None)
            sauver_etat(etat)
            st.rerun()
            return

        # Fiche déjà validée : score + référence.
        if fait and checked:
            d1, d2 = st.columns([1, 2])
            if e.get("score_l1") is not None:
                d1.metric("Score composite L1", f"{e['score_l1']:.2f}")
            d2.write(f"Référence : `{e.get('run_ref', '?')}`")
            d2.caption(f"expérience `{e.get('run_experience', '?')}` · validé {e.get('maj', '?')}")
            if e.get("arbitrages"):
                d2.caption("Écrasements : " + ", ".join(sorted(e["arbitrages"])))
            return

        if not checked:
            return

        # Cochée mais pas encore validée → DEMANDER la référence (la date), puis comparer.
        ref = st.text_input(
            "Référence de l'expérience (sa date, ex. `2026-09-07_14_35_03`)", key=f"ref_{fid}"
        ).strip()
        if not ref:
            st.info("Saisis la référence de l'expérience réalisée pour lancer la comparaison.")
            return
        run = trouver_run(ref)
        if not run:
            st.error(f"Aucune exécution trouvée pour la référence « {ref} ».")
            return

        conf = _config_run(run["dossier"])
        diffs = diff_fiche_run(eng, conf)
        decisions: dict[str, bool] = {}  # champ -> écraser ?
        if diffs:
            st.error(f"⚠️ {len(diffs)} écart(s) entre la fiche et le run « {run['execution']} »")
            for champ, lib, vf, vr in diffs:
                _bloc_ecart(st, lib, vf, vr)
                choix = st.radio(
                    "Décision",
                    ["Rejeter (garder la fiche)", "Écraser la fiche avec le run"],
                    key=f"diff_{fid}_{champ}",
                    horizontal=True,
                    label_visibility="collapsed",
                )
                decisions[champ] = choix.startswith("Écraser")
        else:
            st.success(f"✅ Run « {run['execution']} » conforme à la fiche (champs vérifiés).")

        if st.button("Valider", key=f"val_{fid}", type="primary"):
            if diffs and not all(decisions.values()):
                st.error("Rejeté : un champ en écart n'a pas été écrasé — fiche non validée.")
                return
            for champ, _lib, _vf, vr in diffs:  # tous « écraser » ici
                ecraser_champ_fiche(fid, champ, _coercer(champ, vr))
            etat.setdefault("fiches", {})[fid] = {
                "fait": True,
                "run_ref": run["execution"],
                "run_experience": run.get("experience"),
                "score_l1": run.get("score_l1"),
                "arbitrages": {c: "ecrase" for c, _, _, _ in diffs},
                "maj": _maintenant(),
            }
            sauver_etat(etat)
            st.rerun()


def render(st, pd, **_kw) -> None:
    """Point d'entrée de l'onglet (signature alignée sur experiences.render)."""
    st.subheader("🗂️ Mes travaux")
    st.caption(
        "Cocher une fiche demande la référence (date) de l'expérience réalisée, compare "
        "la config au run et fige son score composite. Le ➕ ajoute un bloc à une phase."
    )

    etat = charger_etat()
    plan = charger_plan()
    groupes = _fiches_par_phase(plan, etat)

    total = sum(len(v) for v in groupes.values())
    faits = sum(
        1
        for fiches in groupes.values()
        for f in fiches
        if (etat.get("fiches") or {}).get(f.get("id"), {}).get("fait")
    )
    c1, c2 = st.columns([1, 3])
    if c1.button("🔄 Rafraîchir", width="stretch"):
        st.rerun()
    c2.metric("Avancement", f"{faits} / {total}")

    phases_connues = [p for p, _ in _PHASES if p in groupes]
    phases_autres = [p for p in groupes if p not in _TITRE_PHASE]
    for phase in phases_connues + phases_autres:
        titre = _TITRE_PHASE.get(phase, phase.replace("_", " ").capitalize())
        h1, h2 = st.columns([9, 1])
        h1.markdown(f"### {titre}")
        zone = _zone_ajout(h2, st, phase)
        _form_ajout_bloc(zone, st, etat, phase)
        for fiche in groupes.get(phase, []):
            _render_fiche(st, fiche, etat)
