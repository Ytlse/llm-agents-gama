"""Arrêter ce qui tourne avant de lancer (spec `arreter-avant-de-lancer.md`).

Le fil de ces tests : un lancement ne doit pas partir en concurrence d'un survivant. Une
exécution peut survivre à ce qui l'a lancée, son `docker compose exec` tué sur l'hôte ne tuant
pas le processus dans le conteneur. L'arrêt reste coopératif — un fichier `STOP`, honoré en
quelques secondes — parce qu'un signal laisserait l'état à « en cours » pour toujours.
"""

import functools
import json
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.dashboard import experiences  # noqa: E402
from scripts.tests.test_dashboard_activites import FauxSt  # noqa: E402

VRAI_LISTER = experiences.lister


@dataclass
class FauxJob:
    """Le strict nécessaire de `runner.Job` pour ces tests."""

    id: str
    label: str
    running: bool = True


def _ecrire(chemin: Path, contenu) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    texte = json.dumps(contenu) if chemin.suffix == ".json" else yaml.safe_dump(contenu, allow_unicode=True)
    chemin.write_text(texte, encoding="utf-8")


def _execution(dossier: Path, experience: str, nom: str, etat: str) -> Path:
    _ecrire(dossier / experience / "experience.yaml",
            {"nom": experience, "jeu": {"nom": "j"}, "decideur": {"type": "passerelle", "modele": "m"}})
    d = dossier / experience / "executions" / nom
    _ecrire(d / "etat.json", {"etat": etat})
    _ecrire(d / "execution.yaml", {"cree_le": "2026-09-07T10:00:00+00:00"})
    return d


@pytest.fixture
def plateforme(tmp_path, monkeypatch):
    """Une exécution qui tourne, une terminée, une en pause, et un jeu en construction."""
    exps, jeux = tmp_path / "experiences", tmp_path / "jeux"
    _execution(exps, "autre_experience", "2026-09-07_10_00_00", "en_cours")
    _execution(exps, "finie", "2026-09-06_09_00_00", "terminee")
    _execution(exps, "suspendue", "2026-09-06_12_00_00", "en_pause")
    _ecrire(jeux / "jeu_en_construction" / "MANIFEST.yaml",
            {"nom": "jeu_en_construction", "clos": False, "population": {"nom": "pop"}, "jour_simule": "2026-03-16"})
    monkeypatch.setattr(experiences, "DOSSIER", exps)
    monkeypatch.setattr(experiences, "DOSSIER_JEUX", jeux)
    monkeypatch.setattr(experiences, "lister", functools.partial(VRAI_LISTER, dossier=exps))
    return tmp_path


def test_R1_les_concurrents_sont_les_executions_en_cours_et_les_jobs_de_lancement(plateforme):
    jobs = [FauxJob("1", "root:experience-lancer"), FauxJob("2", "root:run-offline"),
            FauxJob("3", "root:up"), FauxJob("4", "root:experience-lancer", running=False)]
    conc = experiences.concurrents(lambda: jobs)

    assert [e["experience"] for e in conc["executions"]] == ["autre_experience"], \
        "une exécution en cours d'une AUTRE expérience compte aussi"
    labels = [j.label for j in conc["jobs"]]
    assert labels == ["root:experience-lancer", "root:run-offline"], labels
    assert "root:up" not in labels, "un job d'une autre nature n'est pas un concurrent"


def test_R2_la_construction_d_un_jeu_n_est_jamais_concurrente(plateforme):
    conc = experiences.concurrents(lambda: [FauxJob("1", "root:jeu")])
    assert conc["jobs"] == [], "construire un jeu ne consomme pas de quota et son produit est attendu"
    assert experiences.jeux_en_preparation(), "le jeu en construction existe bien"

    arretes = experiences.arreter_concurrents(conc)
    assert all("jeu" not in a or "exécution" in a for a in arretes)
    assert not (experiences.DOSSIER_JEUX / "jeu_en_construction" / "STOP").exists()


def test_R3_la_case_annonce_ce_qu_elle_arretera(plateforme):
    conc = experiences.concurrents(lambda: [FauxJob("1", "root:run")])
    libelle = experiences.libelle_concurrents(conc)
    assert "autre_experience / 2026-09-07_10_00_00" in libelle
    assert "`root:run`" in libelle


