"""
core/bike_ownership.py — Le vélo du persona, appris sur EMC² et non imputé au ménage.

`personal_bike` était tiré par eqasim avec `p = min(1, vélos_du_donneur / taille)`, où
le nombre de vélos est **recopié** d'un ménage de l'ENTD 2008 apparié sans la taille du
foyer ni l'habitat parmi les attributs d'appariement. Le total sortait à peu près juste
(53,3 % de porteurs pour ~51 % attendus) et la répartition était fausse : le gradient de
taille de ménage était **inversé** (76 % de porteurs chez les personnes seules contre
33 % observés, 36 % dans les ménages de 4 contre 65 %). Ce module remplace cette recopie
par trois étages appris sur l'enquête EMC² Toulouse 2023 (ticket 015).

**Le nombre de vélos est un trait de foyer, pas un tirage par personne.** C'est le point
de fond du ticket et ce qui fixe l'ordre des étages. Sur les ménages de 4 personnes,
l'enquête voit 15,7 % de familles sans aucun vélo et 40,1 % avec un vélo par tête ; un
tirage individuel indépendant **calé sur la même moyenne** produit 1,4 % et 18,3 %, en
empilant tout au milieu (variance 0,91 contre 2,13 observée, surdispersion ×2,4). Les
deux lois ont exactement la même moyenne : aucun redressement sur la moyenne ne peut donc
les rapprocher. On tire `k` d'abord, et il n'y a plus rien à redresser.

Les trois étages :

1. **Combien de vélos dans le ménage** (`stock_law`) — logit multinomial sur `k = M21`
   écrêté à `4+`, appris sur les 10 783 ménages de l'enquête en pondération `COE0`.
2. **Qui, dans le ménage, les tient** (`assign`) — tirage sans remise pondéré par une
   propension apprise sur `P20` (« à vélo, conducteur », pondération `COEP`, enquêtés
   `PENQ = 1`), schéma d'Efraimidis–Spirakis. `k` décide **combien**, la propension
   décide seulement **qui**.
3. **Quel type de vélo** (`VAE_SHARE`) — tirage par vélo attribué, 7,7 % du parc.

Trois garde-fous, les mêmes que `housing_type` :

- **Déterminisme par hachage.** Aucun RNG : la clé est l'adresse du domicile pour
  l'étage 1, l'adresse plus l'index de la personne pour les étages 2 et 3, et le sel est
  versionné. Deux exécutions, deux machines, deux moments donnent le même parc.
- **Hors couche, on ne devine pas.** Un domicile sans zone fine n'a pas de loi : le trait
  est `None`, et il doit se voir. Un `personal_bike = None` massif doit faire **échouer**
  la validation, pas la réussir.
- **Aucun repli silencieux.** Ressource absente ⇒ erreur au chargement.

## Ce sur quoi l'étage 1 est conditionné, et pourquoi pas l'habitat

Le ticket laissait un piège à trancher : le `housing_type` du persona est lui-même
**imputé** depuis la loi de sa zone fine (`core/housing_type.py`). Conditionner `k`
dessus revient-il à conditionner sur la zone, ou apporte-t-il quelque chose ?

Mesuré sur l'enquête : l'habitat imputé ne coïncide avec l'habitat observé que **47,6 %**
du temps. Trois conséquences, dans cet ordre :

1. Conditionner `k` sur (zone, taille, motorisation) **sans** l'habitat reproduit la
   courbe d'équipement par habitat imputé à **0,6 point près** (61,2 → 43,3 % contre
   61,6 → 42,7 % attendus).
2. Conditionner sur l'habitat imputé **dégrade** ce résultat (65,6 → 39,3 %, soit +4,0 à
   −4,6 points d'écart) : c'est appliquer un coefficient appris sur une variable observée
   à une variable fausse une fois sur deux, ce qui gonfle l'amplitude au-delà de ce que
   la variable bruitée peut porter.
3. Surtout, cela créerait une dépendance entre **deux imputations** dont la loi jointe
   n'est ni la vraie, ni celle qu'on peut mesurer — un artefact.

Décision : **l'étage 1 est conditionné sur la zone, la taille du ménage et la
motorisation, jamais sur l'habitat.** L'habitat n'est pas ici « une réécriture de la
zone » qu'on assume par commodité : c'est une variable moins informative que la zone,
puisqu'elle en est tirée.

Corollaire à ne pas taire, et c'est une amende au ticket : le critère « 71 % individuel
isolé → 38 % grand collectif (± 4 pts) » est **inatteignable par construction** sur une
population synthétique, quelle que soit la qualité du modèle. Croiser le nombre de vélos
**vrai** de l'enquête par l'habitat **imputé** donne déjà 61,6 → 42,7 %, soit 19 points
d'amplitude au lieu des 33,4 publiés : c'est de la dilution de régression, et elle
plafonne ce que la mesure peut voir. La cible opposable est donc la courbe diluée, que
l'exportateur calcule et publie à côté de la courbe publiée. Viser les 33,4 points
reviendrait à sur-corriger le modèle pour compenser le bruit de l'axe de mesure.

`M2` (statut d'occupation du logement), que le ticket citait en covariable candidate, est
écarté pour une autre raison, celle du contrat de features du dépôt : le persona ne le
porte pas. Une variable non calculable à l'instant de l'application n'entre pas.

La ressource (`llm_module/data/bike_ownership.json`) est produite par
`scripts/progedo_logit/export_bike_ownership.py` (`make bike-ownership`) depuis les
microdonnées d'accès restreint. Comme la couche de zones fines, elle est **hors dépôt**.

Les entrées/sorties sont confinées à `BikeOwnershipModel.load` ; le reste du module est
pur, conformément au contrat d'architecture de `llm_module.core`.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

# ── Contrat de sortie ────────────────────────────────────────────────────────
# Les trois libellés que porte `traits_json`, et qu'aucun consommateur ne doit
# reconstruire à la main. `None` (trait absent) n'est pas une quatrième modalité :
# c'est « hors couche de zones fines », et ça doit se voir.
TRAIT_KEY = "personal_bike"

NO_BIKE = "Pas de vélo"
PLAIN_BIKE = "vélo normal"
ELECTRIC_BIKE = "VAE"

LABELS: tuple[str, ...] = (NO_BIKE, PLAIN_BIKE, ELECTRIC_BIKE)

# Sel du tirage. Versionné : le changer rebat tout le parc, ce qui doit être un acte
# délibéré et daté, pas un effet de bord.
DRAW_SALT = "personal_bike_v1"

# Écrêtage de `k`. Au-delà de 4 vélos les effectifs de l'enquête ne portent plus rien
# (57 ménages sur 10 783 en déclarent 7 et plus) et la distinction n'a aucun effet en
# simulation : un ménage de 4 personnes ne peut pas monter sur 7 vélos.
K_MAX = 4
K_CLASSES: tuple[int, ...] = tuple(range(K_MAX + 1))

# Écrêtage de la taille du ménage dans les indicatrices du modèle, aligné sur les
# tables de référence du ticket (1 / 2 / 3 / 4+).
SIZE_MAX = 4

# Âge minimum pour porter un vélo. C'est le champ de la question `P20` de l'enquête,
# et ça interdit structurellement d'attribuer le vélo du foyer à un enfant de trois ans.
MIN_AGE_ELIGIBLE = 5

# Âge minimum pour un VAE. Repris du garde-fou existant (ticket 008, A1.a) : le tirage
# sans filtre d'âge attribuait des vélos à assistance électrique à des écoliers.
MIN_AGE_ELECTRIC = 14

# Part de VAE **dans le parc** : `ML21 / M21` sur l'enquête, 7,67 %. Le tirage porte
# donc sur chaque vélo attribué, pas sur chaque personne.
#
# L'erreur que ce chiffre corrige : eqasim appliquait 14,8 %, qui est la part des
# *ménages équipés* possédant au moins un VAE (8 % des ménages / 54 % d'équipés) —
# d'où 1,7× trop de VAE. Une part de ménages n'est pas une part de parc.
#
# À ne pas confondre non plus avec les **12 % de trajets** vélo faits en VAE (rapport
# AUAT p. 26) : l'écart 7,7 → 12 % est un effet d'usage — un VAE roule plus qu'un vélo
# musculaire — pas un effet de stock. Viser 12 % ici serait une erreur de niveau.
VAE_SHARE = 0.0767


# ── Tirages déterministes ────────────────────────────────────────────────────

def address_key(lat: float, lon: float) -> str:
    """Identifiant stable d'une adresse, à 10⁻⁶ degré (~0,1 m).

    Même clé que `core.housing_type.address_key`, et volontairement : l'adresse est
    déjà la clé de ménage du dépôt, celle qui fait qu'un foyer partage un type de
    logement. L'étage 1 n'introduit donc aucune hypothèse nouvelle.
    """
    return f"{float(lat):.6f},{float(lon):.6f}"


def uniform(key: str) -> float:
    """Uniforme sur [0, 1) déterministe, dérivée d'un hachage stable.

    `hash()` de Python est randomisé par processus : il donnerait un parc différent à
    chaque exécution. SHA-256 ne dépend ni de la version, ni de la plateforme, ni de
    `PYTHONHASHSEED`.
    """
    digest = hashlib.sha256(f"{DRAW_SALT}:{key}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2 ** 64


def draw_index(probabilities: Sequence[float], u: float) -> Optional[int]:
    """Inverse de la fonction de répartition. `None` si la loi est vide ou dégénérée.

    Tirer depuis rien rendrait `0` — « pas de vélo » — ce qui est une valeur plausible
    et donc indétectable. C'est exactement le repli silencieux que ce module refuse.

    Le contrôle porte sur un total **fini et strictement positif**, et pas seulement sur
    `total > 0` : un softmax de scores tous infinis rend des `nan`, avec lesquels toutes
    les comparaisons sont fausses. La boucle tombait alors sur son filet d'arrondi et
    rendait la **dernière** classe — soit `k = 4`, un ménage à quatre vélos sorti d'une
    loi vide, sans une ligne de log. C'est le pire des silences possibles ; il est
    détecté par les tests de l'enrichissement.
    """
    total = sum(probabilities)
    if not probabilities or not math.isfinite(total) or total <= 0:
        return None
    threshold = u * total
    cumulated = 0.0
    for index, probability in enumerate(probabilities):
        cumulated += probability
        if threshold < cumulated:
            return index
    return len(probabilities) - 1  # filet d'arrondi flottant : u < 1


# ── Modèles logit, évalués en pur Python ─────────────────────────────────────
# Les deux étages sont servis sous forme de **coefficients**, pas de tables de
# cellules : une table croisant zone × taille × motorisation × k serait creuse (785
# zones) et illisible, là où une trentaine de coefficients se relit et se vérifie à
# l'œil. Les effectifs de cellule, eux, sont publiés par l'exportateur dans le bloc
# `validation` de la ressource — ils servent au contrôle, pas à la prédiction.

def _softmax(scores: Sequence[float]) -> list[float]:
    """Softmax numériquement stable (le décalage par le max évite `exp` qui déborde)."""
    top = max(scores)
    exponentials = [math.exp(s - top) for s in scores]
    total = sum(exponentials)
    return [e / total for e in exponentials]


def _logistic(score: float) -> float:
    """Sigmoïde, écrite pour ne jamais déborder sur les scores très négatifs."""
    if score >= 0:
        return 1.0 / (1.0 + math.exp(-score))
    exponential = math.exp(score)
    return exponential / (1.0 + exponential)


@dataclass(frozen=True)
class LogitModel:
    """Un logit (binaire ou multinomial) réduit à ce qu'il faut pour prédire.

    `features` fixe l'ordre du vecteur de design ; `coefficients` en porte une ligne
    par classe (multinomial) ou une seule (binaire). L'ordre est un **contrat** : une
    ressource écrite pour d'autres features que celles du module est refusée au
    chargement plutôt que d'aligner des coefficients sur les mauvaises colonnes.
    """

    features: tuple[str, ...]
    intercepts: tuple[float, ...]
    coefficients: tuple[tuple[float, ...], ...]
    classes: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.coefficients) != len(self.intercepts):
            raise ValueError(
                f"Logit incohérent : {len(self.coefficients)} lignes de coefficients "
                f"pour {len(self.intercepts)} constantes."
            )
        for row in self.coefficients:
            if len(row) != len(self.features):
                raise ValueError(
                    f"Logit incohérent : ligne de {len(row)} coefficients pour "
                    f"{len(self.features)} features {self.features}."
                )

    def scores(self, design: dict[str, float]) -> list[float]:
        """Scores linéaires, une valeur par ligne de coefficients.

        Une feature absente du design vaut 0 — c'est le sens d'une indicatrice non
        activée, et le seul cas où cela se produit. Les features continues sont
        toujours fournies par les appelants du module.
        """
        return [
            intercept + sum(c * design.get(name, 0.0)
                            for name, c in zip(self.features, row))
            for intercept, row in zip(self.intercepts, self.coefficients)
        ]

    def probabilities(self, design: dict[str, float]) -> list[float]:
        """Loi multinomiale sur `classes`."""
        return _softmax(self.scores(design))

    def probability(self, design: dict[str, float]) -> float:
        """Probabilité de la classe positive d'un logit binaire."""
        if len(self.coefficients) != 1:
            raise ValueError("probability() n'a de sens que pour un logit binaire.")
        return _logistic(self.scores(design)[0])

    @classmethod
    def from_doc(cls, doc: dict) -> "LogitModel":
        return cls(
            features=tuple(str(f) for f in doc["features"]),
            intercepts=tuple(float(v) for v in doc["intercepts"]),
            coefficients=tuple(tuple(float(v) for v in row)
                               for row in doc["coefficients"]),
            classes=tuple(int(c) for c in doc.get("classes") or (1,)),
        )


