"""Adaptateur OpenAI-compatible — contrôles de la réponse du fournisseur."""



# ── Substitution silencieuse de modèle (constatée le 2026-09-10 sur LM Studio) ──


def _adapter_pour(monkeypatch, instance="lmstudio_test", modele="qwen/qwen3.8-27b"):
    from llm_gateway.adapters.openai_compatible import OpenAICompatibleAdapter

    a = OpenAICompatibleAdapter()
    a._instance_name = instance
    monkeypatch.setattr(a, "_resolve_model", lambda request: modele)
    return a


def test_refuse_un_modele_servi_different(monkeypatch):
    """Un identifiant inconnu ne produit pas d'erreur côté LM Studio : il sert un autre modèle."""
    import pytest

    from llm_gateway.adapters.base import ProviderClientError

    a = _adapter_pour(monkeypatch)
    with pytest.raises(ProviderClientError, match="substitution de modèle"):
        a._refuser_substitution_de_modele(object(), {"model": "qwen3-vl-8b-instruct-mlx"})


def test_accepte_le_modele_demande(monkeypatch):
    a = _adapter_pour(monkeypatch)
    a._refuser_substitution_de_modele(object(), {"model": "qwen/qwen3.8-27b"})


def test_reponse_sans_champ_modele_passe(monkeypatch):
    """Refuser sur un champ absent bloquerait des fournisseurs conformes."""
    a = _adapter_pour(monkeypatch)
    a._refuser_substitution_de_modele(object(), {})
    a._refuser_substitution_de_modele(object(), {"model": ""})


def test_message_nomme_les_deux_modeles(monkeypatch):
    import pytest

    from llm_gateway.adapters.base import ProviderClientError

    a = _adapter_pour(monkeypatch)
    with pytest.raises(ProviderClientError) as exc:
        a._refuser_substitution_de_modele(object(), {"model": "autre-modele"})
    assert "qwen/qwen3.8-27b" in str(exc.value) and "autre-modele" in str(exc.value)
    assert "default_model" in str(exc.value), "le message doit dire où corriger"
