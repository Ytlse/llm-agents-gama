"""Ticket 035, specs 03 (S), 05 (Q) et 06 (E) — exécution sans simulateur, ressources, archive.

Tout tourne sur un jeu préparé avec un moteur factice et des décideurs locaux : aucun réseau. Les
règles qui exigent la passerelle réelle (Q1 affichage des quotas, Q4 épuisement réel) sont
couvertes par un moniteur factice.
"""

import asyncio
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml
from experiences import archive as A
from experiences import decision as D
from experiences import erreurs as ERR
from experiences import experience as E
from experiences import jeu as J
from experiences import registre as R
from experiences import runner
from experiences.decideurs import (
    DecideurAleatoire,
    DecideurDureeMinimale,
    DecideurMajoritaireVoiture,
    DecideurRejeu,
)
from experiences.population import charger_population, info_population
from experiences.ressources import MoniteurRessources
from experiences.runner import Controle, executer
from loguru import logger
from tests.test_035_01_jeu import (
    HOME,
    WORK,
    MoteurFactice,
    _pas_de_locale,
    _plan,
    _population,
    _sceller,
)

pytestmark = pytest.mark.usefixtures("sans_anticipation")

# Un événement complet au format figé pour GAMA (décision 14) — accepté à la définition, refusé au lancement.
EV = {
    "type": "incident",
    "jour": 2,
    "heure_debut": "17:00",
    "heure_fin": "20:00",
    "cible": {"ligne": "metro_A"},
    "description": "Métro A interrompu entre Jean-Jaurès et Balma",
    "source": "docs/traces/…",
}


@pytest.fixture
def sans_anticipation(monkeypatch):
    from settings import settings

    monkeypatch.setattr(settings.agent, "agenda_anticipation_enabled", False)


@pytest.fixture
def banc(tmp_path, monkeypatch):
    """Population scellée + jeu clos + racines d'expériences/jeux isolées."""
    pop = tmp_path / "pop"
    pop.mkdir()
    (pop / "population.json").write_text(json.dumps(_population()), encoding="utf-8")
    _sceller(pop)
    monkeypatch.setenv("EXPERIENCES_DIR", str(tmp_path / "experiences"))
    monkeypatch.setenv("JEUX_DIR", str(tmp_path / "jeux"))
    personnes, info = charger_population(pop)
    prep = J.JeuEnPreparation.ouvrir(
        tmp_path / "jeux" / "jeu_t",
        "jeu_t",
        info,
        "2026-03-16",
        dependances={"commit": "abc"},
    )
    asyncio.run(
        J.preparer(
            prep,
            personnes,
            MoteurFactice(n_transit=2),
            fabrique_locale=_pas_de_locale,
            progression_s=100,
        )
    )
    prep.clore(J.deplacements_attendus(personnes, "2026-03-16"), len(personnes))
    return {
        "pop": pop,
        "personnes": personnes,
        "info": info,
        "jeu": J.Jeu.charger(tmp_path / "jeux" / "jeu_t"),
        "tmp": tmp_path,
    }


def _exp_dict(banc, **kw) -> dict:
    d = {
        "nom": "exp_test",
        "population": {"chemin": str(banc["pop"])},
        "jeu": {"nom": "jeu_t"},
        "gabarit": {"categorie": "itinary_multi_agent"},
        "decideur": {"type": "duree_minimale"},
        "mode": "sans_simulateur",
        "calendrier": {"politique": "commune", "date": "2026-03-16", "graine": 42},
        "horizon_jours": 1,
        "memoire": False,
        "evenements": [],
        "graine_ordre": 42,
        "graine_tirage": 42,
        "regroupement": {"parallelisme": 4},
        "tolerances_horaires": {
            "walk": "insensible",
            "bike": "insensible",
            "car": "heure",
            "transit": {"pas_min": 10},
            "rail": {"pas_min": 10},
        },
        "max_candidats": 6,
        "attente_max_s": 5,
    }
    d.update(kw)
    return d


def _exp(banc, **kw) -> E.Experience:
    p = banc["tmp"] / f"{kw.get('nom', 'exp_test')}.yaml"
    p.write_text(
        yaml.safe_dump(_exp_dict(banc, **kw), allow_unicode=True), encoding="utf-8"
    )
    return E.charger_experience(p)


def _execution(banc, exp, **kw) -> A.Execution:
    E.sauver_experience(exp)  # comme la CLI : l'expérience est rangée avant l'exécution
    return A.Execution.creer(
        exp.dossier(),
        E.experience_vers_dict(exp),
        E.empreintes(exp, banc["jeu"], banc["info"], {"commit": "abc"}),
        regime_demande={"parallelisme": exp.regroupement.parallelisme},
        sources_alea={
            "graine_ordre": 42,
            "graine_tirage": 42,
            "graine_calendrier": 42,
            "echantillonnage_decideur": False,
        },
        **kw,
    )


def _lancer(banc, exp, decideur=None, execution=None, **kw):
    execution = execution or _execution(banc, exp)
    compteurs = asyncio.run(
        executer(
            exp,
            banc["jeu"],
            banc["personnes"],
            execution,
            decideur or DecideurDureeMinimale(),
            periode_progression_s=100,
            **kw,
        )
    )
    return compteurs, execution


class DecideurCompteur(DecideurDureeMinimale):
    """Compte les sollicitations et peut demander une pause après N décisions."""

    def __init__(self, controle=None, pause_apres=None):
        self.appels, self.controle, self.pause_apres = 0, controle, pause_apres

    async def choisir(self, person, ctx, presentees):
        self.appels += 1
        if (
            self.pause_apres is not None
            and self.appels >= self.pause_apres
            and self.controle is not None
        ):
            self.controle.pause = True
        return await super().choisir(person, ctx, presentees)


# ═══════════════ Spec 03 ═══════════════


def test_S1_ordre_horaire_et_chaine(banc):
    exp = _exp(banc, regroupement={"parallelisme": 1})
    vus = []

    class Espion(DecideurDureeMinimale):
        async def choisir(self, person, ctx, presentees):
            vus.append(
                (
                    person.person_id,
                    ctx.activity_id,
                    dict(person.state.planning_vehicle_at),
                )
            )
            return await super().choisir(person, ctx, presentees)

    _, exe = _lancer(banc, exp, Espion())
    traces = {(t["person_id"], t["activity_id"]): t for t in exe.decisions}
    a1, a2 = traces[("p3", "a1")], traces[("p3", "a2")]
    # 1er déplacement : décideur sollicité, véhicules au domicile ; durée minimale = voiture.
    assert [v[1] for v in vus if v[0] == "p3"] == ["a1"] and vus[0][2] == {}
    assert a1["retenue"]["mode"] == "car"
    # 2ᵉ déplacement (retour) : la voiture dort au travail → verrou de retour → choix unique,
    # le décideur n'est PAS sollicité (D4 + D5) et l'état du 2ᵉ appel est celui laissé par le 1ᵉʳ.
    assert a2["methode"] == "choix_unique" and a2["retenue"]["mode"] == "car"
    motifs = {e["motif"] for e in a2["ecartees"]}
    assert "retour_force" in motifs and a2["contrainte_chaine"] == "retour_force"
    assert motifs <= {
        "retour_force",
        "vehicule_ailleurs",
    }  # le vélo, lui, est resté au domicile


def test_S2_non_couvert_trace_et_hors_parts(banc, tmp_path):
    exp = _exp(banc)
    exe = _execution(banc, exp)
    # on retire une ligne du jeu chargé : ce déplacement n'est plus couvert
    banc["jeu"]._index.pop(("p2", "b1"))
    compteurs, exe = _lancer(banc, exp, execution=exe)
    assert (
        compteurs["non_couverts"] == 1
        and compteurs["decides"] == 2
        and compteurs["couverture"]["taux"] == pytest.approx(2 / 3)
    )
    s = R.synthese(exe.dossier)
    assert s["parts_modales"]["n"] == 2 and s["methodes"]["non_couvert"] == 1


