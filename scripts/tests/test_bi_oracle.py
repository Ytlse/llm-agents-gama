"""Tests du score composite à deux oracles.

Un test par règle de `specs/score_composite_deux_oracles.md`, R8 à R20. Les distributions
sont fabriquées à la main : ce qui est vérifié, c'est **l'arithmétique du score et ses
refus**, jamais la qualité d'un modèle. Les deux propriétés qui coûteraient le plus cher si
elles cédaient en silence :

- un bloc non mesuré doit rendre `null`, pas `0.0` — dans ce projet, l'absence de mesure
  produit le score parfait ;
- un numérateur et un dénominateur mesurés sur deux substrats ne doivent jamais composer un
  chiffre.

Hors ligne : aucun appel réseau, aucun LLM, aucun parquet réel.
"""

from __future__ import annotations

import math

import pytest

from scripts.synthesis.bi_oracle import (
    DIST_ORDER,
    EPSILON,
    arc_elasticities,
    block_b,
    block_c1,
    block_c2,
    check_substrate,
    compose,
    entropy_bits,
    jsd_bits,
    kl_bits,
    llm_distributions,
    mass_by_stratum,
)

# Le triplet de l'exemple de la spec : prompt, second oracle, oracle supervisé, sur une
# offre à trois modes. Les valeurs attendues plus bas sont calculées à la main.
PROMPT = {"marche": 0.10, "voiture": 0.65, "transports_collectifs": 0.25}
MNL = {"marche": 0.22, "voiture": 0.55, "transports_collectifs": 0.23}
BOOSTER = {"marche": 0.05, "voiture": 0.80, "transports_collectifs": 0.15}
OFFER = sorted(PROMPT)


def entry(distribution: dict, offered=None, dist_cat: str = "2-5km") -> dict:
    return {"p": dict(distribution), "offered": offered or sorted(distribution),
            "dist_cat": dist_cat, "degenere": max(distribution.values()) > 0.999}


def triple(n: int = 1, dist_cat: str = "2-5km"):
    """`n` décisions identiques, vues par les trois décideurs."""
    keys = [(f"a{i}", f"t{i}") for i in range(n)]
    return (
        {k: entry(PROMPT, OFFER, dist_cat) for k in keys},
        {k: entry(MNL, OFFER, dist_cat) for k in keys},
        {k: entry(BOOSTER, OFFER, dist_cat) for k in keys},
    )


# ── R8 : la formule du bloc B ────────────────────────────────────────────────

def test_R8_formule_du_bloc_B():
    """Sur le triplet de la spec, `s_B` vaut le rapport des divergences, à la main."""
    llm, mnl, lgb = triple(3)
    out = block_b(llm, mnl, lgb)
    assert out["jsd_prompt_mnl_bits_mean"] == pytest.approx(0.019944, abs=1e-6)
    assert out["jsd_booster_mnl_bits_mean"] == pytest.approx(0.064591, abs=1e-6)
    assert out["s_B"] == pytest.approx(30.8769, abs=1e-3)
    # Variante Kullback-Leibler : 0,0900 bit contre 0,3148 bit.
    assert out["kl_prompt_mnl_bits_mean"] == pytest.approx(0.090029, abs=1e-6)
    assert out["s_B_kl"] == pytest.approx(28.6012, abs=1e-3)


def test_R8_la_cel_brute_n_est_jamais_publiee_seule():
    """La CEL contre cible molle a un plancher : c'est l'excès qui est publié.

    `CEL(p‖q) = H(q) + KL(q‖p)` : sur ce triplet, 1,53 bit dont 1,44 de plancher. Publier
    la CEL sans son plancher laisserait croire à un désaccord de 1,53 bit là où il vaut
    0,09.
    """
    llm, mnl, lgb = triple(1)
    out = block_b(llm, mnl, lgb)
    assert "cel" not in json_keys(out)
    kl, _ = kl_bits(MNL, PROMPT)
    cel = -sum(p * math.log2(PROMPT[m]) for m, p in MNL.items())
    assert cel == pytest.approx(entropy_bits(MNL) + kl, abs=1e-9)
    assert out["entropie_mnl_bits_mean"] == pytest.approx(entropy_bits(MNL), abs=1e-9)


