# Ticket 030 — Le car scolaire synthétique : rendre aux mineurs périurbains leur premier mode collectif

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ce qui suit est une **spécification**. Issu du rapport de périmètre du 2026-09-03
> (`docs/paper/population/RAPPORT_PERIMETRE_453_COMMUNES.html`, § 6 et action T7) : les GTFS
> Tisséo, TER et liO couvrent toute l'offre régulière des 453 communes, mais aucun ne porte le
> transport scolaire, qui est l'essentiel des transports collectifs des 2ᵉ et 3ᵉ couronnes.

## Le problème, en quatre mesures

1. **Le transport scolaire est le TC des couronnes externes.** Microdonnées EMC² 2023 (fichier
   déplacements × COEP, mode principal MODP) : 97 % des déplacements en autocar des habitants de
   3ᵉ couronne sont faits par des 5-17 ans pour un motif d'études (91 % en 2ᵉ, 93 % en 1ʳᵉ,
   78 % à Toulouse). L'autocar porte 65 % du TC de la 3ᵉ couronne, 57 % de la 2ᵉ ; le TER 10 %
   et 2,5 %. Sur le périmètre, le transport scolaire pèse 1,6 % de tous les déplacements, soit
   13 % du TC.
2. **Il n'est dans aucun GTFS.** Le GTFS liO (transport.data.gouv.fr, ODbL) exclut les services
   à titre principal scolaire ; ni la Région ni le Département ne publient les circuits ;
   les horaires n'existent que sur le portail d'inscription liO, circuit par circuit.
3. **Qui est concerné dans la population scellée v3** : 48 des 172 mineurs habitent sans arrêt
   Tisséo à moins de 1,5 km (18 en 2ᵉ couronne, 30 en 3ᵉ) ; 26 d'entre eux ont une activité
   d'études dans la journée — c'est la clientèle du car scolaire sous la règle retenue (âge + zone
   hors ressort Tisséo). Sans service scolaire, leur part TC est nulle par construction.
