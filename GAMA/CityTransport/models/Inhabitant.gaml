/**
* Nom: Personnes (Habitants)
* Basé sur le modèle vide interne.
* Auteur: dung
* Tags: agents, mobilité, transport, passagers
*
* Description: Agents humains (habitants) qui se déplacent dans la ville en utilisant les transports en commun.
* Ce modèle définit le comportement des personnes naviguant dans le système de transport urbain,
* incluant la marche, l'attente des véhicules, les trajets en transport, et la planification d'activités.
* Supporte à la fois les agents réguliers et les agents intelligents alimentés par LLM.
*/


model People

// Import du système de transport public pour les interactions avec les véhicules
import "PublicTransport.gaml"


global {
    // Paramètres d'affichage pour les habitants
    float inhabitant_display_size <- 20.0;           // Taille d'affichage des habitants
    bool show_inhabitants <- true;                   // Afficher les habitants
    int show_inhabitants_label_density <- 1;       // Pourcentage d'agents affichant les labels

    // Registre global de tous les habitants pour recherche rapide
    map<string, inhabitant> INHABITANT_MAP <- [];
}


/* Insert your model definition here */

/**
 * Espèce de base pour les agents qui peuvent se déplacer dans la ville.
 * Fournit les capacités de mouvement fondamentales et le suivi de distance.
 * Espèce virtuelle - sert de parent pour les agents mobiles concrets.
 */
species in_transfer skills: [moving] virtual: true {
    // État de mouvement
    point moving_target;                    // Destination de mouvement actuelle
    bool is_stop_moving -> moving_target = nil;  // Vrai quand ne bouge pas

    // Suivi de distance pour les métriques
    float last_dist_traveled <- 0.0;       // Distance totale parcourue dans le segment actuel

    // Paramètres de mouvement
    float speed <- 2#m/#s;                 // Vitesse de marche (2 m/s)
    float moving_close_dist <- 15#m;       // Seuil de distance pour considérer la destination atteinte

    /**
     * Réflexe de mouvement continu - déplace l'agent vers la cible
     */
    reflex moving_update when: !is_stop_moving {
        // TODO: se déplacer le long des routes extraites des données OSM
        do goto target: moving_target speed: speed;
        last_dist_traveled <- last_dist_traveled + real_speed * step;
        
        // Vérifier si la destination est atteinte
        if (location distance_to moving_target < moving_close_dist) {
            location <- moving_target;
            moving_target <- nil;
        }
    }

    /**
     * Réinitialiser les métriques de distance parcourue
     */
    action metrics_reset_dist_traveled {
        last_dist_traveled <- 0.0;
    }
}

/**
 * Espèce Passager - agents qui utilisent les transports en commun.
 * Étend in_transfer avec la planification de trajet, l'embarquement/débarquement des véhicules,
 * et la gestion des voyages multimodaux.
 * Espèce virtuelle - sert de parent pour les implémentations concrètes de passagers.
 */
