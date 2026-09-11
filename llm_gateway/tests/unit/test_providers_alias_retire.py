"""Aucune instance ne demande un modèle par un alias que le fournisseur a retiré.

Le 2026-09-10, `google_gemini31_key1` demandait `gemini-3.1-flash-lite-preview` : Google
servait `gemini-3.1-flash-lite` SANS erreur, et l'empreinte scellée de chaque mesure
portait donc un nom de modèle qui n'avait pas répondu. Le garde d'exécution
(`_refuser_substitution_de_modele`) le détecte, mais après avoir consommé du quota et au
milieu d'une campagne. Ce test-ci le détecte avant le commit.

`-latest` n'est PAS refusé ici : `mistral-small-latest` est un alias vivant, entretenu par
son fournisseur, et le choisir reste une décision d'usage. Ce qu'on refuse, c'est un alias
NOMMÉMENT connu comme retiré.
"""

from pathlib import Path

import yaml

PROVIDERS_YAML = Path(__file__).resolve().parents[3] / "config" / "llm_gateway" / "providers.yaml"

# Alias dont on a CONSTATÉ qu'ils sont servis par un autre modèle. Ajouter une entrée
# ici à chaque substitution observée — c'est le seul registre du dépôt.
ALIAS_RETIRES = {
    "gemini-3.1-flash-lite-preview": "gemini-3.1-flash-lite",
}


def test_le_fichier_de_providers_est_bien_la():
    """Sans ce garde, une erreur de chemin rendrait le test suivant vert à vide."""
    assert PROVIDERS_YAML.is_file(), PROVIDERS_YAML


def test_aucune_instance_ne_demande_un_alias_retire():
    providers = yaml.safe_load(PROVIDERS_YAML.read_text(encoding="utf-8"))["providers"]
    assert providers, "providers.yaml lu vide : le test ne vérifierait rien"
    fautives = {
        nom: cfg["default_model"]
        for nom, cfg in providers.items()
        if (cfg or {}).get("default_model") in ALIAS_RETIRES
    }
    assert not fautives, (
        f"instances demandant un alias retiré : {fautives}. Le fournisseur sert le "
        f"successeur en silence et la mesure porte un nom faux. Remplacez par "
        f"{ {k: v for k, v in ALIAS_RETIRES.items()} }.")
