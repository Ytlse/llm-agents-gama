# A/B de la fenêtre météo et du bulletin — ticket 023, étape 3 du protocole

Mesure du **2026-08-25**, sur le substrat `v9` (run de référence `2026-08-24_17_34`).
**Cinq bras**, mêmes personas, même prompt `expert_chaine`, modèle d'éval **épinglé**
`gemini-3.5-flash-lite` (T = 0). 290 appels LLM en deux campagnes.

**Verdict : REJET sur les trois corrections.** Ni la fenêtre d'enquête, ni le bulletin
enrichi, ni l'agenda annoté par étape ne produisent d'effet distinguable de ce qu'un simple
re-tirage produit tout seul. Le rejet est une issue normale du protocole, et il s'archive
comme l'adoption.

**Et un second résultat, sur l'instrument :** `screen` a produit deux fois un « signal » que
`val` n'a pas confirmé. Ce jeu ne doit plus être lu seul.

## Les cinq bras

| Jeu | Tirage | Ce qui change dans le prompt | Rôle |
|---|---|---|---|
| `v9` | année (365 j), `meteo_v2` | d'origine | la référence |
| `v10` | fenêtre EMC² (152 j), `meteo_v3` | d'origine | **le traitement** |
| `v9n` | année (365 j), `meteo_v3n` | d'origine | **le plancher de bruit** — re-tirage seul |
| `v10b` | fenêtre (152 j), `meteo_v3` | enrichi | **le bulletin**, lu contre `v10` |
| `v10c` | fenêtre (152 j), `meteo_v3` | agenda annoté par étape | **l'agenda**, lu contre `v10` |

`v10c` annote **chaque** étape de l'agenda — condition, température, luminosité
(jour / nuit / aube / crépuscule), rafales ≥ 30 km/h, verglas < 3 °C — au relevé de **3 h**
et non de 6 h. La source porte huit relevés ; quatre n'étaient pas lus. ⚠ Ce bras
**n'existe pas en production** : il devait être mesuré d'abord.

`v9n` remplace le canal placebo du protocole, inutilisable ici : le traitement touche 99 %
du jeu, le placebo aurait pesé 1 % — une vingtaine d'enregistrements — et sa mise à l'échelle
en `√(masse_placebo / masse_traitée)` l'aurait amplifié d'un facteur ~10.

## Le résultat

Composite, ↓ meilleur :

| | `v9` | `v10` | `v9n` | `v10b` | `v10c` |
|---|---:|---:|---:|---:|---:|
| `screen` — 121 personas | 22,93 | 22,51 | 22,60 | 23,06 | 24,46 |
| `val` — 182 personas | 26,75 | 25,06 | 28,73 | 26,78 | 24,89 |

Et les quatre contrastes :

| Contraste | `screen` | `val` | |
|---|---:|---:|---|
| `v10 − v9` | −0,43 | −1,69 | la fenêtre — **le traitement** |
| `v9n − v9` | **−0,34** | **+1,98** | le témoin nul — **le plancher de bruit** |
| `v10b − v10` | +0,55 | +1,72 | le bulletin enrichi |
| `v10c − v10` | **+1,95** | **−0,17** | l'agenda annoté par étape |

## Ce que ces chiffres établissent

**1. Le plancher de bruit est plus grand que ce qu'on cherchait à mesurer.** C'est le
résultat principal, et il ne porte pas sur la météo mais sur l'instrument. Le témoin nul ne
change **aucune** distribution — même liste de 365 jours, seule la graine bouge — et il
déplace pourtant le composite de −0,34 sur `screen` et de **+1,98** sur `val`. Il change
même de **signe** entre les deux jeux. Sur `val`, le traitement (−1,69) est plus petit en
valeur absolue que ce plancher : **sous le plancher de bruit**.

