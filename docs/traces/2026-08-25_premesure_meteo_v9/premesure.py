#!/usr/bin/env python3
"""Pré-mesure du ticket 023 sur le substrat `v9` — étape 1 du protocole exogène.

Rejoue les trois tirages météo sur les jeux gelés `v9` (train + val) et écrit
`results.json`. **Aucun appel LLM** : on ne compare que des lignes de contexte,
pas des décisions. C'est ce qui permet de chiffrer avant de payer.

    prompt_calibration/.venv/bin/python docs/traces/2026-08-25_premesure_meteo_v9/premesure.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "prompt_calibration"))
from calibration.weather import WeatherDeck, draw_key, weather_to_natural_language  # noqa: E402

DS = ROOT / "prompt_calibration" / "calibration_datasets" / "v9"
# Fenêtre EMC² — `population_reference.survey_window()`, recopiée ici pour que la trace
# reste rejouable sans le dépôt principal sur le sys.path.
DEBUT, FIN = (9, 20), (2, 18)


def in_window(date_iso: str) -> bool:
    """La fenêtre FRANCHIT le 1er janvier : c'est « >= début OU <= fin », jamais un
    intervalle simple. Un intervalle simple rendrait un tirage vide."""
    m, d = int(date_iso[5:7]), int(date_iso[8:10])
    return (m, d) >= DEBUT or (m, d) <= FIN


def load_records() -> list[dict]:
    """`train` + `val`. `test` reste fermé ; `screen ⊂ train` et compterait deux fois."""
    recs = []
    for split in ("train", "val"):
        for line in (DS / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                recs.append(json.loads(line))
    return recs


def measure(deck: WeatherDeck, recs: list[dict]) -> dict:
    temps, sentences, rainy = [], [], 0
    for r in recs:
        w = deck.weather_for(draw_key(r["agent_id"], r["entry"]), int(r["departure_hour"]))
        temps.append(w["temperature"])
        rainy += w["precip_mm"] > 0
        sentences.append(weather_to_natural_language(w))
    # Moyennes NON arrondies : les écarts se calculent dessus, et l'arrondi vient en
    # dernier. Soustraire deux valeurs déjà arrondies déplaçait le ΔT de 0,01 °C.
    return {"temperature_moyenne_c": sum(temps) / len(temps),
            "part_sous_la_pluie_pct": rainy / len(recs) * 100,
            "_sentences": sentences}


def main() -> int:
    recs = load_records()
    annee = WeatherDeck.load(seed="meteo_v2")
    fenetre_days = [d for d in annee.days if in_window(d["DATE"])]
    if not fenetre_days:                       # contrôle de validité, cf. lot 3
        raise SystemExit("[ALARME] fenêtre vide — le filtre a rejeté les 365 jours")

    def variant(days, seed):
        return WeatherDeck(days=days, labels=annee.labels, seed=seed, source=annee.source)

    bras = {"v9_annee_meteo_v2":   annee,
            "v10_fenetre_meteo_v3": variant(fenetre_days, "meteo_v3"),
            "v9n_annee_meteo_v3n":  variant(annee.days, "meteo_v3n")}

    out, ref = {}, None
    for nom, deck in bras.items():
        m = measure(deck, recs)
        s = m.pop("_sentences")
        premier = ref is None
        if premier:
            ref = s
        if not premier:
            wet = lambda p: "Pas de précipitations" not in p          # noqa: E731
            m["phrase_inchangee_pct"] = round(
                sum(a == b for a, b in zip(ref, s)) / len(recs) * 100, 2)
            m["bascules_pluie_sec_pct"] = round(
                sum(wet(a) != wet(b) for a, b in zip(ref, s)) / len(recs) * 100, 1)
            m["delta_temperature_c"] = round(m["temperature_moyenne_c"] - base_t, 2)
            m["delta_pluie_pt"] = round(m["part_sous_la_pluie_pct"] - base_p, 2)
        if premier:
            base_t, base_p = m["temperature_moyenne_c"], m["part_sous_la_pluie_pct"]
        m["temperature_moyenne_c"] = round(m["temperature_moyenne_c"], 2)
        m["part_sous_la_pluie_pct"] = round(m["part_sous_la_pluie_pct"], 2)
        out[nom] = m

    res = {"date": "2026-08-25", "ticket": "023", "substrat": "v9",
           "run_source": "experiments/archive/2026-08-24_17_34",
           "appels_llm": 0,
           "jours": {"annee": len(annee.days), "fenetre": len(fenetre_days)},
           "fenetre_enquete": {"debut": "09-20", "fin": "02-18",
                               "franchit_le_1er_janvier": True},
           "effectifs": {"enregistrements": len(recs),
                         "personas_distincts": len({r["agent_id"] for r in recs}),
                         "splits": ["train", "val"]},
           "bras": out}
    (Path(__file__).parent / "results.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(recs)} enregistrements, {res['effectifs']['personas_distincts']} personas, "
          f"{len(fenetre_days)}/{len(annee.days)} jours retenus — results.json écrit")
    for nom, m in out.items():
        print(f"  {nom:<24} T={m['temperature_moyenne_c']:6.2f} °C  "
              f"pluie={m['part_sous_la_pluie_pct']:6.2f} %  "
              f"ΔT={m.get('delta_temperature_c', 0):+6.2f}  "
              f"Δpluie={m.get('delta_pluie_pt', 0):+6.2f} pt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