def test_R4_l_arret_d_une_execution_est_cooperatif(plateforme):
    conc = experiences.concurrents()
    arretes = experiences.arreter_concurrents(conc)

    dossier = Path(conc["executions"][0]["dossier"])
    assert (dossier / "STOP").is_file(), "l'arrêt passe par un fichier STOP, jamais un signal"
    assert not (dossier / "PAUSE").exists()
    assert any("effectif en quelques secondes" in a for a in arretes), arretes

    source = Path(experiences.__file__).read_text(encoding="utf-8")
    assert "pkill" not in source, "aucun processus n'est tué dans le conteneur (non-goal)"
    assert "SIGKILL" not in source


def test_R4_la_demande_est_visible_avant_d_etre_effective(plateforme):
    """Le fichier déposé EST le retour immédiat : la barre dit « pause demandée » sans attendre
    que le runner ait réécrit son état. Sans ça, un clic sur Pause n'affichait rien pendant
    tout le délai de grâce, et le message promettait « le prochain point sûr » — jusqu'à 2 min.
    """
    dossier = Path(experiences.concurrents()["executions"][0]["dossier"])
    avant = experiences.activites_en_cours()["executions"]
    assert [e["pause_demandee"] for e in avant] == [None]

    experiences.signaler(dossier, "PAUSE")
    apres = experiences.activites_en_cours()["executions"]
    assert isinstance(apres[0]["pause_demandee"], float) and apres[0]["pause_demandee"] < 5
    assert apres[0]["arret_demande"] is None, "une pause n'est pas un arrêt"


def test_R5_les_jobs_passent_par_le_registre(plateforme):
    demandes = []
    conc = experiences.concurrents(lambda: [FauxJob("job-7", "root:experience-lancer")])
    arretes = experiences.arreter_concurrents(conc, lambda ident: demandes.append(ident) or True)

    assert demandes == ["job-7"], "le registre doit être appelé avec l'identifiant du job"
    assert any("root:experience-lancer" in a for a in arretes)


def test_R5_un_registre_qui_refuse_n_est_pas_annonce_comme_arrete(plateforme):
    conc = experiences.concurrents(lambda: [FauxJob("job-8", "root:run")])
    arretes = experiences.arreter_concurrents(conc, lambda _ident: False)
    assert not any("root:run" in a for a in arretes), "un arrêt qui échoue ne doit pas être annoncé"


def test_R6_l_attente_est_bornee_et_nomme_ce_qui_reste(plateforme):
    executions = experiences.concurrents()["executions"]

    debut = time.time()
    restantes = experiences.attendre_arret(executions, delai_s=1, pas_s=0.05)
    assert restantes == ["autre_experience / 2026-09-07_10_00_00"]
    assert time.time() - debut < 3, "l'attente doit être bornée"


def test_R6_une_execution_qui_s_arrete_pendant_l_attente_laisse_partir_le_lancement(plateforme):
    executions = experiences.concurrents()["executions"]
    etat = Path(executions[0]["dossier"]) / "etat.json"

    def arreter_bientot():
        time.sleep(0.2)
        etat.write_text(json.dumps({"etat": "arretee"}), encoding="utf-8")

    fil = threading.Thread(target=arreter_bientot)
    fil.start()
    try:
        assert experiences.attendre_arret(executions, delai_s=5, pas_s=0.05) == []
    finally:
        fil.join()


def test_R9_ni_les_terminees_ni_les_suspendues_ne_sont_touchees(plateforme):
    conc = experiences.concurrents()
    assert [e["experience"] for e in conc["executions"]] == ["autre_experience"]

    experiences.arreter_concurrents(conc)
    for experience, nom in (("finie", "2026-09-06_09_00_00"), ("suspendue", "2026-09-06_12_00_00")):
        dossier = experiences.DOSSIER / experience / "executions" / nom
        assert not (dossier / "STOP").exists(), f"{experience} ne devait pas être touchée"


def test_R8_sans_rien_en_cours_il_n_y_a_aucun_concurrent(tmp_path, monkeypatch):
    vide = tmp_path / "experiences"
    vide.mkdir()
    monkeypatch.setattr(experiences, "DOSSIER", vide)
    monkeypatch.setattr(experiences, "lister", functools.partial(VRAI_LISTER, dossier=vide))

    conc = experiences.concurrents(lambda: [FauxJob("1", "root:up")])
    assert conc == {"executions": [], "jobs": []}
    assert experiences.libelle_concurrents(conc) == ""
    assert experiences.arreter_concurrents(conc) == []