**2. Le témoin nul a évité un faux positif, et c'est ce qui justifie son coût.** Avec le
canal placebo du protocole — 1 % du jeu, donc un plancher étroit — un Δ de −1,69 sur `val`
aurait été déclaré « signal » sans hésitation. Il est en réalité plus petit que la variance
propre de l'instrument. Le bras supplémentaire a coûté un quart de la campagne ; il a évité
de publier un effet qui n'existe pas.

**3. Le verdict imprimé par le script sur `screen` est trop généreux, et il faut le lire
avec cette réserve.** `ab_meteo.py` applique la règle héritée de `ab_car_availability.py` :
`|Δ traité| > |Δ plancher|` ⇒ « SIGNAL ». Sur `screen`, cela donne 0,43 contre 0,34, soit
**1,26 fois le bruit** — un rapport qui ne veut rien dire. Le seuil n'a **pas** été modifié
après coup : déplacer les poteaux une fois le résultat connu invaliderait la mesure. La
sortie brute est archivée telle quelle dans `store/`, avec cette réserve à côté.

**4. Le bulletin enrichi va dans le mauvais sens, sans qu'on puisse l'affirmer.** +0,55 et
+1,72 sur le composite : une dégradation dans les deux jeux. Mais sur `val` — le seul jeu
indépendant — ce +1,72 reste sous le plancher de +1,98. **Il n'y a donc pas de preuve que le
bulletin dégrade**, seulement l'absence de preuve qu'il améliore.

**5. Le signe du traitement est constant, et ce n'est pas une preuve.** −0,43 puis −1,69 :
les deux vont dans le sens d'une amélioration, là où le plancher change de signe. Avec deux
jeux de lecture, un signe constant n'est pas un résultat — c'est une pièce à verser au
dossier si la question est reprise sur un substrat plus large.

**6. L'agenda annoté est le cas d'école de la campagne.** Sur `screen`, son +1,95 est le
contraste le plus fort de toute la mesure — **5,7 fois le plancher**, une dégradation nette,
avec la marche qui recule de 13,26 % à 10,93 % alors qu'elle est déjà le mode le plus
sous-représenté. On tenait un résultat. Sur `val`, il vaut **−0,17** : il change de signe et
s'effondre à **un dixième** du plancher. Il ne reste rien.

**7. `screen` ne doit plus être lu seul, et c'est un résultat sur l'instrument.** Deux fois
dans cette campagne, il a produit un écart que `val` n'a pas confirmé — le bulletin, puis
l'agenda. Ce n'est pas surprenant après coup : `screen ⊂ train`, il ne porte que 121
personas, et son plancher de bruit y est six fois plus petit que sur `val` (−0,34 contre
+1,98). Un plancher étroit fabrique des signaux. Toute lecture future doit exiger `val`.

## Ce que ces chiffres ne disent pas

- **Rien sur la pluie**, et c'était écrit avant la mesure. Le Δ de pluie change de signe
  selon le substrat — −1,20 pt sur `v7`, +1,10 pt sur `v9` — pour un plancher de −1,16 pt.
  Le ticket refusait d'en tirer un effet quel que soit le résultat de l'A/B ; il n'en tire
  aucun. Cf. [`2026-08-25_premesure_meteo_v9`](../2026-08-25_premesure_meteo_v9/README.md).
- **Rien sur l'offre d'options ni sur les chaînes de véhicule.** Un jeu gelé mesure l'effet
  de la météo sur le **narratif** soumis au modèle, pas sur ce que la simulation aurait fait
  d'un agent trempé.
- **Rien sur l'axe A5 du [ticket 020](../../tickets/ticket_020_perimetre_population_cerema.md).**
  La variance d'un run de cinq jours comparé à une moyenne de 152 jours n'est pas corrigeable
  par un choix de dates : 27,7 % des séquences de cinq jours de la période d'enquête sont
  elles aussi entièrement sèches. Cette limite reste ouverte.
- **Rien sur les transports collectifs**, qui restent à 20,8 % sur `val` contre 12,4 %
  attendus. La fenêtre météo ne touche pas ce défaut, et le faire croire serait malhonnête.

