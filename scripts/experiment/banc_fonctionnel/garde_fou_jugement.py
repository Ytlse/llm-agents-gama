#!/usr/bin/env python3
"""Le garde-fou du jugement — ticket 095, décision de l'auteur du 2026-09-22.

POURQUOI
--------
Depuis la décision D7 du ticket 100, la gravité d'un souvenir est celle que l'agent estime, et
elle seule. C'est elle qui fixe sa durée de vie. Un modèle qui répondrait « anodin » partout
ferait donc tourner cinquante jours de campagne pour ne rien mesurer — ce qui a failli arriver le
2026-09-22, pour une autre raison : le texte de l'événement n'atteignait pas le modèle, et quinze
jugements sur quinze répondaient `negligible` à une page blanche.

Ce script confronte ce que l'agent répond à ce qu'on avait en tête en analysant les textes, AVANT
de payer une campagne. Trente-deux appels, une douzaine de minutes.

CE QU'IL RÉPOND, ET DANS CET ORDRE
----------------------------------
1. **L'écart à l'attendu.** Un jugement hors de sa plage n'est pas une erreur en soi — c'est un
   signal. Au-delà de `part_hors_plage_max`, la campagne ne part pas.
2. **L'étalement entre textes.** C'est le critère qui DÉCIDE. Si tous les textes reçoivent le même
   échelon, l'expérience sur la durée ne mesurera rien, quelle que soit la justesse de chaque
   jugement pris isolément. Et si les trois incidents ne se séparent pas entre eux, ce sont les
   trois bras de l'expérience qui s'effondrent, pas seulement une statistique.
3. **La part du profil.** Le même texte soumis à plusieurs personas. L'écart entre profils est
   ATTENDU — « peut-être que selon le profil de la personne, la réponse ne sera pas
   systématiquement la même » — et il se mesure au lieu d'être traité comme du bruit.

⚠ CE QU'IL NE PEUT PAS FAIRE : dire si l'agent a RAISON. Il dit si le dispositif produit encore
l'étalement sur lequel l'analyse des textes s'appuyait.

⚠ LA VALEUR D'UNE PLAGE DÉPEND DE QUI L'A ÉCRITE ET QUAND. La grille porte un champ `deja_vu` par
texte. Une plage écrite après avoir vu des réponses ne prouve presque rien ; le rapport sépare
donc les deux populations et ne mélange jamais leurs taux.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
AGENTS = RACINE / "services" / "llm-agents"
for chemin in (str(RACINE), str(AGENTS)):
    if chemin not in sys.path:
        sys.path.insert(0, chemin)

from scripts.experiment.banc_fonctionnel import stubs  # noqa: E402
from scripts.experiment.banc_fonctionnel.clients import (  # noqa: E402
    GROQ,
    BudgetEpuise,
    ClientEpingle,
    Journal,
)

GRILLE = RACINE / "specs" / "ticket_095" / "grille_attendus.yaml"
# Repli quand la grille ne déclare pas sa marche. L'ordre VISÉ appartient à l'auteur et se lit
# dans la grille (clé `marche:`) : le coder ici reviendrait à ce que le testeur décide de
# l'hypothèse qu'il teste.
BRAS = ("c2_crevaison", "c6_voiture_suspecte", "c3_panne_reseau")


def charger_grille(chemin: Path) -> tuple[dict, dict, tuple[str, ...]]:
    """La grille, ses seuils et sa marche.

    Une plage vide ARRÊTE : une grille à moitié remplie ne garde rien. Un bras nommé dans la
    marche mais absent de la grille ARRÊTE aussi — l'ordre porterait sur un texte qu'on ne
    mesure pas.
    """
    import yaml

    brut = yaml.safe_load(chemin.read_text("utf-8"))
    seuils = brut.pop("seuils", {}) or {}
    marche = tuple(brut.pop("marche", None) or BRAS)
    vides = [k for k, v in brut.items() if not (v or {}).get("attendu")]
    if vides:
        raise SystemExit(
            f"grille incomplète : {vides} n'ont pas de plage attendue. Un texte sans attendu "
            f"passerait le garde-fou quoi que le modèle réponde — c'est pire que pas de test."
        )
    if absents := [b for b in marche if b not in brut]:
        raise SystemExit(
            f"la marche nomme {absents}, que la grille ne déclare pas. L'ordre porterait sur "
            f"un texte qui n'est pas mesuré."
        )
    return brut, seuils, marche


def texte_de(nom: str) -> str:
    """Le texte réellement servi, lu par le chargeur — jamais recopié à la main."""
    from llm.evenements import charger

    e = charger(AGENTS / "config" / "evenements" / f"{nom}.yaml")
    if e.texte_cite is not None:
        return e.texte_cite.servi
    return e.jours[e.premier_jour].texte


async def mesurer(client: ClientEpingle, grille: dict, personas: int, sortie: Path,
                  marche: tuple[str, ...] = BRAS) -> dict:
    from llm.evenements.jugement import JugementRefuse, juger
    from llm.gravite import NIVEAUX

    population = stubs.population_de_banc()[:personas]
    rangs = {niveau: i for i, niveau in enumerate(NIVEAUX)}
    lignes: list[dict] = []

    for nom, attendu in grille.items():
        texte = texte_de(nom)
        plage = set(attendu["attendu"])
        modes_attendus = set(attendu.get("modes_attendus") or [])
        for agent in population:
            ligne = {
                "evenement": nom, "agent_id": agent.person_id,
                "deja_vu": "oui" if attendu.get("deja_vu") else "non",
                "attendu": "|".join(attendu["attendu"]),
            }
            try:
                j = await juger(
                    client, agent.person_id, stubs.perception_stub(agent), texte,
                    gravite_deterministe=0.0, evenement_id=nom, jour=10,
                )
            except JugementRefuse as err:
                dernier = client.journal.appels[-1]
                ligne |= {"rendu": "SANS RÉPONSE", "dans_la_plage": "",
                          "erreur": (dernier.erreur or str(err))[:140]}
            else:
                hors_modes = sorted(set(j.modes) - modes_attendus) if modes_attendus else []
                ligne |= {
                    "rendu": j.intensite,
                    "gravite": j.importance_retenue,
                    "valence": j.valence,
                    "modes": "|".join(j.modes),
                    "dans_la_plage": "oui" if j.intensite in plage else "NON",
                    # Un mode hors de l'attendu se SIGNALE ; il ne fait pas échouer. La liste
                    # attendue est un jugement de lecture, pas une vérité.
                    "modes_hors_attendu": "|".join(hors_modes),
                    "rang": rangs[j.intensite],
                    "instance": client.journal.appels[-1].instance,
                }
            lignes.append(ligne)
            _ecrire(sortie / "garde_fou_jugement.csv", lignes)

    return _depouiller(lignes, grille, rangs, marche)


def _depouiller(lignes: list[dict], grille: dict, rangs: dict,
                marche: tuple[str, ...] = BRAS) -> dict:
    rendus = [l for l in lignes if l.get("rendu") and l["rendu"] != "SANS RÉPONSE"]

    def part_hors(population: list[dict]) -> float | None:
        if not population:
            return None
        return round(sum(1 for l in population if l["dans_la_plage"] == "NON") / len(population), 3)

    # ⚠ Les deux populations ne se mélangent JAMAIS. Un taux global additionnerait une prédiction
    # aveugle et une plage écrite après avoir vu les réponses, et ne voudrait rien dire.
    aveugles = [l for l in rendus if l["deja_vu"] == "non"]
    vues = [l for l in rendus if l["deja_vu"] == "oui"]

    par_evenement: dict[str, Counter] = defaultdict(Counter)
    for l in rendus:
        par_evenement[l["evenement"]][l["rendu"]] += 1

    # L'étalement : combien d'échelons distincts, et l'échelon MODAL de chaque texte.
    modal = {e: c.most_common(1)[0][0] for e, c in par_evenement.items()}
    # La part du profil : un texte dont tous les personas s'accordent ne dit rien du profil.
    desaccord = {e: len(c) for e, c in par_evenement.items()}

    # Les bras se séparent-ils, et dans l'ordre visé ?
    #
    # ⚠ ON N'EXIGE UN ÉCART STRICT QUE LÀ OÙ LA GRILLE LE PRÉDIT. Deux bras dont les plages
    # attendues se recouvrent n'ont pas été départagés par l'auteur ; demander à la mesure de
    # les départager reviendrait à tester une hypothèse que personne n'a posée. Partout, en
    # revanche, l'ordre ne doit pas DESCENDRE : un bras déclaré plus grave qui reçoit un échelon
    # plus faible contredit la marche, recouvrement ou non.
    bras = [(b, modal.get(b)) for b in marche if b in modal]
    ordre_tenu, ordre_detail = True, []
    for (gauche, ng), (droite, nd) in zip(bras, bras[1:]):
        if ng is None or nd is None:
            ordre_tenu = False
            continue
        plages_disjointes = not (set(grille[gauche]["attendu"]) & set(grille[droite]["attendu"]))
        if rangs[nd] < rangs[ng]:
            ordre_tenu = False
            ordre_detail.append(f"{droite} ({nd}) est SOUS {gauche} ({ng})")
        elif plages_disjointes and rangs[nd] == rangs[ng]:
            ordre_tenu = False
            ordre_detail.append(
                f"{droite} et {gauche} sont au même échelon ({ng}) alors que leurs plages "
                f"attendues sont disjointes"
            )
        elif not plages_disjointes and rangs[nd] == rangs[ng]:
            ordre_detail.append(
                f"{gauche} et {droite} à égalité ({ng}) — NON départagés par la grille, "
                f"donc non comptés contre la marche"
            )

    return {
        "appels": len(lignes),
        "sans_reponse": len(lignes) - len(rendus),
        "part_hors_plage_aveugle": part_hors(aveugles),
        "part_hors_plage_deja_vue": part_hors(vues),
        "echelons_distincts": len(set(modal.values())),
        "echelon_modal_par_texte": modal,
        "personas_en_desaccord": desaccord,
        "bras_dans_l_ordre_predit": ordre_tenu,
        "marche": list(marche),
        "ordre_detail": ordre_detail,
        "bras": dict(bras),
    }


def _ecrire(chemin: Path, lignes: list[dict]) -> None:
    if not lignes:
        return
    colonnes: list[str] = []
    for l in lignes:
        for k in l:
            if k not in colonnes:
                colonnes.append(k)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colonnes)
        w.writeheader()
        w.writerows(lignes)


def verdict(bilan: dict, seuils: dict) -> tuple[bool, list[str]]:
    """Le garde-fou passe-t-il ? Chaque refus dit ce qu'il faut faire, pas seulement qu'il refuse."""
    motifs: list[str] = []
    ok = True

    if bilan["sans_reponse"]:
        ok = False
        motifs.append(
            f"⛔ {bilan['sans_reponse']} appel(s) sans réponse. Une exposition non jugée n'est "
            f"pas une exposition anodine : elle n'a pas eu lieu. Corriger la passerelle avant "
            f"toute campagne."
        )

    minimum = int(seuils.get("echelons_distincts_min", 3))
    if bilan["echelons_distincts"] < minimum:
        ok = False
        motifs.append(
            f"⛔ {bilan['echelons_distincts']} échelon(s) distinct(s) sur les textes, {minimum} "
            f"demandés. Toutes les durées de vie seraient voisines et l'expérience sur la durée "
            f"ne mesurerait rien. Revoir les textes ou le gabarit, pas le seuil."
        )

    if not bilan["bras_dans_l_ordre_predit"]:
        ok = False
        motifs.append(
            f"⛔ la marche n'est pas tenue : {'; '.join(bilan.get('ordre_detail') or []) or bilan['bras']}. "
            f"C'est l'hypothèse même de l'expérience ; la lancer ainsi coûterait une campagne par "
            f"bras pour l'apprendre."
        )
    elif bilan.get("ordre_detail"):
        motifs.append("⚠ " + " ; ".join(bilan["ordre_detail"]))

    plafond = float(seuils.get("part_hors_plage_max", 0.20))
    part = bilan["part_hors_plage_aveugle"]
    if part is not None and part > plafond:
        ok = False
        motifs.append(
            f"⛔ {part:.0%} des jugements AVEUGLES sortent de leur plage, plafond {plafond:.0%}. "
            f"Ce taux-là compte : la plage a été écrite sans avoir vu une réponse."
        )

    vue = bilan["part_hors_plage_deja_vue"]
    if vue is not None and vue > plafond:
        motifs.append(
            f"⚠ {vue:.0%} des jugements sortent de plages écrites APRÈS avoir vu des réponses. "
            f"Signalé, jamais bloquant : une plage ajustée après coup ne prouve rien dans un "
            f"sens comme dans l'autre."
        )
    return ok, motifs


async def _jouer(a) -> int:
    grille, seuils, marche = charger_grille(Path(a.grille))
    personas = int(a.personas or seuils.get("personas", 4))
    sortie = Path(a.sortie)
    journal = Journal()
    client = ClientEpingle(
        instances=tuple(a.instances), base_url=a.passerelle,
        budget_jetons=a.budget, pause=a.pause, journal=journal,
    )
    print(f"Garde-fou du jugement — {len(grille)} textes × {personas} personas = "
          f"{len(grille) * personas} appels, instances {list(a.instances)}.")
    try:
        bilan = await mesurer(client, grille, personas, sortie, marche)
    except BudgetEpuise as err:
        print(f"⏸ {err}")
        return 2
    finally:
        journal.ecrire(sortie / "garde_fou_passerelle.csv")

    print(json.dumps(bilan, ensure_ascii=False, indent=2))
    ok, motifs = verdict(bilan, seuils)
    for m in motifs:
        print(m)
    print("\n" + ("✅ Le garde-fou passe — la campagne peut être lancée."
                  if ok else "⛔ Le garde-fou REFUSE. La campagne ne part pas."))
    print(f"{journal.resume()}\nDétail : {sortie / 'garde_fou_jugement.csv'}")
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--grille", default=str(GRILLE))
    p.add_argument("--personas", type=int, default=None)
    p.add_argument("--instances", nargs="+", default=list(GROQ))
    p.add_argument("--passerelle", default="http://localhost:8000")
    p.add_argument("--budget", type=int, default=6000)
    p.add_argument("--pause", type=float, default=20.0)
    p.add_argument("--sortie", default="docs/traces/garde_fou_jugement_095")
    return asyncio.run(_jouer(p.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
