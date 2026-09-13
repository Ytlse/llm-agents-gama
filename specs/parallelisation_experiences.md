# Spec — Parallélisation des expériences sous contrainte de RPM par clé API

Ticket 035 (plateforme d'expériences). Statut : implémentée le 2026-09-07 — `experiences/cles.py`,
`reservations.py`, `file.py`, `ordonnanceur.py` ; tests `tests/test_035_11_reservations.py`,
`tests/test_035_12_ordonnanceur.py` ; design § 11 de `docs/arch/plateforme-experiences.md`.

## Problème

Aujourd'hui les expériences ne se parallélisent pas de façon fiable : elles s'exécutent
toutes dans le même conteneur `controller`, et `experience-lancer-arret` arrête ce conteneur
en fin de run, tuant les autres expériences en cours. Même corrigé, on ne peut pas lancer
deux expériences n'importe comment : le débit LLM est plafonné **par clé API** côté
fournisseur, donc deux expériences qui partagent une clé se disputeraient le même quota (429,
épuisement) sans gain de débit. Il faut n'autoriser le parallèle que lorsque c'est réellement
gratuit en RPM.

## Utilisateurs

- **Opérateur de la plateforme** (l'exploitant, via le dashboard « Pilotage » ou le CLI
  `python -m experiences`) : définit, lance, arrête les expériences. Seul acteur ; pas de
  multi-tenant. Il a tous les droits sur les expériences et sur les services Docker locaux.

## Définitions

- **Jeu de clés d'une expérience** : ensemble des identités de clé API que l'expérience est
  susceptible de solliciter. Dérivé du **modèle** épinglé (granularité inchangée) :
  modèle → instances passerelle qui servent ce modèle → identité de clé de chaque instance.
- **Identité de clé d'une instance** : `PROVIDER_KEYS[nom_instance]` s'il existe, sinon
  `PROVIDER_KEYS[adapter]` (adapter = champ `adapter` ou, à défaut, le nom de l'instance).
  Deux instances ont la **même** identité de clé si elles résolvent la même entrée
  `PROVIDER_KEYS`. C'est l'identité (le nom de l'entrée), jamais la valeur secrète, qui sert.
- **Expérience active** : expérience qui **réserve** son jeu de clés — son exécution est dans
  un statut **non terminal** (`en_cours`, `en_pause`). Elle cesse d'être active, et libère ses
  clés, quand son exécution atteint un statut **terminal** (`terminee`, `arretee`, `epuisee`,
  `interrompue`).
- **Expérience en attente** : expérience soumise mais dont au moins une clé est réservée par
  une expérience active ; elle est placée en **file** et démarrée automatiquement plus tard.
- **Service partagé** : service Docker utilisé par plusieurs expériences (`controller`, `api`,
  `worker`, `redis`, `otp*`, `osmnx*`).

## Règles métier

- **R1** — Deux expériences peuvent être **actives en même temps** si et seulement si leurs
  jeux de clés sont **disjoints**.
- **R2** — Au lancement d'une expérience B, si le jeu de clés de B **intersecte** celui d'au
  moins une expérience active, B n'est **pas** démarrée : elle entre en **file d'attente**, en
  journalisant l'expérience et la (les) clé(s) qui la retiennent.
- **R3** — Si le jeu de clés de B est disjoint de ceux de toutes les expériences actives, B
  démarre immédiatement, en parallèle, sans arrêter ni ralentir les expériences en cours.
- **R2b** — Quand une expérience atteint un statut terminal et libère ses clés, la première
  expérience en attente (ordre **FIFO** de soumission) **dont le jeu de clés est désormais
  entièrement libre** est démarrée automatiquement. Plusieurs peuvent l'être si leurs clés le
  permettent. Une expérience en attente n'est jamais démarrée tant qu'une seule de ses clés
  reste réservée.
- **R2c** — Une expérience **active n'est jamais préemptée** (arrêtée ou ralentie) pour laisser
  passer une expérience en attente. La file ne fait qu'attendre des libérations naturelles.
- **R2d** — Au moment où une expérience en attente est promue (R2b), les **contrôles de
  lancement habituels** (fraîcheur du jeu, offre suffisante) sont rejoués. S'ils échouent,
  l'expérience n'est pas démarrée : elle **quitte la file** avec un motif journalisé, et
  n'immobilise pas les suivantes.
- **R2e** — L'opérateur peut **retirer** une expérience de la file avant qu'elle ne soit
  promue ; elle ne sera alors jamais démarrée automatiquement.
- **R4** — Le jeu de clés d'une expérience se dérive de son **modèle** épinglé, pas de son
  décideur ni de son gabarit : deux expériences sur des modèles qui partagent une clé
  (ex. deux modèles `adapter: google`) sont en conflit ; deux modèles à clés distinctes ne le
  sont pas.
- **R5** — `experience-lancer-arret` n'arrête un **service partagé** que si **toutes** les
  expériences sont terminées (aucune expérience active autre que celle qui vient de finir).
  S'il reste au moins une expérience active, les services partagés sont laissés en place et le
  fait est journalisé.
- **R6 (déduite)** — L'admission et la promotion (test de disjonction + réservation du jeu de
  clés) sont **atomiques** : deux lancements ou promotions simultanés portant sur une clé
  commune ne peuvent pas passer tous les deux ; l'un démarre, l'autre reste en file.
- **R7 (déduite)** — Le signal de libération d'une clé est le **statut terminal** de
  l'exécution. Pour que ce signal reste fiable, une exécution restée dans un statut non
  terminal alors que son **processus est mort** (panne, kill) est **réconciliée vers un statut
  terminal** (`interrompue`) — ce qui libère ses clés. Sans cette réconciliation, une exécution
  fantôme bloquerait sa clé et la file indéfiniment.
- **R12 (déduite)** — Quand l'état nécessaire pour établir de façon fiable les jeux de clés des
  expériences actives est **indisponible ou incohérent**, le système **ne démarre aucune
  expérience** (ni lancement direct, ni promotion depuis la file) : il attend, plutôt que de
  risquer deux runs sur la même clé (fail-safe).
- **R8 (déduite)** — Une expérience qui ne sollicite **pas** la passerelle (rejeu depuis
  artefact, décideur local sans clé) a un jeu de clés **vide** : elle est toujours
  parallélisable et n'entre jamais en conflit (R1 satisfaite par disjonction triviale).
- **R9 (déduite)** — Les instances **sans clé API disponible** (écartées par le filtrage du
  gateway) ne comptent pas dans le jeu de clés d'une expérience. Si, après filtrage, un modèle
  n'a aucune instance/clé disponible, le lancement relève du refus déjà existant (offre
  insuffisante), pas de cette spec.
- **R10 (déduite)** — Une **reprise** (`REPRENDRE=1`) est soumise aux mêmes règles d'admission
  qu'un lancement : mise en file si son jeu de clés est en conflit avec une expérience active.
- **R11 (déduite)** — Le motif de refus (R2) et les journaux ne contiennent **jamais** la
  valeur d'une clé : uniquement l'**identité** (nom de l'entrée `PROVIDER_KEYS` / de l'adapter).

## Critères d'acceptation

- **R1/R3** — A active sur modèle `mistral-small-latest` (clé `mistral`). Lancer B sur
  `gpt-oss-120b` (clé `cerebras`) → B démarre, A continue, les deux sont actives.
- **R2** — A active sur `gemini-3.5-flash` (clé `google`). Lancer B sur `gemini-3.6-flash`
  (clé `google`) → B **mise en file** (motif citant A et la clé `google`), A reste seule active.
- **R2b** — A (clé `google`) active, B en file sur `google`. A atteint un statut terminal → B
  démarre **automatiquement**. Si B et C sont toutes deux en file sur `google`, seule la
  première soumise (FIFO) démarre ; l'autre reste en file.
- **R2c** — B en attente sur `google` : lancer B ne provoque **jamais** l'arrêt de A.
- **R2d** — B en file ; entre-temps son jeu est devenu périmé. À la libération de la clé, la
  promotion échoue au contrôle de fraîcheur : B **quitte la file** avec un motif, une éventuelle
  C suivante peut être promue.
- **R2e** — B en file, retirée par l'opérateur → à la libération de la clé, B **n'est pas**
  démarrée ; une C suivante peut l'être.
- **R12** — État gateway indisponible au moment d'un second lancement ou d'une promotion →
  **aucun** démarrage n'a lieu ; l'expérience reste en attente, rien ne tourne en double.
- **R4** — Deux modèles distincts partageant l'adapter `google` sont détectés en conflit ;
  deux modèles d'adapters distincts (`google` vs `cerebras`) ne le sont pas — vérifié sans
  lancer réellement les runs (test unitaire sur la dérivation modèle → jeu de clés).
- **R5** — Deux expériences actives X et Y sur des clés disjointes. X se termine via
  `experience-lancer-arret ... SERVICES="controller api worker"` → `controller` (et les autres
  services partagés) **restent up** parce que Y est encore active ; un message le dit. Quand Y
  se termine à son tour de la même manière → les services sont arrêtés.
- **R6** — Deux `lancer` déclenchés simultanément sur le même modèle (clé commune) : exactement
  **un** démarre, l'autre part en file ; jamais deux actifs sur la même clé.
- **R7** — Une exécution `en_cours` dont le PID lanceur n'existe plus est réconciliée en
  `interrompue` ; ses clés sont libérées ; une expérience en file sur la même clé démarre.
- **R8** — Un rejeu depuis artefact (aucun appel passerelle) lancé pendant qu'une expérience
  passerelle est active sur n'importe quelle clé → démarre en parallèle.
- **R9** — Modèle dont toutes les instances sont sans clé disponible : le jeu de clés calculé
  est vide ; l'échec éventuel est le refus « offre insuffisante » préexistant, pas un conflit.
- **R10** — A active sur clé `google`. `experience-reprendre` d'une expérience B en pause dont
  le modèle est aussi sur `google` → mise en file ; démarrée quand A libère `google`.
- **R11** — Inspecter le motif de mise en file et les lignes de journal d'un conflit : ils
  citent `google` (identité) et aucune sous-chaîne de la valeur secrète.

## Non-goals

- **Pas de sous-partage dynamique du RPM d'une même clé** entre deux expériences (pas de
  demi-quota chacune) : une clé est soit libre, soit prise en entier.