species passenger parent: in_transfer virtual: true {
    // État d'activité
    bool is_ready <- false;               // Vrai quand l'agent a un plan de trajet actif
    bool is_active <- false;               // Vrai quand l'agent se déplace

    // Cache de recherche rapide pour les véhicules de route
    map<string, list<public_vehicle>> route_vehicle_map;

    // Paramètres de planification de trajet
    string moving_id;                      // Identifiant unique du trajet
    string activity_id;                    // Identifiant d'activité associé
    string purpose;                        // But du trajet (travail, domicile, loisirs, etc.)
    int expected_arrive_at;               // Horodatage d'arrivée prévu
    int schedule_at;                       // Horodatage de départ prévu
    map<string, unknown> raw_trip;         // Données brutes du trajet du système de planification
    string moving_description;             // Description lisible du trajet
    point target_location -> length(list_destination) > 0 ? list_destination[length(list_destination)-1]: nil;

    // Constantes de route
    string _WALK_ <- "__DIRECT_FOOT__";           // Marqueur pour les segments de marche
    string _CAR_  <- "__DIRECT_CAR__";      // Marqueur pour les segments en voiture
    string _BIKE_  <- "__DIRECT_BICYCLE__";          // Marqueur pour les segments en vélo
    string _PUBLIC_  <- "__PUBLIC__";      // Marqueur pour transport public

    // État d'interaction avec les véhicules
    public_vehicle on_vehicle;             // Véhicule actuellement embarqué (nil si marche)
    float get_in_vehicle_dist <- 25#m;     // Seuil de distance pour embarquer dans les véhicules
    int step_idx <- 0;                     // Étape actuelle dans le plan de voyage

    // Structures de données du plan de voyage
    list<point> list_destination <- [];                    // Destinations géographiques
    list<string> list_destination_stop_name <- [];         // Noms d'arrêts pour chaque destination
    list<string> list_route_id <- [];                      // IDs de route (ou _ROUTE_NONE_ pour marche)
    list<list<string>> list_shape_id <- [];                // IDs de forme pour les segments de transport
    list<float> list_planned_step_duration <- [];          // Durée prévue (secondes) par étape
    float default_car_speed <- 50#km/#h;                   // Vitesse voiture par défaut ~50 km/h
    string main_mode <- "";

    // Suivi des métriques
    int step_started_at <- 0;                              // Horodatage du début de l'étape actuelle
    float on_vehicle_capacity_utilization <- 0.0;          // Capacité du véhicule lors de l'embarquement
    float trip_traveled_duration <- 0.0;                   // Durée totale du trajet jusqu'à présent

    // Actions virtuelles pour la collecte de métriques (à implémenter par les sous-classes)
    action submit_ob_transfer(float segment_duration, float dist, int ob_step_idx) virtual: true;
    action submit_ob_transit(float segment_duration, float dist, int ob_step_idx, float capacity) virtual: true;
    action submit_ob_tripfeedback(float trip_duration) virtual: true;
    action submit_vehicle_wait_time(float wait_duration, int ob_step_idx) virtual: true;

    // Compteur d'activités
    int total_activities <- 0;

    /**
     * Réinitialiser le plan de trajet actuel - effacer toutes les destinations et routes
     */
    action passenger_reset_plan {
        list_destination <- [];
        list_destination_stop_name <- [];
        list_route_id <- [];
        list_shape_id <- [];
        list_planned_step_duration <- [];
        main_mode <- "";
    }

    /**
     * Définir un nouveau plan de trajet pour l'agent basé sur les données de planification de voyage.
     * Convertit les données brutes de trajet en segments de voyage exécutables.
     *
     * @param plan_target Coordonnées de destination finale {lon, lat}
     * @param legs_raw Liste des étapes de trajet du moteur de routage
     * @param raw Structure de données de trajet brute
     */
    action passenger_set_plan(map plan_target, list legs, map raw) {
        
        total_activities <- total_activities + 1;
				
        // Gérer la téléportation directe pour les étapes vides (pas de transport public nécessaire)
        if length(legs) = 0 {
            map raw_loc <- (raw != nil and raw.keys contains "plan" and raw["plan"] is map) ? map(raw["plan"]) : nil;
            map start_loc <- (raw_loc != nil and raw_loc.keys contains "start_location" and raw_loc["start_location"] is map) ? map(raw_loc["start_location"]) : nil;
            
            if (start_loc != nil) {
                if (!(start_loc.keys contains "lon" or start_loc.keys contains "lng") or !(start_loc.keys contains "lat")) {
                    write "❌ ERREUR: Coordonnées manquantes dans start_location pour l'agent " + name + " ! Données: " + start_loc;
                } else {
                    float start_lon <- start_loc.keys contains "lon" ? float(start_loc["lon"]) : float(start_loc["lng"]);
                    float start_lat <- float(start_loc["lat"]);
                    point start_point <- point(to_GAMA_CRS({start_lon, start_lat}, POPULATION_CRS));
                    location <- start_point;
                }
            } else {
                write "❌ ERREUR: start_location est nil pour l'agent " + name + " !";
            }
        }

        // Activer l'agent seulement s'il y a un plan à suivre.
        // legs=[] = même localisation : pas de déplacement possible, is_ready reste false
        // pour éviter le deadlock (agent bloqué "ready" sans jamais générer d'"arrival").
        is_ready <- length(legs) > 0;
        raw_trip <- raw;

        // Réinitialiser l'état du voyage et les métriques
        step_idx <- 0;
        trip_traveled_duration <- 0.0;
        step_started_at <- CURRENT_TIMESTAMP;

        do passenger_reset_plan();

        // Construire le plan de voyage à partir des étapes de routage
        if length(legs) > 0 {
            // Ajouter le segment de marche initial vers le premier arrêt de transport
            map leg0 <- map(legs[0]);
            map start_loc_0 <- map(leg0["start_location"]);

            if (!(start_loc_0.keys contains "lon" or start_loc_0.keys contains "lng") or !(start_loc_0.keys contains "lat")) {
                write "❌ ERREUR: Coordonnées manquantes dans legs[0]['start_location'] pour l'agent " + name + " ! Données: " + start_loc_0;
            } else {
                float start_lon <- start_loc_0.keys contains "lon" ? float(start_loc_0["lon"]) : float(start_loc_0["lng"]);
                float start_lat <- float(start_loc_0["lat"]);

                point start_point <- point(to_GAMA_CRS({start_lon,start_lat}, POPULATION_CRS));
                list_destination << start_point;
                list_destination_stop_name << string(start_loc_0["stop"]);
                list_route_id << _WALK_;
                list_shape_id << nil;
                list_planned_step_duration << 0.0;
            }

            // Traiter chaque étape de transport
            loop leg over: legs {
                map leg_map <- map(leg);
                map leg_end_location <- map(leg_map["end_location"]);
                
                if (!(leg_end_location.keys contains "lon" or leg_end_location.keys contains "lng") or !(leg_end_location.keys contains "lat")) {
                    write "❌ ERREUR: Coordonnées manquantes dans leg['end_location'] pour l'agent " + name + " ! Données: " + leg_end_location;
                } else {
                    float leg_end_lon <- leg_end_location.keys contains "lon" ? float(leg_end_location["lon"]) : float(leg_end_location["lng"]);
                    float leg_end_lat <- float(leg_end_location["lat"]);

                    point end_point <- point(to_GAMA_CRS({leg_end_lon, leg_end_lat}, POPULATION_CRS));
                    list_destination << end_point;
                    list_destination_stop_name << string(leg_end_location["stop"]);

                    // Déterminer si c'est un transfert (marche) ou un segment de transport
                    string transit_route <- string(leg_map["transit_route"]);
                    string mode <- (bool(leg_map["is_transfer"]) ? _WALK_: string(leg_map["transit_route"]));
                    list_route_id << mode;
                    list_shape_id << (bool(leg_map["is_transfer"]) ? nil : (list(leg_map["shape_id"]) collect string(each)));
                    
                    // Durée du segment : champ "duration" (secondes) ou calcul depuis end_time-start_time (ms)
                    float _leg_dur <- (leg_map.keys contains "duration" and leg_map["duration"] != nil) ?
                        float(int(leg_map["duration"])) :
                        (float(int(leg_map["end_time"])) - float(int(leg_map["start_time"]))) / 1000.0;
                    list_planned_step_duration << _leg_dur;
                    
                    // Mets a jour le main mode si non défini ou marche.
                    if main_mode = "" {
                    	main_mode <- mode;
                    }
                    else if main_mode = _WALK_ {
                    	main_mode <- mode;
                    }
                }
            }
        }

        // Ajouter le segment de marche final vers la destination
        if (!(plan_target.keys contains "lon" or plan_target.keys contains "lng") or !(plan_target.keys contains "lat")) {
            write "❌ ERREUR: Coordonnées manquantes dans la destination finale pour l'agent " + name + " ! Données: " + plan_target;
        } else {
            float target_lon <- plan_target.keys contains "lon" ? float(plan_target["lon"]) : float(plan_target["lng"]);
            point end_point <- point(to_GAMA_CRS({target_lon, float(plan_target["lat"])}, POPULATION_CRS));
            
            list_destination << end_point;
            list_destination_stop_name << purpose;
            list_route_id << _WALK_;
            list_shape_id << nil;
            list_planned_step_duration << 0.0;
        }
    }

    /**
     * Action virtuelle appelée quand le plan de trajet est terminé
     * À implémenter par les sous-classes pour un comportement spécifique de fin
     */
    action on_finish_plan virtual: true {

    }
	
//	reflex follow_the_vehicle when: on_vehicle != nil {
//		if !dead(on_vehicle) {
//			// follow the vehicle if we're sitting on it
//			location <- on_vehicle.location;
//		}
//		else {
//			point dest <- list_destination[step_idx];
//			location <- dest;
//			on_vehicle <- nil;
//		}
//		
////		// get off if we reach to the last stop, or close to the destination
////		point dest <- list_destination[step_idx];
////		if location distance_to dest <= get_in_vehicle_dist or dead(on_vehicle){
////			if !dead(on_vehicle) {
////				ask on_vehicle {
////					do get_off(name);
////				}
////			}
////			on_vehicle <- nil;
////			location <- dest;
////		}
//	}
	
		
	reflex follow_the_vehicle when: on_vehicle != nil {
		if CURRENT_TIMESTAMP < schedule_at {
			return;
		}
		
		if !dead(on_vehicle) {
			// suivre le véhicule si nous sommes assis dessus
			location <- on_vehicle.location;
		}
		
		// descendre si nous atteignons le dernier arrêt, ou proche de la destination
		point dest <- list_destination[step_idx];
		if location distance_to dest <= get_in_vehicle_dist or dead(on_vehicle){
			if !dead(on_vehicle) {
				ask on_vehicle {
					do get_off(name);
				}
				// métriques
				on_vehicle_capacity_utilization <- on_vehicle.capacity_utilization;
			}		
			on_vehicle <- nil;
			location <- dest;
		}
		
	}
	
	reflex follow_the_plan_when_stop when: target_location != nil and is_stop_moving and on_vehicle = nil {
		
		/* Si l'heure actuelle est inférieure à l'heure prévue (schedule_at), il'agent ne fait rien et attend.  */
		if CURRENT_TIMESTAMP < schedule_at {
			return;
		}
		
		 is_ready <- false;
		 is_active <- true;
		
		point dest <- list_destination[step_idx];
		
		// passer à l'étape suivante si la destination de l'étape précédente est atteinte
		if location distance_to dest < moving_close_dist {
			// essayer de soumettre l'observation
			bool is_transfer <- list_route_id[step_idx] = _WALK_;
			float _duration <- float(CURRENT_TIMESTAMP-step_started_at);
			// métriques
			trip_traveled_duration <- trip_traveled_duration + _duration;
			
			if is_transfer {
				do submit_ob_transfer(
					_duration,
					last_dist_traveled,
					step_idx
				);
			} else {
				do submit_ob_transit(
					_duration,
					last_dist_traveled,
					step_idx,
					on_vehicle_capacity_utilization
				);
			}
			step_idx <- step_idx + 1;
			location <- dest;
			
			// réinitialiser les métriques
			step_started_at <- CURRENT_TIMESTAMP;
			last_dist_traveled <- 0.0;
		}
		
//		write "Stop: " + step_idx;
		
		/* Si l'index de l'étape dépasse la liste des destinations, cela signifie que le voyage est terminé */
		if step_idx >= length(list_destination) {
			location <- target_location;
			
			do submit_ob_tripfeedback(trip_traveled_duration);
			
			do passenger_reset_plan();
			do on_finish_plan();
			
			activity_id <- nil;
			is_active <- false;
			return;
		}
		
		// planifier le prochain mouvement, déplacement propre ou attente d'un véhicule
		string route_id <- list_route_id[step_idx];
		list<string> shape_id_list <- list_shape_id[step_idx];
		
		/* Cas déplacement en VOITURE — vitesse = distance / durée planifiée du segment */
		if route_id = _CAR_ or route_id = _BIKE_ {
			point dest2 <- list_destination[step_idx];
			float planned_dur <- (step_idx < length(list_planned_step_duration)) ? list_planned_step_duration[step_idx] : 0.0;
			float car_dist <- location distance_to dest2;
			speed <- (planned_dur > 0 and car_dist > 0) ? (car_dist / planned_dur) : default_car_speed;
			moving_target <- dest2;
		}
		/* Cas déplacement a pied */
		else if route_id = _WALK_{
			speed <- 2#m/#s;
			point dest2 <- list_destination[step_idx];
			moving_target <- dest2;
		}
		/* Cas transport en COMMUN */
		else {

			if route_id in route_vehicle_map.keys {
				// TODO: considérer la capacité du véhicule
				public_vehicle closest_vehicle <- (route_vehicle_map[route_id]
						first_with (shape_id_list contains each.shape_id and !each.is_full and distance_to(each, self) < get_in_vehicle_dist)
				);
				if closest_vehicle != nil {
					on_vehicle <- closest_vehicle;
					ask closest_vehicle {
						do get_in(name);
					}

					float waiting_duration <- float(CURRENT_TIMESTAMP-step_started_at);
					do submit_vehicle_wait_time(waiting_duration, step_idx);

					// métriques
					on_vehicle_capacity_utilization <- on_vehicle.capacity_utilization;
				}
			}
			else {
				write "Route id" + route_id + " not in route_vehicle_map.keys";
			}
		}
	}
}

