"""Registre, comparaison, restitution (ticket 035, spec 06 E12–E17, E20).

Le registre est la lecture de `data/experiences/*` : rien n'y est écrit. La synthèse d'une exécution
est un fichier de données (`synthese.json`) dont la page HTML n'est qu'un rendu (E16). La
plateforme ne détient **aucune** valeur d'enquête : quand elle compare, elle lit la source de vérité
du dépôt et cite chemin + empreinte (E17).
"""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

import yaml
from experiences.archive import (
    F_COMPTEURS,
    F_ETAT,
    F_EXECUTION,
    F_SCORES,
    F_SYNTHESE,
    F_SYNTHESE_HTML,
    METHODE_INEXPLOITABLE,
    METHODE_NON_COUVERT,
    Execution,
)
from experiences.decision import METHODE_REPLI_UNIFORME, METHODE_SANS_SOLUTION
from experiences.experience import dossier_experiences
from experiences.population import sha256_fichier

ETAT_ARCHIVE_MANQUANTE = "archive manquante"

# Familles canoniques (mobility_llm.mode_choice) → clé du référentiel d'enquête. C'est une
# CORRESPONDANCE DE NOMS, pas une valeur : les valeurs sont lues dans le fichier cité.
CORRESPONDANCE_REFERENTIEL = {
    "car": "voiture",
    "walking": "marche",
    "cycling": "velo",
    "public_transport": "transports_collectifs",
    "train": "transports_collectifs",
}


def _racine() -> Path:
    return Path(__file__).resolve().parents[2]


def chemin_referentiel() -> Path:
    """Source de vérité des parts modales d'enquête ; `REFERENTIEL_ENQUETE` la désigne dans le conteneur."""
    import os

    return Path(
        os.getenv("REFERENTIEL_ENQUETE")
        or (_racine() / "scripts" / "data" / "population" / "cerema_values.yaml")
    )


# ── Registre (E12, E20) ──────────────────────────────────────────────────────


def _lire_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    except ValueError:
        return {}


def _decideur_label(dec: dict | None) -> str:
    """« type:modele » (ex. passerelle:gemini-3.5-flash-lite) ; vide si aucun type."""
    dec = dec or {}
    t = dec.get("type")
    if not t:
        return ""
    return f"{t}:{dec.get('modele') or ''}".rstrip(":")


