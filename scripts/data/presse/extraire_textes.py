#!/usr/bin/env python3
"""Extrait le texte des articles archivés et prépare le corpus — ticket 059, lot 1.

POURQUOI UN SCRIPT PLUTÔT QU'UN COPIER-COLLER
---------------------------------------------
Le texte de la condition C2 est **cité**, pas rédigé. Un extrait recopié à la main ne se
rejoue pas : personne ne peut vérifier qu'il vient bien de l'archive, ni reproduire la
sélection. Ici, la règle de sélection est écrite — titre, chapeau, puis les premiers
paragraphes du corps jusqu'à un plafond de mots — et deux exécutions rendent le même texte.

CE QUE LE SCRIPT NE FAIT PAS
----------------------------
Il ne traduit pas et ne paraphrase pas : ces deux opérations demandent un modèle, elles se
déclarent, et elles vivent dans `traduire` et `paraphraser` — deux passes séparées dont le
manifeste garde la trace de qui les a faites et quand. Un script qui traduirait au passage
rendrait la traduction invisible, et l'article doit dire qu'elle a eu lieu.

Il ne choisit pas non plus les textes témoins de C4 : le corpus des trente articles a été
constitué pour son lien avec la mobilité, aucun de ses membres ne peut servir de témoin
neutre. Voir `--verifier`, qui le signale plutôt que de le taire.

USAGE
-----
    services/llm-agents/.venv/bin/python -m scripts.data.presse.extraire_textes extraire
    services/llm-agents/.venv/bin/python -m scripts.data.presse.extraire_textes sceller --par "…"
    services/llm-agents/.venv/bin/python -m scripts.data.presse.extraire_textes verifier
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[3]
SOURCES = RACINE / "docs" / "paper" / "sources" / "actualites"
HTML = SOURCES / "articles_html"
CORPUS = SOURCES / "articles_txt"
MANIFESTE = CORPUS / "MANIFEST.yaml"

# Les cinq articles retenus, et le fichier archivé de chacun. L'identifiant est celui de la
# grille des signes : les deux fichiers se lisent ensemble, et un identifiant qui divergerait
# ferait scorer une prédiction contre un autre article.
ARTICLES: dict[str, str] = {
    "a09_vent_autan": "09_vent_autan_fermeture_parcs.html",
    "a13_punaises_metro": "13_psychose_punaises_metro.html",
    "a07_greve_eboueurs": "07_greve_eboueurs_hypercentre.html",
    "a18_la_machine": "18_minotaure_la_machine.html",
    "a25_velotoulouse": "25_velotoulouse_electrique.html",
}

# Le témoin de la condition C4, commun aux cinq articles. Il ne peut PAS venir du corpus des
# trente : celui-ci a été constitué article par article POUR son lien avec la mobilité, et un
# témoin doit n'en avoir aucun. Celui retenu par l'auteur le 2026-09-21 est une dépêche de
# sciences naturelles — une espèce de félin décrite en Bolivie.
TEMOIN_COMMUN = "_temoin_commun"

# Plafond de mots de l'extrait. Un article entier noierait le reste du contexte : le chapitre 6
# mesure un prompt de ~2 100 jetons, et y verser mille mots de presse changerait la grandeur
# mesurée au lieu de l'éclairer. Le plafond coupe à la fin d'un paragraphe ; quand un seul
# paragraphe le dépasse — la mise en page de certains titres de presse n'en fait qu'un — il
# coupe à la fin d'une phrase. L'extrait reste continu dans les deux cas : c'est une citation,
# pas un montage.
MOTS_MAX = 220

# Ce qui n'est pas de l'article : crédits photo, boutons de partage, fils d'Ariane, mentions de
# régie. Ces lignes traversent l'extraction de `get_text` et n'ont rien à faire dans un extrait
# cité. Comparaison faite sans accents ni casse.
LIGNES_CHROME: tuple[str, ...] = (
    "ajouter aux sources", "ajouter comme source", "sur facebook", "sur whatsapp",
    "copier le lien", "nouvelle fenetre", "temps de lecture", "credit", "article redige par",
    "journaliste", "publie le", "publie :", "mis a jour", "modifie :", "l'essentiel",
    "partager", "abonnez-vous", "s'abonner", "newsletter", "commentaires", "voir les",
    "(c)", "©", "ddm -", "photo",
    # Encarts de recommandation : ils traversent le corps de l'article et parlent d'autre
    # chose. Laissés en place, ils feraient lire à l'agent un titre sans rapport avec
    # l'événement, et C2 mesurerait deux textes au lieu d'un.
    "a lire aussi", "lire aussi", "sur le meme sujet", "a voir aussi", "notre dossier",
    "cet article", "en savoir plus",
    # Interpellations du lecteur : fils de commentaires, alertes, sondages. Elles s'adressent à
    # qui lit le site, pas à qui lit l'article, et un agent à qui on demande s'il veut suivre
    # une discussion lit autre chose que l'événement qu'on prétend lui servir.
    "vous souhaitez", "souhaitez-vous", "voulez-vous", "donnez votre avis", "reagir",
    "recevez", "inscrivez-vous", "connectez-vous", "identifiez-vous",
)


# Fragments de classe ou d'identifiant qui désignent une zone hors article. La comparaison est
# une inclusion, sans casse : les sites combinent ces mots avec leurs propres préfixes
# (`ldm-comments-list`, `block-related-articles`).
_FRAGMENTS_HORS_ARTICLE: tuple[str, ...] = (
    "comment", "commentaire", "reaction", "forum", "disqus", "related", "recommend",
    "sidebar", "advert", "publicite", "sponsor", "partner", "newsletter", "social",
    "share", "partage", "breadcrumb", "tag-list",
)

# Part du texte de la page au-delà de laquelle un bloc est le CORPS, quelle que soit sa classe.
# La Dépêche enveloppe ses articles dans un conteneur nommé `paywall` : la liste ci-dessus, prise
# au mot, supprimait l'article entier et l'extraction rendait un fichier vide. Une liste de mots
# ne peut pas prévoir les conventions de chaque site ; une garde sur la taille, si.
PART_CORPS_MIN = 0.40


def _ZONES_HORS_ARTICLE(valeur) -> bool:  # noqa: N802 — prédicat passé à BeautifulSoup
    """Vrai si une classe ou un identifiant désigne une zone qui n'est pas le corps."""
    if not valeur:
        return False
    plat = " ".join(valeur) if isinstance(valeur, list) else str(valeur)
    plat = _sans_accents(plat).lower()
    return any(f in plat for f in _FRAGMENTS_HORS_ARTICLE)


