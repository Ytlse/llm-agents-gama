#!/usr/bin/env python3
"""Par quelle VOIE le passé atteint une décision — ticket 100, lot 5.

LA QUESTION
-----------
Un agent subit une panne, s'en détourne quinze jours, puis y revient. Des quatre voies par
lesquelles son passé atteint une décision, **laquelle a porté cet effet ?** Le § 3.4 du
manuscrit les nomme, et le dispositif les écrit toutes les quatre dans le prompt :

| Voie | Dans le prompt | Ce qu'elle porte |
|---|---|---|
| `habitudes` | « Mes habitudes » | ce que l'agent fait le plus souvent |
| `connaissances` | « Ce que je sais » | ce qu'il tient pour vrai — les concepts |
| `changements` | « Ce qui a changé récemment » | les souvenirs graves et les croyances écartées |
| `rappel` | trois souvenirs choisis | le rappel vectoriel, tracé dans `trace_rappel.jsonl` |

Ce script dit, **par régime et par rôle**, combien de décisions ont vu l'événement passer par
chacune, et combien ne l'ont vu par aucune. Seules comptent les décisions **postérieures** à
l'exposition (`sim_ts` de l'échange contre `timestamp` de l'exposition) ; les antérieures et les
non datées sont écartées, et comptées. Chaque agent se lit dans **sa** section du prompt : un
appel groupe plusieurs agents, et les blocs d'un voisin ne sont pas les siens.

LE RAPPEL : LE SOUVENIR DE L'ÉVÉNEMENT, SERVI, ET VU
----------------------------------------------------
Qu'un souvenir ait été servi ne dit rien : il faut que ce soit **celui de l'événement**. Il se
retrouve en mémoire longue — tel quel pour le `lu`, qui dépose `[ PRESSE ] … « texte »` (lien
exact) ; par mots saillants pour le vécu, que la réflexion reformule (lien `~`). La décision se
relie à sa trace par l'agent, le jour et l'heure de départ de son en-tête, et le souvenir compte
s'il est dans `servis` **et** dans les souvenirs rappelés du prompt : la trace liste le top-K,
le prompt n'en reçoit que les trois plus récents, et jamais une entrée `conversation`. Un `0`
ne sort qu'au rappel, mesuré : lien exact, trace appariée, jamais servi. Sans trace, ou sans
souvenir identifié, la cellule reste vide, et le pied du tableau dit pourquoi.

CE QU'IL NE SAIT PAS FAIRE, ET IL LE DIT
-----------------------------------------
⚠ **L'appariement par le texte échoue pour le vécu.** Mesuré le 2026-09-16 : le texte injecté —
« The engine made a grinding noise and the car stalled » — n'est jamais recopié tel quel. Il
passe en mémoire courte, la réflexion le REFORMULE, et c'est la reformulation qui atteint la
mémoire longue. Chercher le texte littéral ne rend donc rien.

D'où deux recherches, et elles ne valent pas la même chose :

- **exacte** — le texte de l'événement, ou un de ses fragments distinctifs, retrouvé tel quel.
  Elle est fiable quand elle trouve, et muette quand elle ne trouve pas.
- **par mots saillants** — les mots rares du texte, retrouvés ensemble. Elle est indicative,
  et le tableau le dit : une cellule issue de cette voie porte la mention `~`.

Une décision pour laquelle aucune des deux ne conclut sort **vide**, jamais `non`. Écrire
« l'événement n'a pesé sur aucune décision » là où la vérité est « on ne sait pas le dire »
serait un mensonge, et ce dépôt en a déjà produit.

    python scripts/analysis/tableau_quatre_voies.py <run> [--markdown]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from scripts.analysis.lecture_avant_decision import informes_du_run, sous_role
from scripts.analysis.memoire.sources import (
    EntreeLTM,
    horodatage_iso,
    lire_echanges,
    lire_ltm,
)

# Les en-têtes que `llm/noyau.py` pose dans le prompt. LUS ICI, et il faut qu'ils restent
# alignés : un en-tête renommé ferait sortir une voie à zéro sans qu'aucune erreur n'apparaisse.
# Le test `scripts/tests/test_100_lot5_sorties.py` les compare à ceux de `noyau.py`.
EN_TETES = {
    "habitudes": "Mes habitudes",
    "connaissances": "Ce que je sais",
    "changements": "Ce qui a changé récemment",
}
VOIES = ("habitudes", "connaissances", "changements", "rappel")
CATEGORIE_DECISION = "itinary_multi_agent"

# L'en-tête de chaque persona dans un prompt de décision. Un prompt en groupe plusieurs : les
# blocs d'un agent se cherchent dans SA section, jamais dans le prompt entier.
_ENTETE_AGENT = re.compile(r"^--- agent_id=(?P<agent>[^\s|]+)(?P<reste>.*)$", re.MULTILINE)
_DEPART = re.compile(r"Departure:\s*(?P<heure>\d{1,2}):(?P<minute>\d{2})")
# Les souvenirs rappelés, que `llm_agent.py` écrit APRÈS les trois blocs, datés
# (`[Thursday, March 19] …`) ou marqués `[Concept] …`, et que le gabarit préfixe de « - ».
# Sans cette borne, le dernier bloc nommé avalait les souvenirs rappelés.
_LIGNE_RAPPEL = re.compile(r"^- \[(?:Concept|[A-Z][a-z]+, [A-Z][a-z]+ \d{1,2})\] ",
                           re.MULTILINE)
# Longueur du texte comparé. Normalisée — blancs réduits — des deux côtés : un saut de ligne
# de l'article et l'espace qui le remplace dans un autre rendu restent le même texte.
_SIGNATURE = 60
_ENONCE = 80

# Mots trop courants pour être saillants. Volontairement court : la liste sert à écarter le
# bruit, pas à faire de la linguistique.
_BANALS = frozenset("""
the and for with that this from they have been were was are but not you your his her its
into than then there here when what which while would could should about after before
""".split())
_MOT = re.compile(r"[A-Za-zÀ-ÿ']{4,}")


def mots_saillants(texte: str, combien: int = 6) -> list[str]:
    """Les mots les plus rares du texte, dans l'ordre d'apparition. Indicatifs, jamais probants."""
    vus: list[str] = []
    for mot in _MOT.findall(texte or ""):
        bas = mot.lower()
        if bas in _BANALS or bas in vus:
            continue
        vus.append(bas)
    # Les plus longs d'abord : « grinding » discrimine, « road » non.
    return sorted(vus, key=len, reverse=True)[:combien]


def _jsonl(chemin: Path) -> list[dict]:
    """Un vrai JSONL, un objet par ligne : `evenements.jsonl`, `chocs.jsonl`, `trace_rappel.jsonl`.

    PAS `llm_exchanges.jsonl` : la passerelle y écrit des objets indentés, qu'une lecture ligne
    à ligne ne décode pas — ou décode de travers, une liste de chaînes rendant des chaînes nues.
    """
    if not chemin.is_file():
        return []
    lignes = []
    for brut in chemin.read_text("utf-8").splitlines():
        brut = brut.strip()
        if not brut:
            continue
        try:
            lignes.append(json.loads(brut))
        except json.JSONDecodeError:
            # Dernière ligne tronquée par un arrêt brutal : sautée, jamais fatale.
            continue
    return lignes


def evenements_du_run(run: Path) -> list[dict]:
    lignes = _jsonl(run / "evenements.jsonl")
    return lignes or _jsonl(run / "chocs.jsonl")


def roles_du_run(run: Path) -> dict[str, str]:
    """`{person_id: rôle}`, lu dans `moves.csv`. Vide si la colonne n'y est pas.

    L'agent est dans `ID Personne`. `Référence` porte le nom du run (`experiences/journal.py`) :
    lue comme identifiant, elle ne rendait aucun rôle, et chaque ligne du tableau sortait `?`.
    """
    chemin = run / "moves.csv"
    if not chemin.is_file():
        return {}
    roles: dict[str, str] = {}
    with chemin.open(encoding="utf-8") as f:
        lecteur = csv.DictReader(f)
        if "Rôle" not in (lecteur.fieldnames or []):
            return {}
        for ligne in lecteur:
            pid = (ligne.get("ID Personne") or ligne.get("person_id") or "").strip()
            role = (ligne.get("Rôle") or "").strip()
            if pid and role:
                roles.setdefault(pid, role)
    return roles


def _norm(texte: str) -> str:
    """Les blancs réduits à une espace : la forme sous laquelle deux textes se comparent."""
    return " ".join((texte or "").split())


def _signature(texte: str) -> str:
    """Le début du texte de l'événement, normalisé : ce que l'appariement exact cherche."""
    return _norm(texte)[:_SIGNATURE]


def _instant(valeur) -> float | None:
    """Des secondes simulées UTC, ou `None` si la valeur manque ou ne se lit pas."""
    if valeur is None or valeur == "":
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _jour_et_heure(instant: float) -> tuple[str, str]:
    t = datetime.fromtimestamp(instant, tz=timezone.utc)
    return t.strftime("%Y-%m-%d"), t.strftime("%H:%M")


# ── Les expositions ──────────────────────────────────────────────────────────────


class Exposition(NamedTuple):
    canal: str
    texte: str
    instant: float | None  # le PREMIER instant connu, si l'agent est exposé plusieurs fois


def instant_exposition(evenement: dict) -> float | None:
    """`timestamp`, sinon `horodatage_simule` lu en UTC — la convention des `sim_ts`."""
    instant = _instant(evenement.get("timestamp"))
    if instant is not None:
        return instant
    quand = horodatage_iso(evenement.get("horodatage_simule"))
    if quand is None:
        return None
    if quand.tzinfo is None:
        quand = quand.replace(tzinfo=timezone.utc)
    return quand.timestamp()


def expositions_du_run(evenements: list[dict]) -> dict[str, Exposition]:
    """`{person_id: Exposition}`. Un agent sans texte n'est pas exposé : rien à chercher."""
    par_agent: dict[str, Exposition] = {}
    for e in evenements:
        pid = str(e.get("person_id") or "")
        texte = str(e.get("texte") or e.get("vecu") or "")
        if not pid or not texte:
            continue
        instant = instant_exposition(e)
        avant = par_agent.get(pid)
        if avant is not None:
            connus = [t for t in (avant.instant, instant) if t is not None]
            par_agent[pid] = avant._replace(instant=min(connus) if connus else None)
            continue
        par_agent[pid] = Exposition(str(e.get("canal") or ""), texte, instant)
    return par_agent


