"""Ticket 074, B-9 — un prompt rendu ne contient plus de français, hors noms propres.

Le critère d'acceptation est là-dessus, et il est piégeux : le prompt servi n'est pas un
fichier, c'est un ASSEMBLAGE de huit surfaces indépendantes qui ont toutes bougé.

    prompt système (prompts.yaml)
  + gabarit de catégorie (itinary_multi_agent/template.md.j2)
  + schéma de sortie (output_schema.json)
  + récit de persona (llm_agent._build_profile_narrative)
  + description d'itinéraire (travel_plan_describe_v2.j2)
  + libellés terminaux (config/terminal_time.yaml)
  + bulletin météo (weather_loader)
  + libellés de conditions (data/weather/meteo_toulouse_codes.csv)

Tester chaque morceau séparément ne prouve rien sur l'assemblage : c'est précisément là qu'un
libellé oublié se glisse, et c'est ce qui s'est produit pendant la bascule — les familles de
précipitation rendaient encore « Pluie » au milieu d'une phrase anglaise, sans qu'aucun test de
morceau ne tombe. Ce test-ci monte donc le prompt ENTIER.

Ce qu'il ne fait pas : juger la qualité de l'anglais. Il détecte ce qu'une bascule incomplète
laisse derrière elle — des accents et un vocabulaire français courant — en épargnant les noms
propres, qui restent français dans n'importe quelle langue.

Lancement :
    services/llm-agents/.venv/bin/python -m pytest scripts/tests/test_074_prompt_sans_francais.py -q
"""

from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "services" / "llm-agents"))
sys.path.insert(0, str(RACINE / "packages" / "llm_gateway" / "src"))
sys.path.insert(0, str(RACINE / "packages" / "mobility_llm" / "src"))

ACCENTS = re.compile(r"[àâäéèêëîïôöùûüÿçœæÀÂÄÉÈÊËÎÏÔÖÙÛÜŸÇŒÆ]")

# Mots français fréquents dans les surfaces traduites. Volontairement COURTE et ciblée : une
# liste exhaustive du français attraperait des mots communs aux deux langues (`train`, `bus`,
# `distance`, `option`, `mode`, `persona`) et le test crierait au loup à chaque exécution.
MOTS_FRANCAIS = re.compile(
    r"\b(durée|estimée|trajet|marche|marché|jusqu|météo|pluie|neige|ans|revenu|départ|"
    r"destination\s*:|attente|arrivée|correspondance|gratuit|scolaire|stationnement|"
    r"accès|conduite|vélo|voiture|à pied|aujourd|lever|coucher|rafales|verglas|"
    r"seul\(e\)|famille de|prévue|prévues|dont|nuageux|dégagé|ensoleillé|brouillard|brume)\b",
    re.IGNORECASE,
)


# ── Liste blanche de noms propres ────────────────────────────────────────────────────────


def _noms_propres() -> set[str]:
    """Noms d'arrêts GTFS et de communes du périmètre — ils restent français, c'est normal.

    Construite depuis les SOURCES, jamais écrite à la main : un arrêt renommé dans le GTFS ne
    doit pas faire tomber ce test, et une liste figée le ferait.
    """
    blancs: set[str] = set()
    for feed in ("tisseo_gtfs", "lio_gtfs", "ter_gtfs"):
        stops = RACINE / "data" / "gtfs" / feed / "stops.txt"
        if not stops.is_file():
            continue
        with stops.open(encoding="utf-8-sig", newline="") as f:
            for ligne in csv.DictReader(f):
                blancs.update(_mots(ligne.get("stop_name") or ""))
    communes = (RACINE / "packages" / "mobility_core" / "src" / "mobility_core"
                / "data" / "commune_couronne.json")
    if communes.is_file():
        for c in json.loads(communes.read_text(encoding="utf-8"))["communes"]:
            blancs.update(_mots(c.get("commune") or ""))
    # Les prénoms des personas viennent de la population ; ils sont français par construction.
    blancs.update({"toulouse", "tissÉo", "lio", "ter", "sncf"})
    return blancs


