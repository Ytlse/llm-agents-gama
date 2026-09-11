"""Ressources des décideurs distants : instances, quotas, disponibilité (ticket 035, spec 05).

Tout vient de la passerelle et de sa configuration (`config/llm_gateway/providers.yaml`, `/health`),
jamais d'une constante écrite ici (Q1). Une **instance** est une clé + un quota ; le décideur d'une
expérience est un **modèle** + des paramètres (Q2) : les instances admises sont celles qui servent
exactement ce modèle.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from loguru import logger

_SOUS_CHEMIN_PROVIDERS = ("config", "llm_gateway", "providers.yaml")


def candidats_providers() -> list[Path]:
    """Emplacements sondés pour `providers.yaml`, dans l'ordre de priorité.

    Depuis le ticket 037 (itération 2) le fichier vit HORS du paquet : à la racine du dépôt
    sur l'hôte, monté sous `/app/config/llm_gateway` dans les conteneurs. On remonte les
    ancêtres du module au lieu d'indexer un `parents[N]` fixe : ce module vit sous
    `llm-agents/experiences/` sur l'hôte (racine du dépôt à deux crans) mais sous
    `/app/experiences/` dans le conteneur (`./llm-agents` est monté sur `/app`, donc la
    racine est à UN cran et `parents[2]` vaut `/`).
    """
    candidats: list[Path] = []
    depuis_env = os.environ.get("LLM_GATEWAY_PROVIDERS_FILE")
    if depuis_env:
        candidats.append(Path(depuis_env))
    for ancetre in Path(__file__).resolve().parents[:4]:
        candidats.append(ancetre.joinpath(*_SOUS_CHEMIN_PROVIDERS))
    candidats.append(
        Path("/app").joinpath(*_SOUS_CHEMIN_PROVIDERS)
    )  # montage du conteneur
    vus: set[str] = set()
    return [c for c in candidats if not (str(c) in vus or vus.add(str(c)))]


def chemin_providers() -> Path:
    """Le premier candidat lisible ; à défaut le dernier, pour que le message d'erreur cite un chemin."""
    candidats = candidats_providers()
    for c in candidats:
        if c.is_file():
            return c
    return candidats[-1]


def charger_providers(chemin: Path | None = None) -> dict[str, dict]:
    """{instance: configuration} depuis providers.yaml (clé racine `providers:` ou plat)."""
    p = Path(chemin) if chemin else chemin_providers()
    if not p.is_file():
        # Configuration de déploiement absente : tout décideur `passerelle` sera refusé faute
        # d'instance. Muet, ce cas envoie vérifier un fichier qu'on n'a pas lu (panne 2026-09-07).
        logger.error(
            f"[ALARME] aucun fichier de fournisseurs lisible — {diagnostic_providers(p)}"
        )
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    providers = data.get("providers", data) if isinstance(data, dict) else {}
    charges = {
        str(k): dict(v or {}) for k, v in providers.items() if isinstance(v, dict)
    }
    logger.debug(f"[ressources] {len(charges)} instance(s) lue(s) dans {p}")
    return charges


def diagnostic_providers(
    chemin: Path | None = None, providers: dict | None = None
) -> str:
    """Une ligne pour les messages d'erreur : QUEL fichier a été lu et COMBIEN d'instances y sont.

    Un refus qui renvoie vers « providers.yaml » sans dire lequel a été lu coûte du temps :
    c'est exactement ce qui s'est produit le 2026-09-07 avec un conteneur non recréé.
    """
    p = Path(chemin) if chemin else chemin_providers()
    if p.is_file():
        n = len(providers) if providers is not None else len(charger_providers(p))
        return f"{n} instance(s) lue(s) dans {p}"
    env = os.environ.get("LLM_GATEWAY_PROVIDERS_FILE") or "non définie"
    sondes = ", ".join(str(c) for c in candidats_providers())
    return (
        f"aucun fichier lisible (LLM_GATEWAY_PROVIDERS_FILE : {env}) ; "
        f"{len(candidats_providers())} emplacements sondés : {sondes}"
    )


