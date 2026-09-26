"""Rejeu à prompt exact entre les deux bras d'un A/B mémoire — côté orchestration (2026-09-25).

La passerelle ressert au témoin la réponse du traité quand le prompt est identique mot pour mot
(`packages/llm_gateway/tests/integration/test_rejeu_ab.py`). Ici : l'espace est le même pour les
deux bras, un traité qui repart de zéro ne rejoue pas une tentative précédente, le réglage
atteint le conteneur et son identité, et le bilan dénonce un appel payé avant l'événement.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for chemin in (REPO_ROOT, REPO_ROOT / "services" / "llm-agents"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

from experiences import rejeu_ab  # noqa: E402
from scripts.experiment import orchestrateur_memoire as O  # noqa: E402
from scripts.experiment import run_sequential_cohort as C  # noqa: E402

NOM = "exp_mem_presse_a13_punaises_gem31flite_pop_2_foyers_12j_foyer"


def _echange(provider: str, jour: str, categorie: str = "itinary_multi_agent", agent: str = "1") -> dict:
    return {"provider": provider, "sim_day": jour, "category": categorie,
            "response": [{"agent_id": agent}], "messages": []}


# ── L'espace ─────────────────────────────────────────────────────────────────────────────


def test_l_espace_est_le_nom_de_l_experience_et_le_meme_pour_les_deux_bras():
    assert O.espace_rejeu(NOM, {"rejeu_ab": True}) == NOM
    assert O.espace_rejeu(NOM, {}) is None, "une déclaration sans la clé tourne sans rejeu"


def test_une_experience_neuve_rejoue_par_defaut():
    from experiences import memoire

    assert memoire.defauts()["rejeu_ab"] is True


def test_le_reglage_est_verifie_dans_l_identite_du_run():
    """Un conteneur qui ne l'a pas reçu paierait tout le témoin sans le dire."""
    assert C.reglages_attendus({"REJEU_AB": NOM})["rejeu_ab"] == NOM
    from urban_mobility_agents.utils import identite_run as I

    assert "rejeu_ab" not in I.LIBELLES, "hors comparaison de reprise : un run ancien reste reprenable"


def test_le_client_de_l_agent_pose_l_espace():
    source = (REPO_ROOT / "services/llm-agents/urban_mobility_agents/agents/llm_agent.py").read_text()
    assert "espace_rejeu=settings.llm.rejeu_ab or None" in source


# ── Le traité qui repart de zéro ─────────────────────────────────────────────────────────


def test_un_magasin_perime_est_mis_de_cote_pas_efface(tmp_path, monkeypatch):
    monkeypatch.setattr(O, "RACINE_REJEU", tmp_path)
    (tmp_path / NOM).mkdir()
    (tmp_path / NOM / "abc.json").write_text("{}")
    cible = O.mettre_de_cote_magasin(NOM)
    assert cible is not None and (cible / "abc.json").is_file(), "les réponses payées sont gardées"
    assert not (tmp_path / NOM).exists()
    assert O.mettre_de_cote_magasin(NOM) is None, "rien à faire sans magasin"


# ── Le bilan ─────────────────────────────────────────────────────────────────────────────


def test_un_temoin_entierement_rejoue_avant_l_evenement_est_conforme():
    echanges = [_echange("rejeu_ab:k1", "2026-03-20"), _echange("rejeu_ab:k1", "2026-03-24"),
                _echange("k1", "2026-03-25"), _echange("rejeu_ab:k2", "2026-03-26", "stm_reflection")]
    b = rejeu_ab.bilan(echanges, "2026-03-25")
    assert b["payes_avant_evenement"] == 0
    assert (b["servis"], b["payes"]) == (3, 1)
    assert b["par_categorie"]["stm_reflection"] == {"servis": 1, "payes": 0}


def test_un_appel_paye_avant_l_evenement_est_denonce():
    b = rejeu_ab.bilan([_echange("k1", "2026-03-21", agent="643030")], "2026-03-25")
    assert b["payes_avant_evenement"] == 1
    assert b["premiers_payes_avant"][0] == {"categorie": "itinary_multi_agent", "jour": "2026-03-21",
                                             "agents": ["643030"]}