# ── Le prompt : contenu brut, sections, blocs, zone de rappel ────────────────────


def _contenu(echange: dict) -> str:
    """Le texte envoyé au modèle, tel quel : les `content` des messages, bout à bout.

    Jamais `json.dumps(messages)` : la sérialisation échappe sauts de ligne et guillemets, et
    le début d'un article (« (Translated from French)\\nGusts… ») n'y était jamais retrouvé.
    Une chaîne nue est prise telle quelle.
    """
    messages = echange.get("messages")
    if isinstance(messages, str):
        return messages
    return "\n".join(
        str(m.get("content") or "") for m in messages or [] if isinstance(m, dict)
    )


class Section(NamedTuple):
    agent: str
    depart: str | None  # « HH:MM », l'heure de départ que pose l'en-tête
    texte: str


def sections(contenu: str) -> list[Section]:
    """Une section par persona, de son en-tête `--- agent_id=` au suivant.

    ⚠ C'est la SEULE attribution fiable, et elle est indispensable pour le canal `lu` : tous
    les lecteurs d'un même article partagent le même texte, chercher le texte seul ne dirait
    pas qui l'a vu. L'identifiant se lit en entier : `agent_id=286920` n'est pas
    `agent_id=2869201`, que la recherche d'une sous-chaîne confondait.
    """
    entetes = list(_ENTETE_AGENT.finditer(contenu))
    decoupe: list[Section] = []
    for i, entete in enumerate(entetes):
        fin = entetes[i + 1].start() if i + 1 < len(entetes) else len(contenu)
        depart = _DEPART.search(entete.group("reste"))
        decoupe.append(Section(
            agent=entete.group("agent"),
            depart=f"{int(depart['heure']):02d}:{depart['minute']}" if depart else None,
            texte=contenu[entete.start():fin],
        ))
    return decoupe


