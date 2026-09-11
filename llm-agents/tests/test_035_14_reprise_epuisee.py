"""Une exécution épuisée se reprend — seule une archive clôturée ne se reprend pas (ticket 035).

Le runner marque « épuisée » SANS sceller l'archive (R4 : `not exe.cloturee`), précisément pour
qu'on la reprenne quand la fenêtre de quota se rouvre — ou tout de suite, si l'épuisement était
un faux diagnostic. Le 2026-09-08, `make experience-reprendre` répondait pourtant « rien à
reprendre » sur une telle exécution : la CLI refusait tout état de `ETATS_FINAUX`, épuisée
comprise, en contradiction avec son propre message, la spec et le bouton « Reprendre ».
"""

from experiences.cli import motif_non_reprenable


class _Exe:
    def __init__(self, etat: str, cloturee: bool = False, nom: str = "2026-09-08_12_01_16"):
        self._etat, self.cloturee, self.nom = etat, cloturee, nom

    def etat(self) -> dict:
        return {"etat": self._etat, "raison": None, "reprise_possible_a": None}


def test_epuisee_non_cloturee_se_reprend():
    assert motif_non_reprenable(_Exe("epuisee")) is None


def test_en_pause_interrompue_et_en_cours_sans_runner_se_reprennent():
    for etat in ("en_pause", "interrompue", "en_cours", "definie", "en_attente_quota"):
        assert motif_non_reprenable(_Exe(etat)) is None, etat


def test_une_archive_cloturee_ne_se_reprend_pas_quel_que_soit_son_etat():
    for etat in ("arretee", "terminee", "epuisee"):
        motif = motif_non_reprenable(_Exe(etat, cloturee=True))
        assert motif and "clôturée" in motif and "Rejouer" in motif and "2026-09-08_12_01_16" in motif, etat


def test_terminee_ne_se_reprend_pas_meme_sans_bloc_cloture():
    """Ceinture : une terminée est toujours clôturée par le runner, mais un etat.json posé à la main ne doit pas rouvrir."""
    assert motif_non_reprenable(_Exe("terminee", cloturee=False))
