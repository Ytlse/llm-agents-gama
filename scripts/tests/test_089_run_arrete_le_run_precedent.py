"""Ticket 089 — `make run` arrête le run précédent AVANT de lancer le suivant.

Le conteneur GAMA n'était pas redémarré entre deux lancements, si bien que chaque `make run`
chargeait le modèle dans le processus GAMA déjà en place. Mesuré le 2026-09-16 : deux City.gaml
résidents dans la même JVM plafonnée à 12 Go — 453 communes et le réseau de transport complet
en double — et le conteneur tué par sa propre limite (`OOMKilled=true`) au jour 1 du bras C6.
Ce n'est pas le nombre d'agents qui pèse, c'est le territoire : la limite tenait pour UNE
simulation de 1 000 agents, pas pour deux de cinq.
"""

from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
GAMA_MK = RACINE / "make" / "gama.mk"


def _recette_run() -> list[str]:
    """Les lignes de la recette `run:`, jusqu'à la cible suivante."""
    lignes = GAMA_MK.read_text(encoding="utf-8").splitlines()
    debut = next(i for i, l in enumerate(lignes) if l.startswith("run:"))
    recette = []
    for ligne in lignes[debut + 1:]:
        if ligne and not ligne.startswith(("\t", " ", "ifeq", "ifneq", "else", "endif", "#")):
            break
        recette.append(ligne)
    return recette


class TestLeRunPrecedentEstArrete:
    def test_R1_la_recette_appelle_stop_run(self):
        assert any("stop-run" in l for l in _recette_run()), (
            "sans arrêt préalable, GAMA garde en mémoire l'expérience du run précédent "
            "et la suivante s'y ajoute jusqu'à l'OOM"
        )

    def test_R2_l_arret_vient_en_PREMIER(self):
        """Après le premier geste qui touche la pile, il serait trop tard."""
        recette = _recette_run()
        i_stop = next(i for i, l in enumerate(recette) if "stop-run" in l)
        gestes = [i for i, l in enumerate(recette)
                  if any(m in l for m in ("COMPOSE)", "rm -rf", "perl", "wait-ready"))]
        assert gestes, "la recette touche forcément la pile quelque part"
        assert i_stop < min(gestes), (
            f"stop-run est en position {i_stop}, après un geste en position {min(gestes)}"
        )

    def test_R3_l_arret_vaut_AUSSI_pour_la_reprise_a_chaud(self):
        """`CONT=1` reprend dans le même répertoire : il charge lui aussi un modèle, et
        doit donc partir d'un GAMA vide comme les autres."""
        recette = _recette_run()
        i_stop = next(i for i, l in enumerate(recette) if "stop-run" in l)
        conditions = [i for i, l in enumerate(recette) if l.startswith(("ifeq", "ifneq"))]
        assert not conditions or i_stop < min(conditions), (
            "stop-run est à l'intérieur d'une branche conditionnelle : il ne s'appliquerait "
            "pas à tous les lancements"
        )


class TestCeQueLUtilisateurVoit:
    def test_R4_l_arret_est_annonce(self):
        """Arrêter un run en cours n'est pas anodin : la commande doit le dire, sinon un
        `make run` tapé par mégarde tue un run de vingt jours en silence."""
        recette = "\n".join(_recette_run())
        i = recette.find("stop-run")
        assert i >= 0, "stop-run absent de la recette (cf. R1)"
        contexte = recette[max(0, i - 400):i + 200]
        assert "echo" in contexte, "aucun message autour de l'arrêt du run précédent"
