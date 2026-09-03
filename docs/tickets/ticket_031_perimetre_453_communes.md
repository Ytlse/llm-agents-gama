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

### 1.0 Données à obtenir — avec l'accord de l'auteur du dépôt
| Donnée | Source | Volume |
|---|---|---|
| BD TOPO départements 32, 81, 82, 09, 11 | IGN géoservices, édition alignée sur D031 (2024-09) | 1 à 2 Go chacun |
| BAN `adresses-32/81/82/09/11.csv.gz` | adresse.data.gouv.fr | ≈ 20 Mo chacun |
| OSM | déjà présents : `midi-pyrenees-220101`, `languedoc-roussillon-220101` (Aude) | — (fraîcheur 2022 à noter) |

### 1.1 eqasim : six départements et la liste des communes (`config_toulouse.yml`, `data/spatial/`)
- `departments: ["31", "32", "81", "82", "09", "11"]`.
- Nouveau filtre par **liste de communes** (`llm_module/data/commune_couronne.json`, 453 codes
  INSEE) appliqué au stage des codes spatiaux : aujourd'hui eqasim tire sur tout le département
  (4,4 % du vivier hors des 453, audit A4). Journaliser le nombre de communes retenues par
  département (346 / 38 / 27 / 22 / 10 / 10).
- Export `llm_agents.py` : renseigner `household.commune_id` et `iris_id` (aujourd'hui
  `undefined`), pour que le runtime filtre par commune (§ 2.1).

### 1.2 Journées donneuses ENTD = jours de classe (`data/hts/entd/cleaned.py`)
- Aujourd'hui : `V2_TYPJOUR == 1` (jour de semaine), première journée par personne.
- Proposé : **`V2_VAC_SCOL == 0` pour tous les donneurs** — l'EMC² s'enquête elle-même hors
  vacances scolaires, la population entière y gagne en cohérence, pas seulement les écoliers.
  Mesuré : 17 723 → 14 063 donneurs (−21 %) ; la plus petite classe d'âge garde 1 002 donneurs
  pour un seuil `matching_minimum_observations` de 5.
- À décider : exclure aussi le **mercredi** (`V2_JOUR_DEP == 4`) pour les moins de 11 ans ? En
  2008 les écoliers n'avaient pas classe ce jour (17 % de trajets vers l'école) ; l'EMC² 2023
  mesure 91 % d'écoliers de 6-10 ans avec école, mercredis inclus. Hors vacances et hors
  mercredi, l'ENTD donne 88 à 96 %.
- Journaliser les journées écartées par motif ; cible : ≥ 88 % des 6-17 ans mobiles du vivier
  avec une activité `education`. Le contrôle de population gagne la ligne « scolaires avec
  activité d'études » (section ménages et mobilité) et la compare à l'EMC².
- Documentation : commentaire du réglage dans `config_toulouse.yml`, `README.md` et
  `CHANGELOG.md` du fork, `docs/setup/population.md`,
  `docs/arch/controle-population-jeu-de-test.md`, `docs/changelog.md`.

### 1.3 Vivier, pré-imputation, sélection v4
- Vivier de 10 000 (≈ 12 000 livrés) sur les 453 communes ; étape 3ter-a inchangée.
- Règle `aamas_seal_v4` : la descente compte déjà les six classes d'âge du rapport (`classe_age`
  ajouté le 2026-09-03) ; cibles `cj1` et `cm1` inchangées, elles sont calculées sur les
  453 communes. Nommage et sceau : `data/population/population_1000_AAMAS_v4/`.

### 1.4 Routage des plannings sur le polygone (étapes 4+5 du notebook)
- Le recalage des horaires a besoin d'un graphe OSMnx couvrant les domiciles et les écoles de
  3ᵉ couronne. Graphes construits depuis l'extrait pbf du polygone des 453 communes
  (`osmium extract --polygon` sur les pbf régionaux, puis `graph_from_xml`), clé de cache
  distincte de `Toulouse, France_30000`. `MAX_WORKERS` ≤ 8 (mémoire + 30 %) ; réchauffage
  toujours désactivé.
- Mesures à consigner (actions O1, O2, O4 du rapport) : nœuds et arêtes par mode, taille du
  pickle, RAM d'un worker, ms par route, part de paires « même nœud » (attendu ≈ 0 en 3ᵉ
  couronne, contre la majorité aujourd'hui).

