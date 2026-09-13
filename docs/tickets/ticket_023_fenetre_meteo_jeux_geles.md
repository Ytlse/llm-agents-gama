# Ticket 023 — La météo des jeux gelés, tirée dans la fenêtre d'enquête et non dans l'année

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source
> de vérité.
>
> **Nature du ticket** : *correction d'un paramètre exogène*, à mener **selon
> [`docs/arch/protocole-parametre-exogene.md`](../arch/protocole-parametre-exogene.md)** —
> mesurer dans l'enquête, réécrire un jeu gelé, A/B apparié, archiver, porte de décision.
> Le paramètre corrigé est ici l'**instrument** (la météo gelée dans les jeux de
> calibration) et non une valeur de production.
>
> Il porte aussi un **second livrable, transverse** : le **jeton d'exclusion** qui
> garantit qu'aucun autre run ne tourne pendant qu'une procédure de ce protocole
> s'exécute. C'est une exigence du protocole lui-même, qui n'avait jamais été outillée.
>
> Et un **troisième livrable**, décidé le 2026-08-25 : le **bulletin météo enrichi** —
> lever/coucher du soleil, amplitude min/max, créneaux précipitants. Il est livré dans la
> même campagne que la fenêtre, mais porté par un bras d'A/B distinct pour rester
> séparable.

## Ce qui est corrigé

[`prompt_calibration/calibration/weather.py`](../../prompt_calibration/calibration/weather.py)
tire un jour de météo par décision, dans **l'année climatique entière** :

```python
DEFAULT_SEED = "meteo_v2"
DEFAULT_WEATHER_CSV = _REPO_ROOT / "data" / "weather" / "meteo_toulouse_12_mois.csv"  # 365 jours
```

Or les cibles auxquelles ces jeux servent à comparer sont des déplacements recueillis entre
le **20 septembre 2022 et le 18 février 2023** — 152 jours, pas 365. Vérifié deux fois par
le [ticket 020](ticket_020_perimetre_population_cerema.md), axe A5 : la méthode EMC²
recueille les *déplacements de la veille*
([méthodologie CEREMA](https://www.cerema.fr/fr/actualites/enquetes-mobilite-certifiees-cerema-methodologie)),
et les dates de référence des microdonnées ne couvrent que 09→12/2022 et 01→02/2023, jours
ouvrés seulement.

**Ce n'est pas une redécouverte : c'est un raffinement.** L'action A7 du
[ticket 008](ticket_008_run_24h_mesures_synthese.md) a déjà corrigé le défaut grave — les
jeux `v1` ne portaient que cinq valeurs météo, toutes sèches et ensoleillées, parce que la
fenêtre du run source l'était. Le prompt était calibré dans un monde sans pluie. Le tirage
dans l'année a réglé cela. Ce ticket ne remet pas ce choix en cause ; il rétrécit la fenêtre
de tirage à celle de la cible.

---

## Ce que la pré-mesure dit déjà, sans dépenser un appel LLM

Le protocole exige de chiffrer avant de payer. Fait **deux fois**, sur deux substrats
successifs — d'abord `v7`, puis `v9` après que le [run de référence du
2026-08-25](../traces/2026-08-25_run_reference/README.md) a changé la base. La réplication
est ce qui donne son poids à la conclusion, et elle est publiée en entier.

**Substrat courant : `v9`**, jeux `train` + `val` (`test` fermé, `screen ⊂ train`) —
1 810 enregistrements, 613 personas distincts, en rejouant les trois tirages.

> ⚠ **La pré-mesure `v7` comptait double, et le chiffre publié en portait la trace.** Ses
> « 2 087 enregistrements hors `test` » additionnaient `train` + `val` + `screen` + `rank`,
> alors que `screen ⊂ train` et `rank ⊂ screen` : **519 lignes y étaient comptées deux fois**,
> soit 24,9 % du total, toutes issues de `train`. Le décompte juste pour `v7` est **1 568**.
> La mesure `v9` ci-dessous ne prend que `train` + `val`. L'effet sur le −4,90 °C est une
> sur-pondération de `train`, pas une erreur de signe — mais c'est exactement le genre de
> défaut que l'axe D6 demande de vérifier avant de parler de réplication, et il n'avait pas
> été vu. Chiffres et
scripts archivés dans
[`docs/traces/2026-08-25_premesure_meteo_v9`](../traces/2026-08-25_premesure_meteo_v9/README.md) :

| Bras | Jeu | Tirage | T moyenne | Δ T | Part sous la pluie | Δ pluie | Phrase inchangée | Bascules pluie ⇄ sec |
|---|---|---|---:|---:|---:|---:|---:|---:|
| A — existant | `v9` | année (365 j), `meteo_v2` | 15,57 °C | — | 42,43 % | — | — | — |
| B — traitement | `v10` | fenêtre (152 j), `meteo_v3` | 10,84 °C | **−4,74 °C** | 43,54 % | +1,10 pt | 1,05 % | 49,4 % |
| C — témoin nul | `v9n` | année (365 j), `meteo_v3n` | 15,83 °C | +0,26 °C | 41,27 % | −1,16 pt | 1,10 % | 49,3 % |

**Trois conclusions, avant tout A/B :**

1. **La correction est thermique, et elle seule.** −4,74 °C contre +0,26 °C au témoin nul :
   le signal fait dix-huit fois le plancher de bruit. Sur `v7` la mesure donnait −4,90 °C
   contre −0,02 °C.

   **En quel sens c'est une réplication — vérifié, pas supposé.** Les deux substrats
   partagent 89 % de leurs personas (557 des 613 de `v9` figurent aussi dans `v7`,
   Jaccard 0,891) : ce ne sont **pas** deux échantillons indépendants de population. Mais
   l'unité mesurée n'est pas le persona, c'est la **clé de tirage** `(agent_id, entry)` — et
   celles-ci ne se recouvrent qu'à **1,8 %** (1,0 % en tenant compte de l'heure de départ).
   **99 % des enregistrements de `v9` lisent une météo que la pré-mesure `v7` n'a jamais
   lue.** La réplication porte donc sur des tirages disjoints au-dessus d'une population
   largement commune : elle vaut pour la grandeur mesurée, elle ne vaut pas comme réplication
   sur population indépendante.
