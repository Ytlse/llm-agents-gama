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

from experiences.chemins import racine_depot

# Ce que le nom doit satisfaire : il devient un dossier ET la valeur de `EXP=` que `make`
# développe sans guillemets dans un shell (N9). Même motif que `dashboard/experiences.py`.
MOTIF_NOM = re.compile(r"^[^\W_][\w.\-]{0,63}$", re.UNICODE)
LONGUEUR_MAX = 64
PREFIXE = "exp"

# Budget du slug de modèle (N4). Au-delà, les mots sans chiffre tombent à leur initiale :
# `gemini-3.1-flash-lite` → `gemini-31-fl`. À 8 on obtiendrait `gemi31fl`, plus court
# et moins lisible — c'est le seul réglage à toucher pour raccourcir tous les noms d'un coup.
BUDGET_MODELE = 12
BUDGET_VARIANTE = 10
# Assez large pour garder le suffixe de version d'une cohorte (`1000_AAMAS_v5`), qui est
# précisément ce qui la distingue des autres (R18, ticket 045).
BUDGET_POPULATION = 16
# Idem pour le jeu, dont le pouvoir distinctif (la date) est en FIN de nom.
BUDGET_JEU = 16

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
    # PAS de "population" (R18, ticket 045). Y mettre `population_1000_AAMAS` rendait cette
    # cohorte MUETTE dans le nom : aucune des 46 définitions ne mentionnait de substrat, ce
    # qui se lisait « rien à signaler » et signifiait « toutes sur la v1 » — alors que la
    # référence de l'article est la v5. Un substrat ne doit jamais être implicite dans le nom
    # d'une mesure : désormais toute expérience porte sa cohorte, quelle qu'elle soit.
    "horizon_jours": 1,
    "memoire": False,
    # La chaîne des véhicules ACTIVE est le comportement nominal de la simulation : elle est
    # donc muette, et les noms existants ne bougent pas. Coupée, elle se dit (R13).
    "vehicule_chaine": True,
    "verrou_retour": True,
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

    `gemini-3.1-flash-lite` → `gemini-31-fl` · `mistral-small-latest` → `mistral-s`
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


def abreger_population(nom: str) -> str:
    """`population_1000_AAMAS_v5` → `1000_AAMAS_v5`, `population_1000_AAMAS` → `1000_AAMAS`.

    Un tronquage naïf à 16 caractères couperait exactement ce qui DISTINGUE les cohortes :
    `population_1000_AAMAS_v5` et `population_1000_AAMAS` donnent tous deux
    `population_1000_`. Un segment censé nommer le substrat qui ne le nomme pas serait pire
    que pas de segment du tout — c'est le motif « l'absence de mesure passe pour un cas
    sain », que ce ticket traque partout ailleurs.

    On retire donc d'abord le préfixe `population_`, commun à toutes et sans pouvoir
    distinctif, avant de tronquer : ce qui reste porte la taille et la version.
    """
    net = re.sub(r"^population[_-]", "", str(nom).strip(), flags=re.IGNORECASE)
    return _slug(net or nom, BUDGET_POPULATION)


# Format d'artefact → segment de nom. La famille se lit dans l'artefact lui-même, jamais dans
# son nom de fichier : `mnl_model.json` pourrait être renommé sans cesser d'être un logit.
#
# Table SÉPARÉE de `decideur_modele.FAMILLES`, et c'est voulu : celle-là dit ce que le décideur
# sait CHARGER (le témoin random forest en est exclu par la règle R7 du ticket 044, qui le
# tient hors des modules de score) ; celle-ci dit seulement comment NOMMER. Nommer n'est pas
# arbitrer, et une expérience du témoin doit porter son nom quoi qu'il arrive.
ABREV_FORMAT_MODELE = {
    "lightgbm_mode_choice_policy": "lgbm",
    "mnl_mode_choice_policy": "mnl",
    "klr_mode_choice_policy": "klr",
    "rf_mode_choice_policy": "rf",
}


