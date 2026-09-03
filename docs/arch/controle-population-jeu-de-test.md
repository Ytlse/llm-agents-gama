# Contrôle et scellement de la population du jeu de test (AAMAS)

La population synthétique sur laquelle tournent les expériences de l'article est **contrôlée**
contre la population enquêtée par l'EMC² 2023, puis **scellée** : un dossier immuable, avec
son empreinte, la règle qui l'a produit et le rapport qui l'a jugé. Cette page dit ce qui est
comparé, à quoi, avec quels tests, et ce que chaque verdict engage. C'est le jalon 0 du
[protocole](../paper/PROTOCOLE_SCIENTIFIQUE.md) (§ 2) et le § 3.1 du gabarit d'article.

Trois scripts, dans `scripts/AAMAS/` :

| Script | Rôle | Cible Makefile |
|---|---|---|
| `reference_marges.py` | assemble les marges de référence avec leur **source** ; gèle la cible jointe couronne × motorisation | `make reference-marges [RECOMPUTE=1]` |
| `control_population.py` | compare une population aux marges ; rapport, verdicts, code de sortie | `make control-population POP=… [BORNE=1.0] [TRACE=…]` |
| `seal_population.py` | `select` : 1 000 pile par allocation stratifiée ; `seal` : contrôle puis dossier scellé | `make select-population POOL=… N=1000` · `make seal-population POP=…` |

---

## 1. Pourquoi « 1 000 » n'était pas 1 000, et pourquoi une sélection

Le service eqasim tire `population_size × 1,15` personnes ([generate_population.py:259](../../eqasim-toulouse/generate_population.py))
puis **renomme** le fichier à la taille demandée ([:313](../../eqasim-toulouse/generate_population.py)) :
`toulouse_population_1000.json` contient **1 021** personas. Au runtime, le contrôleur
ré-échantillonne au hasard à `population_size` (`population_sample_seed`) après un éventuel
filtre bbox — le run épinglé en portait 930. L'effectif du jeu de test dépendait donc de deux
tirages dont aucun n'était contrôlé.

Un effectif rond ne se règle pas à la génération : il se **sélectionne**. Et la sélection ne
doit pas être aléatoire : la [note de dimensionnement](../paper/JUSTIFICATION_TAILLE_ECHANTILLON.md)
(§ 4.3.1) demande un tirage **stratifié sur les strates mêmes qui serviront à la validation**,
à allocation proportionnelle — 1 000 agents stratifiés valent ≈ 2 000 tirés au hasard.

### La règle v4 — le périmètre des 453 communes et les six classes d'âge (`aamas_seal_v4`, ticket 031)

Même mécanique que la v3 ci-dessous, trois différences :

- **Le périmètre est déclaré et journalisé.** La population est celle des **453 communes de
  l'EMC² 2023, six départements, délimitées par le polygone des communes** (table
  `commune_couronne.json`, version `cc1`) — pas par un rayon. La sélection exclut toujours les
  domiciles hors de ces communes ; le journal (`selection.json`, repris dans `MANIFEST.yaml`)
  ajoute la définition du périmètre et les **départements de résidence des retenus**, lus sur
  `household.commune_id` (renseigné pour tous les ménages par l'export eqasim depuis le
  2026-09-03). Un cadre de tirage amputé — la Haute-Garonne seule du ticket 026 — se lit donc
  dans le sceau (`departements_representes: 1/6`, avertissement à la sélection) au lieu de s'y
  cacher. Une population tirée sur ce cadre est une **répétition**, pas une v4.
- **Les six classes d'âge publiées (p. 11) entrent dans la descente.** Tenir les quinze classes
  quinquennales ne tenait pas la part des 5-17 ans (+1,2 pt sur la v3 : la classe 15-19
  chevauche la frontière 17/18). Le référentiel de l'article étant le rapport AUAT, ses classes
  sont des marges de la sélection.
- **Espace de noms de hachage distinct** (`aamas_seal_v4:`) : l'ordre des ménages change, la v3
  reste rejouable telle quelle.

Cibles `cj1` et `cm1` inchangées — elles sont calculées sur les 453 communes. Dossier :
`data/population/population_1000_AAMAS_v4/`.

