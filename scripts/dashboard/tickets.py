"""Lecture de l'état des tickets de `docs/tickets/`.

Les tickets ne portent pas de champ de statut normalisé : l'état est donc
*déduit* de deux signaux présents dans le texte — les cases à cocher
(`- [x]` / `- [ ]`) et la ligne `**État**` / `**État d'avancement**` — puis
surchargeable dans `scripts/dashboard/tickets_status.yaml`, qui reste la source de
vérité quand elle est renseignée.

Ce fichier est aussi ÉCRIT depuis le tableau de bord (`save_override`) : l'écriture
préserve à l'octet tout ce qui n'est pas l'entrée modifiée — commentaires d'en-tête,
ordre des entrées, notes et style des autres tickets.
"""

from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover — yaml est fourni par le venv du projet
    yaml = None

try:
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap
    from ruamel.yaml.scalarstring import FoldedScalarString
except ImportError:  # pragma: no cover — ruamel est fourni par le venv du projet
    YAML = None

REPO_ROOT = Path(__file__).resolve().parents[2]
TICKETS_DIR = REPO_ROOT / "docs" / "tickets"
OVERRIDES_PATH = Path(__file__).resolve().parent / "tickets_status.yaml"

TODO = "à faire"
DOING = "en cours"
DONE = "terminé"
BLOCKED = "bloqué"
PAUSED = "en veille"
IMPROVEMENT = "amélioration"
DROPPED = "abandonné"
UNKNOWN = "sans statut"

# ── 5 classes majeures de tickets ─────────────────────────────────────────────
CAT_DATA = "Données & Population"
CAT_EXP = "Expériences & Cognition"
CAT_ENG = "Ingénierie & Système"
CAT_STAT = "Modélisation Statistique"
CAT_DOC = "Rédaction & Publication"

CATEGORIES = [
    CAT_DATA,
    CAT_EXP,
    CAT_ENG,
    CAT_STAT,
    CAT_DOC,
]

CATEGORY_ICON = {
    CAT_DATA: "👥",
    CAT_EXP: "🧠",
    CAT_ENG: "⚙️",
    CAT_STAT: "📊",
    CAT_DOC: "📝",
}

# Cartographie de référence des 68 tickets du projet dans les 5 classes majeures
TICKET_CATEGORY_MAPPING: dict[str, str] = {
    # 👥 Données & Population (23 tickets)
    "ticket_015_acces_velo_progedo": CAT_DATA,
    "ticket_016_abonnement_tc_progedo": CAT_DATA,
    "ticket_017_permis_progedo": CAT_DATA,
    "ticket_018_partage_voiture_foyer": CAT_DATA,
    "ticket_019_habitat_taille_menage": CAT_DATA,
    "ticket_020_perimetre_population_cerema": CAT_DATA,
    "ticket_021_couronne_residence_post_traitement": CAT_DATA,
    "ticket_022_rabattement_mode_principal": CAT_DATA,
    "ticket_023_fenetre_meteo_jeux_geles": CAT_DATA,
    "ticket_025_dimension_zone_notee": CAT_DATA,
    "ticket_026_population_conforme_perimetre": CAT_DATA,
    "ticket_027_motif_accompagnement": CAT_DATA,
    "ticket_028_temps_terminal_couronnes_communales": CAT_DATA,
    "ticket_029_selection_par_menage_marges_multiples": CAT_DATA,
    "ticket_030_car_scolaire_synthetique": CAT_DATA,
    "ticket_031_perimetre_453_communes": CAT_DATA,
    "ticket_032_lts_velo_propositions_gama": CAT_DATA,
    "ticket_033_profil_confort_pieton_propositions_gama": CAT_DATA,
    "ticket_034_velo_cle_stable_une_seule_loi": CAT_DATA,
    "ticket_038_licence_des_ressources_emc2_de_mobility_core": CAT_DATA,
    "ticket_045_substrat_unique_v5_et_reconstruction_des_experiences": CAT_DATA,
    "ticket_052_documentation_cohorte_scellee_v5": CAT_DATA,
    "ticket_053_acces_donnees_recherche_et_reproductibilite": CAT_DATA,

    # 🧠 Expériences & Cognition (17 tickets)
    "ticket_004_prompt_calibration_industrialisation": CAT_EXP,
    "ticket_006_relance_run_reference": CAT_EXP,
    "ticket_008_run_24h_mesures_synthese": CAT_EXP,
    "ticket_009_calibration_genetique": CAT_EXP,
    "ticket_014_annexe_prompt_journee": CAT_EXP,
    "ticket_014_anticipation_chaine_journee": CAT_EXP,
    "ticket_024_diversite_et_contexte": CAT_EXP,
    "ticket_040_ablation_filtre_eligibilite_modes": CAT_EXP,
    "ticket_041_etape_3a_hysteresis_longitudinale": CAT_EXP,
    "ticket_048_calendrier_de_consolidation_et_echelle_d_oubli": CAT_EXP,
    "ticket_051_reflexion_architecture_cognitive_memoire": CAT_EXP,
    "ticket_055_benchmark_multimodeles_et_variabilite": CAT_EXP,
    "ticket_056_audit_et_reflexion_resultats_prompt_expert": CAT_EXP,
    "ticket_059_etape_3b_presse_locale_et_predictions_preenregistrees": CAT_EXP,
    "ticket_063_campagne_experimentale_hysteresis_longitudinale": CAT_EXP,
    "ticket_064_campagne_experimentale_presse_locale_et_scoring": CAT_EXP,
    "ticket_068_variabilite_decision_groupe_homogene": CAT_EXP,
    "ticket_072_impact_langue_et_cadrage_culturel_llm": CAT_EXP,
    "ticket_073_reproductibilite_prompt_calibre_multi_graines_multi_populations": CAT_EXP,

    # ⚙️ Ingénierie & Système (13 tickets)
    "ticket_002_snapshot_plan_24h": CAT_ENG,
    "ticket_003_edf_predictive_backpressure": CAT_ENG,
    "ticket_007_procedure_nouveau_run": CAT_ENG,
    "ticket_010_drainage_nocturne_reflexions": CAT_ENG,
    "ticket_011_arrivees_perdues_gama": CAT_ENG,
    "ticket_012_memoisation_reflexions": CAT_ENG,
    "ticket_013_temps_terminal_itineraires": CAT_ENG,
    "ticket_035_plateforme_gestion_experiences_decouplage_spec_fonctionnelle": CAT_ENG,
    "ticket_036_authentification_gateway_llm": CAT_ENG,
    "ticket_037_llm_module_en_trois_bibliotheques": CAT_ENG,
    "ticket_039_organisation_du_depot": CAT_ENG,
    "ticket_070_accidents_aleatoires_sur_les_axes": CAT_ENG,
    "ticket_071_evolution_memoire_du_code_actuel_a_l_etat_vise": CAT_ENG,

    # 📊 Modélisation Statistique (9 tickets)
    "ticket_005_choix_modal_probabiliste": CAT_STAT,
    "ticket_005_mode_choice_model": CAT_STAT,
    "ticket_042_second_oracle_logit_multinomial": CAT_STAT,
    "ticket_043_troisieme_famille_regression_logistique_noyau": CAT_STAT,
    "ticket_044_temoin_random_forest": CAT_STAT,
    "ticket_046_asymetrie_informationnelle_du_contrat_d_evaluation": CAT_STAT,
    "ticket_047_offre_a_mode_unique_ce_qui_compte_comme_decision": CAT_STAT,
    "ticket_057_audit_et_reflexion_double_lecture_tabulaire": CAT_STAT,
    "ticket_058_perimetre_et_methode_audit_unitaire": CAT_STAT,

    # 📝 Rédaction & Publication (10 tickets)
    "ticket_049_itineraire_mixte_limite_a_publier": CAT_DOC,
    "ticket_050_formalisation_mathematique_agent": CAT_DOC,
    "ticket_054_sobriete_computationnelle_prompt_calibration": CAT_DOC,
    "ticket_060_formalisation_architecture_hybride_et_perspectives": CAT_DOC,
    "ticket_061_finalisation_chapitre_9_conclusion": CAT_DOC,
    "ticket_062_revue_et_alignement_des_annexes_techniques": CAT_DOC,
    "ticket_065_consolidation_etat_de_lart_et_harmonisation_bibtex": CAT_DOC,
    "ticket_066_controle_outille_conformite_et_parite_globale": CAT_DOC,
    "ticket_067_relecture_critique_chapitre_par_chapitre_aamas": CAT_DOC,
    "ticket_069_declaration_usage_ia_et_annexe_meta_prompts": CAT_DOC,
}


