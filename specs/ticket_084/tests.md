# Ticket 084 — Spécification des tests fonctionnels

> Écrite le 2026-09-16, **avant le code**. Même convention que les lots des tickets 071, 075,
> 077 et 079 : le contrat est écrit d'abord, le code ensuite, et la validation se fait par
> l'échec — casser une règle doit casser un test nommé.
>
> Objet : une requête peut désigner la LISTE des instances de passerelle admises à la servir,
> et cette liste est honorée **à la sélection**, avant qu'un appel ne soit payé.

---

## A. Le filtrage à la sélection

`LoadBalancer.select_provider` est le seul point de décision. Trois branches y cohabitent —
fournisseur forcé, cascade, rotation pondérée — et la restriction vaut pour les trois.

| # | Cas | Attendu |
|---|---|---|
| A1 | rotation, restriction à deux instances sur cinq | seules ces deux sont réservées, quel que soit le curseur de départ |
| A2 | cascade, restriction | l'ordre de cascade est conservé, mais réduit aux admises |
| A3 | restriction absente (`None`) ou vide | comportement **identique** à avant le ticket, sur les trois branches |
| A4 | la première admise refuse (quota, cooldown, débit) | bascule sur la suivante **admise**, jamais hors de l'ensemble |
| A5 | toutes les admises refusent | `RuntimeError` qui **nomme les instances admises**, et ne mentionne pas les autres comme recours |
| A6 | restriction ne désignant aucune instance connue | refus explicite, **jamais** interprété comme « aucune contrainte » |
| A7 | restriction désignant des instances connues et inconnues | refus explicite : une liste à moitié fausse est une erreur de configuration, pas une intention |
| A8 | fournisseur forcé **hors** des admises | refus explicite, sans arbitrage silencieux entre les deux contraintes |
| A9 | fournisseur forcé **dans** les admises | comportement du forçage, inchangé |

---

## B. La restriction survit au trajet

C'est la règle que le code ne donne pas gratuitement : `LLMRequest` n'interdit pas les champs
supplémentaires, donc un champ posé par le client mais non déclaré dans le modèle serait
**ignoré en silence** par la validation, sans exception ni journal.

| # | Cas | Attendu |
|---|---|---|
| B1 | payload client portant la restriction | elle est présente dans le `LLMRequest` validé côté API |
| B2 | requête sans restriction | le champ vaut `None`, et rien ne change |
| B3 | la restriction traverse Celery | elle parvient à `select_provider` telle qu'elle a été posée (sérialisable, pas d'objet non JSON) |
| B4 | trajet complet client → sélection | une requête restreinte n'est **jamais** servie par une instance hors liste |

---

## C. La clé de lot

Deux requêtes aux restrictions différentes ne doivent pas se retrouver dans le même lot :
l'une serait servie par un fournisseur qu'elle excluait, sans qu'aucune trace ne le dise.

| # | Cas | Attendu |
|---|---|---|
| C1 | deux requêtes, même catégorie, restrictions différentes | clés de lot **différentes** |
| C2 | deux requêtes, même catégorie, même restriction | clé de lot identique |
| C3 | restriction déclarée dans un ordre différent | clé identique — c'est un ensemble, pas une séquence |
| C4 | une requête restreinte et une sans restriction | clés différentes |

---

## D. La bascule après incident

Le worker relance la tâche avec un nouveau fournisseur lorsqu'une instance échoue. Sans
traitement explicite, la restriction posée au premier appel disparaîtrait au premier incident.

| # | Cas | Attendu |
|---|---|---|
| D1 | erreur 4xx sur une instance admise, d'autres admises disponibles | la tâche est rejouée **dans** l'ensemble admis |
| D2 | erreur 4xx, plus aucune admise disponible | échec franc nommant l'ensemble, **jamais** de bascule hors liste |
| D3 | crédits épuisés (402) sur une instance admise | même règle : bascule interne, ou échec nommé |
| D4 | quota journalier atteint sur la dernière admise | échec franc porteur de l'instant de reprise, sans sortir de l'ensemble |
| D5 | instances admises « seulement occupées » (fenêtre pleine, pas de panne) | le worker **attend**, comportement inchangé |

---

## E. Le dimensionnement des lots

| # | Cas | Attendu |
|---|---|---|
| E1 | taille maximale d'un lot sous restriction | calculée sur les instances **admises**, pas sur l'ensemble des fournisseurs |
| E2 | seuil de dispatch immédiat sous restriction | même règle |
| E3 | sans restriction | valeurs inchangées par rapport à avant le ticket |

---

## F. Ce que le ticket ne change pas

| # | Cas | Attendu |
|---|---|---|
| F1 | le filtre client post-appel (`allowed_providers`) | conservé, et il devient une défense en profondeur : il ne doit plus jamais se déclencher quand la restriction est transmise |
| F2 | une requête sans restriction, de bout en bout | rigoureusement le comportement d'avant le ticket — c'est la condition pour que les mesures déjà prises restent comparables |
| F3 | `min_output_required` hors de la clé de lot | **inchangé** : défaut antérieur, hors périmètre, signalé et non corrigé ici |
