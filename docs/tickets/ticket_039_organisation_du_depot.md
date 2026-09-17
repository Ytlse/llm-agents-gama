# Ticket 039 — Organisation du dépôt : bibliothèques, services, données, résultats

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
>
> **Constat consigné le 2026-09-07**, **remesuré et exécuté le 2026-09-12** (pas 1, 2 et 3).

## Constat remesuré le 2026-09-12

| Répertoire | 2026-09-07 | 2026-09-12 | dont suivi par git | Nature |
|---|---|---|---|---|
| `services/eqasim-toulouse/` | 16 Go | 16 Go | **0 fichier** — entièrement ignoré | service + données de synthèse |
| `experiments/` | 10 Go | 7,9 Go | hors git | résultats de runs |
| `data/` | 6,5 Go | 5,1 Go | pointeurs DVC | entrées, caches, exports |
| `services/llm-agents/` | 4,1 Go | 4,1 Go | 179 fichiers | contrôleur + venv du projet |
| `scripts/` | 560 Mo | 567 Mo | **5,4 Mo** | outils ; le reste est du cache |
| `services/GAMA/` | 565 Mo | 565 Mo | 17 fichiers | modèle de simulation |
| `prompt_calibration/` | 457 Mo | 457 Mo | 0 — dépôt git imbriqué | dépôt autonome déployé sur VM |
| `services/otp-toulouse/` | 415 Mo | 415 Mo | 11 fichiers | service de routage transit |
| `docs/` | 196 Mo | **348 Mo** | `paper` 32 Mo ; `slides`, `synthesis`, `capture` : 0 | documentation + article |
| `packages/` | — | 41 Mo | les trois bibliothèques | ticket 037 |
| `infra/` | — | 288 Ko | compose, prometheus, grafana | orchestration |

**Deux corrections au constat du 07/09.** `gama/` et `GAMA/` n'étaient **pas** deux répertoires :
même inode, volume APFS insensible à la casse, une seule casse dans git et aucune référence en
minuscules dans le code. Et le poids de `scripts/` comme celui de `docs/slides` et
`docs/synthesis` **était déjà hors de git** : c'est de l'encombrement disque, pas du poids de
dépôt.

## Principes (inchangés)

1. **Quatre natures, quatre places** : ce qui se versionne et se publie, ce qui se déploie, ce
   qui entre, ce qui sort. Un fichier ne doit jamais hésiter entre deux.
2. **Tout ce qu'une exécution produit vit hors de git**, avec un index lisible et une règle de
   rétention.
3. **Un point d'entrée par composant**, et le `Makefile` racine délègue au lieu de tout porter.
4. **La documentation du projet reste dans `docs/`**, chaque bibliothèque porte la sienne.
5. **Pas de dépôt git imbriqué** : `prompt_calibration` se consomme comme une dépendance
   versionnée, ou devient un sous-module déclaré.

## Cible atteinte le 2026-09-12

```
packages/     llm_gateway · mobility_core · mobility_llm
services/     llm-agents · GAMA · eqasim-toulouse · otp-toulouse
infra/        docker-compose.yml · prometheus.yml · grafana/
data/  experiments/  docs/  notebooks/  scripts/  specs/  tests/   (inchangés, à la racine)
```

## Ce que la migration a appris

**Le compose déplacé exige `--project-directory`.** Sans lui, compose réancre tous les chemins
relatifs sur son propre dossier et échoue dès `.env`. `COMPOSE_FILE` et
`COMPOSE_PROJECT_DIRECTORY` ne suffisent pas — mesuré, pas supposé. Le `Makefile` porte les deux
drapeaux dans `$(COMPOSE)`.

**Les chemins qui comptent des crans sont le vrai coût d'un déplacement**, pas les chemins
écrits en clair. Ce dépôt en portait beaucoup parce que les mêmes fichiers doivent se résoudre
sur l'hôte ET dans un conteneur qui monte le code ailleurs : `parents[2]` valait la racine d'un
côté et `/` de l'autre. La méthode qui tient est l'ancre (`experiences/chemins.py` la
documentait déjà) — chercher un repère plutôt que compter. Trois formes à balayer, pas une :
`parents[N]`, `.parent.parent`, et les chaînes `"../../"` que les deux premières ne montrent pas.

**Deux angles morts de vérification.** `git grep` ne voit que le suivi : sept fichiers non
commités gardaient l'ancien chemin, et c'est une `[ALARME]` d'exécution qui les a dénoncés. Et
un chemin cassé peut se déguiser en donnée absente : 25 tests météo passaient de « réussis » à
**« ignorés »** sans qu'aucun échoue.

**Un `.gitignore` n'agit que sur ce qui n'est pas encore suivi.** Les 42 fichiers de
`docs/traces` étaient couverts par une règle depuis le 2026-09-02 et restaient versionnés. Et
déplacer un répertoire périme les règles qui le nomment : `zf_couronne.json`, déversionné pour
raison de licence au ticket 038, se serait reversionné en silence.

## Pas 4, 5 et 6 — exécutés le 2026-09-15

### Pas 4 — le `Makefile` délègue (principe 3)

1 419 lignes ramenées à **109**. Les 120 cibles vivent dans sept modules de `make/`, une
section par fichier — `docker.mk` (27), `choix-modal.mk` (37), `experiences.mk` (30),
`synthese.mk` (13), `tests.mk` (8), `gama.mk` (3), `pilotage.mk` (2). Aucune recette n'a
changé : le fichier racine ne garde que la configuration, puis `include make/*.mk`.

**Trois pièges, qui étaient le vrai contenu du pas.**

