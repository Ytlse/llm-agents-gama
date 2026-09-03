"""Tests du contrôle et du scellement de la population du jeu de test (scripts/AAMAS).

Ce qui est verrouillé ici, et pourquoi :
  * l'arrondi au plus fort reste somme EXACTEMENT à N — un persona de trop ou de moins
    ferait mentir le nom du dossier scellé ;
  * le TOST rend `équivalent` quand l'IC90 tient dans la borne, `écart` quand l'IC95 exclut la
    cible et que l'écart dépasse la borne, `non concluant` entre les deux ;
  * la sélection est déterministe, exclut les hors périmètre et les moins de 5 ans, et journalise
    un déficit au lieu de le cacher ;
  * le contrôle rend `non mesurable` — jamais 0 — pour une marge sans cible publiée.

    llm-agents/.venv/bin/python -m pytest scripts/tests/test_aamas_population.py -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.AAMAS import control_population as ctl  # noqa: E402
from scripts.AAMAS import seal_population as seal  # noqa: E402
from scripts.AAMAS.reference_marges import (  # noqa: E402
    JOINT_TARGET, MOTORISATION, age_class, cible_jointe, marges, motorisation_class)


def _persona(pid: int, age: int, gender: str, occupation: str, cars: int, size: int,
             couronne: str) -> dict:
    return {
        "person_id": str(pid),
        "identity": {
            "name": f"P{pid}",
            "traits_json": {"age": age, "gender": gender, "main_occupation": occupation,
                            "number_of_cars": cars, "household_size": size,
                            "has_driving_license": age >= 18, "residence_zone": couronne},
            "home": {"lon": 1.44, "lat": 43.6},
            "activities": [],
        },
        "state": {}, "is_llm_based": True,
    }


def _pool(n_per_cell: int = 40) -> list[dict]:
    """Un vivier synthétique : chaque cellule couronne × motorisation peuplée de `n_per_cell`."""
    from llm_module.core.population_reference import COURONNES, OUT_OF_PERIMETER
    pool, pid = [], 0
    occupations = ["Travail à plein temps", "Retraité", "Scolaire (jusqu'au Bac)", "Étudiant",
                   "Travail à temps partiel", "Chômeur/recherche d'emploi", "Personne au foyer"]
    for c in COURONNES:
        for cars in (0, 1, 2):
            for k in range(n_per_cell):
                pid += 1
                pool.append(_persona(pid, 5 + (pid * 7) % 80, "Female" if pid % 2 else "Male",
                                     occupations[pid % 7], cars, 1 + pid % 4, c))
    # Bruit à exclure : hors périmètre, et un enfant de 3 ans.
    pid += 1
    pool.append(_persona(pid, 40, "Male", "Retraité", 1, 2, OUT_OF_PERIMETER))
    pid += 1
    pool.append(_persona(pid, 3, "Female", "Scolaire (jusqu'au Bac)", 1, 3, COURONNES[0]))
    return pool


# ── Références ────────────────────────────────────────────────────────────────

def test_la_cible_jointe_gelee_est_lisible_et_somme_a_100():
    doc = cible_jointe(JOINT_TARGET)
    total = sum(v for row in doc["cible_pct"].values() for v in row.values())
    assert abs(total - 100.0) < 0.05
    # La contre-épreuve retrouve la page 21 du rapport (base ménage) à ± 0,5 pt.
    menage = doc["contre_epreuves"]["motorisation_base_menage_pct"]
    assert abs(menage["sans voiture"] - 19) < 0.5
    assert abs(menage["une voiture"] - 45) < 0.5
    assert abs(menage["deux voitures et +"] - 35) < 0.5


def test_les_marges_recalculees_disent_leur_source():
    """Genre, permis, abonnement… ne sont pas publiés par le rapport : leur cible est un
    recalcul gelé (cm1), et la source de chaque marge le dit."""
    items = {m.nom: m for m in marges()}
    for nom in ("genre", "permis_adultes", "abonnement_tc", "logement", "immobile",
                "age_quinquennal", "taille_menage_personne"):
        assert items[nom].cible_pct is not None, nom
        assert abs(sum(items[nom].cible_pct.values()) - 100) < 0.05, nom
        assert "recalcul" in items[nom].source_cible and "non publié" in items[nom].source_cible, nom
    assert items["classe_age"].source_cible.startswith("AUAT")          # celle-ci est publiée
    assert items["motorisation_personne"].cible_pct["deux voitures et +"] > 45   # base personne
    assert 9 < items["immobile"].cible_pct["Oui"] < 12


def test_recodages():
    assert motorisation_class(0) == "sans voiture"
    assert motorisation_class("1") == "une voiture"
    assert motorisation_class(3) == "deux voitures et +"
    assert motorisation_class(None) is None
    assert age_class(4) is None          # sous la population enquêtée
    assert age_class(17) == "5-17 ans"
    assert age_class(18) == "18-24 ans"
    assert age_class(90) == "65 ans et +"


# ── Statistiques ──────────────────────────────────────────────────────────────

def test_plus_fort_reste_somme_exactement_a_n():
    shares = {"a": 33.3333, "b": 33.3333, "c": 33.3334}
    for n in (10, 999, 1000, 1001):
        out = seal.largest_remainder(shares, n)
        assert sum(out.values()) == n
    doc = cible_jointe(JOINT_TARGET)
    cells = {f"{c} × {m}": doc["cible_pct"][c][m] for c in doc["cible_pct"] for m in MOTORISATION}
    assert sum(seal.largest_remainder(cells, 1000).values()) == 1000


def test_tost_trois_verdicts():
    # IC90 contenu dans ± 1 autour de la cible → équivalent.
    assert ctl.tost(50.2, (49.6, 50.8), (49.4, 51.0), 50.0, 1.0) == ctl.TOST_EQUIVALENT
    # IC95 exclut la cible ET écart > borne → écart.
    assert ctl.tost(55.0, (53.5, 56.5), (53.0, 57.0), 50.0, 1.0) == ctl.TOST_ECART
    # IC95 exclut la cible mais écart sous la borne → non concluant, pas écart.
    assert ctl.tost(50.8, (50.5, 51.1), (50.4, 51.2), 50.0, 1.0) == ctl.TOST_INCONCLUSIF
    # IC large : ni équivalent ni écart.
    assert ctl.tost(52.0, (48.0, 56.0), (47.0, 57.0), 50.0, 1.0) == ctl.TOST_INCONCLUSIF


def test_clopper_pearson_bornes():
    lo, hi = ctl.clopper_pearson(0, 100, 0.05)
    assert lo == 0.0 and 0 < hi < 5
    lo, hi = ctl.clopper_pearson(100, 100, 0.05)
    assert hi == 100.0 and 95 < lo < 100
    lo, hi = ctl.clopper_pearson(50, 100, 0.05)
    assert lo < 50 < hi


# ── Sélection ─────────────────────────────────────────────────────────────────

def test_selection_deterministe_et_exclusions():
    # 40 personas par cellule ; la plus grosse part de la cible jointe est ≈ 20 %, donc
    # n = 150 (cible max ≈ 30) tient dans chaque cellule : aucun déficit attendu.
    pool = _pool(40)
    chosen_a, journal_a = seal.select(pool, 150)
    chosen_b, journal_b = seal.select(list(reversed(pool)), 150)   # ordre du fichier inversé
    assert len(chosen_a) == 150
    assert [p["person_id"] for p in chosen_a] == [p["person_id"] for p in chosen_b]
    ex = journal_a["vivier"]["exclus"]
    assert ex["hors_perimetre"] == 1 and ex["moins_de_5_ans"] == 1
    # Sans household.id, chaque personne est un ménage d'une personne — et le journal le dit.
    assert ex["sans_household_id_menage_d_une_personne"] == 480
    assert sum(journal_a["retenus_par_cellule"].values()) == 150
    assert not journal_a["deficits"]


def test_selection_journalise_le_deficit_au_lieu_de_le_cacher():
    pool = _pool(40)   # 40 par cellule : la cellule « 1ere couronne × deux voitures et + »
    chosen, journal = seal.select(pool, 480)   # demande 20 % de plus que certaines cellules
    assert len(chosen) == 480
    assert journal["deficits"], "un vivier trop petit doit produire un déficit visible"
    assert journal["reports"] and all(r["n"] > 0 for r in journal["reports"])
    # Un déficit est comblé d'abord dans la MÊME couronne.
    for r in journal["reports"]:
        if r["portee"] == "même couronne":
            assert r["deficit"].split(" × ")[0] == r["vers"].split(" × ")[0]


def test_descente_reduit_la_perte_sans_bouger_les_cellules():
    """La descente échange des ménages de même taille dans la même cellule : la perte
    multi-marges baisse, les 12 effectifs de cellule restent ceux de l'allocation."""
    from collections import Counter
    pool = _pool(40)
    chosen, journal = seal.select(pool, 150)
    d = journal["descente"]
    assert d["echanges"] > 0
    assert d["perte_apres_pt"] < d["perte_avant_pt"]
    assert "occupation" in d["marges"] and d["marges"]["occupation"]["mesuree"]
    # Le vivier synthétique n'a ni logement ni abonnement : la descente le dit, ne l'invente pas.
    assert "logement" in d["marges_non_mesurees"]
    cells = Counter(f"{p['identity']['traits_json']['residence_zone']} × "
                    f"{seal.motorisation_class(p['identity']['traits_json']['number_of_cars'])}"
                    for p in chosen)
    assert dict(cells) == {c: n for c, n in journal["retenus_par_cellule"].items() if n}
    assert journal["version"] == seal.SELECTION_RULE


