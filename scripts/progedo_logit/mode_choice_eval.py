"""mode_choice_eval.py — Métriques du choix modal, partagées par les deux oracles.

Ce module existe pour une raison unique : **le booster LightGBM et le logit multinomial
doivent être jugés par le même code**. Deux tables de métriques recopiées divergent au
premier ajout de clé, et la comparaison publiée devient alors une comparaison de deux
implémentations autant que de deux modèles — le défaut que Hillel (2021) relève dans la
littérature comparative.

Les métriques prennent une **matrice de probabilités**, jamais un modèle : c'est ce qui
permet de les appliquer à un booster, à un logit, et demain à n'importe quel décideur qui
sait produire une distribution sur les quatre classes.

**Les deux familles d'indicateurs, et pourquoi les deux.** Martín-Baos et al. (2023)
montrent que le classement des modèles s'inverse selon la famille :

1. *désagrégée* — exactitude, CEL (entropie croisée sur l'étiquette observée) et
   GMPCA = exp(−CEL), la « moyenne géométrique de la probabilité d'affectation correcte ».
   Le GMPCA se lit comme une probabilité, ce que le log-loss ne fait pas ;
2. *agrégée* — parts modales observées contre prédites, en masse de probabilité et en mode
   élu, et leur L1. C'est l'axe sur lequel notre H0 se joue, et celui où le logit tient tête
   aux arbres.

Ne publier que la première flatterait le booster, ne publier que la seconde ne dirait rien
de la qualité individuelle des probabilités.

Toutes les métriques sont pondérées par le redressement d'enquête (COEP) : non pondérées,
les parts modales ne sont pas représentatives.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, log_loss


def mode_shares(labels: np.ndarray, weights: np.ndarray, n_classes: int) -> list[float]:
    """Parts modales pondérées, depuis des étiquettes dures."""
    total = weights.sum()
    return [float(weights[labels == k].sum() / total) for k in range(n_classes)]


def probability_mass_shares(proba: np.ndarray, weights: np.ndarray) -> list[float]:
    """Parts modales pondérées en **masse de probabilité** — ce que le pipeline consomme."""
    return list((proba * weights[:, None]).sum(axis=0) / weights.sum())


def gmpca(cel: float) -> float:
    """GMPCA = exp(−CEL), moyenne géométrique de la probabilité d'affectation correcte.

    Défini sur l'étiquette **observée** : c'est une mesure de vraisemblance, pas d'accord
    entre deux modèles. Contre une cible molle (les probabilités d'un autre modèle), la CEL
    a un plancher irréductible égal à l'entropie de cette cible, et le GMPCA correspondant
    ne se lit plus comme une probabilité — cf. :func:`scripts.synthesis.bi_oracle.kl_bits`.
    """
    return float(np.exp(-cel))


def evaluate_proba(proba: np.ndarray, y: np.ndarray, w: np.ndarray,
                   classes: list[str]) -> dict:
    """Métriques du split test, pour n'importe quel producteur de probabilités.

    Les parts modales sont rapportées de **deux** façons, parce que les deux ont un
    usage : en masse de probabilité (ce que le pipeline consomme réellement, cf.
    ticket 005 §4) et en mode élu (ce que produirait un argmax). La seconde est
    systématiquement plus contrastée — un classifieur bien calibré exagère les parts
    quand on le durcit.
    """
    hard = proba.argmax(axis=1)
    k = len(classes)

    observed = mode_shares(y, w, k)
    predicted_hard = mode_shares(hard, w, k)
    predicted_mass = probability_mass_shares(proba, w)

    cm = confusion_matrix(y, hard, labels=list(range(k)), sample_weight=w)
    cm_counts = confusion_matrix(y, hard, labels=list(range(k)))

    # Rappel/précision par classe, pondérés. Le vélo (4 % des déplacements) est la
    # classe où la calibration se joue : c'est elle que toute repondération casse.
    per_class = {}
    for i, name in enumerate(classes):
        tp = cm[i, i]
        support = cm[i, :].sum()
        predicted = cm[:, i].sum()
        per_class[name] = {
            "support_share": float(support / cm.sum()),
            "recall": float(tp / support) if support else None,
            "precision": float(tp / predicted) if predicted else None,
        }

    labels = list(range(k))
    cel_weighted = float(log_loss(y, proba, labels=labels, sample_weight=w))
    cel_unweighted = float(log_loss(y, proba, labels=labels))

    return {
        "n_rows": int(len(y)),
        # `log_loss_*` et `cel_*` sont la même grandeur, en nats. Les deux noms sont
        # publiés : le premier est celui de l'historique du dépôt, le second celui de la
        # littérature comparative dont le GMPCA dérive.
        "log_loss_weighted": cel_weighted,
        "log_loss_unweighted": cel_unweighted,
        "cel_weighted": cel_weighted,
        "cel_unweighted": cel_unweighted,
        "gmpca_weighted": gmpca(cel_weighted),
        "gmpca_unweighted": gmpca(cel_unweighted),
        "accuracy_weighted": float(accuracy_score(y, hard, sample_weight=w)),
        "accuracy_unweighted": float(accuracy_score(y, hard)),
        "classes": classes,
        "mode_shares": {
            "observed": observed,
            "predicted_probability_mass": predicted_mass,
            "predicted_argmax": predicted_hard,
            "l1_probability_mass": float(
                np.abs(np.array(predicted_mass) - np.array(observed)).sum()),
            "l1_argmax": float(
                np.abs(np.array(predicted_hard) - np.array(observed)).sum()),
        },
        "per_class": per_class,
        # Lignes = vrai, colonnes = prédit, dans l'ordre de `classes`.
        "confusion_matrix_weighted": [[float(v) for v in row] for row in cm],
        "confusion_matrix_counts": [[int(v) for v in row] for row in cm_counts],
    }


def format_shares(classes: list[str], observed: list[float],
                  mass: list[float], hard: list[float]) -> str:
    lines = [f"  {'mode':10s} {'observé':>9s} {'masse p.':>9s} {'mode élu':>9s}"]
    for i, name in enumerate(classes):
        lines.append(f"  {name:10s} {observed[i]:8.1%} {mass[i]:8.1%} {hard[i]:8.1%}")
    return "\n".join(lines)
