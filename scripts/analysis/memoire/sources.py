"""Lecture des fichiers d'un run de mémoire.

Ce module ne mesure rien : il rend des structures propres et **triées**, pour que
le rapport soit reproductible octet pour octet (contrat F7).

Trois pièges du format, traités ici une fois pour toutes :

1. ``llm_exchanges.jsonl`` n'est **pas** du JSONL malgré l'extension : ce sont des
   objets JSON indentés concaténés. On le lit avec ``json.JSONDecoder.raw_decode``
   en boucle (contrat F2).
2. ``moves.csv`` contient des **trajets rejoués** après redémarrage : la même
   décision (même personne, même activité, même instant simulé) y figure deux
   fois. On garde la première par heure de calcul et on compte les autres
   (contrat F1).
3. Les options d'itinéraire proposées à l'agent **n'existent que dans le texte des
   prompts**. On les en extrait ; l'appariement, lui, vit dans :mod:`mesures`.
"""
from __future__ import annotations

import csv
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Vocabulaire des modes ─────────────────────────────────────────────────────
# Palette officielle du dépôt (`.claude/CLAUDE.md`) : voiture rouge, vélo violet,
# transports collectifs vert, marche cyan, train violet, deux-roues magenta.
MODE_COULEURS: dict[str, str] = {
    "car": "#EE4444",
    "cycling": "#8844BB",
    "public_transport": "#22AA44",
    "walking": "#00CCCC",
    "train": "#8844BB",
    "motorbike": "magenta",
    "autres": "#9AA0A6",
}

MODE_LIBELLES: dict[str, str] = {
    "car": "Voiture",
    "cycling": "Vélo",
    "public_transport": "Transports collectifs",
    "walking": "Marche",
    "train": "Train",
    "motorbike": "Deux-roues motorisé",
    "autres": "Autres modes",
}

# Ordre d'affichage stable, indépendant des données.
MODES = ["car", "public_transport", "walking", "cycling", "train", "motorbike", "autres"]

# Étiquettes françaises de `moves.csv` → modes canoniques.
_MODE_DEPUIS_MOVES = {
    "Voiture Privée": "car",
    "Vélo": "cycling",
    "Transports_collectifs": "public_transport",
    "Marche": "walking",
    "Train": "train",
    "Deux-roues motorisé": "motorbike",
    "Autres modes": "autres",
}

# Colonnes de probabilité de `moves.csv` → modes canoniques.
COLONNES_PROBA = {
    "P(Marche) %": "walking",
    "P(Vélo) %": "cycling",
    "P(Voiture Privée) %": "car",
    "P(Transports_collectifs) %": "public_transport",
    "P(Train) %": "train",
    "P(Deux-roues motorisé) %": "motorbike",
    "P(Autres modes) %": "autres",
}

# Motifs : `moves.csv` mêle français et anglais, les prompts sont en anglais.
_MOTIF_CANON = {
    "travail": "work",
    "work": "work",
    "etude": "education",
    "étude": "education",
    "education": "education",
    "achats": "shop",
    "shop": "shop",
    "shopping": "shop",
    "loisir": "leisure",
    "loisirs": "leisure",
    "leisure": "leisure",
    "home": "home",
    "domicile": "home",
    "escort": "escort",
    "accompagnement": "escort",
}

MOTIF_LIBELLES = {
    "work": "Travail",
    "education": "Études",
    "shop": "Achats",
    "leisure": "Loisirs",
    "home": "Retour au domicile",
    "escort": "Accompagnement",
}

# Étiquettes de jambes rencontrées dans les options de prompt → mode canonique.
# Le premier mot reconnu dans l'ordre ci-dessous l'emporte : un « foot,bus,foot »
# est un trajet en transport collectif, pas une marche.
_JAMBES_PRIORITAIRES = [
    (("rail", "train"), "train"),
    (("bus", "metro", "tram", "subway", "school_bus", "ferry", "trolleybus"), "public_transport"),
    (("car", "car_park", "taxi"), "car"),
    (("motorbike", "moped", "scooter"), "motorbike"),
    (("bicycle", "bike", "cycling"), "cycling"),
    (("foot", "walk", "walking"), "walking"),
]

