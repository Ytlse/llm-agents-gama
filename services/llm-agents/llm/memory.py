from dataclasses import asdict, dataclass, fields
from datetime import datetime
from typing import Dict, Optional

# LLM imports
from enum import Enum

class MemoryType(Enum):
    CONVERSATION = "conversation"
    REFLECTION = "reflection"
    CONCEPT = "concept"
    SUMMARY = "summary"

    def __str__(self):
        return str(self.value)

# Registres de mémoire déclarative (Tulving, 1972 ; Sumers et al., 2024 pour les agents de
# langue). Les deux n'ont pas la même dynamique d'effacement : l'épisodique s'efface au TEMPS,
# le sémantique à la CONTRADICTION (lot 3). Qu'une ligne sature les jours de pluie ne devient
# pas faux parce que dix jours ont passé.
TYPES_EPISODIQUES = (MemoryType.CONVERSATION, MemoryType.REFLECTION)
TYPES_SEMANTIQUES = (MemoryType.CONCEPT, MemoryType.SUMMARY)


@dataclass
class MemoryEntry:
    """Represents a memory entry with metadata"""
    content: str
    timestamp: datetime
    memory_type: MemoryType
    person_id: str
    activity_id: Optional[str] = None
    tags: Optional[str] = ""
    # Identifiant du document dans l'index vectoriel. Posé à l'écriture par
    # `MultiUserLongTermMemory.aadd_memory`, il rend l'entrée ADRESSABLE pour la
    # suppression : sans lui, une entrée retirée des métadonnées resterait dans
    # l'index et continuerait d'être resservie au modèle (ticket 071, défaut B).
    # `None` pour les entrées écrites avant ce ticket, qui ne sont pas supprimables.
    doc_id: Optional[str] = None

    # ── Qualification du souvenir (ticket 071, lot 1) ────────────────────────────
    # Tous ces champs ont un DÉFAUT, et ce n'est pas une commodité : une entrée écrite
    # avant le lot 1 doit se recharger sans exception, et une entrée écrite après doit
    # rester lisible par du code qui ignore ces champs. La réversibilité du ticket en
    # dépend.

    # Gravité sur [0, 1]. Décide de la durée de vie, et du poids au rappel (lot 2).
    importance: float = 0.0
    # Sépare un souvenir marquant heureux d'un souvenir marquant subi.
    valence: str = "neutre"
    # ── Provenance (ticket 100, D2) ──────────────────────────────────────────────
    # D'où vient ce que l'entrée raconte : `vecu` (l'agent l'a fait ou subi), `lu` (il l'a
    # lu, canal presse), `entendu` (un autre membre de son foyer le lui a dit).
    #
    # Elle porte la décision D2 — **un seul saut**. Ce qui est entendu ne repart jamais : une
    # croyance née d'un ouï-dire est indiscernable d'une croyance née d'un trajet sans ce
    # champ, et il n'y a pas de raccourci. Le ticket 078 § 4.1 refusait cette généalogie ;
    # elle devient nécessaire dès lors que la circulation est bornée à un saut.
    #
    # `None` = entrée écrite AVANT ce ticket. Elle se LIT comme vécue (`origine_effective`)
    # faute de mieux, mais elle ne le DÉCLARE pas : confondre les deux ferait passer pour une
    # mesure ce qui n'est qu'un défaut, et ce dépôt a déjà payé ce motif.
    origine: Optional[str] = None
    # Les quatre axes, NORMALISÉS À L'ÉCRITURE et jamais à la lecture (lot 2) : sans cela,
    # deux graphies de la même ligne de bus ne se rencontrent jamais. Un axe non résolu vaut
    # `None`, traité comme une absence de correspondance et non comme une correspondance
    # avec tout.
    axe_objet: Optional[str] = None
    axe_lieu: Optional[str] = None
    axe_creneau: Optional[str] = None
    axe_motif: Optional[str] = None
    # Cinquième axe, ajouté au lot 2 : la météo du jour, en cinq valeurs (`sec`, `pluie`,
    # `neige`, `canicule`, `froid`). Elle n'est stockée nulle part ailleurs — elle est
    # recalculée à la volée au moment du prompt — et le classement en a besoin pour apparier
    # un souvenir de pluie à une décision prise sous la pluie.
    axe_meteo: Optional[str] = None
    # Constante de temps de l'oubli, en JOURS. `None` = entrée jamais qualifiée : le rappel
    # retombe alors sur la constante par défaut plutôt que de lui donner un poids nul.
    force: Optional[float] = None
    rappels: int = 0
    # Dernier moment où le souvenir a été SERVI au modèle, en temps simulé. Distinct de
    # `timestamp`, qui reste l'heure de l'ÉVÉNEMENT : celui-ci s'affiche dans le prompt et
    # sert de côté gauche aux filtres par jour et par ancienneté. Le faire glisser au rappel
    # réécrirait l'histoire de l'agent — il croirait que sa chute à vélo a eu lieu hier.
    # `None` = jamais rappelé : la décroissance part alors de l'écriture.
    dernier_rappel: Optional[datetime] = None

    # ── Concepts seulement (lot 3) ───────────────────────────────────────────────
    # Portés par les entrées de type `concept`. Nuls ailleurs.
    panier: Optional[str] = None
    observations: int = 0
    contre_exemples: int = 0
    # Date de MISE À L'ÉCART d'un concept dépassé, en temps simulé. Jamais une suppression :
    # cette mise à l'écart datée EST la trace lisible d'un changement d'habitude, et c'est
    # l'observable que l'expérience d'hystérésis cherche.
    depasse_le: Optional[str] = None
    # Dernière fois que ce concept a été CONFIRMÉ ou PRÉCISÉ, en temps simulé.
    # ⚠ Champ distinct de `timestamp`, et ce n'est pas un doublon : la spécification demandait
    # de « rafraîchir l'horodatage » à chaque confirmation, ce que le lot 1 interdit — le
    # `timestamp` est l'heure de l'ÉVÉNEMENT, il s'affiche dans le prompt, et le faire glisser
    # réécrirait l'histoire de l'agent. Celui-ci ne sert qu'à départager deux concepts de
    # confiance égale, et ne touche ni au texte du prompt, ni aux filtres d'âge.
    derniere_observation: Optional[datetime] = None

    # Version du schéma de l'entrée. Sert à distinguer, au rechargement, une entrée
    # jamais qualifiée (gravité réellement inconnue) d'une entrée qualifiée à zéro
    # (trajet qui s'est bien passé). Les deux portent `importance = 0.0`.
    schema_version: int = 1

    @property
    def origine_effective(self) -> str:
        """La provenance, avec sa lecture par défaut pour les entrées antérieures au 100."""
        return self.origine or "vecu"

    @property
    def est_episodique(self) -> bool:
        """L'oubli au temps ne concerne QUE l'épisodique (lot 1) ; le reste relève du lot 3."""
        return self.memory_type in TYPES_EPISODIQUES

    @property
    def confiance(self) -> float:
        """Règle de succession de Laplace : `(obs + 1) / (obs + contre_ex + 2)`.

        Pour un concept, elle REMPLACE la décroissance d'horloge au classement (lot 3). Un
        concept jamais contredit garde son poids ; un concept contredit le perd, quelle que
        soit son ancienneté.
        """
        from llm.concepts import confiance as _confiance

        return _confiance(self.observations, self.contre_exemples)

    @property
    def est_servi(self) -> bool:
        """Ce souvenir peut-il être servi au modèle ?

        Faux pour un concept contredit plus souvent que confirmé. Il reste dans les
        métadonnées : il n'est pas supprimé, il est mis à l'écart.
        """
        if self.est_episodique:
            return True
        from llm.concepts import est_hors_service

        return not est_hors_service(self.observations, self.contre_exemples)

    @property
    def est_depasse(self) -> bool:
        """Au moins trois contradictions ET plus de contradictions que de confirmations."""
        if self.est_episodique:
            return False
        from llm.concepts import est_depasse as _est_depasse

        return _est_depasse(self.observations, self.contre_exemples)

    @property
    def horodatage_de_reference(self) -> datetime:
        """D'où part la décroissance : le dernier rappel, à défaut l'écriture."""
        return self.dernier_rappel or self.timestamp

    def to_dict(self) -> Dict:
        # JSON-safe : timestamps en ISO et memory_type en valeur str (round-trip avec from_dict)
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat(),
            'memory_type': str(self.memory_type),
            'dernier_rappel': self.dernier_rappel.isoformat() if self.dernier_rappel else None,
            'derniere_observation': (
                self.derniere_observation.isoformat() if self.derniere_observation else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryEntry':
        # Copie défensive : `from_dict` ne doit pas modifier le dictionnaire de l'appelant.
        data = dict(data)
        try:
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        except Exception as e:
            print(f"Error parsing timestamp: {e}, data: {data}")
            raise e
        if data.get('derniere_observation'):
            try:
                data['derniere_observation'] = datetime.fromisoformat(
                    data['derniere_observation']
                )
            except (TypeError, ValueError):
                data['derniere_observation'] = None
        if data.get('dernier_rappel'):
            try:
                data['dernier_rappel'] = datetime.fromisoformat(data['dernier_rappel'])
            except (TypeError, ValueError):
                # Un dernier rappel illisible ne doit pas faire perdre le souvenir : on
                # retombe sur l'écriture, ce qui ne fait que VIEILLIR l'entrée — jamais
                # l'inverse, qui la rajeunirait à tort.
                data['dernier_rappel'] = None
        if isinstance(data.get('memory_type'), str):
            data['memory_type'] = MemoryType(data['memory_type'])
        # Ticket 071 (lot 1) — les clés INCONNUES sont ignorées au lieu de faire éclater
        # `cls(**data)`. Sans cela, revenir en arrière sur ce ticket rendrait illisibles
        # toutes les métadonnées écrites entre-temps : un champ retiré du code suffirait à
        # perdre la mémoire de mille agents. C'est une garantie de réversibilité.
        connus = {f.name for f in fields(cls)}
        inconnus = set(data) - connus
        if inconnus:
            from loguru import logger
            logger.debug(
                f"[memory] champs inconnus ignorés au rechargement : {sorted(inconnus)} "
                f"(entrée écrite par une autre version du schéma)"
            )
        return cls(**{k: v for k, v in data.items() if k in connus})

    def __str__(self) -> str:
        timestamp_str = self.timestamp.strftime("%Y-%m-%d %H:%M")
        return f"[{timestamp_str}]: {self.content}"
