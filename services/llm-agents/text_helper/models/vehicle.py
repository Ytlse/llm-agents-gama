"""Observation d'un segment parcouru par un VÉHICULE PERSONNEL — ticket 077, lot B2.

Avant ce modèle, les segments `__DIRECT_CAR__` et `__DIRECT_BIKE__` passaient par
`submit_ob_transit` côté GAMA, donc par le gabarit du transport collectif, dont les filtres
interrogent le GTFS et n'y trouvent évidemment rien. Le modèle lisait alors, **253 fois sur
le run de trente jours du ticket 075** :

    [ PUBLIC TRANSPORT ] Trip by Unknown Unknown; From: ''; To: ''; Actual duration: 9 minutes.

Un agent qui conduit tous les jours se relisait donc chaque soir comme usager d'un transport
en commun sans nom, entre deux arrêts sans nom. Ce n'est pas un défaut d'affichage : ce texte
est l'entrée de la réflexion, et donc la matière des concepts.
"""

from typing import Literal

from text_helper.templates.repository import tpl_describe_the_ob_vehicle
from text_helper.type import EnvOb


class EnvObVehicle(EnvOb):
    """Segment parcouru avec un véhicule personnel (voiture ou vélo).

    Un seul modèle pour les deux : ils ne diffèrent que par le mot rendu, et deux modèles
    jumeaux divergeraient. `mode` est CONTRAINT — une valeur inattendue doit casser au parsing
    plutôt que produire une phrase plausible et fausse.
    """

    mode: Literal["car", "bike"]
    distance: float
    duration: float

    def describe(self, weather=None) -> str:
        return tpl_describe_the_ob_vehicle.render(ob=self, weather=weather)
