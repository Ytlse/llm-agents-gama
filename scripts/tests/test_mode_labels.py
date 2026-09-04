"""Libellés de mode : rien ne se jette, et un libellé inconnu se voit.

CE QUE CE FICHIER VERROUILLE. Un libellé de mode que la table d'agrégation ne connaît
pas ne lève AUCUNE exception : il sort du dénominateur des parts modales, et les parts
des modes restants montent d'autant. Le chiffre reste plausible. C'est le motif
« l'absence de mesure produit le score parfait », et il s'est produit deux fois de suite
sur le même fil :

* `audit_perimetre.MOVE_MODE_MAP` n'avait pas d'entrée « Train » : depuis le routage du
  TER (16,7 % des itinéraires portent un train), un déplacement en train sortait de
  l'audit des parts modales par un `continue` muet ;
* `scripts/analysis/selected_mode_stats.ipynb` normalisait par un `replace()` sans
  « Train », sans « Deux-roues motorisé » et sans « Autres modes », puis les éliminait
  par `reindex(mode_order)` — sans avertissement, alors que le même carnet avertissait
  (mal) pour une autre colonne.

Trois gardes contre la vacuité : les effectifs sont assertés avant toute boucle, la
table de production (`move_logger._CANONICAL_FR`) est **lue dans sa source** plutôt que
recopiée, et le format de l'alarme est confronté à l'expression régulière de
`scripts/errors.py` — une alarme que `make error` ne relit pas est une alarme inutile.

Lancement : PYTHONPATH=. llm-agents/.venv/bin/python -m pytest scripts/tests/test_mode_labels.py
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from llm_module.core.mode_hierarchy import hierarchy
from scripts.analysis.mode_labels import (
    AGGREGATION, MODE_COLUMN, NON_TRIP, NO_LABEL, SCORED_CATEGORIES,
    SURVEY_CATEGORIES, UNKNOWN, ModeTally, ModeTallyError, aggregation_table,
    alarm_unknown, category_of, check_covers_hierarchy, missing_from,
    normalize_column, normalize_labels, resolve_log_path, tally_labels)

REPO_ROOT = Path(__file__).resolve().parents[2]
MOVE_LOGGER = REPO_ROOT / "llm-agents" / "urban_mobility_agents" / "utils" / "move_logger.py"
ERRORS_SCRIPT = REPO_ROOT / "scripts" / "errors.py"

# Ce que la normalisation rendait AVANT ce module, pour les libellés qu'elle couvrait.
# Non-régression : ces quatre correspondances ne doivent pas bouger, sans quoi tous les
# chiffres déjà publiés changeraient de sens.
NORMALISATION_HISTORIQUE = {
    "Marche": "marche",
    "Voiture Privée": "voiture",
    "Vélo": "velo",
    "Transports_collectifs": "transports_collectifs",
}

# Libellé qui n'existe dans aucune table : le run archivé est ANTÉRIEUR au rail, donc
# l'inconnu se fabrique au lieu d'être attendu des données.
INCONNU = "Trottinette partagée"


# ── Lectures à la source (pas de littéral recopié) ────────────────────────────

def _journal_labels() -> dict[str, str]:
    """Libellés de « Mode de transport Choisi », LUS DANS LEUR SOURCE DE PRODUCTION.

    Depuis le ticket 022, `llm_module.core.mode_hierarchy` est le seul endroit du dépôt
    où ces libellés sont décidés : `move_logger._CANONICAL_FR` les y lit, et n'est plus
    un littéral relisible par AST. On interroge donc la source elle-même — elle
    s'importe sans tirer `settings` (donc sans repointer `experiments/current`), et un
    littéral recopié ici ne tomberait que si l'instrument change, jamais si la
    production change.
    """
    return dict(hierarchy().journal_label)


def _error_regex() -> re.Pattern:
    """`ERROR_RE` de `scripts/errors.py`, lue à la source.

    Le script s'exécute à l'import (il ouvre un journal), donc il ne s'importe pas :
    on extrait le motif de son AST. C'est CE motif que `make error` applique.
    """
    source = ERRORS_SCRIPT.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if (isinstance(node, ast.Assign)
                and any(getattr(t, "id", None) == "ERROR_RE" for t in node.targets)
                and isinstance(node.value, ast.Call)):
            return re.compile(ast.literal_eval(node.value.args[0]))
    raise AssertionError("ERROR_RE introuvable dans scripts/errors.py")


# ── La table couvre le vocabulaire de production ──────────────────────────────

def test_la_table_couvre_tous_les_libelles_du_journal():
    """Un mode ajouté à la hiérarchie sans entrée ici sortirait des parts modales.

    C'est exactement ce qui est arrivé au train : le journal écrivait « Train » depuis
    le routage du TER, `MOVE_MODE_MAP` ne l'a jamais su.
    """
    labels = _journal_labels()
    assert len(labels) >= 9, labels                # garde anti-vacuité
    assert labels.get("rail") == "Train"
    assert labels.get("motorbike") == "Deux-roues motorisé"
    for family, label in labels.items():
        assert label in AGGREGATION, (
            f"« {label} » (famille {family}) est un libellé de journal de la hiérarchie "
            f"mais est absent de mode_labels.AGGREGATION : il sortirait des parts "
            f"modales en silence.")


def test_le_controle_de_couverture_est_vert_et_sait_etre_rouge(monkeypatch):
    """Le contrôle doit être vert AUJOURD'HUI et rouge quand il doit l'être.

    Un contrôle qu'on n'a jamais vu échouer est un contrôle dont on ne sait pas s'il
    peut échouer — le motif de vacuité appliqué aux garde-fous eux-mêmes.
    """
    assert check_covers_hierarchy() == ""
    from scripts.analysis import mode_labels
    sans_train = {k: v for k, v in AGGREGATION.items() if k != "Train"}
    monkeypatch.setattr(mode_labels, "AGGREGATION", sans_train)
    raison = check_covers_hierarchy()
    assert "Train" in raison and "rail" in raison
    assert "AGGREGATION" in raison                 # la raison dit où corriger


def test_lecart_de_couverture_alarme_et_remonte_sur_le_comptage(tmp_path, monkeypatch):
    """Un écart LATENT — invisible dans les données du run — doit quand même crier.

    C'est la forme exacte du défaut corrigé : aucun run archivé ne portait « Train », et
    l'absence de la clé ne se voyait donc nulle part. Le contrôle ne regarde pas les
    données, il regarde la table.
    """
    from scripts.analysis import mode_labels
    monkeypatch.setattr(mode_labels, "AGGREGATION",
                        {k: v for k, v in AGGREGATION.items() if k != "Train"})
    monkeypatch.setattr(mode_labels, "_HIERARCHY_ALARMED", False)
    tally = mode_labels.tally_labels(["Marche"] * 4, source="test", log_dir=tmp_path)
    assert tally.unknown == {}                     # les données, elles, sont propres
    assert "Train" in tally.hierarchy_gap
    journal = (tmp_path / "app.log").read_text(encoding="utf-8")
    assert "[ALARME]" in journal and "Train" in journal


def test_les_deux_valeurs_hors_canonique_du_journal_sont_couvertes():
    """`move_logger` écrit deux valeurs qui ne sont pas des modes, et elles comptent.

    « Aucun » = même localisation, l'agent n'a pas bougé (521 des 5 322 lignes du run
    `2026-09-04_01_09`) ; la cellule vide = aucun itinéraire (554 lignes de « Plus
    rapide »). Ni l'un ni l'autre n'est un déplacement, donc ni l'un ni l'autre n'entre
    dans une part modale — mais les jeter en silence, c'est perdre 10 % des lignes.
    """
    source = MOVE_LOGGER.read_text(encoding="utf-8")
    assert '"Aucun" if no_move' in source, "move_logger n'écrit plus « Aucun »"
    assert AGGREGATION["Aucun"] == NON_TRIP
    assert AGGREGATION[""] == NO_LABEL
    assert NON_TRIP not in SURVEY_CATEGORIES
    assert NO_LABEL not in SURVEY_CATEGORIES


def test_le_train_est_range_avec_les_transports_collectifs():
    """Le détail garde le train distinct, l'agrégation le fond : les deux niveaux.

    La référence `cerema_values.yaml` ne publie pas de part « train » : l'agréger vers
    `transports_collectifs` est la seule façon de rester comparable à la cible, et
    garder le libellé au niveau fin est la seule façon de savoir combien il pèse.
    """
    assert category_of("Train") == "transports_collectifs"
    assert "Train" in AGGREGATION
    assert AGGREGATION["Train"] in SCORED_CATEGORIES


def test_les_deux_roues_et_autres_vont_dans_le_residu_de_lenquete():
    """`autres_modes` est une catégorie de l'enquête (2 à 5 pt), pas un fourre-tout."""
    assert category_of("Deux-roues motorisé") == "autres_modes"
    assert category_of("Autres modes") == "autres_modes"
    assert "autres_modes" in SURVEY_CATEGORIES
    assert "autres_modes" not in SCORED_CATEGORIES


