#!/usr/bin/env python3
"""Ticket 074, lot A — geler l'état FRANÇAIS du dispositif avant de le basculer en anglais.

Ce que ce script produit : `archive/<date>_avant_bascule_anglaise/`, un dossier **froid**.

    Froid = restaurable et auditable, jamais utilisé ni référencé.

À distinguer du statut `archivee` de la plateforme (`make experience-statuer … STATUT=archivee`),
qui ne change que la VISIBILITÉ : les fichiers y restent en place et restent lisibles par le code.
Ici, on déplace hors de portée des chargeurs, et un test (`scripts/tests/test_074_archive_froide.py`)
le vérifie plutôt que de le promettre.

Deux modes de rangement, et la distinction n'est pas cosmétique :

- **copie** — pour ce que git suit déjà (`prompts.yaml`, les gabarits, les schémas, la couche de
  rendu). Ces fichiers RESTENT en place : ce sont eux qu'on traduit. Git porte l'historique ;
  la copie n'existe que pour qu'un auditeur lise l'état français sans faire de l'archéologie
  dans les commits.
- **déplacement** — pour ce que git ne suit pas et qui ne doit plus servir : les jeux scellés,
  les cohortes, les définitions et exécutions d'expériences. Rien n'est supprimé
  (contrainte de `specs/hygiene-prompts-et-plateforme-experiences.md`).

Trois principes repris de `archiver_substrat_v1.py`, qui ne se négocient pas :

1. **Rien n'est supprimé.** Déplacé ou copié, jamais effacé.
2. **Chaque chemin d'origine est journalisé**, avec son empreinte. Une archive dont on ne sait
   plus d'où elle vient n'est pas une archive, c'est une perte.
3. **Idempotent et vérifié.** Relancé, il ne fait rien de plus et le dit. Il refuse de commencer
   si une exécution tourne encore.

Usage :
    python scripts/archiver_avant_bascule_anglaise.py              # n'écrit rien, dit ce qui serait fait
    python scripts/archiver_avant_bascule_anglaise.py --appliquer  # exécute
"""

from __future__ import annotations

# ⚠ AVANT tout autre import. Python place le dossier du script en tête de `sys.path`, et
# `scripts/warnings.py` (l'outil de `make warning`) masque alors le module standard du même
# nom : `subprocess` échoue à l'import sur `warnings.warn`, après avoir déversé un tableau de
# warnings sans rapport. Le dossier du script n'apporte rien ici — on le retire.
import os as _os
import sys as _sys

_ici = _os.path.dirname(_os.path.realpath(__file__))
_sys.path[:] = [p for p in _sys.path if _os.path.realpath(p or ".") != _ici]

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]

DATE = "2026-09-14"
NOM_ARCHIVE = f"{DATE}_avant_bascule_anglaise"
ARCHIVE = RACINE / "archive" / NOM_ARCHIVE

COPIE = "copié"
DEPLACEMENT = "déplacé"

# Une progression écrite il y a moins de ça : un runner tient peut-être encore ce dossier.
# Même seuil que `renommer_experiences.py`, pour la même raison.
FRAICHEUR_VIVANTE_S = 120


@dataclass(frozen=True)
class Piece:
    """Un élément à ranger : d'où il vient, où il va dans l'archive, et comment."""

    origine: str           # relatif à la racine du dépôt
    sous_dossier: str      # sous-dossier de l'archive
    mode: str              # COPIE | DEPLACEMENT
    pourquoi: str

    @property
    def source(self) -> Path:
        return RACINE / self.origine

    @property
    def cible(self) -> Path:
        return ARCHIVE / self.sous_dossier / Path(self.origine).name


