"""Ticket 085, lots B et C — une contrainte de run ne vit pas dans un fichier global à la pile.

Contrat : `specs/ticket_085/tests.md`, sections A (côté client), B et C. Les identifiants (B1,
C2…) y renvoient.

Les deux questions auxquelles ces tests répondent :

1. **Une expérience porte-t-elle SA restriction de routage, ou celle du fichier partagé ?** Le
   2026-09-16, une ligne de `config/config.yaml` posée pour un run gemini 3.1 a fait refuser toutes
   les décisions d'un run gemini 3.5 — deux contraintes contradictoires, et le routeur a eu raison
   de refuser. C'était un défaut de PORTÉE, pas de règle.
2. **Un refus dit-il le bon motif ?** « Aucune instance ne sert ce modèle » annoncé juste après
   avoir listé ce modèle parmi les modèles servis, alors que le vrai motif était « le quota du jour
   n'est pas encore renouvelé ».

Aucun réseau : la passerelle n'est jamais jointe, le moniteur est doublé.
"""

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from experiences import archive as A
from experiences import cli as CLI
from experiences import experience as E
from tests.test_035_03_05_06_execution import (  # noqa: F401 — fixtures pytest réutilisées
    _exp,
    banc,
)

RACINE = Path(__file__).resolve().parents[1]

PROVIDERS = {
    "google_gemini31_key1": {"default_model": "gemini-3.1-flash", "adapter": "google"},
    "google_gemini31_key2": {"default_model": "gemini-3.1-flash", "adapter": "google"},
    "google_gemini35_key1": {"default_model": "gemini-3.5-flash-lite", "adapter": "google"},
    "google_gemini35_key2": {"default_model": "gemini-3.5-flash-lite", "adapter": "google"},
    "lmstudio_qwen": {
        "default_model": "gemini-3.5-flash-lite",
        "adapter": "openai_compatible",
        "base_url": "http://localhost:1234/v1",
    },
}


def _moniteur(providers=None, disponibles=None, joignable=True, raison="") -> SimpleNamespace:
    return SimpleNamespace(
        providers=dict(PROVIDERS if providers is None else providers),
        joignable=joignable,
        instances_disponibles=lambda besoin=1: list(disponibles or []),
        raison_epuisement=lambda: raison,
    )


@pytest.fixture
def reglages(monkeypatch):
    """`settings.llm.instances_admises` restauré après chaque test — c'est un singleton."""
    from settings import settings

    monkeypatch.setattr(settings.llm, "instances_admises", [], raising=False)
    return settings


# ══ B. La restriction suit l'expérience ══════════════════════════════════════════════════


def test_B1_la_valeur_du_fichier_natteint_pas_les_requetes(banc, reglages):  # noqa: F811
    """L'incident, en un test : gemini 3.5 lancé pendant que le fichier porte les clés 3.1."""
    reglages.llm.instances_admises = ["google_gemini31_key1", "google_gemini31_key2"]
    exp = _exp(banc, decideur={"type": "passerelle", "modele": "gemini-3.5-flash-lite",
                               "portee": "distant"})

    retenue = CLI.appliquer_instances_admises(exp, _moniteur())

    assert retenue == ["google_gemini35_key1", "google_gemini35_key2"]
    assert reglages.llm.instances_admises == retenue, (
        "la restriction imposée au PROCESSUS est celle de l'expérience, pas celle du fichier"
    )
    assert "google_gemini31_key1" not in reglages.llm.instances_admises


def test_B1_le_seul_lecteur_de_la_restriction_lit_bien_les_reglages_du_processus():
    """`llm_agent.py` est l'unique lecteur : s'il cessait de lire les settings, B1 serait vide.

    Ticket 092 — la restriction n'est plus recopiée sur le payload de décision mais donnée au
    CLIENT à sa construction, seuil unique par lequel sortent AUSSI les réflexions STM et LTM.
    Le maillon gardé ici est le même — des réglages du processus jusqu'à la requête — mais il
    passe désormais par le constructeur. Que les trois catégories la portent effectivement est
    vérifié par `test_092_restriction_sur_tous_les_appels.py`.
    """
    source = (RACINE / "urban_mobility_agents" / "agents" / "llm_agent.py").read_text(
        encoding="utf-8"
    )
    assert "settings.llm.instances_admises" in source
    assert "instances_admises=list(settings.llm.instances_admises or [])" in source, (
        "la restriction doit être remise au client à sa construction : posée appel par appel, "
        "elle avait laissé la consolidation mémoire partir chez un autre modèle (ticket 092)"
    )


