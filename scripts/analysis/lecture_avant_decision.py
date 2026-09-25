"""La lecture précède-t-elle la décision ? — ticket 111, lot 6.

Le 2026-09-25, le bras traité a09 `2026-09-24_17_50` a montré qu'un article lu au réveil
n'était devant le modèle NI à la décision du lecteur le jour de lecture — pré-calculée la veille —
NI les jours suivants, faute d'une gravité jugée assez haute. Rien ne le disait : il a fallu
relire les prompts un par un.

Ce contrôle relit `llm_exchanges.jsonl` et dit, décision par décision, si la ligne garantie était
là pendant les jours de service : `[ PRESSE ]` pour le lecteur, `[ FOYER ]` pour un membre
informé. Il rend les SUCCÈS aussi : un contrôle dont on ne voit que les échecs ne distingue pas
« tout va bien » de « il ne tourne plus ».

Exact, sans heuristique : le préfixe est rendu mot pour mot au prompt. Chaque message
utilisateur est découpé par `--- agent_id=<id> | … ---` et seul le bloc de la personne concernée
est testé — un prompt fusionné porte plusieurs agents, et la ligne du lecteur n'appartient pas à
son co-résident (ticket 110, § 3).

Usage :
    python scripts/analysis/lecture_avant_decision.py experiments/archive/2026-09-24_17_50
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

# « This morning » a disparu de la ligne le 2026-09-25 : les archives d'avant le portent encore.
MARQUE_LECTURE = re.compile(r"\[ PRESSE \] (?:This morning )?I read in the paper:")
MARQUE_FOYER = re.compile(re.escape("[ FOYER ]"))
# Défaut du ticket 111 quand la déclaration archivée ne porte pas encore `service` (runs d'avant
# le ticket) : c'est ce qui permet de rejouer le contrôle sur l'archive du défaut.
JOURS_PAR_DEFAUT = 5
CATEGORIE_DECISION = "itinary_multi_agent"
_ENTETE = re.compile(r"^--- agent_id=(\S+) \|.*---\s*$", re.M)
_DEPART = re.compile(r"Departure: (\d{1,2}):(\d{2})")


@dataclass
class Jour:
    jour: date
    decisions: int = 0
    avec_ligne: int = 0


@dataclass
class Constat:
    """Ce qu'une personne a vu pendant ses jours de service."""

    person_id: str
    role: str                    # « lecteur », « informé », « non informé »
    date_lecture: date
    jours: list[Jour] = field(default_factory=list)
    message: str = ""
    mineur: bool = False
    modes_choisis: list[str] = field(default_factory=list)
    # La PREMIÈRE décision du jour 1 portait-elle la ligne ? `None` sans décision ce jour-là.
    premiere: bool | None = None

    @property
    def attend_ligne(self) -> bool:
        return self.role != "non informé"

    @property
    def privees(self) -> int:
        """Décisions d'un jour de service SANS la ligne (ou AVEC, pour un non-informé)."""
        if self.attend_ligne:
            return sum(j.decisions - j.avec_ligne for j in self.jours)
        return sum(j.avec_ligne for j in self.jours)

    @property
    def verdict(self) -> str:
        if not any(j.decisions for j in self.jours):
            return "⚪"
        if self.attend_ligne and self.premiere is False:
            return "🔴"
        return "🔴" if self.privees else "✅"


# ── Lecture du run ──────────────────────────────────────────────────────────────────────────
def iter_json_concat(chemin: Path):
    """Objets JSON concaténés et indentés — `llm_exchanges.jsonl` n'est pas du JSONL."""
    tampon = ""
    with chemin.open(encoding="utf-8") as f:
        for ligne in f:
            tampon += ligne
            try:
                yield json.loads(tampon)
                tampon = ""
            except json.JSONDecodeError:
                continue


def _jsonl(chemin: Path) -> list[dict]:
    if not chemin.is_file():
        return []
    sortie = []
    for brute in chemin.read_text(encoding="utf-8").splitlines():
        if brute.strip():
            try:
                sortie.append(json.loads(brute))
            except json.JSONDecodeError:
                continue
    return sortie


def _declaration(run: Path) -> dict:
    chemin = run / "evenement.yaml"
    if not chemin.is_file():
        return {}
    return yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}


