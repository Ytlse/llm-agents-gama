"""Colonne `jeu` et grisé des lignes hors substrat de référence.

Spec `specs/tableau-experiences-colonnes-et-filtres.md`, règles R21 et R22.

Le fil : un composite ne se compare qu'à l'intérieur d'un même jeu. Le tableau doit donc dire
sur QUEL jeu chaque exécution a tourné — celui figé dans l'exécution, jamais celui que la
définition désigne aujourd'hui — et distinguer à l'œil ce qui ne se compare pas.
"""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.dashboard import experiences as D  # noqa: E402

REF = "jeu_corrige"
ANCIEN = "jeu_ancien"


class RerunDemande(Exception):
    """Ce que lève `st.rerun` : dans Streamlit il interrompt le script, ici aussi."""


class FauxSt:
    """Le strict nécessaire pour dessiner le tableau et relire ce qui en sort."""

    def __init__(self, event=None):
        self.session_state: dict = {}
        self.legendes: list[str] = []
        self.textes: list[str] = []
        self.avis: list[str] = []
        self.alertes: list[str] = []
        self.options: dict = {}
        self.tables: list = []          # ce que Streamlit a reçu, Styler compris
        self.event = event

    def columns(self, spec, **_k):
        n = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
        return [self] * n

    @contextlib.contextmanager
    def expander(self, label, expanded=False):
        yield self

    @contextlib.contextmanager
    def popover(self, label, **_k):
        yield self

    @contextlib.contextmanager
    def container(self, **_k):
        yield self

    def empty(self):
        return self

    def fragment(self, run_every=None):
        self.run_every = run_every
        return lambda fonction: fonction

    def rerun(self, scope=None):
        raise RerunDemande()

    def multiselect(self, label, options, default=None, key=None, **_k):
        self.options[key] = list(options)
        return self.session_state.get(key, list(default or []))

    def selectbox(self, label, options, index=0, key=None, **_k):
        options = list(options)
        return self.session_state.setdefault(key, options[index] if options else None)

    def text_input(self, label, value="", key=None, **_k):
        return self.session_state.setdefault(key, value)

    def number_input(self, label, *args, value=None, key=None, **_k):
        return self.session_state.get(key, args[2] if len(args) >= 3 else value)

    def checkbox(self, label, value=False, key=None, **_k):
        return self.session_state.get(key, value)

    def button(self, label, key=None, **_k):
        return False

    def dataframe(self, donnees, **_k):
        self.tables.append(donnees)
        return self.event

    def caption(self, texte, **_k):
        self.legendes.append(texte)

    def markdown(self, texte, **_k):
        self.textes.append(texte)

    def info(self, texte, **_k):
        self.avis.append(texte)

    def warning(self, texte, **_k):
        self.alertes.append(texte)

    def error(self, texte, **_k):
        self.alertes.append(texte)

    def success(self, texte, **_k):
        self.avis.append(texte)

    def progress(self, valeur, text=""):
        self.textes.append(text)

    def subheader(self, texte, **_k):
        self.textes.append(texte)

    def divider(self):
        pass

    def toast(self, *_a, **_k):
        pass

    def code(self, *_a, **_k):
        pass

    @property
    def tout(self) -> str:
        return "\n".join(self.legendes + self.textes + self.avis + self.alertes)


def _ecrire(chemin: Path, contenu) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    if chemin.suffix == ".json":
        chemin.write_text(json.dumps(contenu), encoding="utf-8")
    else:
        chemin.write_text(yaml.safe_dump(contenu, allow_unicode=True), encoding="utf-8")


@pytest.fixture(autouse=True)
def vue_isolee(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "ETAT_VUE_REGISTRE", tmp_path / "vue" / "vue.yaml")


@pytest.fixture
def reference(tmp_path, monkeypatch):
    """Le fichier versionné qui désigne le substrat de référence."""
    chemin = tmp_path / "jeux" / "reference.yaml"
    _ecrire(chemin, {"jeu": REF, "depuis": "2026-09-16"})
    monkeypatch.setattr(D, "JEU_REFERENCE_YAML", chemin)
    return chemin


@pytest.fixture
def plateforme(tmp_path, monkeypatch):
    """Deux expériences dont les DÉFINITIONS nomment toutes deux le jeu corrigé…

    …mais dont une seule a réellement tourné dessus : `exp_vieille` a couru sur l'ancien
    substrat, et son instantané d'exécution le dit. C'est exactement l'état laissé par le
    ticket 088, où les définitions ont été re-pointées après coup.
    """
    exps = tmp_path / "experiences"
    for nom, jeu_execute in (("exp_a_jour", REF), ("exp_vieille", ANCIEN)):
        definition = {"nom": nom, "mode": "sans_simulateur", "jeu": {"nom": REF},
                      "decideur": {"type": "passerelle", "modele": "m1"},
                      "gabarit": {"variante": "b_min"}}
        _ecrire(exps / nom / "experience.yaml", definition)
        d = exps / nom / "executions" / "2026-09-10_08_00_00"
        _ecrire(d / "etat.json", {"etat": "terminee"})
        _ecrire(d / "compteurs.json", {"couverture": {"taux": 0.99, "decides": 99, "attendus": 100}})
        _ecrire(d / "execution.yaml",
                {"cree_le": "2026-09-10T08:00:00", "experience": {**definition, "jeu": {"nom": jeu_execute}}})
    monkeypatch.setattr(D, "DOSSIER", exps)
    monkeypatch.setattr(D, "DOSSIER_JEUX", tmp_path / "jeux_inexistants")
    return exps


