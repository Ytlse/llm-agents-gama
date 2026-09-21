"""Ticket 077, lot K — un réglage d'expérience appartient au run, et le run le dit.

Contrat : `specs/ticket_077/tests.md`, section K.

Le 18 septembre, quatre réglages d'expérience ont été posés dans `config/config.yaml`. Ils sont
devenus le défaut du dépôt — trente tests rouges depuis — et ils ne figuraient nulle part dans
`identite_run.json` : trois bras aux réglages opposés portaient la même identité.
"""

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from urban_mobility_agents.utils import identite_run as I

RACINE = Path(__file__).resolve().parents[1]
CONFIG = RACINE / "config" / "config.yaml"
COHORTE = RACINE.parents[1] / "scripts" / "experiment" / "run_sequential_cohort.py"

# Ce qu'un bras d'expérience fait varier. Retiré de `config.yaml` (K1), posé par
# l'environnement (K7), enregistré dans l'identité du run (K2).
REGLAGES_D_EXPERIENCE = (
    "vehicle_chain_enabled",
    "vehicle_return_home_lock",
    "mode_choice_truncation_threshold",
    "stm_reflection_min_entries",
)


def _reglages(**s):
    base = {
        "chaine": True,
        "verrou": True,
        "troncature": 0.0,
        "seuil_choc": 0.7,
        "fenetre": 14,
        "changements_max": 3,
        "reflexion_min": 10,
        "meteo_par_agent": True,
    }
    base.update(s)
    return SimpleNamespace(
        llm=SimpleNamespace(instances_admises=[], providers={}),
        agent=SimpleNamespace(
            llm_params={"prompt_variant": "prompt_expert_05"},
            long_term_memory_enabled=True,
            long_term_self_reflect_enabled=True,
            mode_draw_seed=42,
            option_order_seed=42,
            weather_draw_seed=42,
            vehicle_chain_enabled=base["chaine"],
            vehicle_return_home_lock=base["verrou"],
            mode_choice_truncation_threshold=base["troncature"],
            memoire__importance_choc=base["seuil_choc"],
            memoire__fenetre_changements_jours=base["fenetre"],
            memoire__changements_max=base["changements_max"],
            stm_reflection_min_entries=base["reflexion_min"],
            weather_per_agent_dates=base["meteo_par_agent"],
        ),
        data=SimpleNamespace(population_file="/data/p.json"),
        cache=SimpleNamespace(enabled=False),
    )


# ══════════════════════ K1 — hors de la configuration du dépôt ══════════════════


def test_K1_config_yaml_ne_declare_aucun_reglage_d_experience():
    """K1 — posés là, ils deviennent la norme du dépôt sans que personne ne l'ait décidé."""
    agent = (yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}).get("agent") or {}
    fautifs = sorted(set(agent) & set(REGLAGES_D_EXPERIENCE))
    assert not fautifs, (
        "config.yaml déclare des réglages d'expérience : "
        + ", ".join(fautifs)
        + " — à passer par l'environnement, où le run les enregistre dans son identité."
    )


# ══════════════════════ K2 à K6 — l'identité les porte ══════════════════════════


def test_K2_l_identite_porte_les_reglages_d_experience():
    """K2 — sans eux, trois bras d'expérience portent la même identité."""
    ident = I.composer(_reglages())
    for champ in (
        "chaine_vehicules",
        "verrou_retour_domicile",
        "seuil_troncature",
        "seuil_choc",
        "fenetre_changements_jours",
        "changements_max",
        "reflexion_stm_min_entrees",
        "meteo_par_agent",
    ):
        assert champ in ident, f"l'identité du run ne porte pas {champ}"


def test_K3_le_seuil_de_troncature_separe_deux_runs():
    """K3 — il change la loi de tirage : deux runs qui en diffèrent ne sont pas comparables."""
    ecarts = I.differences(I.composer(_reglages()), I.composer(_reglages(troncature=0.15)))
    assert len(ecarts) == 1
    assert "troncature" in ecarts[0]


def test_K4_la_fenetre_de_changements_separe_deux_runs():
    """K4 — c'est le paramètre du bras d'ablation : il ne doit pas pouvoir passer inaperçu."""
    ecarts = I.differences(I.composer(_reglages()), I.composer(_reglages(fenetre=7)))
    assert len(ecarts) == 1
    assert "fenêtre" in ecarts[0].lower()


