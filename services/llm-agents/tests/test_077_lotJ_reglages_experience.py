"""Ticket 077, lot J — la configuration du dépôt ne redéfinit pas les règles de mémoire.

Contrat : `specs/ticket_077/tests.md`, section J.

Le § 9 du ticket dit que rien ne change dans les règles de mémoire. Le 18 septembre,
`config.yaml` a pourtant abaissé le seuil de choc de 0,70 à 0,50 — sans effet sur le choc visé,
qui atteignait déjà 0,70, et avec pour seul effet mesurable d'élargir le vivier C.
"""

import sys
from pathlib import Path

import pytest
import yaml
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm.chocs import charger
from llm.gravite import gravite_deterministe
from settings import settings

RACINE = Path(__file__).resolve().parents[1]
CONFIG = RACINE / "config" / "config.yaml"
CONFIG_CHOCS = RACINE / "config" / "chocs"


@pytest.fixture
def journal():
    lignes: list[tuple[str, str]] = []
    sink = logger.add(lambda m: lignes.append((m.record["level"].name, m.record["message"])), level="INFO")
    yield lignes
    logger.remove(sink)


# ══════════════════════ J1 à J4 — les règles de mémoire ═════════════════════════


def test_J1_config_yaml_ne_redefinit_aucune_regle_de_memoire():
    """J1 — une règle de mémoire se varie par l'environnement, pas par le défaut du dépôt.

    Par l'environnement, elle appartient au run et se retrouve dans son identité. Dans
    `config.yaml`, elle devient la norme du dépôt sans que personne ne l'ait décidé — et elle
    fait rougir les tests qui énoncent la règle, ce qui les rend illisibles.
    """
    agent = (yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}).get("agent") or {}
    fautives = sorted(k for k in agent if k.startswith("memoire__"))
    assert not fautives, (
        "config.yaml redéfinit des règles de mémoire : "
        + ", ".join(fautives)
        + " — à passer par l'environnement (AGENT__MEMOIRE__…), où le run les enregistre."
    )


def test_J2_le_seuil_de_choc_est_celui_du_071():
    """J2 — 0,70, et Θ lui est égal. Couvert par le lot 0 du 071 ; ici on le dit une fois de plus."""
    assert settings.agent.memoire__importance_choc == pytest.approx(0.70)
    assert settings.agent.memoire__theta_gravite_cumulee == pytest.approx(0.70)


def test_J3_le_premier_choc_de_c6_franchit_le_seuil_sans_qu_on_l_abaisse():
    """J3 — vérifié sur la valeur CALCULÉE, pas sur une intention écrite en commentaire."""
    choc = charger(CONFIG_CHOCS / "c6_voiture_suspecte.yaml")
    premier = choc.jours[choc.premier_jour]
    gravite, _ = gravite_deterministe(
        premier.retard_s,
        incident_reseau=premier.incident_reseau,
        correspondance_ratee=premier.correspondance_ratee,
    )
    assert gravite >= settings.agent.memoire__importance_choc, (
        f"gravité {gravite:.3f} sous le seuil {settings.agent.memoire__importance_choc} — "
        f"le choc n'entrerait pas dans la mémoire noyau"
    )


def test_J4_le_second_choc_de_c6_reste_sous_le_seuil_et_c_est_voulu():
    """J4 — comportement documenté d'origine : rappelé par le vivier PAR OBJET, pas hors contexte.

    Écrit pour que personne ne le « corrige » à nouveau en abaissant le seuil.
    """
    choc = charger(CONFIG_CHOCS / "c6_voiture_suspecte.yaml")
    second = choc.jours[choc.dernier_jour]
    gravite, _ = gravite_deterministe(
        second.retard_s,
        incident_reseau=second.incident_reseau,
        correspondance_ratee=second.correspondance_ratee,
    )
    assert gravite < settings.agent.memoire__importance_choc


# ══════════════════════ J5 — les jalons d'enquête ═══════════════════════════════


def _module(monkeypatch, **env):
    from urban_mobility_agents import enquetes

    for cle in ("EXPERIMENT_SURVEY_DAYS",):
        monkeypatch.delenv(cle, raising=False)
    for cle, val in env.items():
        monkeypatch.setenv(cle, val)
    enquetes.reinitialiser()
    return enquetes


def test_J5_1_le_defaut_suit_le_protocole_et_se_journalise(monkeypatch, journal):
    """J5.1 — J12 fin de baseline · J17 lendemain du second choc · J29 sortie de fenêtre · J40 tardif."""
    enquetes = _module(monkeypatch)
    assert enquetes.jours_jalons() == (12, 17, 29, 40)
    assert any("jalon" in m.lower() for _, m in journal)


def test_J5_2_les_jalons_se_declarent(monkeypatch):
    """J5.2 — un protocole qui bouge ne doit plus demander de modifier du code."""
    enquetes = _module(monkeypatch, EXPERIMENT_SURVEY_DAYS="3,11")
    assert enquetes.jours_jalons() == (3, 11)


@pytest.mark.parametrize("brut", ["douze", "0", "-4", "3,douze", ",,"])
def test_J5_3_une_declaration_illisible_replie_et_alarme(monkeypatch, journal, brut):
    """J5.3 — un sondage éteint en silence ne se distingue pas d'un sondage sans résultat."""
    enquetes = _module(monkeypatch, EXPERIMENT_SURVEY_DAYS=brut)
    assert enquetes.jours_jalons() == (12, 17, 29, 40)
    assert [m for n, m in journal if n == "ERROR" and "[ALARME]" in m]


def test_J5_4_un_jalon_le_week_end_est_signale(monkeypatch, journal):
    """J5.4 — la simulation saute les week-ends : ce jalon ne se déclencherait jamais."""
    enquetes = _module(monkeypatch, EXPERIMENT_SURVEY_DAYS="42")
    enquetes.verifier_jalons_atteignables(jour_courant=1, date_du_jour_courant="2026-03-16")
    signales = [m for _, m in journal if "week-end" in m or "inatteignable" in m]
    assert signales, "un jalon tombant un dimanche n'a été signalé nulle part"
    assert "42" in signales[0]


def test_J5_5_un_jalon_en_jour_ouvre_ne_signale_rien(monkeypatch, journal):
    """J5.5 — le signalement ne porte que sur l'inatteignable."""
    enquetes = _module(monkeypatch, EXPERIMENT_SURVEY_DAYS="12,17,29,40")
    enquetes.verifier_jalons_atteignables(jour_courant=1, date_du_jour_courant="2026-03-16")
    assert not [m for _, m in journal if "week-end" in m or "inatteignable" in m]