def test_B2_la_liste_est_celle_des_instances_servant_le_modele_filtree_par_portee(banc, reglages):  # noqa: F811
    exp = _exp(banc, decideur={"type": "passerelle", "modele": "gemini-3.5-flash-lite",
                               "portee": "distant"})
    assert CLI.appliquer_instances_admises(exp, _moniteur()) == [
        "google_gemini35_key1", "google_gemini35_key2"
    ], "la portée `distant` écarte l'instance LM Studio qui sert le même identifiant de modèle"

    exp_local = _exp(banc, decideur={"type": "passerelle", "modele": "gemini-3.5-flash-lite",
                                     "portee": "local"})
    assert CLI.appliquer_instances_admises(exp_local, _moniteur()) == ["lmstudio_qwen"]


def test_B2_une_instance_sans_quota_reste_admise(banc, reglages):  # noqa: F811
    """La restriction est structurelle, l'arbitrage du quota appartient au moniteur.

    Dériver la liste de `instances_disponibles()` la ferait rétrécir au fil du run : une clé
    momentanément au plafond en sortirait, et n'y rentrerait jamais — le run finirait épinglé sur
    ce qui restait au moment du lancement.
    """
    exp = _exp(banc, decideur={"type": "passerelle", "modele": "gemini-3.5-flash-lite",
                               "portee": "distant"})
    moniteur = _moniteur(disponibles=["google_gemini35_key1"])  # key2 au plafond
    assert CLI.appliquer_instances_admises(exp, moniteur) == [
        "google_gemini35_key1", "google_gemini35_key2"
    ]


def test_B3_lecrasement_dune_valeur_non_vide_est_journalise(banc, reglages, caplog):  # noqa: F811
    from loguru import logger

    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(m), level="WARNING")
    try:
        reglages.llm.instances_admises = ["google_gemini31_key1", "google_gemini31_key2"]
        exp = _exp(banc, decideur={"type": "passerelle", "modele": "gemini-3.5-flash-lite",
                                   "portee": "distant"})
        CLI.appliquer_instances_admises(exp, _moniteur())
    finally:
        logger.remove(sink)

    trace = "\n".join(messages)
    assert "instances_admises" in trace and "ÉCRASÉE" in trace, trace
    assert "google_gemini31_key1" in trace, "l'ANCIENNE liste est nommée"
    assert "google_gemini35_key1" in trace, "la NOUVELLE liste est nommée"


def test_B3_aucun_journal_quand_le_fichier_est_vide(banc, reglages):  # noqa: F811
    from loguru import logger

    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(m), level="WARNING")
    try:
        exp = _exp(banc, decideur={"type": "passerelle", "modele": "gemini-3.5-flash-lite",
                                   "portee": "distant"})
        CLI.appliquer_instances_admises(exp, _moniteur())
    finally:
        logger.remove(sink)
    assert not [m for m in messages if "instances_admises" in m], (
        "rien n'est écrasé : le cas normal ne doit pas bruiter le journal"
    )


def test_B4_la_liste_retenue_entre_dans_execution_yaml(tmp_path):
    dossier = tmp_path / "exp"
    ex = A.Execution.creer(
        dossier, {"nom": "exp"}, {}, regime_demande={}, sources_alea={},
        reglages_herites={"max_trip_candidates": 6},
    )
    ex.noter_reglages_herites(instances_admises=["google_gemini35_key1"])

    sur_disque = yaml.safe_load((ex.dossier / "execution.yaml").read_text(encoding="utf-8"))
    herites = sur_disque["reglages_herites"]
    assert herites["instances_admises"] == ["google_gemini35_key1"]
    assert herites["max_trip_candidates"] == 6, "les réglages déjà consignés ne sont pas perdus"

    rouverte = A.Execution.ouvrir(ex.dossier)
    assert rouverte.config["reglages_herites"]["instances_admises"] == ["google_gemini35_key1"]


def test_B4_la_reprise_reecrit_la_trace(tmp_path):
    """Une mesure archivée dit sous quelle restriction elle a été prise, pas sous quelle elle a
    commencé (Q3 de `specs/ticket_085/questions.md`)."""
    ex = A.Execution.creer(tmp_path / "exp", {"nom": "exp"}, {}, regime_demande={},
                           sources_alea={}, reglages_herites={})
    ex.noter_reglages_herites(instances_admises=["google_gemini35_key1"])
    A.Execution.ouvrir(ex.dossier).noter_reglages_herites(
        instances_admises=["google_gemini35_key1", "google_gemini35_key2"]
    )
    sur_disque = yaml.safe_load((ex.dossier / "execution.yaml").read_text(encoding="utf-8"))
    assert sur_disque["reglages_herites"]["instances_admises"] == [
        "google_gemini35_key1", "google_gemini35_key2"
    ]


