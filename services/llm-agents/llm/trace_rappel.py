"""Trace des souvenirs SERVIS à une décision — ticket 077, lots E1 et D2.

Le run de trente jours du ticket 075 a laissé une question sans réponse : **la mémoire
change-t-elle les décisions ?** Le journal disait « 10 souvenir(s) servi(s) » et leur incipit,
sans le score qui les a retenus ni le vivier d'où ils venaient. Reconstituer cela après coup
est impossible : les scores ne sont écrits nulle part, et le tampon a changé.

Deux choses vivent ici, parce qu'elles se lisent au même endroit et au même instant.

**E1 — la trace.** Une ligne JSONL par décision servie par la mémoire : l'agent, l'instant,
et le top-K avec, pour chaque souvenir, son identifiant, son type, son vivier d'origine, son
score composite et son rang.

**D2 — la concentration.** Le rappel s'auto-renforce : un souvenir servi voit sa force
augmenter, donc sa probabilité d'être servi de nouveau. Mesuré sur le run du 075 — 128 rappels
sur 133 servent dix souvenirs, et ce sont toujours les mêmes ; le plus servi l'est cinquante-cinq
fois. Ce sont les réflexions des premiers jours, donc les plus contaminées par les observations
que le lot B corrige. Le lot B retire la cause principale ; cette mesure dit si cela a suffi.

⚠ **Ce module ne corrige rien.** Il mesure, et lève une alarme. Changer la règle de
renforcement serait changer une règle de la mémoire, ce que le ticket 077 s'interdit.

Éteint par défaut (`agent.trace_rappel_enabled`) : à mille agents, une ligne par décision et
par souvenir ferait un fichier que personne n'ouvrirait.
"""

from __future__ import annotations

import json
from collections import Counter, deque
from datetime import datetime, timezone

from loguru import logger
from settings import settings

# Fenêtre d'observation de la concentration, en nombre de rappels. Même ordre de grandeur que
# la fenêtre des viviers du lot 2 : une concentration forte sur un rappel ne veut rien dire,
# l'agent n'a qu'une poignée de souvenirs le premier jour.
FENETRE_CONCENTRATION = 200

# Seuils d'alarme. Le haut déclenche, le bas réarme : sans hystérésis, une valeur qui oscille
# autour d'un seuil unique inonderait le journal. Les deux sont des PARTS du total servi.
SEUIL_CONCENTRATION_HAUT = 0.80
SEUIL_CONCENTRATION_BAS = 0.65
# Nombre de souvenirs dont on regarde la part cumulée. Dix, comme le top-K servi au modèle :
# la question est « les dix mêmes reviennent-ils toujours ».
TETE_CONCENTRATION = 10


class _EtatConcentration:
    """Compteur par agent, borné. Rien ne grandit sans fin ici : c'est un processus long."""

    def __init__(self) -> None:
        self.servis: Counter[str] = Counter()
        self.fenetre: deque[str] = deque()
        self.en_alarme: bool = False

    def noter(self, doc_ids: list[str], candidats: int = 0) -> float | None:
        """Ajoute un rappel et rend la concentration, ou `None` si elle n'a pas de sens.

        ⚠ **Un rappel sans choix ne compte pas.** Défaut trouvé en faisant tourner ce module
        le 2026-09-15 : l'alarme s'est levée à 100 % pour quatre agents au cinquième jour
        simulé. Elle disait vrai et ne mesurait rien — un agent qui possède onze souvenirs et
        qui en sert dix les sert forcément tous, et la « concentration » ne mesurait que la
        TAILLE de sa mémoire. C'est le motif récurrent du dépôt, pris à l'envers : l'absence
        de choix produisait ici le score le plus alarmant au lieu du plus parfait.

        Un rappel n'entre donc dans la fenêtre que si le vivier offrait **strictement plus**
        de candidats qu'il n'en a été servi. Alors seulement, servir toujours les mêmes est
        une sélection, et non une fatalité.
        """
        if candidats <= len(doc_ids):
            return None
        for doc_id in doc_ids:
            self.servis[doc_id] += 1
            self.fenetre.append(doc_id)
        while len(self.fenetre) > FENETRE_CONCENTRATION * TETE_CONCENTRATION:
            vieux = self.fenetre.popleft()
            self.servis[vieux] -= 1
            if self.servis[vieux] <= 0:
                del self.servis[vieux]
        total = sum(self.servis.values())
        if total < TETE_CONCENTRATION * 2:
            # Trop peu de matière : une concentration de 1,0 sur douze rappels est le
            # comportement NORMAL d'un agent qui commence, pas une anomalie.
            return None
        # Second garde-fou, sur le VIVIER et non sur le nombre de rappels : tant que l'agent
        # ne dispose pas de nettement plus de souvenirs que le top-K, « les dix mêmes »
        # n'est pas un choix.
        if len(self.servis) < TETE_CONCENTRATION * 2:
            return None
        tete = sum(n for _, n in self.servis.most_common(TETE_CONCENTRATION))
        return tete / total


