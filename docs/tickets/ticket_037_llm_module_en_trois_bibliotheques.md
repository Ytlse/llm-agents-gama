# Ticket 037 — `llm_module` devient trois bibliothèques

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Les questions ouvertes et les hypothèses prises vivent dans
> `specs/ticket_037/questions.md`.
>
> **Décisions de l'auteur du dépôt (2026-09-06)** : découpage en trois paquets validé (GO) ;
> l'authentification est différée (ticket 036) ; versioning et distribution en second temps.

## Constat

`llm_module` est à mi-chemin d'une bibliothèque : architecture ports & adapters,
`pyproject.toml`, contrats import-linter, 504 tests verts. Mais c'est **deux bibliothèques
dans un seul paquet** : un gateway LLM générique et un domaine métier « mobilité toulousaine
EMC² », et le second a colonisé le premier.

| Mesure (2026-09-06) | Valeur |
|---|---|
| Lignes Python, tests compris | 13 513 |
| Lignes de `core/` | 3 352, dont 254 génériques (models, batching, selection) |
| Lignes de tests portant sur le domaine mobilité | ≈ 2 250 sur 4 700 |
| Imports depuis llm-agents, scripts, prompt_calibration | 117, dont 95 visent `core` |
| Imports du SDK gateway par les consommateurs | 1 |

Fuites du domaine dans le générique : le worker importe le choix modal, compte les désaccords
de mode, classe des distances en tranches ; `AgentSpec` impose perception, trajectoires,
ressenti ; les prompts et schémas sont livrés dans le paquet ; le `core/` « pur » remonte de
deux niveaux vers la racine du dépôt et lit `/app/scripts/...`.

Réflexes de composant : `__init__.py` vide sans `__all__` ni `__version__` ; `logger.remove()`
qui efface les handlers de l'hôte ; métriques Prometheus déclarées à l'import du SDK ;
`providers.yaml` réécrit à l'intérieur du paquet installé ; variables d'environnement non
préfixées ; egg-info versionné ; tests dans le paquet ; shims sans dépréciation.

## Cible

Trois paquets installables, répertoires frères à la racine du dépôt :

| Paquet | Rôle | Dépend de |
|---|---|---|
| `llm_gateway` | gateway générique : api, worker, infra, ports, adapters, balancer, moteur de prompts sans contenu, télémétrie, SDK, config | rien du dépôt |
| `mobility_core` | domaine EMC² Toulouse : couronnes, zones fines, hiérarchie des modes, vélo, logement, référence de population, données | rien du dépôt |
| `mobility_llm` | les catégories LLM de la mobilité : persona, templates, schémas, variantes de prompt, choix modal, métriques métier ; s'enregistre auprès du gateway par entry point | les deux autres |

`llm_module/` reste une coquille de compatibilité : chaque ancien module réexporte le nouveau et
émet un `DeprecationWarning` ; retrait à la version majeure suivante.

## Itération 1 (ce ticket)

1. Hygiène : egg-info hors git, journal de dialogue, cibles Makefile mortes, `.env.example`,
   version, refus des clés inconnues dans le YAML des providers.
2. Création des trois paquets, layout `src/`, déplacement par `git mv`, imports ajustés.
3. Coquille de compatibilité + réécriture des imports de llm-agents et scripts.
4. Hook de catégorie minimal : le worker appelle le bundle enregistré (validation des items,
   priorité, observation des métriques) ; il n'importe plus le choix modal.
5. Jalon 1 : trois suites vertes, suite llm-agents verte, import-linter KEPT, images
   reconstruites, `/health` répond.
6. Tests : dossiers unit / contract / integration / e2e, marqueurs, contrats paramétrés sur
   mémoire et Redis, hypothesis, corpus du parseur, couverture, sous-paquet `testing`.
7. CI GitHub Actions, pre-commit, cibles Makefile.
8. Documentation : site mkdocs du gateway, README et CHANGELOG de chaque paquet, ADR,
   mise à jour des pages du dépôt, archivage des tickets LLM-01 à 09.
9. Jalon 2 : CI verte, `mkdocs build --strict`, tutoriel rejouable.

## Reporté (itérations suivantes)

- Paramétrage en couches préfixé `LLM_GATEWAY_` et fichier des providers hors du paquet.
- Adapter OpenAI-compatible générique, cascade des paramètres d'inférence.
- Exécuteur in-process sans Celery.
- Authentification (ticket 036), versioning et distribution, dépôt séparé.

## Les tickets LLM-01 à LLM-09 (Divers/tickets, avant la refonte de juillet)

