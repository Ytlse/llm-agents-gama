"""⛔ MODE RAPIDE — ABANDONNÉ le 2026-08-17. NE PAS UTILISER POUR CALIBRER.

════════════════════════════════════════════════════════════════════════════════
LE VÉLO FANTÔME
════════════════════════════════════════════════════════════════════════════════

Ce générateur ne peut pas rejouer la CHAÎNE DE VÉHICULES, et ce n'est pas une
limite cosmétique : c'est ce qui l'a fait abandonner.

En production, un véhicule est là où on l'a laissé. Qui part travailler en bus
laisse son vélo à la maison : le soir, en quittant le bureau, le vélo n'est PAS
une option. `_vehicle_available` le vérifie, et la docstring du code chiffre ce
que le verrou a corrigé — **352 des 1 086 trajets à vélo d'un run de référence,
soit 5,9 points de part modale, reposaient sur un vélo fantôme**.

Ce générateur n'appelle pas le LLM. Or savoir où est le vélo suppose de savoir
quel mode a été choisi au trajet précédent, donc d'avoir interrogé le LLM. C'est
circulaire, et il n'y a pas de contournement : seules les conditions STATIQUES
sont appliquées (possession, permis, âge, passager). Le vélo est donc proposé à
chaque trajet, comme s'il se téléportait.

**Effet mesuré** sur la base `v4` produite ici, jeu `screen` : le prompt B0 met
**34 % de vélo sur les trajets de moins d'un kilomètre** et 34,7 % sur 1-2 km,
contre ~9 % sur les jeux issus d'une simulation. Les jeux d'options sont
irréalistes, et calibrer contre eux produirait un prompt ajusté à cet
irréalisme.

════════════════════════════════════════════════════════════════════════════════
CE QUE ÇA INTERDIT, CE QUE ÇA AUTORISE ENCORE
════════════════════════════════════════════════════════════════════════════════

INTERDIT   — geler un jeu destiné à une campagne de calibration ;
             comparer des parts modales à EMC² sur une base produite ici.
AUTORISÉ   — réchauffer les caches OTP et OSMnx (il calcule exactement les routes
             dont un run aura besoin) ; éprouver le rendu d'une option ; mesurer
             le coût de routage d'une population.

Toute reprise de ce mode pour la calibration exige d'abord de résoudre la chaîne
de véhicules — par exemple en la simulant sous une politique de mode FIXE et
déclarée (« le véhicule rentre toujours au domicile »), ce qui lève la
circularité au prix d'une hypothèse à écrire dans le manifeste.

Voir : docs/tickets/ticket_013_temps_terminal_itineraires.md §9,
       docs/arch/prompt_calibration.md §3.3.
════════════════════════════════════════════════════════════════════════════════

Ce que le générateur fait, pour mémoire
---------------------------------------
Chaque correction de la construction des itinéraires (ticket 013 : temps
terminal) rend caduque la base de prompts sur laquelle la calibration mesure. La
régénérer imposait jusqu'ici un run GAMA de 24 h simulées — des heures d'horloge
et un budget LLM entier — alors que **les options d'itinéraire ne dépendent pas
de ce que le LLM choisit** : OTP et OSMnx les construisent à partir de la
population, des activités et de l'heure de départ, un point c'est tout.

Ce script produit donc les mêmes entrées que le run, en zéro appel LLM, en
rejouant le chemin de production juste avant la décision :

    activités de la population  →  get_itineraries()  →  _select_candidates()
    →  AgentSpec  →  PromptManager.render("itinary_multi_agent")

La sortie a la forme de ``llm_exchanges.jsonl`` : ``calibration.datasets`` la lit
sans modification (``build_decision_records`` ne consomme que
``messages[1]["content"]``), et toute la chaîne aval — jointure population,
tirage météo, découpage, couverture, manifeste — reste celle des jeux ``v1``–``v3``.

Ce que ce mode NE fait pas, et qui reste au run complet
------------------------------------------------------
- **La mémoire.** Aucune section ``**Historique :**``. Les jeux ``val`` et ``test``
  en sont dépouillés par construction (``strip_memory_section``) et le ``train``
  de ``v3`` n'en portait que sur 1 163 records sur 4 286 : une base uniformément
  sans mémoire est donc plus HOMOGÈNE que ``v3``, et alignée sur ce qui mesure.
  Mais toute étude de l'effet de la mémoire exige le run complet.
- **La chaîne de véhicules.** Le verrou de position (« le vélo est là où tu l'as
  laissé ») dépend du mode choisi au trajet précédent, donc du LLM. Ici seules les
  conditions STATIQUES s'appliquent — possession, permis, âge, passager —, avec
  les prédicats de production eux-mêmes (jamais recopiés). Un trajet part donc
  comme si les véhicules étaient au domicile, ce qui est exactement l'état initial
  d'un run. C'est plus permissif qu'un état de milieu de run : quelques options
  véhiculées apparaissent là où un run stateful les aurait écartées. Consigné au
  manifeste.

Reproductibilité — trois points qui ne vont pas de soi
------------------------------------------------------
1. **L'ordre des options est tiré au sort** en production (``random.shuffle``,
   pour éviter le biais de position). Le tirage est ici semé explicitement
   (``--shuffle-seed``) et la graine est écrite au manifeste : sans elle, deux
   générations de la même base ne donneraient pas le même texte.
2. **Le tirage météo aval dépend du RANG de l'entrée** (``draw_key(agent_id,
   entry_idx)``). L'énumération est donc triée (``agent_id``, index d'activité)
   pour que le rang soit stable.
3. **Aucune météo n'est écrite dans les sections.** C'est voulu : la chaîne aval
   la retire de toute façon et la remplace par un tirage dans l'année climatique
   (ticket 008, A7). Le mode rapide n'a donc aucune dépendance à la météo d'un run.

Usage (depuis le conteneur controller, qui a OTP et OSMnx sous la main) :

    docker compose exec controller python /app/scripts/prompt_base/build.py \
        --population /app/experiments/current/population_1000.json \
        --out /app/experiments/bases/2026-08-17/entries.jsonl \
        --day 2026-03-17

puis, côté calibration :

    python -m calibration.datasets --entries <entries.jsonl> \
        --population <population.json> calibration_datasets v4
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

# En conteneur, /app (= llm-agents) et /opt (= llm_module) sont déjà sur le path
# via PYTHONPATH. Hors conteneur, on les ajoute pour pouvoir lancer le script
# depuis la racine du dépôt.
_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT, _REPO_ROOT / "llm-agents"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from helper import humanize_time, to_timestamp_based_on_day  # noqa: E402
from models import Activity, Location, Person  # noqa: E402
from settings import settings  # noqa: E402
from trip_helper.terminal_time import data_version  # noqa: E402

# Prédicats et sélection de production — importés, jamais recopiés : une copie
# divergerait en silence et la base ne décrirait plus ce que le run décrit.
from urban_mobility_agents.factory.factory import init_static_data  # noqa: E402
from urban_mobility_agents.simulation_controller import (  # noqa: E402
    _can_drive, _is_car_passenger, _owns_bike, _owns_car, _select_candidates,
    _vehicle_mode)
from urban_mobility_agents.agents.llm_agent import _build_profile_narrative  # noqa: E402

from llm_module.core.models import AgentSpec  # noqa: E402
from llm_module.prompts.manager import PromptManager  # noqa: E402

CATEGORY = "itinary_multi_agent"


def log(message: str) -> None:
    """Trace de progression, forcément flushée.

    Sans `flush`, Python bufferise stdout hors terminal : un job d'une heure ne
    montre RIEN jusqu'à sa fin, et une supervision qui suit le fichier de log ne
    peut pas distinguer « en cours » de « planté ». Constaté sur le premier essai.
    """
    print(message, flush=True)


def _cache_stats() -> tuple[int, int]:
    """``(hits, lookups)`` du cache persistant OTP depuis le démarrage."""
    from trip_helper.cached_triphelper import get_otp_cache_stats
    return get_otp_cache_stats()


def _osmnx_stats() -> tuple[int, int]:
    """``(hits, lookups)`` du cache persistant OSMnx depuis le démarrage."""
    from trip_helper.osmnx_direct import get_osmnx_cache_stats
    return get_osmnx_cache_stats()


def init_caches(population_path: Path) -> str:
    """Initialise les caches persistants OSMnx et OTP, comme le fait la production.

    Sans cet appel, `_persistent_cache` reste `None` dans `osmnx_direct` et CHAQUE
    route est recalculée à froid — le premier essai a tourné une heure sur trois
    requêtes simultanées sans rien mettre en cache. Pire : le passage ne réchauffait
    aucun cache, alors que réchauffer est un bénéfice GRATUIT de ce mode (il calcule
    exactement les routes dont un run ultérieur aura besoin).

    La convention de répertoire est celle de `handle/application.py` — un
    sous-dossier par population — pour que le cache réchauffé ici soit celui que le
    run lira. La taille est déduite du nom du fichier (`population_1000.json`), qui
    est ce qui nomme le sous-dossier en production.
    """
    from trip_helper.osmnx_direct import init_persistent_cache
    from trip_helper.cached_triphelper import init_otp_persistent_cache

    size = "".join(ch for ch in population_path.stem if ch.isdigit()) or "0"
    population_name = f"{settings.data.synthetic_file_prefix}population_{size}"

    if settings.gtfs.osmnx_cache_enabled:
        init_persistent_cache(str(Path(settings.gtfs.osmnx_persistent_cache_dir)
                                  / population_name))
    if settings.gtfs.otp_cache_enabled:
        init_otp_persistent_cache(str(Path(settings.gtfs.otp_persistent_cache_dir)
                                      / population_name))
    return population_name


# ── Énumération des trajets d'une journée ────────────────────────────────────

class Trip:
    """Un déplacement : de l'activité N vers l'activité N+1."""

    __slots__ = ("person", "index", "origin", "activity", "departure_time")

    def __init__(self, person: Person, index: int, origin: Location,
                 activity: Activity, departure_time: int):
        self.person = person
        self.index = index
        self.origin = origin
        self.activity = activity
        self.departure_time = departure_time


def iter_trips(persons: list[Person], day_ts: int) -> Iterator[Trip]:
    """Déplacements d'une journée, dans un ordre DÉTERMINISTE.

    Le programme d'activités est cyclique : les trajets d'une journée sont les
    paires d'activités consécutives, la dernière bouclant sur la première. Le tri
    par ``agent_id`` puis index est ce qui rend le rang d'entrée stable — dont
    dépend le tirage météo aval.
    """
    for person in sorted(persons, key=lambda p: str(p.person_id)):
        activities = person.identity.activities or []
        if len(activities) < 2:
            continue
        for index, activity in enumerate(activities):
            previous = activities[index - 1]  # boucle : l'index -1 est la dernière
            origin = previous.location or person.identity.home
            if origin is None or activity.location is None:
                continue
            if (abs(origin.lat - activity.location.lat) < 1e-6
                    and abs(origin.lon - activity.location.lon) < 1e-6):
                continue  # pas de déplacement (production : `same_location`)
            target = (activity.scheduled_start_time
                      if activity.scheduled_start_time is not None else activity.end_time)
            yield Trip(person, index, origin, activity,
                       to_timestamp_based_on_day(int(target), day_ts))


def vehicle_flags(person: Person) -> tuple[bool, bool]:
    """``(include_car, include_bike)`` — conditions STATIQUES seulement.

    Reprend les prédicats de production ; ce qui manque volontairement est le
    verrou de position du véhicule, qui dépend du mode choisi au trajet précédent
    (cf. l'en-tête du module).
    """
    traits = person.identity.traits_json
    include_car = _owns_car(traits) and (_can_drive(traits) or _is_car_passenger(person))
    return include_car, _owns_bike(traits)


# ── Rendu d'une entrée ───────────────────────────────────────────────────────

def build_agent_spec(trip: Trip, options: list) -> AgentSpec:
    """``AgentSpec`` identique à celle que produit ``build_travel_plan_payload``.

    ``context`` et ``history`` restent vides : la météo est réinjectée par la
    chaîne aval depuis l'année climatique, et le mode rapide n'a pas de mémoire.
    """
    trajectories = [
        {
            "index": i,
            "mode": opt.mode_label() or "unknown",
            "description": _describe(opt),
            "total_distance_m": (opt.distance if opt.distance is not None
                                 else sum(leg.get_distance() for leg in (opt.legs or []))),
        }
        for i, opt in enumerate(options)
    ]
    dest_zone = (options[0].end_location.zone
                 if options and options[0].end_location else None)
    return AgentSpec(
        agent_id=str(trip.person.person_id),
        perception=f"{_build_profile_narrative(trip.person.identity.traits_json)} "
                   f"Contraintes : None",
        destination=trip.activity.purpose,
        destination_zone=dest_zone,
        departure_time=humanize_time(trip.departure_time),
        departure_timestamp=float(trip.departure_time),
        current_time=humanize_time(trip.departure_time),
        context=None,
        history=[],
        trajectories=trajectories,
    )


def _describe(plan) -> str:
    from text_helper import env_ob_to_text
    return env_ob_to_text("travel_plan", plan.model_dump())


# ── Boucle principale ────────────────────────────────────────────────────────

async def generate(args) -> int:
    log("=" * 78)
    log("⛔ MODE RAPIDE ABANDONNÉ — le vélo fantôme rend cette base INAPTE à la")
    log("   calibration : la chaîne de véhicules n'est pas rejouée, donc le vélo est")
    log("   proposé à chaque trajet (mesuré : 34 % de vélo sous 1 km contre ~9 % sur")
    log("   une base de simulation). Usage légitime restant : réchauffer les caches.")
    log("   Détail : en-tête de ce fichier et ticket 013 §9.")
    log("=" * 78)
    if not args.je_sais_que_cest_abandonne:
        log("Refus : relancer avec --je-sais-que-cest-abandonne pour confirmer.")
        return 2

    payload = json.loads(Path(args.population).read_text(encoding="utf-8"))
    persons = [Person.model_validate(p) for p in payload]
    if args.llm_only:
        persons = [p for p in persons if p.is_llm_based]

    day_ts = int(datetime.strptime(args.day, "%Y-%m-%d").timestamp())
    trips = list(iter_trips(persons, day_ts))
    if args.limit:
        trips = trips[:args.limit]

    population_name = init_caches(Path(args.population))
    log(f"[base] {len(persons)} personas → {len(trips)} déplacements à router "
        f"(jour simulé {args.day}, version des données {data_version()}, "
        f"caches « {population_name} »)")

    # Le helper vient de la FABRIQUE de production, pas d'un assemblage local. En mode
    # OTP elle câble `OtpCachedTripHelper` (décorateur de cache fin qui délègue verbatim
    # sur miss) autour d'`OTPTripHelper` ; `CachedTripHelper`, lui, appartient au mode
    # SOLARI et change la stratégie de recherche — le prendre par erreur faisait échouer
    # 100 % des routages (`max_transfers` inconnu d'`OTPTripHelper`). Reproduire ce choix
    # à la main serait une divergence en attente : on appelle la fabrique.
    helper = init_static_data().trip_helper
    manager = PromptManager()
    rng = random.Random(args.shuffle_seed)
    semaphore = asyncio.Semaphore(args.concurrency)

    stats = Counter()
    modes = Counter()
    results: list[Optional[dict]] = [None] * len(trips)
    t0 = time.monotonic()
    done = 0
    window = [t0]  # horodatage du dernier palier de 100, pour un débit en fenêtre

    # Écriture INCRÉMENTALE : un job d'une heure qui n'écrit qu'à la fin perd tout
    # sur une interruption, et son avancement est invisible depuis le disque. Les
    # entrées sont donc écrites dès qu'elles sont prêtes, sous verrou (l'ordre des
    # lignes suit l'achèvement, pas l'énumération — `results` garde l'ordre canonique
    # pour la réécriture finale, dont dépend le rang d'entrée du tirage météo).
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    partial_path = out.with_suffix(out.suffix + ".partial")
    partial = partial_path.open("w", encoding="utf-8")
    write_lock = asyncio.Lock()

    async def one(slot: int, trip: Trip) -> None:
        nonlocal done
        include_car, include_bike = vehicle_flags(trip.person)
        async with semaphore:
            try:
                options = await helper.get_itineraries(
                    origin=trip.origin, destination=trip.activity.location,
                    departure_time=trip.departure_time,
                    include_car=include_car, include_bike=include_bike,
                    arrive_by=False)
            except Exception as exc:  # noqa: BLE001
                stats["erreur_routage"] += 1
                log(f"[base] ERREUR routage agent={trip.person.person_id} "
                    f"activité={trip.index} : {exc}")
                return
        # Post-filtre de production : OTP/OSMnx rendent parfois un mode non demandé.
        blocked = {m for m, ok in (("bike", include_bike), ("car", include_car)) if not ok}
        if blocked:
            options = [o for o in options if _vehicle_mode(o) not in blocked]
        if not options:
            stats["sans_itineraire"] += 1
            return
        options = _select_candidates(options, settings.gtfs.max_trip_candidates)
        if len(options) < 2:
            # Un seul itinéraire = décision automatique en production, aucun appel
            # LLM, donc aucune décision à mesurer. L'inclure gonflerait la base de
            # records dont la « prédiction » est imposée par l'offre.
            stats["option_unique"] += 1
            return
        for option in options:
            option.purpose = trip.activity.purpose
        rng.shuffle(options)

        spec = build_agent_spec(trip, options)
        messages = manager.render(CATEGORY, [spec], parameters={})
        entry = {
            "time": datetime.now().isoformat(),
            "sim_ts": float(trip.departure_time),
            "sim_day": args.day,
            "task_id": f"direct_{trip.person.person_id}_{trip.index}",
            "provider": "prompt_base_direct",
            "category": CATEGORY,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "response": [],
        }
        results[slot] = entry
        stats["ok"] += 1
        for option in options:
            modes[option.mode_label()] += 1
        async with write_lock:
            partial.write(json.dumps(entry, ensure_ascii=False) + "\n")
            partial.flush()
            done += 1
            if done % 100 == 0:
                # Débit sur la FENÊTRE des 100 dernières entrées, pas la moyenne
                # cumulée : la charge est très hétérogène (un préfixe déjà en cache
                # part à ~100 trajets/s, le reste à froid autour de 0,4) et une
                # moyenne cumulée annoncerait « reste 1 min » pendant deux heures.
                now = time.monotonic()
                window_s = now - window[0]
                window[0] = now
                rate = 100 / max(1e-9, window_s)
                remaining = (len(trips) - done) / rate if rate else 0
                hits, lookups = _cache_stats()
                log(f"[base] {done}/{len(trips)} — {rate:.1f} trajets/s (100 derniers), "
                    f"reste ~{remaining / 60:.0f} min, cache OTP "
                    f"{100 * hits / lookups if lookups else 0:.0f} % "
                    f"[cumulé {done / max(1e-9, now - t0):.1f}/s]")

    await asyncio.gather(*(one(i, t) for i, t in enumerate(trips)))

    # Réécriture dans l'ordre CANONIQUE d'énumération : le tirage météo aval dépend
    # du rang de l'entrée (`draw_key(agent_id, entry_idx)`), donc l'ordre du fichier
    # final fait partie de sa définition — l'ordre d'achèvement des tâches
    # concurrentes, lui, n'est pas reproductible.
    with out.open("w", encoding="utf-8") as f:
        for entry in results:
            if entry is not None:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    partial.close()
    partial_path.unlink(missing_ok=True)

    otp_hits, otp_lookups = _cache_stats()
    manifest = {
        "generator": "direct",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "population": str(args.population),
        "sim_day": args.day,
        "shuffle_seed": args.shuffle_seed,
        "itinerary_data_version": data_version(),
        "max_trip_candidates": settings.gtfs.max_trip_candidates,
        "llm_calls": 0,
        "trips_enumerated": len(trips),
        "entries": stats["ok"],
        "skipped": {k: v for k, v in stats.items() if k != "ok"},
        "options_by_mode": dict(modes.most_common()),
        "memory_section": "aucune — le mode direct ne simule pas la mémoire STM/LTM",
        "vehicle_chain": "non rejoué — conditions statiques seules "
                         "(possession, permis, âge, passager)",
        "weather": "absente des sections — tirée en aval dans l'année climatique",
        # Réchauffage : ce mode calcule EXACTEMENT les routes dont un run ultérieur
        # aura besoin. Le taux de hit dit si la base a été produite à froid (premier
        # passage : ~0 %) ou sur des caches déjà chauds.
        "otp_cache": {"hits": otp_hits, "lookups": otp_lookups,
                      "hit_ratio": round(otp_hits / otp_lookups, 4) if otp_lookups else 0.0},
        "osmnx_cache": dict(zip(("hits", "lookups"), _osmnx_stats())),
    }
    manifest_path = out.with_name(out.stem + "_manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    log(f"[base] {stats['ok']} entrées écrites dans {out}")
    for reason, count in sorted(stats.items()):
        if reason != "ok":
            log(f"[base] écartés — {reason} : {count}")
    log(f"[base] options par mode : {dict(modes.most_common(8))}")
    o_hits, o_lookups = _osmnx_stats()
    log(f"[base] cache OTP {otp_hits}/{otp_lookups} — cache OSMnx {o_hits}/{o_lookups} "
        f"(les manques sont désormais EN cache pour le prochain run)")
    log(f"[base] manifeste : {manifest_path}")
    log(f"[base] appels LLM : 0")

    # Deux sessions HTTP à refermer : celle d'OTP (portée par le helper) et celle,
    # partagée au niveau du module, des réplicas OSMnx en mode HTTP. Les laisser
    # ouvertes ne fausse rien mais noie la sortie sous des « Unclosed client
    # session » qui masqueraient un vrai message.
    from trip_helper import osmnx_direct

    for session in (getattr(helper, "_session", None),
                    getattr(osmnx_direct, "_osmnx_http_session", None)):
        if session is not None and not session.closed:
            await session.close()
    return 0 if stats["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--population", required=True, type=Path,
                        help="population_N.json (traits, domicile, activités)")
    parser.add_argument("--out", required=True, type=Path,
                        help="fichier d'entrées à écrire (forme llm_exchanges.jsonl)")
    parser.add_argument("--day", required=True,
                        help="jour simulé (YYYY-MM-DD) — fixe les heures de départ "
                             "absolues et la congestion routière")
    parser.add_argument("--shuffle-seed", type=int, default=0,
                        help="graine du mélange des options (défaut 0). Consignée au "
                             "manifeste : sans elle la base n'est pas reproductible.")
    parser.add_argument("--concurrency", type=int, default=8,
                        help="requêtes d'itinéraire simultanées (défaut 8)")
    parser.add_argument("--limit", type=int, default=0,
                        help="ne router que les N premiers déplacements (essai à blanc)")
    parser.add_argument("--llm-only", action="store_true", default=True,
                        help="ne garder que les personas pilotés par LLM (défaut)")
    parser.add_argument("--all-personas", dest="llm_only", action="store_false",
                        help="inclure aussi les personas non pilotés par LLM")
    parser.add_argument("--je-sais-que-cest-abandonne", action="store_true",
                        help="confirme avoir lu l'avertissement sur le vélo fantôme "
                             "(cf. en-tête du fichier). Sans ce drapeau, le script "
                             "refuse de tourner : une base produite ici ne doit pas "
                             "servir à calibrer.")
    return asyncio.run(generate(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
