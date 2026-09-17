"""Ticket 057 — un déplacement compte une fois, et la coupe ne s'applique que s'il y a de quoi couper.

Spec : `specs/ticket_057/perimetre_de_score.md`.

Ce que ces tests verrouillent, en chiffres du 2026-09-16 : sur les huit exécutions sans
simulateur du 14/09, la coupe au premier jour simulé retirait **866 décisions sur 3 299**
pour **zéro couple répété** — dont 797 le déplacement de rang 0 de chaque persona, que
`jeu.py:deplacements_attendus()` date du lendemain parce que l'activité « home » d'origine
enjambe minuit. Le périmètre scoré montait à 56,9 % de retours au domicile contre 43,8 % sur
la journée entière et 39,0 % dans l'enquête, et l'écart entre les deux lectures du composite
passait de +2,24 à +5,64 points EMD chez `lgbm`.

Les tests portent sur des journaux fabriqués : une exécution du dépôt ne peut pas produire à
volonté un couple répété, et un test qui ne vérifierait que le cas sans répétition passerait
en ne mesurant rien.
"""

import csv
from pathlib import Path

import pytest
from scripts.synthesis import frames

EXCLURE: list[str] = []

# Colonnes minimales que `read_moves` exige pour produire une ligne exploitable.
ENTETE = [
    "ID Personne",
    "ID Activité",
    "Temps simulé",
    "Heure de calcul",
    "Mode de transport Choisi",
    "Méthode de sélection",
    "Occupation principale",
    "Genre",
    "Âge",
    "Motifs de déplacement",
    "Distance parcourue",
    "Lieu de résidence",
    "Type de logement",
    "Modes proposés au LLM",
    "Heure de départ",
]

# 2026-03-16 08:00 UTC et le même instant le lendemain.
J1 = 1773648000
J2 = J1 + 86400


def _ligne(person: str, activity: str, ts: int, calcul: str = "2026-09-16 10:00:00") -> dict:
    return {
        "ID Personne": person,
        "ID Activité": activity,
        "Temps simulé": str(ts),
        "Heure de calcul": calcul,
        "Mode de transport Choisi": "Voiture Privée",
        "Méthode de sélection": "LLM",
        "Occupation principale": "Full-time worker",
        "Genre": "Homme",
        "Âge": "40",
        "Motifs de déplacement": "Travail",
        "Distance parcourue": "5000",
        "Lieu de résidence": "Toulouse",
        "Type de logement": "individuel isolé",
        "Modes proposés au LLM": "Marche | Voiture Privée",
        "Heure de départ": "2026-03-16 08:00:00",
    }


def _journal(tmp_path: Path, lignes: list[dict]) -> Path:
    chemin = tmp_path / "moves.csv"
    with chemin.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ENTETE)
        writer.writeheader()
        writer.writerows(lignes)
    return chemin


# ── R3 — pas de répétition, pas de coupe ─────────────────────────────────────────────────

def test_sans_repetition_aucune_ligne_ecartee(tmp_path):
    """Le cas des exécutions sans simulateur : des déplacements uniques, dont certains datés
    du lendemain. Aucun ne doit sortir du périmètre."""
    journal = _journal(
        tmp_path,
        [
            _ligne("1", "a", J1),
            _ligne("1", "b", J1),
            _ligne("1", "c", J2),  # départ du matin, daté du lendemain
            _ligne("2", "d", J2),
        ],
    )
    rows, stats = frames.read_moves(journal, EXCLURE, horizon_jours=1)
    assert stats["coupe"] == "aucune"
    assert stats["couples_repetes"] == 0
    assert stats.get("exclues_jour", 0) == 0
    assert len(rows) == 4


