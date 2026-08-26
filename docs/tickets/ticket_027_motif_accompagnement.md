# Ticket 027 — `other` : un motif à 8 % des déplacements, effacé par une ligne de correspondance

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source
> de vérité. Ce qui suit est une **spécification**. Pendant du
> [ticket 018](ticket_018_partage_voiture_foyer.md) sur un autre attribut : un objet que
> l'enquête décrit et que la chaîne de génération perd avant d'atteindre l'agent.

## Le problème, en une mesure

Le motif de destination servi au LLM vaut `other` pour **19 % des décisions** du jeu gelé, et
la dimension notée `motif` est **vide pour 59,9 %** d'entre elles (`home`, `other` et
`leisure` n'ont pas de correspondance EMC²). Or `other` n'est pas un résidu : il est aux deux
tiers un motif que l'enquête documente, et le plus routier de tous.

Composition mesurée sur les **54 585 déplacements** de l'EMC² Toulouse 2023 (`D5A`,
`fichiers_standards`), pour les 6 797 déplacements (12,5 %) que la chaîne replie sur `other` :

| Code `D5A` | Libellé de l'enquête | Effectif | Part de `other` |
|---|---|---:|---:|
| 61 | Accompagner quelqu'un (personne présente) | 2 270 | 33,4 % |
| 64 | Aller chercher quelqu'un (personne absente) | 1 927 | 28,4 % |
| 41 | Recevoir des soins (santé) | 1 233 | 18,1 % |
| 42 | Faire une démarche autre que rechercher un emploi | 812 | 11,9 % |
| 91 | Autres motifs | 204 | 3,0 % |
| 71 | Déposer une personne à un mode de transport | 180 | 2,6 % |
| 74 | Reprendre une personne à un mode de transport | 126 | 1,9 % |
| 43 | Rechercher un emploi | 45 | 0,7 % |

**L'accompagnement (61, 64, 71, 74) fait 4 503 déplacements — 66,2 % de `other` et 8,2 % de
tous les déplacements de l'enquête.** Santé et démarches en font 30,7 %.

Et c'est le motif le plus dépendant de la voiture de toute la référence :

| Motif EMC² | voiture | marche | TC | vélo |
|---|---:|---:|---:|---:|
| **accompagnement** | **70** | 23 | 2 | 3 |
| travail | 70 | 7 | 12 | 8 |
| achats | 58 | 31 | 6 | 3 |
| études | 26 | 27 | 39 | 5 |

(`cerema_values.yaml`, `motif_deplacement`.) Un déplacement d'accompagnement est donc à la
fois massif, très routier, et aujourd'hui invisible — ni nommé dans le prompt, ni noté.

## Où l'information est détruite

Pas chez nous : dans le pipeline eqasim, et en une ligne. La table qui traduit les motifs de
l'enquête vers le vocabulaire du projet replie **trois familles** sur `other`
([entd/cleaned.py:15](../../eqasim-toulouse/data/hts/entd/cleaned.py)). Comptées sur les
132 879 déplacements de l'ENTD 2008, la source effectivement configurée (`hts: entd`) :

| Famille ENTD | Trajets | Part de `other` | Destin |
|---|---:|---:|---|
| 6 — accompagnement | 6 947 | 60,6 % | → `other` |
| 4 | 2 335 | 20,4 % | → `other` |
| 3 | 2 184 | 19,0 % | → `other` |

