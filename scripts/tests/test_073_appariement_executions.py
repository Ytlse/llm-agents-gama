"""Ticket 073, axe 0 — l'appariement décision par décision ne ment pas sur ce qu'il mesure.

Chaque test porte sur une confusion qui produit un chiffre **présentable mais faux** — le seul
type de défaut qui compte ici, puisque le résultat part dans un chapitre.

1. **`distribution` n'est pas `poids_presentes`.** Le premier agrège sur les six modes
   canoniques et écrase deux options d'un même mode. Mesuré sur les 120 premières décisions
   du réplicat : 5 « bascules à masses égales » avec `distribution`, UNE avec
   `poids_presentes`. Or le ticket qualifie ce cas de défaut du dispositif : se tromper de
   vecteur, c'est inventer un bug.
2. **Une offre différente n'est pas une divergence du décideur.** Le déplacement précédent a
   basculé, le vélo n'est plus où il était : l'écart est réel mais hérité, et l'imputer au
   modèle gonfle la dispersion publiée.
3. **Deux méthodes égales ne sont pas une dissymétrie.** Le premier jet rangeait les 9
   décisions `inexploitable` des deux côtés en « méthode dissymétrique » : 9 incidents
   inventés sur 120 décisions (relevé le 2026-09-21).
4. **Une couverture partielle ne se publie pas.** C'est le défaut du 2026-09-15 : un
   `moves.csv` tronqué à 274 lignes lu comme s'il portait les 3 299 décisions.

Lancement :
    services/llm-agents/.venv/bin/python -m pytest scripts/tests/test_073_appariement_executions.py -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis.appariement_executions import apparier, charger, classer, mesurer


# ──────────────────────────────── fabrique ──────────────────────────────


def decision(
    person: str,
    activite: str,
    *,
    options: list[tuple[str, str]],
    poids: list[float],
    retenue_index: int,
    methode: str = "decideur",
    distribution: dict | None = None,
) -> dict:
    """Une décision, telle que le runner l'archive. `options` = [(code, mode), …]."""
    presentees = [{"code": c, "mode": m, "source": "enregistree"} for c, m in options]
    code, mode = options[retenue_index]
    return {
        "person_id": person,
        "activity_id": activite,
        "methode": methode,
        "presentees": presentees,
        "poids_presentes": poids,
        "distribution": distribution or {},
        "retenue": {"code": code, "mode": mode, "index_presente": retenue_index},
        "graine_tirage": 42,
        "graine_ordre": 42,
        "identifiant_lot": f"lot-{person}-{activite}",
    }


def ecrire(dossier: Path, decisions: list[dict]) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "decisions.jsonl").write_text(
        "\n".join(json.dumps(d, ensure_ascii=False) for d in decisions) + "\n",
        encoding="utf-8",
    )
    return dossier


@pytest.fixture(autouse=True)
def _sans_registre(monkeypatch):
    """Le paquet `experiences` ne vit que dans le conteneur : la garde est neutralisée ici.

    Elle a son propre test (`test_refus_si_non_comparable`), qui la simule explicitement.
    """
    import scripts.analysis.appariement_executions as M

    monkeypatch.setattr(
        M,
        "_garde",
        lambda a, b, inclure: {
            "disponible": False,
            "comparable": None,
            "differences": None,
            "composite_a": None,
            "composite_b": None,
        },
    )


DEUX_OPTIONS = [("c-foot", "foot"), ("c-car", "car")]


# ───────────────────────────────── tests ────────────────────────────────


def test_deux_executions_identiques_ne_dispersent_rien(tmp_path):
    """Le cas de référence : le témoin déterministe du ticket doit sortir à zéro."""
    lot = [
        decision("1", "a", options=DEUX_OPTIONS, poids=[0.7, 0.3], retenue_index=0),
        decision("1", "b", options=DEUX_OPTIONS, poids=[0.2, 0.8], retenue_index=1),
    ]
    a = ecrire(tmp_path / "a", lot)
    b = ecrire(tmp_path / "b", [dict(d) for d in lot])

    r = apparier(a, b)

    assert r["populations"]["appariables"] == 2
    assert r["masses"]["part_identiques"] == 1.0
    assert r["masses"]["l1_moyenne"] == 0.0
    assert r["retenue"]["bascules"] == 0
    assert r["couverture"]["suffisante"] is True