2. **Sur la pluie, il n'y a rien à annoncer, et on en a désormais la preuve.** Le Δ pluie
   **change de signe entre les deux substrats** : −1,20 pt sur `v7`, **+1,10 pt sur `v9`**,
   pour un plancher de bruit de −1,16 pt sur le même `v9`. Un effet qui s'inverse quand on
   change de substrat, à magnitude égale au bruit, **est du bruit**. Toute affirmation du
   genre « restreindre la fenêtre expose davantage — ou moins — à la pluie » est de la
   lecture de bruit, et le ticket la refuse par avance.
3. **Le brassage individuel est énorme et l'effet agrégé minuscule.** 49,4 % des
   enregistrements basculent pluie ⇄ sec pour 1,10 point d'écart agrégé — et le témoin nul,
   qui ne change aucune distribution, en brasse 49,3 %. C'est exactement la configuration où
   l'on lit du signal dans du bruit.

### ⚠ Le témoin placebo du protocole n'est pas disponible ici, et il faut le remplacer

La règle 1 du § « second piège » du protocole demande trois lectures : *traité*, *placebo*
(les enregistrements identiques, qui donnent le plancher de bruit) et *agrégat*. Ce
dispositif suppose que le traitement ne touche qu'une part du jeu.

Ici le traitement touche **98,95 %** des enregistrements. Le canal placebo ne pèse que
**1,05 %, soit 19 enregistrements** : un plancher estimé là-dessus n'est pas un plancher,
c'est du bruit sur du bruit. Le mettre à l'échelle en `√(masse_placebo / masse_traitée)`,
comme le protocole le prescrit, l'amplifierait par **9,7** et rendrait tout test vide de
sens.

**Substitut retenu : le témoin nul à pleine masse.** Un troisième jeu, `v9n` : même liste de
365 jours, graine `meteo_v3n`. Il porte la même quantité de re-tirage que le traitement
(49,3 % de bascules contre 49,4 %) et **aucun** changement de distribution. Son Δ est donc
le plancher de bruit à la bonne masse, et il coûte un bras d'A/B de plus — le prix à payer
pour que le chiffre veuille dire quelque chose. Sans lui, ce ticket produit un nombre non
opposable.

---

## Le bulletin enrichi — troisième livrable

