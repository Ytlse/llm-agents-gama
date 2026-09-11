# Tableau de bord de pilotage

`make dashboard` ouvre une application Streamlit qui rassemble en un seul écran ce
qu'il fallait jusqu'ici aller chercher dans trois terminaux et quatre fichiers :
l'état courant du projet (services, run, providers, expériences), ce qui tourne,
l'état des tickets — modifiable sur place — et les métriques du dépôt.

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

Sept tuiles rafraîchies toutes les 10 secondes répondent à « est-ce que ça tourne
bien, là, maintenant ? » : services Docker, run GAMA (actif/inactif + heartbeat),
providers LLM (disponibles / cooldown / quota jour), calibration (meilleurs scores
et fraîcheur du store cloud rapatrié), git (branche, fichiers modifiés), jobs en
cours, et — sur toute la largeur — les **expériences en cours** : chaque exécution
et chaque jeu de déplacements en préparation, avec sa barre d'avancement. Sans rien
en cours, la tuile compte les expériences définies et les exécutions terminées.
L'horodatage de lecture est affiché en pied de page.

Ce que montre cette dernière tuile est lu **sur le disque** (`etat.json`,
`progression.json`, `MANIFEST.yaml`), pas dans le registre de jobs : une exécution
lancée depuis un terminal, ou survivante d'un redémarrage du tableau de bord,
y figure aussi. Ces fichiers sont écrits par le conteneur pendant qu'on les lit :
un champ manquant s'affiche « ? », un pourcentage aberrant est ramené dans [0, 100],
et un fichier tronqué ne casse pas la page.

Chaque ligne écrit son avancement en chiffres — « 120 / 400 déplacements · 30 % » —
et non seulement en longueur de barre : une colonne étroite ou un lecteur d'écran ne
donnerait sinon aucun chiffre. Chaque ligne porte aussi l'âge de sa progression, et
au-delà de dix minutes sans écriture elle le signale (« ⚠ plus rien d'écrit depuis
15 min ») — deux minutes pour un jeu, dont la progression s'écrit toutes les cinq
secondes. Ce n'est pas un diagnostic
de gel : une pénurie de quota peut légitimement faire attendre. Mais l'arrêt d'une
exécution est **coopératif** (fichiers `PAUSE` / `STOP`), donc une exécution dont le
conteneur a été tué garde `en_cours` dans son `etat.json` — sans ce repère, sa
dernière barre resterait affichée indéfiniment.

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

L'état vu par le load balancer (`GET :8000/health`) : par instance, RPM courant /
limite, requêtes et tokens du jour face aux quotas RPD/TPD, cooldown, quota
épuisé. La colonne **Provider** affiche le fournisseur réel (l'`adapter` :
`google`, `groq`, `mistral`…), pas la clé d'instance de `providers.yaml` — deux
seaux de quota d'un même fournisseur servant le même modèle apparaissent donc
sous le même libellé, disambiguïsés par leurs compteurs de quota. Si l'API est arrêtée, repli sur les quotas déclarés dans
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

### Les actions vivent là où elles ont un sens

Il n'y a plus de catalogue de cibles `make` : chaque bloc de métriques porte ses
actions. Services Docker → `up`/`restart`/`down`, synthèse →
`synthesis`/`synthesis-open`, run → lancement/arrêt/rapport dans 🎮 Run GAMA,
providers → `make providers` dans 🤖 Providers, calibration → cloud dans
🧬 Calibration, expériences → préparation du jeu et lancement dans 🧪 Expériences.
Tous ces boutons passent par le même chemin (helper `make_action` → registre de
jobs → 📟 Activités en cours), à l'exception des consultations courtes (SSH,
statut) exécutées en direct avec la sortie affichée dans la page
(`run_make_inline`).

Les Makefile restent lus par `makefiles.py` — c'est lui qui résout la cible et ses
variables derrière chaque bouton. Ce qui a disparu, c'est son **affichage** en
catalogue : une liste de 79 cibles que personne ne parcourait, doublée par des
boutons mieux placés. Une cible qui n'a de bouton nulle part se lance dans un
terminal, et `make help` en donne la liste documentée — l'onglet était le seul
endroit qui les montrait toutes, le supprimer sans rien mettre à la place aurait
rendu ce catalogue invisible.

### Sondes réseau

`metrics.py` reste strictement hors réseau. Les trois sondes qui interrogent un
service vivant — `GET :8000/health`, `GET :8002/metrics`, `pgrep` — sont isolées
dans [`scripts/dashboard/live.py`](../../scripts/dashboard/live.py), avec des
timeouts de 2 s et un repli silencieux : un service arrêté est un état normal,
pas une erreur. Les consultations SSH de la VM de calibration, elles, ne partent
que sur clic d'un bouton.

## 0 bis · Filtres d'hygiène : ne proposer que ce sur quoi on peut s'appuyer

Trois retraits, un même principe — **compter ce qu'on retire**. Une ligne qui disparaît sans
motif se lit comme une perte de données, alors que tout reste intact sur le disque.

| Où | Ce qui sort | Comment c'est rendu |
|---|---|---|
| « Mes expériences » | expériences `archivee` ou `invalide` (`masquee(ligne)`) | dépli `🗄 N expérience(s) hors tableau`, avec le motif de chacune et le rappel de `make registre TOUT=1` |
| Sélecteur « Prompt système » | variantes invalidées, jugées `non_conforme`, ou dont l'avis d'audit est périmé (`variantes_prompt()`) | `variantes_prompt_ecartees()` → variante et raison |
| Sélecteur « Modèle » | modèles qu'un lancement refuserait (`modeles_inaptes()`) | dépli `🚫 N modèle(s) écarté(s)` avec le verrou nommé |

**Le sélecteur de prompts reproduit le critère du moteur au lieu de l'importer** — le tableau
de bord lit `prompts.yaml` sans monter `PromptManager`. Cette duplication n'est tenable que
verrouillée : `scripts/tests/test_dashboard_filtres_hygiene.py::test_parite_avec_le_refus_de_la_passerelle`
exige l'égalité exacte entre ce que l'IHM écarte et ce que le moteur refuse de servir. Sans ce
test, le formulaire proposerait un prompt que le lancement refuserait ensuite.

**Le filtre des modèles s'appuie sur `experiences/aptitude.py`**, le module qui fait déjà
refuser `experience-estimer` et `experience-lancer` : même critère au formulaire et au
lancement. Il est chargé **par le chemin du fichier**, pas par `from experiences import
aptitude` — ce module-ci s'appelle lui aussi `experiences` et l'import résolvait sur lui-même,
échec qu'un `except` avalait en laissant le filtre inerte. Un test le vérifie explicitement.

Aucun filtre n'est bloquant par construction : si le module d'aptitude n'est pas chargeable,
aucun modèle n'est écarté — mieux vaut un choix trop large qu'un formulaire vide.

## 1 · Drapeaux des cibles `make`

Chaque cible lancée depuis un bouton porte des drapeaux, déclarés dans le
dictionnaire `_META` de [`scripts/dashboard/makefiles.py`](../../scripts/dashboard/makefiles.py)
en même temps que son groupe d'affichage et la liste de ses variables :

| Drapeau | Sens |
|---------|------|
| ⏳ | la cible ne rend pas la main (suivi de logs, serveur, run GAMA) — arrêtez-la avec « Stop » |
| ⌨️ | la cible pose une question au clavier : elle ne peut pas être lancée depuis la page |
| 🔥 | destructive : une case de confirmation garde le bouton |
| 💸 | consomme du quota LLM : chiffrez d'abord avec `DRY_RUN=1` |
| 🪟 | ouvre une fenêtre ou un onglet externe |

