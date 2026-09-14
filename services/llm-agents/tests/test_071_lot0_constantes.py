"""Ticket 071, lot 0 — les constantes de la mémoire visée et la fenêtre d'âge.

Le lot 0 ne change aucun comportement de rappel : il DÉCLARE les constantes du § 2.10 du
ticket et câble la fenêtre d'âge sur l'horizon de l'expérience. Ces tests verrouillent
donc deux choses, et deux seulement :

1. les valeurs publiées sont bien celles du ticket — une constante qui dérive en silence
   rendrait inattribuable tout écart mesuré ensuite ;
2. le score de rappel EN SERVICE n'a pas bougé — les trois poids lus par `rank_nodes`
   gardent leurs valeurs, les deux nouveaux ne sont lus par personne. Un état
   intermédiaire non spécifié ne doit pas être exécutable.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from settings import settings

# ── 1. Les onze constantes du § 2.10, à leurs valeurs publiées ───────────────────

@pytest.mark.parametrize(
    ("nom", "attendu"),
    [
        ("memoire__force_k_importance", 6.0),
        ("memoire__force_delta_rappel_jours", 1.0),
        ("memoire__force_max_jours", 30.0),
        ("memoire__purge_seuil_poids", 0.01),
        ("memoire__retard_ref_s", 1800),
        ("memoire__importance_choc", 0.7),
        ("memoire__theta_gravite_cumulee", 0.7),
        ("memoire__confiance_seuil_service", 0.5),
        ("memoire__contre_exemples_seuil", 3),
        ("memoire__vivier_b_par_mode", 8),
        ("memoire__vivier_c_taille", 5),
        ("memoire__fenetre_age_max_jours", 60),
    ],
)
def test_les_constantes_publiees_sont_celles_du_ticket(nom, attendu):
    assert hasattr(settings.agent, nom), f"constante absente : {nom}"
    assert getattr(settings.agent, nom) == pytest.approx(attendu)


def test_le_seuil_de_choc_et_theta_sont_egaux():
    """Θ vaut le seuil du choc : un seul souvenir grave déclenche en journée.

    Les découpler sans le dire rendrait le déclenchement intrajournalier indépendant de
    ce que le dispositif appelle « une rupture ».
    """
    assert (
        settings.agent.memoire__theta_gravite_cumulee
        == settings.agent.memoire__importance_choc
    )


def test_la_duree_de_vie_d_un_souvenir_marquant_suit_sa_regle():
    """Règle de `k` : « je m'en souviendrai dans un mois ».

    Un souvenir `marquant` (gravité 1,0) doit garder la moitié de son poids à deux
    semaines et un cinquième à trente jours. C'est la règle qui a fait passer k de 3 à 6 ;
    la vérifier ici empêche de rebaisser k sans s'en apercevoir.
    """
    import math

    s0 = settings.agent.long_term_retrieval__force_base_jours
    k = settings.agent.memoire__force_k_importance
    force = min(s0 * (1 + k * 1.0), settings.agent.memoire__force_max_jours)

    assert math.exp(-14 / force) == pytest.approx(0.5, abs=0.05)
    assert math.exp(-30 / force) == pytest.approx(0.2, abs=0.05)


def test_le_plafond_de_force_borne_meme_un_s0_triple():
    """`FORCE_MAX` s'applique DÈS L'ÉCRITURE, pas seulement au renforcement.

    Au point de sensibilité publié (S0 = 8,3 j, Park et al.) comme à S0 × 3, la durée de
    vie d'un souvenir `marquant` dépasserait le plafond sans cette borne.
    """
    plafond = settings.agent.memoire__force_max_jours
    k = settings.agent.memoire__force_k_importance
    for s0 in (8.3, 2.8 * 3):
        assert min(s0 * (1 + k * 1.0), plafond) == pytest.approx(plafond)


# ── 2. Les cinq poids, et l'invariant « rien ne bouge avant le lot 2 » ───────────

def test_les_deux_poids_nouveaux_existent_a_leur_valeur_cible():
    assert settings.agent.long_term_retrieval__importance_weight == pytest.approx(0.20)
    assert settings.agent.long_term_retrieval__affinite_weight == pytest.approx(0.20)


def test_les_cinq_poids_ont_bascule_ensemble():
    """Depuis le lot 2, les cinq poids sont lus et portent leurs valeurs cibles.

    Ils ont basculé ENSEMBLE, et c'était la condition. Les composantes entrent en valeur
    ABSOLUE depuis le ticket 048 — la normalisation min-max a justement été supprimée pour
    rendre deux décisions comparables : n'en basculer qu'une partie aurait fait tourner le
    dispositif sous un régime de score que personne n'a spécifié.

    ⚠ Ce test remplace `test_le_score_en_service_n_a_pas_bouge`, qui verrouillait l'état
    INTERMÉDIAIRE du lot 0, quand le classement ne lisait que trois poids sur cinq.
    """
    assert settings.agent.long_term_retrieval__sim_weight == pytest.approx(0.30)
    assert settings.agent.long_term_retrieval__keyword_weight == pytest.approx(0.10)
    assert settings.agent.long_term_retrieval__time_weight == pytest.approx(0.20)


def test_les_poids_lus_par_le_classement_somment_a_un():
    """Invariant de comparabilité, quel que soit le lot en cours.

    Ce test lit les poids que `rank_nodes` lit RÉELLEMENT, en inspectant le code plutôt
    qu'en recopiant une liste : il restera vrai après le lot 2, quand les cinq poids
    seront lus et sommeront de nouveau à 1.
    """
    import inspect

    from llm.longterm import MultiUserLongTermMemory

    tous = (
        "long_term_retrieval__sim_weight",
        "long_term_retrieval__keyword_weight",
        "long_term_retrieval__time_weight",
        "long_term_retrieval__importance_weight",
        "long_term_retrieval__affinite_weight",
    )
    source = inspect.getsource(MultiUserLongTermMemory.rank_nodes)
    poids_lus = [nom for nom in tous if nom in source]
    assert poids_lus, "aucun poids lu par rank_nodes — le classement ne pondère plus rien"
    total = sum(getattr(settings.agent, nom) for nom in poids_lus)
    assert total == pytest.approx(1.0), (
        f"poids lus par rank_nodes : {poids_lus} → somme {total:.2f}"
    )


# ── 3. La fenêtre d'âge suit l'horizon ──────────────────────────────────────────

def test_la_fenetre_d_age_vaut_l_horizon_quand_il_est_court():
    assert settings.agent.fenetre_age_pour_horizon(5) == 5


def test_la_fenetre_d_age_est_plafonnee():
    """Au-delà du plafond, la fenêtre ne suit plus l'horizon."""
    assert settings.agent.fenetre_age_pour_horizon(90) == 60
    assert settings.agent.fenetre_age_pour_horizon(60) == 60


def test_un_horizon_de_soixante_jours_n_est_plus_coupe_a_trente():
    """Le défaut historique de 30 jours retirait son second mois à un run de 60.

    C'est le défaut que le lot 0 corrige ; ce test échoue sur le comportement d'avant.
    """
    assert settings.agent.fenetre_age_pour_horizon(60) > 30
    assert settings.agent.long_term_max_days_query == 60


def test_un_horizon_absurde_ne_produit_pas_une_memoire_muette():
    """Un horizon nul rendrait la fenêtre vide, donc la mémoire silencieusement inerte.

    Une mémoire vide ne se distingue pas d'une mémoire coupée dans les sorties : le cas
    est ramené à un jour plutôt que laissé produire zéro.
    """
    assert settings.agent.fenetre_age_pour_horizon(0) == 1
    assert settings.agent.fenetre_age_pour_horizon(-3) == 1