La ligne météo du prompt ne porte aujourd'hui que la température du créneau de départ, la
condition, et un cumul de précipitations. Elle ne dit ni **quand** il pleut dans la journée,
ni **quelle amplitude** thermique attend l'agent, ni **s'il fera nuit** au retour — trois
informations qu'un humain consulte avant de sortir un vélo.

**Forme validée le 2026-08-25**, sur données réelles :

| | |
|---|---|
| Avant | `Météo : 2°C, Partiellement nuageux. Précipitations prévues dans la journée : 0,2 mm.` |
| Après | `Météo : 2°C, Partiellement nuageux. Aujourd'hui 2°C à 7°C, lever 07:55, coucher 17:25. Pluie prévue en soirée (0,2 mm sur la journée).` |

Le cadre du jour couvre la **journée entière**, créneaux déjà passés compris : c'est un
cadrage (« quelle journée fait-il »), distinct de la ligne « Météo plus tard » qui, elle,
ne porte que les créneaux restants.

### Ce que la source permet, et ce qu'elle ne permet pas

`SUNRISE`, `SUNSET`, `MIN_TEMPERATURE_C` et `MAX_TEMPERATURE_C` existent dans
`data/weather/meteo_toulouse_12_mois.csv` mais **ne sont lues par personne** aujourd'hui.

Il n'existe en revanche **aucune colonne de probabilité de précipitation**. Un « risque de
pluie » en pourcentage serait fabriqué — le motif *vacuité ≠ perfection* que le dépôt
traque. Ce qui est dérivable et factuel : **quels créneaux portent un code météo
précipitant**. C'est ce qui est retenu.

### Trois pièges relevés sur les 365 jours de la source

1. **25 jours portent des mm sans aucun créneau précipitant** (médiane 0,2 mm, max 2,5 mm ;
   2 jours au-dessus de 1 mm). Un bulletin purement par créneaux y dirait « Pas de
   précipitations prévues » là où la production annonce aujourd'hui un cumul — une **perte**
   d'information. Repli obligatoire sur la formulation actuelle : la forme enrichie
   **ajoute, n'enlève jamais**.
2. **30 créneaux sur 1 460 sortent de `[MIN, MAX]` de la source**, jusqu'à 3 °C, tous de
   nuit. Sans correction le prompt s'auto-contredirait (`Météo : 11°C … Aujourd'hui 13°C à
   20°C`). Les bornes du jour sont élargies aux créneaux effectivement lus ; la source n'est
   pas modifiée.
3. **La neige n'apparaît qu'un jour sur 365.** La branche « Neige prévue … » existera et ne
   se déclenchera quasiment jamais. Elle est conservée : sa vacuité est précisément le motif
   à ne pas masquer.

### L'ordre d'implémentation n'est pas négociable

Le changement atterrit **d'abord dans la production** (`weather_loader.weather_to_natural_language`),
**puis** dans la recopie de `prompt_calibration/calibration/weather.py`. Le test d'égalité
des deux sorties (`tests/test_weather.py`) est le garde-fou : s'il échoue, on calibre un
prompt que la simulation ne peut pas produire, et la mesure ne porte plus sur rien.

---

## Le jeton d'exclusion — second livrable, transverse

### Pourquoi ce n'est pas de l'hygiène mais de la méthode

Le protocole le dit déjà, au § « second piège » : *« Un Δ placebo anormalement grand ne dit
rien du traitement mais beaucoup de l'éval : température, cascade de fournisseurs,
troncature. »* Et il a constaté sur `train` *« un placebo de −0,76 pt sur les transports
collectifs, de même signe que le Δ traité, [qui] signale une dérive systématique entre bras
et non du bruit pur »*.

**Un run concurrent est une cause directe de cette dérive.** Il consomme le même quota LLM.
Quand un fournisseur sature, la cascade bascule sur le suivant — et si la bascule survient
entre le premier et le second bras, les deux bras n'ont pas été évalués par le même modèle.
Ce n'est pas du bruit : c'est un facteur confondu avec le traitement, et il est invisible
dans les agrégats. Exactement le motif que l'audit du ticket 020 a trouvé quatre fois.

Trois autres façons dont un run concurrent abîme la mesure :

| Ressource partagée | Ce qui casse |
|---|---|
| Quota LLM et cascade de fournisseurs | dérive de modèle **entre bras** |
| Store content-addressed du moteur de calibration | deux procédures écrivant sous la même clé `ds=` |
| Lien `experiments/current` | `make run` le repointe ; une archive en cours archiverait le mauvais run |

Et rappel de la règle du dépôt : **pas de dégradation scientifique**. En pénurie de quota on
attend le renouvellement ; on ne replie pas sur un modèle plus faible. Le jeton sert donc
aussi à ne pas *créer* la pénurie.

### Ce que le jeton doit faire

1. **Refuser d'être pris** si un run tourne. La sonde existe déjà et doit être réutilisée,
   pas réécrite : [`scripts/dashboard/live.py`](../../scripts/dashboard/live.py)
   `run_process()` détecte le launcher headless et l'IHM GAMA par `pgrep`, avec les mêmes
   motifs que `make run`. Compléter par l'état des services (`docker compose ps` sur
   `controller` / `worker`).
2. **Enregistrer un instantané de quota à la prise et au relâchement**, via
   `live.api_health()` (les quotas par fournisseur sont déjà exposés sur
   `http://localhost:8000/health`). C'est ce qui permet de **détecter après coup** une
   consommation concurrente qu'on n'aurait pas su bloquer — et donc de savoir si une mesure
   est à jeter.
