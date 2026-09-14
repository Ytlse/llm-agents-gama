"""Ticket 071, lot 2 — axes, trois viviers, score à cinq composantes.

Contrat : `specs/ticket_071/tests_lot2.md`. Les identifiants de cas (A1, B8, C3…) y renvoient.

Le lot 2 a été livré sans ses tests, sur décision de l'auteur ; ce fichier honore le contrat
écrit avant le code.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm.axes import (
    affinite_axes,
    affinite_meteo,
    creneau_de,
    meteo_de,
    mode_canonique,
    normaliser_lieu,
    normaliser_motif,
)
from llm.longterm import (
    MODELE_PLONGEMENT_DEFAUT,
    MemorySearchResult,
    MultiUserLongTermMemory,
)
from llm.memory import MemoryEntry, MemoryType
from settings import settings
from sim_clock import wall_clock

T0 = 1773637200  # 16 mars 2026, 05:00 murales


@pytest.fixture()
def journal():
    """Collecte les lignes de loguru.

    `caplog` de pytest ne les voit pas : loguru n'écrit pas dans le `logging` standard. Un
    test qui vérifie une alarme doit vérifier qu'elle est bien ÉMISE, pas seulement qu'un
    drapeau a changé — une alarme muette ne se distingue pas d'une alarme absente.
    """
    from loguru import logger

    lignes: list = []
    sink = logger.add(lambda m: lignes.append(str(m)), level="INFO")
    yield lignes
    logger.remove(sink)


# ═════════════════════════ A. Normalisation des axes ════════════════════════════


def test_A1_le_mode_principal_l_emporte_sur_la_premiere_jambe():
    """« foot,bus,foot » est un trajet en transport en commun, pas une marche.

    C'est la hiérarchie AUAT/CEREMA qui décide, celle qui fait déjà autorité dans le dépôt :
    une cascade écrite dans le module des axes en aurait dupliqué une sixième, et une liste
    incomplète rend un chiffre plausible et faux.
    """
    assert mode_canonique("foot,bus,foot") == "public_transport"


@pytest.mark.parametrize(
    ("etiquette", "attendu"),
    [("car", "car"), ("bicycle", "cycling"), ("foot", "walking"), ("", None), (None, None)],
)
def test_A2_modes_canoniques(etiquette, attendu):
    assert mode_canonique(etiquette) == attendu


def test_A3_un_mode_inconnu_vaut_none_et_non_un_fourre_tout():
    """Un mode inconnu doit être COMPTÉ et signalé, jamais rangé d'office à côté."""
    from llm.axes import MODES_INCONNUS

    avant = dict(MODES_INCONNUS)
    assert mode_canonique("licorne") is None
    assert MODES_INCONNUS != avant, "un mode inconnu doit laisser une trace"


@pytest.mark.parametrize(
    "graphie", ["Line: 401", "line:401", "LINE : 401", " line:  401 ", "401"]
)
def test_A4_deux_graphies_d_une_meme_ligne_se_rencontrent(graphie):
    """Sans normalisation, trois souvenirs de la même ligne ne se rencontrent jamais."""
    assert normaliser_lieu(graphie) == "401"


@pytest.mark.parametrize(
    ("heure", "attendu"),
    [(8, "matin"), (12, "midi"), (18, "soir"), (23, "soir"), (3, "nuit"), (5, "nuit")],
)
def test_A5_les_quatre_creneaux(heure, attendu):
    # `datetime` NAÏF, volontairement : les souvenirs portent des champs muraux de simulation
    # et non un instant absolu. Y attacher un fuseau réintroduirait celui du processus, qui
    # est exactement le défaut corrigé le 2026-09-04.
    assert creneau_de(datetime(2026, 3, 16, heure, 12)) == attendu  # noqa: DTZ001


def test_A6_un_axe_non_resolu_vaut_none():
    assert creneau_de(None) is None
    assert normaliser_lieu(None) is None
    assert normaliser_motif("") is None
    assert meteo_de(None) is None