def zone_rappel(section: str) -> str:
    """Les souvenirs rappelés : de la première ligne datée ou `[Concept]` à la fin de la section."""
    debut = _LIGNE_RAPPEL.search(section)
    return section[debut.start():] if debut else ""


def _bloc(section: str, voie: str) -> str:
    """Le contenu du bloc nommé, dans la section d'un agent. Chaîne vide s'il n'y figure pas.

    Le bloc s'arrête au prochain en-tête connu, et en tout cas avant le premier souvenir
    rappelé : sans cette borne, le dernier bloc avalait les souvenirs du rappel, et un souvenir
    rappelé portant le texte était imputé à « Ce que je sais ».
    """
    rappel = _LIGNE_RAPPEL.search(section)
    noyau = section[: rappel.start()] if rappel else section
    debut = noyau.find(EN_TETES[voie])
    if debut < 0:
        return ""
    reste = noyau[debut + len(EN_TETES[voie]):]
    fins = [i for i in (reste.find(t) for t in EN_TETES.values()) if i > 0]
    return reste[: min(fins)] if fins else reste


def _voies_textuelles(section: str, texte: str) -> list[tuple[str, str]]:
    """`[(voie, « exact » | « saillant »)]` pour les trois blocs du noyau."""
    signature = _signature(texte)
    saillants = mots_saillants(texte)
    trouvees: list[tuple[str, str]] = []
    for voie in ("habitudes", "connaissances", "changements"):
        bloc = _bloc(section, voie)
        if not bloc:
            continue
        if signature and signature in _norm(bloc):
            trouvees.append((voie, "exact"))
        elif saillants and sum(m in bloc.lower() for m in saillants) >= 2:
            trouvees.append((voie, "saillant"))
    return trouvees


