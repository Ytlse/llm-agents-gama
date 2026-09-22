"""Ticket 100, lot 2 — le canal `lu`, la prise `reveil`, la citation, les foyers.

Contrat de référence : `specs/ticket_100/tests.md`, règles R12 à R23.

Le lot 2 livre le second régime : l'agent sait AVANT de décider. Tout ce qui le distingue du
choc tient dans ce mot — et dans le fait que rien, dans le monde, n'a bougé.

Tout ici est PUR : aucun simulateur, aucun modèle, aucun appel réseau.
"""

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm import evenements as ev
from llm.evenements import RefusDEvenement, RegistreEvenements, charger
from settings import settings

RACINE = Path(__file__).resolve().parents[1]
CONFIG_EVENEMENTS = RACINE / "config" / "evenements"
CORPUS = RACINE.parents[1] / "docs" / "paper" / "sources" / "actualites" / "articles_txt"

ARTICLES = (
    "a07_greve_eboueurs", "a09_vent_autan", "a13_punaises_metro",
    "a18_la_machine", "a25_velotoulouse",
)


@dataclass
class FauxAgent:
    """Le minimum que la règle `foyers` lit sur un agent : son identité et son ménage."""

    person_id: str
    household_id: str | None = None
    immobile: bool = False


def _population(*couples) -> list:
    return [FauxAgent(person_id=p, household_id=h) for p, h in couples]


def _texte(tmp_path: Path, contenu: str, nom: str = "brut.txt") -> tuple[Path, str]:
    dossier = tmp_path / "articles_txt" / "a99_test"
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / nom
    fichier.write_text(contenu, encoding="utf-8")
    return fichier, hashlib.sha256(fichier.read_bytes()).hexdigest()


ARTICLE = (
    "Toulouse: the metro will run a reduced service on Line A next week while signalling "
    "work is carried out at Jean-Jaures. The operator says trains will be spaced further "
    "apart between 10am and 4pm."
)


def _declaration(fichier: Path, sha: str, **surcharges) -> dict:
    base = {
        "evenement": "a99_test",
        "libelle": "Article de test",
        "source": "test",
        "canal": "lu",
        "moment": "reveil",
        "jugement": "aucun",
        "texte": {"fichier": str(fichier), "sha256": sha},
        "calendrier": {"fenetre_jours": [9, 13], "graine": 59},
        "exposition": {
            "regle": "foyers", "foyers": ["5177", "18056"],
            "lecteurs_par_foyer": 1, "graine": 59,
        },
        "cadence": "jour",
    }
    base.update(surcharges)
    return base


def _ecrire(tmp_path: Path, declaration: dict) -> Path:
    p = tmp_path / "evenement.yaml"
    p.write_text(yaml.safe_dump(declaration, allow_unicode=True), encoding="utf-8")
    return p


@pytest.fixture(autouse=True)
def _registre_propre():
    ev.reinitialiser()
    settings.evenements.enabled = False
    settings.evenements.fichier = None
    settings.chocs.enabled = False
    yield
    ev.reinitialiser()
    settings.evenements.enabled = False
    settings.evenements.fichier = None
    settings.chocs.enabled = False


# ── R13, R14. Le monde ne bouge pas ──────────────────────────────────────────────────────
def test_R13_un_article_ne_fait_subir_aucun_retard(tmp_path):
    f, sha = _texte(tmp_path, ARTICLE)
    e = charger(_ecrire(tmp_path, _declaration(f, sha)))
    assert e.jours == {}  # pas de profil jour par jour : un article est le même tous les matins
    assert e.texte_cite is not None


def test_R14_un_effet_physique_au_reveil_est_refuse(tmp_path):
    """Le monde ne change pas avant la décision (§ 9 du ticket).

    Sans cette règle, le jour de l'événement mesurerait à la fois une anticipation et une
    contrainte, et rien ne saurait les séparer.
    """
    d = {
        "evenement": "e_test", "canal": "vecu", "moment": "reveil", "jugement": "aucun",
        "exposition": {"regle": "agents", "agents": ["609"]},
        "jours": [{"jour": 3, "retard_min": 30, "texte": "I could not start my car."}],
    }
    with pytest.raises(RefusDEvenement, match="RÉVEIL"):
        charger(_ecrire(tmp_path, d))


