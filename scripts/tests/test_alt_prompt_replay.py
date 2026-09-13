"""Tests du rejeu « report marche → transports collectifs ».

Chaque test porte sur une décision qui, prise à l'envers, produit un résultat
**plausible mais faux** — c'est le seul type de défaut qui compte ici : le rejeu
appelle un modèle payant sur un sous-jeu, et un sous-jeu mal constitué rend des
chiffres parfaitement présentables.

Quatre pièges, tous rencontrés en vrai lors de la mise au point :

1. **La coupe au premier jour simulé, côté lignes brutes.** Le journal déborde du
   jour retenu, et le couple (personne, activité) y réapparaît le lendemain. Sans
   la coupe, on indexe la ligne du jour 2 et son « Heure de calcul » — 211 des 497
   décisions du sous-jeu passaient alors pour « sans lot retrouvé ».
2. **L'ambiguïté d'appariement se déclare, elle ne se devine pas.** Deux blocs du
   même agent dans la fenêtre de tolérance → la décision est écartée, pas
   rattachée au premier venu.
3. **Le point d'insertion du bloc de variante.** Inséré après le schéma JSON, il se
   lit comme une consigne de format : ce n'est pas la même mesure, et l'absence du
   point d'ancrage doit lever, pas concaténer en silence.
4. **La substitution ne touche que le sous-jeu.** Une ligne non rejouée qui bougerait
   ferait porter à la variante un écart qu'elle n'a pas produit.

Hors ligne : aucun appel LLM, aucune clé d'API. Les journaux sont fabriqués à la main.
"""

from __future__ import annotations

import json

import pytest

from scripts.synthesis import frames
from scripts.synthesis.alt_prompt_replay import (
    row_key,
    select_subset,
    substitute,
    subset_mass,
)
from scripts.synthesis.alt_prompt_variants import (
    INSERT_BEFORE,
    VARIANTS,
    VARIANTS_BY_ID,
    directive,
    system_prompt,
)
from scripts.synthesis.sources import import_calibration

CALIBRATION, _ENGINE_ERROR = import_calibration()
needs_engine = pytest.mark.skipif(
    CALIBRATION is None, reason=f"Moteur de calibration indisponible : {_ENGINE_ERROR}")

MOVES_HEADER = [
    "Référence", "Trajet", "ID Trajet", "Mode de transport Choisi", "Plus rapide",
    "Modes proposés au LLM", "P(Marche) %", "P(Vélo) %", "P(Voiture Privée) %",
    "P(Transports_collectifs) %", "P(Train) %", "P(Deux-roues motorisé) %",
    "P(Autres modes) %", "Lieu de résidence", "Genre", "Âge", "Occupation principale",
    "Type de logement", "Motifs de déplacement", "Distance parcourue",
    "Méthode de sélection", "Contrainte de chaîne", "Anticipation",
    "Fournisseur & Modèle", "Température", "Mémoire à court terme",
    "Mémoire à long terme", "Filtre de perception", "Traits de personnalité",
    "Météo Température (°C)", "Météo Condition", "Météo Précipitations (mm)",
    "Raisonnement", "Retard planification (s)", "Heure de calcul", "Temps simulé",
    "Heure de départ", "ID Personne", "ID Activité",
]

# 2026-03-16 08:00:00 UTC et 2026-03-17 08:00:00 UTC.
DAY1_TS = "1773648000"
DAY2_TS = "1773734400"


def move_row(*, agent="42", activity="act-1", ts=DAY1_TS, computed,
             chosen="Transports_collectifs", offered="Transports_collectifs | Marche",
             p_marche="10", p_tc="90"):
    row = {col: "" for col in MOVES_HEADER}
    row.update({
        "Référence": "test", "ID Personne": agent, "ID Activité": activity,
        "Mode de transport Choisi": chosen, "Modes proposés au LLM": offered,
        "P(Marche) %": p_marche, "P(Vélo) %": "0", "P(Voiture Privée) %": "0",
        "P(Transports_collectifs) %": p_tc, "P(Train) %": "0",
        "P(Deux-roues motorisé) %": "0", "P(Autres modes) %": "0",
        "Genre": "Homme", "Âge": "40", "Occupation principale": "Travail à temps plein",
        "Motifs de déplacement": "travail", "Distance parcourue": "1500",
        "Méthode de sélection": "LLM", "Heure de calcul": computed,
        "Temps simulé": ts, "Heure de départ": "2026-03-16 07:00:00",
    })
    return row


