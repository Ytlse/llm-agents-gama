"""Ticket 095, lot C — un modèle par fonction.

Contrat : `specs/ticket_095/tests.md`, section H.

Les 751 requêtes de la campagne du ticket 077 sont toutes parties sur la même famille de
modèles : la plomberie acceptait déjà une liste blanche par appel, mais l'appelant lisait une
liste globale unique. Décision et réflexion STM consomment 46 % des jetons d'entrée chacune, et
se disputaient la même clé.

⚠ Ce n'est PAS un réglage d'infrastructure. Changer le modèle des réflexions change le contenu
de la mémoire, donc les décisions. Le binding entre dans l'identité du run et se gèle avant la
campagne — sinon l'écart mesuré n'est plus attribuable au choc.
"""

import ast
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from settings import settings
from urban_mobility_agents.utils import identite_run, routage

RACINE = Path(__file__).resolve().parents[1]
AGENT = RACINE / "urban_mobility_agents" / "agents" / "llm_agent.py"


@pytest.fixture(autouse=True)
def _propre():
    routage.reinitialiser()
    yield
    routage.reinitialiser()


@pytest.fixture
def admises(monkeypatch):
    def _poser(valeur):
        monkeypatch.setattr(settings.llm, "instances_admises", valeur, raising=False)
    return _poser


@pytest.fixture
def journal_logs():
    lignes: list[tuple[str, str]] = []
    sink = logger.add(
        lambda m: lignes.append((m.record["level"].name, m.record["message"])), level="INFO"
    )
    yield lignes
    logger.remove(sink)


# ══════════════════════ H — le routage ══════════════════════════════════════════


def test_H1_une_liste_plate_se_comporte_comme_avant(admises):
    """H1 — toutes les catégories la reçoivent : aucune campagne existante ne bouge."""
    admises(["a", "b"])
    for categorie in ("itinary_multi_agent", "stm_reflection", "ltm_self_reflection", "autre"):
        assert routage.instances_pour(categorie) == ["a", "b"]


def test_H2_une_table_route_chaque_appel(admises):
    """H2 — les deux moitiés du run cessent de se disputer la même clé."""
    admises({
        "defaut": ["a", "b"],
        "stm_reflection": ["c", "d"],
        "enquete_affinite": ["c", "d"],
    })
    assert routage.instances_pour("itinary_multi_agent") == ["a", "b"]
    assert routage.instances_pour("stm_reflection") == ["c", "d"]
    assert routage.instances_pour("enquete_affinite") == ["c", "d"]


def test_H3_une_categorie_absente_retombe_sur_le_defaut(admises):
    """H3 — jamais sur rien : un repli sur la liste vide lèverait la restriction au moment
    précis où on croit l'avoir resserrée."""
    admises({"defaut": ["a", "b"], "stm_reflection": ["c", "d"]})
    assert routage.instances_pour("ltm_self_reflection") == ["a", "b"]
    assert routage.instances_pour(None) == ["a", "b"]


def test_H4_une_seule_instance_leve_une_alarme(admises, journal_logs):
    """H4 — sans seconde clé, un 503 est un échec sec. Les quatorze `high demand` de la
    campagne sont passés parce qu'il en restait une."""
    admises({"defaut": ["a", "b"], "stm_reflection": ["c"]})
    assert routage.instances_pour("stm_reflection") == ["c"]
    assert [m for n, m in journal_logs if n == "ERROR" and "qu'UNE instance" in m]


def test_H4b_l_alarme_ne_se_repete_pas(admises, journal_logs):
    """H4b — répétée à chaque appel, elle noierait le journal qu'elle doit faire lire."""
    admises({"defaut": ["a"], "stm_reflection": ["c"]})
    for _ in range(5):
        routage.instances_pour("stm_reflection")
    assert len([m for n, m in journal_logs if "qu'UNE instance" in m]) == 1


def test_H5_le_routage_ne_produit_jamais_un_epinglage_dur():
    """H5 — `task_worker` ne retente QUE si `force_provider is None` : un épinglage dur
    supprime le repli, c'est-à-dire exactement ce que la liste blanche cherche à préserver.

    ⚠ Le PARAMÈTRE `force_provider` de `evaluate_and_choose_travel_plan` reste : il sert à la
    plateforme d'expériences (`experiences/decideurs.py`), qui épingle délibérément une instance
    pour comparer des modèles. Ce qui est interdit, c'est que le ROUTAGE du lot C en produise un.
    """
    for fichier in (
        RACINE / "urban_mobility_agents" / "utils" / "routage.py",
        RACINE / "urban_mobility_agents" / "enquetes.py",
    ):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        poses = [
            n for n in ast.walk(arbre)
            if (isinstance(n, ast.keyword) and n.arg == "force_provider")
            or (isinstance(n, ast.Constant) and n.value == "force_provider")
        ]
        assert not poses, f"{fichier.name} pose force_provider : le repli disparaît."

    # Dans l'agent, aucune instruction ne mêle le routage et l'épinglage.
    for ligne in AGENT.read_text(encoding="utf-8").splitlines():
        assert not ("force_provider" in ligne and "instances_pour" in ligne), (
            "le routage par catégorie alimente un épinglage dur : " + ligne.strip()
        )


def test_H6_le_binding_entre_dans_l_identite_du_run(admises):
    """H6 — deux bras aux bindings différents ne portent pas la même identité."""
    admises({"defaut": ["a", "b"], "stm_reflection": ["c", "d"]})
    ident = identite_run.composer(settings, empreinte_choc="aucun")
    assert ident["routage_instances"] == {"defaut": ["a", "b"], "stm_reflection": ["c", "d"]}
    # Et l'union alimente `instances_admises`, d'où se dérivent les modèles admis.
    assert ident["instances_admises"] == ["a", "b", "c", "d"]


