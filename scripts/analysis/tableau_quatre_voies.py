#!/usr/bin/env python3
"""Par quelle VOIE le passé atteint une décision — ticket 100, lot 5.

LA QUESTION
-----------
Un agent subit une panne, s'en détourne quinze jours, puis y revient. Des quatre voies par
lesquelles son passé atteint une décision, **laquelle a porté cet effet ?** Le § 3.4 du
manuscrit les nomme, et le dispositif les écrit toutes les quatre dans le prompt :

| Voie | Dans le prompt | Ce qu'elle porte |
|---|---|---|
| `habitudes` | « Mes habitudes » | ce que l'agent fait le plus souvent |
| `connaissances` | « Ce que je sais » | ce qu'il tient pour vrai — les concepts |
| `changements` | « Ce qui a changé récemment » | les souvenirs graves et les croyances écartées |
| `rappel` | trois souvenirs choisis | le rappel vectoriel, tracé dans `trace_rappel.jsonl` |

Ce script dit, **par régime et par rôle**, combien de décisions ont vu l'événement passer par
chacune, et combien ne l'ont vu par aucune.

CE QU'IL NE SAIT PAS FAIRE, ET IL LE DIT
-----------------------------------------
⚠ **L'appariement par le texte échoue pour le vécu.** Mesuré le 2026-09-16 : le texte injecté —
« The engine made a grinding noise and the car stalled » — n'est jamais recopié tel quel. Il
passe en mémoire courte, la réflexion le REFORMULE, et c'est la reformulation qui atteint la
mémoire longue. Chercher le texte littéral ne rend donc rien.

D'où deux recherches, et elles ne valent pas la même chose :

- **exacte** — le texte de l'événement, ou un de ses fragments distinctifs, retrouvé tel quel.
  Elle est fiable quand elle trouve, et muette quand elle ne trouve pas.
- **par mots saillants** — les mots rares du texte, retrouvés ensemble. Elle est indicative,
  et le tableau le dit : une cellule issue de cette voie porte la mention `~`.

Une décision pour laquelle aucune des deux ne conclut sort **vide**, jamais `non`. Écrire
« l'événement n'a pesé sur aucune décision » là où la vérité est « on ne sait pas le dire »
serait un mensonge, et ce dépôt en a déjà produit.

    python scripts/analysis/tableau_quatre_voies.py <run> [--markdown]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from scripts.analysis.lecture_avant_decision import informes_du_run, sous_role
from scripts.analysis.memoire.sources import lire_echanges

# Les en-têtes que `llm/noyau.py` pose dans le prompt. LUS ICI, et il faut qu'ils restent
# alignés : un en-tête renommé ferait sortir une voie à zéro sans qu'aucune erreur n'apparaisse.
# Le test `scripts/tests/test_100_lot5_sorties.py` les compare à ceux de `noyau.py`.
EN_TETES = {
    "habitudes": "Mes habitudes",
    "connaissances": "Ce que je sais",
    "changements": "Ce qui a changé récemment",
}
VOIES = ("habitudes", "connaissances", "changements", "rappel")
CATEGORIE_DECISION = "itinary_multi_agent"

# Mots trop courants pour être saillants. Volontairement court : la liste sert à écarter le
# bruit, pas à faire de la linguistique.
_BANALS = frozenset("""
the and for with that this from they have been were was are but not you your his her its
into than then there here when what which while would could should about after before
""".split())
_MOT = re.compile(r"[A-Za-zÀ-ÿ']{4,}")


def mots_saillants(texte: str, combien: int = 6) -> list[str]:
    """Les mots les plus rares du texte, dans l'ordre d'apparition. Indicatifs, jamais probants."""
    vus: list[str] = []
    for mot in _MOT.findall(texte or ""):
        bas = mot.lower()
        if bas in _BANALS or bas in vus:
            continue
        vus.append(bas)
    # Les plus longs d'abord : « grinding » discrimine, « road » non.
    return sorted(vus, key=len, reverse=True)[:combien]


def _jsonl(chemin: Path) -> list[dict]:
    """Un vrai JSONL, un objet par ligne : `evenements.jsonl`, `chocs.jsonl`, `trace_rappel.jsonl`.

    PAS `llm_exchanges.jsonl` : la passerelle y écrit des objets indentés, qu'une lecture ligne
    à ligne ne décode pas — ou décode de travers, une liste de chaînes rendant des chaînes nues.
    """
    if not chemin.is_file():
        return []
    lignes = []
    for brut in chemin.read_text("utf-8").splitlines():
        brut = brut.strip()
        if not brut:
            continue
        try:
            lignes.append(json.loads(brut))
        except json.JSONDecodeError:
            # Dernière ligne tronquée par un arrêt brutal : sautée, jamais fatale.
            continue
    return lignes


def evenements_du_run(run: Path) -> list[dict]:
    lignes = _jsonl(run / "evenements.jsonl")
    return lignes or _jsonl(run / "chocs.jsonl")


def roles_du_run(run: Path) -> dict[str, str]:
    """`{person_id: rôle}`, lu dans `moves.csv`. Vide si la colonne n'y est pas.

    L'agent est dans `ID Personne`. `Référence` porte le nom du run (`experiences/journal.py`) :
    lue comme identifiant, elle ne rendait aucun rôle, et chaque ligne du tableau sortait `?`.
    """
    chemin = run / "moves.csv"
    if not chemin.is_file():
        return {}
    roles: dict[str, str] = {}
    with chemin.open(encoding="utf-8") as f:
        lecteur = csv.DictReader(f)
        if "Rôle" not in (lecteur.fieldnames or []):
            return {}
        for ligne in lecteur:
            pid = (ligne.get("ID Personne") or ligne.get("person_id") or "").strip()
            role = (ligne.get("Rôle") or "").strip()
            if pid and role:
                roles.setdefault(pid, role)
    return roles


def _bloc(prompt: str, voie: str) -> str:
    """Le contenu du bloc nommé, dans le prompt effectif. Chaîne vide s'il n'y figure pas."""
    debut = prompt.find(EN_TETES[voie])
    if debut < 0:
        return ""
    reste = prompt[debut + len(EN_TETES[voie]):]
    # Le bloc s'arrête au prochain en-tête connu, ou à la fin.
    fins = [reste.find(t) for t in EN_TETES.values() if reste.find(t) > 0]
    return reste[: min(fins)] if fins else reste


def depouiller(run: Path) -> dict:
    evenements = evenements_du_run(run)
    if not evenements:
        raise SystemExit(
            f"❌ ni `evenements.jsonl` ni `chocs.jsonl` dans {run} : aucun événement n'a été "
            f"appliqué. Ce n'est pas un résultat nul, c'est un run sans événement."
        )
    # Ticket 111 : dans un foyer où le lecteur a parlé, le co-résident informé et celui à qui
    # rien n'a été dit ne se mêlent pas — `relais_foyer.jsonl` fait foi.
    informes = informes_du_run(run)
    roles = {pid: sous_role(r, pid, informes) for pid, r in roles_du_run(run).items()}
    textes = {
        str(e.get("person_id")): str(e.get("texte") or e.get("vecu") or "")
        for e in evenements
    }
    canal = {
        str(e.get("person_id")): str(e.get("canal") or "") for e in evenements
    }

    # Les décisions, lues dans les échanges LLM. Seules celles de la catégorie de décision
    # comptent : une réflexion nocturne n'est pas une décision. Le lecteur est celui du rapport
    # de mémoire : le fichier n'est pas du JSONL (cf. `_jsonl`).
    echanges = lire_echanges(run)
    rappels = _jsonl(run / "trace_rappel.jsonl")

    docs_par_agent: dict[str, set[str]] = defaultdict(set)
    for r in rappels:
        pid = str(r.get("person_id") or "")
        for servi in r.get("servis") or []:
            if servi.get("doc_id"):
                docs_par_agent[pid].add(str(servi["doc_id"]))

    compte: dict[tuple[str, str, str], Counter] = defaultdict(Counter)
    decisions: Counter = Counter()
    decisions_lues = 0

    for echange in echanges:
        if str(echange.get("category") or "") != CATEGORIE_DECISION:
            continue
        decisions_lues += 1
        prompt = json.dumps(echange.get("messages") or "", ensure_ascii=False)
        for pid, texte in textes.items():
            # ⚠ L'agent se reconnaît à `agent_id=<id>`, que le gabarit de décision pose en
            # tête de chaque persona. C'est la SEULE attribution fiable, et elle est
            # indispensable pour le canal `lu` : tous les lecteurs d'un même article
            # partagent le même texte, donc chercher le texte seul ne dirait pas qui l'a vu.
            if not texte or f"agent_id={pid}" not in prompt:
                continue
            role = roles.get(pid, "")
            cle_base = (canal.get(pid, ""), role)
            decisions[cle_base] += 1
            saillants = mots_saillants(texte)
            for voie in ("habitudes", "connaissances", "changements"):
                bloc = _bloc(prompt, voie)
                if not bloc:
                    continue
                if texte[:60] and texte[:60] in bloc:
                    compte[(*cle_base, voie)]["exact"] += 1
                elif saillants and sum(m in bloc.lower() for m in saillants) >= 2:
                    compte[(*cle_base, voie)]["saillant"] += 1
            if docs_par_agent.get(pid):
                compte[(*cle_base, "rappel")]["exact"] += 1

    return {"compte": compte, "decisions": decisions, "evenements": len(evenements),
            "roles_connus": bool(roles), "echanges": len(echanges),
            "decisions_lues": decisions_lues}


def _lu(resultat: dict) -> str:
    """Ce qui a été lu. Un tableau sans son effectif ne se distingue pas d'un tableau vide."""
    n, d = resultat["echanges"], resultat["decisions_lues"]
    return (f"Lu : {n} échange{'s' * (n > 1)}, dont {d} décision{'s' * (d > 1)} "
            f"(`{CATEGORIE_DECISION}`), pour {resultat['evenements']} exposition(s).")