3. **Porter qui, quoi, depuis quand** : hôte, utilisateur, PID, sujet de la procédure,
   horodatage de prise, durée attendue. Un jeton anonyme ne se débloque pas sans risque.
4. **Détecter le jeton périmé** : si le PID n'existe plus, le jeton est déclaré orphelin et
   sa levée est proposée — jamais automatique et silencieuse. Un jeton qui se libère seul
   n'est pas un verrou.
5. **Être exigé par les scripts du protocole.** `ab_terminal.py`, `ab_chaine.py`,
   `ab_car_availability.py` et les futurs A/B refusent de démarrer sans jeton détenu, sauf
   `--dry-run` — qui ne dépense rien et doit rester utilisable à tout moment.

### La limite qu'il ne faut pas cacher

**Un verrou local ne couvre pas la campagne cloud.** La calibration génétique tourne en
autonomie sur une VM Google Cloud, avec son propre quota et son propre déclenchement
hebdomadaire. Un fichier de verrou sur le poste ne l'atteint pas.

Trois réponses possibles, à trancher dans l'axe D4 — et **ne pas prétendre que le jeton
local résout ce cas** :

- une entrée obligatoire de liste de contrôle à la prise du jeton (« campagne cloud en
  pause ? »), la plus honnête et la moins coûteuse ;
- un marqueur partagé que les deux côtés lisent ;
- la comparaison des instantanés de quota avant/après, qui **détecte** la consommation
  concurrente sans la prévenir — un filet, pas un verrou.

---

## Les axes à instruire

| # | Axe | Question | Attendu |
|---|---|---|---|
| D1 | **Définition de la fenêtre** | Filtrer sur mois-jour, ou reconstruire les dates réelles de l'enquête ? | Mois-jour, en réutilisant `population_reference.survey_window()`. ⚠ **La fenêtre franchit le 1er janvier** : le test est `>= début OU <= fin`, jamais un intervalle simple. Un test du ticket 020 couvre déjà ce piège |
| D2 | **Vacances scolaires** | L'enquête les exclut ; le CSV météo ne les connaît pas. Les retirer du tirage ? | Chiffrer d'abord la part de jours concernée, puis trancher. Retirer les congés de Noël retire aussi les jours les plus froids : à ne pas faire à l'aveugle |
| D3 | **Graine et nom de version** | Réutiliser `meteo_v2` ? | **Non.** Graines `meteo_v3` (traitement) et `meteo_v3n` (témoin nul), jeux **`v10`** et **`v9n`**. ⚠ **`v8` est déjà pris** — c'est la réécriture `car_availability` du [ticket 018](ticket_018_partage_voiture_foyer.md), `derived_from: v7`. Le piège de second ordre du protocole s'appliquait donc à ce ticket même : la clé d'éval porte `ds=<nom>`, pas une empreinte du contenu — réutiliser `v8` aurait fait servir l'éval d'un tout autre jeu, sans que le store le détecte |
| D4 | **Portée du jeton** | Local seulement, ou partagé avec la VM ? | Local outillé, cloud en liste de contrôle explicite. La limite est écrite, pas contournée |
| D5 | **Plancher de bruit** | Placebo du protocole, ou témoin nul ? | **Témoin nul à pleine masse** `v9n` (cf. plus haut). Le placebo ne pèse que 1,05 %, soit 19 enregistrements |
| D6 | **Jeu de lecture** | Quels jeux, et sont-ils indépendants ? | **`train` + `val` de `v9` et rien d'autre** — 1 810 enregistrements, 613 personas. Ajouter `screen` ou `rank` compte double (`rank ⊂ screen ⊂ train`) : c'est le défaut de la pré-mesure `v7`, 519 lignes dupliquées sur 2 087. Filiation à relire sur le manifeste de `v9` (`rank_salt: ga_rank_v9`, `screen_share_of_train: 0,2807`) et **non sur celui de `v7`** : `v9` est un jeu neuf tiré d'un run neuf, pas un dérivé. `val` est le seul réellement indépendant. `test` reste fermé, les scripts le refusent. ⚠ `v7` et `v9` partagent 89 % de leurs personas — ne pas écrire « substrats indépendants » |
| D7 | **Périmètre livré = périmètre mesuré** | La régénération touche-t-elle autre chose que la météo ? | Diff strict. C'est le piège principal du protocole, qui a coûté la moitié d'un chiffre publié sur le temps terminal |

