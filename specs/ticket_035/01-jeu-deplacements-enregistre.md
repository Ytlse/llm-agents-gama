# Spec 01 — Jeu de déplacements enregistré (ticket 035, `J`)

## Problème

Chaque expérience recalcule les itinéraires de toute la population alors qu'ils ne dépendent pas
de ce qu'on teste. Le seul mécanisme qui les mémorise aujourd'hui est un cache technique par
population, dont la clé embarque déjà le filtre véhicule et l'heure au pas de 10 minutes : il ne
peut ni être consulté, ni transporté, ni servir à une expérience qui n'a pas les mêmes réglages.
Il faut un objet de premier rang, préparé une fois, réutilisé partout.

## Utilisateurs

- **Le chercheur** : demande la préparation, consulte, copie d'une machine à l'autre, désigne le jeu
  dans une expérience ou dans `make run`.
- **Les deux modes d'exécution** (specs 03 et 04) : lecteurs exclusifs. Ils ne modifient jamais un jeu.
- **L'analyste** : relit un jeu cité par un résultat archivé, des mois plus tard.

## Règles métier

- **J1** — Un jeu est produit pour **une** population désignée par son nom **et** l'empreinte de son
  contenu (le `sha256` du `MANIFEST.yaml` pour une population scellée, celui du fichier sinon). Le jeu
  porte cette empreinte et dit si la population était scellée.
- **J2** — Le jeu couvre **tous les déplacements de la journée de toutes les personnes** de la
  population : un déplacement = (personne, activité d'origine, activité de destination, heure
  programmée de départ). Le nombre de déplacements attendus est **dérivé des agendas**, jamais saisi.
- **J3** — Pour chaque déplacement, le jeu contient **toutes les propositions que les moteurs savent
  produire**, tous modes confondus (marche, vélo, voiture, transports collectifs, train), **sans**
  le filtre de possession ou de position des véhicules, **sans** la condition de conducteur, **sans**
  le verrou de retour, et **sans** le plafond d'options appliqué aujourd'hui aux candidats.
- **J4** *(déduite)* — Une proposition enregistrée porte tout ce que le décideur lira d'elle (mode,
  itinéraire, durée, distance, description textuelle, profil de sécurité vélo le cas échéant) **et**
  tout ce dont le filtre d'éligibilité (spec 02) a besoin : mode principal, origine, destination,
  heure de départ et d'arrivée calculées.
- **J5** — Le jeu est **nommé** et **daté** ; le nom est libre, l'identité est l'empreinte de son
  contenu. Deux jeux de même contenu ont la même empreinte quel que soit leur nom ou la machine.
- **J6** — Le jeu est **consultable** sans lancer d'expérience : choisir une personne, voir ses
  déplacements de la journée, et pour chacun ses propositions.
- **J7** — Le jeu affiche sa **complétude** : déplacements couverts / attendus, personnes couvertes /
  total, et la liste des déplacements **sans aucune proposition** avec le motif rendu par les moteurs
  (aucun arrêt à portée, aucune correspondance dans la fenêtre, origine = destination…).
- **J8** — Un jeu incomplet reste utilisable mais **ne peut pas se présenter comme complet** : toute
  vue du jeu et tout résultat qui le consomme reprennent le taux de couverture de J7. Les
  déplacements sans aucune proposition sont dits **inexploitables** : un avertissement les compte à
  la préparation, et les expériences les excluent de leurs attendus (décision 3, 2026-09-06).
- **J9** — Le jeu déclare ses **dépendances** : identifiants et empreintes des données de réseau
  (feeds GTFS en service et graphe de routage), version des règles de routage (dépôt : commit),
  tables de congestion, date simulée pour laquelle les horaires ont été calculés. Un jeu **sans**
  dépendances déclarées est refusé au chargement.
- **J10** — **Péremption** : au lancement d'une expérience, si l'une des dépendances de J9 a changé
  par rapport à l'état courant du dépôt, l'utilisateur est averti **avant** l'exécution, avec la liste
  des dépendances qui diffèrent, et **décide**. Aucun rafraîchissement silencieux.
- **J11** — La **préparation** peut être interrompue et **reprise** : un déplacement dont les
  propositions sont déjà enregistrées n'est jamais recalculé ; la reprise dit combien restent.
- **J12** — Le jeu est **portable** : copié tel quel sur une autre machine, il se charge et sert ses
  propositions **sans aucun appel** aux moteurs de routage. Le chargement vérifie l'empreinte et
  refuse un jeu altéré.
- **J13** *(déduite)* — Le jeu est **inerte** : son chargement n'exécute aucun code contenu dans le
  fichier ; un jeu au contenu malformé est refusé avec la position de l'erreur.
- **J14** *(déduite)* — Un jeu est **immuable** après clôture de la préparation : aucune exécution
  n'y écrit ; corriger un jeu produit un nouveau jeu avec une nouvelle empreinte.
- **J15** *(déduite)* — La préparation journalise début, fin, durée, compteurs (déplacements
  calculés, sans proposition, ignorés) et **annonce le succès**. Une ALARME à front montant se lève si
  la part de déplacements sans proposition dépasse un seuil déclaré par la préparation.
