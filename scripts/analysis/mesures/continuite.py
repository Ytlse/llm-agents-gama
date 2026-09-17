"""Vérifie qu'une coupure n'a pas trahi les courbes — ticket 093, § 4 (recette).

CE QUE CETTE VÉRIFICATION ATTRAPE
---------------------------------
La recette du ticket tient en trois gestes : deux jours simulés, un arrêt, une reprise nommée
(ticket 091). Le vrai test est ce qu'on lit ensuite : **une métrique qui saute ou se dédouble à la
reprise est une métrique fausse**, et sur un run de vingt jours personne ne la verrait plus.

Trois défauts, donc, et ils se cherchent à l'œil nu sur deux jours quand on sait où regarder :

1. **Le dédoublement.** Une clé écrite deux fois, parce que le jour rejoué a été ajouté au lieu
   d'être recalculé.
2. **Le trou.** Un jour manquant entre le premier et le dernier — la reprise a repris ailleurs
   qu'où elle avait laissé.
3. **Le saut.** Une valeur d'un jour ANTÉRIEUR à la coupure qui a changé, alors que rien de ce qui
   s'est passé après ne peut la concerner.

⚠ Un jour manquant n'est pas toujours un trou : la simulation saute les week-ends, dont les
départs sont reportés au lundi. Le vérificateur le sait, et ne crie que sur les jours ouvrés.

USAGE
-----
    python -m scripts.analysis.mesures.continuite <avant> <apres>

où `<avant>` est une copie des CSV prise avant la coupure, et `<apres>` le répertoire des CSV
après la reprise. Sortie non nulle si la continuité est rompue : la recette échoue bruyamment.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Sequence

from scripts.analysis.mesures.ecriture import TABLES, Table


@dataclass
class Rupture:
    table: str
    genre: str  # « dédoublement », « trou », « saut »
    detail: str


@dataclass
class Verdict:
    ruptures: list[Rupture] = field(default_factory=list)
    tables_verifiees: list[str] = field(default_factory=list)
    lignes_comparees: int = 0

    @property
    def continu(self) -> bool:
        return not self.ruptures


def _lire(chemin: Path) -> list[dict[str, str]]:
    if not chemin.is_file():
        return []
    with chemin.open(newline="", encoding="utf-8") as flux:
        return list(csv.DictReader(flux))


def _cle(ligne: dict[str, str], table: Table) -> tuple[str, ...]:
    return tuple(ligne.get(colonne, "") for colonne in table.cle)


def _jours_ouvres_manquants(dates: Sequence[str]) -> list[str]:
    """Jours OUVRÉS absents entre le premier et le dernier. Les week-ends ne comptent pas."""
    if len(dates) < 2:
        return []
    connues = {date.fromisoformat(d) for d in dates}
    debut, fin = min(connues), max(connues)
    manquants = []
    courant = debut
    while courant <= fin:
        if courant.isoweekday() <= 5 and courant not in connues:
            manquants.append(courant.isoformat())
        courant += timedelta(days=1)
    return manquants


def verifier(avant: Path | str, apres: Path | str) -> Verdict:
    """Compare deux instantanés des CSV et rend le verdict."""
    avant, apres = Path(avant), Path(apres)
    verdict = Verdict()
    for nom, table in TABLES.items():
        lignes_apres = _lire(apres / table.fichier)
        if not lignes_apres:
            continue
        verdict.tables_verifiees.append(nom)

        vues: dict[tuple[str, ...], int] = {}
        for ligne in lignes_apres:
            clef = _cle(ligne, table)
            vues[clef] = vues.get(clef, 0) + 1
        for clef, compte in sorted(vues.items()):
            if compte > 1:
                verdict.ruptures.append(Rupture(
                    nom, "dédoublement",
                    f"la clé {clef} apparaît {compte} fois — un jour rejoué a été AJOUTÉ au "
                    f"lieu d'être recalculé"))

        dates = sorted({l["date_simulee"] for l in lignes_apres if l.get("date_simulee")})
        for manquant in _jours_ouvres_manquants(dates):
            verdict.ruptures.append(Rupture(
                nom, "trou", f"aucune ligne pour le jour ouvré {manquant}"))

        anciennes = {_cle(l, table): l for l in _lire(avant / table.fichier)}
        if not anciennes:
            continue
        nouvelles = {_cle(l, table): l for l in lignes_apres}
        for clef, ancienne in sorted(anciennes.items()):
            nouvelle = nouvelles.get(clef)
            verdict.lignes_comparees += 1
            if nouvelle is None:
                verdict.ruptures.append(Rupture(
                    nom, "trou", f"la ligne {clef}, écrite avant la coupure, a DISPARU"))
                continue
            for colonne in table.colonnes:
                if ancienne.get(colonne, "") != nouvelle.get(colonne, ""):
                    verdict.ruptures.append(Rupture(
                        nom, "saut",
                        f"{clef} · colonne « {colonne} » : "
                        f"{ancienne.get(colonne, '')!r} → {nouvelle.get(colonne, '')!r} — "
                        f"une valeur d'un jour antérieur à la coupure a changé"))
    return verdict


def main(argv=None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("avant", type=Path, help="CSV copiés AVANT la coupure")
    parseur.add_argument("apres", type=Path, help="CSV APRÈS la reprise")
    args = parseur.parse_args(argv)

    verdict = verifier(args.avant, args.apres)
    print(f"{len(verdict.tables_verifiees)} table(s) vérifiée(s), "
          f"{verdict.lignes_comparees} ligne(s) comparée(s) de part et d'autre de la coupure.")
    if verdict.continu:
        print("✔ Les courbes sont CONTINUES : aucune clé dédoublée, aucun jour ouvré manquant, "
              "aucune valeur d'un jour antérieur modifiée.")
        return 0
    print(f"✘ Continuité ROMPUE — {len(verdict.ruptures)} anomalie(s) :")
    for rupture in verdict.ruptures:
        print(f"  [{rupture.genre}] {rupture.table} — {rupture.detail}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
