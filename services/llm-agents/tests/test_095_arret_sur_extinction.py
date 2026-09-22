"""Ticket 095 — l'arrêt précoce se déclenche sur un ÉVÉNEMENT DATÉ, jamais sur une statistique.

Le cœur est pur : `analyser` lit des lignes et rend (extinction vue, jours vécus écoulés).
Les cas viennent du journal réel de la campagne du 2026-09-21.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "experiment"))

from arret_sur_extinction import analyser  # noqa: E402

SORTIE_PARTIELLE = (
    "2026-09-21 17:36:52 | INFO | llm.noyau - [noyau] 861500 : le souvenir de choc du "
    "2026-03-30 est sorti du bloc « ce qui a changé récemment » (durée 15.29 j)."
)
SORTIE_TOTALE = SORTIE_PARTIELLE[:-1] + " — plus aucun souvenir de choc ne pèse sur ses décisions."


def _jour(d):
    return f"2026-09-21 18:00:00 | INFO | [sync] END sim_time={d} 2026, 05:00"


def test_A_une_sortie_partielle_ne_declenche_pas():
    """Un souvenir qui sort pendant que d'autres restent servis ne termine rien."""
    vue, _ = analyser([SORTIE_PARTIELLE, _jour("15 April")])
    assert vue is False


def test_B_la_sortie_totale_declenche():
    vue, _ = analyser([SORTIE_PARTIELLE, SORTIE_TOTALE, _jour("15 April")])
    assert vue is True


def test_C_le_souvenir_declare_declenche_a_sa_date():
    """Clé recommandée : l'agent fabrique ses propres souvenirs graves, et la sortie TOTALE
    n'arrive qu'en fin de run. Mesuré le 2026-09-21 : 5 jours vécus restants contre 13."""
    vue, _ = analyser([SORTIE_PARTIELLE], souvenir_du="2026-03-30")
    assert vue is True
    vue_autre, _ = analyser([SORTIE_PARTIELLE], souvenir_du="2026-04-07")
    assert vue_autre is False, "un autre souvenir ne doit pas déclencher"


def test_D_les_jours_sont_comptes_en_jours_VECUS():
    """La simulation saute les week-ends : compter en calendaire retirerait deux jours sur sept."""
    lignes = [SORTIE_TOTALE] + [_jour(d) for d in
              ("14 April", "14 April", "15 April", "16 April", "17 April")]
    vue, n = analyser(lignes)
    assert vue is True
    assert n == 3, "quatre dates distinctes après l'extinction, dont celle du jour même"


def test_E_rien_avant_l_extinction_n_est_compte():
    lignes = [_jour("01 April"), _jour("02 April"), SORTIE_TOTALE, _jour("15 April")]
    _, n = analyser(lignes)
    assert n == 0


def test_F_le_journal_reel_du_2026_09_21():
    """Épreuve de bout en bout : les deux clés, sur le journal du bras traité."""
    p = (Path(__file__).resolve().parents[3] / "experiments" / "archive"
         / "2026-09-21_15_13" / "app.log")
    if not p.is_file():
        import pytest
        pytest.skip("archive absente de cette machine")
    with open(p, encoding="utf-8", errors="replace") as f:
        vue_totale, n_totale = analyser(f)
    with open(p, encoding="utf-8", errors="replace") as f:
        vue_declare, n_declare = analyser(f, souvenir_du="2026-03-30")
    assert vue_totale and vue_declare
    assert n_declare > n_totale, (
        "la sortie du souvenir DÉCLARÉ doit laisser plus de marge que l'extinction totale — "
        "c'est ce qui rend l'arrêt précoce rentable"
    )


# ══ Le câblage dans l'orchestrateur de campagne (2026-09-22) ═════════════════════════════════
# Jusqu'ici le détecteur était un script à lancer à la main, avec `--souvenir-du` à recopier
# soi-même depuis la trace. Une campagne de cinquante jours ne se surveille pas à la main :
# l'orchestrateur lit la date dans `evenements.jsonl` et coupe lui-même.

import json  # noqa: E402

from run_sequential_cohort import date_du_souvenir_declare  # noqa: E402


def _trace(tmp_path, dates):
    """Un répertoire de run portant une trace d'événements aux dates simulées données."""
    (tmp_path / "evenements.jsonl").write_text(
        "\n".join(
            json.dumps({"person_id": "861500", "horodatage_simule": f"{d}T14:07:37"})
            for d in dates
        )
        + "\n",
        encoding="utf-8",
    )
    return tmp_path


def test_la_date_surveillee_est_celle_de_la_DERNIERE_application(tmp_path):
    """c6 frappe deux jours. Surveiller le premier couperait le run souvenir encore servi."""
    assert date_du_souvenir_declare(_trace(tmp_path, ["2026-03-16", "2026-03-17"])) == "2026-03-17"


def test_sans_trace_aucune_date_donc_aucun_arret(tmp_path):
    """Le bras TÉMOIN ne subit rien : sa trace est vide et il doit aller à son horizon.

    C'est la condition qui rend la comparaison appariée encore lisible — le témoin n'est jamais
    tronqué par surprise, c'est l'analyse qui le ramène au jour du bras traité.
    """
    assert date_du_souvenir_declare(tmp_path) is None
    (tmp_path / "evenements.jsonl").write_text("", encoding="utf-8")
    assert date_du_souvenir_declare(tmp_path) is None
    assert date_du_souvenir_declare(None) is None


def test_une_ligne_tronquee_ne_fait_pas_tomber_la_surveillance(tmp_path):
    """La trace s'écrit PENDANT qu'on la lit : la dernière ligne peut être coupée en deux."""
    p = _trace(tmp_path, ["2026-03-16"])
    with open(p / "evenements.jsonl", "a", encoding="utf-8") as f:
        f.write('{"person_id": "861500", "horodatage_sim')
    assert date_du_souvenir_declare(p) == "2026-03-16"


def test_le_detecteur_ne_compte_que_les_jours_qui_suivent_la_date_surveillee():
    """Bout en bout : la date vient de la trace, et `analyser` la retrouve dans le journal."""
    sortie = (
        "2026-09-22 10:00:00 | INFO | llm.noyau - [noyau] 861500 : le souvenir de choc du "
        "2026-03-17 est sorti du bloc « ce qui a changé récemment » (durée 16.17 j)."
    )
    lignes = [_jour("10 April"), sortie, _jour("10 April"), _jour("11 April"), _jour("13 April")]
    vue, ecoules = analyser(lignes, "2026-03-17")
    assert vue is True
    # Trois dates après l'extinction, la première comptant pour zéro : deux jours vécus.
    assert ecoules == 2
    # Et le souvenir d'une AUTRE date ne déclenche rien.
    assert analyser(lignes, "2026-03-16") == (False, 0)
