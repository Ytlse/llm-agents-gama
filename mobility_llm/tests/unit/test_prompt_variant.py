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


def test_prompt_minimal_rend_systeme_et_utilisateur(pm):
    """Le prompt système de la variante ET le bloc utilisateur (persona, options) partent ensemble."""
    from mobility_llm.persona import AgentSpec
    agent = AgentSpec(agent_id="418", perception="Femme de 34 ans, cadre, sans voiture, abonnée TC.", destination="work",
                      trajectories=[{"index": 0, "mode": "foot", "description": "Marche 25 min"}, {"index": 1, "mode": "bus", "description": "Bus L1 12 min"}])
    msgs = pm.render("itinary_multi_agent", [agent], {"prompt_variant": "prompt_minimal"})
    roles = [m.role for m in msgs]
    assert roles == ["system", "user"], roles
    systeme, utilisateur = msgs[0].content, msgs[1].content
    assert "en tenant compte du persona" in systeme and "N'élimine aucune option" in systeme
    assert "Schéma JSON attendu" not in systeme.split("\n")[0] and '"probabilities"' in systeme   # le schéma vient du gabarit, pas du texte collé
    assert "agent_id=418" in utilisateur and "Femme de 34 ans" in utilisateur and "[0] foot" in utilisateur and "[1] bus" in utilisateur


# ---------------------------------------------------------------------------
# Invalidation d'une variante (specs/hygiene-prompts-et-plateforme-experiences.md §2)


# Les 9 `calibrated_*` ont été retirées du fichier le 2026-09-10 (artefacts temporaires de
# juin, aucune expérience ne les référençait). Les invalidées restantes sont celles-ci.
INVALIDES = ["minimal_persona", "expert_chaine_m7", "expert_gem_3.8_v1"]


@pytest.mark.parametrize("variante", INVALIDES)
def test_variante_invalidee_refusee_au_service(pm, variante):
    """Servir un prompt invalidé est refusé, et le refus nomme la règle enfreinte."""
    from llm_gateway.prompts.engine import VariantePromptInvalide

    with pytest.raises(VariantePromptInvalide) as exc:
        pm.get_system_prompt("itinary_multi_agent", variante)
    assert exc.value.regle
    assert variante in str(exc.value)


def test_variante_invalidee_refusee_au_rendu(pm):
    """Le refus vaut aussi par `render` : c'est le chemin qu'emprunte une requête."""
    from llm_gateway.prompts.engine import VariantePromptInvalide
    from mobility_llm.persona import AgentSpec

    agent = AgentSpec(agent_id="a1", perception="p", destination="work",
                      trajectories=[{"index": 0, "mode": "car", "description": "d"}])
    with pytest.raises(VariantePromptInvalide):
        pm.render("itinary_multi_agent", [agent], {"prompt_variant": "minimal_persona"})


def test_refus_est_une_valueerror(pm):
    """Sous-classe de ValueError : les appelants qui filtraient déjà les variantes le voient."""
    from llm_gateway.prompts.engine import VariantePromptInvalide

    assert issubclass(VariantePromptInvalide, ValueError)
    with pytest.raises(ValueError):
        pm.get_system_prompt("itinary_multi_agent", "minimal_persona")


def test_empreinte_reste_calculable_sur_une_variante_invalidee(pm):
    """Une invalidation ne doit PAS rendre irreproductibles les empreintes déjà scellées."""
    texte = pm.get_system_prompt("itinary_multi_agent", "minimal_persona", verifier_validite=False)
    assert texte and "pourquoi la marche" in texte


def test_variantes_valides_inchangees(pm):
    """Le refus est ciblé : les autres variantes sont servies comme avant."""
    for variante in ("prompt_minimal", "b_min", "expert_chaine", "expert_chaine_m7.1"):
        assert pm.get_system_prompt("itinary_multi_agent", variante)
        assert pm.invalidation(variante) is None


