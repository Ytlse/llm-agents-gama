"""Le ticket qui porte chaque expérience — recalculé, jamais recopié.

L'association n'existe nulle part comme donnée : elle est écrite dans les tickets (qui citent
des noms d'expériences) et dans les campagnes (dont l'en-tête nomme leur ticket). La recopier
dans un fichier de correspondance, ou dans les `experience.yaml`, créerait un second endroit à
tenir à jour — et donc, tôt ou tard, un ticket affiché à côté d'une expérience qu'il ne porte
plus. On la relit.

**Trois sources, dans cet ordre de priorité.** Une expérience citée nommément par un ticket
l'emporte sur son appartenance à une campagne, qui l'emporte sur une déduction :

1. `cite` — un ticket écrit le nom EXACT de l'expérience ;
2. `campagne` — l'expérience figure dans une campagne dont l'en-tête nomme un ticket ;
3. `deduit` — un segment du nom désigne un dispositif qu'un ticket décrit, et un seul.

**Et rien d'autre.** Une expérience qu'aucune de ces trois sources n'atteint rend une chaîne
vide. Remplir au jugé — « ce bras ressemble à ceux du ticket 088, mettons 088 » — produirait
une colonne qu'on ne peut plus croire, donc qu'on ne lit plus. Sur les 81 expériences du
2026-09-21, 35 restent vides, et c'est le bon résultat.

Les déductions sont volontairement peu nombreuses et chacune s'appuie sur un texte :

- `go123_gt123_gc123` et ses sœurs 456, 789, 2026 → ticket 073, dont l'axe 1 liste exactement
  ces quatre graines ;
- un nom en `_2` dont l'aîné existe → ticket 073, axe 0 (le réplicat à l'identique) ;
- un substrat `enquete_058` / `jeu-58_test` → ticket 058, qui donne son numéro au substrat.

Le coût est réel — 93 tickets et les campagnes à relire — et le registre se redessine toutes
les cinq secondes tant qu'une exécution tourne. D'où le cache, invalidé par la date de
modification des deux dossiers : c'est le même souci que la note de `_etat_jeu` dans
`experiences.py`, où une lecture naïve faisait deux cent quarante relectures par battement.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Iterable, Optional

import yaml

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
TICKETS_DIR = REPO_ROOT / "docs" / "tickets"
CAMPAGNES_DIR = REPO_ROOT / "campagnes"

# Les quatre graines de l'axe 1 du ticket 073. Écrites ici parce que le nom d'expérience les
# porte en clair (`go456_gt456_gc456`) : ce n'est pas une heuristique, c'est une liste.
GRAINES_073 = ("123", "456", "789", "2026")

# L'en-tête d'une campagne nomme son ticket dans ses premières lignes de commentaire.
LIGNES_ENTETE_CAMPAGNE = 12
_RE_TICKET_ENTETE = re.compile(r"[Tt]icket (\d{2,3})")
_RE_NUM_TICKET = re.compile(r"ticket_(\d{3})")

# (empreinte des dossiers, noms demandés) -> correspondance. Un seul jeu conservé : le registre
# redemande toujours la même liste, et garder l'historique ne servirait qu'à occuper la mémoire.
_CACHE: dict[tuple, dict[str, str]] = {}


def _empreinte() -> tuple:
    """Ce qui doit changer pour que la correspondance soit recalculée.

    La date de modification des deux dossiers suffit : créer, supprimer ou réécrire un fichier
    la déplace. Un dossier absent compte comme une empreinte à part entière — sinon le premier
    `campagnes/` créé passerait inaperçu.
    """
    def m(d: Path) -> float:
        try:
            return d.stat().st_mtime
        except OSError:
            return -1.0

    return (m(TICKETS_DIR), m(CAMPAGNES_DIR))


def _citations(noms: tuple[str, ...]) -> dict[str, set[str]]:
    """Les tickets qui écrivent le nom exact d'une expérience."""
    trouve: dict[str, set[str]] = {}
    for chemin in sorted(TICKETS_DIR.glob("ticket_*.md")):
        m = _RE_NUM_TICKET.search(chemin.name)
        if not m:
            continue
        try:
            txt = chemin.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            logger.warning(f"[ticket-exp] {chemin.name} illisible ({exc}) — ignoré")
            continue
        for nom in noms:
            if nom in txt:
                trouve.setdefault(nom, set()).add(m.group(1))
    return trouve


def _campagnes() -> dict[str, set[str]]:
    """Les expériences listées par une campagne dont l'en-tête nomme un ticket."""
    trouve: dict[str, set[str]] = {}
    if not CAMPAGNES_DIR.is_dir():
        return trouve
    for chemin in sorted(CAMPAGNES_DIR.glob("*.yaml")):
        try:
            brut = chemin.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            logger.warning(f"[ticket-exp] {chemin.name} illisible ({exc}) — ignoré")
            continue
        entete = "\n".join(brut.splitlines()[:LIGNES_ENTETE_CAMPAGNE])
        m = _RE_TICKET_ENTETE.search(entete)
        if not m:
            continue
        numero = m.group(1).zfill(3)
        try:
            doc = yaml.safe_load(brut) or {}
        except yaml.YAMLError as exc:
            logger.warning(f"[ticket-exp] {chemin.name} illisible en YAML ({exc}) — ignoré")
            continue
        for phase in doc.get("phases") or []:
            for nom in (phase or {}).get("experiences") or []:
                trouve.setdefault(str(nom), set()).add(numero)
    return trouve


def _deduction(nom: str, connus: frozenset[str]) -> Optional[str]:
    """Le ticket qu'un segment du nom désigne sans ambiguïté, ou None."""
    if any(f"_go{g}_gt{g}_gc{g}_" in nom for g in GRAINES_073):
        return "073"
    if nom.endswith("_2") and nom[:-2] in connus:
        return "073"
    if "enquete_058" in nom or "jeu-58_test" in nom:
        return "058"
    return None


def ticket_par_experience(noms: Iterable[str]) -> dict[str, str]:
    """`nom d'expérience -> numéro de ticket`, vide quand aucune source ne l'atteint.

    Plusieurs tickets pour une même expérience : ils sont rendus séparés par une virgule, dans
    l'ordre croissant. Cela arrive et n'est pas une anomalie — le ticket 073 s'appuie sur un
    bras que le ticket 088 a rejoué.
    """
    cles = tuple(sorted(set(noms)))
    if not cles:
        return {}
    empreinte = (_empreinte(), cles)
    en_cache = _CACHE.get(empreinte)
    if en_cache is not None:
        return dict(en_cache)

    debut = time.monotonic()
    cite = _citations(cles)
    camp = _campagnes()
    connus = frozenset(cles)

    resultat: dict[str, str] = {}
    compte = {"cite": 0, "campagne": 0, "deduit": 0, "vide": 0}
    for nom in cles:
        if cite.get(nom):
            resultat[nom] = ",".join(sorted(cite[nom]))
            compte["cite"] += 1
        elif camp.get(nom):
            resultat[nom] = ",".join(sorted(camp[nom]))
            compte["campagne"] += 1
        else:
            d = _deduction(nom, connus)
            resultat[nom] = d or ""
            compte["deduit" if d else "vide"] += 1

    _CACHE.clear()
    _CACHE[empreinte] = dict(resultat)
    logger.info(
        f"[ticket-exp] {len(cles)} expérience(s) rapprochée(s) en "
        f"{time.monotonic() - debut:.2f} s — cité {compte['cite']}, campagne "
        f"{compte['campagne']}, déduit {compte['deduit']}, sans ticket {compte['vide']}"
    )
    return dict(resultat)
