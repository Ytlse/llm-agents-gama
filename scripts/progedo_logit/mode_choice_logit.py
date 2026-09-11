"""mode_choice_logit.py — Contrat et évaluateur du second oracle (logit multinomial).

Ce module ne sait pas *estimer* un logit : il sait le **relire et le faire prédire**. La
séparation est volontaire — l'estimation demande scikit-learn, la prédiction ne demande que
numpy, et c'est la prédiction qui tourne dans les consommateurs (page de synthèse, décideur
d'expérience, conteneur `controller`).

**Pourquoi un artefact de coefficients et non un modèle sérialisé.** Un `pickle` de
scikit-learn se périme à la version suivante de la bibliothèque et ne se relit pas dans un
diff. Un logit multinomial n'est que `softmax(Zβ + α)` : les coefficients, les constantes
par alternative et le contrat de construction de `Z` suffisent, se relisent et se vérifient à
la main : l'artefact est autoportant au même sens que celui du booster. Il n'est pas versionné
pour autant — `scripts/progedo_logit/*.json` est gitignoré, sauf `feature_spec.json` — et se
régénère par `make logit`.

**La matrice de dessin, et le seul piège de ce module.** L'entrée n'est pas la ligne brute :
c'est la matrice **déjà encodée par le même `encode_features` que le booster** (modalité →
code entier du spec, booléen → 0/1, numérique → flottant, manquant → NaN). C'est ce qui rend
la parité d'information vraie par construction : les deux oracles voient exactement les mêmes
valeurs, et une seule fonction d'encodage existe. Ce module ne fait que **dilater** cette
matrice en indicatrices, centrer-réduire les numériques et matérialiser les manquants.

**Les manquants, déclarés plutôt que subis.** Le booster route les NaN nativement ; un logit
ne peut pas. Trois règles, écrites dans l'artefact et appliquées ici :

- catégorielle manquante ou hors spec → modalité `__missing__` (jamais la modalité modale) ;
- booléen manquant → 0, **plus** son indicatrice de manquant à 1 ;
- numérique manquante → la moyenne pondérée du train (soit 0 après centrage), **plus** son
  indicatrice de manquant à 1.

Les indicatrices sont ce qui distingue « absent » de « moyen » : sans elles, l'imputation
affirmerait une valeur que la donnée ne porte pas.
"""

from __future__ import annotations

from typing import Any

import numpy as np

# Format de l'artefact du second oracle. Décrit la *structure* du JSON, indépendamment de
# `spec_version` qui décrit le contrat de variables. Un consommateur doit refuser un format
# qu'il ne connaît pas plutôt que d'en interpréter les clés au hasard.
LOGIT_FORMAT = "mnl_mode_choice_policy"
LOGIT_FORMAT_VERSION = 1

#: Modalité de repli explicite d'une catégorielle absente ou hors spec.
MISSING_CATEGORY = "__missing__"


def design_columns(spec: dict, missing_indicators: list[str]) -> list[str]:
    """Colonnes de la matrice de dessin, dans un ordre **imposé par le spec**.

    Une catégorielle à *n* modalités donne *n − 1* indicatrices : la première modalité du
    spec est la **référence** (son effet est absorbé par la constante). Sans référence
    écartée, la matrice est singulière et les coefficients ne sont plus interprétables un à
    un, même si la régularisation empêche l'estimation d'échouer.
    """
    columns: list[str] = []
    for feature in spec["features"]:
        name, kind = feature["name"], feature["kind"]
        if kind == "categorical":
            modalities = list(feature["categories"]) + [MISSING_CATEGORY]
            columns += [f"{name}={m}" for m in modalities[1:]]
        else:
            columns.append(name)
        if name in missing_indicators:
            columns.append(f"{name}__missing")
    return columns


