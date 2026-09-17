"""Le journal des mouvements d'une exécution — écriture d'une ligne, et régénération (ticket 081).

`moves.csv` est le SUBSTRAT DU SCORE : `score.calculer` ne lit que lui. Or il n'était écrit
que sur le chemin d'une décision **neuve**. Une reprise à froid resservait les décisions
archivées sans écrire une ligne, et le journal restait tel que le processus interrompu
l'avait laissé. L'exécution `2026-09-12_11_24_28` a ainsi été scorée à 5,35 sur 274 lignes
quand son archive en portait 3 299 ; rescorée sur le journal reconstitué, elle vaut 6,17.
Le chiffre avait déjà été cité dans trois documents.

Ce module ferme la panne par sa cause, pas par son symptôme. Il porte **l'unique** fonction
qui écrit une ligne de journal, `ecrire_ligne`, et les deux chemins l'appellent : le runner
quand la décision vient d'être prise, la régénération quand elle est relue de l'archive.
Deux écritures qui divergent est exactement la classe de bug que ce ticket referme — les
faire partager le code est le seul moyen qu'elles ne redivergent pas.

Une ligne se reconstitue **entièrement** depuis la trace archivée et le jeu scellé :
la trace porte la retenue, les présentées, la distribution, les sources, les écartées, la
contrainte de chaîne et l'anticipation ; le jeu porte les `TravelPlan` complets, donc les
distances. Rien n'est emprunté à une exécution sœur, rien n'est approximé.

Ce que la régénération ne peut PAS rendre, et qu'elle ne feint pas de rendre :
l'archive n'horodate pas les décisions une par une (`archive.ajouter_decision` écrit la
trace telle quelle), donc la colonne « Heure de calcul » d'un journal régénéré est uniforme.
Sans doublon dans le fichier reconstruit, `frames.latest_attempts` n'en souffre pas, mais le
drapeau `reprise` de la lecture du score disparaît. Les interruptions de `synthese.json` le
portent toujours, et elles sont la source de vérité sur ce point.
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import yaml
from experiences import decision as D
from experiences.archive import (
    METHODE_INEXPLOITABLE,
    METHODE_NON_COUVERT,
    Execution,
)
from loguru import logger
from models import Person

F_MOVES = "moves.csv"
SUFFIXE_REGENERATION = ".regen"

# Méthodes archivées qui n'ont JAMAIS produit de ligne de journal, en vivant comme à la
# régénération : le jeu ne couvre pas le déplacement, ou les moteurs n'ont proposé aucun
# itinéraire. Elles sont archivées (elles expliquent un trou dans la couverture) mais il n'y
# a ni mode choisi ni distance à écrire. Les compter comme sautées, et non les taire, est ce
# qui permet de vérifier après coup que le journal est complet.
METHODES_SANS_LIGNE = (METHODE_NON_COUVERT, METHODE_INEXPLOITABLE)


# ── L'étiquette du décideur, telle qu'elle s'écrit dans « Méthode de sélection » ──────────


@dataclass(frozen=True)
class EtiquetteDecideur:
    """De quoi étiqueter une ligne sans construire le décideur réel.

    `_methode_moves` ne consulte du décideur que son nom et son `sans_quota`. Reconstruire
    un `DecideurPasserelle` pour régénérer un journal exigerait un `LlmAgent`, donc une
    configuration réseau, pour écrire un libellé : la régénération deviendrait indisponible
    hors ligne, précisément quand on en a besoin. Cette étiquette se lit dans
    `execution.yaml`, qui fige le décideur RÉELLEMENT utilisé (R6).
    """

    nom: str
    sans_quota: bool

    @classmethod
    def depuis_execution(cls, config: dict) -> EtiquetteDecideur:
        regime = config.get("regime_applique") or {}
        experience = config.get("experience") or {}
        type_decideur = (experience.get("decideur") or {}).get("type")
        # Seule la passerelle consomme un quota (`decideurs.DecideurPasserelle`) ; c'est
        # cette seule valeur qui décide entre l'étiquette « LLM » et « Décideur <nom> ».
        # Vérifié sur les journaux archivés : `passerelle` → « LLM », `antigravity` →
        # « Décideur antigravity:gemini-3.8-flash », `modele` → « Décideur modele:rf@… ».
        return cls(
            nom=str(regime.get("decideur") or type_decideur or "?"),
            sans_quota=type_decideur != "passerelle",
        )


def methode_moves(methode: str, decideur) -> str:
    """Libellé « Méthode de sélection » d'une ligne de journal.

    Prend la MÉTHODE (une chaîne de trace), pas un objet `Decision` : c'est ce qui permet
    au runner et à la régénération d'appeler la même fonction. `decideur` est le décideur
    réel ou une `EtiquetteDecideur` — seuls `nom` et `sans_quota` sont consultés.
    """
    if methode == D.METHODE_CHOIX_UNIQUE:
        return "Un seul itinéraire disponible"
    if methode == D.METHODE_SANS_SOLUTION:
        return "Pas de solution de déplacement"
    if methode == D.METHODE_REPLI_UNIFORME:
        return "LLM Error (Default index) — repli uniforme"
    if methode == D.METHODE_MODELE_NON_IMPUTABLE:
        # Non-décision du modèle (hors domaine) : sans mode choisi, exclue du score.
        return "Modèle : hors domaine (non imputable)"
    return (
        "LLM"
        if not getattr(decideur, "sans_quota", True)
        else f"Décideur {getattr(decideur, 'nom', '?')}"
    )


# ── L'unique écriture d'une ligne ────────────────────────────────────────────────────────


def _par_code(props: Sequence[D.Proposition], code: str | None) -> D.Proposition | None:
    return next((p for p in props if p.code == code), None) if code else None


async def ecrire_ligne(
    moves,
    *,
    personne: Person,
    trace: dict,
    props: Sequence[D.Proposition],
    decideur,
) -> None:
    """Écrit UNE ligne de `moves.csv` depuis une trace de décision et les propositions du jeu.

    Point de passage unique (ticket 081) : le runner l'appelle sur la trace qu'il vient de
    construire, la régénération sur celle qu'elle relit de l'archive. Les deux produisent la
    même ligne, parce que c'est le même code.

    `props` est la liste BRUTE du jeu, pas les présentées : le journal rapporte l'offre telle
    qu'elle existait (« Modes proposés », « Plus rapide », « Options présentées »), et non ce
    qui a survécu au filtrage de la chaîne des véhicules et au plafond de candidats.
    """
    retenue = _par_code(props, (trace.get("retenue") or {}).get("code"))
    plan = retenue.plan if retenue is not None else None
    plus_rapide = min(
        (p.plan for p in props),
        key=lambda pl: pl.duration or float("inf"),
        default=None,
    )
    await moves.ecrire(
        person=personne,
        plan=plan,
        purpose=trace.get("purpose"),
        selection_method=methode_moves(str(trace.get("methode") or ""), decideur),
        provider_model=str(trace.get("fournisseur") or ""),
        faster_itinerary=plus_rapide,
        reasoning=str(trace.get("raison") or ""),
        chain_constraint=trace.get("contrainte_chaine", ""),
        anticipation=trace.get("anticipation", "") or "",
        move_id=f"{trace.get('person_id')}:{trace.get('activity_id')}",
        simulated_time=trace.get("timestamp"),
        start_time=plan.start_time if plan is not None else None,
        available_options=[p.plan for p in props],
        activity_id=trace.get("activity_id"),
        # `{}` et `None` sont traités à l'identique par `_mode_probability_cells` (cellules
        # vides) : une décision sans distribution ne fabrique pas de 0, qui signifierait
        # « le modèle a explicitement écarté ce mode ».
        mode_probabilities=trace.get("distribution") or None,
        sources=",".join(
            f"{k}:{v}"
            for k, v in sorted(
                Counter(
                    str(v).split(":")[0] for v in (trace.get("sources") or {}).values()
                ).items()
            )
        ),
        ecartees=D.resumer_ecartees(trace.get("ecartees") or []),
        lot=str(trace.get("identifiant_lot") or ""),
    )


# ── Régénération intégrale ───────────────────────────────────────────────────────────────


class JournalIrregenerable(ValueError):
    """La régénération ne peut pas être fidèle : elle n'est pas tentée."""


