"""Ticket 045, bloc F — le tableau de bord ne propose RIEN d'archivé, nulle part.

R16 : `populations()` n'expose aucune cohorte archivée, et son défaut est la dernière scellée
      par DATE DE SCEAU, jamais la première par ordre alphabétique.
R17 : aucun élément archivé n'est proposé au choix, y compris quand « Masquer les obsolètes »
      est DÉCOCHÉ — ce bouton règle la visibilité de ce qui est obsolète, pas de ce qui est
      archivé.

Ce que ces tests verrouillent, et pourquoi. Deux notions distinctes portaient jusqu'ici le même
mot « obsolète » :

- une exécution *obsolète* est une exécution qu'une plus récente de la MÊME expérience a
  remplacée ; c'est elle que la case à cocher gouverne, et c'est très bien ainsi ;
- une expérience *archivée* est une expérience retirée du service par une décision.

La seconde ne doit jamais dépendre de la première. Or l'exclusion des archivées n'était vraie
que dans le tableau « Mes expériences » : le sélecteur « S'inspirer d'une expérience existante »
et le bouton « Dupliquer » lisaient `experiences()`, que rien ne filtre. Une expérience archivée
y restait donc proposée, et un clic la recopiait dans le formulaire.

Pour les populations, l'exclusion d'un dossier `archive/` n'était qu'un **accident de
structure** : `populations()` ne retient un dossier que s'il porte un `MANIFEST.yaml` à sa
racine directe, ce qu'un dossier `archive/` n'a pas. Rien ne l'énonçait, rien ne le testait, et
la règle serait tombée à la première cohorte archivée gardant son manifeste au mauvais niveau.
Le défaut du formulaire, lui, était `populations()[0]`, c'est-à-dire le PREMIER par ordre
alphabétique : `population_1000_AAMAS` précède `_v3`, `_v4`, `_v5`. C'est la cause racine des
36 exécutions faites sur la mauvaise cohorte.
"""

import json
import sys
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.dashboard import experiences  # noqa: E402


# ── Bancs ───────────────────────────────────────────────────────────────────


