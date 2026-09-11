"""Page de synthèse d'une exécution : composite + détail par sous-catégorie.

Spec : R5, R7, R9, R15, R16.

Les cellules par sous-catégorie sont rendues par le **même** ``_dimension_blocks``
que la page historique `docs/synthesis` (cf. `docs/arch/score-synthesis.md`) : elles
ne peuvent pas diverger. Seul l'habillage — en-tête composite, formule et son
empreinte, couverture, étiquette de volet — appartient à la plateforme d'expériences.

Volet 1 (décideur LLM) et volet 3 (décideur modèle) partagent ce rendu ; ils ne se
distinguent que par l'en-tête (le décideur nommé, et le SHA du modèle en volet 3).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from experiences import formule as F
from experiences import score as S

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.synthesis import charts
from scripts.synthesis.render import (
    CSS,
    _dimension_blocks,
    escape,
    missing_card,
    tiles,
)

F_SCORES = "scores.json"
F_SYNTHESE = "synthese.json"
F_PAGE = "synthese_scores.html"


def _num(x: float | None, digits: int = 2) -> str:
    return "—" if x is None else f"{x:.{digits}f}"


def _en_tete_decideur(scores: dict, synthese: dict) -> str:
    """Décrit le décideur ; en volet 3, expose le SHA du modèle (R15)."""
    dec = (synthese.get("empreintes") or {}).get("decideur") or {}
    if scores.get("volet") == "3":
        return (
            f"Volet 3 — Modèle statistique · artefact "
            f"<code>{escape((dec.get('sha256') or '')[:12])}</code>"
        )
    modele = dec.get("modele") or dec.get("type") or "décideur"
    return f"Volet 1 — Décideur LLM · <code>{escape(str(modele))}</code>"


def _bandeau_statut(st: dict | None) -> str:
    """Bandeau de tête quand l'expérience est invalidée ou archivée (spec hygiène §3.2).

    Le chiffre reste affiché — il est exact, il vient de l'archive scellée. Ce que le bandeau
    dit, c'est de ne pas le citer sans sa raison.
    """
    if not st or st.get("statut") == "actif":
        return ""
    libelle = {
        "invalide": "mesure invalidée",
        "archivee": "expérience archivée",
    }.get(st["statut"], st["statut"])
    motif = escape(str(st.get("motif") or "sans motif consigné"))
    quand = escape(str(st.get("le") or "?"))
    ref = st.get("reference")
    suite = f' · <code>{escape(str(ref))}</code>' if ref else ""
    return (
        f'<p class="bandeau-statut"><strong>{libelle}</strong> le {quand} — {motif}{suite}<br>'
        "Les chiffres ci-dessous sont ceux de l'archive, inchangés : "
        "ils ne doivent pas être cités sans ce motif.</p>"
    )


def rendu(
    scores: dict,
    synthese: dict,
    registre: F.RegistreFormules | None = None,
    statut: dict | None = None,
) -> str:
    """Produit le HTML autonome de la page de synthèse d'une exécution."""
    registre = registre or F.charger()
    volet = scores.get("volet", "1")
    prefix = "mod" if volet == "3" else "sim"
    comp = scores.get("composite") or {}
    couv = scores.get("couverture") or {}
    formule = scores.get("formule") or {}
    gview = scores.get("global") or {}
    non_mesurees = scores.get("dimensions_non_mesurees") or []

    perimee = not S.est_reference(scores, registre)
    badge = (
        '<span class="badge">⚠ formule périmée</span>'
        if perimee
        else '<span class="badge ok">formule de référence</span>'
    )

    taux = couv.get("taux")
    taux_txt = "—" if taux is None else f"{taux * 100:.1f}%"
    couv_txt = f"{couv.get('decides', '—')} / {couv.get('attendus', '—')} décisions"

    # En-tête : composite (les deux losses), L1 global, couverture (R9).
    entete_tiles = tiles(
        [
            ("Composite (EMD·JSD)", _num(comp.get("emd_jsd")), "masse de probabilité"),
            ("L1 Composite", _num(comp.get("l1"), 1), "points de %"),
            ("Composite (tiré)", _num(comp.get("emd_jsd_tire")), "après tirage"),
            ("Couverture", taux_txt, couv_txt),
        ]
    )

    alerte = ""
    if non_mesurees:
        # R8 — jamais un 0 silencieux : les dimensions non mesurées sont citées.
        alerte = (
            f'<p class="warn">Dimension(s) non mesurée(s) — repli vers la perte '
            f"maximale, pas un score parfait : "
            f"<strong>{escape(', '.join(non_mesurees))}</strong>.</p>"
        )

    global_bloc = ""
    if gview:
        global_bloc = f"<h3>Parts modales globales</h3>{charts.global_bullet(gview)}"

    details = {
        k: (v or {}).get("strates") for k, v in (scores.get("detail") or {}).items()
    }
    blocs = (
        _dimension_blocks(details, prefix)
        if details
        else missing_card(
            "Détail par sous-catégorie",
            "Aucun détail par strate dans ce résultat.",
            [],
            "",
        )
    )

    formule_ligne = (
        f"Formule <strong>{escape(formule.get('nom', '?'))}</strong> "
        f"<code>{escape((formule.get('sha256') or '')[:12])}</code> {badge}"
    )

    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scores — {escape(str(scores.get("experience") or ""))} / {escape(str(scores.get("execution") or ""))}</title>
