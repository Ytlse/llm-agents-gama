"""Ticket 045, R18 — le nom d'une expérience n'est jamais muet sur sa population.

La cause racine du ticket tient en deux mécanismes qui se renforcent. Le formulaire proposait
la première cohorte par ordre alphabétique, donc la v1 (corrigé par R16). Et
`DEFAUTS_NOMMAGE["population"]` valait `population_1000_AAMAS`, ce qui rendait cette
population **muette** dans le nom (règle N7) : aucun des 46 noms d'expérience ne mentionnait de
substrat, ce qui se lisait comme « rien à signaler » et signifiait « toutes sur la v1 ».

Un substrat ne doit jamais être implicite dans le nom d'une mesure. La correction retire
`population` de la table des valeurs muettes : toute expérience porte désormais sa cohorte dans
son nom, quelle qu'elle soit.

Conséquence assumée, et c'est la bonne : les noms proposés à partir d'aujourd'hui diffèrent de
ceux d'hier. La table ne renomme rien de ce qui existe (N12) — le `nom` écrit dans
`experience.yaml` reste autoritaire — donc les définitions archivées gardent le leur.
"""

from __future__ import annotations

from experiences.nommage import DEFAUTS_NOMMAGE, nom_canonique


def _definition(chemin_population: str) -> dict:
    return {
        "population": {"chemin": chemin_population},
        "jeu": {"nom": "population_1000_AAMAS_v5_20260316"},
        "decideur": {"type": "local", "nom": "aleatoire", "graine": 42},
        "calendrier": {"politique": "commune", "date": "2026-03-16", "graine": 42},
        "mode": "sans_simulateur",
        "horizon_jours": 1,
        "memoire": False,
    }


def test_r18_la_population_nest_plus_une_valeur_muette():
    """La table des défauts ne doit plus contenir de population : aucune n'est « la normale »."""
    assert "population" not in DEFAUTS_NOMMAGE


def test_r18_le_nom_mentionne_la_cohorte_v5():
    nom = nom_canonique(_definition("data/population/population_1000_AAMAS_v5"))
    assert "pop-" in nom, nom


def test_r18_le_nom_mentionne_aussi_lancienne_cohorte():
    """Le point du ticket : c'est justement celle-là qui était invisible."""
    nom = nom_canonique(_definition("data/population/population_1000_AAMAS"))
    assert "pop-" in nom, nom


def test_r18_deux_cohortes_donnent_deux_noms_differents():
    """Le contrôle qui manquait : deux substrats ne peuvent plus porter le même nom.

    C'est exactement ce qui s'est produit — 46 définitions, trois orthographes du même chemin,
    et pas un nom pour dire laquelle lisait quoi.
    """
    v1 = nom_canonique(_definition("data/population/population_1000_AAMAS"))
    v5 = nom_canonique(_definition("data/population/population_1000_AAMAS_v5"))
    assert v1 != v5, (v1, v5)
