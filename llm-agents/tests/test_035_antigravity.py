"""Tests du décideur Antigravity (ticket 035, spec decideur-antigravity v2).

Couvre :
- DecideurSpec et validation (modele obligatoire)
- Empreinte décideur avec modele_verifie: false
- Nommage canonique (segment_decideur agy-..., nom complet, NommageImpossible)
- Identité à l'octet près du texte présenté (PromptEngine vs decideur_antigravity)
- Contrat IPC : écriture atomique, rejet hors sujet, rejet modele_declare, repli D10, timeout
- États d'attente (ETAT_EN_ATTENTE_AGENT)
- Trace scellée et validation d'archive
"""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from experiences.archive import (
    ETAT_DEFINIE,
    ETAT_EN_ATTENTE_AGENT,
    ETAT_EN_COURS,
    Execution,
    valider_archive,
)
from experiences.decideur_antigravity import DecideurAntigravity
from experiences.decideurs import construire_decideur
from experiences.decision import (
    ContexteDecision,
    Proposition,
    ReponseDecideur,
    construire_trace,
    decider,
)
from experiences.experience import (
    DecideurSpec,
    _empreinte_decideur,
    empreinte_gabarit,
)
from experiences.nommage import NommageImpossible, nom_canonique, segment_decideur
from mobility_llm import CATEGORIES, prompt_manager
from models import (
    Location,
    Person,
    PersonalIdentity,
    PersonState,
    Transit,
    TransitLocation,
    TravelPlan,
)

HOME = Location(lat=43.6000, lon=1.4400)
WORK = Location(lat=43.6100, lon=1.4500)


def _person(pid="p1") -> Person:
    return Person(
        person_id=pid,
        identity=PersonalIdentity(name="test", traits_json={"age": 30}, home=HOME),
        state=PersonState(),
    )


def _plan(code: str, *modes: str, start=HOME, end=WORK, duration=600) -> TravelPlan:
    if not modes:
        modes = ("car",)
    loc = TransitLocation(stop="", lat=start.lat, lon=start.lon)
    legs = [
        Transit(
            start_time=0,
            end_time=duration,
            duration=duration,
            distance=1000.0,
            mode=m,
            start_location=loc,
            end_location=loc,
            is_transfer=(m == "foot" and len(modes) > 1),
            transit_route=code if (m not in ("foot",) or len(modes) == 1) else None,
        )
        for i, m in enumerate(modes)
    ]
    return TravelPlan(
        id=code,
        start_location=start,
        end_location=end,
        start_time=0,
        end_time=duration,
        duration=duration,
        legs=legs,
    )



def _ctx(activity_id="act_test", purpose="work", **kw) -> ContexteDecision:
    return ContexteDecision(
        timestamp=kw.pop("timestamp", 1773733200),
        activity_id=activity_id,
        purpose=purpose,
        departure_time=kw.pop("departure_time", 1773733200),
        from_location=kw.pop("from_location", HOME),
        destination=kw.pop("destination", WORK),
        **kw,
    )


# ── 1. DecideurSpec & Empreinte ──────────────────────────────────────────────


def test_decideur_spec_antigravity_valide():
    spec = DecideurSpec(type="antigravity", modele="gemini-3.8-flash")
    assert spec.valider() == []
    assert spec.type == "antigravity"
    assert spec.modele == "gemini-3.8-flash"


def test_decideur_spec_antigravity_modele_obligatoire():
    spec = DecideurSpec(type="antigravity", modele=None)
    errs = spec.valider()
    assert len(errs) == 1
    assert "decideur.modele est obligatoire" in errs[0]

    spec_vide = DecideurSpec(type="antigravity", modele="")
    assert len(spec_vide.valider()) == 1


def test_empreinte_decideur_modele_verifie_false():
    spec = DecideurSpec(type="antigravity", modele="gemini-3.8-flash")
    emp = _empreinte_decideur(spec)
    assert emp["type"] == "antigravity"
    assert emp["modele"] == "gemini-3.8-flash"
    assert emp["modele_verifie"] is False
    assert "sha256" in emp


# ── 2. Nommage canonique ─────────────────────────────────────────────────────


