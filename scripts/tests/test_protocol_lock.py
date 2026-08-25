"""Jeton d'exclusion des procédures du protocole exogène (ticket 023, lot 1).

Ce qui est verrouillé ici, ce sont les propriétés sans lesquelles le jeton ne serait
qu'un fichier décoratif :

- **la double prise est refusée** — sinon deux procédures évaluent en parallèle sous le
  même quota, et la cascade de fournisseurs peut basculer entre les bras ;
- **un run actif interdit la prise**, et la détection réutilise `live.run_process()` —
  pas une seconde implémentation de `pgrep`, qui dériverait de `make run` ;
- **un jeton orphelin est signalé, JAMAIS levé automatiquement** : un verrou qui se libère
  seul n'est pas un verrou. Une procédure peut encore tourner sous un autre shell ;
- **le relâchement est idempotent** — une procédure interrompue ne doit pas laisser un
  `make protocol-unlock` en échec derrière elle ;
- **les deux instantanés de quota sont écrits**, y compris quand l'API est injoignable :
  c'est la preuve qui entre dans l'archive, et une absence qui se dit absente vaut mieux
  qu'un zéro qui ressemble à une mesure ;
- **la limite cloud est dans la SORTIE**, pas seulement dans le ticket.

Hors ligne : ni docker, ni API, ni GAMA. Toutes les sondes sont substituées.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_module(tmp_path: Path):
    """Charge `protocol_lock.py` avec son verrou déplacé dans `tmp_path`.

    Chargement par chemin, comme le module le fait lui-même pour `live` : ajouter
    `scripts/` au `sys.path` ferait masquer le module standard `warnings` par
    `scripts/warnings.py`.
    """
    spec = importlib.util.spec_from_file_location(
        f"_pl_{tmp_path.name}", ROOT / "scripts" / "protocol_lock.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.LOCK_PATH = tmp_path / "protocol_lock.json"
    return module


@pytest.fixture
def lock(tmp_path, monkeypatch):
    """Jeton isolé, toutes sondes au vert : pas de run, pas de service, API muette."""
    module = _load_module(tmp_path)
    monkeypatch.setattr(module.live, "run_process",
                        lambda: module.live.RunProcess(False))
    monkeypatch.setattr(module, "running_services", lambda: [])
    monkeypatch.setattr(module, "quota_snapshot",
                        lambda: {"at": "T", "available": False, "error": "hors ligne"})
    return module


def _acquire(module, argv=("--subject", "sujet de test", "--cloud-paused")):
    return module.main(["acquire", *argv])


# ── Prise ────────────────────────────────────────────────────────────────────


def test_prise_ecrit_un_jeton_complet(lock, capsys):
    assert _acquire(lock) == 0
    data = json.loads(lock.LOCK_PATH.read_text(encoding="utf-8"))
    # Qui, quoi, depuis quand — un jeton anonyme ne se débloque pas sans risque.
    for champ in ("subject", "host", "user", "pid", "acquired_at",
                  "expected_duration_minutes", "quota_at_acquire"):
        assert data.get(champ) is not None, f"champ absent du jeton : {champ}"
    assert data["subject"] == "sujet de test"
    assert data["pid"] == os.getsid(0)


def test_la_limite_cloud_est_dans_la_sortie(lock, capsys):
    _acquire(lock)
    out = capsys.readouterr().out
    assert "LOCAL" in out and "cloud" in out.lower(), (
        "la limite du jeton sur la campagne cloud doit être écrite dans sa sortie, "
        "pas seulement dans le ticket")


def test_liste_de_controle_cloud_obligatoire(lock):
    """Sans confirmation que la campagne cloud est en pause, la prise est refusée.

    C'est la réponse retenue à l'axe D4 : le verrou local ne peut pas atteindre la VM,
    donc on exige une vérification humaine plutôt que de prétendre la couvrir.
    """
    assert lock.main(["acquire", "--subject", "x"]) == 4
    assert not lock.LOCK_PATH.exists()


def test_double_prise_refusee(lock):
    assert _acquire(lock) == 0
    assert _acquire(lock) == 2, "un second détenteur ne doit jamais obtenir le jeton"


def test_refus_si_un_run_tourne(lock, monkeypatch):
    monkeypatch.setattr(lock.live, "run_process",
                        lambda: lock.live.RunProcess(True, "offline", 4242))
    assert _acquire(lock) == 5
    assert not lock.LOCK_PATH.exists()


def test_la_detection_de_run_passe_par_live_run_process(lock, monkeypatch):
    """La sonde doit être `live.run_process()` et non un `pgrep` recopié.

    Un second `pgrep` dériverait des motifs de `make run` sans que rien ne le signale.
    On le vérifie en cassant la sonde partagée : si la prise réussit quand même, c'est
    qu'une autre implémentation est utilisée.
    """
    appels = []

    def _sonde():
        appels.append(1)
        return lock.live.RunProcess(True, "ihm", 99)

    monkeypatch.setattr(lock.live, "run_process", _sonde)
    assert _acquire(lock) == 5
    assert appels, "live.run_process() n'a pas été appelée"


def test_refus_si_controller_ou_worker_tournent(lock, monkeypatch):
    monkeypatch.setattr(lock, "running_services", lambda: ["controller", "worker"])
    assert _acquire(lock) == 6
    assert not lock.LOCK_PATH.exists()


# ── Orphelin ─────────────────────────────────────────────────────────────────


def _orpheliniser(module):
    """Remplace le PID du jeton par un PID mort."""
    data = json.loads(module.LOCK_PATH.read_text(encoding="utf-8"))
    data["pid"] = 2 ** 30                      # hors de portée de tout PID vivant
    module.LOCK_PATH.write_text(json.dumps(data), encoding="utf-8")


def test_orphelin_detecte_mais_pas_leve(lock, capsys):
    _acquire(lock)
    _orpheliniser(lock)
    assert lock.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "ORPHELIN" in out and "[ALARME]" in out
    assert lock.LOCK_PATH.exists(), (
        "un jeton orphelin ne doit JAMAIS être levé automatiquement : une procédure peut "
        "encore tourner sous un autre shell")


def test_orphelin_bloque_la_prise_sans_reprise_explicite(lock):
    _acquire(lock)
    _orpheliniser(lock)
    assert _acquire(lock) == 3


def test_orphelin_reprenable_explicitement(lock):
    _acquire(lock)
    _orpheliniser(lock)
    assert lock.main(["acquire", "--subject", "reprise", "--cloud-paused",
                      "--steal-orphan"]) == 0
    assert json.loads(lock.LOCK_PATH.read_text(encoding="utf-8"))["subject"] == "reprise"


def test_jeton_corrompu_ne_vaut_pas_absence(lock):
    """Un fichier illisible bloque, il n'autorise pas une seconde prise."""
    lock.LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock.LOCK_PATH.write_text("{ ceci n'est pas du json", encoding="utf-8")
    assert lock.read_lock() is not None
    assert _acquire(lock) != 0