# ── Le rappel : le souvenir de l'événement, la trace, le prompt ──────────────────


class Souvenir(NamedTuple):
    doc_id: str
    lien: str  # « exact » ou « saillant »
    memory_type: str
    enonce: str  # ce que le prompt en montre : le texte, ou l'énoncé du concept


def souvenirs_de_l_evenement(entrees: list[EntreeLTM], exposition: Exposition) -> list[Souvenir]:
    """Les entrées de mémoire longue nées de l'événement, et la force du lien.

    - **exact** — l'entrée contient le texte de l'événement. C'est le cas du `lu`, déposé tel
      quel : `[ PRESSE ] This morning I read in the paper: « … »`.
    - **saillant** — datée du jour de l'exposition ou après, elle porte au moins deux mots
      saillants du texte. C'est le cas du vécu, que la réflexion REFORMULE. Indicatif.

    Aucun identifiant ne relie une entrée à l'événement : `agent_memory_events.jsonl` marque
    l'écriture (`data.evenement`) sans le `doc_id`, et un concept tiré du souvenir par la
    consolidation n'est marqué nulle part.
    """
    signature = _signature(exposition.texte)
    saillants = mots_saillants(exposition.texte)
    jour = _jour_et_heure(exposition.instant)[0] if exposition.instant is not None else ""
    lies: list[Souvenir] = []
    for e in entrees:
        if not e.doc_id:
            continue
        if signature and signature in _norm(e.contenu):
            lien = "exact"
        elif (jour and e.timestamp[:10] >= jour and saillants
              and sum(m in e.contenu.lower() for m in saillants) >= 2):
            lien = "saillant"
        else:
            continue
        lies.append(Souvenir(e.doc_id, lien, e.memory_type, e.enonce))
    return lies