# ── Ce qui est COPIÉ : les surfaces françaises que la traduction va réécrire sur place ────────
#
# Les huit surfaces de `specs/ticket_074/inventaire_traduction.md`, plus `terminal_time.yaml`
# et le CSV de conditions météo réellement lu à l'exécution — deux découvertes de la
# reconnaissance du 2026-09-14, absentes de l'inventaire initial (cf. README de l'archive).
SURFACES_COPIEES: tuple[Piece, ...] = (
    Piece(
        "packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml",
        "prompts", COPIE,
        "B-1 — les 22 variantes de prompt système, avec leurs sceaux `_neutralite` français",
    ),
    Piece(
        "packages/mobility_llm/src/mobility_llm/categories",
        "prompts", COPIE,
        "B-2/B-3 — les 4 gabarits utilisateur et les 4 schémas de sortie",
    ),
    Piece(
        "services/llm-agents/text_helper/templates/tpl/descriptions",
        "rendu", COPIE,
        "B-4 — les 7 gabarits de description d'itinéraire",
    ),
    Piece(
        "services/llm-agents/config/terminal_time.yaml",
        "rendu", COPIE,
        "B-4 (hors inventaire) — les libellés `access`/`egress`/`terminal` atteignent le prompt "
        "via `terminal_label` et `described_steps`",
    ),
    Piece(
        "services/llm-agents/urban_mobility_agents/agents/llm_agent.py",
        "code", COPIE,
        "B-5 — `_build_profile_narrative` et sa table `_income_map`",
    ),
    Piece(
        "services/llm-agents/urban_mobility_agents/utils/weather_loader.py",
        "code", COPIE,
        "B-6 — le rendu du bulletin météo et les expressions de détection de précipitation",
    ),
    Piece(
        "data/weather/meteo_toulouse_codes.csv",
        "rendu", COPIE,
        "B-6 — la table de conditions RÉELLEMENT lue à l'exécution (48 codes)",
    ),
    Piece(
        "data/weather/Codes meteo.csv",
        "rendu", COPIE,
        "B-6 — la table source du notebook `scripts/weather/concat_weather.ipynb` (47 codes)",
    ),
)

# ── Ce qui est DÉPLACÉ : ce qui a été produit sous prompt français et ne doit plus servir ─────
SUBSTRAT_DEPLACE: tuple[Piece, ...] = (
    Piece(
        "data/experiences",
        "plateforme", DEPLACEMENT,
        "les 24 définitions et leurs exécutions — toutes décidées sous prompt français",
    ),
    Piece(
        "data/jeux",
        "plateforme", DEPLACEMENT,
        "les jeux scellés v5 : leur MANIFEST porte le sha256 de `terminal_time.yaml`, "
        "que la traduction modifie",
    ),
    Piece(
        "data/population/population_1000_AAMAS_v5",
        "population", DEPLACEMENT,
        "la cohorte scellée v5 — `main_occupation`, `personal_bike`, `residence_zone` et "
        "`housing_type` y sont en français ; la v6 les remplace",
    ),
    Piece(
        "data/population/population_1000_AAMAS_v5_escort66",
        "population", DEPLACEMENT,
        "la variante escorte de la v5, mêmes traits français",
    ),
    Piece(
        "data/population/toulouse_population_1000_AAMAS.json",
        "population", DEPLACEMENT,
        "la source déclarée de la v5 (`MANIFEST.population.source`) — la régénération v6 "
        "réécrit ce chemin",
    ),
    Piece(
        "scripts/data/population/Temp",
        "population", COPIE,
        "les checkpoints de la chaîne de génération, dont le VIVIER que le MANIFEST v5 cite "
        "comme sa source (`toulouse_population_10000.json`, sha256 bb8f9095…, 11 329 personas). "
        "COPIE et non déplacement : la régénération v6 réécrit ces mêmes chemins, et sans cette "
        "copie la v5 cesserait d'être reconstructible — son manifeste citerait un fichier qui "
        "n'existe plus sous ce contenu",
    ),
)

PIECES = SURFACES_COPIEES + SUBSTRAT_DEPLACE

