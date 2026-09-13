import json
from collections import defaultdict

categories = {
    'seniors': [],
    'achats': [],
    'proximite': [],
    'actifs_navette': [],
    'abonnes_courts': []
}

seen_ids = {k: set() for k in categories}

with open('data/experiences/exp_gemini-35-fl_expcham6_jtir_t0_nosim/executions/2026-09-09_13_36_40/decisions.jsonl') as f:
    for line in f:
        d = json.loads(line)
        if d.get('methode') != 'decideur':
            continue
        pres = d.get('presente')
        if not pres: continue
        payload = pres.get('payload')
        if not payload: continue
        agents = payload.get('agents', [])
        if not agents: continue
        p = agents[0]
        pid = str(d['person_id'])
        perception = p.get('perception', '')
        dest = d.get('purpose', '')
        dist = d.get('distribution', {})
        trajs = p.get('trajectories', [])
        foot_trajs = [t for t in trajs if t.get('mode') == 'foot']
        foot_dist = foot_trajs[0].get('total_distance_m', 0) if foot_trajs else None
        car_trajs = [t for t in trajs if t.get('mode') == 'car']
        pt_trajs = [t for t in trajs if any(k in t.get('mode', '') for k in ['bus', 'metro', 'tram', 'rail'])]
        
        # 1. Seniors (distinct person_id)
        if len(categories['seniors']) < 20 and pid not in seen_ids['seniors']:
            if ('Retraité' in perception or any(int(a) >= 65 for a in perception.split() if a.isdigit())):
                if dist.get('public_transport', 0) >= 0.35 and foot_dist and foot_dist <= 3000:
                    categories['seniors'].append({
                        'person_id': pid,
                        'perception': perception,
                        'purpose': dest,
                        'dist_origin': dist,
                        'foot_dist': foot_dist,
                        'trajs': trajs,
                        'context': p.get('context'),
                        'day_outlook': p.get('day_outlook')
                    })
                    seen_ids['seniors'].add(pid)
        
        # 2. Achats (distinct person_id)
        if len(categories['achats']) < 20 and pid not in seen_ids['achats']:
            if dest in ('shop', 'achats'):
                if dist.get('public_transport', 0) >= 0.35:
                    categories['achats'].append({
                        'person_id': pid,
                        'perception': perception,
                        'purpose': dest,
                        'dist_origin': dist,
                        'foot_dist': foot_dist,
                        'trajs': trajs,
                        'context': p.get('context'),
                        'day_outlook': p.get('day_outlook')
                    })
                    seen_ids['achats'].add(pid)

        # 3. Proximite (distinct person_id)
        if len(categories['proximite']) < 20 and pid not in seen_ids['proximite']:
            if foot_dist and 700 <= foot_dist <= 2200:
                if dist.get('public_transport', 0) >= 0.35:
                    categories['proximite'].append({
                        'person_id': pid,
                        'perception': perception,
                        'purpose': dest,
                        'dist_origin': dist,
                        'foot_dist': foot_dist,
                        'trajs': trajs,
                        'context': p.get('context'),
                        'day_outlook': p.get('day_outlook')
                    })
                    seen_ids['proximite'].add(pid)

        # 4. Actifs navette travail (distinct person_id)
        if len(categories['actifs_navette']) < 20 and pid not in seen_ids['actifs_navette']:
            if dest == 'work' and 'plein temps' in perception:
                if dist.get('public_transport', 0) >= 0.35 and car_trajs:
                    categories['actifs_navette'].append({
                        'person_id': pid,
                        'perception': perception,
                        'purpose': dest,
                        'dist_origin': dist,
                        'foot_dist': foot_dist,
                        'trajs': trajs,
                        'context': p.get('context'),
                        'day_outlook': p.get('day_outlook')
                    })
                    seen_ids['actifs_navette'].add(pid)

        # 5. Abonnes courts (distinct person_id)
        if len(categories['abonnes_courts']) < 20 and pid not in seen_ids['abonnes_courts']:
            if any('Abonné aux transports en commun' in t.get('description', '') for t in trajs):
                if foot_dist and foot_dist <= 2500 and dist.get('public_transport', 0) >= 0.4:
                    categories['abonnes_courts'].append({
                        'person_id': pid,
                        'perception': perception,
                        'purpose': dest,
                        'dist_origin': dist,
                        'foot_dist': foot_dist,
                        'trajs': trajs,
                        'context': p.get('context'),
                        'day_outlook': p.get('day_outlook')
                    })
                    seen_ids['abonnes_courts'].add(pid)

for k, v in categories.items():
    print(f'{k:20s}: {len(v)} distinct persons')

with open('data/cases_20_unique_per_mutation.json', 'w') as f:
    json.dump(categories, f, indent=2)
