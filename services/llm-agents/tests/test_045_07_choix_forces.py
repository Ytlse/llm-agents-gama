"""Ticket 045, bloc D — ce que le décideur a décidé, et ce que la situation lui imposait (A5).

R10 : une synthèse publie les parts modales **des deux façons** — toutes décisions, et hors
      décisions à itinéraire unique. Les deux portent leur effectif.
R11 : le compte de choix forcés est publié à côté des parts, remonté et non recalculé.
R12 : la comparaison terme à terme entre bras se fait sur l'**intersection** des déplacements
      que tous ont réellement décidés, et le périmètre retenu est déclaré avec le chiffre.

Le fait, avec un exemple. Jean part travailler en voiture le matin. Le soir, sa voiture est au
bureau : le seul itinéraire qui existe pour rentrer est la voiture. **Personne ne décide rien** —
ni le modèle de langue, ni l'oracle, ni le tirage au sort. Ce trajet compte pourtant dans les
parts modales publiées, comme s'il avait été choisi.

Et leur nombre **dépend du bras**, puisqu'il découle de ce que le bras a décidé plus tôt :
prendre la voiture le matin, c'est s'imposer un retour en voiture le soir. Mesuré sur les 23
exécutions complètes de la cohorte v1, à population et jeu identiques : 393 pour
`duree_minimale`, 381 pour `majoritaire_voiture`, 300 à 359 pour les bras LLM, 286 pour
`aleatoire`. Soit 11 à 15 % de journée identique et non décidée, ce qui comprime mécaniquement
les écarts qu'on cherche à mesurer.

**Arbitrage de l'auteur : la contrainte n'est pas le défaut, elle est le cadre.** Un trajet
imposé par un choix antérieur reste un fait de la journée simulée, et une vraie journée en
comporte. On ne neutralise donc pas la chaîne. On publie **les deux chiffres**, parce qu'un seul
mélange ce que le décideur a décidé et ce que la situation lui imposait, et que la seconde
quantité varie d'un bras à l'autre. Les parts « toutes décisions » portent la conclusion ; les
parts hors itinéraire unique disent ce que le décideur a réellement fait.

Pour la comparaison entre bras, ni l'un ni l'autre ne suffit : « hors itinéraire unique » retire
des trajets **différents** selon le bras, donc ne rend pas la comparaison plus juste, il la
déplace. D'où R12 : l'intersection des situations que **tous** ont décidées, déclarée avec son
effectif.
"""

from __future__ import annotations

import pytest

from experiences import registre as R
from experiences.archive import Execution
from experiences.decision import METHODE_CHOIX_UNIQUE
from experiences.registre import perimetre_commun


def _trace(person_id, activity_id, mode, methode="llm"):
    """Une trace de décision minimale mais COMPLÈTE : l'archive refuse les traces partielles."""
    return {
        "person_id": person_id,
        "activity_id": activity_id,
        "methode": methode,
        "retenue": {"mode": mode},
        "presentees": [{"mode": mode}],
        "ecartees": [],
        "distribution": {mode: 1.0},
        "reponse_brute": None,
        "sources": {},
    }


@pytest.fixture
def synthese_banc(tmp_path):
    """Six décisions, dont DEUX à itinéraire unique, toutes deux en voiture.

    C'est le cas réel que l'alerte A5 décrit : un agent parti en voiture le matin n'a plus
    qu'un itinéraire pour rentrer le soir. Les choix forcés tirent donc la part voiture vers
    le haut sans que personne ne les ait décidés.
    """
    ex = Execution.creer(
        tmp_path / "exp_banc",
        {"nom": "exp_banc"},
        {},
        {"parallelisme": 1},
        {"graine_tirage": 42},
    )
    decisions = [
        _trace("p1", "a1", "car"),
        _trace("p1", "a2", "car", METHODE_CHOIX_UNIQUE),
        _trace("p2", "b1", "walk"),
        _trace("p2", "b2", "bike"),
        _trace("p3", "c1", "transit"),
        _trace("p3", "c2", "car", METHODE_CHOIX_UNIQUE),
    ]
    for t in decisions:
        ex.ajouter_decision(t)
    ex.ecrire_compteurs(
        {
            "attendus": 6,
            "attendus_exploitables": 6,
            "decides": 6,
            "choix_unique": 2,
            "couverture": {"attendus": 6, "attendus_bruts": 6, "decides": 6},
        }
    )
    ex.fermer()
    return R.synthese(ex.dossier)


# ── R10 / R11 : la synthèse publie les deux lectures ────────────────────────


def test_r10_les_deux_lectures_sont_publiees(synthese_banc):
    s = synthese_banc
    assert "parts_modales" in s
    assert "parts_modales_hors_choix_unique" in s


