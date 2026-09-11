"""Écriture du statut d'un ticket depuis le tableau de bord (spec R9 à R16).

Ce qui est vérifié ici tient à une chose : `tickets_status.yaml` porte 1 470 lignes de
notes écrites à la main, et l'interface doit pouvoir changer UNE entrée sans que le
reste bouge d'un octet. Les tests travaillent sur une copie du vrai fichier — pas sur
un fragment inventé — parce que c'est son style réel (blocs repliés, commentaires,
accents) qui met l'écriture en défaut.
"""

from pathlib import Path

import pytest

pytest.importorskip("ruamel.yaml")

import sys

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.dashboard import tickets  # noqa: E402

REEL = Path(tickets.OVERRIDES_PATH)


@pytest.fixture(autouse=True)
def dossier_tickets(tmp_path, monkeypatch) -> Path:
    """Les stems réels, plus `ticket_099_essai` : l'écriture refuse une clé sans ticket."""
    dossier = tmp_path / "tickets"
    dossier.mkdir()
    reels = {p.stem for p in Path(tickets.TICKETS_DIR).glob("ticket_*.md")}
    for stem in reels | {"ticket_099_essai"}:
        (dossier / f"{stem}.md").write_text(f"# {stem}\n", encoding="utf-8")
    monkeypatch.setattr(tickets, "TICKETS_DIR", dossier)
    return dossier


@pytest.fixture
def fichier(tmp_path) -> Path:
    copie = tmp_path / "tickets_status.yaml"
    copie.write_text(REEL.read_text(encoding="utf-8"), encoding="utf-8")
    return copie


def _lignes(p: Path) -> list[str]:
    return p.read_text(encoding="utf-8").splitlines()


def test_R9_le_statut_choisi_est_ecrit(fichier):
    assert tickets.save_override("ticket_011_arrivees_perdues_gama", tickets.DONE, path=fichier) is True
    import yaml as pyyaml
    data = pyyaml.safe_load(fichier.read_text(encoding="utf-8"))["tickets"]
    assert data["ticket_011_arrivees_perdues_gama"]["status"] == tickets.DONE


def test_R10_rien_d_autre_que_l_entree_visee_ne_bouge(fichier):
    avant = _lignes(fichier)
    tickets.save_override("ticket_011_arrivees_perdues_gama", tickets.DONE, path=fichier)
    apres = _lignes(fichier)

    assert len(avant) == len(apres), "le nombre de lignes a changé : une autre entrée a été réécrite"
    differentes = [i for i, (a, b) in enumerate(zip(avant, apres)) if a != b]
    assert len(differentes) == 1, f"lignes modifiées : {differentes}"
    assert apres[differentes[0]].strip() == f"status: {tickets.DONE}"


def test_R10_les_commentaires_d_entete_survivent(fichier):
    tickets.save_override("ticket_011_arrivees_perdues_gama", tickets.DOING, path=fichier)
    texte = fichier.read_text(encoding="utf-8")
    assert texte.startswith("# Statut des tickets de `docs/tickets/` — SOURCE DE VÉRITÉ.")
    assert "⚠ Ne pas utiliser la forme courte" in texte


def test_R11_un_ticket_sans_entree_en_recoit_une_avec_la_cle_complete(fichier):
    import yaml as pyyaml

    assert tickets.save_override("ticket_099_essai", tickets.DOING, path=fichier) is True
    data = pyyaml.safe_load(fichier.read_text(encoding="utf-8"))["tickets"]
    assert data["ticket_099_essai"]["status"] == tickets.DOING
    assert "ticket_099" not in data, "la forme courte appliquerait un seul statut à deux tickets"
    assert list(data)[-1] == "ticket_099_essai", "la nouvelle entrée doit aller en fin de liste"


def test_R12_le_statut_ecrit_est_relu_comme_surcharge(fichier, monkeypatch):
    monkeypatch.setattr(tickets, "OVERRIDES_PATH", fichier)
    tickets.save_override("ticket_011_arrivees_perdues_gama", tickets.DONE, path=fichier)
    items = {t.path.stem: t for t in tickets.load_tickets()}
    lu = items["ticket_011_arrivees_perdues_gama"]
    assert (lu.status, lu.status_source) == (tickets.DONE, "surcharge")