def lister(
    dossier: Path | None = None, *, inclure_masquees: bool = False
) -> list[dict]:
    """Une ligne par exécution (et une ligne « définie » pour une expérience sans exécution).

    `inclure_masquees` (spec hygiène §3.2) : par défaut, les expériences marquées `archivee`
    ou `invalide` sortent du listing — leurs données restent intactes sur le disque, seule la
    visibilité change. Chaque ligne porte `statut` et `statut_motif` pour que l'appelant
    puisse afficher la raison plutôt que de faire disparaître la ligne sans explication.
    """
    from experiences import statut as S

    racine = Path(dossier) if dossier else dossier_experiences()
    lignes: list[dict] = []
    if not racine.is_dir():
        return lignes
    # SHA de la formule de référence courante, pour dériver le drapeau « périmée »
    # (R7) sans toucher aux scores.json. Best-effort : un registre illisible ne doit
    # pas casser la liste des expériences.
    ref_sha = None
    try:
        from experiences import formule as _F

        ref_sha = _F.charger().reference.sha256
    except Exception:  # noqa: BLE001 — le registre reste lisible même sans formule
        ref_sha = None
    for exp_dir in sorted(
        p for p in racine.iterdir() if (p / "experience.yaml").is_file()
    ):
        try:
            exp = (
                yaml.safe_load(
                    (exp_dir / "experience.yaml").read_text(encoding="utf-8")
                )
                or {}
            )
        except yaml.YAMLError:
            continue
        st = S.lire(exp_dir)
        if S.est_masquee(st) and not inclure_masquees:
            continue
        base = {
            "experience": exp.get("nom", exp_dir.name),
            "mode": exp.get("mode"),
            "decideur": _decideur_label(exp.get("decideur")),
            "gabarit": (exp.get("gabarit") or {}).get("categorie"),
            "derive_de": exp.get("derive_de"),
            "statut": st["statut"],
            "statut_motif": st.get("motif"),
        }
        connues = set(exp.get("executions_connues") or [])
        sur_disque = (
            sorted(p.name for p in (exp_dir / "executions").iterdir())
            if (exp_dir / "executions").is_dir()
            else []
        )
        for nom in sur_disque:
            d = exp_dir / "executions" / nom
            etat = _lire_json(d / F_ETAT)
            compteurs = _lire_json(d / F_COMPTEURS)
            synthese = _lire_json(d / F_SYNTHESE)
            conf = {}
            try:
                conf = (
                    yaml.safe_load((d / F_EXECUTION).read_text(encoding="utf-8")) or {}
                )
            except (yaml.YAMLError, OSError):
                pass
            couv = compteurs.get("couverture") or {}
            scores = _lire_json(d / F_SCORES)
            comp = scores.get("composite") or {}
            f_score = scores.get("formule") or {}
            f_sha = f_score.get("sha256")
            # R6 — décideur RÉELLEMENT utilisé, figé dans le snapshot de l'exécution, plutôt que
            # celui (mutable) de la définition courante. Repli sur la définition si le snapshot
            # est muet (anciens formats).
            dec_fige = (
                _decideur_label((conf.get("experience") or {}).get("decideur"))
                or base["decideur"]
            )
            lignes.append(
                {
                    **base,
                    "decideur": dec_fige,
                    "execution": nom,
                    "etat": etat.get("etat", "?"),
                    "raison": etat.get("raison"),
                    "date": conf.get("cree_le"),
                    "gabarit_sha256": (
                        (conf.get("empreintes") or {}).get("gabarit") or {}
                    ).get("sha256"),
                    "decides": couv.get("decides"),
                    "attendus": couv.get("attendus"),
                    "couverture": couv.get("taux"),
                    "parts_modales": (synthese.get("parts_modales") or {}).get(
                        "pourcent"
                    ),
                    # Scores (R5, R9) : None → « — » à l'affichage, jamais 0.
                    "composite_emd": comp.get("emd_jsd"),
                    "composite_l1": comp.get("l1"),
                    "volet": scores.get("volet"),
                    "formule": f_score.get("nom"),
                    "formule_sha256": f_sha,
                    # R7 — drapeau dérivé à la lecture : périmée si SHA ≠ référence.
                    "formule_perimee": bool(f_sha and ref_sha and f_sha != ref_sha),
                    "dossier": str(d),
                }
            )
        for nom in sorted(connues - set(sur_disque)):
            lignes.append(
                {
                    **base,
                    "execution": nom,
                    "etat": ETAT_ARCHIVE_MANQUANTE,
                    "raison": "dossier disparu",
                    "date": None,
                    "decides": None,
                    "attendus": None,
                    "couverture": None,
                    "parts_modales": None,
                    "dossier": str(exp_dir / "executions" / nom),
                }
            )
        if not sur_disque and not connues:
            lignes.append(
                {
                    **base,
                    "execution": None,
                    "etat": "definie",
                    "raison": None,
                    "date": None,
                    "decides": None,
                    "attendus": None,
                    "couverture": None,
                    "parts_modales": None,
                    "dossier": str(exp_dir),
                }
            )
    return lignes


def trier_filtrer(
    lignes: list[dict],
    *,
    trier: str | None = None,
    decroissant: bool = False,
    filtres: dict[str, str] | None = None,
) -> list[dict]:
    """E12 — tri sur un champ, filtre `champ=sous-chaîne` (insensible à la casse)."""
    out = lignes
    for champ, valeur in (filtres or {}).items():
        out = [l for l in out if valeur.lower() in str(l.get(champ, "")).lower()]
    if trier:
        out = sorted(
            out,
            key=lambda l: (
                l.get(trier) is None,
                l.get(trier) if l.get(trier) is not None else "",
            ),
            reverse=decroissant,
        )
    return out


