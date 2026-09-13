"""Ticket 045, lot 4b — les quatre familles, et le chemin PROPRE à chacune.

Trois familles sont des **arbitres** : le booster LightGBM, le logit multinomial et la
régression logistique à noyau. Elles sont câblées dans `POLICY_FORMATS` / `load_policy` et
dans la table des libellés, et le décideur les charge directement.

La quatrième, le témoin random forest, ne l'est **pas**, et ce n'est pas un oubli : c'est la
règle R7 du ticket 044 — *un témoin ne devient pas un arbitre*, les deux modules du score ne
doivent pas le connaître. Il se joue par son lanceur dédié, qui inscrit sa famille et remplace
`load_policy` dans le seul espace de noms du décideur, pour la durée de son processus.
L'exécution produite est une vraie exécution de la plateforme ; aucun module de score n'a
appris l'existence du témoin.

Ce fichier existe parce que j'ai failli défaire cette règle en câblant le témoin comme les
trois autres — le lanceur venait justement d'être écrit pour éviter d'écraser le travail
concurrent du ticket 043 sur ces mêmes tables. Les tests ci-dessous fixent le contrat des deux
côtés, pour que la prochaine tentative se heurte à un test plutôt qu'à une relecture.
"""

from __future__ import annotations

import json

import pytest

from experiences.chemins import racine_depot
from experiences.decideur_modele import FAMILLES

ARBITRES = {
    "lightgbm_mode_choice_policy": "scripts/progedo_logit/mode_choice_policy.json",
    "mnl_mode_choice_policy": "scripts/progedo_logit/mnl_model.json",
    "klr_mode_choice_policy": "scripts/progedo_logit/klr_model.json",
}
TEMOIN = ("rf_mode_choice_policy", "scripts/progedo_logit/rf_mode_choice_policy.json")


# ── Les trois arbitres sont câblés ──────────────────────────────────────────


def test_les_trois_arbitres_sont_dans_la_table_des_libelles():
    assert set(ARBITRES) <= set(FAMILLES), sorted(set(ARBITRES) - set(FAMILLES))


def test_les_trois_arbitres_sont_acceptes_par_load_policy():
    from scripts.synthesis.model_on_common_set import POLICY_FORMATS

    assert set(ARBITRES) <= set(POLICY_FORMATS)


def test_chaque_famille_a_un_libelle_distinct():
    """Deux familles sous un même libellé rendraient les traces ininterprétables."""
    libelles = [FAMILLES[f] for f in ARBITRES]
    assert len(set(libelles)) == len(libelles), libelles


@pytest.mark.parametrize("format_, chemin", sorted(ARBITRES.items()))
def test_le_libelle_vient_du_format_declare_par_lartefact(format_, chemin):
    """Le libellé ne se devine pas du nom de fichier : il vient du champ `format`."""
    p = racine_depot() / chemin
    if not p.is_file():
        pytest.skip(f"artefact absent : {chemin}")
    # Tête du fichier seulement : `mode_choice_policy.json` pèse 18 Mo.
    tete = p.read_text(encoding="utf-8")[:400]
    assert f'"format": "{format_}"' in " ".join(tete.split())


# ── Le témoin reste dehors, et son lanceur l'ouvre ──────────────────────────


def test_le_temoin_nest_PAS_cable_comme_un_arbitre():
    """R7 du ticket 044 : les modules de score ne connaissent pas le témoin."""
    from scripts.synthesis.model_on_common_set import POLICY_FORMATS

    format_, _ = TEMOIN
    assert format_ not in FAMILLES, (
        "le témoin ne doit pas figurer statiquement dans la table des libellés : "
        "son lanceur l'y inscrit pour la durée de son processus"
    )
    assert format_ not in POLICY_FORMATS


def test_le_lanceur_dedie_existe_et_ouvre_la_famille():
    """Sans lui, le témoin serait injouable — et le ticket 045 le demande au lot 4b."""
    from scripts.progedo_logit import lancer_experience_rf

    assert hasattr(lancer_experience_rf, "enregistrer_famille_rf")


def test_le_lanceur_rend_le_temoin_chargeable_puis_le_laisse_dehors():
    """Il ouvre la famille dans SON processus, pas sur le disque ni pour les autres."""
    from experiences import decideur_modele
    from scripts.progedo_logit.lancer_experience_rf import enregistrer_famille_rf

    format_, _ = TEMOIN
    officiel = decideur_modele.load_policy
    try:
        enregistrer_famille_rf()
        assert FAMILLES[format_] == "rf"
        assert decideur_modele.load_policy is not officiel, "load_policy doit être remplacée"
    finally:
        decideur_modele.load_policy = officiel
        FAMILLES.pop(format_, None)


def test_lartefact_du_temoin_declare_bien_son_format():
    format_, chemin = TEMOIN
    p = racine_depot() / chemin
    if not p.is_file():
        pytest.skip(f"artefact absent : {chemin}")
    assert json.loads(p.read_text(encoding="utf-8"))["format"] == format_