def test_R14bis_un_canal_lu_pose_a_larrivee_est_refuse(tmp_path):
    f, sha = _texte(tmp_path, ARTICLE)
    with pytest.raises(RefusDEvenement, match="AVANT de décider"):
        charger(_ecrire(tmp_path, _declaration(f, sha, moment="arrivee")))


# ── R15, R16, R17. La garde de citation ──────────────────────────────────────────────────
def test_R15_un_texte_modifie_depuis_la_declaration_est_refuse(tmp_path):
    f, sha = _texte(tmp_path, ARTICLE)
    declaration = _ecrire(tmp_path, _declaration(f, sha))
    f.write_text(ARTICLE + " One more sentence.", encoding="utf-8")
    with pytest.raises(RefusDEvenement, match="a CHANGÉ"):
        charger(declaration)


def test_R15bis_une_empreinte_absente_est_refusee(tmp_path):
    f, sha = _texte(tmp_path, ARTICLE)
    with pytest.raises(RefusDEvenement, match="sha256` absent"):
        charger(_ecrire(tmp_path, _declaration(f, "")))


def test_R15ter_la_seconde_comparaison_attrape_ce_que_la_premiere_laisse_passer(tmp_path):
    """Déclaration et fichier d'accord, manifeste en désaccord : refusé.

    C'est le cas que la comparaison au seul fichier laisserait passer — un texte retouché en
    même temps que sa déclaration. Deux campagnes croiraient avoir joué le même article.
    """
    f, sha = _texte(tmp_path, ARTICLE)
    manifeste = f.parent.parent / "MANIFEST.yaml"
    manifeste.write_text(
        yaml.safe_dump({"articles": {"a99_test": {"brut": {"en": {"sha256": "0" * 64}}}}}),
        encoding="utf-8",
    )
    with pytest.raises(RefusDEvenement, match="manifeste"):
        charger(_ecrire(tmp_path, _declaration(f, sha)))


def test_R15quater_un_texte_introuvable_dit_ou_il_a_cherche(tmp_path):
    with pytest.raises(RefusDEvenement, match="Cherché à"):
        charger(_ecrire(tmp_path, _declaration(Path("nulle/part/brut.txt"), "0" * 64)))


def test_R16_les_cinq_articles_du_059_concordent_avec_leur_manifeste():
    """Chargés depuis le dépôt, empreintes vérifiées contre `MANIFEST.yaml`."""
    for nom in ARTICLES:
        chemin = CONFIG_EVENEMENTS / f"{nom}.yaml"
        assert chemin.is_file(), f"article déclaré manquant : {nom}"
        e = charger(chemin)  # la garde de citation s'exécute ici
        assert e.canal == "lu" and e.moment == "reveil"
        assert e.texte_cite is not None and e.texte_cite.contenu
        assert e.exposition.regle == "foyers"
        assert e.calendrier.fenetre == (9, 13)


def test_R17_la_mention_de_traduction_est_dans_lentree_servie():
    """Une traduction servie comme un original serait une condition non déclarée."""
    e = charger(CONFIG_EVENEMENTS / "a13_punaises_metro.yaml")
    assert e.texte_cite.mention == "Translated from French"
    assert "Translated from French" in e.texte_cite.servi
    assert e.texte_cite.servi.endswith(e.texte_cite.contenu)


# ── Les gardes de contenu s'appliquent au texte cité ─────────────────────────────────────
def test_un_article_qui_dicte_un_mode_est_refuse(tmp_path):
    f, sha = _texte(tmp_path, "Residents should avoid the metro this week, the city says.")
    with pytest.raises(RefusDEvenement, match="avoid"):
        charger(_ecrire(tmp_path, _declaration(f, sha)))


