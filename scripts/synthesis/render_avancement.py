"""render_avancement.py — Page « Avancement et résultats » depuis le registre de mesures.

Rend `scripts/synthesis/avancement.yaml` en `docs/synthesis/avancement_et_resultats.html` :
un tableau « base de référence → base modifiée → modification → résultat → score », une
ligne par mesure faite.

## Pourquoi une page générée et pas une page écrite

Même raison que pour `index.html` et les archives de `docs/traces/` : un tableau de
résultats tenu à la main se périme au premier chiffre corrigé, et personne ne sait plus
lequel des deux documents dit vrai. Ici la source unique est le YAML, et la page en
découle.

## Ce que le rendu REFUSE

- une mesure sans `trace` — un score qu'on ne peut pas retracer jusqu'à une archive
  committée n'a pas à être publié ;
- une trace qui n'existe pas sur le disque — c'est le cas qui arrive vraiment, quand une
  archive est renommée et que la page continue d'y renvoyer ;
- un `verdict` hors vocabulaire.

Le refus est **bruyant et bloquant** : la page n'est pas réécrite. Une page de résultats
qui se dégrade en silence est pire que pas de page.

Usage :
    python -m scripts.synthesis.render_avancement [--out FICHIER] [--check]
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from scripts.synthesis.render import CSS

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "scripts" / "synthesis" / "avancement.yaml"
SYNTHESIS_DIR = ROOT / "docs" / "synthesis"
OUT = SYNTHESIS_DIR / "avancement_et_resultats.html"

# Les synthèses intermédiaires sont DÉCOUVERTES sur le disque, pas listées à la main :
# une liste écrite se périme au premier instantané ajouté. Deux exclusions explicites —
# la page elle-même, et les fichiers de travail (« index copy.html » et compagnie), qui
# ne sont pas des livrables et dont le lien ferait douter de tous les autres.
STRAY_MARKERS = (" copy", "copie", "-wip", ".bak")


def rel(target: str) -> str:
    """Chemin relatif depuis la page vers un chemin donné DEPUIS LA RACINE du dépôt.

    Calculé, pas écrit : un « ../ » compté à la main donne un lien qui a l'air juste et
    sort du dossier `docs/` — c'est l'erreur qui s'est produite au premier jet.
    """
    return os.path.relpath(ROOT / target, SYNTHESIS_DIR)

VERDICTS = {
    "adopte": ("Adopté", "ok", "en production"),
    "mesure": ("Mesuré", "warn", "mesuré, périmètre partiel"),
    "rejete": ("Rejeté", "muted", "hypothèse fermée"),
    "encours": ("En cours", "warn", "mesure incomplète"),
}
SCORE_KIND = {"better": "ok", "worse": "warn", "neutral": "muted"}

EXTRA_CSS = """
.mrow{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:0;margin:16px 0;overflow:hidden}
.mhead{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;
padding:14px 18px;border-bottom:1px solid var(--line)}
.mhead .t{font-size:15.5px;font-weight:500;letter-spacing:-.01em}
.mhead .tk{font-family:var(--mono);font-size:11.5px;color:var(--ink3)}
.badge{font-size:11px;padding:2px 8px;border-radius:999px;border:1px solid var(--line2);
color:var(--ink2);white-space:nowrap}
.badge.ok{color:var(--ok);border-color:var(--ok)}
.badge.warn{color:var(--warn);border-color:var(--warn)}
.badge.muted{color:var(--ink3)}
.mbody{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:0}
.cell{padding:14px 18px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}
.cell:last-child{border-right:none}
.mresult{padding:14px 18px;border-bottom:1px solid var(--line)}
.mresult .k{font-size:11px;color:var(--ink3);margin-bottom:6px}
.mresult .v{font-size:13.5px;color:var(--ink);line-height:1.6;max-width:92ch}
.cell .k{font-size:11px;color:var(--ink3);margin-bottom:6px;letter-spacing:.01em}
.cell .v{font-size:13.5px;color:var(--ink2);line-height:1.55}
.cell .v code{font-size:12px}
.mfoot{display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:13px 18px}
.score{font-size:20px;font-weight:500;letter-spacing:-.02em}
.score.ok{color:var(--ok)}
.score.warn{color:var(--warn)}
.score.muted{color:var(--ink2)}
.score2{font-size:12.5px;color:var(--ink3);line-height:1.4;max-width:52ch}
.caveat{font-size:12px;color:var(--warn);background:var(--warnbg);
border-radius:6px;padding:8px 11px;margin:10px 18px 14px;line-height:1.5}
.cmt{font-size:13px;color:var(--ink2);padding:0 18px 14px;max-width:88ch;font-style:italic}
.arrow{color:var(--ink3);padding:0 2px}
.mcomp{padding:12px 18px;border-bottom:1px solid var(--line);
display:flex;flex-direction:column;gap:6px}
.mcomp .k{font-size:11px;color:var(--ink3)}
.mcomp .v{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.lv{font-family:var(--mono);font-size:16px;color:var(--ink)}
.dl{font-size:14px;font-weight:500;margin-left:4px}
.dl.ok{color:var(--ok)}.dl.warn{color:var(--warn)}
.on{font-size:11.5px;color:var(--ink3)}
.na{font-size:12.5px;color:var(--ink3);font-style:italic}
.cnote{font-size:12px;color:var(--ink2);line-height:1.5;max-width:88ch}
.chart{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:16px 18px;margin:16px 0}
.chart .ch{font-size:13px;color:var(--ink2);margin-bottom:10px}
.chart .ch em{color:var(--ink3);font-style:normal;font-size:12px}
.chart svg{width:100%;height:auto;display:block}
.chart .cn{font-size:12px;color:var(--ink3);line-height:1.55;margin:10px 0 0;max-width:92ch}
.gl{stroke:var(--line);stroke-width:1}
.gt{font-size:10px;fill:var(--ink3);font-family:var(--mono)}
.ln{fill:none;stroke:var(--ink2);stroke-width:2}
.pt{fill:var(--card);stroke:var(--ink2);stroke-width:2}
.pt.best{fill:var(--ok);stroke:var(--ok)}
.pv{font-size:10.5px;fill:var(--ink2);font-family:var(--mono)}
.bnd{fill:var(--warn);opacity:.10;stroke:none}
.bnd-key{display:inline-block;width:22px;height:9px;border-radius:2px;
background:var(--warn);opacity:.28;vertical-align:middle;margin-right:2px}
.ax{font-size:10px;fill:var(--ink3);font-family:var(--mono)}
.grp2{margin:14px 0 4px}
.gh{font-size:11px;color:var(--ink3);text-transform:none;margin-bottom:8px;
border-bottom:1px solid var(--line);padding-bottom:5px}
.bl{display:grid;grid-template-columns:minmax(160px,2fr) minmax(120px,3fr) 62px 110px;
gap:10px;align-items:center;padding:5px 0;font-size:12.5px}
.bl.off{opacity:.45}
.bl .bn{color:var(--ink2);line-height:1.35}
.bl .bn em{display:block;font-style:normal;font-size:10.5px;color:var(--ink3);
font-family:var(--mono)}
.bb{position:relative;height:16px;background:var(--bg2,transparent);
border-left:none;border-radius:3px}
.zero{position:absolute;left:50%;top:-2px;bottom:-2px;width:1px;background:var(--line2)}
.bar{position:absolute;top:2px;bottom:2px;border-radius:2px}
.bar.ok{background:var(--ok)}.bar.warn{background:var(--warn)}
.bv{font-family:var(--mono);font-size:12.5px;text-align:right}
.bv.ok{color:var(--ok)}.bv.warn{color:var(--warn)}
.bl2{font-family:var(--mono);font-size:11px;color:var(--ink3);text-align:right}
.off-legend{opacity:.45}
@media (max-width:760px){.bl{grid-template-columns:1fr;gap:3px}
.bb{height:12px}.bv,.bl2{text-align:left}}
.links{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-left:auto}
.links a{font-size:12.5px}
.synth{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;
margin:14px 0}
.synth a{display:block;background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:13px 16px;text-decoration:none;color:var(--ink)}
.synth a:hover{border-color:var(--line2)}
.synth .f{font-family:var(--mono);font-size:11px;color:var(--ink3);margin-top:5px}
.synth .d{font-size:13.5px;line-height:1.4}
@media (max-width:760px){.mbody{grid-template-columns:1fr}
.cell{border-right:none}}
"""


def esc(text: object) -> str:
    """Échappe, puis rend les `…` en <code> — la seule syntaxe admise dans le registre."""
    out, parts = [], html.escape(str(text or "").strip()).split("`")
    for index, part in enumerate(parts):
        out.append(f"<code>{part}</code>" if index % 2 else part)
    return "".join(out)


def page_title(path: Path) -> str:
    """Titre lu dans le <title> de la page — la seule description qui ne se périme pas."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return path.stem
    start = head.find("<title>")
    if start < 0:
        return path.stem
    end = head.find("</title>", start)
    return html.unescape(head[start + 7:end].strip()) if end > 0 else path.stem


def intermediate_syntheses(out: Path) -> list[tuple[str, str]]:
    """(fichier, titre) des synthèses voisines, la page courante et les brouillons exclus."""
    found = []
    for path in sorted(SYNTHESIS_DIR.glob("*.html")):
        if path.name == out.name:
            continue
        if any(marker in path.name.lower() for marker in STRAY_MARKERS):
            continue
        found.append((path.name, page_title(path)))
    return found


# Horodatage écrit PAR le générateur dans la page elle-même (« … le 24/08/2026 à 12:03 »).
# C'est la seule heure qui survit à un `git clone` : les dates de fichiers, elles, sont
# celles du clone.
STAMP_IN_PAGE = re.compile(r"(\d{2})/(\d{2})/(\d{4})\s*à\s*(\d{2}):(\d{2})")


def linked_document(measure: dict) -> Optional[Path]:
    """Le document HTML que la ligne met en avant, ou son dossier de trace à défaut.

    Priorité à la **synthèse intermédiaire** : c'est la page que la mesure a fait bouger,
    donc celle dont l'heure situe la mesure. Sans elle, on prend le HTML de la trace, puis —
    faute de mieux — le dossier de trace, pour que les mesures dont la trace n'a pas de page
    ne soient pas les seules privées d'heure.
    """
    synthesis = measure.get("synthesis")
    if synthesis and (SYNTHESIS_DIR / synthesis).is_file():
        return SYNTHESIS_DIR / synthesis
    trace = ROOT / str(measure.get("trace") or "")
    if not trace.exists():
        return None
    index = trace / "index.html"
    if index.is_file():
        return index
    pages = sorted(trace.glob("*.html"))
    return pages[0] if len(pages) == 1 else trace


def document_time(path: Optional[Path]) -> tuple[Optional[datetime], str]:
    """(horodatage, provenance) du document lié — l'heure INSCRITE d'abord, le disque ensuite.

    Deux sources, et elles ne se valent pas :

    1. l'heure que le générateur a **écrite dans la page** — versionnée, donc identique sur
       toutes les machines ;
    2. à défaut, l'horodatage du fichier (création si le système la garde, sinon dernière
       modification) — pratique, mais **git ne restitue pas les dates** : après un clone,
       c'est la date du clone. Elle ne sert donc qu'à départager deux mesures du même jour,
       jamais à établir la date elle-même, qui vient du registre.
    """
    if path is None or not path.exists():
        return None, ""
    if path.is_file() and path.suffix == ".html":
        match = STAMP_IN_PAGE.search(path.read_text(encoding="utf-8", errors="replace")[:8000])
        if match:
            day, month, year, hour, minute = (int(g) for g in match.groups())
            try:
                return datetime(year, month, day, hour, minute), "inscrite dans la page liée"
            except ValueError:
                pass
    info = path.stat()
    stamp = getattr(info, "st_birthtime", None) or info.st_mtime
    return datetime.fromtimestamp(stamp), "lue sur le fichier lié (non versionnée)"


def measure_time(measure: dict) -> tuple[Optional[datetime], str]:
    """Heure d'une mesure, retenue SEULEMENT si le document lié tombe le jour de la mesure.

    Un document régénéré plus tard porte une heure qui ne situe plus rien : l'afficher en
    regard de la date du registre donnerait un couple date/heure qui n'a jamais existé. Dans
    ce cas la ligne n'affiche pas d'heure et garde sa place stable — l'absence est honnête,
    l'approximation ne le serait pas.
    """
    stamp, origin = document_time(linked_document(measure))
    if stamp is None:
        return None, ""
    if stamp.strftime("%Y-%m-%d") != str(measure.get("date") or ""):
        return None, ""
    return stamp, origin


def in_chronological_order(measures: list[dict]) -> list[dict]:
    """Mesures de la PLUS ANCIENNE à la plus récente, tri CALCULÉ et non confié au YAML.

    L'ordre d'affichage était celui de la saisie : une mesure ajoutée en tête du registre
    remontait en tête de page quelle que soit sa date — c'est ce qui est arrivé à la ligne
    de référence du 2026-08-25, écrite avant des mesures du 2026-08-24. Une page qui se lit
    comme une chronologie doit en être une, sinon elle raconte l'histoire dans le désordre
    sans que rien ne le signale.

    Le tri est **stable** : à date égale — le cas courant, plusieurs mesures tombant le même
    jour — l'ordre du registre est conservé, parce qu'il porte la dépendance entre mesures
    (le périmètre voiture seule avant le périmètre voiture ET vélo). La date ne saurait pas
    les départager, et un tri instable les intervertirait d'une régénération à l'autre.
    """
    def key(measure: dict) -> tuple[str, str]:
        stamp, _ = measure_time(measure)
        return (str(measure.get("date") or ""),
                stamp.strftime("%H:%M") if stamp else "")
    return sorted(measures, key=key)


def validate(registry: dict) -> list[str]:
    """Erreurs bloquantes. Une page de résultats fausse est pire qu'une page absente."""
    errors: list[str] = []
    measures = registry.get("measures") or []
    if not measures:
        errors.append("aucune mesure dans le registre")
    seen: set[str] = set()
    for index, measure in enumerate(measures):
        tag = measure.get("id") or f"#{index}"
        if not measure.get("id"):
            errors.append(f"{tag} : champ `id` manquant")
        elif measure["id"] in seen:
            errors.append(f"{tag} : `id` en doublon")
        else:
            seen.add(measure["id"])
        for field in ("subject", "reference", "modified", "change", "result", "score",
                      "verdict", "comment", "trace", "date"):
            if not measure.get(field):
                errors.append(f"{tag} : champ `{field}` manquant")
        verdict = measure.get("verdict")
        if verdict and verdict not in VERDICTS:
            errors.append(f"{tag} : verdict « {verdict} » hors vocabulaire "
                          f"({', '.join(VERDICTS)})")
        kind = measure.get("score_kind", "neutral")
        if kind not in SCORE_KIND:
            errors.append(f"{tag} : `score_kind` « {kind} » inconnu "
                          f"({', '.join(SCORE_KIND)})")
        # Le tri chronologique repose sur cette chaîne : une date au mauvais format
        # trierait de travers en silence, ce qui est pire qu'un refus.
        date = measure.get("date")
        if date:
            try:
                datetime.strptime(str(date), "%Y-%m-%d")
            except ValueError:
                errors.append(f"{tag} : date « {date} » — format attendu AAAA-MM-JJ "
                              f"(le tri chronologique de la page en dépend)")
        trace = measure.get("trace")
        if trace and not (ROOT / trace).exists():
            errors.append(f"{tag} : trace absente du disque — {trace}")
        synthesis = measure.get("synthesis")
        if synthesis and not (SYNTHESIS_DIR / synthesis).is_file():
            errors.append(f"{tag} : synthèse intermédiaire absente — "
                          f"docs/synthesis/{synthesis}")
    return errors


def row(measure: dict) -> str:
    label, tone, hint = VERDICTS[measure["verdict"]]
    # L'heure vient du document lié, pas du registre : elle situe la mesure dans sa
    # journée, et c'est elle qui départage deux mesures de la même date au tri. Sa
    # provenance est portée en infobulle — une heure sans source ne se vérifie pas.
    stamp, stamp_origin = measure_time(measure)
    stamp_text = f" à {stamp:%H:%M}" if stamp else ""
    # Chemin RELATIF À LA RACINE du dépôt : un chemin absolu ferait fuiter l'arborescence
    # de la machine de build dans une page destinée à être lue ailleurs.
    document = linked_document(measure)
    stamp_hint = (
        f"Heure {stamp_origin} — {document.relative_to(ROOT)}"
        if stamp and document else
        "Aucune heure : le document lié ne porte pas le jour de la mesure")
    kind = SCORE_KIND[measure.get("score_kind", "neutral")]
    href = rel(measure["trace"])

    # Les trois cellules d'ENTRÉE côte à côte ; le RÉSULTAT en pleine largeur, parce que
    # c'est le texte le plus long et qu'un tiers de colonne le hache en confettis.
    cells = [
        ("Base de référence", measure["reference"]),
        ("Nouvelle base modifiée", measure["modified"]),
        ("Modification faite", measure["change"]),
    ]
    # Les NIVEAUX de composite, quand la mesure en porte. Un écart seul ne dit pas d'où
    # l'on part : « −1,69 » se lit autrement à 26,75 qu'à 5,00.
    ref, mod = measure.get("composite_reference"), measure.get("composite_modified")
    jeu = measure.get("metric_dataset", "")
    if ref is not None:
        niveau = (f'<span class="lv">{ref:.2f}</span>'
                  f'<span class="arrow">→</span>'
                  f'<span class="lv">{mod:.2f}</span>'
                  f'<span class="dl {"ok" if mod < ref else "warn"}">{mod - ref:+.2f}</span>'
                  f'<span class="on">sur <code>{html.escape(str(jeu))}</code></span>')
    else:
        niveau = '<span class="na">composite non applicable</span>'
    note = (f'<div class="cnote">{esc(measure["composite_note"])}</div>'
            if measure.get("composite_note") else "")
    composite = (f'<div class="mcomp"><div class="k">Composite</div>'
                 f'<div class="v">{niveau}</div>{note}</div>')
    body = "".join(
        f'<div class="cell"><div class="k">{html.escape(k)}</div>'
        f'<div class="v">{esc(v)}</div></div>' for k, v in cells)
    result = (f'<div class="mresult"><div class="k">Résultats obtenus</div>'
              f'<div class="v">{esc(measure["result"])}</div></div>')

    caveat = (f'<div class="caveat"><strong>Lecture du score</strong> — '
              f'{esc(measure["score_caveat"])}</div>'
              if measure.get("score_caveat") else "")

    links = [f'<a href="{html.escape(href)}">trace archivée →</a>']
    if measure.get("synthesis"):
        page = measure["synthesis"]
        links.append(f'<a href="{html.escape(page)}">'
                     f'{html.escape(page_title(SYNTHESIS_DIR / page))} →</a>')
    links = "".join(links)
    # Un second chiffre quand la mesure porte plus d'un contraste : le taire ferait lire
    # la ligne comme si elle n'avait mesuré qu'une chose.
    second = (f'<span class="score2">{esc(measure["score_secondary"])}</span>'
              if measure.get("score_secondary") else "")

    return f"""<div class="mrow">
  <div class="mhead">
    <span class="t">{esc(measure["subject"])}</span>
    <span class="tk" title="{html.escape(stamp_hint)}">ticket
      {html.escape(str(measure.get("ticket", "—")))} ·
      {html.escape(str(measure["date"]))}{stamp_text}</span>
    <span class="badge {tone}" title="{html.escape(hint)}">{html.escape(label)}</span>
  </div>
  <div class="mbody">{body}</div>
  {composite}
  {result}
  <div class="mfoot">
    <span class="score {kind}">{esc(measure["score"])}</span>
    {second}
    <span class="links">{links}</span>
  </div>
  {caveat}
  <div class="cmt">{esc(measure["comment"])}</div>
</div>"""



# ── Les deux graphiques ──────────────────────────────────────────────────────
#
# ⚠ Il y en a DEUX, et jamais un seul. Une courbe unique sur les mesures serait un
# artefact : ce sont des ÉCARTS et non des niveaux, lus sur des jeux différents (`rank`,
# `val`, run-à-run) et dans des unités différentes (composite, points de part modale,
# points de L1) — et cinq sur sept n'ont jamais été appliquées. Les cumuler montrerait une
# progression qui n'a pas eu lieu.
#
# La seule série de NIVEAUX est celle des runs de production : c'est elle qui répond à
# « est-ce que ça s'améliore ».

METRIC_LABEL = {
    "composite": "composite",
    "part_modale": "points de part modale",
    "l1_zone": "points de L1 par zone",
}


def chart_runs(runs: list[dict], noise: dict | None = None) -> str:
    """Composite des runs de production dans le temps — des NIVEAUX, pas des écarts.

    ⚠ La courbe porte sa **bande de bruit**, et c'est elle qui la rend lisible. Un run a
    son propre plancher, mesuré par permutation : re-découper le MÊME run en deux moitiés
    déplace le composite de −4,4 à +5,4 points. Sans cette bande, un lecteur lirait des
    progrès et des régressions là où il n'y a que du découpage — la même erreur que le
    témoin nul évite au niveau des jeux gelés.
    """
    if len(runs) < 2:
        return ""
    W, H, PL, PR, PT, PB = 760, 210, 46, 16, 18, 42
    values = [float(r["composite"]) for r in runs]
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    lo, hi = lo - span * 0.18, hi + span * 0.18
    iw, ih = W - PL - PR, H - PT - PB
    x = lambda i: PL + (iw * i / max(1, len(runs) - 1))
    y = lambda v: PT + ih * (hi - v) / (hi - lo)

    # La bande de bruit, centrée sur CHAQUE point : c'est l'amplitude dans laquelle un
    # composite peut se promener sans qu'aucune cause ne l'explique.
    band = ""
    if noise and noise.get("min") is not None:
        lo_n, hi_n = float(noise["min"]), float(noise["max"])
        haut = " ".join(f"{x(i):.1f},{y(min(hi, v - lo_n)):.1f}"
                        for i, v in enumerate(values))
        bas = " ".join(f"{x(i):.1f},{y(max(lo, v - hi_n)):.1f}"
                       for i, v in reversed(list(enumerate(values))))
        band = f'<polygon class="bnd" points="{haut} {bas}"/>'

    grid = "".join(
        f'<line x1="{PL}" y1="{y(v):.1f}" x2="{W - PR}" y2="{y(v):.1f}" class="gl"/>'
        f'<text x="{PL - 8}" y="{y(v) + 4:.1f}" class="gt" text-anchor="end">{v:.0f}</text>'
        for v in (lo + (hi - lo) * k / 4 for k in range(5)))
    path = " ".join(f"{'M' if i == 0 else 'L'}{x(i):.1f},{y(v):.1f}"
                    for i, v in enumerate(values))
    pts = ""
    for i, r in enumerate(runs):
        v = float(r["composite"])
        best = v == min(values)
        pts += (f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="{5 if best else 4}" '
                f'class="pt{" best" if best else ""}">'
                f'<title>{html.escape(str(r["run"]))} — composite {v:.2f} sur '
                f'{r.get("n_trips", "?")} trajets, {r.get("n_persons", "?")} personnes'
                f'</title></circle>'
                # Le premier et le dernier point touchent les bords : leur étiquette
                # centrée mordrait sur la graduation de gauche ou sortirait à droite.
                f'<text x="{x(i):.1f}" y="{y(v) - 11:.1f}" class="pv" '
                f'text-anchor="{"start" if i == 0 else "end" if i == len(runs) - 1 else "middle"}"'
                f'>{v:.2f}</text>'
                f'<text x="{x(i):.1f}" y="{H - PB + 16:.1f}" class="ax" '
                f'text-anchor="middle">{html.escape(str(r["run"])[5:10])}</text>')
    legende = ""
    if noise and noise.get("min") is not None:
        legende = (f'<p class="cn"><span class="bnd-key"></span> <strong>Bande de '
                   f'bruit d\'un run</strong> — {float(noise["min"]):+.1f} à '
                   f'{float(noise["max"]):+.1f} points, mesurés en re-découpant le MÊME '
                   f'run en deux moitiés ({noise.get("n_draws", "?")} tirages, '
                   f'{html.escape(str(noise.get("source_run", "")))}). Rien de réel ne '
                   f'change dans ce test. <strong>Tous les écarts entre runs consécutifs '
                   f'de cette courbe sont plus petits que cette bande</strong> : aucun '
                   f'n\'est attribuable à une cause, y compris le −1,88 de la ligne « Run '
                   f'de référence ». La courbe dit où en est la production, pas pourquoi.</p>')

    return f"""<div class="chart">
  <div class="ch">Composite des runs de production — <em>plus bas, mieux c'est</em></div>
  <svg viewBox="0 0 {W} {H}" role="img" preserveAspectRatio="xMidYMid meet">
    {grid}{band}<path d="{path}" class="ln"/>{pts}
  </svg>
  {legende}
  <p class="cn">La seule série de <strong>niveaux</strong> du dépôt : chaque point est un run
  entier scoré contre l'enquête. ⚠ Ces runs ne sont <strong>pas strictement
  comparables</strong> — la composition de la flotte de modèles, le périmètre et le taux de
  repli d'erreur diffèrent d'un run à l'autre. La courbe dit où en est la production ; elle
  n'attribue aucun écart à aucune cause. Elle n'est pas monotone, et c'est un fait, pas un
  défaut d'affichage.</p>
</div>"""


def chart_measures(measures: list[dict]) -> str:
    """Une barre par mesure, GROUPÉE PAR UNITÉ. Jamais un axe commun.

    Les mesures rejetées ou au périmètre partiel sont marquées : elles n'ont pas bougé la
    production, et les aligner avec les mesures adoptées ferait lire un cumul qui n'existe
    pas.
    """
    par_unite: dict[str, list[dict]] = {}
    for m in measures:
        par_unite.setdefault(m.get("metric", "composite"), []).append(m)

    blocs = []
    for unite, groupe in par_unite.items():
        lignes = [m for m in groupe
                  if m.get("composite_reference") is not None or unite != "composite"]
        if not lignes:
            continue
        deltas = []
        for m in lignes:
            ref, mod = m.get("composite_reference"), m.get("composite_modified")
            deltas.append((m, (mod - ref) if ref is not None else None))
        echelle = max((abs(d) for _, d in deltas if d is not None), default=1.0) or 1.0
        rows = ""
        for m, d in deltas:
            applique = m["verdict"] == "adopte"
            if d is None:
                rows += (f'<div class="bl"><span class="bn">{esc(m["subject"])}</span>'
                         f'<span class="bb"><span class="na">composite non applicable</span>'
                         f'</span><span class="bv na">{esc(m.get("score"))}</span></div>')
                continue
            largeur = 50 * abs(d) / echelle
            gauche = 50 - largeur if d < 0 else 50
            ton = "ok" if d < 0 else "warn"
            rows += (
                f'<div class="bl{"" if applique else " off"}">'
                f'<span class="bn">{esc(m["subject"])}'
                f'<em>{html.escape(str(m.get("metric_dataset", "")))}</em></span>'
                f'<span class="bb"><span class="zero"></span>'
                f'<span class="bar {ton}" style="left:{gauche:.1f}%;width:{largeur:.1f}%">'
                f'</span></span>'
                f'<span class="bv {ton}">{d:+.2f}</span>'
                f'<span class="bl2">{m["composite_reference"]:.2f} → '
                f'{m["composite_modified"]:.2f}</span></div>')
        blocs.append(f'<div class="grp2"><div class="gh">Mesuré en '
                     f'{html.escape(METRIC_LABEL.get(unite, unite))}</div>{rows}</div>')

    return f"""<div class="chart">
  <div class="ch">Ce que chaque mesure a déplacé — <em>vers la gauche, mieux c'est</em></div>
  {"".join(blocs)}
  <p class="cn">Des <strong>écarts</strong>, pas des niveaux : ils ne se cumulent pas, et ils
  ne se comparent pas d'un groupe à l'autre — un point de composite et un point de part
  modale ne sont pas la même chose. Les lignes <span class="off-legend">estompées</span> sont
  les mesures qui <strong>n'ont pas été appliquées</strong> : rejetées, ou au périmètre
  partiel. Le libellé en petit rappelle le jeu de lecture, qui porte son propre niveau de
  bruit.</p>
</div>"""

def render(registry: dict) -> str:
    meta = registry.get("meta") or {}
    measures = in_chronological_order(registry["measures"])
    counts = {key: sum(1 for m in measures if m["verdict"] == key) for key in VERDICTS}
    tiles = "".join(
        f'<div class="tile"><div class="k">{html.escape(VERDICTS[k][0])}</div>'
        f'<div class="v">{v}</div><div class="u">{html.escape(VERDICTS[k][2])}</div></div>'
        for k, v in counts.items() if v)
    rows = "".join(row(m) for m in measures)
    charts = (chart_runs(registry.get("runs") or [], registry.get("runs_noise"))
              + chart_measures(measures))

    syntheses = intermediate_syntheses(OUT)
    cards = "".join(
        f'<a href="{html.escape(name)}"><span class="d">{html.escape(title)}</span>'
        f'<span class="f">{html.escape(name)}</span></a>' for name, title in syntheses)
    archives = sorted(q.name for q in (SYNTHESIS_DIR / "archive").glob("*")
                      if q.is_dir()) if (SYNTHESIS_DIR / "archive").is_dir() else []
    archive_note = (
        f'<p style="font-size:12.5px;color:var(--ink3)">Et {len(archives)} instantané(s) '
        f'plus anciens sous <a href="archive/">archive/</a> — du '
        f'{html.escape(archives[0])} au {html.escape(archives[-1])}.</p>'
        if archives else "")
    proto_href = html.escape(rel("docs/arch/protocole-parametre-exogene.md"))
    traces_href = html.escape(rel("docs/traces"))
    nav_syntheses = "".join(
        f'<a href="{html.escape(name)}">{html.escape(title.split("—")[0].strip()[:30])}</a>'
        for name, title in syntheses)

    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(str(meta.get("title", "Avancement et résultats")))}</title>
