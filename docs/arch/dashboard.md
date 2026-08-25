# Tableau de bord de pilotage

`make dashboard` ouvre une application Streamlit qui rassemble en un seul écran ce
qu'il fallait jusqu'ici aller chercher dans trois terminaux et quatre fichiers :
l'état courant du projet (services, run, providers), les cibles `make` des
sous-projets, l'état des tickets et les métriques du dépôt.

```bash
make dashboard                      # http://localhost:8503
make dashboard DASHBOARD_PORT=8600  # autre port
make dashboard DASHBOARD_THEME=dark # thème sombre
```

L'application tourne avec l'interpréteur `llm-agents/.venv/bin/python`
(surchargeable via `DASHBOARD_PYTHON`) : c'est le seul du dépôt qui porte
Streamlit, pandas et Altair.

---

## 0 · Volets « Vue d'ensemble », « Run GAMA » et « Providers »

### Vue d'ensemble

Six tuiles rafraîchies toutes les 10 secondes répondent à « est-ce que ça tourne
bien, là, maintenant ? » : services Docker, run GAMA (actif/inactif + heartbeat),
providers LLM (disponibles / cooldown / quota jour), calibration (meilleurs scores
et fraîcheur du store cloud rapatrié), git (branche, fichiers modifiés) et jobs en
cours. L'horodatage de lecture est affiché en pied de page.

### Run GAMA

Le volet se concentre sur le run pointé par `experiments/current` :

- **Bandeau d'état** (rafraîchi toutes les 5 s) : run actif ou non (mêmes gardes
  `pgrep` que `make run`), heartbeat (mtime de `app.log`), cycle courant, agents
  actifs, backlog pipeline. Les gauges viennent du controller
  (`GET :8002/metrics`) quand il tourne, de `gama_results/agent_states.csv` sinon.
- **Progression des agents** : courbe inactifs/prêts/actifs par cycle
  (`agent_states.csv`, une ligne par `/sync`), doublée d'une vue tableau.
- **Santé des logs** : compteurs ERROR / WARNING / `[ALARME]` et **top des
  messages d'erreur** normalisés (nombres → N), pour savoir *ce qui* casse sans
  retourner au terminal.
- **Pipeline LLM** : hit rate du cache sémantique (`llm_cache_hits.jsonl` vs
  `llm_exchanges.jsonl`, même calcul que `make report`), erreurs LLM et 429.
- **Actions** : `make run-offline` (choix du `CONFIG`, confirmation obligatoire —
  la cible purge Grafana/Prometheus et les compteurs Redis), `make stop-run`
  (arrête le run sans toucher au reste de la pile), `make down`, et la génération
  du rapport `make report` affichée en Markdown dans la page.

### Providers

L'état vu par le load balancer (`GET :8000/health`) : par provider, RPM courant /
limite, requêtes et tokens du jour face aux quotas RPD/TPD, cooldown, quota
épuisé. Si l'API est arrêtée, repli sur les quotas déclarés dans
`llm_module/config/providers.yaml` (dont le mtime date le dernier
rafraîchissement). Deux boutons pilotent `make providers` : le bilan à blanc
(`DRY_RUN=1`) et le rafraîchissement réel, gardé par une confirmation puisqu'il
réécrit `providers.yaml`. Les 429 du run courant sont listés par provider.

### Calibration

L'onglet 🧬 Calibration regroupe tout le pilotage des campagnes de prompt.

