"""Scoring composite d'une exécution — composite, détail par strate, rejeu de formule.

Spec : `specs/scoring_composite_experiences.md`.

Le composite n'est **pas** réimplémenté (R1) : il sort du ``Scorer`` de
`scripts/synthesis/frames.py`, qui importe la loss du moteur de calibration
(`prompt_calibration/calibration/metrics.py`). Ce module est un **adaptateur** :
il lit le `moves.csv` d'une exécution, le passe au même pipeline que la page de
synthèse historique, et persiste un `scores.json` estampillé d'une formule (R5).

Le rejeu d'une formule est **exact et hors-ligne** (R6, R10) : le composite se
recompose par ``weighted_composite`` depuis les scores bruts par dimension déjà
stockés, sans relire `moves.csv` ni appeler le moindre modèle.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import yaml
from experiences import formule as F
from experiences.chemins import racine_depot
from loguru import logger

# ── Accès au pipeline de synthèse et au moteur de loss ───────────────────────
# `scripts.synthesis.frames` vit à la racine du dépôt (paquet-espace, sans
# __init__). On l'ajoute au path une fois ; `import_calibration` ajoutera ensuite
# le dépôt de calibration, exactement comme le fait `scripts/synthesis/build.py`.
# Jamais `parents[2]` : il vaut `<dépôt>/services` sur l'hôte depuis le ticket 039 et `/`
# dans le conteneur. `racine_depot()` s'ancre sur `scripts/synthesis`, juste des deux côtés.
_RACINE_MODULE = racine_depot()
if str(_RACINE_MODULE) not in sys.path:
    sys.path.insert(0, str(_RACINE_MODULE))

from scripts.synthesis import frames, sources

# Repère de résolution des chemins : celui du pipeline de synthèse, juste des DEUX côtés
# (racine du dépôt sur l'hôte, `/app` dans le conteneur où `llm-agents` est monté). Dérivé
# de `__file__`, il valait `/` dans le conteneur : le référentiel d'enquête devenait
# introuvable et tout scoring lancé côté conteneur — donc à la clôture d'une exécution —
# échouait en FileNotFoundError.
REPO_ROOT = sources.REPO_ROOT

# Lignes sans décision modale, exclues du scoring — même liste que
# `scripts/synthesis/sources.yaml` (common_set.exclude_selection_methods).
# « LLM Error (Default index) » est un repli, pas une décision (ticket 008).
EXCLURE_METHODES = [
    "Pas de déplacement (même localisation)",
    "Pas de solution de déplacement",
    "LLM Error (Default index)",
]

# Libellé écrit dans `moves.csv` quand une seule option existait (`runner.py`, méthode
# `choix_unique`). Il N'EST PAS dans `EXCLURE_METHODES` : ces lignes restent dans le
# composite, qui décrit la journée telle qu'elle a eu lieu. Elles servent à produire la
# SECONDE lecture, celle de ce que le décideur a réellement décidé (ticket 047).
METHODE_CHOIX_UNIQUE_MOVES = "Un seul itinéraire disponible"

# Au-delà de cet écart entre les deux lectures du composite, le chiffre publié dépend
# largement de lignes que personne n'a décidées : on le dit en ERROR plutôt que de laisser
# quelqu'un citer un classement que la seconde lecture retourne. Seuil calé sur la mesure du
# 2026-09-12 (16 exécutions du 11/09, jeu et population identiques) : chaîne coupée, l'écart
# plafonne à 0,32 point EMD ; chaîne active, il va de 2,62 à 12,22 et change le classement
# des bras. Un seuil à 1,0 sépare exactement les deux régimes.
ECART_LECTURES_ALARME = 1.0

# ── Ticket 081 — un journal tronqué ne produit jamais de score ────────────────
# `moves.csv` est le SUBSTRAT du composite ; `couverture.decides` compte ce que l'exécution a
# réellement décidé. Les deux se regardaient dans le même `scores.json` sans jamais se
# comparer. L'exécution du 2026-09-12 a été publiée à 5,35 sur 274 lignes quand son archive en
# portait 3 299 : le chiffre a été cité dans trois documents avant d'être reconnu faux (il vaut
# 6,17 sur le journal reconstitué).
#
# Seuil calé sur le balayage des 38 exécutions du dépôt (2026-09-15) : une exécution saine
# compte 3 161 lignes pour 3 151 à 3 155 décidées, soit un déficit TOUJOURS NÉGATIF, de −0,2 à
# −0,3 % — le journal porte en plus les lignes `sans_solution`, que `decides` exclut.
# L'exécution fautive, elle, est à +91,3 %. Un plancher à 2 % laisse 63 lignes de marge sur
# 3 154 et sépare les deux régimes d'un facteur 45 : il ne peut pas se déclencher à tort sur
# l'historique connu, et il ne peut pas manquer une troncature.
TOLERANCE_JOURNAL = 0.02

# Exécutions déjà signalées dans ce processus — l'alarme part sur FRONT MONTANT. Sans cela,
# `score --toutes` rejouerait la même ligne ERROR à chaque passage et `make error` noierait le
# signal dans sa propre répétition. Le nom sort de l'ensemble dès que le contrôle repasse, si
# bien qu'un journal régénéré puis retronqué ré-alarme.
_JOURNAUX_SIGNALES: set[str] = set()


class JournalIncomplet(ValueError):
    """Le journal des mouvements ne recouvre pas les décisions archivées : pas de score.

    Distincte du refus de R21 (« exécution non terminée ») parce qu'elle appelle un remède
    différent : R21 attend la fin de l'exécution, celle-ci demande de régénérer le journal
    (`python -m experiences journal <execution> --regenerer`) et invalide le `scores.json`
    qui aurait été écrit sur le journal tronqué.
    """


# Chemin canonique du référentiel dans le dépôt (EF-77 : lu, jamais recopié).
CEREMA_DEPOT = REPO_ROOT / "scripts" / "data" / "population" / "cerema_values.yaml"

F_SYNTHESE = "synthese.json"
F_MOVES = "moves.csv"
F_SCORES = "scores.json"

# Nom de métrique → clé lisible dans scores.json.
_CLE_METRIQUE = {"emd_jsd": "emd_jsd", "l1_composite": "l1"}


def _lire_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _sha256_fichier(p: Path) -> str | None:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def est_terminee(synthese: dict) -> bool:
    """R21 — seule une exécution clôturée « terminee » est scorable."""
    return (synthese.get("etat") or {}).get("etat") == "terminee"


def volet_pour(synthese: dict) -> str:
    """R15 — décideur `modele` → volet 3 ; tout autre décideur → volet 1."""
    decideur = (synthese.get("empreintes") or {}).get("decideur") or {}
    return "3" if decideur.get("type") == "modele" else "1"


def _resoudre_cerema(synthese: dict) -> Path:
    """Chemin du référentiel : la source citée si présente, sinon le canon du dépôt."""
    source = ((synthese.get("referentiel") or {}).get("source") or "").strip()
    if source:
        # La source est écrite côté conteneur (« app/… ») : on la ramène au dépôt.
        rel = source.removeprefix("app/")
        cand = REPO_ROOT / rel
        if cand.exists():
            return cand
    return CEREMA_DEPOT


def scorer_pour(formule: F.Formule) -> tuple[Any | None, str | None]:
    """Construit un ``Scorer`` avec les poids de la formule. R18 : sans le moteur,
    renvoie ``(None, message)`` — l'appelant n'écrit alors aucun scores.json."""
    calibration, erreur = sources.import_calibration("prompt_calibration")
    if calibration is None:
        return None, erreur
    scorer = frames.Scorer(
        calibration, formule.poids_scorer(), "emd_jsd", "l1_composite"
    )
    return scorer, None


_MOTIF_COUPE = {
    "aucune": "toutes les décisions du journal, tentative la plus récente",
    "horizon": "premier jour simulé (horizon déclaré au-delà d'un jour), tentative la plus récente",
    "repetitions": "premier jour simulé (couples répétés dans le journal), tentative la plus récente",
    "forcee": "premier jour simulé (coupe imposée par l'appelant), tentative la plus récente",
}


def _libelle_perimetre(stats: dict) -> str:
    """R5 — le périmètre effectivement scoré, dit en clair à côté du compte qu'il porte.

    Un compte posé à côté d'un composite qu'il ne recouvre pas est l'erreur que le ticket 047
    a fermée ; un périmètre annoncé qui n'est plus celui appliqué en serait la récidive.
    """
    motif = str(stats.get("coupe") or "aucune")
    base = _MOTIF_COUPE.get(motif, _MOTIF_COUPE["aucune"])
    repetes = int(stats.get("couples_repetes") or 0)
    doublons = int(stats.get("exclues_doublon") or 0)
    detail = f" ; {repetes} couple(s) répété(s)" if repetes else ""
    detail += f" ; {doublons} doublon(s) écarté(s)" if doublons else ""
    return f"lecture du score : {base}{detail}"


def _horizon_jours(dossier: Path) -> int | None:
    """Nombre de jours que l'exécution déclarait couvrir — `None` si l'archive ne le dit pas.

    Sert au critère de coupe du périmètre (ticket 057, R2) : au-delà d'un jour, le journal
    porte plusieurs journées et le score n'en retient qu'une. Lu dans `execution.yaml`, qui
    fige la définition de l'expérience au lancement — pas dans `data/experiences/<nom>/`, qui
    a pu être redéfini depuis.
    """
    try:
        config = yaml.safe_load(
            (dossier / "execution.yaml").read_text(encoding="utf-8")
        )
    except (OSError, yaml.YAMLError):
        return None
    valeur = ((config or {}).get("experience") or {}).get("horizon_jours")
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


def _couverture_de(synthese: dict) -> dict:
    """Le bloc `couverture` d'une synthèse, quel que soit l'endroit où il a été écrit."""
    return (
        (synthese.get("parts_modales") or {}).get("couverture")
        or synthese.get("couverture")
        or {}
    )


def mesurer_perimetre(lignes_journal: int, synthese: dict) -> dict:
    """Constat brut, sans jugement : le journal recouvre-t-il les décisions archivées ?

    Séparée de la règle pour que le balayage (`journal --verifier`) puisse constater sans
    lever et sans alarmer. `complet` est `None` quand `couverture.decides` est absent ou nul :
    il n'y a alors rien à comparer, et dire « complet » serait prendre la vacuité pour une
    vérification — dans ce dépôt, c'est le motif d'erreur le plus tenace.
    """
    decides = (_couverture_de(synthese) or {}).get("decides")
    decides = int(decides) if isinstance(decides, (int, float)) else None
    ecart = None if not decides else decides - lignes_journal
    relatif = None if not decides else ecart / decides
    return {
        "lignes_journal": int(lignes_journal),
        "decides": decides,
        "ecart": ecart,
        "ecart_relatif": relatif,
        "tolerance": TOLERANCE_JOURNAL,
        "complet": None if relatif is None else relatif <= TOLERANCE_JOURNAL,
    }


def verifier_perimetre(dossier: Path, stats: dict, synthese: dict) -> dict:
    """R24 — refuse de scorer un journal qui ne recouvre pas les décisions archivées.

    Le compte comparé est `stats["total"]`, le nombre BRUT de lignes du fichier, avant la
    coupe au premier jour simulé et avant `latest_attempts` : c'est bien la question « le
    journal a-t-il été écrit en entier ? », pas « combien de lignes entrent au composite ? ».

    Lève `JournalIncomplet` sous le seuil, après une `[ALARME]` à front montant.
    """
    constat = mesurer_perimetre(int(stats.get("total") or 0), synthese)
    cle = str(Path(dossier).resolve())
    if constat["complet"] is not False:
        _JOURNAUX_SIGNALES.discard(cle)
        return constat
    if cle not in _JOURNAUX_SIGNALES:
        _JOURNAUX_SIGNALES.add(cle)
        causes = [
            str(i.get("cause"))
            for i in (synthese.get("interruptions") or [])
            if i.get("cause")
        ]
        logger.error(
            f"[ALARME] Journal des mouvements incomplet — "
            f"{synthese.get('experience')}/{synthese.get('execution') or Path(dossier).name} : "
            f"{constat['lignes_journal']} ligne(s) dans moves.csv pour "
            f"{constat['decides']} décision(s) archivées, soit "
            f"{100 * constat['ecart_relatif']:.1f} % de déficit (tolérance "
            f"{100 * TOLERANCE_JOURNAL:.0f} %). Cause probable : "
            + (
                f"interruption(s) {', '.join(causes)} — les décisions resservies à la "
                f"reprise n'écrivaient pas de ligne de journal."
                if causes
                else "aucune interruption consignée ; le journal a été tronqué autrement."
            )
            + " AUCUN score n'est écrit : un composite calculé sur ce journal porterait sur "
            "une fraction du travail sans le dire. Régénérer le journal avec "
            f"`python -m experiences journal {Path(dossier).name} --regenerer`, puis rescorer."
        )
    raise JournalIncomplet(
        f"journal incomplet, non scorable (R24) : {Path(dossier).name} — "
        f"{constat['lignes_journal']} ligne(s) pour {constat['decides']} décisions archivées"
    )


def _detail_par_dimension(frame_attendu: list[dict], cerema: dict) -> dict:
    """Détail par strate pour les 7 dimensions (R5, R16).

    Les dimensions `scored:False` (lieu de résidence, type de logement) sont
    incluses en affichage — elles ne pèsent pas dans le composite.
    """
    detail: dict[str, dict] = {}
    for dim in frames.DIMENSIONS:
        strates = frames.dimension_detail(frame_attendu, cerema, dim)
        detail[dim["key"]] = {
            "label": dim["label"],
            "scored": dim["scored"],
            "strates": strates,
        }
    return detail


def lire_perimetre(
    dossier: str | Path, exclusions: list[str]
) -> tuple[list[dict], dict]:
    """Le périmètre de score d'une exécution — **le seul endroit** qui le décide (ticket 057).

    Deux lectures sortent d'ici, la principale et celle hors itinéraire unique ; les tests et
    toute analyse qui veut refaire le calcul passent par cette fonction plutôt que de
    re-spécifier la coupe. C'est cette duplication-là qui avait laissé le périmètre du scoreur
    diverger de celui que les vérifications croyaient reproduire.

    La coupe au premier jour simulé ne s'applique QUE s'il y a de quoi couper (R2/R3) :
    horizon déclaré au-delà d'un jour, ou couples répétés dans le journal. Appliquée
    systématiquement, elle retirait 866 décisions sur 3 299 des exécutions sans simulateur
    pour zéro doublon — dont 797 départs du matin, que `jeu.py:deplacements_attendus()` date
    du lendemain parce que l'activité « home » d'origine enjambe minuit.
    """
    dossier = Path(dossier)
    return frames.read_moves(
        dossier / F_MOVES,
        exclusions,
        first_day_only="auto",
        horizon_jours=_horizon_jours(dossier),
    )


def calculer(
    dossier: str | Path, formule: F.Formule, scorer: Any | None = None
) -> dict:
    """Score une exécution terminée sous ``formule`` et renvoie le contenu scores.json.

    Lève ``ValueError`` si l'exécution n'est pas terminée (R21) ou si le moteur de
    loss est indisponible (R18) — dans ce cas l'appelant ne doit rien écrire.
    """
    dossier = Path(dossier)
    synthese = _lire_json(dossier / F_SYNTHESE)
    if not est_terminee(synthese):
        raise ValueError(f"exécution non terminée, non scorable (R21) : {dossier.name}")

    if scorer is None:
        scorer, erreur = scorer_pour(formule)
        if scorer is None:
            raise ValueError(f"moteur de loss indisponible (R18) : {erreur}")

    moves = dossier / F_MOVES
    cerema_path = _resoudre_cerema(synthese)
    cerema = frames.load_cerema(cerema_path)
    rows, stats = lire_perimetre(dossier, EXCLURE_METHODES)
    # R24 (ticket 081) — AVANT tout calcul : un journal qui ne recouvre pas les décisions
    # archivées ne produit pas de score. Placé ici, au seul endroit par lequel passent la
    # clôture, `score --execution` et le recalcul global.
    perimetre = verifier_perimetre(dossier, stats, synthese)

    variants = frames.simulation_frames(rows)
    attendu = variants["attendu"]

    # Scores bruts par dimension, pour les DEUX métriques : ils portent chaque
    # s[dim], ce qui rend le rejeu de formule exact et gratuit (R6).
    bruts = scorer.score(attendu, cerema) if attendu else {}
    emd = bruts.get("emd_jsd", {})
    l1 = bruts.get("l1_composite", {})

    # R8 — dimensions non mesurées (repli vers la perte max côté moteur, jamais 0) :
    # on les cite explicitement à côté du composite.
    non_mesurees: list[str] = []
    if attendu:
        _, mesure = scorer.primary.compute_detailed(
            scorer._pd.DataFrame(attendu), cerema
        )
        non_mesurees = list(mesure.undefined)

    tire = variants.get("tiré") or variants.get("tire")
    composite_tire = None
    if tire:
        bruts_tire = scorer.score(tire, cerema)
        composite_tire = (bruts_tire.get("emd_jsd") or {}).get("composite")

    # ── Seconde lecture : ce que le décideur a RÉELLEMENT décidé (ticket 047) ──────
    # Systématique, jamais sur demande : la mesure du 2026-09-12 montre que retirer les
    # choix à itinéraire unique déplace le composite de −3,75 à +12,22 points EMD selon le
    # bras, et qu'elle change le classement (`lgbm` 4,50 → 10,46 passe derrière `klr`). Un
    # composite publié sans sa seconde lecture ne dit pas s'il note un décideur ou une offre.
    rows_hors, _ = lire_perimetre(
        dossier, EXCLURE_METHODES + [METHODE_CHOIX_UNIQUE_MOVES]
    )
    attendu_hors = frames.simulation_frames(rows_hors)["attendu"]
    bruts_hors = scorer.score(attendu_hors, cerema) if attendu_hors else {}
    emd_hors = bruts_hors.get("emd_jsd", {})
    l1_hors = bruts_hors.get("l1_composite", {})

    # Le compte porte sur le périmètre DU SCORE (premier jour simulé, tentative la plus
    # récente), qui n'est pas celui de `synthese.json` (toutes les décisions archivées) :
    # mesuré sur les 16 exécutions du 11/09, les deux diffèrent de 14 à 19 lignes sur
    # chacune. Les deux sont donc publiés, chacun nommant son périmètre — un compte posé à
    # côté d'un composite qu'il ne recouvre pas est précisément l'erreur que ce ticket ferme.
    n_scorees, n_hors = len(rows), len(rows_hors)
    n_forces = n_scorees - n_hors
    forces_execution = synthese.get("choix_forces") or {}
    choix_forces = {
        "n": n_forces,
        "part": (n_forces / n_scorees) if n_scorees else None,
        "n_scorees": n_scorees,
        "n_hors_choix_unique": n_hors,
        "perimetre": _libelle_perimetre(stats),
        "n_execution": forces_execution.get("n"),
        "part_execution": forces_execution.get("part"),
        "perimetre_execution": "toutes les décisions archivées (synthese.json)",
        "lecture": (
            "décisions à itinéraire unique : une seule option existait, personne n'a choisi. "
            "Elles RESTENT dans le composite principal — la journée a eu lieu — et sont "
            "retirées de la seconde lecture. Leur nombre dépend du bras."
        ),
    }

    couverture = _couverture_de(synthese)

    contenu = {
        "execution": synthese.get("execution") or dossier.name,
        "experience": synthese.get("experience"),
        "volet": volet_pour(synthese),
        "genere_le": frames_now(),
        "formule": {"nom": formule.nom, "sha256": formule.sha256},
        "moves_sha256": _sha256_fichier(moves),
        "referentiel": {
            "source": (synthese.get("referentiel") or {}).get("source"),
            "sha256": _sha256_fichier(cerema_path),
        },
        "couverture": couverture,
        # R24 (ticket 081) — le contrôle qui a AUTORISÉ ce score, publié avec lui. Un score
        # sans ce champ a été calculé avant la règle : `scores_perimes` le déclare périmé
        # pour forcer un calcul complet, une fois.
        "perimetre_verifie": perimetre,
        "composite": {
            "emd_jsd": emd.get("composite"),
            "l1": l1.get("composite"),
            "emd_jsd_tire": composite_tire,
            # Seconde lecture (ticket 047). `None` et jamais 0.0 quand elle n'a pas
            # d'effectif : sans décision restante, il n'y a rien à noter — et dans ce dépôt
            # un 0.0 est le score PARFAIT, donc la vacuité s'y déguiserait en excellence.
            "emd_jsd_hors_choix_unique": emd_hors.get("composite"),
            "l1_hors_choix_unique": l1_hors.get("composite"),
        },
        "scores_bruts": {"emd_jsd": emd, "l1": l1},
        # Les scores bruts de la seconde lecture aussi : sans eux, `rejouer()` ne pourrait
        # recomposer qu'un seul des deux composites, et une formule rejouée laisserait le
        # second figé sous l'ANCIENNE formule — deux chiffres côte à côte qui ne se
        # comparent plus, sans que rien ne le dise.
        "scores_bruts_hors_choix_unique": {"emd_jsd": emd_hors, "l1": l1_hors},
        "choix_forces": choix_forces,
        "dimensions_non_mesurees": non_mesurees,
        "global": frames.global_view(attendu, cerema) if attendu else {},
        "detail": _detail_par_dimension(attendu, cerema) if attendu else {},
        "lecture": dict(stats),
    }
    _journaliser_lectures(contenu)
    return contenu


def _journaliser_lectures(contenu: dict) -> None:
    """Dit le succès, pas seulement l'échec — et alerte quand le composite tient aux forcés.

    Un scoring muet ne permet pas de distinguer « la seconde lecture a été calculée » de
    « elle ne l'est plus ». On journalise donc toujours les deux composites et le compte ;
    l'ERROR ne part que sur franchissement du seuil, une fois par scoring.
    """
    comp = contenu.get("composite") or {}
    forces = contenu.get("choix_forces") or {}
    principal, seconde = comp.get("emd_jsd"), comp.get("emd_jsd_hors_choix_unique")
    part = forces.get("part")
    logger.info(
        f"Score {contenu.get('execution')} — composite EMD {_texte(principal)} "
        f"(toutes décisions, n={forces.get('n_scorees')}) · "
        f"{_texte(seconde)} (hors itinéraire unique, n={forces.get('n_hors_choix_unique')}) "
        f"· choix forcés {forces.get('n')}"
        + (f" ({100 * part:.1f} %)" if part is not None else "")
    )
    if principal is None or seconde is None:
        return
    ecart = seconde - principal
    if abs(ecart) >= ECART_LECTURES_ALARME:
        logger.error(
            f"[ALARME] Composite dépendant des choix forcés : {contenu.get('execution')} "
            f"({contenu.get('experience')}) passe de {principal:.2f} à {seconde:.2f} "
            f"({ecart:+.2f} points EMD) quand on retire les {forces.get('n')} décisions à "
            f"itinéraire unique, soit {100 * (part or 0):.1f} % du périmètre scoré. "
            f"Le classement des bras n'est pas invariant à ce retrait : citer ce composite "
            f"sans sa seconde lecture attribuerait au décideur ce que l'offre lui imposait."
        )


def _texte(valeur: float | None) -> str:
    """« — » plutôt que « 0.00 » : dans ce dépôt, 0 est le score parfait, pas l'absence."""
    return "—" if valeur is None else f"{valeur:.2f}"


