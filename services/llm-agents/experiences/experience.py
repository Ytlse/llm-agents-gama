"""Définition d'une expérience : configuration complète, empreintes, refus, estimation (spec 06).

Une expérience est un fichier YAML dont **tous** les champs sont obligatoires (E1) : aucune valeur
n'est substituée en silence. Ce module ne détient aucune valeur de référence (E17) et n'écrit
aucun littéral d'estimation (E5) : ce qu'il calcule, il en cite la source.
"""

from __future__ import annotations

import csv
import hashlib
import os
import statistics
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from experiences.chemins import racine_depot, racine_llm_agents
from experiences.jeu import Jeu, dependances_courantes, perime
from experiences.nommage import TYPES_LISANT_UN_PROMPT
from experiences.population import InfoPopulation
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

MODE_SANS_SIMULATEUR = "sans_simulateur"
MODE_SIMULATEUR = "simulateur"
POLITIQUES = ("commune", "propre", "aleatoire")
TYPES_DECIDEUR = (
    "passerelle",
    "antigravity",
    "duree_minimale",
    "rejeu",
    "aleatoire",
    "modele",
    "majoritaire_voiture",
    "typesafe",
)
GROUPES_TOLERANCE = ("walk", "bike", "car", "transit", "rail")


class ExperienceInvalide(ValueError):
    """Configuration incomplète ou incohérente — la raison nomme le champ."""


def _racine() -> Path:
    """Racine du dépôt — jamais `parents[2]`, qui vaut `/` dans le conteneur `controller`.

    Le dossier `llm-agents` y est monté sur `/app` : ce module est donc en
    `/app/experiences/`, un niveau plus haut que sur l'hôte. `racine_depot()` s'ancre sur
    `scripts/synthesis`, présent des deux côtés (cf. `chemins.py`).
    """
    return racine_depot()


# Gabarit d'option servi au modèle, RELATIF au dossier `llm-agents` (et non au dépôt) :
# il est livré avec le code, et le conteneur monte `llm-agents` sur `/app`.
GABARIT_OPTION_REL = Path(
    "text_helper/templates/tpl/descriptions/travel_plan_describe_v2.j2"
)


# Plan d'expériences : ratios de jetons mesurés, dernier repli de l'estimation de coût.
# Sous `methode/` — l'oublier faisait rendre `None` en silence (ticket 045, question 3).
CHEMIN_PLAN_EXPERIENCES = (
    racine_depot()
    / "docs"
    / "paper"
    / "methode"
    / "experience_plan"
    / "experiments.yaml"
)


def chemin_gabarit_option() -> Path:
    """Le gabarit d'option effectivement servi, résolu des deux côtés (R5, ticket 045)."""
    return racine_llm_agents() / GABARIT_OPTION_REL


def dossier_experiences() -> Path:
    return Path(os.getenv("EXPERIENCES_DIR") or (_racine() / "data" / "experiences"))


def dossier_jeux() -> Path:
    return Path(os.getenv("JEUX_DIR") or (_racine() / "data" / "jeux"))


# ── Modèle ───────────────────────────────────────────────────────────────────


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PopulationRef(_Strict):
    chemin: str


class JeuRef(_Strict):
    nom: str
    dossier: str | None = None

    def chemin(self) -> Path:
        return Path(self.dossier) if self.dossier else dossier_jeux() / self.nom


class GabaritRef(_Strict):
    categorie: str
    # Variante du prompt système (clé de `prompts:` dans mobility_llm/prompts/prompts.yaml), par
    # exemple `expert_m4` ou `b_min` (prompt minimaliste). None = la variante ACTIVE de la
    # passerelle, celle que la simulation GAMA utilise. Transmise à la passerelle par la requête.
    variante: str | None = None


class DecideurSpec(_Strict):
    type: Literal[
        "passerelle",
        "antigravity",
        "duree_minimale",
        "rejeu",
        "aleatoire",
        "modele",
        "majoritaire_voiture",
        # Ticket 096 — Jev (TypeSafe). Ni passerelle (pas de chat, pas de schéma JSON) ni
        # modèle (rien n'est entraîné ici) : une troisième famille, zéro-shot et calibrée.
        "typesafe",
    ]
    modele: str | None = None
    # Quel bord sert ce modèle : `local` (LM Studio sur cette machine) ou `distant` (une API à
    # quota). Un même identifiant vit parfois des deux côtés — `qwen/qwen3.8-27b` est chez Groq
    # ET dans LM Studio — et le nom du modèle seul ne dit alors pas ce qui a répondu. `None` est
    # la valeur des définitions écrites avant ce champ : elles gardent leur empreinte et leur
    # comportement, et ne sont refusées que si leur modèle est réellement servi des deux côtés.
    portee: Literal["local", "distant"] | None = None
    parametres: dict[str, Any] = Field(default_factory=dict)
    rejeu_de: str | None = None  # dossier d'une exécution archivée (type rejeu)
    graine: int | None = None  # type aléatoire
    artefact: str | None = (
        None  # chemin de l'artefact LightGBM (type modele) ; None → version par défaut
    )

    @field_validator("modele")
    @classmethod
    def _modele_si_passerelle(cls, v, info):
        return v

    def valider(self) -> list[str]:
        erreurs = []
        if self.type in ("passerelle", "antigravity") and not self.modele:
            erreurs.append(
                f"decideur.modele est obligatoire pour un décideur {self.type}"
            )
        if self.type == "rejeu" and not self.rejeu_de:
            erreurs.append(
                "decideur.rejeu_de est obligatoire pour un décideur de rejeu"
            )
        if self.type == "typesafe":
            # Un alias résolu au lancement scellerait une version que l'`experience.yaml` ne
            # porte pas : le refus est la seule façon de garder l'empreinte vraie (S3/S4).
            from experiences.decideur_typesafe import RE_VERSION_FIGEE

            if not self.modele:
                erreurs.append(
                    "decideur.modele est obligatoire pour un décideur typesafe "
                    "(ex. `jev-1.13.0`)"
                )
            elif not RE_VERSION_FIGEE.match(str(self.modele)):
                erreurs.append(
                    f"decideur.modele {self.modele!r} n'est pas une version figée : attendu "
                    "`jev-<majeur>.<mineur>.<correctif>` (ex. `jev-1.13.0`). Les alias "
                    "`jev-latest` et `jev-preview` sont interdits — ils rendraient l'empreinte "
                    "mensongère au premier changement de version, en silence."
                )
        if self.type == "aleatoire" and self.graine is None:
            erreurs.append("decideur.graine est obligatoire pour un décideur aléatoire")
        if self.portee and self.type != "passerelle":
            erreurs.append(
                f"decideur.portee ne vaut que pour un décideur passerelle, pas {self.type!r} "
                f"→ retirez-la"
            )
        return erreurs

    def empreinte(self) -> str:
        # La portée s'AJOUTE en fin de chaîne et seulement si elle est posée : une définition
        # écrite avant ce champ garde l'empreinte exacte qui scelle ses archives. Deux décideurs
        # qui ne diffèrent que par la portée sont bien deux décideurs — deux quantifications du
        # même modèle ne rendent pas les mêmes décisions.
        brut = (
            f"{self.type}|{self.modele or ''}|{sorted(self.parametres.items())}|"
            f"{self.rejeu_de or ''}|{self.graine}|{self.artefact or ''}"
        )
        if self.portee:
            brut += f"|portee={self.portee}"
        return hashlib.sha256(brut.encode("utf-8")).hexdigest()


