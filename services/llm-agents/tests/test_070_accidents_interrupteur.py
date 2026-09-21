"""Ticket 070, première tranche — l'interrupteur d'accidents et le tirage.

Un test par règle de `specs/accidents-interrupteur-gama.md`, le numéro de la règle dans le
nom. Les règles R1 et R3 portent sur l'IHM GAMA et sa persistance : elles se vérifient sur le
texte des modèles `.gaml`, qu'aucun test Python ne peut exécuter — c'est une vérification de
présence, et elle est déclarée comme telle plutôt qu'omise.
"""

from __future__ import annotations

import pathlib
from datetime import datetime, timezone

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


def test_r2_vrai_par_defaut_partout():
    """R2 — vrai par défaut côté GAMA comme côté contrôleur (décision du 2026-09-15).

    Le régime réaliste est l'ordinaire : c'est sa DÉSACTIVATION qui demande un geste. Un
    `sim_params.yaml` antérieur, sans la clé, doit donc activer les accidents et non les taire.
    """
    settings_gaml = (MODELES / "Settings.gaml").read_text(encoding="utf-8")
    assert "bool accidents_enabled <- true;" in settings_gaml
    assert 'contains "true") : true;' in settings_gaml, "le repli sur config absente doit valoir vrai"
    city = (MODELES / "City.gaml").read_text(encoding="utf-8")
    assert "var: accidents_enabled <- true;" in city
    assert AccidentsConfig().enabled is True


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
    """R6 — régime explicitement désactivé : aucun registre, donc aucun accident.

    Depuis que le défaut est à vrai, ce test doit DÉSACTIVER explicitement : c'est le geste
    de l'expérimentateur qui décoche, et c'est lui qu'on vérifie.
    """
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


# ── R8 / R9 / R10 — le retard subi et ses deux gardes ────────────────────────


def _gdf(aretes, travel_times):
    """Une sortie de `route_to_gdf` minimale : un index (u, v, k) et une colonne travel_time."""
    import pandas as pd

    index = pd.MultiIndex.from_tuples([(u, v, 0) for u, v in aretes])
    return pd.DataFrame({"travel_time": travel_times}, index=index)


class _GrapheZones:
    """Un graphe réduit à ce que `_congested_travel_time` lui demande : la zone de ses nœuds."""

    def __init__(self, noeuds):
        from trip_helper.congestion_zones import NODE_ZONE_KEY, ZONE_OUTSIDE

        self.nodes = {n: {NODE_ZONE_KEY: ZONE_OUTSIDE} for n in noeuds}


def test_r8_itineraire_traversant_un_accident_est_allonge(monkeypatch):
    """R8 — la durée rendue est strictement supérieure, et l'arête fautive est comptée."""
    from trip_helper import accidents as mod
    from trip_helper.osmnx_direct import _congested_travel_time

    registre = _registre(taux=5.0)
    registre.tirer_journee(1, T0)
    assert registre._poser(
        Accident(arete=(2, 3), debut_ts=T0, duree_s=3600, classe_vitesse="31-50")
    )
    monkeypatch.setattr(mod, "_registre", registre)

    cong_s, free_s, n_acc = _congested_travel_time(
        _GrapheZones([1, 2, 3, 4]),
        _gdf([(1, 2), (2, 3), (3, 4)], [100.0, 200.0, 100.0]),
        datetime.fromtimestamp(T0 + 600, tz=timezone.utc),
    )

    assert free_s == 400.0
    assert n_acc == 1, "l'arête accidentée n'a pas été reconnue"
    attendu = 100.0 + 200.0 * AccidentsConfig().facteur_ralentissement + 100.0
    assert cong_s == pytest.approx(attendu)
    assert cong_s > free_s


def test_r8_itineraire_hors_accident_est_inchange(monkeypatch):
    """R8 — un itinéraire qui ne croise rien garde sa durée libre."""
    from trip_helper import accidents as mod
    from trip_helper.osmnx_direct import _congested_travel_time

    registre = _registre(taux=5.0)
    registre.tirer_journee(1, T0)
    registre._poser(Accident(arete=(1, 2), debut_ts=T0, duree_s=3600))
    monkeypatch.setattr(mod, "_registre", registre)

    cong_s, free_s, n_acc = _congested_travel_time(
        _GrapheZones([2, 3, 4]),
        _gdf([(2, 3), (3, 4)], [100.0, 100.0]),
        datetime.fromtimestamp(T0 + 600, tz=timezone.utc),
    )
    assert n_acc == 0
    assert cong_s == pytest.approx(free_s)