def traces_par_depart(rappels: list[dict]) -> dict[tuple[str, str, str], list[frozenset[str]]]:
    """`{(agent, jour, « HH:MM »): [doc_ids servis, …]}`, depuis `trace_rappel.jsonl`.

    La trace est datée de l'instant de la requête, qui est l'heure de départ de l'agent — et
    non le `sim_ts` de l'échange, qui est celui du lot. Sur le run 2026-09-24_17_50,
    l'appariement par `sim_ts` manquait 43 sections sur 140 ; celui par l'heure de départ en
    manque 29, qui n'ont aucune trace à cette heure-là.
    """
    index: dict[tuple[str, str, str], list[frozenset[str]]] = defaultdict(list)
    for r in rappels:
        instant = _instant(r.get("sim_ts"))
        if instant is None:
            continue
        jour, heure = _jour_et_heure(instant)
        index[(str(r.get("person_id") or ""), jour, heure)].append(frozenset(
            str(s["doc_id"]) for s in r.get("servis") or []
            if isinstance(s, dict) and s.get("doc_id")
        ))
    return index


def _dans(enonce: str, zone_normalisee: str) -> bool:
    debut = _norm(enonce)[:_ENONCE]
    return bool(debut) and debut in zone_normalisee


def depouiller(run: Path) -> dict:
    evenements = evenements_du_run(run)
    if not evenements:
        raise SystemExit(
            f"❌ ni `evenements.jsonl` ni `chocs.jsonl` dans {run} : aucun événement n'a été "
            f"appliqué. Ce n'est pas un résultat nul, c'est un run sans événement."
        )
    # Ticket 111 : dans un foyer où le lecteur a parlé, le co-résident informé et celui à qui
    # rien n'a été dit ne se mêlent pas — `relais_foyer.jsonl` fait foi.
    informes = informes_du_run(run)
    roles = {pid: sous_role(r, pid, informes) for pid, r in roles_du_run(run).items()}
    expositions = expositions_du_run(evenements)

    # Les décisions, lues dans les échanges LLM. Seules celles de la catégorie de décision
    # comptent : une réflexion nocturne n'est pas une décision. Le lecteur est celui du rapport
    # de mémoire : le fichier n'est pas du JSONL (cf. `_jsonl`).
    echanges = lire_echanges(run)
    rappels = _jsonl(run / "trace_rappel.jsonl")
    traces = traces_par_depart(rappels)
    memoire, _habitudes = lire_ltm(run)
    souvenirs = {
        pid: souvenirs_de_l_evenement(memoire.get(pid, []), expo)
        for pid, expo in expositions.items()
    }

    compte: dict[tuple[str, str, str], Counter] = defaultdict(Counter)
    decisions: Counter = Counter()
    # Par ligne du tableau : ce qui rend le rappel mesurable, ou non. Sans ces compteurs, une
    # cellule vide ne dirait pas si la trace manquait, ou le souvenir, ou s'il n'a pas été servi.
    rappel: dict[tuple[str, str], Counter] = defaultdict(Counter)
    souvenirs_par_ligne: dict[tuple[str, str], set[Souvenir]] = defaultdict(set)
    ecartees: Counter = Counter()
    decisions_lues = 0
    lues_exposes = 0
    traces_appariees: set[tuple[str, str, str]] = set()

    for echange in echanges:
        if str(echange.get("category") or "") != CATEGORIE_DECISION:
            continue
        decisions_lues += 1
        instant = _instant(echange.get("sim_ts"))
        for section in sections(_contenu(echange)):
            expo = expositions.get(section.agent)
            if expo is None:
                continue
            lues_exposes += 1
            # Une décision ne voit l'événement que si elle le suit. Le réveil précède la
            # lecture : une décision prise À l'instant de l'exposition ne l'a pas vue.
            if instant is None or expo.instant is None:
                ecartees["non_datees"] += 1
                continue
            if instant <= expo.instant:
                ecartees["anterieures"] += 1
                continue
            cle_base = (expo.canal, roles.get(section.agent, ""))
            decisions[cle_base] += 1
            for voie, qualite in _voies_textuelles(section.texte, expo.texte):
                compte[(*cle_base, voie)][qualite] += 1

            # Le rappel : le souvenir NÉ DE L'ÉVÉNEMENT, servi pour CETTE décision, et
            # présent dans son prompt. Servi ne suffit pas : la trace liste le top-K, le prompt
            # n'en reçoit que les plus récents, et jamais une entrée `conversation`.
            lies = souvenirs.get(section.agent) or []
            suivi = rappel[cle_base]
            if not lies:
                suivi["sans_souvenir"] += 1
                continue
            souvenirs_par_ligne[cle_base].update(lies)
            jour = str(echange.get("sim_day") or "") or _jour_et_heure(instant)[0]
            cle_trace = (section.agent, jour, section.depart or "")
            candidates = set(traces.get(cle_trace, ())) if section.depart else set()
            if not candidates:
                suivi["sans_trace"] += 1
                continue
            traces_appariees.add(cle_trace)
            if len(candidates) > 1:
                # Deux traces à la même minute qui ne servent pas la même chose : laquelle
                # était celle de cette décision, rien ne le dit.
                suivi["ambigu"] += 1
                continue
            servis = next(iter(candidates))
            suivi["mesurables"] += 1
            if any(s.lien == "exact" for s in lies):
                suivi["mesurables_exact"] += 1
            zone = _norm(zone_rappel(section.texte))
            vus = [s for s in lies if s.doc_id in servis and _dans(s.enonce, zone)]
            if vus:
                meilleur = "exact" if any(s.lien == "exact" for s in vus) else "saillant"
                compte[(*cle_base, "rappel")][meilleur] += 1
            elif any(s.doc_id in servis for s in lies):
                suivi["hors_prompt"] += 1
            if any(s.doc_id not in servis and _dans(s.enonce, zone) for s in lies):
                suivi["hors_trace"] += 1

    # Les rappels du souvenir de l'événement qu'aucune décision lue ne réclame : la trace
    # existe, le prompt non — décision servie par le cache, ou non journalisée.
    rappels_sans_decision: list[tuple[str, str, str]] = []
    for (pid, jour, heure), listes in sorted(traces.items()):
        docs = {s.doc_id for s in souvenirs.get(pid) or []}
        if not docs or (pid, jour, heure) in traces_appariees:
            continue
        for doc in sorted(docs & frozenset().union(*listes)):
            rappels_sans_decision.append((pid, f"{jour} {heure}", doc))

    return {"compte": compte, "decisions": decisions, "evenements": len(evenements),
            "roles_connus": bool(roles), "echanges": len(echanges),
            "decisions_lues": decisions_lues, "lues_exposes": lues_exposes,
            "ecartees": ecartees, "rappel": rappel, "traces_lues": len(rappels),
            "souvenirs": {k: sorted(v) for k, v in souvenirs_par_ligne.items()},
            "rappels_sans_decision": rappels_sans_decision}


