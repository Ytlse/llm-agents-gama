"""Statut d'une expérience — `actif`, `archivee`, `invalide`.

Spec : `specs/hygiene-prompts-et-plateforme-experiences.md` §3.2 et §5.

Ce module ne SUPPRIME jamais rien et ne déplace aucun fichier. Un statut est un marqueur
posé à côté des données (`data/experiences/<exp>/statut.json`) : les exécutions, les traces,
les `scores.json` et les empreintes restent où ils sont, lisibles et vérifiables. Ce qui
change, c'est la visibilité par défaut au registre et au tableau de bord — et, pour
`invalide`, le fait que la mesure ne doit plus être citée sans sa raison.

Trois statuts, et rien d'autre :

- ``actif``    — défaut en l'absence de fichier. Aucun marqueur à écrire pour ce cas.
- ``archivee`` — sans intérêt courant (définition jamais exécutée, exécution avortée,
  doublon de nommage). Les données restent, la ligne sort du listing par défaut.
- ``invalide`` — la mesure est fautive pour une raison nommée (typiquement un gabarit
  invalidé, cf. `PromptManager` / `_invalidation`). Le chiffre reste lisible ; c'est son
  statut qui dit de ne pas s'y fier.

Chaque transition est empilée dans ``historique`` : réactiver une expérience ne fait pas
disparaître la trace de son archivage, et l'on peut toujours répondre « pourquoi cette
expérience a-t-elle été écartée, quand, et par qui ».
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ACTIF = "actif"
ARCHIVEE = "archivee"
INVALIDE = "invalide"
STATUTS = (ACTIF, ARCHIVEE, INVALIDE)

F_STATUT = "statut.json"

# Statuts masqués par défaut au registre et au tableau de bord.
MASQUES_PAR_DEFAUT = (ARCHIVEE, INVALIDE)


class StatutInvalide(ValueError):
    """Statut inconnu, ou expérience introuvable."""


def _maintenant() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def defaut() -> dict[str, Any]:
    """Statut d'une expérience sans marqueur : active, visible, sans motif."""
    return {
        "statut": ACTIF,
        "motif": None,
        "le": None,
        "reference": None,
        "donnees": "conservees",
        "visible_par_defaut": True,
        "historique": [],
    }


def lire(dossier_experience: str | Path) -> dict[str, Any]:
    """Statut d'une expérience. Ne lève jamais : un marqueur illisible vaut `actif`.

    Un registre doit rester listable même si un `statut.json` a été édité à la main de
    travers — le pire résultat acceptable est « on affiche tout », pas « on n'affiche rien ».
    """
    p = Path(dossier_experience) / F_STATUT
    base = defaut()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return base
    if not isinstance(data, dict) or data.get("statut") not in STATUTS:
        return base
    base.update({k: v for k, v in data.items() if k in base})
    base["historique"] = list(data.get("historique") or [])
    base["visible_par_defaut"] = bool(
        data.get("visible_par_defaut", base["statut"] == ACTIF)
    )
    return base


def est_masquee(st: dict[str, Any]) -> bool:
    """Vrai si la ligne doit sortir du listing par défaut."""
    return st.get("statut") in MASQUES_PAR_DEFAUT and not st.get("visible_par_defaut")


def ecrire(
    dossier_experience: str | Path,
    statut: str,
    *,
    motif: str | None = None,
    reference: str | None = None,
    visible_par_defaut: bool | None = None,
) -> dict[str, Any]:
    """Pose un statut. Écriture atomique, historique empilé, aucune donnée touchée.

    `motif` est OBLIGATOIRE pour `archivee` et `invalide` : un marqueur sans raison est
    un marqueur qu'on ne saura pas relire dans six mois.
    """
    dossier = Path(dossier_experience)
    if not (dossier / "experience.yaml").is_file():
        raise StatutInvalide(f"pas une expérience : {dossier}")
    if statut not in STATUTS:
        raise StatutInvalide(
            f"statut {statut!r} inconnu (attendus : {', '.join(STATUTS)})"
        )
    if statut != ACTIF and not (motif or "").strip():
        raise StatutInvalide(f"un statut {statut!r} exige un motif")

    avant = lire(dossier)
    corps = {
        "statut": statut,
        "motif": (motif or None) if statut != ACTIF else None,
        "le": _maintenant(),
        "reference": reference,
        # Dit noir sur blanc ce que le marqueur ne fait pas : rien n'est supprimé.
        "donnees": "conservees",
        "visible_par_defaut": (
            (statut == ACTIF) if visible_par_defaut is None else bool(visible_par_defaut)
        ),
        "historique": [
            *avant["historique"],
            {
                "de": avant["statut"],
                "vers": statut,
                "le": _maintenant(),
                "motif": motif,
            },
        ],
    }
    cible = dossier / F_STATUT
    tmp = dossier / f"{F_STATUT}.tmp"
    tmp.write_text(
        json.dumps(corps, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    os.replace(tmp, cible)
    return corps


def statuts_par_experience(racine: str | Path) -> dict[str, dict[str, Any]]:
    """Statut de chaque expérience d'une racine, indexé par nom de dossier."""
    r = Path(racine)
    if not r.is_dir():
        return {}
    return {
        p.name: lire(p) for p in sorted(r.iterdir()) if (p / "experience.yaml").is_file()
    }


__all__ = [
    "ACTIF",
    "ARCHIVEE",
    "INVALIDE",
    "STATUTS",
    "F_STATUT",
    "StatutInvalide",
    "defaut",
    "ecrire",
    "est_masquee",
    "lire",
    "statuts_par_experience",
]
