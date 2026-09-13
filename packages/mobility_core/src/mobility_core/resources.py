"""resources — où sont les fichiers que ce paquet lit.

Trois familles :

* les **ressources du paquet** (``data/``), livrées avec lui : :func:`data_path` ;
* les **ressources d'accès restreint**, qui vivent au même endroit mais ne sont **jamais**
  redistribuées avec le paquet parce qu'elles reproduisent les microdonnées EMC² Toulouse
  2023 ou leur découpage (convention ProGEDO / ADISP lil-1750) : :func:`restricted_data_path`.
  Un ``pip install mobility-core`` ne les a pas ; le dépôt et les conteneurs, si ;
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
EMC2_DATA_DIR_ENV = "MOBILITY_CORE_EMC2_DATA_DIR"

# Emplacement des ressources dans une arborescence de dépôt, quand le paquet lui-même ne
# les porte pas (cas du `pip install`).
_REPO_DATA_RELATIVE = "mobility_core/src/mobility_core/data"

# Ressources d'accès restreint → commande qui les (re)produit. Cette table est la source de
# vérité du régime de diffusion : elle doit rester alignée sur la liste blanche de
# `MANIFEST.in` et sur `package-data`, ce que `tests/test_packaging_licence.py` vérifie.
#
# Pourquoi celles-ci et pas les autres (ticket 038) : la convention lil-1750 autorise à
# diffuser des RÉSULTATS, pas des DONNÉES. `zf_couronne.json` reproduit le plan de sondage
# de l'enquête (785 zones fines → secteur de tirage → commune) ; `zf_housing_type.json`
# publie l'effectif par zone fine (médiane 12 ménages, 195 zones sous 5) ; `zf_zones.gpkg`
# est la couche SIG de l'enquête. Les autres ressources sont des coefficients de modèles ou
# des agrégats de niveau couronne.
RESTRICTED_RESOURCES: dict[str, str] = {
    "zf_couronne.json": "make communes-couronnes",
    "zf_housing_type.json": "make housing-type",
    "zf_zones.gpkg": "make zones",
    "zf_zones.meta.json": "make zones",
}

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


# ---------------------------------------------------------------------------
# Ressources d'accès restreint — présentes dans le dépôt, jamais dans le paquet.
# ---------------------------------------------------------------------------

def _check_restricted(name: str) -> None:
    """Refuse un nom qui n'est pas déclaré restreint : c'est une faute d'appel."""
    if name not in RESTRICTED_RESOURCES:
        raise ValueError(
            f"« {name} » n'est pas une ressource d'accès restreint. Les ressources livrées "
            f"avec le paquet se lisent par data_path(). Déclarées restreintes : "
            f"{sorted(RESTRICTED_RESOURCES)}.")


def restricted_data_candidates(name: str) -> list[Path]:
    """Emplacements essayés pour une ressource restreinte, dans l'ordre de préférence.

    1. ``$MOBILITY_CORE_EMC2_DATA_DIR`` — le répertoire où le détenteur de la convention
       range ses ressources produites. Il prime sur tout le reste ;
    2. le ``data/`` du paquet — cas du dépôt, d'une installation editable et des conteneurs,
       qui montent ``mobility_core/src/mobility_core`` en volume ;
    3. ``mobility_core/src/mobility_core/data/`` sous une racine de dépôt plausible — cas
       d'un paquet installé à côté d'une copie du dépôt.
    """
    _check_restricted(name)
    candidates: list[Path] = []
    env_dir = os.getenv(EMC2_DATA_DIR_ENV)
    if env_dir:
        candidates.append(Path(env_dir) / name)
    candidates.append(_DATA_DIR / name)
    candidates.extend(root / _REPO_DATA_RELATIVE / name for root in repo_root_candidates())
    # La remontée de répertoires produit des doublons (le paquet EST dans le dépôt, en
    # editable) : les garder rendrait le message d'erreur illisible là où il doit être lu.
    uniques: list[Path] = []
    vus: set[str] = set()
    for candidate in candidates:
        cle = str(candidate)
        if cle not in vus:
            vus.add(cle)
            uniques.append(candidate)
    return uniques


def restricted_data_path(name: str) -> Path:
    """Chemin d'une ressource d'accès restreint : le premier emplacement qui existe.

    Quand aucun n'existe, rend le **premier candidat** plutôt que ``None`` : l'appelant
    lève alors son erreur métier avec un chemin à montrer, et :func:`restricted_resource_hint`
    dit quoi faire. Aucun repli silencieux — une couronne ou un type de logement qui se
    devinerait se lirait ensuite comme une part modale, pas comme un bug.
    """
    candidates = restricted_data_candidates(name)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def restricted_resource_hint(name: str) -> str:
    """Message d'erreur actionnable pour une ressource restreinte introuvable.

    Nomme la commande qui la produit, la variable d'environnement qui la désigne et les
    emplacements essayés — un ``FileNotFoundError`` nu obligerait à relire le code.
    """
    _check_restricted(name)
    essayes = "\n".join(f"    - {c}" for c in restricted_data_candidates(name))
    return (
        f"« {name} » dérive des microdonnées EMC² Toulouse 2023 (ProGEDO / ADISP lil-1750, "
        f"accès restreint) : elle n'est PAS livrée avec le paquet (ticket 038).\n"
        f"  Produisez-la : {RESTRICTED_RESOURCES[name]} — exige les données sous "
        f"« data/PROGEDO 2023/ ».\n"
        f"  Ou désignez le répertoire qui la contient : {EMC2_DATA_DIR_ENV}=/chemin/vers/data\n"
        f"  Emplacements essayés :\n{essayes}"
    )
