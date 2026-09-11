"""Le tableau de bord se charge sans exception, onglet par onglet (harnais Streamlit AppTest).

Un NameError ou un import manquant dans `scripts/dashboard/app.py` ne se voit qu'au premier
clic dans le navigateur ; ce test le fait apparaître avant. Les appels externes (Docker, make)
échouent proprement en environnement de test : ce qui est vérifié, c'est l'absence d'exception
levée par le script lui-même.
"""

import contextlib
from pathlib import Path

import pytest

streamlit = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    # Le formulaire d'expérience retient ses choix dans un fichier : le harnais ne doit ni
    # le lire ni l'écraser, sinon le test dépendrait du dernier brouillon de l'utilisateur.
    import sys

    sys.path.insert(0, str(APP.parents[2]))
    from scripts.dashboard import experiences

    origine = experiences.ETAT_FORMULAIRE
    experiences.ETAT_FORMULAIRE = tmp_path_factory.mktemp("brouillon") / "formulaire.yaml"
    at = AppTest.from_file(str(APP), default_timeout=240)
    at.run()
    yield at
    experiences.ETAT_FORMULAIRE = origine  # la constante est partagée par tous les fichiers de test


def test_le_tableau_de_bord_se_charge_sans_exception(app):
    assert not app.exception, "\n".join(str(e.value) for e in app.exception)


def test_l_onglet_experiences_est_present(app):
    libelles = [t.label for t in app.tabs]
    assert any("Expériences" in lib for lib in libelles), libelles


def test_le_module_experiences_liste_le_registre():
    import sys
    sys.path.insert(0, str(APP.parents[2]))
    from scripts.dashboard import experiences
    lignes = experiences.lister()
    assert isinstance(lignes, list)
    for l in lignes:
        assert {"experience", "etat", "dossier"} <= set(l)


def test_les_cibles_de_la_plateforme_ont_leurs_variables():
    import sys
    sys.path.insert(0, str(APP.parents[2]))
    from scripts.dashboard import makefiles
    _, par_projet = makefiles.all_targets()
    par_nom = {t.name: t for t in par_projet["root"]}
    assert par_nom["jeu"].variables == ("POP", "NOM", "JOUR", "CONCURRENCE", "REQUIS")
    assert "EXP" in par_nom["experience-lancer"].variables and "JEU" in par_nom["run"].variables
    assert par_nom["experience-lancer"].group == "Plateforme d'expériences"
    variables = makefiles._root_variables()
    # Les choix d'EXP se lisent SUR LE DISQUE. Les figer sur le nom d'une expérience locale
    # rendait ce test rouge le jour où elle quittait `data/experiences/` : c'est la propriété
    # « la liste vient du registre » qui se vérifie, pas le contenu du registre du moment.
    racine = APP.parents[2] / "data" / "experiences"
    attendues = tuple(sorted(p.name for p in racine.iterdir()
                             if (p / "experience.yaml").is_file())) if racine.is_dir() else ()
    assert variables["EXP"].kind == "choice"
    assert variables["EXP"].choices == attendues


def test_le_formulaire_produit_un_experience_yaml_complet():
    import sys
    sys.path.insert(0, str(APP.parents[2]))
    from scripts.dashboard import experiences
    v = experiences.defauts()
    v.update({"population": "data/population/population_1000_AAMAS_v5", "jeu": "v5_j1", "variante": "b_min"})
    exp = experiences.construire_experience(v)
    for champ in ("nom", "population", "jeu", "gabarit", "decideur", "mode", "calendrier", "horizon_jours", "memoire", "evenements",
                  "graine_ordre", "graine_tirage", "regroupement", "tolerances_horaires", "max_candidats", "attente_max_s"):
        assert champ in exp, champ
    assert exp["population"]["chemin"] == "/data/eqasim-output/population_1000_AAMAS_v5" and exp["gabarit"]["variante"] == "b_min"
    # aller-retour : une expérience relue remplit le formulaire (dupliquer / s'inspirer)
    base = experiences.depuis_experience(exp)
    assert base["population"] == "data/population/population_1000_AAMAS_v5" and base["variante"] == "b_min"
    assert base["derive_de"] == exp["nom"], "la filiation cite le nom calculé de la source"
    assert "nom" not in base, "le nom ne se recopie pas : il se recalcule (N1)"
    variantes, active = experiences.variantes_prompt()
    assert "b_min" in variantes and active
    assert experiences.modeles()


def test_les_prompts_sont_lisibles_avant_de_choisir():
    import sys
    sys.path.insert(0, str(APP.parents[2]))
    from scripts.dashboard import experiences
    textes = experiences.prompts_textes()
    assert "b_min" in textes and textes["b_min"]["mots"] and "probabilit" in textes["b_min"]["contenu"].lower()
    assert textes["b_min"]["provenance"].get("role")


def test_ajouter_variante_sans_jamais_ecraser(tmp_path):
    import sys, shutil
    sys.path.insert(0, str(APP.parents[2]))
    import yaml
    from scripts.dashboard import experiences
    copie = tmp_path / "prompts.yaml"
    shutil.copy(experiences.PROMPTS_YAML, copie)
    avant = yaml.safe_load(copie.read_text())
    experiences.ajouter_variante("test_dash", "Ligne 1.\n\nLigne 2 : « accents » — ok.", derive_de="b_min", chemin=copie)
    apres = yaml.safe_load(copie.read_text())
    assert set(apres["prompts"]) == set(avant["prompts"]) | {"test_dash"} and apres["active"] == avant["active"]
    assert apres["prompts"]["test_dash"]["content"].strip() == "Ligne 1.\n\nLigne 2 : « accents » — ok."
    assert apres["prompts"]["test_dash"]["_provenance"]["derive_de"] == "b_min"
    with pytest.raises(ValueError, match="existe déjà"):
        experiences.ajouter_variante("b_min", "x", chemin=copie)
    with pytest.raises(ValueError, match="invalide"):
        experiences.ajouter_variante("nom avec espaces", "x", chemin=copie)
    assert yaml.safe_load(copie.read_text()) == apres, "un refus ne touche pas le fichier"


def test_quotas_par_modele_et_passerelle_injoignable():
    import sys
    sys.path.insert(0, str(APP.parents[2]))
    from scripts.dashboard import experiences
    assert experiences.etat_passerelle("http://127.0.0.1:1/health", timeout=0.2) is None
    q = experiences.quotas_par_modele({"google_gemini31_key1": {"daily_requests": 120, "rpd_limit": 500}, "google_gemini31_key2": {"daily_requests": 0, "rpd_limit": 500}})
    g = q["gemini-3.1-flash-lite"]
    assert g["marge"] == 880 and g["limite"] == 1000 and set(g["instances"]) == {"google_gemini31_key1", "google_gemini31_key2"}
    inconnu = experiences.quotas_par_modele(None)["gemini-3.1-flash-lite"]
    assert inconnu["inconnu"] is True and inconnu["limite"] == 1000


def test_R5_l_onglet_commandes_a_disparu(app):
    libelles = [t.label for t in app.tabs]
    assert not any("Commandes" in lib for lib in libelles), libelles
    for fichier in sorted(APP.parent.glob("*.py")):
        source = fichier.read_text(encoding="utf-8")
        assert "render_commands" not in source, f"catalogue laissé en code mort dans {fichier.name}"
        assert "▶ Commandes" not in source, f"renvoi périmé dans {fichier.name}"


def test_R7_l_onglet_s_appelle_activites_en_cours(app):
    libelles = [t.label for t in app.tabs]
    assert "📟 Activités en cours" in libelles, libelles
    for fichier in sorted(APP.parent.glob("*.py")):
        assert "📟 Lancements" not in fichier.read_text(encoding="utf-8"), f"renvoi périmé dans {fichier.name}"


def test_R4_la_vue_d_ensemble_montre_les_experiences_dans_son_fragment(app):
    source = APP.read_text(encoding="utf-8")
    debut = source.index("def render_overview()")
    fin = source.index("def agent_states_chart")
    corps = source[debut:fin]
    assert "rendre_activites" in corps, "la tuile des expériences doit vivre dans la vue d'ensemble"
    entete = source[source.index("@st.fragment", debut - 200):debut]
    assert 'run_every="10s"' in entete, "la tuile doit se rafraîchir avec les autres (10 s)"
    cablage = source[source.index("with tab_overview:"):source.index("with tab_run:")]
    assert "render_overview()" in cablage, "la vue d'ensemble doit être branchée sur son onglet"