La documentation d'une cible reste le bloc de commentaires `##` qui la précède
dans son Makefile ; elle sert d'aide au survol des boutons.

## 2 · Volet « Activités en cours »

Un bouton y lance la **sonde des conteneurs** (`make watch-containers`), à mettre en marche
avant un run long. Elle existe pour une raison précise : le 2026-09-07, trois runs ont été
perdus sur un conteneur `controller` tué avec le code 137, sans une ligne dans ses journaux et
sans OOM signalé par Docker. Impossible de dire après coup combien de mémoire il consommait ni
ce qu'il avait dit avant de tomber.

La sonde relève la mémoire de chaque conteneur à intervalle fixe dans `memoire.csv`, et quand
un conteneur disparaît elle écrit `chute-<service>.txt` avec son état d'inspection — statut,
code de sortie, OOMKilled, nombre de redémarrages — et ses deux cents dernières lignes de
journal.

Elle écoute aussi `docker events` dans un fil séparé et, dès qu'un arrêt est demandé sur un
conteneur du projet, **photographie les processus de l'hôte** dans `appelant-<...>.txt` : pid,
parent, heure de démarrage et ligne de commande. C'est la seule façon de nommer le coupable,
Docker journalisant l'appel (`ContainerStopComposeLinux`) mais pas qui l'a passé, et un
`docker compose stop` ne vivant qu'une seconde ou deux.

Cette campagne écrit ses fichiers dans `experiments/.dashboard/conteneurs/<horodatage>/`
(ignoré par git), lève une alarme sur **front montant** au-dessus de 85 % de la limite d'un
conteneur, ne modifie aucun conteneur, et un `docker` injoignable la fait continuer au lieu de
la tuer. Son **panneau inline a été retiré du volet** pour l'alléger : la sonde reste lançable
et arrêtable comme un job (`make watch-containers`, suivi dans le second bloc), mais son détail
(mesures, pics, chutes, appelants) se lit dans ses fichiers plutôt qu'à l'écran.

À la place, une **ligne unique « dernière erreur LLM »** : le dernier échec de décision, lu en
fin des `erreurs.jsonl` des exécutions en cours, remplacé à chaque nouvelle erreur (horodatage,
type, message, personne). Elle dit d'un coup d'œil ce qui coince — quota, passerelle saturée —
sans historique ni dépliage.

Trois blocs, dans cet ordre : **ce qui tourne d'après le disque** (mêmes exécutions
et mêmes jeux que la tuile de la vue d'ensemble, rafraîchis toutes les 5 s), **les
exécutions arrêtées** (10 s), puis **les cibles `make` lancées depuis cette session**.
L'ordre dit la primauté : le registre de jobs ne connaît que cette session, le disque
connaît tout le reste.

Dans les deux blocs d'exécutions du volet, chaque ligne est **préfixée du fournisseur** —
`🧪 antigravity / exp_agy-gemini-38-f_… / 2026-09-09_13_05_09`, `🪫 cerebras / exp_gemma-4-31b_…`
— avec la même dérivation que la colonne du registre. Un décideur sans LLM n'a pas de préfixe :
« — / » ferait croire à une information manquante. La tuile compacte de la vue d'ensemble le
porte aussi, puisque c'est le même rendu (deux rendus du même état finiraient par se
contredire).

### Les exécutions arrêtées, leur cause, leur reprise

Ajouté le 2026-09-09. Une exécution qui s'arrête quittait ce volet à la seconde même : quota
épuisé pendant la nuit, passerelle injoignable, PC éteint, pause — il fallait aller la chercher
dans le registre de 🧪 Expériences pour comprendre ce qui s'était passé et la reprendre.

Chaque ligne dit **pourquoi**, et la cause est dérivée de ce qui est écrit, jamais devinée :

| Cause | Lue dans |
|---|---|
| 🪫 quota épuisé | `etat.json` : `epuisee`, ou `en_attente_quota` que plus rien n'écrit — l'heure de reprise annoncée par le fournisseur est reprise en détail |
| 🧩 prompt refusé | le **message** du dernier échec : `variante de prompt 'expert_chaine_m5' introuvable dans prompts.yaml` — une erreur de **configuration**, pas une panne |
| 🤖 sous-agent Antigravity muet | `antigravity: pas de réponse en 600s` |
| 🚧 passerelle saturée | `passerelle_occupee`, `Providers saturés ou indisponibles après 8s (50 retries épuisés)` |
| 📡 passerelle injoignable ou coupure réseau | `Gateway LLM injoignable (ConnectError)`, `[Errno -2] Name or service not known`, `Server disconnected without sending a response.` |
| 🔌 PC ou conteneur arrêté | `interrompue` (pid mort, réconcilié par l'ordonnanceur), ou `en_cours` alors que plus rien n'est écrit depuis `FRAICHEUR_EXECUTION_S` |
| ⏳ pause automatique | `en_pause`, raison `pause automatique` — le chien de garde au-delà de `EXP_INACTIVITE_PAUSE_S`, quand le journal ne révèle rien de plus précis |
| ⏸ mise en pause · arrêtée incomplète | `en_pause`, raison `pause` ou `incomplète` |
| ❔ inconnue | aucun des cas ci-dessus : l'état brut est affiché tel quel, rien n'est inventé |

Les quatre causes du milieu **ne se lisent que dans `erreurs.jsonl`** — le runner ne les nomme
jamais dans l'état, qui se contente du symptôme (« plus rien n'avançait »). Leur ordre de
priorité est porteur de sens et vit dans `SIGNAUX_ERREUR` : **la saturation passe avant le
réseau**, parce que `passerelle_occupee: Timeout expiré` est une passerelle débordée et non un
câble coupé, que le mot « timeout » du motif réseau classerait à tort. Et aucune ne prend la
place d'une cause qui se nomme elle-même : sur une exécution épuisée, l'heure de reprise du
quota vaut mieux que tout diagnostic — le diagnostic reste dit dans le détail.

Le détail cite **le message entier** du dernier échec (tronqué à 220 caractères ; le plus long
des archives en fait 483, avec la liste des variantes de prompt connues), **l'instance** qui a
lâché — `cerebras_gemma_4_31b_key1`, `antigravity:gemini-3.8-flash`, ce que la famille de
fournisseur ne dit pas —, **le nombre d'échecs identiques consécutifs** (`≥12` quand la
répétition remplit toute la fenêtre relue : on ne sait pas ce qu'il y a avant), l'horodatage, et
le temps depuis la dernière écriture. Jusqu'au 2026-09-09 seul le *type* était affiché : « pause
automatique — plus rien n'avançait · dernier échec : Exception interne » décrivait le symptôme
en jetant la seule information actionnable, qui était `variante de prompt introuvable`.

**« ▶ Reprendre »** y lance `make experience-reprendre` avec les services requis : la reprise ne
redemande aucune décision déjà acquise, et la ligne affiche combien sont déjà archivées.
N'y figurent pas : une **archive scellée** (arrêt définitif, exécution menée à terme), immuable
(E19) ; une exécution qui tourne ou qui dort en attente de quota, qui repartira seule ; une
exécution **obsolète**, que `make experience-reprendre` ne toucherait pas — celles-là sont
**comptées** en légende, pas escamotées. Une ligne **retirée du tableau** (`🗑`, `.masques.json`)
n'y figure pas non plus : le retrait est un choix de l'utilisateur, que le panneau des entrées
retirées de l'onglet Expériences restitue d'un clic.

Les durées restantes s'écrivent en **`hh:mm:ss`** partout (« reste ≈ 01:52:45 ») : « reste ≈
6765 s » ne se lit pas. Les heures ne sont pas bornées à 24 — une construction de jeu de trente
et une heures s'écrit `31:20:05`.

