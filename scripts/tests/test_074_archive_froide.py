"""Ticket 074, A-4 — l'archive froide est inaccessible À CHAUD, et c'est le code qui le tient.

    Froid = restaurable et auditable, jamais utilisé ni référencé.

Le critère d'acceptation du ticket est explicite : « un test prouve qu'aucun chargeur du code
ne résout un nom depuis `archive/` ». Prouver, pas promettre — une garantie qui n'existe que
dans un README ne se déclenche jamais (leçon du ticket 045 : 36 exécutions ont lu la mauvaise
cohorte sans que rien s'y oppose).

Trois chargeurs, trois points de passage obligés, trois refus :

1. `experiences.population.resoudre_population` — toute lecture de cohorte y passe ;
2. `experiences.jeu.Jeu.charger` — toute lecture de jeu scellé y passe ;
3. `llm_gateway.prompts.engine.PromptManager` — tout service de prompt système y passe.

Et deux propriétés d'ancrage, qui sont la raison pour laquelle le registre et la file ne voient
jamais l'archive : `dossier_experiences()` et `dossier_jeux()` s'ancrent sur `data/`, et
l'archive vit ailleurs.

La dérogation reste possible — la garde de comparabilité D-7 doit pouvoir relire la v5 gelée —
mais elle exige un MOTIF écrit, jamais un booléen.

Lancement :
    services/llm-agents/.venv/bin/python -m pytest scripts/tests/test_074_archive_froide.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "services" / "llm-agents"))
sys.path.insert(0, str(RACINE / "packages" / "llm_gateway" / "src"))

from experiences import froid  # noqa: E402
from experiences.experience import dossier_experiences, dossier_jeux  # noqa: E402
from experiences.population import PopulationArchivee, resoudre_population  # noqa: E402
from llm_gateway.prompts.engine import PromptManager, PromptsArchives  # noqa: E402

MOTIF = "garde de comparabilité D-7, ticket 074"


# ── Le prédicat lui-même ──────────────────────────────────────────────────────────────────


def test_le_garde_porte_sur_l_emplacement_pas_sur_le_nom(tmp_path: Path) -> None:
    """Un segment `archive` dans le chemin suffit ; un NOM qui contient « archive » ne suffit pas.

    La distinction n'est pas une subtilité : une cohorte qui s'appellerait
    `population_archivistes` doit rester parfaitement lisible.
    """
    assert froid.sous_archive(tmp_path / "archive" / "2026-09-14_avant_bascule_anglaise" / "x")
    assert froid.sous_archive(tmp_path / "data" / "archive" / "jeux")
    assert not froid.sous_archive(tmp_path / "data" / "population_archivistes")
    assert not froid.sous_archive(tmp_path / "data" / "jeux" / "archivage.yaml")


def test_la_derogation_exige_un_motif_ecrit(tmp_path: Path) -> None:
    chemin = tmp_path / "archive" / "gel" / "population.json"
    garde = dict(quoi="une cohorte de population", comment_lever="écrire `archivee_confirmee`")
    with pytest.raises(froid.ContenuArchive):
        froid.verifier(chemin, None, **garde)
    with pytest.raises(froid.ContenuArchive):
        froid.verifier(chemin, "   ", **garde)   # une chaîne vide n'est pas un motif
    with pytest.raises(froid.ContenuArchive):
        froid.verifier(chemin, True, **garde)    # type: ignore[arg-type]
    froid.verifier(chemin, MOTIF, **garde)       # motif écrit → passe


def test_le_refus_dit_toujours_comment_le_lever(tmp_path: Path) -> None:
    """Un refus qui ne dit pas quoi faire se contourne au jugé, ou se subit (règle du ticket 045).

    Les trois chargeurs doivent nommer le champ concret, pas « fournir un motif ».
    """
    from experiences.jeu import Jeu

    with pytest.raises(PopulationArchivee) as pop:
        resoudre_population(_cohorte(tmp_path / "archive" / "gel" / "v5"))
    assert "population.archivee_confirmee" in str(pop.value)

    with pytest.raises(froid.ContenuArchive) as jeu:
        Jeu.charger(_jeu(tmp_path / "archive" / "gel" / "j5"))
    assert "archive_confirmee" in str(jeu.value)

    with pytest.raises(PromptsArchives) as pm:
        PromptManager(
            templates_dir=tmp_path,
            prompts_file=_store(tmp_path / "archive" / "gel" / "prompts.yaml"),
            exiger_avis_neutralite=False,
        )
    # Le store de prompts, lui, n'a AUCUNE dérogation : un prompt archivé ne se sert jamais.
    # Le message dit donc où est le store vivant, à la place.
    assert "mobility_llm/prompts/prompts.yaml" in str(pm.value)


# ── 1. Populations ────────────────────────────────────────────────────────────────────────


def _cohorte(dossier: Path) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "population.json").write_text("[]", encoding="utf-8")
    return dossier


def test_aucune_population_ne_se_resout_depuis_l_archive(tmp_path: Path) -> None:
    gelee = _cohorte(tmp_path / "archive" / "2026-09-14_avant_bascule_anglaise" / "population" / "v5")
    with pytest.raises(PopulationArchivee) as e:
        resoudre_population(gelee)
    assert "archive froide" in str(e.value)

    vivante = _cohorte(tmp_path / "data" / "population" / "population_1000_AAMAS_v6")
    fichier, _ = resoudre_population(vivante)
    assert fichier == vivante / "population.json"


def test_une_population_archivee_se_relit_avec_un_motif(tmp_path: Path) -> None:
    gelee = _cohorte(tmp_path / "archive" / "gel" / "v5")
    fichier, _ = resoudre_population(gelee, archivee_confirmee=MOTIF)
    assert fichier == gelee / "population.json"


# ── 2. Jeux scellés ───────────────────────────────────────────────────────────────────────


def _jeu(dossier: Path) -> Path:
    """Un jeu minimal mais VALIDE : le refus doit venir du garde, pas d'un manifeste bancal."""
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "MANIFEST.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "jeu1",
                "nom": dossier.name,
                "clos": False,
                "population": {"sha256": "0" * 64, "nom": "x", "n": 0},
                "dependances": {"commit": None},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    (dossier / "propositions.jsonl").write_text("", encoding="utf-8")
    return dossier