def test_prompt_minimal_ne_nomme_aucun_mode(pm):
    """Famille minimale : rien qui puisse pencher vers un mode (règle M1)."""
    texte = pm.get_system_prompt("itinary_multi_agent", "prompt_minimal").lower()
    for mot in ("marche", "à pied", "vélo", "voiture", "transports collectifs",
                "transports en commun", "bus", "métro", "tram", "train"):
        assert mot not in texte, f"{mot!r} apparaît dans le prompt minimal"


# Famille minimale : `prompt_minimal` est le seul EN SERVICE ; `minimal_persona` déclare la
# famille sous laquelle elle a servi et été jugée (invalidée, donc refusée). Tout le reste est
# expert par `familles.defaut`.
MINIMALES = {"prompt_minimal", "minimal_persona"}


def test_familles_declarees(pm):
    """La famille est déclarée, jamais devinée du nom."""
    for variante in pm.variantes():
        attendue = "minimale" if variante in MINIMALES else "experte"
        assert pm.famille(variante) == attendue, variante


def test_un_seul_minimal_en_service(pm):
    """Le seul prompt minimal servable est `prompt_minimal` : l'autre est invalidé."""
    from llm_gateway.prompts.engine import VariantePromptInvalide

    assert pm.get_system_prompt("itinary_multi_agent", "prompt_minimal")
    with pytest.raises(VariantePromptInvalide):
        pm.get_system_prompt("itinary_multi_agent", "minimal_persona")


def test_mode_strict_arme_et_toutes_les_variantes_auditees(pm):
    """Le garde-fou n'est effectif qu'armé, et il ne l'est qu'une fois le corpus audité."""
    assert pm.exiger_avis_neutralite is True, "le mode strict doit être armé par défaut"
    sans_avis = [v for v in pm.variantes() if pm.etat_neutralite(v)[0] == "absent"]
    assert sans_avis == [], f"variantes sans avis de neutralité : {sans_avis}"


def test_aucun_sceau_perime(pm):
    """Un avis rendu sur un texte qui a bougé depuis ne vaut plus rien : aucun ne doit l'être."""
    perimes = [v for v in pm.variantes() if pm.etat_neutralite(v)[0] == "perime"]
    assert perimes == [], f"avis périmés (texte modifié après audit) : {perimes}"


def test_le_prompt_actif_est_servable(pm):
    """Non-régression cardinale : le prompt actif doit démarrer la plateforme."""
    assert pm.get_system_prompt("itinary_multi_agent")
    pm.check_category("itinary_multi_agent")


def test_seul_prompt_minimal_est_exempt_de_mode(pm):
    """Le prompt de remplacement diffère de l'ancien par la seule consigne n° 4."""
    ancien = pm.get_system_prompt("itinary_multi_agent", "minimal_persona", verifier_validite=False)
    nouveau = pm.get_system_prompt("itinary_multi_agent", "prompt_minimal")
    clause = ", en précisant si c'est le cas pourquoi la marche n'obtient pas la plus forte probabilité"
    assert ancien.replace(clause, "") == nouveau


# ---------------------------------------------------------------------------
# Avis de neutralité rendu par l'agent prompt-auditor (spec hygiène §4.2)


def _pm_sur(tmp_path, entrees: dict, actif="v"):
    """Un PromptManager sur un prompts.yaml jetable, pour isoler l'effet de `_neutralite`."""
    import json

    import yaml

    from llm_gateway.prompts.engine import PromptManager

    tpl = tmp_path / "tpl"
    tpl.mkdir()
    (tpl / "cat.md.j2").write_text(
        "<!-- SYSTEM -->\n{{ system_prompt }}\n<!-- USER -->\nu", encoding="utf-8"
    )
    schemas = tmp_path / "s.json"
    schemas.write_text(json.dumps({"cat": {"type": "object"}}), encoding="utf-8")
    py = tmp_path / "prompts.yaml"
    py.write_text(
        yaml.safe_dump({"active": {"cat": actif}, "prompts": entrees}, allow_unicode=True),
        encoding="utf-8",
    )
    # Mode strict désarmé : ces variantes jetables n'ont pas d'avis, et ce n'est pas
    # l'objet du test. Le test dédié vérifie qu'il est bien armé par défaut.
    return PromptManager(tpl, schemas_file=schemas, prompts_file=py,
                         exiger_avis_neutralite=False)