En tête, la section **Campagne génétique** détaille l'état lu dans la branche
spéciale `__ga__` du store cloud rapatrié : génération, étape courante du cycle
(`populate → eval → cut → confirm → ablate → validate → report → breed`),
population évaluée (n individus avec un score `rank` — **le score de sélection**,
celui sur lequel la coupe se décide ; `screen` ne sert qu'à confirmer le
champion, `val` à l'early stopping), champion, et le tableau de la population :
profil (élite / axe semé), opérateur d'origine (`ga_init`, `ga_cross`,
`ga_mutate`…), génération d'apparition, date de création, scores rank/screen/val,
nombre d'évals. L'historique `champion_by_gen` s'affiche dès qu'une génération
est bouclée. Les rapports HTML par génération (`gen_NN.html`, écrits par l'étape
`report` **sur la VM**, jamais inclus dans `pull-db`) se rapatrient avec la
nouvelle cible `make pull-reports` et s'ouvrent depuis la page. Un expander
rappelle la configuration des rapports par mail (`notify_mail_to` dans
`config/ga_cloud.yaml` + `SMTP_USER`/`SMTP_APP_PASSWORD` dans `~/calib.env` sur
la VM).

Le reste de l'onglet :

- **Stores** `local` et `cloud` : meilleur score, itération, nœuds/évals/
  mutations, branches — plus l'état de la **campagne génétique** (branche
  spéciale `__ga__` du `run_state` : génération, étape du cycle, champion) et la
  **veille quota** (table `cooldown`) quand elle est active. Le store `cloud`
  étant une copie rapatriée, sa date de rapatriement est affichée en
  avertissement : l'état réel de la VM se lit à la demande.
- **Daemon local** : l'instantané `progress.json` (branche, étape, évals payées,
  hits cache) avec l'heuristique de vivacité (plus de 15 min sans écriture →
  « arrêté »).
- **Campagne cloud** : trois boutons de consultation exécutés en direct dans la
  page (`cloud-progress`, `cloud-status`, `cloud-logs`) — chaque clic est un
  `gcloud compute ssh`, rien n'est interrogé automatiquement. Le sélecteur
  `CLOUD_CONFIG` vise `config/ga_cloud.yaml` (campagne GA courante) par défaut,
  et `UNIT` choisit le daemon suivi par les logs (`calib-ga` / `calib`). Les
  actions `pull-db` (rapatriement du store **sans** ouvrir d'UI — nouvelle cible
  du Makefile de `prompt_calibration`), `pause` (avec confirmation) et `start`
  passent par le registre de jobs. Le bouton `pull-db` du dashboard passe
  explicitement `LOCAL_DB=calibration_results/calibration_cloud.db` : il met à
  jour la copie « cloud » lue par l'onglet et ne touche jamais au store local
  (le défaut du Makefile, lui, écrase `calibration.db` — convention historique
  de `pull-cloud`).

### Commandes contextuelles

Le volet ▶ Commandes reste le catalogue exhaustif, mais chaque bloc de métriques
porte désormais ses actions : services Docker → `up`/`restart`/`down`, synthèse
→ `synthesis`/`synthesis-open`, run → lancement/arrêt/rapport dans 🎮 Run GAMA,
providers → `make providers` dans 🤖 Providers, calibration → cloud dans
🧬 Calibration. Tous ces boutons empruntent le même chemin que ▶ Commandes
(helper `make_action` → registre de jobs → 📟 Lancements), à l'exception des
consultations courtes (SSH, statut) exécutées en direct avec la sortie affichée
dans la page (`run_make_inline`).

### Sondes réseau

`metrics.py` reste strictement hors réseau. Les trois sondes qui interrogent un
service vivant — `GET :8000/health`, `GET :8002/metrics`, `pgrep` — sont isolées
dans [`scripts/dashboard/live.py`](../../scripts/dashboard/live.py), avec des
timeouts de 2 s et un repli silencieux : un service arrêté est un état normal,
pas une erreur. Les consultations SSH de la VM de calibration, elles, ne partent
que sur clic d'un bouton.

## 1 · Volet « Commandes »

Les Makefile de la racine, de `prompt_calibration/` et d'`otp-toulouse/` sont lus
au vol : chaque cible apparaît avec sa documentation, c'est-à-dire le bloc de
commentaires `##` qui la précède dans le Makefile. **Documenter une cible avec
`##` suffit donc à la documenter dans le dashboard.**

Chaque cible expose un bouton « ▶ Lancer » et un tiroir « Options et commande »
qui contient les variables `make` pertinentes (`CONFIG`, `RUN`, `ESSAI`,
`DRY_RUN`…), un champ libre pour toute autre variable, et la ligne de commande
équivalente prête à copier.

