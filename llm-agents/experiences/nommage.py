"""Le nom d'une expérience se calcule depuis ses paramètres (spec `nommage-canonique-experiences`).

Le nom EST l'identité : dossier `data/experiences/<nom>/`, clé de dédoublonnage de la file
FIFO, cible de `pause` / `arreter`. Tant qu'il était tapé, rien ne garantissait qu'il dise les
paramètres — trois modèles ont été mesurés sous `Prompt_Minimaliste` le 2026-09-07. Il est
maintenant DÉRIVÉ : deux expériences qui diffèrent d'un paramètre nommé portent deux noms, et
deux définitions strictement identiques sont la même expérience (N10).

Ce module ne dépend que de la bibliothèque standard : le tableau de bord l'importe depuis
l'hôte, sans pydantic ni `settings`.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Ce que le nom doit satisfaire : il devient un dossier ET la valeur de `EXP=` que `make`
# développe sans guillemets dans un shell (N9). Même motif que `dashboard/experiences.py`.
MOTIF_NOM = re.compile(r"^[^\W_][\w.\-]{0,63}$", re.UNICODE)
LONGUEUR_MAX = 64
PREFIXE = "exp"

# Budget du slug de modèle (N4). Au-delà, les mots sans chiffre tombent à leur initiale :
# `gemini-3.1-flash-lite-preview` → `gemini-31-fl`. À 8 on obtiendrait `gemi31fl`, plus court
# et moins lisible — c'est le seul réglage à toucher pour raccourcir tous les noms d'un coup.
BUDGET_MODELE = 12
BUDGET_VARIANTE = 10

# Mots qui ne distinguent aucun modèle : les jeter raccourcit sans rien perdre.
BRUIT_MODELE = frozenset(
    {"latest", "preview", "instruct", "chat", "hf", "awq", "gguf", "it", "gptq", "fp8"}
)

# Types de décideur : liste FERMÉE (`DecideurSpec.type`), donc une table est sans risque de
# dérive — contrairement aux modèles, qui vont et viennent avec les fournisseurs.
ABREV_DECIDEUR = {
    "aleatoire": "alea",
    "antigravity": "agy",
    "duree_minimale": "durmin",
    "majoritaire_voiture": "majvoiture",
    "modele": "lgbm",
    "rejeu": "rejeu",
}

# Portée d'un décideur passerelle : `distant` est la valeur de référence, donc MUETTE (N7) —
# aucun nom existant ne bouge. Seul `local` se dit, parce qu'un même identifiant de modèle est
# parfois servi des deux côtés (`qwen/qwen3.8-27b` chez Groq et dans LM Studio) : sans ce
# segment, les deux expériences porteraient le même nom, donc le même dossier d'archives.
ABREV_PORTEE = {"local": "local"}

ABREV_POLITIQUE = {"aleatoire": "jtir", "propre": "jpers"}
ABREV_MODE = {"sans_simulateur": "nosim", "simulateur": "sim"}

# Tolérances horaires de référence — celles que propose le formulaire.
TOLERANCES_REFERENCE = {
    "walk": "insensible",
    "bike": "insensible",
    "car": "heure",
    "transit": {"pas_min": 10},
    "rail": {"pas_min": 10},
}

# Valeurs de référence : un paramètre qui les vaut est MUET dans le nom (N7). Changer cette
# table change les noms que le générateur PROPOSERA ; elle ne renomme rien de ce qui existe
# (N12), le `nom` écrit dans `experience.yaml` restant autoritaire.
DEFAUTS_NOMMAGE: dict[str, Any] = {
    "population": "population_1000_AAMAS",
    "horizon_jours": 1,
    "memoire": False,
    "evenements": 0,
    "parallelisme": 8,
    "max_candidats": 6,
    "attente_max_s": 120,
    "graine_ordre": 42,
    "graine_tirage": 42,
    "graine_calendrier": 42,
    "graine_decideur": 42,
    "portee": "distant",
    "tolerances_horaires": TOLERANCES_REFERENCE,
}

# Champs d'IDENTITÉ, exclus de la signature : deux définitions qui n'en diffèrent que par là
# décrivent la même expérience (N10).
CHAMPS_IDENTITE = ("nom", "derive_de", "renomme_de", "executions_connues")


class NommageImpossible(ValueError):
    """Les paramètres ne permettent pas de composer un nom — la raison nomme le champ."""


# ── briques ──────────────────────────────────────────────────────────────────


def _mots(texte: str) -> list[str]:
    """Découpe sur tout ce qui n'est ni lettre ni chiffre, points supprimés (`3.1` → `31`)."""
    return [m for m in re.split(r"[^0-9A-Za-z]+", texte.replace(".", "")) if m]