def formater_table(lignes: list[dict], colonnes: list[str] | None = None) -> str:
    colonnes = colonnes or [
        "experience",
        "execution",
        "etat",
        "decideur",
        "mode",
        "couverture",
        "composite_emd",
        "composite_l1",
        "formule",
    ]

    def cell(l, c):
        v = l.get(c)
        if c == "couverture" and isinstance(v, float):
            return f"{100 * v:.1f} %".replace(".", ",")
        # Composite : « — » quand l'exécution n'est pas scorée (jamais 0, R9/vacuité).
        if c in ("composite_emd", "composite_l1"):
            return "—" if v is None else f"{v:.2f}".replace(".", ",")
        if c == "formule":
            if v is None:
                return "—"
            return f"{v} ⚠périmée" if l.get("formule_perimee") else str(v)
        return "" if v is None else str(v)

    largeur = {
        c: max(len(c), *(len(cell(l, c)) for l in lignes)) if lignes else len(c)
        for c in colonnes
    }
    entete = " | ".join(c.ljust(largeur[c]) for c in colonnes)
    sep = "-+-".join("-" * largeur[c] for c in colonnes)
    corps = [" | ".join(cell(l, c).ljust(largeur[c]) for c in colonnes) for l in lignes]
    return "\n".join([entete, sep, *corps])


# ── Synthèse (E14, E16, E17) ─────────────────────────────────────────────────


def lire_referentiel(chemin: Path | None = None) -> dict:
    """Parts modales globales de l'enquête, lues dans la source de vérité — avec chemin + sha256."""
    p = Path(chemin) if chemin else chemin_referentiel()
    if not p.is_file():
        return {"source": str(p), "sha256": None, "valeurs": {}, "disponible": False}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    glob = ((data.get("parts_modales_2023") or {}).get("global")) or {}
    return {
        "source": str(p.relative_to(_racine()))
        if p.is_relative_to(_racine())
        else str(p),
        "sha256": sha256_fichier(p),
        "valeurs": {k: float(v) for k, v in glob.items()},
        "disponible": True,
    }


def synthese(dossier_execution: str | Path, referentiel: Path | None = None) -> dict:
    """Toutes les valeurs de la page, et rien d'autre : la page ne calcule rien que ce JSON n'ait (E16)."""
    from mobility_llm.mode_choice import CANONICAL_MODES, canonical_mode

    d = Path(dossier_execution)
    ex = Execution.ouvrir(d)
    traces = ex.decisions
    compteurs = ex.compteurs or {}
    couv_c = compteurs.get("couverture") or {}
    attendus = int(
        couv_c.get("attendus")
        or compteurs.get("attendus_exploitables")
        or compteurs.get("attendus")
        or 0
    )
    methodes = Counter(str(t.get("methode")) for t in traces)
    exclus = methodes.get(METHODE_INEXPLOITABLE, 0)
    comptees = [
        t
        for t in traces
        if t.get("retenue")
        and t.get("methode")
        not in (
            METHODE_NON_COUVERT,
            METHODE_INEXPLOITABLE,
            METHODE_SANS_SOLUTION,
            METHODE_REPLI_UNIFORME,
        )
    ]
    par_mode: Counter = Counter(
        canonical_mode((t.get("retenue") or {}).get("mode")) for t in comptees
    )
    n = sum(par_mode.values())
    sources: Counter = Counter()
    fournisseurs: Counter = Counter()
    ecartees_motifs: Counter = Counter()
    for t in traces:
        for s in (t.get("sources") or {}).values():
            sources[str(s).split(":")[0]] += 1
        if t.get("fournisseur"):
            fournisseurs[str(t["fournisseur"])] += 1
        for e in t.get("ecartees") or []:
            ecartees_motifs[str(e.get("motif"))] += 1
    ref = lire_referentiel(referentiel)
    ref_par_mode = {}
    if ref.get("disponible"):
        total_ref = sum(
            v
            for k, v in ref["valeurs"].items()
            if k in set(CORRESPONDANCE_REFERENTIEL.values())
        )
        for mode, cle in CORRESPONDANCE_REFERENTIEL.items():
            if cle in ref["valeurs"] and total_ref:
                ref_par_mode[mode] = ref["valeurs"][cle] / total_ref * 100.0
    decides = len(comptees) + methodes.get(METHODE_REPLI_UNIFORME, 0)
    couverture = {
        "decides": decides,
        "comptes_dans_les_parts": n,
        "attendus": attendus,
        "attendus_bruts": int(
            couv_c.get("attendus_bruts") or compteurs.get("attendus") or attendus
        ),
        "inexploitables_exclus": exclus,
        "taux": decides / attendus if attendus else None,
        "complet": bool(attendus)
        and (decides + methodes.get(METHODE_SANS_SOLUTION, 0)) >= attendus,
    }
    return {
        "execution": ex.nom,
        "experience": (ex.config.get("experience") or {}).get("nom"),
        "etat": ex.etat(),
        "empreintes": ex.config.get("empreintes"),
        "regime_applique": ex.config.get("regime_applique"),
        "sources_alea": ex.config.get("sources_alea"),
        "interruptions": ex.config.get("interruptions"),
        "couverture": couverture,
        "methodes": dict(methodes),
        "parts_modales": {
            "n": n,
            "effectifs": {m: par_mode.get(m, 0) for m in CANONICAL_MODES}
            | ({"other": par_mode["other"]} if par_mode.get("other") else {}),
            "pourcent": {
                m: (100.0 * par_mode.get(m, 0) / n if n else None)
                for m in CANONICAL_MODES
            },
            "couverture": couverture,  # E14 : la couverture accompagne TOUJOURS le chiffre
        },
        "referentiel": {
            "source": ref["source"],
            "sha256": ref["sha256"],
            "disponible": ref["disponible"],
            "pourcent_normalise_4_modes": ref_par_mode,
            "note": "valeurs lues dans la source citée, renormalisées sur les modes qu'elle partage avec les canoniques",
        },
        "sources_propositions": dict(sources),
        "fournisseurs": dict(fournisseurs),
        "ecartees_par_motif": dict(ecartees_motifs),
        "compteurs": compteurs,
    }