def test_segment_decideur_antigravity():
    assert (
        segment_decideur({"type": "antigravity", "modele": "gemini-3.8-flash"})
        == "agy-gemini-38-f"
    )


def test_segment_decideur_antigravity_modele_vide():
    with pytest.raises(NommageImpossible, match="decideur.modele est vide"):
        segment_decideur({"type": "antigravity", "modele": ""})


def test_nom_canonique_antigravity():
    exp_def = {
        "population": {"chemin": "population_1000_AAMAS.json"},
        "jeu": {"nom": "population_1000_AAMAS_20260316"},
        "gabarit": {"categorie": "itinary_multi_agent", "variante": "minimal_persona"},
        "decideur": {
            "type": "antigravity",
            "modele": "gemini-3.8-flash",
            "parametres": {"temperature": 0.0},
        },
        "calendrier": {"politique": "aleatoire", "graine": 42},
        "mode": "sans_simulateur",
    }
    nom = nom_canonique(exp_def)
    assert nom == "exp_agy-gemini-38-f_minper_jtir_t0_nosim"
    assert len(nom) <= 64

    # Le nommage n'interroge aucun prompt (`minimal_persona` est invalidée depuis le
    # 2026-09-10 mais reste nommable : les exécutions passées gardent leur identité).
    # Son remplaçant porte son propre segment, ce qui distingue les deux au premier coup d'œil.
    exp_def["gabarit"]["variante"] = "prompt_minimal"
    assert nom_canonique(exp_def) == "exp_agy-gemini-38-f_promin_jtir_t0_nosim"


# ── 3. Identité à l'octet près du texte présenté (§8.1) ──────────────────────


@pytest.mark.asyncio
async def test_identite_texte_presente_octet_par_octet(tmp_path):
    """Vérifie que DecideurAntigravity produit exactement les messages de PromptEngine.render."""
    person = _person("4242")
    ctx = _ctx(
        activity_id="act_test",
        purpose="work",
        timestamp=1773733200,
        departure_time=1773733200,
        anticipation=None,
    )
    plan1 = _plan("car_opt", "car", duration=1800)
    plan2 = _plan("bike_opt", "bicycle", duration=2400)
    presentees = [
        Proposition(plan=plan1, source="enregistree"),
        Proposition(plan=plan2, source="enregistree"),
    ]

    mock_agent = MagicMock()
    simulated_payload = {
        "category": "itinary_multi_agent",
        "agents": [
            {
                "agent_id": "4242",
                "perception": "Test Persona",
                "destination": "work",
                "destination_zone": None,
                "departure_time": "08:00",
                "departure_timestamp": 1773733200.0,
                "current_time": "08:00",
                "context": "Beau temps",
                "day_outlook": None,
                "agenda": [],
                "history": [],
                "trajectories": [
                    {
                        "index": 0,
                        "mode": "car",
                        "description": "Voiture 30 min",
                        "total_distance_m": 5000,
                    },
                    {
                        "index": 1,
                        "mode": "bicycle",
                        "description": "Vélo 40 min",
                        "total_distance_m": 6000,
                    },
                ],
            }
        ],
        "parameters": {"prompt_variant": "prompt_minimal"},
    }
    mock_agent.build_travel_plan_payload = AsyncMock(return_value=simulated_payload)

    # Référence directe PromptEngine
    cat = CATEGORIES["itinary_multi_agent"]
    items = [cat.item_model(**a) for a in simulated_payload["agents"]]
    messages_ref = prompt_manager().render(
        "itinary_multi_agent", items, simulated_payload["parameters"]
    )
    ref_dict = [{"role": m.role, "content": m.content} for m in messages_ref]

    decideur = DecideurAntigravity(
        agent=mock_agent,
        modele="gemini-3.8-flash",
        echanges=tmp_path / "echanges",
        attente_max_s=1,
    )

    # Lancer choisir et injecter immédiatement la réponse IPC
    async def injecter_reponse():
        await asyncio.sleep(0.1)
        demande_fichier = tmp_path / "echanges" / "demandes" / "4242__act_test.json"
        assert demande_fichier.is_file()
        demande_data = json.loads(demande_fichier.read_text(encoding="utf-8"))

        # Vérification byte-level / structure verbatim
        assert demande_data["messages"] == ref_dict
        assert demande_data["person_id"] == "4242"
        assert demande_data["activity_id"] == "act_test"
        assert demande_data["modele_attendu"] == "gemini-3.8-flash"
        assert demande_data["n_options"] == 2

        # Écrire réponse
        reponse_fichier = tmp_path / "echanges" / "reponses" / "4242__act_test.json"
        reponse_tmp = tmp_path / "echanges" / "reponses" / "4242__act_test.json.tmp"
        rep_content = {
            "version": 1,
            "person_id": "4242",
            "activity_id": "act_test",
            "modele_declare": "gemini-3.8-flash",
            "reponse_brute": "raw text",
            "agents": [
                {
                    "agent_id": "4242",
                    "probabilities": [
                        {"index": 0, "mode": "car", "probability": 80.0, "reason": "rapide"},
                        {"index": 1, "mode": "bicycle", "probability": 20.0, "reason": "pluie"},
                    ],
                }
            ],
        }
        reponse_tmp.write_text(json.dumps(rep_content), encoding="utf-8")
        import os

        os.replace(reponse_tmp, reponse_fichier)

    task = asyncio.create_task(injecter_reponse())
    rep = await decideur.choisir(person, ctx, presentees)
    await task

    assert rep.index is not None
    assert rep.modele_verifie is False
    assert rep.presente["messages"] == ref_dict
    assert not rep.repli_uniforme


