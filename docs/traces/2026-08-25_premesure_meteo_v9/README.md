# Pré-mesure du ticket 023 sur le substrat `v9` — et contrôles de la source du bulletin

Mesure du **2026-08-25**. **Aucun appel LLM dépensé.** C'est l'étape 1 du
[protocole exogène](../../arch/protocole-parametre-exogene.md) : chiffrer avant de payer.

**Statut : ce n'est pas un A/B.** Rien n'est évalué par un modèle ici. On compare des
**lignes de contexte** — la phrase météo que le prompt porterait selon le tirage — et on
chiffre la source. Cette trace ne dit rien de l'effet sur les décisions ; elle dit combien
il y a de matière à mesurer, et où sont les pièges.

## Pourquoi elle existe

La pré-mesure du ticket 023 portait sur les jeux `v7`. Le
[run de référence du 2026-08-25](../2026-08-25_run_reference/README.md) a fait de `v9` le
nouveau substrat. Les chiffres devaient être rejoués — et le sont.

## 1. La fenêtre d'enquête, rejouée sur `v9`

Substrat `v9`, jeux `train` + `val` (`test` fermé, `screen ⊂ train`) : **1 810
enregistrements, 613 personas distincts**. Fenêtre EMC² 20/09 → 18/02 : **152 jours retenus
sur 365**.

> ⚠ **La pré-mesure `v7` comptait double.** Ses « 2 087 enregistrements hors `test` »
> additionnaient `train` + `val` + `screen` + `rank`, alors que `screen ⊂ train` et
> `rank ⊂ screen` : **519 lignes comptées deux fois**, soit 24,9 %, toutes issues de `train`.
> Le décompte juste pour `v7` est **1 568**. La lecture ci-dessous ne prend que `train` +
> `val`. Le défaut sur-pondère `train` ; il ne change pas le signe du −4,90 °C, mais il
> n'avait pas été vu.

| Bras | Tirage | T moyenne | Δ T | Sous la pluie | Δ pluie | Phrase inchangée | Bascules pluie ⇄ sec |
|---|---|---:|---:|---:|---:|---:|---:|
| `v9` — existant | année, `meteo_v2` | 15,57 °C | — | 42,43 % | — | — | — |
| `v10` — traitement | fenêtre, `meteo_v3` | 10,84 °C | **−4,74 °C** | 43,54 % | +1,10 pt | 1,05 % | 49,4 % |
| `v9n` — témoin nul | année, `meteo_v3n` | 15,83 °C | +0,26 °C | 41,27 % | −1,16 pt | 1,10 % | 49,3 % |

Le témoin nul rejoue le tirage **sans changer la distribution** : son Δ est le plancher de
bruit, à la même masse que le traitement.

### Ce que ces chiffres établissent

1. **L'effet thermique se réplique — sur des tirages disjoints, pas sur des populations
   indépendantes.** −4,74 °C sur `v9`, −4,90 °C sur `v7`, pour un plancher de bruit de
   +0,26 °C : dix-huit fois. Le recoupement a été fait plutôt que supposé, et il nuance la
   portée : les deux substrats **partagent 89 % de leurs personas** (557 des 613 de `v9`,
   Jaccard 0,891). Ce qui est disjoint, c'est l'unité réellement mesurée — la clé de tirage
   `(agent_id, entry)`, commune à **1,8 %** seulement (1,0 % avec l'heure de départ). **99 %
   des enregistrements de `v9` lisent une météo que la pré-mesure `v7` n'avait jamais lue.**
   La réplication vaut pour la grandeur ; elle ne vaut pas comme réplication sur population
   indépendante, et le mot n'est donc pas employé.
2. **L'effet sur la pluie n'existe pas, et on en a maintenant la preuve.** Le Δ **change de
   signe entre substrats** : −1,20 pt sur `v7`, **+1,10 pt sur `v9`**, pour un plancher de
   bruit de −1,16 pt sur ce même `v9`. Un effet qui s'inverse selon le substrat, à magnitude
   égale au bruit, est du bruit. Le refus de conclure sur la pluie n'est plus une précaution
   de méthode : c'est un résultat.
3. **Le canal placebo du protocole est inutilisable ici.** Le traitement touche 98,95 % des
   enregistrements ; le placebo ne pèse que 1,05 %, soit **19 enregistrements**. La mise à
   l'échelle en `√(masse_placebo / masse_traitée)` que prescrit le protocole l'amplifierait
   par 9,7. D'où le témoin nul à pleine masse, qui coûte un bras d'A/B de plus.

### Ce que ces chiffres ne disent pas

- **Rien sur les décisions.** Aucun modèle n'a lu ces phrases. Un Δ de composite reste
  entièrement à mesurer, et **le rejet est une issue normale** de la porte de décision.
- **Rien sur la variance d'un run de simulation** — l'autre moitié de l'axe A5 du
  [ticket 020](../../tickets/ticket_020_perimetre_population_cerema.md), que ce ticket ne
  ferme pas.
- **Les bascules pluie ⇄ sec ne sont pas un effet** : 49,4 % au traitement contre 49,3 % au
  témoin nul. C'est du brassage, identique des deux côtés.

## 2. Contrôles de la source, pour le bulletin enrichi

`data/weather/meteo_toulouse_12_mois.csv`, 365 jours. Trois pièges à traiter **avant**
d'écrire le bulletin :

| Constat | Mesure | Conséquence |
|---|---:|---|
| Jours portant des mm **sans aucun créneau précipitant** | 25 / 365 (médiane 0,2 mm, max 2,5 mm, 2 jours ≥ 1 mm) | Repli obligatoire sur la formulation actuelle : la forme enrichie **ajoute, n'enlève jamais** |
| Créneaux hors de `[MIN, MAX]` de la source | 30 / 1 460, écart max **3 °C**, tous de nuit | Bornes du jour élargies aux créneaux lus ; la source n'est pas modifiée |
| Créneau précipitant avec 0 mm cumulé | 23 / 365 | Bruine et averses non cumulées — la phrase reste juste, le cumul est omis |
| Jours avec neige | **1 / 365** (`2025-11-21`) | Branche conservée malgré sa vacuité |

**Aucune colonne de probabilité de précipitation n'existe dans cette source.** Un « risque de
pluie » en pourcentage serait fabriqué. Seuls les créneaux dont le **code météo** est
précipitant sont annonçables.

## Reproduire

```bash
prompt_calibration/.venv/bin/python docs/traces/2026-08-25_premesure_meteo_v9/premesure.py
```

```bash
prompt_calibration/.venv/bin/python docs/traces/2026-08-25_premesure_meteo_v9/controles_source_bulletin.py
```

Les deux scripts écrivent `results.json` et `controles_source.json` à côté d'eux. **Aucun
nombre de ce README n'est recopié à la main** : tous sortent de ces deux fichiers.

Substrat : [`calibration_datasets/v9`](../../../prompt_calibration/calibration_datasets/v9/manifest.yaml),
tiré du run `experiments/archive/2026-08-24_17_34`.
