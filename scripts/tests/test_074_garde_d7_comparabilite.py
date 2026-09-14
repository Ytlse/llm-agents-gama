"""Ticket 074, D-7 — la garde de comparabilité, figée.

LA QUESTION. Les quatorze témoins déterministes ne lisent aucun prompt : la traduction ne peut
pas changer leurs sorties. Mais ils dépendent du SUBSTRAT — mêmes personnes, mêmes chaînes
d'activités. Si la régénération en v6 avait bougé ces chaînes, leurs résultats ne se
compareraient plus à ceux des bras LLM, et personne ne l'aurait vu : rien ne plante quand on
compare deux mesures faites sur deux mondes différents.

LA RÉPONSE, MESURÉE le 2026-09-14 contre l'archive froide : la v6 porte les mêmes 1 000
`person_id`, les mêmes 499 ménages, et **0 chaîne d'activité différente sur 1 000** — motifs,
horaires et lieux compris. La garde a donc statué « comparables en l'état ».

CE QUE CE FICHIER FAIT. Il fige cette mesure. Le jour où une v7 arrivera, ce test tombera, et
la question se reposera au lieu d'être héritée. C'est tout le point : une garde qui a statué
une fois et qu'on oublie n'est plus une garde, c'est une habitude.

L'ARCHIVE EST LUE, PAS UTILISÉE. C'est la seule chose que la doctrine du froid autorise —
« restauré ou audité », et un test de comparabilité est exactement un audit. Le test saute en
le disant si l'archive n'est pas là (poste neuf, clone partiel).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
V6 = REPO_ROOT / "data" / "population" / "population_1000_AAMAS_v6"
V5 = (REPO_ROOT / "archive" / "2026-09-14_avant_bascule_anglaise" / "population"
      / "population_1000_AAMAS_v5")

#: Ce que la mesure du 2026-09-14 a établi. Des littéraux, volontairement : un test qui
#: recalculerait ses attendus depuis les fichiers qu'il contrôle ne contrôle rien.
PERSONNES = 1000
MENAGES = 499
DEPLACEMENTS = 3299
SCEAU_V6 = "412efada802f79e8a72976ba25e0c7db8c9404adaed7c1f5e3e3d6afa3531db6"

#: Les six champs que la bascule change, et eux seuls. Tout le reste doit être identique.
CHAMPS_TRADUITS = {
    "main_occupation", "housing_type", "personal_bike", "residence_zone",
    "travel_purposes", "name",
}


def _charger(chemin: Path) -> list[dict]:
    doc = json.loads(chemin.read_text(encoding="utf-8"))
    return doc["people"] if isinstance(doc, dict) else doc


def _pid(p: dict) -> str:
    return str((p.get("identity") or {}).get("person_id") or p.get("person_id"))


def _chaine(p: dict) -> list[tuple]:
    activites = (p.get("identity") or {}).get("activities") or p.get("activities") or []
    return [
        (a.get("purpose"), a.get("start_time"), a.get("end_time"),
         round((a.get("location") or {}).get("lat", 0), 6),
         round((a.get("location") or {}).get("lon", 0), 6))
        for a in activites
    ]


@pytest.fixture(scope="module")
def v6():
    if not (V6 / "population.json").is_file():
        pytest.skip(f"cohorte v6 absente ({V6}) — rien à contrôler")
    return _charger(V6 / "population.json")


@pytest.fixture(scope="module")
def v5():
    if not (V5 / "population.json").is_file():
        pytest.skip(
            f"archive froide absente ({V5}) : la comparaison v5/v6 est un AUDIT, elle a "
            "besoin de l'archive. Sur un clone partiel, ce contrôle ne peut pas être rendu.")
    return _charger(V5 / "population.json")


# ── Le sceau ─────────────────────────────────────────────────────────────────


def test_le_sceau_v6_est_celui_qui_a_ete_mesure():
    manifeste = yaml.safe_load((V6 / "MANIFEST.yaml").read_text(encoding="utf-8")) \
        if (V6 / "MANIFEST.yaml").is_file() else None
    if manifeste is None:
        pytest.skip("cohorte v6 absente")
    trouve = json.dumps(manifeste)
    assert SCEAU_V6 in trouve, (
        "le MANIFEST de la v6 ne porte plus l'empreinte mesurée le 2026-09-14 : la cohorte a "
        "changé, et la garde D-7 doit être REJOUÉE avant de comparer quoi que ce soit.")


def test_la_v6_porte_les_effectifs_annonces(v6):
    assert len(v6) == PERSONNES
    menages = {str(((p.get("identity") or {}).get("traits_json") or {}).get("household_id")
                   or (p.get("identity") or {}).get("household_id") or "")
               for p in v6}
    menages.discard("")
    # Le `household_id` n'est pas toujours dans les traits : le compte de ménages fait foi
    # dans le manifeste, on ne le recalcule que s'il est là.
    if menages:
        assert len(menages) == MENAGES


def test_le_compte_de_deplacements_est_celui_de_experiments_yaml(v6):
    """3 299 : c'est le chiffre que `experiments.yaml` publie et que l'article cite."""
    total = sum(len((p.get("identity") or {}).get("activities") or [])
                for p in v6
                if len((p.get("identity") or {}).get("activities") or []) > 1)
    assert total == DEPLACEMENTS


# ── La garde elle-même ───────────────────────────────────────────────────────


def test_les_memes_personnes_qu_en_v5(v5, v6):
    i5, i6 = {_pid(p) for p in v5}, {_pid(p) for p in v6}
    assert i5 == i6, (
        f"{len(i5 ^ i6)} personne(s) diffèrent entre v5 et v6 : les témoins déterministes ne "
        "sont plus comparables et DOIVENT être rejoués (garde D-7).")


def test_aucune_chaine_d_activite_ne_differe(v5, v6):
    """LE test de la garde. Motifs, horaires ET lieux — pas seulement le nombre."""
    m5 = {_pid(p): _chaine(p) for p in v5}
    m6 = {_pid(p): _chaine(p) for p in v6}
    differents = [k for k in m5.keys() & m6.keys() if m5[k] != m6[k]]
    assert not differents, (
        f"{len(differents)} chaîne(s) d'activité diffèrent (ex. {differents[:3]}) : le "
        "substrat a bougé, les 14 témoins doivent être rejoués avant toute comparaison.")


def test_seuls_les_six_champs_traduits_different(v5, v6):
    """La contrepartie du test précédent : ce qui devait changer a bien changé, et rien d'autre.

    Sans lui, une v6 identique à la v5 au bit près passerait la garde — et la bascule
    anglaise n'aurait servi à rien sans que rien ne le dise.
    """
    t5 = {_pid(p): ((p.get("identity") or {}).get("traits_json") or {}) for p in v5}
    t6 = {_pid(p): ((p.get("identity") or {}).get("traits_json") or {}) for p in v6}
    qui_change: set[str] = set()
    for k in t5.keys() & t6.keys():
        for champ in set(t5[k]) | set(t6[k]):
            if t5[k].get(champ) != t6[k].get(champ):
                qui_change.add(champ)
    inattendus = qui_change - CHAMPS_TRADUITS
    assert not inattendus, f"champs modifiés hors traduction : {sorted(inattendus)}"
    assert qui_change, "aucun champ n'a changé : la v6 n'est pas traduite"


def test_aucune_valeur_francaise_ne_subsiste_dans_les_traits(v6):
    """Le critère d'acceptation du lot C, vérifié sur le fichier scellé et pas sur un échantillon."""
    import re

    francais = re.compile(
        r"couronne|vélo|Pas de vélo|Individuel|habitat collectif|Travail à|Scolaire|"
        r"Étudiant|Retraité|Chômeur|au foyer|périmètre|^Achats$|^Travail$|^Etude$")
    fautifs: list[tuple[str, str]] = []
    for p in v6:
        for champ, valeur in ((p.get("identity") or {}).get("traits_json") or {}).items():
            for v in (valeur if isinstance(valeur, list) else [valeur]):
                if isinstance(v, str) and francais.search(v):
                    fautifs.append((champ, v))
    assert not fautifs, f"valeurs françaises restantes : {sorted(set(fautifs))[:5]}"