| Ticket | Devenir |
|---|---|
| LLM-01 packaging | couvert ici (façade, `__version__`, trois pyproject) |
| LLM-02 paramètres d'inférence | reporté : paramétrage en couches |
| LLM-03 adapter générique | reporté : généricité |
| LLM-04 quotas | refus des clés inconnues fait ici ; quotas journaliers déjà appliqués |
| LLM-05 robustesse | propagation des contraintes déjà corrigée ; erreurs réseau : reporté |
| LLM-06 code mort | `ping()` : reporté avec l'adapter générique |
| LLM-07 documentation | couvert ici |
| LLM-08 qualité et CI | couvert ici |
| LLM-09 registre de catégories | le registre validé au démarrage est posé ici |

## État au 2026-09-07 (itération 1)

| Jalon | Résultat |
|---|---|
| Trois paquets installés en editable (`llm-gateway` 1.1.0, `mobility-core` 0.1.0, `mobility-llm` 0.1.0) | fait |
| Coquille `llm_module` : 53 modules de réexport avec `DeprecationWarning` | fait ; plus aucun import de `llm_module` dans llm-agents et scripts (prompt_calibration, dépôt autonome, reste sur la coquille) |
| Hook de catégorie : registre validé au démarrage, `validate_items` / `priority` / `observe`, entry point `mobility_llm:bundle` | fait ; le worker n'importe plus le choix modal |
| Suites | llm_gateway 233 · mobility_core 199 (1 skip) · mobility_llm 134 (e2e sauté sans gateway) · llm-agents 551 |
| import-linter | 5 contrats KEPT (`.importlinter` à la racine) |
| ruff, mypy strict (core, ports, sdk) | 0 erreur |
| Images `api`/`worker` reconstruites (`llm_gateway/Dockerfile`, contexte racine, utilisateur non-root) | `/health` 200 ; catégorie inconnue → 422 avec la liste des catégories ; persona sans `perception` → 422 ; une seule famille `alarme_total` au scrape |
| Tests en quatre étages, contrats paramétrés mémoire + fakeredis (+ Redis réel en CI), hypothesis, corpus du parseur, intégration API et lot sans Redis | fait |
| CI (`.github/workflows/ci.yml`), pre-commit, cibles Makefile | CI **verte** le 2026-09-07 (run 34086849095, cinq jobs) après deux corrections : déclencheur étendu à toute branche, cliquet de couverture posé à 70 % (74 % mesurés, cible 80 % en itération 2) |
| Documentation : README des trois paquets, site mkdocs (17 pages, `mkdocs build --strict` à zéro avertissement), CHANGELOG des paquets, deux ADR, `.env.example`, pages du dépôt mises à jour, entrée du changelog | fait |
| Refus des clés inconnues dans `providers.yaml` (`extra="forbid"`) | fait le 2026-09-07, après relecture : l'annonce du 06 était prématurée |

Écarts assumés par rapport au plan : cf. `specs/ticket_037/questions.md` (H5 à H13).
Les sept échecs de `scripts/tests/test_qualification_60_tickets.py` (car scolaire, tf22-tf29) sont
antérieurs et indépendants : `ModuleNotFoundError: trip_helper` quand le fichier est lancé depuis la
racine sans le `PYTHONPATH` de llm-agents.

## Clôture de l'itération 1 (2026-09-07)

- Commits sur `feat_cache_population` : `2f27a27` (le découpage), `a5b3c8c` (déclencheur CI),
  `617c0f6` (cliquet de couverture). Poussés ; le travail en cours de l'auteur sur les tickets
  030, 032, 033 et 035 reste non commité, volontairement séparé.
- Pile complète relancée ; test de bout en bout `perception_filter` contre le gateway réel et un
  fournisseur réel : tâche acceptée, traitée en 6,1 s, deux synthèses valides.
- CI : 5 jobs verts (lint, types, contrats ; tests gateway avec Redis de service ; tests mobilité ;
  wheels ; mkdocs strict).
- Reste ouvert : la licence du gateway (question 1 de `specs/ticket_037/questions.md`).

## Itération 2 (plan soumis le 2026-09-07)

Paramétrage en couches et généricité, cinq lots (A réglages, B cascade d'inférence, C adapters,
D télémétrie, E rangement) : plan détaillé dans `specs/ticket_037/iteration_2.md`. GO le 2026-09-07.

| Lot | État |
|---|---|
| A — réglages en couches | **livré le 2026-09-07** : `GatewaySettings` en sept groupes, six sources (constructeur, env `LLM_GATEWAY_*`, anciens noms dépréciés, `LLM_GATEWAY_CONFIG`, profil, défauts), fichier des fournisseurs hors du paquet (`config/llm_gateway/providers.yaml`, clé inconnue refusée en nommant provider et clé), limites apprises derrière le port `LearnedLimits` (Redis, fichier, mémoire), `GET /config` et `/config/providers` masqués, CORS configurable, `disable_after_consecutive_errors`, référence des réglages générée, ADR 0003, gateway 1.2.0. Écarts : H17 à H20 |
| B à E | à venir |
