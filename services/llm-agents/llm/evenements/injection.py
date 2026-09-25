"""Les deux prises — ticket 100, lot 1.

Une seule livrée : `arrivee`.

`a_l_arrivee` s'applique APRÈS la décision. L'agent a choisi en voyant l'offre nominale, il
encaisse ensuite. C'est le régime SUBI, et c'est ce qui rend le jour de l'événement muet sur le
choix : tout l'effet observé les jours suivants est imputable au souvenir, et à rien d'autre.

`au_reveil` s'appliquera AVANT la première décision de la journée. C'est le lot 2, et la
différence entre les deux n'est pas un détail d'implémentation : elle est le cœur du contraste
entre les deux régimes que le chapitre 7 mesure.

POURQUOI DEUX GESTES, ET NON UN SEUL
------------------------------------
Le ticket annonce « une seule fonction dépose l'entrée ». À la lecture du contrôleur, ce n'est pas
ce qui se passe et ce ne peut pas l'être : à l'arrivée, le texte est **joint** à l'observation que
GAMA vient de rendre, et la gravité porte la SOMME du retard mesuré et du retard injecté. Écrire
une entrée séparée changerait le nombre d'entrées, leur horodatage et la gravité de chacune — le
test en or échouerait, et les chiffres du § 7.2 ne vaudraient plus.

Ce qui est commun aux deux prises, et c'est le vrai gain du ticket, ce n'est donc pas l'écriture :
c'est la **qualification**. Gravité — l'estimation de l'agent, et elle seule depuis D7 —,
valence, origine, axes, force, durée de service : une seule route, quel que soit le canal.
"""

from __future__ import annotations

from llm.evenements.declaration import EvenementApplique

# Préfixe du texte joint à l'observation d'arrivée. Inchangé depuis le ticket 079 : il apparaît
# dans la mémoire de tous les agents des runs déjà archivés, et le déplacer rendrait les deux
# corpus incomparables au mot près.
PREFIXE_VECU = "[ INCIDENT ]"

# Préfixe du canal `lu`, posé ici pour que les deux vivent au même endroit. Utilisé au lot 2.
PREFIXE_LU = "[ PRESSE ]"

# Ticket 111 — ce qu'un membre du foyer a ENTENDU du lecteur. Rendu mot pour mot, c'est ce qui
# permet au contrôle après run d'être exact, sans heuristique.
PREFIXE_FOYER = "[ FOYER ]"


def a_l_arrivee(registre, person_id: str, mode: str | None, timestamp: int):
    """L'événement applicable à cette arrivée, ou `None`.

    Ne fait rien d'autre que consulter le registre : la décision d'écrire appartient à
    l'appelant, qui seul sait ce que l'observation contient par ailleurs.
    """
    if registre is None:
        return None
    return registre.applique(person_id, mode, timestamp)


def joindre(texte_observation: str, applique: EvenementApplique) -> str:
    """Le texte de l'événement, ANNEXÉ à l'observation — jamais substitué.

    L'agent doit garder ce que la simulation a mesuré, et y ajouter ce qu'il a vécu. Remplacer
    l'un par l'autre lui ferait perdre l'heure, le mode et la destination de son propre trajet.
    """
    prefixe = PREFIXE_VECU if applique.canal == "vecu" else PREFIXE_LU
    return f"{texte_observation}\n{prefixe} {applique.texte}"


def au_reveil(registre, population, timestamp: int) -> list:
    """Ce que les agents reçoivent ce matin, AVANT leur première décision.

    Rend une liste de `(person_id, EvenementApplique)`, vide les autres jours et vide quand
    l'événement déclaré n'est pas de ce moment-là.

    ⚠ **Ce n'est pas le point d'injection du choc**, et la différence est le cœur du régime : un
    choc s'applique à l'arrivée, après la décision ; un article est su **avant** de décider.
    C'est le seul contraste que le chapitre 7 mesure, et il n'existe que si les deux prises
    restent à leur place.
    """
    if registre is None:
        return []
    return registre.dus_au_reveil(timestamp, population)


def entree_de_lecture(applique) -> str:
    """Le texte tel qu'il entre en mémoire courte, préfixé.

    Contrairement à la prise `arrivee`, il n'y a RIEN à quoi joindre le texte : aucune
    observation n'a eu lieu, l'agent dort encore. L'entrée est donc autonome, et c'est la
    seule différence d'écriture entre les deux prises.
    """
    prefixe = PREFIXE_LU if applique.canal == "lu" else PREFIXE_VECU
    if applique.canal == "lu":
        return ligne_de_lecture(applique.texte)
    return f"{prefixe} {applique.texte}"


def ligne_de_lecture(texte: str) -> str:
    """L'entrée de lecture, construite depuis le seul texte — ticket 111.

    La ligne servie au prompt pendant les jours de service et l'entrée de mémoire longue sont
    la MÊME chaîne. C'est ce qui permet au bloc de ne pas la servir deux fois quand l'agent a
    jugé l'article grave, et au contrôle après run de la retrouver mot pour mot.
    """
    return f"{PREFIXE_LU} This morning I read in the paper: « {texte} »"


def ligne_de_foyer(message: str, prenom_lecteur: str, mineur: bool) -> str:
    """Ce qu'un membre informé voit, et garde en mémoire — ticket 111.

    Pour un mineur, c'est la DÉCISION DES PARENTS (D5) : dans la réalité, ce sont eux qui
    décident du trajet d'un enfant, et une version simplifiée de l'article ne le ferait pas
    changer. Le nom de l'autre parent n'est pas dit : la population ne porte pas la filiation.
    """
    if mineur:
        return f"{PREFIXE_FOYER} My parents decided this morning: « {message} »"
    return f"{PREFIXE_FOYER} {prenom_lecteur or 'Someone at home'} told me this morning: « {message} »"
