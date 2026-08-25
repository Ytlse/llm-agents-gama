# Trace — Audit de périmètre de population (ticket 020)

Mesures du 2026-08-24. Instruction des **neuf écarts de base** entre la population
interrogée par l'enquête EMC² CEREMA 2023 et la population simulée. Ticket :
[`docs/tickets/ticket_020_perimetre_population_cerema.md`](../../tickets/ticket_020_perimetre_population_cerema.md).
Synthèse rédigée : [`docs/arch/perimetre-population.md`](../../arch/perimetre-population.md).

## Entrées mesurées

| | |
|---|---|
| Population | `data/population/toulouse_population_1000.json` — 1 021 personas |
| Run | `experiments/current` → `2026-08-21_19_54` — 3 936 trajets, 901 agents |
| Cibles | `scripts/data/population/cerema_values.yaml` |
| Cadrage | `scripts/data/population/population_emc2_2023.yaml` |
| Microdonnées | EMC² Toulouse 2023, ProGEDO/ADISP `lil-1750` (accès restreint) |
| Méthodologie | [Enquêtes Mobilité Certifiées Cerema — méthodologie](https://www.cerema.fr/fr/actualites/enquetes-mobilite-certifiees-cerema-methodologie) (période de référence, jour de la veille) |
| Couche SIG | `EMC2_Toulouse_2023_DTIR_17072023.shp` (champ `NOM_D2`), `..._ZF_26052023.shp` |

## Reproduction

```bash
make communes-couronnes            # exige les données PROGEDO
make audit-perimetre TRACE=docs/traces/2026-08-24_perimetre_population
```

Le mode `--recompute` (ajouté à la ligne de commande, non exposé par `make` car il
exige les microdonnées) recalcule chaque valeur du cadrage depuis les fichiers
d'enquête et la confronte au YAML :

```bash
llm-agents/.venv/bin/python -m scripts.data.population.audit_perimetre --recompute
```

Code de sortie observé : **2** — au moins un axe est « à corriger ». C'est le
comportement voulu ; 0 signifierait que les neuf axes sont conformes.

## Fichiers

| Fichier | Contenu |
|---|---|
| `audit_perimetre.txt` | Rapport lisible des neuf axes, avec le recoupement du cadrage |
| `audit_perimetre.json` | Même contenu, structuré (tables chiffrées incluses) |
| `agents_reclassement.csv` | Les 1 021 personas : domicile, distance au Capitole, commune réelle, couronne métrique, couronne communale, indicateur de reclassement |
| `matrice_confusion_couronnes.csv` | Croisement des deux classements |
| `communes_reclassees.csv` | Les communes concernées par un reclassement, avec les effectifs |
| `parts_modales_par_zone.csv` | Parts modales publiées par couronne sous les deux classements, et l'écart L1 aux cibles |

## Résultats principaux

- **Recoupement du cadrage : toutes les valeurs reproduites.** Les 11 grandeurs de
  cadrage plus les 4 parts de population par couronne se recalculent depuis les
  microdonnées à moins de 0,5 point près. Les parts modales publiées se reproduisent
  aussi : 55,0 % voiture sur les déplacements internes au périmètre, contre 55 dans
  `cerema_values.yaml`.
- **A2, le plus lourd : 249 personas sur 1 021 (24,4 %) changent de couronne** entre le
  classement métrique en production et le classement communal de l'enquête. Dont 66
  que le disque de 8 km baptise « Toulouse » alors qu'ils habitent Blagnac (21),
  Balma (19), Tournefeuille (6), Colomiers (5), Ramonville (5), L'Union (4)…
- **L'erreur flatte le score.** Écart L1 moyen pondéré aux cibles par zone : **47,8
  points sous le classement publié contre 50,7 sous le classement correct**.
- **A4 : 45 personas (4,4 %) habitent hors des 453 communes**, de 48 à 114 km du
  Capitole. Le classement métrique les range en « 3ᵉ couronne » — ils y forment
  **76 % de ce stratum**.
- **A3 : l'écart de 30 % sur la taille de ménage est un artefact de base**, pas un
  défaut de population. 2,71 en moyenne brute par personne contre 2,01 en pondérant
  par `1/taille`, pour une cible de 2,08.
- **A5 (révisé) : la période de référence de l'enquête est vérifiée**, et elle porte bien
  sur la fenêtre — la méthode recueille les *déplacements de la veille*, et les dates de
  référence des microdonnées ne couvrent que 09→12/2022 et 01→02/2023, jours ouvrés
  seulement. Mais l'enquête publie « un jour moyen de semaine » : l'écart n'est donc pas
  saisonnier, il est de **moyennage**. Les jeux gelés moyennent correctement mais sur
  l'année (biais **thermique** de +5,3 °C) ; un run ne moyenne pas du tout (0 % de trajets
  sous la pluie contre 44,7 % de jours pluvieux). Les jours simulés sont thermiquement
  **typiques** de la fenêtre (56ᵉ–81ᵉ centile) et **27,7 % des séquences de 5 jours de la
  période d'enquête sont aussi entièrement sèches** : ce n'est pas un tirage à corriger,
  c'est une limite de variance. Vérifié sur les 76 runs archivés : les 20 derniers sont
  tous à 0 %.
- **A7 : la hiérarchie de mode principal est inversée** par rapport à l'enquête
  (voiture avant transports collectifs, là où l'enquête code 760 de ses 770
  déplacements mixtes en transports collectifs). Divergence latente aujourd'hui —
  aucun itinéraire simulé ne mêle les deux modes — mais 1,4 point de la cible
  transports collectifs est de ce fait structurellement hors d'atteinte.

## Ce que cette trace ne mesure pas

- L'effet d'un passage au classement communal **sur la simulation elle-même**. Le
  classement facture le temps terminal (ticket 013) : le changer demande un bump de
  `version` dans `terminal_time.yaml`, invalide trois caches et exige un run complet.
  Mesuré ici : l'effet sur la **lecture** des résultats, à run constant.
- Le millésime des données d'appariement (ENTD 2008), traité par les tickets 016 et 017.
