"""Ce que le paquet a le droit d'emporter (ticket 038).

`mobility_core` est installable, donc redistribuable, et il embarque des ressources
dérivées de l'enquête EMC² Toulouse 2023 dont les microdonnées sont d'accès restreint
(convention ProGEDO / ADISP lil-1750). Les conventions de ce type autorisent à diffuser des
**résultats**, pas des **données** : une ressource qui reproduit le plan de sondage de
l'enquête, ou qui publie des effectifs de cellule trop faibles, est de la donnée.

Ce test ne juge rien : il vérifie que la liste `package-data` de `pyproject.toml` dit
explicitement ce qu'elle emporte, et qu'aucune ressource classée restreinte n'y figure.

Deux régressions le font échouer, et ce sont les deux qui se sont déjà produites :

- **le retour d'un glob** (`data/*.json`). Un glob ramasse tout fichier présent sur le
  disque au moment du build, y compris ceux que `.gitignore` exclut : c'est ainsi que
  `zf_housing_type.json`, ignoré par git, se retrouvait dans `build/lib/` puis dans le
  wheel. Le `.gitignore` ne protège pas le paquet ;
- **l'ajout d'une ressource restreinte** à la liste, par commodité de déploiement.

Deux niveaux : les tests de déclaration lisent `pyproject.toml` et `MANIFEST.in` (rapides,
hors ligne) ; le test d'artefact construit réellement le sdist et le wheel et regarde ce
qu'ils contiennent. Le second existe parce que le premier ne suffit pas — la liste explicite
de `package-data` était correcte alors que les DEUX artefacts emportaient encore les
ressources restreintes, par `include-package-data` (True par défaut, il s'unit à la liste)
pour le wheel et par l'absence de `MANIFEST.in` pour le sdist. Ce qui fait foi, c'est
l'archive, pas la déclaration.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"

# Ressources dérivées des microdonnées ou du découpage de l'enquête : jamais dans le paquet.
# `zf_couronne` reproduit le plan de sondage (785 zones fines → secteur → commune) ;
# `zf_housing_type` publie l'effectif par zone fine (médiane 12 ménages, 195 zones sous 5) ;
# `zf_zones` est la couche SIG de l'enquête elle-même.
RESSOURCES_RESTREINTES = (
    "zf_couronne.json",
    "zf_housing_type.json",
    "zf_zones.gpkg",
    "zf_zones.meta.json",
)


@pytest.fixture(scope="module")
def package_data() -> list[str]:
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    entries = config["tool"]["setuptools"]["package-data"]["mobility_core"]
    assert entries, "package-data vide : le paquet n'emporterait aucune ressource"
    return list(entries)


def test_aucun_glob_dans_package_data(package_data: list[str]) -> None:
    """Un glob rendrait le contenu du wheel dépendant de ce qui traîne sur le disque."""
    globs = [entry for entry in package_data if any(c in entry for c in "*?[")]
    assert not globs, (
        "package-data doit lister les ressources une par une (ticket 038) ; "
        f"motifs trouvés : {globs}. Un glob emporte les ressources d'accès restreint "
        "présentes sur le disque de build, que `.gitignore` n'écarte pas du paquet."
    )


@pytest.mark.parametrize("ressource", RESSOURCES_RESTREINTES)
def test_ressource_restreinte_absente_du_paquet(package_data: list[str], ressource: str) -> None:
    """Ajouter une de ces ressources au paquet, c'est redistribuer l'enquête."""
    porteurs = [entry for entry in package_data if entry.endswith(ressource)]
    assert not porteurs, (
        f"`{ressource}` dérive des microdonnées ProGEDO lil-1750 (accès restreint) et ne "
        f"peut pas être redistribuée avec le paquet ; entrée fautive : {porteurs}. "
        "Elle se produit localement (`make communes-couronnes`, `make housing-type`, "
        "`make zones`) et se lit hors paquet."
    )


def test_ressources_declarees_existent_sur_le_disque(package_data: list[str]) -> None:
    """Une entrée qui ne correspond à aucun fichier est une ressource perdue en silence."""
    racine = PYPROJECT.parent / "src" / "mobility_core"
    manquantes = [entry for entry in package_data if not (racine / entry).exists()]
    assert not manquantes, (
        f"déclarées dans package-data mais absentes de {racine} : {manquantes}"
    )


# ---------------------------------------------------------------------------
# Ce qui fait foi : l'artefact construit.
# ---------------------------------------------------------------------------

def _noms_data(chemin: Path) -> set[str]:
    """Noms de fichiers sous `data/` dans un sdist (.tar.gz) ou un wheel (.whl)."""
    if chemin.suffix == ".whl":
        import zipfile
        membres = zipfile.ZipFile(chemin).namelist()
    else:
        import tarfile
        membres = tarfile.open(chemin).getnames()
    return {m.split("/data/")[-1] for m in membres if "/data/" in m}


@pytest.fixture(scope="module")
def artefacts(tmp_path_factory: pytest.TempPathFactory) -> list[Path]:
    """Construit sdist et wheel dans un répertoire jetable. Saute si `build` manque."""
    pytest.importorskip("build", reason="`pip install build` pour vérifier les artefacts")
    import subprocess
    import sys

    sortie = tmp_path_factory.mktemp("dist")
    projet = PYPROJECT.parent
    # `--outdir` hors du projet : on ne veut pas qu'un `build/` résiduel du dépôt participe.
    process = subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(sortie), str(projet)],
        capture_output=True, text=True,
    )
    assert process.returncode == 0, (
        f"construction du paquet en échec (code {process.returncode})\n{process.stderr[-2000:]}"
    )
    construits = sorted(sortie.glob("*.tar.gz")) + sorted(sortie.glob("*.whl"))
    assert len(construits) == 2, f"attendu un sdist et un wheel, obtenu : {construits}"
    return construits


@pytest.mark.slow
def test_artefacts_sans_ressource_restreinte(artefacts: list[Path]) -> None:
    """Le sdist ET le wheel : aucune des deux archives ne redistribue l'enquête."""
    fautes = {
        artefact.name: sorted(_noms_data(artefact) & set(RESSOURCES_RESTREINTES))
        for artefact in artefacts
    }
    coupables = {nom: ressources for nom, ressources in fautes.items() if ressources}
    assert not coupables, (
        f"ressources d'accès restreint présentes dans les artefacts : {coupables}. "
        "Le wheel se règle par `package-data` + `include-package-data = false`, le sdist "
        "par la liste blanche de `MANIFEST.in` — les deux, pas l'un des deux."
    )
