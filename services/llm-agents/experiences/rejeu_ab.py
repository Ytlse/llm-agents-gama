"""Bilan du rejeu à prompt exact d'un A/B mémoire : le témoin a-t-il bien rejoué le traité ?

Le rejeu (`llm_gateway/core/rejeu_ab.py`) ressert au témoin la réponse que le traité a reçue,
tant que le prompt est le même mot pour mot. Avant l'événement, rien ne sépare les deux bras :
chaque appel du témoin devrait donc être servi par rejeu. Un appel payé avant l'événement dit
que les bras ont divergé pour une autre raison que lui — et c'est ce que ce bilan fait voir.

Lecture seule : le journal des échanges du témoin, et la date de la première injection lue
dans les événements du traité.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

PREFIXE_REJEU = "rejeu_ab:"


def lire_echanges(chemin: Path) -> list[dict]:
    """`llm_exchanges.jsonl` est une suite d'objets JSON indentés, pas un objet par ligne."""
    texte = chemin.read_text(encoding="utf-8")
    dec, i, out = json.JSONDecoder(), 0, []
    while True:
        while i < len(texte) and texte[i] in " \n\r\t":
            i += 1
        if i >= len(texte):
            return out
        obj, i = dec.raw_decode(texte, i)
        out.append(obj)


def date_premiere_injection(evenements: Path) -> str | None:
    """Jour simulé (AAAA-MM-JJ) de la première injection du traité, None s'il n'y en a pas."""
    if not evenements.is_file():
        return None
    dates = []
    for ligne in evenements.read_text(encoding="utf-8").splitlines():
        try:
            h = json.loads(ligne).get("horodatage_simule")
        except ValueError:
            continue
        if h:
            dates.append(str(h)[:10])
    return min(dates) if dates else None


def bilan(echanges: list[dict], date_evenement: str | None) -> dict[str, Any]:
    """Appels du témoin servis par rejeu ou payés, par catégorie, et ceux payés AVANT l'événement.

    Un échange sans jour simulé (catégorie sans horodatage de priorité) compte dans les totaux,
    pas dans « avant » : on ne peut pas le dater, on ne l'accuse pas.
    """
    par_categorie: dict[str, dict[str, int]] = defaultdict(
        lambda: {"servis": 0, "payes": 0}
    )
    payes_avant: list[dict[str, Any]] = []
    for e in echanges:
        cat = str(e.get("category") or "?")
        rejoue = str(e.get("provider") or "").startswith(PREFIXE_REJEU)
        par_categorie[cat]["servis" if rejoue else "payes"] += 1
        jour = e.get("sim_day")
        if not rejoue and date_evenement and jour and jour < date_evenement:
            payes_avant.append(
                {
                    "categorie": cat,
                    "jour": jour,
                    "agents": sorted(
                        str(r.get("agent_id", ""))
                        for r in e.get("response") or []
                        if isinstance(r, dict)
                    ),
                }
            )
    servis = sum(c["servis"] for c in par_categorie.values())
    payes = sum(c["payes"] for c in par_categorie.values())
    return {
        "date_evenement": date_evenement,
        "servis": servis,
        "payes": payes,
        "part_servie": round(servis / (servis + payes), 4) if servis + payes else None,
        "par_categorie": dict(par_categorie),
        "payes_avant_evenement": len(payes_avant),
        "premiers_payes_avant": sorted(payes_avant, key=lambda p: p["jour"])[:10],
    }


__all__ = ["PREFIXE_REJEU", "bilan", "date_premiere_injection", "lire_echanges"]
