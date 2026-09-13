"""mode_choice_rf.py — Contrat et évaluateur du témoin random forest (ticket 044).

Ce module ne sait pas *choisir* une forêt : il sait la **reconstruire et la faire prédire**,
à partir d'un artefact qui ne contient aucun arbre.

**Pourquoi aucun arbre dans l'artefact.** La forêt retenue compte 1 200 arbres et
3 740 500 nœuds. Sérialisée, elle pèse ~150 Mo en JSON compact ou 165 Mo en `joblib`
compressé — contre 18,9 Mo pour le booster, qui est déjà à la limite du diffable, et 21 ko
pour le logit. Un fichier pareil ne se relit pas, ne se diffe pas, et un `pickle` de
scikit-learn se périme à la version suivante de la bibliothèque (c'est la raison pour
laquelle le second oracle sérialise des coefficients et non un modèle).

**Ce que l'artefact porte à la place.** De quoi refaire *exactement* la même forêt : les
hyperparamètres retenus, la graine, le contrat de matrice de dessin, l'empreinte du parquet
et la version de scikit-learn. Le réajustement coûte **une dizaine de secondes** et rend un
modèle identique au bit près — `random_state` est fixé, `RandomForestClassifier` est
déterministe à graine donnée. L'empreinte du modèle (règle R12 de la plateforme
d'expériences) devient le SHA de ce petit JSON, qui détermine entièrement la forêt : c'est
une provenance plus honnête que le SHA d'un pickle de 165 Mo, dont personne ne peut vérifier
qu'il correspond à ce que l'artefact déclare.

**Les deux conditions, refusées et non contournées.** Le réajustement dépend de deux choses
que l'artefact fige et que le prédicteur **vérifie avant d'ajuster** :

1. la **matrice d'entraînement**, emportée à côté de l'artefact dans un `.npz` de 1,4 Mo et
   comparée par SHA-256. Elle remplace le parquet pour une raison mesurée : le conteneur
   `controller`, où tournent les expériences, n'a **ni `pyarrow` ni `fastparquet`** et ne sait
   pas lire un parquet. Le rejeu ne demande donc que **numpy**. Le fichier est petit parce que
   la matrice de dessin est surtout faite de 0 et de 1 : 52 248 × 50 valeurs se compriment à
   1,4 Mo, contre 165 Mo pour la forêt elle-même ;
2. la **reproduction des métriques publiées**. C'est le point où la première version de ce
   module se trompait de garde-fou : elle comparait la *version de scikit-learn*, et refusait
   de tourner dès qu'elle différait. Or l'hôte a la 1.8.0 et le conteneur `controller`, où
   tournent les expériences, la 1.9.0 — le témoin n'aurait jamais pu y être rejoué, pour une
   raison qui n'était qu'un numéro. Un numéro de version ne dit pas si la forêt a changé : il
   dit qu'elle *pourrait* avoir changé. Le prédicteur réajuste donc, **prédit sur le split
   test et compare l'exactitude et la CEL à celles que l'artefact publie**. Identiques → c'est
   la forêt du tableau, quelle que soit la bibliothèque. Différentes → refus, avec l'écart.

Un refus bruyant vaut mieux qu'une forêt silencieusement différente de celle du tableau — mais
il faut refuser sur ce qui a changé, pas sur ce qui aurait pu changer.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import sklearn

#: Format de l'artefact du témoin. Décrit la *structure* du JSON, indépendamment de
#: `spec_version` qui décrit le contrat de variables.
RF_FORMAT = "rf_mode_choice_policy"
RF_FORMAT_VERSION = 1

#: Écart maximal toléré entre les métriques de la forêt réajustée et celles publiées.
#: Serré à dessein : deux forêts identiques donnent exactement les mêmes chiffres, et cette
#: marge ne couvre que l'ordre des réductions flottantes.
TOLERANCE_REPRODUCTION = 1e-9


def sha256_fichier(chemin: Path) -> str:
    """SHA-256 d'un fichier, lu par blocs — le parquet pèse plusieurs dizaines de Mo."""
    digest = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            digest.update(bloc)
    return digest.hexdigest()


