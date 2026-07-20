"""Archive tabu dure des mutations rejetées — phase 4.1 du ticket 004 (D3).

Objectif : ne **jamais payer une éval** pour une mutation quasi identique à une
mutation déjà rejetée récemment. À chaque proposition, on calcule l'embedding de
sa *signature* ``(target_block, new_content)`` ; si sa similarité cosinus dépasse
``tabu_threshold`` avec une entrée tabu **non expirée**, elle est rejetée
immédiatement (``rejected_tabu``), sans appel provider.

**Tenure** (demande explicite du brainstorming) : une entrée tabu expire après
``tabu_tenure`` mutations acceptées — le contexte du prompt a changé, la
retentative redevient légitime. On enregistre l'entrée avec le compteur
``expires_after_accepted = accepted_count + tenure`` ; elle est active tant que
le nombre d'acceptations courant lui est inférieur.

**Embedding local par défaut** : *feature hashing* de n-grammes de mots (aucune
dépendance, déterministe, suffisant pour détecter des quasi-doublons textuels).
Il est **injectable** (``embed_fn``) — un vrai modèle d'embedding provider peut
le remplacer sans changer la logique de rejet.
"""

from __future__ import annotations

import re
from typing import Callable, Optional

import numpy as np

from .store import RunStore

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

EmbedFn = Callable[[str], np.ndarray]


def mutation_signature(mutation: dict) -> str:
    """Texte discriminant d'une mutation (ce que le tabu compare).

    On concatène l'opérateur, le bloc ciblé et le nouveau contenu (+ le second
    bloc pour un merge) : deux propositions qui touchent le même bloc avec un
    contenu quasi identique tombent proches, même reformulées.
    """
    return "\n".join([
        str(mutation.get("action", "modify")),
        str(mutation.get("target_block", "")),
        str(mutation.get("second_block", "")),
        str(mutation.get("new_content", "")),
    ]).strip()


def hash_embedding(text: str, dim: int = 256) -> np.ndarray:
    """Embedding local déterministe par *feature hashing* d'uni/bi-grammes de mots.

    Chaque token et bigramme est projeté (hash → index de bucket, signe → ±1) sur
    un vecteur de dimension ``dim``, ensuite L2-normalisé. La similarité cosinus de
    deux textes proches est élevée ; aucune dépendance externe.
    """
    vec = np.zeros(dim, dtype=np.float32)
    tokens = _TOKEN_RE.findall(text.lower())
    grams = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
    for gram in grams:
        h = hash_str(gram)
        vec[h % dim] += 1.0 if (h >> 32) & 1 else -1.0
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def hash_str(s: str) -> int:
    """Hash stable inter-process (``hash()`` est salé par interpréteur)."""
    import hashlib
    return int.from_bytes(hashlib.blake2b(s.encode("utf-8"), digest_size=8).digest(), "big")


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Similarité cosinus (vecteurs supposés L2-normalisés → simple produit scalaire)."""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class TabuArchive:
    """Archive tabu persistée dans le store (table ``tabu``).

    ``embed_fn`` par défaut = :func:`hash_embedding`. La similarité est comparée à
    ``config.tabu_threshold`` ; la tenure vient de ``config.tabu_tenure``.
    """

    def __init__(self, store: RunStore, threshold: float, tenure: int,
                 embed_fn: Optional[EmbedFn] = None):
        self.store = store
        self.threshold = threshold
        self.tenure = tenure
        self.embed_fn = embed_fn or hash_embedding

    def embed(self, mutation: dict) -> np.ndarray:
        return self.embed_fn(mutation_signature(mutation))

    def is_tabu(self, mutation: dict, accepted_count: int) -> tuple[bool, float]:
        """La mutation est-elle un quasi-doublon d'un rejet non expiré ?

        Renvoie ``(tabu, similarité_max)``. Une entrée dont
        ``expires_after_accepted <= accepted_count`` est expirée (tenure écoulée)
        et ignorée.
        """
        vec = self.embed(mutation)
        best = 0.0
        for emb_bytes, expires in self.store.active_tabu(accepted_count):
            other = np.frombuffer(emb_bytes, dtype=np.float32)
            if other.shape != vec.shape:
                continue
            sim = cosine(vec, other)
            best = max(best, sim)
            if sim >= self.threshold:
                return True, sim
        return False, best

    def add(self, mutation: dict, mutation_id: Optional[int],
            accepted_count: int) -> None:
        """Enregistre le rejet : tenure = ``accepted_count + self.tenure``."""
        vec = self.embed(mutation)
        self.store.record_tabu(vec.astype(np.float32).tobytes(), mutation_id,
                               accepted_count + self.tenure)