def _vieillir(dossier: Path, minutes: float) -> None:
    """Écrit une progression datée, pour simuler une exécution que plus rien n'alimente."""
    from datetime import datetime, timedelta, timezone

    quand = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    _ecrire(dossier / "progression.json", {"faits": 209, "attendus": 2693, "maj": quand.isoformat()})


def test_R11_une_execution_morte_n_est_pas_concurrente(plateforme):
    """Le défaut du 2026-09-07 : un STOP écrit dans une exécution morte l'a rendue non reprenable."""
    dossier = experiences.DOSSIER / "autre_experience" / "executions" / "2026-09-07_10_00_00"

    _vieillir(dossier, 20)
    assert experiences.execution_vivante(dossier) is False
    assert experiences.concurrents()["executions"] == [], "une exécution morte n'entre en concurrence avec rien"
    experiences.arreter_concurrents(experiences.concurrents())
    assert not (dossier / "STOP").exists(), "aucun STOP ne doit être écrit dans une exécution morte"

    _vieillir(dossier, 0.1)
    assert experiences.execution_vivante(dossier) is True
    assert len(experiences.concurrents()["executions"]) == 1, "celle qui écrit encore est concurrente"


def test_R11_une_execution_qui_vient_de_naitre_est_vivante(plateforme):
    """Pas encore de progression : c'est `etat.json` qui date la naissance."""
    dossier = experiences.DOSSIER / "autre_experience" / "executions" / "2026-09-07_10_00_00"
    assert not (dossier / "progression.json").exists()
    assert experiences.execution_vivante(dossier) is True

    import os
    vieux = time.time() - 3600
    os.utime(dossier / "etat.json", (vieux, vieux))
    assert experiences.execution_vivante(dossier) is False


def test_R12_les_trois_cas_reprenables(plateforme):
    dossier = experiences.DOSSIER / "autre_experience" / "executions" / "2026-09-07_10_00_00"
    _vieillir(dossier, 20)
    par_nom = {l["experience"]: l for l in experiences.lister() if l.get("execution")}

    assert experiences.est_reprenable(par_nom["autre_experience"]) is True, "en cours, abandonnée"
    assert experiences.est_reprenable(par_nom["suspendue"]) is True, "en pause"
    assert experiences.est_reprenable(par_nom["finie"]) is False, "terminée"

    _vieillir(dossier, 0.1)
    vivante = {l["experience"]: l for l in experiences.lister() if l.get("execution")}
    assert experiences.est_reprenable(vivante["autre_experience"]) is False, \
        "une exécution qui tourne vraiment n'est pas à reprendre, c'est une concurrente"

    for etat in ("epuisee", "arretee"):
        _ecrire(dossier / "etat.json", {"etat": etat})
        ligne = next(l for l in experiences.lister() if l["experience"] == "autre_experience")
        assert experiences.est_reprenable(ligne) is (etat == "epuisee"), etat


def test_R13_le_nombre_de_decisions_deja_archivees_est_lu(plateforme):
    dossier = experiences.DOSSIER / "autre_experience" / "executions" / "2026-09-07_10_00_00"
    _ecrire(dossier / "etat.json", {"etat": "en_pause", "decisions_archivees": 209})
    assert experiences.decisions_archivees(dossier) == 209

    # À défaut du compteur, les lignes du journal des décisions font foi
    _ecrire(dossier / "etat.json", {"etat": "en_pause"})
    (dossier / "decisions.jsonl").write_text('{"a": 1}\n{"a": 2}\n{"a": 3}\n', encoding="utf-8")
    assert experiences.decisions_archivees(dossier) == 3
    assert experiences.decisions_archivees(experiences.DOSSIER / "inexistant") == 0


def test_R15_une_archive_cloturee_n_est_jamais_reprenable(plateforme):
    """La clôture vit dans `execution.yaml`, pas dans `etat.json` : une archive clôturée est
    immuable (E19) et la reprise y échoue toujours. La proposer serait une boucle — c'est le
    piège rencontré le 2026-09-07, où `etat.json` remis à « en pause » ne changeait rien."""
    dossier = experiences.DOSSIER / "autre_experience" / "executions" / "2026-09-07_10_00_00"
    _vieillir(dossier, 20)

    ligne = next(l for l in experiences.lister() if l["experience"] == "autre_experience")
    assert experiences.archive_close(dossier) is False
    assert experiences.est_reprenable(ligne) is True

    _ecrire(dossier / "execution.yaml", {
        "cree_le": "2026-09-07T10:00:00+00:00",
        "cloture": {"le": "2026-09-07T12:54:46+00:00", "etat": "arretee",
                    "sha256": {"decisions.jsonl": "2b7b4c"}},
    })
    ligne = next(l for l in experiences.lister() if l["experience"] == "autre_experience")
    assert experiences.archive_close(dossier) is True
    assert experiences.est_reprenable(ligne) is False, "une archive clôturée n'est pas reprenable"

    for etat in ("en_pause", "epuisee"):
        _ecrire(dossier / "etat.json", {"etat": etat})
        ligne = next(l for l in experiences.lister() if l["experience"] == "autre_experience")
        assert experiences.est_reprenable(ligne) is False, \
            f"{etat} sur une archive clôturée reste non reprenable"


