"""
core/housing_type.py — Le type de logement du persona, imputé et non inventé.

La référence EMC² ventile les parts modales selon huit axes, dont le **type
d'habitat** (variable `M1` du fichier ménages de l'enquête). Côté simulation, ce
trait n'existe nulle part : ni eqasim ni le recensement mobilisé par la chaîne de
génération ne le portent, et la colonne « Type de logement » du journal de
déplacements était écrite vide (action A2).

**Ce module impute, et il le dit.** Un axe imputé n'a pas le statut d'un axe observé,
et tout ce qui le publie doit le rappeler au lecteur. Trois garde-fous encadrent
l'imputation :

1. **Conditionnée à la géographie.** Un tirage indépendant du lieu produirait des
   grands collectifs en périphérie rurale et fausserait précisément l'axe qu'on
   cherche à mesurer. La loi tirée est celle des **personnes de la zone fine**
   (pondérée par les coefficients de redressement de l'enquête), repliée sur son
   secteur de tirage puis sur l'ensemble du périmètre quand la zone est trop mince.
2. **Déterministe.** Le tirage est une fonction de hachage de l'adresse du domicile,
   pas d'un générateur aléatoire : deux exécutions, deux machines et deux moments
   donnent le même trait pour le même logement. La clé est l'**adresse** et non la
   personne, pour que deux personas d'un même foyer ne se retrouvent pas l'un en
   maison individuelle et l'autre en tour.
3. **Hors couche, on ne devine pas.** Un domicile qui n'est rattaché à aucune zone
   fine (hors périmètre d'enquête) n'a pas de type de logement : la fonction rend
   `None`, et la colonne du journal reste vide — « non renseigné » est une
   information, ce n'est pas une modalité.

La ressource (`llm_module/data/zf_housing_type.json`) est produite par
`scripts/progedo_logit/export_housing_type.py` (`make housing-type`) depuis les
microdonnées d'accès restreint. Comme la couche de zones fines, elle est **hors
dépôt** : son absence est un cas normal, traité par une erreur explicite à l'appel
de `load`, jamais par un tirage de repli silencieux.

Les entrées/sorties sont confinées à `HousingTypeTable.load` ; le reste du module est
pur, conformément au contrat d'architecture de `llm_module.core`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
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

# Sel du tirage. Versionné : le changer rebat toutes les imputations, ce qui doit être
# un acte délibéré et daté, pas un effet de bord.
DRAW_SALT = "housing_type_v1"

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


def draw(shares: Sequence[float], u: float) -> Optional[str]:
    """Inverse de la fonction de répartition sur `MODALITY_KEYS`.

    `shares` suit l'ordre de `MODALITY_KEYS` et somme à 1. Une loi vide ou
    dégénérée (somme nulle) rend `None` plutôt qu'une modalité par défaut : imputer
    depuis rien serait exactement l'invention que ce module refuse.
    """
    total = sum(shares)
    if not shares or total <= 0:
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
    """Loi du type de logement par zone fine, telle que l'enquête la donne.

    `zones` porte une loi déjà lissée pour chaque zone connue de l'enquête ;
    `sectors` et `global_shares` sont les replis, dans cet ordre. Le lissage est fait
    à l'export, pas ici : la table servie est celle qu'on peut relire et vérifier.
    """

    zones: dict[str, tuple[float, ...]]
    sectors: dict[str, tuple[float, ...]]
    global_shares: tuple[float, ...]
    meta: dict

    @classmethod
    def load(cls, resource: Optional[Path] = None) -> "HousingTypeTable":
        """Charge la ressource (seul point d'I/O du module).

        Absence = erreur explicite. Un repli silencieux sur la loi d'ensemble
        produirait un trait décorrélé de la géographie, c'est-à-dire précisément le
        biais que l'imputation existe pour éviter.
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
        return cls(
            zones={str(zf): tuple(float(v) for v in node["shares"])
                   for zf, node in (doc.get("zones") or {}).items()},
            sectors={str(sec): tuple(float(v) for v in node["shares"])
                     for sec, node in (doc.get("sectors") or {}).items()},
            global_shares=tuple(float(v) for v in (doc.get("global") or ())),
            meta=doc.get("meta") or {},
        )

    def shares_for(self, zf: Optional[str]) -> tuple[float, ...]:
        """Loi applicable à une zone fine : la sienne, celle de son secteur, ou celle
        de l'ensemble du périmètre. Zone inconnue (`None`) → loi vide."""
        if zf is None:
            return ()
        zf = str(zf)
        if zf in self.zones:
            return self.zones[zf]
        sector = zf[:SECTOR_PREFIX_LEN]
        if sector in self.sectors:
            return self.sectors[sector]
        return self.global_shares

    def housing_type(self, zf: Optional[str], lat: float, lon: float) -> Optional[str]:
        """Libellé EMC² du logement d'un domicile, ou `None` s'il est hors couche."""
        key = draw(self.shares_for(zf), uniform(address_key(lat, lon)))
        return label_for(key) if key else None
