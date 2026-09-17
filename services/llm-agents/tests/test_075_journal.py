"""Ticket 075, § B et C — journal de mémoire et reprise à chaud.

Contrat écrit avant le code : `specs/ticket_075/tests.md`, § 2 et § 3.
"""

import datetime as dt
import json
from pathlib import Path

import pytest
from llm.journal_memoire import JournalMemoire, journal
from llm.memory import MemoryEntry, MemoryType
from settings import settings
from urban_mobility_agents.utils import ancre_run, reprise

QUAND = dt.datetime(2026, 3, 18, 22, 0)  # noqa: DTZ001 — heure MURALE de GAMA, cf. sim_clock


def _episode(contenu="[TRAVEL_PLAN] bike to work", gravite=0.0, force=2.8, **kw):
    return MemoryEntry(
        content=contenu,
        timestamp=QUAND,
        memory_type=MemoryType.CONVERSATION,
        person_id="609",
        importance=gravite,
        force=force,
        **kw,
    )


def _concept(contenu='["line 401 saturates when it rains"]', obs=1, contre=0, **kw):
    return MemoryEntry(
        content=contenu,
        timestamp=QUAND,
        memory_type=MemoryType.CONCEPT,
        person_id="609",
        observations=obs,
        contre_exemples=contre,
        **kw,
    )


@pytest.fixture
def journal_actif(tmp_path, monkeypatch):
    monkeypatch.setattr(settings.agent, "journal_memoire_enabled", True, raising=False)
    monkeypatch.setattr(
        settings.agent, "journal_memoire_dir", str(tmp_path / "memoires"), raising=False
    )
    JournalMemoire.reinitialiser()
    # Sous pytest, `get()` n'ouvre plus de journal tout seul (c'est un artefact de run) :
    # le test fournit le sien, sur un répertoire à lui.
    JournalMemoire._instance = JournalMemoire(tmp_path / "memoires")
    reprise.reinitialiser()
    ancre_run.reinitialiser()
    yield tmp_path / "memoires"
    JournalMemoire.reinitialiser()
    reprise.reinitialiser()
    ancre_run.reinitialiser()


def _texte(repertoire, person_id="609"):
    return (repertoire / f"{person_id}.md").read_text(encoding="utf-8")


class TestExtinction:
    def test_B1_eteint_par_defaut_rien_n_est_ecrit(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            settings.agent, "journal_memoire_enabled", False, raising=False
        )
        monkeypatch.setattr(
            settings.agent,
            "journal_memoire_dir",
            str(tmp_path / "jamais"),
            raising=False,
        )
        JournalMemoire.reinitialiser()
        assert journal() is None
        assert not (tmp_path / "jamais").exists()


class TestConsolidation:
    @pytest.mark.parametrize(
        "motif",
        ["plancher journalier", "rupture", "seuil"],
    )
    def test_B2_B3_B4_le_motif_et_son_declencheur_sont_ecrits(
        self, journal_actif, motif
    ):
        """B2/B3/B4 — une consolidation sans son déclencheur ne s'interprète pas."""
        j = journal()
        j.ouvrir_agent("609", {"name": "Xavier Briand"})
        j.consolidation_debut("609", QUAND, motif, "ce qui l'a provoquée", [_episode()])
        texte = _texte(journal_actif)
        assert "CONSOLIDATION" in texte
        assert motif in texte
        assert "ce qui l'a provoquée" in texte
        assert "[TRAVEL_PLAN] bike to work" in texte

    def test_B5_concept_cree(self, journal_actif):
        j = journal()
        j.operation_concept(
            "609", "créé", apres="line 401 saturates", note="gravité 0.40"
        )
        texte = _texte(journal_actif)
        assert "créé" in texte and "line 401 saturates" in texte and "0.40" in texte

    def test_B6_concept_confirme_porte_l_avant_et_l_apres(self, journal_actif):
        j = journal()
        j.operation_concept(
            "609", "confirmé", observations="3 → 4", confiance="0.80 → 0.83"
        )
        texte = _texte(journal_actif)
        assert "confirmé" in texte and "3 → 4" in texte and "0.80 → 0.83" in texte

    def test_B7_concept_precise_montre_le_contenu_avant_et_apres(self, journal_actif):
        j = journal()
        j.operation_concept(
            "609", "précisé", avant="le bus est lent", apres="le bus 401 sature à 8 h"
        )
        texte = _texte(journal_actif)
        assert "le bus est lent" in texte and "le bus 401 sature à 8 h" in texte

    def test_B8_concept_contredit_et_mise_a_l_ecart(self, journal_actif):
        j = journal()
        j.operation_concept(
            "609",
            "contredit",
            contre_exemples="0 → 1",
            note="**mis à l'écart** le 2026-03-18T22:00 — il cesse d'être servi",
        )
        texte = _texte(journal_actif)
        assert "contredit" in texte and "mis à l'écart" in texte

    def test_B11_l_etat_complet_porte_les_colonnes_attendues(self, journal_actif):
        j = journal()
        depasse = _concept(obs=0, contre=3, depasse_le="2026-03-17T22:00:00")
        j.consolidation_fin("609", QUAND, [_episode(), _concept(), depasse])
        texte = _texte(journal_actif)
        for colonne in (
            "gravité",
            "force (j)",
            "rappels",
            "confiance",
            "axes",
            "statut",
        ):
            assert colonne in texte
        assert "épisodique" in texte
        assert "hors service" in texte or "dépassé" in texte

    def test_B9_purge(self, journal_actif):
        j = journal()
        vieux = _episode(contenu="vieux trajet", force=2.0)
        vieux.dernier_rappel = QUAND - dt.timedelta(days=14)
        j.purge("609", QUAND, [vieux])
        texte = _texte(journal_actif)
        assert "purge" in texte and "vieux trajet" in texte and "14.0 j" in texte

    def test_B12_le_rappel_tient_en_une_ligne(self, journal_actif):
        j = journal()
        j.rappel("609", QUAND, [_episode(), _episode(contenu="autre")])
        lignes = [
            ligne
            for ligne in _texte(journal_actif).splitlines()
            if "**rappel**" in ligne
        ]
        assert len(lignes) == 1
        assert "2 souvenir(s)" in lignes[0]


