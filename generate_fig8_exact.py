import csv
import os
from collections import defaultdict
from datetime import datetime, timedelta

MOVES_FILE = "experiments/archive/2026-09-18_14_31/moves.csv"
OUT_DIR = "/Users/yvesb/.gemini/antigravity/brain/9bee725f-5da0-40f3-8eb0-fbc8a96618f3"

# All calendar dates from 2026-03-16 to 2026-04-06
start_dt = datetime(2026, 3, 16)
end_dt = datetime(2026, 4, 6)
all_dates = []
curr = start_dt
while curr <= end_dt:
    all_dates.append(curr.strftime("%Y-%m-%d"))
    curr += timedelta(days=1)

moves = list(csv.DictReader(open(MOVES_FILE)))

def map_mode_name(code):
    c = code.lower().strip()
    if c == "car": return "Voiture"
    if c == "bicycle": return "Vélo"
    if c == "foot": return "Marche seule"
    # transit legs
    legs = [p for p in c.split(",") if p.strip() != "foot"]
    leg_names = []
    for l in legs:
        if l == "bus": leg_names.append("Bus")
        elif l == "metro": leg_names.append("Métro")
        elif l == "tram": leg_names.append("Tram")
        elif l == "rail" or l == "train": leg_names.append("Train")
        else: leg_names.append(l.capitalize())
    if not leg_names:
        return "Marche"
    return " + ".join(leg_names)

activities = {
    "work_07h": {
        "title": "Activité 1 : Domicile ➔ Travail (07:12)",
        "sub": "Figure 8.1 : Trajet pendulaire aller (8.69 km) — Corinne de la Richard",
        "filter": lambda m: int(m["Heure de départ"][11:13]) < 10,
        "filename": "fig8_work_07h.svg"
    },
    "home_18h": {
        "title": "Activité 2 : Travail ➔ Domicile (18:32)",
        "sub": "Figure 8.2 : Trajet pendulaire retour (8.02 km) — Corinne de la Richard",
        "filter": lambda m: 17 <= int(m["Heure de départ"][11:13]) <= 19 and m["Motifs de déplacement"] == "home",
        "filename": "fig8_home_18h.svg"
    },
    "leisure_19h": {
        "title": "Activité 3 : Domicile ➔ Loisir (19:51)",
        "sub": "Figure 8.3 : Sortie loisir en soirée (1.05 km) — Corinne de la Richard",
        "filter": lambda m: m["Motifs de déplacement"] == "leisure",
        "filename": "fig8_leisure_19h.svg"
    },
    "home_20h": {
        "title": "Activité 4 : Loisir ➔ Domicile (20:45)",
        "sub": "Figure 8.4 : Retour de loisir nocturne (1.01 km) — Corinne de la Richard",
        "filter": lambda m: int(m["Heure de départ"][11:13]) >= 20 and m["Motifs de déplacement"] == "home",
        "filename": "fig8_home_20h.svg"
    }
}