# Port du serveur local LM Studio, et hôtes qui le désignent depuis un conteneur ou depuis la
# machine elle-même. Même règle que `scripts/dashboard/lmstudio.est_instance_lmstudio`, réécrite
# ici parce que ce module tourne dans le conteneur `controller`, sans le paquet du tableau de
# bord : `test_035_15_portee.py` vérifie que les deux verdicts coïncident sur le providers.yaml
# réel, pour que la duplication ne puisse pas diverger en silence.
PORT_LMSTUDIO = 1234
_HOTES_LOCAUX = (
    "host.docker.internal",
    "gateway.docker.internal",
    "localhost",
    "127.0.0.1",
)
PORTEES = ("local", "distant")


def est_instance_locale(cfg: dict) -> bool:
    """Cette instance est-elle servie par LM Studio sur cette machine ?"""
    from urllib.parse import urlsplit

    if not isinstance(cfg, dict):
        return False
    u = urlsplit(str(cfg.get("base_url") or ""))
    if u.hostname not in _HOTES_LOCAUX:
        return False
    return (u.port or (443 if u.scheme == "https" else 80)) == PORT_LMSTUDIO


def portee_instance(cfg: dict) -> str:
    """`local` (LM Studio sur cette machine) ou `distant` (une API à quota)."""
    return "local" if est_instance_locale(cfg) else "distant"


def instances_pour_modele(
    modele: str, providers: dict[str, dict], portee: str | None = None
) -> list[str]:
    """Instances qui servent EXACTEMENT ce modèle (Q2) — changer de clé n'est pas une substitution.

    `portee` restreint au bord demandé. Un même identifiant de modèle peut être servi des deux
    côtés — `qwen/qwen3.8-27b` est chez Groq ET dans LM Studio (deux quantifications) — et sans
    ce filtre l'expérience commencerait sur l'un pour finir sur l'autre à l'épuisement du quota,
    sous un seul nom. `None` (définitions écrites avant ce champ) rend les deux bords : le
    comportement d'archive ne change pas, c'est `refuser_si_impossible` qui exige la portée
    quand elle lève une ambiguïté réelle.
    """
    noms = sorted(
        nom
        for nom, cfg in providers.items()
        if str(cfg.get("default_model", "")) == modele
    )
    if portee is None:
        return noms
    return [n for n in noms if portee_instance(providers.get(n, {})) == portee]


def portees_pour_modele(modele: str, providers: dict[str, dict]) -> dict[str, list[str]]:
    """{portée: instances} pour ce modèle, portées vides omises — la base du diagnostic d'ambiguïté."""
    out: dict[str, list[str]] = {}
    for nom in instances_pour_modele(modele, providers):
        out.setdefault(portee_instance(providers.get(nom, {})), []).append(nom)
    return {p: sorted(v) for p, v in sorted(out.items())}


def url_passerelle() -> str:
    return os.getenv("LLM_API_URL", "http://localhost:8000")


def lire_etat_passerelle(
    base_url: str | None = None, timeout: float = 5.0
) -> dict | None:
    """GET /health → {instance: {daily_requests, rpd_limit, quota_exhausted, available, current_rpm…}} ; None si injoignable."""
    import httpx

    url = (base_url or url_passerelle()).rstrip("/") + "/health"
    try:
        r = httpx.get(url, timeout=timeout)
        r.raise_for_status()
        return (r.json() or {}).get("providers") or {}
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"[ressources] passerelle injoignable ({url}) : {type(e).__name__}: {e}"
        )
        return None


# Fuseau par défaut du reset journalier quand la config ne le dit pas. Gemini free tier
# compte sa journée en heure du Pacifique : viser minuit UTC réveillait une exécution à
# 02:00 heure de Paris pour une fenêtre qui ne rouvrait qu'à 09:00 (incident 2026-09-08).
FUSEAU_QUOTA_DEFAUT = "America/Los_Angeles"