def _metrics() -> Any:
    """Le module ``calibration.metrics``, dépôt de calibration amorcé sur le path.

    Un simple ``from calibration import metrics`` ne suffit pas : seul
    ``import_calibration`` met `prompt_calibration/` sur ``sys.path``. Sans cette
    amorce, le rejeu hors-ligne — qui ne construit aucun ``Scorer``, donc n'appelle
    jamais ``scorer_pour`` — mourait en ``ModuleNotFoundError`` dès la première
    exécution déjà scorée : `score --toutes` et le bouton « Recalculer toutes les
    expériences » n'aboutissaient plus. Aucun appel réseau ici (R10).
    """
    calibration, erreur = sources.import_calibration("prompt_calibration")
    if calibration is None:
        raise ValueError(erreur)
    from calibration import metrics as m

    return m


def rejouer(scores: dict, formule: F.Formule) -> dict:
    """Recompose le composite sous une NOUVELLE formule, sans relire moves.csv (R6, R10).

    Exact parce que le composite est linéaire et que chaque s[dim] est stocké dans
    ``scores_bruts`` : ``weighted_composite`` refait la somme pondérée. Aucun appel
    réseau, aucun modèle.

    Lève ``ValueError`` si le moteur de loss est absent (R18) : l'appelant n'écrit rien.
    """
    m = _metrics()

    bruts = scores.get("scores_bruts") or {}
    emd = bruts.get("emd_jsd") or {}
    l1 = bruts.get("l1") or {}
    # Seconde lecture rejouée par le MÊME chemin (ticket 047) : les deux composites d'un
    # scores.json portent toujours la même formule. La laisser derrière produirait deux
    # chiffres côte à côte calculés sous deux pondérations, dont l'écart ne mesurerait plus
    # les choix forcés mais le changement de formule.
    bruts_hors = scores.get("scores_bruts_hors_choix_unique") or {}
    emd_hors = bruts_hors.get("emd_jsd") or {}
    l1_hors = bruts_hors.get("l1") or {}
    poids = formule.poids_scorer()
    nouveau = dict(scores)
    nouveau["formule"] = {"nom": formule.nom, "sha256": formule.sha256}
    nouveau["composite"] = dict(scores.get("composite") or {})
    nouveau["composite"]["emd_jsd"] = m.weighted_composite(emd, poids) if emd else None
    nouveau["composite"]["l1"] = m.weighted_composite(l1, poids) if l1 else None
    nouveau["composite"]["emd_jsd_hors_choix_unique"] = (
        m.weighted_composite(emd_hors, poids) if emd_hors else None
    )
    nouveau["composite"]["l1_hors_choix_unique"] = (
        m.weighted_composite(l1_hors, poids) if l1_hors else None
    )
    nouveau["genere_le"] = frames_now()
    nouveau["rejoue"] = True
    _journaliser_lectures(nouveau)
    return nouveau


