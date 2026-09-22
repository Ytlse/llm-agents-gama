"""Ticket 100, lot 3 — l'agent juge ce qu'il vient de vivre ou de lire (D4).

Contrat de référence : `specs/ticket_100/tests.md`, règles R24 à R31.

Le modèle est DOUBLÉ : aucun appel réseau. Ce qui se vérifie ici est la grille, le refus, la
règle du maximum et le nombre d'appels — pas la qualité d'un jugement, qui n'est pas testable.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm.evenements import jugement as jg
from llm.evenements.jugement import JugementRefuse, juger, resoudre_modes, resoudre_valence
from llm.gravite import NIVEAUX

RACINE = Path(__file__).resolve().parents[1]


class _Rendu:
    def __init__(self, severity=None, valence=None, modes=None):
        self.severity = severity
        self.valence = valence
        self.modes = modes


class _Reponse:
    def __init__(self, agents):
        self.agents = agents


class _Client:
    """Client doublé. Compte ses appels : c'est ce que R29 vérifie."""

    def __init__(self, *rendus):
        self._rendus = list(rendus)
        self.appels = 0
        self.charges = []

    async def execute(self, payload):
        self.appels += 1
        self.charges.append(payload)
        rendu = self._rendus.pop(0) if self._rendus else None
        return _Reponse([rendu]) if rendu is not None else None


async def _juger(client, gravite=0.0):
    return await juger(
        client, "609", "Jacques Aubert, 49, works full time.", "The engine stalled twice.",
        gravite_deterministe=gravite, evenement_id="c6", jour=15,
    )


# ── R24. Le refus est franc ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("severity", ["catastrophic", "", None, "7", "très grave"])
@pytest.mark.asyncio
async def test_R24_un_echelon_hors_grille_refuse_sans_aucun_repli(severity):
    """Aucune valeur de remplacement : un repli fabriquerait une exposition non jugée."""
    with pytest.raises(JugementRefuse):
        await _juger(_Client(_Rendu(severity=severity, valence="negative")))


@pytest.mark.asyncio
async def test_R24bis_une_reponse_vide_est_refusee():
    with pytest.raises(JugementRefuse):
        await _juger(_Client())


# ── R25. Les deux vocabulaires ───────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_R25_langlais_et_le_francais_donnent_la_meme_gravite():
    anglais = await _juger(_Client(_Rendu("serious", "negative", [])))
    francais = await _juger(_Client(_Rendu("grave", "negative", [])))
    assert anglais.importance_estimee == francais.importance_estimee == NIVEAUX["grave"]
    assert anglais.intensite == francais.intensite == "grave"


# ── R26 bis, R27. La gravité est celle de l'agent, SEULE (D7, 2026-09-22) ───────────────
@pytest.mark.asyncio
async def test_R26bis_la_gravite_retenue_EST_lestimation_quel_que_soit_le_fait():
    """R26 est RETIRÉE. Le plancher `max(estimée, mesurée)` n'existe plus.

    Un dépannage de trente minutes jugé « anodin » vaut désormais 0,10, et non 0,70. Ce n'est
    pas un relâchement de test : c'est la décision D7, et elle est chiffrée — le souvenir vivra
    2,8 jours au lieu de 15,4.
    """
    rendu = await _juger(_Client(_Rendu("negligible", "neutral", [])), gravite=0.70)
    assert rendu.importance_estimee == pytest.approx(0.10)
    assert rendu.importance_retenue == pytest.approx(0.10)
    assert rendu.ecart_au_fait == pytest.approx(-0.60)


@pytest.mark.asyncio
async def test_un_jugement_fort_vaut_toujours_lui_meme():
    """Valable avec ou sans plancher — mais pour une autre raison qu'avant."""
    rendu = await _juger(_Client(_Rendu("memorable", "negative", [])), gravite=0.70)
    assert rendu.importance_retenue == pytest.approx(1.00)
    assert rendu.ecart_au_fait == pytest.approx(+0.30)


