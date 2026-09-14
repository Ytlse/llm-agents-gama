"""Colonnes affichées et filtre par colonne du tableau « Mes expériences ».

Spec `specs/tableau-experiences-colonnes-et-filtres.md` — un test par règle, nommé par elle.

Le fil de ces tests : un filtre est une VUE. Il ne touche pas au disque, il ne fait jamais
disparaître une ligne sans la compter, et il ne doit pas pouvoir cacher en silence ce qui a
été produit après qu'on l'a posé — d'autant qu'il survit maintenant à la fermeture de la page.
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


# ── Un Streamlit de poche ────────────────────────────────────────────────────


class RerunDemande(Exception):
    """Ce que lève `st.rerun` : dans Streamlit il interrompt le script, ici aussi."""


class FauxSt:
    """Le nécessaire de l'API Streamlit pour dessiner le tableau et ses filtres.

    `columns`, `expander` et `popover` rendent cet objet lui-même : tout ce qui est dessiné
    se retrouve dans les mêmes listes, quelle que soit la boîte qui le contient.
    """

    def __init__(self, event=None):
        self.session_state: dict = {}
        self.legendes: list[str] = []
        self.textes: list[str] = []
        self.avis: list[str] = []
        self.alertes: list[str] = []
        self.popovers: list[str] = []
        self.boutons: list[str] = []
        self.options: dict = {}
        self.tables: list = []
        self.clics: set = set()
        self.reruns: list = []
        self.event = event

    # — conteneurs —
    def columns(self, spec, **_k):
        n = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
        return [self] * n

    @contextlib.contextmanager
    def expander(self, label, expanded=False):
        yield self

    @contextlib.contextmanager
    def popover(self, label, **_k):
        self.popovers.append(label)
        yield self

    @contextlib.contextmanager
    def container(self, **_k):
        yield self

    @contextlib.contextmanager
    def spinner(self, *_a, **_k):
        yield self

    def empty(self):
        return self

    def fragment(self, run_every=None):
        self.run_every = run_every
        return lambda fonction: fonction

    def rerun(self, scope=None):
        self.reruns.append(scope)
        raise RerunDemande()

    # — widgets —
    def multiselect(self, label, options, default=None, key=None, **_k):
        self.options[key] = list(options)
        return self.session_state.get(key, list(default or []))

    def selectbox(self, label, options, index=0, key=None, **_k):
        options = list(options)
        return self.session_state.setdefault(key, options[index] if options else None)

    def text_input(self, label, value="", key=None, **_k):
        return self.session_state.setdefault(key, value)

    def text_area(self, label, value="", key=None, **_k):
        return self.session_state.setdefault(key, value)

    def number_input(self, label, *args, value=None, key=None, **_k):
        if len(args) >= 3:
            val = args[2]
        elif args:
            val = args[0]
        else:
            val = value
        return self.session_state.get(key, val)

    def checkbox(self, label, value=False, key=None, **_k):
        return self.session_state.get(key, value)

    def radio(self, label, options, index=0, key=None, **_k):
        options = list(options)
        return self.session_state.setdefault(key, options[index] if options else None)

    def date_input(self, label, value=None, key=None, **_k):
        return self.session_state.setdefault(key, value)

    def button(self, label, key=None, **_k):
        self.boutons.append(label)
        return key in self.clics

    def dataframe(self, donnees, **_k):
        self.tables.append(donnees)
        return self.event

    # — écritures —
    def caption(self, texte, **_k):
        self.legendes.append(texte)

    def markdown(self, texte, **_k):
        self.textes.append(texte)

    def info(self, texte, **_k):
        self.avis.append(texte)

    def warning(self, texte, **_k):
        self.alertes.append(texte)

    def success(self, texte, **_k):
        self.avis.append(texte)

    def error(self, texte, **_k):
        self.alertes.append(texte)

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
        return "\n".join(self.legendes + self.textes + self.avis + self.alertes + self.popovers)


class FauxEvent:
    def __init__(self, rows):
        self.selection = {"rows": list(rows)}


# ── Données ──────────────────────────────────────────────────────────────────

LIGNES = [
    {"experience": "exp_a", "execution": "2026-09-10_08_00_00", "etat": "terminee",
     "fournisseur": "google", "prompt": "minper", "composite_l1": 0.20, "couverture": 0.99},
    {"experience": "exp_b", "execution": "2026-09-10_09_00_00", "etat": "terminee",
     "fournisseur": "mistral", "prompt": "promin", "composite_l1": 0.40, "couverture": 0.98},
    {"experience": "exp_c", "execution": "2026-09-10_10_00_00", "etat": "en_cours",
     "fournisseur": "google", "prompt": None, "composite_l1": None, "couverture": None},
]
COLONNES = ["experience", "execution", "etat", "fournisseur", "prompt", "couverture", "composite_l1"]


def _ecrire(chemin: Path, contenu) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    if chemin.suffix == ".json":
        chemin.write_text(json.dumps(contenu), encoding="utf-8")
    else:
        chemin.write_text(yaml.safe_dump(contenu, allow_unicode=True), encoding="utf-8")


@pytest.fixture(autouse=True)
def vue_isolee(tmp_path, monkeypatch):
    """La mémoire de la vue vit dans le tmp : aucun test n'écrit dans `experiments/`."""
    monkeypatch.setattr(D, "ETAT_VUE_REGISTRE", tmp_path / "vue" / "vue.yaml")
    return tmp_path / "vue" / "vue.yaml"