def _sans_accents(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def _est_chrome(ligne: str) -> bool:
    plat = _sans_accents(ligne).lower().strip()
    # Une accroche tronquée par la maquette — annonce immobilière, article sponsorisé, « lire
    # la suite » — se reconnaît à ses points de suspension entre crochets. Elle n'appartient
    # pas au corps de l'article, et une annonce d'appartement dans un extrait de presse
    # ajouterait au contexte de l'agent un sujet que le protocole n'a pas déclaré.
    if plat.endswith("[...]") or plat.endswith("[…]"):
        return True
    if len(plat) < 25:
        # Une ligne courte est presque toujours une étiquette de navigation ou une légende.
        # Le corps d'un article de presse ne fait pas de phrases de vingt-cinq caractères.
        return True
    return any(marqueur in plat for marqueur in LIGNES_CHROME)


def extraire_texte(chemin_html: Path) -> tuple[str, str]:
    """(titre, corps) — le titre tel qu'il paraît, et les premiers paragraphes du corps."""
    from bs4 import BeautifulSoup  # importé ici : le script `verifier` n'en a pas besoin

    soup = BeautifulSoup(chemin_html.read_text(encoding="utf-8", errors="replace"), "html.parser")
    for t in soup(["script", "style", "nav", "header", "footer", "aside", "figure", "form"]):
        t.decompose()

    # Les zones qui ne sont pas l'article, retirées par leur STRUCTURE et non par leurs mots.
    # Les sites de presse rangent commentaires, recommandations et publicités dans l'arbre du
    # document, souvent sous la même balise que le corps : `La Dépêche` faisait ainsi finir
    # l'extrait du vent d'Autan sur un commentaire de lecteur conseillant un site de météo.
    # Filtrer sur le texte ne marche pas — un commentaire ressemble à une phrase d'article.
    total = len(soup.get_text(" ", strip=True)) or 1
    for attribut in ("class", "id"):
        for t in soup.find_all(attrs={attribut: _ZONES_HORS_ARTICLE}):
            if len(t.get_text(" ", strip=True)) / total < PART_CORPS_MIN:
                t.decompose()

    h1 = soup.find("h1")
    titre = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else ""

    zone = soup.find("article") or soup.find("main") or soup.body
    if zone is None:
        return titre, ""

    paragraphes: list[str] = []
    mots = 0
    for p in zone.find_all("p"):
        ligne = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
        if not ligne or _est_chrome(ligne) or ligne == titre:
            continue
        if ligne in paragraphes:
            continue
        n = len(ligne.split())
        if mots + n > MOTS_MAX:
            if paragraphes:
                break
            ligne = _couper_a_la_phrase(ligne, MOTS_MAX)
            n = len(ligne.split())
        paragraphes.append(ligne)
        mots += n
    return titre, "\n\n".join(paragraphes)


def _couper_a_la_phrase(texte: str, mots_max: int) -> str:
    """Tronque à la dernière phrase complète sous `mots_max`, ou à la première si elle dépasse.

    Couper au milieu d'une phrase produirait un extrait qui ne se lit pas, et un agent à qui
    l'on sert une phrase inachevée n'est plus dans les conditions qu'on prétend mesurer.
    """
    phrases = re.split(r"(?<=[.!?…])\s+", texte)
    garde: list[str] = []
    mots = 0
    for phrase in phrases:
        n = len(phrase.split())
        if garde and mots + n > mots_max:
            break
        garde.append(phrase)
        mots += n
    return " ".join(garde)


def _ecrire(chemin: Path, contenu: str) -> str:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    donnees = (contenu.strip() + "\n").encode("utf-8")
    chemin.write_bytes(donnees)
    return hashlib.sha256(donnees).hexdigest()


def commande_extraire() -> int:
    """Écrit `brut.fr.txt` pour les cinq articles et amorce le manifeste."""
    manifeste: dict = {
        "corpus": "presse locale toulousaine — ticket 059, lot 1",
        "extrait_le": date.today().isoformat(),
        "regle_de_selection": (
            f"titre, puis paragraphes du corps dans l'ordre de parution, chrome retiré, "
            f"coupe à la fin d'un paragraphe sous {MOTS_MAX} mots"
        ),
        "traduction": {"par": None, "le": None},
        "articles": {},
    }
    if MANIFESTE.is_file():
        ancien = yaml.safe_load(MANIFESTE.read_text(encoding="utf-8")) or {}
        manifeste["traduction"] = ancien.get("traduction", manifeste["traduction"])
        manifeste["articles"] = ancien.get("articles") or {}

    for article_id, nom in ARTICLES.items():
        source = HTML / nom
        if not source.is_file():
            print(f"  ABSENT  {article_id} : {source}", file=sys.stderr)
            return 2
        titre, corps = extraire_texte(source)
        if not corps:
            print(f"  VIDE    {article_id} : aucun paragraphe retenu dans {nom}", file=sys.stderr)
            return 2
        if not titre:
            # Pas bloquant : certaines archives n'ont pas de <h1> exploitable. Mais l'extrait
            # perd alors l'accroche que le lecteur voit en premier, et cela se sait.
            print(f"  (sans titre) {article_id} : aucun <h1> dans {nom}", file=sys.stderr)
        texte = f"{titre}\n\n{corps}" if titre else corps
        sha = _ecrire(CORPUS / article_id / "brut.fr.txt", texte)
        # Les clés déjà présentes sont CONSERVÉES — au premier rang desquelles
        # `c3_mots_autorises`, qui se déclare à la main et se justifie. Une réextraction ne doit
        # pas effacer une décision éditoriale au motif qu'elle recalcule un texte.
        entree = manifeste.setdefault("articles", {}).setdefault(article_id, {})
        entree["source"] = {
            "fichier": f"articles_html/{nom}",
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }
        entree.setdefault("brut", {})["fr"] = {"sha256": sha, "mots": len(texte.split())}
        print(f"  écrit   {article_id}/brut.fr.txt — {len(texte.split())} mots")

    MANIFESTE.write_text(
        yaml.safe_dump(manifeste, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    print(f"\nmanifeste : {MANIFESTE}")
    return 0


def commande_sceller(par: str, le: str) -> int:
    """Recalcule l'empreinte de chaque texte présent et pose la trace de la traduction.

    À lancer une fois le corpus complet, et plus jamais ensuite : à partir de là, toute
    divergence entre un fichier et son empreinte fait REFUSER le chargement. C'est ce qui
    distingue un texte cité d'un texte qu'on retouche entre deux campagnes.
    """
    if not MANIFESTE.is_file():
        print("manifeste absent — lancez `extraire` d'abord", file=sys.stderr)
        return 2
    manifeste = yaml.safe_load(MANIFESTE.read_text(encoding="utf-8")) or {}
    manifeste["traduction"] = {"par": par, "le": le}
    manifeste["scelle_le"] = date.today().isoformat()

    scelles = 0
    for article_id in ARTICLES:
        entree = manifeste.setdefault("articles", {}).setdefault(article_id, {})
        for condition in ("brut", "paraphrase"):
            par_langue = entree.setdefault(condition, {})
            for langue in ("fr", "en"):
                nom = f"{condition}.txt" if langue == "en" else f"{condition}.{langue}.txt"
                chemin = CORPUS / article_id / nom
                if not chemin.is_file():
                    par_langue.pop(langue, None)
                    continue
                donnees = chemin.read_bytes()
                par_langue[langue] = {
                    "sha256": hashlib.sha256(donnees).hexdigest(),
                    "mots": len(donnees.decode("utf-8").split()),
                }
                scelles += 1
            if not par_langue:
                entree.pop(condition, None)

    MANIFESTE.write_text(
        yaml.safe_dump(manifeste, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    print(f"{scelles} texte(s) scellé(s) — traduction par {par}, le {le}")
    return 0


def commande_verifier() -> int:
    """Dit ce qui manque au corpus, sans rien écrire.

    Le témoin est COMMUN aux cinq articles depuis le 2026-09-21 : il vit dans `_temoin_commun/`
    et non dans chaque dossier d'article. Ce que C4 mesure — l'effet d'ajouter un texte quel
    qu'il soit — n'en demande qu'un, et un témoin unique rend la condition comparable d'un
    article à l'autre au lieu de la faire dépendre de cinq choix.
    """
    attendus = [(a, c, lg) for a in ARTICLES for c in ("brut", "paraphrase") for lg in ("fr", "en")]
    attendus += [(TEMOIN_COMMUN, "temoin", lg) for lg in ("fr", "en")]
    manquants = [
        (a, c, lg)
        for a, c, lg in attendus
        if not (CORPUS / a / (f"{c}.txt" if lg == "en" else f"{c}.{lg}.txt")).is_file()
    ]
    print(f"{len(attendus) - len(manquants)}/{len(attendus)} fichiers présents")
    for a, c, lg in manquants:
        print(f"  manque  {a}/{c}.{'' if lg == 'en' else lg + '.'}txt")
    return 1 if manquants else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("commande", choices=("extraire", "sceller", "verifier"))
    p.add_argument("--par", help="qui a traduit — obligatoire pour `sceller`")
    p.add_argument("--le", default=date.today().isoformat(), help="date de la traduction")
    args = p.parse_args(argv)
    if args.commande == "sceller":
        if not args.par:
            p.error("`sceller` exige --par : une traduction anonyme ne se vérifie pas")
        return commande_sceller(args.par, args.le)
    return {"extraire": commande_extraire, "verifier": commande_verifier}[args.commande]()


if __name__ == "__main__":
    raise SystemExit(main())