def test_une_exemption_ne_vaut_que_declaree_motivee_et_presente(tmp_path):
    texte = "City staff must first inspect each site to make sure there is no danger."
    f, sha = _texte(tmp_path, texte)
    # Sans exemption : refusé, et le message dit comment exempter.
    with pytest.raises(RefusDEvenement, match="marqueurs_exemptes"):
        charger(_ecrire(tmp_path, _declaration(f, sha)))
    # Exemption sans motif : refusée.
    d = _declaration(f, sha)
    d["texte"]["marqueurs_exemptes"] = [{"marqueur": "make sure"}]
    with pytest.raises(RefusDEvenement, match="sans motif"):
        charger(_ecrire(tmp_path, d))
    # Exemption d'un marqueur ABSENT : refusée — on n'exempte pas par précaution.
    d["texte"]["marqueurs_exemptes"] = [{"marqueur": "you should", "motif": "au cas où"}]
    with pytest.raises(RefusDEvenement, match="NE FIGURE PAS"):
        charger(_ecrire(tmp_path, d))
    # Exemption en règle : le texte passe.
    d["texte"]["marqueurs_exemptes"] = [
        {"marqueur": "make sure", "motif": "le sujet est le personnel municipal"}
    ]
    assert charger(_ecrire(tmp_path, d)).texte_cite is not None


def test_ladresse_a_la_deuxieme_personne_ne_sexempte_jamais(tmp_path):
    f, sha = _texte(tmp_path, "The city reminds you that the metro closes at midnight.")
    d = _declaration(f, sha)
    d["texte"]["marqueurs_exemptes"] = [{"marqueur": "you", "motif": "essayons"}]
    with pytest.raises(RefusDEvenement, match="deuxième"):
        charger(_ecrire(tmp_path, d))


# ── R18, R19. La règle `foyers` ──────────────────────────────────────────────────────────
def _registre(tmp_path, **surcharges) -> RegistreEvenements:
    f, sha = _texte(tmp_path, ARTICLE)
    return RegistreEvenements(charger(_ecrire(tmp_path, _declaration(f, sha, **surcharges))))


POPULATION = _population(
    ("12", "5177"), ("49", "5177"),          # Constance et Jacques
    ("66", "18056"), ("65", "18056"),        # Valérie et Maurice
    ("40", "312"),                           # Xavier, seul — hors foyers déclarés
)


def test_R18_un_lecteur_par_foyer_et_le_co_resident_est_temoin(tmp_path):
    lecteurs = _registre(tmp_path).lecteurs(POPULATION)
    assert len(lecteurs) == 2
    assert {h for _, (h, _) in lecteurs.items()} == {"5177", "18056"}
    assert "40" not in lecteurs  # foyer non déclaré : rien
    for foyer in ("5177", "18056"):
        membres = {p for p, (h, _) in lecteurs.items() if h == foyer}
        assert len(membres) == 1, "le co-résident non tiré est le témoin interne"


def test_R18bis_le_tirage_des_lecteurs_est_stable_sur_trois_executions(tmp_path):
    tirages = [
        set(RegistreEvenements(charger(
            _ecrire(tmp_path, _declaration(*_texte(tmp_path, ARTICLE)))
        )).lecteurs(POPULATION))
        for _ in range(3)
    ]
    assert tirages[0] == tirages[1] == tirages[2]
    # Et l'ordre de la population ne change rien.
    autre = RegistreEvenements(charger(
        _ecrire(tmp_path, _declaration(*_texte(tmp_path, ARTICLE)))
    )).lecteurs(list(reversed(POPULATION)))
    assert set(autre) == tirages[0]


def test_R18ter_deux_lecteurs_par_foyer_en_donnent_deux(tmp_path):
    r = _registre(tmp_path, exposition={
        "regle": "foyers", "foyers": ["5177"], "lecteurs_par_foyer": 2, "graine": 59,
    })
    assert set(r.lecteurs(POPULATION)) == {"12", "49"}


def test_R19_un_foyer_sans_membre_mobile_leve_une_alarme_et_ne_lit_pas(tmp_path):
    r = _registre(tmp_path, exposition={
        "regle": "foyers", "foyers": ["99999"], "lecteurs_par_foyer": 1, "graine": 59,
    })
    assert r.lecteurs(POPULATION) == {}


