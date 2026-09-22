"""Ce qu'un texte d'événement n'a pas le droit de dire — ticket 100, lot 1.

Repris **mot pour mot** de `llm/chocs.py` (ticket 079, règles R7 à R10). Rien n'est ajouté, rien
n'est relâché : les listes sont calibrées sur le corpus du dépôt, les cinq cas c1 à c5 passent
sans modification, et « I am starting to wonder whether this is worth it » (c1, jour 14) reste
accepté — un doute n'est pas un verdict.

Le module est ici, et non dans la déclaration, parce que le **canal `lu` obéit aux mêmes règles**.
Un article de presse qui dirait à l'agent quel mode prendre fabriquerait le résultat qu'on prétend
mesurer, exactement comme un vécu qui conclut à sa place. Une seule liste pour les deux canaux :
deux listes divergeraient, et la divergence ne se verrait pas.

La garde de CITATION — l'empreinte d'un texte cité contre son manifeste — est au bas de ce
module. Elle est propre au canal `lu` : un vécu est écrit par nous, il n'a pas de source à trahir.

CE QUI N'EST PAS REFUSÉ, ET QU'IL NE FAUT PAS CONFONDRE
-------------------------------------------------------
**Un texte peut nommer des modes de transport.** Métro, bus, vélo, voiture : les nommer n'a
jamais été refusé ici, et la décision de l'auteur du 2026-09-22 le confirme — un article sur
une grève des transports qui ne pourrait pas dire « métro » serait inintelligible, et le cacher
ne prouverait rien.

⚠ **Ne pas confondre avec la liste de mots du ticket 059, lot 1.** Celle-là interdit le
vocabulaire de mobilité dans la **paraphrase** (condition C3) et dans le **témoin** (C4), pour
que ces deux conditions ne parlent pas de transport du tout. Elle ne s'applique PAS au texte
brut cité (C2), qui est l'article lui-même. Deux listes, deux objets, deux conditions
différentes : les mêmes mots y jouent des rôles opposés.

Ce que ce module refuse est autre chose : un texte qui dit à l'AGENT ce qu'il doit faire, qui
conclut à sa place sur la fiabilité d'un mode, ou qui annonce ce qu'il fera demain. La frontière
n'est pas le vocabulaire, c'est la DESTINATION de la phrase.
"""

from __future__ import annotations

import re

from loguru import logger

# Marqueurs d'une CONSIGNE déguisée en texte d'événement. R7.
#
# Pourquoi refuser et non avertir : un avertissement au milieu d'un journal de run n'alerte
# personne (le ticket 077 l'a mesuré — deux WARNING sur le vocabulaire des modes noyés dans
# 355 000 lignes, et le mécanisme des concepts est resté cassé trente jours). Et une consigne qui
# passe ne biaise pas un peu : elle fabrique exactement le résultat qu'on prétend mesurer.
MARQUEURS_CONSIGNE: tuple[str, ...] = (
    "you should", "you must", "you'd better", "you ought", "you need to",
    "avoid ", "remember to", "consider ", "try to", "don't ", "do not ",
    "make sure", "next time you", "from now on",
    "tu devrais", "tu dois", "évite ", "evite ", "pense à", "pense a",
    "il faut que tu", "n'oublie pas", "la prochaine fois", "désormais tu",
)

# Marqueurs d'un VERDICT — une croyance durable sur un mode ou un véhicule. R9.
#
# La croyance est exactement ce que l'étape de réflexion existe pour produire : l'écrire à la
# main court-circuite le seul mécanisme que l'expérience prétend mesurer. Le run du 19 septembre
# l'a payé — `vecu` : « I no longer trust this car at all » ; concept « appris » le soir même :
# « My car is unreliable ». Le second n'est que la reformulation du premier.
MARQUEURS_VERDICT: tuple[str, ...] = (
    "no longer trust", "cannot trust", "can't trust", "never trust",
    "is unreliable", "are unreliable", "'s unreliable", "was unreliable",
    "is not reliable", "isn't reliable", "not reliable at all",
    "can't rely on", "cannot rely on", "can no longer rely",
    "ne fais plus confiance", "n'ai plus confiance", "plus confiance en",
    "n'est pas fiable", "pas fiable du tout", "ne peux plus compter sur",
)

