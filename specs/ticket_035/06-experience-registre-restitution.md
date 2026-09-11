# Spec 06 — Expérience, registre, restitution (ticket 035, `E`)

## Problème

On ne sait pas retrouver ce qui a été lancé, ni comparer deux exécutions qui ne diffèrent que par
le décideur, ni dire d'un résultat quelle part des déplacements il couvre. Un run est un dossier daté
dont la configuration est éparpillée (`scenario_params.yaml`, `static_config.yaml`, variables
d'environnement) et dont la population est identifiée par un nom de fichier. La version précédente
du ticket a de plus recopié des valeurs de référence qui n'existent nulle part.

## Utilisateurs

- **Le chercheur** : définit, duplique, estime, lance, retrouve, compare, ouvre le détail.
- **L'analyste** (le même, des mois plus tard, ou un relecteur) : relit un résultat sans le code qui
  l'a produit.
- **Les outils aval** (synthèse, export vers l'article) : lisent les chiffres sans ressaisie.

## Règles métier

### Définir et identifier

- **E1** — Une expérience est définie par : population, jeu de déplacements, gabarit de prompt,
  décideur (modèle + paramètres), mode d'exécution, politique de calendrier, horizon en jours,
  mémoire (activée ou non), événements éventuels, graine d'ordre des propositions, graine de tirage
  de mode, régime de regroupement demandé, tolérances horaires (spec 04, G5). Tout champ absent est
  une **erreur**, jamais un défaut implicite.
- **E2** — **Toute population est admissible.** Scellée ou non ; le résultat dit laquelle des deux
  situations s'appliquait, et porte l'empreinte dans les deux cas (spec 01, J1).
- **E3** — **Tout élément désigné porte son empreinte** : population, jeu, gabarit (empreinte du texte
  effectif du prompt système et du gabarit de rendu), décideur (modèle, version déclarée, paramètres),
  et la version du dépôt (commit, arbre propre ou non). Les **noms** sont des commodités d'affichage.
- **E4** — **Réplication.** Dupliquer une expérience reprend tous ses champs ; l'utilisateur en change
  un ou plusieurs et la nouvelle expérience cite celle dont elle dérive.
- **E5** — **Estimation avant lancement** : nombre de sollicitations du décideur, jetons attendus en
  entrée et en sortie, durée prévisionnelle, et part des quotas disponibles. Chaque valeur cite sa
  **source** : nombre de déplacements dérivé du jeu ; jetons par déplacement mesurés sur les
  exécutions archivées du même gabarit (à défaut, les ratios mesurés déclarés dans le plan
  d'expériences, cités) ; quotas lus dans la configuration et l'état courant de la passerelle.
  **Aucune** valeur littérale n'est écrite dans la plateforme.
- **E6** — **Refus explicite** avant lancement, avec la raison et l'action à mener, pour : empreinte
  de population du jeu différente de la population ; décideur sans instance disponible ; mode sans
  simulateur avec mémoire, événement ou horizon > 1 (spec 03, S3) ; date hors période couverte par
  les données (E9) ; jeu périmé refusé selon la question 1 de la spec 01.

### Temps et calendrier

- **E7** — L'horizon est un entier de jours ≥ 1.
- **E8** — Trois politiques de date, exclusives : **commune** (une date pour toute la population, qui
  avance ensemble), **propre** (une date par personne, qui avance individuellement — le tirage actuel
  par personne, graine déclarée), **aléatoire** (un jour ouvré représentatif tiré par personne dans la
  période de référence, graine déclarée). Une expérience portant un événement **exige** la politique
  commune ; sinon refus (E6).
- **E9** — Une date hors de la période couverte par les données de transport (feeds en service), de
  météo ou de congestion est **refusée** ou **signalée** avant lancement, jamais décalée en silence ;
  le résultat porte les périodes couvertes qu'il a lues.

### Résultats et archive

- **E10** — **Archivage systématique.** Toute exécution, terminée, interrompue, épuisée ou arrêtée,
  produit un ensemble rangé et daté contenant : la configuration complète (E1) et toutes les
  empreintes (E3), la trace de chaque décision (spec 02, D6), le régime de regroupement appliqué
  (spec 03, S5), les sources des propositions (spec 04, G6), l'historique des interruptions (spec 05,
  Q6), la couverture (E14), et les compteurs de fin.
- **E11** — **Relecture ultérieure.** L'archive se relit **sans le code qui l'a produite** : elle porte
  sa propre description de champs, et un lecteur qui ignore un champ inconnu ne casse pas. Ce qui a été
  présenté au décideur — texte complet — en fait partie.
- **E12** — **Registre.** Une vue de toutes les expériences et de leurs exécutions : nom, date, état
  (définie, en cours, en pause, épuisée, arrêtée, terminée), décideur, gabarit, mode, couverture,
  résultats principaux ; triable et filtrable sur chacun de ces champs.
- **E13** — **Comparabilité.** Deux exécutions sont **comparables** si et seulement si les empreintes
  de tout ce qu'elles partagent sont identiques (population, jeu, gabarit si commun, politique de
  calendrier et graines, tolérances, régime de regroupement — selon la question 2). La comparaison
  côte à côte d'exécutions non comparables est **refusée**, ou affichée avec la liste des éléments qui
  diffèrent en tête et une mention « non comparable ». Jamais sur la foi de noms ou de dates.
- **E14** — **Couverture.** Tout chiffre affiché (part modale, score, classement) est accompagné de
  la part des déplacements attendus qu'il couvre effectivement : décidés / attendus **exploitables**
  (les déplacements sans aucune proposition des moteurs sont exclus du dénominateur et leur nombre
  est affiché à côté — décision 3 du 2026-09-06). Un résultat
  partiel ne peut jamais être présenté comme complet ; dans un classement, une ligne à couverture
  incomplète est visuellement distinguée et **non classée** par défaut.
- **E15** — **Détail au clic.** Depuis le registre : exécution → personne → déplacement → trace de
  décision complète (présentées, écartées et motifs, réponse brute, source des propositions, souvenirs
  présentés, période par rapport à l'événement).
- **E16** — **Restitution.** Chaque résultat a une page de synthèse consultable, et **toutes** les
  valeurs qu'elle affiche sont aussi disponibles dans un fichier de données lisible par un script,
  avec le même chemin de calcul : la page ne calcule rien que le fichier n'ait.
- **E17** — **Référentiel non recopié.** La plateforme ne détient **aucune** valeur d'enquête. Toute
  comparaison à l'enquête lit `scripts/data/population/cerema_values.yaml` (ou la source qu'un
  manifeste désigne) et cite **chemin + empreinte** de la source à côté des chiffres. Un test vérifie
  qu'aucun littéral de part modale ne figure dans le code de la plateforme.
- **E18** — **Reproductibilité déclarée.** Chaque résultat liste ses sources d'aléa : graine d'ordre,
  graine de tirage de mode, graine de date, échantillonnage du décideur (un modèle de langage n'est
  pas déterministe même à température 0 : déclaré comme tel). Rejouer une exécution avec le décideur
  de rejeu (spec 02) redonne un résultat identique ; relancer avec le décideur réel produit une
  **nouvelle exécution**, jamais une écrasure.
- **E19** *(déduite)* — **Immutabilité.** Une archive clôturée ne se modifie pas ; une ré-analyse
  écrit à côté et cite l'archive. Un fichier de l'archive altéré est détecté au chargement.
- **E20** *(déduite)* — **Le registre survit à la suppression.** Une exécution dont le dossier a
  disparu reste listée avec l'état « archive manquante », jamais retirée en silence.
- **E21** *(déduite)* — **Aucun secret dans l'archive.** Ni clé, ni URL authentifiée, ni contenu
  d'environnement ; les instances de passerelle sont nommées, pas décrites.
- **E22** *(déduite)* — **Nombre de déplacements attendus dérivé.** Il est calculé depuis les agendas
  de la population (spec 01, J2) au moment de la définition, jamais saisi ni copié d'un document.

## Critères d'acceptation

- **E1** — Définir une expérience sans tolérances horaires → erreur nommant le champ ; aucune valeur
  par défaut n'est substituée.
- **E2** — Population non scellée → expérience acceptée, résultat « scellée : non », empreinte du fichier.
- **E3** — Modifier un caractère du prompt système actif → empreinte de gabarit différente, même nom ;
  deux expériences aux gabarits de noms différents mais textes identiques → même empreinte.
- **E4** — Dupliquer et ne changer que le décideur → tous les autres champs et empreintes identiques ;
  la nouvelle expérience cite l'ancienne.
- **E5** — Estimation d'une expérience de 2 579 déplacements en lots de 10 sur une instance à
  500 requêtes/jour → « ~258 sollicitations (source : jeu), ~52 % du quota (source : passerelle) »,
  jetons cités avec leur source ; changer la limite dans la passerelle change l'estimation.
- **E6** — Chaque cas listé → refus avant lancement avec raison et action ; aucune exécution créée.
- **E7** — Horizon 0 → refus.
- **E8** — Événement + politique « propre » → refus ; politique « aléatoire », graine 42, relancée →
  mêmes dates tirées.
- **E9** — Date commune hors des feeds en service → refus citant la période couverte ; aucune date
  décalée.
- **E10** — Exécution arrêtée à 60 % → archive complète des dix éléments listés ; l'un manquant →
  archive invalide au chargement.
- **E11** — Charger une archive avec un champ inconnu ajouté → lecture réussie ; le texte présenté au
  décideur est présent pour chaque décision.
- **E12** — Registre trié par couverture puis filtré sur « décideur = gemini-3.1 » → lignes attendues.
- **E13** — Deux exécutions de même population, même jeu, décideurs différents → comparables ; jeux
  d'empreintes différentes → « non comparable », liste des différences en tête.
- **E14** — Résultat à 98,4 % → chaque chiffre porte « 2 539 / 2 579 » ; dans le classement, la ligne
  est distinguée et sans rang.
- **E15** — Parcours registre → `person_418` → déplacement 2 → trace complète affichée.
- **E16** — Toute valeur de la page se retrouve à l'identique dans le fichier de données ; test de
  correspondance exhaustive.
- **E17** — Grep sur le code de la plateforme : aucun littéral de part modale ; la page cite
  `cerema_values.yaml` et son empreinte ; modifier le fichier change les cibles affichées.
- **E18** — Résultat → liste de quatre sources d'aléa ; relance réelle → nouvelle exécution, l'ancienne
  intacte.
- **E19** — Modifier un octet d'une archive → détection au chargement.
- **E20** — Supprimer le dossier d'une exécution → registre « archive manquante ».
- **E21** — Grep des clés connues sur toute archive produite en test → 0 occurrence.
- **E22** — Population de test à 3 personnes → « 3 déplacements attendus » calculés, sans champ saisi.

## Non-goals

- Pas de valeurs de référence ni de seuils scientifiques dans la plateforme : elle lit, ne fixe pas,
  ne juge pas ce qu'est un bon score.
- Pas de plan d'expériences : ce qu'on cherche à mesurer relève du plan, la plateforme le déroule.
- Pas de gestion multi-utilisateurs ni de droits : un chercheur, une machine.
- Pas de migration des archives existantes (`experiments/archive/*`) vers la nouvelle forme ; elles
  restent lisibles par leurs outils actuels.
- Pas de maquette imposée : la maquette HTML du ticket est une référence ergonomique, pas un critère.

## Sécurité

- Les textes archivés (raisonnements du décideur, articles, messages d'erreur) sont **hostiles** :
  échappés à l'affichage, jamais interprétés.
- Une archive ou un jeu venus d'ailleurs sont validés avant lecture (empreintes, schéma).
- Aucun secret n'entre dans une archive, un registre ou une page (E21).
- La population est synthétique : aucune donnée personnelle réelle ; les articles de presse cités
  sont référencés par chemin et empreinte, pas recopiés dans les pages publiées.

## Questions ouvertes

1. **Réplication** (ticket §7.7) : combien d'exécutions par expérience, et le registre les gère-t-il
   comme un **ensemble** (moyenne, dispersion) ou comme des exécutions indépendantes ?
2. **Régime de regroupement dans la comparabilité** (ticket §7.6, spec 03) : E13 doit-il exiger le
   même régime S5 pour déclarer deux exécutions comparables ?
3. **Unité de sollicitation** (ticket §7.1) : elle décide de la formule de E5 et de la forme de la
   trace D6 (une réponse par déplacement, ou une réponse par personne à découper).
4. **Résultats principaux du registre** : quelles grandeurs figurent dans la ligne (parts modales
   agrégées aux quatre modes canoniques ? score composite du moteur de synthèse ?) — la plateforme les
   affiche, elle ne les définit pas ; il faut désigner la source qui les définit.
