"""Ce qui tourne, vu par le tableau de bord (spec R1 à R4b, R17, R19, R21 à R22).

Le fil de ces tests : l'état affiché est lu SUR LE DISQUE, dans des fichiers écrits par le
conteneur pendant qu'on les lit. Ils peuvent donc être absents, tronqués ou incomplets — et
c'est le cas que la page doit tenir, parce que c'est celui qui s'est produit : le 2026-09-06
un warm-up a tourné une heure sans que le formulaire s'en aperçoive.
"""

import contextlib
import functools
import json
import sys
import time
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.dashboard import experiences  # noqa: E402

VRAI_LISTER = experiences.lister


class FauxSt:
    """Le strict nécessaire de l'API Streamlit utilisée par `rendre_activites`.

    `columns` rend cet objet lui-même : tout ce qui est dessiné, quelle que soit la colonne,
    se retrouve dans les mêmes listes — c'est ce qu'on veut vérifier.
    """

    def __init__(self):
        self.barres: list[tuple[float, str]] = []
        self.textes: list[str] = []
        self.boutons: list[str] = []
        self.cases: list[str] = []
        self.legendes: list[str] = []

    def progress(self, valeur, text=""):
        self.barres.append((valeur, text))

    def markdown(self, texte):
        self.textes.append(texte)

    def caption(self, texte, **_k):
        self.legendes.append(texte)

    def columns(self, spec, **_k):
        largeur = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
        return [self] * largeur

    def button(self, label, **_k):
        self.boutons.append(label)
        return False

    def checkbox(self, label, **_k):
        self.cases.append(label)
        return False

    def toast(self, *_a, **_k):
        pass

    @property
    def tout(self) -> str:
        return "\n".join(self.textes + self.legendes + [t for _, t in self.barres])


class RerunDemande(Exception):
    """Ce que lève `st.rerun` : dans Streamlit il interrompt le script, ici aussi."""


class FauxStFragment(FauxSt):
    """Un Streamlit de poche qui retient le rythme du fragment et les rechargements demandés."""

    def __init__(self):
        super().__init__()
        self.session_state: dict = {}
        self.run_every = "fragment jamais créé"
        self.reruns: list = []

    def fragment(self, run_every=None):
        self.run_every = run_every
        return lambda fonction: fonction

    def rerun(self, scope=None):
        self.reruns.append(scope)
        raise RerunDemande()


def _clore(nom: str) -> None:
    chemin = experiences.DOSSIER_JEUX / nom / "MANIFEST.yaml"
    contenu = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    contenu["clos"] = True
    _ecrire(chemin, contenu)


def _ecrire(chemin: Path, contenu) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    if chemin.suffix == ".json":
        chemin.write_text(json.dumps(contenu), encoding="utf-8")
    else:
        chemin.write_text(yaml.safe_dump(contenu, allow_unicode=True), encoding="utf-8")


@pytest.fixture
def plateforme(tmp_path, monkeypatch):
    """Une plateforme de poche : une expérience en cours, une terminée, trois jeux."""
    exps, jeux = tmp_path / "experiences", tmp_path / "jeux"

    _ecrire(exps / "exp1" / "experience.yaml",
            {"nom": "exp1", "jeu": {"nom": "j_clos"}, "mode": "sans_simulateur",
             "decideur": {"type": "passerelle", "modele": "m1"}, "gabarit": {"variante": "b_min"}})
    _ecrire(exps / "exp1" / "executions" / "20260907-100000" / "etat.json", {"etat": "en_cours"})
    _ecrire(exps / "exp1" / "executions" / "20260907-100000" / "progression.json",
            {"faits": 120, "attendus": 400, "pourcent": 30, "reste_s": 600,
             "personnes": 50, "personnes_terminees": 12, "erreurs": 0})
    _ecrire(exps / "exp1" / "executions" / "20260906-090000" / "etat.json", {"etat": "terminee"})

    _ecrire(exps / "exp2" / "experience.yaml",
            {"nom": "exp2", "jeu": {"nom": "j_clos"}, "decideur": {"type": "aleatoire"}})
    _ecrire(exps / "exp2" / "executions" / "20260906-110000" / "etat.json", {"etat": "terminee"})

    _ecrire(exps / "exp3" / "experience.yaml", {"nom": "exp3", "jeu": {"nom": "j_clos"}, "decideur": {}})

    _ecrire(jeux / "j_clos" / "MANIFEST.yaml",
            {"nom": "j_clos", "clos": True, "population": {"nom": "pop"}, "jour_simule": "2026-03-16",
             "attendus": {"deplacements": 2693}, "couverts": {"deplacements": 2645}})
    _ecrire(jeux / "j_prep" / "MANIFEST.yaml",
            {"nom": "j_prep", "clos": False, "population": {"nom": "pop"}, "jour_simule": "2026-03-16"})
    _ecrire(jeux / "j_prep" / "progression.json",
            {"jeu": "j_prep", "faits": 1753, "total": 2693, "pourcent": 65.1, "sans_proposition": 31,
             "erreurs": 0, "reste_s": 1288, "maj": "2026-09-06T19:13:31+00:00"})
    _ecrire(jeux / "j_neuf" / "MANIFEST.yaml",
            {"nom": "j_neuf", "clos": False, "population": {"nom": "pop"}, "jour_simule": "2026-03-16"})

    monkeypatch.setattr(experiences, "DOSSIER", exps)
    monkeypatch.setattr(experiences, "DOSSIER_JEUX", jeux)
    monkeypatch.setattr(experiences, "lister", functools.partial(VRAI_LISTER, dossier=exps))
    return tmp_path


def test_R1_une_execution_en_cours_est_listee_avec_son_avancement(plateforme):
    act = experiences.activites_en_cours()
    assert [e["execution"] for e in act["executions"]] == ["20260907-100000"], "seul `en_cours` doit figurer"
    e = act["executions"][0]
    assert (e["experience"], e["faits"], e["total"], e["pourcent"], e["reste_s"]) == ("exp1", 120, 400, 30.0, 600)

    st = FauxSt()
    experiences.rendre_activites(st, act)
    assert "120 / 400 déplacements" in st.tout
    assert "30 %" in st.tout, "le critère demande le pourcentage écrit, pas seulement la barre"
    assert "12 / 50 personnes" in st.tout
    assert "reste ≈ 00:10:00" in st.tout, "une durée se lit en hh:mm:ss, pas en secondes nues"


def test_R2_un_jeu_non_clos_est_liste_avec_sa_progression(plateforme):
    act = experiences.activites_en_cours()
    noms = [j["nom"] for j in act["jeux"]]
    assert "j_clos" not in noms, "un jeu clos n'est plus une activité"
    assert set(noms) == {"j_prep", "j_neuf"}

    st = FauxSt()
    experiences.rendre_activites(st, act)
    assert "1 753 / 2 693 déplacements" in st.tout
    assert "65 %" in st.tout, "le critère demande le pourcentage écrit"
    assert "31 sans proposition" in st.tout
    assert "« j_neuf » en préparation (pas encore de progression)" in st.tout


def test_R3_sans_rien_en_cours_les_compteurs_parlent(plateforme):
    # tout est clos : plus aucune activité
    for nom in ("j_prep", "j_neuf"):
        chemin = experiences.DOSSIER_JEUX / nom / "MANIFEST.yaml"
        contenu = yaml.safe_load(chemin.read_text(encoding="utf-8"))
        contenu["clos"] = True
        _ecrire(chemin, contenu)
    (experiences.DOSSIER / "exp1" / "executions" / "20260907-100000" / "etat.json").write_text(
        json.dumps({"etat": "terminee"}), encoding="utf-8")

    act = experiences.activites_en_cours()
    assert act["executions"] == [] and act["jeux"] == []
    assert (act["definies"], act["terminees"]) == (3, 3)

    st = FauxSt()
    experiences.rendre_activites(st, act)
    assert "Aucune expérience en cours" in st.tout
    assert "**3** définie(s)" in st.tout
    assert "**3** exécution(s) terminée(s)" in st.tout