def test_R8_l_onglet_activites_montre_le_disque_avant_les_jobs(app):
    source = APP.read_text(encoding="utf-8")
    corps = source[source.index("def render_activites()"):source.index("# ── Volet Tickets")]
    assert corps.index("render_activites_disque()") < corps.index("render_jobs_live()")


def test_R9_R16_chaque_ticket_offre_le_vocabulaire_ferme(app):
    from scripts.dashboard import tickets

    selecteurs = [s for s in app.selectbox if s.label == "Statut"]
    assert len(selecteurs) == len(tickets.load_tickets()), "un sélecteur par ticket"
    attendu = [f"{tickets.STATUS_ICON[s]} {s}" for s in tickets.EDITABLE_STATUSES]
    assert list(selecteurs[0].options) == attendu
    assert all("sans statut" not in str(o) for o in selecteurs[0].options)


def test_R20_aucun_bouton_desactive_sans_motif(app):
    from scripts.dashboard import experiences

    # La règle est « aucun contrôle grisé sans motif », PAS « il existe toujours un motif » :
    # sur une machine où la pile tourne et où le jeu du brouillon est clos, plus rien ne bloque
    # le formulaire — et depuis le 2026-09-09 un contrôleur éteint ne bloque plus « Lancer »,
    # qui le démarre. Ce qui se vérifie ici, c'est que tout bouton grisé porte sa raison.
    motifs = [str(c.value) for c in app.caption if "indisponible :" in str(c.value)]
    assert all(len(m.split("indisponible :", 1)[1].strip()) > 3 for m in motifs), motifs
    grises = [b.label for b in app.button if b.label in ("💾 Enregistrer", "🧮 Estimer le coût", "▶ Lancer")
              and b.disabled]
    assert all(any(label in m for m in motifs) for label in grises), (grises, motifs)
    # Le nom étant calculé (N1), aucun motif ne peut plus être « le nom est vide » : sur un
    # formulaire vierge il existe déjà, et les motifs portent sur le jeu et les services.
    assert not any("nom de l'expérience est vide" in m for m in motifs), motifs

    # Aucun bouton grisé de TOUTE la page ne reste sans signal : à défaut d'une ligne écrite,
    # une aide au survol qui dit ce qu'il attend.
    muets = [b.label for b in app.button
             if b.disabled and not (b.help or "").strip()
             and not any(b.label in m for m in motifs)]
    assert muets == [], f"boutons désactivés sans aide au survol ni motif : {muets}"

    # Champs et cases grisés : la règle vaut pour tout contrôle, pas seulement les boutons
    controles = [(genre, c) for genre, liste in (("champ", app.number_input), ("case", app.checkbox))
                 for c in liste if getattr(c, "disabled", False)]
    assert controles, "au premier chargement, « Horizon (jours) » et « Mémoire des agents » sont grisés"
    sans_aide = [f"{genre} « {c.label} »" for genre, c in controles if not (getattr(c, "help", "") or "").strip()]
    assert sans_aide == [], f"contrôles désactivés sans aide au survol : {sans_aide}"

    # Les lignes écrites exigées hors du formulaire. Conditionnelles à l'état réel de la
    # machine : la règle porte sur « un bouton désactivé dit pourquoi », pas sur l'état.
    lignes = [str(c.value) for c in app.caption]
    for fragment, motif in (("make stop-run", "Aucun run en cours"),
                            ("Reprendre", "Aucune exécution reprenable")):
        bouton = next((b for b in app.button if fragment in b.label), None)
        if bouton is not None and bouton.disabled:
            assert any(motif in l for l in lignes), f"« {bouton.label} » doit dire pourquoi"

    # la règle elle-même, hors interface : chaque manque nomme sa cause
    exp = {"nom": "", "jeu": {"nom": ""}}
    vides = experiences.motifs_indisponibilite(exp, jeu_clos=False, controleur_ok=False, registre=False)
    # Le nom se calcule (N1) : quand il manque, le motif nomme le champ qui l'empêche.
    assert "decideur" in vides["lancer"][0], vides["lancer"]
    assert vides["lancer"][1] == "aucun jeu de déplacements n'est préparé pour cette population"
    # Le contrôleur éteint ne bloque plus « Lancer » ni « Construire » : la cible make le
    # démarre. Il reste le verrou d'« Estimer », qui lit la réponse de la plateforme en direct.
    assert "le service `controller` ne tourne pas" in vides["estimer"], vides["estimer"]
    assert "le service `controller` ne tourne pas" not in vides["lancer"], vides["lancer"]
    # Ce qui bloque « Construire », c'est un démon Docker muet : là, personne ne démarre rien.
    muet = experiences.motifs_indisponibilite(exp, jeu_clos=False, controleur_ok=False,
                                              registre=True, docker_ok=False)
    assert any("démon Docker" in m for m in muet["construire"]), muet["construire"]
    assert any("démon Docker" in m for m in muet["lancer"]), muet["lancer"]

    pret = {"nom": "exp", "jeu": {"nom": "j1"}}
    aucun = experiences.motifs_indisponibilite(pret, jeu_clos=True, controleur_ok=True, registre=True)
    assert all(v == [] for v in aucun.values()), aucun

    encours = experiences.motifs_indisponibilite(pret, jeu_clos=False, controleur_ok=True, registre=True)
    assert encours["lancer"] == ["le jeu « j1 » n'est pas encore clos"]
    assert encours["enregistrer"] == [], "on peut enregistrer une expérience dont le jeu se construit"


def test_R6_les_boutons_contextuels_gardent_leurs_cibles_make(app):
    """Le catalogue de cibles a quitté l'interface, pas le code : les boutons s'en servent encore."""
    from scripts.dashboard import makefiles

    _, cibles = makefiles.all_targets()
    noms = {t.name for t in cibles.get("root", [])}
    attendues = {"up", "down", "restart", "run", "synthesis", "synthesis-open", "jeu",
                 "experience-definir", "experience-estimer", "experience-lancer", "experience-reprendre"}
    assert attendues <= noms, sorted(attendues - noms)

    # Et le chemin qu'emprunte chaque bouton : un job listé, son journal, un arrêt qui arrête.
    from scripts.dashboard import runner

    registre = runner.Registry()
    job = registre.launch("test:sommeil", ["sleep", "30"], APP.parents[2])
    journaux = [job.log_path]
    try:
        assert job in registre.jobs() and job.running
        assert job.log_path.exists(), "le lancement doit écrire son journal"
        assert registre.stop(job.id) is True
        assert not job.running and job.state in ("arrêté", "échec")
    finally:
        if job.running:
            registre.stop(job.id)
        registre.clear_finished()
        for journal in journaux:  # ne pas laisser de journaux d'essai dans experiments/.dashboard/
            journal.unlink(missing_ok=True)


def _app_avec_tickets(tmp_path, remplacement):
    """Une instance neuve du tableau de bord, avec une liste de tickets fabriquée."""
    import sys

    sys.path.insert(0, str(APP.parents[2]))
    from scripts.dashboard import experiences, tickets

    origine_brouillon = experiences.ETAT_FORMULAIRE
    experiences.ETAT_FORMULAIRE = tmp_path / "formulaire.yaml"
    origine = tickets.load_tickets
    tickets.load_tickets = remplacement
    try:
        at = AppTest.from_file(str(APP), default_timeout=240)
        at.run()
        return at
    finally:
        tickets.load_tickets = origine
        experiences.ETAT_FORMULAIRE = origine_brouillon


def _ticket_fabrique(stem: str, source: str, statut: str):
    from datetime import datetime

    from scripts.dashboard import tickets

    return tickets.Ticket(
        path=APP.parents[2] / "docs" / "tickets" / f"{stem}.md", number="042",
        title=f"Titre de {stem}", status=statut, status_source=source, done=1, todo=1,
        state_line="", note="", modified=datetime.now(), lines=10,
    )


