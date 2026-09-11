"""La portée local/distant, vue du tableau de bord (D1–D7).

Le formulaire a toujours demandé le bord — deux entrées « modèle de langage », deux sélecteurs
de modèle — mais la réponse mourait dans `type_plateforme`, qui écrasait les deux en
`passerelle`. Le fichier ne gardait que le nom du modèle, et l'expérience pouvait basculer d'un
bord à l'autre en cours de route.

Le fil de ces tests : ce qu'on AFFICHE d'une exécution doit venir de l'exécution, pas du
providers.yaml d'aujourd'hui. `exp_qwen38-27b_minper_jtir_t0_nosim`, servie à 100 % par Groq le
2026-09-09, s'affichait `groq · local` parce qu'une instance LM Studio portant le même
identifiant de modèle a été déclarée le lendemain.
"""

import json
import sys
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.dashboard import experiences  # noqa: E402

PROVIDERS = {
    "providers": {
        "groq_qwen_key1": {
            "adapter": "groq",
            "base_url": "https://api.groq.com/openai/v1",
            "default_model": "qwen/qwen3.8-27b",
        },
        "lmstudio_qwen_key1": {
            "adapter": "openai_compatible",
            "base_url": "http://host.docker.internal:1234/v1",
            "default_model": "qwen/qwen3.8-27b",
        },
        "lmstudio_muse_key1": {
            "adapter": "openai_compatible",
            "base_url": "http://host.docker.internal:1234/v1",
            "default_model": "meta/muse-glimmer",
        },
        "google_g35_key1": {
            "adapter": "google",
            "base_url": "https://generativelanguage.googleapis.com",
            "default_model": "gemini-3.5-flash-lite",
        },
    }
}


@pytest.fixture
def providers(tmp_path, monkeypatch):
    chemin = tmp_path / "providers.yaml"
    chemin.write_text(yaml.safe_dump(PROVIDERS), encoding="utf-8")
    monkeypatch.setattr(experiences, "PROVIDERS_YAML", chemin)
    for cache in (
        experiences._FAMILLES_CACHE,
        experiences._PORTEE_CACHE,
        experiences._FOURNISSEUR_EXEC_CACHE,
    ):
        cache.clear()
    yield chemin
    for cache in (
        experiences._FAMILLES_CACHE,
        experiences._PORTEE_CACHE,
        experiences._FOURNISSEUR_EXEC_CACHE,
    ):
        cache.clear()


# ── D1–D2 : le choix du formulaire survit à l'écriture ───────────────────────


def test_D1_le_bord_choisi_est_ecrit_dans_le_fichier():
    """Sans ce champ, `instances_pour_modele` ré-élargit ensuite aux deux bords."""
    assert experiences.portee_plateforme("passerelle_local") == "local"
    assert experiences.portee_plateforme("passerelle_distant") == "distant"
    # Hors passerelle il n'y a pas de bord à nommer.
    for choix in ("aleatoire", "duree_minimale", "rejeu", "antigravity", "modele"):
        assert experiences.portee_plateforme(choix) is None, choix


def test_D2_la_portee_ecrite_fait_foi_a_la_relecture(providers):
    """La définition dit son bord ; on ne le redevine pas dans le providers.yaml du jour."""
    locaux = experiences.modeles_par_portee()[0]
    c = experiences.choix_decideur
    assert c("passerelle", "qwen/qwen3.8-27b", locaux, "local") == "passerelle_local"
    assert c("passerelle", "qwen/qwen3.8-27b", locaux, "distant") == "passerelle_distant"
    # Un décideur sans LLM garde son type, portée ou pas.
    assert c("aleatoire", None, locaux, None) == "aleatoire"


def test_D3_sans_portee_un_modele_des_deux_bords_se_range_du_cote_distant(providers):
    """L'ancienne heuristique testait `local` d'abord : une archive Groq se rouvrait « locale »."""
    locaux = experiences.modeles_par_portee()[0]
    c = experiences.choix_decideur
    assert c("passerelle", "qwen/qwen3.8-27b", locaux, None) == "passerelle_distant"
    # Un modèle servi UNIQUEMENT en local reste local : l'heuristique n'est pas cassée.
    assert c("passerelle", "meta/muse-glimmer", locaux, None) == "passerelle_local"
    assert c("passerelle", "gemini-3.5-flash-lite", locaux, None) == "passerelle_distant"


# ── D4–D5 : ce qu'on affiche d'une définition ────────────────────────────────


def test_D4_le_fournisseur_affiche_suit_la_portee(providers):
    f = experiences.fournisseur_de
    m = "qwen/qwen3.8-27b"
    assert f({"type": "passerelle", "modele": m, "portee": "local"}) == "local"
    assert f({"type": "passerelle", "modele": m, "portee": "distant"}) == "groq"


def test_D5_sans_portee_l_ambiguite_est_dite_et_non_tranchee(providers):
    """`groq · local` se lisait comme un fournisseur composé — ce qui n'existe pas."""
    rendu = experiences.fournisseur_de({"type": "passerelle", "modele": "qwen/qwen3.8-27b"})
    assert rendu.startswith(experiences.MARQUE_AMBIGU)
    assert "ou" in rendu and "groq" in rendu and "local" in rendu
    # Deux familles DISTANTES restent une liste : des seaux de quota interchangeables, pas
    # deux quantifications — il n'y a rien à trancher.
    assert experiences.fournisseur_de(
        {"type": "passerelle", "modele": "gemini-3.5-flash-lite"}
    ) == "google"


# ── D6–D7 : ce qu'on affiche d'une EXÉCUTION ─────────────────────────────────


def _execution(dossier: Path, instances: list[str]) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    lignes = [
        json.dumps({"fournisseur": i, "methode": "llm"}, ensure_ascii=False)
        for i in instances
    ]
    (dossier / "decisions.jsonl").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return dossier


def test_D6_le_fournisseur_d_une_execution_est_lu_dans_ses_decisions(
    tmp_path, providers
):
    """Le cas réel : une archive servie par Groq seul, un providers.yaml devenu ambigu depuis."""
    d = _execution(tmp_path / "exec", ["groq_qwen_key1"] * 3)
    assert experiences.fournisseur_execute(d) == "groq"
    # …alors que la définition seule ne peut que constater l'ambiguïté.
    assert experiences.fournisseur_de(
        {"type": "passerelle", "modele": "qwen/qwen3.8-27b"}
    ).startswith(experiences.MARQUE_AMBIGU)


def test_D7_une_execution_qui_a_change_de_bord_le_montre(tmp_path, providers):
    """Un mélange ne se masque pas : c'est exactement ce qu'on cherche à voir."""
    d = _execution(tmp_path / "exec", ["groq_qwen_key1", "lmstudio_qwen_key1"])
    assert experiences.fournisseur_execute(d) == "groq · local"
    # Décisions sans fournisseur (choix unique, sans solution) : on ne sait pas, on le dit.
    vide = tmp_path / "vide"
    vide.mkdir()
    (vide / "decisions.jsonl").write_text(
        json.dumps({"methode": "choix_unique"}) + "\n", encoding="utf-8"
    )
    assert experiences.fournisseur_execute(vide) is None
    assert experiences.fournisseur_execute(tmp_path / "inexistant") is None


def test_D7b_une_instance_disparue_reste_lisible(tmp_path, providers):
    """Une archive doit se lire même quand l'instance qui l'a servie n'est plus déclarée."""
    d = _execution(tmp_path / "exec", ["groq_modele_retire_key1", "lmstudio_vieux_key1"])
    assert experiences.fournisseur_execute(d) == "groq · local"
