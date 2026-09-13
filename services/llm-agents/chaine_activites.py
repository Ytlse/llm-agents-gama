"""La chaîne d'activités d'une personne est **cyclique** — une seule implémentation.

La dernière activité de la journée est suivie d'un retour à la première, qui est le domicile
dans la quasi-totalité des cas. Une journée de n activités compte donc n déplacements, pas
n − 1 : le retour au domicile est un déplacement, et il doit être décidé comme les autres.

Ce module existe parce que deux implémentations de cette règle ont divergé (ticket 045,
alerte A1). Le contrôleur de simulation refermait le cycle avec `(i + 1) % n` ; la plateforme
d'expériences énumérait les paires consécutives et s'arrêtait à la dernière activité. Résultat :
la plateforme mesurait 2 693 décisions là où la simulation en jouait 3 693 sur la cohorte v1,
soit **27 % de la journée jamais décidée**. Et l'omission n'était pas aléatoire — elle retirait
exactement le trajet où la contrainte de chaîne des véhicules mord le plus (un agent parti en
voiture rentre en voiture), ce qui poussait structurellement les parts modales vers les modes
d'aller.

La règle du contrôleur fait foi, et les deux appelants passent désormais par ici.

**Heures.** Rien à arbitrer : les populations scellées encodent déjà le bouclage. Pour toute
activité, `scheduled_start_time` de l'activité `(i + 1) % n` vaut `end_time` de l'activité `i`,
**y compris au bouclage** — vérifié le 2026-09-11 sur les 1 894 personnes des cohortes v1 et v5,
sans un seul écart. La convention de la plateforme (heure programmée de la destination) et
celle du contrôleur (fin de l'activité d'origine) désignent donc le même instant.
"""

from __future__ import annotations

from collections.abc import Sequence

from models import Activity

__all__ = ["activite_suivante", "paires_de_la_journee"]


def activite_suivante(
    activites: Sequence[Activity], courante: Activity
) -> Activity | None:
    """L'activité qui suit `courante` dans la chaîne cyclique, ou `None` s'il n'y a pas de trajet.

    Rend `None` dans trois cas, et ce sont ceux que les trois sites du contrôleur testaient
    déjà chacun de leur côté :

    - la personne a zéro ou une seule activité — une chaîne d'un seul maillon ne boucle pas
      sur elle-même, sinon on fabriquerait un trajet d'une activité vers elle-même ;
    - `courante` n'appartient pas à la chaîne (appariement par `id`, jamais par égalité
      d'objet : deux activités peuvent être égales champ à champ) ;
    - l'une des deux extrémités n'a pas de localisation, donc aucun trajet n'est calculable.

    Un retour vers le MÊME lieu, lui, est bien un déplacement : il est énuméré ici et c'est au
    jeu de le classer inexploitable (`origine_egale_destination`). Le distinguer ici reviendrait
    à le faire disparaître des attendus bruts, où il doit compter.
    """
    n = len(activites)
    if n <= 1:
        return None
    idx = next((i for i, a in enumerate(activites) if a.id == courante.id), None)
    if idx is None:
        return None
    suivante = activites[(idx + 1) % n]
    if courante.location is None or suivante.location is None:
        return None
    return suivante


def paires_de_la_journee(
    activites: Sequence[Activity],
) -> list[tuple[Activity, Activity]]:
    """Les paires (origine, destination) de la journée, **fermeture comprise**.

    Une journée de n activités localisées rend n paires, la dernière allant de la dernière
    activité à la première.
    """
    paires: list[tuple[Activity, Activity]] = []
    for courante in activites:
        suivante = activite_suivante(activites, courante)
        if suivante is not None:
            paires.append((courante, suivante))
    return paires
