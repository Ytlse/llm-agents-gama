"""La colonne « ticket » du registre dit ce qu'elle sait, et tait ce qu'elle ignore.

Le défaut qui compte ici n'est pas une erreur de calcul : c'est une case remplie **au jugé**.
Une colonne où l'on a mis « 088 » parce que le bras ressemblait aux autres est une colonne
qu'on ne peut plus croire, donc qu'on cesse de lire — et pire, dont on cite les valeurs. D'où
la forme des tests : chacun vérifie soit qu'une source réelle est trouvée, soit qu'en son
absence la case reste VIDE.

Trois sources, dans un ordre qui a une raison : un ticket qui écrit le nom exact d'un bras en
sait plus long que la campagne qui l'a exécuté, laquelle en sait plus long qu'une déduction
tirée du nom.

Lancement :
    services/llm-agents/.venv/bin/python -m pytest scripts/tests/test_dashboard_ticket_par_experience.py -q
"""

from __future__ import annotations

import os

import pytest

from scripts.dashboard import tickets_par_experience as M


@pytest.fixture
def depots(tmp_path, monkeypatch):
    """Un `docs/tickets/` et un `campagnes/` vierges, et un cache remis à zéro."""
    tickets = tmp_path / "tickets"
    campagnes = tmp_path / "campagnes"
    tickets.mkdir()
    campagnes.mkdir()
    monkeypatch.setattr(M, "TICKETS_DIR", tickets)
    monkeypatch.setattr(M, "CAMPAGNES_DIR", campagnes)
    M._CACHE.clear()
    return tickets, campagnes


def ticket(dossier, numero: str, corps: str) -> None:
    (dossier / f"ticket_{numero}_sujet.md").write_text(corps, encoding="utf-8")


def campagne(dossier, nom: str, numero: str | None, experiences: list[str]) -> None:
    entete = f"# Ticket {numero} — la campagne.\n" if numero else "# Une campagne sans ticket.\n"
    corps = entete + "nom: " + nom + "\nphases:\n- nom: phase\n  experiences:\n"
    corps += "".join(f"  - {e}\n" for e in experiences)
    (dossier / f"{nom}.yaml").write_text(corps, encoding="utf-8")


UN_BRAS = "exp_gemini-35-fl_proexp05_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_t0_nosim"


def test_un_ticket_qui_cite_le_nom_exact(depots):
    tickets, _ = depots
    ticket(tickets, "073", f"Le bras `{UN_BRAS}` sert de référence.")

    assert M.ticket_par_experience([UN_BRAS]) == {UN_BRAS: "073"}


def test_une_campagne_dont_l_entete_nomme_son_ticket(depots):
    _, campagnes = depots
    campagne(campagnes, "rejeu", "088", [UN_BRAS])

    assert M.ticket_par_experience([UN_BRAS]) == {UN_BRAS: "088"}


def test_la_citation_l_emporte_sur_la_campagne(depots):
    """Le ticket qui nomme le bras en sait plus que la campagne qui l'a fait tourner."""
    tickets, campagnes = depots
    ticket(tickets, "073", f"Réplicat de `{UN_BRAS}`.")
    campagne(campagnes, "rejeu", "088", [UN_BRAS])

    assert M.ticket_par_experience([UN_BRAS])[UN_BRAS] == "073"


def test_une_campagne_sans_ticket_dans_son_entete_est_ignoree(depots):
    _, campagnes = depots
    campagne(campagnes, "sans_ticket", None, [UN_BRAS])

    assert M.ticket_par_experience([UN_BRAS]) == {UN_BRAS: ""}


@pytest.mark.parametrize("graine", ["123", "456", "789", "2026"])
def test_les_quatre_graines_de_l_axe_1_se_deduisent(depots, graine):
    """Le nom porte la graine en clair, et le ticket 073 liste exactement ces quatre-là."""
    nom = f"exp_gemini-35-fl_proexp05_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_go{graine}_gt{graine}_gc{graine}_t0_nosim"

    assert M.ticket_par_experience([nom])[nom] == "073"


def test_une_graine_hors_liste_ne_se_deduit_pas(depots):
    """L'axe 1 ne nomme que quatre graines : une cinquième n'est pas de ce ticket."""
    nom = "exp_gemini-35-fl_proexp05_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_go7_gt7_gc7_t0_nosim"

    assert M.ticket_par_experience([nom])[nom] == ""


def test_un_replicat_se_deduit_quand_son_aine_existe(depots):
    """`_2` ne veut dire « réplicat » que s'il y a un aîné — sinon c'est un nom comme un autre."""
    r = M.ticket_par_experience([UN_BRAS, UN_BRAS + "_2"])

    assert r[UN_BRAS + "_2"] == "073"


def test_un_nom_en_2_sans_aine_reste_vide(depots):
    orphelin = "exp_un_bras_qui_finit_en_2"

    assert M.ticket_par_experience([orphelin])[orphelin] == ""


def test_le_substrat_qui_porte_le_numero_du_ticket(depots):
    nom = "exp_alea_jtir_pop-enquete_058_test_jeu-58_test_20260316_nosim"

    assert M.ticket_par_experience([nom])[nom] == "058"


def test_sans_aucune_source_la_case_reste_vide(depots):
    """La propriété qui fait la valeur de la colonne : on ne remplit pas au jugé."""
    inconnu = "exp_openai-go-12_proexp05_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_t0_nosim"

    assert M.ticket_par_experience([inconnu]) == {inconnu: ""}


def test_deux_tickets_pour_un_bras_sont_rendus_tous_les_deux(depots):
    """Un bras rejoué par un ticket et repris par un autre : les deux comptent."""
    tickets, _ = depots
    ticket(tickets, "088", f"Rejeu de `{UN_BRAS}`.")
    ticket(tickets, "073", f"Référence : `{UN_BRAS}`.")

    assert M.ticket_par_experience([UN_BRAS])[UN_BRAS] == "073,088"


def test_le_cache_se_rafraichit_quand_un_ticket_apparait(depots):
    """Sinon la colonne resterait fausse jusqu'au redémarrage du tableau de bord."""
    tickets, _ = depots
    assert M.ticket_par_experience([UN_BRAS])[UN_BRAS] == ""

    ticket(tickets, "073", f"Finalement, `{UN_BRAS}` est à nous.")
    os.utime(tickets, (0, 0))  # l'horloge du système de fichiers est trop grossière pour le test

    assert M.ticket_par_experience([UN_BRAS])[UN_BRAS] == "073"


def test_une_campagne_illisible_n_interrompt_pas_le_registre(depots):
    """Le tableau de bord doit se dessiner même si un fichier est cassé."""
    _, campagnes = depots
    (campagnes / "cassee.yaml").write_text(
        "# Ticket 088 — en-tête correct.\nphases: [ {oups\n", encoding="utf-8"
    )
    campagne(campagnes, "saine", "057", [UN_BRAS])

    assert M.ticket_par_experience([UN_BRAS])[UN_BRAS] == "057"


def test_liste_vide(depots):
    assert M.ticket_par_experience([]) == {}
