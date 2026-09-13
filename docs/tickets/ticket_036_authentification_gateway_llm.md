# Ticket 036 — Authentification par jeton du gateway LLM

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité.
>
> **Décision de l'auteur du dépôt (2026-09-06)** : à traiter dans un second temps, après le
> découpage de `llm_module` en bibliothèque (paramétrage préfixé, cf. étude du 2026-09-06).
> Ce ticket fixe le périmètre pour que la décision ne soit pas reprise de zéro.

## Constat

L'API du gateway (`llm_module/api/routes.py`) n'a aucune authentification : `POST /tasks`,
`GET /tasks/{id}`, `GET /tasks/{id}/wait`, `GET /errors` et `GET /metrics` répondent à
quiconque atteint le port. Le CORS autorise toutes les origines (`allow_origins=["*"]`,
`api/app.py`). Aujourd'hui le service n'est joignable que depuis le réseau Docker du
compose et l'hôte, ce qui rend le risque acceptable pour la simulation. Il ne l'est plus dès
que le gateway devient une bibliothèque déployée ailleurs : un `POST /tasks` ouvert consomme
les quotas et les clés API du déploiement.

## Objectif

Un jeton porteur optionnel, activé par configuration, sans lequel les routes de travail
répondent 401. Désactivé, le comportement actuel est strictement conservé.

## Périmètre

1. **Configuration** : `api.auth_tokens: list[SecretStr]` dans les settings du gateway
   (préfixe `LLM_GATEWAY_`). Liste et non valeur unique, pour permettre la rotation : on
   ajoute le nouveau jeton, on bascule les clients, on retire l'ancien. Vide = pas d'auth.
2. **Vérification** : dépendance FastAPI posée sur le routeur des tâches et sur `/errors`.
   En-tête `Authorization: Bearer <jeton>`. Comparaison en temps constant
   (`secrets.compare_digest`). Absence d'en-tête → 401 ; jeton inconnu → 403.
3. **Exemptions** : `/health` reste ouvert (sondes Docker et Prometheus) ; `/metrics` est
   exempté par défaut et protégeable par `api.metrics_require_auth: bool`.
4. **SDK** : `LLMGatewayClient(auth_token=...)` envoie l'en-tête ; lecture par défaut de
   `LLM_GATEWAY_AUTH_TOKEN` côté client. Un 401/403 devient une erreur typée non
   réessayable (pas de backoff ni de disjoncteur : ce n'est pas une panne).
5. **Journalisation** : jamais le jeton en clair, ni dans les logs ni dans les métriques ;
   un compteur `llm_gateway_auth_rejected_total{reason}` et un `[ALARME]` sur front montant
   si les rejets dépassent un seuil (tentatives répétées).
6. **CORS** : `api.cors_origins: list[str] = []` remplace le `*` codé en dur. Vide = pas de
   CORS ; la valeur actuelle devient un choix explicite du déploiement.

## Hors périmètre

OAuth/OIDC, quotas par client, jetons par catégorie, mTLS. À reconsidérer seulement si le
gateway sert plusieurs équipes.

## Critères d'acceptation

- [ ] Sans `auth_tokens`, la suite de tests actuelle passe inchangée.
- [ ] Avec un jeton configuré : `POST /tasks` sans en-tête → 401, jeton faux → 403, bon
      jeton → 202 ; `/health` répond 200 sans en-tête.
- [ ] Deux jetons configurés sont tous deux acceptés (rotation).
- [ ] Le SDK renvoie une erreur typée sur 401/403 et n'incrémente pas le disjoncteur.
- [ ] `grep` du jeton de test dans les logs du run : zéro occurrence.
- [ ] La doc « configuration » et `.env.example` décrivent la variable et la rotation.

## Dépendances

- Paramétrage préfixé et groupé du gateway (étude du 2026-09-06, section D) : le champ
  `api.auth_tokens` s'y range ; ne pas l'ajouter à l'ancien `Settings` à plat.
- `docker-compose.yml` : variable d'environnement partagée entre `api` et `controller`.

## Effort

S (moins d'une demi-journée) une fois le paramétrage groupé en place.
