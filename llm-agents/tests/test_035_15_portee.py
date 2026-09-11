"""Ticket 035 — la portée d'un décideur passerelle : `local` ou `distant` (P1–P12).

Pourquoi cette règle existe : `qwen/qwen3.8-27b` est le `default_model` d'une instance Groq ET
d'une instance LM Studio. L'épinglage se faisant par égalité de modèle, l'expérience
`exp_qwen38-27b_minper_jtir_t0_nosim` a commencé sur Groq puis se serait poursuivie sur le MLX
4 bit local à l'épuisement du quota — deux quantifications sous un seul nom. La portée nomme le
bord ; les deux usages restent ouverts, c'est le silence qui ne l'est plus.

Un test par règle. Aucun accès au providers.yaml du dépôt sauf P4, qui vérifie justement qu'il
ne met pas les deux implémentations de la règle locale en désaccord.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import ClassVar

import pytest
import yaml
from experiences import experience as E
from experiences import nommage as N
from experiences.cles import jeu_de_cles
from experiences.ressources import (
    est_instance_locale,
    instances_pour_modele,
    portees_pour_modele,
)

RACINE = Path(__file__).resolve().parents[2]

# Deux instances qui servent le MÊME identifiant de modèle des deux côtés : la configuration
# réelle du 2026-09-11, réduite à ce qui compte.
PROVIDERS = {
    "groq_qwen_qwen3_8_27b_key1": {
        "adapter": "groq",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "qwen/qwen3.8-27b",
        "rpm_limit": 30,
    },
    "lmstudio_qwen3_8_27b_key1": {
        "adapter": "openai_compatible",
        "base_url": "http://host.docker.internal:1234/v1",
        "default_model": "qwen/qwen3.8-27b",
        "rpm_limit": 30,
    },
    # Deux CLÉS d'un même fournisseur : un seul bord, donc aucune ambiguïté à lever.
    "google_gemini31_key1": {
        "adapter": "google",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "default_model": "gemini-3.1-flash-lite",
        "rpm_limit": 15,
    },
    "google_gemini31_key2": {
        "adapter": "google",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "default_model": "gemini-3.1-flash-lite",
        "rpm_limit": 15,
    },
}


@pytest.fixture
def providers_factices(tmp_path, monkeypatch):
    """`charger_providers()` lit CE fichier : `candidats_providers` met l'env en tête."""
    p = tmp_path / "providers.yaml"
    p.write_text(yaml.safe_dump({"providers": PROVIDERS}), encoding="utf-8")
    monkeypatch.setenv("LLM_GATEWAY_PROVIDERS_FILE", str(p))
    return p


# ── P1–P4 : la portée d'une instance ─────────────────────────────────────────


def test_P1_sans_portee_les_deux_bords_repondent():
    """Compat : une définition antérieure au champ garde EXACTEMENT son comportement."""
    assert instances_pour_modele("qwen/qwen3.8-27b", PROVIDERS) == [
        "groq_qwen_qwen3_8_27b_key1",
        "lmstudio_qwen3_8_27b_key1",
    ]


def test_P2_la_portee_restreint_au_bord_demande():
    assert instances_pour_modele("qwen/qwen3.8-27b", PROVIDERS, "local") == [
        "lmstudio_qwen3_8_27b_key1"
    ]
    assert instances_pour_modele("qwen/qwen3.8-27b", PROVIDERS, "distant") == [
        "groq_qwen_qwen3_8_27b_key1"
    ]


@pytest.mark.parametrize(
    "url, locale",
    [
        ("http://host.docker.internal:1234/v1", True),
        ("http://localhost:1234/v1", True),
        ("http://127.0.0.1:1234/v1", True),
        ("https://api.groq.com/openai/v1", False),
        ("http://host.docker.internal:8000/v1", False),  # l'hôte, mais pas LM Studio
        ("", False),
    ],
)
def test_P3_une_instance_est_locale_si_elle_vise_LM_Studio_sur_cette_machine(
    url, locale
):
    assert est_instance_locale({"base_url": url}) is locale


