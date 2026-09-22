import asyncio
import hashlib
import json
import os
import re
import time
import traceback
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import demjson3
import numpy as np
from experiences.decision import ordre_presentation
from helper import (
    categorize_date_time_short,
    get_weekday_category,
    humanize_date,
    humanize_date_short,
    humanize_time,
)
from llm.axes import (
    creneau_de,
    meteo_de,
    mode_canonique,
    normaliser_lieu,
    normaliser_motif,
)
from llm.cache import LlmSemanticCache
from llm import foyer
from llm.concepts import (
    CONCEPTS_MONTRES_PAR_PANIER,
    CONFIRMER,
    CONTREDIRE,
    CREER,
    PRECISER,
    normaliser_operation,
    panier_de,
)
from llm.gravite import (
    CONTRAINTES_MODE_FORCE,
    force_apres_rappel,
    gravite_concept,
    gravite_deterministe,
    gravite_jugee,
)
from llm.journal_memoire import journal
from llm.longterm import MultiUserLongTermMemory
from llm.memory import MemoryEntry, MemoryType
from llm.noyau import memoire_noyau
from urban_mobility_agents.utils.modeles import origine as origine_modele
from urban_mobility_agents.utils.routage import instances_pour, toutes_les_instances
from llm.reflection_store import ReflectionMemoStore
from llm.shortterm import UserShortTermMemory
from llm.trace_concepts import tracer_operation
from llm_gateway.sdk import LLMGatewayClient
from loguru import logger
from mobility_llm import prompt_manager as _mobility_prompt_manager
from mobility_llm.mode_choice import (
    UniformFallback,
    draw_index,
    mode_distribution,
    normalize_option_probabilities,
)
from models import Person, TravelPlan
from pydantic import BaseModel
from settings import settings
from sim_clock import gama_timestamp, wall_clock
from text_helper import env_ob_to_text
from urban_mobility_agents.agents.prompt_manager import PromptManager
from urban_mobility_agents.agents.prompt_types import PromptName
from urban_mobility_agents.utils import rejeu_decisions
from urban_mobility_agents.utils.ancre_run import jours_ecoules
from urban_mobility_agents.utils.history_log import HistoryStreamLog
from urban_mobility_agents.utils.pipeline_logger import PipelineLogger
from urban_mobility_agents.utils.reprise import gel_actif
from urban_mobility_agents.utils.weather_draw import (
    date_declaree,
    jours_eligibles,
    timestamp_meteo,
)
from urban_mobility_agents.utils.weather_loader import (
    get_weather,
    weather_to_natural_language,
)
from utils import create_background_task
from world.population import PersonScheduler

history_log = HistoryStreamLog.get_instance()


