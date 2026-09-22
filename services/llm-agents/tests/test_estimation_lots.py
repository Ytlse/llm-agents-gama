"""Du déplacement à la requête : le regroupement entre dans l'estimation de coût.

Le défaut corrigé : `estimer` posait une requête fournisseur par déplacement, alors que la
passerelle en fusionne huit. Repère du ticket 073 § 4 : environ 310 requêtes pour un bras
complet, soit à peu près 0,3 jour de quota — l'ancienne estimation en annonçait 2 500.

Ce que ces tests tiennent, dans l'ordre d'importance :

1. **la prudence ne baisse jamais** — sans exécution archivée comparable, le chiffre qui décide
   redevient exactement celui d'avant la correction (une requête par déplacement) ;
2. les deux unités sont distinctes et nommées dans la sortie ;
3. une mesure archivée qui ne décrit pas le run est écartée, avec son motif.
"""

from __future__ import annotations

import json

import pytest
import yaml
from experiences import lots as L

# ── Plafond dérivé ───────────────────────────────────────────────────────────

PROVIDERS = {
    "k1": {"rpm_limit": 15, "tpm_limit": 250_000},  # 250000/3000=83, borné par rpm → 15
    "k2": {"rpm_limit": 15, "tpm_limit": 250_000},
    "petite": {"rpm_limit": 60, "tpm_limit": 6_000},  # 6000/3000 = 2
}


def test_plafond_derive_de_la_formule_de_la_passerelle():
    """Sans `/health`, la formule de `llm_gateway` est rejouée sur providers.yaml."""
    plafond, source = L.plafond_lot(PROVIDERS, ["k1", "k2"])
    assert plafond == 15
    assert "batch_max_agents=15" in source and "providers.yaml" in source


def test_plafond_pris_sur_la_plus_petite_instance():
    """Le décideur épuise les instances EN SÉRIE : la plus petite capacité finit par servir."""
    plafond, _ = L.plafond_lot(PROVIDERS, ["k1", "petite"])
    assert plafond == 2


def test_la_passerelle_lemporte_sur_le_fichier():
    """`/health` publie la valeur calculée par le conteneur qui sert : c'est elle qui vaut."""
    plafond, source = L.plafond_lot(
        PROVIDERS, ["k1"], etat_passerelle={"k1": {"batch_max_agents": 7}}
    )
    assert plafond == 7 and "passerelle" in source


def test_le_parallelisme_borne_le_lot_sans_simulateur():
    """8 personnes en vol, déplacements sériels : jamais plus de 8 tâches à fusionner."""
    plafond, source = L.plafond_lot(PROVIDERS, ["k1"], parallelisme=8)
    assert plafond == 8 and "parallélisme 8" in source
    # Et il ne borne pas en mode simulateur : GAMA alimente la file, des lots de 15 s'observent.
    assert L.plafond_lot(PROVIDERS, ["k1"], parallelisme=None)[0] == 15


def test_sans_instance_aucun_regroupement_suppose():
    plafond, source = L.plafond_lot(PROVIDERS, [])
    assert plafond == 1 and "aucun regroupement" in source


# ── Mesure sur les exécutions archivées ──────────────────────────────────────

SHA = "a" * 64


def _archiver(
    racine,
    nom,
    *,
    sollicitations,
    requetes=None,
    requetes_jour=None,
    parallelisme=8,
    troncature=False,
    cree_le="2026-09-21T09:00:00+00:00",
    cloture_le="2026-09-21T15:00:00+00:00",
    etat="terminee",
    interruptions=None,
    limite_jour=None,
    epuisee=False,
    sha=SHA,
):
    d = racine / nom / "executions" / "2026-09-21_09_00_00"
    d.mkdir(parents=True)
    (d / "execution.yaml").write_text(
        yaml.safe_dump(
            {
                "cree_le": cree_le,
                "experience": {
                    "regroupement": {"parallelisme": parallelisme},
                    "troncature_15": troncature,
                },
                "empreintes": {"gabarit": {"sha256": sha}},
                "interruptions": interruptions or [],
                "cloture": {"le": cloture_le, "etat": etat},
            }
        ),
        encoding="utf-8",
    )
    compteurs = {"sollicitations": sollicitations}
    if requetes is not None:
        compteurs["requetes"] = {"delta": requetes, "fiable": True}
    if requetes_jour is not None:
        compteurs["quota"] = [
            {
                "instance": "k1",
                "requetes_jour": requetes_jour,
                "limite_jour": limite_jour,
                "epuisee": epuisee,
            }
        ]
    (d / "compteurs.json").write_text(json.dumps(compteurs), encoding="utf-8")
    return d


