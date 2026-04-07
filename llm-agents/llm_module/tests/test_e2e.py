"""
tests/test_e2e.py — Tests end-to-end contre l'API en local.

Lance l'API et le worker avant d'exécuter ce script :
  uvicorn llm_module.main:app --port 8000
  celery -A llm_module.worker.task_worker.celery_app worker --loglevel=info

Usage :
  python tests/test_e2e.py                  # tous les scénarios
  python tests/test_e2e.py --scenario 2     # un seul scénario
  python tests/test_e2e.py --provider mistral  # forcer un provider
"""

from __future__ import annotations
import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

BASE_URL = "http://localhost:8000"
POLL_INTERVAL = 1.0   # secondes entre deux polls
POLL_TIMEOUT  = 60.0  # abandon après N secondes


# ---------------------------------------------------------------------------
# Scénarios de test
# ---------------------------------------------------------------------------

SCENARIOS = [
    {
        "name": "Scénario 1 — Profils Toulouse (Banquier vs Étudiant)",
        "payload": {
            "category": "itenary_multi_agent",
            "agents": [
                {
                    "agent_id": "ag_banquier_toulouse",
                    "role": "Banquier privé, 38 ans, résidant à Vieille-Toulouse. Sensibilités : privilégie le luxe, le confort sensoriel, la rapidité et l'image sociale. Détesterait arriver en sueur ou utiliser des modes 'bon marché' lents et inconfortables. ",
                    "context": "Trajet domicile-travail entre Vieille-Toulouse et le centre-ville (Place du Capitole) ou Labège Enova. ",
                    "history": [
                        "Lundi : Trajet en SUV, 25 min de plaisir, musique classique, café à bord. ",
                        "Mardi : Embouteillages sur l'avenue de l'URSS, stress modéré mais siège massant activé. ",
                        "Mercredi : Test du bus par curiosité écologique; jugé trop lent et manque de standing. ",
                        "Jeudi : Journée pluvieuse, la voiture est restée le seul choix acceptable pour rester au sec. ",
                        "Vendredi : Arrivée tardive, parking Indigo plein, coût du stationnement : 35€. ",
                        "Samedi dernier : Sortie en centre-ville, a regretté de ne pas avoir de chauffeur. ",
                        "Il y a un mois : A envisagé l'achat d'un vélo électrique haut de gamme mais craint le vol. ",
                        "Souvenir : Mauvaise expérience dans le métro (trop de monde, odeurs désagréables). ",
                        "Objectif : Maintenir une expérience 'haut de gamme' malgré la saturation du périphérique. ",
                        "Note : Prêt à payer plus pour ne pas perdre de temps dans les interfaces de transport. "
                    ],
                    "trajectories": [
                        {"index": 0, "mode": "Marche à pied", "description": "Trajet direct par les coteaux, 2h15.", "sensitivities": "Gratuit, sûr, mais interminable, inconfortable et indigne du rang social. "},
                        {"index": 1, "mode": "Vélo classique", "description": "35 min, descente le matin, montée raide le soir.", "sensitivities": "Économique, rapide, mais peu pratique (sueur) et sécurité moyenne. "},
                        {"index": 2, "mode": "Vélo Électrique (VAE)", "description": "25 min, effort réduit, stationnement sécurisé.", "sensitivities": "Efficace, moderne, mais image sociale 'sportive' parfois décalée. "},
                        {"index": 3, "mode": "Bus Linéo", "description": "45 min avec correspondance, voie dédiée partielle.", "sensitivities": "Bon marché, écologique, mais lent et jamais synonyme de luxe. "},
                        {"index": 4, "mode": "Voiture personnelle (SUV)", "description": "22 min, cuir, clim, porte-à-porte.", "sensitivities": "Rapide, très pratique, sensation de luxe; pèse sur le budget et l'écologie. "},
                        {"index": 5, "mode": "Covoiturage Premium", "description": "25 min, partage avec un autre cadre du secteur.", "sensitivities": "Réduction coût, confort maintenu, contrainte horaire. "},
                        {"index": 6, "mode": "Train (TER) + Trottinette", "description": "30 min, évite les bouchons du périph.", "sensitivities": "Ponctualité, mais rupture de charge 'peu élégante'. "},
                        {"index": 7, "mode": "Taxi / Uber Berline", "description": "25 min, service avec chauffeur, pas de parking.", "sensitivities": "Luxe total, zéro stress, coût extrêmement élevé. "},
                        {"index": 8, "mode": "Métro Ligne B (depuis Ramonville)", "description": "40 min, parking relais puis souterrain.", "sensitivities": "Rapide, mais environnement sonore et social bruyant. "},
                        {"index": 9, "mode": "Moto / Scooter 300cc", "description": "15 min, remonte-files efficace.", "sensitivities": "Rapidité imbattable, mais équipement lourd (casque) et sécurité faible. "}
                    ]
                },
                {
                    "agent_id": "ag_etudiant_paul_sab",
                    "role": "Étudiant en Master, 22 ans, budget très serré. Sensibilités : économie maximale, rapidité, flexibilité horaire. ",
                    "context": "Trajet entre Saint-Agne et l'Université Paul Sabatier. ",
                    "history": [
                        "Lundi : Bus 44, arrivé avec 10 min de retard au TD. ",
                        "Mardi : Vélo en libre-service, chaîne a déraillé. ",
                        "Mercredi : Marche sous la pluie, chaussures trempées toute la journée. ",
                        "Jeudi : A profité de la voiture d'un ami pour rentrer plus vite. ",
                        "Vendredi : Métro bondé, a dû laisser passer deux rames. ",
                        "Week-end : A travaillé en livraison vélo pour arrondir ses fins de mois. ",
                        "Mois dernier : A perdu sa carte Tisséo, a dû payer le plein tarif pendant 3 jours. ",
                        "Préférence : Le vélo reste le plus fiable pour ne pas rater les examens. ",
                        "Contrainte : Impossible d'envisager la voiture (assurance trop chère). ",
                        "habitude : Utilise les applications de trajet en temps réel constamment. "
                    ],
                    "trajectories": [
                        {"index": 0, "mode": "Marche à pied", "description": "25 min, trajet urbain sécurisé.", "sensitivities": "Gratuit, fiable, bon pour la santé. "},
                        {"index": 1, "mode": "Vélo Personnel", "description": "10 min, cadenas solide requis.", "sensitivities": "Rapidité imbattable sur cette distance, coût quasi nul. "},
                        {"index": 2, "mode": "VélôToulouse (Libre-service)", "description": "12 min, stations aux deux extrémités.", "sensitivities": "Pas de souci de vol, très économique. "},
                        {"index": 3, "mode": "Métro Ligne B", "description": "8 min de station à station.", "sensitivities": "Rapide, climatisé, inclus dans l'abonnement jeune. "},
                        {"index": 4, "mode": "Bus 44", "description": "15 min selon trafic.", "sensitivities": "Pratique si fatigue, mais soumis aux aléas de circulation. "},
                        {"index": 5, "mode": "Trottinette Électrique", "description": "10 min sur piste cyclable.", "sensitivities": "Fun, rapide, mais cher si location à la minute. "},
                        {"index": 6, "mode": "Skateboard / Longboard", "description": "15 min, trottoirs larges.", "sensitivities": "Zéro coût, style de vie, mais dangereux sur chaussée mouillée. "},
                        {"index": 7, "mode": "Covoiturage spontané", "description": "12 min avec d'autres étudiants.", "sensitivities": "Social, gratuit si partage de frais, incertain. "},
                        {"index": 8, "mode": "Bus de nuit", "description": "20 min, fréquence réduite.", "sensitivities": "Essentiel pour les soirées, sentiment de sécurité variable. "},
                        {"index": 9, "mode": "Auto-stop urbain", "description": "Temps aléatoire.", "sensitivities": "Dernier recours, inconfortable socialement. "}
                    ]
                }
            ],
            "parameters": {
                "context": "Mardi matin, 08h15, ciel voilé, trafic dense sur la rocade et les axes entrants. "
            }
        }
    },
    {
        "name": "Scénario 2 — Senior à mobilité réduite (Déplacement Médical)",
        "payload": {
            "category": "itenary_multi_agent",
            "agents": [
                {
                    "agent_id": "ag_senior_toulouse",
                    "role": "Retraité de 74 ans, résidant à Balma. Mobilité réduite suite à une opération de la hanche. Sensibilités : Confort absolu, sécurité physique, évitement des marches et des stations debout prolongées, besoin de calme. ",
                    "context": "Rendez-vous médical de suivi à 14h30 dans une clinique du quartier des Carmes (hyper-centre de Toulouse). [cite: 7, 8]",
                    "history": [
                        "Lundi : A tenté de marcher jusqu'à la boulangerie (150m), a dû s'arrêter deux fois. [cite: 7]",
                        "Mardi : Trajet en voiture avec son fils ; accès difficile car rue piétonne. [cite: 7]",
                        "Mercredi : Journée de repos, douleur persistante à la hanche. [cite: 7]",
                        "Jeudi : A pris le bus ligne 1, mais a dû rester debout (trop de monde) ; expérience épuisante. [cite: 7]",
                        "Vendredi : Consultation à domicile par une infirmière. [cite: 7]",
                        "Il y a 10 jours : Chute légère sur un trottoir mal entretenu en centre-ville. [cite: 7]",
                        "Souvenir : Adorait conduire sa propre voiture, mais a arrêté sur conseil médical il y a 6 mois. [cite: 7]",
                        "Observation : Les pavés du centre-ville de Toulouse sont un calvaire pour sa canne. [cite: 7]",
                        "Crainte : Peur de rater son rendez-vous à cause des retards de transports en commun. [cite: 7]",
                        "Préférence : Le trajet idéal est celui où il marche le moins possible. [cite: 7]"
                    ],
                    "trajectories": [
                        {"index": 0, "mode": "Marche à pied", "description": "Trajet de 1.8km depuis le parking le plus proche.", "sensitivities": "Totalement exclu : douleur insupportable, risque de chute élevé. "},
                        {"index": 1, "mode": "Vélo classique / VAE", "description": "Location sur Balma.", "sensitivities": "Inadapté : équilibre précaire, incapacité physique à pédaler. "},
                        {"index": 2, "mode": "Bus Tisséo (Ligne 1)", "description": "Arrêt à 400m de la clinique.", "sensitivities": "Risqué : distance de marche finale trop longue, incertitude sur la place assise. "},
                        {"index": 3, "mode": "Métro Ligne A + B", "description": "Changement à Jean-Jaurès, beaucoup de couloirs.", "sensitivities": "Inconfortable : les correspondances imposent trop de marche et d'escaliers. "},
                        {"index": 4, "mode": "Voiture personnelle", "description": "Conduite par l'agent, stationnement en surface.", "sensitivities": "Stressant : recherche de place impossible aux Carmes, marche imprévisible. "},
                        {"index": 5, "mode": "Navette centre-ville (électrique)", "description": "Petit format, passe dans les rues étroites.", "sensitivities": "Intéressant : dépose proche, mais horaires peu fréquents et espace réduit. "},
                        {"index": 6, "mode": "Taxi conventionné (Ambulance légère)", "description": "Porte-à-porte, chauffeur formé à l'aide à la personne.", "sensitivities": "Optimal : confort, prise en charge Sécurité Sociale possible, zéro effort. "},
                        {"index": 7, "mode": "Uber / VTC classique", "description": "Prise en charge à domicile, dépose à 20m de l'entrée.", "sensitivities": "Très bon : confort, rapidité, mais coût à charge de l'agent. "},
                        {"index": 8, "mode": "Covoiturage avec un voisin", "description": "Dépose au plus près.", "sensitivities": "Économique, mais contrainte de l'horaire du voisin peu flexible pour un RDV médical. "},
                        {"index": 9, "mode": "Transport à la demande (TAD)", "description": "Service public pour personnes spécifiques.", "sensitivities": "Fiable et adapté, mais nécessite une réservation 24h à l'avance. "},
                        {"index": 10, "mode": "Trottinette en libre-service", "description": "Disponible partout.", "sensitivities": "Extrêmement dangereux : aucun équilibre, proscrit par le médecin. "},
                        {"index": 11, "mode": "TER Balma-Gramont -> Matabiau -> Métro", "description": "Combinaison train + métro.", "sensitivities": "Trop complexe : ruptures de charge épuisantes physiquement. "},
                        {"index": 12, "mode": "Vélo-taxi (Rickshaw)", "description": "Transporteur à vélo dans l'hyper-centre.", "sensitivities": "Original : permet de circuler dans les rues piétonnes, mais exposé au vent/pluie. "},
                        {"index": 13, "mode": "Dépose-minute par un proche", "description": "Arrêt bref devant la clinique.", "sensitivities": "Efficace, mais nécessite la disponibilité totale d'un tiers. "}
                    ]
                }
            ],
            "parameters": {
                "context": "14h15, météo clémente (soleil), mais pavés glissants suite à un nettoyage de voirie aux Carmes. [cite: 8]"
            }
        }
    },
    {
        "name": "Scénario 3 — Stress Test : 5 Agents, Diversité Urbaine",
        "payload": {
            "category": "itenary_multi_agent",
            "agents": [
                {
                    "agent_id": "prof_01",
                    "role": "Professeur de lycée, 45 ans. Sensibilités : Ponctualité absolue (ne peut pas être en retard en cours), prévisibilité du temps de trajet, budget modéré.",
                    "context": "Retour domicile à 18h30 après une réunion parents-profs. Habite à 4km du lycée.",
                    "history": [
                        "Lundi : Bus retardé de 15 min, stress intense devant la classe.",
                        "Mardi : Trajet à vélo sous un beau soleil, trajet très apprécié.",
                        "Mercredi : A dû rester tard pour corriger des copies, trajet de nuit.",
                        "Jeudi : Grève des transports, a dû marcher 45 min.",
                        "Vendredi : Fatigue de fin de semaine, cherche une solution reposante.",
                        "Mois dernier : A acheté un nouveau casque de vélo haute sécurité.",
                        "Observation : Les pistes cyclables sont bien éclairées sur son trajet.",
                        "Crainte : Se faire voler son vélo s'il le laisse trop longtemps dehors.",
                        "Préférence : Le vélo est son mode favori mais dépend de sa fatigue.",
                        "Note : Dispose d'un garage à vélo sécurisé au lycée."
                    ],
                    "trajectories": [
                        {"index": 0, "mode": "Vélo personnel", "description": "12 min, effort modéré.", "sensitivities": "Rapide, fiable, gratuit, mais demande un effort physique."},
                        {"index": 1, "mode": "Marche à pied", "description": "45 min, trajet urbain.", "sensitivities": "Trop long pour une fin de journée fatigante."},
                        {"index": 2, "mode": "Bus Linéo", "description": "20 min, haute fréquence.", "sensitivities": "Reposant, mais risque d'aléa de trafic à 18h30."},
                        {"index": 3, "mode": "Covoiturage collègue", "description": "15 min, porte-à-porte.", "sensitivities": "Social, gratuit, mais dépend de l'horaire du collègue."},
                        {"index": 4, "mode": "Trottinette électrique", "description": "15 min, location.", "sensitivities": "Amusant, rapide, mais coût élevé à l'usage."}
                    ]
                },
                {
                    "agent_id": "tele_01",
                    "role": "Consultant en télétravail, 30 ans. Sensibilités : Évitement de la foule (agoraphobie légère), confort, utilise le trajet pour écouter des podcasts.",
                    "context": "Doit se rendre en centre-ville pour un afterwork exceptionnel à 19h00.",
                    "history": [
                        "A passé 3 jours sans sortir de chez lui (télétravail intensif).",
                        "Dernier trajet en métro : Crise d'anxiété due à l'affluence.",
                        "Préfère marcher même si c'est plus long, pour prendre l'air.",
                        "Possède un casque à réduction de bruit haut de gamme.",
                        "Aime les modes de transport où il peut être 'dans sa bulle'.",
                        "Déteste la pluie car cela gâche l'expérience de marche.",
                        "N'a pas de contrainte budgétaire forte pour ce trajet.",
                        "Utilise souvent les applications pour voir le taux d'occupation des bus.",
                        "A un abonnement VélôToulouse mais l'utilise peu.",
                        "Cherche une transition douce entre le travail et la détente."
                    ],
                    "trajectories": [
                        {"index": 0, "mode": "Métro Ligne A", "description": "10 min, très fréquenté.", "sensitivities": "Rapide mais densité de foule insupportable à 18h30."},
                        {"index": 1, "mode": "Marche à pied", "description": "35 min, quai de la Daurade.", "sensitivities": "Calme, agréable, permet de décompresser totalement."},
                        {"index": 2, "mode": "VélôToulouse", "description": "15 min, stations disponibles.", "sensitivities": "Actif, évite la foule, mais demande de la vigilance."},
                        {"index": 3, "mode": "Uber X", "description": "15 min, climatisé, seul à bord.", "sensitivities": "Confort maximal, bulle privée, coût modéré."},
                        {"index": 4, "mode": "Bus 14", "description": "25 min, souvent plein à cette heure.", "sensitivities": "Incertain concernant l'espace personnel."}
                    ]
                },
                {
                    "agent_id": "livr_01",
                    "role": "Livreur indépendant, 25 ans. Sensibilités : Agilité, connaissance parfaite des raccourcis, résistance physique, rentabilité du temps.",
                    "context": "Fin de service, doit rentrer chez lui pour charger ses batteries.",
                    "history": [
                        "A parcouru 60km aujourd'hui en vélo cargo.",
                        "Connaît chaque nid-de-poule du quartier.",
                        "A déjà eu deux accidents légers avec des portières de voitures.",
                        "Est payé à la course, donc chaque minute compte.",
                        "Adore la sensation de liberté du vélo.",
                        "Est équipé de vêtements techniques haute visibilité.",
                        "Ses jambes sont lourdes après 8h de selle.",
                        "A un accès privilégié à des parkings sécurisés.",
                        "Ne supporte pas d'être enfermé dans un bus lent.",
                        "Doit surveiller l'état d'usure de ses pneus."
                    ],
                    "trajectories": [
                        {"index": 0, "mode": "Vélo Cargo électrique", "description": "Son outil de travail, 10 min.", "sensitivities": "Logique, rapide, mais fatigue physique accumulée."},
                        {"index": 1, "mode": "Tramway T1", "description": "20 min, emporte le vélo à bord.", "sensitivities": "Reposant, permet de charger le téléphone, mais encombrant."},
                        {"index": 2, "mode": "Marche", "description": "40 min.", "sensitivities": "Trop lent pour ses besoins de récupération."},
                        {"index": 3, "mode": "Skate électrique", "description": "12 min.", "sensitivities": "Fun, rapide, demande peu d'effort final."},
                        {"index": 4, "mode": "Bus", "description": "25 min.", "sensitivities": "Perte de temps inacceptable."}
                    ]
                },
                {
                    "agent_id": "tour_01",
                    "role": "Touriste, 55 ans. Sensibilités : Simplicité d'utilisation (ne parle pas bien la langue), sécurité, aspect panoramique/visuel du trajet.",
                    "context": "Retour à l'hôtel après une visite de la Cité de l'Espace.",
                    "history": [
                        "S'est perdu ce matin dans le réseau de bus.",
                        "Trouve les distributeurs de tickets compliqués.",
                        "Veut voir les monuments de la ville pendant le trajet.",
                        "A peur de se faire voler son portefeuille dans le métro.",
                        "Utilise Google Maps en permanence.",
                        "A des chaussures de marche confortables.",
                        "A déjà un ticket 24h illimité.",
                        "Est impressionné par la couleur des briques roses.",
                        "Préfère les trajets directs sans changement.",
                        "Cherche un trajet 'typique' de Toulouse."
                    ],
                    "trajectories": [
                        {"index": 0, "mode": "Téléo (Téléphérique)", "description": "10 min, vue imprenable sur la ville.", "sensitivities": "Expérience unique, simple, sécurisé, très visuel."},
                        {"index": 1, "mode": "Bus 37 + Métro", "description": "35 min, un changement.", "sensitivities": "Compliqué à comprendre, pas de vue intéressante."},
                        {"index": 2, "mode": "Taxi", "description": "20 min, cher.", "sensitivities": "Simple, sécurisé, mais ne voit rien de la ville."},
                        {"index": 3, "mode": "Marche à pied", "description": "1h10.", "sensitivities": "Trop long malgré la beauté des paysages."},
                        {"index": 4, "mode": "VélôToulouse", "description": "30 min.", "sensitivities": "Trop complexe à déverrouiller, peur du trafic."}
                    ]
                },
                {
                    "agent_id": "peri_01",
                    "role": "Habitant de grande périphérie, 50 ans. Sensibilités : Fiabilité des horaires (ne veut pas rater son train), sécurité nocturne, coût du carburant.",
                    "context": "Quitte son bureau en centre-ville pour rejoindre la gare SNCF avant son train de 19h10.",
                    "history": [
                        "A déjà raté son train deux fois le mois dernier.",
                        "Travaille dans une tour de bureaux climatisée.",
                        "Porte un costume et des chaussures de ville en cuir.",
                        "Est abonné aux alertes trafic sur Twitter.",
                        "Déteste courir sur le quai avec son sac d'ordinateur.",
                        "Pense à acheter une voiture électrique l'année prochaine.",
                        "Trouve le centre-ville trop bruyant à l'heure de pointe.",
                        "Est sensible aux économies d'énergie.",
                        "Privilégie les trajets directs vers la gare.",
                        "A besoin de 5 min d'avance sur le quai pour décompresser."
                    ],
                    "trajectories": [
                        {"index": 0, "mode": "Métro Ligne A", "description": "8 min direct vers la gare.", "sensitivities": "Le plus fiable, très rapide, mais bondé."},
                        {"index": 1, "mode": "Marche à pied", "description": "25 min.", "sensitivities": "Sûr mais risque de transpiration en costume, timing serré."},
                        {"index": 2, "mode": "Bus Linéo 1", "description": "15 min.", "sensitivities": "Confortable, mais risque de bouchons à 18h45."},
                        {"index": 3, "mode": "Vélo en libre-service", "description": "12 min.", "sensitivities": "Rapide, mais risque de salir le costume."},
                        {"index": 4, "mode": "Taxi / Uber", "description": "12 min, dépose devant la gare.", "sensitivities": "Confortable, mais soumis aux aléas du trafic urbain."}
                    ]
                }
            ],
            "parameters": {
                "context": "Mardi, 18h30. Beau temps, température 22°C. Pic de pollution niveau 1 (incitation aux modes doux). Trafic très dense sur les boulevards."
            }
        }
    },
    {
        "name": "Scénario 4 — Erreur de Validation (Input vide)",
        "payload": {
            "category": "itenary_multi_agent",
            "agents": [],  # Erreur attendue : la liste doit contenir au moins 1 agent
            "parameters": {
                "context": "Test de robustesse du schéma"
            }
        },
        "expect_status": 422,
        "expected_error_details": {
            "loc": ["body", "agents"],
            "msg": "List should have at least 1 item",
            "type": "value_error"
        }
    },
    {
        "name": "Scénario 5 — Routage Forcé (Groq) : Militant Vélo",
        "payload": {
            "category": "itenary_multi_agent",
            "force_provider": "groq",  # Test de l'injection forcée du fournisseur
            "agents": [
                {
                    "agent_id": "ag_militant_velo",
                    "role": "Cycliste militant, 32 ans, membre d'une association de promotion du vélo urbain. Sensibilités : Écologie radicale, rejet des énergies fossiles, valorisation de l'effort physique, allergie aux retards des transports en commun.",
                    "context": "Doit se rendre à une réunion associative en centre-ville à 20h00.",
                    "history": [
                        "Lundi : A participé à une 'Vélorution' dans les rues de Toulouse.",
                        "Mardi : A réparé une crevaison en un temps record de 4 minutes.",
                        "Mercredi : A testé le bus électrique mais a trouvé le trajet 'trop passif'.",
                        "Jeudi : A convaincu deux collègues de passer au vélo pour le vélotaf.",
                        "Vendredi : Trajet de 20km sous une pluie battante, n'a pas renoncé.",
                        "Samedi : A milité pour la création d'une nouvelle piste cyclable sécurisée.",
                        "Note : Possède un vélo de route haute performance et un équipement complet.",
                        "Observation : Considère la voiture individuelle comme une aberration urbaine.",
                        "Crainte : Le manque de stationnement sécurisé (peur du vol de ses composants).",
                        "Préférence : Veut rester l'acteur de son propre mouvement."
                    ],
                    "trajectories": [
                        {"index": 0, "mode": "Vélo personnel", "description": "12 min, trajet direct par les boulevards.", "sensitivities": "Écologie totale, rapidité, plaisir de l'effort, mais risque de vol élevé."},
                        {"index": 1, "mode": "Bus électrique (Linéo)", "description": "22 min, zéro émission locale.", "sensitivities": "Écologique et confortable, mais perçu comme moins direct et trop passif."},
                        {"index": 2, "mode": "Marche à pied", "description": "45 min par le centre historique.", "sensitivities": "Sûr et écologique, mais trop lent pour son tempérament actif."},
                        {"index": 3, "mode": "VélôToulouse (VLS)", "description": "15 min, station à 50m.", "sensitivities": "Écologique, évite de risquer son propre vélo contre le vol."},
                        {"index": 4, "mode": "Covoiturage électrique", "description": "15 min.", "sensitivities": "Mieux que le thermique, mais reste une voiture (encombrement de l'espace)."},
                        {"index": 5, "mode": "Métro Ligne B", "description": "10 min.", "sensitivities": "Efficace, mais environnement souterrain déconnecté de la ville."},
                        {"index": 6, "mode": "Trottinette personnelle", "description": "15 min.", "sensitivities": "Électrique, agile, mais moins gratifiant que le vélo."},
                        {"index": 7, "mode": "Taxi hybride", "description": "18 min.", "sensitivities": "Rejeté par principe sauf urgence absolue."},
                        {"index": 8, "mode": "Vélo-cargo partagé", "description": "15 min, permet de transporter du matériel de réunion.", "sensitivities": "Très utile, aligné avec ses valeurs associatives."},
                        {"index": 9, "mode": "Course à pied", "description": "25 min.", "sensitivities": "Sportif, mais nécessite une douche à l'arrivée."}
                    ]
                }
            ],
            "parameters": {
                "context": "Soirée de printemps, 19h45, conditions idéales pour le vélo."
            }
        }
    }
]

