"""Les deux clients du banc : le stub, et le vrai — ticket 100, tests fonctionnels.

LE STUB sert la famille A : il rend une réponse déclarée, sans réseau et sans jeton. Il permet
de jouer une chaîne entière — injection, mémoire, trace, mesure, figure — pour zéro appel.

LE VRAI sert la famille B, et il porte la contrainte de passerelle.

⚠ **PAS DE REPLI, JAMAIS.** L'auteur a tranché le 2026-09-22 : Groq seul aujourd'hui, d'autres
modèles pour les runs longs, et **si le quota est épuisé on attend**. Une mesure obtenue sur
une passerelle qu'on n'a pas déclarée n'est pas la mesure qu'on croit lire — et ce dépôt a déjà
payé le prix d'un repli silencieux.

⚠ **La limite qui mord n'est pas le RPM.** Groq a été écarté des campagnes le 2026-09-08 pour
une limite mesurée de **1 000 jetons de SORTIE par minute**, invisible hors du corps des 429, et
la passerelle n'a pas été corrigée. Les 30 req/min et 1 000 req/jour ne seront jamais atteints
ici ; l'OTPM le sera. D'où : appels en SÉRIE, `max_tokens` serré, et un budget de jetons de
sortie que le banc surveille lui-même plutôt que de découvrir la limite dans un 429 muet.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path

# Les instances déclarées pour AUJOURD'HUI. Paramètre, pas constante : les tests longue durée
# passeront sur d'autres modèles, et le banc écrit dans chaque résultat celle qui a servi —
# sans quoi deux campagnes sur deux passerelles seraient incomparables sans qu'on le sache.
GROQ = ("groq_openai_120_key1", "groq_openai_20_key1", "groq_qwen_qwen3_8_27b_key1")

# Budget de jetons de SORTIE. À 1 000/minute mesurés, 6 000 jetons valent six minutes d'attente
# au pire. Le dépassement ARRÊTE le banc : mieux vaut un arrêt net qu'un 429 en rafale sur une
# clé partagée avec les campagnes.
BUDGET_JETONS_SORTIE = 6000

# Pause entre deux appels, en secondes. Volontairement grossière : 1 000 jetons/minute, ~200
# jetons par réponse, soit cinq réponses par minute au plus.
PAUSE_ENTRE_APPELS = 12.0


class BudgetEpuise(RuntimeError):
    """Le banc s'arrête plutôt que de déborder sur le quota des campagnes."""


class PasserelleRefusee(RuntimeError):
    """Une instance non déclarée a servi, ou allait servir."""


@dataclass
class Appel:
    """Ce qu'on garde de chaque appel. C'est la matière de `passerelle.csv`."""

    categorie: str
    agent_id: str
    etiquette: str
    instance: str = ""
    jetons_sortie: int = 0
    secondes: float = 0.0
    hors_schema: bool = False
    erreur: str = ""


@dataclass
class Journal:
    appels: list[Appel] = field(default_factory=list)

    @property
    def jetons_sortie(self) -> int:
        return sum(a.jetons_sortie for a in self.appels)

    def resume(self) -> str:
        hors = sum(1 for a in self.appels if a.hors_schema)
        erreurs = sum(1 for a in self.appels if a.erreur)
        par_instance: dict[str, int] = {}
        for a in self.appels:
            par_instance[a.instance or "?"] = par_instance.get(a.instance or "?", 0) + 1
        return (
            f"{len(self.appels)} appel(s), {self.jetons_sortie} jeton(s) de sortie, "
            f"{hors} hors schéma, {erreurs} en erreur — instances : {par_instance}"
        )

    def ecrire(self, chemin: Path) -> None:
        import csv

        chemin.parent.mkdir(parents=True, exist_ok=True)
        with chemin.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["categorie", "agent_id", "etiquette", "instance",
                        "jetons_sortie", "secondes", "hors_schema", "erreur"])
            for a in self.appels:
                w.writerow([a.categorie, a.agent_id, a.etiquette, a.instance,
                            a.jetons_sortie, round(a.secondes, 2),
                            "oui" if a.hors_schema else "", a.erreur])


# ── Le client stub ──────────────────────────────────────────────────────────────────────────
class _Rendu:
    def __init__(self, **champs):
        for k, v in champs.items():
            setattr(self, k, v)


class _Reponse:
    def __init__(self, agents, provider_used="stub"):
        self.agents = agents
        self.provider_used = provider_used


class ClientStub:
    """Rend des réponses DÉCLARÉES. Aucun réseau, aucun jeton, aucune latence.

    `reponses` associe une catégorie à une liste de dictionnaires servis dans l'ordre, puis en
    boucle sur le dernier. Une catégorie absente lève : un stub muet ferait passer un chemin
    non testé pour un chemin testé.
    """

    def __init__(self, reponses: dict[str, list[dict]]) -> None:
        self._reponses = {k: list(v) for k, v in reponses.items()}
        self.appels: list[dict] = []

    async def execute(self, payload: dict):
        categorie = str(payload.get("category") or "")
        self.appels.append(payload)
        file = self._reponses.get(categorie)
        if not file:
            raise AssertionError(
                f"le banc a appelé la catégorie « {categorie} », pour laquelle aucune réponse "
                f"n'est déclarée. Un stub muet ferait passer un chemin non testé pour testé."
            )
        rendu = file.pop(0) if len(file) > 1 else file[0]
        agents = payload.get("agents") or [{}]
        return _Reponse([_Rendu(agent_id=str(agents[0].get("agent_id", "")), **rendu)])


