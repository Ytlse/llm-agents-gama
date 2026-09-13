#!/usr/bin/env python3
"""Ticket 045, lots 1 et 3 — archiver tout ce qui n'est pas la v5, et repartir d'une base neuve.

Ce que fait ce script (R22 à R25) :

- **déplace** les cohortes qui ne sont plus la référence sous `data/population/archive/`,
  ainsi que les fichiers nus de travail qui ne servent plus ;
- **déplace** tout `data/experiences/` sous `data/experiences/archive_v1_<date>/` ;
- **déplace** le jeu scellé contre la v1 sous `data/jeux/archive/` ;
- écrit un `README.md` dans chaque archive, disant ce qu'elle contient et la règle qui s'y
  applique ;
- **zippe** chaque archive et journalise l'empreinte du zip ;
- vérifie que la base est bien vierge à l'arrivée.

Trois principes, et ils ne se négocient pas :

1. **Rien n'est supprimé, rien n'est copié : tout est DÉPLACÉ.** Un dossier scellé ne se
   modifie pas (règle du `MANIFEST`), et ces mesures gardent leur valeur d'historique — ce
   sont elles qui disent quoi reconstruire.
2. **Chaque chemin d'origine est journalisé**, dans un fichier lisible à côté de l'archive.
   Une archive dont on ne sait plus d'où elle vient n'est pas une archive, c'est une perte.
3. **Idempotent et vérifié.** Relancé, le script ne fait rien de plus et le dit. Il refuse de
   commencer si la cohorte de référence n'est pas là, ou si une exécution tourne encore.

Usage :
    python scripts/archiver_substrat_v1.py --verifier   # n'écrit rien, dit ce qui serait fait
    python scripts/archiver_substrat_v1.py              # exécute
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
POP = RACINE / "data" / "population"
JEUX = RACINE / "data" / "jeux"
EXPERIENCES = RACINE / "data" / "experiences"

DATE = "2026-09-11"
COHORTE_REFERENCE = "population_1000_AAMAS_v5"

# Cohortes scellées qui ne sont plus la référence.
COHORTES_A_ARCHIVER = (
    "population_1000_AAMAS",
    "population_1000_AAMAS_v3",
    "population_1000_AAMAS_v4",
)

# Fichiers nus de travail qui ne servent plus. `toulouse_population_1000_AAMAS.json` n'y est
# PAS : c'est la source déclarée de la cohorte v5 dans son MANIFEST, elle reste en place.
FICHIERS_NUS_A_ARCHIVER = (
    "toulouse_population_100.json",
    "toulouse_population_1000.json",
    "toulouse_population_1000.json.bak",
    "toulouse_population_10000.json",
    "toulouse_population_1000_AAMAS.json.bak",
    "toulouse_population_1000_AAMAS_v4_repetition_HG.json",
    "toulouse_population_1014.json",
    "toulouse_population_5000.json",
)

JEU_A_ARCHIVER = "population_1000_AAMAS_20260316"

# Laissés en place, et c'est délibéré : `sauvegardes/` est un dépôt de sauvegardes qui porte
# sa propre convention et contient l'archive tar.gz de la v5 elle-même ; `old/` et `origin/`
# sont des dépôts informels antérieurs, déjà hors du chemin et déjà documentés. Les déplacer
# n'ajouterait rien et ferait perdre des repères.
LAISSES_EN_PLACE = ("sauvegardes", "old", "origin")


README_POPULATIONS = """# Cohortes archivées — {date}

Ces cohortes **ne sont plus la référence**. La cohorte de référence de l'article est
`data/population/{reference}` (empreinte `de73532e…`, scellée le 4 septembre 2026).

## Pourquoi elles sont ici

Les 36 exécutions de la plateforme d'expériences ont toutes lu la cohorte **v1**
(`population_1000_AAMAS`, `f67b0777…`) et non la v5. Aucune mesure n'existait sur la cohorte
de référence. Deux mécanismes s'étaient renforcés : le formulaire du tableau de bord proposait
la première cohorte par ordre alphabétique — donc la v1 —, et la table de nommage rendait
cette même cohorte **muette** dans le nom des expériences, si bien qu'aucun des 46 noms ne
signalait le substrat lu.

Les deux causes sont corrigées (ticket 045). Ranger les cohortes périmées ferme la troisième :
on ne se trompe pas de cohorte quand une seule est en place.

## La règle

> Une population archivée **ne se lit pas**. Toute exception demande une confirmation
> explicite de l'auteur, consignée dans le ticket qui la demande.