- **Pas de priorité ni de préemption** : la file est purement **FIFO** ; une expérience active
  n'est jamais interrompue pour laisser passer une expérience en attente (R2c). Une expérience
  longue sur une clé « chaude » peut donc retarder les suivantes — c'est assumé, l'opérateur
  voit la file.
- **Pas de changement de la granularité de réservation** : elle reste le **modèle** (pas
  d'épinglage à un sous-ensemble d'instances/clés d'un même modèle).
- **Pas de modification du parallélisme intra-expérience** (`regroupement.parallelisme`) : il
  reste inchangé et indépendant de cette spec.
- **Pas d'admission fondée sur le TPM, le rpd ou l'épuisement courant d'une clé** : seul le
  partage d'**identité de clé** décide parallèle/série. Une clé épuisée reste « prise » par son
  expérience tant que celle-ci est active.
- **Pas d'orchestration de GAMA** : le mode simulateur reste hors plateforme (déjà refusé).

## Sécurité

- **Données sensibles** : les valeurs des clés API (`PROVIDER_KEYS`, providers.yaml). Elles ne
  transitent pas par cette fonctionnalité et n'apparaissent ni dans les motifs de refus, ni
  dans les journaux, ni dans les fichiers d'exécution (R11) — seule l'identité de clé circule.
- **Acteur unique de confiance** : l'opérateur local ; pas d'élévation de privilège, pas de
  frontière multi-utilisateur à défendre.
- **Entrées hostiles par défaut** : la réponse du gateway (`GET /health`) et les fichiers
  `providers.yaml` / `etat.json` lus pour établir les jeux de clés et le statut des exécutions
  sont traités en données, jamais en instructions ; un état indisponible ou malformé ne doit
  pas faire démarrer deux expériences en conflit (R12, fail-safe).
- **Réservation locale** : l'atomicité de R6 s'appuie sur un mécanisme local (le lanceur et le
  dashboard tournent sur la même machine) ; aucune donnée sensible n'y est stockée.

## Questions ouvertes

_(Aucune bloquante : les trois arbitrages structurants — file d'attente auto, fail-safe sur
état indisponible, libération au statut terminal — sont tranchés. Points de confirmation
mineurs, décidés par défaut dans la spec, à infirmer si besoin :)_

1. **Ordre de la file = FIFO** de soumission, sans priorité ni préemption (R2b/R2c). À
   confirmer : est-ce le bon défaut, ou faut-il pouvoir réordonner la file ?
2. **Promotion périmée (R2d)** : une expérience dont le jeu devient périmé pendant l'attente
   **quitte la file** (plutôt que d'être relancée avec `ACCEPTER_PERIME` automatiquement). À
   confirmer.