# Marqueurs d'une INTENTION MODALE — ce que l'agent fera demain. R10.
#
# Famille distincte de la précédente, et refusée par un message distinct : les deux se relâchent
# séparément le jour où l'auteur voudra discuter la ligne. Un fait PASSÉ, même modal, reste
# accepté — « I had to sort out another way of getting around » (c2, jour 13) décrit une journée
# vécue, pas une résolution.
MARQUEURS_INTENTION: tuple[str, ...] = (
    "thinking about not using", "thinking of not using", "considering not using",
    "thinking about not taking", "considering not taking",
    "i will not use", "i won't use", "i will stop using", "i'll stop using",
    "i am not going to use", "i'm not going to use", "i will never use",
    "i will never drive", "i will never take", "i will stop driving",
    "from now on i", "i will take the", "i'll take the", "i will use the",
    "alternative transport", "another mode of transport", "switch to the",
    " prendrai", "je vais arrêter", "je vais arreter", "je ne conduirai",
    "désormais je", "desormais je", "un autre mode de transport",
)

# Adresse à la deuxième personne, en tête de phrase ou isolée. Un vécu se raconte à la première
# personne ; s'adresser à l'agent, c'est lui parler, donc lui dicter.
DEUXIEME_PERSONNE = re.compile(
    r"\b(you|your|yours|tu|toi|ton|ta|tes|vous|votre|vos)\b", re.IGNORECASE
)

# Marques de première personne. Leur ABSENCE n'est pas refusée — « Flat tyre on the way, hands
# covered in grease » est un vécu parfaitement valide sans un seul « I » — mais elle est signalée.
PREMIERE_PERSONNE = re.compile(
    r"\b(i|i'm|i've|i'd|my|mine|me|je|j'ai|j'|mon|ma|mes|moi)\b", re.IGNORECASE
)


