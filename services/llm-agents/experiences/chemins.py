"""Racines résolues de la même façon sur l'hôte et dans les conteneurs.

Deux racines, et il faut choisir la bonne : `racine_depot()` pour ce qui vit à côté de
`services/llm-agents/` (`scripts/`, `data/`, `docs/`), `racine_llm_agents()` pour ce qui vit
DEDANS (`text_helper/`, `config/`, `settings.py`). Les confondre marche sur l'hôte, où
l'une est le parent de l'autre, et casse dans le conteneur, où `llm-agents` est monté sur
`/app` : `racine_depot()/"llm-agents"/x` y donne `/app/llm-agents/x`, qui n'existe pas.
C'est ainsi que le gabarit d'option sortait du hachage de `empreinte_gabarit` sans bruit,
et qu'un même prompt portait deux empreintes selon l'endroit d'où l'expérience était
lancée (constaté le 2026-09-11, ticket 045 alerte A2).

--- Racine du dépôt ---

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


@lru_cache(maxsize=1)
def racine_llm_agents() -> Path:
    """Dossier `services/llm-agents/` : `<dépôt>/llm-agents` sur l'hôte, `/app` dans le conteneur.

    C'est le dossier qui contient le paquet `experiences` — donc le parent de ce fichier,
    des deux côtés, sans ancre à chercher. À utiliser pour tout ce qui est livré AVEC le
    code : gabarits de `text_helper/`, `config/`, modules top-level.
    """
    return Path(__file__).resolve().parents[1]


__all__ = ["racine_depot", "racine_llm_agents"]