def _mesure(racine, **kw):
    return L.mesures_archivees(
        SHA, parallelisme=8, troncature=False, plafond=8, dossier_experiences_=racine, **kw
    )


# Le compteur journalier ne vaut comme coût d'un run qu'à trois conditions. Elles ne sont pas
# décoratives : lu sans elles sur l'exécution `2026-09-21_17_00_49`, dont la clé était à 506
# requêtes pour une limite de 500, il annonce 2,4 agents/requête là où le regroupement réel est
# de l'ordre de 8 (ticket 073 § 4). Les réessais et les autres runs du jour gonflent le
# dénominateur — et un facteur trop bas, lui, ne coûte que de la prudence.


def test_execution_non_terminee_ecartee(tmp_path):
    _archiver(tmp_path, "a", sollicitations=2229, requetes_jour=290, etat="epuisee")
    assert _mesure(tmp_path) is None


def test_execution_reprise_ecartee(tmp_path):
    """Une reprise ressert des décisions archivées : ses requêtes ne sont pas les siennes."""
    _archiver(
        tmp_path,
        "a",
        sollicitations=2229,
        requetes_jour=290,
        interruptions=[{"type": "reprise", "instant": "2026-09-21T11:00:00+00:00"}],
    )
    assert _mesure(tmp_path) is None


def test_quota_au_plafond_ecarte(tmp_path):
    """Au plafond, le fournisseur a refusé des requêtes qui ont pourtant été comptées."""
    _archiver(
        tmp_path, "a", sollicitations=2229, requetes_jour=506, limite_jour=500
    )
    assert _mesure(tmp_path) is None


def test_ces_garde_fous_ne_touchent_pas_la_mesure_fiable(tmp_path):
    """Le delta du run se passe de ces conditions : il ne compte que ce run, par construction."""
    _archiver(
        tmp_path,
        "a",
        sollicitations=2229,
        requetes=290,
        etat="epuisee",
        interruptions=[{"type": "reprise"}],
    )
    m = _mesure(tmp_path)
    assert m and m["n"] == 1 and m["fiabilite"] == "mesurée"


def test_mesure_fiable_lue_sur_le_delta_du_run(tmp_path):
    """Le delta des compteurs de la passerelle mesure CE run : c'est la bonne source."""
    _archiver(tmp_path, "exp_a", sollicitations=2442, requetes=318)
    m = _mesure(tmp_path)
    assert m["n"] == 1
    assert m["mediane"] == pytest.approx(7.68, abs=0.01)
    assert m["fiabilite"] == "mesurée"


def test_compteur_journalier_accepte_mais_signale_comme_minore(tmp_path):
    """Faute de delta, le compteur du JOUR sert — il agrège d'autres runs, donc il minore."""
    _archiver(tmp_path, "exp_a", sollicitations=2442, requetes_jour=318)
    m = _mesure(tmp_path)
    assert m["n"] == 1 and m["fiabilite"].startswith("minorée")


def test_rapport_sous_un_ecarte(tmp_path):
    """Moins d'un agent par requête est impossible : le compteur décrit plus que ce run."""
    _archiver(tmp_path, "exp_a", sollicitations=194, requetes_jour=760)
    assert (
        L.mesures_archivees(
            SHA, parallelisme=8, troncature=False, plafond=8, dossier_experiences_=tmp_path
        )
        is None
    )


def test_rapport_au_dela_du_plafond_ecarte(tmp_path):
    """14 agents/requête pour un plafond de 8 : le compteur s'est remis à zéro, pas un record."""
    _archiver(tmp_path, "exp_a", sollicitations=1400, requetes_jour=100)
    m = L.mesures_archivees(
        SHA, parallelisme=8, troncature=False, plafond=8, dossier_experiences_=tmp_path
    )
    assert m is None


def test_fenetre_de_quota_traversee_ecarte_le_compteur_journalier(tmp_path):
    """Run à cheval sur minuit : le compteur n'a pas vu tout le run, le rapport gonfle."""
    _archiver(
        tmp_path,
        "exp_a",
        sollicitations=2442,
        requetes_jour=318,
        cree_le="2026-09-20T22:00:00-07:00",
        cloture_le="2026-09-21T03:00:00-07:00",
    )
    assert (
        L.mesures_archivees(
            SHA, parallelisme=8, troncature=False, plafond=8, dossier_experiences_=tmp_path
        )
        is None
    )


