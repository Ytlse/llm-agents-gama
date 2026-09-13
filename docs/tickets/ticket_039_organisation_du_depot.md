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

## Ce qui reste

- **`Makefile` : 1 346 lignes.** Le principe 3 demande qu'il délègue ; il porte encore tout.
- **`prompt_calibration`** : toujours un dépôt git imbriqué, 0 fichier suivi par le parent. Le
  choix dépendance / sous-module n'est pas tranché.
- **`docs/paper` (32 Mo suivis)** et les pages de synthèse archivées : le sort (LFS ou dépôt de
  publication) n'est pas tranché. L'article est verrouillé : il n'a pas été touché.
- **`llm_module/`** reste à la racine, délibérément : coquille de compatibilité sans
  `pyproject.toml`, sans `src/`, sans tests, que plus rien n'importe dans le dépôt. La ranger
  dans `packages/` la promouvrait au rang qu'elle est censée quitter. Son retrait appartient au
  ticket 037 (version 2.0).
- **`Divers/`** attend un tri manuel de l'auteur.
