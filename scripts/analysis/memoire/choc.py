"""Courbe d'un choc : ce que l'agent décide, et ce que sa mémoire lui servait ce jour-là.

Cas d'étude du 2026-09-15. Deux runs APPARIÉS — mêmes graines, même population, une seule
différence, le choc — et la question posée à leur écart : *le changement d'habitude suit-il le
souvenir du choc, ou le précède-t-il ?*

**La variable de sortie est la PROBABILITÉ, pas le mode tiré.** Sur un agent, le tirage est
binaire et bruité : une bascule peut n'être qu'un coup de dé. La masse de probabilité que le
modèle accorde au mode touché est continue, et c'est elle que la mémoire déplace.

**Le test de réfutation est dans la même figure.** Chaque jour porte l'information « le souvenir
du choc a-t-il été servi à cette décision ». Si la courbe décroche les jours où il ne l'est pas,
la corrélation est fortuite et il faut le dire.

Usage :
    python -m scripts.analysis.memoire.choc <run_avec_choc> <run_sans_choc> -o <sortie.html>
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from html import escape
from pathlib import Path

# Palette officielle du dépôt (cf. .claude/CLAUDE.md).
COULEUR_CHOC = "#EE4444"
COULEUR_TEMOIN = "#7A7A85"
COULEUR_SERVI = "#1A4C8B"
COULEUR_GRILLE = "#E2E2E6"


# ── Lecture ──────────────────────────────────────────────────────────────────────


def _lire_moves(run: Path) -> list[dict]:
    chemin = run / "moves.csv"
    if not chemin.is_file():
        raise SystemExit(f"{chemin} est absent : ce n'est pas un répertoire de run.")
    with chemin.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _dedupliquer(rows: list[dict]) -> list[dict]:
    """Écarte les trajets REJOUÉS après un redémarrage.

    Même règle que le rapport par persona : la clé est (personne, activité, temps simulé) et la
    première ligne par heure de calcul est gardée. Sans cela, les jours rejoués comptent deux
    fois et la courbe porte une marche qui n'a pas eu lieu.
    """
    vus: set = set()
    propres: list[dict] = []
    for r in sorted(rows, key=lambda r: r.get("Heure de calcul", "")):
        clef = (r["ID Personne"], r.get("ID Activité", ""), r.get("Temps simulé", ""))
        if clef in vus:
            continue
        vus.add(clef)
        propres.append(r)
    return propres


def _lire_chocs(run: Path) -> list[dict]:
    chemin = run / "chocs.jsonl"
    if not chemin.is_file():
        return []
    return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]


def _lire_rappels(run: Path) -> list[dict]:
    chemin = run / "trace_rappel.jsonl"
    if not chemin.is_file():
        return []
    return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]


# ── Mesures ──────────────────────────────────────────────────────────────────────

# Colonne de probabilité par mode canonique, telle que `move_logger` l'écrit.
_COLONNE_PROBA = {
    "car": "P(Voiture Privée) %",
    "walking": "P(Marche) %",
    "cycling": "P(Vélo) %",
    "public_transport": "P(Transports_collectifs) %",
    "train": "P(Train) %",
    "motorbike": "P(Deux-roues motorisé) %",
}


def _proba_par_jour(rows: list[dict], agent: str, mode: str) -> dict[str, list[float]]:
    """Probabilités accordées au mode, par jour de départ.

    Les décisions à itinéraire unique sont EXCLUES : aucune probabilité n'y est calculée, et
    les compter à zéro ferait chuter la courbe pour une raison qui n'est pas la mémoire.
    """
    colonne = _COLONNE_PROBA[mode]
    par_jour: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if r["ID Personne"] != agent:
            continue
        if r.get("Méthode de sélection") != "LLM":
            continue
        valeur = (r.get(colonne) or "").strip()
        if not valeur:
            continue
        par_jour[r["Heure de départ"][:10]].append(float(valeur))
    return dict(par_jour)


def _part_choisie_par_jour(rows: list[dict], agent: str, libelle_mode: str) -> dict[str, float]:
    """Part des trajets du jour réellement faits dans ce mode — le tirage, pour mémoire."""
    par_jour: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        if r["ID Personne"] != agent:
            continue
        par_jour[r["Heure de départ"][:10]].append(
            1 if r["Mode de transport Choisi"] == libelle_mode else 0
        )
    return {j: sum(v) / len(v) for j, v in par_jour.items() if v}


def _docs_du_choc(chocs: list[dict], agent: str) -> set[str]:
    """Rien dans `chocs.jsonl` ne porte l'identifiant du souvenir écrit.

    On repère donc le souvenir du choc par son TEXTE : le `vecu` est écrit tel quel en mémoire
    courte, puis consommé par la réflexion. Faute de lien direct, la fonction rend les textes,
    et l'appariement se fait sur le contenu servi.
    """
    return {c["vecu"] for c in chocs if str(c["person_id"]) == agent}


def _jours_ou_le_choc_est_servi(
    rappels: list[dict], agent: str, chocs: list[dict], run: Path
) -> set[str]:
    """Jours où un souvenir portant le vécu du choc figurait dans le top-K servi.

    La trace des rappels ne porte que des identifiants de documents. Le rapprochement passe par
    les métadonnées de la mémoire longue, seules à porter à la fois l'identifiant et le texte.
    """
    textes = _docs_du_choc(chocs, agent)
    if not textes:
        return set()
    docs: set[str] = set()
    for fichier in sorted((run / "long_term_memory" / "user_metadata").glob("shard_*/*.json")):
        donnees = json.loads(fichier.read_text(encoding="utf-8"))
        if str(donnees.get("person_id")) != agent:
            continue
        for entree in donnees.get("entries", []):
            contenu = entree.get("content") or ""
            if any(t[:60] in contenu for t in textes) and entree.get("doc_id"):
                docs.add(entree["doc_id"])
    if not docs:
        return set()
    jours: set[str] = set()
    for ligne in rappels:
        if str(ligne.get("person_id")) != agent:
            continue
        if ligne.get("sim_day") and any(
            (s.get("doc_id") in docs) for s in ligne.get("servis", [])
        ):
            jours.add(ligne["sim_day"])
    return jours


# ── Figure ───────────────────────────────────────────────────────────────────────


def courbe(
    jours: list[str],
    avec: dict[str, list[float]],
    sans: dict[str, list[float]],
    servis: set[str],
    jours_de_choc: set[str],
) -> str:
    """Deux traits, un marqueur par jour où le souvenir du choc a été servi."""
    if not jours:
        return "<p>Aucune décision à tracer.</p>"
    largeur, hauteur = 860, 300
    marge_g, marge_h, marge_b = 52, 20, 58
    plot_l = largeur - marge_g - 20
    plot_h = hauteur - marge_h - marge_b
    pas = plot_l / max(1, len(jours) - 1)

    def y(valeur: float) -> float:
        return marge_h + plot_h * (1 - valeur / 100.0)

    parties = [
        (
            f'<svg viewBox="0 0 {largeur} {hauteur}" width="100%" '
            f'style="max-width:{largeur}px" role="img">'
        )
    ]
    for frac in (0, 25, 50, 75, 100):
        gy = y(frac)
        parties.append(
            f'<line x1="{marge_g}" y1="{gy:.1f}" x2="{marge_g + plot_l}" y2="{gy:.1f}" '
            f'stroke="{COULEUR_GRILLE}"/>'
        )
        parties.append(
            f'<text x="{marge_g - 8}" y="{gy + 4:.1f}" text-anchor="end" '
            f'font-size="11" fill="#6A6A72">{frac}%</text>'
        )
    # Bande des jours de choc, dessinée SOUS les courbes.
    for i, jour in enumerate(jours):
        if jour in jours_de_choc:
            parties.append(
                f'<rect x="{marge_g + i * pas - pas / 2:.1f}" y="{marge_h}" '
                f'width="{pas:.1f}" height="{plot_h}" fill="{COULEUR_CHOC}" opacity="0.10"/>'
            )

    for serie, couleur, nom in ((sans, COULEUR_TEMOIN, "témoin"), (avec, COULEUR_CHOC, "choc")):
        points = []
        for i, jour in enumerate(jours):
            valeurs = serie.get(jour) or []
            if not valeurs:
                continue
            points.append((marge_g + i * pas, y(sum(valeurs) / len(valeurs)), jour, sum(valeurs) / len(valeurs)))
        if len(points) > 1:
            trace = " ".join(f"{x:.1f},{yy:.1f}" for x, yy, _, _ in points)
            parties.append(
                f'<polyline points="{trace}" fill="none" stroke="{couleur}" stroke-width="2.4" '
                f'stroke-linejoin="round"/>'
            )
        for x, yy, jour, v in points:
            parties.append(
                f'<circle cx="{x:.1f}" cy="{yy:.1f}" r="3.4" fill="{couleur}">'
                f"<title>{escape(nom)} · {escape(jour)} · {v:.0f} %</title></circle>"
            )

    # Marqueurs « le souvenir du choc a été servi ce jour-là ».
    for i, jour in enumerate(jours):
        if jour in servis:
            parties.append(
                f'<rect x="{marge_g + i * pas - 2.5:.1f}" y="{marge_h + plot_h + 8}" '
                f'width="5" height="9" fill="{COULEUR_SERVI}" rx="1">'
                f"<title>souvenir du choc servi le {escape(jour)}</title></rect>"
            )

    for i, jour in enumerate(jours):
        if i % max(1, len(jours) // 10) == 0 or i == len(jours) - 1:
            parties.append(
                f'<text x="{marge_g + i * pas:.1f}" y="{hauteur - 26}" text-anchor="middle" '
                f'font-size="10" fill="#6A6A72">{escape(jour[5:])}</text>'
            )
    parties.append(
        f'<text x="{marge_g}" y="{hauteur - 6}" font-size="11" fill="#4A4A52">'
        f"jour simulé →</text>"
    )
    parties.append("</svg>")
    legende = (
        f'<p style="font-size:13px;color:#4A4A52">'
        f'<span style="color:{COULEUR_CHOC}">▬</span> bras avec choc &nbsp; '
        f'<span style="color:{COULEUR_TEMOIN}">▬</span> bras témoin, mêmes graines &nbsp; '
        f'<span style="color:{COULEUR_SERVI}">▮</span> le souvenir du choc était servi ce jour-là'
        f" &nbsp; <span style=\"background:{COULEUR_CHOC}22\">&nbsp;&nbsp;</span> jour de choc</p>"
    )
    return "".join(parties) + legende


# ── Assemblage ───────────────────────────────────────────────────────────────────


GABARIT = """<title>Choc et changement d'habitude</title>
<style>
  :root {{ --encre:#1A1A1F; --fond:#FBFBFA; --trait:#E2E2E6; --gris:#6A6A72; }}
  body {{ margin:0; background:var(--fond); color:var(--encre);
         font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,sans-serif; }}
  main {{ max-width:900px; margin:0 auto; padding-block:36px; padding-left:20px; padding-right:20px; }}
  h1 {{ font-size:26px; margin:0 0 4px; letter-spacing:-.02em; }}
  h2 {{ font-size:18px; margin:34px 0 10px; }}
  .sous {{ color:var(--gris); margin:0 0 28px; }}
  table {{ border-collapse:collapse; width:100%; font-size:14px; }}
  th,td {{ text-align:left; padding:7px 10px; border-bottom:1px solid var(--trait); }}
  th {{ font-weight:600; color:var(--gris); font-weight:500; }}
  td.n {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .cadre {{ border:1px solid var(--trait); border-radius:10px; padding:16px 18px;
            background:#fff; margin:18px 0; }}
  .avert {{ border-left:3px solid {COULEUR_CHOC}; }}
  .tableaux {{ overflow-x:auto; }}
</style>
<main>
<h1>Un choc, et ce que l'agent en fait</h1>
<p class="sous">{sous_titre}</p>
{corps}
</main>"""


def construire(run_choc: Path, run_temoin: Path, agent: str, mode: str, libelle_mode: str) -> str:
    rows_choc = _dedupliquer(_lire_moves(run_choc))
    rows_temoin = _dedupliquer(_lire_moves(run_temoin))
    chocs = _lire_chocs(run_choc)
    rappels = _lire_rappels(run_choc)

    avec = _proba_par_jour(rows_choc, agent, mode)
    sans = _proba_par_jour(rows_temoin, agent, mode)
    jours = sorted(set(avec) | set(sans))
    jours_de_choc = {
        c["horodatage_simule"][:10] for c in chocs if str(c["person_id"]) == agent
    }
    servis = _jours_ou_le_choc_est_servi(rappels, agent, chocs, run_choc)

    part_avec = _part_choisie_par_jour(rows_choc, agent, libelle_mode)
    part_sans = _part_choisie_par_jour(rows_temoin, agent, libelle_mode)

    corps = [courbe(jours, avec, sans, servis, jours_de_choc)]

    corps.append("<h2>Jour par jour</h2><div class='tableaux'><table>")
    corps.append(
        "<tr><th>jour</th><th class='n'>P(mode) choc</th><th class='n'>P(mode) témoin</th>"
        "<th class='n'>écart</th><th class='n'>part choisie choc</th>"
        "<th class='n'>part témoin</th><th>souvenir servi</th></tr>"
    )
    for jour in jours:
        va = avec.get(jour) or []
        vs = sans.get(jour) or []
        ma = sum(va) / len(va) if va else None
        ms = sum(vs) / len(vs) if vs else None
        ecart = f"{ma - ms:+.0f}" if (ma is not None and ms is not None) else "—"
        marque = "oui" if jour in servis else ("—" if jour not in jours_de_choc else "jour de choc")
        corps.append(
            f"<tr><td>{escape(jour)}</td>"
            f"<td class='n'>{'' if ma is None else f'{ma:.0f} %'}</td>"
            f"<td class='n'>{'' if ms is None else f'{ms:.0f} %'}</td>"
            f"<td class='n'>{ecart}</td>"
            f"<td class='n'>{part_avec.get(jour, float('nan')) * 100:.0f} %</td>"
            f"<td class='n'>{part_sans.get(jour, float('nan')) * 100:.0f} %</td>"
            f"<td>{marque}</td></tr>"
        )
    corps.append("</table></div>")

    if not chocs:
        corps.append(
            "<div class='cadre avert'><b>Aucun choc appliqué.</b> Le run désigné comme « avec "
            "choc » ne porte aucune ligne dans <code>chocs.jsonl</code> : soit le levier "
            "<code>CHOC=</code> a été oublié, soit l'agent visé n'a pas été exposé. La "
            "comparaison ci-dessus n'oppose alors que deux runs identiques.</div>"
        )
    if not rappels:
        corps.append(
            "<div class='cadre avert'><b>Aucune trace de rappel.</b> "
            "<code>agent.trace_rappel_enabled</code> était éteint : la colonne « souvenir servi » "
            "est vide, et le test de réfutation ne peut pas être conduit.</div>"
        )
    elif not servis:
        corps.append(
            "<div class='cadre avert'><b>Le souvenir du choc n'a jamais été servi.</b> "
            "Tout écart observé entre les deux bras ne peut donc PAS être attribué au rappel de "
            "ce souvenir. C'est un résultat, pas une panne : il faut le lire comme tel.</div>"
        )

    sous = (
        f"Agent {escape(agent)} · mode suivi : {escape(libelle_mode)} · "
        f"{len(jours)} jours · bras choc <code>{escape(run_choc.name)}</code> · "
        f"témoin <code>{escape(run_temoin.name)}</code>"
    )
    return GABARIT.format(
        COULEUR_CHOC=COULEUR_CHOC, sous_titre=sous, corps="\n".join(corps)
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_choc", type=Path)
    ap.add_argument("run_temoin", type=Path)
    ap.add_argument("-a", "--agent", default="899549")
    ap.add_argument("-m", "--mode", default="car", choices=sorted(_COLONNE_PROBA))
    ap.add_argument("--libelle-mode", default="Voiture Privée")
    ap.add_argument("-o", "--sortie", type=Path, required=True)
    args = ap.parse_args()

    html = construire(
        args.run_choc, args.run_temoin, args.agent, args.mode, args.libelle_mode
    )
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    args.sortie.write_text(html, encoding="utf-8")
    print(f"[OK] courbe écrite : {args.sortie} ({len(html.encode('utf-8'))} octets)")


if __name__ == "__main__":
    main()