# Vérifié le 2026-09-14 : AUCUN dossier d'`experiments/` n'est cité par l'article
# (`grep -rIno "experiments/[…]" docs/paper/` ne rend que `experiments/current`, vide).
# La clause A-2 « les dossiers d'`experiments/` référencés par l'article » est donc sans objet.
# Le constat est écrit — pas passé sous silence : une vérification muette se lit comme un oubli.
CONSTATS = (
    "experiments/ — aucun dossier n'est cité par l'article (seul `experiments/current` apparaît, "
    "et il est vide). Rien à déplacer de ce côté.",
    "scripts/synthesis/frames.py et scripts/progedo_logit/ — libellés d'occupation NON archivés "
    "et NON traduits : ce sont des clés de jointure (B-7). La traduction se fait à l'affichage.",
)

# A-3 — les chiffres de l'article qui dérivent de ce qui est gelé ici. Écrits à la main parce
# qu'ils sont le fruit d'une lecture, pas d'un calcul : c'est la liste de ce qui devient daté.
CHIFFRES_DERIVES = {
    "04_metrics_and_substrate.md §4.5": [
        "1 000 personas, 499 ménages (474 complets, 95,0 %)",
        "3 299 déplacements, 3,30 déplacements/persona",
        "10,6 % de personnes immobiles",
        "sha256 de la cohorte : de73532e82c84f62eb72c8a614f3c27767bf5cca1d1574d3574f4a96b65bd8ce",
        "les 13 marges démographiques et leurs écarts max (TOST ±1,0 pt)",
    ],
    "06_ablation.md / 07_untabulated_regimes.md": [
        "les composites L1/EMD/JSD des 10 expériences à décideur LLM",
        "les composites des 14 témoins déterministes (aleatoire, duree_minimale, "
        "majoritaire_voiture, rf, lgbm, mnl, klr)",
        "les plages citées au changelog du 2026-09-14 : classiques 47,3–53,7 · experts 66,5–98,9 "
        "· minimaux 93,8–129,8 · repères naïfs 179–274",
    ],
    "99_annexes.md": [
        "le texte des variantes de prompt publiées en annexe (ticket 069)",
        "l'exemple de prompt rendu, mixte FR/EN",
    ],
}

README = """# Archive froide — l'état français du dispositif, {date}

Gelé avant la **bascule du dispositif en anglais** ([ticket 074](../../docs/tickets/ticket_074_bascule_anglaise_archivage_et_reprise_de_campagne.md)).

## La règle

> Ce dossier est **restaurable et auditable. Il n'est jamais utilisé ni référencé.**

Aucun chargeur du code ne résout un nom depuis ici. Ce n'est pas une promesse de prose : le
garde est dans le code (`experiences.population._verifier_non_archivee` refuse tout chemin
traversant un segment `archive`, et `llm_gateway.prompts.engine` refuse un `prompts.yaml`
rangé de même), et un test le vérifie —
`scripts/tests/test_074_archive_froide.py`.

Restaurer ou auditer se fait **à la main**, en connaissance de cause, et se consigne dans le
ticket qui le demande.

## Pourquoi ce gel

Le prompt servi jusqu'ici était **mixte** : étiquettes et prose en français, motifs
(`work`, `home`), étiquettes de mode (`bicycle`, `foot,bus,foot`) et durées
(`very long (20 minutes or more)`) en anglais. Ce mélange n'a jamais été décidé — il résulte
d'une sédimentation. Le défaut est de forme, pas de validité : la couche de rendu est commune
à toutes les variantes, à tous les bras et à tous les modèles, et ne fait donc varier aucune
comparaison. Mais elle est publiée en annexe, et elle s'y lit comme un travail inachevé.

Toute modification du texte d'un prompt change les décisions. Franciser une durée coûte le
même prix qu'angliciser tout le dispositif : une reprise complète de la campagne. À prix égal,
c'est l'anglais que la littérature soutient (§ 1.3 du ticket).

## Ce que contient ce dossier

{contenu}

Le détail — chemin d'origine, mode de rangement, empreinte sha256, taille — est dans
`MANIFEST.yaml` et `JOURNAL.json`, à côté de ce fichier.

## Deux surfaces que l'inventaire initial ne portait pas

Trouvées à la reconnaissance du 2026-09-14, et archivées ici pour cette raison :

1. **`services/llm-agents/config/terminal_time.yaml`** — ses libellés `labels.access`,
   `.egress`, `.terminal` (« Rejoindre la voiture », « d'accès et de stationnement »…)
   atteignent le prompt via `TravelPlanWrapper.terminal_label` et `.described_steps`.
   Son `sha256` est scellé dans `dependances.config` du MANIFEST de chaque jeu.
2. **`data/weather/meteo_toulouse_codes.csv`** — c'est CE fichier que `weather_loader.py` lit
   à l'exécution, et non `Codes meteo.csv` que nommait le ticket. Ce dernier n'est lu que par
   le notebook `scripts/weather/concat_weather.ipynb`. Les deux sont archivés.

## Constats de vérification

{constats}

## Les chiffres de l'article qui en dérivent

Ils deviennent **datés** dès que la campagne est rejouée en anglais. Liste dans
`MANIFEST.yaml`, clé `chiffres_article`.
"""