def est_reference(scores: dict, registre: F.RegistreFormules) -> bool:
    """R7 — dérivé à la lecture : le SHA stocké est-il celui de la référence courante ?"""
    return (scores.get("formule") or {}).get("sha256") == registre.reference.sha256


def ecrire(dossier: str | Path, contenu: dict) -> Path:
    """Persiste scores.json (déterministe : clés triées, R10/R5)."""
    p = Path(dossier) / F_SCORES
    p.write_text(
        json.dumps(contenu, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )
    return p


def _couronnes_fantomes(scores: dict) -> bool:
    """Ticket 082 — ce `scores.json` porte-t-il une couronne de résidence non traduite ?

    Signature exacte de la panne : la ligne « hors référentiel » de la dimension
    `lieu_residence` porte une clé comme `1st_ring`, que l'ancien `normalize_place`
    fabriquait sur un libellé anglais et que la référence ne ventile pas. Les trois
    couronnes hors Toulouse manquent alors aux strates.

    Ce n'est pas un critère d'apparence — « moins de quatre strates » se produirait aussi
    sur un run légitimement petit. C'est la trace de la clé fautive elle-même.
    """
    strates = ((scores.get("detail") or {}).get("lieu_residence") or {}).get("strates")
    for strate in strates or []:
        if strate.get("cat") != frames.OFF_REFERENCE_ROW:
            continue
        if set(strate.get("categories") or {}) & frames.PLACE_CLES_FANTOMES:
            return True
    return False


def scores_perimes(dossier: str | Path) -> bool:
    """R17 — un scores.json calculé sur un moves.csv qui a changé depuis est périmé.

    Ticket 047 — l'est aussi celui qui ne porte PAS la seconde lecture. Le rejeu hors-ligne
    recompose les composites depuis les scores bruts stockés : un fichier antérieur au
    ticket n'a pas `scores_bruts_hors_choix_unique`, donc un rejeu le laisserait à « non
    mesuré » pour toujours, et tout l'historique resterait muet sur la grandeur que ce
    ticket rend obligatoire. Le déclarer périmé force un calcul complet — une fois.

    Ticket 082 — l'est enfin celui dont les couronnes de résidence n'ont pas été traduites.
    Même raisonnement, même remède : le rejeu ne recalcule QUE le composite, jamais le
    détail par strate. Sans ce critère, `--toutes` réécrirait les exécutions v6 scorées avec
    leurs pages amputées de trois couronnes sur quatre, et la correction n'atteindrait
    jamais un seul fichier publié.

    Ticket 081 — l'est aussi celui qui ne porte pas `perimetre_verifie`, c'est-à-dire tout
    score écrit avant que la règle R24 n'existe. Le rejeu hors-ligne ne relit jamais
    `moves.csv` : sans ce critère, un score calculé sur un journal tronqué se rejouerait
    indéfiniment sous les nouvelles formules, en gardant son composite faux et en ne
    déclenchant jamais le contrôle. Le calcul complet qu'il force est ce qui fait passer
    l'historique entier devant le garde-fou, une fois.

    Ticket 057 — l'est enfin celui dont `lecture` ne dit pas quelle coupe a été appliquée,
    donc tout score écrit quand la coupe au premier jour simulé était systématique. Le
    périmètre lui-même a changé : ces scores portent 2 347 décisions là où le journal en
    compte 3 154, et aucun rejeu de formule ne les corrigerait — il recompose les composites
    depuis des scores bruts calculés sur l'ancien périmètre. Même remède que les précédents :
    un calcul complet, une fois.
    """
    dossier = Path(dossier)
    scores = _lire_json(dossier / F_SCORES)
    if not scores:
        return True
    if not (scores.get("scores_bruts_hors_choix_unique") or {}).get("emd_jsd"):
        return True
    if _couronnes_fantomes(scores):
        return True
    if not scores.get("perimetre_verifie"):
        return True
    if not (scores.get("lecture") or {}).get("coupe"):
        return True
    return scores.get("moves_sha256") != _sha256_fichier(dossier / F_MOVES)


def invalider(dossier: str | Path, motif: str) -> Path | None:
    """Retire de la circulation un `scores.json` que la règle refuse désormais (R24).

    Renommé, pas supprimé : le fichier reste auditable — c'est lui qui a produit le chiffre
    publié, et l'effacer rendrait la correction impossible à retracer. La page HTML, elle,
    est supprimée : elle n'a pas d'autre rôle que d'être lue, et un rendu qui survit à son
    score se lit comme un score valide.
    """
    dossier = Path(dossier)
    source = dossier / F_SCORES
    if not source.is_file():
        return None
    cible = dossier / "scores.invalide.json"
    contenu = _lire_json(source)
    contenu["invalide"] = {"motif": motif, "le": frames_now()}
    cible.write_text(
        json.dumps(contenu, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )
    source.unlink()
    (dossier / "synthese_scores.html").unlink(missing_ok=True)
    logger.error(
        f"[ALARME] Score invalidé — {dossier.name} : {motif}. Composite publié "
        f"{(contenu.get('composite') or {}).get('emd_jsd')} écarté ; l'ancien fichier est "
        f"conservé sous {cible.name} pour audit, la page de synthèse est supprimée."
    )
    return cible


def score_execution(
    dossier: str | Path,
    formule: F.Formule | None = None,
    registre: F.RegistreFormules | None = None,
    scorer: Any | None = None,
) -> Path | None:
    """Score une exécution terminée et écrit scores.json. Renvoie le chemin, ou None
    si l'exécution n'est pas scorable (R21) ou le moteur absent (R18)."""
    dossier = Path(dossier)
    registre = registre or F.charger()
    formule = formule or registre.reference
    try:
        contenu = calculer(dossier, formule, scorer=scorer)
    except JournalIncomplet as exc:
        # R24 — le refus ne suffit pas : un `scores.json` calculé AVANT la règle est encore
        # sur le disque, lisible par la page et le tableau comme s'il était valide. C'est
        # exactement ce qui s'est produit le 2026-09-12. On le retire de la circulation.
        invalider(dossier, str(exc))
        return None
    except ValueError as exc:
        logger.info(f"[score] {dossier.name} non scoré : {exc}")
        return None
    chemin = ecrire(dossier, contenu)
    logger.info(
        f"[score] {contenu['experience']}/{contenu['execution']} scoré sous "
        f"formule {formule.nom} ({formule.sha256[:12]}) : "
        f"composite emd_jsd={contenu['composite']['emd_jsd']}"
    )
    return chemin


def scorer_a_la_cloture(dossier: str | Path) -> Path | None:
    """Score une exécution qui vient d'être clôturée, et écrit sa page (R21, R23).

    Appelée par le runner juste après la synthèse. **Fail-open par construction** :
    elle ne lève jamais. Le scoring est un rendu — hors-ligne, ~0,2 s pour 2 700
    décisions — et son échec ne doit pas transformer une exécution réussie en échec.
    Quand il échoue, l'exécution reste `terminee` sans `scores.json`, la table
    affiche « — », et le bouton « Recalculer toutes les expériences » reste la
    porte de secours.

    Ne fait rien si l'exécution n'est pas `terminee` (R21) : une exécution arrêtée
    ou en pause n'est pas scorable, même largement remplie.
    """
    dossier = Path(dossier)
    synthese = _lire_json(dossier / F_SYNTHESE)
    if not est_terminee(synthese):
        logger.info(
            f"[score] {dossier.name} non scoré à la clôture : exécution non terminée "
            f"(état {(synthese.get('etat') or {}).get('etat')!r})"
        )
        return None
    debut = time.monotonic()
    logger.info(f"[score] Scoring de clôture de {dossier.name} — début")
    try:
        registre = F.charger()
        chemin = score_execution(dossier, registre.reference, registre)
        if chemin is None:
            logger.error(
                f"[ALARME] Scoring de clôture sans résultat — {dossier.parent.parent.name}/"
                f"{dossier.name} : exécution non scorable ou moteur de loss absent ; "
                f"l'exécution reste terminée, sans score"
            )
            return None
        from experiences import rendu_scores

        rendu_scores.ecrire(dossier, registre)
        composite = (_lire_json(chemin).get("composite") or {}).get("emd_jsd")
        logger.info(
            f"[score] Scoring de clôture de {dossier.name} terminé en "
            f"{time.monotonic() - debut:.1f} s — composite emd_jsd={composite}"
        )
        return chemin
    except Exception as exc:  # noqa: BLE001 — fail-open : l'exécution reste terminée
        logger.error(
            f"[ALARME] Scoring de clôture échoué — {dossier.parent.parent.name}/"
            f"{dossier.name} après {time.monotonic() - debut:.1f} s : "
            f"{type(exc).__name__}: {exc} ; l'exécution reste terminée, sans score "
            f"(relancer « Recalculer toutes les expériences »)"
        )
        return None


def _executions(racine: Path):
    """Itère les dossiers d'exécution sous data/experiences/*/executions/*."""
    for exp in sorted(racine.iterdir()) if racine.is_dir() else []:
        execs = exp / "executions"
        if not execs.is_dir():
            continue
        for d in sorted(execs.iterdir()):
            if d.is_dir():
                yield d


def rescorer_tout(
    formule: F.Formule | None = None,
    registre: F.RegistreFormules | None = None,
    racine: Path | None = None,
) -> dict:
    """Recalcule toutes les exécutions terminées sous ``formule`` (R10, R22).

    Hors-ligne : si un scores.json existe et que le moves.csv n'a pas changé, on
    **rejoue** depuis les scores bruts (R6) — aucun ``Scorer`` reconstruit, aucun
    fichier relu. Sinon on calcule à plein. Aucun appel réseau dans les deux cas.
    """
    registre = registre or F.charger()
    formule = formule or registre.reference
    racine = racine or (REPO_ROOT / "data" / "experiences")
    scorer = None  # construit paresseusement, seulement si un calcul complet est requis
    bilan = {"rejouees": 0, "calculees": 0, "ignorees": 0}
    logger.info(
        f"[score] Recalcul global sous formule {formule.nom} "
        f"({formule.sha256[:12]}) — début"
    )
    for dossier in _executions(racine):
        synthese = _lire_json(dossier / F_SYNTHESE)
        if not est_terminee(synthese):
            bilan["ignorees"] += 1
            continue
        existant = _lire_json(dossier / F_SCORES)
        if existant and not scores_perimes(dossier):
            try:
                contenu = rejouer(existant, formule)
            except ValueError as exc:  # moteur absent (R18) : rien d'écrit, on s'arrête
                logger.error(
                    f"[ALARME] Rejeu impossible — moteur de loss absent : {exc}"
                )
                break
            ecrire(dossier, contenu)
            bilan["rejouees"] += 1
            continue
        if scorer is None:
            scorer, erreur = scorer_pour(formule)
            if scorer is None:
                logger.error(
                    f"[ALARME] Recalcul impossible — moteur de loss absent : {erreur}"
                )
                break
        if score_execution(dossier, formule, registre, scorer=scorer):
            bilan["calculees"] += 1
        else:
            bilan["ignorees"] += 1
    logger.info(
        f"[score] Recalcul global terminé : {bilan['rejouees']} rejouées, "
        f"{bilan['calculees']} calculées, {bilan['ignorees']} ignorées"
    )
    return bilan


def frames_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "TOLERANCE_JOURNAL",
    "JournalIncomplet",
    "calculer",
    "ecrire",
    "est_reference",
    "est_terminee",
    "invalider",
    "mesurer_perimetre",
    "rejouer",
    "rescorer_tout",
    "score_execution",
    "scorer_a_la_cloture",
    "scorer_pour",
    "scores_perimes",
    "verifier_perimetre",
    "volet_pour",
]