# ── 4. Contrat IPC (Rejets, Timeout, États) ──────────────────────────────────


@pytest.mark.asyncio
async def test_ipc_reponse_hors_sujet_puis_bonne_reponse(tmp_path):
    person = _person("101")
    ctx = _ctx(activity_id="act1", purpose="work", timestamp=100, departure_time=100)
    presentees = [
        Proposition(plan=_plan("c", "car", duration=100), source="enregistree"),
        Proposition(plan=_plan("w", "walk", duration=200), source="enregistree"),
    ]

    mock_agent = MagicMock()
    mock_agent.build_travel_plan_payload = AsyncMock(
        return_value={
            "category": "itinary_multi_agent",
            "agents": [
                {
                    "agent_id": "101",
                    "perception": "test",
                    "destination": "work",
                    "trajectories": [{"mode": "car"}, {"mode": "walk"}],
                }
            ],
            "parameters": {},
        }
    )

    decideur = DecideurAntigravity(
        agent=mock_agent,
        modele="gemini-3.8-flash",
        echanges=tmp_path / "echanges",
        attente_max_s=3,
    )

    async def scenario():
        await asyncio.sleep(0.1)
        rep_file = tmp_path / "echanges" / "reponses" / "101__act1.json"
        # 1. Mauvais person_id
        rep_file.write_text(
            json.dumps({"person_id": "999", "activity_id": "act1", "modele_declare": "gemini-3.8-flash"})
        )
        await asyncio.sleep(0.6)
        # Fichier hors sujet supprimé par decideur
        assert not rep_file.exists()
        # 2. Bonne réponse
        rep_file.write_text(
            json.dumps(
                {
                    "person_id": "101",
                    "activity_id": "act1",
                    "modele_declare": "gemini-3.8-flash",
                    "agents": [
                        {
                            "agent_id": "101",
                            "probabilities": [
                                {"index": 0, "mode": "car", "probability": 100},
                                {"index": 1, "mode": "walk", "probability": 0},
                            ],
                        }
                    ],
                }
            )
        )

    task = asyncio.create_task(scenario())
    rep = await decideur.choisir(person, ctx, presentees)
    await task

    assert rep.index == 0
    assert decideur.compteurs["rejets"] == 1
    assert decideur.compteurs["servies"] == 1