def _cohorte(dossier: Path, nom: str, scelle_le: str | None) -> Path:
    """Une cohorte scellée CRÉDIBLE : le sceau porte la vraie empreinte du fichier.

    Un sceau inventé (`"x" * 64`) serait refusé au chargement — `info_population` vérifie
    qu'une population scellée n'a pas été altérée. Une fixture qui contourne ce contrôle
    fait passer des tests qui ne prouvent rien.
    """
    import hashlib

    d = dossier / nom
    d.mkdir(parents=True)
    fichier = d / "population.json"
    fichier.write_text("[]", encoding="utf-8")
    manifest = {
        "nom": nom,
        "population": {
            "fichier": "population.json",
            "sha256": hashlib.sha256(fichier.read_bytes()).hexdigest(),
        },
    }
    if scelle_le:
        manifest["scelle_le"] = scelle_le
    (d / "MANIFEST.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    return d


def _sha_contenu(dossier_cohorte: Path) -> str:
    """L'empreinte de CONTENU d'une cohorte : celle de son `population.json`."""
    import hashlib

    return hashlib.sha256((dossier_cohorte / "population.json").read_bytes()).hexdigest()


def _experience(dossier: Path, nom: str, statut: str | None = None) -> Path:
    d = dossier / nom
    d.mkdir(parents=True)
    (d / "experience.yaml").write_text(yaml.safe_dump({"nom": nom}), encoding="utf-8")
    if statut:
        (d / "statut.json").write_text(
            json.dumps({"statut": statut, "motif": "essai"}), encoding="utf-8"
        )
    return d


def _jeu(dossier: Path, nom: str) -> Path:
    d = dossier / nom
    d.mkdir(parents=True)
    (d / "MANIFEST.yaml").write_text(
        yaml.safe_dump({"nom": nom, "jour_simule": "2026-03-16", "clos": True}),
        encoding="utf-8",
    )
    return d


# ── R16 : les populations ───────────────────────────────────────────────────


def test_r16_une_cohorte_sous_archive_nest_jamais_proposee(monkeypatch, tmp_path):
    """Même si elle garde son MANIFEST.yaml : c'est l'emplacement qui décide, pas la forme."""
    pop = tmp_path / "data" / "population"
    _cohorte(pop, "population_1000_AAMAS_v5", "2026-09-04T13:47:53+00:00")
    _cohorte(pop / "archive", "population_1000_AAMAS", "2026-09-02T00:00:00+00:00")
    monkeypatch.setattr(experiences, "DOSSIER_POP", pop)
    monkeypatch.setattr(experiences, "REPO_ROOT", tmp_path)

    listees = experiences.populations()
    assert any("population_1000_AAMAS_v5" in p for p in listees)
    assert not any("archive" in p for p in listees), listees


def test_r16_un_json_nu_sous_archive_nest_pas_propose(monkeypatch, tmp_path):
    pop = tmp_path / "data" / "population"
    _cohorte(pop, "population_1000_AAMAS_v5", "2026-09-04T13:47:53+00:00")
    (pop / "archive").mkdir(parents=True, exist_ok=True)
    (pop / "archive" / "vieille.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(experiences, "DOSSIER_POP", pop)
    monkeypatch.setattr(experiences, "REPO_ROOT", tmp_path)

    assert not any("archive" in p for p in experiences.populations())


def test_r16_le_defaut_est_la_derniere_scellee_pas_la_premiere_alphabetique(
    monkeypatch, tmp_path
):
    """La cause racine des 36 exécutions sur la mauvaise cohorte.

    `population_1000_AAMAS` précède `_v5` alphabétiquement ; c'est pourtant `_v5` qui est la
    référence, parce qu'elle est scellée plus tard.
    """
    pop = tmp_path / "data" / "population"
    _cohorte(pop, "population_1000_AAMAS", "2026-09-02T20:39:00+00:00")
    _cohorte(pop, "population_1000_AAMAS_v3", "2026-09-03T18:58:00+00:00")
    _cohorte(pop, "population_1000_AAMAS_v5", "2026-09-04T13:47:53+00:00")
    monkeypatch.setattr(experiences, "DOSSIER_POP", pop)
    monkeypatch.setattr(experiences, "REPO_ROOT", tmp_path)

    assert experiences.population_par_defaut().endswith("population_1000_AAMAS_v5")


def test_r16_une_cohorte_sans_date_de_sceau_ne_prend_pas_la_tete(monkeypatch, tmp_path):
    """Une cohorte sans `scelle_le` ne peut pas être « la plus récente » : elle passe après.

    Sans cette règle, une cohorte mal scellée deviendrait le défaut par le seul fait que sa
    date est absente — encore le motif « l'absence de mesure fait le meilleur score ».
    """
    pop = tmp_path / "data" / "population"
    _cohorte(pop, "population_1000_AAMAS_v5", "2026-09-04T13:47:53+00:00")
    _cohorte(pop, "zz_population_sans_date", None)
    monkeypatch.setattr(experiences, "DOSSIER_POP", pop)
    monkeypatch.setattr(experiences, "REPO_ROOT", tmp_path)

    assert experiences.population_par_defaut().endswith("population_1000_AAMAS_v5")


# ── R17 : les jeux ──────────────────────────────────────────────────────────


def test_r17_un_jeu_sous_archive_nest_pas_propose(monkeypatch, tmp_path):
    jeux = tmp_path / "data" / "jeux"
    _jeu(jeux, "population_1000_AAMAS_v5_20260316")
    _jeu(jeux / "archive", "population_1000_AAMAS_20260316")
    monkeypatch.setattr(experiences, "DOSSIER_JEUX", jeux)

    noms = [j["nom"] for j in experiences.jeux()]
    assert noms == ["population_1000_AAMAS_v5_20260316"]


# ── R17 : les expériences, partout où elles sont proposées ──────────────────


def test_r17_experiences_exclut_les_archivees_et_les_invalides(monkeypatch, tmp_path):
    """`experiences()` sert « S'inspirer de » et « Dupliquer » : elle doit filtrer aussi.

    C'était la lacune : le tableau « Mes expériences » filtrait, ces deux-là non.
    """
    _experience(tmp_path, "exp_vivante")
    _experience(tmp_path, "exp_rangee", statut="archivee")
    _experience(tmp_path, "exp_cassee", statut="invalide")
    monkeypatch.setattr(experiences, "DOSSIER", tmp_path)

    proposees = experiences.experiences()
    assert "exp_vivante" in proposees
    assert "exp_rangee" not in proposees
    assert "exp_cassee" not in proposees


def test_r17_experiences_toutes_reste_disponible_pour_la_lecture(monkeypatch, tmp_path):
    """Filtrer les propositions ne doit pas rendre les archivées ILLISIBLES.

    Une page de détail, un rapport, une reprise d'historique doivent encore pouvoir les
    ouvrir : la règle est « on ne les PROPOSE plus », pas « on les efface ».
    """
    _experience(tmp_path, "exp_vivante")
    _experience(tmp_path, "exp_rangee", statut="archivee")
    monkeypatch.setattr(experiences, "DOSSIER", tmp_path)

    toutes = experiences.experiences(inclure_masquees=True)
    assert {"exp_vivante", "exp_rangee"} <= set(toutes)


def test_r17_le_bouton_masquer_les_obsoletes_ne_gouverne_pas_les_archivees(
    monkeypatch, tmp_path
):
    """Décoché, il fait réapparaître les obsolètes — jamais les archivées.

    Les deux notions sont distinctes et ne doivent pas se confondre : « obsolète » est une
    exécution remplacée par une plus récente de la même expérience, « archivée » est une
    décision de retrait.
    """
    _experience(tmp_path, "exp_vivante")
    _experience(tmp_path, "exp_rangee", statut="archivee")
    monkeypatch.setattr(experiences, "DOSSIER", tmp_path)

    lignes = experiences.lister(tmp_path)
    rangees = [l for l in lignes if l.get("experience") == "exp_rangee"]
    # `lister()` expose tout — c'est la vue qui filtre — mais elle doit MARQUER le statut,
    # sans quoi aucune vue ne peut décider.
    for ligne in rangees:
        assert experiences.masquee(ligne) is True


# ── R19 : le substrat s'affiche à côté du bouton de lancement ───────────────


def test_r19_lempreinte_de_la_cohorte_est_lisible_avant_le_lancement(monkeypatch, tmp_path):
    """Les 36 premières exécutions ont lu la mauvaise cohorte : rien ne le disait AVANT de payer.

    ⚠ Ce test fixe la distinction qui a produit un faux « substrat incohérent » le
    2026-09-11 : **deux quantités portent le nom `sha256`**. L'IDENTITÉ d'une cohorte est
    l'empreinte de son FICHIER manifeste — c'est elle que le jeu enregistre et compare. Son
    CONTENU est l'empreinte de `population.json`, le champ `population.sha256` écrit DANS le
    manifeste. Les confondre fait crier l'incohérence sur une cohorte parfaitement saine.
    """
    import hashlib

    pop = tmp_path / "data" / "population"
    d = _cohorte(pop, "population_1000_AAMAS_v5", "2026-09-04T13:47:53+00:00")
    monkeypatch.setattr(experiences, "DOSSIER_POP", pop)
    monkeypatch.setattr(experiences, "REPO_ROOT", tmp_path)

    info = experiences.empreinte_population("data/population/population_1000_AAMAS_v5")
    assert info["scellee"] is True
    assert info["scelle_le"].startswith("2026-09-04")
    # L'identité : le FICHIER manifeste, pas le champ qu'il contient.
    assert info["sha256"] == hashlib.sha256((d / "MANIFEST.yaml").read_bytes()).hexdigest()
    # Le contenu : le champ du manifeste, qui décrit `population.json`.
    assert info["fichier_sha256"] == _sha_contenu(d)
    assert info["sha256"] != info["fichier_sha256"], "les deux empreintes sont distinctes"


def test_r19_une_cohorte_non_scellee_se_signale(monkeypatch, tmp_path):
    """Sans sceau, pas d'identité stable : la mesure ne serait rattachable à rien."""
    monkeypatch.setattr(experiences, "REPO_ROOT", tmp_path)
    info = experiences.empreinte_population("data/population/toulouse_population_1000.json")
    assert info["scellee"] is False
    assert info["sha256"] == ""


def test_r19_lidentite_est_celle_que_le_jeu_compare(monkeypatch, tmp_path):
    """La garde du tableau de bord doit lire la MÊME empreinte que la garde du lancement.

    Deux implémentations d'un même concept finissent par diverger : c'est le défaut que le
    ticket 045 corrige ailleurs, et il s'est reproduit ici. Ce test l'interdit en comparant
    à la source — `info_population()`, dont `Jeu.verifier_population` consomme le résultat.
    """
    from experiences.population import info_population

    pop = tmp_path / "data" / "population"
    d = _cohorte(pop, "population_1000_AAMAS_v5", "2026-09-04T13:47:53+00:00")
    monkeypatch.setattr(experiences, "DOSSIER_POP", pop)
    monkeypatch.setattr(experiences, "REPO_ROOT", tmp_path)

    vue = experiences.empreinte_population("data/population/population_1000_AAMAS_v5")
    plateforme = info_population(d)
    assert vue["sha256"] == plateforme.sha256
    assert vue["fichier_sha256"] == plateforme.fichier_sha256


def test_r19_un_jeu_prepare_pour_une_autre_cohorte_est_refuse_avant_le_clic(
    monkeypatch, tmp_path
):
    """La garde existe au lancement (G1) ; la remonter avant le clic évite de payer pour rien."""
    pop = tmp_path / "data" / "population"
    _cohorte(pop, "population_1000_AAMAS_v5", "2026-09-04T13:47:53+00:00")
    jeux = tmp_path / "data" / "jeux"
    d = jeux / "jeu_de_la_v1"
    d.mkdir(parents=True)
    (d / "MANIFEST.yaml").write_text(
        yaml.safe_dump(
            {
                "nom": "jeu_de_la_v1",
                # Identité d'une AUTRE cohorte : plausible en forme, différente en valeur.
                "population": {"nom": "population_1000_AAMAS", "sha256": "b" * 64},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(experiences, "DOSSIER_POP", pop)
    monkeypatch.setattr(experiences, "DOSSIER_JEUX", jeux)
    monkeypatch.setattr(experiences, "REPO_ROOT", tmp_path)

    msg = experiences.coherence_population_jeu(
        "data/population/population_1000_AAMAS_v5", "jeu_de_la_v1"
    )
    assert msg and "population_1000_AAMAS" in msg


def test_r19_un_jeu_de_la_bonne_cohorte_ne_declenche_rien(monkeypatch, tmp_path):
    pop = tmp_path / "data" / "population"
    _cohorte(pop, "population_1000_AAMAS_v5", "2026-09-04T13:47:53+00:00")
    jeux = tmp_path / "data" / "jeux"
    d = jeux / "jeu_v5"
    d.mkdir(parents=True)
    # Le jeu enregistre l'empreinte d'IDENTITÉ de la cohorte : celle de son FICHIER
    # manifeste, pas le champ `sha256` qu'il contient. Écrire ici l'empreinte de contenu
    # ferait passer ce test pour un succès alors que la garde comparerait deux choses
    # différentes — c'est exactement le faux positif du 2026-09-11.
    import hashlib

    identite = hashlib.sha256(
        (pop / "population_1000_AAMAS_v5" / "MANIFEST.yaml").read_bytes()
    ).hexdigest()
    (d / "MANIFEST.yaml").write_text(
        yaml.safe_dump(
            {
                "nom": "jeu_v5",
                "population": {"nom": "population_1000_AAMAS_v5", "sha256": identite},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(experiences, "DOSSIER_POP", pop)
    monkeypatch.setattr(experiences, "DOSSIER_JEUX", jeux)
    monkeypatch.setattr(experiences, "REPO_ROOT", tmp_path)

    assert (
        experiences.coherence_population_jeu(
            "data/population/population_1000_AAMAS_v5", "jeu_v5"
        )
        is None
    )


# ── La chaîne des véhicules se lit en toutes lettres ────────────────────────


def test_la_colonne_chaine_dit_active_par_defaut():
    """Une définition muette décrit le comportement nominal, pas un trou."""
    assert experiences.libelle_chaine({}) == "active"
    assert experiences.libelle_chaine({"vehicule_chaine": True, "verrou_retour": True}) == "active"


def test_la_colonne_chaine_dit_coupee_sans_faire_decoder_le_nom():
    """`nochn_noret` dans le nom suppose de connaître la convention ; la colonne, non."""
    assert (
        experiences.libelle_chaine({"vehicule_chaine": False, "verrou_retour": False})
        == "coupée"
    )


def test_la_colonne_distingue_les_deux_interrupteurs():
    """Couper l'un sans l'autre est possible, et le libellé dit ce qui RESTE.

    « position » tout court ne dirait pas si elle est active ou coupée : le libellé nomme
    l'interrupteur encore en service, jamais celui qui est tombé.
    """
    seule_position = {"vehicule_chaine": True, "verrou_retour": False}
    seul_verrou = {"vehicule_chaine": False, "verrou_retour": True}
    assert experiences.libelle_chaine(seule_position) == "position seule"
    assert experiences.libelle_chaine(seul_verrou) == "verrou seul"


def test_la_colonne_chaine_est_affichable_dans_le_tableau():
    """Une valeur calculée mais jamais montrable ne sert à rien.

    Depuis le 2026-09-11 le tableau s'ouvre sur dix colonnes et `chaine` n'en fait plus
    partie : elle reste RAPPELABLE au sélecteur de colonnes, ce qui suffit à ce qu'elle
    serve — la comparabilité de deux exécutions se vérifie à la demande, pas en permanence.
    """
    assert "chaine" in experiences.COLONNES_REGISTRE
    assert "chaine" not in experiences.COLONNES_REGISTRE_DEFAUT


def test_chaque_ligne_listee_porte_son_etat_de_chaine(monkeypatch, tmp_path):
    d = _experience(tmp_path, "exp_test")
    (d / "experience.yaml").write_text(
        yaml.safe_dump({"nom": "exp_test", "vehicule_chaine": False, "verrou_retour": False}),
        encoding="utf-8",
    )
    monkeypatch.setattr(experiences, "DOSSIER", tmp_path)
    lignes = experiences.lister(tmp_path)
    assert lignes and all(l.get("chaine") == "coupée" for l in lignes)
