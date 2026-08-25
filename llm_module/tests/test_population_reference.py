"""Le cadrage de la population enquêtée est lu, complet et cohérent (ticket 020).

Ce fichier de test EST le lecteur qui manquait. Avant le ticket 020,
`population_emc2_2023.yaml` n'était mentionné que dans un tableau de la doc
d'installation : il avait l'air d'être une donnée, il n'alimentait aucun contrôle.
Les tests ci-dessous échouent si une valeur de cadrage devient incohérente — et
`test_couronnes_identiques_a_cerema_values` échoue si les modalités de couronne
divergent de celles auxquelles les parts modales sont comparées, qui est l'erreur que
le ticket 020 a trouvée en production.
"""

from pathlib import Path

import pytest
import yaml

from llm_module.core.population_reference import (
    COURONNES, MIN_AGE, OUT_OF_PERIMETER, PopulationReferenceError,
    couronne_commune_counts, couronne_population_shares, find_reference,
    household_targets, household_weight, population_reference, survey_window,
    surveyed_weekdays, validate)

REPO_ROOT = Path(__file__).resolve().parents[2]
CEREMA_VALUES = REPO_ROOT / "scripts" / "data" / "population" / "cerema_values.yaml"


@pytest.fixture(scope="module")
def reference() -> dict:
    return population_reference()


def test_le_cadrage_est_present_et_lisible():
    assert find_reference() is not None, (
        "population_emc2_2023.yaml est VERSIONNÉ dans le dépôt : son absence est une "
        "anomalie, pas un cas normal comme pour feature_spec.json.")


def test_plus_aucun_bloc_de_cadrage_ne_dort_en_commentaire(reference):
    """Les quatre sections structurantes sont ACTIVES, pas commentées."""
    for section in ("enquete", "territoire", "population", "menages_equipement_voiture"):
        assert section in reference, f"section « {section} » absente du cadrage actif"
    assert "methodologie" in reference["enquete"]
    assert "echantillon" in reference["enquete"]
    assert "repartition_par_territoire" in reference["population"]


def test_couronnes_identiques_a_cerema_values(reference):
    """Le classement et les cibles doivent désigner les MÊMES territoires.

    C'est le critère d'acceptation central du ticket 020 : si les modalités divergent,
    les parts modales par zone se comparent à des cibles qui ne parlent pas des mêmes
    communes, et personne ne le voit.
    """
    cerema = yaml.safe_load(CEREMA_VALUES.read_text(encoding="utf-8"))
    cibles = set(cerema["parts_modales_2023"]["lieu_residence"])
    # `cerema_values.yaml` indexe par identifiant (souligné), le cadrage par libellé.
    cadrage = {z.replace(" ", "_") for z in COURONNES}
    assert cadrage == cibles, (
        f"modalités divergentes : cadrage {sorted(cadrage)} contre cibles {sorted(cibles)}")


def test_le_hors_perimetre_n_est_pas_une_couronne():
    assert OUT_OF_PERIMETER not in COURONNES, (
        "« hors périmètre » est une cinquième modalité, pas une couronne : un domicile "
        "à 100 km du Capitole n'a pas de cible EMC² à laquelle se comparer.")


def test_communes_par_couronne(reference):
    counts = couronne_commune_counts()
    assert list(counts) == list(COURONNES)
    assert sum(counts.values()) == reference["territoire"]["perimetre_2023"]["communes"]
    assert counts["Toulouse"] == 1


def test_concentration_spatiale_cible(reference):
    shares = couronne_population_shares()
    assert set(shares) == set(COURONNES)
    assert abs(sum(shares.values()) - 100.0) < 0.01
    coeur = shares["Toulouse"] + shares["1ere couronne"]
    publiee = 100.0 * reference["population"]["concentration"][
        "coeur_agglomeration_toulouse_plus_1ere_couronne"]
    assert abs(coeur - publiee) < 1.0, (
        f"la ventilation par couronne donne {coeur:.1f} % en cœur d'agglomération, le "
        f"cadrage en publie {publiee:.1f} %")


