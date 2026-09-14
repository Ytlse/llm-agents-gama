"""Écriture du statut d'un ticket depuis le tableau de bord (spec R9 à R16).

Ce qui est vérifié ici tient à une chose : `tickets_status.yaml` porte 1 470 lignes de
notes écrites à la main, et l'interface doit pouvoir changer UNE entrée sans que le
reste bouge d'un octet. Les tests travaillent sur une copie du vrai fichier — pas sur
un fragment inventé — parce que c'est son style réel (blocs repliés, commentaires,
accents) qui met l'écriture en défaut.
"""

import re
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


def _premiere_entree_notee(texte: str) -> tuple[str, str, str]:
    """La première entrée du fichier réel qui porte une note et un statut éditable.

    Rend `(clé, statut, note)` LUS dans le fichier. Viser un ticket nommément couplait le
    test à une valeur qui bouge : le 2026-09-12, le statut de `ticket_011` est passé de
    « à faire » à « abandonné », le remplacement littéral a cessé de mordre, et deux tests
    ont arrêté de vérifier quoi que ce soit. Ce qui est vérifié ici est la FORME du fichier
    et le comportement de `tickets.py`, pas l'avancement d'un chantier.
    """
    import yaml as pyyaml

    for cle, entree in (pyyaml.safe_load(texte)["tickets"] or {}).items():
        statut, note = entree.get("status"), entree.get("note")
        if note and statut in tickets.EDITABLE_STATUSES:
            return cle, statut, note
    pytest.fail("aucune entrée avec une note et un statut éditable dans tickets_status.yaml")


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


def test_R9_amelioration_s_ecrit_et_se_relit_comme_une_surcharge(fichier, monkeypatch):
    """`amélioration` n'est jamais DÉDUIT : seule une surcharge peut le poser.

    Un ticket conservé comme piste future n'a aucun signal textuel qui le trahisse — ses
    cases à cocher le donneraient `à faire`. Si l'aller-retour se perdait, le ticket
    retomberait silencieusement dans la file de travail.
    """
    import yaml as pyyaml

    monkeypatch.setattr(tickets, "OVERRIDES_PATH", fichier)
    assert tickets.save_override("ticket_099_essai", tickets.IMPROVEMENT, path=fichier) is True
    data = pyyaml.safe_load(fichier.read_text(encoding="utf-8"))["tickets"]
    assert data["ticket_099_essai"]["status"] == tickets.IMPROVEMENT

    relu = tickets.parse_ticket(tickets.TICKETS_DIR / "ticket_099_essai.md", tickets._load_overrides())
    assert (relu.status, relu.status_source) == (tickets.IMPROVEMENT, "surcharge")
    assert tickets.statut_editable(tickets.IMPROVEMENT) == tickets.IMPROVEMENT


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
    texte = fichier.read_text(encoding="utf-8")
    cle, en_vigueur, _ = _premiere_entree_notee(texte)
    # Le `count=1` + le `n == 1` sont le coeur du test : une substitution qui ne mord plus
    # vidait l'épreuve de son contenu SANS la faire rougir. Elle doit désormais échouer fort.
    casse, n = re.subn(rf"(^  {re.escape(cle)}:\n    status: ){re.escape(en_vigueur)}$",
                       lambda m: f"{m.group(1)}a faire", texte, count=1, flags=re.M)
    assert n == 1, f"le fichier n'a plus la forme attendue : « {cle} » puis « status: {en_vigueur} »"
    fichier.write_text(casse, encoding="utf-8")
    monkeypatch.setattr(tickets, "OVERRIDES_PATH", fichier)

    with pytest.raises(ValueError) as refus:
        tickets.load_tickets()
    message = str(refus.value)
    assert "'a faire'" in message, message
    assert cle in message
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
    # Le statut est celui EN VIGUEUR dans le fichier : seule la note doit varier, sinon le
    # test mesure deux changements à la fois et une écriture légitime le fait rougir.
    cle, statut, note = _premiere_entree_notee(fichier.read_text(encoding="utf-8"))
    empreinte = fichier.stat().st_mtime_ns

    assert tickets.save_override(cle, statut, note + "   ", path=fichier) is False
    assert tickets.save_override(cle, statut, note.replace(" ", "  ", 3), path=fichier) is False
    assert fichier.stat().st_mtime_ns == empreinte, "aucune écriture pour une retouche cosmétique"

    assert tickets.save_override(cle, statut, note + " et une phrase de plus.",
                                 path=fichier) is True