def test_offre_differente_est_une_cascade_amont_pas_une_divergence(tmp_path):
    """Masses identiques, options différentes : l'écart est hérité, pas imputable au décideur."""
    a = ecrire(
        tmp_path / "a",
        [decision("1", "a", options=DEUX_OPTIONS, poids=[0.7, 0.3], retenue_index=0)],
    )
    b = ecrire(
        tmp_path / "b",
        [
            decision(
                "1",
                "a",
                options=[("c-bike", "bicycle"), ("c-car", "car")],
                poids=[0.7, 0.3],
                retenue_index=0,
            )
        ],
    )

    r = apparier(a, b)

    assert r["populations"]["cascade_amont"] == 1
    assert r["populations"]["appariables"] == 0
    # Rien n'est chiffré : la dispersion ne se calcule pas sur une offre qui a bougé.
    assert r["masses"]["l1_moyenne"] is None
    assert r["retenue"]["bascules"] == 0


def test_bascule_a_masses_identiques_est_nommee(tmp_path):
    """À masses égales et graine égale, le tirage DOIT rendre la même option (ticket 073).

    Le cas se liste avec ses poids et ses index : c'est un défaut du dispositif, et un taux
    agrégé le rendrait indistinguable d'une dispersion du modèle.
    """
    a = ecrire(
        tmp_path / "a",
        [decision("41927", "x", options=DEUX_OPTIONS, poids=[0.7, 0.3], retenue_index=0)],
    )
    b = ecrire(
        tmp_path / "b",
        [decision("41927", "x", options=DEUX_OPTIONS, poids=[0.7, 0.3], retenue_index=1)],
    )

    r = apparier(a, b)

    assert r["retenue"]["bascules"] == 1
    assert r["retenue"]["bascules_a_masses_identiques"] == 1
    (detail,) = r["retenue"]["detail_masses_identiques"]
    assert detail["person_id"] == "41927"
    assert detail["poids"] == [0.7, 0.3]
    assert detail["a"]["index_presente"] == 0 and detail["b"]["index_presente"] == 1
    assert detail["graine_tirage"] == {"a": 42, "b": 42}


def test_distribution_agregee_egale_ne_vaut_pas_masses_egales(tmp_path):
    """Le piège central : deux options du MÊME mode, `distribution` égale, poids différents.

    Marche à 0,6 des deux côtés dans `distribution` — mais répartie 0,5/0,1 d'un côté et
    0,1/0,5 de l'autre entre les deux itinéraires piétons. Lire `distribution` conclurait
    « masses identiques » et transformerait la bascule en défaut du dispositif.
    """
    options = [("c-foot-1", "foot"), ("c-foot-2", "foot"), ("c-car", "car")]
    meme_distribution = {"walking": 0.6, "car": 0.4}
    a = ecrire(
        tmp_path / "a",
        [
            decision(
                "1",
                "a",
                options=options,
                poids=[0.5, 0.1, 0.4],
                retenue_index=0,
                distribution=meme_distribution,
            )
        ],
    )
    b = ecrire(
        tmp_path / "b",
        [
            decision(
                "1",
                "a",
                options=options,
                poids=[0.1, 0.5, 0.4],
                retenue_index=1,
                distribution=meme_distribution,
            )
        ],
    )

    r = apparier(a, b)

    assert r["masses"]["identiques"] == 0
    assert r["masses"]["l1_moyenne"] == pytest.approx(0.8)
    assert r["retenue"]["bascules"] == 1
    # Et surtout : PAS de défaut du dispositif, les masses diffèrent bel et bien.
    assert r["retenue"]["bascules_a_masses_identiques"] == 0


