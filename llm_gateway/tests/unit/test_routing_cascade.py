"""Routage en cascade : épuiser une clé avant d'entamer la suivante.

Deux clés servent le même modèle, chacune avec son seau de 500 requêtes par jour. Le routage
SWRR les entame en parallèle ; la cascade consomme la première en entier et ne bascule que
lorsqu'elle REFUSE — quota atteint, cooldown, ou débit par minute saturé (demande du
2026-09-07).
"""

import pytest

from llm_gateway.balancer.router import LoadBalancer
from llm_gateway.config.settings import ProviderConfig, RoutingSettings


def _provider(rpm: int = 15, weight: float = 1.0) -> ProviderConfig:
    return ProviderConfig(
        rpm_limit=rpm, base_url="https://exemple.test", default_model="modele-x", weight=weight,
        api_key="clé-de-test",
    )


class LimiteurFactice:
    """Un limiteur qui accepte, refuse, ou n'accepte qu'un nombre fini de réservations."""

    def __init__(self, capacites: dict[str, int]):
        self.capacites = dict(capacites)
        self.reservations: list[str] = []

    def try_reserve(self, provider: str, *_a, **_k) -> bool:
        """La seule méthode que `_try_reserve` appelle : pas de filet attrape-tout, qui
        masquerait un refus et rendrait ces tests toujours verts."""
        if self.capacites.get(provider, 0) <= 0:
            return False
        self.capacites[provider] -= 1
        self.reservations.append(provider)
        return True


@pytest.fixture
def fournisseurs() -> dict[str, ProviderConfig]:
    return {"cle1": _provider(), "cle2": _provider(), "cle3": _provider()}


def test_la_cascade_epuise_le_premier_avant_de_basculer(fournisseurs):
    limiteur = LimiteurFactice({"cle1": 3, "cle2": 2, "cle3": 99})
    balancer = LoadBalancer(fournisseurs, limiteur, policy="cascade")

    choisis = [balancer.select_provider() for _ in range(7)]
    assert choisis == ["cle1", "cle1", "cle1", "cle2", "cle2", "cle3", "cle3"], choisis


def test_le_swrr_etale_la_charge(fournisseurs):
    limiteur = LimiteurFactice({"cle1": 99, "cle2": 99, "cle3": 99})
    balancer = LoadBalancer(fournisseurs, limiteur, policy="swrr")

    choisis = {balancer.select_provider() for _ in range(6)}
    assert len(choisis) > 1, "le routage SWRR doit toucher plusieurs fournisseurs"


def test_la_cascade_epuisee_le_dit_avec_l_ordre_suivi(fournisseurs):
    limiteur = LimiteurFactice({})
    balancer = LoadBalancer(fournisseurs, limiteur, policy="cascade")

    with pytest.raises(RuntimeError) as refus:
        balancer.select_provider()
    message = str(refus.value)
    assert "Cascade épuisée" in message
    for nom in ("cle1", "cle2", "cle3"):
        assert nom in message, message


def test_la_politique_par_defaut_reste_le_swrr():
    assert RoutingSettings().policy == "swrr"
    assert RoutingSettings(policy="cascade").policy == "cascade"
    with pytest.raises(ValueError):
        RoutingSettings(policy="aleatoire")


def test_le_depot_demande_la_cascade_par_l_environnement():
    """Le dépôt tourne en cascade. Le fichier des fournisseurs n'accepte QUE des fournisseurs
    (il refuse toute autre clé) : la politique passe donc par l'environnement du compose."""
    from pathlib import Path

    racine = Path(__file__).resolve().parents[3]
    compose = (racine / "docker-compose.yml").read_text(encoding="utf-8")
    assert "LLM_GATEWAY_ROUTING__POLICY: ${LLM_GATEWAY_ROUTING__POLICY:-cascade}" in compose

    import yaml
    conf = yaml.safe_load((racine / "config" / "llm_gateway" / "providers.yaml").read_text(encoding="utf-8"))
    assert "routing" not in conf, "ce fichier n'accepte que des fournisseurs : il refuserait la clé"