@pytest.fixture
def plateforme(tmp_path, monkeypatch):
    """Trois expériences : deux terminées et scorées, une en cours jamais scorée."""
    exps = tmp_path / "experiences"
    for nom, fournisseur, etat, score in (("exp_a", "google", "terminee", 0.20),
                                          ("exp_b", "mistral", "terminee", 0.40),
                                          ("exp_c", "google", "en_cours", None)):
        _ecrire(exps / nom / "experience.yaml",
                {"nom": nom, "mode": "sans_simulateur", "jeu": {"nom": "j1"},
                 "decideur": {"type": "passerelle", "modele": "m1"},
                 "gabarit": {"variante": "b_min"}})
        d = exps / nom / "executions" / f"2026-09-1{'012'[('exp_a', 'exp_b', 'exp_c').index(nom)]}_08_00_00"
        _ecrire(d / "etat.json", {"etat": etat})
        _ecrire(d / "compteurs.json", {"couverture": {"taux": 0.99, "decides": 99, "attendus": 100}})
        if score is not None:
            _ecrire(d / "scores.json", {"composite": {"l1": score, "emd_jsd": score},
                                        "formule": {"nom": "reference", "sha256": "sha-perimee"}})
    monkeypatch.setattr(D, "DOSSIER", exps)
    monkeypatch.setattr(D, "DOSSIER_JEUX", tmp_path / "jeux")
    return exps


def _dessiner(st) -> None:
    """Un dessin complet du tableau, comme le fragment le fait toutes les 5 s."""
    with contextlib.suppress(RerunDemande):
        D._suivi_du_registre(st, pd)


# ── R1 · R2 — les colonnes affichées ─────────────────────────────────────────


def test_R1_dix_colonnes_par_defaut_dans_l_ordre_annonce():
    st = FauxSt()
    presentes = list(D.COLONNES_REGISTRE)
    choix = D._panneau_colonnes_et_filtres(st, LIGNES, presentes, "")
    assert choix["colonnes"] == list(D.COLONNES_REGISTRE_DEFAUT)
    for sortie in ("scores", "jeu", "jeu_etat", "chaine", "formule"):
        assert sortie not in choix["colonnes"], sortie


def test_R2_une_colonne_rappelee_reprend_sa_place():
    """Rappelée, `jeu` se replace entre `prompt` et `mode` — jamais recollée en bout de ligne."""
    st = FauxSt()
    presentes = list(D.COLONNES_REGISTRE)
    D._panneau_colonnes_et_filtres(st, LIGNES, presentes, "")
    st.session_state[D._cle_vue(st, "colonnes")] = list(D.COLONNES_REGISTRE_DEFAUT) + ["jeu"]
    colonnes = D._panneau_colonnes_et_filtres(st, LIGNES, presentes, "")["colonnes"]
    assert colonnes.index("prompt") < colonnes.index("jeu") < colonnes.index("mode")


