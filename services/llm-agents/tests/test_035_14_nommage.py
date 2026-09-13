"""Ticket 035, spec nommage-canonique-experiences — le nom se calcule (N2–N13).

Un test par règle, nommé par son numéro. Aucun disque hors `tmp_path` : `attribuer_nom` lit
un dossier d'expériences temporaire.

Depuis le ticket 045 (R18), la population n'est plus une valeur de référence : elle est
absente de `DEFAUTS_NOMMAGE`, donc aucune cohorte n'est muette. Tout nom attendu ici porte
son segment `pop-<abrégé>` en tête du bloc N7 — y compris celui de la définition de
référence, qui vaut `exp_durmin_pop-1000_AAMAS_nosim`. C'est précisément ce que le ticket
corrige : un nom sans substrat se lisait « rien à signaler » et voulait dire « cohorte v1 ».
"""

from __future__ import annotations

import copy

import pytest
import yaml

from experiences import nommage as N

BASE = {
    "nom": "peu-importe",
    "population": {"chemin": "/data/eqasim-output/population_1000_AAMAS"},
    "jeu": {"nom": "population_1000_AAMAS_20260316", "dossier": None},
    "gabarit": {"categorie": "itinary_multi_agent", "variante": "minimal_persona"},
    "decideur": {
        "type": "duree_minimale",
        "modele": None,
        "parametres": {},
        "rejeu_de": None,
        "graine": None,
        "artefact": None,
    },
    "mode": "sans_simulateur",
    "calendrier": {"politique": "commune", "date": "2026-03-16", "graine": 42},
    "horizon_jours": 1,
    "memoire": False,
    "evenements": [],
    "graine_ordre": 42,
    "graine_tirage": 42,
    "regroupement": {"parallelisme": 8},
    "tolerances_horaires": dict(N.TOLERANCES_REFERENCE),
    "max_candidats": 6,
    "attente_max_s": 120,
    "derive_de": None,
    "executions_connues": [],
}


def exp(**changements) -> dict:
    """Une définition de référence, n champs changés (chemins pointés : `decideur.modele`)."""
    d = copy.deepcopy(BASE)
    for cle, valeur in changements.items():
        cible, *reste = cle.split("__")
        if reste:
            d[cible][reste[0]] = valeur
        else:
            d[cible] = valeur
    return d


