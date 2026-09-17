"""Ticket 084 — restriction de routage par liste d'instances admises.

Contrat : `specs/ticket_084/tests.md`. Les identifiants de cas (A1, C1, D2…) y renvoient.

La question à laquelle ces tests répondent : **la restriction est-elle honorée à la SÉLECTION,
avant qu'un appel ne soit payé, et survit-elle à tout le trajet — validation de l'API, clé de
lot, passage par Celery, bascule après incident ?** Un mécanisme qui ne tiendrait qu'au premier
appel serait pire qu'aucun : il donnerait une garantie fausse.
"""

import pytest

from llm_gateway.balancer.router import LoadBalancer, RestrictionInstances
from llm_gateway.config.settings import ProviderConfig
from llm_gateway.core.batching import compute_batch_key
from llm_gateway.core.models import LLMRequest


def _provider(rpm: int = 15, weight: float = 1.0, batch_max: int = 5) -> ProviderConfig:
    return ProviderConfig(
        rpm_limit=rpm, base_url="https://exemple.test", default_model="modele-x",
        weight=weight, api_key="clé-de-test", batch_max_agents=batch_max,
    )


class LimiteurFactice:
    """Accepte, refuse, ou n'accepte qu'un nombre fini de réservations — par instance."""

    def __init__(self, capacites: dict[str, int]):
        self.capacites = dict(capacites)
        self.reservations: list[str] = []

    def try_reserve(self, provider: str, *_a, **_k) -> bool:
        if self.capacites.get(provider, 0) <= 0:
            return False
        self.capacites[provider] -= 1
        self.reservations.append(provider)
        return True


CINQ = ("alpha", "beta", "gamma", "delta", "epsilon")


@pytest.fixture
def fournisseurs() -> dict[str, ProviderConfig]:
    return {nom: _provider() for nom in CINQ}


def _balancer(fournisseurs, capacites=None, policy="swrr") -> LoadBalancer:
    caps = capacites if capacites is not None else {nom: 99 for nom in fournisseurs}
    return LoadBalancer(fournisseurs, LimiteurFactice(caps), policy=policy)


# ── A. Le filtrage à la sélection ────────────────────────────────────────────────────────


def test_A1_rotation_ne_sert_que_les_admises(fournisseurs):
    lb = _balancer(fournisseurs)
    admises = ["beta", "delta"]
    servis = {lb.select_provider(admises=admises) for _ in range(20)}
    assert servis == {"beta", "delta"}, (
        f"la rotation a servi hors de l'ensemble admis : {servis - set(admises)}"
    )


def test_A2_cascade_conserve_son_ordre_sous_restriction(fournisseurs):
    """L'ordre déclaré reste la priorité ; seul l'ensemble se réduit."""
    lb = _balancer(fournisseurs, capacites={n: 1 for n in fournisseurs}, policy="cascade")
    premier = lb.select_provider(admises=["gamma", "beta"])
    second = lb.select_provider(admises=["gamma", "beta"])
    # `beta` précède `gamma` dans la configuration : la cascade doit l'entamer d'abord.
    assert (premier, second) == ("beta", "gamma")


@pytest.mark.parametrize("politique", ["swrr", "cascade"])
@pytest.mark.parametrize("restriction", [None, []])
def test_A3_sans_restriction_le_comportement_est_inchange(fournisseurs, politique, restriction):
    """`None` et liste vide valent tous deux « aucune contrainte »."""
    lb = _balancer(fournisseurs, policy=politique)
    servis = {lb.select_provider(admises=restriction) for _ in range(30)}
    attendu = {"alpha"} if politique == "cascade" else set(CINQ)
    assert servis == attendu


def test_A4_la_bascule_reste_dans_l_ensemble_admis(fournisseurs):
    """La première admise refuse : on passe à la suivante ADMISE, jamais au-delà."""
    lb = _balancer(fournisseurs, capacites={"beta": 0, "delta": 5, "alpha": 99})
    servis = {lb.select_provider(admises=["beta", "delta"]) for _ in range(5)}
    assert servis == {"delta"}, "une instance hors liste a servi de recours"


