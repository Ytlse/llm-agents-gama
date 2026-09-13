"""Ticket 027, sonde — le substrat dérivé ne diffère que par le libellé du motif.

Spec : `specs/ticket_027/sonde-motif-escort.md`.

Ce que ces tests verrouillent, et pourquoi chacun existe :

S1/S9  un seul facteur change. Si la dérivation touchait autre chose que `purpose` — une
       coordonnée, une heure, l'ordre des propositions — l'écart mesuré entre les deux bras
       ne serait plus imputable au libellé, et la sonde ne prouverait rien.
S2/S3  les propositions se copient, jamais ne se recalculent. La copie n'est licite que tant
       que le motif n'entre dans aucun calcul d'itinéraire : le jour où ce ne sera plus vrai,
       `verifier_independance_du_motif` doit refuser de dériver plutôt que rendre une mesure
       silencieusement fausse.
S4     le tirage est reproductible. Un tirage qui change d'une machine à l'autre rend les
       deux bras incomparables sans que rien ne le signale.
S5     la population dérivée ne devient jamais le défaut du formulaire. C'est exactement la
       cause racine du ticket 045, et une sonde scellée la reproduirait à l'identique.
S8     l'identité est idempotente : relancer ne change pas les octets qui la portent.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "scripts"))

import deriver_sonde_escort as S  # noqa: E402


# ── un substrat minuscule, mais de la même forme que le vrai ──────────────────


def _personne(pid: str, motifs: list[str]) -> dict:
    return {
        "person_id": pid,
        "immobile": False,
        "identity": {
            "name": f"Persona {pid}",
            "traits_json": {"age": 40, "residence_commune": "Toulouse"},
            "home": {"lon": 1.44, "lat": 43.6},
            "activities": [
                {
                    "id": f"{pid}-a{i}",
                    "purpose": motif,
                    "start_time": 3600.0 * i,
                    "end_time": 3600.0 * (i + 1),
                    "location": {"lon": 1.44 + i / 100, "lat": 43.6 + i / 100},
                }
                for i, motif in enumerate(motifs)
            ],
        },
        "state": {"last_activity_index": 0},
    }


@pytest.fixture()
def substrat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Population + jeu clos cohérents, et les dossiers de sortie détournés vers tmp."""
    population = [
        _personne("1", ["home", "other", "work", "other"]),
        _personne("2", ["home", "other", "other", "other"]),
        _personne("3", ["home", "shop", "education"]),
    ]
    dossier_pop = tmp_path / "source" / "population_test_v5"
    dossier_pop.mkdir(parents=True)
    (dossier_pop / "population.json").write_text(
        json.dumps(population, ensure_ascii=False), encoding="utf-8"
    )

    lignes = []
    for personne in population:
        for activite in personne["identity"]["activities"][1:]:
            lignes.append(
                {
                    "person_id": personne["person_id"],
                    "activity_id": activite["id"],
                    "ordinal": 0,
                    "purpose": activite["purpose"],
                    "depart_ts": 1773737984,
                    "origine": {"lon": 1.44, "lat": 43.6},
                    "destination": activite["location"],
                    "propositions": [
                        {
                            "source": "enregistree",
                            "plan": {"id": f"p-{activite['id']}", "purpose": activite["purpose"]},
                        }
                    ],
                    "motif_absence": None,
                }
            )
    dossier_jeu = tmp_path / "source" / "jeu_test"
    dossier_jeu.mkdir(parents=True)
    chemin_props = dossier_jeu / "propositions.jsonl"
    chemin_props.write_text(
        "".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lignes), encoding="utf-8"
    )
    manifeste = {
        "version": "jeu1",
        "nom": "population_test_v5_20260316",
        "clos": True,
        "cree_le": "2026-09-11T13:05:59+00:00",
        "clos_le": "2026-09-11T14:14:00+00:00",
        "population": {"nom": "population_test_v5", "sha256": "abc", "scellee": True, "n": 3},
        "jour_simule": "2026-03-16",
        "heure_reference": "depart_programme",
        "dependances": {"commit": "deadbeef", "otp_graph_sha256": "cafe"},
        "propositions_sha256": hashlib.sha256(chemin_props.read_bytes()).hexdigest(),
    }
    (dossier_jeu / "MANIFEST.yaml").write_text(
        yaml.safe_dump(manifeste, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    monkeypatch.setattr(S, "POP", tmp_path / "out" / "population")
    monkeypatch.setattr(S, "JEUX", tmp_path / "out" / "jeux")
    monkeypatch.setattr(S, "RACINE", tmp_path)
    return {
        "pop": dossier_pop,
        "jeu": dossier_jeu,
        "out_pop": tmp_path / "out" / "population" / "population_test_v5_escort66",
        "out_jeu": tmp_path / "out" / "jeux" / "population_test_v5_escort66_20260316",
        "population": population,
    }


def _deriver(substrat: dict, *extra: str) -> int:
    return S.main(
        [
            "--population",
            str(substrat["pop"]),
            "--jeu",
            str(substrat["jeu"]),
            "--part",
            "0.5",
            *extra,
        ]
    )


# ── S4 — le tirage est reproductible, et il dépend de la graine ──────────────


def test_le_tirage_est_stable_a_graine_egale(substrat: dict) -> None:
    cles = S.activites_candidates(substrat["population"], "other")
    assert len(cles) == 5
    assert S.tirer(cles, 0.5, 27) == S.tirer(cles, 0.5, 27)


def test_le_tirage_change_avec_la_graine(substrat: dict) -> None:
    cles = S.activites_candidates(substrat["population"], "other")
    tirages = {frozenset(S.tirer(cles, 0.5, g)) for g in range(12)}
    assert len(tirages) > 1, "la graine ne gouverne pas le tirage"


def test_le_tirage_ignore_l_ordre_du_fichier(substrat: dict) -> None:
    """Deux populations aux mêmes activités rangées autrement tirent la même chose (S4)."""
    a = S.activites_candidates(substrat["population"], "other")
    b = S.activites_candidates(list(reversed(substrat["population"])), "other")
    assert S.tirer(a, 0.5, 27) == S.tirer(b, 0.5, 27)


# ── S1/S9 — un seul facteur change ───────────────────────────────────────────


def test_seul_le_motif_differe_dans_la_population(substrat: dict) -> None:
    assert _deriver(substrat) == 0
    source = json.loads((substrat["pop"] / "population.json").read_text(encoding="utf-8"))
    derivee = json.loads((substrat["out_pop"] / "population.json").read_text(encoding="utf-8"))
    ecarts = S.comparer_populations(source, derivee)
    assert ecarts, "aucune activité réétiquetée : la dérivation n'a rien fait"
    assert all(e.endswith("'other' → 'escort'") for e in ecarts), ecarts


def test_les_lignes_hors_tirage_sont_recopiees_a_l_octet(substrat: dict) -> None:
    assert _deriver(substrat) == 0
    avant = (substrat["jeu"] / "propositions.jsonl").read_text(encoding="utf-8").splitlines()
    apres = (substrat["out_jeu"] / "propositions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(avant) == len(apres)
    changees = [i for i, (x, y) in enumerate(zip(avant, apres)) if x != y]
    assert changees, "aucune ligne réécrite"
    for i in changees:
        objet_avant, objet_apres = json.loads(avant[i]), json.loads(apres[i])
        assert objet_avant["purpose"] == "other"
        assert objet_apres["purpose"] == "escort"
        objet_avant.pop("purpose"), objet_apres.pop("purpose")
        for p_avant, p_apres in zip(objet_avant["propositions"], objet_apres["propositions"]):
            assert p_apres["plan"]["purpose"] == "escort", "le plan garde un motif périmé (S9)"
            p_avant["plan"].pop("purpose"), p_apres["plan"].pop("purpose")
        assert objet_avant == objet_apres, "une ligne tirée diffère ailleurs que sur le motif"


def test_le_motif_est_reecrit_aux_memes_cles_des_deux_cotes(substrat: dict) -> None:
    """Population et jeu doivent désigner EXACTEMENT les mêmes déplacements (S9)."""
    assert _deriver(substrat) == 0
    derivee = json.loads((substrat["out_pop"] / "population.json").read_text(encoding="utf-8"))
    cles_pop = {
        (p["person_id"], a["id"])
        for p in derivee
        for a in p["identity"]["activities"]
        if a["purpose"] == "escort"
    }
    cles_jeu = set()
    for ligne in (substrat["out_jeu"] / "propositions.jsonl").read_text(encoding="utf-8").splitlines():
        objet = json.loads(ligne)
        if objet["purpose"] == "escort":
            cles_jeu.add((objet["person_id"], objet["activity_id"]))
    assert cles_jeu <= cles_pop, "le jeu réétiquette un déplacement que la population ignore"
    # L'inverse est permis : une activité tirée peut n'avoir aucune ligne de jeu (non couverte).


# ── S7 — le jeu dérivé est cohérent et traçable ──────────────────────────────


def test_le_manifeste_derive_est_coherent(substrat: dict) -> None:
    assert _deriver(substrat) == 0
    manifeste = yaml.safe_load((substrat["out_jeu"] / "MANIFEST.yaml").read_text(encoding="utf-8"))
    reel = hashlib.sha256((substrat["out_jeu"] / "propositions.jsonl").read_bytes()).hexdigest()
    assert manifeste["propositions_sha256"] == reel, "empreinte périmée : `Jeu.charger` refuserait (J12)"
    assert manifeste["clos"] is True
    assert manifeste["version"] == "jeu1"
    assert manifeste["dependances"] == {"commit": "deadbeef", "otp_graph_sha256": "cafe"}, (
        "les dépendances doivent être HÉRITÉES : ce sont elles qui ont produit ces propositions"
    )
    assert manifeste["derive_de"]["jeu"] == "population_test_v5_20260316"
    assert manifeste["derive_de"]["ticket"] == "027"
    population = json.loads((substrat["out_pop"] / "population.json").read_text(encoding="utf-8"))
    assert manifeste["population"]["scellee"] is False
    assert manifeste["population"]["n"] == len(population)
    assert (
        manifeste["population"]["sha256"]
        == hashlib.sha256((substrat["out_pop"] / "population.json").read_bytes()).hexdigest()
    ), "le jeu dérivé ne pointe pas la population dérivée : `verifier_population` le refuserait"


def test_la_provenance_est_ecrite_et_dit_ce_qui_n_est_pas_mesure(substrat: dict) -> None:
    assert _deriver(substrat) == 0
    provenance = yaml.safe_load((substrat["out_pop"] / "PROVENANCE.yaml").read_text(encoding="utf-8"))
    assert provenance["scellee"] is False
    assert provenance["derive_de"]["population"] == "population_test_v5"
    assert "justesse" in provenance["mesure"], "la provenance doit dire ce que la sonde NE mesure PAS"
    assert provenance["effectifs"]["reetiquetees_escort"] > 0


# ── S5 — la sonde ne devient jamais le défaut ────────────────────────────────


def test_la_population_derivee_n_est_pas_scellee(substrat: dict) -> None:
    """Sans `MANIFEST.yaml`, `populations()` ne la liste pas et `population_par_defaut()`
    ne peut pas la choisir — la cause racine du ticket 045 ne se reproduit pas."""
    assert _deriver(substrat) == 0
    assert not (substrat["out_pop"] / "MANIFEST.yaml").exists()
    assert (substrat["out_pop"] / "PROVENANCE.yaml").exists()


# ── S8 — l'identité est idempotente ──────────────────────────────────────────


def test_relancer_rend_les_memes_octets(substrat: dict) -> None:
    assert _deriver(substrat) == 0
    empreintes = {
        f: hashlib.sha256((substrat["out_pop"] / "population.json").read_bytes()).hexdigest()
        if f == "pop"
        else hashlib.sha256((substrat["out_jeu"] / "propositions.jsonl").read_bytes()).hexdigest()
        for f in ("pop", "jeu")
    }
    assert _deriver(substrat) == 0
    assert (
        hashlib.sha256((substrat["out_pop"] / "population.json").read_bytes()).hexdigest()
        == empreintes["pop"]
    )
    assert (
        hashlib.sha256((substrat["out_jeu"] / "propositions.jsonl").read_bytes()).hexdigest()
        == empreintes["jeu"]
    )


# ── refus ────────────────────────────────────────────────────────────────────


def test_refuse_un_jeu_non_clos(substrat: dict) -> None:
    chemin = substrat["jeu"] / "MANIFEST.yaml"
    manifeste = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    manifeste["clos"] = False
    chemin.write_text(yaml.safe_dump(manifeste, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert _deriver(substrat) == 2


def test_refuse_un_jeu_altere(substrat: dict) -> None:
    """J12 : dériver d'un jeu dont l'empreinte ne colle plus propagerait l'altération."""
    chemin = substrat["jeu"] / "propositions.jsonl"
    chemin.write_text(chemin.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert _deriver(substrat) == 2


def test_refuse_une_source_absente(substrat: dict) -> None:
    assert S.main(["--population", str(substrat["pop"] / "néant"), "--jeu", str(substrat["jeu"])]) == 2


# ── S3 — la copie reste justifiée ────────────────────────────────────────────


def test_le_motif_n_influence_aucune_proposition_dans_le_depot_reel() -> None:
    """Le jour où une proposition dépendra du motif, ce test tombe AVANT la mesure."""
    assert S.verifier_independance_du_motif() == []


def test_le_controle_de_population_est_exhaustif() -> None:
    """Un contrôle qui s'arrête aux vingt premiers écarts laisse passer le vingt-et-unième.

    C'est le défaut trouvé à la première dérivation réelle : 289 activités réétiquetées,
    21 écarts rapportés. Le critère d'acceptation demande « aucune AUTRE différence » — il
    n'est tenu que si la comparaison va jusqu'au bout.
    """
    a = [{"v": i} for i in range(100)]
    b = [{"v": i + 1} for i in range(100)]
    assert len(S.comparer_populations(a, b)) == 100