Cette règle est tenue **par le code**, pas seulement par ce fichier : `resoudre_population()`
refuse tout chemin situé sous `archive/`. Un garde-fou qui n'existe que dans un README ne se
déclenche jamais. La levée passe par un champ explicite dans la définition de l'expérience :

    population:
      chemin: data/population/archive/population_1000_AAMAS
      archivee_confirmee: "témoin du ticket 045"

Le motif est journalisé à chaque lecture. Il faut écrire POURQUOI, pas cocher une case.

## Contenu

{contenu}

Le détail des chemins d'origine est dans `JOURNAL.json`, à côté de ce fichier.
"""

README_EXPERIENCES = """# Expériences archivées — mesures sur la cohorte v1, {date}

## Ce que contient ce dossier

Les **46 définitions** et **36 exécutions** de la plateforme d'expériences telles qu'elles
étaient au {date}. Toutes ont lu la cohorte **v1** (`population_1000_AAMAS`, `f67b0777…`),
alors que la cohorte de référence de l'article est la **v5** (`de73532e…`).

## La règle

> Ces mesures sont **invalides pour l'article**. Elles sont conservées comme trace :
> **ne pas les rejouer, ne pas les citer.**

Elles gardent une valeur, et une seule : ce sont elles qui disent **quoi reconstruire**. La
liste des bras à rejouer sur la v5 en est tirée — seuls ceux dont la mesure v1 était complète
(couverture ≥ 0,99) sont reconstruits.

## Ce qu'il faut savoir avant de les lire

Quatre défauts les affectent, au-delà de la cohorte :

- **la journée n'était pas refermée** : la plateforme énumérait n − 1 déplacements par
  personne là où la simulation en joue n. Le retour au domicile n'était jamais décidé, soit
  27 % de la journée — et précisément la part où la contrainte de chaîne des véhicules mord
  le plus. Les parts modales publiées sont donc celles d'une journée amputée de son retour ;
- **l'empreinte de gabarit différait selon l'endroit du lancement** (hôte ou conteneur) pour
  un texte pourtant identique. Ce n'était qu'une illusion de divergence, mais elle rend les
  empreintes de ces exécutions incomparables entre elles telles quelles ;
- **aucune exécution ne porte l'état du dépôt** : `commit` et `arbre_propre` sont nuls
  presque partout, `git` n'étant pas installé dans le conteneur. Ces mesures ne se
  rattachent à aucun état du code ;
- **quatre bras étiquetés `gemini-3.1-flash-lite` ont en réalité tourné sur la version
  `-preview`**, écartée depuis.

Le détail des chemins d'origine est dans `JOURNAL.json`.
"""

README_JEUX = """# Jeux archivés — {date}

`{jeu}` a été préparé et scellé contre la cohorte **v1**, qui n'est plus la référence.

## La règle

> Un jeu archivé **ne se rejoue pas**. Il est conservé comme trace des 36 exécutions qui
> l'ont lu.

Le jeu de référence est à construire sur la cohorte v5, avec les mêmes jour simulé, politique
et graine, pour que **seule la cohorte change** :

    make jeu POP=data/population/{reference} NOM={reference}_20260316 JOUR=2026-03-16

