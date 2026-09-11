import json
import sys
from pathlib import Path

sys.path.extend(['mobility_llm/src', 'llm-agents', 'llm_gateway/src'])
from mobility_llm import prompt_manager, CATEGORIES
cat = CATEGORIES['itinary_multi_agent']
pm = prompt_manager()

with open('data/cases_20_unique_per_mutation.json') as f:
    cases = json.load(f)

base_m6 = pm.get_system_prompt('itinary_multi_agent', 'expert_chaine_m6')

mutations = {
    'M1_proximite_rabattement': {
        'cat': 'proximite',
        'old': "- Friction d'accès brute (temps d'approche, stationnement, correspondances).",
        'new': "- Proportionnalité de l'effort et friction de rabattement : Compare la marche d'approche et terminale contenue dans l'option collective à la marche directe. Si le transport collectif impose une marche d'accès qui représente la majeure partie du trajet direct pour seulement quelques minutes à bord, le recours au véhicule motorisé collectif relève de la friction inutile : l'usager subit la marche, l'attente et la rupture de charge sans bénéfice d'effort réel."
    },
    'M2_achats_logistique': {
        'cat': 'achats',
        'old': "- Filtre de sécurité : Élimine les options présentant des risques (accident de vélo en l'absence de pistes cyclables, vols, marche dans des zones peu sûres la nuit, etc.).",
        'new': "- Filtre de sécurité : Élimine les options présentant des risques (accident de vélo en l'absence de pistes cyclables, vols, marche dans des zones peu sûres la nuit, etc.).\n- Logistique d'emport et charge utile des motifs : Intègre la contrainte matérielle liée au motif du déplacement (courses alimentaires, sacs, cabas, matériel de travail, bagages). Voyager debout dans une rame bondée, monter des marches et marcher jusqu'à l'arrêt les bras chargés constitue une forte contrainte physique. Pour les achats et l'approvisionnement, l'arbitrage privilégie naturellement l'accès direct sans rupture : la marche directe pour la proximité immédiate de quartier, ou le véhicule individuel pour son volume de coffre et l'absence de portage."
    },
    'M3_seniors_autonomie': {
        'cat': 'seniors',
        'old': "- Confort, effort et pénibilité senior : Compare l'effort continu d'une marche à son propre rythme à la pénibilité composée d'un trajet collectif : rejoindre l'arrêt, attendre debout, monter des marches, voyager secoué debout et correspondre. Pour un senior ou une personne fragile, l'enchaînement physique d'un transport collectif est souvent plus fatigant et stressant qu'une marche directe de courte durée.",
        'new': "- Préservation, rythme personnel et autonomie des aînés : Chez les personnes âgées ou fragiles, la marche à son propre rythme, continue et interruptible, est le mode préférentiel d'autonomie et de maintien physique sur les sorties de proximité. À l'inverse, l'enchaînement des transports collectifs (marches hautes des véhicules, risque de chute aux freinages, bousculades, attente debout sans banc) constitue une source majeure de stress physique et d'insécurité motrice, bien plus dissuasive qu'une marche tranquille."
    },
    'M4_abonnes_sunk_costs': {
        'cat': 'abonnes_courts',
        'old': "- Coût réel et arbitrage d'équipement : Un abonnement de transport ou un véhicule personnel rend une option disponible et limite son coût marginal sur les longs trajets. Il n'exerce aucune attraction sur les trajets locaux de proximité où les modes doux sont déjà gratuits, immédiats et sans réservation. L'équipement est un facilitateur de distance, non une préférence de mode.",
        'new': "- Coût marginal réel et neutralité de l'équipement : La possession d'un abonnement est un coût fixe déjà engagé, qui ne crée aucun gain marginal à être utilisé sur des parcours où la marche est déjà intrinsèquement gratuite, immédiate et sans attente. On n'« amortit » pas un abonnement en subissant l'attente d'un bus pour une courte liaison. De même, les revenus modestes n'orientent pas vers les transports collectifs lorsque les modes actifs offrent une gratuité totale et une maîtrise absolue du temps."
    },
    'M5_actifs_valeur_temps': {
        'cat': 'actifs_navette',
        'old': "- Contraintes horaires et flexibilité des actifs : Pour un actif en trajet travail ou à horaire contraint, la garantie de l'horaire, la flexibilité de départ et la capacité d'emport pèsent fortement en faveur de l'autonomie (voiture ou mode direct), alors que les transports collectifs imposent des marges de sécurité contre les retards.",
        'new': "- Valeur du temps de vie et compétitivité des actifs : Pour un actif engagé dans une journée professionnelle ou familiale, le temps de trajet retranché sur le repos et la vie personnelle a une valeur critique. Quand un transport collectif double ou triple la durée porte-à-porte par rapport à un véhicule individuel disponible, l'usager arbitre en faveur du mode le plus économe en temps de vie, sauf contrainte rédhibitoire de stationnement ou de congestion majeure."
    }
}

for m_key, m_val in mutations.items():
    cat_name = m_val['cat']
    sample_cases = cases[cat_name]
    mutated_prompt = base_m6.replace(m_val['old'], m_val['new'], 1)
    
    # 2 chunks of 10
    chunks = [sample_cases[:10], sample_cases[10:20]]
    for idx, chunk in enumerate(chunks):
        items = []
        for c in chunk:
            item = {
                'agent_id': str(c['person_id']),
                'perception': c['perception'],
                'destination': c['purpose'],
                'destination_zone': None,
                'departure_time': '08:00',
                'departure_timestamp': 1773733000.0,
                'current_time': '08:00',
                'context': c['context'] or '',
                'day_outlook': c.get('day_outlook') or '',
                'agenda': [],
                'history': [],
                'trajectories': c['trajs']
            }
            items.append(cat.item_model(**item))
        params = {'temperature': 0.0, 'top_p': 1.0, 'max_tokens': 4096, 'prompt_variant': 'expert_chaine_m6'}
        rendered = pm.render('itinary_multi_agent', items, params)
        
        batch_data = {
            'mutation': m_key,
            'chunk_index': idx,
            'agent_ids': [str(c['person_id']) for c in chunk],
            'system_prompt': mutated_prompt,
            'user_prompt': rendered[1].content,
            'personas_info': [{'id': str(c['person_id']), 'perception': c['perception'], 'purpose': c['purpose'], 'dist_origin': c['dist_origin']} for c in chunk]
        }
        with open(f'scratch/mutations/{m_key}_chunk{idx}.json', 'w') as out_f:
            json.dump(batch_data, out_f, indent=2)
        print(f"Written scratch/mutations/{m_key}_chunk{idx}.json with {len(chunk)} personas")

print("All 10-persona chunks generated!")
