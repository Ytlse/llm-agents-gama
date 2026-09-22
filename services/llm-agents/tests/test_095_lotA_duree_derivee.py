"""Ticket 095, lot A — la durée d'un souvenir de choc, dérivée de sa gravité.

Contrat : `specs/ticket_095/tests.md`, sections A, B et C.

Pourquoi ce fichier existe. La campagne appariée du ticket 077 a montré un effet de choc qui
s'éteint **le jour exact** où le souvenir sort du bloc de prompt — 13 avril à fenêtre 14, 6 avril
à fenêtre 7. La durée d'un effet était donc un entier posé dans `settings.py`. Que 14,6 — la
durée de vie calculée du souvenir — tombe près de 14 est la coïncidence qui a masqué le défaut :
les deux explications prédisaient la même date, et le bras à fenêtre 7 les a séparées.

Les nombres testés ici sont ceux du contrat, posés AVANT le code :
`force = min(2,8 × (1 + 6 × gravité), 30)` · `durée = force × ln(1/0,35)` · `ln(1/0,35) = 1,049822`.
"""

import math
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm import noyau as noyau_module
from llm.memory import MemoryEntry, MemoryType
from llm.noyau import MODE_DERIVEE, MODE_FIXE, bloc_changements, duree_service_jours
from settings import settings
from sim_clock import wall_clock

T0 = 1773637200
LN = math.log(1 / 0.35)


def _choc(texte="panne sur voie rapide", gravite=0.70, jours=1.0, force=None):
    """Un souvenir de choc. `force=None` = jamais qualifié : elle se recalcule depuis la gravité."""
    return MemoryEntry(
        content=texte,
        timestamp=wall_clock(T0) - timedelta(days=jours),
        memory_type=MemoryType.REFLECTION,
        person_id="899549",
        importance=gravite,
        force=force,
    )


@pytest.fixture(autouse=True)
def _propre(monkeypatch):
    noyau_module.reinitialiser()
    monkeypatch.setattr(
        settings.agent, "memoire__mode_fenetre_changements", MODE_DERIVEE, raising=False
    )
    yield
    noyau_module.reinitialiser()


@pytest.fixture
def journal():
    lignes: list[tuple[str, str]] = []
    sink = logger.add(
        lambda m: lignes.append((m.record["level"].name, m.record["message"])), level="INFO"
    )
    yield lignes
    logger.remove(sink)


@pytest.fixture
def regler(monkeypatch):
    def _poser(**kw):
        for nom, valeur in kw.items():
            monkeypatch.setattr(settings.agent, f"memoire__{nom}", valeur, raising=False)
    return _poser


# ══════════════════════ A — la durée dérivée ════════════════════════════════════


def test_A1_la_force_absente_se_recalcule_depuis_la_gravite():
    """A1 — 15,285 j pour une gravité de 0,70, c'est la valeur du ticket (C6 mesuré)."""
    d = duree_service_jours(_choc(gravite=0.70, force=None))
    assert d.force == pytest.approx(14.56)
    assert d.jours == pytest.approx(15.285, abs=1e-3)
    assert d.borne == ""


def test_A2_une_force_portee_est_utilisee_telle_quelle():
    """A2 — la force a pu croître au rappel ; la recalculer effacerait ce renforcement."""
    d = duree_service_jours(_choc(gravite=0.70, force=20.0))
    assert d.force == 20.0
    assert d.jours == pytest.approx(20.0 * LN, abs=1e-6)


def test_A3_trois_gravites_croissantes_donnent_trois_durees_croissantes():
    """A3 — c'est toute la thèse du lot : la durée suit la gravité."""
    durees = [duree_service_jours(_choc(gravite=g)).jours for g in (0.30, 0.70, 0.90)]
    assert durees == sorted(durees)
    assert durees[0] == pytest.approx(8.231, abs=1e-3)
    assert durees[1] == pytest.approx(15.285, abs=1e-3)
    assert durees[2] == pytest.approx(18.813, abs=1e-3)


def test_A4_le_plancher_ne_mord_pas_a_gravite_faible():
    """A4 — 3,12 j à gravité 0,01 : au-dessus du plancher, donc servi tel quel."""
    d = duree_service_jours(_choc(gravite=0.01))
    assert d.force == pytest.approx(2.968, abs=1e-3)
    assert d.jours == pytest.approx(3.116, abs=1e-3)
    assert d.borne == ""


def test_A5_le_plancher_ne_mord_pas_meme_a_gravite_nulle():
    """A5 — le plancher est une borne de sûreté, PAS une durée minimale observée.

    À S0 = 2,8 j et seuil 0,35, la durée d'un souvenir de gravité nulle vaut déjà 2,94 j. Citer
    « 2 jours » comme durée minimale mesurée serait faux.
    """
    d = duree_service_jours(_choc(gravite=0.0))
    assert d.jours == pytest.approx(2.8 * LN, abs=1e-6)
    assert d.borne == ""


