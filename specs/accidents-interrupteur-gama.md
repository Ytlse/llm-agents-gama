# Interrupteur d'accidents dans GAMA

> Ticket 070. Spécifie **l'interrupteur et ce qu'il commande**. Livré : l'existence des
> accidents et l'interrupteur (2026-09-14), la loi conditionnée BAAC (R14 à R19, même jour),
> le **retard subi et ses deux gardes de cache** (R8 à R10) ainsi que la **pose manuelle**
> (2026-09-15). Reste hors périmètre le **souvenir** du retard, qui demande que l'information
> remonte du routage jusqu'à l'agent et touche une chaîne mémoire en cours de refonte.

## Problème

La simulation ne sait pas produire d'incident routier : rien ne perturbe un déplacement une
fois l'itinéraire calculé. L'expérimentateur n'a donc aucun moyen de faire subir un retard à
une population d'agents, ni par tirage au sort ni à la main. Il manque d'abord le commutateur
qui décide si ce régime est actif pour un run, et la garantie qu'un run archivé dise lequel
des deux régimes il a connu.

## Utilisateurs

- **L'expérimentateur devant l'IHM GAMA** : coche ou décoche l'interrupteur avant de lancer,
  comme il le fait déjà pour la mémoire long terme. C'est le seul acteur qui décide.
- **Le contrôleur Python** : reçoit l'état de l'interrupteur au `/init` et l'applique au run.
  Il ne le décide jamais lui-même.
- **Le lecteur d'un run archivé** (humain ou script d'analyse) : lit `scenario_params.yaml`
  et doit pouvoir dire sans ambiguïté si les accidents étaient actifs.

## Règles métier

- **R1** — L'IHM GAMA expose un interrupteur booléen « Accidents sur les axes », dans la
  catégorie `Simulation`, à côté des interrupteurs de mémoire existants.
- **R2** — L'interrupteur vaut **vrai par défaut** (décision du 2026-09-15). Le régime
  réaliste est l'ordinaire ; c'est sa désactivation qui demande un geste explicite. Un
  `sim_params.yaml` antérieur, qui ne porte pas la clé, active donc les accidents.
- **R20 (déduite)** — Tout ticket dont la réalisation passe par un run GAMA porte un
  avertissement sur l'état de ce paramètre. Un régime actif par défaut qui ne serait signalé
  nulle part ferait attribuer ses effets à la mesure en cours.
- **R3** — L'état de l'interrupteur est persisté dans `config/sim_params.yaml` et rechargé au
  démarrage de GAMA, comme les autres paramètres de scénario.
- **R4** — L'état de l'interrupteur est transmis au contrôleur dans la charge utile du
  `/init`, sous la clé `accidents_enabled`.
- **R5** — L'état **effectif** du run est écrit dans `scenario_params.yaml` du répertoire
  d'expérience, toujours, y compris lorsqu'il vaut faux.
- **R6** — Interrupteur à faux : aucun accident n'est tiré, aucune durée d'itinéraire n'est
  modifiée, et le cache d'itinéraires fonctionne comme aujourd'hui.
- **R7** — Interrupteur à vrai : à chaque journée simulée, un nombre d'accidents est tiré,
  chacun posé sur une arête du graphe routier, avec un instant de début et une durée.
- **R14** — Le NOMBRE d'accidents d'une journée suit une loi de Poisson dont le taux est le
  taux mesuré, multiplié par le facteur du jour de semaine.
- **R15** — L'HEURE d'un accident suit la distribution horaire mesurée, jamais l'uniforme.
- **R16** — La CLASSE DE VITESSE de l'axe suit la distribution mesurée ; l'arête est ensuite
  tirée au prorata de sa longueur **à l'intérieur de cette classe**.
- **R17** — La météo **ne conditionne pas** l'accidentalité (décision du 2026-09-21) : le
  facteur vaut 1 et le jour du bulletin ne change rien au tirage. Le garde-fou reste en place —
  un facteur n'est appliqué que s'il est déclaré établi — mais son absence n'est plus un
  chantier en attente, c'est une limite assumée.
- **R18 (déduite)** — Une loi dont une distribution ne somme pas à 1, ou dont un facteur n'a
  pas pour moyenne 1, est refusée au chargement. Sans ce contrôle, le taux moyen du run
  serait déplacé sans qu'aucun journal ne le dise.
- **R19 (déduite)** — Une classe présente dans la loi mais absente du graphe est signalée au
  chargement, et sa masse redistribuée sur les classes disponibles. Un accident destiné à un
  réseau inexistant ne peut pas être posé en silence.
- **R8** — Un déplacement en voiture dont l'itinéraire calculé emprunte une arête portant un
  accident actif à l'instant du départ subit une **durée allongée**.