def test_R23_un_statut_mal_saisi_n_emporte_pas_les_autres_onglets(tmp_path):
    """Une faute de frappe dans le fichier interrompait le script : l'onglet Expériences
    disparaissait avec l'onglet Tickets, sous forme de traceback."""
    from scripts.dashboard import tickets

    def statut_fautif():
        raise tickets.StatutInconnu(
            "ticket_011_arrivees_perdues_gama : statut de surcharge inconnu 'a faire'")

    at = _app_avec_tickets(tmp_path, statut_fautif)

    assert not at.exception, "\n".join(str(e.value) for e in at.exception)
    erreurs = [str(e.value) for e in at.error]
    assert any("statut inconnu" in e and "'a faire'" in e for e in erreurs), erreurs
    assert any("à faire" in str(c.value) and "abandonné" in str(c.value) for c in at.caption), \
        "les statuts admis doivent être rappelés"
    assert any("Nouvelle expérience" in str(s.value) for s in at.subheader), \
        "l'onglet 🧪 Expériences doit rester affiché"

    # Une clé invalide ne doit pas être annoncée comme un statut inconnu (R28)
    def cle_fautive():
        raise tickets.CleInvalide("tickets_status.yaml : 1 clé(s) ne désignent pas exactement "
                                  "un ticket ('ticket_005' → ticket_005_choix_modal_probabiliste)")

    autre = _app_avec_tickets(tmp_path, cle_fautive)
    assert not autre.exception, "\n".join(str(e.value) for e in autre.exception)
    messages = [str(e.value) for e in autre.error]
    assert any("clé invalide" in m for m in messages), messages
    assert not any("statut inconnu" in m for m in messages), messages
    assert any("Nouvelle expérience" in str(s.value) for s in autre.subheader)


def test_R25_un_ticket_sans_entree_le_dit_avant_tout_enregistrement(tmp_path):
    from scripts.dashboard import tickets

    fabriques = [_ticket_fabrique("ticket_900_sans_entree", "cases", tickets.DOING),
                 _ticket_fabrique("ticket_901_surcharge", "surcharge", tickets.DONE)]
    at = _app_avec_tickets(tmp_path, lambda: fabriques)

    assert not at.exception, "\n".join(str(e.value) for e in at.exception)
    avertissements = [str(c.value) for c in at.caption if "n'a pas d'entrée" in str(c.value)]
    assert len(avertissements) == 1, avertissements
    assert "source : cases" in avertissements[0]
    assert "Enregistrer écrira le statut choisi" in avertissements[0]


def test_R12_le_compteur_de_statuts_suit_les_tickets(app):
    from scripts.dashboard import tickets

    items = tickets.load_tickets()
    comptes = tickets.summary(items)
    assert sum(comptes.values()) == len(items)
    for statut in tickets.STATUS_ORDER:
        assert comptes[statut] == sum(1 for t in items if t.status == statut), statut


def test_R14_une_note_non_touchee_n_est_pas_reecrite(tmp_path):
    """L'interface envoie toujours le contenu de la zone de texte telle qu'elle a été rendue.

    Si elle l'envoyait tel quel, une modification faite à la main dans le fichier pendant que
    le tiroir est ouvert serait silencieusement rétablie à la valeur affichée. Le formulaire
    doit donc dire « je n'ai pas touché à la note » plutôt que de la réécrire.
    """
    import sys

    sys.path.insert(0, str(APP.parents[2]))
    from scripts.dashboard import experiences, tickets

    appels = []
    fabriques = [_ticket_fabrique("ticket_902_note", "surcharge", tickets.DOING)]
    fabriques[0].note = "note d'origine"

    origine_brouillon = experiences.ETAT_FORMULAIRE
    experiences.ETAT_FORMULAIRE = tmp_path / "formulaire.yaml"
    origine_liste, origine_ecriture = tickets.load_tickets, tickets.save_override
    tickets.load_tickets = lambda: fabriques
    tickets.save_override = lambda cle, statut, note=None, **_: appels.append((cle, statut, note)) or True
    try:
        at = AppTest.from_file(str(APP), default_timeout=240)
        at.run()
        soumission = next(b for b in at.button if "Enregistrer le statut" in b.label)
        soumission.click().run()
    finally:
        tickets.load_tickets, tickets.save_override = origine_liste, origine_ecriture
        experiences.ETAT_FORMULAIRE = origine_brouillon

    assert appels, "le clic doit appeler l'écriture"
    cle, statut, note = appels[-1]
    assert cle == "ticket_902_note"
    assert statut == tickets.DOING
    assert note is None, f"note non touchée : attendu None pour ne rien réécrire, reçu {note!r}"


@contextlib.contextmanager
def _app_patchee(tmp_path, patchs: dict):
    """Le tableau de bord démarré avec des attributs remplacés, qui le restent pendant les clics."""
    import sys

    sys.path.insert(0, str(APP.parents[2]))
    from scripts.dashboard import experiences

    origines = {}
    for cible, remplacements in patchs.items():
        for nom, valeur in remplacements.items():
            origines[(cible, nom)] = getattr(cible, nom)
            setattr(cible, nom, valeur)
    brouillon = experiences.ETAT_FORMULAIRE
    experiences.ETAT_FORMULAIRE = tmp_path / "formulaire.yaml"
    try:
        at = AppTest.from_file(str(APP), default_timeout=240)
        at.run()
        yield at
    finally:
        for (cible, nom), valeur in origines.items():
            setattr(cible, nom, valeur)
        experiences.ETAT_FORMULAIRE = brouillon


def test_R6_un_bouton_contextuel_resout_sa_cible_et_appelle_le_registre(tmp_path):
    """Le clic, pas le décor : la cible est résolue depuis le Makefile et remise au registre."""
    from scripts.dashboard import runner

    appels = []

    def faux_launch(self, label, argv, cwd, flags=()):
        appels.append((label, argv, cwd, flags))
        return None

    with _app_patchee(tmp_path, {runner.Registry: {"launch": faux_launch}}) as at:
        bouton = next(b for b in at.button if "make synthesis" in b.label and "open" not in b.label)
        assert not bouton.disabled
        bouton.click().run()

    assert appels, "le clic doit passer par le registre de jobs"
    label, argv, cwd, _flags = appels[-1]
    assert label.endswith(":synthesis")
    assert argv[:2] == ["make", "synthesis"], argv
    assert Path(cwd) == APP.parents[2]


def test_R18_le_clic_lance_la_construction_et_arme_la_surveillance(tmp_path):
    from scripts.dashboard import experiences, runner

    appels = []

    def faux_launch(self, label, argv, cwd, flags=()):
        appels.append((label, argv))
        return None

    # Le bouton de warm-up n'apparaît QUE lorsqu'aucun jeu n'existe encore pour la population :
    # préparer un second jeu ne se fait plus d'ici. On se place donc sans aucun jeu.
    with _app_patchee(tmp_path, {runner.Registry: {"launch": faux_launch},
                                 experiences: {"jeux": lambda: []}}) as at:
        bouton = next(b for b in at.button if "Warm-up" in b.label)
        bouton.click().run()
        arme = at.session_state["_warmup_lance_a"]

    assert appels, "le clic doit lancer `make jeu`"
    label, argv = appels[-1]
    assert label.endswith(":jeu") and argv[:2] == ["make", "jeu"], argv
    assert arme > 0, "la surveillance du dossier doit être armée"


def test_R17_l_avertissement_ne_parait_que_sans_aucun_jeu(tmp_path):
    from scripts.dashboard import experiences

    with _app_patchee(tmp_path, {experiences: {"jeux": lambda: []}}) as sans:
        avertissements = [str(w.value) for w in sans.warning]
    assert any("Aucun jeu de déplacements préparé" in a for a in avertissements), avertissements

    en_cours = [{"nom": "j_prep", "population": "population_1000_AAMAS", "jour": "2026-03-16",
                 "clos": False, "couverts": 10, "attendus": 100}]
    with _app_patchee(tmp_path, {experiences: {"jeux": lambda: en_cours}}) as avec:
        muet = not any("Aucun jeu de déplacements préparé" in str(w.value) for w in avec.warning)
        libelles = [str(o) for s in avec.selectbox for o in s.options]
    assert muet, "un jeu en construction suffit : l'avertissement ne doit plus paraître"
    assert any("(EN PRÉPARATION)" in lib for lib in libelles), \
        "le jeu en construction doit être libellé comme tel dans la liste"


