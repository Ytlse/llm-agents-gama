"""Ticket 059 — la grille des vingt signes et le corpus de presse.

Contrat de référence : `specs/ticket_059/tests.md`, § 1. Les cas portent les numéros de règle
(G1…G5 pour la grille, C1…C7 pour le corpus) pour qu'un test et sa raison d'être se retrouvent.

Tout ici est PUR : aucun simulateur, aucun modèle, aucun appel réseau.

Lancement :
    services/llm-agents/.venv/bin/python -m pytest scripts/tests/test_059_corpus_et_grille.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.analysis.presse.corpus import (  # noqa: E402
    CONDITIONS,
    ECART_LONGUEUR_MAX,
    MENTION_TRADUCTION,
    RefusDeCorpus,
    charger_corpus,
)
from scripts.analysis.presse.grille import (  # noqa: E402
    CELLULES_ATTENDUES,
    RefusDeGrille,
    charger_grille,
)
from scripts.analysis.presse.lexique import mots_de_mobilite_trouves  # noqa: E402

GRILLE = RACINE / "docs" / "paper" / "sources" / "actualites" / "grille_signes.yaml"
CORPUS = RACINE / "docs" / "paper" / "sources" / "actualites" / "articles_txt"


def _grille_valide() -> dict:
    return yaml.safe_load(GRILLE.read_text(encoding="utf-8"))


def _ecrire(tmp_path: Path, d: dict) -> Path:
    p = tmp_path / "grille.yaml"
    p.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


# ── La grille livrée ────────────────────────────────────────────────────────────────────


def test_G1_la_grille_du_depot_porte_vingt_cellules():
    """Le chapitre 7 annonce vingt prédictions et pose la barre du binomial à quinze."""
    g = charger_grille(GRILLE)
    assert len(g.cellules) == CELLULES_ATTENDUES
    assert len(g.articles) == 5
    assert set(g.modes) == {"voiture", "velo", "marche", "tc"}


def test_G5_l_empreinte_est_stable_et_non_vide():
    """C'est le seul point qui rend le « pré-enregistré » vérifiable a posteriori."""
    assert charger_grille(GRILLE).empreinte == charger_grille(GRILLE).empreinte
    assert len(charger_grille(GRILLE).empreinte) == 64


def test_G3_les_trois_cellules_ambigues_sont_declarees_sans_effet_attendu():
    """Marche sous La Machine, voiture sous les éboueurs, marche sous VélôToulouse.

    Elles ne se lisent pas après la mesure : elles se déclarent, avec leur motif.
    """
    g = charger_grille(GRILLE)
    sans_effet = {(c.article, c.mode) for c in g.cellules if c.sans_effet_attendu}
    assert sans_effet == {
        ("a07_greve_eboueurs", "voiture"),
        ("a18_la_machine", "marche"),
        ("a25_velotoulouse", "marche"),
    }
    for article, mode in sans_effet:
        assert g.de(article, mode).motif, "une prédiction sans raison ne se discute pas"


def test_G4_toute_cellule_porte_un_motif():
    assert all(c.motif.strip() for c in charger_grille(GRILLE).cellules)


def test_G_concordance_du_signe_zero_est_une_concordance():
    """Prédire l'absence d'effet et l'observer est une concordance, pas une abstention."""
    c = charger_grille(GRILLE).de("a18_la_machine", "marche")
    assert c.concorde("0") is True
    assert c.concorde("+") is False
    assert c.concorde("-") is False


# ── Ce que la grille refuse ─────────────────────────────────────────────────────────────


def test_G1_refus_cellule_manquante(tmp_path):
    d = _grille_valide()
    del d["articles"]["a09_vent_autan"]["cellules"]["velo"]
    with pytest.raises(RefusDeGrille, match="n'a pas de cellule"):
        charger_grille(_ecrire(tmp_path, d))


def test_G1_refus_compte_different_de_vingt(tmp_path):
    d = _grille_valide()
    del d["articles"]["a25_velotoulouse"]
    with pytest.raises(RefusDeGrille, match="au lieu de 20"):
        charger_grille(_ecrire(tmp_path, d))