def test_P4_la_regle_locale_ne_diverge_pas_de_celle_du_tableau_de_bord():
    """La règle est écrite deux fois — conteneur et hôte — donc elle est épinglée ici.

    `experiences.ressources` tourne dans le conteneur `controller`, sans le paquet du tableau
    de bord ; `scripts.dashboard.lmstudio` tourne sur l'hôte, sans `loguru` ni `yaml` du
    conteneur. Elles ne peuvent pas s'importer l'une l'autre : ce test est le seul garde-fou
    contre leur dérive, et il travaille sur le providers.yaml RÉEL.
    """
    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))
    from scripts.dashboard import lmstudio

    reel = yaml.safe_load(
        (RACINE / "config" / "llm_gateway" / "providers.yaml").read_text(
            encoding="utf-8"
        )
    )
    instances = (reel or {}).get("providers") or {}
    assert instances, "providers.yaml réel introuvable ou vide"
    desaccords = [
        nom
        for nom, cfg in instances.items()
        if isinstance(cfg, dict)
        and est_instance_locale(cfg) != lmstudio.est_instance_lmstudio(cfg)
    ]
    assert not desaccords, f"les deux règles ne disent pas la même chose : {desaccords}"


# ── P5–P7 : le refus, qui vise le SILENCE et non l'usage ─────────────────────


class _JeuFactice:
    """Le strict nécessaire que `refuser_si_impossible` lit sur un jeu clos et à jour."""

    nom = "jeu_t"
    clos = True
    jour_simule = "2026-03-16"
    manifest: ClassVar[dict] = {"dependances": {}}

    def verifier_population(self, _population):
        return None

    def jours_equivalents(self):
        return []


def _exp(tmp_path, decideur: dict) -> E.Experience:
    p = tmp_path / "exp.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "nom": "exp_t",
                "population": {"chemin": "/data/eqasim-output/population_1000_AAMAS"},
                "jeu": {"nom": "jeu_t"},
                "gabarit": {"categorie": "itinary_multi_agent"},
                "decideur": decideur,
                "mode": "sans_simulateur",
                "calendrier": {
                    "politique": "commune",
                    "date": "2026-03-16",
                    "graine": 42,
                },
                "horizon_jours": 1,
                "memoire": False,
                "evenements": [],
                "graine_ordre": 42,
                "graine_tirage": 42,
                "regroupement": {"parallelisme": 4},
                "tolerances_horaires": dict(N.TOLERANCES_REFERENCE),
                "max_candidats": 6,
                "attente_max_s": 5,
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return E.charger_experience(p)


def _refus(tmp_path, decideur: dict) -> list[str]:
    refus, _ = E.refuser_si_impossible(
        _exp(tmp_path, decideur),
        _JeuFactice(),
        object(),
        dependances={},
        periodes={},
    )
    return refus


def test_P5_un_modele_servi_des_deux_cotes_sans_portee_est_refuse(
    tmp_path, providers_factices
):
    refus = _refus(tmp_path, {"type": "passerelle", "modele": "qwen/qwen3.8-27b"})
    ambigus = [r for r in refus if "des deux côtés" in r]
    assert len(ambigus) == 1, refus
    # Le message doit permettre d'AGIR : les deux instances nommées, et la sortie dite.
    assert "groq_qwen_qwen3_8_27b_key1" in ambigus[0]
    assert "lmstudio_qwen3_8_27b_key1" in ambigus[0]
    assert "decideur.portee" in ambigus[0]


@pytest.mark.parametrize("portee", ["local", "distant"])
def test_P6_la_portee_posee_rouvre_les_deux_usages(
    tmp_path, providers_factices, portee
):
    """Le but n'est pas d'interdire un bord : c'est de savoir lequel on mesure."""
    refus = _refus(
        tmp_path,
        {"type": "passerelle", "modele": "qwen/qwen3.8-27b", "portee": portee},
    )
    assert not [r for r in refus if "des deux côtés" in r], refus