_UNITES_DUREE = {
    "second": 1, "seconds": 1,
    "minute": 60, "minutes": 60,
    "hour": 3600, "hours": 3600,
    "day": 86400, "days": 86400,
}


def mode_canonique_depuis_moves(libelle: str) -> str | None:
    """Étiquette française de `moves.csv` → mode canonique. Hors vocabulaire : ``None``."""
    return _MODE_DEPUIS_MOVES.get((libelle or "").strip())


def mode_canonique_depuis_option(mode_option: str) -> str | None:
    """Suite de jambes d'une option de prompt (« foot,bus,foot ») → mode canonique.

    Un mot hors des deux vocabulaires reste ``None`` : on ne devine pas, on déclare.
    """
    jambes = [j.strip().lower() for j in (mode_option or "").split(",") if j.strip()]
    if not jambes:
        return None
    for mots, canon in _JAMBES_PRIORITAIRES:
        if any(j in mots for j in jambes):
            return canon
    return None


def motif_canonique(libelle: str) -> str:
    """Motif de déplacement, ramené au vocabulaire anglais des prompts."""
    brut = (libelle or "").strip()
    return _MOTIF_CANON.get(brut.lower(), brut.lower() or "inconnu")


def libelle_motif(motif: str) -> str:
    return MOTIF_LIBELLES.get(motif, motif or "inconnu")


def duree_en_secondes(texte: str) -> int | None:
    """« 1 hour, 56 minutes » → 6960. ``None`` si aucune durée n'est lisible."""
    couples = re.findall(
        r"(\d+)\s+(seconds?|minutes?|hours?|days?)", texte or "", flags=re.IGNORECASE)
    if not couples:
        return None
    return sum(int(n) * _UNITES_DUREE[u.lower()] for n, u in couples)


# ── Structures ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Trajet:
    person_id: str
    activity_id: str
    trajet_id: str
    mode: str | None
    modes_proposes: tuple[str, ...]
    probabilites: dict[str, float]
    motif: str
    methode: str
    jour: str                 # « AAAA-MM-JJ » du départ simulé
    depart: str               # « HH:MM:SS »
    depart_minutes: int | None
    heure_calcul: str
    sim_ts: str
    distance_km: float | None
    temperature: float | None
    meteo: str
    raisonnement: str
    fournisseur: str
    # Ticket 093 — nombre d'options RÉELLEMENT présentées. Sans lui, « voiture 100 % » ne
    # distingue pas un choix d'une absence d'alternative, et une décision qui n'en était pas
    # se compte comme une décision. `None` quand la colonne est absente ou vide : un trajet
    # dont on ignore le nombre d'options ne prouve pas qu'il y avait un choix, et il ne prouve
    # pas non plus le contraire — le zéro serait un mensonge dans un sens comme dans l'autre.
    options_presentees: int | None = None

    @property
    def depart_complet(self) -> str:
        """« AAAA-MM-JJ HH:MM:SS » — l'instant de départ, jour et heure réunis."""
        return f"{self.jour} {self.depart}".strip()


@dataclass(frozen=True)
class Option:
    index: int
    mode_brut: str
    mode: str | None
    description: str
    etapes: tuple[str, ...]

    @property
    def identite(self) -> tuple[str, tuple[str, ...]]:
        """Identité d'un itinéraire : son mode et la suite de ses étapes."""
        return (self.mode_brut, self.etapes)


@dataclass(frozen=True)
class BlocPrompt:
    agent: str
    jour: str
    motif: str
    depart_minutes: int | None
    options: tuple[Option, ...]
    a_historique: bool
    taille_historique: int


@dataclass(frozen=True)
class EntreeLTM:
    person_id: str
    doc_id: str
    contenu: str
    enonce: str
    memory_type: str
    timestamp: str
    importance: float
    valence: str
    axe_objet: str | None
    axe_motif: str | None
    axe_lieu: str | None
    axe_creneau: str | None
    axe_meteo: str | None
    force: float
    rappels: int
    dernier_rappel: str | None
    observations: int
    contre_exemples: int