---

## Lots

1. **Lot 1 — Le jeton (à livrer en premier).**
   `scripts/protocol_lock.py` + `make protocol-lock SUBJECT=…`, `make protocol-unlock`,
   `make protocol-status`. Fichier de verrou sous `experiments/` (déjà gitignoré), portant
   hôte, utilisateur, PID, sujet, prise, durée attendue et les deux instantanés de quota.
   Refus de prise si `live.run_process().active`, ou si `controller` / `worker` tournent.
   Détection de jeton orphelin sans levée automatique. Tests : prise, double prise refusée,
   refus sur run actif, orphelin détecté, relâchement idempotent.

2. **Lot 2 — Les scripts du protocole exigent le jeton.** Un garde-fou partagé dans
   `prompt_calibration/`, appelé par tous les `ab_*.py`, qui laisse passer `--dry-run` et
   refuse le reste sans jeton. ⚠ `prompt_calibration` est un **dépôt git autonome** : le
   garde-fou doit fonctionner sans le dépôt principal sur le `sys.path` — comme
   `weather.py` recopie la mise en forme météo pour la même raison, avec un test qui
   compare les deux.

3. **Lot 3 — La fenêtre (étape 1 du protocole).** `WeatherDeck.load` accepte une fenêtre,
   lue depuis `population_reference.survey_window()` du côté du dépôt principal et gelée
   dans le manifeste du côté autonome. Publier avec la loi son **contrôle de validité** :
   152 jours retenus sur 365, et la distribution de température et de précipitation des deux
   fenêtres — sans quoi un tirage vide serait indistinguable d'un tirage juste.