/**
 * Espèce d'habitant concrète - représente les personnes individuelles dans la simulation.
 * Étend passenger avec l'identité, l'intégration LLM, et la collecte d'observations.
 * C'est le type d'agent principal avec lequel les utilisateurs interagissent dans la simulation.
 */
species inhabitant parent: passenger {
    // Attributs d'identité et personnels
    string person_name;                    // Nom complet
    string person_id;                      // Identifiant unique
    bool is_llm_based <- false;            // Si cet agent utilise LLM pour les décisions

    // État d'activité
    int time_24h -> CURRENT_TIMESTAMP_24H; // Heure actuelle au format 24h
    bool is_idle -> target_location = nil; // Vrai quand l'agent n'a pas de trajet actif

    // Collecte d'observations pour les agents LLM
    list<map<string,unknown>> OB_LIST <- [];  // Liste d'observations pour l'apprentissage

    // Paramètres d'affichage
    bool show_name <- flip(show_inhabitants_label_density/100.0);  // Afficher ou non le label du nom

    /**
     * Initialiser l'habitant avec un objectif par défaut
     */
    init {
        purpose <- "home";
    }

    /**
     * Appelée quand le plan de trajet est terminé
     * Journalise la fin et pourrait notifier l'agent LLM
     */
    action on_finish_plan {

    	// Calcul de la durée absolue en secondes
	    float diff_seconds <- float(abs(CURRENT_TIMESTAMP - expected_arrive_at));
		// Ramener les timestamps Unix au temps de la journée (mod 24h) avant formatage
		float expected_arrive_at_seconds <- float(expected_arrive_at mod SECONDS_IN_24H);
		float schedule_at_seconds <- float(schedule_at mod SECONDS_IN_24H);

	    // Extraction des unités
	    int diff_h <- int(diff_seconds / 3600);
	    int diff_m <- int((diff_seconds mod 3600) / 60);
	    string formatted_diff_time <- "" + diff_h + "h" + (diff_m < 10 ? "0" : "") + diff_m;

		int expected_arrive_h <- int(expected_arrive_at_seconds / 3600);
	    int expected_arrive_m <- int((expected_arrive_at_seconds mod 3600) / 60);
	    string formatted_expected_arrive_time <- "" + expected_arrive_h + "h" + (expected_arrive_m < 10 ? "0" : "") + expected_arrive_m;

		int schedule_h <- int(schedule_at_seconds / 3600);
	    int schedule_m <- int((schedule_at_seconds mod 3600) / 60);
	    string formatted_schedule_time <- "" + schedule_h + "h" + (schedule_m < 10 ? "0" : "") + schedule_m;

	    int current_h <- int(CURRENT_TIMESTAMP_24H / 3600);
	    int current_m <- int((CURRENT_TIMESTAMP_24H mod 3600) / 60);
	    string formatted_current_time <- "" + current_h + "h" + (current_m < 10 ? "0" : "") + current_m;

		string delay_msg <- ": traject schedule at="+formatted_schedule_time+ " expected arrive at=" + formatted_expected_arrive_time + " current time is " + formatted_current_time;
	    if (CURRENT_TIMESTAMP <= expected_arrive_at) {
	        write "Hura 😊, Person " + person_id + " finished the plan with " + formatted_diff_time + " in advance"+delay_msg; 
	    } 
	    else if (diff_seconds <= 60*15) {
	        write "Too late 😡, Person " + person_id + " finished the plan " + formatted_diff_time + " late"+delay_msg; 
	    }
	    else {
	        write "Too late 🤬, Person " + person_id + " finished the plan " + formatted_diff_time + " very late"+delay_msg; 
	    }

    }
	
	/**
	 * Soumettre une observation pour un segment de marche/transfert
	 * Enregistre la durée, la distance et les informations d'arrêt pour l'apprentissage
	 */
	action submit_ob_transfer(float segment_duration, float dist, int ob_step_idx) {
		map<string,unknown> ob <- [
			"type"::"transfer",
			"timestamp"::CURRENT_TIMESTAMP,
			"moving_id"::moving_id,
			"activity_id"::activity_id,
			"distance"::dist,
			"duration"::segment_duration,
			"from_name"::(ob_step_idx = 0? nil: list_destination_stop_name[ob_step_idx-1]),
			"destination_name"::list_destination_stop_name[ob_step_idx]
		];
		OB_LIST << ob;
	}
	
	/**
	 * Soumettre une observation pour un segment de transport (véhicule)
	 * Enregistre les détails de transport incluant l'utilisation de la capacité et les infos de route
	 */
	action submit_ob_transit(float segment_duration, float dist, int ob_step_idx, float capacity) {    
		map<string,unknown> ob <- [
			"type"::"transit",
			"timestamp"::CURRENT_TIMESTAMP,
			"waiting_time"::0,
			"moving_id"::moving_id,
			"activity_id"::activity_id,
			"distance"::dist,
			"duration"::segment_duration,
			"capacity_utilization"::capacity,
			"departure_stop_name"::(ob_step_idx > 0? list_destination_stop_name[ob_step_idx-1]:""),
			"arrival_stop_name"::list_destination_stop_name[ob_step_idx],
			"by_vehicle_route_id"::list_route_id[ob_step_idx]
		];
		OB_LIST << ob;
	}
	
	/**
	 * Soumettre une observation pour le temps d'attente à un arrêt
	 * Enregistre combien de temps l'agent a attendu un véhicule
	 */
	action submit_vehicle_wait_time(float wait_duration, int ob_step_idx) {
		map<string,unknown> ob <- [
			"type"::"wait_in_stop",
			"timestamp"::CURRENT_TIMESTAMP,
			"activity_id"::activity_id,
			"duration"::wait_duration,
			"stop_name"::list_destination_stop_name[ob_step_idx-1],
			"by_vehicle_route_id"::list_route_id[ob_step_idx]
		];
		OB_LIST << ob;
	}
	
	/**
	 * Soumettre une observation finale quand le trajet est terminé
	 * Enregistre les performances globales du trajet par rapport à la durée planifiée
	 */
	action submit_ob_tripfeedback(float trip_duration) {
		map<string, unknown> plan <- map<string, unknown>(raw_trip["plan"]);
		float plan_duration <- (float(plan["end_time"]) - float(plan["start_time"])) / 1000.0;
		map<string,unknown> ob <- [
			"type"::"arrival",
			"timestamp"::CURRENT_TIMESTAMP,
			"moving_id"::moving_id,
			"activity_id"::activity_id,
			"duration"::trip_duration,
			"plan_duration"::plan_duration,
			"started_at"::CURRENT_TIMESTAMP-trip_duration,
			"schedule_at"::schedule_at,
			"arrive_at"::CURRENT_TIMESTAMP,
			"expected_arrive_at"::expected_arrive_at,
			"prepare_before_seconds"::raw_trip["prepare_before_seconds"],
			"purpose"::purpose
		];
		OB_LIST << ob;
	}
	
	/**
	 * Obtenir la représentation emoji de l'action/état actuel
	 * Utilisé pour l'affichage visuel de l'activité de l'agent
	 */
	string get_action_emoji {
		if !is_idle {
			if list_route_id != nil {
				if list_route_id[step_idx] = _WALK_ {
					return PURPOSE_ICON_MAP["__WALKING__"];
				}
				else if list_route_id[step_idx] = _CAR_ {
					return PURPOSE_ICON_MAP["__DRIVING__"];
				}
				else if list_route_id[step_idx] = _BIKE_ {
					return PURPOSE_ICON_MAP["__BIKE__"];
				}
			}
			return PURPOSE_ICON_MAP["__MOVING__"];
		}
		if purpose in PURPOSE_ICON_MAP.keys {
			return PURPOSE_ICON_MAP[purpose];
		}
		return "";
	}
	
	/**
	 * Couleur selon l'état de déplacement :
	 *   gris clair → inactif (pas de trajet)
	 *   lightblue   → prêt, en attente avant départ
	 *   vert   → en transport en commun (dans le véhicule ou attente à l'arrêt)
	 *   orange → à pied
	 *   rouge  → en voiture
	 */
	rgb get_agent_color {
		if is_idle {
			return #white;
		}
		// Vérifié en priorité : si l'agent est physiquement dans un véhicule TC → vert garanti
		if on_vehicle != nil {
			return #green;
		}
		if is_ready {
			return #gray;
		}
		if main_mode = _BIKE_ {
			return #purple;
		}
		if main_mode = _CAR_ {
			return #red;
		}
		if main_mode = _WALK_ {
			return #orange;
		}

		// Others
		return #yellow;
	}

	/**
	 * Aspect visuel par défaut pour les agents habitants
	 * Couleur selon l'état (gris sombre/gris/orange/rouge), taille plus grande pour les agents LLM
	 */
	aspect default {
		if !show_inhabitants {
			return;
		}
		rgb agent_color <- get_agent_color();
		int base_size <- is_llm_based ? 20 : 9;
		// Agents dans un véhicule TC : cercle (différent du carré habituel) légèrement décalé
		// pour rester visible par-dessus le dessin du véhicule
		if on_vehicle != nil {
			draw circle(base_size * inhabitant_display_size)
				color: agent_color
				border: #white
				at: location + {base_size * inhabitant_display_size * 0.5, -base_size * inhabitant_display_size * 0.5};
		} else {
			draw square(base_size * inhabitant_display_size)
				color: agent_color
				border: true;
		}
		if show_name and is_idle = false and is_ready = false {
			draw (get_action_emoji()) at: location + {-3,1.5} anchor: #bottom_center color: agent_color font: font('Default', (is_llm_based ? 18 : 16), #bold);
			draw (person_id) at: location + {-3,1.5} anchor: #top_left color: agent_color font: font('Default', (is_llm_based ? 10 : 8), #bold);
		}
	}
}