@pytest.mark.parametrize("label,attendu", sorted(NORMALISATION_HISTORIQUE.items()))
def test_non_regression_des_libelles_deja_normalises(label, attendu):
    """Les quatre libellés que l'ancienne table couvrait se normalisent à l'identique."""
    assert category_of(label) == attendu


# ── Rien ne se jette ──────────────────────────────────────────────────────────

def test_un_libelle_inconnu_est_compte_nomme_et_pas_perdu():
    """Le défaut corrigé : l'inconnu reste dans le comptage, sous son propre nom."""
    labels = ["Marche"] * 3 + [INCONNU] * 2 + ["Train"]
    tally = tally_labels(labels, source="test", alarm=False)
    assert tally.total == 6
    assert tally.unknown == {INCONNU: 2}
    assert tally.n_unknown == 2
    assert tally.detail[INCONNU] == 2
    assert tally.categories[UNKNOWN] == 2
    # Et il ne se glisse dans aucune catégorie d'enquête.
    assert sum(tally.categories.get(c, 0) for c in SURVEY_CATEGORIES) == 4


def test_le_total_est_conserve_agregation_comprise():
    """L'invariant : détail et catégories somment tous deux au nombre de lignes lues."""
    labels = (["Marche"] * 3 + ["Voiture Privée"] * 5 + ["Train"] * 2
              + ["Aucun"] * 4 + [""] * 1 + [INCONNU] * 2 + ["Autres modes"] * 1)
    tally = tally_labels(labels, source="test", alarm=False)
    assert tally.total == 18
    assert sum(tally.detail.values()) == 18
    assert sum(tally.categories.values()) == 18
    # Les déplacements sont les seules lignes qui entrent dans une part modale :
    # 3 marche + 5 voiture + 2 train + 1 « autres modes », hors Aucun / vide / inconnu.
    assert tally.n_trips == 11
    assert tally.categories[NON_TRIP] == 4
    assert tally.categories[NO_LABEL] == 1
    assert tally.categories[UNKNOWN] == 2