def test_P7_deux_cles_d_un_meme_fournisseur_ne_sont_pas_une_ambiguite(
    tmp_path, providers_factices
):
    """Deux seaux de quota interchangeables : rien à trancher, rien à demander."""
    refus = _refus(tmp_path, {"type": "passerelle", "modele": "gemini-3.1-flash-lite"})
    assert not [r for r in refus if "des deux côtés" in r], refus
    assert portees_pour_modele("gemini-3.1-flash-lite", PROVIDERS) == {
        "distant": ["google_gemini31_key1", "google_gemini31_key2"]
    }


def test_P8_la_portee_ne_vaut_que_pour_la_passerelle():
    erreurs = E.DecideurSpec(type="aleatoire", graine=1, portee="local").valider()
    assert any("ne vaut que pour un décideur passerelle" in e for e in erreurs)


# ── P9–P10 : l'empreinte, qui scelle les archives ────────────────────────────


def test_P9_une_definition_sans_portee_garde_son_empreinte():
    """Non-régression d'archive : les exécutions déjà scellées doivent rester vérifiables."""
    dec = E.DecideurSpec(type="passerelle", modele="qwen/qwen3.8-27b")
    # La formule d'AVANT le champ, recomposée ici : le test échoue si la portée s'y invite.
    brut = f"passerelle|qwen/qwen3.8-27b|{sorted({}.items())}||None|"
    assert dec.empreinte() == hashlib.sha256(brut.encode("utf-8")).hexdigest()


def test_P10_deux_portees_sont_deux_decideurs():
    commun = {"type": "passerelle", "modele": "qwen/qwen3.8-27b"}
    local = E.DecideurSpec(**commun, portee="local").empreinte()
    distant = E.DecideurSpec(**commun, portee="distant").empreinte()
    muet = E.DecideurSpec(**commun).empreinte()
    assert local != distant, "deux quantifications ne rendent pas les mêmes décisions"
    assert muet not in (local, distant)


# ── P11–P12 : le nom, et le quota ────────────────────────────────────────────


def _def_nommage(portee):
    dec = {
        "type": "passerelle",
        "modele": "qwen/qwen3.8-27b",
        "parametres": {"temperature": 0.0},
    }
    if portee:
        dec["portee"] = portee
    return {
        "population": {"chemin": "/data/eqasim-output/population_1000_AAMAS"},
        "jeu": {"nom": "population_1000_AAMAS_20260316"},
        "gabarit": {"variante": "minimal_persona"},
        "decideur": dec,
        "calendrier": {"politique": "aleatoire", "date": "2026-03-16", "graine": 42},
        "mode": "sans_simulateur",
    }


def test_P11_seul_le_local_se_dit_dans_le_nom():
    """`distant` est la référence (N7) : aucun nom existant ne bouge."""
    muet = N.nom_canonique(_def_nommage(None))
    assert muet == "exp_qwen38-27b_minper_jtir_t0_nosim"
    assert N.nom_canonique(_def_nommage("distant")) == muet
    assert (
        N.nom_canonique(_def_nommage("local"))
        == "exp_qwen38-27b_local_minper_jtir_t0_nosim"
    )


def test_P12_le_quota_reserve_suit_le_bord_epingle():
    """Une expérience locale ne doit pas réserver le quota Groq, et réciproquement."""
    assert jeu_de_cles("qwen/qwen3.8-27b", PROVIDERS, portee="distant") == {"groq_key1"}
    assert jeu_de_cles("qwen/qwen3.8-27b", PROVIDERS, portee="local") == {
        "openai_compatible_key1"
    }
    # Sans portée, les deux bords sont réservés : conservateur, comme avant le champ.
    assert jeu_de_cles("qwen/qwen3.8-27b", PROVIDERS) == {
        "groq_key1",
        "openai_compatible_key1",
    }
