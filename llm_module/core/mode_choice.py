"""
core/mode_choice.py — Du vecteur de probabilités renvoyé par le LLM au mode tiré.

Le LLM ne choisit plus une option : il attribue à **chaque** option proposée la
probabilité que le persona la retienne (somme = 100). Le choix effectif est un
tirage aléatoire dans cette distribution, ce qui restitue au niveau agrégé la
variabilité des comportements individuels au lieu d'un argmax déterministe.

Trois responsabilités, toutes **pures** (aucun I/O, aucune dépendance provider) :

1. ``normalize_option_probabilities`` — nettoie le vecteur brut du LLM (index hors
   bornes, doublons, négatifs, somme ≠ 100) et le ramène à une distribution
   index-alignée sur les options réellement proposées ;
2. ``mode_distribution`` — projette cette distribution sur la liste **canonique**
   des modes : un mode absent des options (ex. la marche quand le trajet est trop
   long) reçoit explicitement 0 %, ce qui rend les répartitions comparables d'un
   agent à l'autre et d'un run à l'autre ;
3. ``draw_index`` — tire une option selon ses probabilités, avec une graine
   dérivée de façon déterministe du contexte de décision : deux runs identiques
   rejouent le même tirage, mais un même agent retire différemment d'un jour à
   l'autre (et donc à chaque cache hit sur un nouveau jour simulé).

Partagé entre le worker (métriques), les agents de simulation (décision + cache
sémantique) et le module de calibration de prompt, pour que tous appliquent
exactement la même politique de décision.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any, Iterable, Mapping, Optional, Sequence

from llm_module.telemetry.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Modes canoniques
# ---------------------------------------------------------------------------

# Liste fermée des modes sur laquelle toute répartition est exprimée. Un mode
# non proposé dans les options reste présent avec 0 % (cf. mode_distribution).
# Aligné sur la palette de référence du projet (cf. .claude/CLAUDE.md).
CANONICAL_MODES: tuple[str, ...] = (
    "walking",
    "cycling",
    "car",
    "public_transport",
    "train",
    "motorbike",
)

# Bucket de débordement : modes non reconnus. Hors CANONICAL_MODES pour ne pas
# polluer les comparaisons, mais conservé dans la répartition pour que la somme
# reste 1 quoi qu'il arrive.
OTHER_MODE = "other"

# Mots-clés → mode canonique, du plus spécifique au plus générique. L'ordre compte :
# une chaîne composée ("foot,bus,foot") contient aussi "foot", or c'est le tronçon
# structurant (le bus) qui qualifie le trajet.
_MODE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("train", ("rail", "train", "ter", "intercités", "intercites")),
    ("public_transport", ("metro", "métro", "subway", "tram", "tramway", "bus",
                          "transit", "public_transport", "transports en commun",
                          "transport en commun", "transports_collectifs", "tc")),
    ("motorbike", ("scooter", "moto", "motorbike", "motorcycle", "deux-roues",
                   "deux_roues")),
    ("car", ("car", "driving", "voiture", "conducteur", "taxi")),
    ("cycling", ("bicycle", "bike", "cycling", "vélo", "velo")),
    ("walking", ("foot", "walk", "walking", "marche", "à pied", "a pied", "pied")),
)


def canonical_mode(raw: Optional[str]) -> str:
    """Réduit une chaîne de modes (« foot,bus,foot », « BICYCLE ») à un mode canonique.

    Renvoie ``OTHER_MODE`` si aucun mot-clé connu n'est reconnu — le cas est tracé
    en WARNING car il signale soit un mode d'itinéraire nouveau, soit un libellé
    inventé par le LLM.
    """
    if not raw:
        return OTHER_MODE
    text = str(raw).lower()
    parts = {p.strip() for p in text.replace("+", ",").split(",") if p.strip()}
    for mode, keywords in _MODE_KEYWORDS:
        for kw in keywords:
            # Égalité sur un tronçon d'abord (« bus » dans « foot,bus,foot »), puis
            # sous-chaîne pour les libellés en toutes lettres (« transports en commun »).
            # Les mots courts sont exclus de la recherche par sous-chaîne : « tc » ou
            # « car » se retrouvent dans trop de mots pour être fiables ainsi.
            if kw in parts or (len(kw) >= 5 and kw in text):
                return mode
    logger.warning(f"Mode de transport non reconnu, classé 'other' | mode={raw!r}")
    return OTHER_MODE


# ---------------------------------------------------------------------------
# Normalisation du vecteur brut
# ---------------------------------------------------------------------------

class UniformFallback(list):
    """Vecteur uniforme issu d'un repli (vecteur LLM absent ou de somme nulle).

    Sous-classe de ``list`` : tout appelant le traite comme un vecteur normal
    (tirage, métriques, égalité avec une liste simple). Mais ce n'est PAS une
    décision du modèle — les appelants qui PERSISTENT une distribution (cache
    LLM) doivent le tester (``isinstance``) et refuser l'écriture, sans quoi le
    repli d'un run pollue les tirages de tous les runs suivants (constaté le
    2026-08-03 : troncatures cerebras_zai-glm-4.7 → distributions uniformes
    écrites en cache comme des décisions légitimes).
    """


def _entry_field(entry: Any, name: str) -> Any:
    """Lit un champ d'une entrée qu'elle soit dict ou modèle Pydantic."""
    if isinstance(entry, Mapping):
        return entry.get(name)
    return getattr(entry, name, None)


def _as_float(value: Any) -> Optional[float]:
    """Coerce une probabilité (« 40 », « 40 % », 0.4) en float, None si illisible."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _options_matching_mode(raw_mode: Optional[str], modes: Sequence[Optional[str]]) -> list[int]:
    """Options que désigne le libellé de mode d'une entrée dont l'index est hors bornes.

    Deux passes, de la plus sûre à la plus tolérante :
    1. égalité de chaîne avec le mode envoyé — le modèle le recopie tel quel, c'est
       une désignation sans ambiguïté ;
    2. égalité de mode canonique (« Marche jusqu'à 'work' » → ``walking``), qui rattrape
       les entrées où il a reformulé l'étiquette.

    Renvoie la liste des options candidates (vide si aucune) : plusieurs options peuvent
    partager un mode, à l'appelant de décider quoi en faire.
    """
    if not raw_mode:
        return []
    text = " ".join(str(raw_mode).strip().lower().split())
    exact = [i for i, m in enumerate(modes)
             if m and " ".join(str(m).strip().lower().split()) == text]
    if exact:
        return exact
    target = canonical_mode(raw_mode)
    if target == OTHER_MODE:
        return []
    return [i for i, m in enumerate(modes) if m and canonical_mode(m) == target]


