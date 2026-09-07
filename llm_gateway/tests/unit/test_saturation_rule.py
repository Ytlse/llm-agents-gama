"""La règle d'abandon du worker : occupé n'est pas en panne."""
from llm_gateway.worker.task_worker import _providers_merely_busy


def _st(**kw):
    base = {"disabled": False, "cooldown": False, "quota_exhausted": False, "available": False}
    base.update(kw)
    return base


def test_fenetre_pleine_est_occupe_pas_en_panne():
    statuses = {"g": _st(available=False)}   # rpm plein, rien d'autre
    assert _providers_merely_busy(statuses, None) is True
    assert _providers_merely_busy(statuses, "g") is True


def test_cooldown_disable_quota_sont_des_pannes():
    assert _providers_merely_busy({"g": _st(cooldown=True)}, None) is False
    assert _providers_merely_busy({"g": _st(disabled=True)}, None) is False
    assert _providers_merely_busy({"g": _st(quota_exhausted=True)}, None) is False


def test_le_provider_force_seul_compte():
    statuses = {"g": _st(cooldown=True), "autre": _st()}
    assert _providers_merely_busy(statuses, "g") is False, "l'autre provider ne compte pas quand g est forcé"
    assert _providers_merely_busy(statuses, None) is True
