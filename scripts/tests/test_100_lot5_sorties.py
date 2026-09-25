"""Ticket 100, lot 5 — la figure unique et le tableau des quatre voies.

Contrat de référence : `specs/ticket_100/tests.md`, règles R43 à R50.

Les deux scripts sont écrits AVANT le premier run, sur des données de forme : une figure dont
le script n'existe qu'après la mesure se taille sur ce qu'elle a trouvé.
"""

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.analysis import figure_evenement as fig
from scripts.analysis import tableau_quatre_voies as quatre


TEXTE = "The engine made a grinding noise and the car stalled on the expressway."


def _moves(dossier: Path, lignes: list[dict], avec_role: bool = True) -> Path:
    entetes = ["Référence", "ID Personne", "Heure de départ", "P(Voiture Privée) %", "Choc",
               "Jour relatif au choc"] + (["Rôle"] if avec_role else [])
    chemin = dossier / "moves.csv"
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=entetes, extrasaction="ignore")
        w.writeheader()
        w.writerows(lignes)
    return chemin


def _jeu_de_forme(dossier: Path, effectif: int = 6) -> Path:
    lignes = []
    for relatif in range(-3, 8):
        for role, base, creux in (("expose", 60, 25), ("co_resident", 60, 6), ("temoin", 60, 0)):
            for i in range(effectif):
                lignes.append({
                    "Référence": f"{role}_{i}", "Heure de départ": "2026-03-16 08:00",
                    "P(Voiture Privée) %": base - (creux if 0 <= relatif <= 5 else 0),
                    "Choc": "c6_voiture_suspecte", "Jour relatif au choc": relatif,
                    "Rôle": role,
                })
    return _moves(dossier, lignes)


# ── R47, R49. La garde de vacuité ────────────────────────────────────────────────────────
def test_R49_sous_leffectif_minimal_la_figure_sort_non_concluant(tmp_path):
    """Une courbe tracée sur deux décisions ressemble à une courbe tracée sur deux cents."""
    _jeu_de_forme(tmp_path, effectif=fig.EFFECTIF_MINIMAL - 1)
    moyennes, _effectifs, _ev = fig.series(tmp_path, "car")
    assert all(not points for points in moyennes.values())
    with pytest.raises(SystemExit, match="non concluant"):
        fig.composer(moyennes, {}, "car", "c6")


def test_R47_un_role_absent_est_ECRIT_sur_la_figure(tmp_path):
    """Une série manquante se lit comme un effet nul par qui ne sait pas qu'elle manque."""
    lignes = []
    for relatif in range(-2, 5):
        for i in range(5):
            lignes.append({
                "Référence": f"e{i}", "Heure de départ": "2026-03-16 08:00",
                "P(Voiture Privée) %": 55, "Choc": "c6", "Jour relatif au choc": relatif,
                "Rôle": "expose",
            })
    _moves(tmp_path, lignes)
    moyennes, effectifs, ev = fig.series(tmp_path, "car")
    svg = fig.composer(moyennes, effectifs, "car", ev)
    assert "not conclusive for" in svg
    assert "Co-resident" in svg and "Control" in svg


def test_une_cellule_vide_nest_pas_un_zero(tmp_path):
    """Une décision sans répartition n'est pas une décision à 0 % de voiture."""
    lignes = [
        {"Référence": "a", "Heure de départ": "2026-03-16 08:00", "P(Voiture Privée) %": "",
         "Choc": "c6", "Jour relatif au choc": 0, "Rôle": "expose"},
    ] + [
        {"Référence": f"b{i}", "Heure de départ": "2026-03-16 08:00",
         "P(Voiture Privée) %": 50, "Choc": "c6", "Jour relatif au choc": 0, "Rôle": "expose"}
        for i in range(3)
    ]
    _moves(tmp_path, lignes)
    moyennes, effectifs, _ = fig.series(tmp_path, "car")
    assert effectifs["expose"][0] == 3, "la ligne vide ne compte pas dans l'effectif"
    assert moyennes["expose"][0] == 50.0, "elle ne tire pas la moyenne vers le bas non plus"


