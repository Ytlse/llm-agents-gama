"""Ticket 071, lot 1 — gravité, durée de vie, rétention : les valeurs et les invariants.

Spécification de référence : `specs/ticket_071/tests_lot1.md`, sections 3 à 5 et 7. Les cas
portent les mêmes identifiants (A1, B2, C7…) pour qu'un test et sa raison d'être se retrouvent.

Tout ici est PUR : aucun simulateur, aucun modèle, aucun disque. Le comportement de bout en
bout est dans `test_071_lot1_chaine.py`.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm.gravite import (
    NIVEAUX,
    borne_0_1,
    ecart_de_rang,
    est_purgeable,
    force_apres_rappel,
    force_initiale,
    gravite_concept,
    gravite_deterministe,
    gravite_jugee,
    journal_des_composantes,
    poids_temporel,
)
from settings import settings

# ── Scénarios de référence (specs/ticket_071/tests_lot1.md, § 2) ────────────────
# Ils viennent de ce que la simulation produit : une observation `arrival` porte un retard,
# une observation `tc_timeout` dit un véhicule manqué, la chaîne des véhicules dit un mode
# contraint. (retard_s, correspondance_ratee, incident_reseau, mode_contraint, I_det attendu)
SCENARIOS = {
    "nominal": (0, False, False, False, 0.00),
    "petit_retard": (540, False, False, False, 0.15),
    "quart_heure": (900, False, False, False, 0.25),
    "demi_heure": (1800, False, False, False, 0.50),
    "panne_ligne_a": (2700, True, False, True, 0.80),
}


def _det(nom: str) -> float:
    retard, corresp, incident, contraint, _ = SCENARIOS[nom]
    return gravite_deterministe(retard, corresp, incident, contraint)[0]


# ═══════════════════════════ A. Gravité déterministe ════════════════════════════


@pytest.mark.parametrize("nom", sorted(SCENARIOS))
def test_A1_les_cinq_scenarios_de_reference(nom):
    assert _det(nom) == pytest.approx(SCENARIOS[nom][4], abs=1e-9)


def test_A1bis_la_panne_de_la_ligne_a_vaut_exactement_le_seuil_du_choc_plus_un_dixieme():
    """La panne des expériences d'hystérésis doit valoir 0,80.

    C'est la valeur sur laquelle le ticket appuie le choix de Θ = 0,7 : « à Θ = 1,0 le choc
    étudié n'aurait pas déclenché ». Si le code en produit une autre, c'est le réglage de Θ qui
    devient indéfendable, pas seulement ce test qui casse.
    """
    assert _det("panne_ligne_a") == pytest.approx(0.80, abs=1e-9)
    assert _det("panne_ligne_a") > settings.agent.memoire__importance_choc


def test_A2_le_retard_sature_a_retard_ref():
    """Au-delà du retard de référence, la composante ne monte plus."""
    assert gravite_deterministe(2700)[0] == pytest.approx(0.50)
    assert gravite_deterministe(36_000)[0] == pytest.approx(0.50)


def test_A3_une_arrivee_en_avance_n_est_pas_un_bonus():
    """Un retard négatif vaut zéro, jamais une gravité négative.

    Sinon une avance viendrait COMPENSER un incident réel survenu dans la même entrée.
    """
    assert gravite_deterministe(-600)[0] == 0.0
    assert gravite_deterministe(-600, correspondance_ratee=True)[0] == pytest.approx(0.20)


def test_A4_la_somme_est_bornee_a_un():
    valeur, _ = gravite_deterministe(36_000, True, True, True)
    assert valeur == pytest.approx(1.0, abs=1e-9)
    assert valeur <= 1.0


def test_A5_chaque_composante_pese_ce_qu_elle_annonce():
    assert gravite_deterministe(retard_s=1800)[0] == pytest.approx(0.50)
    assert gravite_deterministe(correspondance_ratee=True)[0] == pytest.approx(0.20)
    assert gravite_deterministe(incident_reseau=True)[0] == pytest.approx(0.20)
    assert gravite_deterministe(mode_contraint=True)[0] == pytest.approx(0.10)


def test_A6_le_detail_des_composantes_est_rendu():
    """L'instrumentation doit pouvoir dire QUELLE composante a joué, pas seulement combien."""
    valeur, detail = gravite_deterministe(900, True, False, True)
    assert valeur == pytest.approx(0.25 + 0.20 + 0.10)
    assert detail.retard == pytest.approx(0.25)
    assert detail.correspondance_ratee == pytest.approx(0.20)
    assert detail.incident_reseau == 0.0
    assert detail.mode_contraint == pytest.approx(0.10)
    assert set(detail.composantes_actives()) == {"retard", "correspondance_ratee", "mode_contraint"}


def test_A7_la_composante_sans_source_est_declaree_au_journal():
    """Une composante inactive n'est pas une composante nulle, et le dispositif doit le dire.

    Zéro est exactement la valeur d'un trajet parfait : sans déclaration, la gravité serait
    sous-estimée sans qu'aucun symptôme n'apparaisse.
    """
    ligne = journal_des_composantes()
    assert "INACTIVES" in ligne
    assert "incident_reseau" in ligne.split("INACTIVES")[1]
    # et la chaîne est bien posée : le paramètre traverse la fonction
    assert gravite_deterministe(incident_reseau=True)[1].incident_reseau == pytest.approx(0.20)