def test_G2_refus_signe_hors_domaine(tmp_path):
    d = _grille_valide()
    d["articles"]["a09_vent_autan"]["cellules"]["velo"]["signe"] = "?"
    with pytest.raises(RefusDeGrille, match="porte le signe"):
        charger_grille(_ecrire(tmp_path, d))


def test_G3_refus_signe_sans_intensite(tmp_path):
    """Une cellule qui déclare un signe sans intensité pourrait se replier sur « pas d'avis »."""
    d = _grille_valide()
    d["articles"]["a09_vent_autan"]["cellules"]["velo"]["intensite"] = 0
    with pytest.raises(RefusDeGrille, match="équivalence est stricte"):
        charger_grille(_ecrire(tmp_path, d))


def test_G3_refus_intensite_sans_signe(tmp_path):
    d = _grille_valide()
    d["articles"]["a18_la_machine"]["cellules"]["marche"]["intensite"] = 2
    with pytest.raises(RefusDeGrille, match="équivalence est stricte"):
        charger_grille(_ecrire(tmp_path, d))


def test_G4_refus_motif_vide(tmp_path):
    d = _grille_valide()
    d["articles"]["a09_vent_autan"]["cellules"]["velo"]["motif"] = "  "
    with pytest.raises(RefusDeGrille, match="pas de motif"):
        charger_grille(_ecrire(tmp_path, d))


# ── Le lexique de mobilité — ce qui rend C3 vérifiable ──────────────────────────────────


@pytest.mark.parametrize(
    "texte,langue,attendu",
    [
        ("Les trottoirs sont encombrés et la chaussée glissante.", "fr", True),
        ("La mairie ferme les jardins par précaution ce soir.", "fr", False),
        ("Commuters avoided the metro and took their bikes.", "en", True),
        ("The council closed the gardens as a precaution.", "en", False),
    ],
)
def test_C2_le_lexique_voit_les_mots_de_mobilite(texte, langue, attendu):
    assert bool(mots_de_mobilite_trouves(texte, langue)) is attendu


def test_C2_le_lexique_ne_se_declenche_pas_sur_un_prefixe():
    """« car » ne doit pas sortir sur « careful », ni « lane » sur « planet ».

    Un suffixe ouvert produirait des refus incompréhensibles, et un refus incompréhensible
    finit par être contourné.
    """
    trouves = mots_de_mobilite_trouves("He was careful, the planet is round, she is walking.", "en")
    assert "car" not in trouves
    assert "lane" not in trouves
    assert "walking" in trouves


def test_C2_le_lexique_voit_les_flexions_et_les_accents():
    assert "trottoir" in mots_de_mobilite_trouves("Les trottoirs sont pleins.", "fr")
    assert "chaussee" in mots_de_mobilite_trouves("La chaussée est glissante.", "fr")
    assert "ring road" in mots_de_mobilite_trouves("Stuck on the ring road again.", "en")


def test_C2_langue_inconnue_refusee():
    with pytest.raises(ValueError, match="langue inconnue"):
        mots_de_mobilite_trouves("texte", "es")


# ── Le corpus livré ─────────────────────────────────────────────────────────────────────

pytestmark_corpus = pytest.mark.skipif(
    not (CORPUS / "MANIFEST.yaml").is_file(),
    reason="corpus non extrait — lancez `python -m scripts.data.presse.extraire_textes extraire`",
)


@pytestmark_corpus
def test_C1_les_cinq_textes_bruts_francais_existent_et_sont_non_vides():
    for article_id in (
        "a09_vent_autan",
        "a13_punaises_metro",
        "a07_greve_eboueurs",
        "a18_la_machine",
        "a25_velotoulouse",
    ):
        p = CORPUS / article_id / "brut.fr.txt"
        assert p.is_file(), f"{p} manquant"
        assert len(p.read_text(encoding="utf-8").split()) > 50


@pytestmark_corpus
def test_C1_les_identifiants_du_corpus_sont_ceux_de_la_grille():
    """Deux fichiers qui divergeraient feraient scorer une prédiction contre un autre article."""
    manifeste = yaml.safe_load((CORPUS / "MANIFEST.yaml").read_text(encoding="utf-8"))
    assert set(manifeste["articles"]) == set(charger_grille(GRILLE).articles)


