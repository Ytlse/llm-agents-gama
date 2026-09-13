"""« S'inspirer d'une expérience existante » : de la plus récemment utilisée à la moins récente.

L'ordre alphabétique mettait en tête des expériences oubliées depuis des semaines, alors que ce
sélecteur sert d'abord à repartir de ce qu'on vient de faire. Le critère est la dernière
ÉCRITURE d'un `etat.json`, pas le nom du dossier d'exécution : celui-ci porte l'heure de
CRÉATION, si bien qu'une exécution ouverte le matin et reprise le soir passerait pour vieille.
"""

import os
import sys
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.dashboard import experiences  # noqa: E402


def _experience(racine: Path, nom: str, executions: dict[str, float] | None = None) -> Path:
    d = racine / nom
    d.mkdir(parents=True)
    (d / "experience.yaml").write_text(yaml.safe_dump({"nom": nom}), encoding="utf-8")
    for exec_nom, quand in (executions or {}).items():
        e = d / "executions" / exec_nom
        e.mkdir(parents=True)
        etat = e / "etat.json"
        etat.write_text('{"etat": "terminee"}', encoding="utf-8")
        os.utime(etat, (quand, quand))
    return d


def test_la_plus_recemment_utilisee_vient_en_tete(monkeypatch, tmp_path):
    _experience(tmp_path, "a_vieille", {"2026-09-08_09_00_00": 1_000.0})
    _experience(tmp_path, "z_recente", {"2026-09-08_08_00_00": 9_000.0})
    monkeypatch.setattr(experiences, "DOSSIER", tmp_path)
    assert list(experiences.experiences()) == ["z_recente", "a_vieille"]


def test_une_execution_reprise_compte_comme_recente(monkeypatch, tmp_path):
    """Le dossier porte l'heure de création ; c'est l'état réécrit à la reprise qui date l'usage."""
    _experience(tmp_path, "ouverte_le_matin_reprise_ce_soir", {"2026-09-08_08_00_00": 9_000.0})
    _experience(tmp_path, "ouverte_a_midi_jamais_reprise", {"2026-09-08_12_00_00": 2_000.0})
    monkeypatch.setattr(experiences, "DOSSIER", tmp_path)
    assert list(experiences.experiences())[0] == "ouverte_le_matin_reprise_ce_soir"


def test_les_jamais_utilisees_ferment_la_liste_par_ordre_alphabetique(monkeypatch, tmp_path):
    _experience(tmp_path, "b_jamais")
    _experience(tmp_path, "a_jamais")
    _experience(tmp_path, "m_utilisee", {"2026-09-08_10_00_00": 5_000.0})
    monkeypatch.setattr(experiences, "DOSSIER", tmp_path)
    assert list(experiences.experiences()) == ["m_utilisee", "a_jamais", "b_jamais"]


def test_une_experience_sans_execution_ni_dossier_ne_casse_rien(monkeypatch, tmp_path):
    d = _experience(tmp_path, "sans_dossier_executions")
    monkeypatch.setattr(experiences, "DOSSIER", tmp_path)
    assert experiences.derniere_utilisation(d) == 0.0
    assert list(experiences.experiences()) == ["sans_dossier_executions"]


def test_une_execution_sans_etat_lisible_retombe_sur_son_dossier(monkeypatch, tmp_path):
    d = _experience(tmp_path, "etat_absent")
    (d / "executions" / "2026-09-08_10_00_00").mkdir(parents=True)
    monkeypatch.setattr(experiences, "DOSSIER", tmp_path)
    assert experiences.derniere_utilisation(d) > 0.0, "le dossier fait foi quand l'état manque"


def test_le_dossier_des_experiences_absent_rend_une_liste_vide(monkeypatch, tmp_path):
    monkeypatch.setattr(experiences, "DOSSIER", tmp_path / "nexiste-pas")
    assert experiences.experiences() == {}