def infer_category(stem: str) -> str:
    """Déduit la catégorie d'un ticket d'après son identifiant complet."""
    return TICKET_CATEGORY_MAPPING.get(stem, CAT_DATA)

# `en veille` ≠ `bloqué` : rien n'empêche d'avancer, c'est une DÉCISION de ne pas le
# faire maintenant (le travail reprendra tel quel). `bloqué` dit qu'une dépendance
# extérieure manque. Les confondre ferait chercher un déblocage qui n'existe pas.
#
# `amélioration` ≠ `en veille` ≠ `abandonné` : le ticket est CONSERVÉ comme piste
# d'amélioration future, sans travail en cours ni reprise attendue. `en veille` suppose un
# chantier interrompu qui reprendra tel quel ; `abandonné` dit qu'on n'y reviendra pas. Les
# confondre ferait soit chercher un chantier à reprendre, soit jeter une piste gardée exprès.
STATUS_ORDER = [DOING, BLOCKED, TODO, PAUSED, IMPROVEMENT, DONE, DROPPED, UNKNOWN]
STATUS_KIND = {
    DOING: "warning",
    BLOCKED: "critical",
    TODO: "muted",
    PAUSED: "muted",
    IMPROVEMENT: "muted",
    DONE: "good",
    DROPPED: "muted",
    UNKNOWN: "muted",
}
STATUS_ICON = {
    DOING: "🟠",
    BLOCKED: "🔴",
    TODO: "⚪",
    PAUSED: "🔵",
    IMPROVEMENT: "🟣",
    DONE: "🟢",
    DROPPED: "⚫",
    UNKNOWN: "❔",
}

# Ce qu'on peut CHOISIR dans l'interface : le vocabulaire fermé, sans `sans statut`
# qui n'est pas une décision mais l'absence d'entrée (R16).
EDITABLE_STATUSES = [TODO, DOING, DONE, BLOCKED, PAUSED, IMPROVEMENT, DROPPED]

# 4096 est la SEULE largeur de dump pour laquelle les 1 470 lignes existantes se
# relisent et se réécrivent à l'octet (60, 80, 92 et 100 recassent les notes des autres
# tickets). Les notes neuves portent donc leurs propres positions de repli, sinon elles
# tiendraient sur une seule très longue ligne.
_LARGEUR_DUMP = 4096
_LARGEUR_NOTE = 88


class StatutInconnu(ValueError):
    """Le fichier porte une valeur de statut hors vocabulaire."""


class CleInvalide(ValueError):
    """Une clé du fichier ne désigne pas exactement un ticket."""


class TriageInvalide(ValueError):
    """Le bloc `triage` d'un ticket porte une valeur hors bornes ou d'un type inattendu."""