# ── Vecteurs de design — LE point de contact entraînement / application ──────
# Ces deux fonctions sont la raison d'être du module : elles sont appelées **à
# l'entraînement** par `export_bike_ownership.py` et **à l'application** par
# `enrich_personal_bike.py`. Une seule écriture des features, donc aucune dérive
# possible entre les deux côtés — c'est la leçon du ticket 005 (§3, contrat de
# features) appliquée ici.

def stock_design(household_size: int,
                 number_of_cars: Optional[float],
                 density_hh_km2: Optional[float],
                 dist_center_km: float) -> dict[str, float]:
    """Vecteur de design de l'étage 1 (combien de vélos dans le ménage).

    Aucune covariable individuelle : `k` est un attribut du foyer. `density_hh_km2`
    manque pour les 81 zones fines (sur 785) sans ménage enquêté ; on y substitue la
    médiane du périmètre, portée par la ressource — pas zéro, qui décrirait un désert.
    """
    size = max(1, min(int(household_size), SIZE_MAX))
    cars = 0.0 if number_of_cars is None else float(number_of_cars)
    design = {
        "size2": 1.0 if size == 2 else 0.0,
        "size3": 1.0 if size == 3 else 0.0,
        "size4p": 1.0 if size >= 4 else 0.0,
        "cars1": 1.0 if 0.5 <= cars < 1.5 else 0.0,
        "cars2p": 1.0 if cars >= 1.5 else 0.0,
        "log_density": math.log1p(max(0.0, float(density_hh_km2 or 0.0))),
        "log_dist_center": math.log1p(max(0.0, float(dist_center_km))),
    }
    return design