4. **Les écoliers ne vont pas tous à l'école.** Dans la v3, 69 des 151 mineurs mobiles n'ont
   aucune activité d'études un lundi ; dans le vivier eqasim (11 922), 50 à 54 % des 6-17 ans
   seulement en ont une, contre 90 à 95 % dans l'EMC² un jour de semaine. Cause mesurée sur
   l'ENTD 2008 (`K_deploc.csv`) : les journées donneuses des enfants incluent les vacances
   scolaires (`V2_VAC_SCOL = 1`, 20 % des journées, 7 à 16 % d'école) et le mercredi
   (`V2_JOUR_DEP = 4`, 17 % d'école chez les 6-10 ans en 2008) ; hors vacances et hors
   mercredi, 88 à 96 % des journées donneuses ont un trajet vers l'école.

## Ce que le ticket fait

### Lot 0 — Prérequis : les écoliers vont à l'école → **ticket 031, § 1.2**
Le filtre des journées donneuses ENTD (hors vacances scolaires `V2_VAC_SCOL`, mercredi des moins
de 11 ans `V2_JOUR_DEP`) façonne la population : il est porté par le ticket 031 (construction du
fichier de population du périmètre des 453 communes), avec sa cible (≥ 88 % des 6-17 ans mobiles
avec une activité `education`) et sa ligne de contrôle. Les lots A à D ci-dessous sont du runtime
et n'en dépendent que pour avoir des écoliers à transporter.

### Lot A — Éligibilité et calcul de l'option (`llm-agents/trip_helper/`, nouveau module)
Les critères viennent du **règlement des transports scolaires régionaux liO** (document public),
pas de l'enquête. Le règlement sépare deux niveaux, qu'on reprend tels quels :

- **Condition de zone (couverture) — où la Région propose le service.** Le règlement confie le
  transport scolaire des élèves dont *à la fois le domicile et l'établissement sont dans le ressort
  d'une AOM urbaine* à cette AOM, pas à la Région. Le car scolaire liO synthétique n'existe donc
  que **hors du ressort Tisséo** (les 108 communes du ressort). En pratique côté code, le proxy
  disponible est `home.public_transport = false` (aucun arrêt Tisséo à ≤ 1,5 km) ; la forme fidèle
  est l'appartenance de la commune du domicile à la liste hors-ressort.
- **Éligibilité individuelle — un seul critère retenu : l'âge.** Persona de **5 à 17 ans**, sur un
  trajet lié à son activité `education` (aller : destination = l'école ; retour : origine = l'école).
  Décidé le 2026-09-03 : on **abandonne la sectorisation et la distance minimale domicile-école**
  (≥ 3 km du règlement, comme le seuil de 2 km issu de l'enquête). Conséquence assumée : l'option
  est proposée même pour une école proche ; c'est au modèle de ne pas la choisir pour 400 m.

- **Horaire** : calé sur l'activité `education` avec **30 min de marge** — l'aller arrive 30 min
  avant le début de l'activité, le retour part 30 min après sa fin (le règlement cale les circuits
  sur « la première entrée et la dernière sortie de l'établissement » et ne publie pas les heures
  de passage ; 30 min est notre alignement au mieux). Une seule occurrence : pas de suivant. **Pas
  de calendrier scolaire au runtime** : la simulation ne porte que des jours de semaine hors
  vacances (garanti en amont, ticket 031 § 1.2), donc tout jour simulé est un jour de classe.
- **Durée** : 5 min d'accès à l'arrêt + distance à vol d'oiseau × 1,5 à 20 km/h + 10 min de
  ramassage, recalée pour que la médiane retrouve les 30 min observées. **Source : microdonnées
  EMC²** (30 min en médiane, 20 à 40, pour 7,3 km parcourus et 4,9 km à vol d'oiseau ; détour 1,5 ;
  16 km/h porte à porte). L'enquête reste la source de la **durée** (réalisme physique du temps de
  trajet) ; elle ne sert plus à décider *qui* est éligible ni à caler des parts modales — le
  règlement ne donne, lui, aucun chiffre de durée ni de détour.
- **Coût** : nul (transport scolaire régional gratuit depuis 2021).
- L'option porte un mode `school_bus`, compté comme transport collectif dans les métriques, les
  cibles EMC² (code 41) et l'oracle LightGBM (groupe `transit`).

**⚠ Le classement en TC ne va pas de soi.** Un mode `school_bus` non déclaré tombe silencieusement
en « autre » : `canonical_mode` (`llm_module/core/mode_choice.py`) reconnaît `"bus"` comme
mot-clé, mais seulement en tronçon exact ou en sous-chaîne d'au moins 5 caractères — `"school_bus"`
comme tronçon unique ne contient pas `"bus"` en part et le mot fait 3 caractères, donc il finit en
`OTHER_MODE`, hors du groupe `transit`. **Trois tables de métriques + le pont oracle** à étendre
pour que le car scolaire compte en TC :
1. `move_logger._BUS_MODES` (`llm-agents/urban_mobility_agents/utils/move_logger.py`) — pour que
   `moves.csv` range le trajet en `Transports_collectifs` ;
2. `canonical_mode` / `_MODE_KEYWORDS` (`llm_module/core/mode_choice.py`) — pour le vocabulaire
   canonique et, par ricochet, le pont oracle `public_transport → transit`
   (`scripts/synthesis/model_on_common_set.py`, `POLICY_CLASS_TO_CAT` / `CANONICAL_TO_CAT`) ;
3. `categorize_mode` (`scripts/models_influence/prompt_calibration_lib.py`) — pour la loss de
   calibration face aux cibles EMC².

**Exception, à NE PAS étendre : `_PT_LEG_MODES`** (`llm-agents/.../agents/llm_agent.py`). Cette
liste ne sert pas les métriques mais la **mention d'abonnement** accolée à l'option dans le prompt
(`_pt_subscription_note` : « Abonné / Pas d'abonnement aux transports en commun »). Le transport
scolaire est **gratuit** : y ajouter `school_bus` collerait une mention d'abonnement fausse et
trompeuse. Le car scolaire compte en TC pour la mesure, mais ne se comporte pas comme un TC à
abonnement dans le prompt.

**Test de non-régression (obligatoire), en deux assertions.** Un plan portant une jambe
`mode = "school_bus"` doit (a) se catégoriser en `transports_collectifs` / `transit` dans les
**trois tables de métriques ET le pont oracle**, et (b) **ne recevoir aucune mention d'abonnement**
(`_pt_subscription_note` renvoie la chaîne vide). Le volet (a) est d'abord **vu échouer** contre le
code actuel (les tables ignorent `school_bus`), puis passe une fois l'extension faite — un test
qu'on n'a pas vu échouer contre le code fautif ne prouve rien.

### Lot B — Présentation et cycle de vie
L'option est présentée au modèle comme les autres (« car scolaire liO, gratuit, départ 7 h 25,
arrivée 8 h 05, 32 min »), avec le vélo, la marche, la voiture si disponible. Elle n'apparaît
jamais pour un adulte ni pour un trajet sans lien avec l'école, ni pour un domicile dans le ressort
Tisséo. Journalisation : options scolaires proposées / choisies par jour, `[ALARME]` si un persona
éligible (âge + zone) n'en reçoit aucune sur toute la journée. Rendu GAMA : hors périmètre (voir
section dédiée) — l'agent s'affiche en rouge (marqueur `__DIRECT_CAR__`), la palette TC verte est
abandonnée avec le lot GAMA.