@pytest.mark.parametrize(
    ("w", "attendu"),
    [
        ({"weather_code": 71, "precip_mm": 0.0, "temperature": 1}, "neige"),
        ({"weather_code": 61, "precip_mm": 2.0, "temperature": 12}, "pluie"),
        ({"weather_code": 0, "precip_mm": 0.0, "temperature": 33}, "canicule"),
        ({"weather_code": 0, "precip_mm": 0.0, "temperature": -2}, "froid"),
        ({"weather_code": 0, "precip_mm": 0.0, "temperature": 15}, "sec"),
        # un jour chaud ET pluvieux est classé `pluie` : c'est la pluie qui fait renoncer
        # au vélo, pas les degrés
        ({"weather_code": 61, "precip_mm": 3.0, "temperature": 32}, "pluie"),
    ],
)
def test_A7_cascade_meteo(w, attendu):
    assert meteo_de(w) == attendu


def test_A8_l_etiquette_de_mode_n_est_pas_remplacee():
    """`parse_option_modes` relit ces étiquettes dans le TEXTE du prompt.

    L'axe se DÉRIVE de l'étiquette, il ne la remplace pas : les traduire ou les réécrire
    casserait la calibration et les parts modales de `moves.csv`.
    """
    import inspect

    from llm import axes

    source = inspect.getsource(axes)
    assert "mode_label" not in source or "LIT l'étiquette" in source


# ═══════════════════ C. Les cinq composantes et l'affinité ══════════════════════


def test_C3_un_souvenir_sans_aucun_axe_concordant_reste_classable():
    """La règle de non-exclusion : l'affinité est un BONUS, jamais un veto."""
    a = affinite_axes(
        "cycling", "canal", "matin", "leisure",
        objet_courant="car", lieu_courant="rocade",
        creneau_courant="soir", motif_courant="work",
    )
    assert a == 0.0, "aucune concordance : zéro, et non une valeur négative"


def test_C4_un_axe_discordant_ne_retranche_rien():
    """Un souvenir qui concorde sur l'objet seul vaut exactement le poids de l'objet."""
    assert affinite_axes(
        "cycling", "canal", "matin", "leisure",
        objet_courant="cycling", lieu_courant="rocade",
        creneau_courant="soir", motif_courant="work",
    ) == pytest.approx(0.50)


def test_C5_les_quatre_poids_d_axes_somment_a_un():
    assert affinite_axes(
        "a", "b", "c", "d",
        objet_courant="a", lieu_courant="b", creneau_courant="c", motif_courant="d",
    ) == pytest.approx(1.0)


def test_C6_un_axe_absent_ne_s_apparie_pas_avec_un_axe_present():
    assert affinite_axes(None, objet_courant="cycling") == 0.0
    assert affinite_axes("cycling", objet_courant=None) == 0.0


def test_C7_deux_inconnues_ne_font_pas_une_correspondance():
    """C'est le point le plus important du module.

    Faire concorder deux axes absents produirait de la RESSEMBLANCE à partir d'une absence de
    mesure — motif récurrent dans ce projet, où l'absence de mesure produit volontiers le
    score parfait.
    """
    assert affinite_axes(None, None, None, None) == 0.0
    assert affinite_meteo(None, None) == 0.0


def test_C11_l_affinite_d_objet_apparie_un_ensemble():
    """Une décision offre PLUSIEURS modes : exiger l'égalité avec un seul n'a pas de sens."""
    assert affinite_axes("cycling", objet_courant={"car", "cycling"}) == pytest.approx(0.50)
    assert affinite_axes("train", objet_courant={"car", "cycling"}) == 0.0


def test_C12_l_affinite_meteo_est_un_appariement_exact():
    assert affinite_meteo("pluie", "pluie") == 1.0
    assert affinite_meteo("pluie", "sec") == 0.0


def test_C1_les_cinq_poids_somment_a_un():
    total = (
        settings.agent.long_term_retrieval__sim_weight
        + settings.agent.long_term_retrieval__keyword_weight
        + settings.agent.long_term_retrieval__time_weight
        + settings.agent.long_term_retrieval__importance_weight
        + settings.agent.long_term_retrieval__affinite_weight
    )
    assert total == pytest.approx(1.0)


