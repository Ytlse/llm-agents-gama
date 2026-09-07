"""Ticket 035 — une requête peut désigner sa variante de prompt système (`parameters.prompt_variant`)."""

import pytest

from mobility_llm import build_prompt_manager


@pytest.fixture(scope="module")
def pm():
    return build_prompt_manager()


def test_variante_designee_remplace_l_active(pm):
    actif = pm.get_system_prompt("itinary_multi_agent")
    minimal = pm.get_system_prompt("itinary_multi_agent", "b_min")
    assert actif and minimal and minimal != actif and len(minimal) < len(actif)
    assert "b_min" in pm.variantes()


def test_variante_inconnue_refusee(pm):
    with pytest.raises(ValueError, match="introuvable"):
        pm.get_system_prompt("itinary_multi_agent", "n_existe_pas")


def test_render_utilise_la_variante_de_la_requete(pm):
    from mobility_llm.persona import AgentSpec
    agent = AgentSpec(agent_id="a1", perception="p", destination="work", trajectories=[{"index": 0, "mode": "car", "description": "d"}])
    msgs_actif = pm.render("itinary_multi_agent", [agent], {})
    msgs_min = pm.render("itinary_multi_agent", [agent], {"prompt_variant": "b_min"})
    systeme = lambda msgs: next(m.content for m in msgs if m.role == "system")
    assert systeme(msgs_min) != systeme(msgs_actif)
    assert pm.get_system_prompt("itinary_multi_agent", "b_min").split("\n")[0] in systeme(msgs_min)


def test_minimal_persona_rend_systeme_et_utilisateur(pm):
    """Le prompt système de la variante ET le bloc utilisateur (persona, options) partent ensemble."""
    from mobility_llm.persona import AgentSpec
    agent = AgentSpec(agent_id="418", perception="Femme de 34 ans, cadre, sans voiture, abonnée TC.", destination="work",
                      trajectories=[{"index": 0, "mode": "foot", "description": "Marche 25 min"}, {"index": 1, "mode": "bus", "description": "Bus L1 12 min"}])
    msgs = pm.render("itinary_multi_agent", [agent], {"prompt_variant": "minimal_persona"})
    roles = [m.role for m in msgs]
    assert roles == ["system", "user"], roles
    systeme, utilisateur = msgs[0].content, msgs[1].content
    assert "en tenant compte du persona" in systeme and "N'élimine aucune option" in systeme
    assert "Schéma JSON attendu" not in systeme.split("\n")[0] and '"probabilities"' in systeme   # le schéma vient du gabarit, pas du texte collé
    assert "agent_id=418" in utilisateur and "Femme de 34 ans" in utilisateur and "[0] foot" in utilisateur and "[1] bus" in utilisateur