def _mots(texte: str) -> set[str]:
    return {m.lower() for m in re.findall(r"[^\W\d_]+", texte, flags=re.UNICODE) if len(m) > 1}


@pytest.fixture(scope="module")
def blancs() -> set[str]:
    n = _noms_propres()
    assert len(n) > 500, (
        f"liste blanche de noms propres suspecte ({len(n)} mots) : les sources GTFS ou la table "
        "des communes n'ont pas été lues. Sans elle, le test passerait en n'excusant rien — ou "
        "échouerait sur chaque arrêt."
    )
    return n


def _mots_francais_hors_liste(texte: str, blancs: set[str]) -> list[str]:
    trouves = []
    for m in MOTS_FRANCAIS.finditer(texte):
        mot = m.group(0).lower().strip()
        if mot.split()[0] not in blancs:
            trouves.append(texte[max(0, m.start() - 60):m.end() + 40].replace("\n", " ⏎ "))
    return trouves


def _accents_hors_liste(texte: str, blancs: set[str]) -> list[str]:
    trouves = []
    for m in re.finditer(r"[^\W\d_]+", texte, flags=re.UNICODE):
        mot = m.group(0)
        if not ACCENTS.search(mot):
            continue
        if mot.lower() in blancs:
            continue
        # Un mot accentué collé à un nom propre connu (« Baziège » dans « Gare SNCF Baziège »)
        # reste excusé : on regarde le voisinage immédiat.
        voisinage = _mots(texte[max(0, m.start() - 30):m.end() + 30])
        if voisinage & blancs:
            continue
        trouves.append(texte[max(0, m.start() - 60):m.end() + 40].replace("\n", " ⏎ "))
    return trouves


# ── Montage du prompt entier ─────────────────────────────────────────────────────────────


def _reposer_libelles(plan: dict) -> dict:
    """Repose les `step_label` des jambes terminales depuis la configuration VIVANTE.

    Sans cela, ce test échouerait sur « Rejoindre la voiture » et « Conduite » — non parce que
    le code d'aujourd'hui les produit, mais parce qu'ils sont **gelés** dans les plans du jeu
    archivé, écrits sous les libellés français d'avant la bascule.

    C'est exactement le motif du bump `terminal_time.yaml: tt4 → tt5` : `step_label` est
    sérialisé dans le cache OTP et dans les jeux scellés, donc un cache chaud aurait resservi
    ces libellés au jeu v6 au moment de son scellement. Le test vérifie ici ce que produit la
    configuration actuelle ; le bump, lui, est vérifié par
    `test_le_bump_de_version_protege_les_plans_en_cache`.
    """
    from trip_helper.terminal_time import terminal_profile

    mode = next((l.get("mode") for l in plan["legs"]
                 if l.get("mode") and terminal_profile(str(l["mode"]))), None)
    profil = terminal_profile(str(mode)) if mode else None
    if profil is None:
        return plan
    plan = dict(plan)
    plan["legs"] = [dict(l) for l in plan["legs"]]
    terminales = [l for l in plan["legs"] if l.get("step_label")]
    for i, leg in enumerate(terminales):
        if leg.get("mode") == mode:
            leg["step_label"] = profil.labels["main"]
        elif i == 0:
            leg["step_label"] = profil.labels["access"]
        else:
            leg["step_label"] = profil.labels["egress"]
    return plan