def test_K5_un_champ_absent_est_dit_absent(tmp_path):
    """K5 — un run d'avant le 2026-09-19 est irreprenable, et la raison est son ÂGE."""
    ancienne = {k: v for k, v in I.composer(_reglages()).items() if k != "seuil_troncature"}
    I.ecrire(tmp_path, ancienne)
    with pytest.raises(I.IdentiteIncompatible) as exc:
        I.verifier(tmp_path, I.composer(_reglages()))
    assert "absent du run repris" in str(exc.value)


def test_K6_les_defauts_de_l_identite_sont_ceux_du_depot():
    """K6 — un run nominal ne doit jamais se croire différent de lui-même."""
    from settings import settings

    ident = I.composer(settings)
    assert ident["chaine_vehicules"] == bool(settings.agent.vehicle_chain_enabled)
    assert ident["seuil_choc"] == pytest.approx(float(settings.agent.memoire__importance_choc))
    assert ident["fenetre_changements_jours"] == int(
        settings.agent.memoire__fenetre_changements_jours
    )


# ══════════════════════ K7 — la campagne les pose ═══════════════════════════════


def test_K7_la_cohorte_pose_tous_les_reglages_par_l_environnement():
    """K7 — sinon la campagne tourne aux défauts du dépôt sans que rien ne le dise."""
    if not COHORTE.is_file():
        pytest.skip("scripts/experiment/run_sequential_cohort.py absent")
    source = COHORTE.read_text(encoding="utf-8")
    for reglage in REGLAGES_D_EXPERIENCE:
        # ⚠ NOM NU. Cette règle a d'abord été écrite avec un préfixe `AGENT__`, par analogie
        # avec d'autres dépôts — et elle passait, parce que la cohorte posait la même forme
        # fausse. Les sous-configurations de `settings.py` sont des `BaseSettings` SANS
        # préfixe : seul `VEHICLE_CHAIN_ENABLED` est lu. Vérifié à l'exécution le 2026-09-19,
        # après un bras entier tourné aux valeurs par défaut (cf. lot L).
        attendu = reglage.upper()
        assert re.search(rf'"{attendu}"', source) or f'"{attendu}"' in source, (
            f"{attendu} n'est pas posé par la cohorte : retiré de config.yaml et non remplacé, "
            f"ce réglage reprendrait sa valeur par défaut au prochain run."
        )
        actives = [
            l for l in source.splitlines()
            if f"AGENT__{attendu}" in l and not l.strip().startswith("#")
        ]
        assert not actives, (
            f"AGENT__{attendu} encore posé : ce préfixe n'est lu par personne dans ce dépôt.\n"
            + "\n".join(actives)
        )


# ══════════════════════ K8 à K10 — la campagne sépare vraiment ses bras ═════════


def _source_cohorte() -> str:
    if not COHORTE.is_file():
        pytest.skip("scripts/experiment/run_sequential_cohort.py absent")
    return COHORTE.read_text(encoding="utf-8")


def test_K8_la_campagne_declare_un_choc_par_branche():
    """K8 — sans `CHOC=`, `make run` garde la déclaration de config.yaml et le témoin est traité."""
    source = _source_cohorte()
    assert 'f"CHOC={choc}"' in source or "CHOC=" in source, (
        "la commande de la campagne ne porte aucun CHOC= : la branche témoin tournerait avec "
        "le choc déclaré dans config.yaml"
    )
    assert '"treated"' in source and 'else "0"' in source, (
        "les deux branches ne se séparent pas explicitement sur le choc"
    )


def test_K9_le_texte_du_choc_n_est_pas_recopie_dans_le_lanceur():
    """K9 — une copie diverge du fichier testé ; c'est arrivé, et le lot H n'atteignait pas la campagne."""
    source = _source_cohorte()
    assert "CHOC_TEMPLATE" not in source, "le lanceur porte encore sa propre copie du choc"
    assert "CHOC_REFERENCE" in source, "le lanceur ne dérive pas le choc du fichier de référence"
    for mot in ("grinding", "rattling", "Warning lights", "vecu:"):
        assert mot not in source, f"texte de choc recopié dans le lanceur : « {mot} »"


def test_K10_la_campagne_coupe_le_cache():
    """K10 — la clé du cache ne porte aucune durée : une décision d'avant le choc serait resservie."""
    assert "CACHE=0" in _source_cohorte()
