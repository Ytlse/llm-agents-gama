# Synthèse des scores — trois volets face à l'enquête EMC² 2023

Page HTML autonome qui compare la fidélité des parts modales produites par trois
approches, globalement et dans chaque sous-catégorie de l'enquête CEREMA.

**Régénérer :**

```bash
make synthesis
```

La cible commence par **rapatrier le store de la campagne cloud** depuis la VM
(`make -C prompt_calibration pull-db` → `calibration_cloud.db`) : la campagne
tourne là-bas en continu, et sans ce pull le volet calibration refléterait un
instantané local périmé sans le signaler. Si la VM est injoignable (éteinte,
`gcloud` absent, hors-ligne), la synthèse avertit bruyamment (`[ALARME]`) et
continue sur l'instantané local en affichant sa date. Pour sauter le pull
explicitement : `make synthesis PULL=0`.

Sortie : `docs/synthesis/index.html` (page) et `docs/synthesis/data.json`
(toutes les valeurs, pour réutilisation), plus deux **pages dédiées** qui
extraient le seul sous-chapitre « Détail par sous-catégorie » :
`docs/synthesis/detail_simulation.html` (volet 1) et
`docs/synthesis/detail_progedo.html` (volet 3). La page complète les conserve —
les pages dédiées la dupliquent, elles ne l'amputent pas — et y renvoie depuis le
sommaire et depuis chaque sous-chapitre concerné. Elles sont écrites dans le même
dossier que `index.html` (archive comprise), pour que les liens relatifs tiennent.
Elles n'ont **pas** de sommaire latéral — un seul chapitre à afficher, autant laisser
la pleine largeur aux graphiques ; les renvois vers la synthèse et vers l'autre page
dédiée tiennent sur une ligne en tête.
Le rendu des cellules est produit par le **même** `_dimension_blocks()` que la
page complète : aucun chiffre n'est recopié, et une page dédiée ne peut pas
diverger du volet dont elle est extraite.

### Les pages « alternative » — le même volet 1, sous un autre prompt

`docs/synthesis/detail_simulation_26_08_alternative<1..10>.html` reprennent la forme de
`detail_simulation.html` sur un run dont **495 décisions ont été rejouées** : celles où le
modèle a retenu un transport collectif alors que la marche lui était proposée. Chaque page
affiche en entier le prompt système modifié qui les a produites.

Elles sont écrites par `make alt-prompt-pages`, jamais par `make synthesis` : leur substrat
n'est pas le run tel qu'il a tourné. Le sous-chapitre de détail y est rendu par le **même**
`_dimension_blocks()` et scoré par le **même** `Scorer` — une alternative ne peut donc pas
diverger de la page dont elle dérive. Le protocole, ses quatre réserves de lecture et le
piège d'appariement `moves.csv` ↔ `llm_exchanges.jsonl` sont dans
[report-marche-tc.md](report-marche-tc.md).


### Une page de détail datée, pour un run non épinglé

`docs/synthesis/detail_progedo_26_08.html` est le volet 3 mesuré sur
`experiments/archive/2026-08-26_17_46` sans toucher au run épinglé. La recette vaut pour
n'importe quel run — elle tient en un manifeste jetable, parce que `model_on_common_set`
n'a pas de `--run` (il lit `common_set.run` du manifeste) :

```bash
sed -e 's|^  run: .*|  run: experiments/archive/<run>|' \
    -e 's|^    predictions: .*|    predictions: scripts/synthesis/data/progedo_on_common_set_<run>.parquet|' \
    scripts/synthesis/sources.yaml > /tmp/sources_<run>.yaml
python -m scripts.synthesis.model_on_common_set --config /tmp/sources_<run>.yaml
python -m scripts.synthesis.build --config /tmp/sources_<run>.yaml \
    --out /tmp/out/index.html --json /tmp/out/data.json
cp /tmp/out/detail_progedo.html docs/synthesis/detail_progedo_<date>.html
```

Deux points la rendent sûre plutôt que commode :

- **le parquet de sortie est renommé**, sinon la mesure du run épinglé est écrasée et la garde
  de substrat écarte le volet 3 de `index.html` à la régénération suivante — silencieusement du
  point de vue de celui qui voulait juste une page de plus ;
- **la construction passe par un dossier hors dépôt**, parce que `build.py` écrit toujours
  `detail_simulation.html` et `detail_progedo.html` à côté de son `--out` : bâtir directement
  dans `docs/synthesis/` remplacerait les pages publiées.

⚠ **La page ne nomme pas son run.** `render_detail()` n'affiche que la date de génération, et
ses liens de retour (`index.html`, `detail_simulation.html`) pointent vers la synthèse du run
**épinglé**. Une page datée ainsi extraite ne se relit donc qu'accompagnée de l'entrée de
changelog qui dit sur quel run elle porte.

---

### `avancement_et_resultats.html` — le journal des mesures

`make avancement` produit une page distincte des précédentes, et la distinction
est le point : `index.html` score un **run** de simulation, cette page-ci
journalise les **mesures sur jeux gelés** — « base de référence → base modifiée →
modification → résultat → score », une ligne par correction testée.

Sa source unique est `scripts/synthesis/avancement.yaml`. Une ligne n'existe que
si la mesure a été **faite** : le registre n'est pas un plan, sinon la page
devient une liste d'intentions et cesse de dire ce qui est établi.

Le rendu **refuse d'écrire** — bruyamment, code de sortie 1 — si une trace citée
n'existe pas sur le disque, si un champ obligatoire manque, ou si un verdict sort
du vocabulaire (`adopte` / `mesure` / `rejete` / `encours`). Une page de résultats
qui se dégrade en silence est pire qu'une page absente. `make avancement CHECK=1`
valide sans écrire.

Les mesures sont affichées **de la plus ancienne à la plus récente**, et cet ordre est
**calculé par le rendu**, pas hérité de l'ordre de saisie du registre : une ligne écrite en
tête du YAML remontait en tête de page quelle que soit sa date. Le résumé imprimé en console
passe par la même fonction que la page : les deux ne peuvent pas annoncer deux chronologies
différentes. Corollaire : `date` est validée au format `AAAA-MM-JJ`, et une date mal formée
est un **refus** — elle trierait de travers en silence.