def test_R16_le_selecteur_rendu_porte_le_statut_en_vigueur(tmp_path):
    from scripts.dashboard import tickets

    fabriques = [_ticket_fabrique("ticket_910_veille", "surcharge", tickets.PAUSED),
                 _ticket_fabrique("ticket_911_sans", "cases", tickets.UNKNOWN)]
    at = _app_avec_tickets(tmp_path, lambda: fabriques)

    valeurs = [s.value for s in at.selectbox if s.label == "Statut"]
    assert valeurs[0] == tickets.PAUSED, valeurs
    assert valeurs[1] == tickets.TODO, \
        "sans statut : le sélecteur part de « à faire », et le tiroir dit qu'il n'y a pas d'entrée"


def test_R27_le_texte_saisi_gagne_et_n_est_jamais_jete(tmp_path):
    """Le champ n'avait pas de clé : son identité dépendait de `value=`, donc une édition
    du fichier entre deux rendus faisait jeter le texte tapé, avec un message trompeur."""
    import sys

    sys.path.insert(0, str(APP.parents[2]))
    from scripts.dashboard import experiences, tickets

    appels = []
    fabriques = [_ticket_fabrique("ticket_912_note", "surcharge", tickets.DOING)]
    fabriques[0].note = "note d'origine"

    brouillon = experiences.ETAT_FORMULAIRE
    experiences.ETAT_FORMULAIRE = tmp_path / "formulaire.yaml"
    origine_liste, origine_ecriture = tickets.load_tickets, tickets.save_override
    tickets.load_tickets = lambda: fabriques
    tickets.save_override = lambda cle, statut, note=None, **_: appels.append((cle, statut, note)) or True
    try:
        at = AppTest.from_file(str(APP), default_timeout=240)
        at.run()
        at.text_area(key="note-ticket_912_note").set_value("NOTE TAPÉE PAR L'UTILISATEUR").run()
        fabriques[0].note = "note corrigée à la main dans le fichier"  # édition concurrente
        soumission = next(b for b in at.button if "Enregistrer le statut" in b.label)
        soumission.click().run()
    finally:
        tickets.load_tickets, tickets.save_override = origine_liste, origine_ecriture
        experiences.ETAT_FORMULAIRE = brouillon

    assert appels, "le clic doit appeler l'écriture"
    _cle, _statut, note = appels[-1]
    assert note == "NOTE TAPÉE PAR L'UTILISATEUR", f"le texte saisi ne doit jamais être jeté, reçu {note!r}"
    assert not any("Rien à enregistrer" in str(i.value) for i in at.info), \
        "aucun message ne peut dire « rien à enregistrer » quand du texte a été saisi"


def test_R8_les_jobs_en_cours_passent_avant_les_termines():
    from scripts.dashboard import runner

    registre = runner.Registry()
    import time as _t

    fini = registre.launch("test:fini", ["true"], APP.parents[2])
    for _ in range(300):
        registre.jobs()  # c'est la lecture qui moissonne les processus terminés
        if not fini.running:
            break
        _t.sleep(0.02)
    tourne = registre.launch("test:tourne", ["sleep", "30"], APP.parents[2])
    try:
        assert not fini.running and tourne.running
        brut = registre.jobs()
        assert brut.index(tourne) < brut.index(fini), "le registre rend l'ordre chronologique inverse"
        trie = runner.par_priorite(brut)
        assert trie[0] is tourne, "ce qui tourne passe devant"
        assert trie.index(tourne) < trie.index(fini)
    finally:
        registre.stop(tourne.id)
        registre.clear_finished()
        for job in (fini, tourne):
            job.log_path.unlink(missing_ok=True)


def test_R22_un_brouillon_restaure_n_ecrit_aucune_experience(tmp_path):
    """Le vrai risque : un démarrage complet avec formulaire restauré qui enregistrerait tout seul."""
    import sys

    sys.path.insert(0, str(APP.parents[2]))
    from scripts.dashboard import experiences

    brouillon = tmp_path / "formulaire.yaml"
    origine = experiences.ETAT_FORMULAIRE
    experiences.ETAT_FORMULAIRE = brouillon
    try:
        experiences.sauver_etat_formulaire({**experiences.defauts(), "attente_max_s": 300})
        avant = sorted(p.name for p in experiences.DOSSIER.iterdir()) if experiences.DOSSIER.is_dir() else []

        def refuser(*_a, **_k):
            raise AssertionError("un démarrage ne doit rien enregistrer sans clic")

        origine_enregistrer = experiences.enregistrer
        experiences.enregistrer = refuser
        try:
            at = AppTest.from_file(str(APP), default_timeout=240)
            at.run()
            assert not at.exception, "\n".join(str(e.value) for e in at.exception)
            assert any(int(z.value) == 300 for z in at.number_input), "le brouillon doit être restauré"
        finally:
            experiences.enregistrer = origine_enregistrer

        apres = sorted(p.name for p in experiences.DOSSIER.iterdir()) if experiences.DOSSIER.is_dir() else []
        assert apres == avant
    finally:
        experiences.ETAT_FORMULAIRE = origine


def _job_fabrique(tmp_path, ident: str, *, tourne: bool):
    """Un job du registre, sans processus réel : `running` = proc posé et returncode absent.

    Le journal vit sous `experiments/.dashboard/` (ignoré par git) : le volet l'affiche en
    chemin relatif à la racine du dépôt.
    """
    import time

    from scripts.dashboard import runner

    dossier = APP.parents[2] / "experiments" / ".dashboard"
    dossier.mkdir(parents=True, exist_ok=True)
    journal = dossier / f"essai-{ident}.log"
    journal.write_text(f"sortie de {ident}\n", encoding="utf-8")
    return runner.Job(
        id=ident, label=f"root:{ident}", argv=["make", ident], cwd=APP.parents[2],
        log_path=journal, started_at=time.time() - (10 if tourne else 600),
        proc=object() if tourne else None,
        returncode=None if tourne else 0,
        finished_at=None if tourne else time.time() - 60,
    )


def test_R8_le_panneau_montre_ce_qui_tourne_en_premier(tmp_path):
    """Le tri doit être utilisé PAR le panneau : testé sur le rendu, pas sur le source."""
    from scripts.dashboard import runner

    fini = _job_fabrique(tmp_path, "termine", tourne=False)
    tourne = _job_fabrique(tmp_path, "encours", tourne=True)
    # `jobs()` rend le plus récent d'abord : ici le job TERMINÉ est le plus récent.
    with _app_patchee(tmp_path, {runner.Registry: {"jobs": lambda self: [fini, tourne]}}) as at:
        titres = [str(e.label) for e in at.expander]
        resume = [str(m.value) for m in at.markdown if "en cours" in str(m.value) and "terminé" in str(m.value)]
        purge = next(b for b in at.button if "Purger" in b.label)
        purge_grisee = purge.disabled

    for reste in (APP.parents[2] / "experiments" / ".dashboard").glob("essai-*.log"):
        reste.unlink()

    lignes = [x for x in titres if "root:" in x]
    assert lignes, titres
    assert "encours" in lignes[0], f"ce qui tourne doit passer devant : {lignes}"
    assert any("root:termine" in x for x in lignes), "les jobs terminés restent listés"
    assert resume, "le volet doit résumer combien tournent et combien sont terminés"
    assert not purge_grisee, "avec un job terminé, la purge est disponible"


def test_R8_la_purge_est_grisee_quand_tout_tourne(tmp_path):
    from scripts.dashboard import runner

    tourne = _job_fabrique(tmp_path, "encours", tourne=True)
    try:
        with _app_patchee(tmp_path, {runner.Registry: {"jobs": lambda self: [tourne]}}) as at:
            purge = next(b for b in at.button if "Purger" in b.label)
            assert purge.disabled, "rien à purger tant qu'ils tournent tous"
            assert (purge.help or "").strip(), "et le motif est dit au survol (R20)"
    finally:
        for reste in (APP.parents[2] / "experiments" / ".dashboard").glob("essai-*.log"):
            reste.unlink()


