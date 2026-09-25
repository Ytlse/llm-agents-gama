"""L'orchestrateur de cohorte sait jouer un AUTRE événement que c6 — campagne du 2026-09-22.

Jusqu'ici `CHOC_REFERENCE = "c6_voiture_suspecte"` était en dur : la cohorte ne savait jouer
que le cas d'étude du ticket 077. La campagne d'attribution de `c3_panne_reseau` demandait donc
soit d'éditer le script, soit de renoncer.

Le point le plus délicat n'est pas le paramètre mais la RÈGLE D'EXPOSITION : la dérivation par
persona écrivait `exposition.agents` sans toucher à `regle`. Sur c6, déjà en `regle: agents`,
cela marchait. Sur c3 (`regle: mode`) la liste aurait été écrite, acceptée et ignorée — et sur
une population d'un habitant le résultat aurait été le bon PAR ACCIDENT. C'est ce que ces tests
ferment.
"""

import sys
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / "scripts" / "experiment"))

import run_sequential_cohort as cohorte  # noqa: E402


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    """Redirige les deux répertoires de déclaration : aucun test n'écrit dans le dépôt."""
    evenements, chocs = tmp_path / "evenements", tmp_path / "chocs"
    evenements.mkdir()
    chocs.mkdir()
    monkeypatch.setattr(cohorte, "EVENEMENTS_DIR", evenements)
    monkeypatch.setattr(cohorte, "CHOCS_DIR", chocs)
    return evenements, chocs


