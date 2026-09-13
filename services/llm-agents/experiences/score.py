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

from experiences.chemins import racine_depot
from typing import Any

from experiences import formule as F
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
    rows, stats = frames.read_moves(moves, EXCLURE_METHODES, first_day_only=True)

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
    rows_hors, _ = frames.read_moves(
        moves, EXCLURE_METHODES + [METHODE_CHOIX_UNIQUE_MOVES], first_day_only=True
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
        "perimetre": "lecture du score : premier jour simulé, tentative la plus récente",
        "n_execution": forces_execution.get("n"),
        "part_execution": forces_execution.get("part"),
        "perimetre_execution": "toutes les décisions archivées (synthese.json)",
        "lecture": (
            "décisions à itinéraire unique : une seule option existait, personne n'a choisi. "
            "Elles RESTENT dans le composite principal — la journée a eu lieu — et sont "
            "retirées de la seconde lecture. Leur nombre dépend du bras."
        ),
    }

    couverture = (
        (synthese.get("parts_modales") or {}).get("couverture")
        or synthese.get("couverture")
        or {}
    )

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


def scores_perimes(dossier: str | Path) -> bool:
    """R17 — un scores.json calculé sur un moves.csv qui a changé depuis est périmé.

    Ticket 047 — l'est aussi celui qui ne porte PAS la seconde lecture. Le rejeu hors-ligne
    recompose les composites depuis les scores bruts stockés : un fichier antérieur au
    ticket n'a pas `scores_bruts_hors_choix_unique`, donc un rejeu le laisserait à « non
    mesuré » pour toujours, et tout l'historique resterait muet sur la grandeur que ce
    ticket rend obligatoire. Le déclarer périmé force un calcul complet — une fois.
    """
    dossier = Path(dossier)
    scores = _lire_json(dossier / F_SCORES)
    if not scores:
        return True
    if not (scores.get("scores_bruts_hors_choix_unique") or {}).get("emd_jsd"):
        return True
    return scores.get("moves_sha256") != _sha256_fichier(dossier / F_MOVES)


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
    "calculer",
    "ecrire",
    "est_reference",
    "est_terminee",
    "rejouer",
    "rescorer_tout",
    "score_execution",
    "scorer_a_la_cloture",
    "scorer_pour",
    "scores_perimes",
    "volet_pour",
]