class TestIsolationEtRobustesse:
    def test_B10_chaque_agent_a_son_fichier(self, journal_actif):
        j = journal()
        j.ecriture("609", QUAND, _episode())
        autre = _episode(contenu="souvenir du 11195")
        autre.person_id = "11195"
        j.ecriture("11195", QUAND, autre)
        assert "souvenir du 11195" not in _texte(journal_actif, "609")
        assert "souvenir du 11195" in _texte(journal_actif, "11195")

    def test_B13_une_erreur_disque_ne_remonte_jamais(self, journal_actif, monkeypatch):
        """Un journal ne fait pas tomber une simulation de soixante jours."""
        j = journal()

        def _refuse(*_args, **_kwargs):
            raise OSError("disque plein")

        monkeypatch.setattr("pathlib.Path.open", _refuse)
        j.ecriture("609", QUAND, _episode())  # ne doit pas lever


class TestReprise:
    def test_C1_C2_le_point_est_complet_et_atomique(self, tmp_path):
        reprise.reinitialiser()
        ancre_run.reinitialiser()
        workdir = tmp_path / "run"
        (workdir / "long_term_memory").mkdir(parents=True)
        (workdir / "long_term_memory" / "meta.json").write_text("{}", encoding="utf-8")
        (workdir / "memoires").mkdir()
        (workdir / "memoires" / "609.md").write_text("jour 1", encoding="utf-8")

        point = reprise.ecrire_point(workdir, 2, 1_773_810_000)
        assert point is not None and point.name == "jour_002"
        meta = json.loads((point / reprise.DESCRIPTION).read_text(encoding="utf-8"))
        assert meta["jour_simule"] == 2
        assert (point / "long_term_memory" / "meta.json").exists()
        assert (point / "memoires" / "609.md").read_text(encoding="utf-8") == "jour 1"
        # Atomicité : aucun répertoire de travail ne survit à l'écriture.
        assert not list(point.parent.glob("*.en_cours"))

    def test_C3_reprise_sans_point_alarme_et_ne_gele_pas(self, tmp_path):
        reprise.reinitialiser()
        assert reprise.restaurer_si_demande(tmp_path, reprise_demandee=True) is None
        assert reprise.gel_actif() is False

    def test_C4_C5_C8_restauration_gel_et_ancre(self, tmp_path):
        reprise.reinitialiser()
        ancre_run.reinitialiser()
        workdir = tmp_path / "run"
        (workdir / "memoires").mkdir(parents=True)
        (workdir / "memoires" / "609.md").write_text("jour 1 et 2", encoding="utf-8")
        ancre_run.ancrer(1_773_637_200)
        reprise.ecrire_point(workdir, 2, 1_773_810_000)

        # Ce que le rejeu écraserait : la mémoire a continué après le point.
        (workdir / "memoires" / "609.md").write_text(
            "jour 1, 2 et 3 abîmé", encoding="utf-8"
        )
        ancre_run.reinitialiser()
        reprise.reinitialiser()

        meta = reprise.restaurer_si_demande(workdir, reprise_demandee=True)
        assert meta is not None and meta["jour_simule"] == 2
        # C4 : l'état est celui du point.
        assert (workdir / "memoires" / "609.md").read_text(
            encoding="utf-8"
        ) == "jour 1 et 2"
        # C5 : le gel est actif.
        assert reprise.gel_actif() is True
        # C8 : l'ancre vient du point, pas du premier timestamp du rejeu.
        ancre_run.ancrer(1_773_637_200 + 5 * 86400)
        assert ancre_run.ancre() == 1_773_637_200

    def test_C6_le_degel_tombe_au_depassement_du_point(self, tmp_path):
        reprise.reinitialiser()
        reprise.geler_jusqu_a(1_773_810_000, 2)
        assert reprise.degeler_si_depasse(1_773_809_999) is False
        assert reprise.gel_actif() is True
        assert reprise.degeler_si_depasse(1_773_810_000) is True
        assert reprise.gel_actif() is False

    def test_C5bis_le_journal_n_ecrit_rien_pendant_le_rejeu(self, journal_actif):
        j = journal()
        j.ecriture("609", QUAND, _episode(contenu="avant le gel"))
        reprise.geler_jusqu_a(1_773_810_000, 2)
        j.ecriture("609", QUAND, _episode(contenu="pendant le rejeu"))
        texte = _texte(journal_actif)
        assert "avant le gel" in texte
        assert "pendant le rejeu" not in texte


