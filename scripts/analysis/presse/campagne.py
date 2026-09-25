#!/usr/bin/env python3
"""D'un run de campagne à la grille gelée — ticket 059, lot 5 (passerelle).

CE QUE CE MODULE COMBLE
-----------------------
`scoring.py` porte tout le calcul — écart apparié, signes, accord, kappa, gardes de vacuité —
mais il a été écrit pour l'**étage 1**, qui appariait par CONDITION : les mêmes déplacements
joués une fois sans article (C1) et une fois avec (C2), sans simulateur. Cet étage n'existe
plus.

Une campagne n'apparie pas par condition, elle apparie par **rôle** et par **jour relatif** :

| Étage 1 (n'existe plus) | Campagne (ce module) |
|---|---|
| mêmes déplacements, deux conditions | mêmes agents, avant / après parution |
| C1 → C2 | `avant` → `apres`, par rôle |
| aucun run | un run, `moves.csv` + `evenements.jsonl` |

**Le contrefactuel n'est plus une condition, c'est une période.** On compare la part modale d'un
lecteur avant sa parution à celle d'après. Le co-résident donne la diffusion ; le témoin, quand
il y en a un dans le run, donne la dérive commune.

⚠ **Le plancher de bruit n'a pas de défaut, et ce module ne lui en invente pas.** Depuis que le
foyer témoin n'est plus exigé (059 § 6.4, 2026-09-22), il ne se lit plus dans le run : il se
reprend du 095 § 7 bis (3,2 % — **une** mesure, **un** persona) ou se réétablit par rejeu à
l'identique. Il se **déclare** sur la ligne de commande, et il est recopié dans l'en-tête du
rapport. Un écart plus petit que lui n'est pas un effet.

⚠ **Chaque agent est son propre contrôle, et cela a un prix.** Une dérive du modèle au fil du
run se lirait comme un effet. C'est ce que le rôle `temoin` sert à écarter quand il est
présent ; sans lui, la dérive n'est pas mesurée et le rapport le dit en toutes lettres.

    python -m scripts.analysis.presse.campagne <run> --plancher 0.032
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE))

from scripts.analysis.presse.grille import charger_grille  # noqa: E402
from scripts.analysis.presse.scoring import (  # noqa: E402
    NON_CONCLUANT,
    EcartModal,
    accord_de_signe,
    kappa_pondere,
    signes_observes,
)

# Mode de la grille → mode canonique du dépôt. EXPLICITE : trois vocabulaires coexistent, et un
# mot qui passerait « par défaut » scorerait la prédiction d'un mode contre la mesure d'un autre.
MODE_GRILLE_VERS_CANONIQUE = {
    "voiture": "car",
    "velo": "cycling",
    "marche": "walking",
    "tc": "public_transport",
}

# Colonne de `moves.csv` portant le mode retenu, et celle du rôle.
COLONNE_MODE = "Mode de transport Choisi"
COLONNE_ROLE = "Rôle"
COLONNE_JOUR = "Jour relatif au choc"
# ⚠ « Référence » porte l'identifiant du RUN, pas celui de l'agent — trouvé le 2026-09-22 sur
# un run réel, après que le banc l'ait laissé passer : ses stubs écrivaient un identifiant
# d'agent dans cette colonne, donc ils testaient leur propre convention. L'agent est sous
# « ID Personne ».
COLONNE_AGENT = "ID Personne"
COLONNE_EVENEMENT = "Choc"

# Effectif minimal par (rôle, période). Plus bas que celui de l'étage 1 (30 déplacements) parce
# qu'une campagne à six foyers n'en produira jamais autant par mode et par période — et plus
# haut que 1, parce qu'un seul déplacement qui bascule déplace une part de cent points.
EFFECTIF_MIN_PERIODE = 8


def _decisions(run: Path) -> list[dict]:
    chemin = run / "moves.csv"
    if not chemin.is_file():
        raise SystemExit(f"❌ {chemin} introuvable")
    with chemin.open(encoding="utf-8") as f:
        lecteur = csv.DictReader(f)
        manquantes = [
            c for c in (COLONNE_MODE, COLONNE_ROLE, COLONNE_JOUR)
            if c not in (lecteur.fieldnames or [])
        ]
        if manquantes:
            raise SystemExit(
                f"❌ colonnes absentes de {chemin} : {manquantes}. Un run antérieur au "
                f"ticket 100 lot 5 ne porte pas le rôle, et il ne se reconstitue pas après "
                f"coup — il faudrait savoir qui était exposé."
            )
        return list(lecteur)


def _evenement_du_run(run: Path) -> str:
    for nom in ("evenements.jsonl", "chocs.jsonl"):
        chemin = run / nom
        if not chemin.is_file():
            continue
        for brut in chemin.read_text("utf-8").splitlines():
            if not brut.strip():
                continue
            try:
                ligne = json.loads(brut)
            except json.JSONDecodeError:
                continue
            return str(ligne.get("evenement_id") or ligne.get("choc_id") or "")
    return ""


def parts_par_role(
    run: Path, *, article: str
) -> tuple[dict[tuple[str, str], EcartModal], dict[str, dict[str, int]]]:
    """Écart avant / après parution, par rôle et par mode de la grille.

    Rend `({(role, mode_grille): EcartModal}, effectifs)`. Le mode de la grille est traduit vers
    le vocabulaire canonique une seule fois, ici.
    """
    lignes = _decisions(run)
    from scripts.analysis.lecture_avant_decision import informes_du_run, sous_role

    informes = informes_du_run(run)
    # `avant` = jour relatif < 0 ; `apres` = jour relatif >= 0. Le jour 0 est celui où l'agent
    # reçoit le texte : il décide APRÈS l'avoir lu, puisque la prise est au réveil. Le ranger
    # dans « avant » diluerait l'effet du premier jour, qui est celui qu'on cherche.
    seaux: dict[tuple[str, str], list[str]] = defaultdict(list)
    effectifs: dict[str, dict[str, int]] = defaultdict(lambda: {"avant": 0, "apres": 0})
    for ligne in lignes:
        role = (ligne.get(COLONNE_ROLE) or "").strip()
        mode = (ligne.get(COLONNE_MODE) or "").strip()
        brut_jour = (ligne.get(COLONNE_JOUR) or "").strip()
        if not role or not mode or not brut_jour:
            continue
        try:
            jour = int(brut_jour)
        except ValueError:
            continue
        periode = "apres" if jour >= 0 else "avant"
        # Ticket 111 — le co-résident compte AUSSI sous son sous-rôle (informé ou non), sans
        # quitter `co_resident` : les campagnes déjà scorées sous ce rôle ne bougent pas.
        for r in dict.fromkeys((role, sous_role(role, ligne.get("ID Personne") or "", informes))):
            seaux[(r, periode)].append(mode)
            effectifs[r][periode] += 1

    ecarts: dict[tuple[str, str], EcartModal] = {}
    for role in sorted({r for r, _ in seaux}):
        avant = seaux.get((role, "avant")) or []
        apres = seaux.get((role, "apres")) or []
        for mode_grille, canonique in MODE_GRILLE_VERS_CANONIQUE.items():
            if len(avant) < EFFECTIF_MIN_PERIODE or len(apres) < EFFECTIF_MIN_PERIODE:
                # Garde de vacuité : « non concluant », jamais 0,0. Dans ce dépôt, l'absence
                # de mesure produit volontiers la valeur parfaite, et ce motif a déjà menti.
                ecarts[(role, mode_grille)] = EcartModal(
                    article, mode_grille, None, None,
                    min(len(avant), len(apres)), verdict=NON_CONCLUANT,
                )
                continue
            ecarts[(role, mode_grille)] = EcartModal(
                article=article,
                mode=mode_grille,
                part_reference=avant.count(canonique) / len(avant),
                part_condition=apres.count(canonique) / len(apres),
                n_apparies=min(len(avant), len(apres)),
            )
    return ecarts, dict(effectifs)


def depouiller(
    runs: list[Path], *, grille_chemin: Path, plancher: float, role: str = "expose"
) -> dict:
    """Le dépouillement complet : un run par article, scoré contre la grille gelée."""
    grille = charger_grille(grille_chemin)
    observes: dict[tuple[str, str], str | None] = {}
    intensites: dict[tuple[str, str], int | None] = {}
    detail: list[tuple[str, dict]] = []

    for run in runs:
        article = _evenement_du_run(run)
        if not article:
            raise SystemExit(f"❌ {run} ne porte aucun événement : rien à scorer")
        ecarts, effectifs = parts_par_role(run, article=article)
        du_role = [e for (r, _m), e in ecarts.items() if r == role]
        signes = signes_observes(du_role, plancher_de_bruit=plancher)
        for (_a, mode), signe in signes.items():
            observes[(article, mode)] = signe
            # L'intensité observée n'est PAS dérivée de l'écart : la grille l'exprime sur une
            # échelle ordinale 0-3 que rien, dans une part modale, ne permet de retrouver. Elle
            # reste donc vide ici, et le kappa sortira « non concluant ». C'est exact : cette
            # mesure-là demande le troisième niveau — ce que l'agent a compris du texte — qui
            # se lit dans `evenements.jsonl` sous `intensite_jugee`, pas dans `moves.csv`.
            intensites[(article, mode)] = None
        detail.append((article, {"effectifs": effectifs, "ecarts": du_role}))

    accord = accord_de_signe(grille, observes)
    return {
        "grille": grille,
        "accord": accord,
        "kappa": kappa_pondere(grille, intensites),
        "observes": observes,
        "detail": detail,
        "plancher": plancher,
        "role": role,
    }


def rendre(resultat: dict) -> str:
    grille = resultat["grille"]
    accord = resultat["accord"]
    lignes = [
        "# Dépouillement de campagne — presse locale",
        "",
        f"- grille gelée : `{grille.empreinte[:16]}…`",
        f"- plancher de bruit déclaré : **{resultat['plancher']:.3f}** "
        f"({resultat['plancher'] * 100:.1f} %)",
        f"- rôle scoré : `{resultat['role']}`",
        "",
        "⚠ Le plancher de bruit est **déclaré**, pas mesuré par ce run. Depuis que le foyer",
        "témoin n'est plus exigé, il se reprend du ticket 095 § 7 bis — une mesure, un persona —",
        "ou se réétablit par un rejeu à l'identique. Un écart plus petit que lui n'est pas un effet.",
        "",
        "## Accord de signe",
        "",
    ]
    if accord.verdict:
        lignes.append(f"**{accord.verdict}** — aucune cellule lisible.")
    else:
        lignes.append(
            f"{accord.concordants} concordances sur {accord.lisibles} cellules lisibles "
            f"({accord.taux:.0%}), {accord.non_lisibles} non lisibles sur les "
            f"{len(grille.cellules)} de la grille."
        )
        if accord.intervalle:
            lignes.append(
                f"Intervalle à 95 %, rééchantillonné **par événement** : "
                f"[{accord.intervalle[0]:.0%} ; {accord.intervalle[1]:.0%}]."
            )
        else:
            lignes.append(
                "Intervalle **non calculable** : moins de deux événements distincts. Un "
                "intervalle tiré sur un seul groupe ne rééchantillonne rien."
            )
        lignes.append("")
        lignes.append(
            "⚠ Pas de test binomial : les cellules d'un même événement ne sont pas "
            "indépendantes — leurs parts somment à un, et un seul comportement en produit "
            "plusieurs. L'incertitude est groupée par article."
        )

    lignes += ["", f"## Kappa pondéré", "", f"{resultat['kappa']}", ""]
    if resultat["kappa"] == NON_CONCLUANT:
        lignes.append(
            "L'intensité ordinale ne se dérive pas d'une part modale. Elle demande le "
            "troisième niveau de mesure — ce que l'agent a compris du texte — qui se lit dans "
            "`evenements.jsonl` sous `intensite_jugee`."
        )

    lignes += ["", "## Effectifs, par article et par rôle", ""]
    for article, contenu in resultat["detail"]:
        lignes.append(f"**{article}**")
        for role, compte in sorted(contenu["effectifs"].items()):
            lignes.append(
                f"- `{role}` : {compte['avant']} décision(s) avant parution, "
                f"{compte['apres']} après"
            )
        lignes.append("")
    return "\n".join(lignes)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("runs", type=Path, nargs="+", help="un run par article")
    p.add_argument(
        "--plancher", type=float, required=True,
        help="plancher de bruit, en PART (0.032 pour 3,2 %%). Obligatoire : un défaut le ferait "
             "oublier, et un écart plus petit que le bruit n'est pas un effet",
    )
    p.add_argument(
        "--role", default="expose",
        choices=("expose", "co_resident", "co_resident_informe", "co_resident_non_informe",
                 "temoin"),
        help="co_resident_informe / co_resident_non_informe : ticket 111, lus dans "
             "relais_foyer.jsonl",
    )
    p.add_argument(
        "--grille", type=Path,
        default=RACINE / "docs" / "paper" / "sources" / "actualites" / "grille_signes.yaml",
    )
    p.add_argument("-o", "--sortie", type=Path)
    args = p.parse_args()

    rendu = rendre(
        depouiller(args.runs, grille_chemin=args.grille,
                   plancher=args.plancher, role=args.role)
    )
    if args.sortie:
        args.sortie.parent.mkdir(parents=True, exist_ok=True)
        args.sortie.write_text(rendu, encoding="utf-8")
        print(f"✅ {args.sortie}")
    else:
        print(rendu)
    return 0


if __name__ == "__main__":
    sys.exit(main())
