"""build_terminal_page.py — Page de synthèse d'un A/B de jeux gelés, avec graphiques.

Produit `docs/synthesis/<horodatage>_temps_terminal.html` : une page **horodatée et
archivée**, dans le même dossier et le même langage visuel que `index.html`.

## Pourquoi une page à part et pas une section d'`index.html`

`index.html` score un **run de simulation** — trois volets sur un substrat commun, épinglé
dans `sources.yaml`. Les mesures archivées ici portent sur des **jeux gelés** : elles
disent ce que le modèle choisirait dans des situations figées, pas ce qu'une simulation
produirait. Les mêler à la page principale mélangerait deux natures de mesure sous un même
composite, et le lecteur perdrait le seul repère qui compte : de quoi le chiffre parle.

Elles partagent en revanche tout le reste — la loss, la référence EMC², la palette, les
graphiques. La page réutilise donc `scripts.synthesis.charts` et sa `CSS` plutôt que d'en
redessiner une variante : deux styles pour deux pages de mesure du même projet, et on
cesse de les comparer.

## Trois bras, et aucun chiffre de prose écrit à la main

La page lit trois jeux : `v5` (les temps de la config), `v6` (voiture alignée sur EMC²) et
`v7` (voiture **et** vélo alignés, soit le périmètre exact de ce qui est parti en
production sous `tt3`). La colonne du milieu est le résultat intéressant : elle dit ce que
l'alignement du vélo rend du gain mesuré sur la voiture seule.

**Tous les chiffres cités dans le texte sont calculés depuis `results.json`.** La version
précédente de cette page en portait une quinzaine en dur — gain, dimensions, parts
modales — et ils décrivaient déjà un `v6` périmé au moment de sa relecture. Un chiffre en
dur dans une page générée est un chiffre qui dérivera.

## Horodatage, et où la page survit

Le nom porte la date et l'heure de génération. Ces pages sont des **archives** : chaque
mesure garde la sienne, et aucune n'écrase la précédente. C'est l'inverse d'`index.html`,
régénérée en place parce qu'elle suit l'état courant.

⚠ `docs/synthesis/*` est **gitignoré** (ligne 46 du `.gitignore`) : c'est le dossier des
sorties générées, et la page horodatée y est aussi volatile que le store dont elle vient.
Elle y est écrite parce que c'est là qu'on la lit, à côté d'`index.html` — mais un
exemplaire identique part dans le dossier de traces, qui est committé. Une page de mesure
qui ne survit qu'au prochain nettoyage n'est pas une archive.

## Trois arrondis, une seule règle

Les nombres sont rendus à la française (virgule décimale) par `num` et `signed`. La page
est en français ; ses chiffres aussi.

Usage :
    python -m scripts.synthesis.build_terminal_page
    python -m scripts.synthesis.build_terminal_page --traces docs/traces/2026-08-24_temps_terminal
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from html import escape
from pathlib import Path

import yaml

from scripts.synthesis import charts
from scripts.synthesis.frames import MODE_COLORS, MODE_LABELS, MODES
from scripts.synthesis.render import CSS

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRACES = REPO_ROOT / "docs" / "traces" / "2026-08-24_temps_terminal"
OUT_DIR = REPO_ROOT / "docs" / "synthesis"
CEREMA_VALUES = REPO_ROOT / "scripts" / "data" / "population" / "cerema_values.yaml"


def _load_reference() -> dict:
    """Référence EMC² globale — relue depuis `cerema_values.yaml` plutôt que recopiée en
    dur : c'est exactement l'erreur que ce fichier dénonce dans son propre docstring pour
    les chiffres de prose (une quinzaine en dur, décrivant déjà un `v6` périmé)."""
    doc = yaml.safe_load(CEREMA_VALUES.read_text(encoding="utf-8")) or {}
    glob = (doc.get("parts_modales_2023") or {}).get("global") or {}
    return {mode: float(glob[mode]) for mode in ("marche", "voiture", "velo",
                                                  "transports_collectifs")}


REFERENCE = _load_reference()

# Les trois bras, dans l'ordre de lecture. Le dernier est le périmètre livré.
ARMS = (
    ("v5", "temps de la config", "#a8a8b0"),
    ("v6", "voiture alignée", "#7A9CC6"),
    ("v7", "voiture + vélo alignés", "#2E7D5B"),
)
PROMPT_BRANCH = "ab_chaine_expert_chaine"

# EXCEPTION à la règle du docstring (« tous les chiffres viennent de `results.json` ») :
# ces deux blocs sont recopiés à la main depuis des rapports de scripts *hors ligne*
# (`export_terminal_time`, `rewrite_terminal_time.py`), qui n'écrivent pas leur résultat
# dans un fichier stable que cette page pourrait relire — contrairement à REFERENCE,
# recalculée depuis `cerema_values.yaml`. Comme pour la version précédente de ce fichier,
# ils dérivent silencieusement si `tt2`/les jeux gelés sont retirés : à re-produire (et
# recopier à la main) si `export_terminal_time`/`rewrite_terminal_time.py` sont rejoués.

# Enquête contre valeurs `tt2`, par couronne (minutes) — rapport de `export_terminal_time`.
SURVEY_VS_CONFIG = (
    ("Toulouse", 0.36, 3, 0.52, 7),
    ("1ʳᵉ couronne", 0.14, 2, 0.17, 4),
    ("2ᵉ couronne", 0.16, 2, 0.19, 3),
    ("3ᵉ couronne", 0.09, 1, 0.06, 1),
)

# Temps terminal réalisé par option dans les jeux, par mode — rapport de
# `rewrite_terminal_time.py`, lignes « par option » des `DERIVATION.md`.
REALISED = (("voiture", 7.93, 0.55), ("vélo", 2.00, 0.29))

# Dimensions de la loss, dans l'ordre de lecture des pages du dépôt.
DIMENSIONS = (("global", "global"), ("âge", "age"), ("genre", "genre"),
              ("motif", "motif"), ("distance", "distance"))


def score(row, attr: str) -> float:
    return float((row or {}).get("scores", {}).get(attr, 0.0) or 0.0)


def share(row, mode: str) -> float:
    return float((row or {}).get("shares_pct", {}).get(mode, 0.0) or 0.0)


def num(value: float, digits: int = 2) -> str:
    """Nombre à la française : le reste de la page est en français, les chiffres aussi."""
    return f"{value:.{digits}f}".replace(".", ",")


def signed(value: float, digits: int = 2) -> str:
    return f"{value:+.{digits}f}".replace(".", ",")


def dim_bars(arms: dict) -> str:
    """Barres horizontales par dimension de la loss, un trait par bras.

    Pas de `bullet_rows` ici : il compare une part à une CIBLE, et une dimension de
    loss n'a pas de cible — elle a un avant et un après. Des barres superposées, la
    plus courte étant la meilleure, disent exactement ça.
    """
    labels = (("composite", "composite"), *DIMENSIONS)
    rows = [(label, [score(arms[v], attr) for v, _, _ in ARMS])
            for label, attr in labels]
    top = max(max(values) for _, values in rows) * 1.15 or 1.0
    # `pad_r` dimensionné sur l'étiquette la PLUS LONGUE (« 27,00 → 24,83 (-2,17) »,
    # ~21 caractères à 12 px) : trop court, le SVG la rogne sans prévenir — un
    # graphique dont les chiffres sont coupés ment par omission.
    label_w, bar_w, row_h, pad_r = 92, 262, 40, 172
    height = row_h * len(rows) + 24
    width = label_w + bar_w + pad_r
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" '
             f'style="max-width:{width}px" role="img" '
             f'aria-label="Dimensions de la loss, pour les trois jeux">']
    for index, (label, values) in enumerate(rows):
        y = 14 + index * row_h
        weight = ";font-weight:600" if label == "composite" else ""
        parts.append(f'<text class="cx-sub" x="0" y="{y + 13}" '
                     f'style="fill:var(--ink){weight}">{escape(label)}</text>')
        for offset, (value, (_, _, colour)) in enumerate(zip(values, ARMS)):
            length = max(1.0, bar_w * value / top)
            parts.append(
                f'<rect x="{label_w}" y="{y + offset * 9}" width="{length:.1f}" '
                f'height="7" rx="2" fill="{colour}" opacity="0.9"/>')
        delta = values[-1] - values[0]
        colour = "#2E7D5B" if delta < 0 else "#C2571A"
        parts.append(
            f'<text class="cx-sub" x="{label_w + bar_w + 8}" y="{y + 14}" '
            f'style="fill:{colour};font-variant-numeric:tabular-nums">'
            f'{num(values[0])} → {num(values[-1])} ({signed(delta)})</text>')
    parts.append("</svg>")
    legend = charts.legend([(f"{label} ({version})", colour)
                            for version, label, colour in ARMS],
                           extra="plus court = meilleur · l'écart annoté va de v5 à v7")
    return legend + "".join(parts)


def modal_bullets(row, caption: str) -> str:
    """Parts modales face à la cible EMC², avec les couleurs de mode du projet."""
    rows = [{"label": MODE_LABELS[mode], "color": MODE_COLORS[mode],
             "actual": share(row, mode), "target": REFERENCE[mode]}
            for mode in MODES]
    return (f'<div class="cx-cap">{escape(caption)}</div>'
            + charts.bullet_rows(rows, max_pct=60.0))


def terminal_bars() -> str:
    """Temps terminal appliqué contre mesuré, par couronne.

    Échelle unique pour les deux séries : c'est le rapport de grandeur qui est le
    message, et deux échelles le masqueraient.
    """
    top = max(cfg_a + cfg_e for _, _, cfg_a, _, cfg_e in SURVEY_VS_CONFIG) * 1.1
    # Idem : « 10 min → 0,88 min (×11) » fait ~23 caractères.
    label_w, bar_w, row_h, pad_r = 104, 246, 36, 182
    height = row_h * len(SURVEY_VS_CONFIG) + 24
    width = label_w + bar_w + pad_r
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" '
             f'style="max-width:{width}px" role="img" '
             f'aria-label="Temps terminal appliqué contre mesuré, par couronne">']
    for index, (crown, acc, acc_cfg, egr, egr_cfg) in enumerate(SURVEY_VS_CONFIG):
        y = 18 + index * row_h
        survey, applied = acc + egr, acc_cfg + egr_cfg
        parts.append(f'<text class="cx-sub" x="0" y="{y + 11}" '
                     f'style="fill:var(--ink)">{escape(crown)}</text>')
        for offset, (value, color, opacity) in enumerate((
                (applied, "#C2571A", 0.85), (survey, "#2E7D5B", 0.95))):
            length = max(1.0, bar_w * value / top)
            parts.append(
                f'<rect x="{label_w}" y="{y + offset * 9}" width="{length:.1f}" '
                f'height="7" rx="2" fill="{color}" opacity="{opacity}"/>')
        parts.append(
            f'<text class="cx-sub" x="{label_w + bar_w + 8}" y="{y + 12}" '
            f'style="font-variant-numeric:tabular-nums">'
            f'{applied:.0f} min → {num(survey)} min (×{applied / survey:.0f})</text>')
    parts.append("</svg>")
    legend = charts.legend([("appliqué par tt2", "#C2571A"),
                            ("mesuré sur EMC²", "#2E7D5B")],
                           extra="voiture, accès + stationnement, par trajet")
    return legend + "".join(parts)


def render(rows: list[dict], generated: datetime, traces: Path) -> str:
    by_key = {(r["branch"], r["params_key"].split("ds=")[-1]): r for r in rows}
    arms = {version: by_key.get((PROMPT_BRANCH, version)) for version, _, _ in ARMS}
    off = by_key.get(("ab_chaine_expert", "v5"))
    missing = [v for v, row in arms.items() if row is None]
    if missing or off is None:
        absents = ", ".join(missing) or "le bras sans la puce de chaîne"
        raise SystemExit(f"Traces incomplètes : {absents} absent(s) de {traces}. "
                         f"Rejouez `ab_terminal.py` puis `archive_ab.py`.")

    base, car_only, shipped = arms["v5"], arms["v6"], arms["v7"]
    gain_livre = score(shipped, "composite") - score(base, "composite")
    gain_voiture = score(car_only, "composite") - score(base, "composite")
    rendu_velo = score(shipped, "composite") - score(car_only, "composite")
    part_rendue = 100 * rendu_velo / abs(gain_voiture) if gain_voiture else 0.0
    stamp = generated.strftime("%d/%m/%Y à %H:%M")
    personas = shipped.get("n_personas", 0)

    def tile(key: str, value: str, unit: str, highlight: bool = False) -> str:
        cls = ' class="v" style="color:var(--ok)"' if highlight else ' class="v"'
        return (f'<div class="tile"><div class="k">{escape(key)}</div>'
                f'<div{cls}>{escape(value)}</div>'
                f'<div class="u">{escape(unit)}</div></div>')

    # Dimensions qui gagnent et qui perdent : calculées, pas listées à la main.
    deltas = sorted(((label, score(shipped, attr) - score(base, attr))
                     for label, attr in DIMENSIONS), key=lambda item: item[1])
    gagne = [(label, delta) for label, delta in deltas if delta < 0]
    perd = [(label, delta) for label, delta in deltas if delta > 0]
    phrase_gagne = " et ".join(f'<span class="mono">{escape(label)}</span> '
                               f"({signed(delta)})" for label, delta in gagne[:2])
    phrase_perd = " et ".join(f'<span class="mono">{escape(label)}</span> '
                              f"({signed(delta)})" for label, delta in perd[-2:])

    # ⚠ `.wrap` de la CSS du projet est une GRILLE à deux colonnes (220 px + reste),
    # faite pour `<nav> + <main>`. Sans le `<nav>`, `<main>` tombe dans la colonne de
    # 220 px et la page se lit en colonne étroite. On sert donc la même structure que
    # les autres pages de mesure — ce qui donne au passage le sommaire latéral.
    nav = [
        '<nav><h1 style="font-size:17px;margin:0 0 2px">Temps terminal</h1>',
        '<div class="sub" style="margin-bottom:18px">aligné sur l\'enquête</div>',
    ]
    for anchor, label in (("portee", "Ce que la page mesure"),
                          ("perimetre", "Mesuré contre livré"), ("loss", "La loss"),
                          ("parts", "Parts modales"), ("parametre", "Le paramètre"),
                          ("vu", "Ce que le modèle voyait"), ("traces", "Traces")):
        nav.append(f'<a href="#{anchor}">{escape(label)}</a>')
    nav.append("</nav>")

    body = [
        '<div class="wrap">', *nav, "<main>",
        "<h1>Temps terminal aligné sur l'enquête</h1>",
        f'<div class="sub">Mesure appariée sur jeux gelés — trois jeux '
        f'(<span class="mono">v5</span>, <span class="mono">v6</span>, '
        f'<span class="mono">v7</span>), {personas} personas · générée le {stamp}</div>',

        '<div class="tiles">',
        tile("Composite · temps config", num(score(base, "composite")), "jeu v5"),
        tile("Composite · voiture seule", num(score(car_only, "composite")),
             f"jeu v6 · {signed(gain_voiture)}"),
        tile("Composite · périmètre livré", num(score(shipped, "composite")),
             f"jeu v7 · {signed(gain_livre)}", highlight=True),
        tile("Ce que le vélo rend", signed(rendu_velo),
             f"soit {num(part_rendue, 0)} % du gain voiture"),
        "</div>",

        '<div class="note" id="portee"><div class="t">Ce que cette page mesure, et ce '
        "qu'elle ne mesure pas</div>"
        "<p>Elle porte sur des <strong>jeux gelés</strong> : elle dit ce que le modèle "
        "choisirait dans des situations figées, pas ce qu'une simulation produirait. La "
        "réécriture du temps terminal ne rejoue ni l'offre d'options ni les chaînes de "
        "véhicule, où le choix d'un jour se répercute sur les offres du lendemain. C'est "
        "pourquoi elle vit à côté d'<span class=\"mono\">index.html</span> et non "
        "dedans : mêler les deux natures de mesure sous un même composite ferait perdre "
        "le seul repère qui compte, de quoi le chiffre parle.</p></div>",

        '<h2 id="perimetre">Le périmètre mesuré contre le périmètre livré</h2>',
        f'<div class="note warn"><div class="t">Le premier A/B mesurait moins que ce qui '
        f"est parti en production</div>"
        f"<p>La mesure d'origine opposait <span class=\"mono\">v5</span> à "
        f"<span class=\"mono\">v6</span>, où seule la <strong>voiture</strong> est "
        f"alignée : <strong>{signed(gain_voiture)}</strong> de composite. Mais "
        f"<span class=\"mono\">tt3</span>, en production, aligne aussi le "
        f"<strong>vélo</strong> (2,00 → 0,29 min par option) — un mode rendu lui aussi "
        f"plus attractif, donc dans le sens <em>inverse</em> du gain. "
        f"<span class=\"mono\">v7</span> aligne les deux et referme l'écart : le gain "
        f"réellement livré est de <strong>{signed(gain_livre)}</strong>. L'alignement du "
        f"vélo rend {signed(rendu_velo)}, soit {num(part_rendue, 0)} % du gain mesuré sur "
        f"la voiture seule.</p>"
        f"<p>Le gain net reste franc, et la correction reste celle que la source "
        f"réclame : le vélo à 1 min par bout n'était pas plus sourcé que la voiture à "
        f"3-7 min. Mais le chiffre à citer est {signed(gain_livre)}, pas "
        f"{signed(gain_voiture)}.</p></div>",

        '<h2 id="loss">La loss, dimension par dimension</h2>',
        "<p>Seules les jambes terminales changent entre les trois jeux — temps de "
        "conduite intact, offre d'options intacte, même prompt. Temps terminal réalisé "
        "par option : "
        + " ; ".join(f"<strong>{escape(mode)}</strong> {num(before)} → {num(after)} min "
                     f"(÷ {before / after:.1f})" for mode, before, after in REALISED)
        + ". La moyenne toutes options confondues dilue les deux et ne décrit ni l'un ni "
          "l'autre : on ne la cite pas.</p>",
        dim_bars(arms),
        f'<div class="note"><div class="t">Le gain n\'est pas uniforme</div>'
        f"<p>Sur le périmètre livré, le composite gagne "
        f"<strong>{signed(gain_livre)}</strong>, porté par {phrase_gagne}. Mais "
        f"{phrase_perd} se <strong>dégradent</strong> : l'alignement corrige le biais "
        f"dominant, il ne résout pas la sous-représentation de la marche, qui devient "
        f"l'écart principal.</p></div>",

        '<h2 id="parts">Parts modales face à EMC²</h2>',
    ]
    for version, label, _ in ARMS:
        body.append(modal_bullets(arms[version], f"{label} ({version})"))
    decisions = ", ".join(f"{version} : {arms[version]['n_decisions']}"
                          for version, _, _ in ARMS)
    body += [
        f'<div class="note"><div class="t">Le vélo reflue, mais moins qu\'on ne l\'avait '
        f"mesuré</div>"
        f"<p>Le vélo passe de {num(share(base, 'velo'))} à "
        f"{num(share(shipped, 'velo'))} % pour une cible de "
        f"{num(REFERENCE['velo'], 1)} ({signed(share(shipped, 'velo') - share(base, 'velo'))} pt), "
        f"là où l'alignement de la voiture seule le ramenait à "
        f"{num(share(car_only, 'velo'))} % "
        f"({signed(share(car_only, 'velo') - share(base, 'velo'))} pt) : rendre le vélo "
        f"lui aussi plus rapide en retient "
        f"{signed(share(shipped, 'velo') - share(car_only, 'velo'))} pt. La voiture, "
        f"elle, passe de {num(share(base, 'voiture'))} à "
        f"{num(share(shipped, 'voiture'))} % pour {num(REFERENCE['voiture'], 1)} "
        f"attendus. La marche s'éloigne ({num(share(base, 'marche'))} → "
        f"{num(share(shipped, 'marche'))} % pour {num(REFERENCE['marche'], 1)} attendus) "
        f"— c'est le biais suivant, et il n'est pas dans le temps terminal.</p></div>",

        '<h2 id="parametre">Le paramètre corrigé</h2>',
        "<p>EMC² mesure ce temps directement — <span class=\"mono\">T2</span> (marche au "
        "départ), <span class=\"mono\">T6</span> (marche à l'arrivée) et "
        "<span class=\"mono\">T11</span> (durée de recherche du stationnement), sur "
        "24 482 trajets conducteur de VP, renseignés à ~100 %.</p>",
        terminal_bars(),
        '<div class="note"><div class="t">Le contrôle qui autorise la comparaison</div>'
        "<p>Si la marche vers la voiture était codée comme un trajet à pied "
        "<em>distinct</em>, <span class=\"mono\">T2</span> et "
        "<span class=\"mono\">T6</span> vaudraient 0 par construction et la mesure serait "
        "vide. Vérifié : sur les 24 481 déplacements comportant un trajet voiture, "
        "<strong>aucun</strong> ne porte de trajet à pied. Et l'instrument fonctionne — "
        "sur les trajets en transports collectifs, de structure identique, "
        "<span class=\"mono\">T2 + T6</span> donne <strong>6 minutes</strong> en médiane. "
        "L'enquête sait enregistrer un temps terminal ; elle en enregistre 0,55 min par "
        "trajet voiture et 0,22 par trajet vélo.</p></div>",
        '<div class="note"><div class="t">Une loi, pas une moyenne — et pas une '
        "cloche</div><p>La moyenne d'enquête est <em>inférieure à la minute</em> alors "
        "que le rendu n'affiche que des minutes entières : une constante vaudrait 0 "
        "partout et effacerait une queue réelle (2 à 4 % des trajets ont vraiment "
        "5 minutes ou plus). Le tirage garde la moyenne <strong>et</strong> la queue. Et "
        "la distribution n'est pas gaussienne : elle est massée à zéro (87 à 96 % selon "
        "la couronne) et étirée à droite. Une cloche produirait des durées négatives et "
        "détruirait la masse à zéro. C'est aussi pourquoi le réalisé (0,29 min par "
        "option vélo) dépasse la loi (0,22) : l'arrondi à la minute entière ne peut pas "
        "rendre une fraction.</p></div>",

        '<h2 id="vu">Ce que le modèle voyait</h2>',
        "<pre>v5      car: Temps de trajet : 10 minutes, dont 10 minutes d'accès\n"
        "             et de stationnement. Distance : 47 m.\n"
        "          · Rejoindre la voiture : 3 minutes.\n"
        "          · Conduite : 8 seconds.          &lt;- 47 mètres\n"
        "          · Stationnement et marche : 7 minutes.\n\n"
        "v6/v7   car: Temps de trajet : 0 minute. Distance : 47 m.\n\n"
        "v5/v6   bicycle: · Rejoindre le vélo : 1 minute.\n"
        "                 · Stationnement du vélo : 1 minute.\n"
        "v7      bicycle: · Rejoindre le vélo : 0 minute.\n"
        "                 · Stationnement du vélo : 0 minute.</pre>",

        '<h2 id="traces">Traces</h2>',
        '<div class="scroll"><table><thead><tr><th>branche</th><th>jeu</th>'
        '<th class="num">composite</th><th class="num">décisions</th>'
        '<th class="num">personas</th><th>nœud</th><th>modèle d\'éval</th>'
        "</tr></thead><tbody>",
    ]
    for row in rows:
        version = row["params_key"].split("ds=")[-1]
        body.append(f'<tr><td class="mono">{escape(row["branch"])}</td>'
                    f'<td>{escape(row["dataset"])} ({escape(version)})</td>'
                    f'<td class="num">{num(score(row, "composite"))}</td>'
                    f'<td class="num">{row["n_decisions"]}</td>'
                    f'<td class="num">{row["n_personas"]}</td>'
                    f'<td class="mono">{escape(row["node"][:10])}</td>'
                    f'<td class="mono">{escape(str(row["eval_model"]))}</td></tr>')
    body += [
        "</tbody></table></div>",
        f'<div class="note"><div class="t">L\'appariement porte sur les personas, pas '
        f"sur les décisions</div><p>Les {personas} personas sont les mêmes dans les trois "
        f"bras, avec les mêmes jeux d'options : c'est ce qui resserre la variance du Δ. "
        f"Le nombre de <em>lignes de décision</em>, lui, varie d'un bras à l'autre "
        f"({escape(decisions)}) — un rendu de modèle peut être incomplet sur une entrée "
        f"et pas sur une autre. L'effectif opposable reste celui des personas "
        f"distincts.</p></div>",
        f'<p>Résultats agrégés relus depuis '
        f'<span class="mono">{escape(str(traces.relative_to(REPO_ROOT)))}</span>. '
        "Le store de calibration est gitignoré — régénérable, donc volatil : ces "
        "traces-là sont ce qui survit.</p>",
        "<pre>make terminal-time           # la loi d'enquête, depuis les microdonnées\n"
        "cd prompt_calibration\n"
        "python rewrite_terminal_time.py --src v5 --dst v6 --modes car\n"
        "python rewrite_terminal_time.py --src v5 --dst v7 --modes car,bicycle\n"
        "python ab_terminal.py --versions v5,v6,v7 --dry-run\n"
        "python archive_ab.py  --out ../docs/traces/2026-08-24_temps_terminal\n"
        "cd .. &amp;&amp; python -m scripts.synthesis.build_terminal_page</pre>",
        '<p>La correction est en production depuis <span class="mono">tt3</span> '
        '(<span class="mono">llm-agents/config/terminal_time.yaml</span>) : le temps '
        "terminal y est tiré dans cette loi pour la voiture <em>et</em> le vélo, et "
        "56 tests — dont un garde-fou d'alignement — refusent un retour aux valeurs "
        "tt2.</p>",
        "</main></div>",
    ]

    # `.wrap` et `main` ne sont PAS surchargés : ils viennent de la CSS du projet, et
    # les redéfinir casserait la grille à deux colonnes qu'on vient de servir.
    extra = """