# ── R50. L'abscisse existe tous les jours ────────────────────────────────────────────────
def test_R50_le_jour_relatif_couvre_avant_et_apres(tmp_path):
    _jeu_de_forme(tmp_path)
    moyennes, _e, _ev = fig.series(tmp_path, "car")
    jours = sorted(moyennes["temoin"])
    assert min(jours) < 0 < max(jours), (
        "une abscisse qui n'existerait que les jours d'événement ne tracerait rien"
    )


def test_la_figure_se_compose_et_nomme_le_resultat(tmp_path):
    _jeu_de_forme(tmp_path)
    moyennes, effectifs, ev = fig.series(tmp_path, "car")
    svg = fig.composer(moyennes, effectifs, "car", ev)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert "Who changes, and for how long" in svg
    for _role, nom, _couleur in fig.ROLES:
        assert nom in svg
    # Figure en ANGLAIS, légende comprise : toutes celles de l'article le sont.
    for mot_francais in ("exposé", "témoin", "jour relatif"):
        assert mot_francais not in svg


def test_un_run_sans_colonne_role_le_dit_au_lieu_de_deviner(tmp_path):
    _moves(tmp_path, [{"Référence": "a", "Heure de départ": "2026-03-16 08:00",
                       "P(Voiture Privée) %": 50, "Choc": "c6",
                       "Jour relatif au choc": 0}], avec_role=False)
    with pytest.raises(SystemExit, match="Rôle"):
        fig.series(tmp_path, "car")


def test_un_mode_inconnu_est_refuse_et_non_devine():
    assert "teleportation" not in fig.COLONNE_PROBA
    assert set(fig.COLONNE_PROBA) == set(fig.LIBELLE_EN)


# ── Le tableau des quatre voies ──────────────────────────────────────────────────────────
def test_les_en_tetes_de_bloc_sont_ceux_de_noyau_py():
    """Un en-tête renommé ferait sortir une voie à zéro sans qu'aucune erreur n'apparaisse."""
    noyau = (RACINE / "services" / "llm-agents" / "llm" / "noyau.py").read_text("utf-8")
    for en_tete in quatre.EN_TETES.values():
        assert f'"{en_tete}"' in noyau, f"« {en_tete} » n'est plus posé par noyau.py"


def test_les_quatre_voies_sont_celles_du_manuscrit():
    assert quatre.VOIES == ("habitudes", "connaissances", "changements", "rappel")


def test_les_mots_saillants_ecartent_le_banal_et_gardent_le_rare():
    saillants = quatre.mots_saillants(TEXTE)
    assert "grinding" in saillants and "expressway" in saillants
    assert "the" not in saillants and "and" not in saillants


def test_un_run_sans_evenement_le_dit_au_lieu_de_rendre_un_tableau_vide(tmp_path):
    with pytest.raises(SystemExit, match="run sans événement"):
        quatre.depouiller(tmp_path)


def _run_complet(dossier: Path) -> Path:
    (dossier / "evenements.jsonl").write_text(json.dumps({
        "person_id": "899549", "canal": "vecu", "texte": TEXTE, "evenement_id": "c6",
    }) + "\n", encoding="utf-8")
    # Comme le journal réel : `Référence` porte le nom du run, l'agent est dans `ID Personne`.
    _moves(dossier, [{"Référence": "2026-09-24_17_50", "ID Personne": "899549",
                      "Heure de départ": "2026-03-16 08:00",
                      "P(Voiture Privée) %": 30, "Choc": "c6",
                      "Jour relatif au choc": 1, "Rôle": "expose"}])
    return dossier


def test_une_decision_sans_aucune_voie_est_NOMMEE_et_non_lue_comme_un_zero(tmp_path):
    """« On ne sait pas le dire » n'est pas « l'événement n'a pesé sur rien »."""
    _run_complet(tmp_path)
    (tmp_path / "llm_exchanges.jsonl").write_text(json.dumps({
        "category": "itinary_multi_agent",
        "messages": "--- agent_id=899549 ---\nMes habitudes\n- rien de notable",
    }) + "\n", encoding="utf-8")
    resultat = quatre.depouiller(tmp_path)
    assert resultat["decisions"][("vecu", "expose")] == 1
    assert not any(resultat["compte"].get(("vecu", "expose", v)) for v in quatre.VOIES)
    rendu = quatre.rendre(resultat)
    assert "AUCUNE voie" in rendu
    assert "n'a pesé sur rien" in rendu, "le rendu doit DIRE ce qu'il ne sait pas dire"
    assert "absence de mesure" in rendu


