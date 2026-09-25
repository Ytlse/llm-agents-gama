"""Un article se lit par un ADULTE du foyer (2026-09-24).

Famille de quatre, deux adultes et deux enfants : le lecteur se tire parmi les deux adultes ;
l'autre adulte et les enfants sont les témoins internes.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm.evenements.exposition import lecteurs  # noqa: E402


def _membre(pid, foyer, age, immobile=False):
    return SimpleNamespace(
        person_id=pid, household_id=foyer, immobile=immobile,
        identity=SimpleNamespace(traits_json={} if age is None else {"age": age}),
    )


def _expo(foyers, n=1, graine=59):
    return SimpleNamespace(foyers=set(foyers), lecteurs_par_foyer=n, graine=graine)


FAMILLE = [_membre("11", "F", 44), _membre("12", "F", 41), _membre("13", "F", 12), _membre("14", "F", 9)]


def test_le_lecteur_est_un_des_deux_adultes_quelle_que_soit_la_graine():
    for graine in range(40):
        lus = lecteurs(_expo({"F"}, graine=graine), "a09", FAMILLE)
        assert len(lus) == 1
        assert set(lus) <= {"11", "12"}


def test_meme_deux_lecteurs_demandes_aucun_enfant_ne_lit():
    lus = lecteurs(_expo({"F"}, n=3), "a09", FAMILLE)
    assert set(lus) == {"11", "12"}


def test_un_foyer_sans_adulte_mobile_leve_l_alarme():
    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(m.record["message"]), level="ERROR")
    try:
        pop = [_membre("21", "G", 45, immobile=True), _membre("22", "G", 15)]
        assert lecteurs(_expo({"G"}), "a09", pop) == {}
    finally:
        logger.remove(sink)
    assert any("AUCUN adulte mobile" in m for m in messages)


def test_un_age_absent_n_exclut_pas():
    """Les populations sans âge gardent leur lecteur : l'écarter viderait le run sans bruit."""
    pop = [_membre("31", "H", None), _membre("32", "H", None)]
    assert len(lecteurs(_expo({"H"}), "a09", pop)) == 1