# ── Triage : deux échelles à 5 échelons, et un drapeau ────────────────────────
# LES DEUX ÉCHELLES VONT DANS LE MÊME SENS : cinq étoiles est toujours la bonne
# nouvelle. `faisabilite` 5 = prêt à lancer ; `surete` 5 = aucun risque de régression.
#
# Le champ s'appelle `surete` et non `regression` pour cette raison exacte : une clé
# nommée `regression` valant 5 se lirait « beaucoup de régression », c'est-à-dire
# l'inverse de ce qu'elle dit. Un nom qui contredit son échelle est une erreur de
# lecture qui arrive une fois par relecture, et toujours au mauvais moment.
TRIAGE_MIN = 1
TRIAGE_MAX = 5
TRIAGE_PLEINE = "★"
TRIAGE_VIDE = "☆"
ETOILE_AAMAS_PLEINE = "⭐"
ETOILE_AAMAS_VIDE = "☆"
DRAPEAU_JEUX = "🚩"

# Un quick win : faisable tout de suite ET sans risque de casser l'existant. Le seuil
# est délibérément haut des deux côtés — un « assez faisable, assez sûr » n'est pas un
# quick win, c'est un ticket ordinaire.
SEUIL_QUICK_WIN_FAISABILITE = 4
SEUIL_QUICK_WIN_SURETE = 4


def statut_editable(statut: str) -> str:
    """Le statut à pré-sélectionner dans l'interface (R16).

    `sans statut` n'est pas une décision : il n'est pas proposé. Le sélecteur part alors de
    `à faire`, et l'interface doit dire que ce ticket n'a pas encore d'entrée — sinon rien ne
    distingue « je n'ai pas choisi » de « j'ai choisi à faire ».
    """
    return statut if statut in EDITABLE_STATUSES else TODO


_DONE_RE = re.compile(r"^\s*[-*]\s*\[[xX]\]")
_TODO_RE = re.compile(r"^\s*[-*]\s*\[ \]")
_TITLE_RE = re.compile(r"^#\s+(.*)$")
_STATE_RE = re.compile(r"^\*\*(État[^*:]*)\*\*\s*:\s*(.+)$")
_NUM_RE = re.compile(r"ticket[_-]?(\d+)")


@dataclass
class Triage:
    """L'appréciation portée sur un ticket OUVERT : peut-on le faire, et que risque-t-on ?

    Distincte de `note`, qui dit ce sur quoi le STATUT s'appuie. Le triage dit autre
    chose : ce que coûterait d'y aller maintenant. Les mélanger ferait perdre l'un des
    deux — la note porte l'historique des décisions, et elle ne se réécrit pas parce
    qu'on vient de re-noter la faisabilité.
    """

    faisabilite: int  # 1 = verrou non levé … 5 = prêt à lancer
    surete: int  # 1 = régression majeure probable … 5 = inerte
    jeux_de_test: bool = False  # touche la cohorte scellée, `prompts.yaml` ou le jeu gelé
    date: str = ""  # date de l'appréciation, ISO — une notation vieillit
    motif: str = ""
    aamas: int | None = None  # 1 = hors scope / accessoire … 5 = cœur du papier AAMAS

    @property
    def priorite(self) -> int:
        """Somme des deux échelles, de 2 à 10. Plus c'est haut, plus c'est à prendre.

        La somme n'a de sens QUE parce que les deux échelles vont dans le même sens.
        Si `surete` redevenait un `regression` croissant, il faudrait une soustraction
        et ce serait le premier endroit à casser en silence.
        """
        return self.faisabilite + self.surete

    @property
    def quick_win(self) -> bool:
        return (
            self.faisabilite >= SEUIL_QUICK_WIN_FAISABILITE
            and self.surete >= SEUIL_QUICK_WIN_SURETE
        )

    def etoiles_faisabilite(self) -> str:
        return etoiles(self.faisabilite)

    def etoiles_surete(self) -> str:
        return etoiles(self.surete)

    def etoiles_aamas(self) -> str:
        return etoiles_aamas(self.aamas)

    def date_lisible(self) -> str:
        """La date au format de l'interface (JJ/MM/AAAA), stockée en ISO.

        Rendue telle quelle si elle n'est pas une date ISO : une valeur saisie à la main
        se montre comme elle est plutôt que de disparaître.
        """
        try:
            return datetime.strptime(self.date, "%Y-%m-%d").strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            return self.date


def etoiles(valeur: int) -> str:
    """`3` → `★★★☆☆`. Les cinq positions sont toujours écrites : trois étoiles seules
    ne disent pas sur combien, et la colonne perd son échelle."""
    borne = max(TRIAGE_MIN, min(TRIAGE_MAX, int(valeur)))
    return TRIAGE_PLEINE * borne + TRIAGE_VIDE * (TRIAGE_MAX - borne)


def etoiles_aamas(valeur: int | None) -> str:
    """`3` → `⭐⭐⭐☆☆`. Si None → `—`.

    Utilise des étoiles jaunes (émoji ⭐) pour distinguer visuellement la cote
    d'intérêt de soumission AAMAS des échelles de triage faisabilité / sûreté."""
    if valeur is None:
        return "—"
    borne = max(TRIAGE_MIN, min(TRIAGE_MAX, int(valeur)))
    return ETOILE_AAMAS_PLEINE * borne + ETOILE_AAMAS_VIDE * (TRIAGE_MAX - borne)


