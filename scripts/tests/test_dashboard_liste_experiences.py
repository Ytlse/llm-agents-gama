"""« S'inspirer d'une expérience existante » : de la plus récemment utilisée à la moins récente.

L'ordre alphabétique mettait en tête des expériences oubliées depuis des semaines, alors que ce
sélecteur sert d'abord à repartir de ce qu'on vient de faire. Le critère est la dernière
ÉCRITURE d'un `etat.json`, pas le nom du dossier d'exécution : celui-ci porte l'heure de
CRÉATION, si bien qu'une exécution ouverte le matin et reprise le soir passerait pour vieille.
"""

import os
import sys
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.dashboard import experiences  # noqa: E402


def _experience(racine: Path, nom: str, executions: dict[str, float] | None = None) -> Path:
    d = racine / nom
    d.mkdir(parents=True)
    (d / "experience.yaml").write_text(yaml.safe_dump({"nom": nom}), encoding="utf-8")
    for exec_nom, quand in (executions or {}).items():
        e = d / "executions" / exec_nom
        e.mkdir(parents=True)
        etat = e / "etat.json"
        etat.write_text('{"etat": "terminee"}', encoding="utf-8")
        os.utime(etat, (quand, quand))
    return d


def test_la_plus_recemment_utilisee_vient_en_tete(monkeypatch, tmp_path):
    _experience(tmp_path, "a_vieille", {"2026-09-08_09_00_00": 1_000.0})
    _experience(tmp_path, "z_recente", {"2026-09-08_08_00_00": 9_000.0})
    monkeypatch.setattr(experiences, "DOSSIER", tmp_path)
    assert list(experiences.experiences()) == ["z_recente", "a_vieille"]


def test_une_execution_reprise_compte_comme_recente(monkeypatch, tmp_path):
    """Le dossier porte l'heure de création ; c'est l'état réécrit à la reprise qui date l'usage."""
    _experience(tmp_path, "ouverte_le_matin_reprise_ce_soir", {"2026-09-08_08_00_00": 9_000.0})
    _experience(tmp_path, "ouverte_a_midi_jamais_reprise", {"2026-09-08_12_00_00": 2_000.0})
    monkeypatch.setattr(experiences, "DOSSIER", tmp_path)
    assert list(experiences.experiences())[0] == "ouverte_le_matin_reprise_ce_soir"


def test_les_jamais_utilisees_ferment_la_liste_par_ordre_alphabetique(monkeypatch, tmp_path):
    _experience(tmp_path, "b_jamais")
    _experience(tmp_path, "a_jamais")
    _experience(tmp_path, "m_utilisee", {"2026-09-08_10_00_00": 5_000.0})
    monkeypatch.setattr(experiences, "DOSSIER", tmp_path)
    assert list(experiences.experiences()) == ["m_utilisee", "a_jamais", "b_jamais"]


def test_une_experience_sans_execution_ni_dossier_ne_casse_rien(monkeypatch, tmp_path):
    d = _experience(tmp_path, "sans_dossier_executions")
    monkeypatch.setattr(experiences, "DOSSIER", tmp_path)
    assert experiences.derniere_utilisation(d) == 0.0
    assert list(experiences.experiences()) == ["sans_dossier_executions"]


def test_une_execution_sans_etat_lisible_retombe_sur_son_dossier(monkeypatch, tmp_path):
    d = _experience(tmp_path, "etat_absent")
    (d / "executions" / "2026-09-08_10_00_00").mkdir(parents=True)
    monkeypatch.setattr(experiences, "DOSSIER", tmp_path)
    assert experiences.derniere_utilisation(d) > 0.0, "le dossier fait foi quand l'état manque"


def test_le_dossier_des_experiences_absent_rend_une_liste_vide(monkeypatch, tmp_path):
    monkeypatch.setattr(experiences, "DOSSIER", tmp_path / "nexiste-pas")
    assert experiences.experiences() == {}
