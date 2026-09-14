"""Ticket 070, première tranche — l'interrupteur d'accidents et le tirage.

Un test par règle de `specs/accidents-interrupteur-gama.md`, le numéro de la règle dans le
nom. Les règles R1 et R3 portent sur l'IHM GAMA et sa persistance : elles se vérifient sur le
texte des modèles `.gaml`, qu'aucun test Python ne peut exécuter — c'est une vérification de
présence, et elle est déclarée comme telle plutôt qu'omise.
"""

from __future__ import annotations

import pathlib

import pytest
from settings import AccidentsConfig
from trip_helper import accidents as accidents_module
from trip_helper.accidents import (
    Accident,
    LoiBaac,
    RegistreAccidents,
    classe_de_vitesse,
    jour_simule,
)

MODELES = (
    pathlib.Path(__file__).resolve().parents[3]
    / "services"
    / "GAMA"
    / "CityTransport"
    / "models"
)
JOUR = 86400
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
T0 = 1_773_637_200  # un lundi 05:00 simulé, comme le démarrage de référence


class GrapheFactice:
    """Un graphe minimal : des arêtes, une longueur, une vitesse autorisée."""

    def __init__(self, aretes):
        self._aretes = aretes

    def edges(self, data=False):
        if data:
            return [
                (u, v, {"length": lg, "maxspeed": vit})
                for u, v, lg, vit in self._aretes
            ]
        return [(u, v) for u, v, _, _ in self._aretes]


# Trois arêtes de la classe 31-50, de longueurs très inégales, plus une arête rapide : de quoi
# vérifier que la classe se tire sur la loi et l'arête au prorata de sa longueur DANS la classe.
ARETES = [(1, 2, 1000.0, 50), (2, 3, 500.0, 50), (3, 4, 2500.0, 50), (4, 5, 800.0, 80)]


def _registre(
    taux=None, graine=70, loi=None, aretes=ARETES, **kwargs
) -> RegistreAccidents:
    config = AccidentsConfig(
        enabled=True, taux_journalier=taux, graine=graine, **kwargs
    )
    registre = RegistreAccidents(config=config, loi=loi)
    registre.charger_aretes(GrapheFactice(aretes))
    return registre


@pytest.fixture(autouse=True)
def _registre_propre():
    """Aucun test ne doit hériter du registre d'un autre."""
    accidents_module.reinitialiser()
    yield
    accidents_module.reinitialiser()


# ── R1 / R3 — l'interrupteur dans l'IHM GAMA et sa persistance ───────────────


def test_r1_interrupteur_expose_dans_l_ihm_gama():
    """R1 — un paramètre « Accidents sur les axes », catégorie Simulation."""
    city = (MODELES / "City.gaml").read_text(encoding="utf-8")
    assert 'parameter "Accidents sur les axes"' in city
    assert 'category: "Simulation" var: accidents_enabled' in city


def test_r3_interrupteur_persiste_et_recharge():
    """R3 — écrit dans sim_params.yaml et relu au démarrage."""
    settings_gaml = (MODELES / "Settings.gaml").read_text(encoding="utf-8")
    assert '"accidents_enabled: " + string(accidents_enabled)' in settings_gaml, (
        "non écrit"
    )
    assert "accidents_enabled <- (_cfg_acc != nil)" in settings_gaml, "non relu"


def test_r2_faux_par_defaut_partout():
    """R2 — faux par défaut côté GAMA comme côté contrôleur."""
    settings_gaml = (MODELES / "Settings.gaml").read_text(encoding="utf-8")
    assert "bool accidents_enabled <- false;" in settings_gaml
    # Et le repli de lecture ne remonte jamais à vrai sur configuration absente.
    assert 'contains "true") : false;' in settings_gaml
    assert AccidentsConfig().enabled is False


def test_r4_interrupteur_transmis_au_init():
    """R4 — la charge utile du /init porte `accidents_enabled`."""
    llm_agent = (MODELES / "LLMAgent.gaml").read_text(encoding="utf-8")
    assert '"accidents_enabled"::accidents_enabled' in llm_agent

    from gama_models import WorldInitRequest

    requete = WorldInitRequest(timestamp=T0, accidents_enabled=True)
    assert requete.accidents_enabled is True
    # Absent de la requête ≠ désactivé : le contrôleur doit pouvoir distinguer les deux.
    assert WorldInitRequest(timestamp=T0).accidents_enabled is None