**À date égale, l'heure du document lié départage** — le registre ne porte qu'un jour, et
plusieurs mesures tombent le même. L'heure est celle de la **synthèse intermédiaire** quand
la ligne en cite une (c'est la page que la mesure a fait bouger), sinon celle du HTML de sa
trace, sinon celle du dossier de trace. Elle s'affiche en regard de la date
(`ticket 013 · 2026-08-24 à 12:03`), sa provenance en infobulle — une heure sans source ne
se vérifie pas.

Deux provenances, qui ne se valent pas :

| Source | Portée |
|---|---|
| Heure **inscrite dans la page** par son générateur (« généré le 24/08/2026 à 12:03 ») | versionnée : identique sur toutes les machines |
| À défaut, **horodatage du fichier** (création si le système la garde, sinon modification) | **git ne restitue pas les dates** : après un clone, c'est la date du clone |

La seconde ne sert donc qu'à *départager* deux mesures d'un même jour, jamais à établir la
date, qui vient du registre. Conséquence assumée : sur un clone frais, l'ordre intra-journée
des lignes sans heure inscrite peut différer — la date, elle, ne bouge pas.

Une heure n'est retenue que si le document lié **tombe le jour de la mesure**. Un document
régénéré plus tard porte une heure qui ne situe plus rien : l'afficher en regard de la date
du registre composerait un couple date/heure n'ayant jamais existé. Dans ce cas la ligne
n'affiche pas d'heure et garde sa place stable — l'absence est honnête, l'approximation ne
le serait pas.

Chaque ligne porte deux liens : sa **trace archivée** sous `docs/traces/`, et
quand elle existe la **synthèse intermédiaire** correspondante de
`docs/synthesis/`. Les synthèses voisines sont en outre **découvertes sur le
disque** plutôt que listées à la main — une liste écrite se périme au premier
instantané ajouté ; les fichiers de travail (`index copy.html` et compagnie) sont
exclus par motif, parce qu'un lien vers un brouillon fait douter de tous les
autres. Les chemins relatifs sont calculés par `os.path.relpath` et non comptés à
la main : un `../` de trop produit un lien qui a l'air juste et sort de `docs/`.

⚠ Le champ `score` n'est pas libre : c'est la grandeur sur laquelle la décision a
été prise. Quand le composite n'est **pas attribuable** — traitement minoritaire
noyé dans le bruit, cf.
[protocole-parametre-exogene.md](protocole-parametre-exogene.md) — la ligne porte
l'effet **reconstruit** et le dit dans `score_caveat`.

---

## 1. Le principe : une trame, une loss, trois adaptateurs

Les trois volets ne deviennent comparables qu'à une condition : être ramenés au
**même tableau**, puis scorés par la **même fonction**.

La trame de décision est une ligne par (décision, mode envisagé) :

| Colonne | Contenu |
|---|---|
| `agent_id` | Personne — sert d'effectif, jamais de masse |
| `mode_cat` | `marche`, `voiture`, `velo`, `transports_collectifs` |
| `weight` | Masse de probabilité accordée à ce mode (une décision somme à 1) |
| `genre`, `age_cat`, `occupation`, `motif`, `dist_cat` | Catégories EMC² |
| `lieu_residence`, `type_logement` | Affichés hors composite |
| `— hors référentiel —` | Ligne de masse d'une dimension : les catégories que la référence ne ventile pas (`hors périmètre` pour la zone, « Autres » pour le logement). Ni cible, ni L1, jamais « couverte » — elle existe pour que « exclu des cibles » ne se confonde pas avec « inexistant » |

La loss n'est **pas réimplémentée** : elle est importée de
`prompt_calibration/calibration/metrics.py` via `sys.path`. Un score affiché sur
la page est exactement celui que le moteur de calibration optimise. Si le dépôt
de calibration est absent, la page se génère quand même, sans scores, avec un
message explicite.

## 2. Le composite comparable

Le composite du moteur pondère huit dimensions, dont une `length_penalty` qui
pénalise les prompts longs. Cette dimension n'a aucun sens pour la simulation ni
pour le modèle statistique : **son poids est ramené à 0**. Tous les autres poids
sont ceux du moteur (`global` 1.0, `absent_penalty` 1.0, `age` 0.5, `occupation`
0.5, `genre` 0.3, `motif` 0.5, `distance` 0.3).

Deux losses sont rapportées : `emd_jsd` (celle qu'optimise le moteur — EMD sur
les axes ordinaux, JSD sur les nominaux) et `l1_composite`, qui s'exprime en
points de pourcentage et se lit directement.

## 3. Le jeu d'évaluation commun

Le substrat partagé est **un run de simulation**, et non les jeux de personas
gelés de la calibration. C'est le seul terrain où les trois volets peuvent se
rencontrer :

- il porte les personas complets (`population_*.json` → `traits_json`) ;
- il porte les jeux de choix OTP réellement proposés (`Modes proposés au LLM`) ;
- il porte les **coordonnées origine/destination**, dont le modèle PROGEDO a
  besoin et que les jeux gelés ont perdues (ils ne conservent que `dist_km`).

Le run est **épinglé par chemin d'archive** dans `sources.yaml`
(`experiments/archive/2026-07-29_18_34`), jamais par le symlink
`experiments/current` : celui-ci bouge à chaque simulation, et la page décrirait
alors un substrat différent d'une régénération à l'autre sans que rien ne le
signale. Deux régénérations produisent désormais les mêmes chiffres, et les
empreintes sha256 de la table de provenance permettent de le vérifier. La tuile
« Run » de la page affiche l'état de l'épinglage : si le chemin configuré se
résout ailleurs, elle avertit au lieu de se taire.

Pour évaluer un autre run sans toucher au manifeste :
`make synthesis RUN=experiments/archive/<run>`. Si le run est adopté, l'épingler
dans `sources.yaml`.

Un run **repris à chaud** (`make run OFFLINE=1 CONT=1`) est un cas particulier de ce
substrat, et il faut le connaître avant d'en épingler un : la reprise rejoue le jour
simulé depuis t0 **dans le même dossier d'expérience**. `moves.csv` porte alors deux
lignes pour la même décision — une par tentative, toutes deux datées du même jour
simulé — et la coupe au premier jour simulé ne les sépare pas. `frames.latest_attempts`
ne garde que la tentative la plus récente (troisième coupe du périmètre commun,
ci-dessous), et la page annonce qu'elle a lu un run repris ainsi que le nombre de
lignes écartées. Mesuré sur `experiments/archive/2026-08-19_14_36`, repris le
2026-08-20 : 1 469 lignes en doublon, 282 décisions comptées deux fois, et un composite
`emd_jsd` qui passait de 24,09 à 24,43 en lecture brute — 0,34 point, soit l'ordre de
grandeur des gains que la calibration cherche à mesurer.

Les jeux gelés de la calibration sont d'ailleurs eux-mêmes construits à partir
d'un run de ce type — le manifeste `calibration_datasets/v1/manifest.yaml`
enregistre le `llm_exchanges.jsonl` et le `population_1000.json` d'origine.

> **Attention au recouvrement.** Ce manifeste enregistre un chemin de symlink
> (`experiments/current/…`), pas un chemin d'archive. Le symlink a bougé depuis.
> Seule l'empreinte sha256 permet encore d'identifier le run source. Avant de
> conclure quoi que ce soit sur le volet 2, vérifier que le run choisi comme jeu
> commun n'est pas celui qui a servi à l'entraîner.
>
> **Vérification faite le 2026-07-31**, et le résultat mérite d'être connu : le
> `population_1000.json` du run épinglé est **byte-identique** à celui des jeux
> gelés (`aec28f01…`), tandis que le `llm_exchanges.jsonl` diffère
> (`c75c6a00…` contre `a8854615…`). Autrement dit, ce sont **les mêmes personnes**
> mais **d'autres déplacements** — autres destinations, autre météo, autre état de
> mémoire. Le recouvrement porte donc sur la population, pas sur les décisions : un
> score du volet 2 sur le jeu commun n'est pas une mesure hors échantillon, et ne
> doit pas être lu comme telle. Le chiffre de généralisation est celui du jeu de
> test gelé — produit depuis le 2026-07-31, cf. « Généralisation » plus bas.

### ⚠ Les jeux gelés du volet 2 peuvent ne plus porter la population du run

L'invariant « un seul substrat » est vérifié par les gardes **sur le run**. Mais le volet 2
est aussi scoré sur des **jeux gelés**, découpés dans un run antérieur, et leur manifeste
enregistre l'empreinte de la population d'origine. La page la compare désormais à celle du
run épinglé et **déclare la divergence** quand elle existe (bloc `common_set.frozen_sets` du
`data.json`, encadré dans le chapitre « Jeu d'évaluation commun »).

État au 2026-08-27 : le manifeste épingle `aec28f0146…`, le run porte `4cd38bdc19…`. Les
jeux gelés gardent l'abonnement TC et le permis **recopiés du donneur ENTD 2008**, que les
tickets 016 et 017 viennent de réécrire dans la population en service.

Ce que ça change pour la lecture : les scores du volet 2 sur jeux gelés restent comparables
**entre eux** — c'est leur rôle, suivre une trajectoire de prompt — mais pas au volet 1 ni au
volet 3, qui portent la population courante. Le témoin d'échantillon du volet 2 sur le jeu
commun est calculé sur le run et n'est pas concerné.

Divergence **déclarée et non corrigée** : refaire les jeux gelés casserait la comparabilité
de toute la trajectoire de calibration déjà mesurée. L'encadré ne s'affiche que si la
divergence existe — une mise en garde permanente cesse d'être lue.

## 4. Les trois volets

### Périmètre commun aux trois volets

Les trois volets doivent porter sur le **même** sous-ensemble du run, sans quoi la
matrice comparerait trois substrats en les annonçant comme un seul. Trois coupes,
définies une fois et appliquées à la source.

**1. Lignes sans décision modale** — `common_set.exclude_selection_methods` dans
`sources.yaml`, appliqué par `frames.read_moves` :

| Méthode exclue | Pourquoi |
|---|---|
| `Pas de déplacement (même localisation)` | Aucun trajet |
| `Pas de solution de déplacement` | Aucun mode ne relie l'OD |
| `LLM Error (Default index)` | **Ce n'est pas une décision, c'est un repli.** Le prompt n'a pas répondu ; le contrôleur prend l'itinéraire d'index 0. Sur le run de référence, 100 % de ces lignes retenaient le plus rapide, soit 64,7 % de voiture. Les garder revenait à noter le prompt sur un choix qu'il n'a pas fait |

**2. Un seul jour simulé** — le **premier** présent dans le run, jamais une date en dur.
Même quand le run est censé s'arrêter à 24 h, le bootstrap et l'horizon glissant de
planification font déborder le journal au-delà : sur le run de référence, 2 538 couples
(personne, activité) réapparaissaient un jour plus tard, 2,17 fois en moyenne, avec le
même mode dans 57,8 % des cas. Ces répétitions ne sont pas des décisions supplémentaires,
elles pèsent seulement deux fois dans les parts modales.

**Deux points d'entrée, pas un** — c'est le piège de cette coupe :

| Volet | Source | Point d'intervention | Champ |
|---|---|---|---|
| 1 et 3 | `moves.csv` | `frames.read_moves` | colonne « Temps simulé » (via `frames.simulated_day`) |
| 2 | `llm_exchanges.jsonl` | `common_set_eval.build_sample` | champ `sim_day` du journal |

Le volet 2 ne lit pas `moves.csv` : il reconstruit son échantillon depuis le journal
d'échanges. Oublier ce second point ferait porter aux trois volets des périmètres
différents **sans que rien ne le signale**. Les deux emploient la même convention (date
UTC de l'horodatage simulé), donc la même frontière de journée.

**3. Une seule tentative par décision** — la plus récente, identifiée par la colonne
« Heure de calcul ». Cette coupe s'applique **avant** les deux autres
(`frames.latest_attempts`, appelé en tête de `frames.read_moves`), et elle ne concerne
que les runs repris à chaud : sur un run joué d'une seule traite, elle est un no-op et
la page n'en dit rien.

La clé de dédoublonnage porte le **jour simulé** en plus du couple
(`ID Personne`, `ID Activité`), et ce n'est pas un détail de forme :

- **sans le jour**, la décision du jour 1 et sa répétition du jour 2 — celles que la
  coupe n° 2 est justement là pour écarter, 442 couples sur le run repris du
  2026-08-19 — passent pour deux tentatives de la même décision. On garde alors celle
  du jour 2, que la coupe au premier jour simulé écarte ensuite : la décision
  **disparaît du score** au lieu d'y entrer une fois. Mesuré sur ce run : 2 488
  décisions scorées et un composite de 23,45, contre 2 844 et 24,09 avec la bonne clé ;
- **avec le jour**, les deux coupes se composent : le dédoublonnage traite les
  tentatives d'un même jour, la coupe n° 2 les jours en trop.

`model_compare.latest_attempts` applique la même règle sur le même piège — les deux
implémentations doivent rester d'accord.

> **Ce dédoublonnage n'a qu'un seul point d'entrée, contrairement à la coupe n° 2.**
> Il vit dans `frames.read_moves`, donc il couvre les volets 1 et 3 ;
> `common_set_eval.build_sample` ne l'applique pas au journal d'échanges. Aucun chiffre
> publié n'en souffre — le volet 2 refuse de s'afficher s'il n'a pas été mesuré sur le
> run épinglé, et le run épinglé n'a pas été repris — mais épingler un run repris
> demanderait d'étendre la coupe au volet 2 d'abord.

La page publie le jour retenu et les trois comptes d'exclusion dans son bilan de lecture :
un périmètre tu ferait passer un sous-ensemble du journal pour le journal entier. La
vérification se fait en comparant les `n` affichés par les trois volets, pas en les
supposant égaux.

### Volet 1 — Simulation (LLM + tirage)

Source : `experiments/<run>/moves.csv`.

Deux lectures du même run :

- **attendu** — la masse de probabilité (`P(Marche) %`, `P(Vélo) %`, …). C'est la
  grandeur que la calibration optimise ; elle ne dépend d'aucun tirage.
- **tiré** — le mode effectivement retenu par `draw_index`. L'écart avec la
  première lecture mesure le bruit d'échantillonnage introduit par le tirage.

Une **troisième** colonne apparaît dès que le volet 2 est mesuré : *Sim. (éch. V2)*,
le même run restreint aux seules personnes de l'échantillon du volet 2. Ce n'est pas
une lecture de plus de la simulation, c'est un **témoin d'effectif** — il dit ce que
coûte, en points de composite, le fait de mesurer sur 81 personnes plutôt que 881.
Voir le volet 2 pour le chiffre et son usage.

Conventions de correspondance appliquées :

- le train est rangé avec les transports collectifs ;
- les deux-roues motorisés et « autres modes » sortent du périmètre scoré, comme
  le résidu « autres » d'EMC² ; la masse écartée est mesurée et affichée ;
- `Motifs de déplacement` mélange libellés traduits et bruts ; `home`, `leisure`
  et `other` n'ont pas d'équivalent EMC² et sortent de la dimension motif.

La colonne **`Contrainte de chaîne`** (écrite depuis le ticket 008) est lue et
**ventilée dans le bilan de lecture**, pas utilisée comme filtre : une décision prise sur
un jeu d'options déjà restreint par la cohérence des véhicules reste ce que la simulation
a joué, mais elle ne mesure pas la même chose qu'un choix libre entre tous les modes. Le
détail des valeurs est dans [vehicle-chain.md](vehicle-chain.md). Sur un run antérieur à
la colonne, le bloc disparaît de la page plutôt que d'afficher « 100 % aucune ».

Le **lieu de résidence** (Toulouse / 1re / 2e / 3e couronne, plus `hors périmètre`)
n'est pas recalculé par la page : elle relit la colonne `Lieu de résidence` telle
que le run l'a écrite. Et depuis le **ticket 021**, `move_logger.py` ne la calcule
plus non plus : il **recopie** le trait `residence_zone` du persona, posé à la
génération de population depuis le découpage **par liste de communes** de l'enquête
(`llm_module/core/residence_zone.py`). Classer par distance à l'hypercentre — ce que
faisait l'action A9 — comparait 24,4 % des personas à la cible d'une autre zone et
rangeait en 3ᵉ couronne 45 domiciles qui ne sont pas dans le périmètre d'enquête.

Trois conséquences pratiques : une population enrichie avant le ticket 021 produit
une colonne **vide** plutôt qu'une couronne devinée ; `hors périmètre` est une
valeur de première classe, à **exclure** des cibles par zone et dont la masse se
compte ; et un run déjà archivé garde le classement qu'il a écrit, comme avant. Le
classement métrique ne survit plus que comme **témoin d'audit** : depuis le
[ticket 028](../tickets/ticket_028_temps_terminal_couronnes_communales.md) (`tt4`), le
temps terminal classe lui aussi ses points par appartenance aux couronnes et ses lois
sont stratifiées par la table de l'enquête — la divergence de 34 s par bout de trajet
qui séparait le journal de la facturation est refermée.

### Volet 2 — Calibration de prompt

Sources : `prompt_calibration/calibration_results/*.db` et
`prompt_calibration/calibration_datasets/v1/*.jsonl`.

Le store conserve les **décisions brutes** de chaque évaluation
(`evals.decisions` = `[[agent_id, mode, weight], …]`). Tout score est donc
recalculable rétroactivement, **sans un seul appel LLM**. La page recalcule
systématiquement : elle ne relit jamais `scores_json` comme référence.

Seuls les nœuds non rejetés sont tracés (verdicts `accepted`, `imported`, plus
les graines). Le store cloud étant rapatrié dans le store local, la page détecte
l'inclusion et ne trace qu'une fois la même courbe.

#### Régime de mesure, et non « modèle »

Le recalcul de la loss ne suffit pas à rendre deux nœuds comparables. Ce qui doit
être identique, c'est le **régime de mesure** — modèle d'évaluation **et**
politique de décision :

- le **modèle** interrogé change les décisions ;
- la **politique** aussi : le moteur a basculé du « mode élu par persona » à la
  masse de probabilité (cf. `docs/arch/prompt_calibration.md` §4.1). Les évals
  antérieures à la bascule portent des décisions fermes, les nouvelles des poids.

Un composite recalculé n'annule que l'effet de la **loss**. `frames.eval_regime`
dérive donc le régime de l'`eval_params_key` du moteur (`policy=weighted` depuis
la bascule, `samples=N` avant, `legacy_import` pour l'import hérité) et la page
**facette tout par régime** : une courbe par régime, une colonne « régime » dans
la table des nœuds, et une plage de composite limitée au **régime de référence**
de chaque store (le plus fourni). Mêler les régimes dans une même plage n'aurait
pas de sens.

#### Lignée épinglée : la seule trajectoire lisible bout à bout

Les courbes chronologiques mêlent des branches et des nœuds sans parenté : elles
disent « le store contient des scores », pas « la calibration a progressé ». Une
**lignée** le dit — la chaîne des mutations acceptées, de la graine à la feuille —
à condition que tous ses nœuds soient mesurés sous le même régime. C'est l'objet
de l'action A5 et de `calibrate reeval`.

La feuille est **épinglée dans `sources.yaml`** (`arms.calibration.lineage`), pour
la même raison que le run du jeu commun : une reconstruction automatique (« la
plus longue chaîne disponible ») changerait de sujet à chaque campagne sans que la
page le signale. Le champ `regime` dit sous quel régime la lire ; si ce régime ne
couvre pas encore la lignée, la page le **signale** et se replie sur le régime le
mieux couvrant plutôt que de se taire.

La chaîne est reconstruite par `frames.lineage_chain`, qui replie sur les arêtes
`mutations(node_to → node_from)` quand la colonne `parent` est vide — cas d'un
nœud dédoublonné, dont le `parent` est celui de sa première création. Sans ce
repli, la lignée perd sa graine.

Quand **plusieurs** régimes couvrent la même lignée, la page les superpose. La
question posée n'est plus « la calibration a-t-elle progressé » mais « le gain
survit-il au changement d'instrument ? » — même sens sous les deux régimes = un
effet du prompt ; sens opposés = un effet de l'instrument. La page conclut
explicitement dans un sens ou dans l'autre.

#### Deux substrats, deux nombres : personas gelés et jeu commun

Un composite de calibration ne veut rien dire tant qu'on n'a pas dit **sur quelle
population** il a été calculé. Il y en a deux, et la page ne doit jamais les
confondre :

- les **personas gelés** (`calibration_datasets/v1`) : le jeu sur lequel la boucle
  d'optimisation a travaillé. C'est là que vivent tous les scores du store, et
  c'est ce que raconte le bloc « avant / après » ;
- le **jeu commun** : les personas du run épinglé, ceux que scorent aussi les
  volets 1 et 3. C'est le seul chiffre qui a le droit d'entrer dans la synthèse
  comparative.

`scripts/synthesis/common_set_eval.py` (cible `make common-set-eval`, action A3)
produit le second. Il rejoue la **graine et la feuille** de la lignée épinglée sur
un échantillon du run, sous le régime épinglé, et écrit
`scripts/synthesis/data/calibration_on_common_set.jsonl` — une ligne par prompt,
portant ses décisions (`columns` + `decisions`) et le descriptif de l'échantillon.
Le fichier est déclaré dans le manifeste (`arms.calibration.common_set_eval`) ;
absent, la page se génère normalement et affiche sa carte « Données manquantes ».

**L'échantillon est gelé.** Règle :
`sha256("common_set_v1:" + agent_id) % 1000 < 99` → 80 personnes, et autant de
décisions que le run leur en donne (509 sur le run du 29/07, 383 sur celui du
31/07 — la règle ne bouge pas, c'est le run qui porte moins de décisions LLM
depuis que la cohérence de chaîne des véhicules réduit les jeux de choix à une
seule option sur nombre de trajets). Trois propriétés, et chacune répond à un
piège :

- **par personne, jamais par trajet** : tous les déplacements d'une personne
  retenue sont conservés. C'est la logique des jeux gelés du moteur
  (`calibration/datasets.py`), et elle évite de traiter comme indépendants des
  trajets qui ne le sont pas ;
- **dans un espace de hachage distinct** du découpage train/val/test. Reprendre
  `sha256(agent_id) % 100 < k` tel quel aurait sélectionné un préfixe de
  l'intervalle train : l'échantillon aurait été composé à 100 % de personas du
  split sur lequel la calibration a été optimisée, ce qui flatte la feuille. Avec
  le préfixe de namespace, la composition suit celle de la population
  (52 train / 15 val / 13 test personnes) ;
- **seuil choisi par la couverture, pas par le budget** : 99 est le plus petit
  seuil dont le rapport de couverture du moteur est propre — toutes les strates
  Cerema présentes dans le run atteignent l'effectif minimal de 5. En dessous
  (424 décisions), la tranche d'âge 70-74 se vide : la dimension `age` du
  composite porterait sur un support amputé et cesserait d'être comparable au
  volet 1. La seule strate encore signalée, `plus_50km`, est vide **dans le run
  entier** — aucun échantillonnage ne peut la remplir.

Le script ne refait **ni le lotissement ni la boucle de rattrapage** : il passe par
l'`Evaluator` du moteur, donc par les défenses de l'action A10 (comparaison des
personas envoyés aux décisions rendues, re-tir du lot incomplet par moitiés, refus
de mettre en cache une éval sous le plancher de couverture). Les réécrire aurait
réintroduit le défaut que A10 venait de corriger : un score calculé sur une
sous-population, sans que rien ne le signale.

Les décisions écrites portent leurs strates **par décision** et non par agent : une
personne qui fait trois trajets garde ses trois motifs et ses trois distances, là
où une jointure par `agent_id` n'en retiendrait qu'un (c'est la limite documentée
de `cmd_rescore` côté moteur).

**Coût et quota.** Mesuré : **175 appels** pour les deux évals — 128 lots de 8
personas plus 29 re-tirs de lots incomplets (23 %, au-dessus des ~16 % relevés par
A10 sur les personas gelés : ceux du run portent plus de contexte). Le lot est à 8
et non à la capacité déduite du provider (15) : à 15, le modèle rend un JSON valide
mais amputé de personas.

Le seau journalier du free tier Google se réinitialise à **minuit Pacific**, pas à
minuit UTC : `quota_reset_tz` dans la config du moteur le dit, et le `retryDelay`
d'une trentaine de secondes renvoyé dans le 429 ne l'indique pas. Piège vérifié le
2026-07-31 : **une sonde de quelques appels ne dit pas si un seau est ouvert.** Une
clé épuisée a répondu 200 à quatre requêtes consécutives avant de renvoyer
`limit: 500` sur la cinquième — l'application du quota journalier n'est pas exacte à
la frontière. Le seul diagnostic fiable est le 429 lui-même, lu dans le corps de la
réponse. À l'épuisement, le script persiste la date de reprise dans le store
(cooldown) comme le fait `calibrate reeval`, et une relance repart du cache sans
repayer.

Le cooldown est de portée **globale**, alors que chaque clé (`google`, `google2`)
a son propre seau : une clé épuisée bloque donc aussi la seconde, et il faut
effacer la ligne `cooldown` du store pour basculer. C'est délibéré côté garde —
elle refuse de deviner quel seau est ouvert — mais il faut le savoir avant de
conclure qu'il n'y a plus de quota nulle part.

**La clé de cache porte l'empreinte de l'échantillon.** Le store indexe une éval
sur `(nœud × nom de jeu × params)`. Sous un nom de jeu fixe, le run n'entrait pas
dans la clé : épingler un nouveau run resservait la mesure du run précédent, et le
script la réétiquetait avec le descriptif du nouveau — zéro appel payé, composites
identiques au centième, et un fichier affirmant décrire 383 décisions du nouveau
run tout en en portant 762 de l'ancien. Le défaut était silencieux : rien, dans la
page, ne compare `sample.run` au run épinglé. Le nom de jeu est donc
`common_set_v1@<empreinte>`, où l'empreinte est un SHA-256 tronqué des couples
(`agent_id`, texte `section`) réellement soumis au modèle — l'entrée même de la
requête. Deux runs ne peuvent plus partager une entrée ; relancer sur le même run
reste gratuit. Le suffixe reste hors de `train`/`val`/`test`, donc invisible pour
les courbes de calibration.

Conséquence pour le retour arrière : les évals payées avant ce changement vivaient
sous le nom nu `common_set_v1`, dont rien ne dit de quel run il provient. Celles de
l'action A3 ont été ré-indexées sur l'empreinte de leur run d'origine
(`common_set_v1@95935e48c189`, run du 29/07) plutôt que supprimées — revenir à ce
run ne coûte donc aucun appel.

#### Ce que la mesure a donné, et le piège d'effectif

| | graine `4c2ea894` | feuille `0fc427e7` | gain |
|---|---|---|---|
| personas gelés (train, 495 déc. / 298 pers.) | 24,35 | 22,24 | **2,12** |
| jeu commun (509 déc. / 80 pers.) | 38,53 | 36,41 | **2,13** |

Le **gain se transporte** presque à l'identique ; le **niveau** ne se transporte pas
(+14,2 points pour les deux prompts). Avant d'en conclure quoi que ce soit sur le
prompt, il faut retirer ce qui vient du seul **effectif** : JSD et EMD sont biaisées
vers le haut quand les strates sont petites.

La page le chiffre au lieu de le supposer, avec la ligne **« Sim. (éch. V2) »**
(`build_simulation_on_sample`) : le volet 1 restreint aux **mêmes personnes** que le
volet 2, sans aucun appel LLM. Sur ce run, la simulation passe de **24,37 à 29,39**
en descendant de 881 à 81 personnes — **+5,02 points pour la seule réduction
d'effectif**, à décisions inchangées. C'est donc à 29,39 que les colonnes de
calibration se comparent. Elles restent au-dessus : à substrat et à effectif égaux,
le volet 2 est moins fidèle à l'enquête que la simulation elle-même.

Le prédicat d'échantillonnage du témoin est **reconstruit depuis le descriptif écrit
dans le fichier de mesure** (`namespace`, `modulus`, `bucket_max`) et non depuis les
constantes du producteur : un fichier produit sous une autre règle est relu sous
*sa* règle. Le repli sur les constantes se fait sur `is None`, pas sur la véracité —
un seuil de 0 est une valeur légitime (échantillon vide) que `0 or défaut` aurait
silencieusement remplacée.

#### Généralisation : le jeu que la boucle n'a jamais vu (action A4)

Tout ce qui précède est mesuré sur `train` — le jeu qui a servi à **optimiser** la
lignée. Un composite d'entraînement ne distingue pas un prompt qui a compris la
population d'un prompt qui a mémorisé ses 298 personas. Le chiffre qui les
distingue vient de `scripts/synthesis/heldout_eval.py` (cible `make heldout-eval`).

Le script rejoue la lignée épinglée sur un jeu gelé de **retenue** et écrit les
évals **dans le store**, exactement là où `calibrate reeval` les écrit ; la page les
relit par `frames.read_store_history`, qui accepte déjà `train`/`val`/`test`. Aucun
fichier intermédiaire. Comme pour A3, ni le lotissement ni la boucle de rattrapage
ne sont réécrits : l'`Evaluator` du moteur s'en charge, avec les défenses de A10.

**Quel jeu, et pourquoi celui-là.** `test` est le seul que la boucle n'a jamais vu :
`val` sert à l'arrêt anticipé — elle a donc influencé la sélection des prompts — et
`screen` est un sous-ensemble **strict** du `train`. C'est vérifiable et vérifié
(`dataset_profile`) : `screen` partage 52 personnes sur 52 avec le train, `val` et
`test` en partagent zéro.

**De quoi parle-t-on quand on dit « généralisation » ?** La question n'est pas
rhétorique : un découpage **par personne** soutient « des individus jamais vus », un
découpage **par déplacement** seulement « d'autres trajets des mêmes individus ».
`heldout_eval.dataset_profile()` tranche **sur les fichiers**, pas sur la foi de la
règle déclarée dans `manifest.yaml`, et la page affiche la réponse en toutes
lettres. Sur `v1`, la règle est `sha256(agent_id) % 100` → train [0,70), val
[70,85), test [85,100) : c'est bien un découpage **par personne**, intersection vide
vérifiée.

**Le piège d'effectif, en pire.** Le `train` porte 298 personnes, le `test` 66. Lu
brut, l'écart ressemble à du surapprentissage — et n'en est pas. Le témoin
(`build.resample_composite`) rejoue le score des décisions `train` **déjà stockées**
sur 200 sous-ensembles de 66 personnes tirés au hasard (par personne, graine fixée,
zéro appel LLM) : il dit ce que vaudrait le score d'entraînement *s'il était mesuré
sur aussi peu de monde*. C'est à lui, et non à la colonne « Train », que la colonne
« Test » se compare.

Un **second** témoin, `build.resample_gain`, porte sur le *gain* graine → feuille.
Il est **apparié** — les deux prompts sont scorés sur les *mêmes* personnes tirées —
donc bien moins bruyant que le premier, et c'est lui qui autorise la conclusion.

| | graine `4c2ea894` | feuille `0fc427e7` | gain |
|---|---|---|---|
| train (495 déc. / 298 pers.) | 24,35 | 22,24 | **2,12** |
| test (106 déc. / 66 pers.) | 31,60 | 24,06 | **7,54** |
| témoin : train ramené à 66 pers. | 29,84 | 26,90 | **2,94** [-1,84 ; 8,24] |
| écart corrigé (test − témoin) | +1,76 | **−2,84** | |

Lecture : la seule réduction d'effectif coûte **+5,49** points à la graine et
**+4,66** à la feuille — du même ordre que les +5,02 mesurés par A3 sur la
simulation. À effectif neutralisé, la feuille est **meilleure** sur le test que sur
le train, et les six nœuds de la lignée tombent dans la bande du témoin : **aucun
surapprentissage détectable**. Le gain **survit** au changement de population. Son
apparente amplification (7,54 contre 2,12), en revanche, **n'est pas démontrée** :
elle tombe dans la bande du témoin apparié, et 66 personnes ne permettent pas de
trancher plus finement. La page dit les deux.

**Une confusion résiduelle, publiée plutôt que tue.** `calibration/datasets.py`
retire la section `**Historique :**` (mémoire STM/LTM du run source, non
reproductible) des jeux `val` et `test`, et la garde dans le `train` où elle couvre
86 % des records. Le prompt de test n'est donc pas seulement adressé à d'autres
personnes : il est aussi **plus court d'une section**. Les deux effets sont mêlés et
rien dans les données disponibles ne les sépare — il faudrait une éval du train
lui-même privé de sa mémoire.

**Où ces chiffres n'apparaissent pas, et pourquoi.** Ni dans la trajectoire, ni dans
la lignée (y mêler un autre jeu superposerait deux populations dans une même
courbe), ni dans la matrice de synthèse : le jeu de retenue est un **troisième
substrat**, et faire voisiner une colonne de 66 personnes avec des colonnes de 881
rejouerait exactement la confusion que l'action A3 a corrigée. La matrice se contente
d'y renvoyer (`synthesis.generalization_available`).

**Coût.** 98 appels pour les 6 nœuds — 84 lots de 8 personas plus 7 re-tirs de lots
incomplets (8 %). Les deux extrémités seules coûtent ~34 appels. La reprise est **par
nœud** : un rejeu interrompu par le quota garde les nœuds terminés, mais un nœud
interrompu ne laisse rien (la garde de couverture est tout-ou-rien). Chiffrer avant
de tirer : `make heldout-eval DRY_RUN=1`.

### Volet 3 — Modèle de régression PROGEDO

Politique statistique entraînée sur les micro-données de l'enquête. Elle sert de
**référence haute** plus que de concurrent loyal : entraînée sur l'enquête qui
sert aussi de cible, elle est proche de l'oracle sur les parts modales. Son
intérêt est de borner ce qu'un modèle purement statistique atteint.

**Le modèle existe depuis l'action A6**, entraîné par
`scripts/progedo_logit/fit_mode_choice_policy.py` (`make policy`) et sérialisé dans
`mode_choice_policy.json`. Ses hyperparamètres sont ceux du banc `make policy-tune`
(ticket 005 §9), choisis en validation croisée par ménage sans jamais lire le split test. La page en lit les métriques de test directement dans
l'artefact — il les embarque, étant conçu pour être autoportant — et affiche
log-loss, accuracy et parts modales prédites face aux observées. Ces chiffres
portent sur le **split test de l'enquête**, étanche au ménage : ils disent que le
modèle tient, pas qu'il est entré dans la comparaison.

#### Le modèle sur le jeu commun, renormalisé sur l'offre OTP

`scripts/synthesis/model_on_common_set.py` (`make common-set-predict`) applique la
politique **au périmètre du volet 1**, construit par le même `frames.read_moves` et
les mêmes exclusions du manifeste — c'est toute la raison d'être de l'action A8 : deux
colonnes mesurées sur deux populations ne se comparent pas. Le résultat est écrit dans
`scripts/synthesis/data/progedo_on_common_set.parquet` (`arms.model.predictions`), une
ligne par décision, avec les probabilités **avant et après** renormalisation : sans le
« avant », la correction est une affirmation invérifiable. Aucun appel LLM, aucun
réseau, résultat déterministe.

**Garde de substrat — le volet 3 est écarté s'il n'a pas été mesuré sur le run
épinglé.** Symétrique de celle du volet 2, et elle a manqué jusqu'au 2026-08-25 : ce
jour-là, épingler un nouveau run a bien écarté la mesure du volet 2, mais laissé celle du
volet 3 en place. La matrice comparait alors une simulation lue sur un run à un modèle lu
sur un autre, en les annonçant comme un seul substrat — le défaut exact que l'action A1
avait fermé d'un seul côté. Le parquet porte `meta.run` et `meta.moves_sha256` ; la page
compare les deux au run qu'elle épingle et à l'empreinte du `moves.csv` réellement sur le
disque. **L'empreinte n'est pas redondante avec le nom** : une reprise à chaud
(`make run OFFLINE=1 CONT=1`) réécrit `moves.csv` DANS le même dossier, donc sous le même
nom de run — seule l'empreinte distingue ces deux états. Écartée, la mesure devient une
carte « Données manquantes » portant l'action qui la rétablit (`make common-set-predict`),
jamais un chiffre servi en silence.

**Ce que la renormalisation corrige.** La politique prédit sur 4 classes sans savoir ce
qui était offert ; la simulation ne choisit que parmi les itinéraires qu'OTP a
proposés. Comparer les deux sans correction reviendrait à reprocher au LLM de n'avoir
pas choisi un mode qu'on ne lui a jamais offert, ou à créditer le modèle d'une option
inexistante. Chaque prédiction est donc restreinte aux modes de la colonne « Modes
proposés au LLM », puis renormalisée à 100 % (hypothèse IIA, ticket 005 §4).

**La correspondance des modes est établie en un seul point**
(`model_on_common_set.POLICY_CLASS_TO_CAT` et `CANONICAL_TO_CAT`), et testée. Quatre
vocabulaires se croisent — classes de la politique, modes canoniques du simulateur,
libellés du journal, catégories de la page — et deux fusions sont dissymétriques :

| Mode | Politique PROGEDO | Page (EMC²) | Conséquence |
|---|---|---|---|
| `train` | rangé dans `transit` | transports collectifs | les deux s'accordent, le pont tient |
| `motorbike` | rangé dans `car` | « autres », hors des 4 modes scorés | **divergence** : une offre deux-roues est retirée de l'offre, pas comptée comme une offre de voiture |

Compter le deux-roues motorisé comme une offre de voiture gonflerait la part voiture du
seul volet 3, sur un périmètre de modes différent de celui où le volet 1 est scoré.

**Ce qui n'est pas imputé.** Trois situations sortent du score, et elles sont comptées
plutôt que réparées en silence : paire origine-destination hors de la couche de zones
(`od_km` est la première variable du modèle, la deviner serait une extrapolation hors
domaine), offre sans aucun mode prédictible, persona introuvable. Ces lignes sont
**écrites quand même** dans le parquet, avec leur `status` et sans probabilité : la
masse exclue se recompte depuis le fichier.

**Deux lectures, comme le volet 1** : la masse de probabilité renormalisée et le mode
le plus probable. L'écart entre les deux est structurel et non anecdotique — le modèle
n'élit presque jamais le vélo (rappel 0,128 à l'entraînement) alors qu'il le calibre
bien en masse. N'afficher que la première flatterait le modèle, n'afficher que la
seconde le condamnerait.

**Le cadrage doit rester visible au moment du chiffre.** Le volet 3 devance nettement
les deux autres colonnes, et c'est attendu par construction. La page pose donc
l'avertissement « référence haute » **au-dessus** de la matrice comparative, pas dans
une section ultérieure. Rappel du ticket 005 §6 : le jeu d'entraînement est lui-même
restreint au périmètre d'enquête, plus dense et plus marcheur que l'agglomération —
même cette borne est optimiste.

La page affiche la disponibilité de chacune des 21 variables sur le jeu commun :
les 12 variables persona et les 3 variables de contexte sont lues directement, les
6 variables géographiques sont dérivées des coordonnées par le résolveur de zone
fine (`llm_module/core/zone_resolver.py`, action A7). Ce dernier a besoin de la
couche `llm_module/data/zf_zones.gpkg`, hors dépôt comme sa source PROGEDO : quand
elle manque, la page marque ces 6 variables « couche absente » et la régénérer
demande `make zones`. Dès que les prédictions existent, la colonne « État » ne dit
plus ce qu'on attendait de la variable mais **ce que la prédiction a trouvé** : une
variable annoncée disponible peut être massivement manquante à l'arrivée, l'encodage
rendant manquante toute modalité que le spec ne connaît pas — sans rien lever.

#### Le jeu d'entraînement perdait la moitié des déplacements — corrigé le 2026-08-27

Vérifié le 2026-08-27 contre le rapport source de l'enquête
([aua-toulouse.org, 68 p.](https://www.aua-toulouse.org/wp-content/uploads/2024/05/Rapport-final-68-pages-Enquete-mobilite-2023-Bassin-de-vie-toulousain.pdf)) :
`cerema_values.yaml` est **conforme**. Recalculées sur les 54 559 déplacements exploitables
du fichier source, pondérées `COEP`, les parts modales reproduisent la table publiée —
global voiture 56,9 contre 56,7 ; marche 26,9 contre 26,8 ; TC 12,0 contre 12,4 ; vélo 4,1
contre 4,1. Aucun désaccord entre la table publiée et les micro-données.

Mais `build_mode_choice_dataset` n'en garde que **27 886**, et l'attrition vient d'un seul
filtre — `od_km` dans `CRITICAL`, qui exige que l'origine **et** la destination tombent dans
la couche de zones fines. Elle n'est pas uniforme en âge :

| Bande | Déplacements | `od_km` absent | Retenus | Part TC réelle | Part TC dans l'entraînement |
|---|---|---|---|---|---|
| 5-9 | 2 563 | 73,0 % | 27,0 % | 5,5 % | 4,6 % |
| **10-14** | 2 808 | **75,5 %** | **24,5 %** | **27,1 %** | **9,7 %** |
| **15-19** | 3 270 | **64,7 %** | **35,3 %** | **45,2 %** | **31,5 %** |
| 20-24 | 4 316 | 45,9 % | 54,1 % | 29,6 % | 27,3 % |
| 30-49 | 16 061 | 48,4 % | 51,6 % | 5,8 % | 7,0 % |

Trois quarts des déplacements de 10-14 ans sortent du jeu d'entraînement, contre la moitié
de ceux des adultes, et le sous-ensemble retenu **divise leur part TC par près de trois**.

Conséquence à connaître avant de lire le volet 3 : **la politique est mal entraînée
précisément sur la cohorte où la page montre sa plus grosse erreur.** L'écart des 15-19 ans
— voiture +28,0 pt, TC −24,5 pt avant la correction des traits — n'est donc pas seulement
un défaut de population ou de cible ; c'est aussi un défaut d'échantillon d'apprentissage.
La correction de l'abonnement TC n'en a récupéré que 5,3 points, et c'est cohérent : elle ne
touche pas cette cause-là.

Ce n'est **pas** un défaut de la table de référence : la cible est juste. C'était un
défaut de **granularité de codes**. La couche est indexée sur des codes à 9 chiffres dont
les 3 derniers valent toujours `000`, alors que `D3` / `D7` codent au niveau sous-zone
(`102103503`). `build_trips` comparait les deux tels quels.

**Correctif : `zone_key()` ramène le code à la granularité de la couche.** Résolution des
OD **51,1 % → 95,8 %**, jeu d'entraînement **27 886 → 52 248** déplacements. Les 4,2 %
restants sont hors périmètre pour de bon (préfixes 98x, 93x, 909) et le restent — leur
inventer une zone serait une extrapolation hors domaine.

Validé plutôt qu'affirmé : sur les 24 365 déplacements que le correctif récupère, la
distance obtenue corrèle à **0,984** avec la distance à vol d'oiseau déclarée (`D11`),
contre 0,992 sur ceux déjà résolus, même biais médian (+0,18 km contre +0,14) et même
queue (0,3 % d'écarts au-delà de 5 km contre 0,2 %). La troncature situe les déplacements
aussi bien que les codes complets ; elle ne rapproche pas des destinations lointaines.

Le jeu d'entraînement est désormais représentatif :

| Bande | Part TC avant | Part TC après | Part TC réelle |
|---|---|---|---|
| 5-9 | 4,6 % | 5,5 % | 5,5 % |
| 10-14 | 9,7 % | **27,3 %** | 27,1 % |
| 15-19 | 31,5 % | **45,4 %** | 45,2 % |
| 20-24 | 27,3 % | 30,2 % | 29,6 % |
| 30-49 | 7,0 % | 5,9 % | 5,8 % |
| **global** | **9,8 %** | **12,3 %** | **12,4 %** |

Politique ré-entraînée : test sur 13 045 déplacements au lieu de 6 985, log-loss 0,5392,
accuracy 0,791, `od_km` à 31,6 % du gain et `has_pt_subscription` à 10,2 % — deuxième
variable du modèle. L1 du mode élu **0,0861 → 0,0573**.

> **Réglée depuis le 2026-08-30.** Les hyperparamètres du booster ont été cherchés
> (ticket 005 §9) : `num_leaves` 31 → 5, 6 000 arbres au lieu de 560. Le log-loss (0,5402)
> et l'écart aux parts modales ne bougent pas au-delà du bruit ; ce qui change est la
> vraisemblance du **vélo**, 2,42 → 2,35, gain significatif au bootstrap apparié par
> ménage. Les importances de gain se redistribuent en conséquence : `od_km` 28,5 %,
> `has_pt_subscription` 9,5 %. La page lit ces chiffres dans l'artefact, elle suit donc
> d'elle-même.

#### ⚠ La lecture `attendu` est biaisée vers les TC, et pénalise les corrections justes

Quatre mesures sur le run `2026-08-26_17_46`, chaque correction isolée puis combinée :

| Composite `emd_jsd` | A référence | B traits corrigés | C `od_km` corrigé | D les deux |
|---|---|---|---|---|
| `attendu` (masse renormalisée) | 6,015 | 5,941 | 6,086 | **6,208** |
| `elu` (mode le plus probable) | 6,464 | 6,086 | 6,022 | **5,933** |
| `brut` (avant renormalisation) | 6,282 | 5,749 | 6,173 | **5,652** |

Et pourtant, sur l'écart le plus gros de la page :

| Âge 15-19 | A | B | C | D |
|---|---|---|---|---|
| `l1` de la strate | 63,8 | 53,7 | 56,9 | **48,7** |
| voiture | +28,0 | +23,7 | +24,2 | **+20,9** |
| transports collectifs | −24,5 | −19,2 | −19,6 | **−14,8** |

Les deux corrections **se cumulent** là où elles visent : 9,7 des 24,5 points d'écart TC
récupérés, 7,1 des 28 points de voiture. Mais `attendu` **empire**.

Mécanisme, mesuré par mode (`renormalisation_bias` du `data.json`, recalculé à chaque
régénération) — configuration D sur le run `2026-08-26_17_46` :

| Mode | Brut | Renormalisé | Ajouté | Cible | Écart brut | Écart renormalisé |
|---|---|---|---|---|---|---|
| marche | 19,1 % | 24,1 % | **+5,0** | 26,8 % | −7,7 | **−2,7** |
| voiture | 63,1 % | 54,1 % | **−9,0** | 56,7 % | +6,4 | **−2,6** |
| vélo | 4,4 % | 5,3 % | +0,8 | 4,1 % | +0,3 | +1,1 |
| **transports collectifs** | 13,3 % | 16,5 % | +3,2 | 12,4 % | **+0,9** | **+4,1** |

La renormalisation retire 9 points à la voiture — le modèle la surprédit en brut — et les
répartit sur les modes offerts. **Elle améliore donc deux modes sur quatre** : la marche
passe de −7,7 à −2,7 d'écart, la voiture de +6,4 à −2,6. Ce n'est pas une correction
néfaste, et il ne faut pas la présenter comme telle.

Le problème est concentré sur les **transports collectifs** : ils sont à +0,9 de leur cible
dans la vision propre du modèle, et à **+4,1** après renormalisation, parce qu'ils sont
presque toujours offerts et captent donc une part de la masse retirée à la voiture. Le vélo
subit le même effet en plus petit (+0,3 → +1,1).

**Conséquence de lecture, à ne pas escamoter : `attendu` lit les TC comme largement
au-dessus de leur cible alors que le modèle les met presque dessus. Il pénalise donc toute
correction qui augmente les TC, même juste.** Les lectures `elu` et `brut` n'ont pas ce
biais, et ce sont elles qui bougent dans le bon sens ici. Un lot qui corrige la
sous-représentation des TC doit être jugé sur les strates et sur `elu`/`brut`, pas sur le
chiffre de tête.

#### Le garde de substrat couvre désormais la politique

`spec_version` ne bouge que si le contrat de variables change. Le correctif ci-dessus a
porté le jeu d'entraînement de 27 886 à 52 248 déplacements **sans y toucher** : les
parquets mesurés sous l'ancienne politique auraient été servis comme courants, en silence.
Le parquet porte donc `policy_sha256`, et la page le compare à l'artefact sur le disque —
troisième axe du garde, après le nom du run et l'empreinte du journal. Contrepartie
assumée : les parquets écrits avant ce correctif ne portent pas la clé et restent non
gardés sur cet axe ; c'est son absence qui les identifie.


`dist_center_orig_km` et `dist_center_dest_km` se mesurent depuis l'hypercentre
publié par `feature_spec.json`, celui-là même que le volet 1 utilise pour ses
couronnes de résidence depuis l'action A9 : les deux volets parlent désormais du
même centre-ville.

## 5. Organisation du code

| Fichier | Rôle |
|---|---|
| `scripts/synthesis/sources.yaml` | Manifeste : où chercher chaque donnée, quel run et quelle lignée sont épinglés |
| `scripts/synthesis/sources.py` | Résolution, sondage (existence, empreinte), import du moteur |
| `scripts/synthesis/frames.py` | Adaptateurs par volet, détail par dimension, scoring |
| `scripts/synthesis/common_set_eval.py` | Producteur : rejoue graine et feuille sur le jeu commun (`make common-set-eval`) — **consomme du quota LLM** |
| `scripts/synthesis/heldout_eval.py` | Producteur : rejoue la lignée sur un jeu gelé de retenue et écrit dans le store (`make heldout-eval`) — **consomme du quota LLM** ; porte aussi la description des jeux gelés (découpage par personne ou par déplacement) |
| `scripts/synthesis/model_on_common_set.py` | Producteur : applique la politique PROGEDO au jeu commun, renormalisée sur l'offre OTP (`make common-set-predict`) — hors ligne, déterministe |
| `scripts/synthesis/charts.py` | SVG en ligne (bullet, profils ordinaux, matrice) |
| `scripts/synthesis/render.py` | Assemblage HTML — page complète (`render()`) et pages dédiées « Détail par sous-catégorie » (`render_detail()`, spécifiées par `DETAIL_PAGES`) |
| `scripts/synthesis/build.py` | Orchestration + CLI + liste d'actions |

Aucune donnée absente n'interrompt la génération : chaque source manquante
devient une carte « Données manquantes » portant le chemin attendu et l'action
qui la produirait.

**Changer de run ou de store** revient à éditer `sources.yaml`, ou à passer
`make synthesis RUN=experiments/archive/<run>`.

**La liste d'actions** (`ACTIONS` dans `build.py`) est la seule source de vérité
entre cette doc et le rendu. Ses identifiants ne sont **jamais recyclés** : les
avertissements du code et les tickets y renvoient par numéro. Une action faite
n'est donc pas supprimée. Trois états :

| Clé | Rendu | Quand |
|---|---|---|
| aucune | titre en gras, coût affiché, comptée en attente | rien n'a été entrepris |
| `progress` (`{acquis, reste}`) | badge **partiellement faite**, les deux volets affichés, coût **maintenu**, **toujours comptée en attente** | l'outillage est livré mais le résultat visé n'existe pas |
| `done` | titre barré, badge **faite**, coût neutralisé, retirée du compteur | le résultat visé existe |

L'état intermédiaire existe pour une raison précise : livrer le code d'une mesure
n'est pas produire la mesure. A5 en a été le cas d'école — la lecture d'une lignée
sous un régime unique était outillée et affichée, mais **aucune évaluation n'avait
été produite** : la barrer aurait revendiqué un rejeu inexistant. Elle est passée à
`done` le 2026-07-31, quand le rejeu a effectivement produit les 6 évals sous le
régime épinglé (action A10). C'est la règle : on ne barre qu'au vu du résultat, pas
de l'outil qui permettrait de l'obtenir.

**Les versions publiées** sont archivées sous
`docs/synthesis/archive/<date>_<heure>/` (page + `data.json`) avant toute
régénération qui change la structure ou le périmètre. Comparer les deux
`data.json` est le moyen le plus court de vérifier qu'une modification de rendu
n'a pas déplacé un chiffre.

## 6. Choix graphiques

Palette des modes : celle du projet (`.claude/CLAUDE.md`) — voiture rouge, vélo
violet, transports collectifs vert, marche cyan. Validée pour la vision des
couleurs (ΔE adjacent minimal 18,2 en deutan). Le cyan et le vert passant sous
3:1 de contraste sur fond clair, **toute valeur est écrite en clair** à côté de
sa barre.

- La cible EMC² est un **repère** (tick vertical), jamais une seconde couleur.
- Les axes ordinaux (âge, distance) utilisent des profils en petits multiples,
  un par mode, ligne pleine (observé) contre pointillé (EMC²).
- La matrice de synthèse est normalisée **par ligne** : la question posée est
  « quel volet s'en sort le mieux sur cette dimension », pas « quelle dimension
  est la pire ».
- L'alerte sur un écart porte sur son **ampleur**, pas son signe : sous-estimer
  la marche de 19 points est aussi grave que surestimer le vélo de 15.

## 7. Ventilation par modèle — `make model-compare`

La page principale répond à « où en est la simulation face à l'enquête ». Elle ne
répond pas à « **quel modèle** a produit ce score », parce qu'elle agrège le run
entier sans regarder la colonne `Fournisseur & Modèle`. Dès qu'un run fait tourner
plusieurs modèles — c'est le cas dès que la passerelle répartit la charge entre
fournisseurs — la moyenne du run mélange des lignées de décisions distinctes.

```bash
make model-compare RUN=experiments/archive/<run> \
  [BASELINE="experiments/archive/<repère1> experiments/archive/<repère2>"]
```

Sortie : `docs/synthesis/models/<run>/index.html` et `data.json`. **Aucun appel
LLM** : tout est relu dans `moves.csv`. Le module ne réimplémente ni la lecture ni
la loss — il découpe le journal, écrit chaque sous-ensemble dans un CSV temporaire
et le passe à `frames.read_moves` puis `frames.Scorer`. Un score de cette page est
donc directement comparable à celui de la page principale.

Trois précautions structurent le découpage.

**La reprise à chaud.** `make run OFFLINE=1 CONT=1` rejoue le jour simulé depuis
t0 dans le même dossier d'expérience : `moves.csv` porte alors deux fois les mêmes
couples (personne, activité), une fois par tentative. Le lecteur officiel ne coupe
que sur le **jour simulé**, pas sur la tentative — il compte donc deux fois les
décisions d'avant la reprise. La page retient la tentative la plus récente et
publie **les deux lectures côte à côte**, pour que l'écart soit lisible au lieu de
rester dans le score sans être dit. La clé de dédoublonnage porte le jour simulé
en plus du couple : sans lui, la décision du jour 1 et sa répétition du jour 2
(l'horizon glissant en produit quelques centaines) passeraient pour deux
tentatives de la même décision, on garderait celle du jour 2, et la coupe au
premier jour l'écarterait ensuite — la décision disparaîtrait du score.

**L'effectif.** Un sous-ensemble par modèle est plus petit que le run, et les
divergences par strate sont biaisées vers le haut à petits effectifs (c'est le
constat de l'action A3). Un **test de permutation** chiffre donc l'écart entre les
deux modèles les mieux classés contre le bruit de découpage : on remélange leurs
décisions, on recoupe aux mêmes effectifs, et on compte les tirages qui atteignent
l'écart observé. Sans ce témoin, tout écart de composite serait interprétable — y
compris celui qu'un tirage au sort produit. En deçà de 60 décisions, un
sous-ensemble est affiché mais **pas scoré**.

**La comparabilité des échantillons.** Un modèle peut sembler meilleur parce qu'il
a hérité des trajets faciles. La répartition de charge n'est pas censée regarder le
persona ; la page le vérifie (âge, distance, genre, occupation, motif, nombre de
modes proposés) plutôt que de le supposer.

La page publie aussi **les découpes internes du run** — décisions d'un modèle
contre trajets à itinéraire unique — parce que le composite du run n'est pas le
composite de ses modèles : un trajet à itinéraire unique entre dans le score sans
qu'aucun modèle n'ait rien choisi, et il y entre avec une `absent_penalty` élevée
(un seul mode proposé ⇒ trois modes à zéro). Et elle publie **la santé du run**
(échecs par fournisseur et par statut HTTP, cache, débit, backlog, alarmes),
parce qu'un composite se lit toujours sur un périmètre : si un tiers des décisions
n'a jamais atteint un modèle, le taire ferait passer une pénurie de fournisseurs
pour une performance. Les replis d'erreur sortent du score — il n'y a pas de choix
à noter — mais **pas de la simulation** : l'agent a bien pris l'itinéraire d'index 0,
et les trajectoires du run portent cette part non décidée.

## Voir aussi

- `docs/arch/prompt_calibration.md` — le moteur, la loss, l'acceptation statistique
- `docs/tickets/ticket_005_mode_choice_model.md` — le volet 3
- `scripts/data/population/cerema_values.yaml` — la référence EMC² 2023