def test_aucun_jeu_ne_se_charge_depuis_l_archive(tmp_path: Path) -> None:
    from experiences.jeu import Jeu

    gele = _jeu(tmp_path / "archive" / "gel" / "plateforme" / "jeux" / "v5_20260316")
    with pytest.raises(froid.ContenuArchive) as e:
        Jeu.charger(gele)
    assert "un jeu scellé en archive froide" in str(e.value)

    # Le même dossier, ailleurs, se charge : c'est bien l'emplacement qui refuse.
    vivant = _jeu(tmp_path / "data" / "jeux" / "v6_20260316")
    assert Jeu.charger(vivant).nom == "v6_20260316"


def test_un_jeu_archive_se_relit_avec_un_motif(tmp_path: Path) -> None:
    from experiences.jeu import Jeu

    gele = _jeu(tmp_path / "archive" / "gel" / "v5_20260316")
    assert Jeu.charger(gele, archive_confirmee=MOTIF).nom == "v5_20260316"


# ── 3. Prompts système ────────────────────────────────────────────────────────────────────


def _store(chemin: Path) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(
        yaml.safe_dump(
            {
                "active": {"itinary_multi_agent": "v"},
                "prompts": {"v": {"content": "Pick a mode.\n"}},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return chemin


def test_le_prompt_manager_refuse_un_store_archive(tmp_path: Path) -> None:
    gele = _store(tmp_path / "archive" / "gel" / "prompts" / "prompts.yaml")
    with pytest.raises(PromptsArchives) as e:
        PromptManager(templates_dir=tmp_path, prompts_file=gele, exiger_avis_neutralite=False)
    assert "archive froide" in str(e.value)


def test_le_prompt_manager_sert_le_store_vivant(tmp_path: Path) -> None:
    vivant = _store(tmp_path / "packages" / "prompts" / "prompts.yaml")
    pm = PromptManager(templates_dir=tmp_path, prompts_file=vivant, exiger_avis_neutralite=False)
    assert pm.get_system_prompt("itinary_multi_agent") == "Pick a mode."


# ── 4. Ancrage du registre et de la file ──────────────────────────────────────────────────


def test_le_registre_et_la_file_s_ancrent_hors_archive() -> None:
    """`registre` et la file FIFO lisent `dossier_experiences()`, `dossier_jeux()` — jamais l'archive.

    Ce n'est pas un filtre ajouté quelque part, c'est une propriété d'ancrage : ces deux
    fonctions pointent sous `data/`, et l'archive froide vit sous `archive/`, à côté. Le test
    verrouille la propriété pour qu'un déplacement futur de l'un ou de l'autre se voie.
    """
    for dossier in (dossier_experiences(), dossier_jeux()):
        assert not froid.sous_archive(dossier), (
            f"{dossier} traverse un segment `archive` : le registre listerait du contenu gelé"
        )


def test_l_archive_du_ticket_074_n_est_pas_sous_data() -> None:
    """L'archive est un frère de `data/`, pas un enfant — sinon les ancrages ci-dessus la verraient."""
    archive = RACINE / "archive" / "2026-09-14_avant_bascule_anglaise"
    assert froid.sous_archive(archive)
    assert (RACINE / "data") not in archive.parents
