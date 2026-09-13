"""llm_module — COQUILLE DE COMPATIBILITÉ.

Le code vit désormais dans trois paquets (ticket 037) :

* ``llm_gateway``   — gateway LLM générique (api, worker, adapters, SDK, config) ;
* ``mobility_core`` — domaine de l'enquête EMC² Toulouse (couronnes, modes, vélo, logement) ;
* ``mobility_llm``  — catégories LLM de la mobilité (persona, prompts, choix modal).

Chaque sous-module de ``llm_module`` réexporte son successeur et émet un DeprecationWarning.
Retrait prévu à la version majeure suivante de llm-gateway (2.0).
"""