def _pool_menages(n_menages_par_cellule: int = 25) -> list[dict]:
    """Un vivier en MÉNAGES : tailles 1 à 3, une cellule par ménage, household.id à la racine."""
    from llm_module.core.population_reference import COURONNES
    pool, pid, hid = [], 0, 0
    occupations = ["Travail à plein temps", "Retraité", "Scolaire (jusqu'au Bac)", "Étudiant",
                   "Travail à temps partiel", "Chômeur/recherche d'emploi", "Personne au foyer"]
    for c in COURONNES:
        for cars in (0, 1, 2):
            for k in range(n_menages_par_cellule):
                hid += 1
                size = 1 + (hid % 3)
                for j in range(size):
                    pid += 1
                    rec = _persona(pid, 5 + (pid * 7) % 80, "Female" if pid % 2 else "Male",
                                   occupations[pid % 7], cars, size, c)
                    rec["household"] = {"id": f"h{hid}", "iris_id": None, "commune_id": None}
                    rec["immobile"] = (pid % 9 == 0)
                    rec["identity"]["activities"] = ([{"purpose": "home"}] if rec["immobile"] else
                                                     [{"purpose": "home"}, {"purpose": "work"}, {"purpose": "home"}])
                    pool.append(rec)
    return pool


def test_selection_par_menage_retient_des_menages_entiers():
    """Un ménage entre ou sort en entier : jamais un membre sans les autres."""
    from collections import Counter, defaultdict
    pool = _pool_menages(25)
    chosen, journal = seal.select(pool, 300)
    assert len(chosen) == 300
    membres, retenus = defaultdict(set), defaultdict(set)
    for r in pool:
        membres[r["household"]["id"]].add(r["person_id"])
    for r in chosen:
        retenus[r["household"]["id"]].add(r["person_id"])
    for h, ids in retenus.items():
        assert ids == membres[h], f"ménage {h} fragmenté"
    assert journal["menages_retenus"]["n"] == len(retenus)
    assert journal["menages_retenus"]["membres_presents"] == 300
    # Les immobiles sont une marge : mesurée, et rapprochée de la cible (10,6 %).
    im = journal["descente"]["marges"]["immobile"]
    assert im["mesuree"] and im["ecart_max_apres_pt"] <= im["ecart_max_avant_pt"]
    cells = Counter(f"{p['identity']['traits_json']['residence_zone']} × "
                    f"{seal.motorisation_class(p['identity']['traits_json']['number_of_cars'])}"
                    for p in chosen)
    assert dict(cells) == {c: n for c, n in journal["retenus_par_cellule"].items() if n}