def _sans_week_end(run: Path) -> bool:
    chemin = run / "static_config.yaml"
    if not chemin.is_file():
        return True
    brut = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    return bool((brut.get("agent") or {}).get("no_weekend_departures", True))


def jours_de_service(debut: date, n: int, sans_week_end: bool) -> list[date]:
    """Même règle que `llm/evenements/calendrier.jours_de_service`, recopiée pour rester autonome."""
    jours, courant = [], debut
    while len(jours) < n:
        if not (sans_week_end and courant.weekday() >= 5):
            jours.append(courant)
        courant += timedelta(days=1)
    return jours


def jour_du_trajet(sim_ts: float, entete: str, sans_week_end: bool) -> date:
    """Le jour du trajet décidé dans un bloc de prompt.

    ⚠ `sim_ts` n'est PAS le départ de l'agent : le worker y écrit le plus petit départ du LOT
    (`rejeu_decisions.py`), et un lot mêle des trajets de deux jours. L'en-tête du bloc ne porte
    que l'heure (`Departure: 05:57`). Le départ est donc le premier instant à cette heure qui ne
    précède pas `sim_ts`, reporté au lundi sous `no_weekend_departures` comme le calendrier le
    fait. Sans heure lisible, on retombe sur le jour de `sim_ts`.
    """
    debut = datetime.fromtimestamp(float(sim_ts), timezone.utc)
    m = _DEPART.search(entete)
    if not m:
        return debut.date()
    depart = debut.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
    if depart < debut.replace(second=0, microsecond=0):
        depart += timedelta(days=1)
    jour = depart.date()
    while sans_week_end and jour.weekday() >= 5:
        jour += timedelta(days=1)
    return jour


def blocs_par_personne(
    run: Path, sans_week_end: bool = True
) -> dict[str, list[tuple[str, date, str]]]:
    """`{person_id: [(heure réelle, jour du trajet, bloc du prompt), …]}`, dans l'ordre réel."""
    chemin = run / "llm_exchanges.jsonl"
    blocs: dict[str, list[tuple[str, date, str]]] = defaultdict(list)
    if not chemin.is_file():
        return blocs
    for o in iter_json_concat(chemin):
        if o.get("category") != CATEGORIE_DECISION:
            continue
        try:
            sim_ts = float(o["sim_ts"])
        except (KeyError, TypeError, ValueError):
            continue
        for m in o.get("messages") or []:
            if m.get("role") != "user":
                continue
            texte = str(m.get("content") or "")
            entetes = list(_ENTETE.finditer(texte))
            for i, e in enumerate(entetes):
                fin = entetes[i + 1].start() if i + 1 < len(entetes) else len(texte)
                jour = jour_du_trajet(sim_ts, e.group(0), sans_week_end)
                blocs[e.group(1)].append((str(o.get("time") or ""), jour, texte[e.start():fin]))
    for liste in blocs.values():
        liste.sort(key=lambda t: t[0])
    return blocs


def _modes_choisis(run: Path, pid: str, jours: set[date]) -> list[str]:
    chemin = run / "moves.csv"
    if not chemin.is_file():
        return []
    modes = []
    with chemin.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("ID Personne") != pid:
                continue
            try:
                jour = datetime.fromtimestamp(float(row["Temps simulé"]), timezone.utc).date()
            except (KeyError, TypeError, ValueError):
                continue
            if jour in jours:
                modes.append(f"{jour:%d/%m} {row.get('Mode de transport Choisi', '?')}")
    return modes


# ── Les deux sous-rôles du co-résident ──────────────────────────────────────────────────────
def informes_du_run(run: Path | str) -> set[str] | None:
    """Les membres informés par le lecteur, lus dans `relais_foyer.jsonl`, qui fait foi.

    `None` quand le run n'a pas de relais : le co-résident reste alors un seul rôle. Un ensemble
    vide, lui, dit que le relais a eu lieu et que personne n'a été informé.
    """
    chemin = Path(run) / "relais_foyer.jsonl"
    if not chemin.is_file():
        return None
    return {
        str(m.get("destinataire_id"))
        for r in _jsonl(chemin) if not r.get("refus")
        for m in r.get("messages") or [] if m.get("parle")
    }