@pytestmark_corpus
def test_C7_le_manifeste_exige_de_nommer_qui_a_traduit(tmp_path):
    """Une traduction anonyme ne se vérifie pas."""
    manifeste = yaml.safe_load((CORPUS / "MANIFEST.yaml").read_text(encoding="utf-8"))
    manifeste["traduction"] = {"par": None, "le": None}
    p = tmp_path / "MANIFEST.yaml"
    p.write_text(yaml.safe_dump(manifeste, allow_unicode=True), encoding="utf-8")
    with pytest.raises(RefusDeCorpus, match="traduction anonyme"):
        charger_corpus(p)


def test_C6_la_mention_de_traduction_est_declaree_une_seule_fois():
    """L'agent lit qu'il lit une traduction ; le dispositif n'a pas à le lui cacher."""
    assert MENTION_TRADUCTION == "Translated from French"


def test_C4_l_ecart_de_longueur_admis_est_declare():
    assert ECART_LONGUEUR_MAX == 0.15
    assert CONDITIONS == ("brut", "paraphrase", "temoin")


# ── Les textes réellement au dépôt ──────────────────────────────────────────────────────

ARTICLES = (
    "a09_vent_autan",
    "a13_punaises_metro",
    "a07_greve_eboueurs",
    "a18_la_machine",
    "a25_velotoulouse",
)


@pytestmark_corpus
@pytest.mark.parametrize("article_id", ARTICLES)
def test_C1_chaque_article_porte_son_brut_dans_les_deux_langues(article_id):
    for nom in ("brut.fr.txt", "brut.txt"):
        p = CORPUS / article_id / nom
        assert p.is_file(), f"{p} manquant"
        assert len(p.read_text(encoding="utf-8").split()) > 100


def _exemptions(article_id: str, langue: str) -> tuple[str, ...]:
    manifeste = yaml.safe_load((CORPUS / "MANIFEST.yaml").read_text(encoding="utf-8"))
    declare = (manifeste["articles"][article_id].get("c3_mots_autorises") or {}).get(langue) or {}
    return tuple(declare.get("mots") or ())


@pytestmark_corpus
@pytest.mark.parametrize("article_id", ARTICLES)
@pytest.mark.parametrize("nom,langue", [("paraphrase.fr.txt", "fr"), ("paraphrase.txt", "en")])
def test_C2_aucune_paraphrase_livree_ne_nomme_un_mode_de_report(article_id, nom, langue):
    """C3 ne tient que si le texte ne nomme aucun mode VERS LEQUEL un report serait possible.

    Le sujet de l'article, lui, se nomme : un article sur le vélo partagé parle du vélo, et le
    cacher rendrait la paraphrase inintelligible sans rien prouver. Ce sont les modes de report
    qui doivent disparaître — c'est là, et seulement là, que se logerait le suivisme lexical.

    Deux mots se sont fait prendre à la première écriture — « mises en ligne » et
    « underground » — qu'aucune relecture humaine n'aurait signalés.
    """
    p = CORPUS / article_id / nom
    trouves = mots_de_mobilite_trouves(
        p.read_text(encoding="utf-8"), langue, _exemptions(article_id, langue)
    )
    assert not trouves, f"{p} porte {list(trouves)}"


@pytestmark_corpus
@pytest.mark.parametrize("article_id", ARTICLES)
@pytest.mark.parametrize("langue", ["fr", "en"])
def test_C2_un_mot_exempte_figure_dans_le_texte_brut(article_id, langue):
    """On n'exempte pas un mot par précaution, on exempte celui que le sujet impose.

    Sans cette garde, il suffirait d'exempter « voiture » sur l'article des punaises pour que la
    paraphrase puisse suggérer le report — et la condition C3 se viderait sans bruit.
    """
    nom = "brut.txt" if langue == "en" else "brut.fr.txt"
    brut = (CORPUS / article_id / nom).read_text(encoding="utf-8")
    presents = set(mots_de_mobilite_trouves(brut, langue))
    for mot in _exemptions(article_id, langue):
        assert mot in presents, f"{article_id} ({langue}) exempte {mot!r}, absent du texte brut"


