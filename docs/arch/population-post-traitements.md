# Population synthétique — les quatre étages de post-traitement

Entre le tirage statistique d'eqasim et le `traits_json` que lit l'agent LLM, la
population traverse **quatre étages** qui ajoutent, recodent ou corrigent des attributs.
Cette page dit lequel fait quoi, avec la règle exacte appliquée — pour qu'un attribut lu
dans un prompt puisse toujours être remonté à sa source.

Ce que produit l'**algo eqasim amont**, en une phrase : tirage des individus dans le
recensement INSEE (âge, sexe, PCS, activité, voitures, taille du ménage), appariement
statistique avec l'ENTD 2008 (permis, abonnement TC, nombre de vélos, chaîne de
déplacements), affectation du revenu FILOSOFI, localisation BAN/BDTOPO. Tout le reste
vient des étages ci-dessous.

Voir aussi : [../setup/population.md](../setup/population.md) (chaîne de génération,
données d'entrée, service Docker).

---

## A — Modifications du fork `eqasim-llm-toulouse`

Modifient le pipeline eqasim lui-même : l'attribut est produit **dans** la synthèse, pas
posé après coup.

| Fichier | Traits / objets touchés | Détail exact de la transformation |
|---|---|---|
| `config_toulouse.yml` | tout l'appariement HTS | `departments: ["31"]`, `sampling_rate: 0.01`, `filter_hts: false` (vivier ENTD national restauré : ~18 000 donneurs au lieu de quelques centaines), `matching_attributes` réordonné avec `age_class` **en tête** (la dégradation retire les colonnes par la fin, l'âge est donc le dernier abandonné), `matching_minimum_observations: 5`, stage `synthesis.population.llm_agents` ajouté à `run:` |
| `data/census/cleaned.py:145` et `:148-167` | `socioprofessional_class_detail`, `employment_sector` | `PCSL` → PCS 17 postes de la personne de référence (`ZZ` → 0) ; `NA17` → 17 libellés texte (`AZ` → `agriculture`, `OQ` → `public_admin_education_health`…), défaut `not_applicable` |
| `synthesis/population/enriched.py:60` | `number_of_bikes` | jointure du compteur de vélos depuis le ménage HTS apparié (ENTD `V1_JNBVELOADT`) |
| `synthesis/population/enriched.py:78-95` | `car_availability` | `none` / `some` / `all` selon nb voitures vs **nb permis des majeurs** (`age < 18 → has_license = False` avant agrégation) : sans ce filtre, un enfant de neuf ans porteur d'un permis hérité faisait basculer son ménage de `all` à `some` |
| `synthesis/population/enriched.py:101-111` | `bike_availability` | `none` si `number_of_bikes == 0`, `some` si `< household_size`, sinon `all` — calculé au niveau ménage puis rejoint sur les personnes, pour que les non-appariés héritent de la valeur du foyer |
| `synthesis/population/enriched.py:113-118` | `age_range` | `primary_school` ≤ 10, `middle_school` 11-14, `high_school` 15-17, sinon `higher_education` |
| `synthesis/population/enriched.py` (`_assign_personal_bike`) | `personal_bike` | **ticket 015, lot 4** : les trois étages appris sur EMC² 2023 remplacent l'imputation Bernoulli. `k` tiré **par ménage** (`household_id`, nativement présent) conditionnellement à la zone fine du domicile / la taille / la motorisation, attribué par tirage sans remise pondéré par la propension `P20`, puis VAE à 7,7 % **du parc** (et non 14,8 % des porteurs). Déterministe par hachage — ne consomme plus `random_seed`. Nouvelle dépendance de stage : `spatial.home.locations` (pour la zone). Détail : [velo-equipement.md](velo-equipement.md). ⚠ **écrit mais non rejoué** : demande `docker compose build eqasim` (le stage importe désormais `llm_module`, monté dans le service) puis une régénération complète |
| `synthesis/output.py:81-82` | colonnes CSV/parquet | ajout de `household_size`, `consumption_units`, `age_range`, `personal_bike` aux personnes ; filtre des géométries invalides dans la sortie spatiale (évite les `LineString` nulles) |
| `generate_population.py`, `server.py`, `Dockerfile` | — | HTTP 8003 (`/health`, `/generate`), requêtes **sérialisées** (synpp n'est pas réentrant), cache par taille exacte, `sampling_rate` recalculé depuis la population effective des communes (RP 2022) en mode bbox, filtrage bbox → communes par intersection IRIS 2024 en Lambert-93, données montées en volume `/eqasim-data` |

---

## B — Post-traitement d'export (`synthesis/population/llm_agents.py`)

Stage synpp custom : traduit la sortie eqasim en JSON pour GAMA. C'est ici que naissent
les libellés lisibles et la plupart des garde-fous.

| Ancre | Traits / objets touchés | Détail exact de la transformation |
|---|---|---|
| `:466-491` | `name`, `occupation.title`, `occupation.organization`, `socioprofessional_class`, `income`, `employment_sector` | Faker `fr_FR` **non graine** (nom différent à chaque génération, puis re-tiré au chargement) ; `_SPC_LABEL` / `_SPC_OCCUPATION_TITLE` (8 classes → libellé + titre de poste) ; `_SECTOR_ORGANIZATION` (NA17 → « Technology Company », « Public Institution »…) ; `income` textualisé aux seuils 1 500 / 2 500 / 3 500 / 5 000 € (`_income_label`, `:205`) ; `employment_sector = ""` si `not_applicable` |
| `:450-454` | `main_occupation` | 7 modalités FR depuis `professional_activity`, avec la règle scolaire : `student` → « Scolaire (jusqu'au Bac) » si `age < 18`, sinon « Étudiant » ; `under14` → toujours « Scolaire (jusqu'au Bac) » |
| `:456-462` | `travel_purposes` | dédup des motifs de la chaîne, mappés en FR **uniquement** pour `work` → Travail, `education` → Etude, `shop` → Achats : `leisure` et `other` n'apparaissent pas dans la liste vue par le LLM |
| `:26-34`, `:484-485` | `has_driving_license`, `has_pt_subscription` | `_flag()` traite le NaN comme « non » — sans ça `bool(nan) == True` donnait le permis à **toute personne non appariée** ; double verrou avec `age ≥ 18` |
| `:181-243`, `:494-502` | `home` | polygone de couverture OTP récupéré au démarrage (REST OTP1, sinon convex hull des arrêts OTP2 + tampon 0,02°). ⚠ **Le snap n'a jamais lieu** : `_snap_to_polygon` est défini et **n'est appelé nulle part** (vérifié le 2026-08-24). Le polygone ne sert plus qu'à décider de rafraîchir `identity.home` depuis la première activité domicile — un no-op, puisque les coordonnées sont identiques. Conséquence à connaître : aucun domicile n'est déplacé, mais **aucune activité hors du graphe OTP n'est ramenée dedans** — les trajets concernés n'ont simplement pas de solution TC, et le contrôleur les journalise avec `origin_in_bbox` / `dest_in_bbox` |
| `:305-385` | `activities[]` | domicile = unique source de vérité des coordonnées ; ajout d'une activité domicile en tête si la première n'en est pas une (et si `start_time > 0`) et en queue symétriquement (sauf journée déjà close à ≥ 86 400 s) ; continuité spatiale forcée première = dernière |
| `:387-414` | `activities[]` | fusion des activités consécutives de même motif et même lieu (< 1e-5°), pour éviter les requêtes de route origine = destination |
| `:428` | `activities[].id` | `uuid5` sur `{person_id}_{activity_index}` dans un namespace fixe → identifiants stables entre générations |
| `:305-307` | population | **rejet** des personnes dont la journée ne contient que du domicile |
| `_residence_traits` | `residence_zone`, `residence_commune`, `residence_insee` | **ticket 021, lot 5** : la couronne et la commune du domicile, lues sur le découpage communal de l'enquête (`zf_couronne.json`). Posé **après le snap** sur le polygone OTP, donc sur les coordonnées que porte `identity.home` — les poser en étage A (`spatial.home.locations`, avant snap) les ferait diverger de la colonne du journal pour tout persona snappé. ⚠ **écrit mais non rejoué** : demande `docker compose build eqasim` puis une régénération ; d'ici là, une génération neuve doit passer par l'étage D (`make residence-zone`) |
| `_root_field`, `entry` | `household.{id, iris_id, commune_id}`, `provenance.{census_person_id, hts_id}`, `validation.commute_mode` | **scellement AAMAS** ([controle-population-jeu-de-test.md](controle-population-jeu-de-test.md)) : trois blocs posés **à la racine de l'enregistrement**, jamais dans `traits_json` — qui entre dans le narratif du prompt et dans la clé du cache de décisions. `household` rattache le ménage et sa commune sans résolveur géométrique (condition du bootstrap par ménage) ; `provenance` trace le donneur RP et le donneur ENTD ; `commute_mode` (RP `TRANS`) est le mode de navette **déclaré**, vérité terrain par individu qui **ne doit pas atteindre le prompt**. Les trois colonnes source sont ajoutées à la sélection de `enriched.py`, où elles étaient jetées. Un champ absent vaut `None` et le stage compte les absences en fin de run (mesuré : `commute_mode` absent pour les non-actifs, `hts_id` absent pour les moins de 5 ans). Le modèle `Person` (pydantic v2, sans `extra='forbid'`) les ignore au chargement. Rejoué le 2026-09-02 (vivier 5 063) et le 2026-09-03 (11 922) |
| `immobile` (racine), `activities[]` | personnes sans activité hors domicile | **ticket 029** : elles étaient écartées (« skip persons with no activity other than home »), ce qui vidait la population de ses immobiles — 10,6 % des 5 ans et + dans l'EMC² 2023 — et, au passage, de tous les enfants de moins de 5 ans. Elles restent, avec une journée « domicile 0 → 86 400 s » (une activité, aucun trajet, aucun appel LLM) et `immobile: true` à la racine ; un immobile sans coordonnées de domicile est écarté et compté. Mesuré sur 10 000 demandés : 11 922 personnes dont 1 798 immobiles (15,1 % — l'ENTD en donne plus que l'EMC², la sélection ramène à 10,6 %), 364 enfants de moins de 5 ans (exclus par la sélection), 5 924 ménages tous complets. La chaîne aval tolère une journée à une activité (garde `n < 2` dans `population_utils.ajuster_planning`, qui plantait) |
| `:492-500` | `style`, `personality.big_five` | uniquement si `EQASIM_GENERATE_PERSONALITY=true` ; template choisi par `md5(person_id) % N` — déterministe, contrairement au nom |

---

## C — Post-traitement notebook (`scripts/data/population/generate_population.ipynb`)

Cinq étapes idempotentes avec checkpoints dans `Temp/`. Elles ne touchent pas aux traits
socio-démographiques : elles travaillent la **journée** et sa faisabilité.

| Étape | Fichier | Traits / objets touchés | Détail exact de la transformation |
|---|---|---|---|
| 2 — validation | `population_utils.py` | `activities[].start_time`, `.end_time`, `scheduled_start_time` | correction des chevauchements temporels, fusion des redondances, remise à `None` des `scheduled_start_time` |
| 3 — enrichissement TC | `population_utils.enrich_public_transport` | `location.public_transport` | flag vrai si un arrêt Tisséo (GTFS) est à moins de `MAX_PT_DIST_M = 1 500 m` de la localisation ; c'est ce flag que l'agent LLM lit pour envisager le TC |
| 4 — routage | `route_worker.py` | cache de routes (hors JSON) | routes OSMnx jusqu'à 12 workers, cache SQLite `data/cache/osmnx`, clé (origine, destination, mode, heure pour la voiture) |
| 5 — recalage | `travel_time.py` | `scheduled_start_time` | recalcul des heures de départ pour absorber les temps de trajet réels calculés à l'étape 4 |

L'**étape 8** enchaîne ensuite les correctifs de surface de l'étage D, et son ordre porte
deux contraintes, pas une :

1. `enrich_personal_bike` lit `housing_type`, qui doit donc être posé avant ;
2. `car_availability` **dérive** du nombre de permis du ménage, et `enrich_equipment`
   réécrit les permis. `fix_minor_traits` est donc rejoué **après** lui — il est
   idempotent, la seconde passe ne coûte que le recalcul — puis la recette
   d'`enrich_equipment` est repassée en lecture seule (`--dry-run --check`). Inverser cet
   ordre laisse `car_availability` calculé sur d'anciens permis **sans que rien ne le
   signale** : c'est l'avertissement littéral du ticket 017, et c'est pour cela que la
   garde vit dans le `--check` plutôt que dans un commentaire.

---

## D — Correctifs de surface (`scripts/data/population/`)

S'appliquent à une population **déjà générée**, sans accès aux données sources. Ils
existent parce que la cause racine est en amont ; les garde-fous de l'étage A sont ce qui
les rendra inutiles.

| Fichier | Traits touchés | Détail exact de la transformation |
|---|---|---|
| `fix_minor_traits.py` | `has_driving_license`, `activities[].purpose`, `travel_purposes`, `car_availability`, `personal_bike` | 5 règles idempotentes, dans l'ordre : permis → `false` sous 18 ans ; `work` → `education` pour scolaires et étudiants ; recalcul des motifs d'après les activités corrigées ; recalcul de `car_availability` par ménage sans les permis de mineurs ; `VAE` → `vélo normal` sous 14 ans (règle désormais **redondante** avec `enrich_personal_bike`, qui n'attribue plus de VAE sous 14 ans ; elle reste un filet pour les populations enrichies avant le ticket 015). **Ne corrige pas** les chaînes d'activités : horaires et destinations restent ceux de donneurs adultes — un enfant peut rester attendu à 8 h à l'autre bout de l'agglomération |
| `enrich_personal_bike.py` + `llm_module/core/bike_ownership.py` | `personal_bike` | **ticket 015, voie 1** : réécrit le trait sans régénérer. Foyers reconstitués à l'**adresse** du domicile (collisions scindées par `household_size`, ménages partiellement présents complétés par des « places absentes » qui concourent au tirage), puis les trois étages `k` → attribution → VAE. `None` hors couche de zones fines, et un `personal_bike` hérité d'eqasim y est **retiré** — sans quoi la population serait moitié apprise, moitié recopiée sans que rien ne le signale. `--check` échoue si une cible est hors tolérance **ou** si aucun contrôle n'a pu trancher. Détail et cibles opposables : [velo-equipement.md](velo-equipement.md) |
| `enrich_residence_zone.py` + `llm_module/core/residence_zone.py` | `residence_zone`, `residence_commune`, `residence_insee` | **ticket 021** : la couronne de résidence, LUE et non calculée. Le domicile est résolu en zone fine (`zone_resolver`), puis les trois premiers chiffres du code `ZF` donnent le secteur de tirage, qui porte la couronne (`zf_couronne.json`). Trait **observé** : ni tirage, ni hachage, ni loi — donc idempotent au sens fort. Trois écritures distinctes : une couronne dans le périmètre, `hors périmètre` pour un domicile connu et dehors, **aucun trait** sans coordonnées — écrire « dehors » de quelqu'un dont on ne sait rien serait une affirmation. La commune ne s'invente jamais : un domicile hors couche n'en reçoit pas. `--check` contrôle la couverture, l'accord entre classement par CODE et classement par APPARTENANCE géométrique, les modalités et le taux hors périmètre ; l'écart au cadrage de population sort en code 4, informatif, parce qu'il mesure le tirage (axe A9) et non ce trait. `--out` existe pour les populations épinglées par un manifeste de jeu gelé |
| `enrich_housing_type.py` + `llm_module/core/housing_type.py` | `housing_type` | **ticket 019** : imputation depuis la loi EMC² `M1` des **ménages de la zone fine** (pondération `COE0`), repli secteur de tirage puis périmètre entier, puis **levier de taille de ménage** `P(M1\|taille)/P(M1)` estimé au périmètre et renormalisé (*raking* à une dimension) ; la taille utilisée est le `household_size` **nominal** du persona, pas le nombre de membres présents. Tirage = hachage de l'**adresse** du domicile (deux personas du même foyer partagent le type ; résultat stable entre exécutions et machines), sel `housing_type_v2`. `None` hors couche de zones fines **et** sans taille de ménage — la colonne du journal reste vide, « non renseigné » étant une information. `--check` confronte le gradient de taille aux parts observées et échoue si son signe est faux |
| `enrich_equipment.py` + `llm_module/core/equipment_propensity.py` | `has_pt_subscription`, `has_driving_license` | **tickets 016 et 017, voie 1** : les deux traits posés par tirage Bernoulli des lois apprises sur EMC² (`make equipment-propensity`), en un seul script parce que leurs lots sont communs. Tirage = hachage de `(adresse, identifiant de personne, sel versionné)` — sur la **personne** et non l'adresse, un abonnement étant nominatif. Trois niveaux de repli géographique comptés (`zone` / `zone_sans_densite` / `perimetre`), et le niveau `perimetre` **calcule** la distance à l'hypercentre au lieu de la mettre à zéro — la mettre à zéro poserait le domicile au centre-ville, valeur la plus favorable aux TC. Permis `false` sous 18 ans par construction. **Ne recalcule pas `car_availability`** : la règle vit dans `fix_minor_traits` (règle 4) et deux implémentations dériveraient — mais `--check` **échoue** si `car_availability` ne dérive plus des permis posés, ce qui est le piège explicite du ticket 017. Deux codes de sortie distincts : **2** si l'ensemble ou la couverture ratent (la loi ou la pose est en cause), **4** si seule une strate rate (c'est la *composition* de la population, qui se corrige au tirage) |

---

## Attributs calculés en amont qui n'atteignent jamais l'agent

Ils existent dans `toulouse_persons.csv` / `toulouse_households.csv` mais pas dans le
`traits_json` : `household_id`, `iris_id`, `commune_id`, `consumption_units`, `age_range`,
`couple`, `commute_mode` (RP `TRANS`, qui porte pourtant le vélo comme mode de navette
déclaré), `socioprofessional_class_detail`, `number_of_motorcycles`, `number_of_vehicles`,
`use_motorcycle`, `number_of_bikes`, `bike_availability`, `census_person_id`, `hts_id`.

Deux nuances utiles :

- `number_of_vehicles` **est** utilisé, en amont : `synthesis/population/matched.py:204` en
  dérive `any_cars`, l'un des cinq `matching_attributes`. Il pilote donc le choix du
  donneur ENTD, mais sa valeur ne parvient pas à l'agent — et comme il somme voitures et
  deux-roues, un ménage sans voiture mais motorisé est apparié comme « motorisé ».
- `bike_availability` n'a **aucun** consommateur dans notre configuration : seuls
  `matsim/scenario/population.py` et `households.py` le lisent, et `matsim.output` n'est
  pas dans la liste `run:`. Toute l'information vélo qui atteint l'agent passe par
  `personal_bike` — depuis le ticket 015, par le modèle appris sur EMC² (étage A pour une
  génération neuve, étage D pour une population existante), plus par la recopie du donneur
  ENTD.

---

## Les traits d'équipement et leurs tickets

Quatre champs sont **recopiés du donneur ENTD 2008** (`enriched.py`, colonnes jointes
depuis le ménage et la personne HTS) : `has_license`, `has_pt_subscription`, `is_passenger`
(non exporté) et `number_of_bikes`. Chacun de ceux qui atteignent l'agent a été confronté
aux microdonnées EMC² Toulouse 2023 :

Depuis le ticket 015, `number_of_bikes` ne détermine **plus** `personal_bike` : il ne sert
qu'à `bike_availability`, que seul MATSim consommerait. La recopie du donneur subsiste dans
la colonne, pas dans le trait vu par l'agent.

| Trait | Écart mesuré | Ticket |
|---|---|---|
| `personal_bike` | total juste (53,3 % contre ~51 %), gradient de taille de ménage **inversé** — **corrigé** : gradient croissant 34,8 → 67,5 %, cf. [velo-equipement.md](velo-equipement.md) | [ticket 015](../tickets/ticket_015_acces_velo_progedo.md) |
| `has_pt_subscription` | 21,9 % contre 25,8 % ; étudiants 36,7 % contre **74,3 %** — **lot 1 livré** (loi apprise, cf. [ci-dessous](#les-deux-lois-déquipement-lot-1-des-tickets-016-et-017)) | [ticket 016](../tickets/ticket_016_abonnement_tc_progedo.md) |
| `has_driving_license` | 91,5 % contre 85,9 % chez les majeurs ; 18-24 ans **+27 pts** — **lot 1 livré** | [ticket 017](../tickets/ticket_017_permis_progedo.md) |
| `car_availability` / `_owns_car` | `some` en excès de 6,9 pts ; aucune rivalité intra-foyer | [ticket 018](../tickets/ticket_018_partage_voiture_foyer.md) *(non prioritaire)* |

Cause commune aux tickets 016 et 017 : la classe d'âge de l'appariement couvre 15 à 29 ans
d'un bloc, alors que le permis y va de 0 % à 78 % et l'abonnement TC de 64 % à 29 %.

Deux traits **imputés** du même tableau ont été mesurés au passage, avec deux issues
différentes :

- `housing_type` était tiré dans la loi de la zone fine **seule**, sans la taille du ménage.
  Contrefactuel calculé à l'intérieur d'EMC² (chaque ménage reçoit la loi de sa zone) : la
  part d'individuel isolé sortait à 25,4 % chez les personnes seules pour 15,7 % observés, et
  à 49,4 % chez les ménages de quatre et plus pour 53,9 %. Le gradient de taille était aplati,
  et mesuré à 27,2 % / 36,1 % dans la population synthétique — pente inversée.
  → **corrigé** par le [ticket 019](../tickets/ticket_019_habitat_taille_menage.md) : la loi
  de zone passe en pondération ménages et reçoit un levier de taille. Erreur absolue moyenne
  sur les 20 cellules (5 modalités × 4 tailles), mesurée dans EMC² : **3,00 pt → 0,75 pt**,
  marginale géographique inchangée. Détail et pièges : [le module](#le-conditionnement-du-logement-ticket-019)
  ci-dessous.
- `income` est le **revenu total** du ménage seuillé à 1 500 / 2 500 / 3 500 / 5 000 €, alors
  qu'eqasim vient de le construire en multipliant un revenu par unité de consommation par
  `consumption_units` (`income/uniform.py`, `income/bhepop2.py`). L'unité de consommation est
  jetée juste après avoir servi : le libellé mesure une taille de ménage autant qu'un niveau
  de vie — 0,5 % de « High » chez les personnes seules contre 75 % dans les ménages de six.
  **Décision du 2026-08-21 : non corrigé.** Le trait ne touche que le narratif du persona
  (il n'est pas dans la politique de choix modal) et le correctif exige une régénération —
  ni `household_income` ni `consumption_units` n'atteignent le JSON, aucun script de surface
  ne peut donc le rattraper. La limite est ici, elle n'est pas oubliée.

---

## Les deux lois d'équipement — lot 1 des tickets 016 et 017

`make equipment-propensity` apprend, **en une passe**, les deux propensions que les
tickets 016 et 017 spécifient séparément. Les deux tickets écrivent que leurs lots 1 et 2
sont communs — même fichier, même restriction, même pondération, même cause — et que « les
traiter séparément fait écrire deux fois le même chargeur ». Il n'y en a donc qu'un.

| | `has_pt_subscription` | `has_driving_license` |
|---|---|---|
| Cible EMC² | `P12 == 6` | `P7 == 1` |
| Ressource | `llm_module/data/pt_subscription.json` | `llm_module/data/driving_license.json` |
| Champ | 5 ans et plus | **18 ans et plus** — plancher légal en dur, pas une propension |
| AUC hors-échantillon | **0,798** | **0,953** |

`P7 == 3` (« conduite accompagnée et leçons de conduite », 266 personnes, âge médian 18
ans dont 155 majeures) compte **non**. C'est écrit dans le module et dans le chargeur : un
`== 1` nu l'affirmerait en silence.

### Le vecteur de design vit dans le module, pas dans le script

`llm_module/core/equipment_propensity.design_vector()` est la **seule** définition, et
l'export l'appelle comme l'enrichissement l'appellera. Même règle que
`bike_ownership.propensity_design` : une recopie de la formule dériverait au premier
changement de recodage, et l'écart entraînement/application ne se verrait nulle part.
L'aller-retour est vérifié — la loi rechargée depuis sa ressource redonne la prédiction de
`sklearn` à 4·10⁻¹⁶ près.

Covariables : âge continu et sa courbure, genre, occupation principale (8 indicatrices),
**motorisation du ménage** (`cars0` / `cars2p`, référence une voiture), densité de ménages
de la zone fine en log, distance à l'hypercentre. Trois absences délibérées :

- **aucune covariable de déplacement** — un équipement est un *stock*, il doit être
  invariant au trajet, sinon le même agent est abonné pour aller travailler et ne l'est
  plus pour ses courses. Même argument que le ticket 015 sur `D12` ;
- **aucun revenu** — `M22` est livré **vide** (0 valeur sur 10 783 ménages). Les tarifs
  sous condition de ressources sont donc inobservables, et la loi ne les approche pas ;
- **aucun étage de ménage** — un abonnement et un permis sont nominatifs. C'est ce qui rend
  ces deux traits moins coûteux que le vélo : la corrélation intra-foyer est portée par la
  motorisation, observée et juste dans la population synthétique.

### Les paliers tarifaires sont arbitrés, pas décrétés

La tarification Tisséo (« moins de 26 ans », ouverture senior à 65 ans ou 62 pour les
retraités) n'entre **jamais comme grandeur** : ni montant, ni échelon, ni taux de
fréquentation. Elle entre comme *emplacement de rupture* dans la courbe d'âge — et un
emplacement se teste. Le script ajuste chaque trait avec et sans ces paliers, et tranche
sur une règle écrite avant de voir le résultat : retenus si l'AUC hors-échantillon groupée
par ménage gagne au moins 0,002.

| Trait | Sans paliers | Avec paliers | Gain | Verdict |
|---|---|---|---|---|
| `has_pt_subscription` | 0,7903 | 0,7982 | **+0,0079** | **retenus** |
| `has_driving_license` | 0,9530 | 0,9529 | −0,0001 | **retirés** |

L'arbitrage tranche donc dans les deux sens, ce qui est la seule preuve qu'il n'est pas un
tampon : les paliers tarifaires gagnent leur place sur l'abonnement, et la perdent sur le
permis — où ils n'avaient aucune raison métier d'être.

### ⚠ Une cible du ticket 016 est restatée

Le ticket donne **74,3 %** d'abonnés chez les étudiants, sur *n* = 1 327. C'est `P9 == 4`
seul. Or le recodage du dépôt (`MAIN_OCCUPATION`) range **aussi** `P9 == 3`
(alternance/stage, 146 personnes) dans « Étudiant », et ces 146 personnes s'abonnent à
56,7 % — un comportement réellement différent. Sur la définition du dépôt, *n* = 1 473 et
la cible opposable est **72,2 %**.

C'est la définition du dépôt qui doit gagner, parce que c'est celle que le persona porte :
opposer 74,3 % à une population dont les étudiants incluent les alternants noterait la loi
sur une strate qu'elle ne peut pas voir. Le critère est donc **restaté à 72,2 %**, comme
`export_bike_ownership` restate sa moyenne de vélos écrêtée.

### Ce que la loi reproduit hors échantillon

Écarts prédit − observé, validation croisée groupée par ménage, sur l'enquête elle-même.
Tous les strates d'occupation tiennent à 0,1 pt ; les bandes d'âge sont les plus tendues :

| Bande | Abonnement (écart) | Permis (écart) |
|---|---|---|
| 18-24 | −1,3 | +0,2 |
| 25-34 | −2,2 | **−3,2** |
| 35-49 | +1,1 | +0,9 |
| 50-64 | +1,3 | +0,5 |

Le −3,2 des 25-34 sur le permis **dépasse la tolérance de ± 3 pt** du ticket 017. À
trancher au lot 2 : soit une interaction âge × genre (que le ticket demande explicitement
et que cette version n'a pas), soit un critère restaté. Ne pas le laisser passer en
silence.

Ce que la loi **ne reproduit pas**, et c'est une borne d'identification, pas un défaut :
67 % des ménages (7 238 sur 10 783) n'ont qu'une seule personne enquêtée. On peut estimer
`P(équipé | covariables)`, on ne peut pas observer qui, parmi deux frères et sœurs, est
abonné. La corrélation intra-foyer résiduelle est donc mesurée et publiée dans la
ressource, jamais reproduite.

### Ce que la pose donne sur `toulouse_population_1000.json` (lot 2)

| Trait | Avant (recopie ENTD) | Après (loi EMC²) | Cible |
|---|---|---|---|
| abonnement TC, ensemble | 21,9 % | **22,9 %** | 25,8 % |
| permis, 18 ans et + | 91,5 % | **87,7 %** | 85,9 % |
| **écart étudiant − retraité** (abonnement) | **+5,7 pt** | **+45,5 pt** | +54,5 pt |

L'écart étudiant − retraité est le critère le plus discriminant du ticket 016, et c'est
celui qui bouge le plus : la recopie ENTD l'écrasait d'un facteur 10, la loi le restitue
aux quatre cinquièmes. 352 valeurs d'abonnement et 148 de permis changent, et
`car_availability` suit sur 68 ménages à la seconde passe.

⚠ **La recette sort en code 4 — écart de composition, pas défaut du trait.** Deux strates
ratent, et dans des sens opposés :

| Strate | Posé | Cible | Écart |
|---|---|---|---|
| abonnement · Étudiant | 59,8 % | 72,2 % | **−12,4** |
| permis · Étudiant | 72,0 % | 59,2 % | **+12,8** |

Cause mesurée, et ce n'est pas la loi : **les étudiants synthétiques vivent dans des
ménages trop motorisés.**

| Étudiants | Population synthétique | Enquête (pondérée) |
|---|---|---|
| ménage sans voiture | 36,6 % | **48,5 %** |
| ménage à 2 voitures et + | 34,1 % | 24,1 % |
| voitures par ménage | 1,11 | 0,92 |
| femmes | 40,2 % | 54,6 % |
| âge moyen | 21,1 | 21,2 |

L'âge n'y est pour rien (les étudiants synthétiques sont même légèrement plus jeunes). La
motorisation est la covariable la plus forte de la loi — 61,8 % d'abonnés à zéro voiture
contre 16,1 % à deux et plus — donc un déficit de 11,9 points de ménages sans voiture coûte
mécaniquement la part d'abonnement, et un excédent de motorisation gonfle la part de permis.

C'est un défaut **de tirage**, pas d'imputation : `number_of_cars` est juste en agrégat
(1,28 simulé contre 1,25 mesuré), c'est sa **distribution jointe avec l'occupation** qui ne
l'est pas. Aucun post-traitement de trait ne peut le réparer — le motif est le même que
celui des tickets 015 à 019, d'un cran plus haut. À ouvrir en ticket propre ; l'effectif
(82 étudiants) commande d'abord de le confirmer sur une population plus grande.

### Ce que la correction vaut sur le volet 3 (contrefactuel, politique figée)

Mesure faite sur `experiments/archive/2026-08-26_17_46` : mêmes OD, **même offre OTP**,
**même politique**, seuls les deux traits changent. Trace :
`scripts/synthesis/data/progedo_on_common_set_2026-08-26_17_46_equipement.parquet`. La
population enrichie n'est pas versionnée — elle se régénère à l'identique par hachage :

```bash
cp experiments/archive/2026-08-26_17_46/population_1000.json /tmp/pop_cf.json
llm-agents/.venv/bin/python -m scripts.data.population.enrich_equipment /tmp/pop_cf.json
llm-agents/.venv/bin/python -m scripts.data.population.fix_minor_traits  /tmp/pop_cf.json
```

Composite du volet 3, `emd_jsd` (et `l1_composite` en points de %) :

| Lecture | Avant | Après | Écart |
|---|---|---|---|
| **brut** (avant renormalisation) | 6,282 | **5,749** | **−0,533** *(l1 : −9,23)* |
| **élu** (mode le plus probable) | 6,464 | **6,086** | **−0,378** *(l1 : −4,16)* |
| **attendu** (masse renormalisée) | 6,015 | 5,941 | −0,074 *(l1 : **+0,72**)* |

**Le chiffre de tête ne bouge presque pas, et c'est le résultat le plus instructif du
contrefactuel.** La prédiction brute — la vision propre du modèle — gagne 0,53 point de
composite et 9,2 points de L1. La masse renormalisée sur l'offre OTP, elle, gagne 0,07 et
*perd* 0,72 en L1.

L'explication est dans les strates. Là où le ticket 016 annonçait le gain, il est là :

| Strate | Avant | Après | Gain |
|---|---|---|---|
| âge 15-19 · voiture | +28,0 | **+23,7** | 4,2 |
| âge 15-19 · TC | −24,5 | **−19,2** | 5,3 |
| âge 10-14 · TC | −15,3 | **−11,3** | 4,0 |
| motif études · voiture | +16,7 | +13,9 | 2,9 |
| occupation scolaire · voiture | +13,6 | +11,7 | 1,9 |

Et là où il n'y en avait pas à attendre, il n'y en a pas : chômeurs · marche −11,7 → −11,9,
75 ans et + · marche −15,0 → −14,9. Ces écarts-là sont ceux des **longueurs de trajet**, que
nul trait ne corrige.

Mais deux dimensions **se dégradent**, et il faut dire pourquoi :

| Dimension | l1 moyen avant | après |
|---|---|---|
| âge | 19,87 | **18,83** |
| motif | 19,21 | **18,02** |
| occupation | 18,99 | **18,10** |
| **genre** | 5,69 | **7,62** |
| type de logement | 17,43 | 18,10 |
| lieu de résidence | 16,75 | 17,39 |

Cause : **les TC étaient déjà surprédits chez les adultes avant la correction.** Hommes
13,5 % contre une cible de 11,6 ; Toulouse 23,4 contre 21,6 ; 1ʳᵉ couronne 10,5 contre 8,2.
Relever les abonnements — à juste titre, l'enquête le demande — pousse ces valeurs plus haut
encore (hommes 15,6, Toulouse 24,9), donc au-delà de la cible.

C'est **exactement le diagnostic du ticket 016**, vérifié par l'autre bout : « la part TC
globale reste presque juste, et elle est juste pour les mauvaises personnes. Un correctif
sur le niveau agrégé ne peut rien y faire. » La surprédiction agrégée chez les adultes et
la sous-prédiction chez les jeunes se compensaient ; corriger les personnes les **sépare**.
Le composite de tête ne récompense donc pas la correction — il ne la punit pas non plus, il
était juste pour de mauvaises raisons.

Conséquence pratique pour la suite : **le volet 3 n'est pas le bon juge de ce lot.** Ce que
la correction doit produire se mesure au volet 1 — ce que le LLM fait de personas dont
l'abonnement et le permis sont enfin distribués comme dans l'enquête — et cela demande un
run. Réserve à garder pour ce run : ici l'offre OTP est **gelée**, or `_can_drive` lit
`has_driving_license` et conditionne l'offre voiture
([simulation_controller.py:414](../../llm-agents/urban_mobility_agents/simulation_controller.py:414)).
L'effet du permis est donc **sous-estimé** dans ce tableau : retirer un permis retirerait
aussi l'option voiture du jeu de choix.

---

## Le conditionnement du logement (ticket 019)

`housing_type` est le seul trait que **rien** dans la chaîne de génération ne porte : ni
eqasim, ni les tables INSEE du notebook. Il est imputé après coup, et le ticket 019 change
la loi dans laquelle on l'impute — pas le contrat du trait, qui reste les cinq libellés
EMC² ou l'absence.

### La règle

```
P(M1 = m | zone, taille) ∝ P(M1 = m | zone) × [ P(M1 = m | taille) / P(M1 = m) ]
```

La zone fixe le niveau, la taille du ménage déplace les modalités les unes par rapport aux
autres, puis on renormalise. C'est un transfert de rapport de cotes (*raking* à une
dimension), et il tient parce que le levier est estimé **au périmètre** : la cellule (zone,
taille) compte 3 ménages enquêtés en médiane sur 2 145 cellules, dont 18 seulement
atteignent 30 observations. Servir la loi brute `P(M1 | zone, taille)` ferait passer du
bruit d'échantillonnage pour de la géographie.

Le lissage hiérarchique existant est conservé tel quel : zone → secteur de tirage →
périmètre, poids du repli à l'effectif médian d'une zone. Ce poids a suivi le changement
d'unité — 18 personnes enquêtées en médiane, mais **12 ménages**. 195 zones sur 704 comptent
moins de 5 ménages enquêtés (132 comptent moins de 5 personnes) : elles s'effacent derrière
leur secteur, et la ressource publie l'effectif de chaque zone en ménages **et** en
personnes pour que ce soit vérifiable. Le compte par niveau de repli réellement servi est
publié à chaque enrichissement.

### Ce que ça vaut, mesuré dans EMC²

Chaque ménage enquêté reçoit la loi de sa zone corrigée du levier de sa taille, puis on
compare à son `M1` réel. Aucun biais de périmètre : le mécanisme tourne sur des ménages dont
on connaît la vérité. Part d'**individuel isolé**, et erreur absolue moyenne sur les 20
cellules (5 modalités × 4 tailles) :

| Taille du ménage | Observé | Zone seule, `COEP` *(avant)* | Zone seule, `COE0` | **Zone `COE0` + levier** |
|---|---|---|---|---|
| 1 personne | 15,7 % | 26,4 % | 24,0 % | **14,0 %** |
| 2 | 46,5 % | 41,6 % | 38,3 % | **45,6 %** |
| 3 | 45,5 % | 45,3 % | 41,8 % | **47,1 %** |
| 4 et + | 53,9 % | 47,8 % | 43,9 % | **55,2 %** |
| **Erreur absolue moyenne** | — | **3,00 pt** | 3,76 pt | **0,75 pt** |

Deux choses à ne pas perdre de vue, toutes deux écrites dans le module :

- **la pondération n'est pas le sujet.** Passer des poids personnes (`COEP`) aux poids
  ménages (`COE0`) *sans* le levier **dégrade** le résultat (3,00 → 3,76 pt) : la pondération
  personnes compensait partiellement l'absence de taille, par coïncidence. Les deux
  changements vont ensemble ou pas du tout. Une fois la taille conditionnée, la pondération
  ménages est la bonne — un ménage occupe un logement et tire une fois ;
- **le résidu est réel.** Le raké dépasse de 1,2 à 1,6 point aux tailles 3 et 4+ :
  l'hypothèse de transfert (le levier est le même dans toutes les zones) n'est pas exacte,
  elle est bonne à 0,75 point. Un levier par secteur de tirage est l'amélioration suivante ;
  elle n'est pas nécessaire pour tenir la recette et reste hors périmètre.

La géographie ne bouge pas : marginale d'ensemble 34,7 / 12,9 / 28,2 / 23,6 / 0,6 % observée
contre 34,1 / 13,1 / 28,2 / 23,9 / 0,7 % rakée. Si elle bougeait, c'est que le levier
écraserait la zone.

### Les trois pièges

1. **La taille est celle du persona, pas celle du fichier.** 118 des 498 grappes d'adresse
   de `toulouse_population_1000.json` sont partielles (filtrage par bbox). Tirer sur le
   nombre de membres présents mettrait des familles de quatre dans des lois de personne
   seule — même règle que l'étage 2 du [ticket 015](../tickets/ticket_015_acces_velo_progedo.md).
2. **Une ressource v1 est refusée.** Le module exige `version ≥ 2` et les quatre leviers.
   Une v1 imputerait sur la seule zone, donc avec le gradient aplati, sans que rien ne le
   signale : c'est le scénario du déploiement à moitié fait, et il lève au chargement.
   `make housing-type` régénère la ressource ; elle est hors dépôt, comme la couche de zones.
3. **Pas de repli quand la taille manque.** Un persona sans `household_size` ne reçoit
   **aucun** type de logement, il est compté (`sans_taille`) et la colonne du journal reste
   vide. Retomber sur la loi de zone ferait rentrer le défaut par la fenêtre.

### Ce que ça donne sur les populations en service

`enrich_housing_type --check` publie le tableau ci-dessous à chaque passage. Part
d'**individuel isolé** par taille de ménage sur `toulouse_population_1000.json`, avant
(loi de zone seule, fichiers `*.pre_t015.bak`) et après :

| Taille | Avant | **Après** | EMC² observé | Adresses |
|---|---|---|---|---|
| 1 personne | 29,0 % | **14,5 %** | 15,7 % | 204 |
| 2 | 41,8 % | **41,8 %** | 46,5 % | 170 |
| 3 | 38,5 % | **36,9 %** | 45,5 % | 71 |
| 4 et + | 38,5 % | **52,1 %** | 53,9 % | 78 |
| **Pente 1 → 4+** | **+9,5 pt** | **+37,6 pt** | +38,2 pt | — |

Le signe de la pente était le critère principal, et il est retrouvé. Deux cellules (tailles
2 et 3) dépassent les ± 4 points stricts du ticket, et le contrôle les accepte quand même :
à 71 adresses, l'écart-type d'une proportion autour de 45 % vaut 5,9 points, si bien que
± 4 points est **sous le plancher de mesure** de la cellule. La marge appliquée est donc
`4 points + 2 σ`, σ étant calculé sur le nombre d'**adresses** et non de personas — six
personnes d'un même foyer partagent un unique tirage, les compter six fois ferait croire la
cellule six fois plus précise qu'elle n'est. C'est le même raisonnement qui a conduit à
restater trois critères du ticket 015.

Couverture : 976 personas sur 1 021 (95,6 %). Les 45 restants sont hors de la couche de
zones fines et n'ont **pas** de type de logement — la colonne du journal reste vide. 969 des
976 reçoivent la loi de **leur** zone, 7 celle de leur secteur, aucun celle du périmètre.

Sur les populations de 10 et 100 agents, le trait est posé mais **aucune cellule ne
tranche** : le script sort alors le code 3, « enrichie mais non validée », qui n'est ni un
succès ni un échec. Une population de 10 agents ne peut arbitrer aucun croisement, et un
rapport où rien ne tranche ne doit pas se lire comme un rapport vert.

### Ce que ça débloque

L'axe habitat est le critère n° 2 du ticket 015 (équipement vélo par type d'habitat). Il
n'est pas indépendant de la taille du ménage : standardisé sur la structure de tailles, le
gradient de l'équipement vélo tombe de 33,4 à 20,8 points — **38 % de ce gradient est de la
composition de ménages**, pas de l'habitat. Valider les vélos sur cet axe suppose donc que
le croisement habitat × taille soit juste dans la population.

La cible « diluée » que `export_bike_ownership.py` recalcule à chaque export — l'amplitude
atteignable quand on croise le nombre de vélos *vrai* de l'enquête par un habitat *imputé* —
s'est resserrée d'elle-même, sans qu'une ligne du modèle vélo change :

Part de **ménages équipés** (`k > 0`), l'unité de la courbe publiée :

| | Avant (zone seule) | **Après (zone + levier)** | Publiée (habitat observé) |
|---|---|---|---|
| Accord habitat imputé / observé | 47,6 % | **50,2 %** | — |
| Individuel isolé | 62,5 % | **67,2 %** | 70,9 % |
| Grand habitat collectif | 42,5 % | **40,4 %** | 37,5 % |
| **Amplitude opposable** | **19,9 pts** | **26,8 pts** | 33,4 pts |

**+6,9 points d'amplitude regagnés**, soit la moitié de l'écart qui séparait la cible
opposable de la courbe publiée. Le contrôle vélo a été rejoué sur la population ré-imputée
et il passe (`enrich_personal_bike --check`, code 0), avec des écarts de +0,1 à +2,3 points
sur les quatre modalités.

**Une leçon d'unité est tombée en cours de route, et elle vaut pour tout cet axe.** Le
premier rejeu montrait un biais de 0,9 à 8,6 points *sous* la cible, du même signe sur les
quatre modalités — donc pas du bruit. La cause n'était pas le modèle vélo : la cible était
une part de **ménages équipés** (un foyer compte pour un dès qu'il a un vélo) comparée à une
part de **personnes dotées** (`personal_bike` est un trait individuel, et dans un foyer de
quatre avec un vélo une seule personne le porte). L'écart entre les deux grandeurs suit donc
la taille du ménage — 10 points en individuel isolé où le foyer moyen compte 2,6 personnes,
3 points en grand collectif où il en compte 1,6 — ce qui produisait exactement le profil
observé. La ressource sert désormais **les deux** grandeurs avec un champ `unit` qui les
distingue. Détail : [velo-equipement.md](velo-equipement.md).
