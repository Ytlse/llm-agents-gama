"""build_ab_detail.py — Détail par sous-catégorie d'un A/B de jeux gelés (ticket 023).

La page d'avancement donne un **composite par bras**. Un composite est une note agrégée :
il dit qu'un bras est meilleur, jamais **où**. Cette page-ci ouvre l'agrégat, dimension par
dimension et catégorie par catégorie, comme le fait `docs/synthesis/index.html` pour un run.

**Aucun appel LLM.** Les décisions individuelles `(agent_id, mode, poids)` sont déjà dans la
table `evals` du store, écrites lors de l'A/B ; on les relit et on rejoint les traits des
personas depuis le jeu gelé. Tout est donc rejouable à volonté.

## Ce que la page montre, et ce qu'elle ne prouve pas

⚠ **Un écart par catégorie est encore plus bruyant que le composite.** Le témoin nul de
cette campagne déplace le composite AGRÉGÉ de deux points sans rien changer à la
distribution ; sur une catégorie de vingt personas, il déplacera bien davantage. La page
affiche donc systématiquement l'effectif, et le bras `v9n` sert de règle : **tout écart plus
petit que celui du témoin nul, sur la même catégorie, n'est pas un effet.**

Usage :
    python -m scripts.synthesis.build_ab_detail --dataset val
    python -m scripts.synthesis.build_ab_detail --dataset screen --out autre.html
"""

from __future__ import annotations

import argparse
import contextlib
import html
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import yaml

from scripts.synthesis.render import CSS

ROOT = Path(__file__).resolve().parents[2]
CALIB = ROOT / "prompt_calibration"
OUT_DIR = ROOT / "docs" / "synthesis"

MODES = ("marche", "velo", "voiture", "transports_collectifs")
MODE_LABEL = {"marche": "marche", "velo": "vélo", "voiture": "voiture",
              "transports_collectifs": "TC"}

# `(clé de la cible, colonne du dataframe, titre, ordre d'affichage)`. L'ordre compte pour
# l'âge et la distance, qui sont ORDINAUX : les afficher par ordre alphabétique ferait lire
# « 10-14 » entre « 0-1km » et « 20-24 ».
DIMENSIONS = (
    ("Age", "age_cat", "Âge",
     ("5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39", "40-44",
      "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-130")),
    ("distance", "dist_cat", "Distance",
     ("0-1km", "1-2km", "2-5km", "5-10km", "10-20km", "20-50km", "plus_50km")),
    ("genre", "genre", "Genre", ("Homme", "Femme")),
    ("occupation", "occupation", "Occupation", None),
    ("motif_deplacement", "motif", "Motif de déplacement", None),
)

# Les bras, dans l'ordre de lecture, avec ce que chacun sert à lire.
ARMS = (
    ("v9", "référence — année entière"),
    ("v10", "fenêtre d'enquête"),
    ("v9n", "TÉMOIN NUL — la règle de lecture"),
    ("v10b", "bulletin du jour"),
    ("v10c", "agenda annoté"),
)


@contextlib.contextmanager
def _dans(chemin: Path):
    """Exécute le bloc depuis `chemin`, et revient toujours — même sur exception."""
    avant = Path.cwd()
    os.chdir(chemin)
    try:
        yield
    finally:
        os.chdir(avant)


def load_frames(dataset: str, db: Path, config_path: Path):
    """`{bras: dataframe}` — décisions du store, jointes aux traits des personas.

    Le dataframe est celui de l'évaluateur : un persona y pèse 1, réparti sur les modes
    qu'il pourrait prendre. On somme donc des POIDS, jamais des lignes.
    """
    sys.path.insert(0, str(CALIB))
    from calibration.cli import load_records, metadata_by_id
    from calibration.evaluation import decisions_to_df
    from calibration.models import RunConfig

    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute(
        "select params_key, decisions from evals where dataset = ? order by id",
        (dataset,)).fetchall()

    frames = {}
    for params_key, decisions in rows:
        version = next((p[3:] for p in params_key.split("|") if p.startswith("ds=")), None)
        if version is None or not decisions:
            continue
        config = RunConfig.from_yaml(config_path)
        config.dataset_version = version
        try:
            # ⚠ `run_ab_chaine.yaml` porte des chemins RELATIFS à `prompt_calibration`
            # (`calibration_datasets`, `../scripts/data/...`). Lancé depuis la racine du
            # dépôt, `load_records` ne trouve rien — et un `except` muet ferait passer
            # ça pour « aucun bras mesuré ».
            with _dans(CALIB):
                records = load_records(config, dataset)
        except FileNotFoundError as exc:
            print(f"  [ignoré] {version}/{dataset} : {exc}", file=sys.stderr)
            continue
        # La DERNIÈRE éval d'un `ds=` gagne : c'est celle que l'A/B vient d'écrire.
        frames[version] = decisions_to_df(json.loads(decisions), metadata_by_id(records))
    return frames