def test_r5_etat_effectif_ecrit_meme_a_faux(tmp_path, monkeypatch):
    """R5 — `scenario_params.yaml` porte l'état, y compris quand il vaut faux."""
    import types

    import yaml
    from urban_mobility_agents.factory import factory

    # `settings` est un proxy `FactorySettings` : lui assigner `workdir` ne change rien —
    # l'assignation n'atteint pas l'objet sous-jacent (vérifié). On remplace donc le nom que
    # le module lit, que `getattr(settings, "workdir")` résout à l'appel.
    monkeypatch.setattr(factory, "settings", types.SimpleNamespace(workdir=tmp_path))
    factory._save_scenario_params(
        population_size=10,
        llm_agents=10,
        long_term_memory_enabled=True,
        long_term_self_reflect_enabled=True,
        accidents_enabled=False,
    )
    ecrit = yaml.safe_load(
        (tmp_path / "scenario_params.yaml").read_text(encoding="utf-8")
    )
    assert "accidents_enabled" in ecrit, "un run silencieux sur le régime est illisible"
    assert ecrit["accidents_enabled"] is False


# ── R6 / R7 — ce que l'interrupteur commande ─────────────────────────────────


def test_r6_interrupteur_a_faux_ne_tire_rien(monkeypatch):
    """R6 — régime inactif : aucun registre, donc aucun accident."""
    from settings import settings

    monkeypatch.setattr(settings.accidents, "enabled", False)
    assert accidents_module.initialiser() is None
    assert accidents_module.registre() is None


def test_r7_interrupteur_a_vrai_tire_des_accidents_poses_sur_une_arete():
    """R7 — chaque accident porte une arête, un début et une durée."""
    registre = _registre(taux=5.0)
    poses = registre.tirer_journee(jour=1, debut_jour_ts=T0)

    assert poses, "un taux de 5/jour doit produire des accidents"
    for accident in poses:
        assert accident.arete in {(1, 2), (2, 3), (3, 4), (4, 5)}
        assert accident.classe_vitesse in {"31-50", "71-90"}
        assert T0 <= accident.debut_ts < T0 + JOUR
        assert accident.duree_s > 0
        assert accident.fin_ts == accident.debut_ts + accident.duree_s


def test_r7_tirage_idempotent_par_journee():
    """R7 — appelé à chaque sync, le tirage ne produit la journée qu'une fois."""
    registre = _registre(taux=5.0)
    premier = registre.tirer_journee(jour=1, debut_jour_ts=T0)
    second = registre.tirer_journee(jour=1, debut_jour_ts=T0)
    assert second == []
    assert len(registre.accidents) == len(premier)


def test_r7_tirage_deterministe_a_graine_fixee():
    """R7 — deux runs du même scénario posent les mêmes accidents."""
    a = _registre(taux=5.0, graine=70).tirer_journee(1, T0)
    b = _registre(taux=5.0, graine=70).tirer_journee(1, T0)
    assert a == b
    autre = _registre(taux=5.0, graine=71).tirer_journee(1, T0)
    assert autre != a, "une graine différente doit produire un autre monde"


def test_r7_arete_tiree_proportionnellement_a_sa_longueur_dans_sa_classe():
    """R7 — à classe égale, l'arête de 2 500 m est touchée plus souvent que celle de 500 m."""
    registre = _registre(taux=40.0, graine=1)
    for jour in range(1, 40):
        registre.tirer_journee(jour, T0 + (jour - 1) * JOUR)
    comptes = {}
    for accident in registre.accidents:
        comptes[accident.arete] = comptes.get(accident.arete, 0) + 1
    assert comptes.get((3, 4), 0) > comptes.get((2, 3), 0), (
        "le tirage ignore la longueur à l'intérieur d'une classe : la géographie des "
        f"accidents serait celle du découpage OSM, pas du réseau — {comptes}"
    )


# ── R11 / R12 / R13 — les règles déduites ────────────────────────────────────


def test_r11_compteurs_publies_meme_a_zero(caplog):
    """R11 — une journée sans accident le dit, sinon elle ressemble à une panne."""
    registre = _registre(taux=0.0001, graine=3)
    registre.tirer_journee(jour=1, debut_jour_ts=T0)
    compteurs = registre.compteurs
    assert len(compteurs) == 1, "la journée doit être comptée même vide"
    assert compteurs[0].jour == 1
    assert compteurs[0].tires == 0


def test_r12_accident_de_duree_nulle_est_refuse():
    """R12 — refusé à la pose, et rien n'entre dans l'état du monde."""
    registre = _registre()
    assert registre._poser(Accident(arete=(1, 2), debut_ts=T0, duree_s=0)) is False
    assert registre.accidents == []


def test_r12_accident_sur_arete_inconnue_est_refuse():
    """R12 — une arête absente du graphe ne peut pas porter d'accident."""
    registre = _registre()
    assert registre._poser(Accident(arete=(99, 98), debut_ts=T0, duree_s=600)) is False
    assert registre.accidents == []


