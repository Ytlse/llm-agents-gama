"""
core/population_reference.py — Le cadrage de la population enquêtée, lu et opposable.

Toute la chaîne de mesure du dépôt compare des parts modales simulées aux cibles de
`cerema_values.yaml`. Cette comparaison n'a de sens que si les deux côtés parlent de
la **même population** et du **même objet compté**. `population_emc2_2023.yaml`
décrit précisément cette population : périmètre, âge minimum, poids de redressement,
découpage en couronnes, structure des ménages.

**Ce module existe parce que ce fichier n'était lu par personne** (ticket 020,
constat C1). Il décrivait un cadrage, il avait l'air d'être une donnée, et
l'essentiel dormait en commentaire. C'est le motif « vacuité » que le projet traque :
une valeur de cadrage sans lecteur est une valeur fausse en attente.

**Ce que ce module garantit, et ce qu'il ne garantit pas.** Il garantit que le fichier
est lisible, complet, et cohérent avec lui-même (les couronnes somment à 453, les
répartitions à 100 %, la taille de ménage est celle du rapport habitants/ménages).
Il ne garantit PAS que les valeurs sont celles de l'enquête : cela se vérifie en les
recalculant depuis les microdonnées ProGEDO, ce que fait
`scripts/data/population/audit_perimetre.py --recompute` — et les microdonnées sont
d'accès restreint, donc absentes d'un poste ou d'un conteneur ordinaire.

**Deux notions à ne jamais confondre**, et c'est le cœur de l'axe A3 du ticket 020 :

- une cible **PERSONNE** (part modale, âge, occupation) se compare à un comptage de
  personnes ou de déplacements — pondération `COEP` côté enquête ;
- une cible **MÉNAGE** (taille, motorisation) se compare à un comptage de ménages —
  pondération `COE0` côté enquête. Une population synthétique est un échantillon de
  personnes : les grands ménages y apparaissent proportionnellement à leur taille.
  Comparer sa moyenne brute à une cible ménage produit un écart FANTÔME. Mesuré sur
  `toulouse_population_1000.json` : 2,71 personnes par ménage en brut contre 2,01 en
  pondérant chaque personne par `1/taille`, pour une cible de 2,08.
  :func:`household_weight` est cette pondération, et elle a un nom pour qu'on ne la
  redécouvre pas une troisième fois.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from loguru import logger

from mobility_core.resources import find_repo_file

# Le cadrage n'est pas recopié dans le paquet : il vit dans le dépôt
# (`scripts/data/population/population_emc2_2023.yaml`) et se cherche via
# `resources.find_repo_file` — variable d'environnement, racine désignée, remontée depuis
# le répertoire courant, puis /app (conteneur `controller`).
REFERENCE_RELATIVE = "scripts/data/population/population_emc2_2023.yaml"
REFERENCE_ENV = "POPULATION_EMC2_REFERENCE"

# Modalités de couronne. Ce sont EXACTEMENT les clés `lieu_residence` de
# `cerema_values.yaml`, à la normalisation d'espace près (`normalize_place`) : le
# classement des agents doit leur être identique, sinon les parts modales par zone se
# comparent à des cibles qui ne désignent pas les mêmes territoires.
# ANGLAIS depuis le ticket 074, et pour une raison précise : la couronne de résidence est
# SERVIE AU MODÈLE dans le récit de persona (« Lives in: 3rd ring »). Tant qu'elle n'était
# qu'une clé de jointure vers l'enquête, sa langue n'engageait personne ; servie au modèle,
# elle relève de la même règle que le reste du prompt.
#
# Les clés de `cerema_values.yaml` (`1ere_couronne`), elles, restent FRANÇAISES : elles
# franchissent une frontière de dépôt (`prompt_calibration/` les lit) et ne sont jamais vues
# par le modèle. La traduction se fait à la frontière, dans `scripts/synthesis/frames.py`.
COURONNES: tuple[str, ...] = ("Toulouse", "1st ring", "2nd ring", "3rd ring")

#: Les modalités d'avant la v6, dans le MÊME ORDRE. Deux usages, et deux seulement : relire une
#: cohorte ou une trace archivée, et relire une ressource générée avant la bascule.
COURONNES_FR: tuple[str, ...] = ("Toulouse", "1ere couronne", "2eme couronne",
                                 "3eme couronne")

#: Ancienne modalité → modalité canonique.
COURONNE_DEPUIS_FR: dict[str, str] = dict(zip(COURONNES_FR, COURONNES))

#: Modalité canonique → identifiant de `cerema_values.yaml` (`lieu_residence`).
COURONNE_VERS_CEREMA: dict[str, str] = {
    "Toulouse": "Toulouse", "1st ring": "1ere_couronne",
    "2nd ring": "2eme_couronne", "3rd ring": "3eme_couronne",
}


def couronne_canonique(valeur: str | None) -> str | None:
    """Modalité de couronne canonique, quelle que soit la langue de la source.

    Lire une cohorte d'avant la bascule sans traduire ferait tomber chaque agent dans
    « modalité inconnue » : une masse entière comptée hors référentiel, sans qu'une seule
    ligne ne manque nulle part.
    """
    if valeur is None:
        return None
    texte = str(valeur).strip()
    return COURONNE_DEPUIS_FR.get(texte, texte or None)

# Hors périmètre n'est PAS une couronne. C'est une cinquième modalité, et lui donner
# un nom est le point : avant le ticket 020, un domicile à 100 km du Capitole était
# classé « 3eme couronne » par le classement métrique et comparé à la cible d'un
# territoire où il n'habite pas.
OUT_OF_PERIMETER = "outside perimeter"

#: La même modalité avant la bascule (ticket 074).
OUT_OF_PERIMETER_FR = "hors périmètre"

# `main_occupation` du persona → modalité de l'ENQUÊTE, telle que les artefacts ajustés
# la nomment (`driving_license.json`, `pt_subscription.json`, `bike_ownership.json`, dont
# les variables s'appellent littéralement `occ_Travail à plein temps`).
#
# POURQUOI CETTE TABLE EXISTE. Ces trois lois sont des artefacts GELÉS : leurs coefficients
# ont été ajustés sur l'enquête, et le nom de leurs variables fait partie de l'ajustement.
# Quand `main_occupation` est passé à l'anglais (ticket 074), le vecteur de design a cessé
# de reconnaître UNE SEULE modalité : toutes les indicatrices sont tombées à zéro, donc
# toute la cohorte dans la modalité de référence. Rien n'a planté — mesuré : l'écart de
# `permis_adultes` à sa cible est passé de 2,52 à 5,23 points et celui de `abonnement_tc`
# de 2,65 à 8,45, sans une ligne de journal.
#
# Les VALEURS sont donc figées avec les artefacts ; seules les clés suivent le persona.
OCCUPATION_ENQUETE: dict[str, str] = {
    # v6 et après
    "Pupil (up to Baccalaureate)": "Scolaire (jusqu'au Bac)",
    "Student": "Étudiant",
    "Full-time worker": "Travail à plein temps",
    "Part-time worker": "Travail à temps partiel",
    "Unemployed / job seeker": "Chômeur/recherche d'emploi",
    "Homemaker": "Personne au foyer",
    "Retired": "Retraité",
    # v5 et avant : l'identité, pour que les cohortes archivées se relisent sans détour.
    "Scolaire (jusqu'au Bac)": "Scolaire (jusqu'au Bac)",
    "Étudiant": "Étudiant",
    "Travail à plein temps": "Travail à plein temps",
    "Travail à temps partiel": "Travail à temps partiel",
    "Chômeur/recherche d'emploi": "Chômeur/recherche d'emploi",
    "Personne au foyer": "Personne au foyer",
    "Retraité": "Retraité",
    "Autre": "Autre",
}


def occupation_enquete(valeur: object) -> str | None:
    """Modalité d'occupation de l'enquête, quelle que soit la langue du persona.

    `None` pour une valeur absente ou hors vocabulaire — l'appelant décide alors, et le
    DIT ; c'est précisément ce que le zéro silencieux des indicatrices ne faisait pas.
    """
    if valeur is None:
        return None
    return OCCUPATION_ENQUETE.get(str(valeur).strip())


# Motif d'activité → libellé de `travel_purposes` du persona, SERVI au modèle.
#
# UNE SEULE définition : elle vivait en double, dans le générateur eqasim et dans
# `fix_minor_traits`, chacun avec un commentaire disant « le même mapping que l'autre ». Les
# traduire d'un seul côté a suffi à les faire diverger — le générateur posait `['Work']`, la
# pré-imputation le réécrivait en `['Travail']`. `mobility_core` est monté dans l'image
# eqasim : les deux côtés lisent la même table au lieu de promettre de rester d'accord.
PURPOSE_LABEL: dict[str, str] = {
    "work": "Work",
    "education": "Education",
    "shop": "Shopping",
}

#: Libellés d'avant la v6, pour relire les populations archivées.
PURPOSE_LABEL_FR: dict[str, str] = {
    "work": "Travail",
    "education": "Etude",
    "shop": "Achats",
}

# Âge minimum de la population cible de l'enquête. Les classes de parts modales
# commencent à `5-9` : un agent de 3 ans tombe dans cette classe sans que rien ne le
# signale (`frames.age_to_cat` teste `a <= 9`). D'où le contrôle explicite.
MIN_AGE = 5


class PopulationReferenceError(ValueError):
    """Cadrage absent, illisible, ou incohérent. Jamais un repli silencieux.

    Il n'y a pas de valeur de repli raisonnable pour un cadrage : servir des
    couronnes qui ne somment pas à 453, ou une taille de ménage qui ne tombe pas,
    laisserait toute la chaîne comparer des populations différentes en silence.
    """


def find_reference() -> Path | None:
    """Premier `population_emc2_2023.yaml` trouvé aux emplacements standards (cf. `resources`)."""
    return find_repo_file(REFERENCE_RELATIVE, env_var=REFERENCE_ENV)


def _require(node: dict, path: str):
    """Descend un chemin pointé, et lève en nommant ce qui manque."""
    cursor = node
    for part in path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            raise PopulationReferenceError(
                f"cadrage incomplet : clé « {path} » absente")
        cursor = cursor[part]
    return cursor


def _check_sums_to(node: dict, path: str, expected: float, tolerance: float) -> None:
    total = sum(float(v) for v in _require(node, path).values())
    if abs(total - expected) > tolerance:
        raise PopulationReferenceError(
            f"cadrage incohérent : « {path} » somme à {total:g}, "
            f"attendu {expected:g} (± {tolerance:g})")


def validate(reference: dict) -> dict:
    """Contrôles internes du cadrage. Lève `PopulationReferenceError` au premier faux.

    Les tolérances ne sont pas du confort : les valeurs publiées par le CEREMA sont
    arrondies au point de pourcentage et au millier, et exiger l'égalité exacte
    ferait échouer un fichier juste.
    """
    _check_sums_to(reference, "population.repartition_par_classe_age", 100, 1.0)
    _check_sums_to(reference, "population.repartition_par_occupation_principale",
                   100, 1.0)
    _check_sums_to(reference,
                   "menages_equipement_voiture.perimetre_2023.repartition_motorisation",
                   100, 1.0)
    _check_sums_to(reference, "enquete.localisation_deplacements", 100, 0.5)

    # Les couronnes couvrent le périmètre, ni plus ni moins.
    decoupage = _require(reference, "territoire.decoupage_concentrique")
    # Le référentiel est un fichier d'ENQUÊTE : ses modalités sont celles de
    # `cerema_values.yaml`, restées françaises (elles franchissent la frontière de
    # `prompt_calibration/`). On les ramène au vocabulaire canonique avant de comparer, plutôt
    # que d'exiger du référentiel qu'il parle la langue du persona.
    noms = [couronne_canonique(str(z["nom"])) for z in decoupage]
    if tuple(noms) != COURONNES:
        raise PopulationReferenceError(
            f"cadrage incohérent : couronnes {noms} au lieu de {list(COURONNES)} — "
            "ce sont les modalités `lieu_residence` de cerema_values.yaml")
    communes = sum(int(z["communes"]) for z in decoupage)
    attendu = int(_require(reference, "territoire.perimetre_2023.communes"))
    if communes != attendu:
        raise PopulationReferenceError(
            f"cadrage incohérent : les couronnes totalisent {communes} communes, "
            f"le périmètre en déclare {attendu}")

    # La taille moyenne de ménage doit tomber du rapport habitants / ménages, sinon
    # l'une des trois valeurs est un chiffre recopié à côté des deux autres.
    totaux = _require(reference, "population.totaux_perimetre_2023")
    ratio = float(totaux["habitants"]) / float(totaux["nombre_menages"])
    declaree = float(totaux["taille_moyenne_menage"])
    if abs(ratio - declaree) > 0.05:
        raise PopulationReferenceError(
            f"cadrage incohérent : taille de ménage déclarée {declaree:.2f}, "
            f"habitants/ménages = {ratio:.2f}")

    # La population cible (5 ans et +) est un sous-ensemble des habitants, et la
    # ventilation par couronne la retrouve.
    cible = float(totaux["habitants_5_ans_et_plus"])
    if not 0.8 * float(totaux["habitants"]) <= cible <= float(totaux["habitants"]):
        raise PopulationReferenceError(
            f"cadrage incohérent : population 5 ans et + ({cible:g}) hors de "
            f"l'intervalle plausible sous {totaux['habitants']:g} habitants")
    par_zone = sum(float(z["habitants_5_ans_et_plus"])
                   for z in _require(reference,
                                     "population.repartition_par_territoire").values())
    if abs(par_zone - cible) / cible > 0.02:
        raise PopulationReferenceError(
            f"cadrage incohérent : la ventilation par couronne totalise {par_zone:g} "
            f"habitants de 5 ans et +, le total en déclare {cible:g}")

    if int(_require(reference, "enquete.methodologie.age_minimum_enquete")) != MIN_AGE:
        raise PopulationReferenceError(
            "cadrage incohérent : `age_minimum_enquete` diverge de "
            f"`MIN_AGE` = {MIN_AGE}, qui est la borne testée par le contrôle d'âge")

    return reference


@lru_cache(maxsize=1)
def population_reference() -> dict:
    """Cadrage validé de la population enquêtée. Mis en cache, lève s'il est absent.

    `population_reference.cache_clear()` permet aux tests de rejouer la résolution.
    """
    path = find_reference()
    if path is None:
        raise PopulationReferenceError(
            "cadrage introuvable : scripts/data/population/population_emc2_2023.yaml. "
            "Contrairement au spec de features, ce fichier est VERSIONNÉ dans le "
            "dépôt — son absence est une anomalie, pas un cas normal.")
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise PopulationReferenceError(f"cadrage illisible ({path}) : {exc}") from exc
    if not isinstance(loaded, dict):
        raise PopulationReferenceError(f"cadrage vide ou mal formé ({path})")
    validate(loaded)
    logger.info(
        f"Cadrage de population lu depuis {path} | "
        f"{_require(loaded, 'territoire.perimetre_2023.communes')} communes, "
        f"{_require(loaded, 'population.totaux_perimetre_2023.habitants_5_ans_et_plus'):,} "
        "habitants de 5 ans et +")
    return loaded


# ── Accès nommés ──────────────────────────────────────────────────────────────
# Un accès nommé plutôt qu'un chemin pointé recopié chez chaque appelant : c'est ce
# qui permet de renommer une clé du YAML sans casser trois consommateurs en silence.

def survey_window() -> tuple[str, str]:
    """Fenêtre de collecte `(début, fin)` en ISO — la saison que les cibles portent."""
    node = _require(population_reference(), "enquete.periode_enquete")
    return str(node["debut"]), str(node["fin"])


def surveyed_weekdays() -> tuple[int, ...]:
    """Jours de la veille enquêtée, 1 = lundi. L'enquête ne compte pas de week-end."""
    return tuple(int(d) for d in
                 _require(population_reference(),
                          "enquete.methodologie.jours_enquetes"))