def _dessiner(st) -> None:
    with contextlib.suppress(RerunDemande):
        D._suivi_du_registre(st, pd)


def _lignes(nom_a_jeu: dict) -> list[dict]:
    return [{"experience": n, "execution": "e", "etat": "terminee", "jeu": j,
             "hors_reference": D.hors_reference(j, REF)} for n, j in nom_a_jeu.items()]


# ── R21 — la colonne dit le jeu RÉELLEMENT couru ─────────────────────────────


def test_R21_le_jeu_affiche_est_celui_fige_dans_l_execution(plateforme, reference):
    """La définition dit « corrigé » pour les deux ; l'archive dit la vérité pour chacune."""
    par_exp = {l["experience"]: l for l in D.lister() if l.get("execution")}
    assert par_exp["exp_a_jour"]["jeu"] == REF
    assert par_exp["exp_vieille"]["jeu"] == ANCIEN, "la définition re-pointée a masqué l'archive"


def test_R21_une_experience_jamais_lancee_montre_le_jeu_qu_elle_designe(plateforme, reference):
    """Sans exécution il n'y a rien à figer : la définition est la seule source honnête."""
    _ecrire(plateforme / "exp_definie" / "experience.yaml",
            {"nom": "exp_definie", "mode": "sans_simulateur", "jeu": {"nom": REF},
             "decideur": {"type": "passerelle", "modele": "m1"}})
    ligne = next(l for l in D.lister() if l["experience"] == "exp_definie")
    assert ligne["jeu"] == REF and ligne["hors_reference"] is False


def test_R21_la_colonne_jeu_est_affichee_sans_qu_on_la_rappelle(plateforme, reference):
    st = FauxSt()
    _dessiner(st)
    assert "jeu" in getattr(st.tables[-1], "data", st.tables[-1]).columns


def test_R21_un_jeu_absent_s_ecrit_tiret_jamais_une_case_vide(plateforme, reference):
    _ecrire(plateforme / "exp_sans_jeu" / "experience.yaml",
            {"nom": "exp_sans_jeu", "mode": "sans_simulateur",
             "decideur": {"type": "passerelle", "modele": "m1"}})
    st = FauxSt()
    _dessiner(st)
    vue = getattr(st.tables[-1], "data", st.tables[-1])
    assert (vue.loc[vue["experience"] == "exp_sans_jeu", "jeu"] == "—").all()


# ── R22 — le grisé ───────────────────────────────────────────────────────────


def test_R22_seules_les_lignes_hors_reference_sont_grisees(plateforme, reference):
    st = FauxSt()
    _dessiner(st)
    style = st.tables[-1]
    assert hasattr(style, "data"), "hors référence : Streamlit doit recevoir un Styler"
    rendu = style.data.copy()
    applique = style._compute().ctx  # {(ligne, colonne): [styles]}
    gris = {i for (i, _), styles in applique.items()
            if any("color" in str(s) for s in styles)}
    hors = {i for i, nom in enumerate(rendu["experience"]) if nom == "exp_vieille"}
    assert gris == hors, f"grisées {gris}, attendues {hors}"


def test_R22_le_nombre_de_lignes_grisees_est_dit(plateforme, reference):
    st = FauxSt()
    _dessiner(st)
    assert any("1 ligne(s) grisée(s)" in l and REF in l for l in st.legendes), st.legendes


def test_R22_sans_reference_designee_rien_n_est_grise_et_la_page_le_dit(plateforme, tmp_path,
                                                                       monkeypatch):
    monkeypatch.setattr(D, "JEU_REFERENCE_YAML", tmp_path / "absent.yaml")
    assert D.jeu_reference() is None
    st = FauxSt()
    _dessiner(st)
    assert not hasattr(st.tables[-1], "data"), "aucune référence : aucun style à poser"
    assert any("Aucun jeu de référence" in l for l in st.legendes), st.legendes


def test_R22_une_reference_illisible_ne_grise_pas(plateforme, tmp_path, monkeypatch):
    """Un fichier abîmé ne doit ni lever ni griser : il n'y a plus de référence, c'est tout."""
    abime = tmp_path / "reference.yaml"
    abime.write_text("jeu: [pas, une, chaine\n", encoding="utf-8")
    monkeypatch.setattr(D, "JEU_REFERENCE_YAML", abime)
    assert D.jeu_reference() is None


def test_R22_le_grise_ne_touche_ni_le_tri_ni_les_filtres(plateforme, reference):
    """Le style vit sur la copie affichée : les valeurs filtrables restent nues (R11, R15)."""
    st = FauxSt()
    _dessiner(st)
    vue = st.tables[-1].data
    assert set(vue["jeu"]) == {REF, ANCIEN}, "le nom du jeu n'est pas décoré"
    assert D.hors_reference(ANCIEN, REF) and not D.hors_reference(REF, REF)


def test_R22_aucune_designation_ne_vaut_pas_hors_reference():
    """Sans référence, aucune ligne n'est fautive — on ne grise que ce qu'on sait faux."""
    assert D.hors_reference(ANCIEN, None) is False
    assert D.hors_reference(None, REF) is False