# ── Le vrai client, épinglé ─────────────────────────────────────────────────────────────────
class ClientEpingle:
    """Le client de la passerelle, restreint aux instances DÉCLARÉES, sans repli.

    Il compte les jetons de sortie, sérialise les appels, et refuse de continuer au-delà du
    budget. Il ne rattrape rien : une erreur remonte, journalisée, et le banc décide.
    """

    def __init__(
        self,
        instances: tuple[str, ...] = GROQ,
        *,
        base_url: str = "http://localhost:8000",
        budget_jetons: int = BUDGET_JETONS_SORTIE,
        pause: float = PAUSE_ENTRE_APPELS,
        journal: Journal | None = None,
    ) -> None:
        if not instances:
            raise PasserelleRefusee(
                "aucune instance déclarée. Le banc ne choisit pas la passerelle à votre "
                "place : déclarez-la, elle est écrite dans chaque résultat."
            )
        from llm_gateway.sdk.client import LLMGatewayClient

        self.instances = tuple(instances)
        self._budget = int(budget_jetons)
        self._pause = float(pause)
        self.journal = journal or Journal()
        self._dernier_appel = 0.0
        self._client = LLMGatewayClient(
            base_url=base_url, instances_admises=list(self.instances)
        )

    async def execute(self, payload: dict, *, etiquette: str = ""):
        """Un appel, compté. Lève `BudgetEpuise` plutôt que de déborder."""
        if self.journal.jetons_sortie >= self._budget:
            raise BudgetEpuise(
                f"budget atteint : {self.journal.jetons_sortie} jetons de sortie sur "
                f"{self._budget}. Le banc s'arrête — il ne déborde pas sur le quota des "
                f"campagnes. Relancez-le avec un budget déclaré plus haut si c'est voulu."
            )
        # Les instances voyagent DANS la charge utile ET dans le client : la passerelle lit
        # l'une ou l'autre selon le chemin, et laisser le choix ouvert d'un côté suffirait à
        # faire servir une instance non déclarée.
        payload = dict(payload)
        payload["instances_admises"] = list(self.instances)

        attente = self._pause - (time.monotonic() - self._dernier_appel)
        if self._dernier_appel and attente > 0:
            await asyncio.sleep(attente)

        agents = payload.get("agents") or [{}]
        trace = Appel(
            categorie=str(payload.get("category") or ""),
            agent_id=str(agents[0].get("agent_id", "")),
            etiquette=etiquette,
        )
        debut = time.monotonic()
        try:
            reponse = await self._client.execute(payload)
        except Exception as err:  # noqa: BLE001 — journalisé puis relevé, jamais avalé
            trace.erreur = f"{type(err).__name__}: {err}"[:200]
            trace.secondes = time.monotonic() - debut
            self.journal.appels.append(trace)
            self._dernier_appel = time.monotonic()
            raise
        trace.secondes = time.monotonic() - debut
        trace.instance = str(getattr(reponse, "provider_used", "") or "")
        # ⚠ Une réponse VIDE n'est pas une réponse hors grille, et les confondre a coûté une
        # demi-heure de diagnostic le 2026-09-22 : le banc disait « hors grille » là où la
        # passerelle n'avait rien rendu du tout. Sur Groq, c'est la signature de la limite de
        # jetons de SORTIE par minute — invisible hors du corps des 429, et la passerelle ne
        # la remonte pas (mesuré le 2026-09-08, jamais corrigé). Le statut et l'erreur sont
        # donc journalisés, même quand la passerelle dit « succès ».
        statut = str(getattr(reponse, "status", "") or "")
        erreur = str(getattr(reponse, "error", "") or "")
        if not getattr(reponse, "agents", None):
            trace.erreur = (erreur or f"réponse VIDE (statut {statut})")[:200]
        trace.jetons_sortie = int(getattr(reponse, "tokens_out", 0) or 0) or _estimer(reponse)
        self.journal.appels.append(trace)
        self._dernier_appel = time.monotonic()

        # ⚠ La garde qui compte : si une instance NON déclarée a servi, on le dit et on
        # s'arrête. Le résultat serait inutilisable, et pire : on ne le saurait pas.
        if trace.instance and trace.instance not in self.instances:
            raise PasserelleRefusee(
                f"l'instance « {trace.instance} » a servi alors que le banc n'admet que "
                f"{list(self.instances)}. Le résultat est écarté : une mesure obtenue sur une "
                f"passerelle non déclarée n'est pas la mesure qu'on croit lire."
            )
        return reponse


def _estimer(reponse) -> int:
    """Faute de compteur rendu par la passerelle, une estimation grossière et DITE comme telle.

    Quatre caractères par jeton : c'est faux au détail près et suffisant pour une garde de
    budget. Ce qui compte est de ne pas laisser le compteur à zéro — un budget qui ne compte
    rien n'arrête rien.
    """
    try:
        agents = getattr(reponse, "agents", None) or []
        return max(1, len(str(agents)) // 4)
    except Exception:  # noqa: BLE001
        return 1