def test_R13_enregistrer_sans_changement_n_ecrit_pas(fichier):
    import yaml as pyyaml

    entree = pyyaml.safe_load(fichier.read_text(encoding="utf-8"))["tickets"]["ticket_011_arrivees_perdues_gama"]
    empreinte = fichier.stat().st_mtime_ns

    change = tickets.save_override(
        "ticket_011_arrivees_perdues_gama", entree["status"], entree.get("note", ""), path=fichier
    )
    assert change is False
    assert fichier.stat().st_mtime_ns == empreinte, "le fichier a été réécrit à l'identique"


def test_R14_une_edition_manuelle_faite_entre_temps_est_conservee(fichier):
    import yaml as pyyaml

    # quelqu'un édite une AUTRE entrée à la main pendant que le tiroir du 011 est ouvert
    texte = fichier.read_text(encoding="utf-8").replace(
        "  ticket_002_snapshot_plan_24h:\n    status: abandonné",
        "  ticket_002_snapshot_plan_24h:\n    status: en veille",
    )
    fichier.write_text(texte, encoding="utf-8")

    tickets.save_override("ticket_011_arrivees_perdues_gama", tickets.DONE, path=fichier)
    data = pyyaml.safe_load(fichier.read_text(encoding="utf-8"))["tickets"]
    assert data["ticket_002_snapshot_plan_24h"]["status"] == "en veille"
    assert data["ticket_011_arrivees_perdues_gama"]["status"] == tickets.DONE


def test_R15_une_note_videe_retire_la_cle(fichier):
    import yaml as pyyaml

    tickets.save_override("ticket_011_arrivees_perdues_gama", tickets.DONE, "", path=fichier)  # note vidée
    entree = pyyaml.safe_load(fichier.read_text(encoding="utf-8"))["tickets"]["ticket_011_arrivees_perdues_gama"]
    assert "note" not in entree


def test_R15_une_note_neuve_est_un_bloc_replie(fichier):
    import yaml as pyyaml

    note = ("La cause amont n'est pas comprise et l'accusé de réception n'est pas écrit : les arrivées "
            "perdues restent visibles dans le journal de mouvements, mais rien ne dit encore lequel des "
            "deux bouts de la chaîne les perd.")
    tickets.save_override("ticket_011_arrivees_perdues_gama", tickets.DOING, note, path=fichier)

    texte = fichier.read_text(encoding="utf-8")
    bloc = texte.split("  ticket_011_arrivees_perdues_gama:\n", 1)[1].split("\n  ticket_", 1)[0].splitlines()
    assert "    note: >-" in bloc, "la note doit être écrite en bloc replié, comme les autres"
    lignes_note = bloc[bloc.index("    note: >-") + 1:]
    assert len(lignes_note) > 1, "une note longue doit être repliée, pas posée sur une seule ligne"
    assert max(len(l) for l in lignes_note) <= 100, f"ligne trop longue : {max(len(l) for l in lignes_note)}"
    relu = pyyaml.safe_load(texte)["tickets"]["ticket_011_arrivees_perdues_gama"]["note"]
    assert relu == note, "le repli ne doit pas altérer le texte"


def test_R15_les_paragraphes_sont_conserves(fichier):
    import yaml as pyyaml

    tickets.save_override("ticket_099_essai", tickets.DOING, "premier paragraphe\n\nsecond paragraphe", path=fichier)
    relu = pyyaml.safe_load(fichier.read_text(encoding="utf-8"))["tickets"]["ticket_099_essai"]["note"]
    assert relu == "premier paragraphe\n\nsecond paragraphe", "la ligne vide sépare deux paragraphes"


def test_R16_le_vocabulaire_propose_est_ferme_et_sans_sans_statut():
    assert tickets.UNKNOWN not in tickets.EDITABLE_STATUSES
    assert set(tickets.EDITABLE_STATUSES) == set(tickets.STATUS_ICON) - {tickets.UNKNOWN}


def test_R16_un_statut_hors_vocabulaire_est_refuse(fichier):
    empreinte = fichier.stat().st_mtime_ns
    with pytest.raises(ValueError, match="statut inconnu"):
        tickets.save_override("ticket_011_arrivees_perdues_gama", "presque fini", path=fichier)
    assert fichier.stat().st_mtime_ns == empreinte