def _chiffre(mot: str) -> bool:
    return any(c.isdigit() for c in mot)


def abreger_modele(modele: str) -> str:
    """Le nom d'un modèle réduit à ce qui distingue (N4), sans table à tenir à jour.

    `gemini-3.1-flash-lite-preview` → `gemini-31-fl` · `mistral-small-latest` → `mistral-s`
    `qwen/qwen3.6-27b` → `qwen36-27b` · `gpt-oss-120b` → `gpt-oss-120b`
    """
    brut = str(modele or "").strip().lower()
    if not brut:
        return ""
    # `qwen/qwen3.6-27b` : le fournisseur ne distingue rien quand il répète la famille.
    if "/" in brut:
        fournisseur, reste = brut.split("/", 1)
        mots_reste = _mots(reste)
        if mots_reste and mots_reste[0].startswith(fournisseur[:4]):
            brut = reste
        else:
            brut = f"{fournisseur} {reste}"
    mots = [m for m in _mots(brut) if m not in BRUIT_MODELE]
    if not mots:
        mots = _mots(brut) or [brut]
    if len("-".join(mots)) > BUDGET_MODELE:
        # Les chiffres portent la version : on ne les abrège jamais. Les mots sans chiffre
        # tombent à leur initiale et se GROUPENT : `flash lite` → `fl`, pas `f-l`.
        groupes: list[str] = [mots[0]]
        for mot in mots[1:]:
            if _chiffre(mot):
                groupes.append(mot)
            elif groupes and not _chiffre(groupes[-1]) and len(groupes) > 1:
                groupes[-1] += mot[0]
            else:
                groupes.append(mot[0])
        mots = groupes
    return "-".join(mots)[:BUDGET_MODELE].strip("-")


def abreger_variante(variante: str | None) -> str:
    """`minimal_persona` → `minper`, `b_min` → `bmin`. Variante absente → `actif` (N5)."""
    if not variante:
        return "actif"  # le prompt ACTIF de la passerelle : « celui du jour », pas un réglage
    mots = _mots(str(variante))
    # Trois lettres par mot, mais un mot qui porte un chiffre reste entier : c'est une
    # version, et `calibrated_2026` ne doit pas devenir `cal202`.
    court = "".join(m if _chiffre(m) else m[:3] for m in mots)
    return (court[:BUDGET_VARIANTE] or "actif").lower()


def _slug(texte: str, taille: int = 16) -> str:
    """Un fragment sûr pour un segment de nom : accents conservés, danger remplacé."""
    net = re.sub(
        r"[^\w.\-]+", "-", unicodedata.normalize("NFC", str(texte)).strip(), flags=re.UNICODE
    )
    return re.sub(r"-{2,}", "-", net).strip("-._")[:taille]


def _nombre(valeur: float) -> str:
    """`0.0` → `0`, `0.7` → `07`, `1.25` → `125` : la valeur lisible, sans point (N8)."""
    return f"{float(valeur):g}".replace(".", "").replace("-", "m")


