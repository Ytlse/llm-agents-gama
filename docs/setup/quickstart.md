# Quickstart — Lancer la simulation

## Prérequis

- Docker + Docker Compose
- GAMA Platform installé sur l'hôte (hors Docker) — **uniquement pour le mode IHM** ; le mode offline utilise l'image Docker officielle `gamaplatform/gama`
- Données GTFS et graph OTP construits (voir [data-pipeline.md](data-pipeline.md))
- Population EQUASIM configurée (voir [population.md](population.md))
- Fichier `.env` avec les clés API (voir [llm-providers.md](llm-providers.md))

---

## Paquets Python du dépôt (hors Docker)

Depuis le 2026-09-07 (ticket 037), le code LLM vit dans trois paquets installables, à la racine :
`llm_gateway/` (gateway générique), `mobility_core/` (domaine EMC²), `mobility_llm/` (catégories LLM
de la mobilité). Le contrôleur, les scripts et les tests les importent ; en local il faut les
installer en editable dans le venv de `llm-agents` :

```bash
llm-agents/.venv/bin/python -m pip install -e ./mobility_core -e ./llm_gateway[test] -e ./mobility_llm
```

Puis `make test-all` (les trois suites + contrats d'architecture), `make lint`, `make typecheck`.
Les images Docker `api`/`worker` embarquent les trois paquets (`llm_gateway/Dockerfile`, contexte
racine) ; en développement, `docker-compose.yml` monte les sources par-dessus, avec `PYTHONPATH=/app` pour qu'elles précèdent les copies installées dans l'image (sans quoi `celery` et `uvicorn`, scripts console, servent le code figé à la construction).

## Ordre de démarrage (mode IHM)

```
1. docker compose up      ← démarre tous les services Docker
2. Ouvrir GAMA            ← fichier GAMA/CityTransport/City.gaml
3. Cliquer Play dans GAMA ← le controller se connecte via WebSocket ws://host.docker.internal:3001
```

Le service `eqasim` génère (ou charge depuis le cache) la population synthétique. Le controller attend sa disponibilité avant de s'initialiser.

---

## Mode offline — GAMA headless en conteneur

Tout démarre avec Docker, sans IHM GAMA ni intervention manuelle :

```shell
make run OFFLINE=1        # ou l'alias : make run-offline
```

(`make run --offline` n'est pas une syntaxe make valide — utiliser `OFFLINE=1`.)

Options combinables :

```shell
make run OFFLINE=1 NO_GOOGLE=1   # campagne sans les modèles Google (gemini/gemma) :
                                 # clés blanchies, instances google* hors rotation,
                                 # cascade sur mistral/groq/cerebras

make run OFFLINE=1 MEM=0         # coupe la mémoire des agents : LTM ET auto-réflexion
                                 # (MEM=1 pour les réactiver ; sans MEM, réglage inchangé).
                                 # Écrit dans GAMA/CityTransport/config/sim_params.yaml —
                                 # réglage PERSISTANT, il vaut aussi pour les runs IHM
                                 # suivants. L'injection de paramètres GAMA Server ne
                                 # fonctionne pas pour ces drapeaux : Settings.gaml
                                 # (load_sim_config) les écrase depuis ce fichier.

make stop-run                    # arrêt à chaud : stoppe GAMA et le launcher,
                                 # laisse le reste de la pile en place
make run OFFLINE=1 CONT=1        # reprise : réutilise le workdir du run précédent
                                 # (experiments/current) — journaux appendés,
                                 # state.json et checkpoints retrouvés, métriques
                                 # Grafana/Prometheus/Redis conservées
```

Sémantique de la reprise (`CONT=1`) : le contrôleur reprend **le même répertoire
d'expérience** ; la simulation GAMA, elle, repart à `t0` du jour simulé — GAMA ne
sait pas geler son état en plein trajet (ticket 002). Les caches (décisions LLM,
OTP, OSMnx) et `state.json` rendent ce rejeu quasi instantané et déterministe :
en pratique, la simulation « rattrape » le point d'interruption en quelques
minutes sans re-consommer de quota LLM.

Ce que fait le mode offline :

1. Démarre les services avec le profil compose `offline`, qui ajoute le service `gama` (image officielle `gamaplatform/gama:2025.06.4`, alignée sur la version validée des modèles) en mode **GAMA Server** (`-socket 6868`).
2. Le controller et l'api reçoivent `GAMA_WS_URL=ws://gama:3001` (au lieu de `ws://host.docker.internal:3001`).
3. Une fois les services prêts, le launcher `scripts/gama/launch_headless.py` (exécuté dans le conteneur controller) envoie `load` puis `play` au protocole GAMA Server, en injectant les paramètres `http_url`/`http_port` de l'expériment `e` pour que le modèle poste sur `http://controller:8002`.
4. La console GAMA est relayée dans `experiments/current/gama_headless.log`.

Points d'attention :

- Le launcher **garde sa connexion WebSocket ouverte pendant tout le run** : GAMA Server arrête les expériences dont le client se déconnecte. L'arrêt propre passe par `make down` (ou `docker compose --profile offline down`).
- À la pause de fin d'horizon (`simulation_max_days`), le controller **continue de drainer les réflexions STM en attente** (écritures LTM, utiles aux runs qui reprennent cette population). Si la LTM du run doit être réutilisée, attendre dans les logs controller le message `[drainage] Réflexions STM épuisées — LTM complète, arrêt sûr (make down)` avant d'arrêter les services.
- Les paramètres de scénario (population, jours simulés…) restent lus depuis `GAMA/CityTransport/config/sim_params.yaml`, comme en mode IHM.
- Sans display, l'observation passe par Grafana, vizpop (port 5050) et `make report`. Le protocole GAMA Server permet aussi d'évaluer des expressions GAML à chaud (port 6868 exposé sur l'hôte).

---

## Plateforme d'expériences (ticket 035)

Préparer une fois les propositions d'itinéraires d'une population, puis les rejouer sans le
simulateur ou avec GAMA. Tout passe par `python -m experiences` dans le conteneur `controller` ;
les cibles `make` encapsulent les appels. Design : `docs/arch/plateforme-experiences.md`.

```bash
make jeu POP=data/population/population_1000_AAMAS_v5 NOM=v5_j1   # tous modes, sans plafond (services requis)
make jeu-consulter NOM=v5_j1 PERSONNE=418                         # les déplacements d'une personne et leurs propositions
make jeu-verifier NOM=v5_j1                                       # péremption : dépendances changées depuis la préparation
make jeu-verifier-jours NOM=v5_j1 JOUR=2026-03-17 DECLARER=1     # les courses TC proposées existent-elles le mardi ? lu dans le GTFS, déclaré par déplacement
make experience-definir FICHIER=data/experiences/exp_durmin_nosim/experience.yaml   # refuse un `nom` qui ne dit pas ses paramètres
make experience-estimer EXP=exp_durmin_nosim                      # sollicitations, jetons, part des quotas — sources citées
make experience-lancer EXP=exp_durmin_nosim                       # sans simulateur ; REPRENDRE=1 pour reprendre
                                                                  # démarre d'abord ses services : REQUIS="controller api worker" (défaut `controller`), ATTENTE=600
make services-pretes REQUIS="controller api worker"               # les garantir sans rien lancer (docker compose up -d --wait, idempotent)
make experience-pause EXP=exp_durmin_nosim · make experience-arreter EXP=exp_durmin_nosim
make experiences-renommer                                         # les noms disent-ils leurs paramètres ? APPLIQUER=1 FUSIONNER=1 pour aligner
make registre TRIER=couverture FILTRER=decideur=gemini
make comparer A=<dossier exécution> B=<dossier exécution>         # refuse si les empreintes partagées diffèrent
make run OFFLINE=1 JEU=v5_j1                                      # GAMA consomme le jeu : aucun appel moteur en régime nominal
```

Modèle local (LM Studio sur l'hôte) : `make lmstudio-charger MODELE=<id>` puis les mêmes cibles
`experience-*` sur la définition `exp_<modèle>_minper_jtir_p2_t0_nosim` — voir
`docs/setup/llm-providers.md`, section « Modèles locaux — LM Studio ».

### Pas à pas : ma première expérience depuis le tableau de bord

Onglet **🧪 Expériences**. Un bloc au-dessus des boutons dit les services Docker que l'expérience
composée utilise et l'état de chacun ; un bouton démarre exactement ceux-là, sans la métrologie
(`make up` reste la voie pour toute la pile). Rien à éditer à la main sauf, une
fois, le texte d'un prompt. Les choix du formulaire sont retenus d'une session à l'autre.

1. **Composer.** Le bloc « Nouvelle expérience » est un formulaire : population (liste des
   dossiers scellés), jeu de déplacements (liste des jeux préparés, avec leur couverture), prompt
   système (les variantes de `prompts.yaml`, `b_min` est le minimaliste), décideur (modèle de la
   passerelle, heuristique, tirage, rejeu), mode (sans simulateur ou GAMA), jour, calendrier. Les
   graines, le regroupement et les tolérances horaires sont dans « Réglages avancés », déjà
   remplis. Le fichier qui sera écrit s'affiche en dessous.

   **Le nom ne se saisit pas** : il se calcule de ces paramètres et s'affiche en tête —
   `exp_gemini-31-fl_minper_jtir_t0_nosim` dit le modèle, le prompt, le calendrier, la
   température et le mode. Changer de modèle change donc le nom, et deux expériences ne peuvent
   plus se marcher dessus. Si ces paramètres sont **déjà** ceux d'une expérience enregistrée, la
   page le dit : lancer lui ajoutera une exécution. Grammaire complète et cas de collision :
   `specs/nommage-canonique-experiences.md`.
2. **Préparer le jeu** si la population n'en a pas encore : bouton « Warm-up : construire le jeu »
   (long, reprenable ; suivi dans **📟 Activités en cours**, et juste sous le formulaire). La barre
   d'avancement se rafraîchit seule ; quand le jeu est clos, la page le voit sans qu'on la
   recharge et il devient sélectionnable. Un bouton grisé dit toujours ce qui lui manque.
   Vous n'avez pas à attendre pour **enregistrer** l'expérience : elle nomme le jeu qu'elle
   attend, et devient lançable sans retouche dès qu'il est clos.
3. **Décrire son propre prompt** (facultatif) : le texte de la variante choisie s'affiche en
   entier ; « Éditer et enregistrer sous un autre nom » l'ajoute à `prompts.yaml` (jamais
   d'écrasure), puis « Recharger la passerelle ». `prompt_minimal` est le point de départ
   minimaliste : c'est le seul prompt de la **famille minimale** (tâche et format de sortie,
   rien qui puisse influencer un mode) — toutes les autres variantes sont **expertes**, où
   nommer et cadrer les modes est volontaire, seules les règles figées (« sous tel seuil,
   tel mode ») et les formules mathématiques restant proscrites. `minimal_persona` est
   **invalidée** depuis le 2026-09-10 : voir `specs/hygiene-prompts-et-plateforme-experiences.md`.
4. **Enregistrer** : écrit `data/experiences/<nom>/experience.yaml` sans rien lancer, puis le fait
   valider par la plateforme si le service `controller` tourne (tout champ manquant ou incohérent
   est nommé). Le message donne le chemin écrit et l'état du jeu attendu. Réenregistrer sous un nom
   qui porte déjà des exécutions demande une confirmation ; les exécutions archivées ne bougent pas.
   **Estimer le coût** : nombre de sollicitations, jetons, part du quota du jour, refus éventuels.
5. **Lancer.** Si une exécution tourne encore, une case cochée d'avance propose de l'arrêter
   d'abord et nomme ce qu'elle arrêtera : l'arrêt est coopératif (fichier `STOP`, honoré en
   quelques secondes, résultat partiel exploitable), la construction d'un jeu n'est jamais
   arrêtée, et le lancement est refusé si l'arrêt n'aboutit pas en trente secondes plutôt que de
   tourner en concurrence. Sans simulateur : l'exécution démarre, une barre d'avancement apparaît dans « Mes
   expériences » (déplacements décidés, personnes, temps restant, sollicitations, erreurs), avec
   **Pause** et **Arrêter**. **Pause** et **Arrêter** sont effectifs en quelques secondes : les
   sollicitations encore en vol sont abandonnées passé un délai de grâce (`EXP_PAUSE_GRACE_S`,
   15 s), leurs déplacements non archivés étant redemandés à la reprise. Et une exécution qui
   n'avance plus pendant 7 minutes (`EXP_INACTIVITE_PAUSE_S`) se met **en pause d'elle-même**,
   en `[ALARME]`, au lieu de rester « en cours » — elle reste reprenable. Avec GAMA : c'est `make run OFFLINE=1 JEU=<jeu>` qui est lancé, et
   GAMA utilise le prompt actif de la passerelle, pas la variante choisie (limite connue).
6. **Reprendre, rejouer, dupliquer.** Sous la table : « Reprendre » une exécution en pause ou
   épuisée (rien n'est redemandé), « Rejouer » (nouvelle exécution, l'ancienne reste intacte),
   « Dupliquer », ou choisir une expérience dans la liste « S'inspirer de » en tête du formulaire
   (ses réglages sont recopiés dès le choix, sans autre clic ; changez ce que vous voulez : c'est
   ainsi qu'on compare deux prompts ou deux modèles).
7. **Lire.** Détail d'une exécution : couverture, parts modales face à l'enquête, puis personne →
   déplacement → trace (options présentées, écartées et motifs, réponse brute).

`make run JEU=` écrit `data.jeu_enregistre` dans `llm-agents/config/config.yaml` et **recrée le
contrôleur** (les réglages sont lus au démarrage du processus). Les tolérances horaires par groupe
de modes doivent y être déclarées (bloc commenté à décommenter) : sans elles, le jeu est refusé.
Une exécution s'archive dans `data/experiences/<nom>/executions/<horodatage>/` (`decisions.jsonl`,
`moves.csv`, `synthese.html`) ; le tableau de bord (`make dashboard`, ou double-clic sur
`tableau-de-bord.command` à la racine, onglet « 🧪 Expériences ») liste le registre et descend
jusqu'à la décision unitaire.

## Commandes Docker

```shell
# Démarrage standard — configuration unique : llm-agents/config/config.yaml
# (pour changer de config, éditer directement ce fichier)
docker compose up

# Surcharger la taille de population
EQASIM_POPULATION_SIZE=5000 docker compose up

# Forcer la regénération de la population
EQASIM_FORCE_REGENERATE=true docker compose up

# Rebuild après un changement de code
docker compose up --build
```

---

## Ports exposés

| Service | Port | Description |
|---------|------|-------------|
| `controller` | 8002 | API FastAPI principale (Hypercorn HTTP/2) |
| `controller` | 5050 | Visualisation Folium (carte population) |
| `api` (LLM gateway) | 8000 | Passerelle LLM |
| `flower` | 5555 | UI de monitoring Celery |
| `eqasim` | 8003 | Service de génération de population |
| `otp1` | 8080 | OpenTripPlanner instance 1 |
| `otp2` | 8081 | OpenTripPlanner instance 2 |
| `otp3` | 8082 | OpenTripPlanner instance 3 |
| `osmnx1` | 8090 | Serveur de routage OSMnx |
| `redis` | 6379 | Redis (broker + état) |
| `prometheus` | 9090 | Métriques |
| `grafana` | 3000 | Dashboards |

---

## Scripts disponibles

### Analyse des résultats (`scripts/analysis/`)

| Script | Description |
|--------|-------------|
| `current_stats.ipynb` | Statistiques générales de la simulation en cours |
| `llm_traffic_analyse.ipynb` | Analyse du trafic généré par les agents LLM |
| `pipeline_delays.ipynb` | Analyse des délais du pipeline de planification |
| `run_analysis.py` | Script CLI pour lancer les analyses |

### Données GTFS (`scripts/data/gtfs/`)

| Script | Description |
|--------|-------------|
| `analyze_mobility_bbox.py` | Analyse la distribution spatiale des déplacements pour calibrer la bbox |
| `gtfs_analysis.ipynb` | Exploration et statistiques des données GTFS |
| `gtfs_merge.ipynb` | Fusion et vérification des flux GTFS Tisséo + TER |
| `gtfs_to_shapefile.py` | Export des arrêts et tracés GTFS en Shapefile / GeoJSON |

### Données population (`scripts/data/population/`)

| Script | Description |
|--------|-------------|
| `generate_population.ipynb` | Notebook de génération et inspection de la population EQUASIM |
| `statistics_population.ipynb` | Statistiques démographiques et de mobilité de la population |
| `travel_time.py` | Calcul des temps de trajet pour la population |
| `route_worker.py` | Worker de calcul d'itinéraires en batch |
| `cerema_values.yaml` | Valeurs de référence CEREMA EMC² 2023 pour calibration |
| `population_emc2_2023.yaml` | **Cadrage** de la population interrogée par l'enquête CEREMA — périmètre, âge minimum, poids de redressement, couronnes. Chargé et validé par `mobility_core.population_reference` ; toute valeur y est recoupée sur les microdonnées (cf. [périmètre de population](../arch/perimetre-population.md)) |
| `audit_perimetre.py` | `make audit-perimetre` — les neuf écarts de base entre population enquêtée et population simulée. Sortie 0 conforme / 2 à corriger / **3 axe non mesurable** |

### Infrastructure / debug (`scripts/infra/`)

| Script | Description |
|--------|-------------|
| `direct_trip.ipynb` | Test de calcul d'itinéraire direct (OTP / OSMnx) |
| `otp_shape.ipynb` | Visualisation des shapes OTP |
| `graph.ipynb` | Exploration du graphe de transport |
| `load_test_sync.ipynb` | Test de charge du controller |
| `live_chart.example.py` | Exemple de visualisation en temps réel |

---

## Résultats de simulation

Chaque run crée un répertoire horodaté sous `experiments/archive/<YYYY-MM-DD>_<HH_MM>/`. Le lien symbolique `experiments/current` pointe vers le dernier run.

Fichiers CSV exportés dans `gama_results/` :

| Fichier | Description |
|---------|-------------|
| `move_log.csv` | Décisions de mobilité (mode, raisons LLM, retards, météo) |
| `gama_arrivals.csv` | Dérive temporelle entre trajet théorique et temps mesuré |
