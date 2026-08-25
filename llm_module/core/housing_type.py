"""
core/housing_type.py — Le type de logement du persona, imputé et non inventé.

La référence EMC² ventile les parts modales selon huit axes, dont le **type
d'habitat** (variable `M1` du fichier ménages de l'enquête). Côté simulation, ce
trait n'existe nulle part : ni eqasim ni le recensement mobilisé par la chaîne de
génération ne le portent, et la colonne « Type de logement » du journal de
déplacements était écrite vide (action A2).

**Ce module impute, et il le dit.** Un axe imputé n'a pas le statut d'un axe observé,
et tout ce qui le publie doit le rappeler au lecteur. Quatre garde-fous encadrent
l'imputation :

1. **Conditionnée à la géographie.** Un tirage indépendant du lieu produirait des
   grands collectifs en périphérie rurale et fausserait précisément l'axe qu'on
   cherche à mesurer. La loi tirée est celle des **ménages de la zone fine** (pondérée
   par les coefficients de redressement de l'enquête), repliée sur son secteur de
   tirage puis sur l'ensemble du périmètre quand la zone est trop mince.
2. **Conditionnée à la taille du ménage** (ticket 019). Dans une même zone, les
   familles sont dans les maisons et les personnes seules dans les appartements : la
   loi de zone seule mélangeait les deux et **aplatissait le gradient**. La loi de
   zone reçoit donc un **levier de taille** estimé au niveau du périmètre, puis on
   renormalise :

       P(M1 = m | zone, taille) ∝ P(M1 = m | zone) × [ P(M1 = m | taille) / P(M1 = m) ]

   Ce transfert de rapport de cotes (*raking* à une dimension) divise par quatre
   l'erreur du mécanisme mesurée à l'intérieur d'EMC², sans déplacer la géographie
   (3,00 → 0,75 point ; § « Ce que le levier fait » plus bas).
3. **Déterministe.** Le tirage est une fonction de hachage de l'adresse du domicile,
   pas d'un générateur aléatoire : deux exécutions, deux machines et deux moments
   donnent le même trait pour le même logement. La clé est l'**adresse** et non la
   personne, pour que deux personas d'un même foyer ne se retrouvent pas l'un en
   maison individuelle et l'autre en tour.
4. **Hors couche, on ne devine pas.** Un domicile qui n'est rattaché à aucune zone
   fine (hors périmètre d'enquête) n'a pas de type de logement : la fonction rend
   `None`, et la colonne du journal reste vide — « non renseigné » est une
   information, ce n'est pas une modalité. Un persona **sans taille de ménage** rend
   `None` de la même façon : servir la loi de zone seule serait exactement le repli
   silencieux, et le gradient aplati, que le ticket 019 supprime.

Ce que le levier fait — mesuré à l'intérieur d'EMC², chaque ménage enquêté recevant la
loi de sa zone corrigée de sa taille, puis comparé à son `M1` réel (part d'individuel
isolé, et erreur absolue moyenne sur les 20 cellules 5 modalités × 4 tailles) :

    taille       observé   zone seule (COEP, avant)   zone COE0 + levier (après)
    1            15,7 %              26,4 %                    14,0 %
    2            46,5 %              41,6 %                    45,6 %
    3            45,5 %              45,3 %                    47,1 %
    4 et +       53,9 %              47,8 %                    55,2 %
    erreur abs. moyenne              3,00 pt                   0,75 pt

La marginale d'ensemble ne bouge pas : 34,7 / 12,9 / 28,2 / 23,6 / 0,6 % observés contre
34,1 / 13,1 / 28,2 / 23,9 / 0,7 % rakés. Le levier déplace les tailles les unes par
rapport aux autres, il ne déplace pas la géographie.

Deux enseignements à ne pas perdre :

- **La pondération n'est pas le sujet.** Passer des poids personnes (`COEP`) aux poids
  ménages (`COE0`) *sans* le levier **dégrade** le résultat (3,00 → 3,76 pt) : la
  pondération personnes compensait partiellement l'absence de taille, par coïncidence.
  Une fois la taille conditionnée, la pondération ménages est la bonne — un ménage tire
  une fois — et la marginale personnes se reconstitue d'elle-même. Ne jamais toucher
  l'une sans l'autre.
- **Le résidu est réel et petit.** Le raké dépasse de 1,2 à 1,6 point aux tailles 3
  et 4+ : l'hypothèse de transfert (le levier de taille est le même dans toutes les
  zones) n'est pas exacte, elle est bonne à 0,75 point. Un levier estimé par secteur de
  tirage est l'amélioration suivante, hors périmètre du ticket 019.

**Piège** : la taille à utiliser est le `household_size` **nominal** du persona, pas le
nombre de membres présents dans le fichier de population. 118 des 498 grappes d'adresse
de `toulouse_population_1000.json` sont partielles (filtrage par bbox) ; tirer sur le
nombre de présents mettrait des familles de quatre dans des lois de personne seule.
Même règle que l'étage 2 du ticket 015.

La ressource (`llm_module/data/zf_housing_type.json`) est produite par
`scripts/progedo_logit/export_housing_type.py` (`make housing-type`) depuis les
microdonnées d'accès restreint. Comme la couche de zones fines, elle est **hors
dépôt** : son absence est un cas normal, traité par une erreur explicite à l'appel
de `load`, jamais par un tirage de repli silencieux. Une ressource `version` 1 (sans
bloc de leviers) est **refusée** au chargement : imputer sans levier serait revenir au
mécanisme que le ticket 019 corrige, en silence.

Les entrées/sorties sont confinées à `HousingTypeTable.load` ; le reste du module est
pur, conformément au contrat d'architecture de `llm_module.core`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

# Modalités, dans l'ordre qui fixe la fonction de répartition du tirage. Les clés sont
# celles de `scripts/data/population/cerema_values.yaml` (`parts_modales_2023.
# type_logement`) : c'est la clé de jointure de la page de synthèse, et elle ne doit
# pas en dévier. Les libellés sont ceux de l'enquête (`M1`), et c'est eux que porte
# `traits_json` puis la colonne « Type de logement » du journal.
#
# `autres` n'est PAS dans la référence : l'enquête le connaît (0,4 % des personnes),
# la ventilation EMC² publiée l'ignore. Il est imputé quand même — l'écraser sur une
# des quatre autres modalités reviendrait à redistribuer 0,4 % de la population sans
# source — et la page le compte hors référentiel, comme elle le fait déjà des
# occupations inconnues.
MODALITIES: tuple[tuple[str, str], ...] = (
    ("individuel_isole", "Individuel isolé"),
    ("individuel_accole", "Individuel accolé"),
    ("petit_habitat_collectif", "Petit habitat collectif"),
    ("grand_habitat_collectif", "Grand habitat collectif"),
    ("autres", "Autres"),
)

MODALITY_KEYS: tuple[str, ...] = tuple(key for key, _ in MODALITIES)
LABEL_BY_KEY: dict[str, str] = dict(MODALITIES)
KEY_BY_LABEL: dict[str, str] = {label: key for key, label in MODALITIES}

# Les quatre modalités effectivement ventilées par la référence EMC².
REFERENCE_KEYS: tuple[str, ...] = MODALITY_KEYS[:4]

# Clé du trait dans `traits_json`. Le persona porte le LIBELLÉ, pas la clé : c'est ce
# que lit le journal de déplacements, et ce qu'un humain relit dans le JSON.
TRAIT_KEY = "housing_type"

# Trait du persona qui porte la taille NOMINALE du ménage (cf. le piège du docstring).
SIZE_TRAIT_KEY = "household_size"

# Écrêtage de la taille du ménage. Quatre classes : 1, 2, 3, 4 et plus. Au-delà,
# l'enquête compte 1 271 ménages de 4+ pour 4 778 personnes seules : découper plus fin
# donnerait des leviers estimés sur quelques dizaines de ménages.
SIZE_MAX = 4

# Sel du tirage. Versionné : le changer rebat toutes les imputations, ce qui doit être
# un acte délibéré et daté, pas un effet de bord. `v2` = conditionnement sur la taille
# du ménage (ticket 019), acté au changelog du 2026-08-21.
DRAW_SALT = "housing_type_v2"

# Version minimale de la ressource. Une v1 ne porte pas les leviers de taille : elle
# est refusée plutôt que servie sans conditionnement.
MIN_RESOURCE_VERSION = 2

# Préfixe du secteur de tirage dans le code de zone fine (`101101000` → `1011`), le
# même découpage que `build_mode_choice_dataset.build_geo` utilise pour l'hypercentre.
SECTOR_PREFIX_LEN = 4

# Ressource par défaut : voisine de la couche de zones fines, même statut hors dépôt.
DEFAULT_RESOURCE = Path(__file__).resolve().parent.parent / "data" / "zf_housing_type.json"


def label_for(key: str) -> Optional[str]:
    """Clé de modalité → libellé EMC². `None` si la clé est inconnue."""
    return LABEL_BY_KEY.get(key)


def key_for(label: str) -> Optional[str]:
    """Libellé EMC² → clé de modalité. `None` si le libellé est inconnu."""
    return KEY_BY_LABEL.get((label or "").strip())


def size_bucket(household_size: Optional[float | str]) -> Optional[int]:
    """Taille nominale du ménage → classe de levier (1, 2, 3, 4 = « 4 et plus »).

    `None` quand la taille est absente ou inexploitable : l'appelant doit alors
    renoncer au trait, pas retomber sur la loi de zone seule.
    """
    if household_size is None:
        return None
    try:
        size = int(household_size)
    except (TypeError, ValueError):
        return None
    if size < 1:
        return None
    return min(size, SIZE_MAX)


def address_key(lat: float, lon: float) -> str:
    """Identifiant stable d'une adresse, à 10⁻⁶ degré (~0,1 m).

    Le tirage porte sur l'adresse et non sur la personne : dans la population
    synthétique, 930 personas se partagent 498 domiciles (jusqu'à 6 par adresse). Les
    faire tirer séparément mettrait des colocataires dans deux logements différents.
    """
    return f"{float(lat):.6f},{float(lon):.6f}"


def uniform(key: str) -> float:
    """Uniforme sur [0, 1) déterministe, dérivée d'un hachage stable.

    `hash()` de Python est randomisé par processus : il donnerait des traits
    différents à chaque exécution. SHA-256 ne dépend ni de la version, ni de la
    plateforme, ni de `PYTHONHASHSEED`.
    """
    digest = hashlib.sha256(f"{DRAW_SALT}:{key}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2 ** 64


def rake(shares: Sequence[float], leverage: Optional[Sequence[float]]) -> tuple[float, ...]:
    """Loi de zone × levier de taille, renormalisée. Levier absent → loi inchangée.

    C'est le transfert de rapport de cotes du ticket 019 : la géographie fixe le
    niveau, la taille du ménage déplace les modalités les unes par rapport aux autres.
    Une modalité de masse nulle dans la zone le reste — le levier ne crée pas de
    logement que l'enquête n'a pas vu à cet endroit.
    """
    # `len` et non la valeur de vérité : la loi peut arriver en tableau numpy depuis
    # l'exportateur, et `not tableau` lève sur plus d'un élément.
    if shares is None or len(shares) == 0:
        return ()
    if leverage is None:
        return tuple(float(v) for v in shares)
    if len(leverage) != len(shares):
        raise ValueError(
            f"Levier de taille de longueur {len(leverage)} appliqué à une loi de "
            f"longueur {len(shares)} : la ressource et le module ont divergé.")
    tilted = [float(s) * float(l) for s, l in zip(shares, leverage)]
    total = sum(tilted)
    if total <= 0:
        return ()
    return tuple(v / total for v in tilted)


def draw(shares: Sequence[float], u: float) -> Optional[str]:
    """Inverse de la fonction de répartition sur `MODALITY_KEYS`.

    `shares` suit l'ordre de `MODALITY_KEYS` et somme à 1. Une loi vide ou
    dégénérée (somme nulle) rend `None` plutôt qu'une modalité par défaut : imputer
    depuis rien serait exactement l'invention que ce module refuse.
    """
    if shares is None or len(shares) == 0:
        return None
    total = sum(shares)
    if total <= 0:
        return None
    threshold = u * total
    cumulated = 0.0
    for key, share in zip(MODALITY_KEYS, shares):
        cumulated += share
        if threshold < cumulated:
            return key
    # Filet numérique : u < 1 garantit qu'on ne sort qu'aux arrondis flottants.
    return MODALITY_KEYS[len(shares) - 1]


@dataclass(frozen=True)
class HousingTypeTable:
    """Loi du type de logement par zone fine et taille de ménage, telle que l'enquête
    la donne.

    `zones` porte une loi déjà lissée pour chaque zone connue de l'enquête ;
    `sectors` et `global_shares` sont les replis, dans cet ordre. Le lissage est fait
    à l'export, pas ici : la table servie est celle qu'on peut relire et vérifier.

    `size_leverage` porte les rapports `P(M1 | taille) / P(M1)` par classe de taille
    (1, 2, 3, 4+), estimés au niveau du **périmètre** : la cellule (zone, taille)
    compte 3 ménages en médiane, servir son rapport brut ferait passer du bruit
    d'échantillonnage pour de la géographie.
    """

    zones: dict[str, tuple[float, ...]]
    sectors: dict[str, tuple[float, ...]]
    global_shares: tuple[float, ...]
    size_leverage: dict[int, tuple[float, ...]]
    meta: dict
    # Le test interne EMC² publié par l'export : c'est lui qui porte les parts
    # observées par taille de ménage, seules cibles opposables à une population
    # enrichie. Vide sur une table construite à la main (tests).
    validation: dict = field(default_factory=dict)

    @classmethod
    def load(cls, resource: Optional[Path] = None) -> "HousingTypeTable":
        """Charge la ressource (seul point d'I/O du module).

        Absence = erreur explicite. Un repli silencieux sur la loi d'ensemble
        produirait un trait décorrélé de la géographie, c'est-à-dire précisément le
        biais que l'imputation existe pour éviter. Ressource antérieure au ticket 019
        (`version` 1, sans leviers) = erreur explicite pour la même raison : elle
        imputerait sans la taille du ménage, sans que rien ne le signale.
        """
        path = Path(resource) if resource else DEFAULT_RESOURCE
        if not path.exists():
            raise FileNotFoundError(
                f"Table du type de logement absente : {path}. Produisez-la avec "
                "`make housing-type` (python -m scripts.progedo_logit."
                "export_housing_type) — elle exige les données PROGEDO sous "
                "'data/PROGEDO 2023/' (accès restreint lil-1750)."
            )
        doc = json.loads(path.read_text(encoding="utf-8"))
        modalities = tuple(doc.get("modalities") or ())
        if modalities != MODALITY_KEYS:
            raise ValueError(
                f"Table {path} écrite pour d'autres modalités que celles du module.\n"
                f"  table  : {modalities}\n  module : {MODALITY_KEYS}\n"
                "Ré-exportez la table (make housing-type)."
            )
        version = int(doc.get("version") or 0)
        if version < MIN_RESOURCE_VERSION:
            raise ValueError(
                f"Table {path} en version {version}, or le module exige la "
                f"{MIN_RESOURCE_VERSION} : elle ne porte pas les leviers de taille de "
                "ménage (ticket 019) et imputerait le logement sur la seule zone fine, "
                "en aplatissant le gradient de taille. Ré-exportez-la "
                "(make housing-type)."
            )
        leverage = {}
        for size, node in (doc.get("size_leverage") or {}).items():
            # Les clés JSON sont des chaînes ; `size_bucket` les convertit.
            bucket = size_bucket(size)
            if bucket is None:
                continue
            leverage[bucket] = tuple(float(v) for v in node["leverage"])
        missing = [size for size in range(1, SIZE_MAX + 1) if size not in leverage]
        if missing:
            raise ValueError(
                f"Table {path} sans levier pour les tailles de ménage {missing} : "
                "l'imputation serait conditionnée pour certains ménages et pas pour "
                "d'autres. Ré-exportez-la (make housing-type)."
            )
        return cls(
            zones={str(zf): tuple(float(v) for v in node["shares"])
                   for zf, node in (doc.get("zones") or {}).items()},
            sectors={str(sec): tuple(float(v) for v in node["shares"])
                     for sec, node in (doc.get("sectors") or {}).items()},
            global_shares=tuple(float(v) for v in (doc.get("global") or ())),
            size_leverage=leverage,
            meta=doc.get("meta") or {},
            validation=doc.get("validation") or {},
        )

    def observed_isolated_share_by_size(self) -> dict[int, float]:
        """Part d'individuel isolé **observée** dans l'enquête, par taille de ménage.

        Cible du critère de recette n° 2 du ticket 019 (15,7 / 46,4 / 45,5 / 53,9 %).
        Vide si la table ne porte pas de bloc de validation.

        Une ligne incomplète est **ignorée**, pas complétée par un défaut : c'est un
        chemin de verdict, et une cible fabriquée à partir d'une clé absente ferait
        juger la population contre du vide. Le contrôle en aval sait dire « cible non
        servie » ; il ne saurait pas rattraper une cible inventée.
        """
        rows = ((self.validation.get("delivered") or {}).get("by_size") or [])
        out: dict[int, float] = {}
        for row in rows:
            size = size_bucket(row.get("size"))
            observed = row.get("individuel_isole_observed_pct")
            if size is not None and observed is not None:
                out[size] = float(observed)
        return out

    def level_for(self, zf: Optional[str]) -> Optional[str]:
        """Niveau de repli servi pour une zone : `zone`, `secteur` ou `perimetre`.

        Publié à chaque enrichissement : c'est ce compte qui dit combien de personas
        ont reçu la loi de leur zone, et combien celle d'un agrégat plus large.
        """
        if zf is None:
            return None
        zf = str(zf)
        if zf in self.zones:
            return "zone"
        if zf[:SECTOR_PREFIX_LEN] in self.sectors:
            return "secteur"
        return "perimetre"

    def zone_shares(self, zf: Optional[str]) -> tuple[float, ...]:
        """Loi géographique d'une zone fine, avant levier de taille : la sienne, celle
        de son secteur, ou celle de l'ensemble du périmètre. Zone inconnue → loi vide."""
        if zf is None:
            return ()
        zf = str(zf)
        if zf in self.zones:
            return self.zones[zf]
        sector = zf[:SECTOR_PREFIX_LEN]
        if sector in self.sectors:
            return self.sectors[sector]
        return self.global_shares

    def shares_for(self, zf: Optional[str],
                   household_size: Optional[float]) -> tuple[float, ...]:
        """Loi applicable à un domicile : celle de sa zone, rakée sur sa taille.

        `household_size` est la taille **nominale** du ménage. Absente, la loi est
        vide : le trait sera `None`, et il vaut mieux un `None` compté qu'un tirage
        dans la loi de zone seule, dont on a mesuré qu'elle aplatit le gradient.
        """
        shares = self.zone_shares(zf)
        if not shares:
            return ()
        bucket = size_bucket(household_size)
        if bucket is None:
            return ()
        return rake(shares, self.size_leverage.get(bucket))

    def housing_type(self, zf: Optional[str], lat: float, lon: float,
                     household_size: Optional[float]) -> Optional[str]:
        """Libellé EMC² du logement d'un domicile, ou `None` s'il est hors couche ou
        sans taille de ménage."""
        key = draw(self.shares_for(zf, household_size),
                   uniform(address_key(lat, lon)))
        return label_for(key) if key else None