def shares(frame, mask=None) -> tuple[dict, float]:
    """Parts modales pondérées et masse, sur tout le frame ou un sous-ensemble."""
    sub = frame if mask is None else frame[mask]
    if sub is None or sub.empty or "mode_cat" not in sub:
        return {}, 0.0
    total = float(sub["weight"].sum())
    if total <= 0:
        return {}, 0.0
    return ({str(k): 100 * float(v) / total
             for k, v in sub.groupby("mode_cat")["weight"].sum().items()}, total)


def l1(part: dict, target: dict) -> float | None:
    """Distance L1 aux quatre modes de la cible, en points de pourcentage.

    `None` quand la cible ne porte pas la catégorie : une distance à rien vaudrait zéro,
    c'est-à-dire le score parfait — le motif « vacuité ≠ perfection » du dépôt.
    """
    if not part or not target:
        return None
    ref = {m: float(target.get(m, 0.0)) for m in MODES}
    somme = sum(ref.values())
    if somme <= 0:
        return None
    ref = {m: 100 * v / somme for m, v in ref.items()}
    return sum(abs(part.get(m, 0.0) - ref[m]) for m in MODES)


def cell(value: float | None, ton: str = "") -> str:
    if value is None:
        return '<td class="na">—</td>'
    return f'<td class="{ton}">{value:.1f}</td>'


# Traits des bras dans les petits multiples. Le témoin nul est en pointillé : ce n'est
# pas un traitement, c'est la règle de lecture — il ne doit pas se lire comme une courbe
# de plus.
ARM_STYLE = {
    "v9":   ("#8a8f98", "", "référence"),
    "v10":  ("#2f6f4e", "", "fenêtre"),
    "v9n":  ("#c08a2e", "3 3", "témoin nul"),
    "v10b": ("#7a5ea8", "", "bulletin"),
    "v10c": ("#b4553c", "", "agenda"),
}