def _clic_statut(tmp_path, fabriques, *, avant_clic=None, ecriture=None):
    """Ouvre le tiroir d'un ticket, laisse un test agir, puis soumet le formulaire."""
    import sys

    sys.path.insert(0, str(APP.parents[2]))
    from scripts.dashboard import experiences, tickets

    appels = []
    brouillon = experiences.ETAT_FORMULAIRE
    experiences.ETAT_FORMULAIRE = tmp_path / "formulaire.yaml"
    origine_liste, origine_ecriture = tickets.load_tickets, tickets.save_override
    tickets.load_tickets = lambda: fabriques

    def faux_ecrire(cle, statut, note=None, **_):
        appels.append((cle, statut, note))
        return ecriture if ecriture is not None else True

    tickets.save_override = faux_ecrire
    try:
        at = AppTest.from_file(str(APP), default_timeout=240)
        at.run()
        if avant_clic is not None:
            avant_clic(at)
        next(b for b in at.button if "Enregistrer le statut" in b.label).click().run()
        return at, appels
    finally:
        tickets.load_tickets, tickets.save_override = origine_liste, origine_ecriture
        experiences.ETAT_FORMULAIRE = brouillon


def test_R27_le_tiroir_dit_quand_la_note_a_change_dans_le_fichier(tmp_path):
    """Note non touchée mais fichier modifié : la valeur du fichier est gardée, et c'est dit."""
    from scripts.dashboard import tickets

    fabriques = [_ticket_fabrique("ticket_913_note", "surcharge", tickets.DOING)]
    fabriques[0].note = "note d'origine"

    def editer_le_fichier(_at):
        fabriques[0].note = "note corrigée à la main"

    at, appels = _clic_statut(tmp_path, fabriques, avant_clic=editer_le_fichier)

    assert appels[-1][2] is None, "note non touchée : elle ne doit pas être réécrite"
    lignes = [str(c.value) for c in at.caption]
    assert any("changé dans le fichier" in l for l in lignes), lignes


def test_R27_une_retouche_d_espaces_ne_ment_pas_sur_ce_qui_s_est_passe(tmp_path):
    """Écriture sans effet APRÈS une saisie : le message ne peut pas dire « rien à enregistrer »."""
    from scripts.dashboard import tickets

    fabriques = [_ticket_fabrique("ticket_914_espaces", "surcharge", tickets.DOING)]
    fabriques[0].note = "une note"

    def taper_des_espaces(at):
        at.text_area(key="note-ticket_914_espaces").set_value("une   note").run()

    at, appels = _clic_statut(tmp_path, fabriques, avant_clic=taper_des_espaces, ecriture=False)

    assert appels[-1][2] == "une   note", "le texte saisi doit être transmis tel quel"
    messages = [str(i.value) for i in at.info]
    assert not any("Rien à enregistrer" in m for m in messages), messages
    assert any("espaces" in m for m in messages), messages


def _plateforme_isolee(tmp_path):
    """Patchs pour cliquer « Enregistrer » sans jeu, sans conteneur, et sans écrire dans le dépôt."""
    import sys

    sys.path.insert(0, str(APP.parents[2]))
    from scripts.dashboard import experiences

    dossier = tmp_path / "experiences"
    dossier.mkdir(parents=True, exist_ok=True)
    return experiences, {experiences: {
        "jeux": lambda: [],                        # la population n'a aucun jeu préparé
        "services_actifs": lambda *a, **k: set(),  # `controller` arrêté : aucun docker exec réel
        "DOSSIER": dossier,
    }}  # REPO_ROOT n'est PAS patché : `populations()` en a besoin pour les vrais dossiers


def test_R1_R2_le_clic_enregistre_sans_jeu_et_nomme_le_jeu_attendu(tmp_path):
    """De bout en bout : le fichier écrit nomme exactement le jeu que le warm-up construirait."""
    import yaml

    from scripts.dashboard import runner

    experiences, patchs = _plateforme_isolee(tmp_path)
    lancements = []
    patchs[runner.Registry] = {"launch": lambda self, label, argv, cwd, flags=(): lancements.append(argv)}

    with _app_patchee(tmp_path, patchs) as at:
        enregistrer = next(b for b in at.button if b.label == "💾 Enregistrer")
        assert not enregistrer.disabled, "sans jeu et sans conteneur, enregistrer doit rester possible"
        enregistrer.click().run()
        message = "\n".join(str(c.value) for c in at.code)
        next(b for b in at.button if "Warm-up" in b.label or "Préparer un autre jeu" in b.label).click().run()

    ecrits = list((tmp_path / "experiences").glob("*/experience.yaml"))
    assert len(ecrits) == 1, f"le clic doit écrire un fichier d'expérience, et un seul : {ecrits}"
    ecrit = ecrits[0]
    nom_jeu = yaml.safe_load(ecrit.read_text(encoding="utf-8"))["jeu"]["nom"]

    assert lancements, "le bouton de warm-up doit lancer `make jeu`"
    nom_passe = dict(a.split("=", 1) for a in lancements[-1] if "=" in a)["NOM"]
    assert nom_jeu == nom_passe, f"le jeu nommé ({nom_jeu}) doit être celui que le warm-up construit ({nom_passe})"

    assert "validation non tentée" in message, message
    assert f"jeu attendu « {nom_jeu} » : absent" in message, message
    assert f"{ecrit.parent.name}/experience.yaml" in message, message
    assert not (ecrit.parent / "executions").exists()


def test_reenregistrer_un_nom_deja_execute_ne_demande_plus_de_confirmation(tmp_path):
    """Le garde-fou d'écrasement a été retiré : réenregistrer un nom déjà exécuté est direct.

    Les exécutions déjà archivées gardent leur copie figée de la définition ; seule la
    définition courante est réécrite, sans case à cocher.
    """
    experiences, patchs = _plateforme_isolee(tmp_path)

    with _app_patchee(tmp_path, patchs) as at:
        # Le nom calculé par le formulaire, puis une exécution archivée sous ce nom : c'est
        # exactement le cas « ce nom a déjà tourné ».
        nom = str(next(c for c in at.code if str(c.value).startswith("exp_")).value)
        execution = tmp_path / "experiences" / nom / "executions" / "2026-09-01_10_00_00"
        execution.mkdir(parents=True)
        (execution / "etat.json").write_text('{"etat": "terminee"}', encoding="utf-8")

    with _app_patchee(tmp_path, patchs) as at:
        assert not [c for c in at.checkbox if "porte déjà" in c.label], \
            "plus de case de confirmation d'écrasement"
        enregistrer = next(b for b in at.button if b.label == "💾 Enregistrer")
        assert not enregistrer.disabled, "réenregistrer un nom déjà exécuté est désormais direct"


def test_les_deux_lectures_de_providers_pointent_le_meme_fichier():
    """Deux constantes pour un fichier : le refactor du module LLM en a déplacé une seule,
    et la liste des modèles du formulaire s'est vidée sans le dire."""
    from scripts.dashboard import experiences, metrics

    assert experiences.PROVIDERS_YAML == metrics.PROVIDERS_YAML
    assert experiences.PROVIDERS_YAML.is_file(), f"{experiences.PROVIDERS_YAML} est introuvable"
    assert experiences.modeles(), "la liste des modèles du formulaire ne doit pas être vide"


def _plateforme_avec_survivante(tmp_path):
    """Une expérience prête à lancer, plus une exécution qui tourne encore ailleurs."""
    import json
    import sys

    import yaml

    sys.path.insert(0, str(APP.parents[2]))
    from scripts.dashboard import experiences

    exps = tmp_path / "experiences"
    population = experiences.populations()[0]
    # Le nom se calcule des paramètres (N1) : l'exécution qui survit doit porter le nom que
    # le formulaire vierge produira, sinon elle relève d'une autre expérience.
    definition = experiences.construire_experience(
        {**experiences.defauts(), "sans_jeu": False,
         "jeu": experiences.nom_jeu_attendu(population, "2026-03-16")})
    nom = definition["nom"]
    survivante = exps / nom / "executions" / "2026-09-07_10_00_00"
    survivante.mkdir(parents=True)
    (survivante / "etat.json").write_text(json.dumps({"etat": "en_cours"}), encoding="utf-8")
    # La définition ENTIÈRE, pas un squelette : une définition différente porterait un autre
    # nom (indice `_2`, N10) et l'exécution ne serait plus celle de cette expérience.
    (exps / nom / "experience.yaml").write_text(
        yaml.safe_dump(definition, allow_unicode=True, sort_keys=False), encoding="utf-8")

    nom_jeu = experiences.nom_jeu_attendu(population, "2026-03-16")
    jeu = [{"nom": nom_jeu, "population": Path(population).name, "jour": "2026-03-16",
            "clos": True, "couverts": 98, "attendus": 100}]

    patchs = {experiences: {
        "DOSSIER": exps,
        "jeux": lambda: jeu,
        "services_actifs": lambda *a, **k: {"controller"},
    }}
    return experiences, patchs, survivante  # `lister()` lit DOSSIER à l'appel


