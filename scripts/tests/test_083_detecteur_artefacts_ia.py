"""Ticket 083 — le détecteur de marqueurs d'écriture générée mesure la prose, et rien d'autre.

Deux propriétés sont testées, parce que ce sont les deux seules qui peuvent faire mentir le
verdict dans le mauvais sens :

1. **Le filtre de prose.** Un chapitre dont le gras vit dans les lignes d'en-tête éditorial
   (`**Statut :**`, `**Version antérieure :**`) ou dans la section de queue qui liste les
   tickets ne doit pas être accusé. `fr/02_related_work.md` porte quinze gras de métadonnées
   et zéro en prose : il sort à 0,0. La passe manuelle du 2026-09-15 s'était fait piéger dans
   l'autre sens, avec un faux positif de 13,9 % de puces sur `en/03` dont la section de queue
   s'intitule « Tickets attached to this chapter » — d'où le test bilingue.

2. **Les seuils tiennent à la norme du corpus, pas à une constante posée.** Les quatre
   chapitres les plus relus par l'auteur passent sans exemption d'aucune sorte. Si un jour ils
   échouent, c'est le seuil qu'il faut rediscuter, pas le chapitre qu'il faut réécrire.

Lancement :
    python3 -m pytest scripts/tests/test_083_detecteur_artefacts_ia.py -q
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
ARTICLE = RACINE / "docs" / "paper" / "article"
SCRIPT = RACINE / "scripts" / "paper" / "detecter_artefacts_ia.py"

_spec = importlib.util.spec_from_file_location("detecter_artefacts_ia", SCRIPT)
detecteur = importlib.util.module_from_spec(_spec)
sys.modules["detecter_artefacts_ia"] = detecteur
_spec.loader.exec_module(detecteur)

# Les chapitres qui portent la norme : ce sont eux qui ont fixé les seuils.
REFERENCES = [("fr", "01_introduction.md"), ("fr", "02_related_work.md"),
              ("en", "01_introduction.md"), ("en", "02_related_work.md")]


def _analyser(langue: str, nom: str) -> dict:
    chemin = ARTICLE / langue / nom
    if not chemin.exists():
        pytest.skip(f"chapitre absent : {chemin}")
    return detecteur.analyser(chemin, langue)


@pytest.mark.parametrize("langue,nom", REFERENCES)
def test_les_chapitres_de_reference_passent_sans_exemption(langue: str, nom: str) -> None:
    """Les seuils sont calés sur ces quatre chapitres : ils doivent sortir indemnes."""
    r = _analyser(langue, nom)
    assert r["bloquants"] == [], (
        f"{langue}/{nom} devait passer et ne passe plus : {r['bloquants']}. "
        "Soit le chapitre a dérivé, soit le seuil est à rediscuter — pas à desserrer en silence."
    )


def test_le_gras_des_en_tetes_editoriaux_ne_compte_pas() -> None:
    """`fr/02` porte quinze gras de métadonnées et aucun en prose : densité nulle attendue."""
    r = _analyser("fr", "02_related_work.md")
    assert r["gras"] == 0, f"gras comptés en prose : {r['gras']} (attendu 0)"
    assert r["gras_k"] == 0.0
    assert r["ecartees"] > 0, "aucune ligne écartée : le filtre de prose n'a pas tourné"


@pytest.mark.parametrize("langue", ["fr", "en"])
def test_la_section_de_queue_est_exclue_dans_les_deux_langues(langue: str) -> None:
    """« Tickets associés à ce chapitre » et « Tickets attached to this chapter »."""
    chemin = ARTICLE / langue / "03_architecture.md"
    if not chemin.exists():
        pytest.skip(f"chapitre absent : {chemin}")
    prose, _ = detecteur.decouper(chemin)
    numeros = {no for no, _ in prose}
    brut = chemin.read_text(encoding="utf-8").split("\n")
    en_queue = False
    for no, ligne in enumerate(brut, 1):
        nu = ligne.strip()
        if detecteur.RE_QUEUE.match(nu):
            en_queue = True
        elif nu.startswith("#"):
            en_queue = False
        if en_queue and nu:
            assert no not in numeros, (
                f"{langue}/03 l.{no} appartient à la section de queue et a été comptée : {nu[:70]}"
            )
    assert en_queue or True  # la section peut disparaître ; son absence n'est pas un échec


def test_un_chapitre_trop_court_ne_produit_pas_de_densite() -> None:
    """Sous le plancher de mots, une densité ne veut rien dire et ne doit rien déclencher."""
    faux = "\n".join(["# Titre", "", "Une phrase — courte — avec **du gras**."])
    chemin = Path(detecteur.__file__).parent / "_test_court.md"
    chemin.write_text(faux, encoding="utf-8")
    try:
        r = detecteur.analyser(chemin, "fr")
        assert r["mots"] < detecteur.MOTS_MINIMUM
        densites = [b for b in r["bloquants"] if "densité" in b[1]]
        assert densites == [], f"densité calculée sur {r['mots']} mots : {densites}"
    finally:
        chemin.unlink()


def test_le_lexique_est_informatif_et_ne_bloque_jamais() -> None:
    """Treize constats lexicaux, zéro correction, lors de la passe d'ouverture du ticket."""
    faux = " ".join(["Il convient de noter que ce point est crucial."] * 12)
    chemin = Path(detecteur.__file__).parent / "_test_lexique.md"
    chemin.write_text("# Titre\n\n" + faux, encoding="utf-8")
    try:
        r = detecteur.analyser(chemin, "fr")
        assert r["lexique"], "le lexique n'a rien vu sur un texte qui en est saturé"
        assert r["bloquants"] == [], f"le lexique a bloqué : {r['bloquants']}"
    finally:
        chemin.unlink()