`PROJECT_ROOT` se calculait par `$(lastword $(MAKEFILE_LIST))` — juste tant qu'aucun
`include` ne le précède, faux dès qu'un `include` bouge d'une ligne, et toute la résolution
de chemins du dépôt bascule avec lui, **en silence**. Passé à `$(firstword …)`, vrai quel
que soit l'ordre. Même famille que les `parents[N]` du pas 3 : compter des crans, c'est
parier sur une disposition.

`make help` lisait `$(firstword $(MAKEFILE_LIST))` : après découpage il n'aurait plus listé
que les cibles du fichier racine — c'est-à-dire aucune. Passé à `$(MAKEFILE_LIST)`.

Le tableau de bord lisait le Makefile **comme un fichier**
(`scripts/dashboard/makefiles.py`). Sans suivi des `include`, ses 120 cibles cliquables
tombaient à zéro — sans exception ni test rouge, juste des boutons absents. C'est le piège
que le pas 3 avait déjà rencontré sous une autre forme (25 tests météo passés de
« réussis » à « ignorés »). `parse_makefile` développe désormais les `include`, chaque cible
porte le module qui la définit, et `test_makefiles_includes.py` garde le point.

`.DEFAULT_GOAL := up` est posé explicitement : sans lui, la cible par défaut devenait la
première cible du premier `.mk` lu, donc l'ordre alphabétique des fichiers décidait de ce
que fait un `make` nu.

**Vérifié :** `make help` rend les mêmes 104 lignes au mot près (l'ordre seul change,
les modules étant lus alphabétiquement) ; la base de règles de `make -pn` est identique —
mêmes 195 cibles, mêmes 104 `.PHONY`, mêmes recettes, seule la provenance (fichier, ligne)
bouge ; aucun avertissement « overriding recipe » ; le tableau de bord retrouve ses 120
cibles avec la même documentation.

### Pas 5 — `prompt_calibration` devient un sous-module

Le ticket posait « dépendance ou sous-module ». La mesure a tranché : le parent **importe le
code** du dépôt imbriqué. `scripts/synthesis/sources.py` le dit en toutes lettres — on
l'ajoute au `sys.path` *« plutôt que de dupliquer la loss : un score affiché ici doit être
exactement celui du moteur »* — et son message d'erreur demande à l'humain de cloner le
dépôt à cet emplacement. La dépendance packagée ne collait pas : c'est une application
déployée sur VM, pas une bibliothèque.

Ce que le statu quo coûtait touchait à la science du projet : `model_compare.py` inscrit
`prompt_calibration/calibration/metrics.py` au manifeste des sources d'une page de score,
**sans qu'aucun commit ne soit enregistré**. Un score republié six mois plus tard n'était
pas rattachable à la loss qui l'a produit. Le sous-module épingle ce commit dans le parent.

Exclusion retirée du `.gitignore`, `.gitmodules` déclaré, commit `8be8f26` épinglé. Le
dépôt imbriqué n'a pas bougé (même HEAD, même branche, mêmes modifications en attente) et
les quatre couplages tiennent : import du moteur, lecture de son Makefile par le tableau de
bord (25 cibles), `make -C prompt_calibration pull-db`, montage compose.

**À trancher par l'auteur :** l'épingle porte sur `8be8f26` (branche
`feat/diag-plan-arbitre`), l'état présent sur le disque. `origin/main` est en avance à
`f8d55d8`, qui contient la fusion de cette branche. Déplacer l'épingle, une fois le choix
fait : `git -C prompt_calibration checkout main && git add prompt_calibration`.

### Pas 6 — `docs/paper` : pas de migration, une règle

Le ticket supposait un problème de poids. La mesure dit le contraire : chacun des binaires
suivis sous `docs/paper/` a exactement **une** version dans l'historique (`figures/` en deux
commits, `sources/` en trois). 34 Mo écrits une fois coûtent 34 Mo dans le pack — le régime
que git gère le mieux. LFS ajouterait une dépendance à chaque clone et un quota, pour ne
rien économiser.

Le vrai risque est ailleurs, et il est amorcé : `plot_experiences.py` et `plot_familles.py`
écrivent **par défaut** dans `docs/paper/figures/`, qui est versionné (les quatre
`familles_composite_l1_*` datent du 14/09, les deux `comparaison_experiences_*` du 09/09).
Chaque régénération commitée ajoute un blob de plus. La règle — une figure ne se committe
que citée par un chapitre gelé, sinon `--sortie docs/synthesis/<nom>` — est écrite dans
`docs/paper/README.md`, et les deux générateurs avertissent en chiffrant le poids quand ils
écrasent un fichier suivi par git.

L'article n'a pas été touché : seuls `.gitignore`, `docs/paper/README.md` et les deux
générateurs ont changé.

## Ce qui reste

- **`Divers/`** attend un tri manuel de l'auteur.
- **`llm_module/`** reste à la racine, délibérément : coquille de compatibilité sans
  `pyproject.toml`, sans `src/`, sans tests, que plus rien n'importe dans le dépôt. La ranger
  dans `packages/` la promouvrait au rang qu'elle est censée quitter. Son retrait appartient
  au ticket 037 (version 2.0).
- **L'épingle du sous-module** est à confirmer (voir pas 5).

## Ce que la suite de tests a appris

Le chiffre « 2 échecs préexistants » du pas 3 avait trois jours et n'était plus vrai. Surtout,
**le périmètre du run change le résultat** : `test_dashboard_app.py` seul rend 2 échecs sur 53,
le même fichier dans la suite entière en rend 40 — une pollution entre modules de test, pas une
régression. Comparer un run de fichier à un run de suite a failli faire accuser le découpage.
En isolation, 12 échecs subsistent (météo, fenêtre GTFS, onglet « Campagne » ajouté sans sa
table de slugs, statuts de tickets), tous étrangers aux fichiers de ce ticket.
