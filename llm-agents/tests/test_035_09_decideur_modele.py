"""Ticket 035 — décideur modèle LightGBM (R11, R12, R13, R14, R15).

Voir `specs/scoring_composite_experiences.md`. Le modèle est un décideur au même contrat que
la passerelle : on vérifie qu'il décide comme les autres, scelle sa version, et rend une
non-décision explicite hors domaine — pas un repli silencieux.
"""

import asyncio
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

lgb = pytest.importorskip("lightgbm")
gpd = pytest.importorskip("geopandas")

from experiences import decision as D
from experiences.decision import ContexteDecision

POLICY = REPO / "scripts/progedo_logit/mode_choice_policy.json"
pytestmark = pytest.mark.skipif(not POLICY.exists(), reason="artefact LightGBM absent")


# ── Doublures légères (le contrat de décision, pas la chaîne complète) ────────
class FakeLoc:
    def __init__(self, lat, lon):
        self.lat, self.lon = lat, lon
        self.public_transport = True


class FakeAct:
    def __init__(self, id, purpose, loc):
        self.id, self.purpose, self.location = id, purpose, loc


class FakeIdentity:
    def __init__(self, traits, activities):
        self.traits_json, self.activities = traits, activities


class FakePerson:
    def __init__(self, pid, identity):
        self.person_id, self.identity = pid, identity


class FakePlan:
    def __init__(self, duration):
        self.duration = duration


class FakeProp:
    def __init__(self, mode, duree, code, source="enregistree"):
        self.mode, self.code, self.source = mode, code, source
        self.plan = FakePlan(duree)


TRAITS = {
    "age": 35,
    "gender": "Homme",
    "household_size": 3,
    "has_driving_license": True,
    "has_pt_subscription": False,
    "number_of_cars": 1,
    "car_availability": "always",
    "personal_bike": "Un vélo",
    "socioprofessional_class": "Employé",
    "main_occupation": "actif_temps_plein",
    "employed": True,
    "studies": False,
}
# Deux points dans l'agglomération toulousaine (dans la couche de zones).
CENTRE = FakeLoc(43.6045, 1.4440)
UPS = FakeLoc(43.5610, 1.4650)


def _person():
    home = FakeAct("a0", "home", CENTRE)
    work = FakeAct("a1", "work", UPS)
    return FakePerson("p1", FakeIdentity(TRAITS, [home, work]))


def _ctx(dest_activity="a1"):
    return ContexteDecision(
        timestamp=1773731722,
        activity_id=dest_activity,
        purpose="work",
        departure_time=1773731722,
        from_location=CENTRE,
        destination=UPS,
        graine_ordre=42,
        graine_tirage=42,
        max_candidats=6,
    )


def _presentees():
    return [
        FakeProp("car", 1200, "__DIRECT_CAR__^^"),
        FakeProp("foot,bus,foot,metro,foot", 2400, "line:1^A^B"),
        FakeProp("foot", 3600, "walk^^"),
    ]


@pytest.fixture(scope="module")
def decideur():
    from experiences.decideur_modele import DecideurModele

    return DecideurModele()


def test_R11_decideur_modele_meme_trace(decideur):
    # La réponse du modèle a la MÊME forme que celle d'un décideur LLM, et produit une
    # trace valide via le même `construire_trace`. (On appelle `choisir` directement :
    # l'éligibilité amont est testée ailleurs et exige la chaîne véhicule complète.)
    person, ctx, props = _person(), _ctx(), _presentees()
    rep = asyncio.run(decideur.choisir(person, ctx, props))
    assert rep.index is not None and 0 <= rep.index < len(props)
    assert abs(sum(rep.poids) - 1.0) < 1e-6
    assert rep.distribution
    trace = D.construire_trace(
        person,
        ctx,
        props,
        [],
        props[rep.index],
        D.METHODE_DECIDEUR,
        rep,
        D.CONTRAINTE_AUCUNE,
    )
    assert D.valider_trace(trace) == []


