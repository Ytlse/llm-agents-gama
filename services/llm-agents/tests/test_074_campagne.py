"""Ticket 074, lot D — la campagne mène 22 expériences au bout, à travers les quotas.

Ce qui est vérifié ici n'est pas « le code tourne » mais les quatre promesses qui font qu'une
campagne vaut mieux qu'un humain qui relance :

1. elle **refuse** plutôt que de démarrer sur une définition qui la ferait échouer au milieu ;
2. elle respecte l'**ordre des phases** — les témoins gratuits avant le quota ;
3. elle **reprend là où elle s'est arrêtée**, jamais au début, même après un redémarrage ;
4. elle **dit** ce qu'elle fait — succès, échecs, sommeils — avec les alarmes de la doctrine.

Le temps est INJECTÉ (`dormir`, `max_tours`). Une boucle qu'on ne teste qu'en attendant
vraiment trente secondes n'est pas testée : elle est seulement lente à ne pas l'être.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml
from loguru import logger
from experiences import campagne as C

# ── Banc ─────────────────────────────────────────────────────────────────────


def _definir_experience(racine: Path, nom: str) -> Path:
    """Une définition minimale : la campagne ne lit que son existence."""
    d = racine / nom
    d.mkdir(parents=True, exist_ok=True)
    (d / "experience.yaml").write_text(yaml.safe_dump({"nom": nom}), encoding="utf-8")
    return d


def _poser_etat(
    racine: Path,
    nom: str,
    etat: str,
    *,
    horodatage: str = "2026-09-14_10_00_00",
    raison: str | None = None,
    maj: str = "2026-09-14T10:00:00+00:00",
    interruptions: list[dict] | None = None,
) -> None:
    d = racine / nom / "executions" / horodatage
    d.mkdir(parents=True, exist_ok=True)
    (d / "etat.json").write_text(
        json.dumps({"etat": etat, "raison": raison, "maj": maj}),
        encoding="utf-8",
    )
    if interruptions is not None:
        # L'`execution.yaml` porte la trace STRUCTURÉE de l'interruption : c'est elle qui
        # distingue une pause subie d'une pause demandée, pas le message de `etat.json`.
        (d / "execution.yaml").write_text(
            yaml.safe_dump({"interruptions": interruptions}, allow_unicode=True),
            encoding="utf-8",
        )


def _pause_chien_de_garde(racine: Path, nom: str, **kw) -> None:
    """Ce que le runner écrit après 420 s sans avancée : le processus est mort."""
    _poser_etat(
        racine, nom, "en_pause",
        raison="pause automatique — 420s sans avancée ; 0/3299 archivées",
        interruptions=[{"instant": "2026-09-14T10:00:00+00:00", "cause": "pause",
                        "decisions_archivees": 0, "raison": "inactivite:420s"}],
        **kw,
    )


def _pause_humaine(racine: Path, nom: str, **kw) -> None:
    """Ce que le runner écrit quand quelqu'un a demandé la pause : elle attend un humain."""
    _poser_etat(
        racine, nom, "en_pause", raison="pause — 120/3299 archivées",
        interruptions=[{"instant": "2026-09-14T10:00:00+00:00", "cause": "pause",
                        "decisions_archivees": 120, "raison": "manuelle"}],
        **kw,
    )


@pytest.fixture
def journal():
    """Les messages de loguru, que `caplog` ne voit pas (il n'écoute que `logging`)."""
    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(str(m)), level="INFO")
    try:
        yield messages
    finally:
        logger.remove(sink)


@pytest.fixture
def banc(tmp_path, monkeypatch):
    """Un dépôt de poche : des expériences définies, un dossier de campagnes, aucun Docker."""
    experiences = tmp_path / "experiences"
    campagnes = tmp_path / "campagnes"
    experiences.mkdir()
    campagnes.mkdir()
    monkeypatch.setenv("EXPERIENCES_DIR", str(experiences))
    monkeypatch.setenv("CAMPAGNES_DIR", str(campagnes))

    lances: list[str] = []
    vrai_lancement = C._lancer_experience
    # Le vrai `_lancer_experience` prend (exp, lanceurs) : le simulacre doit accepter les
    # deux, sinon il masque la signature au lieu de la remplacer.
    monkeypatch.setattr(C, "_lancer_experience",
                        lambda exp, lanceurs=None: lances.append(exp))
    monkeypatch.setattr(C, "_tour_ordonnanceur", lambda: None)
    return {"experiences": experiences, "campagnes": campagnes, "lances": lances,
            "vrai_lancement": vrai_lancement}