def synthese_html(s: dict) -> str:
    """Rendu d'un `synthese.json` : chaque chiffre est lu du JSON, la couverture est à côté (E14)."""
    e = html.escape
    couv = s.get("couverture") or {}
    taux = couv.get("taux")
    badge = "COMPLET" if couv.get("complet") else "PARTIEL"
    taux_txt = f"{100 * taux:.1f} %" if taux is not None else "n/a"
    lignes = []
    for mode, pct in (s.get("parts_modales") or {}).get("pourcent", {}).items():
        ref = (
            (s.get("referentiel") or {}).get("pourcent_normalise_4_modes", {}).get(mode)
        )
        lignes.append(
            f"<tr><td>{e(mode)}</td><td>{'' if pct is None else f'{pct:.1f} %'}</td>"
            f"<td>{e(str((s['parts_modales']['effectifs'] or {}).get(mode, 0)))}</td>"
            f"<td>{'' if ref is None else f'{ref:.1f} %'}</td><td>{e(str(couv.get('decides')))} / {e(str(couv.get('attendus')))} ({e(taux_txt)})</td></tr>"
        )
    ref = s.get("referentiel") or {}
    return f"""<!doctype html><meta charset="utf-8"><title>Synthèse {e(str(s.get("execution")))}</title>
<style>body{{font-family:system-ui;max-width:900px;margin:2rem auto;padding:0 1rem}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:.3rem .6rem}}.partiel{{color:#b45309;font-weight:bold}}</style>
<h1>Exécution {e(str(s.get("execution")))} — expérience {e(str(s.get("experience")))}</h1>
<p>État : <b>{e(str((s.get("etat") or {}).get("etat")))}</b> · résultat <span class="{"partiel" if badge == "PARTIEL" else ""}">{badge}</span>
· couverture <b>{e(str(couv.get("decides")))} / {e(str(couv.get("attendus")))} déplacements exploitables ({e(taux_txt)})</b>
{f" · <b>{e(str(couv.get('inexploitables_exclus')))} inexploitables exclus</b> (aucune proposition des moteurs, sur {e(str(couv.get('attendus_bruts')))} attendus)" if couv.get("inexploitables_exclus") else ""}</p>
<h2>Parts modales (n = {e(str((s.get("parts_modales") or {}).get("n")))} décisions comptées)</h2>
<table><tr><th>Mode</th><th>Part</th><th>Effectif</th><th>Enquête</th><th>Couverture</th></tr>{"".join(lignes)}</table>
<p>Référentiel : <code>{e(str(ref.get("source")))}</code> (sha256 {e(str(ref.get("sha256"))[:16])}…) — {e(str(ref.get("note")))}</p>
<h2>Méthodes</h2><pre>{e(json.dumps(s.get("methodes"), ensure_ascii=False, indent=1))}</pre>
<h2>Sources des propositions</h2><pre>{e(json.dumps(s.get("sources_propositions"), ensure_ascii=False, indent=1))}</pre>
<h2>Écartées par motif</h2><pre>{e(json.dumps(s.get("ecartees_par_motif"), ensure_ascii=False, indent=1))}</pre>
<h2>Sources d'aléa</h2><pre>{e(json.dumps(s.get("sources_alea"), ensure_ascii=False, indent=1))}</pre>
<h2>Régime appliqué · interruptions</h2><pre>{e(json.dumps({"regime_applique": s.get("regime_applique"), "interruptions": s.get("interruptions")}, ensure_ascii=False, indent=1))}</pre>
<h2>Empreintes</h2><pre>{e(json.dumps(s.get("empreintes"), ensure_ascii=False, indent=1))}</pre>
"""