Dans le second bloc, ce qui tourne passe devant ce qui est terminé, le plus récent
d'abord à l'intérieur de chaque groupe : le registre rend l'ordre chronologique
inverse, où un job fini il y a une minute s'affichait au-dessus d'un job encore en
cours — dans un volet nommé « Activités en cours ».

Chaque lancement est un sous-processus détaché (`start_new_session`) dont la
sortie complète est écrite dans `experiments/.dashboard/<n>-<cible>.log`
(dossier ignoré par git). Le volet affiche l'état, la durée, **l'heure de
lancement**, le code retour et les 400 dernières lignes de sortie, rafraîchis
toutes les deux secondes sans recharger la page. Un job d'expérience
(`experience-lancer` / `-reprendre`) ajoute le **décideur** de l'expérience visée
(lu dans son `experience.yaml`), pour distinguer deux lancements de la même cible
et savoir quel modèle a tourné sans ouvrir le job.

**La console qu'on ouvre reste ouverte.** Le volet du job le plus récent est déplié d'office,
mais seulement au premier affichage : le pli choisi ensuite appartient au lecteur et survit aux
rafraîchissements. Le volet se rejouant toutes les deux secondes et l'argument `expanded` d'un
`st.expander` l'emportant à chaque tour, un simple `expanded=(index == 0)` refermait la console
d'un job relégué en deuxième position par un lancement plus récent — impossible, avec deux
expériences en parallèle, de lire le journal de la plus ancienne. Le pli est désormais écrit
dans `session_state` (`key` + `on_change="rerun"`) puis relu à chaque tour.

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

**Le statut se change depuis la page**, dans le tiroir de chaque ticket : un
sélecteur au vocabulaire fermé, la note à côté, un bouton qui écrit le fichier.
Trois garanties, parce que ce fichier porte 1 470 lignes de notes écrites à la main :

- l'écriture ne touche que l'entrée du ticket visé — commentaires d'en-tête, ordre
  des entrées, notes et style des autres tickets sont préservés **à l'octet** ;
- enregistrer sans rien changer **n'écrit pas** le fichier : pas de `git status`
  sali par un clic de vérification ;
- le fichier est **relu au moment du clic** : une édition faite à la main entre-temps
  n'est pas écrasée — y compris la note du ticket édité, qui n'est réécrite que si on
  l'a effectivement modifiée dans le formulaire. Modifiée, elle gagne : c'est une
  intention explicite, et le tiroir dit quand la note du fichier a changé depuis
  l'ouverture. Une retouche qui ne change que des espaces n'écrit rien — ils sont
  normalisés — et le tiroir dit cela, pas « rien à enregistrer » : la comparaison porte
  sur le texte tel qu'il sera stocké, jamais sur la frappe brute. Le champ porte une clé stable, sans quoi son identité dépendait de son
  contenu : une édition du fichier entre deux rendus faisait jeter le texte tapé, en
  affichant « rien à enregistrer ».

Une note laissée vide retire la clé ; une note écrite ici est repliée en bloc `>-`
autour de 88 colonnes, comme les notes existantes, ses espaces multiples normalisés.
Un ticket sans entrée en reçoit une, ajoutée en fin de liste, avec pour clé son
**nom de fichier complet** — et son tiroir le dit avant tout enregistrement, avec la
source de son statut affiché : `à faire` pré-sélectionné n'est pas une décision déjà
prise, seulement le point de départ du sélecteur.

Le vocabulaire reste **fermé** : une valeur hors liste dans le fichier lève toujours
une erreur plutôt que de passer inaperçue. Une clé invalide et un statut inconnu sont
deux causes distinctes, et chacune s'affiche avec la sienne : accuser un « statut
inconnu » pour un problème de clé enverrait chercher au mauvais endroit. Mais depuis que le fichier s'édite des
deux côtés, cette erreur est **arrêtée dans l'onglet Tickets** : elle y nomme la
valeur fautive et les valeurs admises, sans interrompre le script. Auparavant une
faute de frappe faisait disparaître l'onglet 🧪 Expériences avec celui-ci, sous forme
de traceback.

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

⚠ **Clé = nom de fichier complet, et rien d'autre.** Toute clé du fichier doit désigner
**exactement un** ticket : une forme courte (`ticket_005`) ou une clé mal orthographiée
est refusée à la lecture **et à l'écriture**, en nommant les tickets qu'elle viserait —
sans quoi l'interface produirait un fichier qu'elle ne saurait plus relire. La première
appliquerait un seul statut à deux tickets distincts, la seconde ne s'appliquerait à
rien — on croirait avoir posé un statut qui n'est nulle part. Deux tickets distincts
partagent le numéro 005
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
| `scripts/dashboard/makefiles.py` | lecture des Makefile, métadonnées et variables des cibles (plus affichées en catalogue, toujours résolues derrière chaque bouton) |
| `scripts/dashboard/runner.py` | lancement, suivi et arrêt des sous-processus |
| `scripts/dashboard/tickets.py` | lecture des tickets, et **écriture** du statut (round-trip ruamel) |
| `scripts/dashboard/experiences.py` | expériences : formulaire, registre, activités en cours lues sur disque |
| `scripts/dashboard/mes_travaux.py` | suivi personnel : plan × runs réels, diff fiche↔exécution, **écriture** de `experiments.yaml` (round-trip ruamel) |
| `scripts/dashboard/metrics.py` | Docker, runs, providers.yaml, erreurs LLM, synthèse, calibration, git — jamais de réseau |
| `scripts/dashboard/live.py` | les seules sondes réseau : `/health` API, `/metrics` controller, `pgrep` |
| `scripts/dashboard/palette.py` | couleurs de mode et d'état |

## Voir aussi

- [docs/arch/score-synthesis.md](score-synthesis.md) — la page de synthèse dont le dashboard lit les scores
- [docs/arch/prompt_calibration.md](prompt_calibration.md) — les campagnes dont il lit l'avancement
- [docs/arch/monitoring.md](monitoring.md) — Prometheus et Grafana, pour les métriques temps réel d'un run en cours

## Onglet « 🧪 Expériences » (ticket 035)