def profiles(detail, cats, arms) -> str:
    """Petits multiples : un mini-graphe par mode, une courbe par bras.

    Même grammaire visuelle que `docs/synthesis/detail_simulation.html` — mêmes classes
    `cx-*`, mêmes proportions —, à ceci près qu'ici les courbes sont des **bras** et non
    un observé unique. La cible EMC² reste le repère pointillé.

    ⚠ Une courbe par bras rend l'écart VISIBLE, pas SIGNIFICATIF. Le témoin nul est tracé
    en pointillé pour cette raison : tout ce qui tient dans l'écart entre lui et la
    référence est du bruit, quelle que soit la beauté de la courbe.
    """
    if not cats:
        return ""
    cell_w, cell_h, gap, cols = 300, 124, 18, 2
    rows_n = (len(MODES) + cols - 1) // cols
    total_w, total_h = cols * cell_w + gap, rows_n * cell_h + (rows_n - 1) * gap
    plot_l, plot_t, plot_b = 32, 20, 26

    peak = 1.0
    for c in cats:
        e = detail[c]
        peak = max(peak, max(e["target"].values() or [0]),
                   *[max(e["actual"][a].values() or [0]) for a in arms])
    top = min(100.0, (int(peak / 10) + 1) * 10.0)

    parts = [f'<svg viewBox="0 0 {total_w} {total_h}" width="100%" '
             f'style="max-width:{total_w}px" role="img" '
             f'preserveAspectRatio="xMinYMin meet">']
    for idx, mode in enumerate(MODES):
        ox = (idx % cols) * (cell_w + gap)
        oy = (idx // cols) * (cell_h + gap)
        pw, ph = cell_w - plot_l - 22, cell_h - plot_t - plot_b
        xs = [ox + plot_l + (pw * i / max(1, len(cats) - 1)) for i in range(len(cats))]
        yv = lambda v: oy + plot_t + ph * (1 - min(v, top) / top)
        parts.append(f'<text class="cx-sub" x="{ox}" y="{oy + 11}">'
                     f'{html.escape(MODE_LABEL[mode])}</text>')
        for k in range(3):
            g = top * k / 2
            parts.append(f'<line class="cx-grid" x1="{ox + plot_l}" y1="{yv(g):.1f}" '
                         f'x2="{ox + plot_l + pw}" y2="{yv(g):.1f}"/>'
                         f'<text class="cx-axis-label" x="{ox + plot_l - 6}" '
                         f'y="{yv(g) + 3:.1f}" text-anchor="end">{g:.0f}</text>')
        ref = " ".join(f"{xs[i]:.1f},{yv(detail[c]['target'].get(mode, 0.0)):.1f}"
                       for i, c in enumerate(cats))
        parts.append(f'<polyline class="cx-ref-line" points="{ref}"/>')
        for arm in arms:
            couleur, dash, _ = ARM_STYLE.get(arm, ("#666", "", arm))
            pts = " ".join(f"{xs[i]:.1f},{yv(detail[c]['actual'][arm].get(mode, 0.0)):.1f}"
                           for i, c in enumerate(cats))
            d = f' stroke-dasharray="{dash}"' if dash else ""
            parts.append(f'<polyline points="{pts}" fill="none" stroke="{couleur}"'
                         f' stroke-width="1.6"{d}/>')
        for i, c in enumerate(cats):
            if i % max(1, len(cats) // 6) == 0 or i == len(cats) - 1:
                parts.append(f'<text class="cx-axis-label" x="{xs[i]:.1f}" '
                             f'y="{oy + cell_h - 8}" text-anchor="middle">'
                             f'{html.escape(str(c)[:7])}</text>')
    parts.append("</svg>")

    cle = "".join(
        f'<span class="lg"><span class="sw" style="background:{ARM_STYLE[a][0]}'
        f'{";opacity:.6" if ARM_STYLE[a][1] else ""}"></span>{html.escape(a)}'
        f' <em>{html.escape(ARM_STYLE[a][2])}</em></span>' for a in arms if a in ARM_STYLE)
    cle += '<span class="lg"><span class="sw ref"></span>EMC² <em>la cible</em></span>'
    return f'<div class="lgd">{cle}</div>{"".join(parts)}'


def dimension_table(frames, dim_key, col, titre, ordre, targets) -> str:
    cible_dim = (targets or {}).get(dim_key) or {}
    arms = [a for a, _ in ARMS if a in frames]
    base = frames[arms[0]]
    if col not in base.columns:
        return ""

    cats = [c for c in (ordre or sorted(str(x) for x in base[col].dropna().unique()))
            if c in set(str(x) for x in base[col].dropna().unique())]
    if not cats:
        return ""

    lignes, detail = "", {}
    for cat in cats:
        cellules, masse = "", 0.0
        valeurs = {}
        cible_cat = cible_dim.get(cat) or {}
        somme = sum(float(cible_cat.get(m, 0.0)) for m in MODES) or 1.0
        detail[cat] = {"target": {m: 100 * float(cible_cat.get(m, 0.0)) / somme
                                  for m in MODES},
                       "actual": {}}
        for arm in arms:
            f = frames[arm]
            m = f[col].astype(str) == cat
            part, poids = shares(f, m)
            masse = max(masse, poids)
            detail[cat]["actual"][arm] = {k: part.get(k, 0.0) for k in MODES}
            valeurs[arm] = l1(part, cible_dim.get(cat))
        # Le témoin nul sert de règle : un écart plus petit que le sien n'est pas un
        # effet. ⚠ MAIS c'est UN SEUL tirage, pas une estimation de variance — et quand
        # il tombe à zéro, le test devient VIDE : tout écart le dépasse, donc tout
        # devient « signal ». Un plancher nul n'est pas un plancher parfait, c'est une
        # absence de plancher. On le marque comme non testable.
        bruit = (abs(valeurs.get("v9n") - valeurs.get("v9"))
                 if valeurs.get("v9n") is not None and valeurs.get("v9") is not None
                 else None)
        testable = bruit is not None and bruit > 0.05
        for arm in arms:
            ton = "ref" if arm == "v9" else "noise" if arm == "v9n" else ""
            cellules += cell(valeurs[arm], ton)
        d = (valeurs.get("v10c") - valeurs.get("v10")
             if valeurs.get("v10c") is not None and valeurs.get("v10") is not None
             else None)
        if d is None:
            delta = '<td class="na">—</td>'
        elif not testable:
            delta = (f'<td class="muted" title="le témoin nul ne bouge pas sur cette '
                     f'catégorie : sans plancher, rien n\'est testable ici">'
                     f'{d:+.1f} <span class="nt">?</span></td>')
        elif abs(d) <= bruit:
            delta = (f'<td class="muted" title="plus petit que le témoin nul '
                     f'({bruit:.1f}) : pas un effet">{d:+.1f}</td>')
        else:
            delta = f'<td class="{"ok" if d < 0 else "warn"}"><strong>{d:+.1f}</strong></td>'
        bruit_c = (f'<td class="noise">{bruit:.1f}</td>' if testable else
                   '<td class="na" title="témoin nul immobile : pas de plancher">0,0</td>')
        lignes += (f'<tr><th>{html.escape(str(cat))}</th>'
                   f'<td class="n">{masse:.0f}</td>{cellules}{bruit_c}{delta}</tr>')

    entetes = "".join(f'<th title="{html.escape(desc)}">{html.escape(a)}</th>'
                      for a, desc in ARMS if a in frames)
    graphe = profiles(detail, [c for c in cats if any(detail[c]["target"].values())], arms)
    return f"""<h3>{html.escape(titre)}</h3>
{graphe}
<div class="tw"><table class="dt">
<thead><tr><th>catégorie</th><th class="n">masse</th>{entetes}
<th class="noise" title="|v9n − v9| : ce qu'un re-tirage sans effet produit sur cette
catégorie">bruit</th>
<th title="v10c − v10 : l'agenda annoté, à tirage identique">Δ agenda</th></tr></thead>
<tbody>{lignes}</tbody></table></div>"""


def render(frames, dataset: str, targets: dict) -> str:
    arms = [a for a, _ in ARMS if a in frames]
    resume = ""
    for arm, desc in ARMS:
        if arm not in frames:
            continue
        part, masse = shares(frames[arm])
        cible = (targets or {}).get("global") or {}
        resume += (f'<tr><th>{html.escape(arm)}</th>'
                   f'<td class="d">{html.escape(desc)}</td>'
                   + "".join(f'<td>{part.get(m, 0.0):.2f}</td>' for m in MODES)
                   + f'<td class="n">{masse:.0f}</td>'
                   + cell(l1(part, cible)) + '</tr>')
    cible_g = (targets or {}).get("global") or {}
    somme = sum(float(cible_g.get(m, 0)) for m in MODES) or 1
    ligne_cible = ('<tr class="tgt"><th>EMC²</th><td class="d">la cible</td>'
                   + "".join(f'<td>{100 * float(cible_g.get(m, 0)) / somme:.2f}</td>'
                             for m in MODES)
                   + '<td class="n">—</td><td class="na">—</td></tr>')

    n_personas = int(frames[arms[0]]["agent_id"].nunique()) if arms else 0
    tables = "".join(dimension_table(frames, k, c, t, o, targets)
                     for k, c, t, o in DIMENSIONS)

    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Détail par sous-catégorie — A/B météo ({html.escape(dataset)})</title>
<style>{CSS}{EXTRA}</style></head><body>
<div class="wrap"><nav>
  <h1>Détail A/B météo</h1>
  <div class="sub">{n_personas} personas · jeu <code>{html.escape(dataset)}</code></div>
  <div class="grp">Jeux de lecture</div>
  <a href="ab_meteo_detail_val.html">val — indépendant</a>
  <a href="ab_meteo_detail_screen.html">screen — &sub; train</a>
  <div class="grp">Voir aussi</div>
  <a href="avancement_et_resultats.html">Avancement et résultats</a>
  <a href="../traces/2026-08-25_ab_meteo/README.md">Trace de l'A/B</a>
  <a href="index.html">Synthèse des scores</a>
</nav><main>
<section>
<h2>Détail par sous-catégorie — A/B météo, jeu <code>{html.escape(dataset)}</code></h2>
<p class="lede">Le composite dit qu'un bras est meilleur ; il ne dit jamais <em>où</em>.
Cette page ouvre l'agrégat. Les chiffres sont des <strong>distances L1 à la cible EMC²</strong>,
en points de pourcentage, sur les quatre modes renormalisés — <strong>plus bas, mieux
c'est</strong>. Mesuré sur {n_personas} personas distincts.</p>

<div class="card"><strong>Comment lire la colonne « bruit »</strong> — c'est
<code>|v9n − v9|</code>, l'écart que produit le <strong>témoin nul</strong> sur cette
catégorie : un jeu qui rejoue le tirage sans changer aucune distribution. Tout Δ plus petit
que lui n'est pas un effet, il est <span class="muted">estompé</span> dans la colonne de
droite. ⚠ Sur une catégorie de vingt personas, ce bruit est bien plus grand que sur
l'agrégat — c'est la raison d'être de la colonne, et la raison pour laquelle la masse est
affichée à côté.</div>

<div class="card"><strong>⚠ Ce plancher est UN SEUL tirage, pas une variance</strong> — et
quand il tombe à zéro, le test devient <em>vide</em> : tout écart le dépasse, donc tout
passerait pour un signal. Un plancher nul n'est pas un plancher parfait, c'est une absence de
plancher. Ces lignes portent un <span class="nt">?</span> et ne concluent rien. Plus
généralement, <strong>cette page ne démontre rien à elle seule</strong> : elle sert à voir
<em>où</em> les bras diffèrent, pas à décider s'ils diffèrent. Le verdict de la campagne est
un <strong>rejet</strong>, et il se lit sur le composite agrégé, dans la
<a href="../traces/2026-08-25_ab_meteo/README.md">trace</a>.</div>

<h3>Parts modales globales, par bras</h3>
<div class="tw"><table class="dt">
<thead><tr><th>bras</th><th class="d">ce qu'il porte</th>
{"".join(f"<th>{html.escape(MODE_LABEL[m])}</th>" for m in MODES)}
<th class="n">masse</th><th>L1</th></tr></thead>
<tbody>{resume}{ligne_cible}</tbody></table></div>

{tables}

<p style="font-size:12px;color:var(--ink3);margin-top:18px">
Page <strong>générée</strong> par <code>scripts/synthesis/build_ab_detail.py</code> depuis
les décisions déjà présentes dans <code>prompt_calibration/calibration_results/ab_chaine.db</code>
— <strong>aucun appel LLM</strong>. Composites et verdicts :
<a href="../traces/2026-08-25_ab_meteo/README.md">trace de l'A/B</a>.
Généré le {datetime.now():%Y-%m-%d à %H:%M}.</p>
</section>
</main></div></body></html>
"""


EXTRA = """
.tw{overflow-x:auto;margin:10px 0 18px}
table.dt{border-collapse:collapse;font-size:12.5px;width:100%;min-width:640px}
table.dt th,table.dt td{padding:5px 9px;text-align:right;border-bottom:1px solid var(--line);
font-family:var(--mono);white-space:nowrap}
table.dt thead th{font-size:11px;color:var(--ink3);text-align:right;font-weight:400;
border-bottom:1px solid var(--line2)}
table.dt tbody th{text-align:left;font-weight:400;color:var(--ink2)}
table.dt td.d,table.dt th.d{text-align:left;font-family:inherit;color:var(--ink3);
font-size:11.5px;white-space:normal}
table.dt td.n,table.dt th.n{color:var(--ink3)}
table.dt td.ref{color:var(--ink3)}
table.dt td.noise,table.dt th.noise{color:var(--warn);opacity:.75}
table.dt td.ok{color:var(--ok)}
table.dt td.warn{color:var(--warn)}
table.dt td.muted{color:var(--ink3);opacity:.5}
table.dt td.na{color:var(--ink3);opacity:.4}
.nt{color:var(--warn);font-weight:600}
.lgd{display:flex;gap:14px;flex-wrap:wrap;margin:8px 0 4px;font-size:11.5px;
color:var(--ink3)}
.lgd .lg{display:flex;align-items:center;gap:5px}
.lgd .sw{width:16px;height:2.5px;border-radius:2px;display:inline-block}
.lgd .sw.ref{background:transparent;border-top:2px dashed var(--ink3)}
.lgd em{font-style:normal;opacity:.75}
table.dt tr.tgt th,table.dt tr.tgt td{border-top:1px solid var(--line2);color:var(--ink2)}
h3{font-size:14px;margin:22px 0 0;font-weight:500}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default="val", choices=("val", "screen"))
    parser.add_argument("--db", type=Path,
                        default=CALIB / "calibration_results" / "ab_chaine.db")
    parser.add_argument("--config", type=Path,
                        default=CALIB / "run_ab_chaine.yaml")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if not args.db.exists():
        print(f"[ERREUR] store introuvable : {args.db}", file=sys.stderr)
        return 1
    frames = load_frames(args.dataset, args.db, args.config)
    connus = [a for a, _ in ARMS if a in frames]
    if not connus:
        print(f"[ERREUR] aucun bras de l'A/B météo trouvé dans {args.db} pour "
              f"« {args.dataset} ».", file=sys.stderr)
        return 1

    targets_path = ROOT / "scripts" / "data" / "population" / "cerema_values.yaml"
    targets = (yaml.safe_load(targets_path.read_text(encoding="utf-8")) or {}) \
        .get("parts_modales_2023", {})

    out = args.out or OUT_DIR / f"ab_meteo_detail_{args.dataset}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(frames, args.dataset, targets), encoding="utf-8")
    print(f"  {len(connus)} bras — {', '.join(connus)}")
    print(f"  écrit → {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