def test_la_fenetre_ne_disqualifie_pas_une_mesure_fiable(tmp_path):
    """Le delta est calculé sur les deux bornes : franchir minuit ne le fausse pas."""
    _archiver(
        tmp_path,
        "exp_a",
        sollicitations=2442,
        requetes=318,
        cree_le="2026-09-20T22:00:00-07:00",
        cloture_le="2026-09-21T03:00:00-07:00",
    )
    m = L.mesures_archivees(
        SHA, parallelisme=8, troncature=False, plafond=8, dossier_experiences_=tmp_path
    )
    assert m and m["n"] == 1


def test_execution_trop_courte_ecartee(tmp_path):
    """Un rapport bâti sur deux requêtes ne mesure rien : on exige dix lots pleins."""
    _archiver(tmp_path, "exp_a", sollicitations=20, requetes=5)
    assert (
        L.mesures_archivees(
            SHA, parallelisme=8, troncature=False, plafond=8, dossier_experiences_=tmp_path
        )
        is None
    )


def test_troncature_differente_non_melangee(tmp_path):
    """Contexte plein et contexte tronqué ne groupent pas pareil : leur moyenne ne décrit ni l'un ni l'autre."""
    _archiver(tmp_path, "plein", sollicitations=2400, requetes=800, troncature=False)
    _archiver(tmp_path, "tronque", sollicitations=2442, requetes=318, troncature=True)
    plein = L.mesures_archivees(
        SHA, parallelisme=8, troncature=False, plafond=8, dossier_experiences_=tmp_path
    )
    tronque = L.mesures_archivees(
        SHA, parallelisme=8, troncature=True, plafond=8, dossier_experiences_=tmp_path
    )
    assert plein["n"] == 1 and plein["mediane"] == pytest.approx(3.0, abs=0.01)
    assert tronque["n"] == 1 and tronque["mediane"] == pytest.approx(7.68, abs=0.01)


# ── Les trois facteurs, et celui qui décide ──────────────────────────────────


def test_sans_mesure_le_facteur_prudent_vaut_un(tmp_path):
    """LA garantie de non-régression : aucune archive ⇒ une requête par déplacement."""
    f = L.facteurs(
        providers=PROVIDERS,
        instances=["k1"],
        parallelisme=8,
        empreinte_gabarit_=SHA,
        dossier_experiences_=tmp_path,
    )
    assert f["prudent"] == 1.0
    assert f["attendu"] == 8.0 and f["plafond"] == 8
    assert L.requetes(2229, f["prudent"]) == 2229


def test_avec_mesures_le_prudent_est_le_minimum(tmp_path):
    """Le minimum, pas la médiane : le chiffre qui décide prend l'exécution la moins groupée."""
    _archiver(tmp_path, "a", sollicitations=2400, requetes=800)  # 3,0
    _archiver(tmp_path, "b", sollicitations=2400, requetes=400)  # 6,0
    f = L.facteurs(
        providers=PROVIDERS,
        instances=["k1"],
        parallelisme=8,
        empreinte_gabarit_=SHA,
        dossier_experiences_=tmp_path,
    )
    assert f["prudent"] == pytest.approx(3.0, abs=0.01)
    assert f["attendu"] == pytest.approx(4.5, abs=0.01)  # médiane des deux
    assert f["plafond"] == 8


def test_ordre_des_trois_chiffres(tmp_path):
    """prudente ≥ attendue ≥ plancher, toujours : sinon l'un des trois ment."""
    _archiver(tmp_path, "a", sollicitations=2442, requetes=318)
    f = L.facteurs(
        providers=PROVIDERS,
        instances=["k1"],
        parallelisme=8,
        empreinte_gabarit_=SHA,
        dossier_experiences_=tmp_path,
    )
    p, a, pl = (
        L.requetes(2229, f["prudent"]),
        L.requetes(2229, f["attendu"]),
        L.requetes(2229, f["plafond"]),
    )
    assert p >= a >= pl