class Calendrier(_Strict):
    politique: Literal["commune", "propre", "aleatoire"]
    date: str
    graine: int

    @field_validator("date")
    @classmethod
    def _date_iso(cls, v: str) -> str:
        datetime.strptime(v, "%Y-%m-%d")
        return v


class Evenement(_Strict):
    """Incident de réseau ou information extérieure (EF-46). Format figé pour l'évolution GAMA
    (décision 14, 2026-09-06) : la description sera chargée par GAMA ; tant que ce n'est pas le
    cas, une expérience qui porte un événement est refusée au lancement (E6)."""

    type: Literal["incident", "information"]
    jour: int = Field(ge=1)  # jour de l'horizon (1 = premier jour)
    heure_debut: str  # "HH:MM"
    heure_fin: str | None = None  # None = jusqu'à la fin du jour
    cible: dict[str, Any] = Field(
        default_factory=dict
    )  # {ligne: "metro_A"} · {zone: …} · {troncon: …}
    description: str  # texte porté aux agents (contenu, jamais consigne)
    source: str | None = None  # provenance (chemin + empreinte d'un article, etc.)

    @field_validator("heure_debut", "heure_fin")
    @classmethod
    def _hhmm(cls, v):
        if v is not None:
            datetime.strptime(v, "%H:%M")
        return v


class Regroupement(_Strict):
    parallelisme: int = Field(ge=1)


class ToleranceHoraire(_Strict):
    type: Literal["insensible", "heure", "pas"]
    pas_min: int | None = Field(default=None, ge=1)

    @classmethod
    def depuis_yaml(cls, v) -> ToleranceHoraire:
        if isinstance(v, ToleranceHoraire):
            return v
        if isinstance(v, str):
            return cls(type=v)  # type: ignore[arg-type]
        if isinstance(v, dict) and "pas_min" in v and "type" not in v:
            return cls(type="pas", pas_min=int(v["pas_min"]))
        if isinstance(v, dict):
            return cls(**v)
        raise ValueError(f"tolérance horaire illisible : {v!r}")

    def hors_tolerance(self, ecart_s: int, depart_reference_ts: int) -> bool:
        """L'écart réel − référence dépasse-t-il la tolérance du mode (G5) ?"""
        if self.type == "insensible":
            return False
        if self.type == "heure":
            return (depart_reference_ts // 3600) != (
                (depart_reference_ts + ecart_s) // 3600
            )
        return abs(ecart_s) >= int(self.pas_min or 0) * 60


class Experience(_Strict):
    nom: str
    population: PopulationRef
    jeu: JeuRef
    gabarit: GabaritRef
    decideur: DecideurSpec
    mode: Literal["sans_simulateur", "simulateur"]
    calendrier: Calendrier
    horizon_jours: int = Field(ge=1)
    memoire: bool
    evenements: list[Evenement]
    graine_ordre: int
    graine_tirage: int
    regroupement: Regroupement
    tolerances_horaires: dict[str, ToleranceHoraire]
    max_candidats: int = Field(ge=1)
    attente_max_s: int = Field(ge=1)
    # Chaîne des véhicules (ticket 045, R13 ; mécanisme du ticket 040, lot 1). Deux
    # interrupteurs, et SEULEMENT ces deux-là : la POSITION du véhicule (un agent parti en
    # voiture ne peut pas repartir à pied d'ailleurs) et le VERROU de retour (il rentre avec
    # ce qu'il a pris). Jamais la possession, le permis ni l'âge — ce sont des attributs de
    # la personne, présents dans les 21 variables du contrat, que les deux décideurs voient
    # légitimement ; les couper reviendrait à donner une voiture à tout le monde.
    #
    # Dans la DÉFINITION, et pas seulement dans l'environnement : deux exécutions ne
    # différant que par ces drapeaux portaient la même définition, la même signature et le
    # même nom, si bien que rien dans leur trace ne disait laquelle était laquelle.
    vehicule_chaine: bool = True
    verrou_retour: bool = True
    # Troncature du Consideration Set (ticket 077, Hauser & Wernerfelt 1990) :
    # Si True, les options de choix modal < 15 % sont éliminées avant tirage catégoriel.
    troncature_15: bool = False
    derive_de: str | None = None
    # Ancien nom, quand l'expérience a été renommée par la migration du nommage calculé
    # (spec nommage-canonique-experiences, N12). Filiation ≠ renommage : `derive_de` dit
    # « copiée de », `renomme_de` dit « c'est la même, sous son ancien nom ».
    renomme_de: str | None = None
    executions_connues: list[str] = Field(default_factory=list)

    @field_validator("tolerances_horaires", mode="before")
    @classmethod
    def _tolerances(cls, v):
        if not isinstance(v, dict):
            raise ValueError(
                "tolerances_horaires doit être un dictionnaire groupe → tolérance"
            )
        return {k: ToleranceHoraire.depuis_yaml(val) for k, val in v.items()}

    def erreurs_de_coherence(self) -> list[str]:
        erreurs = self.decideur.valider()
        manquants = [g for g in GROUPES_TOLERANCE if g not in self.tolerances_horaires]
        if manquants:
            erreurs.append(f"tolerances_horaires : groupes manquants {manquants}")
        return erreurs

    def sous_dossier_jeu(self) -> str:
        """Nom du sous-dossier selon le jeu de référence (ex. jeu_1000_AAMAS_v6_EN_c)."""
        nom_jeu = self.jeu.nom
        if "v6_c2" in nom_jeu or "c2_20260316" in nom_jeu:
            return "jeu_1000_AAMAS_v6_c2_EN_c"
        if "enquete_058" in nom_jeu or "58_test" in nom_jeu:
            return "jeu_enquete_058_test"
        if "AAMAS_v6" in nom_jeu or "v6_20260316_EN_c" in nom_jeu:
            return "jeu_1000_AAMAS_v6_EN_c"
        return nom_jeu

    def dossier(self) -> Path:
        existant = trouver_dossier_experience(self.nom)
        if existant:
            return existant
        return dossier_experiences() / "regime_nominal" / self.sous_dossier_jeu() / self.nom