# ── Relâchement ──────────────────────────────────────────────────────────────


def test_relachement_idempotent(lock):
    assert _acquire(lock) == 0
    assert lock.main(["release"]) == 0
    assert lock.main(["release"]) == 0, "relâcher deux fois n'est pas une erreur"
    assert not lock.LOCK_PATH.exists()


def test_relachement_archive_les_deux_instantanes(lock):
    _acquire(lock)
    lock.main(["release"])
    archive = lock.LOCK_PATH.with_name("protocol_lock_last.json")
    data = json.loads(archive.read_text(encoding="utf-8"))
    assert data["quota_at_acquire"] is not None
    assert data["quota_at_release"] is not None, (
        "sans instantané de relâchement, l'archive ne prouve rien")
    assert data["released_at"]


def test_instantane_indisponible_se_dit_indisponible(lock):
    """API injoignable : on enregistre l'absence, on ne fabrique pas des zéros.

    Un instantané de quota rempli de zéros ressemblerait à « aucune consommation » —
    c'est-à-dire au résultat parfait — alors qu'il ne veut rien dire.
    """
    _acquire(lock)
    data = json.loads(lock.LOCK_PATH.read_text(encoding="utf-8"))
    assert data["quota_at_acquire"]["available"] is False
    assert data["quota_at_acquire"]["error"]
    assert "providers" not in data["quota_at_acquire"]


def test_consommation_concurrente_signalee(lock, monkeypatch, capsys):
    """Deux instantanés qui bougent = quelqu'un d'autre a consommé. Le filet du § cloud."""
    snapshots = iter([
        {"at": "T0", "available": True,
         "providers": {"g": {"daily_requests": 10, "daily_tokens": 100,
                             "rpd_limit": None, "tpd_limit": None,
                             "quota_exhausted": False, "available": True}}},
        {"at": "T1", "available": True,
         "providers": {"g": {"daily_requests": 55, "daily_tokens": 900,
                             "rpd_limit": None, "tpd_limit": None,
                             "quota_exhausted": False, "available": True}}},
    ])
    monkeypatch.setattr(lock, "quota_snapshot", lambda: next(snapshots))
    _acquire(lock)
    capsys.readouterr()
    lock.main(["release"])
    out = capsys.readouterr().out
    assert "+45 req" in out and "+800 tok" in out