def test_R4b_un_fichier_de_progression_absurde_ne_casse_rien(plateforme):
    (experiences.DOSSIER_JEUX / "j_prep" / "progression.json").write_text("{tronqué", encoding="utf-8")
    (experiences.DOSSIER / "exp1" / "executions" / "20260907-100000" / "progression.json").write_text(
        json.dumps({"pourcent": 140}), encoding="utf-8")

    act = experiences.activites_en_cours()
    assert act["executions"][0]["pourcent"] == 100.0, "un pourcentage aberrant est ramené à 100"
    assert act["executions"][0]["faits"] is None

    st = FauxSt()
    experiences.rendre_activites(st, act)  # ne doit pas lever
    assert "? / ? déplacements" in st.tout
    assert all(0.0 <= valeur <= 1.0 for valeur, _ in st.barres)


def test_R17_un_jeu_en_preparation_est_visible_pour_sa_population(plateforme):
    assert {j["nom"] for j in experiences.jeux_en_preparation("pop")} == {"j_prep", "j_neuf"}
    assert experiences.jeux_en_preparation("une_autre_pop") == []


def test_R19_la_construction_est_gardee_tant_qu_elle_ecrit(plateforme):
    from datetime import datetime, timedelta, timezone

    chemin = experiences.DOSSIER_JEUX / "j_prep" / "progression.json"
    frais = datetime.now(timezone.utc) - timedelta(seconds=10)
    _ecrire(chemin, {"faits": 10, "total": 100, "maj": frais.isoformat()})
    motif = experiences.construction_active("j_prep")
    assert motif and "déjà en cours" in motif

    vieux = datetime.now(timezone.utc) - timedelta(minutes=10)
    _ecrire(chemin, {"faits": 10, "total": 100, "maj": vieux.isoformat()})
    assert experiences.construction_active("j_prep") is None, "un warm-up interrompu doit rester relançable"

    assert experiences.construction_active("j_neuf") is None, "sans progression, rien ne tourne"


def test_R21_les_choix_du_formulaire_survivent_au_redemarrage(plateforme, monkeypatch, tmp_path):
    monkeypatch.setattr(experiences, "ETAT_FORMULAIRE", tmp_path / "formulaire.yaml")
    choix = dict(experiences.defauts())
    choix.update({"mode": "simulateur", "politique": "propre", "attente_max_s": 300,
                  "max_candidats": 9, "temperature": 0.7, "jeu_courant": {"nom": "ignoré"}})

    assert experiences.sauver_etat_formulaire(choix) is True
    assert experiences.sauver_etat_formulaire(choix) is False, "rien n'a bougé : ne pas réécrire"

    relu = experiences.charger_etat_formulaire()
    assert "nom" not in relu, "le nom se calcule (N1) : il n'est plus un choix à retenir"
    assert relu["attente_max_s"] == 300
    assert (relu["mode"], relu["politique"], relu["max_candidats"], relu["temperature"]) == ("simulateur", "propre", 9, 0.7)
    assert "jeu_courant" not in relu, "seuls les champs du formulaire sont retenus"
    # Les quatre valeurs validées contre le disque doivent aussi revenir quand elles EXISTENT,
    # sinon le repli de R21b les effacerait à chaque démarrage.
    for champ in ("population", "jeu", "variante", "modele"):
        assert relu[champ] == choix[champ], f"{champ} doit être restauré tel quel"


def test_R21b_une_reprise_abimee_revient_aux_defauts_champ_par_champ(plateforme, monkeypatch, tmp_path):
    fichier = tmp_path / "formulaire.yaml"
    monkeypatch.setattr(experiences, "ETAT_FORMULAIRE", fichier)

    fichier.write_text("{{{ pas du yaml", encoding="utf-8")
    assert experiences.charger_etat_formulaire() == {}, "un fichier illisible ne doit pas bloquer le formulaire"

    _ecrire(fichier, {"attente_max_s": 300, "politique": "inventée", "decideur_type": "oracle",
                      "date": "pas-une-date", "parallelisme": 9999, "variante": "variante_disparue",
                      "jeu": "jeu_efface", "modele": "modele_retire",
                      "population": "data/population/population_effacee"})
    relu = experiences.charger_etat_formulaire()
    defaut = experiences.defauts()
    assert relu["attente_max_s"] == 300, "ce qui est valide est conservé"
    assert relu["politique"] == defaut["politique"]
    assert relu["decideur_type"] == defaut["decideur_type"]
    assert relu["date"] == defaut["date"]
    assert relu["parallelisme"] == 64, "une valeur hors bornes est ramenée dans l'intervalle"

    # Les trois valeurs que la règle nomme : une chaîne conservée ferait retomber le sélecteur
    # sur son premier choix — b0_pristine pour le prompt — et cette substitution silencieuse
    # finirait écrite dans experience.yaml.
    assert relu["variante"] == defaut["variante"], "la variante disparue doit revenir au prompt actif"
    assert relu["jeu"] == defaut["jeu"], "un jeu effacé doit revenir au défaut"
    assert relu["modele"] == defaut["modele"], "un modèle retiré doit revenir au défaut"
    assert relu["population"] == defaut["population"], "une population effacée doit revenir au défaut"


def test_R22_restaurer_un_brouillon_ne_cree_aucune_experience(plateforme, monkeypatch, tmp_path):
    monkeypatch.setattr(experiences, "ETAT_FORMULAIRE", tmp_path / "formulaire.yaml")
    experiences.sauver_etat_formulaire({**experiences.defauts(), "attente_max_s": 300})
    avant = sorted(p.name for p in experiences.DOSSIER.iterdir())
    experiences.charger_etat_formulaire()
    assert sorted(p.name for p in experiences.DOSSIER.iterdir()) == avant
    assert experiences.charger_etat_formulaire()["attente_max_s"] == 300


def test_R18_la_page_se_recharge_quand_un_jeu_devient_clos(plateforme):
    st = FauxStFragment()

    experiences._suivi_des_jeux(st, "pop")
    assert st.run_every == "5s", "tant qu'un jeu se construit, le bloc doit se rafraîchir seul"
    assert st.reruns == [], "premier passage : on apprend l'état, on ne recharge pas"
    assert any("j_prep" in texte for _, texte in st.barres)

    _clore("j_prep")
    _clore("j_neuf")
    with pytest.raises(RerunDemande):
        experiences._suivi_des_jeux(st, "pop")
    assert st.reruns == ["app"], "le jeu est clos : la page entière doit le voir"

    experiences._suivi_des_jeux(st, "pop")
    assert st.reruns == ["app"], "état stabilisé : plus de rechargement, sinon la page boucle"
    assert st.run_every is None, "plus rien ne se construit : inutile de sonder le disque"


def test_R18_un_jeu_qui_apparait_recharge_aussi_la_page(plateforme):
    st = FauxStFragment()
    experiences._suivi_des_jeux(st, "pop")
    st.reruns.clear()

    _ecrire(experiences.DOSSIER_JEUX / "j_tard" / "MANIFEST.yaml",
            {"nom": "j_tard", "clos": False, "population": {"nom": "pop"}, "jour_simule": "2026-03-16"})
    with pytest.raises(RerunDemande):
        experiences._suivi_des_jeux(st, "pop")
    assert st.reruns == ["app"]


