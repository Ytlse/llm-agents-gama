"""Quel MODÈLE a produit une réponse — ticket 095, lot E.

`TaskResult.provider_used` porte le nom d'une **instance** de passerelle
(`google_gemini31_key1`), pas celui d'un modèle. Une décision lue dans `app.log` ne disait donc
pas quel modèle l'avait produite, et il fallait recouper `llm_exchanges.jsonl` pour l'établir —
c'est-à-dire ouvrir un second fichier pour répondre à une question de première importance quand
on reconstitue une exécution après coup.

Le modèle se DÉRIVE de l'instance : `providers.yaml` déclare un `default_model` par instance, et
la passerelle ne le surcharge pas par requête. C'est déjà ainsi que `identite_run` compose les
modèles admis d'un run. Aucun champ nouveau ne traverse la passerelle.

⚠ Une instance inconnue rend `"?"` et ne lève JAMAIS : une journalisation ne doit pas faire
tomber une décision qui a abouti.
"""

from __future__ import annotations

from settings import settings

INCONNU = "?"


def modele_de_instance(instance: str | None) -> str:
    """Le modèle servi par cette instance de passerelle, ou `?`."""
    if not instance:
        return INCONNU
    try:
        fournisseurs = getattr(settings.llm, "providers", {}) or {}
        cfg = fournisseurs.get(str(instance))
        modele = getattr(cfg, "default_model", None) if cfg is not None else None
        return str(modele) if modele else INCONNU
    except Exception:  # noqa: BLE001 — jamais au prix de l'appel qu'on journalise
        return INCONNU


def origine(instance: str | None) -> str:
    """`instance/modèle`, prêt à coller dans une ligne de journal."""
    return f"{instance or INCONNU}/{modele_de_instance(instance)}"