def test_description_extraite_depuis_markdown(tmp_path):
    """Vérifie l'extraction automatique de la description courte."""
    fichier_ticket = tmp_path / "tickets" / "ticket_099_essai.md"
    fichier_ticket.write_text(
        "# Ticket 099 — Titre d'essai\n\n"
        "> Une note de statut sous forme de citation.\n\n"
        "## Description\n\n"
        "Voici le [lien](http://example.com) vers la **description** complète du `module`.\n\n"
        "Deuxième paragraphe.\n",
        encoding="utf-8",
    )
    t = tickets.parse_ticket(fichier_ticket, {})
    assert t.description == "Voici le lien vers la description complète du module. Deuxième paragraphe."


def test_description_extraite_premier_paragraphe(tmp_path):
    """À défaut de section Description, retient le premier paragraphe informatif."""
    fichier_ticket = tmp_path / "tickets" / "ticket_099_essai.md"
    fichier_ticket.write_text(
        "# Ticket 099 — Titre d'essai\n\n"
        "> **Statut** : en cours\n\n"
        "Premier paragraphe expliquant la problématique du ticket.\n\n"
        "## Objectif\n",
        encoding="utf-8",
    )
    t = tickets.parse_ticket(fichier_ticket, {})
    assert t.description == "Premier paragraphe expliquant la problématique du ticket."


def test_description_surchargee_dans_fichier(tmp_path):
    """Une clé description dans les surcharges l'emporte sur l'extraction."""
    fichier_ticket = tmp_path / "tickets" / "ticket_099_essai.md"
    fichier_ticket.write_text(
        "# Ticket 099 — Titre d'essai\n\n"
        "## Description\n\n"
        "Description issue du markdown.\n",
        encoding="utf-8",
    )
    overrides = {"ticket_099_essai": {"description": "Description manuelle surchargée."}}
    t = tickets.parse_ticket(fichier_ticket, overrides)
    assert t.description == "Description manuelle surchargée."


def test_save_override_description(fichier):
    """save_override permet d'enregistrer ou modifier une description."""
    import yaml as pyyaml

    assert tickets.save_override(
        "ticket_011_arrivees_perdues_gama",
        tickets.DOING,
        description="Nouvelle description courte du ticket 011.",
        path=fichier,
    ) is True

    data = pyyaml.safe_load(fichier.read_text(encoding="utf-8"))["tickets"]
    assert data["ticket_011_arrivees_perdues_gama"]["description"] == "Nouvelle description courte du ticket 011."


def test_tickets_reels_ont_tous_une_description():
    """Sur les 50 vrais tickets du dépôt, aucun n'a de description vide."""
    dossier_reel = tickets.REPO_ROOT / "docs" / "tickets"
    fichiers = sorted(dossier_reel.glob("ticket_*.md"))
    assert len(fichiers) >= 50
    for f in fichiers:
        t = tickets.parse_ticket(f, {})
        assert t.description, f"{f.name} n'a pas de description extraite"
        assert not re.search(r"\[.+\]\(.+\)", t.description), f"Lien non nettoyé dans {f.name}: {t.description}"


def test_tous_les_tickets_reels_ont_une_categorie_valide():
    """Chaque ticket du dépôt a une catégorie parmi les 5 classes majeures."""
    items = tickets.load_tickets()
    assert len(items) >= 50
    for t in items:
        assert t.category in tickets.CATEGORIES, f"{t.path.stem} a une catégorie invalide: {t.category!r}"
    repartition = tickets.summary_by_category(items)
    assert set(repartition.keys()) == set(tickets.CATEGORIES)
    for cat, n in repartition.items():
        assert n > 0, f"La catégorie {cat} n'a aucun ticket"


def test_save_override_category(fichier):
    """save_override permet d'enregistrer ou modifier une catégorie."""
    import yaml as pyyaml

    assert tickets.save_override(
        "ticket_011_arrivees_perdues_gama",
        tickets.DOING,
        category=tickets.CAT_EXP,
        path=fichier,
    ) is True

    data = pyyaml.safe_load(fichier.read_text(encoding="utf-8"))["tickets"]
    assert data["ticket_011_arrivees_perdues_gama"]["category"] == tickets.CAT_EXP


# ── Triage : faisabilité, sûreté, drapeau « jeux de test » (R29 à R34) ────────
#
# Le triage dit ce que coûterait d'y aller maintenant ; la note dit ce sur quoi le
# STATUT s'appuie. Les deux cohabitent dans la même entrée et ne doivent jamais
# s'écraser — c'est ce que la moitié de ces tests vérifie.