def json_keys(mapping: dict) -> set:
    return {k for k in mapping}


# ── R9 : pas de dénominateur, pas de chiffre ─────────────────────────────────

def test_R9_denominateur_absent_non_publie():
    """Deux oracles exactement d'accord : il n'y a pas d'échelle, donc pas de score."""
    llm, mnl, _ = triple(2)
    out = block_b(llm, mnl, {k: entry(MNL, OFFER) for k in mnl})
    assert out["s_B"] is None
    assert out["mesure"] == "non mesuré"
    assert "pas d'échelle" in out["raison"]


def test_R9_substrat_divergent_refuse():
    """Empreinte `moves.csv` différente : une reprise à chaud garde le nom du run."""
    mnl_meta = {"run": "experiments/archive/r1", "moves_sha256": "a" * 64,
                "spec_version": 2}
    lgb_meta = {"run": "experiments/archive/r1", "moves_sha256": "b" * 64,
                "spec_version": 2}
    verdict = check_substrate(mnl_meta, lgb_meta, "experiments/archive/r1", "a" * 64)
    assert verdict["ok"] is False
    assert any("empreinte moves.csv divergente" in p for p in verdict["problemes"])


def test_R9_contrats_de_variables_differents_refuses():
    verdict = check_substrate({"spec_version": 2}, {"spec_version": 3}, None, None)
    assert verdict["ok"] is False
    assert any("contrat de variables" in p for p in verdict["problemes"])


# ── R10 et R20 : le bloc C1, signes et arbitre ───────────────────────────────

def _curve(walk_by_stratum: list[float], strata: list[str], n: int = 40) -> dict:
    """Décisions synthétiques : part de marche imposée par strate, le reste en voiture."""
    out = {}
    for index, (cat, walk) in enumerate(zip(strata, walk_by_stratum)):
        for i in range(n):
            out[(f"a{index}_{i}", "t")] = entry(
                {"marche": walk, "voiture": 1 - walk}, ["marche", "voiture"], cat)
    return out


def test_R10_bloc_C_signes():
    """Deux transitions contredites sur dix mesurées → `s_C1 = 20`."""
    strata = DIST_ORDER[:6]
    # L'arbitre est monotone : la marche recule à mesure que la distance croît.
    mnl = _curve([0.80, 0.65, 0.50, 0.38, 0.25, 0.12], strata)
    # Le prompt le suit, sauf entre les strates 3 et 4 où il remonte : cette transition
    # contredit l'arbitre pour la marche ET pour la voiture, soit 2 désaccords.
    llm = _curve([0.75, 0.60, 0.45, 0.55, 0.30, 0.15], strata)
    out = block_c1(llm, mnl)
    assert out["n_transitions"] == 10
    assert out["n_desaccords"] == 2
    assert out["s_C1"] == pytest.approx(20.0)
    faulty = {(d["mode"], d["de"], d["vers"]) for d in out["desaccords"]}
    assert faulty == {("marche", strata[2], strata[3]), ("voiture", strata[2], strata[3])}


def test_R20_arbitre_non_monotone_exclu():
    """Une transition où l'arbitre ne bouge pas n'est ni un accord ni un désaccord."""
    strata = DIST_ORDER[:2]
    mnl = _curve([0.50, 0.50], strata)          # arbitre plat : aucun signe à donner
    llm = _curve([0.40, 0.60], strata)
    out = block_c1(llm, mnl)
    assert out["s_C1"] is None
    assert out["mesure"] == "non mesuré"
    assert out["ecartees"]["arbitre_sans_signe"] == 4


def test_R20_strate_trop_mince_ecartee_et_comptee():
    strata = DIST_ORDER[:2]
    mnl = _curve([0.80, 0.20], strata, n=3)
    llm = _curve([0.20, 0.80], strata, n=3)
    out = block_c1(llm, mnl, min_stratum=30)
    assert out["s_C1"] is None
    assert out["ecartees"]["effectif_insuffisant"] == 4