def test_r8_accident_expire_ne_ralentit_plus(monkeypatch):
    """R8 — hors de sa fenêtre, l'accident n'a plus d'effet."""
    from trip_helper import accidents as mod
    from trip_helper.osmnx_direct import _congested_travel_time

    registre = _registre(taux=5.0)
    registre.tirer_journee(1, T0)
    registre._poser(Accident(arete=(1, 2), debut_ts=T0, duree_s=600))
    monkeypatch.setattr(mod, "_registre", registre)

    _cong, _free, n_acc = _congested_travel_time(
        _GrapheZones([1, 2]),
        _gdf([(1, 2)], [100.0]),
        datetime.fromtimestamp(T0 + 1200, tz=timezone.utc),
    )
    assert n_acc == 0


def test_r9_le_cache_d_itineraires_est_contourne_pendant_un_accident():
    """R9 — ni lecture ni écriture tant qu'un accident est actif.

    Le prédicat est exercé ici ; le fait que la garde soit BRANCHÉE dessus se vérifie sur le
    texte du module — le chemin complet est asynchrone et tient au réseau, il n'est pas
    exerçable en test unitaire. Vérification de présence, déclarée comme telle.
    """
    registre = _registre(taux=5.0)
    registre.tirer_journee(1, T0)
    registre._poser(Accident(arete=(1, 2), debut_ts=T0 + 3600, duree_s=1800))

    assert registre.a_des_accidents_actifs(T0 + 4000) is True
    assert registre.a_des_accidents_actifs(T0) is False, "avant l'accident"
    assert registre.a_des_accidents_actifs(T0 + 7200) is False, "après l'accident"

    source = (
        pathlib.Path(__file__).resolve().parents[1] / "trip_helper" / "osmnx_direct.py"
    ).read_text(encoding="utf-8")
    assert "_reg.a_des_accidents_actifs(" in source
    assert "if _persistent_cache is not None and not _accidents_actifs:" in source, (
        "la garde n'est pas branchée sur le prédicat : une durée perturbée peut entrer au cache"
    )


def test_r10_la_cle_de_decision_porte_les_accidents_actifs():
    """R10 — deux états du monde distincts donnent deux signatures distinctes."""
    registre = _registre(taux=5.0)
    registre.tirer_journee(1, T0)
    assert registre.signature_active(T0 + 600) == "", "aucun accident posé : signature vide"

    registre._poser(Accident(arete=(1, 2), debut_ts=T0, duree_s=3600))
    avec = registre.signature_active(T0 + 600)
    assert avec, "un accident actif doit produire une signature"
    assert registre.signature_active(T0 + 7200) == "", "hors fenêtre : signature vide"

    registre._poser(Accident(arete=(3, 4), debut_ts=T0, duree_s=3600))
    assert registre.signature_active(T0 + 600) != avec, "deux accidents ≠ un accident"

    agent = (
        pathlib.Path(__file__).resolve().parents[1]
        / "urban_mobility_agents"
        / "agents"
        / "llm_agent.py"
    ).read_text(encoding="utf-8")
    assert 'anticipation_key = f"{anticipation_key}|accidents:{_sig}"' in agent, (
        "la signature n'entre pas dans la clé : un agent retardé se verrait resservir sa "
        "décision d'avant le retard"
    )


def test_le_retard_et_ses_deux_gardes_sont_livres_ensemble():
    """Le bloc C/D/E est indivisible, et ce test le garde.

    Livrer le retard sans la garde du cache d'itinéraires empoisonnerait des runs qui n'ont
    demandé aucun accident ; sans la clé de décision, un agent retardé rejouerait son choix
    d'avant. Si l'un des trois disparaît, ce test tombe.
    """
    racine = pathlib.Path(__file__).resolve().parents[1]
    osmnx = (racine / "trip_helper" / "osmnx_direct.py").read_text(encoding="utf-8")
    agent = (racine / "urban_mobility_agents" / "agents" / "llm_agent.py").read_text(
        encoding="utf-8"
    )
    assert "registre.facteur_arete((u, v), ts)" in osmnx, "C — le retard a disparu"
    assert "not _accidents_actifs" in osmnx, "D — la garde du cache d'itinéraires a disparu"
    assert "accidents:{_sig}" in agent, "E — la clé de décision a disparu"


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


