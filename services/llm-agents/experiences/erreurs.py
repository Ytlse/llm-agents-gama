"""Rapprochement d'une exécution avec son jeu (ticket 035, R3).

Répond, après coup, à la question qui a manqué le 2026-09-07 : **tous les déplacements du jeu
ont-ils été décidés, et sinon lesquels manquent ?** On lit `decisions.jsonl` (les succès), le jeu
enregistré (la référence des déplacements attendus) et `erreurs.jsonl` (les tentatives échouées
tracées depuis R3), sans rien recalculer ni solliciter le moindre décideur.

Sortie : tentatives par type, déplacements manquants, journées à trous (un déplacement manquant
*suivi* d'un déplacement décidé — la chaîne de véhicule de la journée est alors potentiellement
faussée) et décisions archivées après un trou. Un trou uniquement en fin de journée (exécution
arrêtée en cours de route) est signalé comme manquant mais **pas** comme trou de chaîne.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from loguru import logger

from experiences.archive import F_ERREURS, Execution
from experiences.experience import Experience
from experiences.jeu import Jeu


def _charger_jeu_de_execution(execution: Execution) -> Jeu:
    """Le jeu que cette exécution a rejoué, retrouvé depuis sa configuration figée."""
    exp = Experience.model_validate(execution.config["experience"])
    return Jeu.charger(exp.jeu.chemin())


def _lire_erreurs(dossier: Path) -> list[dict]:
    chemin = dossier / F_ERREURS
    if not chemin.is_file():
        return []
    erreurs: list[dict] = []
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            erreurs.append(json.loads(ligne))
        except ValueError:
            logger.warning(f"[erreurs] ligne illisible ignorée dans {chemin.name}")
    return erreurs


def diagnostiquer(dossier_execution: str | Path) -> dict:
    """Rapproche `decisions.jsonl` du jeu et des `erreurs.jsonl` — dict sérialisable."""
    execution = Execution.ouvrir(dossier_execution)
    jeu = _charger_jeu_de_execution(execution)
    decidees = set(execution._index.keys())  # (person_id, activity_id) archivés
    erreurs = _lire_erreurs(execution.dossier)

    manquants: list[dict] = []
    journees_a_trous: list[str] = []
    decisions_apres_trou = 0
    # Le jeu ordonne déjà les déplacements de chaque personne par (depart_ts, ordinal).
    for person_id, lignes in jeu._par_personne.items():
        presents = [(l, (l.person_id, l.activity_id) in decidees) for l in lignes]
        # Premier trou "interne" : un déplacement manquant qui a un décidé APRÈS lui.
        premier_trou = None
        for i, (_, present) in enumerate(presents):
            if not present and any(p for _, p in presents[i + 1 :]):
                premier_trou = i
                break
        for ligne, present in presents:
            if not present:
                manquants.append(
                    {
                        "person_id": ligne.person_id,
                        "activity_id": ligne.activity_id,
                        "ordinal": ligne.ordinal,
                    }
                )
        if premier_trou is not None:
            journees_a_trous.append(person_id)
            decisions_apres_trou += sum(1 for _, p in presents[premier_trou + 1 :] if p)

    return {
        "execution": execution.nom,
        "etat": execution.etat().get("etat"),
        "jeu": jeu.nom,
        "deplacements_jeu": len(jeu._index),
        "decides": len(decidees & set(jeu._index.keys())),
        "deplacements_manquants": manquants,
        "nb_manquants": len(manquants),
        "journees_a_trous": sorted(journees_a_trous),
        "nb_journees_a_trous": len(journees_a_trous),
        "personnes_touchees": sorted({m["person_id"] for m in manquants}),
        "decisions_apres_trou": decisions_apres_trou,
        "tentatives_par_type": dict(Counter(str(e.get("type")) for e in erreurs)),
        "nb_tentatives": len(erreurs),
    }


def formater(diag: dict) -> str:
    """Rendu texte pour la CLI (`experiences erreurs`)."""
    lignes = [
        f"Exécution {diag['execution']} ({diag['etat']}) — jeu {diag['jeu']}",
        (
            f"  déplacements du jeu : {diag['deplacements_jeu']} · décidés : {diag['decides']} · "
            f"manquants : {diag['nb_manquants']}"
        ),
        f"  tentatives échouées : {diag['nb_tentatives']} {diag['tentatives_par_type'] or '{}'}",
        (
            f"  journées à trous (chaîne potentiellement faussée) : {diag['nb_journees_a_trous']} · "
            f"décisions archivées après un trou : {diag['decisions_apres_trou']}"
        ),
        f"  personnes touchées : {len(diag['personnes_touchees'])}",
    ]
    if diag["deplacements_manquants"]:
        lignes.append("  premiers déplacements manquants :")
        for m in diag["deplacements_manquants"][:10]:
            lignes.append(
                f"    - {m['person_id']} / {m['activity_id']} (ordinal {m['ordinal']})"
            )
        if diag["nb_manquants"] > 10:
            lignes.append(f"    … et {diag['nb_manquants'] - 10} autres")
    else:
        lignes.append("  aucun déplacement manquant : 100 % décidés ✓")
    return "\n".join(lignes)


__all__ = ["diagnostiquer", "formater"]