**Deux hypothèses assumées de la v4** (décisions de l'auteur du dépôt, 2026-09-03) :

- **Une activité hors du polygone des 453 communes est supprimée de la chaîne** de la personne
  (étape 2 du notebook, avant le recalage des horaires ; jamais le domicile, qui fait le
  périmètre). Le graphe de routage et les cibles de l'enquête ne couvrent pas ces lieux. Le compte
  est posé à la racine de chaque enregistrement (`perimetre.activites_hors_perimetre_supprimees`),
  journalisé et alarmé s'il dépasse 0, repris dans le journal de sélection et dans le MANIFEST
  (`perimetre.activites_hors_perimetre`). Mesuré : 0 sur les viviers du 2026-09-03 — le garde-fou
  existe pour le jour où eqasim placera une école ou un emploi dehors. Une population sans cette
  clé n'a **pas été contrôlée** (le MANIFEST le dit : `controle: false`), ce n'est pas un 0.
- **Le vivier porte plus d'immobiles que l'enquête** (19,3 % contre 10,6 %) : l'ENTD nationale
  restreinte aux jours de classe en compte davantage que l'EMC² toulousaine. La cohorte scellée
  est tenue à 10,6 % par la descente ; l'écart du vivier est déclaré ici, non corrigé.

### La règle v3 — par ménage, à marges multiples (`aamas_seal_v3`, ticket 029)

Trois changements sur la v2, chacun pour un écart mesuré sur la population scellée du
2026-09-02 :

- **L'unité est le ménage** (`household.id`, à la racine des enregistrements). La v2
  sélectionnait des personnes : 1 000 retenus dans 865 ménages dont 308 complets. Un ménage a
  une couronne et une motorisation — donc une cellule (0 ménage mixte sur 2 791) — et ses membres
  de 5 ans et + sont tous dans le vivier dès que l'export garde les immobiles : les seuls absents
  sont les enfants de moins de 5 ans, hors population enquêtée. Allocation par cellule en ménages
  (ordre `sha256` des identifiants de ménage, un ménage n'entre que s'il tient), déficits et
  reports comme en v2.
- **Une descente sur marges multiples** remplace l'équilibrage de la seule occupation : tant
  qu'un échange de deux ménages de **même taille** et **même cellule** réduit la somme des écarts
  absolus en points aux marges contrôlées, on l'applique. Marges : occupation et les six classes d'âge publiées (p. 11), et les sept
  marges personne gelées `cm1` — âge quinquennal, genre, taille de ménage, permis des adultes,
  abonnement TC, logement, immobiles. Déterministe (ordre de hachage, première amélioration),
  journalisée (`descente` : avant / après par marge, échanges, perte). Mesuré sur le vivier de
  5 063 : 289 échanges en 3 passes, perte 70,2 → 22,2 pt, chaque marge mesurée à ≤ 0,14 pt.
- **Le vivier est pré-imputé** (étape 3ter-a du notebook) : logement, vélo, permis et abonnement
  sont posés sur le checkpoint avant la sélection, pour être des marges et non des constats. Et
  l'export eqasim **garde les immobiles** (journée « domicile », drapeau racine `immobile`) : la
  population porte enfin ses 10,6 % de personnes sans déplacement, et la marge les contrôle.

Les cibles `cm1` sont des recalculs sur microdonnées (COEP, personnes interrogées) que le rapport
ne publie pas ou pas à ce pas : genre et permis deviennent mesurables, et leur source le dit.

### La règle v2 (historique, `aamas_seal_v2`)

- **Strates** : les 12 cellules couronne × motorisation de la cible jointe sur base **personne**
  (`scripts/AAMAS/cible_jointe_couronne_motorisation.yaml`, version `cj1`).
- **Effectifs cibles** : arrondi au plus fort reste des 12 parts × N — la somme fait exactement N.
- **Exclus avant tout** : domiciles hors des 453 communes (axe A4 du ticket 020), moins de 5 ans
  (population enquêtée), personas sans motorisation connue.
- **Ordre intra-cellule** : `sha256("aamas_seal_v1:" + person_id)` croissant — déterministe,
  indépendant de l'ordre du fichier, rejouable.
- **Équilibrage secondaire sur l'occupation** (v2) : l'allocation sur 12 cellules ne touche pas
  à l'occupation, et le générateur en porte un biais propre — 7,4 % d'actifs à temps partiel
  dans le vivier de 5 063 pour 5 % dans l'enquête, assez pour faire refuser le scellement. Une
  seconde passe **échange à l'intérieur de chaque cellule** : un persona d'une occupation
  sur-représentée sort, un persona d'une occupation sous-représentée de la même cellule entre
  (même classe d'âge de préférence), dans l'ordre `sha256`. Les 12 effectifs ne bougent pas
  d'une unité ; la cible est celle publiée (p. 11). Mesuré : **50 échanges** ramènent les sept
  postes sur la cible à l'unité, les classes d'âge bougent de ± 6 personas, vers la cible. Ce
  qui n'a pu être équilibré est consigné (`equilibrage.residuel`).
- **Auto-pondération** : la composition retenue épouse la cible, donc chaque persona garde son
  poids 1. Aucune pondération de plan à propager dans la chaîne de score.
- **Déficit** : une cellule que le vivier ne remplit pas est comblée dans la **même couronne**
  d'abord (la marge spatiale est celle qui déplace les cibles modales de 30 points), puis dans
  le vivier entier — chaque report est journalisé (`*_selection.json`), alarmé, et fait sortir en
  code 1. On livre les N, mais le contrôle final voit la cellule manquante.

### La taille du vivier

Monte-Carlo sur la composition du vivier de référence (incertitude des taux incluse),
probabilité que **les 12 cellules** soient toutes remplissables à N = 1 000 :

| Vivier | 2 000 | 2 500 | 2 700 | 3 000 | 3 500 | 4 000 | **5 000** | 6 000 |
|---|---|---|---|---|---|---|---|---|
| P(toutes remplies) | 22 % | 53 % | 63 % | 76 % | 90 % | 95,5 % | **99,2 %** | 99,9 % |

La cellule contraignante est *3ᵉ couronne × une voiture* (cible 44 pour 1 000, 17 dans un
vivier de 976). **5 000** est retenu. Comme la sélection s'insère **avant les étapes de
routage** du notebook (étape 3ter de
[generate_population.ipynb](../../scripts/data/population/generate_population.ipynb)), le
vivier ne coûte que la synthèse eqasim ; le scheduling et le réchauffage OSMnx ne tournent
que sur les 1 000 retenus.

---

## 2. Les marges, et d'où vient chaque cible

`reference_marges.py` est le seul endroit où les cibles sont assemblées. Chaque marge porte sa
**base** (personne ou ménage), son **échelle** (ordinale → EMD, nominale → JSD) et sa **source**.

| Marge | Base | Cible | Source |
|---|---|---|---|
| `classe_age` (6 classes) | personne | 16 / 13 / 14 / 22 / 19 / 16 % | rapport AUAT p. 11, via `population_emc2_2023.yaml` |
| `occupation` (7 postes) | personne | 17 / 9 / 39 / 5 / 7 / 18 / 5 % | rapport p. 11 |
| `motorisation_personne` | personne | **13,6 / 37,8 / 48,7 %** | recalcul microdonnées (COEP), gelé `cj1` — **non publié** |
| `motorisation_menage` | ménage (1/taille) | 19 / 45 / 35 % | rapport p. 21 |
| `couronne` | personne | 36,4 / 34,1 / 14,2 / 15,4 % | rapport p. 10 (habitants de 5 ans et +) |
| `couronne_x_motorisation` (12 cellules) | personne | joint recalculé | microdonnées (COEP), gelé `cj1` |
| `genre` | personne | **aucune** | le rapport ne publie pas la répartition par sexe |
| `permis_adultes` | personne | **aucune** | le mot « permis » n'apparaît qu'une fois, p. 4 |

**Deux bases à ne jamais confondre.** Le rapport publie la motorisation par **ménage** (p. 21).
Une population synthétique est un échantillon de **personnes** : un ménage multi-motorisé de
quatre y apparaît quatre fois. Sur base personne, « deux voitures et + » pèse **48,7 %** et non
35 % ; allouer des personas sur la base ménage serait une erreur de base, pas de tirage. La
cible jointe est donc recalculée sur les microdonnées avec le poids personne (`COEP`), et
**gelée** avec sa provenance (empreintes des fichiers, effectifs, date) pour que le contrôle
tourne sans les microdonnées d'accès restreint. Ses contre-épreuves retrouvent la page 21
(19,4 / 45,3 / 35,3 en base ménage) et la page 11 (classes d'âge).

**Ce qui n'a pas de cible le dit.** Genre et permis sortent `non mesurable — aucune cible
publiée`, jamais 0. Des **candidats** recalculés (P2, P7, COEP : femmes 51,3 %, permis adultes
85,9 %) sont affichés à côté, étiquetés comme recalculs.

---

## 3. La batterie, par marge

Pour chaque modalité : part observée, **IC95 de Clopper–Pearson**, cible, écart en points,
verdict **TOST** à la borne d'indifférence `--borne` (± 1 pt par défaut, annoncée d'avance),
effectif. Par marge : **χ² d'ajustement** — parce que le gabarit le demande — publié avec son
**V de Cramér** et l'avertissement qui va avec (sur 1 000 individus il ne tranche pas 0,4 pt,
sur 13 000 il rejette tout) ; **EMD** sur l'ordinal, **JSD** sur le nominal — les définitions
**exactes** du moteur de score (`calibration.metrics`), importées par le pont
`scripts.synthesis.sources.import_calibration`, jamais recopiées.

| TOST | Condition | Verdict de la modalité |
|---|---|---|
| `équivalent` | IC90 de la part ⊂ [cible − borne, cible + borne] | conforme |
| `non concluant` | ni l'un ni l'autre | conforme (l'écart n'est pas établi) |
| `écart` | IC95 exclut la cible **et** \|Δ\| > borne | à corriger ou à publier |

- **Effectif minimal** (`--n-min`, 30) : une modalité en dessous est `non mesurable` — un IC
  sur huit individus n'est pas une mesure. Même règle pour une cellule du croisement
  (`--n-min-cellule`, 50).
- **Hypothèse d'indépendance, dite.** Les personas sont des tirages à poids 1 : l'IC est
  binomial, sans effet de grappe. C'est **faux** pour les attributs de ménage tant que la
  population ne porte pas d'identifiant de ménage — l'export eqasim élargi (`household.id`) le
  pose ; le bootstrap par ménage viendra avec. Base ménage : pondération 1/taille et n efficace
  de Kish, affichés.

**Le croisement**, en deux lectures : le joint observé contre la **cible jointe** (marge
`couronne_x_motorisation`), et contre le **produit des marges observées** — le null d'une
synthèse par marges. Un χ² élevé sur le second dit que la population porte une dépendance
couronne–motorisation ; seul le premier dit si c'est la bonne. Une table dégénérée (une
couronne ou une motorisation sans aucun persona) rend `non mesurable` avec la modalité vide
nommée, au lieu d'interrompre le contrôle.

**La ligne « scolaires avec activité d'études »** (section ménages et mobilité, ticket 031
§ 1.2) : part des 6-17 ans déclarés scolaires et mobiles qui ont au moins une activité
`education` dans la journée, face à l'EMC² 2023 (90 à 95 % un jour de semaine ; seuil 88 %).
Ce n'est pas une marge de la sélection — la descente n'échange pas sur ce critère — mais un
témoin des **chaînes d'activités** : sous le seuil, l'écart sort dans la synthèse comme
« à publier », nature « journées donneuses ENTD et appariement eqasim ». Ce qui l'a fait
monter : les journées donneuses restreintes aux jours de classe (fork eqasim, 2026-09-03), et
surtout l'appariement sur l'ENTD nationale — le service Docker appariait jusqu'ici sur
**308 donneurs** résidents de Haute-Garonne (cf. § 6, « ce que la v3 portait sans le dire »).

### Les verdicts, et ce qu'ils engagent

| Verdict | Sens | Effet sur le scellement |
|---|---|---|
| `conforme` | TOST équivalent, ou écart non établi | — |
| `à corriger` | écart établi sur une marge que la **sélection sait refermer** (couronne, motorisation, joint, âge, occupation) | **refus** |
| `à publier` | écart établi sur une marge que la sélection ne referme pas (base ménage sans identifiants) | scellé, écart dans la synthèse |
| `non mesurable` | pas de cible publiée, ou effectif insuffisant | scellé, déclaré |

Code de sortie : 0 tout conforme · 1 au moins un `à corriger` · 2 population ou référence
illisible.

---

## 4. Le journal de recoupement

Le tableau § 2.1 du protocole publie huit marges « conformes ». Le contrôle les **recoupe**
(règle 5 de [docs/paper/README.md](../paper/README.md)) : chaque ligne face à sa référence, avec
la source. Sur la population de référence, les neuf lignes s'écartent — âge « moins de 18 ans »
publié 19,4 % contre 16,0 % dans l'enquête (5 ans et +), « 18-64 » 62,1 % contre 68,0 %,
ménages sans voiture 22,3 % contre 19,0 %. Rien n'est corrigé en silence : les écarts sont à
consigner en Annexe F du manuscrit.

---

## 5. Le scellement

`seal_population.py seal` rejoue le contrôle sur le fichier final, **refuse** s'il reste un
`à corriger` (rien n'est écrit, le candidat reste en place), et sinon produit un dossier —
`data/population/population_1000_AAMAS/` par défaut :

| Fichier | Contenu |
|---|---|
| `population.json` | la population, octet pour octet |
| `MANIFEST.yaml` | sha256 du fichier et de sa source, effectif, règle de sélection et déficits, verdicts, borne, cible jointe (version, sha256), révision git, note libre |
| `CONTROLE.md` · `report.json` | le rapport de contrôle, lisible et structuré |
| `selection.json` | le journal de sélection (cibles, retenus, reports, `person_ids`) |

**Un dossier scellé ne se modifie pas** : toute correction de la population produit un
nouveau dossier, et les jeux gelés comme les runs qui le citent citent son sha256. Le script
refuse d'écrire dans un dossier non vide.

### Sauvegarde : le sceau et son vivier

`data/population/sauvegardes/population_1000_AAMAS_<date>.tar.gz` archive le dossier scellé
**et le vivier** dont il est tiré (brut eqasim et checkpoint `4_zone_enriched`, 5 063 personas,
sha256 consigné dans `selection.json`). Sans le vivier, la sélection n'est pas rejouable ;
avec, `seal_population select --pool <vivier> --n 1000` redonne le même fichier au sha256
près. Le dossier `sauvegardes/` est versionné (négation dans `data/.gitignore`) ; une archive
ne se modifie pas, un nouveau scellement en produit une nouvelle, datée.

### Consommation par le runtime

Sans réglage, le contrôleur cherche `{eqasim_output_dir}/{prefix}population_{population_size}.json`,
le fait générer par eqasim s'il manque, filtre sur la bbox éventuelle, puis **ré-échantillonne
au hasard** à `population_size` (`population_sample_seed`) — c'est ce tirage qui faisait 930
personas du fichier de 1 021. Le réglage `data.population_file` court-circuite tout cela :

```yaml
# llm-agents/config/config.yaml
data:
  population_file: /data/eqasim-output/population_1000_AAMAS_v3/population.json
```

Le chemin est celui **vu du conteneur** (`./data/population` est monté sur
`/data/eqasim-output`), absolu. Le fichier est pris **entier** : s'il ne compte pas exactement
`population_size` agents après le filtre bbox, le chargement refuse (`[ALARME]`) au lieu de
ré-échantillonner — un sceau ne se rogne pas en silence. Un fichier absent est une erreur de
configuration, pas un retour à eqasim. `population_size` (côté GAMA, `sim_params.yaml`) doit
donc valoir l'effectif scellé.

### Ce que le fichier scellé porte de plus

L'export eqasim élargi (fork `eqasim-toulouse`, stage `llm_agents`) pose **à la racine** de
chaque enregistrement — jamais dans `traits_json`, qui entre dans le narratif du prompt et dans
la clé du cache de décisions :

- `household.id`, `household.iris_id`, `household.commune_id` — le ménage et sa commune, sans
  résolveur géométrique ; condition du bootstrap par ménage et de la négociation intra-ménage
  (§ 6.3 du papier) ;
- `provenance.census_person_id`, `provenance.hts_id` — le donneur RP et le donneur ENTD ;
- `validation.commute_mode` — le mode de navette **déclaré** (RP `TRANS`). ⚠ C'est la réponse
  au problème que l'agent doit résoudre : il **ne doit pas atteindre le prompt**. Il sert à
  comparer, individu par individu, le mode simulé du trajet domicile-travail au mode déclaré.

Le modèle `Person` (pydantic v2, sans `extra='forbid'`) ignore ces champs au chargement : ils
vivent dans le fichier, pas dans l'agent.

---

## 6. La population scellée v4 du 2026-09-03 — le périmètre des 453 communes

`data/population/population_1000_AAMAS_v4/` — sha256 `9f05c655c3ad2cf4…`, **1 000 personas en
513 ménages entiers** (469 complets au sens strict, 95,1 % des membres déclarés présents), tirés
par la règle `aamas_seal_v4` dans un vivier eqasim de **11 329** (`population_size` 10 000, six
départements, BD TOPO 2025-03-15, BAN 2026-09-03, ENTD nationale, jours de classe, borne d'âge 17,
personnes à commune « undefined » pondérées ; 335 enfants de moins de 5 ans, 14 sans domicile et
1 domicile hors des 453 communes exclus). Aucun déficit ; descente 393 échanges en 3 passes, perte
74,0 → 5,0 pt. **Périmètre** : six départements représentés (31 : 939, 32 : 9, 81 : 30, 82 : 19,
09 : 2, 11 : 1 ; 141 communes), 53 des 154 habitants de 3ᵉ couronne (34 %) hors Haute-Garonne
comme les 35 % de l'enquête ; 0 activité hors du polygone. Plannings recalés sur le graphe du
polygone (3 291 paires, 17 `None`, congestion par zone, repli à la vitesse du mode). Traces :
`docs/traces/2026-09-03_18-16_controle_toulouse_population_1000_AAMAS_v4/`,
`…_18-16_audit_perimetre_v4/`, `…_18-03_controle_vivier_10000_v4/`. Sauvegarde
`data/population/sauvegardes/population_1000_AAMAS_v4_2026-09-03.tar.gz` ; `config.yaml` repointé.

**Contrôle : 12 marges conformes, 0 à corriger, 1 à publier, 0 non mesurable.** La marge à publier
est la motorisation en **base ménage** (1/taille, n efficace 752) : ménages sans voiture 22,8 %
contre 19,2 % (+3,6 pt) — la seule marge que la sélection n'alloue pas ; en base personne elle est
conforme. Immobiles **10,6 %** ; **scolaires (6-17 ans) avec activité d'études 131 / 148 =
88,5 %** (seuil 88, enquête 90-95 ; v3 : 54 %) ; mobilité 3,33 déplacements par persona et 3,73
par mobile (enquête 3,53 / 3,95). Audit de périmètre : A1, A2, A4, A9 conformes, A3, A5, A8 à
publier, A6 et A7 propriétés d'un run. Équipement vélo : chaque taille de ménage dans sa tolérance ; la pente par taille
(27,3 / 44,4 / 63,4 / 55,5 % sur 218 / 148 / 69 / 55 foyers) est « non concluante » sur 1 000 agents et se
juge sur le vivier, où elle est croissante (32,8 / 49,1 / 55,0 / 60,9 % sur 2 350 / 1 657 / 744 / 532 foyers) —
règle du 2026-09-03, page [velo-equipement.md](velo-equipement.md). La synthèse HTML lit ces deux verdicts
dans les rapports `enrich_personal_bike --check --rapport-json` de la cohorte et du vivier (`--velo`,
`--velo-vivier` de `synthese_representativite.py`).
Le vivier, lui, avait 9 marges à corriger (65 ans et + +3,4 pt, étudiants −2,8 pt, immobiles
19,4 %, Toulouse −1,8 pt) : la distance entre les deux est ce que la sélection fait.

**Ce que la v4 change dans la lecture.** Le périmètre est celui de l'enquête, exactement ; les
chaînes d'activités viennent pour la première fois de l'ENTD nationale appariée par classe d'âge
(la v3 et ses devancières tiraient dans 308 donneurs résidents du 31) ; les écoliers vont à
l'école. Les runs v3 et v4 ne sont pas comparables. Synthèse HTML :
`docs/paper/population/synthese_representativite_v3_population_v4_2026-09-03.html`.

## 6 bis. La population scellée v3 du 2026-09-03 (historique)

`data/population/population_1000_AAMAS_v3/` — sha256 `8d8bfa3645fa77fb…`, **1 000 personas en
514 ménages entiers**, tirés par la règle `aamas_seal_v3` dans un vivier eqasim de **11 922**
(`population_size` 10 000, immobiles gardés : 1 798, enfants de moins de 5 ans : 364, exclus).
Aucun déficit ; descente 279 échanges en 5 passes, perte 39,9 → 6,1 pt. Trace :
`docs/traces/2026-09-03_01-18_controle_toulouse_population_1000_AAMAS/`.

**Contrôle : 13 marges conformes, 0 à corriger, 0 à publier, 0 non mesurable.** Le vivier, lui,
en avait 9 à corriger (3ᵉ couronne −5,2 pt, immobiles 15,1 %, temps partiel +2,4 pt, 65 ans et +
+2,2 pt) : la distance entre les deux est ce que la sélection fait.

| Marge | Écart max avant descente | après | Verdict |
|---|---|---|---|
| occupation | 4,10 pt | 0,30 | conforme |
| âge quinquennal (15) | 2,86 | 0,10 | conforme |
| genre | 0,08 | 0,02 | conforme |
| taille de ménage (personne) | 4,76 | 2,16 | conforme — la seule marge que des échanges à taille égale ne bougent pas |
| permis (adultes) | 0,31 | 0,01 | conforme |
| abonnement TC | 0,15 | 0,05 | conforme |
| logement | 0,32 | 0,04 | conforme — mesuré grâce à la pré-imputation |
| immobiles | 12,5 % | **10,6 %** | conforme (cible 10,64) |
| classes d'âge (6), motorisation ×2, couronne, croisement | — | — | conformes (allocation) |

**Ménages** : 514, dont 485 complets au sens strict de la taille déclarée (94,4 %) — les 29 autres
n'ont que des enfants de moins de 5 ans absents, hors population enquêtée ; 96,7 % des membres
déclarés présents ; audit A8 : 2,5 % de membres absents (54,6 % en v2, 11,2 % sur la population
de référence). **Mobilité** : 3,47 déplacements par persona, 3,88 par persona mobile (enquête 3,53
et 3,95) — l'écart restant est celui des chaînes ENTD 2008, seul « à publier » de la synthèse.
Depuis le 2026-09-03, les journées donneuses ENTD sont des **jours de classe** (hors vacances
scolaires, hors mercredi des moins de 11 ans — fork eqasim, ticket 031 § 1.2) : la v3 avait été
générée avant ce filtre, avec 82 écoliers sur 151 mineurs mobiles en activité d'études ; le
prochain vivier doit en compter ≥ 88 %, et le contrôle gagnera la ligne « scolaires avec
activité d'études » face à l'EMC² (90 à 95 %).

**Ce que la v3 change dans la lecture.** Genre, permis, abonnement, logement et immobiles sont
désormais **alloués** (par la descente) : leur conformité mesure la sélection, comme celle des
cellules. Ce qui reste probant sans allocation : la motorisation en base ménage (1/taille) et
les classes d'âge à 6 postes lorsqu'elles ne sont pas incluses — ici, l'âge quinquennal l'est,
donc les 6 classes le sont par construction. La représentativité « réelle » du générateur se lit
sur le **vivier** (9 marges à corriger), pas sur la cohorte scellée.

**Ce que la v3 portait sans le dire (constaté le 2026-09-03, ticket 031).** La configuration
synpp construite par le service Docker ne portait ni `filter_hts: false`, ni les attributs
d'appariement, ni le seuil de `config_toulouse.yml` (ticket 008, A1.a) : synpp retombait sur ses
défauts, `filter_hts: True`, soit **308 donneurs ENTD** résidents de Haute-Garonne pour 12 000
personnes à apparier, et une dégradation qui abandonnait la classe d'âge avant le sexe. Les
chaînes d'activités de la v3 — et des populations précédentes générées par le service — viennent
de ce vivier réduit ; c'est une part de l'écart de mobilité « à publier » (3,47 déplacements par
persona contre 3,53) et de la moitié des scolaires sans école. Le service part désormais de
`config_toulouse.yml` (source unique) ; la v4 sera la première population appariée sur l'ENTD
nationale avec la classe d'âge tenue.

## 6 ter. La population scellée v2 du 2026-09-02 (historique)

`data/population/population_1000_AAMAS/` — sha256 `f67b07772f3dced9…`, **1 000 personas**,
tirés dans un vivier eqasim de **5 063** (`population_size` 5 000, périmètre par liste de
communes, graine 1234) par la règle `aamas_seal_v2` : 12 cellules servies sans déficit,
**50 échanges** d'équilibrage sur l'occupation. Trace du contrôle :
[`docs/traces/2026-09-02_population_1000_AAMAS/`](../traces/2026-09-02_population_1000_AAMAS/README.md).

| Marge | Verdict | V de Cramér | Pire écart |
|---|---|---|---|
| classe_age | conforme | 0,031 | 50-64 ans −1,4 pt |
| occupation | conforme | 0,000 | 0,0 pt (équilibrée) |
| motorisation_personne | conforme | 0,001 | 0,1 pt |
| motorisation_menage (1/taille) | conforme | 0,035 | une voiture −2,3 pt |
| couronne | conforme | 0,001 | 0,1 pt |
| couronne_x_motorisation | conforme | 0,002 | 0,05 pt |
| genre, permis | non mesurable | — | aucune cible publiée (candidats : 51,3 % / 85,9 %) |

L'audit de périmètre rend **A2, A4 et A9 conformes** (0 domicile hors périmètre, L1 spatial
0,1 pt) ; A3, A5, A7, A8 restent « à publier », A6 est une propriété du run.

**Une limite nouvelle, mesurable grâce à `household.id`.** La sélection est **par personne** :
les 1 000 retenus appartiennent à 865 ménages, dont **308 complets** (35,6 %) ; 51 % des
membres de ces ménages sont présents (740 ménages n'ont qu'un membre retenu). Taille
déclarée 2,74, taille présente 1,16. Sans conséquence pour le choix modal individuel de
l'article ; à déclarer pour tout ce qui dépend des co-résidents (partage de voiture, chaîne
de véhicules). Une sélection **par ménage** est le remède, et un autre ticket.

## 7. Synthèse des écarts — l'état de la population de référence, avant scellement

`control_population.py` termine toujours par cette section. Sur
`toulouse_population_1000.json` (1 021 personas, 2026-09-02 — trace archivée :
[`docs/traces/2026-09-02_controle_population_reference/`](../traces/2026-09-02_controle_population_reference/README.md)) :

| Écart | Amplitude | Nature | Refermable au scellement ? |
|---|---|---|---|
| Domiciles hors des 453 communes | 45 personas (4,4 %) | population | **oui** — exclusion |
| Couronne | 3ᵉ couronne 9,5 % contre 15,4 % (−5,9 pt) | cadre de tirage (Haute-Garonne) | **oui** — allocation stratifiée, vivier ≥ 5 000 |
| Couronne × motorisation | Toulouse × 2 voitures et + 12,5 % contre 8,4 % | croisement | **oui** — allocation stratifiée |
| Classes d'âge | 25-34 ans +2,8 pt, 35-49 ans −2,8 pt | composition | partiellement — marge contrôlée, non allouée |
| Occupation | actifs à temps partiel 9,8 % contre 5,0 % | composition | partiellement — idem |
| Genre, permis | — | aucune cible publiée | non — à déclarer |
| Motorisation (deux bases) | conforme | — | — |

La composition **intra**-3ᵉ couronne reste une limite structurelle (100 communes sur 275 hors
du cadre de tirage) qu'aucune sélection ne referme : à déclarer, pas à corriger.

---

## Voir aussi

- [perimetre-population.md](perimetre-population.md) — les neuf axes de l'audit de périmètre (ticket 020).
- [population-post-traitements.md](population-post-traitements.md) — les étages de post-traitement.
- [Ticket 028](../tickets/ticket_028_temps_terminal_couronnes_communales.md) — le temps terminal aligné sur les couronnes communales.
- [JUSTIFICATION_TAILLE_ECHANTILLON.md](../paper/JUSTIFICATION_TAILLE_ECHANTILLON.md) — le raisonnement sur N.
- Rapport AUAT/CEREMA EMC² 2023 (68 p.) — pages 10, 11, 21, 26 ; fiches méthodologiques CEREMA
  (hiérarchie des modes, dimensionnement par secteur) : aucune marge toulousaine.