def test_R2_les_cinq_colonnes_restent_proposees_au_selecteur():
    st = FauxSt()
    D._panneau_colonnes_et_filtres(st, LIGNES, list(D.COLONNES_REGISTRE), "")
    assert set(st.options[D._cle_vue(st, "colonnes")]) == set(D.COLONNES_REGISTRE)


# ── R3 — l'avertissement ne tombe pas avec la colonne ────────────────────────


def test_R3_une_formule_perimee_est_dite_meme_colonne_formule_masquee(plateforme, monkeypatch):
    monkeypatch.setattr(D, "_formule_reference_sha", lambda: "sha-courante")
    st = FauxSt(event=FauxEvent([]))
    _dessiner(st)
    assert "formule" not in D.COLONNES_REGISTRE_DEFAUT
    assert any("PÉRIMÉE" in a for a in st.alertes), st.alertes


def test_R3_sans_ligne_perimee_aucun_avertissement(plateforme, monkeypatch):
    monkeypatch.setattr(D, "_formule_reference_sha", lambda: "sha-perimee")  # identique aux scores
    st = FauxSt(event=FauxEvent([]))
    _dessiner(st)
    assert not any("PÉRIMÉE" in a for a in st.alertes), st.alertes


# ── R4 à R6 — le filtre par valeurs ──────────────────────────────────────────


def test_R4_decocher_une_valeur_retire_ses_lignes():
    garde = D.appliquer_filtres(LIGNES, COLONNES, retenues={"etat": ["terminee"]})
    assert garde == [True, True, False]


def test_R5_les_colonnes_se_combinent_en_et_les_valeurs_en_ou():
    garde = D.appliquer_filtres(LIGNES, COLONNES,
                                retenues={"etat": ["terminee"], "fournisseur": ["google", "mistral"]})
    assert garde == [True, True, False]
    garde = D.appliquer_filtres(LIGNES, COLONNES,
                                retenues={"etat": ["terminee"], "fournisseur": ["mistral"]})
    assert garde == [False, True, False]


def test_R6_l_absence_de_valeur_se_filtre_sous_son_propre_nom():
    assert D.valeurs_filtrables(LIGNES, "prompt") == ["minper", "promin", D.VALEUR_VIDE]
    garde = D.appliquer_filtres(LIGNES, COLONNES, retenues={"prompt": ["minper", "promin"]})
    assert garde == [True, True, False], "la ligne sans prompt, et elle seule, sort"


# ── R7 — ce qui est filtré se voit et se compte ──────────────────────────────


def test_R7_le_selecteur_d_une_colonne_filtree_porte_son_compte():
    st = FauxSt()
    st.session_state[D._cle_vue(st, "val-fournisseur")] = ["google"]
    st.session_state[D._cle_vue(st, "vues-fournisseur")] = ["google", "mistral"]
    D._panneau_colonnes_et_filtres(st, LIGNES, list(D.COLONNES_REGISTRE), "")
    assert any(p.startswith("🔹 fournisseur") and "1/2" in p for p in st.popovers), st.popovers


def test_R7_le_nombre_de_lignes_affichees_est_dit(plateforme):
    st = FauxSt(event=FauxEvent([]))
    st.session_state[D._cle_vue(st, "val-etat")] = ["terminee"]
    st.session_state[D._cle_vue(st, "vues-etat")] = ["en_cours", "terminee"]
    _dessiner(st)
    assert any("2 ligne(s) affichée(s) sur 3" in c for c in st.legendes), st.legendes


# ── R8 — réinitialiser ───────────────────────────────────────────────────────