for act_key, act_cfg in activities.items():
    act_moves = [m for m in moves if act_cfg["filter"](m)]
    
    # Collect all available options across all days
    # Format: label -> order
    all_options_set = set()
    day_avail = defaultdict(set)
    day_sel = defaultdict(str)
    
    for m in act_moves:
        d = m["Heure de départ"][:10]
        # chosen
        chosen_mode = m["Mode de transport Choisi"]
        # parse options
        raw_opts = m["Options (descriptif)"]
        opts = []
        for p in raw_opts.split(" | "):
            if not p.strip(): continue
            chunks = p.split(":")
            if len(chunks) >= 2:
                opts.append(chunks[1])
        
        # determine which option was selected
        sel_idx = m["Index retenu"].strip()
        if sel_idx and sel_idx.isdigit() and int(sel_idx) < len(opts):
            sel_opt = opts[int(sel_idx)]
        else:
            # fallback match by mode
            sel_opt = "car" if "voiture" in chosen_mode.lower() else ("bicycle" if "vélo" in chosen_mode.lower() else ("foot" if "marche" in chosen_mode.lower() else (opts[0] if opts else "transit")))
            for o in opts:
                if chosen_mode.lower() in o.lower():
                    sel_opt = o
                    break
        
        sel_lbl = map_mode_name(sel_opt)
        day_sel[d] = sel_lbl
        
        for o in opts:
            lbl = map_mode_name(o)
            all_options_set.add(lbl)
            day_avail[d].add(lbl)
            
    # Sort options logically: Car first, then transit combinations, then Bicycle, then Walk
    def opt_sort_key(lbl):
        if "Voiture" in lbl: return (0, lbl)
        if "Métro" in lbl or "Bus" in lbl or "Tram" in lbl or "Train" in lbl: return (1, lbl)
        if "Vélo" in lbl: return (2, lbl)
        return (3, lbl)
        
    sorted_options = sorted(all_options_set, key=opt_sort_key)
    
    # Render exact Figure 8 SVG (Monochrome paper style)
    cell_w = 34
    cell_h = 32
    label_w = 280
    header_h = 65
    footer_h = 45
    width = label_w + len(all_dates) * cell_w + 30
    height = header_h + len(sorted_options) * cell_h + footer_h
    
    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="background-color: #FFFFFF; font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, Helvetica, Arial, sans-serif;">')
    svg.append('<defs>')
    svg.append('  <pattern id="weekend-hatch" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">')
    svg.append('    <line x1="0" y1="0" x2="0" y2="8" stroke="#D5D8DC" stroke-width="2.5" />')
    svg.append('  </pattern>')
    svg.append('</defs>')
    
    # White background
    svg.append(f'<rect width="{width}" height="{height}" fill="#FFFFFF"/>')
    
    # Title & Subtitle
    svg.append(f'<text x="20" y="28" font-size="15" font-weight="700" fill="#1A1A1A">{act_cfg["title"]}</text>')
    svg.append(f'<text x="20" y="44" font-size="11" fill="#666666">{act_cfg["sub"]}</text>')
    
    grid_x0 = label_w
    grid_y0 = header_h
    
    # Column headers (Days)
    for c_idx, dt_str in enumerate(all_dates):
        dt = datetime.strptime(dt_str, "%Y-%m-%d")
        cx = grid_x0 + c_idx * cell_w
        is_wk = (dt.weekday() >= 5)
        is_shk = (dt_str in ("2026-03-23", "2026-03-24"))
        
        # Hatch weekends
        if is_wk:
            svg.append(f'<rect x="{cx}" y="{grid_y0}" width="{cell_w}" height="{len(sorted_options)*cell_h}" fill="url(#weekend-hatch)" opacity="0.9"/>')
            
        # Shock highlight background
        if is_shk:
            svg.append(f'<rect x="{cx}" y="{grid_y0}" width="{cell_w}" height="{len(sorted_options)*cell_h}" fill="#FADBD8" opacity="0.35"/>')
            
        # Day labels (e.g. 03/16)
        date_lbl = dt.strftime("%m/%d")
        lbl_color = "#900C3F" if is_shk else ("#888888" if is_wk else "#222222")
        font_wt = "700" if is_shk else "500"
        svg.append(f'<text x="{cx + cell_w/2}" y="{grid_y0 - 8}" text-anchor="middle" font-size="9.5" font-weight="{font_wt}" fill="{lbl_color}">{date_lbl}</text>')
        
    # Shock banner
    shk_x1 = grid_x0 + all_dates.index("2026-03-23") * cell_w
    shk_w = 2 * cell_w
    svg.append(f'<rect x="{shk_x1}" y="{grid_y0 - 24}" width="{shk_w}" height="12" rx="2" fill="#900C3F"/>')
    svg.append(f'<text x="{shk_x1 + shk_w/2}" y="{grid_y0 - 15}" text-anchor="middle" font-size="8" font-weight="700" fill="#FFFFFF">⚡ CHOC</text>')
    
    # Grid and cells
    for r_idx, opt_lbl in enumerate(sorted_options):
        ry = grid_y0 + r_idx * cell_h
        
        # Row label (left-aligned)
        svg.append(f'<text x="{grid_x0 - 12}" y="{ry + cell_h/2 + 4}" text-anchor="end" font-size="11" font-weight="500" fill="#222222">{opt_lbl}</text>')
        
        for c_idx, dt_str in enumerate(all_dates):
            cx = grid_x0 + c_idx * cell_w
            dt = datetime.strptime(dt_str, "%Y-%m-%d")
            is_wk = (dt.weekday() >= 5)
            
            # cell border
            svg.append(f'<rect x="{cx}" y="{ry}" width="{cell_w}" height="{cell_h}" fill="none" stroke="#ECEFF1" stroke-width="0.8"/>')
            
            if is_wk:
                continue
                
            is_avail = (opt_lbl in day_avail[dt_str])
            is_sel = (opt_lbl == day_sel[dt_str])
            
            if is_sel:
                # Dark red / burgundy for Selected (Paper S)
                svg.append(f'<rect x="{cx + 2}" y="{ry + 2}" width="{cell_w - 4}" height="{cell_h - 4}" rx="2" fill="#962828"/>')
                svg.append(f'<text x="{cx + cell_w/2}" y="{ry + cell_h/2 + 4.5}" text-anchor="middle" font-size="11" font-weight="800" fill="#FFFFFF">S</text>')
            elif is_avail:
                # Salmon / rose for Available (Paper A)
                svg.append(f'<rect x="{cx + 2}" y="{ry + 2}" width="{cell_w - 4}" height="{cell_h - 4}" rx="2" fill="#E8928A"/>')
                svg.append(f'<text x="{cx + cell_w/2}" y="{ry + cell_h/2 + 4}" text-anchor="middle" font-size="10.5" font-weight="700" fill="#FFFFFF">A</text>')
                
    # Legend at bottom matching the exact Figure 8 caption
    caption_y = grid_y0 + len(sorted_options) * cell_h + 24
    svg.append(f'<text x="20" y="{caption_y}" font-size="10.5" fill="#333333"><tspan font-weight="700">Figure 8:</tspan> The analysis of a single trip made by an agent over days. <tspan font-weight="700">A</tspan> marks the suggestions from OpenTripPlanner, <tspan font-weight="700">S</tspan> marks the option chosen by the agent, and the hatched cells represent the weekends.</text>')
    
    svg.append('</svg>')
    
    out_svg_path = os.path.join(OUT_DIR, act_cfg["filename"])
    with open(out_svg_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))
    print(f"Generated: {out_svg_path}")