@dataclass
class Journal:
    """Ce que le journal lisible `memoires/<id>.md` raconte."""
    person_id: str
    consolidations: int = 0
    declencheurs: dict[str, int] = field(default_factory=dict)
    operations: dict[str, int] = field(default_factory=dict)
    rappels: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)


@dataclass
class Run:
    chemin: Path
    trajets: list[Trajet]
    rejeu: int
    rejeu_detail: list[tuple[str, str, str]]
    arrivees: list[dict[str, Any]]
    evenements: list[dict[str, Any]]
    echanges: list[dict[str, Any]]
    blocs: list[BlocPrompt]
    ltm: dict[str, list[EntreeLTM]]
    habitudes: dict[str, dict[str, Any]]
    journaux: dict[str, Journal]
    personas: dict[str, dict[str, Any]]
    autoreflexions: dict[str, list[tuple[str, str]]]

    @property
    def jours(self) -> list[str]:
        return sorted({t.jour for t in self.trajets})

    @property
    def agents(self) -> list[str]:
        """Identifiants d'agents, triés numériquement quand c'est possible."""
        ids = set(self.personas) | {t.person_id for t in self.trajets} | set(self.ltm)
        return sorted(ids, key=_cle_agent)

    @property
    def fournisseurs(self) -> list[str]:
        return sorted({str(e.get("provider") or "") for e in self.echanges if e.get("provider")})


def _cle_agent(identifiant: str) -> tuple[int, Any]:
    return (0, int(identifiant)) if identifiant.isdigit() else (1, identifiant)


# ── moves.csv ─────────────────────────────────────────────────────────────────

def _flottant(valeur: Any) -> float | None:
    try:
        return float(str(valeur).replace(",", "."))
    except (TypeError, ValueError):
        return None


def lire_moves(chemin_run: Path) -> tuple[list[Trajet], int, list[tuple[str, str, str]]]:
    """Trajets du run, **rejeu exclu** (contrat F1).

    Clé de décision : ``(ID Personne, ID Activité, Temps simulé)`` — l'identifiant
    d'activité seul se répète d'un jour sur l'autre (même emploi du temps), et
    l'instant simulé distingue deux trajets réels d'un même motif dans la journée.
    Après un redémarrage, la même décision est recalculée : deux lignes, deux
    heures de calcul. On garde la **première par heure de calcul** ; les autres
    sont du rejeu, comptées et déclarées.
    """
    fichier = Path(chemin_run) / "moves.csv"
    if not fichier.is_file():
        return [], 0, []
    with fichier.open(newline="", encoding="utf-8") as flux:
        lignes = list(csv.DictReader(flux))

    groupes: dict[tuple[str, str, str], list[tuple[int, dict[str, str]]]] = {}
    for rang, ligne in enumerate(lignes):
        instant = (ligne.get("Temps simulé") or "").strip()
        if not instant:
            # Repli si la colonne manque : le jour du départ simulé.
            instant = (ligne.get("Heure de départ") or "")[:10]
        cle = ((ligne.get("ID Personne") or "").strip(),
               (ligne.get("ID Activité") or "").strip(),
               instant)
        groupes.setdefault(cle, []).append((rang, ligne))

    trajets: list[Trajet] = []
    rejeu = 0
    rejeu_detail: list[tuple[str, str, str]] = []
    for cle in sorted(groupes):
        membres = sorted(groupes[cle],
                         key=lambda item: ((item[1].get("Heure de calcul") or ""), item[0]))
        garde = membres[0][1]
        for _, exclu in membres[1:]:
            rejeu += 1
            rejeu_detail.append((cle[0], (exclu.get("Heure de départ") or "")[:10],
                                 exclu.get("Heure de calcul") or ""))
        trajets.append(_trajet_depuis_ligne(garde))

    trajets.sort(key=lambda t: (_cle_agent(t.person_id), t.jour, t.depart, t.trajet_id))
    rejeu_detail.sort()
    return trajets, rejeu, rejeu_detail