# ---------------------------------------------------------------------------
# Résultat d'un test
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    scenario_name: str
    task_id: Optional[str]      = None
    final_status: Optional[str] = None
    provider_used: Optional[str]= None
    latency_ms: Optional[float] = None
    agents_count: int            = 0
    error: Optional[str]        = None
    elapsed_s: float             = 0.0
    passed: bool                 = False


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

def submit_task(client: httpx.Client, payload: dict, expect_http: int = 202) -> Optional[str]:
    """Envoie la requête POST et retourne le task_id, ou None si erreur attendue."""
    resp = client.post(f"{BASE_URL}/tasks", json=payload)

    if resp.status_code != expect_http:
        print(f"  ✗ HTTP {resp.status_code} (attendu {expect_http})")
        print(f"    {resp.text[:300]}")
        return None

    if expect_http != 202:
        print(f"  ✓ Erreur attendue reçue : HTTP {resp.status_code}")
        return "EXPECTED_ERROR"

    data = resp.json()
    task_id = data["task_id"]
    print(f"  → task_id : {task_id}")
    return task_id


def poll_task(client: httpx.Client, task_id: str) -> dict:
    """Poll jusqu'à completion ou timeout."""
    deadline = time.monotonic() + POLL_TIMEOUT
    attempt  = 0

    while time.monotonic() < deadline:
        attempt += 1
        resp = client.get(f"{BASE_URL}/tasks/{task_id}")
        resp.raise_for_status()
        data = resp.json()

        status = data["status"]
        print(f"  [poll #{attempt}] status={status}", end="")

        if status in ("success", "failed"):
            print()
            return data

        print(f"  (retry dans {POLL_INTERVAL}s...)")
        time.sleep(POLL_INTERVAL)

    return {"status": "timeout", "error": f"Timeout après {POLL_TIMEOUT}s"}


