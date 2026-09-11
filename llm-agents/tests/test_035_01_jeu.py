"""Ticket 035, spec 01 — jeu de déplacements enregistré (règles J1 à J16).

Un moteur factice remplace OTP/OSMnx : on vérifie le contrat du jeu (dérivation des déplacements,
sur-ensemble, complétude, dépendances, reprise, portabilité, immutabilité, journal), pas le routage.
"""

import asyncio
import hashlib
import json
import shutil
from pathlib import Path

import pytest
import yaml
from loguru import logger

from experiences import jeu as J
from experiences.population import charger_population, info_population
from models import Location, TransitLocation, Transit, TravelPlan

HOME = {"lon": 1.4400, "lat": 43.6000, "public_transport": True, "zone": "centre"}
WORK = {"lon": 1.4500, "lat": 43.6100, "public_transport": True, "zone": "nord"}
GYM = {"lon": 1.4600, "lat": 43.6200, "public_transport": False, "zone": "est"}


def _act(aid, purpose, start, end, loc, scheduled=None):
    return {"id": aid, "scheduled_start_time": scheduled, "start_time": float(start), "end_time": float(end),
            "purpose": purpose, "location": loc}


def _entry(pid, activities, **traits):
    base = {"age": 35, "gender": "Female", "main_occupation": "actif", "household_size": 1, "number_of_cars": 1,
            "has_driving_license": True, "personal_bike": "vélo normal", "residence_zone": "Toulouse"}
    base.update(traits)
    return {"person_id": pid, "identity": {"traits_json": base, "home": HOME, "activities": activities},
            "state": {"last_activity_index": 0}, "is_llm_based": True}


def _population():
    """3 personnes : 3, 2 et 1 activités → 2 + 1 + 0 = 3 déplacements attendus (J2)."""
    return [
        _entry("p3", [_act("a0", "home", 0, 8 * 3600, HOME), _act("a1", "work", 9 * 3600, 17 * 3600, WORK, 8 * 3600 + 1800),
                      _act("a2", "home", 18 * 3600, 86400, HOME, 17 * 3600 + 900)]),
        _entry("p2", [_act("b0", "home", 0, 10 * 3600, HOME), _act("b1", "shop", 11 * 3600, 86400, GYM, 10 * 3600 + 600)],
               personal_bike="Pas de vélo", has_driving_license=False, age=15, household_size=1),
        _entry("p1", [_act("c0", "home", 0, 86400, HOME)]),
    ]


@pytest.fixture
def pop_dir(tmp_path):
    d = tmp_path / "pop"
    d.mkdir()
    (d / "population.json").write_text(json.dumps(_population()), encoding="utf-8")
    return d


def _sceller(pop_dir: Path) -> Path:
    sha = hashlib.sha256((pop_dir / "population.json").read_bytes()).hexdigest()
    (pop_dir / "MANIFEST.yaml").write_text(yaml.safe_dump({"nom": "pop_test", "population": {"fichier": "population.json", "sha256": sha}}), encoding="utf-8")
    return pop_dir / "MANIFEST.yaml"


def _plan(mode: str, origin: Location, dest: Location, dep_ts: int, duration=600, route=None) -> TravelPlan:
    loc_o = TransitLocation(stop="", lat=origin.lat, lon=origin.lon)
    loc_d = TransitLocation(stop="", lat=dest.lat, lon=dest.lon)
    leg = Transit(start_time=dep_ts * 1000, end_time=(dep_ts + duration) * 1000, duration=duration, distance=1500.0,
                  mode=mode, start_location=loc_o, end_location=loc_d, transit_route=route or f"__DIRECT_{mode.upper()}__")
    return TravelPlan(id=f"{mode}-{dep_ts}", start_location=origin, end_location=dest, start_time=dep_ts * 1000,
                      end_time=(dep_ts + duration) * 1000, duration=duration, legs=[leg])


class MoteurFactice:
    """Rend marche, vélo, voiture et `n_transit` variantes TC — quels que soient les drapeaux."""

    def __init__(self, n_transit=2, vide_pour=(), echoue_pour=()):
        self.appels, self.n_transit, self.vide_pour, self.echoue_pour = [], n_transit, set(vide_pour), set(echoue_pour)

    async def get_itineraries(self, origin, destination, departure_time, include_car=False, include_bike=True, arrive_by=False, **_):
        self.appels.append({"origin": origin, "destination": destination, "departure_time": departure_time,
                            "include_car": include_car, "include_bike": include_bike, "arrive_by": arrive_by})
        cle = (round(destination.lat, 4), round(destination.lon, 4))
        if cle in self.echoue_pour:
            raise RuntimeError("OTP indisponible")
        if cle in self.vide_pour:
            return []
        plans = [_plan("foot", origin, destination, departure_time, 1800), _plan("bicycle", origin, destination, departure_time, 900),
                 _plan("car", origin, destination, departure_time, 600)]
        plans += [_plan("bus", origin, destination, departure_time, 1000 + 60 * i, route=f"L{i}") for i in range(self.n_transit)]
        return plans