def test_R18_le_clic_sur_la_construction_relance_le_script(plateforme):
    """Le drapeau de surveillance est posé APRÈS la création du fragment, dans le même run.

    Sans `st.rerun()` juste derrière, il ne serait lu qu'au prochain clic de l'utilisateur : le
    bloc de progression resterait figé, exactement le cas que R18 nomme.
    """
    source = Path(experiences.__file__).read_text(encoding="utf-8")
    apres_drapeau = source.split('st.session_state["_warmup_lance_a"] = time.time()', 1)[1]
    assert "st.rerun()" in apres_drapeau.split("\n\n", 1)[0], (
        "le handler de construction doit relancer le script juste après avoir posé le drapeau")


def test_R18_apres_un_clic_la_surveillance_tient_avant_meme_le_dossier(plateforme):
    st = FauxStFragment()
    experiences._suivi_des_jeux(st, "population_sans_jeu")
    assert st.run_every is None, "sans construction lancée, rien à surveiller"

    st.session_state["_warmup_lance_a"] = time.time()
    experiences._suivi_des_jeux(st, "population_sans_jeu")
    assert st.run_every == "5s", "le dossier du jeu n'existe pas encore : il faut attendre qu'il apparaisse"


def test_R17_la_liste_du_formulaire_montre_les_jeux_en_construction(plateforme):
    """R17 porte sur la liste du formulaire et sur l'avertissement, pas sur la tuile."""
    noms = [j["nom"] for j in experiences.jeux_de("pop")]
    assert set(noms) == {"j_clos", "j_prep", "j_neuf"}, "clos ou non, un jeu de cette population est proposé"
    assert experiences.jeux_de("pop_sans_jeu") == [], "sans jeu, la liste est vide et le formulaire avertit"

    par_nom = {j["nom"]: j for j in experiences.jeux_de("pop")}
    en_prep = experiences.libelle_jeu(par_nom["j_prep"])
    assert "(EN PRÉPARATION)" in en_prep
    # `couverts` et `attendus` n'entrent au manifeste qu'à la clôture : les interpoler bruts
    # affichait « None/None » précisément sur le jeu que R17 rend visible.
    assert "None" not in en_prep, en_prep
    assert "?/? déplacements" in en_prep, en_prep
    assert "(EN PRÉPARATION)" not in experiences.libelle_jeu(par_nom["j_clos"])
    assert "2 645/2 693 déplacements" in experiences.libelle_jeu(par_nom["j_clos"])


def test_R8_un_jeu_en_preparation_s_affiche_sans_aucun_job_make(plateforme):
    """L'onglet Activités lit le disque : le registre de jobs peut être vide."""
    from scripts.dashboard import runner

    assert [j for j in runner.Registry().jobs() if j.running] == [], "aucun job lancé dans ce test"
    st = FauxSt()
    experiences.rendre_activites(st, experiences.activites_en_cours())
    assert "j_prep" in st.tout, "le jeu en préparation doit s'afficher sans job make"


def test_R24_l_age_de_la_progression_d_une_execution_est_dit(plateforme):
    from datetime import datetime, timedelta, timezone

    chemin = experiences.DOSSIER / "exp1" / "executions" / "20260907-100000" / "progression.json"
    base = {"faits": 120, "attendus": 400, "pourcent": 30, "personnes": 50, "personnes_terminees": 12}

    frais = (datetime.now(timezone.utc) - timedelta(seconds=3)).isoformat()
    _ecrire(chemin, {**base, "maj": frais})
    st = FauxSt()
    experiences.rendre_activites(st, experiences.activites_en_cours())
    assert "progression écrite il y a" in st.tout

    vieux = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    _ecrire(chemin, {**base, "maj": vieux})
    st = FauxSt()
    experiences.rendre_activites(st, experiences.activites_en_cours())
    assert "plus rien d'écrit depuis 15 min" in st.tout
    assert "gel" not in st.tout.lower(), "on écrit le fait, on ne diagnostique pas un gel"


def test_R22_la_restauration_n_ecrit_jamais_d_experience(plateforme, monkeypatch, tmp_path):
    """Le vrai risque n'est pas qu'un dossier apparaisse, c'est qu'`enregistrer` soit appelé."""
    monkeypatch.setattr(experiences, "ETAT_FORMULAIRE", tmp_path / "formulaire.yaml")
    experiences.sauver_etat_formulaire({**experiences.defauts(), "attente_max_s": 300})

    def refuser(*_args, **_kwargs):
        raise AssertionError("la restauration d'un brouillon ne doit rien enregistrer")

    monkeypatch.setattr(experiences, "enregistrer", refuser)
    avant = sorted(p.name for p in experiences.DOSSIER.iterdir())
    relu = experiences.charger_etat_formulaire()
    assert relu["attente_max_s"] == 300
    assert sorted(p.name for p in experiences.DOSSIER.iterdir()) == avant, \
        "un brouillon restauré ne crée aucune expérience"


def test_R21_le_brouillon_vit_dans_un_dossier_ignore_par_git():
    """Le chemin ÉCRIT dans le module, pas la valeur courante : d'autres tests la redirigent."""
    import subprocess

    source = Path(experiences.__file__).read_text(encoding="utf-8")
    declaration = 'ETAT_FORMULAIRE = REPO_ROOT / "experiments" / ".dashboard" / "formulaire_experience.yaml"'
    assert declaration in source, "le brouillon doit vivre sous experiments/.dashboard/"

    chemin = RACINE / "experiments" / ".dashboard" / "formulaire_experience.yaml"
    sortie = subprocess.run(["git", "check-ignore", "-v", str(chemin)],
                            cwd=RACINE, capture_output=True, text=True)
    assert sortie.returncode == 0, f"{chemin} n'est pas ignoré par git : {sortie.stdout}{sortie.stderr}"


def test_R26_les_cibles_documentees_restent_listables_hors_du_tableau_de_bord():
    import subprocess

    sortie = subprocess.run(["make", "help"], cwd=RACINE, capture_output=True, text=True)
    assert sortie.returncode == 0, sortie.stderr
    lignes = sortie.stdout.splitlines()
    assert any(l.strip().startswith("dashboard ") for l in lignes), "la cible dashboard doit être listée"
    assert any("Tableau de bord de pilotage" in l for l in lignes), "avec sa documentation"
    assert not any(".PHONY" in l for l in lignes), "les lignes .PHONY ne sont pas des cibles"
    assert len(lignes) > 40, f"seulement {len(lignes)} cibles listées"


def test_R24_l_age_est_dit_aussi_dans_la_tuile_compacte(plateforme):
    """C'est dans la vue d'ensemble que le repère sert le plus : elle est en mode compact."""
    from datetime import datetime, timedelta, timezone

    chemin = experiences.DOSSIER / "exp1" / "executions" / "20260907-100000" / "progression.json"
    _ecrire(chemin, {"faits": 120, "attendus": 400, "pourcent": 30,
                     "maj": (datetime.now(timezone.utc) - timedelta(seconds=4)).isoformat()})
    st = FauxSt()
    experiences.rendre_activites(st, experiences.activites_en_cours(), compact=True)
    assert "écrit il y a" in st.tout, "en mode compact aussi, l'âge de la progression est dit"


def test_R19_une_construction_active_grise_le_bouton_avec_son_motif():
    """La composition, pas seulement ses deux moitiés : le motif doit atteindre le bouton."""
    exp = {"nom": "exp", "jeu": {"nom": "j1"}}
    motif = "une construction est déjà en cours (10 / 100 déplacements, progression écrite il y a 3 s)"
    motifs = experiences.motifs_indisponibilite(exp, jeu_clos=True, controleur_ok=True,
                                                registre=True, construction=motif)
    assert motifs["construire"] == [motif]
    assert motifs["lancer"] == [], "lancer l'expérience reste possible pendant qu'un autre jeu se construit"

    sans = experiences.motifs_indisponibilite(exp, jeu_clos=True, controleur_ok=True, registre=True)
    assert sans["construire"] == []


