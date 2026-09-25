"""Ce qu'une journée simulée dit d'un persona — ticket 093, lot 2.

Contrat : `specs/ticket_093/tests.md`.

CE QUE CE MODULE MESURE
-----------------------
Quatre familles, et la première conditionne la lecture des autres :

1. **Choix modal**, avec la part des trajets RÉELLEMENT DÉCIDÉS. Sans elle, « voiture 100 % »
   désigne indifféremment un choix et une absence d'alternative — c'est ce qui rendait deux des
   cinq personas du run `2026-09-16_15_58` illisibles.
2. **Habitude et rupture**, par ACTIVITÉ. Le trajet domicile-travail et le trajet de loisir n'ont
   aucune raison de basculer ensemble, et les agréger masquerait le changement cherché.
3. **Mémoire** : vivier de rappel, opérations de concept, durée de vie des souvenirs.
4. **Choc** : exposés, minutes injectées, et si le souvenir du choc est SERVI à la décision — un
   souvenir écrit mais jamais rappelé ne change rien à un comportement. Le suivi du souvenir
   dans le foyer, jour après jour, vit dans `souvenir.py` (analyse du 2026-09-25).

FLUX ET ÉTAT, ET POURQUOI LA DISTINCTION COMPTE
-----------------------------------------------
Un **flux** se lit dans un journal daté : il se recalcule à l'identique, toujours. Un **état** ne
se reconstitue pas après coup — la `force` d'un souvenir croît à chaque rappel, donc la médiane
calculée aujourd'hui sur les souvenirs du jour 2 n'est pas celle qu'ils avaient au jour 2. Les
états sont donc lus dans le **point de reprise** qui clôt la journée, et restent vides tant qu'il
n'existe pas. Sans cette règle, une valeur déjà écrite bougerait rétroactivement à chaque
recalcul, et la continuité de la reprise serait fausse là où elle a l'air juste.

LA JOURNÉE SIMULÉE
------------------
Elle commence à **3 h**, comme le point de reprise du ticket 075 : à cette heure les tampons sont
vides et presque personne n'est en trajet. Un retour à 00 h 30 appartient donc à la soirée de la
veille.

DEUX REPÈRES TEMPORELS, ET ILS NE DISENT PAS LA MÊME CHOSE
----------------------------------------------------------
`moves.csv` porte deux instants, et les confondre fausse tout :

- **`Temps simulé`** est l'instant où la DÉCISION a été prise. Au bootstrap, les cinq agents du
  run de référence y portent tous `2026-03-16 05:00:01` — l'instant du `/init`.
- **`Heure de départ`** est l'instant où le TRAJET part.

L'écart n'est pas un détail de format. Mesuré sur `2026-09-16_15_58` : 30 lignes sur 270 écartent
les deux repères de plus d'une heure et demie, dont **19 exactement de 48 heures** — des décisions
prises le samedi 21 mars pour des départs reportés au lundi 23, la simulation ne faisant rouler
personne le week-end.

D'où la règle, et elle se lit dans les deux sens :

| Usage | Repère | Ce qu'on casserait avec l'autre |
|---|---|---|
| **Dédupliquer** le rejeu | `Temps simulé` | deux décisions distinctes d'une même activité fusionneraient |
| **Dater la journée** vécue | `Heure de départ` | une journée « samedi » à 19 trajets apparaîtrait, et le lundi en perdrait 19 sur 35 |

⚠ La colonne `Jour relatif au choc` de `moves.csv` n'est **jamais** lue ici, et c'est délibéré :
elle mélange deux conventions si la configuration du choc a bougé pendant le run. Les jours
relatifs au choc se redérivent des horodatages de `chocs.jsonl`.

Et « la veille » est le jour **vécu** précédent. Mesuré sur le run de référence : les dates vont
du 16 au 27 mars en sautant les week-ends, dont les départs sont reportés au lundi. Comparer au
jour calendaire précédent viderait la reprise de la veille tous les lundis — un jour sur cinq —
pour un week-end où l'agent n'a rien vécu et n'a donc rien pu reprendre.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Sequence

from scripts.analysis.memoire.sources import MODES, Trajet, lire_ltm, lire_moves

# Heure à laquelle bascule la journée simulée. Même frontière que le point de reprise
# (ticket 075) : tampons vides, presque personne en trajet.
FRONTIERE_JOUR_H = 3

# Fenêtre de l'habitude, en jours OÙ L'ACTIVITÉ A ÉTÉ OBSERVÉE — pas en jours simulés. Un agent
# qui ne sort qu'un jour sur trois a ainsi la même profondeur d'habitude que les autres, étalée
# sur plus de jours ; une fenêtre en jours simulés aurait dit son assiduité plutôt que son
# habitude.
FENETRE_HABITUDE = 5

OPERATIONS_CONCEPT = ("créé", "confirmé", "précisé", "contredit")


# ── Le calendrier simulé ──────────────────────────────────────────────────────────────


def journee_du_moment(horodatage: str) -> str | None:
    """Journée simulée d'un instant « AAAA-MM-JJ HH:MM:SS », ou d'une date déjà journalière.

    ⚠ **Une date nue ne se décale pas.** Défaut trouvé en écrivant les tests : `sim_day` vaut
    « 2026-03-16 » dans `trace_rappel.jsonl` et dans la trace des opérations — c'est DÉJÀ une
    journée, pas un instant. Lui appliquer la frontière de 3 h la lisait comme minuit et la
    reculait d'un jour : tout le vivier de rappel et toutes les opérations de concept se
    retrouvaient décalés d'une journée par rapport aux trajets, sans que rien ne le signale.

    ⚠ Ces journées-là sont datées par leur producteur en UTC calendaire, et non à la frontière
    de 3 h. L'écart ne peut concerner qu'un rappel survenu entre minuit et 3 h du matin ; il est
    dit ici plutôt que corrigé, faute d'avoir le fuseau du run sous la main.

    `None` si la valeur n'est pas une date lisible — jamais un préfixe de dix caractères pris au
    hasard dans une chaîne quelconque.
    """
    texte = (horodatage or "").strip().replace("T", " ")
    if len(texte) < 10:
        return None
    if len(texte) == 10:
        try:
            return date.fromisoformat(texte).isoformat()
        except ValueError:
            return None
    try:
        quand = datetime.fromisoformat(texte[:19])
    except ValueError:
        try:
            return date.fromisoformat(texte[:10]).isoformat()
        except ValueError:
            return None
    return (quand - timedelta(hours=FRONTIERE_JOUR_H)).date().isoformat()


@dataclass(frozen=True)
class Journee:
    """Une journée VÉCUE : un index, une date, et le jour vécu qui la précède."""

    index: int
    date: str
    veille: str | None


def journees_vecues(trajets: Sequence[Trajet]) -> list[Journee]:
    """Les journées où le run a produit des trajets, indexées depuis la première.

    L'index se compte en jours calendaires depuis la première journée vécue — c'est le même
    `jour_simule` que celui des points de reprise, donc les deux se recoupent. Les journées sans
    trajet n'ont pas de ligne : une ligne de zéros se lirait comme une journée immobile.
    """
    dates = sorted({d for d in (journee_du_moment(t.depart_complet) for t in trajets) if d})
    if not dates:
        return []
    origine = datetime.fromisoformat(dates[0]).date()
    return [
        Journee(
            index=(datetime.fromisoformat(date).date() - origine).days + 1,
            date=date,
            veille=dates[rang - 1] if rang else None,
        )
        for rang, date in enumerate(dates)
    ]


# ── Lignes de mesure ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LigneChoixModal:
    jour_simule: int
    date_simulee: str
    person_id: str
    trajets: int
    trajets_decides: int
    part_decidee: float
    modes_distincts: int
    parts: dict[str, float]
    trajets_mode_inconnu: int


@dataclass(frozen=True)
class LigneHabitude:
    jour_simule: int
    date_simulee: str
    person_id: str
    activite: str
    motif: str
    mode: str | None
    occurrences: int
    mode_veille: str | None
    reprise_veille: bool | None
    mode_habituel: str | None
    conforme_habitude: bool | None
    observations_fenetre: int


@dataclass(frozen=True)
class LigneMemoire:
    jour_simule: int
    date_simulee: str
    person_id: str
    rappels: int
    vivier_min: int | None
    vivier_median: float | None
    vivier_max: int | None
    souvenirs_servis: int
    operations: dict[str, int | None]
    operations_hors_vocabulaire: int
    etat_lu_dans: str | None
    entrees_ltm: int | None


@dataclass(frozen=True)
class LigneDureeDeVie:
    jour_simule: int
    date_simulee: str
    person_id: str
    type_souvenir: str
    entrees: int
    duree_vie_mediane_jours: float
    etat_lu_dans: str


@dataclass(frozen=True)
class LigneChoc:
    jour_simule: int
    date_simulee: str
    person_id: str
    choc_id: str
    # Ticket 100 — par quel CANAL l'événement est entré : `vecu` (subi à l'arrivée, après la
    # décision) ou `lu` (su au réveil, avant de décider). Les deux régimes se mesurent avec la
    # même fonction et se lisent dans le même fichier, ce qui est tout l'objet du ticket ;
    # mais ils ne se confondent pas, et une colonne les sépare. Vide pour les runs antérieurs.
    canal: str
    expositions: int
    minutes_injectees: float
    incidents_reseau: int
    correspondances_ratees: int
    souvenir_choc_servi: bool | None
    decisions_avec_souvenir_choc: int | None
    appariement: str


@dataclass
class Mesures:
    chemin_run: Path
    journees: list[Journee] = field(default_factory=list)
    choix_modal: list[LigneChoixModal] = field(default_factory=list)
    habitudes: list[LigneHabitude] = field(default_factory=list)
    memoire: list[LigneMemoire] = field(default_factory=list)
    durees_de_vie: list[LigneDureeDeVie] = field(default_factory=list)
    chocs: list[LigneChoc] = field(default_factory=list)
    souvenirs: list = field(default_factory=list)
    souvenirs_derives: list = field(default_factory=list)
    trajets_rejoues: int = 0
    rappels_rejoues: int = 0
    operations_tracees: bool = False


# ── Lecture des sources ───────────────────────────────────────────────────────────────


def _jsonl(chemin: Path) -> list[dict[str, Any]]:
    """JSONL tolérant : une ligne illisible est ignorée, jamais fatale."""
    if not chemin.is_file():
        return []
    lignes = []
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            objet = json.loads(ligne)
        except json.JSONDecodeError:
            continue
        if isinstance(objet, dict):
            lignes.append(objet)
    return lignes


def rappels_sans_rejeu(lignes: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Trace de rappel débarrassée des lignes RÉÉCRITES pendant le rejeu d'une reprise.

    ⚠ `trace_rappel` n'est pas gelée pendant le rejeu, contrairement au journal de mémoire.
    Mesuré sur `2026-09-16_15_58` : la clé `(1773637201, 41275)` porte deux lignes — la première
    à **0 candidat**, celle du run vivant au premier jour, la seconde à **22**, celle du rejeu qui
    voit la mémoire gelée à l'état restauré. Le motif est franc : 13 doublons par jour jusqu'au
    24 mars, 1 le 25, 0 ensuite — exactement la fin de la fenêtre de gel.

    Sans cette déduplication, la croissance du vivier — l'objet même de la mesure — est noyée
    sous l'état gelé : le vivier plafonnait à 30 dès le premier jour.

    Règle identique à celle de `moves.csv` : clé `(instant simulé, personne)`, la PREMIÈRE ligne
    gagne, les suivantes sont comptées. Une ligne sans instant simulé n'est pas déduplicable et
    passe telle quelle : on ne fusionne pas ce qu'on ne sait pas distinguer.
    """
    vues: set[tuple[Any, str]] = set()
    gardees: list[dict[str, Any]] = []
    rejeu = 0
    for ligne in lignes:
        instant = ligne.get("sim_ts")
        clef = (instant, str(ligne.get("person_id") or ""))
        if instant is None:
            gardees.append(ligne)
            continue
        if clef in vues:
            rejeu += 1
            continue
        vues.add(clef)
        gardees.append(ligne)
    return gardees, rejeu


