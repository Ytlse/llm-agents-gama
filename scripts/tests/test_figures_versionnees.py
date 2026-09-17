"""Une figure régénérée dans un dossier versionné doit l'annoncer (ticket 039, pas 6).

`plot_experiences.py` et `plot_familles.py` écrivent PAR DÉFAUT dans `docs/paper/figures/`,
qui est suivi par git. Chaque régénération commitée ajoute un blob de plus, définitivement.
L'avertissement ne bloque rien : il rend visible, au moment de l'écriture, un coût qui ne se
voit sinon qu'au `git status` — ou jamais.
"""

import logging
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.analysis.figures_versionnees import signaler


def test_une_figure_hors_git_ne_declenche_rien(tmp_path, caplog):
    figure = tmp_path / "exploration.png"
    figure.write_bytes(b"x" * 1024)
    with caplog.at_level(logging.INFO, logger="figures"):
        signaler([figure])
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("Figure écrite" in r.message for r in caplog.records), \
        "le succès se journalise aussi, pas seulement l'anomalie"


def test_une_figure_suivie_par_git_avertit_et_chiffre(caplog):
    suivie = RACINE / "docs" / "paper" / "figures" / "comparaison_experiences.png"
    if not suivie.is_file():
        import pytest
        pytest.skip("figure de référence absente du disque")
    with caplog.at_level(logging.INFO, logger="figures"):
        signaler([suivie])
    alertes = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(alertes) == 1, "une figure versionnée écrasée doit avertir une fois"
    # Le message doit porter de quoi AGIR : un poids et l'échappatoire.
    assert "Ko" in alertes[0].getMessage()
    assert "--sortie" in alertes[0].getMessage()


def test_git_indisponible_ne_fait_pas_echouer(tmp_path, monkeypatch, caplog):
    """Fail-open : un avertissement perdu vaut mieux qu'une figure non produite."""
    import subprocess

    from scripts.analysis import figures_versionnees

    def tombe(*a, **k):
        raise OSError("git introuvable")

    monkeypatch.setattr(subprocess, "run", tombe)
    figure = tmp_path / "f.png"
    figure.write_bytes(b"x")
    with caplog.at_level(logging.INFO, logger="figures"):
        figures_versionnees.signaler([figure])  # ne doit pas lever
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_les_generateurs_ecrivent_par_defaut_dans_un_dossier_versionne():
    """Le garde-fou n'a de sens que tant que c'est vrai : si la sortie par défaut quitte
    `docs/paper/figures/`, ce test rougit et la règle du pas 6 est à revoir."""
    for module in ("plot_experiences", "plot_familles"):
        source = (RACINE / "scripts" / "analysis" / f"{module}.py").read_text(encoding="utf-8")
        assert '"docs" / "paper" / "figures"' in source, f"{module} : sortie par défaut déplacée"
        assert "signaler(ecrits)" in source, f"{module} : avertissement débranché"