def test_S3_refus_memoire_evenement_horizon(banc):
    for kw in ({"memoire": True}, {"horizon_jours": 5}, {"evenements": [EV]}):
        exp = _exp(banc, **kw)
        refus, _ = E.refuser_si_impossible(
            exp, banc["jeu"], banc["info"], dependances={"commit": "abc"}, periodes={}
        )
        assert any("relèvent du mode simulateur" in r for r in refus), kw


def test_S4_regroupement_indiscernable(banc):
    e1 = _exp(banc, nom="lot1", regroupement={"parallelisme": 1})
    e10 = _exp(banc, nom="lot10", regroupement={"parallelisme": 10})
    _, x1 = _lancer(banc, e1, DecideurAleatoire(7))
    _, x10 = _lancer(banc, e10, DecideurAleatoire(7))
    cles = lambda ex: {
        (t["person_id"], t["activity_id"]): (t["retenue"] or {}).get("code")
        for t in ex.decisions
    }
    assert cles(x1) == cles(x10)
    assert x10.config["regime_applique"]["parallelisme"] == 10


def test_S6_progression_visible(banc):
    from experiences.runner import Progression

    p = Progression(attendus=100, personnes=10, deja=0)
    p.compteurs["decides"] = 71
    p.compteurs["sollicitations"] = 71
    p.attentes_par_type["quota"] = 2
    ligne = p.ligne()
    assert (
        "71/100" in ligne
        and "sollicitations 71" in ligne
        and "attentes 2" in ligne
        and "reste" in ligne
    )


def test_S7_meme_lecteur_et_validation(banc):
    exp = _exp(banc)
    _, exe = _lancer(banc, exp)
    assert A.valider_archive(exe.dossier) == []
    relu = A.Execution.ouvrir(exe.dossier)
    assert len(relu.decisions) == 3 and (exe.dossier / "moves.csv").exists()
    import csv

    with open(exe.dossier / "moves.csv", encoding="utf-8") as f:
        lignes = list(csv.DictReader(f))
    assert len(lignes) == 3 and {l["Mode de transport Choisi"] for l in lignes} <= {
        "Voiture Privée",
        "Vélo",
        "Marche",
        "Transports_collectifs",
    }


def test_S8_journal_de_succes(banc):
    exp = _exp(banc)
    messages = []
    sink = logger.add(lambda m: messages.append(str(m)), level="INFO")
    try:
        _lancer(banc, exp)
    finally:
        logger.remove(sink)
    fin = [m for m in messages if "Exécution terminée" in m]
    assert fin and all(
        k in fin[0]
        for k in (
            "décidés",
            "non couverts",
            "sans solution",
            "choix unique",
            "replis",
            "erreurs",
        )
    )


def test_S9_Q5_reprise_sans_double_depense(banc):
    exp = _exp(banc, regroupement={"parallelisme": 1})
    exe = _execution(banc, exp)
    controle = Controle(exe.dossier)
    dec = DecideurCompteur(controle, pause_apres=1)
    c1, _ = _lancer(banc, exp, dec, execution=exe, controle=controle)
    assert c1["etat"] == "en_pause" and len(exe.decisions) == 1
    exe2 = A.Execution.ouvrir(exe.dossier)
    dec2 = DecideurCompteur()
    c2, _ = _lancer(banc, exp, dec2, execution=exe2)
    # resservie : p3/a1 ; choix unique sans sollicitation : p3/a2 ; sollicitée : p2/b1
    assert (
        dec2.appels == 1
        and c2["resservies"] == 1
        and c2["etat"] == "terminee"
        and len(exe2.decisions) == 3
    )
    assert len(exe2.config["interruptions"]) == 2 and [
        i["cause"] for i in exe2.config["interruptions"]
    ] == ["pause", "reprise"]
    # Q6 : résultat final identique à l'exécution ininterrompue
    _, ref = _lancer(banc, _exp(banc, nom="ref"))
    assert {
        (t["person_id"], t["activity_id"], t["retenue"]["code"]) for t in exe2.decisions
    } == {
        (t["person_id"], t["activity_id"], t["retenue"]["code"]) for t in ref.decisions
    }


def test_S10_Q12_decideur_local_sans_quota(banc):
    exp = _exp(banc)
    c, _ = _lancer(banc, exp)
    assert (
        c["sollicitations"] == 2
        and c["decides"] == 3
        and c["quota"] == {"sans_quota": True}
    )


def test_exp00b_majoritaire_voiture_prend_la_voiture_sinon_repli():
    """Plancher exp_00b : la voiture si son mode PRINCIPAL est offert, même plus lente ; sinon
    repli déterministe sur la première option présentée. Local, sans person ni ctx."""
    from models import Location

    o, d = Location(**HOME), Location(**WORK)
    dec = DecideurMajoritaireVoiture()

    # La voiture (900 s) est retenue bien qu'un bus (500 s) soit plus rapide.
    avec_voiture = [
        D.Proposition(plan=_plan("bus", o, d, 0, duration=500)),
        D.Proposition(plan=_plan("car", o, d, 0, duration=900)),
        D.Proposition(plan=_plan("foot", o, d, 0, duration=1200)),
    ]
    r = asyncio.run(dec.choisir(None, None, avec_voiture))
    assert avec_voiture[r.index].mode == "car"
    assert r.poids == [0.0, 1.0, 0.0]
    assert r.fournisseur == "majoritaire_voiture"

    # Un rabattement voiture+train n'est PAS « la voiture » (mode principal = collectif) : sans
    # option voiture pure, repli sur la première présentée (index 0), sans tirage.
    sans_voiture = [
        D.Proposition(plan=_plan("bus", o, d, 0, duration=500)),
        D.Proposition(plan=_plan("foot", o, d, 0, duration=400)),
    ]
    r2 = asyncio.run(dec.choisir(None, None, sans_voiture))
    assert r2.index == 0


# ═══════════════ Spec 05 ═══════════════


def _moniteur(etat: dict, providers=None):
    providers = providers or {
        "g1": {"default_model": "m", "rpd_limit": 500, "rpm_limit": 15},
        "g2": {"default_model": "m", "rpd_limit": 500, "rpm_limit": 15},
        "autre": {"default_model": "x", "rpd_limit": 500, "rpm_limit": 15},
    }
    m = MoniteurRessources(["g1", "g2"], providers, lecteur=lambda url: etat)
    m.rafraichir()
    return m


def test_Q1_valeurs_de_la_passerelle():
    m = _moniteur(
        {
            "g1": {
                "daily_requests": 120,
                "rpd_limit": 500,
                "current_rpm": 3,
                "quota_exhausted": False,
                "available": True,
            },
            "g2": {
                "daily_requests": 500,
                "rpd_limit": 500,
                "quota_exhausted": True,
                "available": False,
            },
        }
    )
    t = {l["instance"]: l for l in m.tableau()}
    assert (
        t["g1"]["marge"] == 380
        and t["g1"]["rpm_observe"] == 3
        and t["g2"]["epuisee"] is True
    )
    m.providers["g1"]["rpd_limit"] = (
        1000  # la limite change dans la configuration → l'affichage suit
    )
    assert m.marge("g1") == 880


def test_Q2_instances_du_modele():
    from experiences.ressources import instances_pour_modele

    providers = {
        "google_gemini31_key1": {"default_model": "gemini-3.1-flash-lite"},
        "google_gemini31_key2": {"default_model": "gemini-3.1-flash-lite"},
        "google_gemini35_key1": {"default_model": "gemini-3.5-flash-lite"},
        "mistral": {"default_model": "mistral-small-latest"},
    }
    # Le tri place la clé 1 avant la clé 2 : la consommation en série (`_prochaine_instance`)
    # vide donc les seaux dans l'ordre qu'on lit dans les noms. Avec les anciens noms,
    # `google2` passait avant `google_gemini31` parce que « 2 » précède « _ » en ASCII —
    # l'ordre dépendait du nommage, pas d'une décision.
    assert instances_pour_modele("gemini-3.1-flash-lite", providers) == [
        "google_gemini31_key1",
        "google_gemini31_key2",
    ]