def test_le_lancement_ne_stoppe_plus_les_concurrents(tmp_path):
    """La case « Arrêter d'abord » a été retirée : lancer n'interrompt plus ce qui tourne.

    Le lancement part directement (l'expérience est enregistrée puis `experience-lancer`),
    et l'exécution qui tournait ailleurs n'est pas signalée d'un `STOP`.
    """
    from scripts.dashboard import runner

    experiences, patchs, survivante = _plateforme_avec_survivante(tmp_path)
    lances = []
    patchs[runner.Registry] = {
        "launch": lambda self, label, argv, cwd, flags=(): lances.append(label),
    }

    with _app_patchee(tmp_path, patchs) as at:
        assert not [c for c in at.checkbox if "Arrêter d'abord" in c.label], \
            "plus de case « Arrêter d'abord »"

        lancer = next(b for b in at.button if b.label == "▶ Lancer")
        assert not lancer.disabled, "le jeu est clos et le contrôleur tourne"
        lancer.click().run()

    assert not (survivante / "STOP").is_file(), "le lancement ne demande plus l'arrêt des concurrents"
    assert any(l.endswith(":experience-lancer") for l in lances), lances


def test_N1_le_nom_est_affiche_calcule_et_non_saisi(tmp_path):
    """Le champ de saisie a disparu : la page MONTRE le nom que les paramètres imposent."""
    experiences, patchs = _plateforme_isolee(tmp_path)

    with _app_patchee(tmp_path, patchs) as at:
        assert not [i for i in at.text_input if i.label == "Nom de l'expérience"], \
            "le nom ne se saisit plus"
        assert any("calculé" in str(m.value) for m in at.markdown), \
            "la page doit dire que le nom est calculé"
        noms = [str(c.value) for c in at.code if str(c.value).startswith("exp_")]
        assert len(noms) == 1, f"un nom calculé, affiché une fois : {noms}"
        assert experiences.MOTIF_NOM.match(noms[0]), noms[0]
        assert not [b for b in at.button if "Utiliser «" in b.label], \
            "plus rien à proposer : le nom n'est plus une saisie à corriger"
        assert not next(b for b in at.button if b.label == "💾 Enregistrer").disabled


def test_N10_une_definition_deja_enregistree_est_annoncee_comme_telle(tmp_path):
    """Mêmes paramètres = même expérience : la page le dit au lieu de la réécrire en silence."""
    experiences, patchs = _plateforme_isolee(tmp_path)

    with _app_patchee(tmp_path, patchs) as at:
        next(b for b in at.button if b.label == "💾 Enregistrer").click().run()

    with _app_patchee(tmp_path, patchs) as at:
        infos = [str(i.value) for i in at.info]
        assert any("déjà" in i and "exécution" in i for i in infos), infos


def test_R1_R3_le_bloc_des_services_dit_ce_qui_manque_et_le_lancement_le_demarre(tmp_path):
    """Le bloc dit ce qui manque, et c'est « ▶ Lancer » qui le démarre — plus aucun bouton.

    Le bouton « Démarrer les N service(s) manquant(s) » a été retiré le 2026-09-09 : c'était
    une étape à ne pas oublier avant de cliquer sur « Lancer », alors que la cible make sait
    garantir ses services elle-même (`services-pretes`). Le lancement porte donc `REQUIS=` —
    juste les services de l'expérience, jamais la métrologie.
    """
    from scripts.dashboard import runner

    experiences, patchs = _plateforme_isolee(tmp_path)
    population = experiences.populations()[0]
    jeu = [{"nom": experiences.nom_jeu_attendu(population, "2026-03-16"),
            "population": Path(population).name, "jour": "2026-03-16", "clos": True,
            "couverts": 98, "attendus": 100}]
    patchs[experiences]["jeux"] = lambda: jeu
    patchs[experiences]["services_actifs"] = lambda *a, **k: {"controller", "redis"}
    lances = []
    patchs[runner.Registry] = {"launch": lambda self, label, argv, cwd, flags=(): lances.append(argv)}

    with _app_patchee(tmp_path, patchs) as at:
        bloc = " ".join(str(m.value) for m in at.markdown)
        assert "🐳 Services nécessaires" in bloc, bloc[:400]
        assert "🟢 `controller`" in bloc, "un service en marche doit se voir"
        assert "⚪ `api`" in bloc and "⚪ `worker`" in bloc, "et un service arrêté aussi"

        legendes = " ".join(str(c.value) for c in at.caption)
        assert "2 service(s) à démarrer" in legendes, legendes[:600]
        assert not [b for b in at.button if "Démarrer les" in b.label], "plus de bouton de démarrage"

        next(b for b in at.button if b.label == "▶ Lancer").click().run()

    assert lances, "le clic doit passer par le registre de jobs"
    argv = lances[-1]
    assert argv[1].startswith("experience-lancer"), argv
    demandes = dict(a.split("=", 1) for a in argv if "=" in a)["REQUIS"].split()
    assert demandes == ["controller", "api", "worker"], demandes
    assert not set(demandes) & set(experiences.SERVICES_MONITORING)


def test_R1_tout_en_marche_le_bloc_reste_visible_sans_bouton(tmp_path):
    experiences, patchs = _plateforme_isolee(tmp_path)
    population = experiences.populations()[0]
    patchs[experiences]["jeux"] = lambda: [{"nom": experiences.nom_jeu_attendu(population, "2026-03-16"),
                                           "population": Path(population).name, "jour": "2026-03-16",
                                           "clos": True, "couverts": 98, "attendus": 100}]
    patchs[experiences]["services_actifs"] = lambda *a, **k: {"controller", "api", "worker", "redis"}

    with _app_patchee(tmp_path, patchs) as at:
        bloc = " ".join(str(m.value) for m in at.markdown)
        assert "🐳 Services nécessaires" in bloc, "le bloc doit rester visible quand tout tourne"
        assert "⚪" not in bloc.split("Services nécessaires")[1][:120]
        assert not [b for b in at.button if "Démarrer les" in b.label], \
            "rien ne manque : aucun bouton de démarrage"


def test_R8_la_tuile_services_offre_un_demarrage_quand_il_manque_des_conteneurs(app):
    from scripts.dashboard import metrics

    docker = metrics.docker_status()
    if not docker.available:
        pytest.skip("docker injoignable sur cette machine")
    if docker.services and not docker.missing:
        pytest.skip("pile complète : le bouton n'a pas lieu d'être")

    boutons = [b.label for b in app.button if "make up" in b.label]
    assert boutons, "la tuile Services doit offrir un démarrage quand la pile est incomplète"


def test_R10_R15_la_case_d_arret_final_chaine_la_cible_et_ne_fait_rien_sans_lancement(tmp_path):
    """Décochée par défaut ; cochée, le lancement passe par la cible qui arrête après."""
    from scripts.dashboard import runner

    experiences, patchs, survivante = _plateforme_avec_survivante(tmp_path)
    lances = []
    patchs[runner.Registry] = {
        "launch": lambda self, label, argv, cwd, flags=(): lances.append((label, argv)),
        "stop": lambda self, ident, grace=5.0: True,
    }
    patchs[experiences]["attendre_arret"] = lambda executions, **kwargs: []

    with _app_patchee(tmp_path, patchs) as at:
        case = next(c for c in at.checkbox if "à la fin de l'expérience" in c.label)
        assert case.value is False, "l'arrêt final n'est pas coché d'avance"
        assert "rend la RAM" in case.label
        assert "osmnx1" in (case.help or ""), "l'aide nomme les services arrêtés"

        next(c for c in at.checkbox if "à la fin de l'expérience" in c.label).check().run()
        next(b for b in at.button if b.label == "▶ Lancer").click().run()

    assert lances, "le clic doit lancer quelque chose"
    label, argv = lances[-1]
    assert label.endswith(":experience-lancer-arret"), label
    services = dict(a.split("=", 1) for a in argv if "=" in a)["SERVICES"].split()
    assert "osmnx1" in services and "otp1" in services, services
    assert not set(services) & set(experiences.SERVICES_MONITORING)


