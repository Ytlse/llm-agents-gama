# Ticket 039 — Organisation du dépôt : bibliothèques, services, données, résultats

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
>
> **Décision de l'auteur du dépôt (2026-09-07)** : consigner le constat et la vision ; le plan
> détaillé sera l'objet de ce ticket quand il sera ouvert. Rien ne bouge d'ici là.

## Constat (mesuré le 2026-09-07)

Le dépôt mêle à la racine des bibliothèques, des applications, des données, des résultats et
des restes. Tailles sur disque, tout compris (caches, venv, données hors git) :

| Répertoire | Taille | Nature | Remarque |
|---|---|---|---|
| `eqasim-toulouse/` | 16 Go | service + données de synthèse | contexte Docker propre |
| `experiments/` | 10 Go | résultats de runs | hors git ; registre du ticket 035 |
| `data/` | 6,5 Go | entrées, caches, exports, données Prometheus | pointeurs DVC présents ; `cache/` reconstructible |
| `llm-agents/` | 4,1 Go | application contrôleur + venv + caches | le venv du projet vit ici |
| `scripts/` | 560 Mo | outils, notebooks, données | des données et des sorties dedans |
| `gama/`, `GAMA/` | 565 Mo | modèle de simulation | deux casses pour un même sujet |
| `prompt_calibration/` | 457 Mo | dépôt git **imbriqué**, autonome, déployé sur une VM | 0 fichier suivi par le dépôt parent |
| `otp-toulouse/` | 415 Mo | service de routage transit | contexte Docker propre |
| `docs/` | 196 Mo | documentation + pages de synthèse archivées + article | les pages HTML pèsent |
| `llm_gateway/`, `mobility_core/`, `mobility_llm/` | légers | bibliothèques (ticket 037) | layout src, tests, CI, docs |
| `llm_module/` | léger | coquille de compatibilité dépréciée | retrait en 2.0 |
| `grafana/` | 252 Ko | dashboards et alertes comme code | à côté de `docker-compose.yml` |
| `notebooks/`, `scripts/infra` (8 carnets), `scripts/analysis` (5) | | carnets dispersés | sorties parfois versionnées |
| `Divers/`, `scratch/`, `tests/token_usage`, fichiers `batch_*.json`, `chunk49*`, `.pptx` à la racine | | restes de sessions | ni ignorés ni rangés |

## Principes proposés

1. **Quatre natures, quatre places** : ce qui se versionne et se publie (bibliothèques), ce qui se
   déploie (services), ce qui entre (données), ce qui sort (résultats). Un fichier ne doit jamais
   hésiter entre deux.
2. **Tout ce qu'une exécution produit vit hors de git**, avec un index lisible et une règle de
   rétention. `experiments/`, `data/cache/`, `data/prometheus_data/`, les sorties de notebooks.
3. **Un point d'entrée par composant**, et le `Makefile` racine délègue au lieu de tout porter
   (il dépasse le millier de lignes).
4. **La documentation du projet reste dans `docs/`**, chaque bibliothèque porte la sienne
   (README, CHANGELOG, site mkdocs), les pages lourdes archivées sortent du dépôt de code.
5. **Pas de dépôt git imbriqué** : `prompt_calibration` se consomme comme une dépendance
   versionnée (ce que devient aussi le gateway à l'itération 3 du ticket 037), ou devient un
   sous-module déclaré ; jamais une copie de travail invisible du parent.

## Cible, sans déplacement immédiat

```
packages/     llm_gateway, mobility_core, mobility_llm ; prompt_calibration comme dépendance
services/     llm-agents (contrôleur, serveur osmnx), tableau de bord, eqasim-toulouse,
              otp-toulouse, GAMA (le modèle, une seule casse)
infra/        docker-compose, Dockerfiles, grafana (dashboards, alertes), prometheus
data/         inputs/ immuables sous DVC ; reference/ (cerema_values, population_emc2,
              feature_spec : ce que mobility_core.resources cherche) ; cache/ ignoré
experiments/  hors git, registre, rétention
docs/         arch, setup, tickets, changelog ; paper et synthèse archivée en LFS ou dans
              un dépôt de publication
notebooks/    tous les carnets, sorties vidées ; papermill écrit dans experiments/
scripts/      outils maintenus et testés, rien d'autre
specs/  tests/ (bout en bout transverses)
```

## Migration envisagée, en trois pas indépendants

1. **Alléger** : sortir les données de `scripts/` et de `docs/`, ignorer ou archiver les restes,
   une seule casse pour GAMA. Aucun chemin de code ne change.
2. **Infrastructure et services** : `infra/` et `services/` ; les contextes Docker et le Makefile
   suivent. C'est le pas qui touche le plus de chemins.
3. **Bibliothèques** : `packages/` quand le gateway et prompt_calibration sont consommés comme
   dépendances (itération 3 du ticket 037), sinon le déplacement n'apporte rien.

## Ce que ce ticket ne décide pas

L'ordre et le calendrier ; la place de `prompt_calibration` (dépendance ou sous-module) ; le sort
des pages de synthèse (LFS ou dépôt séparé). Ce sont les trois questions à trancher à l'ouverture.