4. **Lot 4 — Le bulletin enrichi.** D'abord `weather_loader` côté production
   (lever/coucher, min/max élargies aux créneaux, créneaux précipitants, repli sur le cumul
   quand aucun créneau n'est précipitant), puis la recopie dans `calibration/weather.py`,
   puis `tests/test_weather.py` qui compare les deux sorties. Tests dédiés sur les trois
   pièges : les 25 jours à mm orphelins, un créneau hors bornes, le jour de neige.

5. **Lot 5 — Les jeux (étape 2).** Quatre jeux, et les quatre sont nécessaires :

   | Jeu | Tirage | Bulletin | Rôle |
   |---|---|---|---|
   | `v9` | année, `meteo_v2` | actuel | substrat de référence (existant) |
   | `v10` | fenêtre, `meteo_v3` | actuel | traitement — la fenêtre seule |
   | `v9n` | année, `meteo_v3n` | actuel | témoin nul — le plancher de bruit |
   | `v10b` | fenêtre, `meteo_v3` | enrichi | traitement — fenêtre + bulletin |

   `--dry-run` d'abord. **Une seule variable bouge par paire** : la ligne de contexte météo,
   la ligne « Météo plus tard » du même jour tiré, et rien d'autre. La mécanique de
   réécriture existe déjà — `rewrite_car_availability.py` a produit `v8` de cette façon.

6. **Lot 6 — L'A/B (étape 3).** Jeton pris, `--dry-run` pour chiffrer, modèle d'éval
   **épinglé** (`assert_pinned_eval_model`), comparatif apparié, effectif opposable = personas
   distincts (613 hors `test`). Quatre bras : `v9` / `v10` / `v9n` / **`v10b`** (fenêtre +
   bulletin enrichi, cf. le lot 4). Les bras `v10` et `v10b` ne diffèrent que par la
   forme du bulletin : c'est ce qui rend les deux corrections séparables alors qu'elles sont
   livrées ensemble.

7. **Lot 7 — Archiver et publier (étape 4).** `archive_ab.py --out ../docs/traces/<date>_fenetre_meteo`,
   puis la page horodatée. Les instantanés de quota du jeton entrent dans l'archive : c'est
   la preuve qu'aucun run concurrent n'a tourné.

8. **Lot 8 — Porte de décision (étape 5).** Adoption, rejet ou report. **Le rejet est une
   issue normale et s'archive autant que l'adoption.** En cas d'adoption : garde-fou de
   non-régression qui refuse un retour au tirage sur l'année.

---

## Critères d'acceptation

- [ ] Aucun appel LLM n'est passé sans **jeton détenu**, et l'archive porte la preuve
      (instantanés de quota à la prise et au relâchement).
- [ ] Le jeton **refuse d'être pris** quand un run tourne, et la détection réutilise
      `live.run_process()` — pas une seconde implémentation de `pgrep`.
- [ ] La limite du jeton sur la **campagne cloud** est écrite dans sa documentation et dans
      sa sortie, pas seulement dans ce ticket.
- [ ] Un jeton orphelin est **signalé**, jamais levé automatiquement.
- [ ] Le filtre de fenêtre teste `>= début OU <= fin` (elle franchit le 1er janvier), et un
      test le vérifie sur un jour de décembre **et** un jour de janvier.
- [ ] Le nouveau jeu porte un **nouveau nom** (`v10`, car `v8` et `v9` sont pris) et une
      **nouvelle graine** (`meteo_v3`). Un test vérifie qu'aucune éval en cache d'un nom
      réutilisé ne peut être servie.
- [ ] Le plancher de bruit est le **témoin nul à pleine masse** `v9n`, pas le canal placebo
      à 1,05 %. Toutes les colonnes sont publiées.
- [ ] **Aucune conclusion sur la pluie.** Le Δ mesuré **change de signe entre substrats**
      (−1,20 pt sur `v7`, +1,10 pt sur `v9`) pour un plancher de bruit de −1,16 pt : le
      ticket doit le dire explicitement et refuser d'en tirer un effet, quel que soit le
      résultat de l'A/B.
- [ ] Le bulletin enrichi **n'enlève jamais d'information** : les 25 jours sur 365 portant
      des mm sans créneau précipitant gardent la formulation actuelle. Un test le vérifie.
- [ ] Les bras `v10` et `v10b` ne diffèrent **que** par la forme du bulletin, de sorte que
      fenêtre et bulletin restent séparables bien que livrés ensemble.
- [ ] Le diff du jeu et le diff de production portent sur **les mêmes lignes**. Si le
      périmètre livré dépasse le périmètre mesuré, il est dit et mesuré.
- [ ] La trace est committée dans `docs/traces/`, y compris en cas de rejet.
- [ ] La filiation des jeux est vérifiée avant de parler de réplication (`rank ⊂ screen ⊂
      train` ; `val` est le seul jeu réellement indépendant).
- [ ] **Aucun enregistrement n'est compté deux fois.** La lecture porte sur `train` + `val`
      et jamais sur `screen` ou `rank`, qui en sont des sous-ensembles. Un test le vérifie.
- [ ] Le mot « indépendant » n'est employé qu'après recoupement chiffré. `v7` et `v9`
      partagent 89 % de leurs personas ; ce sont leurs **clés de tirage** qui sont disjointes
      à 99 %, et c'est cela seul que la réplication établit.

## Hors périmètre

- **La variance d'un run de simulation.** L'axe A5 du ticket 020 porte *deux* défauts. Ce
  ticket ne corrige que celui des jeux gelés. L'autre — un run de cinq jours comparé à une
  moyenne de 152 — **n'est pas corrigeable par un choix de dates** : 27,7 % des séquences de
  cinq jours de la période d'enquête sont elles aussi entièrement sèches. C'est une limite de
  variance, elle reste à publier, et **ce ticket ne la ferme pas.**
- **La météo de production.** `weather_loader` continue d'apparier par mois-jour sur l'année
  entière. La simulation doit pouvoir se jouer n'importe quand ; c'est la **mesure** qui doit
  parler de la fenêtre de l'enquête.
- **Les vacances scolaires**, si l'axe D2 conclut à ne pas les retirer. La décision est dans
  le périmètre, son implémentation ne l'est pas nécessairement.
- **Un « risque de pluie » en pourcentage.** La source ne porte aucune probabilité de
  précipitation. L'obtenir supposerait de re-collecter la météo auprès d'une API qui en
  expose une, et de regeler la source — ce qui invaliderait tous les jeux existants. Autre
  ticket.
- **Un verrou distribué** couvrant la VM cloud. Le lot 1 livre un verrou local et documente
  sa limite ; un verrou partagé est un autre ticket.

## Ce qu'il faut savoir avant de commencer

- **La correction est petite et thermique.** −4,74 °C sur `v9` (−4,90 °C sur `v7`), pas de
  mouvement opposable sur la pluie. Ne pas dimensionner l'effort sur l'espoir d'un gros effet : l'issue la plus probable
  est un Δ de composite faible, et **le rejet est une issue normale du protocole**. Ce qui
  justifie le ticket n'est pas l'ampleur attendue, c'est que la mesure sera enfin faite sur
  la fenêtre de sa cible.
- **49,4 % des enregistrements basculent pluie ⇄ sec** alors que l'agrégat ne bouge que de
  1,1 point — et le témoin nul, qui ne change rien à la distribution, en brasse 49,3 %. Le
  brassage individuel est énorme, l'effet agrégé minuscule : c'est la configuration où l'on
  lit du signal dans du bruit. D'où le témoin nul, non négociable.
- **Le substrat a changé le 2026-08-25.** La base n'est plus `v7` mais `v9`, tiré du [run de
  référence](../traces/2026-08-25_run_reference/README.md) `2026-08-24_17_34`. Toute la
  pré-mesure ci-dessus a été rejouée sur `v9` ; les chiffres `v7` ne sont conservés que
  comme réplication.