def test_selection_refuse_un_vivier_insuffisant():
    with pytest.raises(ValueError, match="vivier insuffisant"):
        seal.select(_pool(2), 1000)


# ── Contrôle ──────────────────────────────────────────────────────────────────

def test_controle_rend_non_mesurable_et_jamais_zero_sans_cible(tmp_path):
    pool = _pool(40)
    path = tmp_path / "pop.json"
    path.write_text(json.dumps(pool), encoding="utf-8")
    report = ctl.run_control(path, borne=1.0, n_min=30, n_min_cellule=50)
    by_name = {m["marge"]: m for m in report["marges"]}
    # Le vivier synthétique ne porte ni logement ni abonnement : ces marges sortent
    # « non mesurable — aucun persona ne porte cette variable », jamais 0.
    for nom in ("logement", "abonnement_tc"):
        assert by_name[nom]["verdict"] == ctl.NON_MESURABLE, nom
        assert by_name[nom]["chi2"] is None
    # Le genre, lui, est désormais mesurable (cible recalculée gelée).
    assert by_name["genre"]["chi2"] is not None
    # Tous immobiles (aucune activité) : la marge le dit, la section mobilité aussi.
    assert by_name["immobile"]["constats"][0]["observe_pct"] == 100.0
    assert report["menages_et_mobilite"]["part_immobiles_pct"] == 100.0
    assert report["compteurs"]["hors_perimetre"] == 1
    assert report["compteurs"]["age_sous_5_ans"] == 1
    assert set(report["verdicts"]) == {ctl.CONFORME, ctl.A_CORRIGER, ctl.A_PUBLIER, ctl.NON_MESURABLE}
    # La synthèse liste le hors périmètre comme refermable au scellement.
    assert any("hors des 453 communes" in row["ecart"] for row in report["synthese"])
    # Le journal de recoupement porte les neuf lignes du protocole.
    assert len(report["recoupement"]) == 13  # tableau §2.1 du protocole v1.5 (13 lignes)


