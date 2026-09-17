"""Ticket 081 — un journal tronqué ne produit jamais de score, et une reprise le régénère.

Ce que ces tests verrouillent tient en une phrase : `moves.csv` est le SUBSTRAT du composite,
et personne ne comparait jamais son compte à celui des décisions archivées. L'exécution
`2026-09-12_11_24_28` a donc été publiée à 5,35 de composite sur 274 lignes quand son archive
en portait 3 299 — le chiffre a traversé trois documents avant d'être reconnu faux. Rescorée
sur le journal reconstitué, elle vaut 6,17.

Les deux moitiés du remède se testent séparément, parce qu'elles échouent séparément :

- le SCOREUR refuse (R24) — même régénération oubliée, aucun chiffre ne sort d'un journal
  incomplet ; c'est la garde qui tient quoi qu'il arrive ailleurs ;
- la REPRISE régénère — le journal redevient complet, donc le score redevient possible.

Le seuil (2 %) n'est pas un réglage d'humeur. Balayage des 38 exécutions du dépôt le
2026-09-15 : une exécution saine porte 3 161 lignes pour 3 151 à 3 155 décidées, soit un
déficit TOUJOURS négatif (le journal porte en plus les lignes `sans_solution`, que `decides`
exclut) ; l'exécution fautive est à +91,3 %. Les deux régimes sont séparés d'un facteur 45.
"""

import asyncio
import csv
import json
import shutil
from pathlib import Path

import pytest
from experiences import formule as F
from experiences import journal as JN
from experiences import score as S
from experiences.archive import METHODE_INEXPLOITABLE, METHODE_NON_COUVERT

# Le banc synthétique du ticket 035 : population scellée, jeu clos, racines isolées. Importé
# tel quel — un second banc dériverait du premier sans que rien ne le dise.
from tests.test_035_03_05_06_execution import (  # noqa: F401
    _exp,
    _lancer,
    banc,
    sans_anticipation,
)

REPO = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.usefixtures("sans_anticipation")


# ── Substrat réel : une exécution terminée du dépôt ──────────────────────────


def _exec_reelle() -> Path | None:
    """Une exécution terminée, complète, avec son archive de décisions et son score.

    Pointée en dur, la référence disparaîtrait avec l'expérience qui la porte. On exige
    `decisions.jsonl` : sans lui, la régénération n'a rien à relire et les tests de fidélité
    passeraient en ne mesurant rien.
    """
    racine = REPO / "data" / "experiences"
    for d in JN.executions(racine):
        if not (d / "decisions.jsonl").is_file() or not (d / "scores.json").is_file():
            continue
        constat = JN.verifier(d)
        if constat["etat"] == "terminee" and constat["complet"] is True:
            return d
    return None


EXEC_REELLE = _exec_reelle()

sans_substrat = pytest.mark.skipif(
    EXEC_REELLE is None,
    reason="aucune exécution terminée, complète et archivée dans data/experiences",
)


@pytest.fixture
def copie_reelle(tmp_path):
    dst = tmp_path / EXEC_REELLE.name
    shutil.copytree(EXEC_REELLE, dst)
    return dst


@pytest.fixture(scope="module")
def registre():
    return F.charger()


def _lignes(chemin: Path) -> list[dict]:
    with Path(chemin).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _tronquer(dossier: Path, fraction: float) -> int:
    """Ne garde que `fraction` des lignes du journal, en-tête conservé. Rend le compte gardé."""
    chemin = dossier / "moves.csv"
    lignes = _lignes(chemin)
    gardees = lignes[: max(1, int(len(lignes) * fraction))]
    with chemin.open("w", encoding="utf-8", newline="") as fh:
        redacteur = csv.DictWriter(fh, fieldnames=list(lignes[0].keys()))
        redacteur.writeheader()
        redacteur.writerows(gardees)
    return len(gardees)


@pytest.fixture(autouse=True)
def alarme_desarmee():
    """Le front montant est un état de PROCESSUS : deux tests le partageraient sinon.

    Sans ce nettoyage, le test du front montant passerait ou non selon l'ordre d'exécution —
    une garde verte pour une mauvaise raison, ce que ce ticket combat précisément.
    """
    S._JOURNAUX_SIGNALES.clear()
    yield
    S._JOURNAUX_SIGNALES.clear()


# ═══════════ Lot A — le scoreur refuse un journal incomplet (R24) ═══════════


