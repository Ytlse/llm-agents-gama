"""Ticket 035, spec parallelisation_experiences — ordonnanceur (R2b/R2c/R2d).

`tour()` est testé avec ses effets injectés (aucun Docker) : on vérifie qu'il réconcilie puis
promeut en FIFO les expériences dont les clés sont libres, et qu'il relance chaque promue.
"""

from __future__ import annotations

import pytest

from experiences import ordonnanceur as O
from experiences import reservations as R
from experiences.archive import Execution


@pytest.fixture
def experiences_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIENCES_DIR", str(tmp_path))
    return tmp_path


def _execution(experiences_dir, nom):
    return Execution.creer(
        experiences_dir / nom,
        experience={"nom": nom},
        empreintes={},
        regime_demande={},
        sources_alea={},
    )


def test_R2b_tour_promeut_les_pretes_en_fifo(experiences_dir):
    a = _execution(experiences_dir, "A")
    b = _execution(experiences_dir, "B")
    c = _execution(experiences_dir, "C")
    # A tient `google` ; B puis C attendent la MÊME clé.
    assert R.admettre({"google"}, a.dossier, "A") == "lance"
    assert R.admettre({"google"}, b.dossier, "B") == "file"
    assert R.admettre({"google"}, c.dossier, "C") == "file"

    relances: list[str] = []
    reconciliations = {"n": 0}

    def faux_reconcilieur():
        reconciliations["n"] += 1

    def faux_lanceur(entree):
        relances.append(entree["exp"])

    # Clé occupée par A : rien n'est promu (R2c, pas de préemption).
    assert O.tour(reconcilieur=faux_reconcilieur, lanceur=faux_lanceur) == []
    assert reconciliations["n"] == 1
    assert [e["exp"] for e in R.lister_file()] == ["B", "C"]

    # A libère `google`. Le faux lanceur ne réserve pas ; on vérifie l'ordre FIFO sur deux tours :
    # B d'abord, puis C.
    R.liberer(a.dossier)
    assert O.tour(reconcilieur=faux_reconcilieur, lanceur=faux_lanceur) == ["B"]
    assert O.tour(reconcilieur=faux_reconcilieur, lanceur=faux_lanceur) == ["C"]
    assert relances == ["B", "C"]
    assert R.lister_file() == []


def test_argv_lancer_reporte_les_options():
    entree = {"exp": "Exp", "args": {"reprendre": True, "accepter_perime": True}}
    argv = O._argv_lancer(entree)
    i = argv.index("lancer")
    assert argv[i : i + 3] == ["lancer", "--experience", "Exp"]
    assert "--reprendre" in argv
    assert "--accepter-perime" in argv
    assert "--attendre-fenetre" not in argv
