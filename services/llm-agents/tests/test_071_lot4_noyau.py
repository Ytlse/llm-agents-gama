"""Ticket 071, lot 4 — la mémoire noyau.

Contrat : `specs/ticket_071/tests_lot4.md`. Les identifiants (A1, B2, C3, D1…) y renvoient.

Le point central est le GARDE-FOU : les trois blocs sont calculés, aucun n'est écrit par le
modèle. Un texte réécrit périodiquement par un modèle dérive et invente ; un bloc calculé reste
vérifiable contre sa source.
"""

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm.memory import MemoryEntry, MemoryType
from llm.noyau import (
    CONNAISSANCES_MAX,
    OCCURRENCES_MIN_HABITUDE,
    bloc_changements,
    bloc_connaissances,
    bloc_habitudes,
    memoire_noyau,
    noter_trajet,
)
from settings import settings
from sim_clock import wall_clock

T0 = 1773637200


def _journal(*trajets) -> dict:
    j: dict = {}
    for motif, creneau, mode, retard in trajets:
        noter_trajet(j, motif, creneau, mode, retard)
    return j


def _concept(texte, obs=1, contre=0, jours=1, depasse=None):
    return MemoryEntry(
        content=f'["{texte}", "k", "s", "t", "work"]',
        timestamp=wall_clock(T0) - timedelta(days=jours),
        memory_type=MemoryType.CONCEPT,
        person_id="42",
        observations=obs,
        contre_exemples=contre,
        depasse_le=depasse,
    )


def _choc(texte, gravite=0.9, jours=1):
    return MemoryEntry(
        content=texte,
        timestamp=wall_clock(T0) - timedelta(days=jours),
        memory_type=MemoryType.REFLECTION,
        person_id="42",
        importance=gravite,
        force=19.6,
    )


# ═══════════════════════ A. Le bloc « Mes habitudes » ═══════════════════════════


def test_A1_la_part_du_mode_dominant_est_dite_sur_le_total():
    j = _journal(*([("work", "matin", "cycling", 0)] * 9), *([("work", "matin", "car", 0)] * 2))
    lignes = bloc_habitudes(j)
    assert len(lignes) == 1
    assert "9 fois sur 11" in lignes[0]
    assert "à vélo" in lignes[0]


def test_A2_une_occurrence_n_est_pas_une_habitude():
    """Dire « vélo, 1 fois sur 1 » donnerait à un aléa l'autorité d'une routine."""
    assert bloc_habitudes(_journal(("work", "matin", "cycling", 0))) == []
    j = _journal(*([("work", "matin", "cycling", 0)] * (OCCURRENCES_MIN_HABITUDE - 1)))
    assert bloc_habitudes(j) == []


def test_A3_deux_motifs_font_deux_lignes():
    j = _journal(
        *([("work", "matin", "cycling", 0)] * 4),
        *([("shop", "midi", "walking", 0)] * 4),
    )
    assert len(bloc_habitudes(j)) == 2


def test_A4_les_retards_sont_comptes_et_dits_sans_etre_inventes():
    sans = _journal(*([("work", "matin", "cycling", 0)] * 4))
    assert "retard" not in bloc_habitudes(sans)[0]
    avec = _journal(
        *([("work", "matin", "cycling", 0)] * 3),
        ("work", "matin", "cycling", 900),
    )
    assert "1 retard(s) de plus de 10 min" in bloc_habitudes(avec)[0]


def test_A4bis_un_retard_court_ne_compte_pas():
    j = _journal(*([("work", "matin", "cycling", 300)] * 4))
    assert "retard" not in bloc_habitudes(j)[0]


def test_A5_sans_trajet_le_bloc_est_absent_et_non_vide_avec_un_titre():
    """Un titre sans contenu dit au modèle qu'il devrait y avoir quelque chose."""
    assert memoire_noyau({}, [], wall_clock(T0)) == []
    assert "Mes habitudes" not in "".join(memoire_noyau({}, [], wall_clock(T0)))