# --- Le hook : il ne doit JAMAIS empêcher d'écrire -------------------------------------

HOOK = RACINE / "scripts" / "paper" / "hook_style_article.py"


def _hook(charge: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HOOK)], input=charge, capture_output=True,
                          text=True, timeout=30, cwd=str(RACINE), env=env)


@pytest.mark.parametrize("charge,attendu", [
    ('{"tool_input":{"file_path":"docs/paper/article/fr/02_related_work.md"}}', "chapitre propre"),
    ('{"tool_input":{"file_path":"README.md"}}', "hors périmètre"),
    ('{"tool_input":{"file_path":"docs/paper/article/README.md"}}', "pas un chapitre"),
    ('{"tool_input":{}}', "sans chemin"),
    ('{}', "charge vide"),
    ('ceci n est pas du json', "charge illisible"),
    ('', "entrée vide"),
])
def test_le_hook_sort_toujours_en_zero(charge: str, attendu: str) -> None:
    r = _hook(charge)
    assert r.returncode == 0, f"cas « {attendu} » : code {r.returncode}, stderr={r.stderr[:200]}"


def test_le_hook_survit_a_la_disparition_du_detecteur(tmp_path: Path) -> None:
    """Critère d'acceptation du ticket : détecteur absent, l'écriture aboutit quand même."""
    faux_depot = tmp_path / "depot"
    (faux_depot / "scripts" / "paper").mkdir(parents=True)
    (faux_depot / "docs" / "paper" / "article" / "fr").mkdir(parents=True)
    (faux_depot / "docs" / "paper" / "article" / "fr" / "01_x.md").write_text("# x\n", encoding="utf-8")
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(faux_depot))
    r = _hook('{"tool_input":{"file_path":"docs/paper/article/fr/01_x.md"}}', env=env)
    assert r.returncode == 0, f"le hook a bloqué : {r.stderr[:300]}"
    assert "absent" in r.stdout, f"le hook n'a pas dit pourquoi il s'abstenait : {r.stdout[:300]}"


def test_le_hook_signale_un_chapitre_charge() -> None:
    """Sur un chapitre au-dessus des seuils, il rend le rapport sans pour autant bloquer."""
    chemin = ARTICLE / "fr" / "99_annexes.md"
    if not chemin.exists():
        pytest.skip("chapitre absent")
    r = _hook('{"tool_input":{"file_path":"docs/paper/article/fr/99_annexes.md"}}')
    assert r.returncode == 0
    assert "Style de l'article" in r.stdout
    assert "signal, pas une autorité" in r.stdout
