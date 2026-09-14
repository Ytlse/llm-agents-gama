"""Le garde d'archive froide — un seul endroit qui dit ce qu'« archivé » veut dire (ticket 074, A-4).

    Froid = restaurable et auditable, jamais utilisé ni référencé.

À ne pas confondre avec le statut `archivee` de la plateforme (`experiences.statut`), qui ne
change que la **visibilité** : les fichiers y restent en place et restent lisibles. Ici, le
chemin lui-même est hors service.

Le garde porte sur l'**EMPLACEMENT**, jamais sur une correspondance de texte dans le nom : une
cohorte qui s'appellerait « population_archivistes » reste parfaitement lisible. Il suffit
qu'un segment du chemin s'appelle `archive` pour que la lecture soit refusée.

Pourquoi un refus dans le code et pas une phrase dans un README : les 36 exécutions de la
plateforme ont toutes lu la cohorte v1 quand la référence de l'article était la v5, et rien ne
s'y est opposé (ticket 045). Un garde-fou qui n'existe que dans la prose ne se déclenche jamais.

La dérogation demande un **MOTIF**, pas un booléen : `confirme=True` se coche sans y penser,
`confirme="garde de comparabilité D-7, ticket 074"` s'écrit, se journalise et se relit.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

# Segment de chemin qui marque un contenu retiré du service.
SEGMENT_ARCHIVE = "archive"


class ContenuArchive(ValueError):
    """Lecture refusée : le contenu a été retiré du service (archive froide)."""


def sous_archive(chemin: str | Path) -> bool:
    """Le chemin traverse-t-il un dossier `archive` ?"""
    return SEGMENT_ARCHIVE in Path(chemin).resolve().parts


def verifier(
    chemin: str | Path,
    confirme: str | None,
    *,
    quoi: str,
    comment_lever: str,
    repli: str = "",
) -> None:
    """Refuse `chemin` s'il est sous archive, sauf motif explicite — et journalise la dérogation.

    - `quoi` nomme la nature du contenu (« une population », « un jeu scellé »), article compris :
      la phrase est construite autour, sans accord à deviner ;
    - `comment_lever` dit CONCRÈTEMENT comment passer outre — le champ à écrire, pas « fournir un
      motif ». Un refus qui ne dit pas quoi faire se contourne au jugé, ou se subit ;
    - `repli` nomme la référence courante, quand il en existe une.
    """
    if not sous_archive(chemin):
        return
    motif = confirme.strip() if isinstance(confirme, str) else ""
    if not motif:
        raise ContenuArchive(
            f"lecture refusée — {quoi} en archive froide : {chemin}\n"
            f"  Un contenu sous `{SEGMENT_ARCHIVE}/` est restaurable et auditable, mais il ne se "
            f"rejoue pas et ne se référence pas."
            + (f"\n  La référence courante est `{repli}`." if repli else "")
            + f"\n  Pour le lire malgré tout : {comment_lever}. Le motif est journalisé et doit "
            "être consigné dans le ticket qui le demande — un booléen se coche sans y penser, "
            "un motif s'écrit et se relit."
        )
    logger.warning(
        f"[froid] DÉROGATION : lecture en archive froide de {chemin} — motif : {motif!r}. "
        f"Cette lecture ne fonde aucune mesure comparable à celles de la référence courante."
    )


__all__ = ["SEGMENT_ARCHIVE", "ContenuArchive", "sous_archive", "verifier"]
