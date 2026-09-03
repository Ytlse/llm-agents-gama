"""equipment_propensity.py — Propension individuelle à un équipement de mobilité.

Machinerie **partagée** par deux traits que les tickets 016 et 017 spécifient
séparément mais dont ils disent explicitement que « les lots 1 et 2 sont communs :
même fichier source, même restriction `PENQ = 1`, même pondération `COEP`, même cause
(la classe d'âge 15-29 de l'appariement ENTD), même patron de correction ». Un seul
chargeur, un seul vecteur de design, deux cibles :

| Trait | Cible EMC² | Ressource |
|---|---|---|
| `has_pt_subscription` | `P12 == 6` (abonnement TC valide hier) | `pt_subscription.json` |
| `has_driving_license` | `P7 == 1` (permis voiture) | `driving_license.json` |

**Pourquoi un module et non deux.** Le vecteur de design est identique aux deux traits,
et c'est le seul endroit du dépôt où l'entraînement et l'application doivent voir
*exactement* le même vecteur. Deux copies dériveraient au premier changement de
recodage — c'est la raison pour laquelle `export_bike_ownership` passe déjà par
`bike_ownership.propensity_design` plutôt que de recopier la formule.

## Ce que le module ne fait pas

- **Aucun étage de ménage.** Un abonnement et un permis sont nominatifs : pas de stock
  partagé, pas de tirage sans remise, pas de ménage à reconstituer. C'est ce qui rend
  ces deux traits moins coûteux que le vélo (ticket 015). La corrélation intra-foyer
  est portée par la **motorisation du ménage**, covariable observée et juste dans la
  population synthétique (1,28 voiture simulée contre 1,25 mesurée).
- **Aucune covariable de déplacement.** Un équipement est un **stock**, il doit être
  invariant au trajet : sinon le même agent est abonné pour aller travailler et ne
  l'est plus pour faire ses courses, et le trait cesse d'être un trait. Même argument
  que le ticket 015 sur `D12`.
- **Aucun revenu.** `M22` (revenu du ménage) est livré **vide** — 0 valeur non nulle sur
  10 783 ménages. Le filtre d'éligibilité des tarifs sous condition de ressources
  (gratuité senior, tarif solidaire demandeur d'emploi, échelons boursiers) est donc
  inobservable, et ce module ne l'approche pas. Il n'en a pas besoin : sa cible est
  « détient un abonnement », pas « bénéficie de telle réduction » — l'enquête ne sert
  que deux modalités de `P12` (oui sans précision / non) et ne permet pas la seconde
  question.

## Où la tarification entre, et où elle n'entre pas

Elle n'entre **jamais comme grandeur** : aucun montant, aucun échelon, aucun taux de
fréquentation. Elle entre uniquement comme **emplacement de rupture** dans la courbe
d'âge — les paliers `under_26`, `age_62p`, `age_65p` de `FEATURE_KNOTS`. Dans un logit
l'âge entre linéairement dans le log-odds et ne *peut pas* produire la falaise que
l'enquête mesure (15-17 : 64,0 % · 18-24 : 63,3 % · 25-29 : 29,3 %) ; la règle Tisséo
« moins de 26 ans et étudiants » dit où placer le nœud, l'enquête dit s'il vaut la
peine. Le script d'export ajuste **avec et sans** ces paliers et publie les deux AUC
hors-échantillon : un palier qui n'améliore pas la validation croisée groupée par
ménage est retiré, et le retrait est imprimé.

## Le tirage

Bernoulli de la propension, clé de hachage `(adresse du domicile, index de la personne,
sel versionné)` — le déterminisme de `housing_type.py`. Deux exécutions, deux machines,
deux moments donnent le même résultat ; changer `DRAW_SALT` est un acte daté.

Contrairement au logement, le tirage porte sur **la personne** et non sur l'adresse : un
abonnement et un permis sont individuels, deux colocataires n'ont aucune raison de
partager le leur. L'adresse reste dans la clé pour que deux populations tirées de deux
sous-ensembles différents donnent la même valeur à la même personne.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
RESOURCE_DIR = REPO_ROOT / "llm_module" / "data"

# Âge légal du permis. Ce n'est pas un paramètre de modèle : aucune propension n'est
# évaluée en dessous, le trait vaut `False` par construction. L'enquête le confirme
# (0,0 % de titulaires à 15-17 ans), et un seuil légal ne s'ajuste pas.
DRIVING_AGE = 18

# Âge minimum du champ de `P12` (« abonnement TC valide hier ») et âge minimum de la
# population exportée. Aucun agent n'échappe donc à l'imputation de l'abonnement.
PT_MIN_AGE = 5


@dataclass(frozen=True)
class TraitSpec:
    """Ce qui distingue les deux traits — tout le reste est commun."""

    key: str                    # clé dans `traits_json`
    resource: str               # nom du fichier de ressource
    salt: str                   # sel de tirage, versionné
    target: str                 # description de la cible EMC², écrite dans la ressource
    min_age: int                # en dessous, pas de propension évaluée
    below_min_age: bool         # valeur imposée sous `min_age`


PT_SUBSCRIPTION = TraitSpec(
    key="has_pt_subscription",
    resource="pt_subscription.json",
    salt="pt_subscription_v1",
    target="P12 == 6 — possession d'un abonnement TC valide hier",
    min_age=PT_MIN_AGE,
    below_min_age=False,
)

DRIVING_LICENSE = TraitSpec(
    key="has_driving_license",
    resource="driving_license.json",
    salt="driving_license_v1",
    # `P7 == 3` vaut « conduite accompagnée et leçons de conduite » : 266 personnes
    # enquêtées, âge médian 18 ans, dont 155 majeures. Elles ne sont PAS titulaires.
    # Un `== 1` nu l'affirmerait en silence ; c'est écrit ici pour être lu.
    target="P7 == 1 — titulaire du permis voiture (P7 == 3, conduite accompagnée, "
           "compte NON)",
    min_age=DRIVING_AGE,
    below_min_age=False,
)

TRAITS = {"pt_subscription": PT_SUBSCRIPTION, "driving_license": DRIVING_LICENSE}


# ── Vecteur de design ────────────────────────────────────────────────────────
#
# Ordre fixe. Les coefficients de la ressource sont alignés dessus, et
# `design_vector` est la SEULE définition : l'entraînement l'appelle comme
# l'application.

# Termes toujours présents.
FEATURE_BASE = (
    "age10",            # âge / 10 — pente continue
    "age10_sq",         # courbure : la propension à l'abonnement n'est pas monotone
    "female",
    "cars0",            # ménage non motorisé — 61,8 % d'abonnés contre 16,1 % à 2+
    "cars2p",           # ménage à deux voitures et plus (référence : une voiture)
    "log_density",      # densité de ménages de la zone fine, en log
    "dist_center10",    # distance à l'hypercentre / 10 km
)

# Paliers tarifaires. Présents seulement si la validation croisée les retient — la
# ressource porte la liste effectivement ajustée dans `features`.
FEATURE_KNOTS = (
    "under_26",         # tarification jeune Tisséo (« moins de 26 ans »)
    "age_62p",          # ouverture senior pour les retraités
    "age_65p",          # ouverture senior générale
)


def _knot_values(age: float) -> dict[str, float]:
    return {
        "under_26": 1.0 if age < 26 else 0.0,
        "age_62p": 1.0 if age >= 62 else 0.0,
        "age_65p": 1.0 if age >= 65 else 0.0,
    }


def design_vector(age: Optional[float],
                  gender: Optional[str],
                  main_occupation: Optional[str],
                  number_of_cars: Optional[float],
                  density_hh_km2: Optional[float],
                  dist_center_km: Optional[float],
                  occupations: Sequence[str],
                  features: Sequence[str],
                  median_density: float) -> list[float]:
    """Vecteur de design, dans l'ordre de ``features``.

    ``features`` vient de la ressource : c'est elle qui fixe l'ordre ET dit quels
    paliers ont été retenus à l'ajustement. Lire l'ordre ailleurs qu'à cet endroit
    (une constante du module, par exemple) désalignerait le vecteur des coefficients
    dès qu'un palier serait retiré.

    Une valeur manquante n'est jamais devinée « au plus fréquent » : la densité
    retombe sur sa médiane de périmètre (publiée dans la ressource), la distance sur
    zéro, et l'absence est comptée par l'appelant. Une modalité d'occupation hors
    vocabulaire laisse toutes ses indicatrices à zéro — c'est-à-dire la modalité de
    référence, pas une modalité inventée.
    """
    a = float(age or 0.0)
    density = median_density if density_hh_km2 is None or (
        isinstance(density_hh_km2, float) and math.isnan(density_hh_km2)
    ) else float(density_hh_km2)
    cars = float(number_of_cars or 0.0)
    values: dict[str, float] = {
        "age10": a / 10.0,
        "age10_sq": (a / 10.0) ** 2,
        "female": 1.0 if (gender or "") == "Female" else 0.0,
        "cars0": 1.0 if cars <= 0 else 0.0,
        "cars2p": 1.0 if cars >= 2 else 0.0,
        "log_density": math.log1p(max(0.0, density)),
        "dist_center10": float(dist_center_km or 0.0) / 10.0,
        **_knot_values(a),
    }
    for occupation in occupations:
        values[f"occ_{occupation}"] = 1.0 if main_occupation == occupation else 0.0
    missing = [f for f in features if f not in values]
    if missing:
        raise KeyError(f"Variables du vecteur de design inconnues : {missing}")
    return [values[f] for f in features]


# ── Tirage déterministe ──────────────────────────────────────────────────────

def uniform(salt: str, key: str) -> float:
    """Uniforme sur [0, 1) déterministe, dérivée d'un hachage stable.

    `hash()` de Python est randomisé par processus : il donnerait des traits
    différents à chaque exécution. SHA-256 ne dépend ni de la version, ni de la
    plateforme, ni de `PYTHONHASHSEED`.
    """
    digest = hashlib.sha256(f"{salt}:{key}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2 ** 64


def draw_key(lat: Optional[float], lon: Optional[float], person_id: Any) -> str:
    """Clé de tirage : adresse du domicile **et** identifiant de personne.

    L'adresse seule ferait tirer identiquement tous les membres d'un foyer — faux pour
    un trait nominatif. L'identifiant seul ferait dépendre le trait du tirage de
    population, donc changerait à chaque régénération.
    """
    if lat is None or lon is None:
        return f"nohome/{person_id}"
    return f"{float(lat):.6f},{float(lon):.6f}/{person_id}"


# ── Ressource ────────────────────────────────────────────────────────────────

@dataclass
class PropensityLaw:
    """Une loi de propension chargée depuis sa ressource, prête à appliquer."""

    spec: TraitSpec
    features: tuple[str, ...]
    occupations: tuple[str, ...]
    intercept: float
    coefficients: tuple[float, ...]
    median_density: float
    meta: dict

    @classmethod
    def load(cls, spec: TraitSpec, resource: Optional[Path] = None) -> "PropensityLaw":
        """Charge la ressource. Son absence est une **erreur explicite**.

        Jamais un repli silencieux sur une propension d'ensemble : une loi absente doit
        arrêter l'enrichissement avec le message qui dit quelle commande la produit, pas
        imputer à l'aveugle un trait que trois consommateurs liront comme mesuré.
        """
        path = Path(resource) if resource else RESOURCE_DIR / spec.resource
        if not path.exists():
            raise FileNotFoundError(
                f"Loi de propension absente : {path}. Produisez-la avec "
                f"`make equipment-propensity` (données PROGEDO requises, accès "
                f"restreint lil-1750).")
        raw = json.loads(path.read_text(encoding="utf-8"))
        law = raw.get("law", raw)
        features = tuple(law["features"])
        coefficients = tuple(float(v) for v in law["coefficients"])
        if len(features) != len(coefficients):
            raise ValueError(
                f"{path} : {len(features)} variables pour {len(coefficients)} "
                f"coefficients. Ressource corrompue ou tronquée.")
        return cls(
            spec=spec,
            features=features,
            occupations=tuple(law["occupations"]),
            intercept=float(law["intercept"]),
            coefficients=coefficients,
            median_density=float(law["median_density"]),
            meta=raw.get("meta", {}),
        )

    def propensity(self, age: Optional[float], gender: Optional[str],
                   main_occupation: Optional[str], number_of_cars: Optional[float],
                   density_hh_km2: Optional[float],
                   dist_center_km: Optional[float]) -> Optional[float]:
        """P(trait) pour une personne, ou ``None`` sous l'âge de champ du trait."""
        if age is None:
            return None
        if float(age) < self.spec.min_age:
            return None
        x = design_vector(age, gender, main_occupation, number_of_cars,
                          density_hh_km2, dist_center_km, self.occupations,
                          self.features, self.median_density)
        z = self.intercept + sum(c * v for c, v in zip(self.coefficients, x))
        return 1.0 / (1.0 + math.exp(-z))

    def value(self, age: Optional[float], gender: Optional[str],
              main_occupation: Optional[str], number_of_cars: Optional[float],
              density_hh_km2: Optional[float], dist_center_km: Optional[float],
              lat: Optional[float], lon: Optional[float],
              person_id: Any) -> tuple[bool, str]:
        """Valeur tirée du trait, et le **motif** — pour que le rapport le compte.

        Motifs : ``sous_age_champ`` (valeur imposée par le seuil), ``tirage`` (Bernoulli
        de la propension). Un motif est retourné plutôt que journalisé ici : le module
        ne sait pas s'il tourne dans un script, un notebook ou un test.
        """
        p = self.propensity(age, gender, main_occupation, number_of_cars,
                            density_hh_km2, dist_center_km)
        if p is None:
            return self.spec.below_min_age, "sous_age_champ"
        u = uniform(self.spec.salt, draw_key(lat, lon, person_id))
        return (u < p), "tirage"


def write_resource(path: Path, spec: TraitSpec, law: dict, validation: dict,
                   source: dict) -> None:
    """Écrit la ressource : la loi, sa recette, et sa provenance.

    **Aucune microdonnée** — coefficients et tables agrégées seulement, comme
    `bike_ownership.json`. C'est ce qui permet de committer la ressource alors que sa
    source est d'accès restreint.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "equipment_propensity/v1",
        "trait": spec.key,
        "law": law,
        "validation": validation,
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "target": spec.target,
            "draw_salt": spec.salt,
            "min_age": spec.min_age,
            **source,
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
