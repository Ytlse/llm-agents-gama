"""Chocs déclarés — ADAPTATEUR vers `llm/evenements/` (ticket 100, lot 1).

CE MODULE N'A PLUS DE LOGIQUE. Tout ce qu'il portait — dataclasses, gardes de contenu, règles
d'exposition, cadence, compteurs, jour du run, trace, alarmes — vit désormais dans
`llm/evenements/`, où un article de presse emprunte le même chemin qu'un choc subi.

POURQUOI UN ADAPTATEUR, ET POURQUOI IL DOIT DISPARAÎTRE
-------------------------------------------------------
Le ticket 079 est livré, mesuré, et ses chiffres sont dans le § 7.2 du manuscrit. Une migration
qui casserait ses 36 tests, ou qui changerait d'un caractère ce que `chocs.jsonl` contient,
rendrait ces chiffres invérifiables. Cet adaptateur existe pour que la migration se prouve : les
tests du 079 tournent **sans que leur attendu bouge**, contre le code neuf.

⚠ Il part au **lot 6 du ticket 100**, après un run court de non-régression sur
`c6_voiture_suspecte` — le test en or rejoue une trace, pas un run, et ne dit rien du chemin
GAMA. Avec lui partiront les alias de compatibilité : `choc_id`, `vecu`, `RegistreChocs.choc`,
les clés `choc_id`/`vecu` de la trace, et les liens `choc.yaml`/`chocs.jsonl` du répertoire de
run. N'écrivez aucun code neuf contre ce module.
"""

from __future__ import annotations

from llm.evenements import (  # noqa: F401 — façade de compatibilité
    CADENCES,
    CADENCE_PAR_DEFAUT,
    REGLES_EXPOSITION,
    CompteursJournee,
    incident_reseau_a_une_source,
    initialiser,
    registre,
    reinitialiser,
)
from llm.evenements.declaration import (  # noqa: F401
    EffetPhysique,
    Evenement,
    EvenementApplique,
    Exposition,
    JourDEvenement,
    RefusDEvenement,
    charger,
)
from llm.evenements.gardes import (  # noqa: F401
    MARQUEURS_CONSIGNE,
    MARQUEURS_INTENTION,
    MARQUEURS_VERDICT,
)
from llm.evenements.registre import RegistreEvenements

# ── Les noms du ticket 079 ──────────────────────────────────────────────────────────────────
# Des ALIAS, et non des sous-classes : les tests du 079 remplacent `RegistreChocs.jour_du_run`
# sur la CLASSE pour jouer une journée donnée sans simulateur. Une sous-classe recevrait le
# correctif sans que la classe réelle le voie, et l'inverse — le test passerait en ne vérifiant
# plus rien, ce qui est pire que de le voir échouer.
RefusDeChoc = RefusDEvenement
RegistreChocs = RegistreEvenements
Choc = Evenement
JourDeChoc = JourDEvenement
ChocApplique = EvenementApplique

__all__ = [
    "CADENCES",
    "CADENCE_PAR_DEFAUT",
    "REGLES_EXPOSITION",
    "Choc",
    "ChocApplique",
    "CompteursJournee",
    "Exposition",
    "JourDeChoc",
    "RefusDeChoc",
    "RegistreChocs",
    "charger",
    "incident_reseau_a_une_source",
    "initialiser",
    "registre",
    "reinitialiser",
]