def test_requetes_arrondit_vers_le_haut():
    """Un reste de déplacements part quand même dans une requête."""
    assert L.requetes(10, 3) == 4
    assert L.requetes(0, 8) == 0
    # Un facteur sous 1 ne peut pas créer plus de requêtes que de déplacements.
    assert L.requetes(10, 0.5) == 10


# ── La sortie de `estimer` : deux unités nommées ─────────────────────────────


class _JeuFactice:
    nom = "jeu_t"

    def couverture(self):
        return {"deplacements_couverts": 2229, "deplacements_attendus": 2300}


def _exp_factice(**kw):
    from types import SimpleNamespace

    from experiences.experience import MODE_SANS_SIMULATEUR

    base = {
        "nom": "exp_t",
        "mode": MODE_SANS_SIMULATEUR,
        "troncature_15": False,
        "regroupement": SimpleNamespace(parallelisme=8),
        "gabarit": SimpleNamespace(categorie="itinary_multi_agent", variante=None),
        "decideur": SimpleNamespace(
            type="passerelle", modele="m", portee=None, parametres={"temperature": 0}
        ),
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _moniteur(providers=None, etat=None):
    from experiences.ressources import MoniteurRessources

    providers = providers or {
        "k1": {"default_model": "m", "rpd_limit": 500, "rpm_limit": 15, "tpm_limit": 250_000}
    }
    m = MoniteurRessources(
        list(providers), providers, lecteur=lambda url: etat or {"k1": {"daily_requests": 0}}
    )
    m.rafraichir()
    return m


def test_estimer_distingue_deplacements_et_requetes(tmp_path, monkeypatch):
    """Les deux unités portent des noms différents et des valeurs différentes."""
    from experiences import experience as E

    monkeypatch.setenv("EXPERIENCES_DIR", str(tmp_path))
    _archiver(tmp_path, "a", sollicitations=2442, requetes=318)
    exp = _exp_factice()
    sha = E.empreinte_gabarit("itinary_multi_agent", None)["sha256"]
    for d in tmp_path.glob("*/executions/*/execution.yaml"):
        d.write_text(
            d.read_text(encoding="utf-8").replace(SHA, sha), encoding="utf-8"
        )
    est = E.estimer(
        exp,
        _JeuFactice(),
        moniteur=_moniteur(),
        jetons={"entree": 576, "sortie": 697, "source": "test"},
    )
    assert est["deplacements"]["valeur"] == 2229
    assert est["deplacements"]["unite"] == "déplacement"
    assert est["sollicitations"]["unite"] == "déplacement"  # même unité, nom historique
    assert est["requetes"]["unite"] == "requête fournisseur"
    # 2 229 ÷ 7,68 ≈ 291 requêtes : l'ancien chiffrage en annonçait 2 229.
    assert est["requetes"]["prudente"] < 400
    assert est["requetes"]["prudente"] >= est["requetes"]["attendue"]
    assert est["requetes"]["attendue"] >= est["requetes"]["plancher"]
    assert est["regroupement"]["decide_par"] == "prudent"
    # Les jetons restent par AGENT, et le nouveau champ dit ce que voit le fournisseur.
    assert est["jetons"]["par_sollicitation"]["entree"] == 576
    assert est["jetons"]["par_requete"]["entree"] > 576


def test_estimer_sans_archive_ne_devient_pas_plus_optimiste(tmp_path, monkeypatch):
    """Sans mesure comparable, requêtes prudentes == déplacements : le comportement d'avant."""
    from experiences import experience as E

    monkeypatch.setenv("EXPERIENCES_DIR", str(tmp_path))
    est = E.estimer(
        _exp_factice(),
        _JeuFactice(),
        moniteur=_moniteur(),
        jetons={"entree": 1, "sortie": 1, "source": "test"},
    )
    assert est["requetes"]["prudente"] == est["deplacements"]["valeur"] == 2229
    assert est["quota"]["part"] == pytest.approx(2229 / 500)


def test_estimer_decideur_local_ne_compte_aucune_requete(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from experiences import experience as E

    monkeypatch.setenv("EXPERIENCES_DIR", str(tmp_path))
    exp = _exp_factice(
        decideur=SimpleNamespace(type="aleatoire", modele=None, portee=None, parametres={})
    )
    est = E.estimer(exp, _JeuFactice())
    assert est["deplacements"]["valeur"] == 2229 and est["requetes"]["valeur"] == 0


# ── Les jetons d'une ligne de journal sont ceux du LOT, pas d'un agent ───────


def test_jetons_ramenes_a_lagent_par_la_taille_du_lot(tmp_path, monkeypatch):
    """4 607 jetons pour `batch_..._8` font 576 par agent, pas 4 607."""
    from experiences import experience as E

    monkeypatch.setenv("EXPERIENCES_DIR", str(tmp_path))
    sha = E.empreinte_gabarit("itinary_multi_agent", None)["sha256"]
    d = _archiver(tmp_path, "a", sollicitations=2442, requetes=318, sha=sha)
    # Le vrai fichier est une suite d'objets JSON INDENTÉS, pas du JSONL : un parseur
    # ligne à ligne n'y lisait rien, silencieusement.
    (d / "llm_exchanges.jsonl").write_text(
        "\n".join(
            json.dumps(
                {"task_id": "batch_7cc7ed2c_8", "tokens_in": 4607, "tokens_out": 5576},
                indent=2,
            )
            for _ in range(3)
        ),
        encoding="utf-8",
    )
    j = E.jetons_mesures(tmp_path, sha)
    assert j["entree"] == 575 and j["sortie"] == 697  # 4607/8 et 5576/8
    assert "ramenée" in j["source"]


def test_ligne_sans_taille_de_lot_ignoree_plutot_que_comptee_pour_un(tmp_path, monkeypatch):
    """La compter pour un agent serait exactement l'erreur qu'on corrige."""
    from experiences import experience as E

    monkeypatch.setenv("EXPERIENCES_DIR", str(tmp_path))
    sha = E.empreinte_gabarit("itinary_multi_agent", None)["sha256"]
    d = _archiver(tmp_path, "a", sollicitations=2442, requetes=318, sha=sha)
    (d / "llm_exchanges.jsonl").write_text(
        json.dumps({"task_id": "inconnu", "tokens_in": 4607, "tokens_out": 5576}),
        encoding="utf-8",
    )
    assert E.jetons_mesures(tmp_path, sha) is None


def test_repli_sur_le_nombre_de_reponses_dagents(tmp_path, monkeypatch):
    from experiences import experience as E

    monkeypatch.setenv("EXPERIENCES_DIR", str(tmp_path))
    sha = E.empreinte_gabarit("itinary_multi_agent", None)["sha256"]
    d = _archiver(tmp_path, "a", sollicitations=2442, requetes=318, sha=sha)
    (d / "llm_exchanges.jsonl").write_text(
        json.dumps(
            {"tokens_in": 400, "tokens_out": 200, "response": [{"agent_id": i} for i in range(4)]}
        ),
        encoding="utf-8",
    )
    j = E.jetons_mesures(tmp_path, sha)
    assert j["entree"] == 100 and j["sortie"] == 50


# ── Un jeu non clos ne produit pas de chiffres négatifs (signalé le 2026-09-22) ──


class _JeuEnPreparation:
    """Manifeste sans `attendus` : c'est l'état d'un jeu encore en préparation."""

    nom = "jeu_en_cours"

    def couverture(self):
        return {"deplacements_couverts": 773, "deplacements_attendus": 0}


def test_jeu_non_clos_ne_rend_pas_un_nombre_negatif(tmp_path, monkeypatch):
    """`0 - 773 = -773` s'affichait comme « déplacements non couverts »."""
    from experiences import experience as E

    monkeypatch.setenv("EXPERIENCES_DIR", str(tmp_path))
    est = E.estimer(
        _exp_factice(),
        _JeuEnPreparation(),
        moniteur=_moniteur(),
        jetons={"entree": 1, "sortie": 1, "source": "test"},
    )
    assert est["non_couverts"]["valeur"] is None
    assert "non clos" in est["non_couverts"]["source"]
    # Et le chiffre des déplacements se présente pour ce qu'il est : un avancement.
    assert est["deplacements"]["jeu_clos"] is False
    assert "NON CLOS" in est["deplacements"]["source"]


def test_jeu_clos_soustrait_normalement(tmp_path, monkeypatch):
    from experiences import experience as E

    monkeypatch.setenv("EXPERIENCES_DIR", str(tmp_path))
    est = E.estimer(
        _exp_factice(),
        _JeuFactice(),
        moniteur=_moniteur(),
        jetons={"entree": 1, "sortie": 1, "source": "test"},
    )
    assert est["non_couverts"]["valeur"] == 2300 - 2229
    assert est["deplacements"]["jeu_clos"] is True