def test_controle_uniforme_est_a_corriger_sur_la_couronne(tmp_path):
    """Un vivier à cellules égales met 25 % par couronne : la 3ᵉ (cible 15,4 %) est en écart."""
    pool = _pool(60)
    path = tmp_path / "pop.json"
    path.write_text(json.dumps(pool), encoding="utf-8")
    report = ctl.run_control(path, borne=1.0, n_min=30, n_min_cellule=50)
    couronne = {m["marge"]: m for m in report["marges"]}["couronne"]
    assert couronne["verdict"] == ctl.A_CORRIGER
    assert report["verdicts"][ctl.A_CORRIGER] >= 1


# ── Règle v4 : périmètre et ligne scolaires (ticket 031) ─────────────────────

def test_regle_v4_journalise_le_perimetre_et_les_departements():
    """La règle est `aamas_seal_v4`, tient les six classes d'âge, et le journal dit d'où
    viennent les retenus (département de `household.commune_id`) et quel périmètre est déclaré."""
    assert seal.SELECTION_RULE == "aamas_seal_v4"
    assert seal.SELECTION_NAMESPACE == "aamas_seal_v4"
    assert "classe_age" in seal.DESCENTE_MARGES and "occupation" in seal.DESCENTE_MARGES
    assert seal.DEFAULT_SEAL_DIR.name == "population_1000_AAMAS_v4"
    pool = _pool_menages(25)
    deps = ["31", "32", "81", "82", "09", "11"]
    for i, rec in enumerate(pool):
        rec["household"]["commune_id"] = f"{deps[int(rec['household']['id'][1:]) % 6]}123"
    chosen, journal = seal.select(pool, 300)
    per = journal["perimetre"]
    assert "453 communes" in per["definition"] and "polygone" in per["definition"]
    assert set(per["departements_attendus"]) == set(deps)
    assert sum(per["retenus_par_departement"].values()) == 300
    assert per["departements_representes"] == 6
    assert per["retenus_sans_commune"] == 0
    assert "aamas_seal_v4" in journal["regle"]