@pytest.fixture(scope="module")
def prompt_rendu() -> str:
    """Le prompt COMPLET — système + gabarit + options décrites + persona + météo.

    Les plans d'options viennent de l'archive froide, en LECTURE SEULE et par dérogation
    motivée : ce sont de vrais itinéraires (marche directe, voiture à jambes terminales,
    chaîne de transports collectifs avec correspondance), et un plan fabriqué à la main ne
    ferait jamais passer le gabarit par ses quatre branches.
    """
    from mobility_llm.persona import AgentSpec
    from mobility_llm.prompts import CATEGORIES_DIR, PROMPTS_FILE
    from models import TravelPlan
    from text_helper import env_ob_to_text
    from urban_mobility_agents.agents.llm_agent import _build_profile_narrative
    from urban_mobility_agents.utils import weather_loader

    from llm_gateway.prompts.engine import AvisNeutraliteManquant, PromptManager

    propositions = (RACINE / "archive" / "2026-09-14_avant_bascule_anglaise" / "plateforme"
                    / "jeux" / "population_1000_AAMAS_v5_20260316" / "propositions.jsonl")
    if not propositions.is_file():
        pytest.skip(f"plans de référence absents ({propositions}) — archive froide déplacée ?")

    # Un plan par branche du gabarit : direct, à jambes terminales, multi-jambes TC.
    from text_helper.models.travel_plan import TravelPlanWrapper
    par_branche: dict[str, dict] = {}

    with propositions.open(encoding="utf-8") as f:
        for i, ligne in enumerate(f):
            if i > 3000 or len(par_branche) >= 3:
                break
            d = json.loads(ligne)
            for p in d["propositions"]:
                brut = dict(p["plan"])
                brut["purpose"] = brut.get("purpose") or d["purpose"]
                w = TravelPlanWrapper(**brut)
                cle = ("terminal" if w.has_terminal_legs
                       else "direct" if len(w.legs) <= 1 else "transit")
                par_branche.setdefault(cle, _reposer_libelles(brut))
    assert len(par_branche) == 3, f"branches couvertes : {sorted(par_branche)}"

    trajectoires = [
        {"index": i,
         "mode": TravelPlan.model_validate(brut).mode_label() or "unknown",
         "description": env_ob_to_text("travel_plan", brut),
         "total_distance_m": brut.get("distance") or 0.0}
        for i, brut in enumerate(par_branche.values())
    ]

    weather_loader._load()
    bulletin = weather_loader.weather_to_natural_language({
        "temperature": 2, "weather_label": weather_loader._code_labels[296],
        "precip_mm": 0.2, "temp_min": -1, "temp_max": 7,
        "sunrise": "07:55", "sunset": "17:25",
        "precip_slots": [("morning", "rain"), ("evening", "snow")], "wind_max_kmh": 95,
    })

    traits = {"name": "Thibault Marty", "age": 58, "main_occupation": "Travail à plein temps",
              "professional_activity": "Full-Time Worker", "household_size": 4,
              "income": "Medium-High"}

    agent = AgentSpec(
        agent_id="2348",
        perception=_build_profile_narrative(traits),
        destination="work",
        # ⚠ `destination_zone` est nul dans le chemin sans simulateur (vérifié sur 1 662 plans
        # du jeu v5), mais PAS forcément dans le chemin GAMA, où la zone de l'activité est
        # une phrase française de la population. On l'injecte donc exprès : c'est le seul
        # endroit où ce canal est éprouvé.
        destination_zone="dense urban neighbourhood",
        departure_time="06:48",
        context=bulletin,
        day_outlook=weather_loader.day_weather_outlook(1773737984) or "afternoon 12°C, Clear/Sunny",
        agenda=["18:10 → home"],
        trajectories=trajectoires,
    )

    pm = PromptManager(
        templates_dir=CATEGORIES_DIR,
        prompts_file=PROMPTS_FILE,
        template_names={"itinary_multi_agent": "itinary_multi_agent/template.md.j2"},
        schema_paths={"itinary_multi_agent": CATEGORIES_DIR / "itinary_multi_agent"
                      / "output_schema.json"},
    )
    try:
        messages = pm.render("itinary_multi_agent", [agent], {"prompt_variant": "expert_m4"})
    except AvisNeutraliteManquant as e:
        # On passe DÉLIBÉRÉMENT par le chemin de SERVICE, pas par une lecture de complaisance :
        # ce qu'il faut vérifier est le texte réellement envoyé au modèle. Un sceau périmé
        # empêche ce texte d'exister — ce n'est pas une raison de sauter le test avec un
        # `skip` (l'absence de mesure passerait pour un succès), c'est un échec à part entière,
        # et le message doit dire lequel plutôt que de laisser lire une régression de langue.
        pytest.fail(
            "le prompt n'est pas SERVABLE, donc son texte n'existe pas et rien n'a été "
            f"vérifié :\n  {e}\n"
            "→ B-8 : faire réexaminer les variantes traduites par l'agent `prompt-auditor`, "
            "puis réécrire `_neutralite` (verdict, date, sha256_texte) avant de relancer."
        )
    return "\n".join(m.content for m in messages)


