"""mode_choice_klr.py — Contrat et évaluateur de la troisième famille (KLR à noyau RBF).

Même partage des rôles que pour le logit : ce module ne sait pas *estimer*, il sait
**relire et faire prédire**. L'estimation demande scikit-learn, la prédiction ne demande
que numpy, et c'est la prédiction qui tourne dans les consommateurs (jeu commun, décideur
d'expérience, conteneur `controller`).

**Ce que cette famille apporte, et pourquoi elle manquait.** Le dépôt tenait les deux
extrêmes d'un axe : un booster exact et non lisse, un logit lisse et moins exact. La
régression logistique à noyau est non linéaire comme le premier et à réponse lisse comme le
second — c'est la famille que Martín-Baos et al. (2023) désignent comme le meilleur
compromis entre exactitude prédictive et plausibilité comportementale. Elle sert donc deux
fois : un troisième chiffre au niveau 3 de l'ablation, et un **second arbitre** pour le bloc
C du score à deux oracles, où un arbitre unique ne se réfute pas.

**Nyström, et pourquoi il n'y a pas le choix.** Un noyau exact exigerait la matrice de Gram
du train : 39 203², soit 1,5 milliard d'entrées. On projette donc sur `m` points d'appui
(500 à 2 000), tirés **par ménage** — `m` ménages distincts, un trajet tiré dans chacun. Un
tirage par trajet concentrerait les appuis sur les gros foyers, qui portent jusqu'à 38
déplacements, et l'espace des variables serait décrit là où quelques ménages habitent.

**Les coefficients duaux, et pourquoi l'artefact est petit.** L'estimation ajuste un logit
multinomial sur la carte de Nyström `Φ = K(Z,L)·W`, où `W = U Λ^{-1/2}` est la racine
inverse de la matrice de Gram des appuis. Prédire ne demande pas `W` : les deux matrices se
replient, et

    softmax(Φ·βᵀ + α) = softmax(K(Z,L)·(W·βᵀ) + α) = softmax(K(Z,L)·B + α)

avec `B` de forme `m × 4`. L'artefact porte donc les appuis, `B`, `γ` et les constantes —
`m × 54` flottants, soit 1,2 Mo à `m = 1 000`, là où transporter `W` en aurait fait 20. Le
repliement est **exact** (vérifié à 1e-9 avant écriture, mesuré à 3e-14), et `B` est
exactement ce qu'on appelle des coefficients duaux : un poids par point d'appui et par
alternative.

**La matrice de dessin n'est pas refaite.** Elle vient de `mode_choice_logit`, par la même
fonction que le logit : un noyau RBF n'a de sens que sur des variables centrées-réduites, et
les manquants y sont matérialisés par les mêmes indicatrices déclarées. Refaire l'encodage
ici aurait produit un décalage silencieux — les probabilités seraient restées plausibles.

**Confidentialité.** Les points d'appui sont `m` **lignes réelles d'enquête**, centrées et
réduites. L'artefact reste donc sous `scripts/progedo_logit/*.json`, gitignoré comme les
deux autres : la source PROGEDO est d'accès restreint (lil-1750) et ne se republie pas par
ricochet dans un fichier de modèle.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from scripts.progedo_logit.mode_choice_logit import (
    design_matrix_from_contract,
    softmax,
)

# Format de l'artefact de la troisième famille. Décrit la *structure* du JSON,
# indépendamment de `spec_version` qui décrit le contrat de variables. Un consommateur
# refuse un format qu'il ne connaît pas plutôt que d'en interpréter les clés au hasard.
KLR_FORMAT = "klr_mode_choice_policy"
KLR_FORMAT_VERSION = 1

#: Taille des blocs de lignes pour l'évaluation du noyau. Le produit `n × m` n'est jamais
#: alloué en entier : à 2 000 appuis, prédire 500 000 lignes d'un coup demanderait 8 Go. Le
#: découpage ne change aucune valeur (vérifié par test), il borne la mémoire du décideur.
KERNEL_CHUNK = 4096

#: Plancher relatif du spectre de la matrice de Gram des appuis. Deux appuis presque
#: confondus rendent `K_LL` numériquement singulière ; la composante correspondante est
#: **écartée et comptée** plutôt qu'inversée, ce qui produirait des coefficients énormes et
#: un modèle qui explose hors du train.
EIGENVALUE_FLOOR = 1e-10


def squared_distances(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Distances au carré entre chaque ligne de `A` et chaque ligne de `B`.

    Forme développée `‖a‖² + ‖b‖² − 2a·b` : une boucle explicite sur 39 203 × 2 000 paires
    coûterait des minutes là où le produit matriciel coûte une fraction de seconde. Les
    valeurs sont ramenées à zéro par le bas — l'annulation catastrophique peut rendre
    −1e-13 sur la diagonale, et une racine négative n'existe pas.
    """
    a2 = np.einsum("ij,ij->i", A, A)[:, None]
    b2 = np.einsum("ij,ij->i", B, B)[None, :]
    return np.maximum(a2 + b2 - 2.0 * (A @ B.T), 0.0)