def verifier_texte(
    texte: str,
    evenement_id: str,
    jour: int,
    refus,
    exemptes: dict[str, str] | None = None,
    attendre_premiere_personne: bool = True,
) -> None:
    """R7 à R10 : un texte d'événement raconte, il ne commande pas.

    `refus` est la classe d'exception à lever — passée en paramètre pour que ce module ne
    dépende pas de `declaration.py`, qui dépend de lui. Le cycle d'import serait sinon
    inévitable, et le contourner par un import local masquerait la dépendance réelle.

    `exemptes` — un marqueur de consigne présent dans un texte CITÉ, levé avec son motif
    (ticket 100, lot 2). La liste des marqueurs a été calibrée sur des vécus que nous écrivons
    à la première personne ; un article de presse est du récit à la troisième personne, et il
    y tombe pour des raisons qui n'ont rien à voir avec le lecteur. Mesuré sur les cinq
    articles du corpus 059 : **une seule occurrence**, « City staff must first inspect each
    site to make sure there is no danger », où le sujet est le personnel municipal.

    L'exemption suit le précédent du 059 sur les mots interdits de la paraphrase : elle est
    déclarée, motivée, et elle voyage avec l'empreinte du texte — un texte modifié perd ses
    exemptions avec sa validité. Elle ne peut JAMAIS lever l'adresse à la deuxième personne :
    c'est le seul signal fiable qu'un texte parle à l'agent, et aucun des cinq articles ne le
    porte.

    `attendre_premiere_personne` — faux pour un texte cité. Un article n'est pas un récit à la
    première personne, et un avertissement qui se lève à chaque chargement cesse d'être lu.
    """
    nu = (texte or "").strip()
    if not nu:
        raise refus(
            f"événement « {evenement_id} », jour {jour} : texte vide — un événement sans "
            f"texte ne laisse aucun souvenir, il ne sert à rien"
        )
    bas = nu.lower()
    # R9 et R10 AVANT R7 : « from now on I will take the metro » est une intention à la première
    # personne, pas une consigne à la deuxième. L'ordre décide du message rendu, et un message
    # qui nomme la mauvaise faute envoie corriger le mauvais mot.
    for marqueur in MARQUEURS_VERDICT:
        if marqueur in bas:
            raise refus(
                f"événement « {evenement_id} », jour {jour} : le texte porte un VERDICT sur un "
                f"mode — « {marqueur.strip()} ». La croyance est ce que la réflexion de l'agent "
                f"doit produire ; l'écrire ici revient à mesurer sa propre consigne. "
                f"Racontez le fait : « the engine stalled twice », jamais « this car is unreliable »"
            )
    for marqueur in MARQUEURS_INTENTION:
        if marqueur in bas:
            raise refus(
                f"événement « {evenement_id} », jour {jour} : le texte annonce une INTENTION "
                f"modale — « {marqueur.strip()} ». Ce que l'agent fera demain est le résultat "
                f"qu'on mesure, pas une donnée d'entrée. Un fait passé reste permis : "
                f"« I had to sort out another way of getting around »"
            )
    for marqueur in MARQUEURS_CONSIGNE:
        if marqueur in bas:
            motif = (exemptes or {}).get(marqueur)
            if motif:
                k = bas.find(marqueur)
                logger.info(
                    f"[evenements] « {evenement_id} » : marqueur de consigne "
                    f"« {marqueur.strip()} » EXEMPTÉ — {motif}. Passage : "
                    f"« …{nu[max(0, k - 60):k + 50].strip()}… »"
                )
                continue
            raise refus(
                f"événement « {evenement_id} », jour {jour} : le texte contient "
                f"« {marqueur.strip()} », qui s'adresse à l'agent au lieu de raconter ce qui "
                f"s'est passé. Un texte qui dicte une conduite fabrique le résultat qu'on "
                f"prétend mesurer. Racontez le fait : « I was stuck for an hour », jamais "
                f"« avoid the ring road ». Si le marqueur ne s'adresse pas au lecteur — "
                f"un texte de presse cité peut le porter pour une autre raison — exemptez-le "
                f"nommément sous `texte.marqueurs_exemptes`, avec son motif"
            )
    # L'adresse à la deuxième personne ne s'exempte JAMAIS. C'est le seul signal fiable qu'un
    # texte parle à l'agent plutôt que de raconter quelque chose ; aucun des cinq articles du
    # corpus ne le porte, et celui qui le porterait aurait à s'expliquer autrement.
    if DEUXIEME_PERSONNE.search(nu):
        raise refus(
            f"événement « {evenement_id} », jour {jour} : le texte s'adresse à l'agent à la "
            f"deuxième personne. Un vécu se raconte à la première personne"
        )
    if attendre_premiere_personne and not PREMIERE_PERSONNE.search(nu):
        logger.warning(
            f"[evenements] « {evenement_id} », jour {jour} : le texte ne porte aucune marque de "
            f"première personne — vérifiez que c'est bien un vécu et non une description "
            f"extérieure : « {nu[:70]}… »"
        )


# ── Garde de CITATION (ticket 100, lot 2) ───────────────────────────────────────────────────
# Propre au canal `lu`, et sans équivalent chez le vécu : un vécu est écrit par nous, il n'a pas
# de source à trahir. Un texte de presse est CITÉ, jamais réécrit — c'est ce qui rend
# vérifiable l'affirmation « articles réels de la presse locale ».
#
# TROIS valeurs, DEUX comparaisons : l'empreinte déclarée dans le YAML, celle du fichier sur le
# disque, et celle du manifeste du corpus. Comparer le fichier à la seule déclaration laisserait
# passer une déclaration juste posée sur un fichier modifié en même temps que son manifeste ;
# comparer au seul manifeste laisserait passer une déclaration qui désigne un autre texte.

# Racines essayées pour un chemin relatif, dans l'ordre. Le dépôt et le conteneur ne voient pas
# le corpus au même endroit : `/app` dans le second, la racine du dépôt dans le premier.
def _racines_possibles() -> tuple:
    from pathlib import Path

    ici = Path(__file__).resolve()
    return (
        Path.cwd(),
        ici.parents[4] if len(ici.parents) > 4 else ici.parents[-1],  # racine du dépôt
        Path("/app"),
    )


def resoudre_chemin(chemin: str):
    """Le fichier désigné, cherché aux endroits où le dépôt et le conteneur le rangent.

    Rend `None` si aucun candidat n'existe : l'appelant en fait un refus nommant les chemins
    essayés. Une erreur « fichier introuvable » sans la liste des endroits regardés envoie
    chercher au mauvais endroit.
    """
    from pathlib import Path

    p = Path(chemin)
    if p.is_absolute():
        return p if p.is_file() else None
    for racine in _racines_possibles():
        candidat = racine / p
        if candidat.is_file():
            return candidat
    return None


