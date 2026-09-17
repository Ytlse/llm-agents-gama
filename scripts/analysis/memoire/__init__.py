"""Rapport d'analyse de la mémoire, par persona (ticket 077, lot F).

Un générateur, pas un rapport écrit à la main : le prochain run posera les mêmes
questions. Bibliothèque standard uniquement, SVG en ligne écrit à la main sur le
modèle de ``scripts/synthesis/charts.py`` — le rapport doit s'ouvrir depuis un
``file://``, sans réseau ni dépendance installée.

Quatre modules :

* :mod:`sources` — lecture brute du run (trajets hors rejeu, arrivées, événements
  de mémoire, échanges LLM, métadonnées LTM, journaux, population) ;
* :mod:`mesures` — redondance, contamination, décisivité et entropie, rappels ;
* :mod:`graphiques` — frise des modes, tableau des itinéraires, courbes, barres ;
* :mod:`rapport` — assemblage HTML autonome et CLI.

Deux exécutions sur le même run rendent le même octet : aucun horodatage de
génération n'entre dans le corps, aucun parcours d'ensemble n'est laissé non trié.
"""

__all__ = ["graphiques", "mesures", "rapport", "sources"]
