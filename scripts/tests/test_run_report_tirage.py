"""L'écart « attendu vs tiré » du rapport de run se mesure à dénominateur commun.

Le rapport somme les probabilités annoncées par le LLM sur les lignes qui en portent
une, mais comptait les modes tirés sur TOUTES les lignes de `moves.csv` — mono-choix,
fallback, « Aucun ». Le mode le plus fréquent y perdait plus de dix points et le
rapport levait une alarme accusant le cache. Ces tests fixent le dénominateur.
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "run_report", RACINE / "scripts" / "debug" / "run_report.py")
run_report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_report)

COLONNES = ["Mode de transport Choisi", "Méthode de sélection",
            "P(Marche) %", "P(Voiture Privée) %", "P(Transports_collectifs) %"]


def _ecrire_moves(dossier: Path, lignes: list[dict]) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / "moves.csv"
    with chemin.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLONNES)
        w.writeheader()
        for ligne in lignes:
            w.writerow({c: ligne.get(c, "") for c in COLONNES})
    return chemin


def _decision(mode: str, p_marche: float, p_voiture: float, p_tc: float) -> dict:
    return {"Mode de transport Choisi": mode, "Méthode de sélection": "LLM",
            "P(Marche) %": p_marche, "P(Voiture Privée) %": p_voiture,
            "P(Transports_collectifs) %": p_tc}


def _sans_repartition(mode: str, methode: str) -> dict:
    return {"Mode de transport Choisi": mode, "Méthode de sélection": methode}


def _rapport(tmp_path: Path, lignes: list[dict]) -> tuple[str, list[str]]:
    _ecrire_moves(tmp_path, lignes)
    out: list[str] = []
    alarmes: list[str] = []
    run_report.section_decisions(tmp_path, out, alarmes)
    return "\n".join(out), alarmes


def test_tirage_fidele_aucune_alarme(tmp_path):
    """Un tirage qui reproduit la répartition annoncée ne lève pas d'alarme."""
    lignes = [_decision("Transports_collectifs", 20, 30, 50) for _ in range(150)]
    lignes += [_decision("Voiture Privée", 20, 30, 50) for _ in range(90)]
    lignes += [_decision("Marche", 20, 30, 50) for _ in range(60)]
    texte, alarmes = _rapport(tmp_path, lignes)
    assert not [a for a in alarmes if "Tirage modal" in a], texte
    assert "Transports_collectifs | 50.0 % | 50.0 %" in texte


def test_lignes_sans_repartition_ne_faussent_pas_l_ecart(tmp_path):
    """Mono-choix, fallback et « Aucun » sortent des DEUX côtés de la comparaison.

    C'est le défaut mesuré sur le run 2026-09-04_16_25 : 1 689 lignes sans
    répartition sur 5 257 diluaient la part tirée d'un mode de 12 points.
    """
    lignes = [_decision("Transports_collectifs", 20, 30, 50) for _ in range(150)]
    lignes += [_decision("Voiture Privée", 20, 30, 50) for _ in range(90)]
    lignes += [_decision("Marche", 20, 30, 50) for _ in range(60)]
    # Autant de lignes sans répartition que de décisions probabilistes.
    lignes += [_sans_repartition("Aucun", "Pas de déplacement (même localisation)")
               for _ in range(150)]
    lignes += [_sans_repartition("Voiture Privée", "Un seul itinéraire disponible")
               for _ in range(150)]
    texte, alarmes = _rapport(tmp_path, lignes)
    assert not [a for a in alarmes if "Tirage modal" in a], texte
    assert "(300 décisions probabilistes" in texte
    # La table des modes, elle, compte bien toutes les lignes du journal.
    assert "| Voiture Privée | 240 |" in texte


def test_vrai_biais_de_tirage_leve_l_alarme(tmp_path):
    """Un tirage qui s'écarte vraiment de plus de 8 points reste détecté."""
    lignes = [_decision("Voiture Privée", 20, 30, 50) for _ in range(300)]
    texte, alarmes = _rapport(tmp_path, lignes)
    modales = [a for a in alarmes if "Tirage modal" in a]
    assert modales, texte
    # L'alarme nomme le mode le plus écarté : la voiture, tirée 100 % pour 30 % annoncés.
    assert "Voiture Privée" in modales[0]
    assert "70.0 pts" in modales[0]


def test_effectif_trop_faible_reste_muet(tmp_path):
    """Sous 200 décisions, l'écart n'est que du bruit : pas d'alarme."""
    lignes = [_decision("Voiture Privée", 20, 30, 50) for _ in range(50)]
    _, alarmes = _rapport(tmp_path, lignes)
    assert not [a for a in alarmes if "Tirage modal" in a]


def test_journal_absent(tmp_path):
    """Sans moves.csv, la section ne produit rien et ne casse pas le rapport."""
    out: list[str] = []
    alarmes: list[str] = []
    run_report.section_decisions(tmp_path, out, alarmes)
    assert out == [] and alarmes == []