def test_R10_changer_le_statut_seul_n_efface_pas_la_note(fichier):
    import yaml as pyyaml

    avant = pyyaml.safe_load(fichier.read_text(encoding="utf-8"))["tickets"]
    note_avant = avant["ticket_011_arrivees_perdues_gama"]["note"]
    tickets.save_override("ticket_011_arrivees_perdues_gama", tickets.DONE, path=fichier)
    apres = pyyaml.safe_load(fichier.read_text(encoding="utf-8"))["tickets"]
    assert apres["ticket_011_arrivees_perdues_gama"]["note"] == note_avant


def test_R15_les_espaces_multiples_d_un_paragraphe_sont_normalises(fichier):
    import yaml as pyyaml

    tickets.save_override("ticket_099_essai", tickets.DOING,
                          "deux   espaces\net un retour   à la ligne", path=fichier)
    relu = pyyaml.safe_load(fichier.read_text(encoding="utf-8"))["tickets"]["ticket_099_essai"]["note"]
    assert relu == "deux espaces et un retour à la ligne"


def test_R16_le_statut_preselectionne_est_celui_en_vigueur():
    assert tickets.statut_editable(tickets.DONE) == tickets.DONE
    assert tickets.statut_editable(tickets.PAUSED) == tickets.PAUSED
    # `sans statut` n'est pas une décision : le sélecteur part de `à faire`, et l'interface
    # doit dire que ce ticket n'a pas d'entrée (R25) pour ne pas faire passer ce défaut
    # pour un choix.
    assert tickets.statut_editable(tickets.UNKNOWN) == tickets.TODO
    assert tickets.statut_editable("statut inventé") == tickets.TODO


def test_R28_une_cle_courte_ou_fautive_est_refusee(monkeypatch, fichier):
    """Une clé courte appliquerait un seul statut à deux tickets ; une clé fautive à aucun."""
    stems = {p.stem for p in tickets.TICKETS_DIR.glob("ticket_*.md")}

    # Les clés RÉELLEMENT présentes dans le fichier, pas des clés fabriquées depuis les stems :
    # c'est la seule version de cette assertion qui puisse échouer.
    reelles = set(tickets._load_overrides())
    assert len(reelles) >= 38
    tickets._verifier_cles(dict.fromkeys(reelles, {}), stems)

    with pytest.raises(ValueError) as courte:
        tickets._verifier_cles({"ticket_005": {}}, stems)
    assert "ticket_005_choix_modal_probabiliste" in str(courte.value)
    assert "ticket_005_mode_choice_model" in str(courte.value)

    with pytest.raises(ValueError, match="aucun ticket"):
        tickets._verifier_cles({"ticket_faute_de_frappe": {}}, stems)


def test_R28_la_forme_courte_n_est_plus_resolue_a_la_lecture(fichier):
    """Le lecteur ne doit pas honorer ce que l'écriture interdit."""
    source = Path(tickets.__file__).read_text(encoding="utf-8")
    assert 'overrides.get(f"ticket_{number}")' not in source
    assert "override = overrides.get(path.stem) or {}" in source


def test_R27_une_note_modifiee_gagne_sur_le_fichier(fichier):
    """Intention explicite : le texte saisi est écrit, même si le fichier a bougé entre-temps."""
    import yaml as pyyaml

    # le fichier change sous nos pieds
    texte = fichier.read_text(encoding="utf-8").replace(
        "  ticket_002_snapshot_plan_24h:\n    status: abandonné",
        "  ticket_002_snapshot_plan_24h:\n    status: en veille")
    fichier.write_text(texte, encoding="utf-8")

    assert tickets.save_override("ticket_011_arrivees_perdues_gama", tickets.DOING,
                                 "ce que l'utilisateur a tapé", path=fichier) is True
    entrees = pyyaml.safe_load(fichier.read_text(encoding="utf-8"))["tickets"]
    assert entrees["ticket_011_arrivees_perdues_gama"]["note"] == "ce que l'utilisateur a tapé"
    assert entrees["ticket_002_snapshot_plan_24h"]["status"] == "en veille", "l'autre entrée survit"


