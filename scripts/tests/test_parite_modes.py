"""Parité des listes de modes — la loss de calibration doit ranger un mode comme la production.

Ce que ce fichier verrouille est un invariant dont la violation ne lève AUCUNE exception :
un mode classé « transport collectif » côté journal de production et « marche » côté loss
de calibration produit deux parts modales plausibles et incomparables. C'est exactement ce
qui s'est produit deux fois :

* **2026-08-26, le Téléo.** `cableway` manquait à `categorize_mode` ; une option
  « foot,cableway,foot » tombait sur le mot « foot » et le téléphérique du réseau Tisséo
  était compté en MARCHE — le mode déjà le plus sous-représenté du modèle.
* **2026-09-04, le TER.** Ni `rail`, ni `train`, ni `ter` n'étaient dans aucune liste de la
  loss ; le train partait au même endroit. Le défaut était latent jusqu'à ce que `rail`
  entre dans le graphe OTP : la sonde du ticket 031 (q. 16) mesure **1 883 des 11 288
  itinéraires** portant un train, et **58,4 % en 3ᵉ couronne**.

Le test de parité qui existait alors comparait `categorize_mode` à un **littéral recopié**
dans le fichier de test. Un littéral ne tombe que si l'INSTRUMENT change ; il ne tombe
jamais si la PRODUCTION change. C'est cette asymétrie qui a laissé les deux défauts se
former. Ici, les listes de production sont **lues dans leur source**, et le test échoue le
jour où l'une d'elles gagne un mode que la loss ne connaît pas.

Deux gardes contre la vacuité (« l'absence de mesure produit le score parfait ») :
une boucle sur une liste vide passe sans rien vérifier, donc les effectifs et quelques
modes-témoins sont assertés avant d'itérer.

Lancement : PYTHONPATH=. llm-agents/.venv/bin/python -m pytest scripts/tests/test_parite_modes.py
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from llm_module.core.mode_choice import canonical_mode
from scripts.models_influence.prompt_calibration_lib import MODE_KEYWORDS, categorize_mode
from scripts.synthesis.frames import CHOSEN_MODE_MAP
from scripts.synthesis.model_on_common_set import CANONICAL_TO_CAT

REPO_ROOT = Path(__file__).resolve().parents[2]
MOVE_LOGGER = REPO_ROOT / "llm-agents" / "urban_mobility_agents" / "utils" / "move_logger.py"

# Ensembles de `move_logger` → catégorie EMC² attendue de la loss. Le rail va avec les
# transports collectifs : la référence EMC² du dépôt (`cerema_values.yaml`) ne publie pas
# de part « train » distincte, et `CHOSEN_MODE_MAP["Train"]` comme
# `CANONICAL_TO_CAT["train"]` appliquent déjà cette fusion.
PRODUCTION_VERS_CATEGORIE = {
    "_BUS_MODES": "transports_collectifs",
    "_RAIL_MODES": "transports_collectifs",
    "_CAR_MODES": "voiture",
    "_BIKE_MODES": "velo",
    "_WALK_MODES": "marche",
}

# Effectif minimal et mode-témoin de chaque liste : une liste vidée par accident ferait
# passer toutes les boucles ci-dessous sans rien mesurer.
TEMOINS = {
    "_BUS_MODES": (8, "cableway"),
    "_RAIL_MODES": (1, "rail"),
    "_CAR_MODES": (2, "car"),
    "_BIKE_MODES": (2, "bicycle"),
    "_WALK_MODES": (2, "foot"),
}


def _listes_de_production() -> dict[str, set[str]]:
    """Les ensembles de modes de `move_logger`, LUS DANS LA SOURCE.

    `urban_mobility_agents.utils.move_logger` importe `settings`, dont l'import repointe
    le lien `experiments/current` — un effet de bord qui détournerait la trace d'un run en
    cours. Les listes sont des littéraux : on les relit à la source, ce qui suffit à
    détecter la divergence (même technique que `test_model_on_common_set._canonical_fr`).
    """
    source = MOVE_LOGGER.read_text(encoding="utf-8")
    trouvees: dict[str, set[str]] = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Assign):
            continue
        for cible in node.targets:
            if isinstance(cible, ast.Name) and cible.id in PRODUCTION_VERS_CATEGORIE:
                trouvees[cible.id] = set(ast.literal_eval(node.value))
    return trouvees


PRODUCTION = _listes_de_production()


def test_les_listes_de_production_sont_bien_lues():
    """Garde anti-vacuité : sans elle, tous les tests suivants passeraient à vide."""
    assert MOVE_LOGGER.exists(), MOVE_LOGGER
    assert set(PRODUCTION) == set(PRODUCTION_VERS_CATEGORIE), (
        "une liste de modes de move_logger.py a été renommée ou supprimée : "
        f"lues={sorted(PRODUCTION)}")
    for nom, (effectif_min, temoin) in TEMOINS.items():
        assert len(PRODUCTION[nom]) >= effectif_min, (nom, sorted(PRODUCTION[nom]))
        assert temoin in PRODUCTION[nom], (nom, temoin)


@pytest.mark.parametrize("nom", sorted(PRODUCTION_VERS_CATEGORIE))
def test_la_loss_range_chaque_mode_de_production_comme_la_production(nom):
    """Le cœur du test : la loss doit reconnaître TOUT mode que la production sait nommer."""
    attendue = PRODUCTION_VERS_CATEGORIE[nom]
    for mode in sorted(PRODUCTION[nom]):
        assert categorize_mode(mode) == attendue, f"{nom} : {mode!r} seul"
        # Les libellés réels d'OTP sont des chaînes : « foot,rail,foot ». Le mode
        # structurant doit gagner sur les jambes de marche qui l'encadrent.
        if nom != "_WALK_MODES":
            assert categorize_mode(f"foot,{mode},foot") == attendue, f"{nom} : {mode!r} en chaîne"


def test_le_train_est_reconnu_dans_toutes_ses_ecritures():
    """`rail` est ce qu'OTP rend ; `train` et `ter` sont ce que le modèle peut recopier."""
    for brut in ("rail", "train", "TER", "foot,rail,foot", "Train", "intercités"):
        assert categorize_mode(brut) == "transports_collectifs", brut


