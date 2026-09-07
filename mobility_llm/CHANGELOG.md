# Changelog — mobility-llm

Format : `## [version] - AAAA-MM-JJ`, entrées les plus récentes en tête. Le ton est celui de
l'usage. Les fichiers touchés sont dans git.

## [0.1.0] - 2026-09-07

Première version : les catégories LLM de la simulation de mobilité, sorties du gateway
(ticket 037). Le paquet est la colle entre `llm_gateway` (générique) et `mobility_core`
(domaine de l'enquête).

**Ce que le paquet apporte :**

- **Un bundle** enregistré sous l'entry point `llm_gateway.categories`
  (`mobility = "mobility_llm:bundle"`) : quatre catégories — `itinary_multi_agent`,
  `perception_filter`, `stm_reflection`, `ltm_self_reflection` — avec leurs templates
  `.md.j2`, `schemas.json` et les variantes de prompt système de `prompts.yaml`.
- **`AgentSpec`**, le persona (ex-`llm_module.core.models.AgentSpec`) : c'est lui qui dit ce
  qu'un item doit porter (`agent_id`, `perception`, options, météo, agenda…). Un persona
  sans `perception` est refusé par l'API en 422 ; un champ non déclaré est ignoré, comme
  avant le découpage.
- **La priorité d'un lot** = plus petit `departure_timestamp` (`departure_priority`).
- **Les métriques métier du worker** (`categories.itinary_multi_agent.observe_itinary`) :
  mode le plus probable, masse de probabilité par mode canonique, tranches de distance,
  désaccords d'étiquette de mode avec alarme au-delà de 5 % sur 200 options. Les noms de
  compteurs Redis sont inchangés : les dashboards Grafana 04 et 07 continuent de les lire.
- **Le choix modal** (`mode_choice`) : normalisation du vecteur de probabilités, projection
  sur les modes canoniques, tirage déterministe par graine dérivée du contexte.
- **`prompt_manager()`** pour les consommateurs hors gateway (contrôleur, expériences) :
  checksum du prompt actif, liste des variantes.

**Avant :** le worker du gateway importait le choix modal et calculait lui-même ces
compteurs ; changer une règle de mobilité modifiait le gateway.
**Après :** le worker appelle `CategorySpec.observe` sans savoir ce qu'est un mode de
transport ; une erreur dans le hook est journalisée et n'échoue jamais le lot.

Tests : 134 collectés le 2026-09-07 (le test e2e est sauté sans `LLM_GATEWAY_E2E_URL`).
`tests/unit/test_bundle_end_to_end.py` est la preuve d'adoption de `llm_gateway.testing` :
registre construit à la main, `FakeAdapter`, sink de métriques en mémoire.