def propensity_design(k: int,
                      household_size: int,
                      age: Optional[float],
                      gender: Optional[str],
                      main_occupation: Optional[str],
                      density_hh_km2: Optional[float],
                      dist_center_km: float,
                      occupations: Sequence[str]) -> dict[str, float]:
    """Vecteur de design de l'étage 2 (propension à la pratique du vélo).

    **Aucune distance de déplacement**, et c'est une décision, pas un oubli : un stock
    doit être invariant au trajet. Sinon le même agent a un vélo pour la boulangerie et
    plus pour le travail, et le verrou de chaîne de véhicule perd son sens. (`D12` est
    en outre endogène au mode et déjà marquée « contaminée » par la politique de choix
    modal ; `DP15` vaut 0 pour 54,6 % des personnes.)

    `occupations` fixe l'ordre des indicatrices d'occupation : il vient de la ressource,
    pour que le vecteur reste aligné sur les coefficients même si le recodage du dépôt
    gagne une modalité.
    """
    size = max(1, min(int(household_size), SIZE_MAX))
    stock = max(0, min(int(k), K_MAX))
    design = {
        "k1": 1.0 if stock == 1 else 0.0,
        "k2": 1.0 if stock == 2 else 0.0,
        "k3": 1.0 if stock == 3 else 0.0,
        "k4p": 1.0 if stock >= 4 else 0.0,
        "size2": 1.0 if size == 2 else 0.0,
        "size3": 1.0 if size == 3 else 0.0,
        "size4p": 1.0 if size >= 4 else 0.0,
        # Âge en centaines d'années, avec son carré : la pratique du vélo n'est pas
        # monotone en âge (elle culmine chez les scolaires et les jeunes actifs).
        "age": 0.0 if age is None else float(age) / 100.0,
        "age2": 0.0 if age is None else (float(age) / 100.0) ** 2,
        "female": 1.0 if (gender or "") == "Female" else 0.0,
        "log_density": math.log1p(max(0.0, float(density_hh_km2 or 0.0))),
        "log_dist_center": math.log1p(max(0.0, float(dist_center_km))),
    }
    for occupation in occupations:
        design[f"occ_{occupation}"] = 1.0 if main_occupation == occupation else 0.0
    return design