@pytest.mark.asyncio
async def test_une_sous_estimation_de_plus_dun_echelon_leve_une_ALARME():
    """La garde qui remplace le plancher DIT, elle ne corrige pas."""
    from loguru import logger as _logger

    messages: list[str] = []
    jeton = _logger.add(lambda m: messages.append(str(m)), level="ERROR")
    try:
        rendu = await _juger(_Client(_Rendu("negligible", "neutral", [])), gravite=0.70)
    finally:
        _logger.remove(jeton)
    assert rendu.importance_retenue == pytest.approx(0.10), "la valeur n'est pas corrigée"
    assert any("[ALARME]" in m and "SOUS-ESTIME" in m for m in messages)


@pytest.mark.asyncio
async def test_un_ecart_dun_seul_echelon_nalarme_pas():
    """Alarmer sur une hésitation entre deux niveaux voisins noierait le journal."""
    from loguru import logger as _logger

    messages: list[str] = []
    jeton = _logger.add(lambda m: messages.append(str(m)), level="ERROR")
    try:
        await _juger(_Client(_Rendu("inconvenient", "neutral", [])), gravite=0.70)
    finally:
        _logger.remove(jeton)
    assert not [m for m in messages if "SOUS-ESTIME" in m]


@pytest.mark.asyncio
async def test_sans_fait_mesure_aucune_alarme_decart():
    """Un article ne mesure rien : l'écart n'a pas de sens, et n'a pas à crier."""
    from loguru import logger as _logger

    messages: list[str] = []
    jeton = _logger.add(lambda m: messages.append(str(m)), level="ERROR")
    try:
        rendu = await _juger(_Client(_Rendu("negligible", "neutral", [])), gravite=0.0)
    finally:
        _logger.remove(jeton)
    assert rendu.importance_retenue == pytest.approx(0.10)
    assert not [m for m in messages if "SOUS-ESTIME" in m]


@pytest.mark.parametrize("niveau,attendu", sorted(NIVEAUX.items()))
@pytest.mark.parametrize("mesure", [0.0, 0.70])
@pytest.mark.asyncio
async def test_R27_le_jugement_decide_seul_avec_ou_sans_fait_mesure(niveau, attendu, mesure):
    """Depuis D7, la présence d'un fait mesuré ne change plus la gravité retenue."""
    rendu = await _juger(_Client(_Rendu(niveau, "neutral", [])), gravite=mesure)
    assert rendu.importance_retenue == pytest.approx(attendu)


# ── R29, R31. Un appel par exposition, et ce qui en sort ─────────────────────────────────
@pytest.mark.asyncio
async def test_R29_un_appel_par_exposition():
    client = _Client(_Rendu("serious", "negative", ["car"]))
    await _juger(client)
    assert client.appels == 1


@pytest.mark.asyncio
async def test_R31_la_valence_et_les_modes_traversent():
    rendu = await _juger(_Client(_Rendu("serious", "positive", ["car", "cycling"])))
    assert rendu.valence == "positive"
    assert rendu.modes == ("car", "cycling")


def test_une_valence_hors_grille_retombe_sur_neutre_sans_rien_fabriquer():
    """Contrairement à l'échelon : la gravité tient sans la valence, le défaut n'ajoute rien."""
    assert resoudre_valence("enthousiaste") == "neutre"
    assert resoudre_valence(None) == "neutre"
    assert resoudre_valence("positive") == "positive"


def test_un_mode_hors_hierarchie_est_ecarte_et_non_laisse_passer():
    """La leçon du lot A du 077 : deux vocabulaires de modes qui coexistent en silence."""
    assert resoudre_modes(["car", "teleportation", "cycling"]) == ("car", "cycling")
    assert resoudre_modes(["car", "car"]) == ("car",)
    assert resoudre_modes(None) == ()


