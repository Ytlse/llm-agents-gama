"""
Analyse de la densité de déplacements de la population toulousaine
pour définir une bounding box basée sur un percentile des flux.

Usage:
    python scripts/analyze_mobility_bbox.py [--population data/eqasim_output/toulouse_population_5194.json]
                                            [--percentile 95]
                                            [--output scripts/bbox_analysis.png]
"""

import json
import math
import argparse
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

# ── Constantes géographiques ───────────────────────────────────────────────────
TOULOUSE_CENTER = (43.6047, 1.4442)   # Place du Capitole (lat, lon)

# Rayons des couronnes (km)
RINGS = {
    "Centre\n(<5 km)":        (0,  5),
    "1ère couronne\n(5–15 km)": (5, 15),
    "2ème couronne\n(15–30 km)":(15, 30),
    "3ème couronne\n(30–50 km)":(30, 50),
    "Au-delà\n(>50 km)":      (50, 999),
}
RING_COLORS = ["#2ecc71", "#3498db", "#9b59b6", "#e67e22", "#e74c3c"]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def dist_from_center(lat: float, lon: float) -> float:
    return haversine_km(TOULOUSE_CENTER[0], TOULOUSE_CENTER[1], lat, lon)


def ring_label(d: float) -> str:
    for label, (lo, hi) in RINGS.items():
        if lo <= d < hi:
            return label
    return list(RINGS.keys())[-1]


def compute_bbox_from_percentile(lats: list, lons: list, pct: float) -> dict:
    """
    Calcule une bbox symétrique basée sur les percentiles de distance au centre,
    puis convertit en coordonnées lat/lon pour la bbox rectangulaire englobante.
    """
    lo_lat = np.percentile(lats, (100 - pct) / 2)
    hi_lat = np.percentile(lats, 100 - (100 - pct) / 2)
    lo_lon = np.percentile(lons, (100 - pct) / 2)
    hi_lon = np.percentile(lons, 100 - (100 - pct) / 2)
    return {"min_lat": lo_lat, "max_lat": hi_lat, "min_lon": lo_lon, "max_lon": hi_lon}


def load_data(path: str):
    with open(path) as f:
        population = json.load(f)

    home_locs, activity_locs, trips = [], [], []

    for person in population:
        identity = person.get("identity", {})
        home = identity.get("home")
        activities = identity.get("activities", [])

        if not home:
            continue

        h_lat, h_lon = home["lat"], home["lon"]
        home_locs.append((h_lat, h_lon))

        prev_loc = (h_lat, h_lon)
        for act in activities:
            loc = act.get("location")
            if not loc:
                continue
            a_lat, a_lon = loc["lat"], loc["lon"]
            activity_locs.append((a_lat, a_lon, act.get("purpose", "unknown")))

            # Distance du trajet (OD crow-fly)
            trip_dist = haversine_km(prev_loc[0], prev_loc[1], a_lat, a_lon)
            trip_dest_dist = dist_from_center(a_lat, a_lon)
            trips.append({
                "dist_km": trip_dist,
                "dest_dist_center_km": trip_dest_dist,
                "purpose": act.get("purpose", "unknown"),
                "dest_lat": a_lat,
                "dest_lon": a_lon,
            })
            prev_loc = (a_lat, a_lon)

    return home_locs, activity_locs, trips