def rbf_kernel(Z: np.ndarray, landmarks: np.ndarray, gamma: float,
               chunk: int = KERNEL_CHUNK) -> np.ndarray:
    """`K[i, j] = exp(−γ‖z_i − l_j‖²)`, par blocs de lignes."""
    Z = np.asarray(Z, dtype="float64")
    landmarks = np.asarray(landmarks, dtype="float64")
    out = np.empty((len(Z), len(landmarks)), dtype="float64")
    for start in range(0, len(Z), chunk):
        stop = min(start + chunk, len(Z))
        out[start:stop] = np.exp(-gamma * squared_distances(Z[start:stop], landmarks))
    return out


def nystrom_basis(gram: np.ndarray,
                  floor: float = EIGENVALUE_FLOOR) -> tuple[np.ndarray, dict]:
    """Racine inverse `W = U Λ^{-1/2}` de la matrice de Gram des appuis, et son diagnostic.

    `eigh` plutôt que `svd` : `K_LL` est symétrique définie positive par construction, et
    `eigh` le sait. Le diagnostic (rang effectif, composantes écartées, conditionnement)
    remonte dans l'artefact : un rang inférieur au `m` annoncé décrit un modèle plus pauvre
    que son étiquette, et c'est le genre de fait qu'on ne remarque pas après coup.
    """
    values, vectors = np.linalg.eigh(np.asarray(gram, dtype="float64"))
    largest = float(values.max())
    kept = values > floor * largest
    rank = int(kept.sum())
    if rank == 0:
        raise ValueError(
            "[ALARME] Matrice de Gram des appuis dégénérée : aucune valeur propre au-dessus "
            f"du plancher {floor:g} × {largest:.3e}. Noyau inexploitable, rien n'est publié.")
    basis = vectors[:, kept] / np.sqrt(values[kept])
    diagnostic = {
        "m": int(len(values)),
        "rank": rank,
        "dropped_eigencomponents": int(len(values) - rank),
        "eigenvalue_floor": floor,
        "eigenvalue_max": largest,
        "eigenvalue_min_kept": float(values[kept].min()),
        "condition_number": float(largest / values[kept].min()),
    }
    return basis, diagnostic


class KLRPredictor:
    """Évaluateur de la KLR-Nyström, sans scikit-learn.

    Expose délibérément la même surface que le booster LightGBM et que le logit
    (``predict``, ``feature_name``) : les trois familles empruntent alors **le même chemin
    de prédiction** sur le jeu commun, ce qui est la condition pour que leurs parquets
    soient comparables (règle K9 de `specs/ticket_043/klr-troisieme-famille.md`).
    """

    def __init__(self, artefact: dict):
        self.artefact = artefact
        klr = artefact["klr"]
        self.contract = klr["design"]
        self.gamma = float(klr["kernel"]["gamma"])
        self.landmarks = np.asarray(klr["landmarks"], dtype="float64")
        self.dual_coef = np.asarray(klr["dual_coef"], dtype="float64")
        self.intercept = np.asarray(klr["intercept"], dtype="float64")
        self.classes = list(artefact["target"]["classes"])
        self.names = [f["name"] for f in artefact["features"]]

        n_columns = len(self.contract["design_columns"])
        if self.landmarks.ndim != 2 or self.landmarks.shape[1] != n_columns:
            raise ValueError(
                f"Points d'appui de forme {self.landmarks.shape}, attendu (m, {n_columns}) "
                "— un appui décrit dans un autre espace que la matrice de dessin.")
        if self.dual_coef.shape != (len(self.landmarks), len(self.classes)):
            raise ValueError(
                f"Coefficients duaux de forme {self.dual_coef.shape}, attendu "
                f"({len(self.landmarks)}, {len(self.classes)}).")
        if self.intercept.shape != (len(self.classes),):
            raise ValueError(
                f"Constantes de forme {self.intercept.shape}, attendu ({len(self.classes)},).")
        if not self.gamma > 0:
            raise ValueError(f"Largeur de noyau invalide : γ = {self.gamma}.")

    # ``num_iteration`` n'a pas de sens ici : accepté et ignoré, pour que l'appelant n'ait
    # pas à savoir quelle famille il tient.
    def predict(self, matrix: Any, num_iteration: Any = None) -> np.ndarray:
        """Probabilités sur les quatre classes, dans l'ordre du spec."""
        design = design_matrix_from_contract(
            matrix, self.artefact["features"], self.contract)
        scores = np.empty((len(design), len(self.classes)), dtype="float64")
        for start in range(0, len(design), KERNEL_CHUNK):
            stop = min(start + KERNEL_CHUNK, len(design))
            kernel = np.exp(-self.gamma * squared_distances(
                design[start:stop], self.landmarks))
            scores[start:stop] = kernel @ self.dual_coef + self.intercept
        return softmax(scores)

    def feature_name(self) -> list[str]:
        """Variables attendues, dans l'ordre du spec — même contrat que les deux autres."""
        return list(self.names)