- **R9 (déduite)** — Aucun itinéraire calculé alors qu'un accident est actif n'entre dans le
  cache d'itinéraires, et aucun n'est servi depuis ce cache. Sans cette règle, une durée
  perturbée serait resservie à des runs qui n'ont demandé aucun accident — le cache est
  adressé sans la date.
- **R10 (déduite)** — La clé du cache de décisions LLM porte l'état d'accident du déplacement.
  Sans cela, un agent retardé se voit resservir la décision qu'il avait prise sans le retard :
  la clé est construite sur les codes d'options, insensibles aux durées.
- **R21** — L'expérimentateur peut **poser** un accident choisi : un point, une heure, une
  durée. L'accident posé entre dans le même registre et suit exactement le même chemin qu'un
  accident tiré. Une pose dans un run où le régime est décoché est **refusée et journalisée**.
- **R11 (déduite)** — À chaque journée simulée, le journal indique le nombre d'accidents tirés
  et le nombre de déplacements touchés, **y compris quand ces nombres valent zéro**. Sans ce
  compteur, « aucun effet » et « aucun accident » sont indiscernables.
- **R12 (déduite)** — Un accident posé sur une arête absente du graphe, ou dont la durée est
  nulle ou négative, est refusé à la pose avec un message nommant l'arête et la valeur, et
  n'entre jamais dans l'état du monde.
- **R13 (déduite)** — Changer l'interrupteur ne change pas la population, l'agenda ni la météo
  du run : deux runs identiques ne différant que par l'interrupteur restent comparables.

## Critères d'acceptation

| Règle | Entrée | Sortie attendue |
|---|---|---|
| R1 | Ouvrir l'expérience dans l'IHM GAMA | Le paramètre « Accidents sur les axes » apparaît sous `Simulation` |
| R2 | `sim_params.yaml` absent, démarrage | `accidents_enabled` vaut `true` |
| R20 | Lire un ticket ouvert qui lance un run GAMA | Il porte l'avertissement sur `accidents_enabled` |
| R3 | Cocher, lancer, quitter, rouvrir GAMA | L'interrupteur est toujours coché |
| R4 | Lancer avec l'interrupteur coché | La requête `/init` contient `accidents_enabled: true` |
| R5 | Lancer avec l'interrupteur décoché | `scenario_params.yaml` contient `accidents_enabled: false` |
| R6 | Run complet, interrupteur à faux | Zéro accident tiré ; durées d'itinéraire identiques à un run de référence sans la fonctionnalité |
| R7 | Run d'une journée, interrupteur à vrai, loi forcée à 3 | 3 accidents dans l'état du monde, chacun avec arête, début et durée |
| R14 | Vendredi (×1,188) contre dimanche (×0,833) | Le taux conditionné du vendredi est strictement supérieur |
| R15 | 60 journées simulées à taux élevé | La part d'accidents à 17 h dépasse trois fois celle de 3 h |
| R16 | Réseau à 58 % en zone apaisée, 34 % en urbain | Moins de 20 % des accidents en zone apaisée ; l'urbain domine |
| R17 | Même jour, avec et sans « pluie forte » | Taux identiques : la météo ne conditionne pas le tirage |
| R18 | Loi dont la distribution horaire somme à 0,24 | `ValueError` au chargement, aucun tirage |
| R19 | Loi portant une classe absente du graphe | Alarme au chargement ; la masse va aux classes présentes |
| R8 | Itinéraire voiture traversant une arête avec accident actif au départ | Durée rendue strictement supérieure à la durée du même itinéraire sans accident |
| R9 | Deux calculs du même itinéraire, l'un pendant un accident actif | Aucune entrée ajoutée au cache pour le calcul perturbé ; le second calcul ne resert pas la durée perturbée |
| R10 | Même agent, mêmes options, une fois avec et une fois sans accident actif | Deux clés de cache de décision distinctes |
| R21 | Poser un accident près d'un point, régime actif | L'accident est accroché à l'arête la plus proche et ralentit sur sa fenêtre |
| R21 | Poser un accident, régime décoché | Refus explicite, alarme au journal, état du monde inchangé |
| R11 | Run d'une journée sans aucun accident tiré | Le journal porte une ligne `accidents tirés=0, déplacements touchés=0` |
| R12 | Pose d'un accident sur une arête inconnue, ou de durée `0` | Refus journalisé nommant l'arête et la valeur ; état du monde inchangé |
| R13 | Deux runs, même graine, interrupteur différent | Populations, agendas et bulletins météo identiques |

## Non-goals