Deux différences attendues sur le nouveau jeu, toutes deux voulues : la journée s'y referme
(3 299 déplacements attendus contre 2 405 sous l'ancienne énumération), et le manifeste porte
désormais l'état du dépôt et la clé effective du graphe OSMnx, tous deux nuls ici.

Le détail des chemins d'origine est dans `JOURNAL.json`.
"""


def _sha256(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def _taille(chemin: Path) -> int:
    if chemin.is_file():
        return chemin.stat().st_size
    return sum(p.stat().st_size for p in chemin.rglob("*") if p.is_file())


def _humain(octets: int) -> str:
    for unite in ("o", "Ko", "Mo", "Go"):
        if octets < 1024 or unite == "Go":
            return f"{octets:.0f} {unite}" if unite == "o" else f"{octets:.1f} {unite}"
        octets /= 1024
    return f"{octets:.1f} Go"


class Journal:
    """Ce qui a bougé, d'où vers où, et ce qui n'a pas bougé — avec la raison."""

    def __init__(self, verifier: bool):
        self.verifier = verifier
        self.deplacements: list[dict] = []
        self.ignores: list[dict] = []
        self.zips: list[dict] = []

    def deplace(self, source: Path, cible: Path) -> None:
        self.deplacements.append(
            {
                "origine": str(source.relative_to(RACINE)),
                "destination": str(cible.relative_to(RACINE)),
                "octets": _taille(source) if source.exists() else None,
            }
        )
        print(
            f"  {'[vérif] ' if self.verifier else ''}"
            f"{source.relative_to(RACINE)}  →  {cible.relative_to(RACINE)}"
        )

    def ignore(self, quoi: str, pourquoi: str) -> None:
        self.ignores.append({"quoi": quoi, "pourquoi": pourquoi})
        print(f"  laissé en place : {quoi} — {pourquoi}")

    def zip(self, archive: Path, sha: str, octets: int, n: int) -> None:
        self.zips.append(
            {
                "zip": str(archive.relative_to(RACINE)),
                "sha256": sha,
                "octets": octets,
                "fichiers": n,
            }
        )
        print(f"  zip {archive.relative_to(RACINE)} — {_humain(octets)}, {n} fichiers, sha256 {sha[:12]}…")

    def ecrire(self, cible: Path) -> None:
        if self.verifier:
            return
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(
            json.dumps(
                {
                    "ticket": "045",
                    "date": DATE,
                    "genere_le": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "cohorte_de_reference": COHORTE_REFERENCE,
                    "deplacements": self.deplacements,
                    "laisses_en_place": self.ignores,
                    "zips": self.zips,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def _deplacer(source: Path, dossier_cible: Path, journal: Journal) -> bool:
    """Déplace `source` dans `dossier_cible`. Rend False si rien à faire."""
    if not source.exists():
        return False
    cible = dossier_cible / source.name
    if cible.exists():
        print(f"  déjà archivé : {cible.relative_to(RACINE)}")
        return False
    journal.deplace(source, cible)
    if not journal.verifier:
        dossier_cible.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(cible))
    return True


def _zipper(dossier: Path, journal: Journal) -> None:
    """Zippe `dossier` à côté de lui-même, et journalise l'empreinte du zip (R24).

    Le zip est la copie **transportable** ; les dossiers archivés restent en place. On ne
    supprime jamais la source après compression : un zip est une commodité, pas un coffre.
    """
    if not dossier.is_dir():
        return
    archive = dossier.parent / f"{dossier.name}.zip"
    if archive.exists():
        print(f"  zip déjà présent : {archive.relative_to(RACINE)}")
        return
    if journal.verifier:
        n = sum(1 for p in dossier.rglob("*") if p.is_file())
        print(f"  [vérif] zipperait {dossier.relative_to(RACINE)} ({n} fichiers, {_humain(_taille(dossier))})")
        return
    fichiers = [p for p in sorted(dossier.rglob("*")) if p.is_file()]
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in fichiers:
            z.write(p, p.relative_to(dossier.parent))
    journal.zip(archive, _sha256(archive), archive.stat().st_size, len(fichiers))


def _prealables() -> list[str]:
    """Ce qui doit être vrai avant de commencer. Une liste vide vaut feu vert."""
    refus = []
    reference = POP / COHORTE_REFERENCE
    if not (reference / "MANIFEST.yaml").is_file():
        refus.append(
            f"la cohorte de référence {COHORTE_REFERENCE} est absente ou non scellée "
            f"({reference}) — archiver le reste laisserait le dépôt sans substrat"
        )
    try:
        sortie = subprocess.run(
            ["docker", "compose", "exec", "-T", "controller", "sh", "-c", "ps ax"],
            cwd=RACINE,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        ).stdout
        if "python -m experiences" in sortie:
            refus.append(
                "une exécution tourne encore dans le conteneur controller — "
                "déplacer data/experiences sous ses pieds la ferait échouer"
            )
    except (OSError, subprocess.SubprocessError):
        pass  # Docker absent ou muet : on ne bloque pas là-dessus, on le dit plus bas.
    return refus


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--verifier",
        action="store_true",
        help="n'écrit rien : dit ce qui serait déplacé, et vérifie les préalables",
    )
    a = ap.parse_args()
    journal = Journal(a.verifier)

    print(f"Ticket 045 — archivage du substrat v1{' (VÉRIFICATION, rien ne sera écrit)' if a.verifier else ''}\n")

    refus = _prealables()
    if refus:
        print("REFUS — préalables non tenus :")
        for r in refus:
            print(f"  · {r}")
        return 1
    print(f"Préalables tenus : cohorte de référence {COHORTE_REFERENCE} en place, rien ne tourne.\n")

    # ── Lot 1 : les cohortes ────────────────────────────────────────────────
    print("Lot 1 — cohortes et fichiers de travail")
    archive_pop = POP / "archive"
    archivees = []
    for nom in COHORTES_A_ARCHIVER:
        if _deplacer(POP / nom, archive_pop, journal):
            archivees.append(nom)
    for nom in FICHIERS_NUS_A_ARCHIVER:
        _deplacer(POP / nom, archive_pop, journal)
    for nom in LAISSES_EN_PLACE:
        if (POP / nom).exists():
            journal.ignore(
                f"data/population/{nom}",
                "dépôt d'archive antérieur, déjà hors du chemin et documenté"
                + (" ; contient la sauvegarde de la v5" if nom == "sauvegardes" else ""),
            )
    journal.ignore(
        "data/population/toulouse_population_1000_AAMAS.json",
        f"source déclarée de la cohorte de référence {COHORTE_REFERENCE} dans son MANIFEST",
    )

    # ── Lot 3 : les expériences et le jeu ───────────────────────────────────
    print("\nLot 3 — expériences et jeu")
    archive_exp = EXPERIENCES / f"archive_v1_{DATE}"
    if EXPERIENCES.is_dir():
        for p in sorted(EXPERIENCES.iterdir()):
            if p.name.startswith("archive_v1_") or p.name.startswith("."):
                continue
            _deplacer(p, archive_exp, journal)
    _deplacer(JEUX / JEU_A_ARCHIVER, JEUX / "archive", journal)

    # ── Les README ──────────────────────────────────────────────────────────
    if not a.verifier:
        contenu = "\n".join(
            f"- `{n}` — cohorte scellée, {_humain(_taille(archive_pop / n))}"
            for n in archivees
            if (archive_pop / n).exists()
        ) or "- (aucune cohorte scellée déplacée lors de ce passage)"
        for dossier, texte in (
            (
                archive_pop,
                README_POPULATIONS.format(
                    date=DATE, reference=COHORTE_REFERENCE, contenu=contenu
                ),
            ),
            (archive_exp, README_EXPERIENCES.format(date=DATE)),
            (
                JEUX / "archive",
                README_JEUX.format(
                    date=DATE, jeu=JEU_A_ARCHIVER, reference=COHORTE_REFERENCE
                ),
            ),
        ):
            if dossier.is_dir():
                (dossier / "README.md").write_text(texte, encoding="utf-8")
                print(f"  README écrit : {(dossier / 'README.md').relative_to(RACINE)}")

    # ── Les zips ────────────────────────────────────────────────────────────
    print("\nCompression")
    for dossier in (archive_pop, archive_exp, JEUX / "archive"):
        _zipper(dossier, journal)

    # ── Vérification d'arrivée ──────────────────────────────────────────────
    print("\nVérification")
    restes_exp = (
        [p.name for p in EXPERIENCES.iterdir() if not p.name.startswith((".", "archive_v1_"))]
        if EXPERIENCES.is_dir()
        else []
    )
    # `archive.zip` est une ARCHIVE, pas un reste : l'exclure par le seul nom de dossier
    # faisait échouer la vérification sur le produit de l'étape précédente.
    restes_jeux = (
        [
            p.name
            for p in JEUX.iterdir()
            if p.name not in ("archive", "archive.zip") and not p.name.startswith(".")
        ]
        if JEUX.is_dir()
        else []
    )
    restes_pop = (
        [
            p.name
            for p in POP.iterdir()
            if (p / "MANIFEST.yaml").is_file() and p.name != COHORTE_REFERENCE
        ]
        if POP.is_dir()
        else []
    )
    ok = True
    for libelle, restes, attendu in (
        ("data/experiences", restes_exp, "vide hors archive"),
        ("data/jeux", restes_jeux, "vide hors archive — le jeu v5 est à construire"),
        ("cohortes scellées en place", restes_pop, f"la seule {COHORTE_REFERENCE}"),
    ):
        if restes:
            ok = False
            print(f"  ✗ {libelle} : attendu {attendu}, trouvé {restes}")
        else:
            print(f"  ✓ {libelle} : {attendu}")

    journal.ecrire(RACINE / "data" / f"JOURNAL_archivage_ticket_045_{DATE}.json")
    if not a.verifier:
        print(f"\nJournal : data/JOURNAL_archivage_ticket_045_{DATE}.json")
    print(
        f"\n{len(journal.deplacements)} élément(s) déplacé(s), "
        f"{len(journal.zips)} archive(s) compressée(s)."
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