def normalize_option_probabilities(
    entries: Optional[Iterable[Any]],
    n_options: int,
    *,
    modes: Optional[Sequence[Optional[str]]] = None,
    context: str = "",
) -> list[float]:
    """Convertit le vecteur brut du LLM en distribution index-alignée sur les options.

    ``entries`` : itérable de ``{index, probability}`` (dicts ou ``OptionProbability``).
    ``modes`` : mode **envoyé** pour chaque option (source de vérité) ; fourni, il permet
    de rattraper les vecteurs renumérotés (cf. plus bas). Retourne une liste de
    ``n_options`` flottants de somme 1.

    Tolérances — le LLM se trompe, la simulation ne doit pas s'arrêter pour autant :
    - les probabilités sont acceptées en % (somme 100) comme en fractions (somme 1) :
      la normalisation finale rend l'échelle indifférente ;
    - une entrée d'index illisible est ignorée (tracée) ;
    - plusieurs entrées sur le même index sont sommées ;
    - une probabilité négative est ramenée à 0 ;
    - une option jamais notée reçoit 0 ;
    - si le total est nul ou le vecteur absent, repli sur l'uniforme (le tirage
      reste possible, et l'anomalie est tracée en ERROR : la décision du modèle est
      alors perdue, la répartition modale du run en porte la trace).

    Index hors bornes — certains modèles renumérotent les options (ils comptent les
    étapes détaillées d'un itinéraire, ou continuent la numérotation d'un persona à
    l'autre dans un lot) et placent la masse sur des index inexistants. Avec ``modes``,
    l'entrée est réalignée sur l'option que son libellé désigne ; si plusieurs options
    partagent ce mode, la masse est répartie entre elles — arbitraire quant à
    l'itinéraire exact, mais fidèle à la **part modale**, qui est la mesure. Sans
    ``modes`` (ou libellé non reconnu), l'entrée est écartée : mieux vaut perdre la
    masse que la placer sur la mauvaise option.
    """
    if n_options <= 0:
        return []

    weights = [0.0] * n_options
    seen = False

    for entry in entries or ():
        raw_index = _entry_field(entry, "index")
        try:
            idx = int(raw_index)
        except (TypeError, ValueError):
            logger.warning(f"Probabilité ignorée : index illisible {raw_index!r} | {context}")
            continue
        prob = _as_float(_entry_field(entry, "probability"))
        if prob is None:
            logger.warning(f"Probabilité ignorée : valeur illisible pour l'index {idx} | {context}")
            continue
        prob = max(0.0, prob)

        if not 0 <= idx < n_options:
            if prob <= 0:
                # Une option notée 0 sur un index inexistant ne coûte rien : c'est le
                # bruit de la renumérotation, pas la peine d'en inonder les logs.
                logger.debug(
                    f"Entrée hors bornes à probabilité nulle ignorée : index {idx} "
                    f"(0..{n_options - 1}) | {context}"
                )
                continue
            raw_mode = _entry_field(entry, "mode")
            targets = _options_matching_mode(raw_mode, modes or ())
            if not targets:
                logger.warning(
                    f"Probabilité perdue : index {idx} hors bornes (0..{n_options - 1}), "
                    f"mode {raw_mode!r} non réalignable — {prob:g} point(s) écartés | {context}"
                )
                continue
            where = f"l'option {targets[0]}" if len(targets) == 1 \
                else f"les options {targets} (masse répartie à parts égales)"
            logger.warning(
                f"Index {idx} hors bornes (0..{n_options - 1}) réaligné sur {where} "
                f"via son mode {raw_mode!r} — {prob:g} point(s) conservés | {context}"
            )
            for target in targets:
                weights[target] += prob / len(targets)
            seen = True
            continue

        weights[idx] += prob
        seen = True

    total = sum(weights)
    if not seen or total <= 0:
        logger.error(
            f"[ALARME] Vecteur de probabilités inexploitable "
            f"({'absent' if not seen else 'somme nulle'}) — repli sur une distribution "
            f"uniforme sur {n_options} option(s), la décision du modèle est perdue | {context}"
        )
        return UniformFallback(1.0 / n_options for _ in range(n_options))

    return [w / total for w in weights]