@pytest.mark.asyncio
async def test_ipc_modele_declare_inattendu(tmp_path):
    person = _person("102")
    ctx = _ctx(activity_id="act2", purpose="work", timestamp=100, departure_time=100)
    presentees = [
        Proposition(plan=_plan("c", "car", duration=100), source="enregistree"),
        Proposition(plan=_plan("w", "walk", duration=200), source="enregistree"),
    ]

    mock_agent = MagicMock()
    mock_agent.build_travel_plan_payload = AsyncMock(
        return_value={
            "category": "itinary_multi_agent",
            "agents": [
                {
                    "agent_id": "102",
                    "perception": "test",
                    "destination": "work",
                    "trajectories": [{"mode": "car"}, {"mode": "walk"}],
                }
            ],
            "parameters": {},
        }
    )

    decideur = DecideurAntigravity(
        agent=mock_agent,
        modele="gemini-3.8-flash",
        echanges=tmp_path / "echanges",
        attente_max_s=2,
    )

    async def scenario():
        await asyncio.sleep(0.1)
        rep_file = tmp_path / "echanges" / "reponses" / "102__act2.json"
        rep_file.write_text(
            json.dumps(
                {
                    "person_id": "102",
                    "activity_id": "act2",
                    "modele_declare": "autre-modele-inattendu",
                }
            )
        )

    task = asyncio.create_task(scenario())
    rep = await decideur.choisir(person, ctx, presentees)
    await task

    assert rep.index is None
    assert "modèle déclaré inattendu" in rep.erreur
    assert decideur.compteurs["rejets"] == 1


@pytest.mark.asyncio
async def test_ipc_timeout_non_reponse(tmp_path):
    person = _person("103")
    ctx = _ctx(activity_id="act3", purpose="work", timestamp=100, departure_time=100)
    presentees = [
        Proposition(plan=_plan("c", "car", duration=100), source="enregistree"),
        Proposition(plan=_plan("w", "walk", duration=200), source="enregistree"),
    ]

    mock_agent = MagicMock()
    mock_agent.build_travel_plan_payload = AsyncMock(
        return_value={
            "category": "itinary_multi_agent",
            "agents": [
                {
                    "agent_id": "103",
                    "perception": "test",
                    "destination": "work",
                    "trajectories": [{"mode": "car"}, {"mode": "walk"}],
                }
            ],
            "parameters": {},
        }
    )

    decideur = DecideurAntigravity(
        agent=mock_agent,
        modele="gemini-3.8-flash",
        echanges=tmp_path / "echanges",
        attente_max_s=1,
    )

    rep = await decideur.choisir(person, ctx, presentees)
    assert rep.index is None
    assert "pas de réponse en 1s" in rep.erreur
    assert decideur.compteurs["timeouts"] == 1


@pytest.mark.asyncio
async def test_changement_etat_en_attente_agent(tmp_path):
    person = _person("104")
    ctx = _ctx(activity_id="act4", purpose="work", timestamp=100, departure_time=100)
    presentees = [
        Proposition(plan=_plan("c", "car", duration=100), source="enregistree"),
        Proposition(plan=_plan("w", "walk", duration=200), source="enregistree"),
    ]

    mock_agent = MagicMock()
    mock_agent.build_travel_plan_payload = AsyncMock(
        return_value={
            "category": "itinary_multi_agent",
            "agents": [
                {
                    "agent_id": "104",
                    "perception": "test",
                    "destination": "work",
                    "trajectories": [{"mode": "car"}, {"mode": "walk"}],
                }
            ],
            "parameters": {},
        }
    )

    # Créer une fausse exécution pour suivre l'état
    mock_exec = MagicMock()
    etat_dict = {"etat": ETAT_EN_COURS}

    def get_etat():
        return etat_dict

    def changer_etat(nouvel_etat, raison=None):
        etat_dict["etat"] = nouvel_etat

    mock_exec.etat = get_etat
    mock_exec.changer_etat = changer_etat

    decideur = DecideurAntigravity(
        agent=mock_agent,
        modele="gemini-3.8-flash",
        echanges=tmp_path / "echanges",
        attente_max_s=2,  # seuil = 0.5s
        execution=mock_exec,
    )

    async def repondre_apres_seuil():
        await asyncio.sleep(0.7)  # > 0.5s -> passe en ETAT_EN_ATTENTE_AGENT
        assert etat_dict["etat"] == ETAT_EN_ATTENTE_AGENT
        rep_file = tmp_path / "echanges" / "reponses" / "104__act4.json"
        rep_file.write_text(
            json.dumps(
                {
                    "person_id": "104",
                    "activity_id": "act4",
                    "modele_declare": "gemini-3.8-flash",
                    "agents": [
                        {
                            "agent_id": "104",
                            "probabilities": [
                                {"index": 0, "mode": "car", "probability": 100},
                                {"index": 1, "mode": "walk", "probability": 0},
                            ],
                        }
                    ],
                }
            )
        )

    task = asyncio.create_task(repondre_apres_seuil())
    rep = await decideur.choisir(person, ctx, presentees)
    await task

    assert rep.index == 0
    # Après réponse valide, l'état revient à ETAT_EN_COURS
    assert etat_dict["etat"] == ETAT_EN_COURS


