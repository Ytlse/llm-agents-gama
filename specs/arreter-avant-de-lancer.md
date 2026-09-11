# Spec — Arrêter ce qui tourne avant de lancer

## Problème

Cliquer « Lancer » alors qu'une exécution tourne encore met deux runners en concurrence sur le
même quota LLM et le même contrôleur. Le cas est courant parce qu'une exécution peut survivre à
ce qui l'a lancée : son `docker compose exec` tué sur l'hôte ne tue pas le processus dans le
conteneur, et son `etat.json` reste « en cours ». Rien, aujourd'hui, ne signale ces survivants au
moment du lancement.

## Utilisateurs

- **Le chercheur** qui relance une expérience depuis le tableau de bord, seul utilisateur, tous
  droits. Il veut que le lancement parte seul, sans concurrent, sans aller chasser des processus.

## Règles métier

- **R1** — Avant de lancer, le formulaire dit ce qui tourne et entrerait en concurrence : les
  exécutions à l'état « en cours », **quelle que soit l'expérience**, et les jobs de la session
  qui lancent ou reprennent une exécution, ou un run GAMA.
- **R2** — La **construction d'un jeu n'est jamais arrêtée** et ne compte pas comme concurrente :
  elle ne consomme pas de quota LLM, son produit est précisément ce que le lancement attend, et
  l'interrompre jetterait une heure de calcul.
- **R3** — Une case cochée d'avance, visible seulement quand quelque chose tourne, commande
  l'arrêt avant le lancement. Décochée, « Lancer » se comporte comme avant.
- **R4** — L'arrêt d'une exécution est **coopératif** : un fichier `STOP` dans son dossier,
  honoré en quelques secondes (délai de grâce aux sollicitations en vol, puis abandon), résultat
  partiel exploitable. Aucun processus n'est tué dans le conteneur : un `pkill` laisserait l'état
  à « en cours » pour toujours et perdrait la garantie du point sûr.
- **R5** — L'arrêt des jobs de la session passe par le registre : signal au groupe de processus,
  puis signal fort après cinq secondes, comme « Tout arrêter ».
- **R6** — Le lancement attend que les exécutions arrêtées quittent l'état « en cours », trente
  secondes au plus, avec un indicateur d'attente. Passé ce délai, le lancement est **refusé** et
  son motif nomme les exécutions encore en cours.
- **R7** — La page écrit ce qui a été arrêté, exécution par exécution et job par job.
- **R8** *(déduite)* — Sans rien qui tourne, aucune case n'apparaît et le lancement est inchangé.
- **R9** *(déduite)* — Une exécution `terminee`, `arretee`, `epuisee` ou `en_pause` n'est jamais
  touchée : seule celle qui tourne entre en concurrence.
- **R10** *(déduite)* — Un arrêt demandé n'est jamais silencieux : même quand le lancement est
  refusé, la page dit ce qui a été arrêté. Sinon on relancerait sans savoir que le quota a déjà
  été rendu.

### Ce qui est mort n'est pas concurrent, et reste reprenable

- **R11** — Une exécution n'est concurrente que si elle **écrit encore** sa progression. Rester
  sur « en cours » dans `etat.json` ne suffit pas : l'arrêt étant coopératif, un runner tué laisse
  cet état pour toujours. Sans ce filtre, le tableau de bord écrit un `STOP` dans une exécution
  déjà morte ; la reprise suivante l'honore et clôture l'exécution en « arrêtée », donc **non
  reprenable**, avec ses décisions payées dedans. C'est arrivé le 2026-09-07 sur 209 décisions.
- **R12** — Une exécution est **reprenable** si elle est en pause, épuisée, ou restée « en cours »
  sans écriture depuis plus de dix minutes. Le bouton « Reprendre » accepte les trois : sans le
  troisième cas, la page n'offre aucun chemin propre après un runner tué, seulement « Rejouer »,
  qui repaie tout.
- **R13** — Quand une exécution reprenable existe pour l'expérience composée, « Lancer » l'annonce
  avant d'agir, en nommant l'exécution, son état et le nombre de décisions déjà archivées : il en
  créerait une deuxième et repaierait ces décisions.