@sans_substrat
def test_un_journal_tronque_a_10_pour_cent_ne_produit_aucun_score(
    copie_reelle, registre
):
    """Pas de `scores.json`, et le refus est une exception nommée — pas un score approché."""
    (copie_reelle / "scores.json").unlink(missing_ok=True)
    garde = _tronquer(copie_reelle, 0.10)
    with pytest.raises(S.JournalIncomplet) as exc:
        S.calculer(copie_reelle, registre.reference)
    assert str(garde) in str(exc.value), "le refus doit citer le compte du journal"
    assert S.score_execution(copie_reelle, registre.reference, registre) is None
    assert not (copie_reelle / "scores.json").exists()


@sans_substrat
def test_l_alarme_part_une_seule_fois_par_execution(copie_reelle, registre, caplog):
    """Front montant : `score --toutes` ne doit pas rejouer la même ERROR à chaque passage.

    Une alarme répétée noie `make error` dans sa propre répétition, et c'est ce journal-là
    qu'on lit pour savoir ce qui ne va pas.
    """
    import logging

    from loguru import logger

    (copie_reelle / "scores.json").unlink(missing_ok=True)
    _tronquer(copie_reelle, 0.10)
    poste = logger.add(caplog.handler, level="ERROR", format="{message}")
    try:
        for _ in range(3):
            with pytest.raises(S.JournalIncomplet):
                S.calculer(copie_reelle, registre.reference)
    finally:
        logger.remove(poste)
    alarmes = [
        r
        for r in caplog.records
        if r.levelno >= logging.ERROR
        and "[ALARME] Journal des mouvements incomplet" in r.getMessage()
    ]
    assert len(alarmes) == 1, f"{len(alarmes)} alarmes pour 3 scorings"
    message = alarmes[0].getMessage()
    assert "274" not in message  # pas de valeur codée en dur : le message est calculé
    # L'alarme doit dire QUOI FAIRE, pas seulement que ça ne va pas : la commande y figure,
    # nommant l'exécution concernée entre le sous-commande et l'option.
    assert "python -m experiences journal" in message and "--regenerer" in message
    assert copie_reelle.name in message


@sans_substrat
def test_le_front_montant_se_rearme_quand_le_journal_redevient_complet(
    copie_reelle, registre, caplog
):
    """Un journal régénéré puis retronqué doit ré-alarmer : sinon la garde s'use à l'usage."""
    import logging

    from loguru import logger

    original = _lignes(EXEC_REELLE / "moves.csv")
    (copie_reelle / "scores.json").unlink(missing_ok=True)
    poste = logger.add(caplog.handler, level="ERROR", format="{message}")
    try:
        _tronquer(copie_reelle, 0.10)
        with pytest.raises(S.JournalIncomplet):
            S.calculer(copie_reelle, registre.reference)
        shutil.copy(EXEC_REELLE / "moves.csv", copie_reelle / "moves.csv")
        S.calculer(copie_reelle, registre.reference)  # journal complet : passe
        _tronquer(copie_reelle, 0.10)
        with pytest.raises(S.JournalIncomplet):
            S.calculer(copie_reelle, registre.reference)
    finally:
        logger.remove(poste)
    alarmes = [
        r
        for r in caplog.records
        if r.levelno >= logging.ERROR
        and "[ALARME] Journal des mouvements incomplet" in r.getMessage()
    ]
    assert len(alarmes) == 2, f"{len(alarmes)} alarmes pour deux troncatures distinctes"
    assert len(original) > 0


@sans_substrat
def test_un_score_deja_ecrit_sur_un_journal_tronque_est_invalide(
    copie_reelle, registre
):
    """Le refus ne suffit pas : le `scores.json` publié reste lisible tant qu'on ne le retire pas.

    C'est exactement ce qui s'est produit le 2026-09-12 — le composite invalide est resté sur
    le disque, servi par la page et par le tableau, pendant que la règle n'existait pas.
    """
    assert (copie_reelle / "scores.json").is_file()
    (copie_reelle / "synthese_scores.html").write_text("page", encoding="utf-8")
    _tronquer(copie_reelle, 0.10)
    assert S.score_execution(copie_reelle, registre.reference, registre) is None
    assert not (copie_reelle / "scores.json").exists()
    assert not (copie_reelle / "synthese_scores.html").exists()
    invalide = copie_reelle / "scores.invalide.json"
    assert invalide.is_file(), "l'ancien score doit rester auditable, pas disparaître"
    contenu = json.loads(invalide.read_text(encoding="utf-8"))
    assert contenu["invalide"]["motif"]
    assert contenu["composite"]["emd_jsd"] is not None