**La famille 6 est bien l'accompagnement, et le recoupement est indépendant de la
nomenclature** : la source porte une colonne dédiée `V2_MMOTIFDACC` (motif d'accompagnement),
renseignée sur 3 759 déplacements — dont **3 743 dans la famille 6**, et 16 ailleurs.

Projection sur nos données : ~288 des 476 activités `other` de la population du run
`2026-08-24_17_34`, et ~208 records du jeu gelé `all`, soit **11,5 % du jeu**.

## Ce que le dépôt fait déjà, et où ça s'arrête

Le côté **score est déjà câblé**. `MOTIF_MAP` porte `"escort": "accompagnement"`
([frames.py:101](../../scripts/synthesis/frames.py:101)) et la cible EMC² est dans
`cerema_values.yaml`. La dimension attend un motif qui n'arrive jamais.

Le côté **simulation ne branche sur rien**. Une recherche sur `purpose ==` / `purpose in (`
dans `llm-agents` et `llm_module` ne trouve que du code commenté : le motif est une étiquette
qui traverse la chaîne et arrive telle quelle dans l'en-tête de section du prompt
(`Destination : other`). **Une valeur neuve ne casse aucune logique aval.**

Il manque donc exactement deux lignes de correspondance :

- `DEST_TO_MOTIF` du constructeur de jeux gelés
  ([metadata.py:65](../../prompt_calibration/calibration/metadata.py:65)) : ajouter
  `"escort": "accompagnement"` ;
- la table de motifs d'eqasim : arrêter d'écraser l'accompagnement.

Et un obstacle réel : eqasim tire les **lieux** des activités secondaires par motif, depuis
des viviers `offers_shop`, `offers_leisure`, `offers_other`
([locations.py:55](../../eqasim-toulouse/synthesis/population/spatial/secondary/locations.py:55),
[facilities.py:91](../../eqasim-toulouse/matsim/scenario/facilities.py:91)). Un motif neuf
sans vivier casse l'affectation des lieux.

## Spécification — deux options, coût sans commune mesure

### Option A — le patch : arrêter d'écraser l'accompagnement

Garder `hts: entd` et sortir la famille 6 de `other`. Concrètement :

- `PURPOSE_MAP` d'ENTD : `("6", "escort")` au lieu de `("6", "other")` ;
- faire pointer `escort` sur le vivier de lieux `other` — un accompagnement se fait vers une
  école, une gare, un domicile de proche, donc les mêmes équipements ;
- `DEST_TO_MOTIF` côté jeux gelés : `"escort": "accompagnement"` ;
- rejouer le pipeline eqasim (invalidation du cache), puis un run.

Le prompt dirait alors `Destination : escort`, et la dimension `motif` gagnerait une strate
peuplée à ~11,5 % du jeu, avec sa cible déjà publiée.

**Ce que l'option A ne corrige pas** : les chaînes d'activités restent celles de l'**ENTD
2008** — une enquête **nationale**, vieille de quinze ans, alors que la référence contre
laquelle on se note est locale et de 2023. Les familles 3 et 4 (39 % de `other`, santé et
démarches) resteraient indistinctes, faute de cible EMC² pour les scorer.

### Option B — le substrat : brancher l'enquête locale comme source de chaînes

eqasim sait lire les enquêtes françaises **standardisées** via son lecteur `mobisurvstd`, et
sa table de motifs porte cette ligne :

```python
PURPOSE_MAP = {…, "escort": "other", …}   # mobisurvstd/cleaned.py:28
```

Autrement dit : **l'accompagnement est un motif de première classe du format standard**, et
eqasim le jette délibérément. Or nos fichiers PROGEDO sont précisément à ce format
(`Toulouse_2023_std_depl.csv`, `…_men`, `…_pers`, `…_traj`).

Basculer `hts: entd` → `mobisurvstd` sur l'EMC² Toulouse 2023 ferait venir de l'enquête
**locale et récente** l'ensemble des chaînes d'activités — horaires, motifs, distances,
enchaînements — et l'accompagnement arriverait par construction, en changeant `"escort":
"other"` en `"escort": "escort"`.

C'est un chantier de substrat, pas un correctif : nouvelle population, nouveau run, nouveaux
jeux gelés, et la comparabilité de toute la série de runs à re-établir. Mais c'est l'écart de
fond — aujourd'hui la simulation apprend ses journées d'une enquête qui n'est ni du bon
territoire ni de la bonne décennie.

### Ce qui n'est pas une option

**Rattraper après coup.** L'information est détruite en amont : la population du run et tous
les jeux gelés portent `other`, sans trace du motif d'origine. Aucun post-traitement ne la
reconstruit — contrairement à la couronne de résidence du
[ticket 021](ticket_021_couronne_residence_post_traitement.md), qui se recalculait depuis la
commune du domicile. Il faut régénérer la population.

**Recommandation** : l'option A d'abord, parce qu'elle est petite, qu'elle peuple une
dimension notée et qu'elle rend le prompt plus informatif pour 11,5 % des décisions. L'option
B ensuite, comme chantier propre, parce qu'elle est la bonne réponse à une question plus large
que ce ticket.

## Méthode de test — et pourquoi le protocole ne suffit pas ici

Le [protocole de paramètre exogène](../arch/protocole-parametre-exogene.md) ne sait **pas**
mesurer ce ticket, et il faut le dire d'emblée : réécrire un jeu gelé ne change pas quel motif
la population a produit. On ne peut pas fabriquer un bras `escort` en réécrivant `other` —
il faudrait savoir *lesquels* des `other` sont des accompagnements, information absente du
jeu.

Deux conséquences :

- l'effet ne se chiffre qu'**après** un run sur une population régénérée, donc au prix d'un
  run complet — c'est le cas contraire du ticket 018, dont le protocole savait trancher le
  narratif à coût quasi nul ;
- une mesure **partielle** reste possible et gratuite : réécrire l'en-tête `Destination :
  other` en `Destination : escort` sur un échantillon tiré au hasard des `other`, à hauteur de
  66 %, mesure la sensibilité du LLM au **libellé** seul. Ça ne dit rien de la justesse de
  l'affectation, mais ça borne le gain narratif atteignable — et si ce gain est nul, l'option
  A ne vaut plus que pour la dimension notée.

**Vigilance de niveau** : la campagne du ticket 024 a montré que le modèle réagit à la **mise
en forme** du contexte plus qu'à son contenu (témoin nul de reformulation : 2,03 de composite,
plus que le retrait de tout le contexte : 2,52). Changer un libellé de motif est un changement
de mise en forme : son effet mesuré devra être lu contre ce plancher-là, pas contre zéro.

## Critères d'acceptation

- [ ] la dimension `motif` est renseignée pour la part attendue des décisions : ~11,5 % en
      `accompagnement`, contre 0 aujourd'hui
- [ ] la part d'accompagnement dans les déplacements simulés vaut **8,2 %** (± 2 pts), valeur
      recalculée depuis `D5A` et non reprise de ce ticket
- [ ] le motif est identique de bout en bout : population, `moves.csv`, prompt, dimension notée
- [ ] les lieux d'accompagnement sont tirés d'un vivier explicite, jamais laissés vides
- [ ] les familles restées dans `other` (santé, démarches) sont **comptées et nommées** dans
      la documentation, pas silencieusement fondues
- [ ] aucune cible atteinte par absence de mesure — un `motif` vide n'est pas un `motif` juste

## Hors périmètre

- **Le trajet du conducteur accompagnant** : décision D5 du ticket 008, et elle mord ici. Un
  enfant conduit à l'école ne génère pas le déplacement du parent — donc même avec le motif
  correct, le déplacement d'accompagnement du parent reste absent des chaînes. À traiter
  ensemble si l'option B est retenue.
- **La ventilation santé / démarches** : aucune cible EMC² publiée par motif pour ces
  familles ; les distinguer n'apporterait qu'un libellé, sans axe de recette.
- **Le choix du mode** : ce ticket nomme un motif, il ne contraint aucune option.

## Sources

- Microdonnées **EMC² Toulouse 2023**, ProGEDO/ADISP `lil-1750` —
  `lil-1750-Donnees_CSV/fichiers_standards/Toulouse_2023_std_depl.csv`, variable `D5A`
  (54 585 déplacements) ; libellés de modalités dans
  `lil-1750-Documentation/LABELS/SAS/Toulouse_2023_std_depl_modalites_SAS_lil-1750.txt`.
- **ENTD 2008**, `eqasim-toulouse/data/entd_2008/K_deploc.csv` — `V2_MMOTIFDES` (132 879
  déplacements) et `V2_MMOTIFDACC` pour le recoupement de la famille 6.
- `eqasim-toulouse/data/hts/entd/cleaned.py` et `…/mobisurvstd/cleaned.py` — les deux tables
  de correspondance des motifs.
- Jeu gelé `all` de `v9` (1 810 décisions) et population du run
  `experiments/archive/2026-08-24_17_34` pour les projections.