def test_linvariant_rompu_alarme_puis_leve(tmp_path):
    """Un effectif perdu ne doit pas passer pour un espoir déçu : ça lève.

    L'égalité ne peut tomber que sur un bug interne. On la casse à la main pour
    vérifier que le contrôle existe VRAIMENT — un invariant jamais exercé est un
    invariant qu'on croit.
    """
    tally = ModeTally(source="test")
    tally.total = 3
    tally.detail["Marche"] = 2                      # un effectif manquant
    tally.categories["marche"] = 2
    with pytest.raises(ModeTallyError):
        tally.check(log_dir=tmp_path)
    ligne = (tmp_path / "app.log").read_text(encoding="utf-8")
    assert "[ALARME]" in ligne and "invariant de comptage rompu" in ligne


def test_normalize_labels_garde_linconnu_dans_la_serie():
    """Pas de `NaN` : l'inconnu devient une catégorie visible, donc dénombrable."""
    valeurs, tally = normalize_labels(["Marche", INCONNU, "Train"], alarm=False)
    assert valeurs == ["marche", UNKNOWN, "transports_collectifs"]
    assert tally.unknown == {INCONNU: 1}


def test_les_parts_modales_ont_un_denominateur_explicite():
    """La part se calcule sur les catégories demandées, pas sur « tout ce qui reste »."""
    tally = tally_labels(["Voiture Privée"] * 6 + ["Marche"] * 2 + ["Train"] * 2
                         + ["Aucun"] * 10, source="test", alarm=False)
    parts = tally.shares()
    assert parts["voiture"] == pytest.approx(60.0)
    assert parts["transports_collectifs"] == pytest.approx(20.0)
    assert parts["velo"] == pytest.approx(0.0)
    assert sum(parts.values()) == pytest.approx(100.0)
    # Les 10 non-déplacements ne sont ni au numérateur ni au dénominateur, mais ils
    # sont dits.
    assert missing_from(tally) == {NON_TRIP: 10}