# ═══════════════════════════ D. Le plongement ═══════════════════════════════════


def test_D3_le_modele_de_plongement_par_defaut_est_celui_en_service():
    """Le paramètre est branché, le modèle ne change pas : aucun index à reconstruire."""
    assert MODELE_PLONGEMENT_DEFAUT == "all-MiniLM-L6-v2"


def test_D1_le_parametre_de_plongement_est_lu_par_le_code():
    import inspect

    from llm.longterm import MultiUserLongTermMemory as M

    source = inspect.getsource(M._init_shared_index)
    assert "settings.agent.embedding_model" in source, "le paramètre doit commander le modèle"
    assert 'HuggingFaceEmbedding(model_name="all-MiniLM-L6-v2")' not in source


# ═════════════════════ B. Les trois viviers ═════════════════════════════════════


class _IndexDouble:
    def __init__(self, noeuds):
        self._noeuds = noeuds

    def as_retriever(self, **_k):
        class _R:
            async def aretrieve(_s, _q):
                return list(self._noeuds)

        return _R()


class _Ltm(MultiUserLongTermMemory):
    def __init__(self, noeuds=()):
        self.shared_index = _IndexDouble(noeuds)
        self.user_metadata = {}
        self.metadata_access_times = {}
        self.long_term_memory_filter_by_datetime = False
        self.metrics = {"queries": 0, "cache_hits": 0, "cache_misses": 0}
        self._dirty = set()

    def ensure_user_initialized(self, person_id):
        self.user_metadata.setdefault(person_id, {"entries": []})

    def _save_user_metadata(self, person_id):
        pass

    def _schedule_flush(self):
        pass


def _concept(doc_id, mode, jours=1, gravite=0.0, motif="work", pid="42"):
    return MemoryEntry(
        content=f'["{doc_id}", "k", "s", "t", "{motif}"]',
        timestamp=wall_clock(T0) - timedelta(days=jours),
        memory_type=MemoryType.CONCEPT,
        person_id=pid,
        doc_id=doc_id,
        importance=gravite,
        axe_objet=mode,
        axe_motif=motif,
        observations=1,
    )


def test_B3_le_vivier_par_objet_prend_les_plus_graves_d_abord():
    ltm = _Ltm()
    ltm.ensure_user_initialized("42")
    ltm.user_metadata["42"]["entries"] = [
        _concept(f"42_{i}", "cycling", jours=i + 1, gravite=i / 20.0) for i in range(12)
    ]
    res = ltm.viviers_structures("42", ["cycling"])
    plafond = settings.agent.memoire__vivier_b_par_mode
    assert len(res) == plafond
    # les plus graves : indices 11..4
    assert {r.metadata["doc_id"] for r in res} == {f"42_{i}" for i in range(11, 11 - plafond, -1)}


def test_B2_un_mode_sans_souvenir_rend_un_vivier_vide_sans_exception():
    ltm = _Ltm()
    ltm.ensure_user_initialized("42")
    ltm.user_metadata["42"]["entries"] = [_concept("42_0", "cycling")]
    assert ltm.viviers_structures("42", ["train"]) == []


def test_B4_le_vivier_des_chocs_ignore_tout_contexte():
    """Un souvenir grave remonte sans condition de lieu, d'heure ni de motif."""
    ltm = _Ltm()
    ltm.ensure_user_initialized("42")
    choc = _concept("42_choc", "train", jours=40, gravite=0.9, motif="leisure")
    ltm.user_metadata["42"]["entries"] = [_concept("42_0", "cycling"), choc]
    res = ltm.viviers_structures("42", ["cycling"])
    origines = {r.metadata["doc_id"]: r.metadata["vivier"] for r in res}
    assert origines.get("42_choc") == "C"