@dataclass
class Ticket:
    path: Path
    number: str
    title: str
    status: str
    status_source: str  # "surcharge" | "cases" | "texte" | "défaut"
    done: int
    todo: int
    state_line: str
    note: str
    modified: datetime
    lines: int
    description: str = ""
    category: str = ""
    triage: Triage | None = None  # None = pas encore trié, distinct d'un triage à 1
    aamas_direct: int | None = None

    @property
    def aamas(self) -> int | None:
        if self.triage is not None and self.triage.aamas is not None:
            return self.triage.aamas
        return self.aamas_direct

    @property
    def etoiles_aamas(self) -> str:
        return etoiles_aamas(self.aamas)

    @property
    def total_boxes(self) -> int:
        return self.done + self.todo

    @property
    def progress(self) -> float | None:
        return self.done / self.total_boxes if self.total_boxes else None

    @property
    def rel_path(self) -> str:
        return str(self.path.relative_to(REPO_ROOT))


def _load_overrides() -> dict[str, dict]:
    if yaml is None or not OVERRIDES_PATH.is_file():
        return {}
    data = yaml.safe_load(OVERRIDES_PATH.read_text(encoding="utf-8")) or {}
    tickets = data.get("tickets", data) if isinstance(data, dict) else {}
    return {str(k): (v or {}) for k, v in tickets.items()} if isinstance(tickets, dict) else {}


def _derive_from_text(state_line: str) -> tuple[str, str] | None:
    """Déduit un statut de la ligne `**État**`, quand elle est explicite."""
    low = state_line.lower()
    if any(k in low for k in ("abandonn", "annulé", "annule")):
        return DROPPED, "texte"
    if any(k in low for k in ("bloqué", "bloque ", "en attente de")):
        return BLOCKED, "texte"
    if any(k in low for k in ("aucune correction engagée", "non démarré", "à engager", "à faire")):
        return TODO, "texte"
    if any(k in low for k in ("livré", "livrée", "livrées", "reste ", "en cours")):
        return DOING, "texte"
    if any(k in low for k in ("clos", "terminé", "complet")):
        return DONE, "texte"
    return None


def _nettoyer_markdown(texte: str) -> str:
    """Nettoie les balises markdown d'un extrait pour le rendre lisible en texte brut."""
    texte = re.sub(r"(?m)^\s*>\s*", "", texte)
    texte = re.sub(r"\s+>\s+", " ", texte)
    texte = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", texte)
    texte = re.sub(r"\*\*([^*]+)\*\*", r"\1", texte)
    texte = re.sub(r"\*([^*]+)\*", r"\1", texte)
    texte = re.sub(r"(?<!\w)__([^_]+)__(?!\w)", r"\1", texte)
    texte = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", texte)
    texte = re.sub(r"`([^`]+)`", r"\1", texte)
    return " ".join(texte.split())


def _decouper_phrases(texte: str, min_phrases: int = 2, max_phrases: int = 3, max_chars: int = 450) -> str:
    """Découpe un texte en 2 à 3 phrases complètes maximum sans coupure abrupte."""
    morceaux = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9«\"(—])", texte.strip())
    phrases = []
    for m in morceaux:
        m = m.strip()
        if re.search(r":\s*\d*\.?$", m) or re.match(r"^\d+\.?$", m):
            continue
        if m:
            phrases.append(m)

    if not phrases:
        return texte

    retenues: list[str] = []
    total_len = 0
    for p in phrases:
        retenues.append(p)
        total_len += len(p)
        if len(retenues) >= max_phrases:
            break
        if len(retenues) >= min_phrases and total_len >= max_chars:
            break

    res = " ".join(retenues)
    res = re.sub(r"\s*:\s*\d*\.?$", ".", res)
    return res