def test_le_detail_se_recompose_en_categories():
    """Le lecteur doit pouvoir refaire l'agrégat depuis le détail publié.

    C'est la demande : un audit détaillé qu'on puisse ensuite agréger. Publier le
    résultat sans la table ne permet pas de vérifier l'agrégation ; publier les deux, si.
    """
    tally = tally_labels(["Train"] * 3 + ["Transports_collectifs"] * 4 + ["Marche"],
                         source="test", alarm=False)
    recompose: dict[str, int] = {}
    for row in tally.detail_rows():
        recompose[row["categorie"]] = recompose.get(row["categorie"], 0) + row["n"]
    assert recompose == dict(tally.categories)
    assert recompose["transports_collectifs"] == 7


def test_la_table_dagregation_est_publiable():
    """`aggregation_table()` dit, pour chaque libellé, où il va et s'il est scoré."""
    rows = aggregation_table()
    assert len(rows) == len(AGGREGATION) >= 9
    train = next(r for r in rows if r["libelle"] == "Train")
    assert train == {"libelle": "Train", "categorie": "transports_collectifs",
                     "dans_les_parts_modales": True, "scoree": True}
    aucun = next(r for r in rows if r["libelle"] == "Aucun")
    assert aucun["dans_les_parts_modales"] is False


# ── L'alarme est repérable par `make error` ───────────────────────────────────

def test_lalarme_secrit_en_error_au_format_que_make_error_relit(tmp_path):
    """Une alarme que `scripts/errors.py` ne sait pas relire n'existe pas.

    `make error` filtre `app.log` sur `AAAA-MM-JJ HH:MM:SS | ERROR    | …`. Le format
    du handler est confronté ici à l'expression régulière du script lui-même.
    """
    tally = tally_labels(["Marche"] * 2 + [INCONNU] * 3,
                         source="moves.csv · Mode de transport Choisi",
                         log_dir=tmp_path)
    assert tally.n_unknown == 3
    lignes = (tmp_path / "app.log").read_text(encoding="utf-8").splitlines()
    assert lignes, "aucune ligne écrite dans app.log"
    motif = _error_regex()
    retenues = [motif.match(l) for l in lignes]
    assert any(retenues), lignes
    # `ERROR_RE` capture « <logger> - <message> » : c'est ce que `make error` affiche.
    capture = next(m for m in retenues if m).group(1)
    logger_name, _, message = capture.partition(" - ")
    assert logger_name == "scripts.analysis.mode_labels"
    assert message.startswith("[ALARME]")
    assert INCONNU in message                       # le libellé est NOMMÉ
    assert "Mode de transport Choisi" in message    # et la colonne d'origine aussi
    assert "3" in message                           # et son effectif