def test_B1_un_souvenir_des_deux_viviers_n_apparait_qu_une_fois():
    ltm = _Ltm()
    ltm.ensure_user_initialized("42")
    ltm.user_metadata["42"]["entries"] = [_concept("42_0", "cycling", gravite=0.9)]
    res = ltm.viviers_structures("42", ["cycling"])
    assert len(res) == 1
    assert res[0].metadata["vivier"] == "B", "le vivier par objet est rencontré en premier"


def test_B5_les_viviers_structures_ne_dependent_pas_de_l_index():
    """Aucun plongement, aucune requête vectorielle : l'index peut être muet."""
    ltm = _Ltm(noeuds=[])
    ltm.ensure_user_initialized("42")
    ltm.user_metadata["42"]["entries"] = [_concept("42_0", "cycling", gravite=0.9)]
    assert len(ltm.viviers_structures("42", ["cycling"])) == 1


def test_B8_la_chute_a_velo_du_matin_atteint_la_decision_du_soir():
    """LE cas qui justifie le lot 2.

    Une chute à vélo à 8 h 12, motif loisir, doit peser sur une décision de 18 h 40 vers le
    travail où le vélo figure parmi les options. Ni le lieu, ni le créneau, ni le motif ne
    coïncident : c'est l'objet qui les relie, et l'objet suffit. Avant le lot 2, ce souvenir
    n'était atteignable que par la ressemblance de texte.
    """
    ltm = _Ltm()
    ltm.ensure_user_initialized("42")
    chute = MemoryEntry(
        content="je suis tombé à vélo boulevard de Strasbourg",
        timestamp=wall_clock(T0).replace(hour=8, minute=12),
        memory_type=MemoryType.CONCEPT,
        person_id="42",
        doc_id="42_chute",
        importance=0.9,
        axe_objet="cycling",
        axe_lieu="boulevard de strasbourg",
        axe_creneau="matin",
        axe_motif="leisure",
        observations=1,
    )
    ltm.user_metadata["42"]["entries"] = [chute]

    servis = ltm.viviers_structures("42", ["cycling", "car"])
    assert [r.metadata["doc_id"] for r in servis] == ["42_chute"]

    # et il reste classable, alors qu'aucun axe ne concorde avec la décision du soir
    score = affinite_axes(
        chute.axe_objet, chute.axe_lieu, chute.axe_creneau, chute.axe_motif,
        objet_courant={"cycling", "car"}, lieu_courant="place esquirol",
        creneau_courant="soir", motif_courant="work",
    )
    assert score == pytest.approx(0.50), "seul l'objet concorde, et il suffit"


def test_B7_la_part_de_chaque_vivier_est_journalisee(journal):
    ltm = _Ltm()
    ltm.ensure_user_initialized("42")
    ltm._viviers_fenetre = []
    ltm._alarme_vivier_b = False
    ltm._alarme_vivier_a = False
    servi = MemorySearchResult(content="x", metadata={"doc_id": "d", "vivier": "B"}, score=0.0)
    for _ in range(ltm._FENETRE_VIVIERS):
        ltm._compter_viviers("42", [servi], [servi])
    assert any("[viviers]" in ligne for ligne in journal)


def test_E3_l_alarme_part_quand_le_vivier_semantique_fait_tout(journal):
    """Si les viviers structurés n'apportent rien, la conception du lot 2 est à revoir."""
    ltm = _Ltm()
    ltm._viviers_fenetre = []
    ltm._alarme_vivier_b = False
    ltm._alarme_vivier_a = False
    a_seul = MemorySearchResult(content="x", metadata={"doc_id": "d", "vivier": "A"}, score=0.5)
    propose_b = MemorySearchResult(content="y", metadata={"doc_id": "e", "vivier": "B"}, score=0.0)
    for _ in range(ltm._FENETRE_VIVIERS):
        # B propose, mais seul A est servi
        ltm._compter_viviers("42", [a_seul, propose_b], [a_seul])
    assert ltm._alarme_vivier_a is True
    assert any("[ALARME]" in ligne and "vivier" in ligne for ligne in journal)
