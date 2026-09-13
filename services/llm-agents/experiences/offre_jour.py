"""L'offre de transports collectifs d'un autre jour, lue dans le GTFS — sans recalcul (décision 18).

« Le mardi joue l'offre du mardi. » Vérifier qu'une course proposée existe encore ne suffit pas
(relecture du 2026-09-06) : une course **ajoutée** ou déplacée ce jour-là — sur une autre ligne,
à un autre arrêt — peut rendre un meilleur itinéraire que celui enregistré. La seule règle sûre :

    l'offre est identique  ⇔  la GRILLE HORAIRE des deux jours est identique
    (mêmes courses : ligne, arrêt, heure de passage, pour tout le réseau).

Si elle diffère, un déplacement ne peut être servi du jeu que si **aucune** des courses qui
diffèrent ne passe **dans sa fenêtre temporelle** (du départ programmé au départ + `fenetre_s`,
qui couvre la fenêtre de recherche d'OTP et la durée du plus long itinéraire). Un événement hors
de cette fenêtre ne peut entrer dans aucun itinéraire du déplacement : c'est une borne rigoureuse
dans le temps, sans hypothèse spatiale. Tout autre déplacement voit ses transports collectifs
recalculés ce jour-là.

La comparaison se fait sur les événements de passage (`route_id`, `stop_id`, heure) des courses qui
ne sont actives que l'un des deux jours : deux identifiants de course différents qui décrivent le
même passage s'annulent. Coût : une passe sur `stop_times.txt`.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger

from experiences.jeu import Jeu

_JOURS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
FENETRE_S_DEFAUT = 4 * 3600      # fenêtre de recherche OTP (30 min) + plus long itinéraire TC, avec marge


def _hms_vers_s(txt: str) -> Optional[int]:
    try:
        h, m, s = (int(x) for x in txt.strip().split(":"))
        return h * 3600 + m * 60 + s          # peut dépasser 24 h (courses après minuit)
    except (ValueError, AttributeError):
        return None


def services_actifs(dossier_gtfs: Path, jour: str) -> frozenset[str]:
    """`service_id` actifs le jour (calendar.txt + exceptions de calendar_dates.txt)."""
    d = Path(dossier_gtfs)
    ymd = jour.replace("-", "")
    wd = _JOURS[date.fromisoformat(jour).weekday()]
    actifs: set[str] = set()
    cal = d / "calendar.txt"
    if cal.is_file():
        with open(cal, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r.get(wd) == "1" and r.get("start_date", "") <= ymd <= r.get("end_date", ""):
                    actifs.add(r["service_id"])
    cd = d / "calendar_dates.txt"
    if cd.is_file():
        with open(cd, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r.get("date") != ymd:
                    continue
                if r.get("exception_type") == "1":
                    actifs.add(r["service_id"])
                elif r.get("exception_type") == "2":
                    actifs.discard(r["service_id"])
    return frozenset(actifs)


def difference_grille(dossier_gtfs: Path, jour_a: str, jour_b: str) -> dict:
    """Événements de passage présents un seul des deux jours (après annulation des doublons).

    Rend {"evenements": Counter[(route_id, stop_id, secondes)] → +n (seulement A) / −n (seulement B),
          "courses_a": …, "courses_b": …, "courses_seulement_a": …, "courses_seulement_b": …}.
    """
    d = Path(dossier_gtfs)
    actifs_a, actifs_b = services_actifs(d, jour_a), services_actifs(d, jour_b)
    trips_a: dict[str, str] = {}
    trips_b: dict[str, str] = {}
    with open(d / "trips.txt", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            sv = r.get("service_id")
            if sv in actifs_a:
                trips_a[r["trip_id"]] = r["route_id"]
            if sv in actifs_b:
                trips_b[r["trip_id"]] = r["route_id"]
    seulement_a = {t for t in trips_a if t not in trips_b}
    seulement_b = {t for t in trips_b if t not in trips_a}
    diff: Counter = Counter()
    if seulement_a or seulement_b:
        with open(d / "stop_times.txt", newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                t = r.get("trip_id", "")
                if t in seulement_a:
                    signe, route = 1, trips_a[t]
                elif t in seulement_b:
                    signe, route = -1, trips_b[t]
                else:
                    continue
                s = _hms_vers_s(r.get("departure_time") or r.get("arrival_time") or "")
                if s is None:
                    continue
                diff[(route, r.get("stop_id", ""), s)] += signe
    diff = Counter({k: v for k, v in diff.items() if v != 0})
    return {"evenements": diff, "courses_a": len(trips_a), "courses_b": len(trips_b),
            "courses_seulement_a": len(seulement_a), "courses_seulement_b": len(seulement_b),
            "services_a": len(actifs_a), "services_b": len(actifs_b)}


def verifier_offre_jour_gtfs(jeu: Jeu, jour: str, dossier_gtfs: Optional[Path] = None,
                             fenetre_s: int = FENETRE_S_DEFAUT) -> dict:
    """Pour chaque déplacement du jeu : l'offre TC de `jour` est-elle identique dans sa fenêtre ? (lecture GTFS)."""
    if dossier_gtfs is None:
        from settings import settings
        dossier_gtfs = Path(settings.gtfs.gtfs_file)
    d = Path(dossier_gtfs)
    grille = difference_grille(d, jeu.jour_simule, jour)
    evenements: Counter = grille["evenements"]
    instants = sorted(s for (_, _, s) in evenements)
    par_route: Counter = Counter()
    par_heure: Counter = Counter()
    for (route, _, s), n in evenements.items():
        par_route[route] += abs(n)
        par_heure[f"{(s // 3600) % 24:02d}h"] += abs(n)

    import bisect
    valides, invalides = [], []
    detail: list[dict] = []
    for ligne in jeu._index.values():
        tc = any(
            leg.transit_route and not leg.transit_route.startswith("__") and not leg.is_transfer
            for prop in ligne.vers_propositions() for leg in prop.plan.legs
        )
        if not tc or not instants:
            valides.append(ligne.cle)                 # aucun TC proposé, ou grille identique : rien ne dépend du jour
            continue
        debut, fin = ligne.depart_24h, ligne.depart_24h + fenetre_s
        i = bisect.bisect_left(instants, debut)
        touches = [s for s in instants[i:] if s <= fin]
        # courses après minuit : une course notée 25:10 le jour du jeu passe à 01:10 le lendemain
        if not touches and fin >= 86400:
            j = bisect.bisect_left(instants, debut - 86400)
            touches = [s for s in instants[j:] if s <= fin - 86400]
        if touches:
            invalides.append(ligne.cle)
            detail.append({"cle": list(ligne.cle), "depart_24h": ligne.depart_24h,
                           "evenements_dans_la_fenetre": len(touches), "premier": touches[0], "dernier": touches[-1]})
        else:
            valides.append(ligne.cle)
    identique = not evenements
    resultat = {
        "methode": "grille_horaire_gtfs", "jeu": jeu.nom, "jour_jeu": jeu.jour_simule, "jour": jour, "gtfs": str(d),
        "fenetre_s": int(fenetre_s),
        "grille": {"services": {"jour_jeu": grille["services_a"], "jour": grille["services_b"]},
                   "courses": {"jour_jeu": grille["courses_a"], "jour": grille["courses_b"],
                               "seulement_jour_jeu": grille["courses_seulement_a"], "seulement_jour": grille["courses_seulement_b"]},
                   "evenements_differents": sum(abs(v) for v in evenements.values()),
                   "par_route": dict(par_route.most_common(15)), "par_heure": dict(sorted(par_heure.items()))},
        "deplacements": len(jeu._index), "valides": len(valides), "invalides": len(invalides),
        "equivalent": identique,
        "verifie_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "invalides_detail": detail[:50],
        "invalides_cles": [f"{p}|{a}" for p, a in invalides],
    }
    n_diff = resultat["grille"]["evenements_differents"]
    logger.info(
        f"[offre_jour] {jeu.nom!r} ({jeu.jour_simule}) vs {jour} : grille "
        f"{'IDENTIQUE' if identique else f'différente ({n_diff} passages)'} — "
        f"{len(valides)} déplacements servables, {len(invalides)} à recalculer (TC) dans une fenêtre de {fenetre_s // 3600} h"
    )
    return resultat


__all__ = ["FENETRE_S_DEFAUT", "services_actifs", "difference_grille", "verifier_offre_jour_gtfs"]
