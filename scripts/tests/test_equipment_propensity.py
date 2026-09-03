"""Tests des lois d'équipement (tickets 016 et 017) et de leur pose sur une population.

Ce qui est testé ici est ce qui casserait en silence : l'alignement du vecteur de design
sur les coefficients, le déterminisme du tirage, les deux planchers d'âge, et la garde qui
empêche `car_availability` de rester calculé sur d'anciens permis.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from llm_module.core.equipment_propensity import (
    DRIVING_AGE,
    DRIVING_LICENSE,
    FEATURE_BASE,
    FEATURE_KNOTS,
    PT_SUBSCRIPTION,
    PropensityLaw,
    design_vector,
    draw_key,
    uniform,
)
from scripts.data.population import enrich_equipment as EE

OCCUPATIONS = ("Retraité", "Travail à plein temps", "Étudiant")


def _law(spec, features, intercept=0.0, coefficients=None) -> PropensityLaw:
    return PropensityLaw(
        spec=spec, features=tuple(features), occupations=OCCUPATIONS,
        intercept=intercept,
        coefficients=tuple(coefficients if coefficients is not None
                           else [0.0] * len(features)),
        median_density=700.0, meta={})


# ── Vecteur de design ────────────────────────────────────────────────────────

class TestDesignVector:
    def test_ordre_suit_features_et_non_une_constante(self):
        """L'ordre vient de la ressource : c'est ce qui permet de retirer un palier."""
        features = ("female", "age10")
        assert design_vector(40, "Female", "Retraité", 1, 700.0, 5.0,
                             OCCUPATIONS, features, 700.0) == [1.0, 4.0]
        assert design_vector(40, "Female", "Retraité", 1, 700.0, 5.0,
                             OCCUPATIONS, tuple(reversed(features)), 700.0) == [4.0, 1.0]

    def test_variable_inconnue_leve_plutot_que_de_valoir_zero(self):
        """Un désalignement doit exploser, pas produire une prédiction plausible."""
        with pytest.raises(KeyError):
            design_vector(40, "Male", "Retraité", 1, 700.0, 5.0,
                          OCCUPATIONS, ("age10", "variable_fantome"), 700.0)

    def test_densite_absente_retombe_sur_la_mediane_publiee(self):
        sans = design_vector(40, "Male", "Retraité", 1, None, 5.0,
                             OCCUPATIONS, ("log_density",), 700.0)
        avec = design_vector(40, "Male", "Retraité", 1, 700.0, 5.0,
                             OCCUPATIONS, ("log_density",), 700.0)
        assert sans == avec == [math.log1p(700.0)]

    def test_occupation_hors_vocabulaire_laisse_les_indicatrices_a_zero(self):
        """« Modalité inattendue » n'est pas « modalité la plus fréquente »."""
        features = tuple(f"occ_{o}" for o in OCCUPATIONS)
        assert design_vector(40, "Male", "Cosmonaute", 1, 700.0, 5.0,
                             OCCUPATIONS, features, 700.0) == [0.0, 0.0, 0.0]

    def test_paliers_tarifaires_aux_bonnes_bornes(self):
        features = FEATURE_KNOTS
        assert design_vector(25, "Male", "Étudiant", 1, 700.0, 5.0, OCCUPATIONS,
                             features, 700.0) == [1.0, 0.0, 0.0]
        assert design_vector(26, "Male", "Étudiant", 1, 700.0, 5.0, OCCUPATIONS,
                             features, 700.0) == [0.0, 0.0, 0.0]
        assert design_vector(62, "Male", "Retraité", 1, 700.0, 5.0, OCCUPATIONS,
                             features, 700.0) == [0.0, 1.0, 0.0]
        assert design_vector(65, "Male", "Retraité", 1, 700.0, 5.0, OCCUPATIONS,
                             features, 700.0) == [0.0, 1.0, 1.0]


# ── Tirage ───────────────────────────────────────────────────────────────────

