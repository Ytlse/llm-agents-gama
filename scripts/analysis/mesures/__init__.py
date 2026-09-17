"""Mesures par jour simulé d'un run de mémoire — ticket 093.

Un seul calcul, deux sorties : les CSV de `ecriture` et les séries Prometheus du contrôleur
sortent d'ici, donc ils ne peuvent pas diverger. Le CSV fait foi ; Grafana est un instrument de
bord dont l'abscisse est le temps RÉEL et non le temps simulé.
"""

from scripts.analysis.mesures.calcul import Mesures, calculer

__all__ = ["Mesures", "calculer"]
