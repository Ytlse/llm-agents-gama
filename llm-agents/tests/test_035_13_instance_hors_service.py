"""Une instance hors service côté passerelle n'est pas « disponible » — une instance occupée, si (ticket 035).

`/health` publie des signaux distincts : `quota_exhausted` (le seau du jour est vide), `disabled`
(désactivée après des erreurs consécutives — 402 crédits, 5xx…), `cooldown`, et `available`
(« peut prendre une requête MAINTENANT » : ni désactivée, ni en cooldown, ni épuisée, ni saturée
en appels simultanés).

Deux pannes ont fixé ce contrat :
- 2026-09-07 : `cerebras_gpt-oss-120b` en HTTP 402, désactivée par la passerelle mais
  `quota_exhausted: false` (seau du jour intact). Le go/no-go ne lisait que le quota : expérience
  admise sur une instance morte, découverte en brûlant ses requêtes.
- 2026-09-08 : `lmstudio_muse_glimmer_28b_key1`, un modèle local à un appel à la fois. Le go/no-go
  lisait alors `available`, faux pendant chaque génération : deux décisions après sa reprise,
  l'expérience a été déclarée épuisée jusqu'au lendemain 07:00, sans quota ni panne.

Motif à traquer dans ce projet : un signal lu pour ce qu'il n'est pas.
"""

from experiences.ressources import MoniteurRessources, hors_service, occupee

_PROVIDERS = {
    "cerebras_gpt-oss-120b": {"default_model": "gpt-oss-120b", "rpd_limit": 1000},
    "mistral": {"default_model": "mistral-small-latest"},
    "lmstudio_muse_glimmer_28b_key1": {"default_model": "meta/muse-glimmer", "concurrency_limit": 1},
}


def _moniteur(etat: dict, instances: list[str] | None = None) -> MoniteurRessources:
    m = MoniteurRessources(
        instances or list(_PROVIDERS), _PROVIDERS, base_url="http://x", lecteur=lambda _u: etat
    )
    m.rafraichir()
    return m


def test_desactivee_rend_l_instance_indisponible():
    """Le 402 du 2026-09-07 : la passerelle désactive, le seau du jour reste intact."""
    m = _moniteur({
        "cerebras_gpt-oss-120b": {"available": False, "disabled": True, "cooldown": False,
                                  "quota_exhausted": False, "daily_requests": 9},
        "mistral": {"available": True, "disabled": False, "cooldown": False, "quota_exhausted": False,
                    "daily_requests": 280},
    }, ["cerebras_gpt-oss-120b", "mistral"])
    assert not m.disponible("cerebras_gpt-oss-120b"), "désactivée, donc pas servable"
    assert m.disponible("mistral")
    assert m.instances_disponibles() == ["mistral"]


def test_en_cooldown_rend_l_instance_indisponible():
    m = _moniteur({"mistral": {"available": False, "disabled": False, "cooldown": True}}, ["mistral"])
    assert not m.disponible("mistral")
    assert hors_service({"disabled": False, "cooldown": True})


def test_occupee_n_est_pas_hors_service():
    """Le 2026-09-08 : un modèle local à un appel à la fois est `available: false` pendant chaque
    génération. Il est servable — la requête suivante attendra son tour, c'est tout."""
    etat = {"lmstudio_muse_glimmer_28b_key1": {"available": False, "disabled": False, "cooldown": False,
                                               "quota_exhausted": False, "active_tasks": 1, "daily_requests": 11}}
    m = _moniteur(etat, ["lmstudio_muse_glimmer_28b_key1"])
    assert m.disponible("lmstudio_muse_glimmer_28b_key1"), "occupée ≠ hors service"
    assert not m.epuise(), "aucun quota, aucune panne : rien n'est épuisé"
    assert not hors_service(etat["lmstudio_muse_glimmer_28b_key1"])
    assert occupee(etat["lmstudio_muse_glimmer_28b_key1"])
    ligne = m.tableau()[0]
    assert ligne["disponible"] and ligne["occupee"] and not ligne["epuisee"]


def test_une_experience_sur_la_seule_instance_hors_service_est_epuisee():
    """Le refus doit tomber à l'admission, pas après neuf requêtes brûlées."""
    m = _moniteur(
        {"cerebras_gpt-oss-120b": {"available": False, "disabled": True, "cooldown": False, "daily_requests": 9}},
        ["cerebras_gpt-oss-120b"],
    )
    assert m.epuise(), "aucune instance servable"
    assert "désactivée côté passerelle" in m.raison_epuisement(), m.raison_epuisement()


def test_sans_disabled_ni_cooldown_available_fait_foi():
    """Passerelle ancienne, qui ne publie pas les deux champs : `available` reste le seul signal."""
    m = _moniteur({"mistral": {"available": False, "daily_requests": 9}}, ["mistral"])
    assert not m.disponible("mistral")
    m = _moniteur({"mistral": {"available": True, "daily_requests": 9}}, ["mistral"])
    assert m.disponible("mistral")


def test_available_absent_reste_permissif():
    """Une passerelle qui ne publie aucun de ces champs ne doit bloquer aucune expérience."""
    m = _moniteur({"mistral": {"daily_requests": 3}})
    assert m.disponible("mistral")
    assert not hors_service({}) and not occupee({})


def test_le_quota_du_jour_reste_un_motif_distinct():
    m = _moniteur({
        "cerebras_gpt-oss-120b": {"available": True, "disabled": False, "cooldown": False,
                                  "quota_exhausted": False, "daily_requests": 1000},
    })
    assert not m.disponible("cerebras_gpt-oss-120b"), "marge nulle : 1000/1000"
    assert not occupee({"available": True}), "disponible n'est pas occupée"