def _trajet_depuis_ligne(ligne: dict[str, str]) -> Trajet:
    depart = (ligne.get("Heure de départ") or "").strip()
    jour, _, heure = depart.partition(" ")
    depart_minutes = None
    if len(heure) >= 5 and heure[:2].isdigit() and heure[3:5].isdigit():
        depart_minutes = int(heure[:2]) * 60 + int(heure[3:5])
    probabilites = {}
    for colonne, mode in COLONNES_PROBA.items():
        valeur = _flottant(ligne.get(colonne))
        if valeur:
            probabilites[mode] = valeur
    proposes = tuple(
        m for m in (
            mode_canonique_depuis_moves(x) or x.strip()
            for x in (ligne.get("Modes proposés au LLM") or "").split("|")
        ) if m
    )
    return Trajet(
        person_id=(ligne.get("ID Personne") or "").strip(),
        activity_id=(ligne.get("ID Activité") or "").strip(),
        trajet_id=(ligne.get("ID Trajet") or "").strip(),
        mode=mode_canonique_depuis_moves(ligne.get("Mode de transport Choisi", "")),
        modes_proposes=proposes,
        probabilites=probabilites,
        motif=motif_canonique(ligne.get("Motifs de déplacement", "")),
        methode=(ligne.get("Méthode de sélection") or "").strip(),
        jour=jour,
        depart=heure,
        depart_minutes=depart_minutes,
        heure_calcul=(ligne.get("Heure de calcul") or "").strip(),
        sim_ts=(ligne.get("Temps simulé") or "").strip(),
        distance_km=_flottant(ligne.get("Distance parcourue")),
        temperature=_flottant(ligne.get("Météo Température (°C)")),
        meteo=(ligne.get("Météo Condition") or "").strip(),
        raisonnement=(ligne.get("Raisonnement") or "").strip(),
        fournisseur=(ligne.get("Fournisseur & Modèle") or "").strip(),
        options_presentees=_entier(ligne.get("Options présentées")),
    )


def _entier(valeur: Any) -> int | None:
    try:
        return int(str(valeur).strip())
    except (TypeError, ValueError):
        return None


# ── gama_arrivals.csv ─────────────────────────────────────────────────────────

def lire_arrivees(chemin_run: Path) -> list[dict[str, Any]]:
    fichier = Path(chemin_run) / "gama_results" / "gama_arrivals.csv"
    if not fichier.is_file():
        return []
    with fichier.open(newline="", encoding="utf-8") as flux:
        lignes = list(csv.DictReader(flux))
    arrivees = []
    for ligne in lignes:
        debut, fin = ligne.get("started_at", ""), ligne.get("arrive_at", "")
        if not str(debut).strip().lstrip("-").isdigit() or not str(fin).strip().lstrip("-").isdigit():
            continue
        arrivees.append({
            "move_id": ligne.get("move_id", ""),
            "person_id": (ligne.get("person_id") or "").strip(),
            "started_at": int(debut),
            "arrive_at": int(fin),
            "delay_s": int(_flottant(ligne.get("delay_s")) or 0),
            "departure_delay_s": int(_flottant(ligne.get("departure_delay_s")) or 0),
            "timed_out": str(ligne.get("timed_out", "")).strip().lower() == "true",
        })
    arrivees.sort(key=lambda a: (a["person_id"], a["started_at"], a["move_id"]))
    return arrivees


# ── agent_memory_events.jsonl ────────────────────────────────────────────────

def lire_evenements(chemin_run: Path) -> list[dict[str, Any]]:
    """Vrai JSONL, lui. Une ligne illisible est ignorée, jamais fatale."""
    fichier = Path(chemin_run) / "agent_memory_events.jsonl"
    if not fichier.is_file():
        return []
    evenements = []
    with fichier.open(encoding="utf-8") as flux:
        for ligne in flux:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                evenements.append(json.loads(ligne))
            except json.JSONDecodeError:
                continue
    evenements.sort(key=lambda e: (str(e.get("person_id", "")), int(e.get("timestamp") or 0),
                                   str(e.get("message", ""))[:80]))
    return evenements


# ── llm_exchanges.jsonl (JSON concaténé, PAS du JSONL) ───────────────────────

