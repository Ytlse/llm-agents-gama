"""Les textes des conditions C2, C3 et C4, et leur manifeste — ticket 059, lot 1.

LA GARDE PROPRE À CE CANAL
--------------------------
Un `vecu` de choc est écrit par nous (ticket 079) ; un article de presse est **cité**. La
différence n'est pas de style : une reformulation « qui rend le texte plus lisible pour le
modèle » ferait de C2 une sixième condition non déclarée, et personne ne saurait laquelle a été
jouée. Le texte servi est donc comparé à son empreinte à chaque chargement.

LA SEULE RÉÉCRITURE ADMISE EST LA TRADUCTION
--------------------------------------------
Les cinq articles paraissent en français ; le dispositif fonctionne en anglais depuis le ticket
074, et une phrase française dans un prompt anglais réintroduit exactement le facteur que la
bascule a supprimé. Décision de l'auteur du 2026-09-21 : **on traduit, et on le dit**.

- Chaque texte existe en DEUX fichiers, `*.fr.txt` et `*.txt`, chacun avec son empreinte.
- L'entrée servie à l'agent porte la mention « Translated from French ». Ce n'est pas un
  commentaire de dépôt : c'est une information que l'agent a, et le dispositif n'a pas à la lui
  cacher.
- Le manifeste nomme QUI a traduit et QUAND. Une traduction anonyme ne se vérifie pas.

CE QUE LE MANIFESTE REFUSE
--------------------------
Une paraphrase qui contient un mot de mobilité — la condition C3 ne séparerait plus rien. Un
témoin qui en contient un — le contrôle de spécificité mesurerait autre chose. Un témoin dont la
longueur s'écarte de plus de 15 % de son article — l'appariement est perdu, et « ajouter un
texte » cesse d'être ce qui les distingue.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from scripts.analysis.presse.lexique import mots_de_mobilite_trouves

# Les trois conditions textuelles. C1 ne reçoit rien et C5 est tabulaire : ni l'une ni l'autre
# n'a de fichier.
CONDITIONS: tuple[str, ...] = ("brut", "paraphrase", "temoin")

# Écart de longueur admis entre un témoin et l'article qu'il apparie, en mots. Au-delà, ce qui
# distingue C4 de C2 n'est plus le contenu mais la taille du bloc ajouté au contexte.
ECART_LONGUEUR_MAX = 0.15

# La mention portée dans l'entrée servie à l'agent, en tête du texte traduit.
MENTION_TRADUCTION = "Translated from French"


class RefusDeCorpus(ValueError):
    """Le corpus ne se charge pas. Le message dit la raison ET l'action."""


@dataclass(frozen=True)
class Texte:
    condition: str
    langue: str
    chemin: Path
    contenu: str
    empreinte: str
    mots: int


@dataclass(frozen=True)
class ArticleDuCorpus:
    article_id: str
    source_html: str
    empreinte_source: str
    textes: dict[tuple[str, str], Texte]  # (condition, langue) -> Texte
    # Les mots de mobilité que la paraphrase a le droit de garder, par langue : ceux qui nomment
    # l'objet même de l'événement. Un article sur le vélo partagé parle du vélo.
    exemptions: dict[str, tuple[str, ...]]

    def texte(self, condition: str, langue: str = "en") -> Texte:
        cle = (condition, langue)
        if cle not in self.textes:
            raise KeyError(f"{self.article_id} : aucun texte {condition!r} en {langue!r}")
        return self.textes[cle]

    def entree_pour_agent(self) -> str:
        """Le texte anglais, précédé de la mention de traduction.

        C'est ce que le canal `information` (lot 4) sert à l'agent, et c'est sur cette chaîne
        que la garde d'empreinte se vérifie côté run.
        """
        return f"[{MENTION_TRADUCTION}] {self.texte('brut', 'en').contenu}"


@dataclass(frozen=True)
class Corpus:
    racine: Path
    articles: dict[str, ArticleDuCorpus]
    traduction_par: str
    traduction_le: str
    empreinte_manifeste: str


def _charger_texte(
    racine: Path, article_id: str, condition: str, langue: str, declare: dict,
    temoin_commun: str | None = None,
) -> Texte:
    nom = f"{condition}.txt" if langue == "en" else f"{condition}.{langue}.txt"
    # Un témoin COMMUN aux cinq articles vit dans son propre dossier. Décision de l'auteur du
    # 2026-09-21 : un seul texte plutôt que cinq. Ce que C4 mesure — l'effet d'ajouter un texte
    # quel qu'il soit — ne demande pas un témoin par article, et un témoin unique rend la
    # condition COMPARABLE d'un article à l'autre au lieu de la faire dépendre de cinq choix.
    dossier = temoin_commun if (condition == "temoin" and temoin_commun) else article_id
    chemin = racine / dossier / nom
    if not chemin.is_file():
        raise RefusDeCorpus(
            f"texte manquant : {chemin} → chaque article porte {len(CONDITIONS)} conditions en "
            f"deux langues, soit six fichiers (ticket 059, lot 1)"
        )
    brut = chemin.read_bytes()
    empreinte = hashlib.sha256(brut).hexdigest()
    attendue = str(declare.get("sha256") or "")
    if attendue and empreinte != attendue:
        raise RefusDeCorpus(
            f"{chemin} : empreinte {empreinte[:12]} au lieu de {attendue[:12]} déclarée au "
            f"manifeste → le texte a changé après le gel. Un article est CITÉ, jamais réécrit : "
            f"restaurez le fichier, ou regelez le corpus en le disant"
        )
    contenu = brut.decode("utf-8").strip()
    if not contenu:
        raise RefusDeCorpus(f"{chemin} : texte vide")
    return Texte(condition, langue, chemin, contenu, empreinte, len(contenu.split()))


