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

**Depuis le 2026-09-04 (ticket 022), la source est unique.** Les cinq listes littérales de
`move_logger` ont disparu : le dépôt lit `llm_module/data/mode_hierarchy_emc2.json`, gelé
depuis l'annexe « Hiérarchie des modes » du rapport AUAT/CEREMA (p. 53) et contrôlé sur les
microdonnées. Ce fichier de test lit donc **la ressource de production**, et il vérifie en
plus qu'aucune cascade de modes n'a été réintroduite à la main dans `move_logger`.

Deux gardes contre la vacuité (« l'absence de mesure produit le score parfait ») :
une boucle sur une liste vide passe sans rien vérifier, donc les effectifs et quelques
modes-témoins sont assertés avant d'itérer.

Lancement : PYTHONPATH=. llm-agents/.venv/bin/python -m pytest scripts/tests/test_parite_modes.py
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from llm_module.core.mode_choice import _MODE_KEYWORDS, canonical_mode
from llm_module.core.mode_hierarchy import DEFAULT_RESOURCE, hierarchy
from scripts.models_influence.prompt_calibration_lib import MODE_KEYWORDS, categorize_mode
from scripts.synthesis.frames import CHOSEN_MODE_MAP
from scripts.synthesis.model_on_common_set import CANONICAL_TO_CAT

REPO_ROOT = Path(__file__).resolve().parents[2]
MOVE_LOGGER = REPO_ROOT / "llm-agents" / "urban_mobility_agents" / "utils" / "move_logger.py"

# Familles de la hiérarchie → nom historique de la liste de `move_logger` (les deux noms
# sont cités dans la doc et dans `llm_agent`) → catégorie EMC² attendue de la loss. Le rail
# va avec les transports collectifs : la référence EMC² du dépôt (`cerema_values.yaml`) ne
# publie pas de part « train » distincte, et `CHOSEN_MODE_MAP["Train"]` comme
# `CANONICAL_TO_CAT["train"]` appliquent déjà cette fusion.
FAMILLES_PAR_LISTE = {
    "_BUS_MODES": ("metro", "tram", "cableway", "bus"),
    "_RAIL_MODES": ("rail",),
    "_CAR_MODES": ("car",),
    "_BIKE_MODES": ("bicycle",),
    "_WALK_MODES": ("foot",),
}
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
    """Les modes de chaque famille, LUS DANS LA RESSOURCE DE PRODUCTION.

    `urban_mobility_agents.utils.move_logger` importe `settings` : on ne l'importe pas
    depuis un test. Mais il n'y a plus de littéral à relire dans sa source — il dérive ses
    cinq ensembles de `llm_module/data/mode_hierarchy_emc2.json`, exactement le fichier lu
    ici. Le test compare donc la loss à la production elle-même.
    """
    familles = hierarchy().legs_by_family
    return {nom: set().union(*(familles[f] for f in cles))
            for nom, cles in FAMILLES_PAR_LISTE.items()}


PRODUCTION = _listes_de_production()


def test_les_listes_de_production_sont_bien_lues():
    """Garde anti-vacuité : sans elle, tous les tests suivants passeraient à vide."""
    assert DEFAULT_RESOURCE.exists(), DEFAULT_RESOURCE
    assert set(PRODUCTION) == set(PRODUCTION_VERS_CATEGORIE), (
        "une famille de la hiérarchie a été renommée ou supprimée : "
        f"lues={sorted(PRODUCTION)}")
    for nom, (effectif_min, temoin) in TEMOINS.items():
        assert len(PRODUCTION[nom]) >= effectif_min, (nom, sorted(PRODUCTION[nom]))
        assert temoin in PRODUCTION[nom], (nom, temoin)


def test_move_logger_ne_reecrit_pas_sa_propre_cascade():
    """Aucune liste de modes littérale ne doit revenir dans `move_logger`.

    C'est la garde qui empêche la régression de fond du ticket 022 : cinq listes écrites à
    la main, dont une incomplète suffisait à faire disparaître un mode d'une part modale.
    Le test lit la source (jamais l'import : `settings` a des effets de bord) et vérifie
    que les cinq noms sont des vues de la hiérarchie, c'est-à-dire des affectations
    calculées et non des littéraux.
    """
    source = MOVE_LOGGER.read_text(encoding="utf-8")
    arbre = ast.parse(source)
    litteraux = []
    for node in ast.walk(arbre):
        if not isinstance(node, ast.Assign):
            continue
        for cible in node.targets:
            if not (isinstance(cible, ast.Name) and cible.id in PRODUCTION_VERS_CATEGORIE):
                continue
            if isinstance(node.value, (ast.Set, ast.List, ast.Tuple, ast.Dict)):
                litteraux.append(cible.id)
    assert not litteraux, (
        f"{litteraux} sont redevenus des littéraux dans move_logger.py. La hiérarchie des "
        "modes a UNE source : llm_module/data/mode_hierarchy_emc2.json.")
    assert "primary_label" in source, (
        "`_plan_transport_mode` ne consulte plus la hiérarchie : il a probablement "
        "retrouvé une cascade de `if`.")


def test_la_hierarchie_place_le_collectif_avant_la_voiture():
    """Le cran mesuré par l'axe A7 : 760 des 770 déplacements mixtes sont codés TC.

    Il était inversé dans `move_logger` — la voiture était testée EN PREMIER (ticket 022,
    M1). Rang publié : voiture conducteur au 19, tout le collectif entre 1 et 13.
    """
    h = hierarchy()
    for famille in ("metro", "tram", "cableway", "bus", "rail"):
        assert h.family_rank[famille] < h.family_rank["car"], famille
    assert h.family_rank["car"] < h.family_rank["motorbike"] < h.family_rank["bicycle"]
    assert h.family_rank["bicycle"] < h.family_rank["foot"]


def test_la_hierarchie_place_le_bus_avant_le_train():
    """L'arbitrage du ticket 022, et il surprend : le BUS gagne contre le train.

    Rapport p. 53 : bus Tisséo au rang 4, TER liO au rang 8. Mesuré sur les microdonnées :
    34 des 35 déplacements mixtes bus/autocar ↔ train tranchés sont codés bus. Un
    itinéraire « autocar liO + TER » est donc un déplacement en transports collectifs de
    surface — ce que `move_logger` faisait déjà, et ce que `mode_choice` et `task_worker`
    faisaient à l'envers.
    """
    h = hierarchy()
    assert h.family_rank["bus"] < h.family_rank["rail"]
    assert h.primary_label(("foot", "bus", "rail", "foot")) == "Transports_collectifs"
    assert h.primary_label(("foot", "rail", "foot")) == "Train"
    assert h.primary_canonical(("foot", "bus", "rail", "foot")) == "public_transport"
    assert h.primary_canonical(("foot", "rail", "foot")) == "train"


def test_la_hierarchie_est_sourcee_et_mesuree():
    """Ni postulée, ni recopiée sans contrôle : la ressource porte sa provenance.

    Garde anti-vacuité de second niveau : une hiérarchie exportée depuis des microdonnées
    illisibles produirait « zéro exception », donc un accord parfait par absence de mesure.
    """
    doc = json.loads(DEFAULT_RESOURCE.read_text(encoding="utf-8"))
    source = doc["source_publiee"]
    assert source["page"] == 53 and "AUAT" in source["rapport"]
    assert len(source["ordre"]) == 36, "l'annexe publie 36 modes"
    accord = doc["mesure"]["accord_avec_l_ordre_publie"]
    assert accord["observations_informatives"] >= 2000, accord
    assert accord["paires_testees"] >= 40, accord
    assert accord["paires_conformes"] == accord["paires_testees"], accord["exceptions"]
    a7 = doc["controles"]["a7_voiture_tc_convention_ticket_020"]
    assert (a7["n"], a7["collectif_au_sens_non_autre"], a7["autre"]) == (770, 760, 10), a7
    assert doc["provenance"]["fichiers"], "empreintes des microdonnées absentes"


def test_les_quatre_tables_de_production_suivent_la_hierarchie():
    """Une seule définition, partout : les trois cascades du dépôt dérivent du même ordre.

    `mode_choice._MODE_KEYWORDS` (répartition du LLM), la loss `MODE_KEYWORDS`, et les
    ponts `CHOSEN_MODE_MAP` / `CANONICAL_TO_CAT` doivent tous ranger un mode comme la
    hiérarchie. `mode_choice` est vérifiée à l'import ; ici on le redit côté test, et on
    ajoute le cas qui distinguait les deux avant le ticket 022.
    """
    h = hierarchy()
    assert tuple(mode for mode, _ in _MODE_KEYWORDS) == h.canonical_order()
    for jambes in (("foot", "bus", "rail", "foot"), ("foot", "rail", "foot"),
                   ("car",), ("bicycle",), ("foot",), ("foot", "cableway", "foot")):
        libelle = h.primary_label(jambes)
        canonique = h.primary_canonical(jambes)
        chaine = ",".join(jambes)
        assert canonical_mode(chaine) == canonique, chaine
        assert CHOSEN_MODE_MAP[libelle] == CANONICAL_TO_CAT[canonique], chaine
        assert categorize_mode(chaine) == CANONICAL_TO_CAT[canonique], chaine


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