<style>{CSS}{EXTRA_CSS}</style></head><body>
<div class="wrap"><nav>
  <h1>{html.escape(str(meta.get("title", "Avancement")))}</h1>
  <div class="sub">{len(measures)} mesure(s)</div>
  <div class="grp">Synthèses intermédiaires</div>
  {nav_syntheses}
  <div class="grp">Voir aussi</div>
  <a href="{proto_href}">Protocole de mesure</a>
  <a href="{traces_href}">Traces archivées</a>
</nav><main>
<section>
  <h2>{html.escape(str(meta.get("title", "Avancement et résultats")))}</h2>
  <p class="lede">{esc(meta.get("subtitle"))}</p>
  <div class="tiles">{tiles}</div>
  {charts}
  <div class="card"><strong>Lire le composite</strong> — {esc(meta.get("metric_note"))}</div>
  {rows}
</section>
<section id="syntheses">
  <h2>Synthèses intermédiaires</h2>
  <p class="lede">Les pages de score que ces mesures ont fait bouger. Une mesure ci-dessus
  dit ce qu'un changement a rendu <em>sur des jeux gelés</em> ; ces pages-ci scorent un
  <strong>run</strong> ou un instantané daté. Les mêler sous un même chiffre ferait perdre
  le seul repère qui compte : de quoi le score parle.</p>
  <div class="synth">{cards}</div>
  {archive_note}