def design_matrix(encoded: Any, artefact: dict) -> np.ndarray:
    """Matrice de dessin `Z`, depuis la matrice encodée du booster.

    ``encoded`` est un ``DataFrame`` à une colonne par variable du spec, dans l'ordre du
    spec — la sortie de ``fit_mode_choice_policy.encode_features``. Aucune colonne n'est
    déduite des valeurs présentes : tout vient de l'artefact, sans quoi deux lots de
    prédiction produiraient deux matrices différentes.
    """
    logit = artefact["logit"]
    stats = logit["standardization"]
    indicators = set(logit["missing_indicators"])
    n = len(encoded)
    blocks: dict[str, np.ndarray] = {}

    for feature in artefact["features"]:
        name, kind = feature["name"], feature["kind"]
        values = np.asarray(encoded[name], dtype="float64")
        missing = np.isnan(values)
        if kind == "categorical":
            modalities = list(feature["categories"]) + [MISSING_CATEGORY]
            codes = np.where(missing, len(modalities) - 1, values).astype("int64")
            # Une modalité hors spec est déjà NaN à l'encodage ; un code hors bornes ne
            # peut donc venir que d'un artefact incohérent avec son spec.
            if codes.min() < 0 or codes.max() >= len(modalities):
                raise ValueError(
                    f"Code de modalité hors bornes pour {name} : "
                    f"{codes.min()}..{codes.max()} pour {len(modalities)} modalités.")
            for index, modality in enumerate(modalities):
                if index == 0:
                    continue                      # modalité de référence
                blocks[f"{name}={modality}"] = (codes == index).astype("float64")
        else:
            column = np.where(missing, 0.0, values)
            if name in stats:
                mean, std = stats[name]["mean"], stats[name]["std"]
                column = np.where(missing, 0.0, (column - mean) / std)
            blocks[name] = column
        if name in indicators:
            blocks[f"{name}__missing"] = missing.astype("float64")

    order = logit["design_columns"]
    unknown = [c for c in order if c not in blocks]
    if unknown:
        raise ValueError(f"Colonnes de dessin introuvables : {unknown[:5]}")
    matrix = np.empty((n, len(order)), dtype="float64")
    for position, column in enumerate(order):
        matrix[:, position] = blocks[column]
    return matrix


def softmax(scores: np.ndarray) -> np.ndarray:
    """Softmax ligne à ligne, stabilisée par retrait du maximum."""
    shifted = scores - scores.max(axis=1, keepdims=True)
    exponentials = np.exp(shifted)
    return exponentials / exponentials.sum(axis=1, keepdims=True)


class LogitPredictor:
    """Évaluateur du logit multinomial, sans scikit-learn.

    Expose délibérément la même surface que le booster LightGBM (``predict``,
    ``feature_name``) : les consommateurs du jeu commun appellent alors **le même chemin de
    prédiction** pour les deux oracles, ce qui est la condition pour que leurs deux parquets
    soient comparables (règle R7 de `specs/score_composite_deux_oracles.md`).
    """

    def __init__(self, artefact: dict):
        self.artefact = artefact
        logit = artefact["logit"]
        self.coef = np.asarray(logit["coef"], dtype="float64")
        self.intercept = np.asarray(logit["intercept"], dtype="float64")
        self.classes = list(artefact["target"]["classes"])
        self.names = [f["name"] for f in artefact["features"]]
        expected = len(logit["design_columns"])
        if self.coef.shape != (len(self.classes), expected):
            raise ValueError(
                f"Coefficients de forme {self.coef.shape}, attendu "
                f"({len(self.classes)}, {expected}).")
        if self.intercept.shape != (len(self.classes),):
            raise ValueError(
                f"Constantes de forme {self.intercept.shape}, attendu ({len(self.classes)},).")

    # ``num_iteration`` n'a pas de sens pour un logit : accepté et ignoré, pour que
    # l'appelant n'ait pas à savoir quel oracle il tient.
    def predict(self, matrix: Any, num_iteration: Any = None) -> np.ndarray:
        """Probabilités sur les quatre classes, dans l'ordre du spec."""
        design = design_matrix(matrix, self.artefact)
        return softmax(design @ self.coef.T + self.intercept)

    def feature_name(self) -> list[str]:
        """Variables attendues, dans l'ordre du spec — même contrat que le booster."""
        return list(self.names)