def check_health(client: httpx.Client) -> bool:
    try:
        resp = client.get(f"{BASE_URL}/health", timeout=3.0)
        data = resp.json()
        print(f"  API : {data['status']}")
        for provider, info in data.get("providers", {}).items():
            print(f"  {provider:10s} rpm={info['current_rpm']}/{info['rpm_limit']}  available={info['available']}")
        return True
    except Exception as e:
        print(f"  ✗ API inaccessible : {e}")
        return False


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_scenario(client: httpx.Client, scenario: dict, force_provider: Optional[str] = None) -> TestResult:
    name    = scenario["name"]
    payload = scenario["payload"].copy()
    expect  = scenario.get("expect_status", 202)

    if force_provider:
        payload["force_provider"] = force_provider

    print(f"\n{'─' * 60}")
    print(f"  {name}")
    print(f"{'─' * 60}")

    result = TestResult(scenario_name=name)
    t0 = time.monotonic()

    # Soumission
    task_id = submit_task(client, payload, expect_http=expect)

    if task_id is None:
        result.error   = "Soumission échouée"
        result.elapsed_s = time.monotonic() - t0
        return result

    if task_id == "EXPECTED_ERROR":
        result.passed    = True
        result.final_status = f"HTTP {expect} (attendu)"
        result.elapsed_s = time.monotonic() - t0
        return result

    result.task_id = task_id

    # Polling
    data = poll_task(client, task_id)
    result.elapsed_s  = time.monotonic() - t0
    result.final_status = data.get("status")
    result.provider_used = data.get("provider_used")
    result.latency_ms    = data.get("latency_ms")
    result.error         = data.get("error")

    if data.get("result"):
        result.agents_count = len(data["result"])
        print(f"\n  Réponses des agents :")
        for agent in data["result"]:
            print(f"    [{agent['agent_id']}] {agent['chosen_index']} - {agent['mode']}: {agent['reason'][:120]}{'...' if len(agent['reason']) > 120 else ''}")

    result.passed = result.final_status == "success"
    return result