- **J16** *(déduite)* — Le jeu ne contient **aucun** attribut personnel du persona au-delà de son
  identifiant : ce qu'il faut pour filtrer se lit dans la population, pas dans le jeu. Ainsi un même
  jeu sert des expériences qui n'ont pas le même filtre.

## Critères d'acceptation

- **J1** — Préparer un jeu pour `population_1000_AAMAS_v5` → le jeu porte le `sha256` de son
  `MANIFEST.yaml` et `scellée = oui` ; pour un fichier JSON nu → `sha256` du fichier, `scellée = non`.
- **J2** — Population à 3 personnes de 3, 2 et 1 activités → 3 déplacements attendus (2 + 1 + 0).
- **J3** — Personne sans vélo, sans permis, dont la voiture est ailleurs → le jeu porte quand même
  des propositions vélo et voiture pour ses déplacements ; un déplacement où OTP rend 9 motifs de
  transit → les 9 sont enregistrées, pas 6.
- **J4** — Toute proposition lue du jeu renseigne mode principal, origine, destination, départ,
  arrivée, et le texte rendu au décideur est **identique** à celui qu'aurait produit un calcul en vol
  (comparaison octet pour octet sur 100 déplacements).
- **J5** — Renommer le fichier ou le copier → empreinte inchangée ; modifier une durée → empreinte
  différente.
- **J6** — Consulter la personne `person_418` → ses déplacements dans l'ordre horaire, chacun avec
  le compte et la liste de ses propositions.
- **J7** — Jeu où 40 déplacements sur 2 579 n'ont aucune proposition → « 2 539 / 2 579 (98,4 %) »,
  et la liste des 40 avec motif.
- **J8** — Ouvrir un jeu à 98,4 % → la couverture est visible dans l'en-tête ; aucune vue ne dit
  « complet ».
- **J9** — Jeu dont le bloc de dépendances est absent → refus explicite au chargement.
- **J10** — Reconstruire le graphe OTP puis lancer une expérience sur l'ancien jeu → avertissement
  listant « graphe de routage » comme dépendance changée ; l'exécution attend la décision.
- **J11** — Interrompre la préparation à 50 % puis reprendre → aucun appel moteur pour les
  déplacements déjà couverts ; le journal dit « reste 1 290 ».
- **J12** — Copier le jeu dans un environnement sans OTP ni OSMnx → chargement et lecture réussis,
  0 appel réseau ; altérer un octet → refus.
- **J13** — Fichier tronqué → refus avec position ; aucun mécanisme de désérialisation exécutant du code.
- **J14** — Tenter d'écrire dans un jeu clos → refus ; « corriger » produit un second jeu.
- **J15** — Préparation terminée → une ligne de succès avec durée et compteurs ; 5 % sans proposition
  au-dessus du seuil → une ALARME, pas une par déplacement.
- **J16** — Le contenu du jeu ne porte ni âge, ni permis, ni possession de véhicule ; le filtre de la
  spec 02 s'exécute avec le jeu et la population comme seules entrées.

## Non-goals

- Pas d'amélioration des moteurs ni de la qualité des propositions (traité ailleurs).
- Pas de partage de propositions entre deux populations : un jeu = une population.
- Pas de propositions pour un autre jour que la journée programmée (voir question 3).
- Pas de suppression des caches techniques existants : ils restent internes et invisibles.

## Sécurité

- Un jeu copié depuis une autre machine est une **entrée hostile** : empreinte vérifiée, schéma validé,
  aucune exécution de code (J12, J13).
- La population est synthétique : aucune donnée personnelle réelle. Le jeu n'en ajoute pas (J16).
- Aucun secret (clé d'API, URL authentifiée) ne figure dans un jeu ni dans ses dépendances.

## Questions ouvertes

1. **Statut du jeu** (ticket §7.2) : artefact **scellé**, versionné et cité dans les résultats au même
   titre que la population — ou objet **régénérable** dont seule l'empreinte compte ? Cela décide si
   J10 avertit seulement ou si un jeu périmé est **refusé** pour une expérience destinée à l'article.
2. **Jeu incomplet** (ticket §7.3) : une expérience peut-elle démarrer sur un jeu dont la couverture
   est inférieure à 100 % ? Si oui, y a-t-il un plancher, et les déplacements non couverts sont-ils
   « sans décision » ou recalculés en vol (ce qui contredit le régime nominal de la spec 04) ?
3. **Déplacements du lendemain** : la simulation pré-calcule l'activité suivante par horizon glissant,
   y compris au-delà de minuit. Un jeu « d'une journée » doit-il porter ces propositions ? Sinon, le
   régime « zéro recalcul » de la spec 04 est inatteignable en fin de journée.
4. **Heure de référence des propositions** : l'heure programmée de départ (le comportement actuel :
   le contrôleur route en `arrive_by=False`, départ à `scheduled_start_time`) ou l'heure d'arrivée à
   l'activité ? Le jeu doit dire laquelle, et le filtre horaire de la spec 04 en dépend.