def couronne_commune_counts() -> dict[str, int]:
    """`couronne → nombre de communes`, du découpage de l'enquête.

    Les clés sont CANONIQUES (anglaises) : le référentiel parle le vocabulaire de l'enquête,
    ses appelants celui du persona. Traduire ici plutôt que chez chacun d'eux évite qu'une
    moitié du dépôt indexe par « 1ere couronne » et l'autre par « 1st ring » — deux
    dictionnaires qui ne se joignent jamais, et dont rien ne dirait qu'ils ne se joignent pas.
    """
    return {couronne_canonique(str(z["nom"])): int(z["communes"]) for z in
            _require(population_reference(), "territoire.decoupage_concentrique")}


def couronne_population_shares() -> dict[str, float]:
    """`couronne → part de la population de 5 ans et + (en %)`.

    C'est la cible de représentativité spatiale (axe A9) : un excès de Toulouse
    tire la part voiture vers le bas de plus de 30 points sans qu'aucun modèle de
    choix ne soit en cause, puisque la cible `voiture` vaut 31 % à Toulouse et 64 %
    en 1ʳᵉ couronne.
    """
    node = _require(population_reference(), "population.repartition_par_territoire")
    order = dict(zip(("toulouse", "premiere_couronne", "deuxieme_couronne",
                      "troisieme_couronne"), COURONNES))
    total = sum(float(v["habitants_5_ans_et_plus"]) for v in node.values())
    return {order[k]: 100.0 * float(v["habitants_5_ans_et_plus"]) / total
            for k, v in node.items() if k in order}


