#!/usr/bin/env python3
"""Figure — rupture et retour de la voiture décidée, autour d'un choc injecté (ticket 106).

CE QUE LA FIGURE TRACE : par jour relatif au choc, les décisions où la voiture était offerte
ET où c'est le modèle qui a tranché, réparties entre « voiture choisie » et « autre mode ».

POURQUOI « DÉCIDÉE » ET NON LA PART BRUTE
------------------------------------------
La part brute compte comme des décisions ce que la chaîne de véhicule impose. Sur le run du
2026-09-23, `sortie_bloquee` passe de 8 trajets avant le choc à 39 après : parti sans la
voiture le matin, l'agent ne peut plus la reprendre de la journée, et cette propagation se lit
alors comme un renoncement répété. Une décision n'entre ici que si la voiture était DANS les
modes proposés ET si `Méthode de sélection == LLM` — les trajets à itinéraire unique en
sortent, y compris ceux où la voiture était le seul choix. Sur ce run, la part voiture passe
de 72,2 % à 23,2 % en brut, et de 97,2 % à 33,3 % en décidé : les deux chiffres ne racontent
pas la même histoire, et seul le second parle de choix.

CE QUE LA FIGURE NE TRACE PAS, ET POURQUOI — mesuré le 2026-09-24, à garder
----------------------------------------------------------------------------
Une seconde courbe était prévue : « le souvenir est-il encore cité dans le raisonnement ? »,
pour séparer deux explications d'un retour à la voiture — le souvenir s'est effacé, ou il est
là et ne gouverne plus. Elle a été RETIRÉE faute d'instrument fiable. Trois lexiques essayés
sur le run `2026-09-23_20_35`, tous avec la machinerie du témoin (mots distinctifs, liste
d'exclusion calibrée, seuil de deux mots) :

  * les mots du TEXTE INJECTÉ (23 mots) → quasi aucun raisonnement marqué, avant comme après.
    Le raisonnement paraphrase : il dit « car breakdown » là où le texte dit « the engine
    stalled on the expressway ». Aucun mot distinctif ne survit à la paraphrase.
  * les mots des 31 entrées de MÉMOIRE LONGUE portant le choc (407 mots) → 56 raisonnements
    marqués sur 77 AVANT le choc. Le vocabulaire d'une réflexion est celui d'une journée
    ordinaire ; il marque tout.
  * les étiquettes du CONCEPT engendré par l'agent (« engine stall, expressway, breakdown,
    roadside assistance ») → 6/77 avant, 38/101 après. La séparation existe mais reste sale
    des deux côtés : `short`, `distance`, `speed`, `shop` marquent des journées ordinaires, et
    un raisonnement qui dit seulement « car breakdown » passe sous le seuil de deux mots.

CE QUE CELA APPREND SUR LE TÉMOIN : sa liste d'exclusion est calibrée sur des RÉFLEXIONS DE
CONSOLIDATION, et elle ne transfère pas à un raisonnement de décision. Le témoin reste valide
là où il est branché — il compare une consolidation au texte qui vient de l'alimenter, deux
textes du même registre. L'étendre au raisonnement demanderait sa propre calibration, et ce
n'est pas ce ticket. La persistance du souvenir dans les décisions se lit pour l'instant sur
les verbatims, consignés dans `docs/paper/article-court/experiments_results.md`.

GARDE DE VACUITÉ, NON NÉGOCIABLE
---------------------------------
Aucune moyenne n'est tracée : chaque jour relatif est une COLONNE dont la hauteur est le
nombre de décisions qui la portent. Un jour à une décision ne peut pas ressembler à un jour à
huit. Dans ce dépôt, l'absence de mesure produit volontiers la valeur parfaite, et ce motif a
déjà menti. Le script refuse de composer sous `DECISIONS_MINIMALES` au total.

Bibliothèque standard uniquement, SVG en ligne, sur le modèle de `figure_fenetre_choc.py`.
Figure composée en ANGLAIS : toutes les figures de l'article le sont.

    python scripts/analysis/figure_rupture_retour.py <run> -o <sortie.svg>
    python scripts/analysis/figure_rupture_retour.py <traité> --temoin <témoin> \
        --mode public_transport -o <sortie.svg>

`--mode` désigne le mode SUIVI, celui que l'événement est censé faire fuir : `car` pour une
panne de voiture, `public_transport` pour une panne de réseau. Le mode n'est jamais deviné —
trois vocabulaires de modes coexistent dans ce dépôt (ticket 077, lot A), et un mot qui
passerait « par défaut » tracerait la courbe d'un autre mode sans que rien ne le dise.

`--temoin` empile le bras témoin sous le bras traité, sur la même abscisse. C'est la seule
lecture qui permette de conclure : la campagne c3 du 2026-09-24 montre les deux bras séparés
d'au plus six points, c'est-à-dire aucun effet — et une figure du seul bras traité aurait
montré une courbe qui monte et qui descend, qu'on aurait pu lire comme un effet.

Le CSV des points tracés est écrit à côté du SVG, même nom, extension `.csv`.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "services" / "llm-agents"))

from llm.evenements import temoin  # noqa: E402  (après l'ajout au chemin)

# Palette catégorielle validée (dataviz, slots 1-2). Ne pas remplacer sans revalider :
#   node scripts/validate_palette.js "#2a78d6,#eb6834,#1baf7a" --mode light
SUIVI, AUTRE = "#eb6834", "#2a78d6"

# Mode canonique → libellé de `moves.csv`, et son nom anglais pour la figure. EXPLICITE et non
# deviné, sur le modèle de `figure_evenement.py`.
MODES = {
    "walking": ("Marche", "walking"),
    "cycling": ("Vélo", "cycling"),
    "car": ("Voiture", "the car"),
    "public_transport": ("Transports_collectifs", "public transport"),
    "train": ("Train", "the train"),
    "motorbike": ("Deux-roues motorisé", "the motorbike"),
}

# Sous ce total, on ne compose pas : une figure de rupture tracée sur quelques décisions
# ressemble exactement à une figure de rupture tracée sur deux cents.
DECISIONS_MINIMALES = 20

L, R, T, B = 66, 26, 96, 86
W = 1180
CORPS = 210   # hauteur du corps d'une bande (un bras)
ECART = 52    # espace entre deux bandes


def texte_injecte(run: Path) -> str:
    """Rend l'identifiant de l'événement injecté, pour le nommer sur la figure.

    Plusieurs injections sont possibles ; on nomme la première et on signale les autres —
    l'abscisse `Jour relatif au choc` de `moves.csv` n'en porte de toute façon qu'une.
    """
    chemin = run / "evenements.jsonl"
    if not chemin.is_file():
        raise SystemExit(f"❌ {chemin} introuvable — ce run ne porte aucune injection")
    lignes = [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lignes:
        raise SystemExit(f"❌ {chemin} est vide — ce run ne porte aucune injection")
    if len(lignes) > 1:
        print(f"  ⚠ {len(lignes)} injections dans ce run ; la figure ne nomme que la première.")
    d = lignes[0]
    texte = d.get("texte") or d.get("vecu") or ""
    mots = temoin.mots_distinctifs(texte)
    print(f"  {len(mots)} mot(s) distinctif(s) dans le texte injecté : {', '.join(mots[:8])}…")
    return d.get("choc_id") or d.get("evenement_id") or "?"


def lire(run: Path, libelle_mode: str) -> tuple[dict[int, list[int]], dict[int, int]]:
    """Rend `({jour: [mode suivi, autre mode]}, {jour: décisions du jour, libres ou non})`."""
    chemin = run / "moves.csv"
    if not chemin.is_file():
        raise SystemExit(f"❌ {chemin} introuvable — ce run n'a pas de journal de décisions")

    choix: dict[int, list[int]] = {}
    tous: dict[int, int] = {}
    with chemin.open(encoding="utf-8") as f:
        lecteur = csv.DictReader(f)
        for colonne in ("Jour relatif au choc", "Modes proposés au LLM",
                        "Méthode de sélection", "Mode de transport Choisi"):
            if colonne not in (lecteur.fieldnames or []):
                raise SystemExit(f"❌ colonne « {colonne} » absente de {chemin} — "
                                 f"ce moves.csv ne vient pas d'un run à événement")
        for ligne in lecteur:
            brut = (ligne["Jour relatif au choc"] or "").strip()
            if not brut:
                continue
            j = int(brut)
            tous[j] = tous.get(j, 0) + 1
            if libelle_mode not in ligne["Modes proposés au LLM"]:
                continue
            if ligne["Méthode de sélection"] != "LLM":
                continue
            c = choix.setdefault(j, [0, 0])
            c[0 if libelle_mode in ligne["Mode de transport Choisi"] else 1] += 1
    return choix, tous


def jours_relatifs(run: Path) -> dict[int, str]:
    """`{jour relatif: date simulée}` — sert à reporter l'abscisse du bras traité sur le témoin.

    Le bras témoin ne reçoit aucun événement : son `Jour relatif au choc` est vide, et c'est
    normal. Les deux bras partagent les graines et le même calendrier, donc la date simulée
    suffit à les aligner. Aligner sur autre chose — l'index de la ligne, l'ordre d'arrivée —
    ferait glisser les deux courbes l'une par rapport à l'autre sans que rien ne le dise.
    """
    table: dict[int, str] = {}
    with (run / "moves.csv").open(encoding="utf-8") as f:
        for ligne in csv.DictReader(f):
            brut = (ligne["Jour relatif au choc"] or "").strip()
            if not brut:
                continue
            jour = datetime.datetime.fromtimestamp(
                int(float(ligne["Temps simulé"])), datetime.UTC
            ).strftime("%Y-%m-%d")
            table[int(brut)] = jour
    return table


def lire_temoin(run: Path, libelle_mode: str,
                calendrier: dict[int, str]) -> tuple[dict[int, list[int]], dict[int, int]]:
    """Le bras témoin, réindexé sur les jours relatifs du bras traité."""
    par_date = {date: rel for rel, date in calendrier.items()}
    choix: dict[int, list[int]] = {}
    tous: dict[int, int] = {}
    chemin = run / "moves.csv"
    if not chemin.is_file():
        raise SystemExit(f"❌ {chemin} introuvable — le bras témoin n'a pas de journal")
    with chemin.open(encoding="utf-8") as f:
        for ligne in csv.DictReader(f):
            date = datetime.datetime.fromtimestamp(
                int(float(ligne["Temps simulé"])), datetime.UTC
            ).strftime("%Y-%m-%d")
            j = par_date.get(date)
            if j is None:
                continue
            tous[j] = tous.get(j, 0) + 1
            if libelle_mode not in ligne["Modes proposés au LLM"]:
                continue
            if ligne["Méthode de sélection"] != "LLM":
                continue
            c = choix.setdefault(j, [0, 0])
            c[0 if libelle_mode in ligne["Mode de transport Choisi"] else 1] += 1
    return choix, tous


def _x(j: int, jmin: int, jmax: int) -> float:
    return L + (j - jmin) / max(jmax - jmin, 1) * (W - L - R)


def _bande(a, choix: dict, jours: list[int], jmin: int, jmax: int, hmax: int,
           haut: float, corps: float, larg: float, titre: str) -> None:
    """Un bras : une colonne par jour relatif, haute de son nombre de décisions."""
    a(f'<text class="ink2" x="{L}" y="{haut - 10:.1f}" font-size="11.5">{titre}</text>')
    for n in range(0, hmax + 1, max(1, hmax // 3)):
        y = haut + corps - n / hmax * corps
        a(f'<line class="grid" x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" stroke-width="1"/>')
        a(f'<text class="ink2" x="{L - 10}" y="{y + 4:.1f}" font-size="11" '
          f'text-anchor="end">{n}</text>')
    x0 = _x(0, jmin, jmax)
    a(f'<line x1="{x0:.1f}" y1="{haut - 6:.1f}" x2="{x0:.1f}" y2="{haut + corps:.1f}" '
      f'stroke="#5c5b54" stroke-width="1.5" stroke-dasharray="4 4" opacity="0.75"/>')
    for j in jours:
        suivi, autre = choix.get(j, [0, 0])
        x = _x(j, jmin, jmax) - larg / 2
        y = haut + corps
        for n, couleur in ((autre, AUTRE), (suivi, SUIVI)):
            if not n:
                continue
            h = n / hmax * corps
            y -= h
            a(f'<rect x="{x:.1f}" y="{y:.1f}" width="{larg:.1f}" height="{h:.1f}" '
              f'fill="{couleur}"/>')
    a(f'<line class="rule" x1="{L}" y1="{haut + corps:.1f}" x2="{W - R}" '
      f'y2="{haut + corps:.1f}" stroke-width="1"/>')


def composer(bras: list[tuple[str, dict, dict]], evenement: str, mode_en: str,
             run: str, titre: str, lecture: str) -> str:
    jours = sorted({j for _, choix, tous in bras for j in set(choix) | set(tous)})
    jmin, jmax = jours[0], jours[-1]
    hmax = max(sum(v) for _, choix, _ in bras for v in choix.values())
    pas = (W - L - R) / max(jmax - jmin, 1)
    larg = max(4.0, min(pas * 0.7, 16.0))

    hauteur = T + len(bras) * (CORPS + ECART) - ECART + B
    o: list[str] = []
    a = o.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {hauteur}" width="{W}" '
      f'height="{hauteur}" font-family="Inter, Helvetica, Arial, sans-serif" role="img" '
      f'aria-label="Decisions about {mode_en} by day relative to the injected shock">')
    a("<style>"
      ".surface{fill:#fcfcfb}.ink{fill:#1a1a19}.ink2{fill:#5c5b54}.grid{stroke:#e6e5e0}"
      ".rule{stroke:#c9c8c1}"
      "@media (prefers-color-scheme: dark){"
      ".surface{fill:#1a1a19}.ink{fill:#ffffff}.ink2{fill:#c3c2b7}"
      ".grid{stroke:#333330}.rule{stroke:#4a4944}}"
      "</style>")
    a(f'<rect class="surface" width="{W}" height="{hauteur}"/>')
    a(f'<text class="ink" x="{L}" y="27" font-size="17" font-weight="600">{titre}</text>')
    a(f'<text class="ink2" x="{L}" y="47" font-size="12.5">'
      f'Only decisions where {mode_en} was on offer and the model chose: trips with a single '
      f'available itinerary are excluded. Every bar is a count,</text>')
    a(f'<text class="ink2" x="{L}" y="64" font-size="12.5">'
      f'never an average — a day carrying one decision cannot look like a day carrying eight. '
      f'<tspan fill="{SUIVI}" font-weight="600">— {mode_en} chosen</tspan> '
      f'<tspan fill="{AUTRE}" font-weight="600">— another mode</tspan></text>')

    for i, (nom, choix, _tous) in enumerate(bras):
        _bande(a, choix, jours, jmin, jmax, hmax,
               T + i * (CORPS + ECART), CORPS, larg, nom)

    bas = T + (len(bras) - 1) * (CORPS + ECART) + CORPS
    for j in jours:
        if j % 5 == 0 or j == 0:
            a(f'<text class="ink2" x="{_x(j, jmin, jmax):.1f}" y="{bas + 18:.1f}" '
              f'font-size="11" text-anchor="middle">{j:+d}</text>')
    a(f'<text class="ink2" x="{(L + W - R) / 2:.0f}" y="{bas + 38:.1f}" font-size="11.5" '
      f'text-anchor="middle">simulated days relative to the injected shock ({evenement}) · '
      f'weekends are not simulated</text>')
    a(f'<text class="ink2" x="{L}" y="{hauteur - 22:.1f}" font-size="11.5">{lecture}</text>')
    a(f'<text class="ink2" x="{L}" y="{hauteur - 8:.1f}" font-size="10.5">source: {run}</text>')
    a("</svg>")
    return "\n".join(o)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path, help="répertoire du bras TRAITÉ (contenant moves.csv)")
    p.add_argument("--temoin", type=Path, default=None,
                   help="répertoire du bras témoin, empilé sous le bras traité")
    p.add_argument("--mode", default="car", choices=sorted(MODES),
                   help="mode SUIVI, celui que l'événement est censé faire fuir (défaut : car)")
    p.add_argument("--titre", default=None, help="titre de la figure (anglais)")
    p.add_argument("--lecture", default="", help="phrase de lecture, sous la figure (anglais)")
    p.add_argument("-o", "--sortie", type=Path, required=True)
    args = p.parse_args()

    libelle, mode_en = MODES[args.mode]
    evenement = texte_injecte(args.run)
    choix, tous = lire(args.run, libelle)
    total = sum(sum(v) for v in choix.values())
    print(f"  traité : {total} décision(s) où {libelle} était offert, sur "
          f"{sum(tous.values())} décision(s), {len(choix)} jour(s) portés")
    if total < DECISIONS_MINIMALES:
        raise SystemExit(f"❌ non concluant : {total} décision(s) libre(s) pour un minimum de "
                         f"{DECISIONS_MINIMALES}. Ce n'est PAS un résultat nul — c'est une "
                         f"absence de mesure, et une figure creuse se lirait comme une absence "
                         f"d'effet.")

    bras = [("treated arm", choix, tous)]
    if args.temoin is not None:
        t_choix, t_tous = lire_temoin(args.temoin, libelle, jours_relatifs(args.run))
        t_total = sum(sum(v) for v in t_choix.values())
        print(f"  témoin : {t_total} décision(s) où {libelle} était offert, sur "
              f"{sum(t_tous.values())} décision(s), {len(t_choix)} jour(s) portés")
        if t_total < DECISIONS_MINIMALES:
            raise SystemExit(f"❌ non concluant : le bras témoin ne porte que {t_total} "
                             f"décision(s) libre(s). Un témoin trop mince ne permet aucune "
                             f"comparaison, et l'empiler donnerait l'illusion du contraire.")
        bras.append(("control arm (no shock)", t_choix, t_tous))

    titre = args.titre or f"Decisions about {mode_en} around the injected shock"
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    args.sortie.write_text(
        composer(bras, evenement, mode_en, str(args.run), titre, args.lecture),
        encoding="utf-8")
    print(f"→ {args.sortie}")

    csv_sortie = args.sortie.with_suffix(".csv")
    with csv_sortie.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["bras", "jour_relatif", "mode_suivi_choisi", "autre_mode_choisi",
                    "decisions_libres", "decisions_du_jour"])
        for nom, ch, to in bras:
            for j in sorted(set(ch) | set(to)):
                suivi, autre = ch.get(j, [0, 0])
                w.writerow([nom, j, suivi, autre, suivi + autre, to.get(j, 0)])
    print(f"→ {csv_sortie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
