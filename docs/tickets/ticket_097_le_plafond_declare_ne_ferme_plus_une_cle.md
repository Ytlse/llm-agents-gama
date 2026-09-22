# Ticket 097 — Le plafond déclaré ne ferme plus une clé

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-21, à la suite d'un chantier déjà écrit et non commité sur `main`
> (garde-fou retiré, endpoint `reset-quota`, réactivation d'OpenAI et de Groq). Le ticket
> **enregistre** cette décision et met la spécification en accord avec elle ; il ne la découvre
> pas.

---

## 1. La question, en une phrase

Une clé d'API doit-elle être écartée parce qu'un fichier de configuration **annonce** qu'elle est
pleine, ou parce que le fournisseur **refuse** de la servir ?

Jusqu'au 2026-09-21, la plateforme répondait « parce qu'un fichier l'annonce ». La règle Q11 du
ticket 035 écartait toute instance dont la marge `rpd_limit − daily_requests` ne couvrait pas le
besoin du lot à venir, de sorte que l'exécution passait `epuisee` **avant** d'avoir reçu un seul
refus. Le chiffre qui fermait la clé — `rpd_limit` — n'était pourtant jamais mesuré : il est
recopié à la main dans `config/llm_gateway/providers.yaml` depuis une documentation fournisseur.

## 2. Pourquoi ce chiffre ne mérite pas ce pouvoir

Trois observations, toutes antérieures au ticket :

- **Groq** n'a jamais publié sa limite journalière ailleurs que dans le corps de ses propres 429.
  Le `rpd_limit` inscrit pour lui est une hypothèse, pas une lecture (écarté le 2026-09-08 pour
  un plafond de jetons par minute découvert de la même façon).
- **Mistral** servait en pratique le double du débit par minute écrit dans le fichier.
- **Google** a retiré la page dont les quotas de `providers.yaml` étaient issus ; les chiffres qui
  en restent ne sont plus rattachables à une source.

Une instance écartée sur ce seul motif ne l'est donc jamais sur une mesure. Le défaut est du même
genre que celui du 2026-09-08 (instantané `/health` figé au démarrage, run arrêté à 70,5 % avec un
seau plein en réserve) : **la plateforme s'arrête sur une croyance, pas sur un fait**, et le coût
est un run interrompu avec des requêtes payées et non consommées.

## 3. Ce qui change

`MoniteurRessources.disponible` ne lit plus que des signaux **produits par la passerelle** :

| Signal | Origine | Écarte ? |
|--------|---------|----------|
| `disabled` / `cooldown` (`hors_service`) | passerelle, après erreurs consécutives | oui |
| `quota_exhausted` | passerelle, posé sur un 429 du fournisseur | oui |
| marge `rpd_limit − daily_requests` | `providers.yaml`, déclaratif | **non, depuis le 2026-09-21** |

La marge reste calculée (`marge()`), affichée dans le panneau des ressources et citée par
`raison_epuisement` : elle renseigne le chercheur, elle ne décide plus.

En contrepartie, une clé est **testée en réel** au lancement : `reinitialiser_quotas()` lève les
verrous locaux résiduels (`POST /providers/reset-quota` côté passerelle, plus une purge Redis de
repli), et `cli.py` admet les instances servantes sans attendre l'aval des compteurs.

**Le prix est assumé :** un 429 par clé et par fenêtre, soit une requête perdue, en échange d'un
plafond mesuré au lieu d'être supposé. C'est moins cher qu'un run arrêté à tort.

**Ce qui ne change pas :** l'épuisement reste un état atteignable et final (Q4), et il faut que
**toutes** les instances du modèle épinglé aient été refusées pour y passer. Aucune substitution
vers un autre modèle, aucune décision par défaut, aucun repli dégradé — quand il n'y a plus de
quota, on attend la fenêtre, on n'invente pas une réponse.

## 4. Portée

Le retrait vaut **partout**, pas seulement au démarrage : `DecideurPasserelle._prochaine_instance`
et `runner.veiller_quotas` lisent le même `disponible()`. C'est le point qui a été tranché
explicitement le 2026-09-21 — le contournement dans `cli.py` aurait suffi pour le seul lancement.

À noter : en production `besoin` a toujours valu 1 (aucun appelant ne le surcharge), si bien que
le scénario d'origine de Q11 — « lot de 10 contre marge de 7 » — n'a jamais été exercé. Le
garde-fou ne mordait en pratique qu'à marge nulle.

## 5. Conséquences documentaires

- `specs/ticket_035/05-ressources-interruption-reprise.md` : règle Q11 marquée abrogée, critère
  d'acceptation Q11 réécrit sur le nouveau comportement.
- `services/llm-agents/tests/test_035_03_05_06_execution.py` : `test_Q11_epuisement_anticipe`
  devient `test_Q11_le_plafond_declare_n_ecarte_pas`, doublé de
  `test_Q11_le_refus_reel_ecarte_toujours` qui tient la contrepartie (Q4 intact).
- `docs/arch/plateforme-experiences.md` : « Disponible » lit désormais **deux** signaux ; la
  troisième panne est consignée.
- Puis, avec la journalisation (§ 7) : règle **Q11b** et son critère d'acceptation ajoutés à la
  même spec ; paragraphe « Ce qu'il reste au plafond déclaré : journaliser » dans
  `docs/arch/plateforme-experiences.md` ; trois tests `test_097_*`.

## 6. Reste à faire

- [x] **2026-09-21** — Vérifié : la passerelle déployée (conteneur `api`, port 8000) expose bien
      `POST /providers/reset-quota` et `POST /providers/{provider}/reset-quota` ; les deux routes
      figurent dans son `openapi.json`. `reinitialiser_quotas()` a donc un interlocuteur, sans
      dépendre de son repli Redis.
- [x] **2026-09-21** — Le franchissement du plafond déclaré est journalisé : deux WARNING posés par
      `MoniteurRessources._journaliser_plafond()` à la lecture de `/health`, sur front montant (une
      ligne par instance et par fenêtre). Détail en § 7.
- [x] **2026-09-21, 18:51** — `make providers` exécuté après la fin du run. **Aucun `rpd_limit`
      n'était à corriger là où la sonde a abouti** ; deux instances restent hors de portée d'une
      mesure. Détail en § 8.

---

## 7. Ce qu'il reste au plafond déclaré : journaliser

Ne décidant plus, le plafond ne laissait plus rien derrière lui : l'abrogation supprimait le
garde-fou **et** la mesure. Deux WARNING le rétablissent, sans rien réintroduire dans la décision.

| Fait journalisé | Ligne | Ce qu'on en apprend |
|-----------------|-------|---------------------|
| `daily_requests` **strictement** au-delà de `rpd_limit`, sans refus | `[ressources] [PLAFOND] g1 : 612/500 requêtes/jour — plafond déclaré dépassé de 112 et le fournisseur sert toujours` | Le chiffre du fichier est trop bas. À `612 == 612`, rien n'est démenti : c'est pourquoi la comparaison est stricte. |
| `quota_exhausted` posé par un 429 | `[ressources] [PLAFOND] g1 refusée par le fournisseur (429) à 412 requêtes/jour — limite réelle observée ; plafond déclaré 500 (écart -88)` | Le compteur au moment du refus **est** la limite réelle. C'est la mesure que le troisième point de la § 6 attendait. |

**Front montant** : une ligne par instance et par fenêtre, pas une par rafraîchissement — le
journal d'un run en compte des dizaines. La trace se réarme quand le compteur journalier retombe
sous le plafond (fenêtre suivante) ou quand le refus se lève.

**Silence assumé** : sans `rpd_limit` déclaré ou sans `daily_requests` publié, rien n'est écrit.
Supposer un chiffre est le défaut même que ce ticket corrige.

Couvert par `test_097_le_depassement_du_plafond_est_journalise`,
`test_097_le_refus_reel_mesure_la_limite` et `test_097_sans_chiffre_mesure_aucune_trace`
(`services/llm-agents/tests/test_035_03_05_06_execution.py`), et spécifié en **Q11b**
(`specs/ticket_035/05-ressources-interruption-reprise.md`).


---

## 8. La remesure du 2026-09-21 : ce que les sondes ont répondu

`make providers` (`scripts/providers/refresh.py`), lancé à 18:51 une fois le run terminé.

| Instance | Sonde | `rpd_limit` |
|----------|-------|-------------|
| `groq_openai_120_key1`, `groq_openai_20_key1`, `groq_qwen_qwen3_8_27b_key1` | en-têtes `x-ratelimit-*` lus | **1000, confirmé** — la valeur du fichier était juste |
| mistral, google | sonde et API Cloud Quotas abouties, aucune ligne modifiée | inchangé (mistral n'a pas de quota journalier) |
| `cerebras_gptoss120b_key1` | 🚨 HTTP 402 *payment required* | **non mesurable** |
| `openai_gpt56_luna_key1` | 🚨 HTTP 429 *you have no credits remaining* sur tous les modèles | **non mesurable** |

Les deux échecs ne disent rien d'un quota : ce sont des comptes sans crédit. Le script a laissé
ces deux instances intactes et a levé une `[ALARME]` pour chacune — jamais d'assouplissement
silencieux. À noter pour le § 3 : `openai_gpt56_luna_key1`, réactivée par ce ticket, **ne peut pas
servir aujourd'hui**. La nouvelle règle la traite correctement — la passerelle la mettra hors
service au premier 402/429 — mais sa réactivation reste sans effet tant que le compte est à sec.

**Ce que la remesure ne peut pas atteindre, la trace du § 7 l'atteindra :** le jour où ces deux
clés serviront, le WARNING posé sur leur refus donnera leur limite réelle sans qu'aucune sonde
ne soit à relancer.

### Un effet de bord à arbitrer (hors périmètre 097)

Le script ne se limite pas aux `rpd_limit` : il a rétabli `tpm_limit: 8000` sur les trois
instances Groq et porté leur `max_tokens_per_request` de 6000 à 8000. Or ces valeurs avaient été
**neutralisées à la main** pour le debug du ticket 077 (« éviter le verrou 60 s artificiel de
`tpm_limit=8000` face au reset sub-seconde de Groq »), commentaire toujours présent dans le
fichier. Le script mesure juste, mais il ignore cette décision.

`config/llm_gateway/providers.yaml` a donc été **rendu à son état d'avant le script** : la
remesure ne changeait aucun `rpd_limit`, et il n'y avait pas de raison de défaire au passage une
décision du 077 en cours de validité. La version produite par le script est conservée hors dépôt
pour arbitrage. La question — garder la neutralisation du 077, ou reprendre les 8000 mesurés —
appartient au ticket 077.