def test_H6b_une_table_ne_se_compare_pas_par_ses_cles(admises):
    """H6b — un `sorted()` sur la table rendrait des NOMS DE CATÉGORIES présentés comme des
    noms d'instances : une identité qui ne discrimine plus rien."""
    admises({"defaut": ["a", "b"]})
    ident = identite_run.composer(settings, empreinte_choc="aucun")
    assert "defaut" not in ident["instances_admises"]


def test_H6c_deux_bindings_differents_font_deux_identites(admises):
    """H6c — c'est le refus de reprise qui protège la comparabilité des bras."""
    admises({"defaut": ["a", "b"], "stm_reflection": ["c", "d"]})
    une = identite_run.composer(settings, empreinte_choc="aucun")
    admises({"defaut": ["a", "b"], "stm_reflection": ["e", "f"]})
    autre = identite_run.composer(settings, empreinte_choc="aucun")
    ecarts = identite_run.differences(une, autre)
    assert any("routage" in e for e in ecarts)


def test_H7_une_table_vide_ne_veut_pas_dire_aucune_instance_admise(admises):
    """H7 — « aucune restriction » et « rien n'est admis » ne se confondent pas : l'un laisse
    la cascade choisir, l'autre ferait échouer tous les appels."""
    admises({})
    assert routage.instances_pour("itinary_multi_agent") == []
    admises([])
    assert routage.instances_pour("itinary_multi_agent") == []


def test_H8_le_routage_en_vigueur_se_journalise(admises):
    """H8 — un binding qu'on ne lit nulle part est un binding qu'on découvre après la campagne."""
    admises({"defaut": ["a", "b"], "stm_reflection": ["c", "d"]})
    ligne = routage.journal_du_routage()
    assert "stm_reflection=['c', 'd']" in ligne
    admises([])
    assert "aucune restriction" in routage.journal_du_routage()


# ══════════════════ I — le maillon qui manquait : la variable atteint-elle le run ? ═════════


COMPOSE = RACINE.parents[1] / "infra" / "docker-compose.yml"
COHORTE = RACINE.parents[1] / "scripts" / "experiment" / "run_sequential_cohort.py"
CONFIG_YAML = RACINE / "config" / "config.yaml"


def test_I1_le_compose_declare_la_restriction_en_passe_plat():
    """I1 — posée sur l'hôte et non déclarée ici, la variable n'atteint rien.

    Défaut trouvé le 2026-09-21 en lançant le premier bras : l'orchestrateur posait
    `LLM__INSTANCES_ADMISES` depuis le 2026-09-08, compose ne le déclarait pas, et
    `identite_run.json` portait la valeur de `config.yaml`. La restriction d'un bras ne se
    déclarait pas, elle se subissait.
    """
    texte = COMPOSE.read_text(encoding="utf-8")
    assert re.search(r"^\s*INSTANCES_ADMISES:\s*'\$\{INSTANCES_ADMISES:-", texte, re.M), (
        "infra/docker-compose.yml ne déclare pas INSTANCES_ADMISES en passe-plat"
    )


def test_I2_le_nom_est_le_nom_nu_du_champ():
    """I2 — `INSTANCES_ADMISES`, et surtout PAS `LLM__INSTANCES_ADMISES`.

    Les sous-configurations de `settings.py` sont instanciées sans préfixe : `LLM__…` n'est lu
    par personne. C'est la même erreur que `AGENT__…`, déjà commise et déjà documentée.
    """
    for fichier in (COMPOSE, COHORTE):
        actives = [
            l for l in fichier.read_text(encoding="utf-8").splitlines()
            if "LLM__INSTANCES_ADMISES" in l and not l.strip().startswith("#")
        ]
        assert not actives, (
            f"{fichier.name} pose encore LLM__INSTANCES_ADMISES, qui n'est lu par personne :\n"
            + "\n".join(actives)
        )
    assert 'env["INSTANCES_ADMISES"]' in COHORTE.read_text(encoding="utf-8")


def test_I3_le_yaml_ne_reprend_pas_la_main():
    """I3 — posé dans `config.yaml`, le réglage PRIME sur l'environnement.

    C'est la règle du ticket 077, lot J, et la raison pour laquelle la clé en a été retirée : un
    réglage qui appartient au run ne se redéfinit pas dans le fichier du dépôt.
    """
    import yaml as _yaml

    charge = _yaml.safe_load(CONFIG_YAML.read_text(encoding="utf-8")) or {}
    llm = charge.get("llm") or {}
    assert "instances_admises" not in llm, (
        "config.yaml repose instances_admises : aucune variable d'environnement ne pourra plus "
        "le changer, et les bras d'expérience redeviendront muets."
    )


def test_I4_le_defaut_du_compose_reproduit_ce_que_le_yaml_posait():
    """I4 — retirer la clé du YAML ne doit pas lever la restriction en silence.

    Un `make run` lancé à la main doit continuer de tourner sur les deux mêmes instances
    qu'avant le 2026-09-21.
    """
    texte = COMPOSE.read_text(encoding="utf-8")
    m = re.search(r"^\s*INSTANCES_ADMISES:\s*'\$\{INSTANCES_ADMISES:-(.*?)\}'\s*$", texte, re.M)
    assert m, "défaut de INSTANCES_ADMISES illisible dans le compose"
    import json as _json

    assert _json.loads(m.group(1)) == ["google_gemini31_key1", "google_gemini31_key2"]
