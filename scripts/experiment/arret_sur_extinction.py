#!/usr/bin/env python3
"""Arrêt précoce d'un run une fois le choc éteint — ticket 095.

POURQUOI
--------
Le retour au comportement d'avant est acquis quelques jours après que le dernier souvenir de
choc a quitté le bloc « ce qui a changé récemment ». Les jours suivants sont payés et
n'apprennent rien. Sur la campagne du 2026-09-21, ils représentent environ 12 % du run.

CE QUI DÉCLENCHE
----------------
La ligne que le contrôleur écrit à l'instant exact de l'extinction, et rien d'autre :

    [noyau] <agent> : le souvenir de choc du <date> est sorti du bloc « ce qui a changé
    récemment » (…) — plus aucun souvenir de choc ne pèse sur ses décisions.

⚠ La queue « plus aucun souvenir de choc » est OBLIGATOIRE. Un souvenir qui sort alors que
d'autres restent servis ne termine rien : l'agent porte encore un choc dans son contexte.

⚠ Ne JAMAIS déclencher sur la stabilité d'une part modale. Sur cette même campagne, la
propension quotidienne vaut 5 % le 11 avril et 52 % le 13 : une bande étroite arrêterait le run
au gré du bruit. L'extinction est un événement daté, pas une statistique.

CE QUI EST COMPTÉ ENSUITE
-------------------------
Des jours VÉCUS, pas des jours calendaires : la simulation saute les week-ends, et compter en
calendaire retirerait deux jours d'observation sur sept.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

# La queue qui distingue « un souvenir est sorti » de « il n'en reste plus aucun ».
EXTINCTION = re.compile(
    r"est sorti du bloc .*plus aucun souvenir de choc ne pèse sur ses décisions"
)
# `sim_time=27 April 2026, 05:00` — la date simulée, pour compter les jours vécus.
SIM_TIME = re.compile(r"sim_time=(\d{2}) (\w+) (\d{4})")
MOIS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"])}


def date_simulee(ligne: str):
    """La date simulée portée par une ligne, ou None."""
    m = SIM_TIME.search(ligne)
    if not m:
        return None
    import datetime
    try:
        return datetime.date(int(m.group(3)), MOIS[m.group(2)], int(m.group(1)))
    except (KeyError, ValueError):
        return None


def analyser(lignes, souvenir_du: str | None = None) -> tuple[bool, int]:
    """(extinction vue, jours VÉCUS écoulés depuis). Pur : c'est ce que les tests exercent.

    ⚠ `souvenir_du` change ce qui compte comme extinction, et le choix n'est pas neutre.

    Sans lui, le déclencheur est « plus aucun souvenir de choc ne pèse sur ses décisions ».
    Mesuré sur la campagne du 2026-09-21 : cette ligne n'arrive que cinq jours vécus avant la
    fin du run, parce que l'agent FABRIQUE ses propres souvenirs de gravité de choc — le bras
    témoin, qui ne subit rien, en produit trois. L'économie est alors nulle.

    Avec lui, le déclencheur est la sortie du souvenir DÉCLARÉ, à sa date. C'est l'événement
    que le protocole étudie, et il tombe treize jours avant la fin du même run.
    """
    vue = False
    jours: list = []
    for ligne in lignes:
        if not vue:
            if souvenir_du:
                touche = f"souvenir de choc du {souvenir_du}" in ligne and "est sorti du bloc" in ligne
            else:
                touche = bool(EXTINCTION.search(ligne))
            if not touche:
                continue
            vue = True
            jours = []
        if vue:
            d = date_simulee(ligne)
            if d is not None and d not in jours:
                jours.append(d)
    # Le jour de l'extinction compte pour zéro : on veut N jours APRÈS lui.
    return vue, max(0, len(jours) - 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--journal", default="experiments/current/app.log",
                    help="app.log du run à surveiller")
    ap.add_argument("--jours", type=int, default=7,
                    help="jours VÉCUS à observer après l'extinction (défaut : 7)")
    ap.add_argument("--arreter", action="store_true",
                    help="lancer `make stop-run` une fois le délai écoulé. Sans ce drapeau, "
                         "le script se contente de signaler et rend la main.")
    ap.add_argument("--souvenir-du", default=None, metavar="AAAA-MM-JJ",
                    help="date SIMULÉE du souvenir déclaré à surveiller. Recommandé : sans lui, "
                         "le déclencheur attend que PLUS AUCUN souvenir de choc ne pèse, ce qui "
                         "n'arrive qu'en toute fin de run puisque l'agent en fabrique lui-même.")
    ap.add_argument("--intervalle", type=float, default=30.0)
    ap.add_argument("--limite-h", type=float, default=6.0,
                    help="abandon au bout de ce nombre d'heures, pour ne jamais tourner sans fin")
    a = ap.parse_args()

    journal = Path(a.journal)
    depart = time.monotonic()
    annonce = False
    while time.monotonic() - depart < a.limite_h * 3600:
        if journal.is_file():
            with open(journal, encoding="utf-8", errors="replace") as f:
                vue, ecoules = analyser(f, a.souvenir_du)
            if vue and not annonce:
                annonce = True
                print(f"[arret] extinction détectée — observation de {a.jours} jours vécus", flush=True)
            if vue and ecoules >= a.jours:
                print(f"[arret] {ecoules} jours vécus depuis l'extinction : le run peut s'arrêter.",
                      flush=True)
                if a.arreter:
                    print("[arret] `make stop-run`", flush=True)
                    subprocess.run(["make", "stop-run"], check=False)
                return 0
        time.sleep(a.intervalle)
    print(f"[arret] limite de {a.limite_h} h atteinte sans extinction — rien n'a été arrêté.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