### Drapeaux

| Drapeau | Sens |
|---------|------|
| ⏳ | la cible ne rend pas la main (suivi de logs, serveur, run GAMA) — arrêtez-la avec « Stop » |
| ⌨️ | la cible pose une question au clavier : **le bouton est désactivé**, copiez la commande dans un terminal |
| 🔥 | destructive : une case de confirmation garde le bouton |
| 💸 | consomme du quota LLM : chiffrez d'abord avec `DRY_RUN=1` |
| 🪟 | ouvre une fenêtre ou un onglet externe |

Ces drapeaux ne sont pas déduits du Makefile : ils sont déclarés dans le
dictionnaire `_META` de [`scripts/dashboard/makefiles.py`](../../scripts/dashboard/makefiles.py),
en même temps que le groupe d'affichage et la liste des variables proposées.
**Une cible ajoutée à un Makefile apparaît automatiquement** — dans le groupe
« Autres », sans drapeau ni variable, jusqu'à ce qu'on l'y déclare.

## 2 · Volet « Lancements »

Chaque lancement est un sous-processus détaché (`start_new_session`) dont la
sortie complète est écrite dans `experiments/.dashboard/<n>-<cible>.log`
(dossier ignoré par git). Le volet affiche l'état, la durée, le code retour et
les 400 dernières lignes de sortie, rafraîchis toutes les deux secondes sans
recharger la page.

« Stop » envoie un `SIGTERM` au **groupe de processus** — donc aussi aux enfants
(`docker compose`, `python -m …`) — puis un `SIGKILL` après cinq secondes de
grâce. « Tout arrêter », dans la barre latérale, fait de même sur tous les jobs
en cours.

Les jobs vivent dans le processus du serveur Streamlit : fermer l'onglet ne les
tue pas, arrêter `make dashboard` les tue.

## 3 · Volet « Tickets »

Le statut d'un ticket est porté par
[`scripts/dashboard/tickets_status.yaml`](../../scripts/dashboard/tickets_status.yaml),
**seule source de vérité**, et par rien d'autre — surtout pas par un `**Statut**`
recopié dans l'en-tête de chaque `.md`, qui se périme en silence et qu'il faudrait
tenir à jour quinze fois.

```yaml
tickets:
  ticket_011_arrivees_perdues_gama:
    status: à faire
    note: la cause amont n'est pas comprise, l'accusé de réception n'est pas écrit
```

Statuts admis — `à faire`, `en cours`, `terminé`, `bloqué`, `en veille`, `abandonné`.
Le vocabulaire est **fermé** : `tickets.py` indexe l'icône par le statut, une valeur
hors liste lève une `KeyError` à l'affichage plutôt que de passer inaperçue.

Deux distinctions qui portent du sens, et qu'il ne faut pas fondre :

- **`en veille` ≠ `bloqué`.** *En veille* est une décision de ne pas avancer
  maintenant, le travail reprendra tel quel ; *bloqué* dit qu'une dépendance
  extérieure manque. Les confondre ferait chercher un déblocage qui n'existe pas.
- **`abandonné` ne veut pas dire « code retiré ».** Le ticket 010 est abandonné comme
  chantier alors que ses actions A1–A4 tournent en production : c'est le volet de
  validation qui est abandonné, pas la livraison. La note dit lequel des deux.

⚠ **Clé = nom de fichier complet.** Les formes courtes (`ticket_005`, `005`) sont
acceptées par `tickets.py`, mais deux tickets distincts partagent le numéro 005
(choix modal probabiliste / politique PROGEDO) et deux autres le 014 (anticipation /
annexe) : une clé courte appliquerait un seul statut aux deux.

À défaut d'entrée, le dashboard **déduit** un statut — repli, pas régime nominal :

1. les cases à cocher : aucune cochée → *à faire*, toutes cochées → *terminé*,
   sinon *en cours* ;