def _lu(resultat: dict) -> str:
    """Ce qui a été lu. Un tableau sans son effectif ne se distingue pas d'un tableau vide."""
    n, d = resultat["echanges"], resultat["decisions_lues"]
    return (f"Lu : {n} échange{'s' * (n > 1)}, dont {d} décision{'s' * (d > 1)} "
            f"(`{CATEGORIE_DECISION}`), pour {resultat['evenements']} exposition(s).")


def _retenues(resultat: dict) -> str:
    """Les décisions des agents exposés, celles qui comptent et celles qui ne peuvent pas."""
    ecartees = resultat["ecartees"]
    return (
        f"Décisions des agents exposés : {resultat['lues_exposes']} lue(s), "
        f"{sum(resultat['decisions'].values())} postérieure(s) à l'exposition retenue(s), "
        f"{ecartees['anterieures']} antérieure(s) et {ecartees['non_datees']} non datée(s) "
        f"écartée(s)."
    )


def _suivi_rappel(resultat: dict) -> list[str]:
    """Ce qui a rendu le rappel mesurable, ligne par ligne. Une cellule vide s'y explique."""
    lignes: list[str] = []
    if not resultat["traces_lues"]:
        lignes.append("⚠ `trace_rappel.jsonl` absent ou vide (`agent.trace_rappel_enabled` "
                      "était-il actif ?) : le rappel ne se mesure pas.")
    for cle in sorted(resultat["decisions"]):
        canal, role = cle
        nom = f"{canal or '?'}/{role or '?'}"
        suivi = resultat["rappel"].get(cle) or Counter()
        lies = resultat["souvenirs"].get(cle) or []
        if not lies:
            lignes.append(f"Rappel ({nom}) : aucun souvenir de l'événement identifié en mémoire "
                          f"longue — voie non mesurable.")
            continue
        noms = ", ".join(f"{s.doc_id} ({s.lien}, {s.memory_type or '?'})" for s in lies[:5])
        noms += " …" if len(lies) > 5 else ""
        details = [
            f"souvenir(s) de l'événement : {noms}",
            f"servi au top-K sans atteindre le prompt : {suivi['hors_prompt']}",
            f"sans trace de rappel appariée : {suivi['sans_trace']}",
        ]
        if suivi["ambigu"]:
            details.append(f"trace ambiguë : {suivi['ambigu']}")
        if suivi["sans_souvenir"]:
            details.append(f"agent sans souvenir identifié : {suivi['sans_souvenir']}")
        lignes.append(f"Rappel ({nom}) : mesurable sur {suivi['mesurables']} des "
                      f"{resultat['decisions'][cle]} décision(s) — " + " ; ".join(details) + ".")
        if suivi["hors_trace"]:
            lignes.append(
                f"⚠ [INCOHÉRENCE] {suivi['hors_trace']} décision(s) ({nom}) portent un souvenir "
                f"de l'événement dans la zone de rappel sans que la trace ne le liste : la trace "
                f"ou le découpage du prompt est faux."
            )
    sans = resultat["rappels_sans_decision"]
    if sans:
        detail = ", ".join(f"{pid} le {quand} ({doc})" for pid, quand, doc in sans[:5])
        detail += " …" if len(sans) > 5 else ""
        lignes.append(
            f"⚠ {len(sans)} rappel(s) d'un souvenir de l'événement sans décision lue : {detail}. "
            f"Servi pour un départ dont le prompt n'est pas dans `llm_exchanges.jsonl` "
            f"(décision servie par le cache, ou non journalisée) — non compté."
        )
    return lignes