def test_la_coupe_systematique_retirait_ces_memes_lignes(tmp_path):
    """Le comportement d'avant, conservé sous `first_day_only=True` (R6) : il écarte les deux
    déplacements du lendemain, qui ne sont pourtant la répétition de rien."""
    journal = _journal(
        tmp_path,
        [_ligne("1", "a", J1), _ligne("1", "c", J2), _ligne("2", "d", J2)],
    )
    rows, stats = frames.read_moves(journal, EXCLURE, first_day_only=True)
    assert stats["coupe"] == "forcee"
    assert stats["exclues_jour"] == 2
    assert len(rows) == 1


# ── R2 — couper quand il y a de quoi couper ──────────────────────────────────────────────

def test_couple_repete_declenche_la_coupe(tmp_path):
    """Horizon glissant : le même couple réapparaît le lendemain. C'est le cas pour lequel la
    coupe existe, et elle doit jouer sans qu'aucun réglage ne l'annonce."""
    journal = _journal(
        tmp_path,
        [
            _ligne("1", "a", J1),
            _ligne("1", "a", J2),  # répétition
            _ligne("1", "b", J1),
        ],
    )
    rows, stats = frames.read_moves(journal, EXCLURE, horizon_jours=1)
    assert stats["coupe"] == "repetitions"
    assert stats["couples_repetes"] == 1
    assert len(rows) == 2


def test_horizon_au_dela_dun_jour_declenche_la_coupe(tmp_path):
    """Un run multi-jours dont chaque journée diffère ne porte aucune répétition : seul
    l'horizon déclaré dit qu'il ne faut en scorer qu'une."""
    journal = _journal(tmp_path, [_ligne("1", "a", J1), _ligne("1", "b", J2)])
    rows, stats = frames.read_moves(journal, EXCLURE, horizon_jours=3)
    assert stats["coupe"] == "horizon"
    assert stats["couples_repetes"] == 0
    assert len(rows) == 1


# ── R1/R4 — l'unicité tient même si le critère se trompe ─────────────────────────────────

def test_un_deplacement_ne_compte_quune_fois(tmp_path):
    """L'invariant, vérifié là où le critère de coupe est explicitement désarmé : même
    `first_day_only=False` ne laisse pas un couple peser deux fois."""
    journal = _journal(
        tmp_path,
        [_ligne("1", "a", J1), _ligne("1", "a", J2), _ligne("1", "b", J1)],
    )
    rows, stats = frames.read_moves(journal, EXCLURE, first_day_only=False)
    assert stats["exclues_doublon"] == 1
    assert len(rows) == 2
    couples = [(r["agent_id"], r["activity_id"]) for r in rows]
    assert len(couples) == len(set(couples))


def test_loccurrence_gardee_est_celle_du_premier_jour(tmp_path):
    """Quand le filet joue, il garde la décision du premier jour simulé — celle que la coupe
    aurait gardée. Sans cette règle, la décision changerait de jour selon l'ordre du fichier."""
    journal = _journal(
        tmp_path,
        [_ligne("1", "a", J2), _ligne("1", "a", J1)],  # le lendemain écrit en premier
    )
    rows, _ = frames.read_moves(journal, EXCLURE, first_day_only=False)
    assert len(rows) == 1
    assert rows[0]["departure_hour"] is not None


# ── R5 — le périmètre appliqué est publié ────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("horizon", "attendu"),
    [(1, "aucune"), (5, "horizon")],
)
def test_le_motif_de_coupe_est_publie(tmp_path, horizon, attendu):
    journal = _journal(tmp_path, [_ligne("1", "a", J1), _ligne("1", "b", J2)])
    _, stats = frames.read_moves(journal, EXCLURE, horizon_jours=horizon)
    assert stats["coupe"] == attendu


def test_libelle_de_perimetre_dit_le_motif():
    from experiences.score import _libelle_perimetre

    assert "toutes les décisions" in _libelle_perimetre({"coupe": "aucune"})
    assert "premier jour simulé" in _libelle_perimetre({"coupe": "horizon"})
    texte = _libelle_perimetre({"coupe": "repetitions", "couples_repetes": 3})
    assert "3 couple(s) répété(s)" in texte