- **Le ticket 008 A7 a déjà fait le gros du travail.** Ne pas le présenter comme une
  découverte : le tirage dans l'année a supprimé le défaut grave (cinq valeurs toutes
  sèches). Ce ticket rétrécit la fenêtre, rien de plus.
- **Modèle d'éval épinglé, et stable sur toute la branche.** Un alias flottant mélangerait
  deux modèles sous une même clé de cache, et changer de modèle en cours de branche détruit
  le cache d'éval déjà payé.

## Sources

- [`docs/arch/protocole-parametre-exogene.md`](../arch/protocole-parametre-exogene.md) — la
  procédure à suivre, ses cinq étapes et ses deux pièges documentés.
- [ticket 020](ticket_020_perimetre_population_cerema.md), axe A5, et
  [`docs/arch/perimetre-population.md`](../arch/perimetre-population.md) — la mesure
  d'origine et sa révision du 2026-08-24.
- [ticket 008](ticket_008_run_24h_mesures_synthese.md), action A7 — le tirage dans l'année,
  qui a supprimé le défaut grave des jeux `v1`.
- [`prompt_calibration/calibration/weather.py`](../../prompt_calibration/calibration/weather.py)
  — `WeatherDeck`, `DEFAULT_SEED`, et la raison de la recopie de mise en forme.
- [`scripts/dashboard/live.py`](../../scripts/dashboard/live.py) — `run_process()` et
  `api_health()`, les sondes à réutiliser pour le jeton.
- [`llm_module/core/population_reference.py`](../../llm_module/core/population_reference.py)
  — `survey_window()`, source unique de la fenêtre (`2022-09-20` → `2023-02-18`).
- [`docs/traces/2026-08-25_run_reference`](../traces/2026-08-25_run_reference/README.md) — le
  run qui a changé le substrat de `v7` à `v9`, et les cinq limites qu'il documente.
- [`prompt_calibration/calibration_datasets/v9/manifest.yaml`](../../prompt_calibration/calibration_datasets/v9/manifest.yaml)
  — le substrat courant ; `v8` y est occupé par la réécriture `car_availability`.
- [Méthodologie des Enquêtes Mobilité Certifiées Cerema](https://www.cerema.fr/fr/actualites/enquetes-mobilite-certifiees-cerema-methodologie)
  — « déplacements de la veille », période de collecte, exclusion des congés.