def _pas_de_locale(**_):
    return None


def _preparer(dossier, pop_dir, moteur, nom="jeu_test", deps=None, seuil=0.05, clore=True):
    personnes, info = charger_population(pop_dir)
    prep = J.JeuEnPreparation.ouvrir(dossier, nom, info, "2026-03-16", dependances=deps or {"commit": "abc", "gtfs": {"calendar.txt": "c1"}})
    compteurs = asyncio.run(J.preparer(prep, personnes, moteur, fabrique_locale=_pas_de_locale, seuil_sans_proposition=seuil, progression_s=100))
    if clore:
        prep.clore(J.deplacements_attendus(personnes, "2026-03-16"), len(personnes))
    else:
        prep.fermer()
    return compteurs, personnes, info


# ── J1 : population par nom ET empreinte, scellée ou non ──────────────────────────────
def test_J1_population_scellee_ou_non(pop_dir):
    nue = info_population(pop_dir / "population.json")
    assert nue.scellee is False and nue.sha256 == hashlib.sha256((pop_dir / "population.json").read_bytes()).hexdigest()
    manifest = _sceller(pop_dir)
    scellee = info_population(pop_dir)
    assert scellee.scellee is True and scellee.nom == "pop_test"
    assert scellee.sha256 == hashlib.sha256(manifest.read_bytes()).hexdigest()


# ── J2 : déplacements dérivés des agendas ─────────────────────────────────────────────
def test_J2_deplacements_derives(pop_dir):
    personnes, _ = charger_population(pop_dir)
    att = J.deplacements_attendus(personnes, "2026-03-16")
    assert len(att) == 3 and sorted(d.person_id for d in att) == ["p2", "p3", "p3"]
    d0 = next(d for d in att if d.activity_id == "a1")
    assert d0.depart_24h == 8 * 3600 + 1800 and d0.depart_ts == J.jour_base_ts("2026-03-16") + 8 * 3600 + 1800
    # `zone` n'est pas lu par le chargeur commun (parité avec la simulation) ; `public_transport` l'est.
    assert d0.origine.public_transport is True and d0.destination.public_transport is True


# ── J3 : sur-ensemble, sans filtre véhicule ni plafond ────────────────────────────────
def test_J3_superset_sans_filtre_ni_plafond(tmp_path, pop_dir):
    moteur = MoteurFactice(n_transit=9)
    _preparer(tmp_path / "jeu", pop_dir, moteur)
    assert all(a["include_car"] and a["include_bike"] and not a["arrive_by"] for a in moteur.appels)
    jeu = J.Jeu.charger(tmp_path / "jeu")
    props = jeu.propositions("p2", "b1")               # mineur sans vélo ni permis : le jeu porte quand même vélo et voiture
    modes = [p.mode for p in props]
    assert "bicycle" in modes and "car" in modes and modes.count("bus") == 9, modes


# ── J4 : la proposition relue est identique à celle calculée ──────────────────────────
def test_J4_proposition_relue_identique(tmp_path, pop_dir):
    moteur = MoteurFactice()
    _preparer(tmp_path / "jeu", pop_dir, moteur)
    jeu = J.Jeu.charger(tmp_path / "jeu")
    for p in jeu.propositions("p3", "a1"):
        d = p.plan.model_dump()
        assert d["start_location"]["lat"] == HOME["lat"] and d["end_location"]["lat"] == WORK["lat"]
        assert p.plan.start_time and p.plan.end_time and p.plan.mode_label()
        assert TravelPlan.model_validate(json.loads(json.dumps(d))).model_dump() == d


# ── J5 : identité = empreinte du contenu ──────────────────────────────────────────────
def test_J5_empreinte_independante_du_nom(tmp_path, pop_dir):
    _preparer(tmp_path / "jeu", pop_dir, MoteurFactice())
    jeu = J.Jeu.charger(tmp_path / "jeu")
    shutil.copytree(tmp_path / "jeu", tmp_path / "autre_nom")
    copie = J.Jeu.charger(tmp_path / "autre_nom")
    assert copie.empreinte == jeu.empreinte
    lignes = (tmp_path / "jeu" / J.FICHIER_PROPOSITIONS).read_text(encoding="utf-8").replace('"duration": 600', '"duration": 601', 1)
    (tmp_path / "jeu" / J.FICHIER_PROPOSITIONS).write_text(lignes, encoding="utf-8")
    assert hashlib.sha256(lignes.encode()).hexdigest() != jeu.empreinte