def _extraire_description(texte: str, max_phrases: int = 3) -> str:
    """Extrait une description de 2 à 3 phrases maximum du ticket depuis son contenu markdown.

    1. Cherche d'abord une mention explicite de type « Nature du ticket ».
    2. Cherche ensuite une section informative (## Description, ## Objectif(s), ## Constat, ## Contexte...).
    3. À défaut, retient les 2 ou 3 premières phrases informatives sous le titre.
    """
    lignes_brutes = texte.splitlines()

    # Sauter les blocs de citation administratifs initiaux (source de vérité, statut dans...)
    lignes: list[str] = []
    in_status_bq = False
    for l in lignes_brutes:
        s = l.strip()
        if s.startswith(">"):
            if any(k in s.lower() for k in ("source de vérité", "tickets_status.yaml", "statut de ce ticket", "statut dans", "statut :", "statut**")):
                in_status_bq = True
                continue
            if in_status_bq:
                if s == ">":
                    in_status_bq = False
                continue
        else:
            in_status_bq = False
        lignes.append(l)

    # 1. Recherche prioritaire de "Nature du ticket"
    for i, l in enumerate(lignes[:30]):
        if "nature du ticket" in l.lower():
            bloc = [l]
            for suiv in lignes[i + 1 : i + 10]:
                s = suiv.strip()
                if not s or s.startswith("##") or s.startswith("---") or s.startswith("|"):
                    break
                bloc.append(s)
            p_clean = _nettoyer_markdown(" ".join(bloc))
            p_clean = re.sub(r"^Nature du ticket\s*:\s*", "", p_clean, flags=re.IGNORECASE)
            desc = _decouper_phrases(p_clean, max_phrases=max_phrases)
            if desc:
                return desc

    # 2. Section explicite informative
    motif_section = re.compile(
        r"^##\s+(?:(?:\d+\s*[·.]\s*)?(?:Objectifs?|Description|Constat|Le constat|La question|Le problème|Contexte))",
        re.IGNORECASE,
    )
    desc_lignes: list[str] = []
    dans_desc = False
    for l in lignes:
        if motif_section.match(l):
            dans_desc = True
            continue
        elif dans_desc and l.startswith("##"):
            break
        elif dans_desc:
            desc_lignes.append(l)

    if desc_lignes:
        paragraphes = [b.strip() for b in "\n".join(desc_lignes).split("\n\n") if b.strip()]
        texte_brut = []
        for p in paragraphes:
            p_clean = _nettoyer_markdown(p)
            if p_clean and not p_clean.startswith("|") and not p_clean.startswith("-") and not p_clean.startswith("```"):
                texte_brut.append(p_clean)
        if texte_brut:
            desc = _decouper_phrases(" ".join(texte_brut), max_phrases=max_phrases)
            if desc and len(re.split(r"(?<=[.!?])\s+", desc)) >= 2:
                return desc

    # 3. Premier bloc de texte informatif après le titre
    lignes_corps: list[str] = []
    apres_titre = False

    for l in lignes:
        s = l.strip()
        if not apres_titre:
            if s.startswith("# "):
                apres_titre = True
            continue
        if s.startswith(">"):
            if re.match(r"^>\s*Ouvert le \d{4}-\d{2}-\d{2}", s):
                continue
            s = re.sub(r"^>\s*", "", s)
        if s.startswith("---") or s.startswith("***") or s.startswith("|") or s.startswith("```"):
            continue
        if s.startswith("##"):
            if any(k in s.lower() for k in ("changelog", "historique", "décisions", "statut", "avertissement")):
                continue
            if lignes_corps:
                break
            continue
        if not s and not lignes_corps:
            continue
        if not s and lignes_corps:
            corps_actuel = " ".join(lignes_corps)
            morceaux = re.split(r"(?<=[.!?])\s+", corps_actuel)
            if len(morceaux) >= 2:
                break
            continue
        lignes_corps.append(s)

    if lignes_corps:
        p_clean = _nettoyer_markdown(" ".join(lignes_corps))
        p_clean = re.sub(
            r"^(Pourquoi ce ticket|Question posée|Destinataire|Objectif global|Ce qui est livré)\s*:\s*",
            "",
            p_clean,
            flags=re.IGNORECASE,
        )
        return _decouper_phrases(p_clean, max_phrases=max_phrases)

    return ""


def _entier_borne(stem: str, champ: str, brut) -> int:
    """Un échelon de triage, ou un refus qui nomme le ticket et le champ.

    Le fichier s'édite aussi à la main : une valeur hors bornes doit s'annoncer, pas
    se laisser ramener en silence dans l'intervalle. Un `faisabilite: 8` corrigé
    discrètement en 5 ferait lire « prêt à lancer » là où quelqu'un s'est trompé.
    """
    if isinstance(brut, bool) or not isinstance(brut, int):
        raise TriageInvalide(
            f"{stem} : `triage.{champ}` vaut {brut!r} dans {OVERRIDES_PATH.name} — "
            f"attendu un entier de {TRIAGE_MIN} à {TRIAGE_MAX}"
        )
    if not TRIAGE_MIN <= brut <= TRIAGE_MAX:
        raise TriageInvalide(
            f"{stem} : `triage.{champ}` vaut {brut} dans {OVERRIDES_PATH.name} — "
            f"attendu un entier de {TRIAGE_MIN} à {TRIAGE_MAX}"
        )
    return brut


def _lire_triage(stem: str, brut) -> Triage | None:
    if brut is None:
        return None
    if not isinstance(brut, dict):
        raise TriageInvalide(
            f"{stem} : `triage` doit être un bloc de clés dans {OVERRIDES_PATH.name}, "
            f"pas {type(brut).__name__}"
        )
    manquants = [c for c in ("faisabilite", "surete") if c not in brut]
    if manquants:
        raise TriageInvalide(
            f"{stem} : `triage` sans {' ni '.join(f'`{c}`' for c in manquants)} dans "
            f"{OVERRIDES_PATH.name} — les deux échelles sont obligatoires, un triage "
            f"à moitié posé ne se compare à rien"
        )
    drapeau = brut.get("jeux_de_test", False)
    if not isinstance(drapeau, bool):
        raise TriageInvalide(
            f"{stem} : `triage.jeux_de_test` vaut {drapeau!r} dans {OVERRIDES_PATH.name} — "
            f"attendu true ou false"
        )
    aamas_brut = brut.get("aamas")
    aamas = _entier_borne(stem, "aamas", aamas_brut) if aamas_brut is not None else None
    return Triage(
        faisabilite=_entier_borne(stem, "faisabilite", brut["faisabilite"]),
        surete=_entier_borne(stem, "surete", brut["surete"]),
        jeux_de_test=drapeau,
        date=str(brut.get("date", "") or "").strip(),
        motif=str(brut.get("motif", "") or "").strip(),
        aamas=aamas,
    )