# ── 5. Trace scellée et validation d'archive ─────────────────────────────────


def test_construire_trace_modele_verifie():
    person = _person("200")
    ctx = _ctx(activity_id="act_tr", purpose="work", timestamp=100, departure_time=100)
    prop = Proposition(plan=_plan("car", "car", duration=100), source="enregistree")

    reponse = ReponseDecideur(
        index=0,
        fournisseur="antigravity:gemini-3.8-flash",
        modele_verifie=False,
        presente={"test": True},
    )

    trace = construire_trace(
        person,
        ctx,
        [prop],
        [],
        prop,
        "decideur",
        reponse,
        "",
    )
    assert trace["modele_verifie"] is False
    assert trace["presente"] == {"test": True}


def test_construire_decideur_antigravity_factory(tmp_path):
    spec = DecideurSpec(type="antigravity", modele="gemini-3.8-flash")
    mock_agent = MagicMock()
    d = construire_decideur(
        spec,
        agent=mock_agent,
        dossier_echanges=tmp_path / "echanges",
        attente_max_s=60,
    )
    assert isinstance(d, DecideurAntigravity)
    assert d.modele == "gemini-3.8-flash"
    assert d.sans_quota is True
    assert d.modele_verifie is False


# ── P8 — sortie littérale du modèle (spec hygiène §8) ────────────────────────


def test_trace_porte_la_sortie_litterale():
    """La sortie du modèle voyage dans la trace, TELLE QU'ÉMISE."""
    person = _person("300")
    ctx = _ctx(activity_id="act_lit", purpose="work", timestamp=100, departure_time=100)
    prop = Proposition(plan=_plan("car", "car", duration=100), source="enregistree")
    litterale = '```json\n{"agents": [{"agent_id": "300"}]}\n```'

    trace = construire_trace(
        person, ctx, [prop], [], prop, "decideur",
        ReponseDecideur(
            index=0,
            fournisseur="antigravity:m",
            reponse_brute='{"agents": [{"agent_id": "300"}]}',
            sortie_litterale=litterale,
            presente={"x": 1},
        ),
        "",
    )
    assert trace["sortie_litterale"] == litterale
    assert trace["sortie_litterale"] != trace["reponse_brute"], (
        "le champ n'a d'intérêt que s'il peut différer de la version normalisée"
    )


def test_trace_declare_un_trou_plutot_qu_une_copie():
    """Sans sortie littérale, la trace porte None — jamais un repli sur reponse_brute."""
    person = _person("301")
    ctx = _ctx(activity_id="act_trou", purpose="work", timestamp=100, departure_time=100)
    prop = Proposition(plan=_plan("car", "car", duration=100), source="enregistree")

    trace = construire_trace(
        person, ctx, [prop], [], prop, "decideur",
        ReponseDecideur(
            index=0, fournisseur="antigravity:m", reponse_brute='{"agents": []}', presente={"x": 1}
        ),
        "",
    )
    assert trace["sortie_litterale"] is None
    assert trace["reponse_brute"] == '{"agents": []}'


