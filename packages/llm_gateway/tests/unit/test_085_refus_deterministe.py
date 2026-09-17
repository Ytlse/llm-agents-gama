"""Ticket 085, lot A — un refus déterministe se dit une fois, tout de suite, et ne se rejoue pas.

Contrat : `specs/ticket_085/tests.md`, section A. Les identifiants (A1, A3…) y renvoient.

La question à laquelle ces tests répondent : **une contradiction de configuration coûte-t-elle une
seconde et un message juste, ou deux minutes et un message faux ?**

Avant ce lot, `RestrictionInstances` — un `ValueError` — traversait la boucle d'attente, qui
n'intercepte que `RuntimeError`. Elle sortait de la tâche AVANT `rt.queue.pop` : le lot restait en
file, chaque dispatch suivant le reprenait et échouait à l'identique, le client expirait à 120 s sur
un « Timeout expiré » qui ne disait rien, et le disjoncteur s'ouvrait au dixième échec. Trois heures
le 2026-09-16, pour une ligne de YAML.

Aucun appel Celery/Redis/LLM : le runtime est doublé et la tâche appelée directement.
"""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from llm_gateway.balancer.router import RestrictionInstances
from llm_gateway.core.models import TaskStatus
from llm_gateway.worker import task_worker
from llm_gateway.worker.task_worker import _vider_file, process_batch_task


class _Queue:
    """File de lot dont `pop` est borné — comme la vraie, qui compte des AGENTS, pas des tâches."""

    def __init__(self, taches, par_pop=2):
        self.taches = list(taches)
        self.par_pop = par_pop
        self.scheduled_cleared: list[str] = []
        self.requeues: list[tuple] = []
        self.pops = 0

    def clear_scheduled(self, batch_key):
        self.scheduled_cleared.append(batch_key)

    def pop(self, batch_key, max_agents):
        self.pops += 1
        n = min(self.par_pop, max_agents, len(self.taches))
        sortis, self.taches = self.taches[:n], self.taches[n:]
        return sortis

    def requeue(self, batch_key, tasks):
        self.requeues.append((batch_key, list(tasks)))
        self.taches.extend(tasks)

    def size(self, batch_key):
        return len(self.taches)


class _Store:
    def __init__(self):
        self.publiees = []

    def save_sync(self, task):
        pass

    def publish_done_sync(self, task):
        self.publiees.append(task)


class _Metrics:
    def __init__(self):
        self.compteurs: dict[str, int] = {}

    def incr(self, cle, *_a, **_k):
        self.compteurs[cle] = self.compteurs.get(cle, 0) + 1


class _Limiter:
    def __init__(self):
        self.actifs: list[str] = []
        self.rendus: list[str] = []

    def incr_active(self, p):
        self.actifs.append(p)

    def decr_active(self, p):
        pass

    def release_slot(self, p):
        self.rendus.append(p)


class _Balancer:
    """Lève ce qu'on lui demande à la sélection, et compte les appels."""

    def __init__(self, leve):
        self.leve = leve
        self.appels = 0

    def select_provider(self, **_k):
        self.appels += 1
        raise self.leve

    def get_status(self):
        return {}


def _taches(n=5):
    return [
        SimpleNamespace(task_id=f"t{i}", status=TaskStatus.PENDING, error=None,
                        error_kind=None, resume_at=None, updated_at=datetime.now(UTC))
        for i in range(n)
    ]


def _runtime(leve, taches, par_pop=2):
    return SimpleNamespace(
        settings=SimpleNamespace(
            providers={},
            resilience=SimpleNamespace(
                provider_wait_seconds=0.0,
                saturation_poll_seconds=0.0,
                saturation_retries=0,
                saturation_retry_seconds=1.0,
                abandon_when_busy=True,
            ),
        ),
        balancer=_Balancer(leve),
        queue=_Queue(taches, par_pop=par_pop),
        store=_Store(),
        metrics=_Metrics(),
        limiter=_Limiter(),
    )


@pytest.fixture
def lot(monkeypatch):
    """Un lot de 5 tâches dont la sélection est refusée par contradiction de configuration."""
    exc = RestrictionInstances(
        "fournisseur forcé 'google_gemini35_key1' hors des instances admises "
        "['google_gemini31_key1', 'google_gemini31_key2'] — contraintes contradictoires, "
        "aucune n'est arbitrée en silence."
    )
    taches = _taches(5)
    rt = _runtime(exc, taches, par_pop=2)
    monkeypatch.setattr(task_worker, "get_worker_runtime", lambda: rt)
    process_batch_task.run(
        "bk",
        force_provider="google_gemini35_key1",
        min_tpm_required=None,
        min_output_required=None,
        instances_admises=["google_gemini31_key1", "google_gemini31_key2"],
    )
    return rt, taches


# ── A1. Le lot sort de la file, et ne se réarme pas ──────────────────────────────────────