def test_A5_toutes_les_admises_saturees_leve_en_les_nommant(fournisseurs):
    lb = _balancer(fournisseurs, capacites={"beta": 0, "delta": 0, "alpha": 99})
    with pytest.raises(RuntimeError) as err:
        lb.select_provider(admises=["beta", "delta"])
    message = str(err.value)
    assert "beta" in message and "delta" in message
    assert "alpha" not in message, (
        "le message propose une instance hors de l'ensemble comme recours"
    )


def test_A6_une_liste_sans_aucune_instance_connue_est_refusee(fournisseurs):
    lb = _balancer(fournisseurs)
    with pytest.raises(RestrictionInstances):
        lb.select_provider(admises=["inexistante"])


def test_A7_une_liste_a_moitie_fausse_est_refusee(fournisseurs):
    """Une faute de frappe ne doit pas se muer en restriction partielle silencieuse."""
    lb = _balancer(fournisseurs)
    with pytest.raises(RestrictionInstances) as err:
        lb.select_provider(admises=["beta", "betaa"])
    assert "betaa" in str(err.value)


def test_A6bis_une_liste_fausse_ne_vaut_JAMAIS_aucune_restriction(fournisseurs):
    """Le cœur du lot : l'erreur ne doit pas dégénérer en « sers-toi partout »."""
    lb = _balancer(fournisseurs)
    try:
        lb.select_provider(admises=["inexistante"])
    except RestrictionInstances:
        pass
    else:
        pytest.fail("une restriction fausse a été acceptée")
    assert lb._limiter.reservations == [], "un appel a été réservé malgré la restriction fausse"


def test_A8_force_hors_des_admises_est_refuse(fournisseurs):
    lb = _balancer(fournisseurs)
    with pytest.raises(RestrictionInstances) as err:
        lb.select_provider(force="alpha", admises=["beta"])
    assert "alpha" in str(err.value) and "beta" in str(err.value)


def test_A9_force_dans_les_admises_est_servi(fournisseurs):
    lb = _balancer(fournisseurs)
    assert lb.select_provider(force="beta", admises=["beta", "delta"]) == "beta"


# ── B. La restriction survit au trajet ───────────────────────────────────────────────────


def _requete(**extra) -> LLMRequest:
    base = {"category": "itinary_multi_agent", "agents": [{"agent_id": "1"}]}
    return LLMRequest(**{**base, **extra})


def test_B1_le_champ_survit_a_la_validation():
    """⚠ `LLMRequest` n'interdit pas les champs supplémentaires.

    Un champ posé par le client sans être déclaré dans le modèle serait ignoré EN SILENCE par
    la validation — ni exception, ni journal, et une mesure prise sous une restriction qui
    n'a jamais existé. Ce test est la garde de cette propriété.
    """
    req = _requete(instances_admises=["beta", "delta"])
    assert req.instances_admises == ["beta", "delta"]


def test_B2_sans_restriction_le_champ_vaut_none():
    assert _requete().instances_admises is None


def test_B3_la_restriction_est_serialisable():
    """Elle traverse Celery et Redis : ce doit être du JSON simple, pas un ensemble."""
    import json

    charge = _requete(instances_admises=["beta"]).model_dump()
    assert json.loads(json.dumps(charge))["instances_admises"] == ["beta"]


def test_B4_le_parametre_est_bien_cable_du_worker_au_selecteur():
    """La tâche Celery accepte la restriction et la transmet à `select_provider`."""
    import inspect

    from llm_gateway.worker import task_worker

    signature = inspect.signature(task_worker.process_batch_task.__wrapped__)
    assert "instances_admises" in signature.parameters
    source = inspect.getsource(task_worker.process_batch_task.__wrapped__)
    assert "admises=instances_admises" in source