def abreger_famille_modele(artefact: str) -> str:
    """Le segment de nom d'un décideur modèle, DÉRIVÉ de la famille déclarée par l'artefact.

    `ABREV_DECIDEUR["modele"]` valait `lgbm` : toute expérience à décideur modèle s'annonçait
    donc LightGBM, y compris un logit multinomial ou une forêt. Le libellé avait été corrigé
    dans les traces et l'empreinte (ticket 042), pas dans le **nom** — celui qu'on lit en
    premier, et qui nomme le dossier d'archives.

    Lecture de la TÊTE du fichier seulement : `mode_choice_policy.json` pèse 18 Mo, et le
    champ `format` est dans ses premières lignes.

    Un artefact illisible ou de format inconnu ne se voit attribuer AUCUNE famille : le segment
    devient `mod-<fichier>`, qui n'affirme rien. Affirmer « lgbm » d'un fichier qu'on n'a pas su
    lire serait exactement le défaut qu'on corrige.
    """
    chemin = Path(artefact)
    if not chemin.is_absolute():
        chemin = racine_depot() / chemin
    format_ = None
    try:
        tete = chemin.open("r", encoding="utf-8").read(400)
        trouve = re.search(r'"format"\s*:\s*"([^"]+)"', tete)
        format_ = trouve.group(1) if trouve else None
    except OSError:
        format_ = None
    if format_ in ABREV_FORMAT_MODELE:
        return ABREV_FORMAT_MODELE[format_]
    return f"mod-{_slug(Path(artefact).stem, 12)}"


def abreger_jeu(nom_jeu: str, nom_population: str = "") -> str:
    """Abrège un nom de jeu en gardant ce qui le DISTINGUE, c'est-à-dire sa queue.

    Un nom de jeu suit `<population>_<AAAAMMJJ>` : tout le pouvoir distinctif est dans la
    date, en fin de chaîne, et c'est précisément ce qu'un tronquage par la tête supprime.
    On retire donc d'abord le nom de la population quand il préfixe, puis le préfixe
    `population_` commun, avant de tronquer — et si le reste déborde encore, on garde la
    QUEUE plutôt que la tête.

    Même défaut, même remède que `abreger_population` : deux objets différents ne doivent
    jamais produire le même segment de nom.
    """
    net = str(nom_jeu).strip()
    if nom_population and net.startswith(nom_population + "_"):
        net = net[len(nom_population) + 1 :]
    net = re.sub(r"^population[_-]", "", net, flags=re.IGNORECASE)
    net = _slug(net or nom_jeu, 10**6)  # nettoie sans tronquer
    if len(net) > BUDGET_JEU:
        net = net[-BUDGET_JEU:].lstrip("-._")
    return net or _slug(nom_jeu, BUDGET_JEU)


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
        return abreger_famille_modele(str(dec["artefact"]))
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
    # La population entre TOUJOURS dans le nom : il n'existe plus de cohorte « par défaut »
    # qu'on pourrait taire (R18).
    if pop:
        out.append(f"pop-{abreger_population(pop)}")
    if jeu_nom and not conventionnel:
        # Un jeu hors convention (jeu gelé, nom donné à la main) : son nom entre dans celui
        # de l'expérience, sinon deux jeux différents donneraient le même nom.
        #
        # `abreger_jeu` et non `_slug` brut : le tronquage naïf coupait exactement la date qui
        # distingue deux jeux. `population_1000_AAMAS_20260316` et `…_20260317` donnaient tous
        # deux `population_1000_` — donc le même nom d'expérience pour deux jeux différents.
        # C'est le défaut que R18 vient de fermer pour la population, resté ouvert ici.
        out.append(f"jeu-{abreger_jeu(jeu_nom, pop)}")
    # La chaîne coupée change ce que le décideur peut choisir : elle appartient à l'identité
    # de la mesure, pas à son environnement (R13).
    if bool(exp.get("vehicule_chaine", D["vehicule_chaine"])) != D["vehicule_chaine"]:
        out.append("nochn")
    if bool(exp.get("verrou_retour", D["verrou_retour"])) != D["verrou_retour"]:
        out.append("noret")
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