def lire_echanges(chemin_run: Path) -> list[dict[str, Any]]:
    """Objets JSON indentés concaténés (contrat F2).

    L'extension ment : une lecture ligne à ligne échoue dès le premier objet.
    On décode en boucle avec ``raw_decode``, en sautant les blancs entre objets.
    """
    fichier = Path(chemin_run) / "llm_exchanges.jsonl"
    if not fichier.is_file():
        return []
    # Le worker écrit ce journal pour TOUS ses clients : seuls les échanges signés par ce run
    # (ou non signés, antérieurs au 2026-09-24) lui appartiennent.
    nom_run = Path(chemin_run).resolve().name
    return [
        o for o in decoder_json_concatene(fichier.read_text(encoding="utf-8"))
        if o.get("origine") in (None, nom_run)
    ]


def decoder_json_concatene(texte: str) -> list[dict[str, Any]]:
    decodeur = json.JSONDecoder()
    objets: list[dict[str, Any]] = []
    position, longueur = 0, len(texte)
    while position < longueur:
        while position < longueur and texte[position] in " \t\r\n":
            position += 1
        if position >= longueur:
            break
        try:
            objet, position = decodeur.raw_decode(texte, position)
        except json.JSONDecodeError:
            # Objet tronqué en fin de fichier (run interrompu) : on s'arrête là.
            break
        if isinstance(objet, dict):
            objets.append(objet)
    return objets


# ── Options d'itinéraire, extraites du texte des prompts ─────────────────────

_ENTETE_BLOC = re.compile(
    r"^--- agent_id=(?P<agent>\S+)\s*\|\s*Destination:\s*(?P<motif>\S+)"
    r".*?\|\s*Departure:\s*(?P<depart>\d{1,2}:\d{2})\s*---\s*$")
_LIGNE_OPTION = re.compile(r"^-\s*\[(?P<index>\d+)\]\s*(?P<mode>[^:]+):\s*(?P<desc>.*)$")
_LIGNE_ETAPE = re.compile(r"^\s+·\s*(?P<etape>.+?)\s*$")


def blocs_itineraires(echanges: Iterable[dict[str, Any]]) -> list[BlocPrompt]:
    """Un bloc par agent et par prompt de décision (`itinary_multi_agent`).

    Les sous-puces « · » détaillent les étapes d'une option ; ce ne sont PAS des
    options. Le bloc mémoire commence à ``**History:**``.
    """
    blocs: list[BlocPrompt] = []
    for echange in echanges:
        if echange.get("category") != "itinary_multi_agent":
            continue
        jour = str(echange.get("sim_day") or "")
        for message in echange.get("messages") or []:
            if message.get("role") != "user":
                continue
            blocs.extend(_blocs_du_prompt(str(message.get("content") or ""), jour))
    blocs.sort(key=lambda b: (_cle_agent(b.agent), b.jour, b.depart_minutes or 0, b.motif))
    return blocs


def _blocs_du_prompt(texte: str, jour: str) -> list[BlocPrompt]:
    blocs: list[BlocPrompt] = []
    courant: dict[str, Any] | None = None

    def clore() -> None:
        if courant is None:
            return
        blocs.append(BlocPrompt(
            agent=courant["agent"], jour=jour, motif=motif_canonique(courant["motif"]),
            depart_minutes=courant["depart"],
            options=tuple(Option(index=o["index"], mode_brut=o["mode"],
                                 mode=mode_canonique_depuis_option(o["mode"]),
                                 description=o["desc"], etapes=tuple(o["etapes"]))
                          for o in courant["options"]),
            a_historique=courant["historique"] > 0,
            taille_historique=courant["historique"]))

    for ligne in texte.splitlines():
        entete = _ENTETE_BLOC.match(ligne)
        if entete:
            clore()
            heure, _, minute = entete.group("depart").partition(":")
            courant = {"agent": entete.group("agent"), "motif": entete.group("motif"),
                       "depart": int(heure) * 60 + int(minute),
                       "options": [], "historique": 0}
            continue
        if courant is None:
            continue
        if ligne.startswith("**History:**"):
            courant["historique"] = max(1, len(ligne) - len("**History:**"))
            continue
        etape = _LIGNE_ETAPE.match(ligne)
        if etape and courant["options"]:
            courant["options"][-1]["etapes"].append(etape.group("etape"))
            continue
        option = _LIGNE_OPTION.match(ligne)
        if option:
            courant["options"].append({
                "index": int(option.group("index")),
                "mode": option.group("mode").strip(),
                "desc": option.group("desc").strip(),
                "etapes": []})
    clore()
    return blocs


