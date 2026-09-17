# Ticket 091 — Contrat de tests

Écrit AVANT le code.

## Le besoin

Rien ne relie aujourd'hui une mémoire stockée au run qui l'a produite. Contenu réel d'un point de
reprise du 2026-09-16 :

```json
{ "jour_simule": 9, "timestamp_simule": 1774321200, "ancre_run": 1773638100,
  "ecrit_le": "2026-09-16T16:37:09", "compteurs": { ... } }
```

Ni modèle, ni prompt, ni population, ni choc. Et la reprise suit le lien `experiments/current`,
qui a pointé deux fois dans la journée sur un run autre que celui qu'on croyait. Un
`make run CONT=1` pouvait donc restaurer la mémoire d'une autre expérience sans qu'une seule ligne
ne le dise. La trace de décisions du ticket 090 hérite du même angle mort.

## Le principe

**Par défaut, on ne réutilise rien.** Ni point de mémoire, ni trace de décisions. La réutilisation
se demande en **nommant le run**, et n'a lieu que si l'expérience est la même.

`make run OFFLINE=1 … REPRISE=2026-09-16_15_58`

**Aucune échappatoire.** Une identité qui diffère fait refuser le lancement. Les cas de mise au
point se traitent à la main, hors du code : un contournement prévu dans le produit finirait par
servir en mesure.

## Cas

| Cas | Reprise nommée et identité |
|---|---|
| A1 | Sans `REPRISE`, aucun point n'est restauré et aucune trace n'est chargée, même si le répertoire courant en déborde |
| A2 | Sans `REPRISE`, un `CONT=1` seul est refusé : la reprise se nomme |
| A3 | Avec `REPRISE=<nom>`, le workdir est résolu **par le nom**, pas par le lien `current` |
| A4 | `REPRISE=<nom>` désignant un run inexistant : refus nommant le répertoire cherché |
| A5 | Identités identiques : la reprise a lieu, point restauré et trace chargée |
| A6 | Une seule différence d'identité : refus **nommant le champ** qui diffère |
| A7 | Plusieurs différences : toutes sont nommées, pas seulement la première |

| Cas | Ce que l'identité retient |
|---|---|
| B1 | Modèle et instances admises |
| B2 | Variante de prompt |
| B3 | Population (chemin du sceau) |
| B4 | Mémoire longue et auto-réflexion actives ou non |
| B5 | Empreinte du choc, ou « aucun » |
| B6 | Graines de tirage, d'ordre et de météo |
| B7 | État du cache de décisions |
| B8 | Deux champs SANS influence sur la comparabilité — l'heure d'écriture, les compteurs — ne font jamais refuser |

| Cas | Écriture et survie |
|---|---|
| C1 | L'identité est écrite dans le workdir au démarrage d'un run neuf |
| C2 | Elle est recopiée dans chaque point de reprise |
| C3 | Une reprise ne réécrit PAS l'identité du run repris : c'est la référence, pas un journal |
| C4 | Un fichier d'identité absent (run antérieur au ticket) fait refuser la reprise en le disant, plutôt que de supposer l'égalité |
| C5 | Un fichier d'identité illisible fait refuser, jamais passer |

## Ce que le ticket ne change pas

Le contenu du point de reprise lui-même, sa périodicité quotidienne à 3 h, ni le gel de mémoire
pendant le rejeu. La reprise repart toujours du dernier point stable — ce qui couvre l'arrêt de la
machine et la recréation des conteneurs par une autre session : le point est écrit de façon
atomique, donc le dernier point valide l'est vraiment.
