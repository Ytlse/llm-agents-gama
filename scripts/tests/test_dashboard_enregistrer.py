"""Enregistrer une expérience sans la lancer (spec `enregistrer-experience-non-lancee.md`).

Le fil de ces tests : écrire son plan aujourd'hui et lancer demain. L'écriture est locale et ne
doit dépendre ni du conteneur `controller`, ni de l'existence du jeu de déplacements — le schéma
de la plateforme accepte une expérience qui nomme un jeu pas encore construit, et le warm-up dure
une heure.
"""

import functools
import json
import sys
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.dashboard import experiences  # noqa: E402

VRAI_LISTER = experiences.lister


def _ecrire(chemin: Path, contenu) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    texte = json.dumps(contenu) if chemin.suffix == ".json" else yaml.safe_dump(contenu, allow_unicode=True)
    chemin.write_text(texte, encoding="utf-8")


@pytest.fixture
def plateforme(tmp_path, monkeypatch):
    """Un dépôt de poche : deux populations, un jeu clos pour l'une, rien pour l'autre."""
    exps, jeux, pops = tmp_path / "experiences", tmp_path / "jeux", tmp_path / "population"
    for nom in ("pop_avec_jeu", "pop_sans_jeu"):
        _ecrire(pops / nom / "MANIFEST.yaml", {"nom": nom, "n": 10})
    _ecrire(jeux / "pop_avec_jeu_20260316" / "MANIFEST.yaml",
            {"nom": "pop_avec_jeu_20260316", "clos": True, "population": {"nom": "pop_avec_jeu"},
             "jour_simule": "2026-03-16", "attendus": {"deplacements": 100}, "couverts": {"deplacements": 98}})
    monkeypatch.setattr(experiences, "DOSSIER", exps)
    monkeypatch.setattr(experiences, "DOSSIER_JEUX", jeux)
    monkeypatch.setattr(experiences, "DOSSIER_POP", pops)
    monkeypatch.setattr(experiences, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(experiences, "lister", functools.partial(VRAI_LISTER, dossier=exps))
    return tmp_path


def _valeurs(**surcharges) -> dict:
    """Les valeurs du formulaire, telles que `_formulaire` les rend (sans nom : il se calcule)."""
    base = {
        "population": "data/population/pop_sans_jeu", "jeu": "", "sans_jeu": True,
        "variante": "b_min", "decideur_type": "passerelle", "modele": "m1", "temperature": 0.0,
        "graine_decideur": 42, "rejeu_de": "", "mode": "sans_simulateur", "politique": "commune",
        "date": "2026-03-16", "graine_calendrier": 42, "horizon_jours": 1, "memoire": False,
        "graine_ordre": 42, "graine_tirage": 42, "parallelisme": 8, "max_candidats": 6,
        "attente_max_s": 120, "tolerances": dict(experiences.TOLERANCES_PROPOSEES), "derive_de": None,
    }
    base.update(surcharges)
    return base


# Le nom se calcule des paramètres (N1) : les tests le lisent au lieu de le poser. Deux
# expériences se distinguent donc par un PARAMÈTRE — ici le modèle — jamais par un libellé.
NOM_DEFAUT = "exp_m1_bmin_pop-pop_sans_jeu_t0_nosim"


def _nom(**surcharges) -> str:
    return experiences.construire_experience(_valeurs(**surcharges))["nom"]


def test_R1_enregistrer_ne_demande_ni_jeu_ni_conteneur(plateforme):
    exp = experiences.construire_experience(_valeurs())
    motifs = experiences.motifs_indisponibilite(exp, jeu_clos=False, controleur_ok=False, registre=False)
    assert motifs["enregistrer"] == [], "un nom recevable suffit pour enregistrer"
    assert motifs["lancer"], "lancer, lui, reste bloqué"

    chemin, change = experiences.enregistrer(exp)
    assert change is True and chemin.is_file()
    assert yaml.safe_load(chemin.read_text(encoding="utf-8"))["nom"] == NOM_DEFAUT
    assert not (chemin.parent / "executions").exists(), "aucune exécution ne doit être créée"


def test_R2_l_experience_nomme_le_jeu_qu_elle_attend(plateforme):
    exp = experiences.construire_experience(_valeurs())
    attendu = experiences.nom_jeu_attendu("data/population/pop_sans_jeu", "2026-03-16")
    assert exp["jeu"]["nom"] == attendu == "pop_sans_jeu_20260316"

    # Quand un jeu existe, c'est lui qui est nommé, pas un nom calculé
    avec = experiences.construire_experience(
        _valeurs(population="data/population/pop_avec_jeu", jeu="pop_avec_jeu_20260316", sans_jeu=False))
    assert avec["jeu"]["nom"] == "pop_avec_jeu_20260316"


def test_R3_la_validation_est_une_etape_distincte(plateforme):
    exp = experiences.construire_experience(_valeurs())

    arrete = experiences._enregistrer_et_dire(
        exp, inline=None, sans_validation="le service `controller` ne tourne pas")
    assert "validation non tentée" in arrete
    assert "`controller` ne tourne pas" in arrete
    assert "raté" not in arrete and "erreur" not in arrete.lower()

    appels = []
    def faux_inline(cible, variables, **kwargs):
        appels.append((cible, variables, kwargs))
        return f"expérience {NOM_DEFAUT!r} validée et rangée"

    actif = experiences._enregistrer_et_dire(exp, inline=faux_inline, sans_validation=None)
    assert appels and appels[0][0] == "experience-definir"
    assert "validée et rangée" in actif


def test_R4_le_message_dit_le_chemin_et_l_etat_du_jeu(plateforme):
    message = experiences._enregistrer_et_dire(
        experiences.construire_experience(_valeurs()), inline=None, sans_validation="pas de conteneur")
    assert f"experiences/{NOM_DEFAUT}/experience.yaml" in message
    assert "jeu attendu « pop_sans_jeu_20260316 » : absent" in message

    pret = experiences._enregistrer_et_dire(
        experiences.construire_experience(
            _valeurs(population="data/population/pop_avec_jeu",
                     jeu="pop_avec_jeu_20260316", sans_jeu=False)),
        inline=None, sans_validation="pas de conteneur")
    assert "clos et prêt" in pret


def test_R5_seul_un_nom_impossible_empeche_d_enregistrer(plateforme):
    """Le nom n'étant plus saisi (N1), le seul cas restant est un nommage qui REFUSE."""
    sans_modele = experiences.construire_experience(_valeurs(modele=""))
    assert sans_modele["nom"] == ""
    motifs = experiences.motifs_indisponibilite(sans_modele, jeu_clos=False, controleur_ok=False,
                                                registre=False)
    assert any("decideur.modele" in m for m in motifs["enregistrer"]), motifs["enregistrer"]

    exp = experiences.construire_experience(_valeurs())
    assert exp["nom"] == NOM_DEFAUT
    assert experiences.MOTIF_NOM.match(exp["nom"])
    assert experiences.motifs_indisponibilite(exp, jeu_clos=False, controleur_ok=False,
                                              registre=False)["enregistrer"] == []


def test_R6_un_nom_deja_execute_demande_confirmation(plateforme):
    exp = experiences.construire_experience(_valeurs())
    experiences.enregistrer(exp)
    dossier = experiences.DOSSIER / exp["nom"] / "executions"
    for horodatage in ("2026-09-01_10_00_00", "2026-09-02_11_00_00"):
        _ecrire(dossier / horodatage / "execution.yaml", {"experience": {"nom": exp["nom"]}})
        _ecrire(dossier / horodatage / "etat.json", {"etat": "terminee"})
    assert experiences.executions_connues(exp["nom"]) == 2

    empreintes = {p: p.read_bytes() for p in dossier.rglob("*") if p.is_file()}

    non_confirme = experiences.motifs_indisponibilite(
        exp, jeu_clos=False, controleur_ok=False, registre=False,
        ecrasement=f"« {exp['nom']} » porte déjà 2 exécution(s) : cochez la confirmation ci-dessus")
    assert any("2 exécution(s)" in m for m in non_confirme["enregistrer"])

    confirme = experiences.motifs_indisponibilite(exp, jeu_clos=False, controleur_ok=False, registre=False)
    assert confirme["enregistrer"] == []

    experiences.enregistrer({**exp, "max_candidats": 9})
    assert {p: p.read_bytes() for p in dossier.rglob("*") if p.is_file()} == empreintes, \
        "les exécutions archivées gardent leur copie figée de la définition"


def test_R6bis_estimer_et_lancer_passent_aussi_par_la_confirmation(plateforme):
    """Le garde-fou d'écrasement (R6) doit couvrir Estimer et Lancer, pas seulement Enregistrer.

    Ces deux boutons écrivent la définition (enregistrer() en amont) : tant qu'ils l'ignoraient,
    lancer un run avec un décideur modifié rebasculait la définition en silence.
    """
    exp = experiences.construire_experience(
        _valeurs(population="data/population/pop_avec_jeu",
                 jeu="pop_avec_jeu_20260316", sans_jeu=False))
    experiences.enregistrer(exp)
    dossier = experiences.DOSSIER / exp["nom"] / "executions"
    _ecrire(dossier / "2026-09-01_10_00_00" / "execution.yaml", {"experience": {"nom": exp["nom"]}})
    _ecrire(dossier / "2026-09-01_10_00_00" / "etat.json", {"etat": "terminee"})
    assert experiences.executions_connues(exp["nom"]) == 1

    motif = f"« {exp['nom']} » porte déjà 1 exécution(s) : cochez la confirmation ci-dessus"
    bloques = experiences.motifs_indisponibilite(
        exp, jeu_clos=True, controleur_ok=True, registre=True, ecrasement=motif)
    assert any("exécution(s)" in m for m in bloques["lancer"]), bloques["lancer"]
    assert any("exécution(s)" in m for m in bloques["estimer"]), bloques["estimer"]

    # Confirmé (ecrasement=None) : plus rien ne bloque du côté écrasement.
    ok = experiences.motifs_indisponibilite(exp, jeu_clos=True, controleur_ok=True, registre=True)
    assert ok["lancer"] == [] and ok["estimer"] == []


def test_R6ter_le_decideur_affiche_est_celui_fige_par_execution(plateforme):
    """Deux exécutions d'une même expérience peuvent porter des décideurs différents : le tableau
    montre celui figé dans le snapshot de chaque exécution, jamais celui (mutable) de la définition."""
    definition = experiences.construire_experience(_valeurs(modele="mistral-small-latest"))
    experiences.enregistrer(definition)
    nom = definition["nom"]
    dossier = experiences.DOSSIER / nom / "executions"
    fige = {"2026-09-01_10_00_00": "gemini-3.5-flash-lite", "2026-09-02_11_00_00": "mistral-small-latest"}
    for horodatage, modele in fige.items():
        _ecrire(dossier / horodatage / "execution.yaml",
                {"experience": {"nom": nom,
                                "decideur": {"type": "passerelle", "modele": modele}}})
        _ecrire(dossier / horodatage / "etat.json", {"etat": "terminee"})

    par_exec = {l["execution"]: l["decideur"] for l in experiences.lister()
                if l["experience"] == nom}
    assert par_exec["2026-09-01_10_00_00"] == "gemini-3.5-flash-lite"
    assert par_exec["2026-09-02_11_00_00"] == "mistral-small-latest"


def test_R7_le_jeu_attendu_suit_le_jour_choisi(plateforme):
    veille = experiences.construire_experience(_valeurs(date="2026-03-16"))
    lendemain = experiences.construire_experience(_valeurs(date="2026-03-17"))
    assert veille["jeu"]["nom"] == "pop_sans_jeu_20260316"
    assert lendemain["jeu"]["nom"] == "pop_sans_jeu_20260317"

    chemin, _ = experiences.enregistrer(lendemain)
    assert yaml.safe_load(chemin.read_text(encoding="utf-8"))["jeu"]["nom"] == "pop_sans_jeu_20260317"


def test_R8_enregistrer_deux_fois_sans_changement_ne_fait_rien(plateforme):
    exp = experiences.construire_experience(_valeurs())
    chemin, premier = experiences.enregistrer(exp)
    empreinte = chemin.stat().st_mtime_ns

    chemin2, second = experiences.enregistrer(exp)
    assert (premier, second) == (True, False)
    assert chemin2 == chemin and chemin.stat().st_mtime_ns == empreinte

    message = experiences._enregistrer_et_dire(exp, inline=None, sans_validation="pas de conteneur")
    assert "inchangé" in message and "le fichier disait déjà cela" in message
    assert not (chemin.parent / "executions").exists()


def test_R9_le_registre_dit_si_le_jeu_est_pret(plateforme):
    a_construire = experiences.construire_experience(_valeurs())
    deja_pret = experiences.construire_experience(
        _valeurs(population="data/population/pop_avec_jeu", jeu="pop_avec_jeu_20260316",
                 sans_jeu=False))
    for exp in (a_construire, deja_pret):
        experiences.enregistrer(exp)

    par_nom = {l["experience"]: l for l in experiences.lister()}
    assert par_nom[a_construire["nom"]]["jeu_etat"] == "absent"
    assert par_nom[deja_pret["nom"]]["jeu_etat"] == "clos et prêt"
    assert a_construire["nom"] != deja_pret["nom"], "deux populations, deux noms (N7)"


def test_R10_la_validation_n_est_pas_tentee_sur_un_etat_inconnu(plateforme):
    """L'inconnu n'est pas un « oui » : sinon un démon Docker qui pend ferait attendre la page."""
    appels = []
    faux_inline = lambda *a, **k: appels.append(a) or "ne devrait pas être appelé"  # noqa: E731

    assert experiences.motif_sans_validation(None, faux_inline) == \
        "l'état des services Docker est inconnu (docker injoignable)"
    assert experiences.motif_sans_validation({"api", "worker"}, faux_inline) == \
        "le service `controller` ne tourne pas"
    assert experiences.motif_sans_validation({"controller"}, None) is not None
    assert experiences.motif_sans_validation({"controller", "api"}, faux_inline) is None

    exp = experiences.construire_experience(_valeurs())
    for services in (None, {"api"}):
        message = experiences._enregistrer_et_dire(
            exp, inline=faux_inline, sans_validation=experiences.motif_sans_validation(services, faux_inline))
        assert "validation non tentée" in message
    assert appels == [], "aucune commande ne doit être lancée quand la validation n'est pas tentée"


def test_R11_la_sortie_de_validation_est_etiquetee_et_bornee(plateforme):
    """Un échec de validation ne doit pas pouvoir se lire comme un échec d'enregistrement."""
    vus = []

    def faux_inline(cible, variables, **kwargs):
        vus.append(kwargs)
        return "expérience refusée : decideur.modele est obligatoire"

    message = experiences._enregistrer_et_dire(
        experiences.construire_experience(_valeurs()), inline=faux_inline, sans_validation=None)

    assert "écrit :" in message, "l'enregistrement est annoncé d'abord"
    lignes = message.splitlines()
    etiquette = next(i for i, l in enumerate(lignes) if l.startswith("validation par la plateforme"))
    assert "refusée" in "\n".join(lignes[etiquette:]), "l'échec est sous l'étiquette de la validation"
    assert vus and vus[0]["timeout"] == experiences.DELAI_VALIDATION_S == 20


def test_le_prompt_affiche_ne_l_est_que_pour_un_decideur_qui_en_lit_un(plateforme):
    """Le tableau ne présente une variante de prompt que si l'exécution en lira une (N5).

    `experiences/cli.py` ne transmet `parameters.prompt_variant` que sous
    `decideur.type == "passerelle"` : pour les quatre autres décideurs, `gabarit.variante`
    est un résidu du formulaire. Le 2026-09-08, `exp_lgbm_jtir_nosim` (LightGBM) annonçait
    « minimal_persona » alors que son archive ne porte pas un seul échange LLM.
    """
    attendu = {}
    for surcharges, prompt in (
        ({"decideur_type": "passerelle", "modele": "m1"}, "b_min"),
        ({"decideur_type": "modele"}, "—"),
        ({"decideur_type": "aleatoire"}, "—"),
        ({"decideur_type": "duree_minimale"}, "—"),
        ({"decideur_type": "rejeu", "rejeu_de": "/app/data/experiences/x/executions/y"}, "—"),
    ):
        exp = experiences.construire_experience(_valeurs(variante="b_min", **surcharges))
        experiences.enregistrer(exp)
        assert exp["gabarit"]["variante"] == "b_min", "la définition garde le champ tel quel"
        attendu[exp["nom"]] = prompt

    par_nom = {l["experience"]: l["prompt"] for l in experiences.lister()}
    assert {n: par_nom[n] for n in attendu} == attendu


def test_le_prompt_affiche_suit_le_decideur_fige_de_chaque_execution(plateforme):
    """Comme le décideur, le prompt affiché est celui du snapshot de l'exécution, pas de la
    définition courante : une expérience redéfinie de la passerelle vers le modèle statistique
    garde un prompt sur ses anciennes exécutions et « — » sur les nouvelles."""
    definition = experiences.construire_experience(_valeurs(variante="b_min"))
    experiences.enregistrer(definition)
    nom = definition["nom"]
    dossier = experiences.DOSSIER / nom / "executions"
    fige = {
        "2026-09-01_10_00_00": {"gabarit": {"variante": "expert_chaine"},
                                "decideur": {"type": "passerelle", "modele": "m1"}},
        "2026-09-02_11_00_00": {"gabarit": {"variante": "expert_chaine"},
                                "decideur": {"type": "modele"}},
        # Snapshot partiel (sans décideur) : la définition fait foi, faute de mieux.
        "2026-09-03_12_00_00": {},
    }
    for horodatage, instantane in fige.items():
        _ecrire(dossier / horodatage / "execution.yaml",
                {"experience": {"nom": nom, **instantane}})
        _ecrire(dossier / horodatage / "etat.json", {"etat": "terminee"})

    par_exec = {l["execution"]: l["prompt"] for l in experiences.lister()
                if l["experience"] == nom}
    assert par_exec["2026-09-01_10_00_00"] == "expert_chaine"
    assert par_exec["2026-09-02_11_00_00"] == "—"
    assert par_exec["2026-09-03_12_00_00"] == "b_min"


def test_sans_variante_designee_la_passerelle_dit_le_prompt_actif(plateforme):
    """Variante vide = le prompt ACTIF de la passerelle, « celui du jour » : le tableau le dit
    au lieu de laisser la colonne vide."""
    assert experiences._prompt_affiche(None, {"type": "passerelle", "modele": "m1"}) == "actif"
    assert experiences._prompt_affiche("", {"type": "passerelle"}) == "actif"
    assert experiences._prompt_affiche(None, {"type": "modele"}) == "—"
    assert experiences._prompt_affiche(None, None) == "—", "décideur inconnu : rien à promettre"


def test_terminee_ne_se_confond_pas_avec_les_autres_etats_finaux():
    """La case « Terminées seulement » ne garde que `terminee`. `epuisee`, `arretee` et
    `interrompue` sont finales — plus rien n'écrit — mais leur couverture est partielle :
    les garder ferait passer un résultat incomplet pour un résultat (E14)."""
    assert experiences.est_terminee({"etat": "terminee"})
    for etat in ("definie", "en_cours", "en_pause", "en_attente_quota",
                 "epuisee", "arretee", "interrompue", "archive manquante", "?"):
        assert not experiences.est_terminee({"etat": etat}), etat
    assert not experiences.est_terminee({}) and not experiences.est_terminee(None)