def test_un_echange_sans_jour_n_est_pas_accuse():
    b = rejeu_ab.bilan([{"provider": "k1", "sim_day": None, "category": "x", "response": []}], "2026-03-25")
    assert b["payes_avant_evenement"] == 0 and b["payes"] == 1


def test_le_prefixe_compare_les_deplacements_pas_seulement_les_appels(tmp_path):
    champs = ["ID Personne", "ID Activité", "Heure de départ", "Mode de transport Choisi"]
    for bras, mode in (("traite", "Vélo"), ("temoin", "Voiture Privée")):
        dossier = tmp_path / bras
        dossier.mkdir()
        with (dossier / "moves.csv").open("w", newline="", encoding="utf-8") as flux:
            writer = csv.DictWriter(flux, fieldnames=champs)
            writer.writeheader()
            writer.writerow({"ID Personne": "1", "ID Activité": "2",
                             "Heure de départ": "2026-03-20T08:00:00", "Mode de transport Choisi": mode})
    bilan = O.verifier_prefixe_deplacements(tmp_path, "2026-03-25")
    assert bilan["conforme"] is False
    assert bilan["cles_divergentes"] == 1


def test_la_date_de_l_evenement_est_la_premiere_injection(tmp_path):
    f = tmp_path / "evenements.jsonl"
    f.write_text("\n".join(json.dumps({"horodatage_simule": h}) for h in
                           ["2026-03-26T07:00:00", "2026-03-25T07:00:00"]))
    assert rejeu_ab.date_premiere_injection(f) == "2026-03-25"
    assert rejeu_ab.date_premiere_injection(tmp_path / "absent.jsonl") is None


def test_le_controle_lit_le_journal_du_temoin_par_le_manifeste(tmp_path, monkeypatch):
    archive = tmp_path / "archive" / "2026-09-26_09_00"
    archive.mkdir(parents=True)
    (archive / "llm_exchanges.jsonl").write_text(
        "\n".join(json.dumps({**e, "origine": archive.name}, indent=2) for e in
                  [_echange("rejeu_ab:k1", "2026-03-20"), _echange("k1", "2026-03-27")]) + "\n")
    runs = tmp_path / "experiments" / "runs" / f"{NOM}_control"
    runs.mkdir(parents=True)
    (runs / "manifeste.json").write_text(json.dumps([{"branche": "control", "archive": str(archive)}]))
    racine_bras = tmp_path / "exp"
    (racine_bras / "traite").mkdir(parents=True)
    (racine_bras / "traite" / "evenements.jsonl").write_text(json.dumps({"horodatage_simule": "2026-03-25T07:00:00"}))
    monkeypatch.setattr(O, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(O, "RACINE_REJEU", tmp_path / "rejeu_ab")
    b = O.controler_rejeu(NOM, racine_bras)
    assert b["payes_avant_evenement"] == 0 and b["servis"] == 1 and b["payes"] == 1
    assert b["date_evenement"] == "2026-03-25"


def test_les_journaux_du_bras_ecartent_les_autres_clients(tmp_path):
    archive, cible = tmp_path / "archive" / "run_a", tmp_path / "sortie"
    archive.mkdir(parents=True)
    (archive / "llm_exchanges.jsonl").write_text("\n".join(
        json.dumps({**_echange("k", "2026-03-20"), "origine": origine}, indent=2)
        for origine in ("run_a", "run_b")) + "\n")
    (archive / "llm_errors.jsonl").write_text("\n".join(
        json.dumps({"task_id": origine, "origine": origine}) for origine in
        ("run_a", "run_b", None)) + "\n")
    bilan = O.isoler_journaux(archive, cible, "run_a")
    assert bilan == {"echanges": 1, "erreurs": 1, "erreurs_sans_origine": 1}
    assert {e["origine"] for e in rejeu_ab.lire_echanges(cible / "llm_exchanges.jsonl")} == {"run_a"}
    assert [json.loads(l)["origine"] for l in (cible / "llm_errors.jsonl").read_text().splitlines()] == ["run_a"]


def test_sans_journal_le_controle_le_dit(tmp_path, monkeypatch):
    monkeypatch.setattr(O, "REPO_ROOT", tmp_path)
    assert O.controler_rejeu(NOM, tmp_path) is None