# ── La colonne « Décideur » nomme la famille du modèle (ticket 043) ──────────
#
# Quatre expériences de modèle coexistent — booster, logit, forêt aléatoire, logistique à
# noyau — et `experience.yaml` ne porte que le chemin de l'artefact. La colonne affichait
# « modele » quatre fois, c'est-à-dire la seule chose que ces quatre lignes avaient en
# commun. La famille se DÉRIVE du format de l'artefact, comme dans les traces d'exécution.

def _artefact(chemin: Path, format_: str) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text('{\n "format": "%s",\n "spec_version": 2\n}\n' % format_,
                      encoding="utf-8")
    return chemin


def test_le_decideur_modele_nomme_sa_famille(tmp_path):
    art = _artefact(tmp_path / "klr_model.json", "klr_mode_choice_policy")
    label = experiences._decideur_label({"type": "modele", "artefact": str(art)})
    assert label == "modele:klr"


def test_chaque_famille_a_son_libelle(tmp_path):
    attendus = {"lightgbm_mode_choice_policy": "modele:lightgbm",
                "mnl_mode_choice_policy": "modele:mnl",
                "klr_mode_choice_policy": "modele:klr",
                "rf_mode_choice_policy": "modele:rf"}
    for format_, attendu in attendus.items():
        art = _artefact(tmp_path / f"{format_}.json", format_)
        assert experiences._decideur_label(
            {"type": "modele", "artefact": str(art)}) == attendu


def test_un_artefact_illisible_laisse_modele_nu(tmp_path):
    """Inventer une famille serait pire que n'en dire aucune."""
    assert experiences._decideur_label(
        {"type": "modele", "artefact": str(tmp_path / "jamais_estime.json")}) == "modele"
    vide = _artefact(tmp_path / "sans_format.json", "")
    vide.write_text('{"spec_version": 2}', encoding="utf-8")
    assert experiences._decideur_label({"type": "modele", "artefact": str(vide)}) == "modele"


def test_un_format_hors_convention_est_rendu_tel_quel(tmp_path):
    """Mieux vaut un libellé brut qu'un libellé traduit au jugé."""
    art = _artefact(tmp_path / "exotique.json", "arbre_magique_v9")
    assert experiences._decideur_label(
        {"type": "modele", "artefact": str(art)}) == "modele:arbre_magique_v9"


def test_sans_artefact_c_est_le_booster_par_defaut():
    """`artefact: null` = l'artefact par défaut, comme à l'exécution."""
    defaut = RACINE / experiences.ARTEFACT_MODELE_DEFAUT
    if not defaut.exists():
        import pytest
        pytest.skip("Booster non entraîné — `make policy`")
    assert experiences._decideur_label({"type": "modele"}) == "modele:lightgbm"


def test_le_defaut_du_tableau_est_celui_du_decideur():
    """Deux constantes qui se désynchronisent annonceraient la mauvaise famille.

    Lu comme du texte plutôt qu'importé : le décideur vit dans `services/llm-agents/`, un autre
    paquet, et l'importer ici pour vérifier un chemin coûterait ses dépendances.
    """
    source = (RACINE / "services" / "llm-agents" / "experiences" / "decideur_modele.py").read_text(
        encoding="utf-8")
    fin = experiences.ARTEFACT_MODELE_DEFAUT.split("/")[-1]
    assert f'"{fin}"' in source, (
        f"POLICY_DEFAUT ne désigne plus {fin} : la colonne Décideur du tableau de bord "
        "nommerait la mauvaise famille pour une expérience sans artefact explicite.")


def test_une_passerelle_reste_nommee_par_son_modele():
    """Le comportement des autres décideurs ne bouge pas."""
    assert experiences._decideur_label(
        {"type": "passerelle", "modele": "gemini-3.5-flash-lite"}) == "gemini-3.5-flash-lite"
    assert experiences._decideur_label({"type": "aleatoire"}) == "aleatoire"
    assert experiences._decideur_label({"type": "rejeu", "modele": "x"}) == "rejeu:x"
    assert experiences._decideur_label(None) == ""
