"""
settings/models.py — Shim de compatibilité.

Les modèles vivent désormais dans llm_module.core.models (restructuration en
package, cf. docs/arch/llm-module-package-refactor.md). Ce module est conservé
pour les consommateurs externes (scripts/models_influence/prompt_calibration_lib.py,
notebooks) ; préférer les imports depuis llm_module.core.models.
"""

from llm_module.core.models import *  # noqa: F401,F403
from llm_module.core.models import _FALLBACK_PRIORITY_SCORE  # noqa: F401