class RFPredictor:
    """Évaluateur du témoin random forest — réajuste, puis prédit.

    Expose délibérément la même surface que le booster LightGBM et que ``LogitPredictor``
    (``predict``, ``feature_name``) : les consommateurs appellent alors **le même chemin de
    prédiction** pour toutes les familles, ce qui est la condition pour que leurs sorties
    soient comparables.
    """

    def __init__(self, artefact: dict, trainset_path: Path | None = None,
                 verifier_metriques: bool = True):
        from scripts.progedo_logit.fit_mode_choice_forest import forest

        self.artefact = artefact
        bloc = artefact["rf"]
        self.classes = list(artefact["target"]["classes"])
        self.names = [f["name"] for f in artefact["features"]]

        chemin = Path(trainset_path) if trainset_path else (
            Path(__file__).resolve().parent / artefact["trainset_file"])
        if not chemin.exists():
            raise FileNotFoundError(
                f"Matrice d'entraînement absente : {chemin}. Le témoin se réajuste au "
                "chargement (aucun arbre n'est sérialisé) ; il lui faut la matrice qui a "
                "servi à l'estimer. Elle se régénère avec "
                "`make forest FOREST_ARGS=--artefact`.")
        empreinte = sha256_fichier(chemin)
        if empreinte != artefact["trainset_sha256"]:
            raise ValueError(
                f"La matrice d'entraînement a changé depuis l'estimation (SHA "
                f"{empreinte[:12]} contre {artefact['trainset_sha256'][:12]}). La forêt "
                "réajustée ne serait pas celle dont les métriques sont publiées. Ré-estimez "
                "avec `make forest FOREST_ARGS=--artefact`.")

        with np.load(chemin) as jeu:
            matrix = jeu["X"]
            y = jeu["y"].astype("int64")
            w = jeu["w"]
            est_train = jeu["is_train"]
            self.est_test = jeu["is_test"]
        if matrix.shape[1] != len(bloc["contrat"]["design_columns"]):
            raise ValueError(
                f"Matrice à {matrix.shape[1]} colonnes, contrat à "
                f"{len(bloc['contrat']['design_columns'])} : l'artefact et sa matrice ne "
                "viennent pas de la même estimation.")

        h = bloc["hyperparameters"]
        self.model = forest(h["n_estimators"], h["max_depth"], h["min_samples_leaf"],
                            h["max_features"])
        self.model.fit(matrix[est_train], y[est_train], sample_weight=w[est_train])
        self.n_fit = int(est_train.sum())
        self.sklearn_estimation = bloc["estimator"]["version"]
        self.sklearn_ici = sklearn.__version__
        if verifier_metriques:
            self.controle = self._verifier_reproduction(matrix, y, w)

    def _verifier_reproduction(self, matrix: np.ndarray, y: np.ndarray,
                               w: np.ndarray) -> dict:
        """La forêt réajustée reproduit-elle les métriques publiées ?

        Le seul garde-fou qui mesure au lieu de présumer. Il coûte une prédiction sur les
        13 045 lignes du test, et il vaut pour n'importe quelle version de scikit-learn : ce
        qu'on veut savoir n'est pas « la bibliothèque a-t-elle changé » mais « la forêt
        a-t-elle changé ».
        """
        from scripts.progedo_logit.fit_mode_choice_forest import proba_complete
        from scripts.progedo_logit.mode_choice_eval import evaluate_proba

        proba = proba_complete(self.model, matrix[self.est_test], len(self.classes))
        obtenu = evaluate_proba(proba, y[self.est_test], w[self.est_test], self.classes)
        publie = self.artefact["metrics"]
        ecarts = {
            "accuracy_weighted": abs(obtenu["accuracy_weighted"]
                                     - publie["accuracy_weighted"]),
            "cel_weighted": abs(obtenu["cel_weighted"] - publie["cel_weighted"]),
        }
        if max(ecarts.values()) > TOLERANCE_REPRODUCTION:
            raise ValueError(
                f"La forêt réajustée ne reproduit pas les métriques publiées : écarts "
                f"{ecarts} (tolérance {TOLERANCE_REPRODUCTION:g}). scikit-learn "
                f"{self.sklearn_ici} ici contre {self.sklearn_estimation} à l'estimation. "
                "Ce n'est plus la forêt du tableau — ré-estimez avec `make forest --artefact` "
                "sous cette version, ou prédisez sous celle de l'estimation.")
        return {
            "reproduit": True,
            "ecarts": ecarts,
            "tolerance": TOLERANCE_REPRODUCTION,
            "sklearn_estimation": self.sklearn_estimation,
            "sklearn_execution": self.sklearn_ici,
        }

    def predict(self, matrix: Any, num_iteration: Any = None) -> np.ndarray:
        """Probabilités sur les quatre classes, dans l'ordre du spec.

        ``matrix`` est la matrice **déjà encodée** par ``encode_features`` — la même entrée
        que ``LogitPredictor``. ``num_iteration`` n'a pas de sens pour une forêt : accepté et
        ignoré, pour que l'appelant n'ait pas à savoir quelle famille il tient.
        """
        from scripts.progedo_logit.fit_mode_choice_forest import proba_complete
        from scripts.progedo_logit.mode_choice_logit import design_matrix

        design = design_matrix(matrix, {"features": self.artefact["features"],
                                        "logit": self.artefact["rf"]["contrat"]})
        return proba_complete(self.model, design, len(self.classes))

    def feature_name(self) -> list[str]:
        """Variables attendues, dans l'ordre du spec — même contrat que les autres familles."""
        return list(self.names)


def charger_rf(path: Path, spec: dict) -> tuple[RFPredictor, dict]:
    """Charge le témoin depuis son artefact — signature de ``load_policy``.

    Les mêmes trois refus que ``load_policy`` : un format inconnu, un ``spec_version`` qui
    diverge, un ordre de variables ou de classes qui n'est pas celui du spec. Un décalage
    d'une colonne donne des probabilités parfaitement plausibles.
    """
    artefact = json.loads(Path(path).read_text(encoding="utf-8"))
    if artefact.get("format") != RF_FORMAT:
        raise ValueError(f"Format d'artefact inattendu : {artefact.get('format')!r}.")
    if artefact.get("spec_version") != spec.get("spec_version"):
        raise ValueError(
            f"Témoin estimé sous le contrat de variables v{artefact.get('spec_version')}, "
            f"le spec lu est en v{spec.get('spec_version')}. Ré-estimez (`make forest`).")
    names = [f["name"] for f in spec["features"]]
    if [f["name"] for f in artefact.get("features") or ()] != names:
        raise ValueError("L'ordre des variables de l'artefact diffère de celui du spec.")
    classes = list(spec["target"]["classes"])
    if list((artefact.get("target") or {}).get("classes") or ()) != classes:
        raise ValueError("L'ordre des classes de l'artefact diffère de celui du spec.")
    return RFPredictor(artefact), artefact
