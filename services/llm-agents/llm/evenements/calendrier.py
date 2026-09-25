"""Quand l'événement a lieu — ticket 100, lot 1.

Deux abscisses, et il faut les deux.

`jour_du_run` compte les jours depuis le début du run, 1 pour le premier. Il se lit sur l'ANCRE
du ticket 075 et **jamais** sur le premier timestamp observé : après une reprise à chaud, GAMA
rejoue depuis son t0, et se réancrer ferait reculer l'événement de plusieurs jours au milieu du
run.

`jour_relatif` compte les jours écoulés depuis le premier jour de l'événement : −2, −1, 0, +1…
Il est défini **tous** les jours du run, y compris longtemps avant et longtemps après : c'est
l'abscisse de toutes les courbes de décrochage et de retour, et une abscisse qui n'existerait que
les jours d'événement ne tracerait rien.

La fenêtre tirée par foyer (059 Q5) arrive au lot 2 ; ce module porte ici la seule forme livrée
par le 079, la liste de jours déclarés.
"""

from __future__ import annotations


def jour_du_run(timestamp: int) -> int:
    """1 pour le premier jour simulé du run."""
    from urban_mobility_agents.utils.ancre_run import jours_ecoules

    return int(jours_ecoules(int(timestamp))) + 1


def jour_tire(graine: int, evenement_id: str, cible: str, fenetre: tuple[int, int]) -> int:
    """Le jour de parution de CETTE cible, tiré dans la fenêtre déclarée (059 Q5).

    Deux foyers ne lisent pas le même jour. C'est ce qui empêche un effet de calendrier — un
    lundi, une veille de vacances, une journée de pluie — de se confondre avec l'effet de
    l'article : si tous lisaient le même matin, les deux seraient rigoureusement inséparables.

    Déterministe et stable d'un run à l'autre, comme le tirage d'exposition et pour la même
    raison : deux rejeux du même scénario doivent être la même expérience.
    """
    from llm.evenements.exposition import tirage_stable

    debut, fin = int(fenetre[0]), int(fenetre[1])
    largeur = fin - debut + 1
    rang = int(tirage_stable(graine, evenement_id, f"parution:{cible}") * largeur)
    return debut + min(rang, largeur - 1)


def date_du_jour_run(jour: int):
    """La date murale du jour `jour` du run (1 = premier jour), ou `None` sans ancre.

    Lue sur l'ancre du ticket 075, comme `jour_du_run` : la même abscisse dans les deux sens.
    """
    from datetime import timedelta

    from sim_clock import wall_clock
    from urban_mobility_agents.utils.ancre_run import ancre

    debut = ancre()
    if debut is None:
        return None
    return wall_clock(int(debut)).date() + timedelta(days=int(jour) - 1)


def jours_de_service(debut, n: int, sans_week_end: bool) -> tuple:
    """Les `n` jours de DÉPLACEMENT qui commencent à `debut` — ticket 111, décision D3.

    `debut` compte comme jour 1 s'il est ouvrable. Quand aucun départ n'a lieu le week-end
    (`agent.no_weekend_departures`), samedi et dimanche sont sautés : un article lu un jeudi est
    servi jeudi, vendredi, lundi, mardi et mercredi. Sans cette règle, cinq jours calendaires ne
    donneraient que trois jours de décisions à un foyer qui lit un jeudi.

    Calendrier MURAL, déterministe : le résultat ne dépend pas du moment où la décision est
    pré-calculée, et c'est ce qui rend la ligne servie indépendante de l'horizon glissant.
    """
    from datetime import timedelta

    jours = []
    courant = debut
    while len(jours) < int(n):
        if not (sans_week_end and courant.weekday() >= 5):
            jours.append(courant)
        courant = courant + timedelta(days=1)
    return tuple(jours)
