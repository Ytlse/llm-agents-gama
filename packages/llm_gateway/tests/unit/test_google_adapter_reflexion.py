"""Profondeur de réflexion côté Google — spec hygiène, point « budget de réflexion ».

Le piège central : la pensée est prélevée sur le budget de SORTIE. Un budget de réflexion
demandé sans réserve fait tronquer la réponse (MAX_TOKENS) et l'appel est perdu.
"""

from __future__ import annotations

import pytest

from llm_gateway.adapters.google_adapter import RESERVE_REFLEXION, GoogleAdapter
from llm_gateway.core.models import InternalMessage, InternalRequest


def _req(**kw) -> InternalRequest:
    base = dict(provider="google", messages=[InternalMessage(role="user", content="x")],
                response_schema={"type": "object"}, temperature=0.0, max_tokens=4096)
    base.update(kw)
    return InternalRequest(**base)


def _config(request) -> dict:
    """Le `generationConfig` que l'adapter construit RÉELLEMENT, sans appel réseau.

    ⚠ Cette fonction en recopiait la construction au lieu de l'appeler. Elle vérifiait donc
    sa propre copie, et le réglage de NIVEAU — que l'adapter posait à côté de
    `maxOutputTokens`, là où l'API le refuse — n'y figurait même pas. Le défaut est parti en
    production sans qu'un test le voie : chaque appel du bras gemini-3.5-flash-lite est
    revenu en 400 le 2026-09-11, et l'expérience est tombée en entier.

    `_generation_config` a été extraite de `call` pour être appelable ici telle quelle. Deux
    implémentations d'un même payload finissent toujours par diverger ; il n'y en a plus
    qu'une.
    """
    a = GoogleAdapter()
    a._instance_name = "google_test"
    # Le seul contrôle qui interroge la configuration de l'instance : les tests de niveau
    # ci-dessous l'exercent séparément, sur la vraie méthode.
    a._refuser_niveau_non_supporte = lambda _niveau: None  # type: ignore[method-assign]
    return a._generation_config(request)


def test_google_declare_appliquer_la_reflexion():
    assert GoogleAdapter.applique_reflexion is True


def test_rien_n_est_envoye_sans_budget():
    """Comportement d'avant le 2026-09-10, conservé : le fournisseur garde son défaut."""
    cfg = _config(_req())
    assert "thinkingConfig" not in cfg
    assert cfg["maxOutputTokens"] == 4096


def test_budget_zero_desactive_sans_reserver():
    cfg = _config(_req(thinking_budget=0))
    assert cfg["thinkingConfig"]["thinkingBudget"] == 0
    assert cfg["maxOutputTokens"] == 4096, "réflexion éteinte : aucune réserve à prendre"


def test_budget_positif_est_ajoute_au_plafond_de_sortie():
    """Sans cette réserve, la pensée mange la réponse et l'appel part en MAX_TOKENS."""
    cfg = _config(_req(thinking_budget=1024))
    assert cfg["thinkingConfig"]["thinkingBudget"] == 1024
    assert cfg["maxOutputTokens"] == 4096 + 1024


def test_budget_dynamique_reserve_un_forfait():
    """-1 laisse le modèle arbitrer : on ne sait pas combien, on réserve un forfait."""
    cfg = _config(_req(thinking_budget=-1))
    assert cfg["thinkingConfig"]["thinkingBudget"] == -1
    assert cfg["maxOutputTokens"] == 4096 + RESERVE_REFLEXION


def test_les_pensees_ne_sont_pas_rapatriees():
    """`includeThoughts: False` — la trace n'a que faire du texte de la pensée."""
    assert _config(_req(thinking_budget=512))["thinkingConfig"]["includeThoughts"] is False