# ── Étage 2 — le tirage sans remise pondéré ──────────────────────────────────

@dataclass(frozen=True)
class Member:
    """Un membre du ménage, tel que l'attribution a besoin de le voir.

    `present = False` désigne une **place absente** : un membre du foyer nominal que le
    filtre spatial n'a pas retenu dans le fichier de population. Ces places concourent
    au tirage et peuvent emporter un vélo, mais rien n'est écrit pour elles.
    """

    index: int
    propensity: float
    eligible: bool
    present: bool = True


def assign(members: Sequence[Member], k: int, household_key: str) -> set[int]:
    """Qui, parmi `members`, tient un des `k` vélos du ménage.

    Tirage sans remise pondéré par la propension, schéma d'**Efraimidis–Spirakis** :
    chaque membre éligible reçoit une clé `u ** (1 / p)` avec `u` uniforme déterministe,
    on classe par clé décroissante, et on sert les `min(k, éligibles)` premiers.

    Trois propriétés voulues :

    - le nombre attribué est **exactement** le stock du ménage — c'est `k` qui fixe le
      niveau, le classement ne fait que hiérarchiser ;
    - la probabilité d'être servi **croît** avec la propension ;
    - il n'y a **aucun ordre déterministe** : pas de « toujours l'aîné », pas d'artefact
      de tri sur les ex æquo. L'index n'entre que dans le hachage.

    Les derniers vélos échoient donc à des membres de faible propension : **ce sont les
    vélos dormants**, et il est juste de les représenter. ~11 points de la population
    tiendront un vélo sans le pratiquer (≈ 51 % de porteurs pour 39,5 % de pratiquants).
    Leur porteur ne les utilisera pas — c'est au modèle de choix modal et à l'agent de
    décider de ne pas les prendre, pas à l'imputation de les faire disparaître.

    Conséquence à assumer : la probabilité d'inclusion réelle de ce schéma n'est pas
    exactement `p_i`, elle est déformée par la contrainte de comptage. La table
    `P(pratique | k, taille)` n'est donc pas une identité mais un **critère de
    validation** — on vérifie après coup que le mécanisme la reproduit.

    Si `k` dépasse le nombre d'éligibles, le surplus n'est porté par personne : un vélo
    est un objet du ménage, et le JSON ne portant que des individus, un vélo sans
    titulaire n'y apparaît simplement pas.
    """
    if k <= 0:
        return set()
    keyed: list[tuple[float, int]] = []
    for member in members:
        if not member.eligible:
            continue
        u = uniform(f"bike-holder:{household_key}:{member.index}")
        # `p = 0` ne doit pas lever : une propension nulle donne la clé la plus basse,
        # donc un service en tout dernier recours — ce qui est le sens voulu, pas une
        # exclusion. `u = 0` (mesure nulle mais atteignable sur 64 bits) idem.
        propensity = max(1e-12, float(member.propensity))
        keyed.append((u ** (1.0 / propensity), member.index))
    keyed.sort(key=lambda pair: (-pair[0], pair[1]))
    return {index for _, index in keyed[:k]}


