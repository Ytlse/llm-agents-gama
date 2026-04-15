/**
* Nom: LLMAgent
* Basé sur le modèle vide interne.
* Auteur: dung
* Tags: LLM, agents intelligents, communication réseau
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

		do send to: "/init" contents: [
			"POST",
			to_json([
				"timestamp"::CURRENT_TIMESTAMP
			]),
			["Content-Type"::"application/json"]
		];
	}

	/**
	 * Synchronisation périodique - envoie des données de population inactive toutes les 15 minutes
	 * Toutes les heures, inclut la liste complète des personnes inactives avec leurs localisations
	 */
	reflex sync when: every(15#mn) and cycle > 1 {
		list<unknown> idle_people <- [];
		if every(60#mn) {
			loop p over: inhabitant where (each.is_idle) {
				point ploc <- point(p.location CRS_transform(POPULATION_CRS));
				idle_people << [
					"person_id"::p.person_id,
					"location"::[
						"lon"::ploc.x,
				    	"lat"::ploc.y
					]
				];
			}
		}

		string json_body;
		if length(idle_people) > 0 {
			json_body <- to_json(["timestamp"::CURRENT_TIMESTAMP, "idle_people"::idle_people]);
		} else {
			json_body <- to_json(["timestamp"::CURRENT_TIMESTAMP]);
		}
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
			} 
		}
		
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
	reflex submit_obseration when: send_to !=nil and every(5#mn) {
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
				write "Send observation of " + p.person_id + ": " + ob;
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
			write "mess.contents " + map(mess.contents);
			string action_data_json <- map(mess.contents)["contents"];
			map<string, unknown> payload_data <- from_json(action_data_json);
			string topic <- payload_data["topic"];
			if topic != "action/data" {
				continue;  // Ignorer les messages qui ne sont pas des actions
			}
			map<string, unknown> action_data <- payload_data["payload"];
			

			string person_id <- action_data["person_id"];
			map<string, unknown> data <- action_data["action"];
			inhabitant person <- INHABITANT_MAP[person_id];
			if person != nil {
				// Appliquer l'action à l'agent trouvé
				ask person {
					
					// Moving ID
					self.moving_id <- string(data["move_id"]);
					
					// Objectif du déplacement (ex: aller travaillier de 9h à 18h)
					map<string, unknown> for_activity <- map<string, unknown>(data["for_activity"]);
					self.activity_id <- string(for_activity["id"]);
					self.purpose <- string(data["purpose"]);
					self.expected_arrive_at <- int(data["expected_arrive_at"]);
					int prepare_before_seconds <- int(data["prepare_before_seconds"]);
					self.schedule_at <- self.expected_arrive_at - prepare_before_seconds;
					//	self.moving_description <- string(data["description"]);

					// Définition du plan de déplacement
					map<string, unknown> plan <- map<string, unknown>(data["plan"]);
					do passenger_set_plan(
						data["target_location"],
						plan["legs"],
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