def _empreinte_du_manifeste(fichier, evenement_id: str):
    """L'empreinte que le manifeste du corpus donne pour ce fichier, ou `None`.

    `None` veut dire « ce fichier ne relève d'aucun manifeste » — un texte hors du corpus de
    presse, par exemple — et non « le manifeste est d'accord ». La distinction compte : sans
    elle, un texte rangé ailleurs passerait la garde par absence de contradicteur, et
    l'absence de vérification aurait exactement l'air d'une vérification réussie.
    """
    import yaml as _yaml

    manifeste = fichier.parent.parent / "MANIFEST.yaml"
    if not manifeste.is_file():
        return None
    data = _yaml.safe_load(manifeste.read_text("utf-8")) or {}
    article = (data.get("articles") or {}).get(fichier.parent.name)
    if not article:
        return None
    # `brut.txt` = anglais ; `brut.fr.txt` = français. Le dispositif s'adresse au modèle en
    # anglais depuis le ticket 074 ; le français reste au dépôt pour prouver la fidélité à la
    # source.
    morceaux = fichier.name.split(".")
    variante = morceaux[0]
    langue = morceaux[1] if len(morceaux) > 2 else "en"
    entree = (article.get(variante) or {}).get(langue) or {}
    return entree.get("sha256")


def verifier_empreinte(chemin: str, sha256_declare: str, evenement_id: str, refus):
    """Lit le texte cité et vérifie ses DEUX empreintes. Rend le contenu.

    Lève `refus` au moindre désaccord : un texte qui a bougé depuis la déclaration rend
    incomparables deux campagnes qui croient avoir joué le même article.
    """
    import hashlib

    fichier = resoudre_chemin(chemin)
    if fichier is None:
        essayes = ", ".join(str(r / chemin) for r in _racines_possibles())
        raise refus(
            f"événement « {evenement_id} » : texte introuvable — « {chemin} ». Cherché à : "
            f"{essayes}. Dans le conteneur `controller`, le corpus doit être monté "
            f"(infra/docker-compose.yml)"
        )
    brut = fichier.read_bytes()
    empreinte = hashlib.sha256(brut).hexdigest()

    attendue = str(sha256_declare or "").strip().lower()
    if not attendue:
        raise refus(
            f"événement « {evenement_id} » : `texte.sha256` absent. Un texte cité sans "
            f"empreinte n'est pas cité, il est recopié — et deux campagnes ne peuvent plus "
            f"prouver qu'elles ont joué le même article. Empreinte du fichier actuel : "
            f"{empreinte}"
        )
    if empreinte != attendue:
        raise refus(
            f"événement « {evenement_id} » : le texte a CHANGÉ depuis la déclaration. "
            f"Déclarée {attendue[:12]}…, trouvée {empreinte[:12]}… dans {fichier}. Soit le "
            f"fichier a été retouché, soit la déclaration désigne un autre texte ; dans les "
            f"deux cas, aucune campagne jouée avant ne reste comparable"
        )

    du_manifeste = _empreinte_du_manifeste(fichier, evenement_id)
    if du_manifeste is None:
        logger.warning(
            f"[evenements] « {evenement_id} » : le texte « {fichier.name} » ne relève d'aucun "
            f"manifeste de corpus — son empreinte n'est vérifiée que contre la déclaration. "
            f"Ce n'est pas une vérification réussie, c'est une vérification absente."
        )
    elif str(du_manifeste).strip().lower() != empreinte:
        raise refus(
            f"événement « {evenement_id} » : le texte concorde avec la déclaration mais PAS "
            f"avec le manifeste du corpus ({str(du_manifeste)[:12]}… attendu, {empreinte[:12]}… "
            f"trouvé). Le fichier et sa déclaration ont bougé ensemble : c'est exactement ce "
            f"que la seconde comparaison existe pour attraper"
        )
    else:
        logger.info(
            f"[evenements] « {evenement_id} » : texte cité vérifié contre sa déclaration ET "
            f"contre le manifeste du corpus — {fichier.name}, empreinte {empreinte[:12]}…"
        )
    return brut.decode("utf-8")