# ── Empreintes et tailles ─────────────────────────────────────────────────────────────────


def _sha256_fichier(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def _sha256(chemin: Path) -> str:
    """Empreinte d'un fichier, ou d'un dossier — sha256 des couples (chemin relatif, sha du fichier).

    Le chemin entre dans le hachage : deux dossiers aux mêmes contenus rangés différemment ne
    sont pas le même dossier, et une archive doit pouvoir le dire.
    """
    if chemin.is_file():
        return _sha256_fichier(chemin)
    h = hashlib.sha256()
    for p in sorted(chemin.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(chemin)).encode("utf-8"))
            h.update(_sha256_fichier(p).encode("ascii"))
    return h.hexdigest()


def _taille(chemin: Path) -> int:
    if chemin.is_file():
        return chemin.stat().st_size
    return sum(p.stat().st_size for p in chemin.rglob("*") if p.is_file())


def _fichiers(chemin: Path) -> int:
    return 1 if chemin.is_file() else sum(1 for p in chemin.rglob("*") if p.is_file())


def _humain(octets: float) -> str:
    for unite in ("o", "Ko", "Mo", "Go"):
        if octets < 1024 or unite == "Go":
            return f"{octets:.0f} {unite}" if unite == "o" else f"{octets:.1f} {unite}"
        octets /= 1024
    return f"{octets:.1f} Go"


