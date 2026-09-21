"""Ticket 077, lot H — le vécu ne conclut pas, et le choc a une cadence.

Contrat : `specs/ticket_077/tests.md`, section H. Les cas portent les numéros de règle.

Pourquoi ce fichier existe. Le run `experiments/archive/2026-09-19_07_31` a mesuré une bascule
modale dont la conclusion était écrite dans le stimulus : le `vecu` disait « I no longer trust
this car at all », la réflexion en a tiré « consider alternative transport options », et cette
phrase a été servie aux quarante décisions des quatorze jours suivants. La règle R7/R8 du 079
refusait déjà qu'on s'adresse à l'agent ; elle laissait passer qu'on conclue à sa place.

Tout ici est PUR : aucun simulateur, aucun modèle, aucun appel réseau.
"""

import sys
from pathlib import Path

import pytest
import yaml
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm import chocs as chocs_module
from llm.chocs import RefusDeChoc, RegistreChocs, charger

CONFIG_CHOCS = Path(__file__).resolve().parents[1] / "config" / "chocs"

VECU_VALIDE = "I was stuck for an hour on the ring road, and I arrived in a foul mood."


def _declaration(**surcharges) -> dict:
    base = {
        "choc": "test_choc",
        "libelle": "Choc de test",
        "source": "test",
        "exposition": {"regle": "mode", "modes": ["car"]},
        "jours": [{"jour": 12, "retard_min": 60, "vecu": VECU_VALIDE}],
    }
    base.update(surcharges)
    return base


def _ecrire(tmp_path: Path, declaration: dict) -> Path:
    p = tmp_path / "choc.yaml"
    p.write_text(yaml.safe_dump(declaration, allow_unicode=True), encoding="utf-8")
    return p


def _charger_vecu(tmp_path: Path, vecu: str):
    return charger(_ecrire(tmp_path, _declaration(jours=[{"jour": 12, "retard_min": 60, "vecu": vecu}])))


@pytest.fixture(autouse=True)
def _registre_propre():
    chocs_module.reinitialiser()
    yield
    chocs_module.reinitialiser()


@pytest.fixture
def journal():
    """Collecte les messages loguru du module, niveau et texte."""
    lignes: list[tuple[str, str]] = []
    sink = logger.add(lambda m: lignes.append((m.record["level"].name, m.record["message"])), level="INFO")
    yield lignes
    logger.remove(sink)


# ══════════════════════ H1 — ni verdict, ni intention ═══════════════════════════


@pytest.mark.parametrize(
    "vecu",
    [
        "The engine stalled. I no longer trust this car at all.",
        "The bus never came. This bus line is unreliable.",
        "Encore en panne. Je ne fais plus confiance à cette voiture.",
    ],
)
def test_H1_1_un_verdict_sur_un_mode_est_refuse(tmp_path, vecu):
    """H1.1 — la croyance est ce que la réflexion doit PRODUIRE, pas ce qu'on lui dicte."""
    with pytest.raises(RefusDeChoc) as exc:
        _charger_vecu(tmp_path, vecu)
    assert "verdict" in str(exc.value).lower()


@pytest.mark.parametrize(
    "vecu",
    [
        "Arrived 20 minutes late. I am seriously thinking about not using this car anymore.",
        "Stuck again. From now on I will take the metro.",
        "Encore une heure de bouchon. Je ne prendrai plus la voiture.",
    ],
)
def test_H1_2_une_intention_modale_est_refusee(tmp_path, vecu):
    """H1.2 — message distinct de H1.1 : les deux familles se relâchent séparément."""
    with pytest.raises(RefusDeChoc) as exc:
        _charger_vecu(tmp_path, vecu)
    assert "intention" in str(exc.value).lower()


@pytest.mark.parametrize("fichier", ["c1_bouchon_rocade", "c2_crevaison", "c3_panne_reseau",
                                     "c4_train_supprime", "c5_orage_grele"])
def test_H1_3_les_chocs_existants_se_chargent(fichier):
    """H1.3 — la règle rend vérifiable la pratique des cinq autres fichiers, elle ne la condamne pas."""
    charger(CONFIG_CHOCS / f"{fichier}.yaml")


def test_H1_4_un_doute_est_accepte(tmp_path):
    """H1.4 — la limite basse, volontairement retenue (c1, jour 14)."""
    _charger_vecu(tmp_path, "Still crawling along. I am starting to wonder whether this is worth it.")


def test_H1_5_un_fait_passe_meme_modal_est_accepte(tmp_path):
    """H1.5 — « j'ai fait autrement hier » n'est pas « je ferai autrement demain » (c2, jour 13)."""
    _charger_vecu(
        tmp_path,
        "My bike is still out of action after yesterday. I had to sort out another way of getting around.",
    )


def test_H1_6_la_redaction_du_18_septembre_est_refusee(tmp_path):
    """H1.6 — le test qui aurait dû échouer avant le run de quarante-deux jours."""
    j15 = (
        "The engine made a grinding noise and the car stalled on the expressway. I had to pull "
        "over and wait 30 minutes for roadside assistance before the car would restart. "
        "I arrived very late and stressed. I no longer trust this car at all."
    )
    j16 = (
        "Warning lights flashing on the dashboard again. The grinding noise is back and louder "
        "than yesterday. I drove very slowly and considered pulling over again. Arrived 20 "
        "minutes late. I am seriously thinking about not using this car anymore."
    )
    with pytest.raises(RefusDeChoc, match="(?i)verdict"):
        _charger_vecu(tmp_path, j15)
    with pytest.raises(RefusDeChoc, match="(?i)intention"):
        _charger_vecu(tmp_path, j16)