def _ecrire_campagne(banc, nom: str, phases: list[dict], **extra) -> None:
    doc = {"nom": nom, "version": C.VERSION_CAMPAGNE, "phases": phases, **extra}
    (banc["campagnes"] / f"{nom}.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


@pytest.fixture
def deux_phases(banc):
    for n in ("t1", "t2", "llm1", "llm2"):
        _definir_experience(banc["experiences"], n)
    _ecrire_campagne(
        banc,
        "c",
        [
            {"nom": "temoins", "raison": "gratuits", "experiences": ["t1", "t2"]},
            {"nom": "llm", "experiences": ["llm1", "llm2"]},
        ],
    )
    return banc


# ── 1. Elle refuse plutôt que d'échouer au milieu ────────────────────────────


class TestRefus:
    def test_une_campagne_absente_dit_lesquelles_existent(self, banc):
        _ecrire_campagne(banc, "reelle", [{"nom": "p", "experiences": ["x"]}])
        _definir_experience(banc["experiences"], "x")
        with pytest.raises(C.CampagneInvalide, match="reelle"):
            C.charger("fantome")

    def test_une_version_inattendue_est_refusee(self, banc):
        (banc["campagnes"] / "c.yaml").write_text(
            yaml.safe_dump(
                {
                    "nom": "c",
                    "version": "campagne0",
                    "phases": [{"nom": "p", "experiences": ["x"]}],
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(C.CampagneInvalide, match="campagne0"):
            C.charger("c")

    def test_une_experience_inexistante_est_refusee_AVANT_de_depenser(self, banc):
        _definir_experience(banc["experiences"], "existe")
        _ecrire_campagne(banc, "c", [{"nom": "p", "experiences": ["existe", "manque"]}])
        with pytest.raises(C.CampagneInvalide, match="manque"):
            C.charger("c")

    def test_une_phase_vide_est_refusee(self, banc):
        _ecrire_campagne(banc, "c", [{"nom": "vide", "experiences": []}])
        with pytest.raises(C.CampagneInvalide, match="aucune expérience"):
            C.charger("c")

    def test_une_experience_dans_deux_phases_est_refusee(self, banc):
        _definir_experience(banc["experiences"], "x")
        _ecrire_campagne(
            banc,
            "c",
            [{"nom": "a", "experiences": ["x"]}, {"nom": "b", "experiences": ["x"]}],
        )
        with pytest.raises(C.CampagneInvalide, match="deux phases"):
            C.charger("c")


# ── 2. L'ordre des phases ────────────────────────────────────────────────────


class TestPhases:
    def test_la_phase_2_ne_demarre_pas_avant_la_fin_de_la_phase_1(self, deux_phases):
        C.lancer("c", max_tours=3, dormir=lambda _s: None)
        # Une seule expérience en vol à la fois, et c'est une expérience de la phase 1.
        assert deux_phases["lances"] == ["t1"], deux_phases["lances"]

    def test_la_phase_2_demarre_quand_la_phase_1_est_close(self, deux_phases):
        for n in ("t1", "t2"):
            _poser_etat(deux_phases["experiences"], n, "terminee")
        C.lancer("c", max_tours=4, dormir=lambda _s: None)
        assert deux_phases["lances"] == ["llm1"], deux_phases["lances"]
        etat = C.lire_etat("c")
        assert etat["phase_courante"] == "llm"
        assert set(etat["faites"]) == {"t1", "t2"}

    def test_une_campagne_toute_faite_se_declare_terminee(self, deux_phases):
        for n in ("t1", "t2", "llm1", "llm2"):
            _poser_etat(deux_phases["experiences"], n, "terminee")
        assert C.lancer("c", max_tours=10, dormir=lambda _s: None) == 0
        etat = C.lire_etat("c")
        assert etat["terminee_le"]
        assert len(etat["faites"]) == 4 and not etat["restantes"]
        assert deux_phases["lances"] == []


# ── 3. La reprise ────────────────────────────────────────────────────────────


class TestReprise:
    def test_elle_reprend_ou_elle_en_etait_pas_au_debut(self, deux_phases):
        """La promesse D-3, et la seule qui compte quand un sommeil dure la nuit."""
        _poser_etat(deux_phases["experiences"], "t1", "terminee")
        C.lancer("c", max_tours=2, dormir=lambda _s: None)
        assert deux_phases["lances"] == ["t2"]

        # Redémarrage : l'état est relu sur le disque, t1 n'est pas rejouée.
        deux_phases["lances"].clear()
        C.lancer("c", max_tours=2, dormir=lambda _s: None)
        assert "t1" not in deux_phases["lances"]

    def test_une_execution_interrompue_est_reprise(self, deux_phases):
        _poser_etat(
            deux_phases["experiences"], "t1", "interrompue", raison="processus mort"
        )
        C.lancer("c", max_tours=2, dormir=lambda _s: None)
        assert "t1" in deux_phases["lances"]

    def test_recommencer_ignore_l_etat_existant(self, deux_phases):
        C.ecrire_etat(
            "c",
            {
                **C.etat_par_defaut(C.charger("c")),
                "faites": ["t1", "t2"],
                "phase_courante": "llm",
            },
        )
        C.lancer("c", reprendre=False, max_tours=2, dormir=lambda _s: None)
        assert C.lire_etat("c")["phase_courante"] == "temoins"

    def test_l_etat_survit_a_un_json_tronque(self, deux_phases):
        (deux_phases["campagnes"] / "c").mkdir(parents=True, exist_ok=True)
        (deux_phases["campagnes"] / "c" / "etat.json").write_text(
            "{tronqué", encoding="utf-8"
        )
        assert C.lire_etat("c") is None  # dit, et repart de zéro — sans lever


# ── 4. Échecs, arrêt, sommeil ────────────────────────────────────────────────


class TestEchecsEtSommeil:
    def test_deux_echecs_de_suite_alarment_et_la_campagne_continue(
        self, deux_phases, caplog
    ):
        _poser_etat(deux_phases["experiences"], "t1", "arretee", raison="clé absente")
        import logging

        with caplog.at_level(logging.ERROR):
            C.lancer("c", max_tours=4, dormir=lambda _s: None)
        etat = C.lire_etat("c")
        assert "t1" in etat["echouees"]
        assert etat["echouees"]["t1"]["tentatives"] > C.TENTATIVES_MAX
        # Et la suivante part quand même : un échec n'annule pas le reste.
        assert "t2" in deux_phases["lances"]

    def test_un_arret_pose_PENDANT_la_boucle_sort_en_130(self, deux_phases):
        """Un arrêt demandé en cours de route est honoré au tour suivant."""

        def dormir_puis_arreter(_s):
            C.arreter("c")

        assert C.lancer("c", max_tours=5, dormir=dormir_puis_arreter) == 130
        # Une seule expérience a été lancée : l'arrêt a empêché la suite.
        assert deux_phases["lances"] == ["t1"], deux_phases["lances"]

    def test_lancer_leve_un_arret_precedent(self, deux_phases):
        C.arreter("c")
        assert C.demande_arret("c")
        C.lancer("c", max_tours=1, dormir=lambda _s: None)
        assert not C.demande_arret("c")

    def test_quota_epuise_et_RIEN_d_autre_a_faire_met_en_sommeil(self, banc):
        """Dormir reste juste quand la file est vide derrière : c'est le seul cas."""
        for n in ("t1", "t2"):
            _definir_experience(banc["experiences"], n)
        _ecrire_campagne(banc, "c", [{"nom": "p", "experiences": ["t1", "t2"]}])
        _poser_etat(banc["experiences"], "t1", "en_attente_quota")
        _poser_etat(banc["experiences"], "t2", "en_attente_quota")
        dormi: list[float] = []
        C.lancer("c", max_tours=2, dormir=dormi.append)
        etat = C.lire_etat("c")
        assert etat["sommeils"], "un sommeil doit être consigné, pas subi en silence"
        assert etat["sommeils"][0]["jusqu"], "l'heure de réveil doit être écrite"
        assert dormi and dormi[0] > 0
        assert not etat["reportees"], "rien à reporter quand rien d'autre ne peut tourner"

    def test_quota_epuise_mais_AUTRE_CHOSE_a_faire_reporte_au_lieu_de_dormir(
        self, deux_phases
    ):
        """Le défaut corrigé le 2026-09-15 : dormir 24 h devant une file pleine.

        Un quota épuisé chez un fournisseur ne dit rien des autres. Tant qu'une expérience
        peut tourner, celle qui dort est mise de côté et la campagne avance.
        """
        _poser_etat(deux_phases["experiences"], "t1", "en_attente_quota")
        _poser_etat(deux_phases["experiences"], "t2", "en_attente_quota")
        C.lancer("c", max_tours=2, dormir=lambda _s: None)
        etat = C.lire_etat("c")
        assert not etat["sommeils"], "la campagne ne doit PAS dormir : llm1 et llm2 attendent"
        assert set(etat["reportees"]) == {"t1", "t2"}
        assert etat["reportees"]["t1"]["motif"], "le motif du report doit être consigné"
        for exp in ("t1", "t2"):
            stop = deux_phases["experiences"] / exp / "executions" / "2026-09-14_10_00_00" / "STOP"
            assert stop.is_file(), (
                "une expérience reportée doit être ARRÊTÉE, sinon son processus dort toujours "
                "et tient sa clé"
            )

    def test_une_seule_en_attente_ne_met_PAS_la_campagne_en_sommeil(self, deux_phases):
        """Le piège : dormir parce qu'UNE exécution dort gèlerait la campagne pour rien."""
        _poser_etat(deux_phases["experiences"], "t1", "en_attente_quota")
        _poser_etat(deux_phases["experiences"], "t2", "en_cours")
        C.lancer("c", max_tours=2, dormir=lambda _s: None)
        assert not (C.lire_etat("c")["sommeils"])

    def test_un_sommeil_trop_long_leve_une_alarme(
        self, deux_phases, monkeypatch, journal
    ):
        monkeypatch.setattr(
            C,
            "prochain_reveil",
            lambda *a, **k: ("2026-09-17T00:00:00+00:00", 40 * 3600),
        )
        _poser_etat(deux_phases["experiences"], "llm1", "en_attente_quota")
        _poser_etat(deux_phases["experiences"], "llm2", "en_attente_quota")
        _poser_etat(deux_phases["experiences"], "t1", "terminee")
        _poser_etat(deux_phases["experiences"], "t2", "terminee")
        C.lancer("c", max_tours=3, dormir=lambda _s: None)
        assert sum("[ALARME]" in m and "24" in m for m in journal) == 1, \
            "une alarme par sommeil, pas une par tour"


# ── Lecture ──────────────────────────────────────────────────────────────────


class TestLecture:
    def test_etat_lisible_ne_leve_pas_sur_une_campagne_jamais_lancee(self, deux_phases):
        vue = C.etat_lisible("c")
        assert vue["etat"] is None and vue["total"] == 4 and vue["faites"] == []
        assert [p["nom"] for p in vue["phases"]] == ["temoins", "llm"]

    def test_etat_lisible_compte_les_faites_par_phase(self, deux_phases):
        _poser_etat(deux_phases["experiences"], "t1", "terminee")
        vue = C.etat_lisible("c")
        assert vue["phases"][0]["faites"] == ["t1"]
        assert vue["faites"] == ["t1"]

    def test_une_experience_jamais_lancee_est_definie_pas_echouee(self, deux_phases):
        assert C.etat_experience("t1")["etat"] == "definie"

    def test_la_derniere_execution_est_la_plus_recente(self, deux_phases):
        _poser_etat(
            deux_phases["experiences"],
            "t1",
            "arretee",
            horodatage="2026-09-14_09_00_00",
        )
        _poser_etat(
            deux_phases["experiences"],
            "t1",
            "terminee",
            horodatage="2026-09-14_11_00_00",
        )
        assert C.etat_experience("t1")["etat"] == "terminee"

    def test_prochain_reveil_rend_une_date_future_et_ses_secondes(self):
        quand, secondes = C.prochain_reveil()
        assert quand.endswith("+00:00") and 0 < secondes <= 24 * 3600

# ── Le lancement lui-même ────────────────────────────────────────────────────


class TestLancementReel:
    """Ces tests exercent le VRAI `_lancer_experience` (seul `Popen` est simulé).

    Les tests ci-dessus le remplacent par une liste, ce qui les rend rapides et lisibles —
    mais les rendait aussi aveugles à ce qui s'est produit le 2026-09-15 : la campagne
    passait `--reprendre` d'office, la CLI le refuse sur une expérience qui n'a jamais
    tourné, et la sortie du lancement partait dans `/dev/null`. La campagne s'est arrêtée
    sur sa toute première action, sans un mot.
    """

    @pytest.fixture
    def lancer_vrai(self, deux_phases, monkeypatch):
        """Rend `(lancement, argv_vus, kwargs_vus)` — sans défaire le banc."""
        argv_vus: list[list[str]] = []
        kwargs_vus: list[dict] = []

        def _popen(argv, **kw):
            argv_vus.append(list(argv))
            kwargs_vus.append(kw)
            return None

        monkeypatch.setattr(C.subprocess, "Popen", _popen)
        return deux_phases["vrai_lancement"], argv_vus, kwargs_vus

    def test_une_experience_neuve_est_lancee_SANS_reprendre(self, lancer_vrai):
        lancement, argv, _ = lancer_vrai
        lancement("t1")
        assert "--reprendre" not in argv[-1], (
            "`lancer --reprendre` refuse quand il n'y a rien à reprendre : le passer d'office "
            "fait échouer le PREMIER lancement de chaque expérience.")
        assert "--experience" in argv[-1] and "t1" in argv[-1]

    def test_une_experience_deja_tentee_est_lancee_AVEC_reprendre(self, deux_phases,
                                                                  lancer_vrai):
        _poser_etat(deux_phases["experiences"], "t1", "interrompue")
        lancement, argv, _ = lancer_vrai
        lancement("t1")
        assert "--reprendre" in argv[-1]

    def test_la_sortie_du_lancement_est_CONSERVEE_pas_jetee(self, deux_phases, lancer_vrai):
        """Un lancement détaché dont on jette la sortie est un lancement dont on ignore le sort."""
        lancement, _, kwargs = lancer_vrai
        lancement("t1")
        flux = kwargs[-1].get("stdout")
        assert flux is not None and flux != C.subprocess.DEVNULL
        journaux = list((deux_phases["experiences"] / "t1" / "lancements").glob("*.log"))
        assert journaux, "le refus éventuel du lancement doit rester lisible quelque part"

# ── Le lancement qui n'aboutit jamais ────────────────────────────────────────


class TestLancementQuiNAboutitPas:
    """Un lancement refusé par la plateforme n'écrit jamais d'état. Que fait la campagne ?

    Elle le relançait SANS FIN : mesuré le 2026-09-15, 178 relances en six heures sur le
    témoin random forest, dont l'artefact est refusé par `decideur_modele` (règle R7 du
    ticket 044). La phase des témoins n'a jamais été close, et les six bras LLM n'ont jamais
    été atteints — une nuit entière perdue, sans une seule alarme.

    Un blocage silencieux vaut moins qu'un échec déclaré : au moins l'échec laisse passer
    la suite.
    """

    def test_un_lancement_muet_finit_par_etre_declare_en_echec(self, deux_phases, monkeypatch,
                                                               journal):
        # Le délai de grâce est ramené à zéro : on teste la logique, pas la patience.
        monkeypatch.setattr(C, "DELAI_ECRITURE_ETAT_S", 0.0)
        C.lancer("c", max_tours=8, dormir=lambda _s: None)
        etat = C.lire_etat("c")
        assert "t1" in etat["echouees"], "un lancement qui n'aboutit jamais doit être déclaré"
        assert "sans jamais écrire d'état" in etat["echouees"]["t1"]["motif"]
        assert sum("[ALARME]" in m and "t1" in m for m in journal) == 1

    def test_et_la_campagne_passe_a_la_SUIVANTE(self, deux_phases, monkeypatch):
        monkeypatch.setattr(C, "DELAI_ECRITURE_ETAT_S", 0.0)
        C.lancer("c", max_tours=8, dormir=lambda _s: None)
        assert "t2" in deux_phases["lances"], (
            "un échec ne doit pas bloquer la phase : c'est exactement ce qui a coûté la nuit "
            "du 2026-09-15.")

    def test_le_nombre_de_relances_est_BORNE(self, deux_phases, monkeypatch):
        monkeypatch.setattr(C, "DELAI_ECRITURE_ETAT_S", 0.0)
        C.lancer("c", max_tours=20, dormir=lambda _s: None)
        relances_t1 = deux_phases["lances"].count("t1")
        # La borne a changé le 2026-09-15 avec la passe de repêchage : une expérience en échec
        # a droit à UNE relance de plus par passe, jamais à un compteur remis à neuf. Le total
        # reste donc borné et calculable, ce qui est tout ce que ce test protège.
        borne = C.TENTATIVES_MAX + 1 + C.REPECHAGES_MAX
        assert relances_t1 <= borne, (
            f"t1 relancée {relances_t1} fois — la borne est {borne} "
            f"({C.TENTATIVES_MAX} tentatives + 1, plus {C.REPECHAGES_MAX} repêchages)")


# ── Repêchage de fin de campagne ─────────────────────────────────────────────


class TestRepechage:
    """Rien n'est abandonné sans une seconde chance (2026-09-15).

    Avant, une expérience mise de côté sortait de l'observation et n'y revenait jamais, même
    en relançant la campagne : son échec était écrit dans l'état, et l'état excluait ce qui y
    figurait. Un quota épuisé en milieu de campagne coûtait donc l'expérience pour de bon.
    """

    def test_une_reportee_repasse_a_la_fin(self, deux_phases):
        _poser_etat(deux_phases["experiences"], "t1", "en_attente_quota")
        _poser_etat(deux_phases["experiences"], "t2", "terminee")
        _poser_etat(deux_phases["experiences"], "llm1", "terminee")
        _poser_etat(deux_phases["experiences"], "llm2", "terminee")
        C.lancer("c", max_tours=6, dormir=lambda _s: None)
        etat = C.lire_etat("c")
        assert etat["repechages"] >= 1, "la fin de campagne doit déclencher un repêchage"
        assert "t1" not in etat["reportees"], (
            "la reportée doit être RESSORTIE de la liste pour être rejouée, pas seulement "
            "comptée"
        )
        assert etat["phase_courante"] == "temoins", (
            "le repêchage doit revenir à la phase qui porte la reportée, pas rester à la fin"
        )
        # Le relancement lui-même n'est pas observable ici : la fixture écrit un `etat.json`
        # figé, si bien que t1 se relit `en_attente_quota` même après son fichier STOP. Sur un
        # vrai run, le runner voit le STOP, clôt en `arretee`, et la reprise standard la
        # relance — c'est le chemin que `TestEchecsEtSommeil` couvre déjà.

    def test_le_repechage_est_borne(self, deux_phases, monkeypatch):
        """Une campagne qui boucle sans fin ne se voit pas : le nombre de passes est fixe."""
        monkeypatch.setattr(C, "DELAI_ECRITURE_ETAT_S", 0.0)
        _poser_etat(deux_phases["experiences"], "t2", "terminee")
        _poser_etat(deux_phases["experiences"], "llm1", "terminee")
        _poser_etat(deux_phases["experiences"], "llm2", "terminee")
        _poser_etat(deux_phases["experiences"], "t1", "arretee", raison="cassée")
        C.lancer("c", max_tours=60, dormir=lambda _s: None)
        etat = C.lire_etat("c")
        assert etat["repechages"] <= C.REPECHAGES_MAX
        assert etat["terminee_le"], "la campagne doit finir, même avec une expérience cassée"

    def test_une_reportee_qui_ne_revient_pas_leve_une_alarme(self, deux_phases, journal):
        """Le silence sur un bras jamais joué serait le pire défaut de cette mécanique."""
        monkeypatch_cible = deux_phases["experiences"]
        for n in ("t2", "llm1", "llm2"):
            _poser_etat(monkeypatch_cible, n, "terminee")
        _poser_etat(monkeypatch_cible, "t1", "en_attente_quota")
        C.lancer("c", max_tours=40, dormir=lambda _s: None)
        etat = C.lire_etat("c")
        if etat["reportees"]:
            assert any("[ALARME]" in m and "REPORTÉE" in m for m in journal), (
                "une expérience qui reste sur le carreau doit le dire fort"
            )


# ── Lanceur dédié ────────────────────────────────────────────────────────────


class TestLanceurDedie:
    """Certaines expériences ne passent pas par `experiences lancer`.

    Le témoin random forest en est une : la règle R7 du ticket 044 le tient hors de
    `decideur_modele.FAMILLES` pour qu'il ne devienne pas un arbitre, et son lanceur dédié
    inscrit sa famille le temps de son propre processus. La campagne doit pouvoir le dire,
    plutôt que de buter dessus.
    """

    def test_un_lanceur_declare_est_utilise_tel_quel(self, banc, monkeypatch):
        _definir_experience(banc["experiences"], "special")
        _ecrire_campagne(banc, "c", [{"nom": "p", "experiences": ["special"]}],
                         lanceurs={"special": ["/bin/echo", "--experience", "{exp}"]})
        argv_vus: list[list[str]] = []
        monkeypatch.setattr(C.subprocess, "Popen",
                            lambda argv, **kw: argv_vus.append(list(argv)))
        banc["vrai_lancement"]("special", C.charger("c").lanceurs)
        assert argv_vus[-1] == ["/bin/echo", "--experience", "special"], (
            "`{exp}` doit être remplacé par le nom de l'expérience")

    def test_sans_lanceur_declare_on_passe_par_la_plateforme(self, deux_phases, monkeypatch):
        argv_vus: list[list[str]] = []
        monkeypatch.setattr(C.subprocess, "Popen",
                            lambda argv, **kw: argv_vus.append(list(argv)))
        deux_phases["vrai_lancement"]("t1", C.charger("c").lanceurs)
        assert "experiences" in argv_vus[-1] and "lancer" in argv_vus[-1]

    def test_un_lanceur_pour_une_experience_absente_est_refuse(self, banc):
        _definir_experience(banc["experiences"], "x")
        _ecrire_campagne(banc, "c", [{"nom": "p", "experiences": ["x"]}],
                         lanceurs={"absente": ["/bin/echo"]})
        with pytest.raises(C.CampagneInvalide, match="absente"):
            C.charger("c")


# ── 9. La pause qui figeait la campagne ──────────────────────────────────────


class TestPauseQuiBloque:
    """Mesuré le 2026-09-16 : `en_pause` tombait dans le fourre-tout « en vol ».

    L'expérience n'était alors ni reprise (l'état n'est pas dans `ETATS_REPRENABLES`), ni
    endormie (ce n'est pas un quota), ni relancée (le délai de grâce ne surveille que les
    lancements du processus courant). La campagne tournait à vide, six heures durant, sans
    rien lancer derrière — et sans rien dire, puisqu'elle ne se déclare vivante qu'un tour
    sur vingt.
    """

    def test_une_pause_de_chien_de_garde_est_reprise(self, deux_phases):
        _pause_chien_de_garde(deux_phases["experiences"], "t1")
        C.lancer("c", max_tours=2, dormir=lambda _s: None)
        assert "t1" in deux_phases["lances"]

    def test_une_execution_incomplete_sans_interruption_est_reprise(self, deux_phases):
        """Le troisième chemin du runner : arrêt incomplet, pause jamais demandée.

        Son propre message dit « reprendre » — encore faut-il que la campagne le fasse.
        """
        _poser_etat(deux_phases["experiences"], "t1", "en_pause",
                    raison="incomplète : 12/3299 archivées — reprendre")
        C.lancer("c", max_tours=2, dormir=lambda _s: None)
        assert "t1" in deux_phases["lances"]

    def test_un_execution_yaml_illisible_penche_vers_la_reprise(self, deux_phases):
        """Un blocage sans borne est pire qu'une reprise de trop, que `TENTATIVES_MAX` plafonne."""
        _pause_chien_de_garde(deux_phases["experiences"], "t1")
        d = deux_phases["experiences"] / "t1" / "executions" / "2026-09-14_10_00_00"
        (d / "execution.yaml").write_text("{ceci n'est pas: du yaml: valide", encoding="utf-8")
        C.lancer("c", max_tours=2, dormir=lambda _s: None)
        assert "t1" in deux_phases["lances"]

    def test_une_pause_demandee_par_un_humain_n_est_pas_reprise(self, deux_phases):
        """La correction ne doit pas passer d'un excès à l'autre.

        Quelqu'un a mis cette exécution en pause ; la campagne ne la relance pas dans son
        dos, et ne saute pas non plus par-dessus pour lancer la suivante.
        """
        _pause_humaine(deux_phases["experiences"], "t1")
        C.lancer("c", max_tours=2, dormir=lambda _s: None)
        assert deux_phases["lances"] == []

    def test_le_scenario_reel_la_phase_llm_ne_reste_pas_a_zero_lancement(self, banc):
        """Une `en_pause` subie devant une `definie` : c'est exactement le blocage du 16/09."""
        for n in ("bloquee", "suivante"):
            _definir_experience(banc["experiences"], n)
        _ecrire_campagne(banc, "c",
                         [{"nom": "llm", "experiences": ["bloquee", "suivante"]}])
        _pause_chien_de_garde(banc["experiences"], "bloquee")
        C.lancer("c", max_tours=2, dormir=lambda _s: None)
        assert banc["lances"], "la campagne doit lancer quelque chose, pas tourner à vide"


# ── 10. L'alarme « en vol, mais figé » ───────────────────────────────────────


class TestEnVolFige:
    """Le garde-fou qui manquait : la campagne DIT qu'elle attend, et qui elle attend."""

    def _pause_humaine_ancienne(self, banc, nom: str) -> None:
        vieux = (
            datetime.now(timezone.utc) - timedelta(seconds=C.EN_VOL_FIGE_S + 600)
        ).isoformat()
        _pause_humaine(banc["experiences"], nom, maj=vieux)

    def test_une_experience_en_vol_figee_leve_une_alarme(self, deux_phases, journal):
        self._pause_humaine_ancienne(deux_phases, "t1")
        C.lancer("c", max_tours=2, dormir=lambda _s: None)
        alarmes = [m for m in journal if "[ALARME]" in m and "EN VOL" in m]
        assert alarmes, "un blocage silencieux ne se voit pas — il doit s'annoncer"
        assert "t1" in alarmes[0]
        assert "experience-reprendre" in alarmes[0], "une alarme dit quoi faire"

    def test_l_alarme_ne_se_repete_pas_a_chaque_tour(self, deux_phases, journal):
        """Front montant : une alarme deux fois par minute noie le journal qu'elle éclaire."""
        self._pause_humaine_ancienne(deux_phases, "t1")
        C.lancer("c", max_tours=8, dormir=lambda _s: None)
        assert len([m for m in journal if "[ALARME]" in m and "EN VOL" in m]) == 1

    def test_une_experience_en_vol_recente_n_alarme_pas(self, deux_phases, journal):
        _pause_humaine(deux_phases["experiences"], "t1",
                       maj=datetime.now(timezone.utc).isoformat())
        C.lancer("c", max_tours=4, dormir=lambda _s: None)
        assert not [m for m in journal if "[ALARME]" in m and "EN VOL" in m]

    def test_l_alarme_ne_touche_a_rien(self, deux_phases, journal):
        """Elle journalise. Elle ne reprend pas, ne déclare pas en échec, ne saute pas."""
        self._pause_humaine_ancienne(deux_phases, "t1")
        C.lancer("c", max_tours=4, dormir=lambda _s: None)
        assert deux_phases["lances"] == []
        assert C.lire_etat("c")["echouees"] == {}

    def test_une_experience_qui_dort_sur_son_quota_n_alarme_pas(self, deux_phases, journal):
        """Son état ne bouge pas non plus — mais c'est une attente comprise, déjà dite.

        Le sommeil de lot la consigne, et l'alarme des 26 h la couvre. En alarmer ici ferait
        passer une attente normale pour une anomalie.
        """
        vieux = (
            datetime.now(timezone.utc) - timedelta(seconds=C.EN_VOL_FIGE_S + 600)
        ).isoformat()
        _poser_etat(deux_phases["experiences"], "t1", "en_attente_quota", maj=vieux)
        C.lancer("c", max_tours=3, dormir=lambda _s: None)
        assert not [m for m in journal if "[ALARME]" in m and "EN VOL" in m]


# ── 5. Une seule campagne à la fois ──────────────────────────────────────────


class TestDoubleLancement:
    """Le 2026-09-16, deux `campagne-lancer bascule_anglaise_v6` ont tourné en parallèle
    vingt minutes durant : ils ont écrit le même `etat.json` chacun leur tour, marqué deux
    bras « arrêt demandé », et déclaré la campagne terminée avec un bras jamais lancé."""

    @staticmethod
    def _dire_que_le_pid_tourne(monkeypatch, ligne: str | None) -> None:
        monkeypatch.setattr(C, "_ligne_de_commande", lambda pid: ligne)

    def test_un_second_lancement_REFUSE_et_ne_touche_a_rien(
        self, deux_phases, monkeypatch, journal
    ):
        C.lancer("c", max_tours=1, dormir=lambda _s: None)
        avant = C.lire_etat("c")
        # Le premier processus n'est plus celui qui appelle : on lui donne un pid d'emprunt,
        # et on dit que ce pid porte bien une ligne de commande de campagne.
        avant["pid"] = os.getpid() + 1
        C.ecrire_etat("c", avant)
        self._dire_que_le_pid_tourne(
            monkeypatch, "python -m experiences campagne-lancer --nom c")

        deux_phases["lances"].clear()
        assert C.lancer("c", max_tours=5, dormir=lambda _s: None) == C.CODE_DEJA_EN_VOL
        assert deux_phases["lances"] == []
        alarme = [l for l in journal if "[ALARME]" in l and "TOURNE DÉJÀ" in l]
        assert alarme, journal
        # Elle dit AUSSI quoi faire : constater, ou arrêter celle qui tourne.
        assert "campagne-etat" in alarme[0] and "campagne-arreter" in alarme[0]

    def test_le_refus_ne_LEVE_PAS_le_drapeau_d_arret_du_premier(
        self, deux_phases, monkeypatch
    ):
        C.lancer("c", max_tours=1, dormir=lambda _s: None)
        etat = C.lire_etat("c")
        etat["pid"] = os.getpid() + 1
        C.ecrire_etat("c", etat)
        C.arreter("c")
        self._dire_que_le_pid_tourne(monkeypatch, "campagne-lancer --nom c")

        C.lancer("c", max_tours=5, dormir=lambda _s: None)
        assert C.demande_arret("c"), "le second lancement a effacé le STOP du premier"

    def test_un_pid_MORT_ne_bloque_pas_la_reprise(self, deux_phases, monkeypatch):
        C.lancer("c", max_tours=1, dormir=lambda _s: None)
        etat = C.lire_etat("c")
        etat["pid"] = os.getpid() + 1
        C.ecrire_etat("c", etat)
        self._dire_que_le_pid_tourne(monkeypatch, None)  # `ps` ne connaît plus ce pid

        deux_phases["lances"].clear()
        C.lancer("c", max_tours=3, dormir=lambda _s: None)
        assert deux_phases["lances"], "une campagne morte doit pouvoir reprendre"

    def test_un_pid_RECYCLE_ne_bloque_pas_non_plus(self, deux_phases, monkeypatch):
        C.lancer("c", max_tours=1, dormir=lambda _s: None)
        etat = C.lire_etat("c")
        etat["pid"] = os.getpid() + 1
        C.ecrire_etat("c", etat)
        # Même pid, mais ce n'est plus une campagne : le système l'a réattribué.
        self._dire_que_le_pid_tourne(monkeypatch, "/usr/bin/vim notes.md")

        deux_phases["lances"].clear()
        C.lancer("c", max_tours=3, dormir=lambda _s: None)
        assert deux_phases["lances"]

    def test_une_AUTRE_campagne_en_vol_ne_bloque_pas_celle_ci(self, deux_phases, monkeypatch):
        C.lancer("c", max_tours=1, dormir=lambda _s: None)
        etat = C.lire_etat("c")
        etat["pid"] = os.getpid() + 1
        C.ecrire_etat("c", etat)
        self._dire_que_le_pid_tourne(monkeypatch, "campagne-lancer --nom une_autre")

        deux_phases["lances"].clear()
        C.lancer("c", max_tours=3, dormir=lambda _s: None)
        assert deux_phases["lances"]

    def test_un_ps_MUET_laisse_passer_plutot_que_de_bloquer(self, deux_phases, monkeypatch):
        """Fail-open : un `ps` en erreur ne doit pas empêcher une campagne de démarrer."""
        def _ps_casse(*_a, **_k):
            raise OSError("ps introuvable")
        monkeypatch.setattr(C.subprocess, "run", _ps_casse)
        C.lancer("c", max_tours=1, dormir=lambda _s: None)
        etat = C.lire_etat("c")
        etat["pid"] = os.getpid() + 1
        C.ecrire_etat("c", etat)

        deux_phases["lances"].clear()
        C.lancer("c", max_tours=3, dormir=lambda _s: None)
        assert deux_phases["lances"]


# ── Refus de lancement : une pénurie de quota n'est pas une panne (2026-09-17) ──────────


class TestRefusDeLancement:
    """Le lanceur refuse parfois de créer l'exécution. La campagne doit savoir POURQUOI.

    Le 2026-09-16, quatre bras ont été déclarés « lancée 3 fois sans jamais écrire d'état »
    alors que leur seul tort était d'attendre le renouvellement d'un quota. La campagne lance
    en tâche de fond : elle ne lit ni la sortie du lanceur ni son code de retour. Le marqueur
    déposé à côté du journal de lancement est le seul canal qui reste.
    """

    def _marqueur(self, racine, nom, classe, motifs):
        base = racine / nom / "lancements"
        base.mkdir(parents=True, exist_ok=True)
        (base / f"2026-09-17_10_00_00{C.REFUS.SUFFIXE_MARQUEUR}").write_text(
            json.dumps({"classe": classe,
                        "reportable": C.REFUS.est_reportable(classe),
                        "motifs": motifs, "le": "2026-09-17T10:00:00+00:00"},
                       ensure_ascii=False),
            encoding="utf-8")

    def test_penurie_de_quota_reporte_sans_decompter_de_tentative(
        self, deux_phases, monkeypatch
    ):
        monkeypatch.setattr(C, "DELAI_ECRITURE_ETAT_S", 0.0)
        self._marqueur(deux_phases["experiences"], "t1", C.REFUS.QUOTA_EPUISE,
                       ["les 2 instance(s) qui servent 'x' sont momentanément épuisées"])
        C.lancer("c", max_tours=3, dormir=lambda _s: None)
        etat = C.lire_etat("c")
        assert "t1" in etat["reportees"], "une pénurie de quota se REPORTE"
        assert "t1" not in etat["echouees"], "et ne compte pas comme une panne"
        assert "momentanément épuisées" in etat["reportees"]["t1"]["motif"], (
            "le motif du lanceur doit survivre jusqu'à l'état de campagne"
        )

    def test_charge_hors_quota_echoue_en_disant_pourquoi(self, deux_phases, monkeypatch):
        """Attendre ne résout pas une charge supérieure au quota journalier : c'est un échec,
        mais un échec qui nomme sa cause au lieu de parler d'état jamais écrit."""
        monkeypatch.setattr(C, "DELAI_ECRITURE_ETAT_S", 0.0)
        self._marqueur(deux_phases["experiences"], "t1", C.REFUS.QUOTA_INSUFFISANT,
                       ["quota journalier hors d'atteinte : ~10 jours de quota"])
        C.lancer("c", max_tours=3, dormir=lambda _s: None)
        etat = C.lire_etat("c")
        assert "t1" in etat["echouees"]
        assert "t1" not in etat["reportees"], "reporter serait une boucle sans fin"
        motif = etat["echouees"]["t1"]["motif"]
        assert "hors d'atteinte" in motif and "sans jamais écrire" not in motif

    def test_sans_marqueur_le_comportement_ne_change_pas(self, deux_phases, monkeypatch):
        """Non-régression : un lancement muet reste une panne après TENTATIVES_MAX."""
        monkeypatch.setattr(C, "DELAI_ECRITURE_ETAT_S", 0.0)
        C.lancer("c", max_tours=20, dormir=lambda _s: None)
        etat = C.lire_etat("c")
        assert "t1" in etat["echouees"]
        assert "sans jamais écrire d'état" in etat["echouees"]["t1"]["motif"]

    def test_un_marqueur_perime_est_ignore(self, deux_phases, monkeypatch):
        """Un marqueur d'hier ne dit rien du lancement d'aujourd'hui : s'il est antérieur au
        dernier journal de lancement, il ne compte pas."""
        monkeypatch.setattr(C, "DELAI_ECRITURE_ETAT_S", 0.0)
        self._marqueur(deux_phases["experiences"], "t1", C.REFUS.QUOTA_EPUISE,
                       ["momentanément épuisées"])
        base = deux_phases["experiences"] / "t1" / "lancements"
        (base / "2026-09-18_09_00_00.log").write_text("lancement postérieur\n", encoding="utf-8")
        C.lancer("c", max_tours=20, dormir=lambda _s: None)
        etat = C.lire_etat("c")
        assert "t1" not in etat["reportees"], "le marqueur est plus vieux que le journal"
        assert "t1" in etat["echouees"]


class TestClassementDesRefus:
    def test_les_trois_classes(self):
        from experiences import refus as R
        assert R.classer(["… sont momentanément épuisées — …"]) == R.QUOTA_EPUISE
        assert R.classer(["quota journalier hors d'atteinte : ~10 jours de quota"]) == R.QUOTA_INSUFFISANT
        assert R.classer(["jeu périmé"]) == R.DEFINITIF
        assert R.classer([]) == R.DEFINITIF

    def test_le_plus_grave_l_emporte(self):
        """Un refus définitif accompagné d'une pénurie reste définitif : attendre ne le lève pas."""
        from experiences import refus as R
        assert R.classer(["momentanément épuisées", "jeu périmé"]) == R.DEFINITIF
        assert R.est_reportable(R.QUOTA_EPUISE) is True
        assert R.est_reportable(R.QUOTA_INSUFFISANT) is False