def trouver_dossier_experience(nom: str) -> Path | None:
    """Trouve le dossier d'une expérience (recherche directe ou récursive par sous-dossiers)."""
    racine = dossier_experiences()
    # 1. Chemin direct
    direct = racine / nom
    if (direct / "experience.yaml").is_file():
        return direct
    # 2. Sous-dossiers par jeu de test
    if racine.is_dir():
        for f in racine.rglob("experience.yaml"):
            if "archive" in f.parts or ".system_generated" in f.parts:
                continue
            if f.parent.name == nom:
                return f.parent
    return None


def charger_experience(chemin: str | Path) -> Experience:
    """Lit et valide ; une erreur nomme le champ (E1). Aucun défaut implicite."""
    p = Path(chemin)
    if not p.is_file() and not p.is_dir():
        d = trouver_dossier_experience(str(chemin))
        if d:
            p = d / "experience.yaml"
    if p.is_dir():
        p = p / "experience.yaml"
    if not p.is_file():
        raise ExperienceInvalide(f"expérience introuvable : {p}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ExperienceInvalide(f"{p} : YAML illisible ({e})") from e
    try:
        exp = Experience.model_validate(data)
    except ValidationError as e:
        details = "; ".join(
            f"{'.'.join(str(x) for x in err['loc']) or '(racine)'} : {err['msg']}"
            for err in e.errors()
        )
        raise ExperienceInvalide(f"{p.name} : {details}") from e
    erreurs = exp.erreurs_de_coherence()
    if erreurs:
        raise ExperienceInvalide(f"{p.name} : " + "; ".join(erreurs))
    return exp


def experience_vers_dict(exp: Experience) -> dict:
    """Forme YAML/JSON d'une expérience — la même à l'écriture du fichier et dans l'archive."""
    contenu = exp.model_dump(mode="json")
    contenu["tolerances_horaires"] = {
        k: (t.type if t.type != "pas" else {"pas_min": t.pas_min})
        for k, t in exp.tolerances_horaires.items()
    }
    return contenu


def sauver_experience(exp: Experience, dossier: Path | None = None) -> Path:
    d = Path(dossier) if dossier else exp.dossier()
    d.mkdir(parents=True, exist_ok=True)
    chemin = d / "experience.yaml"
    contenu = experience_vers_dict(exp)
    tmp = chemin.with_suffix(".yaml.tmp")
    tmp.write_text(
        yaml.safe_dump(contenu, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    os.replace(tmp, chemin)
    return chemin


def dupliquer(
    exp: Experience, nouveau_nom: str | None = None, **changements
) -> Experience:
    """E4 — copie intégrale, n champs changés, filiation citée.

    Sans `nouveau_nom`, le nom est CALCULÉ depuis les paramètres de la copie (N1) : changer de
    modèle suffit à changer de nom, et une copie qui ne change rien porte le nom de sa source
    — c'est alors la même expérience, et l'appelant doit le dire plutôt que de l'écraser.
    """
    data = exp.model_dump()
    data.update(changements)
    data["nom"] = nouveau_nom or exp.nom
    data["derive_de"] = exp.nom
    data["renomme_de"] = None
    data["executions_connues"] = []
    nouvelle = Experience.model_validate(data)
    erreurs = nouvelle.erreurs_de_coherence()
    if erreurs:
        raise ExperienceInvalide("; ".join(erreurs))
    if nouveau_nom is None:
        from experiences.nommage import nom_canonique

        nouvelle.nom = nom_canonique(experience_vers_dict(nouvelle))
    return nouvelle


# ── Empreintes (E3) ──────────────────────────────────────────────────────────


def variantes_de_prompt() -> list[str]:
    try:
        from mobility_llm import prompt_manager as get_prompt_manager

        return get_prompt_manager().variantes()
    except Exception:  # noqa: BLE001
        return []


def empreinte_gabarit(categorie: str, variante: str | None = None) -> dict:
    """sha256 du texte EFFECTIF servi au modèle, et la liste de ce qu'il couvre.

    Morceaux hachés, dans l'ordre : le prompt système (variante désignée, sinon la variante
    active de la catégorie), le template de catégorie `<categorie>.md.j2` **s'il existe**, et
    le gabarit d'option. `sources` énumère exactement ce qui est entré dans le hachage (R6) :
    un morceau attendu mais absent y figure comme introuvable, il ne disparaît pas en silence.

    Le template de catégorie n'existe dans aucun environnement au 2026-09-11 — le dossier
    `prompts/` de `mobility_llm` ne contient que `prompts.yaml`. La branche est gardée parce
    qu'elle est correcte le jour où un template apparaît, mais elle ne doit pas se lire comme
    une garantie : ce qui est haché aujourd'hui, ce sont deux morceaux.
    """
    morceaux: list[str] = []
    sources: list[str] = []
    try:
        from mobility_llm import prompt_manager as get_prompt_manager

        pm = get_prompt_manager()
        # `verifier_validite=False` : une empreinte se calcule même sur une variante invalidée.
        # Sans quoi les empreintes scellées des exécutions passées cesseraient d'être
        # reproductibles, ce qui est précisément ce que l'invalidation ne doit pas casser.
        systeme = (
            pm.get_system_prompt(categorie, variante, verifier_validite=False) or ""
        )
        morceaux.append(systeme)
        sources.append(
            f"prompts.yaml:{variante}"
            if variante
            else f"prompts.yaml:active.{categorie}"
        )
        template = Path(pm._env.loader.searchpath[0]) / f"{categorie}.md.j2"  # type: ignore[attr-defined]
        if template.is_file():
            morceaux.append(template.read_text(encoding="utf-8"))
            sources.append(str(template.name))
    except Exception as e:  # noqa: BLE001 — sur l'hôte sans llm_module complet, l'empreinte le dit
        morceaux.append(f"indisponible:{e}")
        sources.append("prompt système indisponible")
    # Résolu sous `llm-agents`, jamais sous la racine du dépôt : le conteneur monte
    # `llm-agents` sur `/app`, et l'ancienne résolution y cherchait `/llm-agents/…`.
    # Introuvable, le gabarit sortait du hachage SANS BRUIT — d'où deux empreintes pour un
    # même texte selon l'endroit du lancement (ticket 045, A2).
    gabarit_option = chemin_gabarit_option()
    if gabarit_option.is_file():
        morceaux.append(gabarit_option.read_text(encoding="utf-8"))
        sources.append(gabarit_option.name)
    else:
        # Un morceau promis mais absent se DIT : une empreinte muette d'apparence normale
        # est exactement ce que ce ticket corrige.
        logger.error(
            f"[ALARME] gabarit d'option introuvable : {gabarit_option} — l'empreinte du "
            f"gabarit ne le couvre pas, les exécutions lancées ici ne sont pas comparables "
            f"à celles qui le couvrent (catégorie {categorie!r}, variante {variante!r})"
        )
        morceaux.append(f"introuvable:{gabarit_option.name}")
        sources.append(f"{gabarit_option.name} introuvable")
    empreinte = {
        "categorie": categorie,
        "variante": variante,
        "sha256": hashlib.sha256("\n\x00\n".join(morceaux).encode("utf-8")).hexdigest(),
        "sources": sources,
    }
    # Une exécution lancée sur un gabarit invalidé le dit dans son empreinte. Clés ajoutées
    # SEULEMENT dans ce cas, et hors du sha : une variante valide produit l'empreinte
    # d'avant, au caractère près.
    try:
        bloc = get_prompt_manager().invalidation(variante) if variante else None
    except Exception:  # noqa: BLE001 — l'empreinte ne tombe jamais pour un motif d'invalidation
        bloc = None
    if bloc:
        empreinte["invalide"] = True
        empreinte["invalide_regle"] = bloc.get("regle")
    return empreinte


_REPO_ROOT = racine_depot()
_POLICY_DEFAUT = _REPO_ROOT / "scripts" / "progedo_logit" / "mode_choice_policy.json"


def _sha_fichier(p: Path) -> str | None:
    try:
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    except OSError:
        return None


def _empreinte_decideur(spec: DecideurSpec, gabarit: GabaritRef | None = None) -> dict:
    """Empreinte du décideur. Pour le type `modele`, SCELLE le SHA du FICHIER artefact (R12) :
    relancer avec un autre artefact donne un SHA différent, le même artefact le même SHA."""
    d = {
        "type": spec.type,
        "modele": spec.modele,
        "parametres": dict(spec.parametres),
        "sha256": spec.empreinte(),
    }
    if spec.type == "antigravity":
        d["modele_verifie"] = False
    if spec.type == "typesafe":
        # L'empreinte de gabarit hache la variante ENTIÈRE ; ce qui part chez Jev en est une
        # dérivée (bloc `[Output instructions]` retiré, le type Choice le remplace). Sans ce
        # sha-là, changer la règle d'amputation ne bougerait aucune empreinte et deux
        # exécutions incomparables porteraient la même signature (C2/C3).
        from experiences.decideur_typesafe import sha_instructions

        d["variante"] = getattr(gabarit, "variante", None)
        d["instructions_sha256"] = sha_instructions(
            getattr(gabarit, "categorie", "itinary_multi_agent"),
            getattr(gabarit, "variante", None),
        )
    if spec.type == "modele":
        chemin = Path(spec.artefact) if spec.artefact else _POLICY_DEFAUT
        if not chemin.is_absolute():
            chemin = _REPO_ROOT / chemin
        d["artefact"] = spec.artefact or str(_POLICY_DEFAUT.relative_to(_REPO_ROOT))
        d["artefact_sha256"] = _sha_fichier(chemin)
    return d


def empreintes(
    exp: Experience,
    jeu: Jeu,
    population: InfoPopulation,
    dependances: dict | None = None,
) -> dict:
    deps = dependances if dependances is not None else dependances_courantes()
    return {
        "population": {
            "nom": population.nom,
            "sha256": population.sha256,
            "fichier_sha256": population.fichier_sha256,
            "scellee": population.scellee,
        },
        "jeu": {"nom": jeu.nom, "sha256": jeu.empreinte},
        "gabarit": empreinte_gabarit(exp.gabarit.categorie, exp.gabarit.variante),
        "decideur": _empreinte_decideur(exp.decideur, exp.gabarit),
        "depot": {
            "commit": deps.get("commit"),
            "arbre_propre": deps.get("arbre_propre"),
        },
    }


# ── Périodes couvertes (E9) ──────────────────────────────────────────────────


def _yyyymmdd(s: str) -> date | None:
    try:
        return datetime.strptime(s.strip(), "%Y%m%d").date()
    except (ValueError, AttributeError):
        return None


def periodes_couvertes(
    dossier_gtfs: Path | None = None, csv_meteo: Path | None = None
) -> dict:
    """Bornes lues dans les données : feeds en service (feed_info / calendar / calendar_dates), météo."""
    from settings import settings

    gtfs = Path(dossier_gtfs) if dossier_gtfs else Path(settings.gtfs.gtfs_file)
    bornes: dict[str, tuple[str, str] | None] = {"gtfs": None, "meteo": None}
    dates: list[date] = []
    fi = gtfs / "feed_info.txt"
    if fi.is_file():
        with open(fi, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                d1, d2 = (
                    _yyyymmdd(row.get("feed_start_date", "")),
                    _yyyymmdd(row.get("feed_end_date", "")),
                )
                dates += [d for d in (d1, d2) if d]
    if not dates:
        cal = gtfs / "calendar.txt"
        if cal.is_file():
            with open(cal, newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    dates += [
                        d
                        for d in (
                            _yyyymmdd(row.get("start_date", "")),
                            _yyyymmdd(row.get("end_date", "")),
                        )
                        if d
                    ]
        cd = gtfs / "calendar_dates.txt"
        if cd.is_file():
            with open(cd, newline="", encoding="utf-8-sig") as f:
                dates += [
                    d
                    for d in (_yyyymmdd(r.get("date", "")) for r in csv.DictReader(f))
                    if d
                ]
    if dates:
        bornes["gtfs"] = (min(dates).isoformat(), max(dates).isoformat())
    meteo = (
        Path(csv_meteo)
        if csv_meteo
        else _racine() / "data" / "weather" / "meteo_toulouse_12_mois.csv"
    )
    if meteo.is_file():
        with open(meteo, newline="", encoding="utf-8") as f:
            jours = sorted(r["DATE"] for r in csv.DictReader(f) if r.get("DATE"))
        if jours:
            bornes["meteo"] = (jours[0], jours[-1])
    return bornes


def date_couverte(d: str, bornes: tuple[str, str] | None) -> bool | None:
    """True/False, ou None si la période est inconnue (signalé, pas refusé)."""
    if not bornes:
        return None
    return bornes[0] <= d <= bornes[1]


# ── Refus (E6) ───────────────────────────────────────────────────────────────


def refuser_si_impossible(
    exp: Experience,
    jeu: Jeu,
    population: InfoPopulation,
    *,
    instances_disponibles: list[str] | None = None,
    instances_servantes: list[str] | None = None,
    detail_epuisement: str | None = None,
    perime_accepte: bool = False,
    dependances: dict | None = None,
    periodes: dict | None = None,
) -> tuple[list[str], list[str]]:
    """(refus, avertissements). Un refus dit la raison ET l'action ; aucune exécution n'est créée.

    `instances_disponibles` et `instances_servantes` sont DEUX ensembles distincts (ticket 085,
    lot C) : celles qui ont encore du quota, et celles qui servent ce modèle, quel que soit leur
    quota. Les confondre faisait annoncer « aucune instance ne sert ce modèle » quand le motif
    réel était « le quota du jour n'est pas encore renouvelé ».

    `instances_servantes=None` les confond volontairement : c'est le comportement des appelants
    écrits avant ce lot, dont le message ne bouge pas d'un mot. `detail_epuisement` porte le
    compte requêtes/jour par instance (`MoniteurRessources.raison_epuisement()`), et n'est lu que
    dans la branche d'épuisement.
    """
    refus: list[str] = []
    avert: list[str] = []
    if instances_servantes is None:
        instances_servantes = instances_disponibles

    mismatch = jeu.verifier_population(population)
    if mismatch:
        refus.append(
            f"{mismatch} → préparez un jeu pour cette population (`preparer-jeu`) ou changez de population"
        )
    if not jeu.clos:
        refus.append(
            f"le jeu {jeu.nom!r} n'est pas clos → terminez sa préparation (`preparer-jeu`)"
        )

    if exp.mode == MODE_SANS_SIMULATEUR:
        motifs = []
        if exp.memoire:
            motifs.append("mémoire activée")
        if exp.evenements:
            motifs.append("événement déclaré")
        if exp.horizon_jours > 1:
            motifs.append(f"horizon {exp.horizon_jours} jours")
        if motifs:
            refus.append(
                "ces questions relèvent du mode simulateur ("
                + ", ".join(motifs)
                + ") → mode: simulateur, ou retirez-les"
            )
    if exp.evenements:
        # Ticket 100 — le refus E6 est LEVÉ pour les deux types, le 2026-09-22. Il datait du
        # jour où aucun mécanisme d'événement n'existait dans le code : « refuser vaut mieux
        # qu'un déclencheur fantôme ». Les deux passent désormais par le même canal —
        # `incident` = canal `vecu`, prise `arrivee` ; `information` = canal `lu`, prise
        # `reveil` — et l'exécution est déclarée par `config/evenements/<nom>.yaml`, dont le
        # chargement refuse franchement ce qu'il ne sait pas jouer.
        #
        # ⚠ Ce que l'expérience porte ici reste DESCRIPTIF : c'est la déclaration d'événement
        # qui arme le run, pas ce bloc. Les deux ne doivent pas diverger, et c'est pourquoi le
        # levier `EVENEMENT=` écrit la configuration plutôt que ce format.
        if exp.calendrier.politique != "commune":
            refus.append(
                "un événement exige la politique de calendrier `commune` → calendrier.politique: commune"
            )

    # `TYPES_LISANT_UN_PROMPT` et non une liste recopiée : jusqu'au 2026-09-21, `typesafe`
    # manquait ici, et une expérience Jev se rangeait sans un mot sur une variante inexistante
    # — l'échec ne sortait qu'à la première décision, au milieu d'un run (vérifié ce jour-là
    # sur `prompt_expert_21`, accepté avant d'être écrit dans `prompts.yaml`).
    if exp.decideur.type in TYPES_LISANT_UN_PROMPT and exp.gabarit.variante:
        connues = variantes_de_prompt()
        if connues and exp.gabarit.variante not in connues:
            refus.append(
                f"variante de prompt {exp.gabarit.variante!r} inconnue de la passerelle → l'une de : {', '.join(connues)}, "
                "ou ajoutez-la dans mobility_llm/prompts/prompts.yaml (`prompts:`)"
            )
    if exp.decideur.type == "passerelle" and not exp.decideur.portee:
        # Un modèle servi des DEUX bords sous le même identifiant : sans portée, l'expérience
        # commence sur l'un et finit sur l'autre dès que le quota du distant s'épuise (arrivé
        # deux fois à `exp_qwen38-27b_minper_jtir_t0_nosim` le 2026-09-09), deux quantifications
        # mélangées sous un seul nom. On ne refuse pas l'usage — les deux restent possibles —
        # on refuse de CHOISIR à la place de l'expérimentateur.
        try:
            from experiences.ressources import charger_providers, portees_pour_modele

            par_portee = portees_pour_modele(
                exp.decideur.modele or "", charger_providers()
            )
        except Exception as e:  # noqa: BLE001 — un diagnostic ne bloque jamais un lancement
            par_portee = {}
            avert.append(f"portée non vérifiée ({type(e).__name__}: {e})")
        if len(par_portee) > 1:
            detail = " ; ".join(
                f"{p} : {', '.join(insts)}" for p, insts in par_portee.items()
            )
            refus.append(
                f"le modèle {exp.decideur.modele!r} est servi des deux côtés ({detail}) — deux "
                f"quantifications rendraient des décisions différentes sous un seul nom "
                f"→ précisez `decideur.portee: local` ou `decideur.portee: distant`"
            )

    if (
        exp.decideur.type == "passerelle"
        and instances_disponibles is not None
        and not instances_disponibles
        and instances_servantes
    ):
        # Ticket 085, lot C — le modèle EST servi, mais plus aucune instance n'a de quota. C'est
        # un motif entièrement différent du suivant, et il appelle une action différente :
        # attendre la fenêtre, pas corriger une configuration. Le 2026-09-16, les deux clés
        # gemini 3.5 étaient saines mais leur quota journalier n'était pas encore renouvelé
        # (fenêtre America/Los_Angeles, remise à zéro à 09:00 CEST) — et le refus annonçait que
        # personne ne servait le modèle, juste après l'avoir listé parmi les modèles servis.
        refus.append(
            f"les {len(instances_servantes)} instance(s) qui servent le modèle "
            f"{exp.decideur.modele!r} ({', '.join(instances_servantes)}) sont momentanément "
            f"épuisées"
            + (f" — {detail_epuisement}" if detail_epuisement else "")
            + " → attendez le renouvellement du quota, ou relancez avec --attendre-fenetre"
        )
    if (
        exp.decideur.type == "passerelle"
        and instances_disponibles is not None
        and not instances_disponibles
        and not instances_servantes
    ):
        # Nommer le fichier LU et les modèles qu'il sert : un refus qui renvoie vers
        # « providers.yaml » sans dire lequel a été lu envoie chercher une panne de quota alors
        # que le fichier n'a pas été trouvé (panne du 2026-09-07 : conteneur non recréé après le
        # déplacement du fichier hors du paquet, liste d'instances vide, message muet).
        detail = ""
        try:
            from experiences.ressources import charger_providers, diagnostic_providers

            providers = charger_providers()
            detail = f" — {diagnostic_providers(providers=providers)}"
            servis = sorted(
                {
                    str(c.get("default_model"))
                    for c in providers.values()
                    if c.get("default_model")
                }
            )
            if servis:
                detail += f" ; modèles servis : {', '.join(servis)}"
        except Exception as e:  # noqa: BLE001 — un diagnostic ne doit jamais masquer le refus
            detail = f" — diagnostic indisponible ({type(e).__name__})"
        refus.append(
            f"aucune instance de passerelle ne sert le modèle {exp.decideur.modele!r}{detail} "
            f"→ vérifiez ce fichier et /health"
        )
    if exp.decideur.type == "rejeu":
        src = Path(exp.decideur.rejeu_de or "")
        if not (src / "decisions.jsonl").is_file():
            refus.append(
                f"exécution de rejeu introuvable : {src} → désignez un dossier d'exécution archivée"
            )

    bornes = periodes if periodes is not None else periodes_couvertes()
    for nom, borne in bornes.items():
        ok = date_couverte(exp.calendrier.date, borne)
        if ok is False:
            refus.append(
                f"date {exp.calendrier.date} hors de la période couverte par {nom} ({borne[0]} → {borne[1]}) → choisissez une date couverte"
            )
        elif ok is None:
            avert.append(
                f"période couverte par {nom} inconnue : la date {exp.calendrier.date} n'a pas pu être vérifiée"
            )
    if (
        exp.calendrier.politique == "commune"
        and exp.calendrier.date != jeu.jour_simule
        and exp.calendrier.date not in jeu.jours_equivalents()
    ):
        # Décision 18 : un autre jour joue l'offre de transport de CE jour ; sans simulateur, rien
        # n'est recalculé → on refuse tant que l'équivalence des offres n'a pas été mesurée.
        refus.append(
            f"la date commune {exp.calendrier.date} n'est pas le jour du jeu ({jeu.jour_simule}) et son offre de transport "
            f"n'a pas été mesurée équivalente → `verifier-jours --jeu {jeu.nom} --jour {exp.calendrier.date} --declarer`, "
            f"ou préparez un jeu pour cette date"
        )

    differentes, non_verif = perime(
        jeu, dependances if dependances is not None else dependances_courantes()
    )
    if differentes:
        msg = (
            f"jeu {jeu.nom!r} périmé — dépendances changées : {', '.join(differentes)}"
        )
        if perime_accepte:
            avert.append(msg + " (accepté explicitement)")
        else:
            refus.append(
                msg + " → relancez avec --accepter-perime, ou préparez un nouveau jeu"
            )
    if non_verif:
        avert.append("dépendances non vérifiables : " + ", ".join(non_verif))
    return refus, avert


# ── Estimation (E5) ──────────────────────────────────────────────────────────


def echanges_archives(chemin: Path) -> list[dict]:
    """Les échanges d'un journal de la passerelle, quelle que soit sa mise en forme.

    `llm_exchanges.jsonl` porte l'extension `.jsonl` mais n'en est pas : le rédacteur y
    concatène des objets JSON **indentés** (cf. `llm_gateway/telemetry/logger.py`). Un parseur
    ligne à ligne n'y lit donc rien — silencieusement, chaque ligne étant du JSON invalide.
    On décode en continu avec `raw_decode`, ce qui accepte les deux formes.
    """
    import json

    try:
        texte = chemin.read_text(encoding="utf-8")
    except OSError:
        return []
    decodeur, i, n, objets = json.JSONDecoder(), 0, len(texte), []
    while i < n:
        while i < n and texte[i] in " \t\r\n":
            i += 1
        if i >= n:
            break
        try:
            obj, i = decodeur.raw_decode(texte, i)
        except ValueError:
            # Journal tronqué par un arrêt brutal : on garde ce qui précède plutôt que de tout
            # perdre, et on ne devine pas la suite.
            break
        if isinstance(obj, dict):
            objets.append(obj)
    return objets


def jetons_mesures(
    dossier_experiences_: Path | None, empreinte_gabarit_: str
) -> dict | None:
    """Médiane des jetons par sollicitation sur les exécutions archivées du MÊME gabarit — source citée.

    ⚠ Une ligne du journal décrit une **requête**, pas une sollicitation : le worker y consigne
    les jetons du LOT entier, une fois par appel fournisseur (`log_llm_exchange`, appelé après
    la fusion). Les compter pour un agent multipliait la mesure par le facteur de regroupement
    — relevé le 2026-09-22 : 4 607 jetons d'entrée pour `batch_7cc7ed2c_8`, soit 576 par agent
    et non 4 607. On divise donc par la taille du lot, lue sur l'identifiant (`batch_<hash>_<n>`)
    avec repli sur le nombre de réponses d'agents. Une ligne dont la taille reste illisible est
    **ignorée** : la compter pour un agent serait exactement l'erreur qu'on corrige.
    """
    from llm_gateway.core.batching import taille_de_lot

    racine = (
        Path(dossier_experiences_) if dossier_experiences_ else dossier_experiences()
    )
    if not racine.is_dir():
        return None
    entrees, sorties, sources, ignorees = [], [], [], 0
    for exec_yaml in racine.glob("*/executions/*/execution.yaml"):
        try:
            conf = yaml.safe_load(exec_yaml.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if ((conf.get("empreintes") or {}).get("gabarit") or {}).get(
            "sha256"
        ) != empreinte_gabarit_:
            continue
        for fichier in ("jetons.jsonl", "llm_exchanges.jsonl"):
            chemin = exec_yaml.parent / fichier
            if not chemin.is_file():
                continue
            for j in echanges_archives(chemin):
                if not (j.get("tokens_in") and j.get("tokens_out")):
                    continue
                agents = taille_de_lot(j.get("task_id"))
                if agents is None:
                    reponse = j.get("response")
                    agents = len(reponse) if isinstance(reponse, list) and reponse else None
                if agents is None:
                    ignorees += 1
                    continue
                entrees.append(int(j["tokens_in"]) / agents)
                sorties.append(int(j["tokens_out"]) / agents)
        sources.append(str(exec_yaml.parent.relative_to(racine)))
    if ignorees:
        logger.warning(
            f"[estimation] {ignorees} échange(s) archivé(s) ignoré(s) : taille de lot illisible "
            f"(ni `task_id` en `batch_<hash>_<n>`, ni liste de réponses) — les compter pour un "
            f"agent surestimerait les jetons par sollicitation"
        )
    if not entrees:
        return None
    return {
        "entree": int(statistics.median(entrees)),
        "sortie": int(statistics.median(sorties)),
        "source": (
            f"médiane sur {len(entrees)} requête(s) archivée(s) ramenée(s) à l'agent "
            f"({len(sources)} exécutions, même gabarit)"
        ),
    }


def ratios_du_plan(chemin: Path | None = None) -> dict | None:
    """Jetons par sollicitation annoncés par le plan d'expériences — dernier repli de `estimer`.

    Chaîne de repli, dans l'ordre : jetons fournis à l'appel, sinon médiane des exécutions
    archivées de même gabarit, sinon ces ratios. Tant que des exécutions archivées existaient,
    ce dernier maillon n'était jamais atteint — et il était cassé sans que cela se voie : le
    chemin codé désignait `docs/paper/experience_plan/`, quand le fichier vit sous
    `docs/paper/methode/experience_plan/`. Depuis que le ticket 045 a vidé `data/experiences/`,
    ce maillon est le SEUL, et son silence privait d'estimation tout bras payant — au moment
    précis où l'on décide de dépenser.

    Un fichier introuvable se journalise désormais. Un fichier lisible mais sans ratios rend
    `None` sans bruit : il n'a rien à dire, ce n'est pas une anomalie.
    """
    p = Path(chemin) if chemin else CHEMIN_PLAN_EXPERIENCES
    if not p.is_file():
        logger.warning(
            f"[estimation] plan d'expériences introuvable : {p} — l'estimation de coût perd "
            f"son dernier repli et annoncera « aucune mesure disponible »."
        )
        return None
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    ratios = ((data.get("defaults") or {}).get("gateway_quotas_reference") or {}).get(
        "measured_ratios"
    ) or {}
    if "prompt_tokens_per_trip" not in ratios:
        return None
    return {
        "entree": int(ratios["prompt_tokens_per_trip"]),
        "sortie": int(ratios.get("reply_tokens_per_trip", 0)),
        "source": f"{p.name}: measured_ratios",
    }


def instances_visees(exp: Experience, moniteur=None) -> tuple[dict[str, dict], list[str]]:
    """(providers, instances) que ce décideur solliciterait — du moniteur s'il existe, du fichier sinon.

    `estimer` doit savoir chiffrer sans conteneur : la campagne devise depuis l'hôte, sans
    passerelle joignable (cf. `cli._campagne_estimer`). Sans moniteur on relit donc
    `providers.yaml` directement ; ce qui se perd alors, c'est l'état du jour, pas la capacité.
    """
    if moniteur is not None:
        return (getattr(moniteur, "providers", {}) or {}), list(
            getattr(moniteur, "instances", []) or []
        )
    try:
        from experiences.ressources import charger_providers, instances_pour_modele

        providers = charger_providers()
        return providers, instances_pour_modele(
            exp.decideur.modele or "", providers, exp.decideur.portee
        )
    except Exception as e:  # noqa: BLE001 — un devis dégradé vaut mieux qu'un devis absent
        logger.warning(f"[estimation] instances non résolues ({type(e).__name__}: {e})")
        return {}, []


def estimer(
    exp: Experience, jeu: Jeu, *, moniteur=None, jetons: dict | None = None
) -> dict:
    """Coût prévisionnel, chaque valeur avec sa source. Aucun littéral ici.

    **Deux unités, et c'est leur confusion qui produisait l'erreur** : un DÉPLACEMENT est une
    décision à prendre, une REQUÊTE est un appel fournisseur. La passerelle fusionne plusieurs
    agents par appel — huit, mesuré sur les bras de référence : un bras complet tient en quelque
    310 requêtes, soit à peu près 0,3 jour de quota (ticket 073 § 4). Poser l'égalité en
    annonçait 2 500 et faisait renoncer à des lancements largement finançables.

    Le champ `sollicitations` est conservé tel quel — il compte des déplacements, il en comptait
    déjà — et `requetes` porte la seconde unité, avec trois chiffres dont un seul décide
    (cf. `lots.facteurs`).
    """
    from experiences import lots as L

    couv = jeu.couverture()
    deplacements = couv["deplacements_couverts"]
    attendus = couv["deplacements_attendus"]
    # Un jeu NON CLOS n'a pas encore d'`attendus` à son manifeste : il vaut 0, tandis que les
    # `couverts` se comptent sur l'index en cours de remplissage. La soustraction rendait alors
    # un nombre NÉGATIF de non couverts (`-773` relevé le 2026-09-22), et les « déplacements »
    # annoncés n'étaient que l'avancement du jeu à cet instant — pas la charge du bras. On le
    # dit plutôt que de publier deux chiffres qui n'en sont pas.
    jeu_clos = attendus > 0
    if not jeu_clos:
        logger.warning(
            f"[estimation] jeu {jeu.nom!r} non clos : son manifeste ne déclare aucun déplacement "
            f"attendu. Les {deplacements} déplacements chiffrés ici sont l'AVANCEMENT de sa "
            f"préparation, pas la charge de l'expérience — le devis sera à refaire une fois le "
            f"jeu scellé."
        )
    origine = (
        f"déplacements couverts du jeu {jeu.nom!r}"
        if jeu_clos
        else (
            f"jeu {jeu.nom!r} NON CLOS : avancement de sa préparation à cet instant, "
            f"pas la charge de l'expérience"
        )
    )
    est: dict[str, Any] = {
        "deplacements": {
            "valeur": deplacements,
            "unite": "déplacement",
            "jeu_clos": jeu_clos,
            "source": origine,
        },
        # Nom historique, même valeur, même unité : une sollicitation EST un déplacement.
        # Ce n'est PAS un nombre de requêtes — les appelants qui l'affichaient comme tel
        # doivent lire `requetes` (dashboard, campagne).
        "sollicitations": {
            "valeur": deplacements,
            "unite": "déplacement",
            "source": origine,
        },
        "non_couverts": {
            "valeur": (attendus - deplacements) if jeu_clos else None,
            "source": "jeu" if jeu_clos else "jeu non clos : rien à soustraire",
        },
    }
    if exp.decideur.type != "passerelle":
        sans = f"décideur {exp.decideur.type} : aucune requête fournisseur"
        est["regroupement"] = {"valeur": None, "source": sans}
        est["requetes"] = {"valeur": 0, "unite": "requête fournisseur", "source": sans}
        est["quota"] = {"valeur": None, "source": "décideur local : sans quota"}
        est["jetons"] = {"valeur": None, "source": "décideur local : aucun jeton"}
        return est
    empreinte = empreinte_gabarit(exp.gabarit.categorie, exp.gabarit.variante)["sha256"]
    j = jetons or jetons_mesures(None, empreinte) or ratios_du_plan()

    # ── Du déplacement à la requête ──────────────────────────────────────────
    providers, instances = instances_visees(exp, moniteur)
    reg = L.facteurs(
        providers=providers,
        instances=instances,
        # Le parallélisme ne borne le lot QUE sans simulateur : c'est alors la plateforme qui
        # tient la file (`parallelisme` personnes en vol, déplacements sériels par personne).
        # En mode simulateur, GAMA l'alimente et le bornage ne tient pas.
        parallelisme=(
            exp.regroupement.parallelisme if exp.mode == MODE_SANS_SIMULATEUR else None
        ),
        empreinte_gabarit_=empreinte,
        troncature=bool(getattr(exp, "troncature_15", False)),
        etat_passerelle=getattr(moniteur, "etat", None),
    )
    est["regroupement"] = {**reg, "unite": "agents par requête"}
    prudente = L.requetes(deplacements, reg["prudent"])
    est["requetes"] = {
        "prudente": prudente,
        "attendue": L.requetes(deplacements, reg["attendu"]),
        "plancher": L.requetes(deplacements, reg["plafond"]),
        "unite": "requête fournisseur",
        "decision": "prudente",
        "source": (
            f"{deplacements} déplacements ÷ regroupement ({reg['source']}). Le plancher "
            f"suppose le plafond atteint à chaque requête : il s'affiche, il ne décide pas."
        ),
    }

    if j:
        est["jetons"] = {
            "entree": j["entree"] * deplacements,
            "sortie": j["sortie"] * deplacements,
            "par_sollicitation": {"entree": j["entree"], "sortie": j["sortie"]},
            # Ce que le fournisseur voit passer dans UN appel, au regroupement attendu : c'est
            # ce chiffre-là que ses plafonds par requête arbitrent.
            "par_requete": {
                "entree": int(j["entree"] * reg["attendu"]),
                "sortie": int(j["sortie"] * reg["attendu"]),
                "agents": reg["attendu"],
            },
            "source": j["source"],
        }
    else:
        est["jetons"] = {
            "valeur": None,
            "source": "aucune mesure disponible (ni exécution archivée, ni plan)",
        }
    if moniteur is not None:
        marges = [
            m for m in (moniteur.marge(i) for i in moniteur.instances) if m is not None
        ]
        rpm = sum(
            int(moniteur.providers.get(i, {}).get("rpm_limit") or 0)
            for i in moniteur.instances
        )
        marge_totale = sum(marges) if marges else None
        est["quota"] = {
            "part": (prudente / marge_totale) if marge_totale else None,
            "marge_requetes_jour": marge_totale,
            "instances": list(moniteur.instances),
            "source": (
                "providers.yaml (rpd_limit) + /health (daily_requests), rapportés aux "
                "REQUÊTES prudentes — un quota se compte en requêtes, pas en déplacements"
            ),
        }
        est["duree_s"] = {
            "valeur": (prudente / rpm * 60) if rpm else None,
            "attendue": (est["requetes"]["attendue"] / rpm * 60) if rpm else None,
            "source": "rpm_limit cumulé des instances (providers.yaml) ÷ requêtes",
        }
    return est


__all__ = [
    "GROUPES_TOLERANCE",
    "MODE_SANS_SIMULATEUR",
    "MODE_SIMULATEUR",
    "POLITIQUES",
    "TYPES_DECIDEUR",
    "Calendrier",
    "DecideurSpec",
    "Evenement",
    "Experience",
    "ExperienceInvalide",
    "GabaritRef",
    "JeuRef",
    "PopulationRef",
    "Regroupement",
    "ToleranceHoraire",
    "charger_experience",
    "date_couverte",
    "dossier_experiences",
    "dossier_jeux",
    "dupliquer",
    "echanges_archives",
    "empreinte_gabarit",
    "empreintes",
    "estimer",
    "experience_vers_dict",
    "instances_visees",
    "jetons_mesures",
    "periodes_couvertes",
    "ratios_du_plan",
    "refuser_si_impossible",
    "sauver_experience",
    "variantes_de_prompt",
]