@pytest.mark.asyncio
async def test_decideur_transmet_la_sortie_litterale(tmp_path):
    """Bout en bout : le champ du fichier IPC atterrit dans la réponse du décideur."""
    person = _person("4243")
    ctx = _ctx(activity_id="act_p8", purpose="work", timestamp=1773733200, departure_time=1773733200, anticipation=None)
    presentees = [
        Proposition(plan=_plan("car_opt", "car", duration=1800), source="enregistree"),
        Proposition(plan=_plan("bike_opt", "bicycle", duration=2400), source="enregistree"),
    ]
    mock_agent = MagicMock()
    mock_agent.build_travel_plan_payload = AsyncMock(return_value={
        "category": "itinary_multi_agent",
        "agents": [{
            "agent_id": "4243", "perception": "P", "destination": "work",
            "destination_zone": None, "departure_time": "08:00",
            "departure_timestamp": 1773733200.0, "current_time": "08:00",
            "context": "Beau temps", "day_outlook": None, "agenda": [], "history": [],
            "trajectories": [
                {"index": 0, "mode": "car", "description": "d", "total_distance_m": 5000},
                {"index": 1, "mode": "bicycle", "description": "d", "total_distance_m": 6000},
            ],
        }],
        "parameters": {"prompt_variant": "prompt_minimal"},
    })
    d = DecideurAntigravity(agent=mock_agent, modele="m", echanges=tmp_path / "e", attente_max_s=5)

    litterale = "Voici ma réponse :\n```json\n{\"agents\": [...]}\n```"

    async def repondre():
        cible = tmp_path / "e" / "reponses" / f"4243__{ctx.activity_id}.json"
        for _ in range(40):
            if (tmp_path / "e" / "demandes" / f"4243__{ctx.activity_id}.json").is_file():
                cible.write_text(json.dumps({
                    "version": 1, "person_id": "4243", "activity_id": ctx.activity_id,
                    "modele_declare": "m",
                    "sortie_litterale": litterale,
                    "reponse_brute": '{"agents": [{"agent_id": "4243"}]}',
                    "agents": [{"agent_id": "4243", "reason": "r", "probabilities": [
                        {"index": 0, "mode": "car", "probability": 70},
                        {"index": 1, "mode": "bicycle", "probability": 30},
                    ]}],
                }, ensure_ascii=False), encoding="utf-8")
                return
            await asyncio.sleep(0.05)

    _, rep = await asyncio.gather(repondre(), d.choisir(person, ctx, presentees))
    assert rep.sortie_litterale == litterale
    assert d.compteurs["sans_sortie_litterale"] == 0


@pytest.mark.asyncio
async def test_decideur_compte_les_reponses_sans_sortie_litterale(tmp_path):
    person = _person("4244")
    ctx = _ctx(activity_id="act_p8b", purpose="work", timestamp=1773733200, departure_time=1773733200, anticipation=None)
    presentees = [Proposition(plan=_plan("car_opt", "car", duration=1800), source="enregistree"),
                  Proposition(plan=_plan("bike_opt", "bicycle", duration=2400), source="enregistree")]
    mock_agent = MagicMock()
    mock_agent.build_travel_plan_payload = AsyncMock(return_value={
        "category": "itinary_multi_agent",
        "agents": [{
            "agent_id": "4244", "perception": "P", "destination": "work",
            "destination_zone": None, "departure_time": "08:00",
            "departure_timestamp": 1773733200.0, "current_time": "08:00",
            "context": "c", "day_outlook": None, "agenda": [], "history": [],
            "trajectories": [
                {"index": 0, "mode": "car", "description": "d", "total_distance_m": 1},
                {"index": 1, "mode": "bicycle", "description": "d", "total_distance_m": 2},
            ],
        }],
        "parameters": {"prompt_variant": "prompt_minimal"},
    })
    d = DecideurAntigravity(agent=mock_agent, modele="m", echanges=tmp_path / "e", attente_max_s=5)

    async def repondre():
        cible = tmp_path / "e" / "reponses" / f"4244__{ctx.activity_id}.json"
        for _ in range(40):
            if (tmp_path / "e" / "demandes" / f"4244__{ctx.activity_id}.json").is_file():
                cible.write_text(json.dumps({
                    "version": 1, "person_id": "4244", "activity_id": ctx.activity_id,
                    "modele_declare": "m",
                    "reponse_brute": '{"agents": []}',
                    "agents": [{"agent_id": "4244", "reason": "r", "probabilities": [
                        {"index": 0, "mode": "car", "probability": 50},
                        {"index": 1, "mode": "bicycle", "probability": 50},
                    ]}],
                }, ensure_ascii=False), encoding="utf-8")
                return
            await asyncio.sleep(0.05)

    _, rep = await asyncio.gather(repondre(), d.choisir(person, ctx, presentees))
    assert rep.sortie_litterale is None
    assert d.compteurs["sans_sortie_litterale"] == 1