def test_methodes_egales_hors_mesure_ne_sont_pas_des_dissymetries(tmp_path):
    """Régression du 2026-09-21 : `inexploitable` des deux côtés n'est pas un incident."""
    # Aucune proposition des moteurs : ni options, ni poids, ni option retenue.
    inexploitable = {
        "person_id": "1",
        "activity_id": "a",
        "methode": "inexploitable",
        "presentees": [],
        "poids_presentes": [],
        "distribution": {},
        "retenue": {},
        "graine_tirage": 42,
    }
    a = ecrire(tmp_path / "a", [inexploitable])
    b = ecrire(tmp_path / "b", [json.loads(json.dumps(inexploitable))])

    familles = classer(charger(a), charger(b))

    assert len(familles["hors_mesure"]) == 1
    assert familles["methode_dissymetrique"] == []
    assert familles["appariables"] == []


def test_methode_dissymetrique_reste_signalee(tmp_path):
    """Offre identique, décideur d'un côté et pas de l'autre : ça, c'est un incident."""
    a = ecrire(
        tmp_path / "a",
        [decision("1", "a", options=DEUX_OPTIONS, poids=[0.7, 0.3], retenue_index=0)],
    )
    b = ecrire(
        tmp_path / "b",
        [
            decision(
                "1",
                "a",
                options=DEUX_OPTIONS,
                poids=[],
                retenue_index=0,
                methode="choix_unique",
            )
        ],
    )

    familles = classer(charger(a), charger(b))

    assert len(familles["methode_dissymetrique"]) == 1
    assert familles["appariables"] == []


def test_couverture_partielle_leve_l_alarme(tmp_path, caplog):
    """Un réplicat à 3 % ne se publie pas — c'est le défaut du moves.csv du 2026-09-15."""
    complet = [
        decision(str(i), "a", options=DEUX_OPTIONS, poids=[0.7, 0.3], retenue_index=0)
        for i in range(100)
    ]
    a = ecrire(tmp_path / "a", complet)
    b = ecrire(tmp_path / "b", complet[:3])

    with caplog.at_level("ERROR"):
        r = apparier(a, b)

    assert r["couverture"]["taux"] == pytest.approx(0.03)
    assert r["couverture"]["suffisante"] is False
    assert any("[ALARME]" in m and "couverture" in m for m in caplog.messages)


def test_refus_si_non_comparable(tmp_path, monkeypatch):
    """Deux conditions différentes ne mesurent pas le non-déterminisme : l'outil refuse."""
    import scripts.analysis.appariement_executions as M

    monkeypatch.setattr(
        M,
        "_garde",
        lambda a, b, inclure: {
            "disponible": True,
            "comparable": False,
            "differences": [{"champ": "jeu", "a": "…_EN", "b": "…_EN_c"}],
            "composite_a": None,
            "composite_b": None,
        },
    )
    lot = [decision("1", "a", options=DEUX_OPTIONS, poids=[0.7, 0.3], retenue_index=0)]
    a, b = ecrire(tmp_path / "a", lot), ecrire(tmp_path / "b", lot)

    with pytest.raises(ValueError, match="appariement refusé"):
        apparier(a, b)

    # …mais --tout passe outre, en connaissance de cause.
    assert apparier(a, b, inclure_invalides=True)["populations"]["appariables"] == 1


def test_couple_repete_ne_duplique_pas_la_cle(tmp_path):
    """Deux lignes pour le même (person_id, activity_id) : la dernière fait foi, pas les deux."""
    lot = [
        decision("1", "a", options=DEUX_OPTIONS, poids=[0.7, 0.3], retenue_index=0),
        decision("1", "a", options=DEUX_OPTIONS, poids=[0.2, 0.8], retenue_index=1),
    ]
    a = ecrire(tmp_path / "a", lot)

    charge = charger(a)

    assert len(charge) == 1
    assert charge[("1", "a")]["poids_presentes"] == [0.2, 0.8]


def test_mesurer_sans_decision_ne_divise_pas_par_zero(tmp_path):
    """Aucune décision appariable : des None, pas une exception."""
    m = mesurer({}, {}, [])
    assert m["n"] == 0
    assert m["masses"]["part_identiques"] is None
    assert m["retenue"]["taux_bascule"] is None