def _sha(texte: str) -> str:
    import hashlib

    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def test_verdict_non_conforme_refuse(tmp_path):
    from llm_gateway.prompts.engine import AvisNeutraliteManquant

    texte = "consigne"
    pm = _pm_sur(
        tmp_path,
        {
            "v": {
                "content": texte,
                "_neutralite": {
                    "verdict": "non_conforme",
                    "sha256_texte": _sha(texte),
                    "le": "2026-09-10",
                    "constats": [{"regle": "M1", "passage": "la marche"}],
                },
            }
        },
    )
    with pytest.raises(AvisNeutraliteManquant, match="non_conforme"):
        pm.get_system_prompt("cat", "v")
    assert pm.etat_neutralite("v")[0] == "refus"


def test_avis_perime_par_une_retouche_refuse(tmp_path):
    """Le sceau compte autant que le verdict : sinon on valide un texte et on en sert un autre."""
    from llm_gateway.prompts.engine import AvisNeutraliteManquant

    pm = _pm_sur(
        tmp_path,
        {
            "v": {
                "content": "texte RETOUCHÉ après l'avis",
                "_neutralite": {
                    "verdict": "conforme",
                    "sha256_texte": _sha("le texte d'origine"),
                    "le": "2026-09-10",
                },
            }
        },
    )
    with pytest.raises(AvisNeutraliteManquant, match="contenu a changé"):
        pm.get_system_prompt("cat", "v")
    assert pm.etat_neutralite("v")[0] == "perime"


def test_verdict_conforme_passe(tmp_path):
    texte = "consigne neutre"
    pm = _pm_sur(
        tmp_path,
        {"v": {"content": texte, "_neutralite": {"verdict": "conforme", "sha256_texte": _sha(texte)}}},
    )
    assert pm.get_system_prompt("cat", "v") == texte
    assert pm.etat_neutralite("v")[0] == "conforme"


def test_reserve_passe(tmp_path):
    texte = "consigne"
    pm = _pm_sur(
        tmp_path,
        {"v": {"content": texte, "_neutralite": {"verdict": "conforme_avec_reserve", "sha256_texte": _sha(texte)}}},
    )
    assert pm.get_system_prompt("cat", "v") == texte
    assert pm.etat_neutralite("v")[0] == "reserve"


def test_avis_absent_avertit_mais_ne_refuse_pas(tmp_path):
    """Sinon la mise en place de la règle rendait inutilisables les 25 variantes existantes."""
    pm = _pm_sur(tmp_path, {"v": {"content": "consigne"}})
    assert pm.get_system_prompt("cat", "v") == "consigne"
    assert pm.etat_neutralite("v")[0] == "absent"


def test_mode_strict_refuse_un_avis_absent(tmp_path):
    from llm_gateway.prompts.engine import AvisNeutraliteManquant

    pm = _pm_sur(tmp_path, {"v": {"content": "consigne"}})
    pm.exiger_avis_neutralite = True
    with pytest.raises(AvisNeutraliteManquant, match="sans avis de neutralité"):
        pm.get_system_prompt("cat", "v")


def test_empreinte_ignore_l_avis(tmp_path):
    """Comme pour l'invalidation : une empreinte se calcule toujours."""
    pm = _pm_sur(
        tmp_path,
        {"v": {"content": "t", "_neutralite": {"verdict": "non_conforme", "sha256_texte": _sha("t")}}},
    )
    assert pm.get_system_prompt("cat", "v", verifier_validite=False) == "t"


def test_les_25_variantes_du_depot_restent_servies(pm):
    """Non-régression : aucune variante valide du dépôt ne doit être bloquée par la nouveauté."""
    from llm_gateway.prompts.engine import VariantePromptInvalide

    bloquees = []
    for v in pm.variantes():
        try:
            pm.get_system_prompt("itinary_multi_agent", v)
        except VariantePromptInvalide:
            pass  # les trois invalidées, attendu
        except Exception as e:  # noqa: BLE001
            bloquees.append((v, type(e).__name__))
    assert bloquees == []
