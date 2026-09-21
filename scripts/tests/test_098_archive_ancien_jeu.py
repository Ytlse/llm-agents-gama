"""Ticket 098 — l'ancien jeu v6 EN est gelé, et c'est le code qui le tient.

    Froid = restaurable et auditable, jamais utilisé ni référencé.

Le ticket 074 a prouvé que le PRÉDICAT refuse un chemin sous `archive/`
(`scripts/tests/test_074_archive_froide.py`, toujours en vigueur). Ce fichier-ci prouve autre
chose, et c'est la moitié qui manquait : que l'ancien jeu v6 EN **est effectivement rangé
derrière ce prédicat**, et qu'aucune des surfaces vivantes ne le voit plus.

Un garde qui fonctionne sur un contenu qu'on a oublié de ranger ne garde rien.

Ces tests sautent si l'archive n'a pas été produite (`scripts/archiver_ancien_jeu_v6_en.py
--appliquer`) : sur une machine fraîchement clonée, `data/` et `archive/` sont tous deux
absents, et un échec y serait un faux positif — ni l'un ni l'autre n'est versionné.

Lancement :
    services/llm-agents/.venv/bin/python -m pytest scripts/tests/test_098_archive_ancien_jeu.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "services" / "llm-agents"))

from experiences import froid
from experiences.experience import dossier_experiences, dossier_jeux
from experiences.journal import ouvrir

JEU_GELE = "population_1000_AAMAS_v6_20260316_EN"
JEU_COURANT = "population_1000_AAMAS_v6_20260316_EN_c"
ARCHIVE = RACINE / "archive" / "2026-09-21_ancien_jeu_v6_EN"
MOTIF = "audit ticket 098"

gelee = pytest.mark.skipif(
    not (ARCHIVE / "MANIFEST.yaml").is_file(),
    reason="archive du ticket 098 absente — lancer scripts/archiver_ancien_jeu_v6_en.py --appliquer",
)


def _jeu_declare(dossier: Path) -> str | None:
    """Le jeu que déclare `experience.yaml`, lu comme le script de gel le lit."""
    try:
        conf = yaml.safe_load((dossier / "experience.yaml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    jeu = conf.get("jeu")
    if isinstance(jeu, dict):
        jeu = jeu.get("nom")
    return jeu.strip() if isinstance(jeu, str) and jeu.strip() else None


# ── 1. Ce qui reste à chaud ───────────────────────────────────────────────────────────────


@gelee
def test_plus_aucune_experience_vivante_ne_declare_l_ancien_jeu() -> None:
    """La surface que le tableau de bord et le registre listent ne porte plus rien de gelé.

    Le test lit la DÉCLARATION de chaque `experience.yaml`, pas le nom du dossier : `…_EN` est
    un préfixe de `…_EN_c`, et un filtre par nom rangerait le jeu corrigé avec l'ancien.
    """
    restantes = [
        d.name
        for d in sorted(dossier_experiences().iterdir())
        if (d / "experience.yaml").is_file() and _jeu_declare(d) == JEU_GELE
    ]
    assert not restantes, (
        f"{len(restantes)} expérience(s) déclarent encore le jeu gelé : {restantes[:5]}"
    )


@gelee
def test_le_substrat_gele_n_est_plus_proposable() -> None:
    """Un jeu resté sous `data/jeux/` continuerait d'être proposé (R17) — le défaut du ticket 045."""
    assert not (dossier_jeux() / JEU_GELE).exists()
    assert (dossier_jeux() / JEU_COURANT).is_dir(), "la référence courante, elle, doit rester là"


@gelee
def test_le_jeu_courant_n_a_pas_ete_emporte_par_le_prefixe() -> None:
    """`…_EN` préfixe `…_EN_c` : la vraie erreur à craindre est de geler les deux.

    Le compte tient lieu de preuve : les 38 exécutions du jeu corrigé sont toujours là.
    """
    vivantes = [
        d for d in dossier_experiences().iterdir()
        if (d / "experience.yaml").is_file() and _jeu_declare(d) == JEU_COURANT
    ]
    assert len(vivantes) >= 30, f"seulement {len(vivantes)} expériences sur le jeu courant"


# ── 2. Ce qui est parti, et ce qu'il faut pour le relire ──────────────────────────────────


@gelee
def test_l_archive_porte_bien_le_substrat_et_ses_executions() -> None:
    manifeste = yaml.safe_load((ARCHIVE / "MANIFEST.yaml").read_text(encoding="utf-8"))
    assert manifeste["version"] == "froid1"
    assert manifeste["ticket"] == "098"
    assert manifeste["jeu_gele"] == JEU_GELE
    assert (ARCHIVE / "plateforme" / "jeux" / JEU_GELE).is_dir()
    assert (ARCHIVE / "plateforme" / "experiences").is_dir()
    # Chaque entrée dit d'où elle vient et avec quelle empreinte : une archive dont on ne sait
    # plus l'origine n'est pas une archive, c'est une perte.
    for entree in manifeste["contenu"]:
        assert entree["origine"] and len(entree["sha256"]) == 64


@gelee
def test_l_archive_n_est_pas_sous_data() -> None:
    """Frère de `data/`, pas enfant — sinon les ancrages du registre la verraient."""
    assert froid.sous_archive(ARCHIVE)
    assert (RACINE / "data") not in ARCHIVE.parents
    for ancre in (dossier_experiences(), dossier_jeux()):
        assert not froid.sous_archive(ancre)


@gelee
def test_ouvrir_une_execution_gelee_est_refuse_sans_motif() -> None:
    """Le cœur du ticket : gelé ne veut pas dire caché, il veut dire refusé.

    Et le refus doit DIRE comment passer outre — un refus muet se contourne au jugé, ou se subit.
    """
    executions = sorted((ARCHIVE / "plateforme" / "experiences").glob("*/executions/*"))
    if not executions:
        pytest.skip("aucune exécution dans l'archive")
    execution = executions[0]

    with pytest.raises(froid.ContenuArchive) as refus:
        ouvrir(execution)
    message = str(refus.value)
    assert "archive froide" in message
    assert "--motif-archive" in message, "le refus doit dire comment déroger"

    for pas_un_motif in (None, "", "   ", True):
        with pytest.raises(froid.ContenuArchive):
            ouvrir(execution, motif_archive=pas_un_motif)  # type: ignore[arg-type]


@gelee
def test_la_derogation_passe_avec_un_motif_ecrit() -> None:
    """Restaurable et auditable : avec un motif, la lecture aboutit — et se journalise."""
    executions = sorted((ARCHIVE / "plateforme" / "experiences").glob("*/executions/*"))
    execution = next(
        (e for e in executions if (e / "execution.yaml").is_file()), None
    )
    if execution is None:
        pytest.skip("aucune exécution clôturée dans l'archive")
    assert ouvrir(execution, motif_archive=MOTIF) is not None


# ── 3. Ce que la déclaration de référence en dit ──────────────────────────────────────────


@gelee
def test_reference_yaml_dit_ou_le_substrat_est_parti() -> None:
    """Le grisé d'hier doit se relire demain : « où est passé ce jeu ? » a une réponse écrite."""
    fichier = RACINE / "services/llm-agents/experiences/jeux/reference.yaml"
    declare = yaml.safe_load(fichier.read_text(encoding="utf-8"))
    assert declare["jeu"] == JEU_COURANT
    ancien = next(a for a in declare["anciens"] if a["jeu"] == JEU_GELE)
    assert ancien["archive_froide"] == str(ARCHIVE.relative_to(RACINE))
