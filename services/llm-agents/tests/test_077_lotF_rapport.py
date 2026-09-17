"""Ticket 077, lot F — le rapport d'analyse par persona.

Contrat : `specs/ticket_077/tests.md` § F.

Les cas F1 à F7 tournent sur une **fixture minimale** construite dans `tmp_path` :
le rapport doit pouvoir être vérifié sans le run de référence, qui pèse plusieurs
centaines de mégaoctets et n'est pas versionné. Un seul test de bout en bout se
branche sur `experiments/archive/2026-09-14_23_58` quand il est présent.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.analysis.memoire import graphiques, mesures, rapport, sources

RUN_REFERENCE = (
    Path(__file__).resolve().parents[3] / "experiments" / "archive" / "2026-09-14_23_58"
)

JOUR1, JOUR2 = "2026-03-16", "2026-03-17"

COLONNES = [
    "ID Personne",
    "ID Activité",
    "ID Trajet",
    "Mode de transport Choisi",
    "Modes proposés au LLM",
    "P(Marche) %",
    "P(Vélo) %",
    "P(Voiture Privée) %",
    "P(Transports_collectifs) %",
    "P(Train) %",
    "P(Deux-roues motorisé) %",
    "P(Autres modes) %",
    "Motifs de déplacement",
    "Méthode de sélection",
    "Heure de départ",
    "Heure de calcul",
    "Raisonnement",
    "Distance parcourue",
    "Météo Température (°C)",
    "Météo Condition",
    "Temps simulé",
    "Fournisseur & Modèle",
]


def _ligne(**valeurs: str) -> dict[str, str]:
    ligne = {colonne: "" for colonne in COLONNES}
    ligne.update(valeurs)
    return ligne


def _prompt_decision(agent: str, motif: str, depart: str) -> str:
    """Un prompt de décision, au format exact du run : options et sous-puces."""
    return (
        f"--- agent_id={agent} | Destination: {motif} (a neighbourhood) | "
        f"Departure: {depart} ---\n"
        "**Context:** Weather: 7°C, Clear/Sunny.\n"
        "\n"
        "**Trip options** (2 options, indices 0 to 1):\n"
        "- [0] car: Estimated duration: 8 minutes. Distance: 6.5 km.\n"
        "- [1] foot,bus,foot: Travel time: 30 minutes, including 10 minutes of walking.\n"
        "    · Walk to 'Arènes': 4 minutes.\n"
        "    · Bus 'L2' to 'Jean Jaurès': 20 minutes.\n"
        "    · Walk to 'work': 6 minutes.\n"
        "\n"
        "**History:** ce que l'agent se rappelle.\n"
    )


def _echange_decision(jour: str, agent: str, motif: str, depart: str) -> dict:
    return {
        "time": "2026-09-14T21:59:57.543381+00:00",
        "sim_ts": 1773644772.0,
        "sim_day": jour,
        "task_id": f"batch_{jour}_{agent}",
        "provider": "google_gemini31_key1",
        "category": "itinary_multi_agent",
        "tokens_in": 3054,
        "tokens_out": 919,
        "messages": [
            {"role": "system", "content": "# INSTRUCTION"},
            {"role": "user", "content": _prompt_decision(agent, motif, depart)},
        ],
        "response": [{"agent_id": agent, "chosen_index": None, "mode": None}],
    }


def _echange_reflexion(jour: str, croyances: dict[str, list]) -> dict:
    blocs = ["# INPUT DATA"]
    for agent, connues in sorted(croyances.items()):
        charge = json.dumps(
            {
                "today": [{"purpose": "work", "observations": []}],
                "known_beliefs": connues,
            },
            indent=2,
        )
        blocs.append(f"--- AGENT {agent} ---\n\n```json\n{charge}\n```\n")
    return {
        "time": "2026-09-14T22:10:00+00:00",
        "sim_day": jour,
        "task_id": f"reflexion_{jour}",
        "provider": "google_gemini31_key1",
        "category": "stm_reflection",
        "messages": [{"role": "user", "content": "\n".join(blocs)}],
        "response": [],
    }


def _concept(doc: str, enonce: str, horodatage: str, **extra) -> dict:
    entree = {
        "content": json.dumps([enonce, "mots, clés", "au travail", "matin", "work"]),
        "timestamp": horodatage,
        "memory_type": "concept",
        "person_id": "1",
        "doc_id": doc,
        "importance": 0.5,
        "valence": "negative",
        "axe_objet": None,
        "axe_lieu": "au travail",
        "axe_creneau": "matin",
        "axe_motif": "work",
        "axe_meteo": None,
        "force": 12.0,
        "rappels": 3,
        "dernier_rappel": "2026-03-17T08:00:00",
        "observations": 0,
        "contre_exemples": 0,
    }
    entree.update(extra)
    return entree


@pytest.fixture()
def run_minimal(tmp_path: Path) -> Path:
    """Un run miniature : deux agents, deux jours, un rejeu, un trajet non apparié.

    Agent 1 (Alice) décide par LLM et porte des concepts ; agent 2 (Bob) n'a aucun
    concept et son unique trajet n'a **pas** de prompt correspondant — c'est le cas
    de la colonne grise.
    """
    racine = tmp_path / "run"
    (racine / "gama_results").mkdir(parents=True)
    (racine / "memoires").mkdir()
    (racine / "long_term_memory" / "user_metadata" / "shard_01").mkdir(parents=True)

    lignes = [
        # Décision d'origine, jour 1.
        _ligne(
            **{
                "ID Personne": "1",
                "ID Activité": "A1",
                "ID Trajet": "t1",
                "Mode de transport Choisi": "Voiture Privée",
                "Modes proposés au LLM": "Voiture Privée | Transports_collectifs",
                "P(Voiture Privée) %": "70.0",
                "P(Transports_collectifs) %": "30.0",
                "Motifs de déplacement": "Travail",
                "Méthode de sélection": "LLM",
                "Heure de départ": f"{JOUR1} 08:00:00",
                "Heure de calcul": "2026-09-14T22:00:00+00:00",
                "Raisonnement": "The car is faster as usual.",
                "Distance parcourue": "6.5",
                "Météo Température (°C)": "7",
                "Météo Condition": "Clear/Sunny",
                "Temps simulé": "1000",
                "Fournisseur & Modèle": "google_gemini31_key1",
            }
        ),
        # LE MÊME trajet, recalculé après redémarrage : c'est du rejeu.
        _ligne(
            **{
                "ID Personne": "1",
                "ID Activité": "A1",
                "ID Trajet": "t1bis",
                "Mode de transport Choisi": "Marche",
                "Modes proposés au LLM": "Voiture Privée | Marche",
                "P(Marche) %": "100.0",
                "Motifs de déplacement": "Travail",
                "Méthode de sélection": "LLM",
                "Heure de départ": f"{JOUR1} 08:00:00",
                "Heure de calcul": "2026-09-15T04:56:37+00:00",
                "Distance parcourue": "6.5",
                "Temps simulé": "1000",
                "Fournisseur & Modèle": "google_gemini31_key1",
            }
        ),
        # Jour 2, même activité, autre instant simulé : ce n'est PAS du rejeu.
        _ligne(
            **{
                "ID Personne": "1",
                "ID Activité": "A1",
                "ID Trajet": "t2",
                "Mode de transport Choisi": "Transports_collectifs",
                "Modes proposés au LLM": "Voiture Privée | Transports_collectifs",
                "P(Voiture Privée) %": "40.0",
                "P(Transports_collectifs) %": "60.0",
                "Motifs de déplacement": "Travail",
                "Méthode de sélection": "LLM",
                "Heure de départ": f"{JOUR2} 08:05:00",
                "Heure de calcul": "2026-09-14T23:00:00+00:00",
                "Raisonnement": "The bus worked well yesterday.",
                "Distance parcourue": "6.6",
                "Temps simulé": "2000",
                "Fournisseur & Modèle": "google_gemini31_key1",
            }
        ),
        # Agent 2 : aucun prompt ne lui correspond → appariement manqué.
        _ligne(
            **{
                "ID Personne": "2",
                "ID Activité": "B1",
                "ID Trajet": "t3",
                "Mode de transport Choisi": "Vélo",
                "Modes proposés au LLM": "Vélo",
                "Motifs de déplacement": "Achats",
                "Méthode de sélection": "Un seul itinéraire disponible",
                "Heure de départ": f"{JOUR1} 09:00:00",
                "Heure de calcul": "2026-09-14T22:05:00+00:00",
                "Distance parcourue": "2.0",
                "Temps simulé": "1100",
            }
        ),
    ]
    with (racine / "moves.csv").open("w", newline="", encoding="utf-8") as flux:
        redacteur = csv.DictWriter(flux, fieldnames=COLONNES)
        redacteur.writeheader()
        redacteur.writerows(lignes)

    # `llm_exchanges.jsonl` : objets JSON INDENTÉS concaténés, comme le vrai fichier.
    echanges = [
        _echange_decision(JOUR1, "1", "work", "08:00"),
        _echange_decision(JOUR2, "1", "work", "08:05"),
        _echange_reflexion(JOUR1, {"1": [{"content": "le bus est fiable"}], "2": []}),
    ]
    (racine / "llm_exchanges.jsonl").write_text(
        "\n".join(json.dumps(e, indent=2, ensure_ascii=False) for e in echanges),
        encoding="utf-8",
    )

    # Une marche fantôme : durée = retard au départ du trajet qui la contient.
    evenements = [
        {
            "context": "shortterm_memory",
            "timestamp": 1500,
            "person_id": "1",
            "message": "[ WALK ] Walked to ''. Duration: 1 hour, 0 minutes. Weather: 7°C, Clear/Sunny.",
            "activity_id": "A1",
            "data": {"type": None},
        },
        {
            "context": "shortterm_memory",
            "timestamp": 1600,
            "person_id": "1",
            "message": "[ PUBLIC TRANSPORT ] Trip by Unknown Unknown; From: ''; To: ''; "
            "Actual duration: 9 minutes.",
            "activity_id": "A1",
            "data": {"type": None},
        },
    ]
    (racine / "agent_memory_events.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in evenements) + "\n",
        encoding="utf-8",
    )

    with (racine / "gama_results" / "gama_arrivals.csv").open(
        "w", newline="", encoding="utf-8"
    ) as flux:
        redacteur = csv.writer(flux)
        redacteur.writerow(
            [
                "move_id",
                "person_id",
                "arrive_at",
                "expected_arrive_at",
                "delay_s",
                "started_at",
                "schedule_at",
                "departure_delay_s",
                "timed_out",
            ]
        )
        redacteur.writerow(
            ["t1", "1", "2000", "1900", "100", "1000", "1400", "-3600", "False"]
        )

    metadonnees = {
        "person_id": "1",
        "entries": [
            _concept(
                "1_0",
                "Walking to work takes far too long and is exhausting.",
                "2026-03-16T05:00:00",
            ),
            _concept(
                "1_1",
                "Walking to work is far too long and really exhausting.",
                "2026-03-17T05:00:00",
                observations=2,
                contre_exemples=1,
            ),
            _concept(
                "1_2",
                "The bus is reliable and cheap for the morning commute.",
                "2026-03-17T05:00:01",
            ),
            {
                "content": "Une réflexion narrative sur la journée.",
                "timestamp": "2026-03-16T05:00:02",
                "memory_type": "reflection",
                "person_id": "1",
                "doc_id": "1_3",
                "importance": 0.0,
                "valence": "neutre",
                "force": 3.0,
                "rappels": 1,
                "observations": 0,
                "contre_exemples": 0,
            },
        ],
        "journal": {
            "work|matin": {
                "modes": {"car": 1, "public_transport": 1},
                "retards": 0,
                "total": 2,
            }
        },
    }
    (racine / "long_term_memory" / "user_metadata" / "shard_01" / "1.json").write_text(
        json.dumps(metadonnees, ensure_ascii=False), encoding="utf-8"
    )
    # Agent 2 : des métadonnées, mais AUCUN concept.
    (racine / "long_term_memory" / "user_metadata" / "shard_01" / "2.json").write_text(
        json.dumps({"person_id": "2", "entries": [], "journal": {}}), encoding="utf-8"
    )

    (racine / "memoires" / "1.md").write_text(
        "# Mémoire d'Alice — agent 1\n\n"
        "### `18:00` CONSOLIDATION — déclencheur : **seuil**\n\n"
        '- opération **créé** · après : ["Walking to work…"] · gravité 0.50\n'
        '- opération **confirmé** · après : ["Walking to work…"] · gravité 0.50\n'
        "- `07:06` **rappel** — 2 souvenir(s) servi(s) : Walking to work takes far…"
        " (force 12.2 j, rappels 1) · The bus is reliable and cheap… (force 8.8 j, rappels 1)\n",
        encoding="utf-8",
    )
    # Doublon traduit : il ne doit JAMAIS être lu (il doublerait chaque compteur).
    (racine / "memoires" / "1_FR.md").write_text(
        "### `18:00` CONSOLIDATION — déclencheur : **seuil**\n"
        '- opération **créé** · après : ["…"] · gravité 0.50\n',
        encoding="utf-8",
    )

    population = [
        {
            "person_id": "1",
            "identity": {
                "name": "Alice Martin",
                "traits_json": {
                    "age": 40,
                    "main_occupation": "Full-time worker",
                    "income": "Low",
                    "car_availability": "all",
                    "personal_bike": "No bike",
                    "has_pt_subscription": False,
                    "residence_commune": "Toulouse",
                    "residence_zone": "1st ring",
                },
                "activities": [{"purpose": "work", "scheduled_start_time": 28800.0}],
            },
        },
        {
            "person_id": "2",
            "identity": {
                "name": "Bob Durand",
                "traits_json": {
                    "age": 30,
                    "main_occupation": "Retired",
                    "residence_commune": "Blagnac",
                    "residence_zone": "2nd ring",
                },
                "activities": [{"purpose": "shop", "scheduled_start_time": 32400.0}],
            },
        },
    ]
    (racine / "population_2.json").write_text(
        json.dumps(population, ensure_ascii=False), encoding="utf-8"
    )
    return racine


# ── F1 — le rejeu est exclu et déclaré ───────────────────────────────────────


def test_F1_rejeu_exclu_et_declare(run_minimal: Path) -> None:
    trajets, rejeu, detail = sources.lire_moves(run_minimal)
    assert rejeu == 1, (
        "la seconde ligne du même (personne, activité, instant simulé) est du rejeu"
    )
    assert len(detail) == 1
    identifiants = {t.trajet_id for t in trajets}
    assert identifiants == {"t1", "t2", "t3"}, (
        "on garde la PREMIÈRE par heure de calcul"
    )

    html = rapport.construire(sources.charger(run_minimal))
    assert "Rejeu exclu." in html
    assert "1 trajet(s) rejoué(s)" in html, (
        "le nombre de trajets rejoués doit être déclaré"
    )


def test_F1_activite_repetee_les_jours_suivants_nest_pas_du_rejeu(
    run_minimal: Path,
) -> None:
    """La même activité revient chaque jour : seul l'instant simulé sépare les décisions."""
    trajets, rejeu, _ = sources.lire_moves(run_minimal)
    jours = sorted(t.jour for t in trajets if t.person_id == "1")
    assert jours == [JOUR1, JOUR2]
    assert rejeu == 1