def test_R8_reinitialiser_rend_toutes_les_lignes():
    st = FauxSt()
    st.session_state.update({D._cle_vue(st, "filtre"): "google", D._cle_vue(st, "colonnes"): ["etat"],
                             D._cle_vue(st, "val-etat"): ["terminee"],
                             D._cle_vue(st, "vues-etat"): ["en_cours", "terminee"],
                             D._cle_vue(st, "min-composite_l1"): 0.1,
                             "_vue_registre": {"exclues": {"etat": ["en_cours"]}}})
    D._oublier_filtres(st)
    assert st.session_state == {"_vue_registre": {}, "_vue_version": 1,
                                "_vue_registre_restauree": False}
    choix = D._panneau_colonnes_et_filtres(st, LIGNES, list(D.COLONNES_REGISTRE), "")
    assert D.appliquer_filtres(LIGNES, choix["colonnes"], retenues=choix["retenues"],
                               bornes=choix["bornes"]) == [True, True, True]


def test_R8_les_widgets_changent_de_cle_au_lieu_d_etre_effaces():
    """Streamlit renvoie l'état d'un widget depuis le navigateur : une clé simplement
    supprimée revenait garnie, et le tableau restait filtré alors que la mémoire était vide."""
    st = FauxSt()
    avant = D._cle_vue(st, "val-etat")
    st.session_state[avant] = ["terminee"]
    D._oublier_filtres(st)
    assert D._cle_vue(st, "val-etat") != avant, "la génération doit changer"
    assert avant not in st.session_state


def test_R8_le_bouton_de_reinitialisation_est_offert():
    st = FauxSt()
    D._panneau_colonnes_et_filtres(st, LIGNES, list(D.COLONNES_REGISTRE), "")
    assert any("Réinitialiser" in b for b in st.boutons), st.boutons


# ── R9 — les filtres survivent au battement du fragment ──────────────────────


def test_R9_un_filtre_survit_au_redessin(plateforme):
    st = FauxSt(event=FauxEvent([]))
    st.session_state[D._cle_vue(st, "val-experience")] = ["exp_b"]
    st.session_state[D._cle_vue(st, "vues-experience")] = ["exp_a", "exp_b", "exp_c"]
    _dessiner(st)
    _dessiner(st)  # le fragment rebat cinq secondes plus tard
    assert st.session_state[D._cle_vue(st, "val-experience")] == ["exp_b"]
    assert any("1 ligne(s) affichée(s) sur 3" in c for c in st.legendes), st.legendes


# ── R10 — un critère invisible ne filtre pas ─────────────────────────────────


def test_R10_un_filtre_sur_une_colonne_masquee_est_ignore():
    garde = D.appliquer_filtres(LIGNES, ["experience", "etat"], retenues={"fournisseur": ["mistral"]})
    assert garde == [True, True, True]


def test_R10_masquer_une_colonne_retire_son_filtre_du_choix():
    st = FauxSt()
    st.session_state[D._cle_vue(st, "val-fournisseur")] = ["google"]
    st.session_state[D._cle_vue(st, "vues-fournisseur")] = ["google", "mistral"]
    st.session_state[D._cle_vue(st, "colonnes")] = ["experience", "etat"]
    choix = D._panneau_colonnes_et_filtres(st, LIGNES, list(D.COLONNES_REGISTRE), "")
    assert "fournisseur" not in choix["retenues"]
    assert D.appliquer_filtres(LIGNES, choix["colonnes"], retenues=choix["retenues"]) == [True] * 3


# ── R11 — les valeurs proposées ne dépendent pas des autres filtres ──────────


def test_R11_le_selecteur_d_une_colonne_ignore_les_filtres_voisins():
    st = FauxSt()
    st.session_state[D._cle_vue(st, "val-fournisseur")] = ["mistral"]
    st.session_state[D._cle_vue(st, "vues-fournisseur")] = ["google", "mistral"]
    D._panneau_colonnes_et_filtres(st, LIGNES, list(D.COLONNES_REGISTRE), "")
    assert st.options[D._cle_vue(st, "val-etat")] == ["en_cours", "terminee"], \
        "les états des lignes Google restent proposés, sinon on ne pourrait plus les recocher"


# ── R12 — les valeurs du registre bougent sous le filtre ─────────────────────