def test_facteur_meteo_est_neutre_par_decision():
    """La météo ne conditionne PAS l'accidentalité — décision de l'auteur du 2026-09-21.

    Ce n'est pas un chantier remis à plus tard mais une limite assumée, et elle tient à un
    fait mesuré : les conditions à risque n'existent pas dans le monde simulé. Sur les 2 920
    créneaux d'une année servie par `weather_loader`, le brouillard en occupe UN et la neige
    QUATRE — un facteur pour ces conditions ne se déclencherait jamais. Pour celles qui
    restent, les nomenclatures `atm` et météo locale sont incommensurables.

    Si ce test tombe parce que `facteur_meteo_etabli` est passé à vrai, la seule chose qui
    puisse le justifier est un jeu météo servi à la simulation qui porte réellement ces
    conditions — pas une nouvelle correspondance ajustée sur les mêmes données.
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


# ── F — la pose manuelle, d'où viendront les figures ─────────────────────────


def test_f_pose_manuelle_accroche_l_arete_la_plus_proche():
    """F — un point se résout en arête, et l'accident entre dans le même registre."""
    aretes = [
        (1, 2, 1000.0, 50),
        (2, 3, 1000.0, 50),
        (3, 4, 1000.0, 80),
    ]
    registre = _registre(taux=5.0, aretes=aretes)
    registre._positions = {1: (43.60, 1.44), 2: (43.57, 1.43), 3: (43.50, 1.40), 4: (43.40, 1.30)}
    registre.tirer_journee(1, T0)
    avant = len(registre.accidents)

    pose = registre.poser_manuellement(lat=43.5701, lon=1.4301, debut_ts=T0 + 3 * 3600, duree_minutes=45)

    assert pose is not None
    assert pose.arete == (2, 3), f"arête la plus proche mal choisie : {pose.arete}"
    assert pose.duree_s == 45 * 60
    assert len(registre.accidents) == avant + 1, "l'accident posé doit entrer dans le registre"
    # Et il agit exactement comme un accident tiré : même fenêtre, même facteur.
    assert registre.facteur_arete((2, 3), T0 + 3 * 3600 + 60) > 1.0
    assert registre.facteur_arete((2, 3), T0) == 1.0


def test_f_pose_manuelle_refuse_une_duree_non_positive():
    """F — refus journalisé, et rien n'entre dans l'état du monde."""
    registre = _registre(taux=5.0)
    registre._positions = {1: (43.6, 1.4), 2: (43.6, 1.4), 3: (43.6, 1.4), 4: (43.6, 1.4), 5: (43.6, 1.4)}
    registre.tirer_journee(1, T0)
    avant = len(registre.accidents)
    assert registre.poser_manuellement(43.6, 1.4, T0, 0) is None
    assert len(registre.accidents) == avant


def test_f_bouton_et_endpoint_existent():
    """F — le geste est offert dans l'IHM et au contrôleur.

    Vérification de présence, comme R1 et R3 : ni l'IHM GAMA ni la route HTTP ne sont
    exerçables depuis un test unitaire.
    """
    city = (MODELES / "City.gaml").read_text(encoding="utf-8")
    assert 'user_command "Poser un accident maintenant"' in city
    llm_agent = (MODELES / "LLMAgent.gaml").read_text(encoding="utf-8")
    assert 'do send to: "/accidents"' in llm_agent
    app = (
        pathlib.Path(__file__).resolve().parents[1] / "handle" / "application.py"
    ).read_text(encoding="utf-8")
    assert '@app.post(\n    "/accidents",' in app
    assert "régime d'accidents désactivé pour ce run" in app, (
        "une pose dans un run où le régime est décoché doit être refusée explicitement"
    )
