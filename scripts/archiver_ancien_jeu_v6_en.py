#!/usr/bin/env python3
"""Ticket 098 — geler l'ancien jeu de référence v6 EN et tout ce qui a été décidé dessus.

Ce que ce script produit : `archive/2026-09-21_ancien_jeu_v6_EN/`, un dossier **froid**.

    Froid = restaurable et auditable, jamais utilisé ni référencé.

À distinguer du statut `archivee` de la plateforme (`make experience-statuer … STATUT=archivee`),
qui ne change que la VISIBILITÉ : les fichiers y restent en place et le code continue de les
résoudre. Ici, le chemin lui-même sort du service, et `experiences.froid` refuse de le lire sans
motif écrit.

Sont gelés : les définitions et exécutions dont `experience.yaml` déclare le jeu
`population_1000_AAMAS_v6_20260316_EN`, ET le jeu scellé lui-même. Le jeu part avec les
exécutions pour deux raisons : une exécution ne se rejoue pas sans son substrat (`journal.
regenerer` recharge jeu et cohorte), et un jeu resté sous `data/jeux/` continuerait d'être
proposé au tableau de bord — le défaut même du ticket 045.

Trois principes repris de `archiver_avant_bascule_anglaise.py`, qui ne se négocient pas :

1. **Rien n'est supprimé.** Déplacé, jamais effacé.
2. **Chaque chemin d'origine est journalisé**, avec son empreinte. Une archive dont on ne sait
   plus d'où elle vient n'est pas une archive, c'est une perte.
3. **Idempotent et vérifié.** Relancé, il ne fait rien de plus et le dit. L'empreinte est
   revérifiée à l'arrivée.

Une différence assumée avec le script du 074 : la garde de démarrage est SCOPÉE sur l'ensemble
déplacé (cf. `executions_vivantes`). Le 074 déplaçait `data/experiences` en entier, une garde
globale s'imposait ; ici l'ensemble est disjoint du reste, et une garde globale interdirait le
gel dès qu'une expérience sans rapport tourne.

Usage :
    python scripts/archiver_ancien_jeu_v6_en.py              # n'écrit rien, dit ce qui serait fait
    python scripts/archiver_ancien_jeu_v6_en.py --appliquer  # exécute
"""

from __future__ import annotations

# ⚠ AVANT tout autre import. Python place le dossier du script en tête de `sys.path`, et
# `scripts/warnings.py` (l'outil de `make warning`) masque alors le module standard du même
# nom : `subprocess` échoue à l'import sur `warnings.warn`. Le dossier du script n'apporte rien
# ici — on le retire. (Repris tel quel du script du ticket 074, même piège.)
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

import yaml

RACINE = Path(__file__).resolve().parents[1]

DATE = "2026-09-21"
NOM_ARCHIVE = f"{DATE}_ancien_jeu_v6_EN"
ARCHIVE = RACINE / "archive" / NOM_ARCHIVE
TICKET = "098"

#: Le jeu dont TOUT est gelé — le substrat scellé et ce qui a été décidé dessus.
JEU_GELE = "population_1000_AAMAS_v6_20260316_EN"
#: La référence qui le remplace, nommée dans les refus pour que le lecteur sache où aller.
JEU_COURANT = "population_1000_AAMAS_v6_20260316_EN_c"

DEPLACEMENT = "déplacé"

# Une progression écrite il y a moins de ça : un runner tient peut-être encore ce dossier.
# Même seuil que `archiver_avant_bascule_anglaise.py` et `renommer_experiences.py`.
FRAICHEUR_VIVANTE_S = 120

# États qui ne closent pas une exécution : un dossier dans cet état peut se réveiller seul.
ETATS_NON_FINAUX = ("en_cours", "en_attente_quota", "en_attente_agent")


@dataclass(frozen=True)
class Piece:
    """Un élément à geler : d'où il vient, où il va dans l'archive, et pourquoi."""

    origine: str           # relatif à la racine du dépôt
    sous_dossier: str      # sous-dossier de l'archive
    pourquoi: str
    mode: str = DEPLACEMENT

    @property
    def source(self) -> Path:
        return RACINE / self.origine

    @property
    def cible(self) -> Path:
        return ARCHIVE / self.sous_dossier / Path(self.origine).name