def log_llm_cache_hit(
    agent_id: str,
    activity_id: str | None,
    sim_ts: float,
    mode: str,
    category: str = "itinary_multi_agent",
) -> None:
    """Trace une décision servie par le cache sémantique dans workdir/llm_cache_hits.jsonl.

    Un hit ne déclenche aucun appel LLM (donc aucune ligne dans llm_exchanges.jsonl) : ce log
    permet de compter les appels économisés et de ventiler l'économie par jour de simulation
    (sim_day). La valeur en tokens économisés est estimée côté analyse via le coût moyen par
    agent des appels réellement effectués pour la même catégorie."""
    try:
        entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            "sim_ts": sim_ts,
            # sim_day en UTC pour s'aligner avec llm_exchanges.jsonl (cf. logger.log_llm_exchange).
            # `tz=timezone.utc` sur un horodatage GAMA donne DÉJÀ le jour MURAL — c'est la
            # définition même de `sim_clock.wall_clock` — et ne dépend pas du `TZ` du
            # processus : laissé tel quel exprès, pour rester octet pour octet le champ que
            # `llm_module.telemetry.logger` écrit de son côté (paquet séparé, qui ne peut
            # pas importer `sim_clock`).
            "sim_day": datetime.fromtimestamp(sim_ts, tz=timezone.utc).strftime(
                "%Y-%m-%d"
            )
            if sim_ts
            else None,
            "agent_id": str(agent_id),
            "activity_id": str(activity_id or ""),
            "category": category,
            "mode": mode,
        }
        with open(settings.app.llm_cache_hits_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except OSError as e:
        logger.warning(f"Impossible d'écrire le cache hit LLM : {e}")


def _format_distribution(distribution: dict) -> str:
    """« car 60% · public_transport 30% · walking 10% » — modes à 0 % omis du texte.

    Le dictionnaire complet (modes à 0 % inclus) reste la source pour les métriques :
    ce format n'est destiné qu'aux traces lisibles (mémoire court terme, logs).
    """
    parts = [
        f"{mode} {pct * 100:.0f}%"
        for mode, pct in sorted(distribution.items(), key=lambda kv: -kv[1])
        if pct > 0
    ]
    return " · ".join(parts) or "aucune"


@lru_cache(maxsize=1)
def _weather_eligible_days() -> tuple[tuple[int, int], ...]:
    """Jours de l'année dans lesquels le tirage météo par agent puise.

    Résolue une fois : la fenêtre ne change pas en cours de run, et la relire à
    chaque décision coûterait une lecture de YAML par agent et par activité.
    `"enquete"` délègue les bornes à `mobility_core.population_reference`
    plutôt que de les recopier — renommer une clé du cadrage ne doit pas casser
    ce dispositif en silence.
    """
    fenetre = settings.agent.weather_window
    jours_semaine = None
    if fenetre == "enquete":
        from mobility_core.population_reference import survey_window, surveyed_weekdays

        debut, fin = survey_window()
        if settings.agent.weather_weekdays_only:
            jours_semaine = tuple(surveyed_weekdays())
    elif fenetre == "annee":
        debut, fin = "2024-01-01", "2024-12-31"
        if settings.agent.weather_weekdays_only:
            jours_semaine = (1, 2, 3, 4, 5)
    else:
        debut, fin = fenetre
        if settings.agent.weather_weekdays_only:
            jours_semaine = (1, 2, 3, 4, 5)

    jours = jours_eligibles(debut, fin, jours_semaine)
    logger.info(
        f"[météo] une date par agent : {len(jours)} journée(s) éligible(s) dans "
        f"{debut} → {fin}"
        + (f", jours de semaine {jours_semaine}" if jours_semaine else "")
    )
    return jours


def _traits_de(person) -> dict:
    """Traits du persona pour l'en-tête du journal, ou vide.

    Défensif À DESSEIN : le journal ne connaît rien de la structure d'une personne et ne doit
    JAMAIS faire tomber une consolidation pour un en-tête. Un double de test sans `identity` a
    suffi à casser dix tests le 2026-09-14 — c'est exactement le genre d'accident qu'un
    observateur n'a pas le droit de provoquer.
    """
    identite = getattr(person, "identity", None)
    traits = getattr(identite, "traits_json", None) if identite is not None else None
    return traits if isinstance(traits, dict) else {}


class Context(BaseModel):
    person: Person
    timestamp: int
    activity_id: str | None = None
    data: dict | None = None


def log_chat(prompt: str, response: str, context: Context) -> str:
    log_dir = settings.agent.chat_log_dir
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    type_suffix = (
        f"-{context.data['type']}" if context.data and context.data.get("type") else ""
    )
    # Heure MURALE de GAMA (`sim_clock`) : le nom du fichier doit se relire à côté du
    # prompt qu'il contient, et celui-ci porte la même heure.
    sim_time = datetime.strftime(wall_clock(context.timestamp), "%d_%H%M")
    file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{sim_time}-{context.person.person_id}-{context.activity_id}{type_suffix}.txt"

    with open(os.path.join(log_dir, file_name), "a") as f:
        f.write("--------------------\n")
        f.write(f"Prompt: \n{prompt}\n")
        f.write("--------------------\n")
        f.write(f"Response: \n{response}\n\n")
        f.write("--------------------\n")
        f.write(f"Data: \n{context.model_dump_json()}\n")

    return file_name


# Jambes de transport collectif, pour décider si l'abonnement TC est pertinent à
# annoncer sur une option. `cableway` = Téléo, qui fait partie du réseau Tisséo.
#
# ⚠ Cette liste sert le PROMPT, pas le score. Trois listes de modes TC coexistent dans
# le dépôt et doivent rester cohérentes : celle-ci, `move_logger._BUS_MODES` (journal de
# production) et `categorize_mode` (loss de calibration). Cette dernière ignorait
# `cableway` jusqu'au 2026-08-26 — le Téléo y était compté en marche ; un test de parité
# verrouille désormais les deux dernières. La loss est l'instrument de mesure : toute
# évolution s'y chiffre avant de s'appliquer (amendement A13 du protocole).
_PT_LEG_MODES = (
    "bus",
    "metro",
    "métro",
    "tram",
    "cableway",
    "transit",
    "public_transport",
    "rail",
    "train",
)


# Traits du persona EXCLUS de la signature de cache. `name` seulement, et pour une raison
# vérifiée : il vient de Faker non graine à la génération, donc il diffère d'une population
# à l'autre sans qu'aucune décision n'en dépende — l'inclure invaliderait tout le cache à
# chaque régénération de population. Contrôle fait le 2026-08-27 : le `name` est identique
# entre la population source et celle du run (930/930), il n'est donc PAS re-tiré au
# chargement, contrairement à ce que la doc affirmait.
#
# Tout le reste entre, y compris les traits qui ne servent qu'au narratif : le tri par
# « ce qui atteint le prompt » est exactement l'arbitrage qui a produit le défaut qu'on
# corrige ici. Sur-invalider est le sens sûr.
_TRAITS_EXCLUDED_FROM_CACHE_KEY = ("name",)


def _traits_signature(traits: dict | None) -> str:
    """Signature stable des traits du persona, pour le `state_hash` du cache LLM.

    Sans elle, un trait qui ne conditionne pas l'offre — l'abonnement TC — change le
    prompt sans changer la clé de cache, et les décisions déjà stockées sont resservies
    sous l'ancien prompt en silence. Mesuré le 2026-08-27 : 352 abonnements corrigés sur
    la population de 1 000, dont aucun n'aurait atteint les décisions en cache.

    Tri des clés : un dict Python conserve l'ordre d'insertion, et deux populations
    sérialisées différemment donneraient deux signatures pour les mêmes traits.
    """
    if not traits:
        return ""
    kept = {
        k: v
        for k, v in sorted(traits.items())
        if k not in _TRAITS_EXCLUDED_FROM_CACHE_KEY
    }
    raw = json.dumps(kept, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _pt_subscription_note(mode_label: str, has_pt: bool) -> str:
    """Mention d'abonnement TC à accoler à une option, ou chaîne vide.

    L'information vit sur l'OPTION et non plus sur le persona (2026-08-26) : elle n'est
    pas déductible du jeu d'options — une option bus est proposée qu'on soit abonné ou
    non — mais elle ne pèse sur la décision que là où un transport collectif est
    réellement offert. Une ligne de persona la faisait lire même sans aucune option TC.
    """
    ml = (mode_label or "").lower()
    # Car scolaire (ticket 030) : compté en TC pour les métriques, mais GRATUIT — pas
    # d'abonnement. La garde passe avant le test _PT_LEG_MODES, dont la sous-chaîne
    # « bus » capterait sinon « school_bus » et collerait une mention fausse.
    if "school_bus" in ml:
        return ""
    if not any(k in ml for k in _PT_LEG_MODES):
        return ""
    return (
        " Has a public transport pass." if has_pt else " Has no public transport pass."
    )


def _build_profile_narrative(traits: dict) -> str:
    """Identité sociale du persona, en anglais (ticket 074, B-5).

    Deux points de la bascule anglaise se jouent ici.

    **L'occupation vient de `professional_activity`, avec `main_occupation` en repli.** Depuis
    la cohorte v6, les deux sont anglais à la source ; l'ordre reste celui-ci parce que les
    cohortes ANTÉRIEURES portent `main_occupation` en français, et qu'une trace archivée
    relue doit continuer de rendre un récit anglais.

    **Les motifs de déplacement habituels sont servis** (`travel_purposes`). Ils étaient
    produits par le générateur, recalculés par `fix_minor_traits`, documentés comme « la liste
    vue par le LLM » — et lus par personne. Un champ entretenu pour rien est plus trompeur
    qu'un champ absent : il fait croire l'information servie.

    **`_income_map` a disparu.** Cette table n'existait que pour franciser un champ déjà
    anglais dans la population (`Very Low`, `Medium-High`…). La supprimer rend la valeur
    telle qu'elle est ; il n'y a rien à traduire, seulement une traduction à retirer.
    """
    name = traits.get("name", "")
    first_name = name.split()[0] if name else ""
    age = traits.get("age", "")
    occupation = traits.get("professional_activity") or traits.get(
        "main_occupation", ""
    )
    household = traits.get("household_size")
    income = traits.get("income") or ""

    extras = []
    if household == 1:
        extras.append("lives alone")
    elif household:
        extras.append(f"household of {household}")
    if income:
        extras.append(f"{income.lower()} income")
    line1 = f"{first_name}, {age}, {occupation}"
    if extras:
        line1 += f" ({', '.join(extras)})"

    # Motifs habituels. Une personne immobile n'en a aucun : la phrase est alors OMISE plutôt
    # que rendue vide — « Usual trip purposes: » sans rien derrière se lirait comme une
    # information manquante, quand c'est une information qui dit « cette personne ne sort pas ».
    motifs = [
        str(m).strip() for m in (traits.get("travel_purposes") or []) if str(m).strip()
    ]
    if motifs:
        line1 += f". Usual trip purposes: {', '.join(motifs)}"

    # Couronne de résidence. SERVIE au modèle depuis le ticket 074 : elle situe la personne
    # dans l'armature urbaine, ce qu'aucune autre information du prompt ne dit — l'adresse
    # n'y est pas, et la distance d'un trajet ne dit rien de l'endroit où l'on habite.
    #
    # C'est aussi ce qui la fait basculer en anglais À LA SOURCE : tant qu'elle n'était qu'une
    # clé de jointure vers l'enquête, sa langue n'engageait personne ; servie au modèle, elle
    # engage la même règle que le reste du prompt.
    #
    # `hors périmètre` n'est PAS une couronne : c'est la cinquième modalité, et la servir telle
    # quelle vaut mieux que la taire — le domicile est connu, il est simplement dehors.
    couronne = str(traits.get("residence_zone") or "").strip()
    if couronne:
        line1 += f". Lives in: {couronne}"

    # La ligne « Mobilité : » a disparu le 2026-08-26. Ce qu'elle portait :
    #
    # * `car_availability` et le statut de conducteur — RETIRÉS. Le jeu d'options dit déjà
    #   si la voiture est prenable (`_owns_car` / `_can_drive` du contrôleur la proposent
    #   ou non), et le canal narratif a été mesuré puis rejeté : +0,12 pt de part voiture,
    #   au niveau du bruit (ticket 018, docs/traces/2026-08-24_car_availability).
    # * le vélo personnel — RETIRÉ pour la même raison. ⚠ Avec une perte assumée : un
    #   agent qui possède un vélo garé ailleurs (chaîne de véhicules) n'a pas d'option
    #   vélo, et le prompt ne dit plus qu'il en a un. Comme il ne peut pas s'en servir,
    #   l'information ne portait aucune décision.
    # * l'abonnement TC — DÉPLACÉ sur l'option TC (cf. `pt_subscription_suffix`) : il
    #   n'est PAS déductible du jeu d'options (une option bus existe, abonné ou pas),
    #   donc il reste servi — mais là où il pèse, et seulement quand un TC est proposé.
    #
    # Ne reste que l'identité sociale, seule information du bloc que les options ne
    # portent pas. Une ligne vide n'est pas rendue.
    return line1


def _axes_de_la_decision(context: Context, plan, destination, weather) -> dict:
    """Axes normalisés d'une entrée écrite par une décision d'itinéraire (lot 2).

    C'est le seul endroit où le mode retenu, le motif et la météo du jour sont connus
    ensemble. Les normaliser ici, une fois, plutôt qu'à chaque rappel.

    `axe_lieu` reste vide pour une décision : elle porte un itinéraire, pas un arrêt. Il sera
    renseigné par les concepts, dont la portée spatiale en désigne un. Vide vaut mieux que la
    destination : deux trajets vers le même travail par deux modes différents ne sont pas le
    même souvenir de lieu.
    """
    return {
        "axe_objet": mode_canonique(plan.mode_label() if plan is not None else None),
        "axe_lieu": None,
        "axe_creneau": creneau_de(wall_clock(context.timestamp)),
        "axe_motif": normaliser_motif(destination),
        "axe_meteo": meteo_de(weather),
    }


@dataclass
class ConceptLu:
    """Un concept rendu par le modèle, ramené à une forme unique.

    DEUX FORMATS d'entrée sont acceptés, et ce n'est pas de la complaisance :

    - l'OBJET, depuis le lot 1 du ticket 071, qui porte `severity`, `valence`, puis `mode`
      (lot 2) et `operation` / `target_id` (lot 3) ;
    - le TABLEAU de cinq chaînes, format d'avant, qu'un run REPRIS relit dans son propre cache
      de réflexions et dans les concepts déjà écrits. Sans cette tolérance, reprendre un run
      perdrait les concepts accumulés.

    Le `content` stocké reste le 5-uplet dans les deux cas : la gravité, la valence et les axes
    vivent sur les CHAMPS de l'entrée, pas dans son texte. Aucun lecteur en aval ne change.
    """

    cinq: list
    niveau: str | None = None
    valence: str = "neutre"
    mode: str | None = None
    operation: str = CREER
    cible: str = ""
    # Ticket 100, lot 4 — la PROVENANCE. `vecu` par défaut : un concept écrit avant ce lot, ou
    # par un modèle qui ignore le champ, vient de la journée de l'agent — c'est ce qui était
    # vrai avant que le foyer existe, et c'est le défaut le moins inventif.
    origine: str = "vecu"


# Vocabulaire du schéma (anglais, ticket 074) → vocabulaire de `MemoryEntry` (français).
_ORIGINES_MODELE: dict[str, str] = {"lived": "vecu", "heard": "entendu"}


def _normaliser_origine(brut) -> str:
    """La provenance rendue par le modèle, ramenée au vocabulaire de l'entrée.

    Une valeur inconnue ou absente retombe sur `vecu`, et LAISSE UNE TRACE. C'est le repli le
    moins inventif — on tient le concept pour né de la journée de l'agent, ce qui était vrai
    avant que le foyer existe — mais il n'est pas anodin : un concept d'ouï-dire pris pour du
    vécu REPARTIRAIT dans le foyer, ce que la décision D2 interdit. Un modèle qui ne
    respecterait jamais ce champ doit donc se voir.
    """
    clef = str(brut or "").strip().lower()
    if clef in _ORIGINES_MODELE:
        return _ORIGINES_MODELE[clef]
    if clef in ("vecu", "entendu", "lu"):
        return clef
    if clef:
        logger.warning(
            f"[concepts] provenance INCONNUE « {brut} » — hors de "
            f"{sorted(_ORIGINES_MODELE)} ; le concept est tenu pour VÉCU, donc il pourra "
            f"repartir dans le foyer. Vérifiez que le modèle respecte le champ `source`."
        )
    return "vecu"


def _normaliser_concept(concept) -> ConceptLu:
    if isinstance(concept, dict):
        cinq = [
            str(concept.get("content", "")),
            str(concept.get("keywords", "")),
            str(concept.get("spatial_scope", "")),
            str(concept.get("temporal_scope", "")),
            str(concept.get("purpose", "")),
        ]
        mode = str(concept.get("mode") or "").strip().lower() or None
        if mode == "any":
            # « any » est une RÉPONSE, pas une absence : le concept ne parle d'aucun mode.
            # Il vaut `None` comme axe — et un axe absent ne s'apparie avec rien, ce qui est
            # exact : ce concept n'a pas à remonter au titre d'un mode.
            mode = None
        return ConceptLu(
            cinq=cinq,
            niveau=concept.get("severity"),
            valence=str(concept.get("valence") or "neutre"),
            mode=mode,
            operation=normaliser_operation(concept.get("operation")),
            cible=str(concept.get("target_id") or "").strip(),
            origine=_normaliser_origine(concept.get("source")),
        )
    if isinstance(concept, (list, tuple)):
        cinq = [str(x) for x in list(concept)[:5]]
        cinq += [""] * (5 - len(cinq))
        # Format d'avant le lot 1 : ni niveau, ni mode, ni opération n'ont été demandés. Le
        # concept retombera sur la gravité déterministe de son groupe — ce qui est exact — et
        # sur `creer`, le repli le moins destructeur.
        return ConceptLu(cinq=cinq)
    return ConceptLu(cinq=[str(concept), "", "", "", ""])


def _concepts_du_jour(long_term_memory, person_id: str, paniers: set) -> list:
    """Concepts existants des paniers touchés par la journée (ticket 071, lot 3).

    ⚠ **Le panier ne peut pas être calculé après coup.** Il se définit sur le couple
    (mode, motif) du concept NOUVEAU, mais les candidats doivent être montrés au modèle AVANT
    qu'il n'écrive le sien — et un second appel est exclu par la contrainte transverse du
    ticket : aucun lot ne coûte d'appel supplémentaire.

    D'où la portée retenue : les paniers des **entrées consommées du jour**, c'est-à-dire les
    modes et les motifs que l'agent a réellement empruntés. C'est exactement la bonne portée —
    il réfléchit sur sa journée, les concepts qu'il pourrait corriger sont ceux qui en parlent.

    Les concepts HORS SERVICE n'y figurent pas : il n'y a pas lieu de proposer au modèle de
    corriger ce qu'on ne lui sert plus.
    """
    if long_term_memory is None or not paniers:
        return []
    long_term_memory.ensure_user_initialized(person_id)
    entrees = long_term_memory.user_metadata.get(person_id, {}).get("entries", [])

    par_panier: dict = {}
    for e in entrees:
        if str(e.memory_type) != str(MemoryType.CONCEPT.value) or not e.doc_id:
            continue
        if not e.est_servi or e.depasse_le:
            continue
        clef = panier_de(e.axe_objet, e.axe_motif)
        if clef in paniers:
            par_panier.setdefault(clef, []).append(e)

    montres = []
    for clef, candidats in par_panier.items():
        # Les plus confiants d'abord, la dernière observation départageant : c'est ce que
        # l'agent tient pour le plus sûr, donc ce qu'il a le plus de raisons de corriger.
        candidats.sort(
            key=lambda e: (
                e.confiance,
                e.derniere_observation or e.timestamp,
            ),
            reverse=True,
        )
        montres.extend(candidats[:CONCEPTS_MONTRES_PAR_PANIER])
    return montres


def _gravite_de_la_contrainte(context: Context) -> float:
    """Gravité déterministe d'une décision, depuis la contrainte de chaîne (ticket 071, lot 1).

    C'est la quatrième composante de `I_det`, « changement de mode contraint ». Elle n'arrive
    ni par l'arrivée ni par le bus manqué mais par le chemin de DÉCISION : c'est là, et
    seulement là, qu'on sait que l'agent a dû renoncer à un mode — il rentre avec ce qu'il a
    pris (`retour_force`), ou ne peut pas partir comme il l'aurait voulu (`sortie_bloquee`).

    Être passager d'un autre membre du ménage en est exclu : c'est un arrangement, pas une
    dégradation subie (cf. `CONTRAINTES_MODE_FORCE`).
    """
    contrainte = str((context.data or {}).get("contrainte_chaine") or "")
    valeur, _detail = gravite_deterministe(
        mode_contraint=contrainte in CONTRAINTES_MODE_FORCE
    )
    return valeur


# Version du schéma de sortie de la réflexion COURTE. À incrémenter dès que son contrat change
# (champs, ou sémantique d'un champ) : elle entre dans la clé de mémoïsation et invalide donc le
# cache accumulé sous l'ancien contrat, au lieu de le servir de travers.
#   1 — ticket 071, lot 1 : chaque concept devient un objet et porte `severity` et `valence`.
#   2 — ticket 071, lot 2 : chaque concept déclare son `mode`. Sans lui, le vivier par objet
#       du rappel ne trouverait jamais rien : la mémoire longue ne contient que des
#       réflexions et des concepts, et aucun ne dirait de quel mode il parle.
#   3 — ticket 071, lot 3 : chaque concept déclare son `operation` et sa cible. Les concepts
#       cessent de s'empiler : ils se confirment, se précisent ou se voient contredire.
#   4 — ticket 100, lot 4 : chaque concept déclare sa PROVENANCE (`lived` | `heard`). Sans
#       elle, un concept né d'un ouï-dire est indiscernable d'un concept né d'un trajet, et la
#       décision D2 — un seul saut — n'a aucun moyen de s'appliquer. Le ticket 078 § 4.1
#       refusait cette généalogie ; elle devient nécessaire dès lors que la circulation est
#       bornée à un saut.
#       ⚠ Le champ est demandé dans les DEUX bras, drapeau de partage allumé ou éteint : c'est
#       ce qui garde une version de schéma unique entre eux, donc comparable. Drapeau éteint,
#       aucun bloc de foyer n'entre dans l'appel et la réponse vaut `lived` partout.
SCHEMA_REFLEXION_VERSION = 4


class LlmAgent:
    DEFAULT_IDENTITY = ""

    def __init__(self):
        self.short_term_memory: dict[str, UserShortTermMemory] = {}
        if settings.agent.long_term_memory_enabled:
            self.long_term_memory = MultiUserLongTermMemory(
                storage_dir=settings.agent.long_term_memory_storage_dir,
                long_term_memory_filter_by_datetime=settings.agent.long_term_memory_filter_by_datetime,
                max_loaded_metadata=settings.agent.long_term_max_loaded_metadata,
            )
        else:
            self.long_term_memory = None
            logger.info("Long-term memory disabled — ChromaDB initialization skipped")

        # Instance du client LLM (Singleton naturel pour cet Agent) — SDK typé
        # (AsyncClient httpx réutilisé entre les appels, résultats TaskResult)
        self.llm_client = LLMGatewayClient(
            base_url=os.getenv("LLM_API_URL", "http://localhost:8000"),
            wait_timeout=settings.agent.remote_llm_poll_timeout,
            backpressure_max_inflight=settings.world.worker_concurrency,
            backpressure_release_ratio=settings.agent.remote_llm_backpressure_ratio,
            circuit_failure_threshold=settings.agent.remote_llm_circuit_failure_threshold,
            circuit_probe_interval=settings.agent.remote_llm_circuit_probe_interval,
            # Ticket 092 — posée sur le CLIENT : elle couvre tout appel ajouté plus tard.
            # Ticket 095, lot C — les appels connus posent désormais leur liste blanche PAR
            # CATÉGORIE dans leur payload, que le SDK respecte telle quelle. Celle-ci reste le
            # filet : l'UNION de tout ce qui est admis, pour qu'un appel neuf soit restreint
            # par défaut plutôt que libre.
            instances_admises=toutes_les_instances(),
        )
        self.prompt_manager = PromptManager(
            os.path.join(os.path.dirname(__file__), "prompts")
        )

        if settings.cache.enabled:
            population_name = f"{settings.data.synthetic_file_prefix}population_{settings.data.population_size}"
            # Isolation du cache par version de prompt système : si le prompt actif
            # (mobility_llm/prompts/prompts.yaml) change, le checksum change et le cache
            # repart à neuf au lieu de réutiliser des décisions obsolètes.
            prompt_checksum = _mobility_prompt_manager().active_prompt_checksum()
            cache_dir = os.path.join(
                settings.cache.cache_dir, prompt_checksum, population_name
            )
            logger.info(
                f"LLM cache isolé par prompt — checksum={prompt_checksum}, dir={cache_dir}"
            )
            self.llm_cache = LlmSemanticCache(
                cache_dir=cache_dir,
                semantic_threshold=settings.cache.semantic_threshold,
                embed_model_name=settings.cache.embed_model_name,
            )
            # Mémoïsation exacte des réflexions (ticket 012) — même répertoire que le
            # cache de décisions : l'isolation par checksum de prompt est héritée.
            self.reflection_memo = (
                ReflectionMemoStore(cache_dir=cache_dir)
                if settings.cache.reflection_memo_enabled
                else None
            )
        else:
            self.llm_cache = None
            self.reflection_memo = None

    def get_short_term_memory(self, user_id: str) -> UserShortTermMemory:
        if user_id not in self.short_term_memory:
            self.short_term_memory[user_id] = UserShortTermMemory(user_id)
        return self.short_term_memory[user_id]

    def _weather_timestamp(self, context: Context) -> int:
        """Timestamp servant à lire le bulletin météo de cet agent.

        Par défaut, l'horloge simulée — comportement historique. Quand
        `weather_per_agent_dates` est actif, la seule DATE est remplacée par un
        jour de l'année — **celui que la personne a réellement décrit** quand une table de
        dates déclarées accompagne la population (ticket 058), sinon un jour tiré
        déterministement depuis l'identifiant de l'agent :
        sur une journée simulée unique, tous les agents partageraient sinon une
        seule météo, et l'effet météo serait par construction non mesurable
        (ticket 023). L'heure du départ est conservée, l'offre de transport
        aussi : seule la météo varie.
        """
        if not settings.agent.weather_per_agent_dates:
            return context.timestamp
        try:
            jours = _weather_eligible_days()
            return timestamp_meteo(
                context.timestamp,
                context.person.person_id,
                settings.agent.weather_draw_seed,
                jours,
                # Le jour décrit, quand il est connu : il n'y a pas à tirer ce que l'enquête
                # porte. Absent, `date_imposee` vaut None et le tirage reprend à l'identique.
                date_imposee=date_declaree(
                    context.person.person_id, settings.agent.weather_dates_file
                ),
                # Ticket 075 — la date tirée est un DÉPART : elle avance d'un jour calendaire
                # par jour simulé écoulé. À zéro (run d'une journée, ou premier jour d'un run
                # long), le bulletin est exactement celui d'avant le ticket.
                jours_ecoules=jours_ecoules(context.timestamp),
            )
        except Exception as err:  # pragma: no cover - garde-fou de production
            # Un tirage impossible ne doit pas faire tomber une décision : on
            # retombe sur l'horloge simulée, mais en le DISANT — un run muet qui
            # perd silencieusement le dispositif serait pire que son absence.
            logger.error(
                f"[ALARME] tirage de date météo impossible ({err}) — repli sur "
                f"l'horloge simulée, le dispositif « une météo par agent » est INACTIF"
            )
            return context.timestamp

    def add_short_term_memory(
        self,
        context: Context,
        msg: str,
        timestamp: int | None = None,
        importance: float = 0.0,
        axes: dict | None = None,
        valence: str = "neutre",
        origine: str | None = None,
    ):
        # Ticket 075 — rejeu d'une reprise à chaud : l'agent revit une journée qu'il a DÉJÀ
        # apprise. Le point d'étranglement est ici : sans entrée de mémoire courte, aucun agent
        # ne devient éligible à la consolidation, donc rien ne se réécrit en mémoire longue.
        # Les décisions et les déplacements, eux, continuent — il faut bien que la simulation
        # retrouve son état.
        if gel_actif():
            return
        memory = self.get_short_term_memory(context.person.person_id)
        # L'horodatage du souvenir est l'heure MURALE de GAMA. Ce n'est pas cosmétique :
        # ce `datetime` finit dans le PROMPT (« - Time 16 March 2026, 05:12: … » via
        # `humanize_date`, et le nom du jour des souvenirs de réflexion), et il sert de
        # côté gauche aux filtres LTM par jour et par ancienneté. Lu dans le fuseau du
        # processus, il annonçait 06:12 pour 5 h 12 murales.
        memory.add_message(
            msg,
            wall_clock(timestamp or context.timestamp),
            activity_id=context.activity_id,
            importance=importance,
            axes=axes,
            valence=valence,
            origine=origine,
        )
        history_log.log_shortterm_memory(
            timestamp=context.timestamp,
            person_id=context.person.person_id,
            activity_id=context.activity_id,
            message=msg,
            data=context.data,
        )

    def note_decision_contrainte(self, context: Context, plan, destination) -> None:
        """Écrit en mémoire courte un déplacement dont le mode n'a pas été CHOISI.

        Ticket 077, lot C. Un trajet à itinéraire unique n'appelle pas le modèle : il ne
        passait donc par aucun des deux endroits qui écrivent une entrée de décision, et la
        mémoire ignorait purement et simplement qu'un déplacement avait eu lieu. Sur le run
        de trente jours du 075, **116 trajets sur 514** étaient dans ce cas — tous les
        retours des agents ruraux, c'est-à-dire la moitié de leur vécu.

        Deux conséquences, toutes deux mesurées. La réflexion du soir recevait les
        observations physiques du trajet sans la décision qui les explique. Et le journal des
        habitudes, qui s'alimente à l'arrivée en cherchant la décision correspondante, n'en
        trouvait aucune.

        **Le texte dit que le choix était contraint, et ne prétend pas qu'un modèle a
        choisi.** Un agent qui se relit doit pouvoir distinguer ce qu'il a décidé de ce qu'il
        a subi : lui faire lire « chosen by gateway LLM » sur un trajet sans alternative lui
        ferait tirer une préférence d'une absence d'option — exactement le motif que ce
        dépôt traque, où l'absence de mesure produit volontiers le score parfait.
        """
        if plan is None:
            return
        plan_summary = env_ob_to_text("travel_plan", plan.model_dump())
        stm_msg = (
            f"[ TRAVEL_PLAN ] Plan to head <{destination}>. "
            f"No choice was possible: this was the only available itinerary.\n"
            f"{plan_summary}\n"
            f"Reasoning: the mode was imposed by the absence of any alternative, "
            f"not preferred."
        )
        self.add_short_term_memory(
            context,
            stm_msg,
            timestamp=context.timestamp,
            importance=_gravite_de_la_contrainte(context),
            axes=_axes_de_la_decision(
                context,
                plan,
                destination,
                get_weather(self._weather_timestamp(context)),
            ),
        )

    async def aadd_long_term_memory(self, context: Context, msg: MemoryEntry):
        await self.long_term_memory.aadd_memory(msg)
        history_log.log_longterm_memory(
            timestamp=context.timestamp,
            person_id=context.person.person_id,
            message=msg.content,
            data=context.data,
        )

    def parse_response_json(self, response: str) -> tuple[dict | None, str]:
        try:
            match = re.search(r"\{.*\}", response, re.DOTALL)
            assert match is not None, "No JSON found in response"

            json_str = match.group(0)
        except Exception as e:
            traceback.print_exc()
            print(f"Error parsing response: {e}, response raw: {response}")
            json_str = response.strip()

        try:
            parsed = json.loads(json_str)
            return parsed, ""
        except Exception as e:
            traceback.print_exc()
            print(f"Error parsing response: {e}, response raw: {response}")

        try:
            parsed = demjson3.decode(json_str)
            return parsed, ""
        except demjson3.JSONDecodeError as e:
            traceback.print_exc()
            print(f"Error parsing response: {e}, response raw: {response}")

        return None, response.strip()

    def get_person_identity_description(self, person: Person) -> str:
        return _build_profile_narrative(person.identity.traits_json)

    async def query_past_experiences_for_travel(
        self, context: Context, options: list[TravelPlan]
    ) -> list[str]:
        def get_plan_text(plan: TravelPlan) -> str:
            return env_ob_to_text("travel_plan_query", plan.model_dump())

        index = 1
        travel_options = ""
        for option in options:
            travel_options += f"{index}. \n{get_plan_text(option)}\n"
            index += 1

        text = self.prompt_manager.get_prompt(
            PromptName.QUERY_EXPERIENCES,
            current_time=humanize_date_short(context.timestamp),
            temporal_keyword=categorize_date_time_short(context.timestamp),
            weekday=get_weekday_category(context.timestamp).upper(),
            destination=options[0].purpose,
            travel_options=travel_options,
        )

        # logger.debug(f"Querying experiences with travel plans for user {context.person.person_id}, activity {context.activity_id}, query text: {text}")

        # Ticket 071, lot 2 — les modes OFFERTS ouvrent le vivier par objet, et le contexte
        # courant alimente les deux affinités. Sans les modes, le vivier B ne saurait pas quoi
        # chercher ; sans le contexte, les affinités vaudraient zéro partout, ce qui est le
        # score d'une discordance totale et non celui d'une absence d'information.
        modes_offerts = {
            m for m in (mode_canonique(o.mode_label()) for o in options) if m
        }
        contexte_axes = {
            "axe_objet": modes_offerts,
            "axe_lieu": None,
            "axe_creneau": creneau_de(wall_clock(context.timestamp)),
            "axe_motif": normaliser_motif(options[0].purpose if options else None),
            "axe_meteo": meteo_de(get_weather(self._weather_timestamp(context))),
        }

        hist = await self.long_term_memory.aquery_user_memories(
            person_id=context.person.person_id,
            query=text,
            top_k=settings.agent.long_term_max_entries_query,
            max_past_days=settings.agent.long_term_max_days_query,
            query_at=context.timestamp,
            modes_offerts=sorted(modes_offerts),
            contexte=contexte_axes,
        )

        # deduplicate entries based on content
        unique_hist = {}
        for entry in hist:
            if entry.content not in unique_hist:
                unique_hist[entry.content] = entry
        hist = sorted(
            list(unique_hist.values()),
            key=lambda x: x.metadata["timestamp"],
            reverse=True,
        )

        # logger.debug(f"Found {len(hist)} relevant experiences for travel plans for user {context.person.person_id}, activity {context.activity_id}")

        # resp = [
        #     # f"[{datetime.strftime(datetime.fromisoformat(entry.metadata['timestamp']), '%A, %H:%M:%S')}] {entry.content}"
        #     # TODO: we asked the LLM to return the time within the day, so only need to append the day of week here
        #     f"[{datetime.strftime(datetime.fromisoformat(entry.metadata['timestamp']), '%A')} at {time_to_bucket_text(datetime.fromisoformat(entry.metadata['timestamp']).timestamp())}] {entry.content}" if entry.content else ""
        #     for entry in hist
        # ]

        resp = []
        ts = []
        for entry in hist:
            if str(entry.metadata["memory_type"]) == str(MemoryType.REFLECTION.value):
                date_str = datetime.strftime(
                    datetime.fromisoformat(entry.metadata["timestamp"]), "%A, %B %d"
                )
                resp.append(f"[{date_str}] {entry.content}")
                ts.append(
                    datetime.fromisoformat(entry.metadata["timestamp"]).timestamp()
                )
            elif str(entry.metadata["memory_type"]) == str(MemoryType.CONCEPT.value):
                concept = json.loads(entry.content)
                resp.append(f"[Concept] {concept[0]}" if concept else "")
                ts.append(
                    datetime.fromisoformat(entry.metadata["timestamp"]).timestamp()
                )
            else:
                logger.debug(
                    f"Unknown memory type for entry: {entry.metadata['memory_type']}"
                )

        # sort the entries by timestamp asc
        ts = np.array(ts)
        sorted_indices = np.argsort(ts)
        resp = [resp[i] for i in sorted_indices]

        # ── Ticket 071, lot 4 — la MÉMOIRE NOYAU ─────────────────────────────────
        # Les dix souvenirs bruts laissent la place à un bloc permanent structuré, complété de
        # deux ou trois entrées épisodiques rappelées pour la décision en cours. C'est le
        # *working context* de MemGPT : un bloc toujours présent, le reste paginé à la demande.
        #
        # Les trois blocs sont CALCULÉS, aucun n'est écrit par le modèle — un texte réécrit
        # périodiquement par un modèle dérive et invente, un bloc calculé reste vérifiable
        # contre sa source. Le lot ne coûte donc AUCUN appel supplémentaire.
        try:
            _entrees = self.long_term_memory.user_metadata.get(
                context.person.person_id, {}
            ).get("entries", [])
            _bloc = memoire_noyau(
                self.long_term_memory.journal_trajets(context.person.person_id),
                _entrees,
                wall_clock(context.timestamp),
                context.person.person_id,
            )
        except Exception as err:  # noqa: BLE001
            # Un bloc qui ne se construit pas ne doit pas faire perdre la décision — mais il
            # ne doit pas non plus disparaître en silence : sans lui, l'agent retombe au
            # comportement d'avant le lot 4 sans que rien ne le dise.
            logger.warning(
                f"[noyau] mémoire noyau non construite pour {context.person.person_id} "
                f"({err}) — repli sur les souvenirs bruts seuls"
            )
            _bloc = []

        if not _bloc:
            return resp

        # Les épisodiques sont les PLUS RÉCENTES du top-K, et il y en a deux ou trois, pas dix :
        # le bloc porte désormais ce que les dix disaient de répétitif.
        _n = int(settings.agent.memoire__episodiques_avec_noyau)
        return _bloc + resp[-_n:] if _n > 0 else _bloc

    def get_personal_system_prompt(self, person: Person) -> str:
        identity_description = self.get_person_identity_description(person)
        return self.prompt_manager.get_prompt(
            PromptName.PERSONAL_SYSTEM, identity_description=identity_description
        )

    async def build_travel_plan_payload(
        self,
        context: Context,
        options: list[TravelPlan],
        destination: str,
        departure_time: int = 0,
        anticipation: dict | None = None,
    ) -> dict[str, Any]:
        agent_id = context.person.person_id
        perception = self.get_person_identity_description(
            context.person
        )  # TODO To be remplace by feeling and perception about transport modes
        current_time = humanize_time(context.timestamp)
        city_context = (
            weather_to_natural_language(get_weather(self._weather_timestamp(context)))
            or "None"
        )

        history = []
        if settings.agent.long_term_memory_enabled:
            _pl = PipelineLogger.get()
            _rec = _pl.get_record(context.person.person_id) if _pl is not None else None
            if _rec is not None:
                _rec.T_ltm_start = time.time()
            history = await self.query_past_experiences_for_travel(context, options)
            if _rec is not None:
                _rec.T_ltm_end = time.time()

        # Abonnement TC : porté par l'option, pas par le persona (cf. `_pt_subscription_note`).
        _has_pt = bool(
            (context.person.identity.traits_json or {}).get(
                "has_pt_subscription", False
            )
        )

        def _describe(opt: TravelPlan) -> str:
            """Texte de l'option, avec la mention d'abonnement sur sa PREMIÈRE ligne.

            Les lignes suivantes sont les étapes de l'itinéraire, ré-indentées en
            sous-puces par le gabarit : y coller la mention la ferait passer pour une
            étape. Elle est donc accolée à la phrase de synthèse.
            """
            text = env_ob_to_text("travel_plan", opt.model_dump())
            note = _pt_subscription_note(opt.mode_label() or "", _has_pt)
            if not note:
                return text
            head, sep, tail = text.partition("\n")
            return f"{head.rstrip()}{note}{sep}{tail}"

        # Utilisation d'une compréhension de liste pour la performance et la clarté
        trajectories = [
            {
                "index": i,
                "mode": opt.mode_label() or "unknown",
                "description": _describe(opt),
                # Distance totale du trajet (en mètres) — utilisée pour les métriques Prometheus
                "total_distance_m": (
                    opt.distance
                    if opt.distance is not None
                    else sum(leg.get_distance() for leg in (opt.legs or []))
                ),
            }
            for i, opt in enumerate(options)
        ]

        dest_zone = (
            options[0].end_location.zone
            if options and options[0].end_location
            else None
        )

        return {
            "category": "itinary_multi_agent",
            # Ticket 095, lot C — la liste blanche est posée PAR CATÉGORIE, et non une fois
            # pour tout le run. La décision est la variable mesurée de l'article : elle ne
            # partage pas sa file avec la réflexion nocturne, qui consomme autant de jetons.
            "instances_admises": instances_pour("itinary_multi_agent"),
            "agents": [
                {
                    "agent_id": agent_id,
                    # `Contraintes : None` retiré le 2026-08-26 : littéral codé en dur,
                    # jamais implémenté, mesuré constant sur 2 487 records sur 2 487.
                    "perception": perception,
                    "destination": destination,
                    "destination_zone": dest_zone,
                    "departure_time": humanize_time(departure_time)
                    if departure_time
                    else None,
                    "departure_timestamp": float(departure_time)
                    if departure_time
                    else None,
                    "current_time": current_time,
                    # Météo/trafic propre à l'agent (et non plus au niveau requête) :
                    # la clé de batch hache `parameters`, donc en sortant la météo des
                    # parameters, des demandes de météos différentes peuvent fusionner
                    # dans un même appel LLM — chaque persona garde la sienne dans le
                    # prompt (cf. itinary_multi_agent.md.j2, injection par bloc).
                    "context": city_context,
                    # Anticipation de la chaîne (ticket 014) : météo des tranches
                    # restantes de la journée et agenda glissant des trajets
                    # restants — construits par le contrôleur (_build_anticipation),
                    # rendus par bloc dans le gabarit. La position des véhicules
                    # n'est plus énoncée (biais vélo mesuré) : la règle de chaîne
                    # vit dans le prompt système (variante expert_m4).
                    "day_outlook": (anticipation or {}).get("outlook"),
                    "agenda": (anticipation or {}).get("agenda") or [],
                    "history": history,
                    "trajectories": trajectories,
                }
            ],
            "parameters": {**settings.agent.llm_params},
        }

    async def evaluate_and_choose_travel_plan(
        self,
        context: Context,
        options: list[TravelPlan],
        destination: str,
        departure_time: int = 0,
        anticipation: dict | None = None,
        *,
        force_provider: str | None = None,
        allowed_providers: set | None = None,
        trace: dict | None = None,
        presentation_figee: bool = False,
        option_order_seed: int | None = None,
    ) -> tuple[int, str, str, dict]:
        """Choisit un itinéraire et renvoie (index, justification, provider, répartition).

        Ticket 035 (spec 02/05) — kwargs optionnels, sans effet quand ils sont absents :
        `force_provider` épingle une instance de passerelle ; `allowed_providers` refuse
        toute réponse servie par une instance hors de cet ensemble (substitution refusée,
        Q3) ; `trace` (dict fourni par l'appelant) reçoit ce qui a été présenté, la réponse
        brute, les poids et le fournisseur (D6) ; `presentation_figee` garde l'ordre reçu
        (l'appelant l'a déjà ordonné) ; `option_order_seed` remplace la graine des réglages.

        La répartition est la distribution de probabilité par mode canonique qui a servi
        au tirage (modes non proposés inclus, à 0) — vide si la décision n'en vient pas
        (réponse à l'ancien format, point de cache hérité, erreur). Elle est tracée
        telle quelle dans `moves.csv`.

        `anticipation` (ticket 014) : contexte d'anticipation construit par le
        contrôleur — injecté dans le prompt, et sa `signature` entre dans la clé du
        cache de décisions (deux anticipations différentes = deux entrées distinctes).
        """
        assert options, "No travel options provided for planning trip."
        anticipation_key = (anticipation or {}).get("signature", "")

        # GARDE ACCIDENTS (ticket 070, travail E). La clé du cache de décisions est bâtie sur
        # les CODES D'OPTIONS — des routes et des arrêts — donc insensible aux DURÉES par
        # construction (`llm/cache.py`, `_make_state_hash`). Sans ce complément, un agent dont
        # le trajet vient d'être allongé de vingt minutes se verrait resservir la décision
        # qu'il avait prise sans le retard, et aucun journal ne le signalerait.
        #
        # C'est la QUATRIÈME occurrence du même piège dans le dépôt — après le temps terminal,
        # les traits du persona et le contexte d'anticipation, dont l'une a coûté un vidage
        # manuel de cache. `extra_key` existe précisément pour ça.
        if departure_time:
            from trip_helper import accidents as _accidents

            _registre = _accidents.registre()
            if _registre is not None:
                _sig = _registre.signature_active(int(departure_time))
                if _sig:
                    anticipation_key = f"{anticipation_key}|accidents:{_sig}"

        # Ordre déterministe pour les clés de cache (indépendant du shuffle)
        sorted_options = sorted(options, key=lambda p: p.get_code() or "")
        # Ordre de présentation DÉTERMINISTE (ticket 035, D7) : dérivé de la graine, de
        # l'agent et de l'activité — le biais de position est toujours mélangé, mais le
        # même déplacement est présenté dans le même ordre dans les deux modes d'exécution.
        if presentation_figee:
            shuffled_options = list(options)
        else:
            shuffled_options = ordre_presentation(
                options,
                settings.agent.option_order_seed
                if option_order_seed is None
                else option_order_seed,
                context.person.person_id,
                context.activity_id,
            )

        activity_purpose = options[0].purpose or ""
        weather = get_weather(self._weather_timestamp(context))

        # Graine du tirage : le jour simulé en fait partie, donc un même contexte
        # rejoué le lendemain retire un autre mode (y compris sur un cache hit),
        # tandis qu'un run relancé à l'identique reproduit exactement les mêmes trajets.
        # `tz=timezone.utc` rend déjà le JOUR MURAL de GAMA (la définition de
        # `sim_clock.wall_clock`) et ne dépend pas du `TZ` du processus. Laissé mot pour
        # mot : cette chaîne entre dans la graine du tirage de mode, et la réécrire — même
        # à valeur identique — n'apporterait rien qu'un risque de rebattre tous les
        # tirages déjà mesurés.
        seed_parts = (
            settings.agent.mode_draw_seed,
            context.person.person_id,
            context.activity_id,
            datetime.fromtimestamp(context.timestamp, tz=timezone.utc).strftime(
                "%Y-%m-%d"
            ),
        )

        # --- Cache hybride (avant l'appel LLM) ---
        # Sans souvenir, la décision ne dépend que des conditions factuelles : correspondance
        # exacte, et le payload — donc la requête LTM — n'est construit qu'en cas de miss.
        # Avec des souvenirs, le vécu de l'agent pèse sur la décision : on doit construire le
        # payload d'abord pour comparer la LTM courante à celle qui a produit la décision cachée.
        has_memories = (
            self.long_term_memory is not None
            and self.long_term_memory.has_memories(context.person.person_id)
        )
        payload = None
        memory_text = None
        if has_memories:
            payload = await self.build_travel_plan_payload(
                context, shuffled_options, destination, departure_time, anticipation
            )
            # Texte mémoire : sérialisation du champ history déjà calculé dans le payload
            memory_text = json.dumps(
                payload["agents"][0].get("history", []), ensure_ascii=False
            )

        # ── Ticket 075 — pendant le REJEU d'une reprise à chaud ──────────────────────────
        # La branche par similarité compare la mémoire COURANTE à celle qui a produit la
        # décision cachée. Or pendant un rejeu la mémoire est figée au point de reprise,
        # donc plus jamais identique à ce qu'elle était à cet instant du run d'origine : le
        # seuil de 0,95 n'est pas atteint et la décision repart au modèle. Mesuré le
        # 2026-09-14 sur le rejeu d'un jour : 33 % de service seulement, onze décisions sur
        # dix-huit repayées. Sur un rejeu de quarante jours, ce serait plus d'une journée de
        # quota dépensée pour réapprendre ce qu'on sait déjà.
        #
        # ⚠ Ce n'est PAS une dégradation, et c'est l'inverse d'un repli : la branche EXACTE
        # s'adresse au point écrit par le run d'origine pour ce même agent, cette même
        # activité, ce même créneau, cette même météo et ces mêmes options. Ce qu'elle rend
        # est donc la décision que le run d'origine A PRISE. Un appel neuf, lui, rendrait une
        # décision prise sur une mémoire que l'agent n'avait pas encore à ce moment-là.
        # Un miss reste un miss : le modèle est appelé normalement.
        _memory_text_cache = None if gel_actif() else memory_text

        # Ticket 100 (Q5, tranchée le 2026-09-22) — le cache de décisions est CONTOURNÉ les
        # jours d'événement, automatiquement. Ce jour-là, chaque décision passe par le modèle :
        # c'est le jour où l'agent décide en voyant l'offre nominale, et une décision resservie
        # y ferait passer un choix d'un autre jour pour un choix de celui-ci.
        #
        # ⚠ La coupure ne porte QUE sur ce jour. La fenêtre d'après — celle qu'on mesure —
        # garde son cache, et les compteurs de `evenements` disent jour par jour combien de
        # décisions y ont été servies depuis le cache.
        from llm import evenements as _evenements

        _cache_coupe = _evenements.cache_coupe(context.timestamp)

        if self.llm_cache is not None and not _cache_coupe:
            cache_hit = await self.llm_cache.lookup(
                agent_id=context.person.person_id,
                activity_id=context.activity_id,
                timestamp=context.timestamp,
                options=sorted_options,
                memory_text=_memory_text_cache,
                weather=weather,
                activity_purpose=activity_purpose,
                seed_parts=seed_parts,
                extra_key=anticipation_key,
                traits_key=_traits_signature(context.person.identity.traits_json),
            )
            _evenements.noter_decision(context.timestamp, depuis_cache=cache_hit is not None)
            if cache_hit is not None:
                if trace is not None:
                    trace["cache"] = True
                chosen_plan = sorted_options[cache_hit["index"]]
                original_index = options.index(chosen_plan)
                if cache_hit.get("distribution"):
                    reason = (
                        "Mode tiré au sort dans la distribution mise en cache : "
                        + _format_distribution(cache_hit["distribution"])
                    )
                else:
                    reason = "Décision récupérée depuis le cache sémantique LLM."
                plan_summary = env_ob_to_text("travel_plan", chosen_plan.model_dump())
                stm_msg = f"[ TRAVEL_PLAN ] Plan to head <{destination}> served from LLM cache.\n{plan_summary}\nReasoning: {reason}"
                self.add_short_term_memory(
                    context,
                    stm_msg,
                    timestamp=context.timestamp,
                    importance=_gravite_de_la_contrainte(context),
                    axes=_axes_de_la_decision(
                        context, chosen_plan, destination, weather
                    ),
                )
                logger.debug(
                    f"Cache hit for person {context.person.person_id}, activity {context.activity_id}, returning cached plan with reason: {reason}"
                )
                # Écriture jsonl déportée hors de l'event loop (open/write bloquants)
                await asyncio.to_thread(
                    log_llm_cache_hit,
                    agent_id=context.person.person_id,
                    activity_id=context.activity_id,
                    sim_ts=float(context.timestamp),
                    mode=cache_hit.get("mode", ""),
                )
                return (
                    original_index,
                    reason,
                    f"cache:{cache_hit.get('mode', '')}",
                    cache_hit.get("distribution") or {},
                )

        # Ticket 090 — pendant le rejeu d'une reprise à chaud, resservir la décision que CE run
        # a déjà prise, au lieu de la repayer. La condition `gel_actif()` est essentielle : hors
        # de la fenêtre de rejeu, la trace deviendrait un cache permanent, et le run cesserait
        # d'être journalisé sur son périmètre complet. Une clé manquée n'est pas un échec — on
        # appelle le modèle — mais elle est comptée, et alarmée au-delà d'un seuil : un rejeu qui
        # ne retrouve pas ses propres choix ne reconstruit pas l'état qu'on croit reprendre.
        if gel_actif():
            _rejoue = rejeu_decisions.chercher(
                context.person.person_id, context.activity_id, float(context.timestamp)
            )
            if _rejoue is not None:
                _plan = next(
                    (o for o in options if o.get_code() == _rejoue.get("code_plan")), None
                )
                if _plan is not None:
                    # Aucune écriture de mémoire ici : le rejeu ne doit rien réapprendre, et le
                    # gel du ticket 075 l'interdit déjà de son côté.
                    return (
                        options.index(_plan),
                        _rejoue.get("raison", ""),
                        f"rejeu:{_rejoue.get('fournisseur', '')}",
                        _rejoue.get("distribution") or {},
                    )

        # Cache miss sur la branche « mémoire vide » : le payload reste à construire.
        if payload is None:
            payload = await self.build_travel_plan_payload(
                context, shuffled_options, destination, departure_time, anticipation
            )

        _pl = PipelineLogger.get()
        _rec = _pl.get_record(context.person.person_id) if _pl is not None else None

        try:
            if _rec is not None:
                _rec.T_llm_start = time.time()
            # Ticket 084 — la restriction de routage part AVEC la requête : la passerelle
            # refuse alors de servir depuis une autre instance, à la sélection et donc avant
            # qu'un appel ne soit payé. Ticket 092 : elle n'est plus posée ICI mais sur le
            # client, seuil unique par lequel sortent AUSSI les réflexions STM et LTM — les
            # poser appel par appel avait laissé la mémoire se faire écrire par un autre
            # modèle. Le filtre `allowed_providers` ci-dessous reste une défense en
            # profondeur : il constate après coup ce que la restriction empêche.

            attente_instance = None
            if force_provider:
                payload["force_provider"] = force_provider
                # L'instance épinglée porte son attente : un modèle local ne sert qu'un appel
                # à la fois, les tâches suivantes patientent en file et le défaut du client
                # (calé sur un fournisseur distant) les ferait expirer avant leur tour.
                _cfg = settings.llm.providers.get(force_provider)
                attente_instance = getattr(_cfg, "wait_timeout", None) if _cfg else None
            llm_result = await self.llm_client.execute(
                payload, wait_timeout=attente_instance
            )
            _t_after_llm = time.time()
            provider_used = llm_result.provider_used or ""
            if trace is not None:
                trace["payload"] = payload
                trace["fournisseur"] = provider_used
                trace["identifiant_lot"] = llm_result.task_id
                trace["souvenirs"] = list(payload["agents"][0].get("history", []) or [])
                trace["presentees_modes"] = [
                    t.get("mode") for t in payload["agents"][0]["trajectories"]
                ]
                trace["reponse_brute"] = (
                    json.dumps(
                        [a.model_dump() for a in llm_result.agents],
                        ensure_ascii=False,
                        default=str,
                    )
                    if llm_result.agents
                    else None
                )
            if (
                allowed_providers is not None
                and llm_result.ok
                and provider_used not in allowed_providers
            ):
                # Substitution silencieuse de la passerelle (bascule vers un autre modèle
                # après erreur de parse) : refusée, jamais archivée comme décision (Q3).
                if trace is not None:
                    trace["substitution_refusee"] = provider_used
                logger.warning(
                    f"[035] Réponse servie par {provider_used!r}, hors des instances admises "
                    f"{sorted(allowed_providers)} — substitution refusée pour {context.person.person_id}"
                )
                return -1, f"substitution_refusee:{provider_used}", provider_used, {}

            if _rec is not None:
                _post_ms = (llm_result.timing.post_ms if llm_result.timing else 0) or 0
                _rec.T_llm_sent = _rec.T_llm_start + _post_ms / 1000
                _rec.T_llm_result = _t_after_llm
                _timing_p5 = llm_result.timing.timing_p5 if llm_result.timing else None
                if _timing_p5 and _pl is not None:
                    _pl.apply_timing_p5(context.person.person_id, _timing_p5)

            if llm_result.ok:
                agent_result = llm_result.agents[0]
                # Le LLM note toutes les options (somme = 100) ; le mode effectif est
                # tiré au sort dans cette distribution. Les poids sont ré-alignés sur
                # `sorted_options` (ordre déterministe par code) pour que le tirage ne
                # dépende pas du mélange anti-biais de position appliqué au prompt.
                weights = None
                weights_are_fallback = False
                reasons = None
                if agent_result.probabilities:
                    # Modes tels qu'ils ont été envoyés dans le prompt : ils permettent de
                    # réaligner une réponse dont les index sont hors bornes (le modèle a
                    # renuméroté les options) au lieu d'en perdre la masse.
                    sent_modes = [
                        t.get("mode") for t in payload["agents"][0]["trajectories"]
                    ]
                    shuffled_weights = normalize_option_probabilities(
                        agent_result.probabilities,
                        len(shuffled_options),
                        modes=sent_modes,
                        context=f"agent={context.person.person_id} activity={context.activity_id}",
                    )
                    # Repli uniforme (vecteur LLM inexploitable) : le tirage reste valable
                    # pour CE trajet, mais la distribution n'est pas une décision du modèle
                    # — elle ne doit jamais atteindre le cache persistant.
                    weights_are_fallback = isinstance(shuffled_weights, UniformFallback)
                    if trace is not None:
                        trace["poids_presentes"] = [float(w) for w in shuffled_weights]
                        trace["repli_uniforme"] = weights_are_fallback
                    position_in_sorted = {
                        id(opt): i for i, opt in enumerate(sorted_options)
                    }
                    weights = [0.0] * len(sorted_options)
                    for opt, w in zip(shuffled_options, shuffled_weights):
                        weights[position_in_sorted[id(opt)]] += w
                    index = draw_index(
                        weights,
                        *seed_parts,
                        min_prob_threshold=settings.agent.mode_choice_truncation_threshold,
                    )
                    decision_list = sorted_options

                    # Justification PAR OPTION (2026-08-26) : `normalize_option_probabilities`
                    # ne renvoie que les poids, la `reason` de chaque entrée s'y perdrait sinon.
                    # Repérée par l'index envoyé (source de vérité côté prompt), puis reportée
                    # sur `sorted_options` comme les poids, pour retrouver la justification de
                    # l'option effectivement tirée.
                    reasons = [None] * len(sorted_options)
                    for entry in agent_result.probabilities:
                        entry_reason = getattr(entry, "reason", None)
                        if not entry_reason:
                            continue
                        try:
                            entry_idx = int(entry.index)
                        except (TypeError, ValueError):
                            continue
                        if 0 <= entry_idx < len(shuffled_options):
                            opt = shuffled_options[entry_idx]
                            reasons[position_in_sorted[id(opt)]] = entry_reason
                else:
                    # Réponse à l'ancien format (un index choisi) — repli sans tirage.
                    index = agent_result.chosen_index
                    decision_list = shuffled_options

                if isinstance(index, int) and 0 <= index < len(decision_list):
                    reason = (
                        (reasons[index] if reasons is not None else None)
                        or agent_result.reason
                        or "Pas de justification fournie."
                    )

                    # Normalisation de la raison (alignement avec aplan_trip_old)
                    if "is chosen because it" in reason:
                        reason = f"This plan {reason.split('is chosen because it', 1)[1].strip()}"

                    chosen_plan = decision_list[index]

                    distribution = {}
                    if weights is not None:
                        modes = [opt.mode_label() for opt in sorted_options]
                        distribution = mode_distribution(weights, modes)
                        reason = (
                            f"{reason} [Répartition estimée : "
                            f"{_format_distribution(distribution)} — mode tiré au sort.]"
                        )

                    # Écriture de la décision en short-term memory pour alimenter la réflexion journalière
                    plan_summary = env_ob_to_text(
                        "travel_plan", chosen_plan.model_dump()
                    )
                    stm_msg = f"[ TRAVEL_PLAN ] Plan to head <{destination}> chosen by gateway LLM.\n{plan_summary}\nReasoning: {reason}"
                    self.add_short_term_memory(
                        context,
                        stm_msg,
                        timestamp=context.timestamp,
                        importance=_gravite_de_la_contrainte(context),
                        axes=_axes_de_la_decision(
                            context, chosen_plan, destination, weather
                        ),
                    )

                    original_index = options.index(chosen_plan)
                    if _rec is not None:
                        _rec.T_extract_end = time.time()

                    # --- Insertion asynchrone dans le cache (fire-and-forget) ---
                    # C'est la distribution qui est mise en cache, pas la décision : au
                    # prochain hit, un nouveau tirage aura lieu sur ces mêmes probabilités.
                    # Jamais pour un repli uniforme : le cache n'a pas de mode dégradé,
                    # un repli persisté servirait du hasard aux runs suivants.
                    if self.llm_cache is not None and weights_are_fallback:
                        logger.info(
                            f"[cache] store refusé — distribution de repli uniforme non persistée | "
                            f"agent={context.person.person_id} activity={context.activity_id}"
                        )
                    elif self.llm_cache is not None:
                        mode = chosen_plan.mode_label()
                        _cache_task = create_background_task(
                            self.llm_cache.store(
                                agent_id=context.person.person_id,
                                activity_id=context.activity_id,
                                timestamp=context.timestamp,
                                options=sorted_options,
                                memory_text=memory_text,
                                chosen_plan_code=chosen_plan.get_code(),
                                mode=mode,
                                weather=weather,
                                probabilities=weights,
                                extra_key=anticipation_key,
                                traits_key=_traits_signature(
                                    context.person.identity.traits_json
                                ),
                            )
                        )
                        _cache_task.add_done_callback(
                            lambda t: (
                                logger.warning(f"Cache store failed: {t.exception()}")
                                if not t.cancelled() and t.exception()
                                else None
                            )
                        )
                        logger.debug(
                            f"Cache store task created for person {context.person.person_id}, activity {context.activity_id}, chosen plan mode: {mode}"
                        )

                    if trace is not None:
                        trace["distribution"] = distribution
                        trace["index_presente"] = shuffled_options.index(chosen_plan)
                        trace["raison"] = reason
                    # Ticket 090 — consigner la décision pour qu'une reprise à chaud la
                    # ressorte sans la repayer. Rien n'est tracé pendant le gel : une journée
                    # rejouée ne se trace pas deux fois.
                    if not gel_actif():
                        rejeu_decisions.tracer(
                            context.person.person_id,
                            context.activity_id,
                            float(context.timestamp),
                            code_plan=chosen_plan.get_code(),
                            raison=reason,
                            fournisseur=provider_used,
                            distribution=distribution,
                        )
                    # ── Ticket 095, lot E — la décision, avec le MODÈLE qui l'a produite ──
                    # `llm_exchanges.jsonl` portait déjà le fournisseur ; le journal
                    # applicatif, non. Une décision lue dans `app.log` ne disait pas quel
                    # modèle l'avait prise, et il fallait recouper deux fichiers pour
                    # l'établir. C'est la reconstitution d'une exécution après coup qui en
                    # dépend, et elle ne coûte rien.
                    logger.info(
                        f"[decision] agent={context.person.person_id} "
                        f"activite={context.activity_id} "
                        f"mode={chosen_plan.mode_label()} "
                        f"raison={reason} "
                        f"origine={'cache' if (trace or {}).get('cache') else 'direct'} "
                        f"modele={origine_modele(provider_used)}"
                    )
                    # Retourne l'index dans la liste originale (non mélangée) pour cohérence avec le caller
                    return original_index, reason, provider_used, distribution

                if _rec is not None:
                    _rec.T_extract_end = time.time()

            error_msg = llm_result.error or "Format de réponse invalide ou timeout."
            logger.warning(
                f"aplan_trip: gateway a retourné un résultat invalide pour {context.person.person_id}: {error_msg}"
            )
            if trace is not None:
                trace["erreur"] = error_msg
                # Nature de l'échec telle que le gateway l'a qualifiée. Le texte seul ne
                # suffit pas : « Providers saturés ou indisponibles » décrit aussi bien une
                # file d'attente qu'un quota mort pour la journée, et l'appelant doit
                # attendre dans un cas, patienter quelques secondes dans l'autre.
                if llm_result.error_kind:
                    trace["genre_erreur"] = llm_result.error_kind
                if llm_result.resume_at:
                    trace["reprise_a"] = llm_result.resume_at
            return -1, error_msg, provider_used, {}

        except Exception as e:
            logger.exception(f"Erreur lors de l'appel à l'API Gateway LLM: {e}")
            if trace is not None:
                trace["erreur"] = str(e)
            return -1, str(e), "", {}

    async def trigger_short_term_reflection_for_all_people(
        self,
        timestamp: int,
        people: list[Person],
        motif: str = "",
        declencheur: str = "",
    ):
        """
        Reflect on all short-term memories of all people at the given timestamp.
        This is used to process all short-term memories at once, e.g. at the end of the day.

        `motif` et `declencheur` (ticket 075) : ce qui a rendu l'agent éligible — `seuil`,
        `plancher journalier` ou `rupture` — est calculé par le CONTRÔLEUR, seul à connaître
        l'état du tampon au moment du test. Sans ces deux champs, le journal de mémoire
        constate une consolidation sans pouvoir dire ce qui l'a provoquée, c'est-à-dire
        l'essentiel de ce qu'on vient y lire. Vides, rien ne change : la consolidation a lieu
        à l'identique.
        """
        if settings.agent.long_term_memory_enabled is False:
            logger.info("Long-term memory is disabled, skipping reflection.")
            return

        import asyncio

        sem = asyncio.Semaphore(10)

        async def _reflect_one(person):
            async with sem:
                context = Context(
                    person=person,
                    timestamp=timestamp,
                    data={
                        "type": "reflection",
                        "motif": motif,
                        "declencheur": declencheur,
                    },
                )
                await self.reflect_on_short_term_memory(context)

        await asyncio.gather(*[_reflect_one(p) for p in people])

    async def trigger_long_term_reflection_for_all_people(
        self, timestamp: int, from_date: datetime, people: list[Person]
    ):
        if (
            settings.agent.long_term_memory_enabled is False
            or settings.agent.long_term_self_reflect_enabled is False
        ):
            logger.info(
                "Long-term memory is disabled or Self reflection is disable, skipping self reflection."
            )
            return
        if gel_actif():
            # Rejeu d'une reprise (ticket 075) : cette auto-réflexion a déjà eu lieu et son
            # entrée est déjà en mémoire. La refaire l'écrirait deux fois.
            return

        for person in people:
            context = Context(
                person=person, timestamp=timestamp, data={"type": "self_reflection"}
            )
            await self.reflect_on_long_term_memory(context, from_date)

    async def reflect_on_long_term_memory(self, context: Context, from_date: datetime):
        if settings.agent.long_term_memory_enabled is False:
            logger.info("Long-term memory is disabled, skipping reflection.")
            return

        all_entries = self.long_term_memory.get_last_user_memories(
            person_id=context.person.person_id,
            from_date=from_date,
        )
        if not all_entries:
            logger.info(
                f"No long-term memory available for reflection for {context.person.person_id}"
            )
            return

        # `gama_timestamp` et non `.timestamp()` : le `datetime` du souvenir porte des
        # champs MURAUX, et `.timestamp()` les relirait dans le fuseau du processus —
        # `humanize_date` retraduirait ensuite, et les deux conventions se cumuleraient
        # en un décalage d'une heure dans le texte lu par le modèle.
        entries_text = "\n".join(
            f"- Time {humanize_date(gama_timestamp(entry.timestamp))}: {entry.content}"
            for entry in all_entries
        )
        identity_description = self.get_person_identity_description(context.person)

        # Mémoïsation exacte (ticket 012) — même principe que la réflexion STM.
        memo_key = None
        reflection: str | None = None
        if self.reflection_memo is not None:
            memo_key = ReflectionMemoStore.make_key(
                person_id=context.person.person_id,
                category="ltm_self_reflection",
                identity=identity_description,
                context_text=entries_text,
                departure_timestamp=float(context.timestamp),
                llm_params=settings.agent.llm_params,
            )
            hit = await asyncio.to_thread(
                self.reflection_memo.lookup, memo_key, "ltm_self_reflection"
            )
            if hit is not None:
                reflection = hit["reflection"]
                logger.info(
                    f"[reflection-memo] hit LTM — auto-réflexion servie sans appel LLM | "
                    f"person={context.person.person_id} (payée par {hit['provider'] or '?'})"
                )

        if reflection is None:
            payload = {
                "category": "ltm_self_reflection",
                "instances_admises": instances_pour("ltm_self_reflection"),
                "agents": [
                    {
                        "agent_id": context.person.person_id,
                        "perception": identity_description,
                        "context": entries_text,
                        "departure_timestamp": float(context.timestamp),
                    }
                ],
                "parameters": {**settings.agent.llm_params},
            }

            llm_result = await self.llm_client.execute(payload)
            results = llm_result.agents
            if not results:
                logger.error(
                    f"LTM self-reflection gateway returned no result for {context.person.person_id}"
                )
                return
            # AgentResponse accepte les champs hors schéma (extra=allow) —
            # "reflection" est porté par la catégorie ltm_self_reflection.
            reflection = getattr(results[0], "reflection", "") or ""
            # Ticket 095, lot E — rare (13 par run) et à fort enjeu : c'est celle qui relit
            # toute la mémoire longue.
            logger.info(
                f"[auto-reflexion] agent={context.person.person_id} "
                f"modele={origine_modele(llm_result.provider_used)}"
            )
            if self.reflection_memo is not None:
                await asyncio.to_thread(
                    self.reflection_memo.store,
                    memo_key,
                    context.person.person_id,
                    "ltm_self_reflection",
                    reflection,
                    None,
                    llm_result.provider_used or "",
                )

        try:
            entry = MemoryEntry(
                person_id=context.person.person_id,
                content=reflection,
                timestamp=wall_clock(context.timestamp),
                memory_type=MemoryType.REFLECTION,
            )
            # Ticket 075 — l'auto-réflexion long terme est une consolidation d'un autre genre :
            # elle ne consomme aucune entrée de mémoire courte, elle relit la mémoire longue.
            # Elle a sa section pour cette raison même, sinon sa trace se confondrait avec une
            # écriture ordinaire.
            _journal = journal()
            if _journal is not None:
                _journal.ouvrir_agent(
                    context.person.person_id, _traits_de(context.person)
                )
                _journal.consolidation_debut(
                    context.person.person_id,
                    wall_clock(context.timestamp),
                    "auto-réflexion long terme",
                    "relecture périodique de la mémoire longue "
                    f"(intervalle {settings.agent.long_term_reflect_interval} s simulées)",
                    [],
                )
                _journal.reflexion(context.person.person_id, reflection)
            await self.aadd_long_term_memory(context, entry)
        except Exception as e:
            logger.error(
                f"Failed to store LTM self-reflection for person {context.person.person_id}, err: {e}"
            )

    def _marquer_concept_modifie(self, person_id: str) -> None:
        """Un concept mis à jour SUR PLACE doit être persisté comme une écriture neuve.

        Les opérations `confirmer`, `preciser` et `contredire` n'ajoutent aucune entrée : elles
        modifient un objet déjà en mémoire vive. Sans ce marquage, le compteur monterait en RAM
        et retomberait à zéro au rechargement — la consolidation serait parfaitement invisible.
        """
        if self.long_term_memory is None:
            return
        self.long_term_memory._dirty.add(person_id)
        self.long_term_memory._schedule_flush()

    _JOURS_SANS_CONTRADICTION_ALARME = 2

    def _compter_operations(self, operations: dict, jour_simule) -> None:
        """Compteur d'opérations par cycle, et l'alarme du modèle qui confirme tout.

        Un modèle qui ne contredit jamais laisse l'agent agir sur des croyances qui ont cessé
        d'être vraies, et l'hystérésis que l'expérience cherche à observer devient ininterprétable
        : la reprise se gagne par la confiance des concepts, pas par l'oubli.
        """
        if not operations:
            return
        if not hasattr(self, "_jours_sans_contradiction"):
            self._jours_sans_contradiction: set = set()
            self._alarme_confirme_tout = False

        logger.info(
            "[concepts] opérations du cycle — "
            + ", ".join(f"{k} {v}" for k, v in sorted(operations.items()))
        )

        if operations.get(CONTREDIRE):
            self._jours_sans_contradiction.clear()
            if self._alarme_confirme_tout:
                self._alarme_confirme_tout = False
                logger.info("[concepts] le modèle contredit de nouveau ses croyances")
            return

        # Des concepts ont été produits, aucun ne contredit : le jour compte.
        if operations.get(CONFIRMER) or operations.get(CREER):
            self._jours_sans_contradiction.add(jour_simule)

        if (
            len(self._jours_sans_contradiction) > self._JOURS_SANS_CONTRADICTION_ALARME
            and not self._alarme_confirme_tout
        ):
            self._alarme_confirme_tout = True
            logger.error(
                f"[ALARME] aucune contradiction de concept sur "
                f"{len(self._jours_sans_contradiction)} jours simulés, alors que des concepts "
                f"sont produits — le modèle confirme tout. Les croyances des agents ne se "
                f"révisent plus, et la reprise mesurée par l'expérience d'hystérésis devient "
                f"ininterprétable."
            )

    # Fenêtre d'observation du taux de croyances montrées, en nombre d'appels de réflexion.
    _FENETRE_CROYANCES = 50
    # Au-delà, le mécanisme de correction des concepts est hors service DE FAIT : le modèle
    # ne peut confirmer ni préciser ce qu'on ne lui montre pas. Mesuré à 68 % sur le run du
    # ticket 075, et à 100 % pour l'agent sans voiture — d'où 0 précision sur 231 concepts.
    _SEUIL_CROYANCES_VIDES = 0.5

    def _compter_croyances_montrees(self, person_id: str, montrees: int) -> None:
        """Taux d'appels de réflexion où l'agent ne s'est vu montrer AUCUNE croyance.

        Ticket 077, lot E4. C'est le dénominateur qui manquait au run du 075 : sans lui, la
        redondance des concepts s'impute au modèle, alors que la mesure l'innocente — quand
        `known_beliefs` n'est pas vide, il confirme 74 fois sur 76. Ce compteur est la GARDE
        du lot A : si les paniers se vident de nouveau, pour cette raison ou pour une autre,
        l'alarme le dit avant qu'un run de trente jours ne soit à refaire.
        """
        if not hasattr(self, "_croyances_fenetre"):
            self._croyances_fenetre: deque = deque(maxlen=self._FENETRE_CROYANCES)
            self._alarme_croyances_vides = False
        self._croyances_fenetre.append(1 if montrees == 0 else 0)
        if len(self._croyances_fenetre) < self._FENETRE_CROYANCES:
            return
        part_vide = sum(self._croyances_fenetre) / len(self._croyances_fenetre)
        if part_vide >= self._SEUIL_CROYANCES_VIDES and not self._alarme_croyances_vides:
            self._alarme_croyances_vides = True
            logger.error(
                f"[ALARME] aucune croyance montrée au modèle dans {part_vide:.0%} des "
                f"{len(self._croyances_fenetre)} dernières réflexions (seuil : "
                f"{self._SEUIL_CROYANCES_VIDES:.0%}) — le panier (mode, motif) ne désigne "
                f"aucun candidat. Le modèle ne peut ni confirmer ni préciser : il ne lui "
                f"reste qu'à créer, et les concepts s'empilent en reformulations. Vérifier "
                f"d'abord que les axes d'objet des concepts ne sont pas vides."
            )
        elif part_vide < self._SEUIL_CROYANCES_VIDES and self._alarme_croyances_vides:
            self._alarme_croyances_vides = False
            logger.info(
                f"[concepts] croyances de nouveau montrées au modèle "
                f"({1 - part_vide:.0%} des appels) — alarme réarmée"
            )

    async def reflect_on_short_term_memory(self, context: Context):
        mem = self.get_short_term_memory(context.person.person_id)
        group_messages, all_messages = mem.get_all_message_and_group()

        if not all_messages:
            logger.info("No short-term memory available for reflection.")
            return

        exp = []
        for group in group_messages:
            if group:
                activity = (
                    PersonScheduler(context.person).get_activity(group[0].activity_id)
                    if group[0].activity_id
                    else None
                )
                exp.append(
                    {
                        "purpose": activity.purpose if activity else None,
                        "observations": [msg.content for msg in group],
                    }
                )
        # Ticket 071, lot 3 — les concepts que l'agent tient déjà sur les modes et motifs de
        # sa journée sont montrés dans l'appel qui a DÉJÀ lieu. Le modèle désigne celui qu'il
        # met à jour, ou n'en désigne aucun : coût marginal nul, aucun seuil de similarité
        # arbitraire à calibrer, et il dispose du contexte qu'un seuil n'a pas.
        _paniers = {panier_de(m.axe_objet, m.axe_motif) for m in all_messages}
        _connus = _concepts_du_jour(
            self.long_term_memory, context.person.person_id, _paniers
        )
        # Poignées courtes (K1, K2…) plutôt que les identifiants de documents : le modèle a
        # moins de latitude pour en inventer un, et la correspondance est vérifiée au retour.
        _par_poignee = {f"K{i + 1}": e for i, e in enumerate(_connus)}
        self._compter_croyances_montrees(context.person.person_id, len(_par_poignee))
        # ── Ticket 100, lot 4 — ce que le foyer a raconté ce soir ───────────────────────
        # Le bloc est une ENTRÉE de l'appel, au même titre que les expériences de la journée.
        # Rien n'est écrit dans la mémoire du receveur : c'est le modèle qui décide s'il en
        # tire une croyance, et une phrase entendue qui ne résonne avec rien disparaît avec
        # l'appel. C'est le bon défaut — la mémoire ne grossit pas d'avoir écouté.
        #
        # Vide quand le drapeau est éteint, quand l'agent vit seul, ou quand personne n'a rien
        # produit de neuf depuis sa dernière consolidation.
        _bloc_foyer = ""
        try:
            _bloc_foyer = foyer.bloc_du_soir(
                self.long_term_memory, context.person, wall_clock(context.timestamp)
            )
        except Exception as err:  # noqa: BLE001 — le foyer ne fait jamais tomber une réflexion
            logger.error(
                f"[ALARME] [foyer] bloc du soir impossible pour "
                f"{context.person.person_id} ({err}) — la consolidation continue SANS lui, "
                f"donc sans ce que le foyer avait à dire ce soir."
            )

        _contexte_reflexion = {
            "today": exp,
            "known_beliefs": [
                {
                    "id": poignee,
                    "belief": json.loads(e.content)[0]
                    if e.content.startswith("[")
                    else e.content,
                    "times_observed": e.observations,
                    "times_contradicted": e.contre_exemples,
                }
                for poignee, e in _par_poignee.items()
            ],
        }
        if _bloc_foyer:
            _contexte_reflexion["household"] = _bloc_foyer
        experiences_text = json.dumps(
            _contexte_reflexion, indent=2, ensure_ascii=False
        )

        identity_description = self.get_person_identity_description(context.person)
        custom_guidelines = (
            f"\n**IMPORTANT CUSTOM GUIDELINES** {settings.agent.reflection_custom_guidelines}"
            if settings.agent.reflection_custom_guidelines
            else ""
        )

        # Mémoïsation exacte (ticket 012) : même agent, même vécu, mêmes consignes
        # ⇒ même introspection. Hit ⇒ appel LLM évité ; les effets (consommation
        # STM, écritures LTM) restent strictement identiques à un appel réel.
        memo_key = None
        reflection: str | None = None
        concepts: list = []
        if self.reflection_memo is not None:
            memo_key = ReflectionMemoStore.make_key(
                person_id=context.person.person_id,
                category="stm_reflection",
                identity=identity_description,
                context_text=experiences_text,
                guidelines=custom_guidelines,
                departure_timestamp=float(context.timestamp),
                llm_params=settings.agent.llm_params,
                # Le schéma de sortie a changé au lot 1 du ticket 071 : chaque concept porte
                # un niveau de gravité. Une réponse mémoïsée sous l'ancien schéma n'en a pas,
                # et la servir produirait des concepts de gravité nulle SANS ERREUR — or zéro
                # est la gravité d'un trajet parfait. La version fait donc MANQUER le cache
                # plutôt que de servir de travers. Le cache accumulé sous l'ancien schéma est
                # perdu : c'est le prix du champ, et il est annoncé.
                schema_version=SCHEMA_REFLEXION_VERSION,
            )
            hit = await asyncio.to_thread(
                self.reflection_memo.lookup, memo_key, "stm_reflection"
            )
            if hit is not None:
                reflection, concepts = hit["reflection"], hit["concepts"]
                logger.info(
                    f"[reflection-memo] hit STM — réflexion servie sans appel LLM | "
                    f"person={context.person.person_id} (payée par {hit['provider'] or '?'})"
                )

        if reflection is None:
            payload = {
                "category": "stm_reflection",
                "instances_admises": instances_pour("stm_reflection"),
                "min_tpm_required": settings.agent.stm_reflection_min_tpm,
                "agents": [
                    {
                        "agent_id": context.person.person_id,
                        "perception": identity_description,
                        "context": experiences_text,
                        "departure_timestamp": float(context.timestamp),
                    }
                ],
                "parameters": {
                    "custom_guidelines": custom_guidelines,
                    **settings.agent.llm_params,
                },
            }

            llm_result = await self.llm_client.execute(payload)
            results = llm_result.agents
            if not results:
                logger.error(
                    f"STM reflection gateway returned no result for {context.person.person_id}"
                )
                return

            agent_result = results[0]
            # AgentResponse accepte les champs hors schéma (extra=allow) —
            # "reflection"/"concepts" sont portés par la catégorie stm_reflection.
            reflection = (getattr(agent_result, "reflection", "") or "").strip()
            concepts = getattr(agent_result, "concepts", []) or []
            # Ticket 095, lot E — changer le modèle des réflexions change le CONTENU de la
            # mémoire, donc les décisions. Savoir lequel a écrit quoi n'est pas un détail
            # d'infrastructure.
            logger.info(
                f"[reflexion-stm] agent={context.person.person_id} "
                f"concepts={len(concepts)} "
                f"modele={origine_modele(llm_result.provider_used)}"
            )

            if self.reflection_memo is not None:
                # Le store refuse le vide (D3) : un échec de génération ne se rejoue pas.
                await asyncio.to_thread(
                    self.reflection_memo.store,
                    memo_key,
                    context.person.person_id,
                    "stm_reflection",
                    reflection,
                    concepts,
                    llm_result.provider_used or "",
                )

        self.get_short_term_memory(context.person.person_id).remove_batch(all_messages)
        start_timestamp = all_messages[0].timestamp

        # ── Ticket 075 — ouverture de la section de journal ──────────────────────────────
        # Le MOTIF est calculé par le contrôleur au moment de l'éligibilité (seuil d'entrées,
        # plancher de 22 h, rupture de gravité cumulée) : il descend par `context.data`. Sans
        # lui, le journal dirait qu'une consolidation a eu lieu sans pouvoir dire pourquoi —
        # c'est-à-dire l'essentiel de ce qu'on vient y lire.
        _journal = journal()
        if _journal is not None:
            _motif = (context.data or {}).get("motif") or "non précisé"
            _journal.ouvrir_agent(
                context.person.person_id, _traits_de(context.person)
            )
            _journal.consolidation_debut(
                context.person.person_id,
                wall_clock(context.timestamp),
                _motif,
                (context.data or {}).get("declencheur")
                or "motif non transmis par le contrôleur",
                all_messages,
            )
            _journal.reflexion(context.person.person_id, reflection)

        # Ticket 071, lot 1 — PLANCHER de gravité : la plus forte gravité déterministe parmi
        # les entrées que cette réflexion consomme. C'est un FAIT mesuré par la simulation, que
        # le jugement du modèle ne pourra pas descendre.
        plancher = max((float(m.importance or 0.0) for m in all_messages), default=0.0)

        # Axes de la journée consommée (lot 2). Ils sont pris sur l'entrée la PLUS GRAVE, et
        # non sur la dernière ni sur la plus fréquente : c'est l'épisode qui a marqué la
        # journée qui la caractérise. À gravité égale, la dernière l'emporte, parce qu'elle est
        # la plus proche du moment où la réflexion est écrite.
        _pivot = max(
            all_messages,
            key=lambda m: (float(m.importance or 0.0), m.timestamp),
            default=None,
        )
        axes_du_groupe = {
            "axe_objet": getattr(_pivot, "axe_objet", None),
            "axe_lieu": getattr(_pivot, "axe_lieu", None),
            "axe_creneau": getattr(_pivot, "axe_creneau", None),
            "axe_motif": getattr(_pivot, "axe_motif", None),
            "axe_meteo": getattr(_pivot, "axe_meteo", None),
        }

        entries = []
        try:
            # La réflexion narrative hérite du plancher : elle raconte la journée, et une
            # journée qui contient un choc n'est pas une journée ordinaire. Le schéma ne
            # demande pas de niveau pour la réflexion elle-même, seulement pour les concepts.
            entries.append(
                MemoryEntry(
                    person_id=context.person.person_id,
                    content=reflection,
                    timestamp=start_timestamp,
                    memory_type=MemoryType.REFLECTION,
                    importance=plancher,
                    **axes_du_groupe,
                )
            )

            # Le RANG ne sert que de départage à l'intérieur d'un même niveau : il faut donc
            # savoir combien de concepts partagent chaque niveau, et dans quel ordre ils sont
            # arrivés. Un ordre est relatif au lot ; une valeur doit être comparable d'un jour
            # et d'un agent à l'autre.
            normalises = [_normaliser_concept(c) for c in concepts]
            effectif: dict = {}
            for _lu in normalises:
                effectif[_lu.niveau] = effectif.get(_lu.niveau, 0) + 1
            rang_courant: dict = {}
            operations_vues: dict = {}

            for lu in normalises:
                cinq, niveau, valence, mode = lu.cinq, lu.niveau, lu.valence, lu.mode
                origine_concept = lu.origine
                rang_courant[niveau] = rang_courant.get(niveau, 0) + 1
                i_llm = gravite_jugee(
                    niveau, n_niveau=effectif[niveau], rang=rang_courant[niveau]
                )
                importance = gravite_concept(i_llm, plancher)

                # ── Ticket 071, lot 3 — le concept se CORRIGE au lieu de s'empiler ────────
                operation = lu.operation
                cible = _par_poignee.get(lu.cible) if lu.cible else None
                if operation != CREER and cible is None:
                    # Une cible inconnue ne doit pas faire perdre le concept ni toucher un
                    # existant au hasard : on crée, et on le DIT. Un modèle qui désignerait
                    # systématiquement des cibles fantômes passerait sinon inaperçu.
                    logger.warning(
                        f"[concepts] opération « {operation} » sur une cible inconnue "
                        f"« {lu.cible} » | person={context.person.person_id} — repli sur "
                        f"« {CREER} », aucun concept existant n'est modifié"
                    )
                    operation = CREER
                operations_vues[operation] = operations_vues.get(operation, 0) + 1

                if operation in (CONFIRMER, PRECISER):
                    # Rien de neuf n'est écrit : le concept existant est mis à jour sur place.
                    # Ticket 075 — mise à jour SUR PLACE : sans l'avant, aucune trace ne dirait
                    # jamais ce que cette opération a changé.
                    _avant = (cible.content, cible.observations, cible.confiance)
                    if operation == CONFIRMER:
                        cible.observations = int(cible.observations or 0) + 1
                    else:
                        # `preciser` : le contenu est remplacé, compteurs et historique
                        # CONSERVÉS — c'est la même croyance, dite plus finement.
                        cible.content = json.dumps(cinq, ensure_ascii=False)
                        cible.tags = ",".join(cinq[1:])
                    cible.derniere_observation = start_timestamp
                    cible.force = force_apres_rappel(cible.force)
                    cible.importance = max(float(cible.importance or 0.0), importance)
                    self._marquer_concept_modifie(context.person.person_id)
                    tracer_operation(
                        context.person.person_id,
                        "confirmé" if operation == CONFIRMER else "précisé",
                        start_timestamp,
                        doc_id=str(getattr(cible, "doc_id", "") or ""),
                    )
                    if _journal is not None:
                        _journal.operation_concept(
                            context.person.person_id,
                            "confirmé" if operation == CONFIRMER else "précisé",
                            avant=str(_avant[0]),
                            apres=str(cible.content)
                            if operation == PRECISER
                            else "(inchangé)",
                            observations=f"{_avant[1]} → {cible.observations}",
                            confiance=f"{_avant[2]:.2f} → {cible.confiance:.2f}",
                        )
                    continue

                if operation == CONTREDIRE:
                    _contre_avant = int(cible.contre_exemples or 0)
                    _confiance_avant = cible.confiance
                    cible.contre_exemples = int(cible.contre_exemples or 0) + 1
                    cible.derniere_observation = start_timestamp
                    if not cible.est_servi and not cible.depasse_le:
                        # Marqué et DATÉ, jamais supprimé : cette mise à l'écart est la trace
                        # lisible du changement d'habitude que l'expérience cherche.
                        #
                        # ⚠ La date est posée quand le concept CESSE D'ÊTRE SERVI, et non
                        # quand il devient « dépassé » au sens des trois contre-exemples.
                        # Défaut trouvé en écrivant les tests du lot 3 : un concept sort du
                        # panier dès qu'il n'est plus servi, donc il n'est plus montré au
                        # modèle, donc il ne peut plus être contredit. Avec peu
                        # d'observations, le seuil de trois contradictions est ATTEIGNABLE
                        # SEULEMENT si la mise hors service arrive après — sinon le concept
                        # restait en service nul, jamais daté, et l'observable que
                        # l'expérience d'hystérésis cherche n'était jamais écrit.
                        #
                        # La spécification rattache d'ailleurs la trace datée à la cessation
                        # de service — « sous un seuil, le concept cesse d'être servi sans
                        # être supprimé : sa mise à l'écart datée est la trace du changement
                        # d'habitude » — et non au seuil de trois.
                        cible.depasse_le = start_timestamp.isoformat()
                        logger.info(
                            f"[concepts] concept MIS À L'ÉCART pour "
                            f"{context.person.person_id} : {cible.contre_exemples} "
                            f"contradictions contre {cible.observations} confirmations, "
                            f"confiance {cible.confiance:.2f} — il cesse d'être servi et "
                            f"reste CONSERVÉ en mémoire"
                            + (
                                " ; dépassé au sens des trois contre-exemples"
                                if cible.est_depasse
                                else ""
                            )
                        )
                    self._marquer_concept_modifie(context.person.person_id)
                    tracer_operation(
                        context.person.person_id,
                        "contredit",
                        start_timestamp,
                        doc_id=str(getattr(cible, "doc_id", "") or ""),
                    )
                    if _journal is not None:
                        _journal.operation_concept(
                            context.person.person_id,
                            "contredit",
                            avant=str(cible.content),
                            contre_exemples=f"{_contre_avant} → {cible.contre_exemples}",
                            confiance=f"{_confiance_avant:.2f} → {cible.confiance:.2f}",
                            note=(
                                f"**mis à l'écart** le {str(cible.depasse_le)[:16]} — il cesse "
                                f"d'être servi, il n'est PAS supprimé"
                                if cible.depasse_le and not cible.est_servi
                                else ""
                            ),
                        )
                    # et le concept qui prend la relève est écrit ci-dessous
                if i_llm is not None and importance > i_llm:
                    # Le fait a repris la main sur le jugement : c'est exactement ce que la
                    # règle de sécurité doit produire, et il faut pouvoir le compter sur un run.
                    logger.info(
                        f"[gravite] jugement RELEVÉ par le fait mesuré | "
                        f"person={context.person.person_id} niveau={niveau} "
                        f"I_llm={i_llm:.2f} → I={importance:.2f}"
                    )
                entries.append(
                    MemoryEntry(
                        person_id=context.person.person_id,
                        # Le contenu reste le 5-uplet canonique : la gravité, la valence et les
                        # axes vivent sur les CHAMPS de l'entrée, pas dans son texte. Aucun lecteur
                        # en aval ne change, et un concept écrit avant le lot 1 se relit à
                        # l'identique.
                        content=json.dumps(cinq, ensure_ascii=False),
                        timestamp=start_timestamp,
                        memory_type=MemoryType.CONCEPT,
                        tags=",".join(cinq[1:]),
                        importance=importance,
                        valence=valence,
                        # D2 — un seul saut. Une croyance née de ce que l'agent a ENTENDU
                        # porte sa provenance et ne repartira jamais dans le foyer, même
                        # confirmée plus tard par un trajet (Q2, tranchée le 2026-09-21).
                        origine=origine_concept,
                        # Axes normalisés à l'écriture (lot 2). Le mode vient du modèle, qui sait
                        # de quoi parle son concept ; le lieu de sa portée spatiale ; le motif de
                        # son objet. Le créneau et la météo viennent de la journée consommée : un
                        # concept n'a pas d'heure propre, il a celle de ce qui l'a produit.
                        axe_objet=mode_canonique(mode),
                        axe_lieu=normaliser_lieu(cinq[2] or None),
                        axe_creneau=axes_du_groupe.get("axe_creneau"),
                        axe_motif=normaliser_motif(cinq[4] or None),
                        axe_meteo=axes_du_groupe.get("axe_meteo"),
                    )
                )
            self._compter_operations(
                operations_vues, wall_clock(context.timestamp).date().toordinal()
            )
        except Exception as e:
            logger.exception(f"Failed to parse STM reflection response: {e}")

        for entry in entries:
            if entry.memory_type == MemoryType.CONCEPT:
                # La trace est écrite ICI et non dans le journal : le journal est éteint par
                # défaut et se lit, il ne se mesure pas (son propre en-tête le dit). Faire
                # dépendre la courbe des opérations de son activation rendrait la mesure
                # tributaire d'un réglage de confort.
                tracer_operation(
                    context.person.person_id,
                    "créé",
                    start_timestamp,
                    doc_id=str(getattr(entry, "doc_id", "") or ""),
                )
            if _journal is not None and entry.memory_type == MemoryType.CONCEPT:
                _journal.operation_concept(
                    context.person.person_id,
                    "créé",
                    apres=str(entry.content),
                    note=f"gravité {float(entry.importance or 0.0):.2f}",
                )
            await self.aadd_long_term_memory(context, entry)

        # Ticket 075 — l'état COMPLET de la mémoire après la consolidation, seul moment où il
        # est écrit : c'est le point de comparaison d'une consolidation à la suivante. Il est
        # lu dans les métadonnées de l'agent, jamais reconstruit depuis les entrées du jour.
        if _journal is not None:
            _journal.consolidation_fin(
                context.person.person_id,
                wall_clock(context.timestamp),
                self.long_term_memory.user_metadata.get(
                    context.person.person_id, {}
                ).get("entries", []),
            )