def test_A8_les_autres_composantes_ne_sont_pas_repondrees():
    """Avec l'incident inactif, les trois composantes disponibles plafonnent à 0,80.

    Repondérer pour « compenser » l'absence changerait l'échelle de gravité en silence.
    """
    assert gravite_deterministe(36_000, True, False, True)[0] == pytest.approx(0.80)


# ═════════════════════ B. Niveau nommé et règle du maximum ══════════════════════


def test_B1_les_cinq_echelons_ont_leurs_valeurs():
    """Un concept SEUL dans son niveau porte la valeur pleine de l'échelon.

    C'est le cas le plus courant, et c'est le défaut n° 1 corrigé le 2026-09-14 : la formule
    d'origine le pénalisait de 0,05.
    """
    attendu = {"anodin": 0.10, "notable": 0.30, "genant": 0.50, "grave": 0.75, "marquant": 1.00}
    for niveau, valeur in attendu.items():
        assert gravite_jugee(niveau) == pytest.approx(valeur), niveau
    assert NIVEAUX == attendu


def test_B2_le_modele_ne_peut_pas_degrader_un_fait_mesure():
    """LE test du lot. Règle de sécurité non négociable.

    Un modèle qui qualifie de `notable` une panne de quarante-cinq minutes avec correspondance
    ratée et mode contraint ne doit pas pouvoir la dégrader : le fait l'emporte.
    """
    i_llm = gravite_jugee("notable")
    assert gravite_concept(i_llm, _det("panne_ligne_a")) == pytest.approx(0.80)


def test_B3_quand_le_modele_est_d_accord_son_jugement_passe():
    assert gravite_concept(gravite_jugee("grave"), _det("demi_heure")) == pytest.approx(0.75)


def test_B4_la_surestimation_n_est_bornee_que_par_le_plafond():
    """Comportement DOCUMENTÉ, pas souhaité : la règle du maximum ne protège que vers le bas.

    Ce test fige l'asymétrie pour que personne ne croie l'inverse en lisant la règle. Le jour
    où un plafond symétrique est décidé, il doit être réécrit sciemment.
    """
    assert gravite_concept(gravite_jugee("marquant"), _det("nominal")) == pytest.approx(1.00)


def test_B5_le_maximum_porte_sur_tout_le_groupe_consomme():
    """Le pire du groupe, pas le dernier ni la moyenne."""
    groupe = [_det("petit_retard"), _det("panne_ligne_a"), _det("nominal")]
    assert gravite_concept(gravite_jugee("anodin"), max(groupe)) == pytest.approx(0.80)


def test_B6_un_niveau_inconnu_ne_fait_pas_perdre_la_reflexion():
    """Le concept retombe sur la gravité déterministe, et le fait est journalisé."""
    assert gravite_jugee("catastrophique") is None
    assert gravite_concept(gravite_jugee("catastrophique"), _det("demi_heure")) == pytest.approx(0.50)


@pytest.mark.parametrize("absent", [None, "", "   "])
def test_B7_un_niveau_absent_ne_fait_pas_perdre_la_reflexion(absent):
    assert gravite_jugee(absent) is None
    assert gravite_concept(gravite_jugee(absent), _det("quart_heure")) == pytest.approx(0.25)


def test_B8_le_departage_ne_deplace_jamais_d_un_niveau():
    """Trois `genant` rangés 1, 2, 3 : 0,55 / 0,50 / 0,45, et rien ne franchit un échelon."""
    valeurs = [gravite_jugee("genant", n_niveau=3, rang=r) for r in (1, 2, 3)]
    assert valeurs == pytest.approx([0.55, 0.50, 0.45])
    assert all(NIVEAUX["notable"] < v < NIVEAUX["grave"] for v in valeurs)


def test_B9_le_departage_est_nul_quand_le_concept_est_seul():
    """Défaut n° 1 corrigé : rien à départager quand il n'y a qu'un candidat."""
    assert ecart_de_rang(1, 1) == 0.0
    assert gravite_jugee("marquant", n_niveau=1, rang=1) == pytest.approx(1.00)
    assert gravite_jugee("genant", n_niveau=1, rang=1) == pytest.approx(0.50)


def test_B10_la_gravite_jugee_ne_depasse_jamais_un():
    """Défaut n° 2 corrigé : un `marquant` premier de trois valait 1,05.

    Sa durée de vie serait passée de 19,60 à 20,44 jours, hors de la table publiée.
    """
    assert gravite_jugee("marquant", n_niveau=3, rang=1) == pytest.approx(1.00)
    assert force_initiale(gravite_jugee("marquant", n_niveau=3, rang=1)) == pytest.approx(19.60)


