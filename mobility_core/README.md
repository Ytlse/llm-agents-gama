# mobility-core

Le domaine de l'enquête EMC² Toulouse 2023, sans dépendance LLM ni infra. Couronnes de
résidence, zones fines, hiérarchie des modes, équipement vélo, type de logement, propensions
individuelles et cadrage de la population enquêtée. Chaque module lit une ressource gelée dans
`mobility_core/data/` et refuse de deviner ce qu'elle ne contient pas : hors couche, on ne
devine pas ; ressource absente, on lève au chargement. Version 0.1.0 (ticket 037).

Le paquet n'importe ni `llm_gateway`, ni `mobility_llm`, ni Redis, Celery, httpx, FastAPI ou
Jinja2 (contrat import-linter `domaine-sans-gateway`). Ses dépendances : PyYAML, loguru ;
extra `geo` : geopandas, shapely, pyproj, numpy.

## Modules

| Module | Une ligne |
|---|---|
| `resources.py` | où sont les fichiers : `data_path()` pour les ressources du paquet, `find_repo_file()` pour les fichiers de référence du dépôt qui ne sont pas recopiés |
| `residence_zone.py` | la couronne de résidence, **lue** par liste de communes (code de zone fine → secteur → couronne), jamais calculée par distance ; hors des 453 communes = « hors périmètre », pas 3ᵉ couronne |
| `zone_resolver.py` | du point aux variables géographiques du choix modal (`od_km` entre centroïdes, `same_zone`, densités, distances au centre) par jointure point-dans-polygone ; extra `geo` ; alarme si plus de 15 % des points tombent hors couche |
| `geo_reference.py` | l'hypercentre de Toulouse, lu dans `feature_spec.json` et non redéclaré ; repli sur la constante recopiée si le spec est absent |
| `mode_hierarchy.py` | le mode principal d'un déplacement multimodal, une fois pour tout le dépôt : métro > tram > téléphérique > bus > train > voiture > deux-roues motorisé > vélo > marche (annexe p. 53 du rapport) |
| `bike_ownership.py` | le vélo du persona en trois étages appris sur l'enquête : combien de vélos dans le ménage, qui les tient, quel type ; déterministe par hachage de l'adresse |
| `equipment_propensity.py` | propension individuelle à un équipement — abonnement TC (`P12 == 6`) et permis (`P7 == 1`) — même vecteur de design à l'entraînement et à l'application |
| `housing_type.py` | le type de logement imputé : loi de la zone fine, levier de taille du ménage (raking), tirage déterministe par adresse ; `None` hors couche ou sans taille |
| `population_reference.py` | le cadrage de la population enquêtée (`population_emc2_2023.yaml`), validé et opposable ; `household_weight` pour comparer une cible ménage à un échantillon de personnes |

## Ressources `data/`

Versionnées (gelées depuis l'enquête par les scripts de `scripts/progedo_logit/`) :

| Fichier | Lu par | Produit par |
|---|---|---|
| `mode_hierarchy_emc2.json` | `mode_hierarchy` | `export_mode_hierarchy.py` |
| `zf_couronne.json` (785 zones fines → secteur, couronne, commune), `commune_couronne.json` (453 communes), `couronne_perimetre.geojson` | `residence_zone` | `export_commune_couronne.py` (`make communes-couronnes`) |
| `bike_ownership.json` | `bike_ownership` | `make bike-ownership` |
| `pt_subscription.json`, `driving_license.json` | `equipment_propensity` | `make equipment-propensity` |
| `terminal_time_emc2.json`, `car_availability_emc2.json` | consommateurs du dépôt (temps terminal, motorisation) | `make terminal-time`, `make car-availability` |

Hors git (`.gitignore`), même statut que les microdonnées d'accès restreint dont elles
dérivent ; à régénérer avec les données PROGEDO sous `data/PROGEDO 2023/` :

| Fichier | Lu par | Commande |
|---|---|---|
| `zf_zones.gpkg`, `zf_zones.meta.json` | `zone_resolver` | `make zones` |
| `zf_housing_type.json` | `housing_type` | `make housing-type` |

`data_path("zf_zones.gpkg")` rend le chemin même si le fichier n'existe pas : c'est
l'appelant qui décide d'en faire une erreur (les `load` le font, avec la commande à lancer
dans le message).

## Fichiers de référence du dépôt

Deux fichiers ne sont pas recopiés dans le paquet, pour ne pas créer une seconde source de
vérité : `scripts/progedo_logit/feature_spec.json` (contrat de features et hypercentre) et
`scripts/data/population/population_emc2_2023.yaml` (cadrage). `find_repo_file` les cherche
dans l'ordre :

1. la variable d'environnement dédiée, chemin complet du fichier : `MODE_CHOICE_FEATURE_SPEC`,
   `POPULATION_EMC2_REFERENCE` ;
2. la racine `MOBILITY_CORE_REPO_ROOT` ;
3. la remontée depuis le répertoire courant (8 niveaux) ;
4. `/app` — le conteneur `controller` monte `scripts/` sous `/app/scripts`.

Rien trouvé → `None`, et chaque module dit ce qu'il fait de l'absence (`geo_reference` se
replie sur sa constante et le trace ; `population_reference` lève avec la liste des chemins
essayés). Les tests posent `MOBILITY_CORE_REPO_ROOT` sur la racine du dépôt.

## Installation et tests

```bash
pip install -e ./mobility_core[geo,test]      # depuis la racine du dépôt ; sans [geo] : zone_resolver et CommunalZones indisponibles
cd mobility_core && pytest                    # ou `make test-mobility` à la racine
```

199 tests collectés le 2026-09-07, 1 sauté : les tests de parité sur la vraie couche de zones
se sautent d'eux-mêmes quand `zf_zones.gpkg` n'a pas été exporté ; les autres tournent hors
ligne sur des ressources versionnées ou synthétiques. Marqueurs : `unit`, `needs_data`.

Historique : `CHANGELOG.md`. Les docstrings de tête de chaque module portent les mesures et
les décisions (pourquoi le bus passe avant le train, pourquoi le vélo n'est pas conditionné
à l'habitat imputé) : les lire avant de modifier une loi.
