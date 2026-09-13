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

## Fait le 2026-09-12 — le paquet ne redistribue plus les ressources restreintes

Sans rien préjuger des questions ci-dessous, l'architecture **A** (exclusion du paquet, la
ressource se lit hors paquet) est appliquée aux ressources qui reproduisent l'enquête.
`zf_couronne.json`, `zf_housing_type.json`, `zf_zones.gpkg` et `zf_zones.meta.json` ne sont
plus ni dans le sdist ni dans le wheel.

Il fallait **trois** réglages, chacun suffisant à tout laisser passer :

| Réglage | Ce qu'il laissait passer |
|---|---|
| `package-data = ["data/*.json", "data/*.geojson"]` | un glob emporte ce qui est sur le **disque de build**, pas ce que git suit — `zf_housing_type.json`, pourtant `.gitignore`, était déjà dans `build/lib/` |
| `include-package-data` (défaut `true` depuis setuptools 61) | il **s'unit** à `package-data` au lieu de la restreindre : la liste explicite seule ne changeait rien |
| absence de `MANIFEST.in` | le sdist ignore `pyproject.toml` ; il emportait tout `data/` même après les deux corrections ci-dessus |

Constat méthodologique : la liste explicite **et** `include-package-data = false` laissaient
encore fuir le sdist. Seule la construction effective des deux archives l'a montré — d'où
`mobility_core/tests/test_packaging_licence.py`, qui construit sdist et wheel et regarde
dedans, en plus de relire les déclarations.

**Sans effet à l'exécution** : les conteneurs montent `mobility_core/src/mobility_core/` en
volume (`docker-compose.yml`) et le venv local est en editable. `zf_couronne.json` reste
versionné — c'est sa redistribution qui s'arrête.

**Fait le même jour, à la suite :**

- **`zf_couronne.json` déversionnée** (`git rm --cached` + `.gitignore`). Ce n'est pas un
  agrégat mais le plan de sondage, et le dépôt a vocation à accompagner une publication.
  Elle reste sur le disque des postes qui l'ont produite ; un clone neuf lance
  `make communes-couronnes`.
- **`resources.restricted_data_path()`** et ses compagnons `restricted_data_candidates`,
  `restricted_resource_hint`, `RESTRICTED_RESOURCES`. Ordre : `$MOBILITY_CORE_EMC2_DATA_DIR`,
  le `data/` du paquet, une racine de dépôt plausible. `residence_zone`, `housing_type` et
  `zone_resolver` y passent ; l'erreur nomme la ressource, la commande, la variable et les
  chemins essayés.
- **`LICENSE` + `NOTICE` + `license = "Apache-2.0"`** (PEP 639) pour `mobility_core` et
  `mobility_llm`, qui n'en avaient aucun. Le `NOTICE` de `mobility_core` pose explicitement
  que la licence du code **ne couvre pas** `data/`.

Vérifié : 206 tests `mobility_core`, 158 `mobility_llm`, plus `test_enrich_residence_zone`,
`test_parite_modes`, `test_perimeter_filter`, `test_terminal_time`. Les deux paquets
construisent un sdist et un wheel portant `License-Expression: Apache-2.0` et leurs deux
fichiers de licence.

**Reste à faire :**

1. Le point 1 de « À trancher » ci-dessous : l'avis de l'ADISP sur `commune_couronne.json`
   et `couronne_perimetre.geojson`, les deux seules ressources livrées dont le statut n'est
   pas acquis. Tout le reste du paquet est soit un coefficient de modèle, soit un agrégat de
   niveau couronne, soit du rapport publié.
2. Vérifier la cohérence du `LICENSE` de la racine du dépôt avec les trois paquets (point 4).

---

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
