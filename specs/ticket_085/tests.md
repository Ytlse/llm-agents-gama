# Ticket 085 — Spécification des tests fonctionnels

> Écrite le 2026-09-16, **avant le code**. Même convention que les tickets 071, 075, 077, 079
> et 084 : le contrat est écrit d'abord, le code ensuite, et la validation se fait par l'échec —
> casser une règle doit casser un test nommé.
>
> Objet : une contrainte de routage est propre à UN run et non à la pile ; un refus déterministe
> se dit en une seconde au lieu de deux minutes ; et « aucune instance ne sert ce modèle » cesse
> d'être annoncé quand le motif réel est « quota pas encore renouvelé ».

Les trois lots sont indépendants dans leurs tests comme dans leur livraison. L'ordre ci-dessous
est celui du ticket : A d'abord (il transforme trois heures en une seconde quelle que soit la
suite), C ensuite (du texte), B en dernier (il déplace une garantie scientifique).

---

## A. Le refus déterministe — passerelle

`RestrictionInstances` est un `ValueError`. La boucle d'attente du worker n'intercepte que
`RuntimeError` : l'exception traverse la tâche **avant** `rt.queue.pop`, si bien que le lot reste
en file et que chaque dispatch suivant le reprend et échoue à l'identique. Ce n'est pas un échec
qui coûte 120 s une fois, c'est un échec qui se réarme tout seul.

| # | Cas | Attendu |
|---|---|---|
| A1 | `RestrictionInstances` levée à la sélection | les tâches du lot **sortent** de la file, sont marquées en échec, et **aucun** rejeu Celery n'est planifié |
| A2 | le motif rendu au client | il nomme **la liste admise** ET **le fournisseur épinglé** — les deux contraintes en présence, pas une seule |
| A3 | le drapeau de dispatch du lot | `clear_scheduled` est appelé : le lot suivant n'attend pas le TTL pour rien |
| A4 | la nature de l'échec | elle n'est **pas** `passerelle_occupee`, et pas davantage `epuise` : une contradiction de configuration ne se répare pas en cherchant du quota |
| A5 | saturation ordinaire (`RuntimeError`) | comportement d'attente, de `self.retry` et de disjoncteur **exactement** inchangé — le lot A ne touche pas à ce chemin |

Précisions de conception que les tests vérifient aussi :

- **A1** — `pop` est borné par le nombre d'agents, pas de tâches : la file est drainée en boucle,
  sinon un gros lot en laisse derrière lui, et le réarmement revient par la petite porte.
- **A4** — la classification passe par `Task.error_kind`, canal structuré déjà existant
  (`quota_journalier` l'emprunte depuis le 2026-09-08), et non par la chance qu'a un texte
  d'échapper aux expressions régulières de `decideurs.py`.

### A côté client (`experiences/decideurs.py`)

| # | Cas | Attendu |
|---|---|---|
| A6 | `genre_erreur == "restriction_instances"` | l'erreur rendue est préfixée `configuration:` — ni `epuise:`, ni `passerelle_occupee:` |
| A7 | le comportement du runner face à ce type | inchangé : `configuration` est un type inconnu de `runner.py`, il tombe dans la branche d'attente. **Décision du § 9 du ticket** : ce lot rend le motif juste et rapide, il ne change pas ce que le client en fait |

---

## B. La restriction suit l'expérience

Au lancement, `experiences lancer` dérive la liste du **modèle de l'expérience** et l'impose aux
réglages du processus, au même endroit et de la même façon que `appliquer_fenetre_age` règle déjà
la fenêtre mémoire.

| # | Cas | Attendu |
|---|---|---|
| B1 | expérience en gemini 3.5, `config.yaml` portant les clés gemini 3.1 | elle s'exécute sous **ses** instances : la valeur du fichier n'atteint pas ses requêtes |
| B2 | la liste retenue | ce sont les instances servant le modèle, filtrées par `portee` — **pas** celles qui ont encore du quota : une clé momentanément au plafond reste admise, c'est le rôle du moniteur, pas de la restriction |
| B3 | écrasement d'une valeur non vide du fichier | journalisé, avec l'ancienne ET la nouvelle liste. Un écrasement muet de contrainte scientifique est le défaut qu'on corrige, pas un moyen acceptable de le corriger |
| B4 | `execution.yaml` | porte la liste retenue — une mesure archivée dit sous quelle restriction elle a été prise |
| B5 | décideur autre que `passerelle` | aucune restriction : liste **vide**. Y compris quand le fichier en portait une : la restriction suit l'expérience dans les deux sens |
| B6 | `config.yaml` non vide, `experiences lancer` absent | le chemin `make run` conserve la restriction du fichier, à l'identique. Le lot B **ne vide pas** `config.yaml` |

**B4 en reprise.** Une reprise rouvre une exécution existante : sa trace serait fausse si la
restriction avait changé entre le lancement et la reprise. La liste est donc réécrite dans les
deux branches — création et reprise — et un changement est journalisé.

**Pourquoi B6 est une règle et non un oubli.** `make run` lit `config.yaml` à l'import et n'a
aucun équivalent de l'injection par run. Vider le fichier ne déplacerait pas la restriction, il la
supprimerait — et précisément pour le run de soixante jours qui l'avait motivée, sans qu'aucune
ligne ne le dise.

---

## C. Le refus dit le bon motif

Une variable pour deux sens — « les instances qui servent ce modèle » puis « celles qui ont encore
du quota » — et le message ment de bonne foi.

| # | Cas | Attendu |
|---|---|---|
| C1 | modèle servi par personne | message **inchangé** : « aucune instance de passerelle ne sert le modèle … » |
| C2 | modèle servi, mais toutes les instances épuisées | le refus dit l'**épuisement** et rend le compte requêtes/jour par instance (`MoniteurRessources.raison_epuisement()`) |
| C3 | exclusivité | le mot « épuisée » ne peut pas apparaître quand aucune instance ne sert le modèle, et réciproquement |
| C4 | appelant qui ne passe qu'une liste (code existant, tests d'archive) | comportement et message au mot près inchangés — la séparation des deux sens est additive |

---

## Ce que ce contrat ne couvre pas

- **Le verrou par clé sur `make run`** (§ 7 du ticket) : constaté, non traité, il mérite son
  propre ticket. Aucun test ici ne prétend le couvrir.
- **`cache.enabled` et `cache_dir`** (§ 8) : même forme de défaut, même fichier partagé, mais hors
  périmètre. Les nommer sans les traiter vaut mieux que de les traiter à moitié.
- **L'arrêt du run sur refus déterministe** (§ 9) : question ouverte, hypothèse « on ne change pas
  le client » retenue et testée telle quelle en A7. Voir `questions.md`.