def test_un_run_dont_aucune_decision_ne_voit_lagent_sort_NON_CONCLUANT(tmp_path):
    _run_complet(tmp_path)
    (tmp_path / "llm_exchanges.jsonl").write_text(json.dumps({
        "category": "itinary_multi_agent", "messages": "--- agent_id=999 ---\nMes habitudes",
    }) + "\n", encoding="utf-8")
    assert "non concluant" in quatre.rendre(quatre.depouiller(tmp_path))


def test_le_texte_retrouve_dans_un_bloc_est_impute_a_CE_bloc(tmp_path):
    _run_complet(tmp_path)
    prompt = (
        "--- agent_id=899549 ---\n"
        "Mes habitudes\n- souvent la voiture\n"
        f"Ce qui a changé récemment\n- {TEXTE}\n"
    )
    (tmp_path / "llm_exchanges.jsonl").write_text(json.dumps({
        "category": "itinary_multi_agent", "messages": prompt,
    }) + "\n", encoding="utf-8")
    resultat = quatre.depouiller(tmp_path)
    assert resultat["compte"][("vecu", "expose", "changements")]["exact"] == 1
    assert not resultat["compte"].get(("vecu", "expose", "habitudes"))


def test_lappariement_par_mots_saillants_est_marque_comme_indicatif(tmp_path):
    """La réflexion REFORMULE le vécu : l'appariement exact échoue, et il faut le dire."""
    _run_complet(tmp_path)
    reformule = "my car started making a terrible grinding noise on the expressway"
    (tmp_path / "llm_exchanges.jsonl").write_text(json.dumps({
        "category": "itinary_multi_agent",
        "messages": f"--- agent_id=899549 ---\nCe que je sais\n- {reformule}\n",
    }) + "\n", encoding="utf-8")
    resultat = quatre.depouiller(tmp_path)
    assert resultat["compte"][("vecu", "expose", "connaissances")]["saillant"] == 1
    assert "~" in quatre.rendre(resultat)


def test_une_reflexion_nocturne_nest_pas_une_decision(tmp_path):
    _run_complet(tmp_path)
    (tmp_path / "llm_exchanges.jsonl").write_text(json.dumps({
        "category": "stm_reflection",
        "messages": f"--- agent_id=899549 ---\nCe que je sais\n- {TEXTE}",
    }) + "\n", encoding="utf-8")
    assert not quatre.depouiller(tmp_path)["decisions"]


def test_le_role_se_lit_dans_ID_Personne_et_non_dans_Reference(tmp_path):
    """`Référence` porte le nom du run (`experiences/journal.py`). Lue comme identifiant
    d'agent, elle faisait sortir le rôle `?` sur toutes les lignes du run 2026-09-24_17_50."""
    _moves(tmp_path, [
        {"Référence": "2026-09-24_17_50", "ID Personne": "286920", "Rôle": "expose"},
        {"Référence": "2026-09-24_17_50", "ID Personne": "286921", "Rôle": "co_resident"},
    ])
    assert quatre.roles_du_run(tmp_path) == {"286920": "expose", "286921": "co_resident"}


# ── Les échanges tels que la passerelle les écrit ────────────────────────────────────────
def _echanges_passerelle(dossier: Path, objets: list[dict], separateur: str = "\n") -> None:
    """Un objet JSON INDENTÉ par échange, comme `llm_gateway/telemetry/exchanges.py` : ce
    n'est pas du JSONL malgré l'extension."""
    (dossier / "llm_exchanges.jsonl").write_text(
        "".join(json.dumps(o, ensure_ascii=False, indent=2) + separateur for o in objets),
        encoding="utf-8",
    )


