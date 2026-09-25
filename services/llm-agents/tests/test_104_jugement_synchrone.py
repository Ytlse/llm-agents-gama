"""Le jugement d'un événement SUBI est attendu, pas lancé en tâche de fond (2026-09-23).

Q6 du ticket 100 posait le jugement « dans la file du soir » : il partait en tâche de fond et
relevait l'importance de l'entrée courte avant que la consolidation la consomme. Le
raisonnement supposait une consolidation DU SOIR. Il n'y en a pas — la réflexion part au SEUIL
D'ENTRÉES, et l'entrée de l'événement est souvent celle qui fait franchir ce seuil : elle
déclenche alors la consolidation qui la consomme, pendant que son jugement est en vol.

Mesuré sur le run du 2026-09-23, campagne c3 :

    10:24:08  [gravite] CHOC pour 861500 à 27 March 2026, 14:02 : I_det=0.87
    10:24:09  [reflexion-stm] agent=861500 concepts=2        ← consolidation, 1 s après
    10:24:14  « c3_panne_reseau » jugé : grave (0.75)        ← 5 s trop tard

L'événement a été qualifié sur le fait mesuré (0,87) au lieu de la gravité jugée (0,75),
c'est-à-dire sous le régime que la décision D7 a abandonné.
"""

from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
CTRL = (RACINE / "urban_mobility_agents" / "simulation_controller.py").read_text("utf-8")


def _bloc_du_site_d_appel() -> str:
    debut = CTRL.index("if _jugement_attendu:")
    return CTRL[debut : debut + 600]


def test_R11_le_jugement_est_attendu():
    bloc = _bloc_du_site_d_appel()
    assert "await self._juger_evenement_subi(" in bloc


def test_R12_le_jugement_ne_part_plus_en_tache_de_fond():
    """C'EST la régression à empêcher : un `_spawn` rouvre la course, silencieusement."""
    bloc = _bloc_du_site_d_appel()
    assert "_spawn" not in bloc, (
        "lancer le jugement en tâche de fond le fait perdre la course chaque fois que "
        "l'entrée injectée franchit le seuil de réflexion"
    )


def test_R13_la_consolidation_part_bien_au_seuil_d_entrees():
    """La cause. Si ce réglage disparaissait, le raisonnement ci-dessus serait à refaire.

    `stm_reflection_min_entries` est ce qui rend la course INGAGNABLE pour un jugement
    différé : la réflexion ne part pas à une heure, elle part à un compte d'entrées, et
    l'entrée de l'événement est celle qui peut faire franchir le compte.
    """
    from settings import settings

    seuil = settings.agent.stm_reflection_min_entries
    assert isinstance(seuil, int) and seuil > 0, (
        "un seuil positif signifie un déclenchement par COMPTE D'ENTRÉES, pas par horloge"
    )


def test_R14_la_garde_du_jugement_tardif_reste_en_place():
    """Attendre rend la course impossible ; la garde reste, elle ne coûte rien.

    Un futur appelant qui reviendrait au différé retrouverait l'alarme plutôt qu'un silence.
    """
    debut = CTRL.index("async def _juger_evenement_subi")
    fin = CTRL.index("async def _injecter_evenements_du_reveil")
    methode = CTRL[debut:fin]
    assert "est arrivé APRÈS la consolidation" in methode
    assert methode.count("registre.tracer(") == 4


def test_R15_l_alarme_ne_dit_plus_du_soir():
    """Le libellé désignait un moment qui n'existe pas, et m'a fait chercher une latence."""
    assert "APRÈS la consolidation du soir" not in CTRL
