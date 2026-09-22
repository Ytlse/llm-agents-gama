"""Dépouillement de l'étage 1 — ticket 059, lot 3.

CE QUE CE MODULE CALCULE, ET CE QU'IL REFUSE DE CALCULER
--------------------------------------------------------
Trois grandeurs, et deux gardes.

- **L'écart de part modale** entre deux conditions, apparié sur les MÊMES déplacements. Un écart
  calculé sur deux échantillons différents mesurerait la différence entre les échantillons.
- **Le taux d'accord de signe** contre la grille gelée, avec son test binomial. Sur vingt
  prédictions, la barre est à quinze concordances ($p = 0,021$) ; quatorze ne suffisent pas.
- **Le kappa pondéré** sur l'intensité ordinale, publié sans être testé : vingt items ne le
  permettent pas.

La première garde est celle de la **vacuité**. Un mode absent de l'échantillon rend « non
concluant », jamais 0,0. Dans ce dépôt, l'absence de mesure produit le score parfait, et ce motif
a déjà menti : un écart nul et un écart non mesurable s'écrivent tous deux `0.0` si personne n'y
prend garde.

La seconde est celle du **bruit**. Un écart plus petit que le plancher de bruit du décideur n'est
pas un effet. Le plancher se déclare avec le résultat, il ne se tait pas — mesuré à 3,2 % sur
l'agent à mémoire (ticket 095, § 7 bis), et à établir par rejeu à l'identique pour chaque
décideur mesuré ici.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from scripts.analysis.presse.grille import Grille

# Le verdict rendu quand l'effectif ne permet pas de conclure. C'est un RÉSULTAT, pas un échec,
# et il se distingue d'un zéro : `slope_verdict` du ticket 031 a posé ce précédent.
NON_CONCLUANT = "non concluant"

# Nombre minimal de déplacements portant un mode pour que son écart soit interprété. En deçà, un
# seul déplacement qui bascule déplace la part de plus de dix points.
EFFECTIF_MIN_PAR_MODE = 30


@dataclass(frozen=True)
class EcartModal:
    article: str
    mode: str
    part_reference: float | None
    part_condition: float | None
    n_apparies: int
    verdict: str | None = None

    @property
    def ecart(self) -> float | None:
        if self.verdict or self.part_reference is None or self.part_condition is None:
            return None
        return self.part_condition - self.part_reference

    # Pas de propriété `signe` ici, et c'est délibéré : le signe d'un écart n'est pas une
    # propriété de l'écart, il dépend du PLANCHER DE BRUIT du décideur. Le porter sur cette
    # classe reviendrait à en faire un défaut, et un défaut se fait oublier — tout écart non nul
    # prendrait alors un signe, y compris celui d'une décision qui bascule au hasard. Le signe
    # se calcule par `signes_observes`, qui exige ce plancher.


def _part(decisions: list[str], mode: str) -> float | None:
    return decisions.count(mode) / len(decisions) if decisions else None


def ecart_apparie(
    reference: dict[str, str], condition: dict[str, str], *, article: str, mode: str
) -> EcartModal:
    """Écart de part du `mode`, sur les déplacements présents dans LES DEUX conditions.

    `reference` et `condition` associent un identifiant de déplacement au mode choisi.
    L'intersection est prise explicitement : un déplacement qu'une seule condition porte est
    écarté et compté, jamais complété par un défaut.
    """
    communs = sorted(set(reference) & set(condition))
    if len(communs) < EFFECTIF_MIN_PAR_MODE:
        return EcartModal(article, mode, None, None, len(communs), verdict=NON_CONCLUANT)
    ref = [reference[d] for d in communs]
    con = [condition[d] for d in communs]
    return EcartModal(article, mode, _part(ref, mode), _part(con, mode), len(communs))


def signes_observes(ecarts: list[EcartModal], *, plancher_de_bruit: float) -> dict[tuple[str, str], str | None]:
    """Le signe de chaque écart, '0' quand il tient dans le bruit, None quand il n'est pas lisible.

    `plancher_de_bruit` est une PART (0,032 pour 3,2 %), et il est obligatoire : il n'a pas de
    défaut, parce qu'un défaut le ferait oublier. Un écart plus petit que le bruit propre du
    décideur n'est pas un effet, et l'appeler '+' parce qu'il est positif reviendrait à scorer
    du hasard contre une prédiction.
    """
    if plancher_de_bruit < 0:
        raise ValueError("le plancher de bruit est une part positive")
    observes: dict[tuple[str, str], str | None] = {}
    for e in ecarts:
        if e.ecart is None:
            observes[(e.article, e.mode)] = None
            continue
        if abs(e.ecart) <= plancher_de_bruit:
            observes[(e.article, e.mode)] = "0"
        else:
            observes[(e.article, e.mode)] = "+" if e.ecart > 0 else "-"
    return observes


@dataclass(frozen=True)
class AccordDeSigne:
    concordants: int
    lisibles: int
    non_lisibles: int
    # ⚠ `p_binomial` est CONSERVÉ mais vaut désormais toujours `None` : le test binomial a été
    # retiré du chapitre 7 (relecture de l'auteur, 2026-09-21). Le champ reste pour que les
    # rapports déjà écrits se relisent sans exception, et pour qu'on VOIE qu'il est vide plutôt
    # que de croire qu'il n'a jamais existé. Il part à la prochaine reprise du module.
    p_binomial: float | None = None
    # L'intervalle de l'accord de signe, par rééchantillonnage GROUPÉ PAR ÉVÉNEMENT.
    intervalle: tuple[float, float] | None = None
    verdict: str | None = None

    @property
    def taux(self) -> float | None:
        return self.concordants / self.lisibles if self.lisibles else None


# Nombre de rééchantillonnages. 2 000 suffit à stabiliser un intervalle à 95 % au centième sur
# cinq groupes ; monter plus haut coûte du temps sans déplacer la borne.
REECHANTILLONNAGES = 2000
GRAINE_BOOTSTRAP = 59


def intervalle_groupe_par_evenement(
    concordances: list[tuple[str, bool]],
    *,
    tirages: int = REECHANTILLONNAGES,
    graine: int = GRAINE_BOOTSTRAP,
) -> tuple[float, float] | None:
    """Intervalle à 95 % du taux d'accord, en rééchantillonnant les ÉVÉNEMENTS, pas les cellules.

    ⚠ **C'est ce qui remplace le test binomial, et la raison est structurelle.** Le binomial
    supposait vingt tirages indépendants. Ils ne le sont pas : les parts modales d'un même
    événement **somment à un**, si bien qu'un seul comportement — l'agent quitte le vélo pour la
    voiture — produit mécaniquement deux, voire quatre concordances. Compter ces cellules comme
    des observations séparées gonfle l'effectif et rétrécit l'intervalle d'un facteur qui n'a
    aucune contrepartie dans les données.

    L'unité de rééchantillonnage est donc l'**événement** : on tire cinq articles avec remise, et
    chaque article emporte ses quatre cellules en bloc. L'intervalle qui en sort dit ce que
    l'échantillon d'articles permet d'affirmer — et sur cinq articles, il est large. C'est un
    résultat, pas un défaut de la méthode : cinq événements ne portent pas la précision que
    vingt cellules prétendaient donner.

    Rend `None` sous deux événements distincts : un intervalle tiré sur un seul groupe ne
    rééchantillonne rien.
    """
    import random as _random

    par_evenement: dict[str, list[bool]] = {}
    for evenement, concorde in concordances:
        par_evenement.setdefault(evenement, []).append(concorde)
    groupes = [par_evenement[k] for k in sorted(par_evenement)]
    if len(groupes) < 2:
        return None

    alea = _random.Random(graine)
    taux: list[float] = []
    for _ in range(tirages):
        tire = [alea.choice(groupes) for _ in groupes]
        plats = [c for g in tire for c in g]
        if plats:
            taux.append(sum(plats) / len(plats))
    if not taux:
        return None
    taux.sort()
    bas = taux[int(0.025 * (len(taux) - 1))]
    haut = taux[int(0.975 * (len(taux) - 1))]
    return (round(bas, 4), round(haut, 4))


def accord_de_signe(
    grille: Grille, observes: dict[tuple[str, str], str | None]
) -> AccordDeSigne:
    """Le taux d'accord de signe et son intervalle, sur les seules cellules LISIBLES.

    ⚠ Le dénominateur est le nombre de cellules lisibles, pas les vingt de la grille. Compter une
    cellule non mesurable comme une discordance ferait porter à l'effet la faute de l'échantillon ;
    la compter comme une concordance serait pire. Le rapport publie les deux nombres.

    ⚠ **Le test binomial est retiré** (chapitre 7, relecture du 2026-09-21). Il supposait vingt
    cellules indépendantes ; elles ne le sont pas. L'incertitude passe par
    `intervalle_groupe_par_evenement`, qui rééchantillonne les articles et non les cellules.
    """
    lisibles = [
        (c, observes.get((c.article, c.mode)))
        for c in grille.cellules
        if observes.get((c.article, c.mode)) is not None
    ]
    n_non_lisibles = len(grille.cellules) - len(lisibles)
    if not lisibles:
        return AccordDeSigne(0, 0, n_non_lisibles, verdict=NON_CONCLUANT)
    concordants = sum(1 for c, o in lisibles if c.concorde(o))
    return AccordDeSigne(
        concordants=concordants,
        lisibles=len(lisibles),
        non_lisibles=n_non_lisibles,
        p_binomial=None,
        intervalle=intervalle_groupe_par_evenement(
            [(c.article, c.concorde(o)) for c, o in lisibles]
        ),
    )


def kappa_pondere(
    grille: Grille, intensites_observees: dict[tuple[str, str], int | None]
) -> float | str:
    """Kappa de Cohen à pondération quadratique sur l'intensité ordinale 0-3.

    Publié SANS être testé : vingt items ne permettent pas d'en tester la significativité, et un
    intervalle sur vingt cellules dirait surtout la taille de l'échantillon.

    Rend `NON_CONCLUANT` quand moins de dix cellules sont lisibles, ou quand l'une des deux
    séries est constante — un kappa sur une série constante vaut 0 par construction, et ce zéro
    ne dit rien de l'accord.
    """
    paires = [
        (c.intensite, intensites_observees[(c.article, c.mode)])
        for c in grille.cellules
        if intensites_observees.get((c.article, c.mode)) is not None
    ]
    if len(paires) < 10:
        return NON_CONCLUANT
    attendues, observees = zip(*paires, strict=True)
    if len(set(attendues)) == 1 or len(set(observees)) == 1:
        return NON_CONCLUANT

    n = len(paires)
    categories = sorted(set(attendues) | set(observees))
    k = len(categories)
    index = {c: i for i, c in enumerate(categories)}
    poids = [[1 - ((i - j) ** 2) / ((k - 1) ** 2) for j in range(k)] for i in range(k)]

    observe = 0.0
    for a, o in paires:
        observe += poids[index[a]][index[o]]
    observe /= n

    ca, co = Counter(attendues), Counter(observees)
    hasard = 0.0
    for a, na in ca.items():
        for o, no in co.items():
            hasard += poids[index[a]][index[o]] * (na / n) * (no / n)
    if math.isclose(hasard, 1.0):
        return NON_CONCLUANT
    return (observe - hasard) / (1 - hasard)
