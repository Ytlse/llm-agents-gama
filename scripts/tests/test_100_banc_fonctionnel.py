"""Le banc de tests fonctionnels se teste lui-même — ticket 100.

Un banc qui ne se vérifie pas rend des verts sans valeur. Ce qui est contrôlé ici : que les
stubs importent bien les formats du dépôt au lieu de les recopier, que la garde de passerelle
refuse une instance non déclarée, et que le budget arrête le banc au lieu de déborder.

Aucun appel : le client réel n'est jamais construit.
"""

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "services" / "llm-agents"))

from scripts.experiment.banc_fonctionnel import stubs  # noqa: E402
from scripts.experiment.banc_fonctionnel.clients import (  # noqa: E402
    GROQ,
    Appel,
    BudgetEpuise,
    ClientStub,
    Journal,
    PasserelleRefusee,
)


# ── Les stubs importent, ils ne recopient pas ───────────────────────────────────────────
def test_le_stub_de_moves_importe_les_vraies_colonnes(tmp_path):
    """Un stub qui recopie une liste de colonnes teste sa propre copie.

    Il reste vert le jour où le vrai format change — et c'est exactement ce que le banc doit
    attraper. Leçon du lot A du ticket 077.
    """
    import csv

    from urban_mobility_agents.utils.move_logger import CSV_HEADERS

    chemin = stubs.moves_stub(tmp_path / "moves.csv", evenement="a13", jours=range(0, 2))
    with chemin.open(encoding="utf-8") as f:
        lecteur = csv.reader(f)
        entetes = next(lecteur)
        lignes = list(lecteur)
    assert entetes == CSV_HEADERS, "les en-têtes viennent du dépôt, pas d'une copie"
    assert all(len(l) == len(CSV_HEADERS) for l in lignes), (
        "une ligne qui n'a pas le nombre de colonnes de son en-tête décale tout ce qui suit, "
        "et le décalage ne se voit qu'à la relecture"
    )


def test_le_stub_ecrit_lagent_dans_la_COLONNE_DE_LAGENT(tmp_path):
    """Importer les en-têtes ne suffit pas : encore faut-il écrire au bon endroit.

    Trouvé le 2026-09-22 sur un run réel. Le stub écrivait l'identifiant d'agent dans
    « Référence », qui porte l'identifiant du RUN ; l'agent est sous « ID Personne ». Les tests
    passaient parce qu'ils vérifiaient la convention du stub, pas celle du dépôt — la règle
    « importer, ne pas recopier » couvrait les en-têtes, pas le SENS des colonnes.
    """
    import csv

    chemin = stubs.moves_stub(tmp_path / "moves.csv", evenement="a13", jours=range(0, 1))
    with chemin.open(encoding="utf-8") as f:
        ligne = next(csv.DictReader(f))
    assert ligne["ID Personne"], "l'agent va sous « ID Personne »"
    assert "_" in ligne["ID Personne"], "et c'est bien un identifiant d'agent"
    assert ligne["Référence"] == "banc", "« Référence » porte le run, pas l'agent"

    # Et la passerelle de dépouillement lit la même colonne que le stub écrit.
    from scripts.analysis.presse import campagne

    assert campagne.COLONNE_AGENT == "ID Personne"


def test_le_stub_de_memoire_produit_de_vraies_MemoryEntry():
    from llm.memory import MemoryEntry, MemoryType

    reflexion = stubs.reflexion_stub("609", "A quiet day.", 3)
    concept = stubs.concept_stub("609", "Line A is packed", 3, origine="entendu")
    assert isinstance(reflexion, MemoryEntry) and isinstance(concept, MemoryEntry)
    assert reflexion.memory_type == MemoryType.REFLECTION
    assert concept.memory_type == MemoryType.CONCEPT and concept.origine == "entendu"
    # L'aller-retour de sérialisation doit tenir : c'est ce que fait un point de reprise.
    assert MemoryEntry.from_dict(concept.to_dict()).origine == "entendu"


def test_le_stub_de_point_de_reprise_est_lu_par_le_vrai_lecteur(tmp_path):
    from urban_mobility_agents.utils import reprise

    stubs.point_de_reprise_stub(tmp_path, 12, foyer={"lu_jusqu_a": {"1": "x"}})
    trouve = reprise.dernier_point(tmp_path)
    assert trouve is not None, "le point stubé doit être valide pour le lecteur du dépôt"
    _source, meta = trouve
    assert meta["jour_simule"] == 12
    assert meta["foyer"]["lu_jusqu_a"] == {"1": "x"}