def _triage(fichier: Path, cle: str) -> dict:
    import yaml as pyyaml

    return (pyyaml.safe_load(fichier.read_text(encoding="utf-8"))["tickets"] or {})[cle].get("triage")


def test_R29_un_triage_ecrit_se_relit_tel_quel(fichier, monkeypatch):
    assert tickets.save_triage(
        "ticket_099_essai", 4, 2, True, "parce que le graphe est à reconstruire", date="2026-09-14",
        path=fichier,
    ) is True
    bloc = _triage(fichier, "ticket_099_essai")
    assert bloc["faisabilite"] == 4
    assert bloc["surete"] == 2
    assert bloc["jeux_de_test"] is True
    assert bloc["date"] == "2026-09-14"
    assert "reconstruire" in bloc["motif"]

    monkeypatch.setattr(tickets, "OVERRIDES_PATH", fichier)
    lu = tickets._lire_triage("ticket_099_essai", bloc)
    assert (lu.faisabilite, lu.surete, lu.jeux_de_test) == (4, 2, True)
    assert lu.priorite == 6 and lu.quick_win is False


def test_R29_les_deux_echelles_vont_dans_le_meme_sens():
    """5 est toujours la bonne nouvelle : c'est ce qui autorise la priorité par somme.

    Si `surete` redevenait un `regression` croissant, `priorite` classerait en tête les
    tickets les plus dangereux — en silence, et sans qu'aucun autre test ne le voie.
    """
    sur = tickets.Triage(faisabilite=5, surete=5)
    risque = tickets.Triage(faisabilite=5, surete=1)
    assert sur.priorite > risque.priorite
    assert sur.quick_win is True and risque.quick_win is False


def test_R30_ecrire_un_triage_n_efface_ni_la_note_ni_le_statut(fichier):
    cle, statut, note = _premiere_entree_notee(fichier.read_text(encoding="utf-8"))
    tickets.save_triage(cle, 3, 3, False, "un motif neuf", path=fichier)
    import yaml as pyyaml

    entree = (pyyaml.safe_load(fichier.read_text(encoding="utf-8"))["tickets"] or {})[cle]
    assert entree["status"] == statut
    assert entree["note"] == note
    assert entree["triage"]["motif"] == "un motif neuf"


def test_R30_ecrire_un_statut_n_efface_pas_le_triage(fichier):
    tickets.save_triage("ticket_099_essai", 2, 5, True, "posé d'abord", path=fichier)
    tickets.save_override("ticket_099_essai", tickets.DOING, note="une note", path=fichier)
    bloc = _triage(fichier, "ticket_099_essai")
    assert bloc["faisabilite"] == 2 and bloc["surete"] == 5 and bloc["jeux_de_test"] is True
    assert bloc["motif"] == "posé d'abord"


def test_R31_une_valeur_hors_bornes_est_refusee_en_nommant_le_ticket(fichier):
    with pytest.raises(tickets.TriageInvalide) as erreur:
        tickets.save_triage("ticket_099_essai", 8, 3, path=fichier)
    assert "ticket_099_essai" in str(erreur.value) and "faisabilite" in str(erreur.value)
    assert not fichier.read_text(encoding="utf-8").count("faisabilite: 8")


@pytest.mark.parametrize("brut", [
    {"faisabilite": 0, "surete": 3},
    {"faisabilite": 3, "surete": 6},
    {"faisabilite": "trois", "surete": 3},
    {"faisabilite": True, "surete": 3},
    {"surete": 3},
    {"faisabilite": 3},
    {"faisabilite": 3, "surete": 3, "jeux_de_test": "oui"},
])
def test_R31_la_lecture_refuse_un_bloc_mal_formé(brut):
    with pytest.raises(tickets.TriageInvalide):
        tickets._lire_triage("ticket_099_essai", brut)


def test_R32_reenregistrer_le_meme_triage_n_ecrit_rien(fichier):
    tickets.save_triage("ticket_099_essai", 3, 4, False, "stable", date="2026-09-14", path=fichier)
    avant = fichier.read_text(encoding="utf-8")
    assert tickets.save_triage(
        "ticket_099_essai", 3, 4, False, "stable", date="2026-09-14", path=fichier
    ) is False
    assert fichier.read_text(encoding="utf-8") == avant