def test_R12_une_valeur_qui_apparait_arrive_cochee():
    assert D.retenues_a_jour(["google", "mistral", "openai"], ["google"], ["google", "mistral"]) \
        == ["google", "openai"]


def test_R12_une_valeur_disparue_est_oubliee_sans_erreur():
    assert D.retenues_a_jour(["google"], ["google", "mistral"], ["google", "mistral"]) == ["google"]
    assert D.appliquer_filtres(LIGNES, COLONNES, retenues={"fournisseur": ["disparu"]}) == [False] * 3


# ── R13 — les actions portent sur la ligne affichée ──────────────────────────


def test_R13_les_actions_nomment_la_ligne_cochee_apres_filtrage(plateforme):
    st = FauxSt(event=FauxEvent([1]))
    # Trié par exécution décroissante, le tableau montre exp_c puis exp_a : la deuxième
    # ligne AFFICHÉE est exp_a, alors que l'indice 1 du registre non filtré serait exp_b.
    st.session_state[D._cle_vue(st, "val-experience")] = ["exp_a", "exp_c"]
    st.session_state[D._cle_vue(st, "vues-experience")] = ["exp_a", "exp_b", "exp_c"]
    _dessiner(st)
    assert any("Actions sur « exp_a »" in t for t in st.textes), st.textes


# ── R14 — une exécution qui tourne reste pilotable ───────────────────────────


def test_R14_une_execution_en_cours_filtree_garde_ses_boutons(plateforme):
    st = FauxSt(event=FauxEvent([]))
    st.session_state[D._cle_vue(st, "val-etat")] = ["terminee"]  # exp_c (en cours) sort du tableau
    st.session_state[D._cle_vue(st, "vues-etat")] = ["en_cours", "terminee"]
    _dessiner(st)
    assert any("exp_c" in t and "en cours" in t for t in st.textes), st.textes


# ── R15 — un filtre n'écrit rien dans les données ────────────────────────────


def test_R15_filtrer_ne_touche_ni_les_experiences_ni_les_masques(plateforme):
    avant = {p: p.read_bytes() for p in plateforme.rglob("*") if p.is_file()}
    st = FauxSt(event=FauxEvent([]))
    st.session_state.update({D._cle_vue(st, "val-etat"): ["terminee"],
                             D._cle_vue(st, "vues-etat"): ["en_cours", "terminee"],
                             D._cle_vue(st, "min-composite_l1"): 0.3,
                             D._cle_vue(st, "filtre"): "exp_"})
    _dessiner(st)
    apres = {p: p.read_bytes() for p in plateforme.rglob("*") if p.is_file()}
    assert apres == avant


# ── R16 — la recherche est littérale ─────────────────────────────────────────


def test_R16_le_filtre_texte_n_est_pas_une_expression_reguliere():
    lignes = [{"experience": "exp_(alea"}, {"experience": "exp_durmin"}]
    assert D.appliquer_filtres(lignes, ["experience"], texte="exp_(alea") == [True, False]


def test_R16_le_filtre_texte_ignore_la_casse_et_cherche_partout():
    assert D.appliquer_filtres(LIGNES, COLONNES, texte="MISTRAL") == [False, True, False]


# ── R17 — les colonnes numériques se filtrent par bornes ─────────────────────


def test_R17_les_bornes_sont_incluses_et_les_non_scorees_optionnelles():
    sans = D.appliquer_filtres(LIGNES, COLONNES, bornes={"composite_l1": (0.10, 0.30, False)})
    assert sans == [True, False, False], "la ligne à « — » sort quand la case est décochée"
    avec = D.appliquer_filtres(LIGNES, COLONNES, bornes={"composite_l1": (0.10, 0.30, True)})
    assert avec == [True, False, True]
    bord = D.appliquer_filtres(LIGNES, COLONNES, bornes={"composite_l1": (0.20, 0.20, False)})
    assert bord == [True, False, False], "la borne est incluse"


def test_R17_une_borne_absente_ne_borne_pas():
    assert D.appliquer_filtres(LIGNES, COLONNES, bornes={"composite_l1": (None, 0.30, False)}) \
        == [True, False, False]