def test_relachement_d_un_jeton_etranger_refuse(lock):
    _acquire(lock)
    data = json.loads(lock.LOCK_PATH.read_text(encoding="utf-8"))
    data["pid"] = 2 ** 30 - 1
    data["user"] = "quelqu_un_d_autre"
    lock.LOCK_PATH.write_text(json.dumps(data), encoding="utf-8")
    assert lock.main(["release"]) == 2
    assert lock.LOCK_PATH.exists()
    assert lock.main(["release", "--force"]) == 0


# ── Statut ───────────────────────────────────────────────────────────────────


def test_status_libre_puis_detenu(lock, capsys):
    assert lock.main(["status"]) == 0
    assert "LIBRE" in capsys.readouterr().out
    _acquire(lock)
    capsys.readouterr()
    assert lock.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "DÉTENU" in out and "sujet de test" in out


# ── L'état de la pile : la seconde preuve ────────────────────────────────────
#
# Les instantanés de quota exigent que l'API tourne. Or le cas où l'exclusion est la
# MEILLEURE — pile entièrement arrêtée — est précisément celui où l'API ne répond pas.
# Sans cette seconde sonde, l'archive serait la plus pauvre là où la mesure est la plus
# propre.


def test_pile_arretee_est_enregistree_comme_preuve(lock, monkeypatch, capsys):
    monkeypatch.setattr(lock, "all_running_services", lambda: [])
    _acquire(lock)
    data = json.loads(lock.LOCK_PATH.read_text(encoding="utf-8"))
    assert data["stack_at_acquire"]["stack_fully_down"] is True
    assert "AUCUN service en marche" in capsys.readouterr().out


def test_sonde_muette_n_est_pas_une_pile_arretee(lock, monkeypatch, capsys):
    """`None` = « je ne sais pas », `[]` = « rien ne tourne ». Les confondre ferait passer
    une sonde cassée pour une preuve d'exclusion."""
    monkeypatch.setattr(lock, "all_running_services", lambda: None)
    _acquire(lock)
    snap = json.loads(lock.LOCK_PATH.read_text(encoding="utf-8"))["stack_at_acquire"]
    assert snap["probe_available"] is False
    assert snap["stack_fully_down"] is False
    assert "INCONNU" in capsys.readouterr().out


def test_pile_arretee_aux_deux_bouts_vaut_preuve_sans_quotas(lock, monkeypatch, capsys):
    """Quotas indisponibles + pile arrêtée : c'est une preuve, pas un trou."""
    monkeypatch.setattr(lock, "all_running_services", lambda: [])
    _acquire(lock)
    capsys.readouterr()
    lock.main(["release"])
    out = capsys.readouterr().out
    assert "aucun service en marche à la prise NI au relâchement" in out
    assert "[ALARME]" not in out, (
        "une pile entièrement arrêtée ne doit pas déclencher l'alarme des quotas manquants")


def test_quotas_manquants_et_pile_debout_declenchent_l_alarme(lock, monkeypatch, capsys):
    monkeypatch.setattr(lock, "all_running_services", lambda: ["api", "redis"])
    _acquire(lock)
    capsys.readouterr()
    lock.main(["release"])
    assert "[ALARME]" in capsys.readouterr().out


def test_service_bloquant_demarre_pendant_la_procedure_est_signale(lock, monkeypatch,
                                                                   capsys):
    """Le cas qui compte : la prise était propre, quelqu'un a lancé un run ensuite."""
    etats = iter([[], ["controller", "worker"]])
    monkeypatch.setattr(lock, "all_running_services", lambda: next(etats))
    _acquire(lock)
    capsys.readouterr()
    lock.main(["release"])
    out = capsys.readouterr().out
    assert "[ALARME]" in out and "démarrés PENDANT la procédure" in out


def test_l_archive_porte_les_deux_instantanes_de_pile(lock, monkeypatch):
    monkeypatch.setattr(lock, "all_running_services", lambda: [])
    _acquire(lock)
    lock.main(["release"])
    data = json.loads(
        lock.LOCK_PATH.with_name("protocol_lock_last.json").read_text(encoding="utf-8"))
    assert data["stack_at_acquire"] is not None
    assert data["stack_at_release"] is not None
