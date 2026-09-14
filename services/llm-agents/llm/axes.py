"""Axes d'un souvenir — ticket 071, lot 2.

Un souvenir ne porte pas que du texte : il porte **quatre axes typés** — l'objet, le lieu, le
créneau, le motif — plus la météo du jour. Ces axes servent à deux choses :

- le **vivier par objet** du rappel : pour chaque mode offert dans les options d'une décision,
  aller chercher directement les souvenirs qui portent ce mode, sans passer par le plongement ;
- l'**affinité** au classement, en BONUS et jamais en veto.

**La normalisation se fait à l'ÉCRITURE, jamais à la lecture.** Sans cela, deux graphies de la
même ligne ne se rencontrent jamais ; et normaliser au rappel referait le même travail à chaque
décision, sur le chemin critique.

Un axe non résolu vaut `None`, et `None` ne s'apparie avec **rien** — pas même avec un autre
`None`. Deux inconnues ne font pas une correspondance : c'est ce qui empêche l'absence de mesure
de produire de la ressemblance.
"""

from __future__ import annotations

from datetime import datetime

from loguru import logger


def _hierarchie():
    """Hiérarchie des modes, chargée à la PREMIÈRE utilisation et non à l'import.

    ⚠ Ce n'est pas un détail de style. Chargée à l'import, elle fige la configuration du
    dépôt au moment où ce module entre dans l'arbre d'imports — ce qui se produisait avant
    que les tests n'aient posé la leur, et faisait échouer sept tests de périmètre et de
    couronne sans rapport avec la mémoire. Un module utilitaire ne doit rien figer en
    arrivant.
    """
    global _HIERARCHIE
    if _HIERARCHIE is None:
        from mobility_core.mode_hierarchy import hierarchy

        _HIERARCHIE = hierarchy()
    return _HIERARCHIE


_HIERARCHIE = None

# Compteur des modes que la hiérarchie ignore. Un mode inconnu doit être COMPTÉ et signalé,
# jamais rangé d'office dans le fourre-tout d'à côté — c'est la règle de `family_of`, et une
# part modale fausse est plus coûteuse qu'une part modale absente (ticket 022).
MODES_INCONNUS: dict[str, int] = {}


def mode_canonique(mode_label: str | None) -> str | None:
    """Mode canonique du MODE PRINCIPAL d'un trajet, depuis son étiquette de jambes.

    « foot,bus,foot » rend `public_transport`, et non `walking` : c'est la famille de meilleur
    rang présente qui désigne le trajet, selon la hiérarchie AUAT/CEREMA qui fait autorité dans
    le dépôt. Une cascade écrite ici en dupliquerait une sixième, et une liste incomplète rend
    un chiffre plausible et faux.

    ⚠ Cette fonction LIT l'étiquette de mode, elle ne la remplace pas. `parse_option_modes`
    relit ces étiquettes dans le texte du prompt : les changer casserait la calibration et les
    parts modales.
    """
    if not mode_label:
        return None
    jambes = [j.strip() for j in str(mode_label).split(",") if j.strip()]
    if not jambes:
        return None
    canonique = _hierarchie().primary_canonical(jambes)
    if canonique is None:
        clef = ",".join(jambes)
        MODES_INCONNUS[clef] = MODES_INCONNUS.get(clef, 0) + 1
        if MODES_INCONNUS[clef] == 1:
            logger.warning(
                f"[axes] mode inconnu de la hiérarchie : « {clef} » — axe_objet laissé vide "
                f"plutôt que rangé dans un fourre-tout"
            )
    return canonique


def normaliser_lieu(texte: str | None) -> str | None:
    """Arrêt, ligne ou quartier, ramené à une forme unique.

    « Line: 401 », « line:401 » et « LINE : 401 » désignent la même ligne : sans cette
    normalisation, trois souvenirs de la même ligne ne se rencontrent jamais.
    """
    if texte is None:
        return None
    brut = str(texte).strip().lower()
    for prefixe in ("line:", "line :", "ligne:", "ligne :", "stop:", "stop :"):
        if brut.startswith(prefixe):
            brut = brut[len(prefixe):]
            break
    brut = " ".join(brut.replace(":", " ").replace("_", " ").split())
    return brut or None


def creneau_de(quand: datetime | None) -> str | None:
    """Quatre créneaux, sur les tranches horaires DÉJÀ en service dans le dépôt.

    Mêmes bornes que `categorize_date_time_short` : 6-12, 12-18, 18-24, le reste étant la nuit.
    En choisir d'autres suffirait à rendre deux dispositifs incomparables.
    """
    if quand is None:
        return None
    heure = quand.hour
    if 6 <= heure < 12:
        return "matin"
    if 12 <= heure < 18:
        return "midi"
    if 18 <= heure < 24:
        return "soir"
    return "nuit"


def normaliser_motif(purpose: str | None) -> str | None:
    """Motif du déplacement, dans le vocabulaire des activités."""
    if not purpose:
        return None
    return str(purpose).strip().lower() or None