def test_R12_R13_la_page_offre_la_reprise_et_avertit_avant_de_relancer(tmp_path):
    """Après un runner tué : « Reprendre » doit être offert, et « Lancer » doit prévenir."""
    import json

    experiences, patchs, survivante = _plateforme_avec_survivante(tmp_path)
    # L'exécution n'écrit plus depuis 20 minutes : runner tué, pas concurrente (R11)
    from datetime import datetime, timedelta, timezone
    vieux = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    (survivante / "progression.json").write_text(
        json.dumps({"faits": 209, "attendus": 2693, "maj": vieux}), encoding="utf-8")
    (survivante / "etat.json").write_text(
        json.dumps({"etat": "en_cours", "decisions_archivees": 209}), encoding="utf-8")

    with _app_patchee(tmp_path, patchs) as at:
        assert not [c for c in at.checkbox if "Arrêter d'abord" in c.label], \
            "une exécution morte ne doit plus être présentée comme concurrente (R11)"

        alertes = [str(w.value) for w in at.warning]
        assert any("exécution reprenable" in a and "209 décisions" in a for a in alertes), alertes

        reprendre = next(b for b in at.button if "Reprendre" in b.label)
        assert not reprendre.disabled, "une exécution abandonnée en cours doit être reprenable (R12)"


def test_R14_un_demon_docker_muet_est_nomme(tmp_path):
    experiences, patchs = _plateforme_isolee(tmp_path)
    patchs[experiences]["services_actifs"] = lambda *a, **k: None  # docker injoignable

    with _app_patchee(tmp_path, patchs) as at:
        legendes = " ".join(str(c.value) for c in at.caption)
        assert "démon Docker ne répond pas" in legendes, legendes
        assert "Docker Desktop" in legendes, "le geste qui répare doit être dit"


# ── « S'inspirer d'une expérience existante » recopie dès le choix (spec inspirer-recopie-immediate) ──

_JOUR = "2026-03-16"
# Tous les champs numériques et booléens du formulaire s'écartent des défauts : une recopie
# PARTIELLE serait sinon invisible (un champ oublié garderait par hasard la bonne valeur).
_REGLAGES_A = {"parallelisme": 16, "temperature": 0.7, "variante": "b_min", "max_candidats": 4, "attente_max_s": 60,
               "graine_ordre": 7, "graine_tirage": 11, "graine_calendrier": 5, "graine_decideur": 9, "memoire": True}
# (pas d'horizon_jours : hors simulateur le champ est grisé et forcé à 1 par le formulaire lui-même)
_REGLAGES_B = {"parallelisme": 24, "temperature": 0.3}