**Invalidation de cache.** L'ajout de l'option change le jeu d'options présenté à un éligible ;
une décision LLM mise en cache *avant* l'option ne verrait jamais le `school_bus`. Vider le cache
de décisions LLM et le cache sémantique suffit (le `school_bus` est synthétique : aucun appel OTP
ni OSMnx, donc le cache de routage n'est pas concerné). Décidé : on vide ces caches à la livraison.

### Rendu du déplacement dans GAMA — hors périmètre (décision 2026-09-03)
Aucune édition GAMA. La jambe school_bus **réutilise le marqueur `__DIRECT_CAR__`** : GAMA
l'interpole point-à-point (`do goto`, vitesse = distance/durée) exactement comme une voiture, donc
l'agent **se déplace correctement sans aucune modification** de `Inhabitant.gaml`. Contreparties
assumées :
- l'agent s'**affiche en rouge** (couleur voiture) au lieu du vert TC — sans effet en run headless
  (`make run OFFLINE=1`), qui n'a pas de rendu ; à revoir seulement si un rendu GUI l'exige ;
- les **métriques ne sont pas affectées** : elles lisent `leg.mode = "school_bus"` (et non le
  marqueur), donc `_primary_mode` renvoie « transit » et le trajet compte en TC.

**Piège à éviter (déduplication).** `TravelPlan.get_code()` = `transit_route ^ arrêt_départ ^
arrêt_arrivée`. Une jambe voiture directe a des arrêts vides → code `"__DIRECT_CAR__^^"`. Si la
jambe school_bus réutilise `__DIRECT_CAR__` avec des arrêts vides, elle **entre en collision** avec
l'option voiture (même code) et l'une des deux est supprimée par `remove_duplicates`. Parade : la
jambe school_bus porte des **noms d'arrêt non vides** (ex. `start_location.stop = "Arrêt car
scolaire"`, `end_location.stop = "École"`) → code distinct, aucune collision. GAMA ignore ces noms
pour le déplacement (il n'utilise que lat/lon).

**Rendu texte de l'option.** Le gabarit `travel_plan_describe_v2.j2` afficherait une jambe
`__DIRECT` unique comme un trajet direct générique (« Durée estimée : X. Distance : Y. ») — **sans
identité ni prix**. Comme aucun mode n'affiche de coût, on **n'introduit pas de champ tarif** : on
ajoute **une branche de gabarit keyée sur `leg.mode == "school_bus"`** (avant la branche `__DIRECT`)
qui imprime une phrase figée « Car scolaire liO (gratuit). Durée estimée : X. ». C'est le strict
nécessaire pour que le LLM voie l'identité et la gratuité.

### Lot D — Évolution possible (hors périmètre)
Si un GTFS de circuits réels (arrêts, horaires, jours, établissements) existait un jour, il
remplacerait le calculateur du lot A par un feed OTP, avec le même mode `school_bus` et le même
filtre d'éligibilité côté runtime (OTP proposerait sinon le circuit aux adultes). **Rien n'est
demandé à la Région** : les délais d'obtention sont trop longs. Reste une piste, non planifiée.

## Impacts sur les autres maillons
- **OSMnx / OSM** : aucun. Le car scolaire est synthétique — pas d'appel de routage, pas d'entrée
  de cache, pas de graphe sollicité. L'éligibilité et la durée n'utilisent qu'une distance à vol
  d'oiseau (haversine domicile↔école), sans graphe. Les options concurrentes (marche, vélo,
  voiture) continuent d'interroger OSMnx à l'identique.
- **OTP** : aucun appel (le calculateur du lot A ne passe pas par OTP). Un seul **couplage à
  déclarer** : le verrou d'éligibilité `home.public_transport = false` dépend des GTFS qui
  peuplent la proximité d'arrêt (aujourd'hui Tisséo seul, via `enrich_public_transport`). Quand le
  GTFS liO sera chargé (ticket 031, T2), des domiciles ruraux basculeront à `public_transport =
  true` et sortiront de l'éligibilité (ils recevront alors de vraies options OTP) : l'ensemble des
  éligibles rétrécit et se déplace. À mesurer au moment où liO arrive, pas ici.