def parse_ticket(path: Path, overrides: dict[str, dict]) -> Ticket:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    title = next((m.group(1).strip() for m in map(_TITLE_RE.match, lines) if m), path.stem)
    done = sum(1 for line in lines if _DONE_RE.match(line))
    todo = sum(1 for line in lines if _TODO_RE.match(line))
    state_line = next((m.group(2).strip() for m in map(_STATE_RE.match, lines) if m), "")
    number = (_NUM_RE.search(path.stem) or re.match(r"()", "")).group(1) or "—"

    # 1) cases à cocher — le signal le plus fiable quand il existe
    if done + todo > 0:
        status = DONE if todo == 0 else (TODO if done == 0 else DOING)
        source = "cases"
    # 2) ligne d'état explicite
    elif (derived := _derive_from_text(state_line)) is not None:
        status, source = derived
    else:
        status, source = UNKNOWN, "défaut"

    # 3) surcharge manuelle : elle gagne toujours
    # Clé = nom de fichier complet, et rien d'autre : `_verifier_cles` a déjà refusé le
    # reste. Résoudre une forme courte appliquerait un seul statut à deux tickets.
    override = overrides.get(path.stem) or {}
    note = str(override.get("note", "") or "")
    description = str(override.get("description", "") or "").strip()
    if not description:
        description = _extraire_description(text)
    category = str(override.get("category", "") or "").strip()
    if not category:
        category = infer_category(path.stem)

    aamas_direct_val = override.get("aamas")
    aamas_direct = (
        _entier_borne(path.stem, "aamas", aamas_direct_val)
        if aamas_direct_val is not None
        else None
    )

    if override.get("status"):
        override_status = str(override["status"])
        if override_status not in STATUS_ICON:
            raise StatutInconnu(
                f"{path.stem} : statut de surcharge inconnu {override_status!r} dans "
                f"{OVERRIDES_PATH.name} — attendu l'un de {EDITABLE_STATUSES}"
            )
        status, source = override_status, "surcharge"

    return Ticket(
        path=path,
        number=number,
        title=title,
        status=status,
        status_source=source,
        done=done,
        todo=todo,
        state_line=state_line,
        note=note,
        modified=datetime.fromtimestamp(path.stat().st_mtime),
        lines=len(lines),
        description=description,
        category=category,
        triage=_lire_triage(path.stem, override.get("triage")),
        aamas_direct=aamas_direct,
    )


def _verifier_cles(overrides: dict[str, dict], stems: set[str]) -> None:
    """Toute clé du fichier doit désigner exactement un ticket (R28).

    Deux pièges, tous deux silencieux aujourd'hui : une clé mal orthographiée ne
    s'applique à rien — on croit avoir posé un statut qui n'est nulle part —, et une
    clé COURTE (`ticket_005`) s'applique aux DEUX tickets qui portent ce numéro, alors
    qu'ils sont distincts. L'écriture depuis l'interface n'en produit pas, mais le
    fichier s'édite aussi à la main.
    """
    inconnues = sorted(cle for cle in overrides if cle not in stems)
    if not inconnues:
        return
    details = []
    for cle in inconnues:
        vises = sorted(s for s in stems if s == cle or s.startswith(f"{cle}_") or _NUM_RE.search(s) and cle == _NUM_RE.search(s).group(1))
        details.append(f"{cle!r} → {', '.join(vises) if vises else 'aucun ticket'}")
    raise CleInvalide(
        f"{OVERRIDES_PATH.name} : {len(inconnues)} clé(s) ne désignent pas exactement un ticket "
        f"({'; '.join(details)}). La clé est le nom de fichier complet, sans extension."
    )


def load_tickets() -> list[Ticket]:
    if not TICKETS_DIR.is_dir():
        return []
    overrides = _load_overrides()
    chemins = sorted(TICKETS_DIR.glob("ticket_*.md"))
    _verifier_cles(overrides, {p.stem for p in chemins})
    tickets = [parse_ticket(p, overrides) for p in chemins]
    rank = {s: i for i, s in enumerate(STATUS_ORDER)}
    return sorted(tickets, key=lambda t: (rank.get(t.status, 99), t.number))


def summary(tickets: list[Ticket]) -> dict[str, int]:
    counts = {s: 0 for s in STATUS_ORDER}
    for t in tickets:
        counts[t.status] = counts.get(t.status, 0) + 1
    return counts


def summary_by_category(tickets: list[Ticket]) -> dict[str, int]:
    counts = {c: 0 for c in CATEGORIES}
    for t in tickets:
        counts[t.category] = counts.get(t.category, 0) + 1
    return counts


# Ce qui est CLOS ne se trie pas : on ne se demande pas si un ticket terminé est
# faisable. Les tuiles et le compte des non triés portent donc sur ce seul périmètre.
STATUTS_OUVERTS = [DOING, BLOCKED, TODO, PAUSED, IMPROVEMENT]


def est_ouvert(ticket: Ticket) -> bool:
    return ticket.status in STATUTS_OUVERTS


TOUS_STATUTS = "Tous les statuts"
TOUTES_CATEGORIES = "Toutes les catégories"

# Les tris du tableau. Les non triés tombent en fin de liste quel que soit le critère
# (clé −1, ou 99 quand on classe par risque) : un ticket sans appréciation n'est ni
# prioritaire ni sûr, il est inconnu — et le mettre en tête ferait croire l'inverse.
TRIS = {
    "N° de ticket": None,
    "Priorité (faisa. + sûreté)": lambda t: -(t.triage.priorite if t.triage else -1),
    "Intérêt AAMAS ↓": lambda t: -(t.aamas if t.aamas is not None else -1),
    "Faisabilité ↓": lambda t: -(t.triage.faisabilite if t.triage else -1),
    "Sûreté ↓": lambda t: -(t.triage.surete if t.triage else -1),
    "Risque de régression ↓": lambda t: (t.triage.surete if t.triage else 99),
}


STATUTS_OUVERTS_ACTIFS = [DOING, BLOCKED, TODO, PAUSED]