def household_targets() -> dict[str, float]:
    """Cibles MÉNAGE : taille moyenne, motorisation. À pondérer par `1/taille`.

    Voir :func:`household_weight` — comparer ces valeurs à une moyenne brute de
    population synthétique produit un écart fantôme de l'ordre de 30 %.
    """
    reference = population_reference()
    totaux = _require(reference, "population.totaux_perimetre_2023")
    equip = _require(reference,
                     "menages_equipement_voiture.perimetre_2023")
    motor = equip["repartition_motorisation"]
    return {
        "taille_moyenne_menage": float(totaux["taille_moyenne_menage"]),
        "voitures_par_menage": float(equip["voitures_par_menage_moyen"]),
        "sans_voiture_pct": float(motor["sans_voiture"]),
        "une_voiture_pct": float(motor["une_voiture"]),
        "deux_voitures_plus_pct": float(motor["deux_voitures_et_plus"]),
    }


def household_weight(household_size: float | None) -> float:
    """Poids d'une PERSONNE dans un comptage de MÉNAGES : `1 / taille`.

    Une population synthétique échantillonne des personnes. Un ménage de 5 y apparaît
    5 fois, un ménage de 1 une seule fois : la moyenne brute d'un attribut de ménage
    y est donc biaisée par la taille. Pondérer chaque personne par l'inverse de la
    taille de son ménage rend à chaque ménage un poids de 1.

    Taille absente ou non positive → `0.0`, c'est-à-dire *cette personne ne compte
    pas dans une statistique de ménage*. Ce n'est pas un repli dégradé : sans taille
    de ménage, la personne n'a pas de base ménage, et lui en inventer une (1, par
    exemple) fabriquerait un ménage d'une personne qui n'existe pas.
    """
    try:
        size = float(household_size)
    except (TypeError, ValueError):
        return 0.0
    return 1.0 / size if size > 0 else 0.0