def option_modes(entries: Optional[Iterable[Any]], n_options: int) -> list[Optional[str]]:
    """Extrait le libellé de mode annoncé par le LLM pour chaque index d'option."""
    modes: list[Optional[str]] = [None] * n_options
    for entry in entries or ():
        try:
            idx = int(_entry_field(entry, "index"))
        except (TypeError, ValueError):
            continue
        if 0 <= idx < n_options:
            mode = _entry_field(entry, "mode")
            if mode:
                modes[idx] = str(mode)
    return modes


# ---------------------------------------------------------------------------
# Répartition par mode
# ---------------------------------------------------------------------------

def mode_distribution(
    weights: Sequence[float],
    modes: Sequence[Optional[str]],
) -> dict[str, float]:
    """Agrège une distribution sur les options en répartition par mode canonique.

    Toutes les clés de ``CANONICAL_MODES`` sont présentes : un mode qu'aucune option
    ne propose (marche exclue parce que le trajet est trop long, train inexistant sur
    l'axe…) vaut explicitement 0.0 — c'est ce qui rend deux répartitions comparables
    sans se demander si le mode était offert. ``other`` n'apparaît que s'il est non nul.

    Les poids sont supposés normalisés (cf. ``normalize_option_probabilities``) ;
    la somme des valeurs vaut donc 1 (aux arrondis flottants près).
    """
    dist: dict[str, float] = {m: 0.0 for m in CANONICAL_MODES}
    for i, w in enumerate(weights):
        mode = canonical_mode(modes[i] if i < len(modes) else None)
        if mode == OTHER_MODE:
            dist[OTHER_MODE] = dist.get(OTHER_MODE, 0.0) + w
        else:
            dist[mode] += w
    if dist.get(OTHER_MODE) == 0.0:
        dist.pop(OTHER_MODE, None)
    return dist


# ---------------------------------------------------------------------------
# Tirage
# ---------------------------------------------------------------------------

def derive_seed(*parts: Any) -> int:
    """Graine 64 bits dérivée du contexte de décision (agent, activité, jour, run).

    Déterministe et stable entre processus (contrairement à ``hash()``), ce qui
    rend un run rejouable à l'identique tout en faisant varier le tirage d'un
    contexte à l'autre.
    """
    raw = "|".join("" if p is None else str(p) for p in parts)
    return int.from_bytes(hashlib.sha256(raw.encode("utf-8")).digest()[:8], "big")


def draw_index(weights: Sequence[float], *seed_parts: Any) -> int:
    """Tire l'index d'une option proportionnellement à sa probabilité.

    Sans ``seed_parts``, le tirage utilise une instance ``Random`` fraîche, non
    rejouable. Avec, la graine est dérivée du contexte : même contexte → même tirage.
    """
    if not weights:
        raise ValueError("draw_index: aucune option à tirer")
    rng = random.Random(derive_seed(*seed_parts)) if seed_parts else random.Random()
    total = sum(weights)
    if total <= 0:
        return rng.randrange(len(weights))
    # random.choices tolère des poids non normalisés — inutile de re-normaliser.
    return rng.choices(range(len(weights)), weights=weights, k=1)[0]


def argmax_index(weights: Sequence[float]) -> int:
    """Index de l'option la plus probable (départage : le plus petit index).

    Sert aux métriques et au repli déterministe, jamais à la décision de l'agent.
    """
    if not weights:
        raise ValueError("argmax_index: aucune option")
    return max(range(len(weights)), key=lambda i: weights[i])