def _ecrire(dossier: Path, nom: str, exposition: dict) -> None:
    (dossier / f"{nom}.yaml").write_text(
        yaml.safe_dump(
            {"evenement": nom, "canal": "vecu", "moment": "arrivee", "jugement": "a_l_injection",
             "libelle": "T", "source": "test", "exposition": exposition,
             "jours": [{"jour": 12, "retard_min": 28, "vecu": "Something happened."}]},
            allow_unicode=True, sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_la_regle_mode_devient_agents_et_les_modes_survivent(dirs):
    """Le cas c3 : `regle: mode` + `modes` → `regle: agents` + `agents` + les MÊMES modes.

    Garder les modes n'est pas cosmétique : la branche `agents` les lit et restreint l'agent
    désigné à ces trajets-là. Sans eux, 861500 lirait « le métro s'est arrêté » au volant de sa
    voiture — exactement le défaut que c6 avait payé sur Corinne.
    """
    evenements, _ = dirs
    _ecrire(evenements, "c3_panne_reseau", {"regle": "mode", "modes": ["public_transport"]})

    nom = cohorte.choc_pour_persona("861500", "c3_panne_reseau")

    assert nom == "c3_panne_reseau__861500"
    produit = yaml.safe_load((evenements / f"{nom}.yaml").read_text(encoding="utf-8"))
    assert produit["exposition"]["regle"] == "agents"
    assert produit["exposition"]["agents"] == ["861500"]
    assert produit["exposition"]["modes"] == ["public_transport"]


def test_les_parametres_du_tirage_ne_survivent_pas(dirs):
    """Le cas c2 : `part` et `graine` n'ont aucun sens sous `regle: agents`.

    Un paramètre accepté et sans effet est pire qu'un paramètre refusé : rien ne le signale.
    """
    evenements, _ = dirs
    _ecrire(evenements, "c2_crevaison", {"regle": "tirage", "part": 0.30, "graine": 79})

    nom = cohorte.choc_pour_persona("861500", "c2_crevaison")

    expo = yaml.safe_load((evenements / f"{nom}.yaml").read_text(encoding="utf-8"))["exposition"]
    assert expo == {"regle": "agents", "agents": ["861500"]}


def test_le_defaut_reste_c6_et_le_comportement_d_hier_ne_bouge_pas(dirs):
    """Sans `--evenement`, la commande du ticket 077 doit rendre le même run qu'avant."""
    evenements, _ = dirs
    _ecrire(evenements, "c6_voiture_suspecte", {"regle": "agents", "modes": ["car"]})

    assert cohorte.CHOC_REFERENCE == "c6_voiture_suspecte"
    assert cohorte.nom_choc_derive("899549") == "c6_voiture_suspecte__899549"
    assert cohorte.choc_pour_persona("899549") == "c6_voiture_suspecte__899549"


def test_le_repertoire_herite_est_lu_en_second(dirs):
    """Les cinq cas du 079 vivent encore dans config/chocs/ : ils restent jouables."""
    evenements, chocs = dirs
    _ecrire(chocs, "c4_train_supprime", {"regle": "mode", "modes": ["train"]})

    assert cohorte.source_evenement("c4_train_supprime") == chocs / "c4_train_supprime.yaml"
    # …mais le dérivé part dans le canonique, celui que le Makefile préfère.
    cohorte.choc_pour_persona("861500", "c4_train_supprime")
    assert (evenements / "c4_train_supprime__861500.yaml").is_file()
    assert not (chocs / "c4_train_supprime__861500.yaml").exists()


def test_le_canonique_prime_sur_l_herite(dirs):
    """Le même nom des deux côtés : c'est config/evenements/ qui décide."""
    evenements, chocs = dirs
    _ecrire(evenements, "c3_panne_reseau", {"regle": "mode", "modes": ["public_transport"]})
    _ecrire(chocs, "c3_panne_reseau", {"regle": "mode", "modes": ["train"]})

    assert cohorte.source_evenement("c3_panne_reseau") == evenements / "c3_panne_reseau.yaml"


def test_un_evenement_inconnu_dit_ce_qui_existe(dirs):
    """Six heures de run ne se perdent pas sur une faute de frappe : l'erreur liste les cas."""
    evenements, _ = dirs
    _ecrire(evenements, "c3_panne_reseau", {"regle": "mode", "modes": ["public_transport"]})

    with pytest.raises(FileNotFoundError) as exc:
        cohorte.source_evenement("c3_panne_resau")

    assert "c3_panne_reseau" in str(exc.value), "l'erreur doit montrer le nom correct"


# ══ Le battement d'avancement (2026-09-22, pendant la campagne c3) ═══════════════════════════


def test_le_battement_distingue_l_amorcage_d_un_blocage(tmp_path):
    """« ? » se lit comme une panne. Sur six heures de run, c'est la seule question qui compte.

    `[sync] END` n'arrive qu'une fois la boucle démarrée ; l'amorçage — peuplement, itinéraires
    initiaux, d'autant plus long que le cache OSMnx est froid — n'en produit aucun.
    """
    journal = tmp_path / "app.log"

    journal.write_text(
        "INFO | simulation_controller - [bootstrap] pre-computing 1 act[N+3] itineraries (wave 3)...\n",
        encoding="utf-8",
    )
    assert cohorte.derniere_journee_simulee(tmp_path).startswith("amorçage — pre-computing")

    # Dès qu'un cycle est bouclé, c'est la journée simulée qui prime sur l'amorçage.
    with open(journal, "a", encoding="utf-8") as f:
        f.write("INFO | [sync] END sim_time=20 March 2026, 05:00 state_update_duration=0.003s\n")
    assert cohorte.derniere_journee_simulee(tmp_path) == "20 March 2026, 05:00"


def test_le_battement_nomme_l_absence_de_journal(tmp_path):
    """Un répertoire sans app.log n'est pas un run bloqué : c'est un run qui n'a pas commencé."""
    assert cohorte.derniere_journee_simulee(tmp_path) == "journal pas encore écrit"
    assert cohorte.derniere_journee_simulee(None) == "?"


# ══ Qui a produit ce bras (2026-09-22) ═══════════════════════════════════════════════════════


@pytest.fixture
def journal():
    """Capture la sortie loguru — `caplog` de pytest ne la voit pas, loguru n'étant pas logging."""
    from loguru import logger

    lignes: list[str] = []
    jeton = logger.add(lignes.append, level="DEBUG", format="{level} {message}")
    yield lignes
    logger.remove(jeton)


def test_le_lanceur_dit_quels_modeles_servent_le_bras(tmp_path, journal):
    """Un bras dont on ne sait pas qui l'a produit ne se compare à rien.

    La restriction d'instances est déclarée par catégorie dans docker-compose et n'apparaissait
    nulle part dans la sortie du lanceur. Le 2026-09-22 cela a valu une annonce fausse — « le
    pool complet » — pendant que le run tournait sur deux clés d'un seul modèle.
    """
    import json as _json

    (tmp_path / "identite_run.json").write_text(
        _json.dumps({
            "modeles_admis": ["gemini-3.1-flash-lite"],
            "routage_instances": {"itinary_multi_agent": ["google_gemini31_key1"]},
        }),
        encoding="utf-8",
    )
    cohorte.journaliser_qui_sert("861500", "treated", tmp_path)

    sortie = "".join(journal)
    assert "gemini-3.1-flash-lite" in sortie
    assert "itinary_multi_agent" in sortie and "google_gemini31_key1" in sortie


def test_une_identite_illisible_se_signale_au_lieu_de_se_taire(tmp_path, journal):
    """Le silence se lit comme « aucune restriction », qui est l'inverse du cas dangereux."""
    cohorte.journaliser_qui_sert("861500", "treated", tmp_path)
    assert "identite_run.json absent" in "".join(journal)

    journal.clear()
    (tmp_path / "identite_run.json").write_text("{ pas du json", encoding="utf-8")
    cohorte.journaliser_qui_sert("861500", "treated", tmp_path)
    assert "illisible" in "".join(journal)


# ══ Résolution de population scellée et détection d'échec (Ticket 109) ══════════════════════


def test_resoudre_population_unitaire_vs_scellee():
    """Un persona 861500 pointe vers population_1_861500 (n=1), une population 20 foyers pointe vers son dossier (n=20)."""
    pop_path, pop_size, is_dataset, ids = cohorte.resoudre_population_et_taille("861500")
    assert pop_path == "/data/eqasim-output/population_1_861500/population.json"
    assert pop_size == 1
    assert is_dataset is False
    assert ids == ["861500"]

    pop_path_20, pop_size_20, is_dataset_20, ids_20 = cohorte.resoudre_population_et_taille("population_20_foyers_059")
    assert pop_path_20 == "/data/eqasim-output/population_20_foyers_059/population.json"
    assert pop_size_20 == 20
    assert is_dataset_20 is True
    assert len(ids_20) == 20


def test_choc_conserve_regle_foyers_pour_population_scellee(dirs):
    """Pour une population scellée avec événement à règle 'foyers', la règle 'foyers' n'est pas écrasée en 'agents'."""
    evenements, _ = dirs
    _ecrire(
        evenements,
        "a07_greve_eboueurs",
        {
            "regle": "foyers",
            "foyers": ["605813", "234839"],
            "lecteurs_par_foyer": 1,
            "graine": 59,
        },
    )

    nom = cohorte.choc_pour_persona("population_20_foyers_059", "a07_greve_eboueurs")
    assert nom == "a07_greve_eboueurs__population_20_foyers_059"

    produit = yaml.safe_load((evenements / f"{nom}.yaml").read_text(encoding="utf-8"))
    assert produit["exposition"]["regle"] == "foyers"
    assert produit["exposition"]["foyers"] == ["605813", "234839"]
    assert "agents" not in produit["exposition"]


def test_le_battement_detecte_echec_initialisation(tmp_path):
    """Si app.log contient une alarme de population scellée introuvable, le battement ne reste pas sur 'amorçage'."""
    journal = tmp_path / "app.log"
    journal.write_text(
        "INFO | handle.application - INITIALISATION 1/5 Préparation de la population — sim_time=16 March 2026, 05:00\n"
        "ERROR | handle.application - [ALARME] [population] Population scellée introuvable : /data/eqasim-output/foo.json\n",
        encoding="utf-8",
    )
    resultat = cohorte.derniere_journee_simulee(tmp_path)
    assert "échec initialisation" in resultat



# ── Population scellée : la résolution ne dépend ni du répertoire courant, ni de la chance ──


def test_la_resolution_ne_depend_pas_du_repertoire_courant(tmp_path, monkeypatch):
    """Lancée depuis un autre dossier, la première version ne trouvait plus le jeu, retombait sur
    le cas unitaire, et le bras exposait un « agent » nommé comme la population : personne."""
    monkeypatch.chdir(tmp_path)
    _, taille, est_un_jeu, ids = cohorte.resoudre_population_et_taille("population_20_foyers_059")
    assert (taille, est_un_jeu, len(ids)) == (20, True, 20)


def test_une_population_nommee_introuvable_est_refusee(tmp_path, monkeypatch):
    """Un nom non numérique sans dossier n'a pas de repli : il n'y a personne à y exposer."""
    monkeypatch.setattr(cohorte, "POPULATIONS_DIR", tmp_path)
    with pytest.raises(cohorte.PopulationIntrouvable):
        cohorte.resoudre_population_et_taille("population_20_foyers_inexistante")


def test_un_identifiant_numerique_sans_dossier_garde_le_repli_unitaire(tmp_path, monkeypatch):
    monkeypatch.setattr(cohorte, "POPULATIONS_DIR", tmp_path)
    chemin, taille, est_un_jeu, ids = cohorte.resoudre_population_et_taille("123456")
    assert chemin == "/data/eqasim-output/population_1_123456/population.json"
    assert (taille, est_un_jeu, ids) == (1, False, ["123456"])


def test_un_fichier_de_population_illisible_est_refuse(tmp_path, monkeypatch):
    monkeypatch.setattr(cohorte, "POPULATIONS_DIR", tmp_path)
    (tmp_path / "population_casse").mkdir()
    (tmp_path / "population_casse" / "population.json").write_text("{pas du json", encoding="utf-8")
    with pytest.raises(cohorte.PopulationIntrouvable):
        cohorte.resoudre_population_et_taille("population_casse")


def test_sur_un_jeu_la_regle_mode_est_refusee(dirs):
    """Réécrite en `agents`, elle désignerait le nom de la population comme habitant."""
    evenements, _ = dirs
    _ecrire(evenements, "c3_panne_reseau", {"regle": "mode", "modes": ["public_transport"]})
    with pytest.raises(ValueError, match="regle: mode"):
        cohorte.choc_pour_persona("population_20_foyers_059", "c3_panne_reseau")


def test_sur_un_jeu_des_agents_tous_absents_sont_refuses(dirs):
    evenements, _ = dirs
    _ecrire(evenements, "c6_voiture_suspecte", {"regle": "agents", "agents": ["999999999"]})
    with pytest.raises(ValueError, match="AUCUN"):
        cohorte.choc_pour_persona("population_20_foyers_059", "c6_voiture_suspecte")


def test_le_delai_de_garde_suit_le_volume():
    """Six heures pour un habitant ; vingt habitants sur quinze jours en demandent davantage."""
    assert cohorte.delai_de_garde(1, 42) == cohorte.ATTENTE_RUN_S
    assert cohorte.delai_de_garde(20, 15) == 20 * 15 * cohorte.DELAI_PAR_AGENT_JOUR_S
    assert cohorte.delai_de_garde(20, 15) > cohorte.ATTENTE_RUN_S


@pytest.mark.parametrize("brut, attendu", [("true", True), ("1", True), ("false", False)])
def test_le_partage_du_foyer_est_verifie_dans_l_identite(brut, attendu):
    """Posé par l'orchestrateur, il doit se retrouver dans `identite_run.json` — sinon le
    conteneur ne l'a pas reçu et le bras s'arrête au lieu de tourner sans partage."""
    attendus = cohorte.reglages_attendus({"MEMOIRE__PARTAGE_FOYER_ENABLED": brut})
    assert attendus["partage_foyer"] is attendu


# ── Option A (2026-09-24) : un bras suspendu par le garde-fou se reprend par son nom ────────
def test_un_marqueur_anterieur_au_bras_ne_le_dit_pas_suspendu(tmp_path):
    """Un bras repris rejoue dans le répertoire qui s'était arrêté : l'ancien marqueur y est."""
    import json as _json
    import os
    import time as _time

    marqueur = tmp_path / "en_attente_quota.json"
    marqueur.write_text(_json.dumps({"motif": "quota_journalier"}), encoding="utf-8")
    vieux = _time.time() - 3600
    os.utime(marqueur, (vieux, vieux))
    assert cohorte.suspension_du_run(tmp_path, depuis=_time.time()) is None
    assert cohorte.suspension_du_run(tmp_path, depuis=vieux)["motif"] == "quota_journalier"
    assert cohorte.suspension_du_run(None) is None


def test_reprise_en_attente_lit_le_nom_du_run(tmp_path):
    assert cohorte.reprise_en_attente(tmp_path) is None
    (tmp_path / cohorte.FICHIER_REPRISE).write_text('{"archive": "2026-09-24_11_14"}', encoding="utf-8")
    assert cohorte.reprise_en_attente(tmp_path)["archive"] == "2026-09-24_11_14"
    (tmp_path / cohorte.FICHIER_REPRISE).write_text("pas du json", encoding="utf-8")
    assert cohorte.reprise_en_attente(tmp_path) is None


def test_attendre_identite_en_reprise_accepte_l_identite_du_premier_depart(tmp_path, monkeypatch):
    """Ticket 091 : l'identité du run repris est ANTÉRIEURE au contrôleur — c'est le nom qui fait foi."""
    import os
    import time as _time

    archive = tmp_path / "2026-09-24_11_14"
    archive.mkdir()
    ident = archive / "identite_run.json"
    ident.write_text("{}", encoding="utf-8")
    vieux = _time.time() - 7200
    os.utime(ident, (vieux, vieux))
    monkeypatch.setattr(cohorte, "archive_du_run", lambda: archive)
    monkeypatch.setattr(cohorte.time, "sleep", lambda s: None)
    assert cohorte.attendre_identite(_time.time(), timeout_s=1, reprise="2026-09-24_11_14") == archive
    assert cohorte.attendre_identite(_time.time(), timeout_s=0.05) is None
    assert cohorte.attendre_identite(_time.time(), timeout_s=0.05, reprise="autre_run") is None


# ── 2026-09-24 : une population de foyers porte ses foyers exposés dans son MANIFEST ─────────
def _population_de_foyers(racine: Path, nom: str, foyers: list[str], exposes: list[str] | None):
    import json as _json

    d = racine / nom
    d.mkdir(parents=True)
    agents = [
        {"person_id": f"{f}{i}", "household": {"id": f}} for f in foyers for i in range(2)
    ]
    (d / "population.json").write_text(_json.dumps(agents), encoding="utf-8")
    if exposes is not None:
        (d / "MANIFEST.yaml").write_text(
            yaml.safe_dump({"groupes": {"expose": [{"household_id": f} for f in exposes]}}),
            encoding="utf-8",
        )


def test_des_foyers_declares_absents_se_prennent_au_manifeste(dirs, tmp_path, monkeypatch):
    """a09 déclare les foyers de population_20 ; sur une autre population, personne ne lirait."""
    evenements, _ = dirs
    pops = tmp_path / "population"
    monkeypatch.setattr(cohorte, "POPULATIONS_DIR", pops)
    _population_de_foyers(pops, "population_4_foyer_x", ["133048"], ["133048"])
    _ecrire(evenements, "a09_t", {"regle": "foyers", "foyers": ["605813"], "lecteurs_par_foyer": 1})

    nom = cohorte.choc_pour_persona("population_4_foyer_x", "a09_t")
    derive = yaml.safe_load((evenements / f"{nom}.yaml").read_text(encoding="utf-8"))
    assert derive["exposition"]["foyers"] == ["133048"]
    assert derive["exposition"]["lecteurs_par_foyer"] == 1


def test_des_foyers_declares_presents_restent_ceux_de_la_declaration(dirs, tmp_path, monkeypatch):
    evenements, _ = dirs
    pops = tmp_path / "population"
    monkeypatch.setattr(cohorte, "POPULATIONS_DIR", pops)
    _population_de_foyers(pops, "population_4_foyer_y", ["1", "2"], ["2"])
    _ecrire(evenements, "a09_t", {"regle": "foyers", "foyers": ["1"], "lecteurs_par_foyer": 1})
    nom = cohorte.choc_pour_persona("population_4_foyer_y", "a09_t")
    derive = yaml.safe_load((evenements / f"{nom}.yaml").read_text(encoding="utf-8"))
    assert derive["exposition"]["foyers"] == ["1"]


def test_sans_foyer_present_ni_manifeste_le_bras_est_refuse(dirs, tmp_path, monkeypatch):
    evenements, _ = dirs
    pops = tmp_path / "population"
    monkeypatch.setattr(cohorte, "POPULATIONS_DIR", pops)
    _population_de_foyers(pops, "population_4_foyer_z", ["9"], None)
    _ecrire(evenements, "a09_t", {"regle": "foyers", "foyers": ["605813"]})
    with pytest.raises(ValueError, match="sans lecteur"):
        cohorte.choc_pour_persona("population_4_foyer_z", "a09_t")