# ── R18 — la vue survit à la fermeture du tableau de bord ────────────────────


def test_R18_ce_qui_est_ecrit_se_relit(vue_isolee):
    D.sauver_vue_registre(colonnes=["experience", "etat", "chaine"], exclues={"etat": ["en_cours"]},
                          bornes={"composite_l1": (0.1, None, False)}, texte="exp_")
    vue = D.charger_vue_registre()
    assert vue["ajoutees"] == ["chaine"]
    assert "experience" not in vue.get("retirees", []) and "mode" in vue["retirees"]
    assert vue["exclues"] == {"etat": ["en_cours"]}
    assert vue["bornes"] == {"composite_l1": (0.1, None, False)}
    assert vue["texte"] == "exp_"


def test_R18_une_colonne_absente_ce_jour_la_n_est_pas_retenue_comme_masquee(vue_isolee):
    """Un registre sans exécution scorée n'expose pas `composite_l1` : l'enregistrer comme
    « retirée » la perdrait pour toujours, alors que personne ne l'a jamais décochée."""
    offertes = [c for c in D.COLONNES_REGISTRE_DEFAUT if c != "composite_l1"]
    D.sauver_vue_registre(colonnes=offertes, presentes=offertes, exclues={}, bornes={}, texte="")
    assert "composite_l1" not in D.charger_vue_registre().get("retirees", [])
    st = FauxSt()
    colonnes = D._panneau_colonnes_et_filtres(st, LIGNES, list(D.COLONNES_REGISTRE), "")["colonnes"]
    assert colonnes == list(D.COLONNES_REGISTRE_DEFAUT), "la colonne revient dès qu'elle existe"


def test_R18_une_colonne_rappelee_revient_a_l_ouverture_suivante(vue_isolee):
    st = FauxSt()
    st.session_state[D._cle_vue(st, "colonnes")] = list(D.COLONNES_REGISTRE_DEFAUT) + ["chaine"]
    D._panneau_colonnes_et_filtres(st, LIGNES, list(D.COLONNES_REGISTRE), "")
    autre = FauxSt()
    colonnes = D._panneau_colonnes_et_filtres(autre, LIGNES, list(D.COLONNES_REGISTRE), "")["colonnes"]
    assert "chaine" in colonnes


def test_R18_un_etat_illisible_ou_absent_rend_le_tableau_par_defaut(vue_isolee):
    assert D.charger_vue_registre() == {}
    vue_isolee.parent.mkdir(parents=True, exist_ok=True)
    vue_isolee.write_text("retirees: [inconnue]\nexclues: 3\nbornes: [oui]\n", encoding="utf-8")
    assert D.charger_vue_registre() == {}
    st = FauxSt()
    assert D._panneau_colonnes_et_filtres(st, LIGNES, list(D.COLONNES_REGISTRE), "")["colonnes"] \
        == list(D.COLONNES_REGISTRE_DEFAUT)


def test_R18_un_filtre_pose_revient_a_l_ouverture_suivante():
    st = FauxSt()
    st.session_state[D._cle_vue(st, "val-etat")] = ["terminee"]
    st.session_state[D._cle_vue(st, "vues-etat")] = ["en_cours", "terminee"]
    D._panneau_colonnes_et_filtres(st, LIGNES, list(D.COLONNES_REGISTRE), "")
    autre = FauxSt()  # nouvelle session : plus rien en mémoire vive
    choix = D._panneau_colonnes_et_filtres(autre, LIGNES, list(D.COLONNES_REGISTRE), "")
    assert choix["retenues"]["etat"] == ["terminee"]


def test_R18_une_valeur_nee_apres_le_filtre_revient_cochee(vue_isolee):
    """C'est pour cela que le disque retient les EXCLUES, pas les cochées : une exécution
    lancée demain ne doit pas naître invisible sous un filtre écrit hier."""
    D.sauver_vue_registre(colonnes=D.COLONNES_REGISTRE_DEFAUT, exclues={"fournisseur": ["mistral"]},
                          bornes={}, texte="")
    st = FauxSt()
    choix = D._panneau_colonnes_et_filtres(
        st, LIGNES + [{"fournisseur": "openai"}], list(D.COLONNES_REGISTRE), "")
    assert set(choix["retenues"]["fournisseur"]) == {"google", "openai"}, \
        "mistral reste exclue, openai — inconnue à l'écriture du filtre — arrive cochée"


