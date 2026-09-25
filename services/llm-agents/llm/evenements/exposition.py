"""Qui est touché — ticket 100, lot 1.

Trois règles livrées, reprises telles quelles du ticket 079. La quatrième, `foyers`, arrive au
lot 2 : elle a besoin de `Person.household_id`, que le lot 1 fait remonter jusqu'au runtime.

Une règle inconnue est **refusée au chargement** plutôt qu'ignorée, sans quoi une faute de frappe
produirait un événement qui ne touche personne et un run entier sans le moindre symptôme.

Le tirage est DÉTERMINISTE et indépendant de l'ordre d'arrivée des observations. Un tirage qui
dépendrait de l'ordre ferait de deux rejeux du même scénario deux expériences différentes.
"""

from __future__ import annotations

import hashlib

# `foyers` est déclarée ici pour que le refus du lot 1 puisse nommer la règle et dire où elle
# arrive, au lieu de la traiter comme une faute de frappe.
REGLES_EXPOSITION: tuple[str, ...] = ("mode", "tirage", "agents", "foyers")
REGLES_LIVREES: tuple[str, ...] = ("mode", "tirage", "agents", "foyers")


def tirage_stable(graine: int, evenement_id: str, cible: str) -> float:
    """Un réel de [0, 1[ reproductible, fonction de la seule déclaration et de la cible.

    Même formule qu'au 079 — huit chiffres hexadécimaux du SHA-256, divisés par 0xFFFFFFFF.
    Elle ne change pas : la changer redistribuerait les exposés de toutes les campagnes déjà
    jouées, et leurs témoins internes avec eux.
    """
    empreinte = f"{graine}:{evenement_id}:{cible}"
    return int(hashlib.sha256(empreinte.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF


def expose(exposition, evenement_id: str, person_id: str, mode: str | None) -> tuple[bool, str]:
    """Cet agent est-il exposé à cette arrivée, et pour quelle raison ?

    Rend toujours une RAISON, y compris quand la réponse est non : le non est le témoin interne
    du run, et un témoin qu'on ne sait pas nommer ne se dépouille pas.
    """
    if exposition.regle == "mode":
        if mode and mode in exposition.modes:
            return True, f"mode:{mode}"
        return False, f"mode:{mode or 'inconnu'}"

    if exposition.regle == "agents":
        if str(person_id) not in exposition.agents:
            return False, "non_designe"
        # `modes` était PARSÉ, validé, puis ignoré par cette branche : un champ accepté et sans
        # effet est pire qu'un champ refusé, car rien ne le signale. Déclaré, il restreint
        # l'agent désigné aux trajets faits dans ces modes. Le cas qui l'exige : un incident de
        # VOITURE posé sur un agent multimodal, qui lisait sinon « the engine made a grinding
        # noise » au retour d'un trajet en bus.
        if exposition.modes and (not mode or mode not in exposition.modes):
            return False, f"designe:mode:{mode or 'inconnu'}"
        return True, "designe"

    if exposition.regle == "foyers":
        # La règle `foyers` ne se résout pas sur un agent seul : elle tire des lecteurs par
        # ménage, ce qui demande la population entière. Le registre l'a fait une fois pour
        # toutes (`lecteurs()`), et ce qui arrive ici est le verdict déjà pris.
        raise RuntimeError(
            "la règle `foyers` se résout par `lecteurs(population)`, jamais agent par agent"
        )

    # tirage
    if tirage_stable(exposition.graine, evenement_id, str(person_id)) < exposition.part:
        return True, f"tirage:{exposition.part:.2f}"
    return False, "tirage:epargne"


# Un article de presse se lit par un ADULTE du foyer (décision du 2026-09-24) : un enfant de
# neuf ans tiré lecteur dans une famille de quatre ferait porter la mesure de transmission sur
# un agent qui ne décide pas des déplacements du foyer.
AGE_ADULTE = 18


def age_de(personne) -> int | None:
    """L'âge déclaré par la population (`identity.traits_json.age`), ou None s'il manque."""
    traits = getattr(getattr(personne, "identity", None), "traits_json", None) or {}
    try:
        return int(traits.get("age"))
    except (TypeError, ValueError):
        return None


def lecteurs(exposition, evenement_id: str, population) -> dict[str, tuple[str, str]]:
    """Qui lit, dans quel foyer, et pour quelle raison — règle `foyers` (ticket 100, lot 2).

    Rend `{person_id: (household_id, raison)}`.

    UN LECTEUR PAR FOYER par défaut (059 Q2), et c'est ce qui donne son objet à l'étage 3 : le
    co-résident non exposé est le TÉMOIN INTERNE du dispositif. Si tout le monde lisait, il n'y
    aurait plus personne chez qui observer ce qui se transmet.

    Le tirage est déterministe et se fait sur l'ordre NUMÉRIQUE des identifiants, comme
    `extraire_sous_population.py` : un ordre d'insertion ferait de deux chargements de la même
    cohorte deux expériences différentes.

    LECTEURS DÉSIGNÉS (2026-09-25). Si `exposition.lecteurs` est déclaré, il remplace le tirage
    dans TOUS les foyers : un article sur le métro lu par le seul adulte qui ne le prend jamais
    ne mesure rien. Un désigné mineur, immobile ou absent du foyer n'est pas remplacé par un
    tiré : le foyer reste sans lecteur, et l'alarme dit de ne pas le compter comme exposé.
    """
    from loguru import logger

    designes = {str(d) for d in (getattr(exposition, "lecteurs", None) or ())}
    retenus: dict[str, tuple[str, str]] = {}
    par_foyer: dict[str, list] = {}
    for personne in population:
        foyer = getattr(personne, "household_id", None)
        if foyer and str(foyer) in exposition.foyers:
            par_foyer.setdefault(str(foyer), []).append(personne)

    for foyer in sorted(exposition.foyers):
        membres = par_foyer.get(foyer) or []
        mobiles = [p for p in membres if not getattr(p, "immobile", False)]
        if not mobiles:
            logger.error(
                f"[ALARME] [evenements] « {evenement_id} » : le foyer {foyer} est déclaré "
                f"exposé mais ne compte AUCUN membre mobile dans la population chargée "
                f"({len(membres)} membre(s) présent(s)). Personne n'y lira : ne pas compter ce "
                f"foyer comme exposé dans l'analyse."
            )
            continue
        # Seuls les adultes lisent. Un âge ABSENT n'exclut pas : on ne sait pas, et l'écarter
        # viderait sans bruit les populations qui ne le portent pas ; il se signale en revanche.
        mineurs = [p for p in mobiles if (a := age_de(p)) is not None and a < AGE_ADULTE]
        sans_age = [str(p.person_id) for p in mobiles if age_de(p) is None]
        adultes = [p for p in mobiles if p not in mineurs]
        if sans_age:
            logger.warning(
                f"[evenements] « {evenement_id} » : foyer {foyer} — âge inconnu pour "
                f"{sans_age}, admis au tirage des lecteurs faute de pouvoir les écarter."
            )
        if not adultes:
            logger.error(
                f"[ALARME] [evenements] « {evenement_id} » : le foyer {foyer} est déclaré "
                f"exposé mais ne compte AUCUN adulte mobile (âges "
                f"{[age_de(p) for p in mobiles]}). Personne n'y lira : ne pas compter ce foyer "
                f"comme exposé dans l'analyse."
            )
            continue
        if designes:
            _designes_du_foyer(designes, foyer, membres, adultes, evenement_id, retenus, logger)
            continue
        ordonnes = sorted(adultes, key=lambda p: (len(str(p.person_id)), str(p.person_id)))
        combien = max(1, min(int(exposition.lecteurs_par_foyer), len(ordonnes)))
        classes = sorted(
            ordonnes,
            key=lambda p: tirage_stable(
                exposition.graine, evenement_id, f"{foyer}:{p.person_id}"
            ),
        )
        for personne in classes[:combien]:
            retenus[str(personne.person_id)] = (foyer, f"foyer:{foyer}")
        ecartes = [str(p.person_id) for p in classes[combien:]]
        enfants = [str(p.person_id) for p in mineurs]
        logger.info(
            f"[evenements] « {evenement_id} » : foyer {foyer} — lecteur(s) "
            f"{[str(p.person_id) for p in classes[:combien]]}, co-résident(s) témoin(s) "
            f"{ecartes or 'aucun'}, mineur(s) hors tirage {enfants or 'aucun'}"
        )
    if designes:
        dans_les_foyers = {
            str(p.person_id) for membres in par_foyer.values() for p in membres
        }
        hors = sorted(designes - dans_les_foyers)
        if hors:
            logger.error(
                f"[ALARME] [evenements] « {evenement_id} » : lecteur(s) désigné(s) {hors} "
                f"absent(s) des foyers exposés {sorted(exposition.foyers)} de la population "
                f"chargée. Ils ne liront pas : vérifier la déclaration contre le MANIFEST."
            )
    if not retenus:
        logger.error(
            f"[ALARME] [evenements] « {evenement_id} » : règle `foyers` sur "
            f"{sorted(exposition.foyers)} et AUCUN lecteur retenu. L'événement n'aura lieu "
            f"pour personne, et le run entier se déroulera sans le moindre symptôme. "
            f"Vérifiez que la population chargée porte bien `household.id`."
        )
    return retenus


def _designes_du_foyer(designes, foyer, membres, adultes, evenement_id, retenus, logger) -> None:
    """Retient les lecteurs désignés de ce foyer, s'ils sont des adultes mobiles."""
    nommes = [p for p in membres if str(p.person_id) in designes]
    if not nommes:
        logger.error(
            f"[ALARME] [evenements] « {evenement_id} » : lecteurs désignés {sorted(designes)}, "
            f"AUCUN dans le foyer {foyer} (membres {[str(p.person_id) for p in membres]}). "
            f"Personne n'y lira, aucun tirage ne le remplace : ne pas compter ce foyer comme "
            f"exposé dans l'analyse."
        )
        return
    admis = [p for p in nommes if p in adultes]
    for p in nommes:
        if p not in admis:
            motif = "immobile" if getattr(p, "immobile", False) else f"mineur ({age_de(p)} ans)"
            logger.error(
                f"[ALARME] [evenements] « {evenement_id} » : lecteur désigné {p.person_id} du "
                f"foyer {foyer} écarté — {motif}. Aucun tirage ne le remplace."
            )
    for p in admis:
        retenus[str(p.person_id)] = (foyer, f"foyer:{foyer}")
    if admis:
        temoins = [str(p.person_id) for p in membres if p not in admis]
        logger.info(
            f"[evenements] « {evenement_id} » : foyer {foyer} — lecteur(s) DÉSIGNÉ(S) "
            f"{[str(p.person_id) for p in admis]}, co-résident(s) témoin(s) {temoins or 'aucun'}"
        )