def test_le_chemin_par_defaut_est_resolu_a_l_appel(monkeypatch, tmp_path):
    """Lié à l'import, il ignorait une redirection en test et écrivait dans le vrai fichier."""
    copie = tmp_path / "redirige.yaml"
    copie.write_text(REEL.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(tickets, "OVERRIDES_PATH", copie)

    empreinte_reelle = REEL.stat().st_mtime_ns
    assert tickets.save_override("ticket_011_arrivees_perdues_gama", tickets.DONE) is True
    assert REEL.stat().st_mtime_ns == empreinte_reelle, "le vrai fichier ne doit pas être touché"
    assert "status: terminé" in copie.read_text(encoding="utf-8")


def test_R23_un_statut_inconnu_dans_le_fichier_est_refuse(monkeypatch, fichier):
    """La moitié productrice de R23 : sans ce refus, un statut faux passerait inaperçu.

    Le cas s'est produit : au dernier commit, `ticket_030` portait `status: implémenté`, hors
    vocabulaire. Un repli silencieux aurait listé le ticket avec un statut déduit, faux.
    """
    texte = fichier.read_text(encoding="utf-8").replace(
        "  ticket_011_arrivees_perdues_gama:\n    status: à faire",
        "  ticket_011_arrivees_perdues_gama:\n    status: a faire", 1)
    fichier.write_text(texte, encoding="utf-8")
    monkeypatch.setattr(tickets, "OVERRIDES_PATH", fichier)

    with pytest.raises(ValueError) as refus:
        tickets.load_tickets()
    message = str(refus.value)
    assert "'a faire'" in message, message
    assert "ticket_011_arrivees_perdues_gama" in message
    for statut in tickets.EDITABLE_STATUSES:
        assert statut in message, f"la liste admise doit être rappelée ({statut} manque)"
    assert tickets.UNKNOWN not in message, "« sans statut » n'est pas une valeur qu'on puisse écrire"


def test_R28_l_ecriture_refuse_aussi_une_cle_qui_ne_designe_pas_un_ticket(fichier):
    """Ce que la lecture refuse, l'écriture doit le refuser : sinon on produit un fichier
    qui rend l'onglet Tickets entièrement illisible au prochain chargement."""
    empreinte = fichier.stat().st_mtime_ns
    with pytest.raises(tickets.CleInvalide) as courte:
        tickets.save_override("ticket_005", tickets.DOING, path=fichier)
    assert "ticket_005_choix_modal_probabiliste" in str(courte.value)
    assert "ticket_005_mode_choice_model" in str(courte.value)

    with pytest.raises(tickets.CleInvalide, match="aucun ticket"):
        tickets.save_override("ticket_inexistant", tickets.DOING, path=fichier)
    assert fichier.stat().st_mtime_ns == empreinte, "un refus ne doit rien écrire"


def test_R28_une_cle_courte_dans_le_fichier_est_refusee_a_la_lecture(monkeypatch, fichier):
    """L'intégration, pas seulement le vérificateur : `load_tickets` doit lever."""
    texte = fichier.read_text(encoding="utf-8").replace(
        "  ticket_011_arrivees_perdues_gama:", "  ticket_005:", 1)
    fichier.write_text(texte, encoding="utf-8")
    monkeypatch.setattr(tickets, "OVERRIDES_PATH", fichier)

    with pytest.raises(tickets.CleInvalide) as refus:
        tickets.load_tickets()
    assert "ticket_005_choix_modal_probabiliste" in str(refus.value)
    assert not isinstance(refus.value, tickets.StatutInconnu), \
        "une clé invalide ne doit pas être annoncée comme un statut inconnu"


def test_R27_une_retouche_d_espaces_seuls_n_ecrit_rien(fichier):
    """La comparaison doit porter sur le texte STOCKÉ, sinon un double espace produit un diff."""
    import yaml as pyyaml

    note = pyyaml.safe_load(fichier.read_text(encoding="utf-8"))["tickets"]["ticket_011_arrivees_perdues_gama"]["note"]
    empreinte = fichier.stat().st_mtime_ns

    assert tickets.save_override("ticket_011_arrivees_perdues_gama", tickets.TODO,
                                 note + "   ", path=fichier) is False
    assert tickets.save_override("ticket_011_arrivees_perdues_gama", tickets.TODO,
                                 note.replace(" ", "  ", 3), path=fichier) is False
    assert fichier.stat().st_mtime_ns == empreinte, "aucune écriture pour une retouche cosmétique"

    assert tickets.save_override("ticket_011_arrivees_perdues_gama", tickets.TODO,
                                 note + " et une phrase de plus.", path=fichier) is True
