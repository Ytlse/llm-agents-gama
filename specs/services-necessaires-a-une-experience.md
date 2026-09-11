# Spec — Démarrer les services Docker nécessaires à une expérience

## Problème

Une expérience s'exécute dans le conteneur `controller` et, quand son décideur est un modèle de
langage, s'appuie sur la passerelle. Depuis la suppression du volet « Commandes », les boutons
Docker ne vivent plus que dans l'onglet Métriques, et celui de l'onglet Expériences n'apparaît que
si `controller` manque précisément. On ne sait donc pas, en composant une expérience, de quoi elle
a besoin ni ce qui lui manque. Et `make up` réveille toute la pile, métrologie comprise, dont une
expérience n'a aucun usage.

## Utilisateurs

- **Le chercheur** qui compose et lance ses expériences depuis le tableau de bord, seul
  utilisateur, tous droits sur sa machine et sur Docker.

## Règles métier

- **R1** — Le formulaire dit, pour l'expérience courante, les services du compose qu'elle utilise
  et l'état de chacun. Le bloc reste visible même quand tout tourne : on doit savoir sur quoi on
  s'appuie, pas seulement ce qui manque.
- **R2** — Les services requis se déduisent des réglages de l'expérience : `controller` toujours ;
  la passerelle (`api`, `worker`) **seulement** pour un décideur « modèle de langage » ; les
  moteurs de routage (`otp1`, `otp2`, `otp3`, `osmnx1`) **seulement** quand un jeu reste à
  construire. Une heuristique, un tirage ou un rejeu n'attend rien de la passerelle.
- **R3** — Un bouton démarre exactement ces services, pas toute la pile. Il apparaît dès qu'il en
  manque un, ou quand l'état des services est inconnu.
- **R4** — Les services que le compose entraîne par dépendance sont nommés : sans quoi la page
  laisserait croire qu'elle démarre trois conteneurs quand elle en démarre huit.
- **R5** — La métrologie (`prometheus`, `grafana`, `cadvisor`, `node_exporter`, `flower`) n'est
  jamais démarrée par ce bouton, et la page le dit.
- **R6** — La cible `make up-services` refuse une liste de services vide, avec un code de retour
  non nul : sans cette garde, `docker compose up -d` sans argument démarrerait toute la pile,
  soit exactement ce que la cible existe pour éviter.
- **R7** *(déduite)* — Le graphe de dépendances est **lu dans le compose**, jamais recopié dans le
  code : il suit le fichier, y compris quand un service change de dépendances.
- **R8** *(déduite)* — La tuile « Services » de la vue d'ensemble porte un bouton de démarrage
  quand la pile est arrêtée ou incomplète, et dit que l'onglet Expériences démarre, lui, un
  sous-ensemble.
- **R9** *(déduite)* — La lecture du compose ne lance aucun sous-processus : elle ne doit pas
  ajouter une seconde d'attente à chaque affichage du formulaire.

### Rendre la RAM à la fin de l'expérience

- **R10** — Une case à côté de « Lancer » commande l'arrêt des services Docker **à la fin** de
  l'expérience. Décochée par défaut, elle nomme les services qu'elle arrêtera.
- **R11** — L'arrêt est **chaîné dans la commande lancée**, pas surveillé par la page : il a lieu
  même si le navigateur est fermé ou le tableau de bord arrêté. Une surveillance côté page ne
  marcherait que l'onglet ouvert, ce qui viderait la fonction de son intérêt — on coche
  précisément pour partir.
- **R12** — Les services arrêtés sont ceux que l'expérience utilise, **dépendances comprises** :
  c'est là qu'est la mémoire. Mesuré le 2026-09-07 : `osmnx1` 3,5 Gio, chaque OTP de 1,2 à
  1,5 Gio, `controller` 1,0 Gio, la passerelle 0,1 Gio. Arrêter la seule tête de chaîne ne
  rendrait presque rien.
- **R13** — `docker compose stop`, jamais `down` : conteneurs et volumes restent, le redémarrage
  ne recharge que ce qu'il faut. La métrologie, que le bouton de démarrage n'a pas lancée, n'est
  pas arrêtée ; `make down` reste la voie pour tout couper.
- **R14** — Le code de retour de l'expérience est conservé malgré l'arrêt qui suit : un échec
  reste un échec dans le journal du job.