class TestTirage:
    def test_uniform_est_stable_et_borne(self):
        """SHA-256, pas `hash()` : sinon le trait change à chaque processus."""
        assert uniform("sel", "clé") == uniform("sel", "clé")
        assert uniform("sel", "clé") == pytest.approx(uniform("sel", "clé"))
        assert 0.0 <= uniform("sel", "clé") < 1.0

    def test_le_sel_versionne_change_le_tirage(self):
        assert uniform("v1", "clé") != uniform("v2", "clé")

    def test_deux_colocataires_ne_partagent_pas_leur_tirage(self):
        """Un abonnement est nominatif : l'adresse seule ferait tirer le foyer entier."""
        a = draw_key(43.6, 1.44, "personne_a")
        b = draw_key(43.6, 1.44, "personne_b")
        assert a != b
        assert uniform(PT_SUBSCRIPTION.salt, a) != uniform(PT_SUBSCRIPTION.salt, b)

    def test_meme_personne_meme_adresse_meme_valeur(self):
        assert draw_key(43.6, 1.44, "p") == draw_key(43.6, 1.44, "p")

    def test_domicile_absent_ne_fait_pas_echouer_le_tirage(self):
        assert draw_key(None, None, "p").startswith("nohome/")


# ── Planchers d'âge ──────────────────────────────────────────────────────────

class TestPlanchersAge:
    def test_permis_pas_de_propension_sous_18_ans(self):
        """Seuil légal, pas paramètre de modèle : aucune propension n'est évaluée."""
        law = _law(DRIVING_LICENSE, FEATURE_BASE)
        assert law.propensity(17, "Male", "Scolaire (jusqu'au Bac)", 1, 700.0, 5.0) is None
        assert law.propensity(DRIVING_AGE, "Male", "Étudiant", 1, 700.0, 5.0) is not None

    def test_permis_faux_sous_18_ans_avec_motif(self):
        law = _law(DRIVING_LICENSE, FEATURE_BASE)
        value, reason = law.value(9, "Male", "Scolaire (jusqu'au Bac)", 2, 700.0, 5.0,
                                  43.6, 1.44, "enfant")
        assert value is False
        assert reason == "sous_age_champ"

    def test_abonnement_evalue_des_5_ans(self):
        law = _law(PT_SUBSCRIPTION, FEATURE_BASE)
        assert law.propensity(4, "Male", "Scolaire (jusqu'au Bac)", 1, 700.0, 5.0) is None
        assert law.propensity(5, "Male", "Scolaire (jusqu'au Bac)", 1, 700.0, 5.0) is not None

    def test_propension_est_bien_une_logistique(self):
        law = _law(PT_SUBSCRIPTION, ("female",), intercept=0.0, coefficients=[0.0])
        assert law.propensity(30, "Female", "Retraité", 1, 700.0, 5.0) == pytest.approx(0.5)


# ── Ressource ────────────────────────────────────────────────────────────────

class TestRessource:
    def test_absence_est_une_erreur_explicite(self, tmp_path):
        """Jamais un repli silencieux : trois consommateurs lisent ce trait."""
        with pytest.raises(FileNotFoundError, match="equipment-propensity"):
            PropensityLaw.load(PT_SUBSCRIPTION, tmp_path / "absente.json")

    def test_ressource_tronquee_est_refusee(self, tmp_path):
        path = tmp_path / "loi.json"
        path.write_text(json.dumps({"law": {
            "features": ["age10", "female"], "occupations": list(OCCUPATIONS),
            "intercept": 0.0, "coefficients": [1.0], "median_density": 700.0}}),
            encoding="utf-8")
        with pytest.raises(ValueError, match="coefficients"):
            PropensityLaw.load(PT_SUBSCRIPTION, path)

    @pytest.mark.parametrize("spec", [PT_SUBSCRIPTION, DRIVING_LICENSE])
    def test_ressource_du_depot_se_charge_et_predit(self, spec):
        resource = Path("llm_module/data") / spec.resource
        if not resource.exists():
            pytest.skip(f"{resource} absente — `make equipment-propensity`")
        law = PropensityLaw.load(spec)
        assert len(law.features) == len(law.coefficients)
        p = law.propensity(30, "Female", "Travail à plein temps", 1, 700.0, 5.0)
        assert 0.0 < p < 1.0

    def test_les_paliers_sont_retenus_pour_labonnement_et_pas_pour_le_permis(self):
        """L'arbitrage a tranché dans les deux sens — c'est ce qui le rend crédible."""
        for spec, expected in ((PT_SUBSCRIPTION, True), (DRIVING_LICENSE, False)):
            resource = Path("llm_module/data") / spec.resource
            if not resource.exists():
                pytest.skip(f"{resource} absente")
            law = PropensityLaw.load(spec)
            assert any(k in law.features for k in FEATURE_KNOTS) is expected


