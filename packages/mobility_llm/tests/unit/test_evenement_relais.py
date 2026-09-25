"""Ticket 111, T14 — la catégorie `evenement_relais` : gabarit, schéma, bundle."""

from mobility_llm import CATEGORIES, build_prompt_manager, bundle
from mobility_llm.persona import AgentSpec


def _membres():
    return [
        {"agent_id": "102", "prenom": "Claire", "age": 38, "mineur": False,
         "occupation": "Full-Time Worker", "modes_habituels": ["car"],
         "trajets_du_jour": ["08:00 work", "17:13 home"]},
        {"agent_id": "103", "prenom": "Josette", "age": 9, "mineur": True,
         "occupation": "Pupil", "modes_habituels": [], "trajets_du_jour": ["08:30 education"]},
    ]


def test_la_categorie_est_dans_le_bundle_charge_par_la_passerelle():
    assert "evenement_relais" in CATEGORIES
    assert "evenement_relais" in bundle().categories


def test_les_champs_voyagent_jusqu_au_gabarit():
    """`extra="ignore"` jetterait en silence l'article et les membres sans leur déclaration."""
    spec = AgentSpec(agent_id="101", perception="Arthur, 40", article="Gusts…", membres=_membres())
    assert spec.article == "Gusts…" and spec.membres[1]["mineur"] is True


def test_le_gabarit_se_rend_avec_son_schema():
    pm = build_prompt_manager()
    agents = [AgentSpec(agent_id="101", perception="Arthur, 40, Full-Time Worker",
                        article="(Translated from French)\nGusts above 80 km/h…",
                        membres=_membres())]
    messages = pm.render("evenement_relais", agents, {})
    texte = "\n".join(str(getattr(m, "content", m)) for m in messages)
    assert "--- AGENT 101 ---" in texte
    assert "Gusts above 80 km/h" in texte
    assert "agent_id 103 — Josette, 9 (CHILD), Pupil" in texte
    assert "Today's schedule: 08:00 work; 17:13 home" in texte
    assert "decide for the child" in texte
    assert "recipients" in texte and "speaks" in texte
    # Aucun lien de parenté inventé : la population ne porte pas la filiation.
    for interdit in ("your son", "your daughter", "your wife", "your husband"):
        assert interdit not in texte