def _points_de_reprise(chemin_run: Path) -> dict[str, Path]:
    """Journée CLOSE par chaque point de reprise → répertoire du point.

    Un point écrit le 17 mars à 3 h clôt la journée du 16 : la journée close est celle de
    l'instant qui précède immédiatement le point.
    """
    racine = Path(chemin_run) / "checkpoints_memoire"
    par_journee: dict[str, Path] = {}
    if not racine.is_dir():
        return par_journee
    for dossier in sorted(racine.glob("jour_*")):
        meta = dossier / "reprise.json"
        if not meta.is_file():
            continue
        try:
            charge = json.loads(meta.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        horodatage = str(charge.get("horodatage_simule") or "")
        if not horodatage:
            continue
        try:
            instant = datetime.fromisoformat(horodatage.replace("T", " ")[:19])
        except ValueError:
            continue
        journee = journee_du_moment((instant - timedelta(seconds=1)).isoformat())
        if journee:
            par_journee[journee] = dossier
    return par_journee


# ── Choix modal ───────────────────────────────────────────────────────────────────────


def choix_modal(trajets_par_jour: dict[tuple[str, str], list[Trajet]],
                journees: Sequence[Journee]) -> list[LigneChoixModal]:
    index = {j.date: j for j in journees}
    lignes = []
    for (date, person_id), trajets in sorted(trajets_par_jour.items()):
        journee = index.get(date)
        if journee is None:
            continue
        decides = sum(1 for t in trajets if (t.options_presentees or 0) >= 2)
        modes = Counter(t.mode for t in trajets if t.mode)
        lignes.append(LigneChoixModal(
            jour_simule=journee.index,
            date_simulee=date,
            person_id=person_id,
            trajets=len(trajets),
            trajets_decides=decides,
            part_decidee=decides / len(trajets),
            modes_distincts=len(modes),
            parts={mode: modes.get(mode, 0) / len(trajets) for mode in MODES},
            # Un mode que le vocabulaire ne connaît pas n'est pas versé en silence dans
            # « autres » : il est compté ici, pour qu'une part modale qui ne somme pas à 1 se
            # voie au lieu de se rattraper toute seule.
            trajets_mode_inconnu=sum(1 for t in trajets if not t.mode),
        ))
    return sorted(lignes, key=lambda l: (l.jour_simule, _cle_agent(l.person_id)))


# ── Habitude et rupture ───────────────────────────────────────────────────────────────


def habitudes(trajets_par_jour: dict[tuple[str, str], list[Trajet]],
              journees: Sequence[Journee]) -> list[LigneHabitude]:
    """Une ligne par agent, par activité et par journée vécue.

    Deux mesures, parce qu'elles ne détectent pas la même chose : la reprise de la veille voit
    une bascule franche le jour où elle arrive ; la conformité à l'habitude voit une dérive lente
    qu'un seul jour ne révèle pas.
    """
    index = {j.date: j for j in journees}
    # (agent, activité) → [(date, mode)] dans l'ordre des journées vécues
    historique: dict[tuple[str, str], list[tuple[str, str | None]]] = {}
    lignes: list[LigneHabitude] = []

    for journee in journees:
        agents_du_jour = sorted(
            (person_id for (date, person_id) in trajets_par_jour if date == journee.date),
            key=_cle_agent,
        )
        for person_id in agents_du_jour:
            par_activite = _par_activite(trajets_par_jour[(journee.date, person_id)])
            for activite, trajets in sorted(par_activite.items()):
                premier = trajets[0]
                clef = (person_id, activite)
                passe = historique.get(clef, [])
                mode_veille = next(
                    (mode for date, mode in reversed(passe) if date == journee.veille), None
                )
                # La fenêtre porte sur les cinq dernières OBSERVATIONS de cette activité, pas sur
                # les cinq derniers jours simulés : un agent qui ne sort qu'un jour sur trois a
                # ainsi la même profondeur d'habitude, simplement étalée sur plus de jours.
                fenetre = [mode for _, mode in passe[-FENETRE_HABITUDE:] if mode]
                habituel = _majoritaire(fenetre)
                lignes.append(LigneHabitude(
                    jour_simule=journee.index,
                    date_simulee=journee.date,
                    person_id=person_id,
                    activite=activite,
                    motif=premier.motif,
                    mode=premier.mode,
                    occurrences=len(trajets),
                    mode_veille=mode_veille,
                    reprise_veille=(premier.mode == mode_veille) if mode_veille else None,
                    mode_habituel=habituel,
                    conforme_habitude=(premier.mode == habituel) if habituel else None,
                    observations_fenetre=len(fenetre),
                ))
                historique.setdefault(clef, []).append((journee.date, premier.mode))
    return sorted(lignes, key=lambda l: (l.jour_simule, _cle_agent(l.person_id), l.activite))


def _par_activite(trajets: Sequence[Trajet]) -> dict[str, list[Trajet]]:
    """Trajets d'une journée groupés par activité, chaque groupe trié par heure de départ.

    Plusieurs trajets d'une même activité le même jour : le mode retenu est celui du PREMIER
    départ, et le nombre d'occurrences est écrit (question 4 du ticket).
    """
    par_activite: dict[str, list[Trajet]] = {}
    for trajet in sorted(trajets, key=lambda t: (t.depart, t.trajet_id)):
        par_activite.setdefault(trajet.activity_id, []).append(trajet)
    return par_activite


def _majoritaire(modes: Sequence[str]) -> str | None:
    """Le mode strictement majoritaire de la fenêtre, ou `None`.

    ⚠ Un ex æquo rend `None`, jamais un mode tiré au sort ni le premier venu : trancher une
    égalité fabriquerait une habitude que l'agent n'a pas, et la conformité mesurée ensuite
    contre elle ne voudrait rien dire.
    """
    if not modes:
        return None
    comptes = Counter(modes).most_common()
    if len(comptes) > 1 and comptes[0][1] == comptes[1][1]:
        return None
    return comptes[0][0]


# ── Mémoire ───────────────────────────────────────────────────────────────────────────


def memoire(
    chemin_run: Path, journees: Sequence[Journee], agents: Iterable[str],
    points: dict[str, Path],
) -> tuple[list[LigneMemoire], list[LigneDureeDeVie], bool, int]:
    rappels, rappels_rejoues = rappels_sans_rejeu(
        _jsonl(Path(chemin_run) / "trace_rappel.jsonl"))
    operations = _jsonl(Path(chemin_run) / "operations_concept.jsonl")
    tracees = (Path(chemin_run) / "operations_concept.jsonl").is_file()

    par_jour_agent: dict[tuple[str, str], list[dict]] = {}
    for ligne in rappels:
        journee = journee_du_moment(str(ligne.get("sim_day") or ""))
        agent = str(ligne.get("person_id") or "")
        if journee and agent:
            par_jour_agent.setdefault((journee, agent), []).append(ligne)

    ops_par_jour_agent: dict[tuple[str, str], Counter] = {}
    hors_vocabulaire: Counter = Counter()
    for ligne in operations:
        journee = journee_du_moment(str(ligne.get("sim_day") or ""))
        agent = str(ligne.get("person_id") or "")
        if not (journee and agent):
            continue
        operation = str(ligne.get("operation") or "")
        if operation in OPERATIONS_CONCEPT:
            ops_par_jour_agent.setdefault((journee, agent), Counter())[operation] += 1
        else:
            # Une opération hors des quatre n'est pas rangée dans l'une d'elles : elle est
            # comptée à part, sans quoi un vocabulaire qui change en silence se lirait comme un
            # changement de comportement.
            hors_vocabulaire[(journee, agent)] += 1

    etats = {date: _etat_memoire(dossier) for date, dossier in points.items()}

    lignes: list[LigneMemoire] = []
    durees: list[LigneDureeDeVie] = []
    for journee in journees:
        etat = etats.get(journee.date)
        for agent in sorted(agents, key=_cle_agent):
            traces = par_jour_agent.get((journee.date, agent), [])
            viviers = [int(t.get("candidats") or 0) for t in traces]
            ops = ops_par_jour_agent.get((journee.date, agent))
            lignes.append(LigneMemoire(
                jour_simule=journee.index,
                date_simulee=journee.date,
                person_id=agent,
                rappels=len(traces),
                vivier_min=min(viviers) if viviers else None,
                vivier_median=median(viviers) if viviers else None,
                vivier_max=max(viviers) if viviers else None,
                souvenirs_servis=sum(len(t.get("servis") or []) for t in traces),
                # Trace éteinte : les colonnes sont VIDES et non à zéro. « Aucune contradiction »
                # et « on ne mesure pas les contradictions » ne doivent pas se citer pareil.
                operations={
                    nom: ((ops or Counter()).get(nom, 0) if tracees else None)
                    for nom in OPERATIONS_CONCEPT
                },
                operations_hors_vocabulaire=hors_vocabulaire.get((journee.date, agent), 0),
                etat_lu_dans=points[journee.date].name if journee.date in points else None,
                entrees_ltm=len(etat.get(agent, [])) if etat is not None else None,
            ))
            if etat is None:
                continue
            par_type: dict[str, list[float]] = {}
            for entree in etat.get(agent, []):
                par_type.setdefault(entree.memory_type or "inconnu", []).append(entree.force)
            for type_souvenir, forces in sorted(par_type.items()):
                durees.append(LigneDureeDeVie(
                    jour_simule=journee.index,
                    date_simulee=journee.date,
                    person_id=agent,
                    type_souvenir=type_souvenir,
                    entrees=len(forces),
                    duree_vie_mediane_jours=round(median(forces), 2),
                    etat_lu_dans=points[journee.date].name,
                ))
    return lignes, durees, tracees, rappels_rejoues


def _etat_memoire(dossier: Path) -> dict[str, list]:
    entrees, _habitudes = lire_ltm(dossier)
    return entrees


# ── Choc ──────────────────────────────────────────────────────────────────────────────


def chocs(chemin_run: Path, journees: Sequence[Journee],
          decisions_par_jour: dict[tuple[str, str], int] | None = None) -> list[LigneChoc]:
    """Exposés et minutes injectées, par jour d'exposition. Voir `chocs_et_souvenirs`."""
    return chocs_et_souvenirs(chemin_run, journees, decisions_par_jour)[0]


def chocs_et_souvenirs(
    chemin_run: Path, journees: Sequence[Journee],
    decisions_par_jour: dict[tuple[str, str], int] | None = None,
) -> tuple[list[LigneChoc], Any]:
    """Les lignes d'`evenement_par_jour`, et le suivi du souvenir dans le foyer (`souvenir.py`).

    ⚠ **« Servi » se lit dans le prompt, plus dans `trace_rappel`** (2026-09-25). La trace de
    rappel compte ce que la recherche a remonté, pas ce que le modèle a lu : le noyau n'y figure
    pas, et quand il est présent seules deux ou trois épisodiques survivent. Et le lien cherché
    était le texte littéral de l'injection, que la consolidation reformule toujours — le
    souvenir de l'article a09 n'était donc jamais trouvé, et six prompts qui le portaient
    donnaient 0.

    Les deux colonnes de souvenir décrivent la JOURNÉE de l'exposition — ce qui garde une ligne
    d'un jour passé immobile quand le run avance. Ce qui se passe ensuite, jour après jour et
    pour tout le foyer, est dans `souvenir_evenement_par_jour.csv`.

    `appariement` dit comment le souvenir a été trouvé dans les prompts du jour :
    `texte` (l'article mot pour mot), `mots` (une reformulation), `aucune trace` (des prompts,
    aucun ne le porte : 0 mesuré), `sans prompt` (aucun prompt ce jour-là, ou pas de journal
    d'échanges : on ne sait pas, et la cellule reste vide).
    """
    from scripts.analysis.mesures import souvenir

    # Ticket 100 — `evenements.jsonl` est le nom neuf ; `chocs.jsonl` reste lu pour les runs
    # archivés, et c'est là que vivent les chiffres publiés du § 7.2. On lit le premier qui
    # existe, jamais les deux : dans un run neuf, le second est un lien vers le premier.
    tous = _jsonl(Path(chemin_run) / "evenements.jsonl")
    if not tous:
        tous = _jsonl(Path(chemin_run) / "chocs.jsonl")
    # Ticket 111 : la ligne d'un membre informé (`origine: entendu`) n'est pas une exposition.
    # Ce qu'il a reçu se lit dans `relais_foyer.jsonl` et par le sous-rôle du co-résident.
    evenements = [e for e in tous if e.get("origine") != "entendu"]
    if not evenements:
        return [], None
    index = {j.date: j for j in journees}
    suivi = souvenir.mesurer(
        Path(chemin_run), tous, journees, decisions_par_jour or {},
        lambda e: journee_de_l_exposition(e, journees, bavard=False),
    )

    groupes: dict[tuple[str, str, str], list[dict]] = {}
    for evenement in evenements:
        journee = journee_de_l_exposition(evenement, journees)
        agent = str(evenement.get("person_id") or "")
        if journee and agent:
            # `evenement_id` est le nom neuf, `choc_id` celui du 079 : les deux sont écrits
            # côte à côte dans un run neuf, et seul le second dans un run archivé.
            identifiant = str(
                evenement.get("evenement_id") or evenement.get("choc_id") or ""
            )
            groupes.setdefault((journee, agent, identifiant), []).append(evenement)

    lignes = []
    for (date, agent, choc_id), liste in sorted(groupes.items()):
        # Un article se lit au réveil, que l'agent se déplace ou non ce jour-là : l'exposition
        # garde sa ligne même un jour sans trajet, indexée depuis la première journée vécue.
        indice = index[date].index if date in index else _indice_calendaire(date, journees)
        if indice is None:
            continue
        prompts, avec, trouve = suivi.du_jour.get((date, agent, choc_id), (0, 0, ""))
        if not suivi.journal_present or not prompts:
            decisions, appariement = None, "sans prompt"
        else:
            decisions, appariement = avec, (trouve or "aucune trace")
        lignes.append(LigneChoc(
            jour_simule=indice,
            date_simulee=date,
            person_id=agent,
            choc_id=choc_id,
            # Vide — jamais `vecu` — pour un run archivé qui ne portait pas le champ : écrire
            # une modalité qu'on n'a pas mesurée en ferait une mesure.
            canal=str(liste[0].get("canal") or ""),
            expositions=len(liste),
            minutes_injectees=round(
                sum(float(e.get("retard_injecte_s") or 0) for e in liste) / 60.0, 2),
            incidents_reseau=sum(1 for e in liste if e.get("incident_reseau")),
            correspondances_ratees=sum(1 for e in liste if e.get("correspondance_ratee")),
            souvenir_choc_servi=(decisions > 0) if decisions is not None else None,
            decisions_avec_souvenir_choc=decisions,
            appariement=appariement,
        ))
    return lignes, suivi


def journee_de_l_exposition(evenement: dict, journees: Sequence[Journee],
                             bavard: bool = True) -> str | None:
    """Journée simulée d'une exposition, selon le moment où l'événement entre.

    ⚠ **Un article lu au réveil appartient au jour où il est lu.** Le registre l'injecte au
    premier pas après minuit, horodaté `AAAA-MM-JJT00:00:00`. La frontière de 3 h, juste pour un
    trajet, le reculait d'un jour : l'article a09 du run `2026-09-24_17_50`, lu le 26 mars
    (`jour_run: 11`), sortait au jour 10. Le jour calendaire de l'horodatage est celui du
    registre (`ancre_run.jours_ecoules` compte depuis minuit) ; il est recoupé avec `jour_run`
    quand la ligne le porte, et un écart le dit au lieu de trancher en silence.

    Un choc vécu à l'arrivée (`moment: arrivee`, ou absent dans un run du 079) garde la
    frontière de 3 h : il est joint au trajet qu'il accompagne, et doit tomber le même jour que
    lui. C'est ce qui laisse inchangés les chiffres archivés du § 7.2.
    """
    horodatage = str(evenement.get("horodatage_simule") or "")
    if evenement.get("moment") != "reveil":
        return journee_du_moment(horodatage)
    date_lue = journee_du_moment(horodatage[:10])
    jour_run = evenement.get("jour_run")
    indice = _indice_calendaire(date_lue, journees) if date_lue else None
    if bavard and isinstance(jour_run, int) and indice is not None and indice != jour_run:
        print(
            f"  ⚠ exposition de {evenement.get('person_id')} datée du {date_lue} (jour {indice} "
            f"des mesures) mais `jour_run: {jour_run}` dans evenements.jsonl — la première "
            f"journée vécue n'est pas le premier jour du run ; la date de l'horodatage est gardée."
        )
    return date_lue


def _indice_calendaire(date_iso: str, journees: Sequence[Journee]) -> int | None:
    """Rang calendaire d'une date depuis la première journée vécue, même sans trajet ce jour-là."""
    if not journees:
        return None
    origine = date.fromisoformat(journees[0].date) - timedelta(days=journees[0].index - 1)
    try:
        return (date.fromisoformat(date_iso) - origine).days + 1
    except ValueError:
        return None


# ── Assemblage ────────────────────────────────────────────────────────────────────────


def _cle_agent(person_id: str) -> tuple[int, int, str]:
    return (0, int(person_id), "") if person_id.isdigit() else (1, 0, person_id)


def calculer(chemin_run: Path | str) -> Mesures:
    """Toutes les mesures d'un run, recalculées depuis zéro.

    Recalculer intégralement plutôt que compléter est ce qui rend la continuité vraie par
    construction : un jour rejoué après une reprise ne peut pas se dédoubler puisqu'il repart de
    la même source dédupliquée, et une coupure ne peut pas trouer la courbe.
    """
    chemin_run = Path(chemin_run)
    trajets, rejeu, _detail = lire_moves(chemin_run)
    journees = journees_vecues(trajets)

    par_jour: dict[tuple[str, str], list[Trajet]] = {}
    for trajet in trajets:
        date = journee_du_moment(trajet.depart_complet)
        if date:
            par_jour.setdefault((date, trajet.person_id), []).append(trajet)

    agents = sorted({t.person_id for t in trajets}, key=_cle_agent)
    points = _points_de_reprise(chemin_run)
    lignes_memoire, durees, tracees, rappels_rejoues = memoire(
        chemin_run, journees, agents, points)
    decisions_par_jour = {
        cle: sum(1 for t in liste if (t.options_presentees or 0) >= 2)
        for cle, liste in par_jour.items()
    }
    lignes_chocs, suivi = chocs_et_souvenirs(chemin_run, journees, decisions_par_jour)
    return Mesures(
        chemin_run=chemin_run,
        journees=journees,
        choix_modal=choix_modal(par_jour, journees),
        habitudes=habitudes(par_jour, journees),
        memoire=lignes_memoire,
        durees_de_vie=durees,
        chocs=lignes_chocs,
        souvenirs=suivi.lignes if suivi else [],
        souvenirs_derives=suivi.derives if suivi else [],
        trajets_rejoues=rejeu,
        rappels_rejoues=rappels_rejoues,
        operations_tracees=tracees,
    )
