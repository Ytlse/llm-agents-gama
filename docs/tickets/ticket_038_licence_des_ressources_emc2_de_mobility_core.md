# Ticket 038 — Licence des ressources de `mobility_core` : ce que le paquet a le droit de redistribuer

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
>
> **Décision de l'auteur du dépôt (2026-09-07)** : à trancher plus tard. Le gateway est sous
> Apache-2.0 (ticket 037) ; la question ne se pose que pour les données du domaine, dont la
> licence prime sur celle du code.

## Constat

`mobility_core` devient un paquet installable, donc redistribuable, et il embarque dans
`mobility_core/data/` des ressources dérivées de l'enquête ménages-déplacements EMC² Toulouse
2023. Leur `meta.source` cite toutes les microdonnées **ProGEDO / ADISP lil-1750**, d'accès
restreint (convention nominative). Le code est libre ; les données qu'il lit ne le sont pas
forcément, et un paquet publié sur un index les emporterait avec lui.

| Ressource versionnée | Ce que c'est | Origine déclarée dans `meta` |
|---|---|---|
| `bike_ownership.json` | trois étages du modèle d'équipement vélo (lois agrégées) | EMC² 2023, fichiers standards ménages/personnes, lil-1750 |
| `car_availability_emc2.json` | disponibilité voiture par strate | EMC² 2023, variable M6, lil-1750 |
| `driving_license.json`, `pt_subscription.json` | propensions permis et abonnement TC | EMC² 2023, `PENQ = 1`, pondération `COEP`, lil-1750 |
| `zf_housing_type.json` (hors git, `make housing-type`) | loi du type de logement par zone fine et taille de ménage | EMC² 2023, lil-1750 |
| `terminal_time_emc2.json` | lois de temps terminal par couronne | EMC² 2023, fichier trajets, lil-1750 |
| `commune_couronne.json`, `zf_couronne.json` | listes de communes et de zones fines par couronne | découpage de l'enquête, lil-1750 |
| `mode_hierarchy_emc2.json` | ordre de priorité des modes | rapport publié AUAT/CEREMA (p. 53), contrôlé sur les microdonnées |
| `couronne_perimetre.geojson` | polygone des 453 communes par couronne | géométrie communale (Admin Express, Licence Ouverte) + liste de l'enquête |
| `zf_zones.gpkg` (hors git, `make zones`) | couche des 785 zones fines avec densités | shapefile `EMC2_Toulouse_2023_ZF` |

Deux régimes coexistent : ce qui reproduit des **microdonnées ou leur découpage** (listes de
zones fines, lois conditionnées à la zone fine) et ce qui **agrège** ou vient d'un **rapport
publié** (hiérarchie des modes, tables de niveau couronne). La convention lil-1750 dit ce qu'on
peut publier ; personne ne l'a relue avec cette question.

## À trancher

1. Pour chaque ressource : redistribuable telle quelle, redistribuable en agrégé seulement, ou
   à exclure du paquet (chargement depuis un chemin externe, comme `zf_zones.gpkg` aujourd'hui).
2. La licence du paquet `mobility_core` lui-même : Apache-2.0 comme le gateway pour le code, et
   une mention distincte pour `data/` (par exemple « données dérivées de l'EMC² Toulouse 2023,
   usage limité à la recherche, convention ProGEDO lil-1750 »).
3. `mobility_llm` : les prompts citent des communes et des noms de réseaux, rien de l'enquête ;
   Apache-2.0 sans réserve sauf avis contraire.
4. Le dépôt racine porte déjà un fichier `LICENSE` : vérifier sa cohérence avec les trois paquets.

## Pistes

- Relire la convention ProGEDO lil-1750 (clauses de diffusion des résultats) et les conditions
  de la publication AUAT/CEREMA.
- Demander à l'ADISP si des lois agrégées par zone fine (785 unités, parfois peu d'observations)
  relèvent de la diffusion de résultats ou de la reproduction de données.
- Si exclusion : `mobility_core.resources` sait déjà chercher une ressource hors paquet
  (`MOBILITY_CORE_REPO_ROOT`, variables dédiées) ; le mécanisme existe, il manque la décision.

## Effort

Décision juridique, pas technique : une demi-journée de relecture et un échange avec l'ADISP ;
la mise en œuvre (mention dans `data/README`, exclusion éventuelle) tient en une heure.