def test_Q3_Q4_epuisement_arret_propre(banc):
    exp = _exp(banc, regroupement={"parallelisme": 1})
    m = _moniteur(
        {
            "g1": {"daily_requests": 500, "rpd_limit": 500, "quota_exhausted": True},
            "g2": {"daily_requests": 500, "rpd_limit": 500, "quota_exhausted": True},
        }
    )

    class Epuise(DecideurDureeMinimale):
        sans_quota = False

        async def choisir(self, person, ctx, presentees):
            return D.ReponseDecideur(
                index=None, erreur="epuise: g2 : 500/500 requêtes/jour"
            )

    messages = []
    sink = logger.add(lambda x: messages.append(str(x)), level="ERROR")
    try:
        # `attendre_fenetre=False` explicite : attendre la fenêtre est le défaut depuis le
        # 2026-09-08, et ce test-ci porte sur l'ARRÊT propre (Q4), pas sur l'attente.
        c, exe = _lancer(banc, exp, Epuise(), moniteur=m, attendre_fenetre=False)
    finally:
        logger.remove(sink)
    etat = exe.etat()
    assert (
        c["etat"] == "epuisee"
        and etat["etat"] == "epuisee"
        and "500/500" in etat["raison"]
    )
    # La reprise vise la réouverture de la fenêtre du FOURNISSEUR — minuit dans son fuseau,
    # soit 07:00 UTC l'été et 08:00 UTC l'hiver pour le Pacifique. On compare donc à la
    # fonction, pas à une heure en dur qui casserait à chaque passage heure d'été.
    from experiences.ressources import prochaine_fenetre_quota

    assert etat["reprise_possible_a"] == prochaine_fenetre_quota()
    assert any("[ALARME]" in x and "épuisée" in x for x in messages)
    assert not exe.cloturee, "épuisée = reprenable"


def test_Q7_pause_manuelle_par_fichier(banc):
    exp = _exp(banc, regroupement={"parallelisme": 1})
    exe = _execution(banc, exp)

    class PauseParFichier(DecideurDureeMinimale):
        async def choisir(self, person, ctx, presentees):
            (exe.dossier / "PAUSE").touch()
            return await super().choisir(person, ctx, presentees)

    c, _ = _lancer(banc, exp, PauseParFichier(), execution=exe)
    assert (
        c["etat"] == "en_pause" and len(A.Execution.ouvrir(exe.dossier).decisions) == 1
    )
    assert not (exe.dossier / "PAUSE").exists(), "le signal est consommé"
    assert A.Execution.ouvrir(exe.dossier).etat()["etat"] == "en_pause"


def test_Q7_sentinelle_residuelle_ne_bloque_pas_la_reprise(banc):
    """Un runner tué (conteneur arrêté, SIGKILL) laisse son PAUSE sur le disque : la reprise
    doit le purger au démarrage, sinon elle se remet en pause en quelques secondes et
    l'exécution paraît irréprenable — c'est ce qui est arrivé le 2026-09-08.

    La sentinelle ne vaut que pour le run qui l'a reçue : un nouveau run repart franchement.
    """
    exp = _exp(banc, regroupement={"parallelisme": 1})
    exe = _execution(banc, exp)
    # Le cadavre : la sentinelle est déposée AVANT le run, comme le fait le tableau de bord
    # sur une exécution dont le runner est déjà mort.
    (exe.dossier / "PAUSE").touch()

    c, _ = _lancer(banc, exp, execution=exe)

    assert not (exe.dossier / "PAUSE").exists(), "la sentinelle résiduelle est purgée"
    assert c["etat"] != "en_pause", (
        f"la reprise s'est remise en pause sur un PAUSE d'un run précédent (état {c['etat']!r})"
    )
    assert A.Execution.ouvrir(exe.dossier).etat()["etat"] != "en_pause"


def test_Q7_sentinelle_stop_residuelle_purgee_aussi(banc):
    """Idem pour STOP : sans purge, la reprise scellerait l'archive sur un signal périmé."""
    exp = _exp(banc, regroupement={"parallelisme": 1})
    exe = _execution(banc, exp)
    (exe.dossier / "STOP").touch()

    c, _ = _lancer(banc, exp, execution=exe)

    assert not (exe.dossier / "STOP").exists()
    assert c["etat"] != "arretee", f"arrêt sur un STOP périmé (état {c['etat']!r})"


def test_Q7_pause_abandonne_la_sollicitation_en_vol(banc, monkeypatch):
    """La pause n'attend plus le retour d'un appel qui traîne (jusqu'à 120 s de timeout de
    poll) : passé le délai de grâce, l'appel est ABANDONNÉ. Le déplacement reste non archivé,
    donc redemandé tel quel à la reprise — rien de partiel, rien de fabriqué."""
    monkeypatch.setattr(runner, "PAS_ATTENTE_S", 0.02)
    exp = _exp(banc, regroupement={"parallelisme": 1})
    exe = _execution(banc, exp)
    controle = Controle(exe.dossier, grace_s=0.2)

    class Interminable(DecideurDureeMinimale):
        async def choisir(self, person, ctx, presentees):
            controle.pause = True
            await asyncio.sleep(60)  # jamais atteint : l'appel est annulé
            return await super().choisir(person, ctx, presentees)

    debut = time.monotonic()
    c, _ = _lancer(banc, exp, Interminable(), execution=exe, controle=controle)
    assert c["etat"] == "en_pause"
    assert time.monotonic() - debut < 5, "la pause n'attend pas le retour de l'appel"
    assert len(A.Execution.ouvrir(exe.dossier).decisions) == 0, (
        "rien de partiel archivé"
    )


def test_Q7_pause_laisse_finir_une_sollicitation_courte(banc, monkeypatch):
    """La grâce n'est pas une exécution capitale : un appel qui revient dans le délai est
    archivé normalement, donc pas repayé à la reprise."""
    monkeypatch.setattr(runner, "PAS_ATTENTE_S", 0.02)
    exp = _exp(banc, regroupement={"parallelisme": 1})
    exe = _execution(banc, exp)
    controle = Controle(exe.dossier, grace_s=5.0)

    class Lente(DecideurDureeMinimale):
        async def choisir(self, person, ctx, presentees):
            controle.pause = True
            await asyncio.sleep(0.1)
            return await super().choisir(person, ctx, presentees)

    c, _ = _lancer(banc, exp, Lente(), execution=exe, controle=controle)
    assert c["etat"] == "en_pause"
    assert len(A.Execution.ouvrir(exe.dossier).decisions) == 1, (
        "la décision obtenue dans la grâce est archivée"
    )


def test_Q7_chien_de_garde_pause_apres_inactivite(banc, monkeypatch):
    """Une exécution qui n'avance plus se met en pause d'elle-même, en le disant en ERROR,
    au lieu de rester « en cours » indéfiniment. Elle reste reprenable."""
    monkeypatch.setattr(runner, "PAS_ATTENTE_S", 0.02)
    monkeypatch.setattr(runner, "INACTIVITE_PAUSE_S", 0.3)
    exp = _exp(banc, regroupement={"parallelisme": 1})
    exe = _execution(banc, exp)
    controle = Controle(exe.dossier, grace_s=0.05)

    class Bloque(DecideurDureeMinimale):
        async def choisir(self, person, ctx, presentees):
            await asyncio.sleep(60)
            return await super().choisir(person, ctx, presentees)

    messages = []
    sink = logger.add(lambda m: messages.append(str(m)), level="INFO")
    try:
        c, _ = _lancer(banc, exp, Bloque(), execution=exe, controle=controle)
    finally:
        logger.remove(sink)
    relue = A.Execution.ouvrir(exe.dossier)
    assert c["etat"] == "en_pause" and not relue.cloturee, "en pause = reprenable"
    assert len(relue.decisions) == 0
    derniere = relue.config["interruptions"][-1]
    assert derniere["cause"] == "pause"
    assert str(derniere["raison"]).startswith("inactivite:")
    assert str(relue.etat()["raison"]).startswith("pause automatique")
    assert any("[ALARME]" in m and "sans avancée" in m for m in messages)