def _horodatage_compact(chemin: str) -> str:
    """`…/executions/2026-09-07_22_09_48` → `260907-2209`."""
    dernier = Path(str(chemin)).name
    m = re.match(r"(\d{2})(\d{2})-?(\d{2})-?(\d{2})_(\d{2})_(\d{2})", dernier)
    if m:
        _, aa, mm, jj, hh, mi = m.groups()
        return f"{aa}{mm}{jj}-{hh}{mi}"
    return _slug(dernier, 12)


# ── segments ─────────────────────────────────────────────────────────────────


def segment_decideur(decideur: dict) -> str:
    """Le décideur, toujours nommé (N3)."""
    dec = decideur or {}
    type_ = str(dec.get("type") or "")
    if not type_:
        raise NommageImpossible("decideur.type est vide : aucun nom ne peut être composé")
    if type_ == "passerelle":
        slug = abreger_modele(str(dec.get("modele") or ""))
        if not slug:
            raise NommageImpossible(
                "decideur.modele est vide : choisissez le modèle, c'est lui qui nomme "
                "l'expérience"
            )
        return slug
    if type_ == "antigravity":
        slug = abreger_modele(str(dec.get("modele") or ""))
        if not slug:
            raise NommageImpossible(
                "decideur.modele est vide : choisissez le modèle, c'est lui qui nomme "
                "l'expérience"
            )
        return f"agy-{slug}"
    base = ABREV_DECIDEUR.get(type_) or _slug(type_, 10)
    if type_ == "modele" and dec.get("artefact"):
        return f"{base}-{_slug(Path(str(dec['artefact'])).stem, 12)}"
    if type_ == "rejeu" and dec.get("rejeu_de"):
        return f"{base}-{_horodatage_compact(str(dec['rejeu_de']))}"
    return base


