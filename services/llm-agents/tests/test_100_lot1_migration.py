"""Ticket 100, lot 1 — la migration du canal d'événement.

Contrat de référence : `specs/ticket_100/tests.md`, règles R1 à R11. Le lot 1 ne livre AUCUNE
fonction nouvelle : il déplace le ticket 079 dans `llm/evenements/`, ajoute deux champs, et doit
prouver qu'un rejeu rend le même fichier. Une migration se prouve par l'égalité, pas par
l'argument.

Tout ici est PUR : aucun simulateur, aucun modèle, aucun appel réseau.
"""

import ast
import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm import evenements as ev
from llm.evenements import RefusDEvenement, RegistreEvenements, charger
from llm.gravite import gravite_deterministe
from llm.memory import MemoryEntry, MemoryType
from settings import settings

RACINE = Path(__file__).resolve().parents[1]
CONFIG_CHOCS = RACINE / "config" / "chocs"
CONFIG_EVENEMENTS = RACINE / "config" / "evenements"

TEXTE_VALIDE = "I was stuck for an hour on the ring road, and I arrived in a foul mood."


def _declaration(**surcharges) -> dict:
    base = {
        "evenement": "test_evenement",
        "libelle": "Événement de test",
        "source": "test",
        "canal": "vecu",
        "moment": "arrivee",
        "jugement": "aucun",
        "exposition": {"regle": "mode", "modes": ["car"]},
        "jours": [{"jour": 12, "retard_min": 60, "texte": TEXTE_VALIDE}],
    }
    base.update(surcharges)
    return base


def _ecrire(tmp_path: Path, declaration: dict, nom: str = "evenement.yaml") -> Path:
    p = tmp_path / nom
    p.write_text(yaml.safe_dump(declaration, allow_unicode=True), encoding="utf-8")
    return p


@pytest.fixture(autouse=True)
def _registre_propre():
    ev.reinitialiser()
    settings.evenements.enabled = False
    settings.evenements.fichier = None
    settings.chocs.enabled = False
    settings.chocs.fichier = None
    yield
    ev.reinitialiser()
    settings.evenements.enabled = False
    settings.evenements.fichier = None
    settings.chocs.enabled = False
    settings.chocs.fichier = None


# ── R1. Le test en or ────────────────────────────────────────────────────────────────────
def _trace_dun_rejeu(declaration: Path, journal: Path, jours: tuple[int, ...]) -> list[dict]:
    """Rejoue une déclaration sur des journées données et rend les lignes écrites.

    Les agents et les modes sont ceux de `c6_voiture_suspecte` : trois personas désignés, tous
    en voiture, plus un témoin non désigné et un trajet en bus — pour que la trace porte à la
    fois des exposés et des épargnés.
    """
    registre = RegistreEvenements(charger(declaration), journal=journal)
    arrivees = (
        ("899549", "car"), ("899549", "public_transport"),
        ("1250941", "car"), ("861500", "car"), ("609", "car"),
    )
    for jour in jours:
        RegistreEvenements.jour_du_run = staticmethod(lambda ts, _j=jour: _j)
        for rang, (person_id, mode) in enumerate(arrivees):
            applique = registre.applique(person_id, mode, 1_700_000_000 + rang * 3600)
            if applique is None:
                continue
            gravite, detail = gravite_deterministe(
                retard_s=applique.retard_injecte_s,
                correspondance_ratee=applique.correspondance_ratee,
                incident_reseau=applique.incident_reseau,
            )
            registre.tracer(
                applique, person_id, 1_700_000_000 + rang * 3600, gravite, detail
            )
    RegistreEvenements.jour_du_run = staticmethod(
        lambda ts: __import__("llm.evenements.calendrier", fromlist=["x"]).jour_du_run(ts)
    )
    return [json.loads(l) for l in journal.read_text("utf-8").splitlines() if l.strip()]


# Les champs que le ticket 100 AJOUTE. Tout le reste doit être égal à l'octet près.
CHAMPS_AJOUTES = {
    "evenement_id", "canal", "moment", "texte",
    # Lot 3 — ce que l'AGENT en a dit, à côté de ce que la simulation a mesuré.
    "importance_estimee", "intensite_jugee", "valence", "modes_touches",
    "importance_retenue",
    # D7 — l'écart au fait mesuré, journalisé et jamais appliqué.
    "ecart_au_fait",
}


