"""Ticket 045 — le nom d'une expérience dit la VRAIE famille du modèle (trouvé au balayage).

`ABREV_DECIDEUR["modele"]` valait `lgbm`, si bien que **toute** expérience à décideur modèle
s'annonçait LightGBM, quelle que soit sa famille :

| Artefact | Nom produit avant | Ce que le nom disait |
|---|---|---|
| `mnl_model.json` | `exp_lgbm-mnl_model_…` | un booster, pour un logit multinomial |
| `klr_model.json` | `exp_lgbm-klr_model_…` | un booster, pour une régression à noyau |
| `rf_mode_choice_policy.json` | `exp_lgbm-rf_mode_choi_…` | un booster, pour une forêt |

Le commentaire du ticket 042, dans `decideur_modele.py`, dit exactement pourquoi c'est grave :
*« un libellé faux est pire qu'un libellé absent, parce qu'il ne se remarque pas »*. Ce
libellé-là avait été corrigé dans les traces et dans l'empreinte, mais pas dans le **nom**,
qui est pourtant ce qu'on lit en premier et ce qui nomme le dossier d'archives.

La famille se lit dans le champ `format` de l'artefact, en tête de fichier — donc sans charger
18 Mo de booster. Un artefact illisible ou de format inconnu ne se voit attribuer **aucune**
famille : le segment devient `mod-<fichier>`, qui n'affirme rien.
"""

from __future__ import annotations

from experiences.nommage import segment_decideur


def _modele(artefact: str | None) -> dict:
    return {"type": "modele", "artefact": artefact}


def test_chaque_famille_se_nomme_elle_meme():
    attendus = {
        "scripts/progedo_logit/mode_choice_policy.json": "lgbm",
        "scripts/progedo_logit/mnl_model.json": "mnl",
        "scripts/progedo_logit/klr_model.json": "klr",
        "scripts/progedo_logit/rf_mode_choice_policy.json": "rf",
    }
    for artefact, famille in attendus.items():
        assert segment_decideur(_modele(artefact)) == famille, artefact


def test_quatre_familles_quatre_segments_distincts():
    """Deux familles sous un même segment partageraient le dossier d'archives."""
    segments = [
        segment_decideur(_modele(a))
        for a in (
            "scripts/progedo_logit/mode_choice_policy.json",
            "scripts/progedo_logit/mnl_model.json",
            "scripts/progedo_logit/klr_model.json",
            "scripts/progedo_logit/rf_mode_choice_policy.json",
        )
    ]
    assert len(set(segments)) == 4, segments


def test_sans_artefact_cest_le_booster_par_defaut():
    """L'artefact par défaut du décideur EST le booster : le nommer `lgbm` reste vrai."""
    assert segment_decideur(_modele(None)) == "lgbm"


def test_un_artefact_introuvable_naffirme_aucune_famille():
    """Mieux vaut ne rien dire que dire « lgbm » d'un fichier qu'on n'a pas lu."""
    seg = segment_decideur(_modele("scripts/progedo_logit/inexistant_v7.json"))
    assert seg.startswith("mod-"), seg
    assert "lgbm" not in seg


def test_un_format_inconnu_naffirme_aucune_famille(tmp_path):
    f = tmp_path / "exotique.json"
    f.write_text('{"format": "quelque_chose_de_neuf", "spec_version": 2}', encoding="utf-8")
    seg = segment_decideur(_modele(str(f)))
    assert seg.startswith("mod-") and "lgbm" not in seg, seg