def test_Q7_chien_de_garde_muet_pendant_la_fenetre_quota():
    """Attendre la fenêtre de quota (R4) est une immobilité VOULUE : le chien de garde s'y
    tait, sinon il mettrait en pause une exécution qui fait exactement ce qu'on lui demande."""
    prog = runner.Progression(attendus=3, personnes=1, deja=0)
    assert prog.immobile_depuis() < 0.5
    prog._avancement_t -= 1000  # comme si plus rien n'avait bougé depuis longtemps
    assert prog.immobile_depuis() > 900
    prog.entrer_attente_quota("2026-09-09T00:00:00+00:00")
    assert prog.immobile_depuis() is None
    prog.sortir_attente_quota()
    prog.compteurs["decides"] += 1
    assert prog.immobile_depuis() == 0.0, "un déplacement réglé remet l'horloge à zéro"


def test_Q8_arret_definitif(banc):
    exp = _exp(banc, regroupement={"parallelisme": 1})
    exe = _execution(banc, exp)

    class Stop(DecideurDureeMinimale):
        async def choisir(self, person, ctx, presentees):
            (exe.dossier / "STOP").touch()
            return await super().choisir(person, ctx, presentees)

    c, _ = _lancer(banc, exp, Stop(), execution=exe)
    assert c["etat"] == "arretee" and exe.cloturee
    with pytest.raises(A.ArchiveInvalide):
        A.Execution.ouvrir(exe.dossier).ajouter_decision(
            exe.decisions[0] | {"activity_id": "zz"}
        )


def test_Q9_derniere_ligne_tronquee(banc):
    exp = _exp(banc)
    exe = _execution(banc, exp)
    # deux décisions archivées puis une ligne à moitié écrite
    _, ref = _lancer(banc, _exp(banc, nom="ref"))
    for t in [t for t in ref.decisions if t["person_id"] == "p3"]:
        exe.ajouter_decision(t)
    exe.fermer()
    with open(exe.dossier / "decisions.jsonl", "ab") as f:
        f.write(b'{"person_id": "p2", "activity_id": "b1", "methode": "decid')
    messages = []
    sink = logger.add(lambda x: messages.append(str(x)), level="WARNING")
    try:
        relu = A.Execution.ouvrir(exe.dossier)
    finally:
        logger.remove(sink)
    assert len(relu.decisions) == 2 and any(
        "tronquée" in x and "ligne 3" in x for x in messages
    )
    dec = DecideurCompteur()
    c, _ = _lancer(banc, exp, dec, execution=relu)
    assert dec.appels == 1 and c["etat"] == "terminee"


def test_Q11_epuisement_anticipe():
    m = _moniteur(
        {
            "g1": {"daily_requests": 493, "rpd_limit": 500, "quota_exhausted": False},
            "g2": {"daily_requests": 500, "rpd_limit": 500, "quota_exhausted": True},
        }
    )
    assert (
        m.instances_disponibles(besoin=7) == ["g1"]
        and m.instances_disponibles(besoin=10) == []
        and m.epuise(10)
    )


# ═══════════════ Spec 06 ═══════════════


def test_E1_champ_absent_est_une_erreur(banc):
    d = _exp_dict(banc)
    d.pop("tolerances_horaires")
    p = banc["tmp"] / "e1.yaml"
    p.write_text(yaml.safe_dump(d), encoding="utf-8")
    with pytest.raises(E.ExperienceInvalide, match="tolerances_horaires"):
        E.charger_experience(p)
    d = _exp_dict(banc)
    d["tolerances_horaires"].pop("rail")
    p.write_text(yaml.safe_dump(d), encoding="utf-8")
    with pytest.raises(E.ExperienceInvalide, match="rail"):
        E.charger_experience(p)


def test_E2_population_non_scellee_admise(banc):
    (banc["pop"] / "MANIFEST.yaml").unlink()
    info = info_population(banc["pop"] / "population.json")
    assert info.scellee is False
    exp = _exp(banc, population={"chemin": str(banc["pop"] / "population.json")})
    emp = E.empreintes(exp, banc["jeu"], info, {"commit": "abc"})
    assert (
        emp["population"]["scellee"] is False
        and emp["population"]["sha256"] == info.fichier_sha256
    )


def test_E3_empreintes(banc):
    exp = _exp(banc)
    emp = E.empreintes(
        exp, banc["jeu"], banc["info"], {"commit": "abc", "arbre_propre": True}
    )
    assert (
        emp["jeu"]["sha256"] == banc["jeu"].empreinte
        and emp["depot"]["commit"] == "abc"
    )
    assert (
        E.empreinte_gabarit("itinary_multi_agent")["sha256"]
        == E.empreinte_gabarit("itinary_multi_agent")["sha256"]
    )
    assert (
        E.empreinte_gabarit("itinary_multi_agent")["sha256"]
        != E.empreinte_gabarit("stm_reflection")["sha256"]
    )
    a = _exp(banc, nom="a", decideur={"type": "aleatoire", "graine": 1})
    b = _exp(banc, nom="b", decideur={"type": "aleatoire", "graine": 2})
    assert a.decideur.empreinte() != b.decideur.empreinte()


def test_E4_dupliquer(banc):
    exp = _exp(banc)
    nouvelle = E.dupliquer(exp, "exp_bis", decideur={"type": "aleatoire", "graine": 3})
    assert (
        nouvelle.derive_de == "exp_test"
        and nouvelle.jeu == exp.jeu
        and nouvelle.tolerances_horaires == exp.tolerances_horaires
    )
    assert nouvelle.decideur.type == "aleatoire" and nouvelle.executions_connues == []


def test_E5_estimation_cite_ses_sources(banc):
    exp = _exp(
        banc,
        decideur={
            "type": "passerelle",
            "modele": "m",
            "parametres": {"temperature": 0},
        },
    )
    m = _moniteur(
        {
            "g1": {"daily_requests": 100, "rpd_limit": 500},
            "g2": {"daily_requests": 0, "rpd_limit": 500},
        }
    )
    est = E.estimer(
        exp,
        banc["jeu"],
        moniteur=m,
        jetons={"entree": 750, "sortie": 230, "source": "test"},
    )
    assert (
        est["sollicitations"]["valeur"] == 3
        and "jeu" in est["sollicitations"]["source"]
    )
    assert est["jetons"]["entree"] == 2250 and est["jetons"]["source"] == "test"
    assert (
        est["quota"]["part"] == pytest.approx(3 / 900)
        and "providers.yaml" in est["quota"]["source"]
    )
    m.providers["g1"]["rpd_limit"] = 1000
    assert E.estimer(
        exp, banc["jeu"], moniteur=m, jetons={"entree": 1, "sortie": 1, "source": "t"}
    )["quota"]["part"] == pytest.approx(3 / 1400)
    local = E.estimer(_exp(banc), banc["jeu"])
    assert local["quota"]["valeur"] is None and "sans quota" in local["quota"]["source"]


