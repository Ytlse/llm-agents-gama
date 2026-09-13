"""configure_logging ne touche qu'au handler par défaut de loguru et se défait proprement."""
from __future__ import annotations

import sys

from loguru import logger

from llm_gateway.telemetry import logger as tl


def test_les_sinks_de_l_hote_survivent(capsys):
    tl.reset_logging()
    host_id = logger.add(sys.stderr, level="INFO", format="HOTE {message}")
    try:
        tl.configure_logging(level="INFO")
        tl.configure_logging(level="DEBUG")   # idempotent : un seul handler du gateway
        logger.info("bonjour")
        err = capsys.readouterr().err
        assert err.count("bonjour") == 2, "le sink de l'hôte et celui du gateway écrivent tous deux"
        assert "HOTE bonjour" in err
    finally:
        logger.remove(host_id)
        tl.reset_logging()


def test_reset_retire_ce_que_configure_a_pose(capsys):
    tl.reset_logging()
    tl.configure_logging(level="INFO")
    tl.reset_logging()
    logger.info("après reset")
    assert "après reset" not in capsys.readouterr().err