# ── L'inventaire, LU et non recopié ───────────────────────────────────────────────────────


def jeu_declare(dossier: Path) -> str | None:
    """Le jeu que `experience.yaml` déclare, ou None s'il ne se lit pas.

    On lit la DÉCLARATION, jamais le nom du dossier. Le nom porte bien un jeton `jeu-…`, mais
    `…_EN` est un préfixe de `…_EN_c` : un filtre par nom rangerait le jeu corrigé avec
    l'ancien, ou l'inverse selon l'ordre des tests. La déclaration, elle, est exacte.
    """
    fichier = dossier / "experience.yaml"
    try:
        conf = yaml.safe_load(fichier.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    jeu = conf.get("jeu")
    if isinstance(jeu, dict):
        jeu = jeu.get("nom")
    return jeu.strip() if isinstance(jeu, str) and jeu.strip() else None


def inventorier() -> tuple[list[Piece], list[str]]:
    """Les pièces à geler, et les anomalies rencontrées en chemin.

    Recalculé à chaque appel plutôt que figé dans une constante : une liste de 36 noms recopiée
    à la main dérive dès qu'une expérience est renommée, et le script gèlerait alors le mauvais
    ensemble en silence.
    """
    pieces: list[Piece] = []
    anomalies: list[str] = []

    experiences = RACINE / "data" / "experiences"
    if experiences.is_dir():
        for dossier in sorted(experiences.iterdir()):
            if not (dossier / "experience.yaml").is_file():
                continue
            jeu = jeu_declare(dossier)
            if jeu is None:
                anomalies.append(
                    f"{dossier.relative_to(RACINE)} — `experience.yaml` illisible ou sans jeu "
                    "déclaré : NON gelée, elle ne peut pas être rattachée à un substrat"
                )
                continue
            if jeu != JEU_GELE:
                continue
            nb = len([p for p in (dossier / "executions").iterdir() if p.is_dir()]) \
                if (dossier / "executions").is_dir() else 0
            pieces.append(
                Piece(
                    str(dossier.relative_to(RACINE)),
                    "plateforme/experiences",
                    f"décidée sur le substrat daté du 17 mars ({nb} exécution{'s' if nb > 1 else ''})",
                )
            )

    # Ce que l'archive porte DÉJÀ et qui n'est plus sous `data/` : sans cette passe, un second
    # appel ne dirait plus rien des 36 dossiers gelés — ils ont quitté `data/experiences`, donc
    # la boucle ci-dessus ne les voit plus. « 0 pièce » se lirait comme « rien à geler » là où
    # la vérité est « tout est déjà gelé ». Les deux phrases ne valent pas la même chose.
    deja = ARCHIVE / "plateforme" / "experiences"
    if deja.is_dir():
        for range_ in sorted(deja.iterdir()):
            if not (range_ / "experience.yaml").is_file():
                continue
            if (RACINE / "data" / "experiences" / range_.name).exists():
                continue  # présent des deux côtés : `geler` refusera, et dira pourquoi
            pieces.append(
                Piece(
                    str((RACINE / "data" / "experiences" / range_.name).relative_to(RACINE)),
                    "plateforme/experiences",
                    "déjà gelée lors d'un passage précédent",
                )
            )

    jeu_scelle = RACINE / "data" / "jeux" / JEU_GELE
    if jeu_scelle.is_dir() or (ARCHIVE / "plateforme/jeux" / JEU_GELE).exists():
        pieces.append(
            Piece(
                str((RACINE / "data" / "jeux" / JEU_GELE).relative_to(RACINE)),
                "plateforme/jeux",
                "le jeu scellé lui-même — sans lui les exécutions gelées ne se rejouent plus, "
                "et laissé en place il resterait proposé au tableau de bord (R17)",
            )
        )
    else:
        anomalies.append(
            f"data/jeux/{JEU_GELE} — introuvable, ni en place ni dans l'archive"
        )

    return pieces, anomalies


# ── Empreintes et tailles ─────────────────────────────────────────────────────────────────


def _sha256_fichier(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def _sha256(chemin: Path) -> str:
    """Empreinte d'un fichier, ou d'un dossier — sha256 des couples (chemin relatif, sha).

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
            ["git", "rev-parse", "HEAD"], cwd=RACINE, capture_output=True, text=True, timeout=10, check=False
        )
        propre = subprocess.run(
            ["git", "status", "--porcelain"], cwd=RACINE, capture_output=True, text=True, timeout=30, check=False
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


def _vivante(execution: Path, limite: float) -> str | None:
    """Pourquoi cette exécution est peut-être tenue par un runner, ou None si elle est close.

    Deux critères, et il en faut deux. La FRAÎCHEUR de la progression attrape le runner vivant
    dont l'état déclaré ne dit rien (en attente de quota, par exemple). L'ÉTAT attrape celui
    qui dort depuis longtemps mais se réveillera seul. Un runner tué laisse un `en_cours`
    périmé : c'est le seul cas que ni l'un ni l'autre ne doit bloquer, d'où le `ou` et non
    le `et` — l'état périmé n'est vivant que si la progression l'est aussi.
    """
    progression = execution / "progression.json"
    try:
        if progression.is_file() and progression.stat().st_mtime > limite:
            return "progression écrite à l'instant"
    except OSError:
        pass
    try:
        etat = (json.loads((execution / "etat.json").read_text(encoding="utf-8")) or {}).get("etat")
    except (OSError, json.JSONDecodeError):
        return None
    if etat in ETATS_NON_FINAUX:
        try:
            frais = (execution / "etat.json").stat().st_mtime > limite
        except OSError:
            frais = True
        if frais:
            return f"état `{etat}`, écrit à l'instant"
    return None


def executions_vivantes(pieces: list[Piece]) -> list[str]:
    """Exécutions vivantes PARMI LES PIÈCES DÉPLACÉES. On ne déplace pas sous les pieds d'un runner.

    Scopé, contrairement au script du ticket 074 : celui-là déplaçait `data/experiences` en
    entier, et devait donc regarder partout. Ici l'ensemble est disjoint du reste du dépôt —
    une garde globale n'ajouterait aucune sécurité et interdirait le gel dès qu'une expérience
    sans rapport tourne.
    """
    limite = time.time() - FRAICHEUR_VIVANTE_S
    vivantes = []
    for piece in pieces:
        executions = piece.source / "executions"
        if not executions.is_dir():
            continue
        for execution in sorted(executions.iterdir()):
            if not execution.is_dir():
                continue
            raison = _vivante(execution, limite)
            if raison:
                vivantes.append(f"{execution.relative_to(RACINE)} ({raison})")
    return vivantes


def travail_vivant_ailleurs(pieces: list[Piece]) -> list[str]:
    """Exécutions vivantes HORS des pièces déplacées — un avertissement, jamais un refus.

    Elles ne gênent pas le gel. Mais le réancrage Docker de la fin redémarre `controller`,
    `api` et `worker` : une exécution en cours ailleurs le sentira passer. Le dire vaut mieux
    que le laisser découvrir.
    """
    gelees = {piece.source.resolve() for piece in pieces}
    limite = time.time() - FRAICHEUR_VIVANTE_S
    dehors = []
    experiences = RACINE / "data" / "experiences"
    if not experiences.is_dir():
        return dehors
    for dossier in sorted(experiences.iterdir()):
        if not dossier.is_dir() or dossier.resolve() in gelees:
            continue
        for execution in sorted((dossier / "executions").iterdir()) \
                if (dossier / "executions").is_dir() else []:
            if execution.is_dir() and _vivante(execution, limite):
                dehors.append(str(execution.relative_to(RACINE)))
    return dehors


# ── Journal ───────────────────────────────────────────────────────────────────────────────


@dataclass
class Journal:
    verifier: bool
    entrees: list[dict] = field(default_factory=list)
    deja_fait: list[dict] = field(default_factory=list)
    absents: list[dict] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)

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
            f"   ({_humain(octets)}, {fichiers} fichier{'s' if fichiers > 1 else ''},"
            f" sha256 {sha[:12]}…)"
        )

    def deja(self, piece: Piece) -> None:
        self.deja_fait.append({"origine": piece.origine, "mode": piece.mode})
        print(f"  déjà gelé : {piece.origine} — l'archive le porte, la source a disparu")

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
                    "ticket": TICKET,
                    "jeu_gele": JEU_GELE,
                    "jeu_courant": JEU_COURANT,
                    "entrees": self.entrees,
                    "deja_gele": self.deja_fait,
                    "absents": self.absents,
                    "anomalies": self.anomalies,
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )


# ── Gel ───────────────────────────────────────────────────────────────────────────────────


def geler(piece: Piece, journal: Journal, *, verifier: bool) -> bool:
    """Gèle une pièce. Rend True si elle est (ou serait) gelée, False si rien à faire."""
    source, cible = piece.source, piece.cible
    if not source.exists():
        (journal.deja if cible.exists() else journal.absent)(piece)
        return False
    if cible.exists():
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
    shutil.move(str(source), str(cible))
    # Une empreinte qui ne se vérifie pas à l'arrivée n'est pas une empreinte.
    arrivee = _sha256(cible)
    if arrivee != sha:
        raise RuntimeError(
            f"empreinte divergente après gel de {piece.origine} : "
            f"{sha[:12]}… au départ, {arrivee[:12]}… à l'arrivée"
        )
    return True


README = """# Archive froide — l'ancien jeu de référence v6 EN, {date}

Gelé après le remplacement du substrat par sa version corrigée
([ticket 098](../../docs/tickets/ticket_098_archive_froide_de_l_ancien_jeu_v6_en.md),
à la suite du [ticket 088](../../docs/tickets/ticket_088_jeu_corrige_et_rejeu_complet.md)).

## La règle

> Ce dossier est **restaurable et auditable. Il n'est jamais utilisé ni référencé.**

Aucun chargeur du code ne résout un nom depuis ici. Ce n'est pas une promesse de prose : le
garde est dans le code — `experiences.froid.verifier` refuse tout chemin traversant un segment
`archive`, et `scripts/tests/test_098_archive_ancien_jeu.py` le vérifie.

Restaurer ou auditer se fait **à la main**, en connaissance de cause, et se consigne dans le
ticket qui le demande. Le motif est obligatoire et part en WARNING : `confirme=True` se coche
sans y penser, un motif écrit se relit.

## Pourquoi ce gel

Le jeu `{jeu_gele}` portait, pour **797 des 894 personas
mobiles**, une offre d'itinéraires et une météo calculées pour le **17 mars au lieu du 16** :
`deplacements_attendus()` ancrait le curseur sur le `start_time` d'une activité « home »
enjambant minuit, et la règle de report datait le départ du matin du lendemain (ticket 088).

Tout ce qui a été mesuré dessus a été rejoué sur `{jeu_courant}`.
Les mesures de l'ancien substrat ne sont pas seulement périmées : elles sont fausses pour une
raison nommée. Les laisser lisibles à chaud, c'est accepter qu'elles soient relues.

## Ce que le gel ne coûte pas

Vérifié bras par bras **avant** le déplacement :

- aucun bras portant une exécution `terminee` sur l'ancien jeu n'est dépourvu de contrepartie
  `terminee` sur le jeu corrigé (29 bras appariés) ;
- `scripts/analysis/plot_chapitre6.py` porte un repli sur l'ancien jeu, et journalisait déjà
  `Décideurs lus : 13 sur 13 (0 sur l'ancien jeu)` avant le gel. Le repli était mort ; le gel
  l'enregistre.

## Ce que contient ce dossier

{contenu}

Le détail — chemin d'origine, empreinte sha256, taille, nombre de fichiers — est dans
`MANIFEST.yaml` et `JOURNAL.json`, à côté de ce fichier.

## Pourquoi le jeu scellé est ici aussi

Une exécution ne se rejoue pas sans son substrat : `journal.regenerer` recharge le jeu **et** la
cohorte. Et un jeu laissé sous `data/jeux/` serait resté proposé au tableau de bord (R17
n'écarte que ce qui est déjà sous `archive/`) — rien n'aurait empêché de définir demain une
expérience neuve sur le substrat daté du 17 mars. C'est le défaut du ticket 045, à un substrat
près.

La **cohorte** `population_1000_AAMAS_v6`, elle, n'est pas gelée : la correction portait sur le
calcul de l'offre, pas sur les personas, et le jeu corrigé lit la même cohorte.
"""


def ecrire_manifeste(journal: Journal, *, verifier: bool) -> None:
    if verifier:
        return
    total = sum(e["octets"] for e in journal.entrees)
    manifeste = {
        "version": "froid1",
        "nom": NOM_ARCHIVE,
        "ticket": TICKET,
        "gele_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "regle": (
            "restaurable et auditable, jamais utilisé ni référencé — aucun chargeur du code "
            "ne résout un nom depuis ce dossier (test : scripts/tests/test_098_archive_ancien_jeu.py)"
        ),
        "jeu_gele": JEU_GELE,
        "jeu_courant": JEU_COURANT,
        "depot": _commit(),
        "totaux": {
            "entrees": len(journal.entrees),
            "octets": total,
            "lisible": _humain(total),
            "deplacements": len(journal.entrees),
        },
        "contenu": journal.entrees,
        "anomalies": journal.anomalies,
    }
    (ARCHIVE / "MANIFEST.yaml").write_text(
        yaml.safe_dump(manifeste, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    contenu = "\n".join(
        f"- `{e['destination'].split('/', 2)[-1]}` — {e['pourquoi']} ({_humain(e['octets'])})"
        for e in journal.entrees
    )
    (ARCHIVE / "README.md").write_text(
        README.format(
            date=DATE,
            contenu=contenu or "_(rien)_",
            jeu_gele=JEU_GELE,
            jeu_courant=JEU_COURANT,
        ),
        encoding="utf-8",
    )


# ── Réancrage des montages Docker ─────────────────────────────────────────────────────────

#: Services dont un volume pointe sur un dossier que l'archive DÉPLACE.
#: Les nommer ici plutôt que de redémarrer toute la pile : un redémarrage d'OTP coûte
#: plusieurs minutes de rechargement de graphe, pour rien.
SERVICES_A_REANCRER = ("controller", "api", "worker")


def reancrer_montages(*, verifier: bool) -> None:
    """Redémarre les services dont un montage pointe sur un dossier déplacé.

    Appris à la dure le 2026-09-14 (ticket 074). Un montage bind de Docker suit l'**inode**,
    pas le chemin. Déplacer un dossier renomme l'entrée de répertoire : sur l'hôte il n'est
    plus là ; dans le conteneur déjà démarré, le même chemin désigne toujours le MÊME inode,
    c'est-à-dire le dossier maintenant rangé sous `archive/`.

    Le résultat n'est pas une erreur, c'est pire : la plateforme continue de tourner et écrit
    **dans l'archive froide**, que le garde `experiences.froid` ne peut pas voir — il inspecte
    les chemins, et le conteneur ne voit que `/app/data/…`. Une archive « plus jamais
    référencée » resterait la seule chose que le dispositif référence.

    Fail-open : Docker absent ou pile éteinte n'est pas une anomalie (l'archivage doit pouvoir
    tourner sur une machine sans conteneur). On le DIT, et l'archivage continue.
    """
    if verifier:
        print(f"\n[réancrage] {', '.join(SERVICES_A_REANCRER)} seraient redémarrés "
              "(un montage bind suit l'inode, pas le nom).")
        return
    argv = ["docker", "compose", "-f", str(RACINE / "infra" / "docker-compose.yml"),
            "--project-directory", str(RACINE), "restart", *SERVICES_A_REANCRER]
    print(f"\n[réancrage] redémarrage de {', '.join(SERVICES_A_REANCRER)} — sans quoi "
          "les conteneurs continueraient d'écrire dans l'archive.")
    debut = time.time()
    try:
        fait = subprocess.run(argv, cwd=str(RACINE), capture_output=True,
                              text=True, timeout=300, check=False)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"⚠ [réancrage] impossible ({e}). Si la pile tourne, REDÉMARREZ-LA À LA MAIN :\n"
              f"    {' '.join(argv)}")
        return
    if fait.returncode != 0:
        print(f"⚠ [réancrage] échec (code {fait.returncode}) : "
              f"{(fait.stderr or '').strip()[:300]}\n"
              f"    Si la pile tourne, redémarrez-la à la main : {' '.join(argv)}")
        return
    print(f"[réancrage] fait en {time.time() - debut:.0f} s — les conteneurs voient "
          "désormais les dossiers neufs.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--appliquer",
        action="store_true",
        help="exécute réellement (par défaut : dit seulement ce qui serait fait)",
    )
    a = parser.parse_args(argv)
    verifier = not a.appliquer
    debut = time.time()

    print("=" * 78)
    print(f"Ticket {TICKET} — archive froide  ·  {'VÉRIFICATION' if verifier else 'EXÉCUTION'}")
    print(f"jeu gelé : {JEU_GELE}")
    print(f"référence courante : {JEU_COURANT}")
    print(f"cible : archive/{NOM_ARCHIVE}/")
    print("=" * 78)

    pieces, anomalies = inventorier()
    if not pieces:
        print("\nAucune pièce à geler : rien ne déclare ce jeu, et le substrat n'est pas là.")
        return 0

    vivantes = executions_vivantes(pieces)
    if vivantes:
        print(
            f"\nREFUSÉ — {len(vivantes)} exécution(s) à geler sont peut-être tenues par un "
            "runner :\n  - " + "\n  - ".join(vivantes)
        )
        print("On ne déplace pas un dossier sous les pieds d'un runner. Les arrêter d'abord.")
        return 2

    dehors = travail_vivant_ailleurs(pieces)
    if dehors:
        print(
            f"\n⚠ {len(dehors)} exécution(s) vivante(s) HORS de l'ensemble gelé. Elles "
            "n'empêchent pas le gel, mais le réancrage Docker de la fin les fera sursauter :"
            "\n  - " + "\n  - ".join(dehors)
        )

    journal = Journal(verifier=verifier, anomalies=anomalies)
    if anomalies:
        print(f"\n— Anomalies d'inventaire ({len(anomalies)}) —")
        for anomalie in anomalies:
            print(f"  ⚠ {anomalie}")

    print(f"\n— Définitions et exécutions décidées sur `{JEU_GELE}` (déplacées) —")
    geles = sum(
        geler(p, journal, verifier=verifier)
        for p in pieces if p.sous_dossier == "plateforme/experiences"
    )

    print("\n— Substrat scellé (déplacé) —")
    geles += sum(
        geler(p, journal, verifier=verifier)
        for p in pieces if p.sous_dossier == "plateforme/jeux"
    )

    total = sum(e["octets"] for e in journal.entrees)
    print(f"\n{geles} pièce(s) — {_humain(total)} — "
          f"{sum(e['fichiers'] for e in journal.entrees)} fichier(s).")
    if journal.deja_fait:
        print(f"{len(journal.deja_fait)} pièce(s) déjà gelée(s) — rien à refaire.")
    if journal.absents:
        print(f"⚠ {len(journal.absents)} pièce(s) INTROUVABLE(S) — ni en place, ni dans l'archive.")

    if verifier:
        if geles:
            reancrer_montages(verifier=True)
        print("\nRien n'a été écrit. Pour exécuter :"
              "\n    python scripts/archiver_ancien_jeu_v6_en.py --appliquer")
        print(f"Terminé en {time.time() - debut:.1f} s.")
        return 0

    if not geles:
        print(f"\nRien à faire — l'archive est déjà en place. Terminé en {time.time() - debut:.1f} s.")
        return 0

    ecrire_manifeste(journal, verifier=verifier)
    journal.ecrire(ARCHIVE / "JOURNAL.json")
    reancrer_montages(verifier=verifier)
    print(f"\nArchive écrite : {ARCHIVE.relative_to(RACINE)}/")
    print("  MANIFEST.yaml · README.md · JOURNAL.json")
    print(f"Terminé en {time.time() - debut:.1f} s : {geles} pièce(s), {_humain(total)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
