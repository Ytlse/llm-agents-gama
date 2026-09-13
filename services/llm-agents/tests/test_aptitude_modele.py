"""Aptitude d'un modèle à porter une expérience — spec hygiène §6, proposition P3.

La sévérité est le sujet de ces tests. Refuser trop large bloque du travail légitime : les
limites de `providers.yaml` sont déclaratives et parfois fausses (des runs sur
`gemini-3.5-flash-lite` ont abouti au-delà du `rpd_limit` déclaré). On ne refuse donc que
l'impossible, on avertit sur le lent.
"""

from __future__ import annotations

from experiences import aptitude as APT

CHARGE = dict(
    sollicitations=2285, jetons_entree=1289, jetons_sortie=400, max_tokens_demande=4096
)


def _verifier(providers, instances=None, **kw):
    args = {**CHARGE, **kw}
    return APT.verifier(
        modele=kw.pop("modele", "m") if "modele" in kw else "m",
        providers=providers,
        instances=instances if instances is not None else list(providers),
        **{k: v for k, v in args.items() if k != "modele"},
    )


def test_quota_absurde_refuse():
    """20 requêtes/jour pour 2 285 sollicitations = 114 jours : aucun étalement ne rattrape ça."""
    refus, _ = _verifier({"i": {"rpd_limit": 20, "rpm_limit": 5}})
    assert refus and "hors d'atteinte" in refus[0]
    assert "114 jours" in refus[0] or "jours de quota" in refus[0]


def test_quota_juste_court_avertit_sans_refuser():
    """1 000/jour pour 2 285 : deux fenêtres de quota et une reprise, pas une impossibilité."""
    refus, avert = _verifier({"a": {"rpd_limit": 500}, "b": {"rpd_limit": 500}})
    assert refus == []
    assert any("plus court que la charge" in m for m in avert)
    assert any("ce n'est pas un refus" in m for m in avert)


def test_quota_suffisant_ne_dit_rien():
    refus, avert = _verifier({"i": {"rpd_limit": 5000, "rpm_limit": 60, "tpm_limit": 500000}})
    assert refus == [] and avert == []


def test_plafond_par_requete_refuse():
    """Un plafond sous le besoin tronque CHAQUE appel : c'est structurel, pas du quota."""
    refus, _ = _verifier(
        {"i": {"rpd_limit": 99999, "max_tokens_per_request": 1000}}
    )
    assert refus and "plafonne à 1000 jetons par requête" in refus[0]
    assert "tronqué" in refus[0]


def test_plafond_de_sortie_refuse():
    refus, _ = _verifier({"i": {"rpd_limit": 99999, "max_output_tokens": 2048}})
    assert refus and "plafonne la sortie à 2048" in refus[0]


def test_plafond_par_requete_suffisant_passe():
    refus, _ = _verifier(
        {"i": {"rpd_limit": 99999, "max_tokens_per_request": 8000, "max_output_tokens": 4096}}
    )
    assert refus == []


def test_tpm_bride_le_debit_et_le_dit():
    """rpm_limit 30 annoncé, mais tpm 8 000 ÷ 1 689 jetons = 4,7 req/min réelles."""
    _, avert = _verifier(
        {"i": {"rpd_limit": 99999, "rpm_limit": 30, "tpm_limit": 8000}}
    )
    joint = " ".join(avert)
    assert "débit bridé par les jetons" in joint
    assert "4.7 requêtes/min" in joint and "rpm_limit 30" in joint


def test_duree_longue_avertit():
    _, avert = _verifier({"i": {"rpd_limit": 99999, "rpm_limit": 5}})
    assert any("durée estimée" in m and "fenêtre de renouvellement" in m for m in avert)


def test_jetons_inconnus_ne_refusent_pas():
    """Refuser sur une valeur inconnue bloquerait tout modèle jamais mesuré, donc tout modèle neuf."""
    refus, _ = _verifier(
        {"i": {"rpd_limit": 99999, "max_tokens_per_request": 100}},
        jetons_entree=None,
        jetons_sortie=None,
    )
    assert refus == []


def test_limites_non_declarees_ne_refusent_pas():
    """Une instance qui ne déclare aucune limite n'est pas réputée inapte."""
    refus, avert = _verifier({"i": {}})
    assert refus == [] and avert == []


def test_sans_instance_aucun_verdict():
    """L'absence d'instance servant le modèle est déjà refusée en amont : ne pas doubler."""
    refus, avert = _verifier({"i": {"rpd_limit": 20}}, instances=[])
    assert refus == [] and avert == []


def test_marge_de_quota_appliquee():
    """Consommer le quota au jeton près échoue sur la première erreur réessayée."""
    refus, avert = _verifier({"i": {"rpd_limit": 2285}})
    assert refus == []
    assert any("plus court que la charge" in m for m in avert), (
        "2285 de quota pour 2285 sollicitations doit avertir : la marge est de 5 %"
    )


# ── Profondeur de réflexion (2026-09-10) ─────────────────────────────────────


def test_reflexion_au_dela_du_plafond_declare_refuse():
    """Le fournisseur raboterait sans le dire : l'empreinte porterait un budget non appliqué."""
    refus, _ = _verifier(
        {"i": {"rpd_limit": 99999, "thinking_budget_max": 8192}}, reflexion_demandee=16384
    )
    assert refus and "au-delà du plafond déclaré 8192" in refus[0]
    assert "non appliqué" in refus[0]


def test_reflexion_dans_le_plafond_passe():
    refus, avert = _verifier(
        {"i": {"rpd_limit": 99999, "thinking_budget_max": 8192}}, reflexion_demandee=8192
    )
    assert refus == []
    assert not [m for m in avert if "réflexion" in m]


def test_reflexion_sans_plafond_declare_avertit_sans_refuser():
    """On ne refuse pas sur une mesure absente — on dit qu'on ne peut pas vérifier."""
    refus, avert = _verifier({"i": {"rpd_limit": 99999}}, reflexion_demandee=4096)
    assert refus == []
    assert any("aucun `thinking_budget_max`" in m for m in avert)


def test_reflexion_absente_ou_nulle_ne_declenche_rien():
    for valeur in (None, 0, -1):
        refus, avert = _verifier({"i": {"rpd_limit": 99999}}, reflexion_demandee=valeur)
        assert refus == []
        assert not [m for m in avert if "réflexion" in m], valeur


def test_niveau_non_accepte_refuse():
    """`minimal` n'existe pas sur gemini-3.7/3.8 : chaque appel partirait en 400."""
    refus, _ = _verifier(
        {"i": {"rpd_limit": 99999, "thinking_levels": ["low", "medium", "high"]}},
        niveau_demande="minimal",
    )
    assert refus and "non accepté" in refus[0] and "400" in refus[0]


def test_niveau_accepte_passe():
    refus, avert = _verifier(
        {"i": {"rpd_limit": 99999, "thinking_levels": ["low", "medium", "high"]}},
        niveau_demande="high",
    )
    assert refus == []
    assert not [m for m in avert if "niveau" in m]


def test_niveau_sans_declaration_avertit():
    refus, avert = _verifier({"i": {"rpd_limit": 99999}}, niveau_demande="high")
    assert refus == []
    assert any("aucun `thinking_levels`" in m for m in avert)


def test_niveau_et_budget_ensemble_refuses():
    """L'API rend 400 si les deux coexistent — le dire au lancement, pas en vol."""
    refus, _ = _verifier(
        {"i": {"rpd_limit": 99999, "thinking_levels": ["high"]}},
        niveau_demande="high", reflexion_demandee=1024,
    )
    assert refus and "ensemble" in refus[0] and "400" in refus[0]
