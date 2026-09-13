import json
from pathlib import Path

modes_canon = ['walking', 'cycling', 'car', 'public_transport', 'train']

results_dir = Path('scratch/mutations/results')
for res_file in sorted(results_dir.glob('*_evaluated.json')):
    data = json.load(open(res_file))
    mutation = data.get('mutation', res_file.stem)
    agents = data.get('agents', [])
    print(f"=== {mutation} ({len(agents)} personas) ===")
    
    # We can match with original cases
    # Each agent has probabilities
    total_modes = {m: 0.0 for m in modes_canon}
    for a in agents:
        agent_modes = {m: 0.0 for m in modes_canon}
        for p in a.get('probabilities', []):
            m = p.get('mode', '')
            prob = float(p.get('probability', 0.0))
            if 'foot' in m or 'walk' in m:
                if 'bus' in m or 'metro' in m or 'tram' in m:
                    agent_modes['public_transport'] += prob
                elif 'rail' in m or 'train' in m:
                    agent_modes['train'] += prob
                else:
                    agent_modes['walking'] += prob
            elif 'bike' in m or 'bicycle' in m:
                agent_modes['cycling'] += prob
            elif 'car' in m:
                agent_modes['car'] += prob
            elif any(k in m for k in ['bus', 'metro', 'tram']):
                agent_modes['public_transport'] += prob
            elif 'rail' in m or 'train' in m:
                agent_modes['train'] += prob
        for m in modes_canon:
            total_modes[m] += agent_modes[m]
    
    n = len(agents) if agents else 1
    avg_after = {m: round(total_modes[m] / n, 1) for m in modes_canon}
    print(f"  Distribution moyenne après mutation: {avg_after}")
