"""Le lexique de mobilité — ce qui rend la condition C3 vérifiable (ticket 059, lot 1).

POURQUOI CE FICHIER EXISTE
--------------------------
La condition C3 sert à réfuter une objection précise : *« le modèle obéit à une consigne
lexicale, il ne raisonne pas »*. Elle donne à l'agent le même fait, réécrit **sans aucune
mention de mode ni de voirie**. Si un seul mot de mobilité survit à la réécriture, la condition
ne sépare plus rien — et l'objection revient intacte.

Une paraphrase qui se DÉCLARE neutre ne prouve rien. Celle-ci se VÉRIFIE, contre une liste qui
vit dans un fichier plutôt que dans un test : elle se discute, elle s'allonge, et chaque ajout
se voit dans l'historique.

La même interdiction vaut pour le texte témoin de C4. Un témoin qui parlerait de circulation ne
serait pas un témoin, et le contrôle de spécificité mesurerait autre chose que ce qu'il annonce.

CE QUE LA PARAPHRASE NE DOIT PAS RETIRER — décision de l'auteur, 2026-09-21
--------------------------------------------------------------------------
La première écriture interdisait TOUT mot de mobilité, y compris le sujet de l'article. Elle
racontait donc le lancement du vélo partagé sans nommer le vélo, ce qui est absurde : l'objection
à réfuter n'est pas « le texte parle de transport », c'est « le texte DIT à l'agent quel mode
prendre ». Un article sur le vélo partagé parle du vélo ; ce qu'il ne doit pas faire, c'est nommer
la voiture qu'on abandonne ou le bus qu'on délaisse.

Chaque article déclare donc ses mots EXEMPTÉS, ceux qui nomment l'objet même de l'événement, avec
leur raison. Tout le reste du lexique — et en particulier les modes vers lesquels un report serait
possible — reste interdit : c'est là, et seulement là, que se logerait le suivisme lexical.

Une garde va avec, sans quoi l'exemption serait une porte ouverte : un mot ne peut être exempté
que s'il figure dans le TEXTE BRUT de l'article. On n'exempte pas un mot par précaution, on
exempte celui que le sujet impose. La vérification est dans `corpus.py`.

DEUX LANGUES, ET C'EST VOULU
----------------------------
Les articles paraissent en français, le dispositif fonctionne en anglais (ticket 074). Les deux
versions d'une paraphrase se vérifient donc contre les deux listes : traduire n'est pas une
occasion de réintroduire un mot que la réécriture avait retiré.
"""

from __future__ import annotations

import re
import unicodedata

# Modes, infrastructures, gestes de déplacement. Un mot entre ici dès qu'il NOMME un moyen de
# se déplacer ou l'endroit où l'on se déplace — pas dès qu'il évoque un déplacement. « Sortir »
# et « aller » restent admis : les interdire rendrait toute paraphrase impossible.
MOTS_FR: tuple[str, ...] = (
    # modes
    "metro", "rame", "bus", "autobus", "tram", "tramway", "train", "ter", "navette",
    "velo", "bicyclette", "cyclable", "cycliste", "voiture", "auto", "automobile",
    "vehicule", "scooter", "moto", "deux-roues", "taxi", "vtc", "covoiturage",
    "trottinette", "marche", "marcher", "pieton", "pietonne", "pietonnise",
    # infrastructure et voirie
    "trottoir", "chaussee", "rue", "avenue", "boulevard", "route", "rocade", "peripherique",
    "voie", "carrefour", "pont", "passerelle", "tunnel", "station", "arret", "quai", "gare",
    "parking", "stationnement", "piste",
    # circulation et exploitation
    "circulation", "trafic", "embouteillage", "bouchon", "transport", "transports",
    "deplacement", "trajet", "itineraire", "conduire", "conducteur", "rouler", "pedaler",
    "tisseo", "ligne",
)

# ⚠ « ligne » et « line » sont les deux mots les plus polysémiques de ces listes : « ligne A »
# est un mode, « ligne de conduite » ne l'est pas. Ils restent dans le lexique — le réseau
# toulousain se nomme par ses lignes, et les retirer laisserait passer « la ligne B est
# perturbée » dans une paraphrase censée n'en rien dire. Le refus les nomme, et une paraphrase
# légitimement refusée se réécrit en une minute.

MOTS_EN: tuple[str, ...] = (
    # modes
    "metro", "subway", "underground", "bus", "coach", "tram", "streetcar", "train", "rail",
    "shuttle", "bike", "bicycle", "cycling", "cyclist", "car", "vehicle", "scooter",
    "motorbike", "motorcycle", "taxi", "cab", "rideshare", "carpool", "walk", "walking",
    "pedestrian", "pedestrianise", "pedestrianize", "foot",
    # infrastructure
    "pavement", "sidewalk", "roadway", "street", "avenue", "boulevard", "road", "ring road",
    "bypass", "lane", "junction", "bridge", "footbridge", "tunnel", "station", "stop",
    "platform", "parking", "car park",
    # circulation et exploitation
    "traffic", "congestion", "gridlock", "jam", "transport", "transit", "commute",
    "commuting", "journey", "trip", "route", "drive", "driver", "driving", "ride", "riding",
    "line",
)


def _sans_accents(texte: str) -> str:
    """« chaussée » et « chaussee » sont le même mot pour cette vérification."""
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def mots_de_mobilite_trouves(
    texte: str, langue: str, exemptions: tuple[str, ...] | list[str] = ()
) -> tuple[str, ...]:
    r"""Les mots interdits présents dans `texte`, dans l'ordre de la liste.

    La recherche se fait sur le MOT ENTIER, flexions courantes comprises, et rien de plus :
    « car » ne doit pas se déclencher sur « careful », ni « lane » sur « planet ». Un suffixe
    ouvert (`\w*`) produirait des refus incompréhensibles, et un refus incompréhensible finit
    par être contourné. Les formes qui ne se déduisent pas d'un suffixe court figurent en
    toutes lettres dans la liste.

    Les expressions à deux mots (« ring road », « car park ») sont cherchées telles quelles ;
    l'espace y admet plusieurs blancs ou un tiret.

    `exemptions` retire des mots de la recherche : ceux qui nomment le sujet de l'article, qu'il
    serait absurde de cacher. Leur légitimité se vérifie ailleurs — `corpus.py` exige que chacun
    figure dans le texte brut de son article.
    """
    liste = {"fr": MOTS_FR, "en": MOTS_EN}.get(langue)
    if liste is None:
        raise ValueError(f"langue inconnue pour le lexique de mobilité : {langue!r} (fr | en)")
    exemptes = {_sans_accents(m).lower() for m in exemptions}
    liste = tuple(m for m in liste if _sans_accents(m).lower() not in exemptes)
    suffixes = {"fr": r"(?:s|es|e|ent|ons|ez)?", "en": r"(?:s|es|ing|ed)?"}[langue]
    plat = _sans_accents(texte).lower()
    trouves: list[str] = []
    for mot in liste:
        parts = [re.escape(p) for p in _sans_accents(mot).lower().split()]
        motif = r"\b" + r"[\s-]+".join(parts) + suffixes + r"\b"
        if re.search(motif, plat):
            trouves.append(mot)
    return tuple(trouves)