# ── J6 : consultation par personne ────────────────────────────────────────────────────
def test_J6_consulter_une_personne(tmp_path, pop_dir):
    _preparer(tmp_path / "jeu", pop_dir, MoteurFactice())
    jeu = J.Jeu.charger(tmp_path / "jeu")
    lignes = jeu.consulter("p3")
    assert [l.activity_id for l in lignes] == ["a1", "a2"] and all(len(l.propositions) == 5 for l in lignes)
    assert jeu.consulter("inconnu") == [] and jeu.personnes() == ["p2", "p3"]


# ── J7 / J8 : complétude visible, jamais « complet » à tort ───────────────────────────
def test_J7_J8_completude(tmp_path, pop_dir):
    moteur = MoteurFactice(vide_pour={(round(GYM["lat"], 4), round(GYM["lon"], 4))})
    _preparer(tmp_path / "jeu", pop_dir, moteur, seuil=0.9)
    jeu = J.Jeu.charger(tmp_path / "jeu")
    c = jeu.couverture()
    assert (c["deplacements_couverts"], c["deplacements_attendus"]) == (2, 3) and c["taux"] == pytest.approx(2 / 3)
    assert c["sans_proposition"] == [{"person_id": "p2", "activity_id": "b1", "motif": "aucune_proposition"}]
    assert not jeu.est_complet and "66,7 %" in jeu.resume() and "complet" not in jeu.resume().lower().replace("complète", "")


# ── J9 : sans dépendances, refus ──────────────────────────────────────────────────────
def test_J9_refus_sans_dependances(tmp_path, pop_dir):
    _preparer(tmp_path / "jeu", pop_dir, MoteurFactice())
    m = tmp_path / "jeu" / J.FICHIER_MANIFEST
    data = yaml.safe_load(m.read_text()); data.pop("dependances"); m.write_text(yaml.safe_dump(data))
    with pytest.raises(J.JeuInvalide, match="dependances"):
        J.Jeu.charger(tmp_path / "jeu")


# ── J10 : péremption listée, jamais rafraîchie en silence ─────────────────────────────
def test_J10_peremption(tmp_path, pop_dir):
    deps = {"commit": "abc", "gtfs": {"calendar.txt": "c1", "routes.txt": None}, "otp_graph_sha256": "g1"}
    _preparer(tmp_path / "jeu", pop_dir, MoteurFactice(), deps=deps)
    jeu = J.Jeu.charger(tmp_path / "jeu")
    differentes, non_verif = J.perime(jeu, {"commit": "abc", "gtfs": {"calendar.txt": "c1", "routes.txt": "r9"}, "otp_graph_sha256": "g2"})
    assert differentes == ["otp_graph_sha256"] and non_verif == ["gtfs/routes.txt"]
    assert J.perime(jeu, deps) == ([], [])


# ── J11 : reprise sans recalcul ───────────────────────────────────────────────────────
def test_J11_reprise(tmp_path, pop_dir):
    casse = MoteurFactice(echoue_pour={(round(GYM["lat"], 4), round(GYM["lon"], 4))})
    c1, _, _ = _preparer(tmp_path / "jeu", pop_dir, casse, clore=False)
    assert c1["calcules"] == 2 and c1["erreurs"] == 1 and c1["restants_apres"] == 1
    sain = MoteurFactice()
    messages = []
    sink = logger.add(lambda m: messages.append(m), level="INFO")
    try:
        c2, _, _ = _preparer(tmp_path / "jeu", pop_dir, sain)
    finally:
        logger.remove(sink)
    assert len(sain.appels) == 1 and c2["calcules"] == 1 and c2["restants_apres"] == 0
    assert any("reste 1" in str(m) for m in messages)
    assert J.Jeu.charger(tmp_path / "jeu").est_complet


# ── J12 : portable et refus d'un jeu altéré ───────────────────────────────────────────
def test_J12_portable_et_altere(tmp_path, pop_dir):
    _preparer(tmp_path / "jeu", pop_dir, MoteurFactice())
    shutil.copytree(tmp_path / "jeu", tmp_path / "ailleurs" / "jeu")
    jeu = J.Jeu.charger(tmp_path / "ailleurs" / "jeu")     # aucun moteur impliqué
    assert len(jeu) == 3 and jeu.propositions("p3", "a2")
    f = tmp_path / "ailleurs" / "jeu" / J.FICHIER_PROPOSITIONS
    b = bytearray(f.read_bytes()); b[10] ^= 0x01; f.write_bytes(bytes(b))
    with pytest.raises(J.JeuInvalide, match="altéré"):
        J.Jeu.charger(tmp_path / "ailleurs" / "jeu")


