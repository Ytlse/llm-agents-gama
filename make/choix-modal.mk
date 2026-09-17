# ──────────────────────────────────────────────────────────────────────────────
# Modèle de choix modal (ticket 005)
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: zones housing-type bike-ownership terminal-time car-availability avancement policy policy-tune common-set-predict equipment-propensity
.PHONY: logit mnl-predict klr klr-predict bi-oracle forest
.PHONY: communes-couronnes audit-perimetre audit-couronnes residence-zone couronne-v7

## ──────────────────────────────────────────────────────────────────────────────
## Périmètre de population (ticket 020)
## ──────────────────────────────────────────────────────────────────────────────

## Rebuild the commune → couronne table and the couronne geometry (ticket 020, lot 3).
## Requires the restricted PROGEDO data under 'data/PROGEDO 2023/'.
## C'est la DONNÉE MANQUANTE du ticket : l'enquête découpe ses couronnes par LISTE DE
## COMMUNES (1 / 69 / 108 / 275), là où `geo_reference.residence_zone` classe par
## distance à l'hypercentre. Produit packages/mobility_core/src/mobility_core/data/commune_couronne.json et
## couronne_perimetre.geojson, tous deux versionnés.
communes-couronnes:
	@test -d "data/PROGEDO 2023" || { \
	  echo "Données PROGEDO absentes : data/PROGEDO 2023/ (accès restreint lil-1750)"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.export_commune_couronne

## Audit des neuf écarts de base entre population enquêtée et population simulée
## (ticket 020, lot 2). N'exige PAS les données PROGEDO : il lit le cadrage
## `population_emc2_2023.yaml` et les ressources versionnées de `make communes-couronnes`.
##   make audit-perimetre                                  # population et run par défaut
##   make audit-perimetre POP=data/population/x.json RUN=experiments/archive/y
##   make audit-perimetre TRACE=docs/traces/2026-08-24_perimetre_population
## Codes de sortie : 0 tout conforme, 2 au moins un axe à corriger, 3 au moins un axe
## NON MESURABLE — un axe non mesuré est un axe qui passe, et le script refuse de le taire.
## Les deux équivalences du ticket 021, lot 0 : le classement d'un domicile par PRÉFIXE de
## code de zone fine contre son classement par APPARTENANCE géométrique, et « hors couche de
## zones fines » contre « hors périmètre ». Sept portes, dont un recoupement INDÉPENDANT
## contre la trace du ticket 020. Ne modifie rien.
##   make audit-couronnes
##   make audit-couronnes POP=data/population/x.json TRACE=docs/traces/y
## Codes de sortie : 0 les portes passent, 2 une porte ÉCHOUE (le ticket est à reconcevoir),
## 3 une porte est NON MESURABLE — données SIG d'accès restreint absentes, et une porte non
## mesurée est une porte qui passe. Après le lot 1, la table versionnée remplace le SIG.
## Pose la couronne de résidence et la commune sur une population déjà générée
## (ticket 021, lot 2 — étage D). Déterministe, aucun tirage, aucun appel LLM : le trait est
## OBSERVÉ. La ressource, elle, se (re)produit par `make communes-couronnes`.
##   make residence-zone                                    # population par défaut
##   make residence-zone POP=data/population/x.json CHECK=1
##   make residence-zone POP=experiments/archive/y/population_1000.json OUT=/tmp/z.json
## ⚠ NE JAMAIS enrichir EN PLACE une population épinglée par un manifeste de jeu gelé
## (calibration_datasets/v5..v8 épinglent le sha256 de l'archive 2026-08-19_14_36) : passez
## par OUT=. Codes de sortie de CHECK : 0 portes passées, 1 ressource absente, 2 une porte
## démentie, 4 portes passées mais écart au cadrage (axe A9 — le tirage, pas ce trait).
## La cible TRADUIT le 4 en succès, en le disant : make ne sait pas distinguer un code de
## sortie informatif d'une erreur, et un « Error 4 » apprendrait à ignorer les erreurs.
residence-zone:
	@$(SYNTHESIS_PYTHON) -m scripts.data.population.enrich_residence_zone \
	  $(if $(POP),$(POP),data/population/toulouse_population_1000.json) \
	  $(if $(OUT),--out $(OUT),) $(if $(CHECK),--check,) $(if $(DRY),--dry-run,) ; \
	code=$$? ; \
	if [ $$code -eq 4 ]; then \
	  echo "→ code 4 : écart au cadrage (axe A9, le tirage) — PAS un échec de ce trait." ; \
	  exit 0 ; \
	fi ; \
	exit $$code

## Chiffre l'effet du reclassement des couronnes sur le jeu gelé `v7` (ticket 021, lot 4).
## AUCUN appel LLM : les décisions sont déjà dans le store de calibration, et la couronne
## n'entre ni dans le prompt ni dans la clé de cache — « à décisions constantes » est donc
## structurel. Splits `train` + `val` (569 agents) ; `rank` est trop petit pour un découpage
## par couronne, `test` n'a pas d'éval stockée et reste la réserve de publication.
##   make couronne-v7 TRACE=docs/traces/2026-08-24_couronne_v7
couronne-v7:
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.measure_couronne_v7 \
	  $(if $(TRACE),--trace $(TRACE),)

audit-couronnes:
	$(SYNTHESIS_PYTHON) -m scripts.data.population.audit_couronne_equivalences \
	  $(if $(POP),--population $(POP),) $(if $(TRACE),--trace $(TRACE),)

audit-perimetre:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make audit-perimetre SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.data.population.audit_perimetre \
	  $(if $(POP),--population $(POP),) $(if $(RUN),--run $(RUN),) \
	  $(if $(TRACE),--trace $(TRACE),)

.PHONY: osmnx-perimeter-graph

## Graphes OSMnx (marche, vélo, voiture) du polygone des 453 communes du périmètre d'enquête
## (ticket 031 § 1.4) : extrait des pbf OSM régionaux du fork eqasim par `osmium extract`, filtres
## réseau et vitesses de la production, cache data/cache/osmnx/graphs_<clé>.pkl sous une clé
## distincte du disque de 30 km. Aucun téléchargement. Le notebook generate_population exige ce
## graphe pour les étapes 4+5. FORCE=1 reconstruit ; TRACE=<dossier> archive les mesures.
##   make osmnx-perimeter-graph TRACE=docs/traces/$$(date +%Y-%m-%d_%H-%M)_graphe_osmnx_perimetre_453
osmnx-perimeter-graph:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; exit 1; }
	@command -v osmium >/dev/null || test -x /opt/homebrew/bin/osmium || { \
	  echo "osmium introuvable : brew install osmium-tool"; exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.data.population.build_osmnx_perimeter_graph \
	  $(if $(FORCE),--force,) $(if $(TRACE),--trace $(TRACE),)

.PHONY: synthese-representativite

## Synthèse HTML de représentativité d'une population scellée (identité visuelle de la synthèse v2,
## chiffres lus dans report.json / selection.json / MANIFEST du sceau, le contrôle du vivier et l'audit).
##   make synthese-representativite SCEAU=data/population/population_1000_AAMAS_v4 \
##        PRECEDENT=data/population/population_1000_AAMAS_v3 VIVIER=docs/traces/<d>_controle_vivier/report.json \
##        AUDIT=docs/traces/<d>_audit/audit_perimetre.json OUT=docs/traces/<d>/synthese_representativite_v3.html \
##        VELO=docs/traces/<d>/velo_cohorte.json VELO_VIVIER=docs/traces/<d>/velo_vivier.json \
##        COPIE=docs/paper/methode/population/synthese_representativite_v3_population_v4_<date>.html
## Les deux rapports vélo viennent de `enrich_personal_bike <population> --dry-run --check --rapport-json <fichier>`
## sur la cohorte scellée et sur le vivier pré-imputé (Temp/4_zone_enriched) : la pente se juge sur le vivier.
synthese-representativite:
	@test -n "$(SCEAU)" || { echo "SCEAU=<dossier scellé> obligatoire"; exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.AAMAS.synthese_representativite --sceau $(SCEAU) \
	  $(if $(PRECEDENT),--precedent $(PRECEDENT),) $(if $(VIVIER),--vivier $(VIVIER),) \
	  $(if $(AUDIT),--audit $(AUDIT),) $(if $(VELO),--velo $(VELO),) $(if $(VELO_VIVIER),--velo-vivier $(VELO_VIVIER),) \
	  --out $(if $(OUT),$(OUT),$(SCEAU)/synthese_representativite.html) \
	  $(if $(COPIE),--copie $(COPIE),)

.PHONY: synthese-generation-population

## Page « Comment la population du jeu de test est fabriquée » (eqasim, notebook, sélection, routage,
## traits, contrôle, sceau — et les résultats de chaque étage), chiffres lus dans les mêmes fichiers que la
## synthèse de représentativité plus la méta du graphe OSMnx et les mesures du graphe.
##   make synthese-generation-population SCEAU=data/population/population_1000_AAMAS_v4 \
##        VIVIER=… AUDIT=… VELO=… VELO_VIVIER=… MESURES_GRAPHE=docs/traces/<d>_mesures_graphe_perimetre_v4/mesures.json \
##        OUT=docs/traces/<d>/fabrication_population.html COPIE=docs/paper/methode/population/fabrication_population_v4_<date>.html
synthese-generation-population:
	@test -n "$(SCEAU)" || { echo "SCEAU=<dossier scellé> obligatoire"; exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.AAMAS.synthese_generation_population --sceau $(SCEAU) \
	  $(if $(VIVIER),--vivier $(VIVIER),) $(if $(AUDIT),--audit $(AUDIT),) \
	  $(if $(VELO),--velo $(VELO),) $(if $(VELO_VIVIER),--velo-vivier $(VELO_VIVIER),) \
	  $(if $(MESURES_GRAPHE),--mesures-graphe $(MESURES_GRAPHE),) \
	  --out $(if $(OUT),$(OUT),$(SCEAU)/fabrication_population.html) $(if $(COPIE),--copie $(COPIE),)

.PHONY: reference-marges control-population select-population seal-population

## Contrôle de la population du jeu de test (article AAMAS, jalon 0 du protocole).
## Compare une population synthétique aux marges de l'EMC² 2023 — classes d'âge, occupation,
## motorisation (base personne et base ménage), couronne, croisement couronne × motorisation —
## avec IC95, TOST à ± BORNE pt, χ² + V de Cramér, EMD/JSD, journal de recoupement du
## protocole et synthèse des écarts. Code 1 s'il reste un « à corriger ».
##   make control-population                                   # population par défaut
##   make control-population POP=data/population/x.json BORNE=1.0 TRACE=docs/traces/y
control-population:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make control-population SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.AAMAS.control_population \
	  $(if $(POP),$(POP),data/population/toulouse_population_1000.json) \
	  $(if $(BORNE),--borne $(BORNE),) $(if $(TRACE),--trace $(TRACE),--trace-auto) $(if $(JSON),--json $(JSON),)

## Les marges de référence, avec leur source (page du rapport ou recalcul gelé).
## RECOMPUTE=1 regèle la cible jointe couronne × motorisation depuis les microdonnées ProGEDO.
reference-marges:
	$(SYNTHESIS_PYTHON) -m scripts.AAMAS.reference_marges $(if $(RECOMPUTE),--recompute,)

## Sélection stratifiée de N personas dans un vivier (avant le routage — l'étape 3ter du
## notebook l'appelle). POOL obligatoire ; OUT défaut : <dossier du vivier>/toulouse_population_<N>_AAMAS.json
##   make select-population POOL=scripts/data/population/Temp/4_zone_enriched/toulouse_population_5000.json N=1000
select-population:
	@test -n "$(POOL)" || { echo "POOL=<vivier.json> obligatoire"; exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.AAMAS.seal_population select --pool $(POOL) \
	  --n $(if $(N),$(N),1000) \
	  --out $(if $(OUT),$(OUT),$(dir $(POOL))toulouse_population_$(if $(N),$(N),1000)_AAMAS.json)

## Scellement : contrôle puis copie dans un dossier immuable avec MANIFEST.yaml et CONTROLE.md.
## REFUSE si une marge est « à corriger ». POP obligatoire ; OUT_DIR défaut : data/population/population_1000_AAMAS_v4
## (règle de sélection v4 : ménages entiers + six classes d'âge + périmètre des 453 communes,
## ticket 031 ; les dossiers v2 et v3 restent intacts)
##   make seal-population POP=data/population/toulouse_population_1000_AAMAS.json \
##        SELECTION=scripts/data/population/Temp/4_zone_enriched/toulouse_population_1000_AAMAS_selection.json
seal-population:
	@test -n "$(POP)" || { echo "POP=<population.json> obligatoire"; exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.AAMAS.seal_population seal --population $(POP) \
	  $(if $(OUT_DIR),--out-dir $(OUT_DIR),) $(if $(N),--n $(N),) \
	  $(if $(SELECTION),--selection-json $(SELECTION),) $(if $(BORNE),--borne $(BORNE),) \
	  $(if $(NOTE),--note "$(NOTE)",)

.PHONY: gtfs-year gtfs-year-dry gtfs-year-holdout gtfs-window test-gtfs-year

## Reconstruit un feed GTFS couvrant l'année entière à partir des exports partiels
## de l'opérateur. Chaque journée porte soit l'offre réelle publiée, soit la copie
## verbatim d'une journée réelle de même signature (jour de semaine × période
## scolaire zone C) ; aucun horaire n'est synthétisé, et la provenance de chaque
## jour est tracée sous docs/traces/<date>_gtfs_annee/.
##   make gtfs-year                              # Tisséo + TER, 2026 et 2027
##   make gtfs-year RESEAU=tisseo ANNEES="2026"
## Codes de sortie : 0 tout tenu, 1 ressource absente, 2 invariant démenti
## (le feed ne doit PAS être publié), 4 construit mais confiance dégradée.
## La cible TRADUIT le 4 en succès, en le disant : un feed annuel bâti sur six
## mois d'exports comporte forcément des journées extrapolées de loin, et un
## « Error 4 » apprendrait à ignorer les erreurs.
gtfs-year:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make gtfs-year SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	@$(SYNTHESIS_PYTHON) -m scripts.data.gtfs_year.build_year_feed \
	  $(foreach r,$(RESEAU),--reseau $(r)) \
	  $(foreach a,$(ANNEES),--annee $(a)) \
	  $(if $(SORTIE),--sortie $(SORTIE),) $(if $(TRACE),--trace $(TRACE),) \
	  $(if $(DRY),--dry-run,) $(if $(HOLDOUT),--holdout $(HOLDOUT),) \
	  $(if $(REFRESH),--rafraichir-calendrier,) ; \
	code=$$? ; \
	if [ $$code -eq 4 ]; then \
	  echo "→ code 4 : feed construit, mais des journées sont extrapolées sans donneur de même nature." ; \
	  echo "  Lisez docs/traces/*_gtfs_annee/provenance_*.csv avant de publier." ; \
	  exit 0 ; \
	fi ; \
	exit $$code

## Planifie sans rien écrire : quelles journées sont réelles, lesquelles seraient
## copiées et depuis quand. À lancer avant tout build après réception d'exports.
gtfs-year-dry:
	@$(MAKE) gtfs-year DRY=1

## Masque un mois réel et mesure l'écart entre l'offre extrapolée et l'offre
## réellement publiée ce mois-là. C'est la seule preuve que le modèle
## d'extrapolation vaut quelque chose. Mesure de référence sur mai 2026 : écart
## maximal 5,3 %, médiane sous 1 %.
##   make gtfs-year-holdout HOLDOUT=202605
gtfs-year-holdout:
	@$(MAKE) gtfs-year RESEAU=tisseo ANNEES=2026 HOLDOUT=$(if $(HOLDOUT),$(HOLDOUT),202605) \
	  SORTIE=/tmp/gtfs_year_holdout

## Extrait du feed annuel la fenêtre que consomment GAMA et le runtime. OTP lit
## l'année entière, GAMA non : son calendrier est un masque binaire 64 bits
## (services/llm-agents/inputs/gtfs/gama.py, PublicTransport.gaml). La fenêtre DOIT
## contenir la date de simulation, sinon plus aucune course n'est planifiée.
##   make gtfs-window START=2026-03-16 DAYS=64
gtfs-window:
	@$(SYNTHESIS_PYTHON) -m scripts.data.gtfs_year.window_feed \
	  --source $(if $(SOURCE),$(SOURCE),data/gtfs_year/tisseo_2026) \
	  --debut $(if $(START),$(START),2026-03-16) \
	  --jours $(if $(DAYS),$(DAYS),64) \
	  --sortie $(if $(OUT),$(OUT),data/gtfs_year/fenetre_gama) --zip

## Tests unitaires du pipeline de feed annuel. Feeds synthétiques, aucun accès
## réseau, moins d'une seconde. Chaque test porte sur une décision qui, prise à
## l'envers, produit un feed plausible mais faux.
test-gtfs-year:
	@$(SYNTHESIS_PYTHON) -m pytest scripts/tests/test_gtfs_year.py -q

.PHONY: gama-layers gama-trip-info test-gama-includes

## Reconstruit les COUCHES que GAMA dessine — services/GAMA/CityTransport/includes/routes.shp
## et stops.shp — à partir des trois réseaux du périmètre (Tisséo, TER, liO). Les
## couches précédentes sont déplacées dans un dossier archives_<date>, jamais
## supprimées. `includes/` n'est pas versionné : cette recette est la seule trace.
##   make gama-layers
##   make gama-layers FEEDS="tisseo=data/gtfs/tisseo_gtfs ter=data/gtfs/ter_gtfs"
gama-layers:
	@$(SYNTHESIS_PYTHON) scripts/data/gama/export_gtfs_layers.py \
	  $(foreach f,$(FEEDS),--feed $(f)) \
	  $(if $(OUT),--sortie $(OUT),) $(if $(TOUT),--tout,) $(if $(JSON),--json $(JSON),)

## Reconstruit les COURSES que GAMA fait rouler — services/GAMA/CityTransport/includes/trip_info.json —
## à partir des trois réseaux et de la date simulée (lue dans Settings.gaml), PUIS la table
## des tracés que lit le runtime (includes/shape_lookup.json).
##
## La table publie la correspondance route_id -> shape_id -> ordre des arrêts que la recette
## a RÉELLEMENT utilisée : c'est elle qui permet à un agent de monter dans un véhicule
## (get_shape_id_from_route_info, puis `shape_id_list contains each.shape_id` côté GAMA).
## Le runtime ne la recalcule pas — le TER ne publie aucune géométrie, ses shape_id sont
## fabriqués ici, et la recette écarte des courses qu'il faudrait sinon réécarter à
## l'identique. Elle note l'empreinte de routes.shp/.dbf et de trip_info.json : refaire
## les couches SEULES la dépareille, et le runtime l'alarme au chargement.
##
## Les couches sont refaites D'ABORD, dans la même recette : `trip_info.json` porte des
## indices de sommets dans la géométrie de `routes.shp`, et produire l'un sans l'autre est
## exactement le défaut qui a duré cinq mois — couches à trois réseaux, courses à un seul,
## 34 lignes de TER dessinées où aucun train ne roulait. `COUCHES=0` saute cette étape
## quand les couches viennent d'être faites.
##
## Contrôles bloquants (le fichier n'est pas écrit s'ils tombent) : la date simulée est
## dans la fenêtre ET servie ; l'étendue des dates tient dans le masque binaire 64 bits de
## GAMA ; chaque course a son tracé dans routes.shp avec le même nombre de points ; aucun
## route_type de la couche n'est sans course le jour simulé.
##   make gama-trip-info
##   make gama-trip-info DATE=2026-03-16 DAYS=64 COUCHES=0
##   make gama-trip-info TABLE=/tmp/shape_lookup.json     # table ailleurs qu'à côté des courses
## Codes de sortie : 0 écrit, 1 ressource absente, 2 invariant démenti.
gama-trip-info:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make gama-trip-info SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	@if [ "$(COUCHES)" != "0" ]; then $(MAKE) --no-print-directory gama-layers ; fi
	@$(SYNTHESIS_PYTHON) scripts/data/gama/export_trip_info.py \
	  $(foreach f,$(FEEDS),--feed $(f)) \
	  $(if $(DATE),--date-simulee $(DATE),) $(if $(START),--debut $(START),) \
	  $(if $(DAYS),--jours $(DAYS),) $(if $(ROUTES),--routes $(ROUTES),) \
	  $(if $(OUT),--sortie $(OUT),) $(if $(TABLE),--table-traces $(TABLE),) \
	  $(if $(JSON),--json $(JSON),)

## Tests unitaires des deux recettes ci-dessus, dont le contrôle de cohérence
## couches/courses et la table des tracés publiée : feeds synthétiques minimaux, aucun
## gros fichier, aucun accès réseau.
test-gama-includes:
	@$(SYNTHESIS_PYTHON) -m pytest scripts/tests/test_gama_includes.py -q

## Rebuild the fine-zone resource read by mobility_core.zone_resolver.
## Requires the restricted PROGEDO data under 'data/PROGEDO 2023/'.
zones:
	@test -d "data/PROGEDO 2023" || { \
	  echo "Données PROGEDO absentes : data/PROGEDO 2023/ (accès restreint lil-1750)"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.export_zone_layer

## Rebuild the housing-type law read when enriching a synthetic population (action A2).
## Requires the restricted PROGEDO data under 'data/PROGEDO 2023/'.
## Ticket 019 : la loi est conditionnée à la ZONE FINE et à la TAILLE DU MÉNAGE, et la
## ressource produite est en v2 — le module refuse une v1. L'export publie le test interne
## EMC² et ÉCHOUE si l'erreur du mécanisme dépasse 1 point sur les 20 cellules.
## Puis, pour poser le trait sur une population (aucun appel LLM, déterministe) :
##   $(VENV_PYTHON) -m scripts.data.population.enrich_housing_type \
##     data/population/toulouse_population_1000.json --check
## Codes de sortie de --check : 0 tout est dans la tolérance, 1 ressource absente,
## 2 une cible servie est démentie, 3 population enrichie mais trop petite pour trancher.
housing-type:
	@test -d "data/PROGEDO 2023" || { \
	  echo "Données PROGEDO absentes : data/PROGEDO 2023/ (accès restreint lil-1750)"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.export_housing_type

## Rebuild the bike-ownership model read when enriching a synthetic population
## (ticket 015 : les trois étages k / attribution / VAE appris sur EMC²).
## Requires the restricted PROGEDO data under 'data/PROGEDO 2023/'.
## Il lit aussi la table du type de logement (make housing-type) pour publier la cible
## d'équipement par habitat DILUÉE — la seule opposable à une population synthétique.
## Puis, pour poser le trait sur une population (aucun appel LLM, déterministe) :
##   $(VENV_PYTHON) -m scripts.data.population.enrich_personal_bike \
##     data/population/toulouse_population_1000.json --check
bike-ownership:
	@test -d "data/PROGEDO 2023" || { \
	  echo "Données PROGEDO absentes : data/PROGEDO 2023/ (accès restreint lil-1750)"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.export_bike_ownership

## Rebuild the two equipment-propensity laws read when enriching a population:
## `has_pt_subscription` (ticket 016) and `has_driving_license` (ticket 017).
## Lot 1 commun aux deux tickets : un seul chargeur, deux cibles apprises sur le
## fichier standard `pers` d'EMC² (PENQ = 1, pondération COEP), validation croisée
## GROUPÉE PAR MÉNAGE. Les paliers tarifaires (moins de 26 ans, ouverture senior)
## sont ajustés puis ARBITRÉS sur l'AUC hors-échantillon, pas décrétés.
## Requires the restricted PROGEDO data under 'data/PROGEDO 2023/'.
##   make equipment-propensity DRY_RUN=1   # ajuste et affiche la recette, sans écrire
equipment-propensity:
	@test -d "data/PROGEDO 2023" || { \
	  echo "Données PROGEDO absentes : data/PROGEDO 2023/ (accès restreint lil-1750)"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.export_equipment_propensity \
	  $(if $(DRY_RUN),--dry-run,)

## Rebuild the EMC²-measured car terminal time (access + parking search) law.
## Requires the restricted PROGEDO data under 'data/PROGEDO 2023/'.
## Ce que ça mesure : T2 (marche au départ), T6 (marche à l'arrivée) et T11 (durée de
## recherche du stationnement) du fichier trajets, par couronne. À comparer aux valeurs
## de services/llm-agents/config/terminal_time.yaml, mesurées 8x à 24x plus grandes.
terminal-time:
	@test -d "data/PROGEDO 2023" || { \
	  echo "Données PROGEDO absentes : data/PROGEDO 2023/ (accès restreint lil-1750)"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.export_terminal_time

## Rebuild the "Avancement et résultats" page from the measurement registry.
## Une ligne par mesure FAITE : base de référence → base modifiée → modification → résultat
## → score, chacune retraçable jusqu'à une archive de docs/traces/.
## Le rendu REFUSE (et n'écrit rien) si une trace citée n'existe pas sur le disque, si un
## champ manque ou si un verdict sort du vocabulaire : une page de résultats qui se dégrade
## en silence est pire qu'une page absente. `make avancement CHECK=1` valide sans écrire.
avancement:
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.render_avancement $(if $(CHECK),--check,)

.PHONY: ab-detail
## Détail par sous-catégorie d'un A/B de jeux gelés — un mini-graphe par mode, une
## courbe par bras, plus les tableaux L1. Reconstruit depuis les décisions DÉJÀ dans le
## store : aucun appel LLM. Usage: make ab-detail [DATASET=val|screen]
ab-detail:
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.build_ab_detail --dataset $(if $(DATASET),$(DATASET),val)
	$(if $(DATASET),,$(SYNTHESIS_PYTHON) -m scripts.synthesis.build_ab_detail --dataset screen)

## Rebuild the EMC²-measured household car availability reference (ticket 018).
## Requires the restricted PROGEDO data under 'data/PROGEDO 2023/'.
## Ce que ça mesure : `car_availability` (all / some / none) recalculée avec LA RÈGLE
## D'EQASIM — all si voitures >= permis des majeurs, some si <, none si voitures == 0 —
## depuis M6 (voitures) et P7 (permis). Deux pondérations : ménages (COE0) et personnes
## (COE1), cette dernière étant celle opposable à une population d'agents.
## L'export ÉCHOUE si son contrôle positif ne reproduit pas la motorisation publiée
## (1,25 VP/ménage ; 19 / 45 / 35 %) : une lecture qui rate le parc ne peut pas prétendre
## mesurer sa disponibilité.
car-availability:
	@test -d "data/PROGEDO 2023" || { \
	  echo "Données PROGEDO absentes : data/PROGEDO 2023/ (accès restreint lil-1750)"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.export_car_availability

## Retrain the PROGEDO mode-choice policy → scripts/progedo_logit/mode_choice_policy.json
## Le parquet d'entraînement est versionné : contrairement à `zones`, cette cible
## n'exige PAS les données PROGEDO brutes. Résultat déterministe (graine fixée).
policy:
	@test -f scripts/progedo_logit/progedo_mode_choice_v2.parquet || { \
	  echo "Jeu d'entraînement absent : scripts/progedo_logit/progedo_mode_choice_v2.parquet"; \
	  echo "Il est versionné ; s'il manque, régénérez-le avec build_mode_choice_dataset.py"; \
	  echo "(qui exige, lui, les données PROGEDO d'accès restreint)."; \
	  exit 1; }
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make policy SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.fit_mode_choice_policy

## Tune the mode-choice booster's hyperparameters → scripts/progedo_logit/mode_choice_tuning.json
## Validation croisée groupée PAR MÉNAGE, entièrement À L'INTÉRIEUR du train : le split
## test n'est jamais lu. N'écrit aucun modèle — le gagnant se reporte à la main dans
## PARAMS de fit_mode_choice_policy.py, puis `make policy`.
##   make policy-tune TUNE_ARGS="--refine --trials 40"   # espace resserré (2e passe)
policy-tune:
	@test -f scripts/progedo_logit/progedo_mode_choice_v2.parquet || { \
	  echo "Jeu d'entraînement absent : scripts/progedo_logit/progedo_mode_choice_v2.parquet"; \
	  exit 1; }
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make policy-tune SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.tune_mode_choice_policy $(TUNE_ARGS)

## Apply the trained policy to the pinned common set, renormalised on the OTP offer
## (action A8) → scripts/synthesis/data/progedo_on_common_set.parquet
## Aucun appel LLM, aucun réseau, graine sans objet : le résultat est déterministe.
## Exige la couche de zones (`make zones`) pour les six variables géographiques.
##   make common-set-predict DRY_RUN=1   # périmètre et statuts, sans écrire
common-set-predict:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make common-set-predict SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.model_on_common_set \
	  $(if $(DRY_RUN),--dry-run,) $(if $(POLICY),--policy $(POLICY),) $(if $(OUT),--out $(OUT),)

## Estimate the SECOND oracle: multinomial logit at strict parity (21 variables)
## → scripts/progedo_logit/mnl_model.json + mnl_model_metrics.json
## Même jeu, même split par ménage, même sample_weight et mêmes métriques que
## `make policy` : la comparaison des deux oracles ne mesure que les deux modèles.
## La régularisation est choisie en validation croisée groupée DANS le train.
##   make logit C=1.0        # impose C au lieu de le choisir (diagnostic)
logit:
	@test -f scripts/progedo_logit/progedo_mode_choice_v2.parquet || { \
	  echo "Jeu d'entraînement absent : scripts/progedo_logit/progedo_mode_choice_v2.parquet"; \
	  echo "Il est versionné ; s'il manque, régénérez-le avec build_mode_choice_dataset.py"; \
	  exit 1; }
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make logit SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.fit_mode_choice_logit $(if $(C),--C $(C),)

## Random-forest WITNESS: does the booster's edge come from the trees or the boosting?
## → scripts/progedo_logit/rf_mode_choice_metrics.json (mesures seules, AUCUN modèle)
## Mêmes parquet, split par ménage, sample_weight COEP et métriques que `make policy` et
## `make logit`. Réglage en validation croisée groupée DANS le train ; ni class_weight ni
## rééquilibrage. Verdict à seuil déclaré d'avance : part de l'écart booster–logit comblée,
## ≥ 0,70 → les arbres, ≤ 0,30 → le boosting. Hors ligne, ~20 min.
## Prérequis pour le verdict : make policy && make logit (sinon « non mesuré »)
##   make forest FOREST_ARGS="--encodage dessin"   # sans la voie de sensibilité
##   make forest FOREST_ARGS="--rapide"            # passe de fumée, chiffres non publiables
forest:
	@test -f scripts/progedo_logit/progedo_mode_choice_v2.parquet || { \
	  echo "Jeu d'entraînement absent : scripts/progedo_logit/progedo_mode_choice_v2.parquet"; \
	  echo "Il est versionné ; s'il manque, régénérez-le avec build_mode_choice_dataset.py"; \
	  exit 1; }
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make forest SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.fit_mode_choice_forest $(FOREST_ARGS)

## Apply the SECOND oracle to the pinned common set (same code path as the booster)
## → scripts/synthesis/data/mnl_on_common_set.parquet
mnl-predict:
	@$(MAKE) --no-print-directory common-set-predict \
	  POLICY=scripts/progedo_logit/mnl_model.json \
	  OUT=scripts/synthesis/data/mnl_on_common_set.parquet

## Estimate the THIRD family: kernel logistic regression (RBF + Nyström, strict parity)
## → scripts/progedo_logit/klr_model.json + klr_model_metrics.json
## Même jeu, même split par ménage, même sample_weight, MÊME matrice de dessin que
## `make logit` et mêmes métriques : la comparaison des trois familles ne mesure que les
## trois modèles. γ, λ et m sont choisis en validation croisée groupée DANS le train, et
## une configuration qui dérive sur les parts modales est écartée avant tout classement.
## Hors ligne, déterministe (graine fixe), ~20 min pour le banc complet.
##   make klr KLR_ARGS="--gamma 0.0418 --C 1 --m 1000"   # réglage imposé, sans banc
##   make klr KLR_ARGS="--m-grid 500 1000"               # banc raccourci
klr:
	@test -f scripts/progedo_logit/progedo_mode_choice_v2.parquet || { \
	  echo "Jeu d'entraînement absent : scripts/progedo_logit/progedo_mode_choice_v2.parquet"; \
	  echo "Il est versionné ; s'il manque, régénérez-le avec build_mode_choice_dataset.py"; \
	  exit 1; }
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make klr SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.fit_mode_choice_klr $(KLR_ARGS)

## Apply the THIRD family to the pinned common set (same code path as the two others)
## → scripts/synthesis/data/klr_on_common_set.parquet
klr-predict:
	@$(MAKE) --no-print-directory common-set-predict \
	  POLICY=scripts/progedo_logit/klr_model.json \
	  OUT=scripts/synthesis/data/klr_on_common_set.parquet

## Two-oracle composite score → scripts/synthesis/data/bi_oracle.json
## Bloc A fidélité EMC² (inchangé), bloc B accord désagrégé au logit rapporté à la
## distance inter-oracles, bloc C sens de variation. Poids B et C à 0 : les termes sont
## publiés, ils ne sélectionnent aucun prompt. Aucun appel LLM, aucun réseau.
## Bloc C à DEUX arbitres si le parquet KLR est là (make klr && make klr-predict) : une
## transition où logit et KLR divergent sort du score au lieu d'être imputée au prompt.
## Prérequis : make logit && make common-set-predict && make mnl-predict
##             (+ make klr && make klr-predict pour le second arbitre)
bi-oracle:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make bi-oracle SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.bi_oracle