@pytestmark_corpus
def test_C2_les_exemptions_ne_couvrent_jamais_un_mode_de_report():
    """Aucun article n'exempte un mode vers lequel son événement pousserait.

    C'est la garde de fond : « métro » s'exempte sur l'article des punaises parce qu'il en est le
    sujet ; « vélo » ne s'y exempte pas, parce qu'il en est le report attendu.
    """
    manifeste = yaml.safe_load((CORPUS / "MANIFEST.yaml").read_text(encoding="utf-8"))
    reports_interdits = {
        "a13_punaises_metro": {"velo", "voiture", "marche", "bike", "bicycle", "car", "walk"},
        "a25_velotoulouse": {"voiture", "bus", "marche", "car", "walk", "walking"},
    }
    for article_id, interdits in reports_interdits.items():
        declare = manifeste["articles"][article_id].get("c3_mots_autorises") or {}
        for langue in ("fr", "en"):
            mots = set((declare.get(langue) or {}).get("mots") or ())
            assert not (mots & interdits), f"{article_id} ({langue}) exempte un mode de report"


@pytestmark_corpus
@pytest.mark.parametrize("article_id", ARTICLES)
def test_C1_les_empreintes_du_manifeste_correspondent_aux_fichiers(article_id):
    """Un article est CITÉ, jamais réécrit : une divergence fait refuser le chargement."""
    import hashlib

    manifeste = yaml.safe_load((CORPUS / "MANIFEST.yaml").read_text(encoding="utf-8"))
    declare = manifeste["articles"][article_id]
    verifiees = 0
    for condition in CONDITIONS:
        for langue, meta in (declare.get(condition) or {}).items():
            nom = f"{condition}.txt" if langue == "en" else f"{condition}.{langue}.txt"
            donnees = (CORPUS / article_id / nom).read_bytes()
            assert hashlib.sha256(donnees).hexdigest() == meta["sha256"], f"{article_id}/{nom}"
            verifiees += 1
    assert verifiees >= 4, f"{article_id} : {verifiees} empreintes déclarées, brut et paraphrase attendus"


# ── Le témoin commun (décision de l'auteur, 2026-09-21) ─────────────────────────────────


@pytestmark_corpus
def test_C4_le_corpus_complet_se_charge():
    """Le chargement est la vérification : il refuse tout ce que les règles C1 à C9 interdisent."""
    c = charger_corpus(CORPUS / "MANIFEST.yaml")
    assert set(c.articles) == set(ARTICLES)
    assert c.traduction_par and c.traduction_le


@pytestmark_corpus
def test_C4_un_seul_temoin_sert_les_cinq_articles():
    """Un témoin unique rend C4 COMPARABLE d'un article à l'autre.

    Cinq témoins feraient dépendre le contrôle de spécificité de cinq choix distincts ; ce que
    C4 mesure — l'effet d'ajouter un texte quel qu'il soit — n'en demande qu'un.
    """
    c = charger_corpus(CORPUS / "MANIFEST.yaml")
    empreintes = {c.articles[a].texte("temoin", "en").empreinte for a in ARTICLES}
    assert len(empreintes) == 1


@pytestmark_corpus
@pytest.mark.parametrize("article_id", ARTICLES)
def test_C4_le_temoin_est_apparie_en_longueur_a_chaque_article(article_id):
    """Ce qui distingue C4 de C2 ne doit pas être la taille du bloc ajouté au contexte."""
    c = charger_corpus(CORPUS / "MANIFEST.yaml")
    a = c.articles[article_id]
    brut, temoin = a.texte("brut", "en").mots, a.texte("temoin", "en").mots
    assert abs(temoin - brut) / brut <= ECART_LONGUEUR_MAX


@pytestmark_corpus
def test_C6_l_entree_servie_a_l_agent_porte_la_mention_de_traduction():
    c = charger_corpus(CORPUS / "MANIFEST.yaml")
    for article_id in ARTICLES:
        assert c.articles[article_id].entree_pour_agent().startswith(f"[{MENTION_TRADUCTION}]")