# ── R11, R12, R13 : composition ──────────────────────────────────────────────

def test_R11_composition_lineaire():
    weights = {"accord_mnl": 0.1, "coherence_mnl": 0.05}
    out = compose(16.16, 30.0, 20.0, weights)
    assert out["S2"] == pytest.approx(16.16 + 0.1 * 30.0 + 0.05 * 20.0)
    # Rétro-application exacte : promouvoir un poids depuis 0 est une addition.
    base = compose(16.16, 30.0, 20.0, {"accord_mnl": 0.0, "coherence_mnl": 0.0})
    assert base["S2"] + 0.1 * 30.0 + 0.05 * 20.0 == pytest.approx(out["S2"])


def test_R12_poids_nuls_par_defaut():
    """Sans configuration, le composite à deux oracles égale celui de fidélité."""
    out = compose(16.16, 899.4, 5.0, {})
    assert out["S2"] == pytest.approx(16.16)
    assert out["poids"] == {"accord_mnl": 0.0, "coherence_mnl": 0.0}


def test_R13_mesure_publiee_malgre_poids_nul():
    out = compose(16.16, 899.4, 5.0, {})
    scores = {t["terme"]: t["score"] for t in out["termes"]}
    assert scores["accord_mnl"] == 899.4 and scores["coherence_mnl"] == 5.0
    llm, mnl, lgb = triple(4)
    detail = block_b(llm, mnl, lgb, n_perimeter=8)
    assert detail["couverture"] == pytest.approx(0.5)
    assert detail["base_couverture"] == 8


def test_R13_un_terme_pese_mais_non_mesure_bloque_le_total():
    """Un poids non nul sur un terme absent ne se remplace pas par zéro."""
    out = compose(16.16, None, 5.0, {"accord_mnl": 0.1})
    assert out["S2"] is None
    assert out["non_mesures_bloquants"] == ["accord_mnl"]


# ── R14 : vacuité ≠ perfection ───────────────────────────────────────────────

def test_R14_vacuite_non_nulle():
    out = block_b({}, {}, {})
    assert out["s_B"] is None and out["mesure"] == "non mesuré"
    assert out["s_B"] != 0.0
    assert block_c1({}, {})["s_C1"] is None


def test_R14_une_offre_unique_n_est_pas_un_accord():
    """Décision forcée : les trois décideurs sont d'accord sans qu'on ait rien mesuré."""
    moves = [{"agent_id": "a", "activity_id": "t", "offered": ["voiture"],
              "probas": {"voiture": 100.0}, "dist_cat": "2-5km"}]
    distributions, skipped = llm_distributions(moves)
    assert distributions == {}
    assert skipped == {"offre_unique": 1}


# ── R15 : identité du substrat et des deux oracles ───────────────────────────

def test_R15_identite_du_substrat():
    mnl_meta = {"run": "r", "moves_sha256": "s", "spec_version": 2,
                "policy_format": "mnl_mode_choice_policy", "policy_sha256": "m" * 64}
    lgb_meta = {"run": "r", "moves_sha256": "s", "spec_version": 2,
                "policy_format": "lightgbm_mode_choice_policy", "policy_sha256": "l" * 64}
    verdict = check_substrate(mnl_meta, lgb_meta, "r", "s")
    assert verdict["ok"] is True
    assert verdict["oracles"]["mnl"]["sha256"] == "m" * 64
    assert verdict["oracles"]["booster"]["sha256"] == "l" * 64
    assert verdict["oracles"]["mnl"]["format"] == "mnl_mode_choice_policy"


def test_R15_parquet_illisible_est_un_probleme_nomme():
    verdict = check_substrate({"error": "parquet absent"}, {"spec_version": 2}, "r", "s")
    assert verdict["ok"] is False
    assert verdict["problemes"][0].startswith("mnl : parquet absent")


# ── R16 et R17 : appariement et support ──────────────────────────────────────