# Cascade météo, dans cet ordre : ce qui change le plus une décision de mode passe devant. La
# neige prime sur la pluie, la pluie sur la température. Un jour chaud ET pluvieux est classé
# `pluie` : c'est la pluie qui fait renoncer au vélo, pas les degrés.
SEUIL_PLUIE_MM = 0.2
SEUIL_CANICULE_C = 30.0
SEUIL_FROID_C = 0.0
_CODES_NEIGE = frozenset({71, 73, 75, 77, 85, 86})


def meteo_de(w: dict | None) -> str | None:
    """Axe météo d'un souvenir, en cinq valeurs : neige, pluie, canicule, froid, sec.

    Cinq valeurs et pas davantage : l'axe sert à APPARIER deux journées, pas à décrire le
    temps. Un vocabulaire plus fin ferait que deux journées semblables ne se rencontrent
    jamais, ce qui est exactement le défaut que les axes corrigent.
    """
    if not w:
        return None
    try:
        code = int(w.get("weather_code") or -1)
        precip = float(w.get("precip_mm") or 0.0)
        temp = float(w.get("temperature"))
    except (TypeError, ValueError):
        return None
    if code in _CODES_NEIGE:
        return "neige"
    if precip >= SEUIL_PLUIE_MM:
        return "pluie"
    if temp >= SEUIL_CANICULE_C:
        return "canicule"
    if temp <= SEUIL_FROID_C:
        return "froid"
    return "sec"


# ── Affinités ────────────────────────────────────────────────────────────────────

POIDS_AXE_OBJET = 0.50
POIDS_AXE_LIEU = 0.20
POIDS_AXE_CRENEAU = 0.15
POIDS_AXE_MOTIF = 0.15


def _concorde(a: str | None, b) -> bool:
    """L'axe `a` du souvenir concorde-t-il avec ce que porte le contexte courant ?

    `None` ne s'apparie avec rien, pas même avec `None`. Faire concorder deux inconnues
    produirait de la ressemblance à partir d'une absence de mesure — motif récurrent à traquer
    dans ce projet, où l'absence de mesure produit volontiers le score parfait.

    Le côté courant peut être une valeur unique ou un ENSEMBLE. Une décision d'itinéraire offre
    plusieurs modes : un souvenir de vélo est pertinent dès que le vélo figure parmi les options,
    et exiger l'égalité avec un seul mode « courant » n'aurait pas de sens — il n'y en a pas un.
    """
    if a is None or b is None:
        return False
    if isinstance(b, (set, frozenset, list, tuple)):
        return a in b
    return a == b


def affinite_axes(
    objet: str | None = None,
    lieu: str | None = None,
    creneau: str | None = None,
    motif: str | None = None,
    *,
    objet_courant: str | None = None,
    lieu_courant: str | None = None,
    creneau_courant: str | None = None,
    motif_courant: str | None = None,
) -> float:
    """Affinité d'un souvenir avec le contexte courant, sur [0, 1].

    **BONUS, jamais veto.** Un axe discordant contribue zéro : il ne retranche rien, et un
    souvenir dont aucun axe ne concorde reste classable sur ses quatre autres composantes.
    C'est ce qui permet à une chute à vélo du matin d'atteindre la décision du soir, alors
    qu'aucun de leurs contextes ne coïncide. C'est aussi la règle de l'appariement partiel
    d'ACT-R : un attribut discordant applique une pénalité, il n'exclut pas.
    """
    total = 0.0
    if _concorde(objet, objet_courant):
        total += POIDS_AXE_OBJET
    if _concorde(lieu, lieu_courant):
        total += POIDS_AXE_LIEU
    if _concorde(creneau, creneau_courant):
        total += POIDS_AXE_CRENEAU
    if _concorde(motif, motif_courant):
        total += POIDS_AXE_MOTIF
    return total


def affinite_meteo(meteo: str | None, meteo_courante: str | None) -> float:
    """Appariement d'attribut discret sur la MÉTÉO, sur [0, 1].

    ⚠ **Arbitrage du 2026-09-14, issue A** (`specs/ticket_071/tests_lot2.md` § 8.1). Le ticket
    prévoyait ici une « affinité catégorielle » appariant mode, créneau, motif et météo — mais
    trois de ces quatre attributs sont DÉJÀ les axes d'`affinite_axes`. Ils auraient été comptés
    deux fois, avec des poids différents, sans que rien ne le dise : un score dont deux termes
    mesurent la même chose n'est plus interprétable, et la calibration des cinq poids aurait
    porté sur des composantes corrélées par construction.

    La composante se réduit donc au seul attribut qu'elle apporte, la météo — et il a du sens :
    un souvenir de pluie éclaire une décision prise sous la pluie. Les cinq composantes
    redeviennent disjointes, et leur nombre ne change pas.
    """
    return 1.0 if _concorde(meteo, meteo_courante) else 0.0
