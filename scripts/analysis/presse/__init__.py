"""Corpus de presse locale et grille des signes — ticket 059, lots 1 et 2.

Trois modules, et la séparation est celle du protocole :

- `grille` — les vingt signes attendus, gelés avant la première requête ;
- `lexique` — les mots de mobilité, qui rendent la condition C3 vérifiable au lieu de déclarée ;
- `corpus` — les textes des conditions C2, C3 et C4, et leur manifeste ;
- `scoring` — l'écart apparié, le taux d'accord de signe et son binomial, le kappa pondéré.

Aucun de ces modules n'appelle un modèle. Ils chargent, vérifient et refusent.
"""

from scripts.analysis.presse.corpus import Corpus, RefusDeCorpus, charger_corpus
from scripts.analysis.presse.grille import Grille, RefusDeGrille, charger_grille
from scripts.analysis.presse.lexique import mots_de_mobilite_trouves
from scripts.analysis.presse.scoring import (
    NON_CONCLUANT,
    AccordDeSigne,
    EcartModal,
    accord_de_signe,
    ecart_apparie,
    kappa_pondere,
    signes_observes,
)

__all__ = [
    "NON_CONCLUANT",
    "AccordDeSigne",
    "Corpus",
    "EcartModal",
    "Grille",
    "RefusDeCorpus",
    "RefusDeGrille",
    "charger_corpus",
    "accord_de_signe",
    "charger_grille",
    "ecart_apparie",
    "kappa_pondere",
    "mots_de_mobilite_trouves",
    "signes_observes",
]
