"""Ticket 092, lot B — le lanceur tolère les pauses normales de GAMA.

`websockets.connect` ferme la connexion par défaut si un ping reste sans réponse 20 s, et
GAMA Server arrête l'expériment dont le client s'est déconnecté. Or GAMA se bloque pendant
qu'il attend les décisions du LLM : en `CACHE=0` c'est le régime NORMAL, et en pénurie de
jetons l'attente est plus longue encore — la règle du dépôt étant d'attendre le
renouvellement plutôt que de dégrader.

Mesuré sur le run 2026-09-16_12_48 : 23 pauses, médiane 9,0 s, maximum 40,9 s, trois
au-dessus de 20 s. Le run est mort à la troisième.

Contrat : `specs/ticket_092/tests.md`.
"""

import asyncio
import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SOURCE = RACINE / "scripts" / "gama" / "launch_headless.py"

VINGT_MINUTES = 20 * 60


def _charger(monkeypatch, **env):
    """Recharge le module avec un environnement donné (les seuils sont lus à l'import)."""
    for cle, valeur in env.items():
        monkeypatch.setenv(cle, valeur)
    spec = importlib.util.spec_from_file_location("launch_headless_sous_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["launch_headless_sous_test"] = module
    spec.loader.exec_module(module)
    return module


def _kwargs_de_connect(module, monkeypatch) -> dict:
    """Capture les arguments passés à websockets.connect sans ouvrir de socket."""
    vus: dict = {}

    async def faux_connect(url, **kwargs):
        vus.update(kwargs)
        vus["url"] = url
        return object()

    monkeypatch.setattr(module.websockets, "connect", faux_connect)
    asyncio.run(module.connect_with_retries())
    return vus


class TestToleranceAuxPauses:
    def test_B1_le_ping_tolere_au_moins_vingt_minutes(self, monkeypatch):
        module = _charger(monkeypatch)
        kwargs = _kwargs_de_connect(module, monkeypatch)
        assert kwargs.get("ping_timeout") is not None, (
            "sans ping_timeout explicite, le défaut de websockets (20 s) tue le run "
            "à la première pause un peu longue"
        )
        assert kwargs["ping_timeout"] >= VINGT_MINUTES

    def test_B2_le_ping_reste_emis(self, monkeypatch):
        """On desserre le délai de réponse, on ne coupe pas la détection : une connexion
        vraiment morte doit encore se voir."""
        module = _charger(monkeypatch)
        kwargs = _kwargs_de_connect(module, monkeypatch)
        interval = kwargs.get("ping_interval", 20)
        assert interval is not None and interval > 0

    def test_B3_le_seuil_est_reglable_et_vaut_1200_par_defaut(self, monkeypatch):
        module = _charger(monkeypatch)
        assert module.PING_TIMEOUT_S == 1200

        autre = _charger(monkeypatch, GAMA_PING_TIMEOUT_S="2400")
        assert autre.PING_TIMEOUT_S == 2400


class TestLeSymptomeResteVisible:
    def test_B4_la_source_ne_masque_pas_les_pauses(self):
        """Le correctif desserre un seuil ; il ne doit pas faire taire les pauses lentes,
        qui restent le signal d'un run qui peine."""
        texte = SOURCE.read_text(encoding="utf-8")
        assert "sync lent" not in texte, (
            "les pauses sont journalisées côté contrôleur ; le lanceur ne doit pas les filtrer"
        )
