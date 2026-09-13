# ADR 0001 — `llm_module` devient trois paquets

- **Date** : 2026-09-06
- **Statut** : accepté (décision de l'auteur du dépôt, ticket 037)
- **Portée** : `llm_module/` du monorepo `llm-agents-gama`

## Contexte

`llm_module` était à mi-chemin d'une bibliothèque : architecture ports & adapters depuis
la refonte de juillet 2026, `pyproject.toml`, contrats import-linter, 504 tests verts. Mais
c'était deux bibliothèques dans un seul paquet — un gateway LLM générique et un domaine
métier « mobilité toulousaine EMC² » — et le second avait colonisé le premier.

Mesures du 2026-09-06 : 13 513 lignes Python tests compris ; `core/` comptait 3 352
lignes dont 254 seulement génériques (models, batching, selection) ; ≈ 2 250 des 4 700
lignes de tests portaient sur le domaine mobilité ; sur 117 imports depuis `llm-agents`,
`scripts` et `prompt_calibration`, 95 visaient `core` et **un seul** le SDK du gateway.

Fuites concrètes : le worker importait le choix modal, comptait les désaccords de mode et
classait des distances en tranches ; `AgentSpec` imposait perception, trajectoires et
ressenti à toute catégorie ; prompts et schémas étaient livrés dans le paquet ; le `core/`
« pur » remontait de deux niveaux vers la racine du dépôt et lisait `/app/scripts/...`.
Réflexes de composant plutôt que de bibliothèque : `__init__.py` vide, `logger.remove()`
effaçant les handlers de l'hôte, métriques Prometheus déclarées à l'import du SDK,
`providers.yaml` réécrit dans le paquet installé, variables d'environnement non préfixées,
egg-info versionné, shims sans dépréciation.

## Décision

Trois paquets installables, répertoires frères à la racine du dépôt, layout `src/` :

| Paquet | Contenu | Dépend de |
|---|---|---|
| `llm_gateway` 1.1.0 | api, worker, infra, ports, adapters, balancer, moteur de prompts **sans contenu**, télémétrie, SDK, config | rien du dépôt |
| `mobility_core` 0.1.0 | couronnes, zones fines, hiérarchie des modes, vélo, logement, équipement, cadrage de population, données gelées | rien du dépôt |
| `mobility_llm` 0.1.0 | persona, templates, schémas, variantes de prompt, choix modal, métriques métier ; s'enregistre auprès du gateway par entry point | les deux autres |

`llm_module/` reste une coquille de compatibilité : chaque ancien module réexporte son
successeur et émet un `DeprecationWarning` ; retrait à la version majeure suivante (2.0). Les
imports de `llm-agents` et `scripts` sont réécrits ; `prompt_calibration` (dépôt autonome)
reste sur la coquille.

Hypothèses prises avec la décision (`specs/ticket_037/questions.md`) : noms `llm_gateway`,
`mobility_core`, `mobility_llm` (H1) ; trois répertoires dans le monorepo, extraction plus
tard (H2) ; français pour code, docstrings et documentation (H3) ; aucun `LICENSE` tant que
la licence n'est pas choisie (H4, question ouverte) ; le contrat de réponse `AgentResponse`
reste typé « options » dans le gateway pour ne pas casser le contrat HTTP (H5) ; les
templates, schémas et `prompts.yaml` gardent leur disposition à plat dans
`mobility_llm/prompts/` parce que `prompt_calibration` et les expériences citent
`prompts.yaml` (H6) ; le worker Celery reste dans `llm_gateway/worker/` (H7) ;
`providers.yaml` reste une donnée du paquet `llm_gateway` (H8).

## Conséquences

- Un consommateur du gateway installe `llm-gateway` seul et n'embarque ni geopandas, ni les
  ressources de l'enquête, ni un prompt. Sans bundle, toute catégorie est refusée en 422.
- Le domaine EMC² est utilisable sans LLM : eqasim et les notebooks importent
  `mobility_core` sans tirer Redis, Celery, httpx, FastAPI ou Jinja2 (contrat import-linter).
- Cinq contrats d'architecture remplacent les deux d'avant ; `lint-imports` tourne en CI.
- Trois suites de tests (233 · 199 · 134 le 2026-09-07), trois `CHANGELOG.md`, trois
  README ; un site mkdocs pour le gateway.
- L'image Docker `api`/`worker` a pour contexte la racine du dépôt et embarque les trois
  paquets : le worker a besoin du bundle et de son domaine.
- Coût assumé : un déplacement par `git mv` de tout le code, des imports réécrits dans
  `llm-agents` et `scripts`, une coquille à maintenir jusqu'en 2.0. `ruff format` est différé
  (H10) pour que git détecte les renommages.

## Alternatives écartées

- **Deux paquets** (gateway + mobilité) : le domaine de l'enquête aurait continué de
  dépendre du gateway, ou l'inverse. eqasim n'a pas besoin d'un gateway LLM pour tirer un
  vélo.
- **Rester en un paquet avec des sous-paquets et des contrats import-linter** : les
  contrats existaient déjà et n'ont pas empêché la colonisation ; un seul `pyproject.toml`
  impose les dépendances de tous à chacun.
- **Extraire le gateway dans un dépôt séparé tout de suite** : dépend du versioning et de
  la distribution, remis à un second temps par l'auteur.
- **Authentification, adapter générique, exécuteur sans Celery dans le même chantier** :
  reportés (tickets 036 et itérations suivantes de 037) pour garder l'itération 1 lisible.