@sans_substrat
def test_un_score_sans_perimetre_verifie_est_perime(copie_reelle):
    """Sans ce critère, un score antérieur à la règle se rejouerait indéfiniment sans contrôle.

    Le rejeu hors-ligne ne relit jamais `moves.csv` : il recompose le composite depuis les
    scores bruts. Un score faux traverserait donc tous les changements de formule intact.
    """
    scores = json.loads((copie_reelle / "scores.json").read_text(encoding="utf-8"))
    scores.pop("perimetre_verifie", None)
    (copie_reelle / "scores.json").write_text(
        json.dumps(scores, ensure_ascii=False), encoding="utf-8"
    )
    assert S.scores_perimes(copie_reelle) is True


# ═══════════ Non-régression : une exécution complète se score comme avant ═══════════


def test_les_executions_completes_gardent_leur_composite_au_centieme(registre):
    """La garde ne doit rien changer à ce qui allait bien — sinon elle coûte plus qu'elle ne rapporte."""
    racine = REPO / "data" / "experiences"
    compares = 0
    for d in JN.executions(racine):
        chemin = d / "scores.json"
        if not chemin.is_file():
            continue
        ancien = json.loads(chemin.read_text(encoding="utf-8"))
        if (ancien.get("formule") or {}).get("sha256") != registre.reference.sha256:
            continue
        if ancien.get("composite", {}).get("emd_jsd") is None:
            continue
        frais = S.calculer(d, registre.reference)
        assert frais["composite"]["emd_jsd"] == pytest.approx(
            ancien["composite"]["emd_jsd"], abs=0.005
        ), d.name
        assert frais["perimetre_verifie"]["complet"] is True, d.name
        compares += 1
    if compares == 0:
        pytest.skip("aucune exécution scorée sous la formule de référence")


def test_le_seuil_laisse_passer_le_deficit_reel_des_executions_saines():
    """Le déficit d'une exécution saine est NÉGATIF, et la règle ne se déclenche jamais dessus.

    Mesuré le 2026-09-15 : de −0,19 % à −0,32 % sur 37 exécutions. Le journal porte les lignes
    `sans_solution`, que `couverture.decides` exclut ; il en a donc toujours quelques-unes de
    plus. Un seuil qui se déclencherait là rendrait le dépôt inscorable du jour au lendemain.
    """
    synthese = {"couverture": {"decides": 3154}}
    assert S.mesurer_perimetre(3161, synthese)["complet"] is True
    assert S.mesurer_perimetre(3154, synthese)["complet"] is True
    # 2 % de 3 154, soit 63 lignes de marge : la dernière ligne admise, puis la première refusée.
    assert S.mesurer_perimetre(3092, synthese)["complet"] is True
    assert S.mesurer_perimetre(3090, synthese)["complet"] is False
    assert S.mesurer_perimetre(274, synthese)["complet"] is False


def test_sans_compte_de_decisions_le_journal_n_est_pas_declare_complet():
    """Vacuité ≠ vérification. Ne rien pouvoir comparer n'est pas avoir comparé avec succès."""
    for synthese in ({}, {"couverture": {}}, {"couverture": {"decides": 0}}):
        assert S.mesurer_perimetre(3161, synthese)["complet"] is None


# ═══════════ Lot B — la reprise régénère le journal ═══════════


@sans_substrat
def test_la_regeneration_reproduit_le_journal_a_l_identique(copie_reelle, registre):
    """Colonne par colonne, sauf les deux que l'archive ne peut pas rendre.

    « Trajet » est un compteur de processus (l'ordre d'écriture dépend de l'ordonnancement des
    tâches) et « Heure de calcul » n'est pas archivée décision par décision. Tout le reste —
    persona, mode choisi, distance, distribution, options, écartées — doit être identique,
    faute de quoi la régénération fabriquerait un journal plausible mais faux.
    """
    jeu, personnes, info = _sources_reelles(copie_reelle)
    execution = JN.ouvrir(copie_reelle)
    etiquette = JN.EtiquetteDecideur.depuis_execution(execution.config)
    asyncio.run(
        JN.regenerer(execution, jeu, personnes, etiquette, info_population=info)
    )
    origine = {r["ID Trajet"]: r for r in _lignes(EXEC_REELLE / "moves.csv")}
    regenere = {r["ID Trajet"]: r for r in _lignes(copie_reelle / "moves.csv")}
    assert set(regenere) == set(origine)
    volatiles = {"Trajet", "Heure de calcul"}
    divergentes = {
        colonne
        for cle in origine
        for colonne in origine[cle]
        if colonne not in volatiles
        and (origine[cle].get(colonne) or "") != (regenere[cle].get(colonne) or "")
    }
    assert not divergentes, f"colonnes divergentes : {sorted(divergentes)}"


