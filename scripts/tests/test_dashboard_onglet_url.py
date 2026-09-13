"""L'onglet ouvert vit dans l'URL : un rafraîchissement revient là où on était.

Un F5 ouvre une session Streamlit neuve — tout l'état client est perdu, et la page
retombait sur « Vue d'ensemble » quel que soit l'onglet qu'on regardait. Le seul repère qui
survit à un rafraîchissement est la barre d'adresse : c'est ce que ces tests vérifient, dans
les deux sens (l'URL ouvre le bon onglet, un slug trafiqué ne casse pas la page).
"""

import sys
from pathlib import Path

import pytest

streamlit = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
APP = RACINE / "scripts" / "dashboard" / "app.py"


def slug_dans_l_url(at: AppTest) -> str | None:
    """Le slug tel que la barre d'adresse le porterait.

    Le harnais rend les query params bruts — une liste de valeurs par clé, là où
    `st.query_params` côté application rend la dernière valeur. On normalise ici.
    """
    valeur = at.query_params.get("onglet")
    return valeur[-1] if isinstance(valeur, list) else valeur


@pytest.fixture
def lancer(tmp_path_factory):
    """Rend un `AppTest` déroulé avec la query string voulue, sans toucher au disque réel.

    Même précaution que `test_dashboard_app.py` : le formulaire d'expérience et les filtres
    du registre se retiennent dans des fichiers, que le harnais ne doit ni lire ni écraser.
    """
    sys.path.insert(0, str(RACINE))
    from scripts.dashboard import experiences

    origine, origine_vue = experiences.ETAT_FORMULAIRE, experiences.ETAT_VUE_REGISTRE
    experiences.ETAT_FORMULAIRE = tmp_path_factory.mktemp("brouillon") / "formulaire.yaml"
    experiences.ETAT_VUE_REGISTRE = tmp_path_factory.mktemp("vue") / "tableau.yaml"

    def _lancer(onglet: str | None, ouvert: str | None = None) -> AppTest:
        at = AppTest.from_file(str(APP), default_timeout=240)
        if onglet is not None:
            at.query_params["onglet"] = onglet
        if ouvert is not None:  # ce que le navigateur renvoie quand l'utilisateur a cliqué
            at.session_state["onglet_actif"] = ouvert
        at.run()
        assert not at.exception, "\n".join(str(e.value) for e in at.exception)
        return at

    yield _lancer
    experiences.ETAT_FORMULAIRE = origine
    experiences.ETAT_VUE_REGISTRE = origine_vue


@pytest.mark.parametrize(
    "slug, libelle",
    [("tickets", "🎫 Tickets"), ("experiences", "🧪 Expériences"), ("vue", "🏠 Vue d'ensemble")],
)
def test_l_url_ouvre_l_onglet_qu_elle_nomme(lancer, slug, libelle):
    assert lancer(slug).session_state["onglet_actif"] == libelle


@pytest.mark.parametrize("onglet", [None, "nimportequoi", ""])
def test_sans_slug_utilisable_la_page_revient_a_l_accueil(lancer, onglet):
    """Une URL absente, vide ou trafiquée n'est pas une erreur : c'est l'accueil."""
    assert lancer(onglet).session_state["onglet_actif"] == "🏠 Vue d'ensemble"


def test_les_slugs_couvrent_tous_les_onglets_dessines(lancer):
    """Aucun onglet ne doit rester sans slug : il serait impossible d'y revenir par l'URL."""
    at = lancer(None)
    libelles_dessines = [t.label for t in at.tabs]
    # La table ONGLETS vit dans app.py, qu'un test ne peut pas importer (le module EST le
    # script Streamlit) : elle est recopiée ici, et c'est le point : l'oubli se voit.
    slugs = {
        "🏠 Vue d'ensemble": "vue", "🎮 Run GAMA": "run", "🤖 Providers": "providers",
        "🧬 Calibration": "calibration", "📟 Activités en cours": "activites",
        "🎫 Tickets": "tickets", "📊 Métriques": "metriques",
        "🧪 Expériences": "experiences", "🗂️ Mes travaux": "travaux",
    }
    assert set(libelles_dessines) == set(slugs), (
        "un onglet a été ajouté ou renommé sans mettre à jour la table ONGLETS de app.py "
        f"(dessinés : {libelles_dessines})"
    )


def test_l_onglet_ouvert_se_recopie_dans_l_url(lancer):
    """Le clic sur un onglet met l'URL à jour : sans ça, il n'y aurait rien à recharger."""
    at = lancer(None, ouvert="📊 Métriques")
    assert slug_dans_l_url(at) == "metriques"


def test_l_url_perimee_est_corrigee_par_l_onglet_reellement_ouvert(lancer):
    """L'URL suit l'onglet, jamais l'inverse : c'est l'état de la page qui fait foi."""
    at = lancer("vue", ouvert="🎫 Tickets")
    assert slug_dans_l_url(at) == "tickets"