def test_commune_du_domicile_lit_household_puis_le_trait():
    rec = {"household": {"commune_id": "undefined"}, "identity": {"traits_json": {"residence_insee": "9038"}}}
    assert seal._commune_of(rec) == "09038"
    rec["household"]["commune_id"] = "31555"
    assert seal._commune_of(rec) == "31555"
    assert seal._commune_of({"household": {}, "identity": {"traits_json": {}}}) is None


def test_independance_rend_non_mesurable_sur_une_table_degeneree(tmp_path):
    """Une population où toute une colonne de motorisation est vide ne fait pas planter le
    contrôle : le croisement sort `non mesurable`, avec la modalité vide nommée."""
    pool = [p for p in _pool(40) if p["identity"]["traits_json"]["number_of_cars"] == 1]
    path = tmp_path / "pop.json"
    path.write_text(json.dumps(pool), encoding="utf-8")
    report = ctl.run_control(path, borne=1.0, n_min=30, n_min_cellule=50)
    assert report["independance"]["verdict"] == ctl.NON_MESURABLE
    assert "sans voiture" in report["independance"]["raison"]


def _pool_scolaires(n_menages: int = 30, part_etudes: float = 0.5) -> list[dict]:
    """Un vivier avec des ménages parent + enfant scolaire ; `part_etudes` des enfants vont à l'école."""
    from llm_module.core.population_reference import COURONNES
    pool, pid = [], 0
    for h in range(n_menages):
        c = COURONNES[h % 4]
        for age, occ in ((40, "Travail à plein temps"), (9 + h % 9, "Scolaire (jusqu'au Bac)")):
            pid += 1
            rec = _persona(pid, age, "Female" if pid % 2 else "Male", occ, h % 3, 2, c)
            rec["household"] = {"id": f"h{h}", "iris_id": None, "commune_id": "31555"}
            rec["immobile"] = False
            if occ.startswith("Scolaire"):
                purpose = "education" if (h / n_menages) < part_etudes else "leisure"
            else:
                purpose = "work"
            rec["identity"]["activities"] = [{"purpose": "home"}, {"purpose": purpose}, {"purpose": "home"}]
            pool.append(rec)
    return pool