# ── Garde `car_availability` ─────────────────────────────────────────────────

def _person(pid, lat, lon, age, licence, cars, availability):
    return {"person_id": pid, "identity": {
        "home": {"lat": lat, "lon": lon},
        "traits_json": {"age": age, "has_driving_license": licence,
                        "number_of_cars": cars, "car_availability": availability,
                        "gender": "Male", "main_occupation": "Travail à plein temps"}}}


class TestGardeCarAvailability:
    def test_coherent_ne_signale_rien(self):
        # Deux voitures, deux permis → `all`.
        population = [_person("a", 43.6, 1.44, 40, True, 2, "all"),
                      _person("b", 43.6, 1.44, 38, True, 2, "all")]
        assert EE.car_availability_is_stale(population) == 0

    def test_permis_reecrit_rend_car_availability_perime(self):
        """Le piège exact du ticket 017 : il ne se voit nulle part sans cette garde."""
        # Une voiture, deux permis → `some`, mais le fichier porte encore `all`.
        population = [_person("a", 43.6, 1.44, 40, True, 1, "all"),
                      _person("b", 43.6, 1.44, 38, True, 1, "all")]
        assert EE.car_availability_is_stale(population) == 1

    def test_permis_de_mineur_ne_compte_pas(self):
        """Règle A1.a du ticket 008 : un permis hérité par un enfant ne partage rien."""
        population = [_person("a", 43.6, 1.44, 40, True, 1, "all"),
                      _person("b", 43.6, 1.44, 9, True, 1, "all")]
        assert EE.car_availability_is_stale(population) == 0

    def test_sans_voiture_cest_none(self):
        population = [_person("a", 43.6, 1.44, 40, True, 0, "none")]
        assert EE.car_availability_is_stale(population) == 0
        population = [_person("a", 43.6, 1.44, 40, True, 0, "all")]
        assert EE.car_availability_is_stale(population) == 1


# ── Cibles de recette ────────────────────────────────────────────────────────

class TestCibles:
    def test_cible_etudiant_est_la_valeur_restatee(self):
        """72,2 % et non 74,3 : le dépôt range l'alternance avec les étudiants."""
        assert EE.TARGETS["has_pt_subscription"]["Étudiant"] == 72.2

    def test_ecart_etudiant_retraite_est_un_critere(self):
        """Le critère le plus discriminant du ticket 016, cf. sa spécification."""
        targets = EE.TARGETS["has_pt_subscription"]
        assert EE.STUDENT_MINUS_RETIRED_TARGET == pytest.approx(
            targets["Étudiant"] - targets["Retraité"], abs=0.1)

    def test_couverture_insuffisante_invalide_la_recette(self):
        """Un trait absent partout n'est pas une réussite — motif « vacuité »."""
        population = [_person(str(i), 43.6, 1.44, 40, None, 1, "all") for i in range(50)]
        for person in population:
            person["identity"]["traits_json"].pop("has_driving_license")
            person["identity"]["traits_json"].pop("has_pt_subscription", None)
        ok, strata_ok, lines, _ = EE.check(population)
        assert ok is False
        assert any("couverture" in line for line in lines)


# ── Granularité des codes de zone (correctif du 2026-08-27) ──────────────────