# ── J13 : inerte, malformé refusé avec la position ────────────────────────────────────
def test_J13_inerte_et_malforme(tmp_path, pop_dir):
    assert "pickle" not in Path(J.__file__).read_text(encoding="utf-8")
    _preparer(tmp_path / "jeu", pop_dir, MoteurFactice())
    f = tmp_path / "jeu" / J.FICHIER_PROPOSITIONS
    lignes = f.read_text(encoding="utf-8").splitlines()
    lignes[1] = lignes[1][: len(lignes[1]) // 2]
    f.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    with pytest.raises(J.JeuInvalide, match="ligne 2|altéré"):
        J.Jeu.charger(tmp_path / "jeu")
    with pytest.raises(J.JeuInvalide, match="ligne 2"):
        J.Jeu.charger(tmp_path / "jeu", verifier=False)


# ── J14 : immuable après clôture ──────────────────────────────────────────────────────
def test_J14_immuable(tmp_path, pop_dir):
    _, personnes, info = _preparer(tmp_path / "jeu", pop_dir, MoteurFactice())
    with pytest.raises(J.JeuClos):
        J.JeuEnPreparation.ouvrir(tmp_path / "jeu", "jeu_test", info, "2026-03-16")


# ── J15 : journal de succès et ALARME à front montant ─────────────────────────────────
def test_J15_journal_et_alarme(tmp_path, pop_dir):
    messages = []
    sink = logger.add(lambda m: messages.append(str(m)), level="INFO")
    try:
        _preparer(tmp_path / "jeu", pop_dir, MoteurFactice(vide_pour={(round(GYM["lat"], 4), round(GYM["lon"], 4)), (round(WORK["lat"], 4), round(WORK["lon"], 4))}), seuil=0.05)
    finally:
        logger.remove(sink)
    assert sum("[ALARME]" in m for m in messages) == 1, "une alarme, pas une par déplacement"
    assert any("Préparation terminée" in m and "calculés 3" in m for m in messages)


# ── J16 : aucun attribut du persona dans le jeu ───────────────────────────────────────
def test_J16_aucun_attribut_personnel(tmp_path, pop_dir):
    _preparer(tmp_path / "jeu", pop_dir, MoteurFactice())
    contenu = (tmp_path / "jeu" / J.FICHIER_PROPOSITIONS).read_text(encoding="utf-8")
    for champ in ("age", "has_driving_license", "personal_bike", "number_of_cars", "gender", "household_size"):
        assert f'"{champ}"' not in contenu


# ── décision 18 : l'équivalence de l'offre TC d'un autre jour est MESURÉE, jamais supposée ──
def test_D18_comparer_offre_jour(tmp_path, pop_dir):
    _preparer(tmp_path / "jeu", pop_dir, MoteurFactice(n_transit=2))
    jeu = J.Jeu.charger(tmp_path / "jeu")
    identique = asyncio.run(J.comparer_offre_jour(jeu, MoteurFactice(n_transit=2), "2026-03-17", echantillon=10))
    assert identique["equivalent"] is True and identique["compares"] == 3 and identique["differents"] == 0
    assert all(a["departure_time"] >= J.jour_base_ts("2026-03-17") for a in [])  # les requêtes portent le jour demandé
    autre = asyncio.run(J.comparer_offre_jour(jeu, MoteurFactice(n_transit=3), "2026-03-17", echantillon=10))
    assert autre["equivalent"] is False and autre["differents"] == 3 and len(autre["differences"]) == 3
    assert jeu.jours_equivalents() == []
    jeu.declarer_jour_equivalent("2026-03-17", {k: v for k, v in identique.items() if k != "differences"})
    assert J.Jeu.charger(tmp_path / "jeu").jours_equivalents() == ["2026-03-17"]


def test_J15_progression_json_pendant_la_preparation(tmp_path, pop_dir):
    _preparer(tmp_path / "jeu", pop_dir, MoteurFactice())
    prog = json.loads((tmp_path / "jeu" / "progression.json").read_text(encoding="utf-8"))
    assert prog["faits"] == 3 and prog["total"] == 3 and prog["pourcent"] == 100.0 and "maj" in prog