def test_R32_la_date_ne_bouge_pas_quand_l_appreciation_ne_bouge_pas(fichier):
    """Redater à chaque clic salirait `git status` dès le lendemain (R13)."""
    tickets.save_triage("ticket_099_essai", 3, 4, False, "stable", date="2026-01-02", path=fichier)
    tickets.save_triage("ticket_099_essai", 3, 4, False, "stable", path=fichier)
    assert _triage(fichier, "ticket_099_essai")["date"] == "2026-01-02"

    tickets.save_triage("ticket_099_essai", 5, 4, False, "stable", path=fichier)
    assert _triage(fichier, "ticket_099_essai")["date"] != "2026-01-02"


def test_R33_un_ticket_sans_bloc_triage_se_lit_sans_casser():
    non_tries = [t for t in tickets.load_tickets() if t.triage is None]
    assert non_tries, "le fichier réel doit encore porter des tickets sans triage (les clos)"
    assert all(t.triage is None for t in non_tries)
    assert tickets.summary_triage(non_tries)["non_tries"] == sum(
        1 for t in non_tries if tickets.est_ouvert(t)
    )


def test_R34_tous_les_tickets_ouverts_sont_tries():
    """Un ticket ouvert sans appréciation est un angle mort : il n'apparaît dans aucun
    classement et son coût n'a jamais été posé."""
    orphelins = [
        f"{t.number} {t.path.stem}"
        for t in tickets.load_tickets()
        if tickets.est_ouvert(t) and t.triage is None
    ]
    assert not orphelins, f"tickets ouverts non triés : {', '.join(sorted(orphelins))}"


def test_R34_les_tickets_clos_ne_portent_pas_de_triage():
    """On ne se demande pas si un ticket terminé est faisable."""
    parasites = [
        f"{t.number} ({t.status})"
        for t in tickets.load_tickets()
        if not tickets.est_ouvert(t) and t.triage is not None
    ]
    assert not parasites, f"tickets clos portant un triage : {', '.join(sorted(parasites))}"


def test_les_etoiles_ecrivent_toujours_les_cinq_positions():
    assert tickets.etoiles(3) == "★★★☆☆"
    assert tickets.etoiles(5) == "★★★★★"
    assert tickets.etoiles(1) == "★☆☆☆☆"
    assert len(tickets.etoiles(2)) == tickets.TRIAGE_MAX


def test_les_etoiles_aamas_utilisent_des_etoiles_jaunes():
    assert tickets.etoiles_aamas(3) == "⭐⭐⭐☆☆"
    assert tickets.etoiles_aamas(5) == "⭐⭐⭐⭐⭐"
    assert tickets.etoiles_aamas(1) == "⭐☆☆☆☆"
    assert tickets.etoiles_aamas(None) == "—"
    assert len(tickets.etoiles_aamas(2)) == tickets.TRIAGE_MAX


def test_R29_un_triage_avec_aamas_ecrit_se_relit_tel_quel(fichier, monkeypatch):
    assert tickets.save_triage(
        "ticket_099_essai", 4, 3, False, "pertinent pour AAMAS", aamas=5, date="2026-09-14",
        path=fichier,
    ) is True
    bloc = _triage(fichier, "ticket_099_essai")
    assert bloc["faisabilite"] == 4
    assert bloc["surete"] == 3
    assert bloc["aamas"] == 5

    monkeypatch.setattr(tickets, "OVERRIDES_PATH", fichier)
    lu = tickets._lire_triage("ticket_099_essai", bloc)
    assert lu.aamas == 5
    assert lu.etoiles_aamas() == "⭐⭐⭐⭐⭐"


def test_R31_aamas_hors_bornes_ou_type_invalide_est_refuse(fichier):
    with pytest.raises(tickets.TriageInvalide) as err1:
        tickets.save_triage("ticket_099_essai", 3, 3, aamas=7, path=fichier)
    assert "aamas" in str(err1.value)

    with pytest.raises(tickets.TriageInvalide) as err2:
        tickets.save_triage("ticket_099_essai", 3, 3, aamas=0, path=fichier)
    assert "aamas" in str(err2.value)

    with pytest.raises(tickets.TriageInvalide):
        tickets._lire_triage("ticket_099_essai", {"faisabilite": 3, "surete": 3, "aamas": "haut"})


# ── Filtrage et tri du tableau (R35) ──────────────────────────────────────────
#
# Extraits de `render_tickets` pour cette raison : dans Streamlit, une inversion de
# drapeau ou un tri à l'envers ne se voyait qu'en pilotant un widget dans un
# navigateur — donc jamais en CI.


