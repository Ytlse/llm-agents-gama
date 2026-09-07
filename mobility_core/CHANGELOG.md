# Changelog — mobility-core

Format : `## [version] - AAAA-MM-JJ`, entrées les plus récentes en tête. Le ton est celui de
l'usage. Les fichiers touchés sont dans git.

## [0.1.0] - 2026-09-07

Première version installable du domaine de l'enquête EMC² Toulouse, extrait de
`llm_module.core` (ticket 037). Le paquet ne dépend d'aucun LLM, d'aucune infra : ni
`llm_gateway`, ni Redis, ni Celery, ni httpx, ni FastAPI, ni Jinja2 (contrat import-linter
`domaine-sans-gateway`).

**Ce que le paquet apporte, à qui s'en sert :**

- **Couronnes de résidence** lues par liste de communes (`residence_zone`), **zones fines**
  et variables géographiques du choix modal (`zone_resolver`, extra `geo`), **hypercentre**
  lu dans le contrat de features et jamais redéclaré (`geo_reference`).
- **Hiérarchie des modes** de l'enquête (`mode_hierarchy`) : un déplacement multimodal reçoit
  un mode principal, le même dans tout le dépôt.
- **Équipement et logement imputés, déterministes par hachage** : vélo en trois étages
  (`bike_ownership`), abonnement TC et permis (`equipment_propensity`), type de logement
  conditionné à la zone et à la taille du ménage (`housing_type`).
- **Cadrage de la population enquêtée** (`population_reference`) : périmètre, couronnes,
  cibles ménage, pondération `household_weight`.

**Avant :** ces modules remontaient de deux niveaux vers la racine du dépôt et lisaient
`/app/scripts/...` en dur pour trouver `feature_spec.json` ou `population_emc2_2023.yaml`.
**Après :** `mobility_core.resources.find_repo_file` cherche dans l'ordre la variable
d'environnement dédiée (`MODE_CHOICE_FEATURE_SPEC`, `POPULATION_EMC2_REFERENCE`), la racine
`MOBILITY_CORE_REPO_ROOT`, la remontée depuis le répertoire courant, puis `/app`. Les
ressources gelées de l'enquête sont livrées dans `mobility_core/data/` ; celles dérivées
des microdonnées d'accès restreint (`zf_zones.gpkg`, `zf_zones.meta.json`,
`zf_housing_type.json`) restent hors git et se régénèrent par `make zones` et
`make housing-type`.

Tests : 199 collectés le 2026-09-07 (1 sauté sans la couche de zones), marqueur
`needs_data` déclaré pour les tests qui exigent une ressource produite hors git.