def rendre(resultat: dict, markdown: bool = False) -> str:
    compte, decisions = resultat["compte"], resultat["decisions"]
    lignes: list[str] = []
    if not resultat["echanges"]:
        # Rien lu n'est pas « rien trouvé » : sans prompt, aucune décision n'a pu être examinée.
        return (
            "non concluant — aucun échange lu dans `llm_exchanges.jsonl` (absent, vide ou "
            "illisible : `telemetry.exchanges_enabled` était-il actif ?).\n"
            "Ce n'est PAS « l'événement n'a pesé sur rien » : aucune décision n'a été lue.\n"
            + _lu(resultat)
        )
    if not decisions and resultat["lues_exposes"]:
        # Des décisions de l'agent exposé, mais aucune qui ait pu voir l'événement.
        return (
            "non concluant — aucune décision postérieure à l'exposition.\n"
            "Ce n'est PAS « l'événement n'a pesé sur rien » : aucune décision retenue ne suit "
            "l'exposition, ou aucune ne se date.\n"
            + _retenues(resultat) + "\n" + _lu(resultat)
        )
    if not decisions:
        return (
            "non concluant — aucune décision ne porte le texte de l'événement.\n"
            "Ce n'est PAS « l'événement n'a pesé sur rien » : l'appariement par le texte échoue "
            "pour le régime vécu, la réflexion reformule le vécu avant qu'il n'atteigne la "
            "mémoire longue (mesuré le 2026-09-16). Il faudrait un lien explicite posé à la "
            "source, et il n'existe pas.\n" + _lu(resultat)
        )
    sep = "|" if markdown else " "
    lignes.append(f"{'canal':<8}{sep}{'rôle':<14}{sep}{'décisions':>9}{sep}"
                  + sep.join(f"{v:>14}" for v in VOIES))
    if markdown:
        lignes.append("|".join(["---"] * (3 + len(VOIES))))
    for (canal, role), total in sorted(decisions.items()):
        cellules = []
        for voie in VOIES:
            c = compte.get((canal, role, voie)) or Counter()
            exact, saillant = c.get("exact", 0), c.get("saillant", 0)
            if not exact and not saillant:
                mesure = (resultat["rappel"].get((canal, role)) or Counter())["mesurables_exact"]
                # `0` au rappel seulement, et seulement MESURÉ : souvenir lié exactement, trace
                # appariée, jamais servi. Partout ailleurs, VIDE, jamais zéro.
                cellules.append(f"{0:>14}" if voie == "rappel" and mesure else f"{'':>14}")
            elif saillant and not exact:
                cellules.append(f"{f'~{saillant}':>14}")
            elif saillant:
                cellules.append(f"{f'{exact} (~{saillant})':>14}")
            else:
                cellules.append(f"{exact:>14}")
        lignes.append(f"{canal or '?':<8}{sep}{role or '?':<14}{sep}{total:>9}{sep}"
                      + sep.join(cellules))
    # Les décisions où AUCUNE voie n'a été trouvée. Comptées et nommées, parce qu'une ligne
    # de cellules vides se lit trop facilement comme « l'événement n'a pesé sur rien ».
    muettes = sum(
        total for (canal, role), total in decisions.items()
        if not any((compte.get((canal, role, v)) or Counter()) for v in VOIES)
    )
    lignes.append("")
    lignes.append("`~` = appariement par mots saillants, INDICATIF. Une cellule vide n'est pas "
                  "un zéro : c'est une absence de mesure. Un `0` ne sort qu'au rappel, mesuré : "
                  "souvenir de l'événement identifié tel quel, trace appariée, jamais servi.")
    if muettes:
        lignes.append(
            f"⚠ {muettes} décision(s) où l'événement n'a été retrouvé par AUCUNE voie. Ce n'est "
            f"PAS « l'événement n'a pesé sur rien » : l'appariement par le texte échoue pour le "
            f"régime vécu, la réflexion reformulant le vécu avant qu'il n'atteigne la mémoire "
            f"longue (mesuré le 2026-09-16). Il faudrait un lien explicite posé à la source, et "
            f"il n'existe pas."
        )
    lignes.extend(_suivi_rappel(resultat))
    if not resultat["roles_connus"]:
        lignes.append("⚠ `moves.csv` ne porte pas la colonne « Rôle » : run antérieur au ticket "
                      "100, lot 5. Les rôles ne se reconstituent pas après coup.")
    lignes.append(_retenues(resultat))
    lignes.append(_lu(resultat))
    return "\n".join(lignes)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    p.add_argument("--markdown", action="store_true")
    args = p.parse_args()
    print(rendre(depouiller(args.run), args.markdown))
    return 0


if __name__ == "__main__":
    sys.exit(main())