def write_moves(path, rows):
    import csv
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=MOVES_HEADER)
        writer.writeheader()
        writer.writerows(rows)


def section(agent="42", departure="08:00"):
    return (
        f"--- agent_id={agent} | Destination : work | Départ : {departure} ---\n"
        "**Contexte :** Météo : 12°C, Ciel dégagé/Ensoleillé.\n"
        "Camille, 40 ans, Travail à temps plein (seul(e), revenu moyen)\n"
        "Mobilité : abonné·e TC Contraintes : None\n\n"
        "**Options de trajet** (2 options, indices 0 à 1) :\n"
        "- [0] foot,bus,foot: Temps de trajet : 12 minutes.\n"
        "- [1] foot: Durée estimée : 22 minutes. Distance : 1.6 km.\n")


def write_run(tmp_path, *, moves_rows, exchanges, agents=("42",)):
    """Un répertoire de run minimal : moves.csv, llm_exchanges.jsonl, population."""
    run = tmp_path / "run"
    run.mkdir()
    write_moves(run / "moves.csv", moves_rows)
    (run / "llm_exchanges.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in exchanges),
        encoding="utf-8")
    (run / "population_10.json").write_text(json.dumps([
        {"person_id": int(a),
         "identity": {"traits_json": {"gender": "Male", "age": 40,
                                      "main_occupation": "Travail à plein temps",
                                      "household_size": 1}}}
        for a in agents]), encoding="utf-8")
    return run


def exchange(sections, *, time, sim_day="2026-03-16", task="batch_1"):
    return {
        "time": time, "sim_day": sim_day, "task_id": task,
        "category": "itinary_multi_agent",
        "messages": [{"role": "system", "content": "PROMPT" + INSERT_BEFORE + "\nfin"},
                     {"role": "user", "content": "\n\n".join(sections)}],
        "response": [],
    }


# ── 1. La coupe au premier jour simulé, côté lignes brutes ───────────────────

@needs_engine
def test_la_repetition_du_lendemain_ne_vole_pas_l_heure_de_calcul(tmp_path):
    """La même décision rejouée le jour 2 ne doit pas masquer le lot du jour 1.

    `latest_attempts` ne les sépare pas — sa clé porte le jour simulé, ce qui est
    justement ce qui distingue une reprise à chaud d'une répétition d'agenda.
    Indexer les lignes brutes sans couper au premier jour garde celle du jour 2,
    dont l'« Heure de calcul » appartient à un autre lot : la décision devient
    « sans lot retrouvé » alors que son lot est là, et le sous-jeu se vide sans
    qu'aucune exception ne le signale.
    """
    run = write_run(
        tmp_path,
        moves_rows=[
            move_row(ts=DAY1_TS, computed="2026-08-24T20:00:00+00:00"),
            move_row(ts=DAY2_TS, computed="2026-08-24T23:59:00+00:00"),
        ],
        exchanges=[exchange([section()], time="2026-08-24T20:00:02+00:00")])

    _rows, pairs, stats = select_subset(run, [])

    assert stats["sous_jeu_brut"] == 1, "la coupe au premier jour doit précéder"
    assert stats["apparie"] == 1
    assert stats["non_apparie_absent"] == 0
    assert pairs[0]["key"] == row_key("42", "act-1")


# ── 2. L'ambiguïté se déclare ────────────────────────────────────────────────

