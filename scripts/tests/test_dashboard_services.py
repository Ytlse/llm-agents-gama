"""Les services Docker nécessaires à une expérience (spec `services-necessaires-a-une-experience.md`).

Le fil de ces tests : une expérience n'a pas besoin de toute la pile. Elle tourne dans
`controller`, s'appuie sur la passerelle seulement si son décideur est un modèle de langage, et
sur les moteurs de routage seulement s'il reste un jeu à construire. La métrologie ne lui sert
jamais, alors que `make up` la réveille.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.dashboard import experiences  # noqa: E402


@pytest.fixture(autouse=True)
def docker_hors_service(tmp_path, monkeypatch):
    """Aucun test de ce fichier ne parle au Docker réel — il lit un `docker` factice.

    Sans cette garde, `make -n` NE SUFFIT PAS à rendre un appel inoffensif : GNU make
    exécute quand même toute ligne de recette contenant `$(MAKE)`, pour permettre le
    parcours récursif. Dans `run-arret`, ce `$(MAKE)` partage sa ligne shell avec
    `docker compose stop`, qui partait donc pour de vrai. La suite a ainsi arrêté
    `controller` et `osmnx1` 29 fois, dont deux fois sous une expérience en cours — un run
    tué à 70 % le 2026-09-08, diagnostiqué à tort comme une fausse manœuvre de pause.

    Le faux `docker` journalise ses arguments : les tests y gagnent, ils vérifient
    désormais ce qui SERAIT lancé au lieu de faire confiance à l'affichage de `make -n`.
    """
    faux = tmp_path / "bin"
    faux.mkdir()
    journal = tmp_path / "appels-docker.txt"
    (faux / "docker").write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$JOURNAL_DOCKER\"\nexit 0\n",
        encoding="utf-8",
    )
    (faux / "docker").chmod(0o755)
    monkeypatch.setenv("PATH", f"{faux}:{os.environ['PATH']}")
    monkeypatch.setenv("JOURNAL_DOCKER", str(journal))
    return journal


def _exp(type_decideur: str) -> dict:
    return {"nom": "essai", "jeu": {"nom": "j"}, "decideur": {"type": type_decideur}}


def test_R2_les_services_requis_suivent_les_reglages():
    assert experiences.services_requis(_exp("passerelle")) == ["controller", "api", "worker"]
    assert experiences.services_requis(_exp("duree_minimale")) == ["controller"]
    assert experiences.services_requis(_exp("rejeu")) == ["controller"]

    routage = experiences.services_requis(_exp("aleatoire"), jeu_a_construire=True)
    assert routage == ["controller", "otp1", "otp2", "otp3", "osmnx1"], routage
    assert "api" not in routage, "un tirage graîné n'attend rien de la passerelle"

    complet = experiences.services_requis(_exp("passerelle"), jeu_a_construire=True)
    assert set(complet) == {"controller", "api", "worker", "otp1", "otp2", "otp3", "osmnx1"}


def test_R4_les_services_entraines_par_dependance_sont_nommes():
    requis = experiences.services_requis(_exp("passerelle"))
    entraines = experiences.services_entraines(requis)
    assert set(entraines) == {"eqasim", "osmnx1", "otp1", "otp2", "otp3", "redis"}, entraines
    assert not set(entraines) & set(requis), "un service requis n'est pas aussi « entraîné »"


def test_R5_la_metrologie_n_est_jamais_demarree():
    for type_decideur in ("passerelle", "duree_minimale", "aleatoire", "rejeu"):
        for jeu in (False, True):
            requis = experiences.services_requis(_exp(type_decideur), jeu_a_construire=jeu)
            tout = set(requis) | set(experiences.services_entraines(requis))
            assert not tout & set(experiences.SERVICES_MONITORING), (type_decideur, jeu, tout)


def test_R6_la_cible_refuse_une_liste_vide(tmp_path):
    """Sans cette garde, `docker compose up -d` sans argument démarre TOUTE la pile."""
    sortie = subprocess.run(["make", "up-services"], cwd=RACINE, capture_output=True, text=True)
    assert sortie.returncode != 0, sortie.stdout
    assert "SERVICES= est vide" in sortie.stdout + sortie.stderr

    a_blanc = subprocess.run(["make", "-n", "up-services", "SERVICES=controller api worker"],
                             cwd=RACINE, capture_output=True, text=True)
    assert a_blanc.returncode == 0, a_blanc.stderr
    assert "docker compose up -d controller api worker" in a_blanc.stdout


def test_R7_le_graphe_est_lu_dans_le_compose(tmp_path):
    """Le graphe suit le fichier : une dépendance ajoutée doit apparaître."""
    faux = tmp_path / "docker-compose.yml"
    faux.write_text(yaml.safe_dump({"services": {
        "controller": {"depends_on": {"api": {}, "inedit": {}}},
        "api": {"depends_on": ["redis"]},
        "redis": {},
        "inedit": {},
    }}), encoding="utf-8")

    graphe = experiences.dependances_compose(faux)
    assert graphe["controller"] == ["api", "inedit"]
    assert graphe["api"] == ["redis"]
    assert experiences.services_entraines(["controller"], faux) == ["api", "inedit", "redis"]

    # Un compose illisible ne doit pas casser l'affichage
    illisible = tmp_path / "casse.yml"
    illisible.write_text("{{{ pas du yaml", encoding="utf-8")
    assert experiences.dependances_compose(illisible) == {}
    assert experiences.services_entraines(["controller"], illisible) == []


def test_R9_la_lecture_du_compose_ne_lance_aucun_sous_processus(monkeypatch):
    def interdit(*_a, **_k):
        raise AssertionError("la lecture du compose ne doit pas lancer de sous-processus")

    monkeypatch.setattr(subprocess, "run", interdit)
    monkeypatch.setattr(subprocess, "Popen", interdit)
    assert experiences.dependances_compose(), "le compose du dépôt doit être lisible"
    assert experiences.services_entraines(["controller"])


def test_R2_le_compose_du_depot_declare_bien_ces_services():
    """Les noms de services sont écrits dans le code : ils doivent exister dans le compose."""
    graphe = experiences.dependances_compose()
    attendus = {experiences.SERVICE_PLATEFORME, *experiences.SERVICES_PASSERELLE,
                *experiences.SERVICES_ROUTAGE, *experiences.SERVICES_MONITORING}
    manquants = sorted(attendus - set(graphe))
    assert manquants == [], f"services nommés dans le code mais absents du compose : {manquants}"


def test_R12_l_arret_couvre_les_dependances_ou_est_la_memoire():
    """`osmnx1` porte 3,5 Gio et chaque OTP 1,2 à 1,5 Gio : la tête de chaîne ne rend rien."""
    a_rendre = experiences.services_a_arreter(_exp("passerelle"))
    assert a_rendre == ["controller", "api", "worker", "eqasim", "osmnx1",
                        "otp1", "otp2", "otp3", "redis"], a_rendre
    for gourmand in ("osmnx1", "otp1", "otp2", "otp3"):
        assert gourmand in a_rendre, f"{gourmand} porte l'essentiel de la RAM"
    assert not set(a_rendre) & set(experiences.SERVICES_MONITORING), \
        "la métrologie n'a pas été démarrée par nous : on ne l'arrête pas"

    heuristique = experiences.services_a_arreter(_exp("duree_minimale"))
    assert "worker" not in heuristique, "le worker n'a pas été démarré pour une heuristique"
    assert "osmnx1" in heuristique, "mais le compose l'a entraîné, donc il occupe la RAM"


def test_R11_R13_R14_la_cible_chainee_arrete_apres_et_garde_le_code_de_retour():
    a_blanc = subprocess.run(
        ["make", "-n", "experience-lancer-arret", "EXP=essai", "SERVICES=controller osmnx1"],
        cwd=RACINE, capture_output=True, text=True)
    assert a_blanc.returncode == 0, a_blanc.stderr
    recette = a_blanc.stdout

    lancement = recette.index("experiences lancer --experience essai")
    arret = recette.index("docker compose stop controller osmnx1")
    assert lancement < arret, "l'arrêt doit suivre l'expérience, pas la précéder"
    assert "code=$?" in recette and "exit $code" in recette, \
        "le code de retour de l'expérience doit être conservé (R14)"
    assert "docker compose down" not in recette, "jamais `down` : conteneurs et volumes restent (R13)"
    # Une seule commande shell : l'arrêt ne dépend pas du tableau de bord (R11)
    assert recette.count("set +e") == 1


def test_R11_le_lancement_avec_gama_arrete_aussi_le_service_gama(docker_hors_service):
    a_blanc = subprocess.run(["make", "-n", "run-arret", "JEU=j5", "SERVICES=controller osmnx1"],
                             cwd=RACINE, capture_output=True, text=True)
    assert a_blanc.returncode == 0, a_blanc.stderr
    assert "stop controller osmnx1 gama" in a_blanc.stdout, a_blanc.stdout
    assert "--profile offline" in a_blanc.stdout, "le service gama vit dans le profil offline"

    # `make -n` a bel et bien lancé la ligne (elle contient `$(MAKE)`) : ce qu'a reçu le
    # faux docker le prouve, et c'est cela qu'on veut voir arriver au vrai.
    recu = docker_hors_service.read_text(encoding="utf-8") if docker_hors_service.exists() else ""
    assert "compose --profile offline stop controller osmnx1 gama" in recu, \
        f"la commande d'arrêt réellement émise : {recu!r}"


def test_R16_les_trois_cibles_refusent_une_liste_vide():
    for cible, variables in (("up-services", []), ("stop-services", []),
                             ("experience-lancer-arret", ["EXP=essai"]), ("run-arret", ["JEU=j5"])):
        sortie = subprocess.run(["make", cible, *variables], cwd=RACINE,
                                capture_output=True, text=True)
        assert sortie.returncode != 0, f"{cible} devrait refuser une liste vide"
        assert "SERVICES= est vide" in sortie.stdout + sortie.stderr, cible
        assert "docker compose" not in sortie.stdout, f"{cible} ne doit pas appeler docker"
