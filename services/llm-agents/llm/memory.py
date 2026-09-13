from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass, asdict


# LLM imports
from enum import Enum

class MemoryType(Enum):
    CONVERSATION = "conversation"
    REFLECTION = "reflection"
    CONCEPT = "concept"
    SUMMARY = "summary"

    def __str__(self):
        return str(self.value)

@dataclass
class MemoryEntry:
    """Represents a memory entry with metadata"""
    content: str
    timestamp: datetime
    memory_type: MemoryType
    person_id: str
    activity_id: Optional[str] = None
    tags: Optional[str] = ""

    def to_dict(self) -> Dict:
        # JSON-safe : timestamp en ISO et memory_type en valeur str (round-trip avec from_dict)
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat(),
            'memory_type': str(self.memory_type),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryEntry':
        try:
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        except Exception as e:
            print(f"Error parsing timestamp: {e}, data: {data}")
            raise e
        if isinstance(data.get('memory_type'), str):
            data['memory_type'] = MemoryType(data['memory_type'])
        return cls(**data)
    
    def __str__(self) -> str:
        timestamp_str = self.timestamp.strftime("%Y-%m-%d %H:%M")
        return f"[{timestamp_str}]: {self.content}"