@sans_substrat
def test_le_journal_regenere_donne_le_meme_score_au_centieme(copie_reelle, registre):
    avant = S.calculer(EXEC_REELLE, registre.reference)
    jeu, personnes, info = _sources_reelles(copie_reelle)
    execution = JN.ouvrir(copie_reelle)
    asyncio.run(
        JN.regenerer(
            execution,
            jeu,
            personnes,
            JN.EtiquetteDecideur.depuis_execution(execution.config),
            info_population=info,
        )
    )
    apres = S.calculer(copie_reelle, registre.reference)
    for cle in ("emd_jsd", "l1", "emd_jsd_hors_choix_unique", "l1_hors_choix_unique"):
        assert apres["composite"][cle] == pytest.approx(
            avant["composite"][cle], abs=0.005
        ), cle


@sans_substrat
def test_regenerer_depuis_une_autre_cohorte_est_refuse(copie_reelle):
    """Un journal reconstruit sur la mauvaise population serait plausible, scorable, et faux.

    C'est la même famille de panne que celle du ticket : un fichier d'apparence normale dont
    rien ne dit qu'il décrit autre chose que ce qu'on croit.
    """
    jeu, personnes, info = _sources_reelles(copie_reelle)
    execution = JN.ouvrir(copie_reelle)
    empreintes = dict(execution.config.get("empreintes") or {})
    empreintes["population"] = {
        **(empreintes.get("population") or {}),
        "fichier_sha256": "0" * 64,
    }
    execution.config["empreintes"] = empreintes
    with pytest.raises(JN.JournalIrregenerable, match="population différente"):
        asyncio.run(
            JN.regenerer(
                execution,
                jeu,
                personnes,
                JN.EtiquetteDecideur.depuis_execution(execution.config),
                info_population=info,
            )
        )


def _sources_reelles(dossier: Path):
    """(jeu, personnes, info) de l'exécution réelle, ou skip si le dépôt ne les porte plus."""
    from experiences import journal as JN

    execution = JN.ouvrir(dossier)
    exp = execution.config.get("experience") or {}
    nom_jeu = (exp.get("jeu") or {}).get("nom")
    chemin_jeu = REPO / "data" / "jeux" / str(nom_jeu)
    chemin_pop = (
        REPO
        / "data"
        / "population"
        / Path(str((exp.get("population") or {}).get("chemin") or "")).name
    )
    if not chemin_jeu.is_dir() or not chemin_pop.is_dir():
        pytest.skip(f"jeu ou cohorte absents du dépôt : {nom_jeu}")
    return JN.resoudre_sources(execution, jeu=chemin_jeu, population=chemin_pop)


# ═══════════ Lot B — reprise à froid sur le banc synthétique ═══════════


def test_une_reprise_a_froid_laisse_un_journal_complet(banc, monkeypatch):  # noqa: F811
    """Le cas du ticket, rejoué de bout en bout : interruption, journal perdu, reprise.

    À la reprise, les décisions archivées sont RESSERVIES sans solliciter le décideur, et ce
    chemin n'écrivait aucune ligne de journal. On simule la perte du journal laissé par le
    processus interrompu, puis on reprend : le journal doit se retrouver complet, c'est-à-dire
    porter une ligne par décision archivée SAUF les non-couvertes et les inexploitables, qui
    n'ont ni mode choisi ni distance à inscrire.
    """
    from experiences.decideurs import DecideurDureeMinimale
    from experiences.runner import Controle

    exp = _exp(banc, regroupement={"parallelisme": 1})

    class PauseApres(DecideurDureeMinimale):
        nom = "duree_minimale"
        sans_quota = True

        def __init__(self, controle, apres):
            self.controle, self.apres, self.appels = controle, apres, 0

        async def choisir(self, person, ctx, presentees):
            self.appels += 1
            if self.appels >= self.apres:
                self.controle.pause = True
            return await super().choisir(person, ctx, presentees)

    from experiences.archive import Execution

    _, execution = _lancer(banc, exp)  # première exécution, complète
    total_attendu = sum(
        1
        for t in execution.decisions
        if t.get("methode") not in (METHODE_NON_COUVERT, METHODE_INEXPLOITABLE)
    )
    assert total_attendu > 0
    execution.fermer()

    # Le processus interrompu a emporté son journal : c'est la situation du 2026-09-12, où
    # `moves.csv` ne portait plus qu'une fraction des décisions archivées.
    (execution.dossier / "moves.csv").unlink()
    rouverte = Execution.ouvrir(execution.dossier)
    assert len(rouverte.decisions) > 0, (
        "la reprise doit avoir des décisions à resservir"
    )

    compteurs, _ = _lancer(banc, exp, execution=rouverte)
    assert compteurs["resservies"] == len(rouverte.decisions)
    assert compteurs["sollicitations"] == 0, "une reprise complète ne sollicite rien"

    lignes = _lignes(execution.dossier / "moves.csv")
    assert len(lignes) == total_attendu, (
        f"{len(lignes)} ligne(s) de journal pour {total_attendu} décision(s) "
        f"exploitables — une reprise doit laisser un journal complet"
    )
    assert Controle  # le harnais d'interruption reste importable (garde de refactor)