@needs_engine
def test_deux_lots_candidats_ecartent_la_decision_au_lieu_d_en_choisir_un(tmp_path):
    """Deux blocs du même agent dans la fenêtre : on écarte, on ne devine pas.

    Rattacher au premier venu rejouerait le prompt d'un AUTRE trajet sous
    l'étiquette de celui-ci — même agent, même jeu d'options, décision différente.
    Le résultat resterait parfaitement lisible.
    """
    run = write_run(
        tmp_path,
        moves_rows=[move_row(computed="2026-08-24T20:00:00+00:00")],
        exchanges=[
            exchange([section(departure="08:00")], time="2026-08-24T20:00:01+00:00",
                     task="batch_1"),
            exchange([section(departure="17:30")], time="2026-08-24T20:00:03+00:00",
                     task="batch_2"),
        ])

    _rows, pairs, stats = select_subset(run, [])

    assert pairs == []
    assert stats["non_apparie_ambigu"] == 1


@needs_engine
def test_le_jeu_d_options_valide_l_appariement(tmp_path):
    """Un lot proche dans le temps mais portant d'autres options n'est pas le bon.

    La tolérance de 5 secondes ne suffit pas à identifier une décision : sans le
    contrôle sur le jeu d'options, un agent ayant deux trajets calculés dans le
    même lot verrait ses deux décisions confondues.
    """
    other = section().replace(
        "- [1] foot: Durée estimée : 22 minutes. Distance : 1.6 km.",
        "- [1] car: Durée estimée : 4 minutes. Distance : 1.6 km.")
    run = write_run(
        tmp_path,
        moves_rows=[move_row(computed="2026-08-24T20:00:00+00:00")],
        exchanges=[exchange([other], time="2026-08-24T20:00:01+00:00")])

    _rows, pairs, stats = select_subset(run, [])

    assert pairs == []
    assert stats["non_apparie_absent"] == 1


@needs_engine
def test_une_decision_tc_sans_marche_proposee_sort_du_sous_jeu(tmp_path):
    """Le sous-jeu porte sur un ARBITRAGE : sans marche proposée, il n'y en a pas."""
    run = write_run(
        tmp_path,
        moves_rows=[move_row(computed="2026-08-24T20:00:00+00:00",
                             offered="Transports_collectifs | Voiture Privée")],
        exchanges=[exchange([section()], time="2026-08-24T20:00:01+00:00")])

    _rows, pairs, stats = select_subset(run, [])

    assert pairs == []
    assert stats["tc_sans_marche_proposee"] == 1
    assert stats["sous_jeu_brut"] == 0


@needs_engine
def test_deux_decisions_sur_un_meme_bloc_persona_sont_refusees(tmp_path):
    """Un bloc pour deux décisions perdrait l'une des deux, sans un mot.

    La jointure décision → ligne passe par l'identité du record : deux clés
    pointant sur le même objet n'en laissent qu'une, et le sous-jeu rejoué se
    retrouve amputé — avec des parts modales parfaitement présentables.
    """
    run = write_run(
        tmp_path,
        moves_rows=[
            move_row(activity="act-1", computed="2026-08-24T20:00:00+00:00"),
            move_row(activity="act-2", computed="2026-08-24T20:00:02+00:00"),
        ],
        exchanges=[exchange([section()], time="2026-08-24T20:00:01+00:00")])

    with pytest.raises(SystemExit, match="ALARME"):
        select_subset(run, [])


# ── 3. Le point d'insertion du bloc de variante ──────────────────────────────

def test_le_bloc_s_insere_avant_les_instructions_de_sortie():
    """Placé après le schéma JSON, l'ajout se lit comme une consigne de format."""
    base = f"critères{INSERT_BEFORE}\n1) …\nSchéma JSON attendu :\n{{}}"
    out = system_prompt(base, VARIANTS_BY_ID[1])

    assert directive(VARIANTS_BY_ID[1]) in out
    assert out.index(directive(VARIANTS_BY_ID[1])) < out.index("[Instructions de sortie]")
    # Rien n'est retiré : le prompt d'origine est contenu mot pour mot.
    for fragment in ("critères", "Schéma JSON attendu :"):
        assert fragment in out