_ETATS: dict[str, _EtatConcentration] = {}


def reinitialiser() -> None:
    """Remet les compteurs à zéro. Pour les tests, et pour eux seuls."""
    _ETATS.clear()


def _vivier(meta: dict) -> str:
    return str((meta or {}).get("vivier") or "?")


def tracer_rappel(
    person_id: str,
    query_at: int | None,
    servis: list,
    scores_par_doc: dict[str, float],
    candidats: int,
) -> None:
    """Écrit la trace du top-K et met à jour la concentration. Ne lève jamais.

    FAIL-OPEN par construction : une trace qui échoue ne doit pas faire perdre une décision.
    C'est une sortie d'observation, elle n'est sur le chemin critique que par accident.
    """
    try:
        doc_ids = [
            str((r.metadata or {}).get("doc_id") or "") for r in servis
        ]
        etat = _ETATS.setdefault(person_id, _EtatConcentration())
        concentration = etat.noter([d for d in doc_ids if d], candidats)

        if concentration is not None:
            if concentration >= SEUIL_CONCENTRATION_HAUT and not etat.en_alarme:
                etat.en_alarme = True
                logger.error(
                    f"[ALARME] concentration des rappels à {concentration:.0%} pour "
                    f"{person_id} — les {TETE_CONCENTRATION} souvenirs les plus servis "
                    f"occupent la quasi-totalité du top-K sur les {FENETRE_CONCENTRATION} "
                    f"derniers rappels. Le rappel s'auto-renforce : ce que l'agent a appris "
                    f"tôt évince ce qu'il apprend ensuite."
                )
            elif concentration <= SEUIL_CONCENTRATION_BAS and etat.en_alarme:
                etat.en_alarme = False
                logger.info(
                    f"[viviers] concentration des rappels redescendue à "
                    f"{concentration:.0%} pour {person_id} — alarme réarmée"
                )

        if not settings.agent.trace_rappel_enabled:
            return

        entree = {
            "sim_ts": query_at,
            "sim_day": datetime.fromtimestamp(query_at, tz=timezone.utc).strftime(
                "%Y-%m-%d"
            )
            if query_at
            else None,
            "person_id": str(person_id),
            "candidats": int(candidats),
            "concentration": round(concentration, 4)
            if concentration is not None
            else None,
            "servis": [
                {
                    "rang": rang,
                    "doc_id": (r.metadata or {}).get("doc_id"),
                    "type": (r.metadata or {}).get("memory_type"),
                    "vivier": _vivier(r.metadata),
                    "score": round(
                        float(
                            scores_par_doc.get(
                                str((r.metadata or {}).get("doc_id") or ""), 0.0
                            )
                        ),
                        4,
                    ),
                }
                for rang, r in enumerate(servis)
            ],
        }
        with open(settings.app.trace_rappel_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entree, ensure_ascii=False, default=str) + "\n")
    except Exception as err:  # noqa: BLE001 — une trace ne fait jamais tomber une décision
        logger.warning(f"[trace_rappel] trace non écrite pour {person_id} ({err})")