def test_E6_refus_explicites(banc, tmp_path):
    jeu = banc["jeu"]
    # population ≠ jeu
    autre = tmp_path / "autre"
    autre.mkdir()
    (autre / "population.json").write_text(
        json.dumps(_population()[:2]), encoding="utf-8"
    )
    refus, _ = E.refuser_si_impossible(
        _exp(banc),
        jeu,
        info_population(autre / "population.json"),
        dependances={"commit": "abc"},
        periodes={},
    )
    assert any("préparé pour la population" in r for r in refus)
    # décideur sans instance
    exp = _exp(banc, decideur={"type": "passerelle", "modele": "inconnu"})
    refus, _ = E.refuser_si_impossible(
        exp,
        jeu,
        banc["info"],
        instances_disponibles=[],
        dependances={"commit": "abc"},
        periodes={},
    )
    assert any("aucune instance" in r for r in refus)
    # jeu périmé refusé, accepté explicitement → avertissement
    refus, _ = E.refuser_si_impossible(
        _exp(banc), jeu, banc["info"], dependances={"commit": "def"}, periodes={}
    )
    assert any("périmé" in r and "--accepter-perime" in r for r in refus)
    refus, avert = E.refuser_si_impossible(
        _exp(banc),
        jeu,
        banc["info"],
        dependances={"commit": "def"},
        periodes={},
        perime_accepte=True,
    )
    assert not any("périmé" in r for r in refus) and any(
        "accepté explicitement" in a for a in avert
    )


def test_E7_horizon_zero(banc):
    d = _exp_dict(banc, horizon_jours=0)
    p = banc["tmp"] / "e7.yaml"
    p.write_text(yaml.safe_dump(d))
    with pytest.raises(E.ExperienceInvalide, match="horizon_jours"):
        E.charger_experience(p)


def test_E8_politiques(banc):
    exp = _exp(
        banc,
        mode="simulateur",
        evenements=[EV],
        calendrier={"politique": "propre", "date": "2026-03-16", "graine": 42},
    )
    refus, _ = E.refuser_si_impossible(
        exp, banc["jeu"], banc["info"], dependances={"commit": "abc"}, periodes={}
    )
    assert any("politique de calendrier `commune`" in r for r in refus)
    with pytest.raises(E.ExperienceInvalide):
        _exp(
            banc,
            calendrier={"politique": "inconnue", "date": "2026-03-16", "graine": 42},
        )


def test_E9_date_hors_periode(banc, tmp_path):
    gtfs = tmp_path / "gtfs"
    gtfs.mkdir()
    (gtfs / "feed_info.txt").write_text(
        "feed_id,feed_start_date,feed_end_date\ntisseo,20260316,20260512\n"
    )
    bornes = E.periodes_couvertes(gtfs, tmp_path / "absent.csv")
    assert bornes["gtfs"] == ("2026-03-16", "2026-05-12") and bornes["meteo"] is None
    exp = _exp(
        banc, calendrier={"politique": "commune", "date": "2026-07-01", "graine": 42}
    )
    refus, avert = E.refuser_si_impossible(
        exp, banc["jeu"], banc["info"], dependances={"commit": "abc"}, periodes=bornes
    )
    assert any("hors de la période couverte par gtfs" in r for r in refus) and any(
        "meteo" in a for a in avert
    )