def test_A6_le_plafond_de_duree_ne_mord_plus_jamais(regler):
    """A6 — décision de l'auteur du 2026-09-22 : le plafond passe à 50 j et devient un témoin.

    Ce qui borne réellement la durée est `memoire__force_max_jours`, parce que
    `durée = force × 1,0498`. À force saturée à 30, la durée vaut 31,49 j — et aucun nombre de
    rappels ne va au-delà. Le plafond de durée ne pouvait mordre que dans la bande
    `force ∈ ]28,58 ; 30]`, où il rabotait au plus 1,49 j.

    ⚠ L'ancienne version de ce test affirmait que sans plafond « un souvenir souvent rappelé
    repousserait indéfiniment sa propre échéance ». C'était faux : `force_apres_rappel` sature.
    """
    d = duree_service_jours(_choc(gravite=1.0, force=30.0))
    assert d.brute == pytest.approx(31.495, abs=1e-3)
    assert d.jours == pytest.approx(31.495, abs=1e-3), "le plafond de 50 j ne doit plus mordre"
    assert d.borne == ""
    # La gravité seule n'y arrive jamais : 19,6 j de force au maximum.
    assert duree_service_jours(_choc(gravite=1.0)).jours == pytest.approx(20.577, abs=1e-3)

    # Le MÉCANISME reste exercé : abaissé sous la durée atteignable, le plafond mord et se nomme.
    regler(plafond_changement_jours=30.0)
    rabote = duree_service_jours(_choc(gravite=1.0, force=30.0))
    assert rabote.jours == 30.0
    assert rabote.borne == "plafond"


def test_A7_un_souvenir_sort_le_jour_que_sa_duree_predit():
    """A7 — gravité 0,70 : servi au jour 15, plus au jour 16."""
    assert bloc_changements([_choc(gravite=0.70, jours=15.0)], wall_clock(T0))
    assert bloc_changements([_choc(gravite=0.70, jours=16.0)], wall_clock(T0)) == []


def test_A8_la_date_d_extinction_se_deplace_avec_la_gravite():
    """A8 — le cœur de E3, exercé en unitaire avant le run."""
    quand = wall_clock(T0)
    assert bloc_changements([_choc(gravite=0.90, jours=16.0)], quand)
    assert bloc_changements([_choc(gravite=0.70, jours=16.0)], quand) == []


def test_A9_l_age_se_compte_depuis_l_evenement_pas_depuis_le_rappel():
    """A9 — un choc relu hier n'est pas un choc d'hier.

    Le bloc annonce l'ancienneté d'un CHANGEMENT. Le renforcement au rappel continue de jouer,
    mais par la `force`, donc sur la durée — pas en rajeunissant l'événement.
    """
    vieux = _choc(gravite=0.70, jours=16.0)
    vieux.dernier_rappel = wall_clock(T0) - timedelta(hours=1)
    assert bloc_changements([vieux], wall_clock(T0)) == []


def test_A10_sous_le_seuil_de_choc_rien_n_entre():
    """A10 — la durée ne rachète pas une gravité qui n'atteint pas le seuil de choc."""
    assert bloc_changements([_choc(gravite=0.10, jours=0.5)], wall_clock(T0)) == []


# ══════════════════════ B — mode, réglages et bornes ════════════════════════════


def test_B1_en_mode_derive_la_fenetre_fixe_n_est_pas_lue(regler):
    """B1 — sinon deux réglages gouverneraient la même chose, et on ne saurait pas lequel agit."""
    souvenir = _choc(gravite=0.70, jours=10.0)
    regler(fenetre_changements_jours=1)
    assert bloc_changements([souvenir], wall_clock(T0))
    regler(fenetre_changements_jours=40)
    assert bloc_changements([souvenir], wall_clock(T0))


def test_B2_le_mode_fixe_ignore_la_gravite(regler):
    """B2 — le bras de contrôle méthodologique doit reproduire la campagne du 19 septembre."""
    regler(mode_fenetre_changements=MODE_FIXE, fenetre_changements_jours=14)
    quand = wall_clock(T0)
    assert bloc_changements([_choc(gravite=0.90, jours=15.0)], quand) == []
    assert bloc_changements([_choc(gravite=0.70, jours=13.0)], quand)


def test_B3_le_mode_fixe_a_zero_reste_l_ablation(regler):
    """B3 — y compris le souvenir de l'instant même."""
    regler(mode_fenetre_changements=MODE_FIXE, fenetre_changements_jours=0)
    assert bloc_changements([_choc(jours=0.0)], wall_clock(T0)) == []


def test_B4_un_seuil_hors_domaine_est_une_alarme_et_un_repli(regler, journal):
    """B4 — à seuil 1, la durée serait nulle : une ablation que personne n'a déclarée."""
    regler(seuil_service_changement=1.0)
    d = duree_service_jours(_choc(gravite=0.70))
    assert d.jours == pytest.approx(15.285, abs=1e-3)
    assert [m for n, m in journal if n == "ERROR" and "[ALARME]" in m and "seuil" in m]