- **Le facteur météo.** Tranché le 2026-09-21 : la météo ne conditionne pas l'accidentalité,
  et ce n'est pas remis à plus tard. Raison principale, mesurée : **les conditions à risque
  n'existent pas dans le monde simulé** — sur les 2 920 créneaux d'une année servie par
  `weather_loader`, le brouillard en occupe **1** et la neige **4**, et le jeu gelé
  `jeu-20260316` n'en porte aucun. Estimer un coefficient pour une condition absente du jeu de
  données serait sans objet. Raison seconde : pour les conditions qui restent, `atm` et la
  source météo locale sont incommensurables. Seul un jeu météo portant réellement ces
  conditions rouvrirait la question.
- **La normalisation par les kilomètres de réseau.** Elle n'a pas lieu d'être pour les
  variables tirées — c'est la conclusion de la mesure, pas un renoncement : diviser par
  l'exposition donnerait un risque par véhicule-km, quand le tirage a besoin d'une fréquence
  d'événements. Les kilomètres par classe restent publiés comme contrôle.
- **Le souvenir** de l'agent retardé (travail G). Pour l'écrire il faudrait que « ce trajet a
  traversé un accident, +N min » remonte du routage — seul endroit qui connaisse les arêtes —
  jusqu'à l'agent, en traversant le `TravelPlan`. La chaîne mémoire est par ailleurs en cours
  de refonte (tickets 071 et 075) : y écrire maintenant entrerait en collision.
- **Le contournement** : l'agent subit le retard, il ne recalcule pas son itinéraire pour
  éviter l'accident. Le chemin est choisi en temps LIBRE avant que le surcoût ne s'applique ;
  contourner demanderait de recalculer le plus court chemin sur des poids modifiés.
- **Faire rouler les agents sur le graphe routier** — chantier séparé, hors sujet ici.
- **L'agent victime** d'un accident : hors d'atteinte des cohortes (0,0025 agent par journée).
- **Toute figure ou résultat publiable** : l'exposition mesurée (38,5 déplacements touchés par
  journée à 1 000 agents) interdit d'en tirer une conclusion chiffrée, et ce n'est pas le but
  de cette tranche.

## Sécurité

- **Qui peut faire quoi** : seul l'expérimentateur devant l'IHM décide de l'état. Le contrôleur
  applique ; aucun agent, aucun modèle de langue ne peut activer ou désactiver le régime.
- **Entrées hostiles par défaut** : la charge utile du `/init` vient du réseau et n'est pas
  digne de confiance — `accidents_enabled` est validé comme booléen, toute autre valeur est
  refusée plutôt que convertie. Les paramètres de la loi de tirage viennent d'un fichier de
  configuration : un taux négatif, nul ou absurdement grand est refusé au chargement.
- **Données sensibles** : aucune. Les accidents sont synthétiques, aucune donnée personnelle
  n'entre dans le mécanisme.
- **Ce qui ne doit jamais fuiter dans le prompt** : la gravité et le mot « accident ». L'agent
  ne reçoit que des **minutes** — un conducteur coincé ne sait pas ce qui bloque devant lui.
  Une fuite lexicale invaliderait toute expérience ultérieure en suggérant la réponse.
- **Contamination croisée** : R9 et R10 sont des règles de sécurité autant que de correction.
  Un cache empoisonné par une durée perturbée fausse des runs qui n'ont rien demandé, sans
  qu'aucun journal ne le signale.

## Questions ouvertes

1. **Périmètre de cette tranche.** La spec couvre l'interrupteur *et* ce qu'il commande
   (tirage à taux constant + retard subi). Faut-il au contraire livrer d'abord
   l'interrupteur seul, inerte ? Je le déconseille : un interrupteur qui n'allume rien
   produit un run étiqueté « accidents actifs » avec zéro effet, indiscernable d'un run cassé.
2. ~~**Le taux provisoire.**~~ **Tranché par la mesure du 2026-09-14** : 1,558 accident/jour
   dans l'emprise du graphe (3 414 des 3 789 accidents du département y tombent). Le champ
   `accidents.taux_journalier` reste disponible comme surcharge de développement, `None` par
   défaut.
3. ~~**Le facteur météo, établi comment ?**~~ **Tranché le 2026-09-21** : la météo reste sans
   effet sur l'accidentalité. La question était mal posée — on cherchait à mieux estimer un
   coefficient sans vérifier que la condition existe dans le jeu de données servi. Elle n'y
   est pas.
4. **L'ampleur du retard.** Aucune source n'en donne aujourd'hui (le flux DATEX n'est pas
   archivé). C'est un paramètre exogène : passe-t-il par
   `docs/arch/protocole-parametre-exogene.md` dès cette tranche, ou porte-t-il une valeur
   déclarée « hypothèse » dans la configuration ?
5. **Le mode hors-ligne.** L'interrupteur doit-il être pilotable depuis `make run OFFLINE=1`
   sans passer par l'IHM ? Le lanceur headless écrit-il dans `sim_params.yaml` ?