def filtrer(
    tickets: list[Ticket],
    statut: str = TOUS_STATUTS,
    categorie: str = TOUTES_CATEGORIES,
    drapeaux_seuls: bool = False,
    recherche: str = "",
    ordre: str = "N° de ticket",
    ouverts_seuls: bool = False,
) -> list[Ticket]:
    """Le filtrage et le tri du tableau, hors de Streamlit pour être testables.

    Laissés dans `render_tickets`, ils n'étaient vérifiables qu'en pilotant un widget
    dans un navigateur — ce qui ne tient pas en CI, et ce qui laisserait passer une
    inversion de drapeau sans que rien ne rougisse.
    """
    retenus = list(tickets)
    if ouverts_seuls:
        retenus = [t for t in retenus if t.status in {DOING, BLOCKED, TODO, PAUSED}]
    if statut != TOUS_STATUTS:
        retenus = [t for t in retenus if t.status == statut]
    if categorie != TOUTES_CATEGORIES:
        retenus = [t for t in retenus if t.category == categorie]
    if drapeaux_seuls:
        retenus = [t for t in retenus if t.triage is not None and t.triage.jeux_de_test]
    if recherche:
        aiguille = recherche.strip().lower()
        retenus = [
            t for t in retenus
            if (
                aiguille in t.title.lower()
                or aiguille in t.number.lower()
                or aiguille in t.description.lower()
                or aiguille in t.category.lower()
                or aiguille in t.note.lower()
                or (t.triage is not None and aiguille in t.triage.motif.lower())
            )
        ]
    cle = TRIS.get(ordre)
    return sorted(retenus, key=cle) if cle is not None else retenus


def summary_triage(tickets: list[Ticket]) -> dict[str, int]:
    """Compte, sur les seuls tickets ouverts : drapeaux, quick wins, non triés."""
    ouverts = [t for t in tickets if est_ouvert(t)]
    return {
        "ouverts": len(ouverts),
        "jeux_de_test": sum(1 for t in ouverts if t.triage and t.triage.jeux_de_test),
        "quick_wins": sum(1 for t in ouverts if t.triage and t.triage.quick_win),
        "non_tries": sum(1 for t in ouverts if t.triage is None),
    }


# ── Écriture du statut ────────────────────────────────────────────────────────
def _rt_yaml():
    """Le lecteur/écrivain round-trip : il conserve commentaires, ordre et style."""
    if YAML is None:  # pragma: no cover — ruamel est fourni par le venv du projet
        raise RuntimeError(
            "ruamel.yaml est requis pour écrire les statuts de tickets "
            "(pip install ruamel.yaml dans services/llm-agents/.venv)"
        )
    parseur = YAML()
    parseur.preserve_quotes = True
    parseur.width = _LARGEUR_DUMP
    return parseur


def _normaliser_note(note: str) -> str:
    """Le texte tel qu'il sera STOCKÉ : espaces d'un paragraphe réduits, paragraphes gardés.

    L'écriture et la comparaison doivent normaliser pareil, sinon une retouche purement
    cosmétique produit un diff, et l'interface annonce « rien à enregistrer » pour un texte
    qu'elle vient de recevoir.
    """
    paragraphes = [" ".join(bloc.split()) for bloc in re.split(r"\n\s*\n", note.strip()) if bloc.strip()]
    return "\n\n".join(paragraphes)


def _note_pliee(note: str) -> "FoldedScalarString":
    """La note en bloc replié `>-`, replié autour de 88 colonnes comme les notes existantes.

    Les espaces multiples d'un paragraphe sont normalisés ; une ligne vide sépare toujours
    deux paragraphes. Le repli est explicite parce que le dump se fait à 4096 colonnes.
    """
    texte = _normaliser_note(note)
    scalaire = FoldedScalarString(texte)
    positions: list[int] = []
    depart = 0
    for i, caractere in enumerate(texte):
        if caractere == "\n":
            depart = i + 1
        elif caractere == " " and i - depart >= _LARGEUR_NOTE:
            positions.append(i)
            depart = i
    scalaire.fold_pos = positions
    return scalaire


def save_override(
    key: str,
    status: str,
    note: str | None = None,
    description: str | None = None,
    category: str | None = None,
    *,
    path: Path | None = None,
) -> bool:
    """Écrit le statut (et la note / description / catégorie) du ticket `key` dans la source de vérité.

    `key` est le NOM DE FICHIER COMPLET sans extension : deux tickets distincts partagent
    le numéro 005, une clé courte appliquerait un seul statut aux deux.

    `note=None` laisse la note en place ; `note=""` la retire.
    `description=None` laisse la description en place ; `description=""` la retire.
    `category=None` laisse la catégorie en place ; `category=""` la retire.

    Renvoie True si le fichier a changé, False si l'entrée disait déjà cela — auquel cas
    rien n'est écrit, pour ne pas salir `git status` sans raison. Le fichier est relu à
    chaque appel : une édition faite à la main entre-temps est conservée.
    """
    if status not in EDITABLE_STATUSES:
        raise StatutInconnu(f"statut inconnu {status!r} — attendu l'un de {EDITABLE_STATUSES}")

    _verifier_cle_ecrivable(key)
    parseur, data, entree, avant, path = _ouvrir_entree(key, path)

    entree["status"] = status
    propre = None if note is None else note.strip()
    if propre is None:
        pass  # la note n'est pas dans la demande : on n'y touche pas
    elif not propre:
        entree.pop("note", None)
    elif _normaliser_note(propre) != _normaliser_note(str(entree.get("note", "") or "")):
        # La note n'est reconstruite que si son texte a bougé : sinon on garderait le
        # texte mais on lui imposerait NOS positions de repli, donc un diff pour rien.
        entree["note"] = _note_pliee(propre)

    if description is not None:
        propre_desc = description.strip()
        if not propre_desc:
            entree.pop("description", None)
        elif propre_desc != str(entree.get("description", "") or ""):
            entree["description"] = propre_desc

    if category is not None:
        propre_cat = category.strip()
        if not propre_cat:
            entree.pop("category", None)
        elif propre_cat != str(entree.get("category", "") or ""):
            entree["category"] = propre_cat

    return _ecrire_si_change(parseur, data, avant, path)


