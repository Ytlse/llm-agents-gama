"""Ticket 091 — on ne réutilise une mémoire que si c'est la même expérience.

Contrat : `specs/ticket_091/tests.md`.

Avant ce ticket, un point de reprise ne portait ni modèle, ni prompt, ni population, ni choc, et
la reprise suivait le lien `experiments/current` — qui a pointé deux fois le 2026-09-16 sur un run
autre que celui qu'on croyait.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from urban_mobility_agents.utils import identite_run as I

RACINE = Path(__file__).resolve().parents[1]


def _reglages(**surcharges):
    base = {
        "modele": "gemini-3.1-flash-lite",
        "instances": ["google_gemini31_key1", "google_gemini31_key2"],
        "variante": "prompt_expert_05",
        "population": "/data/population_5.json",
        "ltm": True,
        "reflexion": True,
        "graine_tirage": 42,
        "graine_ordre": 42,
        "graine_meteo": 42,
        "cache": False,
    }
    base.update(surcharges)
    return SimpleNamespace(
        llm=SimpleNamespace(
            instances_admises=base["instances"],
            providers={
                nom: SimpleNamespace(default_model=base["modele"]) for nom in base["instances"]
            },
        ),
        agent=SimpleNamespace(
            llm_params={"prompt_variant": base["variante"]},
            long_term_memory_enabled=base["ltm"],
            long_term_self_reflect_enabled=base["reflexion"],
            mode_draw_seed=base["graine_tirage"],
            option_order_seed=base["graine_ordre"],
            weather_draw_seed=base["graine_meteo"],
        ),
        data=SimpleNamespace(population_file=base["population"]),
        cache=SimpleNamespace(enabled=base["cache"]),
    )


class TestCeQueLIdentiteRetient:
    def test_B1_a_B7_les_champs_comparables_y_sont(self):
        ident = I.composer(_reglages(), empreinte_choc="abc123")
        assert ident["modeles_admis"] == ["gemini-3.1-flash-lite"]
        assert ident["instances_admises"] == ["google_gemini31_key1", "google_gemini31_key2"]
        assert ident["variante_prompt"] == "prompt_expert_05"
        assert ident["population"] == "/data/population_5.json"
        assert ident["memoire_longue"] is True and ident["auto_reflexion"] is True
        assert ident["choc"] == "abc123"
        assert (ident["graine_tirage"], ident["graine_ordre"], ident["graine_meteo"]) == (42, 42, 42)
        assert ident["cache_decisions"] is False

    def test_B5_sans_choc_le_champ_dit_aucun(self):
        assert I.composer(_reglages())["choc"] == "aucun"

    def test_les_instances_sont_triees(self):
        """Deux listes de même contenu dans un ordre différent sont la MÊME expérience."""
        a = I.composer(_reglages(instances=["b", "a"]))
        b = I.composer(_reglages(instances=["a", "b"]))
        assert I.differences(a, b) == []

    def test_B8_l_heure_et_les_compteurs_ne_font_jamais_refuser(self, tmp_path):
        ident = I.composer(_reglages())
        I.ecrire(tmp_path, {**ident, "ecrit_le": "hier", "compteurs": {"agents": 5}})
        I.verifier(tmp_path, {**ident, "ecrit_le": "aujourd'hui", "compteurs": {"agents": 9}})


class TestLeRefus:
    def test_A5_identites_identiques_la_reprise_a_lieu(self, tmp_path):
        ident = I.composer(_reglages())
        I.ecrire(tmp_path, ident)
        I.verifier(tmp_path, ident)  # ne lève pas

    def test_A6_une_difference_est_nommee(self, tmp_path):
        I.ecrire(tmp_path, I.composer(_reglages()))
        with pytest.raises(I.IdentiteIncompatible) as err:
            I.verifier(tmp_path, I.composer(_reglages(variante="prompt_minimal_02")))
        assert "variante de prompt" in str(err.value)
        assert "prompt_expert_05" in str(err.value) and "prompt_minimal_02" in str(err.value)

    def test_A7_toutes_les_differences_sont_nommees(self, tmp_path):
        """Corriger un champ pour buter sur le suivant coûterait un lancement par écart."""
        I.ecrire(tmp_path, I.composer(_reglages()))
        with pytest.raises(I.IdentiteIncompatible) as err:
            I.verifier(
                tmp_path,
                I.composer(_reglages(variante="autre", modele="mistral-small", cache=True)),
            )
        msg = str(err.value)
        assert "variante de prompt" in msg and "modèle" in msg and "cache de décisions" in msg

    def test_un_modele_derive_des_instances_discrimine_vraiment(self):
        """Un champ toujours vide donnerait l'illusion d'une vérification : celui-ci varie."""
        a = I.composer(_reglages(modele="gemini-3.1-flash-lite"))
        b = I.composer(_reglages(modele="gemini-3.5-flash-lite"))
        assert a["modeles_admis"] != b["modeles_admis"]
        assert any("modèle" in d for d in I.differences(a, b))

    def test_un_choc_deplace_fait_refuser(self, tmp_path):
        """Le cas vécu le 2026-09-16 : déplacer les jours du choc change l'expérience."""
        I.ecrire(tmp_path, I.composer(_reglages(), empreinte_choc="4c90634a380e"))
        with pytest.raises(I.IdentiteIncompatible) as err:
            I.verifier(tmp_path, I.composer(_reglages(), empreinte_choc="c6d1f2a09b77"))
        assert "choc" in str(err.value)

    def test_C4_une_identite_absente_fait_refuser(self, tmp_path):
        """Supposer l'égalité en l'absence de preuve est exactement le défaut corrigé."""
        with pytest.raises(I.IdentiteIncompatible) as err:
            I.verifier(tmp_path, I.composer(_reglages()))
        assert "identité" in str(err.value)

    def test_C5_une_identite_illisible_fait_refuser(self, tmp_path):
        I.chemin(tmp_path).write_text("{ ceci n'est pas du json", encoding="utf-8")
        with pytest.raises(I.IdentiteIncompatible):
            I.verifier(tmp_path, I.composer(_reglages()))


