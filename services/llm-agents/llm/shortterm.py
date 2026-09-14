from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from llama_index.core.llms import ChatMessage

# Embedding imports
from loguru import logger

from llm.memory import MemoryEntry, MemoryType


class UserShortTermMemory:
    """Manages short-term conversational memory for a specific user"""
    
    def __init__(self, person_id: str):
        self.person_id = person_id
        self.recent_entries: List[MemoryEntry] = []
        self.max_entries = 100
        self.last_activity = datetime.now()
    
    def add_message(
        self,
        msg: str,
        timestamp: Optional[datetime] = None,
        activity_id: Optional[str] = None,
        importance: float = 0.0,
        axes: Optional[dict] = None,
    ):
        """Add a chat message to short-term memory.

        `importance` (ticket 071, lot 1) est la gravité DÉTERMINISTE de l'entrée, calculée
        depuis ce que la simulation a mesuré : retard subi, correspondance ratée, mode
        contraint. Elle ne coûte aucun appel au modèle et elle est objective.

        Elle sert à deux choses, toutes deux en aval : décider si la journée de l'agent
        constitue une RUPTURE qui déclenche une consolidation immédiate, et fournir le
        PLANCHER que le jugement du modèle ne pourra pas descendre lors de la réflexion.
        """
        self.last_activity = datetime.now()

        #logger.info(f"User {self.person_id} added message at {self.last_activity} for activity: {activity_id}")

        # Create memory entry
        entry = MemoryEntry(
            content=msg,
            timestamp=timestamp or datetime.now(),
            memory_type=MemoryType.CONVERSATION,
            person_id=self.person_id,
            activity_id=activity_id,
            importance=float(importance or 0.0),
            # Les axes sont normalisés À L'ÉCRITURE (ticket 071, lot 2) : c'est ici qu'on sait
            # quel mode a été retenu, sous quelle météo et pour quel motif. Les recalculer au
            # rappel referait le même travail à chaque décision, sur le chemin critique — et
            # deux graphies de la même ligne ne se rencontreraient jamais.
            **{k: v for k, v in (axes or {}).items() if k.startswith("axe_")},
        )
        
        self.recent_entries.append(entry)
        
        # Keep only recent entries
        if len(self.recent_entries) > self.max_entries:
            self.recent_entries = self.recent_entries[-self.max_entries:]
    
    def get_all(self) -> List[ChatMessage]:
        """Get all messages from short-term memory"""
        return [entry.content for entry in self.recent_entries]

    def get_all_messages(self) -> List[MemoryEntry]:
        """Get all memory entries"""
        return self.recent_entries

    def get_all_message_and_group(self) -> Tuple[List[List[MemoryEntry]], List[MemoryEntry]]:
        all_entries = self.get_all_messages()
        # for loop to reserve the order
        results = []
        buffer = []
        for entry in all_entries:
            if buffer and entry.activity_id != buffer[-1].activity_id:
                results.append(buffer)
                buffer = []
            if entry.activity_id:
                buffer.append(entry)
            else:
                results.append([entry])
        if buffer:
            results.append(buffer)
        return results, all_entries

    def get_recent_entries(self, hours: int = 24) -> List[MemoryEntry]:
        """Get recent memory entries within specified hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [entry for entry in self.recent_entries if entry.timestamp > cutoff]
    
    def gravite_cumulee(self) -> float:
        """Somme des gravités déterministes du tampon (ticket 071, lot 1).

        C'est le mécanisme de déclenchement de Park et al. (2023, § 4.2), qui remplace un
        compte d'entrées par une somme d'importances. Différence à dire : chez eux le seuil
        se franchit deux ou trois fois par jour, c'est un régime courant ; ici il est
        EXCEPTIONNEL par construction du seuil, la consolidation de base restant le plancher
        journalier de 22 h.
        """
        return float(sum(float(e.importance or 0.0) for e in self.recent_entries))

    def gravite_maximale(self) -> float:
        """La plus forte gravité du tampon — le plancher de la règle du maximum."""
        return max((float(e.importance or 0.0) for e in self.recent_entries), default=0.0)

    def clear(self):
        """Clear short-term memory"""
        self.recent_entries.clear()

    def remove_batch(self, entries: List[MemoryEntry]):
        """Remove a batch of entries from short-term memory"""
        self.recent_entries = [entry for entry in self.recent_entries if entry not in entries]
