"""Les enquêtes d'un jalon s'interrogent ensemble, mode par mode (2026-09-24).

La boucle personne par personne ne présentait jamais au gateway qu'un agent à la fois : aucun
micro-lot ne pouvait se former. Les personas partent désormais ensemble pour un mode donné, et
les modes restent séquentiels — un lot ne réunit que des questions sur le même mode.
"""

import asyncio
import csv
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm import noyau as noyau_module
from urban_mobility_agents import enquetes

T0 = 1773637200
PIDS = ["101", "102", "103", "104"]


class _ClientQuiObserve:
    """Retient, pour chaque appel, le mode demandé et combien d'appels étaient en vol."""

    def __init__(self):
        self.en_vol = 0
        self.observations: list[tuple[str | None, str, int]] = []

    async def execute(self, payload):
        item = payload["agents"][0]
        self.en_vol += 1
        self.observations.append((item.get("mode_interroge"), item["agent_id"], self.en_vol))
        await asyncio.sleep(0.01)   # le temps que les autres personas du même mode arrivent
        self.en_vol -= 1
        return SimpleNamespace(
            agents=[SimpleNamespace(agent_id=item["agent_id"],
                                    scores=dict.fromkeys(enquetes.CRITERES, 5),
                                    justification="j")],
            provider_used="google_gemini31_key1",
        )


class _Memoire:
    user_metadata: dict = {}

    def journal_trajets(self, person_id):
        return {}


@pytest.fixture(autouse=True)
def _propre(monkeypatch):
    enquetes.reinitialiser()
    noyau_module.reinitialiser()
    monkeypatch.delenv("EXPERIMENT_SURVEY_MODES", raising=False)
    monkeypatch.setenv("EXPERIMENT_TARGET_PERSONAS", ",".join(PIDS))
    yield
    enquetes.reinitialiser()
    noyau_module.reinitialiser()


def _jouer(tmp_path):
    client = _ClientQuiObserve()
    agent = SimpleNamespace(
        llm_client=client, long_term_memory=_Memoire(),
        get_person_identity_description=lambda p: "récit",
    )
    personnes = [SimpleNamespace(person_id=p, identity=SimpleNamespace(name=p)) for p in PIDS]
    asyncio.run(enquetes.executer_enquetes_jalon(17, T0, personnes, agent, tmp_path))
    return client


def test_les_personas_d_un_mode_partent_ensemble(tmp_path):
    client = _jouer(tmp_path)
    assert max(n for _, _, n in client.observations) == len(PIDS)


def test_un_mode_ne_commence_qu_apres_le_precedent(tmp_path):
    """Les appels arrivent par blocs d'un seul mode, dans l'ordre des questions."""
    client = _jouer(tmp_path)
    modes = [m for m, _, _ in client.observations]
    blocs = [modes[i:i + len(PIDS)] for i in range(0, len(modes), len(PIDS))]
    assert all(len(set(b)) == 1 for b in blocs)
    assert len(blocs) == len(enquetes.modes_interroges()) + 1
    assert blocs[-1][0] is None   # les priorités en dernier


def test_le_csv_garde_l_ordre_persona_puis_mode(tmp_path):
    _jouer(tmp_path)
    with open(tmp_path / "affinites_declarees.csv", encoding="utf-8") as f:
        lignes = list(csv.DictReader(f))
    ordre = list(dict.fromkeys(l["persona_id"] for l in lignes))
    assert ordre == PIDS
    attendu = len(PIDS) * (len(enquetes.modes_interroges()) + 1) * len(enquetes.CRITERES)
    assert len(lignes) == attendu