class TestLEmpreinteDuChoc:
    """Le registre de chocs n'existe qu'au /init de GAMA, après l'écriture de l'identité :
    interroger le registre rendait « aucun » même sous choc déclaré (constaté le 2026-09-17
    sur le run 2026-09-17_06_24)."""

    def _reglages_avec_choc(self, tmp_path, contenu="choc: c6\nlibelle: x\n"):
        f = tmp_path / "c6.yaml"
        f.write_text(contenu, encoding="utf-8")
        r = _reglages()
        r.chocs = SimpleNamespace(enabled=True, fichier=str(f))
        return r, f

    def test_un_choc_declare_donne_une_empreinte_pas_aucun(self, tmp_path):
        r, _ = self._reglages_avec_choc(tmp_path)
        assert I.composer(r)["choc"] not in ("aucun", "")

    def test_deux_chocs_differents_donnent_deux_identites_differentes(self, tmp_path):
        """Déplacer les jours d'un choc doit faire refuser la reprise."""
        r1, f = self._reglages_avec_choc(tmp_path, "choc: c6\njours:\n  - jour: 8\n")
        e1 = I.composer(r1)
        f.write_text("choc: c6\njours:\n  - jour: 9\n", encoding="utf-8")
        assert I.composer(r1)["choc"] != e1["choc"]

    def test_sans_choc_le_champ_dit_aucun(self, tmp_path):
        r = _reglages()
        r.chocs = SimpleNamespace(enabled=False, fichier=None)
        assert I.composer(r)["choc"] == "aucun"

    def test_un_choc_declare_mais_introuvable_ne_dit_pas_aucun(self, tmp_path):
        """Sinon une expérience sous choc et une sans passeraient pour la même."""
        r = _reglages()
        r.chocs = SimpleNamespace(enabled=True, fichier=str(tmp_path / "absent.yaml"))
        assert I.composer(r)["choc"] != "aucun"

    # ── La clé du ticket 100 (2026-09-22) ────────────────────────────────────────────────
    # `_empreinte_du_choc` ne lisait QUE `reglages.chocs`. Depuis le ticket 100, `make run`
    # écrit la clé `evenements:` dans config.yaml — la forme canonique — et l'empreinte rendait
    # « aucun » SUR UN BRAS TRAITÉ. Son identité devenait celle de son témoin, ce que le
    # docstring de la fonction donne pour la chose à ne pas faire. Trouvé sur la campagne c3,
    # vingt minutes après son lancement.

    def test_la_cle_evenements_du_ticket_100_donne_une_empreinte(self, tmp_path):
        f = tmp_path / "c3.yaml"
        f.write_text("evenement: c3\njours:\n  - jour: 12\n", encoding="utf-8")
        r = _reglages()
        r.chocs = SimpleNamespace(enabled=False, fichier=None)
        r.evenements = SimpleNamespace(enabled=True, fichier=str(f))
        assert I.composer(r)["choc"] not in ("aucun", "")

    def test_un_bras_traite_ne_porte_jamais_la_meme_identite_que_son_temoin(self, tmp_path):
        """Le cas qui a échappé : la campagne d'attribution, deux bras appariés."""
        f = tmp_path / "c3.yaml"
        f.write_text("evenement: c3\njours:\n  - jour: 12\n", encoding="utf-8")

        traite = _reglages()
        traite.chocs = SimpleNamespace(enabled=False, fichier=None)
        traite.evenements = SimpleNamespace(enabled=True, fichier=str(f))

        temoin = _reglages()
        temoin.chocs = SimpleNamespace(enabled=False, fichier=None)
        temoin.evenements = SimpleNamespace(enabled=False, fichier=None)

        assert I.composer(temoin)["choc"] == "aucun"
        assert I.composer(traite)["choc"] != I.composer(temoin)["choc"]

    def test_la_cle_evenements_prime_sur_la_cle_chocs(self, tmp_path):
        """Même ordre que `_declaration_demandee()` : ce qui est JOUÉ est ce qui est enregistré."""
        neuf, vieux = tmp_path / "neuf.yaml", tmp_path / "vieux.yaml"
        neuf.write_text("evenement: c3\njours:\n  - jour: 12\n", encoding="utf-8")
        vieux.write_text("choc: c6\njours:\n  - jour: 8\n", encoding="utf-8")

        r = _reglages()
        r.evenements = SimpleNamespace(enabled=True, fichier=str(neuf))
        r.chocs = SimpleNamespace(enabled=True, fichier=str(vieux))
        empreinte_des_deux = I.composer(r)["choc"]

        seul_le_neuf = _reglages()
        seul_le_neuf.evenements = SimpleNamespace(enabled=True, fichier=str(neuf))
        seul_le_neuf.chocs = SimpleNamespace(enabled=False, fichier=None)
        assert empreinte_des_deux == I.composer(seul_le_neuf)["choc"]

    def test_l_ancienne_cle_reste_lue_quand_elle_est_seule(self, tmp_path):
        """Une campagne lancée sous le ticket 079 doit garder une identité valide."""
        f = tmp_path / "c6.yaml"
        f.write_text("choc: c6\njours:\n  - jour: 8\n", encoding="utf-8")
        r = _reglages()
        r.evenements = SimpleNamespace(enabled=False, fichier=None)
        r.chocs = SimpleNamespace(enabled=True, fichier=str(f))
        assert I.composer(r)["choc"] not in ("aucun", "")


