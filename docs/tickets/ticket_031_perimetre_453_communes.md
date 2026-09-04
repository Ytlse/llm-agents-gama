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
- [x] § 1.0 données des cinq départements : **porte 1 levée le 2026-09-03 après-midi**, BD TOPO
  2025-03-15 (six départements, D031 compris) et BAN téléchargées et vérifiées (md5).
- [x] § 1.5 **sceau v4 livré** : `data/population/population_1000_AAMAS_v4/` (sha256
  `9f05c655c3ad2cf4…`), 12 marges conformes + 1 à publier (motorisation base ménage), immobiles
  10,6 %, scolaires 88,5 %, six départements, A2/A4/A9 conformes ; sauvegarde tar.gz, `config.yaml`
  repointé, synthèse HTML v3. Détail au § « Sceau v4 » ci-dessous. Une répétition Haute-Garonne
  avait précédé (13:20, non scellée).

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
production, c'est le contrat), à revoir en partie 2 (O3).

**O2 — paires « même nœud » de la v3** (3 443 paires de planification : 3 007 voiture, 436 vélo ;
`measure_osmnx_perimeter_graph.py`, trace `docs/traces/2026-09-03_13-20_mesures_graphe_perimetre/`).
Sur le **disque de 30 km** : 6,3 % des paires tombent sur un même nœud — **26,5 % en 3ᵉ couronne**
(Toulouse 2,1 %, 1ʳᵉ 3,3 %, 2ᵉ 3,4 %) : un trajet sur quatre de 3ᵉ couronne n'était pas un
itinéraire mais une vitesse de repli à 70 km/h. Routage effectif d'un échantillon de 866 paires
(code de production, congestion du lundi 8 janvier) : 13 `None` (1,5 %), **884 ms par route**
en médiane — machine en swap (la VM Docker réserve 23 Go), le notebook mesurait 221 ms par route
à 3 workers dans les mêmes conditions.
Sur le **polygone des 453 communes** : **3,0 %** de paires « même nœud » — **3,9 % en 3ᵉ couronne**
(Toulouse 2,1 %, 1ʳᵉ 3,3 %, 2ᵉ 3,4 %), soit le même niveau que les couronnes urbaines : ce résidu
est celui des trajets très courts dont les deux bouts partagent réellement leur nœud le plus
proche (rabattement médian 52 m), plus un effet de couverture. Distance de rabattement au graphe :
p95 **264 m contre 2 951 m** sur le disque. Routage du même échantillon : **6 `None` (0,7 %)
contre 13**, 699 ms par route en médiane contre 884 (le graphe plus grand route plus vite : moins
de plus courts chemins dégénérés). Le critère d'acceptation 3 (« < 1 % en 3ᵉ couronne ») n'est
donc pas tenu à la lettre — 3,9 % — mais la 3ᵉ couronne est ramenée au plancher des autres
couronnes, qui est la mesure des trajets réellement courts, pas d'un défaut de graphe
(question ouverte n° 6 : reformuler le critère en « ≤ le taux des couronnes urbaines », ou ne
compter que les paires « même nœud » distantes de plus de 500 m).

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
  (v3 : 2,58 / 2,88 ; enquête 3,53 / 3,95 — chiffres sous l'ancienne convention n − 1, corrigée le soir : voir § mobilité) — l'écart de mobilité reste à publier, il ne tient
  plus au vivier de donneurs mais aux chaînes ENTD 2008 après fusion des activités consécutives.
  Le recoupement du tableau § 2.1 du protocole garde ses 7 lignes en écart (Annexe F).
- **Audit de périmètre** (`make audit-perimetre`, trace
  `docs/traces/2026-09-03_13-21_audit_perimetre_v4_repetition_HG/`) : **A1, A2, A4, A9
  conformes** (0 domicile hors des 453 communes ; couronnes par liste de communes ; répartition
  spatiale dans la tolérance), A3, A5, A8 à publier comme sur la v3, A6 et A7 non mesurables
  (propriétés d'un run). Critères 1 et 2 de la partie 1 tenus **sur le cadre Haute-Garonne** ;
  le critère « six départements représentés » ne peut l'être qu'après la porte 1.

### Sceau v4 (2026-09-03, 18:16)

- **Vivier** : 11 329 personnes (eqasim 18:01, 3 min avec les caches BD TOPO/BAN ; 8 min à froid),
  couronnes 34,5 / 35,5 / 14,6 / 15,3 %, six départements, 35 % de la 3ᵉ couronne hors 31, A4 = 1
  (exclu), 14 sans domicile (exclus), immobiles 19,4 %, scolaires 92,8 % (15-17 : 91,6 %). Contrôle du
  vivier : 9 à corriger, 1 à publier, 3 conformes (trace `…_18-03_controle_vivier_10000_v4/`).
- **Sélection v4** : 1 000 personas en **513 ménages entiers**, aucun déficit, 393 échanges en
  3 passes, perte 74,0 → 5,0 pt ; **six départements représentés** (31 : 939, 32 : 9, 81 : 30,
  82 : 19, 09 : 2, 11 : 1), 141 communes, 53 des 154 habitants de 3ᵉ couronne hors Haute-Garonne
  (34 %) ; 0 activité hors du polygone (1 000 personas contrôlés).
- **Routage** sur le graphe du polygone avec la congestion par zone et le repli à la vitesse du
  mode : 3 291 paires, 3 274 routées, 17 `None` (0,5 %), 3 workers, **582 s (177 ms par route)** sans
  swap — Docker relancé pour le seul service eqasim, otp1-3 / worker / osmnx1 arrêtés ; 1 000
  plannings valides, 3 335 activités planifiées, 2 660 desservies en TC. Premier essai à 3 workers
  tombé sur une course du lien `experiments/current` entre workers (corrigée dans `settings.py`,
  re-pointage atomique).
- **Traits (étape 8)** : sept post-traitements ; `enrich_personal_bike` rend le **code 2** sur un
  seul critère — la pente de l'équipement par taille de ménage n'est pas monotone entre les tailles
  3 et 4 (63,4 % > 55,5 %, sur 69 et 55 foyers, IC ± 12-13 pt) alors que chaque taille et les
  douze autres cibles sont dans leur tolérance ; trait posé sur 1 000 / 1 000, audit de complétude
  **POPULATION COMPLÈTE**. Déclaré « à publier » dans le MANIFEST et la synthèse (question n° 7).
- **Contrôle** (trace `…_18-16_controle_toulouse_population_1000_AAMAS_v4/`) : **12 conformes,
  0 à corriger, 1 à publier** — motorisation en base ménage (1/taille, n_eff 752) : sans voiture
  22,8 % contre 19,2 % (+3,6 pt), la seule marge non allouée ; immobiles 10,6 % ; **scolaires
  131 / 148 = 88,5 %** (seuil 88) ; 3,33 déplacements par persona, 3,73 par mobile sous la convention cyclique corrigée le 2026-09-03 au soir (2,44 / 2,73 avec l'ancienne convention n − 1 ; enquête 3,53 /
  3,95). **Audit** (`…_18-16_audit_perimetre_v4/`) : A1, A2, A4, A9 conformes ; A3, A5, A8 à
  publier ; A6, A7 propriétés d'un run.
- **Sceau** : MANIFEST avec `perimetre` (définition, départements attendus / retenus, activités hors
  polygone contrôlées : 0) ; sauvegarde `population_1000_AAMAS_v4_2026-09-03.tar.gz` (sha256
  `41f9514231b5013d…`, sceau + vivier brut et pré-imputé + sélection) ; `config.yaml` →
  `population_1000_AAMAS_v4/population.json` ; synthèse
  `docs/paper/population/synthese_representativite_v3_population_v4_2026-09-03.html` (générateur
  `scripts/AAMAS/synthese_representativite.py`, `make synthese-representativite`).
- **Critère 3 mesuré sur la cohorte v4** (3 300 paires de planification : 2 932 voiture, 368
  vélo ; trace `docs/traces/2026-09-03_18-18_mesures_graphe_perimetre_v4/`). Sur le **disque de
  30 km** : 6,9 % de paires « même nœud », 24,9 % en 3ᵉ couronne ; paires **distantes de plus de
  500 m** rabattues sur le même nœud : 2,24 % au total, **15,51 % en 3ᵉ couronne** (0 ailleurs) —
  critère **non tenu**, comme attendu : un trajet de 3ᵉ couronne sur six n'était pas un
  itinéraire ; 787 routes échantillonnées, 9 `None`, 370 ms par route (médiane, un seul processus).
  Sur le **polygone des 453 communes** : 4,2 % de paires « même nœud » (Toulouse 2,2, 1ʳᵉ 4,2,
  2ᵉ 8,0, 3ᵉ 5,9 — de vrais trajets courts, rabattement médian ≈ 50 m) et **0,03 % de paires
  distantes de plus de 500 m** (3ᵉ couronne **0,0 %**, 2ᵉ 0,23 %, 0 ailleurs) — **critère 3 tenu**
  (≤ 0,5 % par couronne) ; 5 `None` (0,6 %), 423 ms par route. Les 3 300 paires de la cohorte ont
  toutes deux bouts sur le graphe : plus aucun trajet de 3ᵉ couronne n'est une vitesse de repli.
- ⚠ Le runtime filtre encore sur `TOULOUSE_OSM_ROUTES_30K_BBOX` : ce sceau ne se charge entier
  qu'après le portage de la partie 2 (chargement par commune du domicile).
  **Réglé le 2026-09-03 au soir** : `slope_verdict` juge la pente à partir de 100 foyers par taille et tolère une inversion contenue dans l'incertitude ; sur la cohorte v4 le critère est « non concluant » (code de sortie 0), sur le vivier la pente est croissante (32,8 / 49,1 / 55,0 / 60,9 %). Doc : `docs/arch/velo-equipement.md`.
- **Pages du 2026-09-03 au soir** : la synthèse de représentativité v3 est régénérée avec le verdict vélo
  (rapports `--rapport-json` de la cohorte et du vivier) et la légende corrigée du compte des déplacements ;
  la page `docs/paper/population/fabrication_population_v4_2026-09-03.html` explique la fabrication de
  bout en bout (`scripts/AAMAS/synthese_generation_population.py`). Trace :
  `docs/traces/2026-09-03_22-32_synthese_v3_population_v4_velo/`.

### Critères d'acceptation — partie 1
1. Vivier : 0 persona hors des 453 communes ; six départements représentés ; ≥ 88 % des 6-17 ans
   mobiles avec activité `education`. **Tenu** : A4 = 1 sur 11 329 (exclu par la sélection, 0 dans
   la cohorte), six départements, 92,8 % (cohorte : 88,5 %).
2. Sceau v4 : 1 000 personas en ménages entiers, 13 marges + classe_age conformes, immobiles
   ≈ 10,6 %, `household.commune_id` renseigné pour tous. **Tenu à une marge près** : 12 conformes,
   la motorisation en base ménage à publier (+3,6 pt sur « sans voiture », marge non allouée) ;
   immobiles 10,6 % ; `commune_id` 1 000 / 1 000 ; 513 ménages entiers.
3. Plannings recalés sur un routage effectif : paires distantes de plus de 500 m à vol d'oiseau
   rabattues sur le même nœud ≈ 0 (≤ 0,5 %) par couronne — reformulé le 2026-09-03 (les paires
   « même nœud » plus courtes sont de vrais trajets courts, servis par le repli à la vitesse du mode).
   **Tenu sur la cohorte v4** : 0,03 % au total, 0,0 % en 3ᵉ couronne (contre 15,5 % sur le disque
   de 30 km).
4. Documentation et changelog à jour ; synthèse de représentativité v3 (HTML) produite et
   inventoriée dans `docs/paper/README.md`. **Tenu.**

---

## Partie 2 — Impacts sur le reste de la chaîne (inventaire, analyse à approfondir)

Chaque ligne est un impact identifié le 3 septembre 2026 ; la colonne « à mesurer » dit ce qui
manque pour en faire une spécification. Actions numérotées du rapport entre parenthèses.

### État au 3 septembre 2026 (soir) — la partie 2 est portée

Trace unique de toutes les mesures ci-dessous :
`docs/traces/2026-09-03_22-46_ticket031_partie2_portage_chaine/` (README + cinq fichiers de
mesure + journal de construction OTP). **T2, T6 et G2, faits le 2026-09-04 une fois la porte de
téléchargement levée** : `docs/traces/2026-09-04_01-30_ticket031_gtfs_lio/`.

| Maillon | État | Chiffre qui le prouve |
|---|---|---|
| Chargement runtime | **fait** | 1 000 / 1 000 agents v4, **0 écarté**, 0 activité hors polygone sur 1 884 (l'ancien rectangle en écartait 77) |
| OSMnx runtime | **fait** | clé de graphe configurée (`444ca7e6a515`) ; arêtes vélo en vitesse de repli **32,0 % → 0,0 %** ; `routing_version` r2 |
| vizpop | **fait** | quatre couronnes tracées à la place du rectangle, enveloppe TC de T4 |
| OTP T1 / T4 / T5 | **fait** | extrait du polygone (76 Mo), graphe reconstruit en 46 s / 2,0 Go, **0 « Couldn't link »** sur 2 580 points |
| OTP T2 / T6 | **fait le 2026-09-04, mise en service à faire** | GTFS liO téléchargé (23 833 236 o, sha256 `d196b763…`, ODbL, 2026-08-01 → 2027-08-31), feeds annuels `lio_2026`/`lio_2027` construits (code 0), graphe reconstruit et mesuré : **670 → 339 points sans itinéraire TC** (3ᵉ couronne 369 → 163, 2ᵉ 160 → 35), `noStopsInRange` 364 → 91. T6 : trois courses routières SNCF dans le périmètre, toutes le 2026-09-03 → **ne pas charger**. Le `graph.obj` attend sous `data/gtfs/prochain_graphe_2026-09-04/` : un run occupait `otp1/2/3` |
| GAMA G1 | **fait** | monde = `perimetre_453.shp`, 86 × 93 km ; avertissement de couverture TC (21 %) ; compteur d'agents hors monde |
| GAMA G4 | **tranché autrement** | les coordonnées de `roads.shp` ne sont valides dans aucune zone UTM : le `.prj` ne se corrige pas, il se documente |
| GAMA G2 | **fait le 2026-09-04** | `routes.shp` 395 → **730 tracés**, `stops.shp` 3 822 → **5 375 arrêts** (Tisséo + TER + liO, restreints au périmètre) ; mailles de 5 km portant un arrêt 52 / 217 → **156 / 217** ; zones fines de l'enquête 394 / 785 → **571 / 785** |
| GAMA G3 | **reporté** | le rendu n'est pas mesurable en headless |
| Caches et jeux gelés | **déclaré** | caches d'itinéraires par population (v4 vierge) ; `routing_version` r2 ; aucun jeu gelé touché |
| Run headless (critère 2) | **partiel, mesuré** | 1 000 agents chargés, 0 « Couldn't link », **0 / 1 000 hors monde GAMA** (201 sous l'ancien monde), 0 `[ALARME]` — journée simulée non terminée |
| Documentation | **fait** | `agents-lifecycle.md`, `cache-memory.md`, `routing.md`, `setup/population.md`, `setup/data-pipeline.md`, changelog |
| Article (`docs/paper/`) | **à faire, hors de cette session** | § 2.2, annexe F, et la largeur « 106 × 93 km » à corriger en 86 × 93 |

| Maillon | Impact identifié | Mesuré ou constaté le 2026-09-03 (code vérifié) → décision proposée |
|---|---|---|
| **Chargement runtime** (`handle/application.py`) | Le filtre rectangulaire `TOULOUSE_OSM_ROUTES_30K_BBOX` doit devenir un filtre par **commune du domicile** (liste des 453) et un `contains` du polygone pour les activités ; un fichier scellé se charge entier ou se refuse | **Deux filtres successifs.** (1) `_prepare_population` (lignes 238-268) écarte tout agent dont le domicile **ou une activité** sort du rectangle 30 km, puis refuse un sceau dont l'effectif a bougé — 79 agents v3 écartés (67 par le domicile), sceau refusé ; la v4 en écartera davantage (3ᵉ couronne complète). (2) `world/population.py` → `eqasim_loader.perimeter_verdict` : trait `residence_zone` dans une couronne → admis ; `hors périmètre` → rejeté ; trait absent → bbox `world_bbox` = arrêts GTFS ± 0,05° (`factory.py:151`) — ce second filtre est déjà **par périmètre** et n'a rien à changer. `WorldGrid(world_bbox)` (`world_data.py:38`) borne l'index spatial sur les arrêts GTFS : à élargir au polygone. **Décision : faire** — remplacer le rectangle de (1) par `household.commune_id ∈ 453` (renseigné pour tous depuis ce jour) et, pour les activités, un `contains` du polygone (`CommunalZones`) ; une activité hors polygone (école, travail hors périmètre) n'écarte **pas** l'agent mais se compte et s'alarme (question ouverte n° 3) ; mesurer « aucun agent v4 écarté » au premier chargement. **LIVRÉ le 2026-09-03 au soir** — `llm-agents/inputs/population/perimeter.py` : `home_verdict` en cascade (commune → trait `residence_zone` → géométrie du polygone, avec `[ALARME]` permanente quand la géométrie a dû trancher), `filter_population` (journal d'une ligne, dix rejets détaillés, `[ALARME]` sur front montant au-dessus de 1 % d'activités hors polygone), `sealed_population_complete` (un sceau se charge entier ou rien n'est chargé), `world_extent` (enveloppe du polygone ∪ arrêts GTFS pour `WorldGrid`). **Mesuré sur le sceau v4 : 1 000 / 1 000 retenus, 1 000 admis par commune, 0 écarté, 0 activité hors polygone sur 1 884 localisées, filtre en 9 ms** — et l'ancien rectangle en écartait **77 agents** (60 domiciles, dont 55 de 3ᵉ couronne ; 105 activités). Confirmé en conteneur au run headless du 22:55. 14 tests neufs (`llm-agents/tests/test_perimetre_chargement.py`). Trace : `docs/traces/2026-09-03_22-46_ticket031_partie2_portage_chaine/`. |
| **OSMnx runtime** (`osmnx_server.py`, `trip_helper/osmnx_direct.py`, `geography.py`) | Graphes sur le polygone (même construction qu'en 1.4) ; `TOULOUSE_CENTER_DIST_M` disparaît au profit d'une emprise ; frontière `_in_city` et facteur de congestion à revérifier hors du disque (O3) ; vitesses de repli moins sollicitées | **O1/O4 mesurés** (§ 1.4) : pickle 223 Mo contre 245, worker 1 828 Mo contre 1 754 (+4 %) hors pression mémoire (0,85-1,6 Go lus sous swap : `ru_maxrss` n'est pas fiable quand la machine swappe), chargement 7 s ; `MAX_WORKERS` se règle sur la RAM libre — 6 sur une machine dédiée, 3 quand la VM Docker en prend 23 Go. **O2 mesuré** (§ 1.4, trace `docs/traces/2026-09-03_13-20_mesures_graphe_perimetre/`) : paires « même nœud » en 3ᵉ couronne **26,5 % → 3,9 %** (plancher urbain 2,1-3,4 %), rabattement p95 2 951 m → 264 m, routes `None` 1,5 % → 0,7 %, 884 → 699 ms par route. **O3 vérifié dans le code** : `_in_city` = commune de Toulouse (géocodage, inchangé et copié pour la nouvelle clé) ; **hors de la commune, le facteur n'est pas 1 mais celui de l'agglomération TomTom** (`metro_raw`) — lundi 8 h : 2,04 en ville, **1,84 hors ville**, appliqué tel quel à un trajet rural de 3ᵉ couronne, ce que le rapport n'attendait pas. Vitesses de repli : le mode vélo n'a pas de vitesse pour `track`, `service`, `footway`, `pedestrian`, `trunk` → 32 % des arêtes du polygone en repli (14 km/h). Portage : `_GraphStore.get(city, dist)` et les deux `cache_key = md5(f"{city}_{dist}")` d'`osmnx_server.py` (l. 51-54, 131-134) deviennent une clé de graphe configurée (`PERIMETER_CACHE_KEY`), `TOULOUSE_CENTER_DIST_M` ne garde qu'un rôle d'audit. **Cache SQLite** (`osmnx_persistent_cache.make_key`) : clé = `routing_version` (`r1`) + mode + coordonnées (+ jour/heure en voiture), **indépendante du graphe** → une entrée calculée sur le disque de 30 km (dont les replis à 70 km/h) serait resservie sur le polygone ; le dossier de cache est par nom de population, donc une v4 part de zéro, mais **bumper `routing_version` à `r2`** au changement de graphe est le geste honnête. **Décision : faire** (partie 2), avec une passe sur `speeds.bike`. **Facteur hors ville : rien maintenant** (décision du 2026-09-03) ; trois pistes pour la partie 2 : (a) profil « metro » appliqué à la seule part du trajet dans l'agglomération — arêtes dans le polygone Toulouse + 1ʳᵉ + 2ᵉ couronne, facteur 1,0 ailleurs (une passe sur la géométrie de la route) ; (b) TomTom Traffic Stats (payant) pour des vitesses par tronçon sur tout le périmètre ; (c) comptages horaires ouverts — Cerema trafic-routier, les ≈ 100 stations permanentes du Département, Toulouse Métropole — pour calibrer un facteur de pointe sur les radiales. **LIVRÉ le 2026-09-03 au soir** : `graph_key()` / `graph_label()` (`trip_helper/osmnx_direct.py`) rendent la clé du graphe **configurable** (`settings.gtfs.osmnx_graph_key`, défaut `PERIMETER_CACHE_KEY` = `444ca7e6a515`) ; `_GraphStore._build_sync(key)` et les deux `md5(f"{city}_{dist}")` d'`osmnx_server.py` sont remplacés ; un pickle absent lève `GraphMissingError` avec `[ALARME]` **au lieu de télécharger un disque de 30 km sous le même nom** (seul `PRODUCTION_CACHE_KEY_30KM` garde sa recette Overpass, pour l'audit) ; `osmnx_server` refuse de démarrer si le graphe manque ; `TOULOUSE_CENTER_DIST_M` et `TOULOUSE_OSM_ROUTES_30K_BBOX` sont commentés « AUDIT ONLY » dans `geography.py`. **Passe O3 sur `speeds.bike` faite** : chaque type manquant a sa vitesse avec sa source citée (profil `bike` de GraphHopper ; art. R412-7, R431-9 et R110-2 du code de la route pour les sections poussées et la zone de rencontre) — arêtes en vitesse de repli **vélo 32,0 % → 0,0 %** (2 arêtes sur 360 801, `highway="R"` aberrant du millésime 2022 ; 24 627 arêtes modifiées), marche 5,1 % → 0,3 %, voiture 1,2 % → 0,3 % ; reposées sur le pickle en 26 s / 2,6 Go de pointe par `build_osmnx_perimeter_graph.py --respeed`. **`routing_version` r1 → r2** (`config/terminal_time.yaml`). Le conteneur `osmnx1` voit bien `data/cache/osmnx` (`/app/osmnx_cache`) ; sa `mem_limit` passe de 4 à 8 Go — à 4 Go le warmup des trois modes tombait en OOM 137 (**modification de `docker-compose.yml` laissée non commitée**, cf. rapport). Facteur de congestion hors ville : **rien**, comme décidé. |
| **OTP** (`otp-toulouse/`, `data/gtfs_year/`) | Extrait OSM sur le polygone (T1) ; GTFS liO en feed annuel (T2, 22,7 Mo, ODbL) ; cars TER éventuels (T6) ; `TOULOUSE_TRANSIT_SERVICE_WKT` recalculée (T4) ; calendrier liO (T5) ; trois instances plus lourdes | `otp-toulouse/toulouse/Toulouse.osm.pbf` (64 Mo, DVC, md5 `06099055…`) n'a **aucune recette** dans le dépôt (le `Makefile` ne fait que `--build` et `--load`) : son emprise ne se rejoue pas. L'extrait intermédiaire du § 1.4, `data/cache/osmnx/perimetre_453/perimetre_453.osm.pbf` (76 Mo, polygone exact, OSM 2022, toutes clés), **est** l'extrait T1 : à copier/renommer et à consigner dans un `Toulouse.osm.pbf.dvc` daté. `build-config.json` : `transitServiceStart/End` 2026 ; liO non chargé. Temps de construction et RAM par instance : **non mesurés** (pas de reconstruction sans décision sur liO). **Décision : reporter** dans un ticket OTP (T1 + T2 + T4 + T5 + T6 ensemble : une seule reconstruction des trois instances), après accord pour le téléchargement du GTFS liO (22,7 Mo). **RÉVISÉ le 2026-09-03 au soir : T1, T4 et T5 sont FAITS** (ils ne demandent aucun téléchargement) ; T2 et T6 restent reportés faute d'accord. **T1** : `data/gtfs/Toulouse.osm.pbf` est l'extrait du polygone exact (76 475 294 o, md5 `62d45fe5…`, OSM 2022-01-01), copié de `data/cache/osmnx/perimetre_453/` ; l'ancien extrait (rectangle, 88 204 065 o, md5 `cc9520bf…`) et son `graph.obj` sont **conservés** (`data/gtfs/archives/2026-09-03_pre_perimetre_453/`, `otp-toulouse/toulouse/Toulouse_bbox30km_2026-05-06.osm.pbf`), rien n'est supprimé ; provenance dans le `.dvc` daté et `README_Toulouse.osm.pbf.md` (écrits à la main, `dvc` n'est pas installé). **Graphe reconstruit et mesuré** : 46 s, **2,0 Go de RAM de pointe**, `graph.obj` de 69,7 Mo, 257 664 sommets / 657 756 arêtes, 4 056 arrêts, 588 patterns ; 1,2 à 1,4 Go par instance chargée. **T3 mesuré** (`scripts/data/gtfs/otp_link_check.py`, lundi 8 h, 2 580 domiciles et lieux d'activité de la v4) : **0 `LOCATION_NOT_FOUND` — zéro « Couldn't link »** ; 670 points sans itinéraire TC, dont 364 `noStopsInRange` et 171 `noTransitConnection` : des lieux sans desserte, pas un défaut d'emprise — c'est le manque de liO, à publier comme limite. **T4** : `TOULOUSE_TRANSIT_SERVICE_WKT` recalculée sur 5 661 arrêts Tisséo + 68 arrêts TER du polygone (23 sommets, 2 100 km²) ; l'ancienne est gardée sous `TOULOUSE_TRANSIT_SERVICE_WKT_TISSEO_ONLY_2026_05` ; elle ne sert plus de garde-fou de routage. **T5** : `data/gtfs/build-config.json` fixe `transitServiceStart/End` = `[2026-01-01, 2027-12-31]` (sans lui, OTP prenait `[build − 1 an, + 3 ans]`). **RÉVISÉ le 2026-09-04 : T2 et T6 sont FAITS, la mise en service reste à faire.** **T2** — GTFS liO téléchargé depuis `transport.data.gouv.fr/resources/81026/download` (ODbL, **23 833 236 o**, sha256 `d196b763ffc6e9183d5e38e01c1b902ac4824163cf5023ab128002de257ab62f`, md5 `0cb81c74…`, `unzip -t` sans erreur, 19 fichiers), archivé sous `data/gtfs/archives/2026-09-04_lio_source/exports_bruts/lio_2026-09-04.zip`. Vérifié **dans les fichiers** et non dans la description : 309 lignes toutes `route_type=3`, 7 506 arrêts, 7 715 courses, 126 701 horaires, validité `calendar.txt` **2026-08-01 → 2027-08-31** (`feed_info.txt` annonce 2018-12-03 → 2030-01-31 : trompeur), TAD présent (608 horaires `pickup_type=2`, 2 291 `pickup_type=3`). **Trois écarts avec le § 6 du rapport** : quatorze agences et non treize (Hérault Transport accompagne les treize réseaux liO), le `feed_info` trompeur, et surtout **le feed ne sert rien le 16 mars 2026** — d'où le passage obligé par `gtfs_year`. Dans le périmètre : **1 485 arrêts, 56 lignes** (42 du réseau `.liO 31`), 1 176 courses. **Feed annuel** : `lio_2026` (153 journées réelles, 212 extrapolées, 6 858 courses) et `lio_2027` (243 / 122), **code de sortie 0**, tous invariants bloquants tenus ; le 16 mars 2026 y est la copie du **lundi 15 mars 2027** (signature exacte, écart de saison 1 jour, 3 494 courses). Trois corrections du pipeline ont été nécessaires, chacune testée : lecture du `calendar.txt` hebdomadaire (457 services, 3 408 ajouts, 2 925 retraits) ; **préservation des courses de contenu identique le même jour** (45 le 14/09/2026 — les fusionner amputait l'offre et faisait échouer V2) via un rang de « place » qui laisse fusionner les jours disjoints ; V7 reformulé en « une journée copiée sert exactement l'offre de son donneur » (l'ancien test d'enveloppe dénonçait les donneurs de l'autre moitié de l'année scolaire) et V6 distinguant un tracé chimère **fabriqué** d'un défaut **recopié** de la source. **Non-régression** : les quatre feeds Tisséo/TER rejoués sont identiques à l'octet près, `feed_info.txt` excepté. **Reconstruction mesurée** (répertoire de build isolé, un run occupait `otp1/2/3`) : référence 48 s / 2,69 Go / 69,7 Mo / 4 056 arrêts / 588 patterns ; **avec liO 54 s / 2,24 Go / 84,9 Mo / 11 562 arrêts / 3 228 patterns** ; avec liO + TER annuel 55 s / 2,62 Go. RAM d'instance 1,0 Go au chargement, 2,2 à 2,6 Go après 2 580 requêtes (`mem_limit: 6g` suffit). **T3 rejoué dans les mêmes conditions** (lundi 16 mars 2026, 8 h, 2 580 points, une instance) : **670 → 419 points sans itinéraire TC avec liO, 339 en ajoutant le TER annuel** ; `noStopsInRange` 364 → 91 ; par couronne, 3ᵉ **369 → 163**, 2ᵉ **160 → 35**, Toulouse inchangé (132, tous `walkingBetterThanTransit`) ; **0 échec de rattachement** dans les trois états. **T6** — le feed TER du dépôt n'a aucune ligne routière (17 lignes, toutes `route_type=2`) ; le GTFS SNCF national en a 114, mais **trois courses seulement touchent le périmètre, toutes le 2026-09-03** (substitution de travaux Toulouse ↔ Boussens / Tarbes). **Décision : ne pas le charger**, et aucun doublon avec liO. **Mais T6 a trouvé un trou** : l'export TER en service ne couvre que 2026-04-29 → 2026-10-26 et **ne sert aucun train le 16 mars 2026** ; `data/gtfs_year/ter_2026` y sert 80 services. Le graphe livré le porte. Trace : `docs/traces/2026-09-04_01-30_ticket031_gtfs_lio/`. |
| **GAMA** (`Settings.gaml`, `includes/`) | Monde = polygone du périmètre au lieu de l'enveloppe Tisséo (G1) ; `routes.shp`/`stops.shp` avec liO et TER (G2) ; performance sur 106 × 93 km (G3) ; projection `roads.prj` UTM 48N à contrôler (G4) ; avertissement au chargement si le shapefile de routes ne couvre pas le monde | Vérifié : `Settings.gaml:61` `geometry shape <- envelope(routes0_shape_file)` (lignes Tisséo, WGS84 — `routes.prj` GCS_WGS_1984) ; `roads.prj` déclare bien **UTM zone 48N** (G4 confirmé : Toulouse est en 31N ; la voirie GAMA n'étant pas exploitée, l'effet est nul aujourd'hui mais le fichier ment). Pas de simulation lancée (hors périmètre de cette partie) : G1 et G3 restent à mesurer. **Décision : reporter** (ticket GAMA : monde = `couronne_perimetre.geojson` dissous, avertissement de couverture, G3). **RÉVISÉ le 2026-09-03 au soir : G1 est FAIT, G4 est TRANCHÉ AUTREMENT, G2 et G3 restent reportés.** **G1** : `scripts/data/gama/export_perimetre_shapefile.py` écrit `includes/perimetre_453.shp` (polygone dissous des quatre couronnes, EPSG:4326 comme `routes.shp`) et `Settings.gaml` en fait `shape` — chargé en **premier**, c'est lui qui fixe la projection interne de GAMA. Enveloppe **86 × 93 km** (mesuré en Lambert-93 : 85,8 × 92,9 km, 5 428 km² de communes dans 7 971 km² d'enveloppe ; GAMA annonce 87 × 94 km dans sa projection). ⚠ **Le rapport de périmètre annonce 106 × 93 km** (§§ 7 et 8) : la largeur y est surestimée de 23 %, un degré de longitude compté à 111 km sans le cosinus de la latitude (80,8 km à 43,5°) — à corriger dans le rapport. Avertissement de couverture livré : au chargement GAMA écrit `[PERIMETRE] … les lignes TC (routes.shp) n'en couvrent que 21 %`, et `LLMAgent.gaml` compte les habitants hors du monde à la création (`[ALARME]` si > 0). **G4 : le `.prj` n'est pas le problème et ne se « corrige » pas.** Vérifié : les coordonnées de `roads.shp` et `nodes.shp` valent x ∈ [−4 143 135, −3 893 452], y ∈ [12 133 512, 12 429 715] — invalides dans **toute** zone UTM (un easting UTM vit dans [0, 1 000 000]). Ce sont les coordonnées internes de GAMA sauvegardées telles quelles par `OSMLoadDriving.gaml` avec le `.prj` par défaut de GAMA ; réécrire le `.prj` en 31N remplacerait un mensonge par un autre. Ces deux couches ne sont lues par aucun modèle (`City.gaml` ne charge que `perimetre_453.shp`, `routes.shp`, `stops.shp`, `trip_info.json`) : **laissées en place, documentées** dans `docs/setup/data-pipeline.md`, à régénérer avec une projection explicite si la voirie GAMA doit servir un jour (question ouverte n° 8). **RÉVISÉ le 2026-09-04 : G2 est FAIT.** `scripts/data/gama/export_gtfs_layers.py` (nouveau, sans dépendance à `settings.py` — l'importer depuis l'hôte détourne `experiments/current`, question ouverte n° 12) produit `routes.shp` et `stops.shp` à partir des **trois** réseaux : **730 tracés** (395 avant) et **5 375 arrêts** (3 822 avant), anciennes couches conservées sous `includes/archives_2026-09-04_02-10/`. Trois choix : couches **restreintes au périmètre** (liO couvre l'Occitanie, 2 632 tracés déborderaient dix fois le monde) mais **tracés jamais découpés** ; tracés du TER reconstruits depuis la suite de ses arrêts (il n'a pas de `shapes.txt`), marqués `trace=arrets` et absents de tout calcul de temps ; `shape_id`/`stop_id` **jamais préfixés** car ils joignent les itinéraires d'OTP — zéro collision mesurée. **Couverture** : l'enveloppe des lignes passe de **21 % à 100 %** du monde (la mesure python reproduit exactement les 21 % qu'annonce `Settings.gaml`), **156 des 217 mailles de 5 km** du périmètre portent un arrêt (52 avant) et **571 des 785 zones fines** de l'enquête (394 avant). ⚠ **L'avertissement `[PERIMETRE]` devient vide de sens** : le test d'enveloppe est vrai dès qu'un réseau régional entre dans la couche, et une enveloppe qui couvre le monde n'y met pas un arrêt — question ouverte n° 15. |
| **Ticket 030** (car scolaire) | Se branche ici : option `school_bus` pour les mineurs hors Tisséo ; sans elle, la 3ᵉ couronne simulée n'a pas de TC pour ses écoliers | Prérequis du ticket 030 (≥ 88 % des 6-17 ans mobiles avec activité `education`) **atteint sur le vivier de répétition : 89,0 %**. Le reste est inchangé (lots A à D). |
| **Résultats et métriques** | Temps terminal déjà par couronne communale (tt4) ; cibles modales inchangées (453) ; oracle LightGBM inchangé ; **les runs v3 et v4 ne sont pas comparables** | Ce qui repose sur la v3 : `docs/paper/MANUSCRIT_DETAILLE_2026.md`, `PROTOCOLE_SCIENTIFIQUE.md`, la synthèse `synthese_representativite_v2_population_v3_2026-09-03.html`, le ticket 029 et la page de contrôle ; runs archivés avec `population_file` : 4 sur le sceau v2, 1 sur la v3, 5 sans sceau. **Constat aggravant** : les chaînes d'activités de la v3 (et des runs antérieurs) viennent de **308 donneurs** résidents du 31 (§ 1.2 bis) — la comparaison v3/v4 porte aussi sur l'appariement, pas seulement sur le périmètre. **Décision : déclarer** dans le manuscrit (§ 2.2, annexe F) que la v3 est un jeu de mise au point, et **rejouer** les mesures publiées sur la v4. |
| **Caches et jeux gelés** | Cache OSMnx SQLite (réutilisable ?), cache OTP, cache sémantique LLM ; jeux gelés de `prompt_calibration` et campagne génétique construits sur une population antérieure | Vérifié : les jeux gelés `v9` à `v10c` épinglent `experiments/archive/2026-08-24_17_34/population_1000.json` (sha256 `4cd38bdc…`), `v5` à `v8` et `ctxL*` épinglent `2026-08-19_14_36/population_1000.json` — **aucun ne dépend de la v3 ni de la v4** : ils restent valides pour ce qu'ils mesurent (calibration du prompt sur une population donnée) et se **déclarent** tels quels ; un jeu gelé sur la v4 (v11) est un autre ticket. Cache OSMnx : clé indépendante du graphe (voir OSMnx) mais dossier par population → v4 vierge ; bump `routing_version`. Cache OTP : dossier par population (`otp_persistent_cache_dir/<population>`) → vierge. Cache sémantique LLM : clé sur le prompt (traits + options + météo) → nouveaux personas, nouvelles clés ; rien à purger, rien à réutiliser. **Décision : déclarer** (jeux gelés), **régénérer** de fait (caches par population). **LIVRÉ le 2026-09-03 au soir** : `docs/arch/cache-memory.md` déclare que les caches d'itinéraires (SQLite OSMnx et OTP) sont **par population** — donc vierges pour la v4, rien à purger — que le pickle des graphes est indexé sur la **clé de graphe** (`444ca7e6a515` = polygone) et non plus sur « zone + mode », et que **`routing_version` passe à `r2`** parce que la clé SQLite ne porte pas le graphe. Le tableau récapitulatif des caches est corrigé en conséquence. Aucun jeu gelé touché. |
| **Visualisation** (`vizpop.py`, Grafana) | `vizpop` utilise la bbox 30 km ; emprises des cartes Grafana à vérifier | `llm-agents/vizpop.py:17,91` trace `TOULOUSE_OSM_ROUTES_30K_BBOX` (rectangle gris) et `TOULOUSE_TRANSIT_SERVICE_WKT` : à remplacer par le polygone des couronnes (`couronne_perimetre.geojson`) et l'enveloppe TC recalculée (T4). Grafana : **aucun panneau `geomap`** dans les huit tableaux de bord — rien à changer. **Décision : faire** (vizpop, avec le runtime). **LIVRÉ le 2026-09-03 au soir** : le rectangle gris est remplacé par les **quatre couronnes** de `couronne_perimetre.geojson` (une couleur par couronne, infobulle « Couronne EMC² »), le polygone jaune par l'enveloppe TC recalculée de T4 (Tisséo + TER), et le titre de la page passe de « Haute-Garonne » à « périmètre EMC² (453 communes) ». Le géojson se cherche dans le dépôt ou dans le montage `/opt/llm_module` du controller ; s'il manque, le fond le dit sur `stderr` au lieu de tracer un faux périmètre. |
| **Article** (`docs/paper/`) | Le périmètre déclaré devient exact ; tableau de conformité à remesurer sur la v4 ; limite « transport scolaire » à déclarer | À réécrire après le sceau v4 : § 2.2 (périmètre « 453 communes, six départements, polygone communal »), annexe F (conformité v4, ligne scolaires, mobilité 2,93 / 3,63 contre 3,53 / 3,95), et une note de méthode sur le vivier de donneurs (§ 1.2 bis) — le manuscrit décrit un appariement national que le service ne faisait pas. **Décision : faire** après le sceau. |

### Décisions de l'auteur du dépôt (2026-09-03, après-midi) — les six questions sont tranchées
1. BD TOPO **2025-03-15** pour les six départements, D031 compris (édition homogène) ; BAN des
   cinq départements : **téléchargées** (journal ci-dessous), l'ancienne D031 2024-09-15 rangée
   hors du chemin d'eqasim. Le service et le notebook servent les six départements par défaut.
2. **Borne d'âge 17** dans l'appariement : livrée (`matching_age_boundaries` configurable dans le
   fork, `[14, 17, 29, 44, 59, 74, 1000]` dans `config_toulouse.yml`) ; effet mesuré sur la v4.
3. **Activité hors du polygone : supprimée** de la chaîne à l'étape 2, comptée, alarmée si > 0,
   déclarée (page de contrôle, MANIFEST) ; garde-fou et tests livrés ; 0 mesuré.
4. **Congestion hors ville : rien maintenant.** Trois pistes notées en partie 2.
5. **Immobiles 19,3 % du vivier : acceptés**, déclarés dans la page de contrôle.
6. **Critère 3 remplacé** par « paires distantes de plus de 500 m à vol d'oiseau rabattues sur le
   même nœud ≤ 0,5 % », mesuré par le script ; et le repli « même nœud » de `_route_sync` rend
   désormais une durée à la vitesse du mode (vol d'oiseau × 1,3, `_FALLBACKS`, minimum 1 s).

**Journal des téléchargements (2026-09-03, 14:08 → 14:13, trace `docs/traces/2026-09-03_14-08_telechargements_porte1/`)** :
D031 339 861 334 o (md5 `4975d547…` vérifié), D032 194 382 642 o (`e88b9a62…`), D081 225 133 383 o
(`5bf903af…`), D082 158 893 048 o (`76412a13…`), D009 147 862 815 o (`4e33074d…`), D011
230 399 808 o (`0ba65809…`) — six empreintes conformes aux `.md5` de l'IGN ; BAN 32/81/82/09/11 :
4,3 / 8,0 / 5,3 / 3,9 / 8,4 Mo, archives gzip valides. Total 1,30 Go de BD TOPO, 30 Mo de BAN.
L'ancienne livraison D031 2024-09-15 est rangée dans `eqasim-toulouse/data/bdtopo_archive_2024-09-15/`.

**Première génération sur les six départements (14:23 → 14:31, 8 min) — anomalie et correction.**
Le vivier livré comptait **17 986 personnes pour 10 000 demandées, 42,5 % en 3ᵉ couronne**
(7 650, dont 6 905 des cinq départements extérieurs ; 1 682 personas pour les dix villages audois
du cadre, 2 143 habitants) ; A4 = 5 domiciles hors des 453 communes (effet de bord des adresses
BD TOPO en limite de commune), 29 sans domicile, `household.commune_id` renseigné pour tous
(378 communes), immobiles 19,9 %, **6-17 ans mobiles avec activité d'études 91,3 %** — la borne 17
porte les 15-17 ans de **80,4 % à 91,0 %** (6-10 : 91,8, 11-14 : 91,0). Cause du gonflement,
vérifiée dans `data/census/filtered.py` : les personnes du recensement à commune « undefined »
(communes sans IRIS, le RP ne donne que le département) sont gardées quel que soit le cadre, puis
`home.zones` les répartit sur les communes sans IRIS **du cadre** — toute la population rurale du
département versée dans quelques villages. Mesuré (RP 2022) : la part de la population sans IRIS
du département qui vit dans le cadre vaut 86,7 % en Haute-Garonne mais 9,4 % (Gers), 9,0 % (Tarn),
20,1 % (Tarn-et-Garonne), 4,0 % (Ariège) et **1,0 % (Aude)**. Correction (fork) : le poids RP de
ces personnes est multiplié par cette part, par département, et journalisé (réglage explicite
`census_undefined_reweighting` : la première relance avait resservi le cache synpp du stage — un
changement de code ne le devalide pas, une valeur de configuration si) ; régénération à la suite. Ce biais existait déjà en Haute-Garonne seule (+13 % sur la 3ᵉ couronne rurale du 31 dans
tous les viviers depuis le ticket 026) ; il était invisible parce que le cadre couvrait presque
tout le département.

**Vivier v4 régénéré avec la pondération (18:01, 3 min avec les caches BD TOPO/BAN)** :
**11 329 personnes** ; couronnes Toulouse 34,5 %, 1ʳᵉ 35,5 %, 2ᵉ 14,6 %, **3ᵉ 15,3 %** (cibles
36,4 / 34,1 / 14,2 / 15,4) ; départements de résidence 31 : 10 626, 32 : 151, 81 : 243, 82 : 256,
09 : 46, 11 : 7 (361 communes) ; **600 des 1 730 habitants de 3ᵉ couronne (34,7 %) hors
Haute-Garonne**, comme les 35 % de l'enquête ; A4 = 1 domicile hors des 453 communes (adresse en
limite de commune, exclu par la sélection), 14 sans domicile ; immobiles 19,4 % ; **6-17 ans
mobiles avec activité d'études 92,8 %** (6-10 : 92,6, 11-14 : 93,9, 15-17 : **91,6** contre 80,4
avant la borne 17) ; 2,93 déplacements par personne, 3,63 par mobile.

**Zones de congestion posées sur le graphe du polygone** (17:40, 18 s, `--zones-only`) : marche
32 342 nœuds en ville, 102 858 en agglomération, 41 140 dehors ; vélo 23 202 / 89 453 / 39 178 ;
voiture 8 878 / 38 447 / 17 825.

### Questions ouvertes — telles que posées avant décision
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
7. **Équipement vélo, pente par taille de ménage** : `enrich_personal_bike` rend le code 2 sur la
   cohorte v4 parce que la taille 3 (63,4 %, 69 foyers) dépasse la taille 4 (55,5 %, 55 foyers),
   chaque taille étant dans sa tolérance (IC ± 12-13 pt) — bruit d'échantillonnage sur des
   sous-groupes de 50-70 foyers, pas un défaut du modèle. Déclaré « à publier » dans le MANIFEST ;
   recommandation : rendre ce contrôle non bloquant sous 100 foyers par taille (ou le mesurer sur le
   vivier, 5 652 ménages, où il est probant).
6. **Critère 3 de la partie 1** (« même nœud < 1 % en 3ᵉ couronne ») : mesuré 3,9 % sur le polygone,
   égal au plancher des couronnes urbaines (trajets réellement courts, rabattement médian 52 m).
   Reformuler en « ≤ le taux des autres couronnes » ou ne compter que les paires distantes de plus
   de 500 m — recommandation : la seconde, qui mesure le défaut de graphe et rien d'autre.

### Questions ouvertes de la partie 2 (2026-09-03, soir)

8. **`roads.prj` (G4) : la consigne « corrige et documente » ne s'applique pas telle quelle.** Le
   ticket demandait de corriger l'UTM 48N en 31N. Mesuré : les coordonnées de `roads.shp` et
   `nodes.shp` (x ∈ [−4 143 135, −3 893 452], y ∈ [12 133 512, 12 429 715]) ne sont valides dans
   **aucune** zone UTM — ce sont les coordonnées internes de GAMA, écrites par
   `OSMLoadDriving.gaml` avec le `.prj` par défaut. Réécrire le `.prj` en 31N donnerait un fichier
   tout aussi faux, et ces deux couches ne sont lues par aucun modèle. **Recommandation : ne rien
   réécrire** ; documenter (fait) et, si la voirie GAMA doit servir un jour, la régénérer en
   sauvegardant depuis une géométrie explicitement projetée. Décision de l'auteur attendue.
9. **`docker-compose.yml` : `mem_limit` du service osmnx, 4 → 8 Go.** À 4 Go, le warmup du
   graphe du polygone (trois modes chargés en parallèle, pointe de 2,8 à 3,0 Go) tombait en OOM
   137 : le service ne démarrait pas. La modification est sur le disque mais **non commitée** (ce
   fichier est hors du périmètre de commit de cette session). À valider et commiter par l'auteur,
   sinon le graphe du polygone ne se charge pas en conteneur.
10. **La largeur du périmètre est fausse dans le rapport de périmètre** (`docs/paper/population/
    RAPPORT_PERIMETRE_453_COMMUNES.html`, §§ 7 et 8) : « 106 × 93 km » au lieu de **86 × 93 km**
    (mesure Lambert-93 : 85,8 × 92,9 km). Un degré de longitude y est compté à 111 km sans le
    cosinus de la latitude. Corrigé dans `docs/setup/data-pipeline.md` et le README de l'extrait
    OTP ; `docs/paper/` n'est pas modifié par cette session.
11. **`otp_link_check` : 670 des 2 580 points de la v4 n'ont aucun itinéraire TC** (364
    `noStopsInRange`, 171 `noTransitConnection`, 124 `walkingBetterThanTransit`). Ce n'est pas un
    défaut d'emprise — 0 « Couldn't link » — mais l'absence du GTFS liO, qui porte 57 à 65 % du TC
    des 2ᵉ et 3ᵉ couronnes. **Recommandation : autoriser le téléchargement du GTFS liO (T2,
    22,7 Mo, ODbL)** avant de comparer les parts modales aux cibles (critère d'acceptation 3), ou
    déclarer la limite dans le manuscrit.
12. **Importer `settings` depuis un script détourne `experiments/current` pendant un run.**
    Constaté en direct le 2026-09-03 à 23:28 : un script d'analyse lancé sur l'hôte a importé
    `llm-agents/settings.py`, dont `get()` / `save_static_config` crée un dossier d'expérience
    horodaté et **re-pointe le lien**. Le run n'a pas bougé (les conteneurs résolvent leur chemin
    au démarrage) mais l'écriture des échanges LLM, qui résout le lien à chaque appel, a versé
    **1 037 échanges** dans le dossier parasite pendant une minute. Récupérés dans le run sous
    `llm_exchanges_detournes_23-28_incident_lien_current.jsonl`, incident consigné dans
    `experiments/archive/2026-09-03_22_54/INCIDENT_lien_current_2026-09-03_23-28.md`, dossier
    parasite renommé `…_23_28_PARASITE_import_settings`. Même famille que la course entre workers
    corrigée le matin. **Recommandation : rendre l'import de `settings` sans effet de bord** (le
    re-pointage devrait être un appel explicite, pas une conséquence de l'import) — sinon tout
    script d'analyse lancé pendant un run corrompt la trace de ce run.
13. **61 % des libellés de zone servis au prompt nomment la mauvaise commune.** Trouvé en
    dépouillant les avertissements du run. Le champ `identity.activities[].location.zone` du
    fichier de population — celui que lit le prompt de l'agent — ne nomme que **2 communes
    distinctes** dans tout le fichier : 3 383 des 3 441 libellés disent « sur la commune de
    Toulouse », dont **2 073 (61,3 %) portent sur une activité qui n'est pas dans Toulouse** (une
    activité à 70 km du Capitole est décrite comme « quartier de bourg rural sur la commune de
    Toulouse ») ; 54 disent « zone inconnue hors aire d'attraction urbaine ». **Le portage n'en est
    pas la cause** : la v3 porte le même défaut à 62,0 %, et le libellé est écrit à l'export, pas au
    runtime. Mais il devient visible maintenant que les trajets ruraux existent. Corriger change le
    prompt, donc les résultats et le cache de décisions : **décision de l'auteur**.
    Recommandation : renseigner la commune réelle depuis `household.commune_id` (déjà présent pour
    tous) au prochain scellement, et déclarer la limite d'ici là. Trace :
    `libelle_zone_activite.json`.

### Questions ouvertes de T2 / T6 / G2 (2026-09-04)

14. **Le graphe OTP avec liO est construit mais pas en service.** Un run de 1 000 agents
    (`experiments/archive/2026-09-04_01_09`, démarré à 01:09 par une autre session) occupait
    `otp1/2/3` pendant toute la session : reconstruire `data/gtfs/graph.obj` et redémarrer les
    conteneurs aurait changé l'offre TC **au milieu** de cette expérience. Le graphe recommandé
    (Tisséo + TER annuel + liO annuel, 84,9 Mo, 11 562 arrêts, 3 228 patterns) attend sous
    `data/gtfs/prochain_graphe_2026-09-04/` avec sa procédure de bascule et son retour arrière ;
    l'ancien est conservé (`data/gtfs/archives/2026-09-04_pre_lio/graph.obj`, sha256 `30dc951b…`).
    **Recommandation : basculer dès qu'aucun run ne tourne**, puis `docker compose up -d otp1 otp2
    otp3` et vérifier les trois healthchecks. Deux décisions accompagnent la bascule :
    (a) **mettre le TER annuel en service** — l'export en place ne sert aucun train le jour simulé ;
    (b) le feed Tisséo reste son export brut, la publication des feeds annuels Tisséo étant une
    décision à part (`docs/arch/gtfs-annee.md`, § Publication).
15. **L'avertissement de couverture TC de `Settings.gaml` devient vide de sens.** Il teste si
    l'enveloppe de `routes.shp` couvre le monde : vrai à 21 % avec Tisséo seul, **vrai à 100 % dès
    que liO entre dans la couche** — or une enveloppe qui couvre le monde n'y met pas un arrêt.
    C'est le motif « l'absence de mesure produit le score parfait ». Les deux chiffres qui disent
    quelque chose sont mesurés par `export_gtfs_layers.py` : **72 % des mailles de 5 km** du
    périmètre portent un arrêt et **73 % des zones fines** de l'enquête. **Recommandation :
    remplacer le test d'enveloppe par un maillage** (une passe sur `stops0_shape_file` au chargement,
    quelques lignes de GAML). Non fait ici : une erreur de syntaxe GAML ne se rattrape qu'en lançant
    GAMA, et le seul GAMA disponible portait le run en cours — **décision et validation de l'auteur**.
16. **Le mode `rail` n'est toujours pas demandé à OTP** (`llm-agents/trip_helper/otp.py` :
    `bus`, `metro`, `tram`, `cableway`). Le TER est dans le graphe, ses arrêts comptent dans
    l'enveloppe de desserte T4, et le feed annuel le fait rouler le jour simulé — mais aucun agent
    ne s'en verra jamais proposer un. liO, lui, est en `route_type=3` et passe par `bus` : rien à
    changer pour lui. Le TER porte 10 % des déplacements TC de la 3ᵉ couronne (EMC² 2023).
    **Recommandation : ajouter `rail` aux modes et la clé `"2"` à `gtfs_modality_name_map`** au même
    moment que la bascule du graphe — c'est un changement de résultats, donc **décision de l'auteur**.
17. **Le GTFS liO ne sert rien avant le 1ᵉʳ août 2026** ; la journée simulée du 16 mars 2026 est donc
    une **copie verbatim du lundi 15 mars 2027** (même signature, écart de saison 1 jour, 3 494
    courses, confiance moyenne). C'est le fonctionnement déclaré du feed annuel, et le donneur est
    le meilleur possible — mais c'est une limite à écrire dans le manuscrit au même titre que les
    journées extrapolées de Tisséo. À noter aussi : **liO publie 20 % de courses en moins au
    printemps 2027 qu'à l'automne 2026** (3 450 contre 4 300 les jours ouvrés) ; la journée servie
    est donc plutôt basse. Un export liO couvrant le premier semestre 2026 la remplacerait sans
    changer une ligne du pipeline.

### Critères d'acceptation — partie 2 (à préciser après l'analyse)
1. Chaque ligne du tableau a une mesure consignée dans une trace horodatée, et une décision
   (faire / déclarer / reporter) inscrite dans ce ticket.
   **Tenu** : trace unique `docs/traces/2026-09-03_22-46_ticket031_partie2_portage_chaine/`
   (README + neuf fichiers de mesure), et chaque ligne du tableau porte sa décision et son chiffre.
2. Un run complet d'une journée sur la v4 tourne de bout en bout : 1 000 agents chargés, zéro
   « Couldn't link », zéro agent hors monde GAMA, alarmes de périmètre silencieuses.
   **Les quatre éléments sont tenus ; le run est PARTIEL et c'est dit.** Run
   `experiments/archive/2026-09-03_22_54` (`make run OFFLINE=1`, lundi 16 mars 2026 simulé,
   `part_of_llm=1.0`) : (a) **1 000 / 1 000 agents chargés**, 0 écarté, sceau pris entier ;
   (b) **0 « Couldn't link »** — 0 `LOCATION_NOT_FOUND` sur les 2 580 domiciles et lieux d'activité,
   les 8 avertissements `No usable itinerary` du run portent `otp_patterns=[]` et
   `origin_in_bbox=True dest_in_bbox=True`, c'est une absence de desserte, pas un défaut de graphe ;
   (c) **0 / 1 000 agent hors du monde GAMA**, recalculé indépendamment en rejouant le test
   `world.shape covers each.location` sur la population du run — contre-épreuve : **201 agents
   auraient été hors de l'ancien monde** (`envelope(routes.shp)`, l'emprise Tisséo ; le ticket
   citait 163, mesurés sur la v3) ; (d) **0 `[ALARME]`** dans tout le journal, la seule `ERROR` étant
   l'échec du message de bienvenue à 22:54:51, antérieur à la connexion du WebSocket GAMA.
   ⚠ **La journée simulée n'était pas terminée** : à 23:43 la phase 4/5 attendait encore 759 tâches
   de pré-planification `act[N+1]`. Les quatre éléments du critère portent sur le chargement et le
   périmètre, pas sur le déroulement de la journée, d'où le verdict. Initialisation mesurée :
   population 19 min 30 (3 335 routes, 17 `None` = 0,5 %), bootstrap 20 min (1 000 / 1 000) avec
   **0 succès de cache sur 1 000** — la preuve que le passage à `r2` n'a rien resservi de `r1`.
   ⚠ **Observabilité** : la vague `act[N+1]` n'a aucun compteur de progression (le bootstrap en a un
   tous les 200) — neuf minutes de journal sans autre signal que des avertissements, contraire à la
   règle « journaliser le succès explicitement » du dépôt. À corriger.
3. Le rapport de run compare les parts modales aux cibles 453 communes, avec le transport
   scolaire déclaré (ou livré).
   **Non tenu, et bloqué en amont** : il demande une journée simulée complète (voir 2) et, surtout,
   le GTFS liO — qui porte 57 à 65 % du TC des 2ᵉ et 3ᵉ couronnes et n'est pas téléchargé
   (question ouverte n° 11) — plus le transport scolaire du ticket 030. Comparer les parts modales
   aux cibles avant d'avoir cette offre mesurerait le manque de données, pas le modèle.

## Ce que ce ticket ne fait pas
- Il ne remplace pas l'ENTD 2008 par l'EMC² 2023 comme enquête d'appariement (levier 3, autre
  ticket) : les chaînes d'activités restent celles de l'ENTD, filtrées sur les jours de classe.
- Il ne réchauffe pas les caches d'itinéraires (script à part, décision du 2026-09-03).