# ── Les contrôles ────────────────────────────────────────────────────────────────────────


def test_le_montage_couvre_bien_les_surfaces(prompt_rendu: str) -> None:
    """Garde-fou du test lui-même : un prompt amputé passerait tous les contrôles suivants.

    C'est le motif « l'absence de mesure produit le score parfait » : si le gabarit rendait
    une page vide, il n'y aurait aucun mot français dedans.
    """
    for attendu, surface in (
        ("Thibault", "récit de persona"),
        ("Weather:", "bulletin météo"),
        ("Travel time:", "description d'itinéraire multi-jambes"),
        ("of access and parking", "libellés terminaux de terminal_time.yaml"),
        ("Trip options", "gabarit de catégorie"),
        ("Strict filtering", "prompt système"),
        ("dense urban neighbourhood", "destination_zone"),
        ('"agent_id"', "schéma de sortie"),
    ):
        assert attendu in prompt_rendu, f"surface absente du montage : {surface} ({attendu!r})"
    assert len(prompt_rendu) > 2500, "prompt suspicieusement court"


def test_aucun_caractere_accentue_hors_noms_propres(prompt_rendu: str, blancs: set[str]) -> None:
    restes = _accents_hors_liste(prompt_rendu, blancs)
    assert not restes, (
        f"{len(restes)} passage(s) accentué(s) hors noms propres :\n  - "
        + "\n  - ".join(restes[:12])
    )


def test_aucun_mot_francais_courant_hors_noms_propres(prompt_rendu: str,
                                                      blancs: set[str]) -> None:
    restes = _mots_francais_hors_liste(prompt_rendu, blancs)
    assert not restes, (
        f"{len(restes)} passage(s) en français :\n  - " + "\n  - ".join(restes[:12])
    )


def test_les_noms_propres_sont_bien_preserves(prompt_rendu: str) -> None:
    """L'envers du test : la bascule ne doit pas avoir angliciser un nom d'arrêt ou de commune.

    Sans ce contrôle, « traduire » `Gare SNCF Baziège` en `Baziege railway station` passerait
    les deux tests précédents avec les félicitations du jury.
    """
    noms = [m for m in re.findall(r"'([^']{3,60})'", prompt_rendu)]
    assert noms, "aucun nom propre entre apostrophes dans le prompt — montage à revoir"
    connus = _noms_propres()
    reconnus = [n for n in noms if _mots(n) & connus]
    assert reconnus, (
        f"aucun des noms cités n'est reconnu comme arrêt ou commune du périmètre : {noms[:10]}"
    )


def test_les_etiquettes_de_mode_restent_intactes(prompt_rendu: str) -> None:
    """Les étiquettes de mode sont relues DANS le texte du prompt par `parse_option_modes`.

    Elles étaient déjà anglaises ; la bascule ne devait pas y toucher. Le contrôle ne porte
    pas sur la langue mais sur l'identité des étiquettes servies.
    """
    from mobility_llm.mode_choice import canonical_mode

    etiquettes = re.findall(r"^- \[\d+\] ([^:]+):", prompt_rendu, flags=re.M)
    assert etiquettes, "aucune ligne d'option « - [n] mode: » dans le prompt"
    for e in etiquettes:
        assert not ACCENTS.search(e), f"étiquette de mode accentuée : {e!r}"
        famille = canonical_mode(e)
        assert famille and famille != "unknown", (
            f"étiquette de mode non catégorisable : {e!r} → {famille!r}. `parse_option_modes` "
            "relit ces étiquettes DANS le texte du prompt ; les traduire casserait "
            "`canonical_mode`, la loss de calibration et les parts modales de moves.csv."
        )


