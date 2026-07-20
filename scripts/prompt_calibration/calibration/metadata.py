"""Métadonnées persona structurées — phase 0.1 du ticket 004.

Principe (D6) : les attributs de scoring proviennent de la **jointure**
``agent_id → traits_json`` du ``population_N.json`` de l'expérience source.
Le texte du persona ne sert plus qu'au LLM — à une exception près : la
distance minimale, extraite des options de trajet (seule métadonnée
réellement textuelle). Le genre vient de ``traits_json.gender`` : **zéro
inférence** depuis le prénom.

Deux formats d'en-tête de section persona sont supportés :
- courant : ``--- agent_id=503036 | Destination : leisure | Départ : 15:53 ---``
- legacy  : ``--- PERSONA 503036 | Destination : work | Départ : 08:00 ---``
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# ── Buckets Cerema (labels identiques à cerema_values.yaml) ─────────────────

_AGE_BUCKETS = [(9, "5-9"), (14, "10-14"), (19, "15-19"), (24, "20-24"),
                (29, "25-29"), (34, "30-34"), (39, "35-39"), (44, "40-44"),
                (49, "45-49"), (54, "50-54"), (59, "55-59"), (64, "60-64"),
                (69, "65-69"), (74, "70-74")]

_DIST_BUCKETS = [(1, "0-1km"), (2, "1-2km"), (5, "2-5km"),
                 (10, "5-10km"), (20, "10-20km"), (50, "20-50km")]


def age_to_cat(age: int) -> str:
    for bp, label in _AGE_BUCKETS:
        if age <= bp:
            return label
    return "75-130"


def distance_to_cat(dist_km: float) -> str:
    for bp, label in _DIST_BUCKETS:
        if dist_km < bp:
            return label
    return "plus_50km"


# ── Mappings structurés (traits_json → catégories Cerema) ───────────────────

GENDER_MAP = {"Male": "Homme", "Female": "Femme"}

# traits_json.main_occupation → label occupation de cerema_values.yaml.
# Correspondance 1:1 vérifiée sur population_1000.json (2026-07-13) — toute
# valeur hors de cette table est une anomalie à remonter, pas à deviner.
OCCUPATION_MAP = {
    "Scolaire (jusqu'au Bac)":     "scolaire",
    "Étudiant":                    "etudiant",
    "Travail à plein temps":       "actif_temps_plein",
    "Travail à temps partiel":     "actif_temps_partiel",
    "Chômeur/recherche d'emploi":  "chomeur_recherche_emploi",
    "Personne au foyer":           "personne_au_foyer",
    "Retraité":                    "Retraité",
}

# Destination (en-tête de section) → motif Cerema (motif_deplacement).
# leisure / other / home n'ont pas de correspondance dans la référence.
DEST_TO_MOTIF = {
    "work":      "travail",
    "education": "etudes",
    "shop":      "achats",
}

# ── Parsing des sections persona ─────────────────────────────────────────────

# Marqueur de début de section, commun aux deux formats.
_SECTION_SPLIT_RE = re.compile(r"(?=---\s*(?:agent_id=|PERSONA\b))")

# En-tête : agent_id + destination, formats courant et legacy confondus.
_HEADER_RE = re.compile(
    r"---\s*(?:agent_id=|PERSONA\s+)(\d+)\s*\|\s*Destination\s*:\s*(\w+)",
    re.IGNORECASE,
)

_DIST_RE = re.compile(r"Distance\s*:\s*([\d.]+)\s*(km|m)\b", re.IGNORECASE)


def split_entry_personas(user_msg: str) -> tuple[str, list[str]]:
    """Sépare le message utilisateur en (préambule contexte, [sections persona]).

    Le préambule (ex. « **Contexte :** Météo … ») précède la première section ;
    l'épilogue éventuel (consigne de réponse après la dernière section) reste
    attaché à la dernière section — il ne contient aucune métadonnée.
    """
    preamble, personas = "", []
    for part in _SECTION_SPLIT_RE.split(user_msg):
        chunk = part.strip()
        if not chunk:
            continue
        if chunk.startswith("---"):
            personas.append(chunk)
        elif not personas:
            preamble = chunk
    return preamble, personas


def parse_persona_header(section: str) -> tuple[str, str] | None:
    """Extrait ``(agent_id, destination)`` de l'en-tête d'une section persona.
    Renvoie ``None`` si l'en-tête ne matche aucun des deux formats connus."""
    m = _HEADER_RE.search(section)
    return (m.group(1), m.group(2).lower()) if m else None