def test_E10_E11_archive_complete_et_tolerante(banc):
    exp = _exp(banc)
    _, exe = _lancer(banc, exp)
    assert A.valider_archive(exe.dossier) == []
    for t in exe.decisions:
        if t["methode"] == "decideur":
            assert t["presente"], (
                "le texte présenté au décideur fait partie de l'archive (E11)"
            )
    # champ inconnu ajouté → lecture réussie
    lignes = (exe.dossier / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
    t = json.loads(lignes[0])
    t["champ_futur"] = 1
    conf = yaml.safe_load((exe.dossier / "execution.yaml").read_text())
    conf["cloture"] = None
    (exe.dossier / "execution.yaml").write_text(yaml.safe_dump(conf))
    (exe.dossier / "decisions.jsonl").write_text(
        "\n".join([json.dumps(t), *lignes[1:]]) + "\n", encoding="utf-8"
    )
    assert len(A.Execution.ouvrir(exe.dossier).decisions) == 3
    # un des cinq éléments supprimé → invalide
    t.pop("reponse_brute")
    (exe.dossier / "decisions.jsonl").write_text(
        "\n".join([json.dumps(t), *lignes[1:]]) + "\n", encoding="utf-8"
    )
    with pytest.raises(A.ArchiveInvalide, match="reponse_brute"):
        A.Execution.ouvrir(exe.dossier)


def test_E12_E20_registre(banc):
    exp = _exp(banc)
    _, _exe = _lancer(banc, exp)
    exp2 = _exp(banc, nom="exp_alea", decideur={"type": "aleatoire", "graine": 1})
    _, _exe2 = _lancer(banc, exp2)
    exp2.executions_connues.append("2020-01-01_00_00_00")
    E.sauver_experience(exp2)
    lignes = R.lister()
    assert {l["experience"] for l in lignes} == {"exp_test", "exp_alea"}
    manquante = [l for l in lignes if l["etat"] == R.ETAT_ARCHIVE_MANQUANTE]
    assert len(manquante) == 1 and manquante[0]["execution"] == "2020-01-01_00_00_00"
    tri = R.trier_filtrer(
        lignes, trier="couverture", decroissant=True, filtres={"decideur": "duree"}
    )
    assert [l["experience"] for l in tri] == ["exp_test"]
    assert "exp_test" in R.formater_table(lignes)


def test_E20bis_le_decideur_du_registre_est_celui_fige(banc):
    """Changer la définition d'une expérience ne doit pas réétiqueter ses exécutions passées :
    chaque ligne du registre montre le décideur figé dans son snapshot, pas celui (mutable) de la
    définition courante (R6). C'est le bug vécu : un run Mistral réétiquetait une exécution Gemini."""
    exp = _exp(banc, nom="mute")
    _, exe = _lancer(banc, exp)  # exécution figée sur duree_minimale
    # La définition bascule ensuite sur un autre décideur (réenregistrement / relance modifiée).
    E.sauver_experience(
        _exp(banc, nom="mute", decideur={"type": "aleatoire", "graine": 7})
    )

    ligne = next(
        l for l in R.lister() if l["experience"] == "mute" and l["execution"] == exe.nom
    )
    assert ligne["decideur"] == "duree_minimale", (
        "l'exécution garde son décideur figé, pas celui de la définition courante"
    )


def test_E13_comparabilite(banc):
    a = _exp(banc, nom="a")
    b = _exp(banc, nom="b", decideur={"type": "aleatoire", "graine": 1})
    _, xa = _lancer(banc, a)
    _, xb = _lancer(banc, b)
    c = R.comparer(xa.dossier, xb.dossier)
    assert (
        c["comparable"] is True
        and c["a"]["parts_modales"]["couverture"]["attendus"] == 3
    )
    d = _exp(banc, nom="d", graine_ordre=43)
    _, xd = _lancer(banc, d)
    c2 = R.comparer(xa.dossier, xd.dossier)
    assert c2["comparable"] is False and [x["champ"] for x in c2["differences"]] == [
        "graine_ordre"
    ]
    assert "NON COMPARABLE" in R.formater_comparaison(c2)


def test_E14_E16_synthese_couverture_et_rendu(banc):
    exp = _exp(banc, regroupement={"parallelisme": 1})
    exe = _execution(banc, exp)
    controle = Controle(exe.dossier)
    _lancer(
        banc,
        exp,
        DecideurCompteur(controle, pause_apres=1),
        execution=exe,
        controle=controle,
    )
    s = R.synthese(exe.dossier)
    assert (
        s["couverture"]["complet"] is False
        and s["parts_modales"]["couverture"]["decides"] == 1
    )
    page = R.synthese_html(s)
    assert "PARTIEL" in page and "1 / 3" in page
    for pct in s["parts_modales"]["pourcent"].values():
        if pct is not None:
            assert f"{pct:.1f} %" in page
    assert (
        s["referentiel"]["source"].endswith("cerema_values.yaml")
        and s["referentiel"]["sha256"]
    )


def test_E17_referentiel_lu_jamais_recopie(banc, tmp_path):
    exp = _exp(banc)
    _, exe = _lancer(banc, exp)
    code = "".join(
        p.read_text(encoding="utf-8") for p in Path(D.__file__).parent.glob("*.py")
    )
    assert (
        "cerema_values.yaml" in code and re.search(r"voiture\s*[:=]\s*\d", code) is None
    )
    ref = R.lire_referentiel()
    s = R.synthese(exe.dossier)
    total = sum(
        v
        for k, v in ref["valeurs"].items()
        if k in ("voiture", "marche", "transports_collectifs", "velo")
    )
    assert s["referentiel"]["pourcent_normalise_4_modes"]["car"] == pytest.approx(
        ref["valeurs"]["voiture"] / total * 100
    )
    autre = tmp_path / "ref.yaml"
    autre.write_text(
        yaml.safe_dump(
            {
                "parts_modales_2023": {
                    "global": {
                        "voiture": 10,
                        "marche": 40,
                        "transports_collectifs": 40,
                        "velo": 10,
                    }
                }
            }
        )
    )
    s2 = R.synthese(exe.dossier, referentiel=autre)
    assert (
        s2["referentiel"]["pourcent_normalise_4_modes"]["car"] == pytest.approx(10.0)
        and s2["referentiel"]["sha256"] != s["referentiel"]["sha256"]
    )


def test_E18_sources_d_alea_et_nouvelle_execution(banc):
    exp = _exp(banc)
    _, x1 = _lancer(banc, exp)
    assert set(x1.config["sources_alea"]) >= {
        "graine_ordre",
        "graine_tirage",
        "graine_calendrier",
        "echantillonnage_decideur",
    }
    _, x2 = _lancer(banc, exp)
    assert x2.dossier != x1.dossier and A.valider_archive(x1.dossier) == []
    rejeu = DecideurRejeu(x1)
    _, x3 = _lancer(banc, _exp(banc, nom="rejeu"), rejeu)
    assert {
        (t["person_id"], t["activity_id"], t["retenue"]["code"]) for t in x3.decisions
    } == {
        (t["person_id"], t["activity_id"], t["retenue"]["code"]) for t in x1.decisions
    }


def test_E19_archive_alteree_detectee(banc):
    exp = _exp(banc)
    _, exe = _lancer(banc, exp)
    f = exe.dossier / "decisions.jsonl"
    b = bytearray(f.read_bytes())
    b[5] ^= 0x01
    f.write_bytes(bytes(b))
    problemes = A.valider_archive(exe.dossier)
    assert any("altéré" in p for p in problemes)


def test_E22_attendus_derives(banc):
    assert len(J.deplacements_attendus(banc["personnes"], "2026-03-16")) == 3
    _, exe = _lancer(banc, _exp(banc))
    assert exe.compteurs["attendus"] == 3


def test_D18_date_autre_que_le_jour_du_jeu(banc):
    exp = _exp(
        banc, calendrier={"politique": "commune", "date": "2026-03-17", "graine": 42}
    )
    refus, _ = E.refuser_si_impossible(
        exp, banc["jeu"], banc["info"], dependances={"commit": "abc"}, periodes={}
    )
    assert any(
        "n'a pas été mesurée équivalente" in r and "verifier-jours" in r for r in refus
    )
    banc["jeu"].declarer_jour_equivalent("2026-03-17", {"compares": 3, "identiques": 3})
    refus, _ = E.refuser_si_impossible(
        exp, banc["jeu"], banc["info"], dependances={"commit": "abc"}, periodes={}
    )
    assert not any("équivalente" in r for r in refus)


def test_D14_format_evenement_pret_mais_refuse(banc):
    ev = EV
    exp = _exp(banc, mode="simulateur", evenements=[ev])
    assert exp.evenements[0].cible == {"ligne": "metro_A"}
    refus, _ = E.refuser_si_impossible(
        exp, banc["jeu"], banc["info"], dependances={"commit": "abc"}, periodes={}
    )
    assert any("pas encore joués par GAMA" in r for r in refus)
    with pytest.raises(E.ExperienceInvalide, match="heure_debut"):
        _exp(banc, mode="simulateur", evenements=[{**ev, "heure_debut": "25h"}])


def test_D3_inexploitables_exclus_des_attendus(banc, tmp_path):
    """Décision 3 : un déplacement couvert par le jeu mais sans AUCUNE proposition des moteurs est
    inexploitable — exclu du dénominateur, archivé, remonté en avertissement."""
    exp = _exp(banc)
    ligne = banc["jeu"]._index[("p2", "b1")]
    banc["jeu"]._index[("p2", "b1")] = ligne.model_copy(
        update={"propositions": [], "motif_absence": "aucune_proposition"}
    )
    messages = []
    sink = logger.add(lambda m: messages.append(str(m)), level="WARNING")
    try:
        c, exe = _lancer(banc, exp)
    finally:
        logger.remove(sink)
    assert (
        c["inexploitables"] == 1
        and c["attendus"] == 3
        and c["attendus_exploitables"] == 2
    )
    assert (
        c["decides"] == 2
        and c["couverture"]["taux"] == pytest.approx(1.0)
        and c["couverture"]["inexploitables_exclus"] == 1
    )
    assert any(
        "INEXPLOITABLES" in m and "aucune_proposition" in m and "p2" in m
        for m in messages
    )
    s = R.synthese(exe.dossier)
    assert (
        s["couverture"]["complet"] is True
        and s["couverture"]["inexploitables_exclus"] == 1
        and s["couverture"]["attendus_bruts"] == 3
    )
    assert "inexploitables exclus" in R.synthese_html(s)
    # archivé : à la reprise il n'est pas retenté
    dec = DecideurCompteur()
    c2, _ = _lancer(banc, exp, dec, execution=A.Execution.ouvrir(exe.dossier))
    assert dec.appels == 0 and c2["etat"] == "terminee"


def test_E3_variante_de_prompt_dans_l_empreinte_et_refus_si_inconnue(banc):
    actif = E.empreinte_gabarit("itinary_multi_agent")
    minimal = E.empreinte_gabarit("itinary_multi_agent", "b_min")
    assert (
        minimal["sha256"] != actif["sha256"]
        and minimal["variante"] == "b_min"
        and "prompts.yaml:b_min" in minimal["sources"]
    )
    exp = _exp(
        banc,
        decideur={"type": "passerelle", "modele": "m"},
        gabarit={"categorie": "itinary_multi_agent", "variante": "n_existe_pas"},
    )
    refus, _ = E.refuser_si_impossible(
        exp,
        banc["jeu"],
        banc["info"],
        instances_disponibles=["g1"],
        dependances={"commit": "abc"},
        periodes={},
    )
    assert any("variante de prompt" in r and "b_min" in r for r in refus)
    ok = _exp(
        banc,
        nom="ok",
        decideur={"type": "passerelle", "modele": "m"},
        gabarit={"categorie": "itinary_multi_agent", "variante": "b_min"},
    )
    refus, _ = E.refuser_si_impossible(
        ok,
        banc["jeu"],
        banc["info"],
        instances_disponibles=["g1"],
        dependances={"commit": "abc"},
        periodes={},
    )
    assert not any("variante" in r for r in refus)


def test_S6_progression_json_pour_le_tableau_de_bord(banc):
    exp = _exp(banc)
    _, exe = _lancer(banc, exp)
    p = json.loads((exe.dossier / "progression.json").read_text(encoding="utf-8"))
    assert (
        p["faits"] == 3
        and p["attendus"] == 3
        and p["pourcent"] == 100.0
        and p["personnes_terminees"] == 2
    )
    assert {"ecoule_s", "reste_s", "sollicitations", "erreurs", "maj"} <= set(p)


# ═══════════════ R1–R4 : aucun déplacement sauté, traçabilité, attente fenêtre ═══════════════


async def _dormir_rapide(duree_s, controle, epuise):
    """Remplace `_dormir_interruptible` dans les tests : honore l'interruption sans attendre le mur."""
    if not (controle.interrompu() or epuise.is_set()):
        await asyncio.sleep(0)


class OccupeeNfois(DecideurDureeMinimale):
    """Échoue `n` fois PAR déplacement sollicité (passerelle occupée, transitoire) puis décide.

    Note : dans le banc, `p3/a2` (retour maison) est contraint par la chaîne de véhicule à une
    seule proposition → `choix_unique`, décideur NON sollicité. Seuls 2 des 3 déplacements passent
    par le décideur, donc ce décideur produit `2 × n` tentatives ratées, pas `3 × n`.
    """

    sans_quota = False

    def __init__(
        self,
        n,
        erreur="passerelle_occupee: Providers saturés ou indisponibles après 8s",
    ):
        self.n, self.erreur = n, erreur
        self.echecs = {}

    async def choisir(self, person, ctx, presentees):
        cle = (person.person_id, ctx.activity_id)
        self.echecs[cle] = self.echecs.get(cle, 0)
        if self.echecs[cle] < self.n:
            self.echecs[cle] += 1
            return D.ReponseDecideur(index=None, fournisseur="g1", erreur=self.erreur)
        return await super().choisir(person, ctx, presentees)


class OccupeeKglobal(DecideurDureeMinimale):
    """Échoue les `k` PREMIÈRES sollicitations (toutes sur le 1er déplacement en parallélisme 1)
    puis décide tout — pour isoler le front montant d'alarme sur un seul déplacement."""

    sans_quota = False

    def __init__(self, k, erreur="passerelle_occupee: saturés"):
        self.k, self.erreur, self.appels = k, erreur, 0

    async def choisir(self, person, ctx, presentees):
        self.appels += 1
        if self.appels <= self.k:
            return D.ReponseDecideur(index=None, fournisseur="g1", erreur=self.erreur)
        return await super().choisir(person, ctx, presentees)


def test_R2_occupee_nest_pas_epuisee(banc, monkeypatch):
    from experiences.decideurs import _RE_OCCUPEE, _RE_QUOTA

    monkeypatch.setattr(runner, "_dormir_interruptible", _dormir_rapide)
    exp = _exp(banc, regroupement={"parallelisme": 1})
    c, exe = _lancer(banc, exp, OccupeeNfois(2))
    assert (
        c["etat"] == "terminee" and len(exe.decisions) == 3
    )  # tous archivés, aucun saut
    assert (
        c["attentes_par_type"].get("passerelle_occupee", 0) == 4
    )  # 2 échecs × 2 déplacements sollicités
    assert "epuise" not in c["attentes_par_type"]
    # R1 ne saute aucun déplacement : aucun échec DÉFINITIF ne doit être compté
    assert c["erreurs"] == 0 and c["erreurs_par_type"] == {}
    assert not _RE_QUOTA.search("Providers saturés") and _RE_OCCUPEE.search(
        "Providers saturés"
    )


def test_R1_aucun_saut_apres_echecs_transitoires(banc, monkeypatch):
    monkeypatch.setattr(runner, "_dormir_interruptible", _dormir_rapide)
    exp = _exp(banc)
    c, exe = _lancer(banc, exp, OccupeeNfois(5))
    assert c["etat"] == "terminee" and c["couverture"]["taux"] == 1.0
    diag = ERR.diagnostiquer(exe.dossier)
    assert diag["nb_manquants"] == 0 and diag["decisions_apres_trou"] == 0
    assert (
        diag["tentatives_par_type"].get("passerelle_occupee", 0) == 10
    )  # 5 × 2 sollicités


def test_R1_alarme_front_montant(banc, monkeypatch):
    monkeypatch.setattr(runner, "_dormir_interruptible", _dormir_rapide)
    # attente_max_s=1 et PAUSE_BASE_S=5 : le seuil est franchi dès le 1er échec. Un SEUL déplacement
    # échoue (3 fois), donc UNE seule alarme — la preuve du front montant (pas une alarme par tentative).
    exp = _exp(banc, regroupement={"parallelisme": 1}, attente_max_s=1)
    msgs = []
    sink = logger.add(lambda m: msgs.append(str(m)), level="ERROR")
    try:
        c, _ = _lancer(banc, exp, OccupeeKglobal(3))
    finally:
        logger.remove(sink)
    assert c["etat"] == "terminee"
    alarmes = [m for m in msgs if "[ALARME]" in m and "on continue d'attendre" in m]
    assert len(alarmes) == 1, (
        "front montant : une alarme pour le déplacement, pas une par tentative"
    )


def test_R1_interruption_pendant_attente_puis_reprise(banc, monkeypatch):
    monkeypatch.setattr(runner, "_dormir_interruptible", _dormir_rapide)
    exp = _exp(banc, regroupement={"parallelisme": 1})
    exe = _execution(banc, exp)
    controle = Controle(exe.dossier)

    class OccupeePuisPause(DecideurDureeMinimale):
        async def choisir(self, person, ctx, presentees):
            controle.pause = True  # pause demandée pendant une attente transitoire
            return D.ReponseDecideur(
                index=None, fournisseur="g1", erreur="passerelle_occupee: saturés"
            )

    c, _ = _lancer(banc, exp, OccupeePuisPause(), execution=exe, controle=controle)
    assert c["etat"] == "en_pause"
    assert (
        len(A.Execution.ouvrir(exe.dossier).decisions) == 0
    )  # rien archivé : déplacement non décidé
    # reprise avec un décideur qui décide → complète, sans saut
    c2, _ = _lancer(
        banc,
        exp,
        DecideurCompteur(),
        execution=A.Execution.ouvrir(exe.dossier),
        controle=Controle(exe.dossier),
    )
    assert (
        c2["etat"] == "terminee" and len(A.Execution.ouvrir(exe.dossier).decisions) == 3
    )


def test_R3_erreurs_jsonl_tracee(banc, monkeypatch):
    monkeypatch.setattr(runner, "_dormir_interruptible", _dormir_rapide)
    exp = _exp(banc, regroupement={"parallelisme": 1})
    _, exe = _lancer(banc, exp, OccupeeNfois(2))
    lignes = (exe.dossier / "erreurs.jsonl").read_text(encoding="utf-8").splitlines()
    assert lignes
    e = json.loads(lignes[0])
    assert {
        "horodatage",
        "person_id",
        "activity_id",
        "tentative",
        "type",
        "message",
        "fournisseur",
        "attente_s",
    } <= set(e)
    assert e["type"] == "passerelle_occupee" and e["fournisseur"] == "g1"


def test_R3_commande_erreurs_detecte_trou(banc):
    _, ref = _lancer(banc, _exp(banc, nom="ref_trou"))
    par_cle = {(t["person_id"], t["activity_id"]): t for t in ref.decisions}
    exe = _execution(banc, _exp(banc, nom="avec_trou"))
    exe.ajouter_decision(
        par_cle[("p3", "a2")]
    )  # 2e journée de p3, SANS la 1re (a1) → trou de chaîne
    exe.ajouter_decision(par_cle[("p2", "b1")])
    exe.fermer()
    diag = ERR.diagnostiquer(exe.dossier)
    assert (
        diag["nb_manquants"] == 1
        and diag["deplacements_manquants"][0]["activity_id"] == "a1"
    )
    assert diag["journees_a_trous"] == ["p3"] and diag["decisions_apres_trou"] == 1
    assert "manquant" in ERR.formater(diag)


def test_R3_arret_force_consigne_a_la_reprise(banc):
    exp = _exp(banc)
    exe = _execution(banc, exp)
    _, ref = _lancer(banc, _exp(banc, nom="ref_af"))
    par_cle = {(t["person_id"], t["activity_id"]): t for t in ref.decisions}
    exe.ajouter_decision(par_cle[("p2", "b1")])
    exe.fermer()
    exe.changer_etat(A.ETAT_EN_COURS)  # laissée `en_cours` = processus tué sans clôture
    c, _ = _lancer(
        banc, exp, DecideurCompteur(), execution=A.Execution.ouvrir(exe.dossier)
    )
    causes = [
        i["cause"] for i in A.Execution.ouvrir(exe.dossier).config["interruptions"]
    ]
    assert "arret_force" in causes and c["etat"] == "terminee"


class MoniteurBascule:
    """Épuisé jusqu'à `ouvre_a`, puis disponible — pour éprouver l'attente de fenêtre (R4)."""

    def __init__(self, ouvre_a):
        self.ouvre_a = ouvre_a
        self.compteurs = {"substitution_refusee": 0}

    @property
    def ouvert(self):
        return datetime.now(timezone.utc) >= self.ouvre_a

    def rafraichir(self):
        pass

    def epuise(self, besoin=1):
        return not self.ouvert

    def instances_disponibles(self, besoin=1):
        return ["g1"] if self.ouvert else []

    def tableau(self):
        return []


def test_R4_attendre_fenetre_quota_reprend_seul(banc, monkeypatch):
    ouvre_a = datetime.now(timezone.utc) + timedelta(seconds=0.6)
    monkeypatch.setattr(
        runner, "prochaine_fenetre_quota", lambda *a, **k: ouvre_a.isoformat()
    )
    m = MoniteurBascule(ouvre_a)

    class EpuisePuisOuvre(DecideurDureeMinimale):
        sans_quota = False

        async def choisir(self, person, ctx, presentees):
            if not m.ouvert:
                return D.ReponseDecideur(
                    index=None,
                    fournisseur="",
                    erreur="epuise: g1 : 500/500 requêtes/jour",
                )
            return await super().choisir(person, ctx, presentees)

    exp = _exp(banc, regroupement={"parallelisme": 1})
    msgs = []
    sink = logger.add(lambda x: msgs.append(str(x)), level="ERROR")
    try:
        c, exe = _lancer(
            banc, exp, EpuisePuisOuvre(), moniteur=m, attendre_fenetre=True
        )
    finally:
        logger.remove(sink)
    assert (
        c["etat"] == "terminee" and len(exe.decisions) == 3
    )  # a attendu la fenêtre, puis tout décidé
    assert any("[ALARME]" in x and "attente de la fenêtre quota" in x for x in msgs)


def test_R4_sans_attendre_fenetre_reste_epuisee(banc):
    """Avec `--ne-pas-attendre-fenetre`, l'épuisement confirmé arrête l'exécution (Q4).

    Ce fut le défaut jusqu'au 2026-09-08 ; c'est désormais l'attente qui l'est, l'arrêt
    immédiat se demandant explicitement.
    """
    m = _moniteur(
        {
            "g1": {"daily_requests": 500, "rpd_limit": 500, "quota_exhausted": True},
            "g2": {"daily_requests": 500, "rpd_limit": 500, "quota_exhausted": True},
        }
    )

    class Epuise(DecideurDureeMinimale):
        sans_quota = False

        async def choisir(self, person, ctx, presentees):
            return D.ReponseDecideur(
                index=None, erreur="epuise: g2 : 500/500 requêtes/jour"
            )

    exp = _exp(banc, regroupement={"parallelisme": 1})
    c, exe = _lancer(banc, exp, Epuise(), moniteur=m, attendre_fenetre=False)
    assert c["etat"] == "epuisee" and not exe.cloturee


# ── la veille des quotas tourne pendant le run ───────────────────────────────
# `moniteur.etat` ne se relisait qu'au DÉMARRAGE : une clé épuisée en cours de route restait
# « disponible », le décideur continuait de l'épingler et la clé suivante n'était jamais
# entamée (2026-09-08 : run arrêté à 70,5 % avec 500 requêtes intactes en réserve).


def _moniteur_compteur(lectures: list, etat=None, dort: float = 0.0):
    from experiences.ressources import MoniteurRessources

    def lecteur(_url):
        if dort:
            time.sleep(dort)
        lectures.append(time.monotonic())
        return etat if etat is not None else {"cle1": {"daily_requests": len(lectures)}}

    return MoniteurRessources(
        ["cle1"], {"cle1": {"rpd_limit": 500}}, base_url="http://x", lecteur=lecteur
    )


class DecideurLent(DecideurDureeMinimale):
    """Assez lent pour que la veille ait le temps de faire plusieurs tours."""

    async def choisir(self, person, ctx, presentees):
        await asyncio.sleep(0.05)
        return await super().choisir(person, ctx, presentees)


def test_les_quotas_sont_relus_PENDANT_le_run_pas_seulement_au_demarrage(banc, monkeypatch):
    monkeypatch.setattr(runner, "RAFRAICHIR_QUOTAS_S", 0.01)
    lectures: list = []
    moniteur = _moniteur_compteur(lectures)

    exp = _exp(banc, regroupement={"parallelisme": 1})
    c, _ = _lancer(banc, exp, DecideurLent(), moniteur=moniteur)

    assert c["etat"] == "terminee", c["etat"]
    assert len(lectures) > 1, (
        f"la veille n'a pas tourné : {len(lectures)} lecture(s) de /health — le correctif "
        f"ne tient qu'à la tâche `veiller_quotas`, dont l'oubli ne casse rien d'autre"
    )


def test_la_veille_desactivee_ne_lit_rien_de_plus_que_le_demarrage(banc, monkeypatch):
    """`EXP_RAFRAICHIR_QUOTAS_S=0` doit vraiment tout couper (réglage d'exploitation)."""
    monkeypatch.setattr(runner, "RAFRAICHIR_QUOTAS_S", 0.0)
    lectures: list = []
    moniteur = _moniteur_compteur(lectures)

    exp = _exp(banc, regroupement={"parallelisme": 1})
    _lancer(banc, exp, DecideurLent(), moniteur=moniteur)

    assert lectures == [], f"aucune lecture attendue hors démarrage, vu {len(lectures)}"


def test_une_passerelle_lente_ne_retarde_pas_la_pause(banc, monkeypatch):
    """La lecture de `/health` est un appel HTTP bloquant (jusqu'à 5 s) : sans `to_thread`
    elle figerait la boucle d'événements, donc la grâce de pause et le chien de garde."""
    monkeypatch.setattr(runner, "RAFRAICHIR_QUOTAS_S", 0.01)
    monkeypatch.setattr(runner, "PAS_ATTENTE_S", 0.01)
    lectures: list = []
    # 1 s de blocage : bien au-delà de la grâce (0,05 s), donc le retard se mesure.
    moniteur = _moniteur_compteur(lectures, dort=1.0)

    exp = _exp(banc, regroupement={"parallelisme": 1})
    exe = _execution(banc, exp)

    class PauseParFichier(DecideurLent):
        async def choisir(self, person, ctx, presentees):
            (exe.dossier / "PAUSE").touch()
            return await super().choisir(person, ctx, presentees)

    c, _ = _lancer(banc, exp, PauseParFichier(), execution=exe, moniteur=moniteur,
                   controle=runner.Controle(exe.dossier, grace_s=0.05))

    assert c["etat"] == "en_pause", c["etat"]
    # La durée du RUN, pas celle de `_lancer` : `asyncio.run` attend en sortant les threads
    # de son executor, donc la lecture lente allonge le retour même quand elle est correcte.
    assert c["duree_s"] < 0.5, (
        f"le run a duré {c['duree_s']:.1f} s alors que /health bloque 1 s : la boucle "
        f"d'événements a été figée par la lecture des quotas (to_thread manquant)"
    )

