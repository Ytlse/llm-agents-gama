# Ticket 098 — L'ancien jeu v6 EN passe en archive froide

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-21, à la demande de l'auteur : « archiver les expériences de
> l'ancien jeu de test, inaccessibles à chaud, consultables à froid ».

---

## 1. La question, en une phrase

Le substrat `population_1000_AAMAS_v6_20260316_EN` a été remplacé le 2026-09-16 par sa version
corrigée (`…_EN_c`, ticket 088). Ses 31 exécutions restent sur le disque, lisibles, scorées et
reprenables. Doivent-elles le rester ?

Non. Elles sont **fausses pour la raison exacte qui a motivé le ticket 088** : pour 797 des 894
personas mobiles, l'offre d'itinéraires et la météo ont été calculées pour le 17 mars au lieu
du 16. Une mesure fausse qu'on laisse à portée de main finit par être lue.

## 2. Pourquoi le statut `archivee` ne suffit pas

La plateforme offre déjà `make experience-statuer … STATUT=archivee`. Ce marqueur change la
**visibilité** — la ligne sort du listing par défaut — et rien d'autre : les fichiers restent en
place, le code continue de les résoudre, et un `--inclure-masquees` les ramène.

Ce n'est pas ce qui est demandé, et ce n'est pas ce qu'il faut. Le précédent est écrit dans
`experiences/froid.py` :

> Les 36 exécutions de la plateforme ont toutes lu la cohorte v1 quand la référence de
> l'article était la v5, et rien ne s'y est opposé (ticket 045). Un garde-fou qui n'existe que
> dans la prose ne se déclenche jamais.

La réponse du dépôt à ce défaut est l'**archive froide** : le contenu quitte `data/` pour
`archive/`, et `experiences.froid.verifier` refuse tout chemin traversant un segment `archive`.
Le garde porte sur l'emplacement, pas sur une correspondance de nom. Déroger exige un **motif
écrit** — `confirme=True` se coche sans y penser, `confirme="…"` s'écrit, se journalise en
WARNING et se relit.

## 3. Ce qui est gelé

`archive/2026-09-21_ancien_jeu_v6_EN/`, frère de `data/` et hors git :

| Pièce | Volume | Pourquoi |
|-------|--------|----------|
| 36 dossiers d'expérience (31 exécutions) | 322,5 Mo | toutes décidées sur le substrat daté du 17 mars |
| le jeu scellé `population_1000_AAMAS_v6_20260316_EN` | 38 Mo | voir § 3.1 |

### 3.1 Pourquoi le jeu part avec les exécutions

Deux raisons, et la seconde est la plus forte.

**Restaurabilité.** Froid veut dire « restaurable et auditable ». Rejouer une exécution archivée
demande son substrat : `journal.regenerer` recharge jeu **et** cohorte, et `Jeu.charger` accepte
déjà `archive_confirmee=<motif>`. Une exécution archivée sans son jeu est auditable mais plus
rejouable — c'est une demi-archive.

**Non-réutilisation.** Tant que le jeu reste sous `data/jeux/`, le tableau de bord continue de le
proposer (R17 n'écarte que ce qui est déjà sous `archive/`) et rien n'empêche de définir demain
une expérience neuve sur le substrat daté du 17 mars. C'est très exactement le défaut du ticket
045, à un substrat près.

### 3.2 Ce qui n'est pas gelé

Les 38 exécutions du jeu corrigé, les 12 du jeu d'enquête 058, et la cohorte
`population_1000_AAMAS_v6` — la correction du ticket 088 portait sur le calcul de l'offre, pas
sur les personas, et le jeu corrigé lit la même cohorte.

## 4. Ce que le gel ne coûte pas

Vérifié **avant** de déplacer quoi que ce soit, bras par bras :

- **Aucun bras portant une exécution `terminee` sur l'ancien jeu n'est dépourvu de contrepartie
  `terminee` sur le jeu corrigé.** 29 bras appariés ; 26 exécutions terminées d'un côté, 32 de
  l'autre. Les 7 dossiers sans contrepartie sont 6 coquilles à 0 exécution et un bras `arretee`
  jamais abouti.
- **Les figures du chapitre 6 ne dépendent déjà plus de l'ancien jeu.** `plot_chapitre6.py`
  porte un repli explicite (« le score du jeu corrigé si le rejeu a abouti, celui de l'ancien
  jeu sinon ») ; exécuté le 2026-09-21 avant le gel, il journalise
  `Décideurs lus : 13 sur 13 (0 sur l'ancien jeu, 0 sans aucun score)`. Le repli est déjà mort.
  Le gel ne le tue pas, il l'enregistre.

Ce constat est la condition du ticket. S'il avait été faux, le gel aurait dû attendre la fin du
rejeu.

## 5. Ce qui change dans le code

| Fichier | Quoi |
|---------|------|
| `scripts/archiver_ancien_jeu_v6_en.py` | le script de gel : simulation par défaut, idempotent, rien n'est supprimé, chaque origine journalisée avec son empreinte |
| `services/llm-agents/experiences/jeux/reference.yaml` | l'entrée `anciens[0]` dit désormais **où** le substrat est parti |
| `scripts/analysis/plot_chapitre6.py` | le repli nomme l'archive froide au lieu de rendre un `None` muet |
| `services/llm-agents/tests/test_093_selection_personas.py` | `RUN_REFERENCE` repointé sur le jeu corrigé — sans quoi le test se met en `skip` silencieux |
| `scripts/tests/test_098_archive_ancien_jeu.py` | la recette, en test |

### 5.1 La garde de démarrage est scopée, et c'est volontaire

Le script du ticket 074 refusait de démarrer si **une** exécution du dépôt avait écrit sa
progression depuis moins de 120 s. C'était juste : il déplaçait `data/experiences` en entier.

Ici l'ensemble déplacé est **disjoint** du reste : la garde porte donc sur les seules pièces
concernées, et se contente d'**avertir** pour le travail vivant ailleurs. Une garde globale
aurait interdit le gel tant qu'une expérience sans rapport tourne — c'est-à-dire, en pratique,
jamais.

## 6. Recette

1. `plot_chapitre6.py` avant le gel → figures de référence, et `0 sur l'ancien jeu` au journal.
2. Le script sans `--appliquer` → annonce les pièces, n'écrit rien.
3. Avec `--appliquer`, puis relancé → « rien à faire » (idempotence).
4. `plot_chapitre6.py` après → **PNG identiques bit à bit**, toujours 13 décideurs sur 13.
   (Les SVG portent un horodatage `dc:date` et des identifiants de `clip-path` tirés au hasard :
   ils diffèrent à chaque rendu sans que le dessin bouge. La comparaison se fait sur les PNG.)
5. `pytest scripts/tests/test_098_archive_ancien_jeu.py scripts/tests/test_074_archive_froide.py`
6. `pytest services/llm-agents/tests/test_093_selection_personas.py` — passe, ne *skippe* pas.
7. Tableau de bord : le groupe `📦 … · ancien jeu de référence (31 exécutions)` disparaît.

## 7. Comment déroger

Lire une exécution gelée reste possible, en connaissance de cause et avec un motif écrit :

```
cd services/llm-agents && .venv/bin/python -m experiences \
  --motif-archive "audit ticket 098, comparaison au substrat du 17 mars"
```

Le motif part en WARNING avec la mention que cette lecture *ne fonde aucune mesure comparable à
celles de la référence courante*, et se consigne dans le ticket qui la demande.