Deux blocs (`scripts/dashboard/experiences.py`). **Nouvelle expérience** : un formulaire compose
le fichier `data/experiences/<nom>/experience.yaml` (population et jeux lus sur le disque,
variantes de prompt lues dans `prompts.yaml`, modèles lus dans `providers.yaml`), l'enregistre, le
fait valider et lance par le registre de jobs. **Le nom ne se saisit pas** : il se calcule des
paramètres et s'affiche en tête du formulaire (cf. « Le nom se calcule » plus bas) ; « S'inspirer de » recopie une expérience existante **dès qu'elle est choisie dans la liste** (E4, spec
`inspirer-recopie-immediate`) — « — partir de zéro — » remet les défauts, « ↺ Recopier à nouveau » réapplique la source après des
retouches, une légende nomme ce qui vient d'être recopié tant que le formulaire n'est pas retouché, une expérience supprimée du disque —
au moment du choix ou après coup — laisse le formulaire intact, le dit et remet la liste d'aplomb, et les valeurs relues passent par la
même validation que le brouillon (une valeur inconnue ou hors bornes revient à son défaut au lieu de casser la page) ; « Dupliquer »,
dans « Mes expériences », fait la même recopie ; le prompt choisi s'affiche en entier et peut être retouché puis enregistré sous un autre nom (`ajouter_variante`, ajout en fin de `prompts.yaml`, relu et annulé si invalide, jamais d'écrasure) ; quand le décideur choisi **ne lit aucun prompt** (modèle statistique, rejeu, tirage, durée minimale), le sélecteur et l'aperçu restent offerts — lire un prompt avant de le choisir est utile en soi — mais le titre porte « non lu par ce décideur » et une légende dit que ce choix n'entrera ni dans le nom calculé ni dans la colonne `prompt` du registre ; la liste des modèles porte les requêtes/jour restantes lues sur `/health` ; le bloc **🐳 Services nécessaires** est remonté en tête de la configuration, en **lecture seule** (plus de bouton de démarrage : « ▶ Lancer » démarre lui-même ce qui manque) et n'affiche plus la liste des dépendances entraînées. **« Estimer le coût »** ouvre une popup réduite au **nombre de requêtes LLM** (durée et part de quota en légende). Le bouton **« Warm-up : construire le jeu »** n'apparaît que lorsqu'aucun jeu n'existe encore pour la population : préparer un second jeu ne se fait plus d'ici. Il n'y a plus de case de confirmation d'écrasement (réenregistrer un nom déjà exécuté est direct — les exécutions archivées gardent leur copie figée) ni de case « Arrêter d'abord ce qui tourne » : lancer n'interrompt plus les exécutions concurrentes. **Mes expériences** : registre (état, décideur, prompt, jeu,
couverture décidés / attendus exploitables, parts modales), barre d'avancement des exécutions en
cours lue dans `progression.json` (écrit toutes les 5 s par le runner). Les colonnes
`composite_emd` / `composite_l1` et l'icône 📊 se remplissent **toutes seules** : le runner score
l'exécution à sa clôture (R23) et la table lit le `scores.json` produit — plus rien à déclencher
à la main. Une exécution non terminée (en cours, en pause, **arrêtée**) reste à « — » : elle
n'est pas scorable. Le décideur est affiché
**sans le préfixe `passerelle:`** — le modèle seul (le préfixe était du bruit) ; les autres types
gardent leur libellé (`rejeu`, `aleatoire`…). La colonne **`prompt` ne dit une variante que si le
décideur en lit une** : seule la passerelle reçoit un prompt système
(`experiences/cli.py` ne transmet `parameters.prompt_variant` que sous
`decideur.type == "passerelle"`), si bien qu'un modèle statistique, un rejeu, un tirage ou
l'heuristique de durée affichent « — ». C'est la même règle que N5 du nommage, qui retire pour
cette raison le segment de prompt du nom calculé (`exp_lgbm_jtir_nosim`, et non
`exp_lgbm_minper_jtir_nosim`). Comme le décideur, le prompt suit le **snapshot figé** de chaque
exécution, pas la définition courante. La colonne **`fournisseur`**, à côté du décideur, dit
**qui sert les décisions** : `local` (une instance LM Studio, reconnue à son `base_url`),
`google`, `groq`, `cerebras`, `mistral`… (l'`adapter` de l'instance dans `providers.yaml`,
jamais son nom — il porte un suffixe `_key1` et onze instances Google désignent un seul
fournisseur), `antigravity` quand la décision passe par un sous-agent plutôt que par la
passerelle — le type l'emporte alors sur le nom du modèle, qui peut être celui d'un modèle
distant. Un modèle servi par deux familles les porte toutes les deux (`cerebras · groq`) : rien
n'est arbitré au hasard. Un modèle qu'aucune instance ne sert affiche `inconnu`, et un décideur
qui ne sollicite aucun LLM (tirage, durée minimale, modèle statistique, rejeu) affiche `—` : la
colonne `decideur` dit déjà l'heuristique. Ce fournisseur suit lui aussi le **snapshot figé**,
pour la même raison que le décideur et le prompt. La case **« Masquer les obsolètes »**, à côté du filtre et
du tri, **cochée d'office**, retire les exécutions qu'une plus récente de la même expérience a
remplacées ; la dernière exécution de chaque expérience reste toujours visible. Elle a remplacé
« Terminées seulement » le 2026-09-09 : ce qui encombre le registre, ce sont les passages
successifs d'une même expérience, pas les états non terminés. C'est un filtre de **vue**,
décoché d'un clic, sans rapport avec « 🗑 Retirer du tableau » ; il compte les lignes qu'il
masque, et le panneau de progression plus bas parcourt les lignes non filtrées — cocher la case
ne peut donc pas faire perdre de vue une exécution qui tourne ni ses boutons Pause / Arrêter
(une exécution qui tourne est de toute façon la dernière de son expérience, donc jamais
obsolète). La colonne `etat` porte le suffixe de l'obsolescence **avec ce qu'elle coûte** :
« obsolète (résultat complet) » sur une exécution menée à terme, dont les scores restent
lisibles et comparables, « obsolète (partielle) » sur une exécution que la reprise ne touchera
plus. `obsolete` est un état de **vue**, calculé par `lister()` : il n'est jamais écrit dans
`etat.json`, dont le runner reste seul propriétaire. **Cliquer une ligne** du tableau ouvre ses actions —
Rejouer, Reprendre, Dupliquer, et **🗑 Retirer du tableau** — juste au-dessus de son détail de score par
sous-catégorie : on agit sur ce qu'on regarde (plus de sélecteur séparé, et le volet « Détail
exécution → personne → déplacement → trace » a été retiré). Les contrôles **⏸ Pause / ⏹ Arrêter**
d'une exécution en cours (fichiers `PAUSE` / `STOP`, honorés en quelques secondes) sont eux aussi
au-dessus du détail. **🗑 Retirer du tableau se fait en un clic et n'efface rien** : la ligne
cliquée — cette exécution-là, pas les autres de la même expérience — sort du registre, sa définition
et ses archives restent sur le disque. Les lignes retirées sont notées dans
`data/experiences/.masques.json` (écriture atomique) et filtrées par `lister()` ; un bandeau
**🙈 N entrée(s) retirée(s) · ↩ Tout réafficher** les compte et les rend, y compris quand le
registre est devenu vide — sans quoi la dernière ligne retirée emporterait le seul bouton capable
de la rendre. Le retrait refuse une exécution encore vivante, qui sortirait du panneau « en cours »
pendant qu'elle écrit, et une ligne retirée qui se remet à tourner (reprise lancée en console)
réapparaît d'elle-même tant qu'elle écrit. L'effacement définitif du dossier `data/experiences/<nom>/`
(`supprimer_experience`) n'est plus branché à l'IHM : un clic y détruisait des heures de calcul sans
retour possible. Le tableau de bord lit et écrit des fichiers et n'importe pas la pile du
contrôleur ; une exécution dont le dossier a disparu reste listée « archive manquante ».

### Tout ce qui vit se rafraîchit seul

Sept blocs se réveillent d'eux-mêmes, et un seul principe les gouverne : **ne battre que
tant qu'il y a quelque chose à suivre**, puis s'arrêter. Interroger Docker ou le disque en
boucle quand rien ne bouge ne sert personne.

| Bloc | Rythme | Condition |
|------|--------|-----------|
| Jobs (barre latérale et volet) | 2 s | toujours |
| Activités lues sur disque | 5 s | toujours |
| Exécutions arrêtées | 10 s | toujours |
| État du run GAMA | 5 s | toujours |
| Vue d'ensemble | 10 s | toujours |
| Dernière erreur LLM | 5 s | toujours |
| Services nécessaires | 5 s | tant qu'il en manque un |
| Jeux en construction | 5 s | tant qu'un warm-up tourne |
| Registre des expériences | 5 s | tant qu'une exécution tourne |
| Panneau des lancements | 5 s | tant qu'un job tourne |

Chacun de ces blocs conditionnels recharge la page **une seule fois** quand l'état qu'il
surveille change, parce que les avertissements et les boutons qui en dépendent sont calculés
ailleurs dans la page. Sans cela, une exécution terminée restait annoncée « en cours » jusqu'au
prochain clic — constaté le 2026-09-07 sur un run fini à 99,8 % de couverture.