<style>{CSS}
.solo{{max-width:1040px;margin:0 auto;padding:32px 40px 96px}}
.solo h1{{font-size:21px;font-weight:500;margin:0 0 4px;letter-spacing:-.015em}}
.solo .sub{{font-size:13px;color:var(--ink3);margin-bottom:6px}}
.warn{{color:var(--warn);font-size:13px;margin:10px 0}}
.bandeau-statut{{border-left:3px solid var(--warn);background:rgba(180,120,0,.07);
  padding:10px 14px;margin:0 0 18px;font-size:13px;line-height:1.55}}
@media(max-width:880px){{.solo{{padding:24px 20px 64px}}}}
</style></head>
<body><main class="solo">
<h1>{escape(str(scores.get("experience") or ""))} — {escape(str(scores.get("execution") or ""))}</h1>
{_bandeau_statut(statut)}
<div class="sub">{_en_tete_decideur(scores, synthese)}</div>
<div class="sub">{formule_ligne}</div>
<p style="color:var(--ink3);font-size:12.5px;margin:6px 0 18px">
Généré le {escape(scores.get("generate_le") or scores.get("genere_le") or "")} ·
composite importé du moteur de calibration (loss non réimplémentée).</p>
{entete_tiles}
{alerte}
{global_bloc}
<h3>Détail par sous-catégorie</h3>
<p>Une cellule par sous-catégorie&nbsp;: parts modales observées face à l'enquête EMC²
2023 (repère pointillé). <strong>Plus l'écart au repère est faible, meilleur c'est.</strong>
Les dimensions <span class="badge ok">dans le composite</span> entrent dans le score&nbsp;;
<span class="badge">hors composite</span> sont rapportées pour lecture seule.</p>
{blocs}
<footer>Recalculer&nbsp;: <code>python -m experiences score --toutes</code> ·
Chiffres produits par le même moteur que <code>docs/synthesis</code>.</footer>
</main></body></html>"""


def ecrire(
    dossier: str | Path, registre: F.RegistreFormules | None = None
) -> Path | None:
    """Lit scores.json + synthese.json d'une exécution, écrit synthese_scores.html.

    Renvoie None si l'exécution n'a pas encore de scores.json (non scorée / partielle)."""
    dossier = Path(dossier)
    scores_path = dossier / F_SCORES
    if not scores_path.exists():
        return None
    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    synthese = json.loads((dossier / F_SYNTHESE).read_text(encoding="utf-8"))
    # Le statut vit au niveau de l'expérience : deux crans au-dessus du dossier d'exécution.
    from experiences import statut as ST

    st = ST.lire(dossier.parent.parent)
    page = rendu(scores, synthese, registre, statut=st)
    cible = dossier / F_PAGE
    cible.write_text(page, encoding="utf-8")
    return cible


__all__ = ["ecrire", "rendu"]