class TestEcriture:
    def test_C1_l_identite_est_ecrite(self, tmp_path):
        assert I.ecrire(tmp_path, I.composer(_reglages())) is True
        assert json.loads(I.chemin(tmp_path).read_text())["variante_prompt"] == "prompt_expert_05"

    def test_C3_une_reprise_ne_reecrit_pas_l_identite(self, tmp_path):
        """C'est la référence contre laquelle on compare : la réécrire ferait disparaître
        l'écart qu'on cherche à détecter."""
        I.ecrire(tmp_path, I.composer(_reglages()))
        assert I.ecrire(tmp_path, I.composer(_reglages(variante="autre"))) is False
        assert json.loads(I.chemin(tmp_path).read_text())["variante_prompt"] == "prompt_expert_05"


class TestLaChaineEstBranchee:
    def _src(self, rel: str) -> str:
        return (RACINE / rel).read_text(encoding="utf-8")

    def test_A1_sans_reprise_nommee_rien_n_est_restaure(self):
        src = self._src("handle/application.py")
        assert "REPRISE_RUN" in src, "l'autorisation de reprise doit être lue au démarrage"
        assert "identite_run" in src, "l'identité doit être vérifiée avant toute restauration"

    def test_A3_le_workdir_est_resolu_par_le_nom(self):
        src = self._src("settings.py")
        assert "REPRISE_RUN" in src, (
            "le répertoire du run repris doit être résolu par son NOM, pas par le lien "
            "`current` — qui a pointé deux fois sur un autre run le 2026-09-16"
        )

    def test_C2_l_identite_est_recopiee_dans_le_point_de_reprise(self):
        assert "identite_run" in self._src("urban_mobility_agents/utils/reprise.py")