def test_supprimer_efface_le_dossier_d_une_experience_inactive(plateforme):
    """« finie » n'a aucune exécution vivante : supprimer efface tout son dossier."""
    dossier = experiences.DOSSIER / "finie"
    assert dossier.is_dir()
    rendu = experiences.supprimer_experience("finie")
    assert rendu == dossier
    assert not dossier.exists(), "la définition et les exécutions archivées sont effacées"
    assert not any(l["experience"] == "finie" for l in experiences.lister())


def test_supprimer_refuse_une_experience_encore_active(plateforme):
    """Une exécution encore vivante interdit la suppression : on ne détruit rien sous ses pieds."""
    with pytest.raises(ValueError, match="encore active"):
        experiences.supprimer_experience("autre_experience")
    assert (experiences.DOSSIER / "autre_experience").is_dir(), "rien n'a été supprimé"


def test_supprimer_un_nom_inconnu_leve_une_erreur(plateforme):
    with pytest.raises(ValueError, match="aucune expérience"):
        experiences.supprimer_experience("nom_qui_n_existe_pas")


# ── retirer une ligne du tableau sans rien effacer ───────────────────────────
# Le 🗑 du registre effaçait `data/experiences/<nom>/` en deux clics ; une expérience et ses
# décisions déjà payées ont ainsi disparu sans retour possible le 2026-09-07. Il retire
# désormais la seule ligne cliquée, et le disque n'est pas touché.


def test_masquer_retire_la_ligne_du_tableau_et_laisse_le_disque_intact(plateforme):
    dossier = experiences.DOSSIER / "finie" / "executions" / "2026-09-06_09_00_00"
    assert any(l["experience"] == "finie" for l in experiences.lister())

    experiences.masquer("finie", "2026-09-06_09_00_00")

    assert not any(l["experience"] == "finie" for l in experiences.lister()), "la ligne a quitté le tableau"
    assert dossier.is_dir(), "l'archive de l'exécution est intacte"
    assert (experiences.DOSSIER / "finie" / "experience.yaml").is_file(), "la définition est intacte"


def test_masquer_ne_retire_que_la_ligne_cliquee(plateforme):
    """Portée : une ligne. Les autres exécutions de la même expérience restent au tableau."""
    _execution(experiences.DOSSIER, "finie", "2026-09-06_18_00_00", "terminee")
    assert len([l for l in experiences.lister() if l["experience"] == "finie"]) == 2

    experiences.masquer("finie", "2026-09-06_09_00_00")

    restantes = [l["execution"] for l in experiences.lister() if l["experience"] == "finie"]
    assert restantes == ["2026-09-06_18_00_00"], restantes


def test_masquer_refuse_une_execution_encore_vivante(plateforme):
    """Retirée du tableau, une exécution qui écrit encore n'aurait plus personne pour l'arrêter."""
    with pytest.raises(ValueError, match="tourne encore"):
        experiences.masquer("autre_experience", "2026-09-07_10_00_00")
    assert any(l["experience"] == "autre_experience" for l in experiences.lister())


def test_masquer_deux_fois_la_meme_ligne_n_ecrit_qu_une_entree(plateforme):
    experiences.masquer("finie", "2026-09-06_09_00_00")
    experiences.masquer("finie", "2026-09-06_09_00_00")
    assert len(experiences.masques()) == 1


def test_demasquer_tout_rend_les_lignes_au_tableau(plateforme):
    experiences.masquer("finie", "2026-09-06_09_00_00")
    experiences.masquer("suspendue", "2026-09-06_12_00_00")

    assert experiences.demasquer_tout() == 2
    assert experiences.masques() == []
    rendues = {l["experience"] for l in experiences.lister()}
    assert {"finie", "suspendue"} <= rendues


