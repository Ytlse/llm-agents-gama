"""Ticket 095, lot E — le modèle journalisé par décision.

Contrat : `specs/ticket_095/tests.md`, section G.

Demande du 2026-09-20. `llm_exchanges.jsonl` porte déjà `provider` ; le journal applicatif, non.
Une décision lue dans `app.log` ne disait pas quel modèle l'avait produite, et il fallait
recouper deux fichiers pour l'établir — sur un dispositif où changer le modèle des réflexions
change le contenu de la mémoire, donc les décisions.

Le modèle se DÉRIVE de l'instance servie : `providers.yaml` déclare un `default_model` par
instance et la passerelle ne le surcharge pas par requête. Aucun champ nouveau ne traverse la
passerelle.
"""

import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from urban_mobility_agents.utils.modeles import INCONNU, modele_de_instance, origine

AGENT = Path(__file__).resolve().parents[1] / "urban_mobility_agents" / "agents" / "llm_agent.py"
ENQUETES = Path(__file__).resolve().parents[1] / "urban_mobility_agents" / "enquetes.py"


def test_G3_une_instance_connue_rend_son_modele():
    """G3 — la dérivation est celle d'`identite_run`, pas une table parallèle."""
    from settings import settings

    instance = next(iter(settings.llm.providers), None)
    if instance is None:
        pytest.skip("aucun fournisseur déclaré dans cet environnement")
    assert modele_de_instance(instance) == settings.llm.providers[instance].default_model


def test_G3b_une_instance_inconnue_rend_un_point_d_interrogation_sans_lever():
    """G3b — une journalisation ne doit JAMAIS faire tomber un appel qui a abouti."""
    assert modele_de_instance("instance_qui_n_existe_pas") == INCONNU
    assert modele_de_instance(None) == INCONNU
    assert modele_de_instance("") == INCONNU
    assert origine(None) == f"{INCONNU}/{INCONNU}"


@pytest.mark.parametrize(
    "marqueur,ce_que_c_est",
    [
        ("[decision]", "la décision d'itinéraire"),
        ("[reflexion-stm]", "la réflexion nocturne"),
        ("[auto-reflexion]", "l'auto-réflexion long terme"),
    ],
)
def test_G1_G2_chaque_appel_journalise_son_modele(marqueur, ce_que_c_est):
    """G1 et G2 — les trois appels du run nomment le modèle qui les a servis."""
    source = AGENT.read_text(encoding="utf-8")
    lignes = [l for l in source.splitlines() if marqueur in l and "logger" not in l]
    assert lignes, f"aucune ligne de journal pour {ce_que_c_est}"
    # Le bloc de la ligne doit porter `modele=`.
    debut = source.index(marqueur)
    bloc = source[debut : debut + 600]
    assert "modele=" in bloc, f"{ce_que_c_est} ne journalise pas son modèle"
    assert "origine_modele(" in bloc, (
        f"{ce_que_c_est} n'utilise pas le dérivateur partagé : une seconde table de modèles "
        f"divergerait de la première."
    )


def test_G2b_l_enquete_journalise_aussi_son_modele():
    """G2b — la quatrième catégorie d'appel du run."""
    source = ENQUETES.read_text(encoding="utf-8")
    assert "modele_de_instance" in source
    assert '"model"' in source, "la colonne `model` manque au CSV de l'enquête"


def test_G4_une_decision_servie_par_le_cache_le_dit():
    """G4 — sans quoi le cache se ferait passer pour un appel, et le compte des appels
    économisés se ferait à l'aveugle."""
    source = AGENT.read_text(encoding="utf-8")
    debut = source.index("[decision]")
    bloc = source[debut : debut + 600]
    assert "cache" in bloc and "direct" in bloc


def test_G5_le_derivateur_est_le_seul_endroit_ou_le_modele_se_lit():
    """G5 — deux dérivations écrites à deux endroits divergent, comme deux valeurs par défaut."""
    arbre = ast.parse(AGENT.read_text(encoding="utf-8"))
    lectures = [
        n for n in ast.walk(arbre)
        if isinstance(n, ast.Attribute) and n.attr == "default_model"
    ]
    assert not lectures, (
        "llm_agent.py lit `default_model` directement : passer par "
        "`utils.modeles.modele_de_instance`."
    )
