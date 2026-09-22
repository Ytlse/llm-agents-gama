"""L'agent juge ce qu'il vient de vivre ou de lire — ticket 100, lot 3, décision D4.

POURQUOI CE MODULE
------------------
Jusqu'ici la gravité d'un événement était purement déterministe : un retard, une correspondance
ratée, un incident réseau. C'est objectif et cela ne coûte rien — mais cela ne sait rien dire
d'un article de presse, qui ne fait subir aucun retard et vaudrait donc **zéro**, c'est-à-dire
exactement la valeur d'un trajet parfait. Une entrée à zéro vit 2,8 jours : son silence
passerait pour une absence d'effet alors qu'il ne mesurerait que la durée de vie qu'on lui a
donnée.

Le jugement donne son poids à ce que la simulation ne mesure pas. Il s'applique aux **deux**
régimes (D4), et depuis la décision **D7 du 2026-09-22** la gravité d'une entrée est
l'estimation de l'agent, **et elle seule** — dans les deux canaux.

CE QUE D7 RETIRE, ET LA GARDE QUI LE REMPLACE
----------------------------------------------
`gravite_concept` appliquait `I = max(I_llm, I_det)` sous un commentaire « NON NÉGOCIABLE » : un
modèle qui jugeait « anodin » un dépannage de trente minutes ne pouvait pas le dégrader. D7
supprime cette protection, et ce n'est pas neutre — un souvenir de 2,8 jours là où le plancher
en imposait quinze ne se distingue plus d'un événement qui n'a rien produit.

Ce qui remplace le plancher ne corrige rien : **l'écart `estimée − déterministe` est journalisé
à chaque jugement**, et une `[ALARME]` se lève quand l'agent sous-estime de plus d'un échelon.
On veut **savoir**, pas rattraper. Corriger en silence rétablirait le plancher sous un autre
nom, et la campagne mesurerait de nouveau la garde au lieu de mesurer l'agent.

⚠ Le terme déterministe ne disparaît pas du dispositif : le retard reste subi, il décale la
journée, contraint les trajets suivants, et entre dans ce que l'agent raconte le soir. Il cesse
seulement de peser sur la gravité.

LE REFUS EST FRANC, ET IL NE RÉUTILISE PAS `gravite_jugee`
----------------------------------------------------------
`llm/gravite.py:gravite_jugee` retombe **silencieusement** sur `None` quand le modèle rend un
échelon hors grille, et c'est voulu là-bas : une réponse aberrante ne doit pas faire perdre une
réflexion entière portant cinq concepts. Ici, l'objet de l'appel EST l'échelon. Une réponse
hors grille ne laisse rien à sauver, et un repli fabriquerait une exposition qui n'a pas été
jugée en la comptant comme les autres (059, Q17).

Donc : refus, `[ALARME]`, et l'exposition est déclarée non avenue. Aucune valeur médiane,
aucune retombée sur la gravité déterministe, aucun échelon par défaut.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from llm.gravite import ALIAS_NIVEAUX, NIVEAUX, ancres_anglaises, borne_0_1
from settings import settings

CATEGORIE = "evenement_jugement"

# Valences du schéma de réflexion, reprises telles quelles (D3 : une seule échelle).
VALENCES: tuple[str, ...] = ("negative", "neutral", "positive")
# Le vocabulaire français de `MemoryEntry.valence`, où elles atterrissent.
VALENCE_FR: dict[str, str] = {
    "negative": "negative", "neutral": "neutre", "positive": "positive",
}


class JugementRefuse(ValueError):
    """Le modèle n'a pas répondu dans la grille. L'exposition est non avenue."""


@dataclass(frozen=True)
class Jugement:
    """Ce que l'agent dit de l'événement, et la gravité qui en sort."""

    intensite: str          # l'un des cinq échelons, vocabulaire français canonique
    valence: str            # `negative` | `neutre` | `positive`
    modes: tuple[str, ...]  # les modes sur lesquels cela porte, éventuellement aucun
    importance_estimee: float
    # Depuis D7, `importance_retenue == importance_estimee`. Les deux champs RESTENT
    # distincts, et ce n'est pas une redondance : la trace doit continuer de dire ce que
    # l'agent a estimé ET ce qui a été retenu. Le jour où une garde reviendrait, elle se
    # verrait dans l'écart entre les deux colonnes plutôt que dans un changelog.
    importance_retenue: float
    # L'écart au fait mesuré, journalisé et jamais appliqué. Négatif = l'agent sous-estime.
    ecart_au_fait: float = 0.0


def resoudre_intensite(brut, evenement_id: str, person_id: str, jour: int) -> str:
    """L'échelon rendu par le modèle, ramené au vocabulaire canonique. Lève sinon.

    Les deux vocabulaires sont acceptés, anglais et français : le dispositif s'adresse au
    modèle en anglais (ticket 074) mais l'échelle a été définie et discutée en français, et un
    modèle qui répondrait dans l'autre langue doit être compris plutôt que rejeté.
    """
    clef = str(brut or "").strip().lower()
    clef = ALIAS_NIVEAUX.get(clef, clef)
    if clef not in NIVEAUX:
        logger.error(
            f"[ALARME] [evenements] « {evenement_id} » : le modèle a rendu l'échelon "
            f"« {brut} », hors des cinq échelons {sorted(ALIAS_NIVEAUX)}. AUCUN repli n'est "
            f"appliqué : l'exposition de {person_id} au jour {jour} n'a PAS eu lieu. Ne pas "
            f"la compter dans l'analyse."
        )
        raise JugementRefuse(f"échelon « {brut} » hors grille")
    return clef


def resoudre_valence(brut) -> str:
    """La valence, ramenée au vocabulaire de `MemoryEntry`. Neutre par défaut.

    Contrairement à l'échelon, une valence absente ne rend pas l'appel vain : la gravité tient
    sans elle, et `neutre` est la valeur que porte déjà toute entrée non qualifiée. Un défaut
    ici ne fabrique donc rien — il ne fait que ne rien ajouter.
    """
    clef = str(brut or "").strip().lower()
    if clef not in VALENCES:
        if clef:
            logger.warning(
                f"[evenements] valence « {brut} » hors de {VALENCES} — tenue pour neutre"
            )
        return "neutre"
    return VALENCE_FR[clef]


def resoudre_modes(brut) -> tuple[str, ...]:
    """Les modes touchés, filtrés sur la hiérarchie du dépôt.

    Un mode inconnu est ÉCARTÉ et compté, jamais laissé passer : le vocabulaire des modes a
    déjà coûté trente jours au ticket 077, où deux listes coexistaient sans que rien ne le dise.
    """
    from llm.axes import mode_canonique

    retenus, ecartes = [], []
    for brut_mode in brut or []:
        canonique = mode_canonique(str(brut_mode))
        if canonique and canonique == str(brut_mode).strip().lower():
            retenus.append(canonique)
        else:
            ecartes.append(str(brut_mode))
    if ecartes:
        logger.warning(
            f"[evenements] mode(s) {ecartes} hors de la hiérarchie du dépôt — écartés du "
            f"jugement. Le concept ne portera pas ces modes."
        )
    return tuple(dict.fromkeys(retenus))


def charge_utile(person_id: str, perception: str, texte: str) -> dict:
    """La charge utile de l'appel. Les ancres viennent de `gravite.py`, pas du gabarit.

    Le gabarit de `stm_reflection` les recopie, et `gravite.py` note que « les ancres
    textuelles vivent dans le gabarit » : deux sources pour une même échelle, qui divergeront
    le jour où l'une bouge. Celle-ci n'en a qu'une — et si l'échelle change, le prompt suit
    sans qu'on ait à y penser.
    """
    from urban_mobility_agents.utils.routage import instances_pour

    return {
        "category": CATEGORIE,
        "instances_admises": instances_pour(CATEGORIE),
        "agents": [
            {"agent_id": str(person_id), "perception": perception, "evenement": texte}
        ],
        "parameters": {
            "temperature": 0.2,
            # ⚠ 256 ÉTAIT TROP SERRÉ, et le symptôme ne ressemblait pas à sa cause. Les modèles
            # de raisonnement (`gpt-oss-120b`, `gpt-oss-20b`) dépensent leur réflexion DANS ce
            # budget : mesuré le 2026-09-22 sur Groq, 240 à 330 jetons de raisonnement avant le
            # premier caractère de JSON. À 256, le fournisseur rend « max completion tokens
            # reached before generating a valid document » — ou, quand la réflexion tient de
            # justesse, un JSON valide mais DÉGRADÉ, où le modèle prend la première valeur de
            # chaque énumération. C'est ainsi que 19 appels sur 38 sont revenus vides et que les
            # 11 autres ont tous répondu `anodin`, premier échelon de la liste.
            #
            # 1024 tient large : 290 jetons mesurés au pire sur `gpt-oss-20b`, 66 sur `qwen3.8`.
            # Le plafond ne coûte rien — seuls les jetons émis sont facturés et comptés dans
            # l'OTPM. Ce qu'il achète, c'est que le budget cesse d'être la variable qui décide
            # de la gravité à la place de l'agent.
            "max_tokens": 1024,
            # Les ancres sont passées sous le libellé ANGLAIS du schéma de sortie. Les donner
            # en français pendant que l'énumération n'accepte que l'anglais revenait à demander
            # au modèle de choisir dans une liste qu'on lui interdisait ensuite d'écrire.
            "ancres": ancres_anglaises(),
        },
    }


async def juger(
    llm_client,
    person_id: str,
    perception: str,
    texte: str,
    gravite_deterministe: float,
    evenement_id: str,
    jour: int,
) -> Jugement:
    """Un appel, un événement. Lève `JugementRefuse` plutôt que de rendre une valeur inventée.

    ⚠ Pas de délai de repli, pas de valeur par défaut, pas de file à part. En pénurie de quota,
    la file ordinaire fait attendre — et on attend. Un jugement rendu par défaut serait une
    mesure fabriquée, et ce dépôt en a déjà payé le prix.
    """
    reponse = await llm_client.execute(charge_utile(person_id, perception, texte))
    if not reponse or not getattr(reponse, "agents", None):
        logger.error(
            f"[ALARME] [evenements] « {evenement_id} » : aucune réponse au jugement de "
            f"{person_id} au jour {jour}. L'exposition n'a PAS été jugée."
        )
        raise JugementRefuse("réponse vide")

    rendu = reponse.agents[0]
    intensite = resoudre_intensite(
        getattr(rendu, "severity", None), evenement_id, person_id, jour
    )
    estimee = NIVEAUX[intensite]
    # ── D7, 2026-09-22 : la gravité est celle de l'AGENT, et elle seule ─────────────────
    # `gravite_concept(estimee, deterministe)` prenait le maximum des deux. Elle n'est plus
    # appelée ici — elle garde son rôle pour les concepts, où le plancher d'un groupe consommé
    # reste une règle de la mémoire, hors du périmètre de ce ticket.
    retenue = borne_0_1(estimee)
    mesure = float(gravite_deterministe or 0.0)
    ecart = round(retenue - mesure, 4)

    jugement = Jugement(
        intensite=intensite,
        valence=resoudre_valence(getattr(rendu, "valence", None)),
        modes=resoudre_modes(getattr(rendu, "modes", None)),
        importance_estimee=estimee,
        importance_retenue=retenue,
        ecart_au_fait=ecart,
    )
    logger.info(
        f"[evenements] « {evenement_id} » jugé par {person_id} (jour {jour}) : "
        f"{intensite} ({estimee:.2f}), valence {jugement.valence}, modes "
        f"{list(jugement.modes) or 'aucun'} — gravité retenue {retenue:.2f}"
        + (f", fait mesuré {mesure:.2f}, écart {ecart:+.2f}" if mesure else "")
    )
    # La garde qui remplace le plancher : elle DIT, elle ne corrige pas. Corriger en silence
    # rétablirait le plancher sous un autre nom, et la campagne mesurerait de nouveau la garde
    # au lieu de mesurer l'agent.
    seuil = float(getattr(settings.agent, "memoire__ecart_jugement_alarme", 0.30))
    if mesure and ecart <= -seuil:
        from llm.gravite import force_initiale

        logger.error(
            f"[ALARME] [evenements] « {evenement_id} » : {person_id} juge « {intensite} » "
            f"({estimee:.2f}) un fait mesuré à {mesure:.2f} — il SOUS-ESTIME de {-ecart:.2f}, "
            f"plus d'un échelon. La valeur n'est PAS corrigée (décision D7) : le souvenir vivra "
            f"{force_initiale(retenue):.1f} jours au lieu de {force_initiale(mesure):.1f}. "
            f"Si ce cas se répète, l'effet mesuré dépend de la qualité du jugement et non de "
            f"l'événement."
        )
    return jugement
