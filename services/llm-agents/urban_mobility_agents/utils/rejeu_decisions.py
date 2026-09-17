"""Trace de rejeu des décisions — ticket 090.

LE PROBLÈME
-----------
À la reprise à chaud, GAMA repart de son `starting_date` et **rejoue** les jours déjà vécus pour
reconstruire son état : positions des agents, et surtout où se trouve la voiture de chacun. La
mémoire, elle, est gelée (ticket 075) — les agents circulent sans rien réapprendre. Mais ils
**redécident**, et avec le cache sémantique coupé — condition d'un run journalisé sur son
périmètre complet — chaque décision rejouée est repayée au modèle. Mesuré le 2026-09-16 : huit
jours rejoués, une centaine de décisions, trois quarts d'heure d'attente réseau pour retrouver un
état déjà connu.

CE QUE FAIT CE MODULE
---------------------
Pendant la vie normale, il consigne chaque décision sous sa clé `(personne, activité, instant)`.
Pendant la fenêtre de gel, il la ressert sans appel au modèle.

⚠ **Ce n'est PAS le cache sémantique**, et la distinction est ce qui rend ce lot acceptable là où
le cache ne l'est pas :

| | Cache sémantique | Trace de rejeu |
|---|---|---|
| Source | répertoire partagé entre runs | le workdir de CE run |
| Clé | empreinte d'état, **non indexée par modèle** | `(personne, activité, instant)` |
| Portée | tout le run | seulement tant que `reprise.gel_actif()` |
| Rien ne correspond | recalcul silencieux | compté, puis **alarmé** au-delà d'un seuil |

Le cache peut resservir une décision prise par un autre modèle sous un autre prompt : c'est
pourquoi il est coupé sur les runs de mesure. Ici on ne ressert que ce que CE run a lui-même
produit, et seulement pour rejouer des journées qu'il a déjà vécues.

⚠ **`llm_exchanges.jsonl` ne peut pas servir de source.** Il est écrit côté worker et son
`sim_ts` vaut `min(departure_timestamp)` du LOT : cinq agents d'un même lot y partagent un
horodatage. Le contrôleur ne peut donc pas prédire, avant l'appel, la clé sous laquelle sa
réponse sera consignée. La trace est écrite ici, côté contrôleur, où la clé est connue.
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

FICHIER = "decisions_rejeu.jsonl"

# Au-delà de cette part de clés manquées, le rejeu a divergé : ce n'est plus une reprise à
# l'identique, et le dire vaut mieux que de le découvrir sur une courbe trois semaines plus tard.
SEUIL_ALARME_MANQUEES = 0.20

_index: dict[str, dict] = {}
_chemin: Path | None = None
_servies = 0
_manquees = 0
_alarme_levee = False


def _cle(personne: str, activite: str, instant: float) -> str:
    return f"{personne}|{activite}|{int(instant)}"


def chemin(workdir: str | Path) -> Path:
    return Path(workdir) / FICHIER


def charger(workdir: str | Path, jusqu_a: float | None = None) -> int:
    """Indexe la trace du run, en ne gardant que ce qui précède le point de reprise.

    Une trace absente est le cas NORMAL du premier run : on rend 0 sans rien dire d'alarmant.
    Une trace illisible ne doit pas empêcher le run de tourner — elle est ignorée, et le dit.
    """
    global _index, _chemin
    _index = {}
    _chemin = chemin(workdir)
    if not _chemin.is_file():
        logger.info(f"[rejeu] aucune trace de décisions dans {workdir} — rien à resservir")
        return 0
    gardees = 0
    ignorees = 0
    for ligne in _chemin.read_text(encoding="utf-8", errors="replace").splitlines():
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            enr = json.loads(ligne)
            if jusqu_a is not None and float(enr["instant"]) > float(jusqu_a):
                continue
            _index[_cle(enr["personne"], enr["activite"], enr["instant"])] = enr
            gardees += 1
        except (ValueError, KeyError, TypeError):
            ignorees += 1
    if ignorees:
        logger.warning(
            f"[rejeu] {ignorees} ligne(s) illisible(s) ignorée(s) dans {_chemin.name} — "
            f"le rejeu se fera sans elles"
        )
    logger.info(
        f"[rejeu] {gardees} décision(s) indexée(s) depuis {_chemin.name}"
        + (f", antérieures au point de reprise ({jusqu_a})" if jusqu_a is not None else "")
    )
    return gardees


def tracer(
    personne: str,
    activite: str,
    instant: float,
    *,
    code_plan: str,
    raison: str,
    fournisseur: str,
    distribution: dict | None,
) -> None:
    """Consigne une décision vivante. Sans effet si le fichier n'est pas ouvrable."""
    if _chemin is None:
        return
    enr = {
        "personne": str(personne),
        "activite": str(activite),
        "instant": float(instant),
        "code_plan": code_plan,
        "raison": raison,
        "fournisseur": fournisseur,
        "distribution": distribution or {},
    }
    try:
        with _chemin.open("a", encoding="utf-8") as f:
            f.write(json.dumps(enr, ensure_ascii=False) + "\n")
    except OSError as e:
        # Une trace qui échoue ne doit jamais casser un run en cours.
        logger.warning(f"[rejeu] trace non écrite ({e})")


def chercher(personne: str, activite: str, instant: float) -> dict | None:
    """La décision déjà prise pour cette clé, ou None. Compte servies et manquées."""
    global _servies, _manquees, _alarme_levee
    enr = _index.get(_cle(personne, activite, instant))
    if enr is None:
        _manquees += 1
        total = _servies + _manquees
        if (
            not _alarme_levee
            and total >= 20
            and _manquees / total > SEUIL_ALARME_MANQUEES
        ):
            _alarme_levee = True
            logger.error(
                f"[ALARME] Rejeu divergent : {_manquees}/{total} décisions rejouées n'ont pas "
                f"été retrouvées dans la trace ({_manquees / total:.0%}). Le run rejoué ne "
                f"refait pas les mêmes choix qu'à l'aller — l'état reconstruit n'est pas celui "
                f"qu'on croit reprendre."
            )
        return None
    _servies += 1
    return enr


def bilan() -> str:
    total = _servies + _manquees
    part = f"{_servies / total:.0%}" if total else "—"
    return (
        f"[rejeu] bilan : {_servies} décision(s) resservie(s) sans appel au modèle, "
        f"{_manquees} manquée(s), {part} de la fenêtre de rejeu épargnée"
    )


def reinitialiser() -> None:
    """Pour les tests : vide l'index et les compteurs."""
    global _index, _chemin, _servies, _manquees, _alarme_levee
    _index = {}
    _chemin = None
    _servies = 0
    _manquees = 0
    _alarme_levee = False