def test_B11_les_bornes_du_depart_age_sont_plus_un_et_moins_un():
    assert ecart_de_rang(3, 1) == pytest.approx(1.0)
    assert ecart_de_rang(3, 2) == pytest.approx(0.0)
    assert ecart_de_rang(3, 3) == pytest.approx(-1.0)
    # un rang hors bornes est ramené dans l'intervalle plutôt que de produire un écart aberrant
    assert ecart_de_rang(3, 99) == pytest.approx(-1.0)
    assert ecart_de_rang(3, 0) == pytest.approx(1.0)


def test_B12_borne_0_1():
    assert borne_0_1(-5) == 0.0
    assert borne_0_1(5) == 1.0
    assert borne_0_1(0.42) == pytest.approx(0.42)


# ════════════════ C. Durée de vie, rappel et renforcement ══════════════════════

TABLE_FORCE = {0.00: 2.80, 0.10: 4.48, 0.30: 7.84, 0.50: 11.20, 0.75: 15.40, 1.00: 19.60}


@pytest.mark.parametrize(("gravite", "attendue"), sorted(TABLE_FORCE.items()))
def test_C1_table_des_durees_de_vie_initiales(gravite, attendue):
    assert force_initiale(gravite) == pytest.approx(attendue, abs=0.01)


# (gravité, Δt en jours, poids attendu) — la table publiée dans memory-stm-ltm.md
TABLE_POIDS = [
    (0.00, 7, 0.08), (0.00, 14, 0.007),
    (0.50, 7, 0.54), (0.50, 14, 0.29), (0.50, 30, 0.07), (0.50, 60, 0.005),
    (0.75, 7, 0.63), (0.75, 14, 0.40), (0.75, 30, 0.14), (0.75, 60, 0.02),
    (1.00, 7, 0.70), (1.00, 14, 0.49), (1.00, 30, 0.22), (1.00, 60, 0.05),
]


@pytest.mark.parametrize(("gravite", "jours", "attendu"), TABLE_POIDS)
def test_C2_table_des_poids_dans_le_temps(gravite, jours, attendu):
    """Si le code s'écarte de cette table, c'est la spécification publiée qui ment."""
    assert poids_temporel(jours, force_initiale(gravite)) == pytest.approx(attendu, abs=0.01)


def test_C3_le_plafond_s_applique_des_l_ecriture(monkeypatch):
    """Au point de sensibilité publié (S0 = 8,3 j, Park et al.), un `marquant` partirait à 58 j."""
    monkeypatch.setattr(settings.agent, "long_term_retrieval__force_base_jours", 8.3)
    assert 8.3 * 7 == pytest.approx(58.1)  # ce que donnerait la formule sans plafond
    assert force_initiale(1.00) == pytest.approx(30.0)


def test_C4_le_renforcement_est_additif_et_non_multiplicatif():
    """Dix rappels d'un trajet banal : 12,80 j. Un facteur × 1,15 donnerait 11,33 j."""
    f = force_initiale(0.0)
    for _ in range(10):
        f = force_apres_rappel(f)
    assert f == pytest.approx(12.80, abs=0.01)
    assert f != pytest.approx(2.8 * 1.15**10, abs=0.01)


def test_C5_nombre_de_rappels_jusqu_au_plafond():
    """Vingt-huit rappels pour un trajet banal, onze pour un `marquant`.

    Ce sont les deux chiffres sur lesquels la spécification appuie le choix de δ = 1 jour.
    """
    def _rappels_jusqu_au_plafond(gravite: float) -> int:
        f, n = force_initiale(gravite), 0
        while f < settings.agent.memoire__force_max_jours:
            f, n = force_apres_rappel(f), n + 1
        return n

    assert _rappels_jusqu_au_plafond(0.00) == 28
    assert _rappels_jusqu_au_plafond(1.00) == 11


def test_C6_le_plafond_tient_au_renforcement():
    f = force_initiale(1.00)
    for _ in range(100):
        f = force_apres_rappel(f)
    assert f == pytest.approx(30.0)


def test_C7_une_force_absente_retombe_sur_la_constante_par_defaut():
    """Une entrée écrite avant le lot 1 n'a pas de `force` : elle ne doit pas valoir zéro.

    Un poids nul la sortirait du rappel sans qu'aucune règle ne l'ait décidé.
    """
    assert poids_temporel(7, None) == pytest.approx(poids_temporel(7, 2.8))
    assert force_apres_rappel(None) == pytest.approx(3.8)


# ═══════════════════════════ E. Rétention ═══════════════════════════════════════


@pytest.mark.parametrize(
    ("gravite", "jours", "purgeable"),
    [
        (0.00, 12, False),   # poids 0,0138
        (0.00, 13, True),    # poids 0,0096
        (1.00, 30, False),   # poids 0,216 — un `marquant` d'un mois reste
        (1.00, 90, False),   # poids 0,0101, encore au-dessus du seuil
        (1.00, 95, True),    # poids 0,0079
    ],
)
def test_E1_la_purge_suit_le_poids_et_non_le_type(gravite, jours, purgeable):
    """Avant le lot 1, la rétention se jouait sur l'âge et le type seuls.

    Un souvenir `marquant` de trente et un jours tombait avec les trajets ordinaires.
    """
    assert est_purgeable(jours, force_initiale(gravite)) is purgeable