def _verifier_cle_ecrivable(key: str) -> None:
    """Écrire une clé courte rendrait l'onglet illisible au prochain chargement : ce que
    la lecture refuse (R28), l'écriture doit le refuser aussi."""
    stems = {p.stem for p in TICKETS_DIR.glob("ticket_*.md")} if TICKETS_DIR.is_dir() else set()
    if stems and key not in stems:
        vises = sorted(s for s in stems if s.startswith(f"{key}_"))
        raise CleInvalide(
            f"clé refusée {key!r} : elle ne désigne pas exactement un ticket "
            f"({', '.join(vises) if vises else 'aucun ticket'}). La clé est le nom de fichier "
            f"complet, sans extension."
        )


def _ouvrir_entree(key: str, path: Path | None):
    """Charge le fichier en round-trip et rend l'entrée du ticket, créée au besoin.

    Rend `(parseur, data, entree, avant, path)` — `avant` est le texte d'origine, que
    `_ecrire_si_change` compare pour n'écrire que si quelque chose a bougé.

    Le défaut de `path` est résolu à l'APPEL et non à l'import : lié à l'import, il
    ignorait une redirection de `OVERRIDES_PATH` en test et écrivait dans le vrai fichier.
    """
    path = Path(path) if path is not None else OVERRIDES_PATH
    parseur = _rt_yaml()
    avant = path.read_text(encoding="utf-8") if path.is_file() else "tickets:\n"
    data = parseur.load(avant)
    if data is None:
        data = CommentedMap()
    entrees = data.get("tickets", data)
    if entrees is None:
        data["tickets"] = entrees = CommentedMap()

    entree = entrees.get(key)
    if entree is None:
        entree = CommentedMap()
        entrees[key] = entree  # ordre d'insertion : la nouvelle entrée va en fin de liste
    return parseur, data, entree, avant, path


def _ecrire_si_change(parseur, data, avant: str, path: Path) -> bool:
    """Dump, comparaison à l'octet, puis remplacement atomique.

    Rien n'est écrit si le fichier dirait déjà cela : `git status` ne se salit pas parce
    qu'on a rouvert un tiroir et cliqué Enregistrer.
    """
    tampon = io.StringIO()
    parseur.dump(data, tampon)
    apres = tampon.getvalue()
    if apres == avant:
        return False

    provisoire = path.with_name(path.name + ".tmp")
    provisoire.write_text(apres, encoding="utf-8")
    os.replace(provisoire, path)
    return True


def save_triage(
    key: str,
    faisabilite: int,
    surete: int,
    jeux_de_test: bool = False,
    motif: str | None = None,
    date: str | None = None,
    aamas: int | None = None,
    *,
    path: Path | None = None,
) -> bool:
    """Écrit le bloc `triage` du ticket `key` SANS toucher à son statut ni à sa note.

    Fonction distincte de `save_override` par intention : le formulaire de statut ne doit
    pas réécrire le triage, et le formulaire de triage ne doit pas réécrire le statut.
    Fondues en une seule, chaque enregistrement de l'un écraserait l'autre — c'est
    exactement la régression que R14 défend déjà pour la note.

    `date=None` horodate au jour de l'appel : une appréciation non datée ne se relit pas,
    on ne sait plus si elle vaut encore après une livraison.

    Renvoie True si le fichier a changé, False si l'entrée disait déjà cela.
    """
    faisabilite = _entier_borne(key, "faisabilite", faisabilite)
    surete = _entier_borne(key, "surete", surete)
    if aamas is not None:
        aamas = _entier_borne(key, "aamas", aamas)
    if not isinstance(jeux_de_test, bool):
        raise TriageInvalide(f"{key} : `jeux_de_test` attend un booléen, reçu {jeux_de_test!r}")
    _verifier_cle_ecrivable(key)
    parseur, data, entree, avant, path = _ouvrir_entree(key, path)

    bloc = entree.get("triage")
    if not isinstance(bloc, dict):
        bloc = CommentedMap()
        entree["triage"] = bloc

    propre = None if motif is None else motif.strip()
    motif_bouge = (
        propre is not None
        and _normaliser_note(propre) != _normaliser_note(str(bloc.get("motif", "") or ""))
    )
    aamas_bouge = aamas is not None and bloc.get("aamas") != aamas
    bouge = (
        bloc.get("faisabilite") != faisabilite
        or bloc.get("surete") != surete
        or aamas_bouge
        or bool(bloc.get("jeux_de_test", False)) != jeux_de_test
        or motif_bouge
    )

    bloc["faisabilite"] = faisabilite
    bloc["surete"] = surete
    if aamas is not None:
        bloc["aamas"] = aamas
    bloc["jeux_de_test"] = jeux_de_test
    if propre is None:
        pass  # le motif n'est pas dans la demande : on n'y touche pas
    elif not propre:
        bloc.pop("motif", None)
    elif motif_bouge:
        # Même règle que la note : on ne reconstruit le scalaire que si le TEXTE a bougé,
        # sinon on lui imposerait nos positions de repli pour un diff vide.
        bloc["motif"] = _note_pliee(propre)

    # La date ne bouge QUE si l'appréciation bouge. Redater à chaque enregistrement
    # ferait écrire le fichier au moindre clic dès le lendemain, et R13 dit l'inverse :
    # enregistrer sans rien changer ne salit pas `git status`. Re-confirmer une note
    # inchangée ne la rend pas plus fraîche — c'est toujours le même jugement.
    if date is not None:
        bloc["date"] = date
    elif bouge or "date" not in bloc:
        bloc["date"] = datetime.now().strftime("%Y-%m-%d")

    return _ecrire_si_change(parseur, data, avant, path)