def _verifier_empreintes(config: dict, jeu, info_population) -> None:
    """Refuse de régénérer depuis une autre cohorte ou un autre jeu que ceux de l'exécution.

    Reconstituer un journal à partir d'une population voisine produirait un fichier
    plausible, scorable, et faux — exactement la corruption silencieuse que ce ticket
    referme. Le contrôle porte sur les empreintes figées dans `execution.yaml` (E19).
    """
    empreintes = config.get("empreintes") or {}
    attendu_jeu = (empreintes.get("jeu") or {}).get("sha256")
    if attendu_jeu and jeu.empreinte and attendu_jeu != jeu.empreinte:
        raise JournalIrregenerable(
            f"jeu différent de celui de l'exécution : l'archive cite "
            f"{attendu_jeu[:12]}…, le jeu fourni fait {jeu.empreinte[:12]}… "
            f"({jeu.nom}). Régénérer le journal depuis un autre jeu produirait des "
            f"distances et des options qui n'ont jamais été présentées."
        )
    attendu_pop = (empreintes.get("population") or {}).get("fichier_sha256")
    reel_pop = getattr(info_population, "fichier_sha256", None)
    if attendu_pop and reel_pop and attendu_pop != reel_pop:
        raise JournalIrregenerable(
            f"population différente de celle de l'exécution : l'archive cite "
            f"{attendu_pop[:12]}…, la cohorte fournie fait {reel_pop[:12]}… "
            f"({getattr(info_population, 'nom', '?')}). Les colonnes de persona "
            f"décriraient d'autres personnes que celles qui ont décidé."
        )


