"""Ticket 093, lot 1 — choisir des personas dont les décisions sont observables.

Contrat : `specs/ticket_093/tests.md`, famille A.

Trois personas sur les cinq du run `2026-09-16_15_58` n'apportent rien : deux n'ont qu'un seul
itinéraire proposé une fois sur deux, le troisième ne vit que 19 trajets. Le critère de ce lot est
mesurable AVANT le run, sur une journée de référence — donc reproductible, et opposable.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.data.population import selectionner_personas_mesurables as S

RACINE = next(
    a
    for a in Path(__file__).resolve().parents
    if (a / "scripts" / "synthesis").is_dir()
)

# Run de référence du ticket : 234 candidats, et 920187 y compte 15 trajets. Il n'est pas
# versionné (`data/experiences/*` est ignoré), d'où le saut plutôt qu'un échec ailleurs.
#
# DEPUIS LE TICKET 098, IL N'EST PLUS LÀ DU TOUT : il a été décidé sur l'ancien jeu v6 EN, et
# tout ce jeu est passé en archive froide. Les deux tests qui s'appuient dessus sautent donc
# désormais toujours. Le chemin reste écrit sous `data/` À DESSEIN — le pointer vers l'archive
# reviendrait à la référencer, ce qu'elle interdit.
#
# Ce saut n'est PAS la solution, c'est le constat en attendant une décision (cf. ticket 098).
# Rejouer le même critère sur la contrepartie du jeu corrigé
# (`…_EN_c_t0_nosim/executions/2026-09-17_07_34_55`) donne des chiffres DIFFÉRENTS :
#   - 246 candidats et non 234 ;
#   - 920187 tient (15 trajets, 9 en marche) ;
#   - mais 41275 ne fait plus qu'un seul mode et CESSE d'être candidat — or c'est précisément
#     lui qui porte la démonstration du test A5bis.
# Repointer ce chemin sans trancher réécrirait donc en silence les chiffres que le ticket 093
# cite et que `data/population/population_10_mesurables_093/MANIFEST.yaml` scelle
# (`run_de_reference`, `candidats: 234`). La sélection des 10 personas mesurables doit être
# re-dérivée sur le substrat corrigé, et le MANIFEST réécrit avec elle. C'est une décision
# scientifique, pas un ajustement de test.
RUN_REFERENCE = (
    RACINE
    / "data/experiences"
    / "exp_gemini-35-fl_proexp08_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_t0_nosim"
    / "executions/2026-09-15_12_38_15"
)

MOTIF_SAUT = (
    "run de référence absent : gelé en archive froide avec l'ancien jeu v6 EN (ticket 098). "
    "La sélection des personas mesurables est à re-dériver sur le jeu corrigé — voir le "
    "commentaire au-dessus de RUN_REFERENCE."
)

COLONNES = [
    "ID Personne",
    "ID Activité",
    "Temps simulé",
    "Heure de départ",
    "Heure de calcul",
    "Mode de transport Choisi",
    "Options présentées",
    "Motifs de déplacement",
]


def _trajet(
    personne, mode, options, *, heure="08:00:00", jour="2026-03-16", activite="a1"
):
    return {
        "ID Personne": personne,
        "ID Activité": activite,
        "Temps simulé": f"{jour} {heure}",
        "Heure de départ": f"{jour} {heure}",
        "Heure de calcul": f"{jour} {heure}",
        "Mode de transport Choisi": mode,
        "Options présentées": str(options),
        "Motifs de déplacement": "work",
    }


def _ecrire_run(dossier: Path, lignes: list[dict]) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    with (dossier / "moves.csv").open("w", newline="", encoding="utf-8") as flux:
        ecrivain = csv.DictWriter(flux, fieldnames=COLONNES)
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    return dossier


def _agent(personne: str) -> dict:
    return {
        "person_id": personne,
        "identity": {
            "traits_json": {"name": f"Agent {personne}", "age": 40},
            "activities": [{"purpose": "work"}, {"purpose": "home"}],
        },
    }


def _ecrire_source(chemin: Path, personnes: list[str]) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps([_agent(p) for p in personnes]), encoding="utf-8")
    return chemin


def _journee_variee(
    personne: str, *, trajets=4, options=5, modes=("Voiture Privée", "Marche")
):
    """Une journée qui satisfait le critère : assez de trajets, des options, plusieurs modes."""
    return [
        _trajet(
            personne,
            modes[i % len(modes)],
            options,
            heure=f"{6 + i:02d}:00:00",
            activite=f"a{i}",
        )
        for i in range(trajets)
    ]


class TestCritere:
    def test_A1_moins_de_quatre_trajets_recale(self, tmp_path):
        run = _ecrire_run(tmp_path / "run", _journee_variee("11195", trajets=3))
        mesures = S.mesurer(run)
        assert mesures["11195"].trajets == 3
        assert not S.est_candidat(mesures["11195"])

    def test_A2_un_seul_trajet_mono_option_recale_quel_que_soit_le_reste(
        self, tmp_path
    ):
        lignes = _journee_variee("42", trajets=30)
        lignes[17]["Options présentées"] = "1"
        run = _ecrire_run(tmp_path / "run", lignes)
        mesure = S.mesurer(run)["42"]
        assert mesure.trajets == 30 and mesure.options_min == 1
        assert not S.est_candidat(mesure)

    def test_A3_un_seul_mode_recale_meme_avec_des_options(self, tmp_path):
        run = _ecrire_run(
            tmp_path / "run",
            _journee_variee("609", trajets=8, options=3, modes=("Voiture Privée",)),
        )
        mesure = S.mesurer(run)["609"]
        assert mesure.options_min == 3 and len(mesure.modes) == 1
        assert not S.est_candidat(mesure)

    def test_A4_les_trois_conditions_reunies_font_un_candidat(self, tmp_path):
        run = _ecrire_run(tmp_path / "run", _journee_variee("920187", trajets=15))
        assert S.est_candidat(S.mesurer(run)["920187"])

    def test_A4bis_le_critere_ne_juge_pas_les_modes_proposes_mais_les_modes_CHOISIS(
        self, tmp_path
    ):
        """Un agent à qui l'on propose tout et qui prend toujours la voiture n'est pas candidat.

        C'est le cas de 609 et 41275 : leurs « décisions » se voient, mais elles ne varient pas.
        """
        run = _ecrire_run(
            tmp_path / "run",
            _journee_variee("41275", trajets=6, options=9, modes=("Voiture Privée",)),
        )
        assert not S.est_candidat(S.mesurer(run)["41275"])

    @pytest.mark.skipif(
        not (RUN_REFERENCE / "moves.csv").is_file(),
        reason=MOTIF_SAUT,
    )
    def test_A5_le_run_de_reference_retient_bien_234_candidats(self):
        mesures = S.mesurer(RUN_REFERENCE)
        candidats = [p for p, m in mesures.items() if S.est_candidat(m)]
        assert len(candidats) == 234
        # Les chiffres que le ticket cite, vérifiés à la source.
        assert mesures["920187"].trajets == 15
        assert dict(mesures["920187"].modes)["walking"] == 9
        # 609 (voiture seule, 3 options figées) et 11195 (2 trajets) sont recalés PAR LE
        # CRITÈRE, pas par décret.
        for recale in ("609", "11195"):
            assert not S.est_candidat(mesures[recale])
        # Les deux conservés passent le critère : leur conservation n'est pas un passe-droit.
        for conserve in ("899549", "616478"):
            assert S.est_candidat(mesures[conserve])

    @pytest.mark.skipif(
        not (RUN_REFERENCE / "moves.csv").is_file(),
        reason=MOTIF_SAUT,
    )
    def test_A5bis_le_critere_juge_un_run_et_pas_un_agent_en_soi(self):
        """41275 PASSE le critère sur le run de référence, alors que le ticket le recale.

        Ce n'est pas une contradiction, c'est la portée exacte du critère : sur ce run-là —
        autre modèle, autre variante de prompt — il fait deux modes sur quatre trajets ; sur le
        run à cinq personas du 2026-09-16, il ne fait que de la voiture avec un seul itinéraire
        une fois sur deux. Une sélection ne vaut donc que POUR SON RUN DE RÉFÉRENCE, et le
        MANIFEST doit nommer ce run pour que la sélection reste opposable.
        """
        mesure = S.mesurer(RUN_REFERENCE)["41275"]
        assert S.est_candidat(mesure)
        assert mesure.modes_distincts == 2


class TestChoix:
    def _fixture(self, tmp_path, personnes_candidates, modes_par_agent=None):
        lignes = []
        for personne in personnes_candidates:
            modes = (modes_par_agent or {}).get(personne, ("Voiture Privée", "Marche"))
            lignes += _journee_variee(personne, trajets=6, modes=modes)
        run = _ecrire_run(tmp_path / "run", lignes)
        source = _ecrire_source(tmp_path / "pop.json", personnes_candidates)
        return run, source

    def test_A6_les_conserves_sont_retenus_de_droit_et_leur_critere_est_ecrit(
        self, tmp_path
    ):
        # 616478 ne fait qu'un seul mode : il est conservé, ET le manifeste dit qu'il recale.
        run, source = self._fixture(
            tmp_path,
            ["899549", "616478"] + [str(900 + i) for i in range(12)],
            modes_par_agent={"616478": ("Marche",)},
        )
        retenus = S.choisir(
            S.mesurer(run),
            json.loads(source.read_text()),
            conserver=["899549", "616478"],
            combien=10,
        )
        par_id = {r.person_id: r for r in retenus}
        assert {"899549", "616478"} <= set(par_id)
        assert par_id["899549"].passe_le_critere is True
        assert par_id["616478"].passe_le_critere is False
        assert par_id["616478"].motif == "conservé"

    def test_A7_dix_agents_et_les_modes_dominants_couverts(self, tmp_path):
        modes = {
            "1001": ("Voiture Privée", "Marche"),
            "1002": ("Marche", "Transports_collectifs"),
            "1003": ("Transports_collectifs", "Marche"),
            "1004": ("Vélo", "Marche"),
        }
        run, source = self._fixture(
            tmp_path,
            list(modes) + [str(2000 + i) for i in range(10)],
            modes_par_agent=modes,
        )
        retenus = S.choisir(
            S.mesurer(run), json.loads(source.read_text()), conserver=[], combien=10
        )
        assert len(retenus) == 10
        dominants = {r.mode_dominant for r in retenus}
        assert {"car", "walking", "public_transport", "cycling"} <= dominants

    def test_A8_deux_executions_rendent_la_meme_liste_dans_le_meme_ordre(
        self, tmp_path
    ):
        run, source = self._fixture(tmp_path, [str(3000 + i) for i in range(14)])
        population = json.loads(source.read_text())
        mesures = S.mesurer(run)
        premier = [
            r.person_id
            for r in S.choisir(mesures, population, conserver=[], combien=10)
        ]
        second = [
            r.person_id
            for r in S.choisir(mesures, population, conserver=[], combien=10)
        ]
        assert premier == second

    def test_A9_les_agents_sont_recopies_tels_quels(self, tmp_path):
        run, source = self._fixture(tmp_path, [str(4000 + i) for i in range(12)])
        population = json.loads(source.read_text())
        retenus = S.choisir(S.mesurer(run), population, conserver=[], combien=10)
        par_id = {str(p["person_id"]): p for p in population}
        for retenu in retenus:
            assert retenu.persona == par_id[retenu.person_id]

    def test_A12_a_mode_dominant_egal_le_plus_observable_passe_avant(self, tmp_path):
        """Le critère est un plancher, pas un objectif.

        Trier par identifiant donnait dix agents minimalement conformes — quatre trajets, deux
        modes — et faisait entrer `41275`, celui-là même que le ticket écarte pour ne rien
        apprendre. Un agent qui décide quinze fois offre quinze prises à la mémoire.
        """
        lignes = _journee_variee("9001", trajets=4)  # conforme, mais minimal
        lignes += _journee_variee(
            "9002", trajets=12, modes=("Voiture Privée", "Marche", "Vélo")
        )  # riche
        run = _ecrire_run(tmp_path / "run", lignes)
        source = _ecrire_source(tmp_path / "pop.json", ["9001", "9002"])
        retenus = S.choisir(
            S.mesurer(run), json.loads(source.read_text()), conserver=[], combien=1
        )
        assert [r.person_id for r in retenus] == ["9002"]

    def test_A10_moins_de_candidats_que_demande_refuse_au_lieu_de_completer(
        self, tmp_path
    ):
        run, source = self._fixture(tmp_path, [str(5000 + i) for i in range(4)])
        with pytest.raises(SystemExit) as refus:
            S.choisir(
                S.mesurer(run), json.loads(source.read_text()), conserver=[], combien=10
            )
        assert "4" in str(refus.value) and "10" in str(refus.value)

    def test_A10bis_un_conserve_absent_de_la_source_refuse_en_le_nommant(
        self, tmp_path
    ):
        run, source = self._fixture(tmp_path, [str(6000 + i) for i in range(12)])
        with pytest.raises(SystemExit) as refus:
            S.choisir(
                S.mesurer(run),
                json.loads(source.read_text()),
                conserver=["999999"],
                combien=10,
            )
        assert "999999" in str(refus.value)


class TestManifeste:
    def test_A11_le_manifeste_porte_le_critere_le_run_et_les_chiffres_mesures(
        self, tmp_path
    ):
        lignes = []
        for personne in [str(7000 + i) for i in range(12)]:
            lignes += _journee_variee(personne, trajets=6)
        run = _ecrire_run(tmp_path / "run", lignes)
        source = _ecrire_source(
            tmp_path / "pop.json", [str(7000 + i) for i in range(12)]
        )
        sortie = tmp_path / "population_10"

        S.ecrire(run, source, sortie, conserver=[], combien=10)

        manifeste = (sortie / "MANIFEST.yaml").read_text(encoding="utf-8")
        assert "run_de_reference" in manifeste
        assert str(S.CRITERE.trajets_min) in manifeste
        assert "trajets: 6" in manifeste
        assert "PAS UN SCEAU" in manifeste.upper()
        produite = json.loads((sortie / "population.json").read_text(encoding="utf-8"))
        assert len(produite) == 10

    def test_A11bis_la_population_ecrite_ne_contient_que_des_agents_de_la_source(
        self, tmp_path
    ):
        personnes = [str(8000 + i) for i in range(12)]
        lignes = []
        for personne in personnes:
            lignes += _journee_variee(personne, trajets=6)
        run = _ecrire_run(tmp_path / "run", lignes)
        source = _ecrire_source(tmp_path / "pop.json", personnes)
        sortie = tmp_path / "population_10"
        S.ecrire(run, source, sortie, conserver=[], combien=10)
        produite = json.loads((sortie / "population.json").read_text(encoding="utf-8"))
        assert {str(p["person_id"]) for p in produite} <= set(personnes)


class TestVerification:
    """Le « scellement » utile à dix agents : le fichier livré est celui que le manifeste décrit.

    Ce n'est PAS un sceau AAMAS — `scripts.AAMAS.seal_population` tire des ménages par strates et
    contrôle treize marges à ± 1 point, ce qui n'a aucun sens à dix agents et n'est pas le but.
    """

    def _produire(self, tmp_path):
        personnes = [str(9000 + i) for i in range(12)]
        lignes = []
        for personne in personnes:
            lignes += _journee_variee(personne, trajets=6)
        run = _ecrire_run(tmp_path / "run", lignes)
        source = _ecrire_source(tmp_path / "pop.json", personnes)
        sortie = tmp_path / "population_10"
        S.ecrire(run, source, sortie, conserver=[], combien=10)
        return sortie

    def test_une_population_intacte_ne_leve_aucune_anomalie(self, tmp_path):
        assert S.verifier(self._produire(tmp_path)) == []

    def test_une_population_modifiee_a_la_main_est_detectee(self, tmp_path):
        """Sans cette vérification, un fichier retouché continuerait de se réclamer du critère."""
        sortie = self._produire(tmp_path)
        agents = json.loads((sortie / "population.json").read_text(encoding="utf-8"))
        (sortie / "population.json").write_text(
            json.dumps(agents[:9]), encoding="utf-8"
        )
        anomalies = S.verifier(sortie)
        assert any("a changé" in a for a in anomalies)
        assert any("9 agent(s)" in a for a in anomalies)

    def test_une_source_disparue_est_dite_plutot_que_supposee_identique(self, tmp_path):
        sortie = self._produire(tmp_path)
        (tmp_path / "pop.json").unlink()
        assert any("plus rejouable" in a for a in S.verifier(sortie))

    def test_un_dossier_incomplet_le_dit_au_lieu_de_passer(self, tmp_path):
        vide = tmp_path / "rien"
        vide.mkdir()
        assert S.verifier(vide)


def test_la_population_du_ticket_est_VERSIONNEE(tmp_path):
    """Le run de référence vit sous `data/experiences/`, qui est ignoré par git.

    Hors git, la population de dix n'existerait que sur la machine qui l'a produite : la
    sélection ne serait ni rejouable ni vérifiable ailleurs, et son critère resterait théorique.
    """
    gitignore = (RACINE / "data" / ".gitignore").read_text(encoding="utf-8")
    assert "!/population/population_10_mesurables_093/" in gitignore