def electric_probability(under_age_holder_share: float) -> float:
    """Probabilité de VAE à appliquer **aux porteurs éligibles**, pour que le parc sorte
    à `VAE_SHARE`.

    Le filtre d'âge et la part de parc se contredisent si on les applique naïvement.
    `VAE_SHARE` est une part du parc **entier**, enfants compris : `ML21 / M21` ne
    distingue pas à qui est le vélo. Mais aucun VAE n'est attribué sous 14 ans (garde-fou
    du ticket 008 : le tirage sans filtre mettait des vélos à assistance électrique sous
    des écoliers). Appliquer 7,67 % aux seuls 14 ans et plus fait donc sortir le parc
    **en dessous** de la cible, à proportion des vélos tenus par des enfants — mesuré à
    11,8 % des porteurs sur `toulouse_population_1000.json`, soit un parc plafonné à
    6,8 % au lieu de 7,7 %.

    On renormalise : `p = VAE_SHARE / (1 − part_des_porteurs_inéligibles)`. C'est aussi
    la lecture la plus juste de la réalité — un VAE n'est presque jamais un vélo
    d'enfant, donc les 7,67 % du parc sont de fait concentrés sur les vélos d'adultes.

    La part inéligible vient de la ressource — mesurée par l'exportateur en rejouant
    l'attribution **sur l'enquête** (16,2 %) — et non de la population qu'on enrichit,
    dont la part observée diffère (11,8 % sur `toulouse_population_1000.json`). Ce choix
    est délibéré : une probabilité recalculée sur chaque fichier ferait dépendre le type
    de vélo d'un persona du **fichier dans lequel il se trouve**, si bien que le même
    ménage sortirait en VAE dans la population à 1 000 agents et en vélo musculaire dans
    celle à 10 000. Le déterminisme par hachage perdrait tout son sens. On préfère un
    demi-point d'écart sur le parc à un trait qui bouge selon le contexte.

    Bornée à 0,5 : au-delà la renormalisation dépasserait 15 % et signalerait une
    population aberrante plutôt qu'un ajustement légitime.
    """
    share = min(0.5, max(0.0, float(under_age_holder_share)))
    return min(1.0, VAE_SHARE / (1.0 - share))


