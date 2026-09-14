"""Ticket 045, bloc B — une empreinte dit ce qui a été servi.

R5 : `empreinte_gabarit` rend le MÊME sha256 sur l'hôte et dans le conteneur.
R6 : les `sources` énumèrent exactement les morceaux hachés.

Le défaut corrigé ici : le gabarit d'option était cherché sous
`racine_du_dépôt / "services" / "llm-agents" / "text_helper" / …`. Dans le conteneur `controller`,
le dossier `llm-agents` est monté sur `/app` — le fichier est donc en
`/app/text_helper/…`, et l'ancienne résolution le cherchait en `/llm-agents/text_helper/…`.
Introuvable, il sortait du hachage sans bruit : deux empreintes pour un même texte,
`88f0aefcff` sur l'hôte et `9afe7d4a52` dans le conteneur pour `prompt_minimal`. C'est ce
qui a fait croire, le 2026-09-11, que deux bras étiquetés du même prompt n'avaient pas reçu
la même chose.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from experiences.chemins import racine_depot, racine_llm_agents
from experiences.experience import (
    GABARIT_OPTION_REL,
    chemin_gabarit_option,
    empreinte_gabarit,
)

CATEGORIE = "itinary_multi_agent"


def test_r5_racine_llm_agents_porte_le_paquet_experiences():
    """La racine `llm-agents` est le dossier qui contient le paquet `experiences`.

    C'est le seul ancrage vrai des deux côtés : `<dépôt>/llm-agents` sur l'hôte, `/app`
    dans le conteneur. La racine du dépôt, elle, diffère (`<dépôt>` contre `/app`), et
    c'est précisément ce qui cassait la résolution.
    """
    racine = racine_llm_agents()
    assert (racine / "experiences" / "experience.py").is_file()
    assert (racine / "settings.py").is_file()


def test_r5_le_gabarit_option_est_trouve_sous_la_racine_llm_agents():
    """Le gabarit d'option existe, et il est résolu sans passer par la racine du dépôt."""
    chemin = chemin_gabarit_option()
    assert chemin.is_file(), f"gabarit d'option introuvable : {chemin}"
    assert chemin == racine_llm_agents() / GABARIT_OPTION_REL


def test_r5_la_resolution_ne_depend_pas_de_la_racine_du_depot():
    """Le chemin du gabarit ne se déduit PAS de la racine du dépôt.

    Sans quoi le conteneur, dont la racine de dépôt est `/app` et non `<dépôt>`, chercherait
    `/app/llm-agents/text_helper/…` — qui n'existe pas.
    """
    faux = racine_depot() / "services" / "llm-agents" / GABARIT_OPTION_REL
    vrai = chemin_gabarit_option()
    # Sur l'hôte les deux coïncident par accident ; dans le conteneur, non. La règle est que
    # `vrai` existe TOUJOURS, ce que `faux` ne garantit pas.
    assert vrai.is_file()
    if faux != vrai:
        assert not faux.is_file(), (
            "deux chemins concurrents existent : l'ambiguïté demeure"
        )


def test_r6_les_sources_enumerent_exactement_les_morceaux_haches():
    """Chaque source annoncée correspond à un morceau réellement concaténé, et inversement.

    On recompose le hachage à partir des seuls morceaux que `sources` annonce : s'il tombe
    juste, l'empreinte ne cache ni n'invente de morceau.
    """
    from mobility_llm import prompt_manager as get_prompt_manager

    emp = empreinte_gabarit(CATEGORIE, "prompt_minimal_02")
    systeme = (
        get_prompt_manager().get_system_prompt(
            CATEGORIE, "prompt_minimal_02", verifier_validite=False
        )
        or ""
    )
    gabarit = chemin_gabarit_option().read_text(encoding="utf-8")

    assert emp["sources"] == [
        "prompts.yaml:prompt_minimal_02",
        chemin_gabarit_option().name,
    ]
    attendu = hashlib.sha256(f"{systeme}\n\x00\n{gabarit}".encode()).hexdigest()
    assert emp["sha256"] == attendu


def test_r6_une_variante_invalidee_garde_une_empreinte_et_le_dit():
    """L'invalidation s'annonce hors du hachage : une variante valide garde son empreinte d'avant."""
    emp = empreinte_gabarit(CATEGORIE, "prompt_minimal_01")
    assert emp.get("invalide") is True
    assert emp.get("invalide_regle")
    assert len(emp["sha256"]) == 64


def test_r6_le_gabarit_option_manquant_est_une_erreur_pas_un_silence(monkeypatch):
    """Un morceau promis mais absent doit se voir, pas disparaître du hachage.

    C'est le motif « l'absence de mesure passe pour un cas sain » : l'ancienne version
    omettait silencieusement le gabarit introuvable et rendait une empreinte plus courte,
    d'apparence normale.
    """
    import experiences.experience as E

    monkeypatch.setattr(
        E, "chemin_gabarit_option", lambda: Path("/introuvable/absent.j2")
    )
    emp = E.empreinte_gabarit(CATEGORIE, "prompt_minimal_02")
    assert any("introuvable" in s for s in emp["sources"]), emp["sources"]