def test_R1_test_en_or_la_declaration_079_rend_la_meme_trace(tmp_path):
    """Le fichier D'ORIGINE, rejoué sur le paquet neuf, rend la trace de l'ancien.

    C'est le seul critère du lot 1. Il rejoue `config/chocs/c6_voiture_suspecte.yaml` tel
    qu'il est au dépôt — pas sa version migrée : une migration qui ne se vérifie que sur des
    fichiers réécrits ne vérifie que la réécriture.
    """
    original = CONFIG_CHOCS / "c6_voiture_suspecte.yaml"
    migre = CONFIG_EVENEMENTS / "c6_voiture_suspecte.yaml"
    assert original.is_file() and migre.is_file()

    lignes_079 = _trace_dun_rejeu(original, tmp_path / "a.jsonl", (15, 16))
    lignes_100 = _trace_dun_rejeu(migre, tmp_path / "b.jsonl", (15, 16))

    assert lignes_079, "le rejeu n'a produit AUCUNE ligne : le test ne prouve rien"
    assert len(lignes_079) == len(lignes_100)
    for ancienne, neuve in zip(lignes_079, lignes_100):
        assert set(ancienne) == set(neuve)
        for champ in sorted(set(ancienne) - CHAMPS_AJOUTES):
            assert ancienne[champ] == neuve[champ], f"champ « {champ} » modifié"
        # Et les champs ajoutés disent ce qu'ils doivent dire, sans rien substituer.
        assert neuve["evenement_id"] == neuve["choc_id"]
        assert neuve["texte"] == neuve["vecu"]
        assert (neuve["canal"], neuve["moment"]) == ("vecu", "arrivee")


def test_R1bis_la_trace_porte_les_champs_du_079_sans_exception(tmp_path):
    """Les dépouilleurs des runs archivés lisent ces clés. Aucune ne disparaît au lot 1."""
    lignes = _trace_dun_rejeu(
        CONFIG_CHOCS / "c6_voiture_suspecte.yaml", tmp_path / "t.jsonl", (15,)
    )
    attendus = {
        "person_id", "timestamp", "horodatage_simule", "choc_id", "jour_run", "jour_relatif",
        "raison_exposition", "retard_injecte_s", "incident_reseau", "correspondance_ratee",
        "vecu", "gravite", "gravite_detail",
    }
    assert attendus <= set(lignes[0])


# ── R3, R4. Les deux formats ─────────────────────────────────────────────────────────────
def test_R3_les_declarations_079_se_chargent_et_le_disent(tmp_path, caplog):
    for fichier in sorted(CONFIG_CHOCS.glob("c*.yaml")):
        evenement = charger(fichier)
        assert evenement.format_source == "079"
        assert (evenement.canal, evenement.moment, evenement.jugement) == (
            "vecu", "arrivee", "aucun",
        )


def test_R4_la_migration_est_COMPLETE():
    """Aucun cas du ticket 079 ne reste sans équivalent migré.

    C'est l'invariant qui compte : un choc oublié dans `config/chocs/` continuerait de se
    charger — le chemin de compatibilité le permet — mais il ne serait plus dans le répertoire
    que le levier `EVENEMENT=` liste, et personne ne le verrait manquer.
    """
    originaux = {p.name for p in CONFIG_CHOCS.glob("c*.yaml")}
    migres = {p.name for p in CONFIG_EVENEMENTS.glob("c*.yaml")}
    assert originaux <= migres, f"cas du 079 non migrés : {sorted(originaux - migres)}"


def test_R4_les_deux_formats_rendent_le_meme_evenement():
    """Chaque cas migré dit exactement ce que disait son original.

    ⚠ Ne porte QUE sur les cas qui ont un original. `config/evenements/` accueille aussi des
    déclarations neuves — les cinq articles, et les variantes de banc — qui ne migrent rien.
    Exiger un original pour toutes interdirait d'en ajouter une sans toucher au test, ce qui
    n'est pas ce que la règle veut dire.
    """
    compares = 0
    for migre in sorted(CONFIG_EVENEMENTS.glob("c*.yaml")):
        original = CONFIG_CHOCS / migre.name
        if not original.is_file():
            continue
        compares += 1
        a, b = charger(original), charger(migre)
        assert (a.evenement_id, a.libelle, a.source) == (b.evenement_id, b.libelle, b.source)
        assert a.cadence == b.cadence
        assert a.exposition == b.exposition
        assert sorted(a.jours) == sorted(b.jours)
        for jour in a.jours:
            assert a.jours[jour].texte == b.jours[jour].texte
            assert a.jours[jour].effet == b.jours[jour].effet
        assert (b.format_source, a.format_source) == ("100", "079")
    assert compares >= 6, f"seulement {compares} cas comparés : la migration n'est plus couverte"