</section>
<section>
  <p style="font-size:12px;color:var(--ink3);margin-top:8px">
    Page <strong>générée</strong> par <code>scripts/synthesis/render_avancement.py</code>
    depuis <code>scripts/synthesis/avancement.yaml</code> — ne pas éditer à la main.
    Chaque score renvoie à une trace committée ; le rendu refuse une ligne sans trace
    existante.</p>
</section>
</main></div></body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--check", action="store_true",
                        help="valide le registre sans écrire la page")
    args = parser.parse_args()

    registry = yaml.safe_load(args.registry.read_text(encoding="utf-8"))
    errors = validate(registry)
    if errors:
        print("[REFUS] le registre ne passe pas la validation — la page n'est PAS "
              "réécrite :", file=sys.stderr)
        for error in errors:
            print(f"  · {error}", file=sys.stderr)
        return 1

    measures = in_chronological_order(registry["measures"])
    print(f"  {len(measures)} mesure(s) validée(s) :")
    for measure in measures:
        print(f"    {VERDICTS[measure['verdict']][0]:8} {measure['score']:42} "
              f"{measure['subject'][:52]}")
    if args.check:
        print("\n  [check] rien n'a été écrit.")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(registry), encoding="utf-8")
    print(f"\n  écrit → {args.out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