def test_R29_ce_qui_est_refuse_est_ce_qui_est_dangereux(plateforme):
    """Les accents sont sans danger ; les espaces cassent `make EXP=` faute de guillemets."""
    acceptes = ("premiere_minimal", "Prompt_Éco", "jeu.v5-1", "P", "prompt2")
    refuses = ("Prompt Minimaliste", "a/b", "../../evade", "-flag", "_debut", "a;rm -rf",
               "a$(ls)", "", "   ", "x" * 65)
    for nom in acceptes:
        assert experiences.MOTIF_NOM.match(nom), f"{nom!r} devrait être accepté"
    for nom in refuses:
        assert not experiences.MOTIF_NOM.match(nom.strip()), f"{nom!r} devrait être refusé"


def test_R29_un_nom_d_experience_ne_peut_pas_sortir_du_dossier(plateforme):
    exp = {"nom": "../../evade", "jeu": {"nom": "j_clos"}}
    motifs = experiences.motifs_indisponibilite(exp, jeu_clos=True, controleur_ok=True, registre=True)
    assert any("ni espace ni séparateur" in m for m in motifs["lancer"]), motifs["lancer"]
    assert motifs["enregistrer"], "un nom refusé doit aussi bloquer l'enregistrement"

    with pytest.raises(ValueError, match="nom d'expérience refusé"):
        experiences.enregistrer({"nom": "../../evade"})
    assert not (experiences.DOSSIER.parent.parent / "evade").exists()

    correct = experiences.motifs_indisponibilite({"nom": "premiere_minimal", "jeu": {"nom": "j_clos"}},
                                                 jeu_clos=True, controleur_ok=True, registre=True)
    assert all(v == [] for v in correct.values()), correct

    # N1 : un nom vide n'est plus une saisie oubliée, c'est un nommage qui a refusé — et le
    # motif doit nommer le champ à corriger, pas constater le vide.
    sans_nom = experiences.motifs_indisponibilite({"nom": "", "jeu": {"nom": "j_clos"}},
                                                  jeu_clos=True, controleur_ok=True, registre=True)
    assert sans_nom["enregistrer"], "un nom impossible bloque l'enregistrement"
    assert any("decideur" in m for m in sans_nom["enregistrer"]), sans_nom["enregistrer"]