def test_R11_decider_mappe_non_imputable(decideur, monkeypatch):
    # `decider()` transforme une réponse non_imputable en décision TERMINALE, comptée,
    # sans retenue, jamais réessayée. On court-circuite l'éligibilité (testée ailleurs).
    props = _presentees()
    monkeypatch.setattr(
        D,
        "eligibilite",
        lambda *a, **k: D.ResultatFiltre(
            eligibles=props, ecartees=[], evenements=[], contrainte=D.CONTRAINTE_AUCUNE
        ),
    )
    monkeypatch.setattr(D, "plafonner", lambda elig, n: (list(elig), []))
    monkeypatch.setattr(
        D, "ordre_presentation", lambda retenues, *a, **k: list(retenues)
    )

    class StubNonImputable:
        sans_quota = True
        nom = "stub"

        async def choisir(self, person, ctx, presentees):
            return D.ReponseDecideur(
                index=None,
                fournisseur=self.nom,
                non_imputable=True,
                raison="modele_non_imputable:test",
            )

    decision = asyncio.run(D.decider(_person(), _ctx(), props, StubNonImputable()))
    assert decision.methode == D.METHODE_MODELE_NON_IMPUTABLE
    assert decision.est_decision and decision.retenue is None


def test_R12_sha_modele_scelle():
    from experiences.experience import DecideurSpec, _empreinte_decideur

    emp = _empreinte_decideur(DecideurSpec(type="modele"))
    assert emp["type"] == "modele"
    assert emp["artefact_sha256"] and len(emp["artefact_sha256"]) == 64
    # Un autre artefact → un autre SHA de fichier.
    autre = (
        REPO
        / "docs/traces/2026-08-31_second_modele_19_features/mode_choice_policy_ref_distance.json"
    )
    if autre.exists():
        emp2 = _empreinte_decideur(
            DecideurSpec(type="modele", artefact=str(autre.relative_to(REPO)))
        )
        assert emp2["artefact_sha256"] != emp["artefact_sha256"]


def test_R13_non_decision_hors_domaine(decideur):
    # OD hors de la couche de zones → non-décision TERMINALE, comptée, non réessayée,
    # sans mode retenu (donc exclue des parts).
    person = _person()
    person.identity.activities[0].location = FakeLoc(0.0, 0.0)  # golfe de Guinée
    ctx = ContexteDecision(
        timestamp=1773731722,
        activity_id="a1",
        purpose="work",
        departure_time=1773731722,
        from_location=FakeLoc(0.0, 0.0),
        destination=FakeLoc(0.01, 0.01),
        graine_ordre=42,
        graine_tirage=42,
        max_candidats=6,
    )
    rep = asyncio.run(decideur.choisir(person, ctx, _presentees()))
    assert rep.non_imputable and rep.index is None
    assert "od_hors_couche_zones" in rep.raison


def test_R13_persona_sans_traits(decideur):
    person = FakePerson(
        "p2",
        FakeIdentity({}, [FakeAct("a0", "home", CENTRE), FakeAct("a1", "work", UPS)]),
    )
    rep = asyncio.run(decideur.choisir(person, _ctx(), _presentees()))
    assert rep.non_imputable and "persona_sans_traits" in rep.raison


def test_R14_refus_sans_dependance(tmp_path):
    from experiences.decideur_modele import DecideurModele

    with pytest.raises(FileNotFoundError, match="policy"):
        DecideurModele(artefact=tmp_path / "absent.json")


def test_R15_routage_volet_modele(decideur):
    # Une exécution dont le décideur est de type modèle est rendue en volet 3.
    from experiences import score as S

    synthese = {"empreintes": {"decideur": {"type": "modele", "sha256": "abc"}}}
    assert S.volet_pour(synthese) == "3"
    synthese["empreintes"]["decideur"]["type"] = "passerelle"
    assert S.volet_pour(synthese) == "1"
