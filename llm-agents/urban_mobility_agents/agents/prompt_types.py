from enum import Enum

class PromptName(str, Enum):
    """Enum for prompt names to avoid using string literals."""
    QUERY_EXPERIENCES = "query_experiences"
    PERSONAL_SYSTEM = "personal_system"
    REFLECTION = "reflection"
    LONGTERM_REFLECTION = "longterm_reflection"