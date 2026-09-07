"""resources — où sont les fichiers que ce paquet lit.

Deux familles :

* les **ressources du paquet** (``data/``), livrées avec lui : :func:`data_path` ;
* les **fichiers de référence du dépôt** (``scripts/data/population/…``,
  ``scripts/progedo_logit/feature_spec.json``), qui ne sont pas recopiés dans le paquet
  pour ne pas créer une seconde source de vérité : :func:`find_repo_file`.

Un fichier du dépôt se cherche, dans l'ordre : la variable d'environnement dédiée, la
racine désignée par ``MOBILITY_CORE_REPO_ROOT``, la remontée depuis le répertoire courant,
puis ``/app`` (le conteneur ``controller`` monte ``scripts/`` sous ``/app/scripts``).
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT_ENV = "MOBILITY_CORE_REPO_ROOT"
_DATA_DIR = Path(__file__).resolve().parent / "data"
_CONTAINER_ROOT = Path("/app")
_MAX_UPWARD_STEPS = 8


def data_dir() -> Path:
    """Répertoire des ressources livrées avec le paquet."""
    return _DATA_DIR


def data_path(name: str) -> Path:
    """Chemin d'une ressource du paquet (``bike_ownership.json``, ``zf_zones.gpkg``…).

    Le fichier peut ne pas exister (``zf_zones.gpkg`` est produit par ``make zones``) :
    l'appelant décide s'il en fait une erreur.
    """
    return _DATA_DIR / name


def repo_root_candidates() -> list[Path]:
    """Racines de dépôt plausibles, dans l'ordre de préférence."""
    roots: list[Path] = []
    env_root = os.getenv(REPO_ROOT_ENV)
    if env_root:
        roots.append(Path(env_root))
    here = Path.cwd().resolve()
    roots.append(here)
    roots.extend(here.parents[:_MAX_UPWARD_STEPS])
    roots.append(_CONTAINER_ROOT)
    return roots


def find_repo_file(relative: str, env_var: str | None = None) -> Path | None:
    """Premier fichier du dépôt trouvé à ``relative`` depuis une racine plausible.

    ``env_var`` désigne une variable d'environnement qui, si elle est définie, prime sur
    toute recherche (chemin complet du fichier). Rend ``None`` si rien n'existe.
    """
    if env_var:
        override = os.getenv(env_var)
        if override:
            candidate = Path(override)
            return candidate.resolve() if candidate.exists() else None
    for root in repo_root_candidates():
        candidate = root / relative
        if candidate.exists():
            return candidate.resolve()
    return None


def repo_file_candidates(relative: str) -> list[Path]:
    """Les chemins essayés par :func:`find_repo_file`, pour un message d'erreur utile."""
    return [root / relative for root in repo_root_candidates()]