# ── R19 — des filtres restaurés qui cachent se disent d'entrée ───────────────


def test_R19_un_filtre_restaure_qui_cache_des_lignes_est_annonce(plateforme, vue_isolee):
    D.sauver_vue_registre(colonnes=D.COLONNES_REGISTRE_DEFAUT,
                          exclues={"etat": ["en_cours"]}, bornes={}, texte="")
    st = FauxSt(event=FauxEvent([]))
    _dessiner(st)
    assert any("dernière session" in a and "etat" in a for a in st.avis), st.avis


def test_R19_sans_ligne_cachee_aucun_bandeau(plateforme, vue_isolee):
    D.sauver_vue_registre(colonnes=D.COLONNES_REGISTRE_DEFAUT,
                          exclues={"etat": ["etat_inexistant"]}, bornes={}, texte="")
    st = FauxSt(event=FauxEvent([]))
    _dessiner(st)
    assert not any("dernière session" in a for a in st.avis), st.avis


def test_R19_le_bandeau_tient_pendant_que_le_fragment_bat(plateforme, vue_isolee):
    """Le registre se redessine toutes les 5 s quand une exécution tourne : un bandeau montré
    une seule fois s'effacerait avant d'avoir été lu."""
    D.sauver_vue_registre(colonnes=D.COLONNES_REGISTRE_DEFAUT,
                          exclues={"etat": ["en_cours"]}, bornes={}, texte="")
    st = FauxSt(event=FauxEvent([]))
    _dessiner(st)
    _dessiner(st)
    assert sum("dernière session" in a for a in st.avis) == 2, st.avis


def test_R19_le_bandeau_tombe_des_qu_on_reinitialise(plateforme, vue_isolee):
    D.sauver_vue_registre(colonnes=D.COLONNES_REGISTRE_DEFAUT,
                          exclues={"etat": ["en_cours"]}, bornes={}, texte="")
    st = FauxSt(event=FauxEvent([]))
    _dessiner(st)
    D._oublier_filtres(st)
    st.avis.clear()
    _dessiner(st)
    assert not any("dernière session" in a for a in st.avis), st.avis


# ── Inversion de l'ordre des blocs & pourcentage de choix forcés ─────────────


def test_ordre_des_blocs_mes_experiences_avant_nouvelle_experience(plateforme):
    """« 📚 Mes expériences » doit précéder « 🧪 Nouvelle expérience » dans la page."""
    st = FauxSt(event=FauxEvent([]))
    with contextlib.suppress(RerunDemande):
        D.render(st, pd)
    subheaders = [t for t in st.textes if "Mes expériences" in t or "Nouvelle expérience" in t]
    assert len(subheaders) >= 2, subheaders
    assert "Mes expériences" in subheaders[0]
    assert "Nouvelle expérience" in subheaders[1]


def test_choix_forces_affiche_pourcentage_trois_decimales(plateforme):
    """La colonne choix_forces affiche le pourcentage avec au moins 3 décimales."""
    exp_a_exec = plateforme / "exp_a" / "executions" / "2026-09-10_08_00_00"
    _ecrire(exp_a_exec / "synthese.json", {
        "choix_forces": {"n": 5, "part": 5 / 99},
        "parts_modales": {"n": 99}
    })
    st = FauxSt(event=FauxEvent([]))
    _dessiner(st)
    table = next(t for t in st.tables if "experience" in t.columns)
    assert "choix_forces" in table.columns
    valeurs = list(table["choix_forces"])
    # 5 / 99 = 0.050505... -> 5.051 %
    assert any(v == "5.051 %" for v in valeurs), valeurs
    # Une exécution sans synthèse de choix forcés affiche "—"
    assert any(v == "—" for v in valeurs), valeurs