def _empreinte_courte(valeur: Any, taille: int = 4) -> str:
    brut = json.dumps(valeur, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(brut.encode("utf-8")).hexdigest()[:taille]


def segments(exp: dict) -> list[str]:
    """Les segments du nom, dans l'ordre fixe de la grammaire (N2)."""
    dec = exp.get("decideur") or {}
    cal = exp.get("calendrier") or {}
    pop_chemin = str((exp.get("population") or {}).get("chemin") or "")
    pop = Path(pop_chemin).name.replace(".json", "")
    D = DEFAUTS_NOMMAGE

    out = [PREFIXE, segment_decideur(dec)]

    # N4b — la portée, juste après le modèle qu'elle qualifie. Muette quand elle est distante
    # ou absente : le distant est la référence, et une définition antérieure à ce champ garde
    # exactement le nom qu'elle avait.
    if dec.get("type") == "passerelle":
        portee = str(dec.get("portee") or D["portee"])
        if portee in ABREV_PORTEE:
            out.append(ABREV_PORTEE[portee])

    # N5 — le prompt ne compte que pour un décideur qui lit un prompt.
    if dec.get("type") in ("passerelle", "antigravity"):
        out.append(abreger_variante((exp.get("gabarit") or {}).get("variante")))

    # N6 — le calendrier, muet dans le cas simple. Le jour du jeu se lit dans son nom quand
    # il suit la convention `<population>_<AAAAMMJJ>` ; sinon il est inconnu, et la date se
    # dit (le segment `jeu-…` dira de son côté que le jeu n'est pas celui qu'on attendait).
    politique = str(cal.get("politique") or "")
    jeu_nom = str((exp.get("jeu") or {}).get("nom") or "")
    conventionnel = re.fullmatch(rf"{re.escape(pop)}_(\d{{8}})", jeu_nom) if pop else None
    jour_du_jeu = conventionnel.group(1) if conventionnel else None
    date_compacte = str(cal.get("date") or "").replace("-", "")
    if politique in ABREV_POLITIQUE:
        out.append(ABREV_POLITIQUE[politique])
    elif politique == "commune" and date_compacte != jour_du_jeu:
        out.append("j" + date_compacte[4:])

    # N7 — écarts aux valeurs de référence, ordre fixe.
    if pop and pop != D["population"]:
        out.append(f"pop-{_slug(pop, 16)}")
    if jeu_nom and not conventionnel:
        # Un jeu hors convention (jeu gelé, nom donné à la main) : son nom entre dans celui
        # de l'expérience, sinon deux jeux différents donneraient le même nom.
        out.append(f"jeu-{_slug(jeu_nom.replace(pop + '_', ''), 16)}")
    if int(exp.get("horizon_jours") or 1) != D["horizon_jours"]:
        out.append(f"h{int(exp['horizon_jours'])}j")
    if bool(exp.get("memoire")) != D["memoire"]:
        out.append("mem")
    if len(exp.get("evenements") or []) != D["evenements"]:
        out.append(f"ev{len(exp['evenements'])}")
    par = int((exp.get("regroupement") or {}).get("parallelisme") or D["parallelisme"])
    if par != D["parallelisme"]:
        out.append(f"p{par}")
    if int(exp.get("max_candidats") or D["max_candidats"]) != D["max_candidats"]:
        out.append(f"c{int(exp['max_candidats'])}")
    if int(exp.get("attente_max_s") or D["attente_max_s"]) != D["attente_max_s"]:
        out.append(f"a{int(exp['attente_max_s'])}")
    for cle, prefixe in (("graine_ordre", "go"), ("graine_tirage", "gt")):
        if int(exp.get(cle) or D[cle]) != D[cle]:
            out.append(f"{prefixe}{int(exp[cle])}")
    if int(cal.get("graine") or D["graine_calendrier"]) != D["graine_calendrier"]:
        out.append(f"gc{int(cal['graine'])}")
    if dec.get("graine") is not None and int(dec["graine"]) != D["graine_decideur"]:
        out.append(f"gd{int(dec['graine'])}")
    tol = exp.get("tolerances_horaires")
    if tol and _normaliser(tol) != _normaliser(D["tolerances_horaires"]):
        out.append(f"tol-{_empreinte_courte(_normaliser(tol))}")

    # N8 — température et mode, toujours nommés.
    if dec.get("type") in ("passerelle", "antigravity"):
        out.append("t" + _nombre((dec.get("parametres") or {}).get("temperature") or 0.0))
    mode = str(exp.get("mode") or "")
    if mode not in ABREV_MODE:
        raise NommageImpossible(f"mode inconnu : {mode!r} (sans_simulateur | simulateur)")
    out.append(ABREV_MODE[mode])
    return out


def nom_canonique(exp: dict) -> str:
    """Le nom que ces paramètres imposent, sans regarder le disque (N2, N9)."""
    nom = "_".join(s for s in segments(exp) if s)[:LONGUEUR_MAX].strip("_.-")
    if not MOTIF_NOM.match(nom):
        raise NommageImpossible(
            f"nom composé invalide : {nom!r} — un paramètre porte un caractère inattendu"
        )
    return nom


def verifier_nom(exp: dict) -> str | None:
    """Le nom canonique quand le `nom` du fichier n'est pas celui-là, None s'il l'est (N13).

    Sert à `experiences definir` : une définition écrite à la main peut nommer autre chose que
    ce que disent ses paramètres, et c'est exactement ce que le nommage calculé supprime.
    L'indice de collision n'entre pas en jeu ici — il dépend du disque, pas des paramètres.
    """
    attendu = nom_canonique(exp)
    actuel = str((exp or {}).get("nom") or "")
    import re as _re

    if actuel == attendu or _re.fullmatch(rf"{_re.escape(attendu)}_\d+", actuel):
        return None
    return attendu


# ── signature et collisions ──────────────────────────────────────────────────


def _normaliser(valeur: Any) -> Any:
    """Forme comparable : dictionnaires triés, tolérance `insensible` == `{type: insensible}`."""
    if isinstance(valeur, dict):
        if set(valeur) == {"type"}:
            return _normaliser(valeur["type"])
        if set(valeur) == {"type", "pas_min"} and valeur.get("pas_min") is None:
            return _normaliser(valeur["type"])
        if set(valeur) == {"type", "pas_min"} and valeur.get("type") == "pas":
            return {"pas_min": int(valeur["pas_min"])}
        return {str(k): _normaliser(v) for k, v in sorted(valeur.items())}
    if isinstance(valeur, (list, tuple)):
        return [_normaliser(v) for v in valeur]
    if isinstance(valeur, float) and valeur.is_integer():
        return int(valeur)
    return valeur


def signature(exp: dict) -> str:
    """sha256 de la définition privée de son identité (N10)."""
    utile = {k: v for k, v in (exp or {}).items() if k not in CHAMPS_IDENTITE}
    brut = json.dumps(
        _normaliser(utile), sort_keys=True, ensure_ascii=False, default=str
    )
    return hashlib.sha256(brut.encode("utf-8")).hexdigest()


def _avec_indice(base: str, indice: int) -> str:
    """`base_2`, sans jamais laisser tomber l'indice : c'est la base qui est rognée (N11)."""
    if indice <= 1:
        return base[:LONGUEUR_MAX].strip("_.-")
    suffixe = f"_{indice}"
    return (base[: LONGUEUR_MAX - len(suffixe)].strip("_.-") + suffixe)[:LONGUEUR_MAX]


def definitions_existantes(dossier: str | Path) -> dict[str, str]:
    """nom → signature, lu dans `data/experiences/*/experience.yaml`.

    Le `nom` du fichier est autoritaire ; le nom de DOSSIER est retenu lui aussi, parce qu'il
    occupe un chemin même s'il ne correspond pas au champ.
    """
    import yaml

    racine = Path(dossier)
    out: dict[str, str] = {}
    if not racine.is_dir():
        return out
    for p in sorted(racine.iterdir()):
        fichier = p / "experience.yaml"
        if not fichier.is_file():
            continue
        try:
            data = yaml.safe_load(fichier.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        sig = signature(data)
        out.setdefault(str(data.get("nom") or p.name), sig)
        out.setdefault(p.name, sig)
    return out


@dataclass
class Attribution:
    """Ce que le nommage a décidé, et de quoi le dire à l'écran."""

    nom: str
    base: str
    indice: int = 1
    reutilise: str | None = None  # expérience existante de MÊME signature
    voisins: list[str] = field(default_factory=list)  # noms pris qui partagent la base


def attribuer_nom(exp: dict, dossier: str | Path, existantes: dict[str, str] | None = None) -> Attribution:
    """Le nom à écrire, indice de collision compris (N10, N11).

    `reutilise` renseigné = ce nom désigne DÉJÀ cette expérience, à l'identique : la relancer
    ajoute une exécution à ses archives, elle n'en crée pas une seconde.
    """
    base = nom_canonique(exp)
    prises = definitions_existantes(dossier) if existantes is None else dict(existantes)
    sig = signature(exp)
    voisins = [n for n in prises if n == base or re.fullmatch(rf"{re.escape(base)}_\d+", n)]
    for indice in range(1, 1000):
        candidat = _avec_indice(base, indice)
        connue = prises.get(candidat)
        if connue is None:
            return Attribution(candidat, base, indice, None, sorted(voisins))
        if connue == sig:
            return Attribution(candidat, base, indice, candidat, sorted(voisins))
    raise NommageImpossible(
        f"plus de mille expériences portent la base {base!r} : nommez-en une à la main"
    )


__all__ = [
    "ABREV_DECIDEUR",
    "ABREV_MODE",
    "ABREV_POLITIQUE",
    "ABREV_PORTEE",
    "BUDGET_MODELE",
    "CHAMPS_IDENTITE",
    "DEFAUTS_NOMMAGE",
    "LONGUEUR_MAX",
    "MOTIF_NOM",
    "TOLERANCES_REFERENCE",
    "Attribution",
    "NommageImpossible",
    "abreger_modele",
    "abreger_variante",
    "attribuer_nom",
    "definitions_existantes",
    "nom_canonique",
    "segment_decideur",
    "segments",
    "signature",
    "verifier_nom",
]
