"""Appariement décision par décision de DEUX exécutions — le chiffrage de l'axe 0 (ticket 073).

L'axe 0 du ticket 073 rejoue une expérience **sans rien changer** : même modèle, même prompt,
même jeu, mêmes graines. Tout écart entre les deux sorties appartient alors au fournisseur, et
à lui seul — le témoin `exp_rf_…_c_nosim` l'établit, ses deux exécutions étant identiques au
centième. Cet outil met les deux exécutions face à face au niveau de la décision.

Trois niveaux, du plus fin au plus grossier :

1. **les masses** — le vecteur de probabilité que le modèle attribue aux options offertes ;
2. **le mode retenu** — l'option effectivement tirée dans ces masses ;
3. **le macro** — composite et parts modales, délégué à `experiences.registre.comparer`.

⚠ **Les masses se lisent dans `poids_presentes`, jamais dans `distribution`.** `distribution`
agrège sur les six modes canoniques et écrase plusieurs options d'un même mode : mesuré le
2026-09-21 sur les 120 premières décisions du réplicat, il annonçait 5 « bascules à masses
égales » là où `poids_presentes` n'en voit qu'UNE. Les quatre autres étaient un artefact de
l'agrégation. La différence n'est pas cosmétique : le ticket qualifie une bascule à masses
égales de défaut du DISPOSITIF, pas du modèle. Se tromper de vecteur, c'est inventer un bug.

Ce que cet outil NE dit PAS :

- il ne score rien — le composite reste au scoreur, et le niveau 3 n'est qu'un renvoi ;
- il ne conclut pas sur une exécution partielle. Une reprise en cours ne couvre qu'une part
  de la cohorte ; le chiffre est alors une indication, pas une mesure, et l'outil le dit en
  `[ALARME]`. C'est exactement le défaut du 2026-09-15 : un `moves.csv` tronqué à 274 lignes
  publié comme s'il portait les 3 299 décisions ;
- il ne distingue pas deux graines. Une graine change l'ordre, le tirage et le calendrier ;
  l'appariement ne saurait pas démêler ces effets et n'y prétend pas.

Usage :

    make apparier A=<dossier exécution> B=<dossier exécution> [JSON=<fichier>] [TOUT=1]

Usage en notebook :

    import sys; sys.path.append("..")          # depuis scripts/analysis/
    from appariement_executions import apparier
    r = apparier(dossier_a, dossier_b)
    r["masses"]["l1_moyenne"]
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger("appariement")

# Fichier de traces lu de part et d'autre. Une ligne = une décision.
F_DECISIONS = "decisions.jsonl"

# Sous ce taux de couverture, l'appariement ne porte plus sur la cohorte mais sur un
# échantillon de circonstance : il sort en [ALARME] et le rapport le répète.
SEUIL_COUVERTURE = 0.80

# Bornes de l'histogramme des écarts L1 entre masses (L1 ∈ [0, 2]). Une queue épaisse sur peu
# de décisions ne se lit pas comme un bruit diffus sur toutes : c'est la forme qui tranche.
TRANCHES_L1 = (0.0, 0.05, 0.10, 0.25, 0.50, 1.00, 2.00)

# Deux flottants issus du même calcul ne se comparent pas au bit près.
EPSILON = 1e-9


# ─────────────────────────────── lecture ────────────────────────────────


def charger(dossier: str | Path) -> dict[tuple[str, str], dict]:
    """Les décisions d'une exécution, indexées par `(person_id, activity_id)`.

    C'est le couple qui identifie un déplacement : le même individu décide plusieurs fois
    dans sa journée, et le même déplacement se retrouve d'une exécution à l'autre.
    """
    chemin = Path(dossier) / F_DECISIONS
    if not chemin.exists():
        raise FileNotFoundError(
            f"{chemin} est absent — ce dossier n'est pas une exécution, ou elle n'a "
            "archivé aucune décision."
        )
    par_cle: dict[tuple[str, str], dict] = {}
    doublons = 0
    for ligne in chemin.open(encoding="utf-8"):
        ligne = ligne.strip()
        if not ligne:
            continue
        d = json.loads(ligne)
        cle = (str(d.get("person_id")), str(d.get("activity_id")))
        if cle in par_cle:
            doublons += 1
        par_cle[cle] = d
    if doublons:
        logger.warning(
            f"[appariement] {chemin} : {doublons} couple(s) (person_id, activity_id) "
            "répété(s) — la dernière occurrence fait foi."
        )
    return par_cle


def _codes_offerts(d: dict) -> list[str]:
    """Les codes des options soumises au décideur, dans l'ordre où elles lui sont présentées.

    L'ordre compte : `poids_presentes` s'aligne dessus, et `index_presente` y renvoie.
    """
    return [str(o.get("code")) for o in (d.get("presentees") or [])]


def _masses(d: dict, taille: int) -> list[float]:
    """`poids_presentes` complété à `taille` — jamais `distribution` (cf. l'en-tête)."""
    p = [float(x) for x in (d.get("poids_presentes") or [])]
    return p + [0.0] * max(0, taille - len(p))


def _code_retenu(d: dict) -> Optional[str]:
    return (d.get("retenue") or {}).get("code")


# ────────────────────────────── classement ──────────────────────────────


def classer(
    a: dict[tuple[str, str], dict], b: dict[tuple[str, str], dict]
) -> dict[str, list[tuple[str, str]]]:
    """Range les clés communes en trois populations disjointes.

    Le classement EST la mesure : confondre ces populations, c'est imputer au décideur une
    divergence que la chaîne a produite en amont, ou noyer le signal dans des décisions où
    le modèle n'a jamais été sollicité.

    - `cascade_amont` : les options offertes diffèrent. Le déplacement précédent a basculé,
      le vélo n'est plus là où il était, l'offre change. Rien ici n'est imputable au décideur
      SUR CE DÉPLACEMENT — l'écart est réel mais hérité.
    - `choix_unique` : une seule option, aucune sollicitation. Témoin : ces décisions doivent
      coïncider, et si elles divergent c'est que l'offre a bougé, donc que la cascade amont
      n'a pas été correctement détectée.
    - `appariables` : mêmes options ET décideur sollicité des deux côtés. **La seule
      population sur laquelle l'axe 0 se chiffre.**
    """
    familles: dict[str, list[tuple[str, str]]] = {
        "cascade_amont": [],
        "choix_unique": [],
        "appariables": [],
        "hors_mesure": [],
        "methode_dissymetrique": [],
    }
    for cle in sorted(set(a) & set(b)):
        da, db = a[cle], b[cle]
        ma, mb = da.get("methode"), db.get("methode")
        if _codes_offerts(da) != _codes_offerts(db):
            familles["cascade_amont"].append(cle)
        elif ma != mb:
            # Le décideur a répondu d'un côté et pas de l'autre, à offre identique. Ni cascade,
            # ni choix unique : un incident, et le taire le rendrait invisible.
            familles["methode_dissymetrique"].append(cle)
        elif ma == "decideur":
            familles["appariables"].append(cle)
        elif ma == "choix_unique":
            familles["choix_unique"].append(cle)
        else:
            # Même méthode des deux côtés, mais aucune décision à comparer : `inexploitable`
            # (aucune proposition des moteurs), `sans_solution`. Les ranger en dissymétrie
            # inventerait 9 incidents là où il n'y en a aucun — relevé le 2026-09-21.
            familles["hors_mesure"].append(cle)
    return familles


def _tranche(l1: float) -> str:
    if l1 <= EPSILON:
        return "0"
    for bas, haut in zip(TRANCHES_L1, TRANCHES_L1[1:]):
        if l1 <= haut:
            return f"]{bas:g} ; {haut:g}]"
    return f"> {TRANCHES_L1[-1]:g}"


# ─────────────────────────────── mesures ────────────────────────────────


def mesurer(
    a: dict[tuple[str, str], dict],
    b: dict[tuple[str, str], dict],
    cles: Iterable[tuple[str, str]],
) -> dict[str, Any]:
    """Niveaux 1 et 2 sur les seules décisions `appariables`.

    Rend aussi, nommées et détaillées, les bascules **à masses strictement identiques** :
    à masses égales et `graine_tirage` égale, le tirage DOIT rendre la même option. Une
    bascule y est un défaut du dispositif, pas une dispersion du modèle, et elle se traite
    comme tel — donc elle se liste, elle ne se résume pas à un taux.
    """
    cles = list(cles)
    l1s: list[float] = []
    identiques = argmax_bascule = retenue_bascule = 0
    histogramme: dict[str, int] = {}
    suspectes: list[dict] = []

    for cle in cles:
        da, db = a[cle], b[cle]
        taille = max(len(_codes_offerts(da)), len(da.get("poids_presentes") or []))
        pa, pb = _masses(da, taille), _masses(db, taille)
        l1 = sum(abs(x - y) for x, y in zip(pa, pb))
        l1s.append(l1)
        egales = l1 <= EPSILON
        if egales:
            identiques += 1
        histogramme[_tranche(l1)] = histogramme.get(_tranche(l1), 0) + 1

        if pa and pb and max(range(len(pa)), key=pa.__getitem__) != max(
            range(len(pb)), key=pb.__getitem__
        ):
            argmax_bascule += 1

        ra, rb = _code_retenu(da), _code_retenu(db)
        if ra != rb:
            retenue_bascule += 1
            if egales:
                suspectes.append(
                    {
                        "person_id": cle[0],
                        "activity_id": cle[1],
                        "poids": pa,
                        "options": _codes_offerts(da),
                        "a": {
                            "code": ra,
                            "index_presente": (da.get("retenue") or {}).get(
                                "index_presente"
                            ),
                            "mode": (da.get("retenue") or {}).get("mode"),
                            "identifiant_lot": da.get("identifiant_lot"),
                        },
                        "b": {
                            "code": rb,
                            "index_presente": (db.get("retenue") or {}).get(
                                "index_presente"
                            ),
                            "mode": (db.get("retenue") or {}).get("mode"),
                            "identifiant_lot": db.get("identifiant_lot"),
                        },
                        "graine_tirage": {
                            "a": da.get("graine_tirage"),
                            "b": db.get("graine_tirage"),
                        },
                    }
                )

    n = len(cles)
    return {
        "n": n,
        "masses": {
            "identiques": identiques,
            "part_identiques": (identiques / n) if n else None,
            "l1_moyenne": statistics.mean(l1s) if l1s else None,
            "l1_mediane": statistics.median(l1s) if l1s else None,
            "l1_max": max(l1s) if l1s else None,
            "histogramme": dict(sorted(histogramme.items())),
            "argmax_bascule": argmax_bascule,
            "part_argmax_bascule": (argmax_bascule / n) if n else None,
        },
        "retenue": {
            "bascules": retenue_bascule,
            "taux_bascule": (retenue_bascule / n) if n else None,
            "bascules_a_masses_identiques": len(suspectes),
            "detail_masses_identiques": suspectes,
        },
    }


def _composite(dossier: str | Path) -> Optional[dict]:
    """Le composite d'une exécution, lu dans son `scores.json`.

    `registre.synthese()` porte les compteurs et les parts modales, PAS le composite : il
    naît du scoreur, qui écrit `scores.json` à part. Une exécution partielle n'en a pas —
    et c'est normal, le scoreur refuse de noter un run incomplet.
    """
    f = Path(dossier) / "scores.json"
    if not f.exists():
        return None
    return (json.loads(f.read_text(encoding="utf-8")) or {}).get("composite")


def _garde(a: str | Path, b: str | Path, inclure_invalides: bool) -> dict[str, Any]:
    """Niveau 3 + garde de comparabilité, délégués au registre (RG-4, P6).

    Apparier deux exécutions qui ne diffèrent pas QUE par le hasard ne mesure pas le hasard :
    `registre.comparer` le vérifie sur les empreintes, jamais sur la foi des noms, et refuse
    une exécution invalidée ou archivée. Le module n'est disponible que là où le paquet
    `experiences` l'est (conteneur `controller`) ; ailleurs, l'appariement reste calculable
    mais la garde ne joue pas, et le rapport le dit au lieu de le taire.
    """
    try:
        from experiences import registre  # type: ignore
    except Exception as exc:  # noqa: BLE001 — paquet absent hors du conteneur
        logger.warning(
            f"[appariement] garde de comparabilité INDISPONIBLE ({exc.__class__.__name__}: "
            f"{exc}) — les empreintes ne sont pas vérifiées. Lancer dans le conteneur "
            "`controller` (make apparier) pour l'activer."
        )
        return {
            "disponible": False,
            "comparable": None,
            "differences": None,
            "composite_a": _composite(a),
            "composite_b": _composite(b),
        }

    r = registre.comparer(a, b, inclure_invalides=inclure_invalides)
    return {
        "disponible": True,
        "comparable": r.get("comparable"),
        "differences": r.get("differences"),
        "statuts": r.get("statuts"),
        "composite_a": _composite(a),
        "composite_b": _composite(b),
    }


# ────────────────────────────── orchestration ───────────────────────────


def apparier(
    dossier_a: str | Path,
    dossier_b: str | Path,
    *,
    inclure_invalides: bool = False,
    seuil_couverture: float = SEUIL_COUVERTURE,
) -> dict[str, Any]:
    """Apparie deux exécutions et rend les trois niveaux. Ne modifie rien, nulle part."""
    debut = time.monotonic()
    logger.info(f"[appariement] début : A={dossier_a} · B={dossier_b}")

    macro = _garde(dossier_a, dossier_b, inclure_invalides)
    if macro["disponible"] and macro["comparable"] is False and not inclure_invalides:
        raise ValueError(
            "appariement refusé : les deux exécutions ne diffèrent pas que par le hasard — "
            f"{json.dumps(macro['differences'], ensure_ascii=False)}. Apparier des conditions "
            "différentes ne mesure pas le non-déterminisme du fournisseur. Pour passer outre "
            "en connaissance de cause : --tout."
        )

    a, b = charger(dossier_a), charger(dossier_b)
    familles = classer(a, b)
    communes = set(a) & set(b)
    orphelines_a, orphelines_b = set(a) - communes, set(b) - communes

    # La couverture qui compte n'est PAS `appariables / communes` : les choix uniques la font
    # chuter alors qu'ils sont légitimes. C'est la part de la plus large des deux exécutions
    # que l'appariement atteint — donc ce qui dirait qu'on publie une fraction pour un tout.
    reference = max(len(a), len(b))
    couverture = (len(communes) / reference) if reference else 0.0

    mesures = mesurer(a, b, familles["appariables"])

    duree = time.monotonic() - debut
    logger.info(
        f"[appariement] A {len(a)} décisions · B {len(b)} · communes {len(communes)} "
        f"· orphelines A {len(orphelines_a)} / B {len(orphelines_b)} · "
        f"appariables {len(familles['appariables'])} · cascade amont "
        f"{len(familles['cascade_amont'])} · choix unique {len(familles['choix_unique'])} "
        f"· hors mesure {len(familles['hors_mesure'])} · méthode dissymétrique "
        f"{len(familles['methode_dissymetrique'])}"
    )
    if couverture < seuil_couverture:
        logger.error(
            f"[ALARME] [appariement] couverture {couverture:.1%} < {seuil_couverture:.0%} : "
            f"{len(communes)} décisions appariées pour {reference} archivées du côté le plus "
            "avancé. Le chiffre porte sur un échantillon de circonstance, PAS sur la cohorte "
            "— ne pas le publier tel quel (cf. le moves.csv tronqué du 2026-09-15)."
        )
    if mesures["retenue"]["bascules_a_masses_identiques"]:
        logger.error(
            f"[ALARME] [appariement] "
            f"{mesures['retenue']['bascules_a_masses_identiques']} bascule(s) du mode retenu "
            "à masses STRICTEMENT identiques et graine de tirage égale : le tirage devrait "
            "être reproductible. C'est un défaut du dispositif, pas une dispersion du modèle."
        )
    logger.info(
        f"[appariement] terminé en {duree:.2f} s — "
        f"{len(familles['appariables'])} décision(s) chiffrée(s), "
        f"masses identiques {mesures['masses']['identiques']}, "
        f"bascules {mesures['retenue']['bascules']}"
    )

    return {
        "a": str(dossier_a),
        "b": str(dossier_b),
        "couverture": {
            "decisions_a": len(a),
            "decisions_b": len(b),
            "communes": len(communes),
            "orphelines_a": len(orphelines_a),
            "orphelines_b": len(orphelines_b),
            "reference": reference,
            "taux": couverture,
            "seuil": seuil_couverture,
            "suffisante": couverture >= seuil_couverture,
        },
        "populations": {k: len(v) for k, v in familles.items()},
        "masses": mesures["masses"],
        "retenue": mesures["retenue"],
        "macro": macro,
        "duree_s": round(duree, 3),
    }


# ──────────────────────────────── rendu ─────────────────────────────────


def _pc(x: Optional[float]) -> str:
    return "—" if x is None else f"{x:.1%}"


def _f(x: Optional[float], n: int = 4) -> str:
    return "—" if x is None else f"{x:.{n}f}"


def rendre(r: dict[str, Any]) -> str:
    """Le rapport lisible. L'ordre suit le ticket : couverture, populations, 1, 2, 3."""
    c, p, m, ret = r["couverture"], r["populations"], r["masses"], r["retenue"]
    L = [
        "=== APPARIEMENT EXÉCUTION CONTRE EXÉCUTION (axe 0, ticket 073) ===",
        f"A : {r['a']}",
        f"B : {r['b']}",
        "",
        f"Couverture — {c['communes']} décisions communes sur {c['reference']} "
        f"({_pc(c['taux'])}) · seuil {_pc(c['seuil'])} : "
        f"{'suffisante' if c['suffisante'] else '*** INSUFFISANTE — chiffre non publiable ***'}",
        f"  A {c['decisions_a']} · B {c['decisions_b']} · "
        f"orphelines A {c['orphelines_a']} / B {c['orphelines_b']}",
        "",
        "Populations",
        f"  appariables (chiffrées)   : {p['appariables']}",
        f"  cascade amont (écartées)  : {p['cascade_amont']}",
        f"  choix unique (écartées)   : {p['choix_unique']}",
        f"  hors mesure (écartées)    : {p['hors_mesure']}",
        f"  méthode dissymétrique     : {p['methode_dissymetrique']}",
        "",
        "Niveau 1 — masses (poids_presentes)",
        f"  identiques        : {m['identiques']} ({_pc(m['part_identiques'])})",
        f"  L1 moyenne        : {_f(m['l1_moyenne'])}",
        f"  L1 médiane        : {_f(m['l1_mediane'])}",
        f"  L1 max            : {_f(m['l1_max'])}",
        f"  argmax qui bascule: {m['argmax_bascule']} ({_pc(m['part_argmax_bascule'])})",
        "  histogramme L1    : "
        + (
            " · ".join(f"{k} → {v}" for k, v in m["histogramme"].items())
            if m["histogramme"]
            else "—"
        ),
        "",
        "Niveau 2 — option retenue",
        f"  bascules          : {ret['bascules']} ({_pc(ret['taux_bascule'])})",
        f"  dont à masses identiques : {ret['bascules_a_masses_identiques']}",
    ]
    for s in ret["detail_masses_identiques"]:
        L.append(
            f"    ⚠ {s['person_id']} / {s['activity_id']} · poids {s['poids']} · "
            f"A idx {s['a']['index_presente']} ({s['a']['mode']}) → "
            f"B idx {s['b']['index_presente']} ({s['b']['mode']}) · "
            f"graine_tirage {s['graine_tirage']['a']}/{s['graine_tirage']['b']} · "
            f"lots {s['a']['identifiant_lot']} / {s['b']['identifiant_lot']}"
        )
    L += ["", "Niveau 3 — macro"]
    macro = r["macro"]
    if not macro["disponible"]:
        L.append("  garde de comparabilité indisponible (paquet `experiences` absent)")
    else:
        L.append(f"  comparable : {macro['comparable']}")
        if macro["differences"]:
            for d in macro["differences"]:
                L.append(f"    différence : {d}")
    for cote in ("a", "b"):
        comp = macro.get(f"composite_{cote}") or {}
        if comp:
            L.append(
                f"  {cote.upper()} composite {_f(comp.get('emd_jsd'), 4)} · "
                f"hors choix unique {_f(comp.get('emd_jsd_hors_choix_unique'), 4)} · "
                f"L1 {_f(comp.get('l1'), 2)}"
            )
        else:
            L.append(f"  {cote.upper()} composite — (pas de scores.json : run partiel)")
    return "\n".join(L)


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    ap = argparse.ArgumentParser(
        description="Apparie deux exécutions décision par décision (axe 0, ticket 073)."
    )
    ap.add_argument("a", help="dossier de l'exécution de référence")
    ap.add_argument("b", help="dossier de l'exécution à comparer")
    ap.add_argument("--json", dest="json_out", help="écrit le rapport complet en JSON")
    ap.add_argument(
        "--tout",
        action="store_true",
        help="apparie malgré une exécution invalidée, archivée ou non comparable",
    )
    ap.add_argument(
        "--seuil",
        type=float,
        default=SEUIL_COUVERTURE,
        help=f"seuil d'alarme sur la couverture (défaut {SEUIL_COUVERTURE})",
    )
    args = ap.parse_args(argv)

    try:
        r = apparier(
            args.a, args.b, inclure_invalides=args.tout, seuil_couverture=args.seuil
        )
    except (ValueError, FileNotFoundError) as exc:
        logger.error(f"[appariement] {exc}")
        return 2

    print(rendre(r))
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        logger.info(f"[appariement] rapport JSON écrit : {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
