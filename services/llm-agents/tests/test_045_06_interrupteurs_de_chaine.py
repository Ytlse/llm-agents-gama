"""Ticket 045, bloc E — l'interrupteur de chaîne est dans la définition, jamais implicite.

R13 : `vehicule_chaine` et `verrou_retour` sont des champs de `experience.yaml`, entrent dans
      `reglages_herites` d'une exécution, et entrent dans le nom dès qu'ils s'écartent de la
      référence, qui est **actif**.

Pourquoi c'est bloquant pour le 2×2 chaîne du lot 4e. Le mécanisme existe déjà — les drapeaux
`vehicle_chain_enabled` et `vehicle_return_home_lock` se pilotent par l'environnement — mais
`reglages_herites` ne portait que `agenda_anticipation_enabled` et `max_trip_candidates`. Deux
exécutions ne différant que par la chaîne auraient donc porté la **même définition, la même
signature et le même nom**, et rien dans leur trace n'aurait dit laquelle est laquelle.

C'est exactement le défaut audité par ce ticket — un réglage qui change la mesure sans laisser
de trace dans son identité — à un autre endroit du même système. Le corriger avant de lancer,
plutôt que de le découvrir après, est tout l'objet de l'exercice.

Ce que ces tests ne couvrent pas, et c'est voulu : les bras LLM se jouent tous **chaîne
active** (R14, décision de l'auteur). L'interrupteur n'existe ici que pour les sept bras
gratuits du 2×2.
"""

from __future__ import annotations

import pytest

from experiences import nommage as N
from experiences.experience import Experience


def _definition(**surcharges) -> dict:
    base = {
        "nom": "exp_test",
        "population": {"chemin": "data/population/population_1000_AAMAS_v5"},
        "jeu": {"nom": "population_1000_AAMAS_v5_20260316"},
        "gabarit": {"categorie": "itinary_multi_agent", "variante": None},
        "decideur": {"type": "duree_minimale"},
        "mode": "sans_simulateur",
        "calendrier": {"politique": "commune", "date": "2026-03-16", "graine": 42},
        "horizon_jours": 1,
        "memoire": False,
        "evenements": [],
        "graine_ordre": 42,
        "graine_tirage": 42,
        "regroupement": {"parallelisme": 8},
        "tolerances_horaires": N.TOLERANCES_REFERENCE,
        "max_candidats": 6,
        "attente_max_s": 120,
    }
    base.update(surcharges)
    return base


# ── Le champ existe, et sa référence est « actif » ──────────────────────────


def test_r13_la_chaine_est_active_par_defaut():
    """Une définition qui ne dit rien décrit le comportement nominal : chaîne active.

    La référence doit être le comportement réel de la simulation, sinon une définition
    antérieure à ce champ changerait de sens en silence.
    """
    exp = Experience.model_validate(_definition())
    assert exp.vehicule_chaine is True
    assert exp.verrou_retour is True


def test_r13_les_deux_interrupteurs_se_posent_independamment():
    """Couper le verrou de retour sans couper la position du véhicule doit rester possible."""
    exp = Experience.model_validate(_definition(verrou_retour=False))
    assert exp.vehicule_chaine is True
    assert exp.verrou_retour is False


def test_r13_les_interrupteurs_ne_touchent_ni_la_possession_ni_le_permis():
    """Garde-fou du lot 4e, point a : seuls la POSITION du véhicule et le VERROU se coupent.

    La possession, le permis et l'âge sont des attributs de la personne, présents dans les
    21 variables du contrat, que les deux décideurs voient légitimement. Les couper
    reviendrait à donner une voiture à tout le monde, ce qui ne mesure plus rien. Aucun
    champ de la définition ne doit permettre de le faire par mégarde.
    """
    # Contrôle EXACT, pas par sous-chaîne : « age » se trouve dans `graine_tirage`, et un
    # test qui crie au loup sur un mot innocent finit par être ignoré.
    interrupteurs = {c for c in Experience.model_fields if c in (
        "vehicule_chaine", "verrou_retour", "possession_vehicule", "permis",
        "age_minimum", "equipement_menage", "eligibilite_modes",
    )}
    assert interrupteurs == {"vehicule_chaine", "verrou_retour"}, (
        f"la définition ne doit porter QUE les deux interrupteurs du lot 1 du ticket 040 ; "
        f"trouvé {sorted(interrupteurs)}"
    )


# ── L'identité : nom et signature ───────────────────────────────────────────


def test_r13_la_chaine_coupee_entre_dans_le_nom():
    nominal = N.nom_canonique(_definition())
    coupee = N.nom_canonique(_definition(vehicule_chaine=False))
    assert nominal != coupee
    assert "chaine" in coupee or "nochn" in coupee, coupee


def test_r13_le_verrou_coupe_entre_dans_le_nom():
    nominal = N.nom_canonique(_definition())
    coupe = N.nom_canonique(_definition(verrou_retour=False))
    assert nominal != coupe


def test_r13_la_chaine_active_reste_muette():
    """La valeur de référence ne s'écrit pas (N7) : les noms existants ne bougent pas."""
    assert N.nom_canonique(_definition()) == N.nom_canonique(
        _definition(vehicule_chaine=True, verrou_retour=True)
    )


def test_r13_deux_conditions_du_2x2_ont_deux_signatures():
    """Le cœur de la règle : deux mesures différentes ne partagent pas une identité.

    Sans cela, la trace d'une exécution ne dirait pas dans quelle condition elle a tourné —
    et c'est précisément le défaut que ce ticket corrige ailleurs.
    """
    a = N.signature(_definition())
    b = N.signature(_definition(vehicule_chaine=False, verrou_retour=False))
    assert a != b


# ── La trace d'exécution ────────────────────────────────────────────────────


@pytest.mark.parametrize("actif", [True, False])
def test_r13_les_reglages_herites_portent_la_chaine(actif):
    """Une exécution doit pouvoir dire, seule, dans quelle condition elle a tourné."""
    from experiences.cli import reglages_herites_de

    exp = Experience.model_validate(
        _definition(vehicule_chaine=actif, verrou_retour=actif)
    )
    herites = reglages_herites_de(exp)
    assert herites["vehicule_chaine"] is actif
    assert herites["verrou_retour"] is actif
    # Les deux réglages déjà tracés ne disparaissent pas.
    assert "agenda_anticipation_enabled" in herites
    assert "max_trip_candidates" in herites