def ecrire_synthese(
    dossier_execution: str | Path, referentiel: Path | None = None
) -> Path:
    d = Path(dossier_execution)
    s = synthese(d, referentiel)
    (d / F_SYNTHESE).write_text(
        json.dumps(s, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    (d / F_SYNTHESE_HTML).write_text(synthese_html(s), encoding="utf-8")
    return d / F_SYNTHESE


# ── Comparaison (E13) ────────────────────────────────────────────────────────

CHAMPS_PARTAGES = (
    (
        "population",
        lambda c: (c.get("empreintes") or {}).get("population", {}).get("sha256"),
    ),
    ("jeu", lambda c: (c.get("empreintes") or {}).get("jeu", {}).get("sha256")),
    (
        "calendrier",
        lambda c: json.dumps(
            (c.get("experience") or {}).get("calendrier"), sort_keys=True
        ),
    ),
    ("graine_ordre", lambda c: (c.get("experience") or {}).get("graine_ordre")),
    ("graine_tirage", lambda c: (c.get("experience") or {}).get("graine_tirage")),
    (
        "tolerances_horaires",
        lambda c: json.dumps(
            (c.get("experience") or {}).get("tolerances_horaires"), sort_keys=True
        ),
    ),
    ("max_candidats", lambda c: (c.get("experience") or {}).get("max_candidats")),
    ("horizon_jours", lambda c: (c.get("experience") or {}).get("horizon_jours")),
    ("memoire", lambda c: (c.get("experience") or {}).get("memoire")),
)


class ComparaisonRefusee(ValueError):
    """Une des deux exécutions appartient à une expérience invalidée ou archivée.

    Le refus est un garde-fou d'usage, pas une contrainte de calcul (spec hygiène, P6) : les
    chiffres restent lisibles dans l'archive et sur la page de synthèse. Ce qui est freiné,
    c'est le rapprochement automatique — celui dont le tableau se retrouve cité six mois plus
    tard sans que personne ne se souvienne que l'un des deux côtés était fautif.
    """


def _statut_de_lexecution(dossier: str | Path) -> dict:
    """Statut de l'expérience à laquelle appartient un dossier d'exécution.

    L'arborescence est `<exp>/executions/<horodatage>` : l'expérience est deux crans au-dessus.
    """
    from experiences import statut as S

    return S.lire(Path(dossier).resolve().parent.parent)


def comparer(
    a: str | Path, b: str | Path, *, inclure_invalides: bool = False
) -> dict:
    """Comparable ⇔ empreintes de tout ce qui est partagé identiques ; jamais sur la foi des noms (RG-4).

    P6 — refuse d'apparier une exécution d'expérience `invalide` ou `archivee` à moins de
    `inclure_invalides=True`. Le message nomme le statut, la date et le motif.
    """
    from experiences import statut as S

    statuts = {"a": _statut_de_lexecution(a), "b": _statut_de_lexecution(b)}
    fautifs = [
        (cote, st) for cote, st in statuts.items() if st["statut"] != S.ACTIF
    ]
    if fautifs and not inclure_invalides:
        details = " · ".join(
            f"[{cote}] {st['statut']} le {st.get('le') or '?'} — "
            f"{st.get('motif') or 'sans motif consigné'}"
            for cote, st in fautifs
        )
        raise ComparaisonRefusee(
            f"comparaison refusée : {details}. "
            "Les chiffres restent lisibles dans l'archive ; pour les rapprocher malgré tout, "
            "relancer avec --inclure-invalides (le statut sera rappelé dans la sortie)."
        )
    ca = Execution.ouvrir(a).config
    cb = Execution.ouvrir(b).config
    differences = []
    for nom, lecteur in CHAMPS_PARTAGES:
        va, vb = lecteur(ca), lecteur(cb)
        if va != vb:
            differences.append({"champ": nom, "a": va, "b": vb})
    ga, gb = (
        (ca.get("empreintes") or {}).get("gabarit", {}),
        (cb.get("empreintes") or {}).get("gabarit", {}),
    )
    if ga.get("categorie") == gb.get("categorie") and ga.get("sha256") != gb.get(
        "sha256"
    ):
        differences.append(
            {
                "champ": "gabarit (même catégorie, texte différent)",
                "a": ga.get("sha256"),
                "b": gb.get("sha256"),
            }
        )
    sa, sb = synthese(a), synthese(b)
    return {
        "comparable": not differences,
        "differences": differences,
        # Rappelé dans la sortie même quand la comparaison est forcée : un tableau d'écarts
        # se copie, le motif doit voyager avec lui.
        "statuts": {cote: st["statut"] for cote, st in statuts.items()},
        "statuts_motifs": {
            cote: st.get("motif") for cote, st in statuts.items() if st.get("motif")
        },
        "force": bool(fautifs),
        "a": {
            "execution": sa["execution"],
            "experience": sa["experience"],
            "decideur": (ca.get("empreintes") or {}).get("decideur"),
            "parts_modales": sa["parts_modales"],
            "couverture": sa["couverture"],
            "statut": statuts["a"]["statut"],
        },
        "b": {
            "execution": sb["execution"],
            "experience": sb["experience"],
            "decideur": (cb.get("empreintes") or {}).get("decideur"),
            "parts_modales": sb["parts_modales"],
            "couverture": sb["couverture"],
            "statut": statuts["b"]["statut"],
        },
    }


def formater_comparaison(c: dict) -> str:
    out = []
    if c.get("force"):
        out.append(
            "⚠ COMPARAISON FORCÉE — un côté au moins n'est pas actif :"
        )
        for cote, statut in (c.get("statuts") or {}).items():
            if statut != "actif":
                motif = (c.get("statuts_motifs") or {}).get(cote) or "sans motif consigné"
                out.append(f"  [{cote}] {statut} — {motif}")
        out.append(
            "  Les écarts ci-dessous ne doivent pas être cités sans ce motif."
        )
    if not c["comparable"]:
        out.append("NON COMPARABLE — éléments partagés qui diffèrent :")
        out += [
            f"  - {d['champ']} : {str(d['a'])[:24]} ≠ {str(d['b'])[:24]}"
            for d in c["differences"]
        ]
    else:
        out.append("Comparables (toutes les empreintes partagées sont identiques).")
    for cle in ("a", "b"):
        x = c[cle]
        couv = x["couverture"]
        taux = f"{100 * couv['taux']:.1f} %" if couv.get("taux") is not None else "n/a"
        marque = "" if x.get("statut", "actif") == "actif" else f" [{x['statut']}]"
        out.append(
            f"[{cle}]{marque} {x['execution']} ({x['experience']}, décideur {(x['decideur'] or {}).get('type')}:{(x['decideur'] or {}).get('modele')}) "
            f"— couverture {couv.get('decides')}/{couv.get('attendus')} ({taux})"
        )
        out.append(
            "     "
            + " · ".join(
                f"{m} {v:.1f} %"
                for m, v in (x["parts_modales"]["pourcent"] or {}).items()
                if v is not None
            )
        )
    return "\n".join(out)


__all__ = [
    "CORRESPONDANCE_REFERENTIEL",
    "ETAT_ARCHIVE_MANQUANTE",
    "chemin_referentiel",
    "comparer",
    "ecrire_synthese",
    "formater_comparaison",
    "formater_table",
    "lire_referentiel",
    "lister",
    "synthese",
    "synthese_html",
    "trier_filtrer",
]
