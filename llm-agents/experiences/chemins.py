"""Racine du dépôt, résolue de la même façon sur l'hôte et dans les conteneurs.

`Path(__file__).resolve().parents[N]` ne peut pas convenir des deux côtés : sur l'hôte
ce module vit dans `<dépôt>/llm-agents/experiences/`, mais dans le conteneur
`controller` le dossier `llm-agents` est monté sur `/app` — le module est donc en
`/app/experiences/`, un niveau plus haut. `parents[2]` y rendait `/`, et le décideur
modèle cherchait ses artefacts dans `/scripts/progedo_logit/` : l'expérience refusait
de démarrer avec « policy introuvable » alors que le fichier était bien là
(constaté le 2026-09-08 sur l'expérience Light_GBM).

On remonte donc jusqu'au premier ancêtre qui porte `scripts/synthesis` — la même ancre
que `scripts.synthesis.sources.REPO_ROOT`, vérifiée juste dans les deux environnements.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_ANCRE = Path("scripts") / "synthesis"


@lru_cache(maxsize=1)
def racine_depot() -> Path:
    """Premier ancêtre de ce fichier qui contient `scripts/synthesis`.

    Lève plutôt que de rendre un chemin faux : une racine erronée ne se voit pas, elle
    se transforme en « fichier introuvable » trois appels plus loin.
    """
    ici = Path(__file__).resolve()
    for parent in ici.parents:
        if (parent / _ANCRE).is_dir():
            return parent
    raise RuntimeError(
        f"Racine du dépôt introuvable depuis {ici} : aucun ancêtre ne contient "
        f"{_ANCRE}. Dans un conteneur, vérifier que le dossier `scripts/` du dépôt est "
        "bien monté (volume `./scripts:/app/scripts`)."
    )


__all__ = ["racine_depot"]
