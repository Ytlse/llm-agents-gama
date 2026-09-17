"""Ticket 045 lot 4b, révisé au ticket 088 § 3.3 — les quatre méthodes et leur chargement.

Les quatre méthodes tabulaires de référence — booster LightGBM, logit multinomial, régression
logistique à noyau, forêt aléatoire — sont câblées de la même façon : un format déclaré dans
`POLICY_FORMATS`, un libellé dans la table des familles, un chargement par `load_policy`.

**Ce fichier disait l'inverse jusqu'au 2026-09-16**, et il faut dire pourquoi il change, sinon
la prochaine session défera le ticket 088 en croyant restaurer le 044.

La forêt était tenue hors des deux tables au nom de la règle R7 du ticket 044 — *un témoin ne
devient pas un arbitre*. Deux choses ont changé depuis :

1. **La raison pratique a disparu.** Le lanceur dédié de la forêt a été écrit le 2026-09-11
   parce que le ticket 043 (régression logistique à noyau) modifiait ces deux mêmes tables au
   même moment, et qu'y écrire en parallèle aurait écrasé l'un des deux travaux. Le 043 est
   clos. Le contournement — inscrire la famille en mémoire et remplacer `load_policy` dans
   l'espace de noms du décideur — coûtait en revanche une expérience non rejouable par la CLI.

2. **Le mot « arbitre » désigne autre chose que la présence dans ces tables.** L'arbitre est le
   modèle dont la préférence tranche dans le score composite à deux oracles, et
   `specs/score_composite_deux_oracles.md` le nomme : c'est le MNL (R19, R20). Figurer dans
   `FAMILLES` ne confère aucun rôle d'arbitrage ; ces tables disent seulement « voici comment
   recharger cet artefact ». La forêt a d'ailleurs perdu son étiquette de témoin dans l'article
   lui-même (chapitre 4, brouillon v0.15) : elle est la quatrième méthode de référence, et le
   plafond se lit axe par axe sur les quatre.

Ce qui reste vrai et que ces tests continuent de fixer : le libellé de famille est **dérivé du
format déclaré par l'artefact**, jamais écrit en dur — une exécution de la forêt qui
s'annoncerait « lightgbm » dans les traces serait pire qu'une exécution sans libellé.

Ce que ces tests ne couvrent pas : la forêt se lance depuis l'HÔTE et non depuis le conteneur
`controller`, parce qu'elle se réajuste au chargement et que scikit-learn n'y est pas dans la
version d'estimation. Ce n'est pas un fait de câblage mais d'environnement, et c'est le
garde-fou de reproduction de `mode_choice_rf.py` qui le fait respecter, en mesurant.
"""

from __future__ import annotations

import json

import pytest
from experiences.chemins import racine_depot
from experiences.decideur_modele import FAMILLES

METHODES = {
    "lightgbm_mode_choice_policy": "scripts/progedo_logit/mode_choice_policy.json",
    "mnl_mode_choice_policy": "scripts/progedo_logit/mnl_model.json",
    "klr_mode_choice_policy": "scripts/progedo_logit/klr_model.json",
    "rf_mode_choice_policy": "scripts/progedo_logit/rf_mode_choice_policy.json",
}
FORMAT_RF = "rf_mode_choice_policy"


# ── Les quatre méthodes sont câblées de la même façon ───────────────────────


def test_les_quatre_methodes_sont_dans_la_table_des_libelles():
    assert set(METHODES) <= set(FAMILLES), sorted(set(METHODES) - set(FAMILLES))


def test_les_quatre_methodes_sont_acceptees_par_load_policy():
    from scripts.synthesis.model_on_common_set import POLICY_FORMATS

    assert set(METHODES) <= set(POLICY_FORMATS)


def test_chaque_famille_a_un_libelle_distinct():
    """Deux familles sous un même libellé rendraient les traces ininterprétables."""
    libelles = [FAMILLES[f] for f in METHODES]
    assert len(set(libelles)) == len(libelles), libelles


@pytest.mark.parametrize("format_, chemin", sorted(METHODES.items()))
def test_le_libelle_vient_du_format_declare_par_lartefact(format_, chemin):
    """Le libellé ne se devine pas du nom de fichier : il vient du champ `format`."""
    p = racine_depot() / chemin
    if not p.is_file():
        pytest.skip(f"artefact absent : {chemin}")
    # Tête du fichier seulement : `mode_choice_policy.json` pèse 18 Mo.
    tete = p.read_text(encoding="utf-8")[:400]
    assert f'"format": "{format_}"' in " ".join(tete.split())


def test_lartefact_de_la_foret_declare_bien_son_format():
    p = racine_depot() / METHODES[FORMAT_RF]
    if not p.is_file():
        pytest.skip("artefact absent")
    assert json.loads(p.read_text(encoding="utf-8"))["format"] == FORMAT_RF


# ── La forêt se charge par le chemin officiel, et rend un RFPredictor ───────


def test_la_foret_porte_son_propre_libelle_et_pas_celui_dune_autre():
    """Le risque que le lanceur documentait : une exécution rf annoncée « lightgbm »."""
    assert FAMILLES[FORMAT_RF] == "rf"


def test_load_policy_aiguille_la_foret_vers_son_chargeur():
    """`load_policy` doit rendre un RFPredictor, pas tenter un Booster LightGBM.

    Le réajustement coûte une quinzaine de secondes et vérifie au passage que la forêt
    reproduit ses métriques publiées : c'est le test le plus lent du fichier, et le seul qui
    prouve que le câblage du ticket 088 § 3.3 mène quelque part.
    """
    from scripts.synthesis.model_on_common_set import load_policy

    artefact = racine_depot() / METHODES[FORMAT_RF]
    spec_file = racine_depot() / "scripts/progedo_logit/feature_spec.json"
    trainset = racine_depot() / "scripts/progedo_logit/rf_mode_choice_trainset.npz"
    for p in (artefact, spec_file, trainset):
        if not p.is_file():
            pytest.skip(f"absent : {p.name}")

    spec = json.loads(spec_file.read_text(encoding="utf-8"))
    modele, lu = load_policy(artefact, spec)
    assert type(modele).__name__ == "RFPredictor"
    assert lu["format"] == FORMAT_RF
    assert modele.feature_name() == [f["name"] for f in spec["features"]]
    # Le garde-fou a tourné et il a conclu : sous une autre version de scikit-learn il aurait
    # levé, ce qui fait de cette assertion un contrôle d'environnement autant que de câblage.
    assert modele.controle["reproduit"] is True


def test_le_lanceur_dedie_ne_remplace_plus_rien():
    """Il vérifie la déclaration au lieu de l'injecter — sinon le câblage serait inutile."""
    from scripts.progedo_logit import lancer_experience_rf

    assert hasattr(lancer_experience_rf, "verifier_famille_rf")
    assert not hasattr(lancer_experience_rf, "enregistrer_famille_rf"), (
        "l'injection en mémoire a été retirée au ticket 088 § 3.3 : la famille est déclarée"
    )


def test_le_lanceur_accepte_la_declaration_en_place():
    from scripts.progedo_logit.lancer_experience_rf import verifier_famille_rf

    verifier_famille_rf()  # ne lève pas : les deux tables portent la famille