def _echanges_de_forme(origine: str) -> list[dict]:
    """`origine` est le nom du run qui a signé l'échange : `lire_echanges` écarte les autres."""
    return [
        {"origine": origine, "category": "itinary_multi_agent", "task_id": "t1",
         "messages": [
             {"role": "system", "content": "Select the optimal travel mode."},
             {"role": "user", "content": "--- agent_id=899549 ---\nMes habitudes\n- la voiture\n"
                                         f"Ce qui a changé récemment\n- {TEXTE}\n"},
         ],
         # Une liste de chaînes : indentée, chacune tient seule sur sa ligne et se décode,
         # lue ligne à ligne, en chaîne nue — c'est elle qui faisait tomber `.get()`.
         "response": {"modes_touches": ["walking", "car"]}},
        {"origine": origine, "category": "stm_reflection", "task_id": "t2",
         "messages": [{"role": "user", "content": f"--- agent_id=899549 ---\n{TEXTE}"}],
         "response": ["walking"]},
    ]


@pytest.mark.parametrize("separateur", ["\n\n", "\n"], ids=["ligne_vide", "saut_de_ligne"])
def test_les_echanges_indentes_de_la_passerelle_se_lisent(tmp_path, separateur):
    """La docstring de la passerelle annonce une ligne vide entre objets ; le run
    2026-09-24_17_50 n'en porte aucune. Les deux se lisent."""
    _run_complet(tmp_path)
    _echanges_passerelle(tmp_path, _echanges_de_forme(tmp_path.name), separateur)
    resultat = quatre.depouiller(tmp_path)
    assert resultat["echanges"] == 2
    assert resultat["decisions"][("vecu", "expose")] == 1
    assert resultat["compte"][("vecu", "expose", "changements")]["exact"] == 1
    assert not resultat["compte"].get(("vecu", "expose", "habitudes"))
    assert "Lu : 2 échanges, dont 1 décision" in quatre.rendre(resultat)


def test_un_echange_signe_par_un_autre_run_nest_pas_compte(tmp_path):
    """Le worker écrit ce journal pour TOUS ses clients : une décision signée par un autre run
    ne dit rien de celui-ci, même si elle porte le même `agent_id`."""
    _run_complet(tmp_path)
    _echanges_passerelle(tmp_path, _echanges_de_forme("un_autre_run")
                         + _echanges_de_forme(tmp_path.name)[:1])
    resultat = quatre.depouiller(tmp_path)
    assert resultat["echanges"] == 1
    assert resultat["decisions"][("vecu", "expose")] == 1


@pytest.mark.parametrize("contenu", [None, ""], ids=["absent", "vide"])
def test_un_run_sans_echanges_le_dit_au_lieu_de_conclure_a_labsence_de_decision(tmp_path, contenu):
    """Sans échange lu, « aucune décision ne porte le texte » serait faux : aucune décision
    n'a été lue du tout. Le tableau sort quand même (A9.3 du banc), il ne lève pas."""
    _run_complet(tmp_path)
    if contenu is not None:
        (tmp_path / "llm_exchanges.jsonl").write_text(contenu, encoding="utf-8")
    rendu = quatre.rendre(quatre.depouiller(tmp_path))
    assert "non concluant" in rendu and "n'a pesé sur rien" in rendu
    assert "aucun échange lu dans `llm_exchanges.jsonl`" in rendu
    assert "aucune décision ne porte le texte" not in rendu


def test_le_tableau_se_lance_en_ligne_de_commande_sur_des_echanges_indentes(tmp_path):
    """Lancé par son chemin, hors de la racine : l'import de `memoire.sources` doit tenir."""
    _run_complet(tmp_path)
    _echanges_passerelle(tmp_path, _echanges_de_forme(tmp_path.name))
    r = subprocess.run(
        [sys.executable, str(RACINE / "scripts" / "analysis" / "tableau_quatre_voies.py"),
         str(tmp_path), "--markdown"],
        capture_output=True, text=True, cwd=tmp_path, check=False,
    )
    assert r.returncode == 0, r.stderr
    assert "expose" in r.stdout and "Lu : 2 échanges" in r.stdout


def test_les_deux_scripts_se_lancent_en_ligne_de_commande(tmp_path):
    _jeu_de_forme(tmp_path)
    sortie = tmp_path / "f.svg"
    r = subprocess.run(
        [sys.executable, str(RACINE / "scripts" / "analysis" / "figure_evenement.py"),
         str(tmp_path), "--mode", "car", "-o", str(sortie)],
        capture_output=True, text=True, cwd=RACINE,
    )
    assert r.returncode == 0, r.stderr
    assert sortie.is_file() and sortie.read_text("utf-8").startswith("<svg")