def test_R24_un_warm_up_qui_n_ecrit_plus_le_dit_aussi(plateforme):
    """Le symétrique de R24 pour les jeux : un warm-up tué garde `clos: false`."""
    from datetime import datetime, timedelta, timezone

    chemin = experiences.DOSSIER_JEUX / "j_prep" / "progression.json"
    base = {"faits": 1753, "total": 2693, "pourcent": 65.1}

    _ecrire(chemin, {**base, "maj": (datetime.now(timezone.utc) - timedelta(seconds=6)).isoformat()})
    st = FauxSt()
    experiences.rendre_activites(st, experiences.activites_en_cours())
    assert "progression écrite il y a" in st.tout
    assert "plus rien d'écrit" not in st.tout

    _ecrire(chemin, {**base, "maj": (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()})
    st = FauxSt()
    experiences.rendre_activites(st, experiences.activites_en_cours())
    assert "plus rien d'écrit depuis 20 min" in st.tout, st.tout

    st = FauxSt()
    experiences.rendre_activites(st, experiences.activites_en_cours(), compact=True)
    assert "plus rien d'écrit depuis 20 min" in st.tout, "la tuile aussi doit le dire"


def test_les_boutons_pause_et_arret_sont_offerts_sur_une_execution_en_cours(plateforme):
    """Demande du 2026-09-07 : pouvoir stopper depuis « Exécutions et jeux en cours »."""
    st = FauxSt()
    experiences.rendre_activites(st, experiences.activites_en_cours())

    assert any("Pause" in b for b in st.boutons), st.boutons
    assert any("Arrêter" in b for b in st.boutons), st.boutons


def test_l_arret_n_est_plus_garde_par_une_case_de_confirmation(plateforme):
    """Retrait demandé le 2026-09-09 : « ⏹ Arrêter » est cliquable sans rien cocher.

    La différence entre pause et arrêt, elle, reste écrite sous les boutons : c'est tout ce
    qui garde encore un geste irréversible (il avait coûté 209 décisions le 2026-09-07).
    """
    st = FauxSt()
    experiences.rendre_activites(st, experiences.activites_en_cours())

    assert st.cases == [], f"plus aucune case de confirmation : {st.cases}"
    assert not any("confirme" in b for b in st.boutons), st.boutons
    dit = "\n".join(st.legendes)
    assert "reprenable" in dit and "scelle l'archive" in dit, dit


def test_la_tuile_compacte_n_offre_pas_de_bouton(plateforme):
    """La vue d'ensemble se rafraîchit toutes les 10 s : pas d'action destructive dedans."""
    st = FauxSt()
    experiences.rendre_activites(st, experiences.activites_en_cours(), compact=True)
    assert st.boutons == [] and st.cases == []


def test_une_tentative_reessayee_est_une_attente_pas_une_erreur(plateforme):
    """R1 ne saute aucun déplacement : compter ces tentatives en « erreurs » faisait lire
    128 erreurs sur un run qui n'en avait aucune."""
    chemin = experiences.DOSSIER / "exp1" / "executions" / "20260907-100000" / "progression.json"
    _ecrire(chemin, {"faits": 106, "attendus": 2693, "pourcent": 3.9, "sollicitations": 192,
                     "attentes": 96, "attentes_par_type": {"passerelle_occupee": 96},
                     "erreurs": 0, "erreurs_par_type": {}})

    st = FauxSt()
    experiences.rendre_activites(st, experiences.activites_en_cours())
    assert "96 attentes (passerelle_occupee)" in st.tout, st.tout
    assert "erreurs" not in st.tout.lower(), "aucune erreur : le mot ne doit pas apparaître"

    # Un échec DÉFINITIF, lui, doit sauter aux yeux
    _ecrire(chemin, {"faits": 106, "attendus": 2693, "attentes": 96,
                     "attentes_par_type": {"passerelle_occupee": 96},
                     "erreurs": 3, "erreurs_par_type": {"schema_invalide": 3}})
    st = FauxSt()
    experiences.rendre_activites(st, experiences.activites_en_cours())
    assert "3 ÉCHECS DÉFINITIFS" in st.tout, st.tout


def test_le_parallelisme_conseille_suit_le_debit_des_instances_vivantes(plateforme):
    """Demander 8 décisions à une instance de 15 requêtes/minute gâche la moitié des essais."""
    vivantes = {"google_gemini35_key1": {"rpm_limit": 15}, "google_gemini35_key2": {"rpm_limit": 15}}
    conseil = experiences.parallelisme_conseille("gemini-3.5-flash-lite", vivantes)
    assert conseil is not None, "les deux instances de ce modèle sont déclarées dans providers.yaml"
    # Série, pas parallèle : le débit d'UNE instance, pas la somme des deux
    assert conseil["rpm"] == 15, conseil
    assert conseil["valeur"] == 3, "15 requêtes/minute sur l'instance servie → 3 en parallèle"

    une_seule = experiences.parallelisme_conseille("gemini-3.5-flash-lite", {"google_gemini35_key2": {"rpm_limit": 15}})
    assert une_seule["rpm"] == 15 and une_seule["valeur"] == 3, une_seule

    # Une instance déclarée mais absente de la passerelle ne compte pas : son débit n'existe pas
    vide = experiences.parallelisme_conseille("gemini-3.5-flash-lite", {})
    assert vide is None, "aucune instance vivante : aucun conseil"


class FauxStServices(FauxStFragment):
    """Ajoute ce que `_suivi_des_services` utilise : conteneur, légendes, boutons."""

    def __init__(self, services):
        super().__init__()
        self.services = services
        self.legendes: list[str] = []
        self.boutons: list[str] = []

    def container(self, **_k):
        import contextlib
        return contextlib.nullcontext(self)

    def caption(self, texte, **_k):
        self.legendes.append(texte)

    def button(self, label, **_k):
        self.boutons.append(label)
        return False

    def toast(self, *_a, **_k):
        pass

    @property
    def vu(self) -> str:
        return "\n".join(self.textes + self.legendes + self.boutons)


def test_le_bloc_des_services_se_rafraichit_tant_qu_il_en_manque(plateforme, monkeypatch):
    """Sans cela le bandeau « le contrôleur ne tourne pas » survit à son démarrage."""
    etat = {"actifs": {"api", "worker"}}
    monkeypatch.setattr(experiences, "services_actifs", lambda *a, **k: set(etat["actifs"]))

    st = FauxStServices(etat)
    experiences._suivi_des_services(st, ["controller", "api", "worker"])
    assert st.run_every == "5s", "il manque `controller` : la sonde doit tourner"
    assert "⚪ `controller`" in st.vu and "🟢 `api`" in st.vu, st.vu
    # Plus de bouton : le lancement démarre lui-même ce qui manque (retrait du 2026-09-09).
    assert st.boutons == [], f"le bloc des services est en lecture seule : {st.boutons}"
    assert any("1 service(s) à démarrer" in l and "Lancer" in l for l in st.legendes), st.legendes

    # le service démarre : la page entière doit se recharger une fois
    etat["actifs"] = {"controller", "api", "worker"}
    st.session_state.pop("_services", None)
    with pytest.raises(RerunDemande):
        experiences._suivi_des_services(st, ["controller", "api", "worker"])
    assert st.reruns == ["app"]
    assert "_services" not in st.session_state, "le cache doit être vidé pour que le bandeau relise"


def test_le_bloc_des_services_cesse_de_sonder_quand_tout_tourne(plateforme, monkeypatch):
    monkeypatch.setattr(experiences, "services_actifs", lambda *a, **k: {"controller", "api", "worker"})
    st = FauxStServices(None)

    experiences._suivi_des_services(st, ["controller", "api", "worker"])
    st.reruns.clear()
    experiences._suivi_des_services(st, ["controller", "api", "worker"])

    assert st.run_every is None, "tout tourne : inutile d'interroger Docker en boucle"
    assert st.reruns == [], "état stable : aucun rechargement"
    assert st.boutons == [], "rien ne manque : aucun bouton de démarrage"


class FauxStRegistre(FauxStFragment):
    """Ce que `_suivi_du_registre` utilise : colonnes, saisies, tableau, barres."""

    def __init__(self):
        super().__init__()
        self.legendes: list[str] = []
        self.boutons: list[str] = []
        self.cases: list[str] = []
        self.tableaux = 0
        self.replis: list[str] = []
        self.profondeur = 0

    @contextlib.contextmanager
    def expander(self, label, **_k):
        """Le panneau « Formule » se rend dans un repli, en tête du registre.

        Ce qu'il dessine ne compte pas pour le registre : sans cette distinction, son tableau
        de poids se serait ajouté au tableau des exécutions et l'aurait rendu incomptable.
        """
        self.replis.append(label)
        self.profondeur += 1
        try:
            yield self
        finally:
            self.profondeur -= 1

    def warning(self, texte, **_k):
        self.textes.append(texte)

    def columns(self, spec, **_k):
        largeur = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
        return [self] * largeur

    def caption(self, texte, **_k):
        self.legendes.append(texte)

    def text_input(self, _label, valeur="", **_k):
        return valeur

    def selectbox(self, _label, options, index=0, **_k):
        return list(options)[index] if options else None

    def dataframe(self, *_a, **_k):
        if not self.profondeur:  # le tableau du registre, pas celui replié du panneau Formule
            self.tableaux += 1

    def button(self, label, **_k):
        self.boutons.append(label)
        return False

    def checkbox(self, label, **_k):
        self.cases.append(label)
        return False

    def toast(self, *_a, **_k):
        pass


def test_le_registre_bat_tant_qu_une_execution_tourne(plateforme):
    """Une exécution terminée restait affichée « en cours » jusqu'au prochain clic."""
    import pandas as pd

    st = FauxStRegistre()
    experiences._suivi_du_registre(st, pd)
    assert st.run_every == "5s", "une exécution tourne : le registre doit se rafraîchir"
    assert st.tableaux == 1
    assert any("Formule" in r for r in st.replis), st.replis
    assert any("en cours" in x for x in st.textes), st.textes
    assert any("Pause" in b for b in st.boutons) and any("Arrêter" in b for b in st.boutons)

    # l'exécution se termine : la page entière doit se recharger une fois
    _ecrire(experiences.DOSSIER / "exp1" / "executions" / "20260907-100000" / "etat.json",
            {"etat": "terminee"})
    with pytest.raises(RerunDemande):
        experiences._suivi_du_registre(st, pd)
    assert st.reruns == ["app"]

    st.reruns.clear()
    experiences._suivi_du_registre(st, pd)
    assert st.reruns == [], "état stabilisé : plus de rechargement"
    assert st.run_every is None, "plus rien ne tourne : le registre cesse de sonder"


def test_les_boutons_d_arret_ne_collisionnent_pas_entre_les_deux_onglets(plateforme, tmp_path):
    """Le même run est affiché dans « Activités en cours » et dans « Mes expériences » :
    deux clés identiques feraient planter Streamlit.

    L'exécution doit écrire encore : les contrôles d'interruption ne s'affichent que dans ce
    cas (une sentinelle déposée dans une exécution morte ne fait que piéger la reprise), donc
    sans progression fraîche il n'y aurait aucune clé à comparer.
    """
    from datetime import datetime, timezone

    dossier = tmp_path / "executions" / "20260907-100000"
    dossier.mkdir(parents=True)
    (dossier / "progression.json").write_text(
        json.dumps({"faits": 12, "attendus": 100,
                    "maj": datetime.now(timezone.utc).isoformat()}),
        encoding="utf-8",
    )
    assert experiences.execution_vivante(dossier), "le préalable du test : elle écrit encore"
    e = {"experience": "exp1", "execution": "20260907-100000", "dossier": str(dossier)}

    class Cles(FauxStRegistre):
        def __init__(self):
            super().__init__()
            self.vues: list[str] = []

        def button(self, label, key=None, **_k):
            self.vues.append(str(key))
            return False

        def checkbox(self, label, key=None, **_k):
            self.vues.append(str(key))
            return False

    st = Cles()
    experiences._boutons_arret(st, e, 0, prefixe="act")
    experiences._boutons_arret(st, e, 0, prefixe="reg")
    assert len(set(st.vues)) == len(st.vues), f"clés dupliquées : {st.vues}"
    assert any(v.startswith("pause-act-") for v in st.vues)
    assert any(v.startswith("pause-reg-") for v in st.vues)


# ── Exécutions arrêtées : leur cause, leur reprise, leur obsolescence ────────────────────
# Demande du 2026-09-09 : une exécution qui s'arrête — quota épuisé, passerelle injoignable,
# PC éteint, pause — quittait l'onglet « Activités en cours » à la seconde même. Il fallait
# aller la chercher dans le registre de l'onglet Expériences pour comprendre et reprendre.


def _arretee(nom_exp: str, execution: str, etat: dict, *, erreur: dict | None = None,
             progression: dict | None = None) -> Path:
    """Une exécution arrêtée sur le disque, telle que le runner l'y laisse."""
    dossier = experiences.DOSSIER / nom_exp / "executions" / execution
    _ecrire(dossier / "etat.json", etat)
    if progression is not None:
        _ecrire(dossier / "progression.json", progression)
    if erreur is not None:
        (dossier / "erreurs.jsonl").write_text(json.dumps(erreur) + "\n", encoding="utf-8")
    return dossier


def test_la_cause_de_l_arret_est_lue_dans_ce_qui_est_ecrit(plateforme):
    """Chaque cause vient d'une trace, jamais d'une supposition : état, raison, journal."""
    _arretee("exp2", "20260908-090000",
             {"etat": "epuisee", "raison": "epuise: groq_key1 : 116/1000 requêtes/jour",
              "reprise_possible_a": "2026-09-10T07:00:00+00:00"})
    _arretee("exp2", "20260908-120000", {"etat": "en_pause", "raison": "pause — 55/2693 archivées"})
    _arretee("exp2", "20260908-130000",
             {"etat": "en_pause", "raison": "pause automatique — 420s sans avancée ; 2/2693 archivées"})

    causes = {l["execution"]: experiences.cause_interruption(l)
              for l in experiences.lister() if l["experience"] == "exp2" and l.get("execution")}

    quota = causes["20260908-090000"]
    assert quota["cle"] == "quota" and "quota épuisé" in quota["libelle"]
    assert "2026-09-10T07:00:00" in quota["detail"], "l'heure de reprise annoncée doit être dite"
    assert "116/1000" in quota["detail"], "la raison brute doit rester citée"

    assert causes["20260908-120000"]["cle"] == "pause"
    assert causes["20260908-130000"]["cle"] == "inactivite"
    assert "420s sans avancée" in causes["20260908-130000"]["detail"]


def test_un_runner_tue_et_une_coupure_reseau_se_distinguent(plateforme):
    """`etat.json` dit « en cours » pour toujours quand le PC s'arrête : la cause est ailleurs.

    Le réseau, lui, ne se lit QUE dans `erreurs.jsonl` — le runner ne le nomme jamais. Il ne
    prend la place que d'une cause qui ne se nomme pas elle-même.
    """
    mort = _arretee("exp2", "20260908-140000", {"etat": "en_cours"},
                    progression={"faits": 10, "attendus": 400,
                                 "maj": "2026-09-08T14:00:00+00:00"})
    coupe = _arretee("exp3", "20260908-150000", {"etat": "en_cours"},
                     progression={"faits": 3, "attendus": 400, "maj": "2026-09-08T15:00:00+00:00"},
                     erreur={"type": "Gateway LLM injoignable (ConnectError)",
                             "message": "connect refused", "horodatage": "2026-09-08T15:01:02+00:00"})
    assert not experiences.execution_vivante(mort) and not experiences.execution_vivante(coupe)

    par_dossier = {str(l["dossier"]): experiences.cause_interruption(l) for l in experiences.lister()}
    assert par_dossier[str(mort)]["cle"] == "processus", par_dossier[str(mort)]
    assert "plus rien d'écrit depuis" in par_dossier[str(mort)]["detail"]
    assert par_dossier[str(coupe)]["cle"] == "reseau", par_dossier[str(coupe)]
    detail = par_dossier[str(coupe)]["detail"]
    assert "connect refused" in detail, f"le message doit être cité : {detail}"
    assert "ConnectError" in detail, f"et le type, quand le message ne le porte pas : {detail}"


def test_un_quota_epuise_reste_un_quota_meme_apres_une_erreur_reseau(plateforme):
    """Le quota se nomme et porte son heure de reprise : un diagnostic réseau ne la remplace pas."""
    _arretee("exp2", "20260908-160000",
             {"etat": "epuisee", "raison": "epuise: crédits épuisés (HTTP 402)",
              "reprise_possible_a": "2026-09-09T07:00:00+00:00"},
             erreur={"type": "Gateway LLM injoignable (ConnectError)", "message": "x",
                     "horodatage": "2026-09-08T16:00:00+00:00"})
    ligne = next(l for l in experiences.lister() if l.get("execution") == "20260908-160000")
    assert experiences.cause_interruption(ligne)["cle"] == "quota"


def test_les_arretees_sont_listees_avec_de_quoi_les_reprendre(plateforme):
    """Le bloc de l'onglet : une ligne par exécution, sa cause, ses décisions déjà payées."""
    dossier = _arretee("exp2", "20260908-090000",
                       {"etat": "epuisee", "raison": "epuise: quota journalier",
                        "reprise_possible_a": "2026-09-10T07:00:00+00:00"},
                       progression={"faits": 55, "attendus": 2693, "pourcent": 2.0})
    (dossier / "decisions.jsonl").write_text('{"a": 1}\n' * 55, encoding="utf-8")

    act = experiences.interrompues()
    assert [l["execution"] for l in act["lignes"]] == ["20260908-090000"], act["lignes"]
    assert act["lignes"][0]["decisions"] == 55

    lances = []
    st = FauxSt()
    st.button = lambda label, **k: (st.boutons.append(label), True)[1]  # tous les boutons cliqués
    experiences.rendre_reprenables(st, act, lancer=lambda cible, vals: lances.append((cible, vals)))

    assert "🪫" in st.tout and "quota épuisé" in st.tout, st.tout
    assert "55 décision(s) déjà archivée(s)" in st.tout, st.tout
    assert any("Reprendre" in b for b in st.boutons), st.boutons
    assert lances and lances[0][0] == "experience-reprendre", lances
    assert lances[0][1]["EXP"] == "exp2"
    assert "controller" in lances[0][1]["REQUIS"], "la reprise démarre les services requis"


def test_une_archive_scellee_ou_terminee_n_est_pas_proposee(plateforme):
    """Une archive clôturée est immuable (E19) : la proposer serait une boucle."""
    dossier = _arretee("exp2", "20260908-170000", {"etat": "arretee", "raison": "arrêt demandé"})
    _ecrire(dossier / "execution.yaml", {"cloture": {"le": "2026-09-08T17:00:00", "etat": "arretee"}})

    assert [l["execution"] for l in experiences.interrompues()["lignes"]] == []


def test_une_execution_obsolete_n_est_ni_reprenable_ni_listee_mais_comptee(plateforme):
    """« Toutes les précédentes » sont obsolètes : la reprise ne porte que sur la dernière.

    `make experience-reprendre` reprend `_derniere_execution` — proposer une plus ancienne
    serait une promesse en l'air. Elle est COMPTÉE, pas escamotée.
    """
    _arretee("exp2", "20260908-090000", {"etat": "en_pause", "raison": "pause — 55/2693 archivées"})
    _arretee("exp2", "20260908-190000", {"etat": "en_pause", "raison": "pause — 3/2693 archivées"})

    lignes = {l["execution"]: l for l in experiences.lister() if l["experience"] == "exp2"}
    assert lignes["20260908-090000"]["obsolete"] and not lignes["20260908-090000"]["derniere"]
    assert lignes["20260908-190000"]["derniere"] and not lignes["20260908-190000"]["obsolete"]
    assert not experiences.est_reprenable(lignes["20260908-090000"])
    assert experiences.est_reprenable(lignes["20260908-190000"])

    act = experiences.interrompues()
    assert [l["execution"] for l in act["lignes"]] == ["20260908-190000"]
    assert act["obsoletes"] == 1, act
    st = FauxSt()
    experiences.rendre_reprenables(st, act)
    assert "1 exécution(s) arrêtée(s) non listée(s)" in st.tout, st.tout


def test_interrompue_et_attente_de_quota_morte_sont_reprenables(plateforme):
    """La CLI reprend toute archive non clôturée : ces deux états manquaient au tableau."""
    _arretee("exp2", "20260908-200000", {"etat": "interrompue", "raison": "pid mort"})
    _arretee("exp3", "20260908-210000",
             {"etat": "en_attente_quota", "raison": "epuise: quota", "reprise_possible_a": "2026-09-09T07:00"},
             progression={"faits": 1, "attendus": 400, "maj": "2026-09-08T21:00:00+00:00"})

    par_execution = {l["execution"]: l["cause"]["cle"] for l in experiences.interrompues()["lignes"]}
    assert par_execution.get("20260908-200000") == "processus", par_execution
    assert par_execution.get("20260908-210000") == "quota", par_execution


def test_une_duree_se_lit_en_heures_minutes_secondes():
    """« reste ≈ 6765 s » ne se lit pas ; les heures ne sont pas bornées à 24."""
    assert experiences._duree(6765) == "01:52:45"
    assert experiences._duree(0) == "00:00:00"
    assert experiences._duree(112805) == "31:20:05", "pas de retour à zéro au-delà d'un jour"
    assert experiences._duree(None) == "?" and experiences._duree("x") == "?" and experiences._duree(-1) == "?"


class FauxStFiltre(FauxStRegistre):
    """Un registre dont les cases répondent leur valeur par défaut, et qui retient son tableau.

    `FauxStRegistre` répond « non cochée » à toute case : la case « Masquer les obsolètes »
    étant cochée d'office, il faut honorer `value` pour éprouver le filtre tel qu'il s'ouvre.
    """

    def __init__(self, cases: dict | None = None):
        super().__init__()
        self.reponses = cases or {}
        self.vues: list = []

    def checkbox(self, label, value=False, **_k):
        self.cases.append(label)
        return self.reponses.get(label, value)

    def dataframe(self, donnees, *_a, **_k):
        if not self.profondeur:
            self.tableaux += 1
            self.vues.append(donnees)
        return None


def test_le_registre_masque_les_obsoletes_et_dit_combien(plateforme, monkeypatch):
    """La case « Terminées seulement » est remplacée par « Masquer les obsolètes » (2026-09-09).

    Rien ne disparaît en silence : le nombre de lignes masquées est écrit sous le tableau,
    comme le fait le panneau des entrées retirées.
    """
    pd = pytest.importorskip("pandas")
    _arretee("exp2", "20260908-090000", {"etat": "en_pause", "raison": "pause — 55/2693 archivées"})
    _arretee("exp2", "20260908-190000", {"etat": "en_pause", "raison": "pause — 3/2693 archivées"})

    st = FauxStFiltre()
    experiences._suivi_du_registre(st, pd)
    assert any("Masquer les obsolètes" in c for c in st.cases), st.cases
    assert not any("Terminées seulement" in c for c in st.cases), st.cases
    assert "fournisseur" in st.vues[-1].columns, "la colonne fournisseur doit être dans le tableau"
    executions = list(st.vues[-1]["execution"])
    assert "20260908-190000" in executions, "la dernière exécution reste toujours visible"
    assert "20260908-090000" not in executions, "l'obsolète est masquée par défaut"
    assert any("obsolète(s) masquée(s)" in l for l in st.legendes), st.legendes

    # décochée, elle les rend — avec ce que l'obsolescence coûte, écrit dans la colonne état
    st = FauxStFiltre({"Masquer les obsolètes": False})
    experiences._suivi_du_registre(st, pd)
    vue = st.vues[-1]
    assert "20260908-090000" in list(vue["execution"])
    etats = dict(zip(vue["execution"], vue["etat"]))
    assert "obsolète (partielle)" in etats["20260908-090000"], etats
    assert "obsolète" not in etats["20260908-190000"], etats
    # exp1 : une exécution terminée qu'une plus récente a remplacée garde un résultat complet
    assert "obsolète (résultat complet)" in etats["20260906-090000"], etats


# ── Qui sert les décisions : la colonne « fournisseur » ──────────────────────────────────
# Demande du 2026-09-09 : savoir d'un coup d'œil si une expérience tourne en local, chez
# Google, chez Groq, ou par un sous-agent Antigravity — dans le registre comme dans l'onglet.


@pytest.fixture
def fournisseurs(tmp_path, monkeypatch):
    """Un `providers.yaml` de poche : deux familles distantes, une locale, un modèle partagé."""
    chemin = tmp_path / "providers.yaml"
    _ecrire(chemin, {"providers": {
        "google_gemini35_key1": {"adapter": "google", "base_url": "https://generativelanguage.googleapis.com",
                                 "default_model": "gemini-3.5-flash-lite"},
        "google_gemini35_key2": {"adapter": "google", "base_url": "https://generativelanguage.googleapis.com",
                                 "default_model": "gemini-3.5-flash-lite"},
        "groq_oss_key1": {"adapter": "groq", "base_url": "https://api.groq.com/openai/v1",
                          "default_model": "openai/gpt-oss-120b"},
        "cerebras_oss_key1": {"adapter": "cerebras", "base_url": "https://api.cerebras.ai/v1",
                              "default_model": "openai/gpt-oss-120b"},
        "lmstudio_muse_key1": {"adapter": "openai_compatible",
                               "base_url": "http://host.docker.internal:1234/v1",
                               "default_model": "meta/muse-glimmer"},
    }})
    monkeypatch.setattr(experiences, "PROVIDERS_YAML", chemin)
    experiences._FAMILLES_CACHE.clear()
    yield chemin
    experiences._FAMILLES_CACHE.clear()


def test_le_fournisseur_se_deduit_du_modele_et_du_type_de_decideur(fournisseurs):
    """La famille est l'`adapter`, jamais le nom d'instance (suffixé `_key1`, onze fois Google)."""
    f = experiences.fournisseur_de
    assert f({"type": "passerelle", "modele": "gemini-3.5-flash-lite"}) == "google", "deux instances, une famille"
    assert f({"type": "passerelle", "modele": "meta/muse-glimmer"}) == "local", "LM Studio se voit à son base_url"
    # Un modèle servi par deux familles les porte toutes les deux : rien n'est arbitré au hasard.
    assert f({"type": "passerelle", "modele": "openai/gpt-oss-120b"}) == "cerebras · groq"
    # Antigravity l'emporte sur le nom du modèle : la décision ne passe pas par la passerelle.
    assert f({"type": "antigravity", "modele": "gemini-3.5-flash-lite"}) == "antigravity"
    # Un modèle qu'aucune instance ne sert : le dire, pas l'inventer.
    assert f({"type": "passerelle", "modele": "modele-fantome"}) == "inconnu"
    # Aucun LLM sollicité : la colonne `decideur` dit déjà l'heuristique.
    for dec in ({"type": "aleatoire"}, {"type": "duree_minimale"}, {"type": "modele"}, {}, None):
        assert f(dec) == "—", dec


def test_le_registre_porte_le_fournisseur_du_decideur_fige(plateforme, fournisseurs):
    """R6 vaut pour le fournisseur : c'est celui du snapshot, pas celui de la définition.

    exp1 est définie sur `m1` (aucune instance ne le sert) mais son exécution a tourné sur
    `gemini-3.5-flash-lite` : la ligne doit dire `google`, sinon elle ment sur l'archive.
    """
    _ecrire(experiences.DOSSIER / "exp1" / "executions" / "20260907-100000" / "execution.yaml",
            {"experience": {"decideur": {"type": "passerelle", "modele": "gemini-3.5-flash-lite"}}})

    lignes = {(l["experience"], l.get("execution")): l for l in experiences.lister()}
    assert lignes[("exp1", "20260907-100000")]["fournisseur"] == "google"
    assert lignes[("exp1", "20260906-090000")]["fournisseur"] == "inconnu", \
        "sans snapshot, la ligne retombe sur la définition — `m1` n'est servi par personne"
    assert lignes[("exp2", "20260906-110000")]["fournisseur"] == "—", "exp2 tire au hasard"


def test_les_lignes_de_l_onglet_nomment_qui_sert(plateforme, fournisseurs):
    """Demande : `🧪 antigravity / exp… / 2026-09-09_13_05_09`, et rien sans LLM."""
    _ecrire(experiences.DOSSIER / "exp1" / "executions" / "20260907-100000" / "execution.yaml",
            {"experience": {"decideur": {"type": "antigravity", "modele": "claude-opus-4.6"}}})
    st = FauxSt()
    experiences.rendre_activites(st, experiences.activites_en_cours())
    assert "🧪 **antigravity / exp1 / 20260907-100000**" in st.tout, st.tout

    # Un décideur sans LLM ne porte pas de préfixe : « — / » ferait croire à un trou.
    _ecrire(experiences.DOSSIER / "exp1" / "executions" / "20260907-100000" / "execution.yaml",
            {"experience": {"decideur": {"type": "aleatoire"}}})
    st = FauxSt()
    experiences.rendre_activites(st, experiences.activites_en_cours())
    assert "🧪 **exp1 / 20260907-100000**" in st.tout, st.tout


def test_le_bloc_des_arretees_nomme_aussi_qui_servait(plateforme, fournisseurs):
    """Deux listes voisines dans le même onglet : elles doivent se lire pareil."""
    _arretee("exp2", "20260908-090000", {"etat": "epuisee", "raison": "epuise: quota journalier"})
    _ecrire(experiences.DOSSIER / "exp2" / "executions" / "20260908-090000" / "execution.yaml",
            {"experience": {"decideur": {"type": "passerelle", "modele": "meta/muse-glimmer"}}})

    st = FauxSt()
    experiences.rendre_reprenables(st, experiences.interrompues())
    assert "**local / exp2 / 20260908-090000**" in st.tout, st.tout


# ── La cause réelle, pas seulement le type d'erreur ─────────────────────────────────────
# Demande du 2026-09-09 : « il y a une raison remontée, le rejet du prompt par exemple ». Elle
# était dans `erreurs.jsonl` — champ `message` — et l'écran n'en gardait que le `type`. Les
# messages ci-dessous sont ceux des archives réelles, à la lettre.


def _echecs(nom_exp: str, execution: str, lignes: list[dict]) -> None:
    dossier = experiences.DOSSIER / nom_exp / "executions" / execution
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "erreurs.jsonl").write_text(
        "".join(json.dumps(l) + "\n" for l in lignes), encoding="utf-8")