- **R14** — Un démon Docker qui ne répond pas est nommé comme tel, avec le geste qui le répare,
  plutôt que laissé à l'erreur brute de Docker dans un journal de job.

## Critères d'acceptation

- **R1** — une exécution `en_cours` d'une AUTRE expérience et un job `root:experience-lancer`
  actif → les deux sont nommés dans la case ; un job `root:up` actif → absent de la liste.
- **R2** — un job `root:jeu` actif et un jeu non clos → absents de la liste des concurrents, et
  l'arrêt ne les touche pas.
- **R3** — rien en cours → aucune case dans la page ; une exécution en cours → case présente et
  cochée ; décochée puis « Lancer » → aucun `STOP` écrit, le lancement part.
- **R4** — arrêt demandé → un fichier `STOP` apparaît dans le dossier de l'exécution, et rien
  d'autre n'est exécuté ; aucun appel `pkill` ni `docker` n'est émis.
- **R5** — un job concurrent actif → le registre est appelé pour l'arrêter, et le job n'est plus
  en cours.
- **R6** — exécution qui reste `en_cours` au-delà du délai → lancement refusé, motif nommant
  l'expérience et l'exécution, aucune cible `make` lancée ; exécution qui passe à `arretee`
  pendant l'attente → le lancement part.
- **R7** — après un arrêt suivi d'un lancement, la page liste « arrêté : … » pour chaque
  exécution et chaque job.
- **R8** — rien en cours → le clic sur « Lancer » appelle la même cible qu'avant, sans détour.
- **R9** — exécutions `terminee` et `en_pause` sur le disque → aucun `STOP` écrit pour elles.
- **R10** — lancement refusé après un arrêt → le message contient à la fois les lignes
  « arrêté : … » et le motif du refus.

- **R11** — exécution « en cours » dont la progression date de 20 minutes → absente des
  concurrents, et aucun `STOP` ne lui est écrit ; progression de 10 secondes → concurrente.
- **R11** — exécution « en cours » sans fichier de progression mais dont `etat.json` vient d'être
  écrit → concurrente : une exécution qui vient de naître n'a pas encore de progression.
- **R12** — états `en_pause`, `epuisee`, et `en_cours` sans écriture depuis 20 minutes →
  reprenables ; `en_cours` fraîche, `terminee` et `arretee` → non reprenables.
- **R13** — une exécution en pause avec 209 décisions archivées → un avertissement nomme
  l'exécution, son état et les 209 décisions avant que « Lancer » soit cliqué.
- **R14** — état des services inconnu → le message nomme le démon Docker et dit d'ouvrir Docker
  Desktop.

## Non-goals

- Ne tuer aucun processus dans le conteneur : pas de `pkill`, l'arrêt reste coopératif.
- Ne pas arrêter la construction d'un jeu, ni aucun job d'une autre nature (`up`, `down`,
  `report`, `synthesis`, `providers`…).
- Ne pas reprendre automatiquement ce qui a été arrêté : une reprise est un clic explicite.
- Ne pas remplacer `make stop-run`, qui reste la voie dédiée pour un run GAMA headless.
- Ne pas attendre indéfiniment : le lancement est refusé plutôt que suspendu.

## Sécurité

- Un arrêt détruit du travail en vol, dont des sollicitations LLM déjà payées. Il est donc gardé
  par une case **visible** qui nomme ce qu'elle arrêtera, et ce qui a été arrêté est écrit après
  coup.
- Le résultat partiel d'une exécution arrêtée reste exploitable : c'est la plateforme qui le
  garantit, à condition de passer par le point sûr, donc par `STOP` et non par un signal. Le
  délai d'attente de R6 (trente secondes) couvre largement le délai de grâce laissé aux
  sollicitations en vol (15 s).
- Le tableau de bord n'écrit qu'un fichier `STOP` dans un dossier d'exécution existant, et
  n'appelle le registre que sur des jobs qu'il a lui-même lancés.

## Questions ouvertes

Aucune : les trois questions ont été tranchées par le GO du 2026-09-07, chacune sur le défaut
proposé — case cochée d'avance, toutes les expériences, trente secondes puis refus.
