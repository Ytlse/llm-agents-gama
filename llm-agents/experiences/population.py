"""Chargement d'une population pour la plateforme — nom, empreinte, sceau (spec 01 J1, spec 06 E2).

Toute population est admissible (EF-02) : un dossier scellé (`MANIFEST.yaml` + `population.json`)
comme un fichier JSON nu. Le résultat dit laquelle des deux situations s'appliquait. Les personnes
sont construites par le **même** chargeur que la simulation (`EqasimJSONPopulationLoader`), donc
avec les mêmes heures programmées : c'est ce qui rend le nombre de déplacements attendus dérivable
à l'identique des deux côtés (J2, E22).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from models import Person


def sha256_fichier(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


@dataclass
class InfoPopulation:
    nom: str
    chemin: str                 # fichier population.json effectivement lu
    sha256: str                 # empreinte d'IDENTITÉ : MANIFEST.yaml si scellée, sinon le fichier
    fichier_sha256: str         # empreinte du population.json dans les deux cas
    scellee: bool
    n: int
    manifest: Optional[dict] = field(default=None, repr=False)

    def as_dict(self) -> dict:
        return {"nom": self.nom, "chemin": self.chemin, "sha256": self.sha256,
                "fichier_sha256": self.fichier_sha256, "scellee": self.scellee, "n": self.n}


def resoudre_population(chemin: str | Path) -> tuple[Path, Optional[Path]]:
    """(population.json, MANIFEST.yaml ou None) depuis un dossier scellé ou un fichier."""
    p = Path(chemin)
    if p.is_dir():
        manifest = p / "MANIFEST.yaml"
        fichier = p / "population.json"
        if not fichier.exists():
            raise FileNotFoundError(f"population introuvable : {fichier}")
        return fichier, (manifest if manifest.exists() else None)
    if not p.exists():
        raise FileNotFoundError(f"population introuvable : {p}")
    manifest = p.parent / "MANIFEST.yaml"
    return p, (manifest if manifest.exists() else None)


def info_population(chemin: str | Path) -> InfoPopulation:
    fichier, manifest_path = resoudre_population(chemin)
    fichier_sha = sha256_fichier(fichier)
    manifest = None
    scellee = False
    if manifest_path is not None:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        attendu = ((manifest.get("population") or {}).get("sha256"))
        scellee = bool(attendu)
        if attendu and attendu != fichier_sha:
            raise ValueError(
                f"population scellée altérée : MANIFEST annonce {attendu[:12]}…, le fichier fait {fichier_sha[:12]}… ({fichier})"
            )
    nom = (manifest or {}).get("nom") or (fichier.parent.name if fichier.name == "population.json" else fichier.stem)
    with open(fichier, encoding="utf-8") as f:
        n = len(json.load(f))
    return InfoPopulation(
        nom=str(nom), chemin=str(fichier),
        sha256=sha256_fichier(manifest_path) if scellee else fichier_sha,
        fichier_sha256=fichier_sha, scellee=scellee, n=n, manifest=manifest,
    )


def charger_population(chemin: str | Path) -> tuple[list[Person], InfoPopulation]:
    """Personnes + info. Même chargeur que la simulation, sans filtre de périmètre ni de taille."""
    from inputs.population.eqasim_loader import EqasimJSONPopulationLoader

    info = info_population(chemin)
    with open(info.chemin, encoding="utf-8") as f:
        brut = json.load(f)
    if brut and "name" in (brut[0].get("identity") or {}) and "traits_json" in brut[0]["identity"] and brut[0]["identity"].get("activities") and "id" in brut[0]["identity"]["activities"][0] and "state" in brut[0] and brut[0]["identity"]["activities"][0].get("start_time") is not None:
        # Format eqasim (celui des populations scellées) — le chargeur pose scheduled_start_time.
        pass
    loader = EqasimJSONPopulationLoader()
    personnes = loader.load_population_from_data(brut, max_size=len(brut), bbox=None)
    return personnes, info