def bike_label(household_key: str, member_index: int, age: Optional[float],
               electric_p: float = VAE_SHARE) -> str:
    """Étage 3 : quel vélo, pour un porteur déjà retenu par l'étage 2.

    Le tirage porte sur **le vélo**, via la clé (ménage, membre) qui l'identifie —
    puisqu'un porteur tient exactement un vélo. Sel distinct de celui de l'attribution :
    sans quoi le rang de tirage de l'étage 2 et le type de vélo seraient corrélés, et
    les VAE iraient systématiquement aux hautes propensions.

    `electric_p` est la probabilité **conditionnelle aux porteurs éligibles**, telle que
    `electric_probability` la calcule. Le défaut `VAE_SHARE` est le cas dégradé « pas de
    renormalisation » : il sous-produit les VAE, et il n'est là que pour que la fonction
    reste appelable seule dans un test.
    """
    if age is not None and float(age) < MIN_AGE_ELECTRIC:
        return PLAIN_BIKE
    u = uniform(f"bike-kind:{household_key}:{member_index}")
    return ELECTRIC_BIKE if u < electric_p else PLAIN_BIKE


# ── La ressource ─────────────────────────────────────────────────────────────

DEFAULT_RESOURCE = Path(__file__).resolve().parent.parent / "data" / "bike_ownership.json"

# Version de ressource acceptée, au même patron que `residence_zone.RESOURCE_VERSION`
# et `housing_type.MIN_RESOURCE_VERSION` : une ressource écrite pour un autre schéma
# (nouvelle covariable, écrêtage différent) doit être rejetée explicitement au
# chargement, pas chargée silencieusement avec des coefficients mal alignés.
RESOURCE_VERSION = 1

# Features attendues de chaque étage. Le module refuse une ressource écrite pour
# d'autres : des coefficients alignés sur les mauvaises colonnes ne produisent pas
# d'erreur, ils produisent un parc faux.
STOCK_FEATURES: tuple[str, ...] = (
    "size2", "size3", "size4p", "cars1", "cars2p", "log_density", "log_dist_center",
)
PROPENSITY_BASE_FEATURES: tuple[str, ...] = (
    "k1", "k2", "k3", "k4p", "size2", "size3", "size4p",
    "age", "age2", "female", "log_density", "log_dist_center",
)