def prochaine_fenetre_quota(
    maintenant: datetime | None = None, fuseau: str | None = None
) -> str:
    """Fin de la fenêtre journalière des quotas `rpd` : prochain minuit dans `fuseau`, en UTC.

    Ce n'est qu'un REPLI : quand le fournisseur annonce lui-même son heure de réouverture
    (429 « per day »), c'est elle qui vaut — cf. `runner._attendre_fenetre_quota`.
    """
    now = maintenant or datetime.now(timezone.utc)
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(fuseau or FUSEAU_QUOTA_DEFAUT)
    except Exception:  # noqa: BLE001 — fuseau inconnu / tzdata absente
        tz = timezone.utc
    local = now.astimezone(tz)
    lendemain = (local + timedelta(days=1)).date()
    minuit = datetime(lendemain.year, lendemain.month, lendemain.day, tzinfo=tz)
    return minuit.astimezone(timezone.utc).isoformat(timespec="seconds")


def hors_service(e: dict | None) -> bool:
    """L'instance est-elle mise hors service par la passerelle — désactivée après des erreurs
    consécutives (402 crédits, 5xx…) ou en cooldown ?

    `/health` publie `disabled` et `cooldown`, qui disent exactement cela. `available`, lui,
    répond à une autre question — « peut-elle prendre une requête MAINTENANT ? » — et vaut
    aussi faux quand l'instance est simplement OCCUPÉE (`active_tasks` ≥ `concurrency_limit`).
    Le 2026-09-08, lu comme « hors service », il a fait déclarer épuisée jusqu'au lendemain une
    expérience sur un modèle local à un appel à la fois, deux décisions après sa reprise.
    Sans ces deux champs (passerelle ancienne), `available` reste le seul signal et fait foi.
    """
    e = e or {}
    if "disabled" in e or "cooldown" in e:
        return bool(e.get("disabled")) or bool(e.get("cooldown"))
    return not e.get("available", True)


def occupee(e: dict | None) -> bool:
    """Servable mais saturée : tous ses appels simultanés sont pris. Une information, jamais un refus."""
    e = e or {}
    return (not e.get("available", True)) and not hors_service(e) and not bool(e.get("quota_exhausted"))


