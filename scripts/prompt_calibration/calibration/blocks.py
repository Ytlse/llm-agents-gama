"""Décomposition / recomposition du prompt en blocs — phase 1 du ticket 004.

Fonctions **pures** (aucun état, aucun appel réseau), donc entièrement testables :
- ``decompose_prompt`` : découpe le prompt en blocs au niveau phrase / puce /
  item numéroté ; le schéma JSON final est isolé dans un bloc verrouillé.
- ``blocks_to_prompt`` : reconstruit le texte du prompt à partir des blocs.

L'aller-retour ``blocks_to_prompt(decompose_prompt(text))`` regroupe les phrases
d'un même paragraphe ; il n'est pas caractère-pour-caractère identitaire au texte
d'origine, mais il est **idempotent** : re-décomposer puis recomposer le résultat
redonne exactement le même texte (propriété vérifiée par les tests).

Portage fidèle de l'ancienne lib (``prompt_calibration_lib.py``), sans les globals.
"""

from __future__ import annotations

import re
from itertools import groupby

# Découpe en phrases françaises : après .!? + espace + majuscule (accentuée incluse).
_SENT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-ZÀÂÄÉÈÊËÎÏÔÙÛÜ])')


def split_sentences(txt: str) -> list[str]:
    """Découpe un texte en phrases sur frontière ``.!?`` + majuscule."""
    return [s.strip() for s in _SENT_RE.split(txt.strip()) if s.strip()]


def decompose_prompt(text: str) -> list[dict]:
    """Décompose le prompt en blocs (1 phrase = 1 bloc). Le schéma JSON est verrouillé.

    Chaque bloc est un dict ``{"name", "mutable", "content"}``. Les noms encodent
    la structure (``intro_sN``, ``consigne_sN``, ``instr_N``, ``bullet_N``,
    ``block_M_sN``, ``json_schema``), ce qui pilote le regroupement en paragraphes
    à la reconstruction.
    """
    blocks: list[dict] = []
    sections = [s.strip() for s in re.split(r'\n\n+', text) if s.strip()]

    # Localiser le schéma JSON (non-mutable) : dernières sections à partir du
    # premier marqueur de schéma.
    schema_start = None
    for i, s in enumerate(sections):
        if ('"type"' in s and '"properties"' in s) or 'Schéma JSON' in s:
            schema_start = i
            break

    content_secs = sections[:schema_start] if schema_start is not None else sections
    schema_text = '\n\n'.join(sections[schema_start:]) if schema_start is not None else None

    bullet_count = 0
    intro_count = 0
    block_idx = 0

    for section in content_secs:
        lines = [l.strip() for l in section.split('\n') if l.strip()]
        if not lines:
            continue

        if any(l.startswith('- ') for l in lines):
            # Section à puces : traite les lignes dans l'ordre pour préserver la
            # position relative des puces (ex. puce entre étape 2 et étape 3).
            i = 0
            while i < len(lines):
                if lines[i].startswith('- '):
                    bullet_count += 1
                    blocks.append({"name": f"bullet_{bullet_count}", "mutable": True,
                                   "content": lines[i]})
                    i += 1
                else:
                    header_run = []
                    while i < len(lines) and not lines[i].startswith('- '):
                        header_run.append(lines[i])
                        i += 1
                    for sent in split_sentences('\n'.join(header_run)):
                        idx = sum(1 for b in blocks if b['name'].startswith('consigne_s'))
                        blocks.append({"name": f"consigne_s{idx + 1}", "mutable": True,
                                       "content": sent})

        elif re.search(r'Instructions\s*:', section) or (lines and re.match(r'\d+\.', lines[0])):
            # Bloc instructions : en-tête séparé + chaque item numéroté = un bloc.
            instr_m = re.match(r'^(Instructions\s*:)\s*\n?', section)
            remainder = section
            if instr_m:
                blocks.append({"name": "instr_header", "mutable": True,
                               "content": instr_m.group(1)})
                remainder = section[instr_m.end():]
            for item in re.split(r'\n(?=\d+\.)', remainder.strip()):
                item = item.strip()
                if not item:
                    continue
                m = re.match(r'^(\d+)\.', item)
                name = f"instr_{m.group(1)}" if m else "instr_misc"
                blocks.append({"name": name, "mutable": True, "content": item})

        elif not any(b['name'].startswith('intro_s') for b in blocks):
            # Premier bloc de prose → intro, une phrase = un bloc.
            for sent in split_sentences(section):
                intro_count += 1
                blocks.append({"name": f"intro_s{intro_count}", "mutable": True,
                               "content": sent})

        else:
            # Autres sections prose → block_N_sM.
            block_idx += 1
            for i, sent in enumerate(split_sentences(section), 1):
                blocks.append({"name": f"block_{block_idx}_s{i}", "mutable": True,
                               "content": sent})

    if schema_text:
        blocks.append({"name": "json_schema", "mutable": False, "content": schema_text})

    return blocks


def _group_key(name: str) -> str:
    if re.match(r'intro_s\d+', name):
        return "intro"
    if re.match(r'consigne_s\d+', name):
        return "consigne"
    if re.match(r'instr_', name):
        return "instr"
    m = re.match(r'(block_\d+)_s\d+', name)
    if m:
        return m.group(1)
    return name  # bullet_N, inserted_N, json_schema → paragraphe isolé


def blocks_to_prompt(blocks: list[dict]) -> str:
    """Reconstruit le prompt : les phrases d'un même groupe forment un paragraphe.

    Puces et items d'instructions sont séparés par ``\\n`` ; la prose par un espace.
    Les blocs vides sont ignorés.
    """
    paragraphs = []
    non_empty = (b for b in blocks if b["content"].strip())
    for key, group in groupby(non_empty, key=lambda b: _group_key(b["name"])):
        items = [b["content"].strip() for b in group]
        sep = "\n" if key.startswith("bullet") or key == "instr" else " "
        paragraphs.append(sep.join(items))
    return "\n\n".join(paragraphs)


def prompt_word_count(blocks: list[dict]) -> int:
    """Nombre de mots du prompt reconstruit (métrique de compaction, phase 4)."""
    return len(blocks_to_prompt(blocks).split())