def test_B4_cmd_lancer_consigne_la_restriction_dans_les_deux_branches():
    """Création et reprise passent par le même point : il est APRÈS le `if derniere is not None`."""
    source = inspect.getsource(CLI.cmd_lancer)
    assert "appliquer_instances_admises(exp, moniteur)" in source
    assert "execution.noter_reglages_herites(instances_admises=" in source
    assert source.index("execution.noter_reglages_herites") > source.index(
        "execution = Execution.ouvrir(derniere)"
    ), "l'appel doit être en aval des deux branches, sinon la reprise n'est pas tracée"


@pytest.mark.parametrize(
    "decideur",
    [
        {"type": "duree_minimale"},
        {"type": "aleatoire", "graine": 7},
        {"type": "majoritaire_voiture"},
    ],
)
def test_B5_un_decideur_hors_passerelle_nimpose_aucune_restriction(banc, reglages, decideur):  # noqa: F811
    """Y compris quand le fichier en portait une : la restriction suit l'expérience DANS LES DEUX
    SENS. Sans cela, un témoin local hériterait silencieusement de la contrainte d'un autre run."""
    reglages.llm.instances_admises = ["google_gemini31_key1"]
    exp = _exp(banc, decideur=decideur)
    assert CLI.appliquer_instances_admises(exp, None) == []
    assert reglages.llm.instances_admises == []


def test_B6_le_fichier_reste_le_vehicule_de_make_run():
    """`make run` lit `config.yaml` à l'import et n'a aucune injection par run (§ 3 du ticket).

    Le vider ne déplacerait pas la restriction, il la SUPPRIMERAIT — et précisément pour le run de
    soixante jours qui l'avait motivée, sans qu'aucune ligne ne le dise. La clé doit donc rester
    déclarée et lue ; c'est sa valeur, pas sa présence, qui appartient à l'opérateur.
    """
    config = yaml.safe_load((RACINE / "config" / "config.yaml").read_text(encoding="utf-8"))
    assert "instances_admises" in config.get("llm", {}), (
        "le lot B ne vide pas config.yaml : il n'est pas en droit de le faire tant que "
        "`make run` n'a pas son équivalent par run"
    )
    from settings import settings

    assert hasattr(settings.llm, "instances_admises"), (
        "le champ reste lu par le modèle de configuration : sans lui, le fichier serait inerte"
    )


def test_B6_appliquer_nécrit_rien_sur_le_disque(banc, reglages):  # noqa: F811
    chemin = RACINE / "config" / "config.yaml"
    avant = chemin.read_bytes()
    exp = _exp(banc, decideur={"type": "passerelle", "modele": "gemini-3.5-flash-lite",
                               "portee": "distant"})
    CLI.appliquer_instances_admises(exp, _moniteur())
    assert chemin.read_bytes() == avant, (
        "la restriction par run vit EN MÉMOIRE ; réécrire le fichier partagé reproduirait "
        "exactement le défaut qu'on corrige"
    )


# ══ C. Le refus dit le bon motif ═════════════════════════════════════════════════════════


def _refus(banc, *, servantes, disponibles, raison=""):  # noqa: F811
    exp = _exp(banc, decideur={"type": "passerelle", "modele": "gemini-3.5-flash-lite",
                               "portee": "distant"})
    refus, _ = E.refuser_si_impossible(
        exp, banc["jeu"], banc["info"],
        instances_disponibles=disponibles,
        instances_servantes=servantes,
        detail_epuisement=raison,
        dependances={"commit": "abc"}, periodes={},
    )
    return refus


def test_C1_modele_servi_par_personne_message_inchange(banc):  # noqa: F811
    refus = _refus(banc, servantes=[], disponibles=[])
    assert any("aucune instance de passerelle ne sert le modèle" in r for r in refus), refus