def charger_corpus(chemin_manifeste: str | Path) -> Corpus:
    chemin_manifeste = Path(chemin_manifeste)
    if not chemin_manifeste.is_file():
        raise RefusDeCorpus(
            f"manifeste du corpus introuvable : {chemin_manifeste} → produisez-le avec "
            f"`scripts/data/presse/extraire_textes.py` (ticket 059, lot 1)"
        )
    octets_manifeste = chemin_manifeste.read_bytes()
    d = yaml.safe_load(octets_manifeste.decode("utf-8")) or {}
    racine = chemin_manifeste.parent
    temoin_commun = d.get("temoin_commun")

    traduction = d.get("traduction") or {}
    par, le = str(traduction.get("par") or ""), str(traduction.get("le") or "")
    if not par or not le:
        raise RefusDeCorpus(
            f"{chemin_manifeste} : `traduction.par` et `traduction.le` sont obligatoires → une "
            f"traduction anonyme ne se vérifie pas, et les cinq textes sont traduits du français"
        )

    articles: dict[str, ArticleDuCorpus] = {}
    for article_id, contenu in (d.get("articles") or {}).items():
        contenu = contenu or {}
        textes: dict[tuple[str, str], Texte] = {}
        for condition in CONDITIONS:
            declare_cond = contenu.get(condition) or {}
            for langue in ("fr", "en"):
                declare = (declare_cond.get(langue) or {}) if isinstance(declare_cond, dict) else {}
                if condition == "temoin" and temoin_commun:
                    declare = ((d.get("temoin") or {}).get(langue)) or {}
                textes[(condition, langue)] = _charger_texte(
                    racine, article_id, condition, langue, declare, temoin_commun
                )

        # Les mots que le SUJET impose, et la garde qui empêche l'exemption de complaisance :
        # un mot ne s'exempte que s'il est dans le texte brut. Sans elle, il suffirait d'exempter
        # « voiture » sur l'article des punaises pour que la paraphrase puisse suggérer le report.
        exemptions: dict[str, tuple[str, ...]] = {}
        declarees = contenu.get("c3_mots_autorises") or {}
        for langue in ("fr", "en"):
            mots = tuple((declarees.get(langue) or {}).get("mots") or ())
            texte_brut = textes[("brut", langue)]
            dans_le_brut = set(mots_de_mobilite_trouves(texte_brut.contenu, langue))
            absents = [mot for mot in mots if mot not in dans_le_brut]
            if absents:
                raise RefusDeCorpus(
                    f"{article_id} ({langue}) : {absents} exemptés mais absents du texte brut → "
                    f"on n'exempte pas un mot par précaution, on exempte celui que le sujet "
                    f"impose. Retirez-les de `c3_mots_autorises`"
                )
            if mots and not str((declarees.get(langue) or {}).get("motif") or "").strip():
                raise RefusDeCorpus(
                    f"{article_id} ({langue}) : `c3_mots_autorises` sans motif → une exemption "
                    f"sans raison ne se discute pas, et c'est par là que la condition C3 se vide"
                )
            exemptions[langue] = mots

        # C3 et C4 ne contiennent aucun mot de mobilité hors exemptions, dans LES DEUX langues.
        # Traduire n'est pas une occasion de réintroduire un mot que la réécriture avait retiré.
        for condition in ("paraphrase", "temoin"):
            for langue in ("fr", "en"):
                t = textes[(condition, langue)]
                # Le témoin n'a AUCUNE exemption : il ne parle pas de l'événement, donc rien
                # dans son sujet n'impose un mot de mobilité.
                admis = exemptions[langue] if condition == "paraphrase" else ()
                trouves = mots_de_mobilite_trouves(t.contenu, langue, admis)
                if trouves:
                    raise RefusDeCorpus(
                        f"{t.chemin} : mots de mobilité présents {list(trouves)} → la condition "
                        f"{'C3' if condition == 'paraphrase' else 'C4'} ne sépare plus rien. "
                        f"Réécrivez le passage, ou retirez le mot de "
                        f"`scripts/analysis/presse/lexique.py` en disant pourquoi"
                    )

        # Appariement de longueur du témoin, sur la version ANGLAISE : c'est elle qui entre dans
        # le contexte, et c'est donc sa taille qui compte.
        brut_en, temoin_en = textes[("brut", "en")], textes[("temoin", "en")]
        if brut_en.mots:
            ecart = abs(temoin_en.mots - brut_en.mots) / brut_en.mots
            if ecart > ECART_LONGUEUR_MAX:
                raise RefusDeCorpus(
                    f"{article_id} : le témoin fait {temoin_en.mots} mots contre "
                    f"{brut_en.mots} pour l'article, soit {ecart:.0%} d'écart (max "
                    f"{ECART_LONGUEUR_MAX:.0%}) → ce qui distingue C4 de C2 ne doit pas être la "
                    f"taille du bloc ajouté au contexte"
                )

        articles[article_id] = ArticleDuCorpus(
            article_id=article_id,
            source_html=str(contenu.get("source", {}).get("fichier", "")),
            empreinte_source=str(contenu.get("source", {}).get("sha256", "")),
            textes=textes,
            exemptions=exemptions,
        )

    if not articles:
        raise RefusDeCorpus(f"{chemin_manifeste} : aucun article déclaré")

    return Corpus(
        racine=racine,
        articles=articles,
        traduction_par=par,
        traduction_le=le,
        empreinte_manifeste=hashlib.sha256(octets_manifeste).hexdigest(),
    )