# ── C. La clé de lot ─────────────────────────────────────────────────────────────────────


def test_C1_restrictions_differentes_donnent_des_lots_differents():
    """Un lot est servi par UNE instance : mélanger deux restrictions en servirait une hors
    de son ensemble, sans aucune trace."""
    a = compute_batch_key(_requete(instances_admises=["beta"]))
    b = compute_batch_key(_requete(instances_admises=["delta"]))
    assert a != b


def test_C2_meme_restriction_meme_lot():
    a = compute_batch_key(_requete(instances_admises=["beta", "delta"]))
    b = compute_batch_key(_requete(instances_admises=["beta", "delta"]))
    assert a == b


def test_C3_l_ordre_de_declaration_ne_compte_pas():
    """C'est un ensemble, pas une séquence."""
    a = compute_batch_key(_requete(instances_admises=["beta", "delta"]))
    b = compute_batch_key(_requete(instances_admises=["delta", "beta"]))
    assert a == b


def test_C4_restreinte_et_non_restreinte_ne_se_melangent_pas():
    assert compute_batch_key(_requete(instances_admises=["beta"])) != compute_batch_key(_requete())


# ── D. La bascule après incident ─────────────────────────────────────────────────────────


def test_D1_la_bascule_reporte_la_restriction():
    """Sans cela, la restriction disparaissait au PREMIER incident et le rejeu repartait en
    rotation libre — le défaut que ce lot supprime."""
    import inspect

    from llm_gateway.worker import task_worker

    source = inspect.getsource(task_worker._switch_provider_or_fail)
    assert '"instances_admises": instances_admises' in source, (
        "le rejeu après bascule ne reporte pas la restriction"
    )


def test_D3_le_chemin_402_transmet_la_restriction():
    import inspect

    from llm_gateway.worker import task_worker

    assert "instances_admises" in inspect.signature(task_worker._credits_epuises).parameters
    assert "instances_admises=instances_admises" in inspect.getsource(task_worker._credits_epuises)


def test_D_tous_les_appels_de_bascule_la_transmettent():
    """Un seul point d'appel qui l'oublierait suffirait à perdre la garantie."""
    import inspect

    from llm_gateway.worker import task_worker

    source = inspect.getsource(task_worker.process_batch_task.__wrapped__)
    appels = source.count("_switch_provider_or_fail(") + source.count("_credits_epuises(")
    portes = source.count("instances_admises=instances_admises")
    assert portes >= appels, (
        f"{appels} appel(s) de bascule pour {portes} transmission(s) de la restriction"
    )


# ── E. Le dimensionnement des lots ───────────────────────────────────────────────────────


def _settings_avec(fournisseurs):
    from llm_gateway.config.settings import Settings

    s = Settings()
    s.providers = fournisseurs
    return s


def test_E1_taille_de_lot_calculee_sur_les_admises(fournisseurs):
    fournisseurs["beta"] = _provider(batch_max=2)
    fournisseurs["delta"] = _provider(batch_max=7)
    s = _settings_avec(fournisseurs)
    assert s.get_batch_max_agents(instances_admises=["delta"]) == 7
    assert s.get_batch_max_agents(instances_admises=["beta", "delta"]) == 2


def test_E2_seuil_de_dispatch_calcule_sur_les_admises(fournisseurs):
    fournisseurs["delta"] = _provider(batch_max=7)
    s = _settings_avec(fournisseurs)
    restreint = s.get_dispatch_threshold(instances_admises=["delta"])
    assert restreint == min(s.batching.target_agents, 7)


def test_E3_sans_restriction_les_valeurs_sont_inchangees(fournisseurs):
    s = _settings_avec(fournisseurs)
    assert s.get_batch_max_agents() == s.get_batch_max_agents(instances_admises=[])
    assert s.get_dispatch_threshold() == s.get_dispatch_threshold(instances_admises=None)
