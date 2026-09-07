"""La cascade des paramètres d'inférence : requête > fournisseur > défauts (core/inference.py)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from llm_gateway.core.inference import InferenceParams, resolve_inference

DEFAULTS = SimpleNamespace(temperature=0.7, top_p=None, max_tokens=4096)


def test_defauts_seuls():
    p = resolve_inference({}, None, DEFAULTS)
    assert p == InferenceParams(temperature=0.7, top_p=None, max_tokens=4096)


def test_le_fournisseur_surcharge_les_defauts():
    prov = SimpleNamespace(temperature=0.2, top_p=0.9, max_tokens=None)
    p = resolve_inference({}, prov, DEFAULTS)
    assert (p.temperature, p.top_p, p.max_tokens) == (0.2, 0.9, 4096), "max_tokens absent → défaut"


def test_la_requete_surcharge_le_fournisseur():
    prov = SimpleNamespace(temperature=0.2, top_p=0.9, max_tokens=1000)
    p = resolve_inference({"temperature": 1.0, "max_tokens": 512}, prov, DEFAULTS)
    assert (p.temperature, p.top_p, p.max_tokens) == (1.0, 0.9, 512)


def test_valeurs_de_requete_en_chaine_sont_coercees():
    p = resolve_inference({"temperature": "0.3", "max_tokens": "256", "top_p": "0.5"}, None, DEFAULTS)
    assert p == InferenceParams(temperature=0.3, top_p=0.5, max_tokens=256)


def test_valeur_illisible_ignoree_pas_d_exception():
    p = resolve_inference({"temperature": "chaud", "max_tokens": None}, None, DEFAULTS)
    assert p.temperature == 0.7 and p.max_tokens == 4096


def test_top_p_reste_none_si_personne_ne_le_donne():
    assert resolve_inference({"temperature": 0.1}, SimpleNamespace(temperature=None, top_p=None, max_tokens=None), DEFAULTS).top_p is None


@pytest.mark.parametrize("params", [None, {}])
def test_parametres_absents(params):
    assert resolve_inference(params, None, DEFAULTS).max_tokens == 4096
