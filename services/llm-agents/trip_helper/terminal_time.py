"""Temps terminal par mode — accès et diffusion d'un trajet véhiculé.

Source de vérité UNIQUE du paramètre décrit par le ticket 013 : les valeurs, leur
provenance et les libellés de rendu vivent dans ``config/terminal_time.yaml``.
Trois consommateurs la partagent, et c'est ce qui garantit qu'ils ne divergent
pas :

- :func:`trip_helper.osmnx_direct._make_travel_plan` — construit les jambes
  d'accès et de diffusion (c'est la décision T3 : la correction est dans la
  construction du scénario, pas dans le gabarit d'affichage) ;
- ``text_helper/models/travel_plan.py`` — restitue la décomposition ;
- les clés de cache (routage OSMnx persistant, décisions LLM) via
  :func:`data_version`.

Le module est **pur** : pas d'I/O au-delà de la lecture du YAML au premier appel,
pas d'état mutable, donc testable sans réseau ni conteneur.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import hashlib

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "terminal_time.yaml"

# Marqueurs de route des jambes terminales. Ils jouent le même rôle que
# ``DIRECT_ROUTE_MARKER`` : rendre la jambe reconnaissable sans deviner d'après
# son mode. Les jambes terminales portent ``is_transfer=True``, ce qui les exclut
# de ``TravelPlan.get_code()`` — invariant CRITIQUE : le code de plan est la clé
# du cache de décisions et de la déduplication d'itinéraires, il ne doit pas
# changer parce qu'on décompose l'affichage.
# Sel du tirage du temps terminal. Versionné : le changer rebat tous les temps
# terminaux, donc les plans ET les décisions LLM mises en cache. À ne bouger qu'avec
# `version` ci-dessous.
DRAW_SALT = "terminal_time_v1"

TERMINAL_ACCESS_ROUTE = "__TERMINAL_ACCESS__"
TERMINAL_EGRESS_ROUTE = "__TERMINAL_EGRESS__"


@dataclass(frozen=True)
class TerminalProfile:
    """Profil terminal d'un mode : durées PAR ZONE (secondes) et libellés de rendu.

    Les durées sont des tables ``{couronne: secondes}`` avec une entrée ``default``.
    L'accès se tarife sur la couronne d'ORIGINE (où le véhicule est garé), la
    diffusion sur celle de DESTINATION (où il faut trouver une place) : les deux
    bouts d'un même trajet peuvent donc être tarifés différemment.
    """

    mode: str
    access_by_zone: dict[str, int]
    egress_by_zone: dict[str, int]
    provenance: str
    spatialise: bool
    labels: dict[str, str]
    # Lois par couronne, `{couronne: {secondes: probabilité}}`. Présentes → le temps
    # terminal est TIRÉ dedans ; absentes → les tables constantes ci-dessus font foi.
    # Les deux mécanismes coexistent : la voiture et le vélo sont sur loi depuis tt3,
    # un mode futur peut rester sur constante sans que rien ne change pour lui.
    access_law_by_zone: dict[str, dict[int, float]] = field(default_factory=dict)
    egress_law_by_zone: dict[str, dict[int, float]] = field(default_factory=dict)

    def _draw(self, law: dict[int, float], key: str) -> int:
        """Inverse de la fonction de répartition, sur un uniforme haché.

        Déterministe et sans RNG : le même trajet reçoit toujours le même temps
        terminal. Ce n'est pas un détail de confort — les plans sont mis en cache
        (OTP) et les décisions LLM le sont aussi ; un tirage aléatoire ferait
        diverger un run de sa reprise, et rendrait le cache de décisions faux.
        """
        digest = hashlib.sha256(f"{DRAW_SALT}:{key}".encode("utf-8")).digest()
        u = int.from_bytes(digest[:8], "big") / 2 ** 64
        cumulated = 0.0
        for seconds, probability in sorted(law.items()):
            cumulated += probability
            if u < cumulated:
                return int(seconds)
        return int(max(law)) if law else 0

    def _law_for(self, laws: dict[str, dict[int, float]], zone: str):
        return laws.get(zone) or laws.get("default")

    def access_s(self, zone: str = "", key: str = "") -> int:
        """Temps d'accès dans la couronne d'origine (repli ``default``).

        Avec une loi servie, ``key`` identifie le trajet : deux trajets distincts
        tirent indépendamment, le même trajet tire toujours pareil. Sans ``key``, le
        tirage retombe sur la couronne seule — tous les trajets d'une couronne
        reçoivent alors la même valeur, ce qui est un repli lisible et non un
        silence, mais pas ce qu'on veut en production.
        """
        law = self._law_for(self.access_law_by_zone, zone)
        if law:
            return self._draw(law, f"{self.mode}:access:{zone}:{key}")
        return int(self.access_by_zone.get(zone, self.access_by_zone["default"]))

    def egress_s(self, zone: str = "", key: str = "") -> int:
        """Temps de stationnement et de marche dans la couronne de destination."""
        law = self._law_for(self.egress_law_by_zone, zone)
        if law:
            return self._draw(law, f"{self.mode}:egress:{zone}:{key}")
        return int(self.egress_by_zone.get(zone, self.egress_by_zone["default"]))

    def total_s(self, origin_zone: str = "", dest_zone: str = "",
                key: str = "") -> int:
        return self.access_s(origin_zone, key) + self.egress_s(dest_zone, key)

    def mean_s(self, end: str, zone: str = "") -> float:
        """Espérance du temps terminal — pour les rapports, jamais pour le rendu."""
        laws = self.access_law_by_zone if end == "access" else self.egress_law_by_zone
        law = self._law_for(laws, zone)
        if law:
            return sum(s * p for s, p in law.items())
        table = self.access_by_zone if end == "access" else self.egress_by_zone
        return float(table.get(zone, table["default"]))

    def egress_label(self, destination: Optional[str]) -> str:
        """Libellé de la jambe de diffusion, nommant la destination si connue.

        ``purpose`` n'est posé sur le plan qu'après le routage
        (``simulation_controller``), donc le libellé ne peut pas être figé à la
        construction : il porte un ``{destination}`` interpolé au rendu. Sans
        destination, on retombe sur une formulation qui n'invente rien — même
        dégradation gracieuse que le gabarit des transports collectifs.
        """
        if destination:
            return self.labels["egress"].format(destination=destination)
        return self.labels["egress_sans_destination"]


_cache: Optional[dict] = None


def _load() -> dict:
    global _cache
    if _cache is None:
        with _CONFIG_PATH.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        _cache = _validate(raw)
    return _cache


def _validate(raw: dict) -> dict:
    """Refuse une configuration qui casserait la cohérence du rendu.

    Le contrôle sur les multiples de 60 s n'est pas du zèle : le rendu affiche
    chaque composante en minutes TRONQUÉES, et l'égalité « total affiché = somme
    des sous-étapes affichées » (critère d'acceptation 2 du ticket 013) ne tient
    que parce que ``floor(a + k×60) == floor(a) + k``. Une valeur de 90 s ferait
    afficher des décompositions qui ne somment pas à leur total — un défaut qui
    se lirait comme une incohérence du modèle, pas comme un bug de configuration.
    """
    if not raw.get("version"):
        raise ValueError(
            f"{_CONFIG_PATH.name} : `version` manquante. Elle entre dans les clés "
            f"de cache (routage et décisions LLM) ; sans elle, un changement de "
            f"temps terminal laisserait servir des durées et des décisions "
            f"périmées.")

    profiles: dict[str, TerminalProfile] = {}
    for mode, cfg in (raw.get("modes") or {}).items():
        # Lois par couronne (`*_law`), servies depuis tt3. Elles remplacent la constante
        # quand elles sont là : la moyenne mesurée sur EMC² est INFÉRIEURE À LA MINUTE
        # (0,36 min d'accès à Toulouse), et le rendu ne sait afficher que des minutes
        # entières. Une constante devrait donc valoir 0 partout, ce qui effacerait une
        # queue bien réelle — 2 à 4 % des trajets ont vraiment 5 minutes ou plus. Le
        # tirage garde les deux, la moyenne ET la queue.
        laws: dict[str, dict[str, dict[int, float]]] = {}
        for name in ("access_law", "egress_law"):
            raw_law = cfg.get(name)
            if raw_law is None:
                laws[name] = {}
                continue
            if not isinstance(raw_law, dict) or "default" not in raw_law:
                raise ValueError(
                    f"{_CONFIG_PATH.name} : {mode}.{name} doit être une table "
                    f"{{couronne: {{minutes: probabilité}}}} avec une entrée `default` "
                    f"— une zone hors couche EMC² tomberait sinon dans le vide.")
            built: dict[str, dict[int, float]] = {}
            for zone, pmf in raw_law.items():
                if not isinstance(pmf, dict) or not pmf:
                    raise ValueError(
                        f"{_CONFIG_PATH.name} : {mode}.{name}.{zone} vide. Tirer dans "
                        f"une loi vide rendrait 0 — une valeur plausible, donc un repli "
                        f"indétectable.")
                total = 0.0
                cell: dict[int, float] = {}
                for minutes, probability in pmf.items():
                    minutes, probability = int(minutes), float(probability)
                    if minutes < 0 or probability < 0:
                        raise ValueError(
                            f"{_CONFIG_PATH.name} : {mode}.{name}.{zone} — valeur "
                            f"négative ({minutes} min, p={probability}).")
                    # Les clés sont en MINUTES : converties en secondes ici, elles sont
                    # des multiples de 60 par construction, ce qui préserve l'invariant
                    # du rendu sans avoir à le vérifier.
                    cell[minutes * 60] = probability
                    total += probability
                if abs(total - 1.0) > 1e-3:
                    raise ValueError(
                        f"{_CONFIG_PATH.name} : {mode}.{name}.{zone} somme à {total:.4f} "
                        f"et non 1. Une loi qui ne somme pas à 1 fait taire une partie "
                        f"de la masse sans le dire.")
                built[zone] = cell
            laws[name] = built

        tables: dict[str, dict[str, int]] = {}
        for name in ("access_s", "egress_s"):
            table = cfg.get(name)
            if table is None and laws[name.replace("_s", "_law")]:
                # Mode servi par une loi : la constante devient facultative. On garde
                # un `default` à 0 pour que `access_s`/`egress_s` restent appelables
                # sans loi (repli de `_law_for` sur une couronne absente).
                tables[name] = {"default": 0}
                continue
            if not isinstance(table, dict):
                raise ValueError(
                    f"{_CONFIG_PATH.name} : {mode}.{name} doit être une table "
                    f"{{couronne: secondes}} avec une entrée `default` "
                    f"(le paramètre est spatialisé depuis la version tt2).")
            if "default" not in table:
                raise ValueError(
                    f"{_CONFIG_PATH.name} : {mode}.{name} sans entrée `default` — "
                    f"une zone inconnue tomberait dans le vide. Or une zone est "
                    f"inconnue dès qu'un point sort de la couche EMC², ce qui arrive.")
            for zone, value in table.items():
                value = int(value)
                if value < 0:
                    raise ValueError(
                        f"{_CONFIG_PATH.name} : {mode}.{name}.{zone} négatif ({value}).")
                if value % 60:
                    raise ValueError(
                        f"{_CONFIG_PATH.name} : {mode}.{name}.{zone} = {value} s n'est "
                        f"pas un multiple de 60. Le total affiché ne serait plus la "
                        f"somme des sous-étapes affichées (ticket 013, critère 2).")
            tables[name] = {z: int(v) for z, v in table.items()}
        labels = cfg.get("labels") or {}
        missing = {"access", "main", "egress", "egress_sans_destination",
                   "terminal"} - set(labels)
        if missing:
            raise ValueError(
                f"{_CONFIG_PATH.name} : libellés manquants pour {mode} : "
                f"{sorted(missing)}.")
        profiles[mode] = TerminalProfile(
            mode=mode, access_by_zone=tables["access_s"],
            egress_by_zone=tables["egress_s"],
            provenance=str(cfg.get("provenance", "unsourced")),
            spatialise=bool(cfg.get("spatialise", False)), labels=dict(labels),
            access_law_by_zone=laws["access_law"],
            egress_law_by_zone=laws["egress_law"])

    if not raw.get("routing_version"):
        raise ValueError(
            f"{_CONFIG_PATH.name} : `routing_version` manquante. Elle indexe le cache "
            f"de routage OSMnx, qui mémorise du temps réseau pur — le confondre avec "
            f"`version` ferait recalculer toutes les routes à chaque ajustement du "
            f"temps terminal (~2 h pour 930 personas).")
    return {"version": str(raw["version"]), "base_version": str(raw["version"]),
            "routing_version": str(raw["routing_version"]),
            "modes": profiles,
            # Profils CENTRAUX conservés à part : `apply_variant` met à l'échelle
            # depuis eux et jamais depuis `modes`, sinon deux bascules successives
            # multiplieraient leurs facteurs (high puis low → 0,75 au lieu de 0,5).
            # Copie de surface suffisante : `TerminalProfile` est gelé et les tables
            # de zones ne sont jamais mutées en place.
            "base_modes": dict(profiles),
            "sensitivity": raw.get("sensitivity") or {}}


def data_version() -> str:
    """Version des données d'itinéraire, à inclure dans toute clé de cache.

    Deux caches survivent aux runs et sont AVEUGLES au temps terminal si on ne
    les version pas :

    - le cache OSMnx persistant est adressé par (mode, coordonnées, créneau) : il
      resservirait des durées calculées sous l'ancien paramétrage ;
    - le cache de décisions LLM est adressé par ``TravelPlan.get_code()``, soit
      route + arrêts — insensible aux durées par construction. Il rejouerait donc
      des décisions prises sur des options qui n'existent plus telles quelles.

    Le second est le plus grave : rien ne le signalerait dans les logs. D'où une
    version explicite, à bumper avec toute modification des valeurs.
    """
    return _load()["version"]


def routing_version() -> str:
    """Version du temps de parcours RÉSEAU — clé du cache de routage OSMnx.

    Séparée de :func:`data_version` à dessein. Ce cache ne mémorise que des durées
    réseau, indépendantes du temps terminal : les indexer sur la version du temps
    terminal ferait recalculer à froid des milliers de routes à chaque ajustement du
    stationnement, pour un résultat identique. Ne bumper que si la durée réseau
    change (vitesses, pénalités, congestion).
    """
    return _load()["routing_version"]


def terminal_profile(trip_mode: str) -> Optional[TerminalProfile]:
    """Profil du mode, ou ``None`` s'il n'a pas de temps terminal.

    ``None`` est le cas de la marche (porte-à-porte par nature) et des transports
    collectifs (leurs jambes de marche d'accès sont DÉJÀ routées par OTP — en
    ajouter serait le double comptage que le critère d'acceptation 4 interdit).
    """
    return _load()["modes"].get(trip_mode)


def sensitivity_variants() -> dict[str, dict]:
    """Grille de sensibilité (ticket 013, T6) : ``{nom: {mode: {access_s, …}}}``."""
    return dict(_load()["sensitivity"])


def apply_variant(name: str) -> None:
    """Bascule les profils sur une variante de la grille de sensibilité.

    Réservé à l'analyse de sensibilité (T6) et aux tests : la production lit
    toujours les valeurs centrales du fichier. Le nom de la variante est répercuté
    dans :func:`data_version`, sans quoi les trois jeux de sensibilité
    partageraient les clés de cache de la version centrale et se mélangeraient.

    La mise à l'échelle part des profils CENTRAUX (``base_modes``), pas des profils
    courants : appelée deux fois de suite — ce que fait précisément une boucle sur la
    grille T6 — la version repartait bien de la base mais les VALEURS, elles,
    s'empilaient (``high`` puis ``low`` donnait 1,5 × 0,5 = 0,75). La mesure de
    sensibilité aurait alors porté sur des temps terminaux qu'aucune variante ne
    déclare, sous une étiquette de variante juste.
    """
    conf = _load()
    variant = (conf["sensitivity"] or {}).get(name)
    if variant is None:
        raise KeyError(f"variante de sensibilité inconnue : {name!r} "
                       f"(connues : {sorted(conf['sensitivity'])})")
    for mode, profile in list(conf["base_modes"].items()):
        override = variant.get(mode) or {}
        # Une variante applique un FACTEUR uniforme sur toutes les couronnes plutôt
        # qu'une valeur unique : sinon elle écraserait la spatialisation, et la
        # sensibilité mesurerait « spatialisé ou non » en même temps que « plus ou
        # moins de temps terminal » — deux variables pour une conclusion.
        factor = float(override.get("factor", 1.0))

        def _scaled(table: dict[str, int]) -> dict[str, int]:
            return {z: int(round(v * factor / 60.0)) * 60 for z, v in table.items()}

        def _scaled_laws(laws: dict[str, dict[int, float]]
                         ) -> dict[str, dict[int, float]]:
            """Met la LOI à l'échelle, pas seulement les constantes.

            ⚠ Sans ceci, une variante reconstruisait le profil en oubliant les champs
            de loi : les lois disparaissaient et le temps terminal retombait sur les
            constantes — nulles depuis tt3. La grille de sensibilité aurait mesuré
            « avec ou sans temps terminal » au lieu de « plus ou moins », sous une
            étiquette de variante juste. C'est exactement le silence que la
            spatialisation avait déjà failli introduire.

            Les secondes mises à l'échelle sont ramenées au multiple de 60 le plus
            proche, et les clés qui collisionnent (×0,5 envoie 1 min et 0 min sur 0)
            voient leurs masses **s'additionner** : la loi somme toujours à 1.
            """
            out: dict[str, dict[int, float]] = {}
            for zone, pmf in laws.items():
                scaled: dict[int, float] = {}
                for seconds, probability in pmf.items():
                    key = int(round(seconds * factor / 60.0)) * 60
                    scaled[key] = scaled.get(key, 0.0) + probability
                out[zone] = scaled
            return out

        conf["modes"][mode] = TerminalProfile(
            mode=mode, access_by_zone=_scaled(profile.access_by_zone),
            egress_by_zone=_scaled(profile.egress_by_zone),
            provenance=profile.provenance, spatialise=profile.spatialise,
            labels=profile.labels,
            access_law_by_zone=_scaled_laws(profile.access_law_by_zone),
            egress_law_by_zone=_scaled_laws(profile.egress_law_by_zone))
    # Repart de la version de BASE et non de la courante : deux bascules
    # successives ne doivent pas empiler les suffixes.
    conf["version"] = f"{conf['base_version']}-{name}"


def reset() -> None:
    """Vide le cache de configuration (tests, et retour aux valeurs centrales)."""
    global _cache
    _cache = None
