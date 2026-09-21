"""Ticket 077, lot G — le BRANCHEMENT de l'hibernation et des mesures du jour.

Spécification : `specs/ticket_077/tests.md`, section G. Les identifiants de cas (G1, G4…)
y renvoient.

Pourquoi ce fichier existe. Le run `experiments/archive/2026-09-19_07_31` n'a produit aucun
des CSV du ticket 093, alors que `mesures_jour_enabled` valait `true`. Cause : la méthode
`_declencher_hibernation_propre` avait été insérée au MILIEU de `_ecrire_point_de_reprise`,
et l'appel aux mesures s'est retrouvé après un `sys.exit(0)` — inatteignable. Les tests du
093 sont restés verts tout du long : ils vérifiaient le module, pas son branchement.

Ces tests portent donc sur le branchement et sur la forme du code, jamais sur le calcul des
mesures, qui est couvert ailleurs (`test_093_mesures_jour.py`).
"""

import ast
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from urban_mobility_agents import simulation_controller as sc
from urban_mobility_agents.utils import mesures_jour

SOURCE = Path(sc.__file__)
T0 = 1773637200  # 16 mars 2026, 05:00 en heure murale de simulation


# ══════════════════════════ doublures ═══════════════════════════════════════════


class _PopulationDouble:
    def get_people_list(self):
        return []


def _boucle(timestamp: int = T0) -> SimpleNamespace:
    """La boucle réduite à ce que les deux méthodes sous test lisent réellement."""
    return SimpleNamespace(
        agent=None,
        population=_PopulationDouble(),
        _current_sim_timestamp=timestamp,
    )


def _poser_workdir(monkeypatch, workdir: Path) -> None:
    """`settings` est un proxy à `__getattribute__` : on remplace le nom dans le module visé.

    Même geste que `test_070_accidents_interrupteur.py` — une doublure posée sur le proxy ne
    prendrait jamais, et le test passerait en lisant le workdir réel du processus.
    """
    monkeypatch.setattr(sc, "settings", SimpleNamespace(workdir=workdir))


def _fonction(nom: str) -> ast.AST:
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)) and noeud.name == nom:
            return noeud
    raise AssertionError(f"fonction introuvable : {nom}")


def _est_appel_terminal(instruction: ast.stmt) -> bool:
    """`sys.exit(…)`, `os._exit(…)`, ou un signal envoyé à son propre processus."""
    if not (isinstance(instruction, ast.Expr) and isinstance(instruction.value, ast.Call)):
        return False
    appel = ast.unparse(instruction.value.func)
    return appel in {"sys.exit", "exit", "os._exit", "os.kill"}


# ══════════════════════════ G1 — les mesures du jour sont branchées ═════════════


def _armer(monkeypatch, tmp_path, actif=True, point_leve=False):
    vus: list[Path] = []

    def _ecriture(workdir):
        vus.append(Path(workdir))
        return 1

    def _point(*_a, **_k):
        if point_leve:
            raise OSError("disque plein")

    monkeypatch.setattr(mesures_jour, "actif", lambda: actif)
    monkeypatch.setattr(mesures_jour, "ecrire_mesures_du_jour", _ecriture)
    monkeypatch.setattr(sc, "ecrire_point", _point)
    _poser_workdir(monkeypatch, tmp_path)
    return vus


def test_G1_le_point_de_reprise_ecrit_les_mesures_du_jour(monkeypatch, tmp_path):
    """G1 — la règle qui échoue si on remet le code dans l'état du 19 septembre."""
    vus = _armer(monkeypatch, tmp_path)
    asyncio.run(sc.SimulationLoopV1._ecrire_point_de_reprise(_boucle(), T0))
    assert vus == [tmp_path], "les mesures du jour ne sont plus appelées au point de reprise"


def test_G1b_reglage_eteint_aucune_mesure(monkeypatch, tmp_path):
    """G1b — éteint, le module ne lit rien et n'écrit rien."""
    vus = _armer(monkeypatch, tmp_path, actif=False)
    asyncio.run(sc.SimulationLoopV1._ecrire_point_de_reprise(_boucle(), T0))
    assert vus == []


def test_G1c_un_point_qui_leve_n_emporte_pas_les_mesures(monkeypatch, tmp_path):
    """G1c — le fail-open du point de reprise ne doit pas emporter celui des mesures."""
    vus = _armer(monkeypatch, tmp_path, point_leve=True)
    asyncio.run(sc.SimulationLoopV1._ecrire_point_de_reprise(_boucle(), T0))
    assert vus == [tmp_path], "un point de reprise en échec a fait sauter les mesures du jour"