def test_A6_un_trajet_sans_mode_resolu_ne_fausse_pas_le_denominateur():
    """Il n'est pas compté du tout, plutôt que compté comme un mode inconnu."""
    j = _journal(*([("work", "matin", "cycling", 0)] * 4), ("work", "matin", None, 0))
    assert "4 fois sur 4" in bloc_habitudes(j)[0]


def test_A7_le_bloc_des_habitudes_est_calcule_et_non_ecrit_par_le_modele():
    """LE garde-fou du lot.

    `bloc_habitudes` ne prend QUE le journal des trajets : il ne peut pas inventer, et son
    résultat se vérifie contre sa source. Aucun texte du modèle n'y entre.
    """
    import inspect

    from llm import noyau

    signature = inspect.signature(noyau.bloc_habitudes)
    assert list(signature.parameters) == ["journal"], (
        "le bloc des habitudes ne doit dépendre que du journal des trajets"
    )
    j = _journal(*([("work", "matin", "cycling", 0)] * 4))
    assert bloc_habitudes(j) == bloc_habitudes(j), "calcul déterministe"


# ═══════════════════ B. Le bloc « Ce que je sais » ══════════════════════════════


def test_B1_chaque_enonce_porte_son_compteur():
    lignes = bloc_connaissances([_concept("le bus 401 est fiable", obs=12)])
    assert "le bus 401 est fiable" in lignes[0]
    assert "(12 obs.)" in lignes[0]


def test_B2_un_concept_hors_service_est_absent():
    """On ne sert pas au modèle ce que l'agent ne croit plus."""
    assert bloc_connaissances([_concept("faux", obs=0, contre=3)]) == []


def test_B2bis_un_concept_mis_a_l_ecart_est_absent():
    ecarte = _concept("périmé", obs=5, contre=1, depasse="2026-03-15T22:00:00")
    assert bloc_connaissances([ecarte]) == []


def test_B3_un_concept_jamais_confirme_est_present():
    lignes = bloc_connaissances([_concept("vu une fois", obs=0)])
    assert len(lignes) == 1 and "(0 obs.)" in lignes[0]


def test_B4_les_plus_confiants_d_abord_et_plafonnes():
    concepts = [_concept(f"c{i}", obs=i) for i in range(12)]
    lignes = bloc_connaissances(concepts)
    assert len(lignes) == CONNAISSANCES_MAX
    assert "c11" in lignes[0], "le plus confiant en tête"


def test_B5_sans_concept_le_bloc_est_absent():
    assert bloc_connaissances([]) == []


def test_B6_une_entree_episodique_n_est_pas_une_connaissance():
    assert bloc_connaissances([_choc("je suis tombé")]) == []


# ═════════════ C. Le bloc « Ce qui a changé récemment » ═════════════════════════


def test_C1_un_choc_recent_est_present():
    lignes = bloc_changements([_choc("panne ligne A, 45 minutes perdues")], wall_clock(T0))
    assert lignes and "panne ligne A" in lignes[0]


def test_C2_un_concept_mis_a_l_ecart_est_present():
    """C'est ici que l'hystérésis devient lisible dans le prompt lui-même."""
    ecarte = _concept(
        "la ligne A est fiable", obs=1, contre=4,
        depasse=(wall_clock(T0) - timedelta(days=1)).isoformat(),
    )
    lignes = bloc_changements([ecarte], wall_clock(T0))
    assert lignes and "Je ne crois plus" in lignes[0]
    assert "la ligne A est fiable" in lignes[0]


def test_C3_un_choc_ancien_est_absent():
    assert bloc_changements([_choc("vieux choc", jours=60)], wall_clock(T0)) == []


def test_C4_sans_changement_le_bloc_est_absent():
    assert bloc_changements([_concept("stable", obs=5)], wall_clock(T0)) == []