## La preuve d'exclusion

`protocol_lock.json` — le jeton pris avant le premier appel, relâché après le dernier :

| | |
|---|---|
| Campagne | Sujet | Prise → relâchement | État de la pile |
|---|---|---|---|
| 4 bras | `A/B fenêtre météo et bulletin (screen + val)` | 08:00:18 → 08:27:32 UTC | **aucun service en marche** aux deux bouts |
| 5ᵉ bras | `5e bras v10c (agenda annoté par étape)` | 09:19 → 09:26 UTC | **aucun service en marche** aux deux bouts |

Instantanés de quota indisponibles dans les deux cas — l'API était arrêtée, ce qui est la
cause même de l'exclusion. Campagne cloud déclarée en pause (`CLOUD_PAUSED=1`).

Les quotas manquent parce que la pile était **entièrement arrêtée** : c'est précisément le
cas où l'exclusion est la meilleure, et où l'API — qui sert `/health` — ne répond pas. « Aucun
service en marche » est une preuve plus directe que deux compteurs inchangés : rien du côté
local ne pouvait consommer.

⚠ **Reste la VM cloud**, que ce verrou n'atteint pas. Elle est couverte par la seule liste de
contrôle humaine, pas par une garantie technique.

## La porte de décision

**Rejet sur les trois corrections.**

L'**agenda annoté** (`v10c`) n'est **pas porté en production**. Il n'y a jamais été : le bras
était expérimental, et c'est précisément ce qui a permis de ne rien livrer sur la foi du
+1,95 de `screen`. Le code vit dans `rewrite_weather.py` et attend un instrument moins
bruyant.

⚠ **La résolution de 3 h reste, elle, une piste ouverte.** `v10c` la portait, mais en paquet
avec l'annotation : la mesure ne peut pas les départager, et son rejet ne condamne pas la
résolution. Quatre relevés sur huit restent inexploités dans la source, et le code météo
diffère entre 12H et 15H sur 44 % des jours. À reprendre seule, si l'instrument le permet.

Le tirage de production reste sur l'**année entière** : la simulation doit pouvoir
se jouer n'importe quand. La fenêtre d'enquête reste disponible dans `WeatherDeck.load` et
gelée dans les manifestes de `v10` / `v10b`, mais elle n'est adoptée nulle part.

Le **bulletin enrichi** est livré en production (`weather_loader`) et reste actif : la mesure
ne montre pas qu'il dégrade, et l'information qu'il porte — amplitude, soleil, créneaux
pluvieux — est factuellement absente du prompt sans lui. Ce choix est un choix de contenu,
pas un résultat de mesure, et il est assumé comme tel.

Ce qui justifiait le ticket n'était pas l'ampleur attendue — la pré-mesure annonçait un effet
faible — mais que la mesure soit **enfin faite sur la fenêtre de sa cible**. Elle l'est.

## Reproduire

```bash
cd prompt_calibration && .venv/bin/python rewrite_weather.py --all --dry-run
```

```bash
make protocol-lock SUBJECT="A/B fenêtre météo" CLOUD_PAUSED=1
```

```bash
cd prompt_calibration && ../llm-agents/.venv/bin/python ab_meteo.py --dataset val --dry-run
```

`screen.json` et `val.json` portent les chiffres de cette page — aucun n'est recopié à la
main. `protocol_lock.json` et `protocol_lock_v10c.json` portent les preuves d'exclusion des
deux campagnes.

⚠ **Quatre alarmes** pendant la campagne : autant de vecteurs de probabilités à somme nulle,
repliés sur une distribution uniforme, soit quatre décisions de modèle perdues sur 2 262
évaluées (0,2 %). Trop peu pour déplacer un composite, assez pour être dit. `store/` contient le dump brut des 17 évals du store `ab_chaine.db`, tous tickets
confondus : les quatre bras de cette mesure s'y repèrent par leur clé `ds=v9`, `ds=v10`,
`ds=v9n`, `ds=v10b`.