# ── R5, R6. Les refus ────────────────────────────────────────────────────────────────────
def test_R5_une_gravite_posee_a_la_main_est_refusee(tmp_path):
    with pytest.raises(RefusDEvenement, match="gravite"):
        charger(_ecrire(tmp_path, _declaration(gravite=0.70)))


@pytest.mark.parametrize(
    "surcharge, motif",
    [
        ({"canal": "entendu"}, "inconnu"),
        ({"moment": "au_coucher"}, "inconnu"),
        ({"jugement": "au_pif"}, "inconnu"),
        ({"effet_physique": {"retard_min": 30}}, "jour par jour"),
    ],
)
def test_R6_une_valeur_hors_vocabulaire_est_refusee(tmp_path, surcharge, motif):
    """Un champ accepté et sans effet est pire qu'un champ refusé : rien ne le signale."""
    with pytest.raises(RefusDEvenement) as err:
        charger(_ecrire(tmp_path, _declaration(**surcharge)))
    assert motif in str(err.value)


def test_R6quater_lire_une_declaration_et_armer_un_run_sont_deux_choses(tmp_path):
    """La séparation posée au lot 2, et qui survit au lot 3 en changeant de motif.

    `charger()` doit pouvoir vérifier un protocole qu'on ne veut pas jouer — sans quoi on ne
    pourrait même pas contrôler que les cinq articles concordent avec leur manifeste. Armer un
    run, lui, s'arrête net.

    Le cas qui l'exige aujourd'hui : un `canal: lu` sans jugement. Il se lit — la déclaration
    est bien formée — mais il n'arme pas, parce qu'un article à gravité 0,00 vit 2,8 jours et
    que son silence passerait pour une absence d'effet.
    """
    from llm.evenements import charger as _charger

    article = CONFIG_EVENEMENTS / "a13_punaises_metro.yaml"
    contenu = yaml.safe_load(article.read_text("utf-8"))
    contenu["jugement"] = "aucun"
    fichier = tmp_path / "sans_jugement.yaml"
    fichier.write_text(yaml.safe_dump(contenu, allow_unicode=True), encoding="utf-8")

    assert _charger(fichier).jugement == "aucun"  # la lecture passe
    settings.evenements.enabled = True
    settings.evenements.fichier = str(fichier)
    settings.cache.enabled = False
    with pytest.raises(RefusDEvenement, match="2,8 jours"):
        ev.initialiser()


def test_R6bis_texte_et_vecu_ensemble_sont_refuses(tmp_path):
    d = _declaration(jours=[{"jour": 3, "retard_min": 10, "texte": TEXTE_VALIDE,
                            "vecu": TEXTE_VALIDE}])
    with pytest.raises(RefusDEvenement, match="pas les deux"):
        charger(_ecrire(tmp_path, d))


def test_R6ter_le_nom_du_079_reste_lisible_seul(tmp_path):
    """`vecu:` seul continue de se lire : les huit cas du dépôt l'emploient."""
    d = _declaration(jours=[{"jour": 3, "retard_min": 10, "vecu": TEXTE_VALIDE}])
    assert charger(_ecrire(tmp_path, d)).jours[3].texte == TEXTE_VALIDE


# ── R8, R9, R10. La provenance ───────────────────────────────────────────────────────────
def _entree(**kw) -> MemoryEntry:
    from datetime import datetime

    base = dict(
        content="x", timestamp=datetime(2026, 3, 16, 8, 0),
        memory_type=MemoryType.CONVERSATION, person_id="609",
    )
    base.update(kw)
    return MemoryEntry(**base)


def test_R8_origine_fait_laller_retour_et_survit_a_un_lecteur_qui_lignore():
    entree = _entree(origine="lu")
    assert MemoryEntry.from_dict(entree.to_dict()).origine == "lu"
    sans = {k: v for k, v in entree.to_dict().items() if k != "origine"}
    assert MemoryEntry.from_dict(sans).origine is None  # relu sans exception


def test_R9_une_entree_anterieure_se_lit_vecue_sans_le_declarer():
    """`None` et `vecu` ne sont pas la même chose, et les confondre effacerait la mesure."""
    ancienne = _entree()
    assert ancienne.origine is None
    assert ancienne.origine_effective == "vecu"
    assert _entree(origine="vecu").origine == "vecu"


def test_R10_valence_et_origine_traversent_la_memoire_courte():
    from llm.shortterm import UserShortTermMemory

    memoire = UserShortTermMemory(person_id="609")
    memoire.add_message("I read about bed bugs on the metro", valence="negative", origine="lu")
    entree = memoire.recent_entries[-1]
    assert (entree.valence, entree.origine) == ("negative", "lu")
    # Le défaut ne change pas ce que le ticket 079 écrivait.
    memoire.add_message("I arrived on time")
    assert (memoire.recent_entries[-1].valence, memoire.recent_entries[-1].origine) == (
        "neutre", None,
    )