def test_les_libelles_meteo_servis_sont_anglais() -> None:
    """Les 48 conditions servies viennent de `Condition_EN`, pas de `Condition`.

    Contrôle séparé du montage : une seule condition est rendue dans un prompt donné, et
    c'est la table ENTIÈRE qui doit être basculée.
    """
    from urban_mobility_agents.utils import weather_loader

    weather_loader._load()
    assert weather_loader._code_labels, "table des conditions vide"
    fautifs = {c: l for c, l in weather_loader._code_labels.items() if ACCENTS.search(l)}
    assert not fautifs, f"conditions météo encore françaises : {fautifs}"


def test_les_familles_de_precipitation_reconnaissent_les_libelles_anglais() -> None:
    """Le piège de la bascule : des expressions restées françaises ne reconnaissent plus rien.

    `_SNOW_RE` / `_RAIN_RE` sont le SEUL lien entre la table des conditions et la phrase de
    précipitation. Restées françaises, elles n'auraient plus rien détecté : `precip_slots`
    toujours vide, et « No precipitation expected. » affirmé tous les jours de l'année, y
    compris sous l'orage. Aucune exception, aucun log — une affirmation fausse, pas un trou.
    """
    from urban_mobility_agents.utils import weather_loader

    weather_loader._load()
    attendu = {296: "rain", 326: "snow", 113: None, 248: None, 350: "snow", 200: "rain"}
    for code, famille in attendu.items():
        libelle = weather_loader._code_labels[code]
        assert weather_loader._precip_family(libelle) == famille, (
            f"code {code} ({libelle!r}) → {weather_loader._precip_family(libelle)!r}, "
            f"attendu {famille!r}"
        )
    # Et globalement : la table ne doit pas être devenue muette.
    familles = {weather_loader._precip_family(l) for l in weather_loader._code_labels.values()}
    assert familles == {"rain", "snow", None}, f"familles produites : {familles}"


def test_le_bump_de_version_protege_les_plans_en_cache() -> None:
    """`terminal_time.yaml` a bien changé de version, et seulement celle qu'il fallait.

    Les libellés terminaux sont sérialisés dans `Transit.step_label`, et le cache OTP mémorise
    les `TravelPlan` complets : sans bump de `data_version`, un cache chaud aurait resservi des
    plans portant « Rejoindre la voiture » au jeu v6, au moment de son scellement, sans qu'aucun
    log ne le signale. C'est vérifiable sur pièce — les plans du jeu v5 archivé les portent.

    `routing_version` ne devait PAS bouger : le cache de routage OSMnx ne mémorise que du temps
    réseau, qu'aucun libellé ne touche. Le bumper aurait coûté ~2 h de recalcul pour rien.
    """
    from trip_helper.terminal_time import data_version, routing_version, terminal_profile

    assert data_version() != "tt4", (
        "data_version est restée à tt4 alors que les libellés terminaux ont été traduits : "
        "le cache OTP resservira des plans à sous-étapes françaises"
    )
    assert routing_version() == "r3", (
        "routing_version a bougé sans nécessité : le cache de routage OSMnx sera recalculé à "
        "froid (~2 h) alors qu'aucune durée réseau n'a changé"
    )
    for mode in ("car", "bicycle"):
        profil = terminal_profile(mode)
        for cle in ("access", "main", "egress", "egress_sans_destination", "terminal"):
            libelle = profil.labels[cle]
            assert not ACCENTS.search(libelle), (
                f"libellé terminal encore français : {mode}.{cle} = {libelle!r}"
            )


def _jour_a_meteo_variable() -> int:
    """Un horodatage tombant sur une journée dont la météo CHANGE au fil des créneaux.

    Le jour du jeu scellé (2026-03-16) est « Clear/Sunny » du matin au soir : sur lui, la
    branche météo de `_agenda_lines` ne se déclenche jamais et le contrôle linguistique porte
    sur rien. La journée est donc choisie dans les données — 228 des 365 jours portent au moins
    trois libellés distincts — plutôt que figée au hasard.
    """
    import calendar
    from datetime import datetime, timezone

    from urban_mobility_agents.utils import weather_loader as W

    W._load()
    for (mois, jour), ligne in sorted(W._weather_index.items()):
        libelles = set()
        for col in W._FINE_CODE_COLS.values():
            try:
                libelles.add(W._code_labels[int(float(ligne[col]))])
            except (KeyError, ValueError, TypeError):
                continue
        if len(libelles) >= 3:
            return calendar.timegm(
                datetime(2026, mois, jour, 6, 0, tzinfo=timezone.utc).timetuple()
            )
    raise AssertionError("aucune journée à météo variable dans data/weather — test inopérant")