def ecrire(dossier, nom: str, definition: dict) -> None:
    d = dossier / nom
    d.mkdir(parents=True, exist_ok=True)
    (d / "experience.yaml").write_text(
        yaml.safe_dump({**definition, "nom": nom}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


# ── N2, N3, N8 : grammaire, décideur, température et mode toujours nommés ────


def test_n2_grammaire_et_mode():
    # `exp` · décideur · population · mode : la cohorte s'intercale entre le décideur et le
    # mode parce qu'elle ouvre le bloc N7, avant tous les autres écarts (R18).
    assert N.nom_canonique(exp()) == "exp_durmin_pop-1000_AAMAS_nosim"
    assert N.nom_canonique(exp(mode="simulateur")) == "exp_durmin_pop-1000_AAMAS_sim"


def test_n3_chaque_decideur_a_son_segment():
    attendus = {
        "aleatoire": "exp_alea_pop-1000_AAMAS_nosim",
        "duree_minimale": "exp_durmin_pop-1000_AAMAS_nosim",
        "majoritaire_voiture": "exp_majvoiture_pop-1000_AAMAS_nosim",
        "modele": "exp_lgbm_pop-1000_AAMAS_nosim",
    }
    for type_, attendu in attendus.items():
        assert N.nom_canonique(exp(decideur__type=type_)) == attendu


def test_n3_artefact_et_rejeu_nomment_leur_source():
    # `police_v7.json` n'existe pas sur le disque : la famille ne peut donc pas être lue dans
    # son champ `format`, et le segment n'en affirme AUCUNE (ticket 045). Le nom du fichier
    # reste dans le segment — c'est bien sa source qui nomme —, mais sans prétendre qu'il
    # s'agit d'un booster : le préfixe `lgbm-` d'avant mentait sur tout artefact qui n'en
    # était pas un. Un artefact réel se nomme par sa famille : voir
    # `test_045_11_nom_de_famille_du_modele.py`.
    inconnu = exp(
        decideur__type="modele",
        decideur__artefact="scripts/progedo_logit/police_v7.json",
    )
    assert N.nom_canonique(inconnu) == "exp_mod-police_v7_pop-1000_AAMAS_nosim"
    rejeu = exp(
        decideur__type="rejeu",
        decideur__rejeu_de="/app/data/experiences/e/executions/2026-09-07_22_09_48",
    )
    assert N.nom_canonique(rejeu) == "exp_rejeu-260907-2209_pop-1000_AAMAS_nosim"


def test_n3_passerelle_sans_modele_refuse_de_nommer():
    with pytest.raises(N.NommageImpossible, match="decideur.modele"):
        N.nom_canonique(exp(decideur__type="passerelle"))


def test_n8_temperature_toujours_nommee_pour_la_passerelle():
    def nom(t):
        return N.nom_canonique(
            exp(
                decideur__type="passerelle",
                decideur__modele="mistral-small-latest",
                decideur__parametres={"temperature": t, "top_p": 1.0},
            )
        )

    assert nom(0.0).endswith("_t0_nosim")
    assert nom(0.7).endswith("_t07_nosim")
    assert nom(1.0).endswith("_t1_nosim")
    assert nom(1.25).endswith("_t125_nosim")
    # Un décideur sans température n'en porte pas dans son nom.
    assert "_t" not in N.nom_canonique(exp()).replace("_tir", "")


# ── N4 : slug de modèle ──────────────────────────────────────────────────────


def test_n4_slugs_de_la_campagne():
    assert N.abreger_modele("gemini-3.1-flash-lite-preview") == "gemini-31-fl"
    # `preview` est du BRUIT_MODELE : l'alias retiré et le nom exact donnent le MÊME
    # slug. C'est ce qui a permis de corriger le nom du juge le 2026-09-10 sans
    # renommer une seule expérience déjà archivée.
    assert N.abreger_modele("gemini-3.1-flash-lite") == "gemini-31-fl"
    assert N.abreger_modele("gemini-3.5-flash-lite") == "gemini-35-fl"
    assert N.abreger_modele("mistral-small-latest") == "mistral-s"
    assert N.abreger_modele("qwen/qwen3.6-27b") == "qwen36-27b"
    assert N.abreger_modele("gpt-oss-120b") == "gpt-oss-120b"
    assert N.abreger_modele("Qwen/Qwen2.5-32B-Instruct-AWQ") == "qwen25-32b"


def test_n4_modele_inconnu_donne_un_slug_court_et_non_vide():
    slug = N.abreger_modele("acme/foo-bar-9b-latest")
    assert slug and len(slug) <= N.BUDGET_MODELE
    assert N.abreger_modele("") == ""


# ── N5 : le prompt ne compte que pour un décideur qui en lit un ──────────────


def test_n5_prompt_absent_hors_passerelle():
    # C'était le défaut de `Light_GBM` : une variante affichée qui ne décidait rien.
    assert "minper" not in N.nom_canonique(exp(decideur__type="modele"))
    passerelle = exp(
        decideur__type="passerelle", decideur__modele="mistral-small-latest"
    )
    assert "minper" in N.nom_canonique(passerelle)


def test_n5_variante_absente_se_nomme_actif():
    d = exp(decideur__type="passerelle", decideur__modele="mistral-small-latest")
    d["gabarit"]["variante"] = None
    assert N.nom_canonique(d) == "exp_mistral-s_actif_pop-1000_AAMAS_t0_nosim"


# ── N6 : calendrier ─────────────────────────────────────────────────────────


def test_n6_calendrier():
    assert (
        N.nom_canonique(
            exp(
                calendrier={
                    "politique": "aleatoire",
                    "date": "2026-03-16",
                    "graine": 42,
                }
            )
        )
        == "exp_durmin_jtir_pop-1000_AAMAS_nosim"
    )
    assert (
        N.nom_canonique(
            exp(calendrier={"politique": "propre", "date": "2026-03-16", "graine": 42})
        )
        == "exp_durmin_jpers_pop-1000_AAMAS_nosim"
    )
    # Date commune = jour du jeu → muette ; un autre jour se dit. Le segment de calendrier
    # (N6) précède celui de population (premier écart du bloc N7).
    assert N.nom_canonique(exp()) == "exp_durmin_pop-1000_AAMAS_nosim"
    autre = exp(calendrier={"politique": "commune", "date": "2026-03-17", "graine": 42})
    assert N.nom_canonique(autre) == "exp_durmin_j0317_pop-1000_AAMAS_nosim"


# ── N7 : les écarts, et rien que les écarts ─────────────────────────────────


def test_n7_defauts_muets():
    """Tous les paramètres à leur valeur de référence : seule la population parle.

    La cohorte n'est PAS un défaut (R18) : il n'existe plus de substrat implicite, donc même
    la définition la plus banale annonce sur quelle population elle a été mesurée.
    """
    assert N.nom_canonique(exp()) == "exp_durmin_pop-1000_AAMAS_nosim"


@pytest.mark.parametrize(
    "changement,attendu",
    [
        ({"regroupement": {"parallelisme": 16}}, "exp_durmin_pop-1000_AAMAS_p16_nosim"),
        ({"memoire": True}, "exp_durmin_pop-1000_AAMAS_mem_nosim"),
        ({"horizon_jours": 5}, "exp_durmin_pop-1000_AAMAS_h5j_nosim"),
        ({"max_candidats": 10}, "exp_durmin_pop-1000_AAMAS_c10_nosim"),
        ({"attente_max_s": 300}, "exp_durmin_pop-1000_AAMAS_a300_nosim"),
        ({"graine_ordre": 7}, "exp_durmin_pop-1000_AAMAS_go7_nosim"),
        ({"graine_tirage": 7}, "exp_durmin_pop-1000_AAMAS_gt7_nosim"),
        (
            {"calendrier": {"politique": "commune", "date": "2026-03-16", "graine": 7}},
            "exp_durmin_pop-1000_AAMAS_gc7_nosim",
        ),
        (
            {"decideur__type": "aleatoire", "decideur__graine": 7},
            "exp_alea_pop-1000_AAMAS_gd7_nosim",
        ),
    ],
)
def test_n7_un_ecart_un_segment(changement, attendu):
    # La population ouvre le bloc N7 : tout écart nommé ci-dessous se place APRÈS elle.
    assert N.nom_canonique(exp(**changement)) == attendu


def test_n7_population_nommee_sans_son_prefixe_commun():
    """Une autre cohorte donne un autre segment — c'est tout l'objet de R18.

    `abreger_population` retire `population_`, que toutes les cohortes partagent et qui ne
    distingue donc rien, avant de tronquer à 16 : ce qui reste porte la taille et la
    version. Ici le jeu, resté celui de la cohorte de référence, ne suit plus la convention
    `<population>_<AAAAMMJJ>` : le jour du jeu devient inconnu, donc la date (`j0316`) et le
    nom du jeu entrent à leur tour dans le nom — un désaccord substrat/jeu doit se voir.
    """
    d = exp(population={"chemin": "/data/eqasim-output/population_10000_v2"})
    nom = N.nom_canonique(d)
    # Le segment du jeu garde sa DATE, qui est tout son pouvoir distinctif. Un tronquage par
    # la tête rendait `population_1000_` pour `…_20260316` comme pour `…_20260317` : deux jeux
    # différents, un seul nom d'expérience. `abreger_jeu` retire le préfixe commun puis coupe
    # par la QUEUE — le même remède que `abreger_population`, appliqué au même défaut.
    assert nom == "exp_durmin_j0316_pop-10000_v2_jeu-0_AAMAS_20260316_nosim"
    assert N.MOTIF_NOM.match(nom)


def test_n7_evenements_et_tolerances():
    ev = exp(
        evenements=[
            {"type": "incident", "jour": 1, "heure_debut": "08:00", "description": "x"},
            {
                "type": "information",
                "jour": 2,
                "heure_debut": "09:00",
                "description": "y",
            },
        ]
    )
    assert "ev2" in N.nom_canonique(ev)
    tol = exp(tolerances_horaires={**N.TOLERANCES_REFERENCE, "car": "insensible"})
    nom = N.nom_canonique(tol)
    assert "tol-" in nom and nom == N.nom_canonique(
        tol
    )  # empreinte stable d'un appel à l'autre
    # Les deux écritures d'une même tolérance ne sont pas un écart.
    equivalent = exp(
        tolerances_horaires={
            **N.TOLERANCES_REFERENCE,
            "transit": {"type": "pas", "pas_min": 10},
        }
    )
    assert "tol-" not in N.nom_canonique(equivalent)


def test_n7_jeu_hors_convention_se_nomme():
    # Hors convention `<population>_<AAAAMMJJ>`, le jour du jeu est inconnu : le jeu ET la
    # date entrent dans le nom, sinon deux jeux gelés différents se confondraient. Le
    # segment de population reste en tête du bloc N7, devant celui du jeu.
    d = exp(jeu={"nom": "population_1000_AAMAS_gele_v5", "dossier": None})
    assert N.nom_canonique(d) == "exp_durmin_j0316_pop-1000_AAMAS_jeu-gele_v5_nosim"


# ── N9 : le nom est utilisable comme dossier et comme EXP= ──────────────────


def test_n9_le_nom_satisfait_le_motif():
    for d in (
        exp(),
        exp(decideur__type="passerelle", decideur__modele="qwen/qwen3.6-27b"),
        exp(population={"chemin": "/data/eqasim-output/pop lente; rm -rf"}),
    ):
        nom = N.nom_canonique(d)
        assert N.MOTIF_NOM.match(nom), nom
        assert len(nom) <= N.LONGUEUR_MAX


def test_n9_mode_inconnu_refuse():
    with pytest.raises(N.NommageImpossible, match="mode"):
        N.nom_canonique(exp(mode="turbo"))


# ── N10 : collision ─────────────────────────────────────────────────────────


def test_n10_definition_identique_reutilise_le_nom(tmp_path):
    ecrire(tmp_path, "exp_durmin_pop-1000_AAMAS_nosim", exp())
    a = N.attribuer_nom(exp(nom="autre-chose"), tmp_path)
    assert a.nom == "exp_durmin_pop-1000_AAMAS_nosim"
    assert a.reutilise == "exp_durmin_pop-1000_AAMAS_nosim"
    assert a.indice == 1


def test_n10_definition_differente_prend_un_indice(tmp_path):
    # Deux définitions que la grammaire abrège pareil : seules leurs tolérances diffèrent…
    ecrire(tmp_path, "exp_durmin_pop-1000_AAMAS_nosim", exp())
    autre = exp(attente_max_s=120, max_candidats=6)
    autre["gabarit"]["categorie"] = "itinary_solo"  # même nom composé, autre définition
    a = N.attribuer_nom(autre, tmp_path)
    assert a.nom == "exp_durmin_pop-1000_AAMAS_nosim_2"
    assert a.reutilise is None
    assert a.voisins == ["exp_durmin_pop-1000_AAMAS_nosim"]
    ecrire(tmp_path, "exp_durmin_pop-1000_AAMAS_nosim_2", autre)
    troisieme = copy.deepcopy(autre)
    troisieme["gabarit"]["categorie"] = "itinary_duo"
    assert (
        N.attribuer_nom(troisieme, tmp_path).nom == "exp_durmin_pop-1000_AAMAS_nosim_3"
    )


def test_n10_signature_ignore_la_seule_identite():
    a, b = exp(nom="un"), exp(nom="deux")
    b["derive_de"], b["executions_connues"] = "un", ["2026-09-08_05_00_00"]
    assert N.signature(a) == N.signature(b)
    assert N.signature(exp(memoire=True)) != N.signature(exp())


# ── N11 : l'indice ne tombe jamais ──────────────────────────────────────────


def test_n11_indice_conserve_quand_le_nom_est_long(tmp_path, monkeypatch):
    longue = "exp_" + "a" * (N.LONGUEUR_MAX - 4)
    prises = {longue: "une-autre-signature"}
    monkeypatch.setattr(N, "nom_canonique", lambda _exp: longue)
    a = N.attribuer_nom(exp(), tmp_path, existantes=prises)
    assert a.nom.endswith("_2")
    assert len(a.nom) <= N.LONGUEUR_MAX


# ── N12/N13 : le fichier est autoritaire, `definir` le vérifie ──────────────


def test_n13_verifier_nom():
    assert N.verifier_nom(exp(nom="exp_durmin_pop-1000_AAMAS_nosim")) is None
    assert (
        N.verifier_nom(exp(nom="exp_durmin_pop-1000_AAMAS_nosim_2")) is None
    )  # indice de collision accepté
    assert (
        N.verifier_nom(exp(nom="Mon_Experience")) == "exp_durmin_pop-1000_AAMAS_nosim"
    )


def test_n12_le_nom_ecrit_est_autoritaire(tmp_path):
    """Un nom historique reste lu tel quel : le nommage ne renomme rien de ce qui existe.

    Il occupe son chemin sans occuper le nom canonique : une nouvelle définition identique
    prend donc le nom canonique, libre, et le dossier historique n'est pas touché.
    """
    ecrire(tmp_path, "un_nom_historique", exp())
    prises = N.definitions_existantes(tmp_path)
    assert prises["un_nom_historique"] == N.signature(exp())
    a = N.attribuer_nom(exp(), tmp_path)
    assert a.nom == "exp_durmin_pop-1000_AAMAS_nosim"
    assert a.reutilise is None
    assert (tmp_path / "un_nom_historique" / "experience.yaml").is_file()
