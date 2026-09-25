"""La chaîne de nuit reconnaît un bras suspendu et le réessaie (2026-09-25).

Le 25/09 à 18h52, le bras traité d'a13 s'est suspendu sur un épisode de HTTP 503 (code 7). La
chaîne l'a classé « en échec » : elle passait par `make`, qui rend 2 pour toute recette en
échec, et le code 7 n'arrivait jamais jusqu'à elle. Ces tests jouent le vrai script avec un
faux orchestrateur, qui se suspend d'abord puis termine.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "experiment" / "enchainer_experiences_memoire.sh"
EXP = "exp_mem_test_suspension"

FAUX_ORCHESTRATEUR = """
import json, sys
from pathlib import Path
racine = Path.cwd()
compteur = racine / "appels.txt"
n = int(compteur.read_text()) + 1 if compteur.exists() else 1
compteur.write_text(str(n))
codes = [int(c) for c in (racine / "codes.txt").read_text().split()]
code = codes[min(n, len(codes)) - 1]
if code == 7:
    courant = racine / "experiments" / "current"
    courant.mkdir(parents=True, exist_ok=True)
    (courant / "en_attente_quota.json").write_text(json.dumps(
        {"motif": (racine / "motif.txt").read_text().strip(), "resume_at": "2026-09-25T16:52:47",
         "jour_simule": 4}))
print("argv", sys.argv[1:])
sys.exit(code)
"""


def _une_campagne_tourne() -> bool:
    return subprocess.run(
        ["pgrep", "-f", "orchestrateur_memoire.py|run_sequential_cohort.py"], capture_output=True,
        check=False,
    ).returncode == 0


def _jouer(tmp_path: Path, codes: list[int], motif: str = "surcharge_fournisseur") -> str:
    if _une_campagne_tourne():
        pytest.skip("une campagne tourne : le script refuserait de démarrer")
    (tmp_path / "data" / "experiences_memoire" / EXP).mkdir(parents=True)
    (tmp_path / "data" / "experiences_memoire" / EXP / "experience_memoire.yaml").write_text("nom: x\n")
    (tmp_path / "experiments").mkdir()
    (tmp_path / "codes.txt").write_text(" ".join(map(str, codes)))
    (tmp_path / "motif.txt").write_text(motif)
    faux = tmp_path / "faux_orchestrateur.py"
    faux.write_text(FAUX_ORCHESTRATEUR)
    env = {**os.environ, "RACINE": str(tmp_path), "PYTHON": sys.executable,
           "ORCHESTRATEUR": str(faux), "ATTENTE_S": "0", "ESSAIS_MAX": "3"}
    subprocess.run(["bash", str(SCRIPT), EXP], env=env, check=True, capture_output=True, timeout=60)
    (journal,) = (tmp_path / "experiments").glob("enchainement_nuit_*.log")
    return journal.read_text(encoding="utf-8")


def test_un_bras_suspendu_par_un_503_est_reessaye_puis_termine(tmp_path):
    journal = _jouer(tmp_path, [7, 0])
    assert "suspendue" in journal and "motif=surcharge_fournisseur" in journal
    assert "ÉCHEC" not in journal
    assert "TERMINÉE" in journal
    assert (tmp_path / "appels.txt").read_text() == "2", "un seul nouvel essai"


def test_l_orchestrateur_recoit_le_nom_de_l_experience(tmp_path):
    _jouer(tmp_path, [0])
    detail = next((tmp_path / "experiments").glob("enchainement_nuit_*.detail.txt"))
    assert f"'--experience', '{EXP}'" in detail.read_text(encoding="utf-8")


def test_un_quota_epuise_passe_a_la_suite_sans_reessayer(tmp_path):
    journal = _jouer(tmp_path, [7, 0], motif="quota_journalier")
    assert "quota du jour épuisé" in journal
    assert (tmp_path / "appels.txt").read_text() == "1"


def test_un_vrai_echec_reste_un_echec(tmp_path):
    journal = _jouer(tmp_path, [1])
    assert "ÉCHEC (code 1)" in journal


def test_le_script_n_appelle_plus_make():
    """`make` rend 2 pour toute recette en échec : le code 7 s'y perdrait."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "make experience-memoire-lancer EXP" not in source.split("set -u", 1)[1]