# ── Blocs de réflexion (known_beliefs) ───────────────────────────────────────

@dataclass(frozen=True)
class BlocReflexion:
    agent: str
    jour: str
    nb_croyances: int
    nb_observations: int


def blocs_reflexion(echanges: Iterable[dict[str, Any]]) -> list[BlocReflexion]:
    """Charge utile de `stm_reflection` : par agent, ``today`` et ``known_beliefs``."""
    blocs: list[BlocReflexion] = []
    for echange in echanges:
        if echange.get("category") != "stm_reflection":
            continue
        jour = str(echange.get("sim_day") or "")
        for message in echange.get("messages") or []:
            if message.get("role") != "user":
                continue
            blocs.extend(_blocs_reflexion_du_prompt(str(message.get("content") or ""), jour))
    blocs.sort(key=lambda b: (_cle_agent(b.agent), b.jour, b.nb_croyances))
    return blocs


_ENTETE_AGENT = re.compile(r"^---\s*AGENT\s+(?P<agent>\S+)\s*---\s*$")


def _blocs_reflexion_du_prompt(texte: str, jour: str) -> list[BlocReflexion]:
    depart = texte.find("# INPUT DATA")
    if depart < 0:
        return []
    blocs: list[BlocReflexion] = []
    agent: str | None = None
    tampon: list[str] = []

    def clore() -> None:
        if agent is None:
            return
        charge = "\n".join(tampon)
        debut = charge.find("{")
        if debut < 0:
            return
        objets = decoder_json_concatene(charge[debut:])
        if not objets:
            return
        donnees = objets[0]
        croyances = donnees.get("known_beliefs") or []
        aujourdhui = donnees.get("today") or []
        blocs.append(BlocReflexion(
            agent=agent, jour=jour,
            nb_croyances=len(croyances) if isinstance(croyances, list) else 0,
            nb_observations=len(aujourdhui) if isinstance(aujourdhui, list) else 0))

    for ligne in texte[depart:].splitlines():
        entete = _ENTETE_AGENT.match(ligne)
        if entete:
            clore()
            agent, tampon = entete.group("agent"), []
            continue
        if agent is not None and not ligne.startswith("```"):
            tampon.append(ligne)
    clore()
    return blocs


def autoreflexions(echanges: Iterable[dict[str, Any]]) -> dict[str, list[tuple[str, str]]]:
    """Auto-réflexions long terme, par agent : ``(jour, texte)`` en ordre chronologique."""
    par_agent: dict[str, list[tuple[str, str]]] = {}
    for echange in echanges:
        if echange.get("category") != "ltm_self_reflection":
            continue
        jour = str(echange.get("sim_day") or "")
        for item in _reponse_en_liste(echange.get("response")):
            agent = str(item.get("agent_id") or "")
            texte = str(item.get("reflection") or item.get("summary") or "").strip()
            if agent and texte:
                par_agent.setdefault(agent, []).append((jour, texte))
    for entrees in par_agent.values():
        entrees.sort()
    return par_agent


def _reponse_en_liste(reponse: Any) -> list[dict[str, Any]]:
    """`response` est tantôt une chaîne JSON, tantôt déjà décodée."""
    if isinstance(reponse, str):
        try:
            reponse = json.loads(reponse)
        except json.JSONDecodeError:
            return []
    if isinstance(reponse, dict):
        reponse = reponse.get("agents") or [reponse]
    if not isinstance(reponse, list):
        return []
    return [item for item in reponse if isinstance(item, dict)]


# ── Métadonnées LTM ───────────────────────────────────────────────────────────

