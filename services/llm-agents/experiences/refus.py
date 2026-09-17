"""Classer un refus de lancement : est-il temporel, ou définitif ?

POURQUOI CE MODULE. Le 2026-09-16, quatre bras d'une campagne ont été déclarés en panne alors
qu'ils attendaient simplement du quota. Le lanceur refuse de créer une exécution quand toutes les
instances d'un modèle sont épuisées ; il sort avec le même code qu'une configuration invalide, et
la campagne, qui lance en tâche de fond sans lire ce code, ne voit qu'une absence d'état. Son
journal annonce alors « lancée 3 fois sans jamais écrire d'état », ce qui envoie chercher une
panne là où il n'y a qu'une fenêtre de quota à attendre.

TROIS CLASSES, ET TROIS ACTIONS DIFFÉRENTES.

- `quota_epuise` — les instances servent bien le modèle, leur quota du jour est consommé. Demain
  le même lancement passe. Une campagne doit REPORTER, pas échouer, et ne pas décompter de
  tentative : rien n'a été tenté.
- `quota_insuffisant` — la charge dépasse le quota journalier, quelle que soit l'heure. Attendre
  n'y change rien : il faut un modèle mieux doté, un jeu plus petit, ou accepter d'étaler sur
  plusieurs jours avec `--ignorer-aptitude`. Reporter serait une boucle sans fin, donc c'est un
  échec — mais un échec qui DIT ce qu'il est.
- `definitif` — tout le reste : configuration invalide, jeu périmé, mode incompatible. Aucune
  attente ne le résout.

La classification porte sur le TEXTE du refus, et c'est un choix assumé : les refus sont produits
à quatre endroits différents, tous déjà écrits pour être lus par un humain. Y ajouter un code
partout demanderait de toucher ces quatre endroits sans rien gagner ici ; ce qui compte est que
la règle soit à UN endroit, nommée, et testée.
"""

from __future__ import annotations

QUOTA_EPUISE = "quota_epuise"
QUOTA_INSUFFISANT = "quota_insuffisant"
DEFINITIF = "definitif"

#: Marqueur écrit à côté du journal de lancement quand un lancement est refusé.
SUFFIXE_MARQUEUR = ".refus.json"

# Ordre significatif : `quota_insuffisant` est testé AVANT `quota_epuise`, parce qu'un refus de
# charge peut mentionner les deux (« 1000 requêtes/jour contre 9695 sollicitations » nomme le
# quota sans être une pénurie du moment).
_SIGNATURES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (QUOTA_INSUFFISANT, ("hors d'atteinte", "jours de quota")),
    (QUOTA_EPUISE, ("momentanément épuisée", "momentanément épuisées")),
)


def classer(motifs: list[str]) -> str:
    """La classe d'un lot de refus. Le plus grave l'emporte : un refus définitif accompagné
    d'une pénurie de quota reste définitif, puisque attendre ne le lèverait pas."""
    if not motifs:
        return DEFINITIF
    classes = set()
    for motif in motifs:
        texte = (motif or "").lower()
        for classe, signatures in _SIGNATURES:
            if any(s.lower() in texte for s in signatures):
                classes.add(classe)
                break
        else:
            classes.add(DEFINITIF)
    if DEFINITIF in classes:
        return DEFINITIF
    if QUOTA_INSUFFISANT in classes:
        return QUOTA_INSUFFISANT
    return QUOTA_EPUISE


def est_reportable(classe: str) -> bool:
    """Un report ne vaut que pour ce qu'une attente résout. Le reste est un échec, et le dire
    tout de suite vaut mieux que de le découvrir après deux passes de repêchage."""
    return classe == QUOTA_EPUISE


__all__ = ["QUOTA_EPUISE", "QUOTA_INSUFFISANT", "DEFINITIF", "SUFFIXE_MARQUEUR",
           "classer", "est_reportable"]