def test_R19bis_une_regle_foyers_sans_foyer_est_refusee(tmp_path):
    f, sha = _texte(tmp_path, ARTICLE)
    d = _declaration(f, sha, exposition={"regle": "foyers", "foyers": []})
    with pytest.raises(RefusDEvenement, match="sans aucun identifiant"):
        charger(_ecrire(tmp_path, d))


def test_R19ter_les_immobiles_ne_lisent_pas(tmp_path):
    population = [FauxAgent("12", "5177", immobile=True), FauxAgent("49", "5177")]
    assert set(_registre(tmp_path).lecteurs(population)) == {"49"}


# ── R20, R21. La fenêtre tirée ───────────────────────────────────────────────────────────
def test_R20_le_jour_est_dans_la_fenetre_stable_et_differe_dun_foyer_a_lautre(tmp_path):
    r = _registre(tmp_path)
    cibles = [str(1000 + i) for i in range(20)]
    jours = {c: r.evenement.calendrier.jour_de("a99_test", c) for c in cibles}
    assert all(9 <= j <= 13 for j in jours.values()), jours
    # Stable : rejoué, le même foyer tire le même jour.
    assert jours == {c: r.evenement.calendrier.jour_de("a99_test", c) for c in cibles}
    # Et tous ne lisent pas le même matin — c'est ce qui sépare l'article du calendrier.
    assert len(set(jours.values())) > 1


def test_R20bis_les_membres_dun_meme_foyer_lisent_le_meme_jour(tmp_path):
    """Sinon le co-résident témoin ne serait plus comparable au lecteur sur la même journée."""
    r = _registre(tmp_path, exposition={
        "regle": "foyers", "foyers": ["5177"], "lecteurs_par_foyer": 2, "graine": 59,
    })
    assert r.jour_de("12", "5177") == r.jour_de("49", "5177")


@pytest.mark.parametrize(
    "fenetre, motif",
    [([13, 9], "est vide"), ([0, 5], "n° 1"), ([9], "deux bornes")],
)
def test_R21_une_fenetre_impossible_est_refusee(tmp_path, fenetre, motif):
    f, sha = _texte(tmp_path, ARTICLE)
    d = _declaration(f, sha, calendrier={"fenetre_jours": fenetre, "graine": 59})
    with pytest.raises(RefusDEvenement) as err:
        charger(_ecrire(tmp_path, d))
    assert motif in str(err.value)


# ── R12, R22. La prise `reveil` ──────────────────────────────────────────────────────────
def _le_jour(registre, jour: int):
    RegistreEvenements.jour_du_run = staticmethod(lambda ts, _j=jour: _j)


def _rendre_le_calendrier():
    from llm.evenements import calendrier as _cal

    RegistreEvenements.jour_du_run = staticmethod(_cal.jour_du_run)


def test_R12_linjection_na_lieu_quune_fois_par_agent(tmp_path):
    r = _registre(tmp_path)
    try:
        lecteurs = r.lecteurs(POPULATION)
        servis = {}
        for jour in range(9, 14):
            _le_jour(r, jour)
            for person_id, applique in r.dus_au_reveil(1_700_000_000, POPULATION):
                servis.setdefault(person_id, []).append(jour)
            # Rappelée trois fois le même jour : rien de plus.
            assert r.dus_au_reveil(1_700_000_000, POPULATION) == []
            assert r.dus_au_reveil(1_700_000_000, POPULATION) == []
        assert set(servis) == set(lecteurs)
        assert all(len(j) == 1 for j in servis.values()), servis
    finally:
        _rendre_le_calendrier()


def test_R22_un_co_resident_non_tire_ne_recoit_rien(tmp_path):
    r = _registre(tmp_path)
    try:
        lecteurs = set(r.lecteurs(POPULATION))
        recus = set()
        for jour in range(9, 14):
            _le_jour(r, jour)
            recus |= {p for p, _ in r.dus_au_reveil(1_700_000_000, POPULATION)}
        assert recus == lecteurs
        temoins = {a.person_id for a in POPULATION} - lecteurs
        assert temoins and not (temoins & recus)
    finally:
        _rendre_le_calendrier()