def lire_ltm(chemin_run: Path) -> tuple[dict[str, list[EntreeLTM]], dict[str, dict[str, Any]]]:
    """Entrées de mémoire longue et journal des habitudes, par agent.

    Le parcours des shards est **trié** : l'ordre du système de fichiers ne doit
    jamais entrer dans le rapport (contrat F7).
    """
    racine = Path(chemin_run) / "long_term_memory" / "user_metadata"
    entrees: dict[str, list[EntreeLTM]] = {}
    habitudes: dict[str, dict[str, Any]] = {}
    if not racine.is_dir():
        return entrees, habitudes
    for fichier in sorted(racine.glob("shard_*/*.json")):
        try:
            charge = json.loads(fichier.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        person_id = str(charge.get("person_id") or fichier.stem)
        liste = [_entree_ltm(person_id, brut) for brut in (charge.get("entries") or [])
                 if isinstance(brut, dict)]
        liste.sort(key=lambda e: (e.timestamp, e.doc_id))
        entrees.setdefault(person_id, []).extend(liste)
        journal = charge.get("journal")
        if isinstance(journal, dict):
            habitudes[person_id] = journal
    return entrees, habitudes


def _entree_ltm(person_id: str, brut: dict[str, Any]) -> EntreeLTM:
    contenu = str(brut.get("content") or "")
    return EntreeLTM(
        person_id=person_id,
        doc_id=str(brut.get("doc_id") or ""),
        contenu=contenu,
        enonce=enonce_du_concept(contenu),
        memory_type=str(brut.get("memory_type") or ""),
        timestamp=str(brut.get("timestamp") or ""),
        importance=float(_flottant(brut.get("importance")) or 0.0),
        valence=str(brut.get("valence") or ""),
        axe_objet=brut.get("axe_objet"),
        axe_motif=brut.get("axe_motif"),
        axe_lieu=brut.get("axe_lieu"),
        axe_creneau=brut.get("axe_creneau"),
        axe_meteo=brut.get("axe_meteo"),
        force=float(_flottant(brut.get("force")) or 0.0),
        rappels=int(_flottant(brut.get("rappels")) or 0),
        dernier_rappel=brut.get("dernier_rappel"),
        observations=int(_flottant(brut.get("observations")) or 0),
        contre_exemples=int(_flottant(brut.get("contre_exemples")) or 0),
    )


def enonce_du_concept(contenu: str) -> str:
    """Le contenu d'un concept est une chaîne JSON d'un tableau de 5 éléments.

    Le premier élément est l'énoncé ; les suivants sont les mots-clés et les axes.
    Un contenu qui n'est pas ce tableau (une réflexion narrative) se rend tel quel.
    """
    texte = (contenu or "").strip()
    if not texte.startswith("["):
        return texte
    try:
        decode = json.loads(texte)
    except json.JSONDecodeError:
        return texte
    if isinstance(decode, list) and decode:
        return str(decode[0])
    return texte


# ── Journaux lisibles memoires/*.md ──────────────────────────────────────────

_NOM_AGENT = re.compile(r"^\d+$")
_CONSOLIDATION = re.compile(r"^###\s+`(?P<heure>[^`]+)`\s+CONSOLIDATION\s+—\s+déclencheur\s*:\s*"
                            r"\*\*(?P<declencheur>[^*]+)\*\*")
_OPERATION = re.compile(r"opération\s+\*\*(?P<operation>créé|confirmé|précisé|contredit)\*\*")
_RAPPEL = re.compile(r"\*\*rappel\*\*\s+—\s+(?P<nb>\d+)\s+souvenir\(s\) servi\(s\)\s*:\s*(?P<liste>.*)$")


def lire_journaux(chemin_run: Path) -> dict[str, Journal]:
    """Journaux `memoires/<person_id>.md`.

    Tout fichier dont le nom n'est pas un identifiant numérique est ignoré : le
    run de référence porte un `609_FR.md`, doublon traduit qui doublerait chaque
    compteur s'il était lu.
    """
    racine = Path(chemin_run) / "memoires"
    journaux: dict[str, Journal] = {}
    if not racine.is_dir():
        return journaux
    for fichier in sorted(racine.glob("*.md")):
        if not _NOM_AGENT.match(fichier.stem):
            continue
        journaux[fichier.stem] = _journal_depuis_md(
            fichier.stem, fichier.read_text(encoding="utf-8"))
    return journaux


def _journal_depuis_md(person_id: str, texte: str) -> Journal:
    journal = Journal(person_id=person_id)
    for ligne in texte.splitlines():
        consolidation = _CONSOLIDATION.match(ligne)
        if consolidation:
            journal.consolidations += 1
            declencheur = consolidation.group("declencheur").strip()
            journal.declencheurs[declencheur] = journal.declencheurs.get(declencheur, 0) + 1
            continue
        operation = _OPERATION.search(ligne)
        if operation:
            nom = operation.group("operation")
            journal.operations[nom] = journal.operations.get(nom, 0) + 1
            continue
        rappel = _RAPPEL.search(ligne)
        if rappel:
            incipits = tuple(
                _incipit(part) for part in rappel.group("liste").split(" · ")
                if part.strip() and not part.strip().startswith("+"))
            journal.rappels.append((rappel.group("nb"), incipits))
    return journal


def _incipit(fragment: str) -> str:
    """Le journal tronque les souvenirs servis : on garde le texte avant « (force … ) »."""
    texte = fragment.strip()
    coupe = texte.rfind(" (force ")
    if coupe > 0:
        texte = texte[:coupe]
    return texte.strip().rstrip("…").strip()


# ── Population ────────────────────────────────────────────────────────────────

def lire_population(chemin_run: Path) -> dict[str, dict[str, Any]]:
    """Personas du run, indexés par identifiant. Le premier `population_*.json` trié."""
    racine = Path(chemin_run)
    candidats = sorted(p for p in racine.glob("population_*.json")
                       if "checkpoint" not in p.name)
    for fichier in candidats:
        try:
            charge = json.loads(fichier.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(charge, dict):
            charge = charge.get("personas") or charge.get("population") or []
        if not isinstance(charge, list):
            continue
        return {str(p.get("person_id")): p for p in charge
                if isinstance(p, dict) and p.get("person_id") is not None}
    return {}


def profil(persona: dict[str, Any]) -> dict[str, Any]:
    """Fiche de profil, réduite à ce que le rapport affiche."""
    identite = persona.get("identity") or {}
    traits = identite.get("traits_json") or {}
    activites = identite.get("activities") or []
    motifs: list[str] = []
    for activite in activites:
        motif = motif_canonique(str(activite.get("purpose") or ""))
        if motif and motif not in motifs:
            motifs.append(motif)
    return {
        "nom": str(identite.get("name") or traits.get("name") or "—"),
        "age": traits.get("age"),
        "occupation": traits.get("main_occupation") or traits.get("professional_activity"),
        "revenu": traits.get("income"),
        "voiture": traits.get("car_availability"),
        "velo": traits.get("personal_bike"),
        "abonnement_tc": traits.get("has_pt_subscription"),
        "commune": traits.get("residence_commune"),
        "zone": traits.get("residence_zone"),
        "motifs": motifs,
        "nb_activites": len(activites),
    }


# ── Chargement complet ────────────────────────────────────────────────────────

def charger(chemin_run: Path | str) -> Run:
    """Lit tout le run d'un coup. Chaque source absente rend une structure vide."""
    racine = Path(chemin_run)
    if not racine.is_dir():
        raise FileNotFoundError(f"dossier de run introuvable : {racine}")
    trajets, rejeu, rejeu_detail = lire_moves(racine)
    echanges = lire_echanges(racine)
    ltm, habitudes = lire_ltm(racine)
    return Run(
        chemin=racine,
        trajets=trajets,
        rejeu=rejeu,
        rejeu_detail=rejeu_detail,
        arrivees=lire_arrivees(racine),
        evenements=lire_evenements(racine),
        echanges=echanges,
        blocs=blocs_itineraires(echanges),
        ltm=ltm,
        habitudes=habitudes,
        journaux=lire_journaux(racine),
        personas=lire_population(racine),
        autoreflexions=autoreflexions(echanges),
    )


def horodatage_iso(valeur: Any) -> datetime | None:
    """Parse tolérant d'un horodatage ISO ; ``None`` si illisible."""
    texte = str(valeur or "").strip().replace("Z", "+00:00")
    if not texte:
        return None
    try:
        return datetime.fromisoformat(texte)
    except ValueError:
        return None