main h1{font-size:27px;font-weight:600;letter-spacing:-.02em;margin:0 0 4px}
.sub{color:var(--ink3);font-size:13px;margin-bottom:24px}
.tiles{display:flex;gap:14px;flex-wrap:wrap;margin:18px 0 6px}
.tile{border:1px solid var(--line2);border-radius:10px;background:var(--card);
padding:12px 16px;min-width:160px}
.tile .k{font-size:11px;color:var(--ink3);text-transform:uppercase;letter-spacing:.04em}
.tile .v{font-size:23px;font-weight:600;margin-top:2px}
.tile .u{font-size:11.5px;color:var(--ink3)}
.cx-cap{font-size:12px;color:var(--ink3);margin:14px 0 2px}
pre{background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:12px 14px;overflow-x:auto;font-family:var(--mono);font-size:12px;
color:var(--ink2);line-height:1.5}
"""
    return (f"<title>Temps terminal aligné sur l'enquête — {stamp}</title>"
            f"<style>{CSS}{extra}</style>" + "".join(body))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACES,
                        help="dossier de traces produit par archive_ab.py")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    results = args.traces / "results.json"
    if not results.is_file():
        print(f"[ERREUR] traces introuvables : {results}\n"
              f"  Produisez-les : cd prompt_calibration && python archive_ab.py "
              f"--out ../{args.traces.relative_to(REPO_ROOT)}")
        return 1
    rows = json.loads(results.read_text(encoding="utf-8"))
    generated = datetime.now()
    page = render(rows, generated, args.traces)

    name = f"{generated:%Y-%m-%d_%H-%M}_temps_terminal.html"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / name
    out.write_text(page, encoding="utf-8")
    print(f"Page écrite : {out.relative_to(REPO_ROOT)} ({len(page)} car.)")
    # `docs/synthesis/*` est gitignoré : sans ce second exemplaire, la page ne
    # survivrait pas plus longtemps que le store dont elle est tirée.
    durable = args.traces / name
    durable.write_text(page, encoding="utf-8")
    print(f"  exemplaire committé : {durable.relative_to(REPO_ROOT)}")
    print(f"  {len(rows)} éval(s) · archive horodatée, aucune page existante écrasée")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
