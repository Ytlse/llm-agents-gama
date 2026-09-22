"""Tests du tirage d'une cohorte disjointe (ticket 073 axe 2, spec `cohortes-disjointes-axe2`).

Un test par règle de la spec, le numéro dans le nom. Ce qui est verrouillé ici :

  * la disjonction porte sur le MÉNAGE et se vérifie sur le RÉSULTAT, pas seulement à l'entrée —
    un filtre qui se tromperait de clé produirait une cohorte recouvrante en silence, et l'axe 2
    serait publié sur du sable ;
  * le sel du hachage ne bouge pas : à exclusion vide, la chaîne redonne la cohorte v6 au sha256
    près, et c'est la seule preuve que l'écart entre deux cohortes vient de l'exclusion ;
  * une cohorte dont le fichier a bougé depuis son scellement n'est plus celle qu'on croit
    exclure, et l'on ne peut pas savoir dans quel sens : c'est une erreur, pas un avertissement.

    services/llm-agents/.venv/bin/python -m pytest scripts/tests/test_073_cohorte_disjointe.py -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.AAMAS import seal_population as seal  # noqa: E402
from scripts.tests.test_aamas_population import _pool  # noqa: E402

COHORTE_1 = REPO_ROOT / "data" / "population" / "population_1000_AAMAS_v6"
COHORTE_2 = REPO_ROOT / "data" / "population" / "population_1000_AAMAS_v6_c2"
VIVIER = (REPO_ROOT / "scripts" / "data" / "population" / "Temp" / "4_zone_enriched"
          / "toulouse_population_10000.json")

SHA_V6 = "412efada802f79e8a72976ba25e0c7db8c9404adaed7c1f5e3e3d6afa3531db6"

besoin_cohortes = pytest.mark.skipif(
    not (COHORTE_1.exists() and COHORTE_2.exists()),
    reason="les deux cohortes scellées sont requises")
besoin_vivier = pytest.mark.skipif(not VIVIER.exists(), reason="vivier absent")


def _menages(pop: Path) -> set[str]:
    return {str((r.get("household") or {}).get("id"))
            for r in json.loads(pop.read_text(encoding="utf-8"))}


def _personnes(pop: Path) -> set[str]:
    return {str(r.get("person_id"))
            for r in json.loads(pop.read_text(encoding="utf-8"))}


def _pool_mixte(n_per_cell: int = 40) -> list[dict]:
    """Vivier synthétique où une moitié des personas vit en ménages de DEUX, l'autre seule.

    Le mélange n'est pas cosmétique : les douze effectifs de cellule sont des égalités en
    personnes, et un vivier fait uniquement de ménages de deux ne peut composer que des effectifs
    pairs. La cible jointe en produit d'impairs, et l'allocation entière n'a alors aucune solution.

    Les paires se forment entre voisins immédiats, qui appartiennent à la même cellule — `_pool`
    remplit chaque cellule par blocs de `n_per_cell` —, sans quoi le ménage serait « mixte » et
    écarté. La taille déclarée suit la taille présente.
    """
    pool = _pool(n_per_cell)
    for i, rec in enumerate(pool):
        apparie = (i % 4) < 2 and (i + 1) < len(pool)
        rec["household"] = {"id": f"h{i // 2}" if apparie else f"s{i}"}
        rec["identity"]["traits_json"]["household_size"] = 2 if apparie else 1
    return pool


# ── R1 : l'exclusion ampute le vivier ─────────────────────────────────────────

@besoin_cohortes
def test_R1_l_exclusion_retire_les_menages_de_la_cohorte_citee():
    exclus, journal = seal.charger_exclusions([COHORTE_1])
    assert len(exclus) == 499, "la v6 retient 499 ménages (MANIFEST : menages_retenus.n)"
    assert journal[0]["nom"] == "population_1000_AAMAS_v6"
    assert journal[0]["personnes"] == 1000


def test_R1_le_vivier_ampute_se_lit_dans_le_journal():
    pool = _pool_mixte()
    # Les ménages de deux portent un identifiant PAIR (`h{i // 2}` pour i = 0, 1, 4, 5, 8, 9…) :
    # h0 groupe les personas 0 et 1, h2 les personas 4 et 5. s2 est un ménage d'une personne.
    _, journal = seal.select(pool, 150, exclure_menages={"h0", "h2", "s2"})
    assert journal["vivier"]["menages_exclus"] == 3
    assert journal["vivier"]["exclus"]["exclus_cohorte_anterieure"] == 5


# ── R2 : la disjonction porte sur le ménage, pas sur la personne ──────────────

def test_R2_exclure_un_menage_emporte_tous_ses_membres():
    pool = _pool_mixte()
    retenus, _ = seal.select(pool, 150, exclure_menages={"h0"})
    # h0 groupe les deux premiers personas du vivier : aucun des deux ne doit reparaître.
    membres_h0 = {str(r["person_id"]) for r in pool if r["household"]["id"] == "h0"}
    assert len(membres_h0) == 2
    assert membres_h0 & {str(r["person_id"]) for r in retenus} == set()


# ── R3 : aucun recouvrement, ni ménage ni personne ────────────────────────────

@besoin_cohortes
def test_R3_les_deux_cohortes_scellees_ne_se_recouvrent_pas():
    p1, p2 = COHORTE_1 / "population.json", COHORTE_2 / "population.json"
    assert _menages(p1) & _menages(p2) == set()
    assert _personnes(p1) & _personnes(p2) == set()
    assert len(_personnes(p1)) == len(_personnes(p2)) == 1000


# ── R4 : le manifeste dit de quoi la cohorte est disjointe ────────────────────

@besoin_cohortes
def test_R4_le_manifeste_nomme_les_cohortes_exclues_et_leur_sha256():
    m = yaml.safe_load((COHORTE_2 / "MANIFEST.yaml").read_text(encoding="utf-8"))
    dis = m["disjonction"]
    assert dis["menages_exclus"] == 499
    citees = {c["nom"]: c["sha256"] for c in dis["cohortes"]}
    assert citees == {"population_1000_AAMAS_v6": SHA_V6}


@besoin_cohortes
def test_R4_une_cohorte_sur_vivier_entier_porte_une_disjonction_nulle():
    """`null`, pas une clé absente : sinon on ne distingue pas un vieux manifeste d'un tirage
    sur vivier entier."""
    m = yaml.safe_load((COHORTE_1 / "MANIFEST.yaml").read_text(encoding="utf-8"))
    assert m.get("disjonction", "ABSENTE") in (None, "ABSENTE")


# ── R5 : la règle de sélection change de nom ──────────────────────────────────

@besoin_cohortes
def test_R5_la_regle_declaree_distingue_le_vivier_ampute():
    m2 = yaml.safe_load((COHORTE_2 / "MANIFEST.yaml").read_text(encoding="utf-8"))
    m1 = yaml.safe_load((COHORTE_1 / "MANIFEST.yaml").read_text(encoding="utf-8"))
    assert m2["selection"]["version"] == seal.SELECTION_RULE_DISJOINT
    assert m1["selection"]["version"] == seal.SELECTION_RULE
    assert seal.SELECTION_RULE_DISJOINT != seal.SELECTION_RULE


def test_R5_le_journal_porte_la_regle_du_vivier_entier_sans_exclusion():
    _, journal = seal.select(_pool_mixte(), 150)
    assert journal["version"] == seal.SELECTION_RULE


# ── R6 : le contrôle territorial ne faiblit pas ───────────────────────────────

@besoin_cohortes
def test_R6_la_cohorte_disjointe_passe_le_controle_sans_indulgence():
    m = yaml.safe_load((COHORTE_2 / "MANIFEST.yaml").read_text(encoding="utf-8"))
    ctl_ = m["controle"]
    assert ctl_["verdicts"]["à corriger"] == 0
    assert ctl_["borne_tost_pt"] == 1.0, "la borne du vivier entier, pas une borne desserrée"
    assert ctl_["n_min"] == 30 and ctl_["n_min_cellule"] == 50


# ── R7 : un déficit dû à l'exclusion se distingue d'un déficit du vivier ──────

def test_R7_un_deficit_cause_par_l_exclusion_est_signale_comme_tel(caplog):
    """Vider une cellule par exclusion, alors que le vivier entier la remplissait."""
    pool = _pool(40)   # sans household.id : chaque persona est un ménage d'une personne
    cible = "Toulouse × sans voiture"
    a_exclure = {f"p:{r['person_id']}" for r in pool
                 if r["identity"]["traits_json"]["residence_zone"] == "Toulouse"
                 and r["identity"]["traits_json"]["number_of_cars"] == 0}
    assert a_exclure, "le vivier synthétique doit peupler la cellule visée"
    _, journal = seal.select(pool, 150, exclure_menages=a_exclure)
    assert journal["deficits_imputables_a_l_exclusion"], (
        "la cellule était servie par le vivier entier : le déficit vient de l'exclusion")
    assert cible in journal["deficits_imputables_a_l_exclusion"]


def test_R7_sans_exclusion_aucun_deficit_n_est_impute_a_l_exclusion():
    _, journal = seal.select(_pool_mixte(), 150)
    assert journal["deficits_imputables_a_l_exclusion"] == {}


# ── R8 : le sel ne bouge pas — à exclusion vide, la v6 revient à l'identique ──

@besoin_vivier
def test_R8_a_exclusion_vide_le_tirage_redonne_la_cohorte_v6():
    """La preuve que l'écart entre les deux cohortes vient de l'EXCLUSION et de rien d'autre.

    Lent (≈ 20 s : chargement du vivier de 26 Mo, programme entier, descente). C'est le prix
    d'une non-régression sur toute la chaîne de tirage.
    """
    from scripts.AAMAS import control_population as ctl
    records = ctl.load_population(VIVIER)
    seal.ensure_residence_zone(records)
    retenus, journal = seal.select(records, 1000)
    assert journal["version"] == seal.SELECTION_RULE
    attendus = json.loads((COHORTE_1 / "selection.json").read_text(encoding="utf-8"))
    assert [str(r["person_id"]) for r in retenus] == attendus["person_ids"]


# ── R9 : une cohorte modifiée depuis son scellement ne s'exclut pas ───────────

@besoin_cohortes
def test_R9_une_cohorte_dont_le_sha256_a_bouge_est_refusee(tmp_path):
    faux = tmp_path / "cohorte_trafiquee"
    faux.mkdir()
    (faux / "MANIFEST.yaml").write_text(
        (COHORTE_1 / "MANIFEST.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    records = json.loads((COHORTE_1 / "population.json").read_text(encoding="utf-8"))
    records.pop()  # un persona de moins : le fichier n'est plus celui que le manifeste scelle
    (faux / "population.json").write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(ValueError, match="modifiée depuis son scellement"):
        seal.charger_exclusions([faux])


def test_R9_une_cohorte_incomplete_est_refusee(tmp_path):
    vide = tmp_path / "sans_rien"
    vide.mkdir()
    with pytest.raises(ValueError, match="incomplète"):
        seal.charger_exclusions([vide])


# ── R10 : la disjonction se vérifie sur le résultat ───────────────────────────

def test_R10_la_garde_leve_quand_un_menage_exclu_figure_dans_le_resultat():
    with pytest.raises(ValueError, match="disjonction rompue"):
        seal.verifier_disjonction({"h1", "h2", "h3"}, {"h3", "h9"})


def test_R10_la_garde_laisse_passer_un_resultat_disjoint():
    seal.verifier_disjonction({"h1", "h2"}, {"h8", "h9"})
    seal.verifier_disjonction({"h1", "h2"}, set())


def test_R10_select_appelle_la_garde_sur_son_resultat(monkeypatch):
    """La garde ne sert à rien si le chemin de production l'oublie : on vérifie l'appel."""
    vus: list[tuple[set, set]] = []
    monkeypatch.setattr(seal, "verifier_disjonction",
                        lambda retenus, exclus: vus.append((set(retenus), set(exclus))))
    seal.select(_pool_mixte(), 150, exclure_menages={"h0"})
    assert len(vus) == 1, "select doit vérifier son résultat exactement une fois"
    retenus, exclus = vus[0]
    assert exclus == {"h0"}
    assert retenus, "la garde reçoit les ménages retenus, pas un ensemble vide"
