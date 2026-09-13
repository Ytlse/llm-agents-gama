"""Fenêtre des quotas journaliers d'un fournisseur : quand elle se referme, quand elle rouvre.

Deux pièges, tous deux mesurés le 2026-09-08 sur une expérience bloquée à 10 % :

1. **Le fuseau.** Le quota journalier du free tier Gemini se réinitialise à minuit
   *Pacifique*, pas à minuit UTC. Les compteurs internes, indexés sur le jour UTC, se
   vidaient donc 7 h trop tôt : à 08:44 heure de Paris, Redis affichait 49 requêtes sur
   500 pendant que Google refusait pour dépassement des 500 (490 comptées la veille +
   les requêtes du matin, dans la MÊME journée Pacifique).

2. **Le `retryDelay`.** Sur un dépassement journalier, Gemini renvoie un délai de
   quelques secondes (0,7 s à 57 s relevés) qui ne dit RIEN du temps jusqu'au reset.
   Le prendre au mot fait boucler : on retente 30 s plus tard, on est refusé, indéfiniment.
   Le corps porte en revanche le `quotaId` — `…PerDayPerProjectPerModel…` — qui tranche.

Le compteur interne reste un garde-fou optimiste : il ne voit que le trafic passé par ce
gateway, alors qu'une clé est aussi tapée par `scripts/synthesis/*` et `prompt_calibration`.
Seule la réponse du fournisseur fait autorité pour déclarer une fenêtre fermée.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

# `quotaId: "GenerateRequestsPerDayPerProjectPerModel-FreeTier"`, et les variantes
# rencontrées dans les messages en clair. Même sémantique que `_DAILY_QUOTA_RE` de
# prompt_calibration (dépôt autonome : la logique y est dupliquée, pas importée).
DAILY_QUOTA_RE = re.compile(r"per\s*day|requestsperday|tokensperday", re.IGNORECASE)

DEFAUT_FUSEAU_QUOTA = "UTC"


def is_daily_quota_error(corps: str | None) -> bool:
    """Le refus porte-t-il sur un quota JOURNALIER (par opposition à un débit/minute) ?

    Sur un quota journalier, le délai annoncé par le fournisseur est à jeter : c'est
    `next_quota_reset()` qui donne l'heure de réouverture.
    """
    return bool(corps) and bool(DAILY_QUOTA_RE.search(corps))


def _fuseau(nom: str | None):
    """Le fuseau demandé, UTC si l'environnement ne sait pas le résoudre (fail-safe)."""
    if not nom:
        return timezone.utc
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(nom)
    except Exception:  # noqa: BLE001 — fuseau inconnu ou base tzdata absente
        return timezone.utc


def next_quota_reset(fuseau: str | None, maintenant: datetime | None = None) -> datetime:
    """Prochain minuit dans `fuseau`, rendu en UTC. Passages heure d'été inclus."""
    tz = _fuseau(fuseau)
    local = (maintenant or datetime.now(timezone.utc)).astimezone(tz)
    lendemain = (local + timedelta(days=1)).date()
    minuit = datetime(lendemain.year, lendemain.month, lendemain.day, tzinfo=tz)
    return minuit.astimezone(timezone.utc)


def quota_day(fuseau: str | None, maintenant: datetime | None = None) -> str:
    """Jour de quota courant, « AAAAMMJJ » dans `fuseau` — la clé des compteurs du jour."""
    return (maintenant or datetime.now(timezone.utc)).astimezone(_fuseau(fuseau)).strftime("%Y%m%d")


def seconds_until_quota_reset(fuseau: str | None, maintenant: datetime | None = None) -> int:
    """Secondes avant la réouverture de la fenêtre (au moins 1)."""
    now = maintenant or datetime.now(timezone.utc)
    return max(1, int((next_quota_reset(fuseau, now) - now).total_seconds()))


__all__ = [
    "DAILY_QUOTA_RE",
    "DEFAUT_FUSEAU_QUOTA",
    "is_daily_quota_error",
    "next_quota_reset",
    "quota_day",
    "seconds_until_quota_reset",
]
