/**
* Nom: LLMAgent
* Basé sur le modèle vide interne.
* Auteur: dung
* Tags: LLM, agents intelligents, communication reseau
*
* Description: Module d'intégration des agents alimentés par LLM (Large Language Models).
* Définit les agents qui communiquent avec des systèmes d'IA externes via HTTP et WebSocket
* pour prendre des décisions intelligentes dans la simulation de transport urbain.
* Gère la synchronisation des données, l'envoi d'observations et la réception d'actions.
*/


model LLMAgent

// Import des modules nécessaires
import "Settings.gaml"
import "Inhabitant.gaml"

global {
	// Configuration de la connexion HTTP pour la communication synchrone
	int http_port <- 8002;
	string http_url <- "http://localhost";

	// Configuration MQTT pour la communication asynchrone (non utilisé actuellement)
	int mqtt_port <- 1883;
	string mqtt_url <- "localhost";
	string mqtt_action_topic <- "action/data";
    string mqtt_observation_topic <- "observation/data";

	init {
		// Créer un agent de synchronisation HTTP
		create llm_agent_sync number: 1 {
			do connect to: http_url protocol: "http" port: http_port raw: true;
		}

		// Créer un agent de communication asynchrone WebSocket
		create llm_agent_async number: 1 {
			do connect protocol: "websocket_server" port: 3001 with_name: name raw: true;
		}
	}
}

/**
 * Agent de synchronisation LLM - gère la communication périodique avec le système LLM via HTTP.
 * Envoie des données de synchronisation toutes les 15 minutes et des données de population toutes les heures.
 * Responsable de l'initialisation de la population et de la synchronisation continue.
 */
species llm_agent_sync skills:[network] {
	/**
	 * Initialisation - envoie les données d'initialisation au système LLM au premier cycle
	 */
	reflex init when: cycle = 1 {
		write "Init population -> LLM, timestamp: " + CURRENT_TIMESTAMP;
		write "Paramètres envoyés : population=" + population_size
			+ " part_of_llm=" + part_of_llm_based_agents
			+ " ltm=" + long_term_memory_enabled
			+ " self_reflect=" + long_term_self_reflect_enabled
			+ " max_days=" + simulation_max_days;

		do send to: "/init" contents: [
			"POST",
			to_json([
				"timestamp"::CURRENT_TIMESTAMP,
				"population_size"::population_size,
				"part_of_llm_based_agents"::part_of_llm_based_agents,
				"long_term_memory_enabled"::long_term_memory_enabled,
				"long_term_self_reflect_enabled"::long_term_self_reflect_enabled,
				// Horizon d'arrêt (ticket 008, A5) : transmis pour être consigné dans
				// le scenario_params.yaml du run. Sans lui, rien dans le répertoire
				// d'expérience ne dit sur combien de jours le run était censé porter.
				"simulation_max_days"::simulation_max_days
			]),
			["Content-Type"::"application/json"]
		];
	}

	/**
	 * Synchronisation périodique - envoie les compteurs de population toutes les 15 minutes
	 * Les fins d'activité sont gérées via les observations WebSocket (submit_obseration)
	 */
	reflex sync when: every(15#mn) and cycle > 1 {
		int nb_ready    <- length(inhabitant where (each.is_ready));
		int nb_active   <- length(inhabitant where (each.is_active));
		int nb_inactive <- length(inhabitant) - nb_ready - nb_active;

		string json_body <- to_json(["timestamp"::CURRENT_TIMESTAMP,
			"ready_count"::nb_ready, "active_count"::nb_active, "inactive_count"::nb_inactive]);
		do send to: "/sync" contents: [
			"POST",
			json_body,
			["Content-Type"::"application/json"]
		];
	}
	
	
	/**
	 * Réception et traitement des messages du système LLM
	 * Traite les réponses d'initialisation et crée la population d'agents
	 */
	reflex get_message {
		loop while:has_more_message()
		{
			message mess <- fetch_message();
			string jsonBody <- map(mess.contents)["BODY"];
			// Guard against non-JSON responses (e.g. HTTP 500 "Internal Server Error")
			if jsonBody = nil or not (jsonBody contains "{") {
				write "[ERROR] Received non-JSON HTTP response from controller: " + jsonBody;
				continue;
			}
			map<string, unknown> json <- from_json(jsonBody);
			if bool(json["success"]) != true {
				write "[ERROR] Got error message: " + string(json);
				continue;
			}
			string messageType <- json["message_type"];
			
			/** 
			 *   --------   WORLD INIT   --------------
			 */
			if messageType = "ag_world_init" {
				// Traiter l'initialisation du monde des agents
				map<string, unknown> data <- json["data"];
				list<map<string, unknown>> people <- data["people"];
				loop p over: people {
					map<string, unknown> p_loc <- map<string, unknown>(p["location"]);
					float lon <- float(p_loc["lon"]);
					float lat <- float(p_loc["lat"]);
					point plocation <- point(to_GAMA_CRS({lon, lat}, POPULATION_CRS));
					create inhabitant with: [
						route_vehicle_map::ROUTE_VEHICLE_MAP,
						person_name::string(p["name"]),
						person_id::string(p["person_id"]),
//						age::int(p["age"]),
						location::plocation,
						is_llm_based::bool(p["is_llm_based"])
					] {
						INHABITANT_MAP[self.person_id] <- self;
					}
				}
			} else if messageType = "calibration_started" {
				// Accusé de démarrage de la calibration du prompt
				map<string, unknown> data <- json["data"];
				write "[CALIBRATION] Démarrée (pid=" + string(data["pid"])
					+ ", cycles=" + string(data["iterations"])
					+ ") — journal : " + string(data["log"]);
			}
		}

	}

	/**
	 * Lance la calibration du prompt côté contrôleur (POST /calibrate).
	 * Non bloquant : le contrôleur exécute la campagne en tâche de fond.
	 * Le nombre de cycles (itérations de la boucle) provient du paramètre
	 * global `calibration_cycles`, réglable depuis l'IHM.
	 */
	action launch_calibration {
		write "[CALIBRATION] Requête de lancement — " + calibration_cycles + " cycle(s)...";
		do send to: "/calibrate" contents: [
			"POST",
			to_json(["iterations"::calibration_cycles]),
			["Content-Type"::"application/json"]
		];
	}
}