class TestZoneKey:
    """La couche de zones est indexée en `XXXXXX000` ; le fichier déplacements code
    plus fin. Comparer les deux tels quels ne résolvait que 51 % des OD, et pas
    uniformément en âge — d'où un modèle mal entraîné sur les cohortes scolaires."""

    def test_ramene_a_la_granularite_de_la_couche(self):
        import pandas as pd
        from scripts.progedo_logit.build_mode_choice_dataset import zone_key
        got = zone_key(pd.Series(["102103503", "127105205", "101101000"]))
        assert list(got) == ["102103000", "127105000", "101101000"]

    def test_un_code_deja_a_la_granularite_est_inchange(self):
        import pandas as pd
        from scripts.progedo_logit.build_mode_choice_dataset import zone_key
        assert list(zone_key(pd.Series(["101101000"]))) == ["101101000"]

    def test_la_sortie_garde_neuf_chiffres(self):
        import pandas as pd
        from scripts.progedo_logit.build_mode_choice_dataset import zone_key
        assert all(len(c) == 9 for c in zone_key(pd.Series(["982121000", "102103503"])))


# ── Garde d'empreinte de politique (correctif du 2026-08-27) ─────────────────

def _tiny_parquet(path: Path, policy_sha: str | None) -> None:
    """Un parquet de prédictions minimal mais VRAI, écrit par le producteur lui-même."""
    from scripts.synthesis.model_on_common_set import (
        PREDICTABLE_CATS, STATUS_OK, write_parquet)
    row = {
        "agent_id": "1", "activity_id": "a", "status": STATUS_OK,
        "offered": "voiture|marche", "offered_predictable": "voiture|marche",
        "n_offered": 2, "sim_chosen": "voiture", "argmax_raw": "voiture",
        "argmax": "voiture", "p_offered_mass": 1.0, "departure_hour": 8,
        "genre": "Homme", "age_cat": "30-34", "occupation": "actif_temps_plein",
        "motif": "travail", "dist_cat": "2-5km", "lieu_residence": "Toulouse",
        "type_logement": "individuel_isole",
    }
    for cat in PREDICTABLE_CATS:
        row[f"p_raw_{cat}"] = 0.5 if cat in ("voiture", "marche") else 0.0
        row[f"p_{cat}"] = 0.5 if cat in ("voiture", "marche") else 0.0
    meta = {"schema": "progedo_on_common_set/v1", "run": "run/X",
            "moves_sha256": "abc", "summary": {"n_moves": 1}}
    if policy_sha is not None:
        meta["policy_sha256"] = policy_sha
    write_parquet([row], path, meta)


class TestGardePolitique:
    """Un ré-entraînement à contrat de variables inchangé ne bouge pas
    `spec_version` : sans empreinte, un parquet périmé était servi comme courant."""

    def _verdict(self, tmp_path, measured_sha, pinned_sha):
        from scripts.synthesis.build import build_model_predictions
        from scripts.synthesis.sources import probe
        path = tmp_path / "preds.parquet"
        _tiny_parquet(path, measured_sha)
        source = probe("test", path)

        class _Scorer:
            primary = type("m", (), {"name": "emd_jsd"})()
            secondary = None

            def score(self, frame, cerema):
                return {"emd_jsd": {"composite": 0.0}}

        return build_model_predictions(source, {}, _Scorer(), "run/X", "abc", pinned_sha)

    def test_empreintes_differentes_ecartent_la_mesure(self, tmp_path):
        out = self._verdict(tmp_path, "empreinte_ancienne", "empreinte_courante")
        assert out["available"] is False
        assert "politique" in out["reason"]
        assert "common-set-predict" in out["action"]

    def test_empreintes_identiques_laissent_passer(self, tmp_path):
        out = self._verdict(tmp_path, "meme_empreinte", "meme_empreinte")
        assert out.get("available") is not False

    def test_parquet_sans_empreinte_ne_declenche_pas_de_fausse_alarme(self, tmp_path):
        """Rétrocompatibilité : les parquets d'avant le correctif n'en portent pas.

        Contrepartie assumée : ils restent NON gardés sur cet axe, et c'est l'absence
        de la clé qui les identifie.
        """
        out = self._verdict(tmp_path, None, "empreinte_courante")
        assert out.get("available") is not False