def test_l_agenda_d_anticipation_est_anglais() -> None:
    """La NEUVIÈME surface — `_agenda_lines`, absente de l'inventaire du ticket.

    Cette ligne d'agenda (« 18:10 → home (≈4,2 km) — light rain expected ») part dans le prompt
    via `agent.agenda`, et sa `signature` entre dans la clé du cache de décisions. Elle n'est
    rendue que pour les agents ayant un véhicule à chaîner ET quand la météo prévue diffère de
    celle du départ : assez rare pour qu'un échantillon la manque, assez fréquente pour qu'elle
    parte en production. Elle a effectivement été manquée au premier passage du lot B, parce que
    la fixture du prompt fournissait une ligne d'agenda ÉCRITE À LA MAIN — un montage qui teste
    le gabarit, jamais le producteur.

    Ce test exerce donc le vrai producteur, sur des personas réels, et **refuse de passer sans
    avoir vu la branche météo** : sans cette exigence, il rendrait vert le jour où la branche
    cesse d'être atteinte, ce qui est le motif « l'absence de mesure produit le score parfait ».
    """
    from experiences.population import charger_population
    from urban_mobility_agents.simulation_controller import _agenda_lines

    cohorte = (RACINE / "archive" / "2026-09-14_avant_bascule_anglaise" / "population"
               / "population_1000_AAMAS_v5")
    if not (cohorte / "population.json").is_file():
        pytest.skip(f"cohorte de référence absente ({cohorte})")

    personnes, _ = charger_population(
        cohorte,
        archivee_confirmee=(
            "ticket 074 B-9 : contrôle linguistique de l'agenda d'anticipation sur des personas "
            "réels — lecture seule, aucune mesure produite"
        ),
    )
    # ⚠ Un VRAI horodatage, pas une heure 24h. `_agenda_lines` appelle `get_weather`, qui lit
    # l'heure murale : lui passer `acte.end_time` (0..86400) situe tout en 1970, tous les
    # créneaux tombent au même endroit, et la branche météo ne se déclenche JAMAIS. Le test
    # passerait alors en n'ayant rien exercé — c'est ce qu'il a refusé de faire au premier jet.
    from helper import to_timestamp_based_on_day

    jour = _jour_a_meteo_variable()

    lignes: list[str] = []
    avec_meteo = 0
    for personne in personnes:
        actes = personne.identity.activities or []
        for i, acte in enumerate(actes[:-1]):
            brut = acte.end_time
            if brut is None:
                continue
            depart = to_timestamp_based_on_day(int(brut), jour)
            produites = _agenda_lines(personne, actes[i + 1], depart)
            lignes.extend(produites)
            avec_meteo += sum(1 for l in produites if " — " in l)
        if len(lignes) > 4000:
            break

    assert lignes, "aucune ligne d'agenda produite — le test ne mesure rien"
    assert avec_meteo > 0, (
        f"{len(lignes)} lignes d'agenda produites, AUCUNE ne porte le suffixe météo « — … » : "
        "la branche qui portait le français n'a pas été exercée, donc rien n'a été vérifié"
    )
    blancs = _noms_propres()
    fautives = [l for l in lignes if _accents_hors_liste(l, blancs)
                or _mots_francais_hors_liste(l, blancs)]
    assert not fautives, (
        f"{len(fautives)} ligne(s) d'agenda en français sur {len(lignes)} "
        f"({avec_meteo} avec suffixe météo) :\n  - " + "\n  - ".join(fautives[:8])
    )