2. à défaut, la ligne `**État**` / `**État d'avancement**`, par repérage de
   tournures (« aucune correction engagée », « livrée », « bloqué »…) ;
3. sinon *sans statut*.

La colonne « Source » dit lequel a parlé. Pourquoi ce repli ne suffit pas : au
2026-08-20 il donnait « à faire, 0/15 » pour le ticket 008 dont les actions A1–A7
sont livrées, et *sans statut* pour 9 tickets sur 15. La raison est structurelle —
quand les cases d'un ticket sont ses **critères d'acceptation** (006, 007, 008), elles
restent vides jusqu'au run de validation, ce qui ne dit rien de l'avancement du
travail. Une ligne « Source : cases » est donc à lire comme une entrée manquante dans
la conf.

## 4 · Volet « Métriques »

| Bloc | Source | Contenu |
|------|--------|---------|
| Services Docker | `docker compose ps` | conteneurs actifs, état et santé de chacun |
| Santé du run | `experiments/**/app.log` | erreurs, warnings, `[ALARME]`, taille et bornes temporelles du log |
| Trajets du run | `experiments/**/moves.csv` | trajets, agents, heures simulées, part décidée par le LLM, retard de planification p95, partage modal, méthode de sélection |
| Synthèse des scores | `docs/synthesis/data.json` | écart au référentiel Cerema par bras et par dimension (produit par `make synthesis`) |

La calibration a quitté ce volet pour l'onglet 🧬 Calibration (voir § 0).

Le run analysé est choisi dans une liste, le run en cours en tête. Comme
`experiments/current` est un **lien symbolique** vers l'archive du run courant,
la liste dédoublonne sur le chemin résolu : le run apparaît une seule fois, sous
son nom d'archive suivi de « (en cours) ». Le dépouillement d'un `app.log` est
mis en cache sur son couple (taille, date de modification) : un log qui grossit
est relu, un log figé ne l'est qu'une fois.

### Couleurs

Le partage modal reprend la palette officielle du projet (voir
`.claude/CLAUDE.md`) : voiture rouge, vélo violet, transports collectifs vert,
marche cyan, deux-roues motorisé magenta. Cette palette **n'est pas séparable en
vision daltonienne** (rouge/vert, cyan/magenta) et ce n'est pas corrigeable sans
rompre la cohérence avec GAMA, Grafana et les notebooks. La couleur ne porte donc
jamais l'identité : chaque barre est nommée sur l'axe, sa valeur est écrite en
bout de barre, et une vue tableau double le graphe.

Les deux jeux de pas (clair et sombre) sont validés séparément en luminosité,
chroma et contraste sur leur surface. C'est pourquoi `make dashboard` **impose**
un thème (`DASHBOARD_THEME`, `light` par défaut) : si le thème de l'application
et celui du navigateur divergent, les libellés d'axe se retrouvent en blanc sur
fond clair.

---

## Structure du code

| Fichier | Rôle |
|---------|------|
| `scripts/dashboard/app.py` | l'interface : onglets, graphes, mise en page |
| `scripts/dashboard/makefiles.py` | lecture des Makefile, métadonnées et variables des cibles |
| `scripts/dashboard/runner.py` | lancement, suivi et arrêt des sous-processus |
| `scripts/dashboard/tickets.py` | lecture et statut des tickets |
| `scripts/dashboard/metrics.py` | Docker, runs, providers.yaml, erreurs LLM, synthèse, calibration, git — jamais de réseau |
| `scripts/dashboard/live.py` | les seules sondes réseau : `/health` API, `/metrics` controller, `pgrep` |
| `scripts/dashboard/palette.py` | couleurs de mode et d'état |

## Voir aussi

- [docs/arch/score-synthesis.md](score-synthesis.md) — la page de synthèse dont le dashboard lit les scores
- [docs/arch/prompt_calibration.md](prompt_calibration.md) — les campagnes dont il lit l'avancement
- [docs/arch/monitoring.md](monitoring.md) — Prometheus et Grafana, pour les métriques temps réel d'un run en cours