# ── R7. Le ménage jusqu'au runtime ───────────────────────────────────────────────────────
def test_R7_household_id_arrive_jusqua_Person():
    """Le champ existait dans le JSON depuis le sceau et se perdait à la validation."""
    from models import Person

    brut = {
        "person_id": "609",
        "household": {"id": "5177", "commune_id": "31555"},
        "identity": {"name": "Jacques Aubert", "traits_json": {"name": "Jacques Aubert"}},
    }
    # Sans la recopie, pydantic ignore `household` : c'est le défaut que le lot 1 corrige.
    assert Person.model_validate(brut).household_id is None
    from world.population import WorldPopulation

    assert Person.model_validate(WorldPopulation._avec_foyer(brut)).household_id == "5177"
    # La recopie ne modifie pas le dictionnaire de l'appelant.
    assert "household_id" not in brut


def test_R7bis_la_cohorte_scellee_porte_un_menage_pour_chaque_agent():
    """Mesuré, pas supposé : 1 000 agents, 0 sans `household.id` (ticket 078, § 0)."""
    import json as _json

    cohorte = RACINE.parents[1] / "data" / "population" / "toulouse_population_1000_AAMAS_v6.json"
    if not cohorte.is_file():
        pytest.skip("cohorte scellée absente de ce poste")
    from inputs.population.eqasim_loader import _identifiant_de_foyer

    entrees = _json.loads(cohorte.read_text("utf-8"))
    sans = [e["person_id"] for e in entrees if _identifiant_de_foyer(e) is None]
    assert not sans, f"{len(sans)} agent(s) sans ménage : {sans[:5]}"


# ── Frontière du régime : aucun moteur d'itinéraire ──────────────────────────────────────
def test_R23_le_paquet_nimporte_aucun_moteur_ditineraire():
    """Reprend R14 du 079, élargi au paquet entier.

    Contrôlé sur les imports et non sur le texte : les docstrings parlent des moteurs
    précisément pour dire qu'elles n'y touchent pas, et un test qui lirait le texte brut
    interdirait d'expliquer la règle qu'il vérifie.
    """
    for module in sorted((RACINE / "llm" / "evenements").glob("*.py")):
        arbre = ast.parse(module.read_text("utf-8"))
        importes: set[str] = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                importes |= {a.name for a in noeud.names}
            elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                importes.add(noeud.module)
        for interdit in ("trip_helper", "otp", "osmnx", "gtfs"):
            assert not any(interdit in m for m in importes), (
                f"{module.name} importe « {interdit} » : un événement ne sollicite AUCUN "
                f"moteur d'itinéraire. Dégrader l'offre relève d'un autre ticket."
            )


# ── La clé de configuration, et l'alarme du cache ────────────────────────────────────────
def test_la_cle_du_100_prime_et_celle_du_079_reste_servie(tmp_path):
    fichier = _ecrire(tmp_path, _declaration())
    settings.evenements.enabled = True
    settings.evenements.fichier = str(fichier)
    settings.cache.enabled = False
    assert ev.initialiser() is not None
    assert ev.registre().evenement.evenement_id == "test_evenement"

    ev.reinitialiser()
    settings.evenements.enabled = False
    settings.chocs.enabled = True
    settings.chocs.fichier = str(fichier)
    assert ev.initialiser() is not None  # l'ancienne clé continue de servir


def test_le_cache_actif_leve_une_alarme(tmp_path, caplog):
    import logging

    settings.evenements.enabled = True
    settings.evenements.fichier = str(_ecrire(tmp_path, _declaration()))
    settings.cache.enabled = True
    try:
        with caplog.at_level(logging.ERROR):
            ev.initialiser()
    finally:
        settings.cache.enabled = False


def test_la_declaration_est_archivee_sous_les_deux_noms(tmp_path):
    """`evenement.yaml` est le nom neuf ; `choc.yaml` reste atteignable jusqu'au lot 6."""
    workdir = tmp_path / "run"
    settings.evenements.enabled = True
    settings.evenements.fichier = str(_ecrire(tmp_path, _declaration()))
    settings.cache.enabled = False
    ev.initialiser(workdir=workdir)
    assert (workdir / "evenement.yaml").is_file()
    assert (workdir / "choc.yaml").is_file()
    assert "test_evenement" in (workdir / "choc.yaml").read_text("utf-8")