def _commit() -> dict:
    """État du dépôt au moment du gel. `git` peut manquer — on le dit plutôt que de mentir."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=RACINE, capture_output=True, text=True, timeout=10
        )
        propre = subprocess.run(
            ["git", "status", "--porcelain"], cwd=RACINE, capture_output=True, text=True, timeout=30
        )
        if sha.returncode != 0:
            return {"commit": None, "arbre_propre": None, "erreur": sha.stderr.strip()}
        return {
            "commit": sha.stdout.strip(),
            "arbre_propre": propre.returncode == 0 and not propre.stdout.strip(),
            "fichiers_modifies": len([l for l in propre.stdout.splitlines() if l.strip()]),
        }
    except (OSError, subprocess.SubprocessError) as e:
        return {"commit": None, "arbre_propre": None, "erreur": str(e)}


# ── Garde de démarrage ────────────────────────────────────────────────────────────────────


def executions_vivantes() -> list[str]:
    """Exécutions dont la progression a bougé récemment : un runner les tient peut-être.

    On ne déplace pas un dossier sous les pieds d'un processus qui y écrit. Le critère est la
    FRAÎCHEUR du fichier de progression, pas l'état déclaré : un runner tué laisse un état
    « en cours » qui ne dit rien de vivant, et un runner vivant peut être en attente de quota.
    """
    vivantes = []
    experiences = RACINE / "data" / "experiences"
    if not experiences.is_dir():
        return vivantes
    limite = time.time() - FRAICHEUR_VIVANTE_S
    for progression in experiences.glob("*/executions/*/progression.json"):
        try:
            if progression.stat().st_mtime > limite:
                vivantes.append(str(progression.parent.relative_to(RACINE)))
        except OSError:
            continue
    return sorted(vivantes)


# ── Journal ───────────────────────────────────────────────────────────────────────────────


@dataclass
class Journal:
    verifier: bool
    entrees: list[dict] = field(default_factory=list)
    deja_fait: list[dict] = field(default_factory=list)
    absents: list[dict] = field(default_factory=list)

    def range(self, piece: Piece, sha: str, octets: int, fichiers: int) -> None:
        self.entrees.append(
            {
                "origine": piece.origine,
                "destination": str(piece.cible.relative_to(RACINE)),
                "mode": piece.mode,
                "sha256": sha,
                "octets": octets,
                "fichiers": fichiers,
                "pourquoi": piece.pourquoi,
            }
        )
        prefixe = "[vérif] " if self.verifier else ""
        print(
            f"  {prefixe}{piece.mode:<9} {piece.origine}"
            f"\n            → {piece.cible.relative_to(RACINE)}"
            f"   ({_humain(octets)}, {fichiers} fichier{'s' if fichiers > 1 else ''},"
            f" sha256 {sha[:12]}…)"
        )

    def deja(self, piece: Piece) -> None:
        self.deja_fait.append({"origine": piece.origine, "mode": piece.mode})
        print(f"  déjà rangé : {piece.origine} — l'archive le porte, la source a disparu")

    def absent(self, piece: Piece) -> None:
        self.absents.append({"origine": piece.origine, "mode": piece.mode})
        print(f"  ABSENT : {piece.origine} — ni à sa place, ni dans l'archive")

    def ecrire(self, cible: Path) -> None:
        if self.verifier:
            return
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(
            json.dumps(
                {
                    "gele_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "ticket": "074",
                    "entrees": self.entrees,
                    "deja_range": self.deja_fait,
                    "absents": self.absents,
                    "constats": list(CONSTATS),
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )


# ── Rangement ─────────────────────────────────────────────────────────────────────────────


def ranger(piece: Piece, journal: Journal, *, verifier: bool) -> bool:
    """Range une pièce. Rend True si elle est (ou serait) rangée, False si rien à faire."""
    source, cible = piece.source, piece.cible
    if not source.exists():
        (journal.deja if cible.exists() else journal.absent)(piece)
        return False
    if cible.exists() and piece.mode == DEPLACEMENT:
        # Source ET cible présentes sur un déplacement : ambigu, on ne tranche pas tout seul.
        print(
            f"  REFUS : {piece.origine} existe des deux côtés "
            f"({cible.relative_to(RACINE)}). Trancher à la main avant de relancer."
        )
        return False

    sha, octets, fichiers = _sha256(source), _taille(source), _fichiers(source)
    journal.range(piece, sha, octets, fichiers)
    if verifier:
        return True

    cible.parent.mkdir(parents=True, exist_ok=True)
    if piece.mode == COPIE:
        if cible.exists():
            shutil.rmtree(cible) if cible.is_dir() else cible.unlink()
        if source.is_dir():
            shutil.copytree(source, cible)
        else:
            shutil.copy2(source, cible)
    else:
        shutil.move(str(source), str(cible))
    # Une empreinte qui ne se vérifie pas à l'arrivée n'est pas une empreinte.
    arrivee = _sha256(cible)
    if arrivee != sha:
        raise RuntimeError(
            f"empreinte divergente après rangement de {piece.origine} : "
            f"{sha[:12]}… au départ, {arrivee[:12]}… à l'arrivée"
        )
    return True


def ecrire_manifeste(journal: Journal, *, verifier: bool) -> None:
    if verifier:
        return
    import yaml  # local : le script doit pouvoir tourner en --verifier sans dépendance

    total = sum(e["octets"] for e in journal.entrees)
    manifeste = {
        "version": "froid1",
        "nom": NOM_ARCHIVE,
        "ticket": "074",
        "gele_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "regle": (
            "restaurable et auditable, jamais utilisé ni référencé — aucun chargeur du code "
            "ne résout un nom depuis ce dossier (test : scripts/tests/test_074_archive_froide.py)"
        ),
        "depot": _commit(),
        "totaux": {
            "entrees": len(journal.entrees),
            "octets": total,
            "lisible": _humain(total),
            "copies": sum(1 for e in journal.entrees if e["mode"] == COPIE),
            "deplacements": sum(1 for e in journal.entrees if e["mode"] == DEPLACEMENT),
        },
        "contenu": journal.entrees,
        "constats": list(CONSTATS),
        "chiffres_article": CHIFFRES_DERIVES,
    }
    (ARCHIVE / "MANIFEST.yaml").write_text(
        yaml.safe_dump(manifeste, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    contenu = "\n".join(
        f"- `{e['destination'].split('/', 2)[-1]}` — {e['pourquoi']} "
        f"({e['mode']}, {_humain(e['octets'])})"
        for e in journal.entrees
    )
    constats = "\n".join(f"- {c}" for c in CONSTATS)
    (ARCHIVE / "README.md").write_text(
        README.format(date=DATE, contenu=contenu or "_(rien)_", constats=constats),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--appliquer",
        action="store_true",
        help="exécute réellement (par défaut : dit seulement ce qui serait fait)",
    )
    a = parser.parse_args(argv)
    verifier = not a.appliquer

    print("=" * 78)
    print(f"Ticket 074 lot A — archive froide  ·  {'VÉRIFICATION' if verifier else 'EXÉCUTION'}")
    print(f"cible : archive/{NOM_ARCHIVE}/")
    print("=" * 78)

    vivantes = executions_vivantes()
    if vivantes:
        print(
            "\nREFUSÉ — des exécutions ont écrit leur progression il y a moins de "
            f"{FRAICHEUR_VIVANTE_S} s :\n  - " + "\n  - ".join(vivantes)
        )
        print("On ne déplace pas un dossier sous les pieds d'un runner. Les arrêter d'abord.")
        return 2

    journal = Journal(verifier=verifier)

    print("\n— Surfaces françaises (copiées ; elles restent en place et seront traduites) —")
    ranges = sum(ranger(p, journal, verifier=verifier) for p in SURFACES_COPIEES)

    print("\n— Substrat produit sous prompt français (déplacé) —")
    ranges += sum(ranger(p, journal, verifier=verifier) for p in SUBSTRAT_DEPLACE)

    print("\n— Constats de vérification —")
    for c in CONSTATS:
        print(f"  {c}")

    total = sum(e["octets"] for e in journal.entrees)
    print(
        f"\n{ranges} entrée(s) — {_humain(total)} — "
        f"{sum(1 for e in journal.entrees if e['mode'] == COPIE)} copie(s), "
        f"{sum(1 for e in journal.entrees if e['mode'] == DEPLACEMENT)} déplacement(s)."
    )
    if journal.deja_fait:
        print(f"{len(journal.deja_fait)} entrée(s) déjà rangée(s) — rien à refaire.")
    if journal.absents:
        print(f"⚠ {len(journal.absents)} entrée(s) INTROUVABLE(S) — ni en place, ni dans l'archive.")

    if verifier:
        print(
            "\nRien n'a été écrit. Pour exécuter :"
            "\n    python scripts/archiver_avant_bascule_anglaise.py --appliquer"
        )
        return 0

    ecrire_manifeste(journal, verifier=verifier)
    journal.ecrire(ARCHIVE / "JOURNAL.json")
    print(f"\nArchive écrite : {ARCHIVE.relative_to(RACINE)}/")
    print("  MANIFEST.yaml · README.md · JOURNAL.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