def test_le_fichier_des_masques_ne_devient_jamais_une_experience(plateforme):
    """`.masques.json` vit dans le dossier des expériences : il ne doit pas y en devenir une."""
    experiences.masquer("finie", "2026-09-06_09_00_00")
    assert (experiences.DOSSIER / ".masques.json").is_file()
    assert "masques" not in {l["experience"] for l in experiences.lister()}
    assert not (experiences.DOSSIER / ".masques.json.tmp").exists(), "l'écriture est atomique"


def test_une_selection_perimee_ne_fait_plus_tomber_la_page():
    """Streamlit garde la sélection par INDICE : il survit au rétrécissement du tableau.

    Sans borne, `df.iloc[3]` sur un tableau redevenu à 2 lignes levait « single positional
    indexer is out-of-bounds » et emportait toute la page (2026-09-07, après un retrait).
    """
    event = {"selection": {"rows": [3]}}
    assert experiences._lignes_selectionnees(event) == [3], "sans borne, l'indice est rendu tel quel"
    assert experiences._lignes_selectionnees(event, 2) == [], "borné : l'indice périmé est écarté"
    assert experiences._lignes_selectionnees(event, 4) == [3], "borné : un indice valide passe"
    assert experiences._lignes_selectionnees({"selection": {"rows": []}}, 2) == []


def test_une_ligne_retiree_qui_se_remet_a_tourner_revient_au_tableau(plateforme):
    """Relancée en console, une exécution retirée écrirait sans que personne ne la voie."""
    experiences.masquer("finie", "2026-09-06_09_00_00")
    assert not any(l["experience"] == "finie" for l in experiences.lister())

    _ecrire(experiences.DOSSIER / "finie" / "executions" / "2026-09-06_09_00_00" / "etat.json",
            {"etat": "en_cours"})

    ligne = next((l for l in experiences.lister() if l["experience"] == "finie"), None)
    assert ligne is not None, "ce qui tourne reste visible, même retiré du tableau"
    assert experiences.masques(), "le retrait est conservé : il reprendra quand elle se sera tue"


# ── ⏸/⏹ ne s'offrent que sur une exécution qui écrit encore ──────────────────
# `etat.json` dit « en cours » pour toujours quand le runner a été tué. Les deux boutons
# restaient donc offerts sur un cadavre, et la sentinelle déposée attendait la reprise
# suivante pour la saboter : PAUSE la remettait en pause aussitôt, STOP scellait l'archive.


def _ligne_arret(dossier):
    """La forme minimale que `_boutons_arret` attend d'une ligne d'exécution."""
    return {"experience": "autre_experience", "execution": "2026-09-07_10_00_00",
            "dossier": str(dossier), "pause_demandee": None, "arret_demande": None}


def test_R11_pause_et_arret_disparaissent_sur_une_execution_morte(plateforme):
    dossier = experiences.DOSSIER / "autre_experience" / "executions" / "2026-09-07_10_00_00"
    _vieillir(dossier, 20)
    assert experiences.execution_vivante(dossier) is False

    st = FauxSt()
    experiences._boutons_arret(st, _ligne_arret(dossier), 0)

    assert st.boutons == [], f"aucun bouton d'interruption sur un runner tué : {st.boutons}"
    assert st.cases == [], "ni la case de confirmation de l'arrêt définitif"
    assert any("Reprendre" in l for l in st.legendes),         f"la page doit nommer le chemin propre : {st.legendes}"


def test_R11_pause_et_arret_restent_offerts_sur_une_execution_vivante(plateforme):
    dossier = experiences.DOSSIER / "autre_experience" / "executions" / "2026-09-07_10_00_00"
    _vieillir(dossier, 0.1)
    assert experiences.execution_vivante(dossier) is True

    st = FauxSt()
    experiences._boutons_arret(st, _ligne_arret(dossier), 0)

    assert any("Pause" in b for b in st.boutons), st.boutons
    assert any("Arrêter" in b for b in st.boutons), st.boutons


def test_R11_aucune_sentinelle_n_est_deposee_par_le_rendu(plateforme):
    """Le rendu seul n'écrit rien : seuls les clics le font (les faux boutons rendent False)."""
    dossier = experiences.DOSSIER / "autre_experience" / "executions" / "2026-09-07_10_00_00"
    _vieillir(dossier, 20)
    experiences._boutons_arret(FauxSt(), _ligne_arret(dossier), 0)
    assert not (dossier / "PAUSE").exists() and not (dossier / "STOP").exists()
