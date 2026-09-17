# Ticket 087 — La restriction ne couvrait que les décisions, et GAMA mourait sur une pause

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert et **livré le 2026-09-16**, 11 tests dédiés. Contrat : `specs/ticket_087/tests.md`,
> écrit avant le code.
>
> **Objet.** Deux défauts trouvés en tentant de lancer le bras choqué C6, chacun capable à lui
> seul d'invalider le run — l'un silencieusement, l'autre bruyamment.

---

## 1. La mémoire du run était écrite par un autre modèle

### Ce qui a été mesuré

Run `experiments/archive/2026-09-16_12_48`, `llm_exchanges.jsonl` :

| Catégorie | Instance | Appels |
|---|---|---|
| `itinary_multi_agent` (les décisions) | `google_gemini31_key1` | 5 |
| **`stm_reflection` (la consolidation mémoire)** | **`mistral_key1`** | **1** |

### Pourquoi

`llm_agent.py` appelle la passerelle à **trois** endroits : la décision d'itinéraire, la
réflexion STM et l'auto-réflexion LTM. Le ticket 084 avait posé `instances_admises` sur le
**premier seulement**. Les deux autres partaient sans restriction, donc servis selon la
politique du dépôt — une cascade qui commence par Mistral.

Pour une expérience dont l'objet d'étude **est la mémoire**, cela signifie que les décisions
venaient de gemini 3.1 pendant que les souvenirs qui les nourrissent étaient rédigés par un
modèle non déclaré. Rien dans les journaux ne l'aurait dit : le run se serait terminé, le
rapport se serait construit, et la mesure aurait porté un nom faux.

### Ce qui est fait

La restriction devient une propriété du **client**, appliquée dans `LLMGatewayClient.execute`
— le seuil unique par lequel sortent les trois appels. Le service la donne une fois à la
construction du client, depuis `settings.llm.instances_admises`.

**Pourquoi pas recopier la ligne sur les deux payloads manquants.** Parce que c'est ce qui a
produit le défaut : trois sites d'appel, une consigne posée sur un seul. Un quatrième site
ajouté demain reproduirait l'oubli, et le reproduirait en silence. La restriction posée au
seuil couvre ce qui existe et ce qui viendra.

**La restriction du client ne fait que combler.** Un appelant qui porte la sienne reste maître
de son routage : le client ne l'écrase jamais (cas A4). Sans restriction déclarée, aucune clé
n'est ajoutée au payload et le comportement est rigoureusement celui d'avant (A5, A6).

L'injection par appel du ticket 084 est retirée : une seule source de vérité.

---

## 2. GAMA était tué par une pause normale

### Ce qui a été mesuré

Même run, `gama_headless.log` :

| Pauses de GAMA entre deux syncs | 23 |
|---|---|
| Médiane | 9,0 s |
| Maximum | **40,9 s** |
| Au-dessus de 20 s | **3** |

Fin du journal :

> [ALARME] Connexion GAMA Server fermée : sent 1011 keepalive ping timeout — l'expériment
> associé est arrêté par GAMA

### Pourquoi

Le lanceur ouvrait sa connexion avec les défauts de `websockets` : ping toutes les 20 s,
**timeout de réponse 20 s**. Or GAMA se bloque pendant qu'il attend les décisions du LLM.
En `CACHE=0` — donc dès qu'on veut un run journalisé sur son périmètre complet — c'est le
régime **normal**, pas une anomalie. En pénurie de jetons il l'est davantage encore : la règle
du dépôt est d'attendre le renouvellement plutôt que de se rabattre sur un modèle dégradé,
donc l'attente peut durer des minutes.

Le seuil du lanceur était calé plus court que le fonctionnement nominal de ce qu'il pilote.

### Ce qui est fait

`ping_timeout` porté à **20 minutes** (`GAMA_PING_TIMEOUT_S`, défaut 1200 s). C'est trente fois
la pause la plus longue observée, cela couvre une pénurie de jetons, et cela reste assez court
pour qu'une vraie coupure réseau soit détectée au lieu de laisser un run fantôme.

Le ping reste **émis** (`ping_interval`, 20 s) : on desserre le délai de réponse, on ne coupe
pas la détection. Et les pauses restent journalisées telles quelles — elles sont le signal
d'un run qui peine, et le correctif ne doit pas les faire taire (cas B4).

---

## 3. Une attribution corrigée

Le premier arrêt du bras, à 11:50, a d'abord été imputé à une collision avec la campagne
`bascule_anglaise_v6`, qui avait repris le contrôleur. Le second arrêt porte la même signature
**sans aucun processus concurrent** : la collision n'était pas nécessaire, la pause suffit.
La campagne a probablement allongé la pause fatale ; elle n'en était pas la cause.

---

## 4. Ce que le ticket ne change pas

La politique de routage du dépôt, la règle « une restriction fausse n'est jamais aucune
restriction » du ticket 084, le filtre client `allowed_providers` — conservé comme défense en
profondeur. Un client sans restriction se comporte exactement comme avant.
