# Ajouter un provider

Un *provider* est une instance nommée dans le fichier des fournisseurs désigné par `LLM_GATEWAY_PROVIDERS_FILE` (dans ce dépôt : `config/llm_gateway/providers.yaml` ; le paquet ne livre qu'un `providers.example.yaml`) : un
modèle, une URL, des quotas, un poids. Plusieurs instances peuvent partager le même
*adapter* (le traducteur vers l'API du fournisseur). Trois cas, du plus simple au plus rare.

## Cas 1 — une instance de plus sur un adapter existant

Adapters livrés : `openai`, `mistral`, `google`, `groq`, `cerebras`. Ajouter un bloc sous
`providers:` :

```yaml
  groq_qwen_qwen3_6_27b:
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
| `default_model` | oui | — | adapter (`_resolve_model`) si la requête n'en impose pas |
| `adapter` | non | nom de l'instance | `get_adapter` : classe d'adapter et héritage de clé `PROVIDER_KEYS__<adapter>` |
| `tpm_limit` | non | `None` | rate-limiter : réservation de tokens estimés dans la même fenêtre 60 s ; borne aussi `batch_max_agents` |
| `rpd_limit` | non | `None` | rate-limiter : compteur requêtes/jour UTC ; atteint → provider écarté jusqu'à minuit UTC |
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
Pour un provider à petit TPM c'est le TPM qui borne : `groq_openai_120` affiche 30 RPM mais
8 000 TPM ne soutient que ~2,7 requêtes/min, d'où `0.18`. Recalculer à chaque changement de
`rpm_limit` ou `tpm_limit` ; `make providers` le fait. Le recalage du 2026-07-10 a montré
l'enjeu : Mistral portait 47 % de la capacité totale et recevait 8 % du trafic.

La séquence SWRR ([explication](../explications/batching-swrr-disjoncteur.md)) répartit
100 créneaux proportionnellement aux poids, chaque provider en rotation en ayant au moins un.

## Cas 2 — une seconde clé pour le même fournisseur

Les quotas free tier Google sont comptés **par projet et par modèle**. Une clé d'un autre
projet est un autre seau de 500 requêtes/jour : c'est l'instance `google2` (clé
`PROVIDER_KEYS__google2`), et `google2_35` réutilise la même clé sur le modèle 3.5
(`docker-compose.yml` dérive `PROVIDER_KEYS__google2_35` de `PROVIDER_KEYS__google2` plutôt
que de dupliquer le secret dans `.env`). Le nom d'instance **doit** correspondre à la
variable : sinon la résolution retombe sur `PROVIDER_KEYS__google`, la clé 1, sans avertir.

## Cas 3 — un nouvel adapter

Quand l'API cible n'est compatible avec aucun des cinq formats. Créer
`src/llm_gateway/adapters/<nom>_adapter.py` :

```python
from llm_gateway.adapters.base import BaseAdapter, register_adapter
from llm_gateway.core.models import InternalRequest, LLMOutput


@register_adapter
class MonAdapter(BaseAdapter):
    provider_name = "monfournisseur"     # = valeur du champ `adapter` dans providers.yaml
    request_timeout = 120.0              # surcharger si le fournisseur est lent (Google : 240 s)

    def call(self, request: InternalRequest) -> tuple[LLMOutput, int, int]:
        response = self._http().post(                       # client httpx partagé (keep-alive)
            f"{self._get_base_url()}/…",
            headers={"Authorization": f"Bearer {self._get_api_key().get_secret_value()}"},
            json={"model": self._resolve_model(request),
                  "messages": [{"role": m.role, "content": m.content} for m in request.messages],
                  "max_tokens": request.max_tokens, "temperature": request.temperature},
        )
        self._raise_for_status(response)                    # 5xx → ProviderServerError, 4xx → ProviderClientError
        data = response.json()
        self._check_openai_finish_reason(data)              # si format OpenAI : troncature → erreur 503 retryable
        raw = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return self._parse_output(raw), usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
```

Le contrat de `call` : rendre `(LLMOutput, tokens_in, tokens_out)` ou lever
`ProviderServerError` (5xx, rejoué avec backoff), `ProviderClientError` (4xx),
`ProviderParseError` (JSON hors schéma). `_parse_output` fait le nettoyage tolérant
(balises Markdown, réparation `json-repair`, détection de boucle de répétition, clé `agents`).
`_raise_for_status` capture le délai de reprise des 429 (en-tête `retry-after`,
`x-ratelimit-reset-*`, ou corps JSON à la Gemini) pour le cooldown. Le schéma de sortie est
dans `request.response_schema` : l'injecter selon ce que l'API propose (`response_format`
chez OpenAI/Groq, `responseSchema` chez Google, texte dans le message système chez Mistral).

`ping()` est facultatif : la base avertit et rend `True` (le provider est inclus par défaut).

!!! warning "Le chargement des adapters est une liste fermée"
    `get_adapter` charge les modules à la demande via `_load_adapters()` dans
    `adapters/base.py`, qui énumère **cinq** modules connus (`openai`, `google`,
    `mistral`, `groq`, `cerebras`). Un adapter nouveau n'est trouvé que si son module a été
    importé avant — il faut donc **ajouter votre module à ce dictionnaire**. C'est une
    limite connue, à lever avec l'adapter OpenAI-compatible générique reporté à l'itération
    suivante (ticket 037). Sans cela : `KeyError: Adapter inconnu pour le fournisseur '…'`.

Ensuite : bloc dans `providers.yaml` avec `adapter: monfournisseur`, clé
`PROVIDER_KEYS__monfournisseur`, un test d'intégration sur `httpx.MockTransport` à la manière
de `tests/integration/test_google_adapter.py`, et une entrée dans le corpus
`tests/data/llm_outputs.json` si le fournisseur produit des sorties d'une forme nouvelle.

## Retirer un provider

Commenter le bloc plutôt que le supprimer, avec la date et la raison (`# [obsolète
2026-08-18] default_model … absent de /models`). `make providers` ne ré-ajoute jamais un
modèle déjà présent dans le fichier, même commenté : un bloc commenté est une décision.