def _plateau(tmp_path, retouches_a=None, avec_b=False):
    """L'expérience A (tous réglages distincts des défauts) — et B à la demande — écrites sur disque, avec les
    patchs pour les voir dans la liste. `retouches_a` corrige la définition de A APRÈS son calcul, par chemin
    pointé (« regroupement.parallelisme »), pour fabriquer une expérience hors bornes ou au nom historique."""
    import sys
    from types import SimpleNamespace

    import yaml

    sys.path.insert(0, str(APP.parents[2]))
    from scripts.dashboard import experiences

    exps = tmp_path / "experiences"
    population = experiences.populations()[0]
    nom_jeu = experiences.nom_jeu_attendu(population, _JOUR)

    def ecrire(reglages, retouches):
        definition = experiences.construire_experience(
            {**experiences.defauts(), "sans_jeu": False, "jeu": nom_jeu, **reglages})
        nom_calcule = definition["nom"]  # celui que le formulaire recalculera, retouches ou pas
        for chemin, valeur in (retouches or {}).items():
            cible = definition
            *parents, feuille = chemin.split(".")
            for cle in parents:
                cible = cible[cle]
            cible[feuille] = valeur
        (exps / definition["nom"]).mkdir(parents=True)
        (exps / definition["nom"] / "experience.yaml").write_text(
            yaml.safe_dump(definition, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return definition["nom"], definition, nom_calcule  # definition["nom"] : le nom sous lequel la liste l'offre

    nom_a, def_a, nom_calcule_a = ecrire(_REGLAGES_A, retouches_a)
    nom_b = ecrire(_REGLAGES_B, None)[0] if avec_b else None
    jeu = [{"nom": nom_jeu, "population": Path(population).name, "jour": _JOUR,
            "clos": True, "couverts": 98, "attendus": 100}]
    patchs = {experiences: {"DOSSIER": exps, "jeux": lambda: jeu,
                            "services_actifs": lambda *a, **k: set()}}
    return SimpleNamespace(experiences=experiences, patchs=patchs, exps=exps, nom_a=nom_a, def_a=def_a,
                           nom_calcule_a=nom_calcule_a, nom_b=nom_b)


def _champ(at, label):
    """Le widget du formulaire qui porte ce libellé — à relire après chaque `run()`, les références vieillissent."""
    return next(w for w in [*at.number_input, *at.selectbox] if w.label == label)


def _parallelisme(at) -> int:
    return int(_champ(at, "Personnes en parallèle").value)


def _brouillon(tmp_path) -> dict:
    """Ce que le formulaire a retenu à la fin du dernier run : ses valeurs, champ par champ (R21)."""
    import yaml

    return yaml.safe_load((tmp_path / "formulaire.yaml").read_text(encoding="utf-8"))


def _ecarts(brut: dict, attendu: dict) -> dict:
    """Les champs du brouillon qui ne valent pas ce qu'on attend (dates et nombres comparés en texte)."""
    def norme(x):
        return x if isinstance(x, dict) else str(x)

    return {k: (brut.get(k), v) for k, v in attendu.items() if norme(brut.get(k)) != norme(v)}


def _nom_affiche(at) -> str:
    return " ".join(str(c.value) for c in at.code)


def test_inspirer_R1_le_choix_recopie_tous_les_champs_sans_autre_clic(tmp_path):
    pl = _plateau(tmp_path)
    with _app_patchee(tmp_path, pl.patchs) as at:
        assert _parallelisme(at) == 8, "le formulaire part des défauts"
        at.selectbox(key="exp-source").select(pl.nom_a).run()
        assert not at.exception, "\n".join(str(e.value) for e in at.exception)
        attendu = pl.experiences._valider_base(pl.experiences.depuis_experience(pl.def_a))
        assert not _ecarts(_brouillon(tmp_path), attendu), _ecarts(_brouillon(tmp_path), attendu)
        assert _parallelisme(at) == 16 and _champ(at, "Prompt système").value == "b_min"
        assert at.session_state["exp_version"] == 1, "les clés des widgets sont remises à neuf"
        assert pl.nom_a in _nom_affiche(at), "le nom calculé en tête est celui de la source"


def test_inspirer_R2_partir_de_zero_remet_les_defauts(tmp_path):
    pl = _plateau(tmp_path)
    with _app_patchee(tmp_path, pl.patchs) as at:
        at.selectbox(key="exp-source").select(pl.nom_a).run()
        assert _parallelisme(at) == 16
        at.selectbox(key="exp-source").select(pl.experiences.SANS_SOURCE).run()
        assert not at.exception, "\n".join(str(e.value) for e in at.exception)
        defauts = pl.experiences.defauts()
        assert not _ecarts(_brouillon(tmp_path), defauts), _ecarts(_brouillon(tmp_path), defauts)
        assert _parallelisme(at) == 8 and at.session_state["exp_version"] == 2


def test_inspirer_R3_la_recopie_ne_recopie_pas_le_nom_mais_la_filiation(tmp_path):
    pl = _plateau(tmp_path, retouches_a={"nom": "un_nom_historique"})  # la liste l'offre sous ce nom
    with _app_patchee(tmp_path, pl.patchs) as at:
        at.selectbox(key="exp-source").select("un_nom_historique").run()
        assert not at.exception, "\n".join(str(e.value) for e in at.exception)
        assert not [w for w in at.text_input if "nom" in w.label.lower() and "expérience" in w.label.lower()], \
            "aucun champ « nom » à saisir : il se calcule (N1)"
        assert pl.nom_calcule_a in _nom_affiche(at) and "un_nom_historique" not in _nom_affiche(at), \
            "le nom affiché est recalculé des paramètres, pas recopié"
        assert _brouillon(tmp_path)["derive_de"] == "un_nom_historique", "la filiation cite la source"


def test_inspirer_R4_l_ouverture_ne_recopie_rien_et_garde_le_brouillon(tmp_path):
    import yaml

    pl = _plateau(tmp_path)
    (tmp_path / "formulaire.yaml").write_text(  # le brouillon du dernier passage (R21), même chemin que _app_patchee
        yaml.safe_dump({**pl.experiences.defauts(), "parallelisme": 12}, allow_unicode=True), encoding="utf-8")
    with _app_patchee(tmp_path, pl.patchs) as at:
        assert at.selectbox(key="exp-source").value == pl.experiences.SANS_SOURCE
        assert _parallelisme(at) == 12, "le brouillon, pas les défauts ni la source"
        assert not [c for c in at.caption if "recopiés" in str(c.value)]


def test_inspirer_R5_recopier_a_nouveau_reapplique_la_source_apres_retouche(tmp_path):
    pl = _plateau(tmp_path)
    with _app_patchee(tmp_path, pl.patchs) as at:
        at.selectbox(key="exp-source").select(pl.nom_a).run()
        _champ(at, "Personnes en parallèle").set_value(4).run()
        assert _parallelisme(at) == 4, "la retouche à la main est prise"
        bouton = next(b for b in at.button if "Recopier à nouveau" in b.label)
        assert not bouton.disabled
        bouton.click().run()
        assert not at.exception, "\n".join(str(e.value) for e in at.exception)
        assert _parallelisme(at) == 16
        at.selectbox(key="exp-source").select(pl.experiences.SANS_SOURCE).run()
        assert next(b for b in at.button if "Recopier à nouveau" in b.label).disabled


def test_inspirer_R6_une_experience_disparue_au_choix_laisse_le_formulaire_intact_et_le_dit(tmp_path):
    import shutil

    pl = _plateau(tmp_path, avec_b=True)
    with _app_patchee(tmp_path, pl.patchs) as at:
        at.selectbox(key="exp-source").select(pl.nom_a).run()
        assert _parallelisme(at) == 16, "un état qui n'est PAS celui des défauts, pour distinguer « intact » de « remis à zéro »"
        shutil.rmtree(pl.exps / pl.nom_b)  # entre l'affichage de la liste et le choix
        at.selectbox(key="exp-source").select(pl.nom_b).run()
        assert not at.exception, "\n".join(str(e.value) for e in at.exception)
        assert any(pl.nom_b in str(w.value) and "n'existe plus" in str(w.value) for w in at.warning), \
            [str(w.value) for w in at.warning]
        assert _parallelisme(at) == 16, "le formulaire garde les réglages de A"
        assert at.selectbox(key="exp-source").value == pl.nom_a, "la liste revient sur ce que le formulaire contient"


def test_inspirer_R7_une_valeur_inconnue_ou_hors_bornes_ne_casse_pas_la_page(tmp_path):
    pl = _plateau(tmp_path, retouches_a={"regroupement.parallelisme": 128, "decideur.modele": "fantome/absent"})
    with _app_patchee(tmp_path, pl.patchs) as at:
        at.selectbox(key="exp-source").select(pl.nom_a).run()
        assert not at.exception, "\n".join(str(e.value) for e in at.exception)
        assert _parallelisme(at) == 64, "hors bornes : ramené dans l'intervalle (R21b)"
        modele = _champ(at, "Modèle (RPD = requêtes/jour restantes)").value
        assert modele != "fantome/absent" and modele in pl.experiences.modeles(), "inconnu : revient au défaut"
        assert abs(float(_champ(at, "Température").value) - 0.7) < 1e-9, "les autres champs sont recopiés"
        assert _champ(at, "Prompt système").value == "b_min"


def test_inspirer_R8_la_page_dit_ce_qu_elle_a_recopie_tant_que_c_est_vrai(tmp_path):
    pl = _plateau(tmp_path)
    with _app_patchee(tmp_path, pl.patchs) as at:
        at.selectbox(key="exp-source").select(pl.nom_a).run()
        legendes = [str(c.value) for c in at.caption]
        assert any(pl.nom_a in l and "recopiés" in l and "recalcule" in l for l in legendes), legendes
        at.run()  # une relance sans retouche : le formulaire est toujours celui de A, la légende reste
        assert [c for c in at.caption if "recopiés" in str(c.value)], "toujours vraie, toujours affichée"
        _champ(at, "Personnes en parallèle").set_value(3).run()  # une retouche : la légende mentirait
        assert not [c for c in at.caption if "recopiés" in str(c.value)], "effacée à la première retouche"


def test_inspirer_R9_la_recopie_n_ecrit_que_le_brouillon_et_des_valeurs_valides(tmp_path):
    import hashlib

    pl = _plateau(tmp_path)

    def empreinte(dossier):
        return {str(p.relative_to(dossier)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in dossier.rglob("*") if p.is_file()}

    avant = empreinte(pl.exps)
    with _app_patchee(tmp_path, pl.patchs) as at:
        at.selectbox(key="exp-source").select(pl.nom_a).run()
        assert empreinte(pl.exps) == avant, "data/experiences/ est inchangé à l'octet"
        brut = _brouillon(tmp_path)
        assert brut["parallelisme"] == 16 and brut["derive_de"] == pl.nom_a
        assert not _ecarts(brut, pl.experiences._valider_base(brut)), \
            "le brouillon ne contient que des valeurs acceptées par R21b"


def test_inspirer_R10_une_source_supprimee_apres_coup_est_dite_et_la_liste_revient(tmp_path):
    import shutil

    pl = _plateau(tmp_path)
    with _app_patchee(tmp_path, pl.patchs) as at:
        at.selectbox(key="exp-source").select(pl.nom_a).run()
        shutil.rmtree(pl.exps / pl.nom_a)  # A choisie, puis supprimée du disque
        at.run()  # n'importe quelle interaction suivante
        assert not at.exception, "\n".join(str(e.value) for e in at.exception)
        assert any(pl.nom_a in str(w.value) and "n'existe plus" in str(w.value) for w in at.warning), \
            [str(w.value) for w in at.warning]
        assert _parallelisme(at) == 16, "le formulaire garde ses réglages"
        assert at.selectbox(key="exp-source").value == pl.experiences.SANS_SOURCE
        assert next(b for b in at.button if "Recopier à nouveau" in b.label).disabled
        at.run()  # relance sans retouche : l'avertissement reste, le formulaire est toujours celui de A
        assert [w for w in at.warning if "n'existe plus" in str(w.value)]
        _champ(at, "Personnes en parallèle").set_value(3).run()  # une retouche : il n'a plus lieu d'être
        assert not [w for w in at.warning if "n'existe plus" in str(w.value)], "effacé à la première retouche"


def test_inspirer_R11_recopier_a_nouveau_sur_une_source_disparue_ne_remet_rien_aux_defauts(tmp_path):
    import shutil

    pl = _plateau(tmp_path)
    with _app_patchee(tmp_path, pl.patchs) as at:
        at.selectbox(key="exp-source").select(pl.nom_a).run()
        bouton = next(b for b in at.button if "Recopier à nouveau" in b.label)  # actif : A existe encore
        shutil.rmtree(pl.exps / pl.nom_a)
        bouton.click().run()  # le clic part avant la disparition, arrive après
        assert not at.exception, "\n".join(str(e.value) for e in at.exception)
        assert _parallelisme(at) == 16, "surtout pas les défauts (8) : la source a disparu, le formulaire reste"
        assert any("n'existe plus" in str(w.value) for w in at.warning), [str(w.value) for w in at.warning]

