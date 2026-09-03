# Ticket 031 — Périmètre des 453 communes : la population d'abord, la chaîne ensuite

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ce qui suit est une **spécification**. Décision issue du rapport de périmètre du
> 2026-09-03 (`docs/paper/population/RAPPORT_PERIMETRE_453_COMMUNES.html`) : le périmètre
> d'étude devient celui de l'enquête EMC² 2023, les 453 communes de six départements (option A),
> délimité par le **polygone des communes** et non par un rayon. Deux parties : construire le
> fichier de population de ce périmètre, puis porter le reste de la chaîne. La seconde partie
> est un inventaire d'impacts **à approfondir**, pas encore une spécification.

## Ce qui est mesuré (3 septembre 2026)

- La population scellée v3 tire dans la seule Haute-Garonne (346 des 453 communes, 93,7 % de la
  population enquêtée) ; 35 % des habitants de la 3ᵉ couronne vivent hors du cadre.
- Aucune emprise technique ne couvre le périmètre : graphe OSMnx à 30 km (98 des 154 agents de
  3ᵉ couronne dehors), extrait OSM d'OTP de 73 × 72 km (trois gares TER dehors), monde GAMA =
  enveloppe des lignes Tisséo (163 domiciles dehors), filtre runtime rectangulaire (79 agents
  écartés, donc sceau refusé).
- Voirie OSM 2022 : 998 k nœuds pour les 453 communes contre 765 k pour le disque de 30 km
  (+30 %) ; surface 5 428 km² contre 2 823.
- Dans le vivier eqasim, 50 à 54 % des 6-17 ans ont une activité d'études (EMC² : 90 à 95 %) :
  les journées donneuses ENTD 2008 incluent les vacances scolaires (20 % des journées) et le
  mercredi des écoliers de 2008.
- Le champ `household.commune_id` de l'export eqasim vaut `undefined` dans la v3 ; la commune
  est disponible dans `traits_json.residence_insee`.

---

## Partie 1 — Construire le fichier de population du périmètre (scellement v4)