@contextmanager
def _reglages_figes(config: dict):
    """Applique le temps d'une régénération les réglages que `moves.csv` recopie du processus.

    `MoveLogger.log_move` ne reçoit pas tout par arguments : « Mémoire à long terme » et
    « Température » sont lues dans `settings`, que `cli.cmd_lancer` avait positionnées depuis
    la définition de l'expérience. Régénérer sans elles produit un journal qui décrit le
    processus de régénération au lieu du run — mesuré sur une exécution `memoire: false`, la
    colonne passait à `True` sur les 3 161 lignes.

    Les valeurs viennent du snapshot `execution.yaml`, qui fige le régime RÉELLEMENT appliqué
    (R6), et sont rendues telles quelles ensuite : appelée depuis le runner, où elles sont
    déjà correctes, la régénération ne change rien.
    """
    from settings import settings

    exp = config.get("experience") or {}
    decideur = exp.get("decideur") or {}
    avant_memoire = settings.agent.long_term_memory_enabled
    avant_params = dict(settings.agent.llm_params)
    try:
        if "memoire" in exp:
            settings.agent.long_term_memory_enabled = bool(exp.get("memoire"))
        if decideur.get("type") in ("passerelle", "antigravity"):
            settings.agent.llm_params = {
                **settings.agent.llm_params,
                **(decideur.get("parametres") or {}),
            }
        yield
    finally:
        settings.agent.long_term_memory_enabled = avant_memoire
        settings.agent.llm_params = avant_params


def _reference_existante(chemin: Path) -> str | None:
    """La valeur de « Référence » que porte le journal actuel, s'il en porte une.

    Cette colonne nomme le processus qui a produit les décisions. Une régénération produit le
    FICHIER, pas les décisions : y écrire la date du jour ferait dire au journal qu'il vient
    d'un run qui n'a jamais rien décidé. On reconduit donc la valeur d'origine.
    """
    if not Path(chemin).is_file():
        return None
    import csv

    with Path(chemin).open(encoding="utf-8") as fh:
        for ligne in csv.DictReader(fh):
            valeur = (ligne.get("Référence") or "").strip()
            return valeur or None
    return None


def _reecrire_reference(chemin: Path, reference: str) -> None:
    import csv

    with Path(chemin).open(encoding="utf-8") as fh:
        lecteur = csv.DictReader(fh)
        colonnes = list(lecteur.fieldnames or [])
        lignes = list(lecteur)
    if "Référence" not in colonnes:
        return
    for ligne in lignes:
        ligne["Référence"] = reference
    with Path(chemin).open("w", encoding="utf-8", newline="") as fh:
        redacteur = csv.DictWriter(fh, fieldnames=colonnes)
        redacteur.writeheader()
        redacteur.writerows(lignes)