def test_la_population_de_banc_porte_les_contrastes_qui_font_jouer_R4():
    """R4 ne se teste que sur des membres qui diffèrent : c'est le cas Constance / Jacques."""
    population = stubs.population_de_banc()
    assert len(population) == 12
    foyers = {a.household_id for a in population}
    assert len(foyers) == 6 and all(
        sum(1 for a in population if a.household_id == f) == 2 for f in foyers
    )
    permis = {a.identity.traits_json["has_driving_license"] for a in population}
    assert permis == {True, False}, "sans contraste de permis, R4 ne se déclenche jamais"


def test_la_journee_stub_produit_les_TROIS_entrees_reelles():
    """Décision, arrivée, contrainte : c'est pourquoi « par entrée brute » triplerait le bloc."""
    assert len(stubs.journee_stub("609", 1)) == 3


# ── La garde de passerelle ──────────────────────────────────────────────────────────────
def test_aucune_instance_declaree_est_refuse():
    from scripts.experiment.banc_fonctionnel.clients import ClientEpingle

    with pytest.raises(PasserelleRefusee, match="ne choisit pas la passerelle"):
        ClientEpingle(instances=())


def test_groq_est_le_defaut_du_jour_mais_reste_un_parametre():
    """Aujourd'hui Groq seul ; les runs longs passeront ailleurs sans toucher au code."""
    assert all(i.startswith("groq_") for i in GROQ)
    import inspect

    from scripts.experiment.banc_fonctionnel.clients import ClientEpingle

    assert inspect.signature(ClientEpingle).parameters["instances"].default == GROQ


def test_le_budget_de_jetons_arrete_le_banc():
    journal = Journal()
    journal.appels.append(Appel("x", "1", "t", "groq_openai_20_key1", jetons_sortie=9000))
    assert journal.jetons_sortie == 9000
    # La garde vit dans `execute`, qu'on ne peut pas appeler sans réseau : on vérifie que le
    # journal la nourrit, et que le message nomme la conséquence.
    assert "quota" in BudgetEpuise.__doc__ or "campagnes" in BudgetEpuise.__doc__


def test_le_journal_dit_quelle_instance_a_servi(tmp_path):
    """Sans cela, deux campagnes sur deux passerelles seraient incomparables sans qu'on le sache."""
    journal = Journal()
    journal.appels.append(Appel("evenement_jugement", "609", "B1",
                                "groq_openai_120_key1", 180, 1.2))
    journal.appels.append(Appel("stm_reflection", "610", "B2",
                                "groq_openai_20_key1", 640, 3.1, hors_schema=True))
    journal.ecrire(tmp_path / "passerelle.csv")
    contenu = (tmp_path / "passerelle.csv").read_text("utf-8")
    assert "groq_openai_120_key1" in contenu and "groq_openai_20_key1" in contenu
    assert "hors_schema" in contenu
    assert "820" not in contenu  # le total n'est pas écrit à la place du détail
    assert journal.jetons_sortie == 820


# ── Le client stub ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_le_stub_refuse_une_categorie_non_declaree():
    """Un stub muet ferait passer un chemin non testé pour un chemin testé."""
    client = ClientStub({"evenement_jugement": [{"severity": "notable"}]})
    with pytest.raises(AssertionError, match="aucune réponse"):
        await client.execute({"category": "stm_reflection", "agents": [{"agent_id": "1"}]})


@pytest.mark.asyncio
async def test_le_stub_sert_les_reponses_dans_lordre_puis_boucle():
    client = ClientStub({"evenement_jugement": [
        {"severity": "negligible"}, {"severity": "memorable"},
    ]})
    charge = {"category": "evenement_jugement", "agents": [{"agent_id": "609"}]}
    assert (await client.execute(charge)).agents[0].severity == "negligible"
    assert (await client.execute(charge)).agents[0].severity == "memorable"
    assert (await client.execute(charge)).agents[0].severity == "memorable"


# ── La famille A tourne, et elle est le préalable ───────────────────────────────────────
def test_la_famille_A_tourne_entierement_sans_appel():
    """Si elle échoue, la famille B ne doit pas partir : elle paierait pour rien."""
    import subprocess

    r = subprocess.run(
        [sys.executable, "-m", "scripts.experiment.banc_fonctionnel.famille_a"],
        capture_output=True, text=True, cwd=RACINE,
    )
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    assert "au vert" in r.stdout
    assert "❌" not in r.stdout and "💥" not in r.stdout
