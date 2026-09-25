"""
load_balancer/router.py — Routeur intelligent multi-fournisseur.

Implémente :
  - Weighted Round-Robin   : répartition proportionnelle aux quotas RPM (SWRR NGINX,
                             séquence pure construite par core.selection)
  - Réservation atomique   : déléguée au port RateLimiter (script Lua Redis) — aucun
                             worker concurrent ne peut dépasser le rpm_limit configuré
  - Circuit Breaker        : exclusion temporaire (cooldown) sur erreurs 5xx / 429
  - Désactivation temporaire : exclusion automatique après N erreurs consécutives,
                               réactivation après `disable_timeout` secondes (défaut 180s)

Le constructeur ne touche PAS à Redis : la remise à zéro des fenêtres RPM est un
geste explicite du lifespan de l'API (cf. api/app.py), plus jamais un effet de
bord d'import.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable

from llm_gateway.config import ProviderConfig
from llm_gateway.core.selection import build_swrr_sequence
from llm_gateway.ports.rate_limiter import RateLimiter
from llm_gateway.telemetry.logger import get_logger

logger = get_logger(__name__)


class RestrictionInstances(ValueError):
    """La liste d'instances admises ne désigne rien d'exploitable — ticket 084.

    ⚠ **Une restriction fausse n'est jamais « aucune restriction ».** C'est la règle qui donne
    sa valeur au lot : une faute de frappe qui vaudrait « sers-toi partout » rendrait douteuse
    toute mesure prise sous restriction, sans qu'aucune ligne ne le signale. Elle est donc levée
    à la sélection, avant qu'un seul appel ne soit payé.
    """


class LoadBalancer:
    """
    Sélectionne le fournisseur optimal pour chaque requête et réserve atomiquement
    un slot RPM (via le RateLimiter injecté) avant de retourner son nom.
    """

    def __init__(self, providers: dict[str, ProviderConfig], limiter: RateLimiter,
                 policy: str = "swrr") -> None:
        self._providers = providers
        self._limiter = limiter
        self._policy = policy
        self._lock = threading.Lock()
        self._cursor: int = 0
        self._sequence: list[str] = self._build_sequence()
        if policy == "cascade":
            logger.info(f"Routage en CASCADE : ordre de priorité = {self._cascade()}")

    def _admises(self, admises: Iterable[str] | None) -> frozenset[str] | None:
        """Ensemble des instances admises, VALIDÉ, ou `None` quand rien n'est restreint.

        Ticket 084. Trois retours possibles et un seul silence : `None` (pas de restriction)
        et un ensemble non vide. Tout le reste lève — liste ne désignant aucune instance
        connue, ou mélangeant connues et inconnues. Une liste à moitié fausse est une erreur
        de configuration, pas une intention à deviner.
        """
        if admises is None:
            return None
        demandees = frozenset(str(nom).strip() for nom in admises if str(nom).strip())
        if not demandees:
            # Liste vide == absence de restriction. C'est le cas d'un réglage déclaré mais non
            # renseigné, et il doit se comporter exactement comme avant le ticket.
            return None
        inconnues = demandees - set(self._providers)
        if inconnues:
            raise RestrictionInstances(
                f"instances admises inconnues : {sorted(inconnues)} — connues : "
                f"{sorted(self._providers)}. Une liste à moitié fausse n'est pas une "
                f"restriction partielle, c'est une erreur de configuration."
            )
        return demandees

    def _cascade(self) -> list[str]:
        """L'ordre de priorité en mode cascade : celui de la configuration, doublons ôtés.

        On épuise le premier fournisseur avant de toucher au suivant, au lieu d'étaler la
        charge : deux clés sur un même modèle se consomment ainsi l'une après l'autre.
        """
        vus: list[str] = []
        for nom in self._sequence:
            if nom not in vus:
                vus.append(nom)
        return vus

    # ------------------------------------------------------------------
    # Construction de la séquence pondérée
    # ------------------------------------------------------------------

    def _build_sequence(self) -> list[str]:
        if not self._providers:
            logger.error("Aucun provider disponible — séquence SWRR vide.")
            return []
        # weight 0 = provider défini mais HORS ROTATION (build_swrr_sequence
        # garantit ≥ 1 slot à chaque entrée, il faut donc filtrer ici). Reste
        # utilisable via un `llm.provider` forcé dans la config d'expérience.
        in_rotation = {name: cfg.weight for name, cfg in self._providers.items()
                       if cfg.weight > 0}
        excluded = sorted(set(self._providers) - set(in_rotation))
        if excluded:
            logger.info(f"Providers hors rotation (weight 0) : {excluded}")
        if not in_rotation:
            logger.error("Tous les providers sont à weight 0 — séquence SWRR vide.")
            return []
        sequence = build_swrr_sequence(in_rotation)
        logger.debug(f"Séquence WRR construite | sequence={sequence}")
        return sequence

    def rebuild_sequence(self) -> None:
        with self._lock:
            self._sequence = self._build_sequence()
            self._cursor = 0

    # ------------------------------------------------------------------
    # Sélection du fournisseur
    # ------------------------------------------------------------------

    def select_provider(
        self,
        force: str | None = None,
        min_tpm: int | None = None,
        min_output: int | None = None,
        admises: Iterable[str] | None = None,
    ) -> str:
        """
        Retourne le nom du fournisseur à utiliser et réserve atomiquement un slot RPM.

        Args:
            force:      Si fourni, bypasse la rotation et utilise ce fournisseur.
            min_tpm:    Si fourni, exclut les providers dont tpm_limit < min_tpm
                        (les providers sans limite TPM, tpm_limit=None, restent éligibles).
            min_output: Si fourni, exclut les providers dont le plafond de complétion
                        max_output_tokens < min_output (budget de sortie d'une tâche).
                        Les providers sans limite connue (None) restent éligibles.
            admises:    Ticket 084 — LISTE des instances admises à servir cette requête. La
                        restriction est honorée ICI, avant toute réservation et donc avant
                        qu'un appel ne soit payé. C'est ce qui la distingue du filtre client
                        `allowed_providers`, qui rejette une réponse déjà facturée. `None` ou
                        liste vide : aucune restriction, comportement d'avant le ticket.

        Raises:
            RuntimeError: Si tous les fournisseurs admis sont saturés ou indisponibles.
            RestrictionInstances: Si `admises` ne désigne aucune instance connue, ou en mêle
                        des inconnues — une liste fausse n'est jamais « aucune restriction ».
        """
        _admises = self._admises(admises)

        if force:
            # Deux contraintes contradictoires sont une erreur de configuration, pas une
            # priorité à arbitrer en silence : servir l'épinglé reviendrait à ignorer la
            # restriction, et l'inverse à ignorer l'épinglage. On refuse, en le disant.
            if _admises is not None and force not in _admises:
                raise RestrictionInstances(
                    f"fournisseur forcé '{force}' hors des instances admises "
                    f"{sorted(_admises)} — contraintes contradictoires, aucune n'est "
                    f"arbitrée en silence."
                )
            if self._try_reserve(force, min_tpm=min_tpm, min_output=min_output):
                return force
            raise RuntimeError(
                f"Fournisseur forcé '{force}' indisponible (quota atteint ou désactivé)."
            )

        if self._policy == "cascade":
            # Cascade : toujours repartir du premier. Il n'est dépassé que s'il REFUSE
            # (quota du jour, cooldown, débit par minute saturé), et le refus est journalisé
            # pour qu'un basculement se lise dans les logs.
            ordre = self._cascade()
            if _admises is not None:
                # L'ORDRE de la cascade est conservé, seul l'ensemble se réduit : la priorité
                # déclarée dans la configuration reste la priorité sous restriction.
                ordre = [nom for nom in ordre if nom in _admises]
            for rang, candidate in enumerate(ordre):
                if self._try_reserve(candidate, min_tpm=min_tpm, min_output=min_output):
                    if rang:
                        logger.info(
                            f"Cascade : bascule sur '{candidate}' (rang {rang + 1}/{len(ordre)}) — "
                            f"les précédents ont refusé : {', '.join(ordre[:rang])}"
                        )
                    return candidate
            raise RuntimeError(
                "Tous les fournisseurs LLM sont saturés ou ont atteint leur limite de concurrence. "
                f"Cascade épuisée dans l'ordre : {', '.join(ordre)}."
                + (
                    f" Restriction en vigueur : {sorted(_admises)} — aucun recours hors de "
                    f"cet ensemble n'est tenté."
                    if _admises is not None
                    else ""
                )
            )

        # Rotation normale — le lock ne protège que la lecture/écriture du curseur.
        # _try_reserve() fait ses appels Redis HORS du lock.
        seq_len = len(self._sequence)
        for _ in range(seq_len):
            with self._lock:
                candidate = self._sequence[self._cursor % seq_len]
                self._cursor += 1

            # Le curseur avance même sur une instance écartée : la séquence pondérée reste
            # parcourue à l'identique, et deux requêtes aux restrictions différentes ne se
            # décalent pas l'une l'autre.
            if _admises is not None and candidate not in _admises:
                continue

            if self._try_reserve(candidate, min_tpm=min_tpm, min_output=min_output):
                return candidate

        raise RuntimeError(
            "Tous les fournisseurs LLM sont saturés ou ont atteint leur limite de concurrence. "
            "Réessayez dans quelques secondes."
            + (
                f" Restriction en vigueur : {sorted(_admises)} — aucun recours hors de cet "
                f"ensemble n'est tenté."
                if _admises is not None
                else ""
            )
        )

    def _try_reserve(
        self,
        provider: str,
        min_tpm: int | None = None,
        min_output: int | None = None,
    ) -> bool:
        """
        Applique les contraintes de routage (provider connu, min_tpm, min_output)
        puis délègue la réservation atomique (désactivation, cooldown, concurrence,
        quota + lissage) au RateLimiter.
        """
        cfg = self._providers.get(provider)
        if cfg is None:
            logger.warning(f"Provider inconnu dans la config | provider={provider}")
            return False

        if min_tpm is not None and cfg.tpm_limit is not None and cfg.tpm_limit < min_tpm:
            return False

        if (
            min_output is not None
            and cfg.max_output_tokens is not None
            and cfg.max_output_tokens < min_output
        ):
            return False

        return self._limiter.try_reserve(provider)

    def get_status(self) -> dict[str, dict]:
        """Snapshot des compteurs RPM pour monitoring / debug (/health)."""
        status = {}
        for name, cfg in self._providers.items():
            current = self._limiter.current_rpm(name)
            quota_exhausted = self._limiter.is_quota_exhausted(name)
            available = (
                not self._limiter.is_disabled(name)
                and not self._limiter.is_in_cooldown(name)
                and not quota_exhausted
                and current < cfg.rpm_limit
                and self._limiter.active_workers(name) < cfg.concurrency_limit
            )
            status[name] = {
                "current_rpm":     current,
                "disabled":        self._limiter.is_disabled(name),
                "rpm_limit":       cfg.rpm_limit,
                "active_tasks":    self._limiter.active_workers(name),
                "usage_pct":       round(current / cfg.rpm_limit * 100, 1) if cfg.rpm_limit else 0,
                "cooldown":        self._limiter.is_in_cooldown(name),
                # Ticket 105 — chiffres INDICATIFS : ils ne voient que le trafic de cette
                # passerelle et ne ferment jamais une clé (seul le 429 du fournisseur le fait).
                # Les noms de champ restent stables : le tableau de bord les lit.
                "daily_requests":  self._limiter.daily_requests_local_seulement(name),
                "rpd_limit":       cfg.rpd_limit,
                "daily_tokens":    self._limiter.daily_tokens_local_seulement(name),
                "tpd_limit":       cfg.tpd_limit,
                "quota_exhausted": quota_exhausted,
                "available":       available,
                # Publiés pour que l'estimation de coût d'une expérience convertisse des
                # DÉPLACEMENTS en REQUÊTES sans recopier la formule : le plafond de lot est
                # calculé au démarrage depuis l'environnement de CE conteneur, et la valeur
                # relue ailleurs dans `providers.yaml` peut en diverger.
                "batch_max_agents":          cfg.batch_max_agents,
                "tpm_estimate_per_request":  cfg.tpm_estimate_per_request,
            }
        return status