def sous_role(role: str, person_id: str, informes: set[str] | None) -> str:
    """`co_resident` → `co_resident_informe` / `co_resident_non_informe` quand un relais a eu lieu.

    La colonne `Rôle` de `moves.csv` ne change pas en cours de run (elle casserait les séries
    par rôle) : la distinction se fait ici, à la lecture.
    """
    if role != "co_resident" or informes is None:
        return role
    return "co_resident_informe" if str(person_id) in informes else "co_resident_non_informe"


# ── Le contrôle ─────────────────────────────────────────────────────────────────────────────
def controler(run_dir: Path | str) -> list[Constat]:
    """Un constat par lecteur, par membre informé et par membre non informé."""
    run = Path(run_dir)
    decl = _declaration(run)
    if str(decl.get("canal") or "") != "lu":
        return []
    n = int(((decl.get("service") or {}).get("jours_de_deplacement")) or JOURS_PAR_DEFAUT)
    sans_we = _sans_week_end(run)
    blocs = blocs_par_personne(run, sans_we)
    lignes = [l for l in _jsonl(run / "evenements.jsonl") if l.get("canal") == "lu"]

    constats: list[Constat] = []
    lecteurs: dict[str, date] = {}
    for l in lignes:
        pid = str(l.get("person_id"))
        quand = datetime.fromisoformat(str(l["horodatage_simule"])).date()
        role = "informé" if l.get("origine") == "entendu" else "lecteur"
        if role == "lecteur":
            lecteurs[pid] = quand
        constats.append(Constat(
            person_id=pid, role=role, date_lecture=quand,
            message=str(l.get("message") or ""), mineur=bool(l.get("mineur")),
        ))
    # Les non-informés : relus dans `relais_foyer.jsonl`, qui fait foi.
    for r in _jsonl(run / "relais_foyer.jsonl"):
        quand = lecteurs.get(str(r.get("lecteur_id")))
        if quand is None or r.get("refus"):
            continue
        for m in r.get("messages") or []:
            if not m.get("parle"):
                constats.append(Constat(
                    person_id=str(m.get("destinataire_id")), role="non informé",
                    date_lecture=quand, mineur=bool(m.get("mineur")),
                ))

    for c in constats:
        service = jours_de_service(c.date_lecture, n, sans_we)
        marque = MARQUE_LECTURE if c.role == "lecteur" else MARQUE_FOYER
        vus = blocs.get(c.person_id, [])
        for j in service:
            du_jour = [b for _, d, b in vus if d == j]
            c.jours.append(Jour(j, len(du_jour), sum(1 for b in du_jour if marque.search(b))))
            if j == service[0] and du_jour and c.attend_ligne:
                c.premiere = bool(marque.search(du_jour[0]))
        if c.mineur and c.role == "informé":
            c.modes_choisis = _modes_choisis(run, c.person_id, set(service))
    return constats


def rendre(constats: list[Constat]) -> list[str]:
    """Les lignes Markdown de la section — succès ET défauts."""
    out = [
        "| Agent | Rôle | Lecture | Jour 1 : 1re décision | Décisions servies / jours de service | Verdict |",
        "|:--|:--|:--|:--|:--|:--|",
    ]
    for c in constats:
        premiere = {True: "✅ ligne présente", False: "🔴 **sans la ligne**", None: "—"}[
            c.premiere
        ] if c.attend_ligne else "—"
        detail = " · ".join(
            f"{j.jour:%d/%m} {j.avec_ligne}/{j.decisions}" for j in c.jours
        )
        role = c.role + (" (mineur)" if c.mineur else "")
        out.append(
            f"| `{c.person_id}` | {role} | {c.date_lecture:%d/%m} | {premiere} | {detail} | "
            f"{c.verdict} |"
        )
    for c in constats:
        if c.mineur and c.role == "informé":
            out.append(
                f"\n- `{c.person_id}` (mineur) — décision parentale reçue : « {c.message} » ; "
                f"modes choisis pendant ses jours de service : "
                f"{', '.join(c.modes_choisis) or 'aucun déplacement'}. Pas de score de "
                f"conformité : l'enfant décide avec son propre appel."
            )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    constats = controler(args.run)
    if not constats:
        print(f"{args.run.name} : aucun événement `lu` à contrôler.")
        return 0
    print("\n".join(rendre(constats)))
    return 1 if any(c.verdict == "🔴" for c in constats) else 0


if __name__ == "__main__":
    raise SystemExit(main())
