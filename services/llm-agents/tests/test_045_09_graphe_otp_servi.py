"""Ticket 045 — le jeu enregistre le graphe OTP QUI L'A SERVI (trouvé au balayage).

Le fait, mesuré le 2026-09-11. OTP est lancé avec `--load /var/otp/toulouse` et charge
`/var/otp/toulouse/graph.obj`, soit `data/gtfs/graph.obj` sur l'hôte — 84,3 Mo, construit le
4 septembre, empreinte `7f0b5b76…`. Le manifeste d'un jeu enregistrait, lui,
`data/gtfs/tisseo_gtfs/graph.obj` — 79,3 Mo, du 19 mai, empreinte `8561b840…` — parce que
`_FICHIER_GRAPHE_OTP` était cherché sous `settings.gtfs.gtfs_file`, qui désigne le dossier du
**flux** Tisséo et non la racine montée dans OTP.

Deux fichiers, deux empreintes, et le jeu nommait le mauvais.

Conséquence : la péremption (J10) ne pouvait **jamais** voir une reconstruction du graphe
réellement en service, puisqu'elle surveillait un fichier qui ne joue aucun rôle. Un jeu
annonçait une provenance fausse, et une reconstruction du graphe passait pour « rien n'a
changé ». C'est le motif que ce ticket traque : **l'absence de mesure passe pour un cas sain**.

C'est aussi plus complet ainsi. Le graphe embarque les **trois** flux en service — Tisséo, liO,
TER — et le fond OSM ; les empreintes de fichiers texte, elles, ne couvrent que Tisséo. Surveiller
le graphe capte donc un changement dans n'importe lequel des trois.
"""

from __future__ import annotations

from pathlib import Path

from experiences.jeu import chemin_graphe_otp, dependances_courantes
from settings import settings


def test_le_graphe_est_cherche_a_la_racine_montee_dans_otp():
    """`--load /var/otp/toulouse` → le graphe est à la RACINE, pas dans le dossier du flux."""
    feed = Path(settings.gtfs.gtfs_file)
    trouve = chemin_graphe_otp(feed)
    assert trouve is not None, "aucun graph.obj trouvé, ni à la racine ni dans le flux"
    assert trouve.name == "graph.obj"
    # La racine (parent du dossier de flux) l'emporte quand les deux existent.
    racine = feed.parent / "graph.obj"
    if racine.is_file():
        assert trouve == racine, f"le graphe servi est {racine}, pas {trouve}"


def test_le_graphe_du_dossier_de_flux_sert_de_repli():
    """Un dépôt où le graphe vit dans le dossier du flux reste lisible — on ne casse rien."""
    feed = Path(settings.gtfs.gtfs_file)
    if (feed.parent / "graph.obj").is_file():
        return  # cas nominal couvert par le test précédent
    assert chemin_graphe_otp(feed) == feed / "graph.obj"


def test_lempreinte_enregistree_est_celle_du_fichier_servi():
    """Le manifeste doit nommer le fichier qu'OTP charge, pas un homonyme."""
    from experiences.population import sha256_fichier

    deps = dependances_courantes()
    chemin = chemin_graphe_otp(Path(settings.gtfs.gtfs_file))
    assert chemin is not None
    assert deps["otp_graph_sha256"] == sha256_fichier(chemin)


def test_un_graphe_absent_se_journalise_au_lieu_de_se_taire(tmp_path, monkeypatch):
    """Une dépendance non enregistrée ne se compare pas : son absence doit se dire.

    Rendre `None` en silence est indistinguable d'un graphe inchangé — c'est ce silence qui
    a laissé passer le défaut pendant des mois.
    """
    from loguru import logger

    vide = tmp_path / "flux"
    vide.mkdir()
    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(str(m)), level="WARNING")
    try:
        assert chemin_graphe_otp(vide) is None
    finally:
        logger.remove(sink)
    assert any("graph.obj" in m for m in messages), messages