@pytest.mark.parametrize("adapter_mod,classe", [
    ("llm_gateway.adapters.openai_compatible", "OpenAICompatibleAdapter"),
    ("llm_gateway.adapters.mistral_adapter", "MistralAdapter"),
    ("llm_gateway.adapters.groq_adapter", "GroqAdapter"),
    ("llm_gateway.adapters.cerebras_adapter", "CerebrasAdapter"),
])
def test_les_autres_adapters_ne_pretendent_pas_l_appliquer(adapter_mod, classe):
    """Un réglage scellé dans l'empreinte et jamais appliqué est le défaut trouvé sur `t0`."""
    import importlib

    cls = getattr(importlib.import_module(adapter_mod), classe)
    assert cls.applique_reflexion is False


def test_l_avertissement_ne_part_qu_une_fois(caplog):
    from llm_gateway.adapters.openai_compatible import OpenAICompatibleAdapter

    a = OpenAICompatibleAdapter()
    a._instance_name = "lmstudio_test"
    a._signaler_reflexion_ignoree(1024)
    assert a._reflexion_signalee is True
    a._signaler_reflexion_ignoree(1024)  # ne doit pas relever le drapeau une seconde fois


def test_aucun_avertissement_sans_budget():
    from llm_gateway.adapters.openai_compatible import OpenAICompatibleAdapter

    a = OpenAICompatibleAdapter()
    a._instance_name = "lmstudio_test"
    a._signaler_reflexion_ignoree(None)
    assert a._reflexion_signalee is False


# ── Niveau de réflexion — le réglage courant de l'API (relevé le 2026-09-10) ──


def test_niveau_est_emis_tel_quel(monkeypatch):
    from llm_gateway.adapters import google_adapter as G

    a = G.GoogleAdapter()
    a._instance_name = "google_test"
    monkeypatch.setattr(G, "get_settings", lambda: type("S", (), {"providers": {}})())
    a._refuser_niveau_non_supporte("high")  # aucune déclaration : laisse passer


def test_niveau_non_declare_ne_bloque_pas(monkeypatch):
    """Sans `thinking_levels`, on ne bloque pas sur une liste devinée."""
    from llm_gateway.adapters import google_adapter as G

    a = G.GoogleAdapter()
    a._instance_name = "i"
    cfg = type("C", (), {"thinking_levels": None, "default_model": "m"})()
    monkeypatch.setattr(G, "get_settings", lambda: type("S", (), {"providers": {"i": cfg}})())
    a._refuser_niveau_non_supporte("minimal")


def test_niveau_hors_liste_refuse(monkeypatch):
    """`minimal` sur un modèle qui ne le déclare pas : 400 à chaque appel, autant le dire ici."""
    import pytest

    from llm_gateway.adapters import google_adapter as G
    from llm_gateway.adapters.base import ProviderClientError

    a = G.GoogleAdapter()
    a._instance_name = "i"
    cfg = type("C", (), {"thinking_levels": ["low", "medium", "high"], "default_model": "gemini-3.8-flash"})()
    monkeypatch.setattr(G, "get_settings", lambda: type("S", (), {"providers": {"i": cfg}})())
    with pytest.raises(ProviderClientError, match="non accepté"):
        a._refuser_niveau_non_supporte("minimal")


def test_niveau_et_budget_ensemble_refuses_par_la_cascade():
    """L'API rend 400 si les deux coexistent : la cascade le refuse avant l'appel."""
    from types import SimpleNamespace

    import pytest

    from llm_gateway.core.inference import ReglagesReflexionIncompatibles, resolve_inference

    d = SimpleNamespace(temperature=0.7, top_p=None, max_tokens=4096)
    with pytest.raises(ReglagesReflexionIncompatibles, match="400"):
        resolve_inference({"thinking_level": "high", "thinking_budget": 1024}, None, d)


def test_niveau_seul_passe():
    from types import SimpleNamespace

    from llm_gateway.core.inference import resolve_inference

    d = SimpleNamespace(temperature=0.7, top_p=None, max_tokens=4096)
    p = resolve_inference({"thinking_level": "high"}, None, d)
    assert p.thinking_level == "high" and p.thinking_budget is None


# ── Substitution silencieuse de modèle côté Google ───────────────────────────


def _adapter():
    a = GoogleAdapter()
    a._instance_name = "google_test"
    return a