def _cause(execution: str) -> dict:
    ligne = next(l for l in experiences.lister() if l.get("execution") == execution)
    return experiences.cause_interruption(ligne)


def test_le_message_de_l_echec_est_affiche_pas_seulement_son_type(plateforme):
    """Le rejet de prompt : « Exception interne » ne dit rien, le message dit quoi corriger."""
    _arretee("exp2", "20260908-090000",
             {"etat": "en_pause", "raison": "pause automatique — 420s sans avancée ; 2/2693 archivées"})
    _echecs("exp2", "20260908-090000", [{
        "type": "Exception interne", "horodatage": "2026-09-08T09:30:00+00:00",
        "message": "Exception interne : variante de prompt 'expert_chaine_m5' introuvable dans "
                   "prompts.yaml (connues : b0_pristine, b_min, calibrated_20260611_1902)",
        "fournisseur": "google_gemini35_key1"}])

    c = _cause("20260908-090000")
    assert c["cle"] == "prompt" and c["icone"] == "🧩", c
    assert "variante introuvable" in c["libelle"], c["libelle"]
    assert "expert_chaine_m5" in c["detail"], "le message doit être cité, pas résumé à son type"
    assert "google_gemini35_key1" in c["detail"], "l'instance qui a lâché doit être nommée"
    assert "09:30:00" in c["detail"]


