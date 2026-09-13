"""La console d'un job reste ouverte quand on l'ouvre (📟 Activités en cours).

Le volet des jobs vit dans un fragment `run_every="2s"`, et l'argument `expanded` d'un
`st.expander` l'emporte à CHAQUE tour. Tant qu'il valait `index == 0`, seule la console du job
le plus récent pouvait rester ouverte : ouvrir celle d'un autre job la refermait deux secondes
plus tard. Cas réel du 2026-09-07 — deux expériences en parallèle, impossible de lire le
journal de la plus ancienne.

Le pli choisi par le lecteur est désormais écrit dans `session_state` (`key` +
`on_change="rerun"`) et relu à chaque tour ; `expanded` n'est plus que le défaut du premier
affichage.
"""

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

SCRIPT = '''
import sys, time
from pathlib import Path
sys.path.insert(0, "__RACINE__")
import streamlit as st
from scripts.dashboard import app, runner

class FauxJob:
    def __init__(self, ident, label):
        self.id, self.label = ident, label
        self.argv, self.cwd = [f"EXP={label}"], Path("__RACINE__")
        self.log_path = Path("__RACINE__") / "experiments" / ".dashboard" / "faux.log"
        self.started_at, self.finished_at = time.time() - 60, None
        self.returncode, self.error, self.flags = None, None, ()
        self.running = True
        self.duration = 60.0
        self.command_line = f"make {label}"
        self.state = "en cours"

# Deux lancements en parallèle, le plus récent en tête (comme `par_priorite`).
for index, job in enumerate([FauxJob("recent", "gemini"), FauxJob("ancien", "mistral")]):
    app.render_job(job, expanded=(index == 0))
'''


def _apptest():
    # Le journal n'a pas besoin d'exister (`runner.tail` rend « log indisponible »), mais
    # son chemin doit vivre sous la racine du dépôt : `render_job` l'affiche en relatif.
    # `import app` rend le tableau de bord entier (≈ 5 s sur une machine chargée) : même marge que
    # les autres AppTest de la suite, au lieu des 3 s par défaut.
    at = AppTest.from_string(SCRIPT.replace("__RACINE__", str(RACINE)), default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    return at


def _plis(at) -> dict[str, bool]:
    """Le pli des DEUX volets de ce test — importer `app` rend la page entière, volets compris."""
    plis = {}
    for e in at.expander:
        for nom in ("gemini", "mistral"):
            if f" {nom} — " in e.proto.label:
                plis[nom] = e.proto.expanded
    return plis


def test_par_defaut_seul_le_job_de_tete_est_ouvert():
    at = _apptest()
    assert _plis(at) == {"gemini": True, "mistral": False}


def test_le_pli_choisi_par_le_lecteur_survit_au_rafraichissement():
    """Le fragment se rejoue toutes les 2 s : il ne doit plus rien réimposer."""
    at = _apptest()
    at.session_state["job-volet-ancien"] = True   # le lecteur ouvre la console de mistral
    at.run()
    assert _plis(at)["mistral"], "la console ouverte reste ouverte au tour suivant"


def test_le_lecteur_peut_aussi_refermer_le_job_de_tete():
    """Le défaut ne doit pas rouvrir de force ce qu'on vient de fermer."""
    at = _apptest()
    at.session_state["job-volet-recent"] = False
    at.run()
    assert not _plis(at)["gemini"]