def test_r12_taux_hors_bornes_ne_tire_rien():
    """R12 — un taux aberrant est refusé plutôt que subi."""
    assert _registre(taux=0.0).tirer_journee(1, T0) == []
    assert _registre(taux=10_000.0).tirer_journee(1, T0) == []


def test_r13_journee_simulee_ancree_sur_le_debut_du_run():
    """R13 — le découpage en journées ne dépend que du début du run."""
    assert jour_simule(T0, T0) == (1, T0)
    assert jour_simule(T0 + JOUR - 1, T0) == (1, T0)
    assert jour_simule(T0 + JOUR, T0) == (2, T0 + JOUR)
    assert jour_simule(T0 + 3 * JOUR + 7200, T0) == (4, T0 + 3 * JOUR)


# ── Non-goal vérifié : aucune durée n'est modifiée par cette tranche ─────────


def test_aucune_duree_d_itineraire_n_est_modifiee_par_cette_tranche():
    """Le registre n'est lu par aucun calcul d'itinéraire — c'est ce qui rend les caches sûrs.

    Si ce test tombe, c'est que le retard a été branché : il faut alors que les gardes de
    cache (R9) et la clé de décision (R10) soient livrées EN MÊME TEMPS, sans quoi une durée
    perturbée se retrouve resservie à des runs qui n'ont rien demandé.
    """
    osmnx = (
        pathlib.Path(__file__).resolve().parents[1] / "trip_helper" / "osmnx_direct.py"
    )
    source = osmnx.read_text(encoding="utf-8")
    assert "accidents" not in source, (
        "osmnx_direct lit désormais les accidents : livrez les gardes de cache (R9) et la "
        "clé de décision (R10) dans la même tranche."
    )


def test_accident_actif_sur_sa_fenetre_seulement():
    """La fenêtre est semi-ouverte : l'instant de fin n'est plus actif."""
    accident = Accident(arete=(1, 2), debut_ts=T0, duree_s=600)
    assert accident.actif_a(T0) is True
    assert accident.actif_a(T0 + 599) is True
    assert accident.actif_a(T0 + 600) is False
    assert accident.actif_a(T0 - 1) is False


# ── Travail A — le tirage est conditionné aux statistiques BAAC ──────────────


def test_loi_baac_livree_est_coherente():
    """La loi du dépôt somme à 1 là où il faut, et ses facteurs ont pour moyenne 1.

    C'est ce qui garantit que le taux de base RESTE le taux moyen : un facteur de moyenne
    1,2 multiplierait discrètement tous les runs par 1,2.
    """
    loi = LoiBaac.charger()
    assert 0.99 <= sum(loi.distribution_horaire.values()) <= 1.01
    assert 0.99 <= sum(loi.distribution_classe_vitesse.values()) <= 1.01
    moyenne_jours = sum(loi.facteur_jour_semaine.values()) / 7
    assert 0.99 <= moyenne_jours <= 1.01
    assert len(loi.distribution_horaire) == 24
    assert loi.taux_base_par_jour > 0


def test_loi_incoherente_est_refusee():
    """Une distribution qui ne somme pas à 1 doit lever, pas tirer en silence."""
    with pytest.raises(ValueError, match="somme à"):
        LoiBaac(
            taux_base_par_jour=1.5,
            distribution_horaire={h: 0.01 for h in range(24)},  # somme 0,24
            facteur_jour_semaine={j: 1.0 for j in JOURS},
            distribution_classe_vitesse={"31-50": 1.0},
            facteur_meteo={},
            facteur_meteo_etabli=False,
            millesimes=[],
        ).verifier()