# ══════════════════════════ G2 — garde générique sur le code mort ═══════════════


def test_G2_aucune_instruction_apres_un_appel_terminal():
    """G2 — la faute se rattrape partout dans le fichier, pas seulement là où elle est née."""
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    fautes = []
    for noeud in ast.walk(arbre):
        for champ in ("body", "orelse", "finalbody"):
            bloc = getattr(noeud, champ, None)
            if not isinstance(bloc, list):
                continue
            for rang, instruction in enumerate(bloc[:-1]):
                if _est_appel_terminal(instruction):
                    fautes.append(
                        f"ligne {instruction.lineno} : {len(bloc) - rang - 1} instruction(s) "
                        f"morte(s) après {ast.unparse(instruction).strip()}"
                    )
    assert not fautes, "code mort après un appel terminal :\n" + "\n".join(fautes)


# ══════════════════════════ G3 à G5 — l'hibernation ═════════════════════════════


def _armer_hibernation(monkeypatch, workdir):
    signaux: list[tuple] = []
    _poser_workdir(monkeypatch, workdir)
    monkeypatch.setattr(sc.os, "kill", lambda pid, sig: signaux.append((pid, sig)))

    async def _point(_ts):
        return None

    boucle = _boucle()
    boucle._ecrire_point_de_reprise = _point
    return boucle, signaux


def test_G3_le_marqueur_est_ecrit_dans_le_workdir_du_run(monkeypatch, tmp_path):
    """G3 — `settings.workdir`, et non un `settings.data.workdir` qui n'existe pas."""
    boucle, _ = _armer_hibernation(monkeypatch, tmp_path)
    asyncio.run(sc.SimulationLoopV1._declencher_hibernation_propre(boucle, "2026-09-19T12:00", "899549"))

    marqueur = tmp_path / "en_attente_quota.json"
    assert marqueur.is_file(), "aucun marqueur d'attente écrit"
    contenu = json.loads(marqueur.read_text(encoding="utf-8"))
    assert contenu["person_id"] == "899549"
    assert contenu["resume_at"] == "2026-09-19T12:00"
    assert contenu["timestamp"] == T0
    assert contenu["jour_simule"] >= 1


def test_G4_l_arret_est_demande_une_seule_fois_par_signal(monkeypatch, tmp_path):
    """G4 — SIGTERM au processus : l'orchestrateur séquentiel attend un code de retour 0."""
    import os
    import signal

    boucle, signaux = _armer_hibernation(monkeypatch, tmp_path)
    asyncio.run(sc.SimulationLoopV1._declencher_hibernation_propre(boucle, "2026-09-19T12:00", "899549"))

    assert len(signaux) == 1, f"arrêt demandé {len(signaux)} fois"
    pid, sig = signaux[0]
    assert pid == os.getpid()
    assert sig == signal.SIGTERM


def test_G5_un_marqueur_impossible_n_annule_pas_l_arret(monkeypatch, tmp_path, caplog):
    """G5 — sinon l'hibernation devient un run qui continue sur des replis par défaut."""
    boucle, signaux = _armer_hibernation(monkeypatch, tmp_path / "chemin" / "inexistant")
    asyncio.run(sc.SimulationLoopV1._declencher_hibernation_propre(boucle, "2026-09-19T12:00", "899549"))
    assert len(signaux) == 1, "l'arrêt n'a pas été demandé alors que le marqueur a échoué"


# ══════════════════════════ G6 — la forme du retour ═════════════════════════════


def test_G6_compute_move_rend_toujours_un_couple():
    """G6 — les quatre appelants font `move, _ = await …` : un `None` nu casse l'unpacking."""
    fonction = _fonction("_compute_move_for_activity")
    imbriquees = {
        n for f in ast.walk(fonction)
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and f is not fonction
        for n in ast.walk(f)
    }
    fautes = []
    for noeud in ast.walk(fonction):
        if isinstance(noeud, ast.Return) and noeud not in imbriquees:
            valeur = noeud.value
            if not (isinstance(valeur, ast.Tuple) and len(valeur.elts) == 2):
                fautes.append(f"ligne {noeud.lineno} : {ast.unparse(noeud).strip()}")
    assert not fautes, "retour non conforme à la signature (couple attendu) :\n" + "\n".join(fautes)