def test_pas_dalarme_quand_tous_les_libelles_sont_connus(tmp_path):
    """Front montant : une alarme qui se déclenche à vide noie le journal."""
    tally = tally_labels(["Marche", "Train", "Aucun", ""], source="test",
                         log_dir=tmp_path)
    assert alarm_unknown(tally, log_dir=tmp_path) is None
    assert not (tmp_path / "app.log").exists() or not (
        tmp_path / "app.log").read_text(encoding="utf-8").strip()


def test_lalarme_va_dans_le_journal_du_run_analyse(tmp_path, monkeypatch):
    """L'alarme concerne un run : elle s'écrit dans l'`app.log` de CE run."""
    monkeypatch.delenv("MODE_LABELS_LOG", raising=False)
    run = tmp_path / "2026-09-04_01_09"
    run.mkdir()
    assert resolve_log_path(run) == run / "app.log"
    assert resolve_log_path(run / "app.log") == run / "app.log"
    # Sans run précisé, c'est le journal courant — celui que `make error` lit sans
    # argument.
    assert resolve_log_path(None).parts[-3:] == ("experiments", "current", "app.log")


# ── Interface pandas (celle du carnet) ───────────────────────────────────────

def test_normalize_column_remplace_la_colonne_et_rend_le_comptage(tmp_path):
    """Ce que le carnet appelle : une colonne normalisée, et de quoi la commenter."""
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame({MODE_COLUMN: ["Marche", "Train", INCONNU, "Aucun",
                                        "Voiture Privée"]})
    tally = normalize_column(frame, MODE_COLUMN, source="test", log_dir=tmp_path)
    assert list(frame[MODE_COLUMN]) == ["marche", "transports_collectifs", UNKNOWN,
                                        NON_TRIP, "voiture"]
    assert tally.total == 5
    assert tally.unknown == {INCONNU: 1}
    assert "[ALARME]" in (tmp_path / "app.log").read_text(encoding="utf-8")


def test_une_cellule_vide_nalarme_pas_quel_que_soit_son_ecriture(tmp_path):
    """`""`, `NaN`, `None`, `pd.NA` : la même absence, jamais un libellé inconnu.

    `pandas.read_csv` rend `NaN` pour une cellule vide, et « Plus rapide » en porte 554
    sur 5 322 dans le dernier run. Les faire alarmer serait apprendre à ignorer
    l'alarme.
    """
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame({MODE_COLUMN: ["Marche", None, float("nan"), "", pd.NA]})
    tally = normalize_column(frame, MODE_COLUMN, source="test", log_dir=tmp_path)
    assert tally.unknown == {}
    assert tally.categories[NO_LABEL] == 4
    assert not (tmp_path / "app.log").exists()


def test_normalize_column_refuse_une_colonne_absente():
    """Une colonne mal nommée doit lever, pas rendre une table intacte en silence."""
    pd = pytest.importorskip("pandas")
    with pytest.raises(KeyError):
        normalize_column(pd.DataFrame({"autre": ["Marche"]}), MODE_COLUMN, alarm=False)


def test_un_reindex_sur_les_modes_scores_ne_perd_plus_rien_en_silence():
    """Le geste exact du carnet : ce que `mode_order` laisse dehors est nommé.

    `value_counts().reindex(mode_order)` élimine tout ce qui n'est pas dans la liste.
    Le remède n'est pas de supprimer le `reindex` — les graphes comparent bien quatre
    catégories à quatre cibles — mais de DIRE ce qu'il laisse dehors.
    """
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame({MODE_COLUMN: ["Marche"] * 2 + ["Train"] * 3
                          + ["Aucun"] * 4 + [INCONNU]})
    tally = normalize_column(frame, MODE_COLUMN, source="test", alarm=False)
    counts = frame[MODE_COLUMN].value_counts().reindex(SCORED_CATEGORIES).fillna(0)
    assert counts.sum() == 5                        # 2 marche + 3 train → TC
    assert missing_from(tally) == {NON_TRIP: 4, UNKNOWN: 1}
    assert counts.sum() + sum(missing_from(tally).values()) == tally.total