def test_heure_suit_la_distribution_mesuree_et_non_l_uniforme():
    """Le conditionnement le plus marqué : 17 h doit dominer 3 h, nettement.

    Sans lui, le tirage uniforme de la première tranche plaçait autant d'accidents à 3 h
    du matin qu'à la pointe du soir.
    """
    registre = _registre(taux=30.0, graine=5)
    for jour in range(1, 60):
        registre.tirer_journee(jour, T0 + (jour - 1) * JOUR)
    heures = [(a.debut_ts - T0) % JOUR // 3600 for a in registre.accidents]
    assert len(heures) > 500, "échantillon trop petit pour conclure"
    creux = sum(1 for h in heures if h == 3)
    pointe = sum(1 for h in heures if h == 17)
    assert pointe > 3 * max(creux, 1), (
        f"la pointe de 17 h ({pointe}) ne domine pas le creux de 3 h ({creux}) : "
        "le tirage horaire est probablement resté uniforme"
    )


def test_le_nombre_depend_du_jour_de_semaine():
    """Vendredi (×1,19) doit produire plus d'accidents que dimanche (×0,83)."""
    loi = LoiBaac.charger()
    assert loi.facteur_jour_semaine["vendredi"] > loi.facteur_jour_semaine["dimanche"]

    # T0 est un lundi 05:00 : on cale sur le vendredi et le dimanche de la même semaine.
    vendredi_ts = T0 + 4 * JOUR
    dimanche_ts = T0 + 6 * JOUR
    registre = _registre(taux=20.0, graine=11)
    taux_vendredi = registre._taux_du_jour(
        accidents_module.wall_clock(vendredi_ts).weekday(), None
    )
    taux_dimanche = registre._taux_du_jour(
        accidents_module.wall_clock(dimanche_ts).weekday(), None
    )
    assert taux_vendredi > taux_dimanche


def test_la_classe_d_axe_suit_baac_et_non_la_longueur_du_reseau():
    """Le résultat qui justifie tout le travail A.

    Le réseau simulé est à 58 % en zone apaisée (≤ 30 km/h), qui ne porte que 8 % des
    accidents réels. Un tirage au seul prorata de la longueur y placerait donc la majorité
    des accidents. Avec la loi, la classe 31-50 — 57 % des accidents réels — doit dominer
    alors qu'elle ne pèse qu'un tiers des kilomètres.
    """
    aretes = [
        (1, 2, 58_000.0, 30),  # zone apaisée : 58 % des mètres
        (2, 3, 34_000.0, 50),  # urbain : 34 % des mètres
        (3, 4, 8_000.0, 80),  # voie rapide : 8 % des mètres
    ]
    registre = _registre(taux=30.0, graine=7, aretes=aretes)
    for jour in range(1, 60):
        registre.tirer_journee(jour, T0 + (jour - 1) * JOUR)

    comptes = {}
    for a in registre.accidents:
        comptes[a.classe_vitesse] = comptes.get(a.classe_vitesse, 0) + 1
    total = sum(comptes.values())
    assert total > 500, "échantillon trop petit pour conclure"
    part_apaisee = comptes.get("<=30", 0) / total
    part_urbaine = comptes.get("31-50", 0) / total
    assert part_urbaine > part_apaisee, (
        f"la classe 31-50 ({part_urbaine:.1%}) ne domine pas la zone apaisée "
        f"({part_apaisee:.1%}) alors qu'elle porte 57 % des accidents réels pour 34 % des "
        "mètres : le tirage suit probablement encore la longueur seule"
    )
    assert part_apaisee < 0.20, (
        f"{part_apaisee:.1%} des accidents en zone apaisée, contre 8 % dans BAAC"
    )


def test_facteur_meteo_reste_neutre_tant_qu_il_n_est_pas_etabli():
    """Le facteur météo mesuré a été REJETÉ : il ne doit rien multiplier.

    Si ce test tombe parce que `facteur_meteo_etabli` est passé à vrai, c'est qu'une
    nouvelle estimation a été versée — elle doit alors venir avec sa source d'exposition
    découpée comme `atm`, ou avec un risque relatif déclaré exogène.
    """
    loi = LoiBaac.charger()
    assert loi.facteur_meteo_etabli is False
    assert all(v == 1.0 for v in loi.facteur_meteo.values())

    registre = _registre(taux=10.0)
    lundi = accidents_module.wall_clock(T0).weekday()
    assert registre._taux_du_jour(lundi, "pluie forte") == registre._taux_du_jour(
        lundi, None
    )


def test_classe_de_vitesse_tolere_les_formes_osm():
    """OSM écrit la vitesse de plusieurs façons : liste, chaîne, unité, absence."""
    assert classe_de_vitesse(50) == "31-50"
    assert classe_de_vitesse("50") == "31-50"
    assert classe_de_vitesse("50 km/h") == "31-50"
    assert classe_de_vitesse(["80", "90"]) == "71-90"
    assert classe_de_vitesse(30) == "<=30"
    assert classe_de_vitesse(130) == ">90"
    assert classe_de_vitesse(None) is None
    assert classe_de_vitesse("") is None
    assert classe_de_vitesse(0) is None
    assert classe_de_vitesse(500) is None


def test_surcharge_de_taux_remplace_la_mesure():
    """`taux_journalier` non nul court-circuite la loi — réservé au développement."""
    registre_mesure = _registre(taux=None)
    registre_force = _registre(taux=50.0)
    lundi = accidents_module.wall_clock(T0).weekday()
    assert registre_force._taux_du_jour(lundi, None) > registre_mesure._taux_du_jour(
        lundi, None
    )
