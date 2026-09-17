"""Le découpage du Makefile racine en `make/*.mk` ne doit pas faire disparaître de cibles.

Ticket 039, pas 4 : le Makefile racine ne porte plus que sa configuration et un
`include make/*.mk`. Le tableau de bord, lui, lit le Makefile comme un fichier —
sans suivi des `include`, ses 120 cibles cliquables tombent à zéro.

La panne est MUETTE : aucune exception, aucun test rouge, juste un catalogue vide.
C'est le motif que le ticket 039 a déjà rencontré (25 tests météo passés de
« réussis » à « ignorés » sans qu'aucun n'échoue). D'où ces gardes.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.dashboard import makefiles


def _cibles_racine():
    _, par_projet = makefiles.all_targets()
    return par_projet["root"]


def test_le_decoupage_ne_perd_aucune_cible():
    """Le seuil est bas exprès : ce qui se vérifie, c'est qu'on lit AU-DELÀ du fichier racine.

    Le Makefile racine ne définit plus AUCUNE cible. Un parseur qui ignore les
    `include` rend donc une liste vide, pas une liste incomplète.
    """
    cibles = _cibles_racine()
    assert len(cibles) > 100, f"{len(cibles)} cibles — les include ne sont pas suivis"
    for nom in ("up", "run", "dashboard", "help", "synthesis", "experience-lancer", "logit"):
        assert nom in {c.name for c in cibles}, f"cible `{nom}` perdue par le découpage"


def test_les_cibles_sont_reparties_sur_les_modules():
    """Une cible pointe le fichier qui la PORTE : le dashboard s'en sert pour la situer."""
    fichiers = {c.makefile.name for c in _cibles_racine()}
    assert fichiers >= {"docker.mk", "gama.mk", "experiences.mk", "choix-modal.mk"}
    assert "Makefile" not in fichiers, "le fichier racine ne doit plus porter de cible"


def test_chaque_module_est_lu():
    """Aucun `make/*.mk` ne doit rester orphelin : le joker de l'include les prend tous."""
    sur_disque = {p.name for p in (RACINE / "make").glob("*.mk")}
    lus = {f.name for f, _, _ in makefiles._lire_avec_includes(RACINE / "Makefile")}
    assert sur_disque <= lus, f"modules jamais lus : {sorted(sur_disque - lus)}"


def test_une_affectation_inexpansible_n_ecrase_pas_l_ancre(tmp_path):
    """PROJECT_ROOT est amorcé par le parseur, puis RÉAFFECTÉ par le Makefile.

    La réaffectation est une expression make ($(patsubst $(dir $(abspath …)))) que le
    parseur n'évalue pas. Si elle écrase l'amorce, le chemin d'include devient
    inexpansible et le catalogue se vide — c'est le bug qui a été corrigé.
    """
    (tmp_path / "make").mkdir()
    (tmp_path / "make" / "a.mk").write_text("## doc\ncible-a:\n\t@true\n", encoding="utf-8")
    (tmp_path / "Makefile").write_text(
        "PROJECT_ROOT := $(patsubst %/,%,$(dir $(abspath $(firstword $(MAKEFILE_LIST)))))\n"
        "include $(PROJECT_ROOT)/make/*.mk\n",
        encoding="utf-8",
    )
    lignes = makefiles._lire_avec_includes(tmp_path / "Makefile")
    assert "cible-a:" in [raw for _, _, raw in lignes]


def test_un_include_irresoluble_est_ignore_sans_planter(tmp_path):
    """Mieux vaut une cible manquante qu'un tableau de bord qui refuse de s'ouvrir."""
    (tmp_path / "Makefile").write_text(
        "include $(VARIABLE_JAMAIS_DEFINIE)\ninclude /chemin/qui/n/existe/pas.mk\n"
        "## doc\ncible-b:\n\t@true\n",
        encoding="utf-8",
    )
    lignes = makefiles._lire_avec_includes(tmp_path / "Makefile")
    assert "cible-b:" in [raw for _, _, raw in lignes]
