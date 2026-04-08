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
    int show_inhabitants_label_density <- 100;       // Pourcentage d'agents affichant les labels

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
    bool is_active <- false;               // Vrai quand l'agent a un plan de trajet actif

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
    string _ROUTE_NONE_ <- "__NONE__";     // Marqueur pour les segments de marche

    // État d'interaction avec les véhicules
    public_vehicle on_vehicle;             // Véhicule actuellement embarqué (nil si marche)
    float get_in_vehicle_dist <- 25#m;     // Seuil de distance pour embarquer dans les véhicules
    int step_idx <- 0;                     // Étape actuelle dans le plan de voyage

    // Structures de données du plan de voyage
    list<point> list_destination <- [];                    // Destinations géographiques
    list<string> list_destination_stop_name <- [];         // Noms d'arrêts pour chaque destination
    list<string> list_route_id <- [];                      // IDs de route (ou _ROUTE_NONE_ pour marche)
    list<list<string>> list_shape_id <- [];                // IDs de forme pour les segments de transport

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
    }

    /**
     * Définir un nouveau plan de trajet pour l'agent basé sur les données de planification de voyage.
     * Convertit les données brutes de trajet en segments de voyage exécutables.
     *
     * @param plan_target Coordonnées de destination finale {lon, lat}
     * @param legs_raw Liste des étapes de trajet du moteur de routage
     * @param raw Structure de données de trajet brute
     */
    action passenger_set_plan(map<string, float> plan_target, list<map<string, unknown>> legs_raw, map<string, unknown> raw) {
        total_activities <- total_activities + 1;

		list<map<string, unknown>> legs <- (legs_raw is list) ? list<map<string, unknown>>(legs_raw) : [];
				
        // Gérer la téléportation directe pour les étapes vides (pas de transport public nécessaire)
        if length(legs) = 0 {
            map<string, unknown> raw_loc <- map<string, unknown>(raw["plan"]);
            map<string, unknown> start_loc <- map<string, unknown>(raw["start_location"]);

            float start_lon <- float(start_loc["lon"]);
            float start_lat <- float(start_loc["lat"]);
            point start_point <- point(to_GAMA_CRS(
                {start_lon, start_lat},
                POPULATION_CRS
            ));
            location <- start_point;
        }

        // Activer l'agent et stocker les données de trajet
        is_active <- true;
        raw_trip <- raw;

        // Réinitialiser l'état du voyage et les métriques
        step_idx <- 0;
        trip_traveled_duration <- 0.0;
        step_started_at <- CURRENT_TIMESTAMP;

        do passenger_reset_plan();

        // Construire le plan de voyage à partir des étapes de routage
        if length(legs) > 0 {
            // Ajouter le segment de marche initial vers le premier arrêt de transport
            map<string, unknown> start_loc_0 <- map<string, unknown>(legs[0]["start_location"]);

            float start_lon <- float(start_loc_0["lon"]);
            float start_lat <- float(start_loc_0["lat"]);

            point start_point <- point(to_GAMA_CRS({start_lon,start_lat},
                POPULATION_CRS
            ));
            list_destination << start_point;
            list_destination_stop_name << string(start_loc_0["stop"]);
            list_route_id << _ROUTE_NONE_;
            list_shape_id << nil;

            // Traiter chaque étape de transport
            loop leg over: legs {
                map<string, unknown> leg_end_location <-  map<string, unknown>(leg["end_location"]);
                float leg_end_lon <- float(leg_end_location["lon"]);
                float leg_end_lat <- float(leg_end_location["lat"]);

                point end_point <- point(to_GAMA_CRS({leg_end_lon, leg_end_lat},
                    POPULATION_CRS
                ));
                list_destination << end_point;
                list_destination_stop_name << string(leg_end_location["stop"]);

                // Déterminer si c'est un transfert (marche) ou un segment de transport
                string transit_route <- string(leg["transit_route"]);
                list_route_id << (bool(leg["is_transfer"]) ? _ROUTE_NONE_: string(leg["transit_route"]));
                list_shape_id << (bool(leg["is_transfer"]) ? "" : (list(leg["shape_id"]) collect string(each)));
            }
        }

        // Ajouter le segment de marche final vers la destination
        point end_point <- point(to_GAMA_CRS(
            {float(plan_target["lon"]), float(plan_target["lat"])},
            POPULATION_CRS
        ));
        list_destination << end_point;
        list_destination_stop_name << purpose;
        list_route_id << _ROUTE_NONE_;
        list_shape_id << nil;
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
		if CURRENT_TIMESTAMP < schedule_at {
			return;
		}
		
		point dest <- list_destination[step_idx];
		// passer à l'étape suivante si la destination de l'étape est atteinte
		if location distance_to dest < moving_close_dist {
			// essayer de soumettre l'observation
			bool is_transfer <- list_route_id[step_idx] = _ROUTE_NONE_;
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
		
		if step_idx >= length(list_destination) {
			location <- target_location;
			
			do submit_ob_tripfeedback(trip_traveled_duration);
			
			do passenger_reset_plan();
			do on_finish_plan();
			
			activity_id <- nil;
			return;
		}
		
		// planifier le prochain mouvement, déplacement propre ou attente d'un véhicule
		string route_id <- list_route_id[step_idx];
		list<string> shape_id_list <- list_shape_id[step_idx];
		if route_id != _ROUTE_NONE_ {
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
		} else {
			// se déplacer vers la cible
			point dest2 <- list_destination[step_idx];
			moving_target <- dest2;
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
        write "Hura, person " + person_id + " finished the plan";
        // TODO: notifier l'agent LLM
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
			if list_route_id != nil and list_route_id[step_idx] = _ROUTE_NONE_ {
				return PURPOSE_ICON_MAP["__WALKING__"];
			}
			return PURPOSE_ICON_MAP["__MOVING__"];
		}
		if purpose in PURPOSE_ICON_MAP.keys {
			return PURPOSE_ICON_MAP[purpose];
		}
		return "";
	}
	
	/**
	 * Aspect visuel par défaut pour les agents habitants
	 * Affiche un carré avec codage couleur (rouge pour basé LLM, gris pour régulier)
	 * Affiche l'emoji et l'ID quand show_name est activé
	 */
	aspect default {
		if !show_inhabitants {
			return;
		}
		
		draw 
			square((is_llm_based ? 20: 9)*inhabitant_display_size) 
			color: (is_llm_based ? #red : #gray)
			border: true;
		if show_name {
			draw (get_action_emoji()) at: location + {-3,1.5} anchor: #bottom_center color: (is_llm_based ? #red : #blue) font: font('Default', (is_llm_based ? 18 : 16), #bold);
			draw (person_id) at: location + {-3,1.5} anchor: #top_left color: (is_llm_based ? #red : #blue) font: font('Default', (is_llm_based ? 10 : 8), #bold); 
		}
	}
}
