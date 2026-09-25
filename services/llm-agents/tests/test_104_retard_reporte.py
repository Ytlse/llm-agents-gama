"""Un départ reporté par le calendrier n'est pas un retard subi (2026-09-23).

`expected_arrive_at` est calculé par GAMA depuis le `schedule_at` d'origine et n'est jamais
recalculé quand le départ est reporté — ni par le bouclage J+1, ni par `no_weekend_departures`.
Le run du 2026-09-23 en portait deux, relevés dans `gama_arrivals.csv` : 23,6 h et 71,6 h de
« retard » pour des trajets de douze minutes. Chacun produisait une gravité de 0,70 et un
souvenir « grave » dans la ligne de base, indiscernable du choc déclaré à 0,75 — et, dans le
prompt de l'agent, un « Late by: 23 hours » qu'il n'avait pas vécu.
"""

from text_helper.models.arrival import (
    SEUIL_REPORT_CALENDAIRE_S,
    EnvObArrival,
    retard_d_arrivee,
)

H = 3600
J = 86400


# ── Les deux cas MESURÉS du run du 2026-09-23 ────────────────────────────────────────────

# schedule_at Wed 18 Mar 19:35 · started_at Thu 19 Mar 19:15 · attendu Wed 18 Mar 19:50
# arrivé Thu 19 Mar 19:27 — bouclage J+1, trajet de 12 min contre 15 planifiées.
BOUCLAGE_J1 = dict(
    schedule_at=1773862500, started_at=1773947700,
    expected_arrive_at=1773863400, arrive_at=1773948420,
)
# schedule_at Fri 20 Mar 19:35 · started_at Mon 23 Mar 19:15 — report de week-end.
REPORT_WEEKEND = dict(
    schedule_at=1774035300, started_at=1774293300,
    expected_arrive_at=1774036200, arrive_at=1774294020,
)


def test_R1_le_bouclage_J1_ne_produit_aucun_retard():
    """23,6 h de « retard » pour un trajet arrivé EN AVANCE sur son propre départ."""
    brut = BOUCLAGE_J1["arrive_at"] - BOUCLAGE_J1["expected_arrive_at"]
    assert brut > 23 * H, "le cas mesuré doit bien porter le défaut d'origine"
    assert retard_d_arrivee(**BOUCLAGE_J1) == 0


def test_R2_le_report_de_week_end_ne_produit_aucun_retard():
    """71,6 h de « retard » pour un trajet du vendredi soir joué le lundi."""
    brut = REPORT_WEEKEND["arrive_at"] - REPORT_WEEKEND["expected_arrive_at"]
    assert brut > 71 * H, "le cas mesuré doit bien porter le défaut d'origine"
    assert retard_d_arrivee(**REPORT_WEEKEND) == 0


def test_R3_ces_deux_cas_ne_produisent_plus_de_souvenir_grave():
    """Le point qui compte pour l'expérience : plus de gravité dans la ligne de base.

    0,70 était la valeur servie, contre 0,75 pour le choc c3 déclaré : à cinq centièmes, la
    ligne de base devenait indiscernable de ce qu'on injecte.
    """
    from llm.gravite import gravite_deterministe

    for cas in (BOUCLAGE_J1, REPORT_WEEKEND):
        avant, _ = gravite_deterministe(
            retard_s=float(cas["arrive_at"] - cas["expected_arrive_at"])
        )
        apres, _ = gravite_deterministe(retard_s=float(retard_d_arrivee(**cas)))
        assert avant >= 0.68, f"le cas mesuré valait {avant:.2f} avant correction"
        assert apres == 0.0


# ── Ce qui NE DOIT PAS changer ───────────────────────────────────────────────────────────


def test_R4_un_glissement_ordinaire_reste_un_retard_vecu():
    """Une activité qui déborde de vingt minutes : l'agent l'a bien vécu."""
    assert retard_d_arrivee(
        arrive_at=1_000_000 + 20 * 60, expected_arrive_at=1_000_000,
        schedule_at=999_000, started_at=999_000 + 20 * 60,
    ) == 20 * 60


def test_R5_un_vrai_retard_sur_un_depart_a_l_heure_est_conserve():
    assert retard_d_arrivee(
        arrive_at=1_000_000 + 1800, expected_arrive_at=1_000_000,
        schedule_at=998_200, started_at=998_200,
    ) == 1800


def test_R6_une_arrivee_en_avance_vaut_zero_et_non_un_retard_negatif():
    """Sans quoi une avance viendrait compenser un incident réel dans la même entrée."""
    assert retard_d_arrivee(
        arrive_at=1_000_000 - 600, expected_arrive_at=1_000_000,
        schedule_at=998_200, started_at=998_200,
    ) == 0


def test_R7_sans_les_deux_champs_le_calcul_est_celui_d_avant():
    """Aucun appelant existant ne change de comportement (compatibilité ascendante)."""
    assert retard_d_arrivee(arrive_at=1_000_000 + 900, expected_arrive_at=1_000_000) == 900
    assert retard_d_arrivee(
        arrive_at=1_000_000 + 900, expected_arrive_at=1_000_000, schedule_at=999_000,
    ) == 900


def test_R8_le_seuil_separe_bien_les_deux_familles():
    """Juste sous le seuil : vécu. Juste au-dessus : reporté."""
    base = 1_000_000
    sous = retard_d_arrivee(
        arrive_at=base + SEUIL_REPORT_CALENDAIRE_S - 1, expected_arrive_at=base,
        schedule_at=base, started_at=base + SEUIL_REPORT_CALENDAIRE_S - 1,
    )
    dessus = retard_d_arrivee(
        arrive_at=base + SEUIL_REPORT_CALENDAIRE_S, expected_arrive_at=base,
        schedule_at=base, started_at=base + SEUIL_REPORT_CALENDAIRE_S,
    )
    assert sous == SEUIL_REPORT_CALENDAIRE_S - 1
    assert dessus == 0


# ── Le texte que LIT l'agent ─────────────────────────────────────────────────────────────


def _observation(**kw) -> EnvObArrival:
    return EnvObArrival(
        type="arrival", timestamp=kw["arrive_at"], purpose="home",
        duration=720.0, plan_duration=900.0, **kw,
    )


def test_R9_le_prompt_ne_dit_plus_un_retard_que_l_agent_n_a_pas_vecu():
    """Le gabarit rend « Late by: … » depuis `ob.late` : c'est entré dans sa mémoire."""
    ob = _observation(**REPORT_WEEKEND)
    assert ob.late == 0
    assert not ob.is_late
    assert "Late by" not in ob.describe()
    assert "On time" in ob.describe()


def test_R10_un_vrai_retard_se_dit_toujours_dans_le_prompt():
    ob = _observation(
        schedule_at=998_200, started_at=998_200,
        expected_arrive_at=1_000_000, arrive_at=1_000_000 + 1800,
    )
    assert ob.late == 1800
    assert "Late by" in ob.describe()