def test_R12bis_lentree_servie_porte_le_prefixe_et_le_texte(tmp_path):
    r = _registre(tmp_path)
    try:
        for jour in range(9, 14):
            _le_jour(r, jour)
            for _, applique in r.dus_au_reveil(1_700_000_000, POPULATION):
                entree = ev.entree_de_lecture(applique)
                assert entree.startswith("[ PRESSE ] This morning I read in the paper:")
                assert ARTICLE in entree
                assert applique.retard_injecte_s == 0
                assert applique.incident_reseau is False
                return
        pytest.fail("aucun lecteur servi : le test ne prouve rien")
    finally:
        _rendre_le_calendrier()


def test_une_prise_arrivee_ne_rend_rien_au_reveil(tmp_path):
    """Les deux prises restent à leur place : c'est tout le contraste du chapitre 7."""
    from llm.evenements.declaration import Calendrier

    chemin = RACINE / "config" / "evenements" / "c6_voiture_suspecte.yaml"
    r = RegistreEvenements(charger(chemin))
    try:
        _le_jour(r, 15)
        assert r.dus_au_reveil(1_700_000_000, POPULATION) == []
    finally:
        _rendre_le_calendrier()


# ── Le cache, coupé le jour de l'événement (Q5) ──────────────────────────────────────────
def test_le_cache_est_coupe_le_jour_de_levenement_et_pas_les_autres(tmp_path):
    chemin = RACINE / "config" / "evenements" / "c6_voiture_suspecte.yaml"
    r = RegistreEvenements(charger(chemin))  # jours 15 et 16
    try:
        for jour, attendu in ((14, False), (15, True), (16, True), (17, False)):
            _le_jour(r, jour)
            assert r.cache_coupe(1_700_000_000) is attendu, f"jour {jour}"
    finally:
        _rendre_le_calendrier()


def test_la_coupure_couvre_toute_la_fenetre_quand_les_jours_sont_tires(tmp_path):
    """Sans la population, on ne sait pas QUI lit quel matin : on coupe large.

    Couper large coûte quelques journées d'appels ; couper à côté laisserait resservir une
    décision le matin même de la parution.
    """
    r = _registre(tmp_path)  # fenêtre [9, 13]
    try:
        for jour, attendu in ((8, False), (9, True), (11, True), (13, True), (14, False)):
            _le_jour(r, jour)
            assert r.cache_coupe(1_700_000_000) is attendu, f"jour {jour}"
    finally:
        _rendre_le_calendrier()


def test_sans_evenement_le_cache_nest_jamais_coupe():
    assert ev.registre() is None
    assert ev.cache_coupe(1_700_000_000) is False


# ── La correction du défaut du 2026-09-22 ────────────────────────────────────────────────
def test_la_prise_reveil_ecrit_AUSSI_en_memoire_longue():
    """Sans cette écriture, le régime `reveil` ne fait pas ce qu'il annonce.

    Mesuré dans le code : la décision ne lit QUE la mémoire longue
    (`query_past_experiences_for_travel` → `aquery_user_memories`), et la consolidation du soir
    CONSOMME le tampon court (`remove_batch`) en n'écrivant que la réflexion et les concepts.
    Une entrée posée à 3 h en mémoire courte n'atteindrait donc aucune décision du jour, et
    « l'agent sait avant de décider » serait faux.

    Vérifié par lecture de source, comme les tests-frontière R14 et R15 du ticket 079 : monter
    un contrôleur complet demanderait GAMA, un modèle et un index vectoriel.
    """
    ctrl = (RACINE / "urban_mobility_agents" / "simulation_controller.py").read_text("utf-8")
    debut = ctrl.index("def _injecter_evenements_du_reveil")
    fin = ctrl.index("async def _tirer_accidents_du_jour")
    methode = ctrl[debut:fin]
    assert "add_short_term_memory" in methode, "la réflexion du soir doit voir ce qui a été lu"
    assert "aadd_long_term_memory" in methode, (
        "la décision du JOUR MÊME ne lit que la mémoire longue : sans cette écriture, "
        "l'article n'atteint aucune décision avant le lendemain"
    )
    # Et la décision, elle, ne lit toujours que la mémoire longue : si cela changeait, la
    # double écriture ci-dessus deviendrait une duplication au lieu d'une nécessité.
    agent = (RACINE / "urban_mobility_agents" / "agents" / "llm_agent.py").read_text("utf-8")
    assert "hist = await self.long_term_memory.aquery_user_memories(" in agent


