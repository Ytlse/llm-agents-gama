"""
tests/test_config.py — Tests unitaires de la configuration (config.py).

Couvre :
  - build_providers : calcul de batch_max_agents (tokens_per_agent = prompt + output
    supposés, borné par RPM et max_batch_agents)
  - get_batch_max_agents : min conservateur des providers (utilisé par le worker au pop)
  - get_dispatch_threshold : cible de batch découplée du min des providers (utilisée
    par l'API pour décider dispatch immédiat vs fenêtre d'accumulation)

Aucun accès Redis/réseau — Settings ne lit que providers.yaml et l'environnement.
"""

from llm_module.config import ProviderConfig, Settings


def _provider(rpm: int, tpm: int | None = None, batch_max: int = 1) -> ProviderConfig:
    return ProviderConfig(
        rpm_limit=rpm,
        tpm_limit=tpm,
        base_url="https://example.test/v1",
        default_model="test-model",
        batch_max_agents=batch_max,
    )


class TestBuildProviders:
    def test_tokens_per_agent_uses_assumed_output_tokens(self):
        # tokens_per_agent = 2200 + 800 = 3000 → un provider à 30 000 TPM doit
        # accueillir 10 agents/batch (l'ancien 4096 codé en dur donnait 4).
        settings = Settings()
        assert settings.assumed_prompt_tokens + settings.assumed_output_tokens == 3000
        if "groq_llama4" in settings.providers:  # tpm_limit=30000, rpm=30
            assert settings.providers["groq_llama4"].batch_max_agents == 10

    def test_batch_max_agents_still_bounded_by_rpm_and_cap(self):
        settings = Settings()
        for cfg in settings.providers.values():
            assert 1 <= cfg.batch_max_agents <= settings.max_batch_agents
            assert cfg.batch_max_agents <= max(cfg.rpm_limit, 1)

    def test_batch_max_agents_bounded_by_request_capacity(self):
        # Un batch qui ne tient pas dans une requête unique (HTTP 413) ne doit
        # jamais être constitué : max_tokens_per_request borne le batch comme le TPM.
        settings = Settings()
        tokens_per_agent = settings.assumed_prompt_tokens + settings.assumed_output_tokens
        for name, cfg in settings.providers.items():
            if cfg.max_tokens_per_request:
                assert cfg.batch_max_agents <= max(1, cfg.max_tokens_per_request // tokens_per_agent), name

    def test_groq_providers_declare_request_capacity(self):
        # Le free tier groq rejette en 413 toute requête unique > TPM : chaque
        # provider groq doit déclarer max_tokens_per_request (sinon max_tokens
        # part sans clamp et les requêtes sont condamnées — run 2026-07-11).
        settings = Settings()
        for name, cfg in settings.providers.items():
            if cfg.adapter == "groq":
                assert cfg.max_tokens_per_request is not None, name


class TestGetDispatchThreshold:
    def test_forced_provider_uses_its_capacity(self):
        settings = Settings()
        settings.providers = {"big": _provider(rpm=90, batch_max=20)}
        assert settings.get_dispatch_threshold("big") == 20

    def test_dynamic_ignores_small_providers(self):
        # Le seuil de dispatch ne doit PAS être tiré vers 1 par les providers à
        # petit TPM, sinon toute requête part immédiatement sans accumulation.
        settings = Settings()
        settings.providers = {
            "tiny": _provider(rpm=2, batch_max=1),
            "big": _provider(rpm=90, batch_max=20),
        }
        assert settings.get_dispatch_threshold() == settings.batch_target_agents
        assert settings.get_batch_max_agents() == 1  # le worker, lui, reste conservateur

    def test_dynamic_capped_by_biggest_provider(self):
        settings = Settings()
        settings.providers = {"small": _provider(rpm=5, batch_max=4)}
        assert settings.get_dispatch_threshold() == 4

    def test_fallback_without_providers(self):
        settings = Settings()
        settings.providers = {}
        assert settings.get_dispatch_threshold() == settings.batch_target_agents