def test_un_sous_agent_muet_et_une_passerelle_saturee_ne_se_confondent_pas(plateforme):
    """Deux murs différents, deux gestes différents : relancer l'agent, ou attendre la passerelle."""
    _arretee("exp2", "20260908-100000",
             {"etat": "en_pause", "raison": "pause automatique — 420s sans avancée"})
    _echecs("exp2", "20260908-100000", [{"type": "antigravity", "message": "antigravity: pas de réponse en 600s",
                                         "fournisseur": "antigravity:gemini-3.8-flash",
                                         "horodatage": "2026-09-08T10:00:00+00:00"}])
    _arretee("exp3", "20260908-110000",
             {"etat": "en_pause", "raison": "pause automatique — 420s sans avancée"})
    _echecs("exp3", "20260908-110000", [{
        "type": "passerelle_occupee", "horodatage": "2026-09-08T11:00:00+00:00",
        "message": "passerelle_occupee: Providers saturés ou indisponibles après 8s (50 retries épuisés)"}])

    agent, saturee = _cause("20260908-100000"), _cause("20260908-110000")
    assert (agent["cle"], agent["icone"]) == ("agent", "🤖"), agent
    assert "pas de réponse en 600s" in agent["detail"]
    assert (saturee["cle"], saturee["icone"]) == ("saturation", "🚧"), saturee
    # « Timeout expiré » d'une passerelle débordée ne doit pas devenir une coupure réseau.
    _echecs("exp3", "20260908-110000", [{"type": "passerelle_occupee",
                                         "message": "passerelle_occupee: Timeout expiré",
                                         "horodatage": "2026-09-08T11:05:00+00:00"}])
    assert _cause("20260908-110000")["cle"] == "saturation", "la saturation passe avant le réseau"