def test_C2_modele_servi_mais_epuise_dit_lepuisement_et_les_quotas(banc):  # noqa: F811
    raison = (
        "google_gemini35_key1 : 1000/1000 requêtes/jour (épuisée) ; "
        "google_gemini35_key2 : 1000/1000 requêtes/jour (épuisée)"
    )
    refus = _refus(
        banc,
        servantes=["google_gemini35_key1", "google_gemini35_key2"],
        disponibles=[],
        raison=raison,
    )
    ligne = next(r for r in refus if "épuisées" in r)
    assert "1000/1000 requêtes/jour" in ligne, "le compte par instance est rendu"
    assert "google_gemini35_key1" in ligne and "google_gemini35_key2" in ligne
    assert "renouvellement du quota" in ligne, "le refus dit l'ACTION, pas seulement la raison"


def test_C3_les_deux_motifs_sexcluent(banc):  # noqa: F811
    """Le mot « épuisée » ne peut pas apparaître quand personne ne sert le modèle, et
    réciproquement. C'est la règle : une variable pour deux sens faisait mentir le message."""
    aucun = " ".join(_refus(banc, servantes=[], disponibles=[]))
    assert "épuis" not in aucun, aucun

    epuise = " ".join(
        _refus(banc, servantes=["google_gemini35_key1"], disponibles=[], raison="…")
    )
    assert "aucune instance de passerelle ne sert" not in epuise, epuise


def test_C3_rien_nest_refuse_quand_une_instance_reste_disponible(banc):  # noqa: F811
    refus = _refus(
        banc,
        servantes=["google_gemini35_key1", "google_gemini35_key2"],
        disponibles=["google_gemini35_key1"],
    )
    assert not any("épuis" in r or "ne sert le modèle" in r for r in refus), refus


def test_C4_un_appelant_qui_ne_passe_quune_liste_garde_son_message(banc):  # noqa: F811
    """La séparation des deux sens est ADDITIVE : le code écrit avant ce lot ne bouge pas d'un mot.

    Ces appelants-là (tests d'archive, outils) ne distinguent pas les deux ensembles ; leur unique
    liste vaut les deux à la fois, comme avant.
    """
    exp = _exp(banc, decideur={"type": "passerelle", "modele": "inconnu"})
    refus, _ = E.refuser_si_impossible(
        exp, banc["jeu"], banc["info"], instances_disponibles=[],
        dependances={"commit": "abc"}, periodes={},
    )
    assert any("aucune instance" in r for r in refus)
    assert not any("épuis" in r for r in refus)


def test_C_le_preparateur_ne_confond_plus_les_deux_ensembles():
    """La variable réécrite est la cause racine : deux noms, et elle ne peut plus l'être."""
    source = inspect.getsource(CLI._preparer_lancement)
    assert "servantes" in source and "disponibles" in source
    assert "instances_servantes=servantes" in source
    assert "instances_disponibles=disponibles" in source


# ══ A côté client — la nature de l'échec ═════════════════════════════════════════════════


def test_A6_une_restriction_non_satisfiable_nest_ni_epuisee_ni_occupee():
    """Le seau où l'on range l'échec dit où chercher la panne. Celui-là n'en est pas un."""
    from experiences import decideurs as D

    motif = (
        "Restriction d'instances non satisfiable : fournisseur forcé 'google_gemini35_key1' "
        "hors des instances admises ['google_gemini31_key1', 'google_gemini31_key2'] "
        "[instances admises déclarées : ['google_gemini31_key1'] ; fournisseur épinglé : "
        "google_gemini35_key1] — refus déterministe, aucun rejeu n'est planifié."
    )
    assert not D._RE_OCCUPEE.search(motif), "ce n'est pas une passerelle occupée"
    assert not D._RE_QUOTA.search(motif) and not D._RE_CREDIT.search(motif), "ce n'est pas un quota"

    source = inspect.getsource(D)
    assert 'genre_erreur") == "restriction_instances"' in source
    assert '"configuration: " + erreur' in source


def test_A7_le_comportement_du_runner_face_a_ce_type_est_inchange():
    """Décision du § 9 : ce lot rend le motif juste et rapide, il ne change pas ce que le client
    en fait. `configuration` n'est PAS un type terminal — il tombe dans la branche d'attente, et
    la pause pour immobilité fait le reste, comme pour tout blocage."""
    source = inspect.getsource(
        __import__("experiences.runner", fromlist=["runner"])
    )
    assert 'type_err == "epuise"' in source
    assert "configuration" not in source, (
        "si le runner venait à connaître ce type, Q1 de questions.md aurait été tranchée "
        "autrement — et ce test doit alors être réécrit, pas supprimé"
    )