def test_un_autocar_nest_pas_une_voiture():
    """Le piège du mot « car » : en français c'est un autocar, et liO n'est QUE des autocars.

    La cascade cherchait ses mots-clés par sous-chaîne : « autocar » contient « car », donc
    un car régional était compté en VOITURE — l'inverse exact de ce qu'il est. La
    correspondance se fait désormais par mot, et les libellés d'autocar sont listés du côté
    des transports collectifs, qui passe avant la voiture.
    """
    for brut in ("autocar", "car liO", "car liO 31", "Autocar interurbain", "coach",
                 "car scolaire", "school_bus", "foot,school_bus,foot"):
        assert categorize_mode(brut) == "transports_collectifs", brut
    # La voiture, elle, reste la voiture.
    for brut in ("car", "__car__", "voiture", "foot,car,foot", "conducteur"):
        assert categorize_mode(brut) == "voiture", brut


def test_la_correspondance_se_fait_par_mot_et_non_par_sous_chaine():
    """Un mot de trois lettres cherché par sous-chaîne se trouve partout.

    « cargo » et « écarter » contiennent « car » ; sous l'ancienne règle ils étaient rangés
    dans VOITURE. Un libellé inconnu doit tomber dans la catégorie fourre-tout, où il est
    COMPTÉ (`mass_report` / A-Autre), et non déguisé en mode plausible.
    """
    for brut in ("cargo", "écarter", "carrefour", "terminal", "hiver"):
        assert categorize_mode(brut) == "Autre", brut


def test_le_vocabulaire_de_la_loss_ne_perd_pas_ses_categories():
    """Les quatre catégories EMC² sont toutes servies, dans l'ordre où la cascade les teste."""
    assert [categorie for categorie, _ in MODE_KEYWORDS] == [
        "transports_collectifs", "voiture", "velo", "marche"]
    for _categorie, mots in MODE_KEYWORDS:
        assert mots, _categorie


def test_le_pont_avec_les_modes_canoniques_tient():
    """Trois vocabulaires, un seul verdict : mode canonique, libellé du journal, loss.

    `canonical_mode` (répartition du LLM) et `categorize_mode` (loss) ne se déduisent pas
    l'une de l'autre. Elles doivent pourtant s'accorder, sans quoi la part modale mesurée
    par la calibration cesse d'être comparable à celle du journal de production.
    """
    for mode_brut in sorted(PRODUCTION["_BUS_MODES"] | PRODUCTION["_RAIL_MODES"]):
        canonique = canonical_mode(mode_brut)
        assert canonique in ("public_transport", "train"), (mode_brut, canonique)
        assert CANONICAL_TO_CAT[canonique] == categorize_mode(mode_brut), mode_brut
    for mode_brut in sorted(PRODUCTION["_BIKE_MODES"]):
        assert CANONICAL_TO_CAT[canonical_mode(mode_brut)] == categorize_mode(mode_brut)
    assert CHOSEN_MODE_MAP["Train"] == categorize_mode("rail")