Une limite mesurée : dans un onglet caché ou en arrière-plan, le navigateur ralentit ces
minuteries. Le bandeau des services a mis 25 secondes à s'effacer au lieu de 5 dans un volet
masqué. C'est le seul argument technique sérieux en faveur d'un mode poussé (SSE), le jour où
suivre la page sans la regarder deviendra un besoin.

### Ce que le formulaire ne laisse plus passer

Trois pièges se sont refermés le 2026-09-06, sur un warm-up d'une heure suivi d'un redémarrage :

**Un jeu qui se construit est visible, et sa fin est vue.** Le manifeste d'un jeu est écrit dès
l'ouverture avec `clos: false` : le jeu figure donc dans la liste de sa population, marqué
« EN PRÉPARATION », et l'avertissement « aucun jeu préparé » ne s'affiche que si la population
n'en a réellement aucun. Surtout, le bloc de progression **se rafraîchit tout seul toutes les
5 s** tant qu'une construction tourne, et quand la liste des jeux de cette population change —
un jeu apparaît, ou vient d'être clos — la page se recharge **une fois** d'elle-même. Sans cela,
un warm-up terminé à 21 h 36 laissait à l'écran l'état de 20 h 33 : « aucun jeu préparé » et un
bouton de construction actif, alors que le jeu était clos et exploitable.

**Le bouton de construction est gardé.** Il est désactivé tant qu'une construction écrit la
progression de ce jeu (moins de deux minutes), avec le motif affiché. Passé ce délai plus rien
n'écrit : le bouton redevient actif, et la construction reprendra où elle s'était arrêtée.

**Aucun bouton grisé sans motif.** Sous les quatre boutons, une ligne par bouton indisponible
dit ce qui lui manque : aucun jeu, jeu pas encore clos, service `controller` arrêté, registre de
lancements absent, ou — le seul cas de nom manquant qui subsiste — un paramètre sans lequel le
nom ne peut pas être composé (`decideur.modele` vide). Un « ▶ Lancer » interdit sans explication
se lit comme une panne du tableau de bord alors qu'il ne manquait qu'un réglage. Même règle ailleurs
dans la page : « ⏹ make stop-run » et « ▶ Reprendre » portent leur ligne écrite, et tout autre
bouton désactivé porte au minimum une aide au survol qui dit ce qu'il attend.

### Le nom se calcule

Le nom d'une expérience est son identité : le dossier, la clé de la file d'attente, la cible de
`arreter`. Et `experience.yaml` ne porte qu'**un** décideur. Tant que le nom était saisi, changer
le modèle dans le sélecteur et réenregistrer sous le même nom n'ouvrait pas une variante : ça
écrasait la précédente — le 2026-09-07, trois modèles ont été mesurés sous `Prompt_Minimaliste`
et le fichier n'a gardé que le dernier.

Le champ de saisie a donc disparu. Le formulaire **affiche** le nom que les paramètres imposent
(`experiences/nommage.py`, spec `nommage-canonique-experiences`) :
`exp_gemini-31-fl_minper_jtir_t0_nosim` — décideur, prompt, calendrier, écarts aux valeurs de
référence, puis température et mode, toujours nommés. Le modèle étant dans le nom, deux modèles
ne peuvent plus partager une identité.

Trois cas, dits à l'écran sous le nom :

- **nom libre** — rien à signaler, la définition sera écrite là ;
- **définition déjà enregistrée** (mêmes paramètres au caractère près) — la page dit sous quel
  nom et avec combien d'exécutions : lancer en **ajoute une**, rien n'est réécrit ;
- **nom déjà pris par une définition différente** (deux réglages que la grammaire abrège
  pareil, comme deux `top_p`) — un indice est ajouté, `_2`, `_3`, à la façon d'une copie de
  fichier. Jamais d'écrasure silencieuse.

Renommer l'existant est un geste explicite : `make experiences-renommer` dit ce qui bougerait,
`APPLIQUER=1 FUSIONNER=1` renomme et réunit les définitions identiques.