def test_fenetre_d_enquete_est_automne_hiver():
    debut, fin = survey_window()
    assert debut == "2022-09-20" and fin == "2023-02-18"
    assert debut[5:] > fin[5:], (
        "la fenêtre franchit le 1er janvier : tout filtre saisonnier travaillant en "
        "mois-jour doit tester « >= début OU <= fin », jamais un intervalle simple.")


def test_l_enquete_ne_compte_aucun_week_end():
    jours = surveyed_weekdays()
    assert jours == (1, 2, 3, 4, 5)
    assert max(jours) <= 5


def test_age_minimum(reference):
    assert MIN_AGE == 5
    assert reference["enquete"]["methodologie"]["age_minimum_enquete"] == MIN_AGE


def test_cibles_menage_sont_annoncees_comme_telles():
    targets = household_targets()
    assert targets["taille_moyenne_menage"] == pytest.approx(2.08, abs=0.01)
    assert targets["voitures_par_menage"] == pytest.approx(1.25, abs=0.01)
    total = (targets["sans_voiture_pct"] + targets["une_voiture_pct"]
             + targets["deux_voitures_plus_pct"])
    assert total == pytest.approx(100.0, abs=1.0)


def test_poids_menage_debiaise_la_taille():
    """Trois ménages de tailles 1, 2 et 4 : la moyenne brute ment, la pondérée non."""
    menage_de_chaque = [1] + [2] * 2 + [4] * 4          # 7 personnes, 3 ménages
    brut = sum(menage_de_chaque) / len(menage_de_chaque)
    poids = [household_weight(s) for s in menage_de_chaque]
    pondere = sum(w * s for w, s in zip(poids, menage_de_chaque)) / sum(poids)
    assert brut == pytest.approx(3.0)                    # biais de taille
    assert pondere == pytest.approx(7 / 3, abs=1e-9)     # vraie moyenne par ménage
    assert sum(poids) == pytest.approx(3.0)              # un poids de 1 par ménage


def test_poids_menage_sans_taille_ne_compte_pas():
    """Sans taille de ménage, la personne n'a pas de base ménage — pas de repli à 1."""
    assert household_weight(None) == 0.0
    assert household_weight(0) == 0.0
    assert household_weight("") == 0.0


# ── Le validateur refuse, il ne replie pas ────────────────────────────────────

def _valide(reference: dict) -> dict:
    import copy
    return copy.deepcopy(reference)


def test_validate_refuse_des_couronnes_incompletes(reference):
    casse = _valide(reference)
    casse["territoire"]["decoupage_concentrique"][1]["communes"] = 1
    with pytest.raises(PopulationReferenceError, match="communes"):
        validate(casse)


def test_validate_refuse_des_couronnes_renommees(reference):
    casse = _valide(reference)
    casse["territoire"]["decoupage_concentrique"][0]["nom"] = "Centre"
    with pytest.raises(PopulationReferenceError, match="couronnes"):
        validate(casse)


def test_validate_refuse_une_repartition_qui_ne_somme_pas(reference):
    casse = _valide(reference)
    casse["population"]["repartition_par_classe_age"]["5-17_ans"] = 40
    with pytest.raises(PopulationReferenceError, match="somme"):
        validate(casse)


def test_validate_refuse_une_taille_de_menage_qui_ne_tombe_pas(reference):
    casse = _valide(reference)
    casse["population"]["totaux_perimetre_2023"]["taille_moyenne_menage"] = 3.5
    with pytest.raises(PopulationReferenceError, match="taille de ménage"):
        validate(casse)


def test_validate_refuse_un_cadrage_ampute(reference):
    casse = _valide(reference)
    del casse["population"]["totaux_perimetre_2023"]
    with pytest.raises(PopulationReferenceError, match="incomplet"):
        validate(casse)