def rendre(resultat: dict, markdown: bool = False) -> str:
    compte, decisions = resultat["compte"], resultat["decisions"]
    lignes: list[str] = []
    if not resultat["echanges"]:
        # Rien lu n'est pas « rien trouvé » : sans prompt, aucune décision n'a pu être examinée.
        return (
            "non concluant — aucun échange lu dans `llm_exchanges.jsonl` (absent, vide ou "
            "illisible : `telemetry.exchanges_enabled` était-il actif ?).\n"
            "Ce n'est PAS « l'événement n'a pesé sur rien » : aucune décision n'a été lue.\n"
            + _lu(resultat)
        )
    if not decisions:
        return (
            "non concluant — aucune décision ne porte le texte de l'événement.\n"
            "Ce n'est PAS « l'événement n'a pesé sur rien » : l'appariement par le texte échoue "
            "pour le régime vécu, la réflexion reformule le vécu avant qu'il n'atteigne la "
            "mémoire longue (mesuré le 2026-09-16). Il faudrait un lien explicite posé à la "
            "source, et il n'existe pas.\n" + _lu(resultat)
        )
    sep = "|" if markdown else " "
    lignes.append(f"{'canal':<8}{sep}{'rôle':<14}{sep}{'décisions':>9}{sep}"
                  + sep.join(f"{v:>14}" for v in VOIES))
    if markdown:
        lignes.append("|".join(["---"] * (3 + len(VOIES))))
    for (canal, role), total in sorted(decisions.items()):
        cellules = []
        for voie in VOIES:
            c = compte.get((canal, role, voie)) or Counter()
            exact, saillant = c.get("exact", 0), c.get("saillant", 0)
            if not exact and not saillant:
                cellules.append(f"{'':>14}")  # VIDE, jamais zéro
            elif saillant and not exact:
                cellules.append(f"{f'~{saillant}':>14}")
            elif saillant:
                cellules.append(f"{f'{exact} (~{saillant})':>14}")
            else:
                cellules.append(f"{exact:>14}")
        lignes.append(f"{canal or '?':<8}{sep}{role or '?':<14}{sep}{total:>9}{sep}"
                      + sep.join(cellules))
    # Les décisions où AUCUNE voie n'a été trouvée. Comptées et nommées, parce qu'une ligne
    # de cellules vides se lit trop facilement comme « l'événement n'a pesé sur rien ».
    muettes = sum(
        total for (canal, role), total in decisions.items()
        if not any((compte.get((canal, role, v)) or Counter()) for v in VOIES)
    )
    lignes.append("")
    lignes.append("`~` = appariement par mots saillants, INDICATIF. Une cellule vide n'est pas "
                  "un zéro : c'est une absence de mesure.")
    if muettes:
        lignes.append(
            f"⚠ {muettes} décision(s) où l'événement n'a été retrouvé par AUCUNE voie. Ce n'est "
            f"PAS « l'événement n'a pesé sur rien » : l'appariement par le texte échoue pour le "
            f"régime vécu, la réflexion reformulant le vécu avant qu'il n'atteigne la mémoire "
            f"longue (mesuré le 2026-09-16). Il faudrait un lien explicite posé à la source, et "
            f"il n'existe pas."
        )
    if not resultat["roles_connus"]:
        lignes.append("⚠ `moves.csv` ne porte pas la colonne « Rôle » : run antérieur au ticket "
                      "100, lot 5. Les rôles ne se reconstituent pas après coup.")
    lignes.append(_lu(resultat))
    return "\n".join(lignes)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    p.add_argument("--markdown", action="store_true")
    args = p.parse_args()
    print(rendre(depouiller(args.run), args.markdown))
    return 0


if __name__ == "__main__":
    sys.exit(main())