Même logique en dupliquant (« s'inspirer de ») : rien ne recopie le nom de la source, il se
recalcule. Une copie qui ne change aucun paramètre retombe donc sur la source — et la page le dit,
au lieu de la réécrire.

> **Avant :** trois lancements de « Prompt_Minimaliste » sur gemini, gpt-oss puis mistral (2026-09-07)
> écrasaient le même fichier ; le tableau de bord montrait trois exécutions homonymes, une seule
> définition, et les lancements se disputaient une clé au lieu de tourner en parallèle.
> **Après :** trois noms distincts, trois jeux de clés disjoints, trois exécutions simultanées.

### Les services Docker que cette expérience utilise

Une expérience n'a pas besoin de toute la pile. Elle s'exécute dans `controller`, s'appuie sur
la passerelle (`api`, `worker`) **seulement** si son décideur est un modèle de langage, et sur
les moteurs de routage (`otp1`, `otp2`, `otp3`, `osmnx1`) **seulement** s'il reste un jeu à
construire. Une heuristique, un tirage graîné ou un rejeu n'attend rien de la passerelle.

Au-dessus des boutons, un bloc dit ces services et l'état de chacun. Il reste visible quand
tout tourne : on doit savoir sur quoi on s'appuie, pas seulement ce qui manque. Il est en
**lecture seule** depuis le 2026-09-09 : son bouton « Démarrer les N service(s) manquant(s) »
a été retiré, parce que c'était une étape à ne pas oublier avant de cliquer sur « Lancer ».

**Le lancement démarre lui-même ce qui manque.** `make experience-lancer` (donc
`experience-reprendre`) et `make jeu` commencent par `make services-pretes REQUIS="…"`, qui
fait `docker compose up -d --no-recreate --wait` sur les seuls services nommés — jamais `make up`, qui
réveillerait aussi les cinq services de métrologie (Prometheus, Grafana, cAdvisor,
node-exporter, Flower) dont une expérience n'a aucun usage. La cible est idempotente : sur une
pile déjà debout, elle passe en une seconde. Le tableau de bord lui passe `REQUIS=` calculé sur
la définition de l'expérience ; en ligne de commande, le défaut est `controller` seul
(`controller otp1 otp2 otp3 osmnx1` pour `make jeu`). `SERVICES=` reste, à côté, la liste de ce
qu'on **arrête** en fin de run : deux listes différentes, deux variables distinctes.

**`--no-recreate` n'est pas un détail.** Un `up -d` nu recrée un conteneur dont la
configuration a bougé depuis son démarrage — et recréer `controller` **tuerait le runner d'une
expérience en cours**, qui y vit par `docker compose exec`. Cette cible étant chaînée à chaque
lancement, y compris pendant qu'une autre expérience travaille, elle démarre ce qui manque et ne
touche à rien de ce qui tourne. Appliquer un changement de configuration reste le travail de
`make run`, qui recrée le contrôleur explicitement quand `config.yaml` a changé.

Ce que cela coûte, dit franchement : `controller` dépend d'`api`, `otp1-3`, `eqasim` et
`osmnx1` en `service_healthy`, et le chargement des graphes OTP/OSMnx prend plusieurs minutes à
froid. Un lancement services éteints attendra donc, visiblement, dans le journal du job ;
`ATTENTE` (600 s par défaut) borne cette attente pour échouer bruyamment plutôt que de pendre
indéfiniment. Le bloc de la page le dit **avant** le clic, en comptant les services à démarrer.

Conséquence sur les verrous : un `controller` éteint ne grise plus « ▶ Lancer » ni
« 🔥 Warm-up » — il les ferait échouer, alors qu'ils le démarrent. Il grise encore
« 🧮 Estimer le coût », qui lit la réponse de la plateforme en direct et ne peut pas attendre.
Ce qui grise « Lancer », désormais, c'est un **démon Docker muet** : là, personne ne démarre
rien. `make up-services` reste, pour démarrer des services sans rien lancer.

Le compose entraîne les dépendances des services nommés, et la page les nomme aussi : sans
cela elle laisserait croire qu'elle démarre trois conteneurs quand elle en démarre huit. Ce
graphe est **lu dans `docker-compose.yml`**, jamais recopié dans le code, et sa lecture ne
lance aucun sous-processus. La tuile « Services » de la vue d'ensemble, elle, garde un bouton
`make up` pour toute la pile.

Le bloc se rafraîchit **tout seul** tant qu'il manque un service, et la page entière se
recharge une fois dès que l'ensemble des manquants change : sinon le bandeau « le service
`controller` ne tourne pas » survivrait à son démarrage, n'étant recalculé qu'à la prochaine
réexécution du script, donc au prochain clic. Pendant cette surveillance l'état des services
est sondé toutes les 3 secondes au lieu des 15 du cache normal, faute de quoi la sonde
relirait la même valeur périmée. Quand tout tourne, la sonde s'arrête : Docker n'est pas
interrogé en boucle.

Attention à ce que « en marche » veut dire ici : le conteneur tourne. Que la passerelle
réponde se lit ailleurs, sur son `/health`, dans l'onglet 🤖 Providers.

### Un job n'écrit jamais dans le journal d'un autre

Chaque lancement écrit dans `experiments/.dashboard/<index>-<cible>.log`. L'index vient d'un
compteur du registre, qui vit dans `st.cache_resource` : un redémarrage du serveur Streamlit le
remet à neuf, alors que les jobs déjà lancés sont **détachés** et continuent d'écrire. Le compteur
repartait de 1, si bien qu'un nouveau `001-root-experience-lancer` rouvrait **en écriture** le
journal d'un `001-root-experience-lancer` d'une session précédente encore vivant : les deux
poignées écrivaient dans le même fichier, chacune à son décalage. Le 2026-09-08, la console d'un
job « meta/muse-glimmer » affichait la fin d'une course Gemini.

Le compteur repart donc du plus grand index déjà présent dans le dossier (`runner.dernier_index`),
et le lancement saute tout nom de fichier qui existe déjà. Les journaux s'accumulent au lieu d'être
réutilisés ; le bouton « Purger l'historique » les efface.

### « S'inspirer d'une expérience existante » : la plus récente d'abord

La liste va de l'expérience la plus récemment utilisée à la moins récente ; celles qui n'ont jamais
tourné ferment la marche, par ordre alphabétique. L'ordre alphabétique mettait en tête des
expériences oubliées depuis des semaines, alors que ce sélecteur sert d'abord à repartir de ce
qu'on vient de faire.

Le critère est la dernière **écriture** d'un `etat.json`, pas le nom du dossier d'exécution :
celui-ci porte l'heure de **création**, si bien qu'une exécution ouverte le matin et reprise le
soir passerait pour vieille. `etat.json` est réécrit à chaque changement d'état, donc à chaque
reprise, pause ou clôture. Une `stat()` par exécution, aucun fichier ouvert.

### Le modèle local que cette expérience utilise (LM Studio)

Le sélecteur « Décideur » distingue **modèle de langage (distant)** — un fournisseur d'API,
avec ses clés et son quota journalier — et **modèle de langage (local, LM Studio)** — un modèle
servi par LM Studio sur cette machine. Chaque entrée n'offre que les modèles de son bord, lus dans
`providers.yaml` : est local tout modèle dont une instance vise le port 1234 de l'hôte. Le fichier
écrit ne connaît pas cette distinction : les deux s'enregistrent `decideur.type: passerelle`, et
une expérience relue se range du côté qui sert son modèle **aujourd'hui**. Le libellé d'un modèle
local dit sa taille et son état dans LM Studio, pas des « requêtes/jour » qui n'ont aucun sens pour
lui ; le parallélisme conseillé devient son nombre d'appels simultanés (`concurrency_limit`), un ou
deux sur un Mac, au lieu d'un cinquième d'un débit par minute.

Sous le bloc des services, quand le modèle est local, un bloc **🖥️ Modèle local** lit
`GET /api/v1/models` de LM Studio (vu de l'hôte, où tourne le tableau de bord) et dit l'un de cinq
états : prêt, LM Studio injoignable, modèle inconnu, non chargé, ou chargé avec un contexte
inférieur à 8 192 jetons — deux agents par requête font environ 4 400 jetons de prompt avant la
réponse, et LM Studio charge à 4 096 par défaut. Un bouton charge le modèle avec 16 384 jetons par
`make lmstudio-charger` (suivi dans 📟 Activités en cours), décharge d'abord ce qui est en mémoire
sous ce nom s'il faut recharger, et un autre décharge un modèle voisin qui occupe la mémoire. Le
bloc se rafraîchit seul tant que le modèle n'est pas prêt, et la page se recharge dès que l'état
change. Tant qu'il ne l'est pas, **« Lancer » est grisé avec le motif** ; enregistrer et estimer
restent possibles, ils n'appellent pas le modèle.

Pourquoi : le 2026-09-08, une expérience lancée sur Muse Glimmer a tourné sept minutes sans une
décision. Le modèle n'était pas chargé ; LM Studio l'a chargé à la volée, plus lentement que les
120 s de l'adaptateur, puis avec 4 096 jetons de contexte. La plateforme a fini en pause
automatique, et rien dans l'interface ne disait pourquoi.

Alias local : quand l'identifiant d'un modèle LM Studio est aussi celui d'un fournisseur distant
(`qwen/qwen3.8-27b` est servi par Groq), l'instance locale porte un alias suffixé `-local`
(`qwen3.8-27b-local`), chargé par `lms load <clé> --identifier <alias>`. Le bloc retrouve la clé
source en retirant le suffixe et en cherchant la clé dont le dernier segment correspond ; deux
clés candidates, et il refuse de deviner. Le code : `scripts/dashboard/lmstudio.py`, pur hormis le
GET, testé sur des réponses figées dans `scripts/tests/test_dashboard_lmstudio.py`.

### Arrêter une exécution depuis son bloc

Chaque exécution en cours porte deux boutons, et la différence entre eux n'est pas cosmétique.
La **pause** laisse l'exécution reprenable : l'archive n'est pas scellée, les décisions acquises
ne seront pas repayées. L'**arrêt** scelle l'archive : le résultat partiel reste exploitable, mais
l'exécution ne peut plus être reprise. Confondre les deux a coûté 209 décisions le 2026-09-07,
d'où l'absence de tout bouton dans la tuile compacte de la vue d'ensemble, qui se rafraîchit
toutes les dix secondes.

**La case « Je confirme l'arrêt définitif » a été retirée le 2026-09-09**, à la demande de
l'auteur : « ⏹ Arrêter » est cliquable directement. Ce qui garde encore ce geste irréversible,
c'est le libellé, l'aide au survol et une légende sous les deux boutons qui écrit la différence
— la pause laisse l'exécution reprenable, l'arrêt scelle l'archive.

**Les deux boutons disparaissent quand l'exécution n'écrit plus (correctif 2026-09-08).**
`etat.json` reste sur `en_cours` pour toujours quand le runner a été tué net : les contrôles
étaient donc offerts sur un cadavre, où une sentinelle n'interrompt rien et ne fait qu'attendre
la reprise suivante pour la saboter. La ligne affiche à la place une légende qui renvoie vers
**▶ Reprendre**, seul chemin utile à ce moment-là. La garde s'appuie sur `execution_vivante()`,
qui existait déjà pour `est_reprenable()` et pour « arrêter avant de lancer » mais n'avait
jamais été branchée sur ces deux boutons.

L'une comme l'autre sont **effectives en quelques secondes** : le runner laisse un délai de grâce
(`EXP_PAUSE_GRACE_S`, 15 s) aux sollicitations déjà en vol, puis les abandonne. Le clic, lui, se
voit **tout de suite** : le fichier déposé est relu à chaque rafraîchissement, la barre écrit
« ⏸ pause demandée il y a N s, en cours » et le bouton passe à « Pause demandée ». Auparavant le
message promettait « le prochain point sûr » et rien ne bougeait à l'écran pendant les deux
minutes que pouvait durer l'attente d'un appel LLM.

La barre écrit aussi **« ⏳ immobile depuis N min »** dès une minute sans le moindre déplacement
réglé (`immobile_depuis_s` de `progression.json`) : au-delà de `EXP_INACTIVITE_PAUSE_S` (7 min par
défaut), le runner met l'exécution en pause tout seul, en `[ALARME]`, plutôt que de la laisser
« en cours » indéfiniment. Elle reste reprenable, et son état dit pourquoi
(`pause automatique — 420s sans avancée`).

### La bascule de clé se lit sans nommer la clé

Quand une clé épuise son quota du jour, la plateforme passe à la suivante et l'écrit ainsi :

```
[decideur] Passage sur la seconde clé (2/2) — la précédente a épuisé son quota du jour ;
1 clé(s) encore disponible(s)
```

Le **rang**, jamais le nom. Un journal est lu, copié et transmis, et le nom d'une instance
désigne un compte : le rang dit tout ce qu'il faut pour agir sans rien exposer. La ligne est
en `WARNING`, parce qu'elle annonce qu'un seau de requêtes vient de se vider.

### Attentes et erreurs ne se comptent plus ensemble

La plateforme ne saute jamais un déplacement : une tentative qui échoue est réessayée jusqu'à
obtenir une décision. La compter comme une erreur faisait lire « 128 erreurs » sur un run dont
aucun déplacement n'avait échoué, et cachait le vrai signal — le débit du fournisseur. Les lignes
disent donc « 96 attentes (passerelle_occupee) », et le compteur d'erreurs est réservé aux échecs
définitifs, un déplacement clos sans décision. Il reste vide tant que la règle tient : une valeur
non nulle **dénonce** une violation, elle ne mesure pas une qualité.

### Un parallélisme tenable

Le formulaire propose une valeur calculée sur le débit de l'instance servie, un cinquième de ses
requêtes par minute, au lieu de huit par défaut. Sur une instance à quinze par minute, il propose
trois : demander huit gâchait la moitié des tentatives en « Providers saturés ». Le débit retenu
est celui d'**une** instance, la mieux dotée, parce que les clés d'un même modèle se consomment
en série, l'une après l'autre.

### Rendre la RAM à la fin de l'expérience

Une case à côté de « Lancer », décochée par défaut, arrête les services Docker quand
l'expérience est finie. Elle sert à ne pas laisser une pile inactive squatter la mémoire des
autres applications de la machine. Mesuré le 2026-09-07 sur cette pile :

| Service | Mémoire |
|---------|---------|
| `osmnx1` | 3,5 Gio |
| `otp3` | 1,5 Gio |
| `otp1` | 1,3 Gio |
| `otp2` | 1,2 Gio |
| `controller` | 1,0 Gio |
| passerelle (`api` + `worker`) | 0,2 Gio |

C'est pourquoi l'arrêt couvre les **dépendances** et pas seulement la tête de chaîne : arrêter
le seul contrôleur rendrait un gigaoctet sur neuf. Les cinq services de métrologie, que le
bouton de démarrage n'a pas lancés, ne sont pas arrêtés non plus ; `make down` reste la voie
pour tout couper.

Deux choix de mise en œuvre portent du sens. L'arrêt est **chaîné dans la commande lancée**
(`make experience-lancer-arret`, ou `make run-arret` avec GAMA), et non surveillé par la page :
il a donc lieu même navigateur fermé, ce qui est précisément le cas où l'on coche la case. Et
c'est `docker compose stop`, jamais `down` : conteneurs et volumes restent, le redémarrage ne
recharge que ce qu'il faut. Le code de retour de l'expérience est conservé malgré l'arrêt qui
suit, pour qu'un échec reste un échec dans le journal du job.

**Ces cibles ne se testent pas avec `make -n` seul (correctif 2026-09-08).** GNU make exécute
quand même toute ligne de recette contenant `$(MAKE)`, même sous `-n`, afin que le parcours
récursif puisse descendre. Dans `run-arret`, ce `$(MAKE)` partage sa ligne shell chaînée avec
`docker compose --profile offline stop …` : un `make -n run-arret` **arrêtait réellement** les
services nommés. Le motif a coupé `controller` et `osmnx1` 29 fois, dont deux sous une
expérience en cours — un run tué à 70,5 % le 2026-09-08, dont la cause a d'abord été imputée à
une fausse manœuvre de pause. Les tests de `scripts/tests/test_dashboard_services.py` placent
désormais un `docker` factice en tête de `PATH` (fixture `docker_hors_service`, appliquée à
tout le fichier) : plus aucun ne peut toucher le Docker réel, et ils vérifient en prime la
commande **réellement émise** au lieu de faire confiance à l'affichage de `make -n`.

### Arrêter ce qui tourne avant de lancer

Un lancement ne doit pas partir en concurrence d'un survivant, sur le même quota LLM et le
même contrôleur. Le cas est courant : une exécution survit à ce qui l'a lancée, son
`docker compose exec` tué sur l'hôte ne tuant pas le processus dans le conteneur, et son
`etat.json` reste « en cours ».

Quand quelque chose tourne, une case **cochée d'avance** apparaît au-dessus des boutons et
nomme ce qu'elle arrêtera : les exécutions à l'état « en cours », quelle que soit
l'expérience, et les jobs de la session qui lancent ou reprennent une exécution, ou un run
GAMA. Rien ne tourne, aucune case n'apparaît et le lancement est inchangé.

**Seule une exécution qui écrit encore compte comme concurrente.** Rester sur « en cours »
dans son `etat.json` ne suffit pas : l'arrêt étant coopératif, un runner tué laisse cet état
pour toujours. La leçon a coûté cher le 2026-09-07 : un `STOP` écrit dans une exécution déjà
morte a été honoré par la reprise suivante, qui a clôturé l'exécution en « arrêtée », donc non
reprenable, avec 209 décisions payées dedans.

**Une archive clôturée n'est jamais reprenable**, quoi que dise son `etat.json`. La clôture
vit dans `execution.yaml`, avec les empreintes des fichiers, et une archive clôturée est
immuable (E19) : la reprise y échoue à la première décision à écrire, sur « archive clôturée :
immuable ». Remettre `etat.json` à « en pause » ne change donc rien, et proposer la reprise
ferait une boucle.

**Une exécution reste reprenable après un runner tué.** « Reprendre » accepte cinq cas : en
pause, épuisée, **interrompue** (pid mort, réconcilié par l'ordonnanceur), **en attente de
quota tuée pendant son sommeil**, et restée « en cours » sans écriture depuis plus de dix
minutes. Sans le dernier, la page n'offrait aucun chemin propre : seulement « Rejouer », qui
repaie tout ; les deux du milieu manquaient au tableau de bord alors que la CLI les acceptait
déjà (elle reprend toute archive non clôturée). Et quand une exécution reprenable existe,
« Lancer » l'annonce avec le nombre de décisions déjà archivées, au lieu de créer une deuxième
exécution en silence.

**Une exécution obsolète n'est jamais reprenable.** `make experience-reprendre` reprend
`_derniere_execution` — la dernière exécution de l'expérience. Proposer la reprise d'un passage
plus ancien serait une promesse que le noyau refuse : le tableau de bord l'écarte donc, en
comptant ce qu'il écarte.

Trois choix portent du sens :

- **L'arrêt est coopératif** : un fichier `STOP` dans le dossier de l'exécution, honoré en
  quelques secondes (délai de grâce aux sollicitations en vol, puis abandon), résultat partiel
  exploitable. Aucun processus n'est tué dans le conteneur, un signal y laisserait l'état à
  « en cours » pour toujours et perdrait la garantie du point sûr.
- **La construction d'un jeu n'est jamais arrêtée.** Elle ne consomme pas de quota LLM, son
  produit est précisément ce que le lancement attend, et l'interrompre jetterait une heure de
  calcul reprenable.
- **Le lancement attend, puis refuse.** Trente secondes au plus pour que les exécutions
  quittent « en cours ». Passé ce délai, le lancement est refusé en nommant celles qui
  tournent encore, plutôt que de démarrer un concurrent. Ce qui a été arrêté est écrit dans
  la page, refus ou pas : sinon on relancerait sans savoir que du quota a déjà été rendu.

### Enregistrer une expérience sans la lancer

Écrire son plan aujourd'hui et lancer demain : le bouton « 💾 Enregistrer » écrit
`data/experiences/<nom>/experience.yaml` et rien d'autre. Il ne demande qu'un nom
recevable.

**Il n'exige pas que le jeu existe.** Le schéma de la plateforme accepte une expérience
qui nomme un jeu pas encore construit, et le warm-up dure une heure : attendre pour
écrire son plan n'avait pas de sens. Quand la population n'a aucun jeu, l'expérience
**nomme le jeu qu'elle attend**, celui que le bouton de warm-up construirait
(`<population>_<AAAAMMJJ>` pour le jour choisi). Elle devient donc lançable sans
retouche dès que ce jeu est clos. Changer le jour simulé change ce nom, à l'écran comme
dans le fichier.

**Il n'exige pas le conteneur.** L'écriture est locale ; la validation par la plateforme
(`make experience-definir`) tourne dans `controller` et n'est tentée que s'il tourne.
Sinon la page dit « enregistré, non validé », au lieu de laisser une erreur Docker se
lire comme un enregistrement raté. Le message donne le chemin écrit, le jeu attendu et
son état : absent, en construction, ou clos et prêt. Réenregistrer un fichier identique
le dit et ne le réécrit pas.

**Un nom déjà exécuté est gardé.** Réenregistrer sous un nom qui porte des exécutions
change la définition pour les exécutions à venir : une case de confirmation garde le
bouton. Les exécutions archivées ne bougent pas, chacune portant sa propre copie figée
de la définition dans son `execution.yaml`. Dans « Mes expériences », la colonne
`jeu_etat` dit si le jeu d'une expérience est prêt.

### Le libellé d'un jeu en construction

`couverts` et `attendus` n'entrent au manifeste qu'à la clôture. Le libellé d'un jeu
non clos dit donc « ?/? déplacements », jamais « None/None » — c'était le cas dans
lequel la liste du formulaire montrait précisément le jeu que ce travail rend visible.

### Le nom d'une expérience devient un dossier

`data/experiences/<nom>/` : le nom construit un chemin, et devient aussi la valeur de
`EXP=` passée à `make`, qui développe `$(EXP)` **sans guillemets** dans une commande shell.
Le nom étant désormais **calculé** (cf. « Le nom se calcule »), il satisfait ces contraintes par
construction : caractères de mot Unicode, tiret, souligné et point, 64 au plus, premier caractère
lettre ou chiffre — ce qui écarte `../…` et `-flag`. La garde reste en place à l'écriture
(`enregistrer` lève, sans quoi `../../evade` écrirait ailleurs dans le dépôt) : elle ne protège
plus d'une frappe mais d'un défaut de programmation, et le générateur refuse plutôt que de rendre
un nom douteux.

Deux autres saisies désignent un chemin **côté conteneur** et traversent sans validation :
« Dossier d'exécution à rejouer », et le champ « Population » libre qui n'apparaît qu'en
l'absence de population scellée. Le tableau de bord ne peut pas les résoudre, c'est la
plateforme qui les interprète : c'est une limite assumée, pas un oubli.

### La mémoire du formulaire

Les choix du formulaire sont écrits dans `experiments/.dashboard/formulaire_experience.yaml`
(dossier ignoré par git) et relus au démarrage suivant : `st.session_state` meurt avec le serveur
Streamlit, et retrouver quinze réglages à la main après chaque `make dashboard` fait renoncer.
C'est un brouillon, pas une expérience : aucun `experience.yaml` n'est écrit sans clic. À la
relecture, chaque valeur qui n'existe plus — population effacée, variante de prompt retirée, jeu
effacé, modèle disparu, décideur renommé, graine hors bornes — revient à son défaut sans emporter
les autres, et un fichier illisible rend simplement le formulaire à ses valeurs de départ. Ce
repli compte : une variante inconnue laissée telle quelle ferait retomber le sélecteur sur son
premier choix, `b0_pristine`, au lieu du prompt actif — une substitution silencieuse qui finirait
écrite dans `experience.yaml`.

## Onglet « 🗂️ Mes travaux »

Le suivi personnel de l'avancement : quelles fiches du plan sont réellement **faites**,
avec quel run, et le run collait-il au plan. Il croise deux sources en lecture —
le plan (`docs/paper/methode/experience_plan/experiments.yaml`) et les runs réels lus sur disque
via `experiences.lister()` — et écrit deux choses : l'état personnel dans
`scripts/dashboard/mes_travaux.yaml`, et, sur arbitrage, la fiche corrigée dans
`experiments.yaml`.

### Cocher = saisir la référence, pas juste marquer « fait »

Les fiches gardent la **présentation en cartes** du plan (titre, pastille de type, config).
Cocher une fiche **demande la référence de l'expérience réalisée** — sa date, au choix sous
la forme du dossier (`2026-09-07_14_35_03`) ou ISO (`2026-09-07T14:35:03+00:00`). Pas de
liste ni d'association automatique : on désigne explicitement le run. La référence retrouvée,
la **vérification fiche ↔ exécution** compare `model`, `temperature`, `seed` de la fiche à
ceux réellement joués (`execution.yaml` : `decideur.modele`, `…parametres.temperature`,
`sources_alea.graine_*`).

Les écarts **sautent aux yeux** — valeur fiche en :red[rouge], valeur run en :green[vert],
en gros. On tranche champ par champ :

- **Écraser la fiche** — la valeur du run est écrite dans `experiments.yaml` (round-trip
  ruamel calé sur le style du fichier : indentation de séquence à 4, `null` réémis, une
  seule ligne touchée par champ).
- **Rejeter** — un seul champ non écrasé et l'association est refusée : la fiche **ne se
  coche pas**. Pas de demi-validation silencieuse.

Sans écart, l'association se valide directement. Le **score composite L1** vient de
`scores.json` (`composite.l1`) et est figé sur la fiche — jamais saisi à la main.

`provider`, `instance`, `batch_size`, `max_parallel_requests` sont affichés mais **non
vérifiés** : absents d'`execution.yaml` ou de sémantique divergente (cf.
`specs/mes_travaux/questions.md`).

### Le ➕ à côté de chaque phase

Ajoute un **bloc de travail libre** rattaché à une phase (titre + description). Il est suivi
et associable à un run comme une fiche du plan, mais vit dans `mes_travaux.yaml`, pas dans
le plan canonique — de quoi tracer un travail hors des fiches prévues sans polluer
`experiments.yaml`.