def test_modele_identique_passe():
    _adapter()._refuser_substitution_de_modele("gemini-3.5-flash", {"modelVersion": "gemini-3.5-flash"})


def test_identifiant_versionne_est_le_meme_modele():
    """L'API répond couramment `-001` : refuser là-dessus casserait des instances qui marchent."""
    _adapter()._refuser_substitution_de_modele(
        "gemini-3.5-flash", {"modelVersion": "gemini-3.5-flash-001"}
    )


def test_alias_retire_servi_par_son_successeur_refuse():
    """Le cas réel : `-preview` arrêté le 2026-05-25, servi par le modèle sans suffixe."""
    import pytest

    from llm_gateway.adapters.base import ProviderClientError

    with pytest.raises(ProviderClientError, match="substitution de modèle"):
        _adapter()._refuser_substitution_de_modele(
            "gemini-3.1-flash-lite-preview", {"modelVersion": "gemini-3.1-flash-lite"}
        )


def test_reponse_sans_model_version_passe():
    _adapter()._refuser_substitution_de_modele("gemini-3.5-flash", {})
    _adapter()._refuser_substitution_de_modele("gemini-3.5-flash", {"modelVersion": ""})


# ── Le NIVEAU de réflexion : ce que les tests ne couvraient pas ──────────────
#
# Tout ce bloc manquait. Le niveau était construit par l'adapter, jamais par le helper de
# test, donc jamais vérifié. Les formes ci-dessous ont été éprouvées contre l'API Google le
# 2026-09-11 : seule `thinkingConfig.thinkingLevel` est acceptée.


def test_le_niveau_va_DANS_thinkingConfig():
    """`generationConfig.thinking_level` → 400 « Unknown name ». C'est le défaut corrigé."""
    cfg = _config(_req(thinking_level="low"))
    assert cfg["thinkingConfig"]["thinkingLevel"] == "low"
    assert "thinking_level" not in cfg, "l'API refuse ce champ au niveau de generationConfig"
    assert "thinkingLevel" not in cfg, "elle le refuse aussi en camelCase à ce niveau"


def test_le_niveau_ne_rapatrie_pas_les_pensees():
    assert _config(_req(thinking_level="high"))["thinkingConfig"]["includeThoughts"] is False


def test_un_niveau_non_minimal_reserve_un_forfait_de_sortie():
    """La pensée est prélevée sur le budget de sortie : sans réserve, la réponse est tronquée."""
    cfg = _config(_req(thinking_level="high"))
    assert cfg["maxOutputTokens"] == 4096 + RESERVE_REFLEXION


def test_le_niveau_minimal_ne_reserve_rien():
    """`minimal` ne pense quasiment pas : réserver du budget pour rien le gaspillerait."""
    cfg = _config(_req(thinking_level="minimal"))
    assert cfg["thinkingConfig"]["thinkingLevel"] == "minimal"
    assert cfg["maxOutputTokens"] == 4096


def test_sans_niveau_ni_budget_aucun_thinkingConfig():
    """Comportement d'avant le 2026-09-10 : le fournisseur garde son défaut."""
    assert "thinkingConfig" not in _config(_req())


def test_le_budget_reste_un_budget_quand_il_est_seul():
    """La correction du niveau ne doit pas déplacer le budget, qui marchait déjà."""
    cfg = _config(_req(thinking_budget=1024))
    assert cfg["thinkingConfig"] == {"thinkingBudget": 1024, "includeThoughts": False}
    assert "thinkingLevel" not in cfg["thinkingConfig"]


def test_niveau_et_budget_ne_coexistent_jamais_dans_le_payload():
    """L'API : « You can only set only one of thinking budget and thinking level » (400).

    La cascade `resolve_inference` les refuse déjà ensemble ; ceci est la seconde barrière,
    au cas où un appelant construirait la requête à la main.
    """
    cfg = _config(_req(thinking_level="low", thinking_budget=512))
    tc = cfg["thinkingConfig"]
    assert ("thinkingLevel" in tc) != ("thinkingBudget" in tc), tc