species llm_agent_async skills:[network] {
	string send_to;  // Identifiant du destinataire WebSocket

//	reflex send when: send_to != nil and every(2#mn) {
//		write "Sending...";
//		do send to: send_to contents: name + " at " + cycle + " sent to server_group a message";
//	}

	/**
	 * Soumission des observations - envoie les observations collectées par les agents habitants
	 * Toutes les 5 minutes, transmet les données d'observation pour l'apprentissage du LLM
	 */
	reflex submit_obseration when: send_to !=nil and every(1#cycle) {
		loop p over: (inhabitant where (length(each.OB_LIST) > 0)) {
			list<map<string, unknown>> ob_list <- p.OB_LIST;
			p.OB_LIST <- [];
			loop ob over: ob_list {
				point ploc <- point(p.location CRS_transform(POPULATION_CRS));
				map<string, unknown> ob_payload <- [
					"person_id"::p.person_id,
					"activity_id"::ob["activity_id"],
					"timestamp"::CURRENT_TIMESTAMP,
					"location"::[
						"lon"::ploc.x,
			    		"lat"::ploc.y
					],
				    "env_ob_code"::string(ob["type"]),
				    "data"::ob
				];
				string payload <- to_json([
					"topic"::"observation/data",
					"payload"::ob_payload
				]);
				do send to: send_to contents: payload;
				//write "Send observation of " + p.person_id + ": " + ob;
			}
		}
	}
	   	
	/**
	 * Réception des actions du système LLM - traite les messages WebSocket entrants
	 * Reçoit les décisions d'action du LLM et les applique aux agents habitants appropriés
	 */
	reflex get_message when: has_more_message() {
		loop while:has_more_message()
		{
			message mess <- fetch_message();
			send_to <- mess.sender;  // Mémoriser l'expéditeur pour les réponses
			//write "mess.contents " + map(mess.contents);
			string action_data_json <- map(mess.contents)["contents"];
			map<string, unknown> payload_data <- from_json(action_data_json);
			string topic <- payload_data["topic"];
			
			/** 
			 *   --------   LOG   --------------
			 */
			if topic = "system/log" {
				map<string, unknown> log_payload <- map<string, unknown>(payload_data["payload"]);
				write "[Python] " + string(log_payload["message"]);
				continue;
			}

			/**
			 *   --------   THROTTLE (contre-pression prédictive, ticket 003)   --------------
			 * Régime dégradé signalé par Python : débit LLM réel et vitesse de simulation.
			 * Le champ `message` reste autoporteur (traité comme un log) ; les globales
			 * alimentent l'UI de l'expérience (monitor/overlay).
			 */
			if topic = "system/throttle" {
				map<string, unknown> t <- map<string, unknown>(payload_data["payload"]);
				THROTTLE_ACTIVE  <- bool(t["active"]);
				LLM_RATE_PER_MIN <- float(t["llm_rate_per_min"]);
				SIM_RATIO_PYTHON <- float(t["sim_ratio"]);
				write "[Python][throttle] " + string(t["message"]);
				continue;
			}

			/** 
			 *   --------   ACTION/DATA   --------------
			 */
			if topic != "action/data" {
				continue;
			}
			map<string, unknown> action_data <- payload_data["payload"];
			

			string person_id <- action_data["person_id"];
			map<string, unknown> data <- action_data["action"];
			inhabitant person <- INHABITANT_MAP[person_id];
			if person != nil {
				// Appliquer l'action à l'agent trouvé
				ask person {
					
					// Moving ID (serialized as "id" by PersonMove.model_dump())
					self.moving_id <- string(data["id"]);
					
					// Objectif du déplacement (ex: aller travaillier de 9h à 18h)
					map<string, unknown> for_activity <- map<string, unknown>(data["for_activity"]);
					self.activity_id <- string(for_activity["id"]);
					self.purpose <- string(data["purpose"]);
					self.expected_arrive_at <- int(data["expected_arrive_at"]);
					int prepare_before_seconds <- int(data["prepare_before_seconds"]);
					self.schedule_at <- self.expected_arrive_at - prepare_before_seconds;
					//  write "[Plan] Person " + person_id + " purpose=" + string(data["purpose"]) + " expected_arrive_at=" + self.expected_arrive_at + " prepare_before_seconds=" + prepare_before_seconds + " schedule_at=" + self.schedule_at + " (now=" + CURRENT_TIMESTAMP + ")";
					if CURRENT_TIMESTAMP > self.schedule_at {
						int sched_h <- int((self.schedule_at mod SECONDS_IN_24H) / 3600);
						int sched_m <- int(((self.schedule_at mod SECONDS_IN_24H) mod 3600) / 60);
						string formatted_sched <- "" + sched_h + "h" + (sched_m < 10 ? "0" : "") + sched_m;
						int now_h <- int(CURRENT_TIMESTAMP_24H / 3600);
						int now_m <- int((CURRENT_TIMESTAMP_24H mod 3600) / 60);
						string formatted_now <- "" + now_h + "h" + (now_m < 10 ? "0" : "") + now_m;
						write "⚠️ Late order: Person " + person_id + " received order to start trajet at " + formatted_sched + " when current time is " + formatted_now;
					}
					//	self.moving_description <- string(data["description"]);
						
					// Définition du plan de déplacement
					//map<string, unknown> plan <- map<string, unknown>(data["plan"]);
					map plan_map <- map(data["plan"]);
					list legs_to_send <- list(plan_map["legs"]);
					
					do passenger_set_plan(
						data["target_location"],
						legs_to_send,
						data
					);
				}	
			} else {
				 write "[LLM Message: action/data] Not found the person: " + person_id;
			}
			
		}
		
	}
}

/**
 * Agent LLM de test - utilisé pour déboguer et tester la communication réseau.
 * Affiche simplement tous les messages reçus pour vérification du fonctionnement.
 */
species llm_agent_test skills:[network] {
	/**
	 * Réception de test - affiche tous les messages reçus pour débogage
	 */
	reflex get_message {
		loop while:has_more_message()
		{
			message mess <- fetch_message();
			write "mess " + mess;
		}
		
	}
}