def test_un_prompt_sans_point_d_ancrage_est_refuse():
    """Concaténer en fin de prompt mesurerait autre chose, en silence."""
    with pytest.raises(ValueError, match="ALARME"):
        system_prompt("un prompt sans le marqueur attendu", VARIANTS_BY_ID[1])


def test_les_dix_variantes_sont_distinctes_et_numerotees():
    assert [v["id"] for v in VARIANTS] == list(range(1, 11))
    assert len({v["slug"] for v in VARIANTS}) == 10
    assert len({v["body"] for v in VARIANTS}) == 10
    for variant in VARIANTS:
        assert variant["body"].strip()
        # Aucune variante ne dicte le résultat : elle fournit un élément de calcul.
        assert "choisis la marche" not in variant["body"].lower()


# ── 4. La substitution ne touche que le sous-jeu ─────────────────────────────

def make_row(agent, activity, probas, chosen="transports_collectifs"):
    return {"agent_id": agent, "activity_id": activity, "probas": dict(probas),
            "chosen": chosen, "offered": ["marche", "transports_collectifs"],
            "genre": "Homme", "age_cat": "35-39", "occupation": "actif_temps_plein",
            "motif": "travail", "dist_cat": "1-2km", "lieu_residence": "Toulouse",
            "type_logement": None, "departure_hour": 8, "contrainte": None}


def test_les_lignes_hors_sous_jeu_sont_rendues_a_l_identique():
    rows = [make_row("1", "a", {"marche": 10.0, "transports_collectifs": 90.0}),
            make_row("2", "b", {"voiture": 100.0}, chosen="voiture")]
    out, stats = substitute(rows, {row_key("1", "a"): {"marche": 0.8,
                                                      "transports_collectifs": 0.2}}, 1)

    assert stats["remplacees"] == 1 and stats["inchangees"] == 1
    assert out[1] is rows[1], "une ligne non rejouée ne doit même pas être recopiée"
    assert out[0]["probas"] == pytest.approx({"marche": 80.0,
                                              "transports_collectifs": 20.0})
    assert sum(out[0]["probas"].values()) == pytest.approx(100.0)


def test_une_masse_rejouee_nulle_conserve_la_decision_du_run():
    """Un bras qui ne rend rien pour une décision ne doit pas l'effacer.

    Remettre la masse à zéro retirerait la ligne du scoring, ce qui déplacerait les
    parts modales *sans* qu'aucune décision ait changé d'avis.
    """
    rows = [make_row("1", "a", {"marche": 10.0, "transports_collectifs": 90.0})]
    out, stats = substitute(rows, {row_key("1", "a"): {}}, 1)

    assert stats["masse_nulle"] == 1
    assert out[0]["probas"] == rows[0]["probas"]


def test_le_retirage_est_reproductible_et_depend_de_la_variante():
    """Graine dérivée de (variante, ligne) : rejouable, et distincte d'un bras à l'autre."""
    rows = [make_row(str(i), "a", {"marche": 50.0, "transports_collectifs": 50.0})
            for i in range(40)]
    decisions = {row_key(str(i), "a"): {"marche": 0.5, "transports_collectifs": 0.5}
                 for i in range(40)}

    first, _ = substitute(rows, decisions, 1)
    again, _ = substitute(rows, decisions, 1)
    other, _ = substitute(rows, decisions, 2)

    assert [r["chosen"] for r in first] == [r["chosen"] for r in again]
    assert [r["chosen"] for r in first] != [r["chosen"] for r in other]


def test_subset_mass_ne_compte_que_les_lignes_du_sous_jeu():
    rows = [make_row("1", "a", {"marche": 20.0, "transports_collectifs": 80.0}),
            make_row("2", "b", {"marche": 100.0})]
    mass = subset_mass(rows, {row_key("1", "a")})

    assert mass["n"] == 1
    assert mass["marche"] == pytest.approx(20.0)
    assert mass["transports_collectifs"] == pytest.approx(80.0)
    # Les modes absents de la décision valent 0, pas None : ils entrent dans les Δ.
    assert mass["voiture"] == 0.0
    assert set(frames.MODES) <= set(mass)
