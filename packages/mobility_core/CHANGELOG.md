# Changelog — mobility-core

Format : `## [version] - AAAA-MM-JJ`, entrées les plus récentes en tête. Le ton est celui de
l'usage. Les fichiers touchés sont dans git.

## [Non publié]

**Licence déclarée** (ticket 038) : `Apache-2.0` pour le code, plus un `NOTICE` qui pose que
cette licence **ne couvre pas** les ressources de `data/` — dérivées de l'EMC² Toulouse 2023,
convention ProGEDO / ADISP lil-1750, usage de recherche et citation de l'enquête.

**Le paquet n'emporte plus les ressources d'accès restreint.** `package-data` liste ses huit
ressources une par une au lieu d'un glob `data/*.json`, `include-package-data` passe à
`false` — à `true` il s'unit à la liste au lieu de la restreindre — et un `MANIFEST.in` en
liste blanche gouverne le sdist, que `pyproject.toml` n'atteint pas. Sortent des deux
archives : `zf_couronne.json` (plan de sondage), `zf_housing_type.json` (effectif par zone
fine), `zf_zones.gpkg`, `zf_zones.meta.json`. `tests/test_packaging_licence.py` construit
sdist et wheel et vérifie leur contenu — la déclaration ne fait pas foi, l'artefact oui.

**Nouveau point d'entrée `resources.restricted_data_path(nom)`**, avec
`restricted_data_candidates`, `restricted_resource_hint` et la table `RESTRICTED_RESOURCES`.
Ordre de recherche : `$MOBILITY_CORE_EMC2_DATA_DIR`, le `data/` du paquet, puis une racine de
dépôt plausible. `residence_zone`, `housing_type` et `zone_resolver` y passent ; introuvable,
ils lèvent en nommant la ressource, la commande `make`, la variable et les chemins essayés.

Aucun effet à l'exécution : les conteneurs montent `src/mobility_core/` et le venv est en
editable. Un `pip install mobility-core` n'a plus `zf_couronne.json` — `CouronneTable.load()`
le dit alors explicitement.

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