@dataclass(frozen=True)
class BikeOwnershipModel:
    """Les trois étages, tels qu'on peut les appliquer hors des données sources."""

    stock: LogitModel
    propensity: LogitModel
    occupations: tuple[str, ...]
    median_density: float
    under_age_holder_share: float
    validation: dict
    meta: dict

    @property
    def electric_p(self) -> float:
        """Probabilité de VAE à appliquer aux porteurs de 14 ans et plus."""
        return electric_probability(self.under_age_holder_share)

    @classmethod
    def load(cls, resource: Optional[Path] = None) -> "BikeOwnershipModel":
        """Charge la ressource (seul point d'I/O du module).

        Absence = erreur explicite. Un repli sur une loi d'ensemble produirait un parc
        décorrélé de la géographie et de la taille des foyers, c'est-à-dire exactement
        le biais que ce module existe pour corriger.
        """
        path = Path(resource) if resource else DEFAULT_RESOURCE
        if not path.exists():
            raise FileNotFoundError(
                f"Modèle d'équipement vélo absent : {path}. Produisez-le avec "
                "`make bike-ownership` (python -m scripts.progedo_logit."
                "export_bike_ownership) — il exige les données PROGEDO sous "
                "'data/PROGEDO 2023/' (accès restreint lil-1750)."
            )
        doc = json.loads(path.read_text(encoding="utf-8"))
        version = int(doc.get("version") or 0)
        if version != RESOURCE_VERSION:
            raise ValueError(
                f"Ressource {path} en version {version}, le module attend "
                f"{RESOURCE_VERSION}. Rejouez `make bike-ownership`."
            )
        stock = LogitModel.from_doc(doc["stock"])
        propensity = LogitModel.from_doc(doc["propensity"])
        occupations = tuple(str(o) for o in doc.get("occupations") or ())

        if stock.features != STOCK_FEATURES:
            raise ValueError(
                f"Ressource {path} : étage 1 écrit pour d'autres features que celles "
                f"du module.\n  ressource : {stock.features}\n  module    : "
                f"{STOCK_FEATURES}\nRé-exportez-la (make bike-ownership)."
            )
        expected = PROPENSITY_BASE_FEATURES + tuple(f"occ_{o}" for o in occupations)
        if propensity.features != expected:
            raise ValueError(
                f"Ressource {path} : étage 2 écrit pour d'autres features que celles "
                f"du module.\n  ressource : {propensity.features}\n  module    : "
                f"{expected}\nRé-exportez-la (make bike-ownership)."
            )
        if stock.classes != K_CLASSES:
            raise ValueError(
                f"Ressource {path} : étage 1 écrit pour les classes {stock.classes}, "
                f"le module attend {K_CLASSES} (écrêtage K_MAX={K_MAX})."
            )
        return cls(
            stock=stock,
            propensity=propensity,
            occupations=occupations,
            median_density=float(doc.get("median_density") or 0.0),
            under_age_holder_share=float(doc.get("under_age_holder_share") or 0.0),
            validation=doc.get("validation") or {},
            meta=doc.get("meta") or {},
        )

    # ── Étage 1 ──────────────────────────────────────────────────────────────

    def stock_probabilities(self, household_size: int,
                            number_of_cars: Optional[float],
                            density_hh_km2: Optional[float],
                            dist_center_km: float) -> list[float]:
        """Loi de `k` sur `K_CLASSES` pour un ménage."""
        density = self.median_density if density_hh_km2 is None else density_hh_km2
        return self.stock.probabilities(
            stock_design(household_size, number_of_cars, density, dist_center_km))

    def draw_stock(self, household_size: int,
                   number_of_cars: Optional[float],
                   density_hh_km2: Optional[float],
                   dist_center_km: float,
                   household_key: str) -> Optional[int]:
        """Nombre de vélos d'un ménage, tiré par hachage de sa clé (l'adresse).

        Un tirage **par ménage**, en remplacement de la recopie du donneur ENTD : le
        nombre de vélos cesse d'être indépendant du foyer qui le reçoit, et c'est tout
        l'objet du ticket.
        """
        probabilities = self.stock_probabilities(
            household_size, number_of_cars, density_hh_km2, dist_center_km)
        index = draw_index(probabilities, uniform(f"bike-stock:{household_key}"))
        return None if index is None else K_CLASSES[index]

    # ── Étage 2 ──────────────────────────────────────────────────────────────

    def propensity_of(self, k: int, household_size: int, age: Optional[float],
                      gender: Optional[str], main_occupation: Optional[str],
                      density_hh_km2: Optional[float],
                      dist_center_km: float) -> float:
        """Propension d'une personne à pratiquer le vélo, au sens de `P20`."""
        density = self.median_density if density_hh_km2 is None else density_hh_km2
        return self.propensity.probability(propensity_design(
            k, household_size, age, gender, main_occupation,
            density, dist_center_km, self.occupations))