def main(population_path: str, percentile: float, output_path: str):
    print(f"Chargement de {population_path} ...")
    home_locs, activity_locs, trips = load_data(population_path)
    n_persons = len(home_locs)
    print(f"  {n_persons} personnes, {len(activity_locs)} activités, {len(trips)} trajets")

    # ── Calcul des distances au centre ────────────────────────────────────────
    home_dists  = [dist_from_center(lat, lon) for lat, lon in home_locs]
    act_dists   = [dist_from_center(lat, lon, ) for lat, lon, _ in activity_locs]
    dest_dists  = [t["dest_dist_center_km"] for t in trips]
    trip_lengths = [t["dist_km"] for t in trips]

    # Toutes les localisations confondues (domiciles + destinations)
    all_lats = [lat for lat, lon in home_locs] + [lat for lat, lon, _ in activity_locs]
    all_lons = [lon for lat, lon in home_locs] + [lon for lat, lon, _ in activity_locs]

    # ── Percentiles clés ──────────────────────────────────────────────────────
    p_home   = np.percentile(home_dists, percentile)
    p_dest   = np.percentile(dest_dists, percentile)
    p_trip   = np.percentile(trip_lengths, percentile)
    p_all    = np.percentile([dist_from_center(lat, lon) for lat, lon in zip(all_lats, all_lons)], percentile)

    bbox = compute_bbox_from_percentile(all_lats, all_lons, percentile)

    print(f"\n── Résultats au percentile {percentile}% ──────────────────────────")
    print(f"  Distance domicile → centre :  {p_home:.1f} km")
    print(f"  Distance destination → centre: {p_dest:.1f} km")
    print(f"  Longueur de trajet (OD)     : {p_trip:.1f} km")
    print(f"  Toutes localisations confondues: {p_all:.1f} km du centre")
    print(f"\n  Bounding Box {percentile}% (WGS84) :")
    print(f"    min_lat = {bbox['min_lat']:.5f}  max_lat = {bbox['max_lat']:.5f}")
    print(f"    min_lon = {bbox['min_lon']:.5f}  max_lon = {bbox['max_lon']:.5f}")

    lat_span_km = haversine_km(bbox['min_lat'], bbox['min_lon'], bbox['max_lat'], bbox['min_lon'])
    lon_span_km = haversine_km(bbox['min_lat'], bbox['min_lon'], bbox['min_lat'], bbox['max_lon'])
    print(f"    → étendue : {lat_span_km:.0f} km (N-S) × {lon_span_km:.0f} km (E-W)")

    # ── Figure ────────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(18, 13))
    fig.suptitle(
        f"Analyse spatiale des déplacements — Population EQASIM Toulouse\n"
        f"({n_persons} personnes, {len(trips)} trajets simulés)",
        fontsize=14, fontweight="bold", y=0.98
    )
    gs = GridSpec(2, 3, figure=fig, hspace=0.38, wspace=0.32)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])
    ax4 = fig.add_subplot(gs[1, 0])
    ax5 = fig.add_subplot(gs[1, 1])
    ax6 = fig.add_subplot(gs[1, 2])

    pct_color = "#c0392b"

    # ── 1. CDF distances domiciles ────────────────────────────────────────────
    sorted_h = np.sort(home_dists)
    cdf_h = np.arange(1, len(sorted_h) + 1) / len(sorted_h) * 100
    ax1.plot(sorted_h, cdf_h, color="#3498db", lw=2)
    ax1.axvline(p_home, color=pct_color, ls="--", lw=1.5, label=f"P{percentile:.0f} = {p_home:.1f} km")
    ax1.axhline(percentile, color=pct_color, ls=":", lw=1, alpha=0.6)
    for label, (lo, hi) in RINGS.items():
        ax1.axvspan(lo, min(hi, sorted_h.max() * 1.05), alpha=0.07,
                    color=RING_COLORS[list(RINGS.keys()).index(label)])
    ax1.set_xlabel("Distance au centre (km)")
    ax1.set_ylabel("% cumulé des domiciles")
    ax1.set_title("CDF — Domiciles / centre-ville")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(0, max(sorted_h) * 1.05)

    # ── 2. CDF distances destinations ────────────────────────────────────────
    sorted_d = np.sort(dest_dists)
    cdf_d = np.arange(1, len(sorted_d) + 1) / len(sorted_d) * 100
    ax2.plot(sorted_d, cdf_d, color="#9b59b6", lw=2)
    ax2.axvline(p_dest, color=pct_color, ls="--", lw=1.5, label=f"P{percentile:.0f} = {p_dest:.1f} km")
    ax2.axhline(percentile, color=pct_color, ls=":", lw=1, alpha=0.6)
    for label, (lo, hi) in RINGS.items():
        ax2.axvspan(lo, min(hi, sorted_d.max() * 1.05), alpha=0.07,
                    color=RING_COLORS[list(RINGS.keys()).index(label)])
    ax2.set_xlabel("Distance destination → centre (km)")
    ax2.set_ylabel("% cumulé des destinations")
    ax2.set_title("CDF — Destinations / centre-ville")
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(0, max(sorted_d) * 1.05)

    # ── 3. CDF longueur de trajet (OD) ───────────────────────────────────────
    sorted_t = np.sort([t for t in trip_lengths if t > 0.01])
    cdf_t = np.arange(1, len(sorted_t) + 1) / len(sorted_t) * 100
    ax3.plot(sorted_t, cdf_t, color="#e67e22", lw=2)
    ax3.axvline(p_trip, color=pct_color, ls="--", lw=1.5, label=f"P{percentile:.0f} = {p_trip:.1f} km")
    ax3.axhline(percentile, color=pct_color, ls=":", lw=1, alpha=0.6)
    ax3.set_xlabel("Distance OD du trajet (km, vol d'oiseau)")
    ax3.set_ylabel("% cumulé des trajets")
    ax3.set_title("CDF — Longueur des trajets")
    ax3.legend(fontsize=9)
    ax3.grid(True, alpha=0.3)

    # ── 4. Distribution par couronne ─────────────────────────────────────────
    ring_labels = list(RINGS.keys())
    home_counts  = [sum(1 for d in home_dists if lo <= d < hi) for _, (lo, hi) in RINGS.items()]
    dest_counts  = [sum(1 for d in dest_dists if lo <= d < hi) for _, (lo, hi) in RINGS.items()]

    x = np.arange(len(ring_labels))
    w = 0.38
    bars1 = ax4.bar(x - w/2, [c/n_persons*100 for c in home_counts], w,
                    label="Domiciles", color="#3498db", alpha=0.85)
    bars2 = ax4.bar(x + w/2, [c/len(dest_dists)*100 for c in dest_counts], w,
                    label="Destinations", color="#9b59b6", alpha=0.85)
    ax4.set_xticks(x)
    ax4.set_xticklabels(ring_labels, fontsize=8)
    ax4.set_ylabel("% des localisations")
    ax4.set_title("Répartition par couronne")
    ax4.legend(fontsize=9)
    ax4.grid(True, axis="y", alpha=0.3)
    for bar in bars1:
        h = bar.get_height()
        if h > 1:
            ax4.text(bar.get_x() + bar.get_width()/2, h + 0.3, f"{h:.0f}%", ha="center", fontsize=7)
    for bar in bars2:
        h = bar.get_height()
        if h > 1:
            ax4.text(bar.get_x() + bar.get_width()/2, h + 0.3, f"{h:.0f}%", ha="center", fontsize=7)

    # ── 5. Heatmap spatiale (scatter des localisations) ───────────────────────
    home_lat = [lat for lat, lon in home_locs]
    home_lon = [lon for lat, lon in home_locs]
    dest_lat = [t["dest_lat"] for t in trips]
    dest_lon = [t["dest_lon"] for t in trips]

    ax5.scatter(dest_lon, dest_lat, c="#9b59b6", s=1, alpha=0.15, label="Destinations")
    ax5.scatter(home_lon, home_lat, c="#3498db", s=2, alpha=0.3, label="Domiciles")
    ax5.scatter([TOULOUSE_CENTER[1]], [TOULOUSE_CENTER[0]],
                c="red", s=80, marker="*", zorder=5, label="Capitole")

    # Cercles de couronnes
    for (label, (lo, hi)), color in zip(RINGS.items(), RING_COLORS):
        if lo == 0:
            continue
        theta = np.linspace(0, 2 * np.pi, 200)
        dlat = lo / 111.0
        dlon = lo / (111.0 * math.cos(math.radians(TOULOUSE_CENTER[0])))
        ax5.plot(TOULOUSE_CENTER[1] + dlon * np.cos(theta),
                 TOULOUSE_CENTER[0] + dlat * np.sin(theta),
                 ls="--", lw=0.8, color=color, alpha=0.7)
        ax5.text(TOULOUSE_CENTER[1] + dlon * 0.72, TOULOUSE_CENTER[0] + dlat * 0.72,
                 f"{lo}km", fontsize=6.5, color=color)

    # Rectangle bbox
    bx = bbox
    rect = plt.Rectangle((bx['min_lon'], bx['min_lat']),
                          bx['max_lon'] - bx['min_lon'], bx['max_lat'] - bx['min_lat'],
                          linewidth=2, edgecolor=pct_color, facecolor="none",
                          linestyle="-", label=f"BBox P{percentile:.0f}")
    ax5.add_patch(rect)
    ax5.set_xlabel("Longitude")
    ax5.set_ylabel("Latitude")
    ax5.set_title(f"Carte des localisations + BBox P{percentile:.0f}")
    ax5.legend(fontsize=7, markerscale=2)
    ax5.set_aspect("equal")
    ax5.grid(True, alpha=0.2)

    # ── 6. Tableau récapitulatif ──────────────────────────────────────────────
    ax6.axis("off")
    table_data = [
        ["Métrique", f"P50", f"P90", f"P{percentile:.0f}", "Max"],
    ]
    for name, vals in [
        ("Domicile → centre (km)", home_dists),
        ("Destination → centre (km)", dest_dists),
        ("Longueur trajet OD (km)", [t for t in trip_lengths if t > 0.01]),
    ]:
        row = [name,
               f"{np.percentile(vals, 50):.1f}",
               f"{np.percentile(vals, 90):.1f}",
               f"{np.percentile(vals, percentile):.1f}",
               f"{np.max(vals):.1f}"]
        table_data.append(row)

    table_data.append(["─" * 25, "─" * 6, "─" * 6, "─" * 6, "─" * 6])
    table_data.append([f"BBox P{percentile:.0f}", "", "", "", ""])
    table_data.append([f"  lat : [{bbox['min_lat']:.4f}, {bbox['max_lat']:.4f}]", "", "", "", ""])
    table_data.append([f"  lon : [{bbox['min_lon']:.4f}, {bbox['max_lon']:.4f}]", "", "", "", ""])
    table_data.append([f"  {lat_span_km:.0f} km (N-S) × {lon_span_km:.0f} km (E-W)", "", "", "", ""])

    tbl = ax6.table(cellText=table_data, loc="center", cellLoc="left")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1.1, 1.6)
    for (row, col), cell in tbl.get_celld().items():
        if row == 0:
            cell.set_facecolor("#2c3e50")
            cell.set_text_props(color="white", fontweight="bold")
        elif row % 2 == 0:
            cell.set_facecolor("#ecf0f1")
        cell.set_edgecolor("#bdc3c7")
    ax6.set_title(f"Tableau récapitulatif (P{percentile:.0f} ciblé)", fontweight="bold")

    # ── Sauvegarde ────────────────────────────────────────────────────────────
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"\n  Figure sauvegardée : {output_path}")
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--population", default="data/eqasim_output/toulouse_population_5194.json")
    parser.add_argument("--percentile", type=float, default=95.0)
    parser.add_argument("--output", default="scripts/bbox_analysis.png")
    args = parser.parse_args()

    # Résoudre le chemin relatif depuis la racine du projet
    root = Path(__file__).parent.parent
    main(
        str(root / args.population),
        args.percentile,
        str(root / args.output),
    )
