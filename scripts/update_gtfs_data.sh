#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# RECETTE REMPLACÉE LE 2026-09-04 — ce script ne fait plus rien, et il le dit.
#
# Il produisait `routes.shp`, `stops.shp` et `trip_info.json` en lançant les blocs
# `__main__` de `llm-agents/inputs/gtfs/{reader,gama}.py`, qui lisent EN DUR le seul
# `data/gtfs/tisseo_gtfs`. C'est ce chemin qui a laissé `trip_info.json` cinq mois en
# retard et à un seul réseau : 39 343 courses Tisséo et AUCUNE en `route_type=2`,
# pendant que les couches, elles, portaient les trois réseaux et traçaient 34 lignes
# de TER et 68 gares où aucun train ne roulerait.
#
# Le laisser exécutable réintroduirait le défaut en une commande, et en silence :
# il écraserait les trois fichiers par des versions mono-réseau, sans un contrôle.
# Il refuse donc, plutôt que de servir un réseau amputé.
#
#     make gama-trip-info     # les couches PUIS les courses, les trois réseaux,
#                             # avec cinq contrôles bloquants
#     make gama-layers        # les couches seules
#     make test-gama-includes # le test de cohérence couches / courses
#
# Voir `docs/setup/data-pipeline.md` § « Préparer les données GTFS pour GAMA » et
# `scripts/data/gama/export_trip_info.py`.
# ─────────────────────────────────────────────────────────────────────────────

cat >&2 <<'FIN'
Ce script est remplacé depuis le 2026-09-04 et ne s'exécute plus.

Il ne connaissait qu'un réseau (data/gtfs/tisseo_gtfs, en dur) et écrasait les trois
fichiers de GAMA/CityTransport/includes/ par des versions mono-réseau, sans contrôle :
c'est ainsi que trip_info.json a passé cinq mois sans une seule course de TER, alors
que les couches en traçaient 34 lignes.

À la place :

    make gama-trip-info      # couches + courses, les trois réseaux, contrôles bloquants
    make gama-layers         # les couches seules
    make test-gama-includes  # le test de cohérence couches / courses

Documentation : docs/setup/data-pipeline.md § « Préparer les données GTFS pour GAMA ».
FIN
exit 2
