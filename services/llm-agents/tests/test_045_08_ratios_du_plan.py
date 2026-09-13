"""Ticket 045 — l'estimation de coût retrouve sa source de repli (question 3 du balayage).

Le fait. `ratios_du_plan()` cherchait le plan d'expériences dans
`docs/paper/experience_plan/experiments.yaml`, alors qu'il vit sous
`docs/paper/methode/experience_plan/`. Elle rendait donc **toujours `None`**, sur l'hôte comme
dans le conteneur, depuis que le dossier `methode/` a été introduit.

Pourquoi personne ne l'a vu, et pourquoi cela devient grave maintenant. C'est le **dernier**
repli d'une chaîne à trois maillons : jetons fournis à l'appel, sinon médiane des exécutions
archivées de même gabarit, sinon les ratios du plan. Tant que des exécutions archivées
existaient, le deuxième maillon répondait et le troisième n'était jamais atteint : le défaut
était latent et sans effet visible.

Le ticket 045 a vidé `data/experiences/`. Le deuxième maillon ne répond donc plus, et le
troisième est devenu le seul — or il était cassé. Résultat : « aucune mesure disponible »
pour tout bras payant, c'est-à-dire au moment précis où l'on décide de dépenser. Le défaut
latent est devenu actif du seul fait de l'archivage.

C'est le motif que ce ticket traque partout : **l'absence de mesure passe pour un cas sain**.
Un chemin introuvable rendait `None` en silence, indistinguable d'un plan sans ratios. Le
correctif fait deux choses : il vise le bon fichier, et un fichier introuvable se journalise.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from experiences.experience import CHEMIN_PLAN_EXPERIENCES, ratios_du_plan


def test_le_plan_dexperiences_existe_a_lendroit_ou_on_le_cherche():
    """Le défaut, en une ligne : le chemin codé ne désignait aucun fichier."""
    assert CHEMIN_PLAN_EXPERIENCES.is_file(), CHEMIN_PLAN_EXPERIENCES


def test_les_ratios_sont_lus_et_non_None():
    r = ratios_du_plan()
    assert r is not None, "le dernier repli de l'estimation de coût doit répondre"
    assert r["entree"] > 0 and r["sortie"] > 0


def test_les_ratios_sont_ceux_du_plan_pas_des_litteraux():
    """Aucun littéral d'estimation dans le code (règle E5) : la valeur vient du fichier."""
    data = yaml.safe_load(CHEMIN_PLAN_EXPERIENCES.read_text(encoding="utf-8")) or {}
    attendus = ((data.get("defaults") or {}).get("gateway_quotas_reference") or {}).get(
        "measured_ratios"
    )
    r = ratios_du_plan()
    assert r["entree"] == int(attendus["prompt_tokens_per_trip"])
    assert r["sortie"] == int(attendus["reply_tokens_per_trip"])


def test_la_source_citee_designe_le_fichier_lu():
    """Chaque valeur d'estimation cite sa source (E5) : encore faut-il que la source soit vraie."""
    r = ratios_du_plan()
    assert "experiments.yaml" in r["source"]
    assert "measured_ratios" in r["source"]


def test_un_plan_introuvable_se_journalise_au_lieu_de_se_taire(tmp_path, caplog):
    """Un `None` silencieux est indistinguable d'un plan sans ratios : il doit se dire."""
    from loguru import logger

    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(str(m)), level="WARNING")
    try:
        assert ratios_du_plan(tmp_path / "absent.yaml") is None
    finally:
        logger.remove(sink)
    assert any("absent.yaml" in m for m in messages), messages


def test_un_plan_sans_ratios_rend_None_sans_crier(tmp_path):
    """Un plan lisible mais sans ratios n'est pas une anomalie : il n'a rien à dire, c'est tout."""
    p = tmp_path / "plan.yaml"
    p.write_text(yaml.safe_dump({"defaults": {}}), encoding="utf-8")
    assert ratios_du_plan(p) is None


@pytest.mark.parametrize("racine", [Path("/"), Path("/app")])
def test_le_chemin_ne_depend_pas_dune_racine_devinee(racine):
    """Le chemin se résout depuis la racine du dépôt ancrée, jamais depuis `parents[N]`.

    Dans le conteneur `controller`, `parents[2]` valait `/` : le plan y était cherché sous
    `/docs/paper/…`. Même défaut de fond que l'empreinte de gabarit (A2).
    """
    assert not str(CHEMIN_PLAN_EXPERIENCES).startswith(str(racine / "docs"))