def test_A1_les_taches_sortent_de_la_file_et_echouent(lot):
    rt, taches = lot
    assert rt.queue.taches == [], "la file du lot est VIDE : rien ne peut se réarmer au dispatch suivant"
    assert all(t.status == TaskStatus.FAILED for t in taches)
    assert len(rt.store.publiees) == 5, "chaque tâche est publiée : le client reçoit son motif"


def test_A1_aucun_rejeu_nest_planifie(lot):
    rt, _ = lot
    assert rt.queue.requeues == [], "un rejeu ne pourrait que reproduire la contradiction"
    assert rt.balancer.appels == 1, "une seule sélection : pas de boucle d'attente sur un refus déterministe"


def test_A1_la_file_est_drainee_meme_au_dela_dun_seul_pop():
    """`pop` est borné par un nombre d'AGENTS : un seul appel laisserait la queue de lot derrière."""
    rt = _runtime(RestrictionInstances("boum"), _taches(7), par_pop=2)
    assert len(_vider_file(rt, "bk")) == 7
    assert rt.queue.taches == []


def test_A1_aucun_slot_nest_restitue(lot):
    rt, _ = lot
    assert rt.limiter.rendus == [], "la sélection a échoué AVANT toute réservation : rien à rendre"


# ── A2. Le motif nomme les DEUX contraintes ──────────────────────────────────────────────


def test_A2_le_motif_nomme_la_liste_admise_et_le_fournisseur_epingle(lot):
    _, taches = lot
    motif = taches[0].error
    assert "google_gemini31_key1" in motif and "google_gemini31_key2" in motif, motif
    assert "google_gemini35_key1" in motif, motif
    assert "admises" in motif and "épinglé" in motif, (
        "les deux contraintes doivent être LISIBLES comme telles, pas seulement présentes"
    )


def test_A2_le_motif_dit_quil_ne_sera_pas_rejoue(lot):
    _, taches = lot
    assert "aucun rejeu" in taches[0].error, taches[0].error


# ── A3. Le drapeau de dispatch ───────────────────────────────────────────────────────────


def test_A3_le_drapeau_de_dispatch_est_leve(lot):
    rt, _ = lot
    assert rt.queue.scheduled_cleared == ["bk"], (
        "sans clear_scheduled, le lot suivant attend le TTL du drapeau pour rien"
    )


# ── A4. La nature de l'échec ─────────────────────────────────────────────────────────────


def test_A4_lechec_porte_sa_propre_nature(lot):
    _, taches = lot
    assert all(t.error_kind == "restriction_instances" for t in taches)
    assert all(t.error_kind != "quota_journalier" for t in taches), (
        "ce n'est pas un quota : chercher du quota est ce qui a coûté les trois heures"
    )


def test_A4_le_motif_nevoque_ni_saturation_ni_quota(lot):
    """Le texte est le repli du client quand `error_kind` manque : il ne doit pas l'égarer.

    `decideurs.py` classe par expressions régulières — `satur|indisponible|timeout|occup` vers
    « passerelle occupée », `429|quota|rate.limit` vers « épuisé ». Le motif d'une contradiction
    de configuration ne doit tomber dans aucun des deux seaux.
    """
    import re

    _, taches = lot
    motif = taches[0].error
    assert not re.search(r"(satur|indisponible|timeout|occup|unavailable)", motif, re.I), motif
    assert not re.search(r"\b(429|quota|rate.?limit)", motif, re.I), motif


def test_A4_une_alarme_est_levee(lot):
    rt, _ = lot
    assert rt.metrics.compteurs.get("alarme:restriction_instances") == 1


# ── A5. La saturation ordinaire n'est pas touchée ────────────────────────────────────────


def test_A5_une_saturation_ordinaire_garde_son_chemin(monkeypatch):
    """`RuntimeError` = fenêtre pleine ou panne : attente, abandon après retries, motif historique.

    Ce lot ne déplace rien sur ce chemin. S'il le déplaçait, il échangerait un incident rare
    contre une régression sur le cas le plus fréquent de la passerelle.
    """
    taches = _taches(3)
    rt = _runtime(RuntimeError("Tous les fournisseurs LLM sont saturés"), taches, par_pop=100)
    monkeypatch.setattr(task_worker, "get_worker_runtime", lambda: rt)

    process_batch_task.run("bk", force_provider=None, min_tpm_required=None,
                           min_output_required=None, instances_admises=None)

    assert all(t.status == TaskStatus.FAILED for t in taches)
    assert all("Providers saturés ou indisponibles" in t.error for t in taches), taches[0].error
    assert all(t.error_kind is None for t in taches), (
        "le chemin saturation ne porte pas de nature d'échec, et n'en gagne pas une ici"
    )
    assert rt.metrics.compteurs.get("alarme:providers_satures") == 1
    assert "alarme:restriction_instances" not in rt.metrics.compteurs
    assert rt.queue.scheduled_cleared == [], (
        "le chemin saturation ne touchait pas au drapeau de dispatch : il n'y touche toujours pas"
    )