def test_B5_un_mode_inconnu_ne_s_interprete_pas(regler, journal):
    """B5 — et la valeur fautive est citée : on doit pouvoir la corriger sans la deviner."""
    regler(mode_fenetre_changements="glissante")
    assert bloc_changements([_choc(gravite=0.70, jours=10.0)], wall_clock(T0))
    alarmes = [m for n, m in journal if n == "ERROR" and "[ALARME]" in m]
    assert alarmes and "glissante" in alarmes[0]


def test_B6_plancher_superieur_au_plafond_est_rattrape_et_dit(regler, journal):
    """B6 — sans l'échange, AUCUN souvenir de choc ne serait jamais servi.

    Bornes remises dans l'ordre : (2 ; 30), donc la durée de 15,29 j passe sans être bornée.
    """
    regler(plancher_changement_jours=30.0, plafond_changement_jours=2.0)
    d = duree_service_jours(_choc(gravite=0.70))
    assert d.jours == pytest.approx(15.285, abs=1e-3)
    assert d.borne == ""
    assert [m for n, m in journal if n == "ERROR" and "plancher" in m and "plafond" in m]


def test_B7_les_reglages_sont_relus_a_chaque_appel(regler):
    """B7 — figés à l'import, une surcharge d'environnement — donc un bras — ne servirait à rien."""
    souvenir = _choc(gravite=0.70, jours=10.0)
    regler(seuil_service_changement=0.9)  # durée = 14,56 × 0,105 = 1,53 j → plancher 2 j
    assert bloc_changements([souvenir], wall_clock(T0)) == []
    regler(seuil_service_changement=0.35)
    assert bloc_changements([souvenir], wall_clock(T0))


def test_B8_le_plafond_a_une_trace_propre(journal, regler):
    """B8 — « le plafond a mordu » doit se lire dans le journal, pas se déduire d'un calcul.

    Le plafond de production (50 j) ne mord plus : on l'abaisse ici pour exercer la trace. Sans
    cela, le jour où la loi ou le plafond de force bougerait, la ligne ne serait plus testée.
    """
    regler(plafond_changement_jours=30.0)
    entrees = [_choc(gravite=1.0, jours=31.0, force=30.0)]
    bloc_changements(entrees, wall_clock(T0), person_id="899549")
    lignes = [m for n, m in journal if "sorti du bloc" in m]
    assert lignes and "plafond" in lignes[0]


# ══════════════════════ C — la ligne de sortie ══════════════════════════════════


def test_C1_la_ligne_porte_la_cause_et_pas_seulement_la_date(journal):
    """C1 — une durée servie sans sa cause ne se vérifie pas après coup."""
    bloc_changements([_choc(gravite=0.70, jours=16.0)], wall_clock(T0), person_id="899549")
    ligne = next(m for n, m in journal if "sorti du bloc" in m)
    assert "0.70" in ligne          # la gravité
    assert "14.56" in ligne         # la force
    assert "15.29" in ligne         # la durée servie, arrondie au centième
    assert "plus aucun souvenir de choc" in ligne


def test_C2_front_montant_une_seule_ligne(journal):
    """C2 — répétée à chaque décision, la ligne noierait ce qu'elle dit."""
    entrees = [_choc(gravite=0.70, jours=16.0)]
    bloc_changements(entrees, wall_clock(T0), person_id="899549")
    bloc_changements(entrees, wall_clock(T0) + timedelta(days=1), person_id="899549")
    assert len([m for _, m in journal if "sorti du bloc" in m]) == 1


def test_C3_deux_gravites_sortent_a_deux_dates_et_font_deux_lignes(journal):
    """C3 — et chaque ligne nomme SA gravité : c'est ce qui rend E3 lisible dans le journal."""
    # Deux ÉVÉNEMENTS distincts, donc deux horodatages distincts : le front montant est
    # mémorisé par (agent, instant du souvenir), et deux souvenirs simultanés n'en font qu'un.
    leger = _choc("crevaison", gravite=0.70, jours=16.0)
    lourd = _choc("panne réseau", gravite=0.90, jours=16.2)
    bloc_changements([leger, lourd], wall_clock(T0), person_id="899549")
    bloc_changements([leger, lourd], wall_clock(T0) + timedelta(days=3), person_id="899549")
    lignes = [m for _, m in journal if "sorti du bloc" in m]
    assert len(lignes) == 2
    assert any("0.70" in m for m in lignes) and any("0.90" in m for m in lignes)


def test_C4_en_mode_fixe_la_ligne_nomme_la_fenetre(regler, journal):
    """C4 — elle ne prétend pas à une durée dérivée qu'elle n'a pas calculée."""
    regler(mode_fenetre_changements=MODE_FIXE, fenetre_changements_jours=14)
    bloc_changements([_choc(jours=15.0)], wall_clock(T0), person_id="899549")
    ligne = next(m for n, m in journal if "sorti du bloc" in m)
    assert "fenêtre fixe de 14 j" in ligne
    assert "gravité" not in ligne