def test_R35_le_filtre_drapeau_ne_garde_que_les_jeux_de_test():
    items = tickets.load_tickets()
    retenus = tickets.filtrer(items, drapeaux_seuls=True)
    assert retenus, "le fichier réel porte des tickets à drapeau"
    assert all(t.triage is not None and t.triage.jeux_de_test for t in retenus)
    assert len(retenus) == tickets.summary_triage(items)["jeux_de_test"]
    # et sans le filtre, on les retrouve tous
    assert len(tickets.filtrer(items)) == len(items)


def test_R35_le_tri_par_priorite_met_les_meilleurs_en_tete():
    items = tickets.load_tickets()
    tries = tickets.filtrer(items, ordre="Priorité (faisa. + sûreté)")
    prios = [t.triage.priorite for t in tries if t.triage]
    assert prios == sorted(prios, reverse=True)


def test_R35_le_tri_par_interet_aamas_met_les_meilleurs_en_tete(fichier, monkeypatch):
    monkeypatch.setattr(tickets, "OVERRIDES_PATH", fichier)
    tickets.save_triage("ticket_099_essai", 3, 3, aamas=5, path=fichier)
    items = tickets.load_tickets()
    tries = tickets.filtrer(items, ordre="Intérêt AAMAS ↓")
    notes = [t.aamas for t in tries if t.aamas is not None]
    assert notes == sorted(notes, reverse=True)
    assert tries[0].aamas == 5


def test_R35_le_tri_par_risque_met_les_plus_dangereux_en_tete():
    """`surete` croissante = du plus risqué au plus sûr. Une inversion ici ferait
    proposer en premier les tickets les plus inoffensifs sous le libellé « risque »."""
    items = tickets.load_tickets()
    tries = tickets.filtrer(items, ordre="Risque de régression ↓")
    sur = [t.triage.surete for t in tries if t.triage]
    assert sur == sorted(sur)


def test_R35_les_non_tries_tombent_en_fin_de_liste():
    items = tickets.load_tickets()
    for ordre in ("Priorité (faisa. + sûreté)", "Faisabilité ↓", "Sûreté ↓", "Risque de régression ↓"):
        tries = tickets.filtrer(items, ordre=ordre)
        positions = [i for i, t in enumerate(tries) if t.triage is None]
        if positions:
            assert min(positions) > max(
                i for i, t in enumerate(tries) if t.triage is not None
            ), f"un ticket non trié précède un ticket trié avec l'ordre {ordre!r}"


def test_R35_la_recherche_fouille_aussi_le_motif_de_triage():
    items = tickets.load_tickets()
    cible = next(t for t in items if t.triage and t.triage.motif)
    mot = max(
        (m for m in re.findall(r"[a-zàâçéèêëîïôûùüÿñ]{7,}", cible.triage.motif.lower())),
        key=len, default="",
    )
    assert mot, "le motif doit porter un mot assez long pour la recherche"
    assert any(t.number == cible.number for t in tickets.filtrer(items, recherche=mot))


def test_R35_le_filtre_ouverts_seuls_exclut_abandonne_termine_amelioration():
    items = tickets.load_tickets()
    retenus = tickets.filtrer(items, ouverts_seuls=True)
    assert retenus, "il doit rester des tickets ouverts"
    statuts_retenus = {t.status for t in retenus}
    assert tickets.DROPPED not in statuts_retenus
    assert tickets.DONE not in statuts_retenus
    assert tickets.IMPROVEMENT not in statuts_retenus
    assert all(t.status in {tickets.TODO, tickets.DOING, tickets.BLOCKED, tickets.PAUSED} for t in retenus)


def test_R35_les_filtres_se_combinent():
    items = tickets.load_tickets()
    retenus = tickets.filtrer(items, statut=tickets.TODO, drapeaux_seuls=True)
    assert all(t.status == tickets.TODO for t in retenus)
    assert all(t.triage.jeux_de_test for t in retenus)


def test_la_date_du_triage_s_affiche_au_format_de_l_interface():
    assert tickets.Triage(3, 3, date="2026-09-14").date_lisible() == "14/09/2026"
    # une valeur saisie à la main se montre telle quelle plutôt que de disparaître
    assert tickets.Triage(3, 3, date="hier").date_lisible() == "hier"
    assert tickets.Triage(3, 3).date_lisible() == ""