- **`llm_agent`** : deux points, traités au lot A (mention d'abonnement — exception
  `_PT_LEG_MODES`) et au rendu (branche de gabarit keyée sur `mode == "school_bus"`). Rien
  d'autre : l'ajout d'une option dans la liste présentée au modèle est absorbé par le mélange
  anti-biais de position existant, et la clé de cache est traitée par la purge (§ Lot B).

## Ce que ce ticket ne fait pas
- Il ne modélise ni la capacité des cars ni les arrêts intermédiaires : un service porte à porte
  à horaire fixe, calibré sur les durées observées.
- **Il ne valide pas les parts modales scolaires au runtime.** Le filtre de qualité (la part de
  l'autocar par couronne / niveau / distance face à l'EMC²) est fait en **validation de
  population**, pas dans ce ticket (ancien lot C retiré).
- **Il ne traite pas l'accompagnement** (enfant passager déposé à l'école) : hors périmètre.
- Il ne distingue pas lignes régulières et circuits dédiés, que l'enquête ne sépare pas : les
  élèves qui prennent une ligne liO régulière la trouveront par OTP une fois le GTFS liO chargé.
- Il ne traite pas les TAD intercommunaux ni les navettes locales (0,02 à 0,12 % des
  déplacements, sans GTFS).

## Critères d'acceptation
1. Prérequis (ticket 031, § 1.2) livré : ≥ 88 % des 6-17 ans mobiles du vivier ont une activité
   `education`.
2. Tout persona de 5 à 17 ans hors ressort Tisséo, sur un trajet lié à son activité `education`,
   reçoit exactement une option `school_bus` à l'aller et une au retour ; aucun adulte, aucun
   domicile dans le ressort Tisséo n'en reçoit.
3. Médiane des durées synthétiques sur les éligibles de la v3 (ou v4) entre 25 et 35 min.
4. **Test de non-régression « school_bus = TC partout »** vert : le mode est classé
   `transports_collectifs` / `transit` dans les **trois tables de métriques et le pont oracle**
   (volet d'abord vu échouer contre le code actuel) et **ne reçoit aucune mention d'abonnement**
   (`_PT_LEG_MODES` non étendu). L'autocar compte en TC dans le rapport de run.
5. **Déplacement GAMA** : sur un run, un persona qui choisit le car scolaire se déplace de son
   domicile à l'école (marqueur `__DIRECT_CAR__`, interpolation point-à-point), **sans `tc_timeout`
   ni téléportation** ; l'affichage rouge est accepté (lot GAMA hors périmètre).
6. Documentation : `docs/arch/routing.md` (nouvelle option), `docs/arch/controle-population-jeu-de-test.md`
   (ligne scolaires), changelog.