# Marqueur de la section mémoire (STM/LTM) d'un bloc persona (phase 0.2).
_MEMORY_HEADER = "**Historique :**"


def strip_memory_section(section: str) -> str:
    """Retire la section mémoire (``**Historique :**``) d'un bloc persona.

    Le contenu mémoire (souvenirs STM datés + concepts ``[Concept]`` LTM) est
    **spécifique au run source et non reproductible** : il ne doit pas entrer
    dans les jeux val/test, dont la mesure de référence ne doit dépendre que du
    profil démographique, du contexte météo et des options de trajet
    (ticket 004 §0.2).

    Le bloc mémoire est un paragraphe (séparé par une ligne vide) commençant par
    ``**Historique :**`` ; on le supprime en préservant le préambule (persona +
    options de trajet) et un éventuel épilogue (consigne de réponse) qui suit.
    """
    if _MEMORY_HEADER not in section:
        return section
    paragraphs = re.split(r"\n\n+", section)
    kept = [p for p in paragraphs if not p.lstrip().startswith(_MEMORY_HEADER)]
    return "\n\n".join(kept).rstrip() + "\n"


def extract_min_distance_km(text: str) -> float | None:
    """Distance minimale (km) parmi les options de trajet d'une section."""
    dists = []
    for m in _DIST_RE.finditer(text):
        val = float(m.group(1))
        if m.group(2).lower() == "m":
            val /= 1000.0
        dists.append(val)
    return min(dists) if dists else None


# ── Jointure population ──────────────────────────────────────────────────────

def load_population(path: str | Path) -> dict[str, dict]:
    """Charge ``population_N.json`` et renvoie ``agent_id → attributs de scoring``.

    Lève ``KeyError`` si un trait attendu manque et ``ValueError`` si une
    valeur (genre, occupation) sort des tables de correspondance — on remonte
    l'anomalie au lieu de produire une métadonnée fausse en silence.
    """
    population = json.loads(Path(path).read_text(encoding="utf-8"))
    traits_by_id: dict[str, dict] = {}
    for person in population:
        agent_id = str(person["person_id"])
        traits = person["identity"]["traits_json"]
        gender, occupation = traits["gender"], traits["main_occupation"]
        if gender not in GENDER_MAP:
            raise ValueError(f"Genre inconnu pour l'agent {agent_id}: {gender!r}")
        if occupation not in OCCUPATION_MAP:
            raise ValueError(
                f"Occupation inconnue pour l'agent {agent_id}: {occupation!r}")
        age = int(traits["age"])
        traits_by_id[agent_id] = {
            "genre":          GENDER_MAP[gender],
            "age":            age,
            "age_cat":        age_to_cat(age),
            "occupation":     OCCUPATION_MAP[occupation],
            "household_size": traits.get("household_size"),
        }
    return traits_by_id


def build_decision_records(entries: list[dict],
                           traits_by_id: dict[str, dict],
                           ) -> tuple[list[dict], list[dict]]:
    """Rattache chaque section persona des entrées à ses métadonnées exactes.

    Renvoie ``(records, anomalies)`` :
    - un *record* par décision (une section persona d'une entrée) :
      identité + traits joints + motif (destination) + distance + textes bruts
      (section, contexte météo) pour la reconstruction des lots d'éval ;
    - une *anomalie* par section non rattachable (en-tête non parsable ou
      agent absent de la population), avec sa cause — le critère d'acceptation
      de la phase 0 est ``anomalies == []``.
    """
    records, anomalies = [], []
    for entry_idx, entry in enumerate(entries):
        user_msg = entry["messages"][1]["content"]
        preamble, sections = split_entry_personas(user_msg)
        for section in sections:
            header = parse_persona_header(section)
            if header is None:
                anomalies.append({"entry": entry_idx, "cause": "header_non_parsable",
                                  "extrait": section[:120]})
                continue
            agent_id, destination = header
            traits = traits_by_id.get(agent_id)
            if traits is None:
                anomalies.append({"entry": entry_idx, "cause": "agent_hors_population",
                                  "agent_id": agent_id})
                continue
            dist_km = extract_min_distance_km(section)
            records.append({
                "agent_id":    agent_id,
                "entry":       entry_idx,
                "task_id":     entry.get("task_id"),
                "destination": destination,
                "motif":       DEST_TO_MOTIF.get(destination),
                "dist_km":     dist_km,
                "dist_cat":    distance_to_cat(dist_km) if dist_km is not None else None,
                "context":     preamble.replace("**Contexte :**", "").strip(),
                "section":     section,
                **traits,
            })
    return records, anomalies