# ── F2 — llm_exchanges.jsonl n'est pas du JSONL ──────────────────────────────


def test_F2_json_concatene_multiligne(run_minimal: Path) -> None:
    contenu = (run_minimal / "llm_exchanges.jsonl").read_text(encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        json.loads(contenu.splitlines()[0])  # une lecture ligne à ligne échoue

    echanges = sources.lire_echanges(run_minimal)
    assert len(echanges) == 3
    assert [e["category"] for e in echanges] == [
        "itinary_multi_agent",
        "itinary_multi_agent",
        "stm_reflection",
    ]

    blocs = sources.blocs_itineraires(echanges)
    assert len(blocs) == 2
    assert {b.motif for b in blocs} == {"work"}
    assert [o.mode_brut for o in blocs[0].options] == ["car", "foot,bus,foot"]
    # Les sous-puces « · » sont des ÉTAPES, pas des options.
    assert len(blocs[0].options[1].etapes) == 3
    assert blocs[0].a_historique


def test_F2_blocs_de_reflexion_lus(run_minimal: Path) -> None:
    blocs = sources.blocs_reflexion(sources.lire_echanges(run_minimal))
    assert {(b.agent, b.nb_croyances) for b in blocs} == {("1", 1), ("2", 0)}
    mesure = mesures.croyances(blocs)
    assert (mesure.blocs, mesure.vides) == (2, 1)


# ── F3 — l'appariement manqué est déclaré, jamais muet ───────────────────────


def test_F3_option_non_retrouvee_colonne_grise_declaree(run_minimal: Path) -> None:
    run = sources.charger(run_minimal)
    trajets = [t for t in run.trajets if t.person_id == "2"]
    appariement = mesures.apparier(trajets, [b for b in run.blocs if b.agent == "2"])
    assert appariement.non_apparies == 1
    assert appariement.par_trajet["t3"] is None

    tableaux = mesures.tableaux_itineraires(trajets, appariement)
    assert [t.motif for t in tableaux] == ["shop"]
    assert tableaux[0].jours_gris == [JOUR1]

    svg = graphiques.tableau_itineraires(tableaux[0], run.jours)
    assert graphiques.GRIS_MANQUANT in svg, "la case grise doit être dessinée"
    assert "appariement manqué" in svg

    html = rapport.construire(run)
    assert "sans option retrouvée dans les prompts" in html
    assert "Appariement trajet ↔ prompt : 0 sur 1" in html


# ── F4 — le tableau des itinéraires ──────────────────────────────────────────


def test_F4_une_ligne_par_itineraire_une_colonne_par_jour(run_minimal: Path) -> None:
    run = sources.charger(run_minimal)
    trajets = [t for t in run.trajets if t.person_id == "1"]
    appariement = mesures.apparier(trajets, [b for b in run.blocs if b.agent == "1"])
    assert appariement.apparies == 2

    tableau = next(t for t in mesures.tableaux_itineraires(trajets, appariement)
                   if t.motif == "work")
    assert len(tableau.lignes) == 2, "une ligne par itinéraire DISTINCT (mode + étapes)"

    par_mode = {ligne.mode_brut: ligne for ligne in tableau.lignes}
    assert set(par_mode) == {"car", "foot,bus,foot"}
    # Jour 1 : la voiture est retenue ; jour 2 : le transport collectif.
    assert par_mode["car"].cases == {JOUR1: "retenu", JOUR2: "propose"}
    assert par_mode["foot,bus,foot"].cases == {JOUR1: "propose", JOUR2: "retenu"}

    svg = graphiques.tableau_itineraires(tableau, run.jours)
    assert graphiques.BLEU_PROPOSE in svg, "bleu clair = proposé"
    assert graphiques.BLEU_RETENU in svg, "bleu foncé = retenu"
    assert "proposé ce jour-là" in svg and "retenu ce jour-là" in svg, (
        "légende explicite"
    )
    # Une colonne par jour du run, sur chacune des deux lignes.
    assert svg.count(f"<title>{JOUR1} ·") + svg.count(f"<title>{JOUR2} ·") == 4


def test_F4_un_tableau_par_motif(run_minimal: Path) -> None:
    run = sources.charger(run_minimal)
    html = rapport.construire(run)
    assert "Itinéraires proposés et retenus" in html
    assert "TRAVAIL" not in html  # les titres de motif sont en casse naturelle…
    assert "Travail" in html and "Achats" in html


# ── F5 — la palette des modes est celle du dépôt ─────────────────────────────


def test_F5_palette_officielle() -> None:
    assert sources.MODE_COULEURS["car"] == "#EE4444"
    assert sources.MODE_COULEURS["cycling"] == "#8844BB"
    assert sources.MODE_COULEURS["public_transport"] == "#22AA44"
    assert sources.MODE_COULEURS["walking"] == "#00CCCC"
    assert sources.MODE_COULEURS["train"] == "#8844BB"
    assert sources.MODE_COULEURS["motorbike"] == "magenta"


def test_F5_la_frise_utilise_la_palette(run_minimal: Path) -> None:
    run = sources.charger(run_minimal)
    trajets = [t for t in run.trajets if t.person_id == "1"]
    svg = graphiques.frise_modes(mesures.frise(trajets, run.jours), run.jours)
    assert 'fill="#EE4444"' in svg, "voiture rouge"
    assert 'fill="#22AA44"' in svg, "transports collectifs vert"
    svg2 = graphiques.frise_modes(
        mesures.frise([t for t in run.trajets if t.person_id == "2"], run.jours),
        run.jours,
    )
    assert 'fill="#8844BB"' in svg2, "vélo violet"


# ── F6 — un agent sans concept produit sa section, vide et déclarée ──────────


def test_F6_agent_sans_concept_section_declaree(run_minimal: Path) -> None:
    run = sources.charger(run_minimal)
    assert mesures.concepts(run.ltm.get("2", [])) == []
    assert mesures.taux_redondance([]) is None, "aucun concept ≠ redondance nulle"

    html = rapport.construire(run)
    assert "Bob Durand" in html, "la section de l'agent sans concept existe"
    assert "Aucun concept en mémoire longue pour cet agent." in html
    assert "ce n'est pas un résultat propre" in html.lower(), (
        "l'absence de mesure ne doit pas se lire comme un score parfait"
    )
    assert "Agents sans aucun concept" in html, "la synthèse le déclare aussi"


def test_F6_les_concepts_de_lautre_agent_sont_regroupes_par_theme(
    run_minimal: Path,
) -> None:
    run = sources.charger(run_minimal)
    liste = mesures.concepts(run.ltm["1"])
    assert len(liste) == 3, "la réflexion narrative n'est pas un concept"
    themes = mesures.themes(liste)
    assert len(themes) == 2, "les deux reformulations de la marche font un seul thème"
    assert mesures.taux_redondance(liste) == pytest.approx(1 / 3)
    # Laplace : deux observations, un contre-exemple.
    assert mesures.confiance(2, 1) == pytest.approx(3 / 5)
    assert mesures.confiance(0, 0) == 0.5


# ── F7 — deux exécutions, le même octet ──────────────────────────────────────


def test_F7_rapport_reproductible(run_minimal: Path, tmp_path: Path) -> None:
    premier = rapport.ecrire(run_minimal, tmp_path / "un.html")
    second = rapport.ecrire(run_minimal, tmp_path / "deux.html")
    assert premier.read_bytes() == second.read_bytes()


def test_F7_aucun_horodatage_de_generation(run_minimal: Path) -> None:
    """Le corps ne porte que des dates issues du run, jamais l'heure de génération."""
    from datetime import datetime, timezone

    html = rapport.construire(sources.charger(run_minimal))
    aujourdhui = datetime.now(tz=timezone.utc).date().isoformat()
    assert aujourdhui not in html or aujourdhui in {JOUR1, JOUR2}
    for mot in ("généré le", "Généré le", "generated at"):
        assert mot not in html


# ── Rendu général ────────────────────────────────────────────────────────────


def test_rapport_autonome_et_echappe(run_minimal: Path) -> None:
    html = rapport.construire(sources.charger(run_minimal))
    assert html.startswith("<!DOCTYPE html>")
    assert "<style>" in html, "CSS en ligne"
    for interdit in ("http://", "https://", "<script"):
        assert interdit not in html, f"le rapport doit être autonome ({interdit})"
    assert "overflow-x: auto" in html, "les tableaux larges défilent"
    assert "width=device-width" in html


def test_rapport_echappe_le_contenu_du_modele(
    tmp_path: Path, run_minimal: Path
) -> None:
    """Les énoncés de concepts viennent d'un modèle de langue : rien n'est du HTML."""
    fichier = run_minimal / "long_term_memory" / "user_metadata" / "shard_01" / "1.json"
    charge = json.loads(fichier.read_text(encoding="utf-8"))
    charge["entries"][0]["content"] = json.dumps(
        ["<img src=x onerror=alert(1)> & « cité »", "k", "l", "c", "m"]
    )
    fichier.write_text(json.dumps(charge, ensure_ascii=False), encoding="utf-8")

    html = rapport.construire(sources.charger(run_minimal))
    assert "<img src=x" not in html
    assert "&lt;img src=x onerror=alert(1)&gt; &amp;" in html


def test_contamination_et_rappels(run_minimal: Path) -> None:
    run = sources.charger(run_minimal)
    contamination = mesures.contamination(run)
    assert contamination.marches_examinees == 1
    assert contamination.marches_fantomes == 1, (
        "3600 s de marche = 3600 s de retard au départ"
    )
    assert contamination.tc_anonymes == 1
    assert contamination.voiture_en_tc == 1, (
        "le trajet t1 est une voiture journalisée en TC"
    )

    journal = run.journaux["1"]
    assert set(run.journaux) == {"1"}, "le doublon 1_FR.md ne doit pas être lu"
    assert journal.consolidations == 1
    assert journal.operations == {"créé": 1, "confirmé": 1}
    mesure = mesures.rappels(journal)
    assert (mesure.evenements, mesure.servis) == (1, 2)
    assert mesure.concentration == pytest.approx(100.0)


def test_semaines_sans_decision_ne_valent_pas_zero(run_minimal: Path) -> None:
    run = sources.charger(run_minimal)
    semaines = mesures.semaines(
        [t for t in run.trajets if t.person_id == "2"], run.jours
    )
    assert len(semaines) == 1
    assert semaines[0].n == 0
    assert semaines[0].decisivite is None and semaines[0].entropie is None


def test_cli(run_minimal: Path, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    code = rapport.main([str(run_minimal), "-o", str(tmp_path / "cli.html")])
    assert code == 0
    assert (tmp_path / "cli.html").is_file()
    assert "[OK]" in capsys.readouterr().out

    assert rapport.main([str(tmp_path / "absent"), "-o", str(tmp_path / "x.html")]) == 2


# ── Bout en bout sur le run de référence ─────────────────────────────────────


@pytest.mark.skipif(
    not RUN_REFERENCE.is_dir(), reason=f"run de référence absent : {RUN_REFERENCE}"
)
def test_bout_en_bout_run_de_reference(tmp_path: Path) -> None:
    run = sources.charger(RUN_REFERENCE)
    assert run.rejeu == 84, "les 84 trajets rejoués du redémarrage de 06:55"
    assert len(run.trajets) == 430
    assert len(run.agents) == 5
    assert len(run.jours) == 30

    premier = rapport.ecrire(RUN_REFERENCE, tmp_path / "a.html")
    second = rapport.ecrire(RUN_REFERENCE, tmp_path / "b.html")
    assert premier.read_bytes() == second.read_bytes(), "F7 sur le run réel"

    html = premier.read_text(encoding="utf-8")
    for nom in (
        "Xavier Briand",
        "Constance Ledoux",
        "Valérie Duhamel",
        "Adrienne Bonneau du Lejeune",
        "Corinne de la Richard",
    ):
        assert nom in html
    assert "84 trajet(s) rejoué(s)" in html
    # Le chiffre du ticket : 159 blocs de réflexion vides sur 235.
    assert "159 bloc(s) de réflexion sur 235" in html