def test_les_vraies_coupures_reseau_sont_encore_reconnues(plateforme):
    """Les deux messages de coupure des archives, que l'ancien motif ratait."""
    for i, message in enumerate(("Exception interne : [Errno -2] Name or service not known",
                                 "Exception interne : Server disconnected without sending a response.",
                                 "Gateway LLM injoignable (ConnectError)")):
        execution = f"2026090{i}-120000"
        _arretee("exp3", execution, {"etat": "interrompue", "raison": "pid mort"})
        _echecs("exp3", execution, [{"type": "Exception interne", "message": message,
                                     "horodatage": "2026-09-08T12:00:00+00:00"}])
        assert _cause(execution)["cle"] == "reseau", message


def test_les_echecs_identiques_consecutifs_sont_comptes(plateforme):
    """Un incident isolé et un mur ne se lisent pas pareil — et la fenêtre relue est bornée."""
    _arretee("exp2", "20260908-130000", {"etat": "en_pause", "raison": "pause automatique"})
    mur = {"type": "antigravity", "message": "antigravity: pas de réponse en 600s",
           "horodatage": "2026-09-08T13:00:00+00:00"}
    _echecs("exp2", "20260908-130000", [{**mur, "message": "autre chose"}, mur, mur, mur])
    c = _cause("20260908-130000")
    assert c["echecs_consecutifs"] == 3, c
    assert "(3 fois de suite)" in c["detail"], c["detail"]

    # Répétition qui remplit toute la fenêtre : on ne sait pas ce qu'il y a avant, donc « ≥ ».
    _echecs("exp2", "20260908-130000", [mur] * (experiences.ECHECS_A_RELIRE + 5))
    assert f"(≥{experiences.ECHECS_A_RELIRE} fois de suite)" in _cause("20260908-130000")["detail"]

    # Un seul échec : pas de compteur du tout, il n'apprendrait rien.
    _echecs("exp2", "20260908-130000", [mur])
    detail = _cause("20260908-130000")["detail"]
    assert "fois de suite" not in detail, detail


def test_le_quota_garde_la_priorite_sur_tout_diagnostic(plateforme):
    """Son heure de reprise vaut mieux que n'importe quelle lecture du journal d'erreurs."""
    _arretee("exp2", "20260908-140000",
             {"etat": "epuisee", "raison": "epuise: quota journalier",
              "reprise_possible_a": "2026-09-09T07:00:00+00:00"})
    _echecs("exp2", "20260908-140000", [{
        "type": "Exception interne", "horodatage": "2026-09-08T14:00:00+00:00",
        "message": "Exception interne : variante de prompt 'x' introuvable dans prompts.yaml"}])

    c = _cause("20260908-140000")
    assert c["cle"] == "quota", c
    assert "2026-09-09T07:00:00" in c["detail"]
    assert "variante de prompt 'x' introuvable" in c["detail"], \
        "le diagnostic ne prend pas la place du quota, mais reste dit dans le détail"
