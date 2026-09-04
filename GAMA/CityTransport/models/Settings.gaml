/**
* Name: MapData
* Based on the internal empty template. 
* Author: dung
* Tags: 
*/


model Settings

global {
	// feature toggle
	bool ft_public_transport_eval <- false;
	bool ft_evaluate_modality_choices <- false;
	
	string diff_arrival_time_file -> "../results/diff_arrival_time.csv";
	string evaluate_modality_choices_file -> "../results/evaluate_modality_choices.csv";
	string evaluate_density_file -> "../results/evaluate_density.csv";
	
	int LLMAGENT_QUERY_MOVE_BATCH_SIZE <- 200;
	
	// TODO: uncomment this line to enable fixed_date GTFS lookup 
//	 date GTFS_FIXED_DATE <- date([2025,3,5,0,0,0]);
	date GTFS_FIXED_DATE <- nil;
	
	// config
	date starting_date <- date([2026,3,16,5,0,0]); // Lundi 5h
	
	// Global helper variables
	date UTC_START_DATE <- date([1970,1,1,0,0,0]);
	// Contre-pression prédictive (ticket 003) : état poussé par Python via le topic
	// system/throttle. Permet d'afficher le régime dégradé dans l'UI de l'expérience.
	bool THROTTLE_ACTIVE <- false;      // true = simulation bridée par le contrôle prédictif
	float LLM_RATE_PER_MIN <- 0.0;      // débit de complétion LLM+OTP réel (tâches/min)
	float SIM_RATIO_PYTHON <- 0.0;      // vitesse de simulation vue par Python (s sim / s réel)

	int CURRENT_TIMESTAMP -> int(current_date - UTC_START_DATE);
	int SECONDS_IN_24H <- 24*3600;
	int CURRENT_TIMESTAMP_24H -> (int(current_date - UTC_START_DATE)) mod SECONDS_IN_24H;
	
	// Variables helpers pour l'affichage (Jour de la semaine et temps écoulé)
	map<int, string> DAYS_OF_WEEK <- [1::"Lundi", 2::"Mardi", 3::"Mercredi", 4::"Jeudi", 5::"Vendredi", 6::"Samedi", 7::"Dimanche"];
	string current_day_name -> DAYS_OF_WEEK[current_date.day_of_week]; // day_of_week va de 1 (Lundi) à 7 (Dimanche)
	
	int elapsed_seconds -> int(current_date - starting_date);
	int elapsed_days -> elapsed_seconds div SECONDS_IN_24H;
	int elapsed_hours -> (elapsed_seconds mod SECONDS_IN_24H) div 3600;
	int elapsed_minutes -> (elapsed_seconds mod 3600) div 60;
	
	// Chaîne formatée prête à être affichée (ex: "Lundi | Écoulé : 2j 4h 30m")
	string display_time_info -> current_day_name + " " + current_date+ " | Écoulé : " + (elapsed_days > 0 ? string(elapsed_days) + "j " : "") + string(elapsed_hours) + "h " + string(elapsed_minutes) + "m";

	// Shape
	// Monde = enveloppe du POLYGONE des 453 communes de l'enquête EMC² 2023 (ticket 031, G1),
	// exporté par scripts/data/gama/export_perimetre_shapefile.py (WGS84, comme routes.shp).
	// Avant le 2026-09-03 : envelope(routes0_shape_file), l'emprise des lignes Tisséo — 163 domiciles
	// de la population en étaient dehors (rapport de périmètre). Ce fichier est chargé le PREMIER :
	// c'est lui qui fixe la projection interne de GAMA (WGS84 → UTM, comme routes.shp avant lui).
	file perimetre_shape_file <- shape_file("../includes/perimetre_453.shp");
	file routes0_shape_file <- shape_file("../includes/routes.shp");
	//file shape_file_buildings <- file("../includes/building.shp");
	file stops0_shape_file <- shape_file("../includes/stops.shp");
	file trip_info_file <- json_file("../includes/trip_info.json");
	map<string, unknown> TRIP_INFO <- trip_info_file.contents;
	list<map<string, unknown>> TRIP_LIST <- TRIP_INFO["trip_list"];

	geometry shape <- envelope(perimetre_shape_file);
	// Emprise des lignes TC (Tisséo), pour l'avertissement de couverture au chargement.
	geometry ROUTES_ENVELOPE <- envelope(routes0_shape_file);
	
	// Nom lisible de chaque `route_type` GTFS servi par les couches. Aligné sur
	// `settings.gtfs.gtfs_modality_name_map` (llm-agents/settings.py), qui est ce que le
	// prompt de l'agent lit : deux libellés différents pour un même type rendraient le
	// journal de GAMA et celui du prompt incomparables.
	map<float, string> ROUTE_TYPE_NAME <- [
		0::"T1/Tram",
		1::"Metro",
		2::"Train",   // TER (SNCF Voyageurs), entré dans les couches le 2026-09-04
		3::"Bus",     // Tisséo urbain ET autocars liO
		6::"Teleo"
	];

	// ⚠ Les deux tables ci-dessous sont indexées par le `route_type` GTFS. Une clé
	// ABSENTE ne lève rien : la largeur devient nil (tracé sans épaisseur) et la capacité
	// devient nil, donc `is_full` est vrai dès le premier passager — un véhicule où
	// personne ne peut monter, sans un mot dans le journal. Le garde-fou qui recense les
	// types réellement présents dans les couches vit dans `PublicTransport.gaml`
	// (`recenser_les_route_types`) : c'est lui le correctif de fond, les clés ne sont que
	// le cas du jour.
	map<float, float> ROUTE_DISPLAY_WIDTH <- [
		0::20, // T1:
		1::30, // Metro A, B
		2::25, // TER — choix d'affichage : entre le tram et le métro. Les 266 tracés du
		       // TER traversent tout le périmètre (86 km de large) ; plus fin, un axe
		       // régional disparaît à l'échelle du monde. (266 et non 34 depuis le
		       // 2026-09-04 : un tracé par desserte, cf. scripts/data/gama/gtfs_traces.py.
		       // Ils se superposent sur les mêmes corridors, l'affichage ne change pas.)
		3::3, // Bus
		6::8 // Teleo
	];

	map<float, int> VEHICLE_MAX_CAPACITY <- [
		0::200,
		1::200,
		// TER — ORDRE DE GRANDEUR, pas une mesure : le GTFS ne publie aucune capacité, et
		// une rame n'est pas un bus. Le matériel réellement engagé en Occitanie encadre la
		// valeur : Régiolis type M à quatre caisses, aménagement périurbain, monoclasse,
		// **206 places assises dont 46 strapontins** (Rail Passion, « L'Occitanie commande
		// de nouveaux Régiolis ») ; Regio 2N, **jusqu'à 500 places dont 343 assises**
		// (Région Occitanie, laregion.fr/Les-nouvelles-rames-TER). 300 se tient entre les
		// deux familles, places debout comprises — comme les autres entrées de cette table,
		// qui comptent l'assis ET le debout (100 pour un bus articulé).
		2::300,
		3::100,
		6::1500
	];

	map<string, string> PURPOSE_ICON_MAP <- [
		"home"::"🏠",
		"work"::"🏢",
		"education"::"🏢",
		"shop"::"🛒",
		"leisure"::"🎵",
		"other"::"",
		"__MOVING__"::"🚌",
		"__WALKING__"::"🚶",
		"__BIKE__"::"🚲",
		"__DRIVING__"::"🚗"
	];
	
//	string POPULATION_CRS <- "EPSG:2154";
	string POPULATION_CRS <- "EPSG:4326";

	// Config persistence — reloads simulation parameters across GAMA sessions
	string SIM_CONFIG_PATH <- "../config/sim_params.yaml";
	list<string> _cfg_lines <- file_exists(SIM_CONFIG_PATH) ? list<string>(text_file(SIM_CONFIG_PATH).contents) : list<string>([]);
	string _cfg_pop <- first(_cfg_lines where (each index_of "population_size:" = 0));
	string _cfg_llm  <- first(_cfg_lines where (each index_of "part_of_llm_based_agents:" = 0));
	string _cfg_ltm  <- first(_cfg_lines where (each index_of "long_term_memory_enabled:" = 0));
	string _cfg_ltsr <- first(_cfg_lines where (each index_of "long_term_self_reflect_enabled:" = 0));
	string _cfg_days <- first(_cfg_lines where (each index_of "simulation_max_days:" = 0));

	int population_size <- 100;
	float part_of_llm_based_agents <- 1.0;
	bool long_term_memory_enabled <- true;
	bool long_term_self_reflect_enabled <- true;
	int simulation_max_days <- 7;

	// Nombre de cycles (itérations de la boucle) pour la calibration du prompt,
	// lancée à la demande depuis l'IHM (bouton "Lancer la calibration du prompt").
	int calibration_cycles <- 20;

	action save_sim_config {
		write "Save config";
		if (population_size>0){
			string content <- "population_size: " + string(population_size) + "\n"
				+ "part_of_llm_based_agents: " + string(part_of_llm_based_agents) + "\n"
				+ "long_term_memory_enabled: " + string(long_term_memory_enabled) + "\n"
				+ "long_term_self_reflect_enabled: " + string(long_term_self_reflect_enabled) + "\n"
				+ "simulation_max_days: " + string(simulation_max_days);
			save content to: SIM_CONFIG_PATH format: "text" rewrite: true;
		}
	}

	action load_sim_config {
		// Simulation scenario parameters — sent to the Python controller at /init
		write "Load config";
		population_size <- (_cfg_pop != nil) ? int((_cfg_pop split_with ":")[1]) : 0;
		part_of_llm_based_agents <- (_cfg_llm != nil) ? float(string((_cfg_llm split_with ":")[1]) replace(" ", "")) : 1.0;
		long_term_memory_enabled <- (_cfg_ltm != nil) ? ((_cfg_ltm split_with ":")[1] contains "true") : false;
		long_term_self_reflect_enabled <- (_cfg_ltsr != nil) ? (string((_cfg_ltsr split_with ":")[1]) contains "true") : false;
		simulation_max_days <- (_cfg_days != nil) ? int(string((_cfg_days split_with ":")[1]) replace(" ", "")) : 7;
	}

	reflex auto_save_sim_config when: cycle = 2 {
		do save_sim_config;
	}
	
	init {
		do load_sim_config;
		// Couverture du monde par le réseau TC (ticket 031, G1). Attendu depuis le passage au
		// polygone des 453 communes : Tisséo ne dessert pas la 3ᵉ couronne, ses lignes ne couvrent
		// pas le monde — l'avertissement dit de combien, pour qu'on ne le découvre pas agent par agent.
		if (!(ROUTES_ENVELOPE covers shape)) {
			float part_couverte <- shape.area > 0 ? (shape inter ROUTES_ENVELOPE).area / shape.area : 0.0;
			write "[PERIMETRE] Monde = enveloppe du périmètre des 453 communes (" + int(shape.width / 1000) + " x " + int(shape.height / 1000) + " km) ; les lignes TC (routes.shp) n'en couvrent que " + int(part_couverte * 100) + " % — les agents hors de leur emprise n'ont pas de transport collectif Tisséo.";
		} else {
			write "[PERIMETRE] Monde = enveloppe du périmètre des 453 communes, entièrement couvert par les lignes TC.";
		}
	}

}