def test_controle_mesure_les_scolaires_avec_activite_etudes(tmp_path):
    """La ligne « scolaires avec activité d'études » compte les 6-17 ans scolaires mobiles, et un
    taux sous 88 % sort dans la synthèse comme écart à publier (levier eqasim, pas la sélection)."""
    path = tmp_path / "pop.json"
    path.write_text(json.dumps(_pool_scolaires(30, 0.5)), encoding="utf-8")
    report = ctl.run_control(path, borne=1.0, n_min=30, n_min_cellule=50)
    m = report["menages_et_mobilite"]
    assert m["scolaires_6_17"] == 30 and m["scolaires_mobiles"] == 30
    assert m["scolaires_avec_activite_etudes"] == 15
    assert m["part_scolaires_avec_etudes_pct"] == 50.0
    assert m["reference_enquete"]["part_scolaires_avec_etudes_pct"] == [90.0, 95.0]
    rows = [r for r in report["synthese"] if r["ecart"] == "scolaires sans activité d'études"]
    assert len(rows) == 1 and rows[0]["verdict"] == ctl.A_PUBLIER
    assert "eqasim" in rows[0]["refermable_au_scellement"]
    assert "Scolaires (6-17 ans) avec activité d'études : 15/30" in ctl.render_text(report)
    assert "50.0 %" in ctl.render_markdown(report)

    # Au-dessus du seuil : pas d'écart dans la synthèse.
    path.write_text(json.dumps(_pool_scolaires(30, 0.95)), encoding="utf-8")
    report = ctl.run_control(path, borne=1.0, n_min=30, n_min_cellule=50)
    assert report["menages_et_mobilite"]["part_scolaires_avec_etudes_pct"] >= 88.0
    assert not [r for r in report["synthese"] if r["ecart"] == "scolaires sans activité d'études"]


def test_le_compte_des_activites_hors_perimetre_distingue_controle_et_zero():
    """Sans la clé `perimetre`, la population n'a pas été contrôlée : le journal le dit, il n'invente pas 0."""
    pool = _pool_menages(5)
    j = seal.count_removed_out_of_perimeter(pool)
    assert j["controle"] is False and j["personas_controles"] == 0
    for i, rec in enumerate(pool):
        rec["perimetre"] = {"activites_hors_perimetre_supprimees": 2 if i < 3 else 0}
    j = seal.count_removed_out_of_perimeter(pool)
    assert j == {"controle": True, "personas_controles": len(pool),
                 "activites_hors_perimetre_supprimees": 6, "personas_touches": 3}
    chosen, journal = seal.select(pool, 60)
    assert "activites_hors_perimetre" in journal["perimetre"]
    assert journal["perimetre"]["activites_hors_perimetre"]["controle"] is True


def test_deplacements_comptent_le_retour_au_domicile(tmp_path):
    """La chaîne d'activités est cyclique (domicile du soir fusionné avec celui du matin) :
    n activités = n déplacements pour un mobile, 0 pour un immobile (une seule activité)."""
    def acts(purposes):
        return [{"id": str(i), "purpose": p, "start_time": 3600.0 * (8 + 3 * i),
                 "end_time": 3600.0 * (10 + 3 * i), "scheduled_start_time": None,
                 "location": {"lon": 1.44, "lat": 43.6}} for i, p in enumerate(purposes)]
    pool = _pool_menages(n_menages_par_cellule=10)
    for k, rec in enumerate(pool):
        if k % 10 == 0:
            rec["identity"]["activities"] = acts(["home"])          # immobile
            rec["immobile"] = True
        elif k % 2 == 0:
            rec["identity"]["activities"] = acts(["home", "work"])  # 2 déplacements (aller, retour)
            rec["immobile"] = False
        else:
            rec["identity"]["activities"] = acts(["home", "work", "shop"])  # 3 déplacements
            rec["immobile"] = False
    path = tmp_path / "pop.json"
    path.write_text(json.dumps(pool), encoding="utf-8")
    report = ctl.run_control(path, borne=1.0, n_min=30, n_min_cellule=50)
    m = report["menages_et_mobilite"]
    n_imm = sum(1 for k in range(len(pool)) if k % 10 == 0)
    n_two = sum(1 for k in range(len(pool)) if k % 10 != 0 and k % 2 == 0)
    n_three = len(pool) - n_imm - n_two
    attendu_mobile = (2 * n_two + 3 * n_three) / (n_two + n_three)
    assert m["immobiles"] == n_imm
    # Le rapport arrondit à 3 décimales.
    assert abs(m["deplacements_par_persona_mobile"] - attendu_mobile) < 5e-4
    assert abs(m["deplacements_par_persona"] - (2 * n_two + 3 * n_three) / len(pool)) < 5e-4