def print_summary(results: list[TestResult]) -> None:
    print(f"\n{'═' * 60}")
    print("  RÉSUMÉ")
    print(f"{'═' * 60}")

    passed = sum(1 for r in results if r.passed)
    total  = len(results)

    for r in results:
        icon = "✓" if r.passed else "✗"
        provider = f"[{r.provider_used}]" if r.provider_used else ""
        latency  = f"{r.latency_ms:.0f}ms" if r.latency_ms else ""
        print(f"  {icon} {r.scenario_name}")
        if r.error and not r.passed:
            print(f"      erreur : {r.error}")
        elif r.passed:
            details = " | ".join(filter(None, [provider, latency, f"{r.agents_count} agents" if r.agents_count else None]))
            print(f"      {details}")

    print(f"\n  {passed}/{total} scénarios passés  ({r.elapsed_s:.1f}s total)")
    print(f"{'═' * 60}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    global BASE_URL

    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=int, help="Numéro du scénario (1-based)")
    parser.add_argument("--provider", type=str, help="Forcer un provider pour tous les scénarios")
    parser.add_argument("--base-url", type=str, default=BASE_URL)
    args = parser.parse_args()

    BASE_URL = args.base_url

    print(f"\n{'═' * 60}")
    print("  LLM MODULE — Tests end-to-end")
    print(f"  {BASE_URL}")
    print(f"{'═' * 60}")

    with httpx.Client(timeout=90.0) as client:

        # Healthcheck
        print("\n[Healthcheck]")
        if not check_health(client):
            print("\nArrêt : l'API n'est pas joignable.")
            sys.exit(1)

        # Sélection des scénarios
        scenarios = SCENARIOS
        if args.scenario:
            idx = args.scenario - 1
            if idx < 0 or idx >= len(SCENARIOS):
                print(f"Scénario {args.scenario} inexistant (1-{len(SCENARIOS)}).")
                sys.exit(1)
            scenarios = [SCENARIOS[idx]]

        # Exécution
        results = []
        for scenario in scenarios:
            result = run_scenario(client, scenario, force_provider=args.provider)
            results.append(result)

        print_summary(results)

    failed = sum(1 for r in results if not r.passed)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()