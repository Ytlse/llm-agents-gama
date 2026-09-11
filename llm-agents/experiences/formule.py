"""Formules de score composite — définition versionnée, empreinte canonique.

Spec : `specs/scoring_composite_experiences.md` (R2, R3, R4, R7, R19, R20).

Une formule pondère **7 dimensions** (`DIMENSIONS`). `length_penalty` n'y figure
pas : elle reste hors composite (R2), et le ``Scorer`` du moteur la voit absente,
donc à poids nul. L'empreinte `formule_sha256` est **canonique** (R3) : elle ne
dépend ni de l'ordre des clés ni de l'écriture des flottants, seulement des
valeurs des 7 dimensions.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

# Ordre canonique des dimensions pondérables du composite (R2). Fixe : il définit
# l'ordre de sérialisation de l'empreinte, donc il ne doit jamais changer.
DIMENSIONS: tuple[str, ...] = (
    "global",
    "absent_penalty",
    "age",
    "occupation",
    "genre",
    "motif",
    "distance",
)

_REGISTRE_DEFAUT = Path(__file__).parent / "formules" / "reference.yaml"


def _poids_canoniques(poids: dict) -> dict:
    """Complète les 7 dimensions (absentes → 0.0) et force le type flottant."""
    return {d: float(poids.get(d, 0.0)) for d in DIMENSIONS}


def empreinte(poids: dict) -> str:
    """SHA-256 canonique des poids (R3).

    Sérialise les 7 dimensions dans l'ordre fixe de ``DIMENSIONS``, chaque poids
    normalisé en flottant via ``.12g`` : ``0.5`` et ``0.50`` donnent la même
    chaîne, l'ordre des clés d'origine n'entre pas.
    """
    canon = _poids_canoniques(poids)
    texte = ";".join(f"{d}={format(canon[d], '.12g')}" for d in DIMENSIONS)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def _valider(nom: str, poids: dict) -> None:
    """Refuse une formule invalide (R19) — jamais évaluée comme du code."""
    inconnues = set(poids) - set(DIMENSIONS)
    if inconnues:
        raise ValueError(
            f"formule {nom!r} : dimension(s) hors des 7 admises : {sorted(inconnues)}"
        )
    for dim, valeur in poids.items():
        try:
            f = float(valeur)
        except (TypeError, ValueError):
            raise ValueError(
                f"formule {nom!r} : poids non numérique pour {dim!r} : {valeur!r}"
            )
        if f < 0:
            raise ValueError(f"formule {nom!r} : poids négatif pour {dim!r} : {f}")


@dataclass(frozen=True)
class Formule:
    """Une formule nommée : ses 7 poids et son empreinte canonique."""

    nom: str
    poids: dict
    sha256: str

    def poids_scorer(self) -> dict:
        """Poids à passer au ``Scorer`` (copie défensive)."""
        return dict(self.poids)


class RegistreFormules:
    """Le registre chargé : accès par nom, par SHA (R20), et formule de référence."""

    def __init__(self, formules: list[Formule], reference_nom: str):
        self._par_nom = {f.nom: f for f in formules}
        # Dernière gagnante en cas de SHA identique (deux formules aux mêmes poids) :
        # sans importance, elles portent la même définition.
        self._par_sha = {f.sha256: f for f in formules}
        self._reference_nom = reference_nom

    @property
    def reference(self) -> Formule:
        """La formule de référence courante (R4, R7)."""
        return self._par_nom[self._reference_nom]

    def par_nom(self, nom: str) -> Formule | None:
        return self._par_nom.get(nom)

    def resoudre(self, sha256: str) -> Formule | None:
        """Retrouve une formule par son empreinte, y compris une ancienne (R20)."""
        return self._par_sha.get(sha256)

    def toutes(self) -> list[Formule]:
        return list(self._par_nom.values())


def charger(chemin: Path | str | None = None) -> RegistreFormules:
    """Charge le registre, valide, et impose une seule référence (R4, R19).

    Refus bruyant (exception) si : nom manquant ou en double, dimension inconnue,
    poids non numérique ou négatif, ou nombre de ``reference: true`` différent de 1.
    """
    chemin = Path(chemin) if chemin else _REGISTRE_DEFAUT
    data = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    entrees = data.get("formules") or []
    formules: list[Formule] = []
    references: list[str] = []
    noms: set[str] = set()
    for entree in entrees:
        nom = entree.get("nom")
        if not nom:
            raise ValueError(f"formule sans nom dans {chemin}")
        if nom in noms:
            raise ValueError(f"formule en double dans {chemin} : {nom!r}")
        noms.add(nom)
        poids = entree.get("poids") or {}
        _valider(nom, poids)
        canon = _poids_canoniques(poids)
        formules.append(Formule(nom=nom, poids=canon, sha256=empreinte(canon)))
        if entree.get("reference"):
            references.append(nom)
    if len(references) != 1:
        raise ValueError(
            f"{chemin} doit déclarer exactement une formule reference:true, "
            f"{len(references)} trouvée(s) : {references or '—'}"
        )
    return RegistreFormules(formules, references[0])


__all__ = ["DIMENSIONS", "Formule", "RegistreFormules", "charger", "empreinte"]
