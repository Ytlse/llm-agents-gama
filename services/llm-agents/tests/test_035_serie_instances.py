"""Les clés d'un même modèle se consomment en SÉRIE (décision du 2026-09-07).

Deux clés servent `gemini-3.5-flash-lite`, chacune avec son seau de 500 requêtes par jour. La
rotation entamait les deux en parallèle ; on veut épuiser la première avant de toucher à la
seconde, pour garder un seau intact et savoir ce qu'on a consommé.
"""

from experiences.decideurs import DecideurPasserelle


class MoniteurFactice:
    """Ne garde que les instances dont le quota du JOUR n'est pas épuisé, comme le vrai."""

    def __init__(self, disponibles: list[str]):
        self.disponibles = list(disponibles)

    def instances_disponibles(self, besoin: int = 1) -> list[str]:
        return list(self.disponibles)


def _decideur(instances, moniteur=None) -> DecideurPasserelle:
    return DecideurPasserelle(agent=None, modele="modele-x", instances=instances, moniteur=moniteur)


def test_la_premiere_instance_est_servie_tant_qu_elle_a_du_quota():
    moniteur = MoniteurFactice(["cle1", "cle2"])
    d = _decideur(["cle1", "cle2"], moniteur)

    assert [d._prochaine_instance() for _ in range(5)] == ["cle1"] * 5, \
        "sans épuisement, on reste sur la première : pas de rotation"


def test_on_bascule_quand_la_premiere_est_epuisee():
    moniteur = MoniteurFactice(["cle1", "cle2"])
    d = _decideur(["cle1", "cle2"], moniteur)
    assert d._prochaine_instance() == "cle1"

    moniteur.disponibles = ["cle2"]           # quota du jour épuisé sur cle1
    assert d._prochaine_instance() == "cle2"
    assert d._prochaine_instance() == "cle2"

    moniteur.disponibles = []                  # les deux épuisées
    assert d._prochaine_instance() is None


def test_la_bascule_est_journalisee_par_son_RANG_jamais_par_son_nom(caplog):
    """Le journal est lu, copié et transmis : le nom d'une instance désigne un compte."""
    import logging

    from loguru import logger

    # loguru vers caplog, le temps du test
    poignee = logger.add(lambda m: logging.getLogger("loguru").warning(m.record["message"]), level="INFO")
    try:
        moniteur = MoniteurFactice(["cle_secrete_1", "cle_secrete_2"])
        d = _decideur(["cle_secrete_1", "cle_secrete_2"], moniteur)
        with caplog.at_level(logging.INFO, logger="loguru"):
            assert d._prochaine_instance() == "cle_secrete_1"
            moniteur.disponibles = ["cle_secrete_2"]
            assert d._prochaine_instance() == "cle_secrete_2"
    finally:
        logger.remove(poignee)

    journal = "\n".join(r.getMessage() for r in caplog.records)
    assert "Passage sur la seconde clé" in journal, journal
    assert "(2/2)" in journal
    assert "épuisé son quota du jour" in journal
    assert "cle_secrete" not in journal, "aucun nom d'instance ne doit apparaître dans le journal"


def test_les_rangs_se_disent_en_mots():
    from experiences.decideurs import rang_en_mots

    assert rang_en_mots(1) == "première"
    assert rang_en_mots(2) == "seconde"
    assert rang_en_mots(10) == "dixième"
    assert rang_en_mots(11) == "n° 11", "au-delà de dix, on numérote"


def test_sans_moniteur_l_ordre_declare_fait_foi():
    d = _decideur(["cle1", "cle2"])
    assert [d._prochaine_instance() for _ in range(3)] == ["cle1"] * 3


# ── fraîcheur de l'instantané des quotas ─────────────────────────────────────
# Le décideur ne bascule que si `instances_disponibles` change. Rien ne le faisait changer
# pendant un run : `etat` restait celui du démarrage, donc une clé épuisée en cours de route
# restait « disponible » et la suivante n'était jamais entamée (2026-09-08, run arrêté à
# 70,5 % avec 500 requêtes intactes en réserve).


def _moniteur(lecteur):
    from experiences.ressources import MoniteurRessources

    return MoniteurRessources(
        instances=["cle1", "cle2"],
        providers={"cle1": {"rpd_limit": 500}, "cle2": {"rpd_limit": 500}},
        base_url="http://passerelle-de-test",
        lecteur=lecteur,
    )


def test_l_instantane_des_quotas_n_est_relu_qu_une_fois_perime():
    lectures = []

    def lecteur(_url):
        lectures.append(1)
        return {"cle1": {"daily_requests": 0}, "cle2": {"daily_requests": 0}}

    m = _moniteur(lecteur)
    assert m.perime(30.0) is True, "jamais lu ⇒ périmé d'office"
    assert m.rafraichir_si_perime(30.0) is True and len(lectures) == 1

    assert m.rafraichir_si_perime(30.0) is False, "trop tôt : on ne martèle pas /health"
    assert len(lectures) == 1
    assert m.rafraichir_si_perime(0.0) is True, "âge nul ⇒ toujours relu"
    assert len(lectures) == 2


def test_une_passerelle_injoignable_laisse_l_instantane_en_place():
    """Fail-safe : on préfère un état un peu vieux à un état vide, qui ferait croire à
    l'épuisement de toutes les clés et arrêterait le run pour rien.

    L'âge, lui, reste celui de la dernière lecture RÉUSSIE : la veille réessaiera à son
    échéance normale au lieu de marteler une passerelle en panne.
    """
    reponses = [{"cle1": {"daily_requests": 12}, "cle2": {"daily_requests": 0}}, None]

    m = _moniteur(lambda _url: reponses.pop(0))
    assert m.rafraichir_si_perime(0.0) is True
    avant, age_avant = dict(m.etat), m.maj_monotone

    assert m.rafraichir_si_perime(0.0) is True, "elle a bien tenté la lecture"
    assert m.etat == avant, "l'instantané précédent est conservé"
    assert m.joignable is False
    assert m.maj_monotone == age_avant, "un échec ne rajeunit pas l'instantané"
    assert m.instances_disponibles() == ["cle1", "cle2"], \
        "un échec de lecture ne doit jamais faire croire que les clés sont épuisées"


def test_la_relecture_fait_basculer_le_decideur_sans_attendre_d_erreur():
    """Le cœur du correctif : la clé épuisée sort des disponibles à la relecture, donc le
    décideur épingle la suivante — sans qu'aucune sollicitation ait eu à échouer."""
    frais = {
        "cle1": {"daily_requests": 100, "quota_exhausted": False, "available": True},
        "cle2": {"daily_requests": 0, "quota_exhausted": False, "available": True},
    }
    epuisee = {
        "cle1": {"daily_requests": 500, "quota_exhausted": True, "available": False},
        "cle2": {"daily_requests": 0, "quota_exhausted": False, "available": True},
    }
    # Le premier appel rend l'état frais, les suivants l'état épuisé.
    etats = [frais, epuisee]
    m = _moniteur(lambda _url: etats.pop(0) if len(etats) > 1 else etats[0])

    m.rafraichir()  # ce que fait le démarrage du run
    d = _decideur(["cle1", "cle2"], m)
    assert d._prochaine_instance() == "cle1", "tant qu'elle a du quota, on reste dessus"

    m.rafraichir_si_perime(0.0)  # ce que fait `veiller_quotas` toutes les 30 s
    assert m.instances_disponibles() == ["cle2"], m.instances_disponibles()
    assert d._prochaine_instance() == "cle2", \
        "la seconde clé est entamée, ses 500 requêtes servent"