def test_le_choc_lui_necrit_pas_en_memoire_longue():
    """L'asymétrie est le régime, pas un oubli.

    Un choc s'applique après la décision : que son effet ne commence que le lendemain est
    exactement ce qu'on veut, et c'est ce qui rend les jours suivants imputables au seul
    souvenir. Lui ouvrir le même chemin effacerait la différence entre les deux régimes.
    """
    ctrl = (RACINE / "urban_mobility_agents" / "simulation_controller.py").read_text("utf-8")
    debut = ctrl.index("# ── Ticket 100 — l'événement déclaré")
    fin = ctrl.index("await GamaArrivalsLogger")
    prise_arrivee = ctrl[debut:fin]
    assert "joindre" in prise_arrivee
    assert "aadd_long_term_memory" not in prise_arrivee


def test_un_article_peut_nommer_des_modes_de_transport(tmp_path):
    """Décision de l'auteur, 2026-09-22. À ne pas confondre avec la liste du 059 lot 1.

    Celle-là interdit le vocabulaire de mobilité dans la PARAPHRASE (C3) et le TÉMOIN (C4),
    pour que ces conditions ne parlent pas de transport du tout. Elle ne s'applique pas au
    texte brut cité, qui est l'article. La frontière de ce module n'est pas le vocabulaire,
    c'est la destination de la phrase.
    """
    texte = (
        "Toulouse: metro Line A, the bus network and the VélôToulouse bike scheme will all be "
        "affected by Thursday's strike. Drivers are expected to face heavy congestion on the "
        "ring road, and the tram will run every twenty minutes instead of six."
    )
    f, sha = _texte(tmp_path, texte)
    e = charger(_ecrire(tmp_path, _declaration(f, sha)))
    for mode in ("metro", "bus", "bike", "ring road", "tram"):
        assert mode in e.texte_cite.contenu


def test_les_foyers_declares_existent_dans_la_population_du_059():
    """Trouvé le 2026-09-22 : les cinq articles nommaient des foyers d'une AUTRE population.

    Les identifiants venaient de la liste du ticket 078 § 7, qui porte sur la cohorte v6
    entière. La population de campagne est `population_20_foyers_059`, dix foyers tout autres :
    une campagne aurait levé l'[ALARME] « aucun lecteur retenu » et se serait déroulée sans
    qu'un seul agent lise quoi que ce soit.

    La garde a fait son travail — elle aurait crié — mais crier au lancement d'une campagne de
    quarante jours coûte plus cher que ce test.
    """
    import yaml as _yaml

    manifeste = (
        RACINE.parents[1] / "data" / "population" / "population_20_foyers_059" / "MANIFEST.yaml"
    )
    if not manifeste.is_file():
        pytest.skip("population de campagne absente de ce poste")
    m = _yaml.safe_load(manifeste.read_text("utf-8"))
    attendus = {f["household_id"] for f in m["groupes"]["expose"]}
    temoins = {f["household_id"] for f in m["groupes"]["temoin"]}

    for nom in ARTICLES:
        e = charger(CONFIG_EVENEMENTS / f"{nom}.yaml")
        assert set(e.exposition.foyers) == attendus, (
            f"{nom} n'expose pas les foyers que le manifeste déclare exposés"
        )
        assert not (set(e.exposition.foyers) & temoins), (
            f"{nom} exposerait un foyer TÉMOIN — le témoin est dans le même run, et "
            f"l'exposer effacerait la ligne de base"
        )
