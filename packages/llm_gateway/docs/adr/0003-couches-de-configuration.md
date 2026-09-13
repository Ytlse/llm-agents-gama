# ADR 0003 — Les réglages viennent de six couches, groupées et préfixées

- **Date** : 2026-09-07
- **Statut** : accepté (ticket 037, itération 2, lot A)
- **Portée** : `llm_gateway.config` (settings, sources, providers, learned), l'API (`/config`), le compose

## Contexte

Avant le lot A, `Settings` était un objet à plat de vingt champs lus dans un environnement **sans
préfixe** (`REDIS_URL`, `APP_WORKDIR`, `LOG_LEVEL`…), partagé avec le contrôleur et les autres
services du même compose : le gateway lisait des variables qui ne lui étaient pas destinées, et
un consommateur qui l'embarquait héritait de ses noms. Le fichier des fournisseurs vivait **dans
le paquet installé**, et le worker y **réécrivait** les plafonds de complétion appris : une
bibliothèque qui modifie ses propres fichiers dans `site-packages`.

## Décision

1. **Un objet `GatewaySettings` composé de sept groupes** (`redis`, `executor`, `inference`,
   `batching`, `resilience`, `api`, `telemetry`) plus le fichier des fournisseurs, les clés et
   le store des limites apprises. Chaque groupe est un modèle pydantic documenté ; les alias à
   plat (`settings.redis_url`…) restent une version pour les consommateurs.
2. **Six sources, ordre fixe** : arguments du constructeur, environnement `LLM_GATEWAY_*`
   (`__` entre les niveaux), anciens noms non préfixés (source héritée qui avertit et ne parle
   que si le nouveau nom est absent), fichier YAML `LLM_GATEWAY_CONFIG`, profil
   `LLM_GATEWAY_PROFILE` livré avec le paquet, défauts du code.
3. **`PROVIDER_KEYS__<nom>` reste canonique** pour les clés d'API : ce nom est partagé avec le
   `.env` de l'auteur, le compose (logique des seconds seaux Google), `make providers` et
   prompt_calibration. Le renommer aurait cassé quatre outils pour un gain nul ; la forme
   préfixée est acceptée aussi.
4. **Le fichier des fournisseurs sort du paquet** : `LLM_GATEWAY_PROVIDERS_FILE` le désigne, le
   paquet ne livre qu'un exemple. Clé inconnue = échec au chargement, provider et clé nommés.
5. **Les limites apprises vont derrière un port** (`LearnedLimits`) : Redis en production
   (partagé API/workers), fichier JSON sans Redis, mémoire sinon. Fusionnées au démarrage par-
   dessus la configuration, elles ne peuvent que resserrer un plafond, jamais l'élargir.
6. **`GET /config` et `GET /config/providers`** publient la configuration effective, secrets
   masqués : les outils qui lisaient le YAML peuvent interroger le gateway.

## Conséquences

- Le compose passe aux noms préfixés pour `api`, `worker`, `flower` ; le `.env` de l'auteur ne
  change pas. Le contrôleur lit le fichier des fournisseurs au nouveau chemin (monté en lecture
  seule) : l'ordre de démarrage ne dépend pas d'un appel à l'API.
- `providers.yaml` du dépôt vit dans `config/llm_gateway/` ; `make providers` l'écrit là.
- La référence des réglages est **générée** (`tools/gen_settings_doc.py`) : la doc ne peut plus
  dériver du code.
- Écart au plan de l'itération : le sous-modèle `providers` prévu est devenu trois champs de
  premier niveau (`providers_file`, `learned_limits`, `learned_limits_file`) pour garder
  `settings.providers` comme dictionnaire des instances résolues, cité à vingt-deux endroits.

## Alternatives écartées

- **Renommer aussi `PROVIDER_KEYS__`** : cohérent, mais quatre outils et le `.env` à changer
  pour un secret qui ne gêne personne sous ce nom.
- **Garder le fichier des fournisseurs dans le paquet avec un chemin surchargeable** : c'est ce
  qui permettait au worker d'écrire dans `site-packages` ; le déplacer coupe la tentation.
- **Interroger `/config/providers` depuis le contrôleur** : fragile au démarrage (l'API n'est
  pas encore prête quand le contrôleur lit ses réglages) ; le fichier monté suffit.
