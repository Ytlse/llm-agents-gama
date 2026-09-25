"""Le cache OSMnx est-il sur son volume ? — fausse alarme du 2026-09-24.

Le contrôleur range le cache d'une population dans un sous-dossier du volume
(`/app/data/cache/osmnx/toulouse_population_20`) ; le test d'égalité stricte sur la cible de
montage le déclarait « hors volume » à chaque démarrage.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trip_helper.osmnx_direct import _cache_dir_is_mounted  # noqa: E402


def _mountinfo(tmp_path, *cibles: str) -> str:
    lignes = [f"{i} 1 0:{i} / {c} rw - ext4 /dev/x rw" for i, c in enumerate(cibles, start=20)]
    f = tmp_path / "mountinfo"
    f.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return str(f)


CODE = "/app/trip_helper/osmnx_direct.py"


def test_un_sous_dossier_du_volume_est_monte(tmp_path):
    mi = _mountinfo(tmp_path, "/", "/app", "/app/data/cache/osmnx")
    assert _cache_dir_is_mounted("/app/data/cache/osmnx/toulouse_population_20", mi, CODE) is True
    assert _cache_dir_is_mounted("/app/data/cache/osmnx", mi, CODE) is True


def test_sans_volume_le_cache_tombe_dans_le_bind_du_code(tmp_path):
    mi = _mountinfo(tmp_path, "/", "/app")
    assert _cache_dir_is_mounted("/app/data/cache/osmnx/toulouse_population_20", mi, CODE) is False


def test_un_prefixe_de_nom_n_est_pas_un_montage(tmp_path):
    """`/app/data/cache/osmnx_old` n'est pas couvert par le volume `/app/data/cache/osmnx`."""
    mi = _mountinfo(tmp_path, "/", "/app", "/app/data/cache/osmnx")
    assert _cache_dir_is_mounted("/app/data/cache/osmnx_old", mi, CODE) is False


def test_sans_aucun_bind_rien_n_est_monte(tmp_path):
    mi = _mountinfo(tmp_path, "/")
    assert _cache_dir_is_mounted("/app/data/cache/osmnx", mi, CODE) is False


def test_hors_linux_indeterminable(tmp_path):
    assert _cache_dir_is_mounted("/x", str(tmp_path / "absent"), CODE) is None