def test_R16_decisions_non_appariees_comptees():
    llm, mnl, lgb = triple(3)
    mnl.pop(("a0", "t0"))
    out = block_b(llm, mnl, lgb, llm_skipped={"offre_unique": 7})
    assert out["n_decisions"] == 2
    assert out["exclusions"]["sans_mnl"] == 1
    assert out["exclusions"]["prompt::offre_unique"] == 7


def test_R16_offre_divergente_exclue():
    llm, mnl, lgb = triple(1)
    key = ("a0", "t0")
    llm[key] = entry(PROMPT, ["marche", "voiture"])
    out = block_b(llm, mnl, lgb)
    assert out["s_B"] is None
    assert out["exclusions"]["offre_divergente"] == 1


def test_R17_support_de_l_offre():
    """Un mode hors offre ne contribue pas : il est retiré avant renormalisation."""
    moves = [{"agent_id": "a", "activity_id": "t",
              "offered": ["marche", "voiture", "autres"],
              "probas": {"marche": 30.0, "voiture": 50.0, "autres": 20.0},
              "dist_cat": "2-5km"}]
    distributions, _ = llm_distributions(moves)
    p = distributions[("a", "t")]["p"]
    assert set(p) == {"marche", "voiture"}
    assert sum(p.values()) == pytest.approx(1.0)
    assert p["marche"] == pytest.approx(30 / 80)


# ── R18 : le plancher est déclaré et compté ──────────────────────────────────

def test_R18_epsilon_declare():
    """Probabilité nulle sur un mode chargé par l'arbitre : divergence finie, et comptée."""
    categorical = {"marche": 0.0, "voiture": 1.0, "transports_collectifs": 0.0}
    key = ("a0", "t0")
    llm = {key: entry(categorical, OFFER)}
    mnl = {key: entry(MNL, OFFER)}
    lgb = {key: entry(BOOSTER, OFFER)}
    value, floored = kl_bits(MNL, categorical)
    assert math.isfinite(value) and floored is True
    out = block_b(llm, mnl, lgb)
    assert out["epsilon"] == EPSILON
    assert out["n_plancher_applique"] == 1
    assert out["n_prompt_degenere"] == 1
    # La JSD, elle, n'a besoin d'aucun plancher : bornée par 1 bit sur les mêmes données.
    assert jsd_bits(MNL, categorical) < 1.0


# ── R19 : un accord, jamais une erreur ───────────────────────────────────────

def test_R19_libelle_accord():
    llm, mnl, lgb = triple(2)
    out = block_b(llm, mnl, lgb)
    assert "accord" in out["mesure"]
    assert "erreur" not in out["mesure"]
    assert "inter-oracles" in out["mesure"]


# ── Élasticités du bloc C2 ───────────────────────────────────────────────────

def test_C2_non_mesure_sans_paire_ab():
    out = block_c2(None, None, None, None, None)
    assert out["s_C2"] is None
    assert "rejouées" in out["raison"]
    assert "--ab-variable" in out["comment"]


def test_C2_signes_d_elasticite_compares():
    before = {("a", "t"): entry({"marche": 0.5, "voiture": 0.5}, ["marche", "voiture"])}
    after = {("a", "t"): entry({"marche": 0.7, "voiture": 0.3}, ["marche", "voiture"])}
    mnl_before = before
    mnl_after = {("a", "t"): entry({"marche": 0.3, "voiture": 0.7},
                                   ["marche", "voiture"])}
    elasticities = arc_elasticities(before, after)
    assert elasticities["marche"] == pytest.approx(0.4)
    out = block_c2(before, after, mnl_before, mnl_after, "has_pt_subscription")
    assert out["s_C2"] == pytest.approx(100.0)
    assert out["variable"] == "has_pt_subscription"


def test_les_parts_par_strate_sont_des_masses_de_probabilite():
    strata = mass_by_stratum({("a", "t"): entry(PROMPT, OFFER, "2-5km"),
                              ("b", "t"): entry(BOOSTER, OFFER, "2-5km")})
    assert strata["2-5km"]["n"] == 2
    assert strata["2-5km"]["shares"]["voiture"] == pytest.approx(72.5)
    assert sum(strata["2-5km"]["shares"].values()) == pytest.approx(100.0)
