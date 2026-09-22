"""La grille des vingt signes, gelée avant la première requête — ticket 059, lot 2.

CE QUE CE MODULE GARANTIT
-------------------------
Une prédiction pré-enregistrée n'a de valeur que si l'on peut prouver qu'elle précédait la
mesure. Trois choses le prouvent, et ce module les porte toutes les trois :

1. **Vingt cellules, ni plus ni moins.** Cinq articles par quatre modes. Une cellule qui
   manque est une prédiction qu'on n'a pas eu à écrire ; une cellule en trop est une
   prédiction ajoutée après coup.
2. **Un signe par cellule, y compris l'absence d'effet.** `signe: '0'` est une PRÉDICTION —
   « aucun déplacement net attendu » — et un déplacement significatif la réfute au même titre
   qu'un signe inversé. L'équivalence est stricte : `signe == '0'` si et seulement si
   `intensite == 0`. Sans elle, une cellule pourrait se replier sur « pas d'avis » après la
   mesure, et le dénominateur du taux de signe deviendrait négociable.
3. **Une empreinte.** `Grille.empreinte` se recopie en tête de tout rapport de dépouillement.
   C'est le seul point qui rend le « pré-enregistré » vérifiable a posteriori : une grille
   modifiée après une campagne se voit.

Le refus est FRANC. Une grille invalide arrête le chargement plutôt que de laisser un
dépouillement se faire sur dix-neuf cellules et rendre un taux dont personne ne saura qu'il
portait sur autre chose que ce qui est annoncé.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

SIGNES_ADMIS: tuple[str, ...] = ("+", "-", "0")
INTENSITES_ADMISES: tuple[int, ...] = (0, 1, 2, 3)

# Le chapitre 7 annonce « vingt prédictions signées » et pose la barre du binomial à quinze
# concordances. Le compte n'est donc pas une convenance de format : il est cité dans l'article,
# et le changer oblige à recalculer cette barre AVANT la campagne.
CELLULES_ATTENDUES = 20


class RefusDeGrille(ValueError):
    """La grille ne se charge pas. Le message dit la raison ET l'action."""


@dataclass(frozen=True)
class Cellule:
    article: str
    mode: str
    signe: str
    intensite: int
    motif: str

    @property
    def sans_effet_attendu(self) -> bool:
        return self.signe == "0"

    def concorde(self, observe: str) -> bool:
        """Le signe observé concorde-t-il avec le signe prédit ?

        `observe` vient du dépouillement et vaut '+', '-' ou '0'. La comparaison est directe,
        y compris pour '0' : prédire l'absence d'effet et l'observer est une concordance, pas
        une abstention.
        """
        if observe not in SIGNES_ADMIS:
            raise ValueError(f"signe observé hors domaine : {observe!r} ({SIGNES_ADMIS})")
        return observe == self.signe


@dataclass(frozen=True)
class Grille:
    version: int
    gele_le: str
    source: str
    modes: tuple[str, ...]
    cellules: tuple[Cellule, ...]
    empreinte: str
    chemin: Path

    def de(self, article: str, mode: str) -> Cellule:
        for c in self.cellules:
            if c.article == article and c.mode == mode:
                return c
        raise KeyError(f"aucune cellule pour ({article}, {mode})")

    @property
    def articles(self) -> tuple[str, ...]:
        vus: list[str] = []
        for c in self.cellules:
            if c.article not in vus:
                vus.append(c.article)
        return tuple(vus)


def charger_grille(chemin: str | Path) -> Grille:
    chemin = Path(chemin)
    if not chemin.is_file():
        raise RefusDeGrille(
            f"grille des signes introuvable : {chemin} → vérifiez le chemin, ou gelez la grille "
            f"avant toute campagne (ticket 059, lot 2)"
        )
    brut = chemin.read_bytes()
    try:
        d = yaml.safe_load(brut.decode("utf-8")) or {}
    except yaml.YAMLError as err:
        raise RefusDeGrille(f"grille illisible ({chemin}) : {err}") from err

    modes = tuple(d.get("modes") or ())
    if not modes:
        raise RefusDeGrille(f"{chemin} : `modes` est vide → déclarez les modes de la grille")

    articles = d.get("articles") or {}
    cellules: list[Cellule] = []
    for nom_article, contenu in articles.items():
        declarees = (contenu or {}).get("cellules") or {}
        manquants = [m for m in modes if m not in declarees]
        if manquants:
            raise RefusDeGrille(
                f"{chemin} : l'article {nom_article!r} n'a pas de cellule pour {manquants} → "
                f"une cellule absente est une prédiction qu'on n'a pas eu à écrire, ajoutez-la "
                f"(signe '0' est un choix légitime, l'absence n'en est pas un)"
            )
        en_trop = [m for m in declarees if m not in modes]
        if en_trop:
            raise RefusDeGrille(
                f"{chemin} : l'article {nom_article!r} déclare des modes hors grille {en_trop} → "
                f"retirez-les ou ajoutez-les à `modes`"
            )
        for mode in modes:
            c = declarees[mode] or {}
            signe = str(c.get("signe", ""))
            if signe not in SIGNES_ADMIS:
                raise RefusDeGrille(
                    f"{chemin} : ({nom_article}, {mode}) porte le signe {signe!r} → "
                    f"attendu {SIGNES_ADMIS}"
                )
            intensite = c.get("intensite")
            if intensite not in INTENSITES_ADMISES:
                raise RefusDeGrille(
                    f"{chemin} : ({nom_article}, {mode}) porte l'intensité {intensite!r} → "
                    f"attendu {INTENSITES_ADMISES}"
                )
            if (signe == "0") != (intensite == 0):
                raise RefusDeGrille(
                    f"{chemin} : ({nom_article}, {mode}) porte signe={signe!r} et "
                    f"intensite={intensite} → l'équivalence est stricte, « pas d'effet attendu » "
                    f"s'écrit signe '0' ET intensité 0. Une cellule qui déclare un signe sans "
                    f"intensité pourrait se replier sur « pas d'avis » après la mesure"
                )
            motif = str(c.get("motif") or "").strip()
            if not motif:
                raise RefusDeGrille(
                    f"{chemin} : ({nom_article}, {mode}) n'a pas de motif → une prédiction sans "
                    f"raison ne se discute pas"
                )
            cellules.append(Cellule(nom_article, mode, signe, int(intensite), motif))

    if len(cellules) != CELLULES_ATTENDUES:
        raise RefusDeGrille(
            f"{chemin} : {len(cellules)} cellules au lieu de {CELLULES_ATTENDUES} → le chapitre 7 "
            f"annonce vingt prédictions signées et pose la barre du binomial à quinze "
            f"concordances. Changer ce compte oblige à recalculer cette barre AVANT la campagne, "
            f"jamais après"
        )

    return Grille(
        version=int(d.get("version", 0)),
        gele_le=str(d.get("gele_le", "")),
        source=str(d.get("source", "")),
        modes=modes,
        cellules=tuple(cellules),
        empreinte=hashlib.sha256(brut).hexdigest(),
        chemin=chemin,
    )