def test_r10_les_deux_lectures_portent_leur_effectif(synthese_banc):
    """Un pourcentage sans son effectif ne se relit pas : 100 % sur deux décisions n'est rien."""
    s = synthese_banc
    assert s["parts_modales"]["n"] > s["parts_modales_hors_choix_unique"]["n"]
    for bloc in (s["parts_modales"], s["parts_modales_hors_choix_unique"]):
        assert bloc["n"] == sum(bloc["effectifs"].values())


def test_r10_la_lecture_hors_choix_unique_retire_exactement_les_choix_forces(
    synthese_banc,
):
    s = synthese_banc
    ecart = s["parts_modales"]["n"] - s["parts_modales_hors_choix_unique"]["n"]
    assert ecart == s["choix_forces"]["n"]


def test_r10_les_deux_lectures_donnent_des_parts_differentes(synthese_banc):
    """Si elles coïncidaient, publier les deux n'apprendrait rien.

    Sur le banc, les choix forcés sont tous en voiture — c'est le cas réel, un agent parti en
    voiture rentre en voiture : les retirer doit faire baisser la part voiture.
    """
    toutes = synthese_banc["parts_modales"]["pourcent"]["car"]
    hors = synthese_banc["parts_modales_hors_choix_unique"]["pourcent"]["car"]
    assert hors < toutes


def test_r11_le_compte_de_choix_forces_est_remonte_pas_recalcule(synthese_banc):
    """`compteurs.choix_unique` existe déjà : la synthèse le relaie, elle n'invente pas."""
    bloc = synthese_banc["choix_forces"]
    assert bloc["n"] == 2
    assert bloc["part"] == 2 / synthese_banc["parts_modales"]["n"]
    assert "dépend du bras" in bloc["lecture"]


# ── R12 : le périmètre commun ───────────────────────────────────────────────


def test_r12_le_perimetre_commun_est_lintersection_des_decisions_reelles():
    """Seuls les déplacements que TOUS les bras ont réellement décidés entrent."""
    a = [
        _trace("p1", "a1", "car"),
        _trace("p1", "a2", "walk"),
        _trace("p2", "b1", "bike"),
    ]
    b = [
        _trace("p1", "a1", "walk"),
        _trace("p1", "a2", "car", METHODE_CHOIX_UNIQUE),  # forcé chez b, pas chez a
        _trace("p2", "b1", "car"),
    ]
    commun = perimetre_commun({"a": a, "b": b})
    assert commun["cles"] == {("p1", "a1"), ("p2", "b1")}
    assert commun["n"] == 2


def test_r12_le_perimetre_est_declare_avec_son_effectif_et_ce_quil_retire():
    """Un périmètre restreint sans son motif se lit comme une donnée manquante."""
    a = [_trace("p1", "a1", "car"), _trace("p1", "a2", "walk")]
    b = [_trace("p1", "a1", "walk"), _trace("p1", "a2", "car", METHODE_CHOIX_UNIQUE)]
    commun = perimetre_commun({"a": a, "b": b})
    assert commun["n"] == 1
    assert commun["retires"]["a"] == 1
    assert commun["retires"]["b"] == 1
    assert commun["motif"]


def test_r12_un_deplacement_absent_dun_bras_sort_du_perimetre():
    """Deux colonnes dont le dénominateur diffère ne se comparent pas terme à terme."""
    a = [_trace("p1", "a1", "car"), _trace("p2", "b1", "walk")]
    b = [_trace("p1", "a1", "walk")]
    commun = perimetre_commun({"a": a, "b": b})
    assert commun["cles"] == {("p1", "a1")}


def test_r12_trois_bras_donnent_un_perimetre_plus_etroit_que_deux():
    """Chaque bras supplémentaire ne peut que restreindre l'intersection, jamais l'élargir."""
    a = [
        _trace("p1", "a1", "car"),
        _trace("p2", "b1", "walk"),
        _trace("p3", "c1", "bike"),
    ]
    b = [
        _trace("p1", "a1", "walk"),
        _trace("p2", "b1", "car"),
        _trace("p3", "c1", "car"),
    ]
    c = [
        _trace("p1", "a1", "bike"),
        _trace("p2", "b1", "car", METHODE_CHOIX_UNIQUE),
        _trace("p3", "c1", "walk"),
    ]
    deux = perimetre_commun({"a": a, "b": b})["n"]
    trois = perimetre_commun({"a": a, "b": b, "c": c})["n"]
    assert trois < deux


def test_r12_un_seul_bras_rend_ses_propres_decisions():
    a = [_trace("p1", "a1", "car"), _trace("p1", "a2", "walk", METHODE_CHOIX_UNIQUE)]
    commun = perimetre_commun({"a": a})
    assert commun["n"] == 1 and commun["retires"]["a"] == 1
