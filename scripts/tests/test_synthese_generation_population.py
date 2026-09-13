"""La page « Comment la population est fabriquée » se construit depuis le sceau versionné, sans
les traces (absentes d'un clone) : les sections manquantes le disent au lieu d'inventer."""
from pathlib import Path

from scripts.AAMAS.synthese_generation_population import build, TEMPLATE_V2, CONFIG_EQASIM, COMMUNES, GRAPHE_META

REPO = Path(__file__).resolve().parents[2]
SCEAU = REPO / "data" / "population" / "population_1000_AAMAS_v4"


def test_la_page_se_construit_depuis_le_sceau_seul():
    html = build(SCEAU, None, None, None, None, CONFIG_EQASIM, COMMUNES,
                 GRAPHE_META if GRAPHE_META.exists() else None, None, TEMPLATE_V2, "synthese.html")
    assert "<title>Fabrication de la population v4</title>" in html
    # Chiffres lus dans le MANIFEST, jamais saisis
    assert "11 329" in html and "513" in html and "aamas_seal_v4" in html
    assert "9f05c655c3ad2cf4" in html
    # Ce qui n'est pas fourni est dit tel quel
    assert "rapport non fourni" in html and "audit non fourni" in html
    # Les chiffres du journal sont marqués
    assert "<sup class='j'" in html