### 1.5 Audit, contrôle, scellement, sauvegarde
- Audit de périmètre : A4 = 0 persona hors des 453 communes ; A2, A9 conformes.
- Contrôle : 13 marges conformes + `classe_age` (six classes) ; ligne scolaires ; trace
  horodatée dans `docs/traces/`.
- Scellement (MANIFEST déclarant le périmètre « 453 communes, polygone communal »), sauvegarde
  `data/population/sauvegardes/population_1000_AAMAS_v4_<date>.tar.gz`, `config.yaml` repointé.

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

| Maillon | Impact identifié | À mesurer ou décider |
|---|---|---|
| **Chargement runtime** (`handle/application.py`) | Le filtre rectangulaire `TOULOUSE_OSM_ROUTES_30K_BBOX` doit devenir un filtre par **commune du domicile** (liste des 453) et un `contains` du polygone pour les activités ; un fichier scellé se charge entier ou se refuse | Aucun agent v4 écarté ; comportement pour une activité hors polygone (école hors périmètre ?) |
| **OSMnx runtime** (`osmnx_server.py`, `trip_helper/osmnx_direct.py`, `geography.py`) | Graphes sur le polygone (même construction qu'en 1.4) ; `TOULOUSE_CENTER_DIST_M` disparaît au profit d'une emprise ; frontière `_in_city` et facteur de congestion à revérifier hors du disque (O3) ; vitesses de repli moins sollicitées | RAM du serveur et des workers, latence, taux de repli ; nouvelle clé de cache = invalidation du cache SQLite d'itinéraires ? (clé par coordonnées : à vérifier) |
| **OTP** (`otp-toulouse/`, `data/gtfs_year/`) | Extrait OSM sur le polygone (T1) ; GTFS liO en feed annuel (T2, 22,7 Mo, ODbL) ; cars TER éventuels (T6) ; `TOULOUSE_TRANSIT_SERVICE_WKT` recalculée (T4) ; calendrier liO (T5) ; trois instances plus lourdes | Temps de construction, RAM par instance, requêtes de plan en 3ᵉ couronne sans « Couldn't link » (T3) |
| **GAMA** (`Settings.gaml`, `includes/`) | Monde = polygone du périmètre au lieu de l'enveloppe Tisséo (G1) ; `routes.shp`/`stops.shp` avec liO et TER (G2) ; performance sur 106 × 93 km (G3) ; projection `roads.prj` UTM 48N à contrôler (G4) ; la voirie GAMA n'étant pas exploitée aujourd'hui, poser un **avertissement au chargement** si le shapefile de routes ne couvre pas le monde | Pas de simulation, mémoire, rendu ; comportement des agents hors enveloppe (contre-épreuve) |
| **Ticket 030** (car scolaire) | Se branche ici : option `school_bus` pour les mineurs hors Tisséo ; sans elle, la 3ᵉ couronne simulée n'a pas de TC pour ses écoliers | Voir ticket 030, lots A à D |
| **Résultats et métriques** | Temps terminal déjà par couronne communale (tt4) ; cibles modales inchangées (453) ; oracle LightGBM inchangé (appris sur toute l'enquête) ; **les runs v3 et v4 ne sont pas comparables** (périmètre, offre TC, plannings) | Quels résultats publiés reposent sur la v3 ? Rejouer ou déclarer |
| **Caches et jeux gelés** | Cache OSMnx SQLite (clé par coordonnées/mode/heure : réutilisable ?), cache OTP (nouveau graphe = nouvelles réponses), cache sémantique LLM (nouveaux personas = nouveaux prompts) ; jeux gelés de `prompt_calibration` et campagne génétique (ticket 009) construits sur une population antérieure | Lister les artefacts dérivés de la population et décider : régénérer, geler à nouveau, ou déclarer |
| **Visualisation** (`vizpop.py`, Grafana) | `vizpop` utilise la bbox 30 km ; emprises des cartes Grafana à vérifier | Emprises, fonds de carte |
| **Article** (`docs/paper/`) | Le périmètre déclaré devient exact (« 453 communes, six départements ») ; tableau de conformité à remesurer sur la v4 ; limite « transport scolaire » à déclarer tant que le ticket 030 n'est pas livré | Réécriture § 2.2 et annexe F |

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
