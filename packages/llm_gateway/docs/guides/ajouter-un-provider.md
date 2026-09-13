# Ajouter un provider

Un *provider* est une instance nommée dans le fichier des fournisseurs désigné par `LLM_GATEWAY_PROVIDERS_FILE` (dans ce dépôt : `config/llm_gateway/providers.yaml` ; le paquet ne livre qu'un `providers.example.yaml`) : un
modèle, une URL, des quotas, un poids. Plusieurs instances peuvent partager le même
*adapter* (le traducteur vers l'API du fournisseur). Trois cas, du plus simple au plus rare.

## Cas 1 — une instance de plus sur un adapter existant

Adapters livrés : `openai`, `mistral`, `google`, `groq`, `cerebras`. Ajouter un bloc sous
`providers:` :

```yaml
  groq_qwen_qwen3_6_27b_key1:
    adapter:                groq                       # nom de l'adapter (défaut = nom de l'instance)
    rpm_limit:              30
    tpm_limit:              8000
    rpd_limit:              1000
    max_tokens_per_request: 8000                       # requête unique > TPM → HTTP 413 chez Groq
    base_url:               https://api.groq.com/openai/v1
    default_model:          qwen/qwen3.6-27b
    weight:                 0.18                       # min(30, 8000/3000)/15
    concurrency_limit:      3
    disable_timeout:        120
```

Puis la clé : `PROVIDER_KEYS__groq_qwen_qwen3_6_27b=…` ou, plus souvent, la clé partagée de
l'adapter `PROVIDER_KEYS__groq=…`. La résolution est `provider_keys[nom_instance] or
provider_keys[adapter]` : une instance dont le nom ne correspond à aucune variable retombe
sur la clé de l'adapter, en silence. Une instance sans aucune clé est exclue au démarrage
(« Fournisseur 'x' exclu : clé API manquante »).

Vérifier :

```bash
llm-gateway config validate        # OK — N provider(s) avec clé : …
llm-gateway config show            # batch_max_agents et tpm_estimate_per_request calculés, secrets masqués
make providers DRY_RUN=1           # depuis la racine : sonde les quotas réels sans écrire
```

## Les champs, et qui les applique

| Champ | Obligatoire | Défaut | Appliqué par |
|---|---|---|---|
| `rpm_limit` | oui | — | rate-limiter : fenêtre glissante 60 s, lissage `min_interval = 60 / rpm` (une réservation trop rapprochée est refusée) |
| `base_url` | oui | — | adapter (`_get_base_url`) |
| `wait_timeout` | non | défaut du client | **personne côté gateway** : recopié tel quel et publié, le SDK le reçoit par appel (`execute(wait_timeout=…)`). Pour un modèle local, l'attente d'une tâche est celle de la file, pas de la génération. |
| `default_model` | oui | — | adapter (`_resolve_model`) si la requête n'en impose pas |
| `adapter` | non | nom de l'instance | `get_adapter` : classe d'adapter et héritage de clé `PROVIDER_KEYS__<adapter>` |
| `tpm_limit` | non | `None` | rate-limiter : réservation de tokens estimés dans la même fenêtre 60 s ; borne aussi `batch_max_agents` |
| `rpd_limit` | non | `None` | rate-limiter : compteur requêtes/jour dans le fuseau du provider ; atteint → provider écarté jusqu'à son reset |
| `quota_reset_tz` | non | `UTC` | fuseau où le provider situe minuit (`America/Los_Angeles` pour Google) |
| `tpd_limit` | non | `None` | rate-limiter : tokens/jour UTC comptés a posteriori (tokens réels) ; même mise à l'écart |
| `max_tokens_per_request` | non | `None` | démarrage : exclusion si `< batch_max_agents × assumed_prompt_tokens + min_output_tokens` ; worker : garde-fou 413 sur le prompt rendu (`ProviderCapacityError`) |
| `max_output_tokens` | non | `None` | worker : borne le `max_tokens` envoyé ; balancer : exclut le provider si `< parameters.max_tokens` de la requête ; **appris** sur HTTP 400 et réécrit dans le fichier |
| `weight` | non | `1.0` | balancer : séquence SWRR ; `0` = défini mais **hors rotation**, utilisable seulement en `force_provider` |
| `concurrency_limit` | non | `2` | rate-limiter : workers Celery simultanés sur ce provider |
| `disable_timeout` | non | `180` | worker : durée de désactivation après 30 erreurs consécutives |
| `batch_max_agents` | ne pas écrire | calculé | `Settings.build_providers` — voir [Régler les quotas](regler-les-quotas.md) |
| `tpm_estimate_per_request` | ne pas écrire | calculé | idem |

Toutes ces valeurs sont **appliquées** par le code. En revanche les quotas eux-mêmes sont
des relevés : un `# TBC` dans le fichier signale une valeur non vérifiée, et les
commentaires datés (`vérifié 2026-08-03 (en-têtes x-ratelimit)`) disent d'où vient le
chiffre. `make providers` (`scripts/providers/refresh.py`) les rafraîchit depuis les
en-têtes réels.

!!! warning "Un champ mal orthographié est ignoré sans erreur"
    `ProviderConfig` accepte aujourd'hui les clés inconnues (comportement pydantic par
    défaut, `extra` non fixé) : `rmp_limit: 30` ne lève rien, et le champ `rpm_limit`
    obligatoire manquant lèvera une `ValidationError` seulement si aucune autre ligne ne le
    fournit. Relire `llm-gateway config show` après une édition.

## Convention de poids

Le poids est proportionnel à la capacité réellement soutenable, pas au RPM affiché :

```
weight = min(rpm_limit, tpm_limit / 3000) / 15
```

3 000 ≈ tokens (entrée + sortie) d'une requête moyenne, 15 = RPM de référence (poids 1,0).
Pour un provider à petit TPM c'est le TPM qui borne : `groq_openai_120_key1` affiche 30 RPM mais
8 000 TPM ne soutient que ~2,7 requêtes/min, d'où `0.18`. Recalculer à chaque changement de
`rpm_limit` ou `tpm_limit` ; `make providers` le fait. Le recalage du 2026-07-10 a montré
l'enjeu : Mistral portait 47 % de la capacité totale et recevait 8 % du trafic.

La séquence SWRR ([explication](../explications/batching-swrr-disjoncteur.md)) répartit
100 créneaux proportionnellement aux poids, chaque provider en rotation en ayant au moins un.

## Cas 2 — une seconde clé pour le même fournisseur

Les quotas free tier Google sont comptés **par projet et par modèle**. Une clé d'un autre
projet est un autre seau de 500 requêtes/jour : c'est l'instance `google_gemini31_key2` (clé
`PROVIDER_KEYS__google2`), et `google_gemini35_key2` réutilise la même clé sur le modèle 3.5
(`docker-compose.yml` dérive `PROVIDER_KEYS__google2_35` de `PROVIDER_KEYS__google2` plutôt
que de dupliquer le secret dans `.env`).

Nommez l'instance `<modèle>_key<N>` : le suffixe rend la clé physique lisible, et il **interdit
le repli** sur `PROVIDER_KEYS__<adapter>`. Sans `PROVIDER_KEYS__<nom_instance>`, l'instance est
écartée de la rotation et le démarrage le signale — au lieu de servir en silence la clé 1, ce
qui a déjà fait partir des appels sur la mauvaise clé. Ajoutez donc la ligne de mapping dans
`docker-compose.yml` en même temps que l'instance dans `providers.yaml`.

Pour un fournisseur qui ne situe pas minuit en UTC, posez aussi
`quota_reset_tz` (cf. `regler-les-quotas.md`).

## Cas 3 — une API compatible OpenAI, sans écrire de code

Ollama, vLLM, OpenRouter, LM Studio, Together, Fireworks… parlent le dialecte
`POST {base_url}/chat/completions` : c'est le traducteur `openai_compatible`, dont OpenAI, Groq,
Cerebras et Mistral ne sont que des réglages. Une entrée dans le fichier des fournisseurs suffit :

```yaml
mon_ollama:
  adapter: openai_compatible
  structured_output: json_object     # json_schema (natif OpenAI) | json_object | none
  schema_in_system: true             # recopie le schéma JSON dans le message system
  base_url: http://ollama:11434/v1
  default_model: qwen3:8b
  rpm_limit: 60
  weight: 1.0
```

puis la clé `PROVIDER_KEYS__mon_ollama` (une valeur quelconque si l'API n'en exige pas : une
instance sans clé est exclue de la rotation). Les deux réglages d'adapter valent aussi pour les
quatre dialectes livrés : `mistral` avec `structured_output: json_schema` bascule un modèle
récent sur la sortie structurée native, sans code.

!!! note "LM Studio n'accepte pas `json_object`"
    Vérifié le 2026-09-08 : `response_format.type` doit valoir `json_schema` ou `text`, sinon
    HTTP 400 « 'response_format.type' must be 'json_schema' or 'text' ». Déclarez donc
    `structured_output: json_schema`. Depuis un conteneur, LM Studio sur l'hôte se joint via
    `http://host.docker.internal:1234/v1`, et `default_model` est l'identifiant de `lms ls`.
    Posez `weight: 0` si un seul modèle est chargé à la fois : hors rotation, l'instance ne sert
    qu'aux requêtes qui la forcent (`force_provider`), et la cascade ne provoque pas de
    chargement à la volée. Déploiement de référence : section LM Studio de
    `config/llm_gateway/providers.yaml` et `docs/setup/llm-providers.md`.

| Dialecte livré | `structured_output` | `schema_in_system` |
|---|---|---|
| `openai` | `json_schema` | non |
| `groq` | `json_object` | non (le schéma vient du prompt) |
| `cerebras` | `json_object` | oui |
| `mistral` | `json_object` | oui |

Les erreurs réseau (délai dépassé, connexion refusée, réponse coupée) sont classées par la base en
`ProviderServerError` avec `error_type` `network_timeout`, `network_connect`, `network_protocol` :
le worker les réessaie avec backoff et cooldown, comme un 5xx.

## Cas 4 — un nouvel adapter, dans votre paquet

Quand l'API n'est compatible avec aucun dialecte connu. Sous-classez `BaseAdapter` (ou
`OpenAICompatibleAdapter` si seul un détail diffère : surchargez `build_payload` ou `_headers`) :

```python
from llm_gateway.adapters.base import BaseAdapter
from llm_gateway.core.models import InternalRequest, LLMOutput


class MonAdapter(BaseAdapter):
    provider_name = "monfournisseur"     # = valeur du champ `adapter` dans le fichier des fournisseurs
    request_timeout = 120.0              # surcharger si le fournisseur est lent (Google : 240 s)

    def call(self, request: InternalRequest) -> tuple[LLMOutput, int, int]:
        response = self._post(                              # erreurs réseau → ProviderServerError
            f"{self._get_base_url()}/…",
            headers={"Authorization": f"Bearer {self._get_api_key().get_secret_value()}"},
            json={"model": self._resolve_model(request), "prompt": "…", "top_p": request.top_p},
        )
        self._raise_for_status(response)                    # 5xx → ProviderServerError, 4xx → ProviderClientError
        data = response.json()
        return self._parse_output(data["text"]), data["in"], data["out"]
```

Le contrat de `call` : rendre `(LLMOutput, tokens_in, tokens_out)` ou lever
`ProviderServerError` (réjoué avec backoff), `ProviderClientError` (4xx), `ProviderParseError`
(JSON hors schéma). `_parse_output` fait le nettoyage tolérant (balises Markdown, réparation
`json-repair`, boucle de répétition, clé `agents`) ; `_raise_for_status` capture le délai de
reprise des 429 ; `request.top_p` peut être `None` : ne l'envoyez que s'il est défini.

Déclarez la classe dans le `pyproject.toml` de **votre** paquet, le gateway la découvre au
premier appel sans que rien ne change chez lui :

```toml
[project.entry-points."llm_gateway.adapters"]
monfournisseur = "mon_paquet.adapters:MonAdapter"
```

Le nom de l'entry point devient le `provider_name` si la classe n'en fixe pas. Un adapter
inchargeable est journalisé en `[ALARME]` et n'empêche pas les autres de servir. Testez sur un
client httpx doublé, à la manière de `tests/integration/test_openai_compatible_adapter.py`, et
ajoutez une entrée au corpus `tests/data/llm_outputs.json` si le fournisseur produit des sorties
d'une forme nouvelle.

## Retirer un provider

Commenter le bloc plutôt que le supprimer, avec la date et la raison (`# [obsolète
2026-08-18] default_model … absent de /models`). `make providers` ne ré-ajoute jamais un
modèle déjà présent dans le fichier, même commenté : un bloc commenté est une décision.
