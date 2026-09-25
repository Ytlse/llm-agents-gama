"""Les stubs du banc — ticket 100, tests fonctionnels.

AUCUN DE CES OBJETS NE SIMULE UNE INTELLIGENCE. Chacun fabrique un objet dont le **format** est
celui du dépôt : une population, une mémoire longue, une journée, un `moves.csv`, un point de
reprise. Ce sont des structures, pas des comportements — les fabriquer à la main coûte zéro
jeton et les rend reproductibles, ce qu'un run ne sera jamais.

RÈGLE UNIQUE, ET ELLE N'EST PAS NÉGOCIABLE
-------------------------------------------
Un stub de format **importe** la définition du dépôt — `CSV_HEADERS`, `MemoryEntry`, les
schémas JSON — au lieu de la recopier. Un stub qui recopie une liste de colonnes teste sa
propre copie : il reste vert le jour où le vrai format change, et c'est précisément ce que le
banc doit attraper. C'est la leçon du lot A du ticket 077, où deux vocabulaires de modes
coexistaient sans que rien ne le dise.
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
AGENTS = RACINE / "services" / "llm-agents"
for chemin in (str(RACINE), str(AGENTS)):
    if chemin not in sys.path:
        sys.path.insert(0, chemin)

from llm.memory import MemoryEntry, MemoryType  # noqa: E402

# Ancre du banc : lundi 16 mars 2026, 5 h — celle des runs du dépôt.
ANCRE = datetime(2026, 3, 16, 5, 0)


# ── La population ───────────────────────────────────────────────────────────────────────────
@dataclass
class IdentiteStub:
    traits_json: dict


@dataclass
class AgentStub:
    """Le minimum que lisent `foyer.py`, `exposition.py` et le contrôleur.

    ⚠ Ce n'est PAS un `models.Person` : construire un Person complet demanderait un domicile,
    des activités et un état de planification dont rien ici n'a besoin. Les trois attributs
    ci-dessous sont exactement ceux que le code du ticket 100 lit sur un agent — si un
    quatrième apparaissait, ce stub casserait, et c'est ce qu'on veut.
    """

    person_id: str
    household_id: str | None = None
    immobile: bool = False
    identity: IdentiteStub = field(default_factory=lambda: IdentiteStub({}))


def population_de_banc() -> list[AgentStub]:
    """Douze agents, six foyers de deux, profils volontairement contrastés.

    La forme vient du `MANIFEST.yaml` de `population_20_foyers_059` : foyers de taille 2, deux
    membres mobiles, au moins un abonné TC. Les contrastes sont ceux du ticket 078 § 0 — permis,
    vélo, abonnement — parce que c'est sur eux que la règle R4 se joue : ce que l'un apprend de
    la voiture ne doit jamais devenir une croyance de l'autre.
    """
    modele = [
        # (foyer, (id, nom, âge, permis, voitures, vélo, abonnement TC))
        ("605813", ("1254859", "Frédérique Lacombe", 20, True, 1, "e-bike", True),
                   ("1254860", "Auguste Guérin", 20, False, 0, "No bike", True)),
        ("234839", ("527098", "Charlotte-Odette Moreau", 62, True, 1, "No bike", False),
                   ("527099", "Rémy de Renaud", 62, False, 0, "No bike", True)),
        ("471076", ("1013072", "Colette Vaillant-Fleury", 44, True, 2, "Own bike", False),
                   ("1013073", "Aimé Vaillant", 12, False, 0, "No bike", True)),
        ("538432", ("880011", "Lucien Barbier", 35, True, 1, "Own bike", True),
                   ("880012", "Marthe Barbier", 33, True, 1, "No bike", True)),
        ("73563",  ("640201", "Solange Perrot", 71, False, 0, "No bike", True),
                   ("640202", "Hubert Perrot", 74, True, 1, "No bike", False)),
        ("625551", ("990301", "Nadia Fontaine", 28, False, 0, "e-bike", True),
                   ("990302", "Oscar Fontaine", 30, True, 1, "Own bike", False)),
    ]
    agents: list[AgentStub] = []
    for foyer, *membres in modele:
        for pid, nom, age, permis, voitures, velo, tc in membres:
            agents.append(AgentStub(
                person_id=pid,
                household_id=foyer,
                identity=IdentiteStub({
                    "name": nom, "age": age,
                    "has_driving_license": permis, "number_of_cars": voitures,
                    "personal_bike": velo, "has_pt_subscription": tc,
                    "main_occupation": "Full-Time Worker" if age < 65 else "Retired",
                    "household_size": 2,
                }),
            ))
    return agents


def perception_stub(agent: AgentStub) -> str:
    """Le récit d'identité servi au modèle, dans la forme de `get_person_identity_description`.

    Court volontairement : le jugement porte sur l'événement, pas sur la journée. Un persona
    long ferait payer des jetons d'entrée sans déplacer la réponse.
    """
    t = agent.identity.traits_json
    morceaux = [f"{t['name']}, {t['age']}, {t.get('main_occupation', 'Worker')}"]
    morceaux.append("has a driving licence" if t.get("has_driving_license")
                    else "has no driving licence")
    morceaux.append(f"{t.get('number_of_cars', 0)} car(s) in the household")
    morceaux.append("owns a bike" if str(t.get("personal_bike", "")).lower() not in
                    ("", "no bike") else "has no bike")
    morceaux.append("holds a public transport pass" if t.get("has_pt_subscription")
                    else "holds no public transport pass")
    return ". ".join(morceaux) + "."


# ── La mémoire longue ───────────────────────────────────────────────────────────────────────
class MemoireLongueStub:
    """Ce que `foyer.py` et les mesures lisent : `user_metadata[pid]["entries"]`.

    Assez pour tout le lot 4. Ne porte pas d'index vectoriel — aucun test du banc ne rappelle
    par similarité, et un index demanderait un modèle d'embedding, donc un coût.
    """

    def __init__(self) -> None:
        self.user_metadata: dict[str, dict] = {}

    def ajouter(self, entree: MemoryEntry) -> MemoryEntry:
        self.user_metadata.setdefault(entree.person_id, {"entries": []})["entries"].append(entree)
        return entree

    def has_memories(self, person_id: str) -> bool:
        return bool((self.user_metadata.get(str(person_id)) or {}).get("entries"))


def reflexion_stub(person_id: str, texte: str, jour: int) -> MemoryEntry:
    """Un bilan de journée, tel que la consolidation en écrit un.

    C'est CE texte que le récit du soir cite (D1 + Q3, 2026-09-22) : le foyer ne rédige rien,
    il reprend ce que l'autre a écrit. L'écrire à la main remplace huit jours de simulation.
    """
    return MemoryEntry(
        content=texte,
        timestamp=ANCRE + timedelta(days=jour - 1, hours=17),
        memory_type=MemoryType.REFLECTION,
        person_id=str(person_id),
        importance=0.30,
    )


def concept_stub(
    person_id: str, texte: str, jour: int, *, mode: str = "public_transport",
    observations: int = 2, contre: int = 0, origine: str | None = "vecu",
    motif: str | None = "work",
) -> MemoryEntry:
    """Un concept, dans le 5-uplet canonique du lot 3 du ticket 071.

    `observations` décide de R1, `origine` décide de D2, `mode` décide de R4 : les trois règles
    que le lot 4 fait jouer se pilotent depuis cette signature.
    """
    return MemoryEntry(
        content=json.dumps([texte, "", "", "", ""], ensure_ascii=False),
        timestamp=ANCRE + timedelta(days=jour - 1, hours=17),
        memory_type=MemoryType.CONCEPT,
        person_id=str(person_id),
        observations=observations,
        contre_exemples=contre,
        axe_objet=mode,
        axe_motif=motif,
        origine=origine,
        importance=0.30,
    )


def journee_stub(person_id: str, jour: int, *, mode: str = "car") -> list[MemoryEntry]:
    """Les trois entrées de mémoire courte qu'une journée produit réellement.

    Décision, arrivée, contrainte de chaîne. Ce n'est pas une simplification : c'est ce que le
    contrôleur écrit, et c'est la raison pour laquelle le récit du soir « par entrée brute »
    aurait triplé le bloc (Q1).
    """
    base = ANCRE + timedelta(days=jour - 1)
    return [
        MemoryEntry(
            content=f"[ TRAVEL_PLAN ] Plan to head <work>. Chosen mode: {mode}.",
            timestamp=base + timedelta(hours=3), memory_type=MemoryType.CONVERSATION,
            person_id=str(person_id), axe_objet=mode, axe_motif="work", origine="vecu",
        ),
        MemoryEntry(
            content="[ ARRIVAL ] Arrived at work 12 minutes later than planned.",
            timestamp=base + timedelta(hours=3, minutes=50),
            memory_type=MemoryType.CONVERSATION, person_id=str(person_id),
            importance=0.24, axe_objet=mode, axe_motif="work", origine="vecu",
        ),
        MemoryEntry(
            content="[ TRAVEL_PLAN ] No choice was possible: this was the only itinerary.",
            timestamp=base + timedelta(hours=11), memory_type=MemoryType.CONVERSATION,
            person_id=str(person_id), importance=0.10, axe_objet=mode, axe_motif="home",
            origine="vecu",
        ),
    ]


# ── Les itinéraires ─────────────────────────────────────────────────────────────────────────
def itineraires_stub(modes: tuple[str, ...] = ("car", "public_transport", "cycling")) -> list[dict]:
    """Deux à quatre propositions, dans la forme d'une option servie au décideur.

    Aucun appel à OTP : le banc ne teste pas le routage, il teste ce que le ticket 100 ajoute.
    Les durées sont plausibles et surtout **distinctes**, pour qu'un choix ait un sens.
    """
    duree = {"car": 1080, "public_transport": 2040, "cycling": 1500, "walking": 3600}
    return [
        {"index": i, "mode": m, "duration_s": duree.get(m, 1800),
         "distance_km": round(duree.get(m, 1800) / 240, 1)}
        for i, m in enumerate(modes)
    ]


# ── Le journal de décisions ─────────────────────────────────────────────────────────────────
def moves_stub(
    chemin: Path, *, evenement: str, jours: range = range(-5, 16),
    roles: tuple[str, ...] = ("expose", "co_resident", "temoin"),
    part_avant: float = 0.60, creux: dict[str, float] | None = None,
    par_jour: int = 4,
) -> Path:
    """Un `moves.csv` aux colonnes RÉELLES, importées de `move_logger`.

    ⚠ Les en-têtes ne sont pas recopiés : `CSV_HEADERS` est importé. Une colonne ajoutée au
    dépôt apparaît donc ici sans rien toucher, et une ligne qui n'a plus le bon nombre de
    champs fait échouer le banc — c'est exactement le défaut qu'on veut voir tôt, parce qu'un
    décalage de colonnes ne se lit qu'à la relecture, quand il est trop tard.
    """
    from urban_mobility_agents.utils.move_logger import CSV_HEADERS

    creux = creux or {"expose": 0.30, "co_resident": 0.08, "temoin": 0.0}
    lignes = []
    for jour in jours:
        for role in roles:
            for i in range(par_jour):
                apres = jour >= 0
                part = part_avant - (creux.get(role, 0.0) if apres and jour <= 10 else 0.0)
                # Alternance déterministe : la part visée se lit dans les fréquences, pas dans
                # un tirage — un banc qui tire au sort ne se rejoue pas à l'identique.
                voiture = (i / par_jour) < part
                lignes.append({
                    # ⚠ « Référence » est l'identifiant du RUN ; l'agent est sous « ID
                    # Personne ». Le stub écrivait l'agent dans la mauvaise colonne, et les
                    # tests passaient : ils vérifiaient la convention du stub, pas celle du
                    # dépôt. C'est exactement le piège que la règle « importer, ne pas
                    # recopier » devait éviter — elle couvrait les EN-TÊTES, pas le SENS des
                    # colonnes. Trouvé par un run réel le 2026-09-22.
                    "Référence": "banc",
                    "ID Personne": f"{role}_{i}",
                    "Heure de départ": (ANCRE + timedelta(days=jour + 10)).strftime(
                        "%Y-%m-%d %H:%M"),
                    "Mode de transport Choisi": "car" if voiture else "public_transport",
                    "P(Voiture Privée) %": round(part * 100, 1),
                    "P(Transports_collectifs) %": round((1 - part) * 100, 1),
                    "Choc": evenement,
                    "Jour relatif au choc": jour,
                    "Rôle": role,
                    "Raison d'exposition": f"foyer:{role}",
                    "Contrainte de chaîne": "",
                })
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADERS, extrasaction="ignore")
        w.writeheader()
        for ligne in lignes:
            w.writerow({c: ligne.get(c, "") for c in CSV_HEADERS})
    return chemin


def point_de_reprise_stub(workdir: Path, jour: int, *, foyer: dict | None = None) -> Path:
    """Un point de reprise valide, au format de `utils/reprise.py`.

    La description est écrite EN DERNIER, comme dans le vrai : c'est elle qui rend le point
    valide, et un point à moitié écrit serait restauré en silence.
    """
    from urban_mobility_agents.utils import reprise

    cible = workdir / reprise.POINTS / f"jour_{jour:03d}"
    for nom in reprise._A_COPIER:
        (cible / nom).mkdir(parents=True, exist_ok=True)
    (cible / reprise.DESCRIPTION).write_text(
        json.dumps({
            "jour_simule": jour,
            "timestamp_simule": int((ANCRE + timedelta(days=jour - 1)).timestamp()),
            "compteurs": {},
            "foyer": foyer or {},
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    return cible


def echanges_stub(
    chemin: Path, *, agent: str, texte: str, exposition: int,
    categorie: str = "itinary_multi_agent",
) -> Path:
    """Un `llm_exchanges.jsonl` portant des prompts de DÉCISION, dans la forme réelle.

    `exposition` est l'instant de l'événement, en secondes simulées UTC. Chaque décision est
    datée après lui (`sim_ts`, `sim_day`), comme les vrais échanges : le tableau écarte une
    décision non datée, ou antérieure à l'exposition (2026-09-25).

    Le tableau des quatre voies lit ce fichier : il y cherche le texte de l'événement, bloc par
    bloc. Sans lui, il sort « non concluant », ce qui est exact — mais il faut alors des
    prompts pour vérifier qu'il sait aussi conclure.

    Trois prompts, et ils couvrent les trois cas qui comptent :
    - l'événement retrouvé TEL QUEL dans « Ce qui a changé récemment » ;
    - l'événement REFORMULÉ, attrapé seulement par les mots saillants — c'est le cas réel du
      régime vécu, où la réflexion du soir reformule avant que le texte n'atteigne la mémoire ;
    - un prompt où il ne figure pas du tout.

    ⚠ L'agent se reconnaît à `agent_id=`, que le gabarit de décision pose en tête de chaque
    persona. C'est la seule attribution fiable : tous les lecteurs d'un même article partagent
    le même texte.

    ⚠ Les mots de la reformulation viennent de `mots_saillants()`, IMPORTÉ du tableau. Le stub
    les tirait de sa propre règle (mots de plus de quatre lettres), qui ne rendait rien sur
    « Bed bugs on line A. » : le prompt reformulé ne portait aucun mot saillant, aucune cellule
    `~` ne pouvait sortir, et A9.5 restait vert sur la seule légende (2026-09-25). Il en faut
    DEUX, le seuil du tableau : un texte qui n'en fournit pas autant est refusé, plutôt que de
    fabriquer en silence un prompt qu'aucun appariement ne peut attraper.
    """
    from scripts.analysis.tableau_quatre_voies import mots_saillants

    saillants = mots_saillants(texte, combien=2)
    if len(saillants) < 2:
        raise ValueError(
            f"echanges_stub : « {texte} » ne fournit que {len(saillants)} mot(s) saillant(s) "
            f"({saillants}) ; le tableau en exige deux pour apparier une reformulation."
        )
    prompts = [
        f"--- agent_id={agent} ---\nMes habitudes\n- souvent la voiture\n"
        f"Ce qui a changé récemment\n- {texte}\n",
        f"--- agent_id={agent} ---\nCe que je sais\n"
        f"- I read something about {' and '.join(saillants)} the other morning\n",
        f"--- agent_id={agent} ---\nMes habitudes\n- rien de notable\n",
    ]
    chemin.parent.mkdir(parents=True, exist_ok=True)
    # Indenté, comme la passerelle : écrit sur une ligne, ce stub laissait passer un lecteur
    # ligne à ligne que le premier run réel faisait tomber (2026-09-25).
    def _echange(rang: int, prompt: str) -> dict:
        sim_ts = exposition + 3600 * (rang + 1)
        return {"category": categorie, "sim_ts": sim_ts,
                "sim_day": datetime.fromtimestamp(sim_ts, tz=timezone.utc).strftime("%Y-%m-%d"),
                "messages": [{"role": "user", "content": prompt}]}

    chemin.write_text(
        "".join(
            json.dumps(_echange(rang, p), ensure_ascii=False, indent=2) + "\n"
            for rang, p in enumerate(prompts)
        ),
        encoding="utf-8",
    )
    return chemin