# ── Les ancres ont UNE seule source ──────────────────────────────────────────────────────
def test_les_ancres_viennent_de_gravite_et_non_du_gabarit():
    """Le gabarit de `stm_reflection` les recopie ; celui-ci les reçoit.

    Deux sources pour une même échelle divergeraient le jour où l'une bouge, et personne ne le
    verrait — c'est exactement le motif du lot A du ticket 077.
    """
    from llm.gravite import ANCRES, ancres_anglaises

    charge = jg.charge_utile("609", "persona", "texte")
    assert charge["parameters"]["ancres"] == ancres_anglaises()
    # Le TEXTE des ancres est celui de `gravite.py`, quel que soit le libellé qui les porte.
    assert sorted(charge["parameters"]["ancres"].values()) == sorted(ANCRES.values())
    gabarit = (
        RACINE.parents[1] / "packages" / "mobility_llm" / "src" / "mobility_llm"
        / "categories" / "evenement_jugement" / "template.md.j2"
    ).read_text("utf-8")
    assert "parameters.ancres" in gabarit
    for ancre in ANCRES.values():
        assert ancre not in gabarit, "une ancre recopiée dans le gabarit ferait deux sources"


def test_les_ancres_portent_le_libelle_de_l_enumeration_du_schema():
    """Mesuré le 2026-09-22 : le prompt proposait `anodin`, le schéma n'acceptait que l'anglais.

    Le modèle recevait deux vocabulaires pour une même échelle et devait en deviner un. C'est un
    défaut qu'aucun test ne voyait parce que les deux moitiés étaient justes chacune de son côté.
    """
    import json

    schema = json.loads((
        RACINE.parents[1] / "packages" / "mobility_llm" / "src" / "mobility_llm"
        / "categories" / "evenement_jugement" / "output_schema.json"
    ).read_text("utf-8"))
    enum = schema["properties"]["agents"]["items"]["properties"]["severity"]["enum"]
    charge = jg.charge_utile("609", "persona", "texte")
    assert sorted(charge["parameters"]["ancres"]) == sorted(enum)


def test_le_budget_de_sortie_laisse_la_place_au_raisonnement():
    """256 jetons ne suffisaient pas : la réflexion des modèles se paie sur ce budget.

    Mesuré sur Groq le 2026-09-22 — 240 à 330 jetons de raisonnement AVANT le premier caractère
    de JSON, et un fournisseur qui rend « max completion tokens reached before generating a valid
    document ». Le seuil n'est pas un réglage de confort : sous lui, la réponse est vide ou
    dégradée, et une réponse dégradée prend la première valeur de chaque énumération.
    """
    charge = jg.charge_utile("609", "persona", "texte")
    assert charge["parameters"]["max_tokens"] >= 512


# ── R28. L'ablation déclarée ─────────────────────────────────────────────────────────────
def test_R28_jugement_aucun_nappelle_pas_le_modele():
    """Vérifié par lecture de source : monter un contrôleur demanderait GAMA et un modèle."""
    ctrl = (RACINE / "urban_mobility_agents" / "simulation_controller.py").read_text("utf-8")
    assert 'registre.evenement.jugement == "a_l_injection"' in ctrl
    assert '_registre_chocs.evenement.jugement == "a_l_injection"' in ctrl


def test_une_seule_ligne_de_trace_par_exposition():
    """Sinon tout compte par exposition serait faux.

    Quand un jugement est attendu, la trace part AVEC lui ; quand il échoue, elle s'écrit
    quand même, sans ses colonnes de jugement. Les quatre chemins de sortie du jugement
    écrivent donc exactement une ligne.
    """
    ctrl = (RACINE / "urban_mobility_agents" / "simulation_controller.py").read_text("utf-8")
    debut = ctrl.index("async def _juger_evenement_subi")
    fin = ctrl.index("async def _injecter_evenements_du_reveil")
    methode = ctrl[debut:fin]
    assert methode.count("registre.tracer(") == 4, (
        "les quatre sorties — refus, erreur, jugement tardif, succès — tracent chacune"
    )
    assert "not _jugement_attendu" in ctrl, (
        "la trace immédiate doit être sautée quand un jugement est attendu"
    )


def test_un_canal_lu_sans_jugement_narme_pas_un_run():
    """Un article à gravité 0,00 vit 2,8 jours : son silence passerait pour une absence d'effet."""
    from llm.gravite import force_initiale

    assert force_initiale(0.0) == pytest.approx(2.8)