async def regenerer(
    execution: Execution,
    jeu,
    personnes: Sequence[Person],
    decideur,
    *,
    info_population=None,
) -> dict:
    """Reconstruit intégralement `moves.csv` depuis `decisions.jsonl` et le jeu scellé.

    Écrit dans un fichier voisin puis remplace atomiquement : le journal existant n'est
    jamais détruit par une régénération qui échoue.

    Rend les compteurs — un programme muet quand tout va bien ne permet pas de distinguer
    « ça a marché » de « ça ne tourne plus ».
    """
    if info_population is not None:
        _verifier_empreintes(execution.config, jeu, info_population)

    debut = time.monotonic()
    cible = execution.dossier / F_MOVES
    provisoire = execution.dossier / (F_MOVES + SUFFIXE_REGENERATION)
    provisoire.unlink(missing_ok=True)
    par_personne = {p.person_id: p for p in personnes}
    avant = _compter_lignes(cible)
    reference = _reference_existante(cible)
    logger.info(
        f"[journal] Régénération de {execution.nom} — début : "
        f"{len(execution.decisions)} décisions archivées, {avant} ligne(s) au journal actuel"
    )

    from experiences.archive import JournalMoves

    moves = JournalMoves(provisoire)
    compteurs = Counter()
    absents: list[str] = []
    with _reglages_figes(execution.config):
        for trace in execution.decisions:
            methode = str(trace.get("methode") or "")
            if methode in METHODES_SANS_LIGNE:
                compteurs[f"sautees_{methode}"] += 1
                continue
            person_id = str(trace.get("person_id"))
            activity_id = str(trace.get("activity_id"))
            personne = par_personne.get(person_id)
            if personne is None:
                compteurs["persona_absente"] += 1
                absents.append(f"{person_id}:{activity_id}")
                continue
            props = jeu.propositions(person_id, activity_id)
            if not props:
                # Le jeu ne porte plus ce déplacement alors qu'une décision l'a tranché : le
                # journal serait amputé sans le dire. On refuse de l'écrire silencieusement.
                compteurs["sans_proposition"] += 1
                absents.append(f"{person_id}:{activity_id}")
                continue
            await ecrire_ligne(
                moves, personne=personne, trace=trace, props=props, decideur=decideur
            )
            compteurs["reconstruites"] += 1

    if absents:
        logger.error(
            f"[ALARME] Journal régénéré incomplet — {execution.nom} : "
            f"{len(absents)} décision(s) archivée(s) sans persona ni proposition dans le "
            f"couple (population, jeu) fourni ; le journal reconstruit leur manquera. "
            f"Premiers cas : {', '.join(absents[:10])}"
            f"{'…' if len(absents) > 10 else ''}"
        )

    if not provisoire.exists():
        # Aucune ligne écrite : ne jamais remplacer un journal existant par rien.
        raise JournalIrregenerable(
            f"aucune ligne reconstruite pour {execution.nom} — journal existant conservé "
            f"({avant} ligne(s)). Décisions archivées : {len(execution.decisions)}."
        )
    if reference:
        _reecrire_reference(provisoire, reference)
    os.replace(provisoire, cible)
    apres = _compter_lignes(cible)
    duree = time.monotonic() - debut
    logger.info(
        f"[journal] Régénération de {execution.nom} terminée en {duree:.1f} s — "
        f"{avant} → {apres} ligne(s) ; reconstruites {compteurs['reconstruites']}, "
        f"non couvertes {compteurs[f'sautees_{METHODE_NON_COUVERT}']}, "
        f"inexploitables {compteurs[f'sautees_{METHODE_INEXPLOITABLE}']}, "
        f"sans proposition {compteurs['sans_proposition']}, "
        f"persona absente {compteurs['persona_absente']}"
    )
    return {
        "execution": execution.nom,
        "lignes_avant": avant,
        "lignes_apres": apres,
        "decisions_archivees": len(execution.decisions),
        "duree_s": round(duree, 3),
        **{k: int(v) for k, v in compteurs.items()},
    }


def _compter_lignes(chemin: Path) -> int:
    """Lignes de données d'un CSV (en-tête exclu) ; 0 si le fichier n'existe pas."""
    if not Path(chemin).is_file():
        return 0
    import csv

    with Path(chemin).open(encoding="utf-8") as fh:
        return sum(1 for _ in csv.DictReader(fh))


# ── Vérification (balayage) ──────────────────────────────────────────────────────────────