class MoniteurRessources:
    """Vue des instances admises d'un décideur : marge, disponibilité, épuisement (Q1, Q4, Q11)."""

    def __init__(
        self,
        instances: list[str],
        providers: dict[str, dict],
        base_url: str | None = None,
        lecteur=lire_etat_passerelle,
    ):
        self.instances = list(instances)
        self.providers = providers
        self.base_url = base_url or url_passerelle()
        self._lecteur = lecteur
        self.etat: dict[str, dict] = {}
        self.joignable: bool | None = None
        self.compteurs = {"429": 0, "402": 0, "substitution_refusee": 0}
        # Âge de l'instantané, en horloge monotone : `rafraichir_si_perime` s'en sert pour
        # ne pas marteler `/health`. None = jamais lu, donc périmé d'office.
        self.maj_monotone: float | None = None

    def rafraichir(self) -> None:
        etat = self._lecteur(self.base_url)
        self.joignable = etat is not None
        if etat is not None:
            self.etat = {i: etat.get(i, {}) for i in self.instances}
            # L'âge ne repart QUE sur une lecture réussie : une passerelle injoignable laisse
            # l'instantané précédent en place (fail-safe) et le laisse périmé, donc réessayé.
            self.maj_monotone = time.monotonic()

    def perime(self, age_max_s: float) -> bool:
        """L'instantané a-t-il dépassé `age_max_s` ? Jamais lu ⇒ périmé."""
        if self.maj_monotone is None:
            return True
        return (time.monotonic() - self.maj_monotone) >= age_max_s

    def rafraichir_si_perime(self, age_max_s: float) -> bool:
        """Relit `/health` seulement si l'instantané est trop vieux. Rend True si elle a lu.

        Sans cela, `etat` restait figé sur la lecture du DÉMARRAGE pendant tout le run :
        une clé qui s'épuisait en cours de route restait « disponible » aux yeux de
        `instances_disponibles`, donc `DecideurPasserelle._prochaine_instance` continuait de
        l'épingler et la clé suivante — 500 requêtes intactes — n'était jamais entamée
        (incident du 2026-09-08 : run arrêté à 70,5 % avec un seau plein en réserve).
        """
        if not self.perime(age_max_s):
            return False
        self.rafraichir()
        return True

    def marge(self, instance: str) -> int | None:
        """Requêtes restantes dans la fenêtre du jour — None si l'instance n'a pas de limite journalière."""
        cfg = self.providers.get(instance, {})
        limite = cfg.get("rpd_limit")
        if limite is None:
            return None
        consomme = int((self.etat.get(instance) or {}).get("daily_requests") or 0)
        return max(0, int(limite) - consomme)

    def disponible(self, instance: str, besoin: int = 1) -> bool:
        e = self.etat.get(instance) or {}
        if hors_service(e):
            # La passerelle a mis l'instance hors service (crédits épuisés, erreurs
            # consécutives, cooldown). Le go/no-go ne le lisait pas jusqu'au 2026-09-07
            # (`cerebras_gpt-oss-120b` en 402 avec `quota_exhausted: false` : admise, puis
            # neuf requêtes brûlées), puis il a lu `available` jusqu'au 2026-09-08 — qui
            # vaut aussi faux quand l'instance est seulement OCCUPÉE : cf. `hors_service`.
            return False
        if e.get("quota_exhausted"):
            return False
        marge = self.marge(instance)
        if marge is not None and marge < besoin:
            return False  # Q11 : anticipé, avant le premier 429
        return True

    def instances_disponibles(self, besoin: int = 1) -> list[str]:
        return [i for i in self.instances if self.disponible(i, besoin)]

    def epuise(self, besoin: int = 1) -> bool:
        return not self.instances_disponibles(besoin)

    def raison_epuisement(self) -> str:
        parts = []
        for i in self.instances:
            cfg = self.providers.get(i, {})
            e = self.etat.get(i) or {}
            parts.append(
                f"{i} : {e.get('daily_requests', '?')}/{cfg.get('rpd_limit', '∞')} requêtes/jour"
                + (" (épuisée)" if e.get("quota_exhausted") else "")
                + (" (désactivée côté passerelle : erreurs consécutives ou cooldown)" if hors_service(e) else "")
            )
        return " ; ".join(parts) or "aucune instance"

    def tableau(self) -> list[dict]:
        """Ce que voit l'utilisateur pendant l'exécution (Q1)."""
        lignes = []
        for i in self.instances:
            cfg = self.providers.get(i, {})
            e = self.etat.get(i) or {}
            lignes.append(
                {
                    "instance": i,
                    "modele": cfg.get("default_model"),
                    "requetes_jour": e.get("daily_requests"),
                    "limite_jour": cfg.get("rpd_limit"),
                    "marge": self.marge(i),
                    "jetons_jour": e.get("daily_tokens"),
                    "limite_jetons_jour": cfg.get("tpd_limit"),
                    "rpm_observe": e.get("current_rpm"),
                    "rpm_limite": cfg.get("rpm_limit"),
                    "epuisee": bool(e.get("quota_exhausted")),
                    "disponible": not hors_service(e),
                    "occupee": occupee(e),
                }
            )
        return lignes


__all__ = [
    "MoniteurRessources",
    "charger_providers",
    "chemin_providers",
    "est_instance_locale",
    "instances_pour_modele",
    "portee_instance",
    "portees_pour_modele",
    "lire_etat_passerelle",
    "FUSEAU_QUOTA_DEFAUT",
    "prochaine_fenetre_quota",
    "url_passerelle",
]