def test_le_journal_regenere_a_la_reprise_est_scorable(banc):  # noqa: F811
    """La boucle se referme : journal complet → la règle R24 laisse passer le score.

    Sans cette vérification, on pourrait régénérer un journal que le garde-fou refuserait
    quand même, et la reprise resterait inutilisable pour la mesure.
    """
    from experiences.archive import Execution

    exp = _exp(banc, regroupement={"parallelisme": 1})
    _, execution = _lancer(banc, exp)
    execution.fermer()
    (execution.dossier / "moves.csv").unlink()
    rouverte = Execution.ouvrir(execution.dossier)
    _lancer(banc, exp, execution=rouverte)

    synthese = json.loads(
        (execution.dossier / "synthese.json").read_text(encoding="utf-8")
    )
    lignes = len(_lignes(execution.dossier / "moves.csv"))
    constat = S.mesurer_perimetre(lignes, synthese)
    assert constat["complet"] is True, constat


# ═══════════ Prérequis du lot C — relire une cohorte d'avant la bascule ═══════════
#
# Découvert en régénérant l'exécution du 12/09 : le journal reconstruit s'arrêtait à 1 158
# lignes sur 3 161, avec 2 003 décisions « sans persona ». Le chargeur rejetait 637 personas
# sur 1 000 en « zone inconnue (1ere couronne) » — la cohorte v5 gelée porte les libellés
# d'avant la bascule anglaise (ticket 074), et le filtre n'admettait que le canon anglais.
# `charger_population` annonce pourtant « sans filtre de périmètre » : l'appelant recevait
# 363 personnes en croyant les avoir toutes.


def _persona(zone):
    """Un persona minimal qui ne porte que ce que le verdict de périmètre regarde."""
    from types import SimpleNamespace

    return SimpleNamespace(
        identity=SimpleNamespace(
            home=SimpleNamespace(lon=1.44, lat=43.60),
            traits_json={"residence_zone": zone} if zone else {},
        )
    )


@pytest.mark.parametrize(
    "fr, en",
    [
        ("1ere couronne", "1st ring"),
        ("2eme couronne", "2nd ring"),
        ("3eme couronne", "3rd ring"),
        ("Toulouse", "Toulouse"),
    ],
)
def test_une_couronne_d_avant_la_bascule_est_admise_comme_sa_traduction(fr, en):
    from inputs.population.eqasim_loader import perimeter_verdict

    assert perimeter_verdict(_persona(fr), None)[0] is True, fr
    assert perimeter_verdict(_persona(en), None)[0] is True, en


def test_hors_perimetre_reste_rejete_et_garde_son_nom():
    """Rejeté, mais NOMMÉ : hors périmètre est une modalité de l'enquête, pas une valeur illisible.

    Les confondre masquerait une cohorte mal traduite derrière un rejet légitime — et c'est
    justement ce qui rendait la panne invisible : 637 rejets « zone inconnue » se lisaient
    comme un filtrage normal.
    """
    from inputs.population.eqasim_loader import perimeter_verdict

    for libelle in ("hors périmètre", "outside perimeter"):
        admis, motif = perimeter_verdict(_persona(libelle), None)
        assert admis is False
        assert motif == "outside perimeter", libelle


def test_une_modalite_vraiment_inconnue_reste_rejetee_et_se_nomme():
    from inputs.population.eqasim_loader import perimeter_verdict

    admis, motif = perimeter_verdict(_persona("4eme couronne"), None)
    assert admis is False
    assert "4eme couronne" in motif