def _lire_json(p: Path) -> dict:
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def verifier(dossier: str | Path) -> dict:
    """Constat, sans jugement d'écriture : combien de lignes, combien de décisions, l'écart.

    Ne lève pas et n'écrit rien : c'est le balayage. La RÈGLE, elle, est dans
    `score.verifier_perimetre`, au seul endroit qui peut refuser un score.
    """
    from experiences import score as S

    dossier = Path(dossier)
    synthese = _lire_json(dossier / "synthese.json")
    lignes = _compter_lignes(dossier / F_MOVES)
    constat = S.mesurer_perimetre(lignes, synthese)
    constat["execution"] = synthese.get("execution") or dossier.name
    constat["experience"] = synthese.get("experience")
    constat["etat"] = (synthese.get("etat") or {}).get("etat")
    constat["dossier"] = str(dossier)
    constat["interruptions"] = [
        str(i.get("cause")) for i in (synthese.get("interruptions") or [])
    ]
    return constat


def executions(racine: str | Path):
    """Itère les dossiers d'exécution sous `<racine>/*/executions/*`."""
    racine = Path(racine)
    for exp in sorted(racine.iterdir()) if racine.is_dir() else []:
        execs = exp / "executions"
        if not execs.is_dir():
            continue
        for d in sorted(execs.iterdir()):
            if d.is_dir():
                yield d


# ── Résolution du jeu et de la population d'une exécution archivée ───────────────────────


def resoudre_sources(
    execution: Execution,
    *,
    jeu: str | Path | None = None,
    population: str | Path | None = None,
    motif_archive: str | None = None,
):
    """(Jeu, personnes, InfoPopulation) d'une exécution, pour la régénérer.

    Les chemins figés dans `execution.yaml` sont ceux du CONTENEUR (`/data/eqasim-output/…`)
    et n'existent pas sur l'hôte : `--jeu` et `--population` les remplacent. Les empreintes
    sont vérifiées ensuite par `regenerer`, donc un chemin fourni à tort est refusé, pas subi.
    """
    from experiences.jeu import Jeu
    from experiences.population import charger_population, info_population

    config = execution.config
    exp = config.get("experience") or {}

    chemin_jeu = Path(jeu) if jeu else None
    if chemin_jeu is None:
        declare = (exp.get("jeu") or {}).get("dossier")
        nom = (exp.get("jeu") or {}).get("nom")
        for candidat in (declare, f"data/jeux/{nom}" if nom else None):
            if candidat and Path(candidat).is_dir():
                chemin_jeu = Path(candidat)
                break
    if chemin_jeu is None:
        raise JournalIrregenerable(
            f"jeu introuvable pour {execution.nom} : l'archive cite "
            f"{(exp.get('jeu') or {}).get('nom')!r}, dont le dossier n'est pas résoluble "
            f"sur cet hôte. Le préciser avec `--jeu <dossier>`."
        )

    chemin_pop = Path(population) if population else None
    if chemin_pop is None:
        declare = (exp.get("population") or {}).get("chemin")
        if declare and Path(declare).exists():
            chemin_pop = Path(declare)
    if chemin_pop is None:
        raise JournalIrregenerable(
            f"population introuvable pour {execution.nom} : l'archive cite "
            f"{(exp.get('population') or {}).get('chemin')!r} (chemin conteneur). "
            f"La préciser avec `--population <dossier>`."
        )

    objet_jeu = Jeu.charger(chemin_jeu, archive_confirmee=motif_archive)
    info = info_population(chemin_pop, archivee_confirmee=motif_archive)
    personnes, _ = charger_population(chemin_pop, archivee_confirmee=motif_archive)
    return objet_jeu, personnes, info


def ouvrir(dossier: str | Path, *, motif_archive: str | None = None) -> Execution:
    """Ouvre une exécution, y compris sous archive froide si un motif est donné."""
    from experiences import froid

    froid.verifier(
        dossier,
        motif_archive,
        quoi="une exécution archivée",
        comment_lever='passer `--motif-archive "<motif>"`',
    )
    return Execution.ouvrir(dossier)


def config_de(dossier: str | Path) -> dict:
    """`execution.yaml` brut, sans passer par `Execution.ouvrir` (pas de lecture de décisions)."""
    p = Path(dossier) / "execution.yaml"
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}


__all__ = [
    "METHODES_SANS_LIGNE",
    "EtiquetteDecideur",
    "JournalIrregenerable",
    "config_de",
    "ecrire_ligne",
    "executions",
    "methode_moves",
    "ouvrir",
    "regenerer",
    "resoudre_sources",
    "verifier",
]