Aucune dépendance au ticket 030 : ses lots A à D sont du runtime. Son ancien lot 0 (les
écoliers vont à l'école) est absorbé ici (§ 1.2), parce qu'il façonne la population.

### État au 3 septembre 2026 (après-midi)

- [x] § 1.1 eqasim : six départements, filtre par liste de communes journalisé, `household.commune_id`
  et `iris_id` renseignés pour tous (fork, commits locaux).
- [x] § 1.2 jours de classe : livré le matin, **corrigé l'après-midi** (les donneurs écartés
  sortaient du vivier comme immobiles : 40,6 % d'immobiles générés). Ligne de contrôle ajoutée.
- [x] **Constat hors ticket, corrigé** : le service Docker n'appliquait pas `config_toulouse.yml`
  (ni `filter_hts: false`, ni les attributs d'appariement) — 308 donneurs ENTD résidents de
  Haute-Garonne pour toutes les populations générées, v3 comprise. Voir § 1.2 bis.
- [x] § 1.3 règle `aamas_seal_v4` (namespace distinct, six classes d'âge, journal du périmètre),
  tests étendus (17 verts).
- [x] § 1.4 graphes OSMnx du polygone (`make osmnx-perimeter-graph`) et mesures O1, O2, O4.
- [ ] § 1.0 données des cinq départements : **porte d'approbation 1, non levée** — URL, tailles et
  commandes prêtes ci-dessous ; l'édition 2024-09-15 n'est plus servie par l'IGN.
- [ ] § 1.5 sceau v4 : impossible sans § 1.0. Une **répétition** de la chaîne complète a tourné
  sur la Haute-Garonne (`toulouse_population_1000_AAMAS_v4_repetition_HG.json`, non scellée) ;
  résultats ci-dessous.

### 1.0 Données à obtenir — avec l'accord de l'auteur du dépôt
| Donnée | Source | Volume |
|---|---|---|
| BD TOPO départements 32, 81, 82, 09, 11 | IGN géoservices, édition alignée sur D031 (2024-09) — **n'est plus servie** ; 2025-03-15 disponible | estimé 1 à 2 Go ; **mesuré 0,15 à 0,23 Go** par département (archives `.7z`, édition 2025-03-15) |
| BAN `adresses-32/81/82/09/11.csv.gz` | adresse.data.gouv.fr | estimé ≈ 20 Mo ; **mesuré 3,9 à 8,4 Mo** |
| OSM | déjà présents : `midi-pyrenees-220101`, `languedoc-roussillon-220101` (Aude) | — (fraîcheur 2022 à noter) |

**Porte d'approbation 1 — préparée le 2026-09-03, rien n'est téléchargé.** Vérifié sur le
service de téléchargement de la Géoplateforme (flux Atom `data.geopf.fr/telechargement/resource/BDTOPO`,
métadonnées seules) : **l'édition 2024-09-15 de la BD TOPO n'est plus servie** (404 pour les six
départements, D031 compris) ; la seule édition 3-4 TOUSTHEMES SHP LAMB93 disponible est
**2025-03-15**. Tailles annoncées par le service :

| Département | Archive BD TOPO 2025-03-15 (`.7z`) | Taille | BAN `adresses-XX.csv.gz` |
|---|---|---:|---:|
| 32 Gers | `…/BDTOPO/BDTOPO_3-4_TOUSTHEMES_SHP_LAMB93_D032_2025-03-15/BDTOPO_3-4_TOUSTHEMES_SHP_LAMB93_D032_2025-03-15.7z` | 0,19 Go | 4,3 Mo |
| 81 Tarn | idem `D081` | 0,23 Go | 8,0 Mo |
| 82 Tarn-et-Garonne | idem `D082` | 0,16 Go | 5,3 Mo |
| 09 Ariège | idem `D009` | 0,15 Go | 3,9 Mo |
| 11 Aude | idem `D011` | 0,23 Go | 8,4 Mo |
| 31 Haute-Garonne (pour l'homogénéité) | idem `D031` | 0,34 Go | présent |

Préfixe des archives : `https://data.geopf.fr/telechargement/download/BDTOPO/` ; BAN :
`https://adresse.data.gouv.fr/data/ban/adresses/latest/csv/adresses-<dep>.csv.gz` (fichiers du
2026-09-03, régénérés chaque nuit). Les `.7z` se posent tels quels dans
`eqasim-toulouse/data/bdtopo_toulouse/` (le stage `data.bdtopo.raw` lit les archives `.7z`,
couche `batiment`) et les BAN dans `ban_toulouse/`. Commande prête (à lancer par l'auteur) :

```shell
cd eqasim-toulouse/data
for d in 032 081 082 009 011; do
  curl -fL -o bdtopo_toulouse/BDTOPO_3-4_TOUSTHEMES_SHP_LAMB93_D${d}_2025-03-15.7z \
    "https://data.geopf.fr/telechargement/download/BDTOPO/BDTOPO_3-4_TOUSTHEMES_SHP_LAMB93_D${d}_2025-03-15/BDTOPO_3-4_TOUSTHEMES_SHP_LAMB93_D${d}_2025-03-15.7z"
done
for d in 32 81 82 09 11; do
  curl -fL -o ban_toulouse/adresses-${d}.csv.gz "https://adresse.data.gouv.fr/data/ban/adresses/latest/csv/adresses-${d}.csv.gz"
done
```

Puis `EQASIM_DEPARTMENTS=31,32,81,82,09,11 docker compose up -d eqasim` (ou `DEPARTMENTS = None`
dans le notebook) ; le service vérifie la présence des données avant de générer. **Question
ouverte** : accepter le mélange BD TOPO D031 2024-09-15 / autres 2025-03-15 (six mois d'écart sur
le bâti, effet négligeable sur le tirage des domiciles) ou retélécharger D031 en 2025-03-15
(0,34 Go) pour une édition homogène — recommandation : homogène, et noter l'édition dans le
MANIFEST.

### 1.1 eqasim : six départements et la liste des communes (`config_toulouse.yml`, `data/spatial/`) — livré
- `departments: ["31", "32", "81", "82", "09", "11"]` et `communes_file` (les 453 codes) dans
  `config_toulouse.yml` ; le service Docker part de ce fichier (monté) et le déploiement restreint
  par `EQASIM_DEPARTMENTS` (défaut `31` tant que la porte 1 n'est pas levée).
- Le filtre par **liste de communes** existait depuis le ticket 026 (`communes`, wrapper Docker) :
  le « 4,4 % hors des 453 » venait de la population de référence d'avant ce ticket ; les viviers
  v3 et v4 sont à 0. Ajouté : `communes_file`, le **journal par département** (vérifié sur le
  référentiel IRIS 2024 : 346 / 38 / 27 / 22 / 10 / 10, 713 IRIS ; 346 et 602 IRIS pour le 31
  seul), le **refus** d'une commune demandée absente du référentiel, et un **contrôle préalable**
  des BD TOPO / BAN par département dans le wrapper (code 3 avec la liste de ce qui manque).
- Export `llm_agents.py` : `household.commune_id` et `iris_id` lus sur le tirage de zone du
  domicile (`spatial.home.zones`) — renseignés pour 11 922 / 11 922 (« undefined » pour 4 292 au
  recensement ; 276 communes distinctes sur le vivier Haute-Garonne) ; « undefined » compte comme
  manquant.

### 1.2 Journées donneuses ENTD = jours de classe (`data/hts/entd/cleaned.py`)
- Aujourd'hui : `V2_TYPJOUR == 1` (jour de semaine), première journée par personne.
- Proposé : **`V2_VAC_SCOL == 0` pour tous les donneurs** — l'EMC² s'enquête elle-même hors
  vacances scolaires, la population entière y gagne en cohérence, pas seulement les écoliers.
  **Livré le 2026-09-03** (fork, `hts_school_days_only`, `hts_exclude_wednesday_under_age: 11`).
  Mesuré au fil du pipeline (jours de référence) : 15 687 → 12 392 donneurs (−21 %) ; la plus
  petite classe d'âge garde 858 donneurs pour un seuil `matching_minimum_observations` de 5 ;
  scolaires mobiles avec trajet vers l'école 72,0 % → 90,8 %. Reste : régénérer le vivier et
  ajouter la ligne de contrôle.
- À décider : exclure aussi le **mercredi** (`V2_JOUR_DEP == 4`) pour les moins de 11 ans ? En
  2008 les écoliers n'avaient pas classe ce jour (17 % de trajets vers l'école) ; l'EMC² 2023
  mesure 91 % d'écoliers de 6-10 ans avec école, mercredis inclus. Hors vacances et hors
  mercredi, l'ENTD donne 88 à 96 %.
- Journaliser les journées écartées par motif ; cible : ≥ 88 % des 6-17 ans mobiles du vivier
  avec une activité `education`. Le contrôle de population gagne la ligne « scolaires avec
  activité d'études » (section ménages et mobilité) et la compare à l'EMC².
- **Décidé et livré : le mercredi est exclu pour les moins de 11 ans** (336 trajets).
- **Correction du 2026-09-03 après-midi.** La version du matin retirait les trajets des donneurs
  en vacances mais laissait ces donneurs dans le vivier : Kish sans trajet, ils devenaient des
  **immobiles** (40,6 % de la population générée, 50 % des 6-17 ans, contre 10,6 % dans
  l'enquête). Ils sortent désormais du vivier (`is_kish = False` : 3 295 donneurs écartés,
  14 702 Kish restants). Immobiles générés : 19,3 % (la sélection les ramène à 10,6 %).
- **Mesuré sur le vivier régénéré (Haute-Garonne, 11 922, 6 min) : 89,0 % des 6-17 ans mobiles
  ont une activité `education`** (6-10 ans 91,9 %, 11-14 ans 91,9 %, 15-17 ans 80,4 %) — contre
  57,5 % dans le vivier v3. Les 15-17 ans partagent la classe d'âge 15-29 de l'appariement
  (`AGE_BOUNDARIES` d'eqasim) avec les jeunes adultes : une borne à 17 ans les porterait plus haut
  (question ouverte, hors ticket). Ligne de contrôle : `control_population.py`, seuil 88 %,
  écart « à publier » en dessous.

### 1.2 bis Le vivier de donneurs du service Docker (constat du 2026-09-03, corrigé)
La configuration synpp construite par `generate_population.py` (service Docker) ne portait ni
`filter_hts`, ni `matching_attributes`, ni `matching_minimum_observations`, ni les réglages des
journées donneuses : synpp retombait sur ses défauts — `filter_hts: True`, soit **308 donneurs
ENTD** résidents de Haute-Garonne (323 après le filtre des jours de classe : 13 enfants de
6-10 ans, 7 de 11-14, 4 de 15-17) pour 12 000 personnes à apparier, seuil de 20 observations et
classe d'âge abandonnée par la dégradation avant le sexe — pendant que `config_toulouse.yml`
disait le contraire depuis le ticket 008 (A1.a). Vérifié dans le cache synpp du conteneur
(`data.hts.entd.reweighted` : 308 personnes depuis le 6 mai) et dans la dernière config
`/tmp/eqasim_config_*.yml`. **Toutes les populations générées par le service, v3 comprise,
portent des chaînes d'activités issues de ce vivier réduit** — une part de l'écart de mobilité
« à publier » (2,58 déplacements par persona contre 3,53) et de la moitié des écoliers sans école.
Corrigé : le wrapper part de `config_toulouse.yml` (source unique, monté dans le conteneur) et
refuse de générer sans lui (code 5) ; le vivier régénéré donne 2,93 déplacements par persona et
3,63 par mobile (enquête 3,53 / 3,95). Deux autres correctifs du wrapper : une régénération forcée
**remplace** le fichier cible (le fichier synpp se reconnaît à sa date), et la sortie du service
est en tampon ligne par ligne.
- Documentation : commentaire du réglage dans `config_toulouse.yml`, `README.md` et
  `CHANGELOG.md` du fork, `docs/setup/population.md`,
  `docs/arch/controle-population-jeu-de-test.md`, `docs/changelog.md`.

### 1.3 Vivier, pré-imputation, sélection v4
- Vivier de 10 000 (≈ 12 000 livrés) sur les 453 communes ; étape 3ter-a inchangée.
- Règle `aamas_seal_v4` — **livrée** : namespace de hachage `aamas_seal_v4:`, six classes d'âge
  dans la descente, journal du périmètre (définition « 453 communes, six départements, polygone
  communal », départements de résidence des retenus lus sur `household.commune_id`,
  avertissement si moins de six départements représentés), repris dans le MANIFEST ; cibles `cj1`
  et `cm1` inchangées. Dossier : `data/population/population_1000_AAMAS_v4/` (ré-inclus dans
  `data/.gitignore`). Le notebook attend cette règle à l'étape 3ter et invalide désormais aussi
  le checkpoint `4_zone_enriched` quand le vivier est régénéré (il repartait sinon de l'ancien
  vivier pré-imputé).

### 1.4 Routage des plannings sur le polygone (étapes 4+5 du notebook)
- Le recalage des horaires a besoin d'un graphe OSMnx couvrant les domiciles et les écoles de
  3ᵉ couronne. Graphes construits depuis l'extrait pbf du polygone des 453 communes
  (`osmium extract --polygon` sur les pbf régionaux, puis `graph_from_xml`), clé de cache
  distincte de `Toulouse, France_30000`. `MAX_WORKERS` ≤ 8 (mémoire + 30 %) ; réchauffage
  toujours désactivé.
- Mesures à consigner (actions O1, O2, O4 du rapport) : nœuds et arêtes par mode, taille du
  pickle, RAM d'un worker, ms par route, part de paires « même nœud » (attendu ≈ 0 en 3ᵉ
  couronne, contre la majorité aujourd'hui).
- **Livré** : `scripts/data/population/build_osmnx_perimeter_graph.py` (`make osmnx-perimeter-graph`),
  clé `444ca7e6a515` (label `perimetre_453_communes:cc1:osm-220101`), filtres réseau lus dans
  OSMnx 2.1.0, vitesses de `config/osmnx.yaml`, frontière `_in_city` copiée ; branché dans le
  notebook (`MAX_WORKERS` 6). Mesures `scripts/data/population/measure_osmnx_perimeter_graph.py`.
  Trace : `docs/traces/2026-09-03_10-23_graphe_osmnx_perimetre_453/`.

| Mesure (O1) | Disque 30 km (production) | Polygone 453 communes |
|---|---:|---:|
| marche : nœuds / arêtes | 204 924 / — | 176 340 / 472 544 (simplifié ; 135 629 voies) |
| vélo : nœuds / arêtes | 166 884 / — | 151 833 / 360 801 (117 061 voies) |
| voiture : nœuds / arêtes | 60 705 / — | 65 150 / 148 959 (61 734 voies) |
| voirie OSM brute (nœuds / voies highway) | 765 k / 126 k | 997 753 / 150 873 |
| pickle des trois graphes | 245 Mo | 223 Mo |
| RAM d'un worker (trois graphes chargés, hors pression mémoire) | 1 754 Mo (7,7 s de chargement) | 1 828 Mo (6,7 s) |
| construction | Overpass, minutes | 603 s, 2,7 Go de pointe, aucun téléchargement |
| arêtes en vitesse de repli | — | marche 5,1 %, vélo 32,0 %, voiture 1,2 % |

Les nœuds simplifiés du polygone sont **moins nombreux** en marche et vélo que ceux du disque
Overpass alors que la voirie brute est plus étendue (+30 %) : le disque de 30 km d'OSMnx est
découpé à la distance réseau après téléchargement d'une boîte englobante, ce qui laisse des
fragments ; et la 3ᵉ couronne est rurale (peu d'intersections). Le mode vélo prend 32 % d'arêtes
en vitesse de repli (14 km/h) : `speeds.bike` de `config/osmnx.yaml` n'a pas d'entrée pour
`track`, `service`, `footway`, `pedestrian`, `trunk` — inchangé ici (mêmes vitesses que la
production, c'est le contrat), à revoir en partie 2 (O3). O2 et O4 : voir la trace
`docs/traces/<date>_mesures_graphe_perimetre/` et la ligne OSMnx de la partie 2.

### 1.5 Audit, contrôle, scellement, sauvegarde
- Audit de périmètre : A4 = 0 persona hors des 453 communes ; A2, A9 conformes.
- Contrôle : 13 marges conformes + `classe_age` (six classes) ; ligne scolaires ; trace
  horodatée dans `docs/traces/`.
- Scellement (MANIFEST déclarant le périmètre « 453 communes, polygone communal »), sauvegarde
  `data/population/sauvegardes/population_1000_AAMAS_v4_<date>.tar.gz`, `config.yaml` repointé.
- **Non scellé le 2026-09-03** : la porte 1 n'est pas levée. La chaîne complète a tourné en
  **répétition sur la Haute-Garonne** (notebook, vivier 10 000 → 11 922, sélection v4 de 1 000,
  routage sur le graphe du polygone, export, traits, audit, contrôle avec trace) sous le nom
  `toulouse_population_1000_AAMAS_v4_repetition_HG.json` ; `config.yaml` reste sur la v3.
  Résultats : § « Répétition » ci-dessous, complété après le run.

### Répétition de la chaîne sur la Haute-Garonne (2026-09-03, non scellée)

Notebook `generate_population.ipynb` par papermill, `DEPARTMENTS = ['31']`, `POPULATION_SIZES =
[10000]`, `SELECT_N = 1000`, `SELECT_TAG = 'AAMAS_v4_repetition_HG'`, `MAX_WORKERS = 6`,
réchauffage sauté. Sortie : `data/population/toulouse_population_1000_AAMAS_v4_repetition_HG.json`.

- **Vivier** : 11 922 personnes (eqasim 6 min ; régénération forcée, fichier cible remplacé),
  0 domicile hors des 453 communes, 17 personnes sans domicile (chaîne sans activité `home`,
  exclues de la sélection), 364 de moins de 5 ans exclues. Contrôle du vivier pré-imputé (trace
  `docs/traces/2026-09-03_13-05_controle_vivier_10000_v4_repetition_HG/`) : 9 marges à corriger
  — dont 3ᵉ couronne 10,2 % contre 15,4 % (le cadre Haute-Garonne), immobiles 19,4 %, 65 ans et +
  +2,2 pt — 1 à publier (motorisation ménage), 3 conformes ; **scolaires avec activité d'études
  89,2 %** (1 376 / 1 542) ; 2,18 déplacements par persona après fusion des activités.
- **Sélection v4** : 1 000 personas en **505 ménages entiers**, aucun déficit, descente 356
  échanges en 3 passes, perte 70,4 → 6,35 pt ; toutes les marges mesurées (classe_age 1,80 →
  0,50 pt, occupation 2,30 → 0,50, âge quinquennal 2,76 → 0,39, taille de ménage 5,83 → 1,54,
  abonnement 2,85 → 0,05, logement 4,08 → 0,07, immobiles 5,76 → 0,05). Journal du périmètre :
  **1 département représenté sur 6** (`31` : 1 000), 131 communes — l'avertissement de cadre
  restreint est émis, c'est ce qui interdit de sceller.
- **Routage (étapes 4+5)** sur le graphe du polygone : lancé avec 6 workers, la machine — déjà à
  12 Go de swap pour d'autres usages — a swappé (six workers à 15 % de CPU chacun, 330 Mo de RSS à
  eux six : les graphes étaient paginés) ; arrêté après 10 min et **relancé avec 3 workers** sur
  les checkpoints (étapes 1 à 3ter sautées : même vivier, même règle). O4 in situ : `MAX_WORKERS`
  se règle sur la RAM **libre** au moment du run, pas sur la RAM totale — 6 est le plafond d'une
  machine de 32 Go dédiée, 3 quand 12 Go de swap sont déjà pris. Cause mesurée : **la VM Docker
  Desktop réserve 23,4 Go des 32 Go** (mémoire câblée : 26,7 Go avec LM Studio), il reste 5 à 8 Go
  à l'hôte pour le noyau du notebook et ses workers. Recommandation : ramener la VM Docker à
  10-12 Go pendant le routage (ou router dans un conteneur), et régler `MAX_WORKERS` sur
  `(RAM libre − 2 Go) / 1,8 Go`. Résultat du routage : **3 324 paires, 3 289 routées, 35 `None`
  (1,1 %), 736 s à 3 workers soit 221 ms par route** (machine en swap), 1 000 plannings valides ;
  export 3 471 activités dont 3 365 planifiées et 2 701 desservies en TC ; étape 8 : sept
  post-traitements `ok` ; étape 9 : **POPULATION COMPLÈTE**. RAM d'un worker mesurée hors
  pression mémoire, juste après le run : **1 754 Mo (disque de 30 km) et 1 828 Mo (polygone)** —
  le polygone ne coûte que +4 % par worker, sa voirie supplémentaire est rurale.
- **Contrôle du fichier exporté** (`make control-population`, trace
  `docs/traces/2026-09-03_13-20_controle_toulouse_population_1000_AAMAS_v4_repetition_HG/`) :
  **13 marges conformes, 0 à corriger, 0 à publier, 0 non mesurable** ; immobiles **10,6 %**
  (cible 10,6) ; **scolaires (6-17 ans) avec activité d'études 133 / 149 = 89,3 %** (seuil 88,
  enquête 90-95 ; v3 : 54 %) ; 505 ménages, 457 complets au sens de la taille déclarée (90,5 %),
  95,1 % des membres déclarés présents ; mobilité 2,47 déplacements par persona et 2,76 par mobile
  (v3 : 2,58 / 2,88 ; enquête 3,53 / 3,95) — l'écart de mobilité reste à publier, il ne tient
  plus au vivier de donneurs mais aux chaînes ENTD 2008 après fusion des activités consécutives.
  Le recoupement du tableau § 2.1 du protocole garde ses 7 lignes en écart (Annexe F).
- **Audit de périmètre** (`make audit-perimetre`, trace
  `docs/traces/2026-09-03_13-21_audit_perimetre_v4_repetition_HG/`) : **A1, A2, A4, A9
  conformes** (0 domicile hors des 453 communes ; couronnes par liste de communes ; répartition
  spatiale dans la tolérance), A3, A5, A8 à publier comme sur la v3, A6 et A7 non mesurables
  (propriétés d'un run). Critères 1 et 2 de la partie 1 tenus **sur le cadre Haute-Garonne** ;
  le critère « six départements représentés » ne peut l'être qu'après la porte 1.

### Critères d'acceptation — partie 1
1. Vivier : 0 persona hors des 453 communes ; six départements représentés ; ≥ 88 % des 6-17 ans
   mobiles avec activité `education`.
2. Sceau v4 : 1 000 personas en ménages entiers, 13 marges + classe_age conformes, immobiles
   ≈ 10,6 %, `household.commune_id` renseigné pour tous.
3. Plannings recalés sur un routage effectif : part de paires « même nœud » < 1 % en 3ᵉ couronne.
4. Documentation et changelog à jour ; synthèse de représentativité v3 (HTML) produite et
   inventoriée dans `docs/paper/README.md`.

---

## Partie 2 — Impacts sur le reste de la chaîne (inventaire, analyse à approfondir)

Chaque ligne est un impact identifié le 3 septembre 2026 ; la colonne « à mesurer » dit ce qui
manque pour en faire une spécification. Actions numérotées du rapport entre parenthèses.

| Maillon | Impact identifié | Mesuré ou constaté le 2026-09-03 (code vérifié) → décision proposée |
|---|---|---|
| **Chargement runtime** (`handle/application.py`) | Le filtre rectangulaire `TOULOUSE_OSM_ROUTES_30K_BBOX` doit devenir un filtre par **commune du domicile** (liste des 453) et un `contains` du polygone pour les activités ; un fichier scellé se charge entier ou se refuse | **Deux filtres successifs.** (1) `_prepare_population` (lignes 238-268) écarte tout agent dont le domicile **ou une activité** sort du rectangle 30 km, puis refuse un sceau dont l'effectif a bougé — 79 agents v3 écartés (67 par le domicile), sceau refusé ; la v4 en écartera davantage (3ᵉ couronne complète). (2) `world/population.py` → `eqasim_loader.perimeter_verdict` : trait `residence_zone` dans une couronne → admis ; `hors périmètre` → rejeté ; trait absent → bbox `world_bbox` = arrêts GTFS ± 0,05° (`factory.py:151`) — ce second filtre est déjà **par périmètre** et n'a rien à changer. `WorldGrid(world_bbox)` (`world_data.py:38`) borne l'index spatial sur les arrêts GTFS : à élargir au polygone. **Décision : faire** — remplacer le rectangle de (1) par `household.commune_id ∈ 453` (renseigné pour tous depuis ce jour) et, pour les activités, un `contains` du polygone (`CommunalZones`) ; une activité hors polygone (école, travail hors périmètre) n'écarte **pas** l'agent mais se compte et s'alarme (question ouverte n° 3) ; mesurer « aucun agent v4 écarté » au premier chargement. |
| **OSMnx runtime** (`osmnx_server.py`, `trip_helper/osmnx_direct.py`, `geography.py`) | Graphes sur le polygone (même construction qu'en 1.4) ; `TOULOUSE_CENTER_DIST_M` disparaît au profit d'une emprise ; frontière `_in_city` et facteur de congestion à revérifier hors du disque (O3) ; vitesses de repli moins sollicitées | **O1/O4 mesurés** (§ 1.4) : pickle 223 Mo contre 245, worker 1 828 Mo contre 1 754 (+4 %) hors pression mémoire (0,85-1,6 Go lus sous swap : `ru_maxrss` n'est pas fiable quand la machine swappe), chargement 7 s ; `MAX_WORKERS` se règle sur la RAM libre — 6 sur une machine dédiée, 3 quand la VM Docker en prend 23 Go. **O2** : voir `docs/traces/<date>_mesures_graphe_perimetre/` (part de paires « même nœud » par couronne d'origine, ms par route, `None`) — reporté ci-dessous dès la mesure achevée. **O3 vérifié dans le code** : `_in_city` = commune de Toulouse (géocodage, inchangé et copié pour la nouvelle clé) ; **hors de la commune, le facteur n'est pas 1 mais celui de l'agglomération TomTom** (`metro_raw`) — lundi 8 h : 2,04 en ville, **1,84 hors ville**, appliqué tel quel à un trajet rural de 3ᵉ couronne, ce que le rapport n'attendait pas. Vitesses de repli : le mode vélo n'a pas de vitesse pour `track`, `service`, `footway`, `pedestrian`, `trunk` → 32 % des arêtes du polygone en repli (14 km/h). Portage : `_GraphStore.get(city, dist)` et les deux `cache_key = md5(f"{city}_{dist}")` d'`osmnx_server.py` (l. 51-54, 131-134) deviennent une clé de graphe configurée (`PERIMETER_CACHE_KEY`), `TOULOUSE_CENTER_DIST_M` ne garde qu'un rôle d'audit. **Cache SQLite** (`osmnx_persistent_cache.make_key`) : clé = `routing_version` (`r1`) + mode + coordonnées (+ jour/heure en voiture), **indépendante du graphe** → une entrée calculée sur le disque de 30 km (dont les replis à 70 km/h) serait resservie sur le polygone ; le dossier de cache est par nom de population, donc une v4 part de zéro, mais **bumper `routing_version` à `r2`** au changement de graphe est le geste honnête. **Décision : faire** (partie 2), avec une passe sur `speeds.bike` et le facteur hors ville (question ouverte n° 4). |
| **OTP** (`otp-toulouse/`, `data/gtfs_year/`) | Extrait OSM sur le polygone (T1) ; GTFS liO en feed annuel (T2, 22,7 Mo, ODbL) ; cars TER éventuels (T6) ; `TOULOUSE_TRANSIT_SERVICE_WKT` recalculée (T4) ; calendrier liO (T5) ; trois instances plus lourdes | `otp-toulouse/toulouse/Toulouse.osm.pbf` (64 Mo, DVC, md5 `06099055…`) n'a **aucune recette** dans le dépôt (le `Makefile` ne fait que `--build` et `--load`) : son emprise ne se rejoue pas. L'extrait intermédiaire du § 1.4, `data/cache/osmnx/perimetre_453/perimetre_453.osm.pbf` (76 Mo, polygone exact, OSM 2022, toutes clés), **est** l'extrait T1 : à copier/renommer et à consigner dans un `Toulouse.osm.pbf.dvc` daté. `build-config.json` : `transitServiceStart/End` 2026 ; liO non chargé. Temps de construction et RAM par instance : **non mesurés** (pas de reconstruction sans décision sur liO). **Décision : reporter** dans un ticket OTP (T1 + T2 + T4 + T5 + T6 ensemble : une seule reconstruction des trois instances), après accord pour le téléchargement du GTFS liO (22,7 Mo). |
| **GAMA** (`Settings.gaml`, `includes/`) | Monde = polygone du périmètre au lieu de l'enveloppe Tisséo (G1) ; `routes.shp`/`stops.shp` avec liO et TER (G2) ; performance sur 106 × 93 km (G3) ; projection `roads.prj` UTM 48N à contrôler (G4) ; avertissement au chargement si le shapefile de routes ne couvre pas le monde | Vérifié : `Settings.gaml:61` `geometry shape <- envelope(routes0_shape_file)` (lignes Tisséo, WGS84 — `routes.prj` GCS_WGS_1984) ; `roads.prj` déclare bien **UTM zone 48N** (G4 confirmé : Toulouse est en 31N ; la voirie GAMA n'étant pas exploitée, l'effet est nul aujourd'hui mais le fichier ment). Pas de simulation lancée (hors périmètre de cette partie) : G1 et G3 restent à mesurer. **Décision : reporter** (ticket GAMA : monde = `couronne_perimetre.geojson` dissous, avertissement de couverture, G3). |
| **Ticket 030** (car scolaire) | Se branche ici : option `school_bus` pour les mineurs hors Tisséo ; sans elle, la 3ᵉ couronne simulée n'a pas de TC pour ses écoliers | Prérequis du ticket 030 (≥ 88 % des 6-17 ans mobiles avec activité `education`) **atteint sur le vivier de répétition : 89,0 %**. Le reste est inchangé (lots A à D). |
| **Résultats et métriques** | Temps terminal déjà par couronne communale (tt4) ; cibles modales inchangées (453) ; oracle LightGBM inchangé ; **les runs v3 et v4 ne sont pas comparables** | Ce qui repose sur la v3 : `docs/paper/MANUSCRIT_DETAILLE_2026.md`, `PROTOCOLE_SCIENTIFIQUE.md`, la synthèse `synthese_representativite_v2_population_v3_2026-09-03.html`, le ticket 029 et la page de contrôle ; runs archivés avec `population_file` : 4 sur le sceau v2, 1 sur la v3, 5 sans sceau. **Constat aggravant** : les chaînes d'activités de la v3 (et des runs antérieurs) viennent de **308 donneurs** résidents du 31 (§ 1.2 bis) — la comparaison v3/v4 porte aussi sur l'appariement, pas seulement sur le périmètre. **Décision : déclarer** dans le manuscrit (§ 2.2, annexe F) que la v3 est un jeu de mise au point, et **rejouer** les mesures publiées sur la v4. |
| **Caches et jeux gelés** | Cache OSMnx SQLite (réutilisable ?), cache OTP, cache sémantique LLM ; jeux gelés de `prompt_calibration` et campagne génétique construits sur une population antérieure | Vérifié : les jeux gelés `v9` à `v10c` épinglent `experiments/archive/2026-08-24_17_34/population_1000.json` (sha256 `4cd38bdc…`), `v5` à `v8` et `ctxL*` épinglent `2026-08-19_14_36/population_1000.json` — **aucun ne dépend de la v3 ni de la v4** : ils restent valides pour ce qu'ils mesurent (calibration du prompt sur une population donnée) et se **déclarent** tels quels ; un jeu gelé sur la v4 (v11) est un autre ticket. Cache OSMnx : clé indépendante du graphe (voir OSMnx) mais dossier par population → v4 vierge ; bump `routing_version`. Cache OTP : dossier par population (`otp_persistent_cache_dir/<population>`) → vierge. Cache sémantique LLM : clé sur le prompt (traits + options + météo) → nouveaux personas, nouvelles clés ; rien à purger, rien à réutiliser. **Décision : déclarer** (jeux gelés), **régénérer** de fait (caches par population). |
| **Visualisation** (`vizpop.py`, Grafana) | `vizpop` utilise la bbox 30 km ; emprises des cartes Grafana à vérifier | `llm-agents/vizpop.py:17,91` trace `TOULOUSE_OSM_ROUTES_30K_BBOX` (rectangle gris) et `TOULOUSE_TRANSIT_SERVICE_WKT` : à remplacer par le polygone des couronnes (`couronne_perimetre.geojson`) et l'enveloppe TC recalculée (T4). Grafana : **aucun panneau `geomap`** dans les huit tableaux de bord — rien à changer. **Décision : faire** (vizpop, avec le runtime). |
| **Article** (`docs/paper/`) | Le périmètre déclaré devient exact ; tableau de conformité à remesurer sur la v4 ; limite « transport scolaire » à déclarer | À réécrire après le sceau v4 : § 2.2 (périmètre « 453 communes, six départements, polygone communal »), annexe F (conformité v4, ligne scolaires, mobilité 2,93 / 3,63 contre 3,53 / 3,95), et une note de méthode sur le vivier de donneurs (§ 1.2 bis) — le manuscrit décrit un appariement national que le service ne faisait pas. **Décision : faire** après le sceau. |

### Questions ouvertes (à trancher avant la suite)
1. **Édition BD TOPO** : l'IGN ne sert plus la 2024-09-15 ; prendre la 2025-03-15 pour les cinq
   départements et retélécharger D031 dans la même édition (0,34 Go) — recommandation : oui,
   édition homogène notée dans le MANIFEST.
2. **Classe d'âge 15-17 à l'appariement** : les 15-17 ans partagent la classe 15-29 d'eqasim
   (`AGE_BOUNDARIES = [14, 29, 44, 59, 74]`) et ne sont qu'à 80,4 % d'activité d'études ; une
   borne à 17 les rapprocherait des 92 % des plus jeunes. Modification d'un paramètre amont
   (`synthesis/population/matched.py`), à décider — recommandation : oui, en même temps que la
   génération v4, pour ne changer l'appariement qu'une fois.
3. **Activité hors polygone au chargement** : une école ou un lieu de travail hors des 453
   communes ne devrait pas écarter l'agent (le domicile fait le périmètre) ; compter, alarmer au
   seuil, router quand même (le graphe du polygone ne couvre pas ce point → repli à vol d'oiseau).
   Recommandation : admettre, compter, et étendre le polygone du graphe d'une marge de 5 km si le
   compte dépasse 1 % des activités.
4. **Congestion hors ville** : le facteur TomTom « agglomération » (1,84 à 8 h) s'applique aux
   trajets ruraux de 3ᵉ couronne ; un troisième palier (hors agglomération = 1,0) demande une
   emprise d'agglomération (Tisséo ? 1ʳᵉ couronne ?). À trancher en partie 2.
5. **Immobiles du vivier** : 19,3 % après correction (enquête 10,6 %, v3 15,1 %) ; la sélection
   les ramène à la cible, mais le vivier national ENTD porte plus d'immobiles que l'EMC². Rien à
   faire pour le sceau ; à déclarer dans la synthèse de représentativité.

### Critères d'acceptation — partie 2 (à préciser après l'analyse)
1. Chaque ligne du tableau a une mesure consignée dans une trace horodatée, et une décision
   (faire / déclarer / reporter) inscrite dans ce ticket.
2. Un run complet d'une journée sur la v4 tourne de bout en bout : 1 000 agents chargés, zéro
   « Couldn't link », zéro agent hors monde GAMA, alarmes de périmètre silencieuses.
3. Le rapport de run compare les parts modales aux cibles 453 communes, avec le transport
   scolaire déclaré (ou livré).

## Ce que ce ticket ne fait pas
- Il ne remplace pas l'ENTD 2008 par l'EMC² 2023 comme enquête d'appariement (levier 3, autre
  ticket) : les chaînes d'activités restent celles de l'ENTD, filtrées sur les jours de classe.
- Il ne réchauffe pas les caches d'itinéraires (script à part, décision du 2026-09-03).
