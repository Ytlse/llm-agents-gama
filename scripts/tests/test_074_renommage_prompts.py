"""Ticket 074, C-4/C-5 — les noms de variantes disent la famille, et les anciens restent lisibles.

Deux propriétés, et la seconde est celle qui coûte cher si elle tombe.

**C-4 — le nom porte la famille et la place dans la série.** Les 22 noms mélangeaient quatre
conventions (`prompt_optimise_v5`, `expert_chaine_m7`, `b_min`, `b0_pristine`, `persona_v3`,
`expert`) : aucune ne disait la famille, et la famille est ce qui détermine quelle grille
d'audit s'applique. Schéma unique : `prompt_<famille>_<nn>`, numéroté dans l'ordre de la
GÉNÉALOGIE (`derive_de`) et non de l'alphabet.

**C-5 — un ancien nom se résout encore en LECTURE.** Les définitions d'expériences archivées
portent `variante: expert_gem_3.8_v2` et ne seront jamais réécrites : l'archive est froide. Sans
résolution, recalculer l'empreinte d'une exécution passée devient impossible — or c'est
précisément ce qu'un renommage ne doit pas casser (`empreinte_gabarit` appelle
`get_system_prompt(..., verifier_validite=False)`).

Lancement :
    services/llm-agents/.venv/bin/python -m pytest scripts/tests/test_074_renommage_prompts.py -q
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "services" / "llm-agents"))
sys.path.insert(0, str(RACINE / "packages" / "llm_gateway" / "src"))
sys.path.insert(0, str(RACINE / "packages" / "mobility_llm" / "src"))

from llm_gateway.prompts.engine import PromptManager  # noqa: E402
from mobility_llm.prompts import CATEGORIES_DIR, PROMPTS_FILE  # noqa: E402

NOM_CANONIQUE = re.compile(r"^prompt_(minimal|expert)_\d{2}$")


@pytest.fixture(scope="module")
def store() -> dict:
    return yaml.safe_load(PROMPTS_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pm() -> PromptManager:
    return PromptManager(
        templates_dir=CATEGORIES_DIR,
        prompts_file=PROMPTS_FILE,
        template_names={"itinary_multi_agent": "itinary_multi_agent/template.md.j2"},
        schema_paths={"itinary_multi_agent": CATEGORIES_DIR / "itinary_multi_agent"
                      / "output_schema.json"},
    )


# ── C-4 : le schéma de nommage ────────────────────────────────────────────────────────────


def test_toutes_les_variantes_portent_un_nom_canonique(store: dict) -> None:
    fautifs = [n for n in store["prompts"] if not NOM_CANONIQUE.match(n)]
    assert not fautifs, f"noms hors schéma `prompt_<famille>_<nn>` : {fautifs}"


def test_le_segment_de_nom_dit_la_FAMILLE_reellement_declaree(store: dict) -> None:
    """Un nom qui contredit la famille est pire que pas de nom du tout.

    C'est le défaut que C-4 corrige : `b_min` se lisait comme un prompt minimal alors qu'il
    relève de la famille experte depuis le 2026-09-10, et l'auditeur qui l'aurait cru sur parole
    lui aurait appliqué M1-M4 — donc rendu un verdict faux.
    """
    declarees = store["familles"]
    for nom, entree in store["prompts"].items():
        propre = entree.get("famille") or (entree.get("_neutralite") or {}).get("famille")
        famille = str(propre or ("minimale" if nom in (declarees.get("minimale") or [])
                                 else declarees.get("defaut", "experte")))
        attendu = {"minimale": "minimal", "experte": "expert"}[famille]
        assert nom.startswith(f"prompt_{attendu}_"), (
            f"{nom} est de famille {famille!r} mais son nom annonce l'autre"
        )


def test_les_references_internes_suivent_le_renommage(store: dict) -> None:
    """`active`, `familles.minimale`, `derive_de`, `remplace_par` pointent des noms qui existent."""
    noms = set(store["prompts"])
    assert store["active"]["itinary_multi_agent"] in noms
    for n in store["familles"]["minimale"]:
        assert n in noms, f"familles.minimale cite {n!r}, absent de prompts:"
    for nom, entree in store["prompts"].items():
        for chemin, valeur in (
            ("_provenance.derive_de", (entree.get("_provenance") or {}).get("derive_de")),
            ("derive_de", entree.get("derive_de")),
            ("_calibration.seed", (entree.get("_calibration") or {}).get("seed")),
            ("_invalidation.remplace_par",
             (entree.get("_invalidation") or {}).get("remplace_par")),
        ):
            if valeur:
                assert valeur in noms, f"{nom}.{chemin} = {valeur!r}, absent de prompts:"


def test_la_numerotation_suit_la_genealogie(store: dict) -> None:
    """Un enfant porte un numéro PLUS GRAND que son parent, dans la même famille.

    C'est ce qui rend la série lisible : `prompt_expert_05` dérive de `prompt_expert_04`. Un tri
    alphabétique ou par date aurait dispersé les lignées — les cinq `persona_*` portaient toutes
    la date de leur archivage, pas de leur écriture.
    """
    def numero(n: str) -> int:
        return int(n.rsplit("_", 1)[1])

    for nom, entree in store["prompts"].items():
        parent = (entree.get("_provenance") or {}).get("derive_de")
        if not parent or parent not in store["prompts"]:
            continue
        if nom.split("_")[1] != parent.split("_")[1]:
            continue  # changement de famille : la comparaison n'a pas de sens
        assert numero(nom) > numero(parent), (
            f"{nom} dérive de {parent} mais porte un numéro inférieur"
        )


# ── C-5 : les anciens noms restent résolubles ─────────────────────────────────────────────


def test_chaque_variante_garde_son_ancien_nom(store: dict) -> None:
    sans = [n for n, e in store["prompts"].items() if not e.get("_ancien_nom")]
    assert not sans, f"variantes sans `_ancien_nom` : {sans}"
    anciens = [e["_ancien_nom"] for e in store["prompts"].values()]
    assert len(anciens) == len(set(anciens)), "deux variantes revendiquent le même ancien nom"


# `expert_gem_3.8_v2` a quitté cette liste le 2026-09-17 : la variante qu'il nommait
# (`prompt_expert_04`) a été SUPPRIMÉE du fichier à la demande de l'auteur. Conséquence
# assumée, et c'est la raison d'être de ce test : les deux expériences archivées qui la
# désignent ne se rejouent plus. Son texte reste lisible dans l'archive froide du 2026-09-14
# et dans l'historique git, mais plus par le `PromptManager`.
@pytest.mark.parametrize("ancien", [
    "prompt_minimal", "expert_gem_3.8_v2_neutre_justif",
    "expert_gem_3.8_v3", "prompt_optimise_v4", "expert_m4",
])
def test_les_variantes_de_la_campagne_se_relisent_par_leur_ancien_nom(
    pm: PromptManager, ancien: str
) -> None:
    """Les 5 variantes que désignent les 10 expériences à rejouer, plus l'active.

    `verifier_validite=False` : c'est le chemin d'`empreinte_gabarit`, qui doit rester
    reproductible même sur une variante invalidée.
    """
    texte = pm.get_system_prompt("itinary_multi_agent", ancien, verifier_validite=False)
    assert texte and len(texte) > 100, f"{ancien} ne se relit pas par son ancien nom"


def test_un_nom_vraiment_inconnu_est_refuse_et_le_message_liste_les_deux_jeux(
    pm: PromptManager,
) -> None:
    """Résoudre en silence serait pire que refuser : le prochain run écrirait le mauvais nom."""
    with pytest.raises(ValueError) as e:
        pm.get_system_prompt("itinary_multi_agent", "variante_qui_n_existe_pas")
    message = str(e.value)
    assert "prompt_expert_01" in message, "le refus doit lister les noms canoniques"
    assert "anciens noms résolus" in message, "le refus doit dire que les anciens noms existent"


def test_la_resolution_d_un_ancien_nom_avertit(pm: PromptManager) -> None:
    """L'avertissement nomme le canonique — sans lui, l'ancien nom se reconduirait de trace en trace.

    Le puits loguru est posé à la main plutôt que de passer par `caplog` : le gateway journalise
    via loguru, qui n'alimente pas le `logging` standard de pytest. Avec `caplog`, ce test serait
    passé au vert en ne capturant rien — l'avertissement pourrait disparaître sans que rien ne
    tombe.
    """
    from loguru import logger

    recu: list[str] = []
    puits = logger.add(recu.append, level="WARNING", format="{message}")
    try:
        pm.get_system_prompt("itinary_multi_agent", "expert_m4", verifier_validite=False)
    finally:
        logger.remove(puits)
    assert any("prompt_expert_16" in m for m in recu), (
        f"la résolution d'un ancien nom doit avertir en nommant le nom canonique ; reçu : {recu}"
    )


# ── Ce que le renommage répare, et qu'on ne voyait pas ────────────────────────────────────


def test_le_renommage_leve_une_collision_d_abreviation(store: dict) -> None:
    """Deux prompts DIFFÉRENTS s'abrégeaient pareil dans le nom des expériences.

    `expert_gem_3.8_v2` et `expert_gem_3.8_v2_neutre_justif` donnaient tous deux `expgem38v2` :
    deux expériences portaient donc le même segment de variante, distinguées par un simple
    indice `_2` qui ne disait pas ce qui changeait. Le nom d'une expérience EST son identité —
    une collision y est un défaut de mesure, pas de cosmétique.
    """
    from experiences.nommage import abreger_variante

    abrege: dict[str, list[str]] = {}
    for nom in store["prompts"]:
        abrege.setdefault(abreger_variante(nom), []).append(nom)
    collisions = {a: v for a, v in abrege.items() if len(v) > 1}
    assert not collisions, f"abréviations en collision après renommage : {collisions}"

    # Et la collision existait bien AVANT — sinon ce test ne garde rien. Le couple est écrit
    # EN DUR depuis le 2026-09-17 : `prompt_expert_04`, qui portait `expert_gem_3.8_v2`, a été
    # supprimé du fichier, si bien que la collision n'est plus dérivable des `_ancien_nom`
    # vivants. Le fait historique, lui, n'a pas bougé — et c'est lui que ce test verrouille.
    couple_historique = ("expert_gem_3.8_v2", "expert_gem_3.8_v2_neutre_justif")
    assert abreger_variante(couple_historique[0]) == abreger_variante(couple_historique[1]), (
        "les deux anciens noms ne collisionnent plus : ce test ne verrouille rien"
    )