def test_H1_7_c6_corrige_se_charge_et_ne_conclut_plus():
    """H1.7 — et la vérification tient aussi sur le texte, pas seulement sur le chargement."""
    choc = charger(CONFIG_CHOCS / "c6_voiture_suspecte.yaml")
    for jour in choc.jours.values():
        bas = jour.vecu.lower()
        assert "trust" not in bas
        assert "anymore" not in bas
        for mode in ("bus", "metro", "bike", "bicycle", "walk", "public transport"):
            assert mode not in bas, f"jour {jour.jour} : le vécu nomme un mode de report ({mode})"


# ══════════════════════ H2 — la cadence ═════════════════════════════════════════


def _registre(tmp_path, monkeypatch, jour=12, **surcharges):
    choc = charger(_ecrire(tmp_path, _declaration(**surcharges)))
    monkeypatch.setattr(RegistreChocs, "jour_du_run", staticmethod(lambda ts: jour))
    return RegistreChocs(choc)


def test_H2_1_cadence_jour_ne_touche_qu_une_fois(tmp_path, monkeypatch):
    """H2.1 — une panne réparée ne se reproduit pas à l'identique trois heures plus tard."""
    r = _registre(tmp_path, monkeypatch, cadence="jour")
    assert r.applique("609", "car", 1000) is not None
    assert r.applique("609", "car", 2000) is None
    assert r.applique("610", "car", 3000) is not None, "la cadence est par AGENT, pas par journée globale"


def test_H2_2_cadence_trajet_touche_chaque_arrivee(tmp_path, monkeypatch):
    """H2.2 — comportement historique, celui d'un bouchon qui dure toute la journée."""
    r = _registre(tmp_path, monkeypatch, cadence="trajet")
    assert r.applique("609", "car", 1000) is not None
    assert r.applique("609", "car", 2000) is not None


def test_H2_3_cadence_absente_vaut_trajet_et_se_journalise(tmp_path, monkeypatch, journal):
    """H2.3 — aucun fichier existant ne change de comportement en silence."""
    r = _registre(tmp_path, monkeypatch)
    assert r.applique("609", "car", 1000) is not None
    assert r.applique("609", "car", 2000) is not None
    assert any("cadence" in m for _, m in journal), "la cadence retenue par défaut n'est pas journalisée"


def test_H2_4_cadence_inconnue_est_refusee(tmp_path):
    """H2.4 — comme une règle d'exposition inconnue : on refuse, on n'ignore pas."""
    with pytest.raises(RefusDeChoc, match="(?i)cadence"):
        charger(_ecrire(tmp_path, _declaration(cadence="parfois")))


def test_H2_5_le_compteur_se_rearme_chaque_journee(tmp_path, monkeypatch):
    """H2.5 — touché une fois par jour, pas une fois pour tout le run."""
    choc = charger(
        _ecrire(
            tmp_path,
            _declaration(
                cadence="jour",
                jours=[
                    {"jour": 12, "retard_min": 60, "vecu": VECU_VALIDE},
                    {"jour": 13, "retard_min": 30, "vecu": VECU_VALIDE},
                ],
            ),
        )
    )
    r = RegistreChocs(choc)
    jours = {"n": 12}
    monkeypatch.setattr(RegistreChocs, "jour_du_run", staticmethod(lambda ts: jours["n"]))
    assert r.applique("609", "car", 1000) is not None
    assert r.applique("609", "car", 2000) is None
    jours["n"] = 13
    assert r.applique("609", "car", 3000) is not None


def test_H2_6_c6_declare_la_cadence_jour():
    """H2.6 — le fichier du run dit lui-même ce qu'il fait."""
    assert charger(CONFIG_CHOCS / "c6_voiture_suspecte.yaml").cadence == "jour"


# ══════════════════════ H3 — un jour de choc sans exposé ════════════════════════


def test_H3_1_jour_de_choc_sans_expose_leve_une_alarme(tmp_path, monkeypatch, journal):
    """H3.1 — le second choc de c6 n'a jamais eu lieu, et le rapport a continué d'en parler."""
    r = _registre(tmp_path, monkeypatch)
    r.applique("609", "walking", 1000)  # épargné : mauvais mode
    r.journaliser_compteurs()
    alarmes = [m for n, m in journal if n == "ERROR" and "[ALARME]" in m]
    assert alarmes, "une journée de choc close sans un seul exposé n'a levé aucune alarme"
    assert "12" in alarmes[0]


def test_H3_2_journee_nominale_sans_expose_reste_en_info(tmp_path, monkeypatch, journal):
    """H3.2 — le cas normal : la plupart des journées d'un run ne sont pas des journées de choc."""
    r = _registre(tmp_path, monkeypatch, jour=10)
    r.applique("609", "car", 1000)
    r.journaliser_compteurs()
    assert not [m for n, m in journal if n == "ERROR"]


def test_H3_3_jour_de_choc_avec_expose_ne_leve_rien(tmp_path, monkeypatch, journal):
    """H3.3 — l'alarme ne se déclenche que sur l'absence, jamais sur la présence."""
    r = _registre(tmp_path, monkeypatch)
    assert r.applique("609", "car", 1000) is not None
    r.journaliser_compteurs()
    assert not [m for n, m in journal if n == "ERROR"]
