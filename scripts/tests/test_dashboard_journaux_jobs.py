"""Un job n'écrit jamais dans le journal d'un autre (onglet « Activités en cours »).

Le registre de jobs vit dans `st.cache_resource` : un redémarrage du serveur Streamlit le
remet à neuf, alors que les jobs qu'il a lancés sont DÉTACHÉS et continuent d'écrire. Le
compteur repartait de 1, si bien qu'un nouveau `001-root-experience-lancer` rouvrait en
ÉCRITURE le journal d'un `001-root-experience-lancer` d'une session précédente encore vivant.
Les deux poignées écrivaient dans le même fichier, chacune à son décalage : le 2026-09-08, la
console d'un job « meta/muse-glimmer » affichait la fin d'une course Gemini.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.dashboard import runner  # noqa: E402


def test_le_compteur_repart_du_dernier_journal_ecrit(tmp_path):
    for nom in ("001-root-jeu.log", "007-root-experience-lancer.log", "013-root-up-services.log"):
        (tmp_path / nom).write_text("", encoding="utf-8")
    assert runner.dernier_index(tmp_path) == 13


def test_un_dossier_vide_ou_absent_repart_de_zero(tmp_path):
    assert runner.dernier_index(tmp_path) == 0
    assert runner.dernier_index(tmp_path / "nexiste-pas") == 0


def test_les_noms_sans_index_sont_ignores(tmp_path):
    (tmp_path / "app.log").write_text("", encoding="utf-8")
    (tmp_path / "trace-2026.log").write_text("", encoding="utf-8")
    assert runner.dernier_index(tmp_path) == 0


def test_au_dela_de_999_l_index_reste_lisible(tmp_path):
    (tmp_path / "1042-root-experience-lancer.log").write_text("", encoding="utf-8")
    assert runner.dernier_index(tmp_path) == 1042


def _registre(monkeypatch, dossier: Path) -> runner.Registry:
    monkeypatch.setattr(runner, "LOG_DIR", dossier)
    return runner.Registry()


def test_un_nouveau_registre_ne_reprend_pas_les_journaux_existants(monkeypatch, tmp_path):
    """Le cas de la panne : le serveur Streamlit redémarre, le job précédent écrit encore."""
    vivant = tmp_path / "001-root-experience-lancer.log"
    vivant.write_text("sortie du job d'une session precedente, toujours en cours\n", encoding="utf-8")

    registre = _registre(monkeypatch, tmp_path)
    job = registre.launch("root:experience-lancer", ["make", "experience-lancer"], tmp_path)

    assert job.log_path != vivant, "un nouveau job ne doit pas rouvrir le journal d'un autre"
    assert job.id == "002-root-experience-lancer"
    assert "session precedente" in vivant.read_text(encoding="utf-8"), "le journal voisin est intact"
    registre.stop(job.id)


def test_deux_jobs_de_la_meme_cible_ont_des_journaux_distincts(monkeypatch, tmp_path):
    registre = _registre(monkeypatch, tmp_path)
    a = registre.launch("root:experience-lancer", ["make", "experience-lancer"], tmp_path)
    b = registre.launch("root:experience-lancer", ["make", "experience-lancer"], tmp_path)
    assert a.log_path != b.log_path and a.id != b.id
    for j in (a, b):
        registre.stop(j.id)