class TestPasDArtefactsALImport:
    """Ticket 075 — deux défauts trouvés EN RUN, le 2026-09-14, et leurs gardes.

    Le run pilote est mort d'une I/O error côté GAMA : le symlink de sortie
    `services/GAMA/CityTransport/results` avait été repointé vers un répertoire qui n'existe
    que sous `services/llm-agents/experiments/`. En cherchant, on a trouvé un second semeur de
    répertoires : le journal de mémoire, qui créait le sien à la construction.
    """

    def test_le_journal_ne_cree_rien_avant_d_ecrire(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings.agent, "journal_memoire_enabled", True, raising=False)
        cible = tmp_path / "jamais_avant_ecriture"
        monkeypatch.setattr(settings.agent, "journal_memoire_dir", str(cible), raising=False)
        JournalMemoire.reinitialiser()
        JournalMemoire._instance = JournalMemoire(cible)
        j = journal()
        assert j is not None
        assert not cible.exists(), "un simple import ne doit créer aucun répertoire de run"
        j.ecriture("609", QUAND, _episode())
        assert cible.is_dir(), "le répertoire apparaît à la première écriture"
        JournalMemoire.reinitialiser()

    def test_un_experiments_hors_racine_ne_vole_pas_le_lien_de_gama(self, tmp_path):
        """`experiments_dir` dont le NOM est « experiments » ne suffit pas : il doit être
        celui de la racine, sinon le lien écrit pend et GAMA échoue sur `save`."""
        from settings import FactorySettings

        source = Path(FactorySettings.claim_run.__func__.__code__.co_filename).read_text(
            encoding="utf-8"
        )
        assert "_experiences_de_la_racine" in source, (
            "la vérification contre le répertoire d'expériences de la racine a disparu"
        )
        assert "Redirection des sorties GAMA REFUSÉE" in source, (
            "le refus doit rester un REFUS : réécrire le lien puis alarmer laisserait la "
            "simulation en cours sans sortie"
        )


class TestRejeuEtQuota:
    """Ticket 075 — le rejeu ne doit pas repayer les décisions du run d'origine.

    Mesuré le 2026-09-14 sur le rejeu d'une journée : 33 % de service seulement, onze
    décisions sur dix-huit renvoyées au modèle, parce que la branche PAR SIMILARITÉ compare la
    mémoire courante — figée au point de reprise — à celle qui avait produit la décision.
    """

    def test_pendant_le_gel_la_recherche_de_cache_ignore_la_memoire(self):
        # Chemin résolu depuis CE fichier, et non depuis le répertoire courant : le test
        # échouait dès que pytest était lancé depuis `services/llm-agents/` plutôt que
        # depuis la racine du dépôt (ticket 077, au passage).
        source = (
            Path(__file__).resolve().parents[1]
            / "urban_mobility_agents"
            / "agents"
            / "llm_agent.py"
        ).read_text(encoding="utf-8")
        assert "_memory_text_cache = None if gel_actif() else memory_text" in source, (
            "la branche exacte pendant le rejeu a disparu : un rejeu de quarante jours "
            "repaierait plus d'une journée de quota"
        )
        assert "memory_text=_memory_text_cache," in source, (
            "la recherche de cache doit utiliser la variable gelée, pas `memory_text`"
        )


class TestSectionsDeJour:
    def test_une_section_par_jour_et_jamais_de_retour_en_arriere(self, journal_actif):
        """Une écriture datée de la veille ne rouvre pas la veille : 32 jours = 32 sections."""
        j = journal()
        veille = QUAND - dt.timedelta(days=1)
        j.consolidation_debut("609", QUAND, "seuil", "10 entrées", [])
        j.ecriture("609", veille, _episode(contenu="souvenir du matin de la veille"))
        j.ecriture("609", QUAND, _episode(contenu="souvenir du soir"))
        j.consolidation_debut("609", QUAND + dt.timedelta(days=1), "plancher", "22 h", [])
        texte = _texte(journal_actif)
        sections = [l for l in texte.splitlines() if l.startswith("## ")]
        assert len(sections) == 2, f"une section par jour attendue, vu : {sections}"
        assert "souvenir du matin de la veille" in texte