def test_C5_un_trajet_ordinaire_n_est_pas_un_changement():
    ordinaire = _choc("trajet sans histoire", gravite=0.1)
    assert bloc_changements([ordinaire], wall_clock(T0)) == []


def test_C6_sans_horloge_simulee_le_bloc_est_vide_plutot_que_faux():
    """Jamais de repli sur l'horloge de la machine."""
    assert bloc_changements([_choc("panne")], None) == []


# ═══════════════════ D. Le bloc complet ═════════════════════════════════════════


def test_D1_le_bloc_ne_porte_aucune_metadonnee_sur_lui_meme():
    """Ni date de mise à jour, ni nombre de jours de vécu.

    Cela ne change aucune décision, coûte des jetons, et rompt la fiction que les gabarits
    maintiennent : une personne ne pense pas « mon résumé d'habitudes date de trois jours ».
    """
    bloc = "\n".join(
        memoire_noyau(
            _journal(*([("work", "matin", "cycling", 0)] * 4)),
            [_concept("le bus 401 est fiable", obs=12)],
            wall_clock(T0),
        )
    )
    for interdit in ("mis à jour", "jours de vécu", "dernière mise", "il y a "):
        assert interdit not in bloc.lower(), f"métadonnée interdite : {interdit}"
    assert "2026" not in bloc, "aucune date sur le bloc lui-même"


def test_D2_les_trois_blocs_apparaissent_dans_l_ordre():
    bloc = memoire_noyau(
        _journal(*([("work", "matin", "cycling", 0)] * 4)),
        [
            _concept("le bus 401 est fiable", obs=12),
            _choc("panne ligne A"),
        ],
        wall_clock(T0),
    )
    texte = "\n".join(bloc)
    assert texte.index("Mes habitudes") < texte.index("Ce que je sais")
    assert texte.index("Ce que je sais") < texte.index("Ce qui a changé récemment")


def test_D3_un_bloc_vide_ne_laisse_pas_son_titre():
    bloc = "\n".join(memoire_noyau({}, [_concept("je sais", obs=3)], wall_clock(T0)))
    assert "Ce que je sais" in bloc
    assert "Mes habitudes" not in bloc
    assert "Ce qui a changé" not in bloc


def test_D4_le_parametre_des_episodiques_est_distinct_du_top_k():
    """Réutiliser `long_term_max_entries_query` rendrait toute mesure de sensibilité ambiguë."""
    assert settings.agent.memoire__episodiques_avec_noyau == 3
    assert settings.agent.long_term_max_entries_query == 10


def test_D5_le_lot_4_ne_coute_aucun_appel_au_modele():
    """Les trois blocs sont calculés : aucune inférence supplémentaire.

    Vérifié par la signature : `memoire_noyau` ne reçoit ni client, ni passerelle, ni prompt.
    """
    import inspect

    from llm import noyau

    # `person_id` ajouté par le lot I du 077 : il ne sert qu'au journal — la sortie de fenêtre
    # d'un souvenir de choc était invisible sans lui. Il ne rapproche d'aucun appel au modèle,
    # et la garde qui compte est celle de la source, juste en dessous.
    assert list(inspect.signature(noyau.memoire_noyau).parameters) == [
        "journal",
        "entrees",
        "maintenant",
        "person_id",
    ]
    source = inspect.getsource(noyau)
    for interdit in ("llm_client", "execute(", "PromptName", "gateway"):
        assert interdit not in source, f"le noyau ne doit rien demander au modèle : {interdit}"


# ═══════════════════ Journal persisté ═══════════════════════════════════════════


def test_le_journal_est_serialisable_en_json():
    """Il est persisté avec les métadonnées de l'agent : il doit passer par JSON.

    Sans persistance, un run repris repartirait sans habitudes, et le bloc mentirait par
    omission tout le premier jour.
    """
    import json

    j = _journal(*([("work", "matin", "cycling", 0)] * 4))
    relu = json.loads(json.dumps(j))
    assert bloc_habitudes(relu) == bloc_habitudes(j)