- **R15** *(déduite)* — Rien n'est arrêté si le lancement n'a pas eu lieu : nom refusé, concurrent
  encore en cours, service manquant.
- **R16** *(déduite)* — Les trois cibles refusent une liste de services vide : `docker compose
  stop` sans argument arrêterait toute la pile, `up -d` la démarrerait entière.

## Critères d'acceptation

- **R1** — tout en marche → le bloc liste les services requis avec un voyant vert chacun, et
  aucun bouton ; `controller` arrêté → voyant éteint sur lui et bouton présent.
- **R2** — décideur `passerelle`, jeu clos → `controller`, `api`, `worker` ; décideur
  `duree_minimale`, jeu clos → `controller` seul ; décideur `aleatoire`, aucun jeu préparé →
  `controller` plus les quatre moteurs de routage.
- **R3** — clic sur le bouton → `make up-services SERVICES="controller api worker"` est lancé par
  le registre de jobs, et jamais `make up`.
- **R4** — services requis `controller api worker` → la page nomme `eqasim`, `osmnx1`, `otp1`,
  `otp2`, `otp3` et `redis` comme entraînés par dépendance.
- **R5** — quels que soient les réglages, aucun des cinq services de métrologie n'apparaît dans
  les services requis ni dans les entraînés.
- **R6** — `make up-services` sans `SERVICES=` → code de retour 2 et un message qui le dit, sans
  appeler `docker compose`.
- **R7** — le graphe est lu dans un fichier compose fabriqué pour le test, et une dépendance
  ajoutée dans ce fichier apparaît dans les services entraînés.
- **R8** — pile incomplète → la tuile « Services » offre un bouton de démarrage.
- **R9** — la lecture du compose n'appelle ni `subprocess` ni `docker`.

- **R10** — case présente, décochée, nommant les services dans son aide ; cochée puis
  « Lancer » → la cible chaînée est lancée avec `SERVICES=` renseigné.
- **R11** — la cible chaînée exécute l'expérience puis l'arrêt dans **une seule** commande, sans
  dépendre du tableau de bord.
- **R12** — décideur `passerelle`, jeu clos → les neuf services `controller api worker eqasim
  osmnx1 otp1 otp2 otp3 redis` sont arrêtés, et aucun des cinq de métrologie.
- **R13** — la commande contient `docker compose stop`, jamais `down`.
- **R14** — expérience qui échoue → le code de retour du job est celui de l'expérience, pas celui
  de l'arrêt.
- **R15** — lancement refusé pour concurrence → aucune cible d'arrêt lancée.
- **R16** — les trois cibles sans `SERVICES=` → code de retour 2 et un message qui le dit.

## Non-goals

- Ne pas démarrer la métrologie, ni le service `gama` du profil `offline` : le lancement avec
  simulateur s'en charge lui-même par `make run OFFLINE=1`.
- Ne pas arrêter les services autrement qu'à la fin d'une expérience, sur demande explicite :
  aucun arrêt automatique n'a lieu sans la case cochée.
- Ne pas remplacer `make up`, qui reste la voie pour démarrer toute la pile depuis la vue
  d'ensemble ou l'onglet Métriques.
- Ne pas vérifier la santé applicative d'un service : « en marche » veut dire que le conteneur
  tourne, pas que l'API répond. La disponibilité de la passerelle se lit ailleurs, sur
  `/health`.
- Ne pas deviner les besoins d'une expérience à partir de son fichier écrit : le bloc parle de ce
  qui est actuellement composé dans le formulaire.

## Sécurité

- Application locale, mono-utilisateur. Démarrer un conteneur n'est pas destructif ; aucun arrêt
  n'est déclenché par cette spec.
- La liste passée à `make` est **calculée**, jamais saisie : elle ne peut contenir que des noms de
  services de ce dépôt. Les variables partent en liste d'arguments, jamais dans un shell.
- La lecture du compose est un simple chargement YAML d'un fichier du dépôt, sans exécution.

## Questions ouvertes

Aucune : les trois questions ont été tranchées par la réponse du 2026-09-07 — sous-ensemble
nécessaire plutôt que toute la pile, bloc d'état toujours visible, bouton aussi dans la tuile de
la vue d'ensemble.